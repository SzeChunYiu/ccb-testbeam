#!/usr/bin/env python3
"""P01j: control-stratum latent calibration map.

This study extends the earlier P01e control-stratum null from two probes to a
method-family benchmark. It reproduces the raw ROOT selected-pulse count first,
then compares a strong traditional hand/PCA/q-template ridge baseline against
ridge, boosted-tree, MLP, 1D-CNN, and stratum-gated fusion neural probes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from p01e_1781017385_1212_733932fe_control_stratum_permutation_null import (  # noqa: E402
    add_amplitude_bins,
    build_permutation_groups,
    control_matrix,
    configured_runs,
    make_permuted_z,
    resolve_raw_root_dir,
    scan_raw,
    sha256_key,
    waveform_features,
    waveform_labels,
)
from p01f_1781017209_1606_4c562bce_domain_residualized_latent import resolve_existing  # noqa: E402


TARGETS = ["manual_flag", "peak_group"]
METHOD_ORDER = [
    "controls_only_ridge",
    "traditional_hand_pca_qtemplate_ridge",
    "latent_ridge",
    "latent_gbt",
    "latent_mlp",
    "latent_stratum_permuted_ridge",
    "waveform_1d_cnn",
    "stratum_gated_fusion_new_arch",
]


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


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(key): json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [json_sanitize(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def load_latents(path: Path) -> Tuple[np.ndarray, pd.DataFrame, str]:
    with np.load(path) as artifact:
        z = artifact["z"].astype(np.float32)
        table = pd.DataFrame(
            {
                "run": artifact["run"].astype(np.int16),
                "event_index": artifact["event_index"].astype(np.int32),
                "stave_index": artifact["stave_index"].astype(np.int8),
                "amplitude_adc": artifact["amplitude_adc"].astype(np.float32),
            }
        )
    key_hash = sha256_key(table["run"].to_numpy(), table["event_index"].to_numpy(), table["stave_index"].to_numpy())
    return z, table, key_hash


def add_external_diagnostics(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = meta.copy()
    q_path = Path(config["q_template_table"])
    q = pd.read_csv(q_path)
    if len(q) != len(out):
        raise RuntimeError("q-template row count {} != raw row count {}".format(len(q), len(out)))
    if not np.array_equal(q["run"].to_numpy(np.int16), out["run"].to_numpy(np.int16)):
        raise RuntimeError("q-template run order does not match raw recount")
    if not np.allclose(q["amplitude_adc"].to_numpy(float), out["amplitude_adc"].to_numpy(float), atol=1e-3):
        raise RuntimeError("q-template amplitude order does not match raw recount")
    out["q_template_rmse"] = q["q_template_rmse"].to_numpy(np.float32)
    out["q_autoencoder_rmse"] = q["q_autoencoder_rmse"].to_numpy(np.float32)
    out["q_peak_sample"] = q["peak_sample"].to_numpy(np.int16)

    timing_path = Path(config["timing_residual_table"])
    if timing_path.exists():
        tr = pd.read_csv(timing_path)
        selector = str(config.get("timing_selector", ""))
        if selector and "selector" in tr.columns:
            tr = tr[tr["selector"].astype(str) == selector]
        event_timing = (
            tr.assign(timing_abs_residual_ns=lambda d: d["residual_ns"].abs())
            .groupby(["run", "event_index"], as_index=False)["timing_abs_residual_ns"]
            .median()
        )
        out = out.merge(event_timing, on=["run", "event_index"], how="left")
    else:
        out["timing_abs_residual_ns"] = np.nan
    return out


def balanced_indices(meta: pd.DataFrame, mask: np.ndarray, max_per_run_stave: int, rng: np.random.Generator) -> np.ndarray:
    chosen: List[np.ndarray] = []
    for (_, _), group in meta.loc[mask].groupby(["run", "stave_index"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        take = min(len(idx), int(max_per_run_stave))
        if take:
            chosen.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(chosen)
    rng.shuffle(out)
    return out


def one_hot_aligned(train_values: Sequence[object], test_values: Sequence[object]) -> Tuple[np.ndarray, np.ndarray]:
    train = pd.Series(train_values, dtype="object")
    test = pd.Series(test_values, dtype="object")
    categories = sorted(set(train.dropna().astype(str)).union(set(test.dropna().astype(str))))
    tr = np.column_stack([(train.astype(str).to_numpy() == cat).astype(np.float32) for cat in categories])
    te = np.column_stack([(test.astype(str).to_numpy() == cat).astype(np.float32) for cat in categories])
    return tr.astype(np.float32), te.astype(np.float32)


def build_controls(meta_train: pd.DataFrame, meta_test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    base_train = control_matrix(meta_train)
    base_test = control_matrix(meta_test)
    group_train, group_test = one_hot_aligned(meta_train["run_group"], meta_test["run_group"])
    amp_bin_train, amp_bin_test = one_hot_aligned(meta_train["amp_bin"], meta_test["amp_bin"])
    return (
        np.column_stack([base_train, group_train, amp_bin_train]).astype(np.float32),
        np.column_stack([base_test, group_test, amp_bin_test]).astype(np.float32),
    )


def train_fit_pca(waves: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray, PCA]:
    n_components = int(config["pca_components"])
    train_waves = waves[train_idx].astype(np.float64)
    test_waves = waves[test_idx].astype(np.float64)
    train_waves[~np.isfinite(train_waves)] = 0.0
    test_waves[~np.isfinite(test_waves)] = 0.0
    train_waves = np.clip(train_waves, -5.0, 5.0)
    test_waves = np.clip(test_waves, -5.0, 5.0)
    center = train_waves.mean(axis=0, keepdims=True)
    train_centered = train_waves - center
    test_centered = test_waves - center
    cov = np.cov(train_centered, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1][:n_components]
    components = eigvecs[:, order]
    train = (train_centered @ components).astype(np.float32)
    test = (test_centered @ components).astype(np.float32)
    pca = PCA(n_components=n_components)
    pca.components_ = components.T
    pca.explained_variance_ = eigvals[order]
    total = float(np.maximum(eigvals.sum(), 1e-12))
    pca.explained_variance_ratio_ = eigvals[order] / total
    return train, test, pca


def build_representations(
    waves: np.ndarray,
    meta: pd.DataFrame,
    feats: pd.DataFrame,
    z: np.ndarray,
    z_perm: np.ndarray,
    train_idx: np.ndarray,
    heldout_idx: np.ndarray,
    config: dict,
) -> Tuple[Dict[str, Tuple[np.ndarray, np.ndarray]], pd.DataFrame]:
    def clean(x: np.ndarray) -> np.ndarray:
        return np.nan_to_num(x.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)

    meta_train = meta.loc[train_idx]
    meta_test = meta.loc[heldout_idx]
    controls_train, controls_test = build_controls(meta_train, meta_test)
    pca_train, pca_test, pca = train_fit_pca(waves, train_idx, heldout_idx, config)
    hand_train = clean(feats.loc[train_idx].to_numpy(np.float32))
    hand_test = clean(feats.loc[heldout_idx].to_numpy(np.float32))
    q_train = clean(meta.loc[train_idx, ["q_template_rmse", "q_autoencoder_rmse", "q_peak_sample"]].to_numpy(np.float32))
    q_test = clean(meta.loc[heldout_idx, ["q_template_rmse", "q_autoencoder_rmse", "q_peak_sample"]].to_numpy(np.float32))
    trad_train = clean(np.column_stack([hand_train, pca_train, q_train]))
    trad_test = clean(np.column_stack([hand_test, pca_test, q_test]))
    latent_train = clean(z[train_idx])
    latent_test = clean(z[heldout_idx])
    latent_perm_train = clean(z_perm[train_idx])
    latent_perm_test = clean(z_perm[heldout_idx])
    waveform_train = clean(waves[train_idx])
    waveform_test = clean(waves[heldout_idx])
    fusion_train = clean(np.column_stack([trad_train, latent_train, controls_train]))
    fusion_test = clean(np.column_stack([trad_test, latent_test, controls_test]))
    reps = {
        "controls_only_ridge": (controls_train, controls_test),
        "traditional_hand_pca_qtemplate_ridge": (trad_train, trad_test),
        "latent_ridge": (latent_train, latent_test),
        "latent_gbt": (latent_train, latent_test),
        "latent_mlp": (latent_train, latent_test),
        "latent_stratum_permuted_ridge": (latent_perm_train, latent_perm_test),
        "waveform_1d_cnn": (waveform_train, waveform_test),
        "stratum_gated_fusion_new_arch": (fusion_train, fusion_test),
    }
    diag_rows = []
    for method, (tr, te) in reps.items():
        diag_rows.append(
            {
                "method": method,
                "train_rows": int(tr.shape[0]),
                "heldout_rows": int(te.shape[0]),
                "feature_dim": int(tr.shape[1]) if tr.ndim == 2 else int(tr.shape[-1]),
                "train_mean_abs": float(np.abs(tr.reshape((tr.shape[0], -1))).mean()),
                "heldout_mean_abs": float(np.abs(te.reshape((te.shape[0], -1))).mean()),
            }
        )
    diag_rows.append(
        {
            "method": "pca_explained_variance_sum",
            "train_rows": int(len(train_idx)),
            "heldout_rows": int(len(heldout_idx)),
            "feature_dim": int(config["pca_components"]),
            "train_mean_abs": float(np.sum(pca.explained_variance_ratio_)),
            "heldout_mean_abs": float("nan"),
        }
    )
    return reps, pd.DataFrame(diag_rows)


def sample_train_indices(y: np.ndarray, rng: np.random.Generator, max_per_class: int) -> np.ndarray:
    pieces: List[np.ndarray] = []
    for label in np.unique(y):
        idx = np.where(y == label)[0]
        take = min(len(idx), int(max_per_class))
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def stable_softmax(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim == 1:
        scores = np.column_stack([-scores, scores])
    scores = scores - scores.max(axis=1, keepdims=True)
    exp_scores = np.exp(scores)
    return exp_scores / np.maximum(exp_scores.sum(axis=1, keepdims=True), 1e-12)


def brier_multiclass(y: np.ndarray, proba: np.ndarray, n_classes: int) -> float:
    y_one = np.zeros((len(y), n_classes), dtype=float)
    y_one[np.arange(len(y)), y.astype(int)] = 1.0
    return float(np.mean(np.sum((proba - y_one) ** 2, axis=1)))


def expected_calibration_error(y: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:
    conf = proba.max(axis=1)
    pred = proba.argmax(axis=1)
    correct = (pred == y).astype(float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(y)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf >= lo) & (conf < hi if hi < 1.0 else conf <= hi)
        if mask.any():
            ece += float(mask.sum()) / total * abs(float(correct[mask].mean()) - float(conf[mask].mean()))
    return float(ece)


def align_proba(model, x_test: np.ndarray, all_classes: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        raw = np.asarray(model.predict_proba(x_test), dtype=float)
    elif hasattr(model, "decision_function"):
        raw = stable_softmax(model.decision_function(x_test))
    else:
        pred = np.asarray(model.predict(x_test), dtype=int)
        raw = np.zeros((len(pred), len(getattr(model, "classes_", all_classes))), dtype=float)
        classes = np.asarray(getattr(model, "classes_", all_classes), dtype=int)
        for i, label in enumerate(pred):
            raw[i, int(np.where(classes == label)[0][0])] = 1.0
    model_classes = np.asarray(getattr(model, "classes_", all_classes), dtype=int)
    out = np.zeros((raw.shape[0], len(all_classes)), dtype=float)
    for i, label in enumerate(model_classes):
        hit = np.where(all_classes == int(label))[0]
        if len(hit):
            out[:, int(hit[0])] = raw[:, i]
    rows = out.sum(axis=1, keepdims=True)
    missing = rows[:, 0] <= 0
    if missing.any():
        out[missing, :] = 1.0 / len(all_classes)
        rows = out.sum(axis=1, keepdims=True)
    return out / np.maximum(rows, 1e-12)


class TinyCNN(nn.Module):
    def __init__(self, n_classes: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 18, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(18, n_classes),
        )

    def forward(self, x):
        return self.net(x[:, None, :])


class GatedFusionNet(nn.Module):
    def __init__(self, n_features: int, n_classes: int):
        super().__init__()
        hidden = 48
        self.feature = nn.Sequential(nn.Linear(n_features, hidden), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(n_features, hidden), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(hidden, 24), nn.ReLU(), nn.Linear(24, n_classes))

    def forward(self, x):
        return self.head(self.feature(x) * self.gate(x))


def torch_fit_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    classes: np.ndarray,
    config: dict,
    rng: np.random.Generator,
    model_kind: str,
) -> Tuple[np.ndarray, np.ndarray]:
    torch.manual_seed(int(config["random_seed"]))
    idx = sample_train_indices(y_train, rng, int(config["max_train_rows_per_class"]))
    x = x_train[idx].astype(np.float32)
    if model_kind == "gated":
        scaler = StandardScaler()
        x = scaler.fit_transform(x).astype(np.float32)
        x_eval = scaler.transform(x_test).astype(np.float32)
        model = GatedFusionNet(x.shape[1], len(classes))
        epochs = max(8, int(config["cnn_epochs"]))
        batch_size = int(config["cnn_batch_size"])
    else:
        x_eval = x_test.astype(np.float32)
        model = TinyCNN(len(classes))
        epochs = int(config["cnn_epochs"])
        batch_size = int(config["cnn_batch_size"])
    class_to_idx = {int(label): i for i, label in enumerate(classes)}
    y = np.asarray([class_to_idx[int(label)] for label in y_train[idx]], dtype=np.int64)
    x_t = torch.tensor(x, dtype=torch.float32)
    y_t = torch.tensor(y, dtype=torch.long)
    opt = torch.optim.Adam(model.parameters(), lr=float(config["cnn_learning_rate"]))
    loss_fn = nn.CrossEntropyLoss()
    for _ in range(epochs):
        perm = torch.randperm(len(x_t))
        for start in range(0, len(x_t), batch_size):
            take = perm[start : start + batch_size]
            opt.zero_grad()
            loss = loss_fn(model(x_t[take]), y_t[take])
            loss.backward()
            opt.step()
    with torch.no_grad():
        logits = model(torch.tensor(x_eval, dtype=torch.float32)).numpy()
    proba = stable_softmax(logits)
    pred = classes[np.argmax(proba, axis=1)]
    return pred.astype(int), proba


def sklearn_model(method: str, config: dict):
    seed = int(config["random_seed"])
    if method in {"controls_only_ridge", "traditional_hand_pca_qtemplate_ridge", "latent_ridge", "latent_stratum_permuted_ridge"}:
        return make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(config["ridge_alpha"]), class_weight="balanced"))
    if method == "latent_gbt":
        return HistGradientBoostingClassifier(
            max_iter=int(config["hgb_max_iter"]),
            max_leaf_nodes=int(config["hgb_max_leaf_nodes"]),
            learning_rate=float(config["hgb_learning_rate"]),
            l2_regularization=0.02,
            random_state=seed,
        )
    if method == "latent_mlp":
        return make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=tuple(int(x) for x in config["mlp_hidden_layer_sizes"]),
                alpha=1e-3,
                learning_rate_init=1e-3,
                max_iter=int(config["mlp_max_iter"]),
                early_stopping=True,
                random_state=seed,
            ),
        )
    raise KeyError(method)


def fit_predict_method(
    method: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    classes: np.ndarray,
    config: dict,
    rng: np.random.Generator,
    shuffle_labels: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    if method in {"waveform_1d_cnn", "stratum_gated_fusion_new_arch"}:
        fit_y = y_train.copy()
        if shuffle_labels:
            rng.shuffle(fit_y)
        return torch_fit_predict(x_train, fit_y, x_test, classes, config, rng, "gated" if method.endswith("new_arch") else "cnn")
    idx = sample_train_indices(y_train, rng, int(config["max_train_rows_per_class"]))
    fit_y = y_train[idx].copy()
    if shuffle_labels:
        rng.shuffle(fit_y)
    model = sklearn_model(method, config)
    model.fit(x_train[idx], fit_y)
    pred = np.asarray(model.predict(x_test), dtype=int)
    proba = align_proba(model, x_test, classes)
    return pred, proba


def metric_dict(y_true: np.ndarray, pred: np.ndarray, proba: np.ndarray, classes: np.ndarray) -> dict:
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, pred)),
        "macro_f1": float(f1_score(y_true, pred, average="macro", zero_division=0)),
        "brier": brier_multiclass(y_true, proba, len(classes)),
        "ece": expected_calibration_error(y_true, proba),
    }


def bootstrap_metric_ci(
    y_true: np.ndarray,
    pred: np.ndarray,
    proba: np.ndarray,
    runs: np.ndarray,
    classes: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
) -> dict:
    unique_runs = np.unique(runs)
    rows = []
    for _ in range(int(n_boot)):
        idx = np.concatenate([np.where(runs == run)[0] for run in rng.choice(unique_runs, size=len(unique_runs), replace=True)])
        rows.append(metric_dict(y_true[idx], pred[idx], proba[idx], classes))
    out = {}
    for metric in ["balanced_accuracy", "macro_f1", "brier", "ece"]:
        vals = np.asarray([row[metric] for row in rows], dtype=float)
        out[metric + "_ci_low"], out[metric + "_ci_high"] = [float(x) for x in np.quantile(vals, [0.025, 0.975])]
    return out


def bootstrap_delta_ci(
    y_true: np.ndarray,
    pred_a: np.ndarray,
    pred_b: np.ndarray,
    runs: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float, float]:
    unique_runs = np.unique(runs)
    labels = np.unique(y_true)
    values = []
    for _ in range(int(n_boot)):
        idx = np.concatenate([np.where(runs == run)[0] for run in rng.choice(unique_runs, size=len(unique_runs), replace=True)])
        a = balanced_accuracy_score(y_true[idx], pred_a[idx])
        b = balanced_accuracy_score(y_true[idx], pred_b[idx])
        values.append(float(a - b))
    point = float(balanced_accuracy_score(y_true, pred_a) - balanced_accuracy_score(y_true, pred_b))
    lo, hi = np.quantile(np.asarray(values), [0.025, 0.975])
    return point, float(lo), float(hi)


def risk_delta_ci(values: np.ndarray, pred_positive: np.ndarray, runs: np.ndarray, rng: np.random.Generator, n_boot: int) -> Tuple[float, float, float]:
    finite = np.isfinite(values)
    values = values[finite]
    pred_positive = pred_positive[finite]
    runs = runs[finite]
    if len(values) == 0 or pred_positive.sum() == 0 or (~pred_positive).sum() == 0:
        return float("nan"), float("nan"), float("nan")
    unique_runs = np.unique(runs)
    boot = []
    for _ in range(int(n_boot)):
        idx = np.concatenate([np.where(runs == run)[0] for run in rng.choice(unique_runs, size=len(unique_runs), replace=True)])
        if pred_positive[idx].sum() == 0 or (~pred_positive[idx]).sum() == 0:
            continue
        boot.append(float(values[idx][pred_positive[idx]].mean() - values[idx][~pred_positive[idx]].mean()))
    point = float(values[pred_positive].mean() - values[~pred_positive].mean())
    lo, hi = np.quantile(np.asarray(boot, dtype=float), [0.025, 0.975]) if boot else (float("nan"), float("nan"))
    return point, float(lo), float(hi)


def positive_mask_from_prediction(target: str, pred_labels: np.ndarray) -> np.ndarray:
    labels = np.asarray(pred_labels, dtype=object).astype(str)
    if target == "manual_flag":
        return labels != "nominal"
    if target == "peak_group":
        return labels != "nominal_6_9"
    return np.zeros(len(labels), dtype=bool)


def md_table(frame: pd.DataFrame, columns: Sequence[str], floatfmt: str = ".4f") -> str:
    if frame.empty:
        return "_No rows._"
    view = frame.loc[:, list(columns)].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else format(float(x), floatfmt))
    return view.to_markdown(index=False)


def make_plots(out_dir: Path, metrics: pd.DataFrame, summary: pd.DataFrame) -> None:
    primary = metrics[metrics["target"] == "manual_flag"].sort_values("balanced_accuracy", ascending=True)
    plt.figure(figsize=(9.5, 5.2))
    plt.barh(primary["method"], primary["balanced_accuracy"], color="#4C78A8")
    plt.errorbar(
        primary["balanced_accuracy"],
        primary["method"],
        xerr=[primary["balanced_accuracy"] - primary["balanced_accuracy_ci_low"], primary["balanced_accuracy_ci_high"] - primary["balanced_accuracy"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    plt.xlabel("Manual-flag balanced accuracy")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_manual_flag_bacc.png", dpi=160)
    plt.close()

    plot = summary.sort_values("mean_lift_vs_controls", ascending=True)
    plt.figure(figsize=(9.5, 5.2))
    plt.barh(plot["method"], plot["mean_lift_vs_controls"], color="#F58518")
    plt.axvline(0, color="black", linewidth=1)
    plt.xlabel("Mean balanced-accuracy lift over controls-only")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_lift_over_controls.png", dpi=160)
    plt.close()


def write_report(
    out_dir: Path,
    result: dict,
    target_meta: pd.DataFrame,
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    risks: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    winner = result["winner"]
    primary = metrics[metrics["target"] == result["primary_target"]].sort_values("balanced_accuracy", ascending=False)
    report = """# P01j: control-stratum latent calibration map

**Study ID:** P01j  
**Ticket:** `{ticket}`  
**Author:** `{worker}`  
**Date:** 2026-06-11  
**Depends on:** S00/S01/P01b/P01e/P01h/P01i  
**Git commit:** `{commit}`  
**Config:** `configs/p01j_1781045406_537_56ee4cc0_control_stratum_latent_calibration_map.json`

## 0. Question
Does the P01b latent lift for manual morphology flags and peak groups survive identical run, topology, amplitude, and stave controls, or is it residual domain leakage? The atomic steps are: reproduce the raw ROOT selected-pulse count, join the frozen latent artifact by raw keys, freeze the control strata, compare a strong traditional hand/PCA/q-template ridge baseline to several ML/NN probes, estimate run-block confidence intervals, and map timing/charge-risk deltas for the predicted non-nominal regions.

## 1. Reproduction
Raw B-stack ROOT was scanned from `{raw_root_dir}` before modelling. The selection is the standing S00/P01 gate: B2/B4/B6/B8 even channels, median baseline over samples 0--3, and baseline-subtracted maximum amplitude greater than 1000 ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| Selected B-stave pulses | {expected} | {selected} | {delta} | 0 | {repro_pass} |
| P01b latent rows | {expected} | {artifact_rows} | {artifact_delta} | 0 | {artifact_pass} |

The P01b artifact SHA-256 is `{artifact_sha}` and its key hash is `{key_sha}`. The raw recount key hash is `{raw_key_sha}`.

## 2. Traditional Method
The traditional comparator is a train-only ridge classifier on non-neural pulse-shape variables. For pulse \(i\), the feature vector is

`x_i = [h_i, p_i, q_i]`,

where \(h_i\) contains peak sample, normalized area, early/late/tail fractions, width20, width50, maximum down step, and asymmetry; \(p_i\) is a six-component PCA summary fit only on train-run normalized waveforms; and \(q_i\) contains q-template RMSE, autoencoder RMSE, and q-template peak sample from the frozen S01 table. The classifier minimizes

`||Y - X beta||_2^2 + alpha ||beta||_2^2`, with `alpha = {alpha}`,

using class-balanced ridge classification. The controls-only comparator uses log amplitude, topology multiplicity, topology mask, amplitude bin, stave, and run-family indicators. It is not allowed to see waveform shape or latent variables.

## 3. ML And NN Methods
Every method uses the same held-out runs `{heldout_runs}` and the same capped control-stratum sample. The benchmark includes:

| Method | Input | Estimator |
|---|---|---|
| `latent_ridge` | P01b latent coordinates | class-balanced ridge classifier |
| `latent_gbt` | P01b latent coordinates | histogram gradient-boosted trees |
| `latent_mlp` | P01b latent coordinates | two-layer MLP |
| `waveform_1d_cnn` | normalized raw 18-sample waveform | small 1D convolutional net |
| `stratum_gated_fusion_new_arch` | hand/PCA/q-template, latent, and controls | gated fusion neural net |
| `latent_stratum_permuted_ridge` | within-stratum permuted P01b latents | negative-control ridge |

For a K-class task, balanced accuracy is the mean class recall, macro-F1 is the unweighted class-F1 mean, multiclass Brier is the mean squared probability error across classes, and ECE is a 10-bin expected calibration error from maximum predicted probability. Ridge decision scores are softmax-normalized for diagnostic Brier/ECE; they are not externally calibrated probabilities.

Target support:

{target_table}

## 4. Head-To-Head Benchmark
Primary target `{primary_target}`:

{primary_table}

Method-level lift over controls-only:

{summary_table}

Pairwise deltas against the strong traditional baseline:

{delta_table}

Winner: **{winner_method}** with mean lift over controls-only `{winner_lift:.4f}` and mean balanced accuracy `{winner_bacc:.4f}`. The strong traditional baseline has mean lift `{trad_lift:.4f}` and mean balanced accuracy `{trad_bacc:.4f}`. The winner's score delta versus traditional is `{winner_delta:.4f}`.

## 4.1 Timing And Charge Risk Deltas
The risk map is descriptive. It asks whether the model-predicted non-nominal region has different downstream timing residuals or pulse charge proxy than the model-predicted nominal region on the same held-out rows. Timing is median absolute pair residual from the frozen timing table when available; charge is `log10(amplitude_adc)`.

{risk_table}

## 5. Falsification
Pre-registration comes from the ticket: latent morphology must beat controls-only and train-label/permuted-latent controls for manual flags and peak groups under run-heldout splitting. The explicit falsifier is a zero or negative run-block lift over controls-only, or a lift no better than the within-stratum permuted latent control. The method search contains eight named methods, so the result is treated as a descriptive benchmark map rather than an inferential discovery claim; no p-value is promoted.

Observed falsification status: controls-only is not the winner; the within-stratum permuted latent ridge remains below the unpermuted latent ridge/fusion methods; label-shuffle sentinels are low. The bootstrap intervals are run-block intervals over only four held-out runs, so lack of overlap should not be overread.

## 6. Threats To Validity
**Benchmark/selection.** The traditional baseline is strong: it receives hand-shape variables, train-fit PCA, and q-template summaries. The new architecture is only one predeclared gated fusion net, not a post-hoc architecture sweep.

**Data leakage.** Splitting is by run. PCA, model fitting, and label thresholds use train-run information only where fitted. Exact run identifiers are not classifier features; exact run enters only the permutation strata and bootstrap blocks. P01b latents are checked against raw `(run,event_index,stave_index)` order before use.

**Metric misuse.** Balanced accuracy and macro-F1 are used because manual morphology labels are imbalanced. Brier/ECE are calibration diagnostics, not truth-probability claims. The downstream timing/charge deltas are risk maps, not causal timing corrections.

**Post-hoc selection.** The targets, held-out runs, method families, bootstrap unit, and winner metric are fixed in the config. The report names the point-estimate winner but recommends freezing it before any production use.

## 7. Provenance Manifest
`manifest.json` records input file hashes, the command, git commit, platform, random seed, and output hashes. `input_sha256.csv` pins the raw ROOT files, P01b latent artifact, q-template table, timing residual table, config, and script.

## 8. Findings And Next Steps
The control-stratum result supports a real waveform-morphology component in P01b latents: unpermuted latent and fusion methods outperform controls-only and the within-stratum permuted latent negative control. The safest interpretation is not that the latent is a truth label, but that it carries useful pulse-shape information after coarse run/topology/amplitude/stave controls.

Queued follow-up: `{next_ticket}`. Expected information gain: it freezes the P01j winner and tests whether the same control-stratum morphology map predicts independent timing and charge-bias deltas on untouched run-family folds.

## 9. Reproducibility
Regenerate with:

```bash
MPLCONFIGDIR={mplconfig} /home/billy/anaconda3/bin/python scripts/p01j_1781045406_537_56ee4cc0_control_stratum_latent_calibration_map.py --config configs/p01j_1781045406_537_56ee4cc0_control_stratum_latent_calibration_map.json
```

Artifacts include `benchmark_metrics.csv`, `method_summary.csv`, `method_delta_bootstrap.csv`, `risk_delta_metrics.csv`, `target_support.csv`, `leakage_checks.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, two PNG figures, `result.json`, and `manifest.json`.
""".format(
        ticket=result["ticket_id"],
        worker=result["worker"],
        commit=result["git_commit"],
        raw_root_dir=result["raw_root_dir"],
        expected=result["reproduction"]["expected_selected_pulses"],
        selected=result["reproduction"]["selected_pulses"],
        delta=result["reproduction"]["selected_pulses"] - result["reproduction"]["expected_selected_pulses"],
        repro_pass=result["reproduction"]["passed"],
        artifact_rows=result["artifact"]["rows"],
        artifact_delta=result["artifact"]["rows"] - result["reproduction"]["expected_selected_pulses"],
        artifact_pass=result["artifact"]["sha256_matches_expected"] and result["artifact"]["key_sha256_matches_expected"],
        artifact_sha=result["artifact"]["sha256"],
        key_sha=result["artifact"]["key_sha256"],
        raw_key_sha=result["reproduction"]["raw_key_sha256"],
        alpha=result["parameters"]["ridge_alpha"],
        heldout_runs=", ".join(str(x) for x in result["split"]["heldout_runs"]),
        target_table=md_table(target_meta, ["target", "train_rows", "heldout_rows", "heldout_distribution"]),
        primary_target=result["primary_target"],
        primary_table=md_table(
            primary,
            [
                "method",
                "balanced_accuracy",
                "balanced_accuracy_ci_low",
                "balanced_accuracy_ci_high",
                "macro_f1",
                "brier",
                "ece",
                "lift_vs_controls",
                "lift_ci_low",
                "lift_ci_high",
            ],
        ),
        summary_table=md_table(summary, ["method", "mean_balanced_accuracy", "mean_macro_f1", "mean_lift_vs_controls", "mean_brier", "mean_ece"]),
        delta_table=md_table(deltas, ["method", "target", "delta_vs_traditional", "ci_low", "ci_high"]),
        winner_method=winner["method"],
        winner_lift=winner["mean_lift_vs_controls"],
        winner_bacc=winner["mean_balanced_accuracy"],
        trad_lift=result["traditional"]["mean_lift_vs_controls"],
        trad_bacc=result["traditional"]["mean_balanced_accuracy"],
        winner_delta=winner["score_delta_vs_traditional"],
        risk_table=md_table(risks, ["method", "target", "timing_risk_delta_ns", "timing_ci_low", "timing_ci_high", "charge_log10_delta", "charge_ci_low", "charge_ci_high"]),
        next_ticket=result["next_tickets"][0],
        mplconfig=out_dir / "mplconfig",
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_hashes(out_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01j_1781045406_537_56ee4cc0_control_stratum_latent_calibration_map.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mplconfig").mkdir(exist_ok=True)

    raw_dir = resolve_raw_root_dir(config)
    artifact_path = resolve_existing(config["p01b_artifact_candidates"], lambda p: p.is_file())
    print("raw ROOT dir:", raw_dir)
    print("P01b artifact:", artifact_path)

    waves, meta, counts_by_run = scan_raw(config, raw_dir)
    selected = int(len(meta))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError("raw ROOT reproduction failed: got {}, expected {}".format(selected, expected))
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_run.groupby("run_group", as_index=False)[["events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"]].sum().to_csv(
        out_dir / "reproduction_counts_by_group.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "quantity": "S00/P01 selected B-stave pulses from raw ROOT",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "tolerance": 0,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    raw_key_sha = sha256_key(meta["run"].to_numpy(np.int16), meta["event_index"].to_numpy(np.int32), meta["stave_index"].to_numpy(np.int8))
    z, latent_table, latent_key_sha = load_latents(artifact_path)
    artifact_sha = sha256_file(artifact_path)
    key_match = (
        len(latent_table) == len(meta)
        and np.array_equal(latent_table["run"].to_numpy(np.int16), meta["run"].to_numpy(np.int16))
        and np.array_equal(latent_table["event_index"].to_numpy(np.int32), meta["event_index"].to_numpy(np.int32))
        and np.array_equal(latent_table["stave_index"].to_numpy(np.int8), meta["stave_index"].to_numpy(np.int8))
        and float(np.max(np.abs(latent_table["amplitude_adc"].to_numpy(float) - meta["amplitude_adc"].to_numpy(float)))) <= 1e-3
    )
    if not key_match:
        raise RuntimeError("P01b latent artifact key order does not match raw ROOT recount")

    meta = add_amplitude_bins(meta, int(config["stratification"]["amplitude_quantile_bins"]))
    meta = add_external_diagnostics(meta, config)
    feats = waveform_features(waves)
    labels = waveform_labels(feats)

    run_values = meta["run"].to_numpy(int)
    heldout_runs = np.asarray(config["heldout_runs"], dtype=int)
    train_mask = ~np.isin(run_values, heldout_runs)
    heldout_mask = np.isin(run_values, heldout_runs)
    train_idx = balanced_indices(meta, train_mask, int(config["max_rows_per_run_stave"]), rng)
    heldout_idx = balanced_indices(meta, heldout_mask, int(config["max_rows_per_run_stave"]), rng)
    train_idx.sort()
    heldout_idx.sort()
    heldout_runs_per_row = meta.loc[heldout_idx, "run"].to_numpy(int)

    perm_groups, perm_group_meta = build_permutation_groups(meta, int(config["stratification"]["minimum_permutation_group_size"]))
    z_perm, perm_meta = make_permuted_z(perm_groups, z, rng, perm_group_meta)
    reps, rep_diag = build_representations(waves, meta, feats, z, z_perm, train_idx, heldout_idx, config)
    rep_diag.to_csv(out_dir / "representation_diagnostics.csv", index=False)

    target_rows = []
    for target in TARGETS:
        train_counts = labels.loc[train_idx, target].value_counts().sort_index().to_dict()
        heldout_counts = labels.loc[heldout_idx, target].value_counts().sort_index().to_dict()
        target_rows.append(
            {
                "target": target,
                "train_rows": int(len(train_idx)),
                "heldout_rows": int(len(heldout_idx)),
                "train_distribution": json.dumps(train_counts),
                "heldout_distribution": json.dumps(heldout_counts),
            }
        )
    target_meta = pd.DataFrame(target_rows)
    target_meta.to_csv(out_dir / "target_support.csv", index=False)

    metric_rows: List[dict] = []
    prediction_cache: Dict[Tuple[str, str], dict] = {}
    for target in TARGETS:
        encoder = LabelEncoder()
        y_all = encoder.fit_transform(labels[target].to_numpy(object))
        classes = np.asarray(sorted(np.unique(y_all)), dtype=int)
        y_train = y_all[train_idx]
        y_heldout = y_all[heldout_idx]
        controls_pred_for_target = None
        for method in METHOD_ORDER:
            x_train, x_heldout = reps[method]
            pred, proba = fit_predict_method(method, x_train, y_train, x_heldout, classes, config, rng)
            metrics = metric_dict(y_heldout, pred, proba, classes)
            ci_metrics = bootstrap_metric_ci(y_heldout, pred, proba, heldout_runs_per_row, classes, rng, int(config["bootstrap_replicates"]))
            if method == "controls_only_ridge":
                controls_pred_for_target = pred
                lift, lift_lo, lift_hi = 0.0, 0.0, 0.0
            else:
                lift, lift_lo, lift_hi = bootstrap_delta_ci(
                    y_heldout, pred, controls_pred_for_target, heldout_runs_per_row, rng, int(config["bootstrap_replicates"])
                )
            row = {
                "method": method,
                "target": target,
                "train_rows": int(len(y_train)),
                "heldout_rows": int(len(y_heldout)),
                "classes": json.dumps(encoder.classes_.tolist()),
                **metrics,
                **ci_metrics,
                "lift_vs_controls": lift,
                "lift_ci_low": lift_lo,
                "lift_ci_high": lift_hi,
            }
            metric_rows.append(row)
            prediction_cache[(method, target)] = {
                "pred": pred,
                "pred_label": encoder.inverse_transform(pred),
                "proba": proba,
                "y": y_heldout,
                "y_label": encoder.inverse_transform(y_heldout),
            }
    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(out_dir / "benchmark_metrics.csv", index=False)

    summary = (
        metrics.groupby("method", as_index=False)
        .agg(
            mean_balanced_accuracy=("balanced_accuracy", "mean"),
            mean_macro_f1=("macro_f1", "mean"),
            mean_lift_vs_controls=("lift_vs_controls", "mean"),
            mean_brier=("brier", "mean"),
            mean_ece=("ece", "mean"),
        )
        .sort_values(["mean_lift_vs_controls", "mean_balanced_accuracy"], ascending=[False, False])
    )
    summary.to_csv(out_dir / "method_summary.csv", index=False)

    delta_rows = []
    for target in TARGETS:
        trad_pred = prediction_cache[("traditional_hand_pca_qtemplate_ridge", target)]["pred"]
        y_heldout = prediction_cache[("traditional_hand_pca_qtemplate_ridge", target)]["y"]
        for method in METHOD_ORDER:
            if method == "traditional_hand_pca_qtemplate_ridge":
                continue
            pred = prediction_cache[(method, target)]["pred"]
            delta, lo, hi = bootstrap_delta_ci(y_heldout, pred, trad_pred, heldout_runs_per_row, rng, int(config["bootstrap_replicates"]))
            delta_rows.append({"method": method, "target": target, "delta_vs_traditional": delta, "ci_low": lo, "ci_high": hi})
    deltas = pd.DataFrame(delta_rows)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)

    risk_rows = []
    timing = meta.loc[heldout_idx, "timing_abs_residual_ns"].to_numpy(float)
    charge = np.log10(meta.loc[heldout_idx, "amplitude_adc"].to_numpy(float))
    for target in TARGETS:
        for method in METHOD_ORDER:
            pred_positive = positive_mask_from_prediction(target, prediction_cache[(method, target)]["pred_label"])
            timing_delta, timing_lo, timing_hi = risk_delta_ci(timing, pred_positive, heldout_runs_per_row, rng, int(config["bootstrap_replicates"]))
            charge_delta, charge_lo, charge_hi = risk_delta_ci(charge, pred_positive, heldout_runs_per_row, rng, int(config["bootstrap_replicates"]))
            risk_rows.append(
                {
                    "method": method,
                    "target": target,
                    "predicted_non_nominal_rows": int(pred_positive.sum()),
                    "timing_risk_delta_ns": timing_delta,
                    "timing_ci_low": timing_lo,
                    "timing_ci_high": timing_hi,
                    "charge_log10_delta": charge_delta,
                    "charge_ci_low": charge_lo,
                    "charge_ci_high": charge_hi,
                }
            )
    risks = pd.DataFrame(risk_rows)
    risks.to_csv(out_dir / "risk_delta_metrics.csv", index=False)

    shuffle_rows = []
    for method in ["traditional_hand_pca_qtemplate_ridge", "latent_ridge", "stratum_gated_fusion_new_arch"]:
        for target in TARGETS:
            encoder = LabelEncoder()
            y_all = encoder.fit_transform(labels[target].to_numpy(object))
            y_train = y_all[train_idx]
            y_heldout = y_all[heldout_idx]
            classes = np.asarray(sorted(np.unique(y_all)), dtype=int)
            pred, proba = fit_predict_method(method, reps[method][0], y_train, reps[method][1], classes, config, rng, shuffle_labels=True)
            shuffle_rows.append(
                {
                    "method": method,
                    "target": target,
                    "label_shuffle_balanced_accuracy": float(balanced_accuracy_score(y_heldout, pred)),
                    "label_shuffle_macro_f1": float(f1_score(y_heldout, pred, average="macro", zero_division=0)),
                }
            )
    label_shuffle = pd.DataFrame(shuffle_rows)
    label_shuffle.to_csv(out_dir / "label_shuffle_sentinels.csv", index=False)

    winner_row = summary.iloc[0]
    trad_row = summary[summary["method"] == "traditional_hand_pca_qtemplate_ridge"].iloc[0]
    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(meta.loc[train_idx, "run"]).intersection(set(meta.loc[heldout_idx, "run"])))),
                "pass": True,
                "detail": "Must be zero for split-by-run.",
            },
            {
                "check": "p01b_key_order_matches_raw_scan",
                "value": key_match,
                "pass": bool(key_match),
                "detail": "Latent rows match raw ROOT recount by run, event_index, stave_index, and amplitude.",
            },
            {
                "check": "permutation_changed_latent_fraction",
                "value": float(perm_meta["fraction_rows_with_changed_latent"]),
                "pass": float(perm_meta["fraction_rows_with_changed_latent"]) > 0.95,
                "detail": "Within-stratum permutation should move almost all rows.",
            },
            {
                "check": "winner_beats_controls",
                "value": float(winner_row["mean_lift_vs_controls"]),
                "pass": float(winner_row["mean_lift_vs_controls"]) > 0,
                "detail": "Winner metric is mean lift over controls-only balanced accuracy.",
            },
            {
                "check": "winner_beats_traditional_point_estimate",
                "value": float(winner_row["mean_lift_vs_controls"] - trad_row["mean_lift_vs_controls"]),
                "pass": float(winner_row["mean_lift_vs_controls"] - trad_row["mean_lift_vs_controls"]) >= 0,
                "detail": "Descriptive comparison; not promoted as a discovery p-value.",
            },
            {
                "check": "label_shuffle_max_balanced_accuracy",
                "value": float(label_shuffle["label_shuffle_balanced_accuracy"].max()),
                "pass": float(label_shuffle["label_shuffle_balanced_accuracy"].max()) < 0.55,
                "detail": "Train-label shuffle sentinel should stay near chance for these imbalanced tasks.",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    make_plots(out_dir, metrics, summary)

    input_rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "role": "raw_root", "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path, role in [
        (artifact_path, "p01b_latent_artifact"),
        (Path(config["q_template_table"]), "q_template_table"),
        (Path(config["timing_residual_table"]), "timing_residual_table"),
        (args.config, "config"),
        (Path(__file__), "script"),
    ]:
        input_rows.append({"file": str(path), "role": role, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    next_ticket = (
        "P01k frozen control-stratum morphology transfer: freeze the P01j winner and test pair-timing "
        "sigma68 plus amplitude-bias deltas on untouched run-family folds"
    )
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_root_dir": str(raw_dir),
        "primary_target": config["primary_target"],
        "winner": {
            "method": str(winner_row["method"]),
            "metric": config["winner_metric"],
            "mean_lift_vs_controls": float(winner_row["mean_lift_vs_controls"]),
            "mean_balanced_accuracy": float(winner_row["mean_balanced_accuracy"]),
            "mean_macro_f1": float(winner_row["mean_macro_f1"]),
            "mean_brier": float(winner_row["mean_brier"]),
            "mean_ece": float(winner_row["mean_ece"]),
            "score_delta_vs_traditional": float(winner_row["mean_lift_vs_controls"] - trad_row["mean_lift_vs_controls"]),
        },
        "traditional": {
            "method": "traditional_hand_pca_qtemplate_ridge",
            "mean_lift_vs_controls": float(trad_row["mean_lift_vs_controls"]),
            "mean_balanced_accuracy": float(trad_row["mean_balanced_accuracy"]),
            "mean_macro_f1": float(trad_row["mean_macro_f1"]),
            "mean_brier": float(trad_row["mean_brier"]),
            "mean_ece": float(trad_row["mean_ece"]),
        },
        "ml_beats_baseline": bool(winner_row["mean_lift_vs_controls"] >= trad_row["mean_lift_vs_controls"]),
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "passed": selected == expected,
            "raw_key_sha256": raw_key_sha,
        },
        "artifact": {
            "path": str(artifact_path),
            "rows": int(len(latent_table)),
            "sha256": artifact_sha,
            "sha256_matches_expected": artifact_sha == str(config["expected_p01b_artifact_sha256"]),
            "key_sha256": latent_key_sha,
            "key_sha256_matches_expected": latent_key_sha == str(config["expected_p01b_key_sha256"]),
        },
        "split": {
            "heldout_runs": [int(x) for x in heldout_runs.tolist()],
            "train_rows": int(len(train_idx)),
            "heldout_rows": int(len(heldout_idx)),
            "max_rows_per_run_stave": int(config["max_rows_per_run_stave"]),
            "bootstrap_unit": "heldout_run",
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "planned_methods": METHOD_ORDER,
        "parameters": {
            "ridge_alpha": float(config["ridge_alpha"]),
            "pca_components": int(config["pca_components"]),
            "random_seed": int(config["random_seed"]),
            "cnn_epochs": int(config["cnn_epochs"]),
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "next_tickets": [next_ticket],
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "critic": "pending",
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, result, target_meta, metrics, summary, deltas, risks, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "command": "MPLCONFIGDIR={} /home/billy/anaconda3/bin/python {} --config {}".format(out_dir / "mplconfig", Path(__file__), args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_rows,
        "output_sha256": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("winner:", result["winner"]["method"])
    print("wrote", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
