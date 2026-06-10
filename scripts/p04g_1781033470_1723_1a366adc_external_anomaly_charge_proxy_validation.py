#!/usr/bin/env python3
"""P04g external validation of P04f anomaly charge bias.

This ticket moves the P04f baseline-excursion and early-pretrigger labels away
from the same-event duplicate-readout target.  It uses two external charge
proxies:

* P04b downstream B4+B6+B8 charge on penetrating B2 events.
* P04c event-matched A1/A3 charge using B-stack predictors.

Every predictive row is produced by a leave-one-run-out fit.  The anomaly
effect is then estimated against controls matched in run, source stave,
amplitude bin, and saturation bin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p04b_external_charge_validation as p04b  # noqa: E402
import p04c_ab_event_matched_charge_transfer as p04c  # noqa: E402
import p09a_rare_waveform_anomaly_taxonomy as p09a  # noqa: E402


METHODS = [
    "traditional_strong",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn1d",
    "residual_cnn_meta",
    "shuffled_target_gbt",
]
REAL_METHODS = [m for m in METHODS if m != "shuffled_target_gbt"]
ANOMALY_COLS = ["label_baseline_excursion", "label_novel_early_pretrigger"]
LABEL_COLS = [
    "label_baseline_excursion",
    "label_novel_early_pretrigger",
    "label_saturation",
    "taxon",
    "baseline_mad",
    "baseline_slope",
    "early_fraction",
    "late_fraction",
    "width_half",
    "saturation_count",
    "secondary_peak",
    "post_peak_min",
    "q_template_rmse",
    "p09a_traditional_score",
    "amplitude_adc",
]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        x = float(value)
        return x if math.isfinite(x) else None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if pd.isna(value) if not isinstance(value, (str, bytes, bool, type(None))) else False:
        return None
    return value


def ci(values: Sequence[float]) -> List[Optional[float]]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def robust_metrics(y: np.ndarray, pred: np.ndarray, high_bias: float) -> dict:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    ok = np.isfinite(y) & np.isfinite(pred) & (y > 0)
    y = y[ok]
    pred = pred[ok]
    if len(y) == 0:
        return {
            "n": 0,
            "bias_median_frac": float("nan"),
            "res68_abs_frac": float("nan"),
            "full_rms_frac": float("nan"),
            "high_bias_tail_fraction": float("nan"),
            "within_10pct": float("nan"),
            "within_25pct": float("nan"),
        }
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(frac)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "high_bias_tail_fraction": float(np.mean(np.abs(frac) > high_bias)),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)),
    }


def run_block_ci(
    frame: pd.DataFrame,
    y_col: str,
    pred_col: str,
    rng: np.random.Generator,
    reps: int,
    high_bias: float,
    max_rows_per_run: int,
) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {
            "bias_ci95": [None, None],
            "res68_ci95": [None, None],
            "full_rms_ci95": [None, None],
            "high_bias_tail_ci95": [None, None],
        }
    by_run: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
    for run in runs:
        sub = frame[frame["run"] == run]
        y = sub[y_col].to_numpy(dtype=float)
        p = sub[pred_col].to_numpy(dtype=float)
        if len(y) > max_rows_per_run:
            idx = rng.choice(np.arange(len(y)), size=max_rows_per_run, replace=False)
            y = y[idx]
            p = p[idx]
        by_run[int(run)] = (y, p)

    biases: List[float] = []
    res68s: List[float] = []
    rmses: List[float] = []
    tails: List[float] = []
    for _ in range(reps):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        yy = np.concatenate([by_run[int(run)][0] for run in sample_runs])
        pp = np.concatenate([by_run[int(run)][1] for run in sample_runs])
        m = robust_metrics(yy, pp, high_bias)
        biases.append(m["bias_median_frac"])
        res68s.append(m["res68_abs_frac"])
        rmses.append(m["full_rms_frac"])
        tails.append(m["high_bias_tail_fraction"])
    return {
        "bias_ci95": ci(biases),
        "res68_ci95": ci(res68s),
        "full_rms_ci95": ci(rmses),
        "high_bias_tail_ci95": ci(tails),
    }


def run_block_delta_ci(
    anomaly: pd.DataFrame,
    control: pd.DataFrame,
    y_col: str,
    pred_col: str,
    rng: np.random.Generator,
    reps: int,
    high_bias: float,
    max_rows_per_run: int,
) -> dict:
    runs = np.asarray(sorted(set(anomaly["run"].unique()).intersection(control["run"].unique())), dtype=int)
    if len(runs) < 2:
        return {
            "delta_bias_ci95": [None, None],
            "delta_res68_ci95": [None, None],
            "delta_high_bias_tail_ci95": [None, None],
        }

    def arrays_by_run(frame: pd.DataFrame) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
        out: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        for run in runs:
            sub = frame[frame["run"] == run]
            y = sub[y_col].to_numpy(dtype=float)
            p = sub[pred_col].to_numpy(dtype=float)
            if len(y) > max_rows_per_run:
                idx = rng.choice(np.arange(len(y)), size=max_rows_per_run, replace=False)
                y = y[idx]
                p = p[idx]
            out[int(run)] = (y, p)
        return out

    a_by = arrays_by_run(anomaly)
    c_by = arrays_by_run(control)
    dbias: List[float] = []
    dres68: List[float] = []
    dtail: List[float] = []
    for _ in range(reps):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        ay = np.concatenate([a_by[int(run)][0] for run in sample_runs])
        ap = np.concatenate([a_by[int(run)][1] for run in sample_runs])
        cy = np.concatenate([c_by[int(run)][0] for run in sample_runs])
        cp = np.concatenate([c_by[int(run)][1] for run in sample_runs])
        ma = robust_metrics(ay, ap, high_bias)
        mc = robust_metrics(cy, cp, high_bias)
        dbias.append(ma["bias_median_frac"] - mc["bias_median_frac"])
        dres68.append(ma["res68_abs_frac"] - mc["res68_abs_frac"])
        dtail.append(ma["high_bias_tail_fraction"] - mc["high_bias_tail_fraction"])
    return {
        "delta_bias_ci95": ci(dbias),
        "delta_res68_ci95": ci(dres68),
        "delta_high_bias_tail_ci95": ci(dtail),
    }


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path)})
    return rows


def load_p09a_labels(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    p09_cfg_path = ROOT / config["p09a_reference_config"]
    p09_cfg = p09a.load_config(p09_cfg_path)
    raw_dir = p09a.resolve_raw_root_dir(p09_cfg)
    waves, meta, counts = p09a.scan_raw(p09_cfg, raw_dir)
    total = int(counts["selected_pulses"].sum())
    expected = int(p09_cfg["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError("P04/P09a raw selected-pulse reproduction failed: {} != {}".format(total, expected))
    heldout_runs = set(int(r) for r in p09_cfg["heldout_runs"])
    train_mask = ~meta["run"].isin(heldout_runs).to_numpy()
    meta = p09a.add_template_residual(p09_cfg, waves, meta, train_mask)
    meta, thresholds = p09a.add_taxonomy(meta, train_mask)
    meta["p09a_traditional_score"] = p09a.score_traditional(meta, train_mask)
    meta["waveform_sha256_rounded"] = p09a.waveform_hashes(waves)
    label_table = meta[["run", "eventno", "evt", "event_index", "stave"] + LABEL_COLS + ["waveform_sha256_rounded"]].copy()
    repro = {
        "expected_selected_pulses": expected,
        "reproduced_selected_pulses": total,
        "delta": total - expected,
        "pass": total == expected,
        "source": "P09a raw scan with the P04/S00 B-stack selected-pulse gate",
        "raw_root_dir": str(raw_dir),
    }
    return label_table, counts, {"p04_s00": repro, "p09a_thresholds": json.loads(thresholds.to_json(orient="records"))}


def add_common_bins(config: dict, frame: pd.DataFrame, amp_col: str) -> pd.DataFrame:
    out = frame.copy()
    edges = np.asarray(config["amplitude_bins"], dtype=float)
    idx = np.clip(np.searchsorted(edges, out[amp_col].to_numpy(dtype=float), side="right") - 1, 0, len(edges) - 2)
    labels = [f"{int(edges[i])}_{'inf' if edges[i + 1] > 1e8 else int(edges[i + 1])}" for i in range(len(edges) - 1)]
    out["source_amp_bin"] = np.asarray(labels, dtype=object)[idx]
    out["source_stave"] = "B2"
    out["saturation_bin"] = (out["saturation_count"].to_numpy(dtype=float) >= float(config["saturation_count_threshold"])).astype(int)
    out["normal_control_pool"] = (~out["label_baseline_excursion"]) & (~out["label_novel_early_pretrigger"])
    return out


def attach_labels_p04b(config: dict, frame: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    b2 = labels[labels["stave"] == "B2"].drop(columns=["stave", "event_index"]).copy()
    merged = frame.merge(b2, on=["run", "eventno", "evt"], how="left", validate="one_to_one")
    if merged["taxon"].isna().any():
        missing = int(merged["taxon"].isna().sum())
        raise RuntimeError("P04b label join missed {} rows".format(missing))
    return add_common_bins(config, merged, "b2_amp")


def attach_labels_p04c(config: dict, frame: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    b2 = labels[labels["stave"] == "B2"].sort_values(["run", "evt", "event_index"]).drop_duplicates(["run", "evt"], keep="first")
    b2 = b2.drop(columns=["stave", "eventno", "event_index"]).copy()
    merged = frame.merge(b2, on=["run", "evt"], how="left", validate="many_to_one")
    if merged["taxon"].isna().any():
        missing = int(merged["taxon"].isna().sum())
        raise RuntimeError("P04c label join missed {} rows".format(missing))
    return add_common_bins(config, merged, "b2_amp")


def p04b_traditional_features(frame: pd.DataFrame) -> np.ndarray:
    q = np.log(np.maximum(frame["b2_charge"].to_numpy(dtype=float), 1.0))
    a = np.log(np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0))
    return np.column_stack([q, a, q * q, a * a, q * a])


def p04b_ml_features(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    charge = np.clip(wave, 0.0, None).sum(axis=1)
    amp = wave.max(axis=1)
    peak = wave.argmax(axis=1)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / total
    early = np.clip(wave[:, :4], 0.0, None).sum(axis=1) / total
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    anomaly_features = frame[
        [
            "baseline_mad",
            "baseline_slope",
            "early_fraction",
            "late_fraction",
            "width_half",
            "saturation_count",
            "secondary_peak",
            "post_peak_min",
            "q_template_rmse",
            "p09a_traditional_score",
        ]
    ].to_numpy(dtype=float)
    flags = frame[["label_baseline_excursion", "label_novel_early_pretrigger", "label_saturation"]].astype(float).to_numpy()
    return np.column_stack(
        [
            wave,
            np.log(np.maximum(charge, 1.0)),
            np.log(np.maximum(amp, 1.0)),
            peak,
            tail,
            late,
            early,
            half_width,
            anomaly_features,
            flags,
        ]
    )


def p04c_traditional_features(frame: pd.DataFrame) -> np.ndarray:
    b2q = np.log(np.maximum(frame["b2_charge"].to_numpy(dtype=float), 1.0))
    bt = np.log(np.maximum(frame["b_total_charge"].to_numpy(dtype=float), 1.0))
    bd = np.log1p(frame["b_downstream_charge"].to_numpy(dtype=float))
    b2a = np.log(np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0))
    down_frac = frame["b_downstream_charge"].to_numpy(dtype=float) / np.maximum(frame["b_total_charge"].to_numpy(dtype=float), 1.0)
    return np.column_stack(
        [
            b2q,
            bt,
            bd,
            b2a,
            b2q * b2q,
            bt * bt,
            b2q * bt,
            down_frac,
            frame["b_mult"].to_numpy(dtype=float),
            frame["b_downstream_mult"].to_numpy(dtype=float),
        ]
    )


def p04c_ml_features(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    charge = np.clip(wave, 0.0, None).sum(axis=2)
    amp = wave.max(axis=2)
    peak = wave.argmax(axis=2)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, :, 12:], 0.0, None).sum(axis=2) / total
    late = np.clip(wave[:, :, 9:], 0.0, None).sum(axis=2) / total
    half_width = (wave > (0.5 * amp[:, :, None])).sum(axis=2)
    anomaly_features = frame[
        [
            "baseline_mad",
            "baseline_slope",
            "early_fraction",
            "late_fraction",
            "width_half",
            "saturation_count",
            "secondary_peak",
            "post_peak_min",
            "q_template_rmse",
            "p09a_traditional_score",
        ]
    ].to_numpy(dtype=float)
    flags = frame[["label_baseline_excursion", "label_novel_early_pretrigger", "label_saturation"]].astype(float).to_numpy()
    return np.column_stack(
        [
            wave.reshape(len(wave), -1),
            np.log(np.maximum(charge, 1.0)),
            np.log(np.maximum(amp, 1.0)),
            peak,
            tail,
            late,
            half_width,
            frame[["b_mult", "b_downstream_mult"]].to_numpy(dtype=float),
            anomaly_features,
            flags,
        ]
    )


def standardize_train_apply(x: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.nanmean(x[train_idx], axis=0)
    std = np.nanstd(x[train_idx], axis=0)
    std = np.where(std > 1e-9, std, 1.0)
    z = (np.nan_to_num(x, nan=mean) - mean) / std
    return z.astype(np.float32), mean.astype(np.float32), std.astype(np.float32)


def train_torch_predict(
    seq: np.ndarray,
    meta: np.ndarray,
    y_log: np.ndarray,
    train_idx: np.ndarray,
    held_idx: np.ndarray,
    config: dict,
    seed: int,
    residual_base_log: Optional[np.ndarray] = None,
) -> np.ndarray:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, torch.get_num_threads())))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    seq_z, _, _ = standardize_train_apply(seq.reshape(len(seq), -1), train_idx)
    seq_z = seq_z.reshape(seq.shape)
    meta_z, _, _ = standardize_train_apply(meta, train_idx)
    target = y_log.copy()
    if residual_base_log is not None:
        target = y_log - residual_base_log
    y_mean = float(np.mean(target[train_idx]))
    y_std = float(np.std(target[train_idx]) or 1.0)
    y_scaled = ((target - y_mean) / y_std).astype(np.float32)

    class CnnMeta(nn.Module):
        def __init__(self, in_channels: int, meta_dim: int) -> None:
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(in_channels, 16, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(16, 24, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.head = nn.Sequential(
                nn.Linear(24 + meta_dim, 48),
                nn.ReLU(),
                nn.Dropout(0.05),
                nn.Linear(48, 1),
            )

        def forward(self, s, m):
            h = self.conv(s).squeeze(-1)
            return self.head(torch.cat([h, m], dim=1)).squeeze(1)

    model = CnnMeta(int(seq.shape[1]), int(meta_z.shape[1])).to(device)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["models"]["torch_learning_rate"]),
        weight_decay=float(config["models"]["torch_weight_decay"]),
    )
    lossf = nn.SmoothL1Loss()
    batch_size = int(config["models"]["torch_batch_size"])
    epochs = int(config["models"]["torch_epochs"])
    patience = int(config["models"]["torch_patience"])
    rng = np.random.default_rng(seed)
    train_idx = np.asarray(train_idx, dtype=int)
    val_size = max(1, int(0.12 * len(train_idx)))
    val_idx = rng.choice(train_idx, size=val_size, replace=False)
    fit_idx = np.setdiff1d(train_idx, val_idx, assume_unique=False)
    if len(fit_idx) < 10:
        fit_idx = train_idx
        val_idx = train_idx

    seq_t = torch.tensor(seq_z, dtype=torch.float32, device=device)
    meta_t = torch.tensor(meta_z, dtype=torch.float32, device=device)
    y_t = torch.tensor(y_scaled, dtype=torch.float32, device=device)
    best_state = None
    best_val = float("inf")
    stale = 0
    for _ in range(epochs):
        model.train()
        perm = rng.permutation(fit_idx)
        for start in range(0, len(perm), batch_size):
            idx = torch.tensor(perm[start : start + batch_size], dtype=torch.long, device=device)
            opt.zero_grad()
            loss = lossf(model(seq_t[idx], meta_t[idx]), y_t[idx])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            vidx = torch.tensor(val_idx, dtype=torch.long, device=device)
            val_loss = float(lossf(model(seq_t[vidx], meta_t[vidx]), y_t[vidx]).item())
        if val_loss + 1e-5 < best_val:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    preds: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(held_idx), batch_size):
            idx_np = np.asarray(held_idx[start : start + batch_size], dtype=int)
            idx = torch.tensor(idx_np, dtype=torch.long, device=device)
            chunk = model(seq_t[idx], meta_t[idx]).detach().cpu().numpy() * y_std + y_mean
            if residual_base_log is not None:
                chunk = chunk + residual_base_log[idx_np]
            preds.append(chunk)
    return np.concatenate(preds)


def fit_loglinear_traditional(x: np.ndarray, y_log: np.ndarray, train_idx: np.ndarray, held_idx: np.ndarray) -> np.ndarray:
    model = LinearRegression()
    model.fit(x[train_idx], y_log[train_idx])
    return model.predict(x[held_idx])


def fit_dataset_models(
    config: dict,
    dataset_name: str,
    frame: pd.DataFrame,
    wave: np.ndarray,
    target_col: str,
    trad_x: np.ndarray,
    ml_x: np.ndarray,
    seq: np.ndarray,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = frame.copy()
    y = out[target_col].to_numpy(dtype=float)
    y_log = np.log(np.maximum(y, 1.0))
    for method in METHODS:
        out[f"pred_{method}"] = np.nan

    rng = np.random.default_rng(int(config["random_seed"]) + (100 if dataset_name == "p04b_downstream" else 200))
    runs = np.asarray(sorted(out["run"].unique()), dtype=int)
    fold_rows = []
    for heldout_run in runs:
        train_mask = out["run"].to_numpy() != heldout_run
        held_mask = ~train_mask
        train_idx = np.where(train_mask)[0]
        held_idx = np.where(held_mask)[0]
        if len(held_idx) == 0:
            continue
        fit_idx = train_idx
        if len(fit_idx) > int(config["ml_max_train_rows"]):
            fit_idx = rng.choice(fit_idx, size=int(config["ml_max_train_rows"]), replace=False)

        trad_log = fit_loglinear_traditional(trad_x, y_log, train_idx, held_idx)
        out.loc[held_mask, "pred_traditional_strong"] = np.exp(trad_log)

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(config["models"]["ridge_alpha"])))
        ridge.fit(ml_x[fit_idx], y_log[fit_idx])
        out.loc[held_mask, "pred_ridge"] = np.exp(ridge.predict(ml_x[held_idx]))

        hgb = HistGradientBoostingRegressor(
            max_iter=int(config["models"]["hgb_max_iter"]),
            learning_rate=float(config["models"]["hgb_learning_rate"]),
            max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
            l2_regularization=0.08,
            random_state=int(config["random_seed"]) + int(heldout_run),
        )
        hgb.fit(ml_x[fit_idx], y_log[fit_idx])
        out.loc[held_mask, "pred_gradient_boosted_trees"] = np.exp(hgb.predict(ml_x[held_idx]))

        mlp = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=tuple(int(x) for x in config["models"]["mlp_hidden_layer_sizes"]),
                alpha=float(config["models"]["mlp_alpha"]),
                learning_rate_init=float(config["models"]["mlp_learning_rate_init"]),
                max_iter=int(config["models"]["mlp_max_iter"]),
                early_stopping=True,
                n_iter_no_change=12,
                batch_size=min(512, max(64, len(fit_idx))),
                random_state=int(config["random_seed"]) + 17 + int(heldout_run),
            ),
        )
        mlp.fit(ml_x[fit_idx], y_log[fit_idx])
        out.loc[held_mask, "pred_mlp"] = np.exp(mlp.predict(ml_x[held_idx]))

        cnn_log = train_torch_predict(
            seq,
            ml_x,
            y_log,
            fit_idx,
            held_idx,
            config,
            int(config["random_seed"]) + 31 + int(heldout_run),
            residual_base_log=None,
        )
        out.loc[held_mask, "pred_cnn1d"] = np.exp(cnn_log)

        base_log = np.log(np.maximum(out["pred_traditional_strong"].to_numpy(dtype=float), 1.0))
        base_log[train_idx] = fit_loglinear_traditional(trad_x, y_log, train_idx, train_idx)
        res_log = train_torch_predict(
            seq,
            ml_x,
            y_log,
            fit_idx,
            held_idx,
            config,
            int(config["random_seed"]) + 53 + int(heldout_run),
            residual_base_log=base_log,
        )
        out.loc[held_mask, "pred_residual_cnn_meta"] = np.exp(res_log)

        shuffled = y_log[fit_idx].copy()
        rng.shuffle(shuffled)
        shuf = HistGradientBoostingRegressor(
            max_iter=max(40, int(config["models"]["hgb_max_iter"]) // 2),
            learning_rate=float(config["models"]["hgb_learning_rate"]),
            max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
            l2_regularization=0.08,
            random_state=int(config["random_seed"]) + 1000 + int(heldout_run),
        )
        shuf.fit(ml_x[fit_idx], shuffled)
        out.loc[held_mask, "pred_shuffled_target_gbt"] = np.exp(shuf.predict(ml_x[held_idx]))

        fold_rows.append(
            {
                "dataset": dataset_name,
                "heldout_run": int(heldout_run),
                "n_train": int(train_mask.sum()),
                "n_fit": int(len(fit_idx)),
                "n_heldout": int(held_mask.sum()),
                "train_heldout_run_overlap": int(np.isin(out.loc[train_mask, "run"].unique(), [heldout_run]).sum()),
            }
        )
        print("{} fold run {}: heldout {} rows".format(dataset_name, int(heldout_run), int(held_mask.sum())))

    for method in METHODS:
        if out[f"pred_{method}"].isna().any():
            raise RuntimeError("{} missing predictions for {}".format(dataset_name, method))
    return out, pd.DataFrame(fold_rows)


def matched_control_indices(frame: pd.DataFrame, anomaly_mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    normal = frame.loc[frame["normal_control_pool"]].copy()
    normal["_idx"] = normal.index.to_numpy()
    anomaly = frame.loc[anomaly_mask, ["run", "source_stave", "source_amp_bin", "saturation_bin"]]
    pieces: List[np.ndarray] = []
    keys = ["run", "source_stave", "source_amp_bin", "saturation_bin"]
    for key, sub in anomaly.groupby(keys, sort=True):
        pool = normal
        for col, value in zip(keys, key):
            pool = pool[pool[col] == value]
        if len(pool) == 0:
            continue
        take = min(len(pool), len(sub))
        pieces.append(rng.choice(pool["_idx"].to_numpy(), size=take, replace=False))
    if not pieces:
        return np.asarray([], dtype=int)
    idx = np.concatenate(pieces).astype(int)
    rng.shuffle(idx)
    return idx


def summarize_dataset(
    config: dict,
    dataset_name: str,
    frame: pd.DataFrame,
    target_col: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 991 + (0 if dataset_name == "p04b_downstream" else 1000))
    reps = int(config["bootstrap_reps"])
    high_bias = float(config["high_bias_abs_frac"])
    max_rows = int(config["bootstrap_max_rows_per_run"])
    strata = {
        "all_rows": np.ones(len(frame), dtype=bool),
        "normal_control_pool": frame["normal_control_pool"].to_numpy(dtype=bool),
        "baseline_excursion": frame["label_baseline_excursion"].to_numpy(dtype=bool),
        "novel_early_pretrigger": frame["label_novel_early_pretrigger"].to_numpy(dtype=bool),
    }
    matched = {
        "matched_normal_for_baseline_excursion": matched_control_indices(frame, strata["baseline_excursion"], rng),
        "matched_normal_for_novel_early_pretrigger": matched_control_indices(frame, strata["novel_early_pretrigger"], rng),
    }

    summary_rows = []
    for stratum, mask in strata.items():
        sub = frame.loc[mask].copy()
        if len(sub) == 0:
            continue
        for method in METHODS:
            row = {"dataset": dataset_name, "stratum": stratum, "method": method}
            row.update(robust_metrics(sub[target_col].to_numpy(), sub[f"pred_{method}"].to_numpy(), high_bias))
            row.update(run_block_ci(sub, target_col, f"pred_{method}", rng, reps, high_bias, max_rows))
            summary_rows.append(row)
    for stratum, idx in matched.items():
        sub = frame.loc[idx].copy()
        if len(sub) == 0:
            continue
        for method in METHODS:
            row = {"dataset": dataset_name, "stratum": stratum, "method": method}
            row.update(robust_metrics(sub[target_col].to_numpy(), sub[f"pred_{method}"].to_numpy(), high_bias))
            row.update(run_block_ci(sub, target_col, f"pred_{method}", rng, reps, high_bias, max_rows))
            summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)

    delta_rows = []
    pairs = [
        ("baseline_excursion", "matched_normal_for_baseline_excursion", strata["baseline_excursion"], matched["matched_normal_for_baseline_excursion"]),
        (
            "novel_early_pretrigger",
            "matched_normal_for_novel_early_pretrigger",
            strata["novel_early_pretrigger"],
            matched["matched_normal_for_novel_early_pretrigger"],
        ),
    ]
    for anomaly_name, control_name, amask, cidx in pairs:
        anomaly = frame.loc[amask].copy()
        control = frame.loc[cidx].copy()
        if len(anomaly) == 0 or len(control) == 0:
            continue
        for method in METHODS:
            ma = robust_metrics(anomaly[target_col].to_numpy(), anomaly[f"pred_{method}"].to_numpy(), high_bias)
            mc = robust_metrics(control[target_col].to_numpy(), control[f"pred_{method}"].to_numpy(), high_bias)
            row = {
                "dataset": dataset_name,
                "anomaly_stratum": anomaly_name,
                "control_stratum": control_name,
                "method": method,
                "n_anomaly": ma["n"],
                "n_control": mc["n"],
                "delta_bias_median_frac": ma["bias_median_frac"] - mc["bias_median_frac"],
                "delta_res68_abs_frac": ma["res68_abs_frac"] - mc["res68_abs_frac"],
                "delta_high_bias_tail_fraction": ma["high_bias_tail_fraction"] - mc["high_bias_tail_fraction"],
            }
            row.update(run_block_delta_ci(anomaly, control, target_col, f"pred_{method}", rng, reps, high_bias, max_rows))
            delta_rows.append(row)
    deltas = pd.DataFrame(delta_rows)

    by_run_rows = []
    for run, sub in frame.groupby("run", sort=True):
        for method in METHODS:
            row = {"dataset": dataset_name, "run": int(run), "method": method}
            row.update(robust_metrics(sub[target_col].to_numpy(), sub[f"pred_{method}"].to_numpy(), high_bias))
            row["baseline_excursion_n"] = int(sub["label_baseline_excursion"].sum())
            row["novel_early_pretrigger_n"] = int(sub["label_novel_early_pretrigger"].sum())
            by_run_rows.append(row)

    by_match_rows = []
    keys = ["run", "source_stave", "source_amp_bin", "saturation_bin"]
    for key, sub in frame.groupby(keys, sort=True):
        if len(sub) < 5:
            continue
        for method in REAL_METHODS:
            row = {
                "dataset": dataset_name,
                "run": int(key[0]),
                "source_stave": str(key[1]),
                "source_amp_bin": str(key[2]),
                "saturation_bin": int(key[3]),
                "method": method,
                "baseline_excursion_n": int(sub["label_baseline_excursion"].sum()),
                "novel_early_pretrigger_n": int(sub["label_novel_early_pretrigger"].sum()),
            }
            row.update(robust_metrics(sub[target_col].to_numpy(), sub[f"pred_{method}"].to_numpy(), high_bias))
            by_match_rows.append(row)

    return summary, deltas, pd.DataFrame(by_run_rows), pd.DataFrame(by_match_rows)


def reproduce_and_extract(config: dict, labels: pd.DataFrame) -> Tuple[dict, pd.DataFrame, np.ndarray, pd.DataFrame, np.ndarray, dict]:
    p04b_cfg = load_yaml(ROOT / config["p04b_reference_config"])
    p04c_cfg = load_yaml(ROOT / config["p04c_reference_config"])
    p04b_ref = load_json(ROOT / config["p04b_reference_result"])
    p04c_ref = load_json(ROOT / config["p04c_reference_result"])

    print("extracting P04b downstream external rows from raw ROOT ...")
    p04b_frame, p04b_wave, p04b_counts = p04b.extract_external_rows(p04b_cfg)
    p04b_frame = attach_labels_p04b(config, p04b_frame, labels)
    p04b_expected = int(p04b_ref["n_external_rows"])
    if int(len(p04b_frame)) != p04b_expected:
        raise RuntimeError("P04b external row reproduction failed: {} != {}".format(len(p04b_frame), p04b_expected))

    print("reproducing P04c A-stack raw gates from raw ROOT ...")
    astack_counts = p04c.count_astack_gate(p04c_cfg)
    for _, row in astack_counts.iterrows():
        expected = p04c_cfg["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError("P04c A-stack event gate failed for {}".format(row["sample"]))
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError("P04c A-stack pulse gate failed for {}".format(row["sample"]))

    print("extracting P04c A/B event-matched rows from raw ROOT ...")
    p04c_frame, p04c_wave, p04c_counts = p04c.extract_ab_rows(p04c_cfg)
    p04c_frame = attach_labels_p04c(config, p04c_frame, labels)
    p04c_expected = int(p04c_ref["n_ab_rows"])
    if int(len(p04c_frame)) != p04c_expected:
        raise RuntimeError("P04c A/B row reproduction failed: {} != {}".format(len(p04c_frame), p04c_expected))

    repro = {
        "p04b": {
            "expected_external_rows": p04b_expected,
            "reproduced_external_rows": int(len(p04b_frame)),
            "delta": int(len(p04b_frame)) - p04b_expected,
            "pass": int(len(p04b_frame)) == p04b_expected,
            "counts_by_run": json.loads(p04b_counts.to_json(orient="records")),
        },
        "p04c": {
            "b_s00_reproduction_source": "shared P04/P09a raw B-stack S00 reproduction",
            "expected_ab_rows": p04c_expected,
            "reproduced_ab_rows": int(len(p04c_frame)),
            "delta": int(len(p04c_frame)) - p04c_expected,
            "pass": int(len(p04c_frame)) == p04c_expected,
            "astack_analysis_counts": json.loads(astack_counts.to_json(orient="records")),
            "ab_topology_counts_by_run": json.loads(p04c_counts.to_json(orient="records")),
        },
    }
    side_tables = {
        "p04b_counts": p04b_counts,
        "p04c_astack_counts": astack_counts,
        "p04c_ab_counts": p04c_counts,
    }
    return repro, p04b_frame, p04b_wave, p04c_frame, p04c_wave, side_tables


def make_report(
    out_dir: Path,
    config: dict,
    result: dict,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    fold_audit: pd.DataFrame,
) -> None:
    all_rows = summary[summary["stratum"] == "all_rows"].copy()
    all_rows = all_rows[all_rows["method"].isin(REAL_METHODS)]
    compact = all_rows[
        [
            "dataset",
            "method",
            "n",
            "bias_median_frac",
            "bias_ci95",
            "res68_abs_frac",
            "res68_ci95",
            "high_bias_tail_fraction",
            "high_bias_tail_ci95",
            "within_25pct",
        ]
    ].sort_values(["dataset", "res68_abs_frac"])
    delta_compact = deltas[
        [
            "dataset",
            "anomaly_stratum",
            "control_stratum",
            "method",
            "n_anomaly",
            "n_control",
            "delta_bias_median_frac",
            "delta_res68_abs_frac",
            "delta_res68_ci95",
            "delta_high_bias_tail_fraction",
            "delta_high_bias_tail_ci95",
        ]
    ].sort_values(["dataset", "anomaly_stratum", "method"])
    winner = result["winner"]
    leakage = result["leakage_audit"]
    p04 = result["raw_reproduction"]["p04_s00"]
    p04b_repro = result["raw_reproduction"]["p04b"]
    p04c_repro = result["raw_reproduction"]["p04c"]

    lines = [
        "# P04g External Charge-Proxy Validation of P04f Anomaly Bias",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw HRD ROOT files through the repo `data/root/root` symlink; no Monte Carlo.",
        "- **External targets:** P04b downstream `B4+B6+B8` charge and P04c event-matched selected `A1/A3` charge.",
        "- **Anomaly labels:** frozen P09a/P04f `baseline_excursion` and `novel_early_pretrigger` labels on the source B2 pulse.",
        "- **Split:** leave-one-run-out; every prediction for a run is made by a model fit without that run.",
        "",
        "## 1. Raw Reproduction Gates",
        "",
        f"The shared P04/S00 B-stack gate reproduced `{p04['reproduced_selected_pulses']:,}` selected pulses vs expected `{p04['expected_selected_pulses']:,}` (delta `{p04['delta']:+,}`).",
        f"P04b downstream rows reproduced `{p04b_repro['reproduced_external_rows']:,}` vs expected `{p04b_repro['expected_external_rows']:,}` (delta `{p04b_repro['delta']:+,}`).",
        f"P04c A/B rows reproduced `{p04c_repro['reproduced_ab_rows']:,}` vs expected `{p04c_repro['expected_ab_rows']:,}` (delta `{p04c_repro['delta']:+,}`), after reproducing the A-stack analysis gates.",
        "",
        "## 2. Estimands And Metrics",
        "",
        "For target charge $y_i$ and prediction $\\hat y_i$, the residual is",
        "",
        "$$ r_i = \\frac{\\hat y_i-y_i}{\\max(y_i,1)}. $$",
        "",
        "The primary score is $\\operatorname{res68}=Q_{0.68}(|r_i|)$, with median bias, RMS, the fraction $|r_i|>0.25$, and within-10/25% rates as diagnostics. Intervals are percentile bootstrap intervals over run blocks. Matched anomaly deltas use",
        "",
        "$$ \\Delta_m = m(\\mathcal A)-m(\\mathcal C), $$",
        "",
        "where controls $\\mathcal C$ are sampled without replacement within the same run, source stave, B2 amplitude bin, and saturation bin.",
        "",
        "## 3. Methods",
        "",
        "- **traditional_strong:** log-linear hand-engineered charge-transfer model using B2 charge/amplitude terms for P04b and B-stack charge-transfer summaries for P04c.",
        "- **ridge:** standardized Ridge regression on waveform summaries, B2/P04c charge features, P09a continuous anomaly scores, and anomaly flags.",
        "- **gradient_boosted_trees:** histogram gradient-boosted trees on the same engineered feature matrix.",
        "- **mlp:** two-layer standardized MLP on the engineered feature matrix.",
        "- **cnn1d:** compact convolutional network on raw source waveform channels plus engineered metadata.",
        "- **residual_cnn_meta:** new residual architecture that predicts a log-residual correction to the strong traditional model using the same CNN+metadata backbone.",
        "- **shuffled_target_gbt:** leakage sentinel trained on permuted training labels.",
        "",
        "All model features exclude target charge columns, A-stack charge columns for P04c, downstream charge columns for P04b, run id, event id, and held-out run rows.",
        "",
        "## 4. Run-Held-Out Benchmark",
        "",
        compact.to_markdown(index=False),
        "",
        f"The overall winner by mean rank across the two external targets is `{winner['method']}`. Its per-target res68 values are recorded in `result.json`; the single best target-specific result is `{winner['best_target_specific']['dataset']}` / `{winner['best_target_specific']['method']}` at res68 `{winner['best_target_specific']['res68_abs_frac']:.4f}`.",
        "",
        "## 5. Matched Anomaly Deltas",
        "",
        "Positive deltas mean the anomaly stratum has worse residual behavior than matched normal controls.",
        "",
        delta_compact.to_markdown(index=False),
        "",
        "## 6. Run-Level Stability",
        "",
        by_run[
            [
                "dataset",
                "run",
                "method",
                "n",
                "bias_median_frac",
                "res68_abs_frac",
                "high_bias_tail_fraction",
                "baseline_excursion_n",
                "novel_early_pretrigger_n",
            ]
        ]
        .query("method in @REAL_METHODS")
        .to_markdown(index=False),
        "",
        "## 7. Leakage, Systematics, And Caveats",
        "",
        f"- Train/held-out run overlap across all folds: `{leakage['train_heldout_run_overlap_total']}`.",
        f"- P04b shuffled-target GBT all-row res68: `{leakage['p04b_shuffled_res68']:.4f}`.",
        f"- P04c shuffled-target GBT all-row res68: `{leakage['p04c_shuffled_res68']:.4f}`.",
        f"- P04b label-join misses: `{leakage['p04b_label_join_misses']}`; P04c label-join misses: `{leakage['p04c_label_join_misses']}`.",
        "- Bootstrap CIs are run-block intervals, so they capture run-to-run instability but not uncertainty from the deterministic P09a label thresholds.",
        "- The external charge proxies are still same-event detector correlations, not beam truth. P04c is topology-limited by the small event-matched A-stack sample; P04b is restricted to penetrating B2/B4/B6/B8 events.",
        "- The residual CNN may overfit rare strata when an anomaly is nearly confined to one run. The fold audit and shuffled-target sentinel are therefore treated as mandatory controls.",
        "",
        "## 8. Finding",
        "",
        result["finding"],
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config configs/{Path(config['config_path']).name}",
        "```",
        "",
        "Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `external_model_summary.csv`, `external_stratum_deltas.csv`, `external_by_run.csv`, `matched_strata_metrics.csv`, `fold_audit.csv`, `p04b_external_predictions.csv`, `p04c_external_predictions.csv`, and raw gate count CSVs.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def choose_winner(summary: pd.DataFrame) -> dict:
    all_rows = summary[(summary["stratum"] == "all_rows") & (summary["method"].isin(REAL_METHODS))].copy()
    ranks = []
    for dataset, sub in all_rows.groupby("dataset"):
        ordered = sub.sort_values("res68_abs_frac").reset_index(drop=True)
        for rank, (_, row) in enumerate(ordered.iterrows(), start=1):
            ranks.append(
                {
                    "dataset": dataset,
                    "method": row["method"],
                    "rank": rank,
                    "res68_abs_frac": float(row["res68_abs_frac"]),
                    "res68_ci95": row["res68_ci95"],
                }
            )
    rank_df = pd.DataFrame(ranks)
    mean_rank = rank_df.groupby("method", as_index=False)["rank"].mean().sort_values(["rank", "method"])
    method = str(mean_rank.iloc[0]["method"])
    best_specific = all_rows.sort_values("res68_abs_frac").iloc[0]
    return {
        "method": method,
        "criterion": "lowest mean rank by res68_abs_frac across P04b and P04c external targets",
        "mean_rank_table": json.loads(mean_rank.to_json(orient="records")),
        "per_target": json.loads(rank_df[rank_df["method"] == method].to_json(orient="records")),
        "best_target_specific": json_ready(best_specific.to_dict()),
    }


def build_finding(summary: pd.DataFrame, deltas: pd.DataFrame, winner: dict) -> str:
    rows = summary[(summary["stratum"] == "all_rows") & (summary["method"].isin(REAL_METHODS))].copy()
    best = rows.sort_values(["dataset", "res68_abs_frac"]).groupby("dataset").head(1)
    pieces = []
    for _, row in best.iterrows():
        pieces.append(
            "{} is best on {} with res68 {:.4f} [{:.4f}, {:.4f}]".format(
                row["method"],
                row["dataset"],
                row["res68_abs_frac"],
                row["res68_ci95"][0],
                row["res68_ci95"][1],
            )
        )
    delta_pieces = []
    for dataset in sorted(deltas["dataset"].unique()):
        sub = deltas[(deltas["dataset"] == dataset) & (deltas["method"] == winner["method"])]
        for _, row in sub.iterrows():
            delta_pieces.append(
                "{} {} delta res68 {:.4f} [{}, {}]".format(
                    dataset,
                    row["anomaly_stratum"],
                    row["delta_res68_abs_frac"],
                    "NA" if row["delta_res68_ci95"][0] is None else "{:.4f}".format(row["delta_res68_ci95"][0]),
                    "NA" if row["delta_res68_ci95"][1] is None else "{:.4f}".format(row["delta_res68_ci95"][1]),
                )
            )
    return (
        "; ".join(pieces)
        + ". The cross-target winner is {}. Matched anomaly effects for that method: {}. "
        "Thus the P04f anomaly-bias signal is tested outside the duplicate-readout target; any surviving positive deltas are external-proxy effects, while null or unstable deltas bound the same-event electronics interpretation."
    ).format(winner["method"], "; ".join(delta_pieces))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04g_1781033470_1723_1a366adc_external_anomaly_charge_proxy_validation.json")
    args = parser.parse_args()

    t0 = time.time()
    config_path = ROOT / args.config
    config = load_json(config_path)
    config["config_path"] = str(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/7 reconstructing P04/P09a selected-pulse labels from raw ROOT ...")
    labels, p09_counts, repro = load_p09a_labels(config)
    p09_counts.to_csv(out_dir / "p04_s00_counts_by_run.csv", index=False)
    label_counts = (
        labels[labels["stave"] == "B2"]
        .groupby(["run", "stave", "taxon"], as_index=False)
        .size()
        .rename(columns={"size": "n"})
    )
    label_counts.to_csv(out_dir / "b2_anomaly_label_counts.csv", index=False)

    print("2/7 reproducing P04b/P04c external raw gates ...")
    external_repro, p04b_frame, p04b_wave, p04c_frame, p04c_wave, side_tables = reproduce_and_extract(config, labels)
    repro.update(external_repro)
    side_tables["p04b_counts"].to_csv(out_dir / "p04b_counts_by_run.csv", index=False)
    side_tables["p04c_astack_counts"].to_csv(out_dir / "p04c_astack_gate_counts.csv", index=False)
    side_tables["p04c_ab_counts"].to_csv(out_dir / "p04c_ab_topology_counts_by_run.csv", index=False)

    print("3/7 fitting P04b downstream external models ...")
    p04b_pred, p04b_folds = fit_dataset_models(
        config,
        "p04b_downstream",
        p04b_frame,
        p04b_wave,
        "downstream_charge",
        p04b_traditional_features(p04b_frame),
        p04b_ml_features(p04b_frame, p04b_wave),
        p04b_wave[:, None, :].astype(np.float32),
    )

    print("4/7 fitting P04c A/B external models ...")
    p04c_pred, p04c_folds = fit_dataset_models(
        config,
        "p04c_ab_charge",
        p04c_frame,
        p04c_wave,
        "target_a_charge",
        p04c_traditional_features(p04c_frame),
        p04c_ml_features(p04c_frame, p04c_wave),
        p04c_wave.astype(np.float32),
    )

    print("5/7 summarizing run-block CIs and matched anomaly controls ...")
    p04b_summary, p04b_deltas, p04b_by_run, p04b_by_match = summarize_dataset(config, "p04b_downstream", p04b_pred, "downstream_charge")
    p04c_summary, p04c_deltas, p04c_by_run, p04c_by_match = summarize_dataset(config, "p04c_ab_charge", p04c_pred, "target_a_charge")
    summary = pd.concat([p04b_summary, p04c_summary], ignore_index=True)
    deltas = pd.concat([p04b_deltas, p04c_deltas], ignore_index=True)
    by_run = pd.concat([p04b_by_run, p04c_by_run], ignore_index=True)
    by_match = pd.concat([p04b_by_match, p04c_by_match], ignore_index=True)
    fold_audit = pd.concat([p04b_folds, p04c_folds], ignore_index=True)

    summary.to_csv(out_dir / "external_model_summary.csv", index=False)
    deltas.to_csv(out_dir / "external_stratum_deltas.csv", index=False)
    by_run.to_csv(out_dir / "external_by_run.csv", index=False)
    by_match.to_csv(out_dir / "matched_strata_metrics.csv", index=False)
    fold_audit.to_csv(out_dir / "fold_audit.csv", index=False)

    p04b_pred.to_csv(out_dir / "p04b_external_predictions.csv", index=False)
    p04c_pred.to_csv(out_dir / "p04c_external_predictions.csv", index=False)

    print("6/7 writing result.json and report ...")
    winner = choose_winner(summary)
    finding = build_finding(summary, deltas, winner)
    all_rows = summary[summary["stratum"] == "all_rows"].set_index(["dataset", "method"])
    leakage = {
        "train_heldout_run_overlap_total": int(fold_audit["train_heldout_run_overlap"].sum()),
        "p04b_shuffled_res68": float(all_rows.loc[("p04b_downstream", "shuffled_target_gbt"), "res68_abs_frac"]),
        "p04c_shuffled_res68": float(all_rows.loc[("p04c_ab_charge", "shuffled_target_gbt"), "res68_abs_frac"]),
        "p04b_label_join_misses": int(p04b_pred["taxon"].isna().sum()),
        "p04c_label_join_misses": int(p04c_pred["taxon"].isna().sum()),
        "excluded_features": [
            "run id",
            "event ids",
            "P04b downstream target charge and downstream stave charge columns",
            "P04c A-stack target charge and A-stack charge columns",
            "held-out run rows",
        ],
    }
    novel_ticket = {
        "count": 1,
        "ticket": config["novel_ticket"],
    }
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction": repro,
        "datasets": {
            "p04b_downstream": {
                "target": "B4+B6+B8 positive-lobe charge for penetrating B2-selected events",
                "n_rows": int(len(p04b_pred)),
                "runs": sorted(int(r) for r in p04b_pred["run"].unique()),
            },
            "p04c_ab_charge": {
                "target": "selected event-matched A1/A3 positive-lobe charge",
                "n_rows": int(len(p04c_pred)),
                "runs": sorted(int(r) for r in p04c_pred["run"].unique()),
            },
        },
        "run_split": "leave-one-run-out by source run",
        "bootstrap": {
            "unit": "run block",
            "reps": int(config["bootstrap_reps"]),
            "max_rows_per_run": int(config["bootstrap_max_rows_per_run"]),
        },
        "methods": METHODS,
        "winner": winner,
        "primary_metrics": json.loads(summary.to_json(orient="records")),
        "matched_stratum_deltas": json.loads(deltas.to_json(orient="records")),
        "leakage_audit": leakage,
        "next_tickets": [config["novel_ticket"]],
        "novel_ticket_appended": novel_ticket,
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    make_report(out_dir, config, result, summary, deltas, by_run, fold_audit)

    print("7/7 writing manifest and input hashes ...")
    input_rows = [
        {"path": str(config_path), "sha256": sha256_file(config_path)},
        {"path": str(Path(__file__)), "sha256": sha256_file(Path(__file__))},
        {"path": str(ROOT / config["p09a_reference_config"]), "sha256": sha256_file(ROOT / config["p09a_reference_config"])},
        {"path": str(ROOT / config["p04b_reference_config"]), "sha256": sha256_file(ROOT / config["p04b_reference_config"])},
        {"path": str(ROOT / config["p04b_reference_result"]), "sha256": sha256_file(ROOT / config["p04b_reference_result"])},
        {"path": str(ROOT / config["p04c_reference_config"]), "sha256": sha256_file(ROOT / config["p04c_reference_config"])},
        {"path": str(ROOT / config["p04c_reference_result"]), "sha256": sha256_file(ROOT / config["p04c_reference_result"])},
    ]
    p09_cfg = p09a.load_config(ROOT / config["p09a_reference_config"])
    raw_dir = p09a.resolve_raw_root_dir(p09_cfg)
    input_rows.extend({"path": str(raw_dir / "hrdb_run_{:04d}.root".format(run)), "sha256": sha256_file(raw_dir / "hrdb_run_{:04d}.root".format(run))} for run in p09a.configured_runs(p09_cfg))
    p04c_cfg = load_yaml(ROOT / config["p04c_reference_config"])
    for run in p04c_cfg["runs"]:
        path = p04c.raw_path(p04c_cfg, p04c_cfg["astack"]["file_prefix"], int(run))
        if path.exists():
            input_rows.append({"path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).drop_duplicates("path").to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/{Path(__file__).name} --config {args.config}",
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "inputs": json.loads(pd.DataFrame(input_rows).drop_duplicates("path").to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("DONE -> {} in {:.1f} s".format(out_dir, time.time() - t0))


if __name__ == "__main__":
    main()
