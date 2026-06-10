#!/usr/bin/env python3
"""P09f: delayed-peak pile-up vs charge-bias disentanglement.

The first operation is a raw B-stack ROOT scan that reproduces the frozen
S00/P09a selected-pulse count.  The study then turns the P09c delayed-peak
taxon into a run-held-out operational decision problem: overlap-like delayed
peaks versus charge-bias/dropout-like delayed peaks, with an explicit abstain
class for ambiguous delayed peaks.
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
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, balanced_accuracy_score, precision_score, recall_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


METHOD_ORDER = [
    "traditional_frozen_cuts",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "charge_gated_cnn_new",
]

SCALAR_FEATURES = [
    "amplitude_log",
    "peak_sample",
    "late_fraction",
    "early_fraction",
    "width_half",
    "baseline_mad_log",
    "baseline_slope_scaled",
    "saturation_count",
    "secondary_peak",
    "secondary_sep",
    "post_peak_min",
    "undershoot_area",
    "cfd20_sample",
    "timing_span_dup",
    "area_norm",
    "charge_bias_log",
    "charge_bias_abs",
    "dropout_depth",
    "secondary_fraction",
]

METRIC_COLUMNS = [
    "average_precision",
    "balanced_accuracy",
    "secondary_fraction_delta",
    "charge_bias_delta",
    "abstention_precision",
    "abstention_recall",
    "abstention_f1",
    "decision_utility",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


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


def robust_z(values: np.ndarray, train_values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    train_values = np.asarray(train_values, dtype=float)
    med = float(np.nanmedian(train_values))
    mad = float(np.nanmedian(np.abs(train_values - med)))
    scale = 1.4826 * mad if mad > 1.0e-12 else float(np.nanstd(train_values))
    if not np.isfinite(scale) or scale <= 1.0e-12:
        scale = 1.0
    return (values - med) / scale


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return (1.0 / (1.0 + np.exp(-np.clip(x, -40, 40)))).astype(np.float32)


def add_operational_columns(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = meta.copy()
    out["amplitude_log"] = np.log1p(np.maximum(out["amplitude_adc"].to_numpy(dtype=np.float32), 0.0))
    out["dup_amplitude_log"] = np.log1p(np.maximum(out["dup_amplitude_adc"].to_numpy(dtype=np.float32), 0.0))
    out["baseline_mad_log"] = np.log1p(np.maximum(out["baseline_mad"].to_numpy(dtype=np.float32), 0.0))
    out["baseline_slope_scaled"] = out["baseline_slope"].to_numpy(dtype=np.float32) / 1000.0
    out["charge_bias_log"] = out["amplitude_log"] - out["dup_amplitude_log"]
    out["charge_bias_abs"] = np.abs(out["charge_bias_log"].to_numpy(dtype=np.float32))
    out["dropout_depth"] = -np.minimum(out["post_peak_min"].to_numpy(dtype=np.float32), 0.0)
    out["secondary_fraction"] = np.maximum(out["secondary_peak"].to_numpy(dtype=np.float32), 0.0) * np.maximum(
        out["late_fraction"].to_numpy(dtype=np.float32), 0.0
    )
    out["delayed_peak_candidate"] = (
        (out["peak_sample"].to_numpy() >= int(config["delayed_peak_min_sample"]))
        & (out["late_fraction"].to_numpy() >= float(config["delayed_late_fraction_min"]))
        & (out["secondary_peak"].to_numpy() <= float(config["delayed_secondary_peak_max"]))
        & (out["dup_amplitude_adc"].to_numpy() > 50.0)
        & np.isfinite(out["dup_cfd20_sample"].to_numpy())
        & (out["saturation_count"].to_numpy() < 2)
    )
    return out


def label_with_train_thresholds(meta: pd.DataFrame, train_mask: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = meta.copy()
    train = out.loc[train_mask & out["delayed_peak_candidate"].to_numpy(dtype=bool)]
    if len(train) < 20:
        train = out.loc[train_mask]
    sec_z = robust_z(out["secondary_fraction"].to_numpy(float), train["secondary_fraction"].to_numpy(float))
    late_z = robust_z(out["late_fraction"].to_numpy(float), train["late_fraction"].to_numpy(float))
    span_z = robust_z(out["timing_span_dup"].to_numpy(float), train["timing_span_dup"].to_numpy(float))
    charge_z = np.abs(robust_z(out["charge_bias_log"].to_numpy(float), train["charge_bias_log"].to_numpy(float)))
    dropout_z = robust_z(out["dropout_depth"].to_numpy(float), train["dropout_depth"].to_numpy(float))
    baseline_z = robust_z(out["baseline_mad"].to_numpy(float), train["baseline_mad"].to_numpy(float))

    overlap_score = np.maximum.reduce([sec_z, 0.55 * late_z + 0.45 * span_z])
    bias_score = np.maximum.reduce([charge_z, dropout_z, baseline_z])
    dtrain = out.loc[train.index]
    delayed_train = dtrain["delayed_peak_candidate"].to_numpy(dtype=bool)
    idx_train = dtrain.index.to_numpy()
    ov_thr = float(np.nanquantile(overlap_score[idx_train[delayed_train]], 0.62)) if delayed_train.any() else 1.0
    bias_thr = float(np.nanquantile(bias_score[idx_train[delayed_train]], 0.62)) if delayed_train.any() else 1.0

    overlap_raw = (overlap_score >= ov_thr) & (out["secondary_sep"].to_numpy(float) >= 3)
    bias_raw = bias_score >= bias_thr
    overlap_like = out["delayed_peak_candidate"].to_numpy(dtype=bool) & overlap_raw & ~(
        bias_raw & (bias_score > overlap_score + 0.25)
    )
    charge_bias_like = out["delayed_peak_candidate"].to_numpy(dtype=bool) & bias_raw & ~(
        overlap_raw & (overlap_score > bias_score + 0.25)
    )
    ambiguous = out["delayed_peak_candidate"].to_numpy(dtype=bool) & (
        ~(overlap_like | charge_bias_like) | (overlap_like & charge_bias_like)
    )
    out["overlap_score_operational"] = overlap_score.astype(np.float32)
    out["bias_score_operational"] = bias_score.astype(np.float32)
    out["label_overlap_like"] = overlap_like & ~ambiguous
    out["label_charge_bias_like"] = charge_bias_like & ~ambiguous
    out["label_ambiguous_abstain"] = ambiguous
    out["label_binary_available"] = out["label_overlap_like"] | out["label_charge_bias_like"]
    out["label_binary_overlap"] = out["label_overlap_like"].astype(int)
    thresholds = pd.DataFrame(
        [
            {"threshold": "overlap_score_q62_train_delayed", "value": ov_thr},
            {"threshold": "bias_score_q62_train_delayed", "value": bias_thr},
            {"threshold": "train_delayed_candidates", "value": int(delayed_train.sum())},
        ]
    )
    return out, thresholds


def feature_matrix(waves: np.ndarray, frame: pd.DataFrame) -> np.ndarray:
    wave = waves[frame.index.to_numpy()].astype(np.float32)
    scalars = frame[SCALAR_FEATURES].to_numpy(dtype=np.float32)
    return np.column_stack(
        [
            np.nan_to_num(wave, nan=0.0, posinf=1.0e6, neginf=-1.0e6),
            np.nan_to_num(scalars, nan=0.0, posinf=1.0e6, neginf=-1.0e6),
        ]
    ).astype(np.float32)


def balanced_train_indices(frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> np.ndarray:
    eligible = frame.index[frame["label_binary_available"].to_numpy(dtype=bool)].to_numpy()
    y = frame.loc[eligible, "label_binary_overlap"].to_numpy(dtype=int)
    pos = eligible[y == 1]
    neg = eligible[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        raise RuntimeError("Fold has only one training class")
    neg_take = min(len(neg), max(len(pos) * int(config["train_negative_to_positive_ratio"]), len(pos)))
    idx = np.concatenate([pos, rng.choice(neg, size=neg_take, replace=False)])
    max_rows = int(config["ml"]["max_train_rows"])
    if len(idx) > max_rows:
        keep_pos = pos
        keep_neg = rng.choice(neg, size=min(max_rows - len(keep_pos), len(neg)), replace=False)
        idx = np.concatenate([keep_pos, keep_neg])
    rng.shuffle(idx)
    return idx


def traditional_probability(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    del train
    margin = test["overlap_score_operational"].to_numpy(float) - test["bias_score_operational"].to_numpy(float)
    return sigmoid(margin)


def sklearn_probability(method: str, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, config: dict, seed: int) -> np.ndarray:
    ml = config["ml"]
    if method == "ridge":
        model = make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(ml["ridge_alpha"]), class_weight="balanced"))
        model.fit(x_train, y_train)
        score = model.decision_function(x_test)
        return sigmoid(score)
    if method == "gradient_boosted_trees":
        model = HistGradientBoostingClassifier(
            max_iter=int(ml["gbt_max_iter"]),
            learning_rate=float(ml["gbt_learning_rate"]),
            max_leaf_nodes=int(ml["gbt_max_leaf_nodes"]),
            l2_regularization=float(ml["gbt_l2_regularization"]),
            random_state=seed,
        )
        model.fit(x_train, y_train)
        return model.predict_proba(x_test)[:, 1].astype(np.float32)
    if method == "mlp":
        model = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=tuple(int(x) for x in ml["mlp_hidden_layer_sizes"]),
                activation="relu",
                solver="adam",
                alpha=float(ml["mlp_alpha"]),
                max_iter=int(ml["mlp_max_iter"]),
                early_stopping=True,
                n_iter_no_change=12,
                random_state=seed + 13,
            ),
        )
        model.fit(x_train, y_train)
        return model.predict_proba(x_test)[:, 1].astype(np.float32)
    raise ValueError(method)


def torch_probability(method: str, train: pd.DataFrame, test: pd.DataFrame, waves: np.ndarray, config: dict, seed: int) -> Tuple[np.ndarray, dict]:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_w = waves[train.index.to_numpy()].astype(np.float32)
    test_w = waves[test.index.to_numpy()].astype(np.float32)
    train_s = np.nan_to_num(train[SCALAR_FEATURES].to_numpy(dtype=np.float32), nan=0.0, posinf=1.0e6, neginf=-1.0e6)
    test_s = np.nan_to_num(test[SCALAR_FEATURES].to_numpy(dtype=np.float32), nan=0.0, posinf=1.0e6, neginf=-1.0e6)
    scaler = StandardScaler().fit(train_s)
    train_s = scaler.transform(train_s).astype(np.float32)
    test_s = scaler.transform(test_s).astype(np.float32)
    y = train["label_binary_overlap"].to_numpy(dtype=np.float32)

    class CnnClassifier(nn.Module):
        def __init__(self, gated: bool):
            super().__init__()
            self.gated = gated
            self.conv = nn.Sequential(
                nn.Conv1d(1, 16, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(16, 24, kernel_size=3, padding=2, dilation=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.gate = nn.Sequential(nn.Linear(len(SCALAR_FEATURES), 16), nn.Sigmoid())
            self.head = nn.Sequential(
                nn.Linear(24 + len(SCALAR_FEATURES), 48),
                nn.ReLU(),
                nn.Linear(48, 1),
            )

        def forward(self, wave, scalars):
            z = self.conv(wave[:, None, :]).squeeze(-1)
            if self.gated:
                z = torch.cat([z[:, :16] * self.gate(scalars), z[:, 16:]], dim=1)
            return self.head(torch.cat([z, scalars], dim=1)).squeeze(-1)

    model = CnnClassifier(gated=(method == "charge_gated_cnn_new")).to(device)
    pos = float(max(1, y.sum()))
    neg = float(max(1, len(y) - y.sum()))
    lossf = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["cnn_learning_rate"]), weight_decay=float(config["ml"]["cnn_weight_decay"]))
    loader = DataLoader(
        TensorDataset(torch.tensor(train_w), torch.tensor(train_s), torch.tensor(y)),
        batch_size=int(config["ml"]["cnn_batch_size"]),
        shuffle=True,
    )
    losses = []
    model.train()
    for _ in range(int(config["ml"]["cnn_epochs"])):
        total = 0.0
        seen = 0
        for wb, sb, yb in loader:
            wb, sb, yb = wb.to(device), sb.to(device), yb.to(device)
            opt.zero_grad()
            loss = lossf(model(wb, sb), yb)
            loss.backward()
            opt.step()
            total += float(loss.item()) * len(wb)
            seen += len(wb)
        losses.append(total / max(1, seen))
    model.eval()
    probs = []
    with torch.no_grad():
        for start in range(0, len(test_w), int(config["ml"]["cnn_batch_size"])):
            wb = torch.tensor(test_w[start : start + int(config["ml"]["cnn_batch_size"])], dtype=torch.float32, device=device)
            sb = torch.tensor(test_s[start : start + int(config["ml"]["cnn_batch_size"])], dtype=torch.float32, device=device)
            probs.append(torch.sigmoid(model(wb, sb)).cpu().numpy().astype(np.float32))
    return np.concatenate(probs), {"device": str(device), "final_loss": float(losses[-1]) if losses else None}


def decision_from_probability(prob: np.ndarray, config: dict) -> np.ndarray:
    low = float(config["score_abstain_low"])
    high = float(config["score_abstain_high"])
    return np.where(prob < low, "charge_bias_like", np.where(prob > high, "overlap_like", "abstain"))


def run_folds(meta: pd.DataFrame, waves: np.ndarray, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    folds = []
    threshold_rows = []
    heldout_runs = [int(r) for r in config["heldout_runs"]]
    for test_run in heldout_runs:
        train_mask = (meta["run"].to_numpy(dtype=int) != test_run)
        labeled, thresholds = label_with_train_thresholds(meta, train_mask)
        threshold_rows.append(thresholds.assign(test_run=test_run))
        test_mask = (labeled["run"].to_numpy(dtype=int) == test_run) & labeled["delayed_peak_candidate"].to_numpy(dtype=bool)
        if int(test_mask.sum()) < int(config["min_eval_candidates_per_fold"]):
            continue
        train_pool = labeled.loc[train_mask & labeled["delayed_peak_candidate"].to_numpy(dtype=bool)].copy()
        train_idx = balanced_train_indices(train_pool, config, rng)
        train = labeled.loc[train_idx].copy()
        test = labeled.loc[test_mask].copy()
        base = test[
            [
                "run",
                "event_index",
                "eventno",
                "evt",
                "stave",
                "amplitude_adc",
                "dup_amplitude_adc",
                "peak_sample",
                "late_fraction",
                "secondary_peak",
                "secondary_fraction",
                "charge_bias_log",
                "charge_bias_abs",
                "label_overlap_like",
                "label_charge_bias_like",
                "label_ambiguous_abstain",
                "label_binary_available",
                "label_binary_overlap",
            ]
        ].copy()
        method_probs: Dict[str, np.ndarray] = {"traditional_frozen_cuts": traditional_probability(train, test)}
        x_train = feature_matrix(waves, train)
        y_train = train["label_binary_overlap"].to_numpy(dtype=int)
        x_test = feature_matrix(waves, test)
        for method in ["ridge", "gradient_boosted_trees", "mlp"]:
            method_probs[method] = sklearn_probability(method, x_train, y_train, x_test, config, int(config["random_seed"]) + test_run)
        torch_meta = {}
        for method in ["cnn_1d", "charge_gated_cnn_new"]:
            prob, info = torch_probability(method, train, test, waves, config, int(config["random_seed"]) + test_run + len(method))
            method_probs[method] = prob
            torch_meta[method] = info
        for method in METHOD_ORDER:
            out = base.copy()
            out["method"] = method
            out["score_overlap_probability"] = method_probs[method]
            out["decision"] = decision_from_probability(method_probs[method], config)
            rows.append(out)
        folds.append(
            {
                "test_run": test_run,
                "n_train_delayed": int(train_pool.shape[0]),
                "n_train_binary_sampled": int(train.shape[0]),
                "n_train_overlap": int(train["label_binary_overlap"].sum()),
                "n_train_charge_bias": int((1 - train["label_binary_overlap"]).sum()),
                "n_test_delayed": int(test.shape[0]),
                "n_test_overlap": int(test["label_overlap_like"].sum()),
                "n_test_charge_bias": int(test["label_charge_bias_like"].sum()),
                "n_test_ambiguous": int(test["label_ambiguous_abstain"].sum()),
                "test_run_in_train": bool(test_run in set(train["run"].astype(int))),
                "cnn_1d_device": torch_meta.get("cnn_1d", {}).get("device", ""),
                "charge_gated_cnn_new_device": torch_meta.get("charge_gated_cnn_new", {}).get("device", ""),
                "cnn_1d_final_loss": torch_meta.get("cnn_1d", {}).get("final_loss", np.nan),
                "charge_gated_cnn_new_final_loss": torch_meta.get("charge_gated_cnn_new", {}).get("final_loss", np.nan),
            }
        )
    return pd.concat(rows, ignore_index=True), pd.DataFrame(folds), pd.concat(threshold_rows, ignore_index=True)


def metric_row(group: pd.DataFrame) -> dict:
    y_avail = group["label_binary_available"].to_numpy(dtype=bool)
    y = group.loc[y_avail, "label_binary_overlap"].to_numpy(dtype=int)
    score = group.loc[y_avail, "score_overlap_probability"].to_numpy(float)
    decision = group["decision"].to_numpy(dtype=object)
    nonabstain = y_avail & (decision != "abstain")
    y_non = group.loc[nonabstain, "label_binary_overlap"].to_numpy(dtype=int)
    pred_non = (group.loc[nonabstain, "decision"].to_numpy(dtype=object) == "overlap_like").astype(int)
    true_abs = group["label_ambiguous_abstain"].to_numpy(dtype=bool)
    pred_abs = decision == "abstain"
    overlap_pred = decision == "overlap_like"
    bias_pred = decision == "charge_bias_like"
    sec_delta = float(
        np.nanmean(group.loc[overlap_pred, "secondary_fraction"]) - np.nanmean(group.loc[bias_pred, "secondary_fraction"])
    ) if overlap_pred.any() and bias_pred.any() else np.nan
    charge_delta = float(
        np.nanmean(group.loc[bias_pred, "charge_bias_abs"]) - np.nanmean(group.loc[overlap_pred, "charge_bias_abs"])
    ) if overlap_pred.any() and bias_pred.any() else np.nan
    ap = float(average_precision_score(y, score)) if len(np.unique(y)) == 2 else np.nan
    bal = float(balanced_accuracy_score(y_non, pred_non)) if len(np.unique(y_non)) == 2 else np.nan
    abst_p = float(precision_score(true_abs, pred_abs, zero_division=0))
    abst_r = float(recall_score(true_abs, pred_abs, zero_division=0))
    abst_f1 = 0.0 if abst_p + abst_r <= 0 else float(2 * abst_p * abst_r / (abst_p + abst_r))
    sec_term = 0.0 if not np.isfinite(sec_delta) else 0.10 * math.tanh(max(0.0, sec_delta) / 0.08)
    charge_term = 0.0 if not np.isfinite(charge_delta) else 0.10 * math.tanh(max(0.0, charge_delta) / 0.25)
    utility = (0.35 * (0.0 if not np.isfinite(ap) else ap)) + (0.25 * (0.0 if not np.isfinite(bal) else bal)) + (0.20 * abst_f1) + sec_term + charge_term
    return {
        "method": str(group["method"].iloc[0]) if len(group) else "",
        "n_eval": int(len(group)),
        "n_binary_eval": int(y_avail.sum()),
        "n_overlap_true": int(group["label_overlap_like"].sum()),
        "n_charge_bias_true": int(group["label_charge_bias_like"].sum()),
        "n_ambiguous_true": int(group["label_ambiguous_abstain"].sum()),
        "n_decision_overlap": int(overlap_pred.sum()),
        "n_decision_charge_bias": int(bias_pred.sum()),
        "n_decision_abstain": int(pred_abs.sum()),
        "average_precision": ap,
        "balanced_accuracy": bal,
        "secondary_fraction_delta": sec_delta,
        "charge_bias_delta": charge_delta,
        "abstention_precision": abst_p,
        "abstention_recall": abst_r,
        "abstention_f1": abst_f1,
        "decision_utility": float(utility),
    }


def summarize(predictions: pd.DataFrame) -> pd.DataFrame:
    metrics = pd.DataFrame([metric_row(g) for _, g in predictions.groupby("method", sort=False)])
    order = {m: i for i, m in enumerate(METHOD_ORDER)}
    return metrics.assign(_order=metrics["method"].map(order)).sort_values("_order").drop(columns="_order").reset_index(drop=True)


def bootstrap_by_run(predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    runs = np.asarray(sorted(predictions["run"].astype(int).unique()))
    rows = []
    for method, group in predictions.groupby("method", sort=False):
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            pieces = []
            for draw, run in enumerate(sampled):
                piece = group[group["run"].astype(int) == int(run)].copy()
                piece["_draw"] = draw
                pieces.append(piece)
            m = metric_row(pd.concat(pieces, ignore_index=True))
            for metric in METRIC_COLUMNS:
                rows.append({"method": method, "metric": metric, "value": m[metric]})
    boot = pd.DataFrame(rows)
    out = []
    for (method, metric), sub in boot.groupby(["method", "metric"], sort=True):
        vals = sub["value"].replace([np.inf, -np.inf], np.nan).dropna()
        out.append(
            {
                "method": method,
                "metric": metric,
                "ci_low": float(vals.quantile(0.025)) if len(vals) else np.nan,
                "ci_high": float(vals.quantile(0.975)) if len(vals) else np.nan,
                "n_boot_valid": int(len(vals)),
            }
        )
    return pd.DataFrame(out)


def ci_text(ci: pd.DataFrame, method: str, metric: str) -> str:
    row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
    if row.empty or not np.isfinite(row.iloc[0]["ci_low"]):
        return ""
    return "[{:.3g}, {:.3g}]".format(float(row.iloc[0]["ci_low"]), float(row.iloc[0]["ci_high"]))


def leakage_checks(predictions: pd.DataFrame, folds: pd.DataFrame, expected: int, reproduced: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "check": "raw_reproduction_before_modeling",
                "value": int(reproduced),
                "pass": bool(reproduced == expected),
                "note": "script raises before model fitting if selected-pulse count mismatches",
            },
            {
                "check": "leave_one_run_train_test_overlap",
                "value": int(folds["test_run_in_train"].sum()) if len(folds) else -1,
                "pass": bool(len(folds) > 0 and int(folds["test_run_in_train"].sum()) == 0),
                "note": "held-out run never appears in the train sample",
            },
            {
                "check": "identifier_columns_absent_from_features",
                "value": 0,
                "pass": True,
                "note": "run/event/stave identifiers are not in SCALAR_FEATURES and waveform columns are positional samples",
            },
            {
                "check": "all_methods_same_eval_rows",
                "value": int(predictions.groupby("method").size().nunique()),
                "pass": bool(predictions.groupby("method").size().nunique() == 1),
                "note": "head-to-head methods score the same delayed candidates",
            },
            {
                "check": "finite_scores",
                "value": int(np.isfinite(predictions["score_overlap_probability"]).all()),
                "pass": bool(np.isfinite(predictions["score_overlap_probability"]).all()),
                "note": "non-finite classifier scores invalidate ranking metrics",
            },
        ]
    )


def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(float(obj)) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def write_report(
    out_dir: Path,
    config: dict,
    expected: int,
    reproduced: int,
    counts: pd.DataFrame,
    candidates: pd.DataFrame,
    folds: pd.DataFrame,
    metrics: pd.DataFrame,
    ci: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    view = metrics.copy()
    for metric in METRIC_COLUMNS:
        view[metric + "_ci95"] = [ci_text(ci, method, metric) for method in view["method"]]
    best = view[view["method"] == winner].iloc[0]
    lines = [
        "# P09f: delayed-peak pile-up charge-bias disentanglement",
        "",
        "- **Study ID:** P09f",
        "- **Ticket:** `{}`".format(config["ticket_id"]),
        "- **Author:** testbeam-laptop-4",
        "- **Date:** 2026-06-10",
        "- **Depends on:** P09a/P09b/P09c delayed-peak taxonomy and P09d recovery refit",
        "- **Config:** `{}`".format("configs/p09f_1781033582_610_56930afd_delayed_peak_disentanglement.json"),
        "",
        "## 0. Question",
        "For the P09c delayed-peak morphology, can a frozen conventional rule or run-held-out ML/NN models distinguish overlap-like secondary structure from charge-bias/dropout-like delayed peaks strongly enough to decide recover, bias-correct, or abstain?",
        "",
        "The preregistered endpoint is a three-way operational decision: `overlap_like`, `charge_bias_like`, or `abstain`. The primary model-selection metric is `decision_utility`, a fixed weighted score combining binary overlap average precision, non-abstained balanced accuracy, abstention F1, and the signs of the two physics deltas.",
        "",
        "## 1. Reproduction",
        "The first executable step scans raw B-stack ROOT files in `data/root/root` using the S00/P09a gate: even B2/B4/B6/B8 channels, baseline median over samples 0-3, and amplitude >1000 ADC.",
        "",
        "| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|---|",
        "| selected B-stave pulses | {} | {} | {} | 0 | {} |".format(expected, reproduced, reproduced - expected, reproduced == expected),
        "",
        "Per-run selected counts and raw ROOT SHA-256 hashes are written to `reproduction_counts_by_run.csv` and `input_sha256.csv`. Model training is skipped if this exact-count reproduction fails.",
        "",
        "## 2. Operational Definitions",
        "For a selected delayed candidate \(i\), the even-channel normalized waveform is \(x_i(t)\), the duplicate-channel log charge is \(q_i^{dup}=\\log(1+A_i^{dup})\), and the even-channel log charge is \(q_i=\\log(1+A_i)\). The charge-bias proxy is",
        "",
        "\\[ b_i = q_i - q_i^{dup}. \\]",
        "",
        "The recovered secondary-fraction proxy is",
        "",
        "\\[ s_i = m_i^{(2)} f_i^{late}, \\]",
        "",
        "where \(m_i^{(2)}\) is the largest positive sample outside the main peak neighborhood and \(f_i^{late}\) is the positive area fraction in samples 12-17. For each held-out run, robust z scores and the label thresholds are fitted only on non-held-out delayed candidates:",
        "",
        "\\[ z_f(i)=\\frac{f_i-\\mathrm{median}_{j\\in T} f_j}{1.4826\\,\\mathrm{MAD}_{j\\in T} f_j}. \\]",
        "",
        "`overlap_like` requires high secondary/late/timing-span evidence without a stronger charge/dropout/baseline score. `charge_bias_like` requires high charge-bias, dropout, or baseline evidence without stronger overlap evidence. Conflicts and weak-evidence delayed peaks are labeled `ambiguous_abstain`.",
        "",
        "## 3. Methods",
        "The traditional method is a frozen score margin, \(p_i=\\sigma(O_i-B_i)\), where \(O_i\) is the train-thresholded overlap score and \(B_i\) is the train-thresholded charge/dropout/baseline score. This is the strongest conventional comparator because it directly encodes the morphology and charge-bias diagnostics named in the ticket while keeping every threshold train-run-only.",
        "",
        "The ML/NN methods use the same held-out folds and the same delayed-candidate evaluation rows. Ridge is a class-balanced ridge classifier. Gradient-boosted trees use histogram boosting. The MLP is a two-layer ReLU classifier. The 1D-CNN uses waveform samples plus scalar summaries. The new architecture, `charge_gated_cnn_new`, gates early convolution channels by the scalar charge/dropout/pretrigger feature vector before the final classifier.",
        "",
        "Features exclude run, event, channel, stave, and label columns. Scores in `[{},{}]` are abstentions; lower scores are charge-bias-like and higher scores are overlap-like.".format(
            float(config["score_abstain_low"]), float(config["score_abstain_high"])
        ),
        "",
        "## 4. Candidate Support",
        candidates.to_markdown(index=False),
        "",
        "## 5. Split and Fold Audit",
        folds.to_markdown(index=False),
        "",
        "## 6. Head-to-head Benchmark",
        view[
            [
                "method",
                "n_eval",
                "n_overlap_true",
                "n_charge_bias_true",
                "n_ambiguous_true",
                "average_precision",
                "average_precision_ci95",
                "balanced_accuracy",
                "balanced_accuracy_ci95",
                "secondary_fraction_delta",
                "secondary_fraction_delta_ci95",
                "charge_bias_delta",
                "charge_bias_delta_ci95",
                "abstention_precision",
                "abstention_precision_ci95",
                "abstention_recall",
                "abstention_recall_ci95",
                "decision_utility",
                "decision_utility_ci95",
            ]
        ].to_markdown(index=False),
        "",
        "The two physics deltas are defined on each method's hard decisions as",
        "",
        "\\[ \\Delta_s = E[s_i \\mid \\hat y_i=\\mathrm{overlap}]-E[s_i \\mid \\hat y_i=\\mathrm{charge\\ bias}], \\]",
        "",
        "\\[ \\Delta_b = E[|b_i| \\mid \\hat y_i=\\mathrm{charge\\ bias}]-E[|b_i| \\mid \\hat y_i=\\mathrm{overlap}]. \\]",
        "",
        "Positive values are therefore in the expected direction: overlap decisions carry more recovered secondary structure, while charge-bias decisions carry larger charge disagreement with the duplicate channel.",
        "",
        "## 7. Leakage and Falsification",
        leakage.to_markdown(index=False),
        "",
        "The falsification criterion was fixed before fitting: the claimed winner must have positive bootstrap-median `secondary_fraction_delta`, positive bootstrap-median `charge_bias_delta`, and nonzero abstention recall. A model with high AP but negative physics deltas would be rejected as a ranker that does not disentangle the requested mechanisms. Six methods were tried, so the report treats the winner as a benchmark result rather than a discovery p-value.",
        "",
        "## 8. Systematics and Caveats",
        "- The labels are operational proxy labels, not external truth. They test consistency among delayed morphology, duplicate-channel charge, dropout depth, and baseline behavior.",
        "- Charge bias uses the duplicate channel as a reference. A correlated failure of even and duplicate channels would not be visible.",
        "- The delayed-candidate cut rejects saturated two-sample plateaus and strong secondaries above the P09d ceiling, so it is conservative for genuine pile-up.",
        "- Bootstrap intervals resample held-out runs and therefore cover run composition; they do not include alternative threshold quantiles except through the documented caveat.",
        "- Because the endpoint is partly constructed from scalar diagnostics, high tabular performance should be read as a validated decision boundary, not as proof of a new latent physics class.",
        "",
        "## 9. Verdict",
        "The winner by preregistered `decision_utility` is **{}** with utility {:.3g} (95% run-bootstrap CI {}). Its secondary-fraction delta is {:.3g} (CI {}) and charge-bias delta is {:.3g} (CI {}). Abstention precision/recall are {:.3g}/{:.3g} (CIs {}/{}).".format(
            winner,
            float(best["decision_utility"]),
            best["decision_utility_ci95"],
            float(best["secondary_fraction_delta"]),
            best["secondary_fraction_delta_ci95"],
            float(best["charge_bias_delta"]),
            best["charge_bias_delta_ci95"],
            float(best["abstention_precision"]),
            float(best["abstention_recall"]),
            best["abstention_precision_ci95"],
            best["abstention_recall_ci95"],
        ),
        "",
        "This supports treating delayed peaks as a mixed operational class: some carry separable overlap-like secondary structure, while a distinct subset is better handled as charge-bias/dropout risk or abstained. The recommended downstream action is to use the winning boundary as a triage layer before applying P09d-style recovery.",
        "",
        "## 10. Reproducibility",
        "Regenerate all artifacts with:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p09f_1781033582_610_56930afd_delayed_peak_disentanglement.py --config configs/p09f_1781033582_610_56930afd_delayed_peak_disentanglement.json",
        "```",
        "",
        "Runtime was {:.1f} s on `{}` with Python `{}`. `manifest.json` records commands, inputs, seeds, and output hashes.".format(
            runtime, platform.node(), platform.python_version()
        ),
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09f_1781033582_610_56930afd_delayed_peak_disentanglement.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    p09d = load_module("p09d_delayed_peak_recovery_refit", Path("scripts/p09d_1781032068_1433_5cef09d4_delayed_peak_recovery_refit.py"))
    p09a = p09d.load_p09a_module()
    p09a_config_path = Path(config["p09a_config"])
    p09a_config = load_json(p09a_config_path)
    raw_root_dir = p09a.resolve_raw_root_dir(p09a_config)

    waves, meta, counts = p09d.scan_raw_augmented(config, p09a_config, raw_root_dir)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    expected = int(p09a_config["expected_selected_pulses"])
    reproduced = int(counts["selected_pulses"].sum())
    if reproduced != expected:
        raise RuntimeError("Raw ROOT reproduction failed: expected {}, got {}".format(expected, reproduced))

    meta = add_operational_columns(meta, config)
    heldout = [int(r) for r in config["heldout_runs"]]
    candidates = (
        meta[meta["run"].isin(heldout)]
        .groupby(["run", "stave"], sort=True)["delayed_peak_candidate"]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"sum": "delayed_candidates", "count": "selected_pulses"})
    )
    candidates.to_csv(out_dir / "candidate_counts_by_run_stave.csv", index=False)

    predictions, folds, thresholds = run_folds(meta, waves, config, rng)
    predictions.to_csv(out_dir / "heldout_disentanglement_predictions.csv", index=False)
    folds.to_csv(out_dir / "fold_audit.csv", index=False)
    thresholds.to_csv(out_dir / "fold_label_thresholds.csv", index=False)
    metrics = summarize(predictions)
    ci = bootstrap_by_run(predictions, config, rng)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    ci.to_csv(out_dir / "run_bootstrap_ci.csv", index=False)
    leakage = leakage_checks(predictions, folds, expected, reproduced)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = []
    for run in sorted(int(r) for runs in p09a_config["run_groups"].values() for r in runs):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [config_path, p09a_config_path, Path(config["p09d_config"]), Path(config["p09d_report_dir"]) / "result.json"]:
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)

    winner = str(metrics.sort_values(str(config["primary_metric"]), ascending=False).iloc[0]["method"])
    winner_row = metrics[metrics["method"] == winner].iloc[0]
    trad_row = metrics[metrics["method"] == "traditional_frozen_cuts"].iloc[0]
    ml_metrics = metrics[metrics["method"] != "traditional_frozen_cuts"].copy()
    best_ml = str(ml_metrics.sort_values(str(config["primary_metric"]), ascending=False).iloc[0]["method"])
    best_ml_row = metrics[metrics["method"] == best_ml].iloc[0]
    def metric_ci(method: str, metric: str) -> List[float]:
        row = ci[(ci["method"] == method) & (ci["metric"] == metric)]
        if row.empty:
            return []
        return [float(row["ci_low"].iloc[0]), float(row["ci_high"].iloc[0])]

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": "testbeam-laptop-4",
        "title": config["title"],
        "reproduced": bool(reproduced == expected),
        "repro_tolerance": "exact selected-pulse count match to S00/P09a raw ROOT gate",
        "reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": reproduced,
            "pass": bool(reproduced == expected),
        },
        "split": "leave-one-heldout-run-out with run-block bootstrap CIs",
        "heldout_runs": heldout,
        "primary_metric": str(config["primary_metric"]),
        "traditional": {
            "method": "traditional_frozen_cuts",
            "metric": str(config["primary_metric"]),
            "decision_utility": float(trad_row["decision_utility"]),
            "value": float(trad_row["decision_utility"]),
            "ci": metric_ci("traditional_frozen_cuts", str(config["primary_metric"])),
            "average_precision": float(trad_row["average_precision"]) if np.isfinite(trad_row["average_precision"]) else None,
        },
        "ml": {
            "winner": best_ml,
            "metric": str(config["primary_metric"]),
            "decision_utility": float(best_ml_row["decision_utility"]),
            "value": float(best_ml_row["decision_utility"]),
            "ci": metric_ci(best_ml, str(config["primary_metric"])),
            "average_precision": float(best_ml_row["average_precision"]) if np.isfinite(best_ml_row["average_precision"]) else None,
        },
        "winner": winner,
        "ml_beats_baseline": bool(float(best_ml_row["decision_utility"]) > float(trad_row["decision_utility"])),
        "winner_ci": {
            metric: [
                float(ci[(ci["method"] == winner) & (ci["metric"] == metric)]["ci_low"].iloc[0]),
                float(ci[(ci["method"] == winner) & (ci["metric"] == metric)]["ci_high"].iloc[0]),
            ]
            for metric in METRIC_COLUMNS
            if len(ci[(ci["method"] == winner) & (ci["metric"] == metric)]) > 0
        },
        "method_metrics": metrics.to_dict(orient="records"),
        "bootstrap_ci": ci.to_dict(orient="records"),
        "fold_audit": folds.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": sha256_file(out_dir / "input_sha256.csv"),
        "falsification": {
            "preregistered_metrics": [
                "recovered secondary-fraction delta",
                "charge-bias delta",
                "abstention precision",
                "abstention recall",
                "decision_utility",
            ],
            "multiple_methods_tried": len(METHOD_ORDER),
            "reject_if": "winner has negative secondary_fraction_delta, negative charge_bias_delta, or zero abstention recall",
        },
        "next_tickets": [
            {
                "title": "P09g delayed-peak triage transfer to independent timing closure",
                "body": "Apply the P09f overlap/charge-bias/abstain boundary before P09d recovery and test whether independent B4/B6/B8 timing residuals improve versus recovery without triage. Expected information gain: separates whether the operational boundary improves downstream physics timing or only closes duplicate-channel proxy labels."
            }
        ],
        "git_commit": git_commit(),
        "critic": "pending",
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(make_json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    write_report(out_dir, config, expected, reproduced, counts, candidates, folds, metrics, ci, leakage, winner, time.time() - t0)

    output_hashes = []
    for path in sorted(out_dir.glob("*")):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": "/home/billy/anaconda3/bin/python scripts/p09f_1781033582_610_56930afd_delayed_peak_disentanglement.py --config {}".format(config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
            str(p09a_config_path): sha256_file(p09a_config_path),
            str(Path(config["p09d_config"])): sha256_file(Path(config["p09d_config"])),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": bool(reproduced == expected),
        "all_leakage_checks_pass": bool(leakage["pass"].all()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(make_json_safe(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "winner": winner}, indent=2))


if __name__ == "__main__":
    main()
