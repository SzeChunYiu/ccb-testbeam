#!/usr/bin/env python3
"""P08e: decompose a conventional PID-like score against ML/NN probes.

This study is a weak-label null test, not a truth PID measurement.  It starts
from the same raw B-stack ROOT reproduction and duplicate-readout PSTAR label
machinery as P08b, then benchmarks a strong conventional score against a wider
run-heldout panel: ridge, gradient-boosted trees, MLP, 1D-CNN, and a
nuisance-residualized hybrid MLP.
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
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import Ridge, RidgeClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - reported in result.json if unavailable
    torch = None
    nn = None


BASE_SCRIPT = Path("scripts/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py")
STAVE_NAMES = np.asarray(["B2", "B4", "B6", "B8"], dtype=object)
SAMPLE_COLS = ["norm_s{:02d}".format(i) for i in range(18)]
HAND_COLS = [
    "b2_area_over_peak_shape",
    "b2_tail_fraction",
    "b2_late_fraction",
    "b2_early_fraction",
    "b2_final_fraction",
    "b2_peak_sample",
    "b2_width50",
    "b2_width20",
    "b2_max_down_step",
]
HEAD_TO_HEAD_METHODS = [
    "traditional_pid_ridge",
    "waveform_ridge",
    "waveform_gradient_boosted_trees",
    "waveform_mlp",
    "waveform_1d_cnn",
    "nuisance_residual_hybrid_mlp",
]


def load_base_module():
    spec = importlib.util.spec_from_file_location("p08b_base", str(BASE_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


P08B = load_base_module()


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def add_wave_columns(meta: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    out = meta.copy()
    wave = np.asarray(waves[out["wave_index"].to_numpy(dtype=int)], dtype=float)
    wave[~np.isfinite(wave)] = 0.0
    wave = np.clip(wave, -5.0, 5.0)
    for i, col in enumerate(SAMPLE_COLS):
        out[col] = wave[:, i].astype(np.float32)
    return out


def balanced_benchmark_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]))
    max_rows = int(config["benchmark"]["max_rows_per_run_label"])
    groups = set(config["benchmark_groups"])
    meta = meta.loc[meta["group"].isin(groups)]
    pieces: List[np.ndarray] = []
    for (_, _), group in meta.groupby(["run", "weak_label"], sort=True):
        idx = group.index.to_numpy()
        if len(idx):
            pieces.append(rng.choice(idx, size=min(len(idx), max_rows), replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-x))


def ece_score(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    prob = np.clip(prob, 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if mask.any():
            ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(prob[mask].mean()))
    return float(ece)


def purity_at_efficiency(y: np.ndarray, score: np.ndarray, efficiency: float) -> float:
    pos = score[y == 1]
    if len(pos) == 0:
        return float("nan")
    threshold = float(np.quantile(pos, max(0.0, 1.0 - efficiency)))
    selected = score >= threshold
    return float(y[selected].mean()) if selected.any() else float("nan")


def run_block_metrics(
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    seed: int,
    n_boot: int,
    fixed_efficiency: float,
) -> dict:
    score = np.asarray(score, dtype=float)
    valid = np.isfinite(score)
    y = y[valid]
    score = score[valid]
    runs = runs[valid]
    prob = sigmoid(StandardScaler().fit_transform(score.reshape(-1, 1)).ravel())
    rows = {"auc": [], "ap": [], "brier": [], "ece": [], "purity": []}
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        rows["auc"].append(float(roc_auc_score(y[idx], score[idx])))
        rows["ap"].append(float(average_precision_score(y[idx], score[idx])))
        rows["brier"].append(float(brier_score_loss(y[idx], np.clip(prob[idx], 0.0, 1.0))))
        rows["ece"].append(ece_score(y[idx], prob[idx]))
        rows["purity"].append(purity_at_efficiency(y[idx], score[idx], fixed_efficiency))
    out = {
        "roc_auc": safe_auc(y, score),
        "average_precision": safe_ap(y, score),
        "brier": float(brier_score_loss(y, np.clip(prob, 0.0, 1.0))),
        "ece": ece_score(y, prob),
        "purity_at_fixed_efficiency": purity_at_efficiency(y, score, fixed_efficiency),
        "bootstrap_valid": int(len(rows["auc"])),
    }
    for key, values in rows.items():
        clean = [v for v in values if np.isfinite(v)]
        out[key + "_ci"] = [float(x) for x in np.quantile(clean, [0.025, 0.975])] if clean else [None, None]
    return out


def paired_auc_diff(
    y: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    runs: np.ndarray,
    seed: int,
    n_boot: int,
) -> dict:
    valid = np.isfinite(left) & np.isfinite(right)
    y = y[valid]
    left = left[valid]
    right = right[valid]
    runs = runs[valid]
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        sampled = rng.choice(np.unique(runs), size=len(np.unique(runs)), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        diffs.append(float(roc_auc_score(y[idx], right[idx]) - roc_auc_score(y[idx], left[idx])))
    return {
        "right_minus_left_auc": float(safe_auc(y, right) - safe_auc(y, left)),
        "ci": [float(x) for x in np.quantile(diffs, [0.025, 0.975])] if diffs else [None, None],
        "bootstrap_valid": int(len(diffs)),
    }


def q_template_scores(train_waves: np.ndarray, waves: np.ndarray) -> np.ndarray:
    train_waves = np.asarray(train_waves, dtype=float)
    waves = np.asarray(waves, dtype=float)
    train_waves[~np.isfinite(train_waves)] = 0.0
    waves[~np.isfinite(waves)] = 0.0
    train_waves = np.clip(train_waves, -5.0, 5.0)
    waves = np.clip(waves, -5.0, 5.0)
    template = np.median(train_waves, axis=0)
    template = template / max(float(np.linalg.norm(template)), 1e-9)
    norm = np.linalg.norm(waves, axis=1)
    return (waves @ template / np.maximum(norm, 1e-9)).astype(np.float32)


def conventional_frame(df: pd.DataFrame, q_template: np.ndarray) -> pd.DataFrame:
    cols = [
        "depth_idx",
        "multiplicity",
        "topology_code",
        "downstream_selected",
        "downstream_charge_fraction",
        "range_energy_residual_frac_even",
        "calibrated_energy_mev_even",
        "pstar_depth_anchor_mev",
        "saturated_count",
        "b2_saturated",
        "b2_amp",
        "b2_area",
        "even_total_charge",
        "b4_amp",
        "b6_amp",
        "b8_amp",
        "b4_area",
        "b6_area",
        "b8_area",
    ]
    out = df[cols + HAND_COLS].copy()
    for col in [
        "calibrated_energy_mev_even",
        "pstar_depth_anchor_mev",
        "b2_amp",
        "b2_area",
        "even_total_charge",
        "b4_amp",
        "b6_amp",
        "b8_amp",
        "b4_area",
        "b6_area",
        "b8_area",
    ]:
        out[col] = np.log1p(np.maximum(out[col].to_numpy(dtype=float), 0.0))
    out["q_template"] = q_template
    return out


def nuisance_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "depth_idx",
            "multiplicity",
            "topology_code",
            "downstream_selected",
            "downstream_charge_fraction",
            "even_total_charge",
            "b2_area",
            "event_index",
        ]
    ].copy()
    for col in ["even_total_charge", "b2_area"]:
        out[col] = np.log1p(np.maximum(out[col].to_numpy(dtype=float), 0.0))
    event = out["event_index"].to_numpy(dtype=float)
    out["event_fraction"] = (event - event.min()) / max(float(event.max() - event.min()), 1.0)
    out = out.drop(columns=["event_index"])
    group_dummies = pd.get_dummies(df["group"].astype(str), prefix="group")
    return pd.concat([out.reset_index(drop=True), group_dummies.reset_index(drop=True)], axis=1)


def fit_ridge_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    clf = make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0, class_weight="balanced"))
    clf.fit(train_x, train_y)
    return clf.decision_function(test_x).astype(float)


def fit_hgb_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, params: dict, seed: int) -> np.ndarray:
    clf = HistGradientBoostingClassifier(
        max_iter=int(params.get("n_estimators", params.get("max_iter", 45))),
        max_leaf_nodes=int(params.get("max_leaf_nodes", 15)),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        learning_rate=float(params.get("learning_rate", 0.08)),
        l2_regularization=float(params.get("l2_regularization", 0.05)),
        random_state=seed,
    )
    weight = compute_sample_weight(class_weight="balanced", y=train_y)
    clf.fit(train_x, train_y, sample_weight=weight)
    return clf.predict_proba(test_x)[:, 1].astype(float)


def fit_mlp_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, seed: int, max_iter: int) -> np.ndarray:
    clf = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=(48, 24),
            activation="relu",
            solver="adam",
            alpha=1.0e-3,
            learning_rate_init=2.0e-3,
            max_iter=max_iter,
            early_stopping=True,
            n_iter_no_change=8,
            random_state=seed,
        ),
    )
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1].astype(float)


class TinyCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(16, 1))

    def forward(self, x):
        return self.head(self.net(x)).squeeze(1)


def fit_cnn_score(train_waves: np.ndarray, train_y: np.ndarray, test_waves: np.ndarray, seed: int, epochs: int) -> np.ndarray:
    if torch is None:
        return np.full(len(test_waves), np.nan, dtype=float)
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TinyCNN().to(device)
    x = torch.tensor(train_waves[:, None, :], dtype=torch.float32, device=device)
    y = torch.tensor(train_y.astype(np.float32), dtype=torch.float32, device=device)
    xt = torch.tensor(test_waves[:, None, :], dtype=torch.float32, device=device)
    pos = float(train_y.sum())
    neg = float(len(train_y) - train_y.sum())
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / max(pos, 1.0)], device=device))
    opt = torch.optim.Adam(model.parameters(), lr=2.0e-3, weight_decay=1.0e-4)
    batch = min(512, len(train_y))
    gen = torch.Generator(device=device)
    gen.manual_seed(seed)
    model.train()
    for _ in range(int(epochs)):
        order = torch.randperm(len(train_y), generator=gen, device=device)
        for start in range(0, len(train_y), batch):
            idx = order[start : start + batch]
            opt.zero_grad()
            loss = loss_fn(model(x[idx]), y[idx])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        score = torch.sigmoid(model(xt)).detach().cpu().numpy()
    return score.astype(float)


def residualized_wave_features(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    train_waves: np.ndarray,
    test_waves: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    train_nuis = nuisance_frame(train_df)
    test_nuis = nuisance_frame(test_df).reindex(columns=train_nuis.columns, fill_value=0)
    scaler = StandardScaler()
    train_z = scaler.fit_transform(train_nuis.to_numpy(dtype=float))
    test_z = scaler.transform(test_nuis.to_numpy(dtype=float))
    reg = Ridge(alpha=10.0)
    reg.fit(train_z, train_waves)
    train_resid = train_waves - reg.predict(train_z)
    test_resid = test_waves - reg.predict(test_z)
    train_hand = train_df[HAND_COLS].to_numpy(dtype=float)
    test_hand = test_df[HAND_COLS].to_numpy(dtype=float)
    return np.column_stack([train_resid, train_hand]), np.column_stack([test_resid, test_hand])


def finite_matrix(x: np.ndarray) -> np.ndarray:
    out = np.asarray(x, dtype=float)
    out[~np.isfinite(out)] = 0.0
    out = np.clip(out, -1.0e6, 1.0e6)
    return out


def build_benchmark(waves_all: np.ndarray, meta_all: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    sample_idx = balanced_benchmark_indices(meta_all, config)
    meta = add_wave_columns(meta_all.loc[sample_idx].reset_index(drop=True), waves_all)
    waves = np.asarray(waves_all[meta["wave_index"].to_numpy(dtype=int)], dtype=float)
    waves[~np.isfinite(waves)] = 0.0
    waves = np.clip(waves, -5.0, 5.0)
    y = meta["weak_label"].to_numpy(dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    seed = int(config["benchmark"]["random_seed"])
    n_boot = int(config["benchmark"]["bootstrap_replicates"])
    fixed_eff = float(config["benchmark"]["fixed_efficiency"])
    min_train = int(config["benchmark"]["min_train_class_rows"])
    min_test = int(config["benchmark"]["min_test_class_rows"])
    hgb_params = config["benchmark"]["ml_grid"][0]
    mlp_max_iter = int(config["benchmark"].get("mlp_max_iter", 70))
    cnn_epochs = int(config["benchmark"].get("cnn_epochs", 5))

    scores: Dict[str, np.ndarray] = {
        name: np.full(len(meta), np.nan, dtype=float)
        for name in HEAD_TO_HEAD_METHODS
        + [
            "sentinel_charge_only_ridge",
            "sentinel_depth_topology_only_ridge",
            "sentinel_group_event_order_ridge",
            "sentinel_shuffled_label_gbt",
        ]
    }
    fold_id = np.full(len(meta), "", dtype=object)
    fold_rows = []

    for fold_number, run in enumerate(np.unique(runs), start=1):
        test = runs == run
        train = ~test
        train_counts = np.bincount(y[train], minlength=2)
        test_counts = np.bincount(y[test], minlength=2)
        if train_counts.min() < min_train or test_counts.min() < min_test:
            continue

        train_df = meta.loc[train].reset_index(drop=True)
        test_df = meta.loc[test].reset_index(drop=True)
        train_waves = waves[train]
        test_waves = waves[test]
        train_y = y[train]
        q_train = q_template_scores(train_waves, train_waves)
        q_test = q_template_scores(train_waves, test_waves)
        trad_train = conventional_frame(train_df, q_train).to_numpy(dtype=float)
        trad_test = conventional_frame(test_df, q_test).to_numpy(dtype=float)

        train_samples = finite_matrix(train_df[SAMPLE_COLS].to_numpy(dtype=float))
        test_samples = finite_matrix(test_df[SAMPLE_COLS].to_numpy(dtype=float))
        wave_train = finite_matrix(np.column_stack([train_samples, train_df[HAND_COLS].to_numpy(dtype=float)]))
        wave_test = finite_matrix(np.column_stack([test_samples, test_df[HAND_COLS].to_numpy(dtype=float)]))
        resid_train, resid_test = residualized_wave_features(train_df, test_df, train_waves, test_waves)

        scores["traditional_pid_ridge"][test] = fit_ridge_score(finite_matrix(trad_train), train_y, finite_matrix(trad_test))
        scores["waveform_ridge"][test] = fit_ridge_score(wave_train, train_y, wave_test)
        scores["waveform_gradient_boosted_trees"][test] = fit_hgb_score(wave_train, train_y, wave_test, hgb_params, seed + fold_number)
        scores["waveform_mlp"][test] = fit_mlp_score(wave_train, train_y, wave_test, seed + 100 + fold_number, mlp_max_iter)
        scores["waveform_1d_cnn"][test] = fit_cnn_score(train_waves, train_y, test_waves, seed + 200 + fold_number, cnn_epochs)
        scores["nuisance_residual_hybrid_mlp"][test] = fit_mlp_score(resid_train, train_y, resid_test, seed + 300 + fold_number, mlp_max_iter)

        charge_cols = ["range_energy_residual_frac_even", "calibrated_energy_mev_even", "even_total_charge", "b2_area"]
        charge_train = train_df[charge_cols].copy()
        charge_test = test_df[charge_cols].copy()
        for col in ["calibrated_energy_mev_even", "even_total_charge", "b2_area"]:
            charge_train[col] = np.log1p(np.maximum(charge_train[col].to_numpy(dtype=float), 0.0))
            charge_test[col] = np.log1p(np.maximum(charge_test[col].to_numpy(dtype=float), 0.0))
        scores["sentinel_charge_only_ridge"][test] = fit_ridge_score(finite_matrix(charge_train.to_numpy(dtype=float)), train_y, finite_matrix(charge_test.to_numpy(dtype=float)))

        depth_cols = ["depth_idx", "multiplicity", "topology_code", "downstream_selected", "downstream_charge_fraction"]
        scores["sentinel_depth_topology_only_ridge"][test] = fit_ridge_score(
            finite_matrix(train_df[depth_cols].to_numpy(dtype=float)),
            train_y,
            finite_matrix(test_df[depth_cols].to_numpy(dtype=float)),
        )

        train_ge = nuisance_frame(train_df)[["event_fraction"]].copy()
        test_ge = nuisance_frame(test_df)[["event_fraction"]].copy()
        group_train = pd.get_dummies(train_df["group"].astype(str), prefix="group")
        group_test = pd.get_dummies(test_df["group"].astype(str), prefix="group").reindex(columns=group_train.columns, fill_value=0)
        scores["sentinel_group_event_order_ridge"][test] = fit_ridge_score(
            finite_matrix(np.column_stack([group_train.to_numpy(dtype=float), train_ge.to_numpy(dtype=float)])),
            train_y,
            finite_matrix(np.column_stack([group_test.to_numpy(dtype=float), test_ge.to_numpy(dtype=float)])),
        )

        shuffled_y = train_y.copy()
        np.random.default_rng(seed + 9000 + fold_number).shuffle(shuffled_y)
        scores["sentinel_shuffled_label_gbt"][test] = fit_hgb_score(wave_train, shuffled_y, wave_test, hgb_params, seed + 400 + fold_number)

        fold_id[test] = "run{}".format(int(run))
        fold_rows.append(
            {
                "heldout_run": int(run),
                "train_rows": int(train.sum()),
                "test_rows": int(test.sum()),
                "train_positive": int(train_y.sum()),
                "test_positive": int(y[test].sum()),
                "pca_variance_4": None,
            }
        )
        print("fold {:02d}: heldout_run={} train={} test={}".format(fold_number, int(run), int(train.sum()), int(test.sum())), flush=True)

    valid = fold_id != ""
    y_eval = y[valid]
    runs_eval = runs[valid]
    meta_eval = meta.loc[valid].copy()
    meta_eval["fold_id"] = fold_id[valid]

    metric_rows = []
    for i, (method, score_all) in enumerate(scores.items()):
        score = score_all[valid]
        metrics = run_block_metrics(y_eval, score, runs_eval, seed + 10 + i, n_boot, fixed_eff)
        family = "head_to_head" if method in HEAD_TO_HEAD_METHODS else "sentinel"
        row = {"method": method, "family": family, "n_events": int(np.isfinite(score).sum()), "n_runs": int(len(np.unique(runs_eval)))}
        row.update(metrics)
        metric_rows.append(row)
        meta_eval[method] = score
    metrics_df = pd.DataFrame(metric_rows)
    winner_row = metrics_df.loc[metrics_df["method"].isin(HEAD_TO_HEAD_METHODS)].sort_values("roc_auc", ascending=False).iloc[0]
    winner = {
        "method": str(winner_row["method"]),
        "selection_metric": "run-heldout ROC AUC among non-sentinel head-to-head methods",
        "roc_auc": float(winner_row["roc_auc"]),
        "roc_auc_ci": [winner_row["auc_ci"][0], winner_row["auc_ci"][1]],
        "caveat": "Winner is for calibrated weak-label discrimination only; it is not a truth PID adoption claim.",
    }
    pairwise_rows = []
    trad_score = scores["traditional_pid_ridge"][valid]
    for method in HEAD_TO_HEAD_METHODS:
        if method == "traditional_pid_ridge":
            continue
        diff = paired_auc_diff(y_eval, trad_score, scores[method][valid], runs_eval, seed + 1000 + len(pairwise_rows), n_boot)
        pairwise_rows.append({"left": "traditional_pid_ridge", "right": method, **diff})
    pairwise = pd.DataFrame(pairwise_rows)

    fold_counts = meta_eval.groupby(["run", "weak_label_name"]).size().reset_index(name="n")
    pd.DataFrame(fold_rows).to_csv(out_dir / "fold_audit.csv", index=False)
    fold_counts.to_csv(out_dir / "heldout_run_label_counts.csv", index=False)
    meta_eval[
        [
            "run",
            "event_index",
            "weak_label",
            "weak_label_name",
            "depth_idx",
            "range_energy_residual_frac_odd",
            "range_energy_residual_frac_even",
            "downstream_selected",
            "downstream_charge_fraction",
        ]
        + HEAD_TO_HEAD_METHODS
    ].to_csv(out_dir / "heldout_predictions.csv.gz", index=False)

    details = {
        "benchmark_rows_after_balancing": int(len(meta)),
        "evaluated_rows": int(valid.sum()),
        "evaluated_runs": [int(run) for run in np.unique(runs_eval)],
        "skipped_runs": [int(run) for run in sorted(set(np.unique(runs).tolist()) - set(np.unique(runs_eval).tolist()))],
        "positive_fraction": float(y_eval.mean()),
        "winner": winner,
        "torch_available": bool(torch is not None),
        "cnn_device": str(torch.device("cuda" if torch is not None and torch.cuda.is_available() else "cpu")) if torch is not None else "unavailable",
    }
    return metrics_df, pairwise, fold_counts, meta, details


def output_manifest(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def fmt_ci(value: float, ci: Sequence[float]) -> str:
    if ci[0] is None or ci[1] is None:
        return "{:.3f} [NA, NA]".format(value)
    return "{:.3f} [{:.3f}, {:.3f}]".format(value, float(ci[0]), float(ci[1]))


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    reproduction: pd.DataFrame,
    metrics: pd.DataFrame,
    pairwise: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    head = metrics[metrics["family"] == "head_to_head"].copy()
    sent = metrics[metrics["family"] == "sentinel"].copy()
    eff = 100 * float(config["benchmark"]["fixed_efficiency"])
    table_rows = []
    for _, row in head.sort_values("roc_auc", ascending=False).iterrows():
        table_rows.append(
            "| {method} | {auc} | {ap} | {brier} | {ece:.3f} | {purity} |".format(
                method=row["method"],
                auc=fmt_ci(row["roc_auc"], row["auc_ci"]),
                ap=fmt_ci(row["average_precision"], row["ap_ci"]),
                brier=fmt_ci(row["brier"], row["brier_ci"]),
                ece=row["ece"],
                purity=fmt_ci(row["purity_at_fixed_efficiency"], row["purity_ci"]),
            )
        )
    pair_rows = []
    for _, row in pairwise.iterrows():
        pair_rows.append(
            "| {right} | {delta:.3f} | [{lo:.3f}, {hi:.3f}] | {n} |".format(
                right=row["right"],
                delta=row["right_minus_left_auc"],
                lo=row["ci"][0],
                hi=row["ci"][1],
                n=int(row["bootstrap_valid"]),
            )
        )
    sentinel_rows = []
    for _, row in sent.sort_values("roc_auc", ascending=False).iterrows():
        sentinel_rows.append(
            "| {method} | {auc} | {ap} | {ece:.3f} |".format(
                method=row["method"],
                auc=fmt_ci(row["roc_auc"], row["auc_ci"]),
                ap=fmt_ci(row["average_precision"], row["ap_ci"]),
                ece=row["ece"],
            )
        )
    leakage_rows = []
    for _, row in leakage.iterrows():
        leakage_rows.append("| {probe} | {value} | {interpretation} |".format(**row))

    report = """# P08e: conventional PID score decomposition null

**Ticket:** {ticket_id}  
**Worker:** {worker}  
**Input:** raw B-stack `HRDv` ROOT from `{raw_root_dir}`  
**Status:** weak-label decomposition only; no truth PID adoption claim.

## Abstract
P08e asks whether the strong conventional P08b charge-current/depth PID-like
score is an independent pulse-shape or range-energy signal, or whether it is a
support and calibration closure that waveform ML should not reproduce as PID.
The study reproduces the raw B-stack selected-pulse count exactly, rebuilds the
P08b duplicate-readout PSTAR/depth residual labels, and benchmarks a conventional
ridge score against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new
nuisance-residualized hybrid MLP under leave-one-run-out evaluation. The winner
stored in `result.json` is **{winner_method}** with ROC AUC {winner_auc:.3f}
[{winner_lo:.3f}, {winner_hi:.3f}], but this is explicitly a weak-label
winner, not a particle-ID truth result.

## Raw ROOT Reproduction
The analysis begins with a full raw ROOT scan over the configured B-stack run
families. Each event reads `HRDv`, estimates the per-channel baseline as the
median of samples 0--3, subtracts it, and selects B2/B4/B6/B8 pulses with
max corrected even-readout amplitude above 1000 ADC. The reproduced values are:

{reproduction_table}

The exact zero-delta reproduction is a hard gate. If this table fails, the
script refuses to run the weak-label benchmark.

## Weak Label and Conventional Score
Let `Q_odd` and `Q_even` be the positive duplicate-readout and even-readout
charge sums over selected B-stack staves, and let `d` be the deepest selected
stave. PSTAR tabulates a monotone mapping from range `r_d` to kinetic energy
anchor `E_d`. On calibration runs only, a per-depth charge quantile map

`C_d(log Q) = E_low,d + F_d(log Q) (E_high,d - E_low,d)`

is fitted, where `F_d` is the empirical charge CDF inside depth atom `d`. The
odd-readout residual

`rho_odd = (C_d(log Q_odd) - E_d) / max(E_d, 1 MeV)`

defines the weak label by taking the bottom and top within-run/depth quantiles.
The even-readout analog `rho_even` is allowed in the conventional score only as
a duplicate-readout control. The conventional feature vector contains tail/area
shape summaries, area/peak-like features, train-fold template quality
`q_template`, B2--B8 amplitude and charge vectors, PSTAR depth anchors,
topology/depth, saturation flags, and event support variables. It is fitted as
a class-balanced ridge discriminant:

`argmin_w ||y - Xw||_2^2 + alpha ||w||_2^2`.

## ML/NN Panel
All methods are trained with no held-out-run rows in fitting, template
construction, or nuisance residualization:

- `waveform_ridge`: ridge classifier on normalized 18-sample B2 waveform
  samples and hand-shape features.
- `waveform_gradient_boosted_trees`: histogram gradient boosting on the same
  waveform feature panel.
- `waveform_mlp`: two-hidden-layer MLP on the same feature panel.
- `waveform_1d_cnn`: compact 1D convolutional network on normalized B2
  samples only.
- `nuisance_residual_hybrid_mlp`: new architecture for this null test. A
  train-fold ridge model first predicts each waveform sample from nuisance
  support variables (depth, topology, charge, event order, run family). The MLP
  receives waveform residuals plus hand-shape features, so its success measures
  residual pulse-shape information after support removal.

## Metrics and Bootstrap
Metrics are evaluated on out-of-fold rows and bootstrapped by resampling held-out
runs with replacement. Reported intervals are 95% percentile intervals over
{n_boot} run-block replicates. Calibration is summarized by Brier score and
10-bin expected calibration error (ECE). Purity is computed at fixed {eff:.0f}%
positive-label efficiency using the global out-of-fold score threshold.

| method | ROC AUC | AP | Brier | ECE | purity at {eff:.0f}% efficiency |
|---|---:|---:|---:|---:|---:|
{head_table}

## ML Minus Conventional
Positive deltas favor the named ML/NN method over the conventional ridge score.

| method | AUC delta vs traditional | 95% CI | bootstrap draws |
|---|---:|---:|---:|
{pair_table}

## Nuisance and Leakage Sentinels
The following probes deliberately restrict information channels. A high
charge-only score means the weak label is dominated by duplicate-readout
charge-scale closure; a high depth/topology score means P08a-style topology
leakage persists; shuffled labels test software leakage.

| probe | ROC AUC | AP | ECE |
|---|---:|---:|---:|
{sentinel_table}

Interpretation ledger:

| probe | value | interpretation |
|---|---:|---|
{leakage_table}

## Systematics
The dominant systematic is label circularity: the positive class is a quantile
of the odd duplicate-readout calibrated residual, and the even readout can share
real charge-scale drift. The leave-one-run split prevents row leakage but cannot
turn duplicate-readout closure into truth PID. The depth/topology sentinel
separates P08a-style terminal/penetrating leakage from the calibrated residual
label. The nuisance-residual hybrid tests whether waveform shape survives after
support variables predict the samples; if it loses to charge/support sentinels,
that is evidence against a standalone B2 waveform PID claim. The CNN is compact
by design to avoid fitting a high-capacity classifier to a weak-label nuisance.

## Caveats
No particle truth labels are available in these B-stack ROOT files, so no method
is adopted as PID. Bootstrap intervals are run-block intervals over the available
run families, not detector-configuration universes. Current is represented by
run family and event-order proxies because independent scaler-current records
are not present in the raw `HRDv` tree used here. The conventional score is
allowed to be strong; if it wins, the result supports the null that the weak PID
axis is already explained by calibration and support variables. If an ML method
wins, the sentinels decide whether that is residual waveform shape or nuisance
leakage.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08e_1781055407_547_08364d02_conventional_pid_score_decomposition_null.py --config configs/p08e_1781055407_547_08364d02_conventional_pid_score_decomposition_null.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`,
`ml_minus_traditional.csv`, `leakage_checks.csv`, `fold_audit.csv`,
`heldout_run_label_counts.csv`, `benchmark_balanced_counts.csv`, and
`heldout_predictions.csv.gz`.
""".format(
        ticket_id=config["ticket_id"],
        worker=config["worker"],
        raw_root_dir=result["raw_root_dir"],
        reproduction_table=reproduction.to_markdown(index=False),
        winner_method=result["winner"]["method"],
        winner_auc=result["winner"]["roc_auc"],
        winner_lo=result["winner"]["roc_auc_ci"][0],
        winner_hi=result["winner"]["roc_auc_ci"][1],
        n_boot=int(config["benchmark"]["bootstrap_replicates"]),
        eff=eff,
        head_table="\n".join(table_rows),
        pair_table="\n".join(pair_rows),
        sentinel_table="\n".join(sentinel_rows),
        leakage_table="\n".join(leakage_rows),
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p08e_1781055407_547_08364d02_conventional_pid_score_decomposition_null.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    raw_dir = P08B.resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    anchors = P08B.geometry_anchors(config)
    waves, meta, counts_by_run, counts_by_group = P08B.scan_raw(config, raw_dir)
    reproduction = P08B.reproduction_table(config, counts_by_group)
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw reproduction failed; refusing to continue")

    labeled, label_support, calibration = P08B.add_calibrated_labels(meta, config, anchors)
    label_support.to_csv(out_dir / "calibrated_label_support.csv", index=False)
    labeled.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "weak_label_counts_by_run.csv", index=False)
    if labeled.empty:
        raise RuntimeError("No calibrated weak-label support")

    metrics, pairwise, fold_counts, benchmark_meta, details = build_benchmark(waves, labeled, config, out_dir)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    pairwise.to_csv(out_dir / "ml_minus_traditional.csv", index=False)
    benchmark_meta.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "benchmark_balanced_counts.csv", index=False)

    input_rows = []
    for run in P08B.configured_runs(config):
        path = P08B.raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    sent = metrics[metrics["family"] == "sentinel"].copy()
    leakage_rows = []
    for _, row in sent.iterrows():
        if row["method"] == "sentinel_charge_only_ridge":
            interp = "Allowed even-readout charge closure probe; high AUC means the weak label is mainly charge-scale support."
        elif row["method"] == "sentinel_depth_topology_only_ridge":
            interp = "P08a-style topology/depth probe; high AUC means terminal/penetrating topology still explains the weak axis."
        elif row["method"] == "sentinel_group_event_order_ridge":
            interp = "Run-family/event-order current proxy; high AUC indicates run-condition drift."
        else:
            interp = "Shuffled-label software leakage guard; should be near chance."
        leakage_rows.append({"probe": row["method"], "value": "{:.3f}".format(row["roc_auc"]), "interpretation": interp})
    leakage = pd.DataFrame(leakage_rows)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    winner = details["winner"]
    result = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "table": reproduction.to_dict(orient="records"),
        },
        "calibrated_label_definition": {
            "weak_label": config["weak_label"],
            "calibration": calibration,
        },
        "calibrated_label_support": {
            "n_atoms": int(len(label_support)),
            "n_labeled_rows": int(len(labeled)),
            "atom_columns": ["run", "depth_idx"],
        },
        "winner": winner,
        "head_to_head_methods": metrics[metrics["family"] == "head_to_head"].to_dict(orient="records"),
        "sentinels": metrics[metrics["family"] == "sentinel"].to_dict(orient="records"),
        "ml_minus_traditional": pairwise.to_dict(orient="records"),
        "primary_interpretation": (
            "This is a conventional PID score decomposition null. The named winner is a weak-label "
            "benchmark winner only; adoption is blocked without truth labels and by the nuisance "
            "sentinel pattern documented in REPORT.md."
        ),
        "benchmark": details,
        "next_tickets": [],
        "input_file_count": int(len(input_sha)),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, reproduction, metrics, pairwise, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p08e_1781055407_547_08364d02_conventional_pid_score_decomposition_null.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "commands": [
            "/home/billy/anaconda3/bin/python scripts/p08e_1781055407_547_08364d02_conventional_pid_score_decomposition_null.py --config configs/p08e_1781055407_547_08364d02_conventional_pid_score_decomposition_null.json"
        ],
        "random_seeds": {
            "benchmark": int(config["benchmark"]["random_seed"]),
            "bootstrap_replicates": int(config["benchmark"]["bootstrap_replicates"]),
        },
        "git_commit_at_run": git_commit(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": getattr(torch, "__version__", None) if torch is not None else None,
        },
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "artifacts": output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(metrics.to_string(index=False))
    print(pairwise.to_string(index=False))
    print("DONE in {:.1f}s -> {}".format(time.time() - t0, out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
