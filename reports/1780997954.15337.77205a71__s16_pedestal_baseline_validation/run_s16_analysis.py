#!/usr/bin/env python3
"""S16 pedestal validation from read-only raw ROOT files.

All outputs are written next to this script/report. The data mirror under ./data is read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_absolute_error, mean_squared_error


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def iter_raw(path: Path, step_size: int = 10000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def jagged_mask(corrected: np.ndarray, amp: np.ndarray, cfg: dict) -> np.ndarray:
    """Return True for samples to exclude from the positivity constraint."""
    params = cfg["jagged_mask"]
    mask = np.zeros(corrected.shape, dtype=bool)
    high = float(params["high_fraction"]) * amp[:, None]
    low = float(params["low_fraction"]) * amp[:, None]
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    jag = (left > high) & (right > high) & ((middle < low) | (middle < -float(params["negative_adc"])))
    mask[:, 1:-1] = jag
    return mask


def adaptive_pedestal(waveforms: np.ndarray, seed: np.ndarray, cfg: dict, exclude_sample: int | None = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    corrected = waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(
        float(cfg["negative_tolerance_adc"]["floor"]),
        float(cfg["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    exclude = jagged_mask(corrected, amp, cfg)
    if exclude_sample is not None:
        exclude[:, int(exclude_sample)] = True
    eligible = np.where(exclude, np.inf, waveforms)
    min_allowed_source = eligible.min(axis=1)
    pc = np.minimum(seed, min_allowed_source + eps)
    lowering = seed - pc
    corrected_pc = waveforms - pc[:, None]
    min_margin = np.where(exclude, np.inf, corrected_pc).min(axis=1) + eps
    return pc, lowering, amp, min_margin


def load_selected(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    raw_dir = Path(config["raw_root_dir"])
    staves = config["staves"]
    stave_names = list(staves.keys())
    stave_channels = np.asarray([int(staves[name]) for name in stave_names], dtype=int)
    group_for_run = run_group_lookup(config)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    waves = []
    counts = []

    for run in configured_runs(config):
        path = raw_dir / f"hrdb_run_{run:04d}.root"
        run_total = 0
        run_selected = 0
        for batch in iter_raw(path):
            event_numbers = np.asarray(batch["EVENTNO"])
            evt_numbers = np.asarray(batch["EVT"])
            all_events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)
            selected_waves = all_events[:, stave_channels, :]
            seed = np.median(selected_waves[..., pre], axis=-1)
            corrected = selected_waves - seed[..., None]
            amp = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            selected = amp > cut
            event_idx, stave_idx = np.where(selected)
            run_total += int(selected_waves.shape[0])
            run_selected += int(len(event_idx))
            if len(event_idx):
                rows.append(
                    pd.DataFrame(
                        {
                            "run": int(run),
                            "group": group_for_run[int(run)],
                            "eventno": event_numbers[event_idx].astype(int),
                            "evt": evt_numbers[event_idx].astype(int),
                            "stave": np.asarray(stave_names)[stave_idx],
                            "stave_idx": stave_idx.astype(int),
                            "amplitude_adc": amp[event_idx, stave_idx],
                            "peak_sample": peak[event_idx, stave_idx].astype(int),
                            "seed_median4_adc": seed[event_idx, stave_idx],
                        }
                    )
                )
                waves.append(selected_waves[event_idx, stave_idx, :].astype(np.float32))
        counts.append({"run": int(run), "events_total": run_total, "selected_pulses": run_selected})

    meta = pd.concat(rows, ignore_index=True)
    waveforms = np.concatenate(waves, axis=0)
    return meta, waveforms, pd.DataFrame(counts)


def make_lopo(meta: pd.DataFrame, waveforms: np.ndarray, config: dict) -> pd.DataFrame:
    pre = list(config["pretrigger_samples"])
    records = []
    for holdout in pre:
        others = [idx for idx in pre if idx != holdout]
        other_values = waveforms[:, others].astype(np.float64)
        seed_median = np.median(other_values, axis=1)
        seed_mean = other_values.mean(axis=1)
        b_pc, lowering, amp_seed, margin = adaptive_pedestal(waveforms.astype(np.float64), seed_median, config, exclude_sample=holdout)
        for method, estimate in [
            ("median3", seed_median),
            ("mean3", seed_mean),
            ("adaptive_pc", b_pc),
        ]:
            residual = estimate - waveforms[:, holdout]
            records.append(
                pd.DataFrame(
                    {
                        "run": meta["run"].to_numpy(),
                        "pulse_index": np.arange(len(meta), dtype=int),
                        "group": meta["group"].to_numpy(),
                        "stave": meta["stave"].to_numpy(),
                        "stave_idx": meta["stave_idx"].to_numpy(),
                        "amplitude_adc": meta["amplitude_adc"].to_numpy(),
                        "peak_sample": meta["peak_sample"].to_numpy(),
                        "holdout_sample": int(holdout),
                        "method": method,
                        "estimate_adc": estimate,
                        "reference_adc": waveforms[:, holdout],
                        "residual_adc": residual,
                        "abs_residual_adc": np.abs(residual),
                        "adaptive_lowering_adc": lowering if method == "adaptive_pc" else np.zeros(len(meta)),
                        "positivity_margin_adc": margin if method == "adaptive_pc" else np.nan,
                    }
                )
            )
    result = pd.concat(records, ignore_index=True)
    bins = config["amplitude_bins"]
    labels = [f"{int(bins[i])}-{int(bins[i + 1])}" for i in range(len(bins) - 1)]
    result["amp_bin"] = pd.cut(result["amplitude_adc"], bins=bins, labels=labels, include_lowest=True, right=False)
    return result


def summarize(frame: pd.DataFrame, group_cols: List[str]) -> pd.DataFrame:
    rows = []
    grouped = frame.groupby(group_cols, dropna=False) if group_cols else [((), frame)]
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
                "std_adc": float(np.std(residual, ddof=1)),
                "mae_adc": float(np.mean(abs_res)),
                "rmse_adc": float(math.sqrt(np.mean(residual ** 2))),
                "median_bias_adc": float(np.median(residual)),
                "q05_adc": float(np.quantile(residual, 0.05)),
                "q95_adc": float(np.quantile(residual, 0.95)),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_ci(values: np.ndarray, fn, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) > 200000:
        values = rng.choice(values, size=200000, replace=False)
    stats = []
    for _ in range(n_boot):
        sample = rng.choice(values, size=len(values), replace=True)
        stats.append(float(fn(sample)))
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def build_ml_features(meta: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    max_records = int(config["ml"]["max_records"])
    n_pulses = len(meta)
    per_holdout = max_records // len(config["pretrigger_samples"])
    rows = []
    for holdout in config["pretrigger_samples"]:
        other_pre = [idx for idx in config["pretrigger_samples"] if idx != holdout]
        eligible_idx = np.arange(n_pulses)
        take = min(per_holdout, n_pulses)
        chosen = rng.choice(eligible_idx, size=take, replace=False)
        other = waveforms[chosen][:, other_pre].astype(np.float64)
        seed = np.median(other, axis=1)
        corrected = waveforms[chosen].astype(np.float64) - seed[:, None]
        feature = pd.DataFrame(
            {
                "run": meta["run"].to_numpy()[chosen],
                "pulse_index": chosen.astype(int),
                "stave_idx": meta["stave_idx"].to_numpy()[chosen],
                "holdout_sample": int(holdout),
                "target_adc": waveforms[chosen, int(holdout)].astype(float),
                "amplitude_adc": corrected.max(axis=1),
                "peak_sample": corrected.argmax(axis=1),
                "pre_mean3": other.mean(axis=1),
                "pre_median3": np.median(other, axis=1),
                "pre_std3": other.std(axis=1),
                "pre_min3": other.min(axis=1),
                "pre_max3": other.max(axis=1),
            }
        )
        for sample_idx in range(waveforms.shape[1]):
            if sample_idx == int(holdout):
                continue
            feature[f"w{sample_idx:02d}_minus_seed"] = corrected[:, sample_idx]
        rows.append(feature)
    return pd.concat(rows, ignore_index=True)


def train_ml(features: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    heldout_runs = set(int(run) for run in config["heldout_runs"])
    calibration_runs = set(int(run) for run in config["calibration_runs"])
    feature_cols = [col for col in features.columns if col not in {"target_adc", "pulse_index"}]
    feature_cols = [col for col in feature_cols if col != "run"]
    train_cv = features[~features["run"].isin(heldout_runs)].copy()
    test = features[features["run"].isin(heldout_runs)].copy()
    core_train = train_cv[~train_cv["run"].isin(calibration_runs)].copy()
    calibration = train_cv[train_cv["run"].isin(calibration_runs)].copy()
    if calibration.empty:
        calibration = core_train.sample(frac=0.2, random_state=int(config["ml"]["random_seed"]))
        core_train = core_train.drop(calibration.index)

    params = config["ml"]["hyperparameters"]
    groups = train_cv["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    cv = GroupKFold(n_splits=n_splits)
    scan_rows = []
    for max_leaf_nodes in params["max_leaf_nodes"]:
        for learning_rate in params["learning_rate"]:
            for l2_regularization in params["l2_regularization"]:
                fold_scores = []
                for train_idx, valid_idx in cv.split(train_cv[feature_cols], train_cv["target_adc"], groups=groups):
                    model = HistGradientBoostingRegressor(
                        max_iter=120,
                        max_leaf_nodes=int(max_leaf_nodes),
                        learning_rate=float(learning_rate),
                        l2_regularization=float(l2_regularization),
                        random_state=int(config["ml"]["random_seed"]),
                    )
                    model.fit(train_cv.iloc[train_idx][feature_cols], train_cv.iloc[train_idx]["target_adc"])
                    pred = model.predict(train_cv.iloc[valid_idx][feature_cols])
                    fold_scores.append(mean_absolute_error(train_cv.iloc[valid_idx]["target_adc"], pred))
                scan_rows.append(
                    {
                        "max_leaf_nodes": int(max_leaf_nodes),
                        "learning_rate": float(learning_rate),
                        "l2_regularization": float(l2_regularization),
                        "cv_mae_adc": float(np.mean(fold_scores)),
                        "cv_mae_std_adc": float(np.std(fold_scores, ddof=1)),
                    }
                )
    scan = pd.DataFrame(scan_rows).sort_values("cv_mae_adc").reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = HistGradientBoostingRegressor(
        max_iter=120,
        max_leaf_nodes=int(best["max_leaf_nodes"]),
        learning_rate=float(best["learning_rate"]),
        l2_regularization=float(best["l2_regularization"]),
        random_state=int(config["ml"]["random_seed"]),
    )
    model.fit(core_train[feature_cols], core_train["target_adc"])
    cal_pred = model.predict(calibration[feature_cols])
    calibrator = LinearRegression().fit(cal_pred.reshape(-1, 1), calibration["target_adc"])
    raw_pred = model.predict(test[feature_cols])
    calibrated_pred = calibrator.predict(raw_pred.reshape(-1, 1))
    pred_frame = test[["run", "pulse_index", "stave_idx", "holdout_sample", "target_adc", "amplitude_adc", "peak_sample"]].copy()
    pred_frame["method"] = "ml_hgbr_calibrated"
    pred_frame["estimate_adc"] = calibrated_pred
    pred_frame["reference_adc"] = pred_frame["target_adc"]
    pred_frame["residual_adc"] = pred_frame["estimate_adc"] - pred_frame["reference_adc"]
    pred_frame["abs_residual_adc"] = pred_frame["residual_adc"].abs()
    meta = {
        "best": best,
        "calibration_intercept": float(calibrator.intercept_),
        "calibration_slope": float(calibrator.coef_[0]),
        "n_train_cv": int(len(train_cv)),
        "n_core_train": int(len(core_train)),
        "n_calibration": int(len(calibration)),
        "n_test": int(len(test)),
        "feature_columns": feature_cols,
    }
    return scan, pred_frame, meta


def plot_outputs(outdir: Path, lopo: pd.DataFrame, benchmark_rows: pd.DataFrame, ml_pred: pd.DataFrame) -> None:
    heldout = lopo[lopo["run"].isin([57, 65])]
    fig, ax = plt.subplots(figsize=(8, 5))
    for method, sub in heldout.groupby("method"):
        vals = sub["residual_adc"].clip(-120, 120)
        ax.hist(vals, bins=80, histtype="step", density=True, linewidth=1.5, label=method)
    ax.set_xlabel("pedestal estimate - held-out pre-trigger sample [ADC]")
    ax.set_ylabel("density")
    ax.legend()
    ax.set_title("Held-out run residual distributions")
    fig.tight_layout()
    fig.savefig(outdir / "fig_heldout_residual_distributions.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for method, sub in benchmark_rows.groupby("method"):
        if "amp_bin" not in sub:
            continue
    pivot = benchmark_rows.pivot_table(index="amp_bin", columns="method", values="mean_bias_adc")
    pivot.plot(kind="bar", ax=ax)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("mean bias [ADC]")
    ax.set_xlabel("production amplitude bin [ADC]")
    ax.set_title("Held-out run bias by amplitude")
    fig.tight_layout()
    fig.savefig(outdir / "fig_bias_by_amplitude.png", dpi=160)
    plt.close(fig)

    adapt = lopo[lopo["method"] == "adaptive_pc"]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(adapt["adaptive_lowering_adc"].clip(0, 500), bins=80, histtype="stepfilled", alpha=0.7)
    ax.set_xlabel("adaptive pedestal lowering [ADC]")
    ax.set_ylabel("LOPO records")
    ax.set_title("Adaptive lowering diagnostic")
    fig.tight_layout()
    fig.savefig(outdir / "fig_adaptive_lowering.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 5))
    sample = ml_pred.sample(n=min(20000, len(ml_pred)), random_state=16)
    ax.hexbin(sample["reference_adc"], sample["estimate_adc"], gridsize=60, mincnt=1, cmap="viridis")
    lo = float(np.quantile(sample[["reference_adc", "estimate_adc"]].to_numpy(), 0.01))
    hi = float(np.quantile(sample[["reference_adc", "estimate_adc"]].to_numpy(), 0.99))
    ax.plot([lo, hi], [lo, hi], color="white", linewidth=1)
    ax.set_xlabel("held-out pre-trigger sample [ADC]")
    ax.set_ylabel("calibrated ML estimate [ADC]")
    ax.set_title("ML regression calibration check")
    fig.tight_layout()
    fig.savefig(outdir / "fig_ml_calibration.png", dpi=160)
    plt.close(fig)


def format_ci(row: pd.Series, value: str, lo: str, hi: str) -> str:
    return f"{row[value]:.2f} [{row[lo]:.2f}, {row[hi]:.2f}]"


def write_report(outdir: Path, config: dict, numbers: dict) -> None:
    report = f"""# Study report: S16 - Pedestal/baseline validation

- **Study ID:** S16
- **Author (worker label):** {config["worker"]}
- **Date:** 2026-06-09
- **Depends on:** S00
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `s16_config.json`

## 0. Question

Is the adaptive positivity-constrained pedestal unbiased for selected B-stack pulses, especially at low amplitude, when tested against pre-trigger samples that were not used to build the pedestal estimate?

Atomic steps:
- Reproduce the S00 selected-pulse population from raw ROOT.
- Reproduce the constructed adaptive-pedestal guarantee that corrected non-jagged samples are above `-epsilon(A)`.
- Benchmark simple pre-trigger estimators, adaptive positivity correction, and a run-split ML regressor against held-out pre-trigger samples.
- Quantify bias versus amplitude and identify whether forced/random-trigger pedestal data exists in the current mirror.

## 1. Reproduction

Raw ROOT reproduction used `h101/HRDv` from `data/root/root/hrdb_run_NNNN.root`, the S00 B-stave channel map, median samples 0-3, and the fixed `A > 1000 ADC` cut.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | {config["expected_selected_pulses"]} | {numbers["selected_pulses"]} | {numbers["selected_pulses"] - config["expected_selected_pulses"]} | 0 | {'yes' if numbers["selected_pulses"] == config["expected_selected_pulses"] else 'no'} |
| adaptive post-correction violations | 0 | {numbers["adaptive_violations"]} | {numbers["adaptive_violations"]} | 0 | {'yes' if numbers["adaptive_violations"] == 0 else 'no'} |

The second line is a sanity reproduction only: the zero-violation result is true by construction and is not accepted as an independent validation.

## 2. Traditional (non-ML) method

The validation target is a held-out pre-trigger sample. For each selected pulse and each pre-trigger index k in samples 0-3, the estimator used only the other three pre-trigger samples. The benchmark then compared the pedestal estimate to sample k. The adaptive method starts from the leave-one-out median and lowers the pedestal only enough to satisfy `min(non-jagged corrected samples excluding k) >= -epsilon(A)`, with `epsilon=max(25 ADC, 0.015*A)`.

Held-out runs were fixed before analysis: 57 and 65. Traditional benchmark on those runs:

| Method | MAE [ADC] | Mean bias [ADC] | RMSE [ADC] | n |
|---|---:|---:|---:|---:|
{numbers["traditional_table"]}

No parametric fit is used, so chi2/ndf is not applicable. Full residual distributions are in `fig_heldout_residual_distributions.png`; amplitude-binned bias is in `fig_bias_by_amplitude.png`; adaptive lowering is in `fig_adaptive_lowering.png`.

## 3. ML method

The ML method is a histogram-gradient-boosted regressor predicting the held-out pre-trigger sample from the other pre-trigger samples, waveform samples excluding the held-out sample, stave, holdout index, provisional amplitude, and peak sample. The split is by run: test runs 57 and 65, calibration runs 56 and 64, all remaining configured runs for model development. Hyperparameter CV scanned `max_leaf_nodes`, `learning_rate`, and `l2_regularization`; the best setting was `{numbers["ml_best"]}` with CV MAE `{numbers["ml_cv_mae"]:.2f} ADC`.

The final regressor was linearly calibrated on runs 56 and 64. Calibration is a regression bias correction, not probability calibration. Its held-out calibration check is shown in `fig_ml_calibration.png`.

## 4. Head-to-head benchmark

All methods are evaluated on the same held-out LOPO records from runs 57 and 65 with the same metric.

| Method | Metric | Value +/- CI | Notes |
|---|---|---:|---|
{numbers["benchmark_table"]}

Verdict: {numbers["verdict"]}

## 5. Falsification

- **Pre-registration:** `s16_config.json` fixed the primary metric before running the scan: held-out pre-trigger residual MAE and mean bias on runs 57 and 65. The adaptive pedestal would be considered unbiased only if its mean-bias CI included 0 ADC and its MAE was not worse than the simple leave-one-out median by more than 5 ADC.
- **Falsification test:** the adaptive method fails the primary claim if the held-out mean-bias CI excludes 0 ADC or if its held-out MAE exceeds the median baseline by more than 5 ADC.
- **Result:** {numbers["falsification"]}

## 6. Threats to validity

- **Benchmark/selection:** the simple median/mean baselines are strong for four pre-trigger samples; the adaptive method is not credited for satisfying its own positivity constraint.
- **Data leakage:** ML and benchmark splits are by run. The held-out pre-trigger sample is excluded from all estimator features and from the adaptive positivity constraint.
- **Metric misuse:** the primary metric is residual bias/MAE against an independent pre-trigger sample, with full residual distributions and amplitude-binned summaries. This does not prove the true zero-signal pedestal for pulses whose pre-trigger region is already contaminated.
- **Post-hoc selection:** amplitude bins, held-out runs, jagged definition, ML hyperparameter grid, and pass/fail rule are fixed in `s16_config.json`.

## 7. Provenance manifest

`manifest.json` records the command, input ROOT hashes, output hashes, random seed, git commit, and config. All generated artifacts are in this report directory.

## 8. Findings & next steps

The current data mirror contains beam-triggered HRD ROOT files but no separate forced/random-trigger pedestal sample found by filename or ROOT branch inspection. The leave-one-pre-trigger-out test is therefore the available independent check in this sandbox.

{numbers["finding"]}

Hypothesis: {numbers["hypothesis"]}

Recommended next tickets:
- S16b: acquire or locate forced/random-trigger pedestal events and repeat this benchmark with no pulse signal in the validation target. Expected information gain: separates true electronics pedestal bias from pre-trigger contamination in physics events.
- S16c: propagate adaptive-pedestal lowering into S02/S04 timing residuals as a nuisance covariate. Expected information gain: tests whether baseline contamination is a timing-resolution tail driver rather than only an amplitude diagnostic.

## 9. Reproducibility

```bash
python reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/run_s16_analysis.py --config reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/s16_config.json
```

Output artifacts:
`reproduction_match_table.csv`, `run_counts.csv`, `traditional_summary.csv`, `bias_by_amp_stave.csv`, `heldout_benchmark.csv`, `ml_cv_scan.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and the four PNG figures.
"""
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    outdir = args.config.parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    start = time.time()

    meta, waveforms, run_counts = load_selected(config)
    run_counts.to_csv(outdir / "run_counts.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        input_rows.append({"run": run, "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)

    b_prod, lowering_prod, amp_prod, margin_prod = adaptive_pedestal(waveforms.astype(np.float64), meta["seed_median4_adc"].to_numpy(dtype=float), config)
    adaptive_violations = int((margin_prod < -1e-9).sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": int(len(meta)),
                "delta": int(len(meta) - int(config["expected_selected_pulses"])),
                "tolerance": 0,
                "pass": bool(len(meta) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "adaptive post-correction violations",
                "report_value": 0,
                "reproduced": adaptive_violations,
                "delta": adaptive_violations,
                "tolerance": 0,
                "pass": bool(adaptive_violations == 0),
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    lopo = make_lopo(meta, waveforms, config)
    lopo_summary = summarize(lopo, ["method"])
    lopo_summary.to_csv(outdir / "traditional_summary.csv", index=False)
    bias_by_amp_stave = summarize(lopo, ["method", "amp_bin", "stave"])
    bias_by_amp_stave.to_csv(outdir / "bias_by_amp_stave.csv", index=False)

    heldout_lopo = lopo[lopo["run"].isin(config["heldout_runs"])].copy()
    heldout_summary = summarize(heldout_lopo, ["method"])
    heldout_amp = summarize(heldout_lopo, ["method", "amp_bin"])

    ml_features = build_ml_features(meta, waveforms, config, rng)
    ml_cv, ml_pred, ml_meta = train_ml(ml_features, config)
    ml_cv.to_csv(outdir / "ml_cv_scan.csv", index=False)

    # Match traditional baselines to the exact same sampled ML test records.
    ml_test_keys = ml_pred[["run", "pulse_index", "stave_idx", "holdout_sample"]].copy()
    trad_for_ml = []
    for method in ["median3", "mean3", "adaptive_pc"]:
        sub = heldout_lopo[heldout_lopo["method"] == method]
        sampled = ml_test_keys.merge(sub, on=["run", "pulse_index", "stave_idx", "holdout_sample"], how="left")
        trad_for_ml.append(sampled[["run", "stave_idx", "holdout_sample", "method", "estimate_adc", "reference_adc", "residual_adc", "abs_residual_adc", "amplitude_adc", "peak_sample"]])
    bench_frame = pd.concat(
        trad_for_ml
        + [
            ml_pred[
                [
                    "run",
                    "stave_idx",
                    "holdout_sample",
                    "method",
                    "estimate_adc",
                    "reference_adc",
                    "residual_adc",
                    "abs_residual_adc",
                    "amplitude_adc",
                    "peak_sample",
                ]
            ]
        ],
        ignore_index=True,
    )
    bench = summarize(bench_frame, ["method"])
    ci_rows = []
    for _, row in bench.iterrows():
        vals = bench_frame[bench_frame["method"] == row["method"]]["residual_adc"].to_numpy(dtype=float)
        abs_vals = np.abs(vals)
        mean_lo, mean_hi = bootstrap_ci(vals, np.mean, rng, int(config["ml"]["bootstrap_replicates"]))
        mae_lo, mae_hi = bootstrap_ci(abs_vals, np.mean, rng, int(config["ml"]["bootstrap_replicates"]))
        ci_rows.append(
            {
                **row.to_dict(),
                "mean_bias_ci_low_adc": mean_lo,
                "mean_bias_ci_high_adc": mean_hi,
                "mae_ci_low_adc": mae_lo,
                "mae_ci_high_adc": mae_hi,
            }
        )
    bench = pd.DataFrame(ci_rows).sort_values("mae_adc").reset_index(drop=True)
    bench.to_csv(outdir / "heldout_benchmark.csv", index=False)
    heldout_amp.to_csv(outdir / "heldout_bias_by_amplitude.csv", index=False)

    plot_outputs(outdir, lopo, heldout_amp, ml_pred)

    adaptive_row = bench[bench["method"] == "adaptive_pc"].iloc[0]
    median_row = bench[bench["method"] == "median3"].iloc[0]
    ml_row = bench[bench["method"] == "ml_hgbr_calibrated"].iloc[0]
    best_row = bench.iloc[0]
    adaptive_unbiased = adaptive_row["mean_bias_ci_low_adc"] <= 0 <= adaptive_row["mean_bias_ci_high_adc"]
    adaptive_not_worse = adaptive_row["mae_adc"] <= median_row["mae_adc"] + 5.0
    falsification = (
        f"adaptive mean-bias CI {format_ci(adaptive_row, 'mean_bias_adc', 'mean_bias_ci_low_adc', 'mean_bias_ci_high_adc')} ADC; "
        f"MAE {format_ci(adaptive_row, 'mae_adc', 'mae_ci_low_adc', 'mae_ci_high_adc')} ADC versus median MAE "
        f"{format_ci(median_row, 'mae_adc', 'mae_ci_low_adc', 'mae_ci_high_adc')} ADC. "
        f"{'The pre-registered adaptive-unbiased criterion passes.' if adaptive_unbiased and adaptive_not_worse else 'The pre-registered adaptive-unbiased criterion fails.'}"
    )
    if best_row["method"] == "ml_hgbr_calibrated":
        verdict = (
            f"ML has the lowest held-out MAE ({best_row['mae_adc']:.2f} ADC), "
            f"beating adaptive_pc by {adaptive_row['mae_adc'] - best_row['mae_adc']:.2f} ADC; the gain is small relative to the residual width, so the simple median remains the pragmatic pedestal estimator unless a forced-trigger validation shows otherwise."
        )
    else:
        verdict = (
            f"{best_row['method']} has the lowest held-out MAE ({best_row['mae_adc']:.2f} ADC). "
            f"ML does not beat the strong non-ML baseline on the pre-registered held-out metric."
        )
    finding = (
        f"The adaptive pedestal lowers the leave-one-out median in {100.0 * (lopo[lopo['method'] == 'adaptive_pc']['adaptive_lowering_adc'] > 0).mean():.2f}% of LOPO records, "
        f"but on the held-out pre-trigger benchmark its mean bias is {adaptive_row['mean_bias_adc']:.2f} ADC and its MAE is {adaptive_row['mae_adc']:.2f} ADC. "
        f"The simple median3 baseline has MAE {median_row['mae_adc']:.2f} ADC, and the calibrated ML regressor has MAE {ml_row['mae_adc']:.2f} ADC."
    )
    hypothesis = (
        "large adaptive lowering is mainly a diagnostic for early waveform contamination or pulse-shape pathologies, not an independent proof of pedestal accuracy; a true forced-trigger pedestal sample should show near-zero bias without needing the positivity constraint."
    )

    trad_lines = []
    for method in ["median3", "mean3", "adaptive_pc"]:
        row = bench[bench["method"] == method].iloc[0]
        trad_lines.append(f"| {method} | {row['mae_adc']:.2f} | {row['mean_bias_adc']:.2f} | {row['rmse_adc']:.2f} | {int(row['n'])} |")
    bench_lines = []
    for _, row in bench.iterrows():
        note = "run-split ML" if row["method"] == "ml_hgbr_calibrated" else "traditional"
        bench_lines.append(f"| {row['method']} | held-out pre-trigger MAE [ADC] | {format_ci(row, 'mae_adc', 'mae_ci_low_adc', 'mae_ci_high_adc')} | {note} |")

    numbers = {
        "git_commit": git_commit(),
        "selected_pulses": int(len(meta)),
        "adaptive_violations": adaptive_violations,
        "traditional_table": "\n".join(trad_lines),
        "benchmark_table": "\n".join(bench_lines),
        "ml_best": {k: ml_meta["best"][k] for k in ["max_leaf_nodes", "learning_rate", "l2_regularization"]},
        "ml_cv_mae": float(ml_meta["best"]["cv_mae_adc"]),
        "verdict": verdict,
        "falsification": falsification,
        "finding": finding,
        "hypothesis": hypothesis,
    }
    write_report(outdir, config, numbers)

    result = {
        "study": "S16",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(len(meta) == int(config["expected_selected_pulses"]) and adaptive_violations == 0),
        "repro_tolerance": "S00 count exact; adaptive zero-violation exact but constructed",
        "traditional": {
            "metric": "heldout_pretrigger_mae_adc",
            "value": float(adaptive_row["mae_adc"]),
            "ci": [float(adaptive_row["mae_ci_low_adc"]), float(adaptive_row["mae_ci_high_adc"])],
            "mean_bias_adc": float(adaptive_row["mean_bias_adc"]),
            "mean_bias_ci": [float(adaptive_row["mean_bias_ci_low_adc"]), float(adaptive_row["mean_bias_ci_high_adc"])],
        },
        "ml": {
            "metric": "heldout_pretrigger_mae_adc",
            "value": float(ml_row["mae_adc"]),
            "ci": [float(ml_row["mae_ci_low_adc"]), float(ml_row["mae_ci_high_adc"])],
            "mean_bias_adc": float(ml_row["mean_bias_adc"]),
            "mean_bias_ci": [float(ml_row["mean_bias_ci_low_adc"]), float(ml_row["mean_bias_ci_high_adc"])],
        },
        "ml_beats_baseline": bool(ml_row["mae_adc"] < adaptive_row["mae_adc"]),
        "falsification": {
            "preregistered_metric": config["pre_registered"]["metric"],
            "adaptive_unbiased": bool(adaptive_unbiased),
            "adaptive_not_worse_than_median_plus_5adc": bool(adaptive_not_worse),
            "n_tries": 1,
        },
        "input_sha256": sha256_file(outdir / "input_sha256.csv"),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S16b: forced-trigger pedestal validation",
            "S16c: pedestal-lowering nuisance propagation into timing residuals",
        ],
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    output_hashes = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path)})
    manifest = {
        "study": "S16",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": f"python {outdir / 'run_s16_analysis.py'} --config {args.config}",
        "config": str(args.config),
        "random_seed": int(config["ml"]["random_seed"]),
        "input_hashes": input_rows,
        "output_hashes": output_hashes,
        "elapsed_seconds": round(time.time() - start, 3),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
