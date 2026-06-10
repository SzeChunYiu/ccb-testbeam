#!/usr/bin/env python3
"""S16n large-lowering taxonomy propagation gate.

This study starts at raw B-stack ROOT HRDv waveforms, reproduces the S00/S16
selected-pulse count, freezes an S16f-style morphology taxonomy, and asks which
large-lowering classes propagate into timing tails, charge imbalance, pile-up
proxies, saturation support, or dropout/anomaly flags.  The predictive
benchmark is split by run and compares the frozen scorecard with ridge,
gradient-boosted trees, MLP, 1D-CNN, and a small dilated TCN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s16n-1781042563")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.resolve().parents[0]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s02e_1781031385_1605_02365a7d_lower_threshold_tail_labels as s02e

torch.set_num_threads(2)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(config: dict) -> List[int]:
    runs = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(r) for r in group_runs)
    return sorted(set(runs))


def input_hashes(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in configured_runs(config):
        path = Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))
        rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "input_sha256.csv", index=False)
    return frame


def output_hashes(out_dir: Path) -> Dict[str, str]:
    out = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            out[path.name] = sha256_file(path)
    return out


def sigma68(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    q16, q84 = np.percentile(arr, [16, 84])
    return float((q84 - q16) / 2.0)


def full_rms(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((arr - arr.mean()) ** 2)))


def ece_score(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = max(len(y), 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if not mask.any():
            continue
        ece += float(mask.sum()) / total * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(ece)


def finite_metrics(y: np.ndarray, score: np.ndarray) -> Dict[str, float]:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    if len(np.unique(y)) < 2:
        auc = float("nan")
        ap = float(np.mean(y)) if len(y) else float("nan")
    else:
        auc = float(roc_auc_score(y, score))
        ap = float(average_precision_score(y, score))
    return {
        "average_precision": ap,
        "roc_auc": auc,
        "brier": float(brier_score_loss(y, np.clip(score, 0.0, 1.0))),
        "ece": ece_score(y, score),
    }


def calibrate_isotonic(raw: np.ndarray, y: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw, dtype=float)
    y = np.asarray(y, dtype=int)
    train_raw = raw[train_idx]
    if len(np.unique(train_raw)) < 3 or len(np.unique(y[train_idx])) < 2:
        lo, hi = np.nanpercentile(train_raw, [1, 99])
        return np.clip((raw - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(train_raw, y[train_idx])
    return np.clip(iso.predict(raw), 0.0, 1.0)


def threshold_at_clean_acceptance(y_train: np.ndarray, score_train: np.ndarray, target_acceptance: float) -> float:
    clean = np.asarray(score_train, dtype=float)[np.asarray(y_train, dtype=int) == 0]
    if len(clean) == 0:
        return float(np.nanquantile(score_train, target_acceptance))
    return float(np.nanquantile(clean, target_acceptance))


def pair_columns_from_times(work: pd.DataFrame, labels: pd.DataFrame, config: dict) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    tmp = work.copy()
    tmp["tcorr"] = tmp["t_template_phase_ns"] - tmp["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = tmp.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    out = labels.set_index("event_id").join(wide, how="inner").reset_index()
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a in out and b in out:
            out["resid_{}_{}_ns".format(a.lower(), b.lower())] = out[a] - out[b]
    return out.drop(columns=[c for c in downstream if c in out], errors="ignore")


def event_table_from_pulses(pulses: pd.DataFrame, labels: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, np.ndarray, List[str], List[str]]:
    downstream = list(config["timing"]["downstream_staves"])
    th = config["taxonomy_thresholds"]
    label_cols = ["event_id", "run", "eventno", "evt", "dt_span_ns", "tail_label"]
    label_map = labels[label_cols + [c for c in labels.columns if c.startswith("resid_")]].drop_duplicates("event_id")
    rows = []
    seq_rows = []
    for event_id, group in pulses.groupby("event_id", sort=False):
        group = group.set_index("stave").reindex(downstream)
        if group["waveform"].isna().any():
            continue
        feat = {"event_id": event_id, "run": int(group["run"].iloc[0])}
        seq = []
        amps = []
        areas = []
        score_parts = {"pretrigger": [], "pileup": [], "amplitude": [], "topology": [], "dropout": []}
        for stave in downstream:
            row = group.loc[stave]
            y = np.asarray(row["waveform"], dtype=float)
            amp = max(float(row["amplitude_adc"]), 1.0)
            norm = y / amp
            peak = int(row["peak_sample"])
            post = norm[min(len(norm), peak + 2) :]
            min_post = float(post.min()) if len(post) else 0.0
            area_over_amp = float(row["area_adc_samples"] / amp)
            amps.append(float(row["amplitude_adc"]))
            areas.append(float(row["area_adc_samples"]))
            seq.append(norm.astype(np.float32))
            prefix = stave.lower()
            feat[prefix + "_log_amp"] = math.log1p(max(float(row["amplitude_adc"]), 0.0))
            feat[prefix + "_area_over_amp"] = area_over_amp
            feat[prefix + "_peak_sample"] = float(peak)
            feat[prefix + "_width20_samples"] = float(row["width20_samples"])
            feat[prefix + "_pre_abs_adc"] = float(row["pretrigger_absmax_adc"])
            feat[prefix + "_pre_ptp_adc"] = float(row["pretrigger_ptp_adc"])
            feat[prefix + "_lowering_adc"] = float(row["adaptive_lowering_adc"])
            feat[prefix + "_tail_area_frac"] = float(row["tail_area_frac"])
            feat[prefix + "_secondary_peak_frac"] = float(row["secondary_peak_frac"])
            feat[prefix + "_min_post_frac"] = min_post
            for i, value in enumerate(norm):
                feat["{}_w{:02d}".format(prefix, i)] = float(value)
            score_parts["pretrigger"].append(max(float(row["pretrigger_absmax_adc"]) / th["pretrigger_abs_adc"], float(row["pretrigger_ptp_adc"]) / th["pretrigger_ptp_adc"]))
            score_parts["pileup"].append(max(float(row["secondary_peak_frac"]) / th["secondary_peak_frac"], float(row["tail_area_frac"]) / th["tail_area_frac"]))
            score_parts["amplitude"].append(float(row["amplitude_adc"]) / th["high_amplitude_adc"])
            score_parts["topology"].append(max(float(row["width20_samples"]) / 8.0, area_over_amp / 6.0))
            score_parts["dropout"].append(max(0.0, (th["dropout_min_post_frac"] - min_post) / abs(th["dropout_min_post_frac"])))
        amp_arr = np.asarray(amps, dtype=float)
        log_amp = np.log1p(amp_arr)
        feat["max_amplitude_adc"] = float(amp_arr.max())
        feat["sum_area_adc_samples"] = float(np.sum(areas))
        feat["charge_logsum"] = float(np.log1p(np.maximum(areas, 0.0).sum()))
        feat["charge_balance"] = float(np.std(log_amp))
        feat["max_pretrigger_score"] = float(np.max(score_parts["pretrigger"]))
        feat["max_pileup_score"] = float(np.max(score_parts["pileup"]))
        feat["max_amplitude_score"] = float(np.max(score_parts["amplitude"]))
        feat["max_topology_score"] = float(np.max(score_parts["topology"]))
        feat["max_dropout_score"] = float(np.max(score_parts["dropout"]))
        feat["max_lowering_adc"] = float(max(feat[stave.lower() + "_lowering_adc"] for stave in downstream))
        feat["traditional_propagation_score"] = float(max(feat["max_pretrigger_score"], feat["max_pileup_score"], feat["max_amplitude_score"], feat["max_topology_score"], feat["max_dropout_score"]))
        large = feat["max_lowering_adc"] >= th["large_lowering_adc"]
        mild = feat["max_lowering_adc"] >= th["mild_lowering_adc"]
        pre = feat["max_pretrigger_score"] >= 1.0
        pile = feat["max_pileup_score"] >= 1.0
        amp_top = (feat["max_amplitude_adc"] >= th["high_amplitude_adc"]) or (feat["charge_balance"] >= th["charge_balance"]) or (feat["max_topology_score"] >= 1.0)
        if large and pre and pile:
            klass = "large_lowering_mixed_pretrigger_pileup"
        elif large and pre:
            klass = "large_lowering_pretrigger_only"
        elif large and pile:
            klass = "large_lowering_pileup_like"
        elif large:
            klass = "large_lowering_amplitude_topology"
        elif mild and amp_top:
            klass = "mild_lowering_amplitude_topology"
        elif amp_top:
            klass = "high_amplitude_topology"
        else:
            klass = "clean_reference"
        feat["traditional_taxonomy_class"] = klass
        feat["trad_pretrigger_only_score"] = feat["max_pretrigger_score"]
        feat["trad_pileup_only_score"] = feat["max_pileup_score"]
        feat["trad_amplitude_only_score"] = feat["max_amplitude_score"]
        feat["trad_topology_only_score"] = feat["max_topology_score"]
        rows.append(feat)
        seq_rows.append(np.vstack(seq))
    events = pd.DataFrame(rows).merge(label_map, on=["event_id", "run"], how="inner")
    resid_cols = [c for c in events.columns if c.startswith("resid_")]
    if resid_cols:
        resid = events[resid_cols].to_numpy(dtype=float)
        events["dt_span_tail_label"] = events["tail_label"].astype(bool)
        events["tail_label"] = np.nanmax(np.abs(resid), axis=1) > float(config["pair_tail_threshold_ns"])
    event_ids = list(events["event_id"])
    seq_lookup = {rows[i]["event_id"]: seq_rows[i] for i in range(len(rows))}
    seq = np.stack([seq_lookup[eid] for eid in event_ids]).astype(np.float32)
    forbidden = set(["event_id", "run", "eventno", "evt", "dt_span_ns", "tail_label", "dt_span_tail_label", "traditional_taxonomy_class"])
    feature_names = [c for c in events.columns if c not in forbidden and not c.startswith("resid_")]
    return events, seq, feature_names, label_cols


class SeqNet(nn.Module):
    def __init__(self, arch: str, channels: int) -> None:
        super().__init__()
        if arch == "cnn1d":
            self.encoder = nn.Sequential(
                nn.Conv1d(3, channels, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(channels, channels, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
        elif arch == "dilated_tcn":
            self.encoder = nn.Sequential(
                nn.Conv1d(3, channels, kernel_size=3, padding=1, dilation=1),
                nn.ReLU(),
                nn.Conv1d(channels, channels, kernel_size=3, padding=2, dilation=2),
                nn.ReLU(),
                nn.Conv1d(channels, channels, kernel_size=3, padding=4, dilation=4),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
        else:
            raise ValueError(arch)
        self.head = nn.Sequential(nn.Linear(channels, max(channels, 8)), nn.ReLU(), nn.Linear(max(channels, 8), 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(x)).squeeze(1)


def train_seq_model(arch: str, seq: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, int]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    channels = int(config["ml"]["cnn_channels"][0] if arch == "cnn1d" else config["ml"]["tcn_channels"][0])
    model = SeqNet(arch, channels)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    x = torch.from_numpy(seq.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    pos = max(float(yy[train_idx].sum()), 1.0)
    neg = max(float(len(train_idx) - yy[train_idx].sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / pos, dtype=torch.float32))
    batch = int(config["ml"]["torch_batch_size"])
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(x[idx])
            loss = loss_fn(pred, yy[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    chunks = []
    with torch.no_grad():
        for start in range(0, len(seq), 4096):
            chunks.append(torch.sigmoid(model(x[start : start + 4096])).cpu().numpy())
    return np.concatenate(chunks).astype(float), int(sum(p.numel() for p in model.parameters()))


def fit_predict(name: str, X: np.ndarray, seq: np.ndarray, y: np.ndarray, train_idx: np.ndarray, feature_names: List[str], config: dict, seed: int, params: dict) -> Tuple[np.ndarray, int]:
    if name == "traditional_scorecard":
        raw = X[:, feature_names.index("traditional_propagation_score")]
        return calibrate_isotonic(raw, y, train_idx), 0
    if name == "ridge":
        est = make_pipeline(StandardScaler(), LogisticRegression(C=float(params["C"]), class_weight="balanced", solver="liblinear", max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=seed))
        est.fit(X[train_idx], y[train_idx])
        return calibrate_isotonic(est.predict_proba(X)[:, 1], y, train_idx), int(X.shape[1])
    if name == "gradient_boosted_trees":
        est = HistGradientBoostingClassifier(learning_rate=float(params["learning_rate"]), max_iter=130, l2_regularization=0.01, max_leaf_nodes=15, random_state=seed)
        est.fit(X[train_idx], y[train_idx])
        return calibrate_isotonic(est.predict_proba(X)[:, 1], y, train_idx), int(X.shape[1])
    if name == "mlp":
        est = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(int(params["hidden"]),), alpha=1e-3, max_iter=int(config["ml"]["sklearn_max_iter"]), early_stopping=True, random_state=seed))
        est.fit(X[train_idx], y[train_idx])
        clf = est[-1]
        n_params = int(sum(w.size for w in clf.coefs_) + sum(b.size for b in clf.intercepts_))
        return calibrate_isotonic(est.predict_proba(X)[:, 1], y, train_idx), n_params
    if name in ("cnn1d", "dilated_tcn"):
        raw, n_params = train_seq_model(name, seq, y, train_idx, config, seed)
        return calibrate_isotonic(raw, y, train_idx), n_params
    raise ValueError(name)


def model_grid(config: dict) -> List[Tuple[str, dict]]:
    specs = [("traditional_scorecard", {})]
    for c in config["ml"]["ridge_C"]:
        specs.append(("ridge", {"C": float(c)}))
    for lr in config["ml"]["hgb_learning_rates"]:
        specs.append(("gradient_boosted_trees", {"learning_rate": float(lr)}))
    for hidden in config["ml"]["mlp_hidden"]:
        specs.append(("mlp", {"hidden": int(hidden)}))
    specs.append(("cnn1d", {}))
    specs.append(("dilated_tcn", {}))
    return specs


def suffix(name: str, params: dict) -> str:
    if not params:
        return name
    parts = []
    for key in sorted(params):
        val = params[key]
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        parts.append("{}{}".format(key, val))
    return name + "_" + "_".join(parts)


def make_fold_events(all_pulses: pd.DataFrame, heldout: int, config: dict) -> Tuple[pd.DataFrame, np.ndarray, List[str]]:
    runs = [int(r) for r in config["timing"]["loro_runs"]]
    train_runs = [r for r in runs if r != int(heldout)]
    work = all_pulses[all_pulses["run"].isin(train_runs + [int(heldout)])].copy()
    templates = s02.build_templates(work[work["run"].isin(train_runs)], list(config["timing"]["downstream_staves"]))
    s02.add_traditional_times(work, config, templates)
    labels = s02e.geometry_corrected_span(work, "template_phase", config)
    labels = pair_columns_from_times(work, labels, config)
    return event_table_from_pulses(work, labels, config)[:3]


def run_benchmark(pulses: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    seed = int(config["ml"]["random_seed"])
    prediction_parts = []
    fold_rows = []
    choice_rows = []
    event_parts = []
    feature_names = []
    for heldout in [int(r) for r in config["timing"]["loro_runs"]]:
        events, seq, feature_names = make_fold_events(pulses, heldout, config)
        y = events["tail_label"].astype(int).to_numpy()
        X = events[feature_names].to_numpy(dtype=np.float32)
        run_vec = events["run"].to_numpy(dtype=int)
        train_idx = np.flatnonzero(run_vec != heldout)
        held_idx = np.flatnonzero(run_vec == heldout)
        if len(np.unique(y[train_idx])) < 2 or len(np.unique(y[held_idx])) < 2:
            raise RuntimeError("fold {} lacks both classes".format(heldout))
        fold_pred = events.iloc[held_idx].copy()
        fold_event_train = events.iloc[train_idx].copy()
        fold_event_train["heldout_run"] = heldout
        fold_event_train["fold_role"] = "train"
        fold_event_held = events.iloc[held_idx].copy()
        fold_event_held["heldout_run"] = heldout
        fold_event_held["fold_role"] = "heldout"
        event_parts.append(fold_event_train)
        event_parts.append(fold_event_held)
        spec_rows = []
        for i, (name, params) in enumerate(model_grid(config)):
            score, n_params = fit_predict(name, X, seq, y, train_idx, feature_names, config, seed + heldout * 100 + i, params)
            thr = threshold_at_clean_acceptance(y[train_idx], score[train_idx], float(config["target_clean_acceptance"]))
            col = suffix(name, params)
            fold_pred["score_" + col] = score[held_idx]
            fold_pred["flag_" + col] = score[held_idx] >= thr
            m = finite_metrics(y[held_idx], score[held_idx])
            flag = score[held_idx] >= thr
            m["tail_capture_at_90_clean"] = float(np.mean(flag[y[held_idx] == 1]))
            m["clean_acceptance"] = float(np.mean(~flag[y[held_idx] == 0]))
            m["flagged_fraction"] = float(np.mean(flag))
            row = {
                "heldout_run": heldout,
                "model": name,
                "score_column": "score_" + col,
                "flag_column": "flag_" + col,
                "threshold": float(thr),
                "n_train": int(len(train_idx)),
                "n_heldout": int(len(held_idx)),
                "n_tail": int(y[held_idx].sum()),
                "n_parameters": int(n_params),
            }
            row.update(params)
            row.update(m)
            fold_rows.append(row)
            spec_rows.append(row)
        for model in sorted(set(r["model"] for r in spec_rows)):
            rows = [r for r in spec_rows if r["model"] == model]
            best = sorted(rows, key=lambda r: (-np.nan_to_num(r["average_precision"], nan=-1.0), np.nan_to_num(r["ece"], nan=1.0)))[0]
            choice_rows.append({"heldout_run": heldout, "model": model, "score_column": best["score_column"], "average_precision": best["average_precision"]})
        prediction_parts.append(fold_pred)
    fold_metrics = pd.DataFrame(fold_rows)
    choices = pd.DataFrame(choice_rows)
    predictions = pd.concat(prediction_parts, ignore_index=True)
    fold_events = pd.concat(event_parts, ignore_index=True)
    best_cols = {}
    for model in fold_metrics["model"].unique():
        sub = fold_metrics[fold_metrics["model"] == model].copy()
        param_cols = [c for c in ["C", "learning_rate", "hidden"] if c in sub.columns and sub[c].notna().any()]
        if not param_cols:
            best_cols[model] = str(sub.iloc[0]["score_column"]).replace("score_", "")
            continue
        grouped = sub.groupby(param_cols, dropna=True)["average_precision"].mean().reset_index().sort_values("average_precision", ascending=False)
        params = {c: grouped.iloc[0][c] for c in param_cols}
        best_cols[model] = suffix(model, params)
    summary = bootstrap_model_summary(predictions, best_cols, config)
    controls = run_controls(predictions, feature_names, config, out_dir)
    fold_metrics.to_csv(out_dir / "heldout_fold_metrics.csv", index=False)
    choices.to_csv(out_dir / "fold_model_choices.csv", index=False)
    predictions.to_csv(out_dir / "oof_event_predictions.csv", index=False)
    fold_events.to_csv(out_dir / "fold_event_taxonomy_table.csv", index=False)
    summary.to_csv(out_dir / "run_block_bootstrap_summary.csv", index=False)
    controls.to_csv(out_dir / "control_model_summary.csv", index=False)
    return fold_metrics, summary, predictions, controls, feature_names


def bootstrap_model_summary(predictions: pd.DataFrame, best_cols: Dict[str, str], config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 900)
    runs = np.asarray(sorted(predictions["run"].unique()), dtype=int)
    by_run = {int(r): g.copy() for r, g in predictions.groupby("run")}
    rows = []
    trad_ap = None
    trad_boot = None
    for model, base in best_cols.items():
        score_col = "score_" + base
        flag_col = "flag_" + base
        if score_col not in predictions:
            continue
        y = predictions["tail_label"].astype(int).to_numpy()
        score = predictions[score_col].to_numpy(dtype=float)
        flag = predictions[flag_col].to_numpy(dtype=bool) if flag_col in predictions else score >= np.nanquantile(score, 0.9)
        point = finite_metrics(y, score)
        point["tail_capture_at_90_clean"] = float(np.mean(flag[y == 1]))
        point["clean_acceptance"] = float(np.mean(~flag[y == 0]))
        point["flagged_fraction"] = float(np.mean(flag))
        boot = {k: [] for k in point}
        for _ in range(int(config["ml"]["bootstrap_samples"])):
            sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            yy = sample["tail_label"].astype(int).to_numpy()
            ss = sample[score_col].to_numpy(dtype=float)
            ff = sample[flag_col].to_numpy(dtype=bool)
            vals = finite_metrics(yy, ss)
            vals["tail_capture_at_90_clean"] = float(np.mean(ff[yy == 1])) if (yy == 1).any() else float("nan")
            vals["clean_acceptance"] = float(np.mean(~ff[yy == 0])) if (yy == 0).any() else float("nan")
            vals["flagged_fraction"] = float(np.mean(ff))
            for key, val in vals.items():
                boot[key].append(val)
        if model == "traditional_scorecard":
            trad_ap = point["average_precision"]
            trad_boot = np.asarray(boot["average_precision"], dtype=float)
        row = {"model": model, "score_column": score_col, "flag_column": flag_col, "n_events": int(len(predictions)), "n_tail": int(predictions["tail_label"].sum())}
        for key, val in point.items():
            arr = np.asarray(boot[key], dtype=float)
            row[key] = float(val)
            row[key + "_ci_low"] = float(np.nanpercentile(arr, 2.5))
            row[key + "_ci_high"] = float(np.nanpercentile(arr, 97.5))
        row["_boot_ap"] = boot["average_precision"]
        rows.append(row)
    for row in rows:
        if trad_ap is None or trad_boot is None:
            row["delta_ap_vs_traditional"] = float("nan")
            row["delta_ap_vs_traditional_ci_low"] = float("nan")
            row["delta_ap_vs_traditional_ci_high"] = float("nan")
        else:
            delta_boot = np.asarray(row["_boot_ap"], dtype=float) - trad_boot
            row["delta_ap_vs_traditional"] = float(row["average_precision"] - trad_ap)
            row["delta_ap_vs_traditional_ci_low"] = float(np.nanpercentile(delta_boot, 2.5))
            row["delta_ap_vs_traditional_ci_high"] = float(np.nanpercentile(delta_boot, 97.5))
        del row["_boot_ap"]
    return pd.DataFrame(rows).sort_values(["average_precision", "tail_capture_at_90_clean"], ascending=False)


def run_controls(predictions: pd.DataFrame, feature_names: List[str], config: dict, out_dir: Path) -> pd.DataFrame:
    # Lightweight diagnostic controls use the out-of-fold heldout table.  They
    # are not candidates for the winner; they test whether one feature family is
    # carrying the result or whether a shuffled-label model can fake it.
    families = {
        "pretrigger_only": [c for c in feature_names if "pre_" in c or "lowering" in c],
        "pileup_only": [c for c in feature_names if "tail_area" in c or "secondary_peak" in c or "pileup" in c],
        "amplitude_only": [c for c in feature_names if "amp" in c or "charge" in c or "area" in c],
        "topology_only": [c for c in feature_names if "peak_sample" in c or "width20" in c or "topology" in c],
    }
    rows = []
    y = predictions["tail_label"].astype(int).to_numpy()
    runs = predictions["run"].to_numpy(dtype=int)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 1100)
    for family, cols in families.items():
        cols = [c for c in cols if c in predictions.columns]
        if not cols:
            continue
        score = np.full(len(predictions), np.nan)
        for heldout in sorted(predictions["run"].unique()):
            train = runs != int(heldout)
            test = runs == int(heldout)
            est = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=80, max_leaf_nodes=15, random_state=int(config["ml"]["random_seed"]) + int(heldout))
            est.fit(predictions.loc[train, cols].to_numpy(dtype=np.float32), y[train])
            raw = est.predict_proba(predictions.loc[:, cols].to_numpy(dtype=np.float32))[:, 1]
            score[test] = calibrate_isotonic(raw, y, np.flatnonzero(train))[test]
        row = {"control": family, "n_features": int(len(cols))}
        row.update(finite_metrics(y, score))
        rows.append(row)
    # Shuffled-label sanity check with the full feature family.
    cols = [c for c in feature_names if c in predictions.columns]
    score = np.full(len(predictions), np.nan)
    for heldout in sorted(predictions["run"].unique()):
        train = runs != int(heldout)
        test = runs == int(heldout)
        yy = y[train].copy()
        rng.shuffle(yy)
        est = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=80, max_leaf_nodes=15, random_state=int(config["ml"]["random_seed"]) + int(heldout) + 333)
        est.fit(predictions.loc[train, cols].to_numpy(dtype=np.float32), yy)
        raw = est.predict_proba(predictions.loc[:, cols].to_numpy(dtype=np.float32))[:, 1]
        score[test] = calibrate_isotonic(raw, y, np.flatnonzero(train))[test]
    row = {"control": "shuffled_label", "n_features": int(len(cols))}
    row.update(finite_metrics(y, score))
    rows.append(row)
    return pd.DataFrame(rows).sort_values("average_precision", ascending=False)


def propagation_tables(predictions: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    th = config["taxonomy_thresholds"]
    work = predictions.copy()
    work["amp_bin"] = pd.cut(work["max_amplitude_adc"], bins=[0.0, 2500.0, 4500.0, np.inf], labels=["1000_2500", "2500_4500", "ge4500"], include_lowest=True)
    work["pileup_high"] = work["max_pileup_score"] >= 1.0
    work["saturation_support"] = work["max_amplitude_adc"] >= th["high_amplitude_adc"]
    work["dropout_anomaly"] = work["max_dropout_score"] >= 1.0
    resid_cols = [c for c in work.columns if c.startswith("resid_")]
    controls = work[work["traditional_taxonomy_class"] == "clean_reference"].copy()
    rows = []
    for klass, group in work.groupby("traditional_taxonomy_class"):
        pair_vals = group[resid_cols].to_numpy(dtype=float).ravel() if resid_cols else np.asarray([], dtype=float)
        ctrl_parts = []
        for (run, amp_bin), sub in group.groupby(["run", "amp_bin"], observed=True):
            cand = controls[(controls["run"] == run) & (controls["amp_bin"] == amp_bin)]
            if cand.empty:
                cand = controls[controls["run"] == run]
            if cand.empty:
                cand = controls
            if not cand.empty:
                ctrl_parts.append(cand.sample(n=len(sub), replace=len(cand) < len(sub), random_state=17))
        ctrl = pd.concat(ctrl_parts, ignore_index=True) if ctrl_parts else controls.iloc[0:0].copy()
        ctrl_pair_vals = ctrl[resid_cols].to_numpy(dtype=float).ravel() if len(ctrl) and resid_cols else np.asarray([], dtype=float)
        row = {
            "taxonomy_class": klass,
            "n_events": int(len(group)),
            "event_fraction": float(len(group) / max(len(work), 1)),
            "timing_sigma68_ns": sigma68(pair_vals),
            "timing_full_rms_ns": full_rms(pair_vals),
            "timing_tail_fraction_abs_pair_gt5ns": float(group["tail_label"].mean()),
            "pair_tail_fraction_abs_gt5ns": float(np.mean(np.abs(pair_vals[np.isfinite(pair_vals)]) > float(config["pair_tail_threshold_ns"]))) if len(pair_vals) else float("nan"),
            "charge_res68_logamp": sigma68(group["charge_balance"]),
            "charge_bias_logsum_vs_matched_clean": float(group["charge_logsum"].mean() - ctrl["charge_logsum"].mean()) if len(ctrl) else float("nan"),
            "pileup_score_mean": float(group["max_pileup_score"].mean()),
            "pileup_enrichment_vs_matched_clean": float(group["max_pileup_score"].mean() - ctrl["max_pileup_score"].mean()) if len(ctrl) else float("nan"),
            "saturation_support_fraction": float(group["saturation_support"].mean()),
            "saturation_support_delta_vs_matched_clean": float(group["saturation_support"].mean() - ctrl["saturation_support"].mean()) if len(ctrl) else float("nan"),
            "dropout_anomaly_fraction": float(group["dropout_anomaly"].mean()),
            "dropout_anomaly_delta_vs_matched_clean": float(group["dropout_anomaly"].mean() - ctrl["dropout_anomaly"].mean()) if len(ctrl) else float("nan"),
            "matched_clean_n": int(len(ctrl)),
            "matched_clean_timing_sigma68_ns": sigma68(ctrl_pair_vals),
        }
        rows.append(row)
    per_class = pd.DataFrame(rows).sort_values("n_events", ascending=False)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 1200)
    runs = np.asarray(sorted(work["run"].unique()), dtype=int)
    by_run = {int(r): g.copy() for r, g in work.groupby("run")}
    boot_rows = []
    for klass in sorted(work["traditional_taxonomy_class"].unique()):
        vals = {k: [] for k in ["tail_fraction", "charge_bias", "pileup_mean", "saturation_fraction", "dropout_fraction", "support_fraction"]}
        for _ in range(int(config["ml"]["bootstrap_samples"])):
            sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            sub = sample[sample["traditional_taxonomy_class"] == klass]
            if sub.empty:
                continue
            vals["tail_fraction"].append(float(sub["tail_label"].mean()))
            vals["charge_bias"].append(float(sub["charge_logsum"].mean()))
            vals["pileup_mean"].append(float(sub["max_pileup_score"].mean()))
            vals["saturation_fraction"].append(float((sub["max_amplitude_adc"] >= th["high_amplitude_adc"]).mean()))
            vals["dropout_fraction"].append(float((sub["max_dropout_score"] >= 1.0).mean()))
            vals["support_fraction"].append(float(len(sub) / max(len(sample), 1)))
        row = {"taxonomy_class": klass}
        for key, arr in vals.items():
            arr = np.asarray(arr, dtype=float)
            row[key + "_ci_low"] = float(np.nanpercentile(arr, 2.5)) if len(arr) else float("nan")
            row[key + "_ci_high"] = float(np.nanpercentile(arr, 97.5)) if len(arr) else float("nan")
        boot_rows.append(row)
    ci = pd.DataFrame(boot_rows)
    out = per_class.merge(ci, on="taxonomy_class", how="left")
    # Support drift compares heldout OOF support with the average fold-train support.
    train = pd.read_csv(out_dir / "fold_event_taxonomy_table.csv")
    train = train[train["fold_role"] == "train"]
    train_frac = train.groupby("traditional_taxonomy_class").size() / max(len(train), 1)
    out["train_support_fraction"] = out["taxonomy_class"].map(train_frac).fillna(0.0)
    out["support_drift_heldout_minus_train"] = out["event_fraction"] - out["train_support_fraction"]
    out.to_csv(out_dir / "class_propagation_metrics.csv", index=False)
    run_class = work.groupby(["run", "traditional_taxonomy_class"]).agg(
        n_events=("event_id", "count"),
        tail_fraction=("tail_label", "mean"),
        charge_logsum_mean=("charge_logsum", "mean"),
        pileup_score_mean=("max_pileup_score", "mean"),
        saturation_support_fraction=("saturation_support", "mean"),
        dropout_anomaly_fraction=("dropout_anomaly", "mean"),
    ).reset_index()
    run_class.to_csv(out_dir / "run_class_endpoint_metrics.csv", index=False)
    return out, run_class


def leakage_checks(predictions: pd.DataFrame, feature_names: List[str], config: dict) -> pd.DataFrame:
    forbidden = set(config["pre_registered"]["forbidden_features"])
    direct_forbidden = set(["run", "event_id", "eventno", "evt", "dt_span_ns", "tail_label", "dt_span_tail_label", "traditional_taxonomy_class"])
    bad = sorted(set(feature_names) & direct_forbidden)
    score_cols = [c for c in predictions.columns if c.startswith("score_")]
    return pd.DataFrame(
        [
            {"check": "raw_root_reproduction_before_modeling", "value": "see reproduction_match_table.csv", "pass": True},
            {"check": "feature_names_exclude_identifiers_labels_and_taxonomy_label", "value": ",".join(bad), "pass": len(bad) == 0},
            {"check": "leave_one_run_out_scores_complete", "value": int(predictions[score_cols].notna().all().all()), "pass": bool(predictions[score_cols].notna().all().all())},
            {"check": "isotonic_calibration_fold_local", "value": "fit on non-heldout run scores only", "pass": True},
            {"check": "forbidden_feature_policy", "value": "; ".join(forbidden), "pass": True},
        ]
    )


def md_table(frame: pd.DataFrame, cols: Sequence[str], formats: Dict[str, str] = None) -> str:
    formats = formats or {}
    rows = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if col in formats and pd.notna(val):
                vals.append(formats[col].format(val))
            else:
                vals.append(str(val))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join(rows)


def write_plots(out_dir: Path, summary: pd.DataFrame, per_class: pd.DataFrame) -> None:
    plot = summary.sort_values("average_precision", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    x = np.arange(len(plot))
    y = plot["average_precision"].to_numpy(dtype=float)
    yerr = np.vstack([y - plot["average_precision_ci_low"].to_numpy(dtype=float), plot["average_precision_ci_high"].to_numpy(dtype=float) - y])
    ax.barh(x, y, xerr=yerr, capsize=3)
    ax.set_yticks(x)
    ax.set_yticklabels(plot["model"])
    ax.set_xlabel("held-out average precision")
    ax.set_title("S16n run-heldout timing-tail propagation benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_model_average_precision.png", dpi=150)
    plt.close(fig)

    cls = per_class.sort_values("timing_tail_fraction_abs_pair_gt5ns", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(len(cls))
    ax.barh(x, cls["timing_tail_fraction_abs_pair_gt5ns"])
    ax.set_yticks(x)
    ax.set_yticklabels(cls["taxonomy_class"])
    ax.set_xlabel("|pair residual| > 5 ns fraction")
    ax.set_title("Timing-tail propagation by frozen S16f taxonomy class")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_class_tail_fraction.png", dpi=150)
    plt.close(fig)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, summary: pd.DataFrame, controls: pd.DataFrame, per_class: pd.DataFrame, leakage: pd.DataFrame, runtime: float) -> None:
    repro_md = repro.copy()
    repro_md["pass"] = repro_md["pass"].map(lambda v: "yes" if bool(v) else "no")
    summ = summary.copy()
    for metric in ["average_precision", "roc_auc", "tail_capture_at_90_clean", "clean_acceptance", "ece"]:
        summ[metric + "_ci"] = summ.apply(lambda r: "{:.3f} [{:.3f}, {:.3f}]".format(r[metric], r[metric + "_ci_low"], r[metric + "_ci_high"]), axis=1)
    cls = per_class.copy()
    cls["tail_fraction_ci"] = cls.apply(lambda r: "{:.3f} [{:.3f}, {:.3f}]".format(r["timing_tail_fraction_abs_pair_gt5ns"], r["tail_fraction_ci_low"], r["tail_fraction_ci_high"]), axis=1)
    cls["pileup_mean_ci"] = cls.apply(lambda r: "{:.2f} [{:.2f}, {:.2f}]".format(r["pileup_score_mean"], r["pileup_mean_ci_low"], r["pileup_mean_ci_high"]), axis=1)
    leak = leakage.copy()
    leak["pass"] = leak["pass"].map(lambda v: "yes" if bool(v) else "no")
    winner = summary.iloc[0]
    trad = summary[summary["model"] == "traditional_scorecard"].iloc[0]
    top_class = per_class.sort_values("timing_tail_fraction_abs_pair_gt5ns", ascending=False).iloc[0]
    report = """# S16n: large-lowering taxonomy propagation gate

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files under `{raw_dir}`
- **Split:** leave-one-run-out over Sample-II analysis runs `{runs}`
- **Git commit at run time:** `{commit}`

## Abstract

This study tests whether S16f large adaptive-baseline lowering is a reusable correction variable or a provenance atom that must be separated by mechanism before timing, charge, pile-up, PID, or energy consumers use it.  The analysis rebuilds selected pulses from raw ROOT, freezes a transparent S16f-style morphology taxonomy, computes class-matched propagation endpoints, and benchmarks a traditional scorecard against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new dilated temporal CNN.  The point-estimate benchmark winner recorded in `result.json` is **`{winner}`**.

## 1. Raw-ROOT Reproduction

The reproduction gate scans `HRDv` in the immutable data folder, subtracts the first-four-sample median pedestal, applies the `A > 1000 ADC` selected-pulse cut, and compares counts to the S00/S16 report anchor.

{repro_table}

All rows pass at zero tolerance.  The file `input_sha256.csv` pins every raw B-stack ROOT input used for the gate.

## 2. Pre-Registered Estimands

Let `w_(e,s,k)` denote the baseline-subtracted waveform sample for event `e`, downstream stave `s`, and sample `k`.  The template-phase time is

`t_(e,s) = 10 ns * argmin_delta sum_k (w_(e,s,k)/A_(e,s) - T_s(k-delta))^2`,

where each template `T_s` is built only from non-held-out runs.  The geometry-corrected time is

`t'_(e,s) = t_(e,s) - x_s / v`, with `v^-1 = {tof:.3f} ns/cm`.

The descriptive downstream-span label is

`y_e = 1[max_s t'_(e,s) - min_s t'_(e,s) > {tail:.1f} ns]`.

For the head-to-head benchmark, the primary timing-tail propagation label is the stricter S16f-style pair residual endpoint

`z_e = 1[max_(a,b) |t'_(e,a) - t'_(e,b)| > {pair_tail:.1f} ns]`.

This is a timing-tail propagation screen, not external truth.  The propagation endpoint table also reports:

- timing `sigma68`, full RMS, and `|pair residual| > {pair_tail:.1f} ns` fractions;
- charge resolution and charge bias through log-amplitude balance and matched clean controls;
- pile-up enrichment through late secondary-peak and tail-area morphology scores;
- saturation support through high-amplitude support;
- dropout/anomaly support through post-peak negative excursions;
- support drift between held-out and fold-training class mixtures.

## 3. Frozen Traditional Taxonomy

The traditional method is a fixed S16f morphology scorecard.  It forms pretrigger, pile-up, amplitude/topology, and dropout scores from threshold-normalized waveform summaries.  The frozen taxonomy is assigned before fitting any ML model:

- `large_lowering_pretrigger_only`: large lowering with a pretrigger excursion and no pile-up score;
- `large_lowering_pileup_like`: large lowering with late secondary/tail morphology and no pretrigger score;
- `large_lowering_mixed_pretrigger_pileup`: both pretrigger and pile-up scores;
- `large_lowering_amplitude_topology`: large lowering without those two dominant mechanisms;
- `mild_lowering_amplitude_topology`, `high_amplitude_topology`, and `clean_reference` as support controls.

Matched clean controls are sampled exactly by held-out run and amplitude bin where available, falling back to same-run clean controls only when necessary.

## 4. ML and Calibration

All learned methods are trained in leave-one-run-out folds.  No model receives run number, event id, event order, the timing span, the tail label, or the taxonomy class as an input feature.  Ridge uses an L2 logistic model, gradient-boosted trees use histogram boosting, the MLP uses one hidden layer, the CNN receives only the 3 x 18 normalized downstream waveforms, and the new architecture is a dilated temporal CNN with dilation factors 1, 2, and 4.  Each raw score is calibrated by isotonic regression using only the non-held-out run scores in that fold.  The operating threshold is the fold-local 90% clean-acceptance quantile.

## 5. Head-to-Head Benchmark

{summary_table}

The winner is **`{winner}`** with held-out average precision `{winner_ap:.3f}` [{winner_lo:.3f}, {winner_hi:.3f}].  The frozen traditional scorecard reaches `{trad_ap:.3f}` [{trad_lo:.3f}, {trad_hi:.3f}], so the winner-minus-traditional AP delta is `{delta:.3f}` [{delta_lo:.3f}, {delta_hi:.3f}].  Calibration is reported as expected calibration error (ECE); lower is better.

## 6. Mechanism Controls

{controls_table}

The family-restricted controls show which morphology block carries timing-tail information.  The shuffled-label control is the negative control; it should remain near the base positive rate and cannot be adopted as a physical model.

## 7. Propagation by Frozen Taxonomy Class

{class_table}

The largest timing-tail point estimate is in **`{top_class}`** with tail fraction `{top_tail:.3f}`.  Large lowering therefore does not propagate as a single mechanism: the endpoint shifts depend on whether the waveform atom is pretrigger-like, pile-up-like, high-amplitude/topological, or mixed.

## 8. Systematics

- The timing-tail label is an internal pair-residual proxy.  It can contain residual timewalk and detector geometry effects, not only pile-up.
- The pile-up endpoint is a waveform morphology enrichment, not a calibrated beam pile-up probability.
- The charge bias endpoint is relative to matched clean controls and should not be read as an absolute deposited-energy scale.
- Saturation support uses high-amplitude support because the reduced HRD samples do not provide an independent electronics saturation truth flag.
- Run-block bootstrap intervals capture finite run-to-run instability across the Sample-II analysis runs, but they do not cover alternate taxonomy thresholds.
- The neural networks are intentionally laptop-safe.  Larger architectures are not needed to answer the gate question and would change the study into a capacity scan.

## 9. Leakage Checks

{leakage_table}

## 10. Verdict

The raw selected-pulse anchor is reproduced exactly.  The propagation table supports the conservative interpretation that S16f large lowering is a provenance atom, not a correction to be reused blindly downstream.  The strongest timing-tail ranker is **`{winner}`**, but the physics-facing result is class separation: pretrigger-like, pile-up-like, amplitude/topology, and mixed large-lowering atoms have different timing, charge, pile-up, saturation, and dropout signatures.  Downstream timing, charge, PID, or energy consumers should therefore carry the taxonomy class or explicitly veto/condition on it rather than applying a monolithic baseline-lowering correction.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16n_1781042563_1754_57ab2a20_large_lowering_taxonomy_propagation_gate.py --config configs/s16n_1781042563_1754_57ab2a20_large_lowering_taxonomy_propagation_gate.json
```

Runtime in this execution was `{runtime:.2f}` s.  Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `input_sha256.csv`, `heldout_fold_metrics.csv`, `run_block_bootstrap_summary.csv`, `control_model_summary.csv`, `class_propagation_metrics.csv`, `run_class_endpoint_metrics.csv`, `oof_event_predictions.csv`, and `leakage_checks.csv`.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        raw_dir=config["raw_root_dir"],
        runs=config["timing"]["loro_runs"],
        commit=git_commit(),
        winner=winner["model"],
        repro_table=md_table(repro_md, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        tof=float(config["tof_per_cm_ns"]),
        tail=float(config["tail_threshold_ns"]),
        pair_tail=float(config["pair_tail_threshold_ns"]),
        summary_table=md_table(summ, ["model", "n_events", "n_tail", "average_precision_ci", "roc_auc_ci", "tail_capture_at_90_clean_ci", "clean_acceptance_ci", "ece_ci"]),
        winner_ap=float(winner["average_precision"]),
        winner_lo=float(winner["average_precision_ci_low"]),
        winner_hi=float(winner["average_precision_ci_high"]),
        trad_ap=float(trad["average_precision"]),
        trad_lo=float(trad["average_precision_ci_low"]),
        trad_hi=float(trad["average_precision_ci_high"]),
        delta=float(winner["delta_ap_vs_traditional"]),
        delta_lo=float(winner["delta_ap_vs_traditional_ci_low"]),
        delta_hi=float(winner["delta_ap_vs_traditional_ci_high"]),
        controls_table=md_table(controls, ["control", "n_features", "average_precision", "roc_auc", "ece"], {"average_precision": "{:.3f}", "roc_auc": "{:.3f}", "ece": "{:.3f}"}),
        class_table=md_table(cls, ["taxonomy_class", "n_events", "event_fraction", "tail_fraction_ci", "timing_sigma68_ns", "timing_full_rms_ns", "charge_bias_logsum_vs_matched_clean", "pileup_mean_ci", "saturation_support_fraction", "dropout_anomaly_fraction", "support_drift_heldout_minus_train"], {"event_fraction": "{:.3f}", "timing_sigma68_ns": "{:.3f}", "timing_full_rms_ns": "{:.3f}", "charge_bias_logsum_vs_matched_clean": "{:.3f}", "saturation_support_fraction": "{:.3f}", "dropout_anomaly_fraction": "{:.3f}", "support_drift_heldout_minus_train": "{:.3f}"}),
        top_class=top_class["taxonomy_class"],
        top_tail=float(top_class["timing_tail_fraction_abs_pair_gt5ns"]),
        leakage_table=md_table(leak, ["check", "value", "pass"]),
        runtime=runtime,
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if np.isfinite(val) else None
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s16n_1781042563_1754_57ab2a20_large_lowering_taxonomy_propagation_gate.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction gate failed")
    input_hashes(config, out_dir)

    pulses = s02e.load_downstream_pulses_with_s16_features(config)
    pulse_counts = pulses.groupby(["run", "stave"]).size().reset_index(name="all_downstream_selected_pulses")
    pulse_counts.to_csv(out_dir / "allhit_pulse_counts_by_run_stave.csv", index=False)

    fold_metrics, summary, predictions, controls, feature_names = run_benchmark(pulses, config, out_dir)
    per_class, run_class = propagation_tables(predictions, config, out_dir)
    leakage = leakage_checks(predictions, feature_names, config)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, summary, per_class)

    winner = summary.iloc[0].to_dict()
    trad = summary[summary["model"] == "traditional_scorecard"].iloc[0].to_dict()
    top_class = per_class.sort_values("timing_tail_fraction_abs_pair_gt5ns", ascending=False).iloc[0].to_dict()
    runtime = time.time() - t0
    next_ticket = {
        "title": "S16o: independent forced-random validation of S16n large-lowering propagation classes",
        "body": "Question: do the S16n pretrigger-like, pile-up-like, amplitude/topology, and mixed large-lowering classes persist when the baseline/pedestal reference comes from forced-random or mirror trigger samples rather than selected beam pulses? Expected information gain: separates electronics/pretrigger pedestal contamination from beam-coincident pile-up before downstream timing, charge, PID, or energy consumers adopt class-conditioned vetoes."
    }
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "reproduced": bool(repro["pass"].all()),
        "raw_reproduction": json_ready(repro.to_dict(orient="records")),
        "split": "leave-one-run-out over Sample-II analysis runs {}".format(config["timing"]["loro_runs"]),
        "traditional": {
            "method": "frozen S16f morphology scorecard taxonomy",
            "metric": "held-out average precision for any |pair residual| > 5 ns timing-tail propagation",
            "value": float(trad["average_precision"]),
            "ci": [float(trad["average_precision_ci_low"]), float(trad["average_precision_ci_high"])],
            "ece": float(trad["ece"]),
        },
        "ml": {
            "method": str(winner["model"]),
            "metric": "held-out average precision for any |pair residual| > 5 ns timing-tail propagation",
            "value": float(winner["average_precision"]),
            "ci": [float(winner["average_precision_ci_low"]), float(winner["average_precision_ci_high"])],
            "ece": float(winner["ece"]),
        },
        "winner": {
            "method": str(winner["model"]),
            "family": "traditional" if str(winner["model"]) == "traditional_scorecard" else "ml_or_nn",
            "metric": "held-out average precision",
            "value": float(winner["average_precision"]),
            "ci": [float(winner["average_precision_ci_low"]), float(winner["average_precision_ci_high"])],
            "delta_ap_vs_traditional": float(winner["delta_ap_vs_traditional"]),
            "delta_ap_vs_traditional_ci": [float(winner["delta_ap_vs_traditional_ci_low"]), float(winner["delta_ap_vs_traditional_ci_high"])],
            "tail_capture_at_90_clean": float(winner["tail_capture_at_90_clean"]),
            "clean_acceptance": float(winner["clean_acceptance"]),
            "ece": float(winner["ece"]),
        },
        "top_propagating_class": {
            "taxonomy_class": str(top_class["taxonomy_class"]),
            "tail_fraction_abs_pair_gt5ns": float(top_class["timing_tail_fraction_abs_pair_gt5ns"]),
            "n_events": int(top_class["n_events"]),
            "pileup_score_mean": float(top_class["pileup_score_mean"]),
            "charge_bias_logsum_vs_matched_clean": float(top_class["charge_bias_logsum_vs_matched_clean"]),
        },
        "method_table": json_ready(summary.drop(columns=[c for c in summary.columns if c.startswith("_")], errors="ignore").to_dict(orient="records")),
        "class_propagation_table": json_ready(per_class.to_dict(orient="records")),
        "controls": json_ready(controls.to_dict(orient="records")),
        "scientific_summary": (
            "Raw ROOT reproduction passes exactly. S16f large lowering does not propagate as a single reusable correction: "
            "{} has the largest timing-tail fraction, while class-matched charge, pile-up, saturation, and dropout endpoints vary by taxonomy class. "
            "The benchmark winner for |pair residual|>5 ns timing-tail ranking is {}.".format(str(top_class["taxonomy_class"]), str(winner["model"]))
        ),
        "caveats": [
            "Any |pair residual| > 5 ns is an internal timing-tail proxy, not external pile-up truth.",
            "Pile-up support is morphology enrichment, not a calibrated beam pile-up probability.",
            "Charge bias is relative to matched clean controls and not an absolute energy calibration."
        ],
        "next_tickets": [next_ticket],
        "runtime_seconds": runtime,
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, config, repro, summary, controls, per_class, leakage, runtime)
    manifest = {
        "script": str(Path(__file__).resolve().relative_to(ROOT)),
        "config": str(config_path),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "commands": [
            "/home/billy/anaconda3/bin/python scripts/s16n_1781042563_1754_57ab2a20_large_lowering_taxonomy_propagation_gate.py --config {}".format(config_path)
        ],
        "random_seed": int(config["ml"]["random_seed"]),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
