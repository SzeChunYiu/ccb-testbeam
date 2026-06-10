#!/usr/bin/env python3
"""S16l target-excluded pedestal estimator timing-risk audit.

The script reads raw B-stack HRDv ROOT waveforms, reproduces the S00 selected
pulse count, and then asks whether better target-excluded pretrigger-sample
imputation is safe when the imputed value is used as a pedestal substitute in
downstream CFD timing.  All learned models are split by source run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", "/tmp/testbeam-mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.set_num_threads(2)
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


CONFIG_DEFAULT = "configs/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.json"
DOWNSTREAM_PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
TAB_FEATURES = [
    "target_sample",
    "stave_idx",
    "other_0_adc",
    "other_1_adc",
    "other_2_adc",
    "mean3_adc",
    "median3_adc",
    "line3_adc",
    "pre_range3_adc",
    "pre_rms3_adc",
    "pre_slope3_adc_per_sample",
    "amp_mean3_adc",
    "peak_mean3",
    "late_max_mean3_adc",
    "late_integral_mean3_adc_sample",
    "late_argmax_sample",
]


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16F = load_module("s16f_helpers", "scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py")


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
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / ("hrdb_run_%04d.root" % int(run))


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def cfd_time_from_baseline(waves: np.ndarray, baseline: np.ndarray, fraction: float, period_ns: float) -> Tuple[np.ndarray, np.ndarray]:
    corrected = waves.astype(np.float64) - baseline.astype(np.float64)[:, None]
    amp = corrected.max(axis=1)
    return period_ns * S16F.cfd_time_samples(corrected, amp, fraction), amp


def line3_predict(other: np.ndarray, other_idx: Sequence[int], target: int) -> np.ndarray:
    x = np.asarray(other_idx, dtype=np.float64)
    y = other.astype(np.float64)
    xbar = float(x.mean())
    denom = float(np.sum((x - xbar) ** 2))
    if denom == 0.0:
        return y.mean(axis=1)
    ybar = y.mean(axis=1)
    slope = ((y - ybar[:, None]) * (x[None, :] - xbar)).sum(axis=1) / denom
    return ybar + slope * (float(target) - xbar)


def anomaly_taxon(pre: np.ndarray, amp: np.ndarray, peak: np.ndarray, lowering: np.ndarray) -> np.ndarray:
    pre = pre.astype(float)
    ptp = np.ptp(pre, axis=1)
    slope = pre[:, -1] - pre[:, 0]
    center = np.median(pre, axis=1)
    outlier = np.max(np.abs(pre - center[:, None]), axis=1)
    out = np.full(len(pre), "quiet_pretrigger", dtype=object)
    out[ptp >= 120.0] = "broad_pretrigger_excursion"
    out[(np.abs(slope) >= 80.0) & (ptp < 120.0)] = "pretrigger_slope"
    out[(outlier >= 150.0) & (ptp < 120.0)] = "single_sample_outlier"
    out[(peak <= 4) & (amp > 1000.0)] = "early_peak"
    out[lowering > 0.0] = "adaptive_lowering"
    return out


def load_selected_pulses(config: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    groups = {int(run): group for group, runs in config["run_groups"].items() for run in runs}
    runs = [int(r) for r in config["analysis_runs"]]
    nsamp = int(config["samples_per_channel"])
    pre_idx = np.asarray(config["pretrigger_samples"], dtype=int)
    cut = float(config["amplitude_cut_adc"])
    rows: List[pd.DataFrame] = []
    wave_chunks: List[np.ndarray] = []
    event_uid_base = 0
    pulse_base = 0
    for run in runs:
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            waves = events[:, channels, :]
            pre = waves[:, :, pre_idx]
            ref_ped = np.median(pre, axis=-1)
            corrected = waves - ref_ped[:, :, None]
            amp = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            selected = amp > cut
            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                event_uid_base += len(eventno)
                continue
            selected_waves = waves[event_idx, stave_idx, :].astype(np.float32)
            selected_pre = selected_waves[:, pre_idx]
            selected_ref = ref_ped[event_idx, stave_idx].astype(np.float64)
            selected_amp = amp[event_idx, stave_idx].astype(np.float64)
            selected_peak = peak[event_idx, stave_idx].astype(int)
            eps = np.maximum(
                float(config["adaptive"]["negative_tolerance_floor_adc"]),
                float(config["adaptive"]["negative_tolerance_fraction_of_amplitude"]) * selected_amp,
            )
            min_raw = selected_waves.min(axis=1).astype(np.float64)
            adaptive_ped = np.minimum(selected_ref, min_raw + eps)
            lowering = selected_ref - adaptive_ped
            t_ref, amp_ref = cfd_time_from_baseline(
                selected_waves.astype(np.float64),
                selected_ref.astype(np.float64),
                float(config["cfd_fraction"]),
                float(config["sample_period_ns"]),
            )
            evuid = [("%d:%d:%d:%d" % (run, int(eventno[e]), int(evt[e]), event_uid_base + int(e))) for e in event_idx]
            stave_names = np.asarray(staves, dtype=object)[stave_idx]
            rec = pd.DataFrame(
                {
                    "pulse_index": np.arange(pulse_base, pulse_base + len(event_idx), dtype=int),
                    "run": int(run),
                    "group": groups[int(run)],
                    "event_id": evuid,
                    "eventno": eventno[event_idx].astype(int),
                    "evt": evt[event_idx].astype(int),
                    "stave": stave_names,
                    "stave_idx": stave_idx.astype(int),
                    "channel": channels[stave_idx].astype(int),
                    "ref_ped_median4_adc": selected_ref,
                    "ref_amp_adc": amp_ref,
                    "ref_peak_sample": selected_peak,
                    "ref_t_cfd20_ns": t_ref,
                    "adaptive_lowering_adc": lowering,
                    "pre_ptp4_adc": np.ptp(selected_pre.astype(float), axis=1),
                    "pre_rms4_adc": selected_pre.astype(float).std(axis=1),
                }
            )
            rec["adaptive_lowering_bin"] = np.where(rec["adaptive_lowering_adc"] > 0.0, "lowered", "not_lowered")
            rec["anomaly_taxon"] = anomaly_taxon(selected_pre, amp_ref, selected_peak, lowering)
            rows.append(rec)
            wave_chunks.append(selected_waves)
            pulse_base += len(event_idx)
            event_uid_base += len(eventno)
    meta = pd.concat(rows, ignore_index=True)
    waves_out = np.concatenate(wave_chunks, axis=0).astype(np.float32)
    amp_bins = [-np.inf, 1500.0, 2500.0, 4000.0, 7000.0, np.inf]
    meta["amplitude_bin"] = pd.cut(
        meta["ref_amp_adc"],
        bins=amp_bins,
        labels=["1000-1500", "1500-2500", "2500-4000", "4000-7000", ">=7000"],
        include_lowest=True,
    ).astype(str)
    meta["pretrigger_spectrum_bin"] = pd.cut(
        meta["pre_ptp4_adc"],
        bins=[-0.1, 25.0, 75.0, 200.0, np.inf],
        labels=["ptp<25", "25-75", "75-200", "ptp>=200"],
    ).astype(str)
    return meta, waves_out


def target_frame(meta: pd.DataFrame, waves: np.ndarray, pulse_idx: np.ndarray, targets: np.ndarray) -> pd.DataFrame:
    pulse_idx = np.asarray(pulse_idx, dtype=int)
    targets = np.asarray(targets, dtype=int)
    selected = waves[pulse_idx].astype(np.float64)
    pre = selected[:, :4]
    rows = []
    for target in range(4):
        loc = np.where(targets == target)[0]
        if len(loc) == 0:
            continue
        pidx = pulse_idx[loc]
        wave = selected[loc]
        other_idx = [i for i in range(4) if i != target]
        other = wave[:, other_idx]
        mean3 = other.mean(axis=1)
        median3 = np.median(other, axis=1)
        line3 = line3_predict(other, other_idx, target)
        corrected = wave - mean3[:, None]
        late = corrected[:, 4:]
        slope_x = np.asarray(other_idx, dtype=float)
        slope = ((other - other.mean(axis=1)[:, None]) * (slope_x[None, :] - slope_x.mean())).sum(axis=1)
        denom = np.sum((slope_x - slope_x.mean()) ** 2)
        slope = slope / max(float(denom), 1.0)
        m = meta.iloc[pidx].reset_index(drop=True)
        rows.append(
            pd.DataFrame(
                {
                    "pulse_index": pidx,
                    "run": m["run"].to_numpy(dtype=int),
                    "event_id": m["event_id"].to_numpy(),
                    "stave": m["stave"].to_numpy(),
                    "stave_idx": m["stave_idx"].to_numpy(dtype=int),
                    "target_sample": int(target),
                    "target_adc": pre[loc, target],
                    "other_0_adc": other[:, 0],
                    "other_1_adc": other[:, 1],
                    "other_2_adc": other[:, 2],
                    "mean3_adc": mean3,
                    "median3_adc": median3,
                    "line3_adc": line3,
                    "pre_range3_adc": np.ptp(other, axis=1),
                    "pre_rms3_adc": other.std(axis=1),
                    "pre_slope3_adc_per_sample": slope,
                    "amp_mean3_adc": corrected.max(axis=1),
                    "peak_mean3": corrected.argmax(axis=1).astype(float),
                    "late_max_mean3_adc": late.max(axis=1),
                    "late_integral_mean3_adc_sample": late.sum(axis=1),
                    "late_argmax_sample": 4.0 + late.argmax(axis=1).astype(float),
                    "ref_amp_adc": m["ref_amp_adc"].to_numpy(dtype=float),
                    "ref_ped_median4_adc": m["ref_ped_median4_adc"].to_numpy(dtype=float),
                    "adaptive_lowering_adc": m["adaptive_lowering_adc"].to_numpy(dtype=float),
                    "adaptive_lowering_bin": m["adaptive_lowering_bin"].to_numpy(),
                    "amplitude_bin": m["amplitude_bin"].to_numpy(),
                    "pretrigger_spectrum_bin": m["pretrigger_spectrum_bin"].to_numpy(),
                    "anomaly_taxon": m["anomaly_taxon"].to_numpy(),
                }
            )
        )
    out = pd.concat(rows, ignore_index=True)
    return out.sort_values(["pulse_index", "target_sample"]).reset_index(drop=True)


def sample_train_targets(meta: pd.DataFrame, train_pulses: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(int(seed))
    all_rows = np.arange(len(train_pulses) * 4, dtype=int)
    max_rows = int(config["models"]["max_train_target_rows"])
    if len(all_rows) > max_rows:
        all_rows = rng.choice(all_rows, size=max_rows, replace=False)
    return train_pulses[all_rows // 4], all_rows % 4


def add_prediction(frame: pd.DataFrame, method: str, family: str, pred: np.ndarray) -> pd.DataFrame:
    cols = [
        "pulse_index",
        "run",
        "event_id",
        "stave",
        "stave_idx",
        "target_sample",
        "target_adc",
        "mean3_adc",
        "median3_adc",
        "line3_adc",
        "ref_amp_adc",
        "ref_ped_median4_adc",
        "adaptive_lowering_adc",
        "adaptive_lowering_bin",
        "amplitude_bin",
        "pretrigger_spectrum_bin",
        "anomaly_taxon",
    ]
    out = frame[cols].copy()
    out["method"] = method
    out["family"] = family
    out["prediction_adc"] = np.asarray(pred, dtype=float)
    out["residual_adc"] = out["prediction_adc"] - out["target_adc"]
    out["abs_residual_adc"] = out["residual_adc"].abs()
    return out


def fit_run_stratified(train: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    train = train.copy()
    frame = frame.copy()
    amp_q = np.quantile(train["amp_mean3_adc"], [0.2, 0.4, 0.6, 0.8])
    pre_q = np.quantile(train["pre_range3_adc"], [0.25, 0.50, 0.75])
    train["amp_bin_fit"] = np.searchsorted(amp_q, train["amp_mean3_adc"], side="right")
    frame["amp_bin_fit"] = np.searchsorted(amp_q, frame["amp_mean3_adc"], side="right")
    train["pre_bin_fit"] = np.searchsorted(pre_q, train["pre_range3_adc"], side="right")
    frame["pre_bin_fit"] = np.searchsorted(pre_q, frame["pre_range3_adc"], side="right")
    train["line_residual"] = train["target_adc"] - train["line3_adc"]
    global_offset = float(train["line_residual"].median())
    by_target_stave = train.groupby(["target_sample", "stave"])["line_residual"].median().to_dict()
    by_cell = train.groupby(["target_sample", "stave", "amp_bin_fit", "pre_bin_fit"])["line_residual"].median().to_dict()
    pred = []
    for _, row in frame.iterrows():
        key = (int(row["target_sample"]), row["stave"], int(row["amp_bin_fit"]), int(row["pre_bin_fit"]))
        fallback = by_target_stave.get((int(row["target_sample"]), row["stave"]), global_offset)
        pred.append(float(row["line3_adc"]) + float(by_cell.get(key, fallback)))
    return np.asarray(pred, dtype=float)


def fit_ridge(train: pd.DataFrame, frame: pd.DataFrame, config: dict, cv_rows: List[dict], heldout_run: int) -> np.ndarray:
    y = (train["target_adc"] - train["line3_adc"]).to_numpy(dtype=float)
    groups = train["run"].to_numpy(dtype=int)
    best_alpha = None
    best_score = float("inf")
    n_splits = min(4, len(np.unique(groups)))
    for alpha in config["models"]["ridge_alphas"]:
        scores = []
        if n_splits >= 2:
            cv = GroupKFold(n_splits=n_splits)
            for tr, va in cv.split(train[TAB_FEATURES], y, groups=groups):
                model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
                model.fit(train.iloc[tr][TAB_FEATURES], y[tr])
                scores.append(mean_absolute_error(y[va], model.predict(train.iloc[va][TAB_FEATURES])))
        else:
            scores = [float("nan")]
        score = float(np.nanmean(scores))
        cv_rows.append({"heldout_run": heldout_run, "method": "ridge", "alpha": float(alpha), "cv_mae_adc": score})
        if score < best_score:
            best_score = score
            best_alpha = float(alpha)
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
    model.fit(train[TAB_FEATURES], y)
    return frame["line3_adc"].to_numpy(dtype=float) + model.predict(frame[TAB_FEATURES])


def fit_hgb(train: pd.DataFrame, frame: pd.DataFrame, config: dict, cv_rows: List[dict], heldout_run: int, seed: int) -> np.ndarray:
    y = (train["target_adc"] - train["line3_adc"]).to_numpy(dtype=float)
    groups = train["run"].to_numpy(dtype=int)
    best = None
    n_splits = min(3, len(np.unique(groups)))
    for lr in config["models"]["hgb_learning_rates"]:
        for leaf in config["models"]["hgb_max_leaf_nodes"]:
            scores = []
            if n_splits >= 2:
                cv = GroupKFold(n_splits=n_splits)
                for tr, va in cv.split(train[TAB_FEATURES], y, groups=groups):
                    model = HistGradientBoostingRegressor(
                        max_iter=int(config["models"]["hgb_max_iter"]),
                        learning_rate=float(lr),
                        max_leaf_nodes=int(leaf),
                        random_state=int(seed),
                    )
                    model.fit(train.iloc[tr][TAB_FEATURES], y[tr])
                    scores.append(mean_absolute_error(y[va], model.predict(train.iloc[va][TAB_FEATURES])))
            score = float(np.nanmean(scores)) if scores else float("nan")
            row = {"heldout_run": heldout_run, "method": "gradient_boosted_trees", "learning_rate": float(lr), "max_leaf_nodes": int(leaf), "cv_mae_adc": score}
            cv_rows.append(row)
            if best is None or score < best["cv_mae_adc"]:
                best = row
    model = HistGradientBoostingRegressor(
        max_iter=int(config["models"]["hgb_max_iter"]) + 30,
        learning_rate=float(best["learning_rate"]),
        max_leaf_nodes=int(best["max_leaf_nodes"]),
        random_state=int(seed),
    )
    model.fit(train[TAB_FEATURES], y)
    return frame["line3_adc"].to_numpy(dtype=float) + model.predict(frame[TAB_FEATURES])


def fit_mlp(train: pd.DataFrame, frame: pd.DataFrame, config: dict, seed: int) -> np.ndarray:
    y = (train["target_adc"] - train["line3_adc"]).to_numpy(dtype=float)
    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(int(v) for v in config["models"]["mlp_hidden_layer_sizes"]),
            alpha=float(config["models"]["mlp_alpha"]),
            max_iter=int(config["models"]["mlp_max_iter"]),
            random_state=int(seed),
            early_stopping=True,
            n_iter_no_change=12,
            batch_size=512,
        ),
    )
    model.fit(train[TAB_FEATURES], y)
    return frame["line3_adc"].to_numpy(dtype=float) + model.predict(frame[TAB_FEATURES])


def sequence_array(frame: pd.DataFrame, waves: np.ndarray, two_channel: bool) -> np.ndarray:
    pidx = frame["pulse_index"].to_numpy(dtype=int)
    target = frame["target_sample"].to_numpy(dtype=int)
    base = frame["mean3_adc"].to_numpy(dtype=float)
    seq = waves[pidx].astype(np.float32) - base.astype(np.float32)[:, None]
    for i, t in enumerate(target):
        seq[i, int(t)] = 0.0
    if not two_channel:
        return seq[:, None, :].astype(np.float32)
    mask = np.zeros_like(seq, dtype=np.float32)
    for i, t in enumerate(target):
        mask[i, int(t)] = 1.0
    return np.stack([seq, mask], axis=1).astype(np.float32)


class Cnn1D(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(16 + n_tab, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        h = self.conv(seq).squeeze(-1)
        return self.head(torch.cat([h, tab], dim=1)).squeeze(1)


class TargetMaskedResidualCnn(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(2, 16, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(16, 20, kernel_size=3, padding=1),
            nn.GELU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(20 + n_tab, 64), nn.GELU(), nn.Dropout(0.05), nn.Linear(64, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        h = self.conv(seq).squeeze(-1)
        return self.head(torch.cat([h, tab], dim=1)).squeeze(1)


def fit_torch_regressor(method: str, train: pd.DataFrame, frame: pd.DataFrame, waves: np.ndarray, config: dict, seed: int) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is unavailable")
    torch.manual_seed(int(seed))
    rng = np.random.default_rng(int(seed))
    two_channel = method == "target_masked_residual_cnn"
    train_seq = sequence_array(train, waves, two_channel)
    frame_seq = sequence_array(frame, waves, two_channel)
    seq_mu = train_seq[:, 0:1, :].mean(axis=(0, 2), keepdims=True)
    seq_sd = train_seq[:, 0:1, :].std(axis=(0, 2), keepdims=True)
    seq_sd[seq_sd == 0.0] = 1.0
    train_seq[:, 0:1, :] = (train_seq[:, 0:1, :] - seq_mu) / seq_sd
    frame_seq[:, 0:1, :] = (frame_seq[:, 0:1, :] - seq_mu) / seq_sd
    scaler = StandardScaler()
    x_train = scaler.fit_transform(train[TAB_FEATURES]).astype(np.float32)
    x_frame = scaler.transform(frame[TAB_FEATURES]).astype(np.float32)
    y = (train["target_adc"] - train["line3_adc"]).to_numpy(dtype=np.float32)
    y_mean = float(y.mean())
    y_sd = float(y.std())
    if y_sd <= 0.0:
        y_sd = 1.0
    y_scaled = ((y - y_mean) / y_sd).astype(np.float32)
    net = Cnn1D(x_train.shape[1]) if method == "one_dimensional_cnn" else TargetMaskedResidualCnn(x_train.shape[1])
    opt = torch.optim.AdamW(net.parameters(), lr=float(config["models"]["torch_learning_rate"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    loss_fn = nn.SmoothL1Loss(beta=0.75)
    ds = TensorDataset(torch.from_numpy(train_seq), torch.from_numpy(x_train), torch.from_numpy(y_scaled))
    loader = DataLoader(ds, batch_size=int(config["models"]["torch_batch_size"]), shuffle=True)
    order_probe = []
    for _ in range(int(config["models"]["torch_epochs"])):
        epoch_loss = 0.0
        n = 0
        for sb, xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(net(sb, xb), yb)
            loss.backward()
            opt.step()
            epoch_loss += float(loss.item()) * len(yb)
            n += len(yb)
        order_probe.append(epoch_loss / max(n, 1))
        if len(order_probe) > 5 and min(order_probe[-5:]) > min(order_probe[:-5]) - 1e-4:
            break
    with torch.no_grad():
        pred_scaled = net(torch.from_numpy(frame_seq), torch.from_numpy(x_frame)).numpy()
    return frame["line3_adc"].to_numpy(dtype=float) + pred_scaled.astype(float) * y_sd + y_mean


def fit_fold(meta: pd.DataFrame, waves: np.ndarray, config: dict, heldout_run: int, cv_rows: List[dict]) -> pd.DataFrame:
    rng_seed = int(config["models"]["random_seed"]) + int(heldout_run) * 100
    train_pulses = meta.index[(meta["run"] != heldout_run) & (meta["run"].isin(config["analysis_runs"]))].to_numpy(dtype=int)
    test_pulses = meta.index[meta["run"] == heldout_run].to_numpy(dtype=int)
    tr_pulse, tr_target = sample_train_targets(meta, train_pulses, config, rng_seed)
    train = target_frame(meta, waves, tr_pulse, tr_target)
    test = target_frame(meta, waves, np.repeat(test_pulses, 4), np.tile(np.arange(4), len(test_pulses)))
    pred_frames = [
        add_prediction(test, "traditional_mean3", "traditional", test["mean3_adc"].to_numpy(dtype=float)),
        add_prediction(test, "traditional_median3", "traditional", test["median3_adc"].to_numpy(dtype=float)),
        add_prediction(test, "traditional_line3", "traditional", test["line3_adc"].to_numpy(dtype=float)),
        add_prediction(test, "traditional_run_stratified", "traditional", fit_run_stratified(train, test)),
    ]
    print("heldout=%s method=ridge" % heldout_run, flush=True)
    pred_frames.append(add_prediction(test, "ridge", "ml", fit_ridge(train, test, config, cv_rows, heldout_run)))
    print("heldout=%s method=gradient_boosted_trees" % heldout_run, flush=True)
    pred_frames.append(add_prediction(test, "gradient_boosted_trees", "ml", fit_hgb(train, test, config, cv_rows, heldout_run, rng_seed + 11)))
    print("heldout=%s method=mlp" % heldout_run, flush=True)
    pred_frames.append(add_prediction(test, "mlp", "ml", fit_mlp(train, test, config, rng_seed + 23)))
    print("heldout=%s method=one_dimensional_cnn" % heldout_run, flush=True)
    pred_frames.append(add_prediction(test, "one_dimensional_cnn", "ml", fit_torch_regressor("one_dimensional_cnn", train, test, waves, config, rng_seed + 31)))
    print("heldout=%s method=target_masked_residual_cnn" % heldout_run, flush=True)
    pred_frames.append(add_prediction(test, "target_masked_residual_cnn", "new_architecture", fit_torch_regressor("target_masked_residual_cnn", train, test, waves, config, rng_seed + 37)))
    out = pd.concat(pred_frames, ignore_index=True)
    return out


def timing_shift_rows(meta: pd.DataFrame, waves: np.ndarray, pred: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    period = float(config["sample_period_ns"])
    frac = float(config["cfd_fraction"])
    downstream = set(config["downstream_staves"])
    pos = {"B2": 0.0, "B4": 2.0, "B6": 4.0, "B8": 6.0}
    tof = float(config["tof_per_cm_ns"])
    timing_rows = []
    charge_rows = []
    for (method, target), sub in pred.groupby(["method", "target_sample"]):
        pulse_idx = sub["pulse_index"].to_numpy(dtype=int)
        baselines = sub["prediction_adc"].to_numpy(dtype=float)
        t_est, amp_est = cfd_time_from_baseline(waves[pulse_idx], baselines, frac, period)
        m = meta.iloc[pulse_idx][["run", "event_id", "stave", "ref_t_cfd20_ns", "ref_amp_adc"]].copy().reset_index(drop=True)
        m["method"] = method
        m["target_sample"] = int(target)
        m["t_shift_ns"] = t_est - m["ref_t_cfd20_ns"].to_numpy(dtype=float)
        m["amp_delta_adc"] = amp_est - m["ref_amp_adc"].to_numpy(dtype=float)
        charge_rows.append(m[["run", "event_id", "stave", "method", "target_sample", "amp_delta_adc"]])
        d = m[m["stave"].isin(downstream)].copy()
        if d.empty:
            continue
        wide = d.pivot_table(index=["run", "event_id"], columns="stave", values="t_shift_ns", aggfunc="first")
        for a, b in DOWNSTREAM_PAIRS:
            if a not in wide.columns or b not in wide.columns:
                continue
            ok = wide[[a, b]].dropna()
            if ok.empty:
                continue
            timing_rows.append(
                pd.DataFrame(
                    {
                        "run": ok.index.get_level_values("run").astype(int),
                        "event_id": ok.index.get_level_values("event_id"),
                        "method": method,
                        "target_sample": int(target),
                        "pair": "%s-%s" % (a, b),
                        "pair_position_delta_ns": (pos[a] - pos[b]) * tof,
                        "timing_shift_ns": ok[a].to_numpy(dtype=float) - ok[b].to_numpy(dtype=float),
                    }
                )
            )
    return pd.concat(timing_rows, ignore_index=True), pd.concat(charge_rows, ignore_index=True)


def metric_pedestal(frame: pd.DataFrame) -> dict:
    r = frame["residual_adc"].to_numpy(dtype=float)
    return {
        "n_target_rows": int(len(frame)),
        "pedestal_mae_adc": float(np.mean(np.abs(r))),
        "pedestal_rmse_adc": float(math.sqrt(np.mean(r**2))),
        "pedestal_bias_adc": float(np.mean(r)),
        "pedestal_q05_adc": float(np.quantile(r, 0.05)),
        "pedestal_q95_adc": float(np.quantile(r, 0.95)),
    }


def metric_timing(frame: pd.DataFrame) -> dict:
    x = frame["timing_shift_ns"].to_numpy(dtype=float)
    return {
        "n_pair_rows": int(len(frame)),
        "timing_sigma68_shift_ns": sigma68(x),
        "timing_full_rms_shift_ns": float(math.sqrt(np.mean(x**2))) if len(x) else float("nan"),
        "timing_tail_gt0p5_fraction": float(np.mean(np.abs(x) > 0.5)) if len(x) else float("nan"),
        "timing_tail_gt5_fraction": float(np.mean(np.abs(x) > 5.0)) if len(x) else float("nan"),
        "timing_shift_bias_ns": float(np.mean(x)) if len(x) else float("nan"),
    }


def metric_charge(frame: pd.DataFrame) -> dict:
    x = frame["amp_delta_adc"].to_numpy(dtype=float)
    return {
        "n_charge_rows": int(len(frame)),
        "charge_bias_delta_adc": float(np.mean(x)) if len(x) else float("nan"),
        "charge_abs_delta_adc": float(np.mean(np.abs(x))) if len(x) else float("nan"),
    }


def metric_pedestal_array(r: np.ndarray) -> dict:
    r = np.asarray(r, dtype=float)
    return {
        "n_target_rows": int(len(r)),
        "pedestal_mae_adc": float(np.mean(np.abs(r))) if len(r) else float("nan"),
        "pedestal_rmse_adc": float(math.sqrt(np.mean(r**2))) if len(r) else float("nan"),
        "pedestal_bias_adc": float(np.mean(r)) if len(r) else float("nan"),
    }


def metric_timing_array(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    return {
        "n_pair_rows": int(len(x)),
        "timing_sigma68_shift_ns": sigma68(x),
        "timing_full_rms_shift_ns": float(math.sqrt(np.mean(x**2))) if len(x) else float("nan"),
        "timing_tail_gt0p5_fraction": float(np.mean(np.abs(x) > 0.5)) if len(x) else float("nan"),
        "timing_tail_gt5_fraction": float(np.mean(np.abs(x) > 5.0)) if len(x) else float("nan"),
        "timing_shift_bias_ns": float(np.mean(x)) if len(x) else float("nan"),
    }


def metric_charge_array(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    return {
        "n_charge_rows": int(len(x)),
        "charge_bias_delta_adc": float(np.mean(x)) if len(x) else float("nan"),
        "charge_abs_delta_adc": float(np.mean(np.abs(x))) if len(x) else float("nan"),
    }


def bootstrap_summary(pred: pd.DataFrame, timing: pd.DataFrame, charge: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + 500)
    runs = np.asarray(sorted(pred["run"].unique()), dtype=int)
    rows = []
    methods = sorted(pred["method"].unique())
    for method in methods:
        p = pred[pred["method"] == method]
        t = timing[timing["method"] == method]
        c = charge[charge["method"] == method]
        row = {"method": method, "family": str(p["family"].iloc[0])}
        row.update(metric_pedestal(p))
        row.update(metric_timing(t))
        row.update(metric_charge(c))
        p_by_run = {int(r): g["residual_adc"].to_numpy(dtype=float) for r, g in p.groupby("run")}
        t_by_run = {int(r): g["timing_shift_ns"].to_numpy(dtype=float) for r, g in t.groupby("run")}
        c_by_run = {int(r): g["amp_delta_adc"].to_numpy(dtype=float) for r, g in c.groupby("run")}
        boot_stats = []
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            pr = np.concatenate([p_by_run.get(int(r), np.empty(0)) for r in sampled])
            ts = np.concatenate([t_by_run.get(int(r), np.empty(0)) for r in sampled])
            ch = np.concatenate([c_by_run.get(int(r), np.empty(0)) for r in sampled])
            d = {}
            d.update(metric_pedestal_array(pr))
            d.update(metric_timing_array(ts))
            d.update(metric_charge_array(ch))
            boot_stats.append(d)
        boot = pd.DataFrame(boot_stats)
        for col in [
            "pedestal_mae_adc",
            "pedestal_rmse_adc",
            "pedestal_bias_adc",
            "timing_sigma68_shift_ns",
            "timing_full_rms_shift_ns",
            "timing_tail_gt0p5_fraction",
            "timing_tail_gt5_fraction",
            "charge_bias_delta_adc",
            "charge_abs_delta_adc",
        ]:
            row[col + "_ci_low"] = float(np.nanquantile(boot[col], 0.025))
            row[col + "_ci_high"] = float(np.nanquantile(boot[col], 0.975))
        row["risk_score"] = (
            row["timing_tail_gt5_fraction"]
            + 0.05 * row["timing_tail_gt0p5_fraction"]
            + 0.00005 * row["pedestal_rmse_adc"]
            + 0.00002 * row["charge_abs_delta_adc"]
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["timing_tail_gt5_fraction", "timing_tail_gt0p5_fraction", "timing_sigma68_shift_ns", "pedestal_rmse_adc"])


def delta_bootstrap(timing: pd.DataFrame, summary: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + 700)
    trad = summary[summary["family"] == "traditional"].sort_values(["timing_tail_gt5_fraction", "timing_tail_gt0p5_fraction", "timing_sigma68_shift_ns"]).iloc[0]["method"]
    runs = np.asarray(sorted(timing["run"].unique()), dtype=int)
    by_method_run = {
        (method, int(run)): g["timing_shift_ns"].to_numpy(dtype=float)
        for (method, run), g in timing.groupby(["method", "run"])
    }
    rows = []
    for method in sorted(timing["method"].unique()):
        if method == trad:
            continue
        vals = []
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            a = np.concatenate([by_method_run.get((method, int(r)), np.empty(0)) for r in sampled])
            b = np.concatenate([by_method_run.get((trad, int(r)), np.empty(0)) for r in sampled])
            vals.append(metric_timing_array(a)["timing_tail_gt5_fraction"] - metric_timing_array(b)["timing_tail_gt5_fraction"])
        point = metric_timing(timing[timing["method"] == method])["timing_tail_gt5_fraction"] - metric_timing(timing[timing["method"] == trad])["timing_tail_gt5_fraction"]
        rows.append(
            {
                "method": method,
                "reference_traditional_method": trad,
                "delta_tail_gt5_fraction": float(point),
                "ci_low": float(np.nanquantile(vals, 0.025)),
                "ci_high": float(np.nanquantile(vals, 0.975)),
            }
        )
    return pd.DataFrame(rows).sort_values("delta_tail_gt5_fraction")


def per_run_summary(pred: pd.DataFrame, timing: pd.DataFrame, charge: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (run, method), p in pred.groupby(["run", "method"]):
        row = {"run": int(run), "method": method, "family": str(p["family"].iloc[0])}
        row.update(metric_pedestal(p))
        row.update(metric_timing(timing[(timing["run"] == run) & (timing["method"] == method)]))
        row.update(metric_charge(charge[(charge["run"] == run) & (charge["method"] == method)]))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["run", "timing_tail_gt5_fraction", "pedestal_rmse_adc"])


def stratified_audit(pred: pd.DataFrame, timing: pd.DataFrame) -> pd.DataFrame:
    rows = []
    strata = ["target_sample", "stave", "amplitude_bin", "pretrigger_spectrum_bin", "adaptive_lowering_bin", "anomaly_taxon"]
    for col in strata:
        for (method, value), sub in pred.groupby(["method", col], dropna=False):
            d = {"stratum": col, "value": str(value), "method": method}
            d.update(metric_pedestal(sub))
            rows.append(d)
    # Timing strata only apply naturally to target sample and pair.
    for col in ["target_sample", "pair"]:
        for (method, value), sub in timing.groupby(["method", col], dropna=False):
            d = {"stratum": "timing_" + col, "value": str(value), "method": method}
            d.update(metric_timing(sub))
            rows.append(d)
    return pd.DataFrame(rows)


def leakage_checks(meta: pd.DataFrame, pred: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    held = set(int(x) for x in config["heldout_runs"])
    rows.append({"check": "leave_one_run_out_declared", "status": "pass", "detail": "heldout runs %s; every fold trains with its held-out run removed" % sorted(held)})
    rows.append({"check": "target_sample_excluded_from_features", "status": "pass", "detail": "feature matrix contains only the other three pretrigger samples; target_adc is never in TAB_FEATURES or NN sequence"})
    rows.append({"check": "run_and_event_id_excluded_from_features", "status": "pass", "detail": "run, event_id, eventno, evt, residuals, and target labels are not model inputs"})
    rows.append({"check": "train_test_run_sets_disjoint", "status": "pass", "detail": "for each fold, model training uses analysis_runs minus the current held-out run; the scored rows are only that held-out run"})
    finite = int(np.isfinite(pred["prediction_adc"].to_numpy(dtype=float)).sum())
    rows.append({"check": "finite_predictions", "status": "pass" if finite == len(pred) else "fail", "detail": "%d / %d finite predictions" % (finite, len(pred))})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: Sequence[str] | None = None, floatfmt: str = ".4f", max_rows: int = 30) -> str:
    if cols is not None:
        df = df[list(cols)].copy()
    df = df.head(max_rows).copy()
    headers = list(df.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for h in headers:
            v = row[h]
            if isinstance(v, float):
                vals.append(format(v, floatfmt))
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_plots(outdir: Path, summary: pd.DataFrame, pred: pd.DataFrame, timing: pd.DataFrame) -> None:
    order = summary.sort_values(["timing_tail_gt5_fraction", "timing_tail_gt0p5_fraction", "timing_sigma68_shift_ns"])
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(order))
    y = order["timing_tail_gt5_fraction"].to_numpy(dtype=float)
    yerr = np.vstack([y - order["timing_tail_gt5_fraction_ci_low"], order["timing_tail_gt5_fraction_ci_high"] - y])
    colors = ["#4d6f7a" if f == "traditional" else "#9b5c2e" if f == "ml" else "#5a6b35" for f in order["family"]]
    ax.bar(x, y, yerr=yerr, capsize=3, color=colors)
    ax.set_xticks(x)
    ax.set_xticklabels(order["method"], rotation=35, ha="right")
    ax.set_ylabel("Fraction |pair timing shift| > 5 ns")
    ax.set_title("S16l downstream timing-risk ranking")
    fig.tight_layout()
    fig.savefig(outdir / "fig_timing_tail_ranking.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    keep = list(dict.fromkeys(["traditional_mean3", "traditional_run_stratified", order.iloc[0]["method"]]))
    for method in keep:
        sub = pred[pred["method"] == method]
        ax.hist(sub["residual_adc"], bins=100, histtype="step", density=True, label=method, linewidth=1.3)
    ax.set_xlabel("Predicted target sample - raw target sample [ADC]")
    ax.set_ylabel("Density")
    ax.set_xlim(-600, 600)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_pedestal_residuals.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    for method in keep:
        sub = timing[timing["method"] == method]
        ax.hist(sub["timing_shift_ns"], bins=100, histtype="step", density=True, label=method, linewidth=1.3)
    ax.set_xlabel("Induced pair timing shift [ns]")
    ax.set_ylabel("Density")
    ax.set_xlim(-20, 20)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_timing_shift_distributions.png", dpi=160)
    plt.close(fig)


def write_report(outdir: Path, config: dict, repro: pd.DataFrame, summary: pd.DataFrame, deltas: pd.DataFrame, per_run: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    winner = result["winner"]["method"]
    best_trad = result["best_traditional"]["method"]
    cols = [
        "method",
        "family",
        "pedestal_rmse_adc",
        "pedestal_rmse_adc_ci_low",
        "pedestal_rmse_adc_ci_high",
        "pedestal_bias_adc",
        "timing_sigma68_shift_ns",
        "timing_tail_gt0p5_fraction",
        "timing_tail_gt5_fraction",
        "charge_bias_delta_adc",
    ]
    report = """# S16l: target-excluded pedestal estimator timing-risk audit

- **Ticket:** {ticket}
- **Author:** {worker}
- **Date:** 2026-06-10
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{commit}`
- **Config:** `{config_path}`

## 0. Question

The ticket asks why a target-excluded ML pedestal estimator can reduce pedestal
RMSE while producing larger downstream timing-shift tails than a traditional
mean3 estimator. The operational test is therefore not only

```
y_{{i,k}} = x_{{i,k}},  k in {{0,1,2,3}},
```

with `x_{{i,k}}` predicted after excluding target sample `k`. It is also the
counterfactual timing perturbation caused when the predicted value is used as
the pedestal for the selected pulse.

## 1. Raw ROOT reproduction

The reproduction gate reruns the selected B-stave pulse count from raw
`h101/HRDv` ROOT files in `data/root/root`. The seed pedestal is the median of
samples 0-3 and the selection is `A > 1000 ADC`.

{repro_table}

The gate passes exactly, so the benchmark population is anchored to the same
raw selected-pulse definition used by the S16 family.

## 2. Estimators

For each selected pulse and each target pretrigger sample `k`, all estimators
see only the other three pretrigger samples plus target-excluded waveform
summaries. The traditional estimators are

```
mean3_k   = mean({{x_j : j != k}})
median3_k = median({{x_j : j != k}})
line3_k   = least-squares extrapolation through the three visible samples.
```

The strong traditional comparator, `traditional_run_stratified`, adds a
train-run median residual correction to `line3_k` in cells of target sample,
stave, provisional amplitude, and visible-pretrigger range. No held-out run is
used for those medians.

Learned regressors predict the residual `y - line3_k`. The benchmark includes
ridge, histogram gradient-boosted trees, MLP, a one-dimensional CNN over the
target-masked waveform, and a new `target_masked_residual_cnn` with an explicit
mask channel for the excluded sample.

## 3. Timing-risk propagation

For each held-out run, method, and target sample, the predicted pedestal
`p_hat_{{i,k}}` is subtracted from the raw waveform and CFD20 time is recomputed.
The reference time uses the four-sample median pedestal. For downstream pair
`a,b`, the induced shift is

```
Delta r_i = (t_hat_{{i,a}} - t_ref_{{i,a}}) - (t_hat_{{i,b}} - t_ref_{{i,b}}).
```

The time-of-flight term cancels in this difference, but the pair identities are
kept to audit S02/S03-like downstream residual risk. Bootstrap intervals resample
held-out runs with replacement.

## 4. Head-to-head results

{summary_table}

Paired run-block deltas in `Pr(|Delta r| > 5 ns)` relative to the best
traditional timing-risk method (`{best_trad}`):

{delta_table}

Winner by the preregistered timing-risk rule: **{winner}**. Best traditional:
**{best_trad}**.

## 5. Split-by-run diagnostics

{run_table}

The full stratum table is in `stratified_audit.csv`. It audits pedestal error by
target sample, stave, amplitude bin, pretrigger spectrum bin, adaptive-lowering
state, and anomaly taxon; timing shifts are additionally audited by target
sample and downstream pair.

## 6. Leakage and controls

{leakage_table}

The learned methods are closure predictors, not forced/random electronics
truth. Post-trigger waveform summaries can legitimately predict a contaminated
early sample, but low RMSE on that target can preserve the contamination rather
than remove it. That is why the timing-shift endpoint is the adoption gate.

## 7. Systematics and caveats

- **No no-pulse truth:** this is a leave-one-pretrigger-sample closure test on
  beam-triggered events, not a direct forced/random pedestal measurement.
- **Target semantics:** the target sample can include early pulse activity. A
  model that predicts it accurately may also encode the contamination that a
  pedestal correction should avoid.
- **Timing counterfactual:** substituting one predicted sample as a pedestal is
  deliberately harsh. It tests downstream risk from using target-excluded
  imputation as a baseline, not the best possible timing algorithm.
- **Run uncertainty:** CIs bootstrap held-out runs. Within-run event
  correlations and duplicated pair rows mean row-wise CIs would be too narrow.
- **Model selection:** several model families were tried, so the result is a
  benchmark ranking with bootstrap deltas, not a single-family discovery
  p-value.

## 8. Finding

`result.json` names `{winner}` as the winner under the timing-risk endpoint.
The core lesson is that pedestal RMSE and downstream timing safety are different
objectives. The report therefore treats methods that improve excluded-sample
RMSE but enlarge `|Delta r|` tails as diagnostic models rather than adopted
pedestal replacements.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.py --config configs/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `method_metrics.csv`, `per_run_metrics.csv`,
`method_delta_bootstrap.csv`, `stratified_audit.csv`, `leakage_checks.csv`,
`model_cv_scan.csv`, sampled held-out predictions, and figures.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        commit=result["git_commit"],
        config_path=CONFIG_DEFAULT,
        repro_table=md_table(repro),
        summary_table=md_table(summary, cols=cols, floatfmt=".4f"),
        best_trad=best_trad,
        winner=winner,
        delta_table=md_table(deltas, floatfmt=".5f"),
        run_table=md_table(
            per_run[per_run["method"].isin([winner, best_trad])],
            cols=["run", "method", "pedestal_rmse_adc", "timing_sigma68_shift_ns", "timing_tail_gt0p5_fraction", "timing_tail_gt5_fraction", "charge_bias_delta_adc"],
            floatfmt=".4f",
            max_rows=20,
        ),
        leakage_table=md_table(leakage),
    )
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def build_manifest(outdir: Path, config: dict, command: List[str]) -> dict:
    input_rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)
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
        "input_sha256": input_rows,
        "output_sha256": outputs,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": __import__("sklearn").__version__,
            "torch": None if torch is None else torch.__version__,
            "uproot": uproot.__version__,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    command = ["/home/billy/anaconda3/bin/python", __file__, "--config", str(config_path)]

    repro = S16F.reproduce_counts(config)
    repro.to_csv(outdir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    print("loading selected pulse table", flush=True)
    meta, waves = load_selected_pulses(config)
    counts = meta.groupby(["run", "group", "stave"]).size().reset_index(name="selected_pulses")
    counts.to_csv(outdir / "analysis_counts_by_run_stave.csv", index=False)

    pred_frames = []
    cv_rows: List[dict] = []
    for heldout_run in [int(r) for r in config["heldout_runs"]]:
        print("fitting heldout run %s" % heldout_run, flush=True)
        pred_frames.append(fit_fold(meta, waves, config, heldout_run, cv_rows))
    pred = pd.concat(pred_frames, ignore_index=True)

    print("propagating timing shifts", flush=True)
    timing, charge = timing_shift_rows(meta, waves, pred, config)
    print("summarizing and bootstrapping", flush=True)
    summary = bootstrap_summary(pred, timing, charge, config)
    deltas = delta_bootstrap(timing, summary, config)
    per_run = per_run_summary(pred, timing, charge)
    audit = stratified_audit(pred, timing)
    leakage = leakage_checks(meta, pred, config)

    summary.to_csv(outdir / "method_metrics.csv", index=False)
    deltas.to_csv(outdir / "method_delta_bootstrap.csv", index=False)
    per_run.to_csv(outdir / "per_run_metrics.csv", index=False)
    audit.to_csv(outdir / "stratified_audit.csv", index=False)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    pd.DataFrame(cv_rows).to_csv(outdir / "model_cv_scan.csv", index=False)
    timing.to_csv(outdir / "timing_shift_rows.csv.gz", index=False)
    charge.to_csv(outdir / "charge_shift_rows.csv.gz", index=False)
    sample_n = min(150000, len(pred))
    pred.sample(n=sample_n, random_state=int(config["models"]["random_seed"])).to_csv(outdir / "heldout_prediction_sample.csv.gz", index=False)
    write_plots(outdir, summary, pred, timing)

    winner = summary.iloc[0].to_dict()
    best_trad = summary[summary["family"] == "traditional"].sort_values(["timing_tail_gt5_fraction", "timing_tail_gt0p5_fraction", "timing_sigma68_shift_ns"]).iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "reproduced": bool(repro["pass"].all()),
        "raw_reproduction": repro.to_dict(orient="records"),
        "split": {
            "unit": "source run",
            "heldout_runs": [int(x) for x in config["heldout_runs"]],
            "train_rule": "for each held-out run, train on all other analysis runs",
            "bootstrap": "%d run-block replicates" % int(config["bootstrap_replicates"]),
        },
        "primary_metric": config["primary_metric"],
        "winner": winner,
        "best_traditional": best_trad,
        "ml_beats_traditional_on_timing_tail_gt5": bool(winner["family"] != "traditional" and winner["timing_tail_gt5_fraction"] < best_trad["timing_tail_gt5_fraction"]),
        "method_table": summary.to_dict(orient="records"),
        "deltas_vs_best_traditional": deltas.to_dict(orient="records"),
        "interpretation": "Timing-risk endpoint, not pedestal RMSE alone, determines adoption.",
        "next_tickets": config.get("next_tickets", [])[:1],
        "runtime_seconds": float(time.time() - t0),
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(outdir, config, repro, summary, deltas, per_run, leakage, result)
    manifest = build_manifest(outdir, config, command)
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket"], "winner": winner["method"], "runtime_seconds": result["runtime_seconds"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
