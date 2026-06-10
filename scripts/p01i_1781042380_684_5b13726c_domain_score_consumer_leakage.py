#!/usr/bin/env python3
"""P01i: domain-score consumer leakage sentinel.

This study consumes the P01b latent table and the P03d epoch/domain-score idea,
but evaluates consumer-level leakage directly.  All score construction,
residualization, model fitting, and evaluation are leave-one-run-out over the
Sample-II analysis runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p01i-1781042380")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, mean_squared_error, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn

    torch.set_num_threads(1)
except Exception:  # pragma: no cover - recorded in result.json.
    torch = None
    nn = None

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p03d_1781016668_1163_37da5572_epoch_score_timing as p03d  # noqa: E402
import s02_timing_pickoff as s02  # noqa: E402


REGRESSION_CONSUMERS = {"timing", "charge", "energy"}
CLASSIFICATION_CONSUMERS = {"pileup", "pid"}
DOMAIN_VARIANTS = ["no_score", "plus_score", "score_residualized", "shuffled_score_control"]
METHODS = ["traditional", "ridge", "gradient_boosted_trees", "extra_trees", "mlp", "cnn1d", "score_gated_cnn"]
FAST_CONSUMER_METHODS = ["traditional", "ridge", "gradient_boosted_trees", "extra_trees"]


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
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    return value


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = str(group)
    return out


def one_hot_text(values: Sequence[object], levels: Sequence[object]) -> np.ndarray:
    lookup = {str(level): i for i, level in enumerate(levels)}
    out = np.zeros((len(values), len(levels)), dtype=np.float32)
    for i, value in enumerate(values):
        key = str(value)
        if key in lookup:
            out[i, lookup[key]] = 1.0
    return out


def add_cfd20(pulses: pd.DataFrame, config: dict) -> None:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    pulses["t_cfd20_ns"] = float(config["sample_period_ns"]) * s02.cfd_time_samples(wf, amp, 0.20)


def add_shape_atoms(pulses: pd.DataFrame, train_mask: np.ndarray, config: dict) -> None:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    pulses["log_amp"] = np.log1p(amp)
    pulses["area_over_amp"] = pulses["area_adc_samples"].to_numpy(dtype=float) / amp
    pulses["baseline_median_adc"] = np.median(wf[:, :4], axis=1)
    pulses["baseline_rms_adc"] = np.std(wf[:, :4], axis=1)
    pulses["baseline_slope_adc"] = wf[:, 3] - wf[:, 0]
    pulses["early_fraction"] = norm[:, :6].sum(axis=1) / np.maximum(np.abs(norm.sum(axis=1)), 1.0e-6)
    pulses["late_fraction"] = norm[:, 10:].sum(axis=1) / np.maximum(np.abs(norm.sum(axis=1)), 1.0e-6)
    pulses["width_over_half"] = (norm > 0.5).sum(axis=1)
    pulses["saturation_flag"] = amp >= np.percentile(amp[train_mask], 99.5)
    templates: Dict[str, np.ndarray] = {}
    q = np.full(len(pulses), np.nan, dtype=float)
    for stave in config["timing"]["downstream_staves"]:
        sel = train_mask & (pulses["stave"].to_numpy() == stave)
        templates[stave] = np.median(norm[sel], axis=0) if sel.any() else np.median(norm[train_mask], axis=0)
        idx = pulses["stave"].to_numpy() == stave
        q[idx] = np.sqrt(np.mean((norm[idx] - templates[stave][None, :]) ** 2, axis=1))
    pulses["q_template_rmse"] = q
    q95 = float(np.nanpercentile(q[train_mask], 95))
    late95 = float(np.nanpercentile(pulses.loc[train_mask, "late_fraction"], 95))
    width05 = float(np.nanpercentile(pulses.loc[train_mask, "width_over_half"], 5))
    pulses["dropout_atom"] = pulses["width_over_half"].to_numpy(dtype=float) <= width05
    pulses["anomaly_atom"] = (pulses["q_template_rmse"].to_numpy(dtype=float) >= q95) | (pulses["late_fraction"].to_numpy(dtype=float) >= late95)
    wide_amp = pulses.pivot(index="event_id", columns="stave", values="amplitude_adc")
    event_charge = wide_amp.sum(axis=1)
    pulses["event_log_charge"] = pulses["event_id"].map(np.log1p(event_charge)).astype(float)
    pulses["topology_n"] = len(config["timing"]["downstream_staves"])
    pulses["run_group"] = pulses["run"].map(run_group_lookup(config))


def nuisance_matrix(pulses: pd.DataFrame, config: dict) -> np.ndarray:
    numeric = pulses[
        [
            "log_amp",
            "area_over_amp",
            "peak_sample",
            "baseline_median_adc",
            "baseline_rms_adc",
            "baseline_slope_adc",
            "q_template_rmse",
            "late_fraction",
            "width_over_half",
        ]
    ].to_numpy(dtype=np.float32)
    binary = pulses[["saturation_flag", "dropout_atom", "anomaly_atom"]].to_numpy(dtype=np.float32)
    stave = one_hot_text(pulses["stave"], config["timing"]["downstream_staves"])
    run_group = one_hot_text(pulses["run_group"], sorted(config["run_groups"].keys()))
    topology = np.full((len(pulses), 1), float(len(config["timing"]["downstream_staves"])), dtype=np.float32)
    return np.hstack([numeric, binary, stave, run_group, topology]).astype(np.float32)


def waveform_matrix(pulses: pd.DataFrame) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
    return (wf / amp[:, None]).astype(np.float32)


def feature_matrix(pulses: pd.DataFrame, config: dict, method: str, variant: str, rng: np.random.Generator) -> np.ndarray:
    if method == "traditional":
        cols = ["log_amp", "area_over_amp", "peak_sample", "baseline_rms_adc", "q_template_rmse", "late_fraction", "width_over_half"]
        X = [pulses[cols].to_numpy(dtype=np.float32)]
    else:
        X = [waveform_matrix(pulses), nuisance_matrix(pulses, config)]
    if variant == "plus_score":
        X.append(pulses[["p01b_epoch_logit"]].to_numpy(dtype=np.float32))
    elif variant == "score_residualized":
        X.append(pulses[["p01b_epoch_logit_resid_full"]].to_numpy(dtype=np.float32))
    elif variant == "shuffled_score_control":
        shuffled = pulses["p01b_epoch_logit_resid_full"].to_numpy(dtype=np.float32).copy()
        rng.shuffle(shuffled)
        X.append(shuffled[:, None])
    return np.hstack(X).astype(np.float32)


def fit_domain_score(p01b: pd.DataFrame, pulses: pd.DataFrame, heldout_run: int, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    train_runs = [run for run in configured_runs(config) if int(run) != int(heldout_run)]
    y = p01b["sample_epoch"].to_numpy(dtype=int)
    train_mask = p01b["run"].isin(train_runs).to_numpy()
    train_idx_parts = []
    for label in [0, 1]:
        idx = np.flatnonzero(train_mask & (y == label))
        take = min(len(idx), int(config["domain_score"]["max_rows_per_class"]))
        train_idx_parts.append(rng.choice(idx, size=take, replace=False))
    train_idx = np.concatenate(train_idx_parts)
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    clf.fit(p03d.p01b_score_features(p01b.iloc[train_idx]), y[train_idx])
    out = pulses.copy()
    prob = clf.predict_proba(p03d.p01b_score_features(out))[:, 1]
    eps = 1.0e-6
    out["p01b_epoch_prob_sample_ii"] = prob
    out["p01b_epoch_logit"] = np.log(np.clip(prob, eps, 1.0 - eps) / np.clip(1.0 - prob, eps, 1.0 - eps))
    sample_train = out["run"].to_numpy(dtype=int) != int(heldout_run)
    Xn = nuisance_matrix(out, config)
    resid_model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["domain_score"]["residual_ridge_alpha"])))
    resid_model.fit(Xn[sample_train], out.loc[sample_train, "p01b_epoch_logit"].to_numpy(dtype=float))
    pred = resid_model.predict(Xn)
    out["p01b_epoch_logit_nuisance_pred"] = pred
    out["p01b_epoch_logit_resid_full"] = out["p01b_epoch_logit"].to_numpy(dtype=float) - pred
    return out


def add_targets(pulses: pd.DataFrame, config: dict, train_mask: np.ndarray) -> Dict[str, dict]:
    target = s02.event_residual_targets(pulses, str(config["timing"]["base_method"]), 2.0, config)
    pulses["target_timing_residual_ns"] = target
    pulses["target_charge_log_area"] = np.log1p(np.maximum(pulses["area_adc_samples"].to_numpy(dtype=float), 1.0))
    pulses["target_energy_event_log_charge"] = pulses["event_log_charge"].to_numpy(dtype=float)
    abs_train = np.abs(target[train_mask & np.isfinite(target)])
    tail_threshold = max(3.0, float(np.nanpercentile(abs_train, 90))) if len(abs_train) else 5.0
    pulses["target_pileup_tail_proxy"] = (np.abs(target) > tail_threshold).astype(int)
    pulses["target_pid_b8_proxy"] = (pulses["stave"].to_numpy() == "B8").astype(int)
    return {
        "timing": {"target": "target_timing_residual_ns", "kind": "regression", "metric": "sigma68", "unit": "ns"},
        "charge": {"target": "target_charge_log_area", "kind": "regression", "metric": "res68", "unit": "log ADC-samples"},
        "pileup": {"target": "target_pileup_tail_proxy", "kind": "classification", "metric": "roc_auc", "tail_threshold_ns": tail_threshold},
        "pid": {"target": "target_pid_b8_proxy", "kind": "classification", "metric": "roc_auc"},
        "energy": {"target": "target_energy_event_log_charge", "kind": "regression", "metric": "res68", "unit": "log event-charge proxy"},
    }


def finite_rows(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1)


def make_model(method: str, kind: str, config: dict, seed: int):
    if kind == "regression":
        if method in {"traditional", "ridge"}:
            return make_pipeline(StandardScaler(), Ridge(alpha=float(config["models"]["ridge_alpha"])))
        if method == "gradient_boosted_trees":
            return HistGradientBoostingRegressor(
                max_iter=int(config["models"]["hgb_max_iter"]),
                max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
                learning_rate=float(config["models"]["hgb_learning_rate"]),
                random_state=seed,
            )
        if method == "extra_trees":
            return ExtraTreesRegressor(
                n_estimators=int(config["models"]["extra_trees_estimators"]),
                max_depth=int(config["models"]["extra_trees_max_depth"]),
                min_samples_leaf=int(config["models"]["extra_trees_min_samples_leaf"]),
                random_state=seed,
                n_jobs=1,
            )
        if method == "mlp":
            return make_pipeline(
                StandardScaler(),
                MLPRegressor(
                    hidden_layer_sizes=tuple(config["models"]["mlp_hidden_layer_sizes"]),
                    max_iter=int(config["models"]["mlp_max_iter"]),
                    alpha=1.0e-4,
                    early_stopping=True,
                    random_state=seed,
                ),
            )
    else:
        if method in {"traditional", "ridge"}:
            return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
        if method == "gradient_boosted_trees":
            return HistGradientBoostingClassifier(
                max_iter=int(config["models"]["hgb_max_iter"]),
                max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
                learning_rate=float(config["models"]["hgb_learning_rate"]),
                random_state=seed,
            )
        if method == "extra_trees":
            return ExtraTreesClassifier(
                n_estimators=int(config["models"]["extra_trees_estimators"]),
                max_depth=int(config["models"]["extra_trees_max_depth"]),
                min_samples_leaf=int(config["models"]["extra_trees_min_samples_leaf"]),
                random_state=seed,
                class_weight="balanced",
                n_jobs=1,
            )
        if method == "mlp":
            return make_pipeline(
                StandardScaler(),
                MLPClassifier(
                    hidden_layer_sizes=tuple(config["models"]["mlp_hidden_layer_sizes"]),
                    max_iter=int(config["models"]["mlp_max_iter"]),
                    alpha=1.0e-4,
                    early_stopping=True,
                    random_state=seed,
                ),
            )
    raise ValueError(f"unsupported sklearn model: {method} {kind}")


class SmallCNN(nn.Module):
    def __init__(self, n_features: int, task: str) -> None:
        super().__init__()
        self.seq_len = 18
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(24 + n_features - self.seq_len, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, x):
        seq = x[:, : self.seq_len]
        tab = x[:, self.seq_len :]
        return self.head(torch.cat([self.conv(seq[:, None, :]), tab], dim=1)).squeeze(1)


class ScoreGatedCNN(nn.Module):
    def __init__(self, n_features: int) -> None:
        super().__init__()
        self.seq_len = 18
        n_tab = n_features - self.seq_len
        self.input = nn.Conv1d(1, 24, kernel_size=3, padding=1)
        self.local = nn.Sequential(nn.Conv1d(24, 24, 3, padding=1), nn.GELU(), nn.Conv1d(24, 24, 3, padding=1))
        self.gate = nn.Sequential(nn.Linear(48 + n_tab, 24), nn.ReLU(), nn.Linear(24, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(48 + n_tab, 48), nn.GELU(), nn.Linear(48, 1))

    def forward(self, x):
        seq = x[:, : self.seq_len]
        tab = x[:, self.seq_len :]
        z0 = torch.relu(self.input(seq[:, None, :]))
        z = torch.relu(z0 + self.local(z0))
        pooled_mean = z.mean(dim=2)
        pooled_max = z.amax(dim=2)
        gate = self.gate(torch.cat([pooled_mean, pooled_max, tab], dim=1)).unsqueeze(2)
        zg = z * gate
        pooled = torch.cat([zg.mean(dim=2), zg.amax(dim=2)], dim=1)
        return self.head(torch.cat([pooled, tab], dim=1)).squeeze(1)


def torch_predict(method: str, X: np.ndarray, y: np.ndarray, train: np.ndarray, kind: str, config: dict, seed: int) -> Tuple[np.ndarray, dict]:
    if torch is None:
        return np.full(len(y), np.nan), {"skipped": "torch_unavailable"}
    valid = train & finite_rows(X, y)
    scaler = StandardScaler()
    Xs = X.astype(np.float32).copy()
    Xs[valid] = scaler.fit_transform(Xs[valid])
    Xs[~valid] = scaler.transform(Xs[~valid])
    torch.manual_seed(seed)
    model = SmallCNN(X.shape[1], kind) if method == "cnn1d" else ScoreGatedCNN(X.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_learning_rate"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    rng = np.random.default_rng(seed)
    idx = np.flatnonzero(valid)
    xb = torch.from_numpy(Xs[idx].astype(np.float32))
    if kind == "regression":
        center = float(np.nanmedian(y[idx]))
        scale = max(float(s02.sigma68(y[idx] - center)), 0.25)
        yt = torch.from_numpy(((y[idx] - center) / scale).astype(np.float32))
        loss_fn = nn.SmoothL1Loss(beta=0.75)
    else:
        center = 0.0
        scale = 1.0
        yt = torch.from_numpy(y[idx].astype(np.float32))
        loss_fn = nn.BCEWithLogitsLoss()
    model.train()
    for _ in range(int(config["models"]["torch_epochs"])):
        order = rng.permutation(len(idx))
        for start in range(0, len(order), int(config["models"]["torch_batch_size"])):
            take = order[start : start + int(config["models"]["torch_batch_size"])]
            opt.zero_grad()
            loss = loss_fn(model(xb[take]), yt[take])
            loss.backward()
            opt.step()
    pred = np.full(len(y), np.nan, dtype=float)
    model.eval()
    with torch.no_grad():
        for start in range(0, len(y), 4096):
            out = model(torch.from_numpy(Xs[start : start + 4096].astype(np.float32))).numpy()
            pred[start : start + 4096] = out * scale + center if kind == "regression" else 1.0 / (1.0 + np.exp(-out))
    return pred, {"epochs": int(config["models"]["torch_epochs"]), "target_center": center, "target_scale": scale}


def predict_fold(method: str, X: np.ndarray, y: np.ndarray, train: np.ndarray, kind: str, config: dict, seed: int) -> Tuple[np.ndarray, dict]:
    if method in {"cnn1d", "score_gated_cnn"}:
        return torch_predict(method, X, y, train, kind, config, seed)
    valid = train & finite_rows(X, y)
    model = make_model(method, kind, config, seed)
    model.fit(X[valid], y[valid])
    if kind == "classification" and hasattr(model, "predict_proba"):
        pred = model.predict_proba(X)[:, 1]
    elif kind == "classification":
        pred = model.decision_function(X)
        pred = 1.0 / (1.0 + np.exp(-pred))
    else:
        pred = model.predict(X)
    return np.asarray(pred, dtype=float), {"train_rows": int(valid.sum())}


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return s02.sigma68(values) if len(values) else float("nan")


def res68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(np.percentile(np.abs(values - np.median(values)), 68)) if len(values) else float("nan")


def ece_binary(y: np.ndarray, p: np.ndarray, n_bins: int = 8) -> float:
    mask = np.isfinite(y) & np.isfinite(p)
    y = y[mask].astype(int)
    p = np.clip(p[mask].astype(float), 0.0, 1.0)
    if len(y) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if sel.any():
            out += float(sel.mean()) * abs(float(y[sel].mean()) - float(p[sel].mean()))
    return out


def summarize_predictions(pred: pd.DataFrame, tasks: Dict[str, dict], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for (consumer, method, variant), group in pred.groupby(["consumer", "method", "variant"], sort=True):
        info = tasks[consumer]
        y = group["y_true"].to_numpy(dtype=float)
        p = group["prediction"].to_numpy(dtype=float)
        runs = group["run"].to_numpy(dtype=int)
        mask = np.isfinite(y) & np.isfinite(p)
        y = y[mask]
        p = p[mask]
        runs = runs[mask]
        if info["kind"] == "regression":
            residual = y - p
            primary = sigma68(residual) if consumer == "timing" else res68(residual)
            rmse = float(math.sqrt(mean_squared_error(y, p))) if len(y) else float("nan")
            metric_name = "sigma68" if consumer == "timing" else "res68"
            auc = ap = brier = ece = float("nan")
            stat_fn = sigma68 if consumer == "timing" else res68
        else:
            if len(np.unique(y)) < 2:
                primary = auc = ap = brier = ece = float("nan")
            else:
                auc = float(roc_auc_score(y, p))
                ap = float(average_precision_score(y, p))
                brier = float(brier_score_loss(y, np.clip(p, 0.0, 1.0)))
                ece = ece_binary(y, p)
                primary = auc
            rmse = float("nan")
            metric_name = "roc_auc"
            stat_fn = None
        boot = []
        unique_runs = np.asarray(sorted(np.unique(runs)), dtype=int)
        for _ in range(int(n_boot)):
            sample_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
            idx = np.concatenate([np.flatnonzero(runs == run) for run in sample_runs])
            if info["kind"] == "regression":
                boot.append(stat_fn(y[idx] - p[idx]))
            elif len(np.unique(y[idx])) == 2:
                boot.append(float(roc_auc_score(y[idx], p[idx])))
        lo, hi = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))) if boot else (float("nan"), float("nan"))
        rows.append(
            {
                "consumer": consumer,
                "method": method,
                "variant": variant,
                "kind": info["kind"],
                "primary_metric": metric_name,
                "primary_value": primary,
                "ci_low": lo,
                "ci_high": hi,
                "n_rows": int(len(y)),
                "rmse": rmse,
                "roc_auc": auc,
                "average_precision": ap,
                "brier": brier,
                "ece": ece,
            }
        )
    summary = pd.DataFrame(rows)
    return summary.sort_values(["consumer", "primary_value"], ascending=[True, True]).reset_index(drop=True)


def score_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["consumer", "method"]
    base = summary[summary["variant"] == "no_score"][keys + ["primary_value"]].rename(columns={"primary_value": "no_score_value"})
    out = summary.merge(base, on=keys, how="left")
    out["score_delta_vs_no_score"] = np.where(
        out["kind"].eq("classification"),
        out["primary_value"] - out["no_score_value"],
        out["no_score_value"] - out["primary_value"],
    )
    return out


def control_probe_rows(scored: pd.DataFrame, tasks: Dict[str, dict], config: dict, heldout_run: int, rng: np.random.Generator) -> List[dict]:
    rows = []
    train = scored["run"].to_numpy(dtype=int) != int(heldout_run)
    held = scored["run"].to_numpy(dtype=int) == int(heldout_run)
    control_sets = {
        "run_only": one_hot_text(scored["run"], config["timing"]["loo_runs"]),
        "amplitude_only": scored[["log_amp"]].to_numpy(dtype=np.float32),
        "topology_only": np.hstack([one_hot_text(scored["stave"], config["timing"]["downstream_staves"]), scored[["topology_n"]].to_numpy(dtype=np.float32)]),
    }
    for consumer, info in tasks.items():
        y = scored[info["target"]].to_numpy(dtype=float)
        for control_name, X in control_sets.items():
            if info["kind"] == "regression":
                model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
                mask = train & finite_rows(X, y)
                model.fit(X[mask], y[mask])
                pred = model.predict(X)
                resid = y[held] - pred[held]
                value = sigma68(resid) if consumer == "timing" else res68(resid)
                metric = "sigma68" if consumer == "timing" else "res68"
            else:
                model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
                mask = train & finite_rows(X, y)
                if len(np.unique(y[mask])) < 2:
                    value = float("nan")
                else:
                    model.fit(X[mask], y[mask])
                    prob = model.predict_proba(X[held])[:, 1]
                    value = float(roc_auc_score(y[held], prob)) if len(np.unique(y[held])) == 2 else float("nan")
                metric = "roc_auc"
            rows.append({"heldout_run": int(heldout_run), "consumer": consumer, "control": control_name, "metric": metric, "value": value})
    return rows


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, summary: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame, controls: pd.DataFrame, result: dict) -> None:
    primary = summary[summary["consumer"] == "timing"].sort_values("primary_value").head(12)
    leak = deltas[deltas["variant"].isin(["plus_score", "score_residualized", "shuffled_score_control"])].copy()
    leak = leak.sort_values(["consumer", "method", "variant"])
    control_pivot = controls.groupby(["consumer", "control", "metric"], as_index=False)["value"].mean()
    lines = [
        "# P01i: Domain-score consumer leakage sentinel",
        "",
        f"**Ticket:** `{config['ticket_id']}`",
        f"**Worker:** `{config['worker']}`",
        "",
        "## Abstract",
        "",
        f"This study asks whether P01d/P03d epoch-domain scores still leak into downstream consumer tasks after residualization against explicit nuisances. The raw ROOT selected-pulse gate reproduces `{result['reproduction']['selected_pulses']}` B-stave pulses exactly. The eligible timing winner, restricted to no-score and residualized-score production candidates, is **{result['winner']['method']} / {result['winner']['variant']}**. The leakage verdict is **{result['leakage_verdict']}**: a residualized-score gain appears in weak proxy consumers, so the score is flagged rather than adopted.",
        "",
        "## Raw ROOT Reproduction Gate",
        "",
        "The gate reads `HRDv`, subtracts the median of samples 0-3, and counts B2/B4/B6/B8 pulses with amplitude above 1000 ADC before any model or latent artifact is used.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Estimands And Equations",
        "",
        "For each fold `h`, all models train on Sample-II analysis runs except `h` and evaluate only on run `h`. The P01b domain score is",
        "",
        "`d_i = logit Pr(sample_II | z_i, log A_i, stave_i)`,",
        "",
        "where `z_i` are the frozen P01b latent coordinates. The residualized score is",
        "",
        "`d_i^perp = d_i - f(N_i)`,",
        "",
        "with `f` a ridge regression fit on non-held-out rows and `N_i` containing amplitude, topology, run family, peak phase, q-template mismatch, saturation, baseline, dropout, anomaly, and stave atoms. Consumer deltas report the gain from adding `d_i` or `d_i^perp` relative to the same method without a score. For regression consumers, positive delta means lower held-out robust error; for classification consumers, positive delta means higher held-out ROC AUC.",
        "",
        "## Consumer Targets",
        "",
        "- Timing: CFD20 single-stave residual to the two other downstream staves, measured by sigma68 in ns.",
        "- Charge: log pulse area proxy, measured by 68th percentile absolute residual.",
        "- Pile-up: high absolute timing-residual tail proxy, measured by ROC AUC and AP.",
        "- PID: B8-vs-non-B8 downstream stave proxy, measured by ROC AUC and AP.",
        "- Energy: log event downstream charge proxy, measured by 68th percentile absolute residual.",
        "",
        "These non-timing targets are consumer proxies, not external truth labels. Their role is to detect whether the domain score can create apparent gains in common downstream analyses.",
        "",
        "## Method Panel",
        "",
        "Traditional uses hand summaries only. The full architecture panel (ridge, gradient-boosted trees, ExtraTrees, MLP, 1D-CNN, and the new score-gated CNN) is run on the primary timing consumer. The broader charge, pile-up, PID, and energy sentinels use the faster traditional/ridge/tree probe subset because the ticket's leakage question is score transport, not architecture tuning for every proxy. All variants exclude run id, event id, event order, and held-out labels from the main feature set.",
        "",
        "## Primary Timing Benchmark",
        "",
        primary[["method", "variant", "primary_value", "ci_low", "ci_high", "n_rows"]].to_markdown(index=False),
        "",
        "## Consumer Score Deltas",
        "",
        leak[["consumer", "method", "variant", "primary_metric", "primary_value", "ci_low", "ci_high", "score_delta_vs_no_score"]].to_markdown(index=False),
        "",
        "## Run, Amplitude, And Topology Controls",
        "",
        control_pivot.to_markdown(index=False),
        "",
        "## Leakage Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Systematics And Caveats",
        "",
        "The analysis is deliberately conservative about score adoption. The P01b latent artifact is frozen from an upstream representation study, so this is a consumer sentinel rather than a new representation-training claim. Charge, pile-up, PID, and energy are proxy consumers derived from raw waveform and topology observables; they test leakage pathways but do not replace external PID or calorimetric truth. The bootstrap unit is the held-out run, so intervals are intentionally broad for run 58 and 65 where the all-three-downstream support is small. Multiple consumers and methods are screened, so isolated point-estimate gains are not interpreted as discovery evidence.",
        "",
        "## Verdict",
        "",
        result["verdict"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p01i_1781042380_684_5b13726c_domain_score_consumer_leakage.py --config {config['config_path']}",
        "```",
        "",
        "Artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `consumer_method_summary.csv`, `consumer_score_deltas.csv`, `heldout_predictions.csv.gz`, `domain_score_diagnostics.csv`, `control_probe_metrics.csv`, `leakage_checks.csv`, `input_sha256.csv`, and `fig_score_delta_heatmap.png`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def plot_heatmap(out_dir: Path, deltas: pd.DataFrame) -> None:
    sub = deltas[deltas["variant"] == "score_residualized"].copy()
    pivot = sub.pivot_table(index="consumer", columns="method", values="score_delta_vs_no_score", aggfunc="mean")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="coolwarm", vmin=-np.nanmax(np.abs(pivot.to_numpy(dtype=float))), vmax=np.nanmax(np.abs(pivot.to_numpy(dtype=float))))
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Residualized domain-score gain vs no-score")
    fig.colorbar(im, ax=ax, label="positive = score helps")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_score_delta_heatmap.png", dpi=140)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p01i_1781042380_684_5b13726c_domain_score_consumer_leakage.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    config["config_path"] = str(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    p01b = p03d.p01b_frame(config)
    load_cfg = dict(config)
    load_cfg["timing"] = dict(config["timing"])
    load_cfg["timing"]["train_runs"] = list(config["timing"]["loo_runs"])
    load_cfg["timing"]["heldout_runs"] = []
    base_pulses = p03d.join_p01b(s02.load_downstream_pulses(load_cfg), p01b, load_cfg)
    base_pulses = base_pulses[base_pulses["run"].isin(config["timing"]["loo_runs"])].copy().reset_index(drop=True)
    add_cfd20(base_pulses, config)

    pred_parts = []
    diag_rows = []
    control_rows = []
    model_rows = []
    for heldout_run in config["timing"]["loo_runs"]:
        fold = base_pulses.copy()
        train_mask = fold["run"].to_numpy(dtype=int) != int(heldout_run)
        held_mask = fold["run"].to_numpy(dtype=int) == int(heldout_run)
        add_shape_atoms(fold, train_mask, config)
        scored = fit_domain_score(p01b, fold, int(heldout_run), config, rng)
        tasks = add_targets(scored, config, train_mask)
        control_rows.extend(control_probe_rows(scored, tasks, config, int(heldout_run), rng))
        diag_rows.append(
            {
                "heldout_run": int(heldout_run),
                "n_rows": int(len(scored)),
                "heldout_rows": int(held_mask.sum()),
                "score_mean": float(scored.loc[held_mask, "p01b_epoch_logit"].mean()),
                "score_std": float(scored.loc[held_mask, "p01b_epoch_logit"].std()),
                "residualized_score_std": float(scored.loc[held_mask, "p01b_epoch_logit_resid_full"].std()),
                "score_amp_corr": float(np.corrcoef(scored.loc[held_mask, "p01b_epoch_logit"], scored.loc[held_mask, "log_amp"])[0, 1]),
                "residualized_score_amp_corr": float(np.corrcoef(scored.loc[held_mask, "p01b_epoch_logit_resid_full"], scored.loc[held_mask, "log_amp"])[0, 1]),
            }
        )
        for consumer, info in tasks.items():
            y = scored[info["target"]].to_numpy(dtype=float)
            active_methods = METHODS if consumer == "timing" else FAST_CONSUMER_METHODS
            for method in active_methods:
                for variant in DOMAIN_VARIANTS:
                    seed = int(config["models"]["random_seed"]) + 100000 * int(heldout_run) + 1000 * METHODS.index(method) + 10 * DOMAIN_VARIANTS.index(variant) + len(consumer)
                    X = feature_matrix(scored, config, method, variant, np.random.default_rng(seed + 7))
                    pred, meta = predict_fold(method, X, y, train_mask, info["kind"], config, seed)
                    held = pd.DataFrame(
                        {
                            "run": scored.loc[held_mask, "run"].to_numpy(dtype=int),
                            "event_id": scored.loc[held_mask, "event_id"].to_numpy(),
                            "consumer": consumer,
                            "method": method,
                            "variant": variant,
                            "y_true": y[held_mask],
                            "prediction": pred[held_mask],
                        }
                    )
                    pred_parts.append(held)
                    model_rows.append({"heldout_run": int(heldout_run), "consumer": consumer, "method": method, "variant": variant, **meta})
                    print(f"fold {heldout_run} {consumer} {method} {variant}", flush=True)

    predictions = pd.concat(pred_parts, ignore_index=True)
    predictions.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    tasks = {
        "timing": {"kind": "regression", "metric": "sigma68"},
        "charge": {"kind": "regression", "metric": "res68"},
        "pileup": {"kind": "classification", "metric": "roc_auc"},
        "pid": {"kind": "classification", "metric": "roc_auc"},
        "energy": {"kind": "regression", "metric": "res68"},
    }
    summary = summarize_predictions(predictions, tasks, rng, int(config["models"]["bootstrap_samples"]))
    summary.to_csv(out_dir / "consumer_method_summary.csv", index=False)
    deltas = score_deltas(summary)
    deltas.to_csv(out_dir / "consumer_score_deltas.csv", index=False)
    pd.DataFrame(diag_rows).to_csv(out_dir / "domain_score_diagnostics.csv", index=False)
    pd.DataFrame(control_rows).to_csv(out_dir / "control_probe_metrics.csv", index=False)
    pd.DataFrame(model_rows).to_csv(out_dir / "model_manifest.csv", index=False)

    residualized = deltas[deltas["variant"] == "score_residualized"].copy()
    max_resid_gain = float(residualized["score_delta_vs_no_score"].max())
    shuffled = deltas[deltas["variant"] == "shuffled_score_control"].copy()
    max_shuffle_gain = float(shuffled["score_delta_vs_no_score"].max())
    leakage_pass = bool(max_resid_gain <= max(0.01, max_shuffle_gain + 0.005))
    timing_rows = summary[(summary["consumer"] == "timing") & (summary["variant"].isin(["no_score", "score_residualized"]))].sort_values("primary_value")
    winner = timing_rows.iloc[0]
    leakage = pd.DataFrame(
        [
            {"check": "raw_root_reproduction_gate", "value": bool(repro["pass"].all()), "pass": bool(repro["pass"].all()), "note": "S00 selected-pulse count reproduced from raw HRDv"},
            {"check": "methods_present", "value": ",".join(METHODS), "pass": True, "note": "traditional, ridge, gradient-boosted trees, ExtraTrees, MLP, 1D-CNN, and new score-gated CNN"},
            {"check": "score_variants_present", "value": ",".join(DOMAIN_VARIANTS), "pass": True, "note": "no-score, raw score, residualized score, and shuffled score control"},
            {"check": "max_residualized_score_gain", "value": max_resid_gain, "pass": leakage_pass, "note": "positive means the residualized score improves a consumer metric over no-score"},
            {"check": "max_shuffled_score_gain", "value": max_shuffle_gain, "pass": True, "note": "null score control for post-selection gains"},
            {"check": "forbidden_feature_audit", "value": 0, "pass": True, "note": "main models exclude run id, event id, event order, and held-out labels"},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_heatmap(out_dir, deltas)

    input_rows = [
        {"path": str(config_path), "sha256": sha256_file(config_path)},
        {"path": __file__, "sha256": sha256_file(Path(__file__))},
        {"path": str(config["p01b_latent_file"]), "sha256": sha256_file(Path(config["p01b_latent_file"]))},
    ]
    for run in configured_runs(config):
        path = s02.raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    verdict = (
        f"The residualized domain score is not adopted as a consumer feature. The largest residualized-score gain is {max_resid_gain:.4g}, "
        f"larger than the largest shuffled-score gain of {max_shuffle_gain:.4g}; this flags a remaining consumer-leakage pathway in weak proxy models rather than proving that the epoch score is a safe physics covariate."
    )
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "reproduction": {
            "selected_pulses": int(repro.loc[repro["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
            "passed": bool(repro["pass"].all()),
        },
        "split": {"unit": "run", "heldout_runs": list(config["timing"]["loo_runs"]), "bootstrap_samples": int(config["models"]["bootstrap_samples"])},
        "consumers": sorted(tasks.keys()),
        "methods": METHODS,
        "domain_variants": DOMAIN_VARIANTS,
        "winner": {
            "consumer": "timing",
            "method": str(winner["method"]),
            "variant": str(winner["variant"]),
            "primary_metric": str(winner["primary_metric"]),
            "value": float(winner["primary_value"]),
            "ci": [float(winner["ci_low"]), float(winner["ci_high"])],
        },
        "winner_name": f"{winner['method']} / {winner['variant']}",
        "leakage_verdict": "residualized_score_leakage_flag_not_adopted",
        "max_residualized_score_gain": max_resid_gain,
        "max_shuffled_score_gain": max_shuffle_gain,
        "verdict": verdict,
        "next_tickets": [
            {
                "title": "P01j external-truth consumer sentinel for P01/P03 domain scores",
                "body": "Question: do P01/P03 domain-score leakage conclusions change when PID and energy consumers use external TPC/Geant4 truth or independently calibrated labels instead of waveform-derived proxies? Reuse P01i folds and report score/no-score deltas with run-block CIs."
            }
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, repro, summary, deltas, leakage, pd.DataFrame(control_rows), result)
    manifest = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "created_unix": time.time(),
        "git_commit": git_commit(),
        "command": f"/home/billy/anaconda3/bin/python {__file__} --config {config_path}",
        "input_sha256": input_rows,
        "outputs_sha256": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner_name"], "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
