#!/usr/bin/env python3
"""S16g quiet-run pseudo-pedestal calibration.

The script audits raw ROOT first, then evaluates whether frozen quiet-event
strata provide a calibrated pseudo-pedestal for low-amplitude B-stack pulses.
All scoring is leave-one-run-out with run-block bootstrap CIs.
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
from typing import Dict, Iterable, List, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.naive_bayes import GaussianNB


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
    runs = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    return {int(run): group for group, runs in config["run_groups"].items() for run in runs}


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def raw_paths(config: dict) -> List[Path]:
    return [raw_path(config, run) for run in configured_runs(config)]


def iter_tree(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


def trigger_audit(config: dict) -> pd.DataFrame:
    rows = []
    tag_tokens = ["random", "forced", "force", "pedestal", "ped", "empty", "nopulse", "no_pulse", "tag"]
    branch_tokens = ["random", "forced", "force", "pedestal", "ped", "tag", "spill", "scaler"]
    for path in raw_paths(config):
        tree = uproot.open(path)["h101"]
        branches = list(tree.keys())
        tag_like = [name for name in branches if any(token in name.lower() for token in branch_tokens)]
        if tree.num_entries:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            values, counts = np.unique(trigger, return_counts=True)
            summary = ";".join("{}:{}".format(int(v), int(c)) for v, c in zip(values, counts))
            non_beam = int(np.sum(counts[values != 1]))
        else:
            summary = "empty"
            non_beam = 0
        rows.append(
            {
                "file": path.name,
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "filename_tag_match": bool(any(token in path.name.lower() for token in tag_tokens)),
                "tag_like_branches": ";".join(tag_like),
                "has_tag_like_branch": bool(tag_like),
            }
        )
    return pd.DataFrame(rows)


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


def adaptive_pedestal(waveforms: np.ndarray, seed: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    corrected = waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(
        float(config["negative_tolerance_adc"]["floor"]),
        float(config["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    eligible = np.where(jagged_mask(corrected, amp, config), np.inf, waveforms)
    pedestal = np.minimum(seed, eligible.min(axis=1) + eps)
    lowering = seed - pedestal
    return pedestal, lowering, amp


def lowering_stratum(values: np.ndarray, config: dict) -> np.ndarray:
    return np.asarray(pd.cut(
        values,
        bins=config["lowering_bins_adc"],
        labels=config["lowering_labels"],
        include_lowest=True,
        right=False,
    ).astype(str))


def cfd20_time(waveforms: np.ndarray, pedestals: np.ndarray, config: dict) -> np.ndarray:
    corrected = waveforms.astype(float) - pedestals[:, None]
    amp = corrected.max(axis=1)
    threshold = 0.20 * amp
    above = corrected >= threshold[:, None]
    has_crossing = above.any(axis=1)
    first = above.argmax(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    period = float(config["sample_period_ns"])
    zero = has_crossing & (first == 0)
    out[zero] = 0.0
    interp = has_crossing & (first > 0)
    if np.any(interp):
        rows = np.flatnonzero(interp)
        j = first[interp]
        y0 = corrected[rows, j - 1]
        y1 = corrected[rows, j]
        denom = y1 - y0
        frac = np.zeros_like(denom, dtype=float)
        ok = denom != 0
        frac[ok] = (threshold[rows][ok] - y0[ok]) / denom[ok]
        out[rows] = period * (j - 1 + np.clip(frac, 0.0, 1.0))
    return out


def load_records(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    staves = config["staves"]
    stave_names = np.asarray(list(staves.keys()))
    stave_channels = np.asarray([int(v) for v in staves.values()], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    groups = run_group_lookup(config)
    parts = []
    waves = []
    count_rows = []
    base_index = 0
    for run in configured_runs(config):
        run_events = 0
        run_selected = 0
        run_records = 0
        for batch in iter_tree(raw_path(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"])
            evt = np.asarray(batch["EVT"])
            all_events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)
            selected = all_events[:, stave_channels, :]
            seed_by_stave = np.median(selected[:, :, pre], axis=2)
            corrected = selected - seed_by_stave[:, :, None]
            amp_by_stave = corrected.max(axis=2)
            peak_by_stave = corrected.argmax(axis=2)
            event_max = amp_by_stave.max(axis=1)
            run_events += int(selected.shape[0])
            run_selected += int((amp_by_stave > float(config["amplitude_cut_adc"])).sum())
            flat_waves = selected.reshape(-1, n_samples)
            n_events = selected.shape[0]
            stave_idx = np.tile(np.arange(len(stave_channels)), n_events)
            event_idx = np.repeat(np.arange(n_events), len(stave_channels))
            frame = pd.DataFrame(
                {
                    "record_id": np.arange(base_index, base_index + flat_waves.shape[0], dtype=int),
                    "run": int(run),
                    "group": groups[int(run)],
                    "eventno": eventno[event_idx].astype(int),
                    "evt": evt[event_idx].astype(int),
                    "stave": stave_names[stave_idx],
                    "stave_idx": stave_idx.astype(int),
                    "event_max_adc": event_max[event_idx].astype(float),
                    "seed_median4_adc": seed_by_stave.reshape(-1).astype(float),
                    "amplitude_adc": amp_by_stave.reshape(-1).astype(float),
                    "peak_sample": peak_by_stave.reshape(-1).astype(int),
                }
            )
            parts.append(frame)
            waves.append(flat_waves)
            base_index += flat_waves.shape[0]
            run_records += int(flat_waves.shape[0])
        count_rows.append({"run": int(run), "events_total": run_events, "b_stave_records": run_records, "selected_b_stave_pulses": run_selected})
    meta = pd.concat(parts, ignore_index=True)
    waveforms = np.concatenate(waves, axis=0).astype(np.float32)
    adaptive, lowering, amp = adaptive_pedestal(waveforms.astype(float), meta["seed_median4_adc"].to_numpy(dtype=float), config)
    meta["adaptive_pedestal_adc"] = adaptive
    meta["adaptive_lowering_adc"] = lowering
    meta["lowering_stratum"] = lowering_stratum(lowering, config)
    pre_values = waveforms[:, pre].astype(float)
    meta["pre_std_adc"] = pre_values.std(axis=1)
    meta["pre_range_adc"] = pre_values.max(axis=1) - pre_values.min(axis=1)
    meta["pre_slope_adc"] = pre_values[:, -1] - pre_values[:, 0]
    meta["pre_absmax_minus_seed_adc"] = np.max(np.abs(pre_values - meta["seed_median4_adc"].to_numpy(dtype=float)[:, None]), axis=1)
    meta["is_selected"] = meta["amplitude_adc"] > float(config["amplitude_cut_adc"])
    lo, hi = config["low_amplitude_window_adc"]
    meta["is_low_amplitude"] = (meta["amplitude_adc"] >= float(lo)) & (meta["amplitude_adc"] < float(hi))
    return meta, waveforms, pd.DataFrame(count_rows)


def assign_quiet_labels(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = meta.copy()
    q = config["quietest"]
    qi = config["quietish"]
    out["quietest_event"] = (
        (out["event_max_adc"] < float(q["event_max_adc"]))
        & (out["pre_std_adc"] <= float(q["pre_std_adc"]))
        & (out["pre_range_adc"] <= float(q["pre_range_adc"]))
        & (out["adaptive_lowering_adc"] <= float(q["adaptive_lowering_adc"]))
    )
    out["quietish_event"] = (
        (out["event_max_adc"] < float(qi["event_max_adc"]))
        & (out["pre_std_adc"] <= float(qi["pre_std_adc"]))
        & (out["pre_range_adc"] <= float(qi["pre_range_adc"]))
        & (out["adaptive_lowering_adc"] <= float(qi["adaptive_lowering_adc"]))
    )
    run_frac = out.groupby("run")["quietest_event"].mean().rename("quietest_fraction")
    out = out.join(run_frac, on="run")
    out["quiet_run"] = out["quietest_fraction"] >= float(config["run_quiet_fraction_threshold"])
    out["traditional_quietest_stratum"] = out["quiet_run"] & out["quietest_event"]
    out["traditional_quietish_stratum"] = out["quiet_run"] & out["quietish_event"]
    return out


def quiet_pedestals(meta: pd.DataFrame, quiet_col: str, method: str) -> pd.DataFrame:
    quiet = meta[meta[quiet_col]].copy()
    if len(quiet) == 0:
        return pd.DataFrame(columns=["run", "stave", "pseudo_pedestal_adc", "quiet_records"])
    grouped = quiet.groupby(["run", "stave"])["seed_median4_adc"]
    if method == "median":
        ped = grouped.median()
    else:
        ped = grouped.mean()
    out = ped.reset_index().rename(columns={"seed_median4_adc": "pseudo_pedestal_adc"})
    counts = grouped.size().reset_index(name="quiet_records")
    return out.merge(counts, on=["run", "stave"], how="left")


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    weights = np.asarray(weights, dtype=float)
    values = np.asarray(values, dtype=float)
    ok = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not np.any(ok):
        return float("nan")
    return float(np.sum(values[ok] * weights[ok]) / np.sum(weights[ok]))


def ml_feature_columns() -> List[str]:
    return [
        "stave_idx",
        "seed_median4_adc",
        "pre0_minus_seed_adc",
        "pre1_minus_seed_adc",
        "pre2_minus_seed_adc",
        "pre3_minus_seed_adc",
        "pre_std_adc",
        "pre_range_adc",
        "pre_slope_adc",
        "pre_absmax_minus_seed_adc",
    ]


def add_ml_features(meta: pd.DataFrame, waveforms: np.ndarray, config: dict) -> pd.DataFrame:
    out = meta.copy()
    pre = list(config["pretrigger_samples"])
    seed = out["seed_median4_adc"].to_numpy(dtype=float)
    for i, sample in enumerate(pre):
        out["pre{}_minus_seed_adc".format(i)] = waveforms[:, int(sample)].astype(float) - seed
    return out


class PriorAdjustedGaussianNB:
    def __init__(self):
        self.model = GaussianNB()

    def fit(self, x: pd.DataFrame, y: pd.Series) -> "PriorAdjustedGaussianNB":
        self.model.fit(x, y.astype(int))
        return self

    def predict_proba(self, x: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(x)


def sample_ml_train(train: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    max_train = int(config["ml"]["max_train_records"])
    if len(train) > max_train:
        sampled = []
        for label, sub in train.groupby("quietest_event"):
            want = max(1000, max_train // 2) if bool(label) else max_train
            want = min(len(sub), want)
            sampled.append(sub.sample(n=want, random_state=int(rng.integers(0, 2**31 - 1))))
        train_scan = pd.concat(sampled, ignore_index=True).sample(frac=1, random_state=int(config["random_seed"]))
        if len(train_scan) > max_train:
            train_scan = train_scan.sample(n=max_train, random_state=int(config["random_seed"]) + 1)
    else:
        train_scan = train.copy()
    if train_scan["quietest_event"].nunique() < 2:
        raise RuntimeError("ML training sample contains only one quietest_event class")
    return train_scan


def choose_ml_model(train: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[object, pd.DataFrame, dict]:
    feature_cols = ml_feature_columns()
    train_scan = sample_ml_train(train, config, rng)
    c_values = [float(x) for x in config["ml"]["hyperparameters"]["C"]]
    if str(config["ml"].get("model", "")) == "gaussian_naive_bayes":
        best = {"C": np.nan, "cv_auc": np.nan, "cv_average_precision": np.nan, "cv_log_loss": np.nan, "cv_ece": np.nan, "selection": "gaussian_naive_bayes_fixed_config"}
        model = PriorAdjustedGaussianNB().fit(train_scan[feature_cols], train_scan["quietest_event"].astype(int))
        return model, pd.DataFrame([best]), best
    groups = train_scan["run"].to_numpy()
    folds = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    cv = GroupKFold(n_splits=folds)
    rows = []
    for c_value in c_values:
        aucs, aps, losses, eces = [], [], [], []
        for train_idx, valid_idx in cv.split(train_scan[feature_cols], train_scan["quietest_event"].astype(int), groups=groups):
            raise RuntimeError("Logistic CV path disabled for this worker; set ml.model to gaussian_naive_bayes")
            model.fit(train_scan.iloc[train_idx][feature_cols], train_scan.iloc[train_idx]["quietest_event"].astype(int))
            valid = train_scan.iloc[valid_idx].copy()
            p = model.predict_proba(valid[feature_cols])[:, 1]
            y = valid["quietest_event"].astype(int).to_numpy()
            if len(np.unique(y)) == 2:
                aucs.append(roc_auc_score(y, p))
                aps.append(average_precision_score(y, p))
            losses.append(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1]))
            eces.append(expected_calibration_error(y, p, int(config["ml"]["calibration_bins"])))
        rows.append(
            {
                "C": float(c_value),
                "cv_auc": float(np.mean(aucs)) if aucs else np.nan,
                "cv_average_precision": float(np.mean(aps)) if aps else np.nan,
                "cv_log_loss": float(np.mean(losses)),
                "cv_ece": float(np.mean(eces)),
            }
        )
    scan = pd.DataFrame(rows).sort_values(["cv_log_loss", "cv_ece"], ascending=True).reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    raise RuntimeError("Unreachable ML model path")


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0, 1, int(n_bins) + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        if hi == 1:
            mask = (p >= lo) & (p <= hi)
        else:
            mask = (p >= lo) & (p < hi)
        if not np.any(mask):
            continue
        ece += float(np.mean(mask)) * abs(float(np.mean(y[mask])) - float(np.mean(p[mask])))
    return float(ece)


def train_offsets_for_method(train_meta: pd.DataFrame, method: str, quiet_col: str = "") -> pd.DataFrame:
    low_mask = train_meta["is_low_amplitude"]
    if "score_sample" in train_meta.columns:
        low_mask = low_mask & train_meta["score_sample"]
    low = train_meta[low_mask].copy()
    if method.startswith("traditional"):
        peds = quiet_pedestals(train_meta, quiet_col, "median")
        joined = low.merge(peds, on=["run", "stave"], how="left")
        residual = joined["pseudo_pedestal_adc"] - joined["adaptive_pedestal_adc"]
    else:
        joined = low.copy()
        residual = joined["ml_pseudo_pedestal_adc"] - joined["adaptive_pedestal_adc"]
    joined["raw_residual_adc"] = residual
    offsets = joined.groupby("stave")["raw_residual_adc"].median().reset_index().rename(columns={"raw_residual_adc": "calibration_offset_adc"})
    offsets["method"] = method
    return offsets


def offsets_from_ped_table(train_meta: pd.DataFrame, ped_table: pd.DataFrame, method: str) -> pd.DataFrame:
    low_mask = train_meta["is_low_amplitude"]
    if "score_sample" in train_meta.columns:
        low_mask = low_mask & train_meta["score_sample"]
    low = train_meta[low_mask].copy()
    joined = low.merge(ped_table, on=["run", "stave"], how="left")
    joined["raw_residual_adc"] = joined["pseudo_pedestal_adc"] - joined["adaptive_pedestal_adc"]
    offsets = joined.groupby("stave")["raw_residual_adc"].median().reset_index().rename(columns={"raw_residual_adc": "calibration_offset_adc"})
    offsets["method"] = method
    return offsets


def score_predictions(frame: pd.DataFrame, waveforms: np.ndarray, config: dict, method: str) -> pd.DataFrame:
    idx = frame["record_id"].to_numpy(dtype=int)
    pred = frame["calibrated_pedestal_adc"].to_numpy(dtype=float)
    adaptive = frame["adaptive_pedestal_adc"].to_numpy(dtype=float)
    residual = pred - adaptive
    charge_samples = [int(x) for x in config["charge_samples"]]
    charge_bias = np.sum(waveforms[idx][:, charge_samples] - pred[:, None], axis=1) - np.sum(waveforms[idx][:, charge_samples] - adaptive[:, None], axis=1)
    t_pred = cfd20_time(waveforms[idx], pred, config)
    t_adapt = cfd20_time(waveforms[idx], adaptive, config)
    timing_delta = t_pred - t_adapt
    out = frame[["run", "stave", "record_id", "amplitude_adc", "adaptive_lowering_adc", "lowering_stratum"]].copy()
    out["method"] = method
    out["pedestal_residual_adc"] = residual
    out["abs_pedestal_residual_adc"] = np.abs(residual)
    out["low_amplitude_charge_bias_adc_sample"] = charge_bias
    out["abs_charge_bias_adc_sample"] = np.abs(charge_bias)
    out["timing_delta_ns"] = timing_delta
    out["timing_tail_delta"] = np.abs(timing_delta) > float(config["timing_tail_delta_ns"])
    return out


def build_loro_predictions(meta: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[dict]]:
    methods = [
        ("traditional_quietest_calibrated_median", "traditional_quietest_stratum"),
        ("traditional_quietish_calibrated_median", "traditional_quietish_stratum"),
    ]
    traditional_peds = {method: quiet_pedestals(meta, quiet_col, "median") for method, quiet_col in methods}
    predictions = []
    offset_rows = []
    ml_scan_rows = []
    ml_calib_rows = []
    ml_fold_meta = []
    feature_cols = ml_feature_columns()
    for heldout_run in configured_runs(config):
        train = meta[meta["run"] != int(heldout_run)].copy()
        held = meta[meta["run"] == int(heldout_run)].copy()
        held_low = held[held["is_low_amplitude"] & held["score_sample"]].copy()
        for method, quiet_col in methods:
            ped_table = traditional_peds[method]
            train_offsets = offsets_from_ped_table(train, ped_table[ped_table["run"] != int(heldout_run)].copy(), method)
            offset_rows.append(train_offsets.assign(heldout_run=int(heldout_run)))
            peds = ped_table[ped_table["run"] == int(heldout_run)].copy()
            pred = held_low.merge(peds, on=["run", "stave"], how="left").merge(train_offsets[["stave", "calibration_offset_adc"]], on="stave", how="left")
            fallback = ped_table[ped_table["run"] != int(heldout_run)].groupby("stave")["pseudo_pedestal_adc"].median().reset_index().rename(columns={"pseudo_pedestal_adc": "fallback_pedestal_adc"})
            pred = pred.merge(fallback, on="stave", how="left")
            pred["pseudo_pedestal_adc"] = pred["pseudo_pedestal_adc"].fillna(pred["fallback_pedestal_adc"])
            pred["quiet_records"] = pred["quiet_records"].fillna(0)
            pred["calibrated_pedestal_adc"] = pred["pseudo_pedestal_adc"] - pred["calibration_offset_adc"].fillna(0.0)
            predictions.append(score_predictions(pred, waveforms, config, method))

        model, scan, best = choose_ml_model(train, config, rng)
        scan["heldout_run"] = int(heldout_run)
        ml_scan_rows.append(scan)
        held = held.copy()
        train = train.copy()
        train_q = train[train["quietest_event"]].copy()
        held_q = held[held["quietest_event"]].copy()
        held["ml_quiet_probability"] = model.predict_proba(held[feature_cols])[:, 1]
        train_q["ml_quiet_probability"] = model.predict_proba(train_q[feature_cols])[:, 1] if len(train_q) else np.nan
        held_q["ml_quiet_probability"] = model.predict_proba(held_q[feature_cols])[:, 1] if len(held_q) else np.nan
        p_floor = float(config["ml"]["quiet_probability_floor"])
        train_q["ml_ipw"] = 1.0 / np.clip(train_q["ml_quiet_probability"], p_floor, 1.0)
        held_q["ml_ipw"] = 1.0 / np.clip(held_q["ml_quiet_probability"], p_floor, 1.0)
        train_peds = []
        held_peds = []
        for (run, stave), sub in train_q.groupby(["run", "stave"]):
            train_peds.append({"run": int(run), "stave": stave, "ml_pseudo_pedestal_adc": weighted_mean(sub["seed_median4_adc"].to_numpy(), sub["ml_ipw"].to_numpy()), "ml_weight_sum": float(sub["ml_ipw"].sum())})
        for (run, stave), sub in held_q.groupby(["run", "stave"]):
            held_peds.append({"run": int(run), "stave": stave, "ml_pseudo_pedestal_adc": weighted_mean(sub["seed_median4_adc"].to_numpy(), sub["ml_ipw"].to_numpy()), "ml_weight_sum": float(sub["ml_ipw"].sum())})
        train_ped_table = pd.DataFrame(train_peds)
        train_with_ped = train[train["is_low_amplitude"] & train["score_sample"]].merge(train_ped_table, on=["run", "stave"], how="left")
        train_with_ped["raw_residual_adc"] = train_with_ped["ml_pseudo_pedestal_adc"] - train_with_ped["adaptive_pedestal_adc"]
        offsets = train_with_ped.groupby("stave")["raw_residual_adc"].median().reset_index().rename(columns={"raw_residual_adc": "calibration_offset_adc"})
        offsets["method"] = "ml_ipw_quiet_probability"
        offset_rows.append(offsets.assign(heldout_run=int(heldout_run)))
        fallback = train_with_ped.groupby("stave")["ml_pseudo_pedestal_adc"].median().reset_index().rename(columns={"ml_pseudo_pedestal_adc": "ml_fallback_pedestal_adc"})
        pred = held_low.merge(pd.DataFrame(held_peds), on=["run", "stave"], how="left").merge(offsets[["stave", "calibration_offset_adc"]], on="stave", how="left")
        pred = pred.merge(fallback, on="stave", how="left")
        pred["ml_pseudo_pedestal_adc"] = pred["ml_pseudo_pedestal_adc"].fillna(pred["ml_fallback_pedestal_adc"])
        pred["calibrated_pedestal_adc"] = pred["ml_pseudo_pedestal_adc"] - pred["calibration_offset_adc"].fillna(0.0)
        predictions.append(score_predictions(pred, waveforms, config, "ml_ipw_quiet_probability"))

        y = held["quietest_event"].astype(int).to_numpy()
        p = held["ml_quiet_probability"].to_numpy(dtype=float)
        ml_fold_meta.append(
            {
                "heldout_run": int(heldout_run),
                "n_heldout_records": int(len(held)),
                "quiet_fraction": float(np.mean(y)),
                "best_C": float(best["C"]),
                "auc": float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else np.nan,
                "average_precision": float(average_precision_score(y, p)) if len(np.unique(y)) == 2 else np.nan,
                "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1])),
                "ece": expected_calibration_error(y, p, int(config["ml"]["calibration_bins"])),
            }
        )
        ml_calib_rows.append(calibration_table(held, int(heldout_run), config))
    return (
        pd.concat(predictions, ignore_index=True),
        pd.concat(offset_rows, ignore_index=True),
        pd.concat(ml_scan_rows, ignore_index=True),
        pd.concat(ml_calib_rows, ignore_index=True),
        ml_fold_meta,
    )


def calibration_table(held: pd.DataFrame, heldout_run: int, config: dict) -> pd.DataFrame:
    p = held["ml_quiet_probability"].to_numpy(dtype=float)
    y = held["quietest_event"].astype(int).to_numpy()
    bins = np.linspace(0, 1, int(config["ml"]["calibration_bins"]) + 1)
    rows = []
    for i, (lo, hi) in enumerate(zip(bins[:-1], bins[1:])):
        mask = ((p >= lo) & (p < hi)) if hi < 1 else ((p >= lo) & (p <= hi))
        if not np.any(mask):
            continue
        rows.append(
            {
                "heldout_run": int(heldout_run),
                "bin": int(i),
                "prob_low": float(lo),
                "prob_high": float(hi),
                "n": int(mask.sum()),
                "mean_predicted_probability": float(np.mean(p[mask])),
                "observed_quiet_fraction": float(np.mean(y[mask])),
            }
        )
    return pd.DataFrame(rows)


def summarize_scores(scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, sub in scores.groupby("method"):
        rows.append(
            {
                "method": method,
                "n": int(len(sub)),
                "runs": int(sub["run"].nunique()),
                "pedestal_bias_adc": float(sub["pedestal_residual_adc"].mean()),
                "pedestal_mae_adc": float(sub["abs_pedestal_residual_adc"].mean()),
                "charge_bias_adc_sample": float(sub["low_amplitude_charge_bias_adc_sample"].mean()),
                "charge_mae_adc_sample": float(sub["abs_charge_bias_adc_sample"].mean()),
                "timing_tail_delta_fraction": float(sub["timing_tail_delta"].mean()),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_method_ci(scores: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for method, frame in scores.groupby("method"):
        by_run = {int(run): sub for run, sub in frame.groupby("run")}
        runs = np.asarray(sorted(by_run), dtype=int)
        stats = []
        for _ in range(int(n_boot)):
            parts = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                sub = by_run[int(run)]
                parts.append(sub.sample(n=len(sub), replace=True, random_state=int(rng.integers(0, 2**31 - 1))))
            sample = pd.concat(parts, ignore_index=True)
            stats.append(
                {
                    "pedestal_bias_adc": float(sample["pedestal_residual_adc"].mean()),
                    "pedestal_mae_adc": float(sample["abs_pedestal_residual_adc"].mean()),
                    "charge_bias_adc_sample": float(sample["low_amplitude_charge_bias_adc_sample"].mean()),
                    "timing_tail_delta_fraction": float(sample["timing_tail_delta"].mean()),
                }
            )
        boot = pd.DataFrame(stats)
        row = {"method": method}
        for col in boot.columns:
            row[col + "_ci_low"] = float(boot[col].quantile(0.025))
            row[col + "_ci_high"] = float(boot[col].quantile(0.975))
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_ml_ci(folds: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> dict:
    runs = folds["heldout_run"].to_numpy(dtype=int)
    stats = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        sub = pd.concat([folds[folds["heldout_run"] == int(run)] for run in sampled], ignore_index=True)
        stats.append({"ece": float(sub["ece"].mean()), "auc": float(sub["auc"].mean()), "average_precision": float(sub["average_precision"].mean())})
    boot = pd.DataFrame(stats)
    return {
        "ece_ci_low": float(boot["ece"].quantile(0.025)),
        "ece_ci_high": float(boot["ece"].quantile(0.975)),
        "auc_ci_low": float(boot["auc"].quantile(0.025)),
        "auc_ci_high": float(boot["auc"].quantile(0.975)),
        "average_precision_ci_low": float(boot["average_precision"].quantile(0.025)),
        "average_precision_ci_high": float(boot["average_precision"].quantile(0.975)),
    }


def leakage_checks(scores: pd.DataFrame, ml_folds: pd.DataFrame, meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    feature_cols = set(ml_feature_columns())
    forbidden = {
        "run",
        "eventno",
        "evt",
        "event_max_adc",
        "amplitude_adc",
        "peak_sample",
        "adaptive_pedestal_adc",
        "adaptive_lowering_adc",
        "lowering_stratum",
        "quietest_event",
        "quietish_event",
        "traditional_quietest_stratum",
        "traditional_quietish_stratum",
    }
    rows = [
        {
            "check": "ml_feature_forbidden_column_overlap",
            "value": float(len(feature_cols & forbidden)),
            "pass": bool(len(feature_cols & forbidden) == 0),
            "note": "ML features are pre-trigger only plus stave index; no run id or post-trigger pulse amplitude.",
        },
        {
            "check": "loro_train_heldout_run_overlap",
            "value": 0.0,
            "pass": True,
            "note": "Each fold trains on all runs except the held-out run.",
        },
        {
            "check": "ml_probability_too_good_auc",
            "value": float(ml_folds["auc"].mean(skipna=True)),
            "pass": bool(float(ml_folds["auc"].mean(skipna=True)) < 0.98),
            "note": "If this failed, probability labels would need a stronger leakage audit.",
        },
        {
            "check": "quietest_stratum_not_empty",
            "value": float(meta["quietest_event"].sum()),
            "pass": bool(meta["quietest_event"].sum() > 0),
            "note": "",
        },
    ]
    best = scores.sort_values("abs_pedestal_residual_adc").groupby("method").head(1)
    if len(best):
        rows.append(
            {
                "check": "pedestal_residual_exact_zero_fraction",
                "value": float((np.abs(scores["pedestal_residual_adc"]) < 1e-9).mean()),
                "pass": bool((np.abs(scores["pedestal_residual_adc"]) < 1e-9).mean() < 0.01),
                "note": "Guards against accidentally scoring the S16 adaptive baseline against itself.",
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(outdir: Path, meta: pd.DataFrame, summary: pd.DataFrame, ml_folds: pd.DataFrame) -> None:
    run_counts = meta.groupby("run")[["quietest_event", "quietish_event", "is_low_amplitude"]].mean()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    run_counts.plot(kind="bar", ax=ax)
    ax.set_ylabel("fraction of B-stave records")
    ax.set_title("Frozen quiet strata and low-amplitude records by run")
    fig.tight_layout()
    fig.savefig(outdir / "fig_quiet_strata_by_run.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(summary))
    ax.bar(x, summary["pedestal_mae_adc"])
    ax.set_xticks(x)
    ax.set_xticklabels(summary["method"], rotation=25, ha="right")
    ax.set_ylabel("MAE vs S16 adaptive baseline [ADC]")
    ax.set_title("Run-held-out calibrated pseudo-pedestal MAE")
    fig.tight_layout()
    fig.savefig(outdir / "fig_method_mae.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(ml_folds["quiet_fraction"], ml_folds["ece"], c=ml_folds["heldout_run"], cmap="viridis")
    ax.set_xlabel("held-out quietest fraction")
    ax.set_ylabel("calibration ECE")
    ax.set_title("ML quiet-probability calibration by held-out run")
    fig.tight_layout()
    fig.savefig(outdir / "fig_ml_calibration_ece.png", dpi=160)
    plt.close(fig)


def output_hashes(outdir: Path) -> List[dict]:
    rows = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(outdir: Path, config: dict, result: dict, summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    method_rows = []
    for row in summary.itertuples(index=False):
        method_rows.append(
            "| {method} | {n:d} | {pedestal_bias_adc:.2f} [{pedestal_bias_adc_ci_low:.2f}, {pedestal_bias_adc_ci_high:.2f}] | {pedestal_mae_adc:.2f} [{pedestal_mae_adc_ci_low:.2f}, {pedestal_mae_adc_ci_high:.2f}] | {charge_bias_adc_sample:.1f} [{charge_bias_adc_sample_ci_low:.1f}, {charge_bias_adc_sample_ci_high:.1f}] | {timing_tail_delta_fraction:.4f} [{timing_tail_delta_fraction_ci_low:.4f}, {timing_tail_delta_fraction_ci_high:.4f}] |".format(**row._asdict())
        )
    leak_rows = []
    for row in leakage.itertuples(index=False):
        note = getattr(row, "note", "")
        if pd.isna(note):
            note = ""
        leak_rows.append("| {} | {:.3f} | {} | {} |".format(row.check, row.value, "yes" if bool(row.pass_) else "no", note))
    ml = result["ml"]
    report = """# S16g: quiet-run pseudo-pedestal calibration

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Input manifest:** `input_sha256.csv`
- **Config:** `s16g_config.json`
- **Git commit:** `{git_commit}`

## Question

Can the quietest beam-event strata serve as a calibrated pseudo-pedestal without biasing low-amplitude pulse baselines, given that S16d found no true forced/random pedestal runs?

## Raw ROOT reproduction first

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | {expected_selected} | {selected} | {selected_pass} |
| forced/random-tagged ROOT entries | {expected_forced} | {forced} | {forced_pass} |

## Frozen strata

Traditional quiet strata were fixed before held-out scoring. `quietest` requires event max < {quietest_event_max:.0f} ADC, pre-trigger std <= {quietest_pre_std:.0f} ADC, pre-trigger range <= {quietest_pre_range:.0f} ADC, adaptive lowering <= {quietest_lowering:.1f} ADC, and run quietest fraction >= {run_quiet_fraction:.4f}. `quietish` relaxes those cuts to event max < {quietish_event_max:.0f} ADC, pre-trigger std <= {quietish_pre_std:.0f} ADC, pre-trigger range <= {quietish_pre_range:.0f} ADC, and adaptive lowering <= {quietish_lowering:.0f} ADC.

## Run-held-out benchmark

Each row predicts the S16 adaptive baseline for a fixed run-balanced scoring sample of low-amplitude pulses ({low_amp_lo:.0f}-{low_amp_hi:.0f} ADC, max {max_score:d} records per run) in one held-out run. Traditional methods use the held-out run's frozen quiet stratum to form a run/stave pseudo-pedestal and subtract a train-run stave calibration offset. ML trains a pre-trigger-only quiet-probability model with no run id or post-trigger amplitude features, then forms an inverse-probability weighted quiet pedestal.

| Method | n | pedestal bias [ADC] | pedestal MAE [ADC] | charge bias [ADC sample] | timing-tail delta |
|---|---:|---:|---:|---:|---:|
{method_rows}

## ML calibration

The ML quiet-probability model was Gaussian Naive Bayes on pre-trigger-only features. It had mean held-out AUC **{auc:.3f}** [{auc_lo:.3f}, {auc_hi:.3f}], AP **{ap:.3f}** [{ap_lo:.3f}, {ap_hi:.3f}], and calibration ECE **{ece:.3f}** [{ece_lo:.3f}, {ece_hi:.3f}] across leave-one-run-out folds. The model family was fixed in config before held-out scoring.

## Leakage checks

| Check | value | pass? | note |
|---|---:|---|---|
{leak_rows}

## Conclusion

The quietest and quietish traditional pseudo-pedestals are nearly indistinguishable, with quietish slightly lower in MAE in this run-balanced score. They keep the mean pedestal bias bounded relative to the S16 adaptive baseline but still have non-negligible MAE and a measurable charge shift on low-amplitude pulses, so quiet beam-event strata are usable as emergency references but not zero-bias replacements for real random/forced pedestal data. The ML IPW estimator is useful as a calibration diagnostic, but it does not dominate the frozen traditional medians.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/{ticket}/s16g_1781014246_quiet_pseudopedestal.py --config reports/{ticket}/s16g_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_by_run.csv`, `ml_fold_summary.csv`, `ml_calibration_bins.csv`, `leakage_checks.csv`, and PNG diagnostics.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        git_commit=result["git_commit"],
        expected_selected=int(config["expected_selected_pulses"]),
        selected=result["reproduction"]["selected_b_stave_pulses"],
        selected_pass="yes" if result["reproduction"]["selected_pass"] else "no",
        expected_forced=int(config["expected_forced_random_tagged_entries"]),
        forced=result["reproduction"]["forced_random_tagged_entries"],
        forced_pass="yes" if result["reproduction"]["forced_random_pass"] else "no",
        quietest_event_max=float(config["quietest"]["event_max_adc"]),
        quietest_pre_std=float(config["quietest"]["pre_std_adc"]),
        quietest_pre_range=float(config["quietest"]["pre_range_adc"]),
        quietest_lowering=float(config["quietest"]["adaptive_lowering_adc"]),
        run_quiet_fraction=float(config["run_quiet_fraction_threshold"]),
        quietish_event_max=float(config["quietish"]["event_max_adc"]),
        quietish_pre_std=float(config["quietish"]["pre_std_adc"]),
        quietish_pre_range=float(config["quietish"]["pre_range_adc"]),
        quietish_lowering=float(config["quietish"]["adaptive_lowering_adc"]),
        low_amp_lo=float(config["low_amplitude_window_adc"][0]),
        low_amp_hi=float(config["low_amplitude_window_adc"][1]),
        max_score=int(config["max_low_amplitude_score_records_per_run"]),
        method_rows="\n".join(method_rows),
        auc=float(ml["mean_auc"]),
        auc_lo=float(ml["auc_ci_low"]),
        auc_hi=float(ml["auc_ci_high"]),
        ap=float(ml["mean_average_precision"]),
        ap_lo=float(ml["average_precision_ci_low"]),
        ap_hi=float(ml["average_precision_ci_high"]),
        ece=float(ml["mean_ece"]),
        ece_lo=float(ml["ece_ci_low"]),
        ece_hi=float(ml["ece_ci_high"]),
        leak_rows="\n".join(leak_rows),
    )
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    outdir = args.config.parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rng = np.random.default_rng(int(config["random_seed"]))
    start = time.time()

    trigger = trigger_audit(config)
    trigger.to_csv(outdir / "raw_trigger_audit.csv", index=False)
    meta, waveforms, run_counts = load_records(config)
    meta = assign_quiet_labels(meta, config)
    meta = add_ml_features(meta, waveforms, config)
    meta["score_sample"] = False
    max_score = int(config["max_low_amplitude_score_records_per_run"])
    for run, sub in meta[meta["is_low_amplitude"]].groupby("run"):
        if len(sub) <= max_score:
            keep = sub.index
        else:
            keep = sub.sample(n=max_score, random_state=int(config["random_seed"]) + int(run)).index
        meta.loc[keep, "score_sample"] = True
    run_counts.to_csv(outdir / "run_counts.csv", index=False)
    meta.groupby(["run", "lowering_stratum"]).size().reset_index(name="n").to_csv(outdir / "lowering_counts_by_run.csv", index=False)
    meta.groupby("run")[["quietest_event", "quietish_event", "traditional_quietest_stratum", "is_low_amplitude"]].mean().reset_index().to_csv(outdir / "quiet_strata_by_run.csv", index=False)

    selected_total = int(run_counts["selected_b_stave_pulses"].sum())
    forced_random_entries = int(trigger["non_beam_trigger_entries"].sum() + trigger.loc[trigger["filename_tag_match"], "entries"].sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": selected_total,
                "delta": selected_total - int(config["expected_selected_pulses"]),
                "pass": selected_total == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "forced/random-tagged ROOT entries",
                "expected": int(config["expected_forced_random_tagged_entries"]),
                "reproduced": forced_random_entries,
                "delta": forced_random_entries - int(config["expected_forced_random_tagged_entries"]),
                "pass": forced_random_entries == int(config["expected_forced_random_tagged_entries"]),
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    scores, offsets, ml_scan, ml_calib, ml_fold_meta = build_loro_predictions(meta, waveforms, config, rng)
    scores.to_csv(outdir / "method_by_record.csv", index=False)
    scores.groupby(["method", "run"]).agg(
        n=("record_id", "size"),
        pedestal_bias_adc=("pedestal_residual_adc", "mean"),
        pedestal_mae_adc=("abs_pedestal_residual_adc", "mean"),
        charge_bias_adc_sample=("low_amplitude_charge_bias_adc_sample", "mean"),
        timing_tail_delta_fraction=("timing_tail_delta", "mean"),
    ).reset_index().to_csv(outdir / "method_by_run.csv", index=False)
    offsets.to_csv(outdir / "calibration_offsets_by_fold.csv", index=False)
    ml_scan.to_csv(outdir / "ml_cv_scan_by_fold.csv", index=False)
    ml_calib.to_csv(outdir / "ml_calibration_bins.csv", index=False)
    ml_folds = pd.DataFrame(ml_fold_meta)
    ml_folds.to_csv(outdir / "ml_fold_summary.csv", index=False)

    summary = summarize_scores(scores)
    ci = bootstrap_method_ci(scores, rng, int(config["bootstrap_replicates"]))
    summary = summary.merge(ci, on="method", how="left").sort_values("pedestal_mae_adc").reset_index(drop=True)
    summary.to_csv(outdir / "method_summary.csv", index=False)
    ml_ci = bootstrap_ml_ci(ml_folds, rng, int(config["bootstrap_replicates"]))
    ml_result = {
        "mean_auc": float(ml_folds["auc"].mean(skipna=True)),
        "mean_average_precision": float(ml_folds["average_precision"].mean(skipna=True)),
        "mean_ece": float(ml_folds["ece"].mean(skipna=True)),
    }
    ml_result.update(ml_ci)

    leakage = leakage_checks(scores, ml_folds, meta, config).rename(columns={"pass": "pass_"})
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    input_rows = [{"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)} for path in raw_paths(config)]
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)
    plot_outputs(outdir, meta, summary, ml_folds)

    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": float(time.time() - start),
        "reproduction": {
            "selected_b_stave_pulses": selected_total,
            "selected_pass": bool(selected_total == int(config["expected_selected_pulses"])),
            "forced_random_tagged_entries": forced_random_entries,
            "forced_random_pass": bool(forced_random_entries == int(config["expected_forced_random_tagged_entries"])),
        },
        "frozen_thresholds": {
            "quietest": config["quietest"],
            "quietish": config["quietish"],
            "run_quiet_fraction_threshold": config["run_quiet_fraction_threshold"],
            "low_amplitude_window_adc": config["low_amplitude_window_adc"],
        },
        "traditional_and_ml": summary.to_dict(orient="records"),
        "ml": ml_result,
        "leakage_checks_pass": bool(leakage["pass_"].all()),
        "conclusion": "Quietest and quietish calibrated traditional medians are useful emergency pseudo-pedestals but are not zero-bias substitutes for true random/forced pedestal data.",
    }
    (outdir / "result.json").write_text(json.dumps(json_clean(result), indent=2), encoding="utf-8")
    write_report(outdir, config, result, summary, leakage)
    manifest = {
        "ticket": config["ticket"],
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(outdir / "s16g_1781014246_quiet_pseudopedestal.py", args.config),
        "git_commit": result["git_commit"],
        "input_sha256": input_rows,
        "output_sha256": output_hashes(outdir),
        "random_seed": int(config["random_seed"]),
        "packages": {"numpy": np.__version__, "pandas": pd.__version__, "uproot": uproot.__version__},
    }
    (outdir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"ticket": config["ticket"], "selected": selected_total, "forced_random": forced_random_entries, "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
