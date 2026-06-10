#!/usr/bin/env python3
"""P03g detector-label permutation stress test for residual timing models."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03g-labelperm")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a

torch.set_num_threads(1)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return json_ready(obj.tolist())
    return obj


def fold_config(config: dict, heldout_run: int, loo_runs: Sequence[int]) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [int(run) for run in loo_runs if int(run) != int(heldout_run)]
    return cfg


def waveform_and_shape(pulses: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    safe_amp = np.maximum(amp, 1.0)
    norm = wf / safe_amp[:, None]
    grad = np.gradient(norm, axis=1)
    rise_50_10 = pulses["t_cfd50_ns"].to_numpy(dtype=np.float32) - pulses["t_cfd10_ns"].to_numpy(dtype=np.float32)
    rise_40_20 = pulses["t_cfd40_ns"].to_numpy(dtype=np.float32) - pulses["t_cfd20_ns"].to_numpy(dtype=np.float32)
    tab = np.column_stack(
        [
            np.log1p(safe_amp),
            1000.0 / safe_amp,
            np.sqrt(1000.0 / safe_amp),
            pulses["peak_sample"].to_numpy(dtype=np.float32),
            pulses["area_adc_samples"].to_numpy(dtype=np.float32) / safe_amp,
            rise_50_10,
            rise_40_20,
            grad.max(axis=1),
            norm[:, :6].sum(axis=1),
            norm[:, 9:].sum(axis=1),
            norm.max(axis=1),
        ]
    ).astype(np.float32)
    names = [
        "log_amp",
        "inv_amp_1000",
        "inv_sqrt_amp_1000",
        "peak_sample",
        "area_over_amp",
        "cfd50_minus_cfd10_ns",
        "cfd40_minus_cfd20_ns",
        "max_norm_slope",
        "early_norm_charge",
        "late_norm_charge",
        "norm_peak_height",
    ]
    return norm.astype(np.float32), tab, names


def one_hot(labels: Sequence[str], levels: Sequence[str]) -> np.ndarray:
    out = np.zeros((len(labels), len(levels)), dtype=np.float32)
    idx = {label: i for i, label in enumerate(levels)}
    for row, label in enumerate(labels):
        if label in idx:
            out[row, idx[label]] = 1.0
    return out


def labels_for_policy(pulses: pd.DataFrame, cfg: dict, policy: str, heldout_run: int, seed: int) -> np.ndarray:
    labels = np.asarray(pulses["stave"].to_numpy(), dtype=object).copy()
    rng = np.random.default_rng(seed + 1009 * int(heldout_run) + 37 * len(policy))
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(cfg["timing"]["train_runs"]))
    held_mask = np.isin(runs, list(cfg["timing"]["heldout_runs"]))
    if policy == "real_stave":
        return labels
    if policy == "train_label_permutation":
        labels[train_mask] = rng.permutation(labels[train_mask])
        return labels
    if policy == "heldout_label_permutation":
        labels[held_mask] = rng.permutation(labels[held_mask])
        return labels
    if policy == "no_stave":
        return np.asarray(["NO_STAVE"] * len(labels), dtype=object)
    raise ValueError(f"unknown label policy {policy}")


def build_features(
    pulses: pd.DataFrame,
    cfg: dict,
    policy: str,
    heldout_run: int,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    seq, tab, tab_names = waveform_and_shape(pulses)
    staves = list(cfg["timing"]["downstream_staves"])
    if policy == "no_stave":
        labels = np.asarray(["NO_STAVE"] * len(pulses), dtype=object)
        label_levels = ["NO_STAVE"]
    else:
        labels = labels_for_policy(pulses, cfg, policy, heldout_run, int(cfg["ml"]["random_seed"]))
        label_levels = staves
    label_tab = one_hot(labels, label_levels)
    label_names = [f"label_{x}" for x in label_levels]
    return seq, np.hstack([tab, label_tab]).astype(np.float32), tab_names + label_names


def finite_mask(seq: np.ndarray, tab: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.isfinite(runs) & np.all(np.isfinite(seq), axis=1) & np.all(np.isfinite(tab), axis=1)


def standardize_by_train(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    scaler = StandardScaler()
    out = X.copy()
    scaler.fit(X[train_idx])
    out[:] = scaler.transform(X)
    return out.astype(np.float32), scaler


class ResidualMLP(nn.Module):
    def __init__(self, n_features: int, hidden: int) -> None:
        super().__init__()
        mid = max(int(hidden) // 2, 8)
        self.net = nn.Sequential(
            nn.Linear(int(n_features), int(hidden)),
            nn.ReLU(),
            nn.Linear(int(hidden), mid),
            nn.ReLU(),
            nn.Linear(mid, 2),
        )

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        out = self.net(torch.cat([seq, tab], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


class ResidualCNN(nn.Module):
    def __init__(self, n_samples: int, n_tab: int, channels: int) -> None:
        super().__init__()
        c = int(channels)
        self.conv = nn.Sequential(
            nn.Conv1d(1, c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(c, 2 * c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        width = max(2 * c + int(n_tab), 8)
        self.head = nn.Sequential(nn.Linear(2 * c + int(n_tab), width), nn.ReLU(), nn.Linear(width, 2))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.conv(seq[:, None, :])
        out = self.head(torch.cat([z, tab], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


class LabelGatedFusion(nn.Module):
    """Small waveform CNN with tabular-label gates before the residual head."""

    def __init__(self, n_samples: int, n_tab: int, channels: int) -> None:
        super().__init__()
        c = int(channels)
        self.conv = nn.Sequential(
            nn.Conv1d(1, c, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(c, 2 * c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.gate = nn.Sequential(nn.Linear(int(n_tab), 2 * c), nn.Sigmoid())
        self.tab = nn.Sequential(nn.Linear(int(n_tab), max(c, 8)), nn.ReLU())
        width = 2 * c + max(c, 8)
        self.head = nn.Sequential(nn.Linear(width, max(width, 16)), nn.ReLU(), nn.Linear(max(width, 16), 2))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.conv(seq[:, None, :])
        z = z * (0.5 + self.gate(tab))
        out = self.head(torch.cat([z, self.tab(tab)], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


def build_torch_model(kind: str, n_samples: int, n_tab: int, cfg: dict) -> nn.Module:
    if kind == "mlp":
        return ResidualMLP(n_samples + n_tab, int(cfg["ml"]["mlp_hidden"]))
    if kind == "cnn":
        return ResidualCNN(n_samples, n_tab, int(cfg["ml"]["cnn_channels"]))
    if kind == "gated_label_fusion":
        return LabelGatedFusion(n_samples, n_tab, int(cfg["ml"]["gated_channels"]))
    raise ValueError(kind)


def train_torch_model(
    seq: np.ndarray,
    tab: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    kind: str,
    cfg: dict,
    seed: int,
) -> Tuple[nn.Module, np.ndarray, np.ndarray, StandardScaler, StandardScaler]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    seq_s, seq_scaler = standardize_by_train(seq, train_idx)
    tab_s, tab_scaler = standardize_by_train(tab, train_idx)
    model = build_torch_model(kind, seq.shape[1], tab.shape[1], cfg)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(cfg["ml"]["learning_rate"]),
        weight_decay=float(cfg["ml"]["weight_decay"]),
    )
    seq_train = torch.from_numpy(seq_s[train_idx])
    tab_train = torch.from_numpy(tab_s[train_idx])
    y_train = torch.from_numpy(y[train_idx].astype(np.float32))
    batch_size = int(cfg["ml"]["batch_size"])
    min_var = float(cfg["ml"]["min_sigma_ns"]) ** 2
    for _ in range(int(cfg["ml"]["epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch_size):
            take = order[start : start + batch_size]
            mu, log_var = model(seq_train[take], tab_train[take])
            var = torch.exp(log_var) + min_var
            loss = torch.mean(0.5 * ((y_train[take] - mu) ** 2 / var + torch.log(var)))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model, seq_s, tab_s, seq_scaler, tab_scaler


def predict_torch(model: nn.Module, seq_s: np.ndarray, tab_s: np.ndarray, cfg: dict) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    with torch.no_grad():
        mu, log_var = model(torch.from_numpy(seq_s.astype(np.float32)), torch.from_numpy(tab_s.astype(np.float32)))
        sigma = torch.sqrt(torch.exp(log_var) + float(cfg["ml"]["min_sigma_ns"]) ** 2)
    return mu.numpy().astype(float), sigma.numpy().astype(float)


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def evaluate_corrected(
    pulses: pd.DataFrame,
    method_name: str,
    values: np.ndarray,
    cfg: dict,
    runs: Iterable[int],
) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, cfg, list(runs))


def event_pair_residual_frame(
    pulses: pd.DataFrame,
    methods: Sequence[Tuple[str, str]],
    cfg: dict,
    runs: Sequence[int],
) -> pd.DataFrame:
    downstream = list(cfg["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(cfg["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    rows = []
    for method, label in methods:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for event_id, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                if a in wide.columns and b in wide.columns:
                    rows.append(
                        {
                            "event_id": event_id,
                            "pair": f"{a}-{b}",
                            "method": label,
                            "residual_ns": float(row[a] - row[b]),
                        }
                    )
    return pd.DataFrame(rows)


def paired_event_bootstrap(pair_frame: pd.DataFrame, baseline_label: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    event_ids = np.asarray(sorted(pair_frame["event_id"].unique()))
    labels = sorted(pair_frame["method"].unique())
    by_method = {
        label: pair_frame[pair_frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for label in labels
    }
    observed = {label: s02.sigma68(pair_frame[pair_frame["method"] == label]["residual_ns"].to_numpy()) for label in labels}
    full_rms = {label: s02.full_rms(pair_frame[pair_frame["method"] == label]["residual_ns"].to_numpy()) for label in labels}
    stats = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
        boot = {}
        for label in labels:
            vals = np.concatenate([by_method[label][event_id] for event_id in sample_ids])
            boot[label] = s02.sigma68(vals)
            stats[label].append(boot[label])
        for label in labels:
            deltas[label].append(boot[label] - boot[baseline_label])
    for label in labels:
        rows.append(
            {
                "method": label,
                "baseline": baseline_label,
                "n_events": int(len(event_ids)),
                "n_pair_residuals": int(len(pair_frame[pair_frame["method"] == label])),
                "sigma68_ns": float(observed[label]),
                "ci_low": float(np.percentile(stats[label], 2.5)),
                "ci_high": float(np.percentile(stats[label], 97.5)),
                "full_rms_ns": float(full_rms[label]),
                "delta_vs_baseline_ns": float(observed[label] - observed[baseline_label]),
                "delta_ci_low": float(np.percentile(deltas[label], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[label], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def select_ridge_alpha(seq: np.ndarray, tab: np.ndarray, y: np.ndarray, train_idx: np.ndarray, runs: np.ndarray, pulses: pd.DataFrame, cfg: dict) -> Tuple[float, pd.DataFrame]:
    X = np.hstack([seq, tab]).astype(np.float32)
    groups = runs[train_idx]
    gkf = GroupKFold(n_splits=min(int(cfg["ml"]["cv_folds"]), len(np.unique(groups))))
    rows = []
    best = (math.inf, float(cfg["ml"]["ridge_alphas"][0]))
    for alpha in [float(x) for x in cfg["ml"]["ridge_alphas"]]:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
            tr_idx = train_idx[tr]
            va_idx = train_idx[va]
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(X[tr_idx], y[tr_idx])
            pred = np.full(len(y), np.nan)
            pred[va_idx] = model.predict(X[va_idx])
            vals = evaluate_corrected(
                pulses.iloc[va_idx].copy(),
                "ridge_cv",
                corrected_values(pulses, str(cfg["ml"]["base_method"]), pred)[va_idx],
                cfg,
                sorted(np.unique(runs[va_idx]).tolist()),
            )
            score = s02.sigma68(vals)
            scores.append(score)
            rows.append({"model": "ridge", "alpha": alpha, "fold": int(fold), "sigma68_ns": float(score), "n_pair_residuals": int(len(vals))})
        mean_score = float(np.nanmean(scores))
        rows.append({"model": "ridge", "alpha": alpha, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
        if mean_score < best[0]:
            best = (mean_score, alpha)
    return float(best[1]), pd.DataFrame(rows)


def select_hgb_params(seq: np.ndarray, tab: np.ndarray, y: np.ndarray, train_idx: np.ndarray, runs: np.ndarray, pulses: pd.DataFrame, cfg: dict) -> Tuple[dict, pd.DataFrame]:
    X = np.hstack([seq, tab]).astype(np.float32)
    groups = runs[train_idx]
    gkf = GroupKFold(n_splits=min(int(cfg["ml"]["cv_folds"]), len(np.unique(groups))))
    rows = []
    best = {"score": math.inf, "learning_rate": None, "max_leaf_nodes": None}
    for lr in [float(x) for x in cfg["ml"]["hgb_learning_rates"]]:
        for leaves in [int(x) for x in cfg["ml"]["hgb_max_leaf_nodes"]]:
            scores = []
            for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
                tr_idx = train_idx[tr]
                va_idx = train_idx[va]
                model = HistGradientBoostingRegressor(
                    learning_rate=lr,
                    max_leaf_nodes=leaves,
                    max_iter=int(cfg["ml"]["hgb_max_iter"]),
                    l2_regularization=0.01,
                    random_state=int(cfg["ml"]["random_seed"]) + fold + leaves,
                )
                model.fit(X[tr_idx], y[tr_idx])
                pred = np.full(len(y), np.nan)
                pred[va_idx] = model.predict(X[va_idx])
                vals = evaluate_corrected(
                    pulses.iloc[va_idx].copy(),
                    "hgb_cv",
                    corrected_values(pulses, str(cfg["ml"]["base_method"]), pred)[va_idx],
                    cfg,
                    sorted(np.unique(runs[va_idx]).tolist()),
                )
                score = s02.sigma68(vals)
                scores.append(score)
                rows.append(
                    {
                        "model": "gradient_boosted_trees",
                        "learning_rate": lr,
                        "max_leaf_nodes": leaves,
                        "fold": int(fold),
                        "sigma68_ns": float(score),
                        "n_pair_residuals": int(len(vals)),
                    }
                )
            mean_score = float(np.nanmean(scores))
            rows.append(
                {
                    "model": "gradient_boosted_trees",
                    "learning_rate": lr,
                    "max_leaf_nodes": leaves,
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "learning_rate": lr, "max_leaf_nodes": leaves}
    return best, pd.DataFrame(rows)


def train_sklearn_method(
    pulses: pd.DataFrame,
    cfg: dict,
    policy: str,
    heldout_run: int,
    targets: np.ndarray,
    train_idx: np.ndarray,
    method: str,
    choice,
) -> Tuple[np.ndarray, dict]:
    seq, tab, names = build_features(pulses, cfg, policy, heldout_run)
    X = np.hstack([seq, tab]).astype(np.float32)
    if method == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(choice)))
    elif method == "gradient_boosted_trees":
        model = HistGradientBoostingRegressor(
            learning_rate=float(choice["learning_rate"]),
            max_leaf_nodes=int(choice["max_leaf_nodes"]),
            max_iter=int(cfg["ml"]["hgb_max_iter"]),
            l2_regularization=0.01,
            random_state=int(cfg["ml"]["random_seed"]) + 11 * int(heldout_run) + len(policy),
        )
    else:
        raise ValueError(method)
    model.fit(X[train_idx], targets[train_idx])
    pred = model.predict(X)
    info = {
        "method": method,
        "policy": policy,
        "heldout_run": int(heldout_run),
        "n_features": int(X.shape[1]),
        "feature_names_sha256": hashlib.sha256(",".join(names).encode("utf-8")).hexdigest(),
        "choice": choice,
    }
    return pred.astype(float), info


def train_torch_method(
    pulses: pd.DataFrame,
    cfg: dict,
    policy: str,
    heldout_run: int,
    targets: np.ndarray,
    train_idx: np.ndarray,
    kind: str,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    seq, tab, names = build_features(pulses, cfg, policy, heldout_run)
    model, seq_s, tab_s, seq_scaler, tab_scaler = train_torch_model(
        seq,
        tab,
        targets,
        train_idx,
        kind,
        cfg,
        int(cfg["ml"]["random_seed"]) + 7001 * int(heldout_run) + 101 * len(policy) + 13 * len(kind),
    )
    pred, sigma = predict_torch(model, seq_s, tab_s, cfg)
    info = {
        "method": kind,
        "policy": policy,
        "heldout_run": int(heldout_run),
        "n_features": int(seq.shape[1] + tab.shape[1]),
        "feature_names_sha256": hashlib.sha256(",".join(names).encode("utf-8")).hexdigest(),
        "seq_scaler_mean_sha256": hashlib.sha256(seq_scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
        "tab_scaler_mean_sha256": hashlib.sha256(tab_scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
    }
    return pred, sigma, info


def label_offset_prediction(pulses: pd.DataFrame, cfg: dict, policy: str, heldout_run: int, targets: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, pd.DataFrame]:
    labels = labels_for_policy(pulses, cfg, policy, heldout_run, int(cfg["ml"]["random_seed"]) + 515)
    frame = pd.DataFrame({"label": labels, "target": targets, "train": False})
    frame.loc[train_idx, "train"] = True
    means = frame.loc[frame["train"]].groupby("label")["target"].mean()
    fallback = float(np.nanmean(targets[train_idx]))
    pred = np.asarray([float(means.get(label, fallback)) for label in labels], dtype=float)
    rows = [{"heldout_run": int(heldout_run), "policy": policy, "label": str(label), "train_mean_target_residual_ns": float(value)} for label, value in means.items()]
    rows.append({"heldout_run": int(heldout_run), "policy": policy, "label": "ALL_FALLBACK", "train_mean_target_residual_ns": fallback})
    return pred, pd.DataFrame(rows)


def run_fold(pulses_all: pd.DataFrame, config: dict, heldout_run: int, loo_runs: Sequence[int], rng: np.random.Generator):
    cfg = fold_config(config, heldout_run, loo_runs)
    train_pulses = pulses_all[pulses_all["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    fold_pulses = pulses_all.copy()
    methods = s02.add_traditional_times(fold_pulses, cfg, templates)
    traditional_scan = s02.evaluate_methods(fold_pulses, methods, cfg)
    traditional_scan["heldout_run"] = int(heldout_run)
    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(
        fold_pulses,
        cfg,
        str(cfg["timing"]["base_method"]),
    )
    combined = analytic_pulses.copy()
    base_method = str(cfg["ml"]["base_method"])
    targets = s02.event_residual_targets(combined, base_method, 2.0, cfg)
    runs = combined["run"].to_numpy(dtype=int)

    seq0, tab0, _ = build_features(combined, cfg, "real_stave", heldout_run)
    mask = np.isin(runs, list(cfg["timing"]["train_runs"])) & finite_mask(seq0, tab0, targets, runs)
    train_idx = np.flatnonzero(mask)
    ridge_alpha, ridge_cv = select_ridge_alpha(seq0, tab0, targets, train_idx, runs, combined, cfg)
    hgb_choice, hgb_cv = select_hgb_params(seq0, tab0, targets, train_idx, runs, combined, cfg)
    cv = pd.concat([ridge_cv, hgb_cv], ignore_index=True)
    cv["heldout_run"] = int(heldout_run)
    cv["policy"] = "real_stave"

    method_specs = [("analytic_timewalk", "traditional_analytic_timewalk")]
    calibration_rows = []
    choice_rows = [
        {
            "heldout_run": int(heldout_run),
            "model": "traditional_analytic_timewalk",
            "policy": "none",
            "choice": f"{best_candidate}, alpha={best_alpha}",
        },
        {"heldout_run": int(heldout_run), "model": "ridge", "policy": "real_stave_cv", "choice": f"alpha={ridge_alpha}"},
        {
            "heldout_run": int(heldout_run),
            "model": "gradient_boosted_trees",
            "policy": "real_stave_cv",
            "choice": f"learning_rate={hgb_choice['learning_rate']}, max_leaf_nodes={hgb_choice['max_leaf_nodes']}",
        },
    ]
    info_rows = []
    offset_frames = []

    for policy in config["ml"]["label_policies"]:
        if policy != "no_stave":
            pred, offsets = label_offset_prediction(combined, cfg, policy, heldout_run, targets, train_idx)
            offset_frames.append(offsets)
            label = f"label_offset_{policy}"
            combined[f"t_{label}_ns"] = corrected_values(combined, base_method, pred)
            method_specs.append((label, label))
        for method, choice in [("ridge", ridge_alpha), ("gradient_boosted_trees", hgb_choice)]:
            pred, info = train_sklearn_method(combined, cfg, policy, heldout_run, targets, train_idx, method, choice)
            label = f"{method}_{policy}"
            combined[f"t_{label}_ns"] = corrected_values(combined, base_method, pred)
            method_specs.append((label, label))
            info_rows.append(info)
        for kind in ["mlp", "cnn", "gated_label_fusion"]:
            pred, sigma, info = train_torch_method(combined, cfg, policy, heldout_run, targets, train_idx, kind)
            label = f"{kind}_{policy}"
            combined[f"t_{label}_ns"] = corrected_values(combined, base_method, pred)
            method_specs.append((label, label))
            held = np.isin(runs, list(cfg["timing"]["heldout_runs"])) & np.isfinite(targets) & np.isfinite(sigma)
            err = targets[held] - pred[held]
            pull = err / sigma[held]
            calibration_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "method": label,
                    "n_pulses": int(np.sum(held)),
                    "pred_sigma_median_ns": float(np.nanmedian(sigma[held])),
                    "abs_error_median_ns": float(np.nanmedian(np.abs(err))),
                    "pull_width_sigma68": float(s02.sigma68(pull)),
                    "pull_rms": float(s02.full_rms(pull)),
                }
            )
            info_rows.append(info)

    pair_frame = event_pair_residual_frame(combined, method_specs, cfg, [heldout_run])
    pair_frame["heldout_run"] = int(heldout_run)
    benchmark = paired_event_bootstrap(pair_frame, "traditional_analytic_timewalk", rng, int(cfg["ml"]["bootstrap_samples"]))
    benchmark["heldout_run"] = int(heldout_run)
    benchmark["train_runs"] = ",".join(str(run) for run in cfg["timing"]["train_runs"])

    train_event_ids = set(combined[combined["run"].isin(cfg["timing"]["train_runs"])]["event_id"])
    held_event_ids = set(combined[combined["run"].isin(cfg["timing"]["heldout_runs"])]["event_id"])
    leakage = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids & held_event_ids)),
                "detail": "must be zero",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "feature_audit",
                "value": float(len(method_specs)),
                "detail": "models use same-pulse normalized waveform and amplitude/shape features; label policies are no label, true stave, train-label permutation, and held-out-label permutation; no event id, event order, other-stave time, pair residual, or held-out target feature is used",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "traditional_analytic_choice",
                "value": float(best_alpha),
                "detail": best_candidate,
            },
        ]
    )
    extras = {
        "traditional_scan": traditional_scan,
        "analytic_cv": analytic_cv.assign(heldout_run=int(heldout_run)),
        "analytic_coef": analytic_coef.assign(heldout_run=int(heldout_run)),
        "ml_cv": cv,
        "calibration": pd.DataFrame(calibration_rows),
        "model_feature_audit": pd.DataFrame(info_rows),
        "model_choices": pd.DataFrame(choice_rows),
        "label_offsets": pd.concat(offset_frames, ignore_index=True) if offset_frames else pd.DataFrame(),
        "leakage": leakage,
    }
    return benchmark, pair_frame, extras


def pooled_summary(heldout: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in heldout.groupby("method"):
        rows.append(
            {
                "method": method,
                "family": method_family(method),
                "label_policy": method_policy(method),
                "mean_sigma68_ns": float(group["sigma68_ns"].mean()),
                "median_sigma68_ns": float(group["sigma68_ns"].median()),
                "min_sigma68_ns": float(group["sigma68_ns"].min()),
                "max_sigma68_ns": float(group["sigma68_ns"].max()),
                "mean_full_rms_ns": float(group["full_rms_ns"].mean()),
                "n_heldout_runs": int(group["heldout_run"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_sigma68_ns")


def method_family(method: str) -> str:
    if method.startswith("traditional"):
        return "traditional"
    if method.startswith("label_offset"):
        return "label_only_offset"
    if method.startswith("gradient_boosted_trees"):
        return "gradient_boosted_trees"
    if method.startswith("gated_label_fusion"):
        return "new_gated_label_fusion"
    return method.split("_", 1)[0]


def method_policy(method: str) -> str:
    for policy in ["train_label_permutation", "heldout_label_permutation", "real_stave", "no_stave"]:
        if method.endswith(policy):
            return policy
    return "none"


def run_bootstrap_gaps(heldout: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 333)
    wide = heldout.pivot(index="heldout_run", columns="method", values="sigma68_ns")
    rows = []
    comparisons = []
    for family in ["ridge", "gradient_boosted_trees", "mlp", "cnn", "gated_label_fusion"]:
        real = f"{family}_real_stave"
        nostave = f"{family}_no_stave"
        trainp = f"{family}_train_label_permutation"
        heldp = f"{family}_heldout_label_permutation"
        for control in [nostave, trainp, heldp]:
            if real in wide.columns and control in wide.columns:
                comparisons.append((real, control, f"{real}_minus_{control}"))
    for real in ["label_offset_real_stave"]:
        for control in ["label_offset_train_label_permutation", "label_offset_heldout_label_permutation"]:
            if real in wide.columns and control in wide.columns:
                comparisons.append((real, control, f"{real}_minus_{control}"))
    for a, b, name in comparisons:
        vals = (wide[a] - wide[b]).dropna().to_numpy(dtype=float)
        boot = [float(np.mean(rng.choice(vals, size=len(vals), replace=True))) for _ in range(int(config["ml"]["run_bootstrap_samples"]))]
        loo = [float(np.mean(np.delete(vals, i))) for i in range(len(vals))] if len(vals) > 1 else [float(vals[0])]
        rows.append(
            {
                "comparison": name,
                "method": a,
                "control": b,
                "n_runs": int(len(vals)),
                "mean_delta_sigma68_ns": float(np.mean(vals)),
                "run_bootstrap_ci_low": float(np.percentile(boot, 2.5)),
                "run_bootstrap_ci_high": float(np.percentile(boot, 97.5)),
                "leave_one_run_min": float(np.nanmin(loo)),
                "leave_one_run_max": float(np.nanmax(loo)),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_delta_sigma68_ns")


def plot_outputs(out_dir: Path, heldout: pd.DataFrame, pooled: pd.DataFrame, gaps: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.0, 5.2))
    show = [
        "traditional_analytic_timewalk",
        "ridge_real_stave",
        "gradient_boosted_trees_real_stave",
        "mlp_real_stave",
        "cnn_real_stave",
        "gated_label_fusion_real_stave",
    ]
    for method in show:
        rows = heldout[heldout["method"] == method].sort_values("heldout_run")
        if len(rows):
            ax.errorbar(
                rows["heldout_run"],
                rows["sigma68_ns"],
                yerr=[rows["sigma68_ns"] - rows["ci_low"], rows["ci_high"] - rows["sigma68_ns"]],
                marker="o",
                capsize=3,
                label=method,
            )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("P03g detector-label permutation benchmark")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_real_stave_methods_by_run.png", dpi=130)
    plt.close(fig)

    top = pooled.head(18).copy().sort_values("mean_sigma68_ns", ascending=False)
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.barh(top["method"], top["mean_sigma68_ns"])
    ax.set_xlabel("mean run-heldout sigma68 (ns)")
    ax.set_title("Top pooled methods")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_top_methods.png", dpi=130)
    plt.close(fig)

    if len(gaps):
        rows = gaps.copy().sort_values("mean_delta_sigma68_ns")
        fig, ax = plt.subplots(figsize=(10.0, 5.0))
        x = np.arange(len(rows))
        ax.bar(x, rows["mean_delta_sigma68_ns"])
        ax.errorbar(
            x,
            rows["mean_delta_sigma68_ns"],
            yerr=[
                rows["mean_delta_sigma68_ns"] - rows["run_bootstrap_ci_low"],
                rows["run_bootstrap_ci_high"] - rows["mean_delta_sigma68_ns"],
            ],
            fmt="none",
            ecolor="black",
            capsize=3,
        )
        ax.axhline(0.0, color="black", linewidth=1)
        ax.set_xticks(x)
        ax.set_xticklabels(rows["comparison"], rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("real-label minus control sigma68 (ns)")
        ax.set_title("Run-bootstrap detector-label stress gaps")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_label_policy_gaps.png", dpi=130)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    heldout: pd.DataFrame,
    pooled: pd.DataFrame,
    gaps: pd.DataFrame,
    calibration: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    real = pooled[pooled["label_policy"].isin(["real_stave", "none"])].copy()
    policy = pooled[pooled["label_policy"].isin(["real_stave", "train_label_permutation", "heldout_label_permutation", "no_stave"])].copy()
    lines = [
        "# Study report: P03g - detector-label permutation stress test for stave-aware residual timing",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo labels or simulated timing targets",
        "- **Split:** leave one Sample-II analysis run out across runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Config:** `{config_path}`",
        "",
        "## Abstract",
        "",
        f"The benchmark winner named in `result.json` is **{result['winner']['method']}**, with mean run-heldout pairwise sigma68 `{result['winner']['mean_sigma68_ns']:.4f}` ns. The purpose is not only to minimize timing width, but to test whether explicit detector labels carry real waveform-shape information or merely static per-stave offsets.",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "Before fitting timing models, the selected-pulse count was recomputed directly from the B-stack ROOT files. The gate is amplitude > 1000 ADC after baseline subtraction on the four B staves.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Estimand and metrics",
        "",
        "For each pulse in event `e` and stave `s`, the base corrected time is",
        "",
        "`u_es = t_es - z_s v_TOF`,",
        "",
        "where `z_s` is the nominal 2 cm-spaced downstream stave position and `v_TOF = 0.078 ns/cm`. The residual-learning target is",
        "",
        "`r_es = u_es - (1/2) sum_{q != s} u_eq`,",
        "",
        "using the other two downstream staves in the same event. A model predicts `rhat_es`; the final time is `t'_es = t_es - rhat_es`. Methods are scored on the three same-event pairwise differences after time-of-flight subtraction. The headline width is `sigma68 = (Q84 - Q16)/2`; event-block bootstraps provide 95% CIs within a held-out run, and run-block bootstraps provide label-policy CIs across the seven held-out runs.",
        "",
        "## Methods",
        "",
        "The traditional reference is template-phase timing followed by a transparent analytic timewalk ridge model. Candidate analytic models were `amp_only`, `amp_rise_shape`, and `amp_rise_shape_by_stave`; the selected candidate and alpha were chosen inside each training split by grouped-run CV.",
        "",
        "The ML/NN benchmark contains ridge regression, histogram gradient-boosted trees, a heteroskedastic MLP, a 1D-CNN, and a new gated label-fusion CNN. Ridge and boosted-tree hyperparameters were selected by grouped-run CV on the real-stave policy and then frozen for all detector-label policies in that fold. Neural nets used the same fixed capacities across policies so policy effects are not confounded with architecture search.",
        "",
        "Detector-label policies:",
        "",
        "- `no_stave`: waveform and scalar shape features, no detector identity.",
        "- `real_stave`: true downstream stave one-hot.",
        "- `train_label_permutation`: training labels are randomly permuted; held-out labels are true.",
        "- `heldout_label_permutation`: training labels are true; held-out labels are randomly permuted.",
        "- `label_offset_*`: label-only train-run mean residual offsets, with no waveform samples.",
        "",
        "## Real-stave head-to-head",
        "",
        real[["method", "family", "label_policy", "mean_sigma68_ns", "median_sigma68_ns", "min_sigma68_ns", "max_sigma68_ns", "mean_full_rms_ns", "n_heldout_runs"]]
        .sort_values("mean_sigma68_ns")
        .to_markdown(index=False),
        "",
        "## Detector-label policy summary",
        "",
        policy[["method", "family", "label_policy", "mean_sigma68_ns", "median_sigma68_ns", "mean_full_rms_ns", "n_heldout_runs"]]
        .sort_values(["family", "mean_sigma68_ns"])
        .to_markdown(index=False),
        "",
        "## Run-bootstrap label stress gaps",
        "",
        "Negative real-minus-control values mean the true detector labels beat that control; intervals covering zero indicate weak evidence that true labels are doing more than the control.",
        "",
        gaps.to_markdown(index=False),
        "",
        "## Per-heldout-run metrics",
        "",
        heldout[["heldout_run", "method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "delta_vs_baseline_ns", "delta_ci_low", "delta_ci_high", "n_pair_residuals"]]
        .sort_values(["heldout_run", "sigma68_ns"])
        .to_markdown(index=False),
        "",
        "## Calibration, leakage, and systematics",
        "",
        calibration.to_markdown(index=False) if len(calibration) else "_No neural calibration rows were produced._",
        "",
        leakage.sort_values(["heldout_run", "check"]).to_markdown(index=False),
        "",
        "Systematic limitations: the run-block CI has only seven blocks, so it is a stability diagnostic rather than an asymptotic interval; the permutation controls preserve the marginal stave frequencies but not every possible run/stave correlation; and the residual target is self-supervised from downstream timing closure rather than an external truth time. A method that improves under `heldout_label_permutation` is treated cautiously because it can be exploiting waveform or amplitude features rather than detector labels. Conversely, large gains by `label_offset_real_stave` would indicate static per-stave offsets rather than waveform-shape learning.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. Winner: `{result['winner']['method']}`. Best real-stave ML/NN method: `{result['best_real_stave_method']['method']}`. Label-only real-stave offset mean sigma68: `{result['label_offset_real_stave_mean_sigma68_ns']:.4f}` ns.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/p03g_1781034623_1447_4a243444_detector_label_permutation.py --config {config_path}",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `downstream_counts_by_run.csv`, `heldout_run_summary.csv`, `pooled_summary.csv`, `run_label_policy_gap_summary.csv`, `heldout_pair_residuals.csv`, `traditional_scan_metrics.csv`, `analytic_cv_scan.csv`, `analytic_coefficients.csv`, `ml_cv_scan.csv`, `ml_calibration.csv`, `model_feature_audit.csv`, `model_choices_by_run.csv`, `label_offset_table.csv`, `leakage_checks.csv`, and PNG figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03g_1781034623_1447_4a243444_detector_label_permutation.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    loo_runs = [int(run) for run in config["timing"]["loo_runs"]]
    all_run_cfg = copy.deepcopy(config)
    all_run_cfg["timing"]["train_runs"] = loo_runs
    all_run_cfg["timing"]["heldout_runs"] = []
    pulses = s02.load_downstream_pulses(all_run_cfg)
    pulses.groupby(["run", "stave"]).size().reset_index(name="selected_downstream_pulses").to_csv(
        out_dir / "downstream_counts_by_run.csv",
        index=False,
    )

    benchmark_frames = []
    pair_frames = []
    extras = {
        "traditional_scan": [],
        "analytic_cv": [],
        "analytic_coef": [],
        "ml_cv": [],
        "calibration": [],
        "model_feature_audit": [],
        "model_choices": [],
        "label_offsets": [],
        "leakage": [],
    }
    for heldout_run in loo_runs:
        benchmark, pair_frame, extra = run_fold(pulses, config, heldout_run, loo_runs, rng)
        benchmark_frames.append(benchmark)
        pair_frames.append(pair_frame)
        for key in extras:
            if key in extra and len(extra[key]):
                extras[key].append(extra[key])

    heldout = pd.concat(benchmark_frames, ignore_index=True)
    heldout.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    pair_frame = pd.concat(pair_frames, ignore_index=True)
    pair_frame.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    pooled = pooled_summary(heldout)
    pooled.to_csv(out_dir / "pooled_summary.csv", index=False)
    gaps = run_bootstrap_gaps(heldout, config)
    gaps.to_csv(out_dir / "run_label_policy_gap_summary.csv", index=False)

    for key, filename in [
        ("traditional_scan", "traditional_scan_metrics.csv"),
        ("analytic_cv", "analytic_cv_scan.csv"),
        ("analytic_coef", "analytic_coefficients.csv"),
        ("ml_cv", "ml_cv_scan.csv"),
        ("calibration", "ml_calibration.csv"),
        ("model_feature_audit", "model_feature_audit.csv"),
        ("model_choices", "model_choices_by_run.csv"),
        ("label_offsets", "label_offset_table.csv"),
        ("leakage", "leakage_checks.csv"),
    ]:
        frame = pd.concat(extras[key], ignore_index=True) if extras[key] else pd.DataFrame()
        frame.to_csv(out_dir / filename, index=False)

    leakage = pd.concat(extras["leakage"], ignore_index=True) if extras["leakage"] else pd.DataFrame()
    calibration = pd.concat(extras["calibration"], ignore_index=True) if extras["calibration"] else pd.DataFrame()
    plot_outputs(out_dir, heldout, pooled, gaps)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in sorted(input_hashes.items())]).to_csv(
        out_dir / "input_sha256.csv",
        index=False,
    )
    winner_row = pooled.iloc[0].to_dict()
    real_methods = pooled[(pooled["label_policy"] == "real_stave") & (pooled["family"] != "label_only_offset")].copy()
    best_real = real_methods.sort_values("mean_sigma68_ns").iloc[0].to_dict()
    label_offset = pooled[pooled["method"] == "label_offset_real_stave"]
    offset_mean = float(label_offset.iloc[0]["mean_sigma68_ns"]) if len(label_offset) else float("nan")
    real_gaps = gaps[gaps["method"].str.endswith("real_stave")] if len(gaps) else pd.DataFrame()
    label_evidence = "weak_or_mixed"
    if len(real_gaps) and bool((real_gaps["run_bootstrap_ci_high"] < 0.0).any()):
        label_evidence = "some_true_label_gaps_exclude_zero"
    if len(real_gaps) and bool((real_gaps["run_bootstrap_ci_high"] < 0.0).all()):
        label_evidence = "all_true_label_gaps_exclude_zero"
    verdict = "waveform_shape_gain_dominates_detector_label_effect"
    if winner_row["method"] == "label_offset_real_stave":
        verdict = "static_detector_offsets_dominate"
    elif method_policy(str(winner_row["method"])) in {"train_label_permutation", "heldout_label_permutation"}:
        verdict = "permutation_control_wins_label_claim_not_supported"
    elif method_policy(str(winner_row["method"])) == "real_stave" and label_evidence != "weak_or_mixed":
        verdict = "real_stave_labels_help_but_waveform_controls_required"

    result = {
        "study": "P03g",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "split_by_run": True,
        "heldout_runs": loo_runs,
        "metric": "leave-one-run-out downstream pairwise sigma68 with event bootstrap CIs and run-block label-policy gap CIs",
        "winner": {
            "method": str(winner_row["method"]),
            "family": str(winner_row["family"]),
            "label_policy": str(winner_row["label_policy"]),
            "mean_sigma68_ns": float(winner_row["mean_sigma68_ns"]),
            "median_sigma68_ns": float(winner_row["median_sigma68_ns"]),
        },
        "best_real_stave_method": {
            "method": str(best_real["method"]),
            "family": str(best_real["family"]),
            "mean_sigma68_ns": float(best_real["mean_sigma68_ns"]),
        },
        "traditional": pooled[pooled["method"] == "traditional_analytic_timewalk"].to_dict(orient="records"),
        "model_families": sorted(set(pooled["family"].tolist())),
        "label_policies": sorted(set(pooled["label_policy"].tolist())),
        "pooled_summary": pooled.to_dict(orient="records"),
        "label_policy_gaps": gaps.to_dict(orient="records"),
        "label_offset_real_stave_mean_sigma68_ns": offset_mean,
        "label_evidence": label_evidence,
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "follow_up_ticket_appended": False,
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, config_path, config, repro, heldout, pooled, gaps, calibration, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03g",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "verdict": verdict}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
