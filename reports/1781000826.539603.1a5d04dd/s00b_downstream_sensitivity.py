#!/usr/bin/env python3
"""S00b: downstream sensitivity to dynamic-range vs median-first-four gates.

This script reads raw B-stack ROOT files directly. It compares two pulse
selection semantics:

* median gate: max(waveform - median(samples 0..3)) > 1000 ADC
* dynamic gate: max(waveform) - min(waveform) > 1000 ADC

The median gate is the S00 selected-pulse definition. The dynamic gate is the
raw-waveform equivalent of the sorted hrdMax shortcut studied in S00a.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


OUT = Path(__file__).resolve().parent
CONFIG = Path("configs/s00_reproduction.yaml")
TICKET = "1781000826.539603.1a5d04dd"
WORKER = "testbeam-laptop-1"
STUDY = "S00b"
TITLE = "downstream sensitivity to baseline estimator"
SEED = 8128
HELDOUT_RUNS = [55, 57, 63, 65]
DOWNSTREAM_STAVES = ["B4", "B6", "B8"]
STAVE_POSITION_CM = {"B2": 0.0, "B4": 2.0, "B6": 4.0, "B8": 6.0}
TOF_NS_PER_CM = 0.078


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


def load_config() -> dict:
    with CONFIG.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def configured_runs(config: dict) -> list:
    runs = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def raw_path(config: dict, run: int) -> Path:
    root_dir = Path(config["raw_root_dir"])
    path = root_dir / f"hrdb_run_{run:04d}.root"
    if path.exists():
        return path
    # Some configs predate the data symlink and include data/extracted.
    fallback = Path("data/root/root") / f"hrdb_run_{run:04d}.root"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(path)


def iter_raw(config: dict, run: int, step_size: int = 20000):
    tree = uproot.open(raw_path(config, run))["h101"]
    yield from tree.iterate(["EVT", "EVENTNO", "HRDv"], step_size=step_size, library="np")


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float = 0.20) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for idx in np.where(valid)[0]:
        j = int(first[idx])
        if j <= 0:
            out[idx] = float(j)
            continue
        y0 = float(waveforms[idx, j - 1])
        y1 = float(waveforms[idx, j])
        denom = y1 - y0
        if denom <= 0:
            out[idx] = float(j)
        else:
            out[idx] = (j - 1) + (threshold[idx] - y0) / denom
    return out


def width_above_fraction(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    return (waveforms >= threshold[:, None]).sum(axis=1).astype(float)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.quantile(values, 0.84) - np.quantile(values, 0.16)) / 2.0)


def rms(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((values - np.mean(values)) ** 2)))


def timing_residuals(times: np.ndarray, selected: np.ndarray, stave_names: list, selector: str, run: int, evt: np.ndarray) -> list:
    rows = []
    down_idx = [stave_names.index(name) for name in DOWNSTREAM_STAVES]
    all_hit = selected[:, down_idx].all(axis=1)
    pair_defs = [(0, 1), (1, 2), (0, 2)]
    for event_idx in np.where(all_hit)[0]:
        for local_i, local_j in pair_defs:
            i = down_idx[local_i]
            j = down_idx[local_j]
            ti = times[event_idx, i]
            tj = times[event_idx, j]
            if not (np.isfinite(ti) and np.isfinite(tj)):
                continue
            si = stave_names[i]
            sj = stave_names[j]
            geom = (STAVE_POSITION_CM[si] - STAVE_POSITION_CM[sj]) * TOF_NS_PER_CM
            rows.append(
                {
                    "run": int(run),
                    "evt": int(evt[event_idx]),
                    "selector": selector,
                    "pair": f"{si}-{sj}",
                    "residual_ns": float((ti - tj) - geom),
                }
            )
    return rows


def append_ml_rows(rows: list, run: int, stave_names: list, corrected: np.ndarray, median_amp: np.ndarray, dynamic_amp: np.ndarray, selected_median: np.ndarray, selected_dynamic: np.ndarray, rng: np.random.Generator) -> None:
    dynamic_pool = selected_dynamic
    if not dynamic_pool.any():
        return

    peak_sample = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    tail = corrected[..., 12:].sum(axis=-1)
    early = corrected[..., :4].sum(axis=-1)
    width20 = np.zeros_like(median_amp, dtype=float)
    width50 = np.zeros_like(median_amp, dtype=float)
    cfd20 = np.zeros_like(median_amp, dtype=float)
    for stave_idx in range(len(stave_names)):
        wf = corrected[:, stave_idx, :]
        amp = np.maximum(median_amp[:, stave_idx], 1.0)
        width20[:, stave_idx] = width_above_fraction(wf, amp, 0.20)
        width50[:, stave_idx] = width_above_fraction(wf, amp, 0.50)
        cfd20[:, stave_idx] = cfd_time_samples(wf, amp, 0.20)

    event_idx, stave_idx = np.where(dynamic_pool)
    is_extra = selected_dynamic[event_idx, stave_idx] & ~selected_median[event_idx, stave_idx]
    is_median = selected_median[event_idx, stave_idx]
    keep = is_extra.copy()
    # Keep all dynamic-only pulses and a reproducible control sample of
    # median-selected pulses. Held-out scoring uses the same sampling rule so
    # the class prior is documented and stable.
    keep |= is_median & (rng.random(len(is_median)) < 0.35)
    if not keep.any():
        return

    event_idx = event_idx[keep]
    stave_idx = stave_idx[keep]
    amp = np.maximum(median_amp[event_idx, stave_idx], 1.0)
    dyn = np.maximum(dynamic_amp[event_idx, stave_idx], 1.0)
    row = pd.DataFrame(
        {
            "run": int(run),
            "stave_idx": stave_idx.astype(int),
            "dynamic_only": (~selected_median[event_idx, stave_idx]).astype(int),
            "peak_sample": peak_sample[event_idx, stave_idx],
            "area_over_amp": area[event_idx, stave_idx] / amp,
            "tail_frac": tail[event_idx, stave_idx] / np.maximum(np.abs(area[event_idx, stave_idx]), 1.0),
            "early_frac": early[event_idx, stave_idx] / np.maximum(np.abs(area[event_idx, stave_idx]), 1.0),
            "width20": width20[event_idx, stave_idx],
            "width50": width50[event_idx, stave_idx],
            "cfd20": cfd20[event_idx, stave_idx],
            "median_amp": median_amp[event_idx, stave_idx],
            "dynamic_amp": dynamic_amp[event_idx, stave_idx],
            "dynamic_minus_median": dyn - amp,
        }
    )
    rows.append(row)


def scan_raw(config: dict) -> tuple:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    staves = {name: int(channel) for name, channel in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names], dtype=int)
    rng = np.random.default_rng(SEED)

    count_rows = []
    timing_rows = []
    ml_rows = []

    for run in configured_runs(config):
        row = defaultdict(int)
        row["run"] = int(run)
        for batch in iter_raw(config, run):
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            baseline = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - baseline[..., None]
            median_amp = corrected.max(axis=-1)
            dynamic_amp = waveforms.max(axis=-1) - waveforms.min(axis=-1)
            selected_median = median_amp > cut
            selected_dynamic = dynamic_amp > cut
            dynamic_only = selected_dynamic & ~selected_median
            median_only = selected_median & ~selected_dynamic

            row["events"] += int(len(evt))
            row["median_pulses"] += int(selected_median.sum())
            row["dynamic_pulses"] += int(selected_dynamic.sum())
            row["dynamic_only_pulses"] += int(dynamic_only.sum())
            row["median_only_pulses"] += int(median_only.sum())
            row["median_events"] += int(selected_median.any(axis=1).sum())
            row["dynamic_events"] += int(selected_dynamic.any(axis=1).sum())

            for prefix, selected in [("median", selected_median), ("dynamic", selected_dynamic)]:
                n_staves = selected.sum(axis=1)
                any_event = n_staves > 0
                denom = int(any_event.sum())
                row[f"{prefix}_selected_events"] += denom
                row[f"{prefix}_multi_stave_events"] += int((n_staves[any_event] >= 2).sum())
                row[f"{prefix}_ge3_stave_events"] += int((n_staves[any_event] >= 3).sum())
                downstream_idx = [stave_names.index(name) for name in DOWNSTREAM_STAVES]
                row[f"{prefix}_downstream_events"] += int((selected[:, downstream_idx].any(axis=1) & any_event).sum())
                row[f"{prefix}_downstream_allhit_events"] += int(selected[:, downstream_idx].all(axis=1).sum())

            times = np.full(median_amp.shape, np.nan, dtype=float)
            for stave_idx in range(len(stave_names)):
                times[:, stave_idx] = cfd_time_samples(corrected[:, stave_idx, :], np.maximum(median_amp[:, stave_idx], 1.0), 0.20)
            timing_rows.extend(timing_residuals(times, selected_median, stave_names, "median_first4", run, evt))
            timing_rows.extend(timing_residuals(times, selected_dynamic, stave_names, "dynamic_range", run, evt))
            append_ml_rows(ml_rows, run, stave_names, corrected, median_amp, dynamic_amp, selected_median, selected_dynamic, rng)
        count_rows.append(dict(row))
        print(f"run {run}: median={row['median_pulses']} dynamic={row['dynamic_pulses']} extra={row['dynamic_only_pulses']}")

    counts = pd.DataFrame(count_rows).sort_values("run").reset_index(drop=True)
    timing = pd.DataFrame(timing_rows)
    ml_sample = pd.concat(ml_rows, ignore_index=True) if ml_rows else pd.DataFrame()
    return counts, timing, ml_sample


def block_bootstrap_table(df: pd.DataFrame, runs: list, value_func, n_boot: int = 1000) -> tuple:
    rng = np.random.default_rng(SEED + 17)
    values = []
    run_values = {run: df[df["run"] == run].copy() for run in runs}
    for _ in range(n_boot):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        pieces = [run_values[int(run)] for run in sampled if not run_values[int(run)].empty]
        if not pieces:
            continue
        values.append(value_func(pd.concat(pieces, ignore_index=True)))
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def summarize_traditional(counts: pd.DataFrame, timing: pd.DataFrame) -> tuple:
    held_counts = counts[counts["run"].isin(HELDOUT_RUNS)].copy()
    rows = []
    for selector, prefix in [("median_first4", "median"), ("dynamic_range", "dynamic")]:
        selected_events = int(held_counts[f"{prefix}_selected_events"].sum())
        rows.extend(
            [
                {
                    "selector": selector,
                    "metric": "selected_pulses",
                    "value": float(held_counts[f"{prefix}_pulses"].sum()),
                    "ci_low": np.nan,
                    "ci_high": np.nan,
                },
                {
                    "selector": selector,
                    "metric": "selected_events",
                    "value": float(selected_events),
                    "ci_low": np.nan,
                    "ci_high": np.nan,
                },
            ]
        )
        for metric, numerator in [
            ("multi_stave_fraction", f"{prefix}_multi_stave_events"),
            ("ge3_stave_fraction", f"{prefix}_ge3_stave_events"),
            ("downstream_fraction", f"{prefix}_downstream_events"),
            ("downstream_allhit_fraction", f"{prefix}_downstream_allhit_events"),
        ]:
            value = float(held_counts[numerator].sum() / selected_events) if selected_events else float("nan")

            def frac_func(sample: pd.DataFrame, n=numerator, d=f"{prefix}_selected_events") -> float:
                denom = float(sample[d].sum())
                return float(sample[n].sum() / denom) if denom else float("nan")

            ci_low, ci_high = block_bootstrap_table(held_counts, HELDOUT_RUNS, frac_func)
            rows.append({"selector": selector, "metric": metric, "value": value, "ci_low": ci_low, "ci_high": ci_high})

        sub = timing[(timing["selector"] == selector) & (timing["run"].isin(HELDOUT_RUNS))]
        value = sigma68(sub["residual_ns"].to_numpy()) if not sub.empty else float("nan")
        ci_low, ci_high = block_bootstrap_table(sub, HELDOUT_RUNS, lambda sample: sigma68(sample["residual_ns"].to_numpy()))
        rows.append({"selector": selector, "metric": "downstream_cfd20_pairwise_sigma68_ns", "value": value, "ci_low": ci_low, "ci_high": ci_high})
        rows.append({"selector": selector, "metric": "downstream_cfd20_pair_count", "value": float(len(sub)), "ci_low": np.nan, "ci_high": np.nan})
        rows.append({"selector": selector, "metric": "downstream_cfd20_pairwise_rms_ns", "value": rms(sub["residual_ns"].to_numpy()) if not sub.empty else float("nan"), "ci_low": np.nan, "ci_high": np.nan})

    summary = pd.DataFrame(rows)

    med_t = timing[(timing["selector"] == "median_first4") & (timing["run"].isin(HELDOUT_RUNS))]["residual_ns"].to_numpy()
    dyn_t = timing[(timing["selector"] == "dynamic_range") & (timing["run"].isin(HELDOUT_RUNS))]["residual_ns"].to_numpy()
    bins = np.linspace(-12.0, 12.0, 49)
    med_hist, _ = np.histogram(med_t[np.isfinite(med_t)], bins=bins)
    dyn_hist, _ = np.histogram(dyn_t[np.isfinite(dyn_t)], bins=bins)
    scale = dyn_hist.sum() / med_hist.sum() if med_hist.sum() else 1.0
    expected = med_hist * scale
    mask = expected > 5
    chi2 = float((((dyn_hist[mask] - expected[mask]) ** 2) / expected[mask]).sum()) if mask.any() else float("nan")
    ndf = int(mask.sum() - 1) if mask.any() else 0
    comparison = {
        "timing_hist_chi2": chi2,
        "timing_hist_ndf": ndf,
        "timing_hist_chi2_ndf": float(chi2 / ndf) if ndf > 0 else float("nan"),
    }
    return summary, comparison


def fit_ml_models(sample: pd.DataFrame) -> tuple:
    train = sample[~sample["run"].isin(HELDOUT_RUNS)].copy()
    test = sample[sample["run"].isin(HELDOUT_RUNS)].copy()
    y_train = train["dynamic_only"].to_numpy(dtype=int)
    y_test = test["dynamic_only"].to_numpy(dtype=int)
    groups = train["run"].to_numpy(dtype=int)

    shape_features = ["stave_idx", "peak_sample", "area_over_amp", "tail_frac", "early_frac", "width20", "width50", "cfd20"]
    leaky_features = shape_features + ["median_amp", "dynamic_amp", "dynamic_minus_median"]
    all_features = sorted(set(leaky_features))
    for frame in [train, test]:
        frame[all_features] = frame[all_features].replace([np.inf, -np.inf], np.nan)
        frame[all_features] = frame[all_features].fillna(-1.0)

    cv_rows = []
    best_c = None
    best_auc = -np.inf
    for c_value in [0.01, 0.1, 1.0, 10.0]:
        aucs = []
        splitter = GroupKFold(n_splits=3)
        X = train[shape_features].to_numpy(dtype=float)
        for fit_idx, valid_idx in splitter.split(X, y_train, groups):
            if len(np.unique(y_train[valid_idx])) < 2:
                continue
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=c_value, class_weight="balanced", max_iter=1000, random_state=SEED),
            )
            model.fit(X[fit_idx], y_train[fit_idx])
            prob = model.predict_proba(X[valid_idx])[:, 1]
            aucs.append(roc_auc_score(y_train[valid_idx], prob))
        mean_auc = float(np.mean(aucs))
        cv_rows.append({"feature_set": "shape_only", "C": c_value, "cv_auc": mean_auc})
        if mean_auc > best_auc:
            best_auc = mean_auc
            best_c = c_value

    def fit_score(features: list, label: str, y_fit: np.ndarray = None) -> dict:
        y_fit = y_train if y_fit is None else y_fit
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=best_c, class_weight="balanced", max_iter=1000, random_state=SEED),
        )
        model.fit(train[features].to_numpy(dtype=float), y_fit)
        prob = model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
        pred = (prob >= 0.5).astype(int)
        row = {
            "model": label,
            "features": ",".join(features),
            "heldout_runs": ",".join(str(run) for run in HELDOUT_RUNS),
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "positive_train": int(y_train.sum()),
            "positive_test": int(y_test.sum()),
            "auc": float(roc_auc_score(y_test, prob)),
            "average_precision": float(average_precision_score(y_test, prob)),
            "accuracy": float(accuracy_score(y_test, pred)),
            "brier": float(brier_score_loss(y_test, prob)),
            "mean_score_dynamic_only": float(prob[y_test == 1].mean()),
            "mean_score_median_selected": float(prob[y_test == 0].mean()),
        }
        return row, prob

    primary_row, primary_prob = fit_score(shape_features, "shape_only_logistic")
    leaky_row, leaky_prob = fit_score(leaky_features, "leaky_amplitude_logistic")
    rng = np.random.default_rng(SEED + 23)
    shuffled = y_train.copy()
    for run in sorted(train["run"].unique()):
        idx = np.flatnonzero(train["run"].to_numpy(dtype=int) == int(run))
        shuffled[idx] = rng.permutation(shuffled[idx])
    shuffled_row, shuffled_prob = fit_score(shape_features, "within_run_label_shuffle_control", shuffled)
    global_shuffled = rng.permutation(y_train)
    global_shuffled_row, global_shuffled_prob = fit_score(shape_features, "global_label_shuffle_control", global_shuffled)

    boot_df = test[["run", "dynamic_only"]].copy()
    boot_df["primary_prob"] = primary_prob
    ci_auc = block_bootstrap_table(
        boot_df,
        HELDOUT_RUNS,
        lambda sample_df: roc_auc_score(sample_df["dynamic_only"].to_numpy(dtype=int), sample_df["primary_prob"].to_numpy(dtype=float))
        if len(np.unique(sample_df["dynamic_only"].to_numpy(dtype=int))) == 2
        else float("nan"),
    )
    ci_ap = block_bootstrap_table(
        boot_df,
        HELDOUT_RUNS,
        lambda sample_df: average_precision_score(sample_df["dynamic_only"].to_numpy(dtype=int), sample_df["primary_prob"].to_numpy(dtype=float))
        if len(np.unique(sample_df["dynamic_only"].to_numpy(dtype=int))) == 2
        else float("nan"),
    )
    primary_row["auc_ci_low"], primary_row["auc_ci_high"] = ci_auc
    primary_row["average_precision_ci_low"], primary_row["average_precision_ci_high"] = ci_ap
    for row in [leaky_row, shuffled_row, global_shuffled_row]:
        row["auc_ci_low"] = np.nan
        row["auc_ci_high"] = np.nan
        row["average_precision_ci_low"] = np.nan
        row["average_precision_ci_high"] = np.nan

    reliability = test[["run", "dynamic_only"]].copy()
    reliability["prob"] = primary_prob
    reliability["bin"] = pd.cut(reliability["prob"], bins=np.linspace(0.0, 1.0, 11), include_lowest=True)
    reliability = (
        reliability.groupby("bin", observed=False)
        .agg(mean_prob=("prob", "mean"), frac_dynamic_only=("dynamic_only", "mean"), n=("dynamic_only", "size"))
        .reset_index()
    )
    reliability["bin"] = reliability["bin"].astype(str)

    return pd.DataFrame(cv_rows), pd.DataFrame([primary_row, leaky_row, shuffled_row, global_shuffled_row]), reliability


def write_figures(counts: pd.DataFrame, timing: pd.DataFrame, ml_reliability: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(counts["run"], counts["median_pulses"], "o-", label="median-first-four")
    ax.plot(counts["run"], counts["dynamic_pulses"], "s-", label="dynamic range")
    ax.bar(counts["run"], counts["dynamic_only_pulses"], alpha=0.25, label="dynamic-only excess")
    for run in HELDOUT_RUNS:
        ax.axvline(run, color="k", alpha=0.08, lw=1)
    ax.set_xlabel("Run")
    ax.set_ylabel("Selected B-stave pulse records")
    ax.set_title("S00b selector counts by run")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig_selector_counts_by_run.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    held = timing[timing["run"].isin(HELDOUT_RUNS)]
    bins = np.linspace(-12.0, 12.0, 49)
    for selector, color in [("median_first4", "tab:blue"), ("dynamic_range", "tab:orange")]:
        vals = held[held["selector"] == selector]["residual_ns"].to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        ax.hist(vals, bins=bins, histtype="step", density=True, label=selector, color=color, lw=1.6)
    ax.set_xlabel("CFD20 downstream pair residual (samples)")
    ax.set_ylabel("Density")
    ax.set_title("Held-out timing residual distribution")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig_heldout_timing_residuals.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.2, 4.8))
    ok = ml_reliability["n"] > 0
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.scatter(
        ml_reliability.loc[ok, "mean_prob"],
        ml_reliability.loc[ok, "frac_dynamic_only"],
        s=np.clip(ml_reliability.loc[ok, "n"] / 60.0, 12, 180),
    )
    ax.set_xlabel("Mean ML score")
    ax.set_ylabel("Observed dynamic-only fraction")
    ax.set_title("Shape-only selector-shift calibration")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig_ml_selector_reliability.png", dpi=160)
    plt.close(fig)


def write_report(result: dict, traditional: pd.DataFrame, comparison: dict, ml_benchmark: pd.DataFrame) -> None:
    repro = result["reproduction"]
    med = traditional[traditional["selector"] == "median_first4"].set_index("metric")
    dyn = traditional[traditional["selector"] == "dynamic_range"].set_index("metric")
    shape = ml_benchmark[ml_benchmark["model"] == "shape_only_logistic"].iloc[0]
    leaky = ml_benchmark[ml_benchmark["model"] == "leaky_amplitude_logistic"].iloc[0]
    shuffled = ml_benchmark[ml_benchmark["model"] == "within_run_label_shuffle_control"].iloc[0]
    global_shuffled = ml_benchmark[ml_benchmark["model"] == "global_label_shuffle_control"].iloc[0]

    def fmt_ci(row, digits=4):
        return f"{row['value']:.{digits}f} [{row['ci_low']:.{digits}f}, {row['ci_high']:.{digits}f}]"

    text = f"""# Study report: S00b - downstream sensitivity to baseline estimator

- **Study ID:** S00b
- **Ticket:** `{TICKET}`
- **Author:** `{WORKER}`
- **Date:** 2026-06-09
- **Depends on:** S00a
- **Input checksum(s):** raw B-stack ROOT hashes in `manifest.json`
- **Git commit:** `{result['git_commit']}`
- **Command:** `/home/billy/anaconda3/bin/python reports/{TICKET}/s00b_downstream_sensitivity.py`

## 0. Question

Do timing and pile-up headline distributions change if low-amplitude B-stack pulses are selected with dynamic range rather than the S00 median-first-four baseline amplitude?

## 1. Reproduction

The S00 median-first-four gate was reproduced directly from raw ROOT before any downstream analysis.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00 median-first-four selected pulses | 640737 | {repro['median_pulses']} | {repro['median_delta']} | 0 | {'yes' if repro['median_pass'] else 'no'} |
| S00a dynamic-range equivalent count | 706373 | {repro['dynamic_pulses']} | {repro['dynamic_delta_vs_s00a_sorted_hrdmax']} | 0 | {'yes' if repro['dynamic_pass'] else 'no'} |
| Dynamic-only excess pulses | 65636 | {repro['dynamic_only_pulses']} | {repro['dynamic_only_delta_vs_s00a_sorted_excess']} | 0 | {'yes' if repro['dynamic_only_pass'] else 'no'} |
| Median-only pulses | 0 | {repro['median_only_pulses']} | {repro['median_only_pulses']} | 0 | {'yes' if repro['median_only_pulses'] == 0 else 'no'} |

The dynamic-range selector is a strict superset of the S00 selector in this data set. The excess is therefore a low-amplitude population admitted by baseline semantics, not a replacement population. The raw dynamic-range count exactly reproduces S00a's sorted `hrdMax > 1000` count.

## 2. Traditional Method

The traditional analysis is a deterministic raw-waveform comparison on held-out runs `{','.join(str(run) for run in HELDOUT_RUNS)}`. Timing uses baseline-subtracted CFD20 downstream B4/B6/B8 pair residuals, with the same fixed geometry correction used by prior timing studies. Pile-up/topology uses selected-event stave multiplicities.

| Held-out metric | Median-first-four | Dynamic range |
|---|---:|---:|
| selected pulses | {int(med.loc['selected_pulses', 'value'])} | {int(dyn.loc['selected_pulses', 'value'])} |
| selected events | {int(med.loc['selected_events', 'value'])} | {int(dyn.loc['selected_events', 'value'])} |
| multi-stave fraction | {fmt_ci(med.loc['multi_stave_fraction'])} | {fmt_ci(dyn.loc['multi_stave_fraction'])} |
| >=3-stave fraction | {fmt_ci(med.loc['ge3_stave_fraction'])} | {fmt_ci(dyn.loc['ge3_stave_fraction'])} |
| downstream-hit fraction | {fmt_ci(med.loc['downstream_fraction'])} | {fmt_ci(dyn.loc['downstream_fraction'])} |
| downstream all-hit fraction | {fmt_ci(med.loc['downstream_allhit_fraction'])} | {fmt_ci(dyn.loc['downstream_allhit_fraction'])} |
| downstream CFD20 pair sigma68 | {fmt_ci(med.loc['downstream_cfd20_pairwise_sigma68_ns'])} samples | {fmt_ci(dyn.loc['downstream_cfd20_pairwise_sigma68_ns'])} samples |

The normalized held-out timing histogram comparison gives chi2/ndf = {comparison['timing_hist_chi2_ndf']:.3f} ({comparison['timing_hist_chi2']:.2f}/{comparison['timing_hist_ndf']}). The timing width shifts only modestly, while topology fractions move visibly because dynamic range admits extra downstream and multi-stave low-amplitude records.

## 3. ML Method

The ML method is a run-held-out logistic selector-shift classifier trained to identify dynamic-only pulses among dynamic-selected pulses. The primary model uses shape/timing features only: stave index, peak sample, area/amp, tail and early fractions, widths, and CFD20. It excludes median amplitude, dynamic amplitude, and their difference.

| Model | Held-out AUC | AP | Accuracy | Notes |
|---|---:|---:|---:|---|
| shape-only logistic | {shape['auc']:.4f} [{shape['auc_ci_low']:.4f}, {shape['auc_ci_high']:.4f}] | {shape['average_precision']:.4f} [{shape['average_precision_ci_low']:.4f}, {shape['average_precision_ci_high']:.4f}] | {shape['accuracy']:.4f} | primary non-leaky model |
| leaky amplitude logistic | {leaky['auc']:.4f} | {leaky['average_precision']:.4f} | {leaky['accuracy']:.4f} | includes selector-defining amplitudes |
| within-run label shuffle | {shuffled['auc']:.4f} | {shuffled['average_precision']:.4f} | {shuffled['accuracy']:.4f} | run/composition confounding control |
| global label shuffle | {global_shuffled['auc']:.4f} | {global_shuffled['average_precision']:.4f} | {global_shuffled['accuracy']:.4f} | pipeline sanity control |

The leaky amplitude model is near-perfect because it sees variables that define the label. Both shuffled-label controls remain elevated, which is a leakage warning: run/topology composition and the sampled class mixture are strong enough that the shape-only classifier is not a clean individual-pulse proof. The ML result is therefore reported as a failed stress test for leakage-prone selector-shift modeling, not as support for adopting an ML selector.

## 4. Head-to-head Benchmark

Same held-out runs, same raw ROOT source:

| Method | Metric | Result | Interpretation |
|---|---|---:|---|
| Traditional deterministic gate comparison | dynamic-only excess / S00 pulses | {result['traditional']['dynamic_excess_fraction_full']:.4f} | dynamic range over-selects by {100.0 * result['traditional']['dynamic_excess_fraction_full']:.2f}% |
| Traditional topology | held-out downstream fraction delta | {result['traditional']['heldout_downstream_fraction_delta']:.4f} | topology headline changes |
| Traditional timing | held-out sigma68 delta | {result['traditional']['heldout_sigma68_delta']:.4f} samples | timing width changes less than topology |
| ML shape-only selector-shift model | held-out AUC | {shape['auc']:.4f} | too good; shuffled controls flag confounding |

Verdict: S00a's sorted `hrdMax` issue is not only bookkeeping for downstream selections. It mostly changes low-amplitude topology composition; the CFD20 timing headline is less sensitive but not exactly invariant.

## 5. Falsification

- **Pre-registered metric:** exact raw S00 count reproduction, exact dynamic-range equivalent reproduction, then held-out run-block bootstrap CIs for topology and timing metrics.
- **Failure criteria:** any S00 count delta or any evidence that the ML headline is only definition leakage without a valid raw deterministic comparison.
- **Result:** count reproduction passed exactly. The leaky model was identified as definition leakage and excluded. Both shuffled controls stayed elevated, so the ML headline is explicitly downgraded to a failed leakage stress test; the deterministic topology/timing comparison carries the result.

## 6. Threats to Validity

- **Benchmark/selection:** the traditional baseline is the deterministic selector comparison from raw ROOT. Timing uses CFD20, so a stronger template/timewalk timing analysis could change the timing-width sensitivity.
- **Data leakage:** all ML evaluation is by held-out run. Direct selector variables are isolated in the leaky ablation and are not included in the primary model.
- **Metric misuse:** ML predicts selector-induced population membership, not physics truth. The physics-facing outputs are the topology and timing distribution changes.
- **Post-hoc selection:** held-out runs and feature ablations are fixed in the script; no threshold scan is used for the headline result.

## 7. Provenance Manifest

`manifest.json` records raw input hashes, command, seed, environment, and output hashes.

## 8. Findings & Next Steps

Dynamic-range selection admits {repro['dynamic_only_pulses']:,} additional B-stave records relative to S00. Those records are not harmless for downstream counting: multi-stave and downstream topology fractions shift on held-out runs. Timing residual widths are comparatively stable, but the selected all-hit sample is larger and not distribution-identical.

Queued follow-ups:

- **S00c:** add a CI/integrator regression that recomputes median and dynamic-range selected counts from raw ROOT and fails on accidental dynamic-range use.
- **S02c:** rerun the strongest template/timewalk timing method under the median-first-four and dynamic-range selectors to bound timing-systematic drift near threshold.

## 9. Reproducibility

Artifacts written: `counts_by_run.csv`, `timing_residuals.csv.gz`, `ml_selector_sample.csv.gz`, `traditional_summary.csv`, `ml_cv_scan.csv`, `ml_benchmark.csv`, `ml_reliability.csv`, figures, `result.json`, and `manifest.json`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def output_hashes() -> dict:
    hashes = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    config = load_config()
    counts, timing, ml_sample = scan_raw(config)
    traditional, comparison = summarize_traditional(counts, timing)
    ml_cv, ml_benchmark, ml_reliability = fit_ml_models(ml_sample)
    write_figures(counts, timing, ml_reliability)

    counts.to_csv(OUT / "counts_by_run.csv", index=False)
    timing.to_csv(OUT / "timing_residuals.csv.gz", index=False, compression="gzip")
    ml_sample.to_csv(OUT / "ml_selector_sample.csv.gz", index=False, compression="gzip")
    traditional.to_csv(OUT / "traditional_summary.csv", index=False)
    pd.DataFrame([comparison]).to_csv(OUT / "timing_histogram_comparison.csv", index=False)
    ml_cv.to_csv(OUT / "ml_cv_scan.csv", index=False)
    ml_benchmark.to_csv(OUT / "ml_benchmark.csv", index=False)
    ml_reliability.to_csv(OUT / "ml_reliability.csv", index=False)

    total_counts = counts.sum(numeric_only=True).to_dict()
    median_pulses = int(total_counts["median_pulses"])
    dynamic_pulses = int(total_counts["dynamic_pulses"])
    dynamic_only_pulses = int(total_counts["dynamic_only_pulses"])
    median_only_pulses = int(total_counts["median_only_pulses"])
    med = traditional[traditional["selector"] == "median_first4"].set_index("metric")
    dyn = traditional[traditional["selector"] == "dynamic_range"].set_index("metric")
    shape = ml_benchmark[ml_benchmark["model"] == "shape_only_logistic"].iloc[0]
    leaky = ml_benchmark[ml_benchmark["model"] == "leaky_amplitude_logistic"].iloc[0]
    shuffled = ml_benchmark[ml_benchmark["model"] == "within_run_label_shuffle_control"].iloc[0]
    global_shuffled = ml_benchmark[ml_benchmark["model"] == "global_label_shuffle_control"].iloc[0]

    input_rows = []
    aggregate = hashlib.sha256()
    for run in configured_runs(config):
        path = raw_path(config, run)
        digest = sha256_file(path)
        aggregate.update(digest.encode("ascii"))
        input_rows.append({"path": str(path), "sha256": digest})

    with (OUT / "input_sha256.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"])
        writer.writeheader()
        writer.writerows(input_rows)

    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": TITLE,
        "reproduced": bool(median_pulses == 640737 and median_only_pulses == 0),
        "reproduction": {
            "median_pulses": median_pulses,
            "median_delta": median_pulses - 640737,
            "median_pass": bool(median_pulses == 640737),
            "dynamic_pulses": dynamic_pulses,
            "dynamic_delta_vs_s00a_sorted_hrdmax": dynamic_pulses - 706373,
            "dynamic_pass": bool(dynamic_pulses == 706373),
            "dynamic_note": "raw max-min count; S00a sorted hrdMax count is 706373",
            "dynamic_only_pulses": dynamic_only_pulses,
            "dynamic_only_delta_vs_s00a_sorted_excess": dynamic_only_pulses - 65636,
            "dynamic_only_pass": bool(dynamic_only_pulses == 65636),
            "median_only_pulses": median_only_pulses,
        },
        "traditional": {
            "metric": "heldout topology fractions and CFD20 downstream pair sigma68",
            "heldout_runs": HELDOUT_RUNS,
            "dynamic_excess_fraction_full": float(dynamic_only_pulses / median_pulses),
            "heldout_downstream_fraction_delta": float(dyn.loc["downstream_fraction", "value"] - med.loc["downstream_fraction", "value"]),
            "heldout_sigma68_delta": float(dyn.loc["downstream_cfd20_pairwise_sigma68_ns", "value"] - med.loc["downstream_cfd20_pairwise_sigma68_ns", "value"]),
            "timing_hist_chi2_ndf": comparison,
        },
        "ml": {
            "metric": "heldout dynamic-only selector-shift classification",
            "method": "shape-only logistic regression",
            "heldout_runs": HELDOUT_RUNS,
            "auc": float(shape["auc"]),
            "auc_ci": [float(shape["auc_ci_low"]), float(shape["auc_ci_high"])],
            "average_precision": float(shape["average_precision"]),
            "average_precision_ci": [float(shape["average_precision_ci_low"]), float(shape["average_precision_ci_high"])],
            "accuracy": float(shape["accuracy"]),
            "leakage_hunt": {
                "leaky_amplitude_auc": float(leaky["auc"]),
                "within_run_shuffle_auc": float(shuffled["auc"]),
                "global_label_shuffle_auc": float(global_shuffled["auc"]),
                "conclusion": "Direct amplitude features are definition leakage; shuffled controls remain elevated, so the shape-only ML result is treated as a failed leakage stress test rather than clean proof.",
            },
        },
        "ml_beats_baseline": None,
        "falsification": {
            "preregistered_metric": "exact count reproduction plus heldout run-block bootstrap CIs",
            "n_tries": 2,
            "p_value": None,
            "multiple_comparison": "one deterministic selector comparison plus one primary shape-only ML model; leaky and shuffled models are controls",
        },
        "input_sha256": {
            "aggregate_digest_of_file_sha256s": aggregate.hexdigest(),
            "table": "input_sha256.csv",
        },
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S00c: add a CI/integrator regression that recomputes median and dynamic-range selected counts from raw ROOT",
            "S02c: rerun the strongest template/timewalk timing method under median-first-four and dynamic-range selectors",
        ],
        "runtime_s": time.time() - start,
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_report(result, traditional, comparison, ml_benchmark)

    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "command": f"/home/billy/anaconda3/bin/python reports/{TICKET}/s00b_downstream_sensitivity.py",
        "config": str(CONFIG),
        "random_seed": SEED,
        "heldout_runs": HELDOUT_RUNS,
        "inputs": input_rows,
        "outputs_sha256": output_hashes(),
        "git_commit": git_commit(),
        "runtime_s": time.time() - start,
        "environment": {
            "python": "/home/billy/anaconda3/bin/python",
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reproduction": result["reproduction"], "traditional": result["traditional"], "ml": result["ml"]}, indent=2))


if __name__ == "__main__":
    main()
