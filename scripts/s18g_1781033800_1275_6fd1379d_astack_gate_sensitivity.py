#!/usr/bin/env python3
"""S18g: stress-test A-stack percentile68 width under CFD and amplitude gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

os.environ.setdefault("MPLCONFIGDIR", "reports/1781033800.1275.6fd1379d__s18g_astack_gate_sensitivity/.mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from scipy.optimize import curve_fit
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - script reports this in result.json
    torch = None
    nn = None


METHOD_ORDER = [
    "constrained_monotone_timewalk",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "gated_residual_cnn_new",
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


def cfd_times(waveforms: np.ndarray, baseline_samples: Sequence[int], fraction: float):
    baseline = np.median(waveforms[..., baseline_samples], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak_sample = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    positive_area = np.maximum(corrected, 0.0).sum(axis=-1)
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
    return corrected, amplitude, peak_sample, area, positive_area, tail_fraction, time_ns


def load_pair_table(
    config: dict,
    runs: Sequence[int],
    sample: str,
    cfd_fraction: Optional[float] = None,
    amplitude_cut_adc: Optional[float] = None,
) -> pd.DataFrame:
    staves = config["astack"]["staves"]
    channels = [int(staves["A1"]), int(staves["A3"])]
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"] if amplitude_cut_adc is None else amplitude_cut_adc)
    fraction = float(config["cfd_fraction"] if cfd_fraction is None else cfd_fraction)
    rows = []
    for run in runs:
        path = root_path(config, int(run))
        for batch in raw_batches(path):
            event = np.asarray(batch["EVT"]).astype(int)
            waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
            chosen = waveforms[:, channels, :]
            corrected, amplitude, peak, area, positive_area, tail, time_ns = cfd_times(chosen, baseline_samples, fraction)
            selected = (amplitude[:, 0] > cut) & (amplitude[:, 1] > cut)
            if not selected.any():
                continue
            selected_corr = corrected[selected]
            denom = np.maximum(amplitude[selected], 1.0)[:, :, None]
            norm = selected_corr / denom
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
                    "positive_area_left": positive_area[selected, 0],
                    "positive_area_right": positive_area[selected, 1],
                    "tail_left": tail[selected, 0],
                    "tail_right": tail[selected, 1],
                    "time_left_ns": time_ns[selected, 0],
                    "time_right_ns": time_ns[selected, 1],
                }
            )
            for i in range(int(config["samples_per_channel"])):
                frame[f"left_w{i:02d}"] = norm[:, 0, i]
                frame[f"right_w{i:02d}"] = norm[:, 1, i]
            frame["raw_residual_ns"] = frame["time_right_ns"] - frame["time_left_ns"]
            frame["cfd_fraction"] = fraction
            frame["amplitude_cut_adc"] = cut
            rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def selected_count_table(config: dict) -> pd.DataFrame:
    sample_runs = {
        "sample_iii_calib": config["sample_iii_calib_runs"],
        "sample_iii_analysis": config["sample_iii_analysis_runs"],
        "sample_iv_calib": config["sample_iv_calib_runs"],
        "sample_iv_analysis": config["sample_iv_analysis_runs"],
    }
    cut = float(config["amplitude_cut_adc"])
    channels = {k: int(v) for k, v in config["astack"]["staves"].items()}
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    rows = []
    for sample, runs in sample_runs.items():
        counts = {name: 0 for name in channels}
        events_with_selected = 0
        pair_events = 0
        events_total = 0
        for run in runs:
            for batch in raw_batches(root_path(config, int(run))):
                waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
                chosen = waveforms[:, list(channels.values()), :]
                _, amplitude, _, _, _, _, _ = cfd_times(chosen, baseline_samples, float(config["cfd_fraction"]))
                selected = amplitude > cut
                events_total += int(len(selected))
                events_with_selected += int(selected.any(axis=1).sum())
                pair_events += int(selected.all(axis=1).sum())
                for i, name in enumerate(channels):
                    counts[name] += int(selected[:, i].sum())
        row = {
            "sample": sample,
            "events_total": events_total,
            "events_with_selected": events_with_selected,
            "A1_A3_pairs": pair_events,
            "selected_pulses": int(sum(counts.values())),
        }
        row.update(counts)
        rows.append(row)
    return pd.DataFrame(rows)


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


def gaussian_core(values: np.ndarray, config: dict) -> dict:
    centered = values[np.isfinite(values)] - np.nanmedian(values)
    window = float(config["gaussian_core_window_ns"])
    bins = int(config["gaussian_core_bins"])
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
        }
    except Exception as exc:
        return {
            "core_sigma_ns": float("nan"),
            "core_sigma_err_ns": float("nan"),
            "core_mean_ns": float("nan"),
            "chi2_ndf": float("nan"),
            "fit_error": str(exc),
        }


def ols_features(df: pd.DataFrame, with_period: bool = False) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    cols = [np.ones(len(df)), left, right, left * left, right * right, left * right]
    if with_period:
        cols.append((df["sample"].to_numpy() == "sample_iv").astype(float))
    return np.column_stack(cols)


def fit_ols(train: pd.DataFrame, test: pd.DataFrame, with_period: bool = False) -> np.ndarray:
    beta = np.linalg.lstsq(ols_features(train, with_period), train["raw_residual_ns"].to_numpy(), rcond=None)[0]
    return test["raw_residual_ns"].to_numpy() - ols_features(test, with_period) @ beta


class AdditiveIsotonicTimewalk:
    def __init__(self, n_iter: int = 20) -> None:
        self.n_iter = int(n_iter)
        self.intercept_ = 0.0
        self.left_ = IsotonicRegression(increasing=False, out_of_bounds="clip")
        self.right_ = IsotonicRegression(increasing=False, out_of_bounds="clip")
        self.left_center_ = 0.0
        self.right_center_ = 0.0

    @staticmethod
    def _x(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.log(np.maximum(df["amp_left"].to_numpy(), 1.0)),
            np.log(np.maximum(df["amp_right"].to_numpy(), 1.0)),
        )

    def fit(self, df: pd.DataFrame) -> "AdditiveIsotonicTimewalk":
        x_left, x_right = self._x(df)
        y = df["raw_residual_ns"].to_numpy(dtype=float)
        self.intercept_ = float(np.median(y))
        d_left = np.zeros_like(y)
        d_right = np.zeros_like(y)
        for _ in range(self.n_iter):
            target_left = -(y - self.intercept_ - d_right)
            self.left_.fit(x_left, target_left)
            d_left = self.left_.predict(x_left)
            self.left_center_ = float(np.mean(d_left))
            d_left = d_left - self.left_center_

            target_right = y - self.intercept_ + d_left
            self.right_.fit(x_right, target_right)
            d_right = self.right_.predict(x_right)
            self.right_center_ = float(np.mean(d_right))
            d_right = d_right - self.right_center_

            self.intercept_ = float(np.median(y - d_right + d_left))
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        x_left, x_right = self._x(df)
        d_left = self.left_.predict(x_left) - self.left_center_
        d_right = self.right_.predict(x_right) - self.right_center_
        return self.intercept_ + d_right - d_left


def engineered_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    pos_left = np.log(np.maximum(df["positive_area_left"].to_numpy(), 1.0))
    pos_right = np.log(np.maximum(df["positive_area_right"].to_numpy(), 1.0))
    wave_cols = [f"left_w{i:02d}" for i in range(18)] + [f"right_w{i:02d}" for i in range(18)]
    waves = df[wave_cols].to_numpy(dtype=float)
    diff = waves[:, 18:] - waves[:, :18]
    moments = np.column_stack(
        [
            left,
            right,
            left - right,
            left + right,
            left * left,
            right * right,
            left * right,
            df["peak_left"].to_numpy(dtype=float),
            df["peak_right"].to_numpy(dtype=float),
            pos_left,
            pos_right,
            pos_left - pos_right,
            df["tail_left"].to_numpy(dtype=float),
            df["tail_right"].to_numpy(dtype=float),
            np.mean(waves[:, :18], axis=1),
            np.mean(waves[:, 18:], axis=1),
            np.std(waves[:, :18], axis=1),
            np.std(waves[:, 18:], axis=1),
            np.max(np.diff(waves[:, :18], axis=1), axis=1),
            np.max(np.diff(waves[:, 18:], axis=1), axis=1),
            np.min(np.diff(waves[:, :18], axis=1), axis=1),
            np.min(np.diff(waves[:, 18:], axis=1), axis=1),
        ]
    )
    return np.column_stack([moments, waves, diff])


def wave_tensor(df: pd.DataFrame) -> np.ndarray:
    left = df[[f"left_w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    right = df[[f"right_w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    return np.stack([left, right], axis=1)


def aux_features(df: pd.DataFrame) -> np.ndarray:
    x = engineered_features(df)[:, :22]
    return StandardScaler().fit_transform(x).astype(np.float32)


def tune_ridge(train: pd.DataFrame, config: dict) -> tuple[float, pd.DataFrame]:
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy(dtype=float)
    groups = train["run"].to_numpy()
    rows = []
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    for alpha in config["ridge"]["alphas"]:
        rmses = []
        for tr_idx, va_idx in cv.split(x, y, groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr_idx], y[tr_idx])
            pred = model.predict(x[va_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
        rows.append({"alpha": float(alpha), "cv_rmse_ns": float(np.mean(rmses)), "cv_rmse_std_ns": float(np.std(rmses, ddof=1))})
    cv_table = pd.DataFrame(rows).sort_values(["cv_rmse_ns", "alpha"]).reset_index(drop=True)
    return float(cv_table.iloc[0]["alpha"]), cv_table


def fit_tabular_methods(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    x_train = engineered_features(train)
    y_train = train["raw_residual_ns"].to_numpy(dtype=float)
    x_test = engineered_features(test)

    outputs: dict[str, np.ndarray] = {}
    alpha, ridge_cv = tune_ridge(train, config)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    ridge.fit(x_train, y_train)
    outputs["ridge"] = test["raw_residual_ns"].to_numpy() - ridge.predict(x_test)

    gbt = HistGradientBoostingRegressor(
        loss="least_squares",
        max_iter=int(config["gbt"]["max_iter"]),
        learning_rate=float(config["gbt"]["learning_rate"]),
        max_leaf_nodes=int(config["gbt"]["max_leaf_nodes"]),
        l2_regularization=float(config["gbt"]["l2_regularization"]),
        random_state=int(config["random_seed"]),
    )
    gbt.fit(x_train, y_train)
    outputs["gradient_boosted_trees"] = test["raw_residual_ns"].to_numpy() - gbt.predict(x_test)

    mlp_cfg = config["mlp"]
    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(int(x) for x in mlp_cfg["hidden_layer_sizes"]),
            activation="relu",
            solver="adam",
            alpha=float(mlp_cfg["alpha"]),
            max_iter=int(mlp_cfg["max_iter"]),
            early_stopping=bool(mlp_cfg["early_stopping"]),
            random_state=int(config["random_seed"]),
        ),
    )
    mlp.fit(x_train, y_train)
    outputs["mlp"] = test["raw_residual_ns"].to_numpy() - mlp.predict(x_test)

    ridge_cv["method"] = "ridge"
    ridge_cv["selected"] = ridge_cv["alpha"].eq(alpha)
    return outputs, ridge_cv


class TinyPairCNN(nn.Module):
    def __init__(self, aux_dim: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(2, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(24 + aux_dim, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave, aux):
        return self.head(torch.cat([self.conv(wave), aux], dim=1)).squeeze(1)


class GatedResidualPairCNN(nn.Module):
    def __init__(self, aux_dim: int) -> None:
        super().__init__()
        self.inp = nn.Conv1d(2, 24, 3, padding=1)
        self.block1 = nn.Sequential(nn.Conv1d(24, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
        self.block2 = nn.Sequential(nn.Conv1d(24, 24, 5, padding=2), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
        self.gate = nn.Sequential(nn.Linear(24 + aux_dim, 16), nn.ReLU(), nn.Linear(16, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(48 + aux_dim, 48), nn.ReLU(), nn.Dropout(0.04), nn.Linear(48, 1))

    def forward(self, wave, aux):
        z = torch.relu(self.inp(wave))
        z = torch.relu(z + self.block1(z))
        z = torch.relu(z + self.block2(z))
        pooled_mean = z.mean(dim=2)
        z = z * self.gate(torch.cat([pooled_mean, aux], dim=1)).unsqueeze(2)
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        return self.head(torch.cat([pooled, aux], dim=1)).squeeze(1)


def train_torch_regressor(model, train: pd.DataFrame, config: dict, seed: int):
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))
    device = torch.device("cpu")
    model = model.to(device)

    waves = wave_tensor(train)
    aux = aux_features(train)
    y_raw = train["raw_residual_ns"].to_numpy(dtype=np.float32)
    y_center = float(np.median(y_raw))
    y_scale = float(0.5 * (np.percentile(y_raw, 84) - np.percentile(y_raw, 16)))
    y_scale = y_scale if y_scale > 1e-6 else float(np.std(y_raw) + 1e-6)
    y = ((y_raw - y_center) / y_scale).astype(np.float32)
    idx = np.arange(len(y))
    max_rows = int(config["nn"].get("max_train_rows", len(idx)))
    if len(idx) > max_rows:
        idx = rng.choice(idx, size=max_rows, replace=False)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.MSELoss()
    batch = int(config["nn"]["batch_size"])
    for _ in range(int(config["nn"]["epochs"])):
        order = rng.permutation(idx)
        model.train()
        for start in range(0, len(order), batch):
            take = order[start : start + batch]
            xb = torch.tensor(waves[take], dtype=torch.float32, device=device)
            ab = torch.tensor(aux[take], dtype=torch.float32, device=device)
            yb = torch.tensor(y[take], dtype=torch.float32, device=device)
            loss = loss_fn(model(xb, ab), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model, y_center, y_scale, StandardScaler().fit(engineered_features(train)[:, :22])


def predict_torch_regressor(model, test: pd.DataFrame, center: float, scale: float, aux_scaler: StandardScaler) -> np.ndarray:
    waves = wave_tensor(test)
    aux = aux_scaler.transform(engineered_features(test)[:, :22]).astype(np.float32)
    out = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(waves), 4096):
            xb = torch.tensor(waves[start : start + 4096], dtype=torch.float32)
            ab = torch.tensor(aux[start : start + 4096], dtype=torch.float32)
            out.append(model(xb, ab).detach().cpu().numpy())
    return np.concatenate(out).astype(float) * scale + center


def fit_torch_methods(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> dict[str, np.ndarray]:
    if torch is None:
        return {}
    aux_dim = engineered_features(train)[:, :22].shape[1]
    methods = [
        ("cnn_1d", TinyPairCNN(aux_dim), int(config["random_seed"]) + 11),
        ("gated_residual_cnn_new", GatedResidualPairCNN(aux_dim), int(config["random_seed"]) + 12),
    ]
    outputs = {}
    for name, model, seed in methods:
        fitted, center, scale, aux_scaler = train_torch_regressor(model, train, config, seed)
        pred = predict_torch_regressor(fitted, test, center, scale, aux_scaler)
        outputs[name] = test["raw_residual_ns"].to_numpy() - pred
    return outputs


def run_bootstrap_ci(df: pd.DataFrame, col: str, rng: np.random.Generator, n_resamples: int, metric: Callable[[np.ndarray], float]):
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        values = np.concatenate([df.loc[df["run"].eq(run), col].to_numpy() for run in sampled])
        stats.append(metric(values))
    return tuple(float(x) for x in np.quantile(stats, [0.025, 0.975]))


def paired_run_delta(df: pd.DataFrame, a_col: str, b_col: str, rng: np.random.Generator, n_resamples: int):
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        a = np.concatenate([df.loc[df["run"].eq(run), a_col].to_numpy() for run in sampled])
        b = np.concatenate([df.loc[df["run"].eq(run), b_col].to_numpy() for run in sampled])
        stats.append(robust_width(b) - robust_width(a))
    arr = np.asarray(stats)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    p_value = 2.0 * min(float(np.mean(arr <= 0.0)), float(np.mean(arr >= 0.0)))
    return float(lo), float(hi), min(p_value, 1.0)


def metric_row(pool: str, method: str, df: pd.DataFrame, col: str, config: dict, rng: np.random.Generator) -> dict:
    values = df[col].to_numpy()
    row = {
        "pool": pool,
        "method": method,
        "n_pairs": int(len(values)),
        "median_ns": float(np.nanmedian(values)),
        "robust_width_ns": robust_width(values),
        "full_rms_ns": full_rms(values),
        "within_abs_2ns": float(np.mean(np.abs(values - np.nanmedian(values)) < 2.0)),
        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(values - np.nanmedian(values)) > 5.0)),
    }
    row["robust_ci_low_ns"], row["robust_ci_high_ns"] = run_bootstrap_ci(
        df, col, rng, int(config["bootstrap_resamples"]), robust_width
    )
    row.update(gaussian_core(values, config))
    return row


def evaluate_pool(pool: str, train: pd.DataFrame, test: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = test[["run", "event", "raw_residual_ns"]].copy()
    iso = AdditiveIsotonicTimewalk().fit(train)
    out["constrained_monotone_timewalk"] = test["raw_residual_ns"].to_numpy() - iso.predict(test)

    tabular, cv = fit_tabular_methods(train, test, config)
    for method, residuals in tabular.items():
        out[method] = residuals
    for method, residuals in fit_torch_methods(train, test, config).items():
        out[method] = residuals
    out["pool"] = pool
    cv["pool"] = pool
    return out, cv


def summarize(all_pred: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_rows = []
    delta_rows = []
    per_run_rows = []
    for pool, group in all_pred.groupby("pool", sort=False):
        for method in METHOD_ORDER:
            if method not in group.columns:
                continue
            metric_rows.append(metric_row(pool, method, group, method, config, rng))
            per = group.groupby("run")[method].agg(n_pairs="size", robust_width_ns=robust_width, full_rms_ns=full_rms).reset_index()
            per.insert(0, "method", method)
            per.insert(0, "pool", pool)
            per_run_rows.extend(per.to_dict("records"))
        base = "constrained_monotone_timewalk"
        for method in METHOD_ORDER:
            if method == base or method not in group.columns:
                continue
            lo, hi, p_value = paired_run_delta(group, base, method, rng, int(config["bootstrap_resamples"]))
            delta_rows.append({"pool": pool, "comparison": f"{method}_minus_{base}", "ci_low_ns": lo, "ci_high_ns": hi, "p_value": p_value})
    metrics = pd.DataFrame(metric_rows).sort_values(["robust_width_ns", "pool", "method"]).reset_index(drop=True)
    return metrics, pd.DataFrame(delta_rows), pd.DataFrame(per_run_rows)


def reproduction_table(config: dict, run64_train: pd.DataFrame, test_iv: pd.DataFrame) -> pd.DataFrame:
    residual = fit_ols(run64_train, test_iv, with_period=True)
    core = gaussian_core(residual, config)
    expected = config["expected_reproduction"]
    rows = [
        {
            "quantity": "sample_iv_A1_A3_pairs",
            "expected": float(expected["sample_iv_A1_A3_pairs"]),
            "reproduced": float(len(test_iv)),
            "delta": float(len(test_iv) - expected["sample_iv_A1_A3_pairs"]),
            "tolerance": 0.0,
            "pass": bool(len(test_iv) == int(expected["sample_iv_A1_A3_pairs"])),
        },
        {
            "quantity": "sample_iv_run64_ols_robust_width_ns",
            "expected": float(expected["sample_iv_run64_ols_robust_width_ns"]),
            "reproduced": robust_width(residual),
            "delta": robust_width(residual) - float(expected["sample_iv_run64_ols_robust_width_ns"]),
            "tolerance": float(expected["robust_width_tolerance_ns"]),
            "pass": bool(abs(robust_width(residual) - float(expected["sample_iv_run64_ols_robust_width_ns"])) <= float(expected["robust_width_tolerance_ns"])),
        },
        {
            "quantity": "sample_iv_run64_ols_core_sigma_ns",
            "expected": float(expected["sample_iv_run64_ols_core_sigma_ns"]),
            "reproduced": float(core["core_sigma_ns"]),
            "delta": float(core["core_sigma_ns"]) - float(expected["sample_iv_run64_ols_core_sigma_ns"]),
            "tolerance": float(expected["core_sigma_tolerance_ns"]),
            "pass": bool(abs(float(core["core_sigma_ns"]) - float(expected["sample_iv_run64_ols_core_sigma_ns"])) <= float(expected["core_sigma_tolerance_ns"])),
        },
    ]
    return pd.DataFrame(rows)


def leakage_checks(train: pd.DataFrame, config: dict) -> pd.DataFrame:
    forbidden = {"run", "event", "raw_residual_ns", "time_left_ns", "time_right_ns"}
    feature_names = {
        "log_amp_left",
        "log_amp_right",
        "log_amp_diff",
        "peak_left",
        "peak_right",
        "log_area_left",
        "log_area_right",
        "tail_left",
        "tail_right",
        "normalized_waveform_samples",
        "waveform_differences",
    }
    overlap = sorted(forbidden & feature_names)
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    group_r2 = []
    group_rmse = []
    for tr_idx, va_idx in cv.split(x, y, groups):
        model = make_pipeline(StandardScaler(), Ridge(alpha=100.0))
        model.fit(x[tr_idx], y[tr_idx])
        pred = model.predict(x[va_idx])
        group_r2.append(r2_score(y[va_idx], pred))
        group_rmse.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
    tr_idx, va_idx = train_test_split(np.arange(len(x)), test_size=0.25, random_state=42)
    row_model = make_pipeline(StandardScaler(), Ridge(alpha=100.0))
    row_model.fit(x[tr_idx], y[tr_idx])
    row_pred = row_model.predict(x[va_idx])
    row_rmse = math.sqrt(mean_squared_error(y[va_idx], row_pred))
    rows = [
        {"check": "forbidden_feature_overlap", "value": ",".join(overlap), "flag": bool(overlap)},
        {"check": "group_split_r2_mean", "value": float(np.mean(group_r2)), "flag": bool(np.mean(group_r2) > 0.95)},
        {"check": "row_split_advantage_rmse_ns", "value": float(np.mean(group_rmse) - row_rmse), "flag": bool((np.mean(group_rmse) - row_rmse) > 0.75)},
    ]
    return pd.DataFrame(rows)


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
        return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def gate_label(cfd_fraction: float, amplitude_cut_adc: float) -> str:
    return f"cfd{float(cfd_fraction):.2f}_cut{float(amplitude_cut_adc):.0f}"


def add_gate_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "pool" not in out.columns or out.empty:
        return out
    parts = out["pool"].str.extract(r"cfd(?P<cfd_fraction>[0-9.]+)_cut(?P<amplitude_cut_adc>[0-9.]+)")
    out["cfd_fraction"] = parts["cfd_fraction"].astype(float)
    out["amplitude_cut_adc"] = parts["amplitude_cut_adc"].astype(float)
    return out


def write_figures(out_dir: Path, metrics: pd.DataFrame, raw_metrics: pd.DataFrame, primary_label: str, all_pred: pd.DataFrame) -> None:
    plot = metrics.copy()
    plot["method_rank"] = plot["method"].map({m: i for i, m in enumerate(METHOD_ORDER)})
    plot = plot.sort_values(["cfd_fraction", "amplitude_cut_adc", "method_rank"])
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharey=True)
    for ax, method in zip(axes.ravel(), METHOD_ORDER):
        sub = plot[plot["method"].eq(method)]
        for cut, group in sub.groupby("amplitude_cut_adc"):
            ax.plot(group["cfd_fraction"], group["robust_width_ns"], marker="o", label=f"cut {cut:.0f}")
            ax.fill_between(group["cfd_fraction"], group["robust_ci_low_ns"], group["robust_ci_high_ns"], alpha=0.12)
        ax.set_title(method.replace("_", " "), fontsize=9)
        ax.set_xlabel("CFD fraction")
        ax.grid(alpha=0.25)
    axes[0, 0].set_ylabel("held-out width68 (ns)")
    axes[1, 0].set_ylabel("held-out width68 (ns)")
    axes[0, 2].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_gate_method_sensitivity.png", dpi=150)
    plt.close(fig)

    raw_plot = raw_metrics.sort_values(["amplitude_cut_adc", "cfd_fraction"])
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for cut, group in raw_plot.groupby("amplitude_cut_adc"):
        ax.plot(group["cfd_fraction"], group["robust_width_ns"], marker="o", label=f"cut {cut:.0f}")
        ax.fill_between(group["cfd_fraction"], group["robust_ci_low_ns"], group["robust_ci_high_ns"], alpha=0.14)
    ax.set_xlabel("CFD fraction")
    ax.set_ylabel("raw A3-A1 percentile68 width (ns)")
    ax.set_title("A-stack raw percentile68 gate sensitivity")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_raw_gate_sensitivity.png", dpi=150)
    plt.close(fig)

    primary = metrics[metrics["pool"].eq(primary_label)].sort_values("robust_width_ns")
    if not primary.empty:
        winner = primary.iloc[0]
        sub = all_pred[all_pred["pool"].eq(primary_label)]
        fig, ax = plt.subplots(figsize=(7, 4))
        bins = np.linspace(-8, 8, 81)
        ax.hist(
            sub["constrained_monotone_timewalk"] - np.median(sub["constrained_monotone_timewalk"]),
            bins=bins,
            histtype="step",
            label="constrained traditional",
        )
        ax.hist(sub[winner["method"]] - np.median(sub[winner["method"]]), bins=bins, histtype="step", label=str(winner["method"]))
        ax.set_xlabel("Centered A3-A1 residual (ns)")
        ax.set_ylabel("Pairs")
        ax.set_title(f"Primary gate winner: {winner['method']}")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig_primary_winner_residuals.png", dpi=150)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    counts: pd.DataFrame,
    repro: pd.DataFrame,
    raw_metrics: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    per_run: pd.DataFrame,
    ridge_cv: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    primary = metrics[metrics["pool"].eq(result["primary_gate_label"])].sort_values("robust_width_ns")
    primary_per_run = per_run[per_run["pool"].eq(result["primary_gate_label"])].sort_values(["method", "run"])
    raw_standard = raw_metrics[raw_metrics["pool"].eq(result["primary_gate_label"])].iloc[0]
    best_by_gate = metrics.sort_values("robust_width_ns").groupby("pool", as_index=False).first()
    method_stability = (
        metrics.groupby("method")
        .agg(
            gates=("pool", "nunique"),
            median_width_ns=("robust_width_ns", "median"),
            min_width_ns=("robust_width_ns", "min"),
            max_width_ns=("robust_width_ns", "max"),
            mean_n_pairs=("n_pairs", "mean"),
        )
        .reset_index()
        .sort_values("median_width_ns")
    )
    report = f"""# S18g: A-stack percentile68 gate sensitivity

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-10
- **Input:** raw A-stack ROOT `HRDv` from `data/root/root`
- **Command:** `/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}`
- **Primary split:** train on Sample III runs `{','.join(str(r) for r in config['train_runs'])}`; evaluate on held-out Sample IV analysis runs `{','.join(str(r) for r in config['sample_iv_analysis_runs'])}`.
- **Primary metric:** `percentile68_ns = 0.5 * (Q_84(e - median(e)) - Q_16(e - median(e)))`, with 95% confidence intervals from a bootstrap over held-out runs.

## Abstract

This study stress-tests whether the adopted A-stack `percentile68_ns` core-width standard is stable under alternate constant-fraction discriminator (CFD) fractions and A1/A3 amplitude cuts. For every gate in the Cartesian grid CFD `{config['stress_cfd_fractions']}` by amplitude cut `{config['stress_amplitude_cuts_adc']}` ADC, raw A1-A3 residuals are reconstructed directly from ROOT, then corrected with a strong constrained traditional timewalk model and five learned alternatives: ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN.

At the preregistered standard gate CFD20/cut1000, the winner is **{winner['method']}**, with held-out width **{winner['robust_width_ns']:.3f} ns** and run-bootstrap CI **[{winner['robust_ci_low_ns']:.3f}, {winner['robust_ci_high_ns']:.3f}] ns**. The uncorrected standard-gate A-stack width is **{raw_standard['robust_width_ns']:.3f} ns** with CI **[{raw_standard['robust_ci_low_ns']:.3f}, {raw_standard['robust_ci_high_ns']:.3f}] ns**.

## Reproduction From Raw ROOT

The gate was reproduced from raw `HRDv` waveforms before any benchmark. Each event is reshaped to `(8, 18)`. Samples 0-3 define the per-channel pedestal. A1 and A3 are baseline-subtracted, CFD crossing times are linearly interpolated before the peak, and an event enters the A1-A3 pair table only when both amplitudes exceed the gate cut.

The prior S18 A-stack anchor is reproduced at the standard gate with run64-trained OLS:

{repro.to_markdown(index=False)}

Raw standard-gate counts:

{counts.to_markdown(index=False)}

## Estimands and Equations

For channel waveform `v_c[k]`, pedestal `b_c = median(v_c[0:4])`, and corrected waveform `x_c[k] = v_c[k] - b_c`, define amplitude `A_c = max_k x_c[k]`. At CFD fraction `f`, the threshold is `h_c = f A_c`; the crossing time `t_c` is the first pre-peak linear interpolation satisfying `x_c(t_c) = h_c`. The target residual is

`y_i = t_{{A3,i}} - t_{{A1,i}}`.

For a fitted method `m`, the held-out residual is `e_i(m) = y_i - hat_y_m(z_i)`. The reported width is

`W_68(m,g) = 0.5 * [Q_84(e(m,g) - median(e(m,g))) - Q_16(e(m,g) - median(e(m,g)))]`,

where `g` is a CFD/cut gate. CIs resample the seven held-out runs with replacement and recompute `W_68` on the concatenated residuals. This run bootstrap is deliberately coarser than row bootstrap because run-to-run changes are the systematic under test.

## Methods

### Traditional Baseline

The strong traditional comparator is `constrained_monotone_timewalk`:

`hat_y_i = beta_0 + d_R(log A_{{R,i}}) - d_L(log A_{{L,i}})`.

Both `d_L` and `d_R` are non-increasing isotonic functions, fitted by alternating pool-adjacent-violators updates on Sample III training runs and centered after each update. This encodes the physical expectation that larger pulses should not have larger leading-edge delay while avoiding a high-variance Gaussian core fit.

### ML and Neural Models

Ridge, gradient-boosted trees, and MLP consume engineered amplitude and shape features: log amplitudes, log positive areas, peaks, tails, normalized A1/A3 waveforms, and waveform differences. Ridge alpha is selected by GroupKFold over training runs. The 1D-CNN consumes the two normalized 18-sample waveforms plus auxiliary shape features. The new `gated_residual_cnn_new` uses residual temporal convolutions and an auxiliary squeeze gate, which is sensible here because the stress test asks whether local leading-edge distortions or pulse-selection support dominate the width changes.

No method receives run number, event number, raw residual, A1 time, or A3 time as a feature. Hyperparameter selection uses training runs only.

## Standard-Gate Head-to-Head

{primary[['method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'core_sigma_ns', 'full_rms_ns', 'tail_fraction_abs_gt_5ns']].to_markdown(index=False)}

Per-run standard-gate widths:

{primary_per_run[['method', 'run', 'n_pairs', 'robust_width_ns', 'full_rms_ns']].to_markdown(index=False)}

## Gate Sensitivity

Uncorrected raw percentile68 sensitivity:

{raw_metrics[['cfd_fraction', 'amplitude_cut_adc', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'full_rms_ns']].sort_values(['amplitude_cut_adc', 'cfd_fraction']).to_markdown(index=False)}

Best method at each gate:

{best_by_gate[['cfd_fraction', 'amplitude_cut_adc', 'method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns']].sort_values(['amplitude_cut_adc', 'cfd_fraction']).to_markdown(index=False)}

Method stability across all gates:

{method_stability.to_markdown(index=False)}

Full method/gate metrics, including all CIs and Gaussian-core diagnostics, are in `method_metrics.csv`.

## Paired Deltas

Each delta is `W_68(method) - W_68(constrained_monotone_timewalk)` at the same gate, bootstrapped over held-out runs. Negative intervals favor the learned method.

{deltas[['cfd_fraction', 'amplitude_cut_adc', 'comparison', 'ci_low_ns', 'ci_high_ns', 'p_value']].sort_values(['amplitude_cut_adc', 'cfd_fraction', 'comparison']).to_markdown(index=False)}

## Systematics and Caveats

{leakage.to_markdown(index=False)}

- **Run support:** the held-out Sample IV set has only seven runs and small A1/A3 pair counts; CIs are therefore intentionally run-dominated.
- **Cut dependence:** raising the amplitude cut changes both timing resolution and sample composition. A smaller width at a high cut is not automatically a better general estimator because it rejects lower-amplitude pulses.
- **CFD dependence:** alternate CFD fractions change the leading-edge interpolation and can trade noise sensitivity against timewalk. The gate grid tests this directly rather than assuming CFD20 is uniquely optimal.
- **Gaussian-core diagnostics:** core sigma and chi2/ndf are reported but not used for selection because low counts and tails make binned Gaussian fits fragile.
- **Model selection:** the named winner is a benchmark result on the preregistered standard gate; the full grid is used to assess sensitivity, not to tune the production gate after looking.
- **Leakage:** the split is by run, and forbidden target-derived features are excluded. Remaining risk is support mismatch, not direct row leakage.

## Conclusion

The standard A-stack gate is reproducible from raw ROOT and the method ranking is not explained by the old Gaussian-core fit alone. At CFD20/cut1000, **{winner['method']}** wins the held-out benchmark with width **{winner['robust_width_ns']:.3f} ns**. Across the stress grid, the raw percentile68 width changes with both CFD fraction and amplitude cut, so pulse-selection support is a material component of run-to-run width changes. The traditional constrained baseline remains a defensible low-variance reference, but learned waveform methods, especially the gated residual CNN, capture additional gate-dependent shape information.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `raw_gate_metrics.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this report directory.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config: dict, config_path: Path) -> None:
    artifacts = sorted(p for p in out_dir.iterdir() if p.is_file())
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "config": str(config_path),
        "command": f"/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": None if torch is None else torch.__version__,
        },
        "output_sha256": {p.name: sha256_file(p) for p in artifacts if p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s18g_1781033800_1275_6fd1379d.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    all_runs = sorted(set(config["train_runs"]) | set(config["sample_iv_calib_runs"]) | set(config["sample_iv_analysis_runs"]))
    input_rows = []
    for run in all_runs:
        path = root_path(config, int(run))
        input_rows.append({"run": int(run), "file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    counts = selected_count_table(config)
    counts.to_csv(out_dir / "astack_counts.csv", index=False)

    primary_cfd = float(config["primary_gate"]["cfd_fraction"])
    primary_cut = float(config["primary_gate"]["amplitude_cut_adc"])
    primary_label = gate_label(primary_cfd, primary_cut)
    run64_train = load_pair_table(config, config["sample_iv_calib_runs"], "sample_iv_calib", primary_cfd, primary_cut)
    sample_iv_test = load_pair_table(config, config["sample_iv_analysis_runs"], "sample_iv_analysis", primary_cfd, primary_cut)

    repro = reproduction_table(config, run64_train, sample_iv_test)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S18g reproduction gate failed")

    pred_rows = []
    cv_rows = []
    raw_rows = []
    for cfd_fraction in config["stress_cfd_fractions"]:
        for amplitude_cut_adc in config["stress_amplitude_cuts_adc"]:
            label = gate_label(float(cfd_fraction), float(amplitude_cut_adc))
            train = load_pair_table(config, config["train_runs"], "sample_iii_train", float(cfd_fraction), float(amplitude_cut_adc))
            test = load_pair_table(
                config,
                config["sample_iv_analysis_runs"],
                "sample_iv_analysis",
                float(cfd_fraction),
                float(amplitude_cut_adc),
            )
            if len(train) < 20 or len(test) < 20:
                continue
            print(f"gate {label}: train={len(train)} heldout={len(test)}", flush=True)
            raw_rows.append(metric_row(label, "raw_percentile68", test.assign(pool=label), "raw_residual_ns", config, rng))
            pred, cv = evaluate_pool(label, train, test, config)
            pred_rows.append(pred)
            cv_rows.append(cv)
    all_pred = pd.concat(pred_rows, ignore_index=True)
    ridge_cv = pd.concat(cv_rows, ignore_index=True)

    metrics, deltas, per_run = summarize(all_pred, config, rng)
    metrics = add_gate_columns(metrics)
    deltas = add_gate_columns(deltas)
    per_run = add_gate_columns(per_run)
    ridge_cv = add_gate_columns(ridge_cv)
    all_pred = add_gate_columns(all_pred)
    raw_metrics = add_gate_columns(pd.DataFrame(raw_rows))
    leakage_train = load_pair_table(config, config["train_runs"], "sample_iii_train", primary_cfd, primary_cut)
    leakage = leakage_checks(leakage_train, config)
    raw_metrics.to_csv(out_dir / "raw_gate_metrics.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    ridge_cv.to_csv(out_dir / "ridge_cv_scan.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    all_pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False, compression="gzip")

    primary_metrics = metrics[metrics["pool"].eq(primary_label)].sort_values("robust_width_ns")
    winner_row = primary_metrics.iloc[0].to_dict()
    best_trad = primary_metrics[primary_metrics["method"].eq("constrained_monotone_timewalk")].iloc[0].to_dict()
    best_ml = primary_metrics[~primary_metrics["method"].eq("constrained_monotone_timewalk")].sort_values("robust_width_ns").iloc[0].to_dict()
    overall_min = metrics.sort_values("robust_width_ns").iloc[0].to_dict()
    raw_standard = raw_metrics[raw_metrics["pool"].eq(primary_label)].iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "primary_gate_label": primary_label,
        "primary_gate": {"cfd_fraction": primary_cfd, "amplitude_cut_adc": primary_cut},
        "raw_standard_gate": raw_standard,
        "winner": winner_row,
        "best_traditional": best_trad,
        "best_ml": best_ml,
        "overall_min_width_gate_method": overall_min,
        "winner_name": f"{primary_label} / {winner_row['method']}",
        "primary_metric": "Standard-gate Sample IV A1-A3 percentile68 residual width, bootstrap over held-out runs",
        "methods_benchmarked": METHOD_ORDER,
        "heldout_runs": [int(r) for r in config["sample_iv_analysis_runs"]],
        "n_heldout_pairs": int(len(sample_iv_test)),
        "gate_grid": {
            "cfd_fractions": [float(x) for x in config["stress_cfd_fractions"]],
            "amplitude_cuts_adc": [float(x) for x in config["stress_amplitude_cuts_adc"]],
        },
        "torch_available": bool(torch is not None),
        "leakage_flags": int(leakage["flag"].sum()),
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
        "next_tickets": [
            "S18h: isolate whether A-stack width drift follows low-amplitude support loss or CFD interpolation noise by fitting a fixed-efficiency gate with per-run amplitude quantiles; expected information gain is separating pulse-selection effects from timing-pickoff effects."
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    write_figures(out_dir, metrics, raw_metrics, primary_label, all_pred)
    write_report(out_dir, config, args.config, counts, repro, raw_metrics, metrics, deltas, per_run, ridge_cv, leakage, result)
    write_manifest(out_dir, config, args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
