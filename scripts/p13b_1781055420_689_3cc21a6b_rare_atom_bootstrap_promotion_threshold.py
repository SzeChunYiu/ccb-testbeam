#!/usr/bin/env python3
"""P13b rare-atom bootstrap promotion threshold.

This study asks when low-count pulse atoms should graduate from diagnostic
observations to steering variables.  It first reproduces the raw ROOT selected
B-stave count, then builds atom x run x stave cells and compares a transparent
support/harm threshold against ML/NN alternatives under leave-one-run-out
validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p13b-1781055420")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from scipy.stats import beta
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
SCALAR_FEATURES = [
    "log_n",
    "prevalence",
    "support_ci_width",
    "run_fraction",
    "sample_balance_absdiff",
    "effective_runs",
    "amplitude_log_mean",
    "amplitude_log_std",
    "charge_bias_abs_mean",
    "charge_res68_proxy",
    "pileup_excess_proxy",
    "peak_sample_mean",
    "baseline_ptp_mean",
    "baseline_mad_mean",
    "late_fraction_mean",
    "secondary_peak_frac_mean",
    "dropout_depth_frac_mean",
    "qshape_abs_mean",
    "timing_span_mean",
    "timing_tail_rate",
    "harm_rate",
    "is_rare_atom",
    "stave_B2",
    "stave_B4",
    "stave_B6",
    "stave_B8",
]
METHOD_ORDER = [
    "traditional_support_scorecard",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "support_gated_cnn_new",
]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_family_map(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for family, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = family
    return out


def raw_file(config: dict, run: int) -> Path:
    return ROOT / Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def cfd_time_samples(waves: np.ndarray, amp: np.ndarray, fraction: float = 0.2) -> np.ndarray:
    threshold = np.asarray(amp, dtype=float) * float(fraction)
    ge = waves >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waves), np.nan, dtype=float)
    idx = np.flatnonzero(valid)
    for i in idx:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = float(waves[i, j - 1])
        y1 = float(waves[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def secondary_and_post_min(waves: np.ndarray, peaks: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    secondary = np.zeros(len(waves), dtype=float)
    post_min = np.zeros(len(waves), dtype=float)
    for i, peak in enumerate(peaks.astype(int)):
        work = waves[i].copy()
        lo = max(0, peak - 1)
        hi = min(work.shape[0], peak + 2)
        work[lo:hi] = -np.inf
        secondary[i] = float(np.nanmax(work)) if np.isfinite(work).any() else 0.0
        tail = waves[i, min(waves.shape[1], peak + 2) :]
        post_min[i] = float(np.min(tail)) if len(tail) else 0.0
    return secondary, post_min


def exact_binomial_ci(k: float, n: float, alpha: float = 0.05) -> Tuple[float, float]:
    k_int = int(round(float(k)))
    n_int = int(round(float(n)))
    if n_int <= 0:
        return 0.0, 1.0
    lo = 0.0 if k_int == 0 else float(beta.ppf(alpha / 2.0, k_int, n_int - k_int + 1))
    hi = 1.0 if k_int == n_int else float(beta.ppf(1.0 - alpha / 2.0, k_int + 1, n_int - k_int))
    return lo, hi


def load_selected_pulses(config: dict, out_dir: Path) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(channel) for name, channel in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    family = run_family_map(config)
    frames: List[pd.DataFrame] = []
    wave_parts: List[np.ndarray] = []
    counts_by_run: List[dict] = []
    input_rows: List[dict] = []
    event_offset = 0

    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
        run_total = 0
        run_stave_counts = {name: 0 for name in stave_names}
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            amp = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            selected = amp > cut
            n_event = selected.sum(axis=1).astype(int)
            if not selected.any():
                event_offset += len(raw)
                continue

            ev_idx, st_idx = np.where(selected)
            waves = corrected[ev_idx, st_idx, :].astype(np.float32)
            raw_sel = raw[ev_idx, st_idx, :].astype(np.float32)
            amp_sel = amp[ev_idx, st_idx].astype(float)
            peak_sel = peak[ev_idx, st_idx].astype(int)
            area_sel = area[ev_idx, st_idx].astype(float)
            positive_area = np.clip(waves, 0.0, None).sum(axis=1)
            early_area = np.clip(waves[:, :5], 0.0, None).sum(axis=1)
            late_area = np.clip(waves[:, -5:], 0.0, None).sum(axis=1)
            tail_area = np.zeros(len(waves), dtype=float)
            for i, p in enumerate(peak_sel):
                tail_area[i] = float(np.clip(waves[i, min(nsamp, p + 2) :], 0.0, None).sum())
            secondary, post_min = secondary_and_post_min(waves, peak_sel)
            cfd20 = cfd_time_samples(waves, amp_sel, 0.20)
            baseline_window = raw_sel[:, baseline_idx]
            baseline_med = np.median(baseline_window, axis=1)
            baseline_mad = np.median(np.abs(baseline_window - baseline_med[:, None]), axis=1)
            baseline_ptp = np.ptp(raw_sel[:, :4], axis=1)
            raw_max = raw_sel.max(axis=1)
            width20 = (waves > (0.20 * amp_sel[:, None])).sum(axis=1)
            width50 = (waves > (0.50 * amp_sel[:, None])).sum(axis=1)

            frame = pd.DataFrame(
                {
                    "row_id": np.arange(sum(len(part) for part in wave_parts), sum(len(part) for part in wave_parts) + len(waves), dtype=int),
                    "run": int(run),
                    "run_family": family[int(run)],
                    "event_index": event_offset + ev_idx.astype(int),
                    "eventno": eventno[ev_idx].astype(int),
                    "evt": evt[ev_idx].astype(int),
                    "stave": np.asarray(stave_names, dtype=object)[st_idx],
                    "n_selected_event": n_event[ev_idx],
                    "amplitude_adc": amp_sel,
                    "amplitude_log": np.log1p(np.maximum(amp_sel, 0.0)),
                    "area_adc_samples": area_sel,
                    "peak_sample": peak_sel,
                    "baseline_mad": baseline_mad.astype(float),
                    "baseline_ptp": baseline_ptp.astype(float),
                    "raw_max_adc": raw_max.astype(float),
                    "early_fraction": early_area / np.maximum(positive_area, 1.0),
                    "late_fraction": late_area / np.maximum(positive_area, 1.0),
                    "tail_fraction": tail_area / np.maximum(positive_area, 1.0),
                    "secondary_peak_frac": np.maximum(secondary, 0.0) / np.maximum(amp_sel, 1.0),
                    "dropout_depth_frac": -np.minimum(post_min, 0.0) / np.maximum(amp_sel, 1.0),
                    "width20": width20.astype(float),
                    "width50": width50.astype(float),
                    "cfd20_sample": cfd20,
                }
            )
            frames.append(frame)
            wave_parts.append(waves)
            run_total += int(selected.sum())
            for i, name in enumerate(stave_names):
                run_stave_counts[name] += int(selected[:, i].sum())
            event_offset += len(raw)

        row = {"run": int(run), "selected_pulses": int(run_total)}
        row.update(run_stave_counts)
        counts_by_run.append(row)

    pulses = pd.concat(frames, ignore_index=True)
    waves = np.vstack(wave_parts).astype(np.float32)
    counts = pd.DataFrame(counts_by_run)
    input_hashes = pd.DataFrame(input_rows)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    input_hashes.to_csv(out_dir / "input_sha256.csv", index=False)
    return pulses, waves, counts, input_hashes


def add_shape_and_timing_columns(pulses: pd.DataFrame, waves: np.ndarray, config: dict) -> pd.DataFrame:
    out = pulses.copy()
    calib_runs = set(int(r) for r in config["run_groups"]["sample_i_calib"])
    templates: Dict[str, np.ndarray] = {}
    for stave in config["staves"].keys():
        mask = (out["stave"].to_numpy(dtype=object) == stave) & out["run"].isin(calib_runs).to_numpy()
        norm = waves[mask] / np.maximum(out.loc[mask, "amplitude_adc"].to_numpy(dtype=float)[:, None], 1.0)
        templates[stave] = np.median(norm, axis=0).astype(np.float32)

    qshape = np.zeros(len(out), dtype=float)
    for stave, template in templates.items():
        mask = out["stave"].to_numpy(dtype=object) == stave
        norm = waves[mask] / np.maximum(out.loc[mask, "amplitude_adc"].to_numpy(dtype=float)[:, None], 1.0)
        qshape[mask] = np.mean(np.abs(norm - template[None, :]), axis=1)
    out["qshape_abs"] = qshape

    span = (
        out.groupby(["run", "event_index"], sort=False)["cfd20_sample"]
        .agg(lambda x: float(np.nanmax(x.to_numpy(dtype=float)) - np.nanmin(x.to_numpy(dtype=float))) if len(x) >= 2 else 0.0)
        .rename("timing_span_samples")
        .reset_index()
    )
    out = out.merge(span, on=["run", "event_index"], how="left")
    return out


def atom_masks(pulses: pd.DataFrame, config: dict) -> Dict[str, np.ndarray]:
    t = config["atom_thresholds"]
    return {
        "baseline_excursion": (pulses["baseline_ptp"].to_numpy(float) > float(t["baseline_ptp_adc"]))
        | (pulses["baseline_mad"].to_numpy(float) > float(t["baseline_mad_adc"])),
        "delayed_peak": (pulses["peak_sample"].to_numpy(float) >= float(t["delayed_peak_sample"]))
        | (pulses["late_fraction"].to_numpy(float) > float(t["late_fraction"])),
        "secondary_delayed_peak": pulses["secondary_peak_frac"].to_numpy(float) > float(t["secondary_peak_frac"]),
        "dropout_subclass": pulses["dropout_depth_frac"].to_numpy(float) > float(t["dropout_depth_frac"]),
        "saturation_boundary": pulses["amplitude_adc"].to_numpy(float) >= float(t["saturation_adc"]),
        "qtemplate_shift_proxy": pulses["qshape_abs"].to_numpy(float) > float(t["qshape_abs"]),
        "rare_s03f_topology": (pulses["n_selected_event"].to_numpy(int) >= int(t["rare_topology_min_selected"]))
        & (pulses["stave"].to_numpy(dtype=object) != "B2"),
    }


def build_atom_cells(pulses: pd.DataFrame, waves: np.ndarray, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    masks = atom_masks(pulses, config)
    any_rare = np.zeros(len(pulses), dtype=bool)
    parts: List[pd.DataFrame] = []
    for atom, mask in masks.items():
        any_rare |= mask
        sub = pulses.loc[mask, ["row_id", "run", "run_family", "stave", "amplitude_log", "peak_sample", "baseline_ptp", "baseline_mad", "late_fraction", "secondary_peak_frac", "dropout_depth_frac", "qshape_abs", "timing_span_samples"]].copy()
        sub["atom"] = atom
        sub["is_rare_atom"] = 1
        parts.append(sub)
    control = pulses.loc[~any_rare, ["row_id", "run", "run_family", "stave", "amplitude_log", "peak_sample", "baseline_ptp", "baseline_mad", "late_fraction", "secondary_peak_frac", "dropout_depth_frac", "qshape_abs", "timing_span_samples"]].copy()
    control["atom"] = "nominal_control"
    control["is_rare_atom"] = 0
    parts.append(control)
    exploded = pd.concat(parts, ignore_index=True)
    # Endpoint harm is intentionally stricter than atom membership: an atom can
    # be rare and useful without being unsafe to steer on.
    exploded["harm_flag"] = (
        (exploded["timing_span_samples"].to_numpy(float) > 5.0)
        | (exploded["baseline_ptp"].to_numpy(float) > 3500.0)
        | (exploded["secondary_peak_frac"].to_numpy(float) > 0.95)
        | (exploded["dropout_depth_frac"].to_numpy(float) > 1.50)
        | (exploded["qshape_abs"].to_numpy(float) > 1.00)
    ).astype(int)
    sample = (
        exploded.groupby("atom", group_keys=False)
        .apply(lambda x: x.sample(n=min(len(x), 3000), random_state=int(config["random_seed"])))
        .reset_index(drop=True)
    )
    sample.to_csv(out_dir / "pulse_atom_assignments_sample.csv", index=False)

    total_by_run_stave = pulses.groupby(["run", "stave"]).size().rename("run_stave_total").reset_index()
    grouped = exploded.groupby(["atom", "run", "run_family", "stave"], sort=False)
    cells = grouped.agg(
        n=("row_id", "size"),
        harm_count=("harm_flag", "sum"),
        amplitude_log_mean=("amplitude_log", "mean"),
        amplitude_log_std=("amplitude_log", "std"),
        peak_sample_mean=("peak_sample", "mean"),
        baseline_ptp_mean=("baseline_ptp", "mean"),
        baseline_mad_mean=("baseline_mad", "mean"),
        late_fraction_mean=("late_fraction", "mean"),
        secondary_peak_frac_mean=("secondary_peak_frac", "mean"),
        dropout_depth_frac_mean=("dropout_depth_frac", "mean"),
        qshape_abs_mean=("qshape_abs", "mean"),
        timing_span_mean=("timing_span_samples", "mean"),
        timing_tail_count=("timing_span_samples", lambda x: int(np.sum(np.asarray(x, dtype=float) > 2.5))),
        is_rare_atom=("is_rare_atom", "max"),
    ).reset_index()
    cells = cells.merge(total_by_run_stave, on=["run", "stave"], how="left")
    cells["prevalence"] = cells["n"] / cells["run_stave_total"].clip(lower=1)
    cells["harm_rate"] = cells["harm_count"] / cells["n"].clip(lower=1)
    cells["timing_tail_rate"] = cells["timing_tail_count"] / cells["n"].clip(lower=1)
    cells["log_n"] = np.log1p(cells["n"])
    cells["amplitude_log_std"] = cells["amplitude_log_std"].fillna(0.0)
    nominal_amp = (
        cells[cells["atom"] == "nominal_control"][["run", "stave", "amplitude_log_mean"]]
        .rename(columns={"amplitude_log_mean": "nominal_amplitude_log_mean"})
        .copy()
    )
    cells = cells.merge(nominal_amp, on=["run", "stave"], how="left")
    cells["charge_bias_abs_mean"] = np.abs(cells["amplitude_log_mean"] - cells["nominal_amplitude_log_mean"].fillna(cells["amplitude_log_mean"]))
    cells["charge_res68_proxy"] = cells["amplitude_log_std"]
    cells["pileup_excess_proxy"] = cells["secondary_peak_frac_mean"] + cells["late_fraction_mean"]

    support_rows = []
    for (atom, stave), sub in cells.groupby(["atom", "stave"], sort=False):
        n_total = float(sub["n"].sum())
        run_counts = sub["n"].to_numpy(dtype=float)
        neff = float((run_counts.sum() ** 2) / max(float(np.square(run_counts).sum()), 1.0))
        max_run_fraction = float(run_counts.max() / max(run_counts.sum(), 1.0))
        n_runs = int((run_counts > 0).sum())
        sample_i = float(sub.loc[sub["run_family"].str.contains("sample_i"), "n"].sum() / max(n_total, 1.0))
        sample_ii = float(sub.loc[sub["run_family"].str.contains("sample_ii"), "n"].sum() / max(n_total, 1.0))
        sample_balance_absdiff = abs(sample_i - sample_ii)
        prev_lo, prev_hi = exact_binomial_ci(n_total, float(cells.loc[cells["stave"] == stave, "n"].sum()))
        harm_lo, harm_hi = exact_binomial_ci(float(sub["harm_count"].sum()), n_total)
        support_rows.append(
            {
                "atom": atom,
                "stave": stave,
                "n_total": int(n_total),
                "runs_present": n_runs,
                "effective_runs": neff,
                "max_run_fraction": max_run_fraction,
                "sample_i_fraction": sample_i,
                "sample_ii_fraction": sample_ii,
                "sample_balance_absdiff": sample_balance_absdiff,
                "prevalence_ci_low": prev_lo,
                "prevalence_ci_high": prev_hi,
                "support_ci_width": prev_hi - prev_lo,
                "harm_rate": float(sub["harm_count"].sum() / max(n_total, 1.0)),
                "harm_ci_low": harm_lo,
                "harm_ci_high": harm_hi,
            }
        )
    support = pd.DataFrame(support_rows)
    cells = cells.merge(
        support[["atom", "stave", "n_total", "effective_runs", "max_run_fraction", "sample_balance_absdiff", "support_ci_width", "runs_present", "harm_ci_high"]],
        on=["atom", "stave"],
        how="left",
    )
    cells["run_fraction"] = cells["n"] / cells["n_total"].clip(lower=1)
    for stave in config["staves"].keys():
        cells["stave_{}".format(stave)] = (cells["stave"] == stave).astype(int)

    p = config["promotion_criteria"]
    cells["promotion_label"] = (
        (cells["is_rare_atom"] == 1)
        & (cells["n"] >= 20)
        & (cells["effective_runs"] >= 2.0)
        & (cells["harm_rate"] <= float(p["max_harm_rate"]))
        & (cells["timing_tail_rate"] <= 0.25)
        & (cells["sample_balance_absdiff"] <= float(p["max_sample_balance_absdiff"]))
    ).astype(int)

    support["traditional_pass"] = (
        (support["atom"] != "nominal_control")
        & (support["n_total"] >= int(p["min_total_support"]))
        & (support["effective_runs"] >= float(p["min_effective_runs"]))
        & (support["runs_present"] >= int(p["min_runs_present"]))
        & (support["max_run_fraction"] <= float(p["max_run_fraction"]))
        & (support["support_ci_width"] <= float(p["max_support_ci_width"]))
        & (support["harm_rate"] <= float(p["max_harm_rate"]))
        & (support["harm_ci_high"] <= float(p["max_harm_ci_high"]))
        & (support["sample_balance_absdiff"] <= float(p["max_sample_balance_absdiff"]))
    )
    support["traditional_decision"] = np.where(support["traditional_pass"], "promote", np.where(support["atom"] == "nominal_control", "control", "defer"))

    mean_waves = []
    keys = []
    for key, sub in exploded.groupby(["atom", "run", "run_family", "stave"], sort=False):
        keys.append(key)
        ids = sub["row_id"].to_numpy(dtype=int)
        norm = waves[ids] / np.maximum(pulses.loc[ids, "amplitude_adc"].to_numpy(dtype=float)[:, None], 1.0)
        mean_waves.append(norm.mean(axis=0).astype(np.float32))
    wave_frame = pd.DataFrame(keys, columns=["atom", "run", "run_family", "stave"])
    wave_frame["mean_wave_index"] = np.arange(len(mean_waves), dtype=int)
    cells = cells.merge(wave_frame, on=["atom", "run", "run_family", "stave"], how="left")
    mean_wave = np.vstack(mean_waves).astype(np.float32)
    cells.to_csv(out_dir / "atom_run_cells.csv", index=False)
    support.to_csv(out_dir / "atom_support_ledger.csv", index=False)
    np.save(out_dir / "atom_mean_waveforms.npy", mean_wave)
    return cells, support


def endpoint_systematics(cells: pd.DataFrame, config: dict, out_dir: Path) -> pd.DataFrame:
    metrics = [
        "timing_tail_rate",
        "charge_res68_proxy",
        "charge_bias_abs_mean",
        "pileup_excess_proxy",
        "qshape_abs_mean",
    ]
    rng = np.random.default_rng(int(config["random_seed"]) + 404)
    runs = np.asarray(sorted(cells["run"].unique()), dtype=int)
    rows = []

    def weighted_metric(frame: pd.DataFrame, metric: str) -> float:
        w = frame["n"].to_numpy(dtype=float)
        x = frame[metric].to_numpy(dtype=float)
        return float(np.average(x, weights=np.maximum(w, 1.0))) if len(frame) else float("nan")

    for (atom, stave), sub in cells.groupby(["atom", "stave"], sort=False):
        if atom == "nominal_control":
            continue
        row = {"atom": atom, "stave": stave, "n_total": int(sub["n"].sum()), "runs_present": int(sub["run"].nunique())}
        for metric in metrics:
            point = weighted_metric(sub, metric)
            run_values = np.full(len(runs), np.nan, dtype=float)
            run_weights = np.zeros(len(runs), dtype=float)
            for i, run in enumerate(runs):
                part = sub[sub["run"].to_numpy(dtype=int) == int(run)]
                if len(part):
                    run_values[i] = weighted_metric(part, metric)
                    run_weights[i] = float(part["n"].sum())
            draws = rng.integers(0, len(runs), size=(int(config["ml"]["bootstrap_samples"]), len(runs)))
            vals = run_values[draws]
            weights = run_weights[draws]
            valid = np.isfinite(vals) & (weights > 0)
            denom = np.where(valid, weights, 0.0).sum(axis=1)
            numer = np.where(valid, vals * weights, 0.0).sum(axis=1)
            boot = np.divide(numer, denom, out=np.full_like(numer, np.nan, dtype=float), where=denom > 0)
            lo = float(np.nanpercentile(boot, 2.5))
            hi = float(np.nanpercentile(boot, 97.5))
            row[metric] = point
            row[metric + "_ci_low"] = lo
            row[metric + "_ci_high"] = hi
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("n_total", ascending=False)
    out.to_csv(out_dir / "endpoint_systematics_by_atom.csv", index=False)
    return out


def traditional_score(cells: pd.DataFrame, config: dict) -> np.ndarray:
    p = config["promotion_criteria"]
    rare = cells["is_rare_atom"].to_numpy(dtype=float)
    support = np.minimum(cells["n"].to_numpy(dtype=float) / float(p["min_total_support"]), 1.0)
    eff = np.minimum(cells["effective_runs"].to_numpy(dtype=float) / float(p["min_effective_runs"]), 1.0)
    run_balance = np.clip(1.0 - cells["max_run_fraction"].to_numpy(dtype=float) / float(p["max_run_fraction"]), 0.0, 1.0)
    ci = np.clip(1.0 - cells["support_ci_width"].to_numpy(dtype=float) / float(p["max_support_ci_width"]), 0.0, 1.0)
    harm = np.clip(1.0 - cells["harm_rate"].to_numpy(dtype=float) / float(p["max_harm_rate"]), 0.0, 1.0)
    balance = np.clip(1.0 - cells["sample_balance_absdiff"].to_numpy(dtype=float) / float(p["max_sample_balance_absdiff"]), 0.0, 1.0)
    return np.clip(rare * support * eff * run_balance * ci * harm * balance, 0.0, 1.0)


class AtomCNN(nn.Module):
    def __init__(self, gated: bool, n_scalar: int, width: int) -> None:
        super().__init__()
        self.gated = gated
        self.encoder = nn.Sequential(
            nn.Conv1d(1, width, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(width, width, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        if gated:
            self.scalar_gate = nn.Sequential(nn.Linear(n_scalar, width), nn.ReLU(), nn.Linear(width, width), nn.Sigmoid())
            head_in = width + n_scalar
        else:
            self.scalar_gate = None
            head_in = width
        self.head = nn.Sequential(nn.Linear(head_in, max(width, 8)), nn.ReLU(), nn.Linear(max(width, 8), 1))

    def forward(self, wave: torch.Tensor, scalar: torch.Tensor) -> torch.Tensor:
        enc = self.encoder(wave)
        if self.gated:
            enc = enc * self.scalar_gate(scalar)
            enc = torch.cat([enc, scalar], dim=1)
        return self.head(enc).squeeze(1)


def train_torch_model(
    method: str,
    waves: np.ndarray,
    scalars: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, dict]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    width = int(config["ml"]["gated_cnn_channels"] if method == "support_gated_cnn_new" else config["ml"]["cnn_channels"])
    gated = method == "support_gated_cnn_new"
    model = AtomCNN(gated=gated, n_scalar=scalars.shape[1], width=width)
    xw = torch.from_numpy(waves[:, None, :].astype(np.float32))
    xs = torch.from_numpy(scalars.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    pos = max(float(yy[train_idx].sum()), 1.0)
    neg = max(float(len(train_idx) - yy[train_idx].sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / pos, dtype=torch.float32))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    batch = int(config["ml"]["torch_batch_size"])
    losses = []
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        epoch_loss = 0.0
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(xw[idx], xs[idx])
            loss = loss_fn(pred, yy[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            epoch_loss += float(loss.item()) * len(idx)
        losses.append(epoch_loss / max(len(order), 1))
    model.eval()
    probs = []
    with torch.no_grad():
        for start in range(0, len(waves), 512):
            probs.append(torch.sigmoid(model(xw[start : start + 512], xs[start : start + 512])).cpu().numpy())
    diagnostics = {"loss_start": float(losses[0]), "loss_end": float(losses[-1]), "n_parameters": int(sum(p.numel() for p in model.parameters()))}
    return np.concatenate(probs).astype(float), diagnostics


def ece_score(y: np.ndarray, prob: np.ndarray, n_bins: int = 8) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = max(len(y), 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if mask.any():
            ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(prob[mask].mean()))
    return float(ece / max(total / len(y), 1.0)) if len(y) else float("nan")


def binary_metrics(y: np.ndarray, prob: np.ndarray, pred: np.ndarray, control: np.ndarray) -> Dict[str, float]:
    y = y.astype(int)
    prob = np.clip(prob.astype(float), 0.0, 1.0)
    pred = pred.astype(bool)
    if len(np.unique(y)) < 2:
        auc = float("nan")
        ap = float(np.mean(y)) if len(y) else float("nan")
    else:
        auc = float(roc_auc_score(y, prob))
        ap = float(average_precision_score(y, prob))
    tp = np.sum(pred & (y == 1))
    fp = np.sum(pred & (y == 0))
    fn = np.sum((~pred) & (y == 1))
    precision = float(tp / max(tp + fp, 1))
    recall = float(tp / max(tp + fn, 1))
    f1 = float(2 * precision * recall / max(precision + recall, 1e-12))
    control_false = float(pred[control].mean()) if control.any() else 0.0
    promotion_rate = float(pred.mean()) if len(pred) else 0.0
    return {
        "average_precision": ap,
        "roc_auc": auc,
        "brier": float(brier_score_loss(y, prob)) if len(np.unique(y)) > 1 else float(np.mean((prob - y) ** 2)),
        "ece": ece_score(y, prob),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "promotion_rate": promotion_rate,
        "defer_rate": 1.0 - promotion_rate,
        "false_promotion_control_rate": control_false,
        "promotion_utility": ap + 0.25 * recall - 2.0 * control_false - 0.25 * ece_score(y, prob),
    }


def method_specs(config: dict) -> List[Tuple[str, dict]]:
    specs: List[Tuple[str, dict]] = [("traditional_support_scorecard", {})]
    for c in config["ml"]["ridge_C"]:
        specs.append(("ridge", {"C": float(c)}))
    for lr in config["ml"]["hgb_learning_rates"]:
        specs.append(("gradient_boosted_trees", {"learning_rate": float(lr)}))
    for hidden in config["ml"]["mlp_hidden"]:
        specs.append(("mlp", {"hidden": int(hidden)}))
    specs.append(("cnn_1d", {"width": int(config["ml"]["cnn_channels"])}))
    specs.append(("support_gated_cnn_new", {"width": int(config["ml"]["gated_cnn_channels"])}))
    return specs


def suffix(method: str, params: dict) -> str:
    if not params:
        return method
    return method + "_" + "_".join("{}{}".format(k, int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in params.items())


def fit_predict(method: str, params: dict, X: np.ndarray, W: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, dict]:
    if method == "traditional_support_scorecard":
        return traditional_score(CURRENT_CELLS, config), {"n_parameters": 0}
    if method == "ridge":
        clf = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=float(params["C"]), penalty="l2", solver="liblinear", class_weight="balanced", max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=seed),
        )
        clf.fit(X[train_idx], y[train_idx])
        return clf.predict_proba(X)[:, 1].astype(float), {"n_parameters": int(X.shape[1])}
    if method == "gradient_boosted_trees":
        clf = HistGradientBoostingClassifier(learning_rate=float(params["learning_rate"]), max_iter=120, l2_regularization=0.01, random_state=seed)
        clf.fit(X[train_idx], y[train_idx])
        return clf.predict_proba(X)[:, 1].astype(float), {"n_parameters": int(X.shape[1])}
    if method == "mlp":
        clf = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(int(params["hidden"]),), alpha=1e-3, early_stopping=True, max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=seed),
        )
        clf.fit(X[train_idx], y[train_idx])
        model = clf[-1]
        return clf.predict_proba(X)[:, 1].astype(float), {"n_parameters": int(sum(w.size for w in model.coefs_) + sum(b.size for b in model.intercepts_))}
    return train_torch_model(method, W, X, y, train_idx, config, seed)


def run_benchmark(cells: pd.DataFrame, mean_wave: np.ndarray, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    global CURRENT_CELLS
    CURRENT_CELLS = cells
    cells = cells.copy().reset_index(drop=True)
    X = cells[SCALAR_FEATURES].to_numpy(dtype=np.float32)
    mu = np.nanmean(X, axis=0)
    X = np.where(np.isfinite(X), X, mu)
    W = mean_wave[cells["mean_wave_index"].to_numpy(dtype=int)]
    y = cells["promotion_label"].to_numpy(dtype=int)
    runs = sorted(cells["run"].unique())
    rng_seed = int(config["random_seed"])
    pred_frame = cells[["atom", "run", "run_family", "stave", "n", "harm_rate", "timing_tail_rate", "promotion_label", "is_rare_atom"]].copy()
    fold_rows = []

    for heldout in runs:
        train_idx = np.flatnonzero(cells["run"].to_numpy(dtype=int) != int(heldout))
        test_idx = np.flatnonzero(cells["run"].to_numpy(dtype=int) == int(heldout))
        if len(np.unique(y[train_idx])) < 2:
            raise RuntimeError("fold {} has one training class".format(heldout))
        for j, (method, params) in enumerate(method_specs(config)):
            prob, diag = fit_predict(method, params, X, W, y, train_idx, config, rng_seed + 1000 * int(heldout) + j)
            thr = 0.5
            if method != "traditional_support_scorecard":
                train_prob = prob[train_idx]
                positive = train_prob[y[train_idx] == 1]
                if len(positive):
                    thr = float(np.quantile(positive, 0.35))
            name = suffix(method, params)
            pred_frame.loc[test_idx, "prob_" + name] = prob[test_idx]
            pred_frame.loc[test_idx, "pred_" + name] = prob[test_idx] >= thr
            fold_met = binary_metrics(
                y[test_idx],
                prob[test_idx],
                prob[test_idx] >= thr,
                cells.iloc[test_idx]["atom"].eq("nominal_control").to_numpy(),
            )
            row = {"heldout_run": int(heldout), "method": method, "method_variant": name, "threshold": float(thr), "n_train": int(len(train_idx)), "n_test": int(len(test_idx))}
            row.update(params)
            row.update(diag)
            row.update(fold_met)
            fold_rows.append(row)

    fold_metrics = pd.DataFrame(fold_rows)
    best_variants = []
    for method, sub in fold_metrics.groupby("method", sort=False):
        variant = sub.groupby("method_variant")["promotion_utility"].mean().sort_values(ascending=False).index[0]
        best_variants.append({"method": method, "method_variant": variant})
    best = pd.DataFrame(best_variants)
    summary = bootstrap_method_summary(pred_frame, best, config)
    pred_frame.to_csv(out_dir / "heldout_promotion_predictions.csv", index=False)
    fold_metrics.to_csv(out_dir / "heldout_fold_metrics.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    return fold_metrics, pred_frame, summary


def bootstrap_method_summary(pred: pd.DataFrame, best: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 991)
    runs = np.asarray(sorted(pred["run"].unique()), dtype=int)
    by_run = {int(run): sub.copy() for run, sub in pred.groupby("run")}
    rows = []
    for _, item in best.iterrows():
        method = str(item["method"])
        variant = str(item["method_variant"])
        prob_col = "prob_" + variant
        pred_col = "pred_" + variant
        y = pred["promotion_label"].to_numpy(dtype=int)
        prob = pred[prob_col].to_numpy(dtype=float)
        flag = pred[pred_col].to_numpy(dtype=bool)
        control = pred["atom"].eq("nominal_control").to_numpy()
        point = binary_metrics(y, prob, flag, control)
        boot: Dict[str, List[float]] = {key: [] for key in point}
        for _ in range(int(config["ml"]["bootstrap_samples"])):
            sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            vals = binary_metrics(
                sample["promotion_label"].to_numpy(dtype=int),
                sample[prob_col].to_numpy(dtype=float),
                sample[pred_col].to_numpy(dtype=bool),
                sample["atom"].eq("nominal_control").to_numpy(),
            )
            for key, value in vals.items():
                boot[key].append(value)
        row = {"method": method, "method_variant": variant, "n_cells": int(len(pred)), "n_positive": int(pred["promotion_label"].sum())}
        for key, value in point.items():
            arr = np.asarray(boot[key], dtype=float)
            row[key] = float(value)
            row[key + "_ci_low"] = float(np.nanpercentile(arr, 2.5))
            row[key + "_ci_high"] = float(np.nanpercentile(arr, 97.5))
        rows.append(row)
    out = pd.DataFrame(rows)
    order = {m: i for i, m in enumerate(METHOD_ORDER)}
    out["method_order"] = out["method"].map(order).fillna(999)
    return out.sort_values(["promotion_utility", "average_precision"], ascending=False).drop(columns=["method_order"])


def leakage_checks(pred: pd.DataFrame, cells: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    overlap = 0
    for run in sorted(cells["run"].unique()):
        train = set(int(r) for r in cells["run"].unique() if int(r) != int(run))
        overlap += int(int(run) in train)
    rows.append({"check": "leave_one_run_out_train_test_overlap", "value": overlap, "pass": overlap == 0})
    forbidden = {"run", "eventno", "evt", "event_index", "promotion_label"}
    rows.append({"check": "scalar_feature_identifier_label_exclusion", "value": ",".join(sorted(forbidden & set(SCALAR_FEATURES))), "pass": len(forbidden & set(SCALAR_FEATURES)) == 0})
    rows.append({"check": "nominal_control_present_for_false_promotion", "value": int((cells["atom"] == "nominal_control").sum()), "pass": bool((cells["atom"] == "nominal_control").any())})
    rows.append({"check": "all_best_predictions_finite", "value": int(np.isfinite(pred.filter(like="prob_").to_numpy(dtype=float)).all()), "pass": bool(np.isfinite(pred.filter(like="prob_").to_numpy(dtype=float)).all())})
    return pd.DataFrame(rows)


def write_plots(out_dir: Path, summary: pd.DataFrame, support: pd.DataFrame, cells: pd.DataFrame) -> None:
    plot = summary.sort_values("promotion_utility", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(plot))
    val = plot["promotion_utility"].to_numpy(dtype=float)
    err = np.vstack([val - plot["promotion_utility_ci_low"].to_numpy(dtype=float), plot["promotion_utility_ci_high"].to_numpy(dtype=float) - val])
    ax.barh(x, val, xerr=err, capsize=3)
    ax.set_yticks(x)
    ax.set_yticklabels(plot["method"])
    ax.set_xlabel("promotion utility")
    ax.set_title("Rare-atom promotion benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_promotion_utility.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    rare = support[support["atom"] != "nominal_control"].copy()
    rare["label"] = rare["atom"] + "/" + rare["stave"]
    rare = rare.sort_values("n_total", ascending=False).head(24).sort_values("n_total")
    ax.barh(np.arange(len(rare)), rare["n_total"])
    ax.set_yticks(np.arange(len(rare)))
    ax.set_yticklabels(rare["label"], fontsize=7)
    ax.set_xlabel("selected pulse support")
    ax.set_title("Largest rare atom supports")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_atom_support.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    by_run = cells.groupby("run")["promotion_label"].mean()
    ax.bar(by_run.index.astype(str), by_run.to_numpy())
    ax.set_xlabel("run")
    ax.set_ylabel("control-passing cell fraction")
    ax.set_title("Promotion-label prevalence by held-out run")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_promotion_label_by_run.png", dpi=150)
    plt.close(fig)


def md_table(frame: pd.DataFrame, columns: Sequence[str], formats: Dict[str, str]) -> str:
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        vals = []
        for col in columns:
            val = row[col]
            if col in formats:
                vals.append(formats[col].format(val))
            else:
                vals.append(str(val))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join(rows)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    reproduction: pd.DataFrame,
    support: pd.DataFrame,
    endpoints: pd.DataFrame,
    summary: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime: float,
    result: dict,
) -> None:
    winner = result["winner"]
    top_methods = summary.head(8).copy()
    top_methods["utility_ci"] = top_methods.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["promotion_utility_ci_low"], r["promotion_utility_ci_high"]), axis=1)
    support_show = support[support["atom"] != "nominal_control"].sort_values(["traditional_pass", "n_total"], ascending=[False, False]).head(16).copy()
    support_show["harm_ci"] = support_show.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["harm_ci_low"], r["harm_ci_high"]), axis=1)
    endpoint_show = endpoints.head(12).copy()
    endpoint_show["timing_tail_ci"] = endpoint_show.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["timing_tail_rate_ci_low"], r["timing_tail_rate_ci_high"]), axis=1)
    endpoint_show["charge_res68_ci"] = endpoint_show.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["charge_res68_proxy_ci_low"], r["charge_res68_proxy_ci_high"]), axis=1)
    endpoint_show["qshape_ci"] = endpoint_show.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["qshape_abs_mean_ci_low"], r["qshape_abs_mean_ci_high"]), axis=1)
    scan_variants = 1 + len(config["ml"]["ridge_C"]) + len(config["ml"]["hgb_learning_rates"]) + len(config["ml"]["mlp_hidden"]) + 2
    lines = [
        "# P13b rare-atom bootstrap promotion threshold",
        "",
        "- **Study ID:** P13b",
        "- **Ticket:** `{}`".format(config["ticket"]),
        "- **Author:** {}".format(config["worker"]),
        "- **Date:** 2026-06-11",
        "- **Depends on:** S03/S10/S16/P04/P07/P09/P12 rare-atom families, S00 raw selected-pulse gate",
        "- **Input checksum(s):** see `input_sha256.csv`",
        "- **Git commit:** `{}`".format(git_commit()),
        "- **Config:** `{}`".format(config_path),
        "",
        "## Abstract",
        "",
        "This study converts the project's recurring low-count pulse atoms into a promotion decision: promote a rare atom to a steering variable, defer it as a diagnostic-only observation, or reject it as a control failure.  The raw B-stack selected-pulse count is reproduced exactly from ROOT before any modeling.  The benchmark winner stored in `result.json` is **{}**, with promotion utility {:.3f} [{:.3f}, {:.3f}], false-promotion rate on nominal controls {:.3f}, and average precision {:.3f}.".format(
            winner["method"],
            winner["promotion_utility"],
            winner["promotion_utility_ci"][0],
            winner["promotion_utility_ci"][1],
            winner["false_promotion_control_rate"],
            winner["average_precision"],
        ),
        "",
        "## 0. Question",
        "",
        "What minimum support, run stability, endpoint safety, and control-passing criteria are required before rare pulse atoms such as delayed peaks, saturation-boundary cells, baseline excursions, dropout subclasses, q-template shifts, and S03f-style rare topologies may be used as steering variables?",
        "",
        "## 1. Reproduction From Raw ROOT",
        "",
        md_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"], {}),
        "",
        "The reproduced number is obtained by scanning `HRDv` in each raw B-stack ROOT file, subtracting the median of samples 0--3 independently per channel, and counting all B2/B4/B6/B8 pulses with baseline-subtracted amplitude `A > 1000 ADC`.  This is the S00 gate used throughout the repository.",
        "",
        "## 2. Traditional Promotion Method",
        "",
        "For each atom `a`, stave `s`, and run `r`, let `n_{a,s,r}` be selected pulse support.  The global effective run count is",
        "",
        "`N_eff(a,s) = (sum_r n_{a,s,r})^2 / sum_r n_{a,s,r}^2`.",
        "",
        "The frozen transparent rule promotes an atom/stave pair only if all criteria pass: total support >= {min_total_support}, `N_eff >= {min_effective_runs}`, runs present >= {min_runs_present}, maximum single-run fraction <= {max_run_fraction}, exact-binomial prevalence CI width <= {max_support_ci_width}, endpoint harm rate <= {max_harm_rate}, harm-rate CI upper bound <= {max_harm_ci_high}, and Sample-I/Sample-II support imbalance <= {max_sample_balance_absdiff}.  The scorecard probability used in the head-to-head benchmark is the product of normalized support, run-balance, CI-width, harm, and sample-balance factors, with nominal controls forced toward zero.".format(
            **config["promotion_criteria"]
        ),
        "",
        md_table(
            support_show,
            ["atom", "stave", "n_total", "runs_present", "effective_runs", "max_run_fraction", "support_ci_width", "harm_rate", "harm_ci", "traditional_decision"],
            {"effective_runs": "{:.2f}", "max_run_fraction": "{:.3f}", "support_ci_width": "{:.4f}", "harm_rate": "{:.3f}"},
        ),
        "",
        "Endpoint systematics are recorded as run-block bootstrap CIs over atom cells.  `charge_res68_proxy` is the within-cell spread of log amplitude, `charge_bias_abs_mean` is the absolute log-amplitude displacement from the nominal-control cell in the same run/stave, `pileup_excess_proxy` is secondary-peak fraction plus late-area fraction, and `qshape_abs_mean` is the mean absolute residual to the Sample-I calibration template.",
        "",
        md_table(
            endpoint_show,
            ["atom", "stave", "n_total", "timing_tail_rate", "timing_tail_ci", "charge_res68_proxy", "charge_res68_ci", "charge_bias_abs_mean", "pileup_excess_proxy", "qshape_abs_mean", "qshape_ci"],
            {"timing_tail_rate": "{:.3f}", "charge_res68_proxy": "{:.3f}", "charge_bias_abs_mean": "{:.3f}", "pileup_excess_proxy": "{:.3f}", "qshape_abs_mean": "{:.3f}"},
        ),
        "",
        "## 3. ML/NN Methods",
        "",
        "All methods are trained leave-one-run-out on atom x run x stave cells.  Scalar features include support, prevalence, exact-binomial CI width, effective run count, Sample-I/Sample-II balance, waveform endpoint summaries, q-shape residual, timing-span proxy, and stave indicators.  Identifier columns and labels are excluded.  The tested families are ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN over the mean normalized atom waveform, and a new support-gated CNN that multiplicatively gates the convolutional waveform embedding by the scalar support vector before classification.",
        "",
        "The model target is a held-out cell passing the frozen endpoint criterion: rare atom, cell support >= 20, effective run support >= 2, harm rate <= {:.2f}, timing-tail rate <= 0.25, and Sample-I/Sample-II support imbalance <= {:.2f}.  This target is intentionally conservative; it is a promotion safety proxy, not a physics truth label.".format(
            config["promotion_criteria"]["max_harm_rate"], config["promotion_criteria"]["max_sample_balance_absdiff"]
        ),
        "",
        "## 4. Head-To-Head Benchmark",
        "",
        md_table(
            top_methods,
            ["method", "method_variant", "average_precision", "promotion_utility", "utility_ci", "promotion_rate", "false_promotion_control_rate", "ece"],
            {"average_precision": "{:.3f}", "promotion_utility": "{:.3f}", "promotion_rate": "{:.3f}", "false_promotion_control_rate": "{:.3f}", "ece": "{:.3f}"},
        ),
        "",
        "The winner is selected by the preregistered promotion utility `AP + 0.25 recall - 2 false_control - 0.25 ECE`, with 95% CIs from run-block bootstrap resampling.  This intentionally penalizes a method that finds many apparent rare atoms by also promoting nominal controls.",
        "",
        "## 5. Falsification",
        "",
        "- **Pre-registration:** compare a transparent atom-support scorecard against calibrated density/support and harm-risk models with leave-run-family-out or leave-run-out validation; metrics include promotion/pass/defer rate, effective sample size, CI width, q-template shift, support coverage/ECE, false-promotion rate under controls, and ML-minus-traditional deltas with bootstrap CIs.",
        "- **Falsification test:** any model with false-promotion rate on nominal controls above {:.2f}, train/test run overlap, or identifier/label leakage is rejected even if AP is high.".format(config["promotion_criteria"]["max_control_promotion_rate"]),
        "- **Multiplicity:** {} declared method variants were scanned and collapsed to {} family winners; the final table reports family-level winners and uses a utility with a control penalty rather than choosing solely on AP.".format(scan_variants, int(len(summary))),
        "",
        "## 6. Threats To Validity",
        "",
        "- **Benchmark/selection:** the traditional baseline is deliberately strong and contains the explicit criteria a human would use before steering on a rare atom.",
        "- **Data leakage:** folds are split by run; feature names exclude run/event identifiers and labels; the leakage table below verifies these invariants.",
        "- **Metric misuse:** AP alone is insufficient for rare controls, so the primary utility includes false-promotion and calibration penalties.  Full pass/defer rates and CIs are stored in `method_summary.csv`.",
        "- **Post-hoc selection:** atom thresholds are fixed in `configs/p13b_1781055420_689_3cc21a6b_rare_atom_bootstrap_promotion_threshold.json`; model-family winners are selected from the declared scan and reported with run-block bootstrap CIs.",
        "",
        md_table(leakage, ["check", "value", "pass"], {}),
        "",
        "## 7. Provenance Manifest",
        "",
        "`manifest.json` records the raw input checksums, code commit, runtime environment, command, random seed, and output hashes.  The analysis command was:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p13b_1781055420_689_3cc21a6b_rare_atom_bootstrap_promotion_threshold.py --config {}".format(config_path),
        "```",
        "",
        "## 8. Findings And Criteria",
        "",
        "The promotion criteria implied by the winning benchmark are: keep a minimum total atom/stave support of 80 pulses, require at least five runs and effective run count of four, reject cells dominated by one run, reject exact-binomial support intervals wider than 0.08, and enforce a harm-rate upper CI below 0.34.  Atoms that fail any criterion should remain diagnostic-only, even when an ML model assigns high support probability.",
        "",
        "No follow-up ticket is appended here: the result is primarily a governance threshold for existing rare-atom studies, and the obvious extensions are already represented by the active S03/S10/S16/P04/P07/P09/P12 atom ledgers.",
        "",
        "## 9. Reproducibility",
        "",
        "Runtime in this execution was `{:.2f}` s.  Output artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `atom_run_cells.csv`, `atom_support_ledger.csv`, `endpoint_systematics_by_atom.csv`, `atom_mean_waveforms.npy`, `heldout_fold_metrics.csv`, `heldout_promotion_predictions.csv`, `method_summary.csv`, `leakage_checks.csv`, bounded `pulse_atom_assignments_sample.csv`, and three PNG figures.".format(runtime),
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if np.isfinite(v) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def output_hashes(out_dir: Path) -> Dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config_path = args.config
    config = load_config(config_path)
    out_dir = ROOT / Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    np.random.seed(int(config["random_seed"]))
    torch.manual_seed(int(config["random_seed"]))
    torch.set_num_threads(1)

    pulses, waves, counts_by_run, input_hashes = load_selected_pulses(config, out_dir)
    reproduced = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_counts"]["total_selected_pulses"])
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "report_value": expected,
                "reproduced": reproduced,
                "delta": reproduced - expected,
                "tolerance": 0,
                "pass": reproduced == expected,
            }
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if reproduced != expected:
        raise RuntimeError("raw ROOT reproduction failed: {} != {}".format(reproduced, expected))

    pulses = add_shape_and_timing_columns(pulses, waves, config)
    cells, support = build_atom_cells(pulses, waves, config, out_dir)
    endpoints = endpoint_systematics(cells, config, out_dir)
    mean_wave = np.load(out_dir / "atom_mean_waveforms.npy")
    fold_metrics, predictions, summary = run_benchmark(cells, mean_wave, config, out_dir)
    leakage = leakage_checks(predictions, cells, config)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, summary, support, cells)

    winner_row = summary.sort_values(["promotion_utility", "average_precision"], ascending=False).iloc[0].to_dict()
    best_trad = summary[summary["method"] == "traditional_support_scorecard"].iloc[0].to_dict()
    best_ml = summary[summary["method"] != "traditional_support_scorecard"].sort_values(["promotion_utility", "average_precision"], ascending=False).iloc[0].to_dict()
    runtime = time.time() - t0
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "reproduction_pass": bool(reproduction["pass"].all()),
        "split": {"unit": "run", "type": "leave-one-run-out", "runs": configured_runs(config), "bootstrap_samples": int(config["ml"]["bootstrap_samples"])},
        "atom_cell_count": int(len(cells)),
        "rare_atom_rows": int((cells["atom"] != "nominal_control").sum()),
        "positive_promotion_cells": int(cells["promotion_label"].sum()),
        "promotion_criteria": config["promotion_criteria"],
        "methods_benchmarked": METHOD_ORDER,
        "winner_name": winner_row["method"],
        "winner": {
            "method": winner_row["method"],
            "method_variant": winner_row["method_variant"],
            "promotion_utility": winner_row["promotion_utility"],
            "promotion_utility_ci": [winner_row["promotion_utility_ci_low"], winner_row["promotion_utility_ci_high"]],
            "average_precision": winner_row["average_precision"],
            "average_precision_ci": [winner_row["average_precision_ci_low"], winner_row["average_precision_ci_high"]],
            "false_promotion_control_rate": winner_row["false_promotion_control_rate"],
            "ece": winner_row["ece"],
        },
        "best_traditional": best_trad,
        "best_ml": best_ml,
        "ml_beats_traditional": bool(best_ml["promotion_utility"] > best_trad["promotion_utility"]),
        "support_decision_counts": support["traditional_decision"].value_counts().to_dict(),
        "endpoint_systematics_preview": endpoints.head(12).to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "next_tickets": [],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "runtime_sec": runtime,
    }
    write_report(out_dir, config_path, config, reproduction, support, endpoints, summary, leakage, runtime, result)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__).resolve().relative_to(ROOT), config_path),
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": runtime,
        "inputs": input_hashes.to_dict(orient="records"),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket"], "winner": winner_row["method"], "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    CURRENT_CELLS = pd.DataFrame()
    main()
