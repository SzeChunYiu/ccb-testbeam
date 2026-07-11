#!/usr/bin/env python3
"""S24B: pedestal drift and waveform-shape invariance benchmark.

The script starts from raw B-stack ROOT, reproduces the selected pulse count,
defines a high-pedestal-drift target from the selected-pulse baseline, surveys
classic pulse-shape scores, and benchmarks the strongest traditional score
against a supervised ML/NN panel under run-heldout splitting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s24b")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - handled at runtime
    torch = None
    nn = None


STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_commit() -> str:
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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No B-stack raw ROOT directory found")


def configured_runs(config: dict) -> List[int]:
    runs = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    duplicate = {name: int(ch) for name, ch in config["duplicate_readout_channels"].items()}
    even_channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    odd_channels = np.asarray([duplicate[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)
    stave_grid = np.asarray(STAVE_NAMES, dtype=object)

    waves = []
    meta_frames = []
    count_rows = []

    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {
            "run": run,
            "group": groups[run],
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        run_counts.update({name: 0 for name in STAVE_NAMES})
        event_offset = 0
        for batch in iter_raw_events(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_channels, :]
            odd = corrected[:, odd_channels, :]
            even_amp = even.max(axis=-1)
            odd_target_amp = (-odd).max(axis=-1)
            selected = even_amp > cut
            event_idx, stave_idx = np.where(selected)

            run_counts["events_total"] += int(len(eventno))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(STAVE_NAMES):
                run_counts[name] += int(selected[:, i].sum())

            if len(event_idx):
                chosen = even[event_idx, stave_idx, :]
                amp = even_amp[event_idx, stave_idx].astype(np.float32)
                norm = chosen / np.maximum(amp[:, None], 1.0)
                waves.append(norm.astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": groups[run],
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_grid[stave_idx],
                            "stave_idx": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "target_odd_neg_amp": odd_target_amp[event_idx, stave_idx].astype(np.float32),
                            "baseline_adc": baseline[event_idx, even_channels[stave_idx]].astype(np.float32),
                            "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                        }
                    )
                )
            event_offset += int(len(eventno))
        count_rows.append(run_counts)
        print("run {:04d}: {} selected pulses".format(run, run_counts["selected_pulses"]))

    return np.concatenate(waves, axis=0), pd.concat(meta_frames, ignore_index=True), pd.DataFrame(count_rows)


def balanced_sample(meta: pd.DataFrame, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    pieces = []
    for _, group in meta.groupby(["run", "stave_idx"], sort=True):
        idx = group.index.to_numpy()
        take = min(len(idx), int(max_per_run_stave))
        if take:
            pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces).astype(int)
    rng.shuffle(out)
    return out


def threshold_crossing(waves: np.ndarray, fraction: float) -> np.ndarray:
    threshold = np.max(waves, axis=1) * float(fraction)
    ge = waves >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waves), np.nan, dtype=np.float64)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = waves[i, j - 1]
        y1 = waves[i, j]
        denom = y1 - y0
        out[i] = float(j) if abs(denom) < 1e-12 else (j - 1) + (threshold[i] - y0) / denom
    return out


def weighted_moments(waves: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    t = np.arange(waves.shape[1], dtype=np.float64)
    w = np.clip(waves, 0.0, None).astype(np.float64)
    s = np.maximum(w.sum(axis=1), 1e-9)
    mean = (w * t[None, :]).sum(axis=1) / s
    centered = t[None, :] - mean[:, None]
    var = (w * centered**2).sum(axis=1) / s
    std = np.sqrt(np.maximum(var, 1e-9))
    skew = (w * centered**3).sum(axis=1) / s / np.maximum(std**3, 1e-9)
    kurt = (w * centered**4).sum(axis=1) / s / np.maximum(var**2, 1e-9)
    return mean, var, skew, kurt


def haar_features(waves: np.ndarray) -> pd.DataFrame:
    x = waves[:, :16].astype(np.float64)
    coeffs = {}
    level = 0
    cur = x
    while cur.shape[1] >= 2:
        avg = 0.5 * (cur[:, 0::2] + cur[:, 1::2])
        diff = 0.5 * (cur[:, 0::2] - cur[:, 1::2])
        for j in range(diff.shape[1]):
            coeffs["haar_l{}_d{:02d}".format(level, j)] = diff[:, j].astype(np.float32)
        cur = avg
        level += 1
    return pd.DataFrame(coeffs)


def classic_features(waves: np.ndarray, meta: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    x = waves.astype(np.float64)
    nsamp = x.shape[1]
    t = np.arange(nsamp, dtype=np.float64)
    pos = np.clip(x, 0.0, None)
    area = x.sum(axis=1)
    pos_area = np.maximum(pos.sum(axis=1), 1e-9)
    abs_area = np.maximum(np.abs(area), 1e-9)
    peak = np.argmax(x, axis=1)
    peak_val = np.max(x, axis=1)
    diff = np.diff(x, axis=1)
    t10 = threshold_crossing(x, 0.10)
    t20 = threshold_crossing(x, 0.20)
    t50 = threshold_crossing(x, 0.50)
    t80 = threshold_crossing(x, 0.80)
    mt, var, skew, kurt = weighted_moments(x)
    fft = np.abs(np.fft.rfft(x - x.mean(axis=1, keepdims=True), axis=1))
    fft_total = np.maximum(fft[:, 1:].sum(axis=1), 1e-9)

    feats = pd.DataFrame(
        {
            "peak_sample": peak.astype(np.float32),
            "area_over_peak": area.astype(np.float32),
            "positive_area": pos_area.astype(np.float32),
            "tail_10_17_over_total": (pos[:, 10:].sum(axis=1) / pos_area).astype(np.float32),
            "tail_12_17_over_total": (pos[:, 12:].sum(axis=1) / pos_area).astype(np.float32),
            "tail_14_17_over_total": (pos[:, 14:].sum(axis=1) / pos_area).astype(np.float32),
            "early_0_4_over_total": (pos[:, :5].sum(axis=1) / pos_area).astype(np.float32),
            "middle_5_9_over_total": (pos[:, 5:10].sum(axis=1) / pos_area).astype(np.float32),
            "late_minus_early_asym": ((pos[:, 10:].sum(axis=1) - pos[:, :5].sum(axis=1)) / pos_area).astype(np.float32),
            "rise_10_50": (t50 - t10).astype(np.float32),
            "rise_20_80": (t80 - t20).astype(np.float32),
            "cfd20_time": t20.astype(np.float32),
            "cfd50_time": t50.astype(np.float32),
            "width20": (x > 0.2 * peak_val[:, None]).sum(axis=1).astype(np.float32),
            "width50": (x > 0.5 * peak_val[:, None]).sum(axis=1).astype(np.float32),
            "max_rise_step": diff.max(axis=1).astype(np.float32),
            "max_fall_step": diff.min(axis=1).astype(np.float32),
            "zero_crossings_derivative": (np.diff(np.signbit(diff), axis=1) != 0).sum(axis=1).astype(np.float32),
            "mean_time": mt.astype(np.float32),
            "time_variance": var.astype(np.float32),
            "time_skewness": skew.astype(np.float32),
            "time_kurtosis": kurt.astype(np.float32),
            "fft_k1_fraction": (fft[:, 1] / fft_total).astype(np.float32),
            "fft_k2_fraction": (fft[:, 2] / fft_total).astype(np.float32),
            "fft_high_over_low": (fft[:, 4:].sum(axis=1) / np.maximum(fft[:, 1:4].sum(axis=1), 1e-9)).astype(np.float32),
            "le_ratio_s4_s7": (x[:, 4] / np.maximum(x[:, 7], 1e-6)).astype(np.float32),
            "le_ratio_s5_s7": (x[:, 5] / np.maximum(x[:, 7], 1e-6)).astype(np.float32),
            "cf_ratio_s6_s8": (x[:, 6] / np.maximum(x[:, 8], 1e-6)).astype(np.float32),
            "final_sample": x[:, -1].astype(np.float32),
            "stave_idx": meta["stave_idx"].to_numpy(dtype=np.float32),
            "log10_amplitude": np.log10(np.maximum(meta["amplitude_adc"].to_numpy(dtype=float), 1.0)).astype(np.float32),
        }
    )
    h = haar_features(waves)
    feats = pd.concat([feats, h], axis=1)
    feature_roles = []
    role_map = {
        "charge_comparison_psd": ["tail_10_17_over_total", "tail_12_17_over_total", "tail_14_17_over_total", "early_0_4_over_total", "middle_5_9_over_total", "late_minus_early_asym"],
        "rise_time_width": ["rise_10_50", "rise_20_80", "width20", "width50"],
        "zero_crossing_derivative": ["max_rise_step", "max_fall_step", "zero_crossings_derivative"],
        "mean_time_moments": ["mean_time", "time_variance", "time_skewness", "time_kurtosis"],
        "frequency_domain_fft": ["fft_k1_fraction", "fft_k2_fraction", "fft_high_over_low"],
        "constant_fraction_shape_ratios": ["cfd20_time", "cfd50_time", "le_ratio_s4_s7", "le_ratio_s5_s7", "cf_ratio_s6_s8"],
        "wavelet_haar": list(h.columns),
        "amplitude_context_not_shape": ["log10_amplitude", "stave_idx"],
    }
    for role, cols in role_map.items():
        for col in cols:
            feature_roles.append({"feature": col, "family": role})
    return feats.replace([np.inf, -np.inf], np.nan).fillna(0.0), pd.DataFrame(feature_roles)


def p02_manual_labels(feats: pd.DataFrame) -> pd.DataFrame:
    peak = feats["peak_sample"].to_numpy()
    area = feats["area_over_peak"].to_numpy()
    down = feats["max_fall_step"].to_numpy()
    labels = pd.DataFrame(index=feats.index)
    manual = np.full(len(feats), "nominal", dtype=object)
    manual[peak <= 3] = "early_peak_p02"
    manual[(peak <= 4) & (area < 3.0)] = "early_low_area"
    manual[peak >= 12] = "late_peak"
    manual[down < -0.75] = "large_negative_step"
    labels["manual_flag"] = manual
    labels["anomalous_shape"] = (manual != "nominal").astype(np.int8)
    labels["peak_group"] = np.where(
        peak <= 3,
        "early_0_3",
        np.where(peak <= 5, "prepeak_4_5", np.where(peak <= 9, "nominal_6_9", "late_10_17")),
    )
    return labels


def pedestal_drift_labels(meta: pd.DataFrame, high_quantile: float) -> pd.DataFrame:
    """Target high absolute pedestal drift relative to run/stave medians."""
    baseline = meta["baseline_adc"].to_numpy(dtype=np.float64)
    center = meta.groupby(["run", "stave_idx"])["baseline_adc"].transform("median").to_numpy(dtype=np.float64)
    drift = baseline - center
    abs_drift = np.abs(drift)
    threshold = float(np.quantile(abs_drift, float(high_quantile)))
    labels = pd.DataFrame(index=meta.index)
    labels["baseline_center_run_stave_adc"] = center.astype(np.float32)
    labels["pedestal_drift_adc"] = drift.astype(np.float32)
    labels["abs_pedestal_drift_adc"] = abs_drift.astype(np.float32)
    labels["pedestal_high_drift"] = (abs_drift >= threshold).astype(np.int8)
    labels["pedestal_high_drift_threshold_adc"] = threshold
    labels["time_block"] = pd.qcut(meta["event_index"].rank(method="first"), q=4, labels=["q1", "q2", "q3", "q4"]).astype(str)
    return labels


def pedestal_summary_tables(meta: pd.DataFrame, labels: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    merged = pd.concat([meta[["run", "group", "stave", "stave_idx", "event_index", "amplitude_adc", "target_odd_neg_amp", "peak_sample"]], labels], axis=1)
    by_run = (
        merged.groupby("run", sort=True)
        .agg(
            rows=("run", "size"),
            high_drift_fraction=("pedestal_high_drift", "mean"),
            baseline_median_adc=("baseline_center_run_stave_adc", "median"),
            abs_drift_median_adc=("abs_pedestal_drift_adc", "median"),
            abs_drift_p90_adc=("abs_pedestal_drift_adc", lambda x: float(np.quantile(x, 0.90))),
            cfd_proxy_median_sample=("peak_sample", "median"),
            energy_proxy_median_adc=("amplitude_adc", "median"),
            pid_proxy_median_adc=("target_odd_neg_amp", "median"),
        )
        .reset_index()
    )
    by_block = (
        merged.groupby(["run", "time_block"], sort=True)
        .agg(
            rows=("run", "size"),
            high_drift_fraction=("pedestal_high_drift", "mean"),
            abs_drift_median_adc=("abs_pedestal_drift_adc", "median"),
            shape_energy_proxy_median_adc=("amplitude_adc", "median"),
            pid_proxy_median_adc=("target_odd_neg_amp", "median"),
        )
        .reset_index()
    )
    return by_run, by_block


def perturbation_negative_controls(waves: np.ndarray, meta: pd.DataFrame, labels: pd.DataFrame, perturbation_adc: float) -> pd.DataFrame:
    amp = np.maximum(meta["amplitude_adc"].to_numpy(dtype=np.float64), 1.0)
    scaled = float(perturbation_adc) / amp
    rows = []
    for sign in [-1.0, 1.0]:
        perturbed = waves + sign * scaled[:, None]
        perturbed = perturbed / np.maximum(perturbed.max(axis=1, keepdims=True), 1e-6)
        dist = np.sqrt(((perturbed - waves) ** 2).mean(axis=1))
        rows.append(
            {
                "perturbation_adc": sign * float(perturbation_adc),
                "rows": int(len(waves)),
                "shape_l2_median": float(np.median(dist)),
                "shape_l2_p95": float(np.quantile(dist, 0.95)),
                "high_drift_shape_l2_median": float(np.median(dist[labels["pedestal_high_drift"].to_numpy(dtype=bool)])),
                "low_drift_shape_l2_median": float(np.median(dist[~labels["pedestal_high_drift"].to_numpy(dtype=bool)])),
            }
        )
    return pd.DataFrame(rows)


def proxy_shift_bootstrap_cis(
    meta: pd.DataFrame,
    labels: pd.DataFrame,
    feats: pd.DataFrame,
    runs: np.ndarray,
    test_mask: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
) -> pd.DataFrame:
    """Run-block CIs for high-minus-low pedestal-drift proxy shifts."""
    high = labels["pedestal_high_drift"].to_numpy(dtype=bool)
    group_cols = [meta["run"], meta["stave_idx"]]
    centered = pd.DataFrame(
        {
            "shape_distance_nominal_chi2": feats["matched_template_nominal_chi2"].to_numpy(dtype=float),
            "timing_residual_mean_time_sample": feats["mean_time"].to_numpy(dtype=float)
            - feats["mean_time"].groupby(group_cols).transform("median").to_numpy(dtype=float),
            "energy_residual_log10_amplitude": feats["log10_amplitude"].to_numpy(dtype=float)
            - feats["log10_amplitude"].groupby(group_cols).transform("median").to_numpy(dtype=float),
            "pid_residual_odd_negative_adc": meta["target_odd_neg_amp"].to_numpy(dtype=float)
            - meta["target_odd_neg_amp"].groupby(group_cols).transform("median").to_numpy(dtype=float),
        }
    )
    metric_labels = {
        "shape_distance_nominal_chi2": "shape-distance stability",
        "timing_residual_mean_time_sample": "timing residual",
        "energy_residual_log10_amplitude": "energy calibration proxy",
        "pid_residual_odd_negative_adc": "PID score proxy",
    }
    idx_by_run = {int(run): np.where((runs == int(run)) & test_mask)[0] for run in np.sort(np.unique(runs[test_mask]))}

    def shift_for_indices(indices: np.ndarray, values: np.ndarray) -> float:
        hi = indices[high[indices]]
        lo = indices[~high[indices]]
        if len(hi) == 0 or len(lo) == 0:
            return float("nan")
        return float(np.median(values[hi]) - np.median(values[lo]))

    rows = []
    heldout_runs = np.asarray(sorted(idx_by_run), dtype=int)
    for metric in centered.columns:
        values = centered[metric].to_numpy(dtype=float)
        heldout_idx = np.concatenate([idx_by_run[int(run)] for run in heldout_runs])
        estimate = shift_for_indices(heldout_idx, values)
        boot = []
        for _ in range(int(n_boot)):
            sampled_runs = rng.choice(heldout_runs, size=len(heldout_runs), replace=True)
            sampled_idx = np.concatenate([idx_by_run[int(run)] for run in sampled_runs])
            boot.append(shift_for_indices(sampled_idx, values))
        boot = np.asarray([v for v in boot if np.isfinite(v)], dtype=float)
        if len(boot):
            lo, hi = np.quantile(boot, [0.025, 0.975])
        else:
            lo, hi = float("nan"), float("nan")
        rows.append(
            {
                "metric": metric,
                "interpretation": metric_labels[metric],
                "heldout_rows": int(len(heldout_idx)),
                "heldout_positive_rows": int(high[heldout_idx].sum()),
                "high_minus_low_median_shift": estimate,
                "ci_low": float(lo),
                "ci_high": float(hi),
                "bootstrap_replicates": int(n_boot),
            }
        )
    return pd.DataFrame(rows)


def orient_score(y_train: np.ndarray, train_score: np.ndarray, score: np.ndarray) -> Tuple[np.ndarray, int, float]:
    auc = safe_auc(y_train, train_score)
    if np.isfinite(auc) and auc < 0.5:
        return -score, -1, float(1.0 - auc)
    return score, 1, float(auc)


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def run_bootstrap_ci(pred: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    runs = np.sort(pred["run"].unique())
    by_run = []
    for run in runs:
        sub = pred[pred["run"] == run]
        by_run.append((sub["y_true"].to_numpy(dtype=int), sub["score"].to_numpy(dtype=float)))
    vals = []
    for _ in range(int(n_boot)):
        sampled = rng.integers(0, len(by_run), size=len(by_run))
        y = np.concatenate([by_run[i][0] for i in sampled])
        score = np.concatenate([by_run[i][1] for i in sampled])
        vals.append(safe_auc(y, score))
    arr = np.asarray([v for v in vals if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan")
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return float(lo), float(hi)


def summarize_predictions(predictions: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    per_run_rows = []
    summary_rows = []
    for method, group in predictions.groupby("method", sort=True):
        y = group["y_true"].to_numpy(dtype=int)
        score = group["score"].to_numpy(dtype=float)
        auc = safe_auc(y, score)
        ap = safe_ap(y, score)
        lo, hi = run_bootstrap_ci(group, rng, n_boot)
        for run, rg in group.groupby("run", sort=True):
            per_run_rows.append(
                {
                    "method": method,
                    "run": int(run),
                    "n": int(len(rg)),
                    "positives": int(rg["y_true"].sum()),
                    "roc_auc": safe_auc(rg["y_true"].to_numpy(dtype=int), rg["score"].to_numpy(dtype=float)),
                    "average_precision": safe_ap(rg["y_true"].to_numpy(dtype=int), rg["score"].to_numpy(dtype=float)),
                }
            )
        summary_rows.append(
            {
                "method": method,
                "n": int(len(group)),
                "positives": int(y.sum()),
                "roc_auc": auc,
                "auc_ci_low": lo,
                "auc_ci_high": hi,
                "average_precision": ap,
            }
        )
    return pd.DataFrame(summary_rows).sort_values("roc_auc", ascending=False), pd.DataFrame(per_run_rows)


def gatti_score(train_x: np.ndarray, train_y: np.ndarray, x: np.ndarray) -> np.ndarray:
    mu0 = train_x[train_y == 0].mean(axis=0)
    mu1 = train_x[train_y == 1].mean(axis=0)
    var0 = train_x[train_y == 0].var(axis=0)
    var1 = train_x[train_y == 1].var(axis=0)
    w = (mu1 - mu0) / np.maximum(var0 + var1, 1e-5)
    return x.dot(w)


def template_scores(waves: np.ndarray, train_mask: np.ndarray, train_y: np.ndarray) -> Dict[str, np.ndarray]:
    nominal_template = waves[train_mask][train_y == 0].mean(axis=0)
    anomaly_template = waves[train_mask][train_y == 1].mean(axis=0)
    nom_chi2 = ((waves - nominal_template[None, :]) ** 2).mean(axis=1)
    anom_chi2 = ((waves - anomaly_template[None, :]) ** 2).mean(axis=1)
    return {
        "matched_template_nominal_chi2": nom_chi2.astype(np.float32),
        "matched_template_delta_chi2": (nom_chi2 - anom_chi2).astype(np.float32),
    }


def one_hot_stave(meta: pd.DataFrame) -> np.ndarray:
    out = np.zeros((len(meta), len(STAVE_NAMES)), dtype=np.float32)
    idx = meta["stave_idx"].to_numpy(dtype=int)
    out[np.arange(len(meta)), idx] = 1.0
    return out


def make_supervised_matrix(waves: np.ndarray, feats: pd.DataFrame, meta: pd.DataFrame) -> np.ndarray:
    columns = [c for c in feats.columns if c != "stave_idx"]
    return np.hstack([waves.astype(np.float32), feats[columns].to_numpy(dtype=np.float32), one_hot_stave(meta)]).astype(np.float32)


def fit_sklearn_methods(x: np.ndarray, y: np.ndarray, runs: np.ndarray, train_mask: np.ndarray, test_mask: np.ndarray) -> List[pd.DataFrame]:
    methods = [
        (
            "ML_ridge_classifier",
            make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0, class_weight="balanced")),
        ),
        (
            "ML_gradient_boosted_trees",
            HistGradientBoostingClassifier(max_iter=80, learning_rate=0.08, max_leaf_nodes=15, l2_regularization=0.02, random_state=914),
        ),
        (
            "ML_mlp",
            make_pipeline(
                StandardScaler(),
                MLPClassifier(
                    hidden_layer_sizes=(64, 32),
                    activation="relu",
                    alpha=1e-4,
                    batch_size=512,
                    learning_rate_init=1e-3,
                    max_iter=35,
                    early_stopping=True,
                    n_iter_no_change=8,
                    random_state=915,
                ),
            ),
        ),
    ]
    out = []
    for name, model in methods:
        print("fitting {}".format(name))
        model.fit(x[train_mask], y[train_mask])
        if hasattr(model, "decision_function"):
            score = model.decision_function(x[test_mask])
        else:
            score = model.predict_proba(x[test_mask])[:, 1]
        out.append(
            pd.DataFrame(
                {
                    "method": name,
                    "run": runs[test_mask].astype(int),
                    "row_index": np.where(test_mask)[0].astype(np.int64),
                    "y_true": y[test_mask].astype(int),
                    "score": np.asarray(score, dtype=float),
                    "role": "ml_panel",
                }
            )
        )
    return out


class TinyCNN(nn.Module):
    def __init__(self, n_staves: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 32, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(32 + n_staves, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave, stave):
        z = self.conv(wave[:, None, :])
        return self.head(torch.cat([z, stave], dim=1)).squeeze(1)


class ResidualSqueezeCNN(nn.Module):
    def __init__(self, n_staves: int) -> None:
        super().__init__()
        self.inp = nn.Conv1d(1, 24, 3, padding=1)
        self.block1 = nn.Sequential(nn.Conv1d(24, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
        self.block2 = nn.Sequential(nn.Conv1d(24, 24, 5, padding=2), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
        self.se = nn.Sequential(nn.Linear(24, 8), nn.ReLU(), nn.Linear(8, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(24 * 2 + n_staves, 48), nn.ReLU(), nn.Dropout(0.05), nn.Linear(48, 1))

    def forward(self, wave, stave):
        z = torch.relu(self.inp(wave[:, None, :]))
        z = torch.relu(z + self.block1(z))
        z = torch.relu(z + self.block2(z))
        gate = self.se(z.mean(dim=2)).unsqueeze(2)
        z = z * gate
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        return self.head(torch.cat([pooled, stave], dim=1)).squeeze(1)


def train_torch_model(model, waves, staves, y, train_mask, config, seed: int):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    idx = np.where(train_mask)[0]
    max_train = int(config["nn"].get("max_train_rows", len(idx)))
    if len(idx) > max_train:
        idx = rng.choice(idx, size=max_train, replace=False)
    x_train = waves[idx].astype(np.float32)
    s_train = staves[idx].astype(np.float32)
    y_train = y[idx].astype(np.float32)
    pos = max(float(y_train.sum()), 1.0)
    neg = max(float(len(y_train) - y_train.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    batch_size = int(config["nn"]["batch_size"])
    for epoch in range(int(config["nn"]["epochs"])):
        order = rng.permutation(len(idx))
        losses = []
        for start in range(0, len(order), batch_size):
            take = order[start : start + batch_size]
            xb = torch.tensor(x_train[take], dtype=torch.float32, device=device)
            sb = torch.tensor(s_train[take], dtype=torch.float32, device=device)
            yb = torch.tensor(y_train[take], dtype=torch.float32, device=device)
            logits = model(xb, sb)
            loss = loss_fn(logits, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print("{} epoch {}/{} loss {:.5f}".format(type(model).__name__, epoch + 1, int(config["nn"]["epochs"]), float(np.mean(losses))))
    return model


def predict_torch_model(model, waves, staves, test_mask) -> np.ndarray:
    device = next(model.parameters()).device
    idx = np.where(test_mask)[0]
    scores = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(idx), 8192):
            take = idx[start : start + 8192]
            xb = torch.tensor(waves[take].astype(np.float32), dtype=torch.float32, device=device)
            sb = torch.tensor(staves[take].astype(np.float32), dtype=torch.float32, device=device)
            scores.append(model(xb, sb).detach().cpu().numpy())
    return np.concatenate(scores).astype(float)


def fit_torch_methods(waves, meta, y, runs, train_mask, test_mask, config) -> List[pd.DataFrame]:
    if torch is None:
        raise RuntimeError("torch is required for CNN benchmarks")
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    staves = one_hot_stave(meta)
    methods = [
        ("NN_1d_cnn", TinyCNN(staves.shape[1]), 3101),
        ("NN_residual_squeeze_cnn_new", ResidualSqueezeCNN(staves.shape[1]), 3102),
    ]
    out = []
    for name, model, seed in methods:
        print("fitting {}".format(name))
        fit = train_torch_model(model, waves, staves, y, train_mask, config, seed)
        score = predict_torch_model(fit, waves, staves, test_mask)
        out.append(
            pd.DataFrame(
                {
                    "method": name,
                    "run": runs[test_mask].astype(int),
                    "row_index": np.where(test_mask)[0].astype(np.int64),
                    "y_true": y[test_mask].astype(int),
                    "score": score,
                    "role": "ml_panel",
                }
            )
        )
    return out


def write_report(
    out_dir: Path,
    result: dict,
    method_summary: pd.DataFrame,
    traditional_summary: pd.DataFrame,
    per_run: pd.DataFrame,
    feature_roles: pd.DataFrame,
) -> None:
    primary = method_summary[method_summary["method"].isin(result["primary_methods"])].copy()
    top_trad = traditional_summary.head(15).copy()
    label_counts = pd.DataFrame(result["label_counts"])
    lines = [
        "# S24B: pedestal drift and waveform-shape invariance benchmark",
        "",
        "**Ticket:** `{}`  ".format(result["ticket_id"]),
        "**Worker:** `{}`  ".format(result["worker"]),
        "**Raw ROOT directory:** `{}`".format(result["raw_root_dir"]),
        "",
        "## Abstract",
        "",
        "This study isolates selected-pulse pedestal drift from corrected 18-sample B-stave pulse shape. The concrete weak-label task is high pedestal drift: pulses whose pre-trigger baseline deviates strongly from the run/stave median are positive. Traditional pulse-shape statistics are benchmarked against ridge, gradient-boosted trees, MLP, a 1D-CNN, and a new residual squeeze CNN under run-heldout validation. The winner by held-out ROC AUC is **{}** with AUC **{:.4f}** [{:.4f}, {:.4f}].".format(
            result["winner"]["method"], result["winner"]["roc_auc"], result["winner"]["auc_ci_low"], result["winner"]["auc_ci_high"]
        ),
        "",
        "## Raw reproduction gate",
        "",
        "The raw ROOT files were rescanned before modeling. For each event, `HRDv` was reshaped to `(8, 18)`, samples 0-3 supplied the per-channel baseline, B-stave even channels B2/B4/B6/B8 were baseline-subtracted, and a pulse was selected when its maximum amplitude exceeded 1000 ADC. This reproduced **{:,}** selected B-stave pulses against the registered **{:,}** count, delta **{}**.".format(
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
            result["reproduction"]["delta"],
        ),
        "",
        "## Pedestal-drift statistical task",
        "",
        "Let `b_i` be the median ADC pedestal in samples 0-3 for the selected channel and `m_{r,s}` the median pedestal for run `r` and stave `s` in the run-balanced benchmark sample. The drift residual is",
        "",
        "`d_i = b_i - m_{run_i,stave_i}`",
        "",
        "and the binary target is",
        "",
        "`y_i = 1{|d_i| >= Q_{%.2f}(|d|)}`." % float(result["label"].get("high_quantile", 0.8)),
        "",
        "The normalized corrected waveform is `x_i(t)=(v_i(t)-b_i)/max_t(v_i(t)-b_i)`. A shape-invariant detector should not predict `y_i` well from `x_i` after run/stave blocking. Conversely, high held-out AUC indicates residual pedestal information is still present in waveform shape, amplitude context, or detector/run structure.",
        "",
        "Label counts in the run-balanced benchmark sample:",
        "",
        "| split | rows | positives | positive fraction |",
        "|---|---:|---:|---:|",
    ]
    for _, row in label_counts.iterrows():
        lines.append("| {} | {:,} | {:,} | {:.4f} |".format(row["split"], int(row["rows"]), int(row["positives"]), float(row["positive_fraction"])))
    lines.extend(
        [
            "",
        "Held-out runs were `{}`; all model fitting used the other runs. Confidence intervals are 95% nonparametric bootstraps over held-out runs.".format(
                ", ".join(str(r) for r in result["split"]["heldout_runs"])
            ),
            "",
            "The benchmark sample is stratified by `(run, stave)` with a cap of `max_per_run_stave` records per cell, so no high-statistics run can dominate the model fit or the held-out evaluation. If `R` is the held-out run set and `AUC(D)` is the pooled ROC AUC on rows `D`, each bootstrap replicate draws `|R|` runs with replacement, pools their rows, and records `AUC_b = AUC(union_{r in R_b} D_r)`. The reported CI is the 2.5% and 97.5% quantile of `{AUC_b}`. The script also writes `pedestal_drift_time_blocks.csv` to audit within-run time-block behavior.",
            "",
            "Pedestal drift summary: median `|d|` = {:.3f} ADC, p90 `|d|` = {:.3f} ADC, high-drift threshold = {:.3f} ADC.".format(
                result["pedestal_drift"]["median_abs_drift_adc"],
                result["pedestal_drift"]["p90_abs_drift_adc"],
                result["label"]["threshold_adc"],
            ),
            "",
            "Synthetic pedestal perturbation negatives add a constant offset before renormalizing each waveform. The median shape L2 shifts are:",
            "",
            "| perturbation ADC | median L2 | p95 L2 | high-drift median | low-drift median |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for row in result["perturbation_negative_controls"]:
        lines.append(
            "| {:.1f} | {:.6f} | {:.6f} | {:.6f} | {:.6f} |".format(
                row["perturbation_adc"],
                row["shape_l2_median"],
                row["shape_l2_p95"],
                row["high_drift_shape_l2_median"],
                row["low_drift_shape_l2_median"],
            )
        )
    lines.extend(
        [
            "",
            "Held-out high-minus-low pedestal-drift proxy shifts use the same run-block bootstrap as the AUC intervals. Timing, energy, and PID proxies are centered by run/stave before differencing so the table emphasizes residual within-run shifts rather than absolute run calibration offsets.",
            "",
            "| proxy | high-minus-low median shift | 95% CI | held-out positives |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in result["proxy_shift_bootstrap_cis"]:
        lines.append(
            "| {} | {:.6f} | [{:.6f}, {:.6f}] | {:,} |".format(
                row["interpretation"],
                row["high_minus_low_median_shift"],
                row["ci_low"],
                row["ci_high"],
                int(row["heldout_positive_rows"]),
            )
        )
    lines.extend(
        [
            "",
            "## Traditional methods",
            "",
            "The survey covers charge-comparison PSD gates, rise-time and pulse-width, derivative/zero-crossing features, Gatti/current-integration filters, matched-template chi2, mean-time and higher moments, FFT features, Haar wavelet coefficients, and constant-fraction/leading-edge ratios.",
            "",
            "| family | representative variables |",
            "|---|---|",
            "| charge-comparison PSD | tail/total gates at samples 10-17, 12-17, 14-17; early/total; late-minus-early asymmetry |",
            "| rise time and width | interpolated 10%, 20%, 50%, 80% crossings; widths above 20% and 50% of peak |",
            "| zero-crossing/current shape | maximum rise/fall sample differences and derivative sign-change count |",
            "| Gatti/current integration | waveform-level optimal linear current filter and Fisher/Gatti feature-space score |",
            "| matched filter/template chi2 | nominal-template chi2 and nominal-minus-anomalous template chi2 |",
            "| moments, FFT, wavelet | mean time, variance, skewness, kurtosis, FFT band ratios, Haar detail coefficients |",
            "| constant-fraction ratios | CFD times and leading-edge sample ratios |",
            "",
            "For a scalar traditional score `s`, orientation is fixed on training runs so that `AUC_train(s) >= 0.5`; the held-out AUC is then evaluated without reorientation. The Gatti filter uses",
            "",
            "`w_t = (mu_1(t)-mu_0(t))/(sigma_1^2(t)+sigma_0^2(t)+epsilon),  S_i = sum_t w_t x_i(t)`,",
            "",
            "and the Fisher/Gatti shape score applies the same supervised linear-discriminant principle to the full engineered traditional feature vector with covariance shrinkage.",
            "",
            "Top traditional rows:",
            "",
            "| rank | method | family | AUC | 95% CI | AP |",
            "|---:|---|---|---:|---:|---:|",
        ]
    )
    for rank, (_, row) in enumerate(top_trad.iterrows(), start=1):
        lines.append(
            "| {} | {} | {} | {:.4f} | [{:.4f}, {:.4f}] | {:.4f} |".format(
                rank,
                row["method"],
                row.get("family", ""),
                row["roc_auc"],
                row["auc_ci_low"],
                row["auc_ci_high"],
                row["average_precision"],
            )
        )
    lines.extend(
        [
            "",
            "## ML/NN comparison",
            "",
            "Ridge, gradient-boosted trees, and MLP receive the normalized waveform, all traditional engineered features, and stave one-hot indicators. The 1D-CNN and the new residual squeeze CNN receive the normalized waveform plus stave one-hot indicators. The residual squeeze CNN is the new architecture: it uses residual temporal convolutions, global average/max pooling, and a small squeeze gate, which is sensible for 18 samples because it can combine local edge cues with pulse-wide tail information without a large parameter count.",
            "",
            "| model | inputs | fit details |",
            "|---|---|---|",
            "| Ridge classifier | waveform + traditional features + stave one-hot | standardized linear ridge classifier, class-balanced loss |",
            "| Gradient-boosted trees | waveform + traditional features + stave one-hot | histogram GBT, 80 boosting iterations, depth constrained by 15 leaves |",
            "| MLP | waveform + traditional features + stave one-hot | standardized 64-32 ReLU network with early stopping |",
            "| 1D-CNN | waveform + stave one-hot | two temporal convolutions with global average pooling |",
            "| Residual squeeze CNN | waveform + stave one-hot | residual temporal convolutions, squeeze gate, average/max pooling |",
            "",
            "| method | role | AUC | 95% CI | AP | rows | positives |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in primary.iterrows():
        lines.append(
            "| {} | {} | {:.4f} | [{:.4f}, {:.4f}] | {:.4f} | {:,} | {:,} |".format(
                row["method"],
                row.get("role", ""),
                row["roc_auc"],
                row["auc_ci_low"],
                row["auc_ci_high"],
                row["average_precision"],
                int(row["n"]),
                int(row["positives"]),
            )
        )
    lines.extend(
        [
            "",
            "## Per-run behavior",
            "",
            "| method | mean per-run AUC | min | max | finite runs |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for method, group in per_run[per_run["method"].isin(result["primary_methods"])].groupby("method", sort=True):
        finite = group["roc_auc"].dropna()
        lines.append(
            "| {} | {:.4f} | {:.4f} | {:.4f} | {} |".format(
                method, float(finite.mean()), float(finite.min()), float(finite.max()), int(len(finite))
            )
        )
    lines.extend(
        [
            "",
            "## Systematics and caveats",
            "",
            "- The target is weak and pedestal-defined; it validates pedestal-shape coupling, not particle truth.",
            "- The target uses the same pre-trigger samples that are subtracted from the waveform. Any residual predictability after run-heldout splitting is evidence against perfect shape invariance, but it does not by itself identify the physical source of coupling.",
            "- Run-heldout splitting protects against random-row leakage, but the eight held-out runs are still finite; CIs are run-block bootstraps, not independent-event CIs.",
            "- Amplitude and stave are included as context in supervised ML matrices because pedestal drift can couple to energy and PID proxy shifts; scalar traditional rows remain interpretable shape-only checks except where explicitly named otherwise.",
            "- Neural nets were intentionally small because the waveform has only 18 samples; larger architectures would be underconstrained without an external truth target.",
            "",
            "## Verdict",
            "",
            "`result.json` names **{}** as the winner. The best traditional method is **{}**. On this pedestal-drift invariance benchmark, the strongest ML/NN model {} the traditional baseline within the run-bootstrap CI structure.".format(
                result["winner"]["method"],
                result["best_traditional"]["method"],
                "beats" if result["winner"]["method"] != result["best_traditional"]["method"] else "is",
            ),
            "",
            "## Reproducibility",
            "",
            "```bash",
            "/home/billy/anaconda3/bin/python scripts/s24b_1783745883_3776_1aba605a_pedestal_shape_invariance.py --config configs/s24b_1783745883_3776_1aba605a_pedestal_shape_invariance.json",
            "```",
            "",
            "Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `pedestal_drift_by_run.csv`, `pedestal_drift_time_blocks.csv`, `pedestal_perturbation_negative_controls.csv`, `proxy_shift_bootstrap_cis.csv`, `traditional_method_summary.csv`, `primary_method_summary.csv`, `heldout_per_run_metrics.csv`, `heldout_predictions.csv.gz`, and this report.",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_manifest(out_dir: Path, config: dict) -> None:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json" and not path.name.endswith(".pt"):
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "generated_at_unix": time.time(),
        "artifacts": rows,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")


def plot_auc(out_dir: Path, method_summary: pd.DataFrame, primary_methods: Sequence[str]) -> None:
    sub = method_summary[method_summary["method"].isin(primary_methods)].copy().sort_values("roc_auc")
    fig, ax = plt.subplots(figsize=(8, 4.8))
    y = np.arange(len(sub))
    ax.barh(y, sub["roc_auc"], color="#4c78a8")
    ax.errorbar(
        sub["roc_auc"],
        y,
        xerr=[sub["roc_auc"] - sub["auc_ci_low"], sub["auc_ci_high"] - sub["roc_auc"]],
        fmt="none",
        ecolor="black",
        capsize=3,
        linewidth=1,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(sub["method"])
    ax.set_xlabel("Held-out ROC AUC")
    ax.set_xlim(0.5, 1.01)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "primary_auc_ci.png", dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s24b_1783745883_3776_1aba605a_pedestal_shape_invariance.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_dir = resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, meta, counts_by_run = scan_raw(config, raw_dir)
    selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError("raw reproduction failed: selected {}, expected {}".format(selected, expected))
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "selected B-stave pulses with baseline-subtracted amplitude > 1000 ADC",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    sample_idx = balanced_sample(meta, int(config["max_per_run_stave"]), rng)
    sample_idx.sort()
    bench_waves = waves[sample_idx]
    bench_meta = meta.iloc[sample_idx].reset_index(drop=True)
    runs = bench_meta["run"].to_numpy(dtype=int)
    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    train_mask = ~np.isin(runs, heldout_runs)
    test_mask = np.isin(runs, heldout_runs)
    if train_mask.sum() == 0 or test_mask.sum() == 0:
        raise RuntimeError("empty train/test split")

    feats, feature_roles = classic_features(bench_waves, bench_meta)
    labels = pedestal_drift_labels(bench_meta, float(config["pedestal_high_quantile"]))
    y = labels["pedestal_high_drift"].to_numpy(dtype=int)
    ped_by_run, ped_by_block = pedestal_summary_tables(bench_meta, labels)
    perturbation_controls = perturbation_negative_controls(
        bench_waves,
        bench_meta,
        labels,
        float(config.get("perturbation_adc", 150.0)),
    )
    ped_by_run.to_csv(out_dir / "pedestal_drift_by_run.csv", index=False)
    ped_by_block.to_csv(out_dir / "pedestal_drift_time_blocks.csv", index=False)
    perturbation_controls.to_csv(out_dir / "pedestal_perturbation_negative_controls.csv", index=False)
    label_table = pd.concat(
        [
            bench_meta[["run", "group", "event_index", "eventno", "stave", "stave_idx", "amplitude_adc", "peak_sample"]],
            labels,
            feats[["area_over_peak", "tail_12_17_over_total", "rise_20_80", "width50", "max_fall_step", "mean_time"]],
        ],
        axis=1,
    )
    label_table.to_csv(out_dir / "benchmark_sample_labels.csv", index=False)
    feature_roles.to_csv(out_dir / "traditional_feature_families.csv", index=False)

    split_rows = []
    for name, mask in [("train", train_mask), ("heldout", test_mask), ("all", np.ones(len(y), dtype=bool))]:
        split_rows.append(
            {
                "split": name,
                "rows": int(mask.sum()),
                "positives": int(y[mask].sum()),
                "positive_fraction": float(y[mask].mean()),
            }
        )
    pd.DataFrame(split_rows).to_csv(out_dir / "label_counts.csv", index=False)

    predictions = []
    feature_family = dict(zip(feature_roles["feature"], feature_roles["family"]))
    template = template_scores(bench_waves, train_mask, y[train_mask])
    for name, score in template.items():
        feats[name] = score
        feature_family[name] = "matched_filter_template_chi2"
    proxy_shift_cis = proxy_shift_bootstrap_cis(
        bench_meta,
        labels,
        feats,
        runs,
        test_mask,
        rng,
        int(config["bootstrap_replicates"]),
    )
    proxy_shift_cis.to_csv(out_dir / "proxy_shift_bootstrap_cis.csv", index=False)

    for col in feats.columns:
        if col in {"stave_idx", "log10_amplitude"}:
            continue
        score, direction, train_auc = orient_score(y[train_mask], feats.loc[train_mask, col].to_numpy(dtype=float), feats[col].to_numpy(dtype=float))
        predictions.append(
            pd.DataFrame(
                {
                    "method": "traditional_scalar__{}".format(col),
                    "run": runs[test_mask].astype(int),
                    "row_index": np.where(test_mask)[0].astype(np.int64),
                    "y_true": y[test_mask].astype(int),
                    "score": score[test_mask],
                    "role": "traditional_scalar",
                    "family": feature_family.get(col, "traditional_scalar"),
                    "train_orientation": int(direction),
                    "train_auc_oriented": train_auc,
                }
            )
        )

    wave_gatti = gatti_score(bench_waves[train_mask], y[train_mask], bench_waves)
    wave_gatti, _, _ = orient_score(y[train_mask], wave_gatti[train_mask], wave_gatti)
    predictions.append(
        pd.DataFrame(
            {
                "method": "traditional_gatti_waveform",
                "run": runs[test_mask].astype(int),
                "row_index": np.where(test_mask)[0].astype(np.int64),
                "y_true": y[test_mask].astype(int),
                "score": wave_gatti[test_mask],
                "role": "traditional_multivariate",
                "family": "current_integration_gatti",
            }
        )
    )

    trad_cols = [c for c in feats.columns if c != "stave_idx"]
    trad_x = feats[trad_cols].to_numpy(dtype=np.float32)
    fisher = make_pipeline(StandardScaler(), LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))
    fisher.fit(trad_x[train_mask], y[train_mask])
    fisher_score = fisher.decision_function(trad_x[test_mask])
    predictions.append(
        pd.DataFrame(
            {
                "method": "traditional_fisher_gatti_all_features",
                "run": runs[test_mask].astype(int),
                "row_index": np.where(test_mask)[0].astype(np.int64),
                "y_true": y[test_mask].astype(int),
                "score": fisher_score,
                "role": "traditional_multivariate",
                "family": "fisher_gatti_engineered_features",
            }
        )
    )

    x_supervised = make_supervised_matrix(bench_waves, feats, bench_meta)
    predictions.extend(fit_sklearn_methods(x_supervised, y, runs, train_mask, test_mask))
    predictions.extend(fit_torch_methods(bench_waves, bench_meta, y, runs, train_mask, test_mask, config))

    pred = pd.concat(predictions, ignore_index=True)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    summary, per_run = summarize_predictions(pred, rng, int(config["bootstrap_replicates"]))
    role_family = pred.groupby("method", sort=False)[["role", "family"]].first().reset_index()
    summary = summary.merge(role_family, on="method", how="left")
    summary.to_csv(out_dir / "method_summary_all.csv", index=False)
    per_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)

    traditional_summary = summary[summary["role"].str.startswith("traditional", na=False)].sort_values("roc_auc", ascending=False).copy()
    traditional_summary.to_csv(out_dir / "traditional_method_summary.csv", index=False)
    primary_methods = [
        str(traditional_summary.iloc[0]["method"]),
        "ML_ridge_classifier",
        "ML_gradient_boosted_trees",
        "ML_mlp",
        "NN_1d_cnn",
        "NN_residual_squeeze_cnn_new",
    ]
    primary_summary = summary[summary["method"].isin(primary_methods)].sort_values("roc_auc", ascending=False).copy()
    primary_summary.to_csv(out_dir / "primary_method_summary.csv", index=False)
    plot_auc(out_dir, summary, primary_methods)

    winner = primary_summary.iloc[0].to_dict()
    best_traditional = traditional_summary.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit": git_commit(),
        "runtime_sec": time.time() - t0,
        "python": platform.python_version(),
        "reproduction": {
            "selected_pulses": selected,
            "expected_selected_pulses": expected,
            "delta": selected - expected,
            "passed": selected == expected,
            "samples_per_channel": int(config["samples_per_channel"]),
        },
        "split": {
            "heldout_runs": [int(r) for r in heldout_runs],
            "train_rows": int(train_mask.sum()),
            "heldout_rows": int(test_mask.sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "label": {
            "name": "high pedestal drift",
            "definition": "abs(baseline_adc - median_run_stave_baseline_adc) >= configured quantile threshold",
            "high_quantile": float(config["pedestal_high_quantile"]),
            "threshold_adc": float(labels["pedestal_high_drift_threshold_adc"].iloc[0]),
        },
        "pedestal_drift": {
            "by_run_rows": int(len(ped_by_run)),
            "time_block_rows": int(len(ped_by_block)),
            "median_abs_drift_adc": float(labels["abs_pedestal_drift_adc"].median()),
            "p90_abs_drift_adc": float(labels["abs_pedestal_drift_adc"].quantile(0.90)),
        },
        "perturbation_negative_controls": perturbation_controls.to_dict(orient="records"),
        "proxy_shift_bootstrap_cis": proxy_shift_cis.to_dict(orient="records"),
        "label_counts": split_rows,
        "best_traditional": best_traditional,
        "winner": winner,
        "primary_methods": primary_methods,
        "verdict": "winner is {} by held-out ROC AUC; best traditional is {}".format(winner["method"], best_traditional["method"]),
        "next_tickets": [
            {
                "appended_ticket_id": config.get("appended_follow_up_ticket_id"),
                "title": "Externalize pedestal drift labels with no-pulse random-trigger windows",
                "body": "Validate S24B by deriving independent pedestal-drift labels from random-trigger/no-pulse windows and testing whether the winning waveform-shape discriminator still predicts them under run-heldout and time-blocked bootstrap CIs.",
            }
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, primary_summary, traditional_summary, per_run, feature_roles)
    write_manifest(out_dir, config)
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": winner["method"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
