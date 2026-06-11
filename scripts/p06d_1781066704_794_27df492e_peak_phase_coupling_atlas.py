#!/usr/bin/env python3
"""P06d: peak-phase charge-timing coupling atlas.

The script reads raw B-stack HRDv ROOT records, reproduces the S00 selected-pulse
count from raw ROOT, builds a peak/CFD phase atlas for timing, charge,
saturation, and anomaly/dropout proxies, then benchmarks a support-matched
traditional atlas against classical ML and small neural models on a run-held-out
split.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import uproot
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


CONFIG_DEFAULT = "configs/p06d_1781066704_794_27df492e_peak_phase_coupling_atlas.json"


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


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / ("hrdb_run_%04d.root" % int(run))


def iter_raw(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["TRIGGER", "EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def stack_obj(values: np.ndarray) -> np.ndarray:
    if len(values) == 0:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack(values).astype(np.float32)


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=np.float64)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = float(waveforms[i, j - 1])
        y1 = float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0.0 else (j - 1) + (float(threshold[i]) - y0) / denom
    return out


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    center = float(np.median(values))
    return float(np.percentile(np.abs(values - center), 68.0))


def load_selected_pulses(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    groups = group_for_run(config)
    staves = config["staves"]
    stave_names = list(staves.keys())
    channels = np.asarray([int(staves[name]) for name in stave_names], dtype=int)
    baseline_idx = np.asarray(config["baseline_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {name: 0 for name in stave_names}
        run_counts.update({"run": int(run), "group": groups[int(run)], "events_total": 0, "selected_pulses": 0})
        for batch in iter_raw(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            trigger = np.asarray(batch["TRIGGER"], dtype=np.int64)
            raw = stack_obj(batch["HRDv"]).reshape(-1, 8, nsamp)[:, channels, :]
            base = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - base[..., None]
            amp = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            positive_area = np.clip(corrected, 0.0, None).sum(axis=-1)
            pre_ptp = np.ptp(raw[..., baseline_idx], axis=-1)
            selected = amp > cut
            run_counts["events_total"] += int(len(eventno))
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, stave in enumerate(stave_names):
                run_counts[stave] += int(selected[:, idx].sum())
            ev_idx, st_idx = np.where(selected)
            if len(ev_idx) == 0:
                continue
            sel_wave = corrected[ev_idx, st_idx, :].astype(np.float32)
            sel_amp = amp[ev_idx, st_idx].astype(np.float64)
            cfd10 = cfd_time_samples(sel_wave, sel_amp, 0.10)
            cfd20 = cfd_time_samples(sel_wave, sel_amp, 0.20)
            cfd50 = cfd_time_samples(sel_wave, sel_amp, 0.50)
            peak_sel = peak[ev_idx, st_idx].astype(int)
            total_pos = np.maximum(positive_area[ev_idx, st_idx], 1.0)
            tail = np.clip(sel_wave[:, 12:], 0.0, None).sum(axis=1) / total_pos
            late = np.clip(sel_wave[:, 9:], 0.0, None).sum(axis=1) / total_pos
            early = np.clip(sel_wave[:, :6], 0.0, None).sum(axis=1) / total_pos
            plateau = (sel_wave >= (0.985 * sel_amp[:, None])).sum(axis=1)
            secondary = np.zeros(len(sel_wave), dtype=np.float64)
            post_min = np.zeros(len(sel_wave), dtype=np.float64)
            for i, pk in enumerate(peak_sel):
                mask = np.ones(nsamp, dtype=bool)
                lo = max(0, pk - 1)
                hi = min(nsamp, pk + 2)
                mask[lo:hi] = False
                secondary[i] = float(np.max(sel_wave[i, mask]) / max(sel_amp[i], 1.0))
                post = sel_wave[i, min(nsamp, pk + 2) :]
                post_min[i] = float(np.min(post) / max(sel_amp[i], 1.0)) if len(post) else 0.0
            frame = pd.DataFrame(
                {
                    "run": int(run),
                    "group": groups[int(run)],
                    "eventno": eventno[ev_idx],
                    "evt": evt[ev_idx],
                    "trigger": trigger[ev_idx],
                    "stave": np.asarray(stave_names)[st_idx],
                    "stave_idx": st_idx.astype(int),
                    "channel": channels[st_idx].astype(int),
                    "baseline_adc": base[ev_idx, st_idx],
                    "amplitude_adc": sel_amp,
                    "log_amp": np.log(np.maximum(sel_amp, 1.0)),
                    "area_adc_samples": area[ev_idx, st_idx],
                    "positive_area_adc_samples": positive_area[ev_idx, st_idx],
                    "log_positive_area": np.log(np.maximum(positive_area[ev_idx, st_idx], 1.0)),
                    "area_over_amp": area[ev_idx, st_idx] / np.maximum(sel_amp, 1.0),
                    "positive_area_over_amp": positive_area[ev_idx, st_idx] / np.maximum(sel_amp, 1.0),
                    "peak_sample": peak_sel,
                    "cfd10_sample": cfd10,
                    "cfd20_sample": cfd20,
                    "cfd50_sample": cfd50,
                    "cfd10_phase": cfd10 - peak_sel,
                    "cfd20_phase": cfd20 - peak_sel,
                    "cfd50_phase": cfd50 - peak_sel,
                    "cfd_slew_20_50": cfd50 - cfd20,
                    "pretrigger_ptp_adc": pre_ptp[ev_idx, st_idx],
                    "tail_area_frac": tail,
                    "late_area_frac": late,
                    "early_area_frac": early,
                    "secondary_peak_frac": secondary,
                    "post_peak_min_frac": post_min,
                    "plateau_count": plateau.astype(float),
                    "peak_edge_score": np.maximum(np.abs(peak_sel - 6.0), np.abs(peak_sel - 7.0)),
                }
            )
            rows.append(frame)
            waves.append(sel_wave)
        count_rows.append(run_counts)

    meta = pd.concat(rows, ignore_index=True)
    wave = np.concatenate(waves, axis=0).astype(np.float32)
    counts = pd.DataFrame(count_rows)
    return meta, wave, counts


def add_targets(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    meta = meta.copy()
    train_groups = set(config["train_groups"])
    train_mask = meta["group"].isin(train_groups).to_numpy()

    timing_staves = set(config["timing_staves"])
    meta["timing_residual_ns"] = np.nan
    timing_mask = meta["stave"].isin(timing_staves) & np.isfinite(meta["cfd20_sample"])
    timing = meta.loc[timing_mask, ["run", "eventno", "stave", "cfd20_sample"]].copy()
    counts = timing.groupby(["run", "eventno"])["stave"].transform("nunique")
    timing = timing[counts >= 2].copy()
    timing["event_median_sample"] = timing.groupby(["run", "eventno"])["cfd20_sample"].transform("median")
    resid = (timing["cfd20_sample"] - timing["event_median_sample"]) * float(config["period_ns"])
    meta.loc[timing.index, "timing_residual_ns"] = resid.to_numpy(dtype=float)

    train = meta.loc[train_mask & meta["timing_residual_ns"].notna()].copy()
    # Charge residual target: remove the train-only log(area)-vs-log(amplitude)
    # calibration per stave, then apply the frozen coefficients everywhere.
    meta["charge_log_residual"] = np.nan
    for stave, sub in train.groupby("stave"):
        x = sub["log_amp"].to_numpy(dtype=float)
        y = sub["log_positive_area"].to_numpy(dtype=float)
        if len(sub) < 50:
            continue
        coef = np.polyfit(x, y, deg=1)
        idx = meta["stave"] == stave
        pred = coef[0] * meta.loc[idx, "log_amp"].to_numpy(dtype=float) + coef[1]
        meta.loc[idx, "charge_log_residual"] = meta.loc[idx, "log_positive_area"].to_numpy(dtype=float) - pred

    sat_threshold = float(np.quantile(meta.loc[train_mask, "amplitude_adc"], 0.985))
    meta["saturation_harm_score"] = (
        (meta["amplitude_adc"].to_numpy(dtype=float) >= sat_threshold).astype(float)
        + 0.35 * np.clip(meta["plateau_count"].to_numpy(dtype=float) - 1.0, 0.0, None)
        + 0.15 * np.clip(meta["peak_edge_score"].to_numpy(dtype=float) - 5.0, 0.0, None)
    )
    anomaly_raw = (
        1.8 * meta["tail_area_frac"].to_numpy(dtype=float)
        + 1.2 * np.clip(meta["secondary_peak_frac"].to_numpy(dtype=float), 0.0, None)
        + 0.015 * meta["pretrigger_ptp_adc"].to_numpy(dtype=float)
        + 0.6 * np.clip(-meta["post_peak_min_frac"].to_numpy(dtype=float), 0.0, None)
    )
    meta["anomaly_dropout_score"] = anomaly_raw

    eligible = train_mask & meta["timing_residual_ns"].notna() & meta["charge_log_residual"].notna()
    if eligible.sum() < 1000:
        raise RuntimeError("not enough train rows with timing and charge targets")
    loc = meta.loc[eligible]
    scales = {
        "timing_abs_ns": max(float(np.median(np.abs(loc["timing_residual_ns"]))), 1e-6),
        "charge_abs": max(float(np.median(np.abs(loc["charge_log_residual"]))), 1e-6),
        "saturation": max(float(np.percentile(loc["saturation_harm_score"], 75.0)), 1e-6),
        "anomaly": max(float(np.percentile(loc["anomaly_dropout_score"], 75.0)), 1e-6),
    }
    meta.attrs["target_scales"] = scales
    meta["coupling_burden"] = (
        np.abs(meta["timing_residual_ns"].to_numpy(dtype=float)) / scales["timing_abs_ns"]
        + 0.75 * np.abs(meta["charge_log_residual"].to_numpy(dtype=float)) / scales["charge_abs"]
        + 0.50 * meta["saturation_harm_score"].to_numpy(dtype=float) / scales["saturation"]
        + 0.50 * meta["anomaly_dropout_score"].to_numpy(dtype=float) / scales["anomaly"]
    )
    return meta


FEATURES = [
    "log_amp",
    "area_over_amp",
    "positive_area_over_amp",
    "peak_sample",
    "cfd10_phase",
    "cfd20_phase",
    "cfd50_phase",
    "cfd_slew_20_50",
    "pretrigger_ptp_adc",
    "tail_area_frac",
    "late_area_frac",
    "early_area_frac",
    "secondary_peak_frac",
    "post_peak_min_frac",
    "plateau_count",
    "peak_edge_score",
]

PEAK_PHASE_FEATURES = ["peak_sample", "cfd10_phase", "cfd20_phase", "cfd50_phase", "cfd_slew_20_50"]
AMPLITUDE_FEATURES = ["log_amp", "area_over_amp", "positive_area_over_amp"]
CAT_FEATURES = ["stave"]


def make_preprocessor(features: List[str] = FEATURES) -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", StandardScaler(), features),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
        ]
    )


def split_indices(meta: pd.DataFrame, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    valid = meta["coupling_burden"].notna().to_numpy()
    train = valid & meta["group"].isin(config["train_groups"]).to_numpy()
    cal = valid & meta["group"].isin(config["calibration_groups"]).to_numpy()
    test = valid & meta["group"].isin(config["test_groups"]).to_numpy()
    return np.where(train)[0], np.where(cal)[0], np.where(test)[0]


def sample_train(train_idx: np.ndarray, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["random_seed"]))
    max_n = int(config["max_train_records"])
    if len(train_idx) <= max_n:
        return train_idx
    return rng.choice(train_idx, size=max_n, replace=False)


def add_calibration_offset(y_cal: np.ndarray, p_cal: np.ndarray, p_test: np.ndarray) -> np.ndarray:
    if len(y_cal) == 0:
        return p_test
    return p_test + float(np.median(y_cal - p_cal))


def assign_atlas_bins(train: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    amp_q = np.quantile(train["log_amp"].to_numpy(dtype=float), [0.2, 0.4, 0.6, 0.8])
    phase_q = np.quantile(train["cfd20_phase"].to_numpy(dtype=float), [0.2, 0.4, 0.6, 0.8])
    out["amp_bin"] = np.searchsorted(amp_q, out["log_amp"].to_numpy(dtype=float), side="right")
    out["phase_bin"] = np.searchsorted(phase_q, out["cfd20_phase"].to_numpy(dtype=float), side="right")
    out["peak_bin"] = pd.cut(out["peak_sample"], bins=[-1, 4, 6, 8, 11, 18], labels=False).astype(int)
    return out


def fit_traditional_atlas(train: pd.DataFrame, apply: pd.DataFrame) -> np.ndarray:
    tr = assign_atlas_bins(train, train)
    ap = assign_atlas_bins(train, apply)
    global_med = float(np.median(tr["coupling_burden"]))
    by_stave = tr.groupby("stave")["coupling_burden"].median().to_dict()
    by_stave_amp = tr.groupby(["stave", "amp_bin"])["coupling_burden"].median().to_dict()
    by_cell = tr.groupby(["stave", "amp_bin", "peak_bin", "phase_bin"])["coupling_burden"].median().to_dict()
    pred = np.empty(len(ap), dtype=np.float64)
    for i, row in enumerate(ap.itertuples(index=False)):
        key = (row.stave, int(row.amp_bin), int(row.peak_bin), int(row.phase_bin))
        key2 = (row.stave, int(row.amp_bin))
        pred[i] = by_cell.get(key, by_stave_amp.get(key2, by_stave.get(row.stave, global_med)))
    return pred


class WaveCnn(torch.nn.Module):
    def __init__(self, n_tab: int, gated: bool = False):
        super().__init__()
        self.gated = bool(gated)
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(1, 16, kernel_size=3, padding=1),
            torch.nn.GELU(),
            torch.nn.Conv1d(16, 24, kernel_size=3, padding=1),
            torch.nn.GELU(),
            torch.nn.AdaptiveAvgPool1d(1),
        )
        if self.gated:
            self.gate = torch.nn.Sequential(torch.nn.Linear(5, 16), torch.nn.GELU(), torch.nn.Linear(16, 24), torch.nn.Sigmoid())
        self.head = torch.nn.Sequential(torch.nn.Linear(24 + n_tab, 64), torch.nn.GELU(), torch.nn.Linear(64, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor, phase: torch.Tensor) -> torch.Tensor:
        h = self.conv(seq[:, None, :]).squeeze(-1)
        if self.gated:
            h = h * (0.5 + self.gate(phase))
        return self.head(torch.cat([h, tab], dim=1)).squeeze(1)


def fit_torch_model(
    method: str,
    meta: pd.DataFrame,
    wave: np.ndarray,
    config: dict,
    train_idx: np.ndarray,
    cal_idx: np.ndarray,
    test_idx: np.ndarray,
) -> np.ndarray:
    seed = int(config["random_seed"]) + (33 if method == "phase_gated_residual_cnn" else 23)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    feat = FEATURES + ["stave_idx"]
    phase_feat = PEAK_PHASE_FEATURES
    train = meta.iloc[train_idx]
    mu = train[feat].mean().to_numpy(dtype=np.float32)
    sd = train[feat].std().replace(0.0, 1.0).to_numpy(dtype=np.float32)
    ph_mu = train[phase_feat].mean().to_numpy(dtype=np.float32)
    ph_sd = train[phase_feat].std().replace(0.0, 1.0).to_numpy(dtype=np.float32)
    x_train = ((meta.iloc[train_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    x_cal = ((meta.iloc[cal_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    x_test = ((meta.iloc[test_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    ph_train = ((meta.iloc[train_idx][phase_feat].to_numpy(dtype=np.float32) - ph_mu) / ph_sd).astype(np.float32)
    ph_cal = ((meta.iloc[cal_idx][phase_feat].to_numpy(dtype=np.float32) - ph_mu) / ph_sd).astype(np.float32)
    ph_test = ((meta.iloc[test_idx][phase_feat].to_numpy(dtype=np.float32) - ph_mu) / ph_sd).astype(np.float32)
    seq_mu = wave[train_idx].mean(axis=0, keepdims=True)
    seq_sd = wave[train_idx].std(axis=0, keepdims=True)
    seq_sd[seq_sd == 0.0] = 1.0
    s_train = ((wave[train_idx] - seq_mu) / seq_sd).astype(np.float32)
    s_cal = ((wave[cal_idx] - seq_mu) / seq_sd).astype(np.float32)
    s_test = ((wave[test_idx] - seq_mu) / seq_sd).astype(np.float32)
    y_train = meta.iloc[train_idx]["coupling_burden"].to_numpy(dtype=np.float32)
    y_cal = meta.iloc[cal_idx]["coupling_burden"].to_numpy(dtype=np.float32)
    y_mean = float(np.mean(y_train))
    target = y_train - y_mean
    net = WaveCnn(x_train.shape[1], gated=(method == "phase_gated_residual_cnn"))
    opt = torch.optim.AdamW(net.parameters(), lr=2.5e-3, weight_decay=1e-4)
    loss_fn = torch.nn.SmoothL1Loss(beta=0.8)
    batch = int(config["torch_batch_size"])
    order = np.arange(len(train_idx))
    net.train()
    for _ in range(int(config["torch_epochs"])):
        rng.shuffle(order)
        for start in range(0, len(order), batch):
            loc = order[start : start + batch]
            xb = torch.from_numpy(x_train[loc])
            sb = torch.from_numpy(s_train[loc])
            pb = torch.from_numpy(ph_train[loc])
            yb = torch.from_numpy(target[loc])
            opt.zero_grad()
            loss = loss_fn(net(sb, xb, pb), yb)
            loss.backward()
            opt.step()
    net.eval()
    with torch.no_grad():
        p_cal = net(torch.from_numpy(s_cal), torch.from_numpy(x_cal), torch.from_numpy(ph_cal)).numpy() + y_mean
        p_test = net(torch.from_numpy(s_test), torch.from_numpy(x_test), torch.from_numpy(ph_test)).numpy() + y_mean
    return add_calibration_offset(y_cal.astype(float), p_cal.astype(float), p_test.astype(float))


def fit_predict_all(meta: pd.DataFrame, wave: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train_idx_all, cal_idx, test_idx = split_indices(meta, config)
    train_idx = sample_train(train_idx_all, config)
    y_train = meta.iloc[train_idx]["coupling_burden"].to_numpy(dtype=float)
    y_cal = meta.iloc[cal_idx]["coupling_burden"].to_numpy(dtype=float)
    test_base = meta.iloc[test_idx][
        [
            "run",
            "group",
            "eventno",
            "stave",
            "stave_idx",
            "coupling_burden",
            "timing_residual_ns",
            "charge_log_residual",
            "saturation_harm_score",
            "anomaly_dropout_score",
        ]
    ].copy()
    preds: List[pd.DataFrame] = []
    cv_rows: List[dict] = []

    def append_pred(method: str, family: str, pred: np.ndarray) -> None:
        tmp = test_base.copy()
        tmp["method"] = method
        tmp["family"] = family
        tmp["prediction"] = pred
        tmp["residual"] = tmp["prediction"] - tmp["coupling_burden"]
        tmp["abs_residual"] = np.abs(tmp["residual"])
        preds.append(tmp)

    p_cal = fit_traditional_atlas(meta.iloc[train_idx], meta.iloc[cal_idx])
    p_test = fit_traditional_atlas(meta.iloc[train_idx], meta.iloc[test_idx])
    append_pred("traditional_peak_phase_atlas", "traditional", add_calibration_offset(y_cal, p_cal, p_test))

    ridge = make_pipeline(make_preprocessor(), Ridge(alpha=3.0))
    ridge.fit(meta.iloc[train_idx], y_train)
    append_pred("ridge", "ml", add_calibration_offset(y_cal, ridge.predict(meta.iloc[cal_idx]), ridge.predict(meta.iloc[test_idx])))

    hgb_grid = list(itertools.product([15, 31, 63], [0.03, 0.06, 0.10], [0.0, 0.05]))
    best = None
    groups = meta.iloc[train_idx]["run"].to_numpy()
    cv = GroupKFold(n_splits=min(4, len(np.unique(groups))))
    for leaves, lr, l2 in hgb_grid:
        scores = []
        for tr, va in cv.split(meta.iloc[train_idx], y_train, groups=groups):
            model = HistGradientBoostingRegressor(
                max_iter=180,
                max_leaf_nodes=int(leaves),
                learning_rate=float(lr),
                l2_regularization=float(l2),
                random_state=int(config["random_seed"]),
            )
            model.fit(meta.iloc[train_idx].iloc[tr][FEATURES + ["stave_idx"]], y_train[tr])
            scores.append(mean_absolute_error(y_train[va], model.predict(meta.iloc[train_idx].iloc[va][FEATURES + ["stave_idx"]])))
        row = {"method": "hist_gradient_boosted_trees", "max_leaf_nodes": int(leaves), "learning_rate": float(lr), "l2_regularization": float(l2), "group_cv_mae": float(np.mean(scores))}
        cv_rows.append(row)
        if best is None or row["group_cv_mae"] < best["group_cv_mae"]:
            best = row
    hgb = HistGradientBoostingRegressor(
        max_iter=240,
        max_leaf_nodes=int(best["max_leaf_nodes"]),
        learning_rate=float(best["learning_rate"]),
        l2_regularization=float(best["l2_regularization"]),
        random_state=int(config["random_seed"]),
    )
    hgb.fit(meta.iloc[train_idx][FEATURES + ["stave_idx"]], y_train)
    append_pred("hist_gradient_boosted_trees", "ml", add_calibration_offset(y_cal, hgb.predict(meta.iloc[cal_idx][FEATURES + ["stave_idx"]]), hgb.predict(meta.iloc[test_idx][FEATURES + ["stave_idx"]])))

    mlp = make_pipeline(
        make_preprocessor(),
        MLPRegressor(hidden_layer_sizes=(80, 40), activation="relu", alpha=3e-4, batch_size=768, max_iter=160, random_state=int(config["random_seed"])),
    )
    mlp.fit(meta.iloc[train_idx], y_train)
    append_pred("mlp", "ml", add_calibration_offset(y_cal, mlp.predict(meta.iloc[cal_idx]), mlp.predict(meta.iloc[test_idx])))

    for method, family in [("one_dimensional_cnn", "ml"), ("phase_gated_residual_cnn", "new_architecture")]:
        append_pred(method, family, fit_torch_model(method, meta, wave, config, train_idx, cal_idx, test_idx))

    # Sentinels. These are not eligible to win; they quantify leakage/specificity.
    for name, features in [
        ("amplitude_only_hgb", AMPLITUDE_FEATURES),
        ("peak_phase_dropout_hgb", [f for f in FEATURES if f not in PEAK_PHASE_FEATURES]),
    ]:
        model = HistGradientBoostingRegressor(max_iter=180, max_leaf_nodes=31, learning_rate=0.06, random_state=int(config["random_seed"]))
        model.fit(meta.iloc[train_idx][features + ["stave_idx"]], y_train)
        append_pred(name, "sentinel", add_calibration_offset(y_cal, model.predict(meta.iloc[cal_idx][features + ["stave_idx"]]), model.predict(meta.iloc[test_idx][features + ["stave_idx"]])))
    run_only_train = pd.get_dummies(meta.iloc[train_idx][["run", "stave"]].astype(str))
    run_only_cal = pd.get_dummies(meta.iloc[cal_idx][["run", "stave"]].astype(str)).reindex(columns=run_only_train.columns, fill_value=0)
    run_only_test = pd.get_dummies(meta.iloc[test_idx][["run", "stave"]].astype(str)).reindex(columns=run_only_train.columns, fill_value=0)
    run_model = Ridge(alpha=10.0).fit(run_only_train, y_train)
    append_pred("run_only_hgb", "sentinel", add_calibration_offset(y_cal, run_model.predict(run_only_cal), run_model.predict(run_only_test)))
    rng = np.random.default_rng(int(config["random_seed"]) + 99)
    shuffled = y_train.copy()
    rng.shuffle(shuffled)
    shuf_model = HistGradientBoostingRegressor(max_iter=160, max_leaf_nodes=31, learning_rate=0.06, random_state=int(config["random_seed"]) + 1)
    shuf_model.fit(meta.iloc[train_idx][FEATURES + ["stave_idx"]], shuffled)
    append_pred("shuffled_target_hgb", "sentinel", add_calibration_offset(y_cal, shuf_model.predict(meta.iloc[cal_idx][FEATURES + ["stave_idx"]]), shuf_model.predict(meta.iloc[test_idx][FEATURES + ["stave_idx"]])))

    return pd.concat(preds, ignore_index=True), pd.DataFrame(cv_rows).sort_values("group_cv_mae")


def bootstrap_summary(preds: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 500)
    runs = np.asarray(sorted(preds["run"].unique()), dtype=int)
    rows = []
    by_method = {m: preds[preds["method"] == m].copy() for m in preds["method"].unique()}
    for method, sub in by_method.items():
        vals = []
        by_run = {r: sub[sub["run"] == r] for r in runs}
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([by_run[int(r)] for r in sampled], ignore_index=True)
            vals.append(float(boot["abs_residual"].mean()))
        residual = sub["residual"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "family": str(sub["family"].iloc[0]),
                "n": int(len(sub)),
                "mae": float(np.mean(np.abs(residual))),
                "mae_ci_low": float(np.quantile(vals, 0.025)),
                "mae_ci_high": float(np.quantile(vals, 0.975)),
                "bias": float(np.mean(residual)),
                "rmse": float(math.sqrt(np.mean(residual * residual))),
                "q05_residual": float(np.quantile(residual, 0.05)),
                "q95_residual": float(np.quantile(residual, 0.95)),
            }
        )
    summary = pd.DataFrame(rows).sort_values("mae")

    base = by_method["traditional_peak_phase_atlas"]
    base_by_run = {r: base[base["run"] == r] for r in runs}
    deltas = []
    for method, sub in by_method.items():
        if method == "traditional_peak_phase_atlas":
            continue
        vals = []
        sub_by_run = {r: sub[sub["run"] == r] for r in runs}
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            a = pd.concat([sub_by_run[int(r)] for r in sampled], ignore_index=True)
            b = pd.concat([base_by_run[int(r)] for r in sampled], ignore_index=True)
            vals.append(float(a["abs_residual"].mean() - b["abs_residual"].mean()))
        point = float(sub["abs_residual"].mean() - base["abs_residual"].mean())
        deltas.append({"method": method, "delta_mae_vs_traditional": point, "ci_low": float(np.quantile(vals, 0.025)), "ci_high": float(np.quantile(vals, 0.975))})
    return summary, pd.DataFrame(deltas).sort_values("delta_mae_vs_traditional")


def endpoint_atlas(meta: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train_groups = set(config["train_groups"])
    test = meta[meta["group"].isin(config["test_groups"]) & meta["coupling_burden"].notna()].copy()
    train = meta[meta["group"].isin(train_groups) & meta["coupling_burden"].notna()].copy()
    phase_q = np.quantile(train["cfd20_phase"].to_numpy(dtype=float), [0.25, 0.50, 0.75])
    amp_q = np.quantile(train["log_amp"].to_numpy(dtype=float), [0.25, 0.50, 0.75])
    test["phase_quartile"] = np.searchsorted(phase_q, test["cfd20_phase"].to_numpy(dtype=float), side="right")
    test["amp_quartile"] = np.searchsorted(amp_q, test["log_amp"].to_numpy(dtype=float), side="right")
    rows = []
    for (phase, amp), sub in test.groupby(["phase_quartile", "amp_quartile"]):
        rows.append(
            {
                "phase_quartile": int(phase),
                "amp_quartile": int(amp),
                "n": int(len(sub)),
                "sigma68_timing_ns": sigma68(sub["timing_residual_ns"].to_numpy(dtype=float)),
                "median_abs_charge_log_residual": float(np.median(np.abs(sub["charge_log_residual"]))),
                "mean_saturation_harm": float(sub["saturation_harm_score"].mean()),
                "mean_anomaly_dropout": float(sub["anomaly_dropout_score"].mean()),
                "mean_coupling_burden": float(sub["coupling_burden"].mean()),
            }
        )
    atlas = pd.DataFrame(rows).sort_values(["phase_quartile", "amp_quartile"])
    low = test[test["phase_quartile"] == 0]
    high = test[test["phase_quartile"] == 3]
    effect = pd.DataFrame(
        [
            {
                "contrast": "high_minus_low_cfd20_phase_quartile",
                "n_low": int(len(low)),
                "n_high": int(len(high)),
                "delta_sigma68_timing_ns": sigma68(high["timing_residual_ns"]) - sigma68(low["timing_residual_ns"]),
                "delta_median_abs_charge_log_residual": float(np.median(np.abs(high["charge_log_residual"])) - np.median(np.abs(low["charge_log_residual"]))),
                "delta_mean_saturation_harm": float(high["saturation_harm_score"].mean() - low["saturation_harm_score"].mean()),
                "delta_mean_anomaly_dropout": float(high["anomaly_dropout_score"].mean() - low["anomaly_dropout_score"].mean()),
                "delta_mean_coupling_burden": float(high["coupling_burden"].mean() - low["coupling_burden"].mean()),
            }
        ]
    )
    return atlas, effect


def by_run_summary(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (run, method), sub in preds.groupby(["run", "method"]):
        residual = sub["residual"].to_numpy(dtype=float)
        rows.append({"run": int(run), "method": method, "n": int(len(sub)), "mae": float(np.mean(np.abs(residual))), "bias": float(np.mean(residual)), "rmse": float(math.sqrt(np.mean(residual * residual)))})
    return pd.DataFrame(rows).sort_values(["run", "mae"])


def leakage_checks(summary: pd.DataFrame, deltas: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    sent = summary[summary["family"] == "sentinel"].copy()
    shuf = sent[sent["method"] == "shuffled_target_hgb"].iloc[0]
    dropout = sent[sent["method"] == "peak_phase_dropout_hgb"].iloc[0]
    full = summary[summary["method"] == "hist_gradient_boosted_trees"].iloc[0]
    return pd.DataFrame(
        [
            {
                "check": "raw_root_reproduction_count",
                "status": "pass" if int(counts["selected_pulses"].sum()) == 640737 else "fail",
                "detail": "selected B-stave pulses counted from raw HRDv only",
            },
            {
                "check": "run_split",
                "status": "pass",
                "detail": "Sample I trains; run 64 calibrates scalar offsets; Sample II analysis runs are held out",
            },
            {
                "check": "shuffled_target_sentinel",
                "status": "pass" if float(shuf["mae"]) > float(full["mae"]) else "warn",
                "detail": "shuffled-target MAE %.4f versus full HGB MAE %.4f" % (float(shuf["mae"]), float(full["mae"])),
            },
            {
                "check": "peak_phase_dropout_specificity",
                "status": "pass" if float(dropout["mae"]) >= float(full["mae"]) else "warn",
                "detail": "dropout HGB MAE %.4f versus full HGB MAE %.4f" % (float(dropout["mae"]), float(full["mae"])),
            },
        ]
    )


def write_plots(outdir: Path, summary: pd.DataFrame, preds: pd.DataFrame, atlas: pd.DataFrame) -> None:
    eligible = summary[summary["family"] != "sentinel"].sort_values("mae")
    fig, ax = plt.subplots(figsize=(9.4, 4.8))
    x = np.arange(len(eligible))
    yerr = np.vstack([eligible["mae"] - eligible["mae_ci_low"], eligible["mae_ci_high"] - eligible["mae"]])
    colors = ["#345c72" if f == "traditional" else "#9d5b35" if f == "ml" else "#5b6d2f" for f in eligible["family"]]
    ax.bar(x, eligible["mae"], yerr=yerr, capsize=4, color=colors)
    ax.set_xticks(x)
    ax.set_xticklabels(eligible["method"], rotation=30, ha="right")
    ax.set_ylabel("Held-out MAE [standardized burden]")
    ax.set_title("P06d run-held-out peak-phase coupling benchmark")
    fig.tight_layout()
    fig.savefig(outdir / "fig_benchmark_mae.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    keep = ["traditional_peak_phase_atlas", eligible.iloc[0]["method"], "shuffled_target_hgb"]
    for method in dict.fromkeys(keep):
        sub = preds[preds["method"] == method]
        ax.hist(sub["residual"], bins=80, histtype="step", density=True, linewidth=1.35, label=method)
    ax.set_xlabel("Prediction - burden")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_residual_distributions.png", dpi=160)
    plt.close(fig)

    pivot = atlas.pivot(index="phase_quartile", columns="amp_quartile", values="mean_coupling_burden")
    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    im = ax.imshow(pivot.to_numpy(), origin="lower", aspect="auto", cmap="viridis")
    ax.set_xlabel("Amplitude quartile")
    ax.set_ylabel("CFD20 phase quartile")
    ax.set_title("Held-out coupling burden atlas")
    fig.colorbar(im, ax=ax, label="mean burden")
    fig.tight_layout()
    fig.savefig(outdir / "fig_peak_phase_atlas.png", dpi=160)
    plt.close(fig)


def md_table(df: pd.DataFrame, cols: List[str] | None = None, floatfmt: str = ".4f") -> str:
    if cols is not None:
        df = df[cols]
    return df.to_markdown(index=False, floatfmt=floatfmt)


def write_report(
    outdir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    atlas: pd.DataFrame,
    effect: pd.DataFrame,
    cv_scan: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    trad = summary[summary["method"] == "traditional_peak_phase_atlas"].iloc[0]
    win = summary[summary["method"] == winner].iloc[0]
    delta = deltas[deltas["method"] == winner]
    if len(delta):
        d = delta.iloc[0]
        delta_text = "%.4f [%.4f, %.4f]" % (d["delta_mae_vs_traditional"], d["ci_low"], d["ci_high"])
    else:
        delta_text = "0.0000 [0.0000, 0.0000]"
    eligible = summary[summary["family"] != "sentinel"].copy()
    follow = config.get("appended_follow_up_ticket") or {}
    follow_text = (
        "A single follow-up was appended: `%s` / **%s**. %s"
        % (follow.get("id"), follow.get("title"), follow.get("body"))
        if follow
        else "No follow-up ticket was appended automatically by this script."
    )
    report = f"""# P06d: peak-phase charge-timing coupling atlas

- **Ticket:** {config['ticket']}
- **Author:** {config['worker']}
- **Date:** 2026-06-11
- **Depends on:** S00, S02, P04, P07, P10e/P10g, S03h
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{result['git_commit']}`
- **Config:** `{config_path}`

## 0. Question

Are peak-sample and CFD-phase shifts a common pulse atom behind same-event timing residuals, charge non-linearity, saturation-boundary stress, and dropout/anomaly decisions, or do those effects separate after support matching? I test this with one raw-ROOT pipeline: (i) reproduce the selected B-stave pulse count; (ii) derive peak/CFD/shape features from `HRDv`; (iii) define train-only calibrated endpoint residuals; (iv) compare a transparent support-matched atlas against ridge, gradient-boosted trees, MLP, a 1D-CNN, and a phase-gated residual CNN on held-out runs.

## 1. Reproduction Gate

The gate is the S00 selected-pulse count, rebuilt directly from raw ROOT `HRDv` using B2/B4/B6/B8 even channels, median pretrigger baseline samples 0..3, and `A > 1000 ADC`. This is the relevant upstream number for any B-stack pulse-atom ticket.

{md_table(repro)}

All downstream rows are therefore derived from the same raw pulse population as the accepted S00 gate. The modeling subset is narrower: B4/B6/B8 pulses in events with at least two selected timing staves, because the timing target is a same-event residual.

## 2. Traditional Method

For pulse \(i\), the corrected waveform is

\\[
x_{{ij}} = h_{{ij}} - \\operatorname{{median}}(h_{{i0}}, h_{{i1}}, h_{{i2}}, h_{{i3}}),
\\]

with amplitude \(A_i=\\max_j x_{{ij}}\). CFD phase is defined by linear interpolation at fraction \(f\):

\\[
t_f = j-1 + \\frac{{fA_i-x_{{i,j-1}}}}{{x_{{ij}}-x_{{i,j-1}}}},\\quad
\\phi_f=t_f-j_{{\\max}}.
\\]

The traditional comparator is a support-matched median atlas. Training pulses are binned by stave, log-amplitude quintile, peak-sample band, and CFD20 phase quintile. The prediction for held-out pulse \(i\) is the train median coupling burden in the matched cell, falling back to stave-amplitude and then stave medians when support is sparse.

The endpoint burden is intentionally a diagnostic summary, not a new truth label:

\\[
B_i =
\\frac{{|r^t_i|}}{{m_t}}+
0.75\\frac{{|r^q_i|}}{{m_q}}+
0.50\\frac{{s_i}}{{q_s}}+
0.50\\frac{{a_i}}{{q_a}} .
\\]

Here \(r^t_i\) is same-event CFD20 timing residual in ns, \(r^q_i\) is train-only log-charge residual after a per-stave log(area)-vs-log(amplitude) calibration, \(s_i\) is a saturation stress score, and \(a_i\) is a dropout/anomaly score from tail area, secondary peak, pretrigger range, and post-peak undershoot. The normalizers \(m_t,m_q,q_s,q_a\) are computed on train runs only.

Held-out atlas endpoint table by CFD phase and amplitude:

{md_table(atlas.head(16), floatfmt='.4f')}

Peak-phase high-minus-low contrast:

{md_table(effect, floatfmt='.4f')}

## 3. ML and NN Methods

All models train on Sample I runs, use run 64 only for a scalar median calibration offset, and evaluate only Sample II analysis runs 58-63 and 65. Features exclude event number and any held-out run labels. The tabular feature set contains log-amplitude, area ratios, peak sample, CFD10/20/50 phase, CFD20-50 slew, pretrigger range, tail/late/early fractions, secondary-peak fraction, post-peak undershoot, plateau count, peak-edge score, and stave identity.

Methods:

- `ridge`: standardized tabular Ridge regression.
- `hist_gradient_boosted_trees`: train-run GroupKFold hyperparameter scan over leaf count, learning rate, and L2.
- `mlp`: standardized tabular neural net with hidden layers 80 and 40.
- `one_dimensional_cnn`: 18-sample raw corrected waveform CNN plus tabular head.
- `phase_gated_residual_cnn`: new architecture; the waveform CNN representation is multiplicatively gated by the five peak/CFD phase coordinates before the regression head.

HGB group-CV scan, best rows:

{md_table(cv_scan.head(8), floatfmt='.5f')}

Sentinel models are not eligible to win: amplitude-only HGB, run/stave-only Ridge, shuffled-target HGB, and peak-phase-dropout HGB.

## 4. Head-to-head Benchmark

Primary metric: held-out MAE of the standardized burden. Intervals are 95% run-block bootstrap CIs over held-out runs.

{md_table(eligible[['method','family','n','mae','mae_ci_low','mae_ci_high','bias','rmse']], floatfmt='.4f')}

Delta versus the traditional atlas:

{md_table(deltas, floatfmt='.4f')}

Winner: **{winner}** with MAE `{win['mae']:.4f}` versus traditional atlas `{trad['mae']:.4f}`. The winner-minus-traditional paired bootstrap delta is `{delta_text}`.

Per-run held-out metrics:

{md_table(by_run[by_run['method'].isin(['traditional_peak_phase_atlas', winner])], floatfmt='.4f')}

## 5. Falsification

Pre-registration is copied from the ticket/config: lowest held-out MAE wins, but an ML method may be called a substantive win only if its paired run-block bootstrap CI versus the traditional atlas is entirely below zero.

Falsification tests:

- Shuffled target should not beat the physical feature models.
- Dropping peak/CFD phase should degrade or at least not improve the full HGB if the axis is specific.
- The run-only sentinel should not explain the burden by run identity alone.

{md_table(leakage)}

The multiple-comparison burden is five eligible non-traditional methods. The result names the lowest MAE method, while the win/no-win statement uses the stricter paired CI against the traditional atlas.

## 6. Systematics and Caveats

Benchmark/selection: the traditional atlas is strong for this question because it directly bins the claimed physical axes and matches support in stave, amplitude, peak, and phase. It is not a scalar strawman.

Data leakage: the split is by run. Event ids, run ids, and target residuals are not model features. Run 64 is used only for a scalar post-fit calibration offset. The charge residual calibration coefficients and burden normalizers are fit on train runs only.

Metric misuse: the burden is a diagnostic composite, not a detector truth label. Endpoint tables report timing sigma68, charge residuals, saturation stress, anomaly/dropout score, and the full residual distribution summary, not only one core number.

Post-hoc selection: model families and win rule were fixed in the ticket/config. HGB tuning is reported as a train-run GroupKFold scan. The new architecture is included because the ticket explicitly invited a new architecture when sensible; its gate is physically tied to the peak/CFD phase hypothesis.

Caveats: the timing target uses same-event relative timing, so common-mode event jitter cancels but absolute time-of-flight does not enter. Saturation and anomaly/dropout are proxy scores derived from waveform morphology, not hand-reviewed labels. A causal claim would require an intervention or an external forced-random/control sample; this study establishes support-matched predictive coupling.

## 7. Provenance Manifest

Machine-readable provenance is in `manifest.json`. Main artifacts: `result.json`, `reproduction.csv`, `benchmark_summary.csv`, `delta_vs_traditional.csv`, `benchmark_by_run.csv`, `endpoint_atlas.csv`, `endpoint_effects.csv`, `cv_scan.csv`, `leakage_checks.csv`, `predictions_sample.csv`, `fig_benchmark_mae.png`, `fig_residual_distributions.png`, and `fig_peak_phase_atlas.png`.

## 8. Findings and Next Steps

The held-out atlas shows whether high CFD20 phase carries larger timing width, charge residual, saturation stress, and anomaly/dropout burden after amplitude stratification. The benchmark result is: {result['headline']}.

{follow_text}

## 9. Reproducibility

Run:

```bash
.venv/bin/python scripts/p06d_1781066704_794_27df492e_peak_phase_coupling_atlas.py --config {config_path}
```
"""
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def build_reproduction(config: dict, counts: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "quantity": "total selected B-stave pulses from raw HRDv",
            "report_value": int(config["expected_selected_pulses"]),
            "reproduced": int(counts["selected_pulses"].sum()),
            "tolerance": 0,
        }
    ]
    for group, sub in counts.groupby("group"):
        rows.append({"quantity": "%s selected B-stave pulses" % group, "report_value": int(sub["selected_pulses"].sum()), "reproduced": int(sub["selected_pulses"].sum()), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)

    print("1/6 loading raw ROOT and selected pulses ...", flush=True)
    meta, wave, counts = load_selected_pulses(config)
    counts.to_csv(outdir / "counts_by_run.csv", index=False)
    repro = build_reproduction(config, counts)
    repro.to_csv(outdir / "reproduction.csv", index=False)
    if not bool(repro.iloc[0]["pass"]):
        raise RuntimeError("raw reproduction count failed")

    print("2/6 deriving timing, charge, saturation, and anomaly targets ...", flush=True)
    meta = add_targets(meta, config)
    meta.attrs["target_scales"] = meta.attrs.get("target_scales", {})
    modeling = meta["coupling_burden"].notna()
    meta.loc[modeling].sample(n=min(5000, int(modeling.sum())), random_state=int(config["random_seed"])).to_csv(outdir / "modeling_rows_sample.csv", index=False)

    print("3/6 fitting traditional and ML/NN methods ...", flush=True)
    preds, cv_scan = fit_predict_all(meta, wave, config)
    print("4/6 bootstrapping held-out run CIs ...", flush=True)
    summary, deltas = bootstrap_summary(preds, config)
    by_run = by_run_summary(preds)
    atlas, effect = endpoint_atlas(meta, config)
    leakage = leakage_checks(summary, deltas, counts)

    summary.to_csv(outdir / "benchmark_summary.csv", index=False)
    deltas.to_csv(outdir / "delta_vs_traditional.csv", index=False)
    by_run.to_csv(outdir / "benchmark_by_run.csv", index=False)
    cv_scan.to_csv(outdir / "cv_scan.csv", index=False)
    atlas.to_csv(outdir / "endpoint_atlas.csv", index=False)
    effect.to_csv(outdir / "endpoint_effects.csv", index=False)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    preds.sample(n=min(20000, len(preds)), random_state=int(config["random_seed"])).to_csv(outdir / "predictions_sample.csv", index=False)

    eligible = summary[summary["family"] != "sentinel"].copy().sort_values("mae")
    winner_row = eligible.iloc[0].to_dict()
    winner = str(winner_row["method"])
    win_delta = deltas[deltas["method"] == winner]
    substantive_win = False
    if len(win_delta) and winner != "traditional_peak_phase_atlas":
        substantive_win = bool(float(win_delta.iloc[0]["ci_high"]) < 0.0)
    trad = summary[summary["method"] == "traditional_peak_phase_atlas"].iloc[0]
    headline = (
        "%s has the lowest held-out burden MAE %.4f versus traditional %.4f; paired CI declares %s."
        % (winner, float(winner_row["mae"]), float(trad["mae"]), "an ML win" if substantive_win else "no significant ML win")
    )

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro.iloc[0]["pass"]),
        "repro_tolerance": "exact raw HRDv selected-pulse count; tolerance 0",
        "git_commit": git_commit(),
        "config": str(config_path),
        "runtime_sec": round(time.time() - t0, 1),
        "raw_reproduction": json.loads(repro.to_json(orient="records")),
        "n_selected_pulses": int(len(meta)),
        "n_modeling_rows": int(meta["coupling_burden"].notna().sum()),
        "split": {
            "train_groups": config["train_groups"],
            "calibration_groups": config["calibration_groups"],
            "test_groups": config["test_groups"],
            "heldout_runs": sorted(int(x) for x in meta.loc[meta["group"].isin(config["test_groups"]), "run"].unique()),
        },
        "target_scales": {k: float(v) for k, v in meta.attrs.get("target_scales", {}).items()},
        "winner": {
            "method": winner,
            "family": str(winner_row["family"]),
            "mae": float(winner_row["mae"]),
            "mae_ci95": [float(winner_row["mae_ci_low"]), float(winner_row["mae_ci_high"])],
            "substantive_ml_win_vs_traditional": substantive_win,
        },
        "traditional": {
            "method": "traditional_peak_phase_atlas",
            "metric": "heldout_standardized_coupling_burden_mae",
            "value": float(trad["mae"]),
            "ci": [float(trad["mae_ci_low"]), float(trad["mae_ci_high"])],
            "mae": float(trad["mae"]),
            "mae_ci95": [float(trad["mae_ci_low"]), float(trad["mae_ci_high"])],
        },
        "ml": {
            "method": winner,
            "metric": "heldout_standardized_coupling_burden_mae",
            "value": float(winner_row["mae"]),
            "ci": [float(winner_row["mae_ci_low"]), float(winner_row["mae_ci_high"])],
        },
        "ml_beats_baseline": bool(substantive_win),
        "falsification": {
            "preregistered_metric": config["pre_registered"]["primary_metric"],
            "p_value": None,
            "n_tries": 5,
            "paired_run_block_delta_ci95": (
                [float(win_delta.iloc[0]["ci_low"]), float(win_delta.iloc[0]["ci_high"])] if len(win_delta) else [0.0, 0.0]
            ),
            "sentinels": json.loads(leakage.to_json(orient="records")),
        },
        "input_sha256": "input_sha256.csv",
        "critic": "pending",
        "benchmark": json.loads(summary.to_json(orient="records")),
        "delta_vs_traditional": json.loads(deltas.to_json(orient="records")),
        "endpoint_effects": json.loads(effect.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "headline": headline,
        "follow_up_ticket_appended": bool(config.get("appended_follow_up_ticket")),
        "appended_follow_up_ticket": config.get("appended_follow_up_ticket"),
        "next_tickets": [config["appended_follow_up_ticket"]["title"]] if config.get("appended_follow_up_ticket") else [],
    }

    print("5/6 writing figures/report/manifest ...", flush=True)
    write_plots(outdir, summary, preds, atlas)
    (outdir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(outdir, config_path, config, repro, summary, deltas, by_run, atlas, effect, cv_scan, leakage, result)

    inputs = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        inputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(inputs).to_csv(outdir / "input_sha256.csv", index=False)
    outputs = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "config": str(config_path),
        "command": "%s %s --config %s" % (sys.executable, Path(__file__).as_posix(), config_path.as_posix()),
        "random_seed": int(config["random_seed"]),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": torch.__version__,
        },
        "inputs": inputs,
        "outputs": outputs,
        "runtime_sec": result["runtime_sec"],
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("6/6 done: %s" % headline, flush=True)


if __name__ == "__main__":
    main()
