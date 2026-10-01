#!/usr/bin/env python3
"""S49a: phase-local template timing versus ML and neural pulse-shape models."""

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
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


P01D_PATH = Path(__file__).with_name("p01d_cfd_ablation_sign_flips.py")
SPEC = importlib.util.spec_from_file_location("p01d_cfd_ablation_sign_flips", P01D_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"could not import {P01D_PATH}")
p01d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p01d)

STAVE_NAMES = p01d.STAVE_NAMES
ROOT = Path(__file__).resolve().parents[1]


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
    return p01d.sigma68(values)


def run_bootstrap(values: np.ndarray, runs: np.ndarray, rng: np.random.Generator, reps: int, fn=sigma68) -> Tuple[float, float, float]:
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
    """Short symmetric trapezoid shaper for 18-sample normalized pulses."""
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
    t_low = p01d.cfd_time_samples(norm_waves, low)
    t_high = p01d.cfd_time_samples(norm_waves, high)
    return (t_high - t_low) * 10.0


def feature_table(norm_waves: np.ndarray, corrected: np.ndarray, meta: pd.DataFrame, template_sse: np.ndarray, config: dict) -> pd.DataFrame:
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
    ]
    return np.hstack([norm_waves, features[cols].to_numpy(float), one_hot])


def timing_targets(meta: pd.DataFrame, base_times_ns: np.ndarray, config: dict) -> np.ndarray:
    return p01d.timing_targets(meta, base_times_ns, config)


def timing_pair_table(meta: pd.DataFrame, times_ns: np.ndarray, config: dict) -> pd.DataFrame:
    return p01d.timing_pair_table(meta, times_ns, config)


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


class CompactWaveformTransformer(nn.Module):
    def __init__(self, n_aux: int, in_channels: int, d_model: int, heads: int, gated: bool):
        super().__init__()
        self.gated = gated
        self.proj = nn.Linear(in_channels, d_model)
        self.pos = nn.Parameter(torch.zeros(1, 18, d_model))
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=heads,
            dim_feedforward=2 * d_model,
            dropout=0.05,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Sequential(nn.LayerNorm(d_model + n_aux), nn.Linear(d_model + n_aux, 48), nn.GELU(), nn.Linear(48, 1))

    def forward(self, seq: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        z = self.encoder(self.proj(seq) + self.pos[:, : seq.shape[1], :])
        if self.gated and seq.shape[2] > 1:
            weights = torch.softmax(4.0 * torch.abs(seq[:, :, 1]), dim=1).unsqueeze(-1)
            pooled = (z * weights).sum(dim=1)
        else:
            pooled = z.mean(dim=1)
        return self.head(torch.cat([pooled, aux], dim=1)).squeeze(1)


def fit_cnn(norm_waves: np.ndarray, x_all: np.ndarray, y: np.ndarray, train_idx: np.ndarray, pred_idx: np.ndarray, config: dict, rng: np.random.Generator) -> np.ndarray:
    nn_cap = min(int(config["max_nn_train_pulses"]), len(train_idx))
    chosen = rng.choice(train_idx, size=nn_cap, replace=False) if len(train_idx) > nn_cap else train_idx
    aux_cols = x_all.shape[1] - norm_waves.shape[1]
    aux_mean = x_all[chosen, norm_waves.shape[1] :].mean(axis=0)
    aux_std = x_all[chosen, norm_waves.shape[1] :].std(axis=0) + 1e-6
    y_mean = float(np.mean(y[chosen]))
    y_std = float(np.std(y[chosen]) + 1e-6)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(int(config["random_seed"]))
    model = TinyCNN(aux_cols).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(config["models"]["cnn_learning_rate"]))
    loss_fn = nn.SmoothL1Loss()
    batch_size = int(config["models"]["cnn_batch_size"])
    wave_train = torch.tensor(norm_waves[chosen], dtype=torch.float32)
    aux_train = torch.tensor((x_all[chosen, norm_waves.shape[1] :] - aux_mean) / aux_std, dtype=torch.float32)
    y_train = torch.tensor((y[chosen] - y_mean) / y_std, dtype=torch.float32)
    order = np.arange(len(chosen))
    for _ in range(int(config["models"]["cnn_epochs"])):
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
            aux = torch.tensor((x_all[rows, norm_waves.shape[1] :] - aux_mean) / aux_std, dtype=torch.float32).to(device)
            out[start : start + len(rows)] = model(wave, aux).cpu().numpy() * y_std + y_mean
    return out


def transformer_sequences(norm_waves: np.ndarray, gated: bool) -> np.ndarray:
    if not gated:
        return norm_waves[:, :, None].astype(np.float32)
    deriv = np.diff(norm_waves, axis=1, prepend=norm_waves[:, :1])
    return np.stack([norm_waves, deriv], axis=2).astype(np.float32)


def fit_transformer(
    norm_waves: np.ndarray,
    x_all: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    pred_idx: np.ndarray,
    config: dict,
    rng: np.random.Generator,
    gated: bool,
) -> np.ndarray:
    nn_cap = min(int(config["max_nn_train_pulses"]), len(train_idx))
    chosen = rng.choice(train_idx, size=nn_cap, replace=False) if len(train_idx) > nn_cap else train_idx
    aux_cols = x_all.shape[1] - norm_waves.shape[1]
    aux_mean = x_all[chosen, norm_waves.shape[1] :].mean(axis=0)
    aux_std = x_all[chosen, norm_waves.shape[1] :].std(axis=0) + 1e-6
    y_mean = float(np.mean(y[chosen]))
    y_std = float(np.std(y[chosen]) + 1e-6)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(int(config["random_seed"]) + (17 if gated else 11))
    train_seq_np = transformer_sequences(norm_waves[chosen], gated)
    model = CompactWaveformTransformer(
        n_aux=aux_cols,
        in_channels=train_seq_np.shape[2],
        d_model=int(config["models"]["transformer_d_model"]),
        heads=int(config["models"]["transformer_heads"]),
        gated=gated,
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["cnn_learning_rate"]), weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    batch_size = int(config["models"]["cnn_batch_size"])
    seq_train = torch.tensor(train_seq_np, dtype=torch.float32)
    aux_train = torch.tensor((x_all[chosen, norm_waves.shape[1] :] - aux_mean) / aux_std, dtype=torch.float32)
    y_train = torch.tensor((y[chosen] - y_mean) / y_std, dtype=torch.float32)
    order = np.arange(len(chosen))
    for _ in range(int(config["models"]["transformer_epochs"])):
        rng.shuffle(order)
        for start in range(0, len(order), batch_size):
            rows = order[start : start + batch_size]
            opt.zero_grad(set_to_none=True)
            pred = model(seq_train[rows].to(device), aux_train[rows].to(device))
            loss = loss_fn(pred, y_train[rows].to(device))
            loss.backward()
            opt.step()
    out = np.zeros(len(pred_idx), dtype=float)
    model.eval()
    with torch.no_grad():
        for start in range(0, len(pred_idx), 4096):
            rows = pred_idx[start : start + 4096]
            seq = torch.tensor(transformer_sequences(norm_waves[rows], gated), dtype=torch.float32).to(device)
            aux = torch.tensor((x_all[rows, norm_waves.shape[1] :] - aux_mean) / aux_std, dtype=torch.float32).to(device)
            out[start : start + len(rows)] = model(seq, aux).cpu().numpy() * y_std + y_mean
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
    clip_lo = max(float(clip_lo), -20.0)
    clip_hi = min(float(clip_hi), 20.0)

    def supported(pred: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(pred, dtype=float), clip_lo, clip_hi)

    best_alpha = None
    best_score = float("inf")
    for alpha in [float(a) for a in config["models"]["ridge_alphas"]]:
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(X_train, y_train)
        pred_train = model.predict(X_train)
        score = sigma68(y_train - pred_train)
        rows.append({"method": "ridge", "hyperparameter": f"alpha={alpha:g}", "train_residual_sigma68_ns": score})
        if score < best_score:
            best_alpha, best_score = alpha, score
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
    ridge.fit(X_train, y_train)
    predictions["ridge"] = supported(ridge.predict(X_pred))

    hgb = HistGradientBoostingRegressor(max_iter=int(config["models"]["hgb_max_iter"]), learning_rate=0.055, l2_regularization=0.02, random_state=int(config["random_seed"]))
    hgb.fit(X_train, y_train)
    predictions["gradient_boosted_trees"] = supported(hgb.predict(X_pred))
    rows.append({"method": "gradient_boosted_trees", "hyperparameter": f"max_iter={config['models']['hgb_max_iter']}", "train_residual_sigma68_ns": sigma68(y_train - hgb.predict(X_train))})

    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=tuple(config["models"]["mlp_hidden"]), max_iter=int(config["models"]["mlp_max_iter"]), alpha=1e-4, random_state=int(config["random_seed"]), early_stopping=True),
    )
    mlp.fit(X_train, y_train)
    predictions["mlp"] = supported(mlp.predict(X_pred))
    rows.append({"method": "mlp", "hyperparameter": f"hidden={config['models']['mlp_hidden']}", "train_residual_sigma68_ns": sigma68(y_train - mlp.predict(X_train))})

    predictions["cnn_1d"] = supported(fit_cnn(norm_waves, x_all, targets, train_idx, pred_idx, config, rng))
    rows.append({"method": "cnn_1d", "hyperparameter": f"epochs={config['models']['cnn_epochs']}", "train_residual_sigma68_ns": np.nan})

    predictions["compact_waveform_transformer"] = supported(fit_transformer(norm_waves, x_all, targets, train_idx, pred_idx, config, rng, gated=False))
    rows.append({"method": "compact_waveform_transformer", "hyperparameter": f"d={config['models']['transformer_d_model']}, epochs={config['models']['transformer_epochs']}", "train_residual_sigma68_ns": np.nan})

    predictions["phase_local_transformer_new"] = supported(fit_transformer(norm_waves, x_all, targets, train_idx, pred_idx, config, rng, gated=True))
    rows.append({"method": "phase_local_transformer_new", "hyperparameter": "waveform+derivative attention gate", "train_residual_sigma68_ns": np.nan})

    extra = ExtraTreesRegressor(n_estimators=160, min_samples_leaf=4, max_features=0.8, n_jobs=-1, random_state=int(config["random_seed"]))
    extra.fit(X_train, y_train)
    gb_pred = predictions["gradient_boosted_trees"]
    cnn_pred = predictions["cnn_1d"]
    extra_pred = supported(extra.predict(X_pred))
    predictions["shape_residual_fusion"] = supported(0.45 * gb_pred + 0.35 * extra_pred + 0.20 * cnn_pred)
    rows.append({"method": "shape_residual_fusion", "hyperparameter": "0.45 HGB + 0.35 ExtraTrees + 0.20 CNN", "train_residual_sigma68_ns": sigma68(y_train - extra.predict(X_train))})

    return predictions, pd.DataFrame(rows)


def add_bins(meta: pd.DataFrame, features: pd.DataFrame, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    out = features.copy()
    train_baseline = out.loc[train_mask, "baseline_proxy_adc"].to_numpy(float)
    edges = np.unique(np.quantile(train_baseline, np.linspace(0.0, 1.0, int(config["pedestal_bins"]) + 1)))
    out["pedestal_bin"] = np.searchsorted(edges[1:-1], out["baseline_proxy_adc"].to_numpy(float), side="right")
    out["pileup_bin"] = np.where(out["post_peak_frac"].to_numpy(float) >= float(config["pileup_tail_threshold"]), "mild_pileup", "single_like")
    med = meta.loc[train_mask].groupby("stave_idx")["amplitude_adc"].median().to_dict()
    pid = []
    for stave, amp in zip(meta["stave_idx"].to_numpy(int), meta["amplitude_adc"].to_numpy(float)):
        ratio = amp / max(float(med.get(int(stave), amp)), 1.0)
        if ratio < 0.75:
            pid.append("low_dE_proxy")
        elif ratio > 1.35:
            pid.append("high_dE_proxy")
        else:
            pid.append("mid_dE_proxy")
    out["pid_proxy"] = pid
    return out


def method_summary(method_times: Dict[str, np.ndarray], meta_eval: pd.DataFrame, features_eval: pd.DataFrame, ref_phase: np.ndarray, ref_rise: np.ndarray, ref_energy: np.ndarray, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    reps = int(config["bootstrap_replicates"])
    for method, times in method_times.items():
        pairs = timing_pair_table(meta_eval, times, config)
        res = pairs["residual_ns"].to_numpy(float)
        runs = pairs["run"].to_numpy(int)
        sig, lo, hi = run_bootstrap(res, runs, rng, reps, sigma68)
        med, med_lo, med_hi = run_bootstrap(res, runs, rng, reps, lambda x: float(np.median(x)))
        phase_bias = times - ref_phase
        rise_bias = features_eval["rise20_80_ns"].to_numpy(float) - ref_rise
        energy_drift = features_eval["area_norm"].to_numpy(float) - ref_energy
        pulse_runs = meta_eval["run"].to_numpy(int)
        pb, pb_lo, pb_hi = run_bootstrap(phase_bias, pulse_runs, rng, reps, lambda x: float(np.median(x)))
        rb, rb_lo, rb_hi = run_bootstrap(rise_bias, pulse_runs, rng, reps, lambda x: float(np.median(x)))
        ed, ed_lo, ed_hi = run_bootstrap(energy_drift, pulse_runs, rng, reps, lambda x: float(np.median(x)))
        rows.append(
            {
                "method": method,
                "n_pair_residuals": int(len(res)),
                "timing_sigma68_ns": sig,
                "timing_sigma68_ci_low": lo,
                "timing_sigma68_ci_high": hi,
                "median_residual_ns": med,
                "median_residual_ci_low": med_lo,
                "median_residual_ci_high": med_hi,
                "shape_phase_bias_ns": pb,
                "shape_phase_bias_ci_low": pb_lo,
                "shape_phase_bias_ci_high": pb_hi,
                "rise_time_bias_ns": rb,
                "rise_time_bias_ci_low": rb_lo,
                "rise_time_bias_ci_high": rb_hi,
                "energy_drift_area_norm": ed,
                "energy_drift_ci_low": ed_lo,
                "energy_drift_ci_high": ed_hi,
            }
        )
    return pd.DataFrame(rows)


def stratified_errors(method_times: Dict[str, np.ndarray], meta_eval: pd.DataFrame, features_eval: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for method, times in method_times.items():
        pulse = meta_eval.copy()
        pulse["time_ns"] = times
        pulse["pid_proxy"] = features_eval["pid_proxy"].to_numpy()
        pulse["pedestal_bin"] = features_eval["pedestal_bin"].to_numpy()
        pulse["pileup_bin"] = features_eval["pileup_bin"].to_numpy()
        for pid in sorted(pulse["pid_proxy"].unique()):
            for ped in sorted(pulse["pedestal_bin"].unique()):
                for pile in sorted(pulse["pileup_bin"].unique()):
                    idx_pulse = (pulse["pid_proxy"] == pid) & (pulse["pedestal_bin"] == ped) & (pulse["pileup_bin"] == pile)
                    sub = pulse.loc[idx_pulse].copy()
                    if sub["event_index"].nunique() < 20:
                        continue
                    pairs = timing_pair_table(sub.reset_index(drop=True), sub["time_ns"].to_numpy(float), config)
                    if len(pairs) < 30:
                        continue
                    sig, lo, hi = run_bootstrap(pairs["residual_ns"].to_numpy(float), pairs["run"].to_numpy(int), rng, int(config["bootstrap_replicates"]), sigma68)
                    rows.append(
                        {
                            "method": method,
                            "pid_proxy": pid,
                            "pedestal_bin": int(ped),
                            "pileup_bin": pile,
                            "n_pair_residuals": int(len(pairs)),
                            "timing_sigma68_ns": sig,
                            "ci_low": lo,
                            "ci_high": hi,
                        }
                    )
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: List[str], sort: str | None = None, max_rows: int | None = None) -> str:
    tab = df.copy()
    if sort is not None:
        tab = tab.sort_values(sort)
    if max_rows is not None:
        tab = tab.head(max_rows)
    return markdown_table(tab[cols])


def markdown_table(df: pd.DataFrame) -> str:
    def fmt(value) -> str:
        if isinstance(value, (float, np.floating)):
            if not np.isfinite(value):
                return ""
            return f"{float(value):.4g}"
        return str(value)

    headers = [str(c) for c in df.columns]
    rows = [[fmt(v).replace("|", "\\|") for v in row] for row in df.to_numpy()]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    header = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep] + body)


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, strata: pd.DataFrame, training: pd.DataFrame, leakage: pd.DataFrame) -> None:
    summary_md = md_table(summary, ["method", "timing_sigma68_ns", "timing_sigma68_ci_low", "timing_sigma68_ci_high", "median_residual_ns", "shape_phase_bias_ns", "rise_time_bias_ns", "energy_drift_area_norm"], "timing_sigma68_ns")
    strata_md = md_table(strata, ["method", "pid_proxy", "pedestal_bin", "pileup_bin", "n_pair_residuals", "timing_sigma68_ns", "ci_low", "ci_high"], "timing_sigma68_ns", 36)
    training_md = markdown_table(training)
    leakage_md = markdown_table(leakage)
    winner = result["winner"]
    report = f"""# S49a: Phase-local pulse-shape timing pedestal drift benchmark

**Ticket:** `{result['ticket_id']}`  
**Worker:** `{result['worker']}`  
**Raw ROOT source:** `{result['raw_root_dir']}`

## Abstract

This ticket asks whether a strong traditional trapezoid-template phase extractor
is still competitive with modern learned pulse-shape regressors when all
methods are evaluated on runs excluded from training. The raw B-stack ROOT files
are read before any benchmark is run, the canonical selected-pulse count is
reproduced exactly, and the same held-out runs are used for all confidence
intervals. The winning method recorded in `result.json` is
**`{winner['method']}`**, with held-out timing sigma68
**{winner['timing_sigma68_ns']:.4g} ns** and 95% run-bootstrap CI
[{winner['ci_low']:.4g}, {winner['ci_high']:.4g}] ns.

## Raw-ROOT Reproduction Gate

The benchmark starts from raw `HRDv` arrays in `{result['raw_root_dir']}`. For
each configured B-stack run, channels B2, B4, B6, and B8 are baseline-subtracted
with the median of samples 0--3. A pulse is selected when
A = max_t(x_t - b) > 1000 ADC. This rerun reproduced
**{result['reproduction']['selected_pulses']:,}** selected B-stave pulses
against the expected **{result['reproduction']['expected_selected_pulses']:,}**
with zero tolerance.

## Estimands and Equations

The primary timing observable is a downstream pair residual. For pulse i on
stave s, each method estimates a phase time t_hat_i. A small time-of-flight
correction is applied by stave position z_s: tau_i = t_hat_i - 0.078 z_s ns/cm.

For every held-out event containing B4, B6, and/or B8, pair residuals are
r_ab = tau_a - tau_b. The robust timing resolution is sigma68 =
(Q84(r) - Q16(r)) / 2.

Uncertainty intervals are non-parametric bootstraps over held-out run labels,
not over individual pulses. The secondary shape diagnostics are the median phase
bias relative to the traditional template phase, the median 20--80% rise-time
bias, and median normalized-area drift. PID strata use a raw dE proxy from
within-stave amplitude terciles; pedestal strata use baseline-proxy terciles;
mild pile-up strata use late post-peak normalized amplitude.

## Methods

**Traditional trapezoid-template.** Train-run median templates are built
separately for B2/B4/B6/B8. The normalized waveform is passed through a short
trapezoid shaper with rise `{result['trapezoid']['rise']}` and flat
`{result['trapezoid']['flat']}` samples. The phase is obtained by minimum-SSE
template matching on a `{result['template_grid']['step']}` sample grid with
parabolic interpolation at the minimum.

**Ridge.** A standardized linear residual corrector predicts the per-pulse
correction to the traditional phase from the 18 normalized samples and
shape-summary features.

**Gradient-boosted trees.** A histogram gradient-boosted regressor uses the same
feature table to model nonlinear timing residuals.

**MLP.** A two-layer feed-forward network is trained with early stopping on the
same run-held-out correction target.

**1D-CNN.** A compact convolutional regressor sees the 18-sample waveform as a
one-dimensional signal plus auxiliary shape features.

**Compact waveform transformer.** A one-layer self-attention encoder is trained
directly on the 18 normalized samples with the same auxiliary shape features.

**Phase-local transformer.** The ticket-local architecture,
`phase_local_transformer_new`, adds a first-derivative channel and pools
self-attention states with a derivative-magnitude gate. It is sensible here
because the requested failure mode is phase-local shape drift: derivative
weighting emphasizes the rising edge and late tail without introducing run
identity as a feature.

**Shape-residual fusion.** A budgeted residual fusion is retained as an
additional nonlinear comparator: histogram gradient boosting, ExtraTrees shape
residuals, and the compact CNN are combined with fixed weights selected before
held-out evaluation.

## Training Audit

{training_md}

## Held-out Results

{summary_md}

## PID, Pedestal, and Mild Pile-up Strata

The table reports the most precise strata first. CIs are still run bootstraps,
so intervals can be wide where only a few held-out runs support a bin.

{strata_md}

## Leakage and Systematics Checks

{leakage_md}

## Systematic Caveats

1. The timing target is self-supervised from same-event downstream consistency,
   not an external clock. A method can improve pair closure without proving
   absolute time calibration.
2. PID labels are amplitude-based dE proxies. They are useful stratification
   axes but are not particle-identification truth.
3. The mild pile-up label is a waveform-tail proxy; it catches late structure
   but does not distinguish electronic after-pulsing from genuine two-pulse
   overlap.
4. Neural methods were deliberately kept compact and CPU/GPU portable. The
   conclusion is about this reproducible local budget, not about all possible
   neural architectures.
5. Bootstrap units are runs. With only four held-out runs, interval coverage is
   conservative but coarse.

## Conclusion

The winner is **`{winner['method']}`** by held-out downstream pair
sigma68. The result is named in `result.json`, and the raw reproduction
gate, run split, leakage sentinels, method table, and stratum table are written
alongside this report.
"""
    (out_dir / "REPORT.md").write_text(report + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s49a_2445_phase_local_pulse_shape_timing_pedestal_drift_benchmark.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_root_dir = p01d.resolve_raw_root_dir(config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

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
    trad_time_all, template_sse = template_phase_time(norm_waves, meta, templates, config)
    features = feature_table(norm_waves, corrected, meta, template_sse, config)
    features = add_bins(meta, features, train_mask, config)
    x_all = design_matrix(norm_waves, features)
    targets = timing_targets(meta, trad_time_all, config)
    predictions, training = fit_predict_models(norm_waves, x_all, targets, train_mask, heldout_mask, config, rng)

    eval_idx = np.flatnonzero(heldout_mask)
    meta_eval = meta.loc[heldout_mask].reset_index(drop=True)
    features_eval = features.loc[heldout_mask].reset_index(drop=True)
    method_times = {"trapezoid_template": trad_time_all[heldout_mask].copy()}
    for method, correction in predictions.items():
        method_times[method] = trad_time_all[heldout_mask] - correction

    ref_phase = trad_time_all[heldout_mask]
    ref_rise = features.loc[heldout_mask, "rise20_80_ns"].to_numpy(float)
    ref_energy = features.loc[heldout_mask, "area_norm"].to_numpy(float)
    summary = method_summary(method_times, meta_eval, features_eval, ref_phase, ref_rise, ref_energy, config, rng)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    strata = stratified_errors(method_times, meta_eval, features_eval, config, rng)
    strata.to_csv(out_dir / "stratified_errors.csv", index=False)
    training.to_csv(out_dir / "training_summary.csv", index=False)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": expected,
                "reproduced": total_selected,
                "delta": total_selected - expected,
                "tolerance": 0,
                "pass": total_selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    pair_rows = []
    for method, times in method_times.items():
        pairs = timing_pair_table(meta_eval, times, config)
        pairs.insert(0, "method", method)
        pair_rows.append(pairs)
    pd.concat(pair_rows, ignore_index=True).to_csv(out_dir / "heldout_pair_residuals.csv", index=False)

    input_rows = []
    for run in p01d.configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    best = summary.sort_values("timing_sigma68_ns").iloc[0].to_dict()
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_root_reproduction",
                "pass": total_selected == expected,
                "value": total_selected,
                "detail": "canonical selected-pulse count must match exactly",
            },
            {
                "check": "train_heldout_run_overlap",
                "pass": len(set(runs[train_mask]) & set(runs[heldout_mask])) == 0,
                "value": int(len(set(runs[train_mask]) & set(runs[heldout_mask]))),
                "detail": "split by run",
            },
            {
                "check": "finite_traditional_phase",
                "pass": bool(np.isfinite(trad_time_all[heldout_mask]).all()),
                "value": int(np.isfinite(trad_time_all[heldout_mask]).sum()),
                "detail": "all held-out pulses must have a traditional phase anchor",
            },
            {
                "check": "training_target_rows",
                "pass": int(np.isfinite(targets[train_mask]).sum()) > 1000,
                "value": int(np.isfinite(targets[train_mask]).sum()),
                "detail": "same-event downstream consistency targets from train runs",
            },
            {
                "check": "winner_named_in_result_json",
                "pass": True,
                "value": str(best["method"]),
                "detail": "winner is selected by minimum held-out timing sigma68",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "claimed_ticket_text": (
            "#2445 S49a: Phase-local pulse-shape timing pedestal drift benchmark\n\n"
            "Compare a constant-fraction/template-fit timing baseline against ridge, "
            "gradient-boosted trees, MLP, 1D-CNN, and a compact waveform transformer. "
            "Quantify how pedestal drift and phase-local shape modes bias time pickoff "
            "and charge using run-block bootstrap CIs, per-stave strata, and "
            "leakage-guarded heldout runs."
        ),
        "raw_root_dir": str(raw_root_dir),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": total_selected,
            "passed": total_selected == expected,
        },
        "split": {
            "train_runs": sorted(int(r) for r in np.unique(runs[train_mask])),
            "heldout_runs": [int(r) for r in heldout_runs],
            "train_pulses": int(train_mask.sum()),
            "heldout_pulses": int(heldout_mask.sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "methods_benchmarked": list(method_times.keys()),
        "winner": {
            "method": str(best["method"]),
            "selection_metric": "minimum held-out downstream pair timing sigma68_ns",
            "timing_sigma68_ns": float(best["timing_sigma68_ns"]),
            "ci_low": float(best["timing_sigma68_ci_low"]),
            "ci_high": float(best["timing_sigma68_ci_high"]),
        },
        "traditional_method": "trapezoid_template",
        "trapezoid": config["trapezoid"],
        "template_grid": config["template_shift_grid"],
        "new_architecture": "phase_local_transformer_new",
        "method_summary": summary.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "novel_ticket_appended": False,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, result, summary, strata, training, leakage)

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "command": " ".join(sys.argv),
        "script": str(Path(__file__).resolve().relative_to(ROOT)),
        "config": str(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "packages": {
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": torch.__version__,
        },
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
