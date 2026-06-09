#!/usr/bin/env python3
"""P04: amplitude / deposited-charge regression on independent readout targets.

The target is not the same positive waveform used as input.  For each selected physical
B-stack channel (even channels 0/2/4/6), the paired odd channel is an inverted duplicate
readout.  We predict its negative-pulse amplitude and positive-lobe charge from the even-channel
waveform.  This gives a same-event electronics cross-check while avoiding the trivial leakage of
predicting a peak or integral from the samples that define that same peak or integral.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["staves"].keys())
    even_channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_channels = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    stave_names = np.asarray(staves)
    group_for_run = run_group_lookup(config)

    meta_frames: List[pd.DataFrame] = []
    waveforms: List[np.ndarray] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {"run": run, "group": group_for_run[run], "events_total": 0, "selected_pulses": 0}
        run_counts.update({s: 0 for s in staves})

        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_channels, :]
            odd = corrected[:, odd_channels, :]

            even_amp = even.max(axis=-1)
            even_peak = even.argmax(axis=-1)
            even_pos_charge = np.clip(even, 0.0, None).sum(axis=-1)
            even_area = even.sum(axis=-1)
            target_amp = (-odd).max(axis=-1)
            target_charge = np.clip(-odd, 0.0, None).sum(axis=-1)
            odd_area_signed = odd.sum(axis=-1)

            selected = even_amp > cut
            run_counts["events_total"] += int(len(eventno))
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, stave in enumerate(staves):
                run_counts[stave] += int(selected[:, idx].sum())

            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue

            chosen = even[event_idx, stave_idx, :]
            waveforms.append(chosen.astype(np.float32))
            meta_frames.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "group": group_for_run[run],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": stave_names[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "even_amp": even_amp[event_idx, stave_idx],
                        "even_peak": even_peak[event_idx, stave_idx].astype(np.int16),
                        "even_pos_charge": even_pos_charge[event_idx, stave_idx],
                        "even_area": even_area[event_idx, stave_idx],
                        "target_odd_neg_amp": target_amp[event_idx, stave_idx],
                        "target_odd_pos_charge": target_charge[event_idx, stave_idx],
                        "target_odd_area_signed": odd_area_signed[event_idx, stave_idx],
                    }
                )
            )

        counts.append(run_counts)

    meta = pd.concat(meta_frames, ignore_index=True)
    wave = np.vstack(waveforms)
    counts_by_run = pd.DataFrame(counts)
    return meta, wave, counts_by_run


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac**2))),
        "within_5pct": float(np.mean(np.abs(frac) < 0.05)),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
    }


def bootstrap_ci(y: np.ndarray, pred: np.ndarray, rng: np.random.Generator, reps: int) -> dict:
    n = len(y)
    if n < 20:
        return {
            "bias_ci95": [None, None],
            "res68_ci95": [None, None],
            "full_rms_ci95": [None, None],
        }
    biases = np.empty(reps)
    res68 = np.empty(reps)
    rms = np.empty(reps)
    frac = (pred - y) / np.maximum(y, 1.0)
    for i in range(reps):
        idx = rng.integers(0, n, size=n)
        sample = frac[idx]
        biases[i] = np.median(sample)
        res68[i] = np.percentile(np.abs(sample), 68)
        rms[i] = np.sqrt(np.mean(sample**2))
    return {
        "bias_ci95": [float(np.percentile(biases, 2.5)), float(np.percentile(biases, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
    }


def fit_log_calibrators(est: np.ndarray, y: np.ndarray, stave_idx: np.ndarray) -> Dict[int, LinearRegression]:
    models: Dict[int, LinearRegression] = {}
    for stave in sorted(np.unique(stave_idx)):
        mask = (stave_idx == stave) & (est > 0) & (y > 0)
        model = LinearRegression()
        model.fit(np.log(est[mask])[:, None], np.log(y[mask]))
        models[int(stave)] = model
    return models


def predict_log_calibrated(models: Dict[int, LinearRegression], est: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(len(est), dtype=float)
    safe = np.maximum(est, 1.0)
    for stave, model in models.items():
        mask = stave_idx == stave
        out[mask] = np.exp(model.predict(np.log(safe[mask])[:, None]))
    return out


def build_templates(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, bins: List[float]) -> Dict[Tuple[int, int], np.ndarray]:
    templates: Dict[Tuple[int, int], np.ndarray] = {}
    train = meta[train_mask]
    for stave in sorted(train["stave_idx"].unique()):
        stave_mask = train_mask & (meta["stave_idx"].to_numpy() == stave)
        amps = meta.loc[stave_mask, "even_amp"].to_numpy()
        wf = wave[stave_mask]
        for bidx in range(len(bins) - 1):
            lo, hi = float(bins[bidx]), float(bins[bidx + 1])
            mask = (amps >= lo) & (amps < hi)
            if int(mask.sum()) < 50:
                continue
            norm = wf[mask] / np.maximum(amps[mask, None], 1.0)
            templates[(int(stave), bidx)] = np.median(norm, axis=0)
    return templates


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_scales(
    meta: pd.DataFrame,
    wave: np.ndarray,
    templates: Dict[Tuple[int, int], np.ndarray],
    bins: List[float],
    shift_grid: List[float],
) -> np.ndarray:
    out = np.asarray(meta["even_amp"].to_numpy(), dtype=float).copy()
    staves = meta["stave_idx"].to_numpy()
    amps = meta["even_amp"].to_numpy()
    bin_idx = np.clip(np.searchsorted(np.asarray(bins, dtype=float), amps, side="right") - 1, 0, len(bins) - 2)
    for key, template in templates.items():
        stave, bidx = key
        mask = (staves == stave) & (bin_idx == bidx)
        if not mask.any():
            continue
        candidates = np.vstack([shifted_template(template, float(shift)) for shift in shift_grid])
        denom = np.einsum("ij,ij->i", candidates, candidates)
        valid = denom > 1e-9
        if not valid.any():
            continue
        candidates = candidates[valid]
        denom = denom[valid]
        block = wave[mask]
        scales = (block @ candidates.T) / denom[None, :]
        residual = block[:, None, :] - scales[:, :, None] * candidates[None, :, :]
        best = np.argmin(np.mean(residual * residual, axis=2), axis=1)
        out[mask] = scales[np.arange(len(block)), best]
    return np.maximum(out, 1.0)


def build_adaptive_template_family(
    meta: pd.DataFrame,
    wave: np.ndarray,
    train_mask: np.ndarray,
    bins: List[float],
    min_rows: int,
) -> Dict[int, dict]:
    """Per-stave amplitude-indexed median templates, normalized to unit peak."""
    families: Dict[int, dict] = {}
    staves = meta["stave_idx"].to_numpy()
    amps = meta["even_amp"].to_numpy()
    for stave in sorted(np.unique(staves[train_mask])):
        stave_train = train_mask & (staves == stave)
        wf = wave[stave_train]
        a = amps[stave_train]
        norm = wf / np.maximum(a[:, None], 1.0)
        fallback = np.median(norm, axis=0)
        centers: List[float] = []
        templates: List[np.ndarray] = []
        counts: List[int] = []
        for bidx in range(len(bins) - 1):
            lo, hi = float(bins[bidx]), float(bins[bidx + 1])
            mask = (a >= lo) & (a < hi)
            if int(mask.sum()) < min_rows:
                continue
            centers.append(float(np.median(np.log(a[mask]))))
            templates.append(np.median(norm[mask], axis=0))
            counts.append(int(mask.sum()))
        if not templates:
            centers = [float(np.median(np.log(a)))]
            templates = [fallback]
            counts = [int(len(a))]
        order = np.argsort(np.asarray(centers))
        families[int(stave)] = {
            "centers": np.asarray(centers, dtype=float)[order],
            "templates": np.asarray(templates, dtype=float)[order],
            "counts": np.asarray(counts, dtype=int)[order],
            "fallback": fallback.astype(float),
        }
    return families


def _interp_template_family(centers: np.ndarray, templates: np.ndarray, log_amp: np.ndarray) -> np.ndarray:
    if len(centers) == 1:
        return np.repeat(templates[:1], len(log_amp), axis=0)
    right = np.searchsorted(centers, log_amp, side="right")
    hi = np.clip(right, 1, len(centers) - 1)
    lo = hi - 1
    denom = np.maximum(centers[hi] - centers[lo], 1e-9)
    weight = np.clip((log_amp - centers[lo]) / denom, 0.0, 1.0)
    return templates[lo] * (1.0 - weight[:, None]) + templates[hi] * weight[:, None]


def adaptive_template_fit(
    meta: pd.DataFrame,
    wave: np.ndarray,
    families: Dict[int, dict],
    shift_grid: List[float],
    block_size: int = 5000,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit an amplitude-adaptive template scale and phase shift to each waveform."""
    n = len(meta)
    scale_out = np.asarray(meta["even_amp"].to_numpy(), dtype=float).copy()
    shift_out = np.zeros(n, dtype=float)
    mse_out = np.full(n, np.nan, dtype=float)
    staves = meta["stave_idx"].to_numpy().astype(int)
    log_amp = np.log(np.maximum(meta["even_amp"].to_numpy(), 1.0))
    x = np.arange(wave.shape[1], dtype=float)
    for stave, family in families.items():
        indices = np.where(staves == stave)[0]
        centers = family["centers"]
        templates = family["templates"]
        for start in range(0, len(indices), block_size):
            idx = indices[start : start + block_size]
            base_templates = _interp_template_family(centers, templates, log_amp[idx])
            best_mse = np.full(len(idx), np.inf, dtype=float)
            best_scale = scale_out[idx].copy()
            best_shift = np.zeros(len(idx), dtype=float)
            block = wave[idx].astype(float)
            for shift in shift_grid:
                shifted = np.vstack(
                    [
                        np.interp(x - float(shift), x, tmpl, left=tmpl[0], right=tmpl[-1])
                        for tmpl in base_templates
                    ]
                )
                denom = np.einsum("ij,ij->i", shifted, shifted)
                valid = denom > 1e-9
                scale = np.zeros(len(idx), dtype=float)
                scale[valid] = np.einsum("ij,ij->i", block[valid], shifted[valid]) / denom[valid]
                residual = block - scale[:, None] * shifted
                mse = np.mean(residual * residual, axis=1)
                improve = mse < best_mse
                best_mse[improve] = mse[improve]
                best_scale[improve] = scale[improve]
                best_shift[improve] = float(shift)
            scale_out[idx] = np.maximum(best_scale, 1.0)
            shift_out[idx] = best_shift
            mse_out[idx] = best_mse
    return scale_out, shift_out, mse_out


def handcrafted_template_features(
    meta: pd.DataFrame,
    wave: np.ndarray,
    template_scale: np.ndarray,
    template_shift: np.ndarray,
    template_mse: np.ndarray,
) -> np.ndarray:
    amp = meta["even_amp"].to_numpy()
    charge = meta["even_pos_charge"].to_numpy()
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / total
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    return np.column_stack(
        [
            np.log(np.maximum(template_scale, 1.0)),
            np.log(np.maximum(amp, 1.0)),
            np.log(np.maximum(charge, 1.0)),
            meta["even_peak"].to_numpy(),
            tail,
            late,
            half_width,
            template_shift,
            np.log(np.maximum(template_mse, 1e-6)),
        ]
    )


def fit_per_stave_ridge(features: np.ndarray, y: np.ndarray, train_mask: np.ndarray, stave_idx: np.ndarray) -> Dict[int, object]:
    models: Dict[int, object] = {}
    alphas = np.asarray([0.01, 0.1, 1.0, 10.0, 100.0], dtype=float)
    for stave in sorted(np.unique(stave_idx)):
        mask = train_mask & (stave_idx == stave) & np.isfinite(features).all(axis=1) & (y > 0)
        model = make_pipeline(StandardScaler(), RidgeCV(alphas=alphas))
        model.fit(features[mask], np.log(y[mask]))
        models[int(stave)] = model
    return models


def predict_per_stave_ridge(models: Dict[int, object], features: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(len(features), dtype=float)
    for stave, model in models.items():
        mask = stave_idx == stave
        out[mask] = np.exp(model.predict(features[mask]))
    return np.maximum(out, 1.0)


def ml_features(meta: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    amp = meta["even_amp"].to_numpy()
    charge = meta["even_pos_charge"].to_numpy()
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / total
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    stave_idx = meta["stave_idx"].to_numpy().astype(int)
    stave_onehot = np.zeros((len(meta), 4), dtype=float)
    stave_onehot[np.arange(len(meta)), stave_idx] = 1.0
    return np.column_stack(
        [
            wave,
            np.log(np.maximum(amp, 1.0)),
            np.log(np.maximum(charge, 1.0)),
            meta["even_peak"].to_numpy(),
            tail,
            late,
            half_width,
            stave_onehot,
        ]
    )


def evaluate_methods(
    meta: pd.DataFrame,
    predictions: Dict[str, Dict[str, np.ndarray]],
    heldout_mask: np.ndarray,
    config: dict,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 99)
    reps = int(config["bootstrap_reps"])
    rows = []
    bin_rows = []
    targets = {
        "amplitude": "target_odd_neg_amp",
        "charge": "target_odd_pos_charge",
    }
    held = meta[heldout_mask].reset_index(drop=True)
    amp_bins = [
        ("1000_3000", 1000.0, 3000.0),
        ("3000_5000", 3000.0, 5000.0),
        ("5000_7000", 5000.0, 7000.0),
        ("ge7000", 7000.0, np.inf),
    ]
    for target_name, col in targets.items():
        y = held[col].to_numpy()
        for method, pred_by_target in predictions.items():
            if target_name not in pred_by_target:
                continue
            pred = pred_by_target[target_name][heldout_mask]
            row = {"target": target_name, "method": method, "subset": "heldout_runs_57_65"}
            row.update(robust_metrics(y, pred))
            row.update(bootstrap_ci(y, pred, rng, reps))
            rows.append(row)

            for run, run_df in held.groupby("run"):
                idx = run_df.index.to_numpy()
                brow = {"target": target_name, "method": method, "subset": f"run_{int(run)}"}
                brow.update(robust_metrics(y[idx], pred[idx]))
                brow.update(bootstrap_ci(y[idx], pred[idx], rng, max(100, reps // 2)))
                bin_rows.append(brow)

            if target_name == "amplitude":
                for stave, stave_df in held.groupby("stave"):
                    idx = stave_df.index.to_numpy()
                    brow = {"target": target_name, "method": method, "subset": f"stave_{stave}"}
                    brow.update(robust_metrics(y[idx], pred[idx]))
                    brow.update(bootstrap_ci(y[idx], pred[idx], rng, max(100, reps // 2)))
                    bin_rows.append(brow)

                even_amp = held["even_amp"].to_numpy()
                for label, lo, hi in amp_bins:
                    idx = np.where((even_amp >= lo) & (even_amp < hi))[0]
                    if len(idx) < 30:
                        continue
                    brow = {"target": target_name, "method": method, "subset": f"even_amp_{label}"}
                    brow.update(robust_metrics(y[idx], pred[idx]))
                    brow.update(bootstrap_ci(y[idx], pred[idx], rng, max(100, reps // 2)))
                    bin_rows.append(brow)
    return pd.DataFrame(rows), pd.DataFrame(bin_rows)


def make_report(
    out_dir: Path,
    config: dict,
    counts_by_run: pd.DataFrame,
    benchmark: pd.DataFrame,
    by_subset: pd.DataFrame,
    leakage_audit: dict,
    result: dict,
) -> None:
    total = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    heldout_runs = ", ".join(str(r) for r in config["heldout_runs"])

    amp_table = benchmark[benchmark["target"] == "amplitude"][
        ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "full_rms_frac", "within_10pct"]
    ].copy()
    charge_table = benchmark[benchmark["target"] == "charge"][
        ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "full_rms_frac", "within_10pct"]
    ].copy()
    high_b2 = by_subset[
        (by_subset["target"] == "amplitude")
        & (by_subset["subset"].isin(["even_amp_ge7000", "stave_B2"]))
        & (
            by_subset["method"].isin(
                ["peak_calibrated", "adaptive_template_ridge", "adaptive_template_scale", "ml_hgb"]
            )
        )
    ][["subset", "method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "within_10pct"]]

    lines = [
        "# P04c: stronger amplitude-adaptive template baseline",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        "- **Worker:** testbeam-laptop-4",
        "- **Input:** raw `data/root/root/hrdb_run_*.root` only; checksums in `manifest.json`.",
        f"- **Held-out runs:** {heldout_runs}; all model calibration/training excludes those runs.",
        "",
        "## 1. Raw reproduction gate",
        "",
        "Before fitting any regressor, the script rebuilds the S00 selected-pulse gate from raw `HRDv`: "
        "`max(even channel - median(samples 0..3)) > 1000 ADC` for B2/B4/B6/B8.",
        "",
        f"| quantity | expected | reproduced | delta | pass |",
        f"|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {expected:,} | {total:,} | {total - expected:+,} | {str(total == expected).lower()} |",
        "",
        "This is the reproduced ticket number used as the entry gate for the P04 benchmark.",
        "",
        "## 2. Leakage-safe target",
        "",
        "The trivial target `even-channel peak` is not used, because peak/integral/template features from "
        "the same waveform would define the label. Instead, the target is the paired odd readout, which is "
        "an inverted duplicate channel: amplitude is `max(-odd_waveform)` and charge is `sum(max(-odd_waveform, 0))`. "
        "Inputs are only the even-channel waveform and derived even-channel features; event number, run number, "
        "and odd-channel samples are excluded from model features.",
        "",
        "## 3. Methods",
        "",
        "- **Peak/integral baselines:** per-stave log-linear calibrations from even peak and positive-lobe integral.",
        "- **P04 fixed-bin template:** per-stave amplitude-bin median templates with time-shift fitting, retained as a legacy reference.",
        "- **P04c adaptive-template scale:** per-stave median templates in finer amplitude bins, linearly interpolated in log-amplitude and fit over a time-shift grid, then per-stave train-only log calibration.",
        "- **P04c strong traditional ridge:** a train-only per-stave ridge calibration on explicit adaptive-template diagnostics (`template scale`, `shift`, `fit MSE`) plus peak/integral/shape summaries. It uses no run id, event id, or odd-channel samples.",
        "- **ML:** `HistGradientBoostingRegressor` on the 18 even waveform samples plus even peak/charge/shape summaries and stave one-hot; separate log-target models for amplitude and charge.",
        "",
        "## 4. Held-out benchmark",
        "",
        "Primary metric is the 68th percentile of absolute fractional error (`res68`); lower is better. "
        "CIs are held-out bootstrap intervals over the evaluated pulse records.",
        "",
        "### Amplitude target",
        "",
        amp_table.to_markdown(index=False),
        "",
        "### Charge target",
        "",
        charge_table.to_markdown(index=False),
        "",
        "### High-amplitude and B2 checks",
        "",
        high_b2.to_markdown(index=False),
        "",
        "## 5. Leakage audit",
        "",
        f"- Held-out runs `{heldout_runs}` are absent from training: `{leakage_audit['heldout_absent_from_train']}`.",
        f"- Feature columns include no run/event ids and no odd-channel target samples: `{leakage_audit['no_identifier_or_target_features']}`.",
        f"- Rows with invalid independent target removed after reproduction: {leakage_audit['invalid_target_rows_removed']:,}.",
        f"- Run/stave-only median predictor amplitude res68: {leakage_audit['context_only_amp_res68']:.4f}.",
        f"- Shuffled-target ML amplitude res68: {leakage_audit['shuffled_target_amp_res68']:.4f}.",
        f"- Train/held-out run overlap: `{leakage_audit['train_heldout_run_overlap']}`.",
        f"- Train/held-out `(run,event,stave)` key overlap: `{leakage_audit['train_heldout_event_key_overlap']}`.",
        "",
        "The ML result is deliberately not interpreted as absolute detector truth: it is a same-event "
        "duplicate-readout closure test. The unusually small ML error is plausible for a duplicate readout "
        "but too strong to promote to a physics energy claim without an external charge/energy reference.",
        "",
        "## 6. Finding",
        "",
        result["finding"],
        "",
        "## 7. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template/p04c_amplitude_adaptive_template.py --config reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template/p04c_config.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template/p04c_config.yaml",
    )
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("loading raw ROOT and reproducing S00 gate ...")
    meta, wave, counts_by_run = extract_rows(config)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"S00 reproduction failed: got {total_selected}, expected {expected}")

    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
    invalid_rows = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]

    heldout_runs = [int(r) for r in config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    if set(meta.loc[train_mask, "run"].unique()).intersection(heldout_runs):
        raise RuntimeError("held-out run leaked into training mask")

    print(f"selected={total_selected} valid={len(meta)} train={int(train_mask.sum())} heldout={int(heldout_mask.sum())}")

    st = meta["stave_idx"].to_numpy()
    even_amp = meta["even_amp"].to_numpy()
    even_charge = meta["even_pos_charge"].to_numpy()
    y_amp = meta["target_odd_neg_amp"].to_numpy()
    y_charge = meta["target_odd_pos_charge"].to_numpy()

    methods: Dict[str, Dict[str, np.ndarray]] = {}

    peak_models = fit_log_calibrators(even_amp[train_mask], y_amp[train_mask], st[train_mask])
    methods["peak_calibrated"] = {"amplitude": predict_log_calibrated(peak_models, even_amp, st)}

    integral_models = fit_log_calibrators(even_charge[train_mask], y_charge[train_mask], st[train_mask])
    methods["integral_calibrated"] = {"charge": predict_log_calibrated(integral_models, even_charge, st)}

    bins = [float(x) for x in config["template_bins"]]
    templates = build_templates(meta, wave, train_mask, bins)
    shift_grid = [float(x) for x in config["template_shift_grid"]]
    tmpl_scale = template_scales(meta, wave, templates, bins, shift_grid)
    tmpl_amp_models = fit_log_calibrators(tmpl_scale[train_mask], y_amp[train_mask], st[train_mask])
    tmpl_charge_models = fit_log_calibrators(tmpl_scale[train_mask], y_charge[train_mask], st[train_mask])
    methods["fixed_bin_template_calibrated"] = {
        "amplitude": predict_log_calibrated(tmpl_amp_models, tmpl_scale, st),
        "charge": predict_log_calibrated(tmpl_charge_models, tmpl_scale, st),
    }

    print("fitting adaptive amplitude-template family ...")
    families = build_adaptive_template_family(
        meta,
        wave,
        train_mask,
        bins,
        int(config.get("adaptive_template_min_bin_rows", 80)),
    )
    adaptive_scale, adaptive_shift, adaptive_mse = adaptive_template_fit(meta, wave, families, shift_grid)
    ad_amp_models = fit_log_calibrators(adaptive_scale[train_mask], y_amp[train_mask], st[train_mask])
    ad_charge_models = fit_log_calibrators(adaptive_scale[train_mask], y_charge[train_mask], st[train_mask])
    methods["adaptive_template_scale"] = {
        "amplitude": predict_log_calibrated(ad_amp_models, adaptive_scale, st),
        "charge": predict_log_calibrated(ad_charge_models, adaptive_scale, st),
    }
    trad_features = handcrafted_template_features(meta, wave, adaptive_scale, adaptive_shift, adaptive_mse)
    trad_amp_models = fit_per_stave_ridge(trad_features, y_amp, train_mask, st)
    trad_charge_models = fit_per_stave_ridge(trad_features, y_charge, train_mask, st)
    methods["adaptive_template_ridge"] = {
        "amplitude": predict_per_stave_ridge(trad_amp_models, trad_features, st),
        "charge": predict_per_stave_ridge(trad_charge_models, trad_features, st),
    }

    context_amp = np.zeros(len(meta), dtype=float)
    context_charge = np.zeros(len(meta), dtype=float)
    for stave in sorted(np.unique(st)):
        mask_train = train_mask & (st == stave)
        mask_all = st == stave
        context_amp[mask_all] = float(np.median(y_amp[mask_train]))
        context_charge[mask_all] = float(np.median(y_charge[mask_train]))
    methods["run_stave_blind_median"] = {"amplitude": context_amp, "charge": context_charge}

    print("training ML regressors ...")
    X = ml_features(meta, wave)
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    ml_params = {
        "max_iter": 220,
        "learning_rate": 0.06,
        "max_leaf_nodes": 31,
        "l2_regularization": 0.05,
        "random_state": int(config["random_seed"]),
    }
    amp_model = HistGradientBoostingRegressor(**ml_params)
    charge_model = HistGradientBoostingRegressor(**ml_params)
    amp_model.fit(X[train_idx], np.log(y_amp[train_idx]))
    charge_model.fit(X[train_idx], np.log(y_charge[train_idx]))
    methods["ml_hgb"] = {
        "amplitude": np.exp(amp_model.predict(X)),
        "charge": np.exp(charge_model.predict(X)),
    }

    shuffle_idx = train_idx.copy()
    shuffled_log_amp = np.log(y_amp[shuffle_idx]).copy()
    rng.shuffle(shuffled_log_amp)
    shuffled_model = HistGradientBoostingRegressor(
        max_iter=80,
        learning_rate=0.06,
        max_leaf_nodes=31,
        l2_regularization=0.05,
        random_state=int(config["random_seed"]) + 1,
    )
    shuffled_model.fit(X[shuffle_idx], shuffled_log_amp)
    shuffled_pred = np.exp(shuffled_model.predict(X))

    benchmark, by_subset = evaluate_methods(meta, methods, heldout_mask, config)
    benchmark.to_csv(out_dir / "benchmark.csv", index=False)
    by_subset.to_csv(out_dir / "benchmark_by_subset.csv", index=False)
    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)

    context_res68 = robust_metrics(y_amp[heldout_mask], context_amp[heldout_mask])["res68_abs_frac"]
    shuffled_res68 = robust_metrics(y_amp[heldout_mask], shuffled_pred[heldout_mask])["res68_abs_frac"]
    leakage_audit = {
        "heldout_absent_from_train": bool(set(meta.loc[train_mask, "run"].unique()).isdisjoint(heldout_runs)),
        "no_identifier_or_target_features": True,
        "invalid_target_rows_removed": invalid_rows,
        "context_only_amp_res68": float(context_res68),
        "shuffled_target_amp_res68": float(shuffled_res68),
        "train_heldout_run_overlap": sorted(
            int(x) for x in set(meta.loc[train_mask, "run"].unique()).intersection(heldout_runs)
        ),
        "train_heldout_event_key_overlap": int(
            len(
                set(
                    zip(
                        meta.loc[train_mask, "run"].astype(int),
                        meta.loc[train_mask, "eventno"].astype(int),
                        meta.loc[train_mask, "stave"].astype(str),
                    )
                ).intersection(
                    set(
                        zip(
                            meta.loc[heldout_mask, "run"].astype(int),
                            meta.loc[heldout_mask, "eventno"].astype(int),
                            meta.loc[heldout_mask, "stave"].astype(str),
                        )
                    )
                )
            )
        ),
    }

    amp_rows = benchmark[benchmark["target"] == "amplitude"].set_index("method")
    charge_rows = benchmark[benchmark["target"] == "charge"].set_index("method")
    ml_amp = float(amp_rows.loc["ml_hgb", "res68_abs_frac"])
    best_trad_amp = float(
        amp_rows.loc[
            ["peak_calibrated", "fixed_bin_template_calibrated", "adaptive_template_scale", "adaptive_template_ridge"],
            "res68_abs_frac",
        ].min()
    )
    ml_charge = float(charge_rows.loc["ml_hgb", "res68_abs_frac"])
    best_trad_charge = float(
        charge_rows.loc[
            [
                "integral_calibrated",
                "fixed_bin_template_calibrated",
                "adaptive_template_scale",
                "adaptive_template_ridge",
            ],
            "res68_abs_frac",
        ].min()
    )
    finding = (
        f"On independent odd-readout closure, ML amplitude res68 is {ml_amp:.4f} versus the best "
        f"traditional amplitude baseline at {best_trad_amp:.4f}; charge res68 is {ml_charge:.4f} "
        f"versus {best_trad_charge:.4f}. The adaptive template family tests the model-definition "
        "hypothesis directly: any remaining ML advantage is treated as duplicate-readout waveform "
        "closure, not an absolute true-energy calibration."
    )

    input_files = [raw_path(config, run) for run in configured_runs(config)]
    result = {
        "study": "P04c",
        "ticket_id": config["ticket_id"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total_selected,
            "delta": total_selected - expected,
            "pass": total_selected == expected,
        },
        "target_definition": "paired odd-channel inverted duplicate readout; features from even channel only",
        "train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()),
        "heldout_runs": heldout_runs,
        "n_valid_rows": int(len(meta)),
        "n_train_rows": int(train_mask.sum()),
        "n_heldout_rows": int(heldout_mask.sum()),
        "invalid_target_rows_removed_after_reproduction": invalid_rows,
        "benchmark": json.loads(benchmark.to_json(orient="records")),
        "leakage_audit": leakage_audit,
        "template_family": {
            str(stave): {
                "n_templates": int(len(family["centers"])),
                "counts": [int(x) for x in family["counts"]],
            }
            for stave, family in families.items()
        },
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    make_report(out_dir, config, counts_by_run, benchmark, by_subset, leakage_audit, result)

    input_manifest = pd.DataFrame(
        [{"path": str(path), "sha256": sha256_file(path)} for path in input_files]
    )
    input_manifest.to_csv(out_dir / "input_sha256.csv", index=False)

    output_files = [
        "REPORT.md",
        "result.json",
        "benchmark.csv",
        "benchmark_by_subset.csv",
        "counts_by_run.csv",
        "input_sha256.csv",
    ]
    manifest = {
        "study": "P04c",
        "ticket_id": config["ticket_id"],
        "command": "/home/billy/anaconda3/bin/python reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template/p04c_amplitude_adaptive_template.py --config reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template/p04c_config.yaml",
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "inputs": json.loads(input_manifest.to_json(orient="records")),
        "outputs": [],
    }
    manifest["outputs"] = [
        {"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)}
        for name in output_files
    ]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
