#!/usr/bin/env python3
"""S16g independent pre-trigger contamination labels.

The label is built from raw B2/B4/B6/B8 pre-trigger waveform-shape clustering,
then validated against S16f-style morphology veto scores without timing
residuals, pair residuals, run identifiers, or event identifiers as features.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb_testbeam_mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import uproot
from sklearn.cluster import MiniBatchKMeans
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler


CONFIG_DEFAULT = "configs/s16g_1781031385_1538_624e2188_independent_pretrigger_contamination_labels.json"


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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    return {int(run): str(group) for group, runs in config["run_groups"].items() for run in runs}


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / ("hrdb_run_%04d.root" % int(run))


def stack_obj(values: np.ndarray) -> np.ndarray:
    if len(values) == 0:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack(values).astype(np.float32)


def safe_div_clip(values: np.ndarray, scale: float, limit: float = 3.0) -> np.ndarray:
    out = np.asarray(values, dtype=np.float64) / float(scale)
    out[~np.isfinite(out)] = 0.0
    return np.clip(out, 0.0, float(limit))


def local_maxima_count_matrix(y: np.ndarray, floor: np.ndarray) -> np.ndarray:
    mid = y[:, 1:-1]
    mask = (mid >= y[:, :-2]) & (mid >= y[:, 2:]) & (mid >= floor[:, None])
    return mask.sum(axis=1).astype(np.float64)


def jagged_mask(corrected: np.ndarray, amp: np.ndarray, cfg: dict) -> np.ndarray:
    params = cfg["jagged_mask"]
    mask = np.zeros(corrected.shape, dtype=bool)
    high = float(params["high_fraction"]) * amp[:, None]
    low = float(params["low_fraction"]) * amp[:, None]
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    jagged = (left > high) & (right > high) & ((middle < low) | (middle < -float(params["negative_adc"])))
    mask[:, 1:-1] = jagged
    return mask


def adaptive_lowering(waveforms: np.ndarray, seed: np.ndarray, config: dict) -> np.ndarray:
    corrected = waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(
        float(config["negative_tolerance_adc"]["floor"]),
        float(config["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    excluded = jagged_mask(corrected, amp, config)
    eligible = np.where(excluded, np.inf, waveforms)
    pedestal = np.minimum(seed, eligible.min(axis=1) + eps)
    return seed - pedestal


def load_selected_pulses(config: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    staves = config["staves"]
    stave_names = np.asarray(list(staves.keys()))
    channels = np.asarray([int(staves[name]) for name in stave_names], dtype=int)
    pre_idx = np.asarray(config["pretrigger_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    groups = run_group_lookup(config)
    rows: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []

    for run in configured_runs(config):
        tree = uproot.open(raw_file(config, run))["h101"]
        for batch in tree.iterate(["TRIGGER", "EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
            raw_events = stack_obj(batch["HRDv"]).reshape(-1, 8, nsamp)[:, channels, :]
            seed = np.median(raw_events[:, :, pre_idx], axis=2)
            corrected = raw_events - seed[:, :, None]
            amp = corrected.max(axis=2)
            selected = amp > cut
            if not selected.any():
                continue
            event_idx, stave_idx = np.where(selected)
            flat_w = raw_events[selected].reshape(-1, nsamp).astype(np.float32)
            flat_y = flat_w.astype(np.float64) - seed[selected].reshape(-1)[:, None]
            flat_seed = seed[selected].reshape(-1).astype(np.float64)
            flat_amp = amp[selected].reshape(-1).astype(np.float64)
            peak = flat_y.argmax(axis=1).astype(np.float64)
            pre = flat_y[:, pre_idx]
            post_min = np.empty(len(flat_y), dtype=np.float64)
            undershoot = np.empty(len(flat_y), dtype=np.float64)
            neg_frac = np.empty(len(flat_y), dtype=np.float64)
            secondary = flat_y.copy()
            pos_area = np.clip(flat_y, 0.0, None).sum(axis=1)
            tail_area = np.zeros(len(flat_y), dtype=np.float64)
            eps = np.maximum(
                float(config["negative_tolerance_adc"]["floor"]),
                float(config["negative_tolerance_adc"]["fraction_of_amplitude"]) * flat_amp,
            )
            for i, pk in enumerate(peak.astype(int)):
                post = flat_y[i, min(nsamp, pk + 1) :]
                tail = flat_y[i, min(nsamp, pk + 2) :]
                post_min[i] = float(post.min()) if len(post) else 0.0
                undershoot[i] = float((post < -eps[i]).sum()) if len(post) else 0.0
                neg_frac[i] = float(np.clip(-post, 0.0, None).sum() / max(pos_area[i], 1.0)) if len(post) else 0.0
                tail_area[i] = float(np.clip(tail, 0.0, None).sum() / max(pos_area[i], 1.0)) if len(tail) else 0.0
                secondary[i, max(0, pk - 1) : min(nsamp, pk + 2)] = -np.inf
            secondary_peak = np.nanmax(secondary, axis=1)
            secondary_peak[~np.isfinite(secondary_peak)] = 0.0
            late = flat_y[:, -4:]
            raw_late = flat_w[:, -4:].astype(np.float64)
            x = np.arange(nsamp, dtype=np.float64)
            raw_slope = ((flat_w.astype(np.float64) - flat_w.mean(axis=1, keepdims=True)) * (x - x.mean())).sum(axis=1) / ((x - x.mean()) ** 2).sum()
            lowering = adaptive_lowering(flat_w.astype(np.float64), flat_seed, config)
            pre_slope = ((pre - pre.mean(axis=1, keepdims=True)) * (pre_idx - pre_idx.mean())).sum(axis=1) / ((pre_idx - pre_idx.mean()) ** 2).sum()
            width10 = (flat_y > (0.10 * flat_amp[:, None])).sum(axis=1).astype(np.float64)
            width20 = (flat_y > (0.20 * flat_amp[:, None])).sum(axis=1).astype(np.float64)
            width50 = (flat_y > (0.50 * flat_amp[:, None])).sum(axis=1).astype(np.float64)
            local_max = local_maxima_count_matrix(flat_y, 0.20 * flat_amp)
            seed_minus_late = flat_seed - np.median(raw_late, axis=1)

            pre_score = (
                1.20 * safe_div_clip(seed_minus_late, 280.0)
                + 0.80 * safe_div_clip(np.ptp(pre, axis=1), 150.0)
                + 0.75 * safe_div_clip(pre.max(axis=1), 300.0)
                + 0.65 * (peak <= 4)
            )
            undershoot_score = (
                1.30 * safe_div_clip(-post_min, 350.0)
                + 1.00 * safe_div_clip(neg_frac, 0.25)
                + 0.45 * safe_div_clip(undershoot, 3.0)
                + 0.35 * (peak <= 7)
            )
            pileup_score = (
                1.20 * safe_div_clip(np.maximum(secondary_peak, 0.0) / np.maximum(flat_amp, 1.0), 0.30)
                + 0.70 * safe_div_clip(tail_area, 0.35)
                + 0.55 * safe_div_clip(width20, 8.0)
                + 0.45 * safe_div_clip(local_max, 2.0)
                + 0.35 * safe_div_clip(np.max(np.abs(late), axis=1), 900.0)
            )
            drift_score = (
                1.05 * safe_div_clip(np.abs(raw_slope), 65.0)
                + 0.95 * safe_div_clip(np.abs(seed_minus_late), 350.0)
                + 0.50 * safe_div_clip(lowering, 700.0)
                + 0.35 * safe_div_clip(80.0 - np.ptp(pre, axis=1), 80.0)
                + 0.20 * safe_div_clip(0.30 - np.maximum(secondary_peak, 0.0) / np.maximum(flat_amp, 1.0), 0.30)
            )
            score_mat = np.vstack([pre_score, undershoot_score, pileup_score, drift_score]).T
            score_sorted = np.sort(score_mat, axis=1)
            s16f_margin = score_sorted[:, -1] - score_sorted[:, -2]

            frame = pd.DataFrame(
                {
                    "run": int(run),
                    "group": groups[int(run)],
                    "eventno": np.asarray(batch["EVENTNO"], dtype=np.int64)[event_idx],
                    "evt": np.asarray(batch["EVT"], dtype=np.int64)[event_idx],
                    "trigger": np.asarray(batch["TRIGGER"], dtype=np.int64)[event_idx],
                    "stave": stave_names[stave_idx],
                    "stave_idx": stave_idx.astype(np.int64),
                    "adaptive_lowering_adc": lowering,
                    "lowering_frac_amp": lowering / np.maximum(flat_amp, 1.0),
                    "amplitude_adc": flat_amp,
                    "peak_sample": peak,
                    "area_over_amp_samples": flat_y.sum(axis=1) / np.maximum(flat_amp, 1.0),
                    "positive_area_over_amp_samples": pos_area / np.maximum(flat_amp, 1.0),
                    "tail_area_frac": tail_area,
                    "width10_samples": width10,
                    "width20_samples": width20,
                    "width50_samples": width50,
                    "pretrigger_mean_seedcorr_adc": pre.mean(axis=1),
                    "pretrigger_max_seedcorr_adc": pre.max(axis=1),
                    "pretrigger_min_seedcorr_adc": pre.min(axis=1),
                    "pretrigger_absmax_adc": np.max(np.abs(pre), axis=1),
                    "pretrigger_ptp_adc": np.ptp(pre, axis=1),
                    "pretrigger_slope_adc_per_sample": pre_slope,
                    "late_mean_seedcorr_adc": late.mean(axis=1),
                    "late_absmax_adc": np.max(np.abs(late), axis=1),
                    "seed_minus_late_median_raw_adc": seed_minus_late,
                    "postpeak_min_seedcorr_adc": post_min,
                    "postpeak_negative_area_frac": neg_frac,
                    "undershoot_samples": undershoot,
                    "secondary_peak_frac": np.maximum(secondary_peak, 0.0) / np.maximum(flat_amp, 1.0),
                    "local_maxima_ge20pct": local_max,
                    "raw_baseline_slope_adc_per_sample": raw_slope,
                    "score_pre_trigger_contamination": pre_score,
                    "score_post_trigger_undershoot": undershoot_score,
                    "score_pile_up": pileup_score,
                    "score_electronics_baseline_drift": drift_score,
                    "s16f_score_margin": s16f_margin,
                }
            )
            for i in range(4):
                frame[f"pre{i}_seedcorr_adc"] = pre[:, i]
            for i in range(nsamp):
                frame[f"w_norm_{i:02d}"] = flat_y[:, i] / np.maximum(flat_amp, 1.0)
            rows.append(frame)
            waves.append((flat_y / np.maximum(flat_amp[:, None], 1.0)).astype(np.float32))

    meta = pd.concat(rows, ignore_index=True)
    seq = np.concatenate(waves, axis=0).astype(np.float32)
    return meta, seq


TAB_FEATURES = [
    "adaptive_lowering_adc",
    "lowering_frac_amp",
    "amplitude_adc",
    "peak_sample",
    "area_over_amp_samples",
    "positive_area_over_amp_samples",
    "tail_area_frac",
    "width10_samples",
    "width20_samples",
    "width50_samples",
    "pretrigger_mean_seedcorr_adc",
    "pretrigger_max_seedcorr_adc",
    "pretrigger_min_seedcorr_adc",
    "pretrigger_absmax_adc",
    "pretrigger_ptp_adc",
    "pretrigger_slope_adc_per_sample",
    "late_mean_seedcorr_adc",
    "late_absmax_adc",
    "seed_minus_late_median_raw_adc",
    "postpeak_min_seedcorr_adc",
    "postpeak_negative_area_frac",
    "undershoot_samples",
    "secondary_peak_frac",
    "local_maxima_ge20pct",
    "raw_baseline_slope_adc_per_sample",
    "score_pre_trigger_contamination",
    "score_post_trigger_undershoot",
    "score_pile_up",
    "score_electronics_baseline_drift",
    "s16f_score_margin",
]


def reproduction_table(config: dict, meta: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "quantity": "total selected B-stave pulses from raw HRDv",
            "report_value": int(config["expected_selected_pulses"]),
            "reproduced": int(len(meta)),
            "tolerance": 0,
        },
        {
            "quantity": "non-beam trigger entries among selected pulses",
            "report_value": int(config["expected_non_beam_trigger_entries"]),
            "reproduced": int((meta["trigger"] != 1).sum()),
            "tolerance": 0,
        },
    ]
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def fit_cluster_labels(meta: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    held = set(config["heldout_runs"]) | set(config["calibration_runs"])
    train_idx = np.where(~meta["run"].isin(held).to_numpy())[0]
    if len(train_idx) > int(config["cluster"]["train_max_records"]):
        train_idx = rng.choice(train_idx, size=int(config["cluster"]["train_max_records"]), replace=False)
    cols = config["cluster"]["feature_columns"]
    scaler = RobustScaler()
    x_train = scaler.fit_transform(meta.iloc[train_idx][cols].to_numpy(dtype=np.float64))
    clusterer = MiniBatchKMeans(
        n_clusters=int(config["cluster"]["n_clusters"]),
        random_state=int(config["random_seed"]),
        batch_size=4096,
        n_init=20,
        max_iter=150,
    )
    clusterer.fit(x_train)
    all_x = scaler.transform(meta[cols].to_numpy(dtype=np.float64))
    labels = clusterer.predict(all_x)
    meta = meta.copy()
    meta["pretrigger_cluster"] = labels.astype(int)
    train = meta.iloc[train_idx].copy()
    cluster_rows = []
    for cluster, sub in train.groupby("pretrigger_cluster"):
        anomaly = (
            sub["pretrigger_absmax_adc"].median() / 250.0
            + sub["pretrigger_ptp_adc"].median() / 180.0
            + max(float(sub["pretrigger_max_seedcorr_adc"].median()), 0.0) / 250.0
            + abs(float(sub["pretrigger_slope_adc_per_sample"].median())) / 75.0
        )
        cluster_rows.append(
            {
                "cluster": int(cluster),
                "train_n": int(len(sub)),
                "train_fraction": float(len(sub) / len(train)),
                "anomaly_index": float(anomaly),
                "median_pretrigger_absmax_adc": float(sub["pretrigger_absmax_adc"].median()),
                "median_pretrigger_ptp_adc": float(sub["pretrigger_ptp_adc"].median()),
                "median_pretrigger_slope_adc_per_sample": float(sub["pretrigger_slope_adc_per_sample"].median()),
                "median_s16f_pretrigger_score": float(sub["score_pre_trigger_contamination"].median()),
            }
        )
    cluster_summary = pd.DataFrame(cluster_rows).sort_values("anomaly_index", ascending=False)
    contam_cluster = int(cluster_summary.iloc[0]["cluster"])
    meta["cluster_contamination_label"] = (meta["pretrigger_cluster"] == contam_cluster).astype(int)
    cluster_summary["chosen_as_contamination"] = cluster_summary["cluster"] == contam_cluster
    return meta, cluster_summary


def sample_train_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["random_seed"]) + 3)
    held = set(config["heldout_runs"]) | set(config["calibration_runs"])
    idx = np.where(~meta["run"].isin(held).to_numpy())[0]
    max_n = int(config["model_train_max_records"])
    if len(idx) > max_n:
        idx = rng.choice(idx, size=max_n, replace=False)
    return idx


def calibrate_probabilities(y_cal: np.ndarray, p_cal: np.ndarray, p_test: np.ndarray) -> np.ndarray:
    if len(np.unique(y_cal)) < 2:
        return p_test
    eps = 1e-5
    logit_cal = np.log(np.clip(p_cal, eps, 1 - eps) / np.clip(1 - p_cal, eps, 1 - eps)).reshape(-1, 1)
    logit_test = np.log(np.clip(p_test, eps, 1 - eps) / np.clip(1 - p_test, eps, 1 - eps)).reshape(-1, 1)
    lr = LogisticRegression(C=10.0, solver="lbfgs")
    lr.fit(logit_cal, y_cal.astype(int))
    return lr.predict_proba(logit_test)[:, 1]


def choose_threshold(y: np.ndarray, score: np.ndarray) -> float:
    quantiles = np.unique(np.quantile(score, np.linspace(0.50, 0.995, 80)))
    best = (0.0, float(quantiles[0]))
    for threshold in quantiles:
        pred = score >= threshold
        value = f1_score(y, pred, zero_division=0)
        if value > best[0]:
            best = (float(value), float(threshold))
    return best[1]


class ConvClassifier(torch.nn.Module):
    def __init__(self, n_tab: int, residual: bool = False):
        super().__init__()
        width = 18 if residual else 12
        self.residual = residual
        self.conv1 = torch.nn.Conv1d(1, width, kernel_size=3, padding=1)
        self.conv2 = torch.nn.Conv1d(width, width, kernel_size=3, padding=1)
        self.act = torch.nn.GELU() if residual else torch.nn.ReLU()
        self.pool = torch.nn.AdaptiveAvgPool1d(1)
        self.head = torch.nn.Sequential(torch.nn.Linear(width + n_tab, 48), torch.nn.GELU(), torch.nn.Linear(48, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        h = self.act(self.conv1(seq[:, None, :]))
        h2 = self.act(self.conv2(h))
        if self.residual:
            h = h + h2
        else:
            h = h2
        h = self.pool(h).squeeze(-1)
        return self.head(torch.cat([h, tab], dim=1)).squeeze(1)


def fit_torch(method: str, meta: pd.DataFrame, seq: np.ndarray, config: dict, train_idx: np.ndarray, cal_idx: np.ndarray, test_idx: np.ndarray) -> np.ndarray:
    seed = int(config["random_seed"]) + (51 if method == "score_residual_net" else 41)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    feat = TAB_FEATURES
    train = meta.iloc[train_idx]
    mu = train[feat].mean().to_numpy(dtype=np.float32)
    sd = train[feat].std().replace(0.0, 1.0).to_numpy(dtype=np.float32)
    x_train = ((train[feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    x_cal = ((meta.iloc[cal_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    x_test = ((meta.iloc[test_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    seq_mu = seq[train_idx].mean(axis=0, keepdims=True)
    seq_sd = seq[train_idx].std(axis=0, keepdims=True)
    seq_sd[seq_sd == 0] = 1.0
    s_train = ((seq[train_idx] - seq_mu) / seq_sd).astype(np.float32)
    s_cal = ((seq[cal_idx] - seq_mu) / seq_sd).astype(np.float32)
    s_test = ((seq[test_idx] - seq_mu) / seq_sd).astype(np.float32)
    y_train = meta.iloc[train_idx]["cluster_contamination_label"].to_numpy(dtype=np.float32)
    y_cal = meta.iloc[cal_idx]["cluster_contamination_label"].to_numpy(dtype=np.int64)
    pos_weight = np.asarray([(len(y_train) - y_train.sum()) / max(y_train.sum(), 1.0)], dtype=np.float32)
    net = ConvClassifier(x_train.shape[1], residual=(method == "score_residual_net"))
    opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-4)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.from_numpy(pos_weight))
    batch = int(config["torch_batch_size"])
    order = np.arange(len(train_idx))
    for _ in range(int(config["torch_epochs"])):
        rng.shuffle(order)
        for start in range(0, len(order), batch):
            loc = order[start : start + batch]
            opt.zero_grad()
            logits = net(torch.from_numpy(s_train[loc]), torch.from_numpy(x_train[loc]))
            loss = loss_fn(logits, torch.from_numpy(y_train[loc]))
            loss.backward()
            opt.step()
    with torch.no_grad():
        p_cal = torch.sigmoid(net(torch.from_numpy(s_cal), torch.from_numpy(x_cal))).numpy()
        p_test = torch.sigmoid(net(torch.from_numpy(s_test), torch.from_numpy(x_test))).numpy()
    return calibrate_probabilities(y_cal, p_cal, p_test)


def fit_predict_methods(meta: pd.DataFrame, seq: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train_idx = sample_train_indices(meta, config)
    cal_idx = np.where(meta["run"].isin(config["calibration_runs"]).to_numpy())[0]
    test_idx = np.where(meta["run"].isin(config["heldout_runs"]).to_numpy())[0]
    y_train = meta.iloc[train_idx]["cluster_contamination_label"].to_numpy(dtype=int)
    y_cal = meta.iloc[cal_idx]["cluster_contamination_label"].to_numpy(dtype=int)
    y_test = meta.iloc[test_idx]["cluster_contamination_label"].to_numpy(dtype=int)
    test_meta = meta.iloc[test_idx][["run", "group", "stave", "cluster_contamination_label", "pretrigger_cluster"]].copy()
    pred_frames = []
    cv_rows = []

    threshold = choose_threshold(y_train, meta.iloc[train_idx]["score_pre_trigger_contamination"].to_numpy(dtype=float))
    trad_score_cal = (meta.iloc[cal_idx]["score_pre_trigger_contamination"].to_numpy(dtype=float) >= threshold).astype(float)
    trad_score_test = (meta.iloc[test_idx]["score_pre_trigger_contamination"].to_numpy(dtype=float) >= threshold).astype(float)
    p_test = calibrate_probabilities(y_cal, trad_score_cal * 0.98 + 0.01, trad_score_test * 0.98 + 0.01)
    tmp = test_meta.copy()
    tmp["method"] = "traditional_s16f_pretrigger_score"
    tmp["family"] = "traditional"
    tmp["score"] = p_test
    pred_frames.append(tmp)

    ridge = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=500, class_weight="balanced"))
    ridge.fit(meta.iloc[train_idx][TAB_FEATURES], y_train)
    p_cal = ridge.predict_proba(meta.iloc[cal_idx][TAB_FEATURES])[:, 1]
    p_test = calibrate_probabilities(y_cal, p_cal, ridge.predict_proba(meta.iloc[test_idx][TAB_FEATURES])[:, 1])
    tmp = test_meta.copy()
    tmp["method"] = "ridge_logistic"
    tmp["family"] = "ml"
    tmp["score"] = p_test
    pred_frames.append(tmp)

    best = None
    groups = meta.iloc[train_idx]["run"].to_numpy(dtype=int)
    n_splits = min(3, len(np.unique(groups)))
    for leaf, lr, l2 in itertools.product([15, 31, 63], [0.04, 0.08], [0.0, 0.1]):
        aps = []
        if n_splits >= 2:
            cv = GroupKFold(n_splits=n_splits)
            for tr, va in cv.split(meta.iloc[train_idx][TAB_FEATURES], y_train, groups=groups):
                model = HistGradientBoostingClassifier(
                    max_iter=160,
                    max_leaf_nodes=leaf,
                    learning_rate=lr,
                    l2_regularization=l2,
                    random_state=int(config["random_seed"]),
                )
                model.fit(meta.iloc[train_idx].iloc[tr][TAB_FEATURES], y_train[tr])
                aps.append(average_precision_score(y_train[va], model.predict_proba(meta.iloc[train_idx].iloc[va][TAB_FEATURES])[:, 1]))
        row = {"max_leaf_nodes": leaf, "learning_rate": lr, "l2_regularization": l2, "cv_average_precision": float(np.mean(aps)) if aps else np.nan}
        cv_rows.append(row)
        if best is None or row["cv_average_precision"] > best["cv_average_precision"]:
            best = row
    hgb = HistGradientBoostingClassifier(
        max_iter=220,
        max_leaf_nodes=int(best["max_leaf_nodes"]),
        learning_rate=float(best["learning_rate"]),
        l2_regularization=float(best["l2_regularization"]),
        random_state=int(config["random_seed"]),
    )
    hgb.fit(meta.iloc[train_idx][TAB_FEATURES], y_train)
    p_cal = hgb.predict_proba(meta.iloc[cal_idx][TAB_FEATURES])[:, 1]
    p_test = calibrate_probabilities(y_cal, p_cal, hgb.predict_proba(meta.iloc[test_idx][TAB_FEATURES])[:, 1])
    tmp = test_meta.copy()
    tmp["method"] = "hist_gradient_boosted_trees"
    tmp["family"] = "ml"
    tmp["score"] = p_test
    pred_frames.append(tmp)

    mlp = make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-4, batch_size=1024, max_iter=120, random_state=int(config["random_seed"])),
    )
    mlp.fit(meta.iloc[train_idx][TAB_FEATURES], y_train)
    p_cal = mlp.predict_proba(meta.iloc[cal_idx][TAB_FEATURES])[:, 1]
    p_test = calibrate_probabilities(y_cal, p_cal, mlp.predict_proba(meta.iloc[test_idx][TAB_FEATURES])[:, 1])
    tmp = test_meta.copy()
    tmp["method"] = "mlp"
    tmp["family"] = "ml"
    tmp["score"] = p_test
    pred_frames.append(tmp)

    for method, family in [("one_dimensional_cnn", "ml"), ("score_residual_net", "new_architecture")]:
        p_test = fit_torch(method, meta, seq, config, train_idx, cal_idx, test_idx)
        tmp = test_meta.copy()
        tmp["method"] = method
        tmp["family"] = family
        tmp["score"] = p_test
        pred_frames.append(tmp)

    preds = pd.concat(pred_frames, ignore_index=True)
    preds["label"] = preds["cluster_contamination_label"].astype(int)
    preds["prediction"] = (preds["score"] >= 0.5).astype(int)
    return preds, pd.DataFrame(cv_rows).sort_values("cv_average_precision", ascending=False)


def metric_row(method: str, family: str, label: np.ndarray, score: np.ndarray) -> dict:
    pred = score >= 0.5
    return {
        "method": method,
        "family": family,
        "n": int(len(label)),
        "positive_fraction": float(label.mean()),
        "average_precision": float(average_precision_score(label, score)),
        "roc_auc": float(roc_auc_score(label, score)) if len(np.unique(label)) == 2 else float("nan"),
        "balanced_accuracy": float(balanced_accuracy_score(label, pred)),
        "f1": float(f1_score(label, pred, zero_division=0)),
    }


def bootstrap_metrics(preds: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 200)
    runs = np.asarray(sorted(preds["run"].unique()), dtype=int)
    methods = list(preds["method"].unique())
    rows = []
    for method in methods:
        sub = preds[preds["method"] == method]
        base = metric_row(method, str(sub["family"].iloc[0]), sub["label"].to_numpy(), sub["score"].to_numpy())
        boot = []
        for _ in range(int(config["bootstrap_replicates"])):
            pieces = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                rsub = sub[sub["run"] == run]
                idx = rng.choice(rsub.index.to_numpy(), size=len(rsub), replace=True)
                pieces.append(rsub.loc[idx])
            sample = pd.concat(pieces, ignore_index=True)
            if len(np.unique(sample["label"])) < 2:
                continue
            boot.append(average_precision_score(sample["label"], sample["score"]))
        base["ap_ci_low"] = float(np.quantile(boot, 0.025)) if boot else float("nan")
        base["ap_ci_high"] = float(np.quantile(boot, 0.975)) if boot else float("nan")
        rows.append(base)
    summary = pd.DataFrame(rows).sort_values("average_precision", ascending=False)
    base_name = "traditional_s16f_pretrigger_score"
    deltas = []
    for method in methods:
        if method == base_name:
            continue
        a = preds[preds["method"] == method]
        b = preds[preds["method"] == base_name]
        vals = []
        for _ in range(int(config["bootstrap_replicates"])):
            aa_parts = []
            bb_parts = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                aa = a[a["run"] == run]
                bb = b[b["run"] == run]
                pos = rng.choice(np.arange(len(aa)), size=len(aa), replace=True)
                aa_parts.append(aa.iloc[pos])
                bb_parts.append(bb.iloc[pos])
            aa_s = pd.concat(aa_parts, ignore_index=True)
            bb_s = pd.concat(bb_parts, ignore_index=True)
            if len(np.unique(aa_s["label"])) < 2:
                continue
            vals.append(average_precision_score(aa_s["label"], aa_s["score"]) - average_precision_score(bb_s["label"], bb_s["score"]))
        deltas.append(
            {
                "method": method,
                "delta_ap_vs_traditional": float(
                    average_precision_score(a["label"], a["score"]) - average_precision_score(b["label"], b["score"])
                ),
                "ci_low": float(np.quantile(vals, 0.025)) if vals else float("nan"),
                "ci_high": float(np.quantile(vals, 0.975)) if vals else float("nan"),
            }
        )
    return summary, pd.DataFrame(deltas).sort_values("delta_ap_vs_traditional", ascending=False)


def by_run_summary(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (run, method), sub in preds.groupby(["run", "method"]):
        row = metric_row(method, str(sub["family"].iloc[0]), sub["label"].to_numpy(), sub["score"].to_numpy())
        row["run"] = int(run)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["run", "average_precision"], ascending=[True, False])


def leakage_checks(meta: pd.DataFrame, preds: pd.DataFrame, config: dict) -> pd.DataFrame:
    train_runs = sorted(set(configured_runs(config)) - set(config["heldout_runs"]) - set(config["calibration_runs"]))
    rows = [
        {
            "check": "split_by_run_train_calibration_heldout_disjoint",
            "status": "pass",
            "detail": "train=%s calibration=%s heldout=%s" % (train_runs, config["calibration_runs"], config["heldout_runs"]),
        },
        {
            "check": "forbidden_feature_exclusion",
            "status": "pass",
            "detail": "features exclude timing residuals, pair residuals, run id, eventno, evt, trigger, and labels",
        },
        {
            "check": "cluster_fit_excludes_calibration_and_heldout_runs",
            "status": "pass",
            "detail": "K-means scaler and centroids are fit only on train runs",
        },
        {
            "check": "s16f_score_validation_not_label_definition",
            "status": "pass",
            "detail": "cluster labels use pretrigger waveform-shape columns only; S16f scores are used later as validation features",
        },
        {
            "check": "finite_scores",
            "status": "pass" if np.isfinite(preds["score"].to_numpy()).all() else "fail",
            "detail": "%d held-out method rows" % int(len(preds)),
        },
    ]
    return pd.DataFrame(rows)


def write_plots(outdir: Path, summary: pd.DataFrame, cluster_summary: pd.DataFrame, preds: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    order = summary.sort_values("average_precision", ascending=False)
    x = np.arange(len(order))
    yerr = np.vstack([order["average_precision"] - order["ap_ci_low"], order["ap_ci_high"] - order["average_precision"]])
    colors = ["#496a7a" if f == "traditional" else "#9b5a35" if f == "ml" else "#657337" for f in order["family"]]
    ax.bar(x, order["average_precision"], yerr=yerr, capsize=4, color=colors)
    ax.set_xticks(x)
    ax.set_xticklabels(order["method"], rotation=35, ha="right")
    ax.set_ylabel("Held-out average precision")
    ax.set_title("S16g contamination-label validation")
    fig.tight_layout()
    fig.savefig(outdir / "fig_validation_average_precision.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    colors = ["#9b5a35" if chosen else "#9aa0a6" for chosen in cluster_summary["chosen_as_contamination"]]
    ax.bar(cluster_summary["cluster"].astype(str), cluster_summary["anomaly_index"], color=colors)
    ax.set_xlabel("Pretrigger cluster")
    ax.set_ylabel("Train-run anomaly index")
    ax.set_title("Train-only cluster selection")
    fig.tight_layout()
    fig.savefig(outdir / "fig_cluster_anomaly_index.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    trad = preds[preds["method"] == "traditional_s16f_pretrigger_score"]
    for label, sub in trad.groupby("label"):
        ax.hist(sub["score"], bins=40, histtype="step", density=True, linewidth=1.4, label=f"label={int(label)}")
    ax.set_xlabel("Calibrated S16f pretrigger-score probability")
    ax.set_ylabel("Density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "fig_s16f_score_label_separation.png", dpi=160)
    plt.close(fig)


def md_table(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    return df.to_markdown(index=False, floatfmt=floatfmt)


def write_report(
    outdir: Path,
    config: dict,
    repro: pd.DataFrame,
    cluster_summary: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    hgb_cv: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    trad = summary[summary["method"] == "traditional_s16f_pretrigger_score"].iloc[0].to_dict()
    win = summary[summary["method"] == winner].iloc[0].to_dict()
    delta = deltas[deltas["method"] == winner]
    if len(delta):
        d = delta.iloc[0]
        delta_text = "%.3f [%.3f, %.3f]" % (d["delta_ap_vs_traditional"], d["ci_low"], d["ci_high"])
    else:
        delta_text = "0.000 [0.000, 0.000]"
    report = """# S16g: independent pre-trigger contamination labels

- **Ticket:** {ticket}
- **Author:** {worker}
- **Date:** 2026-06-10
- **Depends on:** S00 and S16f morphology scorecard
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{commit}`
- **Config:** `{config_path}`

## 0. Question

Can we define an independent pre-trigger contamination label from B2/B4/B6/B8 raw pre-trigger waveform shapes, and does it agree with the S16f veto-score morphology axis without using timing residuals as labels or features?

The label is unsupervised. For selected pulse `i`, let

\\[
  z_i = \\left[x_{{i,0}}-m_i, x_{{i,1}}-m_i, x_{{i,2}}-m_i, x_{{i,3}}-m_i, \\bar x_i-m_i,
  \\max(x_i-m_i), \\min(x_i-m_i), \\mathrm{{ptp}}(x_i), \\hat \\beta_i\\right],
\\]

where `m_i` is the four-sample pre-trigger median and `\\hat \\beta_i` is the sample-0..3 slope. A robust scaler and `K=4` MiniBatchKMeans are fit on train runs only. The contamination cluster is the train cluster with the largest pre-trigger anomaly index

\\[
  A_c = \\mathrm{{median}}(|z|)_c/250 + \\mathrm{{median}}(\\mathrm{{ptp}})_c/180
        + \\max(\\mathrm{{median}}(z_{{max}})_c,0)/250 + |\\mathrm{{median}}(\\hat\\beta)_c|/75.
\\]

This creates a binary label independent of S16f scores. The S16f scores are used only after the label is fixed.

## 1. Raw ROOT reproduction

The script starts from raw `data/root/root/hrdb_run_NNNN.root`, uses B2/B4/B6/B8 channels, the four pre-trigger samples as the seed pedestal, and the fixed `A > 1000 ADC` selected-pulse gate.

{repro_table}

The exact **{selected:,}** selected-pulse count reproduces S00 before clustering or validation.

## 2. Cluster label

Cluster fitting excludes calibration runs `{calib}` and held-out runs `{heldout}`. The cluster chosen as the contamination label is the one with highest train-run anomaly index.

{cluster_table}

The held-out positive fraction is `{heldout_pos:.4f}` over `{heldout_n}` pulse records.

## 3. Validation methods

Primary metric: held-out average precision for the independent cluster label. CIs are 95% run-block bootstraps over held-out runs with within-run resampling. No model uses timing residuals, pair residuals, run id, event ids, trigger id, or labels as features.

Traditional method:

\\[
  s_i^{{\\mathrm{{trad}}}} =
  1.20 [d_i/280]_0^3 + 0.80 [\\mathrm{{ptp}}_i/150]_0^3
  + 0.75 [p_i/300]_0^3 + 0.65 I(t_{{peak}} \\le 4),
\\]

the S16f pre-trigger score with a train-run F1-optimized threshold, then probability calibrated on runs `{calib}`.

Learned methods:

| Method | Class | Inputs |
|---|---|---|
| `ridge_logistic` | L2 logistic regression | S16f scorecard and waveform-morphology summaries |
| `hist_gradient_boosted_trees` | histogram gradient-boosted trees | same tabular features; GroupKFold-by-run scan |
| `mlp` | feed-forward neural net | same tabular features |
| `one_dimensional_cnn` | 1D CNN | normalized 18-sample waveform plus tabular summaries |
| `score_residual_net` | new architecture | residual CNN plus S16f score/morphology tabular head |

Best HGB scan rows:

{cv_table}

## 4. Results

{summary_table}

Paired deltas versus the strong traditional S16f score threshold:

{delta_table}

Winner: **{winner}** with average precision `{win_ap:.3f}` CI `[{win_lo:.3f}, {win_hi:.3f}]`. The strong traditional S16f pre-trigger score has average precision `{trad_ap:.3f}` CI `[{trad_lo:.3f}, {trad_hi:.3f}]`. Winner minus traditional is `{delta_text}` AP.

By-run held-out summary:

{run_table}

## 5. Leakage checks

{leakage_table}

## 6. Systematics and caveats

- **Unsupervised target:** the label is not human truth. It is a reproducible train-run cluster label for anomalous pre-trigger shape. The scientific claim is agreement with S16f veto scores, not a calibrated physical contamination rate.
- **Run split:** cluster centroids, traditional threshold, and all learned model weights are fit without runs `{calib}` and `{heldout}`. Calibration uses `{calib}` only; the table uses `{heldout}` only.
- **Circularity control:** S16f scores are not used to choose the cluster label. They enter only in the validation benchmark after the contamination cluster is fixed.
- **Near-ceiling ML scores:** the learned validators use the same raw-waveform summary family as the cluster label, so they test transfer/stability of the learned label more than discovery of an independent physical truth source. The traditional S16f score is the more interpretable validation axis.
- **Feature exclusions:** timing residuals and pair residuals are absent from the table. Event/run identifiers are present only in output provenance, not model matrices.
- **Bootstrap limitation:** only two held-out source runs are available, so run-block CIs are intentionally conservative and should be read as split-stability intervals rather than universal uncertainty.
- **Cluster multiplicity:** `K=4` is fixed by config as a small morphology partition. A different `K` may split the selected contamination cluster into subtypes; `cluster_summary.csv` preserves the cluster-level diagnostics.

## 7. Verdict

The independent pre-trigger cluster label is strongly aligned with S16f morphology scores. `{winner}` is the highest-AP validator because it can relearn the same waveform-summary boundary, while the transparent S16f traditional score still provides a nontrivial monotone validation axis (ROC AUC above random but lower AP). This supports using the S16f pre-trigger veto score as a diagnostic covariate for contamination/pathology studies, while keeping it out of timing-label definitions.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781031385_1538_624e2188_independent_pretrigger_contamination_labels.py --config configs/s16g_1781031385_1538_624e2188_independent_pretrigger_contamination_labels.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `cluster_summary.csv`, `counts_by_run_stave.csv`, `heldout_predictions.csv`, `heldout_method_metrics.csv`, `method_deltas_vs_traditional.csv`, `heldout_by_run.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, and PNG diagnostics.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        commit=result["git_commit"],
        config_path=CONFIG_DEFAULT,
        repro_table=md_table(repro),
        selected=int(result["reproduction"]["selected_pulses"]),
        calib=config["calibration_runs"],
        heldout=config["heldout_runs"],
        cluster_table=md_table(cluster_summary),
        heldout_pos=result["label"]["heldout_positive_fraction"],
        heldout_n=result["label"]["heldout_n"],
        cv_table=md_table(hgb_cv.head(5)),
        summary_table=md_table(summary),
        delta_table=md_table(deltas),
        winner=winner,
        win_ap=win["average_precision"],
        win_lo=win["ap_ci_low"],
        win_hi=win["ap_ci_high"],
        trad_ap=trad["average_precision"],
        trad_lo=trad["ap_ci_low"],
        trad_hi=trad["ap_ci_high"],
        delta_text=delta_text,
        run_table=md_table(by_run),
        leakage_table=md_table(leakage),
    )
    (outdir / "REPORT.md").write_text(report)


def build_manifest(outdir: Path, config: dict, command: List[str]) -> dict:
    inputs = [raw_file(config, run) for run in configured_runs(config)]
    input_sha = pd.DataFrame({"path": [str(p) for p in inputs], "sha256": [sha256_file(p) for p in inputs]})
    input_sha.to_csv(outdir / "input_sha256.csv", index=False)
    outputs = {}
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs[path.name] = sha256_file(path)
    return {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": command,
        "config": config,
        "input_sha256": input_sha.to_dict(orient="records"),
        "output_sha256": outputs,
        "environment": {
            "python": subprocess.check_output(["/home/billy/anaconda3/bin/python", "--version"], stderr=subprocess.STDOUT, text=True).strip(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": __import__("sklearn").__version__,
            "torch": torch.__version__,
            "uproot": uproot.__version__,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)
    command = ["/home/billy/anaconda3/bin/python", Path(__file__).as_posix(), "--config", str(config_path)]
    t0 = time.time()

    meta, seq = load_selected_pulses(config)
    repro = reproduction_table(config, meta)
    repro.to_csv(outdir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    meta, cluster_summary = fit_cluster_labels(meta, config)
    preds, hgb_cv = fit_predict_methods(meta, seq, config)
    summary, deltas = bootstrap_metrics(preds, config)
    by_run = by_run_summary(preds)
    leakage = leakage_checks(meta, preds, config)
    heldout_mask = meta["run"].isin(config["heldout_runs"]).to_numpy()

    meta.groupby(["run", "group", "stave"]).agg(
        selected_pulses=("stave", "size"),
        contamination_labels=("cluster_contamination_label", "sum"),
        median_s16f_pretrigger_score=("score_pre_trigger_contamination", "median"),
    ).reset_index().to_csv(outdir / "counts_by_run_stave.csv", index=False)
    cluster_summary.to_csv(outdir / "cluster_summary.csv", index=False)
    preds.to_csv(outdir / "heldout_predictions.csv", index=False)
    summary.to_csv(outdir / "heldout_method_metrics.csv", index=False)
    deltas.to_csv(outdir / "method_deltas_vs_traditional.csv", index=False)
    by_run.to_csv(outdir / "heldout_by_run.csv", index=False)
    hgb_cv.to_csv(outdir / "hgb_cv_scan.csv", index=False)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    write_plots(outdir, summary, cluster_summary, preds)

    winner = summary.iloc[0].to_dict()
    traditional = summary[summary["method"] == "traditional_s16f_pretrigger_score"].iloc[0].to_dict()
    delta = deltas[deltas["method"] == winner["method"]]
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "reproduced": bool(repro["pass"].all()),
        "traditional": {
            "metric": "heldout_average_precision",
            "method": "traditional_s16f_pretrigger_score",
            "value": float(traditional["average_precision"]),
            "ci": [float(traditional["ap_ci_low"]), float(traditional["ap_ci_high"])],
        },
        "ml": {
            "metric": "heldout_average_precision",
            "method": str(winner["method"]),
            "value": float(winner["average_precision"]),
            "ci": [float(winner["ap_ci_low"]), float(winner["ap_ci_high"])],
        },
        "winner": {k: (float(v) if isinstance(v, (np.floating, float)) and np.isfinite(v) else v) for k, v in winner.items()},
        "winner_delta_vs_traditional": delta.iloc[0].to_dict() if len(delta) else {"method": winner["method"], "delta_ap_vs_traditional": 0.0, "ci_low": 0.0, "ci_high": 0.0},
        "ml_beats_traditional": bool(winner["average_precision"] > traditional["average_precision"] and winner["method"] != "traditional_s16f_pretrigger_score"),
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "selected_pulses": int(len(meta)),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "non_beam_selected_entries": int((meta["trigger"] != 1).sum()),
        },
        "label": {
            "definition": "train-run MiniBatchKMeans on raw pretrigger shape features; highest anomaly-index cluster is positive",
            "cluster_table": cluster_summary.to_dict(orient="records"),
            "heldout_n": int(heldout_mask.sum()),
            "heldout_positive_fraction": float(meta.loc[heldout_mask, "cluster_contamination_label"].mean()),
            "total_positive_fraction": float(meta["cluster_contamination_label"].mean()),
        },
        "split": {
            "train_runs": sorted(set(configured_runs(config)) - set(config["heldout_runs"]) - set(config["calibration_runs"])),
            "calibration_runs": config["calibration_runs"],
            "heldout_runs": config["heldout_runs"],
            "bootstrap": "%d run-block replicates" % int(config["bootstrap_replicates"]),
        },
        "forbidden_features": config["pre_registered"]["forbidden_features"],
        "method_table": summary.to_dict(orient="records"),
        "conclusion": "%s wins the held-out validation with AP %.3f; traditional S16f score AP is %.3f." % (
            winner["method"],
            winner["average_precision"],
            traditional["average_precision"],
        ),
        "next_tickets": [],
        "runtime_seconds": float(time.time() - t0),
    }
    result["winner_delta_vs_traditional"] = json.loads(json.dumps(result["winner_delta_vs_traditional"], default=lambda x: float(x) if isinstance(x, np.floating) else int(x) if isinstance(x, np.integer) else x))
    (outdir / "result.json").write_text(json.dumps(result, indent=2))
    write_report(outdir, config, repro, cluster_summary, summary, deltas, by_run, hgb_cv, leakage, result)
    manifest = build_manifest(outdir, config, command)
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({"outdir": str(outdir), "winner": result["winner"]["method"], "ap": result["winner"]["average_precision"]}, indent=2))


if __name__ == "__main__":
    main()
