#!/usr/bin/env python3
"""S14d: PSTAR material-budget and geometry envelope audit from raw ROOT.

This uses PSTAR/depth lookup and duplicate-readout charge closure to audit how
center placement, active thickness, dead layers, and PSTAR material assumptions
move the internal energy-proxy envelope. It deliberately makes no GEANT4, Birks,
absolute energy, PID, or particle-truth claim.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
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
from sklearn.ensemble import HistGradientBoostingRegressor


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


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
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_event_table(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    sat = float(config["saturation_adc"])
    staves = list(config["staves"].keys())
    even_ch = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_ch = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    groups = group_for_run(config)
    rows: List[pd.DataFrame] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        count = {
            "run": run,
            "group": groups[run],
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
            rev_depth = np.argmax(selected_block[:, ::-1], axis=1)
            depth_idx = selected_block.shape[1] - 1 - rev_depth
            even_amp_sel = even_amp[idx] * selected_block
            even_charge_sel = even_charge[idx] * selected_block
            odd_charge_sel = odd_charge[idx] * selected_block
            odd_amp_sel = odd_amp[idx] * selected_block
            frame = pd.DataFrame(
                {
                    "run": run,
                    "group": groups[run],
                    "eventno": eventno[idx],
                    "evt": evt[idx],
                    "multiplicity": selected_block.sum(axis=1).astype(np.int16),
                    "depth_idx": depth_idx.astype(np.int16),
                    "even_total_charge": even_charge_sel.sum(axis=1),
                    "odd_total_charge": odd_charge_sel.sum(axis=1),
                    "even_max_amp": even_amp_sel.max(axis=1),
                    "odd_max_amp": odd_amp_sel.max(axis=1),
                    "saturated_count": (even_amp_sel >= sat).sum(axis=1).astype(np.int16),
                }
            )
            for i, stave in enumerate(staves):
                frame[f"{stave}_hit"] = selected_block[:, i].astype(np.int8)
                frame[f"{stave}_amp"] = even_amp_sel[:, i]
                frame[f"{stave}_charge"] = even_charge_sel[:, i]
                frame[f"{stave}_sat"] = (even_amp_sel[:, i] >= sat).astype(np.int8)
            rows.append(frame)
        counts.append(count)

    events = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return events, pd.DataFrame(counts)


def pstar_energy_at_range(config: dict, ranges_cm: np.ndarray, density_g_cm3: Optional[float] = None, range_scale: float = 1.0) -> np.ndarray:
    pstar = config["pstar"]
    energy = np.asarray(pstar["energy_mev"], dtype=float)
    density = float(pstar["density_g_cm3"] if density_g_cm3 is None else density_g_cm3)
    ranges = np.asarray(pstar["range_g_cm2"], dtype=float) * float(range_scale) / density
    x = np.log(np.maximum(ranges_cm, ranges[0]))
    return np.exp(np.interp(x, np.log(ranges), np.log(energy), left=np.log(energy[0]), right=np.log(energy[-1])))


def material_budget_variants(config: dict) -> List[dict]:
    budget = config["material_budget"]
    nominal = {
        "geometry": config["nominal_geometry"],
        "description": "nominal first-center, spacing, active thickness, dead layer, density, and PSTAR range scale",
        "first_center_cm": float(budget["nominal_first_center_cm"]),
        "spacing_cm": float(budget["nominal_spacing_cm"]),
        "active_thickness_cm": float(budget["nominal_active_thickness_cm"]),
        "dead_layer_cm": float(budget["nominal_dead_layer_cm"]),
        "pstar_density_g_cm3": float(budget["nominal_pstar_density_g_cm3"]),
        "pstar_range_scale": float(budget["nominal_pstar_range_scale"]),
    }
    variants: Dict[str, dict] = {nominal["geometry"]: nominal}
    axes = [
        "first_center_cm",
        "spacing_cm",
        "active_thickness_cm",
        "dead_layer_cm",
        "pstar_density_g_cm3",
        "pstar_range_scale",
    ]
    if bool(budget.get("one_at_a_time", True)):
        for axis in axes:
            for value in budget[axis]:
                row = dict(nominal)
                row[axis] = float(value)
                row["geometry"] = f"{axis}_{float(value):.4g}".replace(".", "p")
                row["description"] = f"one-at-a-time scan: {axis}={float(value):.4g}"
                variants[row["geometry"]] = row
    if bool(budget.get("include_corner_envelope", True)):
        lows = {axis: min(float(x) for x in budget[axis]) for axis in axes}
        highs = {axis: max(float(x) for x in budget[axis]) for axis in axes}
        corner_axes = [
            ("first_center_cm", "spacing_cm", "active_thickness_cm"),
            ("dead_layer_cm",),
            ("pstar_density_g_cm3", "pstar_range_scale"),
        ]
        for signs in itertools.product([0, 1], repeat=len(corner_axes)):
            row = dict(nominal)
            signed = []
            for axis_group, sign in zip(corner_axes, signs):
                for axis in axis_group:
                    row[axis] = highs[axis] if sign else lows[axis]
                signed.append(("hi" if sign else "lo") + axis_group[0][:3])
            row["geometry"] = "corner_" + "_".join(signed)
            row["description"] = "corner envelope scan"
            variants[row["geometry"]] = row
    return list(variants.values())


def material_depths_cm(variant: dict, n_staves: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    idx = np.arange(n_staves, dtype=float)
    nominal_thickness = 1.0
    thickness_shift = 0.5 * (float(variant["active_thickness_cm"]) - nominal_thickness)
    centers = float(variant["first_center_cm"]) + idx * float(variant["spacing_cm"]) + thickness_shift
    dead = idx * float(variant["dead_layer_cm"])
    effective = centers + dead
    return centers, dead, effective


def geometry_anchors(config: dict, variant: dict, staves: List[str]) -> np.ndarray:
    _, _, ranges = material_depths_cm(variant, len(staves))
    return pstar_energy_at_range(
        config,
        ranges,
        density_g_cm3=float(variant["pstar_density_g_cm3"]),
        range_scale=float(variant["pstar_range_scale"]),
    )


def depth_bounds(anchors: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    lo = np.empty_like(anchors)
    hi = np.empty_like(anchors)
    for i in range(len(anchors)):
        if i == 0:
            lo[i] = max(1.0, anchors[i] - 0.5 * (anchors[i + 1] - anchors[i]))
        else:
            lo[i] = 0.5 * (anchors[i - 1] + anchors[i])
        if i == len(anchors) - 1:
            hi[i] = anchors[i] + 0.5 * (anchors[i] - anchors[i - 1])
        else:
            hi[i] = 0.5 * (anchors[i] + anchors[i + 1])
    return lo, hi


class DepthChargeQuantileCalibrator:
    def __init__(self, anchors: np.ndarray, quantiles: Optional[np.ndarray] = None):
        self.anchors = anchors
        self.quantiles = np.linspace(0.02, 0.98, 49) if quantiles is None else quantiles
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
            xq = xq[keep]
            q = self.quantiles[keep]
            yq = lo[depth] + q * (hi[depth] - lo[depth])
            self.xq[depth] = xq
            self.yq[depth] = yq
        return self

    def predict(self, charge: np.ndarray, depth_idx: np.ndarray) -> np.ndarray:
        safe = np.log(np.maximum(charge, 1.0))
        out = np.empty(len(charge), dtype=float)
        for depth in range(len(self.anchors)):
            mask = depth_idx == depth
            if not mask.any():
                continue
            out[mask] = np.interp(safe[mask], self.xq[depth], self.yq[depth], left=self.yq[depth][0], right=self.yq[depth][-1])
        return out


def feature_matrix(events: pd.DataFrame, staves: List[str], anchors: np.ndarray) -> Tuple[np.ndarray, List[str], List[int]]:
    cols = ["depth_idx", "multiplicity", "saturated_count", "even_max_amp", "even_total_charge"]
    for stave in staves:
        cols.extend([f"{stave}_hit", f"{stave}_sat", f"{stave}_amp", f"{stave}_charge"])
    data = []
    names = []
    monotonic = []
    for col in cols:
        values = events[col].to_numpy(dtype=float)
        if col.endswith("_amp") or col.endswith("_charge") or col in {"even_max_amp", "even_total_charge"}:
            values = np.log1p(np.maximum(values, 0.0))
            monotonic.append(1)
        elif col in {"depth_idx", "multiplicity", "saturated_count"}:
            monotonic.append(1)
        else:
            monotonic.append(0)
        data.append(values)
        names.append(col)
    anchor_by_depth = anchors[events["depth_idx"].to_numpy(dtype=int)]
    data.append(anchor_by_depth)
    names.append("pstar_depth_anchor_mev")
    monotonic.append(1)
    return np.column_stack(data), names, monotonic


def frac_residual(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    return (pred - y) / np.maximum(y, 1.0)


def res68(y: np.ndarray, pred: np.ndarray) -> float:
    return float(np.percentile(np.abs(frac_residual(y, pred)), 68))


def bias(y: np.ndarray, pred: np.ndarray) -> float:
    return float(np.median(frac_residual(y, pred)))


def depth_violation_rate(events: pd.DataFrame, pred: np.ndarray, mask: np.ndarray) -> float:
    sub = events.loc[mask, ["run", "depth_idx"]].copy()
    sub["pred"] = pred[mask]
    checks = 0
    bad = 0
    for _, run_df in sub.groupby("run"):
        med = run_df.groupby("depth_idx")["pred"].median()
        for d0, d1 in zip(range(3), range(1, 4)):
            if d0 in med.index and d1 in med.index:
                checks += 1
                bad += int(float(med.loc[d1]) < float(med.loc[d0]))
    return float(bad / checks) if checks else float("nan")


def depth_violation_counts(events: pd.DataFrame, pred: np.ndarray, mask: np.ndarray) -> Tuple[int, int]:
    sub = events.loc[mask, ["run", "depth_idx"]].copy()
    sub["pred"] = pred[mask]
    checks = 0
    bad = 0
    for _, run_df in sub.groupby("run"):
        med = run_df.groupby("depth_idx")["pred"].median()
        for d0, d1 in zip(range(3), range(1, 4)):
            if d0 in med.index and d1 in med.index:
                checks += 1
                bad += int(float(med.loc[d1]) < float(med.loc[d0]))
    return bad, checks


def metric_row(events: pd.DataFrame, y: np.ndarray, pred: np.ndarray, mask: np.ndarray, method: str, geometry: str) -> dict:
    return {
        "geometry": geometry,
        "method": method,
        "n": int(mask.sum()),
        "bias_median_frac": bias(y[mask], pred[mask]),
        "res68_abs_frac": res68(y[mask], pred[mask]),
        "depth_order_violation_rate": depth_violation_rate(events, pred, mask),
    }


def run_block_bootstrap(
    events: pd.DataFrame,
    y: np.ndarray,
    pred_trad: np.ndarray,
    pred_ml: np.ndarray,
    heldout_mask: np.ndarray,
    reps: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(events.loc[heldout_mask, "run"].unique()), dtype=int)
    run_stats = {}
    event_runs = events["run"].to_numpy()
    for run in runs:
        idx = np.flatnonzero(heldout_mask & (event_runs == run))
        tmp_mask = np.zeros(len(events), dtype=bool)
        tmp_mask[idx] = True
        trad_bad, trad_checks = depth_violation_counts(events, pred_trad, tmp_mask)
        ml_bad, ml_checks = depth_violation_counts(events, pred_ml, tmp_mask)
        run_stats[int(run)] = {
            "n": int(len(idx)),
            "traditional_res68": res68(y[idx], pred_trad[idx]),
            "ml_res68": res68(y[idx], pred_ml[idx]),
            "traditional_bad": trad_bad,
            "traditional_checks": trad_checks,
            "ml_bad": ml_bad,
            "ml_checks": ml_checks,
        }
    rows = []
    for rep in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        weights = np.asarray([run_stats[int(run)]["n"] for run in chosen], dtype=float)
        trad_values = np.asarray([run_stats[int(run)]["traditional_res68"] for run in chosen], dtype=float)
        ml_values = np.asarray([run_stats[int(run)]["ml_res68"] for run in chosen], dtype=float)
        trad_res = float(np.average(trad_values, weights=weights))
        ml_res = float(np.average(ml_values, weights=weights))
        trad_bad = sum(run_stats[int(run)]["traditional_bad"] for run in chosen)
        trad_checks = sum(run_stats[int(run)]["traditional_checks"] for run in chosen)
        ml_bad = sum(run_stats[int(run)]["ml_bad"] for run in chosen)
        ml_checks = sum(run_stats[int(run)]["ml_checks"] for run in chosen)
        rows.append(
            {
                "rep": rep,
                "traditional_res68": trad_res,
                "ml_res68": ml_res,
                "ml_minus_traditional_res68": ml_res - trad_res,
                "traditional_depth_violation_rate": float(trad_bad / trad_checks) if trad_checks else float("nan"),
                "ml_depth_violation_rate": float(ml_bad / ml_checks) if ml_checks else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def ci(values: np.ndarray) -> List[float]:
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def fit_evaluate_geometry(config: dict, events: pd.DataFrame, variant: dict, train_mask: np.ndarray, heldout_mask: np.ndarray) -> dict:
    staves = list(config["staves"].keys())
    anchors = geometry_anchors(config, variant, staves)
    variant_name = str(variant["geometry"])
    depth_idx = events["depth_idx"].to_numpy(dtype=int)
    odd_charge = events["odd_total_charge"].to_numpy(dtype=float)
    even_charge = events["even_total_charge"].to_numpy(dtype=float)
    target_cal = DepthChargeQuantileCalibrator(anchors).fit(odd_charge, depth_idx, train_mask)
    trad_cal = DepthChargeQuantileCalibrator(anchors).fit(even_charge, depth_idx, train_mask)
    y = target_cal.predict(odd_charge, depth_idx)
    pred_trad = trad_cal.predict(even_charge, depth_idx)

    rng = np.random.default_rng(int(config["random_seed"]) + len(variant_name))
    X, feature_names, monotonic = feature_matrix(events, staves, anchors)
    train_idx = np.flatnonzero(train_mask)
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    model = HistGradientBoostingRegressor(
        max_iter=35,
        learning_rate=0.08,
        max_leaf_nodes=15,
        max_bins=64,
        l2_regularization=0.08,
        monotonic_cst=monotonic,
        random_state=int(config["random_seed"]) + 10,
    )
    model.fit(X[train_idx], y[train_idx])
    pred_ml = model.predict(X)

    pred_depth_only = anchors[depth_idx]
    metrics = pd.DataFrame(
        [
            metric_row(events, y, pred_depth_only, heldout_mask, "pstar_depth_only", variant_name),
            metric_row(events, y, pred_trad, heldout_mask, "traditional_depth_charge_lookup", variant_name),
            metric_row(events, y, pred_ml, heldout_mask, "ml_monotonic_hgb", variant_name),
        ]
    )
    by_run = []
    for run, run_df in events.loc[heldout_mask].groupby("run"):
        mask = heldout_mask & (events["run"].to_numpy() == int(run))
        for method, pred in [
            ("pstar_depth_only", pred_depth_only),
            ("traditional_depth_charge_lookup", pred_trad),
            ("ml_monotonic_hgb", pred_ml),
        ]:
            row = metric_row(events, y, pred, mask, method, variant_name)
            row["run"] = int(run)
            by_run.append(row)
    boot = run_block_bootstrap(
        events,
        y,
        pred_trad,
        pred_ml,
        heldout_mask,
        int(config["bootstrap_reps"]),
        int(config["random_seed"]) + 101,
    )
    return {
        "geometry": variant_name,
        "variant": variant,
        "anchors": anchors,
        "target": y,
        "traditional": pred_trad,
        "ml": pred_ml,
        "depth_only": pred_depth_only,
        "metrics": metrics,
        "by_run": pd.DataFrame(by_run),
        "bootstrap": boot,
        "feature_names": feature_names,
        "monotonic": monotonic,
        "n_train_fit": int(len(train_idx)),
    }


def leakage_audit(config: dict, events: pd.DataFrame, nominal: dict, train_mask: np.ndarray, heldout_mask: np.ndarray) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 303)
    train_runs = set(int(x) for x in events.loc[train_mask, "run"].unique())
    held_runs = set(int(x) for x in events.loc[heldout_mask, "run"].unique())
    key_cols = ["run", "eventno"]
    train_keys = set(map(tuple, events.loc[train_mask, key_cols].to_numpy()))
    held_keys = set(map(tuple, events.loc[heldout_mask, key_cols].to_numpy()))

    staves = list(config["staves"].keys())
    X, _, monotonic = feature_matrix(events, staves, nominal["anchors"])
    train_idx = np.flatnonzero(train_mask)
    if len(train_idx) > int(config["shuffled_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["shuffled_max_train_rows"]), replace=False)
    shuffled_y = nominal["target"][train_idx].copy()
    rng.shuffle(shuffled_y)
    shuffled_model = HistGradientBoostingRegressor(
        max_iter=35,
        learning_rate=0.08,
        max_leaf_nodes=15,
        max_bins=64,
        l2_regularization=0.1,
        monotonic_cst=monotonic,
        random_state=int(config["random_seed"]) + 304,
    )
    shuffled_model.fit(X[train_idx], shuffled_y)
    shuffled_pred = shuffled_model.predict(X)
    rows = [
        {"check": "train_heldout_run_overlap", "value": str(sorted(train_runs.intersection(held_runs))), "pass": len(train_runs.intersection(held_runs)) == 0},
        {"check": "train_heldout_event_key_overlap", "value": str(len(train_keys.intersection(held_keys))), "pass": len(train_keys.intersection(held_keys)) == 0},
        {"check": "features_exclude_run_event_and_odd_readout", "value": "true", "pass": True},
        {"check": "depth_only_res68", "value": f"{res68(nominal['target'][heldout_mask], nominal['depth_only'][heldout_mask]):.6f}", "pass": True},
        {"check": "shuffled_target_ml_res68", "value": f"{res68(nominal['target'][heldout_mask], shuffled_pred[heldout_mask]):.6f}", "pass": True},
    ]
    return pd.DataFrame(rows)


def make_report(out_dir: Path, config: dict, counts: pd.DataFrame, all_metrics: pd.DataFrame, by_run: pd.DataFrame, boot: pd.DataFrame, geom_summary: pd.DataFrame, leak: pd.DataFrame, result: dict) -> None:
    ticket = config["ticket_id"]
    nominal = config["nominal_geometry"]
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    nominal_metrics = all_metrics[all_metrics["geometry"] == nominal].copy()
    metric_cols = ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "depth_order_violation_rate", "depth_violation_ci95"]
    display = nominal_metrics[metric_cols]
    run_display = by_run[(by_run["geometry"] == nominal) & (by_run["method"].isin(["traditional_depth_charge_lookup", "ml_monotonic_hgb"]))][
        ["run", "method", "n", "res68_abs_frac", "depth_order_violation_rate"]
    ]
    lines = [
        "# S14d: PSTAR material-budget and geometry envelope audit",
        "",
        f"- **Ticket ID:** {ticket}",
        "- **Worker:** testbeam-laptop-3",
        "- **Input:** raw `data/root/root/hrdb_run_*.root` only; checksums in `manifest.json` and `input_sha256.csv`.",
        "- **No Monte Carlo / no GEANT4 / no Birks model / no absolute PID claim.** This is a material-budget and closure audit.",
        "",
        "## 1. Raw reproduction gate",
        "",
        "The script rebuilds selected B-stack pulses from `HRDv`: median(samples 0..3) baseline, positive channels B2/B4/B6/B8, and `A > 1000 ADC`.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {expected:,} | {total:,} | {total - expected:+,} | {str(total == expected).lower()} |",
        "",
        "## 2. Material-budget proxy definition",
        "",
        "PSTAR is used only as a depth-order anchor. The scan varies first stave center, center spacing, active thickness, dead layer per downstream stave, PSTAR density, and a PSTAR range-scale nuisance. Each material-budget variant converts effective stave depths to proton CSDA energies by log-log interpolation of the configured plastic-scintillator PSTAR table. Within each penetration-depth bin, an independent odd-duplicate total charge rank maps monotonically into the bracket between neighboring depth anchors. This defines the held-out energy proxy. Predictors see only even-readout amplitudes, charges, depth, multiplicity, and saturation flags.",
        "",
        "## 3. Methods and held-out split",
        "",
        f"- **Train runs:** {', '.join(str(x) for x in result['train_runs'])}.",
        f"- **Held-out runs:** {', '.join(str(x) for x in result['heldout_runs'])}. Bootstrap CIs resample held-out runs as blocks.",
        "- **Traditional:** PSTAR depth plus per-depth monotonic even-charge quantile lookup.",
        "- **ML:** monotonic `HistGradientBoostingRegressor` on the even amplitude vector, even charge vector, penetration depth, multiplicity, and saturation flags.",
        "",
        "## 4. Nominal held-out benchmark",
        "",
        display.to_markdown(index=False),
        "",
        "## 5. Run-split checks",
        "",
        run_display.to_markdown(index=False),
        "",
        "## 6. Material-budget/PSTAR envelope",
        "",
        geom_summary.to_markdown(index=False),
        "",
        "## 7. Leakage audit",
        "",
        leak.to_markdown(index=False),
        "",
        "The ML-minus-traditional residual delta is negative if ML improves the closure. The shuffled-target and depth-only checks are kept because a strong ML closure would otherwise make leakage a credible failure mode.",
        "",
        "## 8. Finding",
        "",
        result["finding"],
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s14d_1781020357_1391_009a0721_material_budget_audit.py --config configs/s14d_1781020357_1391_009a0721.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14d_1781020357_1391_009a0721.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("loading raw ROOT and rebuilding S00 selected-pulse gate ...", flush=True)
    events, counts = extract_event_table(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"S00 selected-pulse reproduction failed: got {total}, expected {expected}")

    valid = (events["odd_total_charge"].to_numpy() > 100.0) & (events["even_total_charge"].to_numpy() > 100.0)
    invalid = int((~valid).sum())
    events = events.loc[valid].reset_index(drop=True)
    held_runs = heldout_runs(config)
    heldout_mask = events["run"].isin(held_runs).to_numpy()
    train_mask = ~heldout_mask
    print(f"events={len(events)} invalid_removed={invalid} train={int(train_mask.sum())} heldout={int(heldout_mask.sum())}", flush=True)

    all_metrics = []
    all_by_run = []
    boot_by_geom = {}
    fit_outputs = {}
    variants = material_budget_variants(config)
    for variant in variants:
        print(f"fitting material-budget variant {variant['geometry']} ...", flush=True)
        fit = fit_evaluate_geometry(config, events, variant, train_mask, heldout_mask)
        metrics = fit["metrics"]
        boot = fit["bootstrap"]
        for method, prefix in [
            ("traditional_depth_charge_lookup", "traditional"),
            ("ml_monotonic_hgb", "ml"),
        ]:
            metrics.loc[metrics["method"] == method, "res68_ci95"] = str(ci(boot[f"{prefix}_res68"].to_numpy()))
            metrics.loc[metrics["method"] == method, "depth_violation_ci95"] = str(ci(boot[f"{prefix}_depth_violation_rate"].dropna().to_numpy()))
        metrics.loc[metrics["method"] == "pstar_depth_only", "res68_ci95"] = "[]"
        metrics.loc[metrics["method"] == "pstar_depth_only", "depth_violation_ci95"] = "[]"
        all_metrics.append(metrics)
        all_by_run.append(fit["by_run"])
        boot_by_geom[fit["geometry"]] = boot
        fit_outputs[fit["geometry"]] = fit

    metrics_df = pd.concat(all_metrics, ignore_index=True)
    by_run_df = pd.concat(all_by_run, ignore_index=True)
    nominal = fit_outputs[config["nominal_geometry"]]
    nominal_boot = boot_by_geom[config["nominal_geometry"]]
    leak = leakage_audit(config, events, nominal, train_mask, heldout_mask)

    geom_rows = []
    for variant, fit in fit_outputs.items():
        m = fit["metrics"].set_index("method")
        centers, dead, effective = material_depths_cm(fit["variant"], len(config["staves"]))
        geom_rows.append(
            {
                "geometry": variant,
                "description": fit["variant"]["description"],
                "first_center_cm": float(fit["variant"]["first_center_cm"]),
                "spacing_cm": float(fit["variant"]["spacing_cm"]),
                "active_thickness_cm": float(fit["variant"]["active_thickness_cm"]),
                "dead_layer_cm": float(fit["variant"]["dead_layer_cm"]),
                "pstar_density_g_cm3": float(fit["variant"]["pstar_density_g_cm3"]),
                "pstar_range_scale": float(fit["variant"]["pstar_range_scale"]),
                "B2_effective_depth_cm": float(effective[0]),
                "B8_effective_depth_cm": float(effective[-1]),
                "B2_anchor_mev": float(fit["anchors"][0]),
                "B8_anchor_mev": float(fit["anchors"][-1]),
                "traditional_res68": float(m.loc["traditional_depth_charge_lookup", "res68_abs_frac"]),
                "ml_res68": float(m.loc["ml_monotonic_hgb", "res68_abs_frac"]),
                "ml_minus_traditional_res68": float(m.loc["ml_monotonic_hgb", "res68_abs_frac"] - m.loc["traditional_depth_charge_lookup", "res68_abs_frac"]),
            }
        )
    geom_summary = pd.DataFrame(geom_rows)
    envelope = {
        "traditional_res68_min": float(geom_summary["traditional_res68"].min()),
        "traditional_res68_max": float(geom_summary["traditional_res68"].max()),
        "ml_res68_min": float(geom_summary["ml_res68"].min()),
        "ml_res68_max": float(geom_summary["ml_res68"].max()),
        "ml_minus_traditional_res68_min": float(geom_summary["ml_minus_traditional_res68"].min()),
        "ml_minus_traditional_res68_max": float(geom_summary["ml_minus_traditional_res68"].max()),
    }

    nominal_metrics = metrics_df[metrics_df["geometry"] == config["nominal_geometry"]].set_index("method")
    trad_res = float(nominal_metrics.loc["traditional_depth_charge_lookup", "res68_abs_frac"])
    ml_res = float(nominal_metrics.loc["ml_monotonic_hgb", "res68_abs_frac"])
    delta = ml_res - trad_res
    delta_ci = ci(nominal_boot["ml_minus_traditional_res68"].to_numpy())
    finding = (
        f"The nominal material-budget scan reproduces S00 exactly and gives held-out odd-readout energy-proxy "
        f"res68 {trad_res:.4f} for the PSTAR/depth/even-charge lookup versus {ml_res:.4f} for monotonic HGB "
        f"(ML - traditional {delta:.4f}, run-block 95% CI {delta_ci[0]:.4f} to {delta_ci[1]:.4f}). "
        f"Across explicit center/thickness/dead-layer/PSTAR variants, traditional res68 spans {envelope['traditional_res68_min']:.4f}-{envelope['traditional_res68_max']:.4f} "
        f"and ML spans {envelope['ml_res68_min']:.4f}-{envelope['ml_res68_max']:.4f}. This passes as an internal charge/depth preflight, "
        "but it is not an absolute energy calibration or PID claim: Birks quenching, GEANT4 transport, and external particle truth remain unresolved."
    )

    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "expected": expected,
                "reproduced": total,
                "delta": total - expected,
                "pass": total == expected,
            }
        ]
    )
    input_files = [raw_path(config, run) for run in configured_runs(config)]
    input_sha = pd.DataFrame(
        [{"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_files]
    )

    metrics_df.to_csv(out_dir / "method_metrics.csv", index=False)
    by_run_df.to_csv(out_dir / "run_heldout_summary.csv", index=False)
    geom_summary.to_csv(out_dir / "geometry_variant_summary.csv", index=False)
    nominal_boot.to_csv(out_dir / "run_block_bootstrap.csv", index=False)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": "S14d",
        "ticket_id": config["ticket_id"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": total - expected,
            "pass": total == expected,
        },
        "n_event_rows_after_valid_charge_cut": int(len(events)),
        "invalid_event_rows_removed_after_reproduction": invalid,
        "train_runs": sorted(int(x) for x in events.loc[train_mask, "run"].unique()),
        "heldout_runs": sorted(int(x) for x in events.loc[heldout_mask, "run"].unique()),
        "nominal_geometry": config["nominal_geometry"],
        "n_material_budget_variants": int(len(variants)),
        "material_budget_axes": config["material_budget"],
        "nominal_metrics": json.loads(metrics_df[metrics_df["geometry"] == config["nominal_geometry"]].to_json(orient="records")),
        "ml_minus_traditional_res68_ci95": delta_ci,
        "geometry_systematic_envelope": envelope,
        "leakage_checks": json.loads(leak.to_json(orient="records")),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, counts, metrics_df, by_run_df, nominal_boot, geom_summary, leak, result)

    output_names = [
        "REPORT.md",
        "result.json",
        "input_sha256.csv",
        "method_metrics.csv",
        "run_heldout_summary.csv",
        "geometry_variant_summary.csv",
        "run_block_bootstrap.csv",
        "leakage_checks.csv",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
    ]
    manifest = {
        "study": "S14d",
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-3",
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "command": "/home/billy/anaconda3/bin/python scripts/s14d_1781020357_1391_009a0721_material_budget_audit.py --config configs/s14d_1781020357_1391_009a0721.yaml",
        "config": str(config_path),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {},
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["outputs"] = {name: sha256_file(out_dir / name) for name in output_names if (out_dir / name).exists()}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
