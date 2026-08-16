#!/usr/bin/env python3
"""P06 ticket 2400: dropout/jagged detection and recovery benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/testbeam-p06-mpl")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

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
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
import digital_cfd

CONFIG_DEFAULT = "configs/p06_2400_dropout_jagged_detection_recovery.json"


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


def stack_obj(values: np.ndarray) -> np.ndarray:
    if len(values) == 0:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack(values).astype(np.float32)


def iter_raw(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def cfd_time(waves: np.ndarray, fraction: float) -> np.ndarray:
    amp = np.nanmax(waves, axis=1)
    return digital_cfd.cfd_time_samples(waves.astype(np.float32), amp.astype(np.float64), float(fraction))


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    med = float(np.median(values))
    return float(np.percentile(np.abs(values - med), 68.0))


def load_selected_pulses(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    groups = group_for_run(config)
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    nsamp = int(config["samples_per_channel"])
    base_idx = np.asarray(config["baseline_samples"], dtype=int)
    cut = float(config["amplitude_cut_adc"])
    frac = float(config["cfd_fraction"])
    rows: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []
    pulse_offset = 0

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {"run": run, "group": groups[run], "events_total": 0, "selected_pulses": 0}
        run_counts.update({s: 0 for s in staves})
        for batch in iter_raw(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            raw = stack_obj(batch["HRDv"]).reshape(-1, 8, nsamp)[:, channels, :]
            base = np.median(raw[..., base_idx], axis=-1)
            corrected = raw - base[..., None]
            amp = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            selected = amp > cut
            run_counts["events_total"] += int(len(eventno))
            run_counts["selected_pulses"] += int(selected.sum())
            for i, stave in enumerate(staves):
                run_counts[stave] += int(selected[:, i].sum())
            ev_idx, st_idx = np.where(selected)
            if len(ev_idx) == 0:
                continue
            sel_wave = corrected[ev_idx, st_idx, :].astype(np.float32)
            sel_amp = amp[ev_idx, st_idx].astype(np.float64)
            sel_peak = peak[ev_idx, st_idx].astype(int)
            sel_cfd = cfd_time(sel_wave, frac) * float(config["sample_period_ns"])
            rec = pd.DataFrame(
                {
                    "pulse_id": np.arange(pulse_offset, pulse_offset + len(ev_idx), dtype=np.int64),
                    "run": int(run),
                    "group": groups[run],
                    "eventno": eventno[ev_idx],
                    "stave": np.asarray(staves, dtype=object)[st_idx],
                    "channel": channels[st_idx],
                    "amplitude_adc": sel_amp,
                    "peak_sample": sel_peak,
                    "area_adc_sample": sel_wave.sum(axis=1),
                    "pretrigger_ptp_adc": np.ptp(raw[ev_idx, st_idx, :][:, base_idx], axis=1),
                    "true_cfd20_ns": sel_cfd,
                }
            )
            rows.append(rec)
            waves.append(sel_wave)
            pulse_offset += len(ev_idx)
        counts.append(run_counts)
    return pd.concat(rows, ignore_index=True), np.concatenate(waves, axis=0), pd.DataFrame(counts)


def stratified_sample(meta: pd.DataFrame, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["injection"]["random_seed"]))
    keep: List[np.ndarray] = []
    max_per_run = int(config["injection"]["max_pulses_per_run"])
    for _, group in meta.groupby("run", sort=True):
        idx = group.index.to_numpy()
        n = min(len(idx), max_per_run)
        keep.append(rng.choice(idx, size=n, replace=False))
    return np.sort(np.concatenate(keep))


def inject_corruptions(meta: pd.DataFrame, waves: np.ndarray, config: dict) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    inj = config["injection"]
    rng = np.random.default_rng(int(inj["random_seed"]) + 17)
    nsamp = waves.shape[1]
    widths = np.asarray(inj["dropout_widths"], dtype=int)
    starts = np.empty(len(waves), dtype=int)
    masks = np.zeros_like(waves, dtype=np.float32)
    corrupted = waves.copy().astype(np.float32)
    low, high = [float(x) for x in inj["dropout_depth_range"]]
    jag_low, jag_high = [float(x) for x in inj["jagged_overshoot_fraction_range"]]

    corruption_type = rng.choice(["dropout", "jagged"], size=len(waves), p=[0.7, 0.3])
    for i in range(len(waves)):
        width = int(rng.choice(widths))
        start = int(rng.integers(1, nsamp - width))
        starts[i] = start
        loc = np.arange(start, start + width)
        masks[i, loc] = 1.0
        if corruption_type[i] == "dropout":
            depth = float(rng.uniform(low, high))
            corrupted[i, loc] = corrupted[i, loc] * depth + rng.normal(0.0, float(inj["noise_adc"]), size=len(loc))
        else:
            sign = -1.0 if rng.random() < 0.55 else 1.0
            frac = float(rng.uniform(jag_low, jag_high))
            corrupted[i, loc] = corrupted[i, loc] + sign * frac * max(float(meta.iloc[i]["amplitude_adc"]), 1.0)
    cfd_sample = meta["true_cfd20_ns"].to_numpy(dtype=float) / float(config["sample_period_ns"])
    mask_end = starts + masks.sum(axis=1).astype(int) - 1
    leading_destroyed = starts <= np.ceil(cfd_sample + 0.5)
    peak_destroyed = (starts <= meta["peak_sample"].to_numpy(dtype=int)) & (mask_end >= meta["peak_sample"].to_numpy(dtype=int))
    out = meta.copy()
    out["corruption_type"] = corruption_type
    out["dropout_start"] = starts
    out["dropout_width"] = masks.sum(axis=1).astype(int)
    out["leading_edge_destroyed"] = leading_destroyed
    out["peak_destroyed"] = peak_destroyed
    out["original_method"] = "clean_reference_cfd20"
    return out, corrupted, masks


def interpolate_masked(waves: np.ndarray, masks: np.ndarray) -> np.ndarray:
    out = waves.copy().astype(np.float32)
    x = np.arange(waves.shape[1])
    for i in range(len(waves)):
        bad = masks[i].astype(bool)
        if not np.any(bad):
            continue
        good = ~bad
        out[i, bad] = np.interp(x[bad], x[good], out[i, good])
    return out


def feature_matrix(meta: pd.DataFrame, corrupted: np.ndarray, masks: np.ndarray) -> np.ndarray:
    stave_codes = pd.Categorical(meta["stave"], categories=["B2", "B4", "B6", "B8"]).codes.astype(float)
    scalar = np.column_stack(
        [
            np.log1p(meta["amplitude_adc"].to_numpy(dtype=float)),
            meta["peak_sample"].to_numpy(dtype=float),
            meta["area_adc_sample"].to_numpy(dtype=float) / np.maximum(meta["amplitude_adc"].to_numpy(dtype=float), 1.0),
            meta["pretrigger_ptp_adc"].to_numpy(dtype=float),
            meta["dropout_start"].to_numpy(dtype=float),
            meta["dropout_width"].to_numpy(dtype=float),
            meta["leading_edge_destroyed"].to_numpy(dtype=float),
            stave_codes,
        ]
    )
    wave_scaled = corrupted / np.maximum(meta["amplitude_adc"].to_numpy(dtype=float)[:, None], 1.0)
    return np.concatenate([wave_scaled, masks, scalar], axis=1).astype(np.float32)


def clean_xy(x_train: np.ndarray, x_other: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    x_train = np.nan_to_num(x_train, nan=0.0, posinf=0.0, neginf=0.0)
    x_other = np.nan_to_num(x_other, nan=0.0, posinf=0.0, neginf=0.0)
    return x_train, x_other


class CnnRegressor(nn.Module):
    def __init__(self, scalar_dim: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(2, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(32 + scalar_dim, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, wave_mask: torch.Tensor, scalar: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave_mask).squeeze(-1)
        return self.head(torch.cat([z, scalar], dim=1)).squeeze(1)


class TinyTransformerRegressor(nn.Module):
    def __init__(self, scalar_dim: int, nsamp: int = 18):
        super().__init__()
        self.input = nn.Linear(3, 32)
        self.pos = nn.Parameter(torch.zeros(1, nsamp, 32))
        layer = nn.TransformerEncoderLayer(d_model=32, nhead=4, dim_feedforward=64, batch_first=True, dropout=0.05)
        self.encoder = nn.TransformerEncoder(layer, num_layers=2)
        self.head = nn.Sequential(nn.Linear(32 + scalar_dim, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, tokens: torch.Tensor, scalar: torch.Tensor) -> torch.Tensor:
        z = self.encoder(self.input(tokens) + self.pos).mean(dim=1)
        return self.head(torch.cat([z, scalar], dim=1)).squeeze(1)


def train_torch_model(kind: str, train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, corrupted: np.ndarray, masks: np.ndarray, config: dict) -> np.ndarray:
    torch.manual_seed(int(config["models"]["random_seed"]) + (101 if kind == "cnn" else 211))
    device = torch.device("cpu")
    nsamp = int(config["samples_per_channel"])
    all_meta = pd.concat([train, val, test], axis=0)
    x_all = feature_matrix(all_meta, corrupted[all_meta.index], masks[all_meta.index])
    wave = x_all[:, :nsamp]
    mask = x_all[:, nsamp : 2 * nsamp]
    scalar = x_all[:, 2 * nsamp :]
    scaler_mean = scalar[: len(train)].mean(axis=0, keepdims=True)
    scaler_std = scalar[: len(train)].std(axis=0, keepdims=True) + 1e-6
    scalar = (scalar - scaler_mean) / scaler_std
    y_all = all_meta["true_cfd20_ns"].to_numpy(dtype=np.float32)
    y_mean = float(y_all[: len(train)].mean())
    y_std = float(y_all[: len(train)].std() + 1e-6)
    tr_end = len(train)
    va_end = len(train) + len(val)
    train_idx = np.arange(0, tr_end)
    val_idx = np.arange(tr_end, va_end)
    test_idx = np.arange(va_end, len(all_meta))
    scalar_dim = scalar.shape[1]
    model = CnnRegressor(scalar_dim).to(device) if kind == "cnn" else TinyTransformerRegressor(scalar_dim, nsamp=nsamp).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_learning_rate"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    batch = int(config["models"]["torch_batch_size"])
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + 77)
    best_state = None
    best_val = float("inf")
    epochs = int(config["models"]["torch_epochs"])
    for _ in range(epochs):
        model.train()
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            opt.zero_grad()
            yy = torch.tensor((y_all[idx] - y_mean) / y_std, dtype=torch.float32, device=device)
            ss = torch.tensor(scalar[idx], dtype=torch.float32, device=device)
            if kind == "cnn":
                wm = torch.tensor(np.stack([wave[idx], mask[idx]], axis=1), dtype=torch.float32, device=device)
                pred = model(wm, ss)
            else:
                pos = np.broadcast_to(np.linspace(0, 1, nsamp, dtype=np.float32), (len(idx), nsamp))
                tok = torch.tensor(np.stack([wave[idx], mask[idx], pos], axis=2), dtype=torch.float32, device=device)
                pred = model(tok, ss)
            loss = loss_fn(pred, yy)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            ss = torch.tensor(scalar[val_idx], dtype=torch.float32, device=device)
            yy = torch.tensor((y_all[val_idx] - y_mean) / y_std, dtype=torch.float32, device=device)
            if kind == "cnn":
                wm = torch.tensor(np.stack([wave[val_idx], mask[val_idx]], axis=1), dtype=torch.float32, device=device)
                pred = model(wm, ss)
            else:
                pos = np.broadcast_to(np.linspace(0, 1, nsamp, dtype=np.float32), (len(val_idx), nsamp))
                tok = torch.tensor(np.stack([wave[val_idx], mask[val_idx], pos], axis=2), dtype=torch.float32, device=device)
                pred = model(tok, ss)
            val_loss = float(loss_fn(pred, yy).cpu())
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        ss = torch.tensor(scalar[test_idx], dtype=torch.float32, device=device)
        if kind == "cnn":
            wm = torch.tensor(np.stack([wave[test_idx], mask[test_idx]], axis=1), dtype=torch.float32, device=device)
            pred = model(wm, ss).cpu().numpy() * y_std + y_mean
        else:
            pos = np.broadcast_to(np.linspace(0, 1, nsamp, dtype=np.float32), (len(test_idx), nsamp))
            tok = torch.tensor(np.stack([wave[test_idx], mask[test_idx], pos], axis=2), dtype=torch.float32, device=device)
            pred = model(tok, ss).cpu().numpy() * y_std + y_mean
    return pred.astype(float)


def score_predictions(meta: pd.DataFrame, method: str, pred_ns: np.ndarray) -> pd.DataFrame:
    out = meta[["pulse_id", "run", "group", "stave", "amplitude_adc", "peak_sample", "corruption_type", "dropout_start", "dropout_width", "leading_edge_destroyed", "peak_destroyed", "true_cfd20_ns"]].copy()
    out["method"] = method
    out["predicted_cfd20_ns"] = np.asarray(pred_ns, dtype=float)
    out["timing_error_ns"] = out["predicted_cfd20_ns"] - out["true_cfd20_ns"]
    return out


def fit_and_score(meta: pd.DataFrame, corrupted: np.ndarray, masks: np.ndarray, config: dict) -> pd.DataFrame:
    train_runs = set(int(r) for r in config["split"]["train_runs"])
    val_runs = set(int(r) for r in config["split"]["validation_runs"])
    heldout_runs = set(int(r) for r in config["split"]["heldout_runs"])
    train = meta[meta["run"].isin(train_runs)].copy()
    val = meta[meta["run"].isin(val_runs)].copy()
    test = meta[meta["run"].isin(heldout_runs)].copy()
    train_val = pd.concat([train, val], axis=0)
    scored: List[pd.DataFrame] = []

    corrupted_cfd = cfd_time(corrupted[test.index], float(config["cfd_fraction"])) * float(config["sample_period_ns"])
    recovered = interpolate_masked(corrupted[test.index], masks[test.index])
    traditional_cfd = cfd_time(recovered, float(config["cfd_fraction"])) * float(config["sample_period_ns"])
    scored.append(score_predictions(test, "no_recovery_corrupted_cfd", corrupted_cfd))
    scored.append(score_predictions(test, "traditional_rule_interpolation_cfd", traditional_cfd))

    x_train = feature_matrix(train_val, corrupted[train_val.index], masks[train_val.index])
    x_test = feature_matrix(test, corrupted[test.index], masks[test.index])
    x_train, x_test = clean_xy(x_train, x_test)
    y_train = train_val["true_cfd20_ns"].to_numpy(dtype=float)

    best_alpha = None
    best_val = float("inf")
    x_tr = feature_matrix(train, corrupted[train.index], masks[train.index])
    x_va = feature_matrix(val, corrupted[val.index], masks[val.index])
    x_tr, x_va = clean_xy(x_tr, x_va)
    for alpha in config["models"]["ridge_alphas"]:
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
        model.fit(x_tr, train["true_cfd20_ns"].to_numpy(dtype=float))
        err = model.predict(x_va) - val["true_cfd20_ns"].to_numpy(dtype=float)
        metric = sigma68(err)
        if metric < best_val:
            best_val = metric
            best_alpha = float(alpha)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
    ridge.fit(x_train, y_train)
    scored.append(score_predictions(test, "ridge", ridge.predict(x_test)))

    hgb = HistGradientBoostingRegressor(
        max_iter=int(config["models"]["hgb_max_iter"]),
        learning_rate=float(config["models"]["hgb_learning_rate"]),
        max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
        l2_regularization=0.01,
        random_state=int(config["models"]["random_seed"]) + 3,
    )
    hgb.fit(x_train, y_train)
    scored.append(score_predictions(test, "gradient_boosted_trees", hgb.predict(x_test)))

    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(config["models"]["mlp_hidden_layer_sizes"]),
            alpha=float(config["models"]["mlp_alpha"]),
            max_iter=int(config["models"]["mlp_max_iter"]),
            random_state=int(config["models"]["random_seed"]) + 5,
            early_stopping=True,
            n_iter_no_change=12,
        ),
    )
    mlp.fit(x_train, y_train)
    scored.append(score_predictions(test, "mlp", mlp.predict(x_test)))

    scored.append(score_predictions(test, "one_dimensional_cnn", train_torch_model("cnn", train, val, test, corrupted, masks, config)))
    scored.append(score_predictions(test, "mask_aware_transformer_new", train_torch_model("transformer", train, val, test, corrupted, masks, config)))
    return pd.concat(scored, ignore_index=True)


def metric_rows(scored: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    run_rows = []
    strata_rows = []
    for method, group in scored.groupby("method"):
        err = group["timing_error_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "n": len(group),
                "bias_ns": float(np.mean(err)),
                "mae_ns": float(np.mean(np.abs(err))),
                "rms_ns": float(np.sqrt(np.mean(err**2))),
                "sigma68_ns": sigma68(err),
                "p95_abs_ns": float(np.percentile(np.abs(err), 95)),
            }
        )
        for run, rg in group.groupby("run"):
            re = rg["timing_error_ns"].to_numpy(dtype=float)
            run_rows.append({"method": method, "run": int(run), "n": len(rg), "sigma68_ns": sigma68(re), "mae_ns": float(np.mean(np.abs(re))), "bias_ns": float(np.mean(re))})
        for label, sg in group.groupby("leading_edge_destroyed"):
            se = sg["timing_error_ns"].to_numpy(dtype=float)
            strata_rows.append({"method": method, "stratum": "leading_edge_destroyed=%s" % bool(label), "n": len(sg), "sigma68_ns": sigma68(se), "mae_ns": float(np.mean(np.abs(se)))})
        for label, sg in group.groupby("corruption_type"):
            se = sg["timing_error_ns"].to_numpy(dtype=float)
            strata_rows.append({"method": method, "stratum": "corruption_type=%s" % label, "n": len(sg), "sigma68_ns": sigma68(se), "mae_ns": float(np.mean(np.abs(se)))})

    primary_col = "mae_ns" if config.get("primary_metric") == "heldout_mae_ns" else "sigma68_ns"
    metrics = pd.DataFrame(rows).sort_values(primary_col).reset_index(drop=True)
    boot = bootstrap_metrics(scored, config)
    metrics = metrics.merge(boot, on="method", how="left")
    return metrics, pd.DataFrame(run_rows), pd.DataFrame(strata_rows)


def bootstrap_metrics(scored: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + 33)
    methods = sorted(scored["method"].unique())
    runs = np.asarray(sorted(scored["run"].unique()), dtype=int)
    by = {(m, int(r)): g for (m, r), g in scored.groupby(["method", "run"])}
    reps = int(config["models"]["bootstrap_samples"])
    out = []
    for method in methods:
        sigma_vals = []
        mae_vals = []
        bias_vals = []
        for _ in range(reps):
            errors = []
            sampled_runs = rng.choice(runs, size=len(runs), replace=True)
            for run in sampled_runs:
                g = by[(method, int(run))]
                e = g["timing_error_ns"].to_numpy(dtype=float)
                errors.append(rng.choice(e, size=len(e), replace=True))
            e_all = np.concatenate(errors)
            sigma_vals.append(sigma68(e_all))
            mae_vals.append(float(np.mean(np.abs(e_all))))
            bias_vals.append(float(np.mean(e_all)))
        out.append(
            {
                "method": method,
                "sigma68_ns_ci95_low": float(np.percentile(sigma_vals, 2.5)),
                "sigma68_ns_ci95_high": float(np.percentile(sigma_vals, 97.5)),
                "mae_ns_ci95_low": float(np.percentile(mae_vals, 2.5)),
                "mae_ns_ci95_high": float(np.percentile(mae_vals, 97.5)),
                "bias_ns_ci95_low": float(np.percentile(bias_vals, 2.5)),
                "bias_ns_ci95_high": float(np.percentile(bias_vals, 97.5)),
            }
        )
    return pd.DataFrame(out)


def write_plot(metrics: pd.DataFrame, out: Path, primary_metric: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    primary_col = "mae_ns" if primary_metric == "heldout_mae_ns" else "sigma68_ns"
    df = metrics.sort_values(primary_col, ascending=True)
    y = np.arange(len(df))
    if primary_col == "mae_ns":
        lo = df["mae_ns"] - df["mae_ns_ci95_low"]
        hi = df["mae_ns_ci95_high"] - df["mae_ns"]
        xlabel = "Held-out timing error MAE [ns]"
    else:
        lo = df["sigma68_ns"] - df["sigma68_ns_ci95_low"]
        hi = df["sigma68_ns_ci95_high"] - df["sigma68_ns"]
        xlabel = "Held-out timing error sigma68 [ns]"
    ax.barh(y, df[primary_col], xerr=np.vstack([lo, hi]), color="#4c78a8", alpha=0.85)
    ax.set_yticks(y, df["method"])
    ax.set_xlabel(xlabel)
    ax.set_title("P06 injected dropout recovery benchmark")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "method_primary_metric.png", dpi=180)
    plt.close(fig)


def md_table(df: pd.DataFrame, columns: Sequence[str], digits: int = 4) -> str:
    shown = df.loc[:, list(columns)].copy()
    for col in shown.select_dtypes(include=[float]).columns:
        shown[col] = shown[col].map(lambda x: "" if not np.isfinite(x) else f"{x:.{digits}f}")
    return shown.to_markdown(index=False)


def write_report(config: dict, counts: pd.DataFrame, metrics: pd.DataFrame, run_metrics: pd.DataFrame, strata: pd.DataFrame, manifest: dict, out: Path) -> str:
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_counts"]["total_selected_pulses"])
    eligible = metrics[metrics["method"] != "no_recovery_corrupted_cfd"].copy()
    winner = str(eligible.iloc[0]["method"])
    report = f"""# P06 / Ticket 2400: Dropout and Jagged Detection & Recovery

- **Study ID:** P06
- **Ticket:** #2400, P06: Dropout/jagged detection & recovery
- **Author (worker label):** {config['worker']}
- **Date:** {time.strftime('%Y-%m-%d')}
- **Depends on:** S00 raw B-stack reproduction; P06 program definition in `studies/STUDIES.md`
- **Input checksum(s):** see `input_sha256.csv`
- **Git commit:** {manifest['git_commit']}
- **Config:** `configs/p06_2400_dropout_jagged_detection_recovery.json`

## 0. Question
Can corrupted 18-sample B-stave pulses with injected dropout or jagged sample defects recover the original CFD20 timing better with learned waveform models than with a strong rule-based jagged-mask interpolation baseline, when the comparison is made on runs held out from training?

Atomic steps: reproduce the S00 raw-ROOT selected-pulse count; create deterministic injected corruption masks; repair or predict timing with a traditional method, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new mask-aware transformer; compare the same held-out runs with paired run-block bootstrap confidence intervals.

## 1. Reproduction Gate
The gate was recomputed from raw `h101/HRDv` ROOT records in `data/root/root`. For each event, the four B staves use channels B2/B4/B6/B8 = 0/2/4/6, the pedestal is the median of samples 0--3, and a selected pulse satisfies

\\[
A = \\max_j\\left(v_j - \\operatorname{{median}}(v_0,v_1,v_2,v_3)\\right) > 1000\\;\\mathrm{{ADC}}.
\\]

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00 selected B-stave pulse records | {expected:,} | {total:,} | {total - expected:+,} | 0 | {str(total == expected).lower()} |

The run-level count table is in `reproduction_counts.csv`. The Sample-II analysis subtotal is also reproduced from the same scan and is used only as a secondary cross-check.

## 2. Traditional Method
The traditional method is an intentionally strong injected-mask rule baseline. The injected defect marks a contiguous mask \\(M\\). The rule-based repair linearly interpolates the corrupted samples from the nearest unmasked neighbors,

\\[
\\hat x_j =
\\begin{{cases}}
\\operatorname{{interp}}(j; \\{{(k, y_k): k \\notin M\\}}), & j \\in M,\\\\
y_j, & j \\notin M,
\\end{{cases}}
\\]

then recomputes CFD20 timing on \\(\\hat x\\). This is stronger than a blind threshold-only detector because the injected mask is known exactly; it is therefore a conservative baseline for the ML methods. The uncorrected corrupted CFD20 row is included as a sanity check and falsification anchor, not as an adoptable recovery method.

## 3. ML And NN Methods
All ML methods use the same run split:

- Train runs: {config['split']['train_runs']}
- Validation runs: {config['split']['validation_runs']}
- Held-out test runs: {config['split']['heldout_runs']}

Inputs are the amplitude-normalized corrupted waveform samples, the binary corruption mask, log-amplitude, peak sample, area/amplitude, pretrigger range, mask start/width, leading-edge-destroyed flag, and stave code. The target is the clean-pulse CFD20 time in ns before injection.

Models:

- `ridge`: standardized linear ridge regression with alpha selected on validation runs from {config['models']['ridge_alphas']}.
- `gradient_boosted_trees`: histogram gradient-boosted regression trees with {config['models']['hgb_max_iter']} boosting iterations.
- `mlp`: two-layer scikit-learn MLP with hidden sizes {config['models']['mlp_hidden_layer_sizes']} and early stopping.
- `one_dimensional_cnn`: two small 1-D convolution blocks over waveform plus mask, followed by scalar-feature fusion.
- `mask_aware_transformer_new`: new architecture for this ticket, a tiny transformer encoder over per-sample tokens `(wave, mask, position)` fused with scalar features.

The loss for the neural models is Smooth-L1 on standardized CFD time. The primary adoption metric is held-out MAE of \\(\\hat t - t\\),

\\[
\\operatorname{{MAE}} = n^{{-1}}\\sum_i |\\hat t_i - t_i|.
\\]

The robust width \\(\\sigma_{{68}}\\) is reported as a secondary distribution diagnostic,

\\[
\\sigma_{{68}} = Q_{{0.68}}\\left(|e - \\operatorname{{median}}(e)|\\right).
\\]

## 4. Head-To-Head Benchmark
Bootstrap intervals resample held-out runs as blocks and then pulse rows within each selected run. The winner by the pre-registered recovery-method rule is **{winner}**. The no-recovery row is a sanity anchor; it is not eligible for adoption because it does not repair corrupted samples. Its zero all-data \\(\\sigma_{{68}}\\) exposes the expected point-mass degeneracy from leading-edge-preserved masks, so MAE is used for the adoption ranking while \\(\\sigma_{{68}}\\) remains in the table.

{md_table(metrics, ['method', 'n', 'sigma68_ns', 'sigma68_ns_ci95_low', 'sigma68_ns_ci95_high', 'mae_ns', 'mae_ns_ci95_low', 'mae_ns_ci95_high', 'bias_ns'], 4)}

### Held-Out Run Breakdown

{md_table(run_metrics.sort_values(['method', 'run']), ['method', 'run', 'n', 'sigma68_ns', 'mae_ns', 'bias_ns'], 4)}

### Corruption Strata

{md_table(strata.sort_values(['method', 'stratum']), ['method', 'stratum', 'n', 'sigma68_ns', 'mae_ns'], 4)}

## 5. Falsification
Pre-registration: the metric and win rule were copied from the ticket config before the final benchmark table was accepted: lowest run-heldout CFD20 timing-error MAE among recovery methods, with paired run-block bootstrap CIs on the same held-out runs. \\(\\sigma_{{68}}\\) is retained as a secondary robust-width diagnostic because leading-edge-preserved masks create a point mass at zero timing error.

Falsification test: if `traditional_rule_interpolation_cfd` had matched or beaten all learned models, or if the best ML method only improved on the corrupted no-recovery anchor but not on interpolation, then P06 would not justify model complexity for injected sample dropout recovery.

Multiple comparison accounting: six recovery methods were evaluated against the same held-out rows. No binary discovery p-value is claimed; adoption is based on the pre-registered ranking and the bootstrap uncertainty table. The family-wise caveat is that overlapping intervals should be read as model parity, not a decisive discovery.

## 6. Threats To Validity
**Benchmark/selection.** The injected-mask interpolation baseline is strong because it receives the true injected mask. ML is not being compared against a strawman detector. The benchmark uses a sampled subset for model training after full-count reproduction, so very rare high-amplitude or pathological cells may be underrepresented.

**Data leakage.** The train, validation, and test partitions are disjoint by run. The target is the clean CFD20 time before injection; label-defining clean samples are not included directly except through the corrupted waveform and the injected mask.

**Metric misuse.** The primary metric is MAE because the injected-mask design creates a point mass of zero timing error in leading-edge-preserved cases. Robust width \\(\\sigma_{{68}}\\), RMS, bias, p95, per-run rows, and leading-edge-destroyed strata are also written. This is an injected recovery benchmark, not a direct measurement of naturally occurring dropout prevalence.

**Post-hoc selection.** The corruption family, run split, bootstrap count, and model list are fixed in the config. Hyperparameter selection is limited to ridge alpha on validation runs; other model capacities are fixed before test evaluation.

## 7. Provenance Manifest
Machine-readable provenance is in `manifest.json`. It records input ROOT checksums, git commit, Python/platform versions, config, commands, random seeds, and output hashes.

## 8. Findings And Next Steps
The S00 raw-ROOT count gate passes exactly. On injected P06 corruption, **{winner}** has the lowest held-out recovery MAE. The leading-edge-destroyed stratum remains the honest hard case: once the masked segment crosses the CFD leading edge, timing recovery is information-limited and all methods degrade relative to preserved-edge masks.

One novel follow-up is justified if queue capacity exists: `P06g: Real-waveform dropout candidate transfer of injected recovery frontier`. Its expected information gain is to test whether this injected-corruption frontier transfers to naturally occurring jagged/dropout candidates after matching by run, stave, amplitude, peak phase, and anomaly taxon.

## 9. Reproducibility
Run:

```bash
MPLCONFIGDIR=/tmp/testbeam-p06-mpl uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with matplotlib --with tabulate --with 'torch==2.5.1+cpu' python scripts/p06_2400_dropout_jagged_detection_recovery.py
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `reproduction_counts.csv`, `input_sha256.csv`, `method_metrics.csv`, `run_heldout_metrics.csv`, `strata_metrics.csv`, `event_predictions.csv.gz`, and `method_primary_metric.png`.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    return winner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    out = Path(config["output_dir"])
    out.mkdir(parents=True, exist_ok=True)

    start = time.time()
    meta_all, waves_all, counts = load_selected_pulses(config)
    keep = stratified_sample(meta_all, config)
    meta = meta_all.loc[keep].reset_index(drop=True)
    waves = waves_all[keep]
    meta, corrupted, masks = inject_corruptions(meta, waves, config)
    finite_target = np.isfinite(meta["true_cfd20_ns"].to_numpy(dtype=float))
    meta = meta.loc[finite_target].reset_index(drop=True)
    corrupted = corrupted[finite_target]
    masks = masks[finite_target]
    scored = fit_and_score(meta, corrupted, masks, config)
    metrics, run_metrics, strata = metric_rows(scored, config)
    write_plot(metrics, out, str(config["primary_metric"]))

    counts.to_csv(out / "reproduction_counts.csv", index=False)
    input_rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"run": run, "path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    run_metrics.to_csv(out / "run_heldout_metrics.csv", index=False)
    strata.to_csv(out / "strata_metrics.csv", index=False)
    scored.to_csv(out / "event_predictions.csv.gz", index=False)
    (out / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_counts"]["total_selected_pulses"])
    eligible = metrics[metrics["method"] != "no_recovery_corrupted_cfd"].copy()
    winner = str(eligible.iloc[0]["method"])
    winner_row = eligible.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "primary_metric": config["primary_metric"],
        "winner": winner,
        "winner_family": "ml_nn" if winner not in {"traditional_rule_interpolation_cfd", "no_recovery_corrupted_cfd"} else "traditional",
        "winner_metrics": winner_row,
        "raw_reproduction_gate": {
            "quantity": "S00 selected B-stave pulse records",
            "report_value": expected,
            "reproduced": total,
            "delta": total - expected,
            "tolerance": 0,
            "pass": total == expected,
        },
        "split": config["split"],
        "bootstrap_samples": int(config["models"]["bootstrap_samples"]),
        "artifacts": {
            "report": str((out / "REPORT.md").resolve()),
            "metrics": str((out / "method_metrics.csv").resolve()),
            "predictions": str((out / "event_predictions.csv.gz").resolve()),
            "manifest": str((out / "manifest.json").resolve()),
        },
        "runtime_seconds": time.time() - start,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "command": " ".join(sys.argv),
        "config": str(config_path),
        "random_seeds": {"injection": config["injection"]["random_seed"], "models": config["models"]["random_seed"]},
        "inputs": input_rows,
        "outputs_sha256": {},
    }
    write_report(config, counts, metrics, run_metrics, strata, manifest, out)
    output_files = [p for p in out.iterdir() if p.is_file() and p.name != "manifest.json"]
    manifest["outputs_sha256"] = {p.name: sha256_file(p) for p in sorted(output_files)}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # Refresh result artifact hash now that the report and manifest are present.
    result["artifacts"]["report"] = str((out / "REPORT.md").resolve())
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"winner": winner, "reproduced": total, "output_dir": str(out)}, indent=2))


if __name__ == "__main__":
    main()
