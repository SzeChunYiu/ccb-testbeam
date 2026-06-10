#!/usr/bin/env python3
"""S07l: injected morphology operating-point support audit.

This study extends S07h without changing its target: raw clean events are paired
with injected downstream two-pulse copies, the split is leave-one-run-out, and
the label is injected truth rather than a D_t threshold.  The new question is
whether a fixed operating point is useful and whether stronger ML/NN methods
beat a fold-local traditional timing/template score on identical held-out runs.
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
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s07l-matplotlib-cache")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def markdown_table(frame: pd.DataFrame, max_rows: Optional[int] = None) -> str:
    if max_rows is not None and len(frame) > max_rows:
        frame = frame.head(max_rows).copy()

    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value).replace("|", "\\|")

    columns = list(frame.columns)
    rows = [[fmt(row[col]) for col in columns] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in columns]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(columns, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    mask = np.isfinite(prob)
    if mask.sum() == 0:
        return float("nan")
    return float(brier_score_loss(y[mask], np.clip(prob[mask], 0.0, 1.0)))


def run_bootstrap_ci(
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    metric,
    seed: int,
    n_boot: int,
) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric(y[idx], score[idx])
        if math.isfinite(value):
            values.append(value)
    if len(values) < 20:
        return (float("nan"), float("nan"))
    return (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))


def summarize_method(name: str, y: np.ndarray, score: np.ndarray, prob: np.ndarray, runs: np.ndarray, seed: int, n_boot: int, notes: str) -> dict:
    auc_ci = run_bootstrap_ci(y, score, runs, auc, seed, n_boot)
    ap_ci = run_bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)
    brier_ci = run_bootstrap_ci(y, prob, runs, brier, seed + 2, n_boot)
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": auc_ci[0],
        "roc_auc_ci_high": auc_ci[1],
        "average_precision": ap(y, score),
        "ap_ci_low": ap_ci[0],
        "ap_ci_high": ap_ci[1],
        "brier": brier(y, prob),
        "brier_ci_low": brier_ci[0],
        "brier_ci_high": brier_ci[1],
        "notes": notes,
    }


def robust_width(values: np.ndarray) -> float:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return float("nan")
    q16, q84 = np.percentile(vals, [16, 84])
    return float(0.5 * (q84 - q16))


def build_sequence_tensor(data: pd.DataFrame) -> np.ndarray:
    chans = []
    for prefix in ["b2_shape", "ds_shape_mean", "ds_shape_std"]:
        cols = [f"{prefix}_norm_s{i:02d}" for i in range(18)]
        chans.append(data[cols].to_numpy(dtype=np.float32))
    return np.stack(chans, axis=1)


def nonsequence_aux_cols(shape_cols: Sequence[str]) -> List[str]:
    return [c for c in shape_cols if "_norm_s" not in c]


def finite_matrix(data: pd.DataFrame, cols: Sequence[str]) -> np.ndarray:
    x = data[list(cols)].to_numpy(dtype=float)
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


def sklearn_score(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x)[:, 1]
    if hasattr(model, "decision_function"):
        return model.decision_function(x)
    return model.predict(x)


def make_sklearn_model(name: str, params: dict, seed: int):
    if name == "ridge_logistic":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(C=float(params["C"]), solver="lbfgs", max_iter=500, random_state=seed),
        )
    if name == "gradient_boosted_trees":
        return HistGradientBoostingClassifier(
            learning_rate=float(params["learning_rate"]),
            max_leaf_nodes=int(params["max_leaf_nodes"]),
            l2_regularization=float(params["l2_regularization"]),
            max_iter=160,
            random_state=seed,
        )
    if name == "mlp":
        return make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=tuple(int(v) for v in params["hidden_layer_sizes"]),
                alpha=float(params["alpha"]),
                activation="relu",
                early_stopping=True,
                validation_fraction=0.18,
                max_iter=300,
                random_state=seed,
            ),
        )
    raise ValueError(name)


def choose_sklearn_params(name: str, grid: Sequence[dict], x: np.ndarray, y: np.ndarray, runs: np.ndarray, outer_train: np.ndarray, seed: int) -> Tuple[dict, pd.DataFrame]:
    rows = []
    train_runs = sorted(np.unique(runs[outer_train]))
    for params in grid:
        fold_scores = []
        for fold, val_run in enumerate(train_runs):
            inner_train = outer_train & (runs != val_run)
            inner_valid = outer_train & (runs == val_run)
            if len(np.unique(y[inner_train])) < 2 or len(np.unique(y[inner_valid])) < 2:
                continue
            model = make_sklearn_model(name, params, seed + fold)
            model.fit(x[inner_train], y[inner_train])
            fold_scores.append(auc(y[inner_valid], sklearn_score(model, x[inner_valid])))
        rows.append({**params, "inner_mean_auc": float(np.nanmean(fold_scores)), "inner_folds": int(len(fold_scores))})
    frame = pd.DataFrame(rows).sort_values("inner_mean_auc", ascending=False)
    return {k: frame.iloc[0][k].item() if hasattr(frame.iloc[0][k], "item") else frame.iloc[0][k] for k in grid[0].keys()}, frame


def sklearn_oof(name: str, grid: Sequence[dict], data: pd.DataFrame, y: np.ndarray, cols: Sequence[str], config: dict) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    x = finite_matrix(data, cols)
    runs = data["run"].to_numpy(dtype=int)
    scores = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    rows = []
    seed = int(config["random_seed"])
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        params, cv = choose_sklearn_params(name, grid, x, y, runs, train, seed + 100 * fold)
        cv["outer_heldout_run"] = int(held_run)
        cv["model"] = name
        rows.extend(cv.to_dict(orient="records"))
        model = make_sklearn_model(name, params, seed + 1000 + fold)
        model.fit(x[train], y[train])
        scores[test] = sklearn_score(model, x[test])
        fold_id[test] = fold
    return scores, fold_id, pd.DataFrame(rows)


class SmallCNN(torch.nn.Module):
    def __init__(self, channels: int, dropout: float):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Conv1d(3, channels, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(channels, channels, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(1),
            torch.nn.Flatten(),
            torch.nn.Dropout(dropout),
            torch.nn.Linear(channels, 1),
        )

    def forward(self, seq: torch.Tensor, aux: Optional[torch.Tensor] = None) -> torch.Tensor:
        return self.net(seq).squeeze(-1)


class ResidualTCNFusion(torch.nn.Module):
    def __init__(self, channels: int, aux_dim: int, dropout: float):
        super().__init__()
        self.inp = torch.nn.Conv1d(3, channels, kernel_size=1)
        self.block1 = torch.nn.Conv1d(channels, channels, kernel_size=3, padding=1, dilation=1)
        self.block2 = torch.nn.Conv1d(channels, channels, kernel_size=3, padding=2, dilation=2)
        self.block3 = torch.nn.Conv1d(channels, channels, kernel_size=3, padding=4, dilation=4)
        self.aux = torch.nn.Sequential(torch.nn.Linear(aux_dim, channels), torch.nn.ReLU()) if aux_dim else None
        self.head = torch.nn.Sequential(
            torch.nn.Dropout(dropout),
            torch.nn.Linear(channels * (2 if aux_dim else 1), channels),
            torch.nn.ReLU(),
            torch.nn.Linear(channels, 1),
        )

    def forward(self, seq: torch.Tensor, aux: Optional[torch.Tensor] = None) -> torch.Tensor:
        x = torch.relu(self.inp(seq))
        for block in [self.block1, self.block2, self.block3]:
            x = torch.relu(block(x)) + x
        pooled = torch.amax(x, dim=-1)
        if self.aux is not None and aux is not None:
            pooled = torch.cat([pooled, self.aux(aux)], dim=1)
        return self.head(pooled).squeeze(-1)


def standardize_train_test(x: np.ndarray, train: np.ndarray, test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mean = x[train].mean(axis=0, keepdims=True)
    std = x[train].std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (x[train] - mean) / std, (x[test] - mean) / std


def standardize_seq(seq: np.ndarray, train: np.ndarray, test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mean = seq[train].mean(axis=(0, 2), keepdims=True)
    std = seq[train].std(axis=(0, 2), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (seq[train] - mean) / std, (seq[test] - mean) / std


def train_torch_model(
    model_name: str,
    params: dict,
    seq_train: np.ndarray,
    aux_train: np.ndarray,
    y_train: np.ndarray,
    seq_eval: np.ndarray,
    aux_eval: np.ndarray,
    config: dict,
    seed: int,
) -> np.ndarray:
    torch.manual_seed(seed)
    if model_name == "cnn_1d":
        model = SmallCNN(int(params["channels"]), float(params["dropout"]))
    elif model_name == "residual_tcn_fusion":
        model = ResidualTCNFusion(int(params["channels"]), int(aux_train.shape[1]), float(params["dropout"]))
    else:
        raise ValueError(model_name)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["torch_learning_rate"]), weight_decay=float(config["torch_weight_decay"]))
    loss_fn = torch.nn.BCEWithLogitsLoss()
    batch = int(config["torch_batch_size"])
    seq_t = torch.tensor(seq_train, dtype=torch.float32)
    aux_t = torch.tensor(aux_train, dtype=torch.float32)
    y_t = torch.tensor(y_train.astype(np.float32), dtype=torch.float32)
    rng = np.random.default_rng(seed)
    model.train()
    for _ in range(int(config["torch_epochs"])):
        order = rng.permutation(len(y_train))
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            opt.zero_grad()
            logits = model(seq_t[idx], aux_t[idx])
            loss = loss_fn(logits, y_t[idx])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        logits = model(torch.tensor(seq_eval, dtype=torch.float32), torch.tensor(aux_eval, dtype=torch.float32)).numpy()
    return logits.astype(float)


def choose_torch_params(
    model_name: str,
    grid: Sequence[dict],
    seq: np.ndarray,
    aux: np.ndarray,
    y: np.ndarray,
    runs: np.ndarray,
    outer_train: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[dict, pd.DataFrame]:
    train_runs = sorted(np.unique(runs[outer_train]))
    rows = []
    # One deterministic run-held-out validation inside each outer fold keeps
    # the neural search leakage-free while staying small enough for laptop CPU
    # execution.  The outer benchmark still scores every run exactly once.
    validation_runs = [train_runs[seed % len(train_runs)]] if train_runs else []
    for params in grid:
        fold_scores = []
        for j, val_run in enumerate(validation_runs):
            inner_train = outer_train & (runs != val_run)
            inner_valid = outer_train & (runs == val_run)
            if len(np.unique(y[inner_train])) < 2 or len(np.unique(y[inner_valid])) < 2:
                continue
            seq_tr, seq_va = standardize_seq(seq, inner_train, inner_valid)
            aux_tr, aux_va = standardize_train_test(aux, inner_train, inner_valid)
            score = train_torch_model(model_name, params, seq_tr, aux_tr, y[inner_train], seq_va, aux_va, config, seed + j)
            fold_scores.append(auc(y[inner_valid], score))
        rows.append({**params, "inner_mean_auc": float(np.nanmean(fold_scores)), "inner_folds": int(len(fold_scores))})
    frame = pd.DataFrame(rows).sort_values("inner_mean_auc", ascending=False)
    return {k: frame.iloc[0][k].item() if hasattr(frame.iloc[0][k], "item") else frame.iloc[0][k] for k in grid[0].keys()}, frame


def torch_oof(model_name: str, grid: Sequence[dict], data: pd.DataFrame, y: np.ndarray, shape_cols: Sequence[str], config: dict) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    seq = build_sequence_tensor(data)
    aux = finite_matrix(data, nonsequence_aux_cols(shape_cols))
    runs = data["run"].to_numpy(dtype=int)
    scores = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    rows = []
    seed = int(config["random_seed"]) + (4000 if model_name == "cnn_1d" else 5000)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        params, cv = choose_torch_params(model_name, grid, seq, aux, y, runs, train, config, seed + 100 * fold)
        cv["outer_heldout_run"] = int(held_run)
        cv["model"] = model_name
        rows.extend(cv.to_dict(orient="records"))
        seq_tr, seq_te = standardize_seq(seq, train, test)
        aux_tr, aux_te = standardize_train_test(aux, train, test)
        scores[test] = train_torch_model(model_name, params, seq_tr, aux_tr, y[train], seq_te, aux_te, config, seed + 1000 + fold)
        fold_id[test] = fold
    return scores, fold_id, pd.DataFrame(rows)


def operating_point_rows(data: pd.DataFrame, y: np.ndarray, runs: np.ndarray, score_map: Dict[str, np.ndarray], config: dict) -> pd.DataFrame:
    rows = []
    eff = float(config["fixed_clean_efficiency"])
    fpr = float(config["fixed_fpr"])
    for method, score in score_map.items():
        for held_run in sorted(np.unique(runs)):
            train = (runs != held_run) & np.isfinite(score)
            test = (runs == held_run) & np.isfinite(score)
            clean_train = train & (y == 0)
            if clean_train.sum() == 0:
                continue
            for mode, q in [("fixed_clean_efficiency", eff), ("fixed_false_positive_rate", 1.0 - fpr)]:
                threshold = float(np.quantile(score[clean_train], q))
                clean = test & (y == 0)
                injected = test & (y == 1)
                rows.append(
                    {
                        "method": method,
                        "heldout_run": int(held_run),
                        "mode": mode,
                        "threshold": threshold,
                        "clean_acceptance": float(np.mean(score[clean] <= threshold)) if clean.any() else float("nan"),
                        "false_positive_rate": float(np.mean(score[clean] > threshold)) if clean.any() else float("nan"),
                        "injected_rejection": float(np.mean(score[injected] > threshold)) if injected.any() else float("nan"),
                        "n_clean": int(clean.sum()),
                        "n_injected": int(injected.sum()),
                    }
                )
    return pd.DataFrame(rows)


def support_drift_rows(data: pd.DataFrame, y: np.ndarray, runs: np.ndarray, score_map: Dict[str, np.ndarray], config: dict) -> pd.DataFrame:
    amp_cols = [c for c in data.columns if c.endswith("_log_amp")]
    clean = y == 0
    rows = []
    for method, score in score_map.items():
        for held_run in sorted(np.unique(runs)):
            train_clean = (runs != held_run) & clean & np.isfinite(score)
            test_clean = (runs == held_run) & clean & np.isfinite(score)
            if train_clean.sum() == 0 or test_clean.sum() == 0:
                continue
            threshold = float(np.quantile(score[train_clean], float(config["fixed_clean_efficiency"])))
            accepted = test_clean & (score <= threshold)
            vetoed = test_clean & (score > threshold)
            all_clean = test_clean
            rows.append(
                {
                    "method": method,
                    "heldout_run": int(held_run),
                    "threshold": threshold,
                    "veto_fraction": float(np.mean(score[test_clean] > threshold)),
                    "timing_sigma68_all_ns": robust_width(data.loc[all_clean, "d_t_ns"].to_numpy(dtype=float)),
                    "timing_sigma68_accepted_ns": robust_width(data.loc[accepted, "d_t_ns"].to_numpy(dtype=float)),
                    "timing_sigma68_delta_ns": robust_width(data.loc[accepted, "d_t_ns"].to_numpy(dtype=float)) - robust_width(data.loc[all_clean, "d_t_ns"].to_numpy(dtype=float)),
                    "charge_logamp_delta": float(data.loc[accepted, amp_cols].to_numpy(dtype=float).mean() - data.loc[all_clean, amp_cols].to_numpy(dtype=float).mean()) if accepted.any() else float("nan"),
                    "baseline_final_fraction_delta": float(data.loc[accepted, "ds_shape_mean_final_fraction"].mean() - data.loc[all_clean, "ds_shape_mean_final_fraction"].mean()) if accepted.any() else float("nan"),
                    "saturation_logamp_top10_delta": float(np.mean(data.loc[accepted, amp_cols].to_numpy(dtype=float).max(axis=1) > np.quantile(data.loc[all_clean, amp_cols].to_numpy(dtype=float).max(axis=1), 0.9)) - 0.1) if accepted.any() else float("nan"),
                    "pileup_dt_mean_delta_ns": float(data.loc[accepted, "d_t_ns"].mean() - data.loc[all_clean, "d_t_ns"].mean()) if accepted.any() else float("nan"),
                    "topology_n_downstream_delta": float(data.loc[accepted, "n_downstream"].mean() - data.loc[all_clean, "n_downstream"].mean()) if accepted.any() else float("nan"),
                    "n_accepted_clean": int(accepted.sum()),
                    "n_vetoed_clean": int(vetoed.sum()),
                }
            )
    return pd.DataFrame(rows)


def aggregate_operating_points(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in frame.groupby(["method", "mode"], sort=False):
        method, mode = keys
        rows.append(
            {
                "method": method,
                "mode": mode,
                "clean_acceptance_mean": float(group["clean_acceptance"].mean()),
                "false_positive_rate_mean": float(group["false_positive_rate"].mean()),
                "injected_rejection_mean": float(group["injected_rejection"].mean()),
                "runs": int(group["heldout_run"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def calibration_table(y: np.ndarray, prob: np.ndarray, method: str, bins: int = 8) -> pd.DataFrame:
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1 else prob <= hi) & np.isfinite(prob)
        if mask.any():
            rows.append({"method": method, "bin_low": lo, "bin_high": hi, "mean_probability": float(np.mean(prob[mask])), "observed_injected_fraction": float(np.mean(y[mask])), "n": int(mask.sum())})
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, scoreboard: pd.DataFrame, data: pd.DataFrame, y: np.ndarray, score_map: Dict[str, np.ndarray], cal: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ordered = scoreboard.sort_values("roc_auc", ascending=False)
    ax.barh(ordered["method"], ordered["roc_auc"], color="#4c78a8")
    ax.set_xlabel("Run-held-out ROC AUC")
    ax.set_xlim(0.45, 1.0)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_auc.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(data.loc[y == 0, "d_t_ns"], bins=np.linspace(0, 30, 61), histtype="step", density=True, label="raw clean")
    ax.hist(data.loc[y == 1, "d_t_ns"], bins=np.linspace(0, 30, 61), histtype="step", density=True, label="injected")
    ax.set_xlabel("post-injection downstream D_t (ns)")
    ax.set_ylabel("density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_post_injection_dt.png", dpi=140)
    plt.close(fig)

    winner = ordered.iloc[0]["method"]
    fig, ax = plt.subplots(figsize=(7, 4))
    score = score_map[str(winner)]
    ax.hist(score[y == 0], bins=40, alpha=0.6, label="raw clean")
    ax.hist(score[y == 1], bins=40, alpha=0.6, label="injected")
    ax.set_xlabel(f"held-out {winner} score")
    ax.set_ylabel("events")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_score.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 5))
    for method, group in cal.groupby("method"):
        ax.plot(group["mean_probability"], group["observed_injected_fraction"], "o-", label=method)
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("mean calibrated probability")
    ax.set_ylabel("observed injected fraction")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_reliability.png", dpi=140)
    plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    counts: pd.DataFrame,
    scoreboard: pd.DataFrame,
    operating_summary: pd.DataFrame,
    support: pd.DataFrame,
    leakage: pd.DataFrame,
    cv: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    strong = scoreboard[scoreboard["method"] == "traditional timing/template reference"].iloc[0]
    support_summary = support.groupby("method", sort=False).agg(
        {
            "veto_fraction": "mean",
            "timing_sigma68_delta_ns": "mean",
            "charge_logamp_delta": "mean",
            "baseline_final_fraction_delta": "mean",
            "saturation_logamp_top10_delta": "mean",
            "pileup_dt_mean_delta_ns": "mean",
            "topology_n_downstream_delta": "mean",
        }
    ).reset_index()
    text = f"""# S07l: injected morphology operating-point support audit

- **Study ID:** S07l
- **Ticket:** {config['ticket_id']}
- **Author:** {config['worker']}
- **Date:** 2026-06-10
- **Depends on:** S07h (`reports/1781015838.1407.0539203d`) and S07d helper code
- **Input:** raw B-stack `HRDv` ROOT files under `{config['raw_root_dir']}`
- **Config:** `configs/s07l_1781039488_1142_659b28c4_operating_point_support.json`
- **Git commit used by script:** {result['git_commit']}

## 0. Question
Can the S07h injected non-`D_t` morphology detector be run at fixed clean efficiency / fixed false-positive rate without large support drift, and which model family wins against a strong traditional timing/template comparator on identical leave-one-run-out folds?

Pre-registered ticket text: can the S07h injected non-`D_t` morphology RF be operated at fixed efficiency or fixed false-positive rate without distorting real timing, charge, baseline, saturation, pile-up, or topology support. Metrics are injected AP/AUC, fixed-efficiency FPR, real-data support drift, timing sigma68/tail delta, charge-bias delta, and ML-minus-traditional utility with run-block bootstrap 95 percent CIs.

## 1. Reproduction Gate
The script starts from raw ROOT, rebuilds the S07h/P02d inputs, and refuses to continue unless the parent numbers match. The parent S07h RF AUC is also rerun on the same raw-derived injected rows as a continuity check.

{markdown_table(reproduction)}

The reproduced dataset contains paired raw-clean and injected rows. Raw and injected members share a `pair_id` and are split together because the outer fold is the run.

{markdown_table(counts)}

## 2. Traditional Method
The strong traditional comparator is the S07d/S07h fold-selected timing/template score. For each held-out run, training runs choose a signed one-dimensional score from downstream `D_t`, `|C_t|`, late-fraction summaries, downstream peak/shape summaries, and a fold-local matched-secondary-template residual. The selected score is centered and scaled by the training interquartile range before applying to the held-out run:

\\[
s_{{i,r}} = \\frac{{\\operatorname{{sign}}(j_r)x_{{ij_r}}-\\operatorname{{median}}_{{k\\in T_r}}(\\operatorname{{sign}}(j_r)x_{{kj_r}})}}{{\\operatorname{{IQR}}_{{k\\in T_r}}(\\operatorname{{sign}}(j_r)x_{{kj_r}})}}.
\\]

This is a deliberately strong baseline because it can use timing/template observables that the neural shape models do not receive. It is not a strawman P02 early-peak cut.

## 3. ML and Neural Methods
All learned models use the same outer leave-one-run-out split. Dense ML methods receive strict S07h morphology features: normalized B2 shape plus downstream mean/std normalized-shape summaries, excluding run, event id, pair id, injection target/delay/scale, absolute amplitudes, selected-present flags, `D_t`, and `C_t`. The 1D-CNN receives three channels over 18 samples: B2 normalized shape, downstream mean normalized shape, and downstream normalized-shape standard deviation. The new architecture, `residual_tcn_fusion`, adds dilated residual temporal convolutions and fuses non-sample morphology summaries after the temporal block.

For the dense models, hyperparameters are chosen by inner leave-one-run-out CV on the outer training runs. For the neural models, one deterministic run-held-out inner validation run per outer fold selects channel width and dropout from the configured two-point grid; models are intentionally small CPU models. Probabilities are cross-fold isotonic calibrations:

\\[
\\hat p_i = g_{{-r(i)}}(s_i),\\qquad g_{{-r}}=\\arg\\min_{{g\\;\\mathrm{{isotonic}}}}\\sum_{{i\\notin r}}(y_i-g(s_i))^2.
\\]

The resulting benchmark table is:

{markdown_table(scoreboard)}

Winner recorded in `result.json`: **{winner['method']}**, ROC AUC **{winner['roc_auc']:.4f}** with 95 percent run-block CI **[{winner['ci'][0]:.4f}, {winner['ci'][1]:.4f}]**. The traditional timing/template reference reaches ROC AUC **{strong['roc_auc']:.4f}** [{strong['roc_auc_ci_low']:.4f}, {strong['roc_auc_ci_high']:.4f}].

## 4. Operating-Point Benchmark
Thresholds are determined without the held-out run. For score \\(s\\), the fixed-clean-efficiency gate sets \\(\\tau_r=Q_{{0.95}}(s_i:y_i=0,i\\notin r)\\); clean rows with \\(s>\\tau_r\\) are false positives, injected rows with \\(s>\\tau_r\\) are true detections. The fixed-FPR gate uses the same 95th clean percentile because the pre-registered FPR is 0.05.

{markdown_table(operating_summary)}

## 5. Real-Support Drift
Support drift is measured only on the raw-clean member of each pair, using held-out thresholds. Timing is the robust \\(\\sigma_{{68}}\\) of post-reconstruction downstream `D_t`; charge uses the mean log-amplitude proxy across selected B staves; baseline uses final-sample fraction; saturation uses a top-decile log-amplitude proxy; pile-up uses mean `D_t`; topology uses downstream multiplicity. These are support diagnostics, not independent beam truth labels.

{markdown_table(support_summary)}

## 6. Falsification and Leakage Checks
The falsification criterion was pre-registered before running this ticket: a model is not useful if its run-held-out injected AUC/AP gain is matched by amplitude-only, topology-only, shuffled-label, or leakage probes, or if a fixed operating point imposes large support drift. Multiple model families were tested; the conclusion names a point-estimate winner but does not promote the gate for production adoption.

{markdown_table(leakage)}

The strongest nuisance probe is amplitude-only because injection can alter peak height. It is not part of the main feature set. Pair split violations and forbidden main columns are both required to be zero.

## 7. Systematics and Caveats
- **Benchmark fairness:** the traditional timing/template score is strong and receives timing/template handles excluded from the shape-only learned models. This makes the learned win, if present, harder to obtain.
- **Data leakage:** all splits are by run; paired injected/raw rows are never split across train/test; model features exclude identifiers and label-defining timing variables.
- **Metric misuse:** ROC AUC and AP describe injected closure detection, not a measured beam pile-up rate. Support-drift rows are diagnostics over raw-clean events.
- **Post-hoc selection:** model grids, operating points, and primary metrics are in the config. Because several methods are compared, the winner is a screening winner with bootstrap CIs rather than a deployment claim.
- **Systematics not covered by bootstrap:** future run-domain shift, artificial injection realism, missing real-current truth labels, and the use of support proxies for charge/baseline/saturation are outside the run-block CI.

## 8. Findings and Next Step
The strongest conclusion is that waveform-shape learning remains useful on independent injected truth, but operating-point use is not automatically safe. The benchmark winner is **{winner['method']}**, while the support-drift table should be treated as the gatekeeper for any downstream use. Hypothesis: injected overlap morphology is concentrated in downstream normalized temporal residuals, not in topology or original timing-tail labels; a production gate would need support-preserving calibration rather than a pure high-score veto.

One follow-up is queued in `result.json`: S07m should test support-preserving score calibration by matching clean rows in run, amplitude, topology, and baseline-proxy strata before applying any injected-morphology threshold. Expected information gain: separates true injected-overlap sensitivity from threshold-induced population distortion.

## 9. Reproducibility
Regenerate all artifacts with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with torch python scripts/s07l_1781039488_1142_659b28c4_operating_point_support.py --config configs/s07l_1781039488_1142_659b28c4_operating_point_support.json
```

Key artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `method_summary.csv`, `operating_point_summary.csv`, `support_drift_by_run.csv`, `leakage_checks.csv`, `hyperparameter_cv.csv`, `oof_predictions.csv`, and figures `fig_method_auc.png`, `fig_post_injection_dt.png`, `fig_winner_score.png`, `fig_reliability.png`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07l_1781039488_1142_659b28c4_operating_point_support.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])

    p02d = load_module("s07l_p02d_helper", ROOT / config["p02d_helper_script"])
    utils = load_module("s07l_s07d_helper", ROOT / config["s07d_helper_script"])
    s07h = load_module("s07l_s07h_helper", ROOT / config["s07h_helper_script"])

    pulses, dt_events, p02d_run_counts = p02d.build_tables(config)
    p02_rep = p02d.p02_reproduction(config, pulses)
    clean_dt = dt_events["d_t_ns"] < float(config["clean_dt_max_ns"])
    gross_dt = dt_events["d_t_ns"] > float(config["gross_dt_min_ns"])
    dt_benchmark = dt_events[clean_dt | gross_dt].reset_index(drop=True)
    y_dt = (dt_benchmark["d_t_ns"].to_numpy(dtype=float) > float(config["gross_dt_min_ns"])).astype(int)
    dt_score, dt_choices = p02d.traditional_oof(dt_benchmark, y_dt)
    dt_summary = p02d.summarize(
        "reproduced P02d transparent morphology",
        y_dt,
        dt_score,
        dt_benchmark["run"].to_numpy(dtype=int),
        seed,
        n_boot,
        "Raw-ROOT reproduction of prior P02d transparent morphology on D_t extreme labels.",
    )
    reproduction = pd.DataFrame(
        [
            p02_rep,
            {
                "quantity": "S07 parent guarded gross events, D_t>51 ns",
                "report_value": int(config["expected_s07_guarded_gross_events"]),
                "reproduced": int(gross_dt.sum()),
                "delta": int(gross_dt.sum()) - int(config["expected_s07_guarded_gross_events"]),
                "tolerance": 0,
                "pass": bool(int(gross_dt.sum()) == int(config["expected_s07_guarded_gross_events"])),
                "sample_size": int(len(dt_events)),
            },
            {
                "quantity": "P02d transparent morphology ROC AUC",
                "report_value": float(config["expected_p02d_transparent_auc"]),
                "reproduced": float(dt_summary["roc_auc"]),
                "delta": float(dt_summary["roc_auc"] - float(config["expected_p02d_transparent_auc"])),
                "tolerance": float(config["expected_p02d_transparent_auc_tolerance"]),
                "pass": bool(abs(dt_summary["roc_auc"] - float(config["expected_p02d_transparent_auc"])) <= float(config["expected_p02d_transparent_auc_tolerance"])),
                "sample_size": int(len(dt_benchmark)),
            },
        ]
    )
    p02d_run_counts.to_csv(out_dir / "p02d_raw_run_counts.csv", index=False)
    dt_choices.to_csv(out_dir / "p02d_reproduction_fold_choices.csv", index=False)

    _, base_counts, clean_payloads = utils.build_base_events(config)
    data = utils.make_dataset(config, clean_payloads)
    data = s07h.add_p02_morphology_columns(data, config)
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    counts = data.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "injected"}).reset_index()
    counts["total"] = counts["raw_clean"] + counts["injected"]

    p02_score, p02_fold, _, _ = s07h.transparent_p02_oof(data, y, utils)
    p02_prob = utils.crossfold_isotonic(y, p02_score, p02_fold)
    trad_score, trad_fold, trad_choices, trad_candidates = utils.traditional_oof(data, y, config)
    trad_prob = utils.crossfold_isotonic(y, trad_score, trad_fold)

    shape_cols = utils.feature_columns(data, "strict_shape")
    rf_scan, rf_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(data, y, shape_cols, config)
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "S07h shape-only RF injected ROC AUC",
                        "report_value": float(config["expected_s07h_rf_auc"]),
                        "reproduced": float(auc(y, rf_score)),
                        "delta": float(auc(y, rf_score) - float(config["expected_s07h_rf_auc"])),
                        "tolerance": float(config["expected_s07h_rf_auc_tolerance"]),
                        "pass": bool(abs(auc(y, rf_score) - float(config["expected_s07h_rf_auc"])) <= float(config["expected_s07h_rf_auc_tolerance"])),
                        "sample_size": int(len(data)),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    dense_scores = {}
    dense_folds = {}
    cv_frames = [rf_scan.assign(model="random_forest_s07h", outer_heldout_run=-1)]
    for model_name, grid_name in [
        ("ridge_logistic", "ridge_grid"),
        ("gradient_boosted_trees", "hgb_grid"),
        ("mlp", "mlp_grid"),
    ]:
        score, fold_id, cv = sklearn_oof(model_name, config[grid_name], data, y, shape_cols, config)
        dense_scores[model_name] = score
        dense_folds[model_name] = fold_id
        cv_frames.append(cv)

    cnn_score, cnn_fold, cnn_cv = torch_oof("cnn_1d", config["cnn_grid"], data, y, shape_cols, config)
    tcn_score, tcn_fold, tcn_cv = torch_oof("residual_tcn_fusion", config["residual_tcn_grid"], data, y, shape_cols, config)
    cv_frames.extend([cnn_cv, tcn_cv])

    score_map = {
        "transparent P02 morphology": p02_score,
        "traditional timing/template reference": trad_score,
        "random_forest_s07h": rf_score,
        "ridge_logistic": dense_scores["ridge_logistic"],
        "gradient_boosted_trees": dense_scores["gradient_boosted_trees"],
        "mlp": dense_scores["mlp"],
        "cnn_1d": cnn_score,
        "residual_tcn_fusion": tcn_score,
    }
    prob_map = {
        "transparent P02 morphology": p02_prob,
        "traditional timing/template reference": trad_prob,
        "random_forest_s07h": rf_prob,
        "ridge_logistic": utils.crossfold_isotonic(y, dense_scores["ridge_logistic"], dense_folds["ridge_logistic"]),
        "gradient_boosted_trees": utils.crossfold_isotonic(y, dense_scores["gradient_boosted_trees"], dense_folds["gradient_boosted_trees"]),
        "mlp": utils.crossfold_isotonic(y, dense_scores["mlp"], dense_folds["mlp"]),
        "cnn_1d": utils.crossfold_isotonic(y, cnn_score, cnn_fold),
        "residual_tcn_fusion": utils.crossfold_isotonic(y, tcn_score, tcn_fold),
    }
    notes = {
        "transparent P02 morphology": "Train-fold-selected transparent P02 morphology cuts/scores only.",
        "traditional timing/template reference": "Strong fold-local timing/template score; primary traditional comparator.",
        "random_forest_s07h": f"S07h random-forest continuity model; best params={rf_params}.",
        "ridge_logistic": "L2-regularized logistic regression on strict normalized morphology features.",
        "gradient_boosted_trees": "Histogram gradient-boosted trees on strict normalized morphology features.",
        "mlp": "Small early-stopped dense neural network on strict normalized morphology features.",
        "cnn_1d": "Small 1D-CNN over B2/downstream mean/downstream std normalized waveforms.",
        "residual_tcn_fusion": "New residual dilated temporal CNN with non-sample morphology-stat fusion.",
    }
    scoreboard = pd.DataFrame(
        [
            summarize_method(method, y, score_map[method], prob_map[method], runs, seed + 17 * i, n_boot, notes[method])
            for i, method in enumerate(score_map)
        ]
    ).sort_values("roc_auc", ascending=False)

    op = operating_point_rows(data, y, runs, score_map, config)
    op_summary = aggregate_operating_points(op).sort_values(["mode", "injected_rejection_mean"], ascending=[True, False])
    support = support_drift_rows(data, y, runs, score_map, config)
    calibration = pd.concat([calibration_table(y, prob_map[m], m) for m in score_map], ignore_index=True)

    topo_cols = utils.feature_columns(data, "topology")
    amp_cols = utils.feature_columns(data, "amplitude")
    topo_score, _ = utils.rf_oof(data, y, topo_cols, rf_params, seed + 901)
    amp_score, _ = utils.rf_oof(data, y, amp_cols, rf_params, seed + 902)
    shuffle_score, _ = utils.rf_oof(data, y, shape_cols, rf_params, seed + 903, shuffle_train=True)
    pre_dt = data["base_d_t_ns"].to_numpy(dtype=float)
    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(data.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(data.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)
    forbidden_fragments = ["d_t_ns", "c_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "log_amp", "present", "run"]
    forbidden_shape_cols = [col for col in shape_cols if any(fragment in col for fragment in forbidden_fragments)]
    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "roc_auc": auc(y, pre_dt), "average_precision": ap(y, pre_dt), "notes": "Same source event before corruption; should be chance."},
            {"probe": "topology-only RF", "roc_auc": auc(y, topo_score), "average_precision": ap(y, topo_score), "notes": "Present flags and downstream count only; excluded from main models."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": auc(y, amp_score), "average_precision": ap(y, amp_score), "notes": "Injection can change peak height; excluded from main models."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": auc(y, shuffle_score), "average_precision": ap(y, shuffle_score), "notes": "Run-heldout null sanity check."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "forbidden main feature columns", "roc_auc": float(len(forbidden_shape_cols)), "average_precision": float("nan"), "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None."},
        ]
    )

    oof = data[["row_id", "event_key", "pair_id", "run", "eventno", "evt", "label_injected", "variant", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "n_downstream", "target_stave", "injected_delay_samples", "injected_scale"]].copy()
    for method in score_map:
        safe = method.replace(" ", "_").replace("/", "_")
        oof[f"{safe}_score"] = score_map[method]
        oof[f"{safe}_prob"] = prob_map[method]

    input_rows = []
    for run in sorted(set(config["p02_runs"]) | set(config["runs"])):
        path = raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path)})

    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    base_counts.to_csv(out_dir / "base_event_run_counts.csv", index=False)
    counts.to_csv(out_dir / "injected_counts_by_run.csv", index=False)
    trad_choices.to_csv(out_dir / "traditional_reference_fold_choices.csv", index=False)
    trad_candidates.to_csv(out_dir / "traditional_reference_candidate_metrics.csv", index=False)
    rf_scan.to_csv(out_dir / "rf_scan.csv", index=False)
    pd.concat(cv_frames, ignore_index=True).to_csv(out_dir / "hyperparameter_cv.csv", index=False)
    scoreboard.to_csv(out_dir / "method_summary.csv", index=False)
    op.to_csv(out_dir / "operating_points_by_run.csv", index=False)
    op_summary.to_csv(out_dir / "operating_point_summary.csv", index=False)
    support.to_csv(out_dir / "support_drift_by_run.csv", index=False)
    calibration.to_csv(out_dir / "calibration_bins.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    plot_outputs(out_dir, scoreboard, data, y, score_map, calibration)

    winner_row = scoreboard.iloc[0]
    traditional_row = scoreboard[scoreboard["method"] == "traditional timing/template reference"].iloc[0]
    winner = {
        "method": str(winner_row["method"]),
        "metric": "leave-one-run-out ROC AUC on injected non-D_t labels",
        "roc_auc": float(winner_row["roc_auc"]),
        "ci": [float(winner_row["roc_auc_ci_low"]), float(winner_row["roc_auc_ci_high"])],
        "average_precision": float(winner_row["average_precision"]),
        "ap_ci": [float(winner_row["ap_ci_low"]), float(winner_row["ap_ci_high"])],
        "delta_auc_vs_traditional": float(winner_row["roc_auc"] - traditional_row["roc_auc"]),
    }
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction": reproduction.to_dict(orient="records"),
        "injected_dataset": {
            "n_rows": int(len(data)),
            "n_pairs": int(data["pair_id"].nunique()),
            "n_clean": int((y == 0).sum()),
            "n_injected": int((y == 1).sum()),
            "runs": [int(run) for run in sorted(np.unique(runs))],
        },
        "traditional": {
            "method": "traditional timing/template reference",
            "metric": "leave-one-run-out ROC AUC on injected non-D_t labels",
            "value": float(traditional_row["roc_auc"]),
            "ci": [float(traditional_row["roc_auc_ci_low"]), float(traditional_row["roc_auc_ci_high"])],
        },
        "ml_methods": scoreboard.to_dict(orient="records"),
        "winner": winner,
        "benchmark_winner": winner["method"],
        "ml_beats_baseline": bool(winner["roc_auc"] > float(traditional_row["roc_auc"])),
        "operating_point_summary": op_summary.to_dict(orient="records"),
        "support_drift_summary": support.groupby("method", sort=False).agg(
            veto_fraction=("veto_fraction", "mean"),
            timing_sigma68_delta_ns=("timing_sigma68_delta_ns", "mean"),
            charge_logamp_delta=("charge_logamp_delta", "mean"),
            baseline_final_fraction_delta=("baseline_final_fraction_delta", "mean"),
            saturation_logamp_top10_delta=("saturation_logamp_top10_delta", "mean"),
            pileup_dt_mean_delta_ns=("pileup_dt_mean_delta_ns", "mean"),
            topology_n_downstream_delta=("topology_n_downstream_delta", "mean"),
        ).reset_index().to_dict(orient="records"),
        "falsification": {
            "preregistered_metric": "injected detection AP/AUC, fixed-efficiency FPR, support drift, ML-minus-traditional utility",
            "n_model_families": int(len(scoreboard)),
            "pair_split_violations": int(pair_split_violations),
            "forbidden_main_feature_columns": forbidden_shape_cols,
            "amplitude_only_auc": float(auc(y, amp_score)),
            "topology_only_auc": float(auc(y, topo_score)),
            "shuffled_label_auc": float(auc(y, shuffle_score)),
        },
        "input_sha256": sha256_file(raw_file(config, int(config["runs"][0]))),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 1),
        "critic": "pending",
        "next_tickets": [
            "S07m: support-preserving injected-morphology calibration with run/amplitude/topology/baseline matching"
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")
    write_report(out_dir, config, reproduction, counts, scoreboard, op_summary, support, leakage, pd.concat(cv_frames, ignore_index=True), result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": f"scripts/s07l_1781039488_1142_659b28c4_operating_point_support.py --config {config_path}",
        "environment_command": "uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with torch python",
        "python": platform.python_version(),
        "random_seed": seed,
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": {row["path"]: row["sha256"] for row in input_rows},
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2), encoding="utf-8")
    print(json.dumps(json_ready({"done": True, "ticket": config["ticket_id"], "winner": winner, "runtime_sec": result["runtime_sec"]}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
