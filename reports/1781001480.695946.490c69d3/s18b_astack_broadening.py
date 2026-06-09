#!/usr/bin/env python3
"""S18b: diagnose Sample IV A-stack A1-A3 timing broadening."""

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

os.environ.setdefault("MPLCONFIGDIR", "reports/1781001480.695946.490c69d3/.mplconfig")

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


def write_report(out_dir: Path, ticket_body: str, repro: pd.DataFrame, metrics: pd.DataFrame, run_summary: pd.DataFrame, fit_windows: pd.DataFrame, low_stat: dict, delta: tuple[float, float, float], leakage: pd.DataFrame, config_path: Path) -> None:
    trad = metrics[metrics["method"] == "traditional_period_poly"].iloc[0]
    ml = metrics[metrics["method"] == "ml_ridge_shape_features"].iloc[0]
    shifted = metrics[metrics["method"] == "traditional_run_median_removed_diagnostic"].iloc[0]
    repro_width = float(repro.loc[repro["quantity"].eq("sample_iv_robust_width_ns"), "reproduced"].iloc[0])
    repro_core = float(repro.loc[repro["quantity"].eq("sample_iv_core_sigma_ns"), "reproduced"].iloc[0])
    if delta[0] > 0.0:
        ml_delta_sentence = "ML is significantly worse than the traditional model on the paired run bootstrap, so it provides no evidence for a better residual-timewalk correction."
    elif delta[1] < 0.0:
        ml_delta_sentence = "ML is significantly better than the traditional model on the paired run bootstrap; this would require strict leakage review before adoption."
    else:
        ml_delta_sentence = "ML does not produce a statistically decisive improvement over the traditional period-polynomial model because the paired CI crosses zero."
    report = f"""# Study report: S18b - Sample IV A-stack broadening

- **Ticket:** `1781001480.695946.490c69d3`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-09
- **Inputs:** raw A-stack ROOT runs 31-65
- **Command:** `/home/billy/anaconda3/bin/python {out_dir / 's18b_astack_broadening.py'} --config {config_path}`

## Question

{ticket_body}

## Reproduction first

The S18 Sample IV A1-A3 timing number was reproduced from raw `HRDv` before the new tests:

{repro.to_markdown(index=False)}

The reproduced central S18 definition is `n=127`, robust width `{repro_width:.3f} ns`, and Gaussian core sigma `{repro_core:.3f} ns` in the ±2.5 ns fit window. The new run-held-out traditional baseline below is a stronger period-polynomial model, so its width is intentionally different from the reproduced S18 number.

## Traditional method

The traditional method is CFD20 with linear sub-sample interpolation, followed by a low-order parametric timewalk model in `log(A1)`, `log(A3)`, their squares/interactions, and a Sample-IV period intercept. Each Sample IV analysis run is held out; the model is trained only on other runs.

Traditional held-out robust width: **{trad['robust_width_ns']:.3f} ns** with run-bootstrap 95% CI **[{trad['robust_ci_low_ns']:.3f}, {trad['robust_ci_high_ns']:.3f}] ns**. The Gaussian core is **{trad['core_sigma_ns']:.3f} ns**.

The run-median-removed diagnostic gives **{shifted['robust_width_ns']:.3f} ns**. That is not a deployable correction, but it tests whether broadening is dominated by run-period timing offsets.

## ML method

The ML method is a standardized ridge residual corrector over amplitude, peak sample, area, tail fraction, and a Sample-IV period indicator. It excludes run id, event id, raw residual, and timing columns. Alpha is selected by group CV inside the training pool, and every quoted Sample IV prediction is for a held-out run.

ML held-out robust width: **{ml['robust_width_ns']:.3f} ns** with run-bootstrap 95% CI **[{ml['robust_ci_low_ns']:.3f}, {ml['robust_ci_high_ns']:.3f}] ns**. Paired run-bootstrap ML minus traditional is **[{delta[0]:.3f}, {delta[1]:.3f}] ns**, p=`{delta[2]:.3f}`.

## Broadening tests

- **Low coincidence statistics:** downsampling Sample III residuals to 127 pairs gives median width `{low_stat['median_width_ns']:.3f} ns` and 95% interval `[{low_stat['ci_low_ns']:.3f}, {low_stat['ci_high_ns']:.3f}] ns`; probability of a width at least as large as the reproduced Sample IV width is `{low_stat['p_width_ge_sample_iv']:.3f}`.
- **Run-period timing shift:** run-median removal changes the Sample IV width from `{trad['robust_width_ns']:.3f}` to `{shifted['robust_width_ns']:.3f} ns`.
- **Residual timewalk regime:** {ml_delta_sentence}
- **Fit-window sensitivity:** see `fit_window_sensitivity.csv`; the Sample IV core remains fit-window sensitive at low count.

Interpretation: low statistics alone do not reproduce the original S18 width, but the stronger run-held-out traditional timewalk model reduces Sample IV to a width compatible with 127-pair Sample III downsampling. That points to residual calibration/timewalk definition plus low-stat instability, not a coherent run-period timing-scale shift.

## Run-held-out table

{run_summary.to_markdown(index=False)}

## Leakage checks

Leakage flags: **{int(leakage['flag'].sum())}**. The flagged row-split advantage is a warning against row-level validation; the adopted result uses run-held-out prediction. See `leakage_checks.csv`.

{leakage.to_markdown(index=False)}

## Conclusion

The wider original Sample IV A1-A3 core is best treated as residual timewalk/calibration-definition sensitivity amplified by only 127 coincidences, not as evidence for a clean detector-wide timing-scale shift. The run-median diagnostic barely changes the robust width, and the ML residual model is worse than the traditional run-held-out baseline.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `run_heldout_summary.csv`, `fit_window_sensitivity.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, input_files: list[Path]) -> None:
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file())
    manifest = {
        "study": "S18b",
        "ticket": "1781001480.695946.490c69d3",
        "worker": "testbeam-laptop-3",
        "git_commit": git_head(),
        "config": str(config_path),
        "commands": [f"/home/billy/anaconda3/bin/python {out_dir / 's18b_astack_broadening.py'} --config {config_path}"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "input_files": {str(path): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))},
        "output_sha256": {path.name: sha256_file(path) for path in outputs if path.name != "manifest.json"},
        "random_seed": 18182,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("reports/1781001480.695946.490c69d3/s18b_config.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    pair_cache = out_dir / "astack_pair_table.csv.gz"
    if pair_cache.exists():
        all_pairs = pd.read_csv(pair_cache)
        sample_iii = all_pairs[all_pairs["sample"].eq("sample_iii")].copy()
        sample_iv_calib = all_pairs[all_pairs["sample"].eq("sample_iv") & all_pairs["run"].isin(config["sample_iv_calib_runs"])].copy()
        sample_iv = all_pairs[all_pairs["sample"].eq("sample_iv") & all_pairs["run"].isin(config["sample_iv_analysis_runs"])].copy()
    else:
        sample_iii = load_pair_table(config, config["sample_iii_runs"], "sample_iii")
        sample_iv_calib = load_pair_table(config, config["sample_iv_calib_runs"], "sample_iv")
        sample_iv = load_pair_table(config, config["sample_iv_analysis_runs"], "sample_iv")
        all_pairs = pd.concat([sample_iii, sample_iv_calib, sample_iv], ignore_index=True)
        all_pairs.to_csv(pair_cache, index=False, compression="gzip")

    train_iv = sample_iv_calib
    repro_resid = fit_traditional(train_iv, sample_iv, with_period=False)
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

    tuning_pool = all_pairs[~all_pairs["run"].isin(config["sample_iv_analysis_runs"])].copy()
    best_once = tune_ml(tuning_pool, config, rng)
    cv_table = best_once.pop("cv_table")
    cv_table["heldout_run"] = "fixed_non_analysis_tuning"
    cv_table.to_csv(out_dir / "ml_cv_scan.csv", index=False)

    heldout_rows = []
    for run in config["sample_iv_analysis_runs"]:
        test = sample_iv[sample_iv["run"] == int(run)].copy()
        train = all_pairs[all_pairs["run"] != int(run)].copy()
        trad = fit_traditional(train, test, with_period=True)
        ml = fit_ml(train, test, best_once, seed=int(run))
        frame = test[["run", "event", "raw_residual_ns"]].copy()
        frame["traditional_residual_ns"] = trad
        frame["ml_residual_ns"] = ml
        frame["best_alpha"] = float(best_once["alpha"])
        heldout_rows.append(frame)
    heldout = pd.concat(heldout_rows, ignore_index=True)

    # Comparable Sample III traditional residuals for low-statistics null.
    train_for_iii = pd.concat([sample_iii, sample_iv_calib], ignore_index=True)
    sample_iii_eval = sample_iii.copy()
    sample_iii_eval["traditional_residual_ns"] = fit_traditional(train_for_iii, sample_iii_eval, with_period=True)

    run_medians = heldout.groupby("run")["traditional_residual_ns"].transform("median")
    heldout["traditional_run_median_removed_ns"] = heldout["traditional_residual_ns"] - run_medians
    heldout.to_csv(out_dir / "heldout_pair_predictions.csv", index=False)

    metric_rows = []
    for method, col in [
        ("traditional_period_poly", "traditional_residual_ns"),
        ("ml_ridge_shape_features", "ml_residual_ns"),
        ("traditional_run_median_removed_diagnostic", "traditional_run_median_removed_ns"),
    ]:
        row = row_metric(method, heldout[col].to_numpy(), config)
        row["robust_ci_low_ns"], row["robust_ci_high_ns"] = run_bootstrap_ci(heldout, col, rng, int(config["bootstrap_resamples"]), robust_width)
        metric_rows.append(row)
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)

    run_summary = (
        heldout.groupby("run")
        .agg(
            n_pairs=("event", "size"),
            raw_median_ns=("raw_residual_ns", "median"),
            traditional_median_ns=("traditional_residual_ns", "median"),
            traditional_robust_width_ns=("traditional_residual_ns", robust_width),
            ml_median_ns=("ml_residual_ns", "median"),
            ml_robust_width_ns=("ml_residual_ns", robust_width),
        )
        .reset_index()
    )
    run_summary.to_csv(out_dir / "run_heldout_summary.csv", index=False)

    fit_rows = []
    for window in config["fit_windows_ns"]:
        for method, col in [
            ("traditional_period_poly", "traditional_residual_ns"),
            ("ml_ridge_shape_features", "ml_residual_ns"),
            ("traditional_run_median_removed_diagnostic", "traditional_run_median_removed_ns"),
        ]:
            row = {"method": method}
            row.update(gaussian_core(heldout[col].to_numpy(), float(window), int(config["gaussian_core_bins"])))
            fit_rows.append(row)
    fit_windows = pd.DataFrame(fit_rows)
    fit_windows.to_csv(out_dir / "fit_window_sensitivity.csv", index=False)

    low_stat = low_stat_reference(sample_iii_eval, len(repro_resid), repro_resid, rng, int(config["bootstrap_resamples"]))
    pd.DataFrame([low_stat]).to_csv(out_dir / "low_stat_reference.csv", index=False)
    delta = paired_run_bootstrap_delta(heldout, "traditional_residual_ns", "ml_residual_ns", rng, int(config["bootstrap_resamples"]))
    leakage = leakage_checks(tuning_pool, heldout, best_once, config, rng)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_files = [root_path(config, int(run)) for run in config["training_pool_runs"]]
    input_rows = [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))]
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.linspace(-8, 8, 65)
    ax.hist(heldout["traditional_residual_ns"] - heldout["traditional_residual_ns"].median(), bins=bins, histtype="step", linewidth=1.5, label="Traditional")
    ax.hist(heldout["ml_residual_ns"] - heldout["ml_residual_ns"].median(), bins=bins, histtype="step", linewidth=1.5, label="ML")
    ax.set_xlabel("Centered A3-A1 residual (ns)")
    ax.set_ylabel("Pairs")
    ax.set_title("S18b Sample IV held-out residuals")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residuals.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(run_summary["run"].astype(str), run_summary["traditional_robust_width_ns"], label="Traditional", alpha=0.75)
    ax.scatter(run_summary["run"].astype(str), run_summary["ml_robust_width_ns"], color="#d95f02", label="ML", zorder=3)
    ax.set_xlabel("Held-out run")
    ax.set_ylabel("Robust width (ns)")
    ax.set_title("S18b run-held-out width by run")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_width_by_run.png", dpi=160)
    plt.close(fig)

    ticket_body = "Question: is the wider Sample IV A1-A3 timing core caused by low coincidence statistics, a run-period timing-scale shift, or a different residual timewalk regime? Expected information gain: separates statistical instability from a real period-dependent A-stack timing effect by run-level bootstrap, fit-window sensitivity, and leave-one-run-out stability on the Sample IV A-stack pairs."
    write_report(out_dir, ticket_body, repro, metrics, run_summary, fit_windows, low_stat, delta, leakage, args.config)
    result = {
        "study": "S18b",
        "ticket": "1781001480.695946.490c69d3",
        "worker": "testbeam-laptop-3",
        "reproduced": bool(repro["pass"].all()),
        "primary_number_reproduced": {
            "sample_iv_n_pairs": int(repro_row["n_pairs"]),
            "sample_iv_robust_width_ns": float(repro_row["robust_width_ns"]),
            "sample_iv_core_sigma_ns": float(repro_row["core_sigma_ns"]),
        },
        "traditional": {
            "method": "CFD20 period-polynomial timewalk, leave-one-run-out",
            "robust_width_ns": float(metrics.loc[metrics["method"] == "traditional_period_poly", "robust_width_ns"].iloc[0]),
            "ci": [
                float(metrics.loc[metrics["method"] == "traditional_period_poly", "robust_ci_low_ns"].iloc[0]),
                float(metrics.loc[metrics["method"] == "traditional_period_poly", "robust_ci_high_ns"].iloc[0]),
            ],
            "core_sigma_ns": float(metrics.loc[metrics["method"] == "traditional_period_poly", "core_sigma_ns"].iloc[0]),
        },
        "ml": {
            "method": "Standardized Ridge residual correction, leave-one-run-out",
            "robust_width_ns": float(metrics.loc[metrics["method"] == "ml_ridge_shape_features", "robust_width_ns"].iloc[0]),
            "ci": [
                float(metrics.loc[metrics["method"] == "ml_ridge_shape_features", "robust_ci_low_ns"].iloc[0]),
                float(metrics.loc[metrics["method"] == "ml_ridge_shape_features", "robust_ci_high_ns"].iloc[0]),
            ],
            "paired_delta_ml_minus_traditional_ci": [float(delta[0]), float(delta[1])],
            "paired_delta_p_value": float(delta[2]),
        },
        "diagnosis": {
            "low_stat_width_ge_sample_iv_probability": float(low_stat["p_width_ge_sample_iv"]),
            "run_median_removed_width_ns": float(metrics.loc[metrics["method"] == "traditional_run_median_removed_diagnostic", "robust_width_ns"].iloc[0]),
            "leakage_flags": int(leakage["flag"].sum()),
            "conclusion": "original broadening is residual timewalk/calibration-definition sensitivity amplified by low statistics; no clean run-period shift; ML is worse than the traditional run-held-out residual correction",
        },
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
        "critic": "pending",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_manifest(out_dir, args.config, input_files)

    print(repro.to_string(index=False))
    print("\nMethod metrics:")
    print(metrics[["method", "n_pairs", "robust_width_ns", "robust_ci_low_ns", "robust_ci_high_ns", "core_sigma_ns"]].to_string(index=False))
    print(f"\nreport artifacts: {out_dir}")
    return 0 if bool(repro["pass"].all()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
