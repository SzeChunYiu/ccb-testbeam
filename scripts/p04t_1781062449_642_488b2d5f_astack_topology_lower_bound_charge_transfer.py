#!/usr/bin/env python3
"""P04t: A-stack topology lower-bound charge transfer.

This follows P04c/P04d's raw ROOT event matching, reproduces the broad
A/B charge-transfer number first, then asks what lower bound is achievable
inside A1-only, A3-only, and A1+A3 topologies when the B-stack support
information is kept fixed and the split is strictly leave-one-run-out.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.set_num_threads(1)
except Exception:  # pragma: no cover - recorded in artifacts when unavailable
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_p04c_module(path: Path):
    spec = importlib.util.spec_from_file_location("p04c_ab_event_matched_charge_transfer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)),
    }


def run_block_ci(frame: pd.DataFrame, value_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {"bias_ci95": [None, None], "res68_ci95": [None, None], "full_rms_ci95": [None, None]}
    by_run = {run: frame[frame["run"] == run] for run in runs}
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    for idx in range(reps):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in sample_runs], ignore_index=True)
        frac = (sample[pred_col].to_numpy() - sample[value_col].to_numpy()) / np.maximum(sample[value_col].to_numpy(), 1.0)
        bias[idx] = np.median(frac)
        res68[idx] = np.percentile(np.abs(frac), 68)
        rms[idx] = np.sqrt(np.mean(frac * frac))
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
    }


def b_charge_features(frame: pd.DataFrame) -> np.ndarray:
    b2q = np.log(np.maximum(frame["b2_charge"].to_numpy(), 1.0))
    b2a = np.log(np.maximum(frame["b2_amp"].to_numpy(), 1.0))
    bt = np.log(np.maximum(frame["b_total_charge"].to_numpy(), 1.0))
    bd = np.log1p(frame["b_downstream_charge"].to_numpy())
    down_frac = frame["b_downstream_charge"].to_numpy() / np.maximum(frame["b_total_charge"].to_numpy(), 1.0)
    return np.column_stack(
        [
            b2q,
            b2a,
            bt,
            bd,
            b2q * b2q,
            b2a * b2a,
            bt * bt,
            b2q * bt,
            down_frac,
            frame["b_mult"].to_numpy(),
            frame["b_downstream_mult"].to_numpy(),
            frame["B4_selected"].to_numpy(),
            frame["B6_selected"].to_numpy(),
            frame["B8_selected"].to_numpy(),
            frame["B2_peak"].to_numpy(),
            frame["B4_peak"].to_numpy(),
            frame["B6_peak"].to_numpy(),
            frame["B8_peak"].to_numpy(),
        ]
    )


def waveform_features(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    charge = np.clip(wave, 0.0, None).sum(axis=2)
    amp = wave.max(axis=2)
    peak = wave.argmax(axis=2)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, :, 12:], 0.0, None).sum(axis=2) / total
    late = np.clip(wave[:, :, 9:], 0.0, None).sum(axis=2) / total
    half_width = (wave > (0.5 * amp[:, :, None])).sum(axis=2)
    engineered = np.column_stack(
        [
            np.log(np.maximum(charge, 1.0)),
            np.log(np.maximum(amp, 1.0)),
            peak,
            tail,
            late,
            half_width,
            frame["b_mult"].to_numpy(),
            frame["b_downstream_mult"].to_numpy(),
        ]
    )
    return np.column_stack([wave.reshape(len(wave), -1), engineered])


def support_cell(frame: pd.DataFrame) -> pd.Series:
    b2_bin = pd.cut(
        frame["b2_amp"],
        bins=[1000, 2000, 3000, 5000, 7000, np.inf],
        labels=["b2_1_2k", "b2_2_3k", "b2_3_5k", "b2_5_7k", "b2_7k_inf"],
        include_lowest=True,
    ).astype(str)
    bmask = (
        frame["B4_selected"].astype(str)
        + frame["B6_selected"].astype(str)
        + frame["B8_selected"].astype(str)
    )
    peak_atom = np.where(frame["B2_peak"].to_numpy() >= 15, "latepeak", "inwindow")
    return frame["topology"].astype(str) + "|" + b2_bin + "|b" + bmask + "|" + pd.Series(peak_atom, index=frame.index)


class Cnn1DRegressor(nn.Module):
    def __init__(self, n_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(n_channels, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(16, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, wave: "torch.Tensor", tab: "torch.Tensor") -> "torch.Tensor":
        del tab
        z = self.conv(wave).squeeze(-1)
        return self.head(z).squeeze(1)


class HybridSupportGateRegressor(nn.Module):
    def __init__(self, n_channels: int, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(n_channels, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 16, kernel_size=5, padding=2),
            nn.ReLU(),
        )
        self.tab = nn.Sequential(nn.Linear(n_tab, 16), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(n_tab, 16), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(32, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, wave: "torch.Tensor", tab: "torch.Tensor") -> "torch.Tensor":
        z = self.conv(wave)
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        gate = self.gate(tab)
        tab_z = self.tab(tab)
        return self.head(torch.cat([pooled[:, :16] * gate, tab_z], dim=1)).squeeze(1)


def fit_torch_regressor(
    kind: str,
    train_wave: np.ndarray,
    train_tab: np.ndarray,
    train_y: np.ndarray,
    test_wave: np.ndarray,
    test_tab: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, dict]:
    if torch is None:
        return np.full(len(test_wave), np.nan), {"skipped": "torch_unavailable"}
    rng = np.random.default_rng(seed)
    idx = np.arange(len(train_y))
    if len(idx) > int(config["nn_max_train_rows"]):
        idx = rng.choice(idx, size=int(config["nn_max_train_rows"]), replace=False)

    wave_train = train_wave[idx].astype(np.float32)
    tab_train = train_tab[idx].astype(np.float32)
    y = train_y[idx].astype(np.float32)
    y_center = float(np.median(y))
    y_scale = float(np.std(y) + 1e-6)
    y_scaled = ((y - y_center) / y_scale).astype(np.float32)

    tab_center = np.nanmedian(tab_train, axis=0).astype(np.float32)
    tab_scale = (np.nanstd(tab_train, axis=0) + 1e-6).astype(np.float32)
    tab_train = (tab_train - tab_center) / tab_scale
    tab_test = (test_tab.astype(np.float32) - tab_center) / tab_scale

    torch.manual_seed(seed)
    model = Cnn1DRegressor(wave_train.shape[1]) if kind == "cnn1d_waveform" else HybridSupportGateRegressor(wave_train.shape[1], tab_train.shape[1])
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["torch_learning_rate"]),
        weight_decay=float(config["torch_weight_decay"]),
    )
    loss_fn = nn.SmoothL1Loss()
    dataset = TensorDataset(
        torch.from_numpy(wave_train),
        torch.from_numpy(tab_train),
        torch.from_numpy(y_scaled),
    )
    loader = DataLoader(dataset, batch_size=int(config["torch_batch_size"]), shuffle=True)
    model.train()
    final_loss = np.nan
    for _epoch in range(int(config["torch_epochs"])):
        for wb, tb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(wb, tb), yb)
            loss.backward()
            opt.step()
            final_loss = float(loss.detach().cpu().item())

    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(test_wave), 2048):
            stop = start + 2048
            out = model(torch.from_numpy(test_wave[start:stop].astype(np.float32)), torch.from_numpy(tab_test[start:stop]))
            preds.append(out.cpu().numpy())
    pred_log = np.concatenate(preds) * y_scale + y_center
    lower = max(0.0, float(np.percentile(y, 0.5) - 1.0))
    upper = float(np.percentile(y, 99.5) + 1.0)
    pred_log = np.nan_to_num(pred_log, nan=y_center, posinf=upper, neginf=lower)
    pred_log = np.clip(pred_log, lower, upper)
    return np.exp(pred_log), {
        "epochs": int(config["torch_epochs"]),
        "final_loss": final_loss,
        "train_rows": int(len(idx)),
        "log_prediction_clip": [lower, upper],
    }


def metric_delta_ci(
    frame: pd.DataFrame,
    value_col: str,
    method_col: str,
    baseline_col: str,
    rng: np.random.Generator,
    reps: int,
) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {"delta_res68_ci95": [None, None], "delta_full_rms_ci95": [None, None]}
    by_run = {run: frame[frame["run"] == run] for run in runs}
    d_res68 = np.empty(reps, dtype=float)
    d_rms = np.empty(reps, dtype=float)
    for idx in range(reps):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in sample_runs], ignore_index=True)
        y = sample[value_col].to_numpy()
        denom = np.maximum(y, 1.0)
        frac_m = (sample[method_col].to_numpy() - y) / denom
        frac_b = (sample[baseline_col].to_numpy() - y) / denom
        d_res68[idx] = np.percentile(np.abs(frac_m), 68) - np.percentile(np.abs(frac_b), 68)
        d_rms[idx] = np.sqrt(np.mean(frac_m * frac_m)) - np.sqrt(np.mean(frac_b * frac_b))
    return {
        "delta_res68_ci95": [float(np.percentile(d_res68, 2.5)), float(np.percentile(d_res68, 97.5))],
        "delta_full_rms_ci95": [float(np.percentile(d_rms, 2.5)), float(np.percentile(d_rms, 97.5))],
    }


def build_topology_frame(frame: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, np.ndarray]:
    pieces: List[pd.DataFrame] = []
    wave_idx: List[np.ndarray] = []
    definitions = [
        ("A1_only", (frame["A1_selected"] == 1) & (frame["A3_selected"] == 0), "A1_charge", "A1 selected, A3 quiet"),
        ("A3_only", (frame["A1_selected"] == 0) & (frame["A3_selected"] == 1), "A3_charge", "A3 selected, A1 quiet"),
        ("A1A3", (frame["A1_selected"] == 1) & (frame["A3_selected"] == 1), None, "A1 and A3 both selected"),
    ]
    for topology, mask, charge_col, description in definitions:
        idx = np.where(mask.to_numpy())[0]
        if len(idx) == 0:
            continue
        sub = frame.iloc[idx].copy()
        sub["topology"] = topology
        sub["topology_definition"] = description
        sub["source_row"] = idx.astype(np.int64)
        if charge_col is None:
            sub["target_charge"] = sub["A1_charge"] + sub["A3_charge"]
        else:
            sub["target_charge"] = sub[charge_col]
        pieces.append(sub)
        wave_idx.append(idx)
    if not pieces:
        raise RuntimeError("no topology rows were built")
    topo = pd.concat(pieces, ignore_index=True)
    topo_wave = wave[np.concatenate(wave_idx)]
    return topo, topo_wave


def model_topologies(config: dict, topo: pd.DataFrame, topo_wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    methods = [
        "topology_median",
        "ridge_log_charge",
        "huber_log_charge",
        "gradient_boosted_trees",
        "extra_trees",
        "mlp",
        "cnn1d_waveform",
        "hybrid_support_gate_cnn",
        "shuffled_target_extra_trees",
    ]
    for method in methods:
        topo[f"pred_{method}"] = np.nan

    topo["support_cell"] = support_cell(topo)
    x_b = b_charge_features(topo).astype(np.float64)
    x_w = waveform_features(topo, topo_wave).astype(np.float64)
    wave_nn = np.clip(topo_wave, -5000.0, 25000.0).astype(np.float32)
    wave_center = np.nanmedian(wave_nn, axis=(0, 2), keepdims=True)
    wave_scale = np.nanstd(wave_nn, axis=(0, 2), keepdims=True) + 1e-6
    wave_nn = ((wave_nn - wave_center) / wave_scale).astype(np.float32)
    y_log = np.log(np.maximum(topo["target_charge"].to_numpy(), 1.0))
    runs = np.asarray(sorted(topo["run"].unique()), dtype=int)
    fold_rows = []

    for heldout_run in runs:
        held_mask_all = topo["run"].to_numpy() == heldout_run
        train_mask_all = ~held_mask_all
        train = topo.loc[train_mask_all]

        for topology, held_idx in topo.loc[held_mask_all].groupby("topology").groups.items():
            same_topo_train_mask = train_mask_all & (topo["topology"].to_numpy() == topology)
            same_topo_train_idx = np.where(same_topo_train_mask)[0]
            held_idx_array = np.asarray(list(held_idx), dtype=int)
            train_values = topo.loc[same_topo_train_idx, "target_charge"].to_numpy()
            if len(train_values) == 0:
                train_values = train["target_charge"].to_numpy()
            topo.loc[held_idx_array, "pred_topology_median"] = float(np.median(train_values))

            if len(same_topo_train_idx) < 8:
                fallback = float(np.median(train_values))
                for method in methods[1:]:
                    topo.loc[held_idx_array, f"pred_{method}"] = fallback
                continue

            ridge = make_pipeline(StandardScaler(), Ridge(alpha=8.0, random_state=None))
            ridge.fit(x_b[same_topo_train_idx], y_log[same_topo_train_idx])
            topo.loc[held_idx_array, "pred_ridge_log_charge"] = np.exp(ridge.predict(x_b[held_idx_array]))

            huber = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=400))
            huber.fit(x_b[same_topo_train_idx], y_log[same_topo_train_idx])
            topo.loc[held_idx_array, "pred_huber_log_charge"] = np.exp(huber.predict(x_b[held_idx_array]))

            ml_train_idx = same_topo_train_idx
            if len(ml_train_idx) > int(config["ml_max_train_rows"]):
                ml_train_idx = rng.choice(ml_train_idx, size=int(config["ml_max_train_rows"]), replace=False)

            hgb = HistGradientBoostingRegressor(
                loss="squared_error",
                learning_rate=0.055,
                max_iter=70,
                max_leaf_nodes=11,
                min_samples_leaf=8,
                l2_regularization=0.05,
                max_bins=64,
                random_state=int(config["random_seed"]) + int(heldout_run) * 17 + len(topology),
            )
            hgb.fit(x_w[ml_train_idx], y_log[ml_train_idx])
            topo.loc[held_idx_array, "pred_gradient_boosted_trees"] = np.exp(hgb.predict(x_w[held_idx_array]))

            et = ExtraTreesRegressor(
                n_estimators=96,
                max_depth=8,
                min_samples_leaf=3,
                max_features=0.7,
                n_jobs=1,
                random_state=int(config["random_seed"]) + int(heldout_run) * 11 + len(topology),
            )
            et.fit(x_w[ml_train_idx], y_log[ml_train_idx])
            topo.loc[held_idx_array, "pred_extra_trees"] = np.exp(et.predict(x_w[held_idx_array]))

            mlp_train_idx = ml_train_idx
            if len(mlp_train_idx) > int(config["nn_max_train_rows"]):
                mlp_train_idx = rng.choice(mlp_train_idx, size=int(config["nn_max_train_rows"]), replace=False)
            mlp = make_pipeline(
                StandardScaler(),
                MLPRegressor(
                    hidden_layer_sizes=(48, 24),
                    activation="relu",
                    alpha=0.002,
                    learning_rate_init=0.002,
                    max_iter=500,
                    early_stopping=True,
                    validation_fraction=0.20,
                    n_iter_no_change=12,
                    random_state=int(config["random_seed"]) + int(heldout_run) * 19 + len(topology),
                ),
            )
            mlp.fit(x_w[mlp_train_idx], y_log[mlp_train_idx])
            topo.loc[held_idx_array, "pred_mlp"] = np.exp(mlp.predict(x_w[held_idx_array]))

            for torch_method in ["cnn1d_waveform", "hybrid_support_gate_cnn"]:
                pred, meta = fit_torch_regressor(
                    torch_method,
                    wave_nn[ml_train_idx],
                    x_b[ml_train_idx],
                    y_log[ml_train_idx],
                    wave_nn[held_idx_array],
                    x_b[held_idx_array],
                    config,
                    int(config["random_seed"]) + int(heldout_run) * 23 + len(topology) + (0 if torch_method == "cnn1d_waveform" else 1000),
                )
                topo.loc[held_idx_array, f"pred_{torch_method}"] = pred
                fold_rows.append(
                    {
                        "heldout_run": int(heldout_run),
                        "topology": topology,
                        "method": torch_method,
                        **meta,
                    }
                )

            shuffled = y_log[ml_train_idx].copy()
            rng.shuffle(shuffled)
            sentinel = ExtraTreesRegressor(
                n_estimators=64,
                max_depth=8,
                min_samples_leaf=3,
                max_features=0.7,
                n_jobs=1,
                random_state=73 + int(heldout_run) * 13 + len(topology),
            )
            sentinel.fit(x_w[ml_train_idx], shuffled)
            topo.loc[held_idx_array, "pred_shuffled_target_extra_trees"] = np.exp(sentinel.predict(x_w[held_idx_array]))

    ci_rng = np.random.default_rng(int(config["random_seed"]) + 900)
    summary_rows = []
    by_run_rows = []
    for topology, sub in topo.groupby("topology"):
        for method in methods:
            row = {"topology": topology, "method": method}
            row.update(robust_metrics(sub["target_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
            row.update(run_block_ci(sub, "target_charge", f"pred_{method}", ci_rng, int(config["bootstrap_reps"])))
            summary_rows.append(row)
        for run, run_sub in sub.groupby("run"):
            for method in methods[:-1]:
                row = {"topology": topology, "run": int(run), "method": method}
                row.update(robust_metrics(run_sub["target_charge"].to_numpy(), run_sub[f"pred_{method}"].to_numpy()))
                by_run_rows.append(row)

    delta_rows = []
    delta_rng = np.random.default_rng(int(config["random_seed"]) + 1900)
    for topology, sub in topo.groupby("topology"):
        base_col = "pred_huber_log_charge"
        base = robust_metrics(sub["target_charge"].to_numpy(), sub[base_col].to_numpy())
        for method in methods:
            if method == "shuffled_target_extra_trees":
                continue
            metrics = robust_metrics(sub["target_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy())
            row = {
                "topology": topology,
                "method": method,
                "baseline": "huber_log_charge",
                "delta_res68_vs_huber": float(metrics["res68_abs_frac"] - base["res68_abs_frac"]),
                "delta_full_rms_vs_huber": float(metrics["full_rms_frac"] - base["full_rms_frac"]),
            }
            row.update(metric_delta_ci(sub, "target_charge", f"pred_{method}", base_col, delta_rng, int(config["bootstrap_reps"])))
            delta_rows.append(row)

    leakage_rows = []
    wave_hash = np.asarray([hashlib.sha1(np.ascontiguousarray(row).view(np.uint8)).hexdigest() for row in topo_wave])
    for topology, sub in topo.groupby("topology"):
        exact_overlap = 0
        for heldout_run in sorted(sub["run"].unique()):
            held_idx = sub.index[sub["run"] == heldout_run].to_numpy()
            train_idx = sub.index[sub["run"] != heldout_run].to_numpy()
            exact_overlap += len(set(wave_hash[held_idx]).intersection(set(wave_hash[train_idx])))
        real_res68 = [
            r["res68_abs_frac"]
            for r in summary_rows
            if r["topology"] == topology and r["method"] not in {"shuffled_target_extra_trees"}
        ]
        shuffled_res68 = next(r["res68_abs_frac"] for r in summary_rows if r["topology"] == topology and r["method"] == "shuffled_target_extra_trees")
        best_real = min(real_res68)
        leakage_rows.append(
            {
                "topology": topology,
                "split": "leave-one-run-out",
                "train_heldout_run_overlap": 0,
                "features_exclude": "run, evt, A selected flags, A charge columns, target_charge",
                "exact_b_waveform_hash_train_test_overlaps": int(exact_overlap),
                "best_real_res68": float(best_real),
                "shuffled_target_extra_trees_res68": float(shuffled_res68),
                "best_to_shuffled_res68_ratio": float(best_real / shuffled_res68) if shuffled_res68 > 0 else None,
                "looks_too_good": bool(best_real < 0.15 or best_real < 0.50 * shuffled_res68),
            }
        )
    support_rows = (
        topo.groupby(["topology", "support_cell"])
        .agg(
            n=("target_charge", "size"),
            runs=("run", "nunique"),
            median_target_charge=("target_charge", "median"),
            median_b2_charge=("b2_charge", "median"),
        )
        .reset_index()
        .sort_values(["topology", "n"], ascending=[True, False])
    )
    return (
        pd.DataFrame(summary_rows),
        pd.DataFrame(by_run_rows),
        pd.DataFrame(delta_rows),
        pd.DataFrame(leakage_rows),
        pd.DataFrame(fold_rows),
        support_rows,
    )


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    ab_counts: pd.DataFrame,
    p04c_summary: pd.DataFrame,
    topology_counts: pd.DataFrame,
    topology_summary: pd.DataFrame,
    topology_by_run: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    support_counts: pd.DataFrame,
    result: dict,
) -> None:
    p04c_ridge = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    p04c_ml = p04c_summary[p04c_summary["method"] == "b_waveform_extra_trees"].iloc[0]
    compact_summary = topology_summary[
        [
            "topology",
            "method",
            "n",
            "bias_median_frac",
            "bias_ci95",
            "res68_abs_frac",
            "res68_ci95",
            "full_rms_frac",
            "full_rms_ci95",
            "within_10pct",
            "within_25pct",
        ]
    ].copy()
    compact_deltas = deltas[
        [
            "topology",
            "method",
            "baseline",
            "delta_res68_vs_huber",
            "delta_res68_ci95",
            "delta_full_rms_vs_huber",
            "delta_full_rms_ci95",
        ]
    ].copy()
    support_display = support_counts.head(30).copy()
    support_display["support_cell"] = support_display["support_cell"].astype(str).str.replace("|", "\\|", regex=False)
    lines = [
        "# P04t A-stack Topology Lower-Bound Charge Transfer",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.",
        "- **Pre-registered metric:** fractional 68% absolute residual width (`res68`), median fractional bias, full RMS, and within-10% coverage.",
        "- **Split:** leave-one-run-out by run; every topology prediction is trained on other runs.",
        "- **Targets:** `A1_only`, `A3_only`, and `A1A3` selected positive-lobe A-stack charge matched to B-stack events by `(run, EVT)`.",
        "",
        "## Abstract",
        "",
        result["abstract"],
        "",
        "## Raw Reproduction",
        "",
        f"B-stack S00 selected-pulse count reproduced exactly: `{int(b_counts['selected_pulses'].sum()):,}`.",
        "",
        a_counts[["sample", "events_with_selected", "selected_pulses", "A1", "A3"]].to_markdown(index=False),
        "",
        f"P04c broad target reproduction: `{int(p04c_ridge['n'])}` rows, ridge res68 `{p04c_ridge['res68_abs_frac']:.6f}`, "
        f"waveform ExtraTrees res68 `{p04c_ml['res68_abs_frac']:.6f}`.",
        "",
        "## Topology Support",
        "",
        topology_counts.to_markdown(index=False),
        "",
        "Support cells fixed the B-side selected downstream mask, B2 amplitude band, B2 peak atom, and A topology. The largest cells are:",
        "",
        support_display.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "For event `i`, topology `g`, and method `m`, the fitted quantity is `z_i = log(max(Q^A_i,1))`; predictions are back-transformed as `Qhat_i = exp(zhat_i)`. The fractional residual is",
        "",
        "`r_i(m) = (Qhat_i(m) - Q^A_i) / max(Q^A_i, 1)`.",
        "",
        "The headline width is `res68_m = quantile_0.68(|r_i(m)|)`. Full RMS is `sqrt(mean(r_i(m)^2))`, and coverage is `mean(|r_i(m)| < 0.10)`. Confidence intervals resample complete run blocks with replacement inside each topology; delta intervals resample the same run blocks and subtract the Huber baseline statistic in each bootstrap draw.",
        "",
        "Traditional comparators are a topology median, log-charge ridge over B-stack charge/support summaries, and robust log-charge Huber regression. The ML/NN comparators are gradient-boosted trees, ExtraTrees, an MLP, a 1D-CNN over B-stack waveforms, and a new hybrid support-gated CNN that gates waveform features with B-stack support summaries. A shuffled-target ExtraTrees sentinel tests whether run-split leakage or support echo can explain the apparent lower bound.",
        "",
        "## Held-Out Benchmark",
        "",
        compact_summary.to_markdown(index=False),
        "",
        "## Deltas Versus Strong Traditional Baseline",
        "",
        compact_deltas.to_markdown(index=False),
        "",
        "## Per-Run Stress Table",
        "",
        topology_by_run[["topology", "run", "method", "n", "bias_median_frac", "res68_abs_frac", "full_rms_frac", "within_10pct"]].to_markdown(index=False),
        "",
        "## Leakage Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "The feature matrices exclude run id, event id, all A selected flags, all A charge columns, and the target. Each exact B-waveform hash is checked for train/test overlap across the leave-one-run-out folds.",
        "",
        "## Systematics And Caveats",
        "",
        "- This is an A/B external charge-transfer lower bound, not an absolute energy calibration. The target is selected A-stack positive-lobe charge, so detector acceptance and A-stack selection remain part of the estimand.",
        "- The run-block bootstrap captures run-to-run variation but not unobserved future beam conditions outside the sampled support cells.",
        "- Huber and ridge models are intentionally limited to transparent B-charge/support summaries; tree and NN models can exploit waveform morphology, so a win is a predictive lower-bound statement rather than a causal energy model.",
        "- The MLP is included as a required comparator but is numerically unstable on sparse topology folds; its full-RMS failures are reported rather than hidden. CNN log-charge predictions are clipped to train-fold quantile bounds before back-transforming to avoid non-finite physical charges.",
        "- Sparse support cells are reported but not dropped, because dropping them would make the lower bound look artificially optimistic.",
        "",
        "## Verdict",
        "",
        result["finding"],
        "",
        f"Winner: `{result['winner']}` by the predefined pooled selection score (`{result['winner_selection']['score_definition']}`).",
        "",
        "## Next Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `p04c_reproduction_summary.csv`, `ab_topology_counts_by_run.csv`, "
        "`target_topology_counts.csv`, `support_cell_counts.csv`, `topology_summary.csv`, `method_deltas_vs_huber.csv`, "
        "`topology_by_run.csv`, `topology_predictions.csv`, `torch_fold_audit.csv`, and `leakage_checks.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04t_1781062449_642_488b2d5f_astack_topology_lower_bound_charge_transfer.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p04c = load_p04c_module(Path(config["p04c_script"]))

    print("1/6 reproducing raw ROOT B-stack and A-stack gates ...", flush=True)
    b_counts = p04c.count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "b_s00_counts_by_run.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    if got_b != expected_b:
        raise RuntimeError(f"B-stack selected-pulse reproduction failed: {got_b} != {expected_b}")

    a_counts = p04c.count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A-stack event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A-stack pulse gate failed for {row['sample']}")

    print("2/6 extracting P04c event-matched rows from raw ROOT ...", flush=True)
    frame, wave, ab_counts = p04c.extract_ab_rows(config)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)
    if len(frame) != int(config["expected_p04c_rows"]):
        raise RuntimeError(f"P04c row reproduction failed: {len(frame)} != {config['expected_p04c_rows']}")

    print("3/6 reproducing P04c broad charge-transfer number ...", flush=True)
    p04c_summary, p04c_by_run, p04c_by_amp, p04c_leakage = p04c.fit_leave_one_run(config, frame.copy(), wave)
    p04c_summary.to_csv(out_dir / "p04c_reproduction_summary.csv", index=False)
    p04c_by_run.to_csv(out_dir / "p04c_reproduction_by_run.csv", index=False)
    p04c_by_amp.to_csv(out_dir / "p04c_reproduction_by_b2_amp.csv", index=False)
    p04c_ridge = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    expected_res68 = float(config["expected_p04c_charge_transfer_ridge_res68"])
    tolerance = float(config["expected_p04c_tolerance_res68"])
    if abs(float(p04c_ridge["res68_abs_frac"]) - expected_res68) > tolerance:
        raise RuntimeError(f"P04c ridge res68 reproduction failed: {p04c_ridge['res68_abs_frac']} vs {expected_res68}")

    print("4/6 building A-topology targets ...", flush=True)
    topo, topo_wave = build_topology_frame(frame, wave)
    topology_counts = (
        topo.groupby("topology")
        .agg(
            n=("target_charge", "size"),
            runs=("run", "nunique"),
            median_target_charge=("target_charge", "median"),
            median_b2_charge=("b2_charge", "median"),
            a_mult=("a_mult", "median"),
        )
        .reset_index()
    )
    topology_counts.to_csv(out_dir / "target_topology_counts.csv", index=False)

    print(f"5/6 fitting topology-specific leave-one-run-out models on {len(topo)} target rows ...", flush=True)
    topology_summary, topology_by_run, deltas, leakage, torch_audit, support_counts = model_topologies(config, topo, topo_wave)
    topology_summary.to_csv(out_dir / "topology_summary.csv", index=False)
    topology_by_run.to_csv(out_dir / "topology_by_run.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas_vs_huber.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    torch_audit.to_csv(out_dir / "torch_fold_audit.csv", index=False)
    support_counts.to_csv(out_dir / "support_cell_counts.csv", index=False)

    pred_cols = [
        "run",
        "evt",
        "topology",
        "target_charge",
        "a_mult",
        "b_mult",
        "b2_amp",
        "b2_charge",
        "b_downstream_charge",
        "support_cell",
        "pred_topology_median",
        "pred_ridge_log_charge",
        "pred_huber_log_charge",
        "pred_gradient_boosted_trees",
        "pred_extra_trees",
        "pred_mlp",
        "pred_cnn1d_waveform",
        "pred_hybrid_support_gate_cnn",
        "pred_shuffled_target_extra_trees",
    ]
    topo[pred_cols].to_csv(out_dir / "topology_predictions.csv", index=False)

    print("6/6 writing report, hashes, and manifest ...", flush=True)
    real_summary = topology_summary[~topology_summary["method"].eq("shuffled_target_extra_trees")].copy()
    best_real = (
        real_summary
        .sort_values(["topology", "res68_abs_frac"])
        .groupby("topology")
        .first()
        .reset_index()
    )
    method_ranking = (
        real_summary.assign(weighted_res68=lambda d: d["n"] * d["res68_abs_frac"], weighted_rms=lambda d: d["n"] * d["full_rms_frac"])
        .groupby("method")
        .agg(
            n=("n", "sum"),
            weighted_res68_sum=("weighted_res68", "sum"),
            weighted_rms_sum=("weighted_rms", "sum"),
            median_within_10pct=("within_10pct", "median"),
            topologies=("topology", "nunique"),
        )
        .reset_index()
    )
    method_ranking["weighted_res68"] = method_ranking["weighted_res68_sum"] / method_ranking["n"]
    method_ranking["weighted_full_rms"] = method_ranking["weighted_rms_sum"] / method_ranking["n"]
    method_ranking = method_ranking.sort_values(["weighted_res68", "weighted_full_rms", "method"]).drop(columns=["weighted_res68_sum", "weighted_rms_sum"])
    method_ranking.to_csv(out_dir / "method_ranking.csv", index=False)
    winner = str(method_ranking.iloc[0]["method"])

    huber_rows = topology_summary[topology_summary["method"] == "huber_log_charge"].set_index("topology")
    gbt_rows = topology_summary[topology_summary["method"] == "gradient_boosted_trees"].set_index("topology")
    shuffle_rows = topology_summary[topology_summary["method"] == "shuffled_target_extra_trees"].set_index("topology")
    finding_parts = []
    for _, row in best_real.iterrows():
        topology = row["topology"]
        huber = huber_rows.loc[topology]
        gbt = gbt_rows.loc[topology]
        shuffle = shuffle_rows.loc[topology]
        finding_parts.append(
            f"{topology}: best real `{row['method']}` res68 {row['res68_abs_frac']:.4f}; "
            f"Huber {huber['res68_abs_frac']:.4f} [{huber['res68_ci95'][0]:.4f}, {huber['res68_ci95'][1]:.4f}], "
            f"GBT {gbt['res68_abs_frac']:.4f}, shuffled {shuffle['res68_abs_frac']:.4f}"
        )
    broad = float(p04c_ridge["res68_abs_frac"])
    best_topology_res68 = float(best_real["res68_abs_frac"].min())
    if best_topology_res68 < 0.80 * broad:
        interpretation = "Topology mixing contributes to the broad P04c transfer, but the remaining widths are still far from a useful duplicate-readout-like closure."
    else:
        interpretation = "Separating A topology does not materially narrow the broad P04c transfer, so the null is better explained as intrinsic A/B decorrelation under the current B2-source selection."
    finding = interpretation + " " + " ".join(finding_parts)

    hypothesis = (
        "If the A/B transfer floor is dominated by support topology rather than a missing waveform architecture, then future "
        "models that condition on B support cells should not beat the best P04t topology-specific lower bound unless they add "
        "independent A-side or calibrated energy information. A falsification test is to repeat this benchmark with an explicit "
        "A-side nuisance proxy held out by run and require a simultaneous res68 and full-RMS gain without shuffled-target improvement."
    )
    abstract = (
        f"P04t reproduces the raw-ROOT B-stack S00 count ({got_b:,}), the A-stack analysis gates, and the P04c event-matched "
        f"row count ({len(frame):,}) before fitting any model. Across A1-only, A3-only, and A1A3 topologies, the pooled winner is "
        f"`{winner}` with weighted res68 {float(method_ranking.iloc[0]['weighted_res68']):.4f}. The topology-specific lower bounds "
        "remain broad compared with duplicate-readout closure, so the result is a support-limited external-transfer bound rather "
        "than an adoptable energy/PID correction."
    )

    result = {
        "study": "P04t",
        "title": config["title"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "winner": winner,
        "winner_selection": {
            "score_definition": "minimum topology-size-weighted res68 over non-shuffled methods; weighted full RMS breaks ties",
            "ranking": json.loads(method_ranking.to_json(orient="records")),
        },
        "abstract": abstract,
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "astack_analysis_counts": json.loads(a_counts.to_json(orient="records")),
            "p04c_expected_rows": int(config["expected_p04c_rows"]),
            "p04c_reproduced_rows": int(len(frame)),
            "p04c_expected_charge_transfer_ridge_res68": expected_res68,
            "p04c_reproduced_charge_transfer_ridge_res68": float(p04c_ridge["res68_abs_frac"]),
            "p04c_reproduction_pass": True,
        },
        "row_definition": {
            "match_key": "(run, EVT)",
            "source_gate": "B2 amplitude > 1000 ADC",
            "topologies": {
                "A1_only": "A1 amplitude > 1000 ADC and A3 <= 1000 ADC",
                "A3_only": "A3 amplitude > 1000 ADC and A1 <= 1000 ADC",
                "A1A3": "A1 and A3 both amplitude > 1000 ADC",
            },
            "target": "selected A-topology positive-lobe charge",
            "features": "B-stack even-channel waveforms and charge summaries only",
        },
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "methods": {
            "traditional": ["topology_median", "ridge_log_charge", "huber_log_charge"],
            "ml_nn": ["gradient_boosted_trees", "extra_trees", "mlp", "cnn1d_waveform", "hybrid_support_gate_cnn"],
            "sentinel": ["shuffled_target_extra_trees"],
            "new_architecture": "hybrid_support_gate_cnn",
        },
        "p04c_reproduction_summary": json.loads(p04c_summary.to_json(orient="records")),
        "topology_counts": json.loads(topology_counts.to_json(orient="records")),
        "support_cell_counts_head": json.loads(support_counts.head(50).to_json(orient="records")),
        "topology_summary": json.loads(topology_summary.to_json(orient="records")),
        "method_deltas_vs_huber": json.loads(deltas.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": finding,
        "hypothesis": hypothesis,
        "next_tickets": [
            {
                "title": "P04u: A-side nuisance-proxy falsification of topology charge-transfer floor",
                "question": "Does adding run-heldout A-side nuisance information reduce the P04t A/B lower-bound width without matching shuffled-target sentinels?",
                "expected_information_gain": "Separates irreducible A/B decorrelation from missing nuisance conditioning by rerunning the P04t raw-ROOT reproduction and topology benchmark with A-side proxy features gated out of the target definition.",
            }
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, ab_counts, p04c_summary, topology_counts, topology_summary, topology_by_run, deltas, leakage, support_counts, result)

    input_runs = sorted(set(p04c.configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    manifest = {
        "study": "P04t",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/p04t_1781062449_642_488b2d5f_astack_topology_lower_bound_charge_transfer.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": "scripts/p04t_1781062449_642_488b2d5f_astack_topology_lower_bound_charge_transfer.py",
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
            "p04c_script": str(config["p04c_script"]),
            "p04c_script_sha256": sha256_file(Path(config["p04c_script"])),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
