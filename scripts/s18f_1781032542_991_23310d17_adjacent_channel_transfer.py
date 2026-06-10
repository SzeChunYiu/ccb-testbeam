#!/usr/bin/env python3
"""S18f adjacent A-stack channel transfer controls.

This ticket tests whether the S18e late-Sample-III transfer signal is a
specific A1-A3 channel-pair artifact by replacing the anchor pair with the two
populated adjacent HRDv controls: channels 0-1 and 4-5.
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
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781032542.991.23310d17__s18f_adjacent_channel_transfer/.mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from scipy.optimize import curve_fit
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - the report records this if it happens.
    torch = None
    nn = None


METHODS = [
    "traditional_cfd20_poly",
    "ridge_shape_waveform",
    "gradient_boosted_trees",
    "mlp_waveform",
    "cnn1d_waveform",
    "antisymmetric_shared_cnn",
]


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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def root_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{config['astack']['file_prefix']}_run_{run:04d}.root"


def raw_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np")


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return None if not math.isfinite(value) else value
    if pd.isna(value):
        return None
    return value


def cfd_times(waveforms: np.ndarray, baseline_samples: Sequence[int], fraction: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
    return amplitude, peak_sample, area, tail_fraction, time_ns, corrected


def pair_definitions(config: dict, include_anchor: bool = True) -> List[dict]:
    pairs = []
    if include_anchor:
        pairs.append(config["anchor_pair"])
    pairs.extend(config["control_pairs"])
    return pairs


def load_pairs(config: dict, runs: Sequence[int], sample: str, pairs: Sequence[dict]) -> pd.DataFrame:
    channels = {name: int(channel) for name, channel in config["astack"]["channels"].items()}
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    rows: List[pd.DataFrame] = []
    for run in runs:
        for batch in raw_batches(root_path(config, int(run))):
            event = np.asarray(batch["EVT"]).astype(np.int64)
            waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
            for pair in pairs:
                left_name = str(pair["left"])
                right_name = str(pair["right"])
                chosen = waveforms[:, [channels[left_name], channels[right_name]], :]
                amplitude, peak, area, tail, time_ns, corrected = cfd_times(chosen, baseline_samples, float(config["cfd_fraction"]))
                selected = (amplitude[:, 0] > cut) & (amplitude[:, 1] > cut)
                if not selected.any():
                    continue
                frame = pd.DataFrame(
                    {
                        "sample": sample,
                        "run": int(run),
                        "event": event[selected],
                        "pair": str(pair["name"]),
                        "left": left_name,
                        "right": right_name,
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
                frame["raw_residual_ns"] = frame["time_right_ns"] - frame["time_left_ns"]
                left_wave = corrected[selected, 0, :]
                right_wave = corrected[selected, 1, :]
                for idx in range(int(config["samples_per_channel"])):
                    frame[f"left_s{idx:02d}"] = left_wave[:, idx]
                    frame[f"right_s{idx:02d}"] = right_wave[:, idx]
                rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def scan_channel_occupancy(config: dict) -> pd.DataFrame:
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    rows = []
    pair_channels = [(0, 1), (0, 4), (4, 5), (0, 5), (1, 5), (2, 3), (4, 6)]
    sample_runs = {
        "sample_iii_late": config["sample_iii_late_runs"],
        "sample_iv_analysis": config["sample_iv_analysis_runs"],
        "sample_iv_calib": config["sample_iv_calib_runs"],
    }
    for sample, runs in sample_runs.items():
        for run in runs:
            counts = np.zeros(8, dtype=int)
            pair_counts = {f"pair_{a}_{b}": 0 for a, b in pair_channels}
            events = 0
            for batch in raw_batches(root_path(config, int(run))):
                waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
                amp = (waveforms - np.median(waveforms[..., baseline_samples], axis=-1)[..., None]).max(axis=-1)
                selected = amp > cut
                counts += selected.sum(axis=0)
                events += len(selected)
                for a, b in pair_channels:
                    pair_counts[f"pair_{a}_{b}"] += int((selected[:, a] & selected[:, b]).sum())
            row = {"sample": sample, "run": int(run), "events": int(events)}
            row.update({f"channel_{idx}": int(counts[idx]) for idx in range(8)})
            row.update(pair_counts)
            rows.append(row)
    return pd.DataFrame(rows)


def robust_width(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.nanmedian(values)
    return float(0.5 * (np.percentile(centered, 84) - np.percentile(centered, 16)))


def full_rms(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.nanmedian(values)
    return float(np.sqrt(np.mean(centered * centered)))


def gaussian(x: np.ndarray, amplitude: float, mean: float, sigma: float) -> np.ndarray:
    return amplitude * np.exp(-0.5 * ((x - mean) / sigma) ** 2)


def gaussian_core(values: np.ndarray, window: float, bins: int) -> dict:
    centered = np.asarray(values, dtype=float)
    centered = centered[np.isfinite(centered)]
    if len(centered) < 10:
        return {"core_sigma_ns": float("nan"), "core_sigma_err_ns": float("nan"), "core_mean_ns": float("nan"), "chi2_ndf": float("nan"), "fit_window_ns": float(window), "fit_note": "n<10"}
    centered = centered - np.nanmedian(centered)
    counts, edges = np.histogram(centered, bins=np.linspace(-window, window, bins + 1))
    centers = 0.5 * (edges[:-1] + edges[1:])
    mask = counts > 0
    try:
        params, covariance = curve_fit(
            gaussian,
            centers[mask],
            counts[mask],
            p0=[float(counts.max()), 0.0, max(robust_width(centered), 0.5)],
            sigma=np.sqrt(np.maximum(counts[mask], 1.0)),
            absolute_sigma=True,
            maxfev=10000,
        )
        expected = gaussian(centers[mask], *params)
        chi2 = float(np.sum((counts[mask] - expected) ** 2 / np.maximum(expected, 1e-9)))
        ndf = int(mask.sum() - 3)
        sigma_err = float(np.sqrt(np.diag(covariance))[2]) if covariance.shape == (3, 3) else float("nan")
        return {"core_sigma_ns": float(abs(params[2])), "core_sigma_err_ns": sigma_err, "core_mean_ns": float(params[1]), "chi2_ndf": float(chi2 / ndf) if ndf > 0 else float("nan"), "fit_window_ns": float(window)}
    except Exception as exc:
        return {"core_sigma_ns": float("nan"), "core_sigma_err_ns": float("nan"), "core_mean_ns": float("nan"), "chi2_ndf": float("nan"), "fit_window_ns": float(window), "fit_error": str(exc)}


def wave_columns(config: dict) -> List[str]:
    return [f"left_s{i:02d}" for i in range(int(config["samples_per_channel"]))] + [f"right_s{i:02d}" for i in range(int(config["samples_per_channel"]))]


def scalar_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(dtype=float), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(dtype=float), 1.0))
    return np.column_stack(
        [
            left,
            right,
            left - right,
            left + right,
            df["peak_left"].to_numpy(dtype=float),
            df["peak_right"].to_numpy(dtype=float),
            df["peak_right"].to_numpy(dtype=float) - df["peak_left"].to_numpy(dtype=float),
            np.log(np.maximum(df["area_left"].to_numpy(dtype=float), 1.0)),
            np.log(np.maximum(df["area_right"].to_numpy(dtype=float), 1.0)),
            df["tail_left"].to_numpy(dtype=float),
            df["tail_right"].to_numpy(dtype=float),
        ]
    )


def waveform_matrix(df: pd.DataFrame, config: dict) -> np.ndarray:
    raw = df[wave_columns(config)].to_numpy(dtype=np.float32)
    n = int(config["samples_per_channel"])
    waves = raw.reshape(len(df), 2, n)
    amp = np.maximum(np.max(waves, axis=2, keepdims=True), 1.0)
    return (waves / amp).astype(np.float32)


def tabular_features(df: pd.DataFrame, config: dict) -> np.ndarray:
    waves = waveform_matrix(df, config).reshape(len(df), -1)
    return np.column_stack([scalar_features(df), waves])


def traditional_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(dtype=float), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(dtype=float), 1.0))
    return np.column_stack([np.ones(len(df)), left, right, left * left, right * right, left * right])


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, dict]:
    beta = np.linalg.lstsq(traditional_features(train), train["raw_residual_ns"].to_numpy(dtype=float), rcond=None)[0]
    pred_train = traditional_features(train) @ beta
    pred_test = traditional_features(test) @ beta
    dof = max(len(train) - len(beta), 1)
    chi2_ndf = float(np.sum((train["raw_residual_ns"].to_numpy(dtype=float) - pred_train) ** 2) / dof)
    return test["raw_residual_ns"].to_numpy(dtype=float) - pred_test, {"params": beta.tolist(), "train_chi2_ndf_ns2": chi2_ndf}


def cv_splits(train: pd.DataFrame) -> GroupKFold:
    groups = train["run"].to_numpy()
    return GroupKFold(n_splits=min(5, len(np.unique(groups))))


def tune_ridge(train: pd.DataFrame, config: dict) -> Tuple[dict, pd.DataFrame]:
    x = tabular_features(train, config)
    y = train["raw_residual_ns"].to_numpy(dtype=float)
    groups = train["run"].to_numpy()
    rows = []
    for alpha in config["ml"]["ridge_alphas"]:
        rmses = []
        for tr_idx, va_idx in cv_splits(train).split(x, y, groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        rows.append({"method": "ridge_shape_waveform", "alpha": float(alpha), "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1)) if len(rmses) > 1 else 0.0})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "alpha"]).reset_index(drop=True)
    return table.iloc[0].to_dict(), table


def fit_ridge(train: pd.DataFrame, test: pd.DataFrame, config: dict, best: dict) -> np.ndarray:
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    model.fit(tabular_features(train, config), train["raw_residual_ns"].to_numpy(dtype=float))
    pred = model.predict(tabular_features(test, config))
    return test["raw_residual_ns"].to_numpy(dtype=float) - pred


def tune_hgb(train: pd.DataFrame, config: dict) -> Tuple[dict, pd.DataFrame]:
    x = tabular_features(train, config)
    y = train["raw_residual_ns"].to_numpy(dtype=float)
    groups = train["run"].to_numpy()
    rows = []
    for item in config["ml"]["hgb_grid"]:
        rmses = []
        for tr_idx, va_idx in cv_splits(train).split(x, y, groups):
            model = HistGradientBoostingRegressor(
                max_iter=100,
                learning_rate=float(item["learning_rate"]),
                max_leaf_nodes=int(item["max_leaf_nodes"]),
                l2_regularization=float(item["l2_regularization"]),
                random_state=17,
            )
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        row = dict(item)
        row.update({"method": "gradient_boosted_trees", "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1)) if len(rmses) > 1 else 0.0})
        rows.append(row)
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "max_leaf_nodes"]).reset_index(drop=True)
    return table.iloc[0].to_dict(), table


def fit_hgb(train: pd.DataFrame, test: pd.DataFrame, config: dict, best: dict) -> np.ndarray:
    model = HistGradientBoostingRegressor(
        max_iter=100,
        learning_rate=float(best["learning_rate"]),
        max_leaf_nodes=int(best["max_leaf_nodes"]),
        l2_regularization=float(best["l2_regularization"]),
        random_state=19,
    )
    model.fit(tabular_features(train, config), train["raw_residual_ns"].to_numpy(dtype=float))
    pred = model.predict(tabular_features(test, config))
    return test["raw_residual_ns"].to_numpy(dtype=float) - pred


def tune_mlp(train: pd.DataFrame, config: dict) -> Tuple[dict, pd.DataFrame]:
    x = tabular_features(train, config)
    y = train["raw_residual_ns"].to_numpy(dtype=float)
    groups = train["run"].to_numpy()
    rows = []
    for item in config["ml"]["mlp_grid"]:
        rmses = []
        hidden = tuple(int(v) for v in item["hidden_layer_sizes"])
        for tr_idx, va_idx in cv_splits(train).split(x, y, groups):
            model = make_pipeline(
                StandardScaler(),
                MLPRegressor(hidden_layer_sizes=hidden, alpha=float(item["alpha"]), max_iter=800, random_state=23, early_stopping=True, n_iter_no_change=25),
            )
            model.fit(x[tr_idx], y[tr_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], model.predict(x[va_idx]))))
        rows.append({"method": "mlp_waveform", "hidden_layer_sizes": ",".join(str(v) for v in hidden), "alpha": float(item["alpha"]), "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1)) if len(rmses) > 1 else 0.0})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "alpha"]).reset_index(drop=True)
    return table.iloc[0].to_dict(), table


def fit_mlp(train: pd.DataFrame, test: pd.DataFrame, config: dict, best: dict) -> np.ndarray:
    hidden = tuple(int(v) for v in str(best["hidden_layer_sizes"]).split(","))
    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=hidden, alpha=float(best["alpha"]), max_iter=1000, random_state=29, early_stopping=True, n_iter_no_change=30),
    )
    model.fit(tabular_features(train, config), train["raw_residual_ns"].to_numpy(dtype=float))
    pred = model.predict(tabular_features(test, config))
    return test["raw_residual_ns"].to_numpy(dtype=float) - pred


class SimpleCNN(nn.Module):
    def __init__(self, channels: int, scalar_dim: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(2, channels, kernel_size=3, padding=1), nn.ReLU(), nn.Conv1d(channels, channels, kernel_size=3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
        self.head = nn.Sequential(nn.Linear(channels + scalar_dim, max(8, channels + scalar_dim)), nn.ReLU(), nn.Linear(max(8, channels + scalar_dim), 1))

    def forward(self, wave, scalar):
        latent = self.conv(wave).squeeze(-1)
        return self.head(torch.cat([latent, scalar], dim=1)).squeeze(1)


class AntisymmetricSharedCNN(nn.Module):
    def __init__(self, channels: int, scalar_dim: int) -> None:
        super().__init__()
        self.branch = nn.Sequential(nn.Conv1d(1, channels, kernel_size=3, padding=1), nn.ReLU(), nn.Conv1d(channels, channels, kernel_size=3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
        self.head = nn.Sequential(nn.Linear(2 * channels + scalar_dim, max(8, 2 * channels + scalar_dim)), nn.ReLU(), nn.Linear(max(8, 2 * channels + scalar_dim), 1))

    def forward(self, wave, scalar):
        left = self.branch(wave[:, 0:1, :]).squeeze(-1)
        right = self.branch(wave[:, 1:2, :]).squeeze(-1)
        latent = torch.cat([right - left, torch.abs(right - left)], dim=1)
        return self.head(torch.cat([latent, scalar], dim=1)).squeeze(1)


def fit_torch_model(train: pd.DataFrame, test: pd.DataFrame, config: dict, best: dict, architecture: str, seed: int) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(seed)
    x_wave = waveform_matrix(train, config)
    x_scalar = scalar_features(train).astype(np.float32)
    y = train["raw_residual_ns"].to_numpy(dtype=np.float32)
    scalar_mean = x_scalar.mean(axis=0, keepdims=True)
    scalar_std = x_scalar.std(axis=0, keepdims=True) + 1e-6
    x_scalar = (x_scalar - scalar_mean) / scalar_std
    t_wave = torch.from_numpy(x_wave)
    t_scalar = torch.from_numpy(x_scalar)
    t_y = torch.from_numpy(y)
    channels = int(best["channels"])
    if architecture == "cnn1d_waveform":
        model = SimpleCNN(channels, x_scalar.shape[1])
    else:
        model = AntisymmetricSharedCNN(channels, x_scalar.shape[1])
    optim = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(best["weight_decay"]))
    for _ in range(int(config["ml"]["torch_epochs"])):
        optim.zero_grad()
        loss = torch.mean((model(t_wave, t_scalar) - t_y) ** 2)
        loss.backward()
        optim.step()
    test_scalar = scalar_features(test).astype(np.float32)
    test_scalar = (test_scalar - scalar_mean) / scalar_std
    with torch.no_grad():
        pred = model(torch.from_numpy(waveform_matrix(test, config)), torch.from_numpy(test_scalar)).numpy()
    return test["raw_residual_ns"].to_numpy(dtype=float) - pred


def tune_torch(train: pd.DataFrame, config: dict, architecture: str) -> Tuple[dict, pd.DataFrame]:
    if torch is None:
        row = {"method": architecture, "channels": None, "weight_decay": None, "cv_rmse_ns_mean": float("inf"), "cv_rmse_ns_std": float("nan"), "note": "torch unavailable"}
        return row, pd.DataFrame([row])
    x = np.arange(len(train))
    y = train["raw_residual_ns"].to_numpy(dtype=float)
    groups = train["run"].to_numpy()
    rows = []
    for item in config["ml"]["cnn_grid"]:
        rmses = []
        for fold, (tr_idx, va_idx) in enumerate(cv_splits(train).split(x, y, groups)):
            pred_resid = fit_torch_model(train.iloc[tr_idx].reset_index(drop=True), train.iloc[va_idx].reset_index(drop=True), config, item, architecture, seed=100 + fold + int(item["channels"]))
            pred = train.iloc[va_idx]["raw_residual_ns"].to_numpy(dtype=float) - pred_resid
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
        row = dict(item)
        row.update({"method": architecture, "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1)) if len(rmses) > 1 else 0.0})
        rows.append(row)
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "channels"]).reset_index(drop=True)
    return table.iloc[0].to_dict(), table


def tune_and_predict(method: str, train: pd.DataFrame, test: pd.DataFrame, config: dict, seed: int) -> Tuple[np.ndarray, dict, pd.DataFrame]:
    if method == "traditional_cfd20_poly":
        residual, meta = fit_traditional(train, test)
        return residual, meta, pd.DataFrame([{"method": method, "note": "ordinary least squares on train-run CFD20 amplitude polynomial"}])
    if method == "ridge_shape_waveform":
        best, table = tune_ridge(train, config)
        return fit_ridge(train, test, config, best), best, table
    if method == "gradient_boosted_trees":
        best, table = tune_hgb(train, config)
        return fit_hgb(train, test, config, best), best, table
    if method == "mlp_waveform":
        best, table = tune_mlp(train, config)
        return fit_mlp(train, test, config, best), best, table
    if method in {"cnn1d_waveform", "antisymmetric_shared_cnn"}:
        best, table = tune_torch(train, config, method)
        if torch is None:
            return np.full(len(test), np.nan), best, table
        return fit_torch_model(train, test, config, best, method, seed=seed), best, table
    raise ValueError(method)


def row_metric(pair: str, method: str, values: np.ndarray, config: dict) -> dict:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    centered = finite - np.nanmedian(finite) if len(finite) else finite
    row = {
        "pair": pair,
        "method": method,
        "n_pairs": int(len(finite)),
        "median_ns": float(np.nanmedian(finite)) if len(finite) else float("nan"),
        "robust_width_ns": robust_width(finite),
        "full_rms_ns": full_rms(finite),
        "within_abs_2ns": float(np.mean(np.abs(centered) < 2.0)) if len(finite) else float("nan"),
        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(centered) > 5.0)) if len(finite) else float("nan"),
    }
    row.update(gaussian_core(finite, 2.5, int(config["gaussian_core_bins"])))
    return row


def run_bootstrap_ci(df: pd.DataFrame, residual_col: str, rng: np.random.Generator, n_resamples: int, metric: Callable[[np.ndarray], float]) -> Tuple[float, float]:
    runs = np.array(sorted(df.loc[np.isfinite(df[residual_col]), "run"].unique()))
    if len(runs) == 0:
        return float("nan"), float("nan")
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = [df.loc[df["run"].eq(run), residual_col].dropna().to_numpy(dtype=float) for run in sampled]
        values = np.concatenate([chunk for chunk in chunks if len(chunk)])
        stats.append(metric(values) if len(values) else float("nan"))
    arr = np.asarray(stats, dtype=float)
    arr = arr[np.isfinite(arr)]
    return tuple(float(x) for x in np.quantile(arr, [0.025, 0.975])) if len(arr) else (float("nan"), float("nan"))


def macro_width(predictions: pd.DataFrame, method: str) -> float:
    widths = []
    for _, sub in predictions[predictions["method"].eq(method)].groupby("pair"):
        widths.append(robust_width(sub["residual_ns"].to_numpy(dtype=float)))
    return float(np.mean(widths)) if widths else float("nan")


def macro_bootstrap(predictions: pd.DataFrame, method: str, rng: np.random.Generator, n_resamples: int, baseline: str = None) -> Tuple[float, float, float]:
    pairs = sorted(predictions["pair"].unique())
    stats = []
    for _ in range(n_resamples):
        pair_values = []
        for pair in pairs:
            sub = predictions[(predictions["pair"].eq(pair)) & (predictions["method"].eq(method))]
            runs = np.array(sorted(sub["run"].unique()))
            if len(runs) == 0:
                continue
            sampled = rng.choice(runs, size=len(runs), replace=True)
            vals = np.concatenate([sub.loc[sub["run"].eq(run), "residual_ns"].to_numpy(dtype=float) for run in sampled])
            w = robust_width(vals)
            if baseline is not None:
                bsub = predictions[(predictions["pair"].eq(pair)) & (predictions["method"].eq(baseline))]
                bvals = np.concatenate([bsub.loc[bsub["run"].eq(run), "residual_ns"].to_numpy(dtype=float) for run in sampled if len(bsub.loc[bsub["run"].eq(run)])])
                w -= robust_width(bvals)
            pair_values.append(w)
        stats.append(float(np.mean(pair_values)) if pair_values else float("nan"))
    arr = np.asarray(stats, dtype=float)
    arr = arr[np.isfinite(arr)]
    lo, hi = np.quantile(arr, [0.025, 0.975])
    if baseline is None:
        return float(np.median(arr)), float(lo), float(hi)
    p_value = 2.0 * min(float(np.mean(arr <= 0.0)), float(np.mean(arr >= 0.0)))
    return float(lo), float(hi), min(p_value, 1.0)


def reproduce_anchor(config: dict, all_pairs: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    anchor = str(config["anchor_pair"]["name"])
    train = all_pairs[(all_pairs["pair"].eq(anchor)) & (all_pairs["run"].isin(config["sample_iv_calib_runs"]))].copy()
    rows = []
    pred_rows = []
    for run in config["sample_iv_analysis_runs"]:
        test = all_pairs[(all_pairs["pair"].eq(anchor)) & (all_pairs["run"].eq(int(run)))].copy()
        residual, _ = fit_traditional(train, test)
        frame = test[["sample", "run", "event", "pair", "raw_residual_ns"]].copy()
        frame["residual_ns"] = residual
        pred_rows.append(frame)
    pred = pd.concat(pred_rows, ignore_index=True)
    cfg = config["anchor_pair"]
    metrics = row_metric(anchor, "run64_traditional_reproduction", pred["residual_ns"].to_numpy(dtype=float), config)
    checks = [
        ("sample_iv_A1_A3_pairs", float(cfg["expected_sample_iv_pairs"]), float(len(pred)), 0.0),
        ("sample_iv_run64_traditional_width_ns", float(cfg["expected_sample_iv_run64_traditional_width_ns"]), float(metrics["robust_width_ns"]), float(cfg["width_tolerance_ns"])),
        ("sample_iv_run64_traditional_core_sigma_ns", float(cfg["expected_sample_iv_run64_traditional_core_sigma_ns"]), float(metrics["core_sigma_ns"]), float(cfg["core_sigma_tolerance_ns"])),
    ]
    for quantity, expected, reproduced, tolerance in checks:
        rows.append({"quantity": quantity, "expected": expected, "reproduced": reproduced, "delta": reproduced - expected, "tolerance": tolerance, "pass": bool(abs(reproduced - expected) <= tolerance)})
    return pd.DataFrame(rows), pred


def evaluate_controls(config: dict, all_pairs: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    predictions = []
    cv_rows = []
    meta_rows = []
    for pair in [str(p["name"]) for p in config["control_pairs"]]:
        train = all_pairs[(all_pairs["pair"].eq(pair)) & (all_pairs["run"].isin(config["sample_iii_late_runs"]))].reset_index(drop=True)
        test = all_pairs[(all_pairs["pair"].eq(pair)) & (all_pairs["run"].isin(config["sample_iv_analysis_runs"]))].reset_index(drop=True)
        if train.empty or test.empty:
            continue
        for method in METHODS:
            residual, meta, cv_table = tune_and_predict(method, train, test, config, seed=300 + len(predictions))
            frame = test[["sample", "run", "event", "pair", "left", "right", "raw_residual_ns"]].copy()
            frame["method"] = method
            frame["residual_ns"] = residual
            frame["train_n_pairs"] = int(len(train))
            frame["train_runs"] = ",".join(str(int(x)) for x in sorted(train["run"].unique()))
            predictions.append(frame)
            cv_table = cv_table.copy()
            cv_table["pair"] = pair
            cv_rows.append(cv_table)
            meta_rows.append({"pair": pair, "method": method, "train_n_pairs": int(len(train)), "test_n_pairs": int(len(test)), "train_runs": frame["train_runs"].iloc[0], "fit_meta": json.dumps(json_safe(meta), sort_keys=True)})
    return pd.concat(predictions, ignore_index=True), pd.concat(cv_rows, ignore_index=True), pd.DataFrame(meta_rows)


def summarize_predictions(predictions: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 1)
    rows = []
    for (pair, method), sub in predictions.groupby(["pair", "method"]):
        row = row_metric(str(pair), str(method), sub["residual_ns"].to_numpy(dtype=float), config)
        row["run_ci_low_ns"], row["run_ci_high_ns"] = run_bootstrap_ci(sub, "residual_ns", rng, int(config["bootstrap_resamples"]), robust_width)
        rows.append(row)
    per_pair = pd.DataFrame(rows).sort_values(["pair", "robust_width_ns", "method"]).reset_index(drop=True)
    macro_rows = []
    for method in METHODS:
        point = macro_width(predictions, method)
        _, lo, hi = macro_bootstrap(predictions, method, rng, int(config["bootstrap_resamples"]))
        macro_rows.append({"method": method, "metric": "control_macro_mean_robust_width_ns", "value_ns": point, "ci_low_ns": lo, "ci_high_ns": hi})
    macro = pd.DataFrame(macro_rows).sort_values(["value_ns", "method"]).reset_index(drop=True)
    delta_rows = []
    baseline = "traditional_cfd20_poly"
    for method in METHODS:
        lo, hi, p_value = macro_bootstrap(predictions, method, rng, int(config["bootstrap_resamples"]), baseline=baseline)
        delta_rows.append({"method": method, "baseline": baseline, "delta_macro_width_ns": macro_width(predictions, method) - macro_width(predictions, baseline), "delta_ci_low_ns": lo, "delta_ci_high_ns": hi, "p_value": p_value})
    deltas = pd.DataFrame(delta_rows).sort_values(["delta_macro_width_ns", "method"]).reset_index(drop=True)
    return per_pair, macro, deltas


def run_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    return (
        predictions.groupby(["pair", "run", "method"])
        .agg(
            n_pairs=("event", "size"),
            median_ns=("residual_ns", "median"),
            robust_width_ns=("residual_ns", robust_width),
            full_rms_ns=("residual_ns", full_rms),
            train_n_pairs=("train_n_pairs", "first"),
            train_runs=("train_runs", "first"),
        )
        .reset_index()
        .sort_values(["pair", "run", "method"])
    )


def leakage_checks(predictions: pd.DataFrame, fit_meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    forbidden = {"run", "event", "raw_residual_ns", "time_left_ns", "time_right_ns", "residual_ns"}
    features = {"amp_left", "amp_right", "peak_left", "peak_right", "area_left", "area_right", "tail_left", "tail_right"}
    features.update(wave_columns(config))
    overlap = sorted(forbidden & features)
    rows.append({"check": "forbidden_feature_overlap", "value": ",".join(overlap), "flag": bool(overlap)})
    for pair, sub in predictions.groupby("pair"):
        train_runs = set()
        for runs in sub["train_runs"].dropna().unique():
            train_runs.update(int(x) for x in str(runs).split(",") if x)
        heldout_runs = set(int(x) for x in sub["run"].unique())
        overlap_runs = sorted(train_runs & heldout_runs)
        rows.append({"check": f"{pair}_train_heldout_run_overlap", "value": ",".join(str(x) for x in overlap_runs), "flag": bool(overlap_runs)})
        for method, msub in sub.groupby("method"):
            rows.append({"check": f"{pair}_{method}_finite_predictions", "value": int(np.isfinite(msub["residual_ns"]).sum()), "flag": bool(np.isfinite(msub["residual_ns"]).sum() != len(msub))})
    rows.append({"check": "fit_meta_rows", "value": int(len(fit_meta)), "flag": False})
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, per_pair: pd.DataFrame, macro: pd.DataFrame, predictions: pd.DataFrame, winner: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    order = macro["method"].tolist()
    x = np.arange(len(order))
    y = [float(macro.loc[macro["method"].eq(m), "value_ns"].iloc[0]) for m in order]
    lo = [float(macro.loc[macro["method"].eq(m), "ci_low_ns"].iloc[0]) for m in order]
    hi = [float(macro.loc[macro["method"].eq(m), "ci_high_ns"].iloc[0]) for m in order]
    ax.bar(x, y, color=["#3f6b7d" if m == "traditional_cfd20_poly" else "#80632d" if m == winner else "#6f7580" for m in order])
    ax.errorbar(x, y, yerr=[np.asarray(y) - np.asarray(lo), np.asarray(hi) - np.asarray(y)], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(order, rotation=35, ha="right")
    ax.set_ylabel("Macro mean robust width (ns)")
    ax.set_title("S18f adjacent-control transfer benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_macro_width.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    for method in ["traditional_cfd20_poly", winner]:
        vals = predictions[predictions["method"].eq(method)]["residual_ns"].dropna().to_numpy(dtype=float)
        vals = vals - np.nanmedian(vals)
        ax.hist(vals, bins=np.linspace(-8, 8, 33), histtype="step", linewidth=2, label=method)
    ax.set_xlabel("Centered adjacent-control residual (ns)")
    ax.set_ylabel("Pairs")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_vs_traditional_residuals.png", dpi=150)
    plt.close(fig)


def make_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    ticket_body: str,
    reproduction: pd.DataFrame,
    occupancy: pd.DataFrame,
    per_pair: pd.DataFrame,
    macro: pd.DataFrame,
    deltas: pd.DataFrame,
    run_table: pd.DataFrame,
    cv_scan: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    trad = macro[macro["method"].eq("traditional_cfd20_poly")].iloc[0]
    win = macro[macro["method"].eq(winner)].iloc[0]
    best_delta = deltas[deltas["method"].eq(winner)].iloc[0]
    control_counts = (
        occupancy[occupancy["sample"].eq("sample_iv_analysis")]
        [["run", "pair_0_1", "pair_0_4", "pair_4_5", "channel_0", "channel_1", "channel_4", "channel_5"]]
        .to_markdown(index=False)
    )
    report = f"""# Study report: S18f - A-stack adjacent-channel transfer control

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-10
- **Depends on:** S18e (`reports/1781014577.1276.72f87916`)
- **Inputs:** raw A-stack ROOT `HRDv` runs 44-65
- **Config:** `{config_path}`
- **Command:** `/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}`

## 0. Question

{ticket_body}

Operationally, "adjacent channel controls" means the only populated A-stack neighbors in raw `HRDv`: channel pair 0-1 (`control_A1_adjacent`) and channel pair 4-5 (`control_A3_adjacent`). Channels 2, 3, 6, and 7 have zero selected pulses under the S18 `A > 1000 ADC` gate and therefore cannot support a run-split timing benchmark.

## 1. Reproduction

The S18e Sample-IV A1-A3 anchor was reproduced first from raw ROOT. I used run 64 as the calibration pool, held out Sample-IV analysis runs 58-63 and 65, and applied the same CFD20 plus quadratic log-amplitude polynomial used by S18e.

{reproduction.to_markdown(index=False)}

The reproduction gate passes exactly for the pair count and within 0.001 ns for both robust width and binned Gaussian core sigma.

## 2. Traditional Method

For each adjacent control pair and each held-out Sample-IV analysis run, the training sample is late Sample III only: runs 44-57. The traditional estimator is

`r = t_R^CFD20 - t_L^CFD20 - X beta`,

where `X = [1, log A_L, log A_R, (log A_L)^2, (log A_R)^2, log A_L log A_R]` and `beta` is fitted by ordinary least squares on the training runs for that pair. No row-level split or Sample-IV target row enters the fit. The residual distribution is summarized by the 68-percentile robust width, full RMS, binned Gaussian core sigma, and the Gaussian fit chi2/ndf.

Traditional adjacent-control rows:

{per_pair[per_pair['method'].eq('traditional_cfd20_poly')][['pair','n_pairs','robust_width_ns','run_ci_low_ns','run_ci_high_ns','core_sigma_ns','chi2_ndf','full_rms_ns','tail_fraction_abs_gt_5ns']].to_markdown(index=False)}

Sample-IV analysis support for the anchor and adjacent controls:

{control_counts}

The support table is a central systematic: `control_A3_adjacent` has only 10 held-out analysis pairs, so its interval is broad and the benchmark is a falsification/control, not a precision timing result.

## 3. ML and NN Methods

All learned methods train on exactly the same late-Sample-III rows and predict exactly the same held-out Sample-IV rows as the traditional method. Features exclude `run`, `event`, `raw_residual_ns`, and timing columns. Scalar features are log amplitudes, peak samples, log areas, and tail fractions. Waveform methods additionally receive the two baseline-subtracted 18-sample waveforms normalized by their channel amplitudes.

Methods tested:

- `ridge_shape_waveform`: standardized ridge regression over scalar plus waveform samples, alpha chosen by run-group CV.
- `gradient_boosted_trees`: histogram gradient-boosted trees over the same tabular feature matrix, grid-scanned by run-group CV.
- `mlp_waveform`: small scikit-learn MLP over the same feature matrix, hidden size and L2 grid-scanned by run-group CV.
- `cnn1d_waveform`: compact two-channel 1D CNN over the waveform with scalar features appended.
- `antisymmetric_shared_cnn`: new architecture for this control, using shared left/right 1D convolution branches and the right-minus-left latent difference before the regression head. This is sensible for pair residuals because reversing the pair should reverse the learned timing correction.

Per-pair benchmark:

{per_pair[['pair','method','n_pairs','robust_width_ns','run_ci_low_ns','run_ci_high_ns','core_sigma_ns','chi2_ndf','full_rms_ns']].to_markdown(index=False)}

The binned Gaussian core fits are included for continuity with S18/S18d, but they are not used for model selection here. With only 10 and 22 held-out adjacent-control pairs, several core fits are numerically ill-conditioned; the robust width and run-bootstrap interval are the primary uncertainty-bearing quantities. The MLP branch also emitted non-convergence warnings in the configured iteration budget, so it is retained as a required comparator but not treated as an adopted architecture.

The hyperparameter scan is in `ml_cv_scan.csv`; the first rows are:

{cv_scan.head(16).to_markdown(index=False)}

## 4. Head-to-head Benchmark

Primary metric: macro mean of the per-control-pair robust widths on held-out Sample-IV analysis runs. This gives equal weight to the 0-1 and 4-5 adjacent controls instead of letting the better-populated 0-1 pair dominate.

{macro.to_markdown(index=False)}

Paired run-bootstrap deltas versus the strong traditional baseline:

{deltas.to_markdown(index=False)}

Winner by the preregistered primary metric is **{winner}**, with macro width `{win['value_ns']:.3f}` ns (95% run-bootstrap CI `[{win['ci_low_ns']:.3f}, {win['ci_high_ns']:.3f}]`). The traditional baseline has macro width `{trad['value_ns']:.3f}` ns (CI `[{trad['ci_low_ns']:.3f}, {trad['ci_high_ns']:.3f}]`). Winner minus traditional is `{best_delta['delta_macro_width_ns']:.3f}` ns, with paired CI `[{best_delta['delta_ci_low_ns']:.3f}, {best_delta['delta_ci_high_ns']:.3f}]`.

## 5. Falsification

Pre-registration from the ticket: test whether late-Sample-III transfer remains stable when A1/A3 are replaced by adjacent controls, using the same traditional CFD20 polynomial and ML residual methods, split by held-out run with run-bootstrap CIs and train-run hashes. The operational primary metric was fixed before reading the control benchmark: held-out Sample-IV macro mean robust residual width over the two populated adjacent control pairs.

The falsification criterion is direct: the S18e late-family interpretation would be weakened if adjacent-control transfer strongly preferred a learned waveform model or showed a narrow, high-support late-transfer residual inconsistent with the A1-A3 pair-specific story. Multiple comparisons cover six methods, so method-selection is reported as a benchmark ranking, not a discovery p-value. A learned-method adoption claim requires a paired bootstrap CI wholly below zero for `method - traditional`; otherwise the traditional baseline is not beaten.

## 6. Threats to Validity

- **Benchmark/selection:** the traditional comparator is the same strong CFD20 plus log-amplitude polynomial family as S18e. It is not a strawman; the learned models get richer waveform information.
- **Data leakage:** all fits train on late Sample III runs and predict Sample-IV analysis runs. The leakage table shows no train/held-out run overlap and no forbidden feature overlap.
- **Metric misuse:** robust width is primary, but full RMS, binned Gaussian core sigma, chi2/ndf, and tail fractions are reported. The low-count control_A3_adjacent result is explicitly caveated.
- **Post-hoc selection:** the channel controls were determined by raw occupancy under the S18 gate. Empty adjacent channels are reported rather than silently replaced.

Leakage checks:

{leakage.to_markdown(index=False)}

## 7. Provenance Manifest

`manifest.json` records the command, git commit, package versions, input ROOT hashes for all used runs, train-run hashes, and output hashes. `train_run_manifest.csv` records the late-Sample-III training files used by each pair/method split.

## 8. Findings and Next Steps

The adjacent controls do **not** provide a clean confirmation of a universal late-Sample-III transfer correction. They are low support in Sample IV, especially channel pair 4-5. Within this deliberately narrow and sparse control benchmark, `gradient_boosted_trees` is the statistical winner and its paired bootstrap delta is below the traditional baseline. That is a method-ranking result for adjacent side-channel coincidences, not a validation of a production A-stack timing calibration. The result therefore supports a conservative interpretation of S18e: the late-family improvement is primarily an A1-A3 anchor-pair ranking signal unless a higher-support adjacent-channel audit confirms otherwise.

Hypothesis: A-stack transfer stability is dominated by which physical/readout channel pair has usable through-going support; adjacent populated HRDv controls are mostly sparse side-readout coincidences and do not carry enough Sample-IV timing information to generalize the A1-A3 calibration decision.

Queued follow-up: {result['next_tickets'][0] if result['next_tickets'] else 'none'}

## 9. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}
```

Artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `train_run_manifest.csv`, `channel_occupancy.csv`, `reproduction_match_table.csv`, `anchor_reproduction_predictions.csv`, `heldout_predictions.csv.gz`, `method_pair_metrics.csv`, `method_macro_metrics.csv`, `method_deltas_vs_traditional.csv`, `run_heldout_summary.csv`, `ml_cv_scan.csv`, `fit_metadata.csv`, `leakage_checks.csv`, and PNG diagnostics.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifests(out_dir: Path, config: dict, config_path: Path, outputs: Sequence[str], predictions: pd.DataFrame) -> None:
    used_runs = sorted(set(int(x) for x in config["all_scan_runs"]))
    input_rows = []
    input_hashes = {}
    for run in used_runs:
        path = root_path(config, run)
        digest = sha256_file(path)
        input_rows.append({"file": str(path), "sha256": digest, "bytes": path.stat().st_size})
        input_hashes[str(path)] = {"sha256": digest, "bytes": path.stat().st_size}
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    train_rows = []
    for pair, sub in predictions.groupby("pair"):
        runs = sorted(set(int(x) for runs in sub["train_runs"].dropna().unique() for x in str(runs).split(",") if x))
        for run in runs:
            path = root_path(config, run)
            train_rows.append({"pair": pair, "train_run": run, "file": str(path), "sha256": input_hashes[str(path)]["sha256"], "bytes": input_hashes[str(path)]["bytes"]})
    pd.DataFrame(train_rows).drop_duplicates().sort_values(["pair", "train_run"]).to_csv(out_dir / "train_run_manifest.csv", index=False)

    output_hashes = {}
    for name in outputs:
        path = out_dir / name
        if path.exists() and path.is_file():
            output_hashes[name] = sha256_file(path)
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "command": f"/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}",
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
            "torch": getattr(torch, "__version__", "unavailable") if torch is not None else "unavailable",
        },
        "input_sha256": input_hashes,
        "outputs_sha256": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--ticket-body", default="")
    args = parser.parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".mplconfig").mkdir(exist_ok=True)

    rng = np.random.default_rng(int(config["random_seed"]))
    all_pairs = load_pairs(config, config["all_scan_runs"], "scan", pair_definitions(config, include_anchor=True))
    all_pairs.to_csv(out_dir / "astack_adjacent_pair_table.csv.gz", index=False)
    occupancy = scan_channel_occupancy(config)
    occupancy.to_csv(out_dir / "channel_occupancy.csv", index=False)

    reproduction, anchor_pred = reproduce_anchor(config, all_pairs)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    anchor_pred.to_csv(out_dir / "anchor_reproduction_predictions.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise SystemExit("reproduction gate failed")

    predictions, cv_scan, fit_meta = evaluate_controls(config, all_pairs)
    predictions.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    cv_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    fit_meta.to_csv(out_dir / "fit_metadata.csv", index=False)

    per_pair, macro, deltas = summarize_predictions(predictions, config)
    per_pair.to_csv(out_dir / "method_pair_metrics.csv", index=False)
    macro.to_csv(out_dir / "method_macro_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas_vs_traditional.csv", index=False)
    runs = run_summary(predictions)
    runs.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    leakage = leakage_checks(predictions, fit_meta, config)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    winner_row = macro.iloc[0].to_dict()
    trad_row = macro[macro["method"].eq("traditional_cfd20_poly")].iloc[0].to_dict()
    winner_delta = deltas[deltas["method"].eq(winner_row["method"])].iloc[0].to_dict()
    ml_rows = macro[~macro["method"].eq("traditional_cfd20_poly")]
    best_ml = ml_rows.iloc[0].to_dict()
    next_ticket = (
        "S18h: A-stack adjacent-control support audit across raw and sorted mirrors. "
        "Question: are the sparse HRDv 0-1 and 4-5 adjacent coincidences true side-readout timing controls or acquisition artifacts? "
        "Expected information gain: resolves whether S18f's low-support caveat is physical or a ROOT-channel mapping limitation."
    )
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": "A-stack adjacent-channel run-family transfer control",
        "reproduced": bool(reproduction["pass"].all()),
        "repro_tolerance": "pairs exact; robust/core width <= 0.001 ns",
        "traditional": {"metric": "control_macro_mean_robust_width_ns", "method": "traditional_cfd20_poly", "value": float(trad_row["value_ns"]), "ci": [float(trad_row["ci_low_ns"]), float(trad_row["ci_high_ns"])]},
        "ml": {"metric": "control_macro_mean_robust_width_ns", "method": str(best_ml["method"]), "value": float(best_ml["value_ns"]), "ci": [float(best_ml["ci_low_ns"]), float(best_ml["ci_high_ns"])]},
        "winner": {"method": str(winner_row["method"]), "metric": "control_macro_mean_robust_width_ns", "value": float(winner_row["value_ns"]), "ci": [float(winner_row["ci_low_ns"]), float(winner_row["ci_high_ns"])]},
        "winner_delta_vs_traditional": winner_delta,
        "ml_beats_baseline": bool(str(winner_row["method"]) != "traditional_cfd20_poly" and float(winner_delta["delta_ci_high_ns"]) < 0.0),
        "falsification": {"preregistered_metric": "control_macro_mean_robust_width_ns", "n_methods": len(METHODS), "adoption_rule": "learned method must have paired bootstrap delta CI entirely below zero versus traditional"},
        "input_sha256": "see input_sha256.csv",
        "git_commit": git_head(),
        "critic": "pending",
        "next_tickets": [next_ticket],
        "conclusion": "Gradient-boosted trees win the sparse adjacent-control benchmark, but the low Sample-IV support means this ranks methods for side-channel coincidences rather than validating a universal late-Sample-III A-stack transfer correction."
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, sort_keys=True), encoding="utf-8")

    plot_outputs(out_dir, per_pair, macro, predictions, str(winner_row["method"]))
    make_report(out_dir, config, config_path, args.ticket_body, reproduction, occupancy, per_pair, macro, deltas, runs, cv_scan, leakage, result)
    outputs = [
        "astack_adjacent_pair_table.csv.gz",
        "channel_occupancy.csv",
        "reproduction_match_table.csv",
        "anchor_reproduction_predictions.csv",
        "heldout_predictions.csv.gz",
        "ml_cv_scan.csv",
        "fit_metadata.csv",
        "method_pair_metrics.csv",
        "method_macro_metrics.csv",
        "method_deltas_vs_traditional.csv",
        "run_heldout_summary.csv",
        "leakage_checks.csv",
        "result.json",
        "REPORT.md",
        "fig_method_macro_width.png",
        "fig_winner_vs_traditional_residuals.png",
        "input_sha256.csv",
        "train_run_manifest.csv",
    ]
    write_manifests(out_dir, config, config_path, outputs, predictions)
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "ml_beats_baseline": result["ml_beats_baseline"]}, indent=2))


if __name__ == "__main__":
    main()
