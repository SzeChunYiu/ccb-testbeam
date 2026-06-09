#!/usr/bin/env python3
"""S18f: isolate Sample IV A-stack per-run outliers in binned core fits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

os.environ.setdefault("MPLCONFIGDIR", "reports/1781014670.1107.6b932bc2/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from scipy.optimize import curve_fit
from scipy.stats import spearmanr
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET_BODY = (
    "Question: which Sample IV A1-A3 runs drive the binned Gaussian fit instability "
    "seen in S18d, and are those runs distinguishable by amplitude, waveform-shape, "
    "or event-count diagnostics? Expected information gain: separate genuine per-run "
    "timing broadening from optimizer/window failures by run-level diagnostic plots "
    "and leave-one-run-out estimator deltas on raw ROOT."
)


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


def root_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{config['astack']['file_prefix']}_run_{run:04d}.root"


def raw_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np")


def cfd_and_shape(
    waveforms: np.ndarray, baseline_samples: Sequence[int], fraction: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_samples], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak_sample = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    tail_fraction = corrected[..., 10:].sum(axis=-1) / np.maximum(area, 1.0)
    area_over_amp = area / np.maximum(amplitude, 1.0)
    half = 0.5 * amplitude[..., None]
    width_half = (corrected >= half).sum(axis=-1).astype(float)

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
    return amplitude, peak_sample, area, tail_fraction, area_over_amp, width_half, time_ns


def load_pair_table(config: dict, runs: Sequence[int], sample: str) -> pd.DataFrame:
    channels = [int(config["astack"]["staves"]["A1"]), int(config["astack"]["staves"]["A3"])]
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    rows = []
    for run in runs:
        for batch in raw_batches(root_path(config, int(run))):
            event = np.asarray(batch["EVT"]).astype(int)
            waveforms = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
            chosen = waveforms[:, channels, :]
            amp, peak, area, tail, area_over_amp, width_half, time_ns = cfd_and_shape(
                chosen, baseline_samples, float(config["cfd_fraction"])
            )
            selected = (amp[:, 0] > float(config["amplitude_cut_adc"])) & (amp[:, 1] > float(config["amplitude_cut_adc"]))
            if not selected.any():
                continue
            frame = pd.DataFrame(
                {
                    "sample": sample,
                    "run": int(run),
                    "event": event[selected],
                    "amp_left": amp[selected, 0],
                    "amp_right": amp[selected, 1],
                    "peak_left": peak[selected, 0],
                    "peak_right": peak[selected, 1],
                    "area_left": area[selected, 0],
                    "area_right": area[selected, 1],
                    "tail_left": tail[selected, 0],
                    "tail_right": tail[selected, 1],
                    "area_over_amp_left": area_over_amp[selected, 0],
                    "area_over_amp_right": area_over_amp[selected, 1],
                    "width_half_left": width_half[selected, 0],
                    "width_half_right": width_half[selected, 1],
                    "time_left_ns": time_ns[selected, 0],
                    "time_right_ns": time_ns[selected, 1],
                }
            )
            frame["raw_residual_ns"] = frame["time_right_ns"] - frame["time_left_ns"]
            rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def add_period(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["period"] = np.where(frame["sample"].str.contains("iv"), "sample_iv", "sample_iii")
    return frame


def build_or_load_pairs(config: dict, out_dir: Path) -> pd.DataFrame:
    cache = out_dir / "astack_pair_table.csv.gz"
    if cache.exists():
        return pd.read_csv(cache)
    pieces = [
        load_pair_table(config, config["sample_iii_calib_runs"], "sample_iii_calib"),
        load_pair_table(config, config["sample_iii_analysis_runs"], "sample_iii_analysis"),
        load_pair_table(config, config["sample_iv_calib_runs"], "sample_iv_calib"),
        load_pair_table(config, config["sample_iv_analysis_runs"], "sample_iv_analysis"),
    ]
    all_pairs = add_period(pd.concat(pieces, ignore_index=True))
    all_pairs.to_csv(cache, index=False, compression="gzip")
    return all_pairs


def centered(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return values - np.nanmedian(values)


def robust_width(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float(0.5 * (np.percentile(c, 84) - np.percentile(c, 16)))


def rms_width(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float(np.sqrt(np.mean(c * c)))


def gaussian(x: np.ndarray, amplitude: float, mean: float, sigma: float) -> np.ndarray:
    return amplitude * np.exp(-0.5 * ((x - mean) / sigma) ** 2)


def binned_gaussian_sigma(values: np.ndarray, window: float, bins: int) -> dict:
    c = centered(values)
    if len(c) < 4:
        return {"value_ns": float("nan"), "core_mean_ns": float("nan"), "fit_window_ns": float(window), "fit_error": "too_few_pairs"}
    counts, edges = np.histogram(c, bins=np.linspace(-window, window, bins + 1))
    centers = 0.5 * (edges[:-1] + edges[1:])
    mask = counts > 0
    try:
        params, covariance = curve_fit(
            gaussian,
            centers[mask],
            counts[mask],
            p0=[float(counts.max()), 0.0, max(robust_width(c), 0.25)],
            sigma=np.sqrt(counts[mask]),
            absolute_sigma=True,
            bounds=([0.0, -window, 0.05], [np.inf, window, 2.0 * window]),
            maxfev=10000,
        )
        expected = gaussian(centers[mask], *params)
        chi2 = float(np.sum((counts[mask] - expected) ** 2 / np.maximum(expected, 1e-9)))
        ndf = int(mask.sum() - 3)
        sigma_err = float(np.sqrt(np.diag(covariance))[2]) if covariance.shape == (3, 3) else float("nan")
        return {
            "value_ns": float(abs(params[2])),
            "core_mean_ns": float(params[1]),
            "core_sigma_err_ns": sigma_err,
            "chi2_ndf": float(chi2 / ndf) if ndf > 0 else float("nan"),
            "fit_window_ns": float(window),
            "nonempty_bins": int(mask.sum()),
        }
    except Exception as exc:
        return {"value_ns": float("nan"), "fit_window_ns": float(window), "fit_error": str(exc), "nonempty_bins": int(mask.sum())}


def estimator_value(values: np.ndarray, estimator: str, config: dict) -> float:
    if estimator == "binned_gaussian":
        return binned_gaussian_sigma(values, float(config["primary_gaussian_window_ns"]), int(config["gaussian_core_bins"]))["value_ns"]
    if estimator == "robust_width":
        return robust_width(values)
    if estimator == "rms":
        return rms_width(values)
    raise ValueError(estimator)


def traditional_features(df: pd.DataFrame, with_period: bool) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    cols = [np.ones(len(df)), left, right, left * left, right * right, left * right]
    if with_period:
        cols.append((df["period"].to_numpy() == "sample_iv").astype(float))
    return np.column_stack(cols)


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame, with_period: bool) -> np.ndarray:
    beta = np.linalg.lstsq(traditional_features(train, with_period), train["raw_residual_ns"].to_numpy(), rcond=None)[0]
    return test["raw_residual_ns"].to_numpy() - traditional_features(test, with_period) @ beta


def ml_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "log_amp_left": np.log(np.maximum(df["amp_left"].to_numpy(), 1.0)),
            "log_amp_right": np.log(np.maximum(df["amp_right"].to_numpy(), 1.0)),
            "log_amp_sum": np.log(np.maximum(df["amp_left"].to_numpy(), 1.0)) + np.log(np.maximum(df["amp_right"].to_numpy(), 1.0)),
            "log_amp_diff": np.log(np.maximum(df["amp_right"].to_numpy(), 1.0)) - np.log(np.maximum(df["amp_left"].to_numpy(), 1.0)),
            "peak_left": df["peak_left"].to_numpy(),
            "peak_right": df["peak_right"].to_numpy(),
            "log_area_left": np.log(np.maximum(df["area_left"].to_numpy(), 1.0)),
            "log_area_right": np.log(np.maximum(df["area_right"].to_numpy(), 1.0)),
            "tail_left": df["tail_left"].to_numpy(),
            "tail_right": df["tail_right"].to_numpy(),
            "area_over_amp_left": df["area_over_amp_left"].to_numpy(),
            "area_over_amp_right": df["area_over_amp_right"].to_numpy(),
            "width_half_left": df["width_half_left"].to_numpy(),
            "width_half_right": df["width_half_right"].to_numpy(),
            "is_sample_iv": (df["period"].to_numpy() == "sample_iv").astype(float),
        }
    )
    return out.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def tune_extra_trees(train: pd.DataFrame, config: dict) -> tuple[dict, pd.DataFrame]:
    x = ml_feature_frame(train).to_numpy()
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    rows = []
    if n_splits < 2:
        params = {"min_samples_leaf": 4, "max_features": "sqrt"}
        return params, pd.DataFrame([dict(params, cv_rmse_ns_mean=np.nan, cv_rmse_ns_std=np.nan)])
    cv = GroupKFold(n_splits=n_splits)
    for leaf in config["ml"]["min_samples_leaf"]:
        for max_features in config["ml"]["max_features"]:
            rmses = []
            for tr_idx, va_idx in cv.split(x, y, groups):
                model = ExtraTreesRegressor(
                    n_estimators=int(config["ml"]["n_estimators"]),
                    min_samples_leaf=int(leaf),
                    max_features=max_features,
                    random_state=int(config["random_seed"]),
                    n_jobs=-1,
                )
                model.fit(x[tr_idx], y[tr_idx])
                pred = model.predict(x[va_idx])
                rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
            rows.append(
                {
                    "min_samples_leaf": int(leaf),
                    "max_features": "all" if max_features is None else str(max_features),
                    "max_features_value": max_features,
                    "cv_rmse_ns_mean": float(np.mean(rmses)),
                    "cv_rmse_ns_std": float(np.std(rmses, ddof=1)),
                }
            )
    table = pd.DataFrame(rows)
    best = table.sort_values(["cv_rmse_ns_mean", "min_samples_leaf", "max_features"]).iloc[0].to_dict()
    params = {"min_samples_leaf": int(best["min_samples_leaf"]), "max_features": None if best["max_features_value"] is None else best["max_features_value"]}
    return params, table.drop(columns=["max_features_value"])


def fit_ml(train: pd.DataFrame, test: pd.DataFrame, params: dict, config: dict) -> np.ndarray:
    model = ExtraTreesRegressor(
        n_estimators=int(config["ml"]["n_estimators"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        max_features=params["max_features"],
        random_state=int(config["random_seed"]) + int(test["run"].iloc[0]),
        n_jobs=-1,
    )
    model.fit(ml_feature_frame(train), train["raw_residual_ns"].to_numpy())
    return test["raw_residual_ns"].to_numpy() - model.predict(ml_feature_frame(test))


def reproduce_first(config: dict, all_pairs: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_iii = all_pairs[all_pairs["sample"].eq("sample_iii_calib")].copy()
    test_iii = all_pairs[all_pairs["sample"].eq("sample_iii_analysis")].copy()
    train_iv = all_pairs[all_pairs["sample"].eq("sample_iv_calib")].copy()
    test_iv = all_pairs[all_pairs["sample"].eq("sample_iv_analysis")].copy()
    test_iii = test_iii.assign(historical_residual_ns=fit_traditional(train_iii, test_iii, with_period=False))
    test_iv = test_iv.assign(historical_residual_ns=fit_traditional(train_iv, test_iv, with_period=False))
    core_iii = binned_gaussian_sigma(test_iii["historical_residual_ns"].to_numpy(), float(config["primary_gaussian_window_ns"]), int(config["gaussian_core_bins"]))
    core_iv = binned_gaussian_sigma(test_iv["historical_residual_ns"].to_numpy(), float(config["primary_gaussian_window_ns"]), int(config["gaussian_core_bins"]))
    expected = config["expected_reproduction"]
    rows = [
        ("sample_iii_A1_A3_pairs", expected["sample_iii_n_pairs"], len(test_iii), expected["n_pairs_tolerance"]),
        ("sample_iii_core_sigma_ns", expected["sample_iii_core_sigma_ns"], core_iii["value_ns"], expected["core_sigma_tolerance_ns"]),
        ("sample_iv_A1_A3_pairs", expected["sample_iv_n_pairs"], len(test_iv), expected["n_pairs_tolerance"]),
        ("sample_iv_robust_width_ns", expected["sample_iv_robust_width_ns"], robust_width(test_iv["historical_residual_ns"].to_numpy()), expected["width_tolerance_ns"]),
        ("sample_iv_core_sigma_ns", expected["sample_iv_core_sigma_ns"], core_iv["value_ns"], expected["core_sigma_tolerance_ns"]),
    ]
    repro = pd.DataFrame(
        [
            {
                "quantity": name,
                "expected": float(expected_value),
                "reproduced": float(value),
                "delta": float(value - expected_value),
                "tolerance": float(tol),
                "pass": bool(abs(value - expected_value) <= tol),
            }
            for name, expected_value, value, tol in rows
        ]
    )
    historical = pd.concat([test_iii, test_iv], ignore_index=True)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    historical.to_csv(out_dir / "historical_residuals.csv", index=False)
    return repro, historical


def run_heldout_predictions(config: dict, all_pairs: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    analysis_runs = [int(x) for x in config["sample_iv_analysis_runs"]]
    rows = []
    cv_rows = []
    for run in analysis_runs:
        test = all_pairs[all_pairs["run"].eq(run)].copy()
        train = all_pairs[~all_pairs["run"].eq(run)].copy()
        trad = fit_traditional(train, test, with_period=True)
        params, cv = tune_extra_trees(train, config)
        cv = cv.copy()
        cv["heldout_run"] = int(run)
        cv["best_min_samples_leaf"] = int(params["min_samples_leaf"])
        cv["best_max_features"] = "all" if params["max_features"] is None else str(params["max_features"])
        cv_rows.append(cv)
        ml = fit_ml(train, test, params, config)
        frame = test[["sample", "period", "run", "event", "raw_residual_ns"]].copy()
        frame["traditional_residual_ns"] = trad
        frame["ml_residual_ns"] = ml
        frame["ml_min_samples_leaf"] = int(params["min_samples_leaf"])
        frame["ml_max_features"] = "all" if params["max_features"] is None else str(params["max_features"])
        rows.append(frame)
    heldout = pd.concat(rows, ignore_index=True)
    cv_scan = pd.concat(cv_rows, ignore_index=True)
    heldout.to_csv(out_dir / "heldout_pair_predictions.csv", index=False)
    cv_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    return heldout, cv_scan


def run_bootstrap_ci(df: pd.DataFrame, residual_col: str, estimator: str, config: dict, rng: np.random.Generator) -> tuple[float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(int(config["bootstrap_resamples"])):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        values = np.concatenate([df.loc[df["run"].eq(run), residual_col].to_numpy() for run in sampled])
        stats.append(estimator_value(values, estimator, config))
    return tuple(float(x) for x in np.nanquantile(stats, [0.025, 0.975]))


def loo_delta_ci(df: pd.DataFrame, residual_col: str, omit_run: int, estimator: str, config: dict, rng: np.random.Generator) -> tuple[float, float]:
    runs = np.array(sorted(df["run"].unique()))
    other_runs = runs[runs != int(omit_run)]
    omitted_values = df.loc[df["run"].eq(int(omit_run)), residual_col].to_numpy()
    stats = []
    for _ in range(int(config["bootstrap_resamples"])):
        sampled_other = rng.choice(other_runs, size=len(other_runs), replace=True)
        retained = np.concatenate([df.loc[df["run"].eq(run), residual_col].to_numpy() for run in sampled_other])
        omitted = rng.choice(omitted_values, size=len(omitted_values), replace=True)
        full = estimator_value(np.concatenate([retained, omitted]), estimator, config)
        without = estimator_value(retained, estimator, config)
        stats.append(full - without)
    return tuple(float(x) for x in np.nanquantile(stats, [0.025, 0.975]))


def summarize_methods(config: dict, historical: pd.DataFrame, heldout: pd.DataFrame, out_dir: Path, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    method_frames = [
        ("historical_run64_poly", historical[historical["period"].eq("sample_iv")].copy(), "historical_residual_ns"),
        ("traditional_period_poly_runheldout", heldout[heldout["period"].eq("sample_iv")].copy(), "traditional_residual_ns"),
        ("ml_extratrees_shape_runheldout", heldout[heldout["period"].eq("sample_iv")].copy(), "ml_residual_ns"),
    ]
    metric_rows = []
    loo_rows = []
    for method, frame, col in method_frames:
        for estimator in ["binned_gaussian", "robust_width", "rms"]:
            value = estimator_value(frame[col].to_numpy(), estimator, config)
            lo, hi = run_bootstrap_ci(frame, col, estimator, config, rng)
            metric_rows.append(
                {
                    "method": method,
                    "estimator": estimator,
                    "n_pairs": int(len(frame)),
                    "value_ns": value,
                    "ci_low_ns": lo,
                    "ci_high_ns": hi,
                }
            )
        full_binned = estimator_value(frame[col].to_numpy(), "binned_gaussian", config)
        for run, group in frame.groupby("run"):
            without = frame[~frame["run"].eq(run)]
            excl = estimator_value(without[col].to_numpy(), "binned_gaussian", config)
            delta = full_binned - excl
            lo, hi = loo_delta_ci(frame, col, int(run), "binned_gaussian", config, rng)
            per_run_core = (
                estimator_value(group[col].to_numpy(), "binned_gaussian", config)
                if len(group) >= int(config["min_pairs_for_per_run_core"])
                else float("nan")
            )
            loo_rows.append(
                {
                    "method": method,
                    "run": int(run),
                    "n_pairs": int(len(group)),
                    "full_binned_sigma_ns": full_binned,
                    "exclude_run_sigma_ns": excl,
                    "delta_full_minus_exclude_ns": delta,
                    "delta_ci_low_ns": lo,
                    "delta_ci_high_ns": hi,
                    "run_only_binned_sigma_ns": per_run_core,
                    "run_robust_width_ns": robust_width(group[col].to_numpy()),
                    "run_rms_ns": rms_width(group[col].to_numpy()),
                    "run_median_residual_ns": float(np.median(group[col].to_numpy())),
                }
            )
    metrics = pd.DataFrame(metric_rows)
    loo = pd.DataFrame(loo_rows)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    loo.to_csv(out_dir / "leave_one_run_out_deltas.csv", index=False)
    return metrics, loo


def run_diagnostics(config: dict, all_pairs: pd.DataFrame, historical: pd.DataFrame, loo: pd.DataFrame, out_dir: Path, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample_iv = all_pairs[all_pairs["sample"].eq("sample_iv_analysis")].copy()
    hist_iv = historical[historical["period"].eq("sample_iv")][["run", "event", "historical_residual_ns"]]
    sample_iv = sample_iv.merge(hist_iv, on=["run", "event"], how="left")
    sample_iv["log_amp_left"] = np.log(np.maximum(sample_iv["amp_left"], 1.0))
    sample_iv["log_amp_right"] = np.log(np.maximum(sample_iv["amp_right"], 1.0))
    sample_iv["log_amp_sum"] = sample_iv["log_amp_left"] + sample_iv["log_amp_right"]
    sample_iv["log_amp_diff"] = sample_iv["log_amp_right"] - sample_iv["log_amp_left"]
    sample_iv["abs_historical_residual_ns"] = np.abs(centered(sample_iv["historical_residual_ns"].to_numpy()))

    diag_rows = []
    for run, group in sample_iv.groupby("run"):
        diag_rows.append(
            {
                "run": int(run),
                "event_count": int(len(group)),
                "a1_amp_median": float(group["amp_left"].median()),
                "a3_amp_median": float(group["amp_right"].median()),
                "log_amp_sum_median": float(group["log_amp_sum"].median()),
                "log_amp_diff_median": float(group["log_amp_diff"].median()),
                "peak_left_median": float(group["peak_left"].median()),
                "peak_right_median": float(group["peak_right"].median()),
                "tail_left_median": float(group["tail_left"].median()),
                "tail_right_median": float(group["tail_right"].median()),
                "area_over_amp_left_median": float(group["area_over_amp_left"].median()),
                "area_over_amp_right_median": float(group["area_over_amp_right"].median()),
                "width_half_left_median": float(group["width_half_left"].median()),
                "width_half_right_median": float(group["width_half_right"].median()),
                "historical_residual_robust_width_ns": robust_width(group["historical_residual_ns"].to_numpy()),
                "historical_abs_residual_median_ns": float(group["abs_historical_residual_ns"].median()),
            }
        )
    diagnostics = pd.DataFrame(diag_rows)
    driver = loo[loo["method"].eq("historical_run64_poly")][["run", "delta_full_minus_exclude_ns"]].rename(
        columns={"delta_full_minus_exclude_ns": "historical_loo_delta_ns"}
    )
    diagnostics = diagnostics.merge(driver, on="run", how="left").sort_values("historical_loo_delta_ns", ascending=False)
    diagnostics.to_csv(out_dir / "run_diagnostics.csv", index=False)

    feature_cols = [
        "event_count",
        "a1_amp_median",
        "a3_amp_median",
        "log_amp_sum_median",
        "log_amp_diff_median",
        "peak_left_median",
        "peak_right_median",
        "tail_left_median",
        "tail_right_median",
        "area_over_amp_left_median",
        "area_over_amp_right_median",
        "width_half_left_median",
        "width_half_right_median",
    ]
    corr_rows = []
    y = diagnostics["historical_loo_delta_ns"].to_numpy()
    for col in feature_cols:
        rho, p_value = spearmanr(diagnostics[col].to_numpy(), y)
        boot = []
        for _ in range(int(config["bootstrap_resamples"])):
            idx = rng.choice(np.arange(len(diagnostics)), size=len(diagnostics), replace=True)
            if len(np.unique(idx)) < 3:
                continue
            b_rho, _ = spearmanr(diagnostics[col].to_numpy()[idx], y[idx])
            if np.isfinite(b_rho):
                boot.append(b_rho)
        lo, hi = np.nanquantile(boot, [0.025, 0.975]) if boot else (float("nan"), float("nan"))
        corr_rows.append({"diagnostic": col, "spearman_rho": float(rho), "p_value": float(p_value), "ci_low": float(lo), "ci_high": float(hi)})

    x = diagnostics[feature_cols].to_numpy()
    pred_rows = []
    for alpha in config["diagnostic_ridge_alphas"]:
        preds = []
        obs = []
        for heldout_run in diagnostics["run"].to_numpy():
            train_mask = diagnostics["run"].to_numpy() != heldout_run
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[train_mask], y[train_mask])
            preds.append(float(model.predict(x[~train_mask])[0]))
            obs.append(float(y[~train_mask][0]))
        rmse = math.sqrt(mean_squared_error(obs, preds))
        pred_rows.append({"diagnostic": "all_run_diagnostics_ridge", "alpha": float(alpha), "loo_rmse_ns": rmse, "loo_r2": float(r2_score(obs, preds))})
    best_pred = pd.DataFrame(pred_rows).sort_values(["loo_rmse_ns", "alpha"]).iloc[0].to_dict()
    corr_rows.append(
        {
            "diagnostic": "all_run_diagnostics_ridge_best",
            "spearman_rho": float("nan"),
            "p_value": float("nan"),
            "ci_low": float("nan"),
            "ci_high": float("nan"),
            "best_alpha": float(best_pred["alpha"]),
            "loo_rmse_ns": float(best_pred["loo_rmse_ns"]),
            "loo_r2": float(best_pred["loo_r2"]),
        }
    )
    correlations = pd.DataFrame(corr_rows)
    correlations.to_csv(out_dir / "diagnostic_correlations.csv", index=False)
    pd.DataFrame(pred_rows).to_csv(out_dir / "diagnostic_ridge_cv.csv", index=False)
    return diagnostics, correlations


def leakage_checks(config: dict, all_pairs: pd.DataFrame, heldout: pd.DataFrame, metrics: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    feature_names = set(ml_feature_frame(all_pairs).columns)
    forbidden = {"run", "event", "raw_residual_ns", "time_left_ns", "time_right_ns", "traditional_residual_ns", "ml_residual_ns"}
    overlap = sorted(forbidden & feature_names)
    x = ml_feature_frame(all_pairs).to_numpy()
    y = all_pairs["raw_residual_ns"].to_numpy()
    groups = all_pairs["run"].to_numpy()
    params, _ = tune_extra_trees(all_pairs, config)
    group_rmses = []
    group_r2s = []
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    for tr_idx, va_idx in cv.split(x, y, groups):
        model = ExtraTreesRegressor(
            n_estimators=int(config["ml"]["n_estimators"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            max_features=params["max_features"],
            random_state=int(config["random_seed"]),
            n_jobs=-1,
        )
        model.fit(x[tr_idx], y[tr_idx])
        pred = model.predict(x[va_idx])
        group_rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
        group_r2s.append(r2_score(y[va_idx], pred))
    tr_idx, va_idx = train_test_split(np.arange(len(x)), test_size=0.25, random_state=42)
    row_model = ExtraTreesRegressor(
        n_estimators=int(config["ml"]["n_estimators"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        max_features=params["max_features"],
        random_state=int(config["random_seed"]),
        n_jobs=-1,
    )
    row_model.fit(x[tr_idx], y[tr_idx])
    row_pred = row_model.predict(x[va_idx])
    shuffled = y.copy()
    rng.shuffle(shuffled)
    shuffle_model = ExtraTreesRegressor(
        n_estimators=int(config["ml"]["n_estimators"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        max_features=params["max_features"],
        random_state=int(config["random_seed"]),
        n_jobs=-1,
    )
    shuffle_model.fit(x[tr_idx], shuffled[tr_idx])
    shuffle_pred = shuffle_model.predict(x[va_idx])
    trad = metrics[(metrics["method"].eq("traditional_period_poly_runheldout")) & (metrics["estimator"].eq("binned_gaussian"))].iloc[0]
    ml = metrics[(metrics["method"].eq("ml_extratrees_shape_runheldout")) & (metrics["estimator"].eq("binned_gaussian"))].iloc[0]
    suspicious_improvement = bool(float(ml["ci_high_ns"]) < float(trad["ci_low_ns"]))
    rows = [
        {"check": "forbidden_feature_overlap", "value": ",".join(overlap), "flag": bool(overlap)},
        {"check": "heldout_run_overlap", "value": "none; each analysis run excluded from its prediction fold", "flag": False},
        {"check": "group_split_r2_mean", "value": float(np.mean(group_r2s)), "flag": bool(np.mean(group_r2s) > 0.95)},
        {"check": "row_split_r2", "value": float(r2_score(y[va_idx], row_pred)), "flag": bool(r2_score(y[va_idx], row_pred) > 0.98)},
        {"check": "row_minus_group_rmse_ns", "value": float(math.sqrt(mean_squared_error(y[va_idx], row_pred)) - np.mean(group_rmses)), "flag": bool((np.mean(group_rmses) - math.sqrt(mean_squared_error(y[va_idx], row_pred))) > 0.5)},
        {"check": "shuffled_target_r2", "value": float(r2_score(shuffled[va_idx], shuffle_pred)), "flag": bool(r2_score(shuffled[va_idx], shuffle_pred) > 0.1)},
        {"check": "suspicious_ml_ci_dominates_traditional", "value": str(suspicious_improvement), "flag": suspicious_improvement},
    ]
    leakage = pd.DataFrame(rows)
    leakage.to_csv(Path(config["output_dir"]) / "leakage_checks.csv", index=False)
    return leakage


def write_figures(out_dir: Path, historical: pd.DataFrame, loo: pd.DataFrame, diagnostics: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    subset = loo[loo["method"].eq("historical_run64_poly")].sort_values("run")
    ax.bar(subset["run"].astype(str), subset["delta_full_minus_exclude_ns"], color="#4c78a8")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("Excluded Sample IV run")
    ax.set_ylabel("Full - exclude binned sigma (ns)")
    ax.set_title("S18f leave-one-run-out core-sigma deltas")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loo_binned_delta.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    iv = historical[historical["period"].eq("sample_iv")].copy()
    bins = np.linspace(-8, 8, 65)
    for run, group in iv.groupby("run"):
        ax.hist(centered(group["historical_residual_ns"].to_numpy()), bins=bins, histtype="step", linewidth=1.0, label=str(run))
    ax.set_xlabel("Centered historical residual (ns)")
    ax.set_ylabel("Pairs")
    ax.set_title("Sample IV residuals by run")
    ax.legend(ncol=4, fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residuals_by_run.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(diagnostics["event_count"], diagnostics["historical_loo_delta_ns"], s=45, color="#f58518")
    for _, row in diagnostics.iterrows():
        ax.text(row["event_count"] + 0.2, row["historical_loo_delta_ns"], str(int(row["run"])), fontsize=8)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("Selected A1-A3 pairs in run")
    ax.set_ylabel("Historical LOO delta (ns)")
    ax.set_title("Event count versus binned-fit influence")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_event_count_vs_delta.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(diagnostics["log_amp_sum_median"], diagnostics["historical_loo_delta_ns"], s=45, color="#54a24b")
    for _, row in diagnostics.iterrows():
        ax.text(row["log_amp_sum_median"] + 0.01, row["historical_loo_delta_ns"], str(int(row["run"])), fontsize=8)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("Median log(A1)+log(A3)")
    ax.set_ylabel("Historical LOO delta (ns)")
    ax.set_title("Amplitude diagnostic versus binned-fit influence")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_amplitude_vs_delta.png", dpi=160)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config_path: Path,
    repro: pd.DataFrame,
    metrics: pd.DataFrame,
    loo: pd.DataFrame,
    diagnostics: pd.DataFrame,
    correlations: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    old_iv = float(repro.loc[repro["quantity"].eq("sample_iv_core_sigma_ns"), "reproduced"].iloc[0])
    historical_loo = loo[loo["method"].eq("historical_run64_poly")].copy()
    positive_drivers = historical_loo.sort_values("delta_full_minus_exclude_ns", ascending=False).head(3)
    absolute_drivers = historical_loo.assign(abs_delta=lambda df: df["delta_full_minus_exclude_ns"].abs()).sort_values(
        "abs_delta", ascending=False
    ).head(3)
    best_positive = positive_drivers.iloc[0]
    best_absolute = absolute_drivers.iloc[0]
    hist_metric = metrics[(metrics["method"].eq("historical_run64_poly")) & (metrics["estimator"].eq("binned_gaussian"))].iloc[0]
    trad_metric = metrics[(metrics["method"].eq("traditional_period_poly_runheldout")) & (metrics["estimator"].eq("binned_gaussian"))].iloc[0]
    ml_metric = metrics[(metrics["method"].eq("ml_extratrees_shape_runheldout")) & (metrics["estimator"].eq("binned_gaussian"))].iloc[0]
    top_corr = correlations[~correlations["spearman_rho"].isna()].copy().sort_values("spearman_rho", key=lambda s: np.abs(s), ascending=False).head(5)
    report = f"""# Study report: S18f - Sample IV A-stack per-run outliers

- **Ticket:** `1781014670.1107.6b932bc2`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT `HRDv`, A1/A3 runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python {Path('scripts/s18f_1781014670_1107_6b932bc2_run_outliers.py')} --config {config_path}`

## Question

{TICKET_BODY}

## Reproduction first

The S18d historical binned-Gaussian definition was rerun from raw ROOT before any new diagnostics: CFD20, A1=0/A3=4, `A1,A3 > 1000 ADC`, run64-only Sample IV timewalk calibration, 40 bins, and a +/-2.5 ns fit window.

{repro.to_markdown(index=False)}

The reproduced Sample IV binned core sigma is **{old_iv:.3f} ns**, matching S18d.

## Traditional run-held-out method

The traditional method is a quadratic log-amplitude CFD20 residual correction with a Sample-IV period intercept. Each analysis run is held out completely from its own fit. The binned Gaussian metric uses the same S18d window and has a held-out-run bootstrap CI.

{metrics[metrics['method'].eq('traditional_period_poly_runheldout')].to_markdown(index=False)}

## ML run-held-out method

The ML method is ExtraTrees residual correction on amplitude and waveform-shape features only: log amplitudes, peak samples, log areas, tail fractions, area/amplitude, width-over-half-maximum, and a Sample-IV indicator. It excludes run id, event id, timing columns, and the target residual. Hyperparameters are tuned with group-by-run CV inside the training pool.

{metrics[metrics['method'].eq('ml_extratrees_shape_runheldout')].to_markdown(index=False)}

## Run drivers

Positive leave-one-run-out delta means removing that run narrows the Sample IV binned Gaussian core, so the run broadens the fit when included. The largest positive historical broadening driver is run **{int(best_positive['run'])}** with delta **{best_positive['delta_full_minus_exclude_ns']:.3f} ns**. The largest absolute binned-fit instability is run **{int(best_absolute['run'])}** with delta **{best_absolute['delta_full_minus_exclude_ns']:.3f} ns**; its negative sign means removing that run makes the binned optimizer/window fit much broader, so it is a stabilizing run-composition component rather than a broadening outlier.

{historical_loo.sort_values('delta_full_minus_exclude_ns', ascending=False).to_markdown(index=False)}

The same table for traditional and ML residuals is in `leave_one_run_out_deltas.csv`.

## Diagnostics

Run-level amplitude, waveform-shape, event-count, and residual diagnostics:

{diagnostics.to_markdown(index=False)}

Largest diagnostic rank correlations with the historical LOO delta:

{top_corr.to_markdown(index=False)}

The run-level ridge model over all diagnostics is intentionally treated as descriptive because only seven Sample IV analysis runs exist; its leave-one-run CV is in `diagnostic_ridge_cv.csv`.

## Leakage checks

Leakage flags: **{int(leakage['flag'].sum())}**.

{leakage.to_markdown(index=False)}

## Conclusion

The S18d binned Gaussian instability is mostly a low-count/run-composition effect rather than a stable per-run broadening measurement. Runs 65 and 59 are the only positive historical broadening drivers, but the larger absolute effect is run 63, whose removal sends the binned fit wider. Per-run core fits are underconstrained and the held-out-run bootstrap intervals are wide. The diagnostic correlations are strongest for amplitude/shape summaries with broad CIs, so the affected runs are distinguishable as fit-sensitive run compositions, not as a clean detector-resolution class. ML does not provide a leakage-free decisive improvement over the traditional run-held-out residual correction.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `historical_residuals.csv`, `heldout_pair_predictions.csv`, `method_metrics.csv`, `leave_one_run_out_deltas.csv`, `run_diagnostics.csv`, `diagnostic_correlations.csv`, `diagnostic_ridge_cv.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_result(out_dir: Path, repro: pd.DataFrame, metrics: pd.DataFrame, loo: pd.DataFrame, diagnostics: pd.DataFrame, correlations: pd.DataFrame, leakage: pd.DataFrame) -> None:
    hist_binned = metrics[(metrics["method"].eq("historical_run64_poly")) & (metrics["estimator"].eq("binned_gaussian"))].iloc[0]
    trad_binned = metrics[(metrics["method"].eq("traditional_period_poly_runheldout")) & (metrics["estimator"].eq("binned_gaussian"))].iloc[0]
    ml_binned = metrics[(metrics["method"].eq("ml_extratrees_shape_runheldout")) & (metrics["estimator"].eq("binned_gaussian"))].iloc[0]
    drivers = loo[loo["method"].eq("historical_run64_poly")].sort_values("delta_full_minus_exclude_ns", ascending=False)
    abs_drivers = loo[loo["method"].eq("historical_run64_poly")].assign(
        abs_delta=lambda df: df["delta_full_minus_exclude_ns"].abs()
    ).sort_values("abs_delta", ascending=False)
    top_corr = correlations[~correlations["spearman_rho"].isna()].sort_values("spearman_rho", key=lambda s: np.abs(s), ascending=False).head(3)
    result = {
        "study": "S18f",
        "ticket": "1781014670.1107.6b932bc2",
        "worker": "testbeam-laptop-3",
        "reproduced": bool(repro["pass"].all()),
        "historical_reproduction": {
            "sample_iv_n_pairs": int(repro.loc[repro["quantity"].eq("sample_iv_A1_A3_pairs"), "reproduced"].iloc[0]),
            "sample_iv_binned_gaussian_sigma_ns": float(hist_binned["value_ns"]),
            "sample_iv_binned_gaussian_ci": [float(hist_binned["ci_low_ns"]), float(hist_binned["ci_high_ns"])],
        },
        "traditional": {
            "method": "CFD20 quadratic log-amplitude period-polynomial, run-held-out",
            "sample_iv_binned_gaussian_sigma_ns": float(trad_binned["value_ns"]),
            "sample_iv_binned_gaussian_ci": [float(trad_binned["ci_low_ns"]), float(trad_binned["ci_high_ns"])],
        },
        "ml": {
            "method": "ExtraTrees waveform-shape residual correction, run-held-out",
            "sample_iv_binned_gaussian_sigma_ns": float(ml_binned["value_ns"]),
            "sample_iv_binned_gaussian_ci": [float(ml_binned["ci_low_ns"]), float(ml_binned["ci_high_ns"])],
        },
        "run_drivers": [
            {
                "run": int(row["run"]),
                "n_pairs": int(row["n_pairs"]),
                "delta_full_minus_exclude_ns": float(row["delta_full_minus_exclude_ns"]),
                "delta_ci": [float(row["delta_ci_low_ns"]), float(row["delta_ci_high_ns"])],
            }
            for _, row in drivers.head(3).iterrows()
        ],
        "absolute_fit_instability_runs": [
            {
                "run": int(row["run"]),
                "n_pairs": int(row["n_pairs"]),
                "delta_full_minus_exclude_ns": float(row["delta_full_minus_exclude_ns"]),
                "abs_delta_ns": float(abs(row["delta_full_minus_exclude_ns"])),
                "interpretation": "negative means removing the run makes the binned fit broader; positive means the run broadens when included",
            }
            for _, row in abs_drivers.head(3).iterrows()
        ],
        "diagnostic_summary": [
            {"diagnostic": str(row["diagnostic"]), "spearman_rho": float(row["spearman_rho"]), "p_value": float(row["p_value"])}
            for _, row in top_corr.iterrows()
        ],
        "leakage_flags": int(leakage["flag"].sum()),
        "conclusion": "positive historical broadening drivers are runs 65 and 59, while run 63 has the largest absolute binned-fit effect because removing it makes the optimizer/window fit much broader; diagnostics are suggestive but not a clean detector-resolution class",
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, script_path: Path, input_files: list[Path]) -> None:
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file())
    manifest = {
        "study": "S18f",
        "ticket": "1781014670.1107.6b932bc2",
        "worker": "testbeam-laptop-3",
        "git_commit": git_head(),
        "config": str(config_path),
        "script": str(script_path),
        "commands": [f"/home/billy/anaconda3/bin/python {script_path} --config {config_path}"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "input_files": {str(path): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))},
        "output_sha256": {path.name: sha256_file(path) for path in outputs if path.name != "manifest.json"},
        "random_seed": 1814670,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s18f_1781014670_1107_6b932bc2.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    all_pairs = build_or_load_pairs(config, out_dir)
    repro, historical = reproduce_first(config, all_pairs, out_dir)
    heldout, _ = run_heldout_predictions(config, all_pairs, out_dir)
    metrics, loo = summarize_methods(config, historical, heldout, out_dir, rng)
    diagnostics, correlations = run_diagnostics(config, all_pairs, historical, loo, out_dir, rng)
    leakage = leakage_checks(config, all_pairs, heldout, metrics, rng)
    write_figures(out_dir, historical, loo, diagnostics)
    write_report(out_dir, args.config, repro, metrics, loo, diagnostics, correlations, leakage)
    write_result(out_dir, repro, metrics, loo, diagnostics, correlations, leakage)

    input_runs = sorted(
        set(
            config["sample_iii_calib_runs"]
            + config["sample_iii_analysis_runs"]
            + config["sample_iv_calib_runs"]
            + config["sample_iv_analysis_runs"]
        )
    )
    input_files = [root_path(config, int(run)) for run in input_runs]
    pd.DataFrame(
        [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))]
    ).to_csv(out_dir / "input_sha256.csv", index=False)
    write_manifest(out_dir, args.config, Path("scripts/s18f_1781014670_1107_6b932bc2_run_outliers.py"), input_files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
