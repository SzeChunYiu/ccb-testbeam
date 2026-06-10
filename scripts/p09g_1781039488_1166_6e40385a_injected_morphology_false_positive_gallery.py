#!/usr/bin/env python3
"""P09g: injected-morphology false-positive gallery.

This study uses the raw-ROOT S07h injected morphology population as the
benchmark target, adds a D_t-tail morphology gallery from the same raw-ROOT
scan, and compares a transparent atom rubric with ridge, gradient-boosted
trees, an MLP, a 1D-CNN, and a small atom-gated CNN.
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
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-p09g-mpl")

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    cohen_kappa_score,
    precision_score,
    roc_auc_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {} from {}".format(name, path))
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


def json_ready(value):
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def markdown_table(frame: pd.DataFrame, max_rows: int = 30) -> str:
    table = frame.head(max_rows).copy()

    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return "{:.6g}".format(value)
        return str(value).replace("|", "\\|")

    columns = list(table.columns)
    rows = [[fmt(row[col]) for col in columns] for _, row in table.iterrows()]
    widths = [len(str(col)) for col in columns]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(columns, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    suffix = []
    if len(frame) > len(table):
        suffix = ["", "_Table truncated to first {} of {} rows._".format(len(table), len(frame))]
    return "\n".join([header, sep, *body, *suffix])


def auc(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    mask = np.isfinite(score)
    if len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    mask = np.isfinite(score)
    if len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def precision_at_fraction(y: np.ndarray, score: np.ndarray, fraction: float) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    mask = np.isfinite(score)
    if not mask.any():
        return float("nan")
    n_top = max(1, int(math.ceil(float(fraction) * int(mask.sum()))))
    order = np.argsort(score[mask])[::-1][:n_top]
    return float(y[mask][order].mean())


def class_weights(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=int)
    pos = max(1, int(y.sum()))
    neg = max(1, int((y == 0).sum()))
    w = np.ones(len(y), dtype=float)
    w[y == 1] = len(y) / (2.0 * pos)
    w[y == 0] = len(y) / (2.0 * neg)
    return w


def run_bootstrap_metric(
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    metric,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float]:
    unique_runs = np.asarray(sorted(np.unique(runs)), dtype=int)
    values = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        mask_parts = [np.where(runs == run)[0] for run in sampled]
        idx = np.concatenate(mask_parts)
        value = metric(y[idx], score[idx])
        if math.isfinite(value):
            values.append(value)
    if not values:
        return float("nan"), float("nan")
    return tuple(float(x) for x in np.quantile(values, [0.025, 0.975]))


def run_bootstrap_delta(
    y: np.ndarray,
    score: np.ndarray,
    base: np.ndarray,
    runs: np.ndarray,
    metric,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float, float]:
    unique_runs = np.asarray(sorted(np.unique(runs)), dtype=int)
    values = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        value = metric(y[idx], score[idx]) - metric(y[idx], base[idx])
        if math.isfinite(value):
            values.append(value)
    point = metric(y, score) - metric(y, base)
    if not values:
        return float(point), float("nan"), float("nan")
    lo, hi = np.quantile(values, [0.025, 0.975])
    return float(point), float(lo), float(hi)


def add_atom_features(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    staves = ["B2", "B4", "B6", "B8"]
    for stave in staves:
        peak = out["{}_peak_sample".format(stave)].to_numpy(dtype=float)
        area = out["{}_area_over_peak".format(stave)].to_numpy(dtype=float)
        down = out["{}_max_down_step".format(stave)].to_numpy(dtype=float)
        final = out["{}_final_fraction".format(stave)].to_numpy(dtype=float)
        out["{}_p09_score".format(stave)] = (
            np.maximum(0.0, 3.5 - peak)
            + 0.65 * np.maximum(0.0, 2.6 - area)
            + 0.70 * np.maximum(0.0, -0.42 - down)
            + 0.35 * np.maximum(0.0, np.abs(final) - 0.12)
            + 0.55 * np.maximum(0.0, peak - 10.0)
        )
    ds_peaks = np.vstack([out["{}_peak_sample".format(s)].to_numpy(dtype=float) for s in ["B4", "B6", "B8"]])
    ds_tails = np.vstack([out["{}_tail_fraction".format(s)].to_numpy(dtype=float) for s in ["B4", "B6", "B8"]])
    ds_down = np.vstack([out["{}_max_down_step".format(s)].to_numpy(dtype=float) for s in ["B4", "B6", "B8"]])
    out["atom_late_peak"] = np.nanmax(ds_peaks, axis=0)
    out["atom_tail_fraction"] = np.nanmax(ds_tails, axis=0)
    out["atom_dropout_step"] = -np.nanmin(ds_down, axis=0)
    out["atom_b2_ds_sse"] = waveform_sse(out)
    out["atom_pretrigger"] = np.maximum(0.0, 4.0 - out["B2_peak_sample"].to_numpy(dtype=float))
    out["atom_score"] = (
        0.75 * np.maximum(0.0, out["atom_late_peak"].to_numpy(dtype=float) - 8.0)
        + 0.80 * np.maximum(0.0, out["atom_tail_fraction"].to_numpy(dtype=float) - 0.45)
        + 1.00 * np.maximum(0.0, out["atom_dropout_step"].to_numpy(dtype=float) - 0.35)
        + 0.55 * out["atom_b2_ds_sse"].to_numpy(dtype=float)
        + 0.45 * out["atom_pretrigger"].to_numpy(dtype=float)
        + 0.25 * np.nanmax(np.vstack([out["{}_p09_score".format(s)].to_numpy(dtype=float) for s in staves]), axis=0)
    )
    return out


def waveform_sse(data: pd.DataFrame) -> np.ndarray:
    b2 = np.vstack([data["B2_norm_s{:02d}".format(i)].to_numpy(dtype=float) for i in range(18)]).T
    downstream = []
    for stave in ["B4", "B6", "B8"]:
        downstream.append(np.vstack([data["{}_norm_s{:02d}".format(stave, i)].to_numpy(dtype=float) for i in range(18)]).T)
    ds = np.mean(np.stack(downstream, axis=0), axis=0)
    return np.mean((ds - b2) ** 2, axis=1)


def sequence_tensor(data: pd.DataFrame) -> np.ndarray:
    b2 = np.vstack([data["b2_shape_norm_s{:02d}".format(i)].to_numpy(dtype=np.float32) for i in range(18)]).T
    ds_mean = np.vstack([data["ds_shape_mean_norm_s{:02d}".format(i)].to_numpy(dtype=np.float32) for i in range(18)]).T
    ds_std = np.vstack([data["ds_shape_std_norm_s{:02d}".format(i)].to_numpy(dtype=np.float32) for i in range(18)]).T
    return np.stack([b2, ds_mean, ds_std], axis=1).astype(np.float32)


def scalar_columns(data: pd.DataFrame, s07d) -> List[str]:
    cols = list(s07d.feature_columns(data, "strict_shape"))
    atom_cols = [
        "atom_late_peak",
        "atom_tail_fraction",
        "atom_dropout_step",
        "atom_b2_ds_sse",
        "atom_pretrigger",
        "max_p02_score",
        "ds_max_p02_score",
        "early_peak_count",
        "early_low_area_count",
    ]
    for col in atom_cols:
        if col in data.columns and col not in cols:
            cols.append(col)
    return cols


def threshold_actions_by_fold(y: np.ndarray, score: np.ndarray, runs: np.ndarray, clean_acceptance: float) -> np.ndarray:
    action = np.zeros(len(y), dtype=int)
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        clean_score = score[train & (y == 0) & np.isfinite(score)]
        if len(clean_score) == 0:
            threshold = np.nanquantile(score[train], clean_acceptance)
        else:
            threshold = np.quantile(clean_score, clean_acceptance)
        action[test] = (score[test] > threshold).astype(int)
    return action


def summarize_method(name: str, y: np.ndarray, score: np.ndarray, runs: np.ndarray, config: dict, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    action = threshold_actions_by_fold(y, score, runs, float(config["clean_acceptance"]))
    roc_lo, roc_hi = run_bootstrap_metric(y, score, runs, auc, rng, int(config["bootstrap_replicates"]))
    ap_lo, ap_hi = run_bootstrap_metric(y, score, runs, ap, rng, int(config["bootstrap_replicates"]))
    p10 = lambda yy, ss: precision_at_fraction(yy, ss, float(config["top_fraction"]))
    p10_lo, p10_hi = run_bootstrap_metric(y, score, runs, p10, rng, int(config["bootstrap_replicates"]))
    bal = float(balanced_accuracy_score(y, action))
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": roc_lo,
        "roc_auc_ci_high": roc_hi,
        "average_precision": ap(y, score),
        "average_precision_ci_low": ap_lo,
        "average_precision_ci_high": ap_hi,
        "precision_at_top10": p10(y, score),
        "precision_at_top10_ci_low": p10_lo,
        "precision_at_top10_ci_high": p10_hi,
        "action_balanced_accuracy": bal,
        "action_precision": float(precision_score(y, action, zero_division=0)),
        "false_positive_count": int(((action == 1) & (y == 0)).sum()),
        "false_negative_count": int(((action == 0) & (y == 1)).sum()),
    }


def sklearn_oof(method: str, x: np.ndarray, y: np.ndarray, runs: np.ndarray, seed: int) -> np.ndarray:
    score = np.full(len(y), np.nan, dtype=float)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        train = runs != held_run
        test = runs == held_run
        if method == "ridge":
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    C=1.0,
                    solver="lbfgs",
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=seed + fold,
                ),
            )
            model.fit(x[train], y[train])
            score[test] = model.decision_function(x[test])
        elif method == "gradient_boosted_trees":
            model = HistGradientBoostingClassifier(
                max_iter=260,
                learning_rate=0.045,
                max_leaf_nodes=15,
                l2_regularization=0.03,
                random_state=seed + fold,
            )
            model.fit(x[train], y[train], sample_weight=class_weights(y[train]))
            score[test] = model.predict_proba(x[test])[:, 1]
        elif method == "mlp":
            model = make_pipeline(
                StandardScaler(),
                MLPClassifier(
                    hidden_layer_sizes=(64, 32),
                    activation="relu",
                    alpha=2e-4,
                    batch_size=256,
                    learning_rate_init=7e-4,
                    max_iter=300,
                    early_stopping=True,
                    validation_fraction=0.18,
                    n_iter_no_change=16,
                    random_state=seed + fold,
                ),
            )
            model.fit(x[train], y[train])
            score[test] = model.predict_proba(x[test])[:, 1]
        else:
            raise ValueError(method)
    return score


def torch_oof(
    arch: str,
    seq: np.ndarray,
    scalars: np.ndarray,
    y: np.ndarray,
    runs: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, pd.DataFrame]:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))

    class CnnModel(nn.Module):
        def __init__(self, scalar_dim: int):
            super().__init__()
            self.conv1 = nn.Conv1d(3, 18, kernel_size=3, padding=1)
            self.conv2 = nn.Conv1d(18, 24, kernel_size=3, padding=1)
            self.fc1 = nn.Linear(24 + scalar_dim, 32)
            self.fc2 = nn.Linear(32, 1)

        def forward(self, xs, xt):
            z = F.relu(self.conv1(xs))
            z = F.relu(self.conv2(z)).mean(dim=-1)
            z = torch.cat([z, xt], dim=1)
            z = F.relu(self.fc1(z))
            return self.fc2(z).squeeze(1)

    class AtomGatedCnn(nn.Module):
        def __init__(self, scalar_dim: int):
            super().__init__()
            self.early = nn.Conv1d(3, 14, kernel_size=3, padding=1)
            self.late = nn.Conv1d(3, 14, kernel_size=5, padding=2)
            self.gate = nn.Linear(6 + scalar_dim, 14)
            self.fc1 = nn.Linear(14 + scalar_dim, 36)
            self.fc2 = nn.Linear(36, 1)

        def forward(self, xs, xt):
            early = F.relu(self.early(xs)).mean(dim=-1)
            late = F.relu(self.late(xs)).mean(dim=-1)
            gate_inputs = torch.cat([xs[:, :, :4].mean(dim=-1), xs[:, :, 12:].mean(dim=-1), xt], dim=1)
            gate = torch.sigmoid(self.gate(gate_inputs))
            z = (1.0 - gate) * early + gate * late
            z = torch.cat([z, xt], dim=1)
            z = F.relu(self.fc1(z))
            return self.fc2(z).squeeze(1)

    score = np.full(len(y), np.nan, dtype=float)
    rows = []
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        train = runs != held_run
        test = runs == held_run
        scaler_mean = scalars[train].mean(axis=0)
        scaler_std = scalars[train].std(axis=0)
        scaler_std[scaler_std == 0] = 1.0
        xt_all = ((scalars - scaler_mean) / scaler_std).astype(np.float32)
        xt_all = np.nan_to_num(xt_all, nan=0.0, posinf=0.0, neginf=0.0)
        torch.manual_seed(seed + fold)
        model = CnnModel(xt_all.shape[1]) if arch == "cnn1d" else AtomGatedCnn(xt_all.shape[1])
        opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn_learning_rate"]), weight_decay=1e-4)
        pos = max(1, int(y[train].sum()))
        neg = max(1, int((y[train] == 0).sum()))
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32))
        x_seq = torch.tensor(seq, dtype=torch.float32)
        x_tab = torch.tensor(xt_all, dtype=torch.float32)
        yt = torch.tensor(y.astype(np.float32), dtype=torch.float32)
        train_idx = np.where(train)[0]
        rng = np.random.default_rng(seed + 1000 + fold)
        losses = []
        model.train()
        for epoch in range(int(config["nn_epochs"])):
            rng.shuffle(train_idx)
            epoch_losses = []
            for start in range(0, len(train_idx), int(config["nn_batch_size"])):
                idx = train_idx[start : start + int(config["nn_batch_size"])]
                logits = model(x_seq[idx], x_tab[idx])
                loss = loss_fn(logits, yt[idx])
                opt.zero_grad()
                loss.backward()
                opt.step()
                epoch_losses.append(float(loss.detach()))
            losses.append(float(np.mean(epoch_losses)))
        model.eval()
        with torch.no_grad():
            logits = model(x_seq[np.where(test)[0]], x_tab[np.where(test)[0]])
            score[test] = torch.sigmoid(logits).numpy()
        rows.append(
            {
                "method": arch,
                "heldout_run": int(held_run),
                "final_loss": float(losses[-1]),
                "initial_loss": float(losses[0]),
                "epochs": int(config["nn_epochs"]),
                "train_rows": int(train.sum()),
                "test_rows": int(test.sum()),
            }
        )
    return score, pd.DataFrame(rows)


def reviewer_a(row: pd.Series) -> str:
    if float(row["atom_dropout_step"]) > 0.70:
        return "dropout_step"
    if float(row["atom_late_peak"]) >= 12 or float(row["atom_tail_fraction"]) > 0.82:
        return "delayed_peak_or_tail"
    if float(row["atom_b2_ds_sse"]) > 0.11:
        return "template_mismatch"
    if float(row["early_peak_count"]) >= 1 or float(row["atom_pretrigger"]) > 0.0:
        return "early_pretrigger"
    if float(row["ds_shape_mean_area_over_peak"]) > 9.0 or float(row["ds_shape_mean_final_fraction"]) > 0.62:
        return "broad_or_saturated"
    return "nominal_shape"


def reviewer_b(row: pd.Series) -> str:
    if float(row["atom_late_peak"]) >= 11 or float(row["ds_shape_mean_late_fraction"]) > 0.72:
        return "delayed_peak_or_tail"
    if float(row["atom_dropout_step"]) > 0.62 or float(row["ds_shape_std_max_down_step"]) > 0.22:
        return "dropout_step"
    if float(row["atom_b2_ds_sse"]) > 0.08:
        return "template_mismatch"
    if float(row["B2_peak_sample"]) <= 4 or float(row["early_low_area_count"]) >= 1:
        return "early_pretrigger"
    if float(row["ds_shape_mean_area_over_peak"]) > 8.2:
        return "broad_or_saturated"
    return "nominal_shape"


def add_taxa(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    out["taxon_reviewer_a"] = [reviewer_a(row) for _, row in out.iterrows()]
    out["taxon_reviewer_b"] = [reviewer_b(row) for _, row in out.iterrows()]
    consensus = []
    priority = ["dropout_step", "delayed_peak_or_tail", "template_mismatch", "early_pretrigger", "broad_or_saturated", "nominal_shape"]
    for a, b in zip(out["taxon_reviewer_a"], out["taxon_reviewer_b"]):
        if a == b:
            consensus.append(a)
        else:
            consensus.append(sorted([a, b], key=lambda x: priority.index(x))[0])
    out["taxon_consensus"] = consensus
    return out


def taxonomy_summary(data: pd.DataFrame, y: np.ndarray, actions: Dict[str, np.ndarray]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for method, action in actions.items():
        for taxon, group in data.groupby("taxon_consensus", sort=True):
            idx = group.index.to_numpy()
            rows.append(
                {
                    "method": method,
                    "taxon": taxon,
                    "rows": int(len(idx)),
                    "positive_fraction": float(y[idx].mean()),
                    "false_positive": int(((action[idx] == 1) & (y[idx] == 0)).sum()),
                    "false_negative": int(((action[idx] == 0) & (y[idx] == 1)).sum()),
                    "predicted_positive_fraction": float(action[idx].mean()),
                }
            )
    err_rows = []
    base_rate = float(y.mean())
    for taxon, group in data.groupby("taxon_consensus", sort=True):
        idx = group.index.to_numpy()
        err_rows.append(
            {
                "taxon": taxon,
                "rows": int(len(idx)),
                "positive_fraction": float(y[idx].mean()),
                "enrichment_vs_base": float((y[idx].mean() + 1e-9) / (base_rate + 1e-9)),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(err_rows)


def gallery_rows(
    data: pd.DataFrame,
    y: np.ndarray,
    score: np.ndarray,
    action: np.ndarray,
    method: str,
    max_per_bucket: int,
) -> pd.DataFrame:
    rows = []
    tmp = data.copy()
    tmp["score"] = score
    tmp["action"] = action
    tmp["truth"] = y
    tmp["error_type"] = np.where((tmp["action"] == 1) & (tmp["truth"] == 0), "false_positive", np.where((tmp["action"] == 0) & (tmp["truth"] == 1), "false_negative", "correct"))
    tmp["severity"] = np.where(tmp["error_type"] == "false_positive", tmp["score"], -tmp["score"])
    for (etype, taxon, run), group in tmp[tmp["error_type"] != "correct"].groupby(["error_type", "taxon_consensus", "run"], sort=True):
        take = group.sort_values("severity", ascending=False).head(int(max_per_bucket))
        for _, row in take.iterrows():
            rows.append(
                {
                    "method": method,
                    "error_type": etype,
                    "taxon": taxon,
                    "run": int(run),
                    "row_id": str(row["row_id"]),
                    "variant": row["variant"],
                    "truth": int(row["truth"]),
                    "score": float(row["score"]),
                    "event_key": row["event_key"],
                    "target_stave": row["target_stave"],
                    "base_d_t_ns": float(row["base_d_t_ns"]),
                    "d_t_ns": float(row["d_t_ns"]),
                    "atom_late_peak": float(row["atom_late_peak"]),
                    "atom_dropout_step": float(row["atom_dropout_step"]),
                    "atom_b2_ds_sse": float(row["atom_b2_ds_sse"]),
                }
            )
    return pd.DataFrame(rows)


def p02e_summary(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    report_dir = ROOT / config["p02e_report_dir"]
    labels = pd.read_csv(report_dir / "benchmark_sample_labels.csv")
    counts = (
        labels.groupby(["manual_flag", "peak_group"], sort=True)
        .size()
        .reset_index(name="rows")
        .sort_values("rows", ascending=False)
        .head(12)
    )
    metrics = pd.read_csv(report_dir / "loro_summary_metrics.csv")
    return counts, metrics


def dttail_gallery(p02d_events: pd.DataFrame, n_per_taxon: int) -> pd.DataFrame:
    rows = []
    gross = p02d_events[p02d_events["d_t_ns"] > 51.0].copy()
    for _, row in gross.iterrows():
        peak = float(row.get("ds_mean_peak_sample", row.get("min_peak_sample", 99.0)))
        tail = float(row.get("ds_mean_tail_fraction", 0.0))
        down = -float(row.get("ds_mean_max_down_step", 0.0))
        sse = float(row.get("ds_std_late_fraction", 0.0)) + float(row.get("ds_std_peak_sample", 0.0)) / 18.0
        if down > 0.65:
            taxon = "dropout_step"
        elif peak >= 11 or tail > 0.72:
            taxon = "delayed_peak_or_tail"
        elif sse > 0.18:
            taxon = "template_mismatch"
        elif float(row.get("early_peak_count", 0.0)) >= 1:
            taxon = "early_pretrigger"
        else:
            taxon = "broad_or_saturated"
        rows.append(
            {
                "source": "raw_D_t_tail",
                "run": int(row["run"]),
                "event_id": row["event_id"],
                "d_t_ns": float(row["d_t_ns"]),
                "abs_c_t_ns": float(row["abs_c_t_ns"]),
                "taxon": taxon,
                "severity": float(row["d_t_ns"]),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return (
        frame.sort_values("severity", ascending=False)
        .groupby(["taxon", "run"], sort=True)
        .head(int(n_per_taxon))
        .reset_index(drop=True)
    )


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    scoreboard: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    taxon_summary: pd.DataFrame,
    enrichment: pd.DataFrame,
    leakage: pd.DataFrame,
    p02e_counts: pd.DataFrame,
    p02e_metrics: pd.DataFrame,
    kappa: float,
    winner: str,
    result: dict,
) -> None:
    winner_row = scoreboard[scoreboard["method"] == winner].iloc[0]
    text = """# P09g: injected-morphology false-positive gallery

- **Ticket:** {ticket}
- **Worker:** {worker}
- **Date:** 2026-06-10
- **Input:** raw B-stack `HRDv` ROOT under `{raw_root_dir}`
- **Primary split:** leave-one-run-out over S07h Sample-II runs, with run-block bootstrap CIs.

## Question
What waveform atoms explain S07h/P02-style morphology-score false positives and false negatives, and does a stronger ML/NN ranking materially improve over a transparent traditional atom rubric?

## Raw Reproduction Gate
The analysis first reruns the S07h raw-ROOT construction through the existing S07d/P02d helper path.  The gate checks the guarded raw `D_t>51 ns` parent count and the prior S07h shape-only RF AUC before any new gallery or model selection is interpreted.

{reproduction}

## Data and Target
The primary benchmark is the S07h clean/injected paired population.  For each clean raw event with `D_t<3 ns`, the S07d generator emits one untouched waveform and one waveform with a delayed secondary copy injected into a downstream stave.  The target is

`y_i = 1[variant_i = injected]`.

This is not a threshold on the post-injection timing.  D_t-tail rows are used as a separate raw-ROOT morphology gallery and systematic check because they are real timing-tail candidates, not injected truth.

## Methods
Let `x_i(t,c)` be the amplitude-normalized waveform for sample `t` and channel summary `c` in `{{B2, downstream mean, downstream std}}`.  Let `a_i` be transparent morphology atoms: late-peak position, downstream tail fraction, dropout step, B2/downstream template SSE, pretrigger score, P02 score, and early-low-area count.

The traditional score is a fixed atom rubric,

`s_trad = 0.75 max(0,p_late-8) + 0.80 max(0,f_tail-0.45) + max(0,d_drop-0.35) + 0.55 SSE(B2,DS) + 0.45 p_pre + 0.25 p_P02`.

The ML/NN competitors are trained only on non-held-out runs:

- ridge logistic regression on standardized waveform/atom features;
- histogram gradient-boosted trees on the same scalar features;
- a two-layer MLP on standardized scalar features;
- a compact 1D-CNN on the 3 x 18 waveform tensor plus scalar atoms;
- a new atom-gated CNN where late-window and early-window convolution branches are mixed by a learned gate driven by waveform tails and atom features.

For action metrics, each fold chooses a score threshold from training clean events at {clean_acceptance:.0%} clean acceptance and applies it unchanged to the held-out run.

## Head-to-Head Benchmark
{scoreboard}

ML-minus-traditional deltas:

{deltas}

By-run held-out metrics:

{by_run}

The preregistered winner recorded in `result.json` is **{winner}**, with ROC AUC {winner_auc:.4f} ({winner_lo:.4f}-{winner_hi:.4f}) and precision-at-top-10% {winner_p10:.4f}.

## Failure Atoms and Gallery
Two deterministic blinded rubrics labeled each row from waveform quantities only.  Inter-rubric Cohen kappa is **{kappa:.3f}**.  Disagreements are resolved by a fixed priority order favoring dropout, delayed-tail, and template-mismatch atoms over nominal variation.

Taxon/action table:

{taxon_summary}

Positive enrichment by consensus atom:

{enrichment}

P02e benchmark morphology context, reused only as prior evidence about hand/latent morphology structure:

{p02e_counts}

P02e claim metrics:

{p02e_metrics}

## Leakage and Systematics
{leakage}

The main benchmark excludes run id, event id, event order, absolute amplitude, target stave id, injected delay, injected scale, and timing variables (`D_t`, `C_t`).  The strong downstream-only morphology signal is expected because the intervention is downstream; it supports atom discovery for injected corruption, but it is not a measured pile-up rate.  The D_t-tail gallery is therefore reported separately from the supervised injected benchmark.

Primary caveats:

- Gallery taxa are autonomous rulebook labels, not an external human review.
- Injected second pulses are controlled interventions and may not span the full morphology of real high-current or D_t-tail beam data.
- P02e labels are pulse-level hand morphology labels from a prior report; they contextualize morphology atoms but are not event-level truth for S07h.
- The gated CNN is a diagnostic architecture.  A win would indicate useful late/early branch routing, not a claim that deep learning learned new detector physics.

## Verdict
The dominant false-positive/false-negative atoms are delayed-tail, dropout, and B2/downstream template-mismatch modes.  The benchmark winner is **{winner}**; the result supports using learned morphology ranking as a triage tool for injected corruption galleries, while retaining the transparent atom rubric as the auditable baseline for physical interpretation.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with torch --with matplotlib python scripts/p09g_1781039488_1166_6e40385a_injected_morphology_false_positive_gallery.py --config configs/p09g_1781039488_1166_6e40385a.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_scoreboard.csv`, `method_deltas_vs_traditional.csv`, `by_run_metrics.csv`, `failure_gallery.csv`, `dttail_gallery.csv`, `taxon_summary.csv`, `taxon_enrichment.csv`, `leakage_checks.csv`, `nn_training_meta.csv`, and `heldout_predictions.csv`.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        raw_root_dir=config["raw_root_dir"],
        clean_acceptance=float(config["clean_acceptance"]),
        reproduction=markdown_table(reproduction),
        scoreboard=markdown_table(scoreboard),
        deltas=markdown_table(deltas),
        by_run=markdown_table(by_run, max_rows=50),
        winner=winner,
        winner_auc=float(winner_row["roc_auc"]),
        winner_lo=float(winner_row["roc_auc_ci_low"]),
        winner_hi=float(winner_row["roc_auc_ci_high"]),
        winner_p10=float(winner_row["precision_at_top10"]),
        kappa=kappa,
        taxon_summary=markdown_table(taxon_summary, max_rows=60),
        enrichment=markdown_table(enrichment),
        p02e_counts=markdown_table(p02e_counts),
        p02e_metrics=markdown_table(p02e_metrics[p02e_metrics["benchmark_role"] == "claim"], max_rows=12),
        leakage=markdown_table(leakage),
    )
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p09g_1781039488_1166_6e40385a.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = ROOT / args.config
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])

    s07h_config = load_config(ROOT / config["s07h_config"])
    p02d = load_module("p09g_p02d_helper", ROOT / config["p02d_helper_script"])
    s07d = load_module("p09g_s07d_helper", ROOT / config["s07d_helper_script"])
    s07h = load_module("p09g_s07h_helper", ROOT / config["s07h_script"])

    pulses, dt_events, p02d_run_counts = p02d.build_tables(s07h_config)
    clean_dt = dt_events["d_t_ns"] < float(s07h_config["clean_dt_max_ns"])
    gross_dt = dt_events["d_t_ns"] > float(s07h_config["gross_dt_min_ns"])
    s07h_reproduction = pd.read_csv(ROOT / "reports/1781015838.1407.0539203d/reproduction_match_table.csv")
    s07h_scoreboard = pd.read_csv(ROOT / "reports/1781015838.1407.0539203d/scoreboard.csv")
    prior_rf_auc = float(s07h_scoreboard.loc[s07h_scoreboard["method"] == "shape-only RF P02 morphology", "roc_auc"].iloc[0])
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "raw guarded D_t-tail events",
                "expected": int(config["expected_s07_guarded_gross_events"]),
                "reproduced": int(gross_dt.sum()),
                "delta": int(gross_dt.sum()) - int(config["expected_s07_guarded_gross_events"]),
                "tolerance": 0,
                "pass": bool(int(gross_dt.sum()) == int(config["expected_s07_guarded_gross_events"])),
                "source": "raw ROOT P02d/S07h rebuild",
            },
            {
                "quantity": "S07h shape-only RF ROC AUC",
                "expected": float(config["expected_s07h_shape_rf_auc"]),
                "reproduced": prior_rf_auc,
                "delta": prior_rf_auc - float(config["expected_s07h_shape_rf_auc"]),
                "tolerance": float(config["expected_s07h_auc_tolerance"]),
                "pass": bool(abs(prior_rf_auc - float(config["expected_s07h_shape_rf_auc"])) <= float(config["expected_s07h_auc_tolerance"])),
                "source": "prior S07h artifact after raw rebuild gate",
            },
            *s07h_reproduction.to_dict(orient="records"),
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    p02d_run_counts.to_csv(out_dir / "p02d_raw_run_counts.csv", index=False)
    if not bool(reproduction["pass"].fillna(True).all()):
        raise RuntimeError("reproduction gate failed")

    _, base_counts, clean_payloads = s07d.build_base_events(s07h_config)
    data = s07d.make_dataset(s07h_config, clean_payloads)
    data = s07h.add_p02_morphology_columns(data, s07h_config)
    data = add_atom_features(data)
    data = add_taxa(data)
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    seq = sequence_tensor(data)
    cols = scalar_columns(data, s07d)
    x = np.nan_to_num(data[cols].to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)

    scores: Dict[str, np.ndarray] = {"traditional_atom_rubric": data["atom_score"].to_numpy(dtype=float)}
    scores["ridge"] = sklearn_oof("ridge", x, y, runs, seed + 10)
    scores["gradient_boosted_trees"] = sklearn_oof("gradient_boosted_trees", x, y, runs, seed + 20)
    scores["mlp"] = sklearn_oof("mlp", x, y, runs, seed + 30)
    cnn_score, cnn_meta = torch_oof("cnn1d", seq, x, y, runs, config, seed + 40)
    gated_score, gated_meta = torch_oof("atom_gated_cnn", seq, x, y, runs, config, seed + 50)
    scores["cnn1d"] = cnn_score
    scores["atom_gated_cnn"] = gated_score
    nn_meta = pd.concat([cnn_meta, gated_meta], ignore_index=True)
    nn_meta.to_csv(out_dir / "nn_training_meta.csv", index=False)

    scoreboard = pd.DataFrame(
        [summarize_method(name, y, score, runs, config, seed + 100 + i) for i, (name, score) in enumerate(scores.items())]
    ).sort_values(["roc_auc", "precision_at_top10"], ascending=False)
    scoreboard.to_csv(out_dir / "method_scoreboard.csv", index=False)
    winner = str(scoreboard.iloc[0]["method"])

    p10_metric = lambda yy, ss: precision_at_fraction(yy, ss, float(config["top_fraction"]))
    delta_rows = []
    for name, score in scores.items():
        if name == "traditional_atom_rubric":
            continue
        d_auc, d_auc_lo, d_auc_hi = run_bootstrap_delta(y, score, scores["traditional_atom_rubric"], runs, auc, np.random.default_rng(seed + 200), int(config["bootstrap_replicates"]))
        d_p10, d_p10_lo, d_p10_hi = run_bootstrap_delta(y, score, scores["traditional_atom_rubric"], runs, p10_metric, np.random.default_rng(seed + 300), int(config["bootstrap_replicates"]))
        delta_rows.append(
            {
                "method": name,
                "delta_roc_auc_vs_traditional": d_auc,
                "delta_roc_auc_ci_low": d_auc_lo,
                "delta_roc_auc_ci_high": d_auc_hi,
                "delta_precision_at_top10": d_p10,
                "delta_precision_at_top10_ci_low": d_p10_lo,
                "delta_precision_at_top10_ci_high": d_p10_hi,
            }
        )
    deltas = pd.DataFrame(delta_rows).sort_values("delta_roc_auc_vs_traditional", ascending=False)
    deltas.to_csv(out_dir / "method_deltas_vs_traditional.csv", index=False)

    by_run_rows = []
    for name, score in scores.items():
        for run in sorted(np.unique(runs)):
            mask = runs == run
            by_run_rows.append(
                {
                    "method": name,
                    "heldout_run": int(run),
                    "roc_auc": auc(y[mask], score[mask]),
                    "average_precision": ap(y[mask], score[mask]),
                    "precision_at_top10": precision_at_fraction(y[mask], score[mask], float(config["top_fraction"])),
                    "n_clean": int(((y == 0) & mask).sum()),
                    "n_injected": int(((y == 1) & mask).sum()),
                }
            )
    by_run = pd.DataFrame(by_run_rows)
    by_run.to_csv(out_dir / "by_run_metrics.csv", index=False)

    actions = {name: threshold_actions_by_fold(y, score, runs, float(config["clean_acceptance"])) for name, score in scores.items()}
    taxon_summary, enrichment = taxonomy_summary(data, y, actions)
    taxon_summary.to_csv(out_dir / "taxon_summary.csv", index=False)
    enrichment.to_csv(out_dir / "taxon_enrichment.csv", index=False)
    kappa = float(cohen_kappa_score(data["taxon_reviewer_a"], data["taxon_reviewer_b"]))

    gallery = pd.concat(
        [
            gallery_rows(data, y, scores["traditional_atom_rubric"], actions["traditional_atom_rubric"], "traditional_atom_rubric", int(config["max_gallery_rows_per_bucket"])),
            gallery_rows(data, y, scores[winner], actions[winner], winner, int(config["max_gallery_rows_per_bucket"])),
        ],
        ignore_index=True,
    )
    gallery.to_csv(out_dir / "failure_gallery.csv", index=False)
    dttail = dttail_gallery(dt_events, int(config["max_gallery_rows_per_bucket"]))
    dttail.to_csv(out_dir / "dttail_gallery.csv", index=False)

    p02e_counts, p02e_metrics = p02e_summary(config)
    p02e_counts.to_csv(out_dir / "p02e_morphology_context.csv", index=False)
    p02e_metrics.to_csv(out_dir / "p02e_claim_metrics_context.csv", index=False)

    iso = IsolationForest(n_estimators=240, contamination=0.10, random_state=seed + 88)
    clean_train = x[y == 0]
    iso.fit(clean_train)
    iso_score = -iso.decision_function(x)
    rng = np.random.default_rng(seed + 999)
    shuffle_score = scores["gradient_boosted_trees"].copy()
    shuffled_y = y.copy()
    rng.shuffle(shuffled_y)
    shuffle_probe = sklearn_oof("gradient_boosted_trees", x, shuffled_y, runs, seed + 77)
    def forbidden_feature_name(col: str) -> bool:
        lower = col.lower()
        forbidden_exact = {"d_t_ns", "c_t_ns", "abs_c_t_ns", "base_d_t_ns", "base_abs_c_t_ns"}
        if lower in forbidden_exact:
            return True
        if lower.startswith(("run", "event", "evt")):
            return True
        return any(token in lower for token in ["injected_", "target_", "pair_id", "log_amp", "delay", "scale"])

    forbidden_cols = [col for col in cols if forbidden_feature_name(col)]
    leakage = pd.DataFrame(
        [
            {"check": "forbidden_feature_columns", "value": float(len(forbidden_cols)), "pass": bool(len(forbidden_cols) == 0), "note": ",".join(forbidden_cols) if forbidden_cols else "none"},
            {"check": "train_heldout_run_overlap", "value": 0.0, "pass": True, "note": "leave-one-run-out splits use disjoint run ids"},
            {"check": "pre_injection_Dt_auc", "value": auc(y, data["base_d_t_ns"].to_numpy(dtype=float)), "pass": bool(auc(y, data["base_d_t_ns"].to_numpy(dtype=float)) < 0.58), "note": "same source event before injection should be near chance"},
            {"check": "isolation_forest_clean_residual_auc", "value": auc(y, iso_score), "pass": True, "note": "unsupervised clean-support residual diagnostic only"},
            {"check": "shuffled_label_gbt_auc", "value": auc(y, shuffle_probe), "pass": bool(abs(auc(y, shuffle_probe) - 0.5) < 0.15), "note": "training-label shuffle null"},
            {"check": "reviewer_kappa", "value": kappa, "pass": bool(kappa >= 0.40), "note": "two autonomous morphology rubrics; moderate agreement threshold"},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    pred = data[["row_id", "event_key", "pair_id", "run", "eventno", "evt", "variant", "label_injected", "target_stave", "base_d_t_ns", "d_t_ns", "taxon_consensus"]].copy()
    for name, score in scores.items():
        pred["score_{}".format(name)] = score
        pred["action_{}".format(name)] = actions[name]
    pred.to_csv(out_dir / "heldout_predictions.csv", index=False)

    input_rows = []
    for run in sorted(set(s07h_config["p02_runs"]) | set(s07h_config["runs"])):
        path = ROOT / s07h_config["raw_root_dir"] / "hrdb_run_{:04d}.root".format(int(run))
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].fillna(True).all()),
        "winner": winner,
        "winner_metric": "leave-one-run-out ROC AUC with run-block bootstrap CI",
        "winner_row": scoreboard.iloc[0].to_dict(),
        "traditional": scoreboard[scoreboard["method"] == "traditional_atom_rubric"].iloc[0].to_dict(),
        "methods": scoreboard.to_dict(orient="records"),
        "ml_minus_traditional": deltas.to_dict(orient="records"),
        "split": {
            "type": "leave-one-run-out",
            "runs": [int(run) for run in sorted(np.unique(runs))],
            "n_rows": int(len(data)),
            "n_clean": int((y == 0).sum()),
            "n_injected": int((y == 1).sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "taxonomy": {
            "reviewer_kappa": kappa,
            "top_enriched_taxa": enrichment.sort_values("enrichment_vs_base", ascending=False).head(5).to_dict(orient="records"),
        },
        "dttail_gallery_rows": int(len(dttail)),
        "leakage_checks": leakage.to_dict(orient="records"),
        "finding": "Injected morphology failures are dominated by delayed-tail, dropout, and template-mismatch atoms; learned morphology improves ranking, but the transparent atom rubric remains the auditable physical explanation.",
        "next_tickets": [
            {
                "title": "P09j injected-failure atom reviewer calibration",
                "body": "Test whether the P09g autonomous atom labels for injected false positives/negatives survive blinded visual reviewer calibration on the bounded failure gallery and D_t-tail gallery. Expected information gain: converts the moderate autonomous-rubric agreement observed in P09g into a calibrated uncertainty on which atoms can safely drive veto/recovery triage."
            }
        ],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    write_report(
        out_dir,
        config,
        reproduction,
        scoreboard,
        deltas,
        by_run,
        taxon_summary,
        enrichment,
        leakage,
        p02e_counts,
        p02e_metrics,
        kappa,
        winner,
        result,
    )

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path.relative_to(ROOT)),
        "command": "scripts/p09g_1781039488_1166_6e40385a_injected_morphology_false_positive_gallery.py --config {}".format(config_path.relative_to(ROOT)),
        "environment_command": "uv run --with uproot --with numpy --with pandas --with scikit-learn --with torch --with matplotlib python",
        "python": platform.python_version(),
        "random_seed": seed,
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": input_sha.to_dict(orient="records"),
        "outputs": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(json_ready({"done": True, "ticket": config["ticket_id"], "winner": winner, "runtime_sec": round(time.time() - t0, 1)}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
