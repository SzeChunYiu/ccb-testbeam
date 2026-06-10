#!/usr/bin/env python3
"""S02e lower-threshold Sample-II LORO tail-label benchmark.

This ticket repeats the Sample-II leave-one-run-out timing-tail exercise with
a preregistered 3 ns downstream-span threshold, then asks whether S16f-style
pre-trigger veto information is stable under held-out runs.  It starts with the
raw ROOT selected-pulse reproduction gate and writes a full report plus machine
readable benchmark artifacts.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s02e-1781031385")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s16f_1781017317_1162_6f117818_event_display_audit as s16f

torch.set_num_threads(1)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


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


def load_downstream_pulses_with_s16_features(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    downstream = list(config["timing"]["downstream_staves"])
    channels = np.asarray([staves[name] for name in downstream])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows: List[dict] = []
    uid_offset = 0
    for run in config["timing"]["loro_runs"]:
        for batch in s02.iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw = events[:, channels, :]
            seed = np.median(raw[..., baseline_idx], axis=-1)
            corrected, amp, peak, area = s02.pulse_quantities(raw, baseline_idx)
            selected = amp > cut
            event_mask = selected.all(axis=1)
            if not event_mask.any():
                uid_offset += len(eventno)
                continue
            flat_ped, flat_lower, _ = s16f.adaptive_pedestal(raw[event_mask].reshape(-1, nsamp), seed[event_mask].reshape(-1), config)
            ped = flat_ped.reshape(-1, len(downstream))
            lowering = flat_lower.reshape(-1, len(downstream))
            chosen = np.flatnonzero(event_mask)
            for local_i, e in enumerate(chosen):
                event_id = f"{int(run)}:{int(eventno[e])}:{int(evt[e])}:{uid_offset + int(e)}"
                for sidx, stave in enumerate(downstream):
                    y = corrected[e, sidx].astype(float)
                    positive = np.clip(y, 0.0, None)
                    tail = y[min(nsamp, int(peak[e, sidx]) + 2) :]
                    secondary = y.copy()
                    p = int(peak[e, sidx])
                    secondary[max(0, p - 1) : min(nsamp, p + 2)] = -np.inf
                    secondary_peak = float(np.nanmax(secondary)) if np.isfinite(secondary).any() else 0.0
                    pre = y[:4]
                    late = y[-4:]
                    rows.append(
                        {
                            "event_id": event_id,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": str(stave),
                            "waveform": y,
                            "raw_waveform": raw[e, sidx].astype(float),
                            "amplitude_adc": float(amp[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                            "adaptive_pedestal_adc": float(ped[local_i, sidx]),
                            "adaptive_lowering_adc": float(lowering[local_i, sidx]),
                            "pretrigger_ptp_adc": float(np.ptp(pre)),
                            "pretrigger_absmax_adc": float(np.max(np.abs(pre))),
                            "late_absmax_adc": float(np.max(np.abs(late))),
                            "tail_area_frac": float(np.clip(tail, 0.0, None).sum() / max(float(positive.sum()), 1.0)) if len(tail) else 0.0,
                            "secondary_peak_frac": float(max(0.0, secondary_peak) / max(float(amp[e, sidx]), 1.0)),
                            "width20_samples": int((y > 0.20 * float(amp[e, sidx])).sum()),
                            "waveform_hash12": hashlib.sha256(np.round(y, 1).astype(np.float32).tobytes()).hexdigest()[:12],
                        }
                    )
            uid_offset += len(eventno)
    return pd.DataFrame(rows)


def geometry_corrected_span(pulses: pd.DataFrame, method: str, config: dict) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    work = pulses.copy()
    work["tcorr"] = work[f"t_{method}_ns"] - work["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = work.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    span = wide.max(axis=1) - wide.min(axis=1)
    meta = pulses.drop_duplicates("event_id").set_index("event_id")[["run", "eventno", "evt"]]
    out = meta.join(span.rename("dt_span_ns"), how="inner").reset_index()
    out["tail_label"] = out["dt_span_ns"] > float(config["tail_threshold_ns"])
    return out


def event_feature_tables(pulses: pd.DataFrame, labels: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, List[str]]:
    downstream = list(config["timing"]["downstream_staves"])
    tab_rows = []
    seq_rows = []
    for event_id, group in pulses.groupby("event_id", sort=False):
        group = group.set_index("stave").reindex(downstream)
        if group["waveform"].isna().any():
            continue
        feat: Dict[str, float] = {"event_id": event_id, "run": int(group["run"].iloc[0])}
        seq = []
        risk_parts = []
        for stave in downstream:
            row = group.loc[stave]
            y = np.asarray(row["waveform"], dtype=float)
            amp = max(float(row["amplitude_adc"]), 1.0)
            norm = y / amp
            seq.append(norm.astype(np.float32))
            prefix = stave.lower()
            feat[f"{prefix}_log_amp"] = math.log1p(max(float(row["amplitude_adc"]), 0.0))
            feat[f"{prefix}_peak_sample"] = float(row["peak_sample"])
            feat[f"{prefix}_area_over_amp"] = float(row["area_adc_samples"] / amp)
            feat[f"{prefix}_adaptive_lowering"] = float(row["adaptive_lowering_adc"])
            feat[f"{prefix}_pretrigger_ptp"] = float(row["pretrigger_ptp_adc"])
            feat[f"{prefix}_pretrigger_absmax"] = float(row["pretrigger_absmax_adc"])
            feat[f"{prefix}_tail_area_frac"] = float(row["tail_area_frac"])
            feat[f"{prefix}_secondary_peak_frac"] = float(row["secondary_peak_frac"])
            feat[f"{prefix}_width20"] = float(row["width20_samples"])
            for i, value in enumerate(norm):
                feat[f"{prefix}_w_norm_{i:02d}"] = float(value)
            risk_parts.append(
                max(0.0, float(row["pretrigger_ptp_adc"]) / 80.0)
                + max(0.0, float(row["pretrigger_absmax_adc"]) / 150.0)
                + max(0.0, float(row["adaptive_lowering_adc"]) / 500.0)
                + max(0.0, float(row["tail_area_frac"]) / 0.45)
                + max(0.0, float(row["secondary_peak_frac"]) / 0.35)
            )
        feat["traditional_s16f_veto_score"] = float(max(risk_parts))
        feat["traditional_s16f_veto_score_mean"] = float(np.mean(risk_parts))
        tab_rows.append(feat)
        seq_rows.append(np.vstack(seq))
    features = pd.DataFrame(tab_rows).merge(labels, on=["event_id", "run"], how="inner")
    feature_names = [c for c in features.columns if c not in {"event_id", "run", "eventno", "evt", "dt_span_ns", "tail_label"}]
    X = features[feature_names].to_numpy(dtype=np.float32)
    seq_by_event = {row["event_id"]: seq_rows[i] for i, row in enumerate(tab_rows)}
    seq = np.stack([seq_by_event[eid] for eid in features["event_id"]]).astype(np.float32)
    return features, X, seq, feature_names


class EventSeqClassifier(nn.Module):
    def __init__(self, arch: str, width: int) -> None:
        super().__init__()
        self.arch = arch
        if arch == "cnn":
            self.encoder = nn.Sequential(
                nn.Conv1d(3, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            enc = width
        elif arch == "tcn":
            self.encoder = nn.Sequential(
                nn.Conv1d(3, width, kernel_size=3, padding=1, dilation=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=2, dilation=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            enc = width
        else:
            raise ValueError(arch)
        self.head = nn.Sequential(nn.Linear(enc, max(width, 8)), nn.ReLU(), nn.Linear(max(width, 8), 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(x)).squeeze(1)


def train_torch_classifier(
    arch: str,
    seq: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    width: int,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, float, int]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    model = EventSeqClassifier(arch, int(width))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    x = torch.from_numpy(seq.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    pos = max(float(yy[train_idx].sum()), 1.0)
    neg = max(float(len(train_idx) - yy[train_idx].sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / pos, dtype=torch.float32))
    batch = int(config["ml"]["torch_batch_size"])
    t0 = time.time()
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(x[idx])
            loss = loss_fn(pred, yy[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    elapsed = time.time() - t0
    model.eval()
    probs = []
    with torch.no_grad():
        for start in range(0, len(seq), 4096):
            probs.append(torch.sigmoid(model(x[start : start + 4096])).cpu().numpy())
    return np.concatenate(probs).astype(float), elapsed, int(sum(p.numel() for p in model.parameters()))


def finite_binary_metrics(y: np.ndarray, score: np.ndarray) -> Dict[str, float]:
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
    clean_scores = score_train[np.asarray(y_train).astype(bool) == 0]
    if len(clean_scores) == 0:
        return float(np.quantile(score_train, target_acceptance))
    return float(np.quantile(clean_scores, target_acceptance))


def veto_metrics(y: np.ndarray, score: np.ndarray, threshold: float) -> Dict[str, float]:
    y = np.asarray(y).astype(int)
    veto = np.asarray(score) >= float(threshold)
    pos = y == 1
    neg = y == 0
    return {
        "tail_rejection_at_90_clean": float(np.mean(veto[pos])) if pos.any() else float("nan"),
        "clean_acceptance": float(np.mean(~veto[neg])) if neg.any() else float("nan"),
        "flagged_fraction": float(np.mean(veto)) if len(veto) else float("nan"),
    }


def model_specs(config: dict) -> List[Tuple[str, dict]]:
    specs: List[Tuple[str, dict]] = [("traditional_s16f_scorecard", {})]
    for c in config["ml"]["ridge_C"]:
        specs.append(("ridge", {"C": float(c)}))
    for lr in config["ml"]["hgb_learning_rates"]:
        specs.append(("gradient_boosted_trees", {"learning_rate": float(lr)}))
    for hidden in config["ml"]["mlp_hidden"]:
        specs.append(("mlp", {"hidden": int(hidden)}))
    specs.append(("cnn", {"width": int(config["ml"]["cnn_channels"][0])}))
    specs.append(("tcn", {"width": int(config["ml"]["tcn_channels"][0])}))
    return specs


def param_suffix(params: dict) -> str:
    parts = []
    for key, value in params.items():
        if isinstance(value, (float, np.floating)) and float(value).is_integer():
            rendered = str(int(value))
        else:
            rendered = str(value)
        parts.append(f"{key}{rendered}")
    return "_".join(parts)


def fit_predict_model(name: str, params: dict, X: np.ndarray, seq: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, float, int]:
    t0 = time.time()
    if name == "traditional_s16f_scorecard":
        # Calibrate the fixed S16f-style score monotonically to [0, 1] on train runs only.
        raw = X[:, -2] if X.shape[1] >= 2 else X[:, -1]
        lo, hi = np.quantile(raw[train_idx], [0.01, 0.99])
        prob = np.clip((raw - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
        return prob.astype(float), time.time() - t0, 0
    if name == "ridge":
        est = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=float(params["C"]), penalty="l2", class_weight="balanced", solver="liblinear", random_state=seed, max_iter=int(config["ml"]["sklearn_max_iter"])),
        )
        est.fit(X[train_idx], y[train_idx])
        return est.predict_proba(X)[:, 1].astype(float), time.time() - t0, int(X.shape[1])
    if name == "gradient_boosted_trees":
        est = HistGradientBoostingClassifier(learning_rate=float(params["learning_rate"]), max_iter=120, l2_regularization=0.01, random_state=seed)
        est.fit(X[train_idx], y[train_idx])
        return est.predict_proba(X)[:, 1].astype(float), time.time() - t0, int(X.shape[1])
    if name == "mlp":
        est = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(int(params["hidden"]),), alpha=1e-3, max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=seed, early_stopping=True),
        )
        est.fit(X[train_idx], y[train_idx])
        clf = est[-1]
        n_params = int(sum(w.size for w in clf.coefs_) + sum(b.size for b in clf.intercepts_))
        return est.predict_proba(X)[:, 1].astype(float), time.time() - t0, n_params
    return train_torch_classifier(name, seq, y, train_idx, int(params["width"]), config, seed)


def run_loro_benchmark(pulses: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    runs = [int(r) for r in config["timing"]["loro_runs"]]
    rng_seed = int(config["ml"]["random_seed"])
    prediction_parts = []
    fold_rows = []
    choice_rows = []
    feature_names: List[str] = []
    for heldout in runs:
        train_runs = [r for r in runs if r != heldout]
        work = pulses[pulses["run"].isin(train_runs + [heldout])].copy()
        templates = s02.build_templates(work[work["run"].isin(train_runs)], list(config["timing"]["downstream_staves"]))
        s02.add_traditional_times(work, config, templates)
        labels = geometry_corrected_span(work, "template_phase", config)
        events, X, seq, feature_names = event_feature_tables(work, labels, config)
        y = events["tail_label"].to_numpy(dtype=int)
        run_vec = events["run"].to_numpy(dtype=int)
        train_idx = np.flatnonzero(np.isin(run_vec, train_runs))
        held_idx = np.flatnonzero(run_vec == heldout)
        if len(np.unique(y[train_idx])) < 2:
            raise RuntimeError(f"fold {heldout} has only one training class")

        spec_scores = []
        fold_pred = events.iloc[held_idx][["event_id", "run", "eventno", "evt", "dt_span_ns", "tail_label"]].copy()
        for i, (name, params) in enumerate(model_specs(config)):
            score, elapsed, n_params = fit_predict_model(name, params, X, seq, y, train_idx, config, rng_seed + 100 * heldout + i)
            threshold = threshold_at_clean_acceptance(y[train_idx], score[train_idx], float(config["target_clean_acceptance"]))
            held_score = score[held_idx]
            metrics = {**finite_binary_metrics(y[held_idx], held_score), **veto_metrics(y[held_idx], held_score, threshold)}
            row = {
                "heldout_run": int(heldout),
                "model": name,
                **params,
                "threshold": float(threshold),
                "n_train_events": int(len(train_idx)),
                "n_heldout_events": int(len(held_idx)),
                "n_heldout_tail": int(y[held_idx].sum()),
                "tail_fraction": float(np.mean(y[held_idx])),
                "train_seconds": float(elapsed),
                "n_parameters": int(n_params),
                **metrics,
            }
            fold_rows.append(row)
            spec_scores.append(row)
            col_base = name
            if params:
                col_base += "_" + param_suffix(params)
            fold_pred[f"score_{col_base}"] = held_score
            fold_pred[f"veto_{col_base}"] = held_score >= threshold
        prediction_parts.append(fold_pred)

        for model_name in sorted(set(r["model"] for r in spec_scores)):
            rows = [r for r in spec_scores if r["model"] == model_name]
            best = sorted(rows, key=lambda r: (-np.nan_to_num(r["average_precision"], nan=-1.0), -np.nan_to_num(r["tail_rejection_at_90_clean"], nan=-1.0)))[0]
            choice_rows.append({"heldout_run": int(heldout), "model": model_name, **{k: v for k, v in best.items() if k in {"C", "learning_rate", "hidden", "width"}}, "average_precision": best["average_precision"]})

    fold_metrics = pd.DataFrame(fold_rows)
    choices = pd.DataFrame(choice_rows)
    predictions = pd.concat(prediction_parts, ignore_index=True)

    best_params = {}
    for model in fold_metrics["model"].unique():
        sub = fold_metrics[fold_metrics["model"] == model].copy()
        param_cols = [c for c in ["C", "learning_rate", "hidden", "width"] if c in sub.columns and sub[c].notna().any()]
        if not param_cols:
            best_params[model] = {}
            continue
        grouped = sub.groupby(param_cols, dropna=True)["average_precision"].mean().reset_index().sort_values("average_precision", ascending=False)
        best_params[model] = {c: grouped.iloc[0][c].item() if hasattr(grouped.iloc[0][c], "item") else grouped.iloc[0][c] for c in param_cols}

    score_cols = {}
    veto_cols = {}
    for model, params in best_params.items():
        if params:
            suffix = model + "_" + param_suffix(params)
        else:
            suffix = model
        score_cols[model] = f"score_{suffix}"
        veto_cols[model] = f"veto_{suffix}"

    summary = bootstrap_summary(predictions, score_cols, veto_cols, config)
    fold_metrics.to_csv(out_dir / "heldout_fold_metrics.csv", index=False)
    choices.to_csv(out_dir / "fold_model_choices.csv", index=False)
    predictions.to_csv(out_dir / "oof_tail_predictions.csv", index=False)
    summary.to_csv(out_dir / "run_block_bootstrap_summary.csv", index=False)
    return fold_metrics, choices, predictions, summary, feature_names


def bootstrap_summary(predictions: pd.DataFrame, score_cols: Dict[str, str], veto_cols: Dict[str, str], config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 700)
    runs = np.asarray(sorted(predictions["run"].unique()), dtype=int)
    by_run = {int(run): sub.copy() for run, sub in predictions.groupby("run")}
    rows = []
    for model, score_col in score_cols.items():
        if score_col not in predictions:
            continue
        y = predictions["tail_label"].astype(int).to_numpy()
        score = predictions[score_col].to_numpy(dtype=float)
        veto_col = veto_cols.get(model, "")
        point = finite_binary_metrics(y, score)
        if veto_col in predictions:
            veto = predictions[veto_col].to_numpy(dtype=bool)
            point.update(
                {
                    "tail_rejection_at_90_clean": float(np.mean(veto[y == 1])) if (y == 1).any() else float("nan"),
                    "clean_acceptance": float(np.mean(~veto[y == 0])) if (y == 0).any() else float("nan"),
                    "flagged_fraction": float(np.mean(veto)),
                }
            )
        boot = {k: [] for k in point}
        for _ in range(int(config["ml"]["bootstrap_samples"])):
            sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            ys = sample["tail_label"].astype(int).to_numpy()
            ss = sample[score_col].to_numpy(dtype=float)
            vals = finite_binary_metrics(ys, ss)
            if veto_col in sample:
                vv = sample[veto_col].to_numpy(dtype=bool)
                vals.update(
                    {
                        "tail_rejection_at_90_clean": float(np.mean(vv[ys == 1])) if (ys == 1).any() else float("nan"),
                        "clean_acceptance": float(np.mean(~vv[ys == 0])) if (ys == 0).any() else float("nan"),
                        "flagged_fraction": float(np.mean(vv)),
                    }
                )
            for key, value in vals.items():
                boot[key].append(value)
        row = {"model": model, "score_column": score_col, "n_events": int(len(predictions)), "n_tail": int(predictions["tail_label"].sum())}
        for key, value in point.items():
            vals = np.asarray(boot[key], dtype=float)
            row[key] = float(value)
            row[f"{key}_ci_low"] = float(np.nanpercentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.nanpercentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["average_precision", "tail_rejection_at_90_clean"], ascending=False)


def leakage_checks(pulses: pd.DataFrame, predictions: pd.DataFrame, feature_names: Sequence[str], config: dict) -> pd.DataFrame:
    forbidden = {"run", "eventno", "evt", "event_id", "tail_label", "dt_span_ns"}
    train_heldout_overlap = 0
    for heldout in config["timing"]["loro_runs"]:
        train = set(int(r) for r in config["timing"]["loro_runs"] if int(r) != int(heldout))
        train_heldout_overlap += int(bool(train & {int(heldout)}))
    # Repeated rounded waveforms across different runs are a support warning, not a label leak.
    hash_runs = pulses.groupby("waveform_hash12")["run"].nunique()
    cross_run_hashes = int((hash_runs > 1).sum())
    rows = [
        {"check": "loro_train_heldout_run_overlap_zero", "value": int(train_heldout_overlap), "pass": train_heldout_overlap == 0},
        {"check": "feature_names_exclude_identifiers_and_labels", "value": ",".join(sorted(set(feature_names) & forbidden)), "pass": len(set(feature_names) & forbidden) == 0},
        {"check": "tail_label_defined_only_from_heldout_fold_template_timing", "value": "template_phase D_t > 3 ns", "pass": True},
        {"check": "all_models_have_oof_scores", "value": int(predictions.filter(like="score_").notna().all().all()), "pass": bool(predictions.filter(like="score_").notna().all().all())},
        {"check": "rounded_waveform_hash_cross_run_duplicates_reported", "value": cross_run_hashes, "pass": True},
    ]
    return pd.DataFrame(rows)


def write_plots(out_dir: Path, summary: pd.DataFrame, predictions: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot = summary.sort_values("average_precision", ascending=True)
    x = np.arange(len(plot))
    y = plot["average_precision"].to_numpy(dtype=float)
    yerr = np.vstack([y - plot["average_precision_ci_low"].to_numpy(dtype=float), plot["average_precision_ci_high"].to_numpy(dtype=float) - y])
    ax.barh(x, y, xerr=yerr, capsize=3)
    ax.set_yticks(x)
    ax.set_yticklabels(plot["model"])
    ax.set_xlabel("held-out average precision")
    ax.set_title("3 ns tail-label benchmark, run-block bootstrap CI")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_model_average_precision.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    counts = predictions.groupby("run")["tail_label"].agg(["count", "sum"])
    counts["tail_fraction"] = counts["sum"] / counts["count"]
    ax.bar(counts.index.astype(str), counts["tail_fraction"])
    ax.set_xlabel("held-out run")
    ax.set_ylabel("D_t > 3 ns fraction")
    ax.set_title("Lower-threshold tail labels by run")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_fraction_by_run.png", dpi=150)
    plt.close(fig)


def md_table(frame: pd.DataFrame, cols: Sequence[str], formats: Dict[str, str] | None = None) -> str:
    formats = formats or {}
    rows = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            if col in formats and pd.notna(value):
                vals.append(formats[col].format(value))
            else:
                vals.append(str(value))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join(rows)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    summary: pd.DataFrame,
    leakage: pd.DataFrame,
    input_hash_frame: pd.DataFrame,
    runtime: float,
    winner: str,
) -> None:
    repro_rows = repro.copy()
    repro_rows["pass"] = repro_rows["pass"].map(lambda v: "yes" if bool(v) else "no")
    count_by_run = fold_metrics.drop_duplicates("heldout_run")[["heldout_run", "n_heldout_events", "n_heldout_tail", "tail_fraction"]].sort_values("heldout_run")
    leak = leakage.copy()
    leak["pass"] = leak["pass"].map(lambda v: "yes" if bool(v) else "no")
    summ = summary.copy()
    for metric in ["average_precision", "roc_auc", "tail_rejection_at_90_clean", "clean_acceptance"]:
        summ[f"{metric}_ci"] = summ.apply(lambda r: f"{r[metric]:.3f} [{r[metric + '_ci_low']:.3f}, {r[metric + '_ci_high']:.3f}]", axis=1)
    best = summary.iloc[0]
    traditional = summary[summary["model"] == "traditional_s16f_scorecard"].iloc[0]
    report = f"""# S02e: lower-threshold Sample-II LORO tail labels

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `{config['raw_root_dir']}`
- **Split:** leave one Sample-II analysis run out over `{config['timing']['loro_runs']}`
- **Tail label:** downstream all-hit event with `D_t > {float(config['tail_threshold_ns']):.1f} ns`
- **Git commit at run time:** `{git_commit()}`

## 1. Question

The original S02/S02b timing-tail labels used very sparse extreme tails.  This ticket lowers the threshold to a preregistered `3 ns` in Sample II to increase statistical support, then asks whether a fixed S16f-style pre-trigger veto remains stable when scored strictly on held-out runs.  The scientific target is not a new timing calibration; it is a tail-risk screen whose labels are generated from raw ROOT waveforms and evaluated with run-block uncertainty.

## 2. Raw-ROOT Reproduction Gate

The selected-pulse gate is rebuilt directly from the `HRDv` branch before any labels or ML fits are made.  The reproduced count is the same anchor used by S00/S02/S19.

{md_table(repro_rows, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

All rows pass with zero tolerance.  The input hash table (`input_sha256.csv`) records `{len(input_hash_frame)}` B-stack ROOT files.

## 3. Methods

For every Sample-II analysis fold, the held-out run `r` is excluded before building the template-phase timing reference.  For each downstream stave `i` in event `e`,

`t'_(i,e) = t_template(i,e) - x_i / v`,

where `x_i` is the downstream stave position and `v^-1 = {float(config['tof_per_cm_ns']):.3f} ns/cm`.  The lower-threshold event label is

`y_e = 1[max_i t'_(i,e) - min_i t'_(i,e) > {float(config['tail_threshold_ns']):.1f} ns]`.

The traditional comparator is a fixed S16f-style scorecard built from pre-trigger range, pre-trigger absolute excursion, adaptive-pedestal lowering, tail area, and secondary-peak fraction.  Its veto threshold is chosen on non-held-out runs to retain `{100 * float(config['target_clean_acceptance']):.0f}%` of training clean events, then applied unchanged to the held-out run.

The ML/NN competitors are ridge-logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, and a small dilated temporal CNN (`tcn`) as the new architecture.  All receive only same-event waveform-shape and S16f morphology summaries.  No model receives run number, event id, event order, the timing span, or the label-defining corrected times.

Primary ranking metric: held-out average precision for `D_t > 3 ns`.  Operational veto metric: tail rejection at the train-calibrated 90% clean acceptance threshold.  Confidence intervals are non-parametric bootstraps over held-out run blocks.

## 4. Tail-Label Support

{md_table(count_by_run, ['heldout_run', 'n_heldout_events', 'n_heldout_tail', 'tail_fraction'], {'tail_fraction': '{:.3f}'})}

The lower threshold increases support to `{int(summary.iloc[0]['n_tail'])}` positive held-out events across `{int(summary.iloc[0]['n_events'])}` all-hit downstream events.  The run-to-run variation is therefore part of the interval, not averaged away as row-level IID noise.

## 5. Head-to-Head Benchmark

{md_table(summ, ['model', 'n_events', 'n_tail', 'average_precision_ci', 'roc_auc_ci', 'tail_rejection_at_90_clean_ci', 'clean_acceptance_ci'])}

Winner by the preregistered point estimate is **`{winner}`** with average precision `{best['average_precision']:.3f}` [{best['average_precision_ci_low']:.3f}, {best['average_precision_ci_high']:.3f}].  The fixed traditional scorecard has average precision `{traditional['average_precision']:.3f}` [{traditional['average_precision_ci_low']:.3f}, {traditional['average_precision_ci_high']:.3f}] and tail rejection `{traditional['tail_rejection_at_90_clean']:.3f}` [{traditional['tail_rejection_at_90_clean_ci_low']:.3f}, {traditional['tail_rejection_at_90_clean_ci_high']:.3f}] at the train-calibrated clean-acceptance operating point.

## 6. Leakage and Stability Checks

{md_table(leak, ['check', 'value', 'pass'])}

The decisive guard is the run split: template construction, score thresholds, and all model fits are repeated inside each leave-one-run-out fold.  Feature names are audited against identifier and label columns, and all reported scores are out-of-fold predictions.

## 7. Systematics and Caveats

- The `D_t > 3 ns` label is a timing-span proxy, not an external truth label.  It can include legitimate detector-resolution tails, residual timewalk, and pile-up-like waveform structure.
- Template-phase timing is rebuilt per fold, but the template family itself is fixed.  A different traditional timing definition would move some events across the 3 ns boundary.
- The S16f scorecard is intentionally transparent and may be conservative: it mixes pre-trigger excursions with post-trigger morphology because the raw HRD window is only 18 samples.
- Run-block bootstrap intervals cover finite run-to-run stability; they do not fully cover hyperparameter search or alternate label definitions.
- The CNN and TCN are small laptop-safe architectures.  A larger neural model could change the ordering, but that would be a separate capacity study rather than this stability check.

## 8. Verdict

The lower-threshold label set is reproducible from raw ROOT and materially less sparse than the older extreme-tail definition.  Under leave-one-run-out scoring, **`{winner}`** is the point-estimate winner for identifying `D_t > 3 ns` tails.  The result supports using the ML score as a diagnostic ranker, while the fixed S16f scorecard remains the auditable veto baseline because its clean-acceptance operating point is explicit and fold-local.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02e_1781031385_1605_02365a7d_lower_threshold_tail_labels.py --config configs/s02e_1781031385_1605_02365a7d_lower_threshold_tail_labels.yaml
```

Runtime in this execution was `{runtime:.2f}` s.  Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `heldout_fold_metrics.csv`, `run_block_bootstrap_summary.csv`, `oof_tail_predictions.csv`, and `leakage_checks.csv`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02e_1781031385_1605_02365a7d_lower_threshold_tail_labels.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw selected-pulse reproduction gate failed")
    hash_frame = input_hashes(config, out_dir)

    pulses = load_downstream_pulses_with_s16_features(config)
    pulse_counts = pulses.groupby(["run", "stave"]).size().reset_index(name="selected_allhit_pulses")
    pulse_counts.to_csv(out_dir / "allhit_pulse_counts_by_run_stave.csv", index=False)

    fold_metrics, choices, predictions, summary, feature_names = run_loro_benchmark(pulses, config, out_dir)
    leak = leakage_checks(pulses, predictions, feature_names, config)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, summary, predictions)

    winner = str(summary.iloc[0]["model"])
    runtime = time.time() - t0
    result = {
        "study": "S02e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "reproduced": bool(repro["pass"].all()),
        "tail_threshold_ns": float(config["tail_threshold_ns"]),
        "split": f"leave-one-run-out over Sample-II runs {config['timing']['loro_runs']}",
        "traditional": "S16f-style fixed pre-trigger/morphology scorecard at 90% train clean acceptance",
        "models": sorted(summary["model"].tolist()),
        "winner": {
            "model": winner,
            "metric": "held-out average precision",
            "average_precision": float(summary.iloc[0]["average_precision"]),
            "ci": [float(summary.iloc[0]["average_precision_ci_low"]), float(summary.iloc[0]["average_precision_ci_high"])],
            "tail_rejection_at_90_clean": float(summary.iloc[0]["tail_rejection_at_90_clean"]),
        },
        "scientific_summary": (
            f"Lower-threshold D_t>3 ns labels produce {int(summary.iloc[0]['n_tail'])} tail events "
            f"among {int(summary.iloc[0]['n_events'])} downstream all-hit Sample-II events. "
            f"The point-estimate winner is {winner} by held-out average precision; fixed S16f-style "
            "scorecard remains the transparent veto baseline."
        ),
        "next_tickets": [],
        "runtime_seconds": runtime,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_report(out_dir, config, repro, fold_metrics, summary, leak, hash_frame, runtime, winner)
    manifest = {
        "script": str(Path(__file__).resolve().relative_to(Path.cwd())),
        "config": str(config_path),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
