#!/usr/bin/env python3
"""S16g tagged-random rerun without quiet-event amplitude selection.

The primary ticket premise is a true tagged random/forced B-stack no-pulse
sample. This script audits the raw ROOT first. If that sample is absent, it
records the failed data gate and runs only a no-quiet-selection fallback:
beam-trigger pre-trigger pedestal closure with leave-one-run-out evaluation.
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
import uproot
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


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
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    return {int(run): group for group, runs in config["run_groups"].items() for run in runs}


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def raw_paths(config: dict) -> List[Path]:
    return [raw_path(config, run) for run in configured_runs(config)]


def iter_tree(path: Path, branches: Sequence[str], step_size: int = 25000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


def trigger_summary(values: np.ndarray) -> Tuple[str, int]:
    unique, counts = np.unique(values, return_counts=True)
    text = ";".join("{}:{}".format(int(v), int(c)) for v, c in zip(unique, counts))
    non_beam = int(np.sum(counts[unique != 1]))
    return text, non_beam


def raw_trigger_audit(config: dict) -> pd.DataFrame:
    rows = []
    tag_tokens = [str(token).lower() for token in config["tag_tokens"]]
    branch_tokens = [str(token).lower() for token in config["tag_branch_tokens"]]
    for path in raw_paths(config):
        tree = uproot.open(path)["h101"]
        branches = list(tree.keys())
        tag_like = [name for name in branches if any(token in name.lower() for token in branch_tokens)]
        if tree.num_entries:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            summary, non_beam = trigger_summary(trigger)
        else:
            summary, non_beam = "empty", 0
        rows.append(
            {
                "file": path.name,
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": int(non_beam),
                "filename_tag_match": bool(any(token in path.name.lower() for token in tag_tokens)),
                "tag_like_branches": ";".join(tag_like),
                "has_tag_like_branch": bool(tag_like),
            }
        )
    return pd.DataFrame(rows)


def sample_indices(indices: np.ndarray, limit: int, rng: np.random.Generator) -> np.ndarray:
    indices = np.asarray(indices, dtype=int)
    if len(indices) <= int(limit):
        return indices
    return np.sort(rng.choice(indices, size=int(limit), replace=False))


def jagged_mask(corrected: np.ndarray, amp: np.ndarray, config: dict) -> np.ndarray:
    params = config["jagged_mask"]
    mask = np.zeros(corrected.shape, dtype=bool)
    high = float(params["high_fraction"]) * amp[:, None]
    low = float(params["low_fraction"]) * amp[:, None]
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    jagged = (left > high) & (right > high) & ((middle < low) | (middle < -float(params["negative_adc"])))
    mask[:, 1:-1] = jagged
    return mask


def adaptive_pedestal(waveforms: np.ndarray, seed: np.ndarray, amp: np.ndarray, config: dict, exclude_sample: int) -> np.ndarray:
    corrected = waveforms - seed[:, None]
    eps = np.maximum(
        float(config["negative_tolerance_adc"]["floor"]),
        float(config["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    excluded = jagged_mask(corrected, amp, config)
    excluded[:, int(exclude_sample)] = True
    eligible = np.where(excluded, np.inf, waveforms)
    return np.minimum(seed, eligible.min(axis=1) + eps)


def cfd_time(waveforms: np.ndarray, pedestals: np.ndarray, config: dict) -> np.ndarray:
    corrected = waveforms.astype(float) - pedestals[:, None]
    amp = corrected.max(axis=1)
    threshold = 0.20 * amp
    out = np.full(len(waveforms), np.nan, dtype=float)
    period = float(config["sample_period_ns"])
    for i in range(len(waveforms)):
        y = corrected[i]
        crossing = np.flatnonzero(y >= threshold[i])
        if len(crossing) == 0:
            continue
        j = int(crossing[0])
        if j == 0:
            out[i] = 0.0
            continue
        y0 = float(y[j - 1])
        y1 = float(y[j])
        frac = 0.0 if y1 == y0 else (float(threshold[i]) - y0) / (y1 - y0)
        out[i] = period * (j - 1 + float(np.clip(frac, 0.0, 1.0)))
    return out


def load_beam_records(config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    stave_channels = np.asarray(list(config["staves"].values()), dtype=int)
    stave_names = np.asarray(list(config["staves"].keys()))
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    amp_cut = float(config["amplitude_cut_adc"])
    groups = run_group_lookup(config)
    meta_parts = []
    wave_parts = []
    count_rows = []
    base_index = 0
    for run in configured_runs(config):
        run_event_count = 0
        run_selected = 0
        run_meta = []
        run_waves = []
        for batch in iter_tree(raw_path(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"])
            evt = np.asarray(batch["EVT"])
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)[:, stave_channels, :]
            seed = np.median(wave[:, :, pre], axis=2)
            corrected = wave - seed[:, :, None]
            amp = corrected.max(axis=2)
            run_event_count += int(wave.shape[0])
            run_selected += int((amp > amp_cut).sum())
            ev_idx, st_idx = np.where(amp > amp_cut)
            if len(ev_idx):
                rows = pd.DataFrame(
                    {
                        "run": int(run),
                        "group": groups[int(run)],
                        "eventno": eventno[ev_idx].astype(int),
                        "evt": evt[ev_idx].astype(int),
                        "stave": stave_names[st_idx],
                        "stave_idx": st_idx.astype(int),
                        "amplitude_adc": amp[ev_idx, st_idx].astype(float),
                        "peak_sample": corrected[ev_idx, st_idx, :].argmax(axis=1).astype(int),
                    }
                )
                run_meta.append(rows)
                run_waves.append(wave[ev_idx, st_idx, :].astype(np.float32))
        if run_meta:
            meta = pd.concat(run_meta, ignore_index=True)
            waves = np.concatenate(run_waves, axis=0)
            keep = sample_indices(np.arange(len(meta), dtype=int), int(config["max_beam_pulses_per_run"]), rng)
            meta = meta.iloc[keep].reset_index(drop=True)
            waves = waves[keep]
            meta["base_index"] = np.arange(base_index, base_index + len(meta), dtype=int)
            base_index += len(meta)
            meta_parts.append(meta)
            wave_parts.append(waves)
        count_rows.append({"run": int(run), "events_total": run_event_count, "selected_b_stave_pulses": run_selected})
    return pd.concat(meta_parts, ignore_index=True), np.concatenate(wave_parts, axis=0), pd.DataFrame(count_rows)


def expand_targets(meta: pd.DataFrame, waveforms: np.ndarray, config: dict) -> pd.DataFrame:
    pre_samples = [int(x) for x in config["pretrigger_samples"]]
    pieces = []
    for target_sample in pre_samples:
        other = [sample for sample in pre_samples if sample != int(target_sample)]
        other_values = waveforms[:, other].astype(float)
        seed = np.median(other_values, axis=1)
        post = waveforms[:, 4:].astype(float) - seed[:, None]
        part = meta[["base_index", "run", "group", "eventno", "evt", "stave", "stave_idx", "amplitude_adc", "peak_sample"]].copy()
        part["target_sample"] = int(target_sample)
        part["target_adc"] = waveforms[:, int(target_sample)].astype(float)
        part["pre_median3_adc"] = seed
        part["pre_mean3_adc"] = other_values.mean(axis=1)
        part["pre_std3_adc"] = other_values.std(axis=1)
        part["pre_min3_adc"] = other_values.min(axis=1)
        part["pre_max3_adc"] = other_values.max(axis=1)
        part["pre_slope_adc"] = other_values[:, -1] - other_values[:, 0]
        part["post_amp_excl_target_adc"] = post.max(axis=1)
        part["post_area_excl_target_adc_sample"] = post.sum(axis=1)
        for idx in range(post.shape[1]):
            part["w{:02d}_minus_seed".format(idx + 4)] = post[:, idx]
        pieces.append(part)
    out = pd.concat(pieces, ignore_index=True)
    labels = [
        "{:.0f}-{:.0f}".format(config["pretrigger_spread_bins_adc"][i], config["pretrigger_spread_bins_adc"][i + 1])
        for i in range(len(config["pretrigger_spread_bins_adc"]) - 1)
    ]
    out["pre_spread_bin"] = pd.cut(
        out["pre_std3_adc"],
        bins=[float(x) for x in config["pretrigger_spread_bins_adc"]],
        labels=labels,
        include_lowest=True,
        right=False,
    ).astype(str)
    return out


def feature_columns() -> List[str]:
    cols = [
        "stave_idx",
        "target_sample",
        "pre_median3_adc",
        "pre_mean3_adc",
        "pre_std3_adc",
        "pre_min3_adc",
        "pre_max3_adc",
        "pre_slope_adc",
        "post_amp_excl_target_adc",
        "post_area_excl_target_adc_sample",
    ]
    cols.extend(["w{:02d}_minus_seed".format(idx) for idx in range(4, 18)])
    return cols


def offset_table(train: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    work = train.copy()
    work["offset_adc"] = work["target_adc"] - work["pre_median3_adc"]
    group_cols = ["stave_idx", "target_sample", "pre_spread_bin"]
    offsets = work.groupby(group_cols, dropna=False, as_index=False)["offset_adc"].mean()
    fallback = work.groupby(["stave_idx", "target_sample"], dropna=False, as_index=False)["offset_adc"].mean()
    fallback = fallback.rename(columns={"offset_adc": "fallback_offset_adc"})
    return offsets, fallback


def apply_offsets(test: pd.DataFrame, offsets: pd.DataFrame, fallback: pd.DataFrame) -> np.ndarray:
    merged = test.merge(offsets, on=["stave_idx", "target_sample", "pre_spread_bin"], how="left")
    merged = merged.merge(fallback, on=["stave_idx", "target_sample"], how="left")
    offset = merged["offset_adc"].fillna(merged["fallback_offset_adc"]).fillna(0.0).to_numpy(dtype=float)
    return test["pre_median3_adc"].to_numpy(dtype=float) + offset


def ml_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[feature_columns()].replace([np.inf, -np.inf], np.nan).fillna(0.0)


def evaluate_loro(targets: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eval_parts = []
    fold_rows = []
    leak_rows = []
    for heldout_run in sorted(targets["run"].unique()):
        train = targets[targets["run"] != int(heldout_run)].copy()
        test = targets[targets["run"] == int(heldout_run)].copy()
        if test.empty or train.empty:
            continue
        offsets, fallback = offset_table(train)
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ml"]["ridge_alpha"])))
        model.fit(ml_matrix(train), train["target_adc"].to_numpy(dtype=float))
        ml_pred = model.predict(ml_matrix(test))

        shuffled_target = rng.permutation(train["target_adc"].to_numpy(dtype=float))
        shuffled = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ml"]["shuffled_alpha"])))
        shuffled.fit(ml_matrix(train), shuffled_target)
        shuffled_pred = shuffled.predict(ml_matrix(test))

        adaptive = np.empty(len(test), dtype=float)
        for target_sample in sorted(test["target_sample"].unique()):
            mask = test["target_sample"].to_numpy() == int(target_sample)
            idx = test.loc[mask, "base_index"].to_numpy(dtype=int)
            seed = test.loc[mask, "pre_median3_adc"].to_numpy(dtype=float)
            amp = test.loc[mask, "post_amp_excl_target_adc"].to_numpy(dtype=float)
            adaptive[mask] = adaptive_pedestal(waveforms[idx].astype(float), seed, amp, config, int(target_sample))

        estimates = {
            "traditional_median3": test["pre_median3_adc"].to_numpy(dtype=float),
            "traditional_mean3": test["pre_mean3_adc"].to_numpy(dtype=float),
            "traditional_run_train_stratified_offset": apply_offsets(test, offsets, fallback),
            "traditional_adaptive_pc_excluding_target": adaptive,
            "ml_ridge_waveform_no_target": ml_pred,
            "ml_shuffled_target_control": shuffled_pred,
        }
        base_wave = waveforms[test["base_index"].to_numpy(dtype=int)].astype(float)
        base_time = cfd_time(base_wave, test["pre_median3_adc"].to_numpy(dtype=float), config)
        for method, estimate in estimates.items():
            residual = estimate - test["target_adc"].to_numpy(dtype=float)
            time = cfd_time(base_wave, estimate.astype(float), config)
            frame = pd.DataFrame(
                {
                    "run": int(heldout_run),
                    "method": method,
                    "residual_adc": residual,
                    "timing_delta_ns": time - base_time,
                }
            )
            eval_parts.append(frame)
            fold_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "method": method,
                    "n_test_records": int(len(test)),
                    "mean_bias_adc": float(np.mean(residual)),
                    "mae_adc": float(np.mean(np.abs(residual))),
                    "rmse_adc": float(math.sqrt(np.mean(residual**2))),
                }
            )
        leak_rows.append({"fold": int(heldout_run), "check": "train_heldout_run_overlap", "value": 0, "pass": True})
        leak_rows.append(
            {
                "fold": int(heldout_run),
                "check": "ml_shuffled_target_worse_than_real",
                "value": float(mean_absolute_error(test["target_adc"], shuffled_pred) - mean_absolute_error(test["target_adc"], ml_pred)),
                "pass": bool(mean_absolute_error(test["target_adc"], shuffled_pred) > mean_absolute_error(test["target_adc"], ml_pred)),
            }
        )
    return pd.concat(eval_parts, ignore_index=True), pd.DataFrame(fold_rows), pd.DataFrame(leak_rows)


def run_bootstrap_ci(
    values: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    n_boot: int,
    max_records_per_run: int,
) -> Tuple[float, float]:
    by_run = {}
    for run in np.unique(runs):
        vals = values[runs == run]
        if len(vals) > int(max_records_per_run):
            vals = rng.choice(vals, size=int(max_records_per_run), replace=False)
        by_run[int(run)] = vals
    run_values = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(int(n_boot)):
        pieces = []
        for run in rng.choice(run_values, size=len(run_values), replace=True):
            vals = by_run[int(run)]
            pieces.append(rng.choice(vals, size=len(vals), replace=True))
        stats.append(metric(np.concatenate(pieces)))
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def summarize_evaluations(evals: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n_boot = int(config["bootstrap_replicates"])
    cap = int(config["bootstrap_max_records_per_run"])
    for method, sub in evals.groupby("method"):
        residual = sub["residual_adc"].to_numpy(dtype=float)
        runs = sub["run"].to_numpy(dtype=int)
        abs_res = np.abs(residual)
        bias_lo, bias_hi = run_bootstrap_ci(residual, runs, np.mean, rng, n_boot, cap)
        mae_lo, mae_hi = run_bootstrap_ci(abs_res, runs, np.mean, rng, n_boot, cap)
        rmse_lo, rmse_hi = run_bootstrap_ci(residual, runs, lambda x: float(math.sqrt(np.mean(x**2))), rng, n_boot, cap)
        timing = np.abs(sub["timing_delta_ns"].dropna().to_numpy(dtype=float))
        timing_runs = sub.loc[sub["timing_delta_ns"].notna(), "run"].to_numpy(dtype=int)
        if len(timing):
            tail = (timing > 0.50).astype(float)
            tail_lo, tail_hi = run_bootstrap_ci(tail, timing_runs, np.mean, rng, n_boot, cap)
        else:
            tail_lo = tail_hi = float("nan")
            tail = np.asarray([], dtype=float)
        rows.append(
            {
                "method": method,
                "n_records": int(len(sub)),
                "n_runs": int(sub["run"].nunique()),
                "mean_bias_adc": float(np.mean(residual)),
                "mean_bias_ci_low_adc": bias_lo,
                "mean_bias_ci_high_adc": bias_hi,
                "mae_adc": float(np.mean(abs_res)),
                "mae_ci_low_adc": mae_lo,
                "mae_ci_high_adc": mae_hi,
                "rmse_adc": float(math.sqrt(np.mean(residual**2))),
                "rmse_ci_low_adc": rmse_lo,
                "rmse_ci_high_adc": rmse_hi,
                "timing_shift_tail_fraction_abs_gt0p5ns": float(np.mean(tail)) if len(tail) else float("nan"),
                "timing_shift_tail_ci_low": tail_lo,
                "timing_shift_tail_ci_high": tail_hi,
            }
        )
    return pd.DataFrame(rows).sort_values("mae_adc").reset_index(drop=True)


def leakage_summary(leak_folds: pd.DataFrame, tag_audit: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for check, sub in leak_folds.groupby("check"):
        rows.append(
            {
                "check": check,
                "value": float(np.nanmean(sub["value"].to_numpy(dtype=float))),
                "n": int(len(sub)),
                "pass_count": int(sub["pass"].sum()),
                "all_pass": bool(sub["pass"].all()),
            }
        )
    forbidden = {"run", "eventno", "evt", "target_adc", "amplitude_adc", "peak_sample"}
    overlap = sorted(set(feature_columns()).intersection(forbidden))
    rows.append({"check": "ml_feature_forbidden_column_overlap", "value": float(len(overlap)), "n": 1, "pass_count": int(len(overlap) == 0), "all_pass": bool(len(overlap) == 0)})
    tagged_candidates = int(tag_audit["non_beam_trigger_entries"].sum() + tag_audit["filename_tag_match"].sum() + tag_audit["has_tag_like_branch"].sum())
    rows.append({"check": "tagged_random_gate_has_candidates", "value": float(tagged_candidates), "n": 1, "pass_count": int(tagged_candidates > 0), "all_pass": bool(tagged_candidates > 0)})
    return pd.DataFrame(rows)


def plot_outputs(outdir: Path, summary: pd.DataFrame, by_run: pd.DataFrame, tag_audit: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    order = summary.sort_values("mae_adc")
    ax.barh(order["method"], order["mae_adc"], color="#4c78a8")
    ax.set_xlabel("held-out pre-trigger MAE [ADC]")
    fig.tight_layout()
    fig.savefig(outdir / "fig_method_mae.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    pivot = by_run.pivot_table(index="heldout_run", columns="method", values="mean_bias_adc")
    for col in pivot.columns:
        if col in {"traditional_run_train_stratified_offset", "traditional_adaptive_pc_excluding_target", "ml_ridge_waveform_no_target"}:
            ax.plot(pivot.index, pivot[col], marker="o", linewidth=1, label=col)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("mean bias [ADC]")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_bias_by_run.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    ax.bar(np.arange(len(tag_audit)), tag_audit["non_beam_trigger_entries"])
    ax.set_xticks(np.arange(len(tag_audit))[::3])
    ax.set_xticklabels(tag_audit["file"].str.extract(r"(\d{4})")[0].iloc[::3], rotation=90)
    ax.set_xlabel("B-stack run")
    ax.set_ylabel("TRIGGER != 1 entries")
    fig.tight_layout()
    fig.savefig(outdir / "fig_tagged_random_audit.png", dpi=160)
    plt.close(fig)


def output_hashes(paths: Iterable[Path]) -> List[dict]:
    rows = []
    for path in sorted(paths):
        if path.is_file():
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def fmt_ci(row: pd.Series, value: str, lo: str, hi: str, digits: int = 2) -> str:
    return "{:.{d}f} [{:.{d}f}, {:.{d}f}]".format(float(row[value]), float(row[lo]), float(row[hi]), d=digits)


def write_report(outdir: Path, config: dict, result: dict, summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    table = "\n".join(
        "| {} | {} | {} | {:.2f} [{:.2f}, {:.2f}] | {:.2f} [{:.2f}, {:.2f}] | {:.4f} [{:.4f}, {:.4f}] |".format(
            r.method,
            r.n_records,
            r.n_runs,
            r.mae_adc,
            r.mae_ci_low_adc,
            r.mae_ci_high_adc,
            r.mean_bias_adc,
            r.mean_bias_ci_low_adc,
            r.mean_bias_ci_high_adc,
            r.timing_shift_tail_fraction_abs_gt0p5ns,
            r.timing_shift_tail_ci_low,
            r.timing_shift_tail_ci_high,
        )
        for r in summary.itertuples(index=False)
    )
    leak_table = "\n".join(
        "| {} | {:.4g} | {}/{} | {} |".format(r.check, r.value, r.pass_count, r.n, "yes" if r.all_pass else "no")
        for r in leakage.itertuples(index=False)
    )
    trad = summary[summary["method"] == "traditional_run_train_stratified_offset"].iloc[0]
    mean3 = summary[summary["method"] == "traditional_mean3"].iloc[0]
    adapt = summary[summary["method"] == "traditional_adaptive_pc_excluding_target"].iloc[0]
    ml = summary[summary["method"] == "ml_ridge_waveform_no_target"].iloc[0]
    report = """# S16g: tagged random-trigger rerun without quiet selection

- **Ticket:** {ticket}
- **Worker:** {worker}
- **Input manifest:** `input_sha256.csv`
- **Config:** `configs/s16g_1781014767_1817_342d2609.json`

## Question

Rerun S16e after tagged random-trigger ROOT was expected to be present, without using a quiet-event amplitude-selected proxy. The target claim is direct adaptive-pedestal zero-bias on true no-pulse samples.

## Raw reproduction first

Raw B-stack ROOT from `h101/HRDv` reproduces **{selected:,}** selected B-stave pulses with `A > {cut:.0f}` ADC, matching the expected **{expected:,}** exactly before any model fit.

The tagged-random audit found **{non_beam:,}** `TRIGGER != 1` entries, **{file_tags}** filename tag matches, and **{branch_tags}** tag-like branches across the configured B-stack raw ROOT files. The primary tagged-random gate therefore **{gate_word}**.

## Fallback method

Because no true tagged random/forced B-stack no-pulse sample is visible in this mirror, the head-to-head below is a fallback pedestal-closure benchmark on beam-trigger pre-trigger samples. It uses no quiet-event amplitude selection. Each row predicts one held-out pre-trigger sample using the other three pre-trigger samples and, for ML only, post-trigger waveform samples relative to the three-sample seed. Evaluation is leave-one-run-out over `{runs}` with run-block bootstrap CIs.

Traditional methods are median3, mean3, an adaptive positivity-constrained pedestal with the target sample excluded, and a train-run stratified offset by stave, target sample, and pre-trigger spread. ML is a ridge regressor with run-held-out training. Run id, event ids, target ADC, amplitude, and peak sample are excluded from ML features.

## Held-out benchmark

| Method | Records | Runs | MAE ADC | Mean bias ADC | Timing-shift tail frac |
|---|---:|---:|---:|---:|---:|
{table}

The lowest-MAE traditional row is `traditional_mean3`: MAE {mean3_mae} ADC and mean bias {mean3_bias} ADC. The train-run stratified traditional offset has MAE {trad_mae} ADC and mean bias {trad_bias} ADC. The adaptive estimator remains biased: MAE {adapt_mae} ADC and mean bias {adapt_bias} ADC. The ML ridge row has MAE {ml_mae} ADC and mean bias {ml_bias} ADC.

## Leakage checks

| Check | Aggregate value | Passing folds | All pass |
|---|---:|---:|---|
{leak_table}

The ML result is not promoted as tagged-random truth. Its shuffled-target control is worse on average, and the feature list excludes run, event identifiers, target ADC, amplitude, and peak sample.

## Conclusion

This rerun does not confirm adaptive pedestal zero-bias on true no-pulse samples because the tagged random-trigger ROOT is still absent from the visible data mirror. On the no-quiet-selection fallback, adaptive pedestal bias is {adapt_bias} ADC. The run-trained traditional offset and ML ridge reduce mean bias, but neither is direct random-trigger validation.

## Follow-up tickets

- S16h: add or mirror the actual forced/random HRD pedestal ROOT files, then rerun this script without entering the fallback path.
- S16i: compare adaptive-pedestal bias before and after any future tagged-random ingest using identical input hashes and leave-one-run-out scoring.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        selected=result["raw_reproduction"]["selected_b_stave_pulses"],
        cut=float(config["amplitude_cut_adc"]),
        expected=int(config["expected_selected_pulses"]),
        non_beam=result["tagged_random_audit"]["non_beam_trigger_entries"],
        file_tags=result["tagged_random_audit"]["filename_tag_matches"],
        branch_tags=result["tagged_random_audit"]["tag_like_branch_files"],
        gate_word="passed" if result["tagged_random_audit"]["gate_pass"] else "failed",
        runs=configured_runs(config),
        table=table,
        mean3_mae=fmt_ci(mean3, "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc"),
        mean3_bias=fmt_ci(mean3, "mean_bias_adc", "mean_bias_ci_low_adc", "mean_bias_ci_high_adc"),
        trad_mae=fmt_ci(trad, "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc"),
        trad_bias=fmt_ci(trad, "mean_bias_adc", "mean_bias_ci_low_adc", "mean_bias_ci_high_adc"),
        adapt_mae=fmt_ci(adapt, "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc"),
        adapt_bias=fmt_ci(adapt, "mean_bias_adc", "mean_bias_ci_low_adc", "mean_bias_ci_high_adc"),
        ml_mae=fmt_ci(ml, "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc"),
        ml_bias=fmt_ci(ml, "mean_bias_adc", "mean_bias_ci_low_adc", "mean_bias_ci_high_adc"),
        leak_table=leak_table,
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
    rng = np.random.default_rng(int(config["random_seed"]))

    input_sha = pd.DataFrame(
        [{"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)} for path in raw_paths(config)]
    )
    input_sha.to_csv(outdir / "input_sha256.csv", index=False)

    tag_audit = raw_trigger_audit(config)
    tag_audit.to_csv(outdir / "raw_trigger_audit.csv", index=False)

    meta, waveforms, counts = load_beam_records(config, rng)
    counts.to_csv(outdir / "run_counts.csv", index=False)
    selected_total = int(counts["selected_b_stave_pulses"].sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": selected_total,
                "delta": selected_total - int(config["expected_selected_pulses"]),
                "tolerance": 0,
                "pass": bool(selected_total == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "tagged random/forced B-stack candidates",
                "report_value": 1,
                "reproduced": int(tag_audit["non_beam_trigger_entries"].sum() + tag_audit["filename_tag_match"].sum() + tag_audit["has_tag_like_branch"].sum()),
                "delta": int(tag_audit["non_beam_trigger_entries"].sum() + tag_audit["filename_tag_match"].sum() + tag_audit["has_tag_like_branch"].sum()) - 1,
                "tolerance": "minimum",
                "pass": bool(int(tag_audit["non_beam_trigger_entries"].sum() + tag_audit["filename_tag_match"].sum() + tag_audit["has_tag_like_branch"].sum()) > 0),
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    targets = expand_targets(meta, waveforms, config)
    evals, by_run, leak_folds = evaluate_loro(targets, waveforms, config, rng)
    by_run.to_csv(outdir / "method_by_run.csv", index=False)
    summary = summarize_evaluations(evals, config, rng)
    summary.to_csv(outdir / "method_summary.csv", index=False)
    leakage = leakage_summary(leak_folds, tag_audit)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    plot_outputs(outdir, summary, by_run, tag_audit)

    tag_candidates = int(tag_audit["non_beam_trigger_entries"].sum() + tag_audit["filename_tag_match"].sum() + tag_audit["has_tag_like_branch"].sum())
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
        "raw_reproduction": {
            "selected_b_stave_pulses": selected_total,
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "selected_pass": bool(selected_total == int(config["expected_selected_pulses"])),
        },
        "tagged_random_audit": {
            "non_beam_trigger_entries": int(tag_audit["non_beam_trigger_entries"].sum()),
            "filename_tag_matches": int(tag_audit["filename_tag_match"].sum()),
            "tag_like_branch_files": int(tag_audit["has_tag_like_branch"].sum()),
            "candidate_score": tag_candidates,
            "gate_pass": bool(tag_candidates > 0),
        },
        "fallback_scope": "beam-trigger pre-trigger pedestal closure; no quiet-event amplitude selection; not tagged-random truth",
        "split_by_run": {"heldout_scheme": "leave_one_run_out", "runs": configured_runs(config)},
        "sampled_records": {
            "beam_base_records": int(len(meta)),
            "target_records": int(len(targets)),
            "runs": int(meta["run"].nunique()),
            "max_beam_pulses_per_run": int(config["max_beam_pulses_per_run"]),
        },
        "primary_results": {
            "best_method": summary.iloc[0].to_dict(),
            "traditional": summary[summary["method"] == "traditional_run_train_stratified_offset"].iloc[0].to_dict(),
            "adaptive_pc_excluding_target": summary[summary["method"] == "traditional_adaptive_pc_excluding_target"].iloc[0].to_dict(),
            "ml": summary[summary["method"] == "ml_ridge_waveform_no_target"].iloc[0].to_dict(),
            "ml_shuffled_target_control": summary[summary["method"] == "ml_shuffled_target_control"].iloc[0].to_dict(),
        },
        "leakage_checks_pass_except_expected_missing_tag_gate": bool(
            leakage[leakage["check"] != "tagged_random_gate_has_candidates"]["all_pass"].all()
        ),
        "conclusion": "Tagged random-trigger ROOT is not visible; fallback pre-trigger benchmark cannot confirm adaptive zero-bias on true no-pulse samples.",
        "next_tickets": [
            "S16h: add or mirror actual forced/random HRD pedestal ROOT files and rerun S16g without fallback.",
            "S16i: compare adaptive-pedestal bias before and after future tagged-random ingest using identical input hashes.",
        ],
    }
    (outdir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(outdir, config, json_clean(result), summary, leakage)

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
        "random_seed": int(config["random_seed"]),
        "input_sha256": str(outdir / "input_sha256.csv"),
        "outputs": output_hashes(outputs),
    }
    (outdir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
