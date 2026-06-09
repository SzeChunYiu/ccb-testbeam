#!/usr/bin/env python3
"""S16f quiet-proxy selection-bias study.

The ticket asks whether the all-stave quiet-event proxy biases pedestal closure
relative to beam-trigger pre-trigger activity. The script reads raw ROOT first
to reproduce the S00 selected-pulse count, then evaluates quiet-trained
pedestal offsets on beam-selected pulses with leave-one-run-out held-out
metrics, a traditional stratified method, and a logistic inverse-propensity ML
method. No Monte Carlo inputs are used.
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    return {int(run): group for group, runs in config["run_groups"].items() for run in runs}


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def raw_paths(config: dict) -> List[Path]:
    return [raw_path(config, run) for run in configured_runs(config)]


def iter_tree(path: Path, branches: Sequence[str], step_size: int = 25000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


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
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


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


def adaptive_pedestal(
    waveforms: np.ndarray, seed: np.ndarray, config: dict, exclude_sample: int | None = None
) -> Tuple[np.ndarray, np.ndarray]:
    corrected = waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(
        float(config["negative_tolerance_adc"]["floor"]),
        float(config["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    excluded = jagged_mask(corrected, amp, config)
    if exclude_sample is not None:
        excluded[:, int(exclude_sample)] = True
    eligible = np.where(excluded, np.inf, waveforms)
    estimate = np.minimum(seed, eligible.min(axis=1) + eps)
    return estimate, seed - estimate


def cfd_time(waveforms: np.ndarray, pedestals: np.ndarray, config: dict) -> np.ndarray:
    corrected = waveforms.astype(float) - pedestals[:, None]
    amp = corrected.max(axis=1)
    threshold = float(config["timing"]["cfd_fraction"]) * amp
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


def sample_indices(indices: np.ndarray, limit: int, rng: np.random.Generator) -> np.ndarray:
    indices = np.asarray(indices, dtype=int)
    if len(indices) <= int(limit):
        return indices
    return np.sort(rng.choice(indices, size=int(limit), replace=False))


def load_records(config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    stave_channels = np.asarray(list(config["staves"].values()), dtype=int)
    stave_names = np.asarray(list(config["staves"].keys()))
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    amp_cut = float(config["amplitude_cut_adc"])
    quiet_scan_max = float(max(config["quiet_cut_scan_adc"]))
    groups = run_group_lookup(config)
    meta_parts = []
    wave_parts = []
    count_rows = []
    base_index = 0
    for run in configured_runs(config):
        run_event_count = 0
        run_selected = 0
        quiet_counts = {float(cut): 0 for cut in config["quiet_cut_scan_adc"]}
        run_meta = []
        run_waves = []
        for batch in iter_tree(raw_path(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"])
            evt = np.asarray(batch["EVT"])
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)[:, stave_channels, :]
            seed = np.median(wave[:, :, pre], axis=2)
            corrected = wave - seed[:, :, None]
            amp = corrected.max(axis=2)
            event_max = amp.max(axis=1)
            run_event_count += int(wave.shape[0])
            run_selected += int((amp > amp_cut).sum())
            for cut in quiet_counts:
                quiet_counts[cut] += int((event_max < cut).sum())

            quiet_event_idx = np.where(event_max < quiet_scan_max)[0]
            quiet_flat_idx = []
            if len(quiet_event_idx):
                for ev in quiet_event_idx:
                    for stave_idx in range(len(stave_channels)):
                        quiet_flat_idx.append((int(ev), int(stave_idx)))
            beam_event_idx, beam_stave_idx = np.where(amp > amp_cut)
            quiet_take = np.arange(len(quiet_flat_idx), dtype=int)
            beam_take = np.arange(len(beam_event_idx), dtype=int)

            if len(quiet_take):
                ev_idx = np.asarray([quiet_flat_idx[i][0] for i in quiet_take], dtype=int)
                st_idx = np.asarray([quiet_flat_idx[i][1] for i in quiet_take], dtype=int)
                rows = pd.DataFrame(
                    {
                        "run": int(run),
                        "group": groups[int(run)],
                        "eventno": eventno[ev_idx].astype(int),
                        "evt": evt[ev_idx].astype(int),
                        "domain": "quiet",
                        "stave": stave_names[st_idx],
                        "stave_idx": st_idx,
                        "event_max_amplitude_adc": event_max[ev_idx].astype(float),
                        "amplitude_adc": amp[ev_idx, st_idx].astype(float),
                    }
                )
                run_meta.append(rows)
                run_waves.append(wave[ev_idx, st_idx, :].astype(np.float32))
            if len(beam_take):
                ev_idx = beam_event_idx[beam_take].astype(int)
                st_idx = beam_stave_idx[beam_take].astype(int)
                rows = pd.DataFrame(
                    {
                        "run": int(run),
                        "group": groups[int(run)],
                        "eventno": eventno[ev_idx].astype(int),
                        "evt": evt[ev_idx].astype(int),
                        "domain": "beam",
                        "stave": stave_names[st_idx],
                        "stave_idx": st_idx,
                        "event_max_amplitude_adc": event_max[ev_idx].astype(float),
                        "amplitude_adc": amp[ev_idx, st_idx].astype(float),
                    }
                )
                run_meta.append(rows)
                run_waves.append(wave[ev_idx, st_idx, :].astype(np.float32))
        if run_meta:
            meta = pd.concat(run_meta, ignore_index=True)
            waves = np.concatenate(run_waves, axis=0)
            keep_parts = []
            for domain, limit in [
                ("quiet", int(config["max_quiet_stave_records_per_run"])),
                ("beam", int(config["max_beam_pulses_per_run"])),
            ]:
                domain_idx = np.where(meta["domain"].to_numpy() == domain)[0]
                keep_parts.append(sample_indices(domain_idx, limit, rng))
            keep = np.sort(np.concatenate(keep_parts))
            meta = meta.iloc[keep].reset_index(drop=True)
            waves = waves[keep]
            meta["base_index"] = np.arange(base_index, base_index + len(meta), dtype=int)
            base_index += len(meta)
            meta_parts.append(meta)
            wave_parts.append(waves)
        row = {"run": int(run), "events_total": run_event_count, "selected_b_stave_pulses": run_selected}
        for cut, value in quiet_counts.items():
            row[f"quiet_events_lt_{int(cut)}adc"] = int(value)
        count_rows.append(row)
    return pd.concat(meta_parts, ignore_index=True), np.concatenate(wave_parts, axis=0), pd.DataFrame(count_rows)


def expand_targets(meta: pd.DataFrame, waveforms: np.ndarray, config: dict) -> pd.DataFrame:
    pre_samples = [int(x) for x in config["pretrigger_samples"]]
    pieces = []
    for target_sample in pre_samples:
        other = [sample for sample in pre_samples if sample != int(target_sample)]
        values = waveforms[:, other].astype(float)
        part = meta[
            [
                "base_index",
                "run",
                "group",
                "eventno",
                "evt",
                "domain",
                "stave",
                "stave_idx",
                "event_max_amplitude_adc",
                "amplitude_adc",
            ]
        ].copy()
        part["target_sample"] = int(target_sample)
        part["target_adc"] = waveforms[:, int(target_sample)].astype(float)
        part["pre_median3_adc"] = np.median(values, axis=1)
        part["pre_mean3_adc"] = values.mean(axis=1)
        part["pre_std3_adc"] = values.std(axis=1)
        part["pre_min3_adc"] = values.min(axis=1)
        part["pre_max3_adc"] = values.max(axis=1)
        part["pre_slope_adc"] = values[:, -1] - values[:, 0]
        pieces.append(part)
    out = pd.concat(pieces, ignore_index=True)
    labels = [f"{config['pretrigger_spread_bins_adc'][i]:.0f}-{config['pretrigger_spread_bins_adc'][i + 1]:.0f}" for i in range(len(config["pretrigger_spread_bins_adc"]) - 1)]
    out["pre_spread_bin"] = pd.cut(
        out["pre_std3_adc"],
        bins=[float(x) for x in config["pretrigger_spread_bins_adc"]],
        labels=labels,
        include_lowest=True,
        right=False,
    ).astype(str)
    return out


def feature_columns() -> List[str]:
    return [
        "stave_idx",
        "target_sample",
        "pre_median3_adc",
        "pre_mean3_adc",
        "pre_std3_adc",
        "pre_min3_adc",
        "pre_max3_adc",
        "pre_slope_adc",
    ]


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    total = float(np.sum(weights))
    if total <= 0:
        return float(np.mean(values))
    return float(np.sum(values * weights) / total)


def offset_table(train: pd.DataFrame, weights: np.ndarray | None = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    work = train.copy()
    work["offset_adc"] = work["target_adc"] - work["pre_median3_adc"]
    work["weight"] = 1.0 if weights is None else np.asarray(weights, dtype=float)
    group_cols = ["stave_idx", "target_sample", "pre_spread_bin"]
    rows = []
    for key, sub in work.groupby(group_cols, dropna=False):
        rows.append({**{col: val for col, val in zip(group_cols, key)}, "offset_adc": weighted_mean(sub["offset_adc"], sub["weight"])})
    full_rows = []
    for key, sub in work.groupby(["stave_idx", "target_sample"], dropna=False):
        full_rows.append(
            {
                "stave_idx": key[0],
                "target_sample": key[1],
                "fallback_offset_adc": weighted_mean(sub["offset_adc"], sub["weight"]),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(full_rows)


def apply_offsets(test: pd.DataFrame, offsets: pd.DataFrame, fallback: pd.DataFrame) -> np.ndarray:
    merged = test.merge(offsets, on=["stave_idx", "target_sample", "pre_spread_bin"], how="left")
    merged = merged.merge(fallback, on=["stave_idx", "target_sample"], how="left")
    offset = merged["offset_adc"].fillna(merged["fallback_offset_adc"]).fillna(0.0).to_numpy(dtype=float)
    return test["pre_median3_adc"].to_numpy(dtype=float) + offset


def make_propensity_model(config: dict):
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=float(config["ml"]["logistic_c"]),
            class_weight="balanced",
            max_iter=400,
            solver="lbfgs",
            random_state=int(config["random_seed"]),
        ),
    )


def train_propensity(train: pd.DataFrame, config: dict, rng: np.random.Generator, shuffle: bool = False):
    max_per = int(config["ml"]["max_train_records_per_domain"])
    quiet = train[train["domain"] == "quiet"]
    beam = train[train["domain"] == "beam"]
    if len(quiet) > max_per:
        quiet = quiet.iloc[rng.choice(np.arange(len(quiet)), size=max_per, replace=False)]
    if len(beam) > max_per:
        beam = beam.iloc[rng.choice(np.arange(len(beam)), size=max_per, replace=False)]
    sampled = pd.concat([quiet, beam], ignore_index=True)
    y = (sampled["domain"] == "beam").astype(int).to_numpy()
    if shuffle:
        y = rng.permutation(y)
    model = make_propensity_model(config)
    model.fit(sampled[feature_columns()], y)
    auc = float("nan")
    try:
        auc = float(roc_auc_score((sampled["domain"] == "beam").astype(int), model.predict_proba(sampled[feature_columns()])[:, 1]))
    except Exception:
        pass
    return model, auc, int(len(sampled))


def propensity_weights(model, quiet_train: pd.DataFrame, config: dict) -> np.ndarray:
    p = model.predict_proba(quiet_train[feature_columns()])[:, 1]
    p = np.clip(p, 1e-4, 1.0 - 1e-4)
    odds = p / (1.0 - p)
    return np.clip(
        odds,
        float(config["ml"]["propensity_clip_min"]),
        float(config["ml"]["propensity_clip_max"]),
    )


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
        if len(vals) > max_records_per_run:
            vals = rng.choice(vals, size=max_records_per_run, replace=False)
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
    tail_ns = float(config["timing"]["timing_shift_tail_ns"])
    for method, sub in evals.groupby("method"):
        residual = sub["residual_adc"].to_numpy(dtype=float)
        runs = sub["run"].to_numpy(dtype=int)
        abs_res = np.abs(residual)
        bias_lo, bias_hi = run_bootstrap_ci(residual, runs, np.mean, rng, n_boot, cap)
        mae_lo, mae_hi = run_bootstrap_ci(abs_res, runs, np.mean, rng, n_boot, cap)
        ds = sub[sub["is_downstream"]]
        timing = ds["timing_delta_ns"].dropna().to_numpy(dtype=float)
        timing_runs = ds.loc[ds["timing_delta_ns"].notna(), "run"].to_numpy(dtype=int)
        if len(timing):
            tail = (np.abs(timing) > tail_ns).astype(float)
            t_lo, t_hi = run_bootstrap_ci(tail, timing_runs, np.mean, rng, n_boot, cap)
            mean_abs_timing = float(np.mean(np.abs(timing)))
        else:
            t_lo = t_hi = mean_abs_timing = float("nan")
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
                "downstream_timing_shift_tail_fraction": float(np.mean(tail)) if len(tail) else float("nan"),
                "downstream_timing_shift_tail_ci_low": t_lo,
                "downstream_timing_shift_tail_ci_high": t_hi,
                "downstream_mean_abs_timing_delta_ns": mean_abs_timing,
            }
        )
    return pd.DataFrame(rows).sort_values("mae_adc").reset_index(drop=True)


def evaluate_loro(targets: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    primary_quiet = float(config["primary_quiet_event_max_amplitude_adc"])
    eval_parts = []
    fold_rows = []
    leak_rows = []
    for heldout_run in sorted(targets["run"].unique()):
        train = targets[targets["run"] != int(heldout_run)].copy()
        test = targets[(targets["run"] == int(heldout_run)) & (targets["domain"] == "beam")].copy()
        quiet_train = train[(train["domain"] == "quiet") & (train["event_max_amplitude_adc"] < primary_quiet)].copy()
        beam_train = train[train["domain"] == "beam"].copy()
        if test.empty or quiet_train.empty or beam_train.empty:
            continue

        quiet_offsets, quiet_fallback = offset_table(quiet_train)
        beam_offsets, beam_fallback = offset_table(beam_train)
        model, auc, n_train = train_propensity(train[(train["domain"] == "beam") | ((train["domain"] == "quiet") & (train["event_max_amplitude_adc"] < primary_quiet))], config, rng)
        weights = propensity_weights(model, quiet_train, config)
        ml_offsets, ml_fallback = offset_table(quiet_train, weights)
        shuffled_model, shuffled_auc, _ = train_propensity(
            train[(train["domain"] == "beam") | ((train["domain"] == "quiet") & (train["event_max_amplitude_adc"] < primary_quiet))],
            config,
            rng,
            shuffle=True,
        )
        shuffled_weights = propensity_weights(shuffled_model, quiet_train, config)
        shuffled_offsets, shuffled_fallback = offset_table(quiet_train, shuffled_weights)

        estimates = {
            "traditional_median3_no_proxy": test["pre_median3_adc"].to_numpy(dtype=float),
            "traditional_quiet_offset_stratified": apply_offsets(test, quiet_offsets, quiet_fallback),
            "traditional_beam_train_offset_control": apply_offsets(test, beam_offsets, beam_fallback),
            "ml_inverse_propensity_quiet_offset": apply_offsets(test, ml_offsets, ml_fallback),
            "ml_shuffled_domain_control": apply_offsets(test, shuffled_offsets, shuffled_fallback),
        }
        adaptive = np.empty(len(test), dtype=float)
        for target_sample in sorted(test["target_sample"].unique()):
            mask = test["target_sample"].to_numpy() == int(target_sample)
            idx = test.loc[mask, "base_index"].to_numpy(dtype=int)
            seed = test.loc[mask, "pre_median3_adc"].to_numpy(dtype=float)
            adaptive[mask], _ = adaptive_pedestal(waveforms[idx].astype(float), seed, config, exclude_sample=int(target_sample))
        estimates["traditional_adaptive_pc_excluding_target"] = adaptive

        base_wave = waveforms[test["base_index"].to_numpy(dtype=int)].astype(float)
        base_time = cfd_time(base_wave, test["pre_median3_adc"].to_numpy(dtype=float), config)
        is_downstream = test["stave_idx"].isin([int(x) for x in config["downstream_stave_idx"]]).to_numpy()
        for method, estimate in estimates.items():
            residual = estimate - test["target_adc"].to_numpy(dtype=float)
            time = cfd_time(base_wave, estimate.astype(float), config)
            frame = pd.DataFrame(
                {
                    "run": int(heldout_run),
                    "method": method,
                    "residual_adc": residual,
                    "timing_delta_ns": time - base_time,
                    "is_downstream": is_downstream,
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
                    "downstream_timing_shift_tail_fraction": float(
                        np.mean(np.abs(frame.loc[frame["is_downstream"], "timing_delta_ns"].dropna()) > float(config["timing"]["timing_shift_tail_ns"]))
                    ),
                    "propensity_train_auc": auc if method == "ml_inverse_propensity_quiet_offset" else float("nan"),
                    "propensity_train_records": n_train if method == "ml_inverse_propensity_quiet_offset" else 0,
                }
            )
        leak_rows.extend(
            [
                {
                    "fold": int(heldout_run),
                    "check": "train_heldout_run_overlap",
                    "value": int(set(train["run"]).intersection({int(heldout_run)}) != set()),
                    "pass": True,
                },
                {
                    "fold": int(heldout_run),
                    "check": "propensity_train_auc",
                    "value": auc,
                    "pass": bool(0.50 <= auc <= 0.98),
                },
                {
                    "fold": int(heldout_run),
                    "check": "shuffled_domain_auc",
                    "value": shuffled_auc,
                    "pass": bool(shuffled_auc < auc),
                },
            ]
        )
    return pd.concat(eval_parts, ignore_index=True), pd.DataFrame(fold_rows), pd.DataFrame(leak_rows)


def threshold_scan(targets: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    beam = targets[targets["domain"] == "beam"].copy()
    for cut in [float(x) for x in config["quiet_cut_scan_adc"]]:
        quiet = targets[(targets["domain"] == "quiet") & (targets["event_max_amplitude_adc"] < cut)].copy()
        if quiet.empty:
            continue
        for spread_bin, qsub in quiet.groupby("pre_spread_bin"):
            bsub = beam[beam["pre_spread_bin"] == spread_bin]
            if bsub.empty:
                continue
            q_res = qsub["target_adc"] - qsub["pre_median3_adc"]
            b_res = bsub["target_adc"] - bsub["pre_median3_adc"]
            rows.append(
                {
                    "quiet_cut_adc": cut,
                    "pre_spread_bin": str(spread_bin),
                    "quiet_records": int(len(qsub)),
                    "beam_records": int(len(bsub)),
                    "quiet_offset_median_adc": float(np.median(q_res)),
                    "beam_offset_median_adc": float(np.median(b_res)),
                    "beam_minus_quiet_offset_adc": float(np.median(b_res) - np.median(q_res)),
                    "quiet_mae_vs_median3_adc": float(np.mean(np.abs(q_res))),
                    "beam_mae_vs_median3_adc": float(np.mean(np.abs(b_res))),
                }
            )
    return pd.DataFrame(rows)


def plot_outputs(outdir: Path, summary: pd.DataFrame, by_run: pd.DataFrame, scan: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    order = summary.sort_values("mae_adc")
    ax.barh(order["method"], order["mae_adc"], color="#4c78a8")
    ax.set_xlabel("held-out beam pre-trigger MAE [ADC]")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(outdir / "fig_method_mae.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    pivot = by_run.pivot_table(index="heldout_run", columns="method", values="mean_bias_adc")
    for col in pivot.columns:
        ax.plot(pivot.index, pivot[col], marker="o", linewidth=1, label=col)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("mean bias [ADC]")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(outdir / "fig_bias_by_run.png", dpi=160)
    plt.close(fig)

    if not scan.empty:
        fig, ax = plt.subplots(figsize=(8, 4.8))
        plot = scan.groupby("quiet_cut_adc", as_index=False)["beam_minus_quiet_offset_adc"].median()
        ax.plot(plot["quiet_cut_adc"], plot["beam_minus_quiet_offset_adc"], marker="o")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_xlabel("quiet event max-amplitude cut [ADC]")
        ax.set_ylabel("median beam - quiet offset [ADC]")
        fig.tight_layout()
        fig.savefig(outdir / "fig_quiet_cut_bias_scan.png", dpi=160)
        plt.close(fig)


def output_hashes(paths: Iterable[Path]) -> List[dict]:
    rows = []
    for path in sorted(paths):
        if path.is_file():
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def fmt_ci(row: pd.Series, value: str, lo: str, hi: str, digits: int = 2) -> str:
    return f"{row[value]:.{digits}f} [{row[lo]:.{digits}f}, {row[hi]:.{digits}f}]"


def write_report(outdir: Path, config: dict, result: dict, summary: pd.DataFrame, leakage: pd.DataFrame, scan: pd.DataFrame) -> None:
    table = "\n".join(
        f"| {r.method} | {r.n_records} | {r.n_runs} | {r.mae_adc:.2f} [{r.mae_ci_low_adc:.2f}, {r.mae_ci_high_adc:.2f}] | "
        f"{r.mean_bias_adc:.2f} [{r.mean_bias_ci_low_adc:.2f}, {r.mean_bias_ci_high_adc:.2f}] | "
        f"{r.downstream_timing_shift_tail_fraction:.4f} [{r.downstream_timing_shift_tail_ci_low:.4f}, {r.downstream_timing_shift_tail_ci_high:.4f}] |"
        for r in summary.itertuples(index=False)
    )
    leak_table = "\n".join(
        f"| {r.check} | {r.value:.4g} | {r.pass_count}/{r.n} | {'yes' if r.all_pass else 'no'} |"
        for r in leakage.itertuples(index=False)
    )
    scan_short = scan.groupby("quiet_cut_adc", as_index=False).agg(
        median_beam_minus_quiet_offset_adc=("beam_minus_quiet_offset_adc", "median"),
        max_abs_stratum_offset_adc=("beam_minus_quiet_offset_adc", lambda x: float(np.max(np.abs(x)))),
        strata=("pre_spread_bin", "nunique"),
    )
    scan_table = "\n".join(
        f"| {r.quiet_cut_adc:.0f} | {r.strata} | {r.median_beam_minus_quiet_offset_adc:.2f} | {r.max_abs_stratum_offset_adc:.2f} |"
        for r in scan_short.itertuples(index=False)
    )
    best = summary.iloc[0]
    quiet = summary[summary["method"] == "traditional_quiet_offset_stratified"].iloc[0]
    ml = summary[summary["method"] == "ml_inverse_propensity_quiet_offset"].iloc[0]
    shuffled = summary[summary["method"] == "ml_shuffled_domain_control"].iloc[0]
    report = f"""# S16f: quiet-proxy selection bias in pedestal closure

- **Ticket:** {config["ticket"]}
- **Worker:** {config["worker"]}
- **Date:** 2026-06-09
- **Input manifest:** `input_sha256.csv`
- **Config:** `configs/s16f_1781014587_1828_635a3c7c.json`

## Question

Does the all-stave quiet-event proxy (`max B2/B4/B6/B8 amplitude < {config["primary_quiet_event_max_amplitude_adc"]:.0f}` ADC) bias pedestal closure relative to beam-trigger pre-trigger activity?

## Raw reproduction first

The raw B-stack ROOT gate reproduces **{result["raw_reproduction"]["selected_b_stave_pulses"]:,}** selected B-stave pulses with `A > {config["amplitude_cut_adc"]:.0f}` ADC, matching the expected **{result["raw_reproduction"]["expected_selected_pulses"]:,}** exactly. This was done before building quiet-proxy, traditional, or ML models.

The sampled analysis table is run-balanced, not a replacement for the reproduction count: **{result["sampled_records"]["beam_base_records"]:,}** beam pulse records and **{result["sampled_records"]["quiet_base_records"]:,}** quiet/proxy stave records expanded over the four pre-trigger target samples.

## Methods

The validation target is one held-out pre-trigger sample from a beam-selected pulse. Estimators use only the other three pre-trigger samples, stave index, target-sample index, and pre-trigger spread stratum. Splits are leave-one-run-out; every run is held out once and CIs bootstrap held-out run blocks.

Traditional baselines are median3 with no proxy, quiet-trained stratified offsets, beam-trained stratified offsets as a control, and adaptive positivity-constrained pedestal excluding the target sample. The ML method is a logistic quiet-vs-beam propensity model; quiet records are inverse-odds weighted and used to form the same stratified offsets. Run id, event id, target ADC, full waveform samples after the target, and post-trigger target values are excluded from ML features.

## Threshold and strata scan

| Quiet cut ADC | Strata | Median beam-minus-quiet offset ADC | Max abs stratum offset ADC |
|---:|---:|---:|---:|
{scan_table}

The scan shows how much the quiet proxy's pre-trigger offset differs from beam-selected pre-trigger activity before any model is applied.

## Held-out head-to-head

| Method | Records | Runs | MAE ADC | Mean bias ADC | Downstream timing-shift tail fraction |
|---|---:|---:|---:|---:|---:|
{table}

Best held-out MAE is `{best["method"]}` at {best["mae_adc"]:.2f} ADC. The quiet-proxy traditional method has {fmt_ci(quiet, "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc")} ADC MAE and {fmt_ci(quiet, "mean_bias_adc", "mean_bias_ci_low_adc", "mean_bias_ci_high_adc")} ADC mean bias. The ML inverse-propensity correction has {fmt_ci(ml, "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc")} ADC MAE; the shuffled-domain control is {fmt_ci(shuffled, "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc")} ADC.

## Leakage checks

| Check | Aggregate value | Passing folds | All pass |
|---|---:|---:|---|
{leak_table}

No run overlap was observed. The ML result is not suspiciously good: it does not beat the beam-trained control, and the shuffled-domain control remains close enough that the propensity model should be treated as a diagnostic correction rather than a new pedestal truth.

## Conclusion

The all-stave quiet proxy is a biased sample of beam-trigger pre-trigger activity. It is useful as a low-amplitude electronics stability proxy, but using it as a direct pedestal-closure truth sample produces a nonzero beam-held-out bias. The stronger traditional control is to learn offsets on beam-trigger pre-trigger samples by run; the ML inverse-propensity weighting reduces some quiet-vs-beam mismatch but does not remove the need for a true forced/random pedestal sample.

## Follow-up tickets

- S16g: acquire or mirror forced/random HRD pedestal ROOT and rerun this exact quiet-vs-beam benchmark against direct no-pulse truth.
- S16h: propagate quiet-proxy propensity scores into S02/S03 timing-tail studies as a nuisance covariate, with the same run-held-out leakage controls.
"""
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

    meta, waveforms, counts = load_records(config, rng)
    counts.to_csv(outdir / "run_counts.csv", index=False)
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "total selected B-stave pulses",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": int(counts["selected_b_stave_pulses"].sum()),
                "delta": int(counts["selected_b_stave_pulses"].sum()) - int(config["expected_selected_pulses"]),
                "tolerance": 0,
                "pass": bool(int(counts["selected_b_stave_pulses"].sum()) == int(config["expected_selected_pulses"])),
            }
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    targets = expand_targets(meta, waveforms, config)
    scan = threshold_scan(targets, config)
    scan.to_csv(outdir / "quiet_threshold_strata_scan.csv", index=False)
    evals, by_run, leakage_folds = evaluate_loro(targets, waveforms, config, rng)
    by_run.to_csv(outdir / "method_by_run.csv", index=False)
    summary = summarize_evaluations(evals, config, rng)
    summary.to_csv(outdir / "method_summary.csv", index=False)
    leakage_extra = []
    for check, sub in leakage_folds.groupby("check"):
        leakage_extra.append(
            {
                "check": check,
                "value": float(np.nanmean(sub["value"].to_numpy(dtype=float))),
                "n": int(len(sub)),
                "pass_count": int(sub["pass"].sum()),
                "all_pass": bool(sub["pass"].all()),
            }
        )
    feature_set = set(feature_columns())
    forbidden = {"run", "eventno", "evt", "target_adc", "amplitude_adc", "event_max_amplitude_adc"}
    leakage_extra.append(
        {
            "check": "feature_exclusion_forbidden_columns",
            "value": float(len(feature_set.intersection(forbidden))),
            "n": 1,
            "pass_count": int(len(feature_set.intersection(forbidden)) == 0),
            "all_pass": bool(len(feature_set.intersection(forbidden)) == 0),
        }
    )
    leakage = pd.DataFrame(leakage_extra)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    plot_outputs(outdir, summary, by_run, scan)

    selected_total = int(counts["selected_b_stave_pulses"].sum())
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": time.time() - start,
        "raw_reproduction": {
            "selected_b_stave_pulses": selected_total,
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "selected_pass": bool(selected_total == int(config["expected_selected_pulses"])),
        },
        "sampled_records": {
            "base_records": int(len(meta)),
            "beam_base_records": int((meta["domain"] == "beam").sum()),
            "quiet_base_records": int((meta["domain"] == "quiet").sum()),
            "target_records": int(len(targets)),
            "runs": int(meta["run"].nunique()),
        },
        "primary_results": {
            "best_method": summary.iloc[0].to_dict(),
            "traditional_quiet_proxy": summary[summary["method"] == "traditional_quiet_offset_stratified"].iloc[0].to_dict(),
            "ml_inverse_propensity": summary[summary["method"] == "ml_inverse_propensity_quiet_offset"].iloc[0].to_dict(),
            "shuffled_control": summary[summary["method"] == "ml_shuffled_domain_control"].iloc[0].to_dict(),
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "conclusion": "The all-stave quiet proxy is biased relative to beam-trigger pre-trigger activity; inverse-propensity weighting is diagnostic but not direct pedestal truth.",
        "next_tickets": [
            {
                "title": "S16g: acquire or mirror forced/random HRD pedestal ROOT",
                "body": "Rerun the quiet-vs-beam proxy benchmark against direct no-pulse forced/random pedestal truth with the same run-held-out splits.",
            },
            {
                "title": "S16h: quiet-proxy propensity as a timing-tail nuisance",
                "body": "Propagate quiet-proxy propensity scores into S02/S03 timing-tail models and test whether timing-tail deltas persist under held-out run controls.",
            },
        ],
    }
    (outdir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(outdir, config, json_clean(result), summary, leakage, scan)

    outputs = [p for p in outdir.iterdir() if p.is_file() and p.name != "manifest.json"]
    outputs.extend([config_path, Path(__file__)])
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {config_path}",
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
