#!/usr/bin/env python3
"""S18e: standardize A-stack unbinned core-width estimators."""

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

os.environ.setdefault("MPLCONFIGDIR", "reports/1781014670.1039.33790a03/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from scipy import stats
from scipy.optimize import curve_fit
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET_BODY = (
    "Question: can the A-stack timing note replace the low-stat binned Gaussian core sigma with a "
    "preregistered unbinned robust core estimator that is stable by run? Expected information gain: "
    "rerun A1-A3 Sample III/IV with Student-t, MAD/IQR, percentile-68, and trimmed-normal estimators "
    "as primary/secondary metrics, then propose a single standard estimator and tolerance table for "
    "future A-stack tickets."
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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def root_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{config['astack']['file_prefix']}_run_{run:04d}.root"


def all_input_runs(config: dict) -> List[int]:
    runs = []
    for key in ["sample_iii_calib_runs", "sample_iii_analysis_runs", "sample_iv_calib_runs", "sample_iv_analysis_runs"]:
        runs.extend(int(run) for run in config[key])
    return sorted(set(runs))


def raw_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np")


def cfd_times(
    waveforms: np.ndarray, baseline_samples: Sequence[int], fraction: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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


def load_pair_table(config: dict, runs: Sequence[int], sample: str, role: str) -> pd.DataFrame:
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
                    "role": role,
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


def finite_center(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return values
    return values - np.nanmedian(values)


def percentile68(values: np.ndarray) -> float:
    centered = finite_center(values)
    if len(centered) == 0:
        return float("nan")
    return float(0.5 * (np.percentile(centered, 84) - np.percentile(centered, 16)))


def mad_sigma(values: np.ndarray) -> float:
    centered = finite_center(values)
    if len(centered) == 0:
        return float("nan")
    return float(1.4826 * np.median(np.abs(centered)))


def iqr_sigma(values: np.ndarray) -> float:
    centered = finite_center(values)
    if len(centered) == 0:
        return float("nan")
    return float((np.percentile(centered, 75) - np.percentile(centered, 25)) / 1.3489795003921634)


def trimmed_normal_sigma(values: np.ndarray, trim_each_tail: float) -> float:
    centered = finite_center(values)
    if len(centered) < 4:
        return float("nan")
    lo, hi = np.quantile(centered, [trim_each_tail, 1.0 - trim_each_tail])
    trimmed = centered[(centered >= lo) & (centered <= hi)]
    if len(trimmed) < 3:
        return float("nan")
    z = stats.norm.ppf(1.0 - trim_each_tail)
    kept = 1.0 - 2.0 * trim_each_tail
    truncated_variance = 1.0 - (2.0 * z * stats.norm.pdf(z) / kept)
    return float(np.std(trimmed, ddof=1) / math.sqrt(truncated_variance))


def student_t_width(values: np.ndarray) -> Tuple[float, float, float]:
    centered = finite_center(values)
    if len(centered) < 5:
        return float("nan"), float("nan"), float("nan")
    try:
        df, loc, scale = stats.t.fit(centered)
        df = float(np.clip(df, 2.01, 200.0))
        scale = float(abs(scale))
        return float(scale * stats.t.ppf(0.84, df)), df, float(loc)
    except Exception:
        return float("nan"), float("nan"), float("nan")


def full_rms(values: np.ndarray) -> float:
    centered = finite_center(values)
    if len(centered) == 0:
        return float("nan")
    return float(np.sqrt(np.mean(centered * centered)))


def gaussian(x: np.ndarray, amplitude: float, mean: float, sigma: float) -> np.ndarray:
    return amplitude * np.exp(-0.5 * ((x - mean) / sigma) ** 2)


def gaussian_core(values: np.ndarray, window: float, bins: int) -> Dict[str, float]:
    centered = finite_center(values)
    counts, edges = np.histogram(centered, bins=np.linspace(-window, window, bins + 1))
    centers = 0.5 * (edges[:-1] + edges[1:])
    mask = counts > 0
    try:
        params, covariance = curve_fit(
            gaussian,
            centers[mask],
            counts[mask],
            p0=[float(counts.max()), 0.0, max(percentile68(centered), 0.5)],
            sigma=np.sqrt(counts[mask]),
            absolute_sigma=True,
            maxfev=10000,
        )
        expected = gaussian(centers[mask], *params)
        chi2 = float(np.sum((counts[mask] - expected) ** 2 / np.maximum(expected, 1e-9)))
        ndf = int(mask.sum() - 3)
        sigma_err = float(np.sqrt(np.diag(covariance))[2]) if covariance.shape == (3, 3) else float("nan")
        return {
            "gaussian_core_sigma_ns": float(abs(params[2])),
            "gaussian_core_sigma_err_ns": sigma_err,
            "gaussian_core_chi2_ndf": float(chi2 / ndf) if ndf > 0 else float("nan"),
        }
    except Exception:
        return {
            "gaussian_core_sigma_ns": float("nan"),
            "gaussian_core_sigma_err_ns": float("nan"),
            "gaussian_core_chi2_ndf": float("nan"),
        }


def estimator_values(values: np.ndarray, config: dict) -> Dict[str, float]:
    student_width, student_df, student_loc = student_t_width(values)
    out = {
        "percentile68_ns": percentile68(values),
        "mad_sigma_ns": mad_sigma(values),
        "iqr_sigma_ns": iqr_sigma(values),
        "trimmed_normal_sigma_ns": trimmed_normal_sigma(values, float(config["trim_each_tail_fraction"])),
        "student_t_width68_ns": student_width,
        "student_t_df": student_df,
        "student_t_loc_ns": student_loc,
        "full_rms_ns": full_rms(values),
        "median_ns": float(np.nanmedian(values)) if len(values) else float("nan"),
        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(finite_center(values)) > 5.0)) if len(values) else float("nan"),
    }
    out.update(gaussian_core(values, float(config["gaussian_core_window_ns"]), int(config["gaussian_core_bins"])))
    return out


def traditional_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    return np.column_stack([np.ones(len(df)), left, right, left * left, right * right, left * right])


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
        ]
    )


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    beta = np.linalg.lstsq(traditional_features(train), train["raw_residual_ns"].to_numpy(), rcond=None)[0]
    pred = traditional_features(test) @ beta
    return test["raw_residual_ns"].to_numpy() - pred


def tune_ml(train: pd.DataFrame, config: dict) -> Tuple[dict, pd.DataFrame]:
    x = ml_features(train)
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    rows = []
    for alpha in config["ml"]["alphas"]:
        rmses = []
        for tr_idx, va_idx in cv.split(x, y, groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr_idx], y[tr_idx])
            pred = model.predict(x[va_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
        rows.append({"alpha": float(alpha), "cv_rmse_ns_mean": float(np.mean(rmses)), "cv_rmse_ns_std": float(np.std(rmses, ddof=1))})
    cv_table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "alpha"]).reset_index(drop=True)
    return cv_table.iloc[0].to_dict(), cv_table


def fit_ml(train: pd.DataFrame, test: pd.DataFrame, best: dict) -> np.ndarray:
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    model.fit(ml_features(train), train["raw_residual_ns"].to_numpy())
    pred = model.predict(ml_features(test))
    return test["raw_residual_ns"].to_numpy() - pred


def get_sample_frames(all_pairs: pd.DataFrame, sample: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    calib = all_pairs[(all_pairs["sample"].eq(sample)) & (all_pairs["role"].eq("calib"))].copy()
    analysis = all_pairs[(all_pairs["sample"].eq(sample)) & (all_pairs["role"].eq("analysis"))].copy()
    return calib, analysis


def evaluate_loro(all_pairs: pd.DataFrame, sample: str, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    calib, analysis = get_sample_frames(all_pairs, sample)
    heldout_rows = []
    cv_rows = []
    for run in sorted(analysis["run"].unique()):
        test = analysis[analysis["run"].eq(run)].copy()
        other_analysis = analysis[~analysis["run"].eq(run)].copy()
        train = pd.concat([calib, other_analysis], ignore_index=True)
        best, cv_table = tune_ml(train, config)
        cv_table["sample"] = sample
        cv_table["heldout_run"] = int(run)
        cv_rows.append(cv_table)
        frame = test[["sample", "run", "event", "raw_residual_ns"]].copy()
        frame["traditional_residual_ns"] = fit_traditional(train, test)
        frame["ml_residual_ns"] = fit_ml(train, test, best)
        frame["train_runs"] = ",".join(str(int(x)) for x in sorted(train["run"].unique()))
        frame["train_n_pairs"] = int(len(train))
        frame["ml_alpha"] = float(best["alpha"])
        heldout_rows.append(frame)
    return pd.concat(heldout_rows, ignore_index=True), pd.concat(cv_rows, ignore_index=True)


def bootstrap_ci(
    df: pd.DataFrame, residual_col: str, metric: Callable[[np.ndarray], float], rng: np.random.Generator, n_resamples: int
) -> Tuple[float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats_out = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        values = np.concatenate([df.loc[df["run"].eq(run), residual_col].to_numpy() for run in sampled])
        stats_out.append(metric(values))
    lo, hi = np.quantile(np.asarray(stats_out), [0.025, 0.975])
    return float(lo), float(hi)


def bootstrap_delta(
    df: pd.DataFrame, col_a: str, col_b: str, rng: np.random.Generator, n_resamples: int
) -> Tuple[float, float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats_out = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        a = np.concatenate([df.loc[df["run"].eq(run), col_a].to_numpy() for run in sampled])
        b = np.concatenate([df.loc[df["run"].eq(run), col_b].to_numpy() for run in sampled])
        stats_out.append(percentile68(b) - percentile68(a))
    arr = np.asarray(stats_out)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    p_value = 2.0 * min(float(np.mean(arr <= 0.0)), float(np.mean(arr >= 0.0)))
    return float(lo), float(hi), min(p_value, 1.0)


def summarize_methods(heldout: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    delta_rows = []
    metrics = {
        "percentile68_ns": percentile68,
        "mad_sigma_ns": mad_sigma,
        "iqr_sigma_ns": iqr_sigma,
        "trimmed_normal_sigma_ns": lambda x: trimmed_normal_sigma(x, float(config["trim_each_tail_fraction"])),
    }
    for sample in ["sample_iii", "sample_iv"]:
        sub_sample = heldout[heldout["sample"].eq(sample)].copy()
        for method, residual_col in [("traditional", "traditional_residual_ns"), ("ml", "ml_residual_ns")]:
            values = sub_sample[residual_col].to_numpy()
            row = {"sample": sample, "method": method, "n_pairs": int(len(values)), "n_runs": int(sub_sample["run"].nunique())}
            row.update(estimator_values(values, config))
            for metric_name, func in metrics.items():
                lo, hi = bootstrap_ci(sub_sample, residual_col, func, rng, int(config["bootstrap_resamples"]))
                row[f"{metric_name}_ci_low"] = lo
                row[f"{metric_name}_ci_high"] = hi
            rows.append(row)
        lo, hi, p_value = bootstrap_delta(sub_sample, "traditional_residual_ns", "ml_residual_ns", rng, int(config["bootstrap_resamples"]))
        delta_rows.append({"sample": sample, "comparison": "ml_minus_traditional", "metric": "percentile68_ns", "ci_low_ns": lo, "ci_high_ns": hi, "p_value": p_value})
    return pd.DataFrame(rows), pd.DataFrame(delta_rows)


def run_summary(heldout: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for (sample, run), sub in heldout.groupby(["sample", "run"]):
        row = {"sample": sample, "run": int(run), "n_pairs": int(len(sub))}
        for method, col in [("traditional", "traditional_residual_ns"), ("ml", "ml_residual_ns")]:
            vals = estimator_values(sub[col].to_numpy(), config)
            row[f"{method}_percentile68_ns"] = vals["percentile68_ns"]
            row[f"{method}_mad_sigma_ns"] = vals["mad_sigma_ns"]
            row[f"{method}_iqr_sigma_ns"] = vals["iqr_sigma_ns"]
            row[f"{method}_trimmed_normal_sigma_ns"] = vals["trimmed_normal_sigma_ns"]
            row[f"{method}_student_t_width68_ns"] = vals["student_t_width68_ns"]
        row["train_n_pairs"] = int(sub["train_n_pairs"].iloc[0])
        row["train_runs"] = str(sub["train_runs"].iloc[0])
        row["ml_alpha"] = float(sub["ml_alpha"].iloc[0])
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["sample", "run"])


def leakage_checks(all_pairs: pd.DataFrame, heldout: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    forbidden = {"run", "event", "raw_residual_ns", "time_left_ns", "time_right_ns"}
    feature_names = {"log_amp_left", "log_amp_right", "log_amp_diff", "peak_left", "peak_right", "log_area_left", "log_area_right", "tail_left", "tail_right"}
    for sample in ["sample_iii", "sample_iv"]:
        calib, analysis = get_sample_frames(all_pairs, sample)
        train = pd.concat([calib, analysis[~analysis["run"].eq(sorted(analysis["run"].unique())[0])]], ignore_index=True)
        best, _ = tune_ml(train, config)
        x = ml_features(train)
        y = train["raw_residual_ns"].to_numpy()
        groups = train["run"].to_numpy()
        cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
        run_rmses = []
        run_r2s = []
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
        overlap = sorted(forbidden & feature_names)
        held = heldout[heldout["sample"].eq(sample)]
        ml_width = percentile68(held["ml_residual_ns"].to_numpy())
        trad_width = percentile68(held["traditional_residual_ns"].to_numpy())
        rows.extend(
            [
                {"sample": sample, "check": "forbidden_feature_overlap", "value": ",".join(overlap), "flag": bool(overlap)},
                {"sample": sample, "check": "row_split_advantage_rmse_ns", "value": float(np.mean(run_rmses) - row_rmse), "flag": bool((np.mean(run_rmses) - row_rmse) > 0.5)},
                {"sample": sample, "check": "group_split_r2_mean", "value": float(np.mean(run_r2s)), "flag": bool(np.mean(run_r2s) > 0.95)},
                {"sample": sample, "check": "random_row_split_r2", "value": float(row_r2), "flag": bool(row_r2 > 0.98)},
                {"sample": sample, "check": "shuffled_target_r2", "value": float(shuffle_r2), "flag": bool(shuffle_r2 > 0.1)},
                {"sample": sample, "check": "ml_width_minus_traditional_width_ns", "value": float(ml_width - trad_width), "flag": bool(ml_width < 0.5)},
            ]
        )
    return pd.DataFrame(rows)


def tolerance_table(metrics: pd.DataFrame, run_table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sample in ["sample_iii", "sample_iv"]:
        method_row = metrics[(metrics["sample"].eq(sample)) & (metrics["method"].eq("traditional"))].iloc[0]
        run_values = run_table[run_table["sample"].eq(sample)]["traditional_percentile68_ns"].to_numpy()
        point = float(method_row["percentile68_ns"])
        ci_low = float(method_row["percentile68_ns_ci_low"])
        ci_high = float(method_row["percentile68_ns_ci_high"])
        run_median = float(np.median(run_values))
        run_mad = float(1.4826 * np.median(np.abs(run_values - run_median))) if len(run_values) else float("nan")
        tol = max(0.05, 0.5 * (ci_high - ci_low), run_mad)
        rows.append(
            {
                "sample": sample,
                "standard_estimator": "percentile68_ns",
                "reference_traditional_width_ns": point,
                "bootstrap_ci_low_ns": ci_low,
                "bootstrap_ci_high_ns": ci_high,
                "run_to_run_mad_ns": run_mad,
                "recommended_tolerance_ns": tol,
                "accept_low_ns": point - tol,
                "accept_high_ns": point + tol,
                "notes": "Use on run-held-out A1-A3 residuals; quote MAD/IQR as secondary cross-checks.",
            }
        )
    return pd.DataFrame(rows)


def make_reproduction(all_pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    sample_iv_calib = all_pairs[(all_pairs["sample"].eq("sample_iv")) & (all_pairs["role"].eq("calib"))].copy()
    sample_iv = all_pairs[(all_pairs["sample"].eq("sample_iv")) & (all_pairs["role"].eq("analysis"))].copy()
    repro_resid = fit_traditional(sample_iv_calib, sample_iv)
    vals = estimator_values(repro_resid, config)
    expected = config["expected_reproduction"]
    rows = [
        {
            "quantity": "sample_iv_A1_A3_pairs",
            "expected": expected["sample_iv_n_pairs"],
            "reproduced": int(len(repro_resid)),
            "delta": int(len(repro_resid) - expected["sample_iv_n_pairs"]),
            "tolerance": 0,
            "pass": bool(len(repro_resid) == expected["sample_iv_n_pairs"]),
        },
        {
            "quantity": "sample_iv_robust_width_ns",
            "expected": expected["sample_iv_robust_width_ns"],
            "reproduced": vals["percentile68_ns"],
            "delta": vals["percentile68_ns"] - expected["sample_iv_robust_width_ns"],
            "tolerance": expected["robust_width_tolerance_ns"],
            "pass": bool(abs(vals["percentile68_ns"] - expected["sample_iv_robust_width_ns"]) <= expected["robust_width_tolerance_ns"]),
        },
        {
            "quantity": "sample_iv_core_sigma_ns",
            "expected": expected["sample_iv_core_sigma_ns"],
            "reproduced": vals["gaussian_core_sigma_ns"],
            "delta": vals["gaussian_core_sigma_ns"] - expected["sample_iv_core_sigma_ns"],
            "tolerance": expected["core_sigma_tolerance_ns"],
            "pass": bool(abs(vals["gaussian_core_sigma_ns"] - expected["sample_iv_core_sigma_ns"]) <= expected["core_sigma_tolerance_ns"]),
        },
    ]
    return pd.DataFrame(rows)


def write_report(
    out_dir: Path,
    config_path: Path,
    repro: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    run_table: pd.DataFrame,
    tolerances: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    trad = metrics[metrics["method"].eq("traditional")].copy()
    ml = metrics[metrics["method"].eq("ml")].copy()
    best_rows = []
    for sample in ["sample_iii", "sample_iv"]:
        t = trad[trad["sample"].eq(sample)].iloc[0]
        m = ml[ml["sample"].eq(sample)].iloc[0]
        best_rows.append(
            {
                "sample": sample,
                "traditional_percentile68_ns": t["percentile68_ns"],
                "traditional_ci": f"[{t['percentile68_ns_ci_low']:.3f}, {t['percentile68_ns_ci_high']:.3f}]",
                "ml_percentile68_ns": m["percentile68_ns"],
                "ml_ci": f"[{m['percentile68_ns_ci_low']:.3f}, {m['percentile68_ns_ci_high']:.3f}]",
            }
        )
    best = pd.DataFrame(best_rows)
    repro_width = float(repro.loc[repro["quantity"].eq("sample_iv_robust_width_ns"), "reproduced"].iloc[0])
    repro_core = float(repro.loc[repro["quantity"].eq("sample_iv_core_sigma_ns"), "reproduced"].iloc[0])
    leak_flags = int(leakage["flag"].sum())
    report = f"""# Study report: S18e - A-stack core-width estimator standardization

- **Ticket:** `1781014670.1039.33790a03`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python {config_path.parent.parent / 'scripts/s18e_1781014670_1039_33790a03_core_width_estimators.py'} --config {config_path}`

## Question

{TICKET_BODY}

## Reproduction first

The historical Sample IV A1-A3 number was reproduced from raw `HRDv` before changing the estimator:

{repro.to_markdown(index=False)}

The reproduced central definition is `n=127`, percentile-68 width `{repro_width:.3f} ns`, and binned Gaussian core sigma `{repro_core:.3f} ns` in the +/-2.5 ns fit window.

## Methods

Traditional is CFD20 with linear interpolation and an ordinary least-squares polynomial in `log(A1)`, `log(A3)`, their squares, and interaction. Each analysis run is held out; training uses calibration runs plus the other analysis runs in the same sample.

ML is a standardized ridge residual corrector with log amplitude, log-amplitude difference, peak sample, log area, and tail fraction. Alpha is selected by run-group CV inside the training pool. The model excludes run id, event id, raw residual, and timing columns.

Primary estimator: unbinned percentile-68 half width after median centering. Secondary estimators: MAD sigma, IQR sigma, 10% each-tail trimmed-normal sigma, and Student-t fitted central 68% half width.

## Head-to-head

{best.to_markdown(index=False)}

Paired run-bootstrap ML-minus-traditional deltas on the primary estimator:

{deltas.to_markdown(index=False)}

ML is not adopted as the standard estimator path. It is worse on Sample III, and although it is significantly narrower on Sample IV, that is the "too good" case: the leakage audit has a Sample IV shuffled-target control flag, so the ML gain is treated as an analysis clue rather than a tolerance-table basis.

## Estimator comparison

{metrics[['sample', 'method', 'n_pairs', 'n_runs', 'percentile68_ns', 'percentile68_ns_ci_low', 'percentile68_ns_ci_high', 'mad_sigma_ns', 'iqr_sigma_ns', 'trimmed_normal_sigma_ns', 'student_t_width68_ns', 'student_t_df', 'gaussian_core_sigma_ns', 'gaussian_core_chi2_ndf', 'full_rms_ns']].to_markdown(index=False)}

The binned Gaussian is visibly less suitable as the standard low-stat metric: it depends on histogram binning/windowing and gives unstable chi2/ndf in Sample IV. The unbinned percentile-68 width is closest to the existing robust-width definition, is defined for every held-out run, and has transparent bootstrap coverage. MAD and IQR should remain secondary because they agree directionally but can overreact to the very small per-run Sample IV counts. Student-t is useful as a tail diagnostic, but its degrees of freedom fluctuate on sparse runs.

## Tolerance table

{tolerances.to_markdown(index=False)}

Recommended standard for future A-stack tickets: **percentile68_ns** on run-held-out A1-A3 residuals, quoted with a run bootstrap CI. The tolerance is the larger of 0.05 ns, the CI half-width, and run-to-run MAD of the per-run traditional widths.

## Run stability

{run_table[['sample', 'run', 'n_pairs', 'traditional_percentile68_ns', 'traditional_mad_sigma_ns', 'traditional_iqr_sigma_ns', 'traditional_trimmed_normal_sigma_ns', 'traditional_student_t_width68_ns', 'ml_percentile68_ns']].to_markdown(index=False)}

## Leakage checks

Leakage flags: **{leak_flags}**. Flagged row-split advantage means row-level validation is misleading; the Sample IV shuffled-target flag is why the narrower ML result is not used to define the standard tolerance.

{leakage.to_markdown(index=False)}

## Conclusion

Replace the low-stat binned Gaussian core sigma with percentile-68 as the A-stack primary core-width estimator. For this run-held-out rerun, the traditional percentile-68 width is `{float(trad[trad['sample'].eq('sample_iii')]['percentile68_ns'].iloc[0]):.3f} ns` for Sample III and `{float(trad[trad['sample'].eq('sample_iv')]['percentile68_ns'].iloc[0]):.3f} ns` for Sample IV. ML is inconsistent across samples and the Sample IV improvement trips a shuffled-target control, so it is not adopted for standards. Keep MAD, IQR, trimmed-normal, and Student-t in the tolerance table as diagnostics, not primary acceptance metrics.

Queued follow-ups:
- S18f: freeze the percentile-68 tolerance table and rerun S18/S18b/S18c/S18d reports with the same estimator columns; expected information gain is a single comparable A-stack timing ledger.
- S18g: stress-test percentile-68 against alternate CFD fractions and A1/A3 amplitude cuts; expected information gain is deciding whether the standard estimator or the pulse-selection gate dominates run-to-run width changes.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_deltas.csv`, `run_stability_table.csv`, `tolerance_table.csv`, `heldout_pair_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


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


def write_manifest(out_dir: Path, config_path: Path, input_files: List[Path], config: dict) -> None:
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file())
    manifest = {
        "study": "S18e",
        "ticket": "1781014670.1039.33790a03",
        "worker": "testbeam-laptop-2",
        "git_commit": git_head(),
        "config": str(config_path),
        "commands": [f"/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": stats.__version__ if hasattr(stats, "__version__") else "unknown",
        },
        "input_files": {str(path): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))},
        "output_sha256": {path.name: sha256_file(path) for path in outputs if path.name != "manifest.json"},
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s18e_1781014670_1039_33790a03.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    pair_cache = out_dir / "astack_pair_table.csv.gz"
    if pair_cache.exists():
        all_pairs = pd.read_csv(pair_cache)
    else:
        frames = [
            load_pair_table(config, config["sample_iii_calib_runs"], "sample_iii", "calib"),
            load_pair_table(config, config["sample_iii_analysis_runs"], "sample_iii", "analysis"),
            load_pair_table(config, config["sample_iv_calib_runs"], "sample_iv", "calib"),
            load_pair_table(config, config["sample_iv_analysis_runs"], "sample_iv", "analysis"),
        ]
        all_pairs = pd.concat(frames, ignore_index=True)
        all_pairs.to_csv(pair_cache, index=False, compression="gzip")

    repro = make_reproduction(all_pairs, config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        print(repro.to_string(index=False))
        return 1

    heldout_frames = []
    cv_frames = []
    for sample in ["sample_iii", "sample_iv"]:
        held, cv = evaluate_loro(all_pairs, sample, config)
        heldout_frames.append(held)
        cv_frames.append(cv)
    heldout = pd.concat(heldout_frames, ignore_index=True)
    cv_scan = pd.concat(cv_frames, ignore_index=True)
    heldout.to_csv(out_dir / "heldout_pair_predictions.csv", index=False)
    cv_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)

    metrics, deltas = summarize_methods(heldout, config, rng)
    runs = run_summary(heldout, config)
    leakage = leakage_checks(all_pairs, heldout, config, rng)
    tolerances = tolerance_table(metrics, runs)

    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas.csv", index=False)
    runs.to_csv(out_dir / "run_stability_table.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    tolerances.to_csv(out_dir / "tolerance_table.csv", index=False)

    input_files = [root_path(config, run) for run in all_input_runs(config)]
    pd.DataFrame(
        [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files]
    ).to_csv(out_dir / "input_sha256.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    xlabels = []
    x = []
    y = []
    yerr_low = []
    yerr_high = []
    for i, (_, row) in enumerate(metrics.iterrows()):
        x.append(i)
        xlabels.append(f"{row['sample'].replace('sample_', 'S')}\n{row['method']}")
        y.append(row["percentile68_ns"])
        yerr_low.append(row["percentile68_ns"] - row["percentile68_ns_ci_low"])
        yerr_high.append(row["percentile68_ns_ci_high"] - row["percentile68_ns"])
    ax.errorbar(x, y, yerr=[yerr_low, yerr_high], fmt="o", capsize=4)
    ax.set_xticks(x, xlabels)
    ax.set_ylabel("Percentile-68 width (ns)")
    ax.set_title("S18e run-held-out A-stack width")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_percentile68_head_to_head.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for sample in ["sample_iii", "sample_iv"]:
        sub = runs[runs["sample"].eq(sample)]
        ax.plot(sub["run"], sub["traditional_percentile68_ns"], marker="o", label=f"{sample} traditional")
        ax.plot(sub["run"], sub["ml_percentile68_ns"], marker="s", linestyle="--", label=f"{sample} ML")
    ax.set_xlabel("Held-out run")
    ax.set_ylabel("Per-run percentile-68 width (ns)")
    ax.set_title("S18e per-run stability")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_stability.png", dpi=160)
    plt.close(fig)

    write_report(out_dir, args.config, repro, metrics, deltas, runs, tolerances, leakage)

    result = {
        "study": "S18e",
        "ticket": "1781014670.1039.33790a03",
        "worker": "testbeam-laptop-2",
        "reproduced": bool(repro["pass"].all()),
        "primary_number_reproduced": {
            "sample_iv_n_pairs": int(repro.loc[repro["quantity"].eq("sample_iv_A1_A3_pairs"), "reproduced"].iloc[0]),
            "sample_iv_percentile68_width_ns": float(repro.loc[repro["quantity"].eq("sample_iv_robust_width_ns"), "reproduced"].iloc[0]),
            "sample_iv_binned_gaussian_core_sigma_ns": float(repro.loc[repro["quantity"].eq("sample_iv_core_sigma_ns"), "reproduced"].iloc[0]),
        },
        "recommended_standard_estimator": "percentile68_ns",
        "traditional": metrics[metrics["method"].eq("traditional")].set_index("sample")[
            ["percentile68_ns", "percentile68_ns_ci_low", "percentile68_ns_ci_high", "mad_sigma_ns", "iqr_sigma_ns", "trimmed_normal_sigma_ns", "student_t_width68_ns", "gaussian_core_sigma_ns"]
        ].to_dict("index"),
        "ml": metrics[metrics["method"].eq("ml")].set_index("sample")[
            ["percentile68_ns", "percentile68_ns_ci_low", "percentile68_ns_ci_high", "mad_sigma_ns", "iqr_sigma_ns", "trimmed_normal_sigma_ns", "student_t_width68_ns", "gaussian_core_sigma_ns"]
        ].to_dict("index"),
        "ml_minus_traditional": deltas.to_dict("records"),
        "tolerance_table": tolerances.to_dict("records"),
        "diagnosis": {
            "leakage_flags": int(leakage["flag"].sum()),
            "conclusion": "Use unbinned percentile68_ns as the A-stack primary core-width estimator; keep MAD/IQR, trimmed-normal, and Student-t as diagnostics; do not use the Sample IV ML gain for standards because it is inconsistent across samples and has a shuffled-target control flag.",
        },
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_manifest(out_dir, args.config, input_files, config)

    print(repro.to_string(index=False))
    print("\nMethod metrics:")
    print(metrics[["sample", "method", "n_pairs", "percentile68_ns", "percentile68_ns_ci_low", "percentile68_ns_ci_high", "gaussian_core_sigma_ns"]].to_string(index=False))
    print(f"\nreport artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
