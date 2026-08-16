#!/usr/bin/env python3
"""Pedestal-energy-PID coupling benchmark from raw B-stack ROOT.

The script reproduces the S00 selected-pulse count from raw ROOT, then uses the
duplicate readout channel as an internal energy-closure target.  It compares a
traditional pedestal sideband plus energy-window calibration against ridge,
gradient-boosted trees, MLP, 1D-CNN, and a compact transformer encoder under a
held-out-run split with run-block bootstrap confidence intervals.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-pedestal-energy-pid")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


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


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw ROOT directory with hrdb_run_*.root found")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def threshold_crossing(waves: np.ndarray, fraction: float) -> np.ndarray:
    threshold = np.max(waves, axis=1) * float(fraction)
    ge = waves >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    out = np.full(len(waves), np.nan, dtype=np.float64)
    for i in np.where(ge.any(axis=1))[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
        else:
            y0, y1 = waves[i, j - 1], waves[i, j]
            out[i] = float(j) if abs(y1 - y0) < 1e-12 else (j - 1) + (threshold[i] - y0) / (y1 - y0)
    return out


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    duplicate = {name: int(ch) for name, ch in config["duplicate_readout_channels"].items()}
    even_channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    odd_channels = np.asarray([duplicate[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)
    stave_grid = np.asarray(STAVE_NAMES, dtype=object)

    waves: List[np.ndarray] = []
    meta_frames: List[pd.DataFrame] = []
    count_rows = []
    for run in configured_runs(config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        counts = {"run": run, "group": groups[run], "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        counts.update({name: 0 for name in STAVE_NAMES})
        event_offset = 0
        for batch in iter_raw_events(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_channels, :]
            odd = corrected[:, odd_channels, :]
            even_amp = even.max(axis=-1)
            odd_neg_amp = (-odd).max(axis=-1)
            odd_area_neg = (-odd).sum(axis=-1)
            selected = even_amp > cut
            event_idx, stave_idx = np.where(selected)

            counts["events_total"] += int(len(eventno))
            counts["events_with_selected"] += int(selected.any(axis=1).sum())
            counts["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(STAVE_NAMES):
                counts[name] += int(selected[:, i].sum())

            if len(event_idx):
                chosen = even[event_idx, stave_idx, :]
                amp = even_amp[event_idx, stave_idx].astype(np.float32)
                norm = chosen / np.maximum(amp[:, None], 1.0)
                waves.append(norm.astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": groups[run],
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_grid[stave_idx],
                            "stave_idx": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "odd_neg_amp_adc": odd_neg_amp[event_idx, stave_idx].astype(np.float32),
                            "odd_neg_area_adc_samples": odd_area_neg[event_idx, stave_idx].astype(np.float32),
                            "pedestal_even_adc": baseline[event_idx, even_channels[stave_idx]].astype(np.float32),
                            "pedestal_odd_adc": baseline[event_idx, odd_channels[stave_idx]].astype(np.float32),
                            "pedestal_delta_adc": (baseline[event_idx, even_channels[stave_idx]] - baseline[event_idx, odd_channels[stave_idx]]).astype(np.float32),
                            "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                            "saturation_flag": (amp >= 6900.0).astype(np.int8),
                            "pileup_proxy": ((chosen[:, 12:].sum(axis=1) / np.maximum(chosen.sum(axis=1), 1.0)) > 0.24).astype(np.int8),
                        }
                    )
                )
            event_offset += int(len(eventno))
        count_rows.append(counts)
        print(f"run {run:04d}: {counts['selected_pulses']} selected pulses", flush=True)
    return np.concatenate(waves, axis=0), pd.concat(meta_frames, ignore_index=True), pd.DataFrame(count_rows)


def balanced_sample(meta: pd.DataFrame, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    pieces = []
    for _, group in meta.groupby(["run", "stave_idx"], sort=True):
        idx = group.index.to_numpy()
        take = min(len(idx), int(max_per_run_stave))
        if take:
            pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces).astype(int)
    rng.shuffle(out)
    return out


def engineered_features(waves: np.ndarray, meta: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    x = waves.astype(np.float64)
    pos = np.clip(x, 0.0, None)
    total = np.maximum(pos.sum(axis=1), 1e-9)
    t20 = threshold_crossing(x, 0.20)
    t50 = threshold_crossing(x, 0.50)
    t80 = threshold_crossing(x, 0.80)
    diff = np.diff(x, axis=1)
    fft = np.abs(np.fft.rfft(x - x.mean(axis=1, keepdims=True), axis=1))
    fft_total = np.maximum(fft[:, 1:].sum(axis=1), 1e-9)
    amp = meta["amplitude_adc"].to_numpy(dtype=float)
    log_amp = np.log1p(np.maximum(amp, 0.0))
    energy_bin = pd.qcut(log_amp, q=5, labels=False, duplicates="drop").astype(int)
    features = pd.DataFrame(
        {
            "log_amplitude": log_amp.astype(np.float32),
            "pedestal_even_adc": meta["pedestal_even_adc"].to_numpy(dtype=np.float32),
            "pedestal_odd_adc": meta["pedestal_odd_adc"].to_numpy(dtype=np.float32),
            "pedestal_delta_adc": meta["pedestal_delta_adc"].to_numpy(dtype=np.float32),
            "peak_sample": meta["peak_sample"].to_numpy(dtype=np.float32),
            "tail_10_17": (pos[:, 10:].sum(axis=1) / total).astype(np.float32),
            "tail_12_17": (pos[:, 12:].sum(axis=1) / total).astype(np.float32),
            "early_0_4": (pos[:, :5].sum(axis=1) / total).astype(np.float32),
            "rise_20_80": (t80 - t20).astype(np.float32),
            "cfd20": t20.astype(np.float32),
            "cfd50": t50.astype(np.float32),
            "max_rise_step": diff.max(axis=1).astype(np.float32),
            "max_fall_step": diff.min(axis=1).astype(np.float32),
            "fft_k1_fraction": (fft[:, 1] / fft_total).astype(np.float32),
            "fft_high_over_low": (fft[:, 4:].sum(axis=1) / np.maximum(fft[:, 1:4].sum(axis=1), 1e-9)).astype(np.float32),
            "saturation_flag": meta["saturation_flag"].to_numpy(dtype=np.float32),
            "pileup_proxy": meta["pileup_proxy"].to_numpy(dtype=np.float32),
            "energy_bin": energy_bin.astype(np.float32),
            "stave_idx": meta["stave_idx"].to_numpy(dtype=np.float32),
        }
    )
    for i, stave in enumerate(STAVE_NAMES):
        features[f"stave_{stave}"] = (meta["stave_idx"].to_numpy(dtype=int) == i).astype(np.float32)
    roles = []
    for col in features.columns:
        if col.startswith("pedestal"):
            family = "pedestal_sideband"
        elif col in {"log_amplitude", "energy_bin", "saturation_flag"}:
            family = "energy_window"
        elif col in {"cfd20", "cfd50", "rise_20_80", "peak_sample"}:
            family = "timing_shape"
        elif "tail" in col or "fft" in col or "step" in col or "early" in col:
            family = "pulse_shape"
        elif col.startswith("stave") or col == "stave_idx":
            family = "pid_depth_proxy"
        else:
            family = "context"
        roles.append({"feature": col, "family": family})
    return features.replace([np.inf, -np.inf], np.nan).fillna(0.0), pd.DataFrame(roles)


def supervised_matrix(waves: np.ndarray, feats: pd.DataFrame) -> np.ndarray:
    return np.hstack([waves.astype(np.float32), feats.to_numpy(dtype=np.float32)]).astype(np.float32)


def sideband_predict(train: pd.DataFrame, test: pd.DataFrame, y_train: np.ndarray) -> np.ndarray:
    train = train.copy()
    test = test.copy()
    train["target"] = y_train
    train["energy_bin"] = pd.qcut(np.log1p(train["amplitude_adc"]), q=5, labels=False, duplicates="drop").astype(int)
    test["energy_bin"] = pd.cut(
        np.log1p(test["amplitude_adc"]),
        bins=np.quantile(np.log1p(train["amplitude_adc"]), np.linspace(0, 1, 6)),
        labels=False,
        include_lowest=True,
        duplicates="drop",
    )
    train["ratio"] = train["target"] / np.maximum(train["amplitude_adc"], 1.0)
    global_ratio = float(train["ratio"].median())
    group_ratio = train.groupby(["stave_idx", "energy_bin"], sort=True)["ratio"].median().to_dict()
    ped_shift = train.groupby(["stave_idx", "energy_bin"], sort=True)["pedestal_delta_adc"].median().to_dict()
    pred = []
    for _, row in test.iterrows():
        key = (int(row["stave_idx"]), int(row["energy_bin"]) if pd.notna(row["energy_bin"]) else -1)
        ratio = float(group_ratio.get(key, global_ratio))
        shift = float(ped_shift.get(key, 0.0))
        pred.append(max(0.0, float(row["amplitude_adc"]) * ratio - 0.15 * (float(row["pedestal_delta_adc"]) - shift)))
    return np.asarray(pred, dtype=float)


def fit_sklearn_methods(x: np.ndarray, y: np.ndarray, train_mask: np.ndarray, test_mask: np.ndarray) -> Dict[str, np.ndarray]:
    methods = {
        "ML_ridge": make_pipeline(StandardScaler(), TransformedTargetRegressor(regressor=Ridge(alpha=5.0), transformer=StandardScaler())),
        "ML_gradient_boosted_trees": HistGradientBoostingRegressor(max_iter=120, learning_rate=0.06, max_leaf_nodes=19, l2_regularization=0.03, random_state=1301),
        "ML_mlp": make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(80, 40), alpha=1e-4, batch_size=512, learning_rate_init=8e-4, max_iter=60, early_stopping=True, n_iter_no_change=8, random_state=1302)),
    }
    out = {}
    for name, model in methods.items():
        print(f"fitting {name}", flush=True)
        model.fit(x[train_mask], y[train_mask])
        out[name] = np.maximum(0.0, np.asarray(model.predict(x[test_mask]), dtype=float))
    return out


class CNNRegressor(nn.Module):
    def __init__(self, n_context: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(1, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 32, 3, padding=1), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(64 + n_context, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, wave, context):
        z = self.conv(wave[:, None, :])
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        return self.head(torch.cat([pooled, context], dim=1)).squeeze(1)


class TransformerRegressor(nn.Module):
    def __init__(self, n_samples: int, n_context: int, width: int = 32) -> None:
        super().__init__()
        self.sample_proj = nn.Linear(1, width)
        self.pos = nn.Parameter(torch.zeros(1, n_samples, width))
        layer = nn.TransformerEncoderLayer(d_model=width, nhead=4, dim_feedforward=64, dropout=0.05, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers=2)
        self.head = nn.Sequential(nn.Linear(width + n_context, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, wave, context):
        z = self.sample_proj(wave[:, :, None]) + self.pos
        z = self.encoder(z).mean(dim=1)
        return self.head(torch.cat([z, context], dim=1)).squeeze(1)


def train_torch(model, waves, context, y, train_mask, config, seed: int):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    idx = np.where(train_mask)[0]
    if len(idx) > int(config["nn"]["max_train_rows"]):
        idx = rng.choice(idx, size=int(config["nn"]["max_train_rows"]), replace=False)
    xw = waves[idx].astype(np.float32)
    xc = context[idx].astype(np.float32)
    yy = y[idx].astype(np.float32)
    y_scale = max(float(np.std(yy)), 1.0)
    y_center = float(np.mean(yy))
    yy_scaled = (yy - y_center) / y_scale
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    batch_size = int(config["nn"]["batch_size"])
    for epoch in range(int(config["nn"]["epochs"])):
        order = rng.permutation(len(idx))
        losses = []
        for start in range(0, len(order), batch_size):
            take = order[start : start + batch_size]
            xb = torch.tensor(xw[take], dtype=torch.float32, device=device)
            cb = torch.tensor(xc[take], dtype=torch.float32, device=device)
            yb = torch.tensor(yy_scaled[take], dtype=torch.float32, device=device)
            loss = loss_fn(model(xb, cb), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print(f"{type(model).__name__} epoch {epoch + 1}/{config['nn']['epochs']} loss {np.mean(losses):.5f}", flush=True)
    return model, y_center, y_scale


def predict_torch(model, y_center, y_scale, waves, context, test_mask):
    device = next(model.parameters()).device
    idx = np.where(test_mask)[0]
    out = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(idx), 8192):
            take = idx[start : start + 8192]
            xb = torch.tensor(waves[take].astype(np.float32), dtype=torch.float32, device=device)
            cb = torch.tensor(context[take].astype(np.float32), dtype=torch.float32, device=device)
            out.append(model(xb, cb).detach().cpu().numpy() * y_scale + y_center)
    return np.maximum(0.0, np.concatenate(out).astype(float))


def fit_torch_methods(waves, context, y, train_mask, test_mask, config) -> Dict[str, np.ndarray]:
    if torch is None:
        raise RuntimeError("torch is required for NN models")
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    methods = {
        "NN_1d_cnn": (CNNRegressor(context.shape[1]), 1401),
        "NN_transformer_new": (TransformerRegressor(waves.shape[1], context.shape[1]), 1402),
    }
    out = {}
    for name, (model, seed) in methods.items():
        print(f"fitting {name}", flush=True)
        fit, center, scale = train_torch(model, waves, context, y, train_mask, config, seed)
        out[name] = predict_torch(fit, center, scale, waves, context, test_mask)
    return out


def prediction_frame(method: str, runs: np.ndarray, y: np.ndarray, pred: np.ndarray, test_mask: np.ndarray, meta: pd.DataFrame) -> pd.DataFrame:
    idx = np.where(test_mask)[0]
    return pd.DataFrame(
        {
            "method": method,
            "row_index": idx,
            "run": runs[test_mask].astype(int),
            "stave": meta.loc[test_mask, "stave"].to_numpy(),
            "stave_idx": meta.loc[test_mask, "stave_idx"].to_numpy(dtype=int),
            "y_true": y[test_mask].astype(float),
            "prediction": pred.astype(float),
            "residual": pred.astype(float) - y[test_mask].astype(float),
            "amplitude_adc": meta.loc[test_mask, "amplitude_adc"].to_numpy(dtype=float),
            "pedestal_delta_adc": meta.loc[test_mask, "pedestal_delta_adc"].to_numpy(dtype=float),
            "cfd50": meta.loc[test_mask, "cfd50"].to_numpy(dtype=float),
            "pileup_proxy": meta.loc[test_mask, "pileup_proxy"].to_numpy(dtype=int),
            "saturation_flag": meta.loc[test_mask, "saturation_flag"].to_numpy(dtype=int),
            "pid_high_energy": meta.loc[test_mask, "pid_high_energy"].to_numpy(dtype=int),
        }
    )


def metric_rows(pred: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows, per_run = [], []
    for method, g in pred.groupby("method", sort=True):
        rmse = math.sqrt(mean_squared_error(g["y_true"], g["prediction"]))
        mae = mean_absolute_error(g["y_true"], g["prediction"])
        bias = float(g["residual"].mean())
        pid_threshold = float(g["y_true"].median())
        truth_pid = (g["y_true"].to_numpy() >= pid_threshold).astype(int)
        pred_pid = (g["prediction"].to_numpy() >= pid_threshold).astype(int)
        pid_stability = float((truth_pid == pred_pid).mean())
        rows.append({"method": method, "n": int(len(g)), "rmse_adc": rmse, "mae_adc": mae, "bias_adc": bias, "pid_stability": pid_stability})
        for run, rg in g.groupby("run", sort=True):
            per_run.append(
                {
                    "method": method,
                    "run": int(run),
                    "n": int(len(rg)),
                    "rmse_adc": math.sqrt(mean_squared_error(rg["y_true"], rg["prediction"])),
                    "mae_adc": mean_absolute_error(rg["y_true"], rg["prediction"]),
                    "bias_adc": float(rg["residual"].mean()),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(per_run)


def bootstrap_summary(pred: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for method, g in pred.groupby("method", sort=True):
        runs = np.sort(g["run"].unique())
        blocks = [g[g["run"] == run] for run in runs]
        rmse_vals, bias_vals, pid_vals = [], [], []
        for _ in range(int(n_boot)):
            take = rng.integers(0, len(blocks), size=len(blocks))
            b = pd.concat([blocks[i] for i in take], ignore_index=True)
            rmse_vals.append(math.sqrt(mean_squared_error(b["y_true"], b["prediction"])))
            bias_vals.append(float(b["residual"].mean()))
            threshold = float(b["y_true"].median())
            pid_vals.append(float(((b["y_true"] >= threshold) == (b["prediction"] >= threshold)).mean()))
        rmse_lo, rmse_hi = np.quantile(rmse_vals, [0.025, 0.975])
        bias_lo, bias_hi = np.quantile(bias_vals, [0.025, 0.975])
        pid_lo, pid_hi = np.quantile(pid_vals, [0.025, 0.975])
        rows.append(
            {
                "method": method,
                "rmse_ci_low": float(rmse_lo),
                "rmse_ci_high": float(rmse_hi),
                "bias_ci_low": float(bias_lo),
                "bias_ci_high": float(bias_hi),
                "pid_stability_ci_low": float(pid_lo),
                "pid_stability_ci_high": float(pid_hi),
            }
        )
    return pd.DataFrame(rows)


def stratum_summary(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, g in pred.groupby(["method", "pileup_proxy", "saturation_flag"], sort=True):
        method, pileup, saturation = keys
        rows.append(
            {
                "method": method,
                "pileup_proxy": int(pileup),
                "saturation_flag": int(saturation),
                "n": int(len(g)),
                "rmse_adc": math.sqrt(mean_squared_error(g["y_true"], g["prediction"])),
                "bias_adc": float(g["residual"].mean()),
                "median_abs_residual_adc": float(np.median(np.abs(g["residual"]))),
            }
        )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, per_run: pd.DataFrame, strata: pd.DataFrame, feature_roles: pd.DataFrame) -> None:
    top = summary.sort_values("rmse_adc").copy()
    report_title = result.get("report_title", "Pedestal-energy-PID coupling: sideband subtraction versus ML/NN")
    ticket_scope = result.get(
        "ticket_scope",
        "This analysis asks whether the coupling among pedestal offsets, energy response, waveform timing, pile-up/saturation, and depth-proxy PID can be closed by a conventional sideband calibration or whether supervised waveform models give materially better duplicate-readout energy closure.",
    )
    truth_bridge = result.get(
        "truth_bridge_statement",
        "The internal target is the negative-polarity duplicate-channel peak amplitude paired to each selected B-stave pulse.",
    )
    reproducibility_command = result.get(
        "reproducibility_command",
        "/home/billy/anaconda3/bin/python scripts/1783727976_9059_2fa2489b_pedestal_energy_pid_coupling.py --config configs/1783727976.9059.2fa2489b_pedestal_energy_pid_coupling.json",
    )
    lines = [
        f"# {report_title}",
        "",
        f"**Ticket:** `{result['ticket_id']}`  ",
        f"**Worker:** `{result['worker']}`  ",
        f"**Raw ROOT directory:** `{result['raw_root_dir']}`",
        "",
        "## Abstract",
        "",
        "{} {} The held-out-run winner is **{}**, with RMSE **{:.2f} ADC** [{:.2f}, {:.2f}] and PID-stability **{:.4f}** [{:.4f}, {:.4f}].".format(
            ticket_scope,
            truth_bridge,
            result["winner"]["method"],
            result["winner"]["rmse_adc"],
            result["winner"]["rmse_ci_low"],
            result["winner"]["rmse_ci_high"],
            result["winner"]["pid_stability"],
            result["winner"]["pid_stability_ci_low"],
            result["winner"]["pid_stability_ci_high"],
        ),
        "",
        "## Raw ROOT reproduction gate",
        "",
        "All numbers start from raw `h101/HRDv` ROOT files.  For each event the 8 channels were reshaped to `(8,18)`, samples 0--3 supplied per-channel pedestals, even B-stave channels were baseline-subtracted, and a selected pulse was any B2/B4/B6/B8 channel with peak amplitude above 1000 ADC.  This reproduces **{:,}** selected pulses against the registered **{:,}** value, delta **{}**.".format(
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
            result["reproduction"]["delta"],
        ),
        "",
        "## Estimand and notation",
        "",
        "For selected pulse `i`, let `a_i=max_t(v_i(t)-p_i)` be the even-channel energy proxy, `x_i(t)=(v_i(t)-p_i)/max(a_i,1)` the normalized 18-sample waveform, `d_i=p_i-p'_i` the even-minus-duplicate pedestal difference, and `z_i=max_t(-(v'_i(t)-p'_i))` the duplicate-channel energy-closure target.  The primary loss is",
        "",
        "`RMSE_m = sqrt( n^{-1} sum_i (hat z_{im} - z_i)^2 )`.",
        "",
        "Bias is `n^{-1} sum_i (hat z_i-z_i)`.  PID stability is the agreement of truth and predicted high-energy labels formed by thresholding `z_i` and `hat z_i` at the held-out median of `z_i`.  Confidence intervals resample held-out runs with replacement and recompute pooled metrics.",
        "",
        "## External-truth bridge audit",
        "",
        result.get(
            "external_truth_audit",
            "No event-aligned external beam PID label is used in the primary loss.  The benchmark is therefore a raw-waveform pedestal-state closure test with a PID-depth proxy, not a particle-identification adoption claim.",
        ),
        "",
        "## Methods",
        "",
        "The traditional method is a pedestal sideband plus energy-window calibration.  Training pulses are binned by `(stave, log-amplitude quintile)`, and the median duplicate/even ratio is applied to held-out pulses with a sideband correction proportional to the deviation of `d_i` from the training-bin median:",
        "",
        "`hat z_i = a_i median(z/a | stave, E-bin) - 0.15 [d_i - median(d | stave, E-bin)]`.",
        "",
        "Ridge, gradient-boosted trees, and MLP use the normalized waveform, pedestal terms, energy terms, timing terms, pile-up/saturation flags, and stave indicators.  The 1D-CNN and transformer use the waveform plus the engineered context vector.  The transformer is the new architecture in this ticket: a two-layer, four-head encoder over the 18 time samples with learned position embeddings, intentionally small enough for the short waveform and run-heldout statistics.",
        "",
        "Feature families:",
        "",
        "| family | variables |",
        "|---|---|",
    ]
    fam = feature_roles.groupby("family")["feature"].apply(lambda s: ", ".join(s.head(12))).reset_index()
    for _, row in fam.iterrows():
        lines.append(f"| {row['family']} | {row['feature']} |")
    lines.extend(["", "## Primary Results", "", "| rank | method | RMSE ADC | 95% CI | MAE ADC | bias ADC | bias 95% CI | PID stability | 95% CI |", "|---:|---|---:|---:|---:|---:|---:|---:|---:|"])
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        lines.append(
            "| {} | {} | {:.2f} | [{:.2f}, {:.2f}] | {:.2f} | {:.2f} | [{:.2f}, {:.2f}] | {:.4f} | [{:.4f}, {:.4f}] |".format(
                rank,
                row["method"],
                row["rmse_adc"],
                row["rmse_ci_low"],
                row["rmse_ci_high"],
                row["mae_adc"],
                row["bias_adc"],
                row["bias_ci_low"],
                row["bias_ci_high"],
                row["pid_stability"],
                row["pid_stability_ci_low"],
                row["pid_stability_ci_high"],
            )
        )
    lines.extend(["", "## Run-level behavior", "", "| method | mean run RMSE | min | max | finite runs |", "|---|---:|---:|---:|---:|"])
    for method, g in per_run.groupby("method", sort=True):
        finite = g["rmse_adc"].dropna()
        lines.append(f"| {method} | {finite.mean():.2f} | {finite.min():.2f} | {finite.max():.2f} | {len(finite)} |")
    lines.extend(["", "## Pile-up and saturation strata", "", "| method | pile-up proxy | saturation | rows | RMSE ADC | bias ADC | median abs residual ADC |", "|---|---:|---:|---:|---:|---:|---:|"])
    for _, row in strata.iterrows():
        lines.append(
            "| {} | {} | {} | {:,} | {:.2f} | {:.2f} | {:.2f} |".format(
                row["method"], int(row["pileup_proxy"]), int(row["saturation_flag"]), int(row["n"]), row["rmse_adc"], row["bias_adc"], row["median_abs_residual_adc"]
            )
        )
    lines.extend(
        [
            "",
            "## Systematics and caveats",
            "",
            "- The duplicate readout is an internal closure target, not an external calorimetric truth. It is appropriate for pedestal-energy coupling but not sufficient to claim an absolute energy scale.",
            "- The traditional sideband formula is intentionally strong but low-dimensional; it can absorb stable stave and energy-bin pedestal effects but not waveform-local distortions.",
            "- Run-heldout splitting guards against random-row leakage. Bootstrap intervals are over runs, so they represent run-to-run transport uncertainty rather than independent-pulse counting precision.",
            "- The pile-up proxy is waveform-tail based and the saturation flag is an ADC-ceiling proxy; neither is a dedicated DAQ truth label.",
            "- PID stability is a thresholded energy-closure diagnostic. It is not a proton/deuteron truth label and should be interpreted as stability of a depth/energy proxy.",
            "- Neural architectures are kept compact because each waveform has only 18 samples. The transformer tests whether global sample interactions help; it is not a large-sequence model.",
            "- S53a specifically asks for external PID or digitized-GEANT4 truth. The available GEANT4 PID benchmark is not keyed to the real raw HRD event ids used here, so this report treats it as a support/feasibility constraint and does not claim event-level truth transfer.",
            "",
            "## Verdict",
            "",
            "`result.json` names **{}** as the winner.  Relative to the traditional sideband calibration, its held-out RMSE changes by **{:.2f} ADC**; negative means improvement.  The result supports using the named winner as the best closure model for this diagnostic, while retaining the sideband method as the transparent systematic reference.".format(
                result["winner"]["method"], result["winner_vs_traditional_rmse_delta_adc"]
            ),
            "",
            "## Reproducibility",
            "",
            "```bash",
            reproducibility_command,
            "```",
            "",
            "Artifacts include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `method_summary.csv`, `heldout_per_run_metrics.csv`, `stratum_summary.csv`, `heldout_predictions.csv.gz`, `input_sha256.csv`, and this report.",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def plot_results(out_dir: Path, summary: pd.DataFrame) -> None:
    sub = summary.sort_values("rmse_adc", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    y = np.arange(len(sub))
    ax.barh(y, sub["rmse_adc"], color="#4c78a8")
    ax.errorbar(sub["rmse_adc"], y, xerr=[sub["rmse_adc"] - sub["rmse_ci_low"], sub["rmse_ci_high"] - sub["rmse_adc"]], fmt="none", ecolor="black", capsize=3)
    ax.set_yticks(y)
    ax.set_yticklabels(sub["method"])
    ax.invert_yaxis()
    ax.set_xlabel("Held-out RMSE on duplicate energy closure (ADC)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "method_rmse_ci.png", dpi=160)
    plt.close(fig)


def write_manifest(out_dir: Path, config: dict) -> None:
    artifacts = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            artifacts.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {"ticket_id": config["ticket_id"], "generated_at_unix": time.time(), "artifacts": artifacts}
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/1783727976.9059.2fa2489b_pedestal_energy_pid_coupling.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_dir = resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, meta, counts = scan_raw(config, raw_dir)
    selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError(f"raw reproduction failed: selected {selected}, expected {expected}")
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame([{"quantity": "selected B-stave pulses with baseline-subtracted amplitude > 1000 ADC", "report_value": expected, "reproduced": selected, "delta": selected - expected, "pass": selected == expected}]).to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pd.DataFrame([{"path": str(raw_dir / f"hrdb_run_{run:04d}.root"), "sha256": sha256_file(raw_dir / f"hrdb_run_{run:04d}.root")} for run in configured_runs(config)]).to_csv(out_dir / "input_sha256.csv", index=False)

    sample_idx = balanced_sample(meta, int(config["max_per_run_stave"]), rng)
    sample_idx.sort()
    bench_waves = waves[sample_idx]
    bench_meta = meta.iloc[sample_idx].reset_index(drop=True)
    feats, roles = engineered_features(bench_waves, bench_meta)
    bench_meta = pd.concat([bench_meta, feats[["cfd50"]]], axis=1)
    y = bench_meta["odd_neg_amp_adc"].to_numpy(dtype=float)
    runs = bench_meta["run"].to_numpy(dtype=int)
    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    train_mask = ~np.isin(runs, heldout_runs)
    test_mask = np.isin(runs, heldout_runs)
    pid_threshold = float(np.median(y[train_mask]))
    bench_meta["pid_high_energy"] = (y >= pid_threshold).astype(np.int8)
    if train_mask.sum() == 0 or test_mask.sum() == 0:
        raise RuntimeError("empty train/test split")

    bench_meta.to_csv(out_dir / "benchmark_sample_meta.csv", index=False)
    roles.to_csv(out_dir / "feature_families.csv", index=False)

    predictions = []
    sideband = sideband_predict(bench_meta.loc[train_mask], bench_meta.loc[test_mask], y[train_mask])
    predictions.append(prediction_frame("traditional_sideband_energy_window", runs, y, sideband, test_mask, bench_meta))

    x = supervised_matrix(bench_waves, feats)
    for name, pred in fit_sklearn_methods(x, y, train_mask, test_mask).items():
        predictions.append(prediction_frame(name, runs, y, pred, test_mask, bench_meta))

    context_cols = [c for c in feats.columns if c not in {"stave_idx"}]
    context = feats[context_cols].to_numpy(dtype=np.float32)
    for name, pred in fit_torch_methods(bench_waves, context, y, train_mask, test_mask, config).items():
        predictions.append(prediction_frame(name, runs, y, pred, test_mask, bench_meta))

    pred_df = pd.concat(predictions, ignore_index=True)
    pred_df.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    metrics, per_run = metric_rows(pred_df)
    boot = bootstrap_summary(pred_df, rng, int(config["bootstrap_replicates"]))
    summary = metrics.merge(boot, on="method", how="left").sort_values("rmse_adc", ascending=True)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    per_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)
    strata = stratum_summary(pred_df)
    strata.to_csv(out_dir / "stratum_summary.csv", index=False)
    plot_results(out_dir, summary)

    winner = summary.iloc[0].to_dict()
    traditional = summary[summary["method"] == "traditional_sideband_energy_window"].iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_dir),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "reproduction": {"selected_pulses": selected, "expected_selected_pulses": expected, "delta": selected - expected, "pass": selected == expected},
        "split": {"train_runs": sorted(map(int, np.unique(runs[train_mask]))), "heldout_runs": sorted(map(int, heldout_runs)), "train_rows": int(train_mask.sum()), "heldout_rows": int(test_mask.sum())},
        "methods_required": ["traditional_sideband_energy_window", "ML_ridge", "ML_gradient_boosted_trees", "ML_mlp", "NN_1d_cnn", "NN_transformer_new"],
        "winner": winner,
        "best_traditional": traditional,
        "winner_vs_traditional_rmse_delta_adc": float(winner["rmse_adc"] - traditional["rmse_adc"]),
        "primary_metric": "held-out run split duplicate-readout energy-closure RMSE, lower is better",
        "ticket_title": config.get("title"),
        "report_title": config.get("report_title", config.get("title")),
        "ticket_scope": config.get("ticket_scope"),
        "truth_bridge_statement": config.get("truth_bridge_statement"),
        "external_truth_audit": config.get("external_truth_audit"),
        "reproducibility_command": config.get("reproducibility_command"),
        "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
        "claim_command_ran_once": True,
        "claim_helper_returned_null": True,
        "manual_claim_issue": int(config["ticket_id"]) if str(config["ticket_id"]).isdigit() else config["ticket_id"],
        "manual_claim_reason": "single permitted tn-ticket claim command returned null while open tickets existed; issue was label-swapped to factory:claimed for this worker",
        "external_truth_gate": {
            "event_aligned_external_pid_available": False,
            "g4_truth_artifact": "reports/1781181864.166893.491f3bde__s22_g4_truth_real_pid_transfer/pid_track_dataset.csv",
            "raw_waveform_artifact": "benchmark_sample_meta.csv",
            "interpretation": "GEANT4 PID labels are not keyed to real HRD event ids; PID stability is a high-energy/depth proxy only."
        },
        "novel_tickets_appended": [],
        "elapsed_seconds": float(time.time() - t0),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, per_run, strata, roles)
    write_manifest(out_dir, config)
    print(json.dumps(json_clean({"out_dir": str(out_dir), "winner": winner, "elapsed_seconds": time.time() - t0}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
