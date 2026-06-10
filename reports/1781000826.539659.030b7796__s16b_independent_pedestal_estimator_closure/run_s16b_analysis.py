#!/usr/bin/env python3
"""S16b independent early-sample pedestal estimator closure.

This study reads the raw ROOT files through the already-tracked S16 loader, then
builds a separate closure benchmark for early-sample baseline estimators.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Iterable, Sequence

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def load_base_module(path: Path):
    spec = importlib.util.spec_from_file_location("s16_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load base S16 module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configured_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def estimator_values(other_values: np.ndarray, other_idx: Sequence[int], holdout: int) -> dict[str, np.ndarray]:
    other_values = other_values.astype(np.float64)
    order = np.argsort(other_values, axis=1)
    sorted_vals = np.take_along_axis(other_values, order, axis=1)
    low2 = sorted_vals[:, :2].mean(axis=1)
    min3 = sorted_vals[:, 0]
    mean3 = other_values.mean(axis=1)
    median3 = np.median(other_values, axis=1)
    x = np.asarray(other_idx, dtype=np.float64)
    y = other_values
    xbar = float(np.mean(x))
    denom = float(np.sum((x - xbar) ** 2))
    if denom == 0.0:
        line = mean3
    else:
        ybar = y.mean(axis=1)
        slope = ((y - ybar[:, None]) * (x[None, :] - xbar)).sum(axis=1) / denom
        line = ybar + slope * (float(holdout) - xbar)
    return {
        "mean3": mean3,
        "median3": median3,
        "low2_mean3": low2,
        "min3": min3,
        "line3_predict": line,
    }


def build_closure_frame(meta: pd.DataFrame, waveforms: np.ndarray, config: dict) -> pd.DataFrame:
    pre = [int(x) for x in config["pretrigger_samples"]]
    frames = []
    pulse_index = np.arange(len(meta), dtype=int)
    for holdout in pre:
        others = [idx for idx in pre if idx != holdout]
        other = waveforms[:, others].astype(np.float64)
        values = estimator_values(other, others, holdout)
        pre_range = other.max(axis=1) - other.min(axis=1)
        late_peak = waveforms[:, 4:].max(axis=1).astype(np.float64)
        for method, estimate in values.items():
            residual = estimate - waveforms[:, holdout]
            frames.append(
                pd.DataFrame(
                    {
                        "run": meta["run"].to_numpy(dtype=int),
                        "group": meta["group"].to_numpy(),
                        "pulse_index": pulse_index,
                        "eventno": meta["eventno"].to_numpy(dtype=int),
                        "stave": meta["stave"].to_numpy(),
                        "stave_idx": meta["stave_idx"].to_numpy(dtype=int),
                        "amplitude_adc": meta["amplitude_adc"].to_numpy(dtype=float),
                        "peak_sample": meta["peak_sample"].to_numpy(dtype=int),
                        "holdout_sample": int(holdout),
                        "pre_range3_adc": pre_range,
                        "late_peak_raw_adc": late_peak,
                        "method": method,
                        "estimate_adc": estimate,
                        "reference_adc": waveforms[:, holdout].astype(float),
                        "residual_adc": residual,
                        "abs_residual_adc": np.abs(residual),
                    }
                )
            )
    out = pd.concat(frames, ignore_index=True)
    bins = [float(x) for x in config["amplitude_bins"]]
    labels = [f"{int(bins[i])}-{int(bins[i + 1])}" for i in range(len(bins) - 1)]
    out["amp_bin"] = pd.cut(out["amplitude_adc"], bins=bins, labels=labels, include_lowest=True, right=False)
    out["contamination_bin"] = pd.cut(
        out["pre_range3_adc"],
        bins=[-0.1, 50.0, 150.0, 500.0, np.inf],
        labels=["range<50", "50-150", "150-500", "range>=500"],
    )
    return out


def fit_calibrated_low2(closure: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    heldout = set(int(run) for run in config["heldout_runs"])
    train = closure[(closure["method"] == "low2_mean3") & ~closure["run"].isin(heldout)].copy()
    all_low2 = closure[closure["method"] == "low2_mean3"].copy()
    feature_cols = ["estimate_adc", "holdout_sample", "stave_idx", "pre_range3_adc", "amplitude_adc", "peak_sample"]
    max_train = int(config["ml"].get("traditional_calibration_max_records", len(train)))
    if len(train) > max_train:
        train = train.sample(n=max_train, random_state=int(config["ml"]["random_seed"]))
    model = HuberRegressor(epsilon=1.5, alpha=1e-4, max_iter=300)
    model.fit(train[feature_cols], train["reference_adc"])
    pred = all_low2[["run", "group", "pulse_index", "eventno", "stave", "stave_idx", "amplitude_adc", "peak_sample", "holdout_sample", "pre_range3_adc", "late_peak_raw_adc", "reference_adc", "amp_bin", "contamination_bin"]].copy()
    pred["method"] = "train_calibrated_low2"
    pred["estimate_adc"] = model.predict(all_low2[feature_cols])
    pred["residual_adc"] = pred["estimate_adc"] - pred["reference_adc"]
    pred["abs_residual_adc"] = pred["residual_adc"].abs()
    return pred, {"feature_columns": feature_cols, "n_train": int(len(train))}


def summarize(frame: pd.DataFrame, group_cols: Sequence[str]) -> pd.DataFrame:
    rows = []
    grouped: Iterable
    grouped = frame.groupby(list(group_cols), dropna=False) if group_cols else [((), frame)]
    for key, sub in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        residual = sub["residual_adc"].to_numpy(dtype=float)
        abs_res = np.abs(residual)
        row = {name: value for name, value in zip(group_cols, key)}
        row.update(
            {
                "n": int(len(sub)),
                "mean_bias_adc": float(np.mean(residual)),
                "mae_adc": float(np.mean(abs_res)),
                "rmse_adc": float(math.sqrt(np.mean(residual ** 2))),
                "median_bias_adc": float(np.median(residual)),
                "q05_adc": float(np.quantile(residual, 0.05)),
                "q95_adc": float(np.quantile(residual, 0.95)),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_metric_ci(values: np.ndarray, fn: Callable[[np.ndarray], float], rng: np.random.Generator, reps: int) -> list[float]:
    values = np.asarray(values, dtype=float)
    stats = []
    for _ in range(int(reps)):
        sample = rng.choice(values, size=len(values), replace=True)
        stats.append(float(fn(sample)))
    return [float(x) for x in np.quantile(stats, [0.025, 0.975])]


def paired_bootstrap_delta(
    frame: pd.DataFrame,
    ml_method: str,
    trad_method: str,
    rng: np.random.Generator,
    reps: int,
) -> dict:
    key_cols = ["run", "pulse_index", "stave_idx", "holdout_sample"]
    left = frame[frame["method"] == ml_method][key_cols + ["abs_residual_adc"]].rename(columns={"abs_residual_adc": "ml_abs"})
    right = frame[frame["method"] == trad_method][key_cols + ["abs_residual_adc"]].rename(columns={"abs_residual_adc": "trad_abs"})
    merged = left.merge(right, on=key_cols, how="inner")
    delta = (merged["ml_abs"] - merged["trad_abs"]).to_numpy(dtype=float)
    ci = bootstrap_metric_ci(delta, np.mean, rng, reps)
    return {
        "ml_method": ml_method,
        "traditional_method": trad_method,
        "n_pairs": int(len(merged)),
        "delta_mae_adc": float(np.mean(delta)),
        "delta_mae_ci_low_adc": ci[0],
        "delta_mae_ci_high_adc": ci[1],
    }


def build_ml_features(meta: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    max_records = int(config["ml"]["max_records"])
    n_pulses = len(meta)
    per_holdout = max_records // len(config["pretrigger_samples"])
    rows = []
    for holdout in [int(x) for x in config["pretrigger_samples"]]:
        other_pre = [idx for idx in config["pretrigger_samples"] if int(idx) != holdout]
        take = min(per_holdout, n_pulses)
        chosen = rng.choice(np.arange(n_pulses), size=take, replace=False)
        other = waveforms[chosen][:, other_pre].astype(np.float64)
        values = estimator_values(other, other_pre, holdout)
        seed = values["median3"]
        corrected = waveforms[chosen].astype(np.float64) - seed[:, None]
        feature = pd.DataFrame(
            {
                "run": meta["run"].to_numpy(dtype=int)[chosen],
                "pulse_index": chosen.astype(int),
                "eventno": meta["eventno"].to_numpy(dtype=int)[chosen],
                "stave_idx": meta["stave_idx"].to_numpy(dtype=int)[chosen],
                "holdout_sample": int(holdout),
                "target_adc": waveforms[chosen, holdout].astype(float),
                "pre_mean3": values["mean3"],
                "pre_median3": values["median3"],
                "pre_low2_mean3": values["low2_mean3"],
                "pre_min3": values["min3"],
                "pre_line3_predict": values["line3_predict"],
                "pre_range3": other.max(axis=1) - other.min(axis=1),
                "amplitude_adc": corrected.max(axis=1),
                "peak_sample": corrected.argmax(axis=1),
                "late_peak_minus_seed": corrected[:, 4:].max(axis=1),
            }
        )
        for sample_idx in range(waveforms.shape[1]):
            if sample_idx == holdout:
                continue
            feature[f"w{sample_idx:02d}_minus_seed"] = corrected[:, sample_idx]
        rows.append(feature)
    return pd.concat(rows, ignore_index=True)


def train_ml(features: pd.DataFrame, config: dict, shuffled: bool = False, fixed_params: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    seed = int(config["ml"]["random_seed"]) + (99 if shuffled else 0)
    rng = np.random.default_rng(seed)
    heldout_runs = set(int(run) for run in config["heldout_runs"])
    calibration_runs = set(int(run) for run in config["calibration_runs"])
    feature_cols = [
        col
        for col in features.columns
        if col not in {"target_adc", "pulse_index", "eventno", "run"}
    ]
    train_cv = features[~features["run"].isin(heldout_runs)].copy()
    test = features[features["run"].isin(heldout_runs)].copy()
    if shuffled:
        shuffled_target = train_cv["target_adc"].to_numpy(dtype=float).copy()
        for holdout in sorted(train_cv["holdout_sample"].unique()):
            idx = np.where(train_cv["holdout_sample"].to_numpy() == holdout)[0]
            segment = shuffled_target[idx].copy()
            rng.shuffle(segment)
            shuffled_target[idx] = segment
        train_cv["target_adc"] = shuffled_target
    core_train = train_cv[~train_cv["run"].isin(calibration_runs)].copy()
    calibration = train_cv[train_cv["run"].isin(calibration_runs)].copy()
    if fixed_params is None:
        params = config["ml"]["hyperparameters"]
        groups = train_cv["run"].to_numpy(dtype=int)
        cv = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
        scan_rows = []
        for alpha in params["alpha"]:
            scores = []
            for train_idx, valid_idx in cv.split(train_cv[feature_cols], train_cv["target_adc"], groups=groups):
                model = Ridge(alpha=float(alpha))
                model.fit(train_cv.iloc[train_idx][feature_cols].fillna(0.0), train_cv.iloc[train_idx]["target_adc"])
                pred = model.predict(train_cv.iloc[valid_idx][feature_cols].fillna(0.0))
                scores.append(mean_absolute_error(train_cv.iloc[valid_idx]["target_adc"], pred))
            scan_rows.append(
                {
                    "alpha": float(alpha),
                    "cv_mae_adc": float(np.mean(scores)),
                    "cv_mae_std_adc": float(np.std(scores, ddof=1)),
                    "shuffled_target": bool(shuffled),
                }
            )
        scan = pd.DataFrame(scan_rows).sort_values("cv_mae_adc").reset_index(drop=True)
        best = scan.iloc[0].to_dict()
    else:
        best = {
            "alpha": float(fixed_params["alpha"]),
            "cv_mae_adc": float("nan"),
            "cv_mae_std_adc": float("nan"),
            "shuffled_target": bool(shuffled),
        }
        scan = pd.DataFrame([best])
    model = Ridge(alpha=float(best["alpha"]))
    model.fit(core_train[feature_cols].fillna(0.0), core_train["target_adc"])
    cal_pred = model.predict(calibration[feature_cols].fillna(0.0))
    calibrator = LinearRegression().fit(cal_pred.reshape(-1, 1), calibration["target_adc"])
    raw_pred = model.predict(test[feature_cols].fillna(0.0))
    calibrated = calibrator.predict(raw_pred.reshape(-1, 1))
    pred_frame = test[["run", "pulse_index", "eventno", "stave_idx", "holdout_sample", "target_adc", "amplitude_adc", "peak_sample"]].copy()
    pred_frame["method"] = "ml_ridge_calibrated_shuffled_target" if shuffled else "ml_ridge_calibrated"
    pred_frame["estimate_adc"] = calibrated
    pred_frame["reference_adc"] = pred_frame["target_adc"]
    pred_frame["residual_adc"] = pred_frame["estimate_adc"] - pred_frame["reference_adc"]
    pred_frame["abs_residual_adc"] = pred_frame["residual_adc"].abs()
    meta = {
        "best": {"alpha": float(best["alpha"])},
        "best_cv_mae_adc": float(best["cv_mae_adc"]),
        "calibration_intercept": float(calibrator.intercept_),
        "calibration_slope": float(calibrator.coef_[0]),
        "feature_columns": feature_cols,
        "n_train_cv": int(len(train_cv)),
        "n_core_train": int(len(core_train)),
        "n_calibration": int(len(calibration)),
        "n_test": int(len(test)),
        "shuffled_target": bool(shuffled),
    }
    return scan, pred_frame, meta


def match_ml_to_closure(closure: pd.DataFrame, ml_pred: pd.DataFrame, methods: Sequence[str]) -> pd.DataFrame:
    key_cols = ["run", "pulse_index", "stave_idx", "holdout_sample"]
    keys = ml_pred[key_cols].drop_duplicates()
    frames = []
    for method in methods:
        sub = closure[closure["method"] == method]
        frames.append(keys.merge(sub, on=key_cols, how="left"))
    ml = ml_pred.copy()
    ml["group"] = ""
    ml["stave"] = ""
    ml["pre_range3_adc"] = np.nan
    ml["late_peak_raw_adc"] = np.nan
    ml["amp_bin"] = pd.NA
    ml["contamination_bin"] = pd.NA
    frames.append(ml)
    return pd.concat(frames, ignore_index=True)


def add_cis(summary: pd.DataFrame, frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    reps = int(config["ml"]["bootstrap_replicates"])
    for _, row in summary.iterrows():
        sub = frame[frame["method"] == row["method"]]
        residual = sub["residual_adc"].to_numpy(dtype=float)
        abs_res = np.abs(residual)
        mean_ci = bootstrap_metric_ci(residual, np.mean, rng, reps)
        mae_ci = bootstrap_metric_ci(abs_res, np.mean, rng, reps)
        rows.append(
            {
                **row.to_dict(),
                "mean_bias_ci_low_adc": mean_ci[0],
                "mean_bias_ci_high_adc": mean_ci[1],
                "mae_ci_low_adc": mae_ci[0],
                "mae_ci_high_adc": mae_ci[1],
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(outdir: Path, bench_frame: pd.DataFrame, by_contam: pd.DataFrame, benchmark: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    for method in ["mean3", "median3", "low2_mean3", "train_calibrated_low2", "ml_ridge_calibrated"]:
        sub = bench_frame[bench_frame["method"] == method]
        if sub.empty:
            continue
        ax.hist(sub["residual_adc"].clip(-250, 250), bins=100, density=True, histtype="step", linewidth=1.3, label=method)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("estimate - excluded early sample [ADC]")
    ax.set_ylabel("density")
    ax.set_title("Held-out run closure residuals")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_residual_distributions.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    methods = ["mean3", "median3", "low2_mean3", "min3", "line3_predict", "train_calibrated_low2"]
    pivot = by_contam[by_contam["method"].isin(methods)].pivot_table(index="contamination_bin", columns="method", values="mean_bias_adc")
    pivot.plot(kind="bar", ax=ax)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("mean bias [ADC]")
    ax.set_xlabel("range of the three visible early samples")
    ax.set_title("Bias versus pre-trigger activity proxy")
    fig.tight_layout()
    fig.savefig(outdir / "fig_bias_by_pretrigger_activity.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ordered = benchmark.sort_values("mae_adc")
    ax.barh(ordered["method"], ordered["mae_adc"], xerr=[ordered["mae_adc"] - ordered["mae_ci_low_adc"], ordered["mae_ci_high_adc"] - ordered["mae_adc"]])
    ax.set_xlabel("held-out MAE [ADC]")
    ax.set_title("Head-to-head held-out benchmark")
    fig.tight_layout()
    fig.savefig(outdir / "fig_head_to_head.png", dpi=150)
    plt.close(fig)


def format_ci(row: pd.Series, value: str, low: str, high: str) -> str:
    return f"{row[value]:.2f} [{row[low]:.2f}, {row[high]:.2f}]"


def write_report(outdir: Path, config: dict, numbers: dict) -> None:
    report = f"""# Study report: S16b - Independent pedestal estimator closure

- **Study ID:** S16b
- **Ticket:** {config["ticket"]}
- **Author (worker label):** {config["worker"]}
- **Date:** 2026-06-09
- **Depends on:** S00a, S16
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `s16b_config.json`

## 0. Question

Which early-sample baseline estimator is least biased by pre-trigger activity?

Atomic steps:
- Reproduce the selected B-stave pulse count from raw `h101/HRDv` ROOT before using derived quantities.
- Compare strong non-ML early-sample estimators in a leave-one-pretrigger-sample closure test.
- Train one run-split ML closure estimator on the same target and benchmark it with held-out bootstrap CIs.
- Audit leakage because the ML closure can look very strong when later pulse-shape samples predict an early contaminated sample.

## 1. Reproduction

Raw ROOT reproduction used `data/root/root/hrdb_run_NNNN.root`, physical B-stack channels B2/B4/B6/B8, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Expected | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| selected B-stave pulses | {config["expected_selected_pulses"]} | {numbers["selected_pulses"]} | {numbers["selected_pulses"] - config["expected_selected_pulses"]} | {'yes' if numbers["selected_pulses"] == config["expected_selected_pulses"] else 'no'} |

## 2. Traditional method

The independent target is one excluded pre-trigger sample from samples 0-3. Every traditional estimator sees only the other three early samples. The strongest conventional option is `train_calibrated_low2`: the mean of the two lowest visible early samples with a Huber calibration trained only on non-held-out runs using holdout index, stave, early-sample range, amplitude, and peak sample.

Held-out runs were fixed as 57 and 65. Traditional benchmark:

| Method | MAE [ADC] | Mean bias [ADC] | n |
|---|---:|---:|---:|
{numbers["traditional_rows"]}

Bias versus the visible pre-trigger activity proxy is in `fig_bias_by_pretrigger_activity.png`.

## 3. ML method

The ML method is a regularized ridge regressor predicting the excluded early sample. It uses the other early samples, full waveform samples except the excluded sample, stave, holdout index, provisional amplitude, and peak sample. The split is by run: runs 57 and 65 are never used in training or calibration; runs 56 and 64 are used only for final linear calibration.

Best CV setting: `{numbers["ml_best"]}` with non-held-out GroupKFold MAE `{numbers["ml_cv_mae"]:.2f} ADC`. The held-out ML MAE is `{numbers["ml_mae_ci"]} ADC`.

## 4. Head-to-head benchmark

All rows below use the same sampled held-out records and held-out bootstrap CIs.

| Method | Metric | Value +/- CI | Mean bias +/- CI |
|---|---|---:|---:|
{numbers["benchmark_rows"]}

Paired ML minus best-traditional MAE delta: `{numbers["paired_delta"]}` ADC. Verdict: {numbers["verdict"]}

## 5. Leakage audit

| Check | Result |
|---|---|
{numbers["leakage_rows"]}

The ML result is therefore treated as a closure predictor, not as an adopted pedestal estimator. Later waveform samples can encode the same pulse that contaminates the pre-trigger region; that is useful for diagnosing contamination but not an independent zero-signal pedestal measurement.

## 6. Threats to validity

- **No forced-trigger sample in this mirror:** this is a leave-one-early-sample closure, not a direct electronics pedestal truth test.
- **Target semantics:** a predicted early sample may include pre-trigger pulse activity; low MAE does not prove an unbiased pedestal.
- **Only two held-out runs:** the train/test split is by run, but bootstrap CIs are held-out record CIs and should be interpreted as conditional on these runs.
- **Estimator selection:** the non-ML candidates and ML grid are fixed in `s16b_config.json`.

## 7. Findings

{numbers["finding"]}

Recommended follow-up tickets:
- S16d: search DAQ metadata and raw mirrors for forced/random-trigger HRD pedestal events, then repeat S16b with no-pulse targets.
- S16e: add the S16b pre-trigger activity proxy to S02 timing residual fits to test whether early contamination explains timing tails.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/{config["ticket"]}__s16b_independent_pedestal_estimator_closure/run_s16b_analysis.py --config reports/{config["ticket"]}__s16b_independent_pedestal_estimator_closure/s16b_config.json
```

Output artifacts include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `heldout_benchmark.csv`, `leakage_checks.csv`, and diagnostic figures.
"""
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    outdir = args.config.resolve().parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    start = time.time()

    base = load_base_module(Path(config["base_s16_script"]).resolve())
    meta, waveforms, run_counts = base.load_selected(config)
    run_counts.to_csv(outdir / "run_counts.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        input_rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)

    reproduction = pd.DataFrame(
        [
            {
                "quantity": "selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(meta)),
                "delta": int(len(meta) - int(config["expected_selected_pulses"])),
                "pass": bool(len(meta) == int(config["expected_selected_pulses"])),
            }
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction.iloc[0]["pass"]):
        raise RuntimeError("raw ROOT selected-pulse reproduction failed")

    closure = build_closure_frame(meta, waveforms, config)
    calibrated_low2, cal_meta = fit_calibrated_low2(closure, config)
    closure = pd.concat([closure, calibrated_low2], ignore_index=True)
    closure_summary = summarize(closure, ["method"])
    closure_summary.to_csv(outdir / "all_run_estimator_summary.csv", index=False)

    ml_features = build_ml_features(meta, waveforms, config, rng)
    ml_cv, ml_pred, ml_meta = train_ml(ml_features, config, shuffled=False)
    ml_cv.to_csv(outdir / "ml_cv_scan.csv", index=False)
    shuffle_cv, shuffle_pred, shuffle_meta = train_ml(ml_features, config, shuffled=True, fixed_params=ml_meta["best"])
    shuffle_cv.to_csv(outdir / "ml_shuffled_target_cv_scan.csv", index=False)

    methods = ["mean3", "median3", "low2_mean3", "min3", "line3_predict", "train_calibrated_low2"]
    bench_frame = match_ml_to_closure(closure, ml_pred, methods)
    bench = add_cis(summarize(bench_frame, ["method"]), bench_frame, config, rng).sort_values("mae_adc").reset_index(drop=True)
    bench.to_csv(outdir / "heldout_benchmark.csv", index=False)

    by_run = summarize(bench_frame, ["method", "run"])
    by_run.to_csv(outdir / "heldout_by_run.csv", index=False)
    by_contam = summarize(bench_frame[bench_frame["method"].isin(methods)], ["method", "contamination_bin"])
    by_contam.to_csv(outdir / "bias_by_pretrigger_activity.csv", index=False)

    best_trad = bench[bench["method"].isin(methods)].sort_values("mae_adc").iloc[0]
    ml_row = bench[bench["method"] == "ml_ridge_calibrated"].iloc[0]
    paired_delta = paired_bootstrap_delta(bench_frame, "ml_ridge_calibrated", str(best_trad["method"]), rng, int(config["ml"]["bootstrap_replicates"]))

    shuffle_bench_frame = shuffle_pred.copy()
    shuffle_summary = summarize(shuffle_bench_frame, ["method"])
    shuffle_summary = add_cis(shuffle_summary, shuffle_bench_frame, config, rng)
    shuffle_summary.to_csv(outdir / "ml_shuffled_target_heldout.csv", index=False)
    shuffle_row = shuffle_summary.iloc[0]

    feature_cols = list(ml_meta["feature_columns"])
    forbidden_features = [f"w{int(row.holdout_sample):02d}_minus_seed" for row in ml_features[["holdout_sample"]].drop_duplicates().itertuples()]
    target_feature_absent = True
    forbidden_values = []
    for holdout in sorted(ml_features["holdout_sample"].unique()):
        col = f"w{int(holdout):02d}_minus_seed"
        if col in ml_features.columns:
            missing_fraction = float(ml_features.loc[ml_features["holdout_sample"] == holdout, col].isna().mean())
            forbidden_values.append(f"holdout {int(holdout)} {col} NaN fraction={missing_fraction:.3f}")
            target_feature_absent = target_feature_absent and missing_fraction == 1.0
        else:
            forbidden_values.append(f"holdout {int(holdout)} {col} column absent")
    train_runs = set(int(x) for x in ml_features[~ml_features["run"].isin(config["heldout_runs"])]["run"].unique())
    test_runs = set(int(x) for x in ml_features[ml_features["run"].isin(config["heldout_runs"])]["run"].unique())
    event_overlap = (
        ml_features[~ml_features["run"].isin(config["heldout_runs"])][["run", "eventno", "stave_idx", "holdout_sample"]]
        .merge(
            ml_features[ml_features["run"].isin(config["heldout_runs"])][["run", "eventno", "stave_idx", "holdout_sample"]],
            on=["run", "eventno", "stave_idx", "holdout_sample"],
            how="inner",
        )
    )
    leakage = pd.DataFrame(
        [
            {"check": "train/test runs disjoint", "pass": bool(train_runs.isdisjoint(test_runs)), "value": f"train={sorted(train_runs)} test={sorted(test_runs)}"},
            {"check": "excluded sample feature row-masked", "pass": bool(target_feature_absent), "value": "; ".join(forbidden_values)},
            {"check": "train/test event-key overlap", "pass": bool(len(event_overlap) == 0), "value": str(int(len(event_overlap)))},
            {"check": "shuffled-target ML held-out MAE larger than real ML", "pass": bool(float(shuffle_row["mae_adc"]) > float(ml_row["mae_adc"]) * 2.0), "value": f"shuffled={float(shuffle_row['mae_adc']):.2f} real={float(ml_row['mae_adc']):.2f}"},
        ]
    )
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)

    plot_outputs(outdir, bench_frame, by_contam, bench)

    traditional_rows = []
    for _, row in bench[bench["method"].isin(methods)].iterrows():
        traditional_rows.append(f"| {row['method']} | {row['mae_adc']:.2f} | {row['mean_bias_adc']:.2f} | {int(row['n'])} |")
    benchmark_rows = []
    for _, row in bench.iterrows():
        benchmark_rows.append(
            f"| {row['method']} | held-out excluded-sample MAE [ADC] | {format_ci(row, 'mae_adc', 'mae_ci_low_adc', 'mae_ci_high_adc')} | {format_ci(row, 'mean_bias_adc', 'mean_bias_ci_low_adc', 'mean_bias_ci_high_adc')} |"
        )
    leakage_rows = []
    for _, row in leakage.iterrows():
        leakage_rows.append(f"| {row['check']} | {'pass' if row['pass'] else 'fail'}: {row['value']} |")
    ml_wins = bool(paired_delta["delta_mae_ci_high_adc"] < 0.0 and leakage["pass"].all())
    unbiased_trad = bool(best_trad["mean_bias_ci_low_adc"] <= 0.0 <= best_trad["mean_bias_ci_high_adc"])
    if ml_wins:
        verdict = "ML has a statistically lower closure MAE than the best traditional estimator, but it is not adopted as a pedestal because its later-waveform features can predict pulse contamination."
    else:
        verdict = f"{best_trad['method']} remains the preferred non-ML estimator; ML is not accepted as a pedestal improvement under the leakage-aware win rule."
    finding = (
        f"The lowest-MAE traditional estimator is `{best_trad['method']}` with MAE {best_trad['mae_adc']:.2f} ADC "
        f"and mean bias {best_trad['mean_bias_adc']:.2f} ADC; its bias CI "
        f"{format_ci(best_trad, 'mean_bias_adc', 'mean_bias_ci_low_adc', 'mean_bias_ci_high_adc')} "
        f"{'includes' if unbiased_trad else 'does not include'} zero. "
        f"ML reaches MAE {ml_row['mae_adc']:.2f} ADC, but the result is interpreted only as a contamination closure diagnostic."
    )

    numbers = {
        "git_commit": git_commit(),
        "selected_pulses": int(len(meta)),
        "traditional_rows": "\n".join(traditional_rows),
        "benchmark_rows": "\n".join(benchmark_rows),
        "leakage_rows": "\n".join(leakage_rows),
        "ml_best": ml_meta["best"],
        "ml_cv_mae": float(ml_meta["best_cv_mae_adc"]),
        "ml_mae_ci": format_ci(ml_row, "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc"),
        "paired_delta": f"{paired_delta['delta_mae_adc']:.2f} [{paired_delta['delta_mae_ci_low_adc']:.2f}, {paired_delta['delta_mae_ci_high_adc']:.2f}]",
        "verdict": verdict,
        "finding": finding,
    }
    write_report(outdir, config, numbers)

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(len(meta) == int(config["expected_selected_pulses"])),
        "reproduction": {
            "quantity": "selected B-stave pulses",
            "expected": int(config["expected_selected_pulses"]),
            "reproduced": int(len(meta)),
        },
        "traditional": {
            "method": str(best_trad["method"]),
            "metric": "heldout_excluded_pretrigger_mae_adc",
            "value": float(best_trad["mae_adc"]),
            "ci": [float(best_trad["mae_ci_low_adc"]), float(best_trad["mae_ci_high_adc"])],
            "mean_bias_adc": float(best_trad["mean_bias_adc"]),
            "mean_bias_ci": [float(best_trad["mean_bias_ci_low_adc"]), float(best_trad["mean_bias_ci_high_adc"])],
        },
        "ml": {
            "method": "ml_ridge_calibrated",
            "metric": "heldout_excluded_pretrigger_mae_adc",
            "value": float(ml_row["mae_adc"]),
            "ci": [float(ml_row["mae_ci_low_adc"]), float(ml_row["mae_ci_high_adc"])],
            "mean_bias_adc": float(ml_row["mean_bias_adc"]),
            "mean_bias_ci": [float(ml_row["mean_bias_ci_low_adc"]), float(ml_row["mean_bias_ci_high_adc"])],
            "best_params": ml_meta["best"],
        },
        "ml_beats_baseline": bool(ml_wins),
        "falsification": {
            "paired_ml_minus_traditional_mae_adc": paired_delta,
            "leakage_checks_pass": bool(leakage["pass"].all()),
            "traditional_bias_ci_includes_zero": bool(unbiased_trad),
            "n_traditional_methods": int(len(methods)),
            "n_ml_grid_points": int(len(ml_cv)),
        },
        "input_sha256": sha256_file(outdir / "input_sha256.csv"),
        "git_commit": git_commit(),
        "next_tickets": [
            "S16d: forced/random-trigger HRD pedestal event search and closure",
            "S16e: pre-trigger activity proxy in timing residual tails",
        ],
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    output_hashes = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path)})
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": f"/home/billy/anaconda3/bin/python {outdir / 'run_s16b_analysis.py'} --config {args.config}",
        "config": str(args.config),
        "random_seed": int(config["ml"]["random_seed"]),
        "input_hashes": input_rows,
        "output_hashes": output_hashes,
        "base_s16_script": config["base_s16_script"],
        "elapsed_seconds": round(time.time() - start, 3),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
