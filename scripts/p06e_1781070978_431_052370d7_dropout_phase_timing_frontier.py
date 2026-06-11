#!/usr/bin/env python3
"""P06e: dropout-phase timing irrecoverability frontier.

This study reads raw B-stack ROOT, reproduces the S00 selected-pulse count,
injects controlled sample dropouts into real clean pulses, then benchmarks a
strong conventional repair against ridge, gradient-boosted trees, MLP, 1D-CNN,
and a phase-gated CNN under a train-by-run / held-out-by-run split.
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
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p06e")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


CONFIG_DEFAULT = "configs/p06e_1781070978_431_052370d7_dropout_phase_timing_frontier.json"
STAVE_NAMES = ["B2", "B4", "B6", "B8"]


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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def group_for_run(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / ("hrdb_run_%04d.root" % int(run))


def iter_batches(path: Path, step_size: int = 25000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd_time_samples(wave: np.ndarray, amp: np.ndarray, fraction: float) -> np.ndarray:
    wave = np.asarray(wave, dtype=float)
    amp = np.asarray(amp, dtype=float)
    threshold = amp * float(fraction)
    ge = wave >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(wave), np.nan, dtype=float)
    for idx in np.where(valid)[0]:
        j = int(first[idx])
        if j <= 0:
            out[idx] = float(j)
            continue
        y0, y1 = float(wave[idx, j - 1]), float(wave[idx, j])
        denom = y1 - y0
        out[idx] = float(j) if denom <= 0.0 else (j - 1) + (threshold[idx] - y0) / denom
    return out


def sigma68(values: Sequence[float]) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    center = float(np.median(values))
    return float(np.percentile(np.abs(values - center), 68.0))


def full_rms(values: Sequence[float]) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float(math.sqrt(np.mean(values * values)))


def one_hot(values: np.ndarray, n: int) -> np.ndarray:
    values = values.astype(int)
    out = np.zeros((len(values), n), dtype=float)
    good = (values >= 0) & (values < n)
    out[np.where(good)[0], values[good]] = 1.0
    return out


def extract_selected(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, pd.DataFrame]:
    groups = group_for_run(config)
    baseline_idx = np.asarray(config["baseline_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    channels = np.asarray([int(config["staves"][name]) for name in STAVE_NAMES], dtype=int)
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    count_rows: List[dict] = []
    hash_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        hash_rows.append({"file": str(path), "sha256": sha256_file(path)})
        counts = {"run": int(run), "group": groups[int(run)], "events_total": 0, "selected_pulses": 0}
        counts.update({name: 0 for name in STAVE_NAMES})
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            base = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - base[..., None]
            amp = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            pos = np.clip(corrected, 0.0, None)
            charge = pos.sum(axis=-1)
            selected = amp > cut
            counts["events_total"] += int(len(eventno))
            counts["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(STAVE_NAMES):
                counts[name] += int(selected[:, i].sum())
            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue
            sel = corrected[event_idx, stave_idx, :].astype(np.float32)
            sel_amp = amp[event_idx, stave_idx].astype(float)
            sel_peak = peak[event_idx, stave_idx].astype(int)
            cfd = cfd_time_samples(sel, sel_amp, float(config["cfd_fraction"]))
            total = np.maximum(charge[event_idx, stave_idx], 1.0)
            frames.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "group": groups[int(run)],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                        "stave_idx": stave_idx.astype(int),
                        "amplitude_adc": sel_amp,
                        "log_amp": np.log(np.maximum(sel_amp, 1.0)),
                        "clean_peak": sel_peak,
                        "clean_charge": total,
                        "area_over_amp": total / np.maximum(sel_amp, 1.0),
                        "tail_fraction": np.clip(sel[:, 12:], 0.0, None).sum(axis=1) / total,
                        "early_fraction": np.clip(sel[:, :6], 0.0, None).sum(axis=1) / total,
                        "clean_time_sample": cfd,
                    }
                )
            )
            waves.append(sel)
        count_rows.append(counts)
        print("run %04d: %d selected pulses" % (run, counts["selected_pulses"]))

    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(count_rows), pd.DataFrame(hash_rows)


def peak_region(peak: np.ndarray) -> np.ndarray:
    return np.where(peak <= 5, "early", np.where(peak <= 9, "central", "late"))


def stratified_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["random_seed"]))
    work = meta[np.isfinite(meta["clean_time_sample"].to_numpy(dtype=float))].copy()
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    work["amp_bin"] = np.clip(np.searchsorted(bins, work["amplitude_adc"].to_numpy(), side="right") - 1, 0, len(bins) - 2)
    work["peak_region"] = peak_region(work["clean_peak"].to_numpy(dtype=int))
    chosen: List[np.ndarray] = []
    cap = int(config["max_sample_per_stratum"])
    for _, group in work.groupby(["run", "stave_idx", "amp_bin", "peak_region"], sort=True):
        idx = group.index.to_numpy()
        if len(idx) > cap:
            idx = rng.choice(idx, size=cap, replace=False)
        chosen.append(idx)
    out = np.sort(np.concatenate(chosen).astype(int))
    return out


def inject_dropouts(meta: pd.DataFrame, wave: np.ndarray, indices: np.ndarray, config: dict) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    base = meta.iloc[indices].reset_index(drop=True)
    clean = wave[indices].astype(float)
    rows: List[pd.DataFrame] = []
    corrupt_blocks: List[np.ndarray] = []
    mask_blocks: List[np.ndarray] = []
    nsamp = int(config["samples_per_channel"])
    peaks = base["clean_peak"].to_numpy(dtype=int)
    for case_idx, case in enumerate(config["dropout_cases"]):
        mask = np.zeros_like(clean, dtype=bool)
        for offset in case["offsets"]:
            pos = np.clip(peaks + int(offset), len(config["baseline_samples"]), nsamp - 1)
            mask[np.arange(len(mask)), pos] = True
        corrupt = clean.copy()
        corrupt[mask] = 0.0
        block = base.copy()
        block["dropout_case"] = str(case["name"])
        block["dropout_phase"] = str(case["phase"])
        block["dropout_idx"] = int(case_idx)
        block["mask_count"] = mask.sum(axis=1).astype(int)
        block["mask_center_sample"] = np.where(mask.any(axis=1), (mask * np.arange(nsamp)).sum(axis=1) / np.maximum(mask.sum(axis=1), 1), -1.0)
        rows.append(block)
        corrupt_blocks.append(corrupt.astype(np.float32))
        mask_blocks.append(mask)
    inj = pd.concat(rows, ignore_index=True)
    clean_repeat = np.vstack([clean for _ in config["dropout_cases"]]).astype(np.float32)
    corrupt = np.vstack(corrupt_blocks).astype(np.float32)
    mask = np.vstack(mask_blocks)
    return inj, clean_repeat, corrupt, mask


def interpolate_missing(wave: np.ndarray, mask: np.ndarray) -> np.ndarray:
    x = np.arange(wave.shape[1], dtype=float)
    filled = wave.astype(float).copy()
    for i in range(len(filled)):
        miss = mask[i]
        if not miss.any():
            continue
        keep = ~miss
        filled[i, miss] = np.interp(x[miss], x[keep], filled[i, keep])
    return filled


def amplitude_bin(values: np.ndarray, config: dict) -> np.ndarray:
    bins = np.asarray(config["amplitude_bins"], dtype=float)
    return np.clip(np.searchsorted(bins, values, side="right") - 1, 0, len(bins) - 2)


def build_templates(meta: pd.DataFrame, clean: np.ndarray, train_mask: np.ndarray, config: dict) -> Dict[Tuple[int, int, str], np.ndarray]:
    amp_bins = amplitude_bin(meta["amplitude_adc"].to_numpy(dtype=float), config)
    regions = peak_region(meta["clean_peak"].to_numpy(dtype=int))
    templates: Dict[Tuple[int, int, str], np.ndarray] = {}
    for stave in sorted(meta["stave_idx"].unique()):
        for abin in sorted(np.unique(amp_bins)):
            for region in sorted(np.unique(regions)):
                m = train_mask & (meta["stave_idx"].to_numpy() == stave) & (amp_bins == abin) & (regions == region)
                if int(m.sum()) < 12:
                    continue
                norm = clean[m] / np.maximum(meta.loc[m, "amplitude_adc"].to_numpy(dtype=float)[:, None], 1.0)
                templates[(int(stave), int(abin), str(region))] = np.median(norm, axis=0)
    return templates


def template_refit_wave(meta: pd.DataFrame, corrupt: np.ndarray, mask: np.ndarray, templates: Dict[Tuple[int, int, str], np.ndarray], config: dict) -> np.ndarray:
    amp_bins = amplitude_bin(meta["amplitude_adc"].to_numpy(dtype=float), config)
    regions = peak_region(meta["clean_peak"].to_numpy(dtype=int))
    out = corrupt.astype(float).copy()
    global_norm = corrupt / np.maximum(corrupt.max(axis=1)[:, None], 1.0)
    fallback = np.nanmedian(global_norm, axis=0)
    for i in range(len(corrupt)):
        tmpl = templates.get((int(meta.iloc[i]["stave_idx"]), int(amp_bins[i]), str(regions[i])), fallback)
        usable = (~mask[i]) & (tmpl > 0.02)
        if usable.sum() < 5:
            usable = ~mask[i]
        denom = float(np.dot(tmpl[usable], tmpl[usable]))
        scale = float(np.dot(corrupt[i, usable], tmpl[usable]) / denom) if denom > 1e-9 else float(max(corrupt[i].max(), 1.0))
        out[i] = max(scale, 1.0) * tmpl
        out[i, ~mask[i]] = corrupt[i, ~mask[i]]
    return out


def time_from_wave(wave: np.ndarray, config: dict) -> np.ndarray:
    amp = np.maximum(np.max(wave, axis=1), 1.0)
    return cfd_time_samples(wave, amp, float(config["cfd_fraction"]))


def train_case_winners(meta: pd.DataFrame, train_mask: np.ndarray, true_time: np.ndarray, candidates: Dict[str, np.ndarray], config: dict) -> Dict[str, str]:
    winners: Dict[str, str] = {}
    period = float(config["sample_period_ns"])
    for case in sorted(meta["dropout_case"].unique()):
        m = train_mask & (meta["dropout_case"].to_numpy() == case)
        best_name = None
        best_metric = float("inf")
        for name, pred_time in candidates.items():
            err = (pred_time[m] - true_time[m]) * period
            metric = sigma68(err)
            if metric < best_metric:
                best_name = name
                best_metric = metric
        winners[str(case)] = str(best_name)
    return winners


def apply_case_winners(meta: pd.DataFrame, candidates: Dict[str, np.ndarray], winners: Dict[str, str]) -> np.ndarray:
    out = np.full(len(meta), np.nan, dtype=float)
    cases = meta["dropout_case"].to_numpy(dtype=object)
    for case, method in winners.items():
        m = cases == case
        out[m] = candidates[method][m]
    return out


def add_calibration_offset(y_cal: np.ndarray, p_cal: np.ndarray, p_test: np.ndarray) -> np.ndarray:
    valid = np.isfinite(y_cal) & np.isfinite(p_cal)
    if int(valid.sum()) == 0:
        return p_test
    return p_test + float(np.median(y_cal[valid] - p_cal[valid]))


def feature_matrix(meta: pd.DataFrame, corrupt: np.ndarray, mask: np.ndarray, interp: np.ndarray, config: dict) -> Tuple[np.ndarray, List[str]]:
    obs_amp = np.maximum(interp.max(axis=1), 1.0)
    norm = corrupt / obs_amp[:, None]
    interp_norm = interp / obs_amp[:, None]
    pos = np.clip(interp, 0.0, None)
    pos_total = np.maximum(pos.sum(axis=1), 1.0)
    names = [f"corrupt_norm_{i}" for i in range(corrupt.shape[1])]
    names += [f"interp_norm_{i}" for i in range(interp.shape[1])]
    names += [f"mask_{i}" for i in range(mask.shape[1])]
    scalar = np.column_stack(
        [
            np.log(obs_amp),
            np.log(pos_total),
            interp.argmax(axis=1),
            meta["mask_count"].to_numpy(dtype=float),
            meta["mask_center_sample"].to_numpy(dtype=float),
            pos[:, :6].sum(axis=1) / pos_total,
            pos[:, 12:].sum(axis=1) / pos_total,
            one_hot(meta["stave_idx"].to_numpy(dtype=int), 4),
            one_hot(meta["dropout_idx"].to_numpy(dtype=int), int(meta["dropout_idx"].max()) + 1),
        ]
    )
    names += [
        "log_observed_amp",
        "log_observed_charge",
        "observed_peak",
        "mask_count",
        "mask_center_sample",
        "early_fraction",
        "tail_fraction",
    ]
    names += [f"stave_{i}" for i in range(4)]
    names += [f"case_{i}" for i in range(int(meta["dropout_idx"].max()) + 1)]
    return np.column_stack([norm, interp_norm, mask.astype(float), scalar]).astype(np.float32), names


def select_train_rows(idx: np.ndarray, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["random_seed"]) + 11)
    max_rows = int(config["ml_max_train_rows"])
    if len(idx) <= max_rows:
        return idx
    return np.sort(rng.choice(idx, size=max_rows, replace=False))


def cv_ridge(X: np.ndarray, y: np.ndarray, groups: np.ndarray, config: dict) -> Tuple[float, pd.DataFrame]:
    alphas = [0.01, 0.1, 1.0, 10.0, 100.0]
    cv = GroupKFold(n_splits=min(4, len(np.unique(groups))))
    rows = []
    for alpha in alphas:
        scores = []
        for tr, va in cv.split(X, y, groups=groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(X[tr], y[tr])
            scores.append(mean_absolute_error(y[va], model.predict(X[va])))
        rows.append({"method": "ridge", "alpha": float(alpha), "group_cv_mae_sample": float(np.mean(scores))})
    best = min(rows, key=lambda r: r["group_cv_mae_sample"])
    return float(best["alpha"]), pd.DataFrame(rows)


def cv_hgb(X: np.ndarray, y: np.ndarray, groups: np.ndarray, config: dict) -> Tuple[dict, pd.DataFrame]:
    grid = []
    for leaves in [15, 31, 63]:
        for lr in [0.04, 0.08]:
            for l2 in [0.0, 0.05]:
                grid.append({"max_leaf_nodes": leaves, "learning_rate": lr, "l2_regularization": l2})
    cv = GroupKFold(n_splits=min(4, len(np.unique(groups))))
    rows = []
    for params in grid:
        scores = []
        for tr, va in cv.split(X, y, groups=groups):
            model = HistGradientBoostingRegressor(max_iter=160, random_state=int(config["random_seed"]), **params)
            model.fit(X[tr], y[tr])
            scores.append(mean_absolute_error(y[va], model.predict(X[va])))
        row = dict(params)
        row.update({"method": "hist_gradient_boosted_trees", "group_cv_mae_sample": float(np.mean(scores))})
        rows.append(row)
    best = min(rows, key=lambda r: r["group_cv_mae_sample"])
    return best, pd.DataFrame(rows)


class WaveNet(nn.Module):
    def __init__(self, n_scalar: int, gated: bool):
        super().__init__()
        self.gated = bool(gated)
        self.conv = nn.Sequential(
            nn.Conv1d(2, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        if self.gated:
            self.gate = nn.Sequential(nn.Linear(3, 16), nn.ReLU(), nn.Linear(16, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(24 + n_scalar, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, seq: torch.Tensor, scalar: torch.Tensor, phase: torch.Tensor) -> torch.Tensor:
        h = self.conv(seq).squeeze(-1)
        if self.gated:
            h = h * (0.5 + self.gate(phase))
        return self.head(torch.cat([h, scalar], dim=1)).squeeze(1)


def fit_torch(
    method: str,
    meta: pd.DataFrame,
    corrupt: np.ndarray,
    mask: np.ndarray,
    scalar_X: np.ndarray,
    train_idx: np.ndarray,
    cal_idx: np.ndarray,
    test_idx: np.ndarray,
    y: np.ndarray,
    config: dict,
) -> Tuple[np.ndarray, pd.DataFrame]:
    seed = int(config["random_seed"]) + (73 if method == "phase_gated_cnn" else 41)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    obs_amp = np.maximum(corrupt.max(axis=1), 1.0)
    norm = (corrupt / obs_amp[:, None]).astype(np.float32)
    seq = np.stack([norm, mask.astype(np.float32)], axis=1)
    mu = scalar_X[train_idx].mean(axis=0)
    sd = scalar_X[train_idx].std(axis=0)
    sd[sd == 0.0] = 1.0
    scalar = ((scalar_X - mu) / sd).astype(np.float32)
    phase_raw = meta[["dropout_idx", "mask_count", "mask_center_sample"]].to_numpy(dtype=np.float32)
    ph_mu = phase_raw[train_idx].mean(axis=0)
    ph_sd = phase_raw[train_idx].std(axis=0)
    ph_sd[ph_sd == 0.0] = 1.0
    phase = ((phase_raw - ph_mu) / ph_sd).astype(np.float32)
    y_train = y[train_idx].astype(np.float32)
    y_mean = float(np.mean(y_train))
    target = y_train - y_mean
    net = WaveNet(scalar.shape[1], gated=(method == "phase_gated_cnn"))
    opt = torch.optim.AdamW(net.parameters(), lr=0.0025, weight_decay=1.0e-4)
    loss_fn = nn.SmoothL1Loss(beta=0.20)
    batch = int(config["torch_batch_size"])
    order = np.arange(len(train_idx))
    rows = []
    for epoch in range(int(config["torch_epochs"])):
        rng.shuffle(order)
        losses = []
        net.train()
        for start in range(0, len(order), batch):
            loc = order[start : start + batch]
            idx = train_idx[loc]
            xb = torch.from_numpy(seq[idx])
            sb = torch.from_numpy(scalar[idx])
            pb = torch.from_numpy(phase[idx])
            yb = torch.from_numpy(target[loc])
            opt.zero_grad()
            loss = loss_fn(net(xb, sb, pb), yb)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().item()))
        rows.append({"method": method, "epoch": epoch + 1, "train_smooth_l1": float(np.mean(losses))})
    net.eval()
    with torch.no_grad():
        p_cal = net(torch.from_numpy(seq[cal_idx]), torch.from_numpy(scalar[cal_idx]), torch.from_numpy(phase[cal_idx])).numpy() + y_mean
        p_test = net(torch.from_numpy(seq[test_idx]), torch.from_numpy(scalar[test_idx]), torch.from_numpy(phase[test_idx])).numpy() + y_mean
    return add_calibration_offset(y[cal_idx], p_cal, p_test), pd.DataFrame(rows)


def fit_methods(meta: pd.DataFrame, clean: np.ndarray, corrupt: np.ndarray, mask: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    true_time = meta["clean_time_sample"].to_numpy(dtype=float)
    interp = interpolate_missing(corrupt, mask)
    train_mask = meta["group"].isin(config["train_groups"]).to_numpy()
    cal_mask = meta["group"].isin(config["calibration_groups"]).to_numpy()
    test_mask = meta["group"].isin(config["test_groups"]).to_numpy()
    train_idx_all = np.where(train_mask)[0]
    train_idx = select_train_rows(train_idx_all, config)
    cal_idx = np.where(cal_mask)[0]
    test_idx = np.where(test_mask)[0]

    templates = build_templates(meta, clean, train_mask, config)
    template_wave = template_refit_wave(meta, corrupt, mask, templates, config)
    candidate_times = {
        "interpolation_cfd": time_from_wave(interp, config),
        "template_refit_cfd": time_from_wave(template_wave, config),
    }
    case_winners = train_case_winners(meta, train_mask, true_time, candidate_times, config)
    trad_time_all = apply_case_winners(meta, candidate_times, case_winners)
    trad_pred_test = add_calibration_offset(true_time[cal_idx], trad_time_all[cal_idx], trad_time_all[test_idx])

    X, feature_names = feature_matrix(meta, corrupt, mask, interp, config)
    y = true_time
    groups = meta.iloc[train_idx]["run"].to_numpy(dtype=int)
    cv_tables: List[pd.DataFrame] = []
    preds: List[pd.DataFrame] = []

    base_cols = ["run", "group", "eventno", "stave", "stave_idx", "dropout_case", "dropout_phase", "mask_count", "mask_center_sample", "clean_time_sample"]
    base = meta.iloc[test_idx][base_cols].copy().reset_index(drop=True)
    period = float(config["sample_period_ns"])

    def add_pred(method: str, family: str, pred_sample: np.ndarray, eligible: bool = True) -> None:
        tmp = base.copy()
        tmp["method"] = method
        tmp["family"] = family
        tmp["eligible_winner"] = bool(eligible)
        tmp["pred_time_sample"] = pred_sample
        tmp["error_ns"] = (tmp["pred_time_sample"].to_numpy(dtype=float) - tmp["clean_time_sample"].to_numpy(dtype=float)) * period
        tmp["abs_error_ns"] = np.abs(tmp["error_ns"].to_numpy(dtype=float))
        preds.append(tmp)

    add_pred("traditional_phase_selected_template_interp", "traditional", trad_pred_test, True)
    add_pred("corrupted_cfd", "sentinel", add_calibration_offset(y[cal_idx], time_from_wave(corrupt, config)[cal_idx], time_from_wave(corrupt, config)[test_idx]), False)

    alpha, ridge_cv = cv_ridge(X[train_idx], y[train_idx], groups, config)
    cv_tables.append(ridge_cv)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    ridge.fit(X[train_idx], y[train_idx])
    add_pred("ridge", "ml", add_calibration_offset(y[cal_idx], ridge.predict(X[cal_idx]), ridge.predict(X[test_idx])), True)

    hgb_params, hgb_cv = cv_hgb(X[train_idx], y[train_idx], groups, config)
    cv_tables.append(hgb_cv)
    hgb_fit_params = {k: hgb_params[k] for k in ["max_leaf_nodes", "learning_rate", "l2_regularization"]}
    hgb = HistGradientBoostingRegressor(max_iter=220, random_state=int(config["random_seed"]), **hgb_fit_params)
    hgb.fit(X[train_idx], y[train_idx])
    add_pred("hist_gradient_boosted_trees", "ml", add_calibration_offset(y[cal_idx], hgb.predict(X[cal_idx]), hgb.predict(X[test_idx])), True)

    mlp_rows = []
    mlp_options = [(64,), (96, 48)]
    cv = GroupKFold(n_splits=min(4, len(np.unique(groups))))
    best_mlp = None
    for hidden in mlp_options:
        scores = []
        for tr, va in cv.split(X[train_idx], y[train_idx], groups=groups):
            model = make_pipeline(
                StandardScaler(),
                MLPRegressor(hidden_layer_sizes=hidden, alpha=3e-4, batch_size=512, max_iter=120, random_state=int(config["random_seed"])),
            )
            model.fit(X[train_idx][tr], y[train_idx][tr])
            scores.append(mean_absolute_error(y[train_idx][va], model.predict(X[train_idx][va])))
        row = {"method": "mlp", "hidden": str(hidden), "group_cv_mae_sample": float(np.mean(scores))}
        mlp_rows.append(row)
        if best_mlp is None or row["group_cv_mae_sample"] < best_mlp["group_cv_mae_sample"]:
            best_mlp = row
    cv_tables.append(pd.DataFrame(mlp_rows))
    hidden = tuple(int(x) for x in best_mlp["hidden"].strip("()").replace(" ", "").split(",") if x)
    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=hidden, alpha=3e-4, batch_size=512, max_iter=160, random_state=int(config["random_seed"])),
    )
    mlp.fit(X[train_idx], y[train_idx])
    add_pred("mlp", "ml", add_calibration_offset(y[cal_idx], mlp.predict(X[cal_idx]), mlp.predict(X[test_idx])), True)

    scalar_cols = [i for i, name in enumerate(feature_names) if not name.startswith("corrupt_norm_") and not name.startswith("mask_")]
    scalar_X = X[:, scalar_cols]
    torch_tables = []
    for method, family in [("one_dimensional_cnn", "ml"), ("phase_gated_cnn", "new_architecture")]:
        pred, losses = fit_torch(method, meta, corrupt, mask, scalar_X, train_idx, cal_idx, test_idx, y, config)
        torch_tables.append(losses)
        add_pred(method, family, pred, True)

    rng = np.random.default_rng(int(config["random_seed"]) + 101)
    shuffled = y[train_idx].copy()
    rng.shuffle(shuffled)
    shuf = HistGradientBoostingRegressor(max_iter=160, max_leaf_nodes=31, learning_rate=0.08, random_state=int(config["random_seed"]) + 1)
    shuf.fit(X[train_idx], shuffled)
    add_pred("shuffled_target_hgb", "sentinel", add_calibration_offset(y[cal_idx], shuf.predict(X[cal_idx]), shuf.predict(X[test_idx])), False)

    phase_only = meta[["dropout_idx", "mask_count", "mask_center_sample", "stave_idx"]].to_numpy(dtype=float)
    phase_model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    phase_model.fit(phase_only[train_idx], y[train_idx])
    add_pred("mask_phase_only_ridge", "sentinel", add_calibration_offset(y[cal_idx], phase_model.predict(phase_only[cal_idx]), phase_model.predict(phase_only[test_idx])), False)

    audit = {
        "train_rows_all": int(len(train_idx_all)),
        "train_rows_fit": int(len(train_idx)),
        "calibration_rows": int(len(cal_idx)),
        "test_rows": int(len(test_idx)),
        "traditional_case_winners": case_winners,
        "feature_count": int(X.shape[1]),
        "train_runs": sorted(int(x) for x in meta.iloc[train_idx_all]["run"].unique()),
        "calibration_runs": sorted(int(x) for x in meta.iloc[cal_idx]["run"].unique()),
        "test_runs": sorted(int(x) for x in meta.iloc[test_idx]["run"].unique()),
    }
    cv_all = pd.concat(cv_tables, ignore_index=True, sort=False)
    torch_all = pd.concat(torch_tables, ignore_index=True)
    return pd.concat(preds, ignore_index=True), cv_all, torch_all, audit


def metric_row(sub: pd.DataFrame, config: dict) -> dict:
    err = sub["error_ns"].to_numpy(dtype=float)
    bad_thr = float(config["bad_tail_abs_error_ns"])
    return {
        "n": int(len(sub)),
        "sigma68_ns": sigma68(err),
        "full_rms_ns": full_rms(err),
        "median_bias_ns": float(np.nanmedian(err)),
        "mean_bias_ns": float(np.nanmean(err)),
        "bad_tail_frac": float(np.nanmean(np.abs(err) > bad_thr)),
    }


def summarize(preds: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for (method, family), sub in preds.groupby(["method", "family"], sort=True):
        row = {"method": method, "family": family, "eligible_winner": bool(sub["eligible_winner"].iloc[0])}
        row.update(metric_row(sub, config))
        rows.append(row)
    summary = pd.DataFrame(rows)

    phase_rows = []
    for (method, family, phase, case), sub in preds.groupby(["method", "family", "dropout_phase", "dropout_case"], sort=True):
        row = {"method": method, "family": family, "dropout_phase": phase, "dropout_case": case}
        row.update(metric_row(sub, config))
        phase_rows.append(row)
    phase = pd.DataFrame(phase_rows)

    rng = np.random.default_rng(int(config["random_seed"]) + 331)
    boot_rows = []
    runs = np.asarray(sorted(preds["run"].unique()), dtype=int)
    for method, sub in preds.groupby("method", sort=True):
        by_run = {run: sub[sub["run"] == run] for run in runs}
        samples = {"sigma68_ns": [], "full_rms_ns": [], "bad_tail_frac": []}
        for _ in range(int(config["bootstrap_reps"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([by_run[int(run)] for run in sampled], ignore_index=True)
            m = metric_row(boot, config)
            for key in samples:
                samples[key].append(m[key])
        for metric, vals in samples.items():
            boot_rows.append(
                {
                    "method": method,
                    "scope": "all_test",
                    "metric": metric,
                    "ci_low": float(np.percentile(vals, 2.5)),
                    "ci_high": float(np.percentile(vals, 97.5)),
                }
            )
    return summary.sort_values("sigma68_ns"), phase.sort_values(["dropout_phase", "dropout_case", "sigma68_ns"]), pd.DataFrame(boot_rows)


def phase_deltas(preds: pd.DataFrame, config: dict, baseline: str, winner: str) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 777)
    rows = []
    runs = np.asarray(sorted(preds["run"].unique()), dtype=int)
    methods = [m for m in sorted(preds["method"].unique()) if m not in {baseline}]
    for phase in sorted(preds["dropout_phase"].unique()):
        for case in sorted(preds.loc[preds["dropout_phase"] == phase, "dropout_case"].unique()):
            base = preds[(preds["method"] == baseline) & (preds["dropout_case"] == case)]
            for method in methods:
                sub = preds[(preds["method"] == method) & (preds["dropout_case"] == case)]
                if sub.empty or base.empty:
                    continue
                vals = []
                for _ in range(int(config["bootstrap_reps"])):
                    sampled = rng.choice(runs, size=len(runs), replace=True)
                    a = pd.concat([sub[sub["run"] == int(run)] for run in sampled], ignore_index=True)
                    b = pd.concat([base[base["run"] == int(run)] for run in sampled], ignore_index=True)
                    vals.append(sigma68(a["error_ns"]) - sigma68(b["error_ns"]))
                rows.append(
                    {
                        "method": method,
                        "dropout_phase": phase,
                        "dropout_case": case,
                        "delta_sigma68_vs_traditional_ns": sigma68(sub["error_ns"]) - sigma68(base["error_ns"]),
                        "ci_low": float(np.percentile(vals, 2.5)),
                        "ci_high": float(np.percentile(vals, 97.5)),
                        "is_winner": method == winner,
                    }
                )
    return pd.DataFrame(rows)


def abstention_policy(preds: pd.DataFrame, phase_metrics: pd.DataFrame, boot: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    sigma_thr = float(config["irrecoverable_sigma68_ns"])
    bad_thr = float(config["irrecoverable_bad_tail_frac"])
    for method in sorted(preds["method"].unique()):
        accepted_cases = []
        for case in sorted(preds["dropout_case"].unique()):
            row = phase_metrics[(phase_metrics["method"] == method) & (phase_metrics["dropout_case"] == case)]
            if row.empty:
                continue
            r = row.iloc[0]
            if float(r["sigma68_ns"]) <= sigma_thr and float(r["bad_tail_frac"]) <= bad_thr:
                accepted_cases.append(case)
        kept = preds[(preds["method"] == method) & (preds["dropout_case"].isin(accepted_cases))]
        all_rows = preds[preds["method"] == method]
        metric = metric_row(kept, config) if len(kept) else {"n": 0, "sigma68_ns": float("nan"), "full_rms_ns": float("nan"), "median_bias_ns": float("nan"), "mean_bias_ns": float("nan"), "bad_tail_frac": float("nan")}
        rows.append(
            {
                "method": method,
                "accepted_cases": ",".join(accepted_cases),
                "abstention_coverage": float(len(kept) / max(len(all_rows), 1)),
                "post_abstention_sigma68_ns": metric["sigma68_ns"],
                "post_abstention_bad_tail_frac": metric["bad_tail_frac"],
                "post_abstention_n": int(metric["n"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["abstention_coverage", "post_abstention_sigma68_ns"], ascending=[False, True])


def plot_summary(summary: pd.DataFrame, boot: pd.DataFrame, out_dir: Path) -> None:
    eligible = summary[summary["eligible_winner"]].copy().sort_values("sigma68_ns")
    lookup = boot[(boot["scope"] == "all_test") & (boot["metric"] == "sigma68_ns")].set_index("method")
    lows, highs = [], []
    for _, row in eligible.iterrows():
        ci = lookup.loc[row["method"]]
        lows.append(row["sigma68_ns"] - float(ci["ci_low"]))
        highs.append(float(ci["ci_high"]) - row["sigma68_ns"])
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(eligible["method"], eligible["sigma68_ns"], color="#557c83")
    ax.errorbar(eligible["sigma68_ns"], eligible["method"], xerr=[lows, highs], fmt="none", ecolor="#222222", capsize=3)
    ax.set_xlabel("Held-out timing sigma68 (ns)")
    ax.set_ylabel("")
    ax.set_title("P06e dropout timing recovery benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_sigma68.png", dpi=160)
    plt.close(fig)


def plot_phase(phase: pd.DataFrame, out_dir: Path, methods: List[str]) -> None:
    focus = phase[phase["method"].isin(methods)].copy()
    focus["case_label"] = focus["dropout_phase"] + "/" + focus["dropout_case"]
    pivot = focus.pivot_table(index="case_label", columns="method", values="sigma68_ns", aggfunc="first")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    pivot.plot(kind="bar", ax=ax, width=0.82)
    ax.axhline(10.0, color="#aa3333", linestyle="--", linewidth=1.2)
    ax.set_ylabel("Timing sigma68 (ns)")
    ax.set_xlabel("")
    ax.set_title("Dropout phase frontier")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_phase_frontier.png", dpi=160)
    plt.close(fig)


def markdown_table(df: pd.DataFrame, columns: List[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    rows = df[columns].head(max_rows).copy()
    for col in rows.columns:
        if rows[col].dtype.kind in "fc":
            rows[col] = rows[col].map(lambda x: "nan" if not np.isfinite(x) else f"{x:.4g}")
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows.to_numpy()]
    return "\n".join([header, sep] + body)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    result: dict,
    counts: pd.DataFrame,
    summary: pd.DataFrame,
    phase: pd.DataFrame,
    boot: pd.DataFrame,
    deltas: pd.DataFrame,
    policy: pd.DataFrame,
    cv: pd.DataFrame,
    audit: dict,
) -> None:
    ci = boot[(boot["method"] == result["winner"]["method"]) & (boot["metric"] == "sigma68_ns")].iloc[0]
    trad = summary[summary["method"] == "traditional_phase_selected_template_interp"].iloc[0]
    winner = summary[summary["method"] == result["winner"]["method"]].iloc[0]
    delta_row = deltas[(deltas["method"] == result["winner"]["method"]) & (deltas["dropout_case"] == "peak_contiguous")]
    delta_text = "not applicable"
    if not delta_row.empty:
        r = delta_row.iloc[0]
        delta_text = f"{r['delta_sigma68_vs_traditional_ns']:.3g} ns, 95% CI [{r['ci_low']:.3g}, {r['ci_high']:.3g}] for peak_contiguous"
    phase_focus = phase[phase["method"].isin(["traditional_phase_selected_template_interp", result["winner"]["method"], "corrupted_cfd"])]
    lines = [
        "# P06e: dropout-phase timing irrecoverability frontier",
        "",
        f"- **Study ID:** P06e",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-11",
        "- **Depends on:** S00 raw selected-pulse gate; P04g dropout injection closure; P06d peak-phase coupling atlas",
        f"- **Input checksum(s):** see `input_sha256.csv` ({len(counts)} raw ROOT files)",
        f"- **Git commit:** {result['git_commit']}",
        f"- **Config:** `{config_path}`",
        "",
        "## 0. Question",
        "",
        "At which 18-sample phase locations does an injected dropout make CFD20 timing unrecoverable, and does any learned waveform model beat a strong conventional interpolation/template repair on the same held-out runs?",
        "",
        "## 1. Reproduction",
        "",
        "Raw `h101/HRDv` B-stack files are read directly. For every configured run I subtract the median of samples 0-3, select physical B channels `B2/B4/B6/B8 = 0/2/4/6`, and count pulses with baseline-subtracted amplitude `A > 1000 ADC`.",
        "",
        "| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {config['expected_selected_pulses']:,} | {result['raw_reproduction']['reproduced_selected_pulses']:,} | {result['raw_reproduction']['delta']:+,} | 0 | {result['raw_reproduction']['pass']} |",
        "",
        "## 2. Traditional Method",
        "",
        "For pulse waveform \\(x_i(t)\\), clean CFD20 time is",
        "",
        "\\[",
        "\\hat t_i = t_0 + \\frac{0.2 A_i - x_i(t_0)}{x_i(t_0+1)-x_i(t_0)}, \\quad A_i=\\max_t x_i(t),",
        "\\]",
        "",
        "where \\(t_0\\) is the sample before first threshold crossing. A dropout mask \\(m_i(t)\\) sets selected samples to zero. The conventional candidate repairs are (i) local linear interpolation over masked samples and (ii) an amplitude/stave/peak-region template refit. The selected traditional baseline is not a strawman: for each dropout case the train-run sigma68 chooses the better conventional candidate, then run 64 supplies only a scalar median calibration offset.",
        "",
        "Case-wise traditional choices from train runs:",
        "",
        markdown_table(pd.DataFrame([{"dropout_case": k, "traditional_candidate": v} for k, v in audit["traditional_case_winners"].items()]), ["dropout_case", "traditional_candidate"], 20),
        "",
        "## 3. ML Method",
        "",
        "All ML methods receive only the corrupted waveform, the binary mask, and pre-registered scalar morphology available after corruption: observed amplitude/charge, observed peak, mask count/center, stave, and dropout case. The target is the clean CFD20 time in samples; reported errors multiply by the 10 ns sample period. No model receives event id, clean waveform samples, clean amplitude, held-out run labels, or clean timing residuals.",
        "",
        "Models: ridge with grouped alpha CV; histogram gradient-boosted trees with grouped hyperparameter CV; an MLP with grouped hidden-size CV; a 1D-CNN over `[corrupted normalized waveform, mask]`; and a new phase-gated CNN whose convolutional latent is multiplicatively gated by dropout phase coordinates `(case, mask_count, mask_center)`. CNNs are deliberately small because this is a laptop-scale raw-data study.",
        "",
        "Split: train groups are Sample I runs, run 64 is used only for scalar offset calibration, and held-out test groups are Sample II analysis runs 58-63 and 65. Bootstrap intervals resample whole held-out runs.",
        "",
        "Grouped CV audit:",
        "",
        markdown_table(cv.sort_values("group_cv_mae_sample", na_position="last"), [c for c in ["method", "alpha", "max_leaf_nodes", "learning_rate", "l2_regularization", "hidden", "group_cv_mae_sample"] if c in cv.columns], 18),
        "",
        "## 4. Head-to-head Benchmark",
        "",
        "Primary metric is timing sigma68 on identical held-out injected rows. The table also reports full RMS and the fraction with `|error| > 10 ns`.",
        "",
        markdown_table(summary.merge(boot[boot["metric"] == "sigma68_ns"][["method", "ci_low", "ci_high"]], on="method", how="left"), ["method", "family", "n", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "bad_tail_frac"], 20),
        "",
        f"Winner by held-out sigma68 is **{result['winner']['method']}**: {winner['sigma68_ns']:.3g} ns with 95% CI [{ci['ci_low']:.3g}, {ci['ci_high']:.3g}] versus traditional {trad['sigma68_ns']:.3g} ns. ML-minus-traditional phase harm example: {delta_text}.",
        "",
        "Per-phase frontier for the traditional baseline, corrupted CFD sentinel, and winner:",
        "",
        markdown_table(phase_focus, ["dropout_phase", "dropout_case", "method", "n", "sigma68_ns", "full_rms_ns", "bad_tail_frac"], 40),
        "",
        "ML-minus-traditional timing harm by dropout phase. Positive values mean the learned method is wider than the strong conventional baseline; negative values mean a learned method improves sigma68. The intervals are held-out-run bootstrap CIs.",
        "",
        markdown_table(deltas[deltas["method"].isin(["hist_gradient_boosted_trees", "mlp", "one_dimensional_cnn", "phase_gated_cnn", "ridge"])].sort_values(["dropout_phase", "dropout_case", "delta_sigma68_vs_traditional_ns"]), ["dropout_phase", "dropout_case", "method", "delta_sigma68_vs_traditional_ns", "ci_low", "ci_high"], 40),
        "",
        "## 5. Falsification",
        "",
        f"Pre-registration copied from the ticket/config: primary metric is `{config['pre_registered']['primary_metric']}`; significance level is `{config['pre_registered']['significance_level']}`; the ML adoption rule requires a paired run-bootstrap delta versus traditional with a 95% CI below zero.",
        "",
        "Falsification tests: shuffled-target HGB must not win; mask/phase-only ridge must not match the full waveform models; corrupted-CFD sentinel quantifies the no-repair baseline. Multiple comparisons cover five eligible learned/traditional model families and six dropout cases; phase claims are therefore interpreted as frontier diagnostics unless their uncertainty is separated from the traditional baseline.",
        "",
        markdown_table(summary[summary["family"] == "sentinel"], ["method", "sigma68_ns", "full_rms_ns", "bad_tail_frac"], 10),
        "",
        "## 6. Threats to Validity",
        "",
        "- **Benchmark/selection:** the conventional baseline is case-wise train-selected between interpolation and template refit, so ML is not compared against a deliberately weak repair.",
        "- **Data leakage:** the split is by run; calibration run 64 contributes only median offsets; event ids and clean targets are excluded from features; rows are injected after selecting clean raw pulses.",
        "- **Metric misuse:** sigma68, full RMS, signed bias, and bad-tail fraction are all reported. There is no fitted Gaussian core or chi-square fit in this study, so chi-square/ndf is not applicable.",
        "- **Post-hoc selection:** dropout cases, metrics, model families, and win rule are fixed in the config before running the benchmark. HGB/ridge/MLP tuning uses GroupKFold on training runs only.",
        "",
        "Systematics: the dropout truth is injected, not observed electronics dropout; samples 0-3 are protected because they define the baseline; the CFD20 timing target is a software timing endpoint, not an external time-of-flight truth; low-support high-amplitude/late-peak strata can broaden run-bootstrap CIs.",
        "",
        "## 7. Provenance Manifest",
        "",
        "A machine-readable `manifest.json` records the command, commit, environment, seeds, input ROOT hashes, and output hashes. `input_sha256.csv` pins every raw ROOT input.",
        "",
        "## 8. Findings & Next Steps",
        "",
        result["finding"],
        "",
        "Recover-vs-veto phase policy using the configured irrecoverability thresholds:",
        "",
        markdown_table(policy, ["method", "accepted_cases", "abstention_coverage", "post_abstention_sigma68_ns", "post_abstention_bad_tail_frac"], 20),
        "",
        "Hypothesis: leading-edge and peak-adjacent dropouts remove threshold-crossing information, so recovery is only reliable where the mask leaves enough monotonic rising-edge support or the model can infer phase from amplitude/stave-specific shape priors. A consumer should therefore treat recovery as a phase-conditioned action, not as a universal waveform correction.",
        "",
        f"Proposed follow-up ticket: **{config['candidate_next_ticket']['title']}**. {config['candidate_next_ticket']['body']}",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {Path(__file__).as_posix()} --config {config_path.as_posix()}",
        "```",
        "",
        "Artifacts: `counts_by_run.csv`, `injection_counts.csv`, `method_metrics.csv`, `method_metrics_bootstrap_ci.csv`, `method_phase_metrics.csv`, `method_phase_delta_vs_traditional.csv`, `abstention_policy.csv`, figures, `result.json`, and `manifest.json`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("reading raw ROOT and reproducing selected-pulse count")
    meta_all, wave_all, counts, hashes = extract_selected(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError("raw reproduction failed: got %d expected %d" % (total, expected))

    selected = stratified_indices(meta_all, config)
    print("injecting %d clean pulses x %d dropout cases" % (len(selected), len(config["dropout_cases"])))
    inj, clean, corrupt, mask = inject_dropouts(meta_all, wave_all, selected, config)
    injection_counts = inj.groupby(["group", "run", "dropout_phase", "dropout_case"]).size().reset_index(name="n")
    print("fitting methods")
    preds, cv, torch_loss, audit = fit_methods(inj, clean, corrupt, mask, config)
    summary, phase, boot = summarize(preds, config)
    baseline = "traditional_phase_selected_template_interp"
    eligible = summary[summary["eligible_winner"]].sort_values("sigma68_ns").copy()
    winner = str(eligible.iloc[0]["method"])
    deltas = phase_deltas(preds, config, baseline, winner)
    policy = abstention_policy(preds, phase, boot, config)

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    hashes.to_csv(out_dir / "input_sha256.csv", index=False)
    injection_counts.to_csv(out_dir / "injection_counts.csv", index=False)
    preds.to_csv(out_dir / "heldout_predictions.csv", index=False)
    cv.to_csv(out_dir / "model_cv_audit.csv", index=False)
    torch_loss.to_csv(out_dir / "torch_training_loss.csv", index=False)
    summary.to_csv(out_dir / "method_metrics.csv", index=False)
    phase.to_csv(out_dir / "method_phase_metrics.csv", index=False)
    boot.to_csv(out_dir / "method_metrics_bootstrap_ci.csv", index=False)
    deltas.to_csv(out_dir / "method_phase_delta_vs_traditional.csv", index=False)
    policy.to_csv(out_dir / "abstention_policy.csv", index=False)
    plot_summary(summary, boot, out_dir)
    plot_phase(phase, out_dir, [baseline, winner, "corrupted_cfd"])

    winner_ci = boot[(boot["method"] == winner) & (boot["metric"] == "sigma68_ns")].iloc[0]
    trad = summary[summary["method"] == baseline].iloc[0]
    winner_row = summary[summary["method"] == winner].iloc[0]
    delta_all = float(winner_row["sigma68_ns"] - trad["sigma68_ns"])
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "status": "done",
        "git_commit": git_commit(),
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": int(total - expected),
            "pass": bool(total == expected),
        },
        "split": {
            "train_runs": audit["train_runs"],
            "calibration_runs": audit["calibration_runs"],
            "test_runs": audit["test_runs"],
            "train_rows_fit": audit["train_rows_fit"],
            "test_rows": audit["test_rows"],
        },
        "winner": {
            "method": winner,
            "family": str(winner_row["family"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "sigma68_ci95": [float(winner_ci["ci_low"]), float(winner_ci["ci_high"])],
            "delta_sigma68_vs_traditional_ns": delta_all,
            "traditional_sigma68_ns": float(trad["sigma68_ns"]),
            "full_rms_ns": float(winner_row["full_rms_ns"]),
            "bad_tail_frac": float(winner_row["bad_tail_frac"]),
        },
        "traditional_case_winners": audit["traditional_case_winners"],
        "next_tickets": [config["candidate_next_ticket"]],
        "finding": (
            "The raw S00 selected-pulse count is reproduced exactly from ROOT. "
            f"The held-out winner is {winner} with sigma68 {winner_row['sigma68_ns']:.3g} ns "
            f"versus traditional {trad['sigma68_ns']:.3g} ns; delta {delta_all:.3g} ns. "
            "Dropout recoverability is phase-conditioned: the per-case table separates "
            "leading-edge, peak, and tail masks and the abstention policy reports which cases "
            "remain below the configured 10 ns / 25% bad-tail irrecoverability frontier."
        ),
        "artifacts": {
            "report": str(out_dir / "REPORT.md"),
            "metrics": str(out_dir / "method_metrics.csv"),
            "phase_metrics": str(out_dir / "method_phase_metrics.csv"),
        },
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, config_path, config, result, counts, summary, phase, boot, deltas, policy, cv, audit)
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "created_unix": time.time(),
        "elapsed_seconds": time.time() - t0,
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join(["/home/billy/anaconda3/bin/python", Path(__file__).as_posix(), "--config", str(config_path)]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "torch": torch.__version__,
        "random_seed": int(config["random_seed"]),
        "input_files": hashes.to_dict(orient="records"),
        "output_sha256": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")
    print("wrote", out_dir)
    print(json.dumps(json_clean(result["winner"]), indent=2))


if __name__ == "__main__":
    main()
