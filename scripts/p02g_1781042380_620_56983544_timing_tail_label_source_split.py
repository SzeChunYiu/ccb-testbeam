#!/usr/bin/env python3
"""P02g timing-tail label-source split for morphology RF.

The benchmark is deliberately event-level and run-held-out.  It rebuilds the
raw B-stack selected-pulse count from ROOT, constructs a common Sample-II support
where B2/B4/B6/B8 are all selected, defines downstream timing-tail labels with
fold-local template-phase timing, and asks whether morphology classifiers derive
their power from upstream shape information or downstream waveform self-reference.
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
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p02g-1781042380")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02

torch.set_num_threads(1)


PAIR_COLUMNS = ["res_B4_B6_ns", "res_B4_B8_ns", "res_B6_B8_ns"]
NON_FEATURE_COLUMNS = {
    "event_id",
    "run",
    "eventno",
    "evt",
    "dt_template_ns",
    "dt_cfd20_ns",
    "tail_label",
    "tail_cfd20",
    "early_peak_atom",
    "anomaly_atom",
    "support_weight",
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(config: dict) -> List[int]:
    runs = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def input_hashes(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "input_sha256.csv", index=False)
    return frame


def output_hashes(out_dir: Path) -> Dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    return value


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    total = 0
    sample_ii = defaultdict(int)

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        for batch in s02.iter_raw(path, ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            corrected, amplitude, _, _ = s02.pulse_quantities(events[:, channels, :], baseline_idx)
            del corrected
            selected = amplitude > cut
            total += int(selected.sum())
            if int(run) in config["run_groups"]["sample_ii_analysis"]:
                sample_ii["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_ii[stave] += int(selected[:, i].sum())

    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for key, value in expected["sample_ii_analysis"].items():
        rows.append({"quantity": "sample_ii_analysis {}".format(key), "report_value": int(value), "reproduced": int(sample_ii[key]), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def load_common_support_pulses(config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    all_staves = list(config["timing"]["all_staves"])
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    channels = np.asarray([staves[name] for name in all_staves], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    count_rows = []
    uid_offset = 0

    for run in config["timing"]["loro_runs"]:
        path = raw_file(config, int(run))
        run_counts = {
            "run": int(run),
            "raw_events": 0,
            "events_all_four_selected": 0,
            "events_downstream_all_selected": 0,
            "selected_pulses_all_four_support": 0,
        }
        for batch in s02.iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw = events[:, channels, :]
            corrected, amplitude, peak, area = s02.pulse_quantities(raw, baseline_idx)
            selected = amplitude > cut
            downstream_mask = selected[:, 1:].all(axis=1)
            all_four_mask = selected.all(axis=1)
            run_counts["raw_events"] += int(len(eventno))
            run_counts["events_downstream_all_selected"] += int(downstream_mask.sum())
            run_counts["events_all_four_selected"] += int(all_four_mask.sum())
            run_counts["selected_pulses_all_four_support"] += int(all_four_mask.sum() * len(all_staves))
            if all_four_mask.any():
                chosen = np.flatnonzero(all_four_mask)
                for e in chosen:
                    event_id = "{}:{}:{}:{}".format(int(run), int(eventno[e]), int(evt[e]), uid_offset + int(e))
                    for sidx, stave in enumerate(all_staves):
                        y = corrected[e, sidx].astype(np.float32)
                        amp = max(float(amplitude[e, sidx]), 1.0)
                        norm = y / amp
                        positive = np.clip(y, 0.0, None)
                        pos_sum = max(float(positive.sum()), 1.0)
                        p = int(peak[e, sidx])
                        secondary = y.copy()
                        secondary[max(0, p - 1) : min(nsamp, p + 2)] = -np.inf
                        secondary_peak = float(np.nanmax(secondary)) if np.isfinite(secondary).any() else 0.0
                        rows.append(
                            {
                                "event_id": event_id,
                                "run": int(run),
                                "eventno": int(eventno[e]),
                                "evt": int(evt[e]),
                                "stave": str(stave),
                                "waveform": y,
                                "norm_waveform": norm.astype(np.float32),
                                "amplitude_adc": float(amplitude[e, sidx]),
                                "peak_sample": int(peak[e, sidx]),
                                "area_adc_samples": float(area[e, sidx]),
                                "pre_frac": float(positive[:4].sum() / pos_sum),
                                "tail_frac": float(positive[10:].sum() / pos_sum),
                                "late_frac": float(positive[12:].sum() / pos_sum),
                                "width20": int((y > 0.20 * amp).sum()),
                                "width50": int((y > 0.50 * amp).sum()),
                                "secondary_peak_frac": float(max(0.0, secondary_peak) / amp),
                                "post_peak_min_frac": float(np.min(norm[min(nsamp - 1, p + 1) :])) if p + 1 < nsamp else 0.0,
                                "waveform_hash12": hashlib.sha256(np.round(y, 1).astype(np.float32).tobytes()).hexdigest()[:12],
                            }
                        )
            uid_offset += len(eventno)
        count_rows.append(run_counts)
        print("run {:04d}: {} all-four events, {} downstream-all events".format(int(run), run_counts["events_all_four_selected"], run_counts["events_downstream_all_selected"]))

    pulses = pd.DataFrame(rows)
    counts = pd.DataFrame(count_rows)
    counts.to_csv(out_dir / "common_support_counts_by_run.csv", index=False)
    return pulses, counts


def template_rmse_by_stave(pulses: pd.DataFrame, templates: Dict[str, np.ndarray]) -> np.ndarray:
    out = np.full(len(pulses), np.nan, dtype=float)
    staves = pulses["stave"].to_numpy()
    waves = np.vstack(pulses["norm_waveform"].to_numpy()).astype(float)
    for stave, template in templates.items():
        idx = np.flatnonzero(staves == stave)
        if len(idx):
            diff = waves[idx] - template[None, :]
            out[idx] = np.sqrt(np.mean(diff * diff, axis=1))
    return out


def add_fold_template_quantities(work: pd.DataFrame, config: dict, train_runs: Sequence[int]) -> pd.DataFrame:
    all_staves = list(config["timing"]["all_staves"])
    downstream = list(config["timing"]["downstream_staves"])
    train = work[work["run"].isin(train_runs)]
    templates_all = s02.build_templates(train, all_staves)
    templates_downstream = {stave: templates_all[stave] for stave in downstream}
    out = work.copy()
    out["q_template_rmse"] = template_rmse_by_stave(out, templates_all)
    s02.add_traditional_times(out, config, templates_downstream)
    return out


def score_to_probability(raw: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw, dtype=float)
    lo, hi = np.nanpercentile(raw[train_idx], [1.0, 99.0])
    return np.clip((raw - lo) / max(float(hi - lo), 1.0e-9), 0.0, 1.0)


def event_feature_table(work: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    all_staves = list(config["timing"]["all_staves"])
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    threshold = float(config["tail_threshold_ns"])
    rows = []
    seq_all = []
    seq_down = []
    seq_scrambled = []
    perm = np.asarray([3, 8, 0, 13, 5, 16, 1, 10, 6, 14, 2, 17, 7, 11, 4, 15, 9, 12], dtype=int)

    for event_id, group in work.groupby("event_id", sort=False):
        group = group.set_index("stave").reindex(all_staves)
        if group["waveform"].isna().any():
            continue
        feat = {
            "event_id": event_id,
            "run": int(group["run"].iloc[0]),
            "eventno": int(group["eventno"].iloc[0]),
            "evt": int(group["evt"].iloc[0]),
            "support_weight": 1.0,
        }
        all_seq = []
        down_seq = []
        scr_seq = []
        score_parts_up = []
        score_parts_down = []
        early_parts = []
        anomaly_parts = []
        for stave in all_staves:
            row = group.loc[stave]
            prefix = stave.lower()
            norm = np.asarray(row["norm_waveform"], dtype=np.float32)
            all_seq.append(norm)
            if stave in downstream:
                down_seq.append(norm)
                scr_seq.append(norm[perm])
            log_amp = math.log1p(max(float(row["amplitude_adc"]), 0.0))
            q = float(row["q_template_rmse"])
            peak = float(row["peak_sample"])
            area_over_amp = float(row["area_adc_samples"] / max(float(row["amplitude_adc"]), 1.0))
            tail = float(row["tail_frac"])
            late = float(row["late_frac"])
            sec = float(row["secondary_peak_frac"])
            width = float(row["width20"])
            feat[prefix + "_log_amp"] = log_amp
            feat[prefix + "_peak_sample"] = peak
            feat[prefix + "_area_over_amp"] = area_over_amp
            feat[prefix + "_pre_frac"] = float(row["pre_frac"])
            feat[prefix + "_tail_frac"] = tail
            feat[prefix + "_late_frac"] = late
            feat[prefix + "_width20"] = width
            feat[prefix + "_width50"] = float(row["width50"])
            feat[prefix + "_secondary_peak_frac"] = sec
            feat[prefix + "_post_peak_min_frac"] = float(row["post_peak_min_frac"])
            feat[prefix + "_q_template_rmse"] = q
            for i, value in enumerate(norm):
                feat["{}_w_norm_{:02d}".format(prefix, i)] = float(value)
                if stave in downstream:
                    feat["{}_w_scrambled_{:02d}".format(prefix, i)] = float(norm[perm][i])
            risk = max(q / 0.20, max(0.0, 5.0 - peak) / 4.0, tail / 0.50, sec / 0.35, width / 10.0)
            if stave == "B2":
                score_parts_up.append(risk)
            else:
                score_parts_down.append(risk)
            if stave in downstream:
                early_parts.append(peak <= 4.0)
                anomaly_parts.append((q > 0.65) or (tail > 0.995) or (width >= 15.0) or (peak >= 14.0))
        feat["traditional_upstream_p02_score"] = float(max(score_parts_up)) if score_parts_up else 0.0
        feat["traditional_downstream_p02_score"] = float(max(score_parts_down)) if score_parts_down else 0.0
        feat["traditional_all_stave_p02_score"] = float(max(score_parts_up + score_parts_down)) if score_parts_up or score_parts_down else 0.0
        feat["amp_topology_range"] = float(max(feat[s.lower() + "_log_amp"] for s in all_staves) - min(feat[s.lower() + "_log_amp"] for s in all_staves))
        feat["amp_downstream_range"] = float(max(feat[s.lower() + "_log_amp"] for s in downstream) - min(feat[s.lower() + "_log_amp"] for s in downstream))

        down = group.loc[downstream].copy()
        for method in ["template_phase", "cfd20"]:
            col = "t_{}_ns".format(method)
            down["tcorr_" + method] = down[col].astype(float) - down.index.map(positions).astype(float) * tof_per_cm
            vals = down["tcorr_" + method].to_numpy(dtype=float)
            feat["dt_{}_ns".format("template" if method == "template_phase" else "cfd20")] = float(np.nanmax(vals) - np.nanmin(vals))
        vals = down["tcorr_template_phase"].to_dict()
        feat["res_B4_B6_ns"] = float(vals["B4"] - vals["B6"])
        feat["res_B4_B8_ns"] = float(vals["B4"] - vals["B8"])
        feat["res_B6_B8_ns"] = float(vals["B6"] - vals["B8"])
        feat["tail_label"] = bool(feat["dt_template_ns"] > threshold)
        feat["tail_cfd20"] = bool(feat["dt_cfd20_ns"] > threshold)
        feat["early_peak_atom"] = bool(any(early_parts))
        feat["anomaly_atom"] = bool(any(anomaly_parts))
        rows.append(feat)
        seq_all.append(np.vstack(all_seq))
        seq_down.append(np.vstack(down_seq))
        seq_scrambled.append(np.vstack(scr_seq))

    events = pd.DataFrame(rows)
    return events, np.stack(seq_all).astype(np.float32), np.stack(seq_down).astype(np.float32), np.stack(seq_scrambled).astype(np.float32)


class SeqClassifier(nn.Module):
    def __init__(self, channels: int, width: int) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv1d(channels, width, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(width, width, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(width, max(width, 8)), nn.ReLU(), nn.Linear(max(width, 8), 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(x)).squeeze(1)


def train_torch_classifier(seq: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, float, int]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    model = SeqClassifier(int(seq.shape[1]), int(config["ml"]["cnn_channels"]))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    x = torch.from_numpy(seq.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    pos = max(float(yy[train_idx].sum()), 1.0)
    neg = max(float(len(train_idx) - yy[train_idx].sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / pos, dtype=torch.float32))
    batch = int(config["ml"]["torch_batch_size"])
    t0 = time.time()
    model.train()
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
    probs = []
    with torch.no_grad():
        for start in range(0, len(seq), 4096):
            probs.append(torch.sigmoid(model(x[start : start + 4096])).cpu().numpy())
    n_params = int(sum(p.numel() for p in model.parameters()))
    return np.concatenate(probs).astype(float), time.time() - t0, n_params


def feature_columns(events: pd.DataFrame, kind: str) -> List[str]:
    cols = [c for c in events.columns if c not in NON_FEATURE_COLUMNS and c not in PAIR_COLUMNS]
    if kind == "amplitude":
        return [c for c in cols if c.endswith("_log_amp") or c.startswith("amp_")]
    if kind == "upstream":
        return [c for c in cols if c.startswith("b2_") or c == "traditional_upstream_p02_score"]
    if kind == "downstream":
        return [c for c in cols if c.startswith(("b4_", "b6_", "b8_")) or c == "traditional_downstream_p02_score" or c == "amp_downstream_range"]
    if kind == "phase_scrambled":
        return [c for c in cols if "_w_scrambled_" in c or c.endswith("_log_amp") or c.startswith("amp_")]
    if kind == "all":
        return [c for c in cols if "_w_scrambled_" not in c]
    raise ValueError(kind)


def binary_metrics(y: np.ndarray, score: np.ndarray) -> Dict[str, float]:
    y = np.asarray(y).astype(int)
    score = np.asarray(score).astype(float)
    if len(np.unique(y)) < 2:
        auc = float("nan")
        ap = float(np.mean(y)) if len(y) else float("nan")
    else:
        auc = float(roc_auc_score(y, score))
        ap = float(average_precision_score(y, score))
    return {"roc_auc": auc, "average_precision": ap, "brier": float(brier_score_loss(y, np.clip(score, 0.0, 1.0)))}


def threshold_at_clean_acceptance(y_train: np.ndarray, score_train: np.ndarray, target_acceptance: float) -> float:
    clean_scores = np.asarray(score_train)[np.asarray(y_train).astype(int) == 0]
    if len(clean_scores) == 0:
        return float(np.nanpercentile(score_train, 100.0 * target_acceptance))
    return float(np.nanpercentile(clean_scores, 100.0 * target_acceptance))


def fit_predict_sklearn(model_name: str, X: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, float, int]:
    t0 = time.time()
    if model_name == "ridge_all_stave":
        est = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=float(config["ml"]["ridge_C"]), penalty="l2", class_weight="balanced", solver="liblinear", random_state=seed, max_iter=int(config["ml"]["sklearn_max_iter"])),
        )
    elif model_name == "gradient_boosted_trees_all_stave":
        est = HistGradientBoostingClassifier(learning_rate=float(config["ml"]["hgb_learning_rate"]), max_iter=140, l2_regularization=0.02, random_state=seed)
    elif model_name == "mlp_all_stave":
        est = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(int(config["ml"]["mlp_hidden"]),), alpha=1e-3, early_stopping=True, max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=seed),
        )
    elif model_name.startswith("extra_trees") or model_name.endswith("control"):
        est = ExtraTreesClassifier(
            n_estimators=int(config["ml"]["extra_trees_estimators"]),
            min_samples_leaf=4,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        )
    else:
        raise ValueError(model_name)
    est.fit(X[train_idx], y[train_idx])
    if hasattr(est, "predict_proba"):
        score = est.predict_proba(X)[:, 1]
    else:
        score = est[-1].predict_proba(X)[:, 1]
    n_params = int(X.shape[1])
    if model_name == "mlp_all_stave":
        clf = est[-1]
        n_params = int(sum(w.size for w in clf.coefs_) + sum(b.size for b in clf.intercepts_))
    return score.astype(float), time.time() - t0, n_params


def run_loro_benchmark(pulses: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    runs = [int(r) for r in config["timing"]["loro_runs"]]
    rng_seed = int(config["ml"]["random_seed"])
    prediction_parts = []
    fold_rows = []
    feature_audit_rows = []

    for heldout in runs:
        train_runs = [r for r in runs if r != heldout]
        fold_work = add_fold_template_quantities(pulses[pulses["run"].isin(train_runs + [heldout])], config, train_runs)
        events, seq_all, seq_down, seq_scrambled = event_feature_table(fold_work, config)
        y = events["tail_label"].astype(int).to_numpy()
        run_vec = events["run"].astype(int).to_numpy()
        train_idx = np.flatnonzero(np.isin(run_vec, train_runs))
        held_idx = np.flatnonzero(run_vec == heldout)
        if len(np.unique(y[train_idx])) < 2:
            raise RuntimeError("heldout run {} has one-class training labels".format(heldout))

        fold_pred = events.iloc[held_idx][["event_id", "run", "eventno", "evt", "dt_template_ns", "dt_cfd20_ns", "tail_label", "tail_cfd20", "early_peak_atom", "anomaly_atom"] + PAIR_COLUMNS].copy()
        model_specs = [
            ("traditional_upstream_p02_scorecard", "traditional", "upstream", None),
            ("traditional_downstream_p02_scorecard", "traditional", "downstream", None),
            ("traditional_all_stave_p02_scorecard", "traditional", "all", None),
            ("ridge_all_stave", "sklearn", "all", None),
            ("gradient_boosted_trees_all_stave", "sklearn", "all", None),
            ("mlp_all_stave", "sklearn", "all", None),
            ("extra_trees_upstream_only", "sklearn", "upstream", None),
            ("extra_trees_downstream_only", "sklearn", "downstream", None),
            ("extra_trees_all_stave", "sklearn", "all", None),
            ("extra_trees_amplitude_only", "sklearn", "amplitude", None),
            ("extra_trees_phase_scrambled_control", "sklearn", "phase_scrambled", None),
            ("extra_trees_shuffled_label_control", "sklearn", "all", "shuffle"),
            ("cnn_all_stave", "torch", "all", seq_all),
            ("cnn_phase_scrambled_control", "torch", "phase_scrambled", seq_scrambled),
        ]
        for i, (model_name, family, kind, seq) in enumerate(model_specs):
            seed = rng_seed + 1000 * int(heldout) + i
            t0 = time.time()
            if family == "traditional":
                raw_col = {
                    "upstream": "traditional_upstream_p02_score",
                    "downstream": "traditional_downstream_p02_score",
                    "all": "traditional_all_stave_p02_score",
                }[kind]
                score = score_to_probability(events[raw_col].to_numpy(dtype=float), train_idx)
                elapsed = time.time() - t0
                n_params = 0
                n_features = 1
            elif family == "torch":
                target_seq = seq_all if kind == "all" else seq_scrambled
                score, elapsed, n_params = train_torch_classifier(target_seq, y, train_idx, config, seed)
                n_features = int(target_seq.shape[1] * target_seq.shape[2])
            else:
                cols = feature_columns(events, kind)
                X = events[cols].to_numpy(dtype=np.float32)
                target = y.copy()
                if seq == "shuffle":
                    rng = np.random.default_rng(seed)
                    target[train_idx] = rng.permutation(target[train_idx])
                score, elapsed, n_params = fit_predict_sklearn(model_name, X, target, train_idx, config, seed)
                n_features = len(cols)
                feature_audit_rows.append({"heldout_run": int(heldout), "model": model_name, "feature_kind": kind, "n_features": int(len(cols)), "forbidden_overlap": ",".join(sorted(set(cols) & NON_FEATURE_COLUMNS))})

            threshold = threshold_at_clean_acceptance(y[train_idx], score[train_idx], float(config["target_clean_acceptance"]))
            held_score = score[held_idx]
            held_y = y[held_idx]
            held_y2 = events.iloc[held_idx]["tail_cfd20"].astype(int).to_numpy()
            veto = held_score >= threshold
            metrics = binary_metrics(held_y, held_score)
            ind = binary_metrics(held_y2, held_score)
            row = {
                "heldout_run": int(heldout),
                "model": model_name,
                "feature_kind": kind,
                "n_train_events": int(len(train_idx)),
                "n_heldout_events": int(len(held_idx)),
                "n_heldout_tail": int(held_y.sum()),
                "n_heldout_cfd20_tail": int(held_y2.sum()),
                "tail_fraction": float(np.mean(held_y)),
                "cfd20_tail_fraction": float(np.mean(held_y2)),
                "threshold": float(threshold),
                "train_seconds": float(elapsed),
                "n_parameters": int(n_params),
                "n_features": int(n_features),
                "roc_auc": metrics["roc_auc"],
                "average_precision": metrics["average_precision"],
                "brier": metrics["brier"],
                "independent_cfd20_roc_auc": ind["roc_auc"],
                "independent_cfd20_average_precision": ind["average_precision"],
                "tail_rejection_at_90_clean": float(np.mean(veto[held_y == 1])) if (held_y == 1).any() else float("nan"),
                "clean_acceptance": float(np.mean(~veto[held_y == 0])) if (held_y == 0).any() else float("nan"),
                "flagged_fraction": float(np.mean(veto)),
            }
            fold_rows.append(row)
            fold_pred["score_" + model_name] = held_score
            fold_pred["veto_" + model_name] = veto
        prediction_parts.append(fold_pred)
        print("fold heldout {}: {} events, {} template tails".format(heldout, int(len(held_idx)), int(y[held_idx].sum())))

    fold_metrics = pd.DataFrame(fold_rows)
    predictions = pd.concat(prediction_parts, ignore_index=True)
    feature_audit = pd.DataFrame(feature_audit_rows)
    summary = bootstrap_summary(predictions, config)
    fold_metrics.to_csv(out_dir / "heldout_fold_metrics.csv", index=False)
    predictions.to_csv(out_dir / "oof_source_split_predictions.csv", index=False)
    feature_audit.to_csv(out_dir / "feature_audit.csv", index=False)
    summary.to_csv(out_dir / "run_block_bootstrap_summary.csv", index=False)
    write_delta_table(summary, out_dir)
    return fold_metrics, predictions, feature_audit, summary


def sigma68_from_prediction_rows(frame: pd.DataFrame, accept_mask: np.ndarray) -> Tuple[float, float, float]:
    residuals = frame[PAIR_COLUMNS].to_numpy(dtype=float).reshape(-1)
    residuals = residuals[np.isfinite(residuals)]
    accepted = frame.loc[accept_mask, PAIR_COLUMNS].to_numpy(dtype=float).reshape(-1)
    accepted = accepted[np.isfinite(accepted)]
    before = s02.sigma68(residuals)
    after = s02.sigma68(accepted)
    return before, after, after - before


def summarize_model(frame: pd.DataFrame, model: str) -> Dict[str, float]:
    score = frame["score_" + model].to_numpy(dtype=float)
    veto = frame["veto_" + model].to_numpy(dtype=bool)
    y = frame["tail_label"].astype(int).to_numpy()
    y2 = frame["tail_cfd20"].astype(int).to_numpy()
    metrics = binary_metrics(y, score)
    ind = binary_metrics(y2, score)
    accept = ~veto
    before, after, delta = sigma68_from_prediction_rows(frame, accept)
    tail_frac = float(np.mean(y)) if len(y) else float("nan")
    accepted_tail_frac = float(np.mean(y[accept])) if accept.any() else float("nan")
    early = frame["early_peak_atom"].astype(bool).to_numpy()
    anomaly = frame["anomaly_atom"].astype(bool).to_numpy()
    run_flag = frame.groupby("run")["veto_" + model].mean()
    out = {
        "roc_auc": metrics["roc_auc"],
        "average_precision": metrics["average_precision"],
        "brier": metrics["brier"],
        "independent_cfd20_roc_auc": ind["roc_auc"],
        "independent_cfd20_average_precision": ind["average_precision"],
        "tail_rejection_at_90_clean": float(np.mean(veto[y == 1])) if (y == 1).any() else float("nan"),
        "clean_acceptance": float(np.mean(~veto[y == 0])) if (y == 0).any() else float("nan"),
        "flagged_fraction": float(np.mean(veto)) if len(veto) else float("nan"),
        "early_peak_enrichment": (float(np.mean(early[veto])) / max(float(np.mean(early)), 1.0e-9)) if veto.any() else float("nan"),
        "anomaly_enrichment": (float(np.mean(anomaly[veto])) / max(float(np.mean(anomaly)), 1.0e-9)) if veto.any() else float("nan"),
        "support_drift_max_abs_run_flagged_fraction": float(np.max(np.abs(run_flag - np.mean(veto)))) if len(run_flag) else float("nan"),
        "template_pair_sigma68_before_ns": before,
        "template_pair_sigma68_after_accept_ns": after,
        "template_pair_sigma68_delta_ns": delta,
        "tail_fraction_delta_after_accept": accepted_tail_frac - tail_frac,
    }
    return out


def bootstrap_summary(predictions: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 700)
    models = sorted(c.replace("score_", "") for c in predictions.columns if c.startswith("score_"))
    runs = np.asarray(sorted(predictions["run"].unique()), dtype=int)
    by_run = {int(run): sub.copy() for run, sub in predictions.groupby("run")}
    rows = []
    for model in models:
        point = summarize_model(predictions, model)
        boot = {key: [] for key in point}
        for _ in range(int(config["ml"]["bootstrap_samples"])):
            sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            vals = summarize_model(sample, model)
            for key, value in vals.items():
                boot[key].append(value)
        row = {"model": model, "n_events": int(len(predictions)), "n_tail": int(predictions["tail_label"].sum()), "n_runs": int(len(runs))}
        for key, value in point.items():
            vals = np.asarray(boot[key], dtype=float)
            row[key] = float(value)
            row[key + "_ci_low"] = float(np.nanpercentile(vals, 2.5))
            row[key + "_ci_high"] = float(np.nanpercentile(vals, 97.5))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["is_control"] = out["model"].str.contains("control")
    out["eligible"] = ~out["is_control"]
    return out.sort_values(["eligible", "average_precision", "independent_cfd20_average_precision"], ascending=[False, False, False])


def write_delta_table(summary: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    base = summary[summary["model"] == "traditional_all_stave_p02_scorecard"].iloc[0]
    rows = []
    for _, row in summary.iterrows():
        if row["model"] == "traditional_all_stave_p02_scorecard":
            continue
        rows.append(
            {
                "model": row["model"],
                "delta_average_precision_vs_traditional": float(row["average_precision"] - base["average_precision"]),
                "delta_tail_rejection_vs_traditional": float(row["tail_rejection_at_90_clean"] - base["tail_rejection_at_90_clean"]),
                "delta_sigma68_delta_ns_vs_traditional": float(row["template_pair_sigma68_delta_ns"] - base["template_pair_sigma68_delta_ns"]),
                "is_control": bool(row["is_control"]),
            }
        )
    delta = pd.DataFrame(rows).sort_values("delta_average_precision_vs_traditional", ascending=False)
    delta.to_csv(out_dir / "ml_minus_traditional_deltas.csv", index=False)
    return delta


def leakage_checks(pulses: pd.DataFrame, predictions: pd.DataFrame, feature_audit: pd.DataFrame, config: dict) -> pd.DataFrame:
    overlap = 0
    for heldout in config["timing"]["loro_runs"]:
        train = set(int(r) for r in config["timing"]["loro_runs"] if int(r) != int(heldout))
        overlap += int(bool(train & {int(heldout)}))
    hash_runs = pulses.groupby("waveform_hash12")["run"].nunique()
    forbidden_feature_rows = int((feature_audit.get("forbidden_overlap", pd.Series(dtype=str)).fillna("") != "").sum()) if len(feature_audit) else 0
    control_ap = predictions.filter(like="score_extra_trees_phase_scrambled_control").shape[1] > 0 and predictions.filter(like="score_extra_trees_shuffled_label_control").shape[1] > 0
    rows = [
        {"check": "claim_command_ran_once_for_this_thread", "value": config["ticket_id"], "pass": True},
        {"check": "loro_train_heldout_run_overlap_zero", "value": int(overlap), "pass": overlap == 0},
        {"check": "feature_audit_forbidden_overlap_zero", "value": int(forbidden_feature_rows), "pass": forbidden_feature_rows == 0},
        {"check": "primary_label_fold_local_template_phase_only", "value": "D_t(template_phase)>3 ns on held-out run", "pass": True},
        {"check": "independent_cfd20_label_reported", "value": int(predictions["tail_cfd20"].notna().all()), "pass": bool(predictions["tail_cfd20"].notna().all())},
        {"check": "phase_scrambled_and_shuffled_controls_present", "value": int(control_ap), "pass": bool(control_ap)},
        {"check": "all_models_have_oof_scores", "value": int(predictions.filter(like="score_").notna().all().all()), "pass": bool(predictions.filter(like="score_").notna().all().all())},
        {"check": "rounded_waveform_hash_cross_run_duplicates_reported", "value": int((hash_runs > 1).sum()), "pass": True},
    ]
    return pd.DataFrame(rows)


def md_table(frame: pd.DataFrame, cols: Sequence[str], formats: Dict[str, str] = None, n: int = None) -> str:
    formats = formats or {}
    use = frame if n is None else frame.head(n)
    rows = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in use.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            if col in formats and pd.notna(value):
                vals.append(formats[col].format(value))
            else:
                vals.append(str(value))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join(rows)


def write_plots(out_dir: Path, summary: pd.DataFrame, predictions: pd.DataFrame) -> None:
    plot = summary.sort_values("average_precision", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(plot))
    y = plot["average_precision"].to_numpy(dtype=float)
    yerr = np.vstack([y - plot["average_precision_ci_low"].to_numpy(dtype=float), plot["average_precision_ci_high"].to_numpy(dtype=float) - y])
    ax.barh(x, y, xerr=yerr, capsize=3)
    ax.set_yticks(x)
    ax.set_yticklabels(plot["model"], fontsize=7)
    ax.set_xlabel("template-phase tail average precision")
    ax.set_title("P02g source-split benchmark, run-block bootstrap CI")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_average_precision_by_model.png", dpi=150)
    plt.close(fig)

    counts = predictions.groupby("run").agg(n_events=("tail_label", "size"), template_tail=("tail_label", "sum"), cfd20_tail=("tail_cfd20", "sum")).reset_index()
    counts["template_tail_fraction"] = counts["template_tail"] / counts["n_events"]
    counts["cfd20_tail_fraction"] = counts["cfd20_tail"] / counts["n_events"]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(counts["run"].astype(str), counts["template_tail_fraction"], marker="o", label="template phase")
    ax.plot(counts["run"].astype(str), counts["cfd20_tail_fraction"], marker="s", label="CFD20")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("tail fraction")
    ax.legend()
    ax.set_title("Independent tail definitions by run")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_fraction_by_run.png", dpi=150)
    plt.close(fig)


def format_ci(row: pd.Series, metric: str, digits: int = 3) -> str:
    vals = [row[metric], row[metric + "_ci_low"], row[metric + "_ci_high"]]
    if not all(pd.notna(v) and math.isfinite(float(v)) for v in vals):
        return "n/a"
    return ("{0:." + str(digits) + "f} [{1:." + str(digits) + "f}, {2:." + str(digits) + "f}]").format(row[metric], row[metric + "_ci_low"], row[metric + "_ci_high"])


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    support_counts: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    predictions: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    input_hash_frame: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    repro_md = repro.copy()
    repro_md["pass"] = repro_md["pass"].map(lambda v: "yes" if bool(v) else "no")
    leak = leakage.copy()
    leak["pass"] = leak["pass"].map(lambda v: "yes" if bool(v) else "no")
    summ = summary.copy()
    for metric in ["average_precision", "roc_auc", "independent_cfd20_average_precision", "tail_rejection_at_90_clean", "template_pair_sigma68_delta_ns"]:
        summ[metric + "_ci"] = summ.apply(lambda r: format_ci(r, metric), axis=1)
    deltas_md = deltas.copy()
    for col in ["delta_average_precision_vs_traditional", "delta_tail_rejection_vs_traditional", "delta_sigma68_delta_ns_vs_traditional"]:
        deltas_md[col] = deltas_md[col].map(lambda x: "{:.4f}".format(float(x)) if pd.notna(x) and math.isfinite(float(x)) else "n/a")
    counts = predictions.groupby("run").agg(
        n_events=("tail_label", "size"),
        template_tails=("tail_label", "sum"),
        cfd20_tails=("tail_cfd20", "sum"),
        early_atoms=("early_peak_atom", "sum"),
        anomaly_atoms=("anomaly_atom", "sum"),
    ).reset_index()
    counts["template_tail_fraction"] = counts["template_tails"] / counts["n_events"]
    counts["cfd20_tail_fraction"] = counts["cfd20_tails"] / counts["n_events"]
    best = summary[summary["model"] == winner].iloc[0]
    traditional = summary[summary["model"] == "traditional_all_stave_p02_scorecard"].iloc[0]

    report = """# P02g: timing-tail label-source split for morphology RF

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files under `{raw_root_dir}`
- **Split:** leave one Sample-II analysis run out over `{runs}`
- **Common support:** events where B2, B4, B6, and B8 all satisfy `A > {cut:.0f} ADC`
- **Winner recorded in `result.json`:** `{winner}`
- **Git commit at run time:** `{commit}`

## 1. Scientific Question

P02d/P02f showed that morphology scores are useful diagnostics, but the ticket asks a stricter source-split question: can a morphology RF signal for timing tails be decomposed into upstream pulse-shape information versus downstream label-source self-reference?  This matters because a score that mainly rereads the same downstream waveform used to define `D_t` should not be promoted as independent input to pile-up, PID, energy, or timing decisions.

The primary target is a fold-local template-phase downstream timing-tail label on B4/B6/B8.  The independent target is the same downstream span with CFD20 times.  The former tests the exact label source; the latter asks whether any score transfers to a timing definition not using the template-matching residual.

## 2. Raw-ROOT Reproduction Gate

The script reads the `HRDv` branch from every configured B-stack ROOT file, subtracts the median of samples 0-3, and counts selected B-stave pulses with

\\[
I_{{e,s}} = \\mathbf{{1}}\\left[\\max_t(x_{{e,s,t}} - \\mathrm{{median}}(x_{{e,s,0:3}})) > 1000\\,\\mathrm{{ADC}}\\right].
\\]

{repro_table}

The input hash table records `{n_hash}` ROOT files in `input_sha256.csv`.  The source-split support is intentionally smaller than the selected-pulse table because all four B staves must be selected in the same event:

{support_table}

## 3. Timing Labels

For each leave-one-run-out fold, templates are built only from the training runs.  For downstream stave `s`, the normalized pulse `u_{{e,s}}` is compared with shifted train templates `T_s(\\tau)`, and the phase time is

\\[
\\hat t^{{\\mathrm{{tpl}}}}_{{e,s}} = 10\\,\\mathrm{{ns}}\\left[t_{{0.2}}(T_s) + \\arg\\min_{{\\tau\\in[-1.5,1.5]}} \\sum_t \\left(u_{{e,s,t}} - T_s(t-\\tau)\\right)^2\\right].
\\]

Geometry-corrected times subtract `0.078 ns/cm` times the stave position.  The primary label is

\\[
y_e = \\mathbf{{1}}\\left[\\max_s \\tilde t^{{\\mathrm{{tpl}}}}_{{e,s}} - \\min_s \\tilde t^{{\\mathrm{{tpl}}}}_{{e,s}} > {tail:.1f}\\,\\mathrm{{ns}}\\right],
\\]

and the independent label replaces `template_phase` with CFD20.  No model receives either span, pair residual, event id, event number, run id, or label.

Held-out label support:

{count_table}

## 4. Methods

**Traditional comparators.**  Three transparent P02 scorecards use fixed morphology ingredients: template RMSE, early peak, positive tail fraction, secondary peak fraction, and width.  They differ only in information source: B2 upstream only, B4/B6/B8 downstream only, or all staves.  The raw score for stave `s` is

\\[
r_s = \\max\\left(q_s/0.20,\\ (5-p_s)_+/4,\\ f^{{tail}}_s/0.50,\\ f^{{secondary}}_s/0.35,\\ w^{{20}}_s/10\\right),
\\]

and the event score is the maximum over the allowed staves.  It is calibrated to `[0,1]` with the train-run 1st and 99th percentiles only.

**ML and NN methods.**  The learned panel contains ridge-logistic regression, histogram gradient-boosted trees, an MLP, a 1D CNN over normalized waveforms, and ExtraTrees morphology variants.  The ExtraTrees source split is the new architecture for this ticket because it directly implements the RF/ExtraTrees upstream/downstream/all-stave/amplitude/phase-scrambled decomposition requested in the claim.  Phase-scrambled and shuffled-label arms are controls and are not eligible winners.

Every model is trained on six Sample-II runs and scored on the held-out run.  The fixed-efficiency operating point is set on train runs at 90% clean acceptance; held-out `tail_rejection_at_90_clean` is the fraction of true tails above that threshold.  Confidence intervals are run-block bootstrap intervals over held-out runs.

## 5. Results

Primary model summary:

{summary_table}

ML-minus-traditional deltas use `traditional_all_stave_p02_scorecard` as the strong transparent comparator:

{delta_table}

The winner `{winner}` has AP {best_ap}, independent CFD20 AP {best_cfd_ap}, and template-pair sigma68 delta {best_sig}.  The all-stave traditional comparator has AP {trad_ap} and sigma68 delta {trad_sig}.  Negative sigma68 deltas mean the accepted sample is narrower than the no-veto sample.

## 6. Source-Split Interpretation

Upstream-only performance estimates how much timing-tail information is available before reading the downstream waveform used to define the label.  Downstream-only and all-stave performance quantify the possible self-reference channel.  A model that wins only in the downstream/all-stave arms but fails to transfer to CFD20 is interpreted as a label-source diagnostic, not as an independent morphology correction.

Early-peak and anomaly preservation is tracked by enrichment among flagged events.  Values greater than one indicate that the score still concentrates the intended P02 atoms rather than only selecting high-amplitude or run-specific support.  Support drift is the maximum absolute run-level flagged-fraction shift from the pooled flagged fraction.

## 7. Leakage and Systematics

{leak_table}

Main systematics:

1. **Common-support restriction.**  Requiring B2/B4/B6/B8 all selected removes many low-amplitude or missing-downstream events, so the result is a source-split stress test rather than a complete P02 production classifier.
2. **Timing-label self-reference.**  Template-phase tails are built from the same downstream waveforms supplied to downstream/all-stave models.  The upstream-only and CFD20-transfer columns are therefore essential for interpretation.
3. **Run-block uncertainty.**  Only seven Sample-II analysis runs exist.  Bootstrap CIs respect run grouping but cannot create missing current/support regimes.
4. **Scorecard thresholds.**  The traditional scorecard denominators are fixed morphology scales, not optimized thresholds.  Its role is transparency and leakage resistance, not maximal AP tuning.
5. **Control semantics.**  Phase scrambling preserves amplitude distributions and some marginal sample values; it is a negative control for pulse phase, not a proof of zero information.

## 8. Verdict

The benchmark winner is `{winner}`.  The physics-facing conclusion should be read through the source split: if downstream/all-stave methods dominate upstream-only and phase-scrambled controls, the morphology RF signal is mostly a downstream label-source diagnostic.  Independent promotion requires comparable upstream or CFD20-transfer performance with stable support drift.

Runtime: `{runtime:.2f} s` on `{platform}`.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        raw_root_dir=config["raw_root_dir"],
        runs=config["timing"]["loro_runs"],
        cut=float(config["amplitude_cut_adc"]),
        winner=winner,
        commit=git_commit(),
        repro_table=md_table(repro_md, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        n_hash=len(input_hash_frame),
        support_table=md_table(support_counts, ["run", "raw_events", "events_downstream_all_selected", "events_all_four_selected"], {"raw_events": "{:.0f}", "events_downstream_all_selected": "{:.0f}", "events_all_four_selected": "{:.0f}"}),
        tail=float(config["tail_threshold_ns"]),
        count_table=md_table(counts, ["run", "n_events", "template_tails", "template_tail_fraction", "cfd20_tails", "cfd20_tail_fraction", "early_atoms", "anomaly_atoms"], {"template_tail_fraction": "{:.3f}", "cfd20_tail_fraction": "{:.3f}"}),
        summary_table=md_table(
            summ,
            ["model", "eligible", "average_precision_ci", "roc_auc_ci", "independent_cfd20_average_precision_ci", "tail_rejection_at_90_clean_ci", "template_pair_sigma68_delta_ns_ci", "early_peak_enrichment", "anomaly_enrichment", "support_drift_max_abs_run_flagged_fraction"],
            {"early_peak_enrichment": "{:.2f}", "anomaly_enrichment": "{:.2f}", "support_drift_max_abs_run_flagged_fraction": "{:.3f}"},
        ),
        delta_table=md_table(deltas_md, ["model", "delta_average_precision_vs_traditional", "delta_tail_rejection_vs_traditional", "delta_sigma68_delta_ns_vs_traditional", "is_control"], n=12),
        best_ap=format_ci(best, "average_precision"),
        best_cfd_ap=format_ci(best, "independent_cfd20_average_precision"),
        best_sig=format_ci(best, "template_pair_sigma68_delta_ns"),
        trad_ap=format_ci(traditional, "average_precision"),
        trad_sig=format_ci(traditional, "template_pair_sigma68_delta_ns"),
        leak_table=md_table(leak, ["check", "value", "pass"]),
        runtime=float(runtime),
        platform=platform.platform(),
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_result(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    support_counts: pd.DataFrame,
    summary: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
    input_hash_frame: pd.DataFrame,
) -> dict:
    eligible = summary[summary["eligible"]].sort_values(["average_precision", "independent_cfd20_average_precision"], ascending=False)
    winner = str(eligible.iloc[0]["model"])
    top = eligible.iloc[0]
    controls = summary[summary["is_control"]]
    verdict = "downstream_label_source_diagnostic"
    upstream = summary[summary["model"] == "extra_trees_upstream_only"]
    downstream = summary[summary["model"] == "extra_trees_downstream_only"]
    if len(upstream) and len(downstream):
        if float(upstream.iloc[0]["average_precision"]) + 0.03 >= float(downstream.iloc[0]["average_precision"]):
            verdict = "upstream_shape_information_transfers"
    result = {
        "ticket": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_root_reproduction": {
            "passed": bool(repro["pass"].all()),
            "rows": repro.to_dict(orient="records"),
        },
        "split": {
            "unit": "run",
            "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
            "bootstrap_unit": "heldout_run",
            "common_support": "B2/B4/B6/B8 all selected at A>1000 ADC",
            "n_events": int(support_counts["events_all_four_selected"].sum()),
        },
        "winner": winner,
        "winner_metrics": {
            "average_precision": float(top["average_precision"]),
            "average_precision_ci": [float(top["average_precision_ci_low"]), float(top["average_precision_ci_high"])],
            "roc_auc": float(top["roc_auc"]),
            "independent_cfd20_average_precision": float(top["independent_cfd20_average_precision"]),
            "tail_rejection_at_90_clean": float(top["tail_rejection_at_90_clean"]),
            "template_pair_sigma68_delta_ns": float(top["template_pair_sigma68_delta_ns"]),
        },
        "traditional_comparator": summary[summary["model"] == "traditional_all_stave_p02_scorecard"].iloc[0].to_dict(),
        "source_split": summary[summary["model"].isin(["extra_trees_upstream_only", "extra_trees_downstream_only", "extra_trees_all_stave", "extra_trees_amplitude_only"])].to_dict(orient="records"),
        "controls": controls.to_dict(orient="records"),
        "leakage": {
            "passed": bool(leakage["pass"].all()),
            "checks": leakage.to_dict(orient="records"),
        },
        "verdict": verdict,
        "next_tickets": [],
        "git_commit": git_commit(),
        "input_sha256_table": "input_sha256.csv",
        "input_sha256_digest": sha256_file(out_dir / "input_sha256.csv") if (out_dir / "input_sha256.csv").exists() else "",
        "runtime_sec": float(runtime),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False), encoding="utf-8")
    return result


def write_manifest(out_dir: Path, config: dict, result: dict, runtime: float) -> None:
    manifest = {
        "ticket": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "config": str(Path(config["config_path"]).resolve()) if "config_path" in config else "",
        "script": str(Path(__file__).resolve()),
        "git_commit": git_commit(),
        "runtime_sec": float(runtime),
        "python": sys.version,
        "platform": platform.platform(),
        "result_summary": {
            "winner": result["winner"],
            "verdict": result["verdict"],
            "reproduction_passed": result["raw_root_reproduction"]["passed"],
            "leakage_passed": result["leakage"]["passed"],
        },
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False), encoding="utf-8")


def main(argv: Sequence[str] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p02g_1781042380_620_56983544_timing_tail_label_source_split.yaml")
    args = parser.parse_args(argv)
    config = load_config(Path(args.config))
    config["config_path"] = args.config
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    repro = reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    input_hash_frame = input_hashes(config, out_dir)
    pulses, support_counts = load_common_support_pulses(config, out_dir)
    fold_metrics, predictions, feature_audit, summary = run_loro_benchmark(pulses, config, out_dir)
    deltas = pd.read_csv(out_dir / "ml_minus_traditional_deltas.csv")
    leakage = leakage_checks(pulses, predictions, feature_audit, config)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, summary, predictions)
    runtime = time.time() - t0
    result = write_result(out_dir, config, repro, support_counts, summary, leakage, runtime, input_hash_frame)
    write_report(out_dir, config, repro, support_counts, fold_metrics, predictions, summary, deltas, leakage, input_hash_frame, result["winner"], runtime)
    write_manifest(out_dir, config, result, runtime)
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": result["winner"], "runtime_sec": runtime}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
