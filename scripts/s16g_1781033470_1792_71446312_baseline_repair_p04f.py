#!/usr/bin/env python3
"""S16g: traditional baseline repair for P04f anomaly strata.

This ticket starts with the same raw ROOT selected-pulse reproduction gate as
P04, imports the frozen P09a baseline-excursion and early-pretrigger taxonomy,
and tests whether explicit baseline repairs improve duplicate-readout charge
closure on those anomaly strata under run-held-out splits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04_amplitude_charge_regression as p04  # noqa: E402
import p09a_rare_waveform_anomaly_taxonomy as p09a  # noqa: E402


STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd20_crossing(waves: np.ndarray) -> np.ndarray:
    """First rising-edge crossing of 20 percent of the local positive peak."""
    out = np.full(len(waves), np.nan, dtype=np.float32)
    peaks = waves.argmax(axis=1)
    amps = np.maximum(waves.max(axis=1), 1.0)
    norm = waves / amps[:, None]
    for i, peak in enumerate(peaks):
        if peak <= 0:
            continue
        above = np.where(norm[i, : peak + 1] >= 0.2)[0]
        if len(above) == 0:
            continue
        j = int(above[0])
        if j == 0:
            out[i] = 0.0
            continue
        y0, y1 = float(norm[i, j - 1]), float(norm[i, j])
        frac = 0.0 if abs(y1 - y0) < 1e-9 else (0.2 - y0) / (y1 - y0)
        out[i] = float(j - 1 + np.clip(frac, 0.0, 1.0))
    return out


def waveform_atom_features(
    corrected_even: np.ndarray,
    raw_even: np.ndarray,
    corrected_odd: np.ndarray,
    baseline_idx: List[int],
    saturation_raw_adc: float,
) -> pd.DataFrame:
    amp = corrected_even.max(axis=1)
    peak = corrected_even.argmax(axis=1).astype(np.int16)
    charge = np.clip(corrected_even, 0.0, None).sum(axis=1)
    total = np.maximum(charge, 1.0)
    positive = np.clip(corrected_even, 0.0, None)
    norm = corrected_even / np.maximum(amp[:, None], 1.0)
    baseline_median = np.median(raw_even[:, baseline_idx], axis=1)
    baseline_mad = np.median(np.abs(raw_even[:, baseline_idx] - baseline_median[:, None]), axis=1)
    baseline_slope = raw_even[:, baseline_idx[-1]] - raw_even[:, baseline_idx[0]]
    baseline_range = raw_even[:, baseline_idx].max(axis=1) - raw_even[:, baseline_idx].min(axis=1)
    raw_max = raw_even.max(axis=1)
    sat_count = (raw_even >= saturation_raw_adc).sum(axis=1).astype(np.int16)
    late_fraction = positive[:, 12:].sum(axis=1) / total
    early_fraction = positive[:, :4].sum(axis=1) / total
    tail_fraction = positive[:, 9:].sum(axis=1) / total
    width_half = (corrected_even > (0.5 * amp[:, None])).sum(axis=1).astype(np.int16)
    area_norm = corrected_even.sum(axis=1) / total
    secondary_peak = np.zeros(len(corrected_even), dtype=np.float32)
    secondary_sep = np.zeros(len(corrected_even), dtype=np.int16)
    post_peak_min = np.zeros(len(corrected_even), dtype=np.float32)
    undershoot_area = np.zeros(len(corrected_even), dtype=np.float32)
    dropout_score = np.zeros(len(corrected_even), dtype=np.float32)
    for i, p in enumerate(peak):
        masked = positive[i].copy()
        lo, hi = max(0, int(p) - 1), min(corrected_even.shape[1], int(p) + 2)
        masked[lo:hi] = 0.0
        sidx = int(masked.argmax())
        secondary_peak[i] = float(masked[sidx] / max(float(amp[i]), 1.0))
        secondary_sep[i] = abs(sidx - int(p))
        tail = norm[i, min(corrected_even.shape[1] - 1, int(p) + 1) :]
        post_peak_min[i] = float(tail.min()) if len(tail) else 0.0
        undershoot_area[i] = float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0
        expected_tail = positive[i, min(corrected_even.shape[1], int(p) + 1) :].sum() / max(float(total[i]), 1.0)
        dropout_score[i] = float(max(0.0, -post_peak_min[i]) + max(0.0, 0.12 - expected_tail))

    odd_pos = np.clip(-corrected_odd, 0.0, None)
    odd_cfd = cfd20_crossing(odd_pos)
    even_cfd = cfd20_crossing(positive)
    timing_span = np.abs(even_cfd - odd_cfd)
    timing_span = np.where(np.isfinite(timing_span), timing_span, corrected_even.shape[1]).astype(np.float32)

    return pd.DataFrame(
        {
            "baseline_median": baseline_median.astype(np.float32),
            "baseline_mad": baseline_mad.astype(np.float32),
            "baseline_slope": baseline_slope.astype(np.float32),
            "baseline_range": baseline_range.astype(np.float32),
            "raw_max_adc": raw_max.astype(np.float32),
            "saturation_count": sat_count,
            "late_fraction": late_fraction.astype(np.float32),
            "early_fraction": early_fraction.astype(np.float32),
            "tail_fraction": tail_fraction.astype(np.float32),
            "width_half": width_half,
            "area_norm": area_norm.astype(np.float32),
            "secondary_peak": secondary_peak,
            "secondary_sep": secondary_sep,
            "post_peak_min": post_peak_min,
            "undershoot_area": undershoot_area,
            "dropout_score": dropout_score,
            "timing_span_dup": timing_span,
        }
    )


def extract_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["staves"].keys())
    even_channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_channels = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    stave_names = np.asarray(staves, dtype=object)
    groups = run_group_lookup(config)

    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []
    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {"run": run, "group": groups[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        run_counts.update({name: 0 for name in staves})
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            raw_even = raw[:, even_channels, :]
            raw_odd = raw[:, odd_channels, :]
            base_even = np.median(raw_even[..., baseline_idx], axis=-1)
            base_odd = np.median(raw_odd[..., baseline_idx], axis=-1)
            even = raw_even - base_even[..., None]
            odd = raw_odd - base_odd[..., None]
            even_amp = even.max(axis=-1)
            even_peak = even.argmax(axis=-1)
            even_pos_charge = np.clip(even, 0.0, None).sum(axis=-1)
            even_area = even.sum(axis=-1)
            target_amp = (-odd).max(axis=-1)
            target_charge = np.clip(-odd, 0.0, None).sum(axis=-1)
            selected = even_amp > cut
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(eventno))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, stave in enumerate(staves):
                run_counts[stave] += int(selected[:, idx].sum())

            if len(event_idx) == 0:
                continue
            chosen_even = even[event_idx, stave_idx]
            chosen_raw_even = raw_even[event_idx, stave_idx]
            chosen_odd = odd[event_idx, stave_idx]
            atoms = waveform_atom_features(
                chosen_even,
                chosen_raw_even,
                chosen_odd,
                baseline_idx,
                float(config["saturation_raw_adc"]),
            )
            atoms.insert(0, "target_odd_pos_charge", target_charge[event_idx, stave_idx].astype(np.float32))
            atoms.insert(0, "target_odd_neg_amp", target_amp[event_idx, stave_idx].astype(np.float32))
            atoms.insert(0, "even_area", even_area[event_idx, stave_idx].astype(np.float32))
            atoms.insert(0, "even_pos_charge", even_pos_charge[event_idx, stave_idx].astype(np.float32))
            atoms.insert(0, "even_peak", even_peak[event_idx, stave_idx].astype(np.int16))
            atoms.insert(0, "even_amp", even_amp[event_idx, stave_idx].astype(np.float32))
            atoms.insert(0, "stave_idx", stave_idx.astype(np.int16))
            atoms.insert(0, "stave", stave_names[stave_idx])
            atoms.insert(0, "evt", evt[event_idx])
            atoms.insert(0, "eventno", eventno[event_idx])
            atoms.insert(0, "group", groups[run])
            atoms.insert(0, "run", np.full(len(event_idx), run, dtype=np.int16))
            frames.append(atoms)
            waves.append(chosen_even.astype(np.float32))
        counts.append(run_counts)
        print(f"run {run:04d}: {run_counts['selected_pulses']} selected pulses")

    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def robust_metrics(y: np.ndarray, pred: np.ndarray, timing_tail: np.ndarray, catastrophic_cut: float) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    tail = timing_tail.astype(bool)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "catastrophic_rate": float(np.mean(abs_frac > catastrophic_cut)),
        "within_10pct": float(np.mean(abs_frac < 0.10)),
        "timing_tail_abs_frac_mean": float(np.mean(abs_frac[tail])) if tail.any() else None,
        "timing_tail_catastrophic_rate": float(np.mean(abs_frac[tail] > catastrophic_cut)) if tail.any() else None,
    }


def event_bootstrap_ci(y: np.ndarray, pred: np.ndarray, timing_tail: np.ndarray, catastrophic_cut: float, rng: np.random.Generator, reps: int) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    tail = timing_tail.astype(bool)
    n = len(frac)
    bias = np.empty(reps)
    res68 = np.empty(reps)
    rms = np.empty(reps)
    cat = np.empty(reps)
    tail_abs = np.empty(reps)
    for i in range(reps):
        idx = rng.integers(0, n, size=n)
        sample = frac[idx]
        sample_abs = abs_frac[idx]
        sample_tail = tail[idx]
        bias[i] = np.median(sample)
        res68[i] = np.percentile(sample_abs, 68)
        rms[i] = np.sqrt(np.mean(sample * sample))
        cat[i] = np.mean(sample_abs > catastrophic_cut)
        tail_abs[i] = np.mean(sample_abs[sample_tail]) if sample_tail.any() else np.nan
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
        "catastrophic_rate_ci95": [float(np.percentile(cat, 2.5)), float(np.percentile(cat, 97.5))],
        "timing_tail_abs_frac_mean_ci95": [
            float(np.nanpercentile(tail_abs, 2.5)),
            float(np.nanpercentile(tail_abs, 97.5)),
        ],
    }


def run_block_ci(frame: pd.DataFrame, target_col: str, pred_col: str, catastrophic_cut: float, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    bias = np.empty(reps)
    res68 = np.empty(reps)
    rms = np.empty(reps)
    cat = np.empty(reps)
    for i in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        frac = (sample[pred_col].to_numpy() - sample[target_col].to_numpy()) / np.maximum(sample[target_col].to_numpy(), 1.0)
        abs_frac = np.abs(frac)
        bias[i] = np.median(frac)
        res68[i] = np.percentile(abs_frac, 68)
        rms[i] = np.sqrt(np.mean(frac * frac))
        cat[i] = np.mean(abs_frac > catastrophic_cut)
    return {
        "run_block_bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "run_block_res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "run_block_full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
        "run_block_catastrophic_rate_ci95": [float(np.percentile(cat, 2.5)), float(np.percentile(cat, 97.5))],
    }


def train_thresholds(meta: pd.DataFrame, train_mask: np.ndarray, config: dict) -> dict:
    q = float(config["atom_quantile"])
    pre = np.sqrt(meta["baseline_mad"].to_numpy() ** 2 + meta["baseline_slope"].to_numpy() ** 2 + meta["baseline_range"].to_numpy() ** 2)
    return {
        "baseline_score": float(np.quantile(pre[train_mask], q)),
        "dropout_score": float(np.quantile(meta.loc[train_mask, "dropout_score"], q)),
        "secondary_peak": float(np.quantile(meta.loc[train_mask, "secondary_peak"], q)),
        "peak_sample": int(np.quantile(meta.loc[train_mask, "even_peak"], q)),
        "timing_span_dup": float(np.quantile(meta.loc[train_mask, "timing_span_dup"], q)),
    }


def add_derived_columns(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    out = meta.copy()
    thresholds = train_thresholds(out, train_mask, config)
    baseline_score = np.sqrt(out["baseline_mad"].to_numpy() ** 2 + out["baseline_slope"].to_numpy() ** 2 + out["baseline_range"].to_numpy() ** 2)
    out["baseline_score"] = baseline_score.astype(np.float32)
    out["atom_baseline_excursion"] = (baseline_score >= thresholds["baseline_score"]).astype(np.int8)
    out["atom_delayed_peak"] = ((out["even_peak"].to_numpy() >= thresholds["peak_sample"]) | (out["secondary_peak"].to_numpy() >= thresholds["secondary_peak"])).astype(np.int8)
    out["atom_dropout"] = (out["dropout_score"].to_numpy() >= thresholds["dropout_score"]).astype(np.int8)
    out["timing_tail"] = (out["timing_span_dup"].to_numpy() >= thresholds["timing_span_dup"]).astype(np.int8)
    out["is_saturated"] = ((out["saturation_count"].to_numpy() > 0) | (out["raw_max_adc"].to_numpy() >= float(config["saturation_raw_adc"]))).astype(np.int8)
    out["amp_bin"] = pd.cut(
        out["even_amp"],
        bins=[float(x) for x in config["amplitude_bins"]],
        labels=False,
        include_lowest=True,
    ).astype(int)
    out["peak_bin"] = pd.cut(out["even_peak"], bins=[-1, 5, 7, 9, 11, 18], labels=False, include_lowest=True).astype(int)

    train_features = np.column_stack(
        [
            wave / np.maximum(out["even_amp"].to_numpy()[:, None], 1.0),
            out[["baseline_score", "dropout_score", "secondary_peak", "tail_fraction", "late_fraction", "area_norm"]].to_numpy(),
        ]
    )
    train_features = np.nan_to_num(train_features, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(train_features[train_mask])
    all_scaled = scaler.transform(train_features)
    train_scaled = np.nan_to_num(train_scaled, nan=0.0, posinf=0.0, neginf=0.0)
    all_scaled = np.nan_to_num(all_scaled, nan=0.0, posinf=0.0, neginf=0.0)
    center = np.nanmedian(train_scaled, axis=0)
    mad = 1.4826 * np.nanmedian(np.abs(train_scaled - center[None, :]), axis=0)
    mad = np.where(np.isfinite(mad) & (mad > 1e-6), mad, 1.0)
    z = (all_scaled - center[None, :]) / mad[None, :]
    z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
    out["p09_pca_anomaly_score"] = np.mean(np.clip(z, -10.0, 10.0) ** 2, axis=1).astype(np.float32)
    return out


def feature_matrix(meta: pd.DataFrame, wave: np.ndarray, include_atoms: bool = True, include_saturation: bool = True, include_topology: bool = True) -> np.ndarray:
    amp = meta["even_amp"].to_numpy()
    charge = meta["even_pos_charge"].to_numpy()
    norm_wave = wave / np.maximum(amp[:, None], 1.0)
    cols = [
        norm_wave,
        np.column_stack(
            [
                np.log(np.maximum(amp, 1.0)),
                np.log(np.maximum(charge, 1.0)),
                meta["even_peak"].to_numpy(),
                meta["baseline_mad"].to_numpy(),
                meta["baseline_slope"].to_numpy(),
                meta["baseline_range"].to_numpy(),
                meta["baseline_score"].to_numpy(),
                meta["late_fraction"].to_numpy(),
                meta["early_fraction"].to_numpy(),
                meta["tail_fraction"].to_numpy(),
                meta["width_half"].to_numpy(),
                meta["area_norm"].to_numpy(),
                meta["secondary_peak"].to_numpy(),
                meta["secondary_sep"].to_numpy(),
                meta["post_peak_min"].to_numpy(),
                meta["undershoot_area"].to_numpy(),
                meta["dropout_score"].to_numpy(),
                meta["p09_pca_anomaly_score"].to_numpy(),
                meta["timing_span_dup"].to_numpy(),
            ]
        ),
    ]
    if include_atoms:
        cols.append(meta[["atom_baseline_excursion", "atom_delayed_peak", "atom_dropout"]].to_numpy())
    if include_saturation:
        cols.append(meta[["saturation_count", "raw_max_adc", "is_saturated"]].to_numpy())
    if include_topology:
        stave_idx = meta["stave_idx"].to_numpy().astype(int)
        onehot = np.zeros((len(meta), 4), dtype=float)
        onehot[np.arange(len(meta)), stave_idx] = 1.0
        cols.append(onehot)
    return np.nan_to_num(np.column_stack(cols), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def scalar_context(meta: pd.DataFrame) -> np.ndarray:
    stave_idx = meta["stave_idx"].to_numpy().astype(int)
    onehot = np.zeros((len(meta), 4), dtype=np.float32)
    onehot[np.arange(len(meta)), stave_idx] = 1.0
    out = np.column_stack(
        [
            np.log(np.maximum(meta["even_amp"].to_numpy(), 1.0)),
            np.log(np.maximum(meta["even_pos_charge"].to_numpy(), 1.0)),
            meta[[
                "even_peak",
                "baseline_score",
                "dropout_score",
                "secondary_peak",
                "tail_fraction",
                "late_fraction",
                "p09_pca_anomaly_score",
                "timing_span_dup",
                "is_saturated",
                "atom_baseline_excursion",
                "atom_delayed_peak",
                "atom_dropout",
            ]].to_numpy(),
            onehot,
        ]
    )
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def fit_log_calibrated(est: np.ndarray, y: np.ndarray, train_mask: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    def fit_line(x: np.ndarray, yy: np.ndarray) -> Tuple[float, float]:
        lx = np.log(np.maximum(x.astype(float), 1.0))
        ly = np.log(np.maximum(yy.astype(float), 1.0))
        finite = np.isfinite(lx) & np.isfinite(ly)
        lx = lx[finite]
        ly = ly[finite]
        if len(lx) < 10:
            return 0.0, float(np.nanmedian(ly)) if len(ly) else 0.0
        xm = float(np.mean(lx))
        ym = float(np.mean(ly))
        denom = float(np.mean((lx - xm) ** 2))
        slope = 0.0 if denom < 1e-12 else float(np.mean((lx - xm) * (ly - ym)) / denom)
        intercept = ym - slope * xm
        return slope, intercept

    out = np.zeros(len(est), dtype=float)
    safe_est = np.nan_to_num(est.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
    safe_y = np.nan_to_num(y.astype(float), nan=0.0, posinf=0.0, neginf=0.0)
    global_mask = train_mask & (safe_est > 0) & (safe_y > 0)
    global_slope, global_intercept = fit_line(safe_est[global_mask], safe_y[global_mask])
    for stave in sorted(np.unique(stave_idx)):
        mask = train_mask & (stave_idx == stave) & (safe_est > 0) & (safe_y > 0)
        if int(mask.sum()) >= 10:
            slope, intercept = fit_line(safe_est[mask], safe_y[mask])
        else:
            slope, intercept = global_slope, global_intercept
        pred_mask = stave_idx == stave
        log_pred = intercept + slope * np.log(np.maximum(safe_est[pred_mask], 1.0))
        out[pred_mask] = np.exp(np.clip(log_pred, 0.0, 20.0))
    return np.maximum(out, 1.0)


def fit_strong_huber(features: np.ndarray, y: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=1e-4, max_iter=250))
    model.fit(features[train_mask], np.log(y[train_mask]))
    return np.maximum(np.exp(model.predict(features)), 1.0)


def fit_ridge(features: np.ndarray, y: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    model.fit(features[train_idx], np.log(y[train_idx]))
    return np.maximum(np.exp(model.predict(features)), 1.0)


def fit_hgb(features: np.ndarray, y: np.ndarray, train_idx: np.ndarray, seed: int) -> np.ndarray:
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
    model = HistGradientBoostingRegressor(
        max_iter=240,
        learning_rate=0.055,
        max_leaf_nodes=31,
        min_samples_leaf=30,
        l2_regularization=0.08,
        random_state=seed,
    )
    model.fit(features[train_idx], np.log(y[train_idx]))
    return np.maximum(np.exp(model.predict(features)), 1.0)


class TabularMLP(nn.Module):
    def __init__(self, n_features: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, 96),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(96, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x_tab: torch.Tensor, x_wave: torch.Tensor | None = None) -> torch.Tensor:
        return self.net(x_tab).squeeze(1)


class WaveCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(32, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, x_tab: torch.Tensor, x_wave: torch.Tensor) -> torch.Tensor:
        z = self.conv(x_wave[:, None, :]).squeeze(-1)
        return self.head(z).squeeze(1)


class WaveAtomNet(nn.Module):
    def __init__(self, n_context: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.atom = nn.Sequential(nn.Linear(n_context, 48), nn.ReLU(), nn.Dropout(0.05), nn.Linear(48, 24), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(56, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x_tab: torch.Tensor, x_wave: torch.Tensor) -> torch.Tensor:
        z_wave = self.conv(x_wave[:, None, :]).squeeze(-1)
        z_atom = self.atom(x_tab)
        return self.head(torch.cat([z_wave, z_atom], dim=1)).squeeze(1)


class BaselineGatedCNN(nn.Module):
    """Small new architecture: temporal CNN gated by baseline-repair summaries."""

    def __init__(self, n_context: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.context = nn.Sequential(nn.Linear(n_context, 48), nn.ReLU(), nn.Linear(48, 32), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(n_context, 32), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x_tab: torch.Tensor, x_wave: torch.Tensor) -> torch.Tensor:
        zw = self.conv(x_wave[:, None, :]).squeeze(-1)
        zc = self.context(x_tab)
        return self.head(torch.cat([zw * self.gate(x_tab), zc], dim=1)).squeeze(1)


def torch_predict(model: nn.Module, x_tab: np.ndarray, x_wave: np.ndarray, device: torch.device, batch_size: int) -> np.ndarray:
    model.eval()
    preds: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x_tab), batch_size):
            end = min(len(x_tab), start + batch_size)
            xt = torch.from_numpy(x_tab[start:end]).to(device)
            xw = torch.from_numpy(x_wave[start:end]).to(device)
            preds.append(model(xt, xw).detach().cpu().numpy())
    return np.concatenate(preds)


def fit_torch_model(
    kind: str,
    x_tab: np.ndarray,
    x_wave: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
) -> np.ndarray:
    seed = int(config["random_seed"]) + {"mlp": 11, "cnn": 17, "wave_atom_net": 23, "baseline_gated_cnn": 29}[kind]
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    max_rows = int(config["nn_max_train_rows"])
    use_idx = train_idx.copy()
    if len(use_idx) > max_rows:
        use_idx = rng.choice(use_idx, size=max_rows, replace=False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    y_log = np.log(y)
    y_mean = float(y_log[use_idx].mean())
    y_std = float(y_log[use_idx].std() + 1e-6)

    tab_scaler = StandardScaler()
    x_tab_scaled = tab_scaler.fit_transform(x_tab[use_idx]).astype(np.float32)
    all_tab = tab_scaler.transform(x_tab).astype(np.float32)
    wave_scale = np.maximum(np.percentile(np.abs(x_wave[use_idx]), 95), 1.0)
    all_wave = (x_wave / wave_scale).astype(np.float32)
    train_wave = all_wave[use_idx]
    train_y = ((y_log[use_idx] - y_mean) / y_std).astype(np.float32)

    if kind == "mlp":
        model: nn.Module = TabularMLP(x_tab_scaled.shape[1])
    elif kind == "cnn":
        model = WaveCNN()
        x_tab_scaled = np.zeros((len(use_idx), 1), dtype=np.float32)
        all_tab = np.zeros((len(x_tab), 1), dtype=np.float32)
    elif kind == "baseline_gated_cnn":
        model = BaselineGatedCNN(x_tab_scaled.shape[1])
    else:
        model = WaveAtomNet(x_tab_scaled.shape[1])
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    batch_size = int(config["nn_batch_size"])
    epochs = int(config["nn_epochs"])
    n = len(use_idx)
    for epoch in range(epochs):
        order = rng.permutation(n)
        model.train()
        losses = []
        for start in range(0, n, batch_size):
            idx = order[start : start + batch_size]
            xt = torch.from_numpy(x_tab_scaled[idx]).to(device)
            xw = torch.from_numpy(train_wave[idx]).to(device)
            yy = torch.from_numpy(train_y[idx]).to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xt, xw), yy)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print(f"{kind} epoch {epoch + 1}/{epochs}: loss={np.mean(losses):.5f}")
    pred_std = torch_predict(model, all_tab, all_wave, device, batch_size * 4)
    return np.maximum(np.exp(pred_std * y_std + y_mean), 1.0)


def dropout_injected_prediction(meta: pd.DataFrame, base_pred: np.ndarray, y: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    pred = base_pred.copy()
    train = meta.loc[train_mask].copy()
    train["_frac"] = (base_pred[train_mask] - y[train_mask]) / np.maximum(y[train_mask], 1.0)
    keys = ["stave", "amp_bin", "peak_bin", "is_saturated", "atom_dropout"]
    corrections = train.groupby(keys)["_frac"].median()
    fallback = train.groupby(["stave", "amp_bin", "atom_dropout"])["_frac"].median()
    all_keys = list(zip(meta["stave"], meta["amp_bin"], meta["peak_bin"], meta["is_saturated"], meta["atom_dropout"]))
    fb_keys = list(zip(meta["stave"], meta["amp_bin"], meta["atom_dropout"]))
    corr = np.zeros(len(meta), dtype=float)
    for i, key in enumerate(all_keys):
        value = corrections.get(key, np.nan)
        if not np.isfinite(value):
            value = fallback.get(fb_keys[i], 0.0)
        corr[i] = float(value)
    return np.maximum(base_pred / np.maximum(1.0 + corr, 0.1), 1.0)


def evaluate_predictions(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 101)
    y = meta["target_odd_pos_charge"].to_numpy()
    held = meta.loc[heldout_mask, ["run", "target_odd_pos_charge", "timing_tail"]].copy()
    rows = []
    by_run_rows = []
    for method, pred_all in predictions.items():
        pred = pred_all[heldout_mask]
        h = held.copy()
        h["_pred"] = pred
        row = {"target": "duplicate_odd_charge", "method": method, "split": "sample_ii_run_heldout"}
        row.update(robust_metrics(h["target_odd_pos_charge"].to_numpy(), pred, h["timing_tail"].to_numpy(), float(config["catastrophic_abs_frac"])))
        row.update(event_bootstrap_ci(h["target_odd_pos_charge"].to_numpy(), pred, h["timing_tail"].to_numpy(), float(config["catastrophic_abs_frac"]), rng, int(config["bootstrap_reps"])))
        row.update(run_block_ci(h, "target_odd_pos_charge", "_pred", float(config["catastrophic_abs_frac"]), rng, int(config["bootstrap_reps"])))
        rows.append(row)
        for run, sub in h.groupby("run"):
            brow = {"target": "duplicate_odd_charge", "method": method, "split": f"heldout_run_{int(run)}"}
            brow.update(robust_metrics(sub["target_odd_pos_charge"].to_numpy(), sub["_pred"].to_numpy(), sub["timing_tail"].to_numpy(), float(config["catastrophic_abs_frac"])))
            by_run_rows.append(brow)
    return pd.DataFrame(rows), pd.DataFrame(by_run_rows)


def matched_atom_effects(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, methods: List[str], config: dict) -> pd.DataFrame:
    held = meta.loc[heldout_mask].copy().reset_index(drop=True)
    y = held["target_odd_pos_charge"].to_numpy()
    rng = np.random.default_rng(int(config["random_seed"]) + 202)
    reps = int(config["bootstrap_reps"])
    min_cell = int(config["min_matched_cell"])
    atom_cols = ["atom_baseline_excursion", "atom_delayed_peak", "atom_dropout"]
    controls = ["run", "stave", "amp_bin", "peak_bin", "is_saturated"]
    rows = []
    for method in methods:
        pred = predictions[method][heldout_mask]
        frac = (pred - y) / np.maximum(y, 1.0)
        held["_abs_frac"] = np.abs(frac)
        held["_cat"] = (np.abs(frac) > float(config["catastrophic_abs_frac"])).astype(float)
        for atom in atom_cols:
            cell_rows = []
            for key, sub in held.groupby(controls, sort=True):
                n1 = int((sub[atom] == 1).sum())
                n0 = int((sub[atom] == 0).sum())
                if n1 < min_cell or n0 < min_cell:
                    continue
                exposed = sub[sub[atom] == 1]
                control = sub[sub[atom] == 0]
                weight = min(n1, n0)
                cell_rows.append(
                    {
                        "run": int(sub["run"].iloc[0]),
                        "weight": weight,
                        "d_abs_frac": float(exposed["_abs_frac"].mean() - control["_abs_frac"].mean()),
                        "d_cat_rate": float(exposed["_cat"].mean() - control["_cat"].mean()),
                        "n_exposed": n1,
                        "n_control": n0,
                    }
                )
            if not cell_rows:
                continue
            cells = pd.DataFrame(cell_rows)
            w = cells["weight"].to_numpy(dtype=float)
            point_abs = float(np.average(cells["d_abs_frac"], weights=w))
            point_cat = float(np.average(cells["d_cat_rate"], weights=w))
            runs = np.asarray(sorted(cells["run"].unique()), dtype=int)
            by_run = {int(run): cells[cells["run"] == run] for run in runs}
            boot_abs = np.empty(reps)
            boot_cat = np.empty(reps)
            for i in range(reps):
                chosen = rng.choice(runs, size=len(runs), replace=True)
                sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
                sw = sample["weight"].to_numpy(dtype=float)
                boot_abs[i] = np.average(sample["d_abs_frac"], weights=sw)
                boot_cat[i] = np.average(sample["d_cat_rate"], weights=sw)
            rows.append(
                {
                    "method": method,
                    "atom": atom,
                    "matched_controls": "+".join(controls),
                    "n_cells": int(len(cells)),
                    "n_exposed_weighted": int(cells["n_exposed"].sum()),
                    "n_control_weighted": int(cells["n_control"].sum()),
                    "delta_abs_frac": point_abs,
                    "delta_abs_frac_ci95": [float(np.percentile(boot_abs, 2.5)), float(np.percentile(boot_abs, 97.5))],
                    "delta_catastrophic_rate": point_cat,
                    "delta_catastrophic_rate_ci95": [float(np.percentile(boot_cat, 2.5)), float(np.percentile(boot_cat, 97.5))],
                }
            )
    return pd.DataFrame(rows)


def leakage_sentinels(meta: pd.DataFrame, features: np.ndarray, y: np.ndarray, train_idx: np.ndarray, heldout_mask: np.ndarray, config: dict) -> dict:
    rng = np.random.default_rng(int(config["random_seed"]) + 303)
    shuffled = np.log(y[train_idx]).copy()
    rng.shuffle(shuffled)
    model = HistGradientBoostingRegressor(max_iter=80, learning_rate=0.06, max_leaf_nodes=31, random_state=int(config["random_seed"]) + 303)
    model.fit(features[train_idx], shuffled)
    shuffled_pred = np.exp(model.predict(features))

    topology_features = meta[["stave_idx", "amp_bin", "peak_bin", "is_saturated"]].to_numpy(dtype=np.float32)
    topo = fit_ridge(topology_features, y, train_idx)
    baseline_features = meta[["baseline_mad", "baseline_slope", "baseline_range", "baseline_score", "atom_baseline_excursion"]].to_numpy(dtype=np.float32)
    baseline_only = fit_ridge(baseline_features, y, train_idx)
    sat_features = meta[["saturation_count", "raw_max_adc", "is_saturated", "even_amp"]].to_numpy(dtype=np.float32)
    sat_only = fit_ridge(sat_features, y, train_idx)
    timing_tail = meta["timing_tail"].to_numpy()
    return {
        "shuffled_target_hgb": robust_metrics(y[heldout_mask], shuffled_pred[heldout_mask], timing_tail[heldout_mask], float(config["catastrophic_abs_frac"])),
        "topology_only_ridge": robust_metrics(y[heldout_mask], topo[heldout_mask], timing_tail[heldout_mask], float(config["catastrophic_abs_frac"])),
        "baseline_only_ridge": robust_metrics(y[heldout_mask], baseline_only[heldout_mask], timing_tail[heldout_mask], float(config["catastrophic_abs_frac"])),
        "saturation_only_ridge": robust_metrics(y[heldout_mask], sat_only[heldout_mask], timing_tail[heldout_mask], float(config["catastrophic_abs_frac"])),
    }


def markdown_table(frame: pd.DataFrame, columns: List[str], max_rows: int | None = None) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].copy()
    if max_rows is not None:
        use = use.head(max_rows)
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}" if pd.notna(x) else "")
    return use.to_markdown(index=False)


def output_hashes(out_dir: Path) -> List[dict]:
    return [{"path": str(path), "sha256": sha256_file(path)} for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"]


def align_p09a_taxonomy(config: dict, meta: pd.DataFrame, valid: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    p09_config = p09a.load_config(Path(config["p09a_reference_config"]))
    raw_dir = p09a.resolve_raw_root_dir(p09_config)
    waves, p09_meta, counts = p09a.scan_raw(p09_config, raw_dir)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(p09_config["expected_selected_pulses"])
    if reproduced != expected:
        raise RuntimeError(f"P09a raw reproduction failed: {reproduced} != {expected}")
    key_cols = ["run", "eventno", "evt", "stave"]
    if len(p09_meta) != len(meta):
        raise RuntimeError(f"P09a/P04 row count mismatch: {len(p09_meta)} != {len(meta)}")
    for col in key_cols:
        if not np.array_equal(p09_meta[col].to_numpy(), meta[col].to_numpy()):
            raise RuntimeError(f"P09a/P04 selected-row alignment mismatch at {col}")

    p09_meta = p09_meta.loc[valid].reset_index(drop=True)
    waves = waves[valid]
    train = ~p09_meta["run"].isin([int(x) for x in p09_config["heldout_runs"]]).to_numpy()
    p09_meta = p09a.add_template_residual(p09_config, waves, p09_meta, train)
    p09_meta, thresholds = p09a.add_taxonomy(p09_meta, train)
    p09_meta["p09a_traditional_score"] = p09a.score_traditional(p09_meta, train)
    return p09_meta, thresholds


def baseline_repair_estimates(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> Dict[str, np.ndarray]:
    pre_idx = [int(i) for i in config["baseline_samples"]]
    raw_wave = wave + meta["baseline_median"].to_numpy(dtype=np.float32)[:, None]
    t = np.arange(raw_wave.shape[1], dtype=np.float32)
    pre_t = t[pre_idx]
    pre = raw_wave[:, pre_idx]
    median_base = np.median(pre, axis=1)
    med = median_base[:, None]
    dist = np.abs(pre - med)
    keep = np.ones_like(pre, dtype=bool)
    keep[np.arange(len(pre)), np.argmax(dist, axis=1)] = False
    robust_base = np.mean(np.where(keep, pre, np.nan), axis=1)
    robust_base = np.where(np.isfinite(robust_base), robust_base, median_base)

    x = pre_t - float(pre_t.mean())
    denom = float(np.sum(x * x))
    slopes = ((pre - pre.mean(axis=1)[:, None]) * x[None, :]).sum(axis=1) / max(denom, 1e-6)
    intercept = pre.mean(axis=1) - slopes * float(pre_t.mean())
    slope_baseline = intercept[:, None] + slopes[:, None] * t[None, :]

    out = {
        "repair_median_sample": np.clip(raw_wave - median_base[:, None], 0.0, None).sum(axis=1),
        "repair_robust_pretrigger": np.clip(raw_wave - robust_base[:, None], 0.0, None).sum(axis=1),
        "repair_slope_corrected": np.clip(raw_wave - slope_baseline, 0.0, None).sum(axis=1),
    }

    repaired = np.empty_like(raw_wave, dtype=np.float32)
    train = meta.loc[train_mask].copy()
    train["_idx"] = np.where(train_mask)[0]
    keys = ["stave", "amp_bin", "peak_bin", "is_saturated"]
    global_template = np.median(pre[train_mask] - median_base[train_mask, None], axis=0)
    templates = {
        key: np.median(pre[sub["_idx"].to_numpy()] - median_base[sub["_idx"].to_numpy(), None], axis=0)
        for key, sub in train.groupby(keys, sort=True)
        if len(sub) >= int(config["min_matched_cell"])
    }
    for i, key in enumerate(zip(meta["stave"], meta["amp_bin"], meta["peak_bin"], meta["is_saturated"])):
        template = templates.get(key, global_template)
        corrected_pre = pre[i] - template
        level = float(np.median(corrected_pre))
        repaired[i] = raw_wave[i] - level
    out["repair_train_run_template_pedestal"] = np.clip(repaired, 0.0, None).sum(axis=1)
    return out


def add_p09a_context(meta: pd.DataFrame, p09_meta: pd.DataFrame) -> pd.DataFrame:
    out = meta.copy()
    copy_cols = [
        "label_baseline_excursion",
        "label_novel_early_pretrigger",
        "label_saturation",
        "label_dropout",
        "taxon",
        "q_template_rmse",
        "p09a_traditional_score",
    ]
    for col in copy_cols:
        out[col] = p09_meta[col].to_numpy()
    out["p09a_target_stratum"] = np.select(
        [
            out["label_baseline_excursion"].to_numpy(dtype=bool),
            out["label_novel_early_pretrigger"].to_numpy(dtype=bool),
        ],
        ["baseline_excursion", "novel_early_pretrigger"],
        default="other_valid",
    )
    return out


def stratum_summary(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 501)
    rows = []
    strata = ["all_valid", "baseline_excursion", "novel_early_pretrigger", "other_valid"]
    for stratum in strata:
        if stratum == "all_valid":
            mask = np.ones(len(meta), dtype=bool)
        else:
            mask = (meta["p09a_target_stratum"].to_numpy() == stratum)
        sub_base = meta.loc[mask, ["run", "target_odd_pos_charge", "timing_tail"]].copy()
        if len(sub_base) == 0:
            continue
        for method, pred in predictions.items():
            sub = sub_base.copy()
            sub["_pred"] = pred[mask]
            row = {"stratum": stratum, "method": method}
            row.update(robust_metrics(sub["target_odd_pos_charge"].to_numpy(), sub["_pred"].to_numpy(), sub["timing_tail"].to_numpy(), float(config["catastrophic_abs_frac"])))
            row.update(run_block_ci(sub, "target_odd_pos_charge", "_pred", float(config["catastrophic_abs_frac"]), rng, int(config["bootstrap_reps"])))
            rows.append(row)
    return pd.DataFrame(rows)


def matched_p09a_effects(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, methods: List[str], config: dict) -> pd.DataFrame:
    held = meta.loc[heldout_mask].copy().reset_index(drop=True)
    y = held["target_odd_pos_charge"].to_numpy()
    rng = np.random.default_rng(int(config["random_seed"]) + 707)
    controls = ["run", "stave", "amp_bin", "peak_bin", "is_saturated"]
    labels = {
        "p09a_baseline_excursion": "label_baseline_excursion",
        "p09a_novel_early_pretrigger": "label_novel_early_pretrigger",
    }
    rows = []
    for method in methods:
        pred = predictions[method][heldout_mask]
        frac = (pred - y) / np.maximum(y, 1.0)
        held["_abs_frac"] = np.abs(frac)
        held["_cat"] = (np.abs(frac) > float(config["catastrophic_abs_frac"])).astype(float)
        for label_name, col in labels.items():
            cell_rows = []
            for _, sub in held.groupby(controls, sort=True):
                exposed = sub[sub[col].astype(bool)]
                control = sub[~sub[col].astype(bool) & ~sub["label_baseline_excursion"].astype(bool) & ~sub["label_novel_early_pretrigger"].astype(bool)]
                if len(exposed) < int(config["min_matched_cell"]) or len(control) < int(config["min_matched_cell"]):
                    continue
                cell_rows.append(
                    {
                        "run": int(sub["run"].iloc[0]),
                        "weight": min(len(exposed), len(control)),
                        "delta_abs_frac": float(exposed["_abs_frac"].mean() - control["_abs_frac"].mean()),
                        "delta_catastrophic_rate": float(exposed["_cat"].mean() - control["_cat"].mean()),
                        "n_exposed": int(len(exposed)),
                        "n_control": int(len(control)),
                    }
                )
            if not cell_rows:
                continue
            cells = pd.DataFrame(cell_rows)
            w = cells["weight"].to_numpy(dtype=float)
            point_abs = float(np.average(cells["delta_abs_frac"], weights=w))
            point_cat = float(np.average(cells["delta_catastrophic_rate"], weights=w))
            runs = np.asarray(sorted(cells["run"].unique()), dtype=int)
            by_run = {int(run): cells[cells["run"] == int(run)] for run in runs}
            boot_abs = np.empty(int(config["bootstrap_reps"]))
            boot_cat = np.empty(int(config["bootstrap_reps"]))
            for i in range(int(config["bootstrap_reps"])):
                sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
                sw = sample["weight"].to_numpy(dtype=float)
                boot_abs[i] = float(np.average(sample["delta_abs_frac"], weights=sw))
                boot_cat[i] = float(np.average(sample["delta_catastrophic_rate"], weights=sw))
            rows.append(
                {
                    "method": method,
                    "label": label_name,
                    "matched_controls": "+".join(controls),
                    "n_cells": int(len(cells)),
                    "n_exposed": int(cells["n_exposed"].sum()),
                    "n_control": int(cells["n_control"].sum()),
                    "delta_abs_frac": point_abs,
                    "delta_abs_frac_ci95": [float(np.percentile(boot_abs, 2.5)), float(np.percentile(boot_abs, 97.5))],
                    "delta_catastrophic_rate": point_cat,
                    "delta_catastrophic_rate_ci95": [float(np.percentile(boot_cat, 2.5)), float(np.percentile(boot_cat, 97.5))],
                }
            )
    return pd.DataFrame(rows)



def write_report(
    out_dir: Path,
    config: dict,
    counts: pd.DataFrame,
    benchmark: pd.DataFrame,
    by_run: pd.DataFrame,
    stratum: pd.DataFrame,
    matched: pd.DataFrame,
    leakage: dict,
    p09_thresholds: pd.DataFrame,
    result: dict,
) -> None:
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    winner = result["winner"]["method"]
    best_traditional = result["best_traditional"]["method"]
    heldout_runs = ", ".join(str(int(x)) for x in config["heldout_runs"])
    bench_cols = ["method", "n", "bias_median_frac", "res68_abs_frac", "run_block_res68_ci95", "full_rms_frac", "catastrophic_rate", "run_block_catastrophic_rate_ci95", "timing_tail_abs_frac_mean"]
    stratum_cols = ["stratum", "method", "n", "bias_median_frac", "res68_abs_frac", "run_block_res68_ci95", "catastrophic_rate"]
    match_cols = ["method", "label", "n_cells", "n_exposed", "n_control", "delta_abs_frac", "delta_abs_frac_ci95", "delta_catastrophic_rate"]
    run_cols = ["method", "split", "n", "res68_abs_frac", "catastrophic_rate", "timing_tail_abs_frac_mean"]
    lines = [
        "# S16g: Traditional Baseline Repair for P04f Anomaly Strata",
        "", f"- **Ticket:** `{config['ticket_id']}`", f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/hrdb_run_*.root`; P09a labels are recomputed from the same raw ROOT rows.",
        f"- **Run split:** train on Sample I plus run 64; hold out Sample II analysis runs `{heldout_runs}`.",
        "- **Primary target:** paired odd-channel inverted duplicate-readout positive charge, `sum(max(-odd,0))`.",
        "", "## Abstract", "", result["finding"],
        "", "## 1. Raw ROOT Reproduction Gate", "",
        "| quantity | expected | reproduced | delta | pass |", "|---|---:|---:|---:|:---|",
        f"| selected B-stave pulse records | {expected:,} | {total:,} | {total - expected:+,} | {str(total == expected).lower()} |",
        "", "The reproduction gate reshapes `HRDv` into eight 18-sample channels, subtracts the median of samples 0--3 independently per channel, and selects B2/B4/B6/B8 even-channel pulses with peak amplitude above 1000 ADC. Odd-channel target quality cuts are applied only after this count is reproduced.",
        "", "## 2. Estimand and Metrics", "",
        "For pulse record \\(i\\), the duplicate-readout charge target is", "", "\\[ y_i = \\sum_t \\max[-o_i(t),0], \\]", "",
        "where \\(o_i(t)\\) is the baseline-subtracted paired odd-channel waveform. Each method predicts \\(\\hat y_i\\). The fractional residual is", "", "\\[ r_i = \\frac{\\hat y_i-y_i}{\\max(y_i,1)}. \\]", "",
        "The primary metric is \\(Q_{0.68}(|r_i|)\\), the 68th percentile of absolute fractional residuals. Secondary metrics are median residual bias, full RMS, catastrophic rate \\(P(|r_i|>0.25)\\), and timing-tail mean absolute residual. Confidence intervals resample held-out runs with replacement, preserving within-run correlations.",
        "", "## 3. P09a Strata", "",
        "P09a baseline-excursion and novel early-pretrigger labels are recomputed after a second raw ROOT scan and exact row alignment on `(run,eventno,evt,stave)`. The frozen thresholds used by the taxonomy are:", "",
        markdown_table(p09_thresholds, ["threshold", "value"], max_rows=40),
        "", "## 4. Methods", "", "### Traditional Baseline Repair", "",
        "- `repair_median_sample_logcal`: per-stave log calibration of the positive charge after subtracting the median of pretrigger samples 0--3.",
        "- `repair_robust_pretrigger_logcal`: same calibration after dropping the most deviant pretrigger sample and averaging the remaining three.",
        "- `repair_slope_corrected_logcal`: sample-wise subtraction of the linear baseline trend fitted on samples 0--3.",
        "- `repair_train_run_template_pedestal_logcal`: subtracts a train-run pedestal-shape template in `(stave, amplitude bin, peak bin, saturation)` cells before charge integration.",
        "- `strong_huber_baseline_repair`: Huber log-charge regression on hand-built pulse, saturation, and baseline-repair summaries.",
        "", "### ML/NN Comparators", "",
        "Ridge regression, histogram gradient-boosted trees, a tabular MLP, a waveform 1D-CNN, `wave_atom_net`, and the new `baseline_gated_cnn_new` are trained on the same train-run rows. Features exclude event identifiers, run id, odd-channel target samples, and target charge.",
        "", "## 5. Held-out Benchmark", "", markdown_table(benchmark.sort_values("res68_abs_frac"), bench_cols), "",
        f"The winner by held-out \\(Q_{{0.68}}(|r|)\\) is `{winner}`. The strongest traditional method is `{best_traditional}`.",
        "", "## 6. P09a-Stratum Benchmark", "",
        markdown_table(stratum[stratum["method"].isin([winner, best_traditional, "repair_median_sample_logcal", "repair_slope_corrected_logcal", "hgb_waveform_atoms", "baseline_gated_cnn_new"])], stratum_cols, max_rows=120),
        "", "## 7. Matched Stratum Effects", "",
        "Controls are sampled within run, stave, amplitude bin, peak bin, and saturation. Positive deltas mean the P09a stratum has larger residuals than matched non-P09a controls.", "",
        markdown_table(matched, match_cols, max_rows=120),
        "", "## 8. Per-run Stability", "",
        markdown_table(by_run[by_run["method"].isin([winner, best_traditional, "hgb_waveform_atoms", "ridge_waveform_atoms", "cnn_1d_waveform"])], run_cols, max_rows=100),
        "", "## 9. Leakage Sentinels and Systematics", "",
        f"- Train/held-out run overlap: `{result['leakage_audit']['train_heldout_run_overlap']}`.",
        f"- Train/held-out `(run,event,stave)` key overlap: `{result['leakage_audit']['train_heldout_event_key_overlap']}`.",
        f"- Invalid odd-target rows removed after reproduction: `{result['invalid_target_rows_removed_after_reproduction']}`.",
        f"- Shuffled-target HGB res68: `{leakage['shuffled_target_hgb']['res68_abs_frac']:.4f}`.",
        f"- Topology-only ridge res68: `{leakage['topology_only_ridge']['res68_abs_frac']:.4f}`.",
        f"- Baseline-only ridge res68: `{leakage['baseline_only_ridge']['res68_abs_frac']:.4f}`.",
        f"- Saturation-only ridge res68: `{leakage['saturation_only_ridge']['res68_abs_frac']:.4f}`.",
        "", "The target is duplicate-readout electronics closure, not deposited-energy truth. Since baseline-repair features come from the same even waveform as the charge estimate, improvements support an electronics-correction interpretation but do not by themselves prove external energy transfer. The held-out set contains seven runs, so run-block intervals are the uncertainty scale emphasized in all tables.",
        "", "## 10. Caveats", "",
        "- P09a labels are deterministic taxonomy labels, not hand-reviewed causal categories for every event.",
        "- Neural models are laptop-scale capacity checks with fixed hyperparameters; they are not an exhaustive architecture search.",
        "- The train-run pedestal template can only repair pretrigger shapes represented in train support; unseen baseline modes should be treated as out-of-support.",
        "- Same-event duplicate closure can be much easier than external charge prediction because both channels share electronics and event conditions.",
        "", "## 11. Reproducibility", "", "```bash", "/home/billy/anaconda3/bin/python scripts/s16g_1781033470_1792_71446312_baseline_repair_p04f.py --config configs/s16g_1781033470_1792_71446312_baseline_repair_p04f.json", "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s16g_1781033470_1792_71446312_baseline_repair_p04f.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    print("1/7 scanning raw ROOT and reproducing selected-pulse number ...")
    meta_all, wave_all, counts = extract_rows(config)
    total_selected = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"raw ROOT selected-pulse reproduction failed: {total_selected} != {expected}")
    valid = (np.isfinite(meta_all["target_odd_neg_amp"].to_numpy()) & np.isfinite(meta_all["target_odd_pos_charge"].to_numpy()) & np.isfinite(meta_all["even_amp"].to_numpy()) & np.isfinite(meta_all["even_pos_charge"].to_numpy()) & (meta_all["target_odd_neg_amp"].to_numpy() > 100.0) & (meta_all["target_odd_pos_charge"].to_numpy() > 100.0) & (meta_all["even_amp"].to_numpy() > 0.0) & (meta_all["even_pos_charge"].to_numpy() > 0.0))
    invalid_rows = int((~valid).sum())
    print("2/7 recomputing and aligning P09a anomaly taxonomy ...")
    p09_meta, p09_thresholds = align_p09a_taxonomy(config, meta_all, valid)
    meta = meta_all.loc[valid].reset_index(drop=True)
    wave = wave_all[valid]
    heldout_runs = [int(run) for run in config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    print(f"selected={total_selected} valid={len(meta)} train={int(train_mask.sum())} heldout={int(heldout_mask.sum())}")
    print("3/7 deriving repair features and P09a strata ...")
    meta = add_derived_columns(meta, wave, train_mask, config)
    meta = add_p09a_context(meta, p09_meta)
    repair = baseline_repair_estimates(meta, wave, train_mask, config)
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    y = meta["target_odd_pos_charge"].to_numpy()
    stave_idx = meta["stave_idx"].to_numpy().astype(int)
    predictions: Dict[str, np.ndarray] = {}
    print("4/7 fitting traditional baseline-repair estimators ...")
    for name, estimate in repair.items():
        predictions[f"{name}_logcal"] = fit_log_calibrated(estimate, y, train_mask, stave_idx)
    templates = p04.build_templates(meta, wave, train_mask, [float(x) for x in config["template_bins"]])
    template_scale = p04.template_scales(meta, wave, templates, [float(x) for x in config["template_bins"]], [float(x) for x in config["template_shift_grid"]])
    predictions["adaptive_template_logcal"] = fit_log_calibrated(template_scale, y, train_mask, stave_idx)
    repair_logs = np.column_stack([np.log(np.maximum(v, 1.0)) for v in repair.values()])
    trad_features = np.column_stack([meta[["even_amp", "even_pos_charge", "even_peak", "tail_fraction", "late_fraction", "width_half", "baseline_score", "baseline_mad", "baseline_slope", "baseline_range", "saturation_count", "is_saturated", "p09a_traditional_score", "q_template_rmse"]].to_numpy(dtype=np.float32), repair_logs])
    predictions["strong_huber_baseline_repair"] = fit_strong_huber(trad_features, y, train_mask)
    print("5/7 fitting ridge, gradient-boosted trees, MLP, 1D-CNN, and new gated CNN ...")
    p09_cols = meta[["label_baseline_excursion", "label_novel_early_pretrigger", "p09a_traditional_score", "q_template_rmse"]].astype(float).to_numpy()
    features = np.column_stack([feature_matrix(meta, wave), p09_cols, repair_logs]).astype(np.float32)
    predictions["ridge_waveform_atoms"] = fit_ridge(features, y, train_idx)
    predictions["hgb_waveform_atoms"] = fit_hgb(features, y, train_idx, int(config["random_seed"]) + 1)
    context = np.column_stack([scalar_context(meta), p09_cols, repair_logs]).astype(np.float32)
    norm_wave = (wave / np.maximum(meta["even_amp"].to_numpy()[:, None], 1.0)).astype(np.float32)
    predictions["mlp_waveform_atoms"] = fit_torch_model("mlp", features, norm_wave, y, train_idx, config)
    predictions["cnn_1d_waveform"] = fit_torch_model("cnn", context, norm_wave, y, train_idx, config)
    predictions["wave_atom_net"] = fit_torch_model("wave_atom_net", context, norm_wave, y, train_idx, config)
    predictions["baseline_gated_cnn_new"] = fit_torch_model("baseline_gated_cnn", context, norm_wave, y, train_idx, config)
    print("6/7 evaluating split-by-run metrics, bootstrap CIs, matched effects, sentinels ...")
    benchmark, by_run = evaluate_predictions(meta, predictions, heldout_mask, config)
    held_meta = meta.loc[heldout_mask].reset_index(drop=True)
    strata = stratum_summary(held_meta, {k: v[heldout_mask] for k, v in predictions.items()}, config)
    traditional_methods = ["repair_median_sample_logcal", "repair_robust_pretrigger_logcal", "repair_slope_corrected_logcal", "repair_train_run_template_pedestal_logcal", "adaptive_template_logcal", "strong_huber_baseline_repair"]
    ml_methods = ["ridge_waveform_atoms", "hgb_waveform_atoms", "mlp_waveform_atoms", "cnn_1d_waveform", "wave_atom_net", "baseline_gated_cnn_new"]
    best_traditional = benchmark[benchmark["method"].isin(traditional_methods)].sort_values("res68_abs_frac").iloc[0]
    winner = benchmark.sort_values("res68_abs_frac").iloc[0]
    matched_methods = list(dict.fromkeys([str(best_traditional["method"]), str(winner["method"]), "repair_median_sample_logcal", "repair_slope_corrected_logcal", "hgb_waveform_atoms", "baseline_gated_cnn_new"]))
    matched = matched_p09a_effects(meta, predictions, heldout_mask, matched_methods, config)
    leakage = leakage_sentinels(meta, features, y, train_idx, heldout_mask, config)
    print("7/7 writing artifacts ...")
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    p09_thresholds.to_csv(out_dir / "p09a_thresholds.csv", index=False)
    benchmark.to_csv(out_dir / "heldout_benchmark.csv", index=False)
    by_run.to_csv(out_dir / "heldout_benchmark_by_run.csv", index=False)
    strata.to_csv(out_dir / "p09a_stratum_benchmark.csv", index=False)
    matched.to_csv(out_dir / "matched_p09a_effects.csv", index=False)
    pd.DataFrame({"method": list(repair.keys()), "description": ["median samples 0-3", "drop largest pretrigger outlier", "linear pretrigger trend", "train-run cell pedestal template"]}).to_csv(out_dir / "baseline_repair_methods.csv", index=False)
    sample_cols = ["run", "eventno", "evt", "stave", "even_amp", "target_odd_pos_charge", "taxon", "p09a_target_stratum"]
    pred_sample = meta[sample_cols].copy()
    for method in [str(winner["method"]), str(best_traditional["method"]), "repair_median_sample_logcal", "hgb_waveform_atoms", "baseline_gated_cnn_new"]:
        pred_sample[f"pred_{method}"] = predictions[method]
    pred_sample.sample(n=min(25000, len(pred_sample)), random_state=int(config["random_seed"])).to_csv(out_dir / "prediction_sample.csv", index=False)
    finding = (f"Raw selected-pulse reproduction passes exactly ({total_selected:,} vs {expected:,}). The held-out winner is {winner['method']} with res68 {winner['res68_abs_frac']:.4f} and run-block CI {winner['run_block_res68_ci95']}; the best traditional baseline-repair comparator is {best_traditional['method']} with res68 {best_traditional['res68_abs_frac']:.4f}. P09a baseline-excursion and early-pretrigger rows remain measurable stress strata under run/stave/amplitude/peak/saturation matching, so the safest interpretation is a duplicate-readout electronics repair benchmark rather than external energy recovery.")
    result = {"study": config["study_id"], "ticket_id": config["ticket_id"], "worker": config["worker"], "title": config["title"], "runtime_sec": round(time.time() - t0, 1), "reproduced": True, "raw_reproduction": {"expected_selected_pulses": expected, "reproduced_selected_pulses": total_selected, "delta": total_selected - expected, "pass": total_selected == expected}, "invalid_target_rows_removed_after_reproduction": invalid_rows, "split": {"train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()), "heldout_runs": heldout_runs, "bootstrap_unit": "held-out run", "bootstrap_reps": int(config["bootstrap_reps"])}, "primary_metric": "held-out duplicate-readout charge res68_abs_frac; lower is better", "best_traditional": json.loads(pd.Series(best_traditional).to_json()), "winner": json.loads(pd.Series(winner).to_json()), "methods": {"traditional_baseline_repair": traditional_methods, "ml_nn": ml_methods}, "benchmark": json.loads(benchmark.to_json(orient="records")), "p09a_stratum_benchmark": json.loads(strata.to_json(orient="records")), "matched_p09a_effects": json.loads(matched.to_json(orient="records")), "leakage_sentinels": leakage, "leakage_audit": {"train_heldout_run_overlap": sorted(set(meta.loc[train_mask, "run"].unique()).intersection(set(heldout_runs))), "train_heldout_event_key_overlap": 0, "feature_exclusions": ["run", "eventno", "evt", "target_odd_pos_charge", "target_odd_neg_amp", "odd waveform samples"]}, "finding": finding, "next_tickets": [config["next_ticket"]]}
    def json_default(o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, default=json_default) + "\n", encoding="utf-8")
    write_report(out_dir, config, counts, benchmark, by_run, strata, matched, leakage, p09_thresholds, result)
    input_files = [raw_path(config, int(run)) for run in configured_runs(config)]
    input_rows = [{"path": str(path), "sha256": sha256_file(path)} for path in input_files]
    input_rows.extend([{"path": str(config_path), "sha256": sha256_file(config_path)}, {"path": str(Path(__file__)), "sha256": sha256_file(Path(__file__))}, {"path": str(Path(config["p09a_reference_config"])), "sha256": sha256_file(Path(config["p09a_reference_config"]))}])
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {"study": config["study_id"], "ticket_id": config["ticket_id"], "command": f"{sys.executable} scripts/s16g_1781033470_1792_71446312_baseline_repair_p04f.py --config {args.config}", "config": str(config_path), "python": platform.python_version(), "platform": platform.platform(), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True).strip(), "inputs": input_rows, "outputs": output_hashes(out_dir)}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
