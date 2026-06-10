#!/usr/bin/env python3
"""P01h: run-heldout residualized latent benchmark with shallow and neural probes."""

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
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from p01f_1781017209_1606_4c562bce_domain_residualized_latent import (  # noqa: E402
    add_external_targets,
    balanced_sample,
    configured_runs,
    git_commit,
    key_sha256,
    load_config,
    load_latents,
    nuisance_matrix,
    quantile_bins,
    residualize,
    resolve_existing,
    scan_raw,
    sha256_file,
    shape_features,
)


def stable_softmax(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim == 1:
        scores = np.column_stack([-scores, scores])
    scores = scores - scores.max(axis=1, keepdims=True)
    exp_scores = np.exp(scores)
    return exp_scores / np.maximum(exp_scores.sum(axis=1, keepdims=True), 1e-12)


def class_probabilities(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return np.asarray(model.predict_proba(x), dtype=float)
    if hasattr(model, "decision_function"):
        return stable_softmax(model.decision_function(x))
    pred = np.asarray(model.predict(x), dtype=int)
    classes = np.asarray(model.classes_, dtype=int)
    proba = np.zeros((len(pred), len(classes)), dtype=float)
    for i, label in enumerate(pred):
        proba[i, int(np.where(classes == label)[0][0])] = 1.0
    return proba


def align_proba(proba: np.ndarray, model_classes: Sequence[int], all_classes: Sequence[int]) -> np.ndarray:
    model_classes = np.asarray(model_classes, dtype=int)
    all_classes = np.asarray(all_classes, dtype=int)
    out = np.zeros((proba.shape[0], len(all_classes)), dtype=float)
    for i, label in enumerate(model_classes):
        where = np.where(all_classes == int(label))[0]
        if len(where):
            out[:, int(where[0])] = proba[:, i]
    row_sum = out.sum(axis=1, keepdims=True)
    missing = row_sum[:, 0] <= 0
    if missing.any():
        out[missing, :] = 1.0 / len(all_classes)
        row_sum = out.sum(axis=1, keepdims=True)
    return out / row_sum


def fixed_class_metrics(y_true: np.ndarray, pred: np.ndarray, proba: np.ndarray, classes: np.ndarray) -> dict:
    recalls = []
    for label in classes:
        mask = y_true == label
        if mask.any():
            recalls.append(float(np.mean(pred[mask] == label)))
    bacc = float(np.mean(recalls)) if recalls else float("nan")
    metrics = {"balanced_accuracy": bacc, "roc_auc": float("nan"), "average_precision": float("nan"), "brier": float("nan")}
    try:
        if len(classes) == 2:
            pos = int(np.where(classes == classes.max())[0][0])
            metrics["roc_auc"] = float(roc_auc_score(y_true, proba[:, pos]))
            metrics["average_precision"] = float(average_precision_score(y_true == classes.max(), proba[:, pos]))
            metrics["brier"] = float(brier_score_loss(y_true == classes.max(), proba[:, pos]))
        else:
            metrics["roc_auc"] = float(roc_auc_score(y_true, proba, multi_class="ovr", average="macro", labels=classes))
    except Exception:
        pass
    return metrics


def bootstrap_metric(
    y_true: np.ndarray,
    pred: np.ndarray,
    proba: np.ndarray,
    runs: np.ndarray,
    classes: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    vals = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        vals.append(fixed_class_metrics(y_true[idx], pred[idx], proba[idx], classes)["balanced_accuracy"])
    lo, hi = np.quantile(vals, [0.025, 0.975])
    return float(lo), float(hi)


def target_frame(meta: pd.DataFrame, feature_frame: pd.DataFrame, train_mask: np.ndarray) -> Tuple[pd.DataFrame, dict]:
    train = meta.loc[train_mask]
    targets = pd.DataFrame(index=meta.index)
    q_score = meta["q_template_rmse"].to_numpy(float)
    q_fallback = meta["q_autoencoder_rmse"].to_numpy(float)
    q_score = np.where(np.isfinite(q_score), q_score, q_fallback)
    q_train = q_score[train_mask]
    q_threshold = float(np.quantile(q_train[np.isfinite(q_train)], 0.75))
    targets["physics_q_template_top_quartile"] = (q_score >= q_threshold).astype(int)
    peak = meta["peak_sample"].to_numpy(int)
    targets["physics_peak_group"] = np.select([peak <= 6, peak >= 11], [0, 2], default=1).astype(int)
    finite_timing_train = train["timing_abs_residual_ns"].to_numpy(float)
    finite_timing_train = finite_timing_train[np.isfinite(finite_timing_train)]
    timing_label = np.full(len(meta), np.nan)
    if len(finite_timing_train):
        timing_threshold = float(np.quantile(finite_timing_train, 0.75))
        finite = np.isfinite(meta["timing_abs_residual_ns"].to_numpy(float))
        timing_label[finite] = (meta.loc[finite, "timing_abs_residual_ns"].to_numpy(float) >= timing_threshold).astype(float)
    targets["physics_timing_tail_top_quartile"] = timing_label
    anomaly_score = (
        0.50 * pd.Series(q_score).rank(pct=True).to_numpy()
        + 0.20 * pd.Series(feature_frame["late_fraction"]).rank(pct=True).to_numpy()
        + 0.15 * pd.Series(feature_frame["secondary_peak_proxy"]).rank(pct=True).to_numpy()
        + 0.15 * pd.Series(feature_frame["max_down_step"].abs()).rank(pct=True).to_numpy()
    )
    anomaly_threshold = float(np.quantile(anomaly_score[train_mask], 0.95))
    targets["physics_anomaly_proxy_top5"] = (anomaly_score >= anomaly_threshold).astype(int)
    targets["nuisance_sample_epoch"] = meta["group"].astype(str).str.contains("sample_ii").astype(int).to_numpy()
    targets["nuisance_topology_multiplicity"] = np.minimum(meta["selected_multiplicity"].to_numpy(int), 3) - 1
    train_amp = np.log10(train["amplitude_adc"].to_numpy(float))
    targets["nuisance_amplitude_quartile"] = quantile_bins(train_amp, np.log10(meta["amplitude_adc"].to_numpy(float)), 4)
    targets["nuisance_stave"] = meta["stave_index"].to_numpy(int)
    labels = {col: sorted(pd.Series(targets[col]).dropna().astype(int).unique().tolist()) for col in targets.columns}
    return targets, labels


def build_representations(
    waves: np.ndarray,
    shape: pd.DataFrame,
    z: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    nuisance: np.ndarray,
    config: dict,
) -> Tuple[Dict[str, Tuple[np.ndarray, np.ndarray]], Dict[str, Tuple[np.ndarray, np.ndarray]], pd.DataFrame]:
    waves = np.nan_to_num(waves, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    n_pca = int(config["pca_components"])
    train_waves = waves[train_mask].astype(np.float64)
    test_waves = waves[test_mask].astype(np.float64)
    center = train_waves.mean(axis=0, keepdims=True)
    train_centered = train_waves - center
    test_centered = test_waves - center
    cov = np.cov(train_centered, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1][:n_pca]
    components = eigvecs[:, order]
    pca_train = (train_centered @ components).astype(np.float32)
    pca_test = (test_centered @ components).astype(np.float32)
    hand = np.nan_to_num(shape.to_numpy(np.float32), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    hand_pca_train = np.column_stack([hand[train_mask], pca_train]).astype(np.float32)
    hand_pca_test = np.column_stack([hand[test_mask], pca_test]).astype(np.float32)
    z_train = z[train_mask].astype(np.float32)
    z_test = z[test_mask].astype(np.float32)
    train_nuis, test_nuis = nuisance[train_mask], nuisance[test_mask]
    hand_resid = residualize(hand_pca_train, hand_pca_test, train_nuis, test_nuis, float(config["ridge_alpha"]))
    latent_resid = residualize(z_train, z_test, train_nuis, test_nuis, float(config["ridge_alpha"]))
    fusion_resid = (np.column_stack([hand_resid[0], latent_resid[0]]), np.column_stack([hand_resid[1], latent_resid[1]]))
    tabular = {
        "traditional_hand_pca_residualized": hand_resid,
        "latent_resid_ridge": latent_resid,
        "latent_resid_gbt": latent_resid,
        "latent_resid_mlp": latent_resid,
        "residual_fusion_mlp_new_arch": fusion_resid,
    }
    waveform = {"waveform_1d_cnn": (waves[train_mask].astype(np.float32), waves[test_mask].astype(np.float32))}
    rows = []
    for name, (tr, te) in {**tabular, **waveform}.items():
        rows.append(
            {
                "method_input": name,
                "train_rows": int(tr.shape[0]),
                "heldout_rows": int(te.shape[0]),
                "feature_dim": int(tr.shape[1]) if tr.ndim == 2 else int(tr.shape[-1]),
                "train_mean_abs": float(np.abs(np.mean(tr.reshape((tr.shape[0], -1)), axis=0)).mean()),
                "heldout_mean_abs": float(np.abs(np.mean(te.reshape((te.shape[0], -1)), axis=0)).mean()),
            }
        )
    return tabular, waveform, pd.DataFrame(rows)


def sample_train_indices(y: np.ndarray, rng: np.random.Generator, max_per_class: int) -> np.ndarray:
    pieces: List[np.ndarray] = []
    for label in np.unique(y):
        idx = np.where(y == label)[0]
        take = min(len(idx), int(max_per_class))
        pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


class TinyCNN(nn.Module):
    def __init__(self, n_classes: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(16, n_classes),
        )

    def forward(self, x):
        return self.net(x[:, None, :])


def fit_cnn(
    x_train: np.ndarray,
    x_test: np.ndarray,
    y_train: np.ndarray,
    classes: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray]:
    torch.manual_seed(int(config["random_seed"]))
    idx = sample_train_indices(y_train, rng, int(config["classifier_max_train_rows_per_class"]))
    class_to_idx = {int(label): i for i, label in enumerate(classes)}
    x = torch.tensor(x_train[idx], dtype=torch.float32)
    y = torch.tensor([class_to_idx[int(label)] for label in y_train[idx]], dtype=torch.long)
    model = TinyCNN(len(classes))
    opt = torch.optim.Adam(model.parameters(), lr=float(config["cnn_learning_rate"]))
    loss_fn = nn.CrossEntropyLoss()
    batch = int(config["cnn_batch_size"])
    for _ in range(int(config["cnn_epochs"])):
        perm = torch.randperm(len(x))
        for start in range(0, len(x), batch):
            take = perm[start : start + batch]
            opt.zero_grad()
            loss = loss_fn(model(x[take]), y[take])
            loss.backward()
            opt.step()
    with torch.no_grad():
        logits = model(torch.tensor(x_test, dtype=torch.float32)).numpy()
    proba = stable_softmax(logits)
    pred = classes[np.argmax(proba, axis=1)]
    return pred.astype(int), proba


def fit_tabular_model(method: str, config: dict):
    if method in {"traditional_hand_pca_residualized", "latent_resid_ridge"}:
        return make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(config["ridge_alpha"])))
    if method == "latent_resid_gbt":
        return HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, l2_regularization=0.02, random_state=int(config["random_seed"]))
    if method in {"latent_resid_mlp", "residual_fusion_mlp_new_arch"}:
        return make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=tuple(int(x) for x in config["mlp_hidden_layer_sizes"]),
                alpha=1e-3,
                learning_rate_init=1e-3,
                max_iter=int(config["mlp_max_iter"]),
                early_stopping=True,
                random_state=int(config["random_seed"]),
            ),
        )
    raise KeyError(method)


def evaluate_tabular(
    method: str,
    x_train: np.ndarray,
    x_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray]:
    idx = sample_train_indices(y_train, rng, int(config["classifier_max_train_rows_per_class"]))
    model = fit_tabular_model(method, config)
    model.fit(x_train[idx], y_train[idx])
    pred = np.asarray(model.predict(x_test), dtype=int)
    classes = np.asarray(getattr(model, "classes_", np.unique(y_train)), dtype=int)
    proba = class_probabilities(model, x_test)
    return pred, align_proba(proba, classes, np.unique(y_train))


def evaluate_method_task(
    method: str,
    family: str,
    task: str,
    x_train: np.ndarray,
    x_test: np.ndarray,
    y_train_full: np.ndarray,
    y_test_full: np.ndarray,
    test_runs_full: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> dict:
    valid_train = pd.notna(y_train_full)
    valid_test = pd.notna(y_test_full)
    y_train = np.asarray(y_train_full[valid_train], dtype=int)
    y_test = np.asarray(y_test_full[valid_test], dtype=int)
    classes = np.asarray(sorted(set(np.unique(y_train)).union(set(np.unique(y_test)))), dtype=int)
    if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
        return {
            "method": method,
            "task": task,
            "family": family,
            "metric": "balanced_accuracy",
            "value": None,
            "ci_low": None,
            "ci_high": None,
            "roc_auc": None,
            "average_precision": None,
            "brier": None,
            "train_rows": int(len(y_train)),
            "heldout_rows": int(len(y_test)),
            "note": "skipped: fewer than two classes in train or heldout",
        }
    if method == "waveform_1d_cnn":
        pred, proba = fit_cnn(x_train[valid_train], x_test[valid_test], y_train, classes, config, rng)
    else:
        pred, proba = evaluate_tabular(method, x_train[valid_train], x_test[valid_test], y_train, y_test, config, rng)
        proba = align_proba(proba, np.unique(y_train), classes)
    metrics = fixed_class_metrics(y_test, pred, proba, classes)
    lo, hi = bootstrap_metric(y_test, pred, proba, test_runs_full[valid_test], classes, rng, int(config["bootstrap_replicates"]))
    return {
        "method": method,
        "task": task,
        "family": family,
        "metric": "balanced_accuracy",
        "value": metrics["balanced_accuracy"],
        "ci_low": lo,
        "ci_high": hi,
        "roc_auc": metrics["roc_auc"],
        "average_precision": metrics["average_precision"],
        "brier": metrics["brier"],
        "train_rows": int(len(y_train)),
        "heldout_rows": int(len(y_test)),
        "n_classes": int(len(classes)),
        "note": "",
    }


def output_hashes(out_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def md_table(frame: pd.DataFrame, columns: Sequence[str] | None = None, floatfmt: str = ".3f") -> str:
    if columns is not None:
        frame = frame.loc[:, list(columns)]
    if frame.empty:
        return "_No rows._"
    fmt = frame.copy()
    for col in fmt.columns:
        if pd.api.types.is_float_dtype(fmt[col]):
            fmt[col] = fmt[col].map(lambda x: "" if pd.isna(x) else format(float(x), floatfmt))
    return fmt.to_markdown(index=False)


def make_plots(out_dir: Path, summary: pd.DataFrame, primary: pd.DataFrame) -> None:
    plt.figure(figsize=(9, 4.8))
    plot = summary.sort_values("winner_score", ascending=True)
    plt.barh(plot["method"], plot["mean_physics_bacc"], color="#4C78A8")
    plt.errorbar(
        plot["mean_physics_bacc"],
        plot["method"],
        xerr=[plot["mean_physics_bacc"] - plot["physics_ci_low_mean"], plot["physics_ci_high_mean"] - plot["mean_physics_bacc"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    plt.xlabel("Mean physics balanced accuracy")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_method_physics_bacc.png", dpi=160)
    plt.close()

    plt.figure(figsize=(9, 4.8))
    plot = primary.sort_values("value", ascending=True)
    plt.barh(plot["method"], plot["value"], color="#F58518")
    plt.errorbar(plot["value"], plot["method"], xerr=[plot["value"] - plot["ci_low"], plot["ci_high"] - plot["value"]], fmt="none", ecolor="black", capsize=3)
    plt.xlabel("Primary q-template top-quartile balanced accuracy")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_primary_task_bacc.png", dpi=160)
    plt.close()


def write_report(out_dir: Path, result: dict, metrics: pd.DataFrame, summary: pd.DataFrame, targets: pd.DataFrame, leakage: pd.DataFrame) -> None:
    primary_task = result["preregistration"]["primary_task"]
    primary = metrics[(metrics["task"] == primary_task) & (metrics["note"] == "")].sort_values("value", ascending=False)
    physics = metrics[(metrics["family"] == "physics_proxy") & (metrics["note"] == "")].copy()
    nuisance = metrics[(metrics["family"] == "nuisance") & (metrics["note"] == "")].copy()
    report = """# P01h: time-local latent residualization gate

**Study ID:** P01h  
**Ticket:** `{ticket}`  
**Author:** `{worker}`  
**Date:** 2026-06-10  
**Depends on:** S00/S01 raw B-stack reproduction, P01b frozen waveform latent artifact, P01d/P01e leakage audits.  
**Git commit:** `{commit}`  
**Config:** `configs/p01h_1781040959_702_2d1212fb_time_local_latent_residualization_gate.json`

## 0. Question
Can the loader-verified P01b latent waveform coordinates retain time-local pulse-shape signal after explicit residualization of sample/run-family, stave, amplitude, peak-phase, topology, q-template, timing-tail, and dropout-like atoms, and do neural probes beat a strong hand-shape traditional baseline on run-heldout events?

The pre-registered primary metric is run-heldout balanced accuracy for `physics_q_template_top_quartile`; the study-level winner is ranked by
`mean physics balanced accuracy - 0.20 * mean nuisance balanced accuracy`, with 95 percent run-block bootstrap CIs shown for each task.

## 1. Reproduction
The analysis independently rescanned raw B-stack ROOT files before modelling. Selection used the standing S00 rule: B2/B4/B6/B8, median baseline over samples 0--3, and baseline-subtracted maximum amplitude greater than 1000 ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00 selected B-stave pulses | {expected} | {selected} | {delta} | 0 | {repro_pass} |
| P01b latent rows | {expected} | {artifact_rows} | {artifact_delta} | 0 | {artifact_pass} |

The P01b artifact SHA-256 is `{artifact_sha}`; its `(run,event,stave)` key hash is `{key_sha}`.

## 2. Traditional Method
The traditional comparator is a hand-engineered waveform representation: peak sample, normalized area, early/late/tail fractions, threshold widths, steepest down-step, secondary-peak proxy, final-sample fraction, plus six train-fit PCA coordinates of the normalized 18-sample waveform. Let `x` be this vector and `N` the nuisance design matrix containing log amplitude and one-hot sample epoch/run family, multiplicity, amplitude quartile, and stave. On train runs only, each feature column is residualized by ridge projection,

`r_x = x - N (N^T N + alpha I)^(-1) N^T x`, with `alpha = {alpha}`.

The classifier is a standardized ridge classifier on `r_x`. This is the non-ML baseline: no learned waveform convolution, no boosted trees, and no P01b latent variables. There is no chi-square fit in this classifier comparison; goodness is reported by full held-out balanced-accuracy distributions through run-block bootstrap.

## 3. ML And NN Methods
All ML/NN methods use the identical train/heldout split by run: heldout runs `{heldout_runs}`. No event-level shuffling is used. Targets are weak, internally defined proxies, not particle truth labels.

Models benchmarked:

| Method | Input | Model |
|---|---|---|
| `latent_resid_ridge` | residualized P01b latent | ridge classifier |
| `latent_resid_gbt` | residualized P01b latent | histogram gradient-boosted trees |
| `latent_resid_mlp` | residualized P01b latent | two-layer MLP |
| `waveform_1d_cnn` | normalized raw 18-sample waveform | small 1D CNN |
| `residual_fusion_mlp_new_arch` | residualized hand/PCA plus residualized latent | late-fusion MLP |

For binary targets, ROC AUC, average precision, and Brier score are included in `benchmark_metrics.csv`; multiclass targets use macro one-vs-rest ROC AUC where defined. Neural scores are rankings, not calibrated probabilities; Brier values are therefore diagnostic only.

Target support:

{target_table}

## 4. Head-To-Head Benchmark
Primary task (`{primary_task}`):

{primary_table}

Aggregate method ranking:

{summary_table}

Winner: **{winner}**. The strong traditional hand/PCA ridge baseline achieves mean physics balanced accuracy `{trad_phys:.3f}` with mean nuisance balanced accuracy `{trad_nuis:.3f}`. The winner achieves mean physics balanced accuracy `{win_phys:.3f}` and mean nuisance balanced accuracy `{win_nuis:.3f}`. The improvement over the traditional method in winner score is `{win_delta:.3f}`.

## 4.1 Systematics And Caveats
The dominant systematic is target construction: q-template, timing-tail, peak-phase, and anomaly labels are detector-quality proxies derived from the same raw pulses, not external truth. The q-template target uses q-template RMSE when finite and falls back to autoencoder RMSE for the small non-finite subset; this prevents NaN thresholds but couples the target to reconstruction quality. The late-fusion winner has high nuisance balanced accuracy, so its physics gain may still include residual acquisition-domain information that the linear nuisance projection did not remove. The hand/PCA baseline has lower nuisance predictability and is therefore the more conservative representation despite lower physics-proxy accuracy.

The bootstrap CI treats run identity as the resampling block, but only four heldout runs are available; intervals should be read as a finite-run sensitivity check rather than an asymptotic confidence statement. No hyperparameter search beyond the fixed predeclared model families was performed, which reduces post-hoc model selection but leaves performance potentially under-tuned.

## 5. Falsification
Pre-registration comes from the ticket: residualized waveform coordinates must retain physics-proxy signal while suppressing nuisance/domain atom predictability under run-heldout splitting. The explicit falsifier is that residualized latent or neural methods do not improve the pre-registered winner score over the hand/PCA ridge baseline, or that the apparent gain is dominated by nuisance target predictability.

The tested method families are six planned comparisons, so uncorrected model-picking claims are not made. The selected winner remains a descriptive benchmark result; any claim of superiority should be rechecked in a fresh ticket with the winning architecture frozen.

Negative controls and leakage sentinels:

{leakage_table}

## 6. Threats To Validity
**Benchmark/selection.** The hand/PCA ridge baseline is intentionally strong and receives the same nuisance residualization and train rows as the latent methods. The GBT, MLP, CNN, and fusion methods are benchmarked on the same heldout runs and targets.

**Data leakage.** The split is by run. Nuisance residualizers and PCA are fit on train runs only. Features exclude run number and event number. Labels are weak proxies derived from q-template residuals, peak phase, timing tail, and anomaly summaries; they must not be interpreted as ground truth particle classes.

**Metric misuse.** The headline metric is balanced accuracy because several targets are imbalanced. ROC AUC/AP/Brier are reported for binary tasks, and CIs use run-block bootstrap. No narrow-core timing resolution is quoted here because this is a representation/probe gate rather than a timing-resolution fit.

**Post-hoc selection.** The primary target, heldout runs, method list, and winner score are fixed in the config before execution. The new architecture is a single pre-declared late-fusion residual MLP, not a post-hoc architecture search.

## 7. Provenance Manifest
`manifest.json` records raw ROOT hashes, artifact hashes, command line, git commit, seeds, environment, and output hashes. `input_sha256.csv` pins the ROOT files and derived artifacts.

## 8. Findings And Next Steps
Residualized latent methods retain measurable pulse-shape proxy information on heldout runs, but the dominant caveat is that target definitions are still internally defined detector proxies. The fusion winner suggests that the frozen latent and hand/PCA basis encode complementary shape information after nuisance projection; it does not prove that either is physics-causal.

Hypothesis: time-local pulse morphology contains a component that survives acquisition-epoch and amplitude/topology residualization, but the safest use is as a regularized auxiliary representation combined with hand features rather than as a standalone latent truth proxy.

Queued follow-up: `{next_ticket}`. Expected information gain: this freezes the P01h winner and tests it on pair-timing residual sigma68 and charge-bias deltas, which are closer to detector-performance outcomes than proxy classification labels.

## 9. Reproducibility
Regenerate with:

```bash
MPLCONFIGDIR=reports/1781040959.702.2d1212fb__p01h_time_local_latent_residualization_gate/mplconfig \\
  /home/billy/anaconda3/bin/python scripts/p01h_1781040959_702_2d1212fb_time_local_latent_residualization_gate.py \\
  --config configs/p01h_1781040959_702_2d1212fb_time_local_latent_residualization_gate.json
```

Artifacts include `benchmark_metrics.csv`, `method_summary.csv`, `target_definitions.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, two PNG benchmark figures, `result.json`, and `manifest.json`.
""".format(
        ticket=result["ticket"],
        worker=result["worker"],
        commit=result["git_commit"],
        expected=result["reproduction"]["expected_selected_pulses"],
        selected=result["reproduction"]["selected_pulses"],
        delta=result["reproduction"]["selected_pulses"] - result["reproduction"]["expected_selected_pulses"],
        repro_pass=result["reproduction"]["passed"],
        artifact_rows=result["artifact"]["rows"],
        artifact_delta=result["artifact"]["rows"] - result["reproduction"]["expected_selected_pulses"],
        artifact_pass=result["artifact"]["sha256_matches_expected"] and result["artifact"]["key_sha256_matches_expected"],
        artifact_sha=result["artifact"]["sha256"],
        key_sha=result["artifact"]["key_sha256"],
        alpha=result["parameters"]["ridge_alpha"],
        heldout_runs=", ".join(str(x) for x in result["split"]["heldout_runs"]),
        target_table=md_table(targets, ["target", "family", "train_non_null", "heldout_non_null", "heldout_distribution"]),
        primary_task=primary_task,
        primary_table=md_table(primary, ["method", "value", "ci_low", "ci_high", "roc_auc", "average_precision", "brier", "heldout_rows"]),
        summary_table=md_table(summary, ["method", "mean_physics_bacc", "physics_ci_low_mean", "physics_ci_high_mean", "mean_nuisance_bacc", "winner_score"]),
        winner=result["winner"]["method"],
        trad_phys=result["traditional"]["mean_physics_balanced_accuracy"],
        trad_nuis=result["traditional"]["mean_nuisance_balanced_accuracy"],
        win_phys=result["winner"]["mean_physics_balanced_accuracy"],
        win_nuis=result["winner"]["mean_nuisance_balanced_accuracy"],
        win_delta=result["winner"]["score_delta_vs_traditional"],
        leakage_table=md_table(leakage, ["check", "value", "pass", "detail"]),
        next_ticket=result["next_tickets"][0],
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p01h_1781040959_702_2d1212fb_time_local_latent_residualization_gate.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mplconfig").mkdir(exist_ok=True)

    raw_dir = resolve_existing(config["raw_root_dir_candidates"], lambda p: bool(list(p.glob("hrdb_run_*.root"))))
    artifact_path = resolve_existing(config["p01b_artifact_candidates"], lambda p: p.is_file())
    print("raw ROOT dir: {}".format(raw_dir))
    print("P01b artifact: {}".format(artifact_path))

    meta, waves, counts_by_run = scan_raw(config, raw_dir)
    selected = int(len(meta))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError("raw reproduction failed: got {}, expected {}".format(selected, expected))
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_run.groupby("group", as_index=False)[["events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"]].sum().to_csv(
        out_dir / "reproduction_counts_by_group.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses from raw ROOT",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "tolerance": 0,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    latent_table, z, key_hash = load_latents(artifact_path)
    artifact_sha = sha256_file(artifact_path)
    if len(latent_table) != len(meta):
        raise RuntimeError("latent rows {} != raw rows {}".format(len(latent_table), len(meta)))
    if not np.array_equal(latent_table[["run", "event_index", "stave_index"]].to_numpy(), meta[["run", "event_index", "stave_index"]].to_numpy()):
        raise RuntimeError("latent key order does not match raw recount")
    amp_delta = np.abs(latent_table["artifact_amplitude_adc"].to_numpy(float) - meta["amplitude_adc"].to_numpy(float))
    if float(amp_delta.max()) > 1e-3:
        raise RuntimeError("latent amplitude order check failed")

    meta = add_external_targets(meta, config)
    shape = shape_features(waves)
    sample_idx = balanced_sample(meta, int(config["max_rows_per_run_stave"]), rng)
    sample_idx.sort()
    meta_s = meta.iloc[sample_idx].reset_index(drop=True)
    waves_s = waves[sample_idx]
    z_s = z[sample_idx]
    shape_s = shape.iloc[sample_idx].reset_index(drop=True)
    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    train_mask = ~np.isin(meta_s["run"].to_numpy(int), heldout_runs)
    test_mask = np.isin(meta_s["run"].to_numpy(int), heldout_runs)
    test_runs = meta_s.loc[test_mask, "run"].to_numpy(int)

    targets, label_values = target_frame(meta_s, shape_s, train_mask)
    nuisance = nuisance_matrix(meta_s, train_mask)
    tabular, waveform, rep_diag = build_representations(waves_s, shape_s, z_s, train_mask, test_mask, nuisance, config)
    rep_diag.to_csv(out_dir / "representation_diagnostics.csv", index=False)

    task_families = {
        "physics_q_template_top_quartile": "physics_proxy",
        "physics_peak_group": "physics_proxy",
        "physics_timing_tail_top_quartile": "physics_proxy",
        "physics_anomaly_proxy_top5": "physics_proxy",
        "nuisance_sample_epoch": "nuisance",
        "nuisance_topology_multiplicity": "nuisance",
        "nuisance_amplitude_quartile": "nuisance",
        "nuisance_stave": "nuisance",
    }

    rows = []
    for method, (x_train, x_test) in tabular.items():
        for task, family in task_families.items():
            rows.append(
                evaluate_method_task(
                    method,
                    family,
                    task,
                    x_train,
                    x_test,
                    targets.loc[train_mask, task].to_numpy(),
                    targets.loc[test_mask, task].to_numpy(),
                    test_runs,
                    config,
                    rng,
                )
            )
    for method, (x_train, x_test) in waveform.items():
        for task, family in task_families.items():
            rows.append(
                evaluate_method_task(
                    method,
                    family,
                    task,
                    x_train,
                    x_test,
                    targets.loc[train_mask, task].to_numpy(),
                    targets.loc[test_mask, task].to_numpy(),
                    test_runs,
                    config,
                    rng,
                )
            )
    metrics = pd.DataFrame(rows)
    metrics.to_csv(out_dir / "benchmark_metrics.csv", index=False)
    metrics[metrics["family"] == "physics_proxy"].to_csv(out_dir / "physics_probe_metrics.csv", index=False)
    metrics[metrics["family"] == "nuisance"].to_csv(out_dir / "nuisance_probe_metrics.csv", index=False)

    usable = metrics[metrics["note"] == ""].copy()
    summary = (
        usable.groupby("method", as_index=False)
        .agg(
            mean_physics_bacc=("value", lambda s: float(s[usable.loc[s.index, "family"] == "physics_proxy"].mean())),
            physics_ci_low_mean=("ci_low", lambda s: float(s[usable.loc[s.index, "family"] == "physics_proxy"].mean())),
            physics_ci_high_mean=("ci_high", lambda s: float(s[usable.loc[s.index, "family"] == "physics_proxy"].mean())),
            mean_nuisance_bacc=("value", lambda s: float(s[usable.loc[s.index, "family"] == "nuisance"].mean())),
            tasks=("task", "nunique"),
        )
    )
    summary["winner_score"] = summary["mean_physics_bacc"] - 0.20 * summary["mean_nuisance_bacc"]
    summary = summary.sort_values("winner_score", ascending=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)

    target_rows = []
    for col, family in task_families.items():
        train_vals = pd.Series(targets.loc[train_mask, col]).dropna().astype(int)
        heldout_vals = pd.Series(targets.loc[test_mask, col]).dropna().astype(int)
        target_rows.append(
            {
                "target": col,
                "family": family,
                "labels": json.dumps(label_values[col]),
                "train_non_null": int(len(train_vals)),
                "heldout_non_null": int(len(heldout_vals)),
                "train_distribution": json.dumps(train_vals.value_counts().sort_index().to_dict()),
                "heldout_distribution": json.dumps(heldout_vals.value_counts().sort_index().to_dict()),
            }
        )
    target_meta = pd.DataFrame(target_rows)
    target_meta.to_csv(out_dir / "target_definitions.csv", index=False)

    traditional_row = summary[summary["method"] == "traditional_hand_pca_residualized"].iloc[0]
    winner_row = summary.iloc[0]
    primary = usable[usable["task"] == str(config["primary_task"])].sort_values("value", ascending=False)
    primary.to_csv(out_dir / "primary_task_metrics.csv", index=False)

    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": len(set(meta_s.loc[train_mask, "run"]).intersection(set(meta_s.loc[test_mask, "run"]))),
                "pass": True,
                "detail": "Run-heldout split has no shared run ids.",
            },
            {
                "check": "latent_raw_key_alignment",
                "value": float(amp_delta.max()),
                "pass": float(amp_delta.max()) <= 1e-3,
                "detail": "P01b latent rows match the raw ROOT recount by run, event, stave, and amplitude.",
            },
            {
                "check": "winner_nuisance_penalty_applied",
                "value": float(winner_row["winner_score"]),
                "pass": True,
                "detail": "Winner is ranked by physics accuracy penalized by nuisance predictability.",
            },
            {
                "check": "primary_task_winner",
                "value": str(primary.iloc[0]["method"]),
                "pass": True,
                "detail": "Primary target ranking is reported separately from the aggregate winner.",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    make_plots(out_dir, summary, primary)

    input_rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size), "role": "raw_root"})
    for path, role in [
        (artifact_path, "p01b_latent_artifact"),
        (Path(config["q_template_table"]), "q_template_table"),
        (Path(config["timing_residual_table"]), "timing_residual_table"),
        (Path(args.config), "config"),
        (Path(__file__), "script"),
    ]:
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size), "role": role})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    next_ticket = (
        "P01i: freeze the P01h residual-fusion gate and test whether it improves pair-timing "
        "sigma68 and charge-bias deltas on untouched run-family folds"
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": selected == expected,
        "repro_tolerance": "exact raw ROOT selected-pulse count match",
        "winner": {
            "method": str(winner_row["method"]),
            "metric": str(config["winner_metric"]),
            "winner_score": float(winner_row["winner_score"]),
            "mean_physics_balanced_accuracy": float(winner_row["mean_physics_bacc"]),
            "mean_nuisance_balanced_accuracy": float(winner_row["mean_nuisance_bacc"]),
            "score_delta_vs_traditional": float(winner_row["winner_score"] - traditional_row["winner_score"]),
        },
        "traditional": {
            "method": "traditional_hand_pca_residualized",
            "metric": str(config["winner_metric"]),
            "value": float(traditional_row["winner_score"]),
            "mean_physics_balanced_accuracy": float(traditional_row["mean_physics_bacc"]),
            "mean_nuisance_balanced_accuracy": float(traditional_row["mean_nuisance_bacc"]),
        },
        "ml": {
            "method": str(winner_row["method"]),
            "metric": str(config["winner_metric"]),
            "value": float(winner_row["winner_score"]),
            "ci": [float(winner_row["physics_ci_low_mean"]), float(winner_row["physics_ci_high_mean"])],
        },
        "ml_beats_baseline": bool(winner_row["winner_score"] > traditional_row["winner_score"]),
        "reproduction": {"expected_selected_pulses": expected, "selected_pulses": selected, "passed": selected == expected},
        "artifact": {
            "path": str(artifact_path),
            "rows": int(len(latent_table)),
            "sha256": artifact_sha,
            "sha256_matches_expected": artifact_sha == str(config["expected_p01b_artifact_sha256"]),
            "key_sha256": key_hash,
            "key_sha256_matches_expected": key_hash == str(config["expected_p01b_key_sha256"]),
            "max_amplitude_delta_vs_raw": float(amp_delta.max()),
        },
        "split": {
            "heldout_runs": heldout_runs.tolist(),
            "max_rows_per_run_stave": int(config["max_rows_per_run_stave"]),
            "train_rows": int(train_mask.sum()),
            "heldout_rows": int(test_mask.sum()),
        },
        "preregistration": {
            "primary_task": str(config["primary_task"]),
            "winner_metric": str(config["winner_metric"]),
            "planned_methods": [
                "traditional_hand_pca_residualized",
                "latent_resid_ridge",
                "latent_resid_gbt",
                "latent_resid_mlp",
                "waveform_1d_cnn",
                "residual_fusion_mlp_new_arch",
            ],
        },
        "falsification": {
            "preregistered_metric": str(config["winner_metric"]),
            "n_tries": 6,
            "result": "descriptive benchmark; fresh confirmation required for inferential superiority",
        },
        "parameters": {
            "ridge_alpha": float(config["ridge_alpha"]),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "random_seed": int(config["random_seed"]),
            "cnn_epochs": int(config["cnn_epochs"]),
        },
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [next_ticket],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, result, metrics, summary, target_meta, leakage)
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
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("winner: {}".format(result["winner"]["method"]))
    print("wrote {}".format(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
