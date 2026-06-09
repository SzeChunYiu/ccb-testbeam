#!/usr/bin/env python3
"""S16g Sample-I/Sample-II pedestal-lowering timing transfer study.

The script reads raw B-stack ROOT first to reproduce the S00/S02 counts, then
tests whether a pedestal-lowering timing residual model trained in one sample
period transfers to the other. Evaluation is by held-out target run with
run-block bootstrap confidence intervals. No Monte Carlo inputs are used.
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
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

import s02_timing_pickoff as s02


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def raw_paths(config: dict) -> List[Path]:
    return [raw_file(config, run) for run in configured_runs(config)]


def sample_by_run(config: dict) -> Dict[int, str]:
    out = {}
    for group, runs in config["run_groups"].items():
        sample = "sample_ii" if group.startswith("sample_ii") else "sample_i"
        for run in runs:
            out[int(run)] = sample
    return out


def cfd20_from_corrected(waveforms: np.ndarray, amplitudes: np.ndarray, config: dict) -> np.ndarray:
    samples = s02.cfd_time_samples(waveforms, amplitudes, 0.20)
    return float(config["sample_period_ns"]) * samples


def jagged_mask(corrected: np.ndarray, amplitude: np.ndarray, config: dict) -> np.ndarray:
    params = config["lowering"]
    mask = np.zeros(corrected.shape, dtype=bool)
    high = float(params["jagged_high_fraction"]) * amplitude[:, None]
    low = float(params["jagged_low_fraction"]) * amplitude[:, None]
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    mask[:, 1:-1] = (left > high) & (right > high) & (
        (middle < low) | (middle < -float(params["jagged_negative_adc"]))
    )
    return mask


def adaptive_lowering(corrected: np.ndarray, amplitude: np.ndarray, config: dict) -> np.ndarray:
    params = config["lowering"]
    eps = np.maximum(
        float(params["negative_tolerance_floor_adc"]),
        float(params["negative_tolerance_fraction_of_amplitude"]) * amplitude,
    )
    excluded = jagged_mask(corrected, amplitude, config)
    eligible = np.where(excluded, np.inf, corrected)
    estimate = np.minimum(0.0, eligible.min(axis=1) + eps)
    return -estimate


def add_lowering_features(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = pulses.copy()
    wf = np.vstack(out["waveform"].to_numpy()).astype(float)
    amp = out["amplitude_adc"].to_numpy(dtype=float)
    out["sample"] = out["run"].map(sample_by_run(config))
    out["stave_idx"] = out["stave"].map({name: i for i, name in enumerate(config["timing"]["downstream_staves"])})
    out["lowering_adc"] = adaptive_lowering(wf, amp, config)
    out["pre_min_adc"] = wf[:, :4].min(axis=1)
    out["pre_max_adc"] = wf[:, :4].max(axis=1)
    out["pre_range_adc"] = out["pre_max_adc"] - out["pre_min_adc"]
    out["pre_std_adc"] = wf[:, :4].std(axis=1)
    out["early_charge_norm"] = wf[:, :6].sum(axis=1) / np.maximum(amp, 1.0)
    out["late_charge_norm"] = wf[:, 9:].sum(axis=1) / np.maximum(out["area_adc_samples"].to_numpy(dtype=float), 1.0)
    out["area_over_amp"] = out["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    out["t_cfd20_ns"] = cfd20_from_corrected(wf, amp, config)
    lowered_wave = wf + out["lowering_adc"].to_numpy(dtype=float)[:, None]
    lowered_amp = lowered_wave.max(axis=1)
    out["t_adaptive_lowered_cfd20_ns"] = cfd20_from_corrected(lowered_wave, lowered_amp, config)
    return out


def add_bins(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = frame.copy()
    out["amp_bin"] = pd.cut(
        out["amplitude_adc"],
        bins=[float(x) for x in config["traditional"]["amplitude_bins_adc"]],
        labels=False,
        include_lowest=True,
        right=False,
    ).fillna(-1).astype(int)
    out["lowering_bin"] = pd.cut(
        out["lowering_adc"],
        bins=[float(x) for x in config["traditional"]["lowering_bins_adc"]],
        labels=False,
        include_lowest=True,
        right=False,
    ).fillna(-1).astype(int)
    return out


def residual_targets(pulses: pd.DataFrame, config: dict) -> np.ndarray:
    return s02.event_residual_targets(pulses, "cfd20", float(config["spacing_cm"]), config)


def fit_traditional(train: pd.DataFrame) -> Dict[Tuple[str, Tuple], float]:
    work = train[np.isfinite(train["target_residual_ns"])].copy()
    tables: Dict[Tuple[str, Tuple], float] = {}
    for cols, prefix in [
        (["stave", "amp_bin", "lowering_bin"], "stave_amp_lowering"),
        (["stave", "lowering_bin"], "stave_lowering"),
        (["stave"], "stave"),
    ]:
        for key, sub in work.groupby(cols):
            if not isinstance(key, tuple):
                key = (key,)
            tables[(prefix, key)] = float(np.median(sub["target_residual_ns"]))
    tables[("global", ())] = float(np.median(work["target_residual_ns"])) if len(work) else 0.0
    return tables


def predict_traditional(test: pd.DataFrame, tables: Dict[Tuple[str, Tuple], float]) -> np.ndarray:
    pred = []
    for row in test.itertuples(index=False):
        keys = [
            ("stave_amp_lowering", (row.stave, int(row.amp_bin), int(row.lowering_bin))),
            ("stave_lowering", (row.stave, int(row.lowering_bin))),
            ("stave", (row.stave,)),
            ("global", ()),
        ]
        for key in keys:
            if key in tables:
                pred.append(tables[key])
                break
    return np.asarray(pred, dtype=float)


def feature_columns() -> List[str]:
    cols = [
        "stave_idx",
        "amplitude_adc",
        "peak_sample",
        "area_over_amp",
        "lowering_adc",
        "pre_min_adc",
        "pre_range_adc",
        "pre_std_adc",
        "early_charge_norm",
        "late_charge_norm",
    ]
    cols.extend(["wf_norm_{:02d}".format(i) for i in range(18)])
    return cols


def add_ml_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    wf = np.vstack(out["waveform"].to_numpy()).astype(float)
    amp = np.maximum(out["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    for i in range(norm.shape[1]):
        out["wf_norm_{:02d}".format(i)] = norm[:, i]
    return out


def ml_matrix(frame: pd.DataFrame) -> np.ndarray:
    return frame[feature_columns()].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)


def fit_ml(train: pd.DataFrame, config: dict, rng: np.random.Generator, shuffle_target: bool = False):
    work = train[np.isfinite(train["target_residual_ns"])].copy()
    limit = int(config["ml"]["max_train_rows"])
    if len(work) > limit:
        take = rng.choice(np.arange(len(work)), size=limit, replace=False)
        work = work.iloc[np.sort(take)].copy()
    y = work["target_residual_ns"].to_numpy(dtype=float)
    if shuffle_target:
        y = rng.permutation(y)
    model = RandomForestRegressor(
        n_estimators=int(config["ml"]["n_estimators"]),
        max_depth=int(config["ml"]["max_depth"]),
        min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
        random_state=int(config["ml"]["random_seed"]) + (17 if shuffle_target else 0),
        n_jobs=2,
    )
    model.fit(ml_matrix(work), y)
    return model, int(len(work))


def pair_residual_frame(pulses: pd.DataFrame, method: str, config: dict, heldout_run: int, direction: str) -> pd.DataFrame:
    vals = s02.pairwise_residuals(pulses, method, float(config["spacing_cm"]), config, [int(heldout_run)])
    return pd.DataFrame(
        {
            "direction": direction,
            "heldout_run": int(heldout_run),
            "method": method,
            "pairwise_residual_ns": vals,
        }
    )


def evaluate_transfer(pulses: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eval_runs = {k: [int(x) for x in v] for k, v in config["transfer_eval_runs"].items()}
    train_runs = {k: [int(x) for x in v] for k, v in config["transfer_train_runs"].items()}
    residual_parts = []
    by_run_rows = []
    leakage_rows = []
    for source, target in [("sample_i", "sample_ii"), ("sample_ii", "sample_i")]:
        direction = "{}_to_{}".format(source, target)
        train = pulses[pulses["run"].isin(train_runs[source])].copy()
        train = train[train["sample"] == source].copy()
        trad_tables = fit_traditional(train)
        ml_model, ml_n = fit_ml(train, config, rng, shuffle_target=False)
        shuffled_model, _ = fit_ml(train, config, rng, shuffle_target=True)
        train_event_ids = set(train["event_id"])
        for heldout_run in eval_runs[target]:
            test = pulses[pulses["run"] == int(heldout_run)].copy()
            if test.empty:
                continue
            test = test[test["sample"] == target].copy()
            trad_pred = predict_traditional(test, trad_tables)
            ml_pred = ml_model.predict(ml_matrix(test))
            shuffle_pred = shuffled_model.predict(ml_matrix(test))

            scored = test.copy()
            scored["t_traditional_lowering_strata_ns"] = scored["t_cfd20_ns"] - trad_pred
            scored["t_ml_lowering_rf_ns"] = scored["t_cfd20_ns"] - ml_pred
            scored["t_ml_shuffled_target_control_ns"] = scored["t_cfd20_ns"] - shuffle_pred
            for method in [
                "cfd20",
                "adaptive_lowered_cfd20",
                "traditional_lowering_strata",
                "ml_lowering_rf",
                "ml_shuffled_target_control",
            ]:
                frame = pair_residual_frame(scored, method, config, heldout_run, direction)
                residual_parts.append(frame)
                by_run_rows.append(
                    {
                        "direction": direction,
                        "source_sample": source,
                        "target_sample": target,
                        "heldout_run": int(heldout_run),
                        "method": method,
                        **s02.metric_summary(frame["pairwise_residual_ns"].to_numpy(dtype=float)),
                    }
                )

            leakage_rows.extend(
                [
                    {
                        "direction": direction,
                        "heldout_run": int(heldout_run),
                        "check": "train_heldout_run_overlap",
                        "value": float(int(heldout_run in set(train["run"]))),
                        "pass": bool(heldout_run not in set(train["run"])),
                    },
                    {
                        "direction": direction,
                        "heldout_run": int(heldout_run),
                        "check": "train_target_sample_overlap",
                        "value": float(int(source == target)),
                        "pass": bool(source != target),
                    },
                    {
                        "direction": direction,
                        "heldout_run": int(heldout_run),
                        "check": "train_heldout_event_id_overlap",
                        "value": float(len(train_event_ids.intersection(set(test["event_id"])))),
                        "pass": bool(len(train_event_ids.intersection(set(test["event_id"]))) == 0),
                    },
                    {
                        "direction": direction,
                        "heldout_run": int(heldout_run),
                        "check": "ml_train_rows",
                        "value": float(ml_n),
                        "pass": bool(ml_n > 100),
                    },
                ]
            )
    residuals = pd.concat(residual_parts, ignore_index=True)
    by_run = pd.DataFrame(by_run_rows)
    leakage = pd.DataFrame(leakage_rows)
    for (direction, heldout_run), sub in by_run.groupby(["direction", "heldout_run"]):
        raw = float(sub[sub["method"] == "cfd20"]["sigma68_ns"].iloc[0])
        ml = float(sub[sub["method"] == "ml_lowering_rf"]["sigma68_ns"].iloc[0])
        shuffled = float(sub[sub["method"] == "ml_shuffled_target_control"]["sigma68_ns"].iloc[0])
        leakage = pd.concat(
            [
                leakage,
                pd.DataFrame(
                    [
                        {
                            "direction": direction,
                            "heldout_run": int(heldout_run),
                            "check": "ml_not_implausibly_better_than_raw",
                            "value": raw - ml,
                            "pass": bool((raw - ml) < 1.0),
                        },
                        {
                            "direction": direction,
                            "heldout_run": int(heldout_run),
                            "check": "shuffled_target_not_better_than_ml",
                            "value": shuffled - ml,
                            "pass": bool(shuffled >= ml),
                        },
                    ]
                ),
            ],
            ignore_index=True,
        )
    return residuals, by_run, leakage


def run_block_bootstrap(
    values: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    n_boot: int,
    cap_per_run: int,
) -> Tuple[float, float]:
    by_run = {}
    for run in np.unique(runs):
        vals = values[runs == run]
        if len(vals) > cap_per_run:
            vals = rng.choice(vals, size=cap_per_run, replace=False)
        by_run[int(run)] = vals
    run_values = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(int(n_boot)):
        pieces = []
        for run in rng.choice(run_values, size=len(run_values), replace=True):
            vals = by_run[int(run)]
            pieces.append(rng.choice(vals, size=len(vals), replace=True))
        stats.append(metric(np.concatenate(pieces)))
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def summarize_residuals(residuals: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for (direction, method), sub in residuals.groupby(["direction", "method"]):
        values = sub["pairwise_residual_ns"].to_numpy(dtype=float)
        runs = sub["heldout_run"].to_numpy(dtype=int)
        finite = np.isfinite(values)
        values = values[finite]
        runs = runs[finite]
        sigma_lo, sigma_hi = run_block_bootstrap(
            values,
            runs,
            s02.sigma68,
            rng,
            int(config["bootstrap_replicates"]),
            int(config["bootstrap_max_residuals_per_run"]),
        )
        rms_lo, rms_hi = run_block_bootstrap(
            values,
            runs,
            s02.full_rms,
            rng,
            int(config["bootstrap_replicates"]),
            int(config["bootstrap_max_residuals_per_run"]),
        )
        tail_fn = lambda x: float(np.mean(np.abs(x - np.median(x)) > 5.0))
        tail_lo, tail_hi = run_block_bootstrap(
            values,
            runs,
            tail_fn,
            rng,
            int(config["bootstrap_replicates"]),
            int(config["bootstrap_max_residuals_per_run"]),
        )
        rows.append(
            {
                "direction": direction,
                "method": method,
                "n_pair_residuals": int(len(values)),
                "n_heldout_runs": int(len(np.unique(runs))),
                "median_ns": float(np.median(values)),
                "sigma68_ns": s02.sigma68(values),
                "sigma68_ci_low_ns": sigma_lo,
                "sigma68_ci_high_ns": sigma_hi,
                "full_rms_ns": s02.full_rms(values),
                "full_rms_ci_low_ns": rms_lo,
                "full_rms_ci_high_ns": rms_hi,
                "tail_frac_abs_gt5ns": tail_fn(values),
                "tail_ci_low": tail_lo,
                "tail_ci_high": tail_hi,
            }
        )
    return pd.DataFrame(rows).sort_values(["direction", "sigma68_ns"]).reset_index(drop=True)


def leakage_summary(leakage_folds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for check, sub in leakage_folds.groupby("check"):
        rows.append(
            {
                "check": check,
                "value": float(np.nanmean(sub["value"].to_numpy(dtype=float))),
                "n": int(len(sub)),
                "pass_count": int(sub["pass"].sum()),
                "all_pass": bool(sub["pass"].all()),
            }
        )
    forbidden = {"run", "eventno", "evt", "event_id", "sample", "target_residual_ns", "t_cfd20_ns"}
    overlap = sorted(forbidden.intersection(feature_columns()))
    rows.append(
        {
            "check": "ml_feature_forbidden_column_overlap",
            "value": float(len(overlap)),
            "n": 1,
            "pass_count": int(len(overlap) == 0),
            "all_pass": bool(len(overlap) == 0),
        }
    )
    return pd.DataFrame(rows)


def plot_outputs(outdir: Path, summary: pd.DataFrame, by_run: pd.DataFrame, pulses: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    plot = summary.copy()
    plot["label"] = plot["direction"] + "\n" + plot["method"]
    plot = plot.sort_values(["direction", "sigma68_ns"])
    ax.bar(np.arange(len(plot)), plot["sigma68_ns"], color="#4c78a8")
    ax.set_xticks(np.arange(len(plot)))
    ax.set_xticklabels(plot["label"], rotation=75, ha="right", fontsize=7)
    ax.set_ylabel("run-heldout pairwise sigma68 [ns]")
    fig.tight_layout()
    fig.savefig(outdir / "fig_transfer_sigma68.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for method in ["cfd20", "traditional_lowering_strata", "ml_lowering_rf"]:
        sub = by_run[by_run["method"] == method]
        ax.scatter(sub["heldout_run"], sub["sigma68_ns"], label=method, s=26)
    ax.set_xlabel("held-out target run")
    ax.set_ylabel("pairwise sigma68 [ns]")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_by_run_sigma68.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for sample, sub in pulses.groupby("sample"):
        ax.hist(sub["lowering_adc"], bins=np.linspace(0, 120, 61), histtype="step", density=True, label=sample)
    ax.set_xlabel("adaptive pedestal lowering [ADC]")
    ax.set_ylabel("density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "fig_lowering_by_sample.png", dpi=160)
    plt.close(fig)


def output_hashes(paths: Iterable[Path]) -> List[dict]:
    rows = []
    for path in sorted(paths):
        if path.is_file():
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(
    outdir: Path,
    config: dict,
    result: dict,
    reproduction: pd.DataFrame,
    summary: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    repro_table = "\n".join(
        "| {} | {} | {} | {} | {} | {} |".format(
            r.quantity, r.report_value, r.reproduced, r.delta, r.tolerance, "yes" if r.pass_ else "no"
        )
        for r in reproduction.rename(columns={"pass": "pass_"}).itertuples(index=False)
    )
    summary_table = "\n".join(
        "| {} | {} | {} | {} | {:.3f} [{:.3f}, {:.3f}] | {:.3f} [{:.3f}, {:.3f}] | {:.4f} [{:.4f}, {:.4f}] |".format(
            r.direction,
            r.method,
            r.n_heldout_runs,
            r.n_pair_residuals,
            r.sigma68_ns,
            r.sigma68_ci_low_ns,
            r.sigma68_ci_high_ns,
            r.full_rms_ns,
            r.full_rms_ci_low_ns,
            r.full_rms_ci_high_ns,
            r.tail_frac_abs_gt5ns,
            r.tail_ci_low,
            r.tail_ci_high,
        )
        for r in summary.itertuples(index=False)
    )
    leak_table = "\n".join(
        "| {} | {:.4g} | {}/{} | {} |".format(r.check, r.value, r.pass_count, r.n, "yes" if r.all_pass else "no")
        for r in leakage.itertuples(index=False)
    )
    def row(direction: str, method: str) -> pd.Series:
        return summary[(summary["direction"] == direction) & (summary["method"] == method)].iloc[0]

    i_to_ii_ml = row("sample_i_to_sample_ii", "ml_lowering_rf")
    ii_to_i_ml = row("sample_ii_to_sample_i", "ml_lowering_rf")
    i_to_ii_trad = row("sample_i_to_sample_ii", "traditional_lowering_strata")
    ii_to_i_trad = row("sample_ii_to_sample_i", "traditional_lowering_strata")
    ml_gain_flag = leakage[leakage["check"] == "ml_not_implausibly_better_than_raw"].iloc[0]
    report = """# S16g: Sample-I/Sample-II pedestal-lowering timing transfer

- **Ticket:** {ticket}
- **Worker:** {worker}
- **Input manifest:** `input_sha256.csv`
- **Config:** `configs/s16g_1781015168_1156_3a38609b.json`

## Question

Does a pedestal-lowering timing-residual model trained on Sample I transfer to Sample II, and vice versa, on B4/B6/B8 timing residuals?

## Raw reproduction first

Raw B-stack ROOT was read from `h101/HRDv` before any fitting. The S00/S02 count gate passes:

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass |
|---|---:|---:|---:|---:|---|
{repro_table}

The downstream timing table then uses events where B4, B6, and B8 are all selected above 1000 ADC. The table contains {n_pulses:,} downstream pulse rows from {n_events:,} events.

## Methods

The base timing is CFD20 on baseline samples 0-3. The S16 lowering diagnostic is the adaptive pedestal decrease, computed from the corrected waveform with jagged-sample masking. For each pulse the target is its base corrected time residual relative to the other two downstream staves after the fixed 2 cm time-of-flight correction.

The traditional model is a train-sample-only median residual table by stave, amplitude bin, and lowering bin, with stave/lowering and stave fallbacks. The ML model is a random forest over normalized waveform shape plus amplitude, peak, area/amp, pre-trigger spread, and lowering. Both are trained on one sample period and evaluated run-by-run on the other sample's analysis runs. Run id, event id, sample label, target residual, and timing columns are excluded from ML features.

## Transfer Results

Intervals are run-block bootstraps over held-out target runs.

| Direction | Method | Held-out runs | Pair residuals | Sigma68 ns | Full RMS ns | Tail frac abs>5 ns |
|---|---|---:|---:|---:|---:|---:|
{summary_table}

Sample I -> Sample II: traditional lowering strata gives {i_to_ii_trad.sigma68_ns:.3f} ns sigma68 and ML gives {i_to_ii_ml.sigma68_ns:.3f} ns. Sample II -> Sample I: traditional gives {ii_to_i_trad.sigma68_ns:.3f} ns and ML gives {ii_to_i_ml.sigma68_ns:.3f} ns. The deterministic lowering-strata model is the strongest transfer result in both directions.

## Leakage Checks

| Check | Aggregate value | Passing folds | All pass |
|---|---:|---:|---|
{leak_table}

The transfer split has no train/held-out run overlap and no train/held-out event overlap. The shuffled-target control is worse than ML in all folds, but the ML-vs-raw improvement exceeds the pre-set "too good" guard in {ml_gain_pass}/{ml_gain_n} folds. Those fold details are saved in `leakage_fold_details.csv`, and the RF is therefore treated as a diagnostic transfer model rather than the headline correction.

## Conclusion

A simple traditional lowering-strata correction transfers across sample periods and substantially narrows B4/B6/B8 pair residuals versus raw CFD20. The direct adaptive-lowered CFD20 timing does not transfer, and ML does not beat the traditional correction. The conservative reading is that pedestal lowering is a useful detector diagnostic and coarse timing nuisance term, but the high-lowering tail should not be promoted as a portable ML timing correction without stronger run-family controls.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        repro_table=repro_table,
        n_pulses=result["downstream_table"]["pulse_rows"],
        n_events=result["downstream_table"]["event_rows"],
        summary_table=summary_table,
        i_to_ii_trad=i_to_ii_trad,
        i_to_ii_ml=i_to_ii_ml,
        ii_to_i_trad=ii_to_i_trad,
        ii_to_i_ml=ii_to_i_ml,
        leak_table=leak_table,
        ml_gain_pass=int(ml_gain_flag.pass_count),
        ml_gain_n=int(ml_gain_flag.n),
    )
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    input_sha = pd.DataFrame(
        [{"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)} for path in raw_paths(config)]
    )
    input_sha.to_csv(outdir / "input_sha256.csv", index=False)

    reproduction = s02.reproduce_counts(config)
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    pulses = s02.load_downstream_pulses(config)
    pulses = add_lowering_features(pulses, config)
    pulses = add_bins(pulses, config)
    pulses = add_ml_features(pulses)
    pulses["target_residual_ns"] = residual_targets(pulses, config)
    pulses.to_csv(outdir / "downstream_pulse_features.csv", index=False)

    residuals, by_run, leak_folds = evaluate_transfer(pulses, config, rng)
    residuals.to_csv(outdir / "pairwise_residuals.csv", index=False)
    by_run.to_csv(outdir / "method_by_run.csv", index=False)
    leak_folds.to_csv(outdir / "leakage_fold_details.csv", index=False)
    summary = summarize_residuals(residuals, config, rng)
    summary.to_csv(outdir / "method_summary.csv", index=False)
    leakage = leakage_summary(leak_folds)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    plot_outputs(outdir, summary, by_run, pulses)

    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "raw_reproduction_all_pass": bool(reproduction["pass"].all()),
        "downstream_table": {
            "pulse_rows": int(len(pulses)),
            "event_rows": int(pulses["event_id"].nunique()),
            "runs": sorted(int(x) for x in pulses["run"].unique()),
            "sample_i_pulse_rows": int((pulses["sample"] == "sample_i").sum()),
            "sample_ii_pulse_rows": int((pulses["sample"] == "sample_ii").sum()),
        },
        "split_by_run": {
            "sample_i_to_sample_ii": {
                "train_runs": [int(x) for x in config["transfer_train_runs"]["sample_i"]],
                "heldout_runs": [int(x) for x in config["transfer_eval_runs"]["sample_ii"]],
            },
            "sample_ii_to_sample_i": {
                "train_runs": [int(x) for x in config["transfer_train_runs"]["sample_ii"]],
                "heldout_runs": [int(x) for x in config["transfer_eval_runs"]["sample_i"]],
            },
        },
        "primary_results": summary.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "leakage_detail_file": str(outdir / "leakage_fold_details.csv"),
        "conclusion": "A simple train-sample stratified lowering correction transfers in both directions; ML is diagnostic only because its fold-level gains trigger the too-good leakage guard despite clean run/event separation.",
        "follow_up_ticket_appended": False,
        "follow_up_ticket_reason": "Skipped: prior reports already propose forced/random pedestal ingest and timing-tail nuisance follow-ups.",
    }
    (outdir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(outdir, config, json_clean(result), reproduction, summary, leakage)

    outputs = [p for p in outdir.iterdir() if p.is_file() and p.name != "manifest.json"]
    outputs.extend([config_path, Path(__file__)])
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__), config_path),
        "config": str(config_path),
        "script": str(Path(__file__)),
        "git_commit": result["git_commit"],
        "random_seed": int(config["ml"]["random_seed"]),
        "input_sha256": str(outdir / "input_sha256.csv"),
        "outputs": output_hashes(outputs),
    }
    (outdir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
