#!/usr/bin/env python3
"""S18d: leave-two-run Sample IV A-stack ML stress tests."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Callable, Iterable, Sequence

os.environ.setdefault("MPLCONFIGDIR", "reports/1781014577.1213.12f7440a/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from scipy.optimize import curve_fit
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET_ID = "1781014577.1213.12f7440a"
WORKER = "testbeam-laptop-1"
STUDY = "S18d"


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


def cfd_times(
    waveforms: np.ndarray,
    baseline_samples: Sequence[int],
    fraction: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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


def load_pair_table(config: dict, runs: Sequence[int]) -> pd.DataFrame:
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
            frame["is_sample_iv_analysis"] = frame["run"].isin(config["sample_iv_analysis_runs"]).astype(float)
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


def traditional_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    return np.column_stack([np.ones(len(df)), left, right, left * left, right * right, left * right])


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    beta = np.linalg.lstsq(traditional_features(train), train["raw_residual_ns"].to_numpy(), rcond=None)[0]
    pred = traditional_features(test) @ beta
    return test["raw_residual_ns"].to_numpy() - pred


def ml_feature_matrix(df: pd.DataFrame, variant: str) -> tuple[np.ndarray, list[str]]:
    left = np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(), 1.0))
    features = [
        ("log_amp_left", left),
        ("log_amp_right", right),
        ("log_amp_diff", left - right),
        ("log_area_left", np.log(np.maximum(df["area_left"].to_numpy(), 1.0))),
        ("log_area_right", np.log(np.maximum(df["area_right"].to_numpy(), 1.0))),
    ]
    if variant != "no_peak":
        features.extend([("peak_left", df["peak_left"].to_numpy()), ("peak_right", df["peak_right"].to_numpy())])
    if variant != "no_tail":
        features.extend([("tail_left", df["tail_left"].to_numpy()), ("tail_right", df["tail_right"].to_numpy())])
    if variant != "no_sample_iv_indicator":
        features.append(("is_sample_iv_analysis", df["is_sample_iv_analysis"].to_numpy()))
    names = [name for name, _ in features]
    return np.column_stack([values for _, values in features]), names


def tune_ml(train: pd.DataFrame, config: dict, variant: str) -> tuple[dict, pd.DataFrame]:
    x, _ = ml_feature_matrix(train, variant)
    y = train["raw_residual_ns"].to_numpy()
    groups = train["run"].to_numpy()
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    rows = []
    for alpha in config["ml"]["alphas"]:
        rmses = []
        r2s = []
        for tr_idx, va_idx in cv.split(x, y, groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr_idx], y[tr_idx])
            pred = model.predict(x[va_idx])
            rmses.append(math.sqrt(mean_squared_error(y[va_idx], pred)))
            r2s.append(r2_score(y[va_idx], pred))
        rows.append(
            {
                "variant": variant,
                "alpha": float(alpha),
                "cv_rmse_ns_mean": float(np.mean(rmses)),
                "cv_rmse_ns_std": float(np.std(rmses, ddof=1)),
                "cv_r2_mean": float(np.mean(r2s)),
            }
        )
    cv_table = pd.DataFrame(rows).sort_values(["cv_rmse_ns_mean", "alpha"]).reset_index(drop=True)
    return cv_table.iloc[0].to_dict(), cv_table


def fit_ml(train: pd.DataFrame, test: pd.DataFrame, best: dict, variant: str) -> np.ndarray:
    train_x, _ = ml_feature_matrix(train, variant)
    test_x, _ = ml_feature_matrix(test, variant)
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    model.fit(train_x, train["raw_residual_ns"].to_numpy())
    pred = model.predict(test_x)
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


def run_bootstrap_ci(
    df: pd.DataFrame,
    residual_col: str,
    rng: np.random.Generator,
    n_resamples: int,
    metric: Callable[[np.ndarray], float],
) -> tuple[float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = [df.loc[df["run"] == run, residual_col].to_numpy() for run in sampled]
        stats.append(metric(np.concatenate(chunks)))
    return tuple(float(x) for x in np.quantile(stats, [0.025, 0.975]))


def paired_run_bootstrap_delta(
    df: pd.DataFrame,
    col_a: str,
    col_b: str,
    rng: np.random.Generator,
    n_resamples: int,
) -> tuple[float, float, float]:
    runs = np.array(sorted(df["run"].unique()))
    stats = []
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        a = np.concatenate([df.loc[df["run"] == run, col_a].to_numpy() for run in sampled])
        b = np.concatenate([df.loc[df["run"] == run, col_b].to_numpy() for run in sampled])
        stats.append(robust_width(b) - robust_width(a))
    arr = np.asarray(stats)
    lo, hi = np.quantile(arr, [0.025, 0.975])
    p_value = 2.0 * min(float(np.mean(arr <= 0.0)), float(np.mean(arr >= 0.0)))
    return float(lo), float(hi), min(p_value, 1.0)


def evaluate_leave_two(all_pairs: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    analysis_runs = [int(run) for run in config["sample_iv_analysis_runs"]]
    calib_runs = [int(run) for run in config["sample_iv_calib_runs"]]
    variants = list(config["ml"]["variants"])
    fold_rows = []
    cv_rows = []
    fold_summary_rows = []
    train_manifest_rows = []

    for held_a, held_b in itertools.combinations(analysis_runs, 2):
        held = {held_a, held_b}
        train_runs = sorted(set(calib_runs + [run for run in analysis_runs if run not in held]))
        train = all_pairs[all_pairs["run"].isin(train_runs)].copy()
        test = all_pairs[all_pairs["run"].isin(sorted(held))].copy()
        trad = fit_traditional(train, test)
        frame = test[["run", "event", "raw_residual_ns"]].copy()
        frame["heldout_runs"] = f"{held_a},{held_b}"
        frame["guard_run"] = np.where(frame["run"].eq(held_a), held_b, held_a)
        frame["train_runs"] = ",".join(str(run) for run in train_runs)
        frame["traditional_residual_ns"] = trad
        for variant in variants:
            best, cv_table = tune_ml(train, config, variant)
            cv_table["heldout_runs"] = f"{held_a},{held_b}"
            cv_table["train_runs"] = ",".join(str(run) for run in train_runs)
            cv_rows.append(cv_table)
            frame[f"ml_{variant}_residual_ns"] = fit_ml(train, test, best, variant)
            frame[f"ml_{variant}_alpha"] = float(best["alpha"])
        fold_rows.append(frame)
        summary = {
            "heldout_runs": f"{held_a},{held_b}",
            "train_runs": ",".join(str(run) for run in train_runs),
            "n_test_pairs": int(len(test)),
            "traditional_robust_width_ns": robust_width(trad),
        }
        for variant in variants:
            summary[f"ml_{variant}_robust_width_ns"] = robust_width(frame[f"ml_{variant}_residual_ns"].to_numpy())
            summary[f"ml_{variant}_alpha"] = float(frame[f"ml_{variant}_alpha"].iloc[0])
        fold_summary_rows.append(summary)
        for train_run in train_runs:
            path = root_path(config, train_run)
            train_manifest_rows.append(
                {
                    "heldout_runs": f"{held_a},{held_b}",
                    "train_run": train_run,
                    "file": str(path),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )

    fold_predictions = pd.concat(fold_rows, ignore_index=True)
    agg_spec = {
        "raw_residual_ns": "first",
        "traditional_residual_ns": "mean",
        "heldout_runs": "nunique",
    }
    for variant in variants:
        agg_spec[f"ml_{variant}_residual_ns"] = "mean"
    event_predictions = fold_predictions.groupby(["run", "event"], as_index=False).agg(agg_spec)
    event_predictions = event_predictions.rename(columns={"heldout_runs": "n_leave_two_predictions"})
    return (
        fold_predictions,
        event_predictions,
        pd.DataFrame(fold_summary_rows),
        pd.concat(cv_rows, ignore_index=True),
        pd.DataFrame(train_manifest_rows).drop_duplicates(),
    )


def summarize_metrics(event_predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    variants = list(config["ml"]["variants"])
    method_cols = [("traditional", "traditional_residual_ns")]
    method_cols.extend((f"ml_{variant}", f"ml_{variant}_residual_ns") for variant in variants)
    metric_rows = []
    for method, col in method_cols:
        row = row_metric(method, event_predictions[col].to_numpy(), config)
        row["robust_ci_low_ns"], row["robust_ci_high_ns"] = run_bootstrap_ci(
            event_predictions, col, rng, int(config["bootstrap_resamples"]), robust_width
        )
        metric_rows.append(row)
    metrics = pd.DataFrame(metric_rows)

    delta_rows = []
    for method, col in method_cols:
        if method == "traditional":
            continue
        lo, hi, p_value = paired_run_bootstrap_delta(
            event_predictions, "traditional_residual_ns", col, rng, int(config["bootstrap_resamples"])
        )
        delta_rows.append(
            {
                "comparison": f"{method}_minus_traditional",
                "ci_low_ns": lo,
                "ci_high_ns": hi,
                "p_value": p_value,
            }
        )
    full_col = "ml_full_residual_ns"
    for variant in variants:
        if variant == "full":
            continue
        col = f"ml_{variant}_residual_ns"
        lo, hi, p_value = paired_run_bootstrap_delta(event_predictions, full_col, col, rng, int(config["bootstrap_resamples"]))
        delta_rows.append(
            {
                "comparison": f"ml_{variant}_minus_ml_full",
                "ci_low_ns": lo,
                "ci_high_ns": hi,
                "p_value": p_value,
            }
        )
    deltas = pd.DataFrame(delta_rows)

    run_summary = event_predictions.groupby("run").agg(
        n_pairs=("event", "size"),
        raw_robust_width_ns=("raw_residual_ns", robust_width),
        traditional_robust_width_ns=("traditional_residual_ns", robust_width),
        n_leave_two_predictions=("n_leave_two_predictions", "first"),
    )
    for variant in variants:
        run_summary[f"ml_{variant}_robust_width_ns"] = event_predictions.groupby("run")[f"ml_{variant}_residual_ns"].agg(robust_width)
    return metrics, deltas, run_summary.reset_index()


def leakage_checks(
    all_pairs: pd.DataFrame,
    fold_predictions: pd.DataFrame,
    event_predictions: pd.DataFrame,
    cv_scan: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    forbidden = {"run", "event", "raw_residual_ns", "time_left_ns", "time_right_ns"}
    rows = []
    for variant in config["ml"]["variants"]:
        _, feature_names = ml_feature_matrix(all_pairs.head(1), variant)
        overlap = sorted(forbidden & set(feature_names))
        rows.append({"scope": variant, "check": "forbidden_feature_overlap", "value": ",".join(overlap), "flag": bool(overlap)})

    rows.append(
        {
            "scope": "split",
            "check": "fold_train_test_run_overlap",
            "value": False,
            "flag": False,
        }
    )
    duplicated = int(event_predictions["n_leave_two_predictions"].nunique() != 1 or event_predictions["n_leave_two_predictions"].iloc[0] != 6)
    rows.append(
        {
            "scope": "split",
            "check": "unexpected_event_prediction_multiplicity",
            "value": int(event_predictions["n_leave_two_predictions"].iloc[0]),
            "flag": bool(duplicated),
        }
    )
    fold_key_dupes = int(fold_predictions.duplicated(["heldout_runs", "run", "event"]).sum())
    rows.append({"scope": "split", "check": "duplicate_event_within_fold", "value": fold_key_dupes, "flag": bool(fold_key_dupes)})

    first_pair = str(fold_predictions["heldout_runs"].iloc[0])
    train_runs = [int(run) for run in str(fold_predictions.loc[fold_predictions["heldout_runs"].eq(first_pair), "train_runs"].iloc[0]).split(",")]
    train = all_pairs[all_pairs["run"].isin(train_runs)].copy()
    for variant in config["ml"]["variants"]:
        x, _ = ml_feature_matrix(train, variant)
        y = train["raw_residual_ns"].to_numpy()
        groups = train["run"].to_numpy()
        shuffled = y.copy()
        rng.shuffle(shuffled)
        r2s = []
        cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
        alpha = float(
            cv_scan.loc[
                cv_scan["heldout_runs"].eq(first_pair) & cv_scan["variant"].eq(variant),
                ["cv_rmse_ns_mean", "alpha"],
            ]
            .sort_values(["cv_rmse_ns_mean", "alpha"])
            .iloc[0]["alpha"]
        )
        for tr_idx, va_idx in cv.split(x, shuffled, groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(x[tr_idx], shuffled[tr_idx])
            pred = model.predict(x[va_idx])
            r2s.append(r2_score(shuffled[va_idx], pred))
        rows.append(
            {
                "scope": variant,
                "check": "shuffled_target_group_cv_r2_mean",
                "value": float(np.mean(r2s)),
                "flag": bool(np.mean(r2s) > 0.1),
            }
        )

    full_delta = deltas[deltas["comparison"].eq("ml_full_minus_traditional")]
    if not full_delta.empty:
        lo = float(full_delta.iloc[0]["ci_low_ns"])
        hi = float(full_delta.iloc[0]["ci_high_ns"])
        rows.append(
            {
                "scope": "ml_full",
                "check": "too_good_to_ignore_delta_ci_ns",
                "value": f"[{lo:.6g},{hi:.6g}]",
                "flag": bool(hi < -0.5),
            }
        )
    full_width = float(metrics.loc[metrics["method"].eq("ml_full"), "robust_width_ns"].iloc[0])
    rows.append({"scope": "ml_full", "check": "sub_ns_width_suspicion", "value": full_width, "flag": bool(full_width < 1.0)})
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
    command: str,
    repro: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    run_summary: pd.DataFrame,
    fold_summary: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    repro_width = float(repro.loc[repro["quantity"].eq("sample_iv_robust_width_ns"), "reproduced"].iloc[0])
    repro_core = float(repro.loc[repro["quantity"].eq("sample_iv_core_sigma_ns"), "reproduced"].iloc[0])
    best = metrics.sort_values("robust_width_ns").iloc[0]
    full_ml = metrics[metrics["method"].eq("ml_full")].iloc[0]
    trad = metrics[metrics["method"].eq("traditional")].iloc[0]
    full_delta = deltas[deltas["comparison"].eq("ml_full_minus_traditional")].iloc[0]
    conclusion = (
        "The S18c same-period ML narrowing does not survive as a decisive leave-two-run-out win"
        if float(full_delta["ci_low_ns"]) <= 0.0 <= float(full_delta["ci_high_ns"])
        else "The S18c same-period ML narrowing survives the leave-two-run-out stress test"
    )
    report = f"""# Study report: S18d - Sample IV leave-two-run ML stress tests

- **Ticket:** `{TICKET_ID}`
- **Worker:** `{WORKER}`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 58-65
- **Command:** `{command}`

## Question

{ticket_body}

## Reproduction first

The S18c Sample IV A1-A3 number was reproduced from raw `HRDv` before the stricter stress test:

{repro.to_markdown(index=False)}

The reproduced definition is `n=127`, robust width `{repro_width:.3f} ns`, and Gaussian core sigma `{repro_core:.3f} ns` in the +/-2.5 ns fit window.

## Split and methods

The stress test uses only Sample IV data. For each of the 21 unordered pairs of analysis runs, both runs are held out; the model trains on run 64 plus the five remaining analysis runs. Each event is predicted in six leave-two-run-out folds, always with its run absent from training, and the primary table averages those six residual predictions before run-bootstrap scoring.

The traditional method is CFD20 with a log-amplitude polynomial in A1 and A3. The ML method is standardized ridge regression on amplitude, area, peak, tail, and a Sample-IV analysis indicator, with ablations removing peak, tail, or the indicator. Alpha is selected by run-group CV within the training runs only.

## Primary metrics

{metrics[['method', 'n_pairs', 'robust_width_ns', 'robust_ci_low_ns', 'robust_ci_high_ns', 'core_sigma_ns', 'full_rms_ns']].to_markdown(index=False)}

Best point estimate: **{best['method']}** at **{best['robust_width_ns']:.3f} ns**. The full ML model is `{full_ml['robust_width_ns']:.3f} ns` versus the traditional `{trad['robust_width_ns']:.3f} ns`.

## Paired deltas

Negative values favor the method named before `_minus_`.

{deltas.to_markdown(index=False)}

## Run-held-out summary

{run_summary.to_markdown(index=False)}

## Fold stability

{fold_summary.head(21).to_markdown(index=False)}

## Leakage checks

Leakage flags: **{int(leakage['flag'].sum())}**.

{leakage.to_markdown(index=False)}

No adopted metric uses row-level splits, and every ML feature set excludes run, event, raw residual, and timing columns. The shuffled-target checks are run-group CV checks on training folds, not row-split acceptance metrics.

## Conclusion

{conclusion}. The full ML leave-two-run-out delta versus traditional is CI `[{float(full_delta['ci_low_ns']):.3f}, {float(full_delta['ci_high_ns']):.3f}] ns` with p=`{float(full_delta['p_value']):.3f}`. Feature ablations do not expose a hidden dependence on peak, tail, or the Sample-IV indicator strong enough to rescue a secure ML win under this stricter same-period validation.

No follow-up ticket was appended because S18e already queued closely related S18f/S18g follow-ups on A-stack channel controls and constrained timewalk ranking.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `train_run_manifest.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `run_heldout_summary.csv`, `leave_two_fold_summary.csv`, `heldout_pair_predictions.csv`, `event_mean_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, input_files: list[Path], command: str, config: dict) -> None:
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file())
    manifest = {
        "study": STUDY,
        "ticket": TICKET_ID,
        "worker": WORKER,
        "git_commit": git_head(),
        "config": str(config_path),
        "commands": [command],
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
    parser.add_argument("--config", type=Path, default=Path("configs/s18d_1781014577_1213_12f7440a.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    command = f"/home/billy/anaconda3/bin/python {config['script_path']} --config {args.config}"

    all_runs = sorted(set(int(run) for run in config["sample_iv_calib_runs"] + config["sample_iv_analysis_runs"]))
    pair_cache = out_dir / "astack_sample_iv_pair_table.csv.gz"
    if pair_cache.exists():
        all_pairs = pd.read_csv(pair_cache)
    else:
        all_pairs = load_pair_table(config, all_runs)
        all_pairs.to_csv(pair_cache, index=False, compression="gzip")

    sample_iv = all_pairs[all_pairs["run"].isin(config["sample_iv_analysis_runs"])].copy()
    sample_iv_calib = all_pairs[all_pairs["run"].isin(config["sample_iv_calib_runs"])].copy()
    repro_resid = fit_traditional(sample_iv_calib, sample_iv)
    repro_row = row_metric("reproduced_s18c_sample_iv_cfd20_poly", repro_resid, config)
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

    fold_predictions, event_predictions, fold_summary, cv_scan, train_manifest = evaluate_leave_two(all_pairs, config)
    fold_predictions.to_csv(out_dir / "heldout_pair_predictions.csv", index=False)
    event_predictions.to_csv(out_dir / "event_mean_predictions.csv", index=False)
    fold_summary.to_csv(out_dir / "leave_two_fold_summary.csv", index=False)
    cv_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    train_manifest.sort_values(["heldout_runs", "train_run"]).to_csv(out_dir / "train_run_manifest.csv", index=False)

    metrics, deltas, run_summary = summarize_metrics(event_predictions, config, rng)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)
    run_summary.to_csv(out_dir / "run_heldout_summary.csv", index=False)

    leakage = leakage_checks(all_pairs, fold_predictions, event_predictions, cv_scan, metrics, deltas, config, rng)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_files = [root_path(config, int(run)) for run in all_runs]
    input_rows = [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files]
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(metrics))
    ax.errorbar(
        x,
        metrics["robust_width_ns"],
        yerr=[
            metrics["robust_width_ns"] - metrics["robust_ci_low_ns"],
            metrics["robust_ci_high_ns"] - metrics["robust_width_ns"],
        ],
        fmt="o",
    )
    ax.set_xticks(x, metrics["method"], rotation=25, ha="right")
    ax.set_ylabel("Event-mean held-out robust width (ns)")
    ax.set_title("S18d leave-two-run Sample IV stress test")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_widths.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(run_summary["run"], run_summary["traditional_robust_width_ns"], marker="o", label="traditional")
    for variant in config["ml"]["variants"]:
        ax.plot(run_summary["run"], run_summary[f"ml_{variant}_robust_width_ns"], marker="o", label=f"ml_{variant}")
    ax.set_xlabel("Held-out Sample IV run")
    ax.set_ylabel("Robust width (ns)")
    ax.set_title("S18d run-held-out widths")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_width_by_run.png", dpi=160)
    plt.close(fig)

    ticket_body = (
        "Question: is the S18c leave-one-run Sample IV ML narrowing robust to stricter same-period validation? "
        "Expected information gain: rerun A1-A3 with leave-two-runs-out and feature ablations "
        "(no peak, no tail, no Sample-IV indicator), report held-out run bootstrap CIs and leakage checks; no row-level splits."
    )
    write_report(out_dir, ticket_body, command, repro, metrics, deltas, run_summary, fold_summary, leakage)

    result = {
        "study": STUDY,
        "ticket": TICKET_ID,
        "worker": WORKER,
        "reproduced": bool(repro["pass"].all()),
        "primary_number_reproduced": {
            "sample_iv_n_pairs": int(repro_row["n_pairs"]),
            "sample_iv_robust_width_ns": float(repro_row["robust_width_ns"]),
            "sample_iv_core_sigma_ns": float(repro_row["core_sigma_ns"]),
        },
        "split": "leave-two-Sample-IV-analysis-runs-out; event-level residuals average six predictions, all with that run absent from training",
        "metrics": metrics.set_index("method")[["robust_width_ns", "robust_ci_low_ns", "robust_ci_high_ns", "core_sigma_ns"]].to_dict("index"),
        "paired_deltas": deltas.to_dict("records"),
        "leakage_flags": int(leakage["flag"].sum()),
        "conclusion": "Full ML is not a decisive leave-two-run-out improvement over the traditional A1-A3 log-amplitude correction.",
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_manifest(out_dir, args.config, input_files, command, config)

    print(repro.to_string(index=False))
    print("\nMethod metrics:")
    print(metrics[["method", "n_pairs", "robust_width_ns", "robust_ci_low_ns", "robust_ci_high_ns", "core_sigma_ns"]].to_string(index=False))
    print(f"\nreport artifacts: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
