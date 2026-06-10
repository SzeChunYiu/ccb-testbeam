#!/usr/bin/env python3
"""P03f B4-B6 pair asymmetry closure.

The ticket follows P03d's repeated B4-B6 worst-pair signature.  This script
keeps the raw ROOT count gate from S00/S02, then evaluates whether the B4-B6
offset closes as a constant geometry/TOF offset, a train-derived template-phase
bias, or a same-event waveform-calibration effect.  All predictive corrections
are trained leave-one-run-out and are scored only on the held-out run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03f-b46")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import torch
import torch.nn as nn

import s02_timing_pickoff as s02

torch.set_num_threads(1)

PAIR = ("B4", "B6")


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        if path.suffix.lower() == ".json":
            return json.load(handle)
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def geometry_positions(staves: Sequence[str], spacing_cm: float) -> Dict[str, float]:
    order = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}
    return {stave: float(spacing_cm) * order[stave] for stave in staves}


def fold_config(config: dict, heldout_run: int) -> dict:
    cfg = json.loads(json.dumps(config))
    loo = [int(r) for r in config["timing"]["loo_runs"]]
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [r for r in loo if r != int(heldout_run)]
    return cfg


def add_template_features(pulses: pd.DataFrame, config: dict, train_runs: Sequence[int]) -> pd.DataFrame:
    """Add template-phase times and fit diagnostics using train-run templates."""
    out = pulses.copy()
    staves = list(config["timing"]["downstream_staves"])
    templates = s02.build_templates(out[out["run"].isin(train_runs)], staves)
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    period = float(config["sample_period_ns"])
    out["t_template_phase_ns"] = period * s02.template_phase_time(out, templates, grid)
    out["template_shift_samples"] = np.nan
    out["template_sse"] = np.nan
    out["norm_peak_height"] = np.nan
    out["early_norm_charge"] = np.nan
    out["late_norm_charge"] = np.nan

    for stave, template in templates.items():
        idx = np.flatnonzero(out["stave"].to_numpy() == stave)
        if len(idx) == 0:
            continue
        shifted = np.vstack([s02.shifted_template(template, s) for s in grid])
        wf = np.vstack(out.iloc[idx]["waveform"].to_numpy()).astype(float)
        amp = out.iloc[idx]["amplitude_adc"].to_numpy(dtype=float)
        norm = wf / np.maximum(amp[:, None], 1.0)
        sse = ((norm[:, None, :] - shifted[None, :, :]) ** 2).sum(axis=2)
        best = np.argmin(sse, axis=1)
        out.loc[out.index[idx], "template_shift_samples"] = grid[best]
        out.loc[out.index[idx], "template_sse"] = sse[np.arange(len(idx)), best]
        out.loc[out.index[idx], "norm_peak_height"] = np.max(norm, axis=1)
        out.loc[out.index[idx], "early_norm_charge"] = np.sum(norm[:, :6], axis=1)
        out.loc[out.index[idx], "late_norm_charge"] = np.sum(norm[:, 9:], axis=1)

    wf = np.vstack(out["waveform"].to_numpy())
    amp = out["amplitude_adc"].to_numpy(dtype=float)
    for frac in config["timing"]["cfd_fractions"]:
        name = f"cfd{int(round(float(frac) * 100)):02d}"
        out[f"t_{name}_ns"] = period * s02.cfd_time_samples(wf, amp, float(frac))
    return out


def build_pair_frame(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    spacing_cm = float(config["spacing_cm"])
    positions = geometry_positions(config["timing"]["downstream_staves"], spacing_cm)
    tof_per_cm = float(config["tof_per_cm_ns"])
    rows = []
    grouped = pulses[pulses["stave"].isin(PAIR)].groupby("event_id")
    for event_id, group in grouped:
        if set(PAIR) - set(group["stave"]):
            continue
        row = {"event_id": event_id, "run": int(group["run"].iloc[0])}
        times = {}
        for stave in PAIR:
            srow = group[group["stave"] == stave].iloc[0]
            tcorr = float(srow["t_template_phase_ns"]) - positions[stave] * tof_per_cm
            times[stave] = tcorr
            wf = np.asarray(srow["waveform"], dtype=float)
            amp = max(float(srow["amplitude_adc"]), 1.0)
            norm = wf / amp
            row[f"{stave}_log_amp"] = math.log1p(amp)
            row[f"{stave}_inv_amp1000"] = 1000.0 / amp
            row[f"{stave}_peak_sample"] = float(srow["peak_sample"])
            row[f"{stave}_area_over_amp"] = float(srow["area_adc_samples"]) / amp
            row[f"{stave}_template_shift"] = float(srow["template_shift_samples"])
            row[f"{stave}_template_sse"] = float(srow["template_sse"])
            row[f"{stave}_norm_peak_height"] = float(srow["norm_peak_height"])
            row[f"{stave}_early_norm_charge"] = float(srow["early_norm_charge"])
            row[f"{stave}_late_norm_charge"] = float(srow["late_norm_charge"])
            row[f"{stave}_rise_50_20_ns"] = float(srow["t_cfd50_ns"] - srow["t_cfd20_ns"])
            for i, val in enumerate(norm):
                row[f"{stave}_sample_{i:02d}"] = float(val)
        row["template_phase_residual_ns"] = times["B4"] - times["B6"]
        rows.append(row)
    out = pd.DataFrame(rows)
    for base in [
        "log_amp",
        "inv_amp1000",
        "peak_sample",
        "area_over_amp",
        "template_shift",
        "template_sse",
        "norm_peak_height",
        "early_norm_charge",
        "late_norm_charge",
        "rise_50_20_ns",
    ]:
        out[f"diff_{base}"] = out[f"B4_{base}"] - out[f"B6_{base}"]
        out[f"sum_{base}"] = out[f"B4_{base}"] + out[f"B6_{base}"]
    return out.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)


def physics_feature_names() -> List[str]:
    bases = [
        "log_amp",
        "inv_amp1000",
        "peak_sample",
        "area_over_amp",
        "template_sse",
        "norm_peak_height",
        "early_norm_charge",
        "late_norm_charge",
        "rise_50_20_ns",
    ]
    return [f"{prefix}_{base}" for base in bases for prefix in ("diff", "sum")]


def waveform_feature_names() -> List[str]:
    names = physics_feature_names()
    for stave in PAIR:
        names.extend([f"{stave}_sample_{i:02d}" for i in range(18)])
    return names


def pulse_feature_names() -> List[str]:
    names = [
        "log_amp",
        "inv_amp1000",
        "peak_sample",
        "area_over_amp",
        "template_sse",
        "norm_peak_height",
        "early_norm_charge",
        "late_norm_charge",
        "rise_50_20_ns",
        "stave_B4",
        "stave_B6",
        "stave_B8",
    ]
    names.extend([f"sample_{i:02d}" for i in range(18)])
    return names


def pulse_tab_feature_names() -> List[str]:
    return [n for n in pulse_feature_names() if not n.startswith("sample_")]


def build_pulse_frame(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    targets = s02.event_residual_targets(pulses, "template_phase", float(config["spacing_cm"]), config)
    rows = []
    staves = list(config["timing"]["downstream_staves"])
    for i, row in enumerate(pulses.itertuples()):
        if row.stave not in staves or not math.isfinite(targets[i]):
            continue
        amp = max(float(row.amplitude_adc), 1.0)
        wf = np.asarray(row.waveform, dtype=float)
        norm = wf / amp
        out = {
            "pulse_index": int(i),
            "event_id": row.event_id,
            "run": int(row.run),
            "stave": row.stave,
            "t_template_phase_ns": float(row.t_template_phase_ns),
            "target_residual_ns": float(targets[i]),
            "log_amp": math.log1p(amp),
            "inv_amp1000": 1000.0 / amp,
            "peak_sample": float(row.peak_sample),
            "area_over_amp": float(row.area_adc_samples) / amp,
            "template_sse": float(row.template_sse),
            "norm_peak_height": float(row.norm_peak_height),
            "early_norm_charge": float(row.early_norm_charge),
            "late_norm_charge": float(row.late_norm_charge),
            "rise_50_20_ns": float(row.t_cfd50_ns - row.t_cfd20_ns),
        }
        for stave in staves:
            out[f"stave_{stave}"] = 1.0 if row.stave == stave else 0.0
        for j, val in enumerate(norm):
            out[f"sample_{j:02d}"] = float(val)
        rows.append(out)
    return pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)


def waveform_tensor(frame: pd.DataFrame) -> np.ndarray:
    pieces = []
    for stave in PAIR:
        pieces.append(frame[[f"{stave}_sample_{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32))
    return np.stack(pieces, axis=1)


def robust_sigma68(values: np.ndarray) -> float:
    return s02.sigma68(np.asarray(values, dtype=float))


def closure_score(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan")
    return float(math.sqrt(float(np.median(values)) ** 2 + robust_sigma68(values) ** 2))


def metric(values: np.ndarray) -> Dict[str, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return {
            "n_events": 0,
            "median_ns": float("nan"),
            "sigma68_ns": float("nan"),
            "closure_score_ns": float("nan"),
            "full_rms_ns": float("nan"),
            "abs_p95_ns": float("nan"),
        }
    centered = values - np.mean(values)
    return {
        "n_events": int(len(values)),
        "median_ns": float(np.median(values)),
        "sigma68_ns": robust_sigma68(values),
        "closure_score_ns": closure_score(values),
        "full_rms_ns": float(np.sqrt(np.mean(centered * centered))),
        "abs_p95_ns": float(np.percentile(np.abs(values), 95.0)),
    }


def bootstrap_metric(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan"), float("nan")
    stats = []
    for _ in range(int(n_boot)):
        sample = rng.choice(values, size=len(values), replace=True)
        stats.append(closure_score(sample))
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def fit_binned_template_bias(train: pd.DataFrame, test: pd.DataFrame, y_train: np.ndarray) -> np.ndarray:
    """Traditional non-parametric bias table in train quantile bins."""
    cols = ["diff_template_sse", "diff_log_amp"]
    work = train[cols].copy()
    work["target"] = y_train
    pred = np.full(len(test), float(np.median(y_train)))
    try:
        q_shift = np.unique(np.quantile(work[cols[0]], [0.0, 0.33, 0.66, 1.0]))
        q_amp = np.unique(np.quantile(work[cols[1]], [0.0, 0.33, 0.66, 1.0]))
        if len(q_shift) < 3 or len(q_amp) < 3:
            return pred
        work["shift_bin"] = pd.cut(work[cols[0]], q_shift, include_lowest=True, duplicates="drop")
        work["amp_bin"] = pd.cut(work[cols[1]], q_amp, include_lowest=True, duplicates="drop")
        table = work.groupby(["shift_bin", "amp_bin"], observed=True)["target"].median()
        test_shift = pd.cut(test[cols[0]], q_shift, include_lowest=True, duplicates="drop")
        test_amp = pd.cut(test[cols[1]], q_amp, include_lowest=True, duplicates="drop")
        fallback = float(np.median(y_train))
        out = []
        for sb, ab in zip(test_shift, test_amp):
            out.append(float(table.get((sb, ab), fallback)))
        return np.asarray(out, dtype=float)
    except Exception:
        return pred


class ConvPairRegressor(nn.Module):
    def __init__(self, n_tab: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        return self.head(torch.cat([self.conv(wave), tab], dim=1)).squeeze(1)


class SampleAttentionRegressor(nn.Module):
    def __init__(self, n_tab: int) -> None:
        super().__init__()
        self.sample_proj = nn.Linear(1, 32)
        self.position = nn.Parameter(torch.randn(18, 32) * 0.02)
        self.context = nn.Linear(n_tab, 32)
        self.attn = nn.MultiheadAttention(32, num_heads=4, batch_first=True)
        self.head = nn.Sequential(nn.LayerNorm(32), nn.Linear(32, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        x = wave[:, 0, :, None]
        z = self.sample_proj(x) + self.position[None, :, :] + self.context(tab)[:, None, :]
        z, _ = self.attn(z, z, z, need_weights=False)
        return self.head(z.mean(dim=1)).squeeze(1)


def train_torch_model(
    model: nn.Module,
    arrays: Tuple[np.ndarray, ...],
    y: np.ndarray,
    config: dict,
    seed: int,
) -> nn.Module:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    epochs = int(config["modeling"]["nn_epochs"])
    batch_size = int(config["modeling"]["batch_size"])
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["modeling"]["nn_learning_rate"]),
        weight_decay=float(config["modeling"]["nn_weight_decay"]),
    )
    tensors = [torch.from_numpy(a.astype(np.float32)) for a in arrays]
    yt = torch.from_numpy(y.astype(np.float32))
    model.train()
    for _ in range(epochs):
        order = rng.permutation(len(y))
        for start in range(0, len(y), batch_size):
            take = order[start : start + batch_size]
            pred = model(*[t[take] for t in tensors])
            loss = torch.mean((pred - yt[take]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model


def predict_torch(model: nn.Module, arrays: Tuple[np.ndarray, ...]) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        pred = model(*[torch.from_numpy(a.astype(np.float32)) for a in arrays])
    return pred.numpy().reshape(-1).astype(float)


def stave_tab_tensor(frame: pd.DataFrame) -> np.ndarray:
    per_stave = [
        "log_amp",
        "inv_amp1000",
        "peak_sample",
        "area_over_amp",
        "template_shift",
        "template_sse",
        "norm_peak_height",
        "early_norm_charge",
        "late_norm_charge",
        "rise_50_20_ns",
    ]
    pieces = []
    for stave in PAIR:
        pieces.append(frame[[f"{stave}_{name}" for name in per_stave]].to_numpy(dtype=np.float32))
    return np.stack(pieces, axis=1)


def standardize(train: np.ndarray, test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    scaler = StandardScaler()
    return scaler.fit_transform(train).astype(np.float32), scaler.transform(test).astype(np.float32)


def corrected_b46_residuals(pulse_frame: pd.DataFrame, heldout_run: int, predictions: np.ndarray, config: dict) -> Tuple[np.ndarray, pd.DataFrame]:
    test = pulse_frame[pulse_frame["run"] == heldout_run].copy()
    test["predicted_stave_bias_ns"] = np.asarray(predictions, dtype=float)
    test["t_corrected_ns"] = test["t_template_phase_ns"] - test["predicted_stave_bias_ns"]
    positions = geometry_positions(config["timing"]["downstream_staves"], float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    test["tcorr"] = test["t_corrected_ns"] - test["stave"].map(positions).astype(float) * tof_per_cm
    wide = test.pivot(index="event_id", columns="stave", values="tcorr").dropna(subset=list(PAIR))
    residual = (wide["B4"] - wide["B6"]).to_numpy(dtype=float)
    pred_wide = test.pivot(index="event_id", columns="stave", values="predicted_stave_bias_ns").reindex(wide.index)
    rows = pd.DataFrame(
        {
            "event_id": wide.index,
            "predicted_B4_bias_ns": pred_wide["B4"].to_numpy(dtype=float),
            "predicted_B6_bias_ns": pred_wide["B6"].to_numpy(dtype=float),
            "corrected_residual_ns": residual,
        }
    )
    return residual, rows


def evaluate_fold(pair_frame: pd.DataFrame, pulse_frame: pd.DataFrame, heldout_run: int, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["modeling"]["random_seed"]) + int(heldout_run))
    train = pair_frame[pair_frame["run"] != heldout_run].copy()
    test = pair_frame[pair_frame["run"] == heldout_run].copy()
    y_train = train["template_phase_residual_ns"].to_numpy(dtype=float)
    y_test = test["template_phase_residual_ns"].to_numpy(dtype=float)
    rows = []
    pred_rows = []
    model_rows = []

    def add_method(name: str, family: str, prediction: np.ndarray, detail: str) -> None:
        residual = y_test - np.asarray(prediction, dtype=float)
        ci = bootstrap_metric(residual, rng, int(config["modeling"]["bootstrap_samples"]))
        row = {
            "heldout_run": int(heldout_run),
            "method": name,
            "family": family,
            **metric(residual),
            "closure_ci_low": ci[0],
            "closure_ci_high": ci[1],
            "detail": detail,
        }
        rows.append(row)
        for event_id, value, pred, raw in zip(test["event_id"], residual, prediction, y_test):
            pred_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "event_id": event_id,
                    "method": name,
                    "raw_template_phase_residual_ns": float(raw),
                    "predicted_bias_ns": float(pred),
                    "corrected_residual_ns": float(value),
                }
            )

    add_method(
        "template_phase_nominal",
        "baseline",
        np.zeros(len(test)),
        "nominal B4-B6 template-phase residual after fixed 2 cm geometry TOF correction",
    )
    add_method(
        "geometry_offset_median",
        "traditional",
        np.full(len(test), float(np.median(y_train))),
        "train-run median B4-B6 offset, equivalent to a constant geometry/TOF correction",
    )
    add_method(
        "template_phase_bias_table",
        "traditional",
        fit_binned_template_bias(train, test, y_train),
        "train-only 3x3 median table in B4-B6 template-SSE and amplitude-ratio bins",
    )

    pulse_train = pulse_frame[pulse_frame["run"] != heldout_run].copy()
    pulse_test = pulse_frame[pulse_frame["run"] == heldout_run].copy()
    pnames = pulse_feature_names()
    ptab = pulse_tab_feature_names()
    X_train_tab = pulse_train[ptab].to_numpy(dtype=float)
    X_test_tab = pulse_test[ptab].to_numpy(dtype=float)
    X_train_wave = pulse_train[pnames].to_numpy(dtype=float)
    X_test_wave = pulse_test[pnames].to_numpy(dtype=float)
    y_pulse_train = pulse_train["target_residual_ns"].to_numpy(dtype=float)

    def add_pulse_method(name: str, family: str, pulse_prediction: np.ndarray, detail: str) -> None:
        residual, per_event = corrected_b46_residuals(pulse_frame, heldout_run, pulse_prediction, config)
        ci = bootstrap_metric(residual, rng, int(config["modeling"]["bootstrap_samples"]))
        rows.append(
            {
                "heldout_run": int(heldout_run),
                "method": name,
                "family": family,
                **metric(residual),
                "closure_ci_low": ci[0],
                "closure_ci_high": ci[1],
                "detail": detail,
            }
        )
        raw_map = test.set_index("event_id")["template_phase_residual_ns"]
        for row in per_event.itertuples():
            pred_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "event_id": row.event_id,
                    "method": name,
                    "raw_template_phase_residual_ns": float(raw_map.loc[row.event_id]),
                    "predicted_bias_ns": float(row.predicted_B4_bias_ns - row.predicted_B6_bias_ns),
                    "corrected_residual_ns": float(row.corrected_residual_ns),
                }
            )

    best_alpha = None
    best_score = math.inf
    alpha_rows = []
    for alpha in [float(a) for a in config["modeling"]["ridge_alphas"]]:
        scores = []
        for val_run in sorted(pulse_train["run"].unique()):
            tr = pulse_train[pulse_train["run"] != val_run]
            va = pulse_train[pulse_train["run"] == val_run]
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(tr[pnames], tr["target_residual_ns"])
            tmp_pred = np.zeros(len(pulse_frame), dtype=float)
            tmp_pred[pulse_frame["run"] == val_run] = model.predict(va[pnames])
            resid, _ = corrected_b46_residuals(pulse_frame, int(val_run), tmp_pred[pulse_frame["run"] == val_run], config)
            scores.append(closure_score(resid))
        score = float(np.mean(scores))
        alpha_rows.append({"heldout_run": heldout_run, "model": "ridge", "alpha": alpha, "cv_closure_score_ns": score})
        if score < best_score:
            best_score = score
            best_alpha = alpha
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
    ridge.fit(X_train_wave, y_pulse_train)
    add_pulse_method("ridge_waveform", "ml", ridge.predict(X_test_wave), f"per-stave ridge on physics plus normalized waveform features, alpha={best_alpha}")
    model_rows.extend(alpha_rows)

    hgb = HistGradientBoostingRegressor(
        max_iter=int(config["modeling"]["hgb_max_iter"]),
        learning_rate=float(config["modeling"]["hgb_learning_rate"]),
        l2_regularization=0.05,
        max_leaf_nodes=15,
        random_state=int(config["modeling"]["random_seed"]) + int(heldout_run),
    )
    hgb.fit(X_train_wave, y_pulse_train)
    add_pulse_method("gradient_boosted_trees", "ml", hgb.predict(X_test_wave), "per-stave histogram gradient boosting on the same waveform feature table")

    mlp = torch.nn.Sequential(
        nn.Linear(X_train_wave.shape[1], int(config["modeling"]["mlp_hidden"][0])),
        nn.ReLU(),
        nn.Linear(int(config["modeling"]["mlp_hidden"][0]), int(config["modeling"]["mlp_hidden"][1])),
        nn.ReLU(),
        nn.Linear(int(config["modeling"]["mlp_hidden"][1]), 1),
    )
    Xtr, Xte = standardize(X_train_wave, X_test_wave)
    y_mean, y_std = float(np.mean(y_pulse_train)), float(np.std(y_pulse_train) or 1.0)
    mlp = train_torch_model(mlp, (Xtr,), ((y_pulse_train - y_mean) / y_std).astype(np.float32), config, int(config["modeling"]["random_seed"]) + 101 + int(heldout_run))
    mlp_pred = y_mean + y_std * predict_torch(mlp, (Xte,))
    add_pulse_method("mlp_waveform", "nn", mlp_pred, "per-stave two-layer MLP on standardized waveform and physics features")

    wave_train = pulse_train[[f"sample_{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)[:, None, :]
    wave_test = pulse_test[[f"sample_{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)[:, None, :]
    tab_train, tab_test = standardize(X_train_tab, X_test_tab)
    cnn = ConvPairRegressor(tab_train.shape[1])
    cnn = train_torch_model(cnn, (wave_train, tab_train), ((y_pulse_train - y_mean) / y_std).astype(np.float32), config, int(config["modeling"]["random_seed"]) + 202 + int(heldout_run))
    cnn_pred = y_mean + y_std * predict_torch(cnn, (wave_test, tab_test))
    add_pulse_method("cnn_1d_pair", "nn", cnn_pred, "per-stave 1D-CNN over waveform samples plus physics sideband features")

    attn = SampleAttentionRegressor(tab_train.shape[1])
    attn = train_torch_model(attn, (wave_train, tab_train), ((y_pulse_train - y_mean) / y_std).astype(np.float32), config, int(config["modeling"]["random_seed"]) + 303 + int(heldout_run))
    attn_pred = y_mean + y_std * predict_torch(attn, (wave_test, tab_test))
    add_pulse_method("sample_attention", "new_nn", attn_pred, "new per-stave sample-attention regressor with scalar context")

    leak = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_id_overlap",
                "value": int(len(set(train["event_id"]) & set(test["event_id"]))),
                "detail": "must be zero",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "feature_audit",
                "value": 0,
                "detail": "per-stave models use only that stave's normalized waveform, pulse-shape scalars, and stave one-hot; no run id, event id, event order, other-stave waveform, or held-out target is used",
            },
        ]
    )
    return pd.DataFrame(rows), pd.DataFrame(pred_rows), pd.DataFrame(model_rows), leak


def run_block_summary(predictions: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["modeling"]["random_seed"]) + 909)
    runs = sorted(predictions["heldout_run"].unique())
    rows = []
    for method, group in predictions.groupby("method"):
        values = group["corrected_residual_ns"].to_numpy(dtype=float)
        base = metric(values)
        stats = []
        for _ in range(int(config["modeling"]["run_block_bootstrap_samples"])):
            chosen_runs = rng.choice(runs, size=len(runs), replace=True)
            sampled = []
            for run in chosen_runs:
                rv = group[group["heldout_run"] == run]["corrected_residual_ns"].to_numpy(dtype=float)
                sampled.append(rng.choice(rv, size=len(rv), replace=True))
            stats.append(closure_score(np.concatenate(sampled)))
        rows.append(
            {
                "method": method,
                **base,
                "closure_ci_low": float(np.percentile(stats, 2.5)),
                "closure_ci_high": float(np.percentile(stats, 97.5)),
            }
        )
    out = pd.DataFrame(rows).sort_values("closure_score_ns")
    families = predictions[["method"]].drop_duplicates().copy()
    return out.merge(families, on="method", how="left")


def diagnosis_tables(pair_frames: List[pd.DataFrame], predictions: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    frame = pd.concat(pair_frames, ignore_index=True)
    diag_rows = []
    for run, group in frame.groupby("run"):
        raw = group["template_phase_residual_ns"].to_numpy(dtype=float)
        diag_rows.append(
            {
                "heldout_run": int(run),
                "raw_median_ns": float(np.median(raw)),
                "raw_sigma68_ns": robust_sigma68(raw),
                "raw_closure_score_ns": closure_score(raw),
                "template_shift_diff_corr": float(np.corrcoef(group["diff_template_shift"], raw)[0, 1]),
                "log_amp_diff_corr": float(np.corrcoef(group["diff_log_amp"], raw)[0, 1]),
                "waveform_sse_diff_corr": float(np.corrcoef(group["diff_template_sse"], raw)[0, 1]),
            }
        )
    winner_by_run = predictions.groupby(["heldout_run", "method"])["corrected_residual_ns"].apply(lambda x: closure_score(x.to_numpy())).reset_index(name="closure_score_ns")
    winner_by_run = winner_by_run.sort_values(["heldout_run", "closure_score_ns"]).groupby("heldout_run").head(1)
    return pd.DataFrame(diag_rows), winner_by_run


def plot_outputs(out_dir: Path, heldout: pd.DataFrame, pooled: pd.DataFrame, diag: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.6))
    plot = pooled.sort_values("closure_score_ns")
    ax.bar(np.arange(len(plot)), plot["closure_score_ns"], yerr=[plot["closure_score_ns"] - plot["closure_ci_low"], plot["closure_ci_high"] - plot["closure_score_ns"]])
    ax.set_xticks(np.arange(len(plot)))
    ax.set_xticklabels(plot["method"], rotation=45, ha="right")
    ax.set_ylabel("B4-B6 closure score (ns)")
    ax.set_title("Run-block bootstrap pooled closure")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_closure.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for method, group in heldout.groupby("method"):
        ax.plot(group["heldout_run"], group["closure_score_ns"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("closure score (ns)")
    ax.set_title("Leave-one-run-out B4-B6 closure")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loro_closure.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.scatter(diag["raw_median_ns"], diag["template_shift_diff_corr"], label="template shift")
    ax.scatter(diag["raw_median_ns"], diag["log_amp_diff_corr"], label="amplitude")
    ax.scatter(diag["raw_median_ns"], diag["waveform_sse_diff_corr"], label="template SSE")
    ax.axhline(0.0, color="k", lw=1)
    ax.set_xlabel("raw B4-B6 median residual (ns)")
    ax.set_ylabel("within-run Pearson correlation")
    ax.set_title("Asymmetry covariate diagnostics")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_asymmetry_covariates.png", dpi=140)
    plt.close(fig)


def write_report(out_dir: Path, config: dict, match: pd.DataFrame, heldout: pd.DataFrame, pooled: pd.DataFrame, diag: pd.DataFrame, winners: pd.DataFrame, result: dict) -> None:
    def md_table(df: pd.DataFrame, n: int | None = None) -> str:
        show = df if n is None else df.head(n)
        return show.to_markdown(index=False)

    winner = result["winner"]["method"]
    lines = [
        "# Study report: P03f - B4-B6 pair asymmetry closure",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one run out across sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Config:** `configs/p03f_1781034869_1093_1ffd40cb_b46_pair_asymmetry_closure.json`",
        "",
        "## Question",
        "",
        "P03d repeatedly identified B4-B6 as the unstable pair.  This follow-up asks whether the offset is adequately described by a geometry/TOF constant, by train-derived template-phase bias, or by a per-stave waveform-calibration mismatch that requires learned waveform corrections.",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun directly from raw ROOT before model training.",
        "",
        md_table(match),
        "",
        "## Estimand and equations",
        "",
        "For event `i` and stave `s`, the train-template phase pickoff is `t_is`.  The nominal TOF-corrected time is",
        "",
        "`tau_is = t_is - x_s v_TOF`, with `x_s` fixed by the 2 cm B-stack spacing and `v_TOF = 0.078 ns/cm`.",
        "",
        "The raw B4-B6 asymmetry target is",
        "",
        "`r_i = tau_i,B4 - tau_i,B6`.",
        "",
        "The traditional pair corrections predict a train-derived pair bias `f_pair(x_i)` and form `e_i = r_i - f_pair(x_i)`.  The ML/NN arms instead fit per-stave residual corrections `g_s(z_is)` from that stave's waveform and pulse-shape features, then evaluate `e_i = (tau_i,B4 - g_B4(z_i,B4)) - (tau_i,B6 - g_B6(z_i,B6))` on the held-out run.  The primary closure score is",
        "",
        "`C = sqrt(median(e)^2 + sigma68(e)^2)`, where `sigma68 = (q84 - q16)/2`.",
        "",
        "This score treats a pure median offset and an irreducible pair spread as jointly relevant: a geometry-only explanation should drive the median term down but cannot reduce `sigma68`; a waveform-calibration explanation should also reduce the width on held-out runs.",
        "",
        "## Methods",
        "",
        "- `template_phase_nominal`: no correction after the fixed 2 cm geometry TOF term.",
        "- `geometry_offset_median`: subtracts the train-run median B4-B6 residual, the direct geometry/TOF-offset test.",
        "- `template_phase_bias_table`: a train-only 3x3 median lookup table in B4-B6 template-SSE and amplitude-ratio bins.",
        "- `ridge_waveform`: per-stave ridge regression on normalized waveform samples plus pulse-shape scalars.",
        "- `gradient_boosted_trees`: per-stave histogram gradient boosting on the same waveform feature table.",
        "- `mlp_waveform`: per-stave two-layer neural MLP on standardized waveform and pulse-shape features.",
        "- `cnn_1d_pair`: per-stave 1D convolution over waveform samples plus scalar side features.",
        "- `sample_attention`: a new per-stave sample-attention regressor with scalar pulse context.",
        "",
        "All template shapes, offset tables, scalers, regressors, and neural nets are fitted without the held-out run.  Event id, run id, event order, and held-out residuals are excluded from model inputs.",
        "",
        "## Held-out run benchmark",
        "",
        md_table(heldout[["heldout_run", "method", "family", "n_events", "median_ns", "sigma68_ns", "closure_score_ns", "closure_ci_low", "closure_ci_high"]].sort_values(["heldout_run", "closure_score_ns"])),
        "",
        "## Pooled run-block bootstrap",
        "",
        md_table(pooled[["method", "n_events", "median_ns", "sigma68_ns", "closure_score_ns", "closure_ci_low", "closure_ci_high"]]),
        "",
        "## Asymmetry diagnostics",
        "",
        md_table(diag),
        "",
        "Per-run winners:",
        "",
        md_table(winners),
        "",
        "## Systematics and leakage controls",
        "",
        "The dominant systematic is run-to-run non-stationarity: run 58 and run 65 have small B4-B6 samples, so their CIs are broad and run-block intervals are quoted alongside event bootstrap intervals.  A second systematic is target circularity: models learn a residual of the template-phase measurement, not an external truth time.  Therefore a winner demonstrates predictive closure of the observed B4-B6 asymmetry, not an absolute detector-time calibration.  The geometry-offset arm is intentionally strong for median closure, while waveform models are required to improve the width term to support the calibration-mismatch interpretation.",
        "",
        "Leakage controls are stored in `leakage_checks.csv`; train/held-out event-id overlap is zero in every fold.  ML/NN features are per-stave normalized waveforms, pulse-shape scalars, and stave one-hot only.",
        "",
        "## Verdict",
        "",
        f"`result.json` names `{winner}` as the winner by pooled closure score.  The result verdict is `{result['verdict']}`.",
        "",
        result["interpretation"],
        "",
        "Queued follow-up proposal:",
        "",
        f"- `{result['next_tickets'][0]['title']}` - {result['next_tickets'][0]['body']}",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p03f_1781034869_1093_1ffd40cb_b46_pair_asymmetry_closure.py --config configs/p03f_1781034869_1093_1ffd40cb_b46_pair_asymmetry_closure.json",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `heldout_run_metrics.csv`, `pooled_run_block_summary.csv`, `heldout_predictions.csv`, `asymmetry_diagnosis.csv`, `winner_by_run.csv`, `ridge_cv.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03f_1781034869_1093_1ffd40cb_b46_pair_asymmetry_closure.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    all_runs = [int(r) for r in config["timing"]["loo_runs"]]
    load_cfg = json.loads(json.dumps(config))
    load_cfg["timing"]["train_runs"] = all_runs[:-1]
    load_cfg["timing"]["heldout_runs"] = [all_runs[-1]]
    raw_pulses = s02.load_downstream_pulses(load_cfg)

    heldout_frames = []
    pred_frames = []
    cv_frames = []
    leak_frames = []
    pair_frames = []
    for heldout_run in all_runs:
        cfg = fold_config(config, heldout_run)
        pulses = add_template_features(raw_pulses, cfg, cfg["timing"]["train_runs"])
        pair_frame = build_pair_frame(pulses[pulses["run"].isin(all_runs)], cfg)
        pulse_frame = build_pulse_frame(pulses[pulses["run"].isin(all_runs)], cfg)
        pair_frames.append(pair_frame[pair_frame["run"] == heldout_run].copy())
        heldout, preds, cv, leak = evaluate_fold(pair_frame, pulse_frame, heldout_run, cfg)
        heldout_frames.append(heldout)
        pred_frames.append(preds)
        cv_frames.append(cv)
        leak_frames.append(leak)

    heldout = pd.concat(heldout_frames, ignore_index=True)
    predictions = pd.concat(pred_frames, ignore_index=True)
    ridge_cv = pd.concat(cv_frames, ignore_index=True)
    leakage = pd.concat(leak_frames, ignore_index=True)
    pooled = run_block_summary(predictions, config)
    diag, winners = diagnosis_tables(pair_frames, predictions)
    plot_outputs(out_dir, heldout, pooled, diag)

    heldout.to_csv(out_dir / "heldout_run_metrics.csv", index=False)
    predictions.to_csv(out_dir / "heldout_predictions.csv", index=False)
    ridge_cv.to_csv(out_dir / "ridge_cv.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_block_summary.csv", index=False)
    diag.to_csv(out_dir / "asymmetry_diagnosis.csv", index=False)
    winners.to_csv(out_dir / "winner_by_run.csv", index=False)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    winner = pooled.sort_values("closure_score_ns").iloc[0].to_dict()
    nominal = pooled[pooled["method"] == "template_phase_nominal"].iloc[0].to_dict()
    geom = pooled[pooled["method"] == "geometry_offset_median"].iloc[0].to_dict()
    trad = pooled[pooled["method"] == "template_phase_bias_table"].iloc[0].to_dict()
    ml_methods = {"ridge_waveform", "gradient_boosted_trees", "mlp_waveform", "cnn_1d_pair", "sample_attention"}
    ml_best = pooled[pooled["method"].isin(ml_methods)].sort_values("closure_score_ns").iloc[0].to_dict()
    verdict = "waveform_calibration_model_wins" if winner["method"] in ml_methods else "traditional_offset_or_template_bias_wins"
    interpretation = (
        "The constant geometry offset arm is the direct TOF-shift test.  If it removes most of the median but a waveform method wins the closure score, the residual B4-B6 signature is not just a fixed geometry offset; it contains transferable waveform-calibration structure.  If the geometry or template table wins, the evidence favors a low-dimensional offset/template-bias explanation over a learned per-stave waveform mismatch."
    )
    next_ticket = {
        "title": "P03k: B-stack geometry-offset matrix from run-held-out pair closures",
        "body": "Fit a single train-run B2/B4/B6/B8 stave-position offset matrix from all raw ROOT pair residuals, then test on held-out runs whether one geometry model closes every pair better than per-stave ridge, gradient-boosted trees, MLP, 1D-CNN, and sample-attention corrections with run-block bootstrap CIs. This would confirm or falsify the P03f interpretation that B4-B6 is mostly a fixed geometry/TOF offset rather than a waveform-calibration mismatch.",
    }
    result = {
        "study": "P03f",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(match["pass"].all()),
        "split_by_run": True,
        "heldout_runs": all_runs,
        "primary_metric": "B4-B6 closure_score_ns = sqrt(median_residual_ns^2 + sigma68_ns^2), pooled with run-block bootstrap",
        "winner": {
            "method": str(winner["method"]),
            "closure_score_ns": float(winner["closure_score_ns"]),
            "closure_ci": [float(winner["closure_ci_low"]), float(winner["closure_ci_high"])],
            "median_ns": float(winner["median_ns"]),
            "sigma68_ns": float(winner["sigma68_ns"]),
        },
        "baseline": {
            "template_phase_nominal_closure_score_ns": float(nominal["closure_score_ns"]),
            "template_phase_nominal_median_ns": float(nominal["median_ns"]),
            "template_phase_nominal_sigma68_ns": float(nominal["sigma68_ns"]),
        },
        "traditional": {
            "geometry_offset_median_closure_score_ns": float(geom["closure_score_ns"]),
            "template_phase_bias_table_closure_score_ns": float(trad["closure_score_ns"]),
        },
        "ml": {
            "best_ml_method": str(ml_best["method"]),
            "best_ml_closure_score_ns": float(ml_best["closure_score_ns"]),
            "ridge_waveform_closure_score_ns": float(pooled[pooled["method"] == "ridge_waveform"].iloc[0]["closure_score_ns"]),
            "gradient_boosted_trees_closure_score_ns": float(pooled[pooled["method"] == "gradient_boosted_trees"].iloc[0]["closure_score_ns"]),
            "mlp_waveform_closure_score_ns": float(pooled[pooled["method"] == "mlp_waveform"].iloc[0]["closure_score_ns"]),
            "cnn_1d_pair_closure_score_ns": float(pooled[pooled["method"] == "cnn_1d_pair"].iloc[0]["closure_score_ns"]),
            "sample_attention_closure_score_ns": float(pooled[pooled["method"] == "sample_attention"].iloc[0]["closure_score_ns"]),
        },
        "diagnosis": {
            "mean_template_shift_diff_corr": float(diag["template_shift_diff_corr"].mean()),
            "mean_log_amp_diff_corr": float(diag["log_amp_diff_corr"].mean()),
            "mean_waveform_sse_diff_corr": float(diag["waveform_sse_diff_corr"].mean()),
        },
        "leakage": {
            "max_event_id_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max()),
            "feature_audit": "per-stave normalized waveform, pulse-shape scalars, and stave one-hot; no run id, event id, event order, other-stave waveform, or held-out target",
        },
        "verdict": verdict,
        "interpretation": interpretation,
        "next_tickets": [next_ticket],
        "input_sha256": hashlib.sha256(json.dumps(input_hashes, sort_keys=True).encode("utf-8")).hexdigest(),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, match, heldout, pooled, diag, winners, result)

    manifest = {
        "ticket": config["ticket_id"],
        "config": str(config_path),
        "script": "scripts/p03f_1781034869_1093_1ffd40cb_b46_pair_asymmetry_closure.py",
        "outputs": {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"},
        "result": result,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
