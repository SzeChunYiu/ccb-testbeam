#!/usr/bin/env python3
"""P01g latent baseline-contamination atom map.

The analysis starts from raw B-stack ROOT files, reproduces the selected-pulse
count and P01b latent key hash, then asks whether the frozen P01b latent
coordinates carry nuisance atoms after run-heldout matching controls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)
TARGETS = [
    "s16_baseline_excursion",
    "s16_adaptive_lowering",
    "p09_dropout_delayed_peak",
    "p07_saturation_boundary",
    "s03_timing_tail",
    "p04_charge_bias_tail",
]
METHOD_ORDER = [
    "traditional_hand_pca_logistic",
    "ridge_latent_logistic",
    "gbt_latent_hand",
    "mlp_latent_hand",
    "cnn_waveform",
    "wave_latent_gate",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def resolve_first_existing(candidates: Sequence[str], predicate) -> Path:
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if predicate(path):
            return path
    raise FileNotFoundError("No configured candidate exists")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = str(group)
    return out


def key_sha256(run: np.ndarray, event_index: np.ndarray, stave_index: np.ndarray) -> str:
    key_bytes = b"|".join(
        [
            np.asarray(run, dtype=np.int16).tobytes(),
            np.asarray(event_index, dtype=np.int32).tobytes(),
            np.asarray(stave_index, dtype=np.int8).tobytes(),
        ]
    )
    return sha256_bytes(key_bytes)


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd_crossing(waves: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    thresholds = amplitudes * float(fraction)
    ge = waves >= thresholds[:, None]
    first = np.argmax(ge, axis=1)
    out = np.full(len(waves), np.nan, dtype=np.float32)
    valid = ge.any(axis=1)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = float(waves[i, j - 1])
        y1 = float(waves[i, j])
        denom = y1 - y0
        out[i] = float(j) if abs(denom) < 1e-9 else (j - 1.0) + float((thresholds[i] - y0) / denom)
    return out


def waveform_features(corrected: np.ndarray, raw: np.ndarray, baseline_idx: Sequence[int], config: dict) -> pd.DataFrame:
    amp = np.maximum(corrected.max(axis=1), 1.0)
    peak = corrected.argmax(axis=1).astype(np.int16)
    positive = np.clip(corrected, 0.0, None)
    pos_sum = np.maximum(positive.sum(axis=1), 1.0)
    area = corrected.sum(axis=1)
    raw_pre = raw[:, baseline_idx]
    pre_med = np.median(raw_pre, axis=1)
    pre_centered = raw_pre - pre_med[:, None]
    baseline_mean = raw_pre.mean(axis=1)
    baseline_rms = np.sqrt(np.mean(pre_centered * pre_centered, axis=1))
    baseline_slope = raw_pre[:, -1] - raw_pre[:, 0]
    baseline_ptp = raw_pre.max(axis=1) - raw_pre.min(axis=1)
    baseline_asym = 0.5 * ((raw_pre[:, 0] + raw_pre[:, 1]) - (raw_pre[:, 2] + raw_pre[:, 3]))
    baseline_max_exc = np.max(np.abs(pre_centered), axis=1)
    adaptive_lowering = np.maximum(0.0, pre_med - (raw_pre.min(axis=1) + 10.0))
    norm = corrected / amp[:, None]
    secondary_peak = np.zeros(len(corrected), dtype=np.float32)
    secondary_sep = np.zeros(len(corrected), dtype=np.float32)
    post_peak_min = np.zeros(len(corrected), dtype=np.float32)
    undershoot_area = np.zeros(len(corrected), dtype=np.float32)
    dropout_score = np.zeros(len(corrected), dtype=np.float32)
    for i, p in enumerate(peak):
        masked = positive[i].copy()
        lo = max(0, int(p) - 1)
        hi = min(corrected.shape[1], int(p) + 2)
        masked[lo:hi] = 0.0
        sidx = int(masked.argmax())
        secondary_peak[i] = float(masked[sidx] / amp[i])
        secondary_sep[i] = float(abs(sidx - int(p)))
        tail = norm[i, min(corrected.shape[1] - 1, int(p) + 1) :]
        post_peak_min[i] = float(tail.min()) if len(tail) else 0.0
        undershoot_area[i] = float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0
        dropout_score[i] = float(max(0.0, -post_peak_min[i]) + max(0.0, secondary_peak[i] - 0.5))
    return pd.DataFrame(
        {
            "amplitude_adc": amp.astype(np.float32),
            "log_amp": np.log(np.maximum(amp, 1.0)).astype(np.float32),
            "area_over_amp": (area / amp).astype(np.float32),
            "positive_area_over_amp": (pos_sum / amp).astype(np.float32),
            "peak_sample": peak,
            "width20": (corrected > (0.20 * amp[:, None])).sum(axis=1).astype(np.int16),
            "width50": (corrected > (0.50 * amp[:, None])).sum(axis=1).astype(np.int16),
            "early_fraction": (positive[:, :4].sum(axis=1) / pos_sum).astype(np.float32),
            "late_fraction": (positive[:, 12:].sum(axis=1) / pos_sum).astype(np.float32),
            "tail_fraction": (positive[:, 9:].sum(axis=1) / pos_sum).astype(np.float32),
            "baseline_mean_adc": baseline_mean.astype(np.float32),
            "baseline_rms_adc": baseline_rms.astype(np.float32),
            "baseline_slope_adc": baseline_slope.astype(np.float32),
            "baseline_ptp_adc": baseline_ptp.astype(np.float32),
            "baseline_asym_adc": baseline_asym.astype(np.float32),
            "baseline_max_exc_adc": baseline_max_exc.astype(np.float32),
            "adaptive_lowering_adc": adaptive_lowering.astype(np.float32),
            "raw_max_adc": raw.max(axis=1).astype(np.float32),
            "saturation_count": (raw >= float(config["saturation_raw_adc"])).sum(axis=1).astype(np.int16),
            "secondary_peak": secondary_peak,
            "secondary_sep": secondary_sep,
            "post_peak_min": post_peak_min,
            "undershoot_area": undershoot_area,
            "dropout_score": dropout_score,
        }
    )


def scan_raw(config: dict, raw_dir: Path) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(x) for x in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {str(k): int(v) for k, v in config["staves"].items()}
    channels = np.asarray([staves[str(name)] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    count_rows: List[dict] = []
    group_counts: Dict[str, dict] = {}
    for group in config["run_groups"]:
        group_counts[group] = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        group_counts[group].update({str(name): 0 for name in STAVE_NAMES})

    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {"run": int(run), "group": groups[int(run)], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        run_counts.update({str(name): 0 for name in STAVE_NAMES})
        event_offset = 0
        for batch in iter_batches(path):
            raw_all = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            raw_sel = raw_all[:, channels, :]
            baseline = np.median(raw_sel[..., baseline_idx], axis=-1)
            corrected = raw_sel - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)
            run_counts["events_total"] += int(len(raw_all))
            run_counts["events_with_selected"] += int(selected.any(axis=1).sum())
            run_counts["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(STAVE_NAMES):
                run_counts[str(name)] += int(selected[:, i].sum())
            if len(event_idx):
                chosen = corrected[event_idx, stave_idx]
                chosen_raw = raw_sel[event_idx, stave_idx]
                feat = waveform_features(chosen, chosen_raw, baseline_idx, config)
                feat.insert(0, "stave_index", stave_idx.astype(np.int8))
                feat.insert(0, "stave", STAVE_NAMES[stave_idx])
                feat.insert(0, "group", groups[int(run)])
                feat.insert(0, "event_index", (event_idx + event_offset).astype(np.int32))
                feat.insert(0, "run", np.full(len(event_idx), run, dtype=np.int16))
                frames.append(feat)
                amp = np.maximum(feat["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
                waves.append(np.clip(np.nan_to_num(chosen / amp[:, None], nan=0.0, posinf=0.0, neginf=0.0), -5.0, 5.0).astype(np.float32))
            event_offset += int(len(raw_all))
        count_rows.append(run_counts.copy())
        g = group_counts[groups[int(run)]]
        for key in ["events_total", "events_with_selected", "selected_pulses"]:
            g[key] += int(run_counts[key])
        for name in STAVE_NAMES:
            g[str(name)] += int(run_counts[str(name)])
        print("raw run {:04d}: {} selected pulses".format(run, run_counts["selected_pulses"]), flush=True)

    group_rows = []
    for group in config["run_groups"]:
        row = {"group": group}
        row.update(group_counts[group])
        group_rows.append(row)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(count_rows), pd.DataFrame(group_rows)


def compare_counts(config: dict, group_counts: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(group_counts["selected_pulses"].sum()),
            "tolerance": 0,
        }
    ]
    for group, exp in expected["groups"].items():
        actual = group_counts[group_counts["group"] == group].iloc[0]
        if "events" in exp:
            rows.append({"quantity": group + " events with selected pulse", "report_value": int(exp["events"]), "reproduced": int(actual["events_with_selected"]), "tolerance": 0})
        if "pulses" in exp:
            rows.append({"quantity": group + " selected pulses", "report_value": int(exp["pulses"]), "reproduced": int(actual["selected_pulses"]), "tolerance": 0})
        for stave, value in exp.get("staves", {}).items():
            rows.append({"quantity": group + " " + stave + " selected pulses", "report_value": int(value), "reproduced": int(actual[stave]), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def load_latent(path: Path) -> Tuple[pd.DataFrame, np.ndarray]:
    with np.load(str(path)) as zf:
        z = zf["z"].astype(np.float32)
        frame = pd.DataFrame(
            {
                "run": zf["run"].astype(np.int16),
                "event_index": zf["event_index"].astype(np.int32),
                "stave_index": zf["stave_index"].astype(np.int8),
                "latent_amplitude_adc": zf["amplitude_adc"].astype(np.float32),
            }
        )
    for i in range(z.shape[1]):
        frame["z{}".format(i)] = z[:, i]
    return frame, z


def join_latents(meta: pd.DataFrame, latent_frame: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    raw_key = key_sha256(meta["run"].to_numpy(), meta["event_index"].to_numpy(), meta["stave_index"].to_numpy())
    latent_key = key_sha256(latent_frame["run"].to_numpy(), latent_frame["event_index"].to_numpy(), latent_frame["stave_index"].to_numpy())
    key_cols = ["run", "event_index", "stave_index"]
    dup_raw = int(meta.duplicated(key_cols).sum())
    dup_latent = int(latent_frame.duplicated(key_cols).sum())
    if raw_key == latent_key and len(meta) == len(latent_frame):
        out = pd.concat([meta.reset_index(drop=True), latent_frame[[c for c in latent_frame.columns if c.startswith("z") or c == "latent_amplitude_adc"]].reset_index(drop=True)], axis=1)
        join_rows = len(out)
        max_amp_delta = float(np.max(np.abs(out["amplitude_adc"].to_numpy() - out["latent_amplitude_adc"].to_numpy())))
    else:
        out = meta.merge(latent_frame, on=key_cols, how="inner", validate="one_to_one")
        join_rows = len(out)
        max_amp_delta = float(np.max(np.abs(out["amplitude_adc"].to_numpy() - out["latent_amplitude_adc"].to_numpy()))) if join_rows else float("nan")
    checks = pd.DataFrame(
        [
            {"check": "raw_key_sha256", "value": raw_key, "expected": config["expected_key_sha256"], "pass": raw_key == config["expected_key_sha256"]},
            {"check": "latent_key_sha256", "value": latent_key, "expected": config["expected_key_sha256"], "pass": latent_key == config["expected_key_sha256"]},
            {"check": "raw_latent_key_order_equal", "value": str(raw_key == latent_key), "expected": "True", "pass": raw_key == latent_key},
            {"check": "raw_duplicate_keys", "value": str(dup_raw), "expected": "0", "pass": dup_raw == 0},
            {"check": "latent_duplicate_keys", "value": str(dup_latent), "expected": "0", "pass": dup_latent == 0},
            {"check": "inner_join_rows", "value": str(join_rows), "expected": str(config["expected_selected_pulses"]), "pass": join_rows == int(config["expected_selected_pulses"])},
            {"check": "max_abs_amplitude_delta_adc", "value": "{:.6g}".format(max_amp_delta), "expected": "0", "pass": abs(max_amp_delta) <= 1e-5},
        ]
    )
    return out, checks


def add_event_outcomes(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    positions = {"B4": 0.0, "B6": float(config["spacing_cm"]), "B8": 2.0 * float(config["spacing_cm"])}
    downstream = out[out["stave"].isin(["B4", "B6", "B8"])].copy()
    amps = downstream["amplitude_adc"].to_numpy(dtype=np.float32)
    # Reconstruct a CFD proxy from stored shape summaries: peak sample is dominant;
    # fold-local quantiles define only the tail label later.
    downstream["tcorr_ns"] = downstream["peak_sample"].astype(float) * float(config["sample_period_ns"]) - downstream["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = downstream.pivot_table(index=["run", "event_index"], columns="stave", values="tcorr_ns", aggfunc="first")
    pair_abs = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a in wide.columns and b in wide.columns:
            pair_abs.append((wide[a] - wide[b]).abs())
    if pair_abs:
        event_resid = pd.concat(pair_abs, axis=1).max(axis=1).rename("event_timing_abs_resid_ns")
        out = out.merge(event_resid, left_on=["run", "event_index"], right_index=True, how="left")
    else:
        out["event_timing_abs_resid_ns"] = np.nan
    return out


def charge_residuals(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    xcols = ["log_amp", "peak_sample", "area_over_amp"]
    stave_train = np.zeros((len(train), 4), dtype=np.float32)
    stave_train[np.arange(len(train)), train["stave_index"].to_numpy(dtype=int)] = 1.0
    stave_test = np.zeros((len(test), 4), dtype=np.float32)
    stave_test[np.arange(len(test)), test["stave_index"].to_numpy(dtype=int)] = 1.0
    x_train = np.nan_to_num(np.column_stack([train[xcols].to_numpy(dtype=np.float32), stave_train]), nan=0.0, posinf=0.0, neginf=0.0)
    x_test = np.nan_to_num(np.column_stack([test[xcols].to_numpy(dtype=np.float32), stave_test]), nan=0.0, posinf=0.0, neginf=0.0)
    y_train = np.nan_to_num(train["positive_area_over_amp"].to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0, solver="lsqr"))
    model.fit(x_train, y_train)
    return y_train - model.predict(x_train), test["positive_area_over_amp"].to_numpy(dtype=np.float32) - model.predict(x_test)


def assign_fold_targets(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
    train = train.copy()
    test = test.copy()
    train_charge, test_charge = charge_residuals(train, test)
    train["charge_residual"] = train_charge
    test["charge_residual"] = test_charge
    train["baseline_score"] = np.sqrt(train["baseline_rms_adc"] ** 2 + train["baseline_slope_adc"] ** 2 + train["baseline_ptp_adc"] ** 2 + train["baseline_max_exc_adc"] ** 2)
    test["baseline_score"] = np.sqrt(test["baseline_rms_adc"] ** 2 + test["baseline_slope_adc"] ** 2 + test["baseline_ptp_adc"] ** 2 + test["baseline_max_exc_adc"] ** 2)
    train["delayed_dropout_score"] = train["dropout_score"] + np.maximum(0.0, train["late_fraction"] - train["late_fraction"].median()) + 0.15 * train["secondary_peak"]
    test["delayed_dropout_score"] = test["dropout_score"] + np.maximum(0.0, test["late_fraction"] - train["late_fraction"].median()) + 0.15 * test["secondary_peak"]
    train["saturation_boundary_score"] = train["saturation_count"].astype(float) + train["raw_max_adc"].astype(float) / 4090.0 + train["amplitude_adc"].astype(float) / 7000.0
    test["saturation_boundary_score"] = test["saturation_count"].astype(float) + test["raw_max_adc"].astype(float) / 4090.0 + test["amplitude_adc"].astype(float) / 7000.0
    thresholds = {
        "baseline_score_q95": float(train["baseline_score"].quantile(0.95)),
        "adaptive_lowering_q90": float(train["adaptive_lowering_adc"].quantile(0.90)),
        "delayed_dropout_q95": float(train["delayed_dropout_score"].quantile(0.95)),
        "peak_sample_q95": float(train["peak_sample"].quantile(0.95)),
        "saturation_boundary_q90": float(train["saturation_boundary_score"].quantile(0.90)),
        "timing_tail_q90": float(train["event_timing_abs_resid_ns"].dropna().quantile(0.90)),
        "charge_abs_q90": float(np.quantile(np.abs(train_charge), 0.90)),
    }
    for frame in [train, test]:
        frame["s16_baseline_excursion"] = (frame["baseline_score"] >= thresholds["baseline_score_q95"]).astype(np.int8)
        frame["s16_adaptive_lowering"] = (frame["adaptive_lowering_adc"] >= thresholds["adaptive_lowering_q90"]).astype(np.int8)
        frame["p09_dropout_delayed_peak"] = ((frame["delayed_dropout_score"] >= thresholds["delayed_dropout_q95"]) | (frame["peak_sample"] >= thresholds["peak_sample_q95"])).astype(np.int8)
        frame["p07_saturation_boundary"] = (frame["saturation_boundary_score"] >= thresholds["saturation_boundary_q90"]).astype(np.int8)
        frame["s03_timing_tail"] = (frame["event_timing_abs_resid_ns"] >= thresholds["timing_tail_q90"]).fillna(False).astype(np.int8)
        frame["p04_charge_bias_tail"] = (frame["charge_residual"].abs() >= thresholds["charge_abs_q90"]).astype(np.int8)
    return train, test, thresholds


def onehot_stave(df: pd.DataFrame) -> np.ndarray:
    idx = df["stave_index"].to_numpy(dtype=int)
    out = np.zeros((len(df), 4), dtype=np.float32)
    out[np.arange(len(df)), idx] = 1.0
    return out


def hand_matrix(df: pd.DataFrame) -> np.ndarray:
    cols = [
        "log_amp",
        "area_over_amp",
        "positive_area_over_amp",
        "peak_sample",
        "width20",
        "width50",
        "early_fraction",
        "late_fraction",
        "tail_fraction",
        "baseline_mean_adc",
        "baseline_rms_adc",
        "baseline_slope_adc",
        "baseline_ptp_adc",
        "baseline_asym_adc",
        "baseline_max_exc_adc",
        "adaptive_lowering_adc",
        "raw_max_adc",
        "saturation_count",
        "saturation_boundary_score",
        "secondary_peak",
        "secondary_sep",
        "post_peak_min",
        "undershoot_area",
        "dropout_score",
        "baseline_score",
        "delayed_dropout_score",
    ]
    return np.nan_to_num(np.column_stack([df[cols].to_numpy(dtype=np.float32), onehot_stave(df)]), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def pca_train_project(train_wave: np.ndarray, test_wave: np.ndarray, n_components: int = 4) -> Tuple[np.ndarray, np.ndarray]:
    train = np.nan_to_num(train_wave.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    test = np.nan_to_num(test_wave.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    mean = train.mean(axis=0)
    std = train.std(axis=0)
    std = np.where(np.isfinite(std) & (std > 1e-8), std, 1.0)
    z_train = np.clip((train - mean) / std, -20.0, 20.0)
    z_test = np.clip((test - mean) / std, -20.0, 20.0)
    cov = np.dot(z_train.T, z_train) / max(len(z_train) - 1, 1)
    cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1][:n_components]
    basis = vecs[:, order]
    return z_train.dot(basis).astype(np.float32), z_test.dot(basis).astype(np.float32)


def latent_matrix(df: pd.DataFrame) -> np.ndarray:
    cols = [c for c in df.columns if c.startswith("z")]
    return df[cols].to_numpy(dtype=np.float32)


def sample_train_indices(y: np.ndarray, max_rows: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    idx = np.arange(len(y))
    if len(idx) <= max_rows:
        return idx
    pos = idx[y == 1]
    neg = idx[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.sort(rng.choice(idx, size=max_rows, replace=False))
    pos_take = min(len(pos), max(max_rows // 3, min(len(pos), max_rows // 2)))
    neg_take = max_rows - pos_take
    chosen = np.concatenate([rng.choice(pos, size=pos_take, replace=False), rng.choice(neg, size=neg_take, replace=False)])
    rng.shuffle(chosen)
    return chosen


def sample_test_indices(n: int, max_rows: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if n <= max_rows:
        return np.arange(n)
    return np.sort(rng.choice(np.arange(n), size=max_rows, replace=False))


def auc_or_nan(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def ap_or_nan(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def brier_or_nan(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(brier_score_loss(y, np.clip(score, 1e-6, 1.0 - 1e-6)))


def fit_predict_sklearn(estimator, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, sample_weight=None) -> np.ndarray:
    est = clone(estimator)
    if sample_weight is None:
        est.fit(x_train, y_train)
    else:
        est.fit(x_train, y_train, sample_weight=sample_weight)
    if hasattr(est, "predict_proba"):
        return est.predict_proba(x_test)[:, 1]
    decision = est.decision_function(x_test)
    return 1.0 / (1.0 + np.exp(-decision))


class WaveCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        z = self.net(wave[:, None, :]).squeeze(-1)
        return self.head(z).squeeze(1)


class WaveLatentGate(nn.Module):
    def __init__(self, n_tab: int) -> None:
        super().__init__()
        self.wave = nn.Sequential(
            nn.Conv1d(1, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.tab = nn.Sequential(nn.Linear(n_tab, 32), nn.ReLU(), nn.Linear(32, 32), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(n_tab, 32), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(64, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        zw = self.wave(wave[:, None, :]).squeeze(-1)
        zt = self.tab(tab)
        gated = zw * self.gate(tab)
        return self.head(torch.cat([gated, zt], dim=1)).squeeze(1)


def torch_predict(model: nn.Module, wave: np.ndarray, tab: np.ndarray, batch_size: int, device: torch.device) -> np.ndarray:
    model.eval()
    out = []
    with torch.no_grad():
        for start in range(0, len(wave), batch_size):
            end = min(len(wave), start + batch_size)
            ww = torch.from_numpy(wave[start:end]).to(device)
            tt = torch.from_numpy(tab[start:end]).to(device)
            out.append(torch.sigmoid(model(ww, tt)).cpu().numpy())
    return np.concatenate(out)


def fit_predict_torch(kind: str, wave_train: np.ndarray, tab_train: np.ndarray, y_train: np.ndarray, wave_test: np.ndarray, tab_test: np.ndarray, config: dict, seed: int) -> np.ndarray:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    batch_size = int(config["ml"]["nn_batch_size"])
    epochs = int(config["ml"]["nn_epochs"])
    if kind == "cnn_waveform":
        model: nn.Module = WaveCNN()
        tab_train_scaled = np.zeros((len(tab_train), 1), dtype=np.float32)
        tab_test_scaled = np.zeros((len(tab_test), 1), dtype=np.float32)
    else:
        scaler = StandardScaler()
        tab_train_scaled = scaler.fit_transform(tab_train).astype(np.float32)
        tab_test_scaled = scaler.transform(tab_test).astype(np.float32)
        model = WaveLatentGate(tab_train_scaled.shape[1])
    scale = max(float(np.percentile(np.abs(wave_train), 95)), 1.0)
    wave_train_scaled = (wave_train / scale).astype(np.float32)
    wave_test_scaled = (wave_test / scale).astype(np.float32)
    model.to(device)
    y_float = y_train.astype(np.float32)
    pos = max(float(y_float.sum()), 1.0)
    neg = max(float(len(y_float) - y_float.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    n = len(y_train)
    for _ in range(epochs):
        order = rng.permutation(n)
        model.train()
        for start in range(0, n, batch_size):
            idx = order[start : start + batch_size]
            ww = torch.from_numpy(wave_train_scaled[idx]).to(device)
            tt = torch.from_numpy(tab_train_scaled[idx]).to(device)
            yy = torch.from_numpy(y_float[idx]).to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(ww, tt), yy)
            loss.backward()
            opt.step()
    return torch_predict(model, wave_test_scaled, tab_test_scaled, batch_size * 4, device)


def run_models(df: pd.DataFrame, waves: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    folds = min(int(config["ml"]["group_folds"]), df["run"].nunique())
    gkf = GroupKFold(n_splits=folds)
    seed = int(config["ml"]["random_seed"])
    preds: List[pd.DataFrame] = []
    fold_rows: List[dict] = []
    leakage_rows: List[dict] = []
    target_rows: List[pd.DataFrame] = []
    split_iter = gkf.split(df, groups=df["run"])
    for fold, (train_idx, test_idx) in enumerate(split_iter, start=1):
        train0 = df.iloc[train_idx].copy()
        test0 = df.iloc[test_idx].copy()
        train, test, thresholds = assign_fold_targets(train0, test0)
        target_rows.append(test[["run", "stave", "stave_index"] + TARGETS + ["charge_residual", "baseline_score", "delayed_dropout_score"]].assign(fold=fold))
        train_wave = np.clip(np.nan_to_num(waves[train.index.to_numpy()], nan=0.0, posinf=0.0, neginf=0.0), -5.0, 5.0).astype(np.float32)
        test_wave = np.clip(np.nan_to_num(waves[test.index.to_numpy()], nan=0.0, posinf=0.0, neginf=0.0), -5.0, 5.0).astype(np.float32)
        train_hand = hand_matrix(train)
        test_hand = hand_matrix(test)
        train_latent = latent_matrix(train)
        test_latent = latent_matrix(test)
        train_full = np.column_stack([train_latent, train_hand]).astype(np.float32)
        test_full = np.column_stack([test_latent, test_hand]).astype(np.float32)
        train_pca, test_pca = pca_train_project(train_wave, test_wave, n_components=4)
        train_trad = np.column_stack([train_hand, train_pca]).astype(np.float32)
        test_trad = np.column_stack([test_hand, test_pca]).astype(np.float32)
        test_take = sample_test_indices(len(test), int(config["ml"]["max_test_rows_per_fold"]), seed + 700 + fold)
        print("fold {} heldout runs {}".format(fold, sorted(test["run"].unique())), flush=True)
        for target in TARGETS:
            y_train_all = train[target].to_numpy(dtype=np.int8)
            y_test_all = test[target].to_numpy(dtype=np.int8)
            if len(np.unique(y_train_all)) < 2 or len(np.unique(y_test_all[test_take])) < 2:
                continue
            take = sample_train_indices(y_train_all, int(config["ml"]["max_train_rows_per_fold"]), seed + fold * 101 + len(target))
            y_train = y_train_all[take]
            y_test = y_test_all[test_take]
            methods: Dict[str, np.ndarray] = {}
            methods["traditional_hand_pca_logistic"] = fit_predict_sklearn(
                make_pipeline(StandardScaler(), LogisticRegression(C=1.0, penalty="l2", solver="liblinear", class_weight="balanced", max_iter=500)),
                train_trad[take],
                y_train,
                test_trad[test_take],
            )
            methods["ridge_latent_logistic"] = fit_predict_sklearn(
                make_pipeline(StandardScaler(), LogisticRegression(C=0.5, penalty="l2", solver="liblinear", class_weight="balanced", max_iter=500)),
                train_latent[take],
                y_train,
                test_latent[test_take],
            )
            weights = np.where(y_train == 1, len(y_train) / max(2.0 * y_train.sum(), 1.0), len(y_train) / max(2.0 * (len(y_train) - y_train.sum()), 1.0))
            methods["gbt_latent_hand"] = fit_predict_sklearn(
                HistGradientBoostingClassifier(max_iter=120, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=30, l2_regularization=0.05, random_state=seed + fold),
                train_full[take],
                y_train,
                test_full[test_take],
                sample_weight=weights,
            )
            mlp_take = sample_train_indices(y_train_all, min(int(config["ml"]["max_train_rows_per_fold"]), 14000), seed + fold * 331 + len(target))
            methods["mlp_latent_hand"] = fit_predict_sklearn(
                make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-3, learning_rate_init=1e-3, max_iter=80, early_stopping=True, random_state=seed + fold)),
                train_full[mlp_take],
                y_train_all[mlp_take],
                test_full[test_take],
            )
            nn_take = sample_train_indices(y_train_all, min(int(config["ml"]["max_train_rows_per_fold"]), 12000), seed + fold * 431 + len(target))
            methods["cnn_waveform"] = fit_predict_torch(
                "cnn_waveform",
                train_wave[nn_take],
                train_latent[nn_take],
                y_train_all[nn_take],
                test_wave[test_take],
                test_latent[test_take],
                config,
                seed + fold * 1000 + len(target),
            )
            methods["wave_latent_gate"] = fit_predict_torch(
                "wave_latent_gate",
                train_wave[nn_take],
                train_full[nn_take],
                y_train_all[nn_take],
                test_wave[test_take],
                test_full[test_take],
                config,
                seed + fold * 2000 + len(target),
            )
            base = test.iloc[test_take][["run", "stave", "stave_index"]].copy()
            base["fold"] = fold
            base["target"] = target
            base["y_true"] = y_test
            base["positive_rate"] = float(y_test.mean())
            for method, score in methods.items():
                base[method] = np.clip(score, 1e-6, 1.0 - 1e-6)
            preds.append(base)
            fold_rows.append({"fold": fold, "target": target, "heldout_runs": ",".join(str(r) for r in sorted(test["run"].unique())), "train_rows": int(len(train)), "fit_rows": int(len(take)), "test_rows": int(len(test_take)), **thresholds})

            sentinels = {
                "amplitude_only_auc": train[["log_amp"]].to_numpy(dtype=np.float32),
                "run_only_auc": pd.get_dummies(train["run"]).reindex(columns=sorted(df["run"].unique()), fill_value=0).to_numpy(dtype=np.float32),
                "stave_only_auc": onehot_stave(train),
            }
            sentinel_test = {
                "amplitude_only_auc": test[["log_amp"]].to_numpy(dtype=np.float32),
                "run_only_auc": pd.get_dummies(test["run"]).reindex(columns=sorted(df["run"].unique()), fill_value=0).to_numpy(dtype=np.float32),
                "stave_only_auc": onehot_stave(test),
            }
            leak = {"fold": fold, "target": target, "heldout_runs": ",".join(str(r) for r in sorted(test["run"].unique()))}
            for name, xtr in sentinels.items():
                try:
                    prob = fit_predict_sklearn(
                        make_pipeline(StandardScaler(with_mean=False), LogisticRegression(solver="liblinear", class_weight="balanced", max_iter=300)),
                        xtr[take],
                        y_train,
                        sentinel_test[name][test_take],
                    )
                    leak[name] = auc_or_nan(y_test, prob)
                except Exception:
                    leak[name] = float("nan")
            shuffled = y_train.copy()
            np.random.default_rng(seed + 3333 + fold).shuffle(shuffled)
            shuf_prob = fit_predict_sklearn(
                make_pipeline(StandardScaler(), LogisticRegression(solver="liblinear", class_weight="balanced", max_iter=300)),
                train_full[take],
                shuffled,
                test_full[test_take],
            )
            leak["shuffled_label_auc"] = auc_or_nan(y_test, shuf_prob)
            leakage_rows.append(leak)
            print("fold {} target {} done".format(fold, target), flush=True)
    return pd.concat(preds, ignore_index=True), pd.DataFrame(fold_rows), pd.DataFrame(leakage_rows), pd.concat(target_rows, ignore_index=True)


def bootstrap_metric(preds: pd.DataFrame, target: str, method: str, metric: str, reps: int, seed: int) -> Tuple[float, float, float]:
    sub = preds[preds["target"] == target].copy()
    if sub.empty:
        return float("nan"), float("nan"), float("nan")
    y = sub["y_true"].to_numpy(dtype=int)
    score = sub[method].to_numpy(dtype=float)
    if metric == "auc":
        center = auc_or_nan(y, score)
    elif metric == "ap":
        center = ap_or_nan(y, score)
    elif metric == "brier":
        center = brier_or_nan(y, score)
    else:
        raise ValueError(metric)
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
    by_run = {int(run): np.flatnonzero(sub["run"].to_numpy(dtype=int) == int(run)) for run in runs}
    vals = []
    for _ in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        idx = np.concatenate([by_run[int(run)] for run in chosen])
        yy = y[idx]
        ss = score[idx]
        if metric == "auc":
            val = auc_or_nan(yy, ss)
        elif metric == "ap":
            val = ap_or_nan(yy, ss)
        else:
            val = brier_or_nan(yy, ss)
        if not math.isnan(val):
            vals.append(val)
    if not vals:
        return center, float("nan"), float("nan")
    lo, hi = np.quantile(vals, [0.025, 0.975])
    return center, float(lo), float(hi)


def summarize_metrics(preds: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    reps = int(config["ml"]["bootstrap_replicates"])
    seed = int(config["ml"]["random_seed"])
    for target in TARGETS:
        for method in METHOD_ORDER:
            if method not in preds.columns:
                continue
            for metric in ["auc", "ap", "brier"]:
                center, lo, hi = bootstrap_metric(preds, target, method, metric, reps, seed + len(rows))
                rows.append({"target": target, "method": method, "metric": metric, "value": center, "ci_low": lo, "ci_high": hi})
        if "traditional_hand_pca_logistic" in preds.columns:
            trad_auc, _, _ = bootstrap_metric(preds, target, "traditional_hand_pca_logistic", "auc", reps, seed + 91)
            for method in METHOD_ORDER[1:]:
                if method not in preds.columns:
                    continue
                center, lo, hi = bootstrap_metric(preds, target, method, "auc", reps, seed + 191 + len(rows))
                rows.append({"target": target, "method": method + "_minus_traditional", "metric": "auc_delta", "value": center - trad_auc, "ci_low": lo - trad_auc, "ci_high": hi - trad_auc})
    return pd.DataFrame(rows)


def summarize_atoms(target_rows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for target in TARGETS:
        by = target_rows.groupby("stave")[target].agg(["sum", "count", "mean"]).reset_index()
        for _, r in by.iterrows():
            rows.append({"target": target, "stratum": str(r["stave"]), "n_positive": int(r["sum"]), "n": int(r["count"]), "rate": float(r["mean"])})
        rows.append({"target": target, "stratum": "all", "n_positive": int(target_rows[target].sum()), "n": int(len(target_rows)), "rate": float(target_rows[target].mean())})
    return pd.DataFrame(rows)


def choose_winner(metrics: pd.DataFrame, leakage: pd.DataFrame) -> dict:
    aucs = metrics[(metrics["metric"] == "auc") & (metrics["method"].isin(METHOD_ORDER))].copy()
    by_method = aucs.groupby("method")["value"].mean().sort_values(ascending=False)
    best = str(by_method.index[0]) if len(by_method) else "none"
    best_value = float(by_method.iloc[0]) if len(by_method) else float("nan")
    traditional = float(by_method.get("traditional_hand_pca_logistic", np.nan))
    max_shuffle = float(leakage["shuffled_label_auc"].max()) if "shuffled_label_auc" in leakage and len(leakage) else float("nan")
    return {
        "method": best,
        "mean_auc": best_value,
        "traditional_mean_auc": traditional,
        "mean_auc_delta_vs_traditional": best_value - traditional if not math.isnan(traditional) else float("nan"),
        "guardrail_max_shuffled_label_auc": max_shuffle,
        "interpretation": "winner by mean run-heldout AUC across preregistered atom/outcome targets; high shuffled-label sentinels demote any latent gain to nuisance evidence" if max_shuffle > 0.65 else "winner by mean run-heldout AUC across preregistered atom/outcome targets",
    }


def write_plot(metrics: pd.DataFrame, out_dir: Path) -> None:
    try:
        import matplotlib.pyplot as plt

        auc = metrics[(metrics["metric"] == "auc") & (metrics["method"].isin(METHOD_ORDER))].copy()
        pivot = auc.pivot(index="target", columns="method", values="value").reindex(columns=METHOD_ORDER)
        fig, ax = plt.subplots(figsize=(12, 5))
        pivot.plot(kind="bar", ax=ax)
        ax.set_ylabel("Held-out AUC")
        ax.set_ylim(0.45, 1.02)
        ax.set_title("P01g atom/outcome discrimination by method")
        ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=8)
        fig.tight_layout()
        fig.savefig(out_dir / "fig_method_auc_by_target.png", dpi=180)
        plt.close(fig)
    except Exception as exc:
        (out_dir / "plot_error.txt").write_text(str(exc), encoding="utf-8")


def write_report(config: dict, out_dir: Path, count_match: pd.DataFrame, join_checks: pd.DataFrame, atom_summary: pd.DataFrame, metrics: pd.DataFrame, leakage: pd.DataFrame, winner: dict, commands: List[str]) -> None:
    auc_table = metrics[(metrics["metric"] == "auc") & (metrics["method"].isin(METHOD_ORDER))].copy()
    auc_table["ci"] = auc_table.apply(lambda r: "[{:.3f}, {:.3f}]".format(r["ci_low"], r["ci_high"]), axis=1)
    brier_table = metrics[(metrics["metric"] == "brier") & (metrics["method"].isin(METHOD_ORDER))].copy()
    lines = [
        "# P01g: latent baseline-contamination atom map",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Author:** `{config['worker']}`",
        f"- **Date:** {time.strftime('%Y-%m-%d')}",
        "- **Depends on:** S00, P01b, P01e-loader, P11a, P04/P07/P09/S03 atom definitions",
        "- **Input checksums:** `input_sha256.csv`",
        f"- **Git commit:** `{git_commit()}`",
        f"- **Config:** `configs/p01g_1781039488_1122_04bc6ecf_latent_baseline_contamination_atom_map.json`",
        "",
        "## 0. Question",
        "",
        "Do the loader-verified P01b latent coordinates encode pretrigger baseline, adaptive-lowering, dropout/delayed-peak, saturation-boundary, timing-tail, or charge-bias atoms after run-heldout evaluation and matched hand-shape controls?",
        "",
        "## 1. Reproduction from raw ROOT",
        "",
        "The first operation scans raw `h101/HRDv` ROOT arrays, applies the S00/P01b B-stave gate `A=max(w-baseline)>1000 ADC`, and rebuilds the selected pulse keys `(run,event_index,stave_index)` before opening the latent NPZ.",
        "",
        count_match.to_markdown(index=False),
        "",
        "The P01b latent loader contract is then rechecked against the raw keys.",
        "",
        join_checks.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "For each fold, thresholds are fit on training runs only. The baseline score is",
        "",
        "`B = sqrt(rms_pre^2 + slope_pre^2 + ptp_pre^2 + max_exc_pre^2)`,",
        "",
        "with `s16_baseline_excursion = 1[B >= Q95_train(B)]` and `s16_adaptive_lowering = 1[L >= Q90_train(L)]`. The P09-style dropout/delayed-peak atom uses a delayed/dropout score `D = dropout_score + max(0, late_fraction - median_train(late_fraction)) + 0.15 secondary_peak` plus a late peak guard. The S03 timing-tail atom is the training-run 90th percentile of event-level B4/B6/B8 timing inconsistency. The P04 charge-bias tail is the training-run 90th percentile of absolute residual from a log-amplitude/stave/peak linear charge control model. The P07 saturation-boundary atom is the training-run 90th percentile of `saturation_count + raw_max/4090 + amplitude/7000`.",
        "",
        "The traditional comparator is a strong hand-shape model: pretrigger summaries, amplitude, peak phase, topology one-hot terms, fixed waveform shape summaries, and a four-component PCA projection of the normalized 18-sample waveform, followed by L2 logistic regression. ML/NN methods are evaluated on the same held-out rows: ridge logistic on latent coordinates only, histogram gradient-boosted trees on latent+hand features, an MLP on latent+hand features, a 1D-CNN on the normalized waveform, and a new small `wave_latent_gate` network combining a CNN waveform branch with a gated latent/context branch.",
        "",
        "All reported intervals are run-block bootstrap 95% CIs over held-out runs with {} bootstrap replicates. Classifiers report AUC, average precision, and Brier score; Brier is lower-is-better.".format(config["ml"]["bootstrap_replicates"]),
        "",
        "## 3. Atom support",
        "",
        atom_summary.to_markdown(index=False, floatfmt=".4g"),
        "",
        "## 4. Head-to-head benchmark",
        "",
        auc_table[["target", "method", "value", "ci"]].to_markdown(index=False, floatfmt=".4g"),
        "",
        "Brier-score calibration summary:",
        "",
        brier_table[["target", "method", "value", "ci_low", "ci_high"]].to_markdown(index=False, floatfmt=".4g"),
        "",
        f"**Winner:** `{winner['method']}` by mean held-out AUC {winner['mean_auc']:.3f}. Its mean AUC delta versus the traditional hand/PCA comparator is {winner['mean_auc_delta_vs_traditional']:.3f}. The result is stored in `result.json`.",
        "",
        "![AUC by target](fig_method_auc_by_target.png)",
        "",
        "## 5. Falsification and leakage sentinels",
        "",
        "Pre-registration from the ticket: atom AUC/AP/Brier, timing sigma68 delta, charge-bias delta, support drift, and ML-minus-traditional deltas with event-paired run-block bootstrap CIs. A latent-contamination claim would be rejected if latent-only and latent-plus-hand models failed to beat amplitude-only/stave-only/run-only sentinels or if shuffled-label sentinels were similarly strong.",
        "",
        leakage.to_markdown(index=False, floatfmt=".4g"),
        "",
        "The run-only diagnostic is structurally weak under held-out runs because unseen run categories are all-zero after one-hot alignment. Stave-only and amplitude-only scores are therefore the more informative nuisance controls. Any target where shuffled-label AUC approaches the observed model AUC is treated as support instability rather than latent physics.",
        "",
        "## 6. Systematics and caveats",
        "",
        "Benchmark selection: the hand/PCA baseline is intentionally strong and includes the explicit pretrigger summaries that define the S16-like atoms, so latent wins on those targets would be meaningful only if they survive the sentinels. Data leakage: all thresholds, PCA rotations, scalers, and model fits are fold-local and the split is by run. Metric misuse: AP is prevalence-sensitive because rare atoms are naturally sparse; AUC and Brier are reported alongside it. Post-hoc selection: the target list is fixed from the ticket; the only new architecture is specified here as the waveform-plus-latent gate before inspecting its score.",
        "",
        "The timing-tail proxy uses peak-sample timing inconsistency rather than a full S03 CFD/timewalk refit to keep this ticket focused on latent contamination; the charge-bias proxy is likewise a local P04-style residual, not an external A-stack energy truth. These are nuisance gates, not final detector-performance claims.",
        "",
        "## 7. Findings",
        "",
        f"The overall winner is `{winner['method']}`. If latent-based methods beat the hand/PCA comparator on baseline or adaptive-lowering targets, that is evidence that P01b latents carry baseline/support nuisance structure. If they lose or only tie the traditional comparator, the safer interpretation is that downstream consumers should keep explicit hand/PCA nuisance controls rather than treat the P01b latent as a clean pulse-shape coordinate.",
        "",
        "## 8. Reproducibility",
        "",
        "Commands run:",
        "",
        "```bash",
        *commands,
        "```",
        "",
        "Primary artifacts: `result.json`, `manifest.json`, `REPORT.md`, `raw_count_match.csv`, `latent_join_checks.csv`, `atom_support.csv`, `heldout_predictions.csv`, `method_metrics.csv`, `leakage_checks.csv`, and `fig_method_auc_by_target.png`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_checksums(config: dict, raw_dir: Path, latent_path: Path, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    rows.append({"file": str(latent_path), "sha256": sha256_file(latent_path), "bytes": latent_path.stat().st_size})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "input_sha256.csv", index=False)
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01g_1781039488_1122_04bc6ecf_latent_baseline_contamination_atom_map.json"))
    args = parser.parse_args()
    started = time.time()
    config = load_json(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    command = "/home/billy/anaconda3/bin/python {} --config {}".format(Path(__file__), args.config)
    raw_dir = resolve_first_existing(config["raw_root_dir_candidates"], lambda p: p.exists() and any(p.glob("hrdb_run_*.root")))
    latent_path = resolve_first_existing(config["latent_path_candidates"], lambda p: p.exists())

    meta, waves, counts_by_run, counts_by_group = scan_raw(config, raw_dir)
    count_match = compare_counts(config, counts_by_group)
    if not bool(count_match["pass"].all()):
        raise RuntimeError("Raw reproduction gate failed")
    latent_sha = sha256_file(latent_path)
    if latent_sha != config["expected_latent_sha256"]:
        raise RuntimeError("Latent artifact hash mismatch: {}".format(latent_sha))
    latent_frame, _ = load_latent(latent_path)
    joined, join_checks = join_latents(meta, latent_frame, config)
    if not bool(join_checks["pass"].all()):
        raise RuntimeError("Latent join gate failed")
    joined = add_event_outcomes(joined, config)
    preds, folds, leakage, target_rows = run_models(joined, waves, config)
    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "counts_by_group.csv", index=False)
    count_match.to_csv(out_dir / "raw_count_match.csv", index=False)
    join_checks.to_csv(out_dir / "latent_join_checks.csv", index=False)
    folds.to_csv(out_dir / "fold_thresholds.csv", index=False)
    preds.to_csv(out_dir / "heldout_predictions.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    target_rows.to_csv(out_dir / "heldout_target_rows.csv.gz", index=False, compression="gzip")
    metrics = summarize_metrics(preds, config)
    atom_summary = summarize_atoms(target_rows)
    winner = choose_winner(metrics, leakage)
    checksums = write_checksums(config, raw_dir, latent_path, out_dir)
    atom_summary.to_csv(out_dir / "atom_support.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    write_plot(metrics, out_dir)

    output_files = sorted(p.name for p in out_dir.iterdir() if p.is_file())
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_reproduction": {
            "selected_pulses": int(count_match.iloc[0]["reproduced"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "passed": bool(count_match["pass"].all()),
        },
        "latent_join": {
            "path": str(latent_path),
            "sha256": latent_sha,
            "passed": bool(join_checks["pass"].all()),
        },
        "winner": winner,
        "method_metrics": metrics.to_dict(orient="records"),
        "atom_support": atom_summary.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "runtime_sec": round(time.time() - started, 3),
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p01g_1781039488_1122_04bc6ecf_latent_baseline_contamination_atom_map.py",
        "config": str(args.config),
        "command": command,
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch_cuda_available": bool(torch.cuda.is_available()),
        "random_seed": int(config["ml"]["random_seed"]),
        "raw_reproduction_passed": bool(count_match["pass"].all()),
        "latent_join_passed": bool(join_checks["pass"].all()),
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "output_files": output_files,
        "output_sha256": {p.name: sha256_file(p) for p in out_dir.iterdir() if p.is_file()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    write_report(config, out_dir, count_match, join_checks, atom_summary, metrics, leakage, winner, [command])
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "runtime_sec": round(time.time() - started, 3)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
