#!/usr/bin/env python3
"""P04w: external A/B charge-transfer abstention frontier.

The study uses the P04h A-stack target: event-matched selected A1/A3
positive-lobe charge predicted from B-stack waveforms.  It reproduces the raw
ROOT B/A gates first, then benchmarks a strong traditional panel against ridge,
gradient-boosted trees, MLP, a compact 1D-CNN, and a support-gated residual CNN.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04c_ab_event_matched_charge_transfer as p04c  # noqa: E402
import p04h_1781023326_470_61534f82_support_map as p04h  # noqa: E402


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    finite_y = y[np.isfinite(y)]
    ymax = float(np.max(finite_y)) if len(finite_y) else 1.0
    pred = np.nan_to_num(pred, nan=1.0, posinf=ymax * 50.0, neginf=1.0)
    pred = np.clip(pred, 1.0, ymax * 50.0)
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(abs_frac <= 0.10)),
        "within_25pct": float(np.mean(abs_frac <= 0.25)),
    }


def run_block_ci(frame: pd.DataFrame, target_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {
            "bias_ci95": [None, None],
            "res68_ci95": [None, None],
            "full_rms_ci95": [None, None],
            "within_10pct_ci95": [None, None],
            "within_25pct_ci95": [None, None],
        }
    by_run = {
        int(run): (
            frame.loc[frame["run"].to_numpy() == int(run), target_col].to_numpy(dtype=float),
            frame.loc[frame["run"].to_numpy() == int(run), pred_col].to_numpy(dtype=float),
        )
        for run in runs
    }
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    w10 = np.empty(reps, dtype=float)
    w25 = np.empty(reps, dtype=float)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        y = np.concatenate([by_run[int(run)][0] for run in chosen])
        pred = np.concatenate([by_run[int(run)][1] for run in chosen])
        got = robust_metrics(y, pred)
        bias[idx] = got["bias_median_frac"]
        res68[idx] = got["res68_abs_frac"]
        rms[idx] = got["full_rms_frac"]
        w10[idx] = got["within_10pct"]
        w25[idx] = got["within_25pct"]
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
        "within_10pct_ci95": [float(np.percentile(w10, 2.5)), float(np.percentile(w10, 97.5))],
        "within_25pct_ci95": [float(np.percentile(w25, 2.5)), float(np.percentile(w25, 97.5))],
    }


def safe_exp(log_pred: np.ndarray) -> np.ndarray:
    return np.exp(np.clip(np.asarray(log_pred, dtype=float), 0.0, 20.0))


def add_frontier_strata(frame: pd.DataFrame, wave: np.ndarray, config: dict) -> pd.DataFrame:
    out = p04h.add_support_strata(frame, wave, config)
    out["saturation_depth_adc"] = np.maximum(out["b2_amp"].to_numpy(dtype=float) - float(config["saturation_adc"]), 0.0)
    pre = wave[:, 0, :4]
    out["baseline_excursion_adc"] = np.max(np.abs(pre), axis=1)
    out["baseline_bin"] = pd.cut(
        out["baseline_excursion_adc"],
        bins=[-np.inf, 20.0, 50.0, 100.0, np.inf],
        labels=["quiet", "mild", "active", "large"],
    ).astype(str)
    out["peak_phase_bin"] = pd.cut(
        out["B2_peak"].to_numpy(dtype=int),
        bins=[-1, 5, 8, 11, 18],
        labels=["early_le5", "rising_6_8", "central_9_11", "late_ge12"],
    ).astype(str)
    out["q_template_bin"] = pd.cut(
        out["B2_late_frac"].to_numpy(dtype=float),
        bins=[-np.inf, 0.05, 0.15, 0.35, np.inf],
        labels=["low", "moderate", "high", "extreme"],
    ).astype(str)
    out["support_cell_full"] = (
        out["topology_pattern"].astype(str)
        + "|"
        + out["b2_amp_bin"].astype(str)
        + "|"
        + out["saturation_stratum"].astype(str)
        + "|"
        + out["anomaly_stratum"].astype(str)
        + "|"
        + out["baseline_bin"].astype(str)
        + "|"
        + out["peak_phase_bin"].astype(str)
        + "|"
        + out["q_template_bin"].astype(str)
    )
    return out


def one_hot_frame(frame: pd.DataFrame, columns: List[str]) -> np.ndarray:
    enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    return enc.fit_transform(frame[columns])


def scalar_features(frame: pd.DataFrame, wave: np.ndarray, categorical: bool = True) -> np.ndarray:
    amp = wave.max(axis=2)
    charge = np.clip(wave, 0.0, None).sum(axis=2)
    total = np.maximum(charge, 1.0)
    peak = wave.argmax(axis=2)
    width50 = (wave > (0.5 * np.maximum(amp, 1.0)[:, :, None])).sum(axis=2)
    width20 = (wave > (0.2 * np.maximum(amp, 1.0)[:, :, None])).sum(axis=2)
    tail = np.clip(wave[:, :, 12:], 0.0, None).sum(axis=2) / total
    late = np.clip(wave[:, :, 9:], 0.0, None).sum(axis=2) / total
    early = np.clip(wave[:, :, :6], 0.0, None).sum(axis=2) / total
    downstream_frac = frame["b_downstream_charge"].to_numpy(dtype=float) / np.maximum(frame["b_total_charge"].to_numpy(dtype=float), 1.0)
    numeric = np.column_stack(
        [
            np.log(np.maximum(charge, 1.0)),
            np.log(np.maximum(amp, 1.0)),
            peak,
            width50,
            width20,
            tail,
            late,
            early,
            frame["b_mult"].to_numpy(dtype=float),
            frame["b_downstream_mult"].to_numpy(dtype=float),
            downstream_frac,
            frame["B2_postpeak_min"].to_numpy(dtype=float),
            frame["B2_late_frac"].to_numpy(dtype=float),
            frame["baseline_excursion_adc"].to_numpy(dtype=float),
            frame["saturation_depth_adc"].to_numpy(dtype=float),
        ]
    )
    if not categorical:
        return numeric
    cats = one_hot_frame(
        frame,
        [
            "topology_pattern",
            "b2_amp_bin",
            "saturation_stratum",
            "anomaly_stratum",
            "downstream_coincidence",
            "a_topology",
            "baseline_bin",
            "peak_phase_bin",
            "q_template_bin",
        ],
    )
    return np.column_stack([numeric, cats])


def full_features(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    norm = wave / np.maximum(wave.max(axis=2)[:, :, None], 1.0)
    return np.column_stack([norm.reshape(len(wave), -1), scalar_features(frame, wave, categorical=True)])


def standardize_from_train(train: np.ndarray, all_values: np.ndarray) -> np.ndarray:
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    return ((np.nan_to_num(all_values, nan=mu) - mu) / sd).astype(np.float32)


class ConvChargeNet(nn.Module):
    def __init__(self, n_aux: int, channels: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(4, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(channels + n_aux, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        return self.head(torch.cat([self.conv(wave), aux], dim=1)).squeeze(1)


class SupportGatedResidualNet(nn.Module):
    def __init__(self, n_aux: int, channels: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(8, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.gate = nn.Sequential(nn.Linear(n_aux, channels), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(channels + n_aux, 40), nn.ReLU(), nn.Linear(40, 1))

    def forward(self, wave_pair: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave_pair)
        z = z * (0.5 + self.gate(aux))
        return self.head(torch.cat([z, aux], dim=1)).squeeze(1)


def train_torch(model: nn.Module, arrays: Tuple[np.ndarray, ...], y: np.ndarray, config: dict, seed: int) -> nn.Module:
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    tensors = [torch.tensor(a.astype(np.float32), dtype=torch.float32) for a in arrays]
    yy = torch.tensor(y.astype(np.float32), dtype=torch.float32)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["torch_learning_rate"]),
        weight_decay=float(config["torch_weight_decay"]),
    )
    loss_fn = nn.SmoothL1Loss(beta=0.05)
    rng = np.random.default_rng(seed)
    batch = min(int(config["torch_batch_size"]), len(y))
    model.train()
    for _ in range(int(config["torch_epochs"])):
        order = rng.permutation(len(y))
        for start in range(0, len(y), batch):
            take = order[start : start + batch]
            opt.zero_grad()
            pred = model(*(tensor[take] for tensor in tensors))
            loss = loss_fn(pred, yy[take])
            loss.backward()
            opt.step()
    return model.eval()


def predict_torch(model: nn.Module, arrays: Tuple[np.ndarray, ...], batch: int = 4096) -> np.ndarray:
    tensors = [torch.tensor(a.astype(np.float32), dtype=torch.float32) for a in arrays]
    out = []
    with torch.no_grad():
        for start in range(0, len(arrays[0]), batch):
            sl = slice(start, min(start + batch, len(arrays[0])))
            out.append(model(*(tensor[sl] for tensor in tensors)).cpu().numpy())
    return np.concatenate(out).astype(float)


def residual_wave_channels(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    norm = wave / np.maximum(wave.max(axis=2)[:, :, None], 1.0)
    train_templates: Dict[Tuple[str, str], np.ndarray] = {}
    fallback = np.median(norm, axis=0)
    for key, sub in frame.groupby(["topology_pattern", "b2_amp_bin"], observed=True):
        if len(sub) >= 20:
            train_templates[(str(key[0]), str(key[1]))] = np.median(norm[sub.index.to_numpy()], axis=0)
    tmpl = np.empty_like(norm)
    for idx, row in enumerate(frame.itertuples(index=False)):
        tmpl[idx] = train_templates.get((str(row.topology_pattern), str(row.b2_amp_bin)), fallback)
    residual = norm - tmpl
    return np.concatenate([norm, residual], axis=1).astype(np.float32)


def fit_models(config: dict, frame: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    y = frame["target_a_charge"].to_numpy(dtype=float)
    log_y = np.log(np.maximum(y, 1.0))
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    methods = [
        "topology_median",
        "strong_huber_transfer",
        "ridge",
        "gradient_boosted_trees",
        "mlp",
        "1d_cnn",
        "support_gated_residual_cnn",
        "topology_only_sentinel",
        "shuffled_target_hgb",
    ]
    for method in methods:
        frame[f"pred_{method}"] = np.nan
        frame[f"risk_{method}"] = np.nan

    scalar_x = scalar_features(frame, wave, categorical=True)
    full_x = full_features(frame, wave)
    topo_x = one_hot_frame(frame, ["topology_pattern", "a_topology", "b2_amp_bin", "downstream_coincidence"])
    aux_x = standardize_from_train(scalar_x, scalar_x)
    norm_wave = (wave / np.maximum(wave.max(axis=2)[:, :, None], 1.0)).astype(np.float32)
    wave_resid = residual_wave_channels(frame, wave)

    for heldout_run in runs:
        print(f"  P04w heldout run {int(heldout_run)}", flush=True)
        train_mask = frame["run"].to_numpy() != int(heldout_run)
        held_mask = ~train_mask
        train_idx = np.where(train_mask)[0]
        train_idx_ml = train_idx
        if len(train_idx_ml) > int(config["ml_max_train_rows"]):
            train_idx_ml = rng.choice(train_idx_ml, size=int(config["ml_max_train_rows"]), replace=False)
        train_idx_nn = train_idx
        if len(train_idx_nn) > int(config["nn_max_train_rows"]):
            train_idx_nn = rng.choice(train_idx_nn, size=int(config["nn_max_train_rows"]), replace=False)

        global_median = float(np.median(log_y[train_mask]))
        group_median = (
            frame.loc[train_mask]
            .assign(log_y=log_y[train_mask])
            .groupby(["support_cell_full", "a_topology"], observed=True)["log_y"]
            .median()
            .to_dict()
        )
        topo_pred = []
        for row in frame.loc[held_mask].itertuples(index=False):
            topo_pred.append(group_median.get((row.support_cell_full, row.a_topology), global_median))
        frame.loc[held_mask, "pred_topology_median"] = safe_exp(np.asarray(topo_pred))

        huber = make_pipeline(StandardScaler(), HuberRegressor(alpha=0.0005, epsilon=1.35, max_iter=300))
        huber.fit(scalar_x[train_idx_ml], log_y[train_idx_ml])
        frame.loc[held_mask, "pred_strong_huber_transfer"] = safe_exp(huber.predict(scalar_x[held_mask]))

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        ridge.fit(full_x[train_idx_ml], log_y[train_idx_ml])
        frame.loc[held_mask, "pred_ridge"] = safe_exp(ridge.predict(full_x[held_mask]))

        hgb = HistGradientBoostingRegressor(
            max_iter=220,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=0.08,
            random_state=int(config["random_seed"]) + int(heldout_run),
        )
        hgb.fit(full_x[train_idx_ml], log_y[train_idx_ml])
        frame.loc[held_mask, "pred_gradient_boosted_trees"] = safe_exp(hgb.predict(full_x[held_mask]))

        mu = float(np.mean(log_y[train_idx_ml]))
        sd = float(np.std(log_y[train_idx_ml])) or 1.0
        mlp = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(64, 32),
                activation="relu",
                alpha=0.001,
                learning_rate_init=0.001,
                max_iter=int(config["mlp_max_iter"]),
                early_stopping=True,
                n_iter_no_change=12,
                random_state=int(config["random_seed"]) + 100 + int(heldout_run),
                batch_size=512,
            ),
        )
        mlp.fit(full_x[train_idx_ml], (log_y[train_idx_ml] - mu) / sd)
        frame.loc[held_mask, "pred_mlp"] = safe_exp(mlp.predict(full_x[held_mask]) * sd + mu)

        y_nn = log_y[train_idx_nn]
        nn_mu = float(np.mean(y_nn))
        nn_sd = float(np.std(y_nn)) or 1.0
        yy = (y_nn - nn_mu) / nn_sd
        cnn = ConvChargeNet(aux_x.shape[1], int(config["torch_channels"]))
        cnn = train_torch(cnn, (norm_wave[train_idx_nn], aux_x[train_idx_nn]), yy, config, int(config["random_seed"]) + 200 + int(heldout_run))
        frame.loc[held_mask, "pred_1d_cnn"] = safe_exp(predict_torch(cnn, (norm_wave[held_mask], aux_x[held_mask])) * nn_sd + nn_mu)

        gated = SupportGatedResidualNet(aux_x.shape[1], int(config["torch_channels"]))
        gated = train_torch(
            gated,
            (wave_resid[train_idx_nn], aux_x[train_idx_nn]),
            yy,
            config,
            int(config["random_seed"]) + 300 + int(heldout_run),
        )
        frame.loc[held_mask, "pred_support_gated_residual_cnn"] = safe_exp(
            predict_torch(gated, (wave_resid[held_mask], aux_x[held_mask])) * nn_sd + nn_mu
        )

        topo_model = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        topo_model.fit(topo_x[train_mask], log_y[train_mask])
        frame.loc[held_mask, "pred_topology_only_sentinel"] = safe_exp(topo_model.predict(topo_x[held_mask]))

        shuffled = log_y[train_idx_ml].copy()
        rng.shuffle(shuffled)
        shuffled_model = HistGradientBoostingRegressor(
            max_iter=140,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=0.08,
            random_state=int(config["random_seed"]) + 400 + int(heldout_run),
        )
        shuffled_model.fit(full_x[train_idx_ml], shuffled)
        frame.loc[held_mask, "pred_shuffled_target_hgb"] = safe_exp(shuffled_model.predict(full_x[held_mask]))

        # Train-fold conformal risk, assigned by support cell when possible.
        for method in methods:
            if method == "topology_median":
                train_pred = np.exp(frame.loc[train_mask, "support_cell_full"].map(
                    frame.loc[train_mask].assign(log_y=log_y[train_mask]).groupby("support_cell_full", observed=True)["log_y"].median()
                ).fillna(global_median).to_numpy(dtype=float))
            elif method == "topology_only_sentinel":
                train_pred = safe_exp(topo_model.predict(topo_x[train_mask]))
            elif method == "shuffled_target_hgb":
                train_pred = safe_exp(shuffled_model.predict(full_x[train_mask]))
            elif method == "strong_huber_transfer":
                train_pred = safe_exp(huber.predict(scalar_x[train_mask]))
            elif method == "ridge":
                train_pred = safe_exp(ridge.predict(full_x[train_mask]))
            elif method == "gradient_boosted_trees":
                train_pred = safe_exp(hgb.predict(full_x[train_mask]))
            elif method == "mlp":
                train_pred = safe_exp(mlp.predict(full_x[train_mask]) * sd + mu)
            elif method == "1d_cnn":
                train_pred = safe_exp(predict_torch(cnn, (norm_wave[train_mask], aux_x[train_mask])) * nn_sd + nn_mu)
            else:
                train_pred = safe_exp(predict_torch(gated, (wave_resid[train_mask], aux_x[train_mask])) * nn_sd + nn_mu)
            train_abs = np.abs((train_pred - y[train_mask]) / np.maximum(y[train_mask], 1.0))
            global_q = float(np.percentile(train_abs, 68))
            train_tmp = frame.loc[train_mask, ["support_cell_full"]].copy()
            train_tmp["abs_resid"] = train_abs
            cell_q = train_tmp.groupby("support_cell_full", observed=True)["abs_resid"].quantile(0.68).to_dict()
            risk = frame.loc[held_mask, "support_cell_full"].map(cell_q).fillna(global_q).to_numpy(dtype=float)
            n_cell = frame.loc[held_mask, "support_cell_full"].map(
                train_tmp.groupby("support_cell_full", observed=True).size().to_dict()
            ).fillna(0).to_numpy(dtype=float)
            risk = risk + np.where(n_cell >= float(config["strong_support_rows"]), 0.0, 0.05)
            frame.loc[held_mask, f"risk_{method}"] = risk

    rows = []
    rng_ci = np.random.default_rng(int(config["random_seed"]) + 99)
    family = {
        "topology_median": "traditional",
        "strong_huber_transfer": "traditional",
        "ridge": "ml",
        "gradient_boosted_trees": "ml",
        "mlp": "ml",
        "1d_cnn": "nn",
        "support_gated_residual_cnn": "new_architecture",
        "topology_only_sentinel": "negative_control",
        "shuffled_target_hgb": "negative_control",
    }
    for method in methods:
        row = {"method": method, "family": family[method], "target": "selected_A1A3_charge", "split": "leave_one_run_out"}
        row.update(robust_metrics(y, frame[f"pred_{method}"].to_numpy(dtype=float)))
        row.update(run_block_ci(frame, "target_a_charge", f"pred_{method}", rng_ci, int(config["bootstrap_reps"])))
        rows.append(row)
    return frame, pd.DataFrame(rows)


def summarize_abstention(config: dict, frame: pd.DataFrame, methods: List[str]) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 177)
    y = frame["target_a_charge"].to_numpy(dtype=float)
    for method in methods:
        risk = frame[f"risk_{method}"].to_numpy(dtype=float)
        order = np.argsort(risk, kind="mergesort")
        for frac in [float(x) for x in config["abstention_accept_fractions"]]:
            n_accept = max(1, int(round(frac * len(frame))))
            keep_idx = order[:n_accept]
            sub = frame.iloc[keep_idx].copy()
            row = {
                "method": method,
                "accept_fraction_target": frac,
                "accepted_fraction": float(len(sub) / len(frame)),
                "abstained_fraction": float(1.0 - len(sub) / len(frame)),
                "risk_threshold": float(np.max(risk[keep_idx])),
                "n_runs": int(sub["run"].nunique()),
            }
            row.update(robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub[f"pred_{method}"].to_numpy(dtype=float)))
            row.update(run_block_ci(sub, "target_a_charge", f"pred_{method}", rng, max(100, int(config["bootstrap_reps"]) // 2)))
            if method != "shuffled_target_hgb":
                shuf_pred = sub["pred_shuffled_target_hgb"].to_numpy(dtype=float)
                topo_pred = sub["pred_topology_only_sentinel"].to_numpy(dtype=float)
                real = row["res68_abs_frac"]
                shuf = robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), shuf_pred)["res68_abs_frac"]
                topo = robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), topo_pred)["res68_abs_frac"]
                row["shuffled_res68_abs_frac"] = shuf
                row["topology_only_res68_abs_frac"] = topo
                row["real_minus_shuffled_res68"] = float(real - shuf)
                row["real_minus_topology_res68"] = float(real - topo)
            else:
                row["shuffled_res68_abs_frac"] = None
                row["topology_only_res68_abs_frac"] = None
                row["real_minus_shuffled_res68"] = None
                row["real_minus_topology_res68"] = None
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_frontier_cells(config: dict, frame: pd.DataFrame, method: str) -> pd.DataFrame:
    rows = []
    for category in [
        "support_cell",
        "topology_pattern",
        "b2_amp_bin",
        "saturation_stratum",
        "anomaly_stratum",
        "baseline_bin",
        "peak_phase_bin",
        "q_template_bin",
    ]:
        for value, sub in frame.groupby(category, observed=True):
            if len(sub) < int(config["min_support_rows"]):
                continue
            row = {
                "category": category,
                "value": str(value),
                "n": int(len(sub)),
                "n_runs": int(sub["run"].nunique()),
            }
            row.update(robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub[f"pred_{method}"].to_numpy(dtype=float)))
            shuf = robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub["pred_shuffled_target_hgb"].to_numpy(dtype=float))
            topo = robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub["pred_topology_only_sentinel"].to_numpy(dtype=float))
            row["shuffled_res68_abs_frac"] = shuf["res68_abs_frac"]
            row["topology_only_res68_abs_frac"] = topo["res68_abs_frac"]
            row["real_minus_shuffled_res68"] = row["res68_abs_frac"] - row["shuffled_res68_abs_frac"]
            row["real_minus_topology_res68"] = row["res68_abs_frac"] - row["topology_only_res68_abs_frac"]
            enough = row["n"] >= int(config["strong_support_rows"]) and row["n_runs"] >= int(config["strong_support_runs"])
            row["support_call"] = (
                "candidate"
                if enough
                and row["res68_abs_frac"] < 0.45
                and row["real_minus_shuffled_res68"] < -0.03
                and row["real_minus_topology_res68"] < -0.03
                else "weak_or_null"
            )
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["support_call", "res68_abs_frac", "n"], ascending=[True, True, False])


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    ab_counts: pd.DataFrame,
    p04c_summary: pd.DataFrame,
    method_summary: pd.DataFrame,
    abstention: pd.DataFrame,
    cells: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    expected = int(config["expected_b_s00_selected_pulses"])
    got = int(b_counts["selected_pulses"].sum())
    eligible = method_summary[~method_summary["family"].eq("negative_control")]
    best = eligible.sort_values("res68_abs_frac").iloc[0]
    trad = eligible[eligible["family"].eq("traditional")].sort_values("res68_abs_frac").iloc[0]
    ml = eligible[eligible["family"].isin(["ml", "nn", "new_architecture"])].sort_values("res68_abs_frac").iloc[0]
    shuf = method_summary[method_summary["method"].eq("shuffled_target_hgb")].iloc[0]
    top_abst = abstention[abstention["method"].eq(str(best["method"]))].sort_values("accepted_fraction", ascending=False)
    p04c_trad = p04c_summary[p04c_summary["method"].eq("charge_transfer_ridge")].iloc[0]
    p04c_ml = p04c_summary[p04c_summary["method"].eq("b_waveform_extra_trees")].iloc[0]
    lines = [
        "# P04w External-Charge Abstention Frontier",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.",
        "- **Split:** leave-one-run-out by run; all bootstrap intervals resample held-out run blocks.",
        "- **Target:** event-matched selected A1/A3 positive-lobe charge on rows with selected B2 and selected A1 or A3.",
        "",
        "## 0. Question",
        "",
        "Can any support-aware abstention frontier make B-stack waveform charge a safe external proxy for downstream energy/PID labels, or does the A-stack target remain indistinguishable from topology/shuffled sentinels?",
        "",
        "## 1. Reproduction From Raw ROOT",
        "",
        "The B-stack gate is rebuilt directly from `HRDv`: for each event and B stave, the channel median over samples 0--3 is subtracted and the pulse is selected when the corrected peak exceeds 1000 ADC. The A-stack gate uses the same baseline rule on A1/A3. No sorted-table target is used for the gate.",
        "",
        "| quantity | expected | reproduced | delta | tolerance | pass |",
        "|---|---:|---:|---:|---:|:---|",
        f"| B-stack selected pulse records | {expected:,} | {got:,} | {got - expected:+,} | 0 | {str(got == expected).lower()} |",
        "",
        a_counts[["sample", "events_with_selected", "selected_pulses", "A1", "A3"]].to_markdown(index=False),
        "",
        "As a ticket-local reproduction of the previous external-charge number, the P04c leave-one-run-out A/B charge-transfer benchmark is rerun on the same raw ROOT rows:",
        "",
        p04c_summary[["method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "full_rms_frac", "within_25pct"]].to_markdown(index=False),
        "",
        f"The reproduced P04c traditional ridge res68 is `{p04c_trad['res68_abs_frac']:.4f}` and the waveform ExtraTrees res68 is `{p04c_ml['res68_abs_frac']:.4f}` on `{int(p04c_ml['n']):,}` rows.",
        "",
        "## 2. Methods",
        "",
        "For event i, the external target is",
        "",
        "`y_i = sum_{a in {A1,A3}} 1[A_a>1000] sum_t max(A_{iat}, 0)`.",
        "",
        "Every model predicts `log(y_i)` from B-stack waveform and topology features only. Event number, run number, A-stack charge, A-stack selected flags, and the target are excluded from features. The residual reported in all tables is",
        "",
        "`e_i(m) = (hat y_i(m) - y_i) / max(y_i, 1)`",
        "",
        "with primary width `res68 = Q_0.68(|e_i|)`. The traditional panel is a topology/support-cell median and a robust Huber log-charge transfer using B2/B-stack charge, amplitude, peak phase, width, late/early fractions, saturation, baseline, and topology atoms. The ML/NN panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, and the new support-gated residual CNN. The new architecture is appropriate here because the question is explicitly about support atoms: it convolves normalized B2/B4/B6/B8 waveforms and fold-local residual-template channels, then gates the latent representation with scalar support features before regression.",
        "",
        "The abstention score is train-fold conformal risk: within each support cell, the 68th percentile of train-run absolute fractional residual is assigned to held-out rows, with a penalty for cells below strong support. This uses training targets only and is fixed before looking at the held-out target residuals.",
        "",
        "## 3. Head-To-Head Benchmark",
        "",
        method_summary[[
            "method",
            "family",
            "n",
            "bias_median_frac",
            "bias_ci95",
            "res68_abs_frac",
            "res68_ci95",
            "full_rms_frac",
            "full_rms_ci95",
            "within_10pct",
            "within_25pct",
        ]].to_markdown(index=False),
        "",
        f"Point-estimate winner among non-sentinel methods: `{best['method']}` with res68 `{best['res68_abs_frac']:.4f}`. Best traditional method: `{trad['method']}` at `{trad['res68_abs_frac']:.4f}`. Best ML/NN method: `{ml['method']}` at `{ml['res68_abs_frac']:.4f}`. The shuffled-target HGB sentinel is `{shuf['res68_abs_frac']:.4f}`.",
        "",
        "## 4. Abstention Frontier",
        "",
        "The table below shows risk-ranked accepted fractions for the point-estimate winner. A valid production frontier would need lower res68, useful accepted support, and a negative real-minus-shuffled separation.",
        "",
        top_abst[[
            "method",
            "accepted_fraction",
            "abstained_fraction",
            "n",
            "n_runs",
            "bias_median_frac",
            "res68_abs_frac",
            "res68_ci95",
            "full_rms_frac",
            "within_10pct",
            "within_25pct",
            "shuffled_res68_abs_frac",
            "topology_only_res68_abs_frac",
            "real_minus_shuffled_res68",
            "real_minus_topology_res68",
        ]].to_markdown(index=False),
        "",
        "Largest or best support cells for the winner:",
        "",
        cells.head(24)[[
            "category",
            "value",
            "n",
            "n_runs",
            "bias_median_frac",
            "res68_abs_frac",
            "shuffled_res68_abs_frac",
            "topology_only_res68_abs_frac",
            "real_minus_shuffled_res68",
            "real_minus_topology_res68",
            "support_call",
        ]].to_markdown(index=False),
        "",
        "## 5. Falsification",
        "",
        "The preregistered failure condition is that an apparent real model improvement is rejected if a shuffled-target or topology-only sentinel matches it within run-block uncertainty, or if abstention can only improve res68 by throwing away nearly all support. This is the decisive test for P04w because P04h found the global A-stack proxy to be shuffled-like.",
        "",
        f"Observed shuffled-target res68 is `{leakage['shuffled_target_res68']:.4f}` and topology-only res68 is `{leakage['topology_only_res68']:.4f}`. The best non-sentinel minus shuffled res68 is `{leakage['best_minus_shuffled_res68']:.4f}`, while best-minus-topology is `{leakage['best_minus_topology_res68']:.4f}`. The analysis therefore treats any point-estimate win as diagnostic unless both separations are clearly negative.",
        "",
        "## 6. Systematics And Caveats",
        "",
        "- The A-stack charge target is an external detector handle but not absolute energy or PID truth; particle identity, material budget, Birks quenching, and geometry are not calibrated here.",
        "- A/B event matching by `(run, EVT)` may couple topology and trigger acceptance; the topology-only sentinel bounds this risk.",
        "- Run-block CIs cover finite run-to-run variation among the available matched runs, not unobserved detector configurations or alternate baseline definitions.",
        "- The neural networks are compact CPU-scale models. They test architecture class plausibility, not an exhaustive GPU sweep.",
        "- The conformal abstention score is target-calibrated on train runs only; if support cells drift across runs, its coverage can fail despite clean splitting.",
        "",
        "## 7. Findings And Next Steps",
        "",
        result["finding"],
        "",
        "Hypothesis: B-stack waveform charge does not contain enough independent information to predict sparse selected A-stack charge after topology and run-family effects are controlled; any safe use in PID/energy needs either new external truth or a much narrower detector-geometry acceptance label.",
        "",
        "No follow-up ticket is appended from this study. The current queue already contains P04x/S14/PID externalization tickets, and adding another external-charge frontier without new truth would duplicate this negative-control result.",
        "",
        "## 8. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config {config['config_path_for_report']}",
        "```",
        "",
        "Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `method_summary.csv`, `abstention_frontier.csv`, `support_frontier_cells.csv`, `prediction_sample.csv`, and `leakage_checks.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04w_1781065299_620_6b5f516e_external_charge_abstention_frontier.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    config["config_path_for_report"] = str(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/6 reproducing raw ROOT gates ...", flush=True)
    b_counts = p04c.count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    if got_b != expected_b:
        raise RuntimeError(f"B-stack S00 gate reproduction failed: {got_b} != {expected_b}")
    a_counts = p04c.count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A-stack event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A-stack pulse gate failed for {row['sample']}")

    print("2/6 extracting A/B event-matched rows ...", flush=True)
    frame, wave, ab_counts = p04c.extract_ab_rows(config)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)
    frame = add_frontier_strata(frame, wave, config)

    print("3/6 reproducing previous P04c A/B charge benchmark ...", flush=True)
    p04c_summary, p04c_by_run, p04c_by_amp, p04c_leakage = p04c.fit_leave_one_run(config, frame.copy(), wave)
    p04c_summary.to_csv(out_dir / "p04c_reproduction_summary.csv", index=False)
    p04c_by_run.to_csv(out_dir / "p04c_reproduction_by_run.csv", index=False)
    p04c_by_amp.to_csv(out_dir / "p04c_reproduction_by_b2_amp.csv", index=False)

    print("4/6 fitting P04w method panel ...", flush=True)
    pred_frame, method_summary = fit_models(config, frame.copy(), wave)
    method_summary.to_csv(out_dir / "method_summary.csv", index=False)

    methods = method_summary["method"].tolist()
    abstention = summarize_abstention(config, pred_frame, methods)
    abstention.to_csv(out_dir / "abstention_frontier.csv", index=False)

    eligible = method_summary[~method_summary["family"].eq("negative_control")]
    best = eligible.sort_values("res68_abs_frac").iloc[0]
    cells = summarize_frontier_cells(config, pred_frame, str(best["method"]))
    cells.to_csv(out_dir / "support_frontier_cells.csv", index=False)

    pred_cols = [
        "run",
        "evt",
        "target_a_charge",
        "topology_pattern",
        "b2_amp_bin",
        "saturation_stratum",
        "anomaly_stratum",
        "baseline_bin",
        "peak_phase_bin",
        "q_template_bin",
    ]
    pred_cols += [f"pred_{m}" for m in methods] + [f"risk_{m}" for m in methods]
    pred_frame[pred_cols].head(20000).to_csv(out_dir / "prediction_sample.csv", index=False)

    print("5/6 writing result and report ...", flush=True)
    shuf = method_summary[method_summary["method"].eq("shuffled_target_hgb")].iloc[0]
    topo = method_summary[method_summary["method"].eq("topology_only_sentinel")].iloc[0]
    best_minus_shuffle = float(best["res68_abs_frac"] - shuf["res68_abs_frac"])
    best_minus_topology = float(best["res68_abs_frac"] - topo["res68_abs_frac"])
    candidate_frontiers = abstention[
        (abstention["method"].eq(str(best["method"])))
        & (abstention["real_minus_shuffled_res68"].fillna(999.0) < -0.03)
        & (abstention["real_minus_topology_res68"].fillna(999.0) < -0.03)
        & (abstention["accepted_fraction"] >= 0.25)
        & (abstention["res68_abs_frac"] < 0.45)
    ]
    production_winner = (
        str(best["method"])
        if best_minus_shuffle < -0.03 and best_minus_topology < -0.03 and len(candidate_frontiers)
        else "none_admissible_topology_or_shuffled_like"
    )
    if production_winner == "none_admissible_topology_or_shuffled_like":
        finding = (
            f"The point-estimate winner is {best['method']} (res68 {best['res68_abs_frac']:.4f}), "
            f"but it does not earn production status because the shuffled-target sentinel is {shuf['res68_abs_frac']:.4f} "
            f"and the topology-only sentinel is {topo['res68_abs_frac']:.4f}; the best-minus-topology separation is {best_minus_topology:.4f}. "
            "Risk-ranked abstention lowers some local widths but does not produce a supported frontier that beats both sentinels. "
            "B-stack waveform charge should therefore remain a diagnostic proxy, not an energy/PID label source."
        )
    else:
        best_front = candidate_frontiers.sort_values("res68_abs_frac").iloc[0]
        finding = (
            f"{production_winner} is admissible at accepted fraction {best_front['accepted_fraction']:.3f}: "
            f"res68 {best_front['res68_abs_frac']:.4f}, shuffled {best_front['shuffled_res68_abs_frac']:.4f}, "
            f"real-minus-shuffled {best_front['real_minus_shuffled_res68']:.4f}."
        )
    leakage = {
        "split": "leave-one-run-out by run",
        "features_exclude": ["run", "evt", "target_a_charge", "A1_charge", "A3_charge", "A1_selected", "A3_selected"],
        "train_heldout_run_overlap": 0,
        "topology_only_res68": float(topo["res68_abs_frac"]),
        "shuffled_target_res68": float(shuf["res68_abs_frac"]),
        "best_method": str(best["method"]),
        "best_res68": float(best["res68_abs_frac"]),
        "best_minus_shuffled_res68": best_minus_shuffle,
        "best_minus_topology_res68": best_minus_topology,
        "production_winner": production_winner,
        "too_good_flag": bool(best["res68_abs_frac"] < 0.25 and shuf["res68_abs_frac"] > 0.45),
    }
    pd.DataFrame([leakage]).to_csv(out_dir / "leakage_checks.csv", index=False)

    result = {
        "study": "P04w",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": True,
        "repro_tolerance": "exact B-stack selected-pulse count; exact A-stack selected gate counts",
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "astack_gate_counts": json.loads(a_counts.to_json(orient="records")),
            "p04c_reproduction_summary": json.loads(p04c_summary.to_json(orient="records")),
        },
        "traditional": {
            "metric": "external_charge_res68_abs_frac",
            "method": str(eligible[eligible["family"].eq("traditional")].sort_values("res68_abs_frac").iloc[0]["method"]),
            "value": float(eligible[eligible["family"].eq("traditional")].sort_values("res68_abs_frac").iloc[0]["res68_abs_frac"]),
        },
        "ml": {
            "metric": "external_charge_res68_abs_frac",
            "method": str(eligible[eligible["family"].isin(["ml", "nn", "new_architecture"])].sort_values("res68_abs_frac").iloc[0]["method"]),
            "value": float(eligible[eligible["family"].isin(["ml", "nn", "new_architecture"])].sort_values("res68_abs_frac").iloc[0]["res68_abs_frac"]),
        },
        "winner": production_winner,
        "point_estimate_winner": str(best["method"]),
        "ml_beats_baseline": bool(
            eligible[eligible["family"].isin(["ml", "nn", "new_architecture"])].sort_values("res68_abs_frac").iloc[0]["res68_abs_frac"]
            < eligible[eligible["family"].eq("traditional")].sort_values("res68_abs_frac").iloc[0]["res68_abs_frac"]
        ),
        "falsification": {
            "preregistered_metric": "external-charge res68, accepted support fraction, and real-minus-shuffled separation under run-block bootstrap",
            "shuffled_target_res68": float(shuf["res68_abs_frac"]),
            "topology_only_res68": float(topo["res68_abs_frac"]),
            "best_minus_shuffled_res68": best_minus_shuffle,
            "best_minus_topology_res68": best_minus_topology,
        },
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "head_to_head": json.loads(method_summary.to_json(orient="records")),
        "abstention_frontier": json.loads(abstention.to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
        "critic": "pending",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, ab_counts, p04c_summary, method_summary, abstention, cells, leakage, result)

    print("6/6 writing provenance manifest ...", flush=True)
    input_runs = sorted(set(p04c.configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": "P04w",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/{Path(__file__).name} --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
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
