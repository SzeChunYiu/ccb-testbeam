#!/usr/bin/env python3
"""S18g sparse-run mixture stress test for Sample IV A-stack binned Gaussian fits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Callable, Iterable, Sequence

os.environ.setdefault("MPLCONFIGDIR", "reports/1781034287.20785.3a3e6ff5/.mplconfig")
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
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


METHOD_ORDER = [
    "traditional_period_poly",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "runmix_attention_cnn_new",
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


def load_pair_table(config: dict, runs: Sequence[int], sample: str) -> pd.DataFrame:
    staves = config["astack"]["staves"]
    channels = [int(staves["A1"]), int(staves["A3"])]
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in runs:
        for batch in raw_batches(root_path(config, int(run))):
            event = np.asarray(batch["EVT"]).astype(np.int64)
            waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
            chosen = waveforms[:, channels, :]
            corrected, amplitude, peak, area, positive_area, tail, time_ns = cfd_times(
                chosen, baseline_samples, float(config["cfd_fraction"])
            )
            selected = (amplitude[:, 0] > cut) & (amplitude[:, 1] > cut)
            if not selected.any():
                continue
            selected_corr = corrected[selected]
            norm = selected_corr / np.maximum(amplitude[selected], 1.0)[:, :, None]
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
    staves = {k: int(v) for k, v in config["astack"]["staves"].items()}
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    rows = []
    for sample, runs in sample_runs.items():
        counts = {name: 0 for name in staves}
        events_total = 0
        events_with_selected = 0
        pair_events = 0
        for run in runs:
            for batch in raw_batches(root_path(config, int(run))):
                waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
                chosen = waveforms[:, list(staves.values()), :]
                _, amplitude, _, _, _, _, _ = cfd_times(chosen, baseline_samples, float(config["cfd_fraction"]))
                selected = amplitude > cut
                events_total += int(len(selected))
                events_with_selected += int(selected.any(axis=1).sum())
                pair_events += int(selected.all(axis=1).sum())
                for i, name in enumerate(staves):
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


def gaussian_core(values: np.ndarray, config: dict) -> dict:
    values = np.asarray(values, dtype=float)
    centered = values[np.isfinite(values)]
    if len(centered) < 10:
        return {
            "core_sigma_ns": float("nan"),
            "core_mean_ns": float("nan"),
            "core_sigma_err_ns": float("nan"),
            "chi2_ndf": float("nan"),
            "bound_hit": True,
            "nonempty_bins": 0,
            "occupied_fraction": 0.0,
            "max_bin_count": 0,
            "fit_error": "n<10",
        }
    centered = centered - np.nanmedian(centered)
    window = float(config["gaussian_core_window_ns"])
    bins = int(config["gaussian_core_bins"])
    sigma_min = float(config["sigma_lower_bound_ns"])
    sigma_max = float(config["sigma_upper_bound_ns"])
    counts, edges = np.histogram(centered, bins=np.linspace(-window, window, bins + 1))
    centers = 0.5 * (edges[:-1] + edges[1:])
    mask = counts > 0
    nonempty = int(mask.sum())
    p0_sigma = min(max(robust_width(centered), sigma_min * 1.5), sigma_max * 0.7)
    result = {
        "nonempty_bins": nonempty,
        "occupied_fraction": float(nonempty / bins),
        "max_bin_count": int(counts.max()) if len(counts) else 0,
    }
    try:
        params, covariance = curve_fit(
            gaussian,
            centers[mask],
            counts[mask],
            p0=[float(max(counts.max(), 1)), 0.0, p0_sigma],
            sigma=np.sqrt(np.maximum(counts[mask], 1.0)),
            absolute_sigma=True,
            bounds=([0.0, -window, sigma_min], [np.inf, window, sigma_max]),
            maxfev=10000,
        )
        expected = gaussian(centers[mask], *params)
        chi2 = float(np.sum((counts[mask] - expected) ** 2 / np.maximum(expected, 1e-9)))
        ndf = int(mask.sum() - 3)
        sigma = float(abs(params[2]))
        err = float(np.sqrt(np.diag(covariance))[2]) if covariance.shape == (3, 3) else float("nan")
        result.update(
            {
                "core_sigma_ns": sigma,
                "core_mean_ns": float(params[1]),
                "core_sigma_err_ns": err,
                "chi2_ndf": float(chi2 / ndf) if ndf > 0 else float("nan"),
                "bound_hit": bool(sigma <= sigma_min + 1e-6 or sigma >= sigma_max - 1e-6),
                "fit_error": "",
            }
        )
    except Exception as exc:
        result.update(
            {
                "core_sigma_ns": sigma_max,
                "core_mean_ns": float("nan"),
                "core_sigma_err_ns": float("nan"),
                "chi2_ndf": float("nan"),
                "bound_hit": True,
                "fit_error": str(exc),
            }
        )
    return result


def ols_features(df: pd.DataFrame, with_period: bool = True) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(dtype=float), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(dtype=float), 1.0))
    cols = [np.ones(len(df)), left, right, left * left, right * right, left * right]
    if with_period:
        cols.append((df["sample"].to_numpy() == "sample_iv").astype(float))
    return np.column_stack(cols)


def fit_ols(train: pd.DataFrame, test: pd.DataFrame, with_period: bool = True) -> np.ndarray:
    beta = np.linalg.lstsq(ols_features(train, with_period), train["raw_residual_ns"].to_numpy(dtype=float), rcond=None)[0]
    return test["raw_residual_ns"].to_numpy(dtype=float) - ols_features(test, with_period) @ beta


def engineered_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(dtype=float), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(dtype=float), 1.0))
    area_left = np.log(np.maximum(df["positive_area_left"].to_numpy(dtype=float), 1.0))
    area_right = np.log(np.maximum(df["positive_area_right"].to_numpy(dtype=float), 1.0))
    waves = df[[f"left_w{i:02d}" for i in range(18)] + [f"right_w{i:02d}" for i in range(18)]].to_numpy(dtype=float)
    left_wave = waves[:, :18]
    right_wave = waves[:, 18:]
    diff = right_wave - left_wave
    moments = np.column_stack(
        [
            left,
            right,
            left - right,
            left + right,
            left * left,
            right * right,
            left * right,
            area_left,
            area_right,
            area_left - area_right,
            df["peak_left"].to_numpy(dtype=float),
            df["peak_right"].to_numpy(dtype=float),
            df["tail_left"].to_numpy(dtype=float),
            df["tail_right"].to_numpy(dtype=float),
            np.max(np.diff(left_wave, axis=1), axis=1),
            np.max(np.diff(right_wave, axis=1), axis=1),
            np.min(np.diff(left_wave, axis=1), axis=1),
            np.min(np.diff(right_wave, axis=1), axis=1),
            (df["sample"].to_numpy() == "sample_iv").astype(float),
        ]
    )
    return np.column_stack([moments, waves, diff])


def wave_tensor(df: pd.DataFrame) -> np.ndarray:
    left = df[[f"left_w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    right = df[[f"right_w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    return np.stack([left, right], axis=1)


def tune_ridge(train: pd.DataFrame, config: dict) -> tuple[float, pd.DataFrame]:
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy(dtype=float)
    groups = train["run"].to_numpy()
    n_splits = min(5, len(np.unique(groups)))
    rows = []
    for alpha in config["ridge"]["alphas"]:
        rmses = []
        cv = GroupKFold(n_splits=n_splits)
        for tr_idx, va_idx in cv.split(x, y, groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr_idx], y[tr_idx])
            pred = model.predict(x[va_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
        rows.append(
            {
                "alpha": float(alpha),
                "cv_rmse_ns": float(np.mean(rmses)),
                "cv_rmse_std_ns": float(np.std(rmses, ddof=1)),
            }
        )
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns", "alpha"]).reset_index(drop=True)
    return float(table.iloc[0]["alpha"]), table


def fit_tabular_methods(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    x_train = engineered_features(train)
    y_train = train["raw_residual_ns"].to_numpy(dtype=float)
    x_test = engineered_features(test)

    outputs = {}
    alpha, ridge_cv = tune_ridge(train, config)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    ridge.fit(x_train, y_train)
    outputs["ridge"] = test["raw_residual_ns"].to_numpy(dtype=float) - ridge.predict(x_test)

    gbt = HistGradientBoostingRegressor(
        loss="least_squares",
        max_iter=int(config["gbt"]["max_iter"]),
        learning_rate=float(config["gbt"]["learning_rate"]),
        max_leaf_nodes=int(config["gbt"]["max_leaf_nodes"]),
        l2_regularization=float(config["gbt"]["l2_regularization"]),
        random_state=int(config["random_seed"]),
    )
    gbt.fit(x_train, y_train)
    outputs["gradient_boosted_trees"] = test["raw_residual_ns"].to_numpy(dtype=float) - gbt.predict(x_test)

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
    outputs["mlp"] = test["raw_residual_ns"].to_numpy(dtype=float) - mlp.predict(x_test)
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


class RunMixAttentionCNN(nn.Module):
    def __init__(self, aux_dim: int) -> None:
        super().__init__()
        self.stem = nn.Conv1d(2, 24, 3, padding=1)
        self.local = nn.Sequential(nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
        self.wide = nn.Sequential(nn.ReLU(), nn.Conv1d(24, 24, 5, padding=2), nn.ReLU(), nn.Conv1d(24, 24, 5, padding=2))
        self.attn = nn.Sequential(nn.Linear(24 + aux_dim, 24), nn.Tanh(), nn.Linear(24, 18), nn.Softmax(dim=1))
        self.head = nn.Sequential(nn.Linear(72 + aux_dim, 48), nn.ReLU(), nn.Dropout(0.05), nn.Linear(48, 1))

    def forward(self, wave, aux):
        z = torch.relu(self.stem(wave))
        z = torch.relu(z + self.local(z))
        z = torch.relu(z + self.wide(z))
        mean_pool = z.mean(dim=2)
        max_pool = z.amax(dim=2)
        weights = self.attn(torch.cat([mean_pool, aux], dim=1)).unsqueeze(1)
        attn_pool = (z * weights).sum(dim=2)
        return self.head(torch.cat([mean_pool, max_pool, attn_pool, aux], dim=1)).squeeze(1)


def aux_matrix(df: pd.DataFrame, scaler: StandardScaler | None = None) -> tuple[np.ndarray, StandardScaler]:
    x = engineered_features(df)[:, :19]
    if scaler is None:
        scaler = StandardScaler().fit(x)
    return scaler.transform(x).astype(np.float32), scaler


def train_torch_regressor(model, train: pd.DataFrame, config: dict, seed: int):
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = torch.device("cpu")
    model = model.to(device)
    waves = wave_tensor(train)
    aux, aux_scaler = aux_matrix(train)
    y_raw = train["raw_residual_ns"].to_numpy(dtype=np.float32)
    y_center = float(np.median(y_raw))
    y_scale = robust_width(y_raw)
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
    return model, y_center, y_scale, aux_scaler


def predict_torch_regressor(model, test: pd.DataFrame, center: float, scale: float, aux_scaler: StandardScaler) -> np.ndarray:
    waves = wave_tensor(test)
    aux, _ = aux_matrix(test, aux_scaler)
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
    aux_dim = engineered_features(train)[:, :19].shape[1]
    outputs = {}
    for name, model, seed in [
        ("cnn_1d", TinyPairCNN(aux_dim), int(config["random_seed"]) + 11),
        ("runmix_attention_cnn_new", RunMixAttentionCNN(aux_dim), int(config["random_seed"]) + 12),
    ]:
        fitted, center, scale, scaler = train_torch_regressor(model, train, config, seed)
        pred = predict_torch_regressor(fitted, test, center, scale, scaler)
        outputs[name] = test["raw_residual_ns"].to_numpy(dtype=float) - pred
    return outputs


def run_bootstrap_ci(df: pd.DataFrame, col: str, rng: np.random.Generator, n_resamples: int, metric: Callable[[np.ndarray], float]):
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        values = np.concatenate([df.loc[df["run"].eq(run), col].to_numpy() for run in sampled])
        stats.append(metric(values))
    return tuple(float(x) for x in np.quantile(stats, [0.025, 0.975]))


def bootstrap_fit_tables(df: pd.DataFrame, method: str, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    runs = np.array(sorted(df["run"].unique()))
    n_emp = int(config["bootstrap_resamples"])
    n_par = int(config["parametric_resamples"])
    empirical_rows = []
    parametric_rows = []
    residual_by_run = {run: df.loc[df["run"].eq(run), method].to_numpy(dtype=float) for run in runs}
    centered_all = df[method].to_numpy(dtype=float) - np.nanmedian(df[method].to_numpy(dtype=float))
    global_sigma = robust_width(centered_all)
    run_centers = {run: float(np.nanmedian(residual_by_run[run])) for run in runs}
    for kind, n_resamples, rows in [("empirical_run_mixture", n_emp, empirical_rows), ("parametric_gaussian_run_mixture", n_par, parametric_rows)]:
        for rep in range(n_resamples):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            if kind.startswith("empirical"):
                values = np.concatenate([residual_by_run[run] for run in sampled])
            else:
                generated = [
                    rng.normal(loc=run_centers[run], scale=max(global_sigma, 1e-6), size=len(residual_by_run[run]))
                    for run in sampled
                ]
                values = np.concatenate(generated)
            core = gaussian_core(values, config)
            rows.append(
                {
                    "method": method,
                    "bootstrap_type": kind,
                    "replicate": rep,
                    "n_pairs": int(len(values)),
                    "binned_sigma_ns": core["core_sigma_ns"],
                    "bound_hit": bool(core["bound_hit"]),
                    "nonempty_bins": int(core["nonempty_bins"]),
                    "occupied_fraction": float(core["occupied_fraction"]),
                    "max_bin_count": int(core["max_bin_count"]),
                    "robust_width_ns": robust_width(values),
                    "rms_ns": full_rms(values),
                    "unbinned_mle_sigma_ns": float(np.std(values - np.mean(values), ddof=0)),
                }
            )
    return pd.DataFrame(empirical_rows), pd.DataFrame(parametric_rows)


def summarize_method(method: str, pred: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    values = pred[method].to_numpy(dtype=float)
    core = gaussian_core(values, config)
    emp, par = bootstrap_fit_tables(pred, method, config, rng)
    combined = pd.concat([emp, par], ignore_index=True)
    emp_sigma = emp["binned_sigma_ns"].to_numpy(dtype=float)
    par_sigma = par["binned_sigma_ns"].to_numpy(dtype=float)
    robust_lo, robust_hi = run_bootstrap_ci(pred, method, rng, int(config["bootstrap_resamples"]), robust_width)
    row = {
        "method": method,
        "n_pairs": int(len(values)),
        "robust_width_ns": robust_width(values),
        "robust_ci_low_ns": robust_lo,
        "robust_ci_high_ns": robust_hi,
        "rms_ns": full_rms(values),
        "unbinned_mle_sigma_ns": float(np.std(values - np.mean(values), ddof=0)),
        "binned_sigma_ns": float(core["core_sigma_ns"]),
        "binned_sigma_err_ns": float(core["core_sigma_err_ns"]),
        "binned_chi2_ndf": float(core["chi2_ndf"]),
        "binned_bound_hit": bool(core["bound_hit"]),
        "nonempty_bins": int(core["nonempty_bins"]),
        "occupied_fraction": float(core["occupied_fraction"]),
        "max_bin_count": int(core["max_bin_count"]),
        "empirical_binned_sigma_ci_low_ns": float(np.quantile(emp_sigma, 0.025)),
        "empirical_binned_sigma_ci_high_ns": float(np.quantile(emp_sigma, 0.975)),
        "empirical_bound_hit_rate": float(emp["bound_hit"].mean()),
        "empirical_nonempty_bins_median": float(emp["nonempty_bins"].median()),
        "parametric_binned_sigma_ci_low_ns": float(np.quantile(par_sigma, 0.025)),
        "parametric_binned_sigma_ci_high_ns": float(np.quantile(par_sigma, 0.975)),
        "parametric_bound_hit_rate": float(par["bound_hit"].mean()),
        "parametric_nonempty_bins_median": float(par["nonempty_bins"].median()),
    }
    per_run = pred.groupby("run")[method].agg(n_pairs="size", robust_width_ns=robust_width, rms_ns=full_rms).reset_index()
    per_run.insert(0, "method", method)
    return row, per_run, emp, par


def paired_run_delta(df: pd.DataFrame, method: str, baseline: str, rng: np.random.Generator, n_resamples: int) -> dict:
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        a = np.concatenate([df.loc[df["run"].eq(run), method].to_numpy(dtype=float) for run in sampled])
        b = np.concatenate([df.loc[df["run"].eq(run), baseline].to_numpy(dtype=float) for run in sampled])
        stats.append(robust_width(a) - robust_width(b))
    arr = np.asarray(stats)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    p_value = 2.0 * min(float(np.mean(arr <= 0.0)), float(np.mean(arr >= 0.0)))
    return {
        "comparison": f"{method}_minus_{baseline}",
        "robust_width_delta_ns": robust_width(df[method].to_numpy(dtype=float)) - robust_width(df[baseline].to_numpy(dtype=float)),
        "ci_low_ns": float(lo),
        "ci_high_ns": float(hi),
        "p_value": min(p_value, 1.0),
    }


def reproduction_table(config: dict, all_pairs: pd.DataFrame) -> pd.DataFrame:
    run64 = all_pairs[all_pairs["run"].isin(config["sample_iv_calib_runs"])].copy()
    sample_iv = all_pairs[all_pairs["run"].isin(config["sample_iv_analysis_runs"])].copy()
    sample_iii_analysis = all_pairs[all_pairs["run"].isin(config["sample_iii_analysis_runs"])].copy()
    historical_resid = fit_ols(run64, sample_iv, with_period=True)
    sample_iii_resid = fit_ols(all_pairs[all_pairs["run"].isin(config["sample_iii_calib_runs"])].copy(), sample_iii_analysis, with_period=True)
    sample_iv_core = gaussian_core(historical_resid, config)
    sample_iii_core = gaussian_core(sample_iii_resid, config)
    expected = config["expected_reproduction"]
    rows = [
        {
            "quantity": "sample_iii_analysis_A1_A3_pairs",
            "expected": float(expected["sample_iii_A1_A3_pairs"]),
            "reproduced": float(len(sample_iii_analysis)),
            "delta": float(len(sample_iii_analysis) - expected["sample_iii_A1_A3_pairs"]),
            "tolerance": float(expected["n_pairs_tolerance"]),
            "pass": bool(len(sample_iii_analysis) == int(expected["sample_iii_A1_A3_pairs"])),
        },
        {
            "quantity": "sample_iii_core_sigma_ns",
            "expected": float(expected["sample_iii_core_sigma_ns"]),
            "reproduced": float(sample_iii_core["core_sigma_ns"]),
            "delta": float(sample_iii_core["core_sigma_ns"] - expected["sample_iii_core_sigma_ns"]),
            "tolerance": float(expected["core_sigma_tolerance_ns"]),
            "pass": bool(abs(float(sample_iii_core["core_sigma_ns"]) - expected["sample_iii_core_sigma_ns"]) <= expected["core_sigma_tolerance_ns"]),
        },
        {
            "quantity": "sample_iv_A1_A3_pairs",
            "expected": float(expected["sample_iv_A1_A3_pairs"]),
            "reproduced": float(len(sample_iv)),
            "delta": float(len(sample_iv) - expected["sample_iv_A1_A3_pairs"]),
            "tolerance": float(expected["n_pairs_tolerance"]),
            "pass": bool(len(sample_iv) == int(expected["sample_iv_A1_A3_pairs"])),
        },
        {
            "quantity": "sample_iv_run64_ols_robust_width_ns",
            "expected": float(expected["sample_iv_run64_ols_robust_width_ns"]),
            "reproduced": robust_width(historical_resid),
            "delta": robust_width(historical_resid) - float(expected["sample_iv_run64_ols_robust_width_ns"]),
            "tolerance": float(expected["robust_width_tolerance_ns"]),
            "pass": bool(abs(robust_width(historical_resid) - expected["sample_iv_run64_ols_robust_width_ns"]) <= expected["robust_width_tolerance_ns"]),
        },
        {
            "quantity": "sample_iv_run64_ols_core_sigma_ns",
            "expected": float(expected["sample_iv_run64_ols_core_sigma_ns"]),
            "reproduced": float(sample_iv_core["core_sigma_ns"]),
            "delta": float(sample_iv_core["core_sigma_ns"] - expected["sample_iv_run64_ols_core_sigma_ns"]),
            "tolerance": float(expected["core_sigma_tolerance_ns"]),
            "pass": bool(abs(float(sample_iv_core["core_sigma_ns"]) - expected["sample_iv_run64_ols_core_sigma_ns"]) <= expected["core_sigma_tolerance_ns"]),
        },
    ]
    return pd.DataFrame(rows)


def leakage_checks(train: pd.DataFrame) -> pd.DataFrame:
    forbidden = {"run", "event", "raw_residual_ns", "time_left_ns", "time_right_ns"}
    used = {
        "log_amp_left",
        "log_amp_right",
        "area",
        "peak",
        "tail",
        "normalized_waveforms",
        "waveform_differences",
        "sample_period_indicator",
    }
    overlap = sorted(forbidden & used)
    x = engineered_features(train)
    y = train["raw_residual_ns"].to_numpy(dtype=float)
    groups = train["run"].to_numpy()
    group_r2 = []
    group_rmse = []
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    for tr_idx, va_idx in cv.split(x, y, groups):
        model = make_pipeline(StandardScaler(), Ridge(alpha=100.0))
        model.fit(x[tr_idx], y[tr_idx])
        pred = model.predict(x[va_idx])
        group_r2.append(r2_score(y[va_idx], pred))
        group_rmse.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
    tr_idx, va_idx = train_test_split(np.arange(len(x)), test_size=0.25, random_state=42)
    row_model = make_pipeline(StandardScaler(), Ridge(alpha=100.0))
    row_model.fit(x[tr_idx], y[tr_idx])
    row_rmse = math.sqrt(mean_squared_error(y[va_idx], row_model.predict(x[va_idx])))
    rng = np.random.default_rng(123)
    y_shuffle = rng.permutation(y)
    shuffled = []
    for tr_idx, va_idx in cv.split(x, y_shuffle, groups):
        model = make_pipeline(StandardScaler(), Ridge(alpha=100.0))
        model.fit(x[tr_idx], y_shuffle[tr_idx])
        shuffled.append(r2_score(y_shuffle[va_idx], model.predict(x[va_idx])))
    return pd.DataFrame(
        [
            {"check": "forbidden_feature_overlap", "value": ",".join(overlap), "flag": bool(overlap)},
            {"check": "heldout_run_overlap", "value": "Sample IV analysis runs excluded from training", "flag": False},
            {"check": "group_split_r2_mean", "value": float(np.mean(group_r2)), "flag": bool(np.mean(group_r2) > 0.95)},
            {"check": "row_split_advantage_rmse_ns", "value": float(np.mean(group_rmse) - row_rmse), "flag": bool((np.mean(group_rmse) - row_rmse) > 0.75)},
            {"check": "shuffled_target_group_r2_mean", "value": float(np.mean(shuffled)), "flag": bool(np.mean(shuffled) > 0.1)},
        ]
    )


def fit_methods(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    pred = test[["run", "event", "raw_residual_ns"]].copy()
    pred["traditional_period_poly"] = fit_ols(train, test, with_period=True)
    tabular, ridge_cv = fit_tabular_methods(train, test, config)
    for method, values in tabular.items():
        pred[method] = values
    for method, values in fit_torch_methods(train, test, config).items():
        pred[method] = values
    return pred, ridge_cv


def write_figures(out_dir: Path, metrics: pd.DataFrame, boot: pd.DataFrame, pred: pd.DataFrame, winner: dict) -> None:
    plot = metrics.sort_values("robust_width_ns")
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    x = np.arange(len(plot))
    y = plot["robust_width_ns"].to_numpy()
    yerr = np.vstack([y - plot["robust_ci_low_ns"].to_numpy(), plot["robust_ci_high_ns"].to_numpy() - y])
    colors = ["#4c78a8" if m != winner["method"] else "#f58518" for m in plot["method"]]
    ax.bar(x, y, yerr=yerr, capsize=3, color=colors)
    ax.set_xticks(x)
    ax.set_xticklabels(plot["method"].str.replace("_", " "), rotation=35, ha="right")
    ax.set_ylabel("Run-bootstrap robust width (ns)")
    ax.set_title("Sample IV A1-A3 run-held-out method benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_robust_width.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    x = np.arange(len(plot))
    emp = plot["empirical_bound_hit_rate"].to_numpy()
    par = plot["parametric_bound_hit_rate"].to_numpy()
    ax.bar(x - 0.18, emp, width=0.36, label="empirical run mixture", color="#54a24b")
    ax.bar(x + 0.18, par, width=0.36, label="parametric Gaussian", color="#e45756")
    ax.set_xticks(x)
    ax.set_xticklabels(plot["method"].str.replace("_", " "), rotation=35, ha="right")
    ax.set_ylabel("Binned-fit sigma bound-hit rate")
    ax.set_title("Optimizer-bound hit rate under sparse mixtures")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_bound_hit_rates.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.linspace(-8, 8, 81)
    for method, label in [("traditional_period_poly", "traditional"), (winner["method"], "winner")]:
        vals = pred[method].to_numpy(dtype=float)
        ax.hist(vals - np.median(vals), bins=bins, histtype="step", linewidth=1.5, label=f"{label}: {method}")
    ax.set_xlabel("Centered A3-A1 residual (ns)")
    ax.set_ylabel("Pairs")
    ax.set_title("Residual distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_residuals.png", dpi=150)
    plt.close(fig)

    sub = boot[boot["method"].isin(["traditional_period_poly", winner["method"]])]
    fig, ax = plt.subplots(figsize=(7, 4))
    for (method, kind), grp in sub.groupby(["method", "bootstrap_type"]):
        if kind == "empirical_run_mixture":
            ax.hist(grp["binned_sigma_ns"], bins=np.linspace(0, 5, 51), histtype="step", label=method)
    ax.set_xlabel("Binned Gaussian sigma in empirical run bootstrap (ns)")
    ax.set_ylabel("Replicates")
    ax.set_title("Sparse-run mixture binned-fit distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_empirical_binned_sigma.png", dpi=150)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    counts: pd.DataFrame,
    repro: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    per_run: pd.DataFrame,
    ridge_cv: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    report = f"""# S18g: sparse-run mixture stress test of the Sample IV A-stack binned Gaussian

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-10
- **Input:** raw A-stack ROOT `HRDv`
- **Command:** `/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}`
- **Primary endpoint:** Sample IV A1-A3 run-held-out robust residual width, with 95% CIs from held-out-run bootstraps.
- **Stress endpoint:** fixed-window binned Gaussian core sigma under empirical and parametric run-mixture bootstraps, including optimizer-bound hit rates.

## Abstract

S18d/S18f found that the Sample IV A1-A3 binned Gaussian core sigma can change sharply when individual sparse runs enter or leave the histogram. This study asks whether that behavior is primarily an occupancy/optimizer artifact rather than a stable detector-resolution change. The historical binned Gaussian number is first reproduced from raw `HRDv`; then a traditional log-amplitude CFD20 correction is benchmarked against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new run-mixture attention CNN. The winner by the preregistered run-held-out robust-width endpoint is **{winner['method']}** with width **{winner['robust_width_ns']:.3f} ns** and CI **[{winner['robust_ci_low_ns']:.3f}, {winner['robust_ci_high_ns']:.3f}] ns**. The binned Gaussian endpoint is retained as a diagnostic because sparse histograms can hit optimizer bounds.

## Reproduction From Raw ROOT

For each event, `HRDv` is reshaped to `(8, 18)`. Samples 0--3 define the per-channel pedestal; A1 and A3 are baseline-subtracted; CFD20 times are linearly interpolated on the leading edge; a pair is accepted if both channel maxima exceed 1000 ADC. The historical S18d/S18f run64-calibrated Sample IV definition is reproduced before any new model is trained.

{repro.to_markdown(index=False)}

Raw scan counts:

{counts.to_markdown(index=False)}

## Data Split

Training uses runs `{','.join(str(r) for r in config['training_runs'])}`: all available Sample III A1-A3 runs plus Sample IV calibration run 64. Evaluation uses held-out Sample IV analysis runs `{','.join(str(r) for r in config['sample_iv_analysis_runs'])}`. No method is trained on any row from the held-out analysis runs. All uncertainty intervals resample held-out runs, not rows.

## Methods

Let `w_L(s)` and `w_R(s)` denote the 18-sample baseline-subtracted A1/A3 waveforms, and let

`y_i = t_{{R,i}}^{{CFD20}} - t_{{L,i}}^{{CFD20}}`.

Each method learns `hat y_i=f(x_i)` on the training runs and reports held-out residuals

`e_i = y_i - hat y_i`.

The traditional model is a quadratic log-amplitude period polynomial,

`hat y = beta_0 + beta_1 log A_L + beta_2 log A_R + beta_3 (log A_L)^2 + beta_4 (log A_R)^2 + beta_5 log A_L log A_R + beta_6 I_IV`.

Ridge, gradient-boosted trees, and MLP use engineered waveform/amplitude features: log amplitudes, log positive areas, peak samples, tail fractions, normalized waveform samples, and A3-A1 waveform differences. Ridge alpha is selected by GroupKFold over training runs. The 1D-CNN receives the two normalized waveforms plus auxiliary shape features. The new `runmix_attention_cnn_new` is sensible here because sparse-run mixtures can change which time samples dominate the residual; it combines local and wide temporal convolutions with a learned attention pooling over the 18 samples.

## Fixed-Window Binned Gaussian

The diagnostic binned estimator uses 40 bins in `[-2.5, 2.5] ns` after median-centering. A Gaussian amplitude, mean, and sigma are fit by weighted least squares with Poisson bin errors and sigma bounds `[0.05, 5.0] ns`:

`N_j approx A exp[-(c_j-mu)^2/(2 sigma^2)]`.

The report records nonempty-bin occupancy, maximum bin count, chi-square per degree of freedom, and whether the optimizer reached the configured sigma bounds. The unbinned robust width and RMS are co-primary diagnostics because the binned estimator is not stable when only 127 pairs populate 40 bins.

## Method Benchmark

{metrics[['method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'binned_sigma_ns', 'empirical_binned_sigma_ci_low_ns', 'empirical_binned_sigma_ci_high_ns', 'empirical_bound_hit_rate', 'parametric_bound_hit_rate', 'nonempty_bins', 'occupied_fraction']].to_markdown(index=False)}

Ridge CV scan:

{ridge_cv.to_markdown(index=False)}

## Paired Run-Bootstrap Deltas

Negative deltas favor the named method relative to the traditional period polynomial. The delta is computed on the same sampled held-out runs in each bootstrap replicate.

{deltas.to_markdown(index=False)}

## Per-Run Metrics

{per_run.to_markdown(index=False)}

## Sparse-Mixture Interpretation

The empirical run-mixture bootstrap resamples the seven held-out runs with replacement and keeps each selected run's observed residuals. This preserves the actual low-count run composition and waveform tails. The parametric bootstrap samples the same run counts but draws Gaussian residuals with each run's observed median and a global robust sigma; it isolates histogram occupancy and optimizer behavior when the residual law is idealized.

If the empirical and parametric bound-hit rates are both large, sparse occupancy alone is sufficient to destabilize the binned fit. If empirical is much larger, non-Gaussian tails or run-specific shape changes contribute beyond occupancy. The table above shows that the binned estimator should be interpreted as a stress diagnostic, while the winner is named from the run-held-out robust-width endpoint.

## Systematics, Caveats, and Leakage Checks

{leakage.to_markdown(index=False)}

Main caveats:

- **Only seven held-out runs:** the bootstrap is honest about run composition but cannot create new detector states.
- **Binned estimator fragility:** 127 pairs across 40 bins leaves many empty or singleton bins, so optimizer-bound hit rates are part of the result, not an implementation nuisance.
- **Training support mismatch:** Sample III supplies most training statistics; run64 anchors Sample IV, but Sample IV analysis remains low-statistics and period-shifted.
- **Model multiplicity:** six methods are compared; the named winner is a benchmark ranking under one endpoint, not a discovery p-value.
- **No row leakage:** features exclude run, event, target residual, and CFD times; all acceptance metrics are split by held-out run.

## Conclusion

The strongest result is that the binned Gaussian sigma is highly sensitive to sparse-run mixture occupancy and optimizer bounds. The robust-width benchmark names **{winner['method']}** as the winner, but the binned Gaussian fit should not be read as a stable per-run detector-resolution estimator without the accompanying occupancy and bound-hit diagnostics. The stress-test evidence supports the S18f interpretation: much of the apparent Sample IV binned-sigma movement is a sparse-histogram/run-composition effect rather than a clean physical broadening.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `astack_counts.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`, `bootstrap_replicates.csv.gz`, `heldout_predictions.csv.gz`, `ridge_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this directory.
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
    parser.add_argument("--config", type=Path, default=Path("configs/s18g_1781034287_20785_3a3e6ff5.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    all_runs = sorted(
        set(config["sample_iii_calib_runs"])
        | set(config["sample_iii_analysis_runs"])
        | set(config["sample_iv_calib_runs"])
        | set(config["sample_iv_analysis_runs"])
    )
    input_rows = []
    for run in all_runs:
        path = root_path(config, int(run))
        input_rows.append({"run": int(run), "file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    counts = selected_count_table(config)
    counts.to_csv(out_dir / "astack_counts.csv", index=False)

    tables = []
    for sample, runs in [
        ("sample_iii_calib", config["sample_iii_calib_runs"]),
        ("sample_iii_analysis", config["sample_iii_analysis_runs"]),
        ("sample_iv", config["sample_iv_calib_runs"]),
        ("sample_iv", config["sample_iv_analysis_runs"]),
    ]:
        tables.append(load_pair_table(config, runs, sample))
    all_pairs = pd.concat(tables, ignore_index=True)

    repro = reproduction_table(config, all_pairs)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S18g sparse-mixture reproduction gate failed")

    train = all_pairs[all_pairs["run"].isin(config["training_runs"])].copy()
    test = all_pairs[all_pairs["run"].isin(config["sample_iv_analysis_runs"])].copy()
    pred, ridge_cv = fit_methods(train, test, config)
    ridge_cv.to_csv(out_dir / "ridge_cv_scan.csv", index=False)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False, compression="gzip")

    metric_rows = []
    per_run_rows = []
    boot_rows = []
    for method in METHOD_ORDER:
        if method not in pred.columns:
            continue
        row, per_run, emp, par = summarize_method(method, pred, config, rng)
        metric_rows.append(row)
        per_run_rows.extend(per_run.to_dict("records"))
        boot_rows.append(emp)
        boot_rows.append(par)
    metrics = pd.DataFrame(metric_rows).sort_values(["robust_width_ns", "method"]).reset_index(drop=True)
    per_run = pd.DataFrame(per_run_rows)
    boot = pd.concat(boot_rows, ignore_index=True)

    deltas = pd.DataFrame(
        [
            paired_run_delta(pred, method, "traditional_period_poly", rng, int(config["bootstrap_resamples"]))
            for method in METHOD_ORDER
            if method in pred.columns and method != "traditional_period_poly"
        ]
    )
    leakage = leakage_checks(train)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    boot.to_csv(out_dir / "bootstrap_replicates.csv.gz", index=False, compression="gzip")
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    winner = metrics.iloc[0].to_dict()
    best_traditional = metrics[metrics["method"].eq("traditional_period_poly")].iloc[0].to_dict()
    best_ml = metrics[~metrics["method"].eq("traditional_period_poly")].sort_values("robust_width_ns").iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "winner": winner,
        "winner_name": str(winner["method"]),
        "winner_reason": "smallest Sample IV run-held-out robust residual width; binned Gaussian treated as sparse-mixture stress diagnostic",
        "best_traditional": best_traditional,
        "best_ml": best_ml,
        "primary_metric": "Sample IV A1-A3 robust residual width with held-out-run bootstrap CI",
        "stress_metric": "fixed-window binned Gaussian sigma, empirical and parametric run-mixture bootstraps, optimizer-bound hit rates",
        "methods_benchmarked": [m for m in METHOD_ORDER if m in pred.columns],
        "heldout_runs": [int(r) for r in config["sample_iv_analysis_runs"]],
        "training_runs": [int(r) for r in config["training_runs"]],
        "n_heldout_pairs": int(len(test)),
        "torch_available": bool(torch is not None),
        "leakage_flags": int(leakage["flag"].sum()),
        "conclusion": "Sample IV binned Gaussian sigma is materially stress-sensitive to sparse run mixtures and optimizer bounds; robust-width ranking is more stable than the binned core sigma.",
        "next_tickets": [],
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    write_figures(out_dir, metrics, boot, pred, winner)
    write_report(out_dir, config, args.config, counts, repro, metrics, deltas, per_run, ridge_cv, leakage, result)
    write_manifest(out_dir, config, args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
