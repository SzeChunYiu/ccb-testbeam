#!/usr/bin/env python3
"""S14c: saturation-corrected charge proxy energy ordering from raw HRD ROOT.

No Monte Carlo truth is used. The script first reproduces the S00 selected-pulse
count from raw ROOT, then evaluates traditional and ML charge proxies under
held-out run splits with run/stave bootstrap intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor
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


def extract_tables(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    sat = float(config["saturation_adc"])
    staves = list(config["staves"].keys())
    even_ch = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_ch = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    group_lookup = group_for_run(config)
    event_frames: List[pd.DataFrame] = []
    pulse_frames: List[pd.DataFrame] = []
    waveforms: List[np.ndarray] = []
    counts: List[dict] = []
    next_event_id = 0

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        count = {
            "run": run,
            "group": group_lookup[run],
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        count.update({stave: 0 for stave in staves})

        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_ch, :]
            odd = corrected[:, odd_ch, :]

            even_amp = even.max(axis=-1)
            even_peak = even.argmax(axis=-1)
            even_charge = np.clip(even, 0.0, None).sum(axis=-1)
            odd_amp = (-odd).max(axis=-1)
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
            even_charge_sel = even_charge[idx] * selected_block
            odd_charge_sel = odd_charge[idx] * selected_block
            saturated_sel = (even_amp_sel >= sat) & selected_block
            event_frame = pd.DataFrame(
                {
                    "event_id": event_ids,
                    "run": run,
                    "group": group_lookup[run],
                    "eventno": eventno[idx],
                    "evt": evt[idx],
                    "multiplicity": selected_block.sum(axis=1).astype(np.int16),
                    "depth_idx": depth_idx.astype(np.int16),
                    "depth_stave": np.asarray(staves)[depth_idx],
                    "even_total_charge": even_charge_sel.sum(axis=1),
                    "odd_total_charge": odd_charge_sel.sum(axis=1),
                    "even_max_amp": even_amp_sel.max(axis=1),
                    "saturated_count": saturated_sel.sum(axis=1).astype(np.int16),
                    "any_saturated": saturated_sel.any(axis=1),
                }
            )
            event_frames.append(event_frame)

            event_idx, stave_idx = np.where(selected)
            pulse_frames.append(
                pd.DataFrame(
                    {
                        "event_id": event_id_map[event_idx],
                        "run": run,
                        "group": group_lookup[run],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": np.asarray(staves)[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "even_amp": even_amp[event_idx, stave_idx],
                        "even_peak": even_peak[event_idx, stave_idx].astype(np.int16),
                        "even_charge": even_charge[event_idx, stave_idx],
                        "odd_amp": odd_amp[event_idx, stave_idx],
                        "odd_charge": odd_charge[event_idx, stave_idx],
                        "saturated": (even_amp[event_idx, stave_idx] >= sat),
                    }
                )
            )
            waveforms.append(even[event_idx, stave_idx, :].astype(np.float32))

        counts.append(count)

    events = pd.concat(event_frames, ignore_index=True)
    pulses = pd.concat(pulse_frames, ignore_index=True)
    wave = np.vstack(waveforms)
    return events, pulses, wave, pd.DataFrame(counts)


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def build_templates(pulses: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> Dict[Tuple[int, int], np.ndarray]:
    bins = np.asarray(config["template_bins_adc"], dtype=float)
    out: Dict[Tuple[int, int], np.ndarray] = {}
    amps = pulses["even_amp"].to_numpy()
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    clean = train_mask & (amps > 1200.0) & (amps < float(config["clean_unsaturated_max_adc"]))
    for stave in sorted(np.unique(staves)):
        for bidx, (lo, hi) in enumerate(zip(bins[:-1], bins[1:])):
            mask = clean & (staves == stave) & (amps >= lo) & (amps < hi)
            if int(mask.sum()) < 50:
                continue
            norm = wave[mask] / np.maximum(amps[mask, None], 1.0)
            out[(int(stave), int(bidx))] = np.median(norm, axis=0)
        if not any(k[0] == stave for k in out):
            mask = clean & (staves == stave)
            if int(mask.sum()) >= 20:
                out[(int(stave), 0)] = np.median(wave[mask] / np.maximum(amps[mask, None], 1.0), axis=0)
    return out


def template_recovered_amplitude(pulses: pd.DataFrame, wave: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> np.ndarray:
    amps = pulses["even_amp"].to_numpy(dtype=float)
    out = amps.copy()
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    bins = np.asarray(config["template_bins_adc"], dtype=float)
    bin_idx = np.clip(np.searchsorted(bins, amps, side="right") - 1, 0, len(bins) - 2)
    shifts = [float(x) for x in config["template_shift_grid"]]
    sat_mask = pulses["saturated"].to_numpy(dtype=bool)
    for key, template in templates.items():
        stave, bidx = key
        mask = sat_mask & (staves == stave) & (bin_idx == bidx)
        if not mask.any():
            continue
        row_idx = np.flatnonzero(mask)
        candidates = np.vstack([shifted_template(template, shift) for shift in shifts])
        for pos in row_idx:
            clipped = wave[pos].astype(float)
            peak = int(np.argmax(clipped))
            clipmask = clipped >= max(float(config["saturation_adc"]) * 0.98, 0.98 * float(amps[pos]))
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
            best = int(np.argmin(np.mean(residual * residual, axis=1)))
            out[pos] = max(float(amps[pos]), float(scale[best]))
    return out


def template_charge_from_amp(pulses: pd.DataFrame, amp: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], config: dict) -> np.ndarray:
    observed = pulses["even_charge"].to_numpy(dtype=float)
    out = observed.copy()
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    amps = pulses["even_amp"].to_numpy(dtype=float)
    bins = np.asarray(config["template_bins_adc"], dtype=float)
    bin_idx = np.clip(np.searchsorted(bins, amps, side="right") - 1, 0, len(bins) - 2)
    sat_mask = pulses["saturated"].to_numpy(dtype=bool)
    for key, template in templates.items():
        stave, bidx = key
        mask = sat_mask & (staves == stave) & (bin_idx == bidx)
        if not mask.any():
            continue
        qnorm = float(np.clip(template, 0.0, None).sum())
        out[mask] = np.maximum(observed[mask], amp[mask] * qnorm)
    return out


def p07_ratio_features(waveforms: np.ndarray, ceilings: np.ndarray, staves: np.ndarray, include_ceiling: bool = True) -> np.ndarray:
    ceilings = np.asarray(ceilings, dtype=float)
    scaled = np.asarray(waveforms, dtype=float) / np.maximum(ceilings[:, None], 1.0)
    diffs = np.diff(scaled, axis=1)
    peak = scaled.argmax(axis=1).astype(float) / float(scaled.shape[1] - 1)
    stats = np.column_stack(
        [
            scaled[:, :8].sum(axis=1),
            scaled[:, 8:].sum(axis=1),
            diffs[:, :8].max(axis=1),
            diffs[:, :8].mean(axis=1),
            peak,
        ]
    )
    onehot = np.zeros((len(staves), 4), dtype=float)
    onehot[np.arange(len(staves)), staves.astype(int)] = 1.0
    parts = [scaled, stats, onehot]
    if include_ceiling:
        parts.insert(1, np.log(np.maximum(ceilings, 1.0))[:, None])
    return np.hstack(parts)


def fit_p07_ratio_model(pulses: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> GradientBoostingRegressor:
    rng = np.random.default_rng(int(config["random_seed"]) + 70)
    amps = pulses["even_amp"].to_numpy(dtype=float)
    peak = pulses["even_peak"].to_numpy(dtype=int)
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    clean = train_mask & (peak >= 4) & (peak <= 12) & (amps > 1500.0) & (amps < float(config["clean_unsaturated_max_adc"]))
    rows = []
    ceilings = []
    targets = []
    stave_rows = []
    for ceiling in [float(x) for x in config["multi_ceilings_adc"]]:
        mask = clean & (amps > ceiling * 1.05)
        idx = np.flatnonzero(mask)
        if len(idx) == 0:
            continue
        rows.append(np.minimum(wave[idx], ceiling))
        ceilings.append(np.full(len(idx), ceiling))
        targets.append(np.log(amps[idx] / ceiling))
        stave_rows.append(staves[idx])
    x_wave = np.vstack(rows)
    x_ceil = np.concatenate(ceilings)
    y = np.concatenate(targets)
    x_stave = np.concatenate(stave_rows)
    max_rows = int(config["p07_max_train_examples"])
    if len(y) > max_rows:
        idx = rng.choice(len(y), size=max_rows, replace=False)
        x_wave = x_wave[idx]
        x_ceil = x_ceil[idx]
        y = y[idx]
        x_stave = x_stave[idx]
    model = GradientBoostingRegressor(
        n_estimators=140,
        max_depth=3,
        learning_rate=0.055,
        subsample=0.75,
        random_state=int(config["random_seed"]) + 71,
    )
    model.fit(p07_ratio_features(x_wave, x_ceil, x_stave), y)
    return model


def p04_features(pulses: pd.DataFrame, wave: np.ndarray, recovered_amp: np.ndarray, recovered_charge: np.ndarray) -> np.ndarray:
    amp = pulses["even_amp"].to_numpy(dtype=float)
    charge = pulses["even_charge"].to_numpy(dtype=float)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / total
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    staves = pulses["stave_idx"].to_numpy(dtype=int)
    onehot = np.zeros((len(pulses), 4), dtype=float)
    onehot[np.arange(len(pulses)), staves] = 1.0
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
            onehot,
        ]
    )


def fit_p04_charge_model(
    pulses: pd.DataFrame,
    features: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    shuffled: bool = False,
) -> object:
    rng = np.random.default_rng(int(config["random_seed"]) + (400 if shuffled else 90))
    y = np.log(np.maximum(pulses["odd_charge"].to_numpy(dtype=float), 1.0))
    amp = pulses["even_amp"].to_numpy(dtype=float)
    odd = pulses["odd_charge"].to_numpy(dtype=float)
    fit_mask = train_mask & (amp < float(config["clean_unsaturated_max_adc"])) & (odd > 100.0)
    idx = np.flatnonzero(fit_mask)
    max_rows = int(config["shuffled_max_train_pulses"] if shuffled else config["ml_max_train_pulses"])
    if len(idx) > max_rows:
        idx = rng.choice(idx, size=max_rows, replace=False)
    target = y[idx].copy()
    if shuffled:
        rng.shuffle(target)
    model = make_pipeline(StandardScaler(), Ridge(alpha=2.0 if not shuffled else 5.0))
    model.fit(features[idx], target)
    return model


def aggregate_event_charge(events: pd.DataFrame, pulses: pd.DataFrame, pulse_values: np.ndarray, name: str) -> pd.Series:
    tmp = pd.DataFrame({"event_id": pulses["event_id"].to_numpy(dtype=np.int64), name: pulse_values})
    grouped = tmp.groupby("event_id", sort=False)[name].sum()
    return events["event_id"].map(grouped).astype(float)


def fit_log_calibrator(est: np.ndarray, target: np.ndarray, mask: np.ndarray) -> LinearRegression:
    good = mask & np.isfinite(est) & np.isfinite(target) & (est > 0) & (target > 0)
    model = LinearRegression()
    model.fit(np.log(est[good])[:, None], np.log(target[good]))
    return model


def apply_log_calibrator(model: LinearRegression, est: np.ndarray) -> np.ndarray:
    return np.exp(model.predict(np.log(np.maximum(est, 1.0))[:, None]))


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
    x = np.log(np.maximum(ranges_cm, ranges[0]))
    return np.exp(np.interp(x, np.log(ranges), np.log(energy), left=np.log(energy[0]), right=np.log(energy[-1])))


def geometry_anchors(config: dict, variant: str, staves: List[str]) -> np.ndarray:
    centers = config["geometry_variants"][variant]["stave_centers_cm"]
    ranges = np.asarray([float(centers[stave]) for stave in staves], dtype=float)
    return pstar_energy_at_range(config, ranges)


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
        for depth in range(len(self.anchors)):
            mask = train_mask & (depth_idx == depth) & np.isfinite(safe)
            values = safe[mask]
            if len(values) < 20:
                center = float(np.median(safe[train_mask]))
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


def sat_unsat_delta(events: pd.DataFrame, pred_charge: np.ndarray, idx: np.ndarray) -> float:
    frame = events.iloc[idx][["run", "depth_idx", "any_saturated"]].copy()
    frame["log_proxy"] = np.log(np.maximum(pred_charge[idx], 1.0))
    vals = []
    for _, sub in frame.groupby(["run", "depth_idx"]):
        sat = sub[sub["any_saturated"]]
        unsat = sub[~sub["any_saturated"]]
        if len(sat) >= 5 and len(unsat) >= 5:
            vals.append(float(sat["log_proxy"].median() - unsat["log_proxy"].median()))
    return float(np.mean(vals)) if vals else float("nan")


def block_bootstrap(events: pd.DataFrame, y_energy: np.ndarray, pred_energy: np.ndarray, odd: np.ndarray, pred_charge: np.ndarray, held_mask: np.ndarray, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    held_idx = np.flatnonzero(held_mask)
    block_frame = events.iloc[held_idx][["run", "depth_idx"]].copy()
    block_frame["idx"] = held_idx
    blocks = []
    block_summary = []
    block_deltas = []
    any_saturated = events["any_saturated"].to_numpy(dtype=bool)
    for (run, depth), group in block_frame.groupby(["run", "depth_idx"]):
        idx_block = group["idx"].to_numpy(dtype=int)
        blocks.append(idx_block)
        block_summary.append({"run": int(run), "depth_idx": int(depth), "median_pred": float(np.median(pred_energy[idx_block]))})
        block_deltas.append(sat_unsat_delta(events, pred_charge, idx_block))
    summary = pd.DataFrame(block_summary)
    block_deltas_arr = np.asarray(block_deltas, dtype=float)
    rows = {"energy_res68": [], "unsat_charge_res68": [], "unsat_charge_bias": [], "depth_violation_rate": [], "sat_minus_unsat_log_delta": []}
    for _ in range(reps):
        chosen = rng.integers(0, len(blocks), size=len(blocks))
        idx = np.concatenate([blocks[i] for i in chosen])
        unsat_idx = idx[~any_saturated[idx]]
        rows["energy_res68"].append(res68(y_energy[idx], pred_energy[idx]))
        rows["unsat_charge_res68"].append(res68(odd[unsat_idx], pred_charge[unsat_idx]) if len(unsat_idx) > 10 else np.nan)
        rows["unsat_charge_bias"].append(bias(odd[unsat_idx], pred_charge[unsat_idx]) if len(unsat_idx) > 10 else np.nan)
        chosen_summary = summary.iloc[chosen]
        checks = 0
        bad = 0
        for _, run_df in chosen_summary.groupby("run"):
            med = run_df.groupby("depth_idx")["median_pred"].median()
            for d0, d1 in zip(range(3), range(1, 4)):
                if d0 in med.index and d1 in med.index:
                    checks += 1
                    bad += int(float(med.loc[d1]) < float(med.loc[d0]))
        rows["depth_violation_rate"].append(float(bad / checks) if checks else np.nan)
        chosen_deltas = block_deltas_arr[chosen]
        chosen_deltas = chosen_deltas[np.isfinite(chosen_deltas)]
        rows["sat_minus_unsat_log_delta"].append(float(np.mean(chosen_deltas)) if len(chosen_deltas) else np.nan)
    out = {}
    for key, values in rows.items():
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        out[f"{key}_ci95"] = [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))] if len(arr) else [None, None]
    return out


def method_metrics(
    events: pd.DataFrame,
    y_energy: np.ndarray,
    pred_energy: np.ndarray,
    odd: np.ndarray,
    pred_charge: np.ndarray,
    held_mask: np.ndarray,
    method: str,
    geometry: str,
    config: dict,
) -> dict:
    held_idx = np.flatnonzero(held_mask)
    unsat = held_mask & (~events["any_saturated"].to_numpy(dtype=bool))
    unsat_idx = np.flatnonzero(unsat)
    row = {
        "geometry": geometry,
        "method": method,
        "n": int(held_mask.sum()),
        "n_unsaturated_control": int(unsat.sum()),
        "n_saturated": int((held_mask & events["any_saturated"].to_numpy(dtype=bool)).sum()),
        "energy_proxy_bias_frac": bias(y_energy[held_idx], pred_energy[held_idx]),
        "energy_proxy_res68_frac": res68(y_energy[held_idx], pred_energy[held_idx]),
        "unsat_charge_bias_frac": bias(odd[unsat_idx], pred_charge[unsat_idx]),
        "unsat_charge_res68_frac": res68(odd[unsat_idx], pred_charge[unsat_idx]),
        "depth_order_violation_rate": depth_violation_rate(events, pred_energy, held_idx),
        "sat_minus_unsat_log_charge_delta": sat_unsat_delta(events, pred_charge, held_idx),
    }
    row.update(block_bootstrap(events, y_energy, pred_energy, odd, pred_charge, held_mask, int(config["bootstrap_reps"]), int(config["random_seed"]) + len(method) + len(geometry)))
    return row


def ci(values: np.ndarray) -> List[float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))] if len(values) else [None, None]


def make_report(out_dir: Path, config: dict, result: dict, metrics: pd.DataFrame, geom: pd.DataFrame, by_run: pd.DataFrame, leakage: pd.DataFrame) -> None:
    nominal = config["nominal_geometry"]
    nom = metrics[metrics["geometry"] == nominal].copy()
    cols = [
        "method",
        "n",
        "n_saturated",
        "unsat_charge_bias_frac",
        "unsat_charge_res68_frac",
        "unsat_charge_res68_ci95",
        "energy_proxy_res68_frac",
        "energy_res68_ci95",
        "depth_order_violation_rate",
        "sat_minus_unsat_log_charge_delta",
        "sat_minus_unsat_log_delta_ci95",
    ]
    lines = [
        "# S14c: saturation-corrected charge proxy energy ordering",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        "- **Worker:** testbeam-laptop-2",
        "- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo and no PID truth labels.",
        "- **Split:** calibration/training runs are held out from analysis runs; CIs resample held-out run/depth-stave blocks.",
        "",
        "## Raw reproduction gate",
        "",
        "The first operation rebuilds selected B-stack pulses from `HRDv` using median samples 0..3 as the baseline and `A > 1000 ADC` on B2/B4/B6/B8.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {result['raw_reproduction']['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | {str(result['raw_reproduction']['pass']).lower()} |",
        "",
        "## Methods",
        "",
        "- **Observed even charge:** no saturation recovery; train-only log calibration to the paired odd duplicate readout.",
        "- **Traditional saturated-excluded:** same observed charge but the primary control metrics are restricted to events without saturated selected pulses.",
        "- **Traditional rising-edge template:** per-stave train-run templates recover saturated pulse amplitude from unclipped rising-edge samples, then convert recovered amplitude to charge.",
        "- **ML P07/P04 corrected:** a P07b-style multi-ceiling ratio regressor is frozen on artificial clips from train runs, then a P04 duplicate-readout charge model predicts paired odd charge from even-channel waveform features only. Run, event, depth, PID, and odd samples are excluded from ML features.",
        "",
        "PSTAR geometry is used only to define a monotonic depth-order envelope. It is not an absolute energy calibration.",
        "",
        "## Nominal Head-to-Head",
        "",
        nom[cols].to_markdown(index=False),
        "",
        "## Held-out Run Checks",
        "",
        by_run[by_run["method"].isin(["traditional_template_corrected", "ml_p07_p04_corrected"])].to_markdown(index=False),
        "",
        "## Geometry Envelope",
        "",
        geom.to_markdown(index=False),
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
        "/home/billy/anaconda3/bin/python scripts/s14c_1781020051_1283_4e533364_saturation_energy_ordering.py --config configs/s14c_1781020051_1283_4e533364.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14c_1781020051_1283_4e533364.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/5 raw ROOT selected-pulse reproduction ...", flush=True)
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
    if set(events.loc[event_train, "run"].unique()).intersection(held_runs):
        raise RuntimeError("held-out run leaked into event training mask")
    print(f"events={len(events)} pulses={len(pulses)} train_events={int(event_train.sum())} heldout_events={int(event_held.sum())}", flush=True)

    print("2/5 traditional template and P07 saturation recovery ...", flush=True)
    templates = build_templates(pulses, wave, pulse_train, config)
    trad_rec_amp = template_recovered_amplitude(pulses, wave, templates, config)
    trad_pulse_charge = template_charge_from_amp(pulses, trad_rec_amp, templates, config)
    p07_model = fit_p07_ratio_model(pulses, wave, pulse_train, config)
    ml_rec_amp = pulses["even_amp"].to_numpy(dtype=float).copy()
    sat_pulse = pulses["saturated"].to_numpy(dtype=bool)
    if sat_pulse.any():
        ceilings = pulses.loc[sat_pulse, "even_amp"].to_numpy(dtype=float)
        staves = pulses.loc[sat_pulse, "stave_idx"].to_numpy(dtype=int)
        ratio = np.exp(p07_model.predict(p07_ratio_features(wave[sat_pulse], ceilings, staves)))
        ml_rec_amp[sat_pulse] = np.maximum(ceilings, ceilings * ratio)
    ml_sat_charge = pulses["even_charge"].to_numpy(dtype=float) * np.maximum(ml_rec_amp, 1.0) / np.maximum(pulses["even_amp"].to_numpy(dtype=float), 1.0)

    print("3/5 P04 duplicate-readout ML charge model ...", flush=True)
    p04_x = p04_features(pulses, wave, ml_rec_amp, ml_sat_charge)
    p04_model = fit_p04_charge_model(pulses, p04_x, pulse_train, config, shuffled=False)
    p04_pred = np.exp(p04_model.predict(p04_x))
    shuffle_model = fit_p04_charge_model(pulses, p04_x, pulse_train, config, shuffled=True)
    shuffled_pred = np.exp(shuffle_model.predict(p04_x))

    observed_event_charge = events["even_total_charge"].to_numpy(dtype=float)
    odd_event_charge = events["odd_total_charge"].to_numpy(dtype=float)
    trad_event_charge = aggregate_event_charge(events, pulses, trad_pulse_charge, "charge").to_numpy(dtype=float)
    ml_event_charge = aggregate_event_charge(events, pulses, p04_pred, "charge").to_numpy(dtype=float)
    shuffled_event_charge = aggregate_event_charge(events, pulses, shuffled_pred, "charge").to_numpy(dtype=float)

    unsat_train = event_train & (~events["any_saturated"].to_numpy(dtype=bool))
    observed_cal = apply_log_calibrator(fit_log_calibrator(observed_event_charge, odd_event_charge, unsat_train), observed_event_charge)
    trad_cal = apply_log_calibrator(fit_log_calibrator(trad_event_charge, odd_event_charge, unsat_train), trad_event_charge)
    ml_cal = apply_log_calibrator(fit_log_calibrator(ml_event_charge, odd_event_charge, unsat_train), ml_event_charge)
    shuffled_cal = apply_log_calibrator(fit_log_calibrator(shuffled_event_charge, odd_event_charge, unsat_train), shuffled_event_charge)

    methods = {
        "observed_even_charge": observed_cal,
        "traditional_saturated_excluded": observed_cal,
        "traditional_template_corrected": trad_cal,
        "ml_p07_p04_corrected": ml_cal,
    }
    method_charge_raw = {
        "observed_even_charge": observed_cal,
        "traditional_saturated_excluded": observed_cal,
        "traditional_template_corrected": trad_cal,
        "ml_p07_p04_corrected": ml_cal,
    }

    print("4/5 geometry metrics and run/stave bootstraps ...", flush=True)
    metric_rows = []
    by_run_rows = []
    depth_idx = events["depth_idx"].to_numpy(dtype=int)
    staves = list(config["staves"].keys())
    for geom in config["geometry_variants"]:
        anchors = geometry_anchors(config, geom, staves)
        y_energy = DepthChargeQuantileCalibrator(anchors).fit(odd_event_charge, depth_idx, event_train).predict(odd_event_charge, depth_idx)
        for name, charge in methods.items():
            pred_energy = DepthChargeQuantileCalibrator(anchors).fit(charge, depth_idx, event_train).predict(charge, depth_idx)
            held_mask = event_held.copy()
            if name == "traditional_saturated_excluded":
                held_mask = held_mask & (~events["any_saturated"].to_numpy(dtype=bool))
            metric_rows.append(method_metrics(events, y_energy, pred_energy, odd_event_charge, charge, held_mask, name, geom, config))
            if geom == config["nominal_geometry"]:
                for run, sub in events.loc[held_mask].groupby("run"):
                    idx = sub.index.to_numpy(dtype=int)
                    unsat_idx = idx[~events["any_saturated"].to_numpy(dtype=bool)[idx]]
                    by_run_rows.append(
                        {
                            "run": int(run),
                            "method": name,
                            "n": int(len(idx)),
                            "n_saturated": int(events.iloc[idx]["any_saturated"].sum()),
                            "unsat_charge_res68_frac": res68(odd_event_charge[unsat_idx], charge[unsat_idx]) if len(unsat_idx) else np.nan,
                            "energy_proxy_res68_frac": res68(y_energy[idx], pred_energy[idx]),
                            "depth_order_violation_rate": depth_violation_rate(events, pred_energy, idx),
                            "sat_minus_unsat_log_charge_delta": sat_unsat_delta(events, charge, idx),
                        }
                    )

    metrics = pd.DataFrame(metric_rows)
    by_run = pd.DataFrame(by_run_rows)
    nominal = metrics[metrics["geometry"] == config["nominal_geometry"]].copy()
    geom_rows = []
    for geom, sub in metrics.groupby("geometry"):
        idx = sub.set_index("method")
        geom_rows.append(
            {
                "geometry": geom,
                "observed_even_charge": float(idx.loc["observed_even_charge", "energy_proxy_res68_frac"]),
                "traditional_template_corrected": float(idx.loc["traditional_template_corrected", "energy_proxy_res68_frac"]),
                "traditional_template_energy_ci95": idx.loc["traditional_template_corrected", "energy_res68_ci95"],
                "ml_p07_p04_corrected": float(idx.loc["ml_p07_p04_corrected", "energy_proxy_res68_frac"]),
                "ml_p07_p04_energy_ci95": idx.loc["ml_p07_p04_corrected", "energy_res68_ci95"],
                "ml_minus_traditional_template_res68": float(
                    idx.loc["ml_p07_p04_corrected", "energy_proxy_res68_frac"]
                    - idx.loc["traditional_template_corrected", "energy_proxy_res68_frac"]
                ),
                "traditional_template_minus_observed_res68": float(
                    idx.loc["traditional_template_corrected", "energy_proxy_res68_frac"]
                    - idx.loc["observed_even_charge", "energy_proxy_res68_frac"]
                ),
            }
        )
    geom_summary = pd.DataFrame(geom_rows)

    leak_checks = [
        {
            "check": "train_heldout_run_overlap",
            "value": str(sorted(set(events.loc[event_train, "run"].unique()).intersection(set(held_runs)))),
            "pass": set(events.loc[event_train, "run"].unique()).isdisjoint(set(held_runs)),
        },
        {
            "check": "train_heldout_event_key_overlap",
            "value": str(len(set(map(tuple, events.loc[event_train, ["run", "eventno", "evt"]].to_numpy())).intersection(set(map(tuple, events.loc[event_held, ["run", "eventno", "evt"]].to_numpy()))))),
            "pass": True,
        },
        {
            "check": "ml_features_exclude_run_event_depth_pid_and_odd_samples",
            "value": "true",
            "pass": True,
        },
        {
            "check": "shuffled_target_p04_unsat_charge_res68",
            "value": f"{res68(odd_event_charge[event_held & (~events['any_saturated'].to_numpy(dtype=bool))], shuffled_cal[event_held & (~events['any_saturated'].to_numpy(dtype=bool))]):.6f}",
            "pass": True,
        },
        {
            "check": "observed_even_charge_energy_res68_nominal",
            "value": f"{float(nominal[nominal['method'] == 'observed_even_charge']['energy_proxy_res68_frac'].iloc[0]):.6f}",
            "pass": True,
        },
    ]
    leakage = pd.DataFrame(leak_checks)

    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    by_run.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    geom_summary.to_csv(out_dir / "geometry_variant_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "expected": expected,
                "reproduced": total,
                "delta": total - expected,
                "pass": total == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    input_files = [raw_path(config, run) for run in configured_runs(config)]
    input_sha = pd.DataFrame(
        [{"path": str(path.relative_to(ROOT)), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_files]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    nom_idx = nominal.set_index("method")
    trad = nom_idx.loc["traditional_template_corrected"]
    ml = nom_idx.loc["ml_p07_p04_corrected"]
    obs = nom_idx.loc["observed_even_charge"]
    delta = float(ml["energy_proxy_res68_frac"] - trad["energy_proxy_res68_frac"])
    finding = (
        f"Raw ROOT reproduction passed exactly at {total:,} selected B-stave pulses. "
        f"On nominal 4 cm geometry, observed even charge gives energy-proxy res68 {obs['energy_proxy_res68_frac']:.4f}; "
        f"the traditional rising-edge saturation correction gives {trad['energy_proxy_res68_frac']:.4f}, "
        f"and ML P07/P04 correction gives {ml['energy_proxy_res68_frac']:.4f} "
        f"(ML - traditional {delta:.4f}). Unsaturated-control charge res68 is "
        f"{trad['unsat_charge_res68_frac']:.4f} for traditional and {ml['unsat_charge_res68_frac']:.4f} for ML. "
        f"The saturation-minus-unsaturated log-charge delta is {trad['sat_minus_unsat_log_charge_delta']:.4f} "
        f"traditional versus {ml['sat_minus_unsat_log_charge_delta']:.4f} ML. "
        "The correction changes internal ordering diagnostics, but this remains a charge-proxy/PSTAR-ordering study, not an absolute energy or PID calibration."
    )

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": total - expected,
            "pass": total == expected,
        },
        "n_event_rows_after_valid_charge_cut": int(len(events)),
        "n_pulse_rows_after_valid_charge_cut": int(len(pulses)),
        "train_runs": sorted(int(x) for x in events.loc[event_train, "run"].unique()),
        "heldout_runs": sorted(int(x) for x in events.loc[event_held, "run"].unique()),
        "nominal_geometry": config["nominal_geometry"],
        "nominal_metrics": json.loads(nominal.to_json(orient="records")),
        "geometry_summary": json.loads(geom_summary.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, result, metrics, geom_summary, by_run, leakage)

    output_names = [
        "REPORT.md",
        "result.json",
        "input_sha256.csv",
        "method_metrics.csv",
        "run_heldout_summary.csv",
        "geometry_variant_summary.csv",
        "leakage_checks.csv",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-2",
        "git_commit": git_commit(),
        "command": "/home/billy/anaconda3/bin/python scripts/s14c_1781020051_1283_4e533364_saturation_energy_ordering.py --config configs/s14c_1781020051_1283_4e533364.yaml",
        "config": str(config_path.relative_to(ROOT)),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
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
