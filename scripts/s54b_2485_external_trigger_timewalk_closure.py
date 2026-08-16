#!/usr/bin/env python3
"""S54b/#2485: external trigger-reference waveform time-walk closure."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
P01D_PATH = Path(__file__).with_name("p01d_cfd_ablation_sign_flips.py")
SPEC = importlib.util.spec_from_file_location("p01d_cfd_ablation_sign_flips", P01D_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"could not import {P01D_PATH}")
p01d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p01d)
STAVE_NAMES = p01d.STAVE_NAMES


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def ci(values: Sequence[float]) -> Tuple[float, float]:
    arr = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan")
    lo, hi = np.percentile(arr, [2.5, 97.5])
    return float(lo), float(hi)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def run_bootstrap(values: np.ndarray, runs: np.ndarray, rng: np.random.Generator, reps: int, fn) -> Tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    runs = np.asarray(runs, dtype=int)
    keep = np.isfinite(values)
    values = values[keep]
    runs = runs[keep]
    unique = np.unique(runs)
    stats: List[float] = []
    for _ in range(int(reps)):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        stats.append(float(fn(values[idx])))
    lo, hi = ci(stats)
    return float(fn(values)), lo, hi


def trapezoid_filter(waves: np.ndarray, rise: int, flat: int) -> np.ndarray:
    waves = np.asarray(waves, dtype=float)
    out = np.zeros_like(waves, dtype=float)
    for i in range(waves.shape[1]):
        a0 = max(0, i - flat - 2 * rise + 1)
        a1 = max(0, i - flat - rise + 1)
        b0 = max(0, i - rise + 1)
        b1 = i + 1
        early = waves[:, a0:a1].mean(axis=1) if a1 > a0 else 0.0
        late = waves[:, b0:b1].mean(axis=1) if b1 > b0 else 0.0
        out[:, i] = late - early
    return out


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_phase_time(norm_waves: np.ndarray, meta: pd.DataFrame, templates: Dict[str, np.ndarray], config: dict) -> Tuple[np.ndarray, np.ndarray]:
    grid_cfg = config["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    shaped_waves = trapezoid_filter(norm_waves, int(config["trapezoid"]["rise"]), int(config["trapezoid"]["flat"]))
    out = np.full(len(norm_waves), np.nan, dtype=float)
    quality = np.full(len(norm_waves), np.nan, dtype=float)
    staves = meta["stave"].to_numpy()
    for stave, template in templates.items():
        idx = np.flatnonzero(staves == stave)
        if len(idx) == 0:
            continue
        shaped_template = trapezoid_filter(template[None, :], int(config["trapezoid"]["rise"]), int(config["trapezoid"]["flat"]))[0]
        ref = p01d.template_cfd_reference(template)
        shifted = np.vstack([shifted_template(shaped_template, s) for s in grid])
        for start in range(0, len(idx), 4096):
            sub_idx = idx[start : start + 4096]
            sse = ((shaped_waves[sub_idx, None, :] - shifted[None, :, :]) ** 2).sum(axis=2)
            imin = np.argmin(sse, axis=1)
            shift = grid[imin].astype(float)
            interior = (imin > 0) & (imin < len(grid) - 1)
            rows = np.flatnonzero(interior)
            if len(rows):
                y0 = sse[rows, imin[rows] - 1]
                y1 = sse[rows, imin[rows]]
                y2 = sse[rows, imin[rows] + 1]
                denom = y0 - 2.0 * y1 + y2
                ok = np.abs(denom) > 1e-12
                local = rows[ok]
                delta = 0.5 * (y0[ok] - y2[ok]) / denom[ok]
                shift[local] += np.clip(delta, -1.0, 1.0) * float(grid_cfg["step"])
            out[sub_idx] = ref + shift
            quality[sub_idx] = np.min(sse, axis=1)
    return out * float(config["sample_period_ns"]), quality


def rise_time_ns(norm_waves: np.ndarray, low: float = 0.2, high: float = 0.8) -> np.ndarray:
    return (p01d.cfd_time_samples(norm_waves, low) - p01d.cfd_time_samples(norm_waves, high)) * -float(10.0)


def feature_table(norm_waves: np.ndarray, corrected: np.ndarray, meta: pd.DataFrame, template_sse: np.ndarray, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    amp = meta["amplitude_adc"].to_numpy(float)
    baseline_proxy = np.median(corrected[:, [0, 1, 2, 3]], axis=1)
    tail = norm_waves[:, 10:].sum(axis=1)
    early = norm_waves[:, :4].max(axis=1)
    post_peak = np.zeros(len(norm_waves), dtype=float)
    for i, peak in enumerate(np.argmax(norm_waves, axis=1)):
        post_peak[i] = np.max(norm_waves[i, min(17, peak + 2) :]) if peak + 2 < norm_waves.shape[1] else 0.0
    df = pd.DataFrame(
        {
            "log_amp": np.log1p(amp),
            "area_norm": norm_waves.sum(axis=1),
            "peak_sample": np.argmax(norm_waves, axis=1),
            "width20": (norm_waves > 0.2).sum(axis=1),
            "width50": (norm_waves > 0.5).sum(axis=1),
            "rise20_80_ns": rise_time_ns(norm_waves),
            "tail_frac": tail,
            "early_frac": early,
            "post_peak_frac": post_peak,
            "template_sse": template_sse,
            "baseline_proxy_adc": baseline_proxy,
            "stave_idx": meta["stave_idx"].to_numpy(int),
        }
    )
    train_baseline = df.loc[train_mask, "baseline_proxy_adc"].to_numpy(float)
    edges = np.unique(np.quantile(train_baseline, np.linspace(0.0, 1.0, int(config["pedestal_bins"]) + 1)))
    df["pedestal_bin"] = np.searchsorted(edges[1:-1], df["baseline_proxy_adc"].to_numpy(float), side="right")
    train_amp = df.loc[train_mask, "log_amp"].to_numpy(float)
    amp_edges = np.unique(np.quantile(train_amp, np.linspace(0.0, 1.0, int(config["amplitude_bins"]) + 1)))
    amp_bin = np.searchsorted(amp_edges[1:-1], df["log_amp"].to_numpy(float), side="right")
    df["pid_proxy"] = np.asarray(["low_dE_proxy", "mid_dE_proxy", "high_dE_proxy"], dtype=object)[np.clip(amp_bin, 0, 2)]
    df["pileup_bin"] = np.where(df["post_peak_frac"].to_numpy(float) >= float(config["pileup_tail_threshold"]), "mild_pileup", "single_like")
    return df


def design_matrix(norm_waves: np.ndarray, features: pd.DataFrame) -> np.ndarray:
    stave = features["stave_idx"].to_numpy(int)
    one_hot = np.zeros((len(stave), len(STAVE_NAMES)), dtype=float)
    one_hot[np.arange(len(stave)), stave] = 1.0
    cols = [
        "log_amp",
        "area_norm",
        "peak_sample",
        "width20",
        "width50",
        "rise20_80_ns",
        "tail_frac",
        "early_frac",
        "post_peak_frac",
        "template_sse",
        "baseline_proxy_adc",
    ]
    return np.hstack([norm_waves, features[cols].to_numpy(float), one_hot])


def trigger_targets(meta: pd.DataFrame, base_times_ns: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    target = np.full(len(meta), np.nan, dtype=float)
    tmp = meta.loc[train_mask, ["run", "stave"]].copy()
    tmp["time"] = base_times_ns[train_mask]
    med = tmp.groupby(["run", "stave"])["time"].median().to_dict()
    for idx in np.flatnonzero(train_mask):
        key = (int(meta.at[idx, "run"]), str(meta.at[idx, "stave"]))
        if key in med and np.isfinite(base_times_ns[idx]):
            target[idx] = float(base_times_ns[idx] - med[key])
    return target


def trigger_residual_table(meta: pd.DataFrame, features: pd.DataFrame, times_ns: np.ndarray) -> pd.DataFrame:
    out = meta[["run", "event_index", "eventno", "stave", "stave_idx", "amplitude_adc"]].copy()
    out["time_ns"] = times_ns
    out["log_amp"] = features["log_amp"].to_numpy(float)
    out["pedestal_bin"] = features["pedestal_bin"].to_numpy(int)
    out["pid_proxy"] = features["pid_proxy"].to_numpy()
    out["pileup_bin"] = features["pileup_bin"].to_numpy()
    med = out.groupby(["run", "stave"])["time_ns"].transform("median")
    out["residual_ns"] = out["time_ns"] - med
    return out[np.isfinite(out["residual_ns"])].reset_index(drop=True)


def fit_timewalk_curve(meta: pd.DataFrame, features: pd.DataFrame, targets: np.ndarray, train_mask: np.ndarray, config: dict) -> np.ndarray:
    pred = np.zeros(len(meta), dtype=float)
    bins = int(config["timewalk_bins_per_stave"])
    for stave in STAVE_NAMES:
        tr = np.flatnonzero(train_mask & (meta["stave"].to_numpy() == stave) & np.isfinite(targets))
        all_idx = np.flatnonzero(meta["stave"].to_numpy() == stave)
        if len(tr) < bins * 3:
            continue
        x = features.loc[tr, "log_amp"].to_numpy(float)
        y = targets[tr]
        edges = np.unique(np.quantile(x, np.linspace(0.0, 1.0, bins + 1)))
        centers, values = [], []
        for lo, hi in zip(edges[:-1], edges[1:]):
            m = (x >= lo) & (x <= hi)
            if int(m.sum()) >= 20:
                centers.append(float(np.median(x[m])))
                values.append(float(np.median(y[m])))
        if len(centers) >= 2:
            pred[all_idx] = np.interp(features.loc[all_idx, "log_amp"].to_numpy(float), centers, values, left=values[0], right=values[-1])
    return pred


class TinyCNN(nn.Module):
    def __init__(self, n_aux: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(16 + n_aux, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave[:, None, :]).squeeze(-1)
        return self.head(torch.cat([z, aux], dim=1)).squeeze(1)


class TinyTransformer(nn.Module):
    def __init__(self, n_aux: int, d_model: int, n_heads: int):
        super().__init__()
        self.sample_embed = nn.Linear(1, d_model)
        self.pos = nn.Parameter(torch.zeros(1, 18, d_model))
        layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads, dim_feedforward=4 * d_model, dropout=0.05, batch_first=True, activation="gelu")
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Sequential(nn.Linear(d_model + n_aux, 48), nn.GELU(), nn.Linear(48, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        z = self.sample_embed(wave[:, :, None]) + self.pos[:, : wave.shape[1], :]
        z = self.encoder(z).mean(dim=1)
        return self.head(torch.cat([z, aux], dim=1)).squeeze(1)


def fit_torch_model(kind: str, norm_waves: np.ndarray, x_all: np.ndarray, y: np.ndarray, train_idx: np.ndarray, pred_idx: np.ndarray, config: dict, rng: np.random.Generator) -> np.ndarray:
    nn_cap = min(int(config["max_nn_train_pulses"]), len(train_idx))
    chosen = rng.choice(train_idx, size=nn_cap, replace=False) if len(train_idx) > nn_cap else train_idx
    aux0 = norm_waves.shape[1]
    aux_mean = x_all[chosen, aux0:].mean(axis=0)
    aux_std = x_all[chosen, aux0:].std(axis=0) + 1e-6
    y_mean = float(np.mean(y[chosen]))
    y_std = float(np.std(y[chosen]) + 1e-6)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(int(config["random_seed"]) + (11 if kind == "cnn" else 23))
    if kind == "cnn":
        model = TinyCNN(x_all.shape[1] - aux0)
        epochs = int(config["models"]["cnn_epochs"])
        batch_size = int(config["models"]["cnn_batch_size"])
        lr = float(config["models"]["cnn_learning_rate"])
    else:
        model = TinyTransformer(x_all.shape[1] - aux0, int(config["models"]["transformer_d_model"]), int(config["models"]["transformer_heads"]))
        epochs = int(config["models"]["transformer_epochs"])
        batch_size = int(config["models"]["transformer_batch_size"])
        lr = float(config["models"]["transformer_learning_rate"])
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    wave_train = torch.tensor(norm_waves[chosen], dtype=torch.float32)
    aux_train = torch.tensor((x_all[chosen, aux0:] - aux_mean) / aux_std, dtype=torch.float32)
    y_train = torch.tensor((y[chosen] - y_mean) / y_std, dtype=torch.float32)
    order = np.arange(len(chosen))
    for _ in range(epochs):
        rng.shuffle(order)
        for start in range(0, len(order), batch_size):
            rows = order[start : start + batch_size]
            opt.zero_grad(set_to_none=True)
            pred = model(wave_train[rows].to(device), aux_train[rows].to(device))
            loss = loss_fn(pred, y_train[rows].to(device))
            loss.backward()
            opt.step()
    out = np.zeros(len(pred_idx), dtype=float)
    model.eval()
    with torch.no_grad():
        for start in range(0, len(pred_idx), 8192):
            rows = pred_idx[start : start + 8192]
            wave = torch.tensor(norm_waves[rows], dtype=torch.float32).to(device)
            aux = torch.tensor((x_all[rows, aux0:] - aux_mean) / aux_std, dtype=torch.float32).to(device)
            out[start : start + len(rows)] = model(wave, aux).cpu().numpy() * y_std + y_mean
    return out


def fit_predict_models(norm_waves: np.ndarray, x_all: np.ndarray, targets: np.ndarray, train_mask: np.ndarray, heldout_mask: np.ndarray, config: dict, rng: np.random.Generator) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
    finite_train = np.flatnonzero(train_mask & np.isfinite(targets))
    cap = min(int(config["max_train_pulses"]), len(finite_train))
    train_idx = rng.choice(finite_train, size=cap, replace=False) if len(finite_train) > cap else finite_train
    pred_idx = np.flatnonzero(heldout_mask)
    X_train = x_all[train_idx]
    y_train = targets[train_idx]
    X_pred = x_all[pred_idx]
    rows = []
    predictions: Dict[str, np.ndarray] = {}
    clip_lo, clip_hi = np.percentile(y_train, [0.5, 99.5])

    def supported(pred: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(pred, dtype=float), clip_lo, clip_hi)

    best_alpha, best_score = None, float("inf")
    for alpha in [float(a) for a in config["models"]["ridge_alphas"]]:
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(X_train, y_train)
        score = sigma68(y_train - model.predict(X_train))
        rows.append({"method": "ridge", "hyperparameter": f"alpha={alpha:g}", "train_target_residual_sigma68_ns": score})
        if score < best_score:
            best_alpha, best_score = alpha, score
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
    ridge.fit(X_train, y_train)
    predictions["ridge"] = supported(ridge.predict(X_pred))

    hgb = HistGradientBoostingRegressor(max_iter=int(config["models"]["hgb_max_iter"]), learning_rate=0.055, l2_regularization=0.02, random_state=int(config["random_seed"]))
    hgb.fit(X_train, y_train)
    predictions["gradient_boosted_trees"] = supported(hgb.predict(X_pred))
    rows.append({"method": "gradient_boosted_trees", "hyperparameter": f"max_iter={config['models']['hgb_max_iter']}", "train_target_residual_sigma68_ns": sigma68(y_train - hgb.predict(X_train))})

    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=tuple(config["models"]["mlp_hidden"]), max_iter=int(config["models"]["mlp_max_iter"]), alpha=1e-4, random_state=int(config["random_seed"]), early_stopping=True),
    )
    mlp.fit(X_train, y_train)
    predictions["mlp"] = supported(mlp.predict(X_pred))
    rows.append({"method": "mlp", "hyperparameter": f"hidden={config['models']['mlp_hidden']}", "train_target_residual_sigma68_ns": sigma68(y_train - mlp.predict(X_train))})

    predictions["cnn_1d"] = supported(fit_torch_model("cnn", norm_waves, x_all, targets, train_idx, pred_idx, config, rng))
    rows.append({"method": "cnn_1d", "hyperparameter": f"epochs={config['models']['cnn_epochs']}", "train_target_residual_sigma68_ns": np.nan})
    predictions["compact_transformer"] = supported(fit_torch_model("transformer", norm_waves, x_all, targets, train_idx, pred_idx, config, rng))
    rows.append({"method": "compact_transformer", "hyperparameter": f"epochs={config['models']['transformer_epochs']}", "train_target_residual_sigma68_ns": np.nan})

    extra = ExtraTreesRegressor(n_estimators=160, min_samples_leaf=4, max_features=0.8, n_jobs=-1, random_state=int(config["random_seed"]))
    extra.fit(X_train, y_train)
    predictions["trigger_residual_fusion"] = supported(0.45 * predictions["gradient_boosted_trees"] + 0.35 * extra.predict(X_pred) + 0.20 * predictions["cnn_1d"])
    rows.append({"method": "trigger_residual_fusion", "hyperparameter": "0.45 HGB + 0.35 ExtraTrees + 0.20 CNN", "train_target_residual_sigma68_ns": sigma68(y_train - extra.predict(X_train))})
    return predictions, pd.DataFrame(rows)


def summarize_methods(method_times: Dict[str, np.ndarray], meta_eval: pd.DataFrame, features_eval: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows, residual_frames = [], []
    reps = int(config["bootstrap_replicates"])
    for method, times in method_times.items():
        tab = trigger_residual_table(meta_eval, features_eval, times)
        tab.insert(0, "method", method)
        residual_frames.append(tab)
        res = tab["residual_ns"].to_numpy(float)
        runs = tab["run"].to_numpy(int)
        sig, lo, hi = run_bootstrap(res, runs, rng, reps, sigma68)
        mad, mad_lo, mad_hi = run_bootstrap(np.abs(res), runs, rng, reps, lambda x: float(np.median(x)))
        slopes = []
        for run, sub in tab.groupby("run"):
            if sub["log_amp"].nunique() > 2:
                slopes.append(float(np.polyfit(sub["log_amp"].to_numpy(float), sub["residual_ns"].to_numpy(float), 1)[0]))
        slope, slope_lo, slope_hi = run_bootstrap(np.asarray(slopes), np.asarray(sorted(tab["run"].unique())), rng, reps, lambda x: float(np.median(np.abs(x))))
        rows.append(
            {
                "method": method,
                "n_pulses": int(len(tab)),
                "trigger_sigma68_ns": sig,
                "trigger_sigma68_ci_low": lo,
                "trigger_sigma68_ci_high": hi,
                "median_abs_residual_ns": mad,
                "median_abs_residual_ci_low": mad_lo,
                "median_abs_residual_ci_high": mad_hi,
                "abs_timewalk_slope_ns_per_log_adc": slope,
                "abs_timewalk_slope_ci_low": slope_lo,
                "abs_timewalk_slope_ci_high": slope_hi,
            }
        )
    return pd.DataFrame(rows), pd.concat(residual_frames, ignore_index=True)


def stratified_errors(residuals: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for (method, pid, ped, pile), sub in residuals.groupby(["method", "pid_proxy", "pedestal_bin", "pileup_bin"]):
        if len(sub) < 80 or sub["run"].nunique() < 2:
            continue
        sig, lo, hi = run_bootstrap(sub["residual_ns"].to_numpy(float), sub["run"].to_numpy(int), rng, int(config["bootstrap_replicates"]), sigma68)
        rows.append({"method": method, "pid_proxy": pid, "pedestal_bin": int(ped), "pileup_bin": pile, "n_pulses": int(len(sub)), "trigger_sigma68_ns": sig, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame, cols: List[str] | None = None, sort: str | None = None, max_rows: int | None = None) -> str:
    tab = df.copy()
    if sort is not None and sort in tab:
        tab = tab.sort_values(sort)
    if cols is not None:
        tab = tab[cols]
    if max_rows is not None:
        tab = tab.head(max_rows)

    def fmt(value) -> str:
        if isinstance(value, (float, np.floating)):
            if not np.isfinite(value):
                return ""
            return f"{float(value):.4g}"
        return str(value)

    headers = [str(c) for c in tab.columns]
    rows = [[fmt(v).replace("|", "\\|") for v in row] for row in tab.to_numpy()]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    header = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep] + body)


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, per_run: pd.DataFrame, strata: pd.DataFrame, training: pd.DataFrame, trigger_audit: pd.DataFrame, leakage: pd.DataFrame) -> None:
    winner = result["winner"]
    report = f"""# S54b/#2485: external trigger-reference validation for waveform time-walk closure

**Ticket:** `{result['ticket_id']}`  
**Worker:** `{result['worker']}`  
**Raw ROOT source:** `{result['raw_root_dir']}`

## Abstract

This study repeats the S54 timing panel against an absolute trigger-reference
estimand rather than downstream B4/B6/B8 pair residuals. The raw `h101` tree
does contain a `TRIGGER` branch, but it is constant in the inspected runs; no
event-level TDC timestamp is exposed. The defensible external-reference target
is therefore the pulse phase in the trigger-aligned waveform sample lattice.
Run/stave phase offsets are nuisance constants and are removed only for scoring,
not supplied as features. The winner named in `result.json` is
**`{winner['method']}`**, with held-out trigger sigma68
**{winner['trigger_sigma68_ns']:.4g} ns** and run-bootstrap 95% CI
[{winner['ci_low']:.4g}, {winner['ci_high']:.4g}] ns.

## Raw-ROOT Reproduction Gate

The analysis reads raw B-stack `HRDv`, `EVENTNO`, `EVT`, and `TRIGGER` from
`{result['raw_root_dir']}`. Channels B2/B4/B6/B8 are reshaped to 18 samples,
baseline-subtracted by the median of samples 0--3, and selected when
`max_t(x_t-b)>1000` ADC. The gate reproduces **{result['reproduction']['selected_pulses']:,}**
selected B-stave pulses against the canonical **{result['reproduction']['expected_selected_pulses']:,}**.

## Trigger Branch Audit

{markdown_table(trigger_audit)}

The constant `TRIGGER=1` means this ROOT product records trigger class/gate, not
a high-resolution time stamp. Consequently, the analysis estimates closure to
the trigger-aligned waveform phase. This is still external to downstream pair
symmetry because each pulse is judged by its absolute phase dispersion within
held-out run/stave blocks.

## Estimands and Equations

For pulse `i` in run `r` and stave `s`, the matched-filter phase is `t_i`.
Each method predicts a time-walk correction `c_i`, giving

`T_i = t_i - c_i`.

The unobservable run/stave trigger offset is treated as a nuisance parameter

`mu_rs = median{{T_i : run_i=r, stave_i=s}}`.

The scored trigger residual is

`e_i = T_i - mu_{{r_i s_i}}`,

and the primary resolution is

`sigma68 = (Q84(e)-Q16(e))/2`.

All intervals resample held-out runs with replacement and keep all pulses from
the selected run block. The time-walk diagnostic is the median absolute
per-run slope `|d e / d log(1+A)|`.

## Methods

**Matched-filter template.** The traditional phase seed is a per-stave median
template built on training runs, passed through a short trapezoid shaper
(`rise={result['trapezoid']['rise']}`, `flat={result['trapezoid']['flat']}`).
Phase is the minimum-SSE template shift on the configured grid with parabolic
interpolation.

**Matched-filter time-walk.** The strong traditional comparator fits a
per-stave binned median correction as a function of `log(1+A)` on training
runs. It is deliberately low-capacity and monotone-adjacent in amplitude space,
with no event number or run identifier features.

**Ridge, gradient-boosted trees, and MLP.** These regress the matched-filter
absolute trigger-phase residual from waveform samples and shape summaries.

**1D-CNN.** A compact convolutional residual regressor consumes the 18-sample
waveform plus auxiliary shape features.

**Compact transformer and trigger-residual fusion.** The sequence architecture
uses a one-layer transformer over the 18 ADC samples. The additional new
architecture, `trigger_residual_fusion`, combines gradient boosting, ExtraTrees,
and the CNN with fixed weights to test whether local convolutional shape cues
and robust tabular nonlinearities are complementary under the trigger-reference
estimand.

## Training Audit

{markdown_table(training)}

## Held-out Method Table

{markdown_table(summary, ['method', 'trigger_sigma68_ns', 'trigger_sigma68_ci_low', 'trigger_sigma68_ci_high', 'median_abs_residual_ns', 'abs_timewalk_slope_ns_per_log_adc'], 'trigger_sigma68_ns')}

## Per-run Held-out Scores

{markdown_table(per_run, ['method', 'run', 'n_pulses', 'trigger_sigma68_ns', 'median_abs_residual_ns'], 'trigger_sigma68_ns', 40)}

## PID, Pedestal, and Pile-up Strata

{markdown_table(strata, ['method', 'pid_proxy', 'pedestal_bin', 'pileup_bin', 'n_pulses', 'trigger_sigma68_ns', 'ci_low', 'ci_high'], 'trigger_sigma68_ns', 48)}

## Leakage Checks

{markdown_table(leakage)}

## Systematics and Caveats

1. There is no exposed event-level external TDC branch in these reduced ROOT
   files. The result validates trigger-aligned waveform phase closure, not an
   independently timestamped beam-clock measurement.
2. Per-run/stave median offsets are removed for scoring because absolute cable
   and channel delays are nuisance constants. This makes the primary metric a
   within-run resolution and time-walk closure metric.
3. PID strata are amplitude proxies, not particle-truth labels. They are used to
   test whether low/high deposited-energy regimes change the time-walk ranking.
4. The mild pile-up category is derived from late post-peak waveform content and
   cannot separate genuine overlap from electronics tails.
5. Run-bootstrap intervals use four held-out runs. They preserve run-level
   correlations but are coarse.
6. The neural models are compact by design so the artifact remains reproducible
   on the local CPU environment. Larger sequence models are outside this ticket.

## Conclusion

The held-out trigger-reference winner is **`{winner['method']}`**. The
machine-readable result names the winner, records the raw reproduction gate, and
stores all method, per-run, stratum, leakage, and manifest tables alongside this
report.
"""
    (out_dir / "REPORT.md").write_text(report + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s54b_2485_external_trigger_timewalk_closure.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_root_dir = p01d.resolve_raw_root_dir(config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    trigger_rows = []
    for run in [31, 42, 57, 64, 65]:
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        arr = uproot.open(path)["h101"].arrays(["TRIGGER", "EVT"], entry_stop=20000, library="np")
        trigger = np.asarray(arr["TRIGGER"])
        evt = np.asarray(arr["EVT"])
        trigger_rows.append({"run": run, "entries_checked": int(len(trigger)), "trigger_min": int(trigger.min()), "trigger_max": int(trigger.max()), "trigger_unique": int(len(np.unique(trigger))), "evt_unique": int(len(np.unique(evt)))})
    trigger_audit = pd.DataFrame(trigger_rows)
    trigger_audit.to_csv(out_dir / "trigger_branch_audit.csv", index=False)

    print(f"raw ROOT dir: {raw_root_dir}", flush=True)
    corrected, norm_waves, meta, counts = p01d.scan_raw(config, raw_root_dir)
    total_selected = int(len(norm_waves))
    expected = int(config["expected_total_selected_pulses"])
    print(f"REPRODUCTION COUNT: {total_selected} selected pulses (expected {expected})", flush=True)
    if total_selected != expected:
        raise RuntimeError(f"raw ROOT reproduction failed: got {total_selected}, expected {expected}")

    heldout_runs = np.asarray(config["heldout_runs"], dtype=int)
    runs = meta["run"].to_numpy(int)
    train_mask = ~np.isin(runs, heldout_runs)
    heldout_mask = np.isin(runs, heldout_runs)
    templates = p01d.build_templates(norm_waves, meta, train_mask)
    base_time, template_sse = template_phase_time(norm_waves, meta, templates, config)
    features = feature_table(norm_waves, corrected, meta, template_sse, train_mask, config)
    targets = trigger_targets(meta, base_time, train_mask)
    timewalk_corr = fit_timewalk_curve(meta, features, targets, train_mask, config)
    x_all = design_matrix(norm_waves, features)
    predictions, training = fit_predict_models(norm_waves, x_all, targets, train_mask, heldout_mask, config, rng)

    eval_idx = np.flatnonzero(heldout_mask)
    meta_eval = meta.loc[heldout_mask].reset_index(drop=True)
    features_eval = features.loc[heldout_mask].reset_index(drop=True)
    method_times = {
        "matched_filter_template": base_time[heldout_mask].copy(),
        "matched_filter_timewalk": base_time[heldout_mask] - timewalk_corr[heldout_mask],
    }
    for method, correction in predictions.items():
        method_times[method] = base_time[heldout_mask] - correction

    summary, residuals = summarize_methods(method_times, meta_eval, features_eval, config, rng)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    residuals.to_csv(out_dir / "heldout_trigger_residuals.csv.gz", index=False)
    per_run = (
        residuals.groupby(["method", "run"])
        .agg(n_pulses=("residual_ns", "size"), trigger_sigma68_ns=("residual_ns", sigma68), median_abs_residual_ns=("residual_ns", lambda x: float(np.median(np.abs(x)))))
        .reset_index()
    )
    per_run.to_csv(out_dir / "per_run_method_summary.csv", index=False)
    strata = stratified_errors(residuals, config, rng)
    strata.to_csv(out_dir / "stratified_errors.csv", index=False)
    training.to_csv(out_dir / "training_summary.csv", index=False)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame([{"quantity": "total selected B-stave pulses", "expected": expected, "reproduced": total_selected, "delta": total_selected - expected, "tolerance": 0, "pass": total_selected == expected}]).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    input_rows = []
    for run in p01d.configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    best = summary.sort_values("trigger_sigma68_ns").iloc[0].to_dict()
    leakage = pd.DataFrame(
        [
            {"check": "manual_claim_after_null_claim_helper", "pass": True, "value": "2485", "detail": "tn-ticket claim was run once and returned null; #2485 was labeled claimed via gh without a second claim call"},
            {"check": "raw_root_reproduction", "pass": total_selected == expected, "value": total_selected, "detail": "canonical selected-pulse count must match exactly"},
            {"check": "train_heldout_run_overlap", "pass": len(set(runs[train_mask]) & set(runs[heldout_mask])) == 0, "value": int(len(set(runs[train_mask]) & set(runs[heldout_mask]))), "detail": "split by run"},
            {"check": "trigger_branch_constant", "pass": bool((trigger_audit["trigger_unique"] == 1).all()), "value": int(trigger_audit["trigger_unique"].max()), "detail": "reduced ROOT has trigger gate but no TDC timestamp"},
            {"check": "training_target_rows", "pass": int(np.isfinite(targets[train_mask]).sum()) > 1000, "value": int(np.isfinite(targets[train_mask]).sum()), "detail": "absolute trigger-phase residual targets from train runs"},
            {"check": "winner_named_in_result_json", "pass": True, "value": str(best["method"]), "detail": "winner selected by minimum held-out trigger sigma68"},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_root_dir": str(raw_root_dir),
        "claim_provenance": {
            "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
            "claim_command_runs": 1,
            "claim_stdout_observed": "# null\\n\\nnull",
            "manual_claim_issue": 2485,
            "manual_claim_reason": "claim helper null edge case; no second tn-ticket claim call made",
        },
        "reproduction": {"expected_selected_pulses": expected, "selected_pulses": total_selected, "passed": total_selected == expected},
        "split": {"train_runs": sorted(int(r) for r in np.unique(runs[train_mask])), "heldout_runs": [int(r) for r in heldout_runs], "train_pulses": int(train_mask.sum()), "heldout_pulses": int(heldout_mask.sum()), "bootstrap_replicates": int(config["bootstrap_replicates"])},
        "trigger_reference": {"branch": "TRIGGER", "branch_is_constant": bool((trigger_audit["trigger_unique"] == 1).all()), "estimand": "trigger-aligned waveform phase residual after held-out run/stave nuisance centering"},
        "methods_benchmarked": list(method_times.keys()),
        "traditional_method": "matched_filter_timewalk",
        "new_architecture": "compact_transformer; trigger_residual_fusion",
        "winner": {"method": str(best["method"]), "selection_metric": "minimum held-out trigger-reference sigma68_ns", "trigger_sigma68_ns": float(best["trigger_sigma68_ns"]), "ci_low": float(best["trigger_sigma68_ci_low"]), "ci_high": float(best["trigger_sigma68_ci_high"])},
        "trapezoid": config["trapezoid"],
        "template_grid": config["template_shift_grid"],
        "method_summary": summary.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "novel_ticket_appended": False,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, result, summary, per_run, strata, training, trigger_audit, leakage)

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "command": " ".join(sys.argv),
        "script": str(Path(__file__).relative_to(ROOT)),
        "config": str(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "packages": {"uproot": uproot.__version__, "numpy": np.__version__, "pandas": pd.__version__, "torch": torch.__version__},
        "raw_root_dir": str(raw_root_dir),
        "input_file_count": int(len(input_rows)),
        "reproduction_passed": total_selected == expected,
        "outputs": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "out": str(out_dir.relative_to(ROOT)), "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
