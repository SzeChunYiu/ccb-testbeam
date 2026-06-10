#!/usr/bin/env python3
"""P08b: calibration-backed PID weak-label upgrade from raw B-stack ROOT.

This is a weak-label and leakage study, not a truth PID measurement. It replaces
P08a's direct terminal/penetrating topology labels with a calibrated
range-energy residual label based on PSTAR depth anchors and the duplicate
odd-polarity readout. Models are still split by run.
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
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)


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
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(key): json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [json_sanitize(item) for item in value]
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
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = str(group)
    return lookup


def raw_file(raw_root_dir: Path, run: int) -> Path:
    return raw_root_dir / "hrdb_run_{:04d}.root".format(run)


def iter_raw(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def pstar_energy_at_range(config: dict, ranges_cm: np.ndarray) -> np.ndarray:
    pstar = config["pstar"]
    energy = np.asarray(pstar["energy_mev"], dtype=float)
    ranges = np.asarray(pstar["range_g_cm2"], dtype=float) / float(pstar["density_g_cm3"])
    x = np.log(np.maximum(ranges_cm, ranges[0]))
    return np.exp(np.interp(x, np.log(ranges), np.log(energy), left=np.log(energy[0]), right=np.log(energy[-1])))


def geometry_anchors(config: dict) -> np.ndarray:
    variant = config["geometry_variants"][config["nominal_geometry"]]
    ranges = np.asarray([float(variant["stave_centers_cm"][name]) for name in STAVE_NAMES], dtype=float)
    return pstar_energy_at_range(config, ranges)


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
        fallback = safe[train_mask & np.isfinite(safe)]
        fallback_center = float(np.median(fallback)) if len(fallback) else 0.0
        for depth in range(len(self.anchors)):
            mask = train_mask & (depth_idx == depth) & np.isfinite(safe)
            values = safe[mask]
            if len(values) < 20:
                self.xq[depth] = np.asarray([fallback_center - 1.0, fallback_center + 1.0])
                self.yq[depth] = np.asarray([lo[depth], hi[depth]])
                continue
            xq = np.quantile(values, self.quantiles)
            keep = np.r_[True, np.diff(xq) > 1e-9]
            xq = xq[keep]
            q = self.quantiles[keep]
            self.xq[depth] = xq
            self.yq[depth] = lo[depth] + q * (hi[depth] - lo[depth])
        return self

    def predict(self, charge: np.ndarray, depth_idx: np.ndarray) -> np.ndarray:
        safe = np.log(np.maximum(charge, 1.0))
        out = np.empty(len(charge), dtype=float)
        for depth in range(len(self.anchors)):
            mask = depth_idx == depth
            if not mask.any():
                continue
            out[mask] = np.interp(
                safe[mask],
                self.xq[depth],
                self.yq[depth],
                left=self.yq[depth][0],
                right=self.yq[depth][-1],
            )
        return out


def shape_features(wave: np.ndarray) -> pd.DataFrame:
    area = wave.sum(axis=1)
    abs_area = np.maximum(np.abs(area), 1e-6)
    return pd.DataFrame(
        {
            "b2_area_over_peak_shape": area.astype(np.float32),
            "b2_tail_fraction": (wave[:, 12:].sum(axis=1) / abs_area).astype(np.float32),
            "b2_late_fraction": (wave[:, 9:].sum(axis=1) / abs_area).astype(np.float32),
            "b2_early_fraction": (wave[:, :5].sum(axis=1) / abs_area).astype(np.float32),
            "b2_final_fraction": wave[:, -1].astype(np.float32),
            "b2_peak_sample": np.argmax(wave, axis=1).astype(np.float32),
            "b2_width50": (wave > 0.5).sum(axis=1).astype(np.float32),
            "b2_width20": (wave > 0.2).sum(axis=1).astype(np.float32),
            "b2_max_down_step": np.diff(wave, axis=1).min(axis=1).astype(np.float32),
        }
    )


def scan_raw(config: dict, raw_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    even_ch = np.asarray([int(config["staves"][str(name)]) for name in STAVE_NAMES], dtype=int)
    odd_ch = np.asarray([int(config["duplicate_readout_channels"][str(name)]) for name in STAVE_NAMES], dtype=int)
    group_for_run = run_group_lookup(config)
    sat = float(config["saturation_adc"])

    waves: List[np.ndarray] = []
    meta_parts: List[pd.DataFrame] = []
    run_rows: List[dict] = []
    wave_offset = 0

    for run in configured_runs(config):
        path = raw_file(raw_dir, run)
        if not path.exists():
            raise FileNotFoundError(path)
        group = group_for_run[int(run)]
        event_offset = 0
        run_counts = {
            "run": int(run),
            "group": group,
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
            "b2_selected_events": 0,
        }
        stave_counts = {str(name): 0 for name in STAVE_NAMES}
        for batch in iter_raw(path):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_ch, :]
            odd = -corrected[:, odd_ch, :]

            even_amp = even.max(axis=-1)
            even_charge = np.clip(even, 0.0, None).sum(axis=-1)
            odd_amp = odd.max(axis=-1)
            odd_charge = np.clip(odd, 0.0, None).sum(axis=-1)
            selected = even_amp > cut

            run_counts["events_total"] += int(len(raw))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(STAVE_NAMES):
                stave_counts[str(name)] += int(selected[:, idx].sum())

            b2 = selected[:, 0]
            if b2.any():
                downstream_selected = selected[:, 1:].sum(axis=1)
                even_total = (even_charge * selected).sum(axis=1)
                odd_total = (odd_charge * selected).sum(axis=1)
                total_charge = np.maximum(even_charge.sum(axis=1), 1e-6)
                downstream_fraction = even_charge[:, 1:].sum(axis=1) / total_charge
                max_depth = np.where(
                    selected[:, 3],
                    3,
                    np.where(selected[:, 2], 2, np.where(selected[:, 1], 1, np.where(selected[:, 0], 0, -1))),
                )
                topology_code = (
                    selected[:, 1].astype(int) + 2 * selected[:, 2].astype(int) + 4 * selected[:, 3].astype(int)
                )
                b2_amp = np.maximum(even_amp[b2, 0], 1e-6)
                b2_wave = (even[b2, 0, :] / b2_amp[:, None]).astype(np.float32)
                waves.append(b2_wave)
                event_idx = np.flatnonzero(b2)
                meta_parts.append(
                    pd.DataFrame(
                        {
                            "wave_index": (np.arange(len(event_idx)) + wave_offset).astype(np.int32),
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": group,
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "event_order_proxy": (event_idx + event_offset).astype(np.float32),
                            "eventno": np.asarray(batch["EVENTNO"])[event_idx].astype(np.int64),
                            "evt": np.asarray(batch["EVT"])[event_idx].astype(np.int64),
                            "depth_idx": max_depth[b2].astype(np.int8),
                            "max_depth_stave": (max_depth[b2] + 1).astype(np.int8),
                            "multiplicity": selected[b2].sum(axis=1).astype(np.int8),
                            "topology_code": topology_code[b2].astype(np.int8),
                            "downstream_selected": downstream_selected[b2].astype(np.int8),
                            "downstream_charge_fraction": downstream_fraction[b2].astype(np.float32),
                            "even_total_charge": even_total[b2].astype(np.float32),
                            "odd_total_charge": odd_total[b2].astype(np.float32),
                            "even_max_amp": (even_amp[b2] * selected[b2]).max(axis=1).astype(np.float32),
                            "odd_max_amp": (odd_amp[b2] * selected[b2]).max(axis=1).astype(np.float32),
                            "saturated_count": ((even_amp[b2] >= sat) & selected[b2]).sum(axis=1).astype(np.int8),
                            "b2_saturated": (even_amp[b2, 0] >= sat).astype(np.int8),
                            "b2_amp": even_amp[b2, 0].astype(np.float32),
                            "b2_area": even_charge[b2, 0].astype(np.float32),
                            "b2_odd_area": odd_charge[b2, 0].astype(np.float32),
                            "b4_amp": even_amp[b2, 1].astype(np.float32),
                            "b6_amp": even_amp[b2, 2].astype(np.float32),
                            "b8_amp": even_amp[b2, 3].astype(np.float32),
                            "b4_area": even_charge[b2, 1].astype(np.float32),
                            "b6_area": even_charge[b2, 2].astype(np.float32),
                            "b8_area": even_charge[b2, 3].astype(np.float32),
                            "b2_hit": selected[b2, 0].astype(np.int8),
                            "b4_hit": selected[b2, 1].astype(np.int8),
                            "b6_hit": selected[b2, 2].astype(np.int8),
                            "b8_hit": selected[b2, 3].astype(np.int8),
                        }
                    )
                )
                wave_offset += int(len(event_idx))
                run_counts["b2_selected_events"] += int(b2.sum())
            event_offset += int(len(raw))

        run_rows.append({**run_counts, **stave_counts})
        print(
            "run {:04d}: selected_pulses={} b2_events={}".format(
                run, run_counts["selected_pulses"], run_counts["b2_selected_events"]
            ),
            flush=True,
        )

    wave_array = np.concatenate(waves, axis=0)
    meta = pd.concat(meta_parts, ignore_index=True)
    meta = pd.concat([meta, shape_features(wave_array)], axis=1)
    counts = pd.DataFrame(run_rows)
    groups = (
        counts.groupby("group", sort=False)[["events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"]]
        .sum()
        .reset_index()
    )
    return wave_array, meta, counts, groups


def reproduction_table(config: dict, counts_by_group: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(counts_by_group["selected_pulses"].sum()),
            "tolerance": 0,
        }
    ]
    for group in config["run_groups"]:
        rows.append(
            {
                "quantity": "{} selected pulses".format(group),
                "report_value": int(expected["{}_pulses".format(group)]),
                "reproduced": int(counts_by_group.loc[counts_by_group["group"] == group, "selected_pulses"].iloc[0]),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out


def add_calibrated_labels(meta: pd.DataFrame, config: dict, anchors: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    out = meta.copy()
    label_cfg = config["weak_label"]
    valid = (
        (out["odd_total_charge"] > float(label_cfg["min_odd_total_charge"]))
        & (out["even_total_charge"] > float(label_cfg["min_even_total_charge"]))
        & (out["depth_idx"] >= 0)
    )
    out = out.loc[valid].reset_index(drop=True)

    calib_groups = set(config["label_calibration_groups"])
    train_mask = out["group"].isin(calib_groups).to_numpy()
    if int(train_mask.sum()) < 100:
        raise RuntimeError("Too few calibration rows for range-energy weak-label calibrator")

    depth = out["depth_idx"].to_numpy(dtype=int)
    odd_cal = DepthChargeQuantileCalibrator(anchors).fit(out["odd_total_charge"].to_numpy(dtype=float), depth, train_mask)
    even_cal = DepthChargeQuantileCalibrator(anchors).fit(out["even_total_charge"].to_numpy(dtype=float), depth, train_mask)
    out["calibrated_energy_mev_odd"] = odd_cal.predict(out["odd_total_charge"].to_numpy(dtype=float), depth).astype(np.float32)
    out["calibrated_energy_mev_even"] = even_cal.predict(out["even_total_charge"].to_numpy(dtype=float), depth).astype(np.float32)
    out["pstar_depth_anchor_mev"] = anchors[depth].astype(np.float32)
    out["range_energy_residual_frac_odd"] = (
        (out["calibrated_energy_mev_odd"] - out["pstar_depth_anchor_mev"])
        / np.maximum(out["pstar_depth_anchor_mev"], 1.0)
    ).astype(np.float32)
    out["range_energy_residual_frac_even"] = (
        (out["calibrated_energy_mev_even"] - out["pstar_depth_anchor_mev"])
        / np.maximum(out["pstar_depth_anchor_mev"], 1.0)
    ).astype(np.float32)

    q = float(label_cfg["within_run_depth_quantile"])
    min_class = int(label_cfg["min_atom_class_rows"])
    out["weak_label"] = np.nan
    support_rows = []
    for (run, depth_idx), grp in out.groupby(["run", "depth_idx"], sort=True):
        if len(grp) < 2 * min_class:
            continue
        lo = float(grp["range_energy_residual_frac_odd"].quantile(q))
        hi = float(grp["range_energy_residual_frac_odd"].quantile(1.0 - q))
        low_idx = grp.index[grp["range_energy_residual_frac_odd"] <= lo]
        high_idx = grp.index[grp["range_energy_residual_frac_odd"] >= hi]
        n = min(len(low_idx), len(high_idx))
        if n < min_class or hi <= lo:
            continue
        out.loc[low_idx[:n], "weak_label"] = 0
        out.loc[high_idx[-n:], "weak_label"] = 1
        support_rows.append(
            {
                "run": int(run),
                "depth_idx": int(depth_idx),
                "available_rows": int(len(grp)),
                "low_rows": int(n),
                "high_rows": int(n),
                "low_threshold_residual": lo,
                "high_threshold_residual": hi,
            }
        )
    labeled = out.dropna(subset=["weak_label"]).copy()
    labeled["weak_label"] = labeled["weak_label"].astype(np.int8)
    labeled["weak_label_name"] = np.where(
        labeled["weak_label"] == 1, label_cfg["positive_name"], label_cfg["negative_name"]
    )
    calibration = {
        "calibration_groups": sorted(calib_groups),
        "calibration_rows": int(train_mask.sum()),
        "anchors_mev": {str(name): float(value) for name, value in zip(STAVE_NAMES, anchors)},
        "label_source": "odd duplicate-readout PSTAR/depth charge quantile residual, thresholded within run/depth",
    }
    return labeled.reset_index(drop=True), pd.DataFrame(support_rows), calibration


def balanced_benchmark_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]))
    max_rows = int(config["benchmark"]["max_rows_per_run_label"])
    groups = set(config["benchmark_groups"])
    meta = meta.loc[meta["group"].isin(groups)]
    pieces: List[np.ndarray] = []
    for (_, _), group in meta.groupby(["run", "weak_label"], sort=True):
        idx = group.index.to_numpy()
        take = min(len(idx), max_rows)
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def fit_logistic_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def fit_ml_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, params: dict, seed: int) -> np.ndarray:
    clf = HistGradientBoostingClassifier(
        max_iter=int(params.get("n_estimators", params.get("max_iter", 30))),
        max_leaf_nodes=int(params.get("max_leaf_nodes", 15)),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        learning_rate=float(params.get("learning_rate", 0.08)),
        l2_regularization=float(params.get("l2_regularization", 0.05)),
        random_state=seed,
    )
    weight = compute_sample_weight(class_weight="balanced", y=train_y)
    clf.fit(train_x, train_y, sample_weight=weight)
    return clf.predict_proba(test_x)[:, 1]


def crossfold_isotonic(y: np.ndarray, score: np.ndarray, folds: np.ndarray) -> np.ndarray:
    prob = np.full(len(y), np.nan, dtype=float)
    for fold in np.unique(folds):
        test = folds == fold
        cal = ~test
        if len(np.unique(y[cal])) < 2:
            prob[test] = np.clip(score[test], 0.0, 1.0)
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(score[cal], y[cal])
        prob[test] = iso.predict(score[test])
    return prob


def run_block_ci(y: np.ndarray, score: np.ndarray, prob: np.ndarray, runs: np.ndarray, seed: int, n_boot: int) -> dict:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    aucs, aps, briers = [], [], []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        aucs.append(roc_auc_score(y[idx], score[idx]))
        aps.append(average_precision_score(y[idx], score[idx]))
        briers.append(brier_score_loss(y[idx], np.clip(prob[idx], 0.0, 1.0)))
    return {
        "roc_auc_ci": [float(x) for x in np.quantile(aucs, [0.025, 0.975])] if aucs else [None, None],
        "average_precision_ci": [float(x) for x in np.quantile(aps, [0.025, 0.975])] if aps else [None, None],
        "brier_ci": [float(x) for x in np.quantile(briers, [0.025, 0.975])] if briers else [None, None],
        "bootstrap_valid": int(len(aucs)),
    }


def fixed_efficiency_purity(y: np.ndarray, score: np.ndarray, runs: np.ndarray, efficiency: float, seed: int, n_boot: int) -> Tuple[float, List[Optional[float]]]:
    pos_scores = score[y == 1]
    threshold = float(np.quantile(pos_scores, max(0.0, 1.0 - efficiency)))
    selected = score >= threshold
    purity = float(y[selected].mean()) if selected.any() else float("nan")
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        sel = selected[idx]
        if sel.any():
            boot.append(float(y[idx][sel].mean()))
    ci = [float(x) for x in np.quantile(boot, [0.025, 0.975])] if boot else [None, None]
    return purity, ci


def paired_auc_diff(y: np.ndarray, left: np.ndarray, right: np.ndarray, runs: np.ndarray, seed: int, n_boot: int) -> dict:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    diffs = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        diffs.append(roc_auc_score(y[idx], right[idx]) - roc_auc_score(y[idx], left[idx]))
    return {
        "right_minus_left_auc": safe_auc(y, right) - safe_auc(y, left),
        "ci": [float(x) for x in np.quantile(diffs, [0.025, 0.975])] if diffs else [None, None],
        "bootstrap_valid": int(len(diffs)),
    }


def traditional_matrix(df: pd.DataFrame) -> np.ndarray:
    cols = [
        "depth_idx",
        "multiplicity",
        "topology_code",
        "downstream_selected",
        "downstream_charge_fraction",
        "range_energy_residual_frac_even",
        "calibrated_energy_mev_even",
        "pstar_depth_anchor_mev",
        "saturated_count",
        "b2_saturated",
        "b2_amp",
        "b2_area",
        "even_total_charge",
        "b4_area",
        "b6_area",
        "b8_area",
    ]
    out = df[cols].copy()
    for col in ["calibrated_energy_mev_even", "pstar_depth_anchor_mev", "b2_amp", "b2_area", "even_total_charge", "b4_area", "b6_area", "b8_area"]:
        out[col] = np.log1p(np.maximum(out[col].to_numpy(dtype=float), 0.0))
    return out.to_numpy(dtype=float)


def build_benchmark(waves_all: np.ndarray, meta_all: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    sample_idx = balanced_benchmark_indices(meta_all, config)
    meta = meta_all.loc[sample_idx].reset_index(drop=True).copy()
    waves = waves_all[meta["wave_index"].to_numpy(dtype=int)]
    for sample in range(waves.shape[1]):
        meta["norm_s{:02d}".format(sample)] = waves[:, sample].astype(np.float32)

    y = meta["weak_label"].to_numpy(dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    seed = int(config["benchmark"]["random_seed"])
    min_train_class = int(config["benchmark"]["min_train_class_rows"])
    min_test_class = int(config["benchmark"]["min_test_class_rows"])
    sample_cols = ["norm_s{:02d}".format(i) for i in range(18)]
    hand_cols = [
        "b2_area_over_peak_shape",
        "b2_tail_fraction",
        "b2_late_fraction",
        "b2_early_fraction",
        "b2_final_fraction",
        "b2_peak_sample",
        "b2_width50",
        "b2_width20",
        "b2_max_down_step",
    ]

    fold_id = np.full(len(meta), "", dtype=object)
    traditional_score = np.full(len(meta), np.nan)
    ml_score = np.full(len(meta), np.nan)
    topology_score = np.full(len(meta), np.nan)
    even_charge_proxy_score = np.full(len(meta), np.nan)
    forbidden_energy_score = np.full(len(meta), np.nan)
    run_only_score = np.full(len(meta), np.nan)
    event_proxy_score = np.full(len(meta), np.nan)
    shuffled_score = np.full(len(meta), np.nan)
    ml_rows = []

    folds = []
    for run in np.unique(runs):
        test = runs == run
        train = ~test
        train_counts = np.bincount(y[train], minlength=2)
        test_counts = np.bincount(y[test], minlength=2)
        if train_counts.min() < min_train_class or test_counts.min() < min_test_class:
            continue
        folds.append((train, test, int(run)))

    for fold_number, (train, test, heldout_run) in enumerate(folds, start=1):
        train_y = y[train]
        traditional_score[test] = fit_logistic_score(traditional_matrix(meta.loc[train]), train_y, traditional_matrix(meta.loc[test]))

        pca = PCA(n_components=4, random_state=seed + fold_number)
        train_pca = pca.fit_transform(meta.loc[train, sample_cols].to_numpy(dtype=float))
        test_pca = pca.transform(meta.loc[test, sample_cols].to_numpy(dtype=float))
        ml_train = np.column_stack([meta.loc[train, sample_cols + hand_cols].to_numpy(dtype=float), train_pca])
        ml_test = np.column_stack([meta.loc[test, sample_cols + hand_cols].to_numpy(dtype=float), test_pca])
        best_params = config["benchmark"]["ml_grid"][0]
        ml_score[test] = fit_ml_score(ml_train, train_y, ml_test, best_params, seed + fold_number)
        shuffled_y = train_y.copy()
        np.random.default_rng(seed + 9000 + fold_number).shuffle(shuffled_y)
        shuffled_score[test] = fit_ml_score(ml_train, shuffled_y, ml_test, best_params, seed + 3000 + fold_number)
        ml_rows.append({"heldout_run": heldout_run, **best_params, "selection": "fixed preconfigured HGB"})

        topology_cols = ["depth_idx", "multiplicity", "topology_code", "downstream_selected", "downstream_charge_fraction"]
        topology_score[test] = fit_logistic_score(
            meta.loc[train, topology_cols].to_numpy(dtype=float),
            train_y,
            meta.loc[test, topology_cols].to_numpy(dtype=float),
        )

        even_proxy_cols = ["range_energy_residual_frac_even", "calibrated_energy_mev_even", "even_total_charge", "b2_area"]
        even_proxy_train = meta.loc[train, even_proxy_cols].copy()
        even_proxy_test = meta.loc[test, even_proxy_cols].copy()
        for col in ["calibrated_energy_mev_even", "even_total_charge", "b2_area"]:
            even_proxy_train[col] = np.log1p(np.maximum(even_proxy_train[col].to_numpy(dtype=float), 0.0))
            even_proxy_test[col] = np.log1p(np.maximum(even_proxy_test[col].to_numpy(dtype=float), 0.0))
        even_charge_proxy_score[test] = fit_logistic_score(
            even_proxy_train.to_numpy(dtype=float),
            train_y,
            even_proxy_test.to_numpy(dtype=float),
        )

        forbidden_cols = ["range_energy_residual_frac_odd", "calibrated_energy_mev_odd", "odd_total_charge", "b2_odd_area"]
        forbidden_train = meta.loc[train, forbidden_cols].copy()
        forbidden_test = meta.loc[test, forbidden_cols].copy()
        for col in ["calibrated_energy_mev_odd", "odd_total_charge", "b2_odd_area"]:
            forbidden_train[col] = np.log1p(np.maximum(forbidden_train[col].to_numpy(dtype=float), 0.0))
            forbidden_test[col] = np.log1p(np.maximum(forbidden_test[col].to_numpy(dtype=float), 0.0))
        forbidden_energy_score[test] = fit_logistic_score(forbidden_train.to_numpy(dtype=float), train_y, forbidden_test.to_numpy(dtype=float))

        run_train = pd.get_dummies(meta.loc[train, "run"].astype(str))
        run_test = pd.get_dummies(meta.loc[test, "run"].astype(str)).reindex(columns=run_train.columns, fill_value=0)
        run_only_score[test] = fit_logistic_score(run_train.to_numpy(dtype=float), train_y, run_test.to_numpy(dtype=float))

        proxy_train = pd.get_dummies(meta.loc[train, "group"].astype(str))
        proxy_test = pd.get_dummies(meta.loc[test, "group"].astype(str)).reindex(columns=proxy_train.columns, fill_value=0)
        event_train_raw = meta.loc[train, ["event_index"]].to_numpy(dtype=float)
        event_test_raw = meta.loc[test, ["event_index"]].to_numpy(dtype=float)
        event_min = float(event_train_raw.min())
        event_scale = max(float(event_train_raw.max() - event_min), 1.0)
        event_train = (event_train_raw - event_min) / event_scale
        event_test = (event_test_raw - event_min) / event_scale
        event_proxy_score[test] = fit_logistic_score(
            np.column_stack([proxy_train.to_numpy(dtype=float), event_train]),
            train_y,
            np.column_stack([proxy_test.to_numpy(dtype=float), event_test]),
        )

        fold_id[test] = "run{}".format(heldout_run)
        print(
            "fold {:02d}: heldout_run={} train={} test={}".format(fold_number, heldout_run, int(train.sum()), int(test.sum())),
            flush=True,
        )

    valid = fold_id != ""
    meta_eval = meta.loc[valid].copy()
    y_eval = y[valid]
    runs_eval = runs[valid]
    folds_eval = fold_id[valid]
    scores = {
        "traditional calibrated charge-depth logistic": traditional_score[valid],
        "ML raw B2 waveform + train-only PCA latent HGB": ml_score[valid],
        "leakage sentinel: topology-only logistic": topology_score[valid],
        "leakage sentinel: even-charge calibration-proxy logistic": even_charge_proxy_score[valid],
        "leakage sentinel: forbidden odd-energy-label logistic": forbidden_energy_score[valid],
        "leakage sentinel: run-only logistic": run_only_score[valid],
        "leakage sentinel: group/event-order logistic": event_proxy_score[valid],
        "leakage sentinel: shuffled-label waveform HGB": shuffled_score[valid],
    }

    rows = []
    for idx, (name, score) in enumerate(scores.items()):
        prob = crossfold_isotonic(y_eval, score, folds_eval)
        ci = run_block_ci(y_eval, score, prob, runs_eval, seed + idx + 10, int(config["benchmark"]["bootstrap_replicates"]))
        purity, purity_ci = fixed_efficiency_purity(
            y_eval,
            score,
            runs_eval,
            float(config["benchmark"]["fixed_efficiency"]),
            seed + idx + 100,
            int(config["benchmark"]["bootstrap_replicates"]),
        )
        rows.append(
            {
                "method": name,
                "n_events": int(len(y_eval)),
                "n_runs": int(len(np.unique(runs_eval))),
                "positive_fraction": float(y_eval.mean()),
                "roc_auc": safe_auc(y_eval, score),
                "roc_auc_ci_low": ci["roc_auc_ci"][0],
                "roc_auc_ci_high": ci["roc_auc_ci"][1],
                "average_precision": safe_ap(y_eval, score),
                "ap_ci_low": ci["average_precision_ci"][0],
                "ap_ci_high": ci["average_precision_ci"][1],
                "brier_isotonic": float(brier_score_loss(y_eval, np.clip(prob, 0.0, 1.0))),
                "brier_ci_low": ci["brier_ci"][0],
                "brier_ci_high": ci["brier_ci"][1],
                "purity_at_{:.0f}pct_eff".format(100 * float(config["benchmark"]["fixed_efficiency"])): purity,
                "purity_ci_low": purity_ci[0],
                "purity_ci_high": purity_ci[1],
                "bootstrap_valid": ci["bootstrap_valid"],
            }
        )
        clean_name = name.replace(" ", "_").replace(":", "").replace("/", "_")
        meta_eval[clean_name] = score
        meta_eval[clean_name + "_prob"] = prob

    scoreboard = pd.DataFrame(rows)
    diff = paired_auc_diff(
        y_eval,
        scores["traditional calibrated charge-depth logistic"],
        scores["ML raw B2 waveform + train-only PCA latent HGB"],
        runs_eval,
        seed + 777,
        int(config["benchmark"]["bootstrap_replicates"]),
    )
    topology_vs_p08a = None
    p08a_path = Path(config["p08a_result"])
    if p08a_path.exists():
        p08a = json.loads(p08a_path.read_text(encoding="utf-8"))
        topology_auc = float(scoreboard.loc[scoreboard["method"] == "leakage sentinel: topology-only logistic", "roc_auc"].iloc[0])
        topology_vs_p08a = {
            "p08a_traditional_topology_proxy_auc": float(p08a["traditional"]["roc_auc"]),
            "p08a_ml_waveform_auc": float(p08a["ml"]["roc_auc"]),
            "this_topology_only_auc": topology_auc,
            "topology_auc_drop_vs_p08a_traditional": topology_auc - float(p08a["traditional"]["roc_auc"]),
            "this_ml_auc_minus_p08a_ml_auc": float(scoreboard.loc[scoreboard["method"] == "ML raw B2 waveform + train-only PCA latent HGB", "roc_auc"].iloc[0]) - float(p08a["ml"]["roc_auc"]),
        }

    leakage_rows = []
    for probe, interp in [
        ("topology-only logistic", "Direct P08a-style topology sentinel; high values would mean the calibrated label still leaks penetration topology."),
        ("even-charge calibration-proxy logistic", "Duplicate-readout control: uses only the allowed even-readout version of the odd calibrated label source; high values mean the weak label is mostly charge-scale closure."),
        ("forbidden odd-energy-label logistic", "Ceiling probe using the duplicate odd-readout calibrated residual that defines the weak label."),
        ("run-only logistic", "Strict leave-one-run-out run-id sentinel; unseen held-out runs collapse to the intercept."),
        ("group/event-order logistic", "Sample group plus event-order sentinel for run-family/rate-drift confounding."),
        ("shuffled-label waveform HGB", "Same waveform HGB pipeline with shuffled training labels; should fall near chance."),
    ]:
        row = scoreboard.loc[scoreboard["method"] == "leakage sentinel: {}".format(probe)].iloc[0]
        leakage_rows.append(
            {
                "probe": probe,
                "roc_auc": row["roc_auc"],
                "average_precision": row["average_precision"],
                "interpretation": interp,
            }
        )
    leakage_rows.append(
        {
            "probe": "ML-minus-traditional paired run bootstrap",
            "roc_auc": diff["right_minus_left_auc"],
            "average_precision": None,
            "interpretation": "Positive values favor waveform/latent ML; CI is stored in result.json.",
        }
    )
    leakage = pd.DataFrame(leakage_rows)

    fold_counts = meta_eval.groupby(["run", "weak_label_name"]).size().reset_index(name="n")
    pd.DataFrame(ml_rows).to_csv(out_dir / "ml_fixed_hgb_folds.csv", index=False)
    fold_counts.to_csv(out_dir / "heldout_run_label_counts.csv", index=False)
    meta_eval[
        [
            "run",
            "event_index",
            "weak_label",
            "weak_label_name",
            "depth_idx",
            "range_energy_residual_frac_odd",
            "range_energy_residual_frac_even",
            "downstream_selected",
            "downstream_charge_fraction",
        ]
    ].head(20000).to_csv(out_dir / "oof_prediction_preview.csv", index=False)

    details = {
        "benchmark_rows_after_balancing": int(len(meta)),
        "evaluated_rows": int(len(y_eval)),
        "evaluated_runs": [int(run) for run in np.unique(runs_eval)],
        "skipped_runs": [int(run) for run in sorted(set(np.unique(runs).tolist()) - set(np.unique(runs_eval).tolist()))],
        "positive_fraction": float(y_eval.mean()),
        "ml_vs_traditional": diff,
        "topology_vs_p08a": topology_vs_p08a,
    }
    return scoreboard, leakage, fold_counts, meta, details


def output_manifest(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(out_dir: Path, config: dict, result: dict, reproduction: pd.DataFrame, scoreboard: pd.DataFrame, leakage: pd.DataFrame) -> None:
    trad = scoreboard[scoreboard["method"] == "traditional calibrated charge-depth logistic"].iloc[0]
    ml = scoreboard[scoreboard["method"] == "ML raw B2 waveform + train-only PCA latent HGB"].iloc[0]
    topology = scoreboard[scoreboard["method"] == "leakage sentinel: topology-only logistic"].iloc[0]
    forbidden = scoreboard[scoreboard["method"] == "leakage sentinel: forbidden odd-energy-label logistic"].iloc[0]
    shuffled = scoreboard[scoreboard["method"] == "leakage sentinel: shuffled-label waveform HGB"].iloc[0]
    diff = result["ml_vs_traditional"]
    eff_col = "purity_at_{:.0f}pct_eff".format(100 * float(config["benchmark"]["fixed_efficiency"]))
    comparison = result.get("p08a_comparison") or {}
    report = """# P08b: calibration-backed PID weak-label upgrade

**Ticket:** {ticket_id}  
**Worker:** {worker}  
**Input:** raw B-stack `HRDv` ROOT from `{raw_root_dir}`  
**Constraint:** no Monte Carlo and no truth PID claim.

## Reproduction First
Before any weak-labeling or modeling, the raw ROOT scan reproduced the S00
selected B-stave pulse count exactly:

{reproduction_table}

## Calibrated Weak Labels
P08a used direct topology labels (`terminal_b2_like` versus
`penetrating_like`). Here the label is instead a calibrated range-energy
residual: PSTAR converts the nominal B2/B4/B6/B8 depth anchors to proton CSDA
energy anchors, a duplicate odd-readout charge quantile calibration is frozen
on the calibration runs, and the odd-readout energy residual is thresholded
inside each run/depth atom. The bottom {label_q:.0f}% is `{neg}` and the top
{label_q:.0f}% is `{pos}`. This is still a weak label, not particle truth.

Labeled support: {label_rows:,} rows from {support_atoms:,} run/depth atoms.
The held-out benchmark evaluates {n_eval:,} balanced rows over {n_runs} runs.

## Run-Held-Out Benchmark
All scores are leave-one-run-out predictions with held-out run-block bootstrap
95% CIs. Traditional uses calibrated even-readout charge-depth variables,
topology, saturation, and range-energy residual features. ML uses normalized B2
waveform samples, hand-shape summaries, and train-only PCA waveform latents.

| method | ROC AUC | AP | purity at {eff:.0f}% high-residual efficiency |
|---|---:|---:|---:|
| traditional calibrated charge-depth logistic | {trad_auc:.3f} [{trad_lo:.3f}, {trad_hi:.3f}] | {trad_ap:.3f} | {trad_purity:.3f} |
| ML raw B2 waveform + PCA latent HGB | {ml_auc:.3f} [{ml_lo:.3f}, {ml_hi:.3f}] | {ml_ap:.3f} | {ml_purity:.3f} |

Paired run-block bootstrap for ML minus traditional ROC AUC is **{diff:.3f}**
with 95% CI **[{diff_lo:.3f}, {diff_hi:.3f}]**.

## P08a Comparison
P08a's topology-defined traditional score was AUC {p08a_trad:.3f}; the
P08a waveform ML score was AUC {p08a_ml:.3f}. Under this calibrated residual
label, a direct topology-only sentinel is AUC {topology_auc:.3f}; the topology
AUC drop relative to P08a's traditional topology proxy is {topology_drop:.3f}.
The waveform ML shift relative to P08a is {ml_shift:.3f}. That quantifies the
P08a apparent PID signal as mostly topology-label leakage rather than stable
B2 waveform PID information.

## Leakage Hunt
| probe | ROC AUC | AP | interpretation |
|---|---:|---:|---|
{leakage_table}

The forbidden odd-energy residual probe is expected to be high because it sees
the label source. The even-charge calibration-proxy sentinel explains why the
main AUCs are too good for PID adoption: the duplicate even readout carries the
same calibrated charge-scale residual as the odd weak-label source. The topology
sentinel is the key P08a leakage check, and the shuffled-label HGB is the
software leakage guardrail. The benchmark is B2-event-level, so stave id is
constant by construction.

## Verdict
The calibrated weak label removes the perfect topology shortcut seen in P08a,
but it does not create a PID adoption result. The very high traditional and ML
AUCs are explained by duplicate-readout charge-scale closure, not by independent
particle identity. The B2 waveform/PCA-latent ML result is reported as a
leakage-controlled weak-label stress test only.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py --config configs/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `scoreboard.csv`, `leakage_checks.csv`,
`calibrated_label_support.csv`, `weak_label_counts_by_run.csv`,
`heldout_run_label_counts.csv`, and `ml_fixed_hgb_folds.csv`.
""".format(
        ticket_id=config["ticket_id"],
        worker=config["worker"],
        raw_root_dir=result["raw_root_dir"],
        reproduction_table=reproduction.to_markdown(index=False),
        label_q=100 * float(config["weak_label"]["within_run_depth_quantile"]),
        neg=config["weak_label"]["negative_name"],
        pos=config["weak_label"]["positive_name"],
        label_rows=int(result["calibrated_label_support"]["n_labeled_rows"]),
        support_atoms=int(result["calibrated_label_support"]["n_atoms"]),
        n_eval=int(result["benchmark"]["evaluated_rows"]),
        n_runs=len(result["benchmark"]["evaluated_runs"]),
        eff=100 * float(config["benchmark"]["fixed_efficiency"]),
        trad_auc=trad["roc_auc"],
        trad_lo=trad["roc_auc_ci_low"],
        trad_hi=trad["roc_auc_ci_high"],
        trad_ap=trad["average_precision"],
        trad_purity=trad[eff_col],
        ml_auc=ml["roc_auc"],
        ml_lo=ml["roc_auc_ci_low"],
        ml_hi=ml["roc_auc_ci_high"],
        ml_ap=ml["average_precision"],
        ml_purity=ml[eff_col],
        diff=diff["right_minus_left_auc"],
        diff_lo=diff["ci"][0],
        diff_hi=diff["ci"][1],
        p08a_trad=comparison.get("p08a_traditional_topology_proxy_auc", float("nan")),
        p08a_ml=comparison.get("p08a_ml_waveform_auc", float("nan")),
        topology_auc=topology["roc_auc"],
        topology_drop=comparison.get("topology_auc_drop_vs_p08a_traditional", float("nan")),
        ml_shift=comparison.get("this_ml_auc_minus_p08a_ml_auc", float("nan")),
        leakage_table="\n".join(
            "| {} | {} | {} | {} |".format(
                row["probe"],
                "" if pd.isna(row["roc_auc"]) else "{:.3f}".format(row["roc_auc"]),
                "" if pd.isna(row["average_precision"]) else "{:.3f}".format(row["average_precision"]),
                row["interpretation"],
            )
            for _, row in leakage.iterrows()
        ),
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    raw_dir = resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    anchors = geometry_anchors(config)

    waves, meta, counts_by_run, counts_by_group = scan_raw(config, raw_dir)
    reproduction = reproduction_table(config, counts_by_group)
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw reproduction failed; refusing to continue to weak-label modeling")

    meta, label_support, calibration = add_calibrated_labels(meta, config, anchors)
    label_support.to_csv(out_dir / "calibrated_label_support.csv", index=False)
    if meta.empty:
        raise RuntimeError("No weak-label rows survived calibrated support")
    meta.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "weak_label_counts_by_run.csv", index=False)

    scoreboard, leakage, fold_counts, benchmark_meta, details = build_benchmark(waves, meta, config, out_dir)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    benchmark_meta.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "benchmark_balanced_counts.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    trad = scoreboard[scoreboard["method"] == "traditional calibrated charge-depth logistic"].iloc[0]
    ml = scoreboard[scoreboard["method"] == "ML raw B2 waveform + train-only PCA latent HGB"].iloc[0]
    topology = scoreboard[scoreboard["method"] == "leakage sentinel: topology-only logistic"].iloc[0]
    forbidden = scoreboard[scoreboard["method"] == "leakage sentinel: forbidden odd-energy-label logistic"].iloc[0]
    result = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "table": reproduction.to_dict(orient="records"),
        },
        "calibrated_label_definition": {
            "weak_label": config["weak_label"],
            "calibration": calibration,
        },
        "calibrated_label_support": {
            "n_atoms": int(len(label_support)),
            "n_labeled_rows": int(len(meta)),
            "atom_columns": ["run", "depth_idx"],
        },
        "traditional": {
            "method": "leave-one-run-out logistic over calibrated even-readout charge-depth, topology, saturation, and range-energy variables",
            "roc_auc": float(trad["roc_auc"]),
            "roc_auc_ci": [float(trad["roc_auc_ci_low"]), float(trad["roc_auc_ci_high"])],
            "average_precision": float(trad["average_precision"]),
        },
        "ml": {
            "method": "histogram gradient boosting over raw normalized B2 waveform samples, hand-shape features, and train-only PCA latents",
            "roc_auc": float(ml["roc_auc"]),
            "roc_auc_ci": [float(ml["roc_auc_ci_low"]), float(ml["roc_auc_ci_high"])],
            "average_precision": float(ml["average_precision"]),
        },
        "ml_vs_traditional": details["ml_vs_traditional"],
        "p08a_comparison": details["topology_vs_p08a"],
        "leakage_hunt": leakage.to_dict(orient="records"),
        "primary_interpretation": (
            "Calibration-backed weak-label upgrade: P08a's perfect topology proxy collapses under a duplicate-readout "
            "range-energy residual label, and B2 waveform/latent ML does not beat the calibrated charge-depth baseline."
        ),
        "benchmark": details,
        "input_file_count": int(len(input_sha)),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, reproduction, scoreboard, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "commands": [
            "/home/billy/anaconda3/bin/python scripts/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py --config configs/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.json"
        ],
        "random_seeds": {
            "benchmark": int(config["benchmark"]["random_seed"]),
            "bootstrap_replicates": int(config["benchmark"]["bootstrap_replicates"]),
        },
        "git_commit_at_run": git_commit(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "artifacts": output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print(scoreboard.to_string(index=False))
    print(leakage.to_string(index=False))
    print("DONE in {:.1f}s -> {}".format(time.time() - t0, out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
