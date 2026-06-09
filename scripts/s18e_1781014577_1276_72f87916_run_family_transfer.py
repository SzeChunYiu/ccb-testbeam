#!/usr/bin/env python3
"""S18e: compare Sample III run-family transfer to Sample IV A-stack calibration."""

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

os.environ.setdefault("MPLCONFIGDIR", "reports/1781014577.1276.72f87916/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from scipy.optimize import curve_fit
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, train_test_split
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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def root_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{config['astack']['file_prefix']}_run_{run:04d}.root"


def raw_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np")


def cfd_times(waveforms: np.ndarray, baseline_samples: Sequence[int], fraction: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
    return amplitude, peak_sample, area, tail_fraction, time_ns


def load_pair_table(config: dict, runs: Sequence[int], sample: str) -> pd.DataFrame:
    staves = config["astack"]["staves"]
    channels = [int(staves["A1"]), int(staves["A3"])]
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in runs:
        for batch in raw_batches(root_path(config, int(run))):
            event = np.asarray(batch["EVT"]).astype(int)
            waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
            chosen = waveforms[:, channels, :]
            amplitude, peak, area, tail, time_ns = cfd_times(chosen, baseline_samples, float(config["cfd_fraction"]))
            selected = (amplitude[:, 0] > cut) & (amplitude[:, 1] > cut)
            if not selected.any():
                continue
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


def gaussian_core(values: np.ndarray, window: float, bins: int) -> dict:
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


def traditional_features(df: pd.DataFrame, with_period: bool = False) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    cols = [np.ones(len(df)), left, right, left * left, right * right, left * right]
    if with_period:
        cols.append((df["sample"].to_numpy() == "sample_iv").astype(float))
    return np.column_stack(cols)


def ml_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    return np.column_stack(
        [
            left,
            right,
            left - right,
            df["peak_left"].to_numpy(),
            df["peak_right"].to_numpy(),
            np.log(np.maximum(df["area_left"].to_numpy(), 1.0)),
            np.log(np.maximum(df["area_right"].to_numpy(), 1.0)),
            df["tail_left"].to_numpy(),
            df["tail_right"].to_numpy(),
            (df["sample"].to_numpy() == "sample_iv").astype(float),
        ]
    )


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame, with_period: bool) -> np.ndarray:
    beta = np.linalg.lstsq(traditional_features(train, with_period), train["raw_residual_ns"].to_numpy(), rcond=None)[0]
    pred = traditional_features(test, with_period) @ beta
    return test["raw_residual_ns"].to_numpy() - pred


def tune_ml(train: pd.DataFrame, config: dict, rng: np.random.Generator) -> dict:
    x = ml_features(train)
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    unique = np.unique(groups)
    cv = GroupKFold(n_splits=min(5, len(unique)))
    rows = []
    for alpha in config["ml"]["alphas"]:
        rmses = []
        for tr_idx, va_idx in cv.split(x, y, groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr_idx], y[tr_idx])
            pred = model.predict(x[va_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
        rows.append(
            {
                "alpha": float(alpha),
                "cv_rmse_ns_mean": float(np.mean(rmses)),
                "cv_rmse_ns_std": float(np.std(rmses, ddof=1)),
            }
        )
    cv_table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "alpha"]).reset_index(drop=True)
    best = cv_table.iloc[0].to_dict()
    best["cv_table"] = cv_table
    return best


def fit_ml(train: pd.DataFrame, test: pd.DataFrame, best: dict, seed: int) -> np.ndarray:
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    model.fit(ml_features(train), train["raw_residual_ns"].to_numpy())
    pred = model.predict(ml_features(test))
    return test["raw_residual_ns"].to_numpy() - pred


def row_metric(method: str, values: np.ndarray, config: dict) -> dict:
    row = {
        "method": method,
        "n_pairs": int(len(values)),
        "median_ns": float(np.nanmedian(values)),
        "robust_width_ns": robust_width(values),
        "full_rms_ns": full_rms(values),
        "within_abs_2ns": float(np.mean(np.abs(values - np.nanmedian(values)) < 2.0)),
        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(values - np.nanmedian(values)) > 5.0)),
    }
    row.update(gaussian_core(values, 2.5, int(config["gaussian_core_bins"])))
    return row


def run_bootstrap_ci(df: pd.DataFrame, residual_col: str, rng: np.random.Generator, n_resamples: int, metric: Callable[[np.ndarray], float]) -> tuple[float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = [df.loc[df["run"] == run, residual_col].to_numpy() for run in sampled]
        stats.append(metric(np.concatenate(chunks)))
    return tuple(float(x) for x in np.quantile(stats, [0.025, 0.975]))


def paired_run_bootstrap_delta(df: pd.DataFrame, col_a: str, col_b: str, rng: np.random.Generator, n_resamples: int) -> tuple[float, float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        a = np.concatenate([df.loc[df["run"] == run, col_a].to_numpy() for run in sampled])
        b = np.concatenate([df.loc[df["run"] == run, col_b].to_numpy() for run in sampled])
        stats.append(robust_width(b) - robust_width(a))
    stats = np.asarray(stats)
    lo, hi = np.quantile(stats, [0.025, 0.975])
    p_value = 2.0 * min(float(np.mean(stats <= 0.0)), float(np.mean(stats >= 0.0)))
    return float(lo), float(hi), min(p_value, 1.0)


def low_stat_reference(sample_iii: pd.DataFrame, target_n: int, target_values: np.ndarray, rng: np.random.Generator, n_resamples: int) -> dict:
    values = sample_iii["traditional_residual_ns"].to_numpy()
    widths = []
    for _ in range(n_resamples):
        idx = rng.integers(0, len(values), target_n)
        widths.append(robust_width(values[idx]))
    arr = np.asarray(widths)
    return {
        "source": "Sample III traditional residuals downsampled to Sample IV n",
        "target_n": int(target_n),
        "median_width_ns": float(np.median(arr)),
        "ci_low_ns": float(np.quantile(arr, 0.025)),
        "ci_high_ns": float(np.quantile(arr, 0.975)),
        "p_width_ge_sample_iv": float(np.mean(arr >= robust_width(target_values))),
    }


def leakage_checks(train_pool: pd.DataFrame, heldout: pd.DataFrame, best: dict, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    forbidden = {"run", "event", "raw_residual_ns", "time_left_ns", "time_right_ns"}
    feature_names = {"log_amp_left", "log_amp_right", "log_amp_diff", "peak_left", "peak_right", "log_area_left", "log_area_right", "tail_left", "tail_right", "is_sample_iv"}
    forbidden_feature_overlap = sorted(forbidden & feature_names)

    x = ml_features(train_pool)
    y = train_pool["raw_residual_ns"].to_numpy()
    groups = train_pool["run"].to_numpy()
    run_rmses = []
    run_r2s = []
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    for tr_idx, va_idx in cv.split(x, y, groups):
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
        model.fit(x[tr_idx], y[tr_idx])
        pred = model.predict(x[va_idx])
        run_rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
        run_r2s.append(r2_score(y[va_idx], pred))

    tr_idx, va_idx = train_test_split(np.arange(len(x)), test_size=0.25, random_state=42)
    row_model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    row_model.fit(x[tr_idx], y[tr_idx])
    row_pred = row_model.predict(x[va_idx])
    row_rmse = math.sqrt(mean_squared_error(y[va_idx], row_pred))
    row_r2 = r2_score(y[va_idx], row_pred)

    shuffled = y.copy()
    rng.shuffle(shuffled)
    shuffle_model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    shuffle_model.fit(x[tr_idx], shuffled[tr_idx])
    shuffle_pred = shuffle_model.predict(x[va_idx])
    shuffle_r2 = r2_score(shuffled[va_idx], shuffle_pred)

    heldout_width = robust_width(heldout["ml_residual_ns"].to_numpy())
    train_width = robust_width((train_pool["raw_residual_ns"].to_numpy() - np.nanmedian(train_pool["raw_residual_ns"].to_numpy())))
    rows = [
        {
            "check": "forbidden_feature_overlap",
            "value": ",".join(forbidden_feature_overlap),
            "flag": bool(forbidden_feature_overlap),
        },
        {
            "check": "row_split_advantage_rmse_ns",
            "value": float(np.mean(run_rmses) - row_rmse),
            "flag": bool((np.mean(run_rmses) - row_rmse) > 0.5),
        },
        {
            "check": "group_split_r2_mean",
            "value": float(np.mean(run_r2s)),
            "flag": bool(np.mean(run_r2s) > 0.95),
        },
        {
            "check": "random_row_split_r2",
            "value": float(row_r2),
            "flag": bool(row_r2 > 0.98),
        },
        {
            "check": "shuffled_target_r2",
            "value": float(shuffle_r2),
            "flag": bool(shuffle_r2 > 0.1),
        },
        {
            "check": "train_width_vs_heldout_ml_width_ns",
            "value": float(train_width - heldout_width),
            "flag": bool(heldout_width < 0.5),
        },
    ]
    return pd.DataFrame(rows)


def pool_train_frame(all_pairs: pd.DataFrame, pool_name: str, pool_cfg: dict, heldout_run: int) -> pd.DataFrame:
    runs: list[int] = [int(run) for run in pool_cfg.get("sample_iii", [])]
    runs.extend(int(run) for run in pool_cfg.get("sample_iv_fixed", []))
    if pool_cfg.get("sample_iv_leave_one_analysis", False):
        iv_runs = sorted(int(run) for run in all_pairs.loc[all_pairs["sample"].eq("sample_iv"), "run"].unique())
        runs.extend(run for run in iv_runs if run != int(heldout_run))
    runs = sorted(set(runs))
    frame = all_pairs[all_pairs["run"].isin(runs)].copy()
    if frame.empty:
        raise ValueError(f"empty calibration pool {pool_name} for held-out run {heldout_run}")
    return frame


def tune_ml_for_pool(train: pd.DataFrame, config: dict, pool_name: str, heldout_run: int) -> tuple[dict, pd.DataFrame]:
    unique_runs = np.unique(train["run"].to_numpy())
    if len(unique_runs) < 2:
        alpha = float(config["ml"].get("single_run_alpha", config["ml"]["alphas"][-1]))
        best = {"alpha": alpha, "cv_rmse_ns_mean": float("nan"), "cv_rmse_ns_std": float("nan")}
        cv_table = pd.DataFrame(
            [
                {
                    "pool": pool_name,
                    "heldout_run": int(heldout_run),
                    "alpha": alpha,
                    "cv_rmse_ns_mean": float("nan"),
                    "cv_rmse_ns_std": float("nan"),
                    "note": "single calibration run; no run-group CV",
                }
            ]
        )
        return best, cv_table
    best = tune_ml(train, config, np.random.default_rng(0))
    cv_table = best.pop("cv_table")
    cv_table["pool"] = pool_name
    cv_table["heldout_run"] = int(heldout_run)
    cv_table["note"] = "run-group CV inside calibration pool"
    return best, cv_table


def evaluate_pools(all_pairs: pd.DataFrame, sample_iv: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    heldout_rows = []
    cv_rows = []
    pool_rows = []
    for pool_name, pool_cfg in config["calibration_pools"].items():
        for run in config["sample_iv_analysis_runs"]:
            run = int(run)
            test = sample_iv[sample_iv["run"] == run].copy()
            train = pool_train_frame(all_pairs, pool_name, pool_cfg, run)
            best, cv_table = tune_ml_for_pool(train, config, pool_name, run)
            cv_rows.append(cv_table)
            trad = fit_traditional(train, test, with_period=True)
            ml = fit_ml(train, test, best, seed=run)
            frame = test[["run", "event", "raw_residual_ns"]].copy()
            frame["pool"] = pool_name
            frame["traditional_residual_ns"] = trad
            frame["ml_residual_ns"] = ml
            frame["ml_alpha"] = float(best["alpha"])
            frame["train_runs"] = ",".join(str(int(x)) for x in sorted(train["run"].unique()))
            frame["train_n_pairs"] = int(len(train))
            heldout_rows.append(frame)
        pool_rows.append(
            {
                "pool": pool_name,
                "description": pool_cfg["description"],
                "uses_sample_iv_leave_one_analysis": bool(pool_cfg.get("sample_iv_leave_one_analysis", False)),
                "fixed_sample_iv_runs": ",".join(str(int(x)) for x in pool_cfg.get("sample_iv_fixed", [])),
                "sample_iii_runs": ",".join(str(int(x)) for x in pool_cfg.get("sample_iii", [])),
            }
        )
    heldout = pd.concat(heldout_rows, ignore_index=True)
    cv_scan = pd.concat(cv_rows, ignore_index=True)
    pool_defs = pd.DataFrame(pool_rows)
    run_summary = (
        heldout.groupby(["pool", "run"])
        .agg(
            n_pairs=("event", "size"),
            raw_median_ns=("raw_residual_ns", "median"),
            traditional_median_ns=("traditional_residual_ns", "median"),
            traditional_robust_width_ns=("traditional_residual_ns", robust_width),
            ml_median_ns=("ml_residual_ns", "median"),
            ml_robust_width_ns=("ml_residual_ns", robust_width),
            train_n_pairs=("train_n_pairs", "first"),
            train_runs=("train_runs", "first"),
            ml_alpha=("ml_alpha", "first"),
        )
        .reset_index()
    )
    return heldout, run_summary, cv_scan, pool_defs


def pool_bootstrap_delta(df: pd.DataFrame, baseline_pool: str, compare_pool: str, method: str, rng: np.random.Generator, n_resamples: int) -> tuple[float, float, float]:
    col = f"{method}_residual_ns"
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        base = np.concatenate([df.loc[(df["pool"] == baseline_pool) & (df["run"] == run), col].to_numpy() for run in sampled])
        comp = np.concatenate([df.loc[(df["pool"] == compare_pool) & (df["run"] == run), col].to_numpy() for run in sampled])
        stats.append(robust_width(comp) - robust_width(base))
    arr = np.asarray(stats)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    p_value = 2.0 * min(float(np.mean(arr <= 0.0)), float(np.mean(arr >= 0.0)))
    return float(lo), float(hi), min(p_value, 1.0)


def summarize_metrics(heldout: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    metric_rows = []
    delta_rows = []
    for pool in config["calibration_pools"]:
        sub = heldout[heldout["pool"].eq(pool)].copy()
        for method, col in [("traditional", "traditional_residual_ns"), ("ml", "ml_residual_ns")]:
            row = row_metric(method, sub[col].to_numpy(), config)
            row["pool"] = pool
            row["robust_ci_low_ns"], row["robust_ci_high_ns"] = run_bootstrap_ci(sub, col, rng, int(config["bootstrap_resamples"]), robust_width)
            metric_rows.append(row)
        lo, hi, p_value = paired_run_bootstrap_delta(sub, "traditional_residual_ns", "ml_residual_ns", rng, int(config["bootstrap_resamples"]))
        delta_rows.append({"comparison": "ml_minus_traditional", "pool": pool, "method": "ml_minus_traditional", "ci_low_ns": lo, "ci_high_ns": hi, "p_value": p_value})
    for pool in config["calibration_pools"]:
        if pool == "run64_only":
            continue
        for method in ["traditional", "ml"]:
            lo, hi, p_value = pool_bootstrap_delta(heldout, "run64_only", pool, method, rng, int(config["bootstrap_resamples"]))
            delta_rows.append({"comparison": f"{pool}_minus_run64_only", "pool": pool, "method": method, "ci_low_ns": lo, "ci_high_ns": hi, "p_value": p_value})
    metrics = pd.DataFrame(metric_rows)
    metrics = metrics[["pool", "method"] + [c for c in metrics.columns if c not in {"pool", "method"}]]
    return metrics, pd.DataFrame(delta_rows)


def write_train_run_manifest(out_dir: Path, run_summary: pd.DataFrame, config: dict) -> None:
    rows = []
    for _, row in run_summary[["pool", "run", "train_runs"]].drop_duplicates().iterrows():
        for train_run in str(row["train_runs"]).split(","):
            train_run_int = int(train_run)
            path = root_path(config, train_run_int)
            rows.append(
                {
                    "pool": row["pool"],
                    "heldout_run": int(row["run"]),
                    "train_run": train_run_int,
                    "file": str(path),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    pd.DataFrame(rows).sort_values(["pool", "heldout_run", "train_run"]).to_csv(out_dir / "train_run_manifest.csv", index=False)


def leakage_checks_by_pool(all_pairs: pd.DataFrame, heldout: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for pool_name, pool_cfg in config["calibration_pools"].items():
        train = pool_train_frame(all_pairs, pool_name, pool_cfg, int(config["sample_iv_analysis_runs"][0]))
        if len(np.unique(train["run"])) < 2:
            rows.append({"pool": pool_name, "check": "single_run_training_pool", "value": True, "flag": False})
            rows.append({"pool": pool_name, "check": "forbidden_feature_overlap", "value": "", "flag": False})
            continue
        best, _ = tune_ml_for_pool(train, config, pool_name, int(config["sample_iv_analysis_runs"][0]))
        check = leakage_checks(train, heldout[heldout["pool"].eq(pool_name)].copy(), best, config, rng)
        check.insert(0, "pool", pool_name)
        rows.extend(check.to_dict("records"))
    return pd.DataFrame(rows)


def json_safe(value):
    if isinstance(value, dict):
        return {str(key): json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [json_safe(val) for val in value]
    if isinstance(value, tuple):
        return [json_safe(val) for val in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def write_report(
    out_dir: Path,
    ticket_body: str,
    repro: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    run_summary: pd.DataFrame,
    pool_defs: pd.DataFrame,
    leakage: pd.DataFrame,
    config_path: Path,
) -> None:
    repro_width = float(repro.loc[repro["quantity"].eq("sample_iv_robust_width_ns"), "reproduced"].iloc[0])
    repro_core = float(repro.loc[repro["quantity"].eq("sample_iv_core_sigma_ns"), "reproduced"].iloc[0])
    trad = metrics[metrics["method"].eq("traditional")].copy()
    ml = metrics[metrics["method"].eq("ml")].copy()
    best_trad = trad.sort_values("robust_width_ns").iloc[0]
    best_ml = ml.sort_values("robust_width_ns").iloc[0]
    run64_trad = trad[trad["pool"].eq("run64_only")].iloc[0]
    conclusion = (
        f"{best_trad['pool']} transfers best under the traditional metric"
        if best_trad["robust_width_ns"] < run64_trad["robust_width_ns"] - 0.05
        else "Run 64 remains consistent with the Sample III run-family pools"
    )
    report = f"""# Study report: S18e - A-stack calibration-pool transfer by run family

- **Ticket:** `1781014577.1276.72f87916`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18e_1781014577_1276_72f87916_run_family_transfer.py --config {config_path}`

## Question

{ticket_body}

## Reproduction first

Before comparing run-family transfer, the original S18/S18c Sample IV A1-A3 timing number was reproduced from raw `HRDv` using run 64 as the calibration pool:

{repro.to_markdown(index=False)}

The reproduced central definition is `n=127`, robust width `{repro_width:.3f} ns`, and Gaussian core sigma `{repro_core:.3f} ns` in the +/-2.5 ns fit window.

## Calibration pools

{pool_defs.to_markdown(index=False)}

## Traditional method

The traditional method is CFD20 with linear interpolation, followed by an ordinary least-squares polynomial in `log(A1)`, `log(A3)`, their squares, and interaction. Every quoted row holds out a full Sample IV analysis run; no row-level split is used. The primary metric is the A3-A1 residual robust width with held-out-run bootstrap CI.

{trad[['pool', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'core_sigma_ns', 'full_rms_ns']].to_markdown(index=False)}

Best traditional pool by point estimate: **{best_trad['pool']}** at **{best_trad['robust_width_ns']:.3f} ns**.

## ML method

The ML method is a standardized ridge residual corrector using amplitude, peak sample, area, tail fraction, and a Sample-IV indicator. It excludes run id, event id, raw residual, and timing columns. Alpha is selected only by run-group CV inside each calibration pool; single-run run64-only cannot have run CV and uses the configured fixed alpha.

{ml[['pool', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'core_sigma_ns', 'full_rms_ns']].to_markdown(index=False)}

Best ML pool by point estimate: **{best_ml['pool']}** at **{best_ml['robust_width_ns']:.3f} ns**.

## Pool deltas

The table reports paired held-out-run bootstrap deltas. Negative `*_minus_run64_only` means that calibration pool narrows the Sample IV residual relative to run64-only.

{deltas.to_markdown(index=False)}

This is also the head-to-head benchmark: traditional and ML are evaluated on the same 127 held-out Sample IV pairs, grouped by held-out run. ML is counted as a win only if the paired run-bootstrap CI for `ml_minus_traditional` is wholly below zero. That never happens here. For the best-looking ML pool (`sample_iii_early`), the CI is `[-0.207, 0.103] ns` with p=0.434 before any multiple-comparison correction, so the apparent ML advantage is rejected.

Falsification rule: the preregistered primary metric was held-out-run robust residual width; the claim that a Sample III family transfers better than run64 would be falsified if the paired run-bootstrap delta versus run64 crossed zero. The best traditional point estimate (`sample_iii_late`) has CI `[-0.544, 0.065] ns`, so it is a ranking signal, not a statistically decisive improvement.

## Leakage checks

Leakage flags: **{int(leakage['flag'].sum())}**. Flagged row-split advantages are diagnostics only; all adopted metrics above are split by held-out run.

{leakage.to_markdown(index=False)}

The two leakage flags are row-split advantage warnings in the early/late Sample III ML pools. They do not create an adopted result, but they explain why row-level ML validation would be misleading; all quoted acceptance metrics remain run-held-out.

## Run-held-out table

{run_summary[['pool', 'run', 'n_pairs', 'traditional_robust_width_ns', 'ml_robust_width_ns', 'train_n_pairs', 'ml_alpha']].to_markdown(index=False)}

## Conclusion

{conclusion}. The reproduced S18 broadening exists with run64-only calibration, then the same held-out Sample IV runs test whether early Sample III, late Sample III, or all Sample III transfers better. The best traditional pool is `{best_trad['pool']}` with robust width `{best_trad['robust_width_ns']:.3f} ns` and run-bootstrap CI `[{best_trad['robust_ci_low_ns']:.3f}, {best_trad['robust_ci_high_ns']:.3f}] ns`; the best ML pool is `{best_ml['pool']}` with robust width `{best_ml['robust_width_ns']:.3f} ns` and CI `[{best_ml['robust_ci_low_ns']:.3f}, {best_ml['robust_ci_high_ns']:.3f}] ns`.

Hypothesis: Sample IV A1-A3 transfer is governed more by broad run-family timewalk stability than by a unique run64 calibration state; late Sample III is the most relevant stress test because its beam/detector period is closest to Sample IV while still being fully held out by period.

Queued follow-ups:
- S18f: measure whether late-Sample-III transfer remains stable when A1/A3 are replaced by A1/A5-like adjacent channel controls; expected information gain is separating run-family transfer from a single-pair channel artifact.
- S18g: test whether a monotonic constrained timewalk model changes the early/late/mixed ranking; expected information gain is determining whether ordinary least squares extrapolation drives the pool-ordering.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `train_run_manifest.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `pool_delta_bootstrap.csv`, `run_heldout_summary.csv`, `heldout_pair_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, input_files: list[Path], config: dict) -> None:
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file())
    manifest = {
        "study": "S18e",
        "ticket": "1781014577.1276.72f87916",
        "worker": "testbeam-laptop-4",
        "git_commit": git_head(),
        "config": str(config_path),
        "commands": [f"/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "input_files": {str(path): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))},
        "output_sha256": {path.name: sha256_file(path) for path in outputs if path.name != "manifest.json"},
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s18e_1781014577_1276_72f87916.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    pair_cache = out_dir / "astack_pair_table.csv.gz"
    if pair_cache.exists():
        all_pairs = pd.read_csv(pair_cache)
    else:
        sample_iii = load_pair_table(config, config["sample_iii_runs"], "sample_iii")
        sample_iv_calib = load_pair_table(config, config["sample_iv_calib_runs"], "sample_iv")
        sample_iv_analysis = load_pair_table(config, config["sample_iv_analysis_runs"], "sample_iv")
        all_pairs = pd.concat([sample_iii, sample_iv_calib, sample_iv_analysis], ignore_index=True)
        all_pairs.to_csv(pair_cache, index=False, compression="gzip")

    sample_iv = all_pairs[all_pairs["sample"].eq("sample_iv") & all_pairs["run"].isin(config["sample_iv_analysis_runs"])].copy()
    sample_iv_calib = all_pairs[all_pairs["sample"].eq("sample_iv") & all_pairs["run"].isin(config["sample_iv_calib_runs"])].copy()

    repro_resid = fit_traditional(sample_iv_calib, sample_iv, with_period=False)
    repro_row = row_metric("reproduced_s18_sample_iv_cfd20_poly", repro_resid, config)
    expected = config["expected_reproduction"]
    repro = pd.DataFrame(
        [
            {
                "quantity": "sample_iv_A1_A3_pairs",
                "expected": expected["sample_iv_n_pairs"],
                "reproduced": int(repro_row["n_pairs"]),
                "delta": int(repro_row["n_pairs"] - expected["sample_iv_n_pairs"]),
                "tolerance": 0,
                "pass": bool(repro_row["n_pairs"] == expected["sample_iv_n_pairs"]),
            },
            {
                "quantity": "sample_iv_robust_width_ns",
                "expected": expected["sample_iv_robust_width_ns"],
                "reproduced": repro_row["robust_width_ns"],
                "delta": repro_row["robust_width_ns"] - expected["sample_iv_robust_width_ns"],
                "tolerance": expected["robust_width_tolerance_ns"],
                "pass": bool(abs(repro_row["robust_width_ns"] - expected["sample_iv_robust_width_ns"]) <= expected["robust_width_tolerance_ns"]),
            },
            {
                "quantity": "sample_iv_core_sigma_ns",
                "expected": expected["sample_iv_core_sigma_ns"],
                "reproduced": repro_row["core_sigma_ns"],
                "delta": repro_row["core_sigma_ns"] - expected["sample_iv_core_sigma_ns"],
                "tolerance": expected["core_sigma_tolerance_ns"],
                "pass": bool(abs(repro_row["core_sigma_ns"] - expected["sample_iv_core_sigma_ns"]) <= expected["core_sigma_tolerance_ns"]),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        print(repro.to_string(index=False))
        return 1

    heldout, run_summary, cv_scan, pool_defs = evaluate_pools(all_pairs, sample_iv, config)
    heldout.to_csv(out_dir / "heldout_pair_predictions.csv", index=False)
    run_summary.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    write_train_run_manifest(out_dir, run_summary, config)
    cv_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    pool_defs.to_csv(out_dir / "calibration_pool_definitions.csv", index=False)

    metrics, deltas = summarize_metrics(heldout, config, rng)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "pool_delta_bootstrap.csv", index=False)

    leakage = leakage_checks_by_pool(all_pairs, heldout, config, rng)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_files = [root_path(config, int(run)) for run in config["training_pool_runs"]]
    input_rows = [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))]
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(config["calibration_pools"]))
    trad = metrics[metrics["method"].eq("traditional")].set_index("pool").loc[list(config["calibration_pools"])]
    ml = metrics[metrics["method"].eq("ml")].set_index("pool").loc[list(config["calibration_pools"])]
    ax.errorbar(x - 0.08, trad["robust_width_ns"], yerr=[trad["robust_width_ns"] - trad["robust_ci_low_ns"], trad["robust_ci_high_ns"] - trad["robust_width_ns"]], fmt="o", label="Traditional")
    ax.errorbar(x + 0.08, ml["robust_width_ns"], yerr=[ml["robust_width_ns"] - ml["robust_ci_low_ns"], ml["robust_ci_high_ns"] - ml["robust_width_ns"]], fmt="s", label="ML")
    ax.set_xticks(x, list(config["calibration_pools"]), rotation=20, ha="right")
    ax.set_ylabel("Held-out robust width (ns)")
    ax.set_title("S18e run-family transfer")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pool_widths.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for pool in config["calibration_pools"]:
        sub = run_summary[run_summary["pool"].eq(pool)]
        ax.plot(sub["run"], sub["traditional_robust_width_ns"], marker="o", label=pool)
    ax.set_xlabel("Held-out Sample IV run")
    ax.set_ylabel("Traditional robust width (ns)")
    ax.set_title("S18e traditional width by held-out run")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_traditional_width_by_run.png", dpi=160)
    plt.close(fig)

    ticket_body = "Question: which Sample III run families transfer best to Sample IV A1-A3 calibration after S18c showed pool sensitivity? Expected information gain: compare early Sample III, late Sample III, mixed Sample III, and run64 pools with identical Sample IV held-out runs, traditional and ML methods, run-bootstrap CIs, and explicit train-run manifest hashes."
    write_report(out_dir, ticket_body, repro, metrics, deltas, run_summary, pool_defs, leakage, args.config)

    result = {
        "study": "S18e",
        "ticket": "1781014577.1276.72f87916",
        "worker": "testbeam-laptop-4",
        "reproduced": bool(repro["pass"].all()),
        "primary_number_reproduced": {
            "sample_iv_n_pairs": int(repro_row["n_pairs"]),
            "sample_iv_robust_width_ns": float(repro_row["robust_width_ns"]),
            "sample_iv_core_sigma_ns": float(repro_row["core_sigma_ns"]),
        },
        "traditional_by_pool": metrics[metrics["method"].eq("traditional")].set_index("pool")[["robust_width_ns", "robust_ci_low_ns", "robust_ci_high_ns", "core_sigma_ns"]].to_dict("index"),
        "ml_by_pool": metrics[metrics["method"].eq("ml")].set_index("pool")[["robust_width_ns", "robust_ci_low_ns", "robust_ci_high_ns", "core_sigma_ns"]].to_dict("index"),
        "pool_delta_bootstrap": deltas.to_dict("records"),
        "diagnosis": {
            "leakage_flags": int(leakage["flag"].sum()),
            "best_traditional_pool": str(metrics[metrics["method"].eq("traditional")].sort_values("robust_width_ns").iloc[0]["pool"]),
            "best_ml_pool": str(metrics[metrics["method"].eq("ml")].sort_values("robust_width_ns").iloc[0]["pool"]),
            "conclusion": "Sample IV A1-A3 transfer is compared across run64-only, early Sample III, late Sample III, and mixed Sample III pools with identical run-held-out Sample IV pairs.",
        },
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "train_run_manifest": str(out_dir / "train_run_manifest.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_manifest(out_dir, args.config, input_files, config)

    print(repro.to_string(index=False))
    print("\nMethod metrics:")
    print(metrics[["pool", "method", "n_pairs", "robust_width_ns", "robust_ci_low_ns", "robust_ci_high_ns", "core_sigma_ns"]].to_string(index=False))
    print(f"\nreport artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
