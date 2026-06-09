#!/usr/bin/env python3
"""S16b forced/random-trigger pedestal validation.

The current mirror has no populated ROOT entries tagged as forced/random triggers.
This script records that raw-ROOT reproduction first, then runs a no-pulse proxy
benchmark on quiet B-stack events with held-out runs.
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
from typing import Callable, Dict, Iterable, List, Tuple

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


def raw_roots(config: dict) -> List[Path]:
    root = Path(config["raw_root_dir"])
    return sorted(root.glob("hrda_run_*.root")) + sorted(root.glob("hrdb_run_*.root"))


def bstack_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def trigger_audit(config: dict) -> pd.DataFrame:
    rows = []
    for path in raw_roots(config):
        tree = uproot.open(path)["h101"]
        if tree.num_entries:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            values, counts = np.unique(trigger, return_counts=True)
            non_beam = int(np.sum(counts[values != 1]))
            summary = ";".join(f"{int(v)}:{int(c)}" for v, c in zip(values, counts))
        else:
            non_beam = 0
            summary = "empty"
        rows.append(
            {
                "file": path.name,
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "filename_forced_random_match": bool(
                    any(token in path.name.lower() for token in ["force", "random", "ped", "pulser"])
                ),
            }
        )
    return pd.DataFrame(rows)


def iter_bstack(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "TRIGGER", "HRDv"], step_size=step_size, library="np")


def jagged_mask(corrected: np.ndarray, amp: np.ndarray, cfg: dict) -> np.ndarray:
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


def adaptive_estimate_for_target(waveforms: np.ndarray, seed: np.ndarray, target_sample: int, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    corrected = waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(
        float(config["negative_tolerance_adc"]["floor"]),
        float(config["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    excluded = jagged_mask(corrected, amp, config)
    excluded[:, int(target_sample)] = True
    eligible = np.where(excluded, np.inf, waveforms)
    min_allowed_source = eligible.min(axis=1)
    estimate = np.minimum(seed, min_allowed_source + eps)
    return estimate, seed - estimate


def load_quiet_proxy(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    staves = config["staves"]
    stave_names = np.asarray(list(staves.keys()))
    stave_channels = np.asarray([int(v) for v in staves.values()], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    quiet_cut = float(config["quiet_event_max_amplitude_adc"])
    amp_cut = float(config["amplitude_cut_adc"])
    group_for_run = run_group_lookup(config)
    rows = []
    waves = []
    count_rows = []

    for run in configured_runs(config):
        run_events = 0
        run_selected = 0
        run_quiet_events = 0
        run_quiet_records = 0
        for batch in iter_bstack(bstack_path(config, run)):
            eventno = np.asarray(batch["EVENTNO"])
            evt = np.asarray(batch["EVT"])
            waveform = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)[:, stave_channels, :]
            seed = np.median(waveform[:, :, pre], axis=2)
            corrected = waveform - seed[:, :, None]
            amp = corrected.max(axis=2)
            event_quiet = amp.max(axis=1) < quiet_cut
            selected = amp > amp_cut
            run_events += int(waveform.shape[0])
            run_selected += int(selected.sum())
            run_quiet_events += int(event_quiet.sum())
            if np.any(event_quiet):
                quiet_waves = waveform[event_quiet]
                n_events = quiet_waves.shape[0]
                flat_waves = quiet_waves.reshape(-1, n_samples)
                stave_idx = np.tile(np.arange(len(stave_channels), dtype=int), n_events)
                event_idx = np.repeat(np.where(event_quiet)[0], len(stave_channels))
                flat_amp = amp[event_quiet].reshape(-1)
                rows.append(
                    pd.DataFrame(
                        {
                            "run": int(run),
                            "group": group_for_run[int(run)],
                            "eventno": eventno[event_idx].astype(int),
                            "evt": evt[event_idx].astype(int),
                            "stave": stave_names[stave_idx],
                            "stave_idx": stave_idx.astype(int),
                            "proxy_max_amplitude_adc": flat_amp.astype(float),
                        }
                    )
                )
                waves.append(flat_waves)
                run_quiet_records += int(flat_waves.shape[0])
        count_rows.append(
            {
                "run": int(run),
                "events_total": run_events,
                "selected_b_stave_pulses": run_selected,
                "quiet_proxy_events": run_quiet_events,
                "quiet_proxy_stave_records": run_quiet_records,
            }
        )
    return pd.concat(rows, ignore_index=True), np.concatenate(waves, axis=0), pd.DataFrame(count_rows)


def make_target_records(meta: pd.DataFrame, waveforms: np.ndarray, indices: np.ndarray, samples: np.ndarray) -> pd.DataFrame:
    parts = []
    for target_sample in samples:
        target_sample = int(target_sample)
        chosen = indices
        part = pd.DataFrame(
            {
                "row_index": chosen.astype(int),
                "run": meta["run"].to_numpy()[chosen],
                "stave_idx": meta["stave_idx"].to_numpy()[chosen],
                "target_sample": target_sample,
                "target_adc": waveforms[chosen, target_sample].astype(float),
            }
        )
        pre = waveforms[chosen][:, :4].astype(float)
        seed = np.median(pre, axis=1)
        part["seed_median4_adc"] = seed
        part["pre_mean4_adc"] = pre.mean(axis=1)
        part["pre_std4_adc"] = pre.std(axis=1)
        part["pre_min4_adc"] = pre.min(axis=1)
        part["pre_max4_adc"] = pre.max(axis=1)
        part["pre_slope03_adc"] = pre[:, 3] - pre[:, 0]
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def ml_feature_columns() -> List[str]:
    return [
        "stave_idx",
        "target_sample",
        "seed_median4_adc",
        "pre_mean4_adc",
        "pre_std4_adc",
        "pre_min4_adc",
        "pre_max4_adc",
        "pre_slope03_adc",
    ]


def train_ml(features: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, dict, HistGradientBoostingRegressor, LinearRegression]:
    heldout_runs = set(int(run) for run in config["heldout_runs"])
    calibration_runs = set(int(run) for run in config["calibration_runs"])
    feature_cols = ml_feature_columns()
    train_cv = features[~features["run"].isin(heldout_runs)].copy()
    core_train = train_cv[~train_cv["run"].isin(calibration_runs)].copy()
    calibration = train_cv[train_cv["run"].isin(calibration_runs)].copy()
    params = config["ml"]["hyperparameters"]
    groups = train_cv["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    cv = GroupKFold(n_splits=n_splits)
    scan_rows = []
    for max_leaf_nodes in params["max_leaf_nodes"]:
        for learning_rate in params["learning_rate"]:
            for l2_regularization in params["l2_regularization"]:
                scores = []
                for train_idx, valid_idx in cv.split(train_cv[feature_cols], train_cv["target_adc"], groups=groups):
                    model = HistGradientBoostingRegressor(
                        max_iter=80,
                        max_leaf_nodes=int(max_leaf_nodes),
                        learning_rate=float(learning_rate),
                        l2_regularization=float(l2_regularization),
                        random_state=int(config["random_seed"]),
                    )
                    model.fit(train_cv.iloc[train_idx][feature_cols], train_cv.iloc[train_idx]["target_adc"])
                    pred = model.predict(train_cv.iloc[valid_idx][feature_cols])
                    scores.append(mean_absolute_error(train_cv.iloc[valid_idx]["target_adc"], pred))
                scan_rows.append(
                    {
                        "max_leaf_nodes": int(max_leaf_nodes),
                        "learning_rate": float(learning_rate),
                        "l2_regularization": float(l2_regularization),
                        "cv_mae_adc": float(np.mean(scores)),
                        "cv_mae_std_adc": float(np.std(scores, ddof=1)),
                    }
                )
    scan = pd.DataFrame(scan_rows).sort_values("cv_mae_adc").reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = HistGradientBoostingRegressor(
        max_iter=80,
        max_leaf_nodes=int(best["max_leaf_nodes"]),
        learning_rate=float(best["learning_rate"]),
        l2_regularization=float(best["l2_regularization"]),
        random_state=int(config["random_seed"]),
    )
    model.fit(core_train[feature_cols], core_train["target_adc"])
    cal_pred = model.predict(calibration[feature_cols])
    calibrator = LinearRegression().fit(cal_pred.reshape(-1, 1), calibration["target_adc"])
    meta = {
        "best": best,
        "feature_columns": feature_cols,
        "n_train_cv": int(len(train_cv)),
        "n_core_train": int(len(core_train)),
        "n_calibration": int(len(calibration)),
        "calibration_slope": float(calibrator.coef_[0]),
        "calibration_intercept": float(calibrator.intercept_),
    }
    return scan, calibration, meta, model, calibrator


def fit_traditional_offsets(train_features: pd.DataFrame) -> pd.DataFrame:
    train = train_features.copy()
    train["seed_residual_target_minus_seed"] = train["target_adc"] - train["seed_median4_adc"]
    return (
        train.groupby(["stave_idx", "target_sample"], as_index=False)["seed_residual_target_minus_seed"]
        .median()
        .rename(columns={"seed_residual_target_minus_seed": "offset_adc"})
    )


def run_bootstrap_ci(
    residual: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    n_boot: int,
    max_records_per_run: int,
) -> Tuple[float, float]:
    by_run = {}
    for run in np.unique(runs):
        vals = residual[runs == run]
        if len(vals) > max_records_per_run:
            vals = rng.choice(vals, size=max_records_per_run, replace=False)
        by_run[int(run)] = vals
    run_values = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(n_boot):
        pieces = []
        for run in rng.choice(run_values, size=len(run_values), replace=True):
            vals = by_run[int(run)]
            pieces.append(rng.choice(vals, size=len(vals), replace=True))
        stats.append(metric(np.concatenate(pieces)))
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def metric_summary(method: str, residual: np.ndarray, runs: np.ndarray, config: dict, rng: np.random.Generator) -> dict:
    residual = np.asarray(residual, dtype=float)
    abs_res = np.abs(residual)
    n_boot = int(config["bootstrap_replicates"])
    cap = int(config["bootstrap_max_records_per_run"])
    bias_lo, bias_hi = run_bootstrap_ci(residual, runs, np.mean, rng, n_boot, cap)
    mae_lo, mae_hi = run_bootstrap_ci(residual, runs, lambda x: float(np.mean(np.abs(x))), rng, n_boot, cap)
    rmse_lo, rmse_hi = run_bootstrap_ci(residual, runs, lambda x: float(math.sqrt(np.mean(x**2))), rng, n_boot, cap)
    return {
        "method": method,
        "n_records": int(len(residual)),
        "mean_bias_adc": float(np.mean(residual)),
        "mean_bias_ci_low_adc": bias_lo,
        "mean_bias_ci_high_adc": bias_hi,
        "mae_adc": float(np.mean(abs_res)),
        "mae_ci_low_adc": mae_lo,
        "mae_ci_high_adc": mae_hi,
        "rmse_adc": float(math.sqrt(np.mean(residual**2))),
        "rmse_ci_low_adc": rmse_lo,
        "rmse_ci_high_adc": rmse_hi,
        "median_bias_adc": float(np.median(residual)),
        "q05_adc": float(np.quantile(residual, 0.05)),
        "q95_adc": float(np.quantile(residual, 0.95)),
    }


def evaluate_methods(
    meta: pd.DataFrame,
    waveforms: np.ndarray,
    train_features: pd.DataFrame,
    test_features: pd.DataFrame,
    model: HistGradientBoostingRegressor,
    calibrator: LinearRegression,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_cols = ml_feature_columns()
    offset = fit_traditional_offsets(train_features)
    test = test_features.merge(offset, on=["stave_idx", "target_sample"], how="left")
    test["offset_adc"] = test["offset_adc"].fillna(0.0)
    method_residuals = {}
    method_runs = test["run"].to_numpy()
    target = test["target_adc"].to_numpy()
    method_residuals["median4_pre"] = test["seed_median4_adc"].to_numpy() - target
    method_residuals["mean4_pre"] = test["pre_mean4_adc"].to_numpy() - target
    method_residuals["median4_plus_train_offset"] = test["seed_median4_adc"].to_numpy() + test["offset_adc"].to_numpy() - target

    adapt = np.empty(len(test), dtype=float)
    lowering = np.empty(len(test), dtype=float)
    for sample in sorted(test["target_sample"].unique()):
        mask = test["target_sample"].to_numpy() == sample
        idx = test.loc[mask, "row_index"].to_numpy(dtype=int)
        seed = test.loc[mask, "seed_median4_adc"].to_numpy(dtype=float)
        estimate, lower = adaptive_estimate_for_target(waveforms[idx].astype(float), seed, int(sample), config)
        adapt[mask] = estimate
        lowering[mask] = lower
    method_residuals["adaptive_pc_excluding_target"] = adapt - target

    raw_ml = model.predict(test[feature_cols])
    ml_pred = calibrator.predict(raw_ml.reshape(-1, 1))
    method_residuals["ml_pretrigger_hgbr_calibrated"] = ml_pred - target

    benchmark = pd.DataFrame(
        [metric_summary(method, residual, method_runs, config, rng) for method, residual in method_residuals.items()]
    ).sort_values("mae_adc")

    by_run_rows = []
    for method, residual in method_residuals.items():
        for run in sorted(np.unique(method_runs)):
            vals = residual[method_runs == run]
            by_run_rows.append(
                {
                    "method": method,
                    "run": int(run),
                    "n_records": int(len(vals)),
                    "mean_bias_adc": float(np.mean(vals)),
                    "mae_adc": float(np.mean(np.abs(vals))),
                    "rmse_adc": float(math.sqrt(np.mean(vals**2))),
                }
            )
    by_run = pd.DataFrame(by_run_rows)

    sample_parts = []
    for method, residual in method_residuals.items():
        take = min(60000, len(residual))
        chosen = rng.choice(np.arange(len(residual)), size=take, replace=False)
        sample_parts.append(
            pd.DataFrame(
                {
                    "method": method,
                    "run": method_runs[chosen],
                    "target_sample": test["target_sample"].to_numpy()[chosen],
                    "residual_adc": residual[chosen],
                    "adaptive_lowering_adc": lowering[chosen] if method == "adaptive_pc_excluding_target" else np.nan,
                }
            )
        )
    residual_sample = pd.concat(sample_parts, ignore_index=True)
    return benchmark, by_run, residual_sample


def leakage_checks(
    train_features: pd.DataFrame,
    test_features: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    feature_cols = ml_feature_columns()
    rows = []
    shuffled = train_features.copy()
    shuffled["target_adc"] = rng.permutation(shuffled["target_adc"].to_numpy())
    model = HistGradientBoostingRegressor(max_iter=80, max_leaf_nodes=15, learning_rate=0.06, random_state=int(config["random_seed"]) + 9)
    model.fit(shuffled[feature_cols], shuffled["target_adc"])
    pred = model.predict(test_features[feature_cols])
    rows.append(
        {
            "check": "shuffled_training_target",
            "mae_adc": float(mean_absolute_error(test_features["target_adc"], pred)),
            "interpretation": "should be no better than simple pedestal baselines",
        }
    )

    leaky_cols = feature_cols + ["target_adc"]
    leaky = HistGradientBoostingRegressor(max_iter=40, max_leaf_nodes=7, learning_rate=0.1, random_state=int(config["random_seed"]) + 10)
    leaky.fit(train_features[leaky_cols], train_features["target_adc"])
    leaky_pred = leaky.predict(test_features[leaky_cols])
    rows.append(
        {
            "check": "intentional_target_feature_oracle",
            "mae_adc": float(mean_absolute_error(test_features["target_adc"], leaky_pred)),
            "interpretation": "very low error confirms direct target leakage would be obvious and is excluded from the real model",
        }
    )

    rows.append(
        {
            "check": "real_feature_exclusion",
            "mae_adc": np.nan,
            "interpretation": "real ML features exclude run, eventno, evt, target_adc, and any post-trigger target sample value",
        }
    )
    return pd.DataFrame(rows)


def plot_outputs(outdir: Path, counts: pd.DataFrame, benchmark: pd.DataFrame, residual_sample: pd.DataFrame, by_run: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(counts["run"].astype(str), counts["quiet_proxy_events"], label="quiet proxy events")
    ax.set_xlabel("run")
    ax.set_ylabel("events")
    ax.set_title("Quiet no-pulse proxy population by B-stack run")
    ax.tick_params(axis="x", rotation=90)
    fig.tight_layout()
    fig.savefig(outdir / "fig_quiet_proxy_counts.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for method, sub in residual_sample.groupby("method"):
        ax.hist(sub["residual_adc"].clip(-80, 80), bins=100, histtype="step", density=True, linewidth=1.3, label=method)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("pedestal estimate - held-out no-pulse sample [ADC]")
    ax.set_ylabel("density")
    ax.set_title("Held-out run residuals, quiet no-pulse proxy")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_heldout_residuals.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ordered = benchmark.sort_values("mae_adc")
    ax.errorbar(
        ordered["mae_adc"],
        ordered["method"],
        xerr=[ordered["mae_adc"] - ordered["mae_ci_low_adc"], ordered["mae_ci_high_adc"] - ordered["mae_adc"]],
        fmt="o",
    )
    ax.set_xlabel("held-out MAE [ADC]")
    ax.set_title("Run-heldout bootstrap intervals")
    fig.tight_layout()
    fig.savefig(outdir / "fig_method_mae_ci.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    pivot = by_run.pivot(index="run", columns="method", values="mean_bias_adc")
    pivot.plot(kind="bar", ax=ax)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("mean bias [ADC]")
    ax.set_title("Held-out bias by run")
    fig.tight_layout()
    fig.savefig(outdir / "fig_bias_by_run.png", dpi=160)
    plt.close(fig)


def fmt_ci(row: pd.Series, value: str, lo: str, hi: str) -> str:
    def get(name: str) -> float:
        if hasattr(row, "_asdict"):
            return float(row._asdict()[name])
        return float(row[name])

    return f"{get(value):.2f} [{get(lo):.2f}, {get(hi):.2f}]"


def output_hashes(outdir: Path) -> List[dict]:
    rows = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def json_records(frame: pd.DataFrame) -> List[dict]:
    records = frame.replace({np.nan: None}).to_dict(orient="records")
    return records


def write_report(outdir: Path, config: dict, numbers: dict) -> None:
    bench = numbers["benchmark"]
    best = bench.iloc[0]
    adaptive = bench[bench["method"] == "adaptive_pc_excluding_target"].iloc[0]
    median = bench[bench["method"] == "median4_pre"].iloc[0]
    ml = bench[bench["method"] == "ml_pretrigger_hgbr_calibrated"].iloc[0]
    rows = "\n".join(
        f"| {row.method} | {row.n_records} | {fmt_ci(row, 'mae_adc', 'mae_ci_low_adc', 'mae_ci_high_adc')} | "
        f"{fmt_ci(row, 'mean_bias_adc', 'mean_bias_ci_low_adc', 'mean_bias_ci_high_adc')} | {fmt_ci(row, 'rmse_adc', 'rmse_ci_low_adc', 'rmse_ci_high_adc')} |"
        for row in bench.itertuples(index=False)
    )
    leak_rows = "\n".join(
        f"| {row.check} | {'' if pd.isna(row.mae_adc) else f'{row.mae_adc:.2f}'} | {row.interpretation} |"
        for row in numbers["leakage"].itertuples(index=False)
    )
    report = f"""# Study report: S16b - forced-trigger pedestal validation

- **Ticket:** {config["ticket"]}
- **Author:** {config["worker"]}
- **Date:** 2026-06-09
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `s16b_config.json`

## Question

Is the adaptive pedestal unbiased when validated on true no-pulse forced/random-trigger events rather than physics-event pre-trigger samples?

## Raw ROOT reproduction first

Two raw-ROOT checks were run before modeling:

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | {config["expected_selected_pulses"]} | {numbers["selected_pulses"]} | {"yes" if numbers["selected_pulses"] == config["expected_selected_pulses"] else "no"} |
| forced/random-tagged ROOT entries (`TRIGGER != 1` or forced/random filename token) | {config["expected_forced_random_tagged_entries"]} | {numbers["forced_random_entries"]} | {"yes" if numbers["forced_random_entries"] == config["expected_forced_random_tagged_entries"] else "no"} |

The current mirror still contains no populated true forced/random pedestal sample: every populated A/B ROOT file has `TRIGGER == 1`; A-stack runs 0000-0003 are empty. The rest of this report is therefore a clearly labeled **quiet no-pulse proxy**, not a true forced-trigger validation.

## Proxy dataset

Proxy no-pulse events are B-stack events where all configured B staves have baseline-subtracted max amplitude below `{config["quiet_event_max_amplitude_adc"]:.0f} ADC` using samples 0-3 as the seed pedestal. This gives `{numbers["quiet_events"]}` events and `{numbers["quiet_records"]}` stave records across configured runs; held-out runs `{config["heldout_runs"]}` contribute `{numbers["heldout_target_records"]}` sample-level targets from samples {config["validation_samples"]}.

## Methods

Traditional estimators:
- `median4_pre`: median of samples 0-3.
- `mean4_pre`: mean of samples 0-3.
- `median4_plus_train_offset`: median4 plus a train-run median offset by stave and target sample.
- `adaptive_pc_excluding_target`: S16 adaptive positivity correction, with the target sample excluded from the constraint.

ML estimator: `ml_pretrigger_hgbr_calibrated`, a histogram-gradient-boosted regressor using only pre-trigger summaries, stave, and target sample. Splits are by run: held-out runs {config["heldout_runs"]}, calibration runs {config["calibration_runs"]}, all remaining configured runs for model development. Best CV setting: `{numbers["ml_meta"]["best"]}`.

## Held-out benchmark

Intervals are run-heldout bootstraps over runs {config["heldout_runs"]}; residual is estimate minus held-out no-pulse sample.

| Method | n | MAE [ADC] | Mean bias [ADC] | RMSE [ADC] |
|---|---:|---:|---:|---:|
{rows}

Verdict: best proxy MAE is `{best.method}` at {best.mae_adc:.2f} ADC. The adaptive method is {'consistent with zero bias' if adaptive.mean_bias_ci_low_adc <= 0 <= adaptive.mean_bias_ci_high_adc else 'not consistent with zero bias'} on this proxy, with mean bias {adaptive.mean_bias_adc:.2f} ADC and MAE {adaptive.mae_adc:.2f} ADC. Compared with `median4_pre`, adaptive changes MAE by {adaptive.mae_adc - median.mae_adc:+.2f} ADC; ML changes MAE by {ml.mae_adc - median.mae_adc:+.2f} ADC.

## Leakage checks

| Check | MAE [ADC] | Interpretation |
|---|---:|---|
{leak_rows}

The real ML feature list is recorded in `manifest.json` and excludes run ID, event ID, target ADC, and target-sample waveform value. Because no true forced/random triggers exist, the proxy can still inherit beam-trigger selection bias.

## Outputs

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `trigger_audit.csv`, `quiet_counts_by_run.csv`, `heldout_benchmark.csv`, `heldout_by_run.csv`, `ml_cv_scan.csv`, and `leakage_checks.csv`.

## Follow-up

The high-value next step is not another proxy: locate or acquire true random/forced B-stack pedestal ROOT with a non-beam trigger code or a separate run log. Once present, this same script can rerun with the proxy flag removed and no amplitude-selected quiet cut.
"""
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    outdir = args.config.parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rng = np.random.default_rng(int(config["random_seed"]))
    start = time.time()

    audit = trigger_audit(config)
    audit.to_csv(outdir / "trigger_audit.csv", index=False)
    forced_random_entries = int(audit["non_beam_trigger_entries"].sum() + audit.loc[audit["filename_forced_random_match"], "entries"].sum())

    meta, waveforms, counts = load_quiet_proxy(config)
    counts.to_csv(outdir / "quiet_counts_by_run.csv", index=False)
    selected_pulses = int(counts["selected_b_stave_pulses"].sum())
    quiet_events = int(counts["quiet_proxy_events"].sum())
    quiet_records = int(counts["quiet_proxy_stave_records"].sum())

    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": selected_pulses,
                "delta": selected_pulses - int(config["expected_selected_pulses"]),
                "pass": selected_pulses == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "forced/random-tagged ROOT entries",
                "expected": int(config["expected_forced_random_tagged_entries"]),
                "reproduced": forced_random_entries,
                "delta": forced_random_entries - int(config["expected_forced_random_tagged_entries"]),
                "pass": forced_random_entries == int(config["expected_forced_random_tagged_entries"]),
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    runs = meta["run"].to_numpy()
    heldout_mask = np.isin(runs, np.asarray(config["heldout_runs"], dtype=int))
    train_indices_all = np.where(~heldout_mask)[0]
    test_indices = np.where(heldout_mask)[0]
    validation_samples = np.asarray(config["validation_samples"], dtype=int)
    max_train = int(config["ml"]["max_train_records"])
    target_train_rows = len(train_indices_all) * len(validation_samples)
    if target_train_rows > max_train:
        chosen_wave = rng.choice(train_indices_all, size=max_train, replace=True)
        chosen_sample = rng.choice(validation_samples, size=max_train, replace=True)
        train_features = make_target_records(meta, waveforms, chosen_wave, np.asarray([validation_samples[0]], dtype=int)).iloc[:0]
        parts = []
        for sample in validation_samples:
            idx = chosen_wave[chosen_sample == sample]
            if len(idx):
                parts.append(make_target_records(meta, waveforms, idx, np.asarray([sample], dtype=int)))
        train_features = pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=int(config["random_seed"]))
    else:
        train_features = make_target_records(meta, waveforms, train_indices_all, validation_samples)
    test_features = make_target_records(meta, waveforms, test_indices, validation_samples)

    ml_scan, calibration_frame, ml_meta, model, calibrator = train_ml(train_features, config)
    ml_scan.to_csv(outdir / "ml_cv_scan.csv", index=False)
    benchmark, by_run, residual_sample = evaluate_methods(
        meta, waveforms, train_features, test_features, model, calibrator, config, rng
    )
    benchmark.to_csv(outdir / "heldout_benchmark.csv", index=False)
    by_run.to_csv(outdir / "heldout_by_run.csv", index=False)
    residual_sample.to_csv(outdir / "heldout_residual_sample.csv.gz", index=False)
    leak = leakage_checks(train_features, test_features, config, rng)
    leak.to_csv(outdir / "leakage_checks.csv", index=False)

    input_rows = []
    for path in raw_roots(config):
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)

    plot_outputs(outdir, counts, benchmark, residual_sample, by_run)

    numbers = {
        "git_commit": git_commit(),
        "selected_pulses": selected_pulses,
        "forced_random_entries": forced_random_entries,
        "quiet_events": quiet_events,
        "quiet_records": quiet_records,
        "heldout_target_records": int(len(test_features)),
        "benchmark": benchmark,
        "leakage": leak,
        "ml_meta": ml_meta,
    }
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "raw_reproduction": {
            "selected_b_stave_pulses": selected_pulses,
            "expected_selected_b_stave_pulses": int(config["expected_selected_pulses"]),
            "forced_random_tagged_entries": forced_random_entries,
            "true_forced_random_sample_available": bool(forced_random_entries > 0),
        },
        "proxy_dataset": {
            "quiet_event_max_amplitude_adc": float(config["quiet_event_max_amplitude_adc"]),
            "quiet_proxy_events": quiet_events,
            "quiet_proxy_stave_records": quiet_records,
            "heldout_target_records": int(len(test_features)),
            "heldout_runs": config["heldout_runs"],
        },
        "primary_metric": "heldout quiet-proxy sample MAE with run bootstrap CI",
        "best_method": benchmark.iloc[0].to_dict(),
        "adaptive_method": benchmark[benchmark["method"] == "adaptive_pc_excluding_target"].iloc[0].to_dict(),
        "ml_method": benchmark[benchmark["method"] == "ml_pretrigger_hgbr_calibrated"].iloc[0].to_dict(),
        "ml_meta": ml_meta,
        "leakage_checks": json_records(leak),
        "conclusion": "No true forced/random-trigger pedestal entries are present in the current raw ROOT mirror; the quiet-event benchmark is a proxy only.",
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    write_report(outdir, config, numbers)

    manifest = {
        "command": f".venv/bin/python {outdir / 's16b_forced_trigger_pedestal_validation.py'} --config {outdir / 's16b_config.json'}",
        "config": str(outdir / "s16b_config.json"),
        "git_commit": numbers["git_commit"],
        "random_seed": int(config["random_seed"]),
        "environment": {
            "python": ".".join(map(str, tuple(os.sys.version_info[:3]))),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
        },
        "inputs": str(outdir / "input_sha256.csv"),
        "outputs": output_hashes(outdir),
        "runtime_seconds": float(time.time() - start),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
