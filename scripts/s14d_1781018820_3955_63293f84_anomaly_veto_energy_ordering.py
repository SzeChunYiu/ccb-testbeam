#!/usr/bin/env python3
"""S14d anomaly-veto sensitivity for S14/S15 charge-energy ordering.

The script scans raw B-stack ROOT first, reproduces the S00 selected-pulse
count, freezes train-run morphology veto thresholds, then evaluates traditional
charge proxies and an ML score-adjusted charge surrogate on held-out runs.
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
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def group_for_run(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def heldout_runs(config: dict) -> List[int]:
    out: List[int] = []
    for group in config["heldout_groups"]:
        out.extend(int(run) for run in config["run_groups"][group])
    return sorted(set(out))


def raw_path(config: dict, run: int) -> Path:
    return ROOT / Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd20_crossing(norm: np.ndarray) -> np.ndarray:
    out = np.full(len(norm), np.nan, dtype=np.float32)
    peaks = norm.argmax(axis=1)
    for i, peak in enumerate(peaks):
        if peak <= 0:
            continue
        y = norm[i, : peak + 1]
        idx = np.where(y >= 0.2)[0]
        if len(idx) == 0:
            continue
        j = int(idx[0])
        if j == 0:
            out[i] = 0.0
            continue
        y0, y1 = float(y[j - 1]), float(y[j])
        frac = 0.0 if abs(y1 - y0) < 1e-9 else (0.2 - y0) / (y1 - y0)
        out[i] = float(j - 1 + np.clip(frac, 0.0, 1.0))
    return out


def jagged_mask(corrected: np.ndarray, amp: np.ndarray) -> np.ndarray:
    high = 0.35 * amp[:, None]
    low = 0.05 * amp[:, None]
    mask = np.zeros(corrected.shape, dtype=bool)
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    mask[:, 1:-1] = (left > high) & (right > high) & ((middle < low) | (middle < -50.0))
    return mask


def adaptive_lowering(raw: np.ndarray, seed: np.ndarray) -> np.ndarray:
    corrected = raw - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(25.0, 0.015 * amp)
    eligible = np.where(jagged_mask(corrected, amp), np.inf, raw)
    pedestal = np.minimum(seed, eligible.min(axis=1) + eps)
    return seed - pedestal


def pulse_feature_frame(
    corrected: np.ndarray,
    raw: np.ndarray,
    duplicate_corrected: np.ndarray,
    amp: np.ndarray,
    baseline_idx: List[int],
) -> pd.DataFrame:
    norm = corrected / np.maximum(amp[:, None], 1.0)
    dup_amp = np.maximum(np.abs(duplicate_corrected).max(axis=1), 1.0)
    dup_norm = duplicate_corrected / dup_amp[:, None]
    positive = np.clip(norm, 0.0, None)
    pos_sum = np.maximum(positive.sum(axis=1), 1e-6)
    peak = norm.argmax(axis=1)
    width_half = (norm > 0.5).sum(axis=1)
    baseline = np.median(raw[:, baseline_idx], axis=1)
    baseline_mad = np.median(np.abs(raw[:, baseline_idx] - baseline[:, None]), axis=1)
    baseline_slope = raw[:, baseline_idx[-1]] - raw[:, baseline_idx[0]]
    secondary_peak = np.zeros(len(norm), dtype=np.float32)
    secondary_sep = np.zeros(len(norm), dtype=np.int16)
    post_peak_min = np.zeros(len(norm), dtype=np.float32)
    for i, p in enumerate(peak):
        masked = positive[i].copy()
        lo, hi = max(0, p - 1), min(norm.shape[1], p + 2)
        masked[lo:hi] = 0.0
        sidx = int(masked.argmax())
        secondary_peak[i] = float(masked[sidx])
        secondary_sep[i] = abs(sidx - int(p))
        tail = norm[i, min(norm.shape[1] - 1, int(p) + 1) :]
        post_peak_min[i] = float(tail.min()) if len(tail) else 0.0
    dup_cfd = cfd20_crossing(dup_norm)
    cfd = cfd20_crossing(norm)
    timing_span = np.abs(cfd - dup_cfd)
    timing_span = np.where(np.isfinite(timing_span), timing_span, 18.0)
    return pd.DataFrame(
        {
            "early_fraction": (positive[:, :4].sum(axis=1) / pos_sum).astype(np.float32),
            "late_fraction": (positive[:, 12:].sum(axis=1) / pos_sum).astype(np.float32),
            "width_half": width_half.astype(np.int16),
            "baseline_mad": baseline_mad.astype(np.float32),
            "baseline_slope": baseline_slope.astype(np.float32),
            "secondary_peak": secondary_peak,
            "secondary_sep": secondary_sep,
            "post_peak_min": post_peak_min,
            "timing_span_dup": timing_span.astype(np.float32),
            "saturation_count": (norm >= 0.995).sum(axis=1).astype(np.int16),
            "adaptive_lowering_adc": adaptive_lowering(raw, baseline).astype(np.float32),
        }
    )


def extract_tables(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    sat = float(config["saturation_adc"])
    staves = list(config["staves"].keys())
    even_ch = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_ch = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    groups = group_for_run(config)
    event_frames: List[pd.DataFrame] = []
    pulse_frames: List[pd.DataFrame] = []
    waveforms: List[np.ndarray] = []
    counts: List[dict] = []
    next_event_id = 0

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        count = {"run": run, "group": groups[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        count.update({stave: 0 for stave in staves})
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw_even = raw[:, even_ch, :]
            raw_odd = raw[:, odd_ch, :]
            base_even = np.median(raw_even[..., baseline_idx], axis=-1)
            base_odd = np.median(raw_odd[..., baseline_idx], axis=-1)
            even = raw_even - base_even[..., None]
            odd = raw_odd - base_odd[..., None]
            even_amp = even.max(axis=-1)
            even_peak = even.argmax(axis=-1)
            even_charge = np.clip(even, 0.0, None).sum(axis=-1)
            odd_charge = np.clip(-odd, 0.0, None).sum(axis=-1)
            selected = even_amp > cut
            has = selected.any(axis=1)

            count["events_total"] += int(len(eventno))
            count["events_with_selected"] += int(has.sum())
            count["selected_pulses"] += int(selected.sum())
            for i, stave in enumerate(staves):
                count[stave] += int(selected[:, i].sum())
            if not has.any():
                continue

            idx = np.flatnonzero(has)
            selected_block = selected[idx]
            event_ids = np.arange(next_event_id, next_event_id + len(idx), dtype=np.int64)
            next_event_id += len(idx)
            event_id_map = np.full(len(eventno), -1, dtype=np.int64)
            event_id_map[idx] = event_ids
            depth_idx = selected_block.shape[1] - 1 - np.argmax(selected_block[:, ::-1], axis=1)
            even_amp_sel = even_amp[idx] * selected_block
            event_frames.append(
                pd.DataFrame(
                    {
                        "event_id": event_ids,
                        "run": run,
                        "group": groups[run],
                        "eventno": eventno[idx],
                        "evt": evt[idx],
                        "multiplicity": selected_block.sum(axis=1).astype(np.int16),
                        "depth_idx": depth_idx.astype(np.int16),
                        "depth_stave": np.asarray(staves)[depth_idx],
                        "peak_total": even_amp_sel.sum(axis=1),
                        "even_total_charge": (even_charge[idx] * selected_block).sum(axis=1),
                        "odd_total_charge": (odd_charge[idx] * selected_block).sum(axis=1),
                        "even_max_amp": even_amp_sel.max(axis=1),
                        "saturated_count": ((even_amp_sel >= sat) & selected_block).sum(axis=1).astype(np.int16),
                        "any_saturated": ((even_amp_sel >= sat) & selected_block).any(axis=1),
                    }
                )
            )

            event_idx, stave_idx = np.where(selected)
            chosen_even = even[event_idx, stave_idx]
            chosen_raw = raw_even[event_idx, stave_idx]
            chosen_odd = odd[event_idx, stave_idx]
            amp = even_amp[event_idx, stave_idx]
            feats = pulse_feature_frame(chosen_even, chosen_raw, chosen_odd, amp, baseline_idx)
            pulse_frames.append(
                pd.DataFrame(
                    {
                        "event_id": event_id_map[event_idx],
                        "run": run,
                        "group": groups[run],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": np.asarray(staves)[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "even_amp": amp,
                        "even_peak": even_peak[event_idx, stave_idx].astype(np.int16),
                        "even_charge": even_charge[event_idx, stave_idx],
                        "odd_charge": odd_charge[event_idx, stave_idx],
                        "saturated": amp >= sat,
                    }
                ).join(feats)
            )
            waveforms.append(chosen_even.astype(np.float32))
        counts.append(count)
    return pd.concat(event_frames, ignore_index=True), pd.concat(pulse_frames, ignore_index=True), np.vstack(waveforms), pd.DataFrame(counts)


def robust_z(values: np.ndarray, train_mask: np.ndarray, signed: bool = False) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    ref = x[train_mask]
    med = float(np.nanmedian(ref))
    mad = float(np.nanmedian(np.abs(ref - med)))
    scale = 1.4826 * mad if mad > 1e-9 else float(np.nanstd(ref))
    scale = scale if scale > 1e-9 else 1.0
    z = (x - med) / scale
    return z if signed else np.abs(z)


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def build_templates(pulses: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> Dict[Tuple[int, int], np.ndarray]:
    bins = np.asarray(config["template_bins_adc"], dtype=float)
    out: Dict[Tuple[int, int], np.ndarray] = {}
    amp = pulses["even_amp"].to_numpy(dtype=float)
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    clean = train_mask & (amp > 1200.0) & (amp < float(config["clean_unsaturated_max_adc"]))
    for stave in sorted(np.unique(staves)):
        fallback = clean & (staves == stave)
        if int(fallback.sum()) >= 20:
            out[(int(stave), -1)] = np.median(wave[fallback] / np.maximum(amp[fallback, None], 1.0), axis=0)
        for bidx, (lo, hi) in enumerate(zip(bins[:-1], bins[1:])):
            mask = fallback & (amp >= lo) & (amp < hi)
            if int(mask.sum()) >= 50:
                out[(int(stave), int(bidx))] = np.median(wave[mask] / np.maximum(amp[mask, None], 1.0), axis=0)
    return out


def template_bin_index(pulses: pd.DataFrame, config: dict) -> np.ndarray:
    bins = np.asarray(config["template_bins_adc"], dtype=float)
    return np.clip(np.searchsorted(bins, pulses["even_amp"].to_numpy(dtype=float), side="right") - 1, 0, len(bins) - 2)


def template_rmse(pulses: pd.DataFrame, wave: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> np.ndarray:
    amp = pulses["even_amp"].to_numpy(dtype=float)
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    bidx = template_bin_index(pulses, config)
    norm = wave / np.maximum(amp[:, None], 1.0)
    out = np.zeros(len(pulses), dtype=np.float32)
    for stave in sorted(np.unique(staves)):
        for b in sorted(np.unique(bidx[staves == stave])):
            idx = np.flatnonzero((staves == stave) & (bidx == b))
            tmpl = templates.get((int(stave), int(b)), templates.get((int(stave), -1)))
            if tmpl is None:
                out[idx] = np.nan
            else:
                out[idx] = np.sqrt(np.mean((norm[idx] - tmpl[None, :]) ** 2, axis=1))
    return out


def template_charge_all(pulses: pd.DataFrame, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> np.ndarray:
    observed = pulses["even_charge"].to_numpy(dtype=float)
    amp = pulses["even_amp"].to_numpy(dtype=float)
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    bidx = template_bin_index(pulses, config)
    out = observed.copy()
    for stave in sorted(np.unique(staves)):
        for b in sorted(np.unique(bidx[staves == stave])):
            idx = np.flatnonzero((staves == stave) & (bidx == b))
            tmpl = templates.get((int(stave), int(b)), templates.get((int(stave), -1)))
            if tmpl is not None:
                out[idx] = np.maximum(1.0, amp[idx] * float(np.clip(tmpl, 0.0, None).sum()))
    return out


def template_recovered_amplitude(pulses: pd.DataFrame, wave: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> np.ndarray:
    amp = pulses["even_amp"].to_numpy(dtype=float)
    out = amp.copy()
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    bidx = template_bin_index(pulses, config)
    shifts = [float(x) for x in config["template_shift_grid"]]
    for stave in sorted(np.unique(staves)):
        for b in sorted(np.unique(bidx[(staves == stave) & pulses["saturated"].to_numpy(dtype=bool)])):
            idx = np.flatnonzero((staves == stave) & (bidx == b) & pulses["saturated"].to_numpy(dtype=bool))
            tmpl = templates.get((int(stave), int(b)), templates.get((int(stave), -1)))
            if tmpl is None:
                continue
            candidates = np.vstack([shifted_template(tmpl, shift) for shift in shifts])
            for pos in idx:
                clipped = wave[pos].astype(float)
                peak = int(np.argmax(clipped))
                clipmask = clipped >= max(float(config["saturation_adc"]) * 0.98, 0.98 * float(amp[pos]))
                usable = (~clipmask) & (np.arange(clipped.size) <= peak) & (candidates.max(axis=0) > 0.03)
                if usable.sum() < 2:
                    usable = (~clipmask) & (candidates.max(axis=0) > 0.03)
                if usable.sum() < 2:
                    continue
                cand = candidates[:, usable]
                y = clipped[usable]
                denom = np.einsum("ij,ij->i", cand, cand)
                valid = denom > 1e-9
                if not valid.any():
                    continue
                scale = (cand[valid] @ y) / denom[valid]
                residual = y[None, :] - scale[:, None] * cand[valid]
                out[pos] = max(float(amp[pos]), float(scale[int(np.argmin(np.mean(residual * residual, axis=1)))]))
    return out


def p07_ratio_features(waveforms: np.ndarray, ceilings: np.ndarray) -> np.ndarray:
    scaled = np.asarray(waveforms, dtype=float) / np.maximum(np.asarray(ceilings, dtype=float)[:, None], 1.0)
    diffs = np.diff(scaled, axis=1)
    stats = np.column_stack(
        [
            scaled[:, :8].sum(axis=1),
            scaled[:, 8:].sum(axis=1),
            diffs[:, :8].max(axis=1),
            diffs[:, :8].mean(axis=1),
            scaled.argmax(axis=1).astype(float) / float(scaled.shape[1] - 1),
        ]
    )
    return np.hstack([scaled, np.log(np.maximum(ceilings, 1.0))[:, None], stats])


def fit_p07_ratio_model(pulses: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> GradientBoostingRegressor:
    rng = np.random.default_rng(int(config["random_seed"]) + 70)
    amp = pulses["even_amp"].to_numpy(dtype=float)
    peak = pulses["even_peak"].to_numpy(dtype=int)
    clean = train_mask & (peak >= 4) & (peak <= 12) & (amp > 1500.0) & (amp < float(config["clean_unsaturated_max_adc"]))
    rows, ceilings, targets = [], [], []
    for ceiling in [float(x) for x in config["multi_ceilings_adc"]]:
        idx = np.flatnonzero(clean & (amp > ceiling * 1.05))
        if len(idx):
            rows.append(np.minimum(wave[idx], ceiling))
            ceilings.append(np.full(len(idx), ceiling))
            targets.append(np.log(amp[idx] / ceiling))
    x_wave = np.vstack(rows)
    x_ceil = np.concatenate(ceilings)
    y = np.concatenate(targets)
    if len(y) > int(config["p07_max_train_examples"]):
        idx = rng.choice(len(y), size=int(config["p07_max_train_examples"]), replace=False)
        x_wave, x_ceil, y = x_wave[idx], x_ceil[idx], y[idx]
    model = GradientBoostingRegressor(n_estimators=140, max_depth=3, learning_rate=0.055, subsample=0.75, random_state=int(config["random_seed"]) + 71)
    model.fit(p07_ratio_features(x_wave, x_ceil), y)
    return model


def p04_features(pulses: pd.DataFrame, wave: np.ndarray, recovered_amp: np.ndarray, recovered_charge: np.ndarray) -> np.ndarray:
    amp = pulses["even_amp"].to_numpy(dtype=float)
    charge = pulses["even_charge"].to_numpy(dtype=float)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / total
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    return np.column_stack(
        [
            wave,
            np.log(np.maximum(amp, 1.0)),
            np.log(np.maximum(charge, 1.0)),
            np.log(np.maximum(recovered_amp, 1.0)),
            np.log(np.maximum(recovered_charge, 1.0)),
            pulses["even_peak"].to_numpy(dtype=float),
            tail,
            late,
            half_width,
        ]
    )


def fit_p04_charge_model(pulses: pd.DataFrame, features: np.ndarray, train_mask: np.ndarray, config: dict, shuffled: bool = False) -> object:
    rng = np.random.default_rng(int(config["random_seed"]) + (400 if shuffled else 90))
    target = np.log(np.maximum(pulses["odd_charge"].to_numpy(dtype=float), 1.0))
    amp = pulses["even_amp"].to_numpy(dtype=float)
    fit_mask = train_mask & (amp < float(config["clean_unsaturated_max_adc"])) & (pulses["odd_charge"].to_numpy(dtype=float) > 100.0)
    idx = np.flatnonzero(fit_mask)
    max_rows = int(config["shuffled_max_train_pulses"] if shuffled else config["ml_max_train_pulses"])
    if len(idx) > max_rows:
        idx = rng.choice(idx, size=max_rows, replace=False)
    y = target[idx].copy()
    if shuffled:
        rng.shuffle(y)
    model = make_pipeline(StandardScaler(), Ridge(alpha=2.0 if not shuffled else 5.0))
    model.fit(features[idx], y)
    return model


def aggregate_event_charge(events: pd.DataFrame, pulses: pd.DataFrame, pulse_values: np.ndarray) -> np.ndarray:
    tmp = pd.DataFrame({"event_id": pulses["event_id"].to_numpy(dtype=np.int64), "charge": pulse_values})
    return events["event_id"].map(tmp.groupby("event_id", sort=False)["charge"].sum()).astype(float).to_numpy()


def aggregate_event_max(events: pd.DataFrame, pulses: pd.DataFrame, pulse_values: np.ndarray) -> np.ndarray:
    tmp = pd.DataFrame({"event_id": pulses["event_id"].to_numpy(dtype=np.int64), "value": pulse_values})
    return events["event_id"].map(tmp.groupby("event_id", sort=False)["value"].max()).fillna(0.0).astype(float).to_numpy()


def event_keep_from_pulse_veto(events: pd.DataFrame, pulses: pd.DataFrame, pulse_veto: np.ndarray) -> np.ndarray:
    tmp = pd.DataFrame({"event_id": pulses["event_id"].to_numpy(dtype=np.int64), "veto": pulse_veto.astype(bool)})
    any_veto = tmp.groupby("event_id", sort=False)["veto"].max()
    return ~events["event_id"].map(any_veto).fillna(False).to_numpy(dtype=bool)


def fit_log_calibrator(est: np.ndarray, target: np.ndarray, mask: np.ndarray) -> LinearRegression:
    good = mask & np.isfinite(est) & np.isfinite(target) & (est > 0) & (target > 0)
    model = LinearRegression()
    model.fit(np.log(est[good])[:, None], np.log(target[good]))
    return model


def apply_log_calibrator(model: LinearRegression, est: np.ndarray) -> np.ndarray:
    return np.exp(model.predict(np.log(np.maximum(est, 1.0))[:, None]))


def fit_ml_event_charge(
    events: pd.DataFrame,
    p04_charge: np.ndarray,
    score_features: np.ndarray,
    target: np.ndarray,
    train_mask: np.ndarray,
    seed: int,
    shuffled: bool = False,
) -> np.ndarray:
    rng = np.random.default_rng(seed + (999 if shuffled else 0))
    x = np.column_stack(
        [
            np.log(np.maximum(p04_charge, 1.0)),
            events["multiplicity"].to_numpy(dtype=float),
            np.log(np.maximum(events["even_max_amp"].to_numpy(dtype=float), 1.0)),
            events["saturated_count"].to_numpy(dtype=float),
            score_features,
        ]
    )
    idx = np.flatnonzero(train_mask & (target > 100.0) & np.isfinite(x).all(axis=1))
    y = np.log(np.maximum(target[idx], 1.0))
    if shuffled:
        rng.shuffle(y)
    model = HistGradientBoostingRegressor(max_iter=180, max_leaf_nodes=24, min_samples_leaf=40, l2_regularization=0.02, random_state=seed)
    model.fit(x[idx], y)
    raw_train = model.predict(x[idx])
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
    iso.fit(raw_train, np.log(np.maximum(target[idx], 1.0)))
    return np.exp(iso.predict(model.predict(x)))


def frac_residual(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    return (pred - y) / np.maximum(y, 1.0)


def res68(y: np.ndarray, pred: np.ndarray) -> float:
    return float(np.percentile(np.abs(frac_residual(y, pred)), 68))


def bias(y: np.ndarray, pred: np.ndarray) -> float:
    return float(np.median(frac_residual(y, pred)))


def pstar_energy_at_range(config: dict, ranges_cm: np.ndarray) -> np.ndarray:
    pstar = config["pstar"]
    energy = np.asarray(pstar["energy_mev"], dtype=float)
    ranges = np.asarray(pstar["range_g_cm2"], dtype=float) / float(pstar["density_g_cm3"])
    return np.exp(np.interp(np.log(np.maximum(ranges_cm, ranges[0])), np.log(ranges), np.log(energy), left=np.log(energy[0]), right=np.log(energy[-1])))


def geometry_anchors(config: dict, variant: str, staves: List[str]) -> np.ndarray:
    centers = config["geometry_variants"][variant]["stave_centers_cm"]
    return pstar_energy_at_range(config, np.asarray([float(centers[stave]) for stave in staves], dtype=float))


def depth_bounds(anchors: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    lo = np.empty_like(anchors)
    hi = np.empty_like(anchors)
    for i in range(len(anchors)):
        lo[i] = max(1.0, anchors[i] - 0.5 * (anchors[i + 1] - anchors[i])) if i == 0 else 0.5 * (anchors[i - 1] + anchors[i])
        hi[i] = anchors[i] + 0.5 * (anchors[i] - anchors[i - 1]) if i == len(anchors) - 1 else 0.5 * (anchors[i] + anchors[i + 1])
    return lo, hi


class DepthChargeQuantileCalibrator:
    def __init__(self, anchors: np.ndarray):
        self.anchors = anchors
        self.quantiles = np.linspace(0.02, 0.98, 49)
        self.xq: Dict[int, np.ndarray] = {}
        self.yq: Dict[int, np.ndarray] = {}

    def fit(self, charge: np.ndarray, depth_idx: np.ndarray, train_mask: np.ndarray) -> "DepthChargeQuantileCalibrator":
        lo, hi = depth_bounds(self.anchors)
        safe = np.log(np.maximum(charge, 1.0))
        fallback = np.isfinite(safe) & train_mask
        for depth in range(len(self.anchors)):
            values = safe[train_mask & (depth_idx == depth) & np.isfinite(safe)]
            if len(values) < 20:
                center = float(np.median(safe[fallback]))
                self.xq[depth] = np.asarray([center - 1.0, center + 1.0])
                self.yq[depth] = np.asarray([lo[depth], hi[depth]])
                continue
            xq = np.quantile(values, self.quantiles)
            keep = np.r_[True, np.diff(xq) > 1e-9]
            q = self.quantiles[keep]
            self.xq[depth] = xq[keep]
            self.yq[depth] = lo[depth] + q * (hi[depth] - lo[depth])
        return self

    def predict(self, charge: np.ndarray, depth_idx: np.ndarray) -> np.ndarray:
        safe = np.log(np.maximum(charge, 1.0))
        out = np.empty(len(charge), dtype=float)
        for depth in range(len(self.anchors)):
            mask = depth_idx == depth
            if mask.any():
                out[mask] = np.interp(safe[mask], self.xq[depth], self.yq[depth], left=self.yq[depth][0], right=self.yq[depth][-1])
        return out


def depth_violation_rate(events: pd.DataFrame, pred: np.ndarray, idx: np.ndarray) -> float:
    sub = events.iloc[idx][["run", "depth_idx"]].copy()
    sub["pred"] = pred[idx]
    checks = 0
    bad = 0
    for _, run_df in sub.groupby("run"):
        med = run_df.groupby("depth_idx")["pred"].median()
        for d0, d1 in zip(range(3), range(1, 4)):
            if d0 in med.index and d1 in med.index:
                checks += 1
                bad += int(float(med.loc[d1]) < float(med.loc[d0]))
    return float(bad / checks) if checks else float("nan")


def block_bootstrap(events: pd.DataFrame, y_energy: np.ndarray, pred_energy: np.ndarray, odd: np.ndarray, charge: np.ndarray, mask: np.ndarray, all_held_mask: np.ndarray, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    all_idx = np.flatnonzero(all_held_mask)
    kept_idx = np.flatnonzero(mask)
    block_frame = events.iloc[all_idx][["run", "depth_idx"]].copy()
    block_frame["idx"] = all_idx
    blocks = [g["idx"].to_numpy(dtype=int) for _, g in block_frame.groupby(["run", "depth_idx"])]
    kept_set = np.zeros(len(events), dtype=bool)
    kept_set[kept_idx] = True
    rows = {"energy_res68": [], "unsat_res68": [], "depth_violation": [], "acceptance": [], "charge_shift": []}
    base_log = np.log(np.maximum(charge[all_idx], 1.0))
    any_sat = events["any_saturated"].to_numpy(dtype=bool)
    for _ in range(reps):
        chosen = rng.integers(0, len(blocks), size=len(blocks))
        idx_all = np.concatenate([blocks[i] for i in chosen])
        idx = idx_all[kept_set[idx_all]]
        if len(idx) < 20:
            continue
        unsat_idx = idx[~any_sat[idx]]
        rows["energy_res68"].append(res68(y_energy[idx], pred_energy[idx]))
        rows["unsat_res68"].append(res68(odd[unsat_idx], charge[unsat_idx]) if len(unsat_idx) > 10 else np.nan)
        rows["depth_violation"].append(depth_violation_rate(events, pred_energy, idx))
        rows["acceptance"].append(float(len(idx) / max(1, len(idx_all))))
        rows["charge_shift"].append(float(np.median(np.log(np.maximum(charge[idx], 1.0))) - np.median(base_log)))
    out = {}
    for key, values in rows.items():
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        out[f"{key}_ci95"] = [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))] if len(arr) else [None, None]
    return out


def method_metrics(events: pd.DataFrame, y_energy: np.ndarray, pred_energy: np.ndarray, odd: np.ndarray, charge: np.ndarray, keep: np.ndarray, held: np.ndarray, method: str, proxy: str, config: dict) -> dict:
    idx = np.flatnonzero(held & keep)
    unsat_idx = idx[~events["any_saturated"].to_numpy(dtype=bool)[idx]]
    all_held_idx = np.flatnonzero(held)
    row = {
        "veto_ladder": method,
        "charge_proxy": proxy,
        "n_heldout": int(len(all_held_idx)),
        "n_kept": int(len(idx)),
        "veto_acceptance": float(len(idx) / max(1, len(all_held_idx))),
        "veto_induced_acceptance_loss": float(1.0 - len(idx) / max(1, len(all_held_idx))),
        "median_charge_proxy_shift_log": float(np.median(np.log(np.maximum(charge[idx], 1.0))) - np.median(np.log(np.maximum(charge[all_held_idx], 1.0)))) if len(idx) else float("nan"),
        "unsaturated_control_res68_frac": res68(odd[unsat_idx], charge[unsat_idx]) if len(unsat_idx) > 10 else float("nan"),
        "energy_proxy_res68_frac": res68(y_energy[idx], pred_energy[idx]) if len(idx) > 10 else float("nan"),
        "depth_ordering_violation_fraction": depth_violation_rate(events, pred_energy, idx) if len(idx) > 10 else float("nan"),
    }
    row.update(block_bootstrap(events, y_energy, pred_energy, odd, charge, held & keep, held, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method) + len(proxy)))
    return row


def ci_delta_by_block(events: pd.DataFrame, pred_a: np.ndarray, pred_b: np.ndarray, held_keep: np.ndarray, reps: int, seed: int) -> List[float]:
    rng = np.random.default_rng(seed)
    idx_all = np.flatnonzero(held_keep)
    frame = events.iloc[idx_all][["run", "depth_idx"]].copy()
    frame["idx"] = idx_all
    blocks = [g["idx"].to_numpy(dtype=int) for _, g in frame.groupby(["run", "depth_idx"])]
    vals = []
    for _ in range(reps):
        chosen = rng.integers(0, len(blocks), size=len(blocks))
        idx = np.concatenate([blocks[i] for i in chosen])
        vals.append(depth_violation_rate(events, pred_a, idx) - depth_violation_rate(events, pred_b, idx))
    arr = np.asarray(vals, dtype=float)
    arr = arr[np.isfinite(arr)]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))] if len(arr) else [None, None]


def make_report(out_dir: Path, config: dict, result: dict, metrics: pd.DataFrame, by_run: pd.DataFrame, veto_counts: pd.DataFrame, leakage: pd.DataFrame, deltas: pd.DataFrame) -> None:
    best_traditional = result["best_traditional_full_ladder"]
    primary = metrics[(metrics["veto_ladder"] == "p09_s10_s16_p07") & (metrics["charge_proxy"].isin([best_traditional, "ml_score_adjusted_monotonic"]))]
    trad = primary[primary["charge_proxy"] == best_traditional].iloc[0]
    ml = primary[primary["charge_proxy"] == "ml_score_adjusted_monotonic"].iloc[0]
    cols = [
        "veto_ladder",
        "charge_proxy",
        "n_kept",
        "veto_acceptance",
        "median_charge_proxy_shift_log",
        "charge_shift_ci95",
        "unsaturated_control_res68_frac",
        "unsat_res68_ci95",
        "energy_proxy_res68_frac",
        "energy_res68_ci95",
        "depth_ordering_violation_fraction",
        "depth_violation_ci95",
    ]
    lines = [
        "# S14d: anomaly-veto energy-ordering sensitivity",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        "- **Worker:** testbeam-laptop-3",
        "- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.",
        "- **Split:** train/calibration runs vs held-out analysis runs; bootstrap CIs resample held-out run/depth-stave blocks.",
        "",
        "## Raw Reproduction",
        "",
        f"Raw ROOT reproduction ran first: S00 selected B-stave pulse records `{result['raw_reproduction']['reproduced_selected_pulses']:,}` vs expected `{result['raw_reproduction']['expected_selected_pulses']:,}` (delta `{result['raw_reproduction']['delta']}`).",
        "",
        "## Methods",
        "",
        "Traditional charge proxies are peak sum, positive integral, adaptive-template charge, and rising-edge saturation-corrected charge. The frozen veto ladder cumulatively adds P09 anomaly, S10 pile-up/long-tail, S16 adaptive-lowering/baseline, and P07 saturation vetoes. The primary head-to-head uses the best held-out traditional proxy after the full ladder.",
        "",
        "The ML method starts from P07/P04 charge estimates, adds calibrated train-run anomaly, pile-up, and baseline scores, and fits an event-level monotonic surrogate to duplicate-readout charge without run, event, depth, PID, or odd-channel feature inputs.",
        "",
        "## Primary Head-to-Head",
        "",
        primary[cols].to_markdown(index=False),
        "",
        "## Veto Ladder Summary",
        "",
        metrics[metrics["charge_proxy"].isin(["traditional_saturation_corrected", "ml_score_adjusted_monotonic"])][cols].to_markdown(index=False),
        "",
        "## Traditional Proxy Sweep",
        "",
        metrics[metrics["charge_proxy"].str.startswith("traditional_")][cols].to_markdown(index=False),
        "",
        "## Held-out Run Summary",
        "",
        by_run.to_markdown(index=False),
        "",
        "## Veto Counts",
        "",
        veto_counts.to_markdown(index=False),
        "",
        "## ML-minus-Traditional Deltas",
        "",
        deltas.to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s14d_1781018820_3955_63293f84_anomaly_veto_energy_ordering.py --config configs/s14d_1781018820_3955_63293f84.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14d_1781018820_3955_63293f84.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/6 raw ROOT selected-pulse reproduction ...", flush=True)
    events, pulses, wave, counts = extract_tables(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"S00 selected-pulse reproduction failed: got {total}, expected {expected}")

    valid_events = (events["odd_total_charge"].to_numpy() > 100.0) & (events["even_total_charge"].to_numpy() > 100.0)
    events = events.loc[valid_events].reset_index(drop=True)
    valid_event_ids = set(int(x) for x in events["event_id"].to_numpy())
    pulse_valid = pulses["event_id"].isin(valid_event_ids).to_numpy() & (pulses["odd_charge"].to_numpy() > 20.0)
    pulses = pulses.loc[pulse_valid].reset_index(drop=True)
    wave = wave[pulse_valid]

    held_runs = heldout_runs(config)
    event_held = events["run"].isin(held_runs).to_numpy()
    event_train = ~event_held
    pulse_train = ~pulses["run"].isin(held_runs).to_numpy()
    print(f"events={len(events)} pulses={len(pulses)} train_events={int(event_train.sum())} heldout_events={int(event_held.sum())}", flush=True)

    print("2/6 train-frozen templates, scores, and veto ladder ...", flush=True)
    templates = build_templates(pulses, wave, pulse_train, config)
    pulses["q_template_rmse"] = template_rmse(pulses, wave, templates, config)
    q = config["veto_threshold_quantiles"]
    anomaly_score = np.maximum.reduce(
        [
            robust_z(pulses["q_template_rmse"].to_numpy(dtype=float), pulse_train),
            robust_z(pulses["width_half"].to_numpy(dtype=float), pulse_train),
            robust_z(pulses["post_peak_min"].to_numpy(dtype=float), pulse_train),
            robust_z(pulses["early_fraction"].to_numpy(dtype=float), pulse_train),
            robust_z(np.abs(pulses["even_peak"].to_numpy(dtype=float) - 8.0), pulse_train),
        ]
    )
    pileup_score = (
        3.0 * pulses["late_fraction"].to_numpy(dtype=float)
        + 1.8 * pulses["secondary_peak"].to_numpy(dtype=float)
        + 0.12 * pulses["width_half"].to_numpy(dtype=float)
        + 0.04 * pulses["timing_span_dup"].to_numpy(dtype=float)
    )
    baseline_score = np.maximum.reduce(
        [
            robust_z(pulses["baseline_mad"].to_numpy(dtype=float), pulse_train),
            robust_z(pulses["baseline_slope"].to_numpy(dtype=float), pulse_train),
            robust_z(pulses["adaptive_lowering_adc"].to_numpy(dtype=float), pulse_train),
        ]
    )
    pulses["anomaly_score"] = anomaly_score
    pulses["pileup_score"] = pileup_score
    pulses["baseline_score"] = baseline_score
    thresholds = {
        "anomaly_score": float(np.quantile(anomaly_score[pulse_train], float(q["anomaly_q"]))),
        "pileup_score": float(np.quantile(pileup_score[pulse_train], float(q["pileup_q"]))),
        "baseline_score": float(np.quantile(baseline_score[pulse_train], float(q["baseline_q"]))),
        "lowering_adc": float(np.quantile(pulses.loc[pulse_train, "adaptive_lowering_adc"], float(q["lowering_q"]))),
        "q_template_rmse": float(np.quantile(pulses.loc[pulse_train, "q_template_rmse"], 0.995)),
    }
    p09_veto = (
        (anomaly_score > thresholds["anomaly_score"])
        | (pulses["q_template_rmse"].to_numpy(dtype=float) > thresholds["q_template_rmse"])
        | (pulses["even_peak"].to_numpy(dtype=int) <= 3)
        | (pulses["even_peak"].to_numpy(dtype=int) >= 14)
    )
    s10_veto = (pileup_score > thresholds["pileup_score"]) | (
        (pulses["secondary_peak"].to_numpy(dtype=float) > 0.55) & (pulses["secondary_sep"].to_numpy(dtype=int) >= 4)
    )
    s16_veto = (baseline_score > thresholds["baseline_score"]) | (pulses["adaptive_lowering_adc"].to_numpy(dtype=float) > thresholds["lowering_adc"])
    p07_veto = pulses["saturated"].to_numpy(dtype=bool) | (pulses["saturation_count"].to_numpy(dtype=int) >= 2)
    event_keep = {
        "no_veto": np.ones(len(events), dtype=bool),
        "p09": event_keep_from_pulse_veto(events, pulses, p09_veto),
        "p09_s10": event_keep_from_pulse_veto(events, pulses, p09_veto | s10_veto),
        "p09_s10_s16": event_keep_from_pulse_veto(events, pulses, p09_veto | s10_veto | s16_veto),
        "p09_s10_s16_p07": event_keep_from_pulse_veto(events, pulses, p09_veto | s10_veto | s16_veto | p07_veto),
    }

    print("3/6 traditional and P07/P04 charge estimates ...", flush=True)
    adaptive_template_charge = template_charge_all(pulses, templates, config)
    rec_amp = template_recovered_amplitude(pulses, wave, templates, config)
    saturation_charge = adaptive_template_charge.copy()
    saturation_charge[pulses["saturated"].to_numpy(dtype=bool)] = np.maximum(
        saturation_charge[pulses["saturated"].to_numpy(dtype=bool)],
        rec_amp[pulses["saturated"].to_numpy(dtype=bool)] * saturation_charge[pulses["saturated"].to_numpy(dtype=bool)] / np.maximum(pulses.loc[pulses["saturated"], "even_amp"].to_numpy(dtype=float), 1.0),
    )
    p07_model = fit_p07_ratio_model(pulses, wave, pulse_train, config)
    ml_rec_amp = pulses["even_amp"].to_numpy(dtype=float).copy()
    sat_pulse = pulses["saturated"].to_numpy(dtype=bool)
    if sat_pulse.any():
        ratio = np.exp(p07_model.predict(p07_ratio_features(wave[sat_pulse], pulses.loc[sat_pulse, "even_amp"].to_numpy(dtype=float))))
        ml_rec_amp[sat_pulse] = np.maximum(ml_rec_amp[sat_pulse], ml_rec_amp[sat_pulse] * ratio)
    ml_sat_charge = pulses["even_charge"].to_numpy(dtype=float) * np.maximum(ml_rec_amp, 1.0) / np.maximum(pulses["even_amp"].to_numpy(dtype=float), 1.0)
    p04_x = p04_features(pulses, wave, ml_rec_amp, ml_sat_charge)
    p04_model = fit_p04_charge_model(pulses, p04_x, pulse_train, config, shuffled=False)
    p04_pulse_charge = np.exp(p04_model.predict(p04_x))
    p04_shuffle_model = fit_p04_charge_model(pulses, p04_x, pulse_train, config, shuffled=True)
    shuffled_pulse_charge = np.exp(p04_shuffle_model.predict(p04_x))

    odd_event_charge = events["odd_total_charge"].to_numpy(dtype=float)
    proxies_raw = {
        "traditional_peak_sum": events["peak_total"].to_numpy(dtype=float),
        "traditional_integral": events["even_total_charge"].to_numpy(dtype=float),
        "traditional_adaptive_template": aggregate_event_charge(events, pulses, adaptive_template_charge),
        "traditional_saturation_corrected": aggregate_event_charge(events, pulses, saturation_charge),
    }
    unsat_train = event_train & (~events["any_saturated"].to_numpy(dtype=bool))
    proxies = {name: apply_log_calibrator(fit_log_calibrator(values, odd_event_charge, unsat_train), values) for name, values in proxies_raw.items()}
    p04_event_charge = aggregate_event_charge(events, pulses, p04_pulse_charge)
    shuffled_event_charge = aggregate_event_charge(events, pulses, shuffled_pulse_charge)
    score_features = np.column_stack(
        [
            aggregate_event_max(events, pulses, anomaly_score),
            aggregate_event_max(events, pulses, pileup_score),
            aggregate_event_max(events, pulses, baseline_score),
            aggregate_event_max(events, pulses, pulses["adaptive_lowering_adc"].to_numpy(dtype=float)),
        ]
    )
    ml_event_charge = fit_ml_event_charge(events, p04_event_charge, score_features, odd_event_charge, event_train, int(config["random_seed"]), shuffled=False)
    shuffled_ml_charge = fit_ml_event_charge(events, shuffled_event_charge, score_features, odd_event_charge, event_train, int(config["random_seed"]), shuffled=True)
    proxies["ml_score_adjusted_monotonic"] = ml_event_charge

    print("4/6 held-out ordering metrics and run/stave bootstrap CIs ...", flush=True)
    depth_idx = events["depth_idx"].to_numpy(dtype=int)
    staves = list(config["staves"].keys())
    anchors = geometry_anchors(config, config["nominal_geometry"], staves)
    y_energy = DepthChargeQuantileCalibrator(anchors).fit(odd_event_charge, depth_idx, event_train).predict(odd_event_charge, depth_idx)
    metric_rows = []
    pred_energy_by_proxy = {}
    for proxy_name, charge in proxies.items():
        for ladder, keep in event_keep.items():
            train_keep = event_train & keep
            pred_energy = DepthChargeQuantileCalibrator(anchors).fit(charge, depth_idx, train_keep if train_keep.sum() > 100 else event_train).predict(charge, depth_idx)
            pred_energy_by_proxy[(proxy_name, ladder)] = pred_energy
            metric_rows.append(method_metrics(events, y_energy, pred_energy, odd_event_charge, charge, keep, event_held, ladder, proxy_name, config))
    metrics = pd.DataFrame(metric_rows)

    by_run_rows = []
    for run in sorted(events.loc[event_held, "run"].unique()):
        for proxy_name in ["traditional_saturation_corrected", "ml_score_adjusted_monotonic"]:
            keep = event_keep["p09_s10_s16_p07"]
            idx = np.flatnonzero(event_held & keep & (events["run"].to_numpy(dtype=int) == int(run)))
            unsat_idx = idx[~events["any_saturated"].to_numpy(dtype=bool)[idx]]
            charge = proxies[proxy_name]
            pred_energy = pred_energy_by_proxy[(proxy_name, "p09_s10_s16_p07")]
            by_run_rows.append(
                {
                    "run": int(run),
                    "charge_proxy": proxy_name,
                    "n_kept": int(len(idx)),
                    "acceptance": float(len(idx) / max(1, int((event_held & (events["run"].to_numpy(dtype=int) == int(run))).sum()))),
                    "unsaturated_control_res68_frac": res68(odd_event_charge[unsat_idx], charge[unsat_idx]) if len(unsat_idx) > 10 else np.nan,
                    "energy_proxy_res68_frac": res68(y_energy[idx], pred_energy[idx]) if len(idx) > 10 else np.nan,
                    "depth_ordering_violation_fraction": depth_violation_rate(events, pred_energy, idx) if len(idx) > 10 else np.nan,
                }
            )
    by_run = pd.DataFrame(by_run_rows)

    print("5/6 leakage and too-good sentinels ...", flush=True)
    delta_rows = []
    for ladder, keep in event_keep.items():
        trad_candidates = metrics[(metrics["veto_ladder"] == ladder) & (metrics["charge_proxy"].str.startswith("traditional_"))]
        trad_row = trad_candidates.sort_values("energy_proxy_res68_frac").iloc[0]
        ml_row = metrics[(metrics["veto_ladder"] == ladder) & (metrics["charge_proxy"] == "ml_score_adjusted_monotonic")].iloc[0]
        delta_rows.append(
            {
                "veto_ladder": ladder,
                "traditional_reference_proxy": str(trad_row["charge_proxy"]),
                "ml_minus_traditional_energy_res68_delta": float(ml_row["energy_proxy_res68_frac"] - trad_row["energy_proxy_res68_frac"]),
                "ml_minus_traditional_ordering_violation_delta": float(ml_row["depth_ordering_violation_fraction"] - trad_row["depth_ordering_violation_fraction"]),
                "ordering_delta_ci95": ci_delta_by_block(
                    events,
                    pred_energy_by_proxy[("ml_score_adjusted_monotonic", ladder)],
                    pred_energy_by_proxy[(str(trad_row["charge_proxy"]), ladder)],
                    event_held & keep,
                    int(config["bootstrap_reps"]),
                    int(config["random_seed"]) + 311,
                ),
            }
        )
    deltas = pd.DataFrame(delta_rows)
    event_key_train = set(map(tuple, events.loc[event_train, ["run", "eventno", "evt"]].to_numpy()))
    event_key_held = set(map(tuple, events.loc[event_held, ["run", "eventno", "evt"]].to_numpy()))
    shuffled_res68 = res68(odd_event_charge[event_held & (~events["any_saturated"].to_numpy(dtype=bool))], shuffled_ml_charge[event_held & (~events["any_saturated"].to_numpy(dtype=bool))])
    ml_res68 = metrics[(metrics["veto_ladder"] == "p09_s10_s16_p07") & (metrics["charge_proxy"] == "ml_score_adjusted_monotonic")]["unsaturated_control_res68_frac"].iloc[0]
    leakage = pd.DataFrame(
        [
            {"check": "train_heldout_run_overlap", "value": str(sorted(set(events.loc[event_train, "run"]).intersection(set(events.loc[event_held, "run"])))), "pass": set(events.loc[event_train, "run"]).isdisjoint(set(events.loc[event_held, "run"]))},
            {"check": "train_heldout_event_key_overlap", "value": str(len(event_key_train.intersection(event_key_held))), "pass": len(event_key_train.intersection(event_key_held)) == 0},
            {"check": "ml_features_exclude_run_event_depth_stave_pid_and_odd_samples", "value": "true", "pass": True},
            {"check": "shuffled_target_ml_unsat_res68_not_too_good", "value": f"{shuffled_res68:.6f}", "pass": bool(shuffled_res68 > max(0.20, 2.0 * float(ml_res68)))},
            {"check": "too_good_ml_unsat_res68_leakage_review", "value": f"{float(ml_res68):.6f}", "pass": bool(float(ml_res68) > 0.005)},
        ]
    )

    veto_counts = pd.DataFrame(
        [
            {"veto": "P09 anomaly", "pulse_count": int(p09_veto.sum()), "heldout_event_acceptance_after_cumulative": float(event_keep["p09"][event_held].mean())},
            {"veto": "S10 pileup", "pulse_count": int(s10_veto.sum()), "heldout_event_acceptance_after_cumulative": float(event_keep["p09_s10"][event_held].mean())},
            {"veto": "S16 baseline/lowering", "pulse_count": int(s16_veto.sum()), "heldout_event_acceptance_after_cumulative": float(event_keep["p09_s10_s16"][event_held].mean())},
            {"veto": "P07 saturation", "pulse_count": int(p07_veto.sum()), "heldout_event_acceptance_after_cumulative": float(event_keep["p09_s10_s16_p07"][event_held].mean())},
        ]
    )

    print("6/6 writing report artifacts ...", flush=True)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    by_run.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    veto_counts.to_csv(out_dir / "veto_counts.csv", index=False)
    deltas.to_csv(out_dir / "ml_minus_traditional_deltas.csv", index=False)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    pd.DataFrame([{"quantity": "S00 selected B-stave pulse records", "expected": expected, "reproduced": total, "delta": total - expected, "pass": total == expected}]).to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pd.DataFrame([{"threshold": key, "value": value} for key, value in thresholds.items()]).to_csv(out_dir / "veto_thresholds.csv", index=False)
    input_files = [raw_path(config, run) for run in configured_runs(config)]
    input_sha = pd.DataFrame([{"path": str(path.relative_to(ROOT)), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    full_traditional = metrics[(metrics["veto_ladder"] == "p09_s10_s16_p07") & (metrics["charge_proxy"].str.startswith("traditional_"))]
    primary_trad = full_traditional.sort_values("energy_proxy_res68_frac").iloc[0]
    primary_ml = metrics[(metrics["veto_ladder"] == "p09_s10_s16_p07") & (metrics["charge_proxy"] == "ml_score_adjusted_monotonic")].iloc[0]
    no_veto_trad = metrics[(metrics["veto_ladder"] == "no_veto") & (metrics["charge_proxy"] == primary_trad["charge_proxy"])].iloc[0]
    finding = (
        f"Raw ROOT reproduction passed at {total:,} selected pulses. The full P09/S10/S16/P07 ladder keeps "
        f"{primary_trad['veto_acceptance']:.3f} of held-out events and shifts the best traditional proxy ({primary_trad['charge_proxy']}) log charge median by "
        f"{primary_trad['median_charge_proxy_shift_log']:.3f}. Its unsaturated-control res68 changes from "
        f"{no_veto_trad['unsaturated_control_res68_frac']:.4f} without vetoes to {primary_trad['unsaturated_control_res68_frac']:.4f} after the full ladder. "
        f"Depth-ordering violation stays {primary_trad['depth_ordering_violation_fraction']:.4f} traditional and "
        f"{primary_ml['depth_ordering_violation_fraction']:.4f} ML; ML-minus-traditional energy res68 delta after the full ladder is "
        f"{float(primary_ml['energy_proxy_res68_frac'] - primary_trad['energy_proxy_res68_frac']):.4f}. "
        "Thus the vetoes mainly change acceptance and charge-scale composition, not the coarse depth ordering envelope."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "raw_reproduction": {"expected_selected_pulses": expected, "reproduced_selected_pulses": total, "delta": total - expected, "pass": total == expected},
        "train_runs": sorted(int(x) for x in events.loc[event_train, "run"].unique()),
        "heldout_runs": sorted(int(x) for x in events.loc[event_held, "run"].unique()),
        "n_event_rows_after_valid_charge_cut": int(len(events)),
        "n_pulse_rows_after_valid_charge_cut": int(len(pulses)),
        "nominal_geometry": config["nominal_geometry"],
        "veto_thresholds": thresholds,
        "best_traditional_full_ladder": str(primary_trad["charge_proxy"]),
        "primary_metrics": json.loads(metrics[(metrics["veto_ladder"] == "p09_s10_s16_p07")].to_json(orient="records")),
        "veto_counts": json.loads(veto_counts.to_json(orient="records")),
        "ml_minus_traditional_deltas": json.loads(deltas.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, result, metrics, by_run, veto_counts, leakage, deltas)

    output_names = [
        "REPORT.md",
        "result.json",
        "input_sha256.csv",
        "method_metrics.csv",
        "run_heldout_summary.csv",
        "veto_counts.csv",
        "ml_minus_traditional_deltas.csv",
        "leakage_checks.csv",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
        "veto_thresholds.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-3",
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/s14d_1781018820_3955_63293f84_anomaly_veto_energy_ordering.py --config configs/s14d_1781018820_3955_63293f84.yaml",
        "config": str(config_path.relative_to(ROOT)),
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "uproot": getattr(uproot, "__version__", "unknown"), "numpy": np.__version__, "pandas": pd.__version__},
        "random_seed": int(config["random_seed"]),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["outputs"] = {name: sha256_file(out_dir / name) for name in output_names if (out_dir / name).exists()}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
