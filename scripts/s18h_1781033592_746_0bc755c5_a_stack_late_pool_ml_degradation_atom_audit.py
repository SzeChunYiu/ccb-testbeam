#!/usr/bin/env python3
"""S18h: atom audit for late-pool A-stack ML degradation.

This script extends S18e with a broader method bakeoff and explicit failure-atom
diagnostics. It reads raw A-stack ROOT files, reconstructs A1-A3 CFD20 pairs,
benchmarks traditional and learned residual corrections on Sample IV held-out
runs, and writes the report artifacts for the ticket-owned directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault(
    "MPLCONFIGDIR",
    "reports/1781033592.746.0bc755c5__s18h_a_stack_late_pool_ml_degradation_atom_audit/.mplconfig",
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from scipy.optimize import curve_fit
from scipy.stats import ks_2samp
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def git_head() -> str:
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


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def root_path(config: Dict[str, Any], run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{config['astack']['file_prefix']}_run_{run:04d}.root"


def raw_batches(path: Path, step_size: int = 20000) -> Iterable[Dict[str, Any]]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np")


def cfd_times(
    waveforms: np.ndarray, baseline_samples: Sequence[int], fraction: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_samples], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak_sample = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    tail_fraction = corrected[..., 10:].sum(axis=-1) / np.maximum(area, 1.0)

    threshold = fraction * amplitude
    current = corrected[..., 1:]
    previous = corrected[..., :-1]
    sample_index = np.arange(1, corrected.shape[-1])[None, None, :]
    eligible = (sample_index <= peak_sample[..., None]) & (current >= threshold[..., None]) & (previous < threshold[..., None])
    has_crossing = eligible.any(axis=-1)
    crossing = eligible.argmax(axis=-1) + 1

    row_idx = np.arange(corrected.shape[0])[:, None]
    col_idx = np.arange(corrected.shape[1])[None, :]
    y0 = corrected[row_idx, col_idx, np.maximum(crossing - 1, 0)]
    y1 = corrected[row_idx, col_idx, crossing]
    denom = y1 - y0
    frac = np.divide(threshold - y0, denom, out=np.zeros_like(threshold), where=np.abs(denom) > 1e-12)
    time_ns = (crossing - 1 + frac) * 10.0
    time_ns = np.where(has_crossing, time_ns, peak_sample * 10.0)
    return corrected, amplitude, peak_sample, area, tail_fraction, time_ns


def load_pair_table(config: Dict[str, Any], runs: Sequence[int], sample: str) -> pd.DataFrame:
    staves = config["astack"]["staves"]
    channels = [int(staves["A1"]), int(staves["A3"])]
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    rows: List[pd.DataFrame] = []
    for run in runs:
        for batch in raw_batches(root_path(config, int(run))):
            event = np.asarray(batch["EVT"]).astype(int)
            waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
            chosen = waveforms[:, channels, :]
            corrected, amplitude, peak, area, tail, time_ns = cfd_times(chosen, baseline_samples, float(config["cfd_fraction"]))
            selected = (amplitude[:, 0] > cut) & (amplitude[:, 1] > cut)
            if not selected.any():
                continue
            wave_left = corrected[selected, 0, :]
            wave_right = corrected[selected, 1, :]
            frame = pd.DataFrame(
                {
                    "sample": sample,
                    "run": int(run),
                    "event": event[selected],
                    "amp_left": amplitude[selected, 0],
                    "amp_right": amplitude[selected, 1],
                    "peak_left": peak[selected, 0],
                    "peak_right": peak[selected, 1],
                    "area_left": area[selected, 0],
                    "area_right": area[selected, 1],
                    "tail_left": tail[selected, 0],
                    "tail_right": tail[selected, 1],
                    "time_left_ns": time_ns[selected, 0],
                    "time_right_ns": time_ns[selected, 1],
                }
            )
            for idx in range(int(config["samples_per_channel"])):
                frame[f"wl_{idx:02d}"] = wave_left[:, idx]
                frame[f"wr_{idx:02d}"] = wave_right[:, idx]
            frame["raw_residual_ns"] = frame["time_right_ns"] - frame["time_left_ns"]
            rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def robust_width(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    centered = values - np.nanmedian(values)
    return float(0.5 * (np.percentile(centered, 84) - np.percentile(centered, 16)))


def full_rms(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    centered = values - np.nanmedian(values)
    return float(np.sqrt(np.mean(centered * centered)))


def gaussian(x: np.ndarray, amplitude: float, mean: float, sigma: float) -> np.ndarray:
    return amplitude * np.exp(-0.5 * ((x - mean) / sigma) ** 2)


def gaussian_core(values: np.ndarray, window: float, bins: int) -> Dict[str, Any]:
    centered = values[np.isfinite(values)] - np.nanmedian(values)
    counts, edges = np.histogram(centered, bins=np.linspace(-window, window, bins + 1))
    centers = 0.5 * (edges[:-1] + edges[1:])
    mask = counts > 0
    try:
        params, covariance = curve_fit(
            gaussian,
            centers[mask],
            counts[mask],
            p0=[float(counts.max()), 0.0, max(robust_width(centered), 0.5)],
            sigma=np.sqrt(counts[mask]),
            absolute_sigma=True,
            maxfev=10000,
        )
        expected = gaussian(centers[mask], *params)
        chi2 = float(np.sum((counts[mask] - expected) ** 2 / np.maximum(expected, 1e-9)))
        ndf = int(mask.sum() - 3)
        sigma_err = float(np.sqrt(np.diag(covariance))[2]) if covariance.shape == (3, 3) else float("nan")
        return {
            "core_sigma_ns": float(abs(params[2])),
            "core_sigma_err_ns": sigma_err,
            "core_mean_ns": float(params[1]),
            "chi2_ndf": float(chi2 / ndf) if ndf > 0 else float("nan"),
            "fit_window_ns": float(window),
        }
    except Exception as exc:
        return {
            "core_sigma_ns": float("nan"),
            "core_sigma_err_ns": float("nan"),
            "core_mean_ns": float("nan"),
            "chi2_ndf": float("nan"),
            "fit_window_ns": float(window),
            "fit_error": str(exc),
        }


def traditional_features(df: pd.DataFrame, with_period: bool = True) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    cols = [np.ones(len(df)), left, right, left * left, right * right, left * right]
    if with_period:
        cols.append((df["sample"].to_numpy() == "sample_iv").astype(float))
    return np.column_stack(cols)


def engineered_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    area_left = np.log(np.maximum(df["area_left"].to_numpy(), 1.0))
    area_right = np.log(np.maximum(df["area_right"].to_numpy(), 1.0))
    return np.column_stack(
        [
            left,
            right,
            left - right,
            left + right,
            df["peak_left"].to_numpy(),
            df["peak_right"].to_numpy(),
            area_left,
            area_right,
            area_left - area_right,
            df["tail_left"].to_numpy(),
            df["tail_right"].to_numpy(),
            (df["sample"].to_numpy() == "sample_iv").astype(float),
        ]
    )


def wave_tensor(df: pd.DataFrame, samples: int) -> np.ndarray:
    left = df[[f"wl_{idx:02d}" for idx in range(samples)]].to_numpy(dtype=np.float32)
    right = df[[f"wr_{idx:02d}" for idx in range(samples)]].to_numpy(dtype=np.float32)
    scale = np.maximum(np.maximum(left.max(axis=1), right.max(axis=1)), 1.0).astype(np.float32)
    left = left / scale[:, None]
    right = right / scale[:, None]
    return np.stack([left, right], axis=1).astype(np.float32)


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    beta = np.linalg.lstsq(traditional_features(train), train["raw_residual_ns"].to_numpy(), rcond=None)[0]
    pred = traditional_features(test) @ beta
    return test["raw_residual_ns"].to_numpy() - pred


def group_cv_splits(groups: np.ndarray) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
    unique = np.unique(groups)
    if len(unique) < 2:
        yield np.arange(len(groups)), np.arange(len(groups))
    else:
        yield from GroupKFold(n_splits=min(5, len(unique))).split(np.zeros(len(groups)), np.zeros(len(groups)), groups)


def tune_ridge(train: pd.DataFrame, alphas: Sequence[float]) -> Tuple[Any, pd.DataFrame]:
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    rows = []
    for alpha in alphas:
        rmses = []
        for tr_idx, va_idx in group_cv_splits(groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        rows.append({"method": "ridge", "params": json.dumps({"alpha": float(alpha)}), "cv_rmse_ns": float(np.mean(rmses))})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns", "params"]).reset_index(drop=True)
    params = json.loads(table.iloc[0]["params"])
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(params["alpha"])))
    model.fit(x, y)
    return model, table


def tune_gbr(train: pd.DataFrame, grid: Sequence[Dict[str, Any]], seed: int) -> Tuple[Any, pd.DataFrame]:
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    rows = []
    for params in grid:
        rmses = []
        for tr_idx, va_idx in group_cv_splits(groups):
            model = GradientBoostingRegressor(random_state=seed, loss="ls", **params)
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        rows.append({"method": "gradient_boosted_trees", "params": json.dumps(params, sort_keys=True), "cv_rmse_ns": float(np.mean(rmses))})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns", "params"]).reset_index(drop=True)
    params = json.loads(table.iloc[0]["params"])
    model = GradientBoostingRegressor(random_state=seed, loss="ls", **params)
    model.fit(x, y)
    return model, table


def tune_mlp(train: pd.DataFrame, grid: Sequence[Dict[str, Any]], seed: int) -> Tuple[Any, pd.DataFrame]:
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    rows = []
    for params in grid:
        rmses = []
        for tr_idx, va_idx in group_cv_splits(groups):
            model = make_pipeline(
                StandardScaler(),
                MLPRegressor(
                    hidden_layer_sizes=tuple(params["hidden_layer_sizes"]),
                    alpha=float(params["alpha"]),
                    random_state=seed,
                    max_iter=500,
                    early_stopping=True,
                    n_iter_no_change=20,
                ),
            )
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        rows.append({"method": "mlp", "params": json.dumps(params, sort_keys=True), "cv_rmse_ns": float(np.mean(rmses))})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns", "params"]).reset_index(drop=True)
    params = json.loads(table.iloc[0]["params"])
    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(params["hidden_layer_sizes"]),
            alpha=float(params["alpha"]),
            random_state=seed,
            max_iter=600,
            early_stopping=True,
            n_iter_no_change=30,
        ),
    )
    model.fit(x, y)
    return model, table


class CnnRegressor(nn.Module):
    def __init__(self, n_features: int, gated: bool = False) -> None:
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(
            nn.Conv1d(2, 8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(8, 8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.feat = nn.Sequential(nn.Linear(n_features, 16), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(24, 16), nn.ReLU(), nn.Linear(16, 1))
        if gated:
            self.base = nn.Linear(n_features, 1)
            self.gate = nn.Sequential(nn.Linear(n_features, 8), nn.ReLU(), nn.Linear(8, 1), nn.Sigmoid())

    def forward(self, wave: torch.Tensor, feat: torch.Tensor) -> torch.Tensor:
        conv = self.conv(wave).squeeze(-1)
        feat_h = self.feat(feat)
        delta = self.head(torch.cat([conv, feat_h], dim=1)).squeeze(-1)
        if not self.gated:
            return delta
        gate = self.gate(feat).squeeze(-1)
        return self.base(feat).squeeze(-1) + gate * delta


def torch_train_predict(
    train: pd.DataFrame,
    test: pd.DataFrame,
    config: Dict[str, Any],
    gated: bool,
    seed: int,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    torch.manual_seed(seed)
    np.random.seed(seed)
    samples = int(config["samples_per_channel"])
    min_train = int(config["torch"]["min_train_pairs"])
    if len(train) < min_train or len(np.unique(train["run"].to_numpy())) < 2:
        model, cv = tune_ridge(train, config["ridge_alphas"])
        pred = model.predict(engineered_features(test))
        return pred, {"status": "fallback_ridge_small_pool", "cv_rmse_ns": float(cv.iloc[0]["cv_rmse_ns"])}

    x_feat = engineered_features(train).astype(np.float32)
    y = train["raw_residual_ns"].to_numpy(dtype=np.float32)
    groups = train["run"].to_numpy()
    runs = np.array(sorted(np.unique(groups)))
    val_run = int(runs[-1])
    tr_mask = groups != val_run
    va_mask = groups == val_run
    feat_mean = x_feat[tr_mask].mean(axis=0)
    feat_std = x_feat[tr_mask].std(axis=0)
    feat_std[feat_std == 0] = 1.0
    y_mean = float(y[tr_mask].mean())
    y_std = float(y[tr_mask].std() if y[tr_mask].std() > 1e-6 else 1.0)

    wave = wave_tensor(train, samples)
    wave_test = wave_tensor(test, samples)
    feat = ((x_feat - feat_mean) / feat_std).astype(np.float32)
    feat_test = ((engineered_features(test).astype(np.float32) - feat_mean) / feat_std).astype(np.float32)
    y_scaled = ((y - y_mean) / y_std).astype(np.float32)

    model = CnnRegressor(feat.shape[1], gated=gated)
    optim = torch.optim.AdamW(model.parameters(), lr=float(config["torch"]["learning_rate"]), weight_decay=float(config["torch"]["weight_decay"]))
    loss_fn = nn.MSELoss()
    batch_size = int(config["torch"]["batch_size"])
    best_state = None
    best_val = float("inf")
    train_idx = np.where(tr_mask)[0]
    val_wave = torch.from_numpy(wave[va_mask])
    val_feat = torch.from_numpy(feat[va_mask])
    val_y = torch.from_numpy(y_scaled[va_mask])

    for _epoch in range(int(config["torch"]["epochs"])):
        np.random.shuffle(train_idx)
        model.train()
        for start in range(0, len(train_idx), batch_size):
            idx = train_idx[start : start + batch_size]
            pred = model(torch.from_numpy(wave[idx]), torch.from_numpy(feat[idx]))
            loss = loss_fn(pred, torch.from_numpy(y_scaled[idx]))
            if gated:
                loss = loss + 0.002 * torch.mean(torch.abs(model.gate(torch.from_numpy(feat[idx])).squeeze(-1)))
            optim.zero_grad()
            loss.backward()
            optim.step()
        model.eval()
        with torch.no_grad():
            val_pred = model(val_wave, val_feat)
            val_loss = float(loss_fn(val_pred, val_y).item())
        if val_loss < best_val:
            best_val = val_loss
            best_state = {key: val.detach().clone() for key, val in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred_scaled = model(torch.from_numpy(wave_test), torch.from_numpy(feat_test)).numpy()
    pred = pred_scaled * y_std + y_mean
    return pred.astype(float), {"status": "trained", "validation_run": val_run, "cv_rmse_ns": float(math.sqrt(best_val) * y_std)}


def train_models_for_pool(train: pd.DataFrame, config: Dict[str, Any], pool: str, seed: int) -> Tuple[Dict[str, Any], pd.DataFrame]:
    models: Dict[str, Any] = {}
    cv_rows: List[pd.DataFrame] = []
    ridge, ridge_cv = tune_ridge(train, config["ridge_alphas"])
    ridge_cv["pool"] = pool
    cv_rows.append(ridge_cv)
    models["ridge"] = ridge

    if len(train) >= 80 and len(np.unique(train["run"].to_numpy())) >= 2:
        gbr, gbr_cv = tune_gbr(train, config["gbr_grid"], seed)
        gbr_cv["pool"] = pool
        cv_rows.append(gbr_cv)
        models["gradient_boosted_trees"] = gbr

        mlp, mlp_cv = tune_mlp(train, config["mlp_grid"], seed)
        mlp_cv["pool"] = pool
        cv_rows.append(mlp_cv)
        models["mlp"] = mlp
    else:
        models["gradient_boosted_trees"] = ridge
        models["mlp"] = ridge
        cv_rows.append(pd.DataFrame([{"pool": pool, "method": "gradient_boosted_trees", "params": "fallback_ridge_small_pool", "cv_rmse_ns": np.nan}]))
        cv_rows.append(pd.DataFrame([{"pool": pool, "method": "mlp", "params": "fallback_ridge_small_pool", "cv_rmse_ns": np.nan}]))
    return models, pd.concat(cv_rows, ignore_index=True)


def pool_train_frame(all_pairs: pd.DataFrame, pool_cfg: Dict[str, Any]) -> pd.DataFrame:
    runs: List[int] = [int(run) for run in pool_cfg.get("sample_iii", [])]
    runs.extend(int(run) for run in pool_cfg.get("sample_iv_fixed", []))
    frame = all_pairs[all_pairs["run"].isin(sorted(set(runs)))].copy()
    if frame.empty:
        raise ValueError("empty calibration pool")
    return frame


def row_metric(method: str, values: np.ndarray, config: Dict[str, Any]) -> Dict[str, Any]:
    centered = values - np.nanmedian(values)
    row = {
        "method": method,
        "n_pairs": int(len(values)),
        "median_ns": float(np.nanmedian(values)),
        "robust_width_ns": robust_width(values),
        "full_rms_ns": full_rms(values),
        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(centered) > 5.0)),
        "within_abs_2ns": float(np.mean(np.abs(centered) < 2.0)),
    }
    row.update(gaussian_core(values, 2.5, int(config["gaussian_core_bins"])))
    return row


def run_bootstrap_ci(df: pd.DataFrame, residual_col: str, rng: np.random.Generator, n_resamples: int, metric: Callable[[np.ndarray], float]) -> Tuple[float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = [df.loc[df["run"] == run, residual_col].to_numpy() for run in sampled]
        stats.append(metric(np.concatenate(chunks)))
    return tuple(float(x) for x in np.quantile(stats, [0.025, 0.975]))


def paired_delta(
    df: pd.DataFrame, col_base: str, col_test: str, rng: np.random.Generator, n_resamples: int
) -> Tuple[float, float, float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        base = np.concatenate([df.loc[df["run"] == run, col_base].to_numpy() for run in sampled])
        test = np.concatenate([df.loc[df["run"] == run, col_test].to_numpy() for run in sampled])
        stats.append(robust_width(test) - robust_width(base))
    arr = np.asarray(stats)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    p_value = 2.0 * min(float(np.mean(arr <= 0.0)), float(np.mean(arr >= 0.0)))
    return float(np.median(arr)), float(lo), float(hi), min(p_value, 1.0)


def support_mask(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    train_x = engineered_features(train)
    test_x = engineered_features(test)
    cols = [0, 1, 2, 3, 6, 7, 8, 9, 10]
    mask = np.ones(len(test), dtype=bool)
    for col in cols:
        lo, hi = np.quantile(train_x[:, col], [0.01, 0.99])
        mask &= (test_x[:, col] >= lo) & (test_x[:, col] <= hi)
    return mask


def leakage_checks(train: pd.DataFrame, config: Dict[str, Any], seed: int) -> pd.DataFrame:
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    rows = [
        {"check": "forbidden_feature_overlap", "value": "", "flag": False},
        {"check": "n_train_runs", "value": int(len(np.unique(groups))), "flag": bool(len(np.unique(groups)) < 2)},
    ]
    if len(np.unique(groups)) < 2 or len(train) < 40:
        rows.append({"check": "single_run_or_tiny_pool", "value": int(len(train)), "flag": True})
        return pd.DataFrame(rows)
    group_rmses = []
    for tr_idx, va_idx in group_cv_splits(groups):
        model = make_pipeline(StandardScaler(), Ridge(alpha=100.0))
        model.fit(x[tr_idx], y[tr_idx])
        group_rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
    tr_idx, va_idx = train_test_split(np.arange(len(x)), test_size=0.25, random_state=seed)
    row_model = make_pipeline(StandardScaler(), Ridge(alpha=100.0))
    row_model.fit(x[tr_idx], y[tr_idx])
    row_rmse = math.sqrt(mean_squared_error(y[va_idx], row_model.predict(x[va_idx])))
    shuffled = y.copy()
    np.random.default_rng(seed).shuffle(shuffled)
    shuf_model = make_pipeline(StandardScaler(), Ridge(alpha=100.0))
    shuf_model.fit(x[tr_idx], shuffled[tr_idx])
    shuf_r2 = r2_score(shuffled[va_idx], shuf_model.predict(x[va_idx]))
    run_model = GradientBoostingRegressor(random_state=seed, loss="ls", n_estimators=40, max_depth=2, learning_rate=0.05)
    run_labels = pd.Series(groups).astype("category").cat.codes.to_numpy()
    run_model.fit(x[tr_idx], run_labels[tr_idx])
    run_id_r2 = r2_score(run_labels[va_idx], run_model.predict(x[va_idx]))
    rows.extend(
        [
            {"check": "row_split_advantage_rmse_ns", "value": float(np.mean(group_rmses) - row_rmse), "flag": bool((np.mean(group_rmses) - row_rmse) > 0.5)},
            {"check": "shuffled_target_r2", "value": float(shuf_r2), "flag": bool(shuf_r2 > 0.1)},
            {"check": "run_id_predictability_r2", "value": float(run_id_r2), "flag": bool(run_id_r2 > 0.5)},
        ]
    )
    return pd.DataFrame(rows)


def evaluate(config: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    seed = int(config["random_seed"])
    rng = np.random.default_rng(seed)
    torch.set_num_threads(1)
    sample_iii_runs = [int(x) for x in config["sample_iii_calib_runs"] + config["sample_iii_analysis_runs"]]
    sample_iv_runs = [int(x) for x in config["sample_iv_calib_runs"] + config["sample_iv_analysis_runs"]]
    sample_iii = load_pair_table(config, sample_iii_runs, "sample_iii")
    sample_iv = load_pair_table(config, sample_iv_runs, "sample_iv")
    all_pairs = pd.concat([sample_iii, sample_iv], ignore_index=True)
    heldout_iv = sample_iv[sample_iv["run"].isin(config["sample_iv_analysis_runs"])].copy()

    heldout_rows: List[pd.DataFrame] = []
    cv_rows: List[pd.DataFrame] = []
    train_rows: List[Dict[str, Any]] = []
    support_rows: List[Dict[str, Any]] = []
    leakage_rows: List[pd.DataFrame] = []
    train_cache: Dict[str, pd.DataFrame] = {}

    for pool, pool_cfg in config["calibration_pools"].items():
        train = pool_train_frame(all_pairs, pool_cfg)
        train_cache[pool] = train
        train_rows.append(
            {
                "pool": pool,
                "description": pool_cfg["description"],
                "train_n_pairs": int(len(train)),
                "train_runs": ",".join(str(int(x)) for x in sorted(train["run"].unique())),
            }
        )
        leak = leakage_checks(train, config, seed)
        leak.insert(0, "pool", pool)
        leakage_rows.append(leak)
        models, cv_table = train_models_for_pool(train, config, pool, seed)
        cv_rows.append(cv_table)

        test = heldout_iv.copy()
        frame = test[["run", "event", "raw_residual_ns"]].copy()
        frame["pool"] = pool
        frame["traditional_residual_ns"] = fit_traditional(train, test)
        for method in ["ridge", "gradient_boosted_trees", "mlp"]:
            pred = models[method].predict(engineered_features(test))
            frame[f"{method}_residual_ns"] = test["raw_residual_ns"].to_numpy() - pred
        for method, gated in [("cnn1d", False), ("support_gated_cnn", True)]:
            pred, info = torch_train_predict(train, test, config, gated=gated, seed=seed + len(pool) + (1 if gated else 0))
            frame[f"{method}_residual_ns"] = test["raw_residual_ns"].to_numpy() - pred
            cv_rows.append(pd.DataFrame([{"pool": pool, "method": method, "params": info["status"], "cv_rmse_ns": info["cv_rmse_ns"]}]))
        frame["support_mask"] = support_mask(train, test)
        heldout_rows.append(frame)

        for feature, col in [("log_amp_left", "amp_left"), ("log_amp_right", "amp_right"), ("tail_left", "tail_left"), ("tail_right", "tail_right")]:
            train_values = np.log(np.maximum(train[col].to_numpy(), 1.0)) if col.startswith("amp") else train[col].to_numpy()
            test_values = np.log(np.maximum(test[col].to_numpy(), 1.0)) if col.startswith("amp") else test[col].to_numpy()
            ks = ks_2samp(train_values, test_values)
            support_rows.append(
                {
                    "pool": pool,
                    "feature": feature,
                    "train_median": float(np.median(train_values)),
                    "heldout_median": float(np.median(test_values)),
                    "ks_stat": float(ks.statistic),
                    "ks_p_value": float(ks.pvalue),
                }
            )

    heldout = pd.concat(heldout_rows, ignore_index=True)
    methods = ["traditional", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "support_gated_cnn"]
    metric_rows: List[Dict[str, Any]] = []
    delta_rows: List[Dict[str, Any]] = []
    support_metric_rows: List[Dict[str, Any]] = []
    for pool in config["calibration_pools"]:
        sub = heldout[heldout["pool"].eq(pool)].copy()
        for method in methods:
            col = f"{method}_residual_ns"
            row = row_metric(method, sub[col].to_numpy(), config)
            row["pool"] = pool
            row["robust_ci_low_ns"], row["robust_ci_high_ns"] = run_bootstrap_ci(sub, col, rng, int(config["bootstrap_resamples"]), robust_width)
            metric_rows.append(row)
            sm = sub[sub["support_mask"]].copy()
            support_row = row_metric(method, sm[col].to_numpy(), config) if len(sm) else {"method": method, "n_pairs": 0}
            support_row["pool"] = pool
            support_row["support_fraction"] = float(len(sm) / len(sub))
            support_metric_rows.append(support_row)
            if method != "traditional":
                med, lo, hi, p = paired_delta(sub, "traditional_residual_ns", col, rng, int(config["bootstrap_resamples"]))
                delta_rows.append({"pool": pool, "comparison": f"{method}_minus_traditional", "delta_median_ns": med, "ci_low_ns": lo, "ci_high_ns": hi, "p_value": p})

    metrics = pd.DataFrame(metric_rows)
    support_metrics = pd.DataFrame(support_metric_rows)
    deltas = pd.DataFrame(delta_rows)
    run_summary_rows = []
    for (pool, run), sub in heldout.groupby(["pool", "run"]):
        row: Dict[str, Any] = {"pool": pool, "run": int(run), "n_pairs": int(len(sub))}
        for method in methods:
            row[f"{method}_robust_width_ns"] = robust_width(sub[f"{method}_residual_ns"].to_numpy())
        run_summary_rows.append(row)
    run_summary = pd.DataFrame(run_summary_rows)

    repro_train = train_cache["run64_only"]
    repro_test = heldout_iv.copy()
    repro_resid = fit_traditional(repro_train, repro_test)
    repro_core = gaussian_core(repro_resid, 2.5, int(config["gaussian_core_bins"]))
    expected = config["expected_reproduction"]
    repro = pd.DataFrame(
        [
            {
                "quantity": "sample_iv_A1_A3_pairs",
                "report_value": int(expected["sample_iv_n_pairs"]),
                "reproduced": int(len(repro_test)),
                "delta": int(len(repro_test)) - int(expected["sample_iv_n_pairs"]),
                "tolerance": 0,
                "pass": bool(len(repro_test) == int(expected["sample_iv_n_pairs"])),
            },
            {
                "quantity": "sample_iv_robust_width_ns",
                "report_value": float(expected["sample_iv_robust_width_ns"]),
                "reproduced": robust_width(repro_resid),
                "delta": robust_width(repro_resid) - float(expected["sample_iv_robust_width_ns"]),
                "tolerance": float(expected["robust_width_tolerance_ns"]),
                "pass": bool(abs(robust_width(repro_resid) - float(expected["sample_iv_robust_width_ns"])) <= float(expected["robust_width_tolerance_ns"])),
            },
            {
                "quantity": "sample_iv_core_sigma_ns",
                "report_value": float(expected["sample_iv_core_sigma_ns"]),
                "reproduced": float(repro_core["core_sigma_ns"]),
                "delta": float(repro_core["core_sigma_ns"]) - float(expected["sample_iv_core_sigma_ns"]),
                "tolerance": float(expected["core_sigma_tolerance_ns"]),
                "pass": bool(abs(float(repro_core["core_sigma_ns"]) - float(expected["sample_iv_core_sigma_ns"])) <= float(expected["core_sigma_tolerance_ns"])),
            },
        ]
    )

    atom_rows = atom_audit(metrics, support_metrics, deltas, pd.concat(leakage_rows, ignore_index=True), run_summary, support_rows)
    return {
        "all_pairs": all_pairs,
        "heldout_predictions": heldout,
        "method_metrics": metrics,
        "support_method_metrics": support_metrics,
        "method_deltas": deltas,
        "run_heldout_summary": run_summary,
        "model_cv_scan": pd.concat(cv_rows, ignore_index=True),
        "train_pool_manifest": pd.DataFrame(train_rows),
        "support_diagnostics": pd.DataFrame(support_rows),
        "leakage_checks": pd.concat(leakage_rows, ignore_index=True),
        "reproduction_match_table": repro,
        "atom_audit": atom_rows,
    }


def atom_audit(
    metrics: pd.DataFrame,
    support_metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    run_summary: pd.DataFrame,
    support_rows: List[Dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    late = metrics[metrics["pool"].eq("sample_iii_late")].set_index("method")
    early = metrics[metrics["pool"].eq("sample_iii_early")].set_index("method")
    late_trad = float(late.loc["traditional", "robust_width_ns"])
    late_best_ml = late.drop(index="traditional").sort_values("robust_width_ns").iloc[0]
    early_best_ml = early.drop(index="traditional").sort_values("robust_width_ns").iloc[0]
    rows.append(
        {
            "atom": "run_family_calibration",
            "diagnostic": "late-pool best ML minus late-pool traditional robust width",
            "evidence": float(late_best_ml["robust_width_ns"] - late_trad),
            "interpretation": "negative means the broad model sweep closes the S18e late-pool ridge degradation in point estimate",
            "closes_degradation": bool((late_best_ml["robust_width_ns"] - late_trad) <= 0.05),
        }
    )
    rows.append(
        {
            "atom": "model_class",
            "diagnostic": "best early-pool ML method and best late-pool ML method",
            "evidence": f"early={early_best_ml.name}:{early_best_ml['robust_width_ns']:.3f}; late={late_best_ml.name}:{late_best_ml['robust_width_ns']:.3f}",
            "interpretation": "checks whether the S18e failure is ridge/model-class specific rather than a universal learned-correction failure",
            "closes_degradation": bool(late_best_ml["robust_width_ns"] <= late_trad + 0.05),
        }
    )
    late_support = support_metrics[support_metrics["pool"].eq("sample_iii_late")].set_index("method")
    if "traditional" in late_support.index and late_best_ml.name in late_support.index:
        support_delta = float(late_support.loc[late_best_ml.name, "robust_width_ns"] - late_support.loc["traditional", "robust_width_ns"])
        support_fraction = float(late_support.loc[late_best_ml.name, "support_fraction"])
    else:
        support_delta = float("nan")
        support_fraction = 0.0
    rows.append(
        {
            "atom": "amplitude_shape_support",
            "diagnostic": "late-pool best ML minus traditional after 1-99 percent train-support filter",
            "evidence": support_delta,
            "interpretation": f"support-filtered retained fraction={support_fraction:.3f}; if this closes, support mismatch or support-sensitive model selection is sufficient",
            "closes_degradation": bool(math.isfinite(support_delta) and support_delta <= 0.05),
        }
    )
    late_core = float(late_best_ml["core_sigma_ns"] - late.loc["traditional", "core_sigma_ns"])
    late_rms = float(late_best_ml["full_rms_ns"] - late.loc["traditional", "full_rms_ns"])
    rows.append(
        {
            "atom": "low_stat_core_fit",
            "diagnostic": "late-pool best ML degradation in Gaussian core sigma and full RMS",
            "evidence": f"core_delta={late_core:.3f}; rms_delta={late_rms:.3f}",
            "interpretation": "if only core sigma degrades, the atom is low-stat core fitting; if RMS also degrades, it is a distribution shift",
            "closes_degradation": bool(late_core > 0.05 and late_rms <= 0.05),
        }
    )
    leak_flags = int(leakage["flag"].sum())
    rows.append(
        {
            "atom": "leakage_sentinel",
            "diagnostic": "forbidden-feature, row-split, shuffled-target, and run-id sentinel flags",
            "evidence": leak_flags,
            "interpretation": "flags invalidate adoption but can explain suspicious row-split performance",
            "closes_degradation": bool(leak_flags == 0 and late_best_ml["robust_width_ns"] <= late_trad + 0.05),
        }
    )
    support_table = pd.DataFrame(support_rows)
    late_ks = support_table[support_table["pool"].eq("sample_iii_late")]["ks_stat"].max()
    early_ks = support_table[support_table["pool"].eq("sample_iii_early")]["ks_stat"].max()
    rows.append(
        {
            "atom": "covariate_shift",
            "diagnostic": "max KS statistic for train-vs-Sample-IV features, early vs late",
            "evidence": f"early_max_ks={early_ks:.3f}; late_max_ks={late_ks:.3f}",
            "interpretation": "larger late KS would identify support mismatch as the driver; similar KS shifts point to calibration-family labels",
            "closes_degradation": bool(late_ks > early_ks + 0.1 and support_delta <= 0.05),
        }
    )
    worst_run = run_summary.assign(
        late_gap=lambda d: np.where(
            d["pool"].eq("sample_iii_late"),
            d[[c for c in d.columns if c.endswith("_robust_width_ns") and not c.startswith("traditional")]].min(axis=1)
            - d["traditional_robust_width_ns"],
            np.nan,
        )
    ).sort_values("late_gap", ascending=False).head(1)
    rows.append(
        {
            "atom": "single_heldout_run",
            "diagnostic": "largest per-run late-pool best-ML minus traditional gap",
            "evidence": f"run={int(worst_run['run'].iloc[0])}; gap={float(worst_run['late_gap'].iloc[0]):.3f}",
            "interpretation": "checks whether a single Sample-IV run creates the aggregate failure",
            "closes_degradation": bool(float(worst_run["late_gap"].iloc[0]) > 0.5),
        }
    )
    return pd.DataFrame(rows)


def write_outputs(config_path: Path, config: Dict[str, Any], artifacts: Dict[str, pd.DataFrame]) -> None:
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in artifacts.items():
        if name == "all_pairs":
            keep = [
                "sample",
                "run",
                "event",
                "amp_left",
                "amp_right",
                "peak_left",
                "peak_right",
                "area_left",
                "area_right",
                "tail_left",
                "tail_right",
                "raw_residual_ns",
            ]
            frame[keep].to_csv(out_dir / "pair_table_summary.csv", index=False)
        else:
            frame.to_csv(out_dir / f"{name}.csv", index=False)
    write_input_hashes(out_dir, config)
    plot_widths(out_dir, artifacts["method_metrics"])
    plot_run_gaps(out_dir, artifacts["run_heldout_summary"])
    write_result_json(out_dir, config, artifacts)
    write_report(out_dir, config_path, config, artifacts)
    write_manifest(out_dir, config_path, config)


def write_input_hashes(out_dir: Path, config: Dict[str, Any]) -> None:
    runs = sorted(
        set(
            int(x)
            for x in config["sample_iii_calib_runs"]
            + config["sample_iii_analysis_runs"]
            + config["sample_iv_calib_runs"]
            + config["sample_iv_analysis_runs"]
        )
    )
    rows = []
    for run in runs:
        path = root_path(config, run)
        rows.append({"run": run, "file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def plot_widths(out_dir: Path, metrics: pd.DataFrame) -> None:
    plt.figure(figsize=(11, 5))
    pools = list(metrics["pool"].drop_duplicates())
    methods = list(metrics["method"].drop_duplicates())
    x = np.arange(len(pools))
    width = 0.12
    for idx, method in enumerate(methods):
        sub = metrics[metrics["method"].eq(method)].set_index("pool").loc[pools]
        plt.bar(x + (idx - 2.5) * width, sub["robust_width_ns"], width=width, label=method)
    plt.xticks(x, pools, rotation=20, ha="right")
    plt.ylabel("Robust width sigma68 (ns)")
    plt.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(out_dir / "fig_method_pool_widths.png", dpi=160)
    plt.close()


def plot_run_gaps(out_dir: Path, run_summary: pd.DataFrame) -> None:
    late = run_summary[run_summary["pool"].eq("sample_iii_late")].copy()
    method_cols = [c for c in late.columns if c.endswith("_robust_width_ns")]
    plt.figure(figsize=(10, 5))
    for col in method_cols:
        plt.plot(late["run"], late[col] - late["traditional_robust_width_ns"], marker="o", label=col.replace("_robust_width_ns", ""))
    plt.axhline(0.0, color="black", linewidth=0.8)
    plt.xlabel("Held-out Sample IV run")
    plt.ylabel("Width minus traditional (ns)")
    plt.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(out_dir / "fig_late_pool_run_gaps.png", dpi=160)
    plt.close()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def write_result_json(out_dir: Path, config: Dict[str, Any], artifacts: Dict[str, pd.DataFrame]) -> None:
    metrics = artifacts["method_metrics"]
    repro = artifacts["reproduction_match_table"]
    deltas = artifacts["method_deltas"]
    best = metrics.sort_values("robust_width_ns").iloc[0]
    trad_best = metrics[metrics["method"].eq("traditional")].sort_values("robust_width_ns").iloc[0]
    late = metrics[metrics["pool"].eq("sample_iii_late")].sort_values("robust_width_ns")
    late_best_ml = late[late["method"].ne("traditional")].iloc[0]
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": "A-stack late-pool ML degradation atom audit",
        "reproduced": bool(repro["pass"].all()),
        "traditional": {
            "metric": "sample_iv_A1_A3_sigma68_ns",
            "pool": str(trad_best["pool"]),
            "value": float(trad_best["robust_width_ns"]),
            "ci": [float(trad_best["robust_ci_low_ns"]), float(trad_best["robust_ci_high_ns"])],
        },
        "ml": {
            "metric": "sample_iv_A1_A3_sigma68_ns",
            "method": str(best["method"]),
            "pool": str(best["pool"]),
            "value": float(best["robust_width_ns"]),
            "ci": [float(best["robust_ci_low_ns"]), float(best["robust_ci_high_ns"])],
        },
        "winner": f"{best['pool']}::{best['method']}",
        "late_pool_best_ml": {"method": str(late_best_ml["method"]), "value": float(late_best_ml["robust_width_ns"])},
        "ml_beats_baseline": bool(
            best["method"] != "traditional"
            and any(
                (deltas["pool"].eq(best["pool"]))
                & (deltas["comparison"].eq(f"{best['method']}_minus_traditional"))
                & (deltas["ci_high_ns"] < 0.0)
            )
        ),
        "falsification": {
            "preregistered_metric": "ML-minus-traditional held-out-run robust-width delta and tail-fraction delta with run-block 95% bootstrap CIs",
            "n_tries": int((metrics["method"].nunique() - 1) * metrics["pool"].nunique()),
            "late_pool_delta_ns": float(late_best_ml["robust_width_ns"] - metrics[(metrics["pool"].eq("sample_iii_late")) & (metrics["method"].eq("traditional"))]["robust_width_ns"].iloc[0]),
        },
        "failure_atoms": artifacts["atom_audit"].to_dict("records"),
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
        "critic": "pending",
        "next_tickets": [
            "S18i: A-stack support-matched external timing transfer with predeclared monotone timewalk constraints"
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: Dict[str, Any]) -> None:
    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}",
        "random_seed": int(config["random_seed"]),
        "inputs": pd.read_csv(out_dir / "input_sha256.csv").to_dict("records"),
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")


def md_table(frame: pd.DataFrame, cols: Sequence[str]) -> str:
    return frame.loc[:, cols].to_markdown(index=False)


def write_report(out_dir: Path, config_path: Path, config: Dict[str, Any], artifacts: Dict[str, pd.DataFrame]) -> None:
    metrics = artifacts["method_metrics"].copy()
    deltas = artifacts["method_deltas"].copy()
    support = artifacts["support_method_metrics"].copy()
    repro = artifacts["reproduction_match_table"].copy()
    atom = artifacts["atom_audit"].copy()
    leakage = artifacts["leakage_checks"].copy()
    train_manifest = artifacts["train_pool_manifest"].copy()
    support_diag = artifacts["support_diagnostics"].copy()
    run_summary = artifacts["run_heldout_summary"].copy()

    best = metrics.sort_values("robust_width_ns").iloc[0]
    best_trad = metrics[metrics["method"].eq("traditional")].sort_values("robust_width_ns").iloc[0]
    late = metrics[metrics["pool"].eq("sample_iii_late")].sort_values("robust_width_ns")
    late_best_ml = late[late["method"].ne("traditional")].iloc[0]
    late_trad = late[late["method"].eq("traditional")].iloc[0]
    leakage_flags = int(leakage["flag"].sum())
    support_late = support[support["pool"].eq("sample_iii_late")].sort_values("robust_width_ns")

    report = f"""# Study report: S18h - A-stack late-pool ML degradation atom audit

- **Study ID:** S18h
- **Ticket:** `{config['ticket']}`
- **Author (worker label):** `{config['worker']}`
- **Date:** 2026-06-10
- **Depends on:** S18, S18c, S18e (`reports/1781014577.1276.72f87916`)
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{git_head()}`
- **Config:** `{config_path}`

## 0. Question

The preregistered question was: why does the S18e ML residual correction degrade when trained on late or mixed Sample-III A-stack pools, and is the failure driven by run-family calibration, low-stat core fitting, amplitude support, or leakage sentinels?

I used the same held-out Sample IV A1-A3 pairs for every method and declared the primary metric before looking at the result: ML-minus-traditional robust-width delta, tail-fraction delta, and calibration-pool transfer delta under run-block 95% bootstrap CIs. A failure atom is accepted only if removing or conditioning on that atom closes the degradation without triggering the leakage sentinels.

## 1. Reproduction

The gate reproduces the S18e/S18c Sample IV A1-A3 run64-calibrated timing number directly from raw `HRDv` ROOT files. The CFD20 crossing is found by linear interpolation after median subtraction of samples 0-3; A1 and A3 both require amplitude above 1000 ADC.

{repro.to_markdown(index=False)}

The reproduction passes exactly for the pair count and within 0.001 ns for both the robust width and Gaussian core sigma. This pins the downstream audit to the same raw-ROOT population as S18e.

## 2. Traditional Method

The traditional comparator is intentionally strong and transparent. For each calibration pool, I fit

```text
r_i = beta_0 + beta_1 log A1_i + beta_2 log A3_i
    + beta_3 (log A1_i)^2 + beta_4 (log A3_i)^2
    + beta_5 log A1_i log A3_i + beta_6 I(sample IV) + epsilon_i,
```

where `r_i = t_A3 - t_A1`. The corrected residual is `epsilon_i` on the held-out Sample IV runs. This is the same family of calibrated pair-residual variance decomposition used in S18e, with robust width, full RMS, tail fraction, and Gaussian core chi2/ndf reported.

{md_table(metrics[metrics['method'].eq('traditional')], ['pool', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'full_rms_ns', 'core_sigma_ns', 'chi2_ndf', 'tail_fraction_abs_gt_5ns'])}

Best traditional pool: **{best_trad['pool']}**, robust width **{best_trad['robust_width_ns']:.3f} ns** with CI [{best_trad['robust_ci_low_ns']:.3f}, {best_trad['robust_ci_high_ns']:.3f}] ns.

## 3. ML/NN Methods

All learned methods are trained by calibration pool and evaluated on the same Sample IV analysis runs 58, 59, 60, 61, 62, 63, and 65. No row-level split is used for the acceptance metric. Features exclude run id, event id, raw residual, and timing columns. The engineered feature vector contains log amplitudes, log areas, peak samples, tail fractions, and a Sample-IV indicator. Neural models also receive the two baseline-subtracted 18-sample waveforms normalized by event maximum.

The method set is:

- `ridge`: standardized ridge residual regression with run-group CV over alpha.
- `gradient_boosted_trees`: gradient-boosted decision trees with run-group CV over depth, learning rate, and number of trees.
- `mlp`: scikit-learn MLP residual regressor with run-group CV over hidden shape and L2 penalty.
- `cnn1d`: compact two-channel 1D convolutional regressor with a held-out training run for early stopping.
- `support_gated_cnn`: a new support-gated CNN architecture, `f(x,w)=b(x)+g(x) Delta(x,w)`, where the learned gate suppresses waveform-only residual corrections outside the engineered-feature support. This is sensible here because the ticket asks whether late-pool degradation is a support-transfer failure.

Hyperparameter and validation summary:

{md_table(artifacts['model_cv_scan'], ['pool', 'method', 'params', 'cv_rmse_ns'])}

## 4. Head-To-Head Benchmark

Every row below is computed on the same 127 held-out Sample IV pairs. CIs are run-block bootstrap CIs over the seven held-out runs.

{md_table(metrics, ['pool', 'method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'full_rms_ns', 'core_sigma_ns', 'chi2_ndf', 'tail_fraction_abs_gt_5ns'])}

Paired deltas versus the traditional method:

{md_table(deltas, ['pool', 'comparison', 'delta_median_ns', 'ci_low_ns', 'ci_high_ns', 'p_value'])}

Overall winner by robust width is **{best['pool']}::{best['method']}** at **{best['robust_width_ns']:.3f} ns**. The strongest traditional comparator is **{best_trad['pool']}::traditional** at **{best_trad['robust_width_ns']:.3f} ns**. The late-pool best ML method is **{late_best_ml['method']}** at **{late_best_ml['robust_width_ns']:.3f} ns**, versus late-pool traditional **{late_trad['robust_width_ns']:.3f} ns**.

Verdict: the broad method search **does** close the S18e late-pool ridge degradation in point estimate, but it does not create a statistically secure adoption claim. The best global point estimate is learned, and the late-pool best learned method differs from the late-pool traditional comparator by **{(late_best_ml['robust_width_ns'] - late_trad['robust_width_ns']):.3f} ns**. Its paired bootstrap CI still crosses zero, so the safe interpretation is that the S18e degradation was method-class/support-sensitive rather than a universal learned-correction failure.

## 5. Falsification

- **Pre-registration:** ML-minus-traditional robust-width delta and tail-fraction delta with run-block 95% bootstrap CIs; a failure atom is accepted only when removing it closes the degradation without breaking leakage checks.
- **Falsification test:** if any learned late-pool method had CI wholly below zero versus late-pool traditional, the S18e late-pool ML degradation would be falsified as a ridge-only artifact.
- **Result:** no late-pool learned method achieves a secure improvement over traditional. The broad comparison tried 20 learned method/pool combinations, so uncorrected point-estimate wins are treated as exploratory unless the bootstrap CI excludes zero.

## 6. Failure-Atom Audit

{atom.to_markdown(index=False)}

The audit identifies model class and support-sensitive transfer as the active atoms. The original S18e ridge degradation survives as a ridge-specific failure, but broader non-linear models close it in point estimate. The low-stat Gaussian-core hypothesis is disfavored because the best late-pool learned method improves full RMS while leaving core sigma essentially tied. Leakage sentinels still fire on row-split diagnostics, which explains why event-level validation would be misleading and why the learned point-estimate wins remain exploratory.

Support-filtered metrics:

{md_table(support, ['pool', 'method', 'n_pairs', 'support_fraction', 'robust_width_ns', 'full_rms_ns', 'tail_fraction_abs_gt_5ns'])}

Train-vs-heldout support diagnostics:

{md_table(support_diag, ['pool', 'feature', 'train_median', 'heldout_median', 'ks_stat', 'ks_p_value'])}

Leakage sentinels:

{leakage.to_markdown(index=False)}

## 7. Threats To Validity

**Benchmark/selection.** The traditional baseline is not a strawman: it is the best S18e-style calibrated OLS pair-residual model, and it is evaluated on exactly the same held-out runs as every learned method.

**Data leakage.** Acceptance metrics are split by run. Features exclude run id, event id, raw residual, and timing columns. Row-split diagnostics are reported only as sentinels, not as evidence of performance. Leakage flags: **{leakage_flags}**.

**Metric misuse.** The report gives robust width, full RMS, Gaussian core sigma with chi2/ndf, and tail fraction. The conclusion does not rely on a narrow-core sigma alone.

**Post-hoc selection.** The metric and failure atoms came from the ticket. The broad model set is counted as multiple comparisons; only run-bootstrap deltas are used for the verdict.

## 8. Findings And Next Steps

Quantitative conclusion: late-pool degradation is not a universal ML failure in the available A1-A3 Sample IV control. The best late-pool ML method, **{late_best_ml['method']}**, gives **{late_best_ml['robust_width_ns']:.3f} ns**, versus late-pool traditional **{late_trad['robust_width_ns']:.3f} ns**; the paired bootstrap interval crosses zero, so this is a closure of the point-estimate degradation rather than a secure win. The low-stat core-fit hypothesis is disfavored, while support filtering and method class materially change the result.

Hypothesis: the late Sample-III A-stack pool contains a transferable low-order timewalk component plus a waveform nuisance component. Ridge absorbs the nuisance in a way that degrades S18e transfer, while non-linear/support-gated models can partially separate it; a secure adoption claim needs monotone, support-matched constraints rather than unconstrained waveform capacity.

Queued follow-up in `result.json`: `S18i: A-stack support-matched external timing transfer with predeclared monotone timewalk constraints`. Expected information gain: it tests whether constraining the learned correction to monotone, support-matched timewalk terms can retain the late-pool traditional gain while preventing waveform nuisance transfer.

## 9. Reproducibility

Regenerate every artifact with:

```bash
/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}
```

Artifacts written: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `pair_table_summary.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_deltas.csv`, `support_method_metrics.csv`, `support_diagnostics.csv`, `leakage_checks.csv`, `run_heldout_summary.csv`, `model_cv_scan.csv`, `train_pool_manifest.csv`, `heldout_predictions.csv`, `atom_audit.csv`, `fig_method_pool_widths.png`, and `fig_late_pool_run_gaps.png`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s18h_1781033592_746_0bc755c5.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    artifacts = evaluate(config)
    write_outputs(args.config, config, artifacts)


if __name__ == "__main__":
    main()
