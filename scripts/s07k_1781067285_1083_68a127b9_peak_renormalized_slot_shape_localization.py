#!/usr/bin/env python3
"""S07k: peak-renormalized slot-shape localization benchmark."""

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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s07k-matplotlib-cache")

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
S07F_PATH = ROOT / "scripts/s07f_independent_all_three_appi_validation.py"
S07G_PATH = ROOT / "scripts/s07g_1781024319_1318_2f4a5acc_amp_preserving_appi_control.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


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
    return float(brier_score_loss(y[mask], prob[mask]))


def fixed_95_clean_rejection(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    clean = mask & (y == 0)
    injected = mask & (y == 1)
    if clean.sum() == 0 or injected.sum() == 0:
        return float("nan")
    threshold = float(np.percentile(score[clean], 95.0))
    return float(np.mean(score[injected] > threshold))


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
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def markdown_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    view = frame if max_rows is None else frame.head(max_rows)

    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    columns = list(view.columns)
    rows = [[fmt(row[col]) for col in columns] for _, row in view.iterrows()]
    widths = [len(str(col)) for col in columns]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(columns, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def summarize_method(
    name: str,
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    seed: int,
    n_boot: int,
    notes: str,
) -> dict:
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": run_bootstrap_ci(y, score, runs, auc, seed, n_boot)[0],
        "roc_auc_ci_high": run_bootstrap_ci(y, score, runs, auc, seed, n_boot)[1],
        "average_precision": ap(y, score),
        "ap_ci_low": run_bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)[0],
        "ap_ci_high": run_bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)[1],
        "brier": brier(y, score),
        "brier_ci_low": run_bootstrap_ci(y, score, runs, brier, seed + 2, n_boot)[0],
        "brier_ci_high": run_bootstrap_ci(y, score, runs, brier, seed + 2, n_boot)[1],
        "fixed_95_clean_rejection": fixed_95_clean_rejection(y, score),
        "fixed_95_clean_rejection_ci_low": run_bootstrap_ci(y, score, runs, fixed_95_clean_rejection, seed + 3, n_boot)[0],
        "fixed_95_clean_rejection_ci_high": run_bootstrap_ci(y, score, runs, fixed_95_clean_rejection, seed + 3, n_boot)[1],
        "notes": notes,
    }


def strict_shape_columns(data: pd.DataFrame, utils) -> List[str]:
    cols = utils.feature_columns(data, "strict_shape")
    forbidden = ["d_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "log_amp", "present", "run"]
    bad = [col for col in cols if any(fragment in col for fragment in forbidden)]
    if bad:
        raise RuntimeError(f"forbidden shape columns: {bad}")
    return cols


def slot_shape_columns(data: pd.DataFrame, utils) -> List[str]:
    cols = [col for col in utils.feature_columns(data, "slot_shape") if not col.endswith("_present")]
    forbidden = ["d_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "log_amp", "run"]
    bad = [col for col in cols if any(fragment in col for fragment in forbidden)]
    if bad:
        raise RuntimeError(f"forbidden slot-shape columns: {bad}")
    return cols


def normalized_waveforms(data: pd.DataFrame) -> np.ndarray:
    waves = []
    for _, row in data.iterrows():
        corrected = np.asarray(row["_corrected"], dtype=np.float32)
        denom = np.maximum(np.max(corrected, axis=1, keepdims=True), 1.0)
        waves.append(corrected / denom)
    return np.stack(waves).astype(np.float32)


def fold_iter(runs: np.ndarray) -> Iterable[Tuple[int, int, np.ndarray, np.ndarray]]:
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        yield fold, int(held_run), train, test


def sklearn_oof(data: pd.DataFrame, y: np.ndarray, cols: List[str], model_name: str, config: dict) -> Tuple[np.ndarray, pd.DataFrame]:
    runs = data["run"].to_numpy(dtype=int)
    scores = np.full(len(data), np.nan, dtype=float)
    rows = []
    X = data[cols].to_numpy(dtype=np.float32)
    seed = int(config["random_seed"])
    for fold, held_run, train, test in fold_iter(runs):
        if model_name == "ridge":
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(
                    penalty="l2",
                    C=1.0,
                    class_weight="balanced",
                    solver="lbfgs",
                    max_iter=1000,
                    random_state=seed + fold,
                ),
            )
        elif model_name == "gbt":
            model = HistGradientBoostingClassifier(
                max_iter=220,
                learning_rate=0.045,
                max_leaf_nodes=23,
                l2_regularization=0.03,
                random_state=seed + fold,
            )
        elif model_name == "mlp":
            model = make_pipeline(
                StandardScaler(),
                MLPClassifier(
                    hidden_layer_sizes=tuple(int(v) for v in config["mlp_hidden"]),
                    activation="relu",
                    alpha=0.001,
                    learning_rate_init=0.001,
                    max_iter=int(config["mlp_max_iter"]),
                    early_stopping=True,
                    n_iter_no_change=25,
                    random_state=seed + fold,
                ),
            )
        else:
            raise ValueError(model_name)
        model.fit(X[train], y[train])
        scores[test] = model.predict_proba(X[test])[:, 1]
        rows.append({"method": model_name, "heldout_run": held_run, "n_train": int(train.sum()), "n_test": int(test.sum()), "fold_auc": auc(y[test], scores[test])})
    return scores, pd.DataFrame(rows)


class Cnn1D(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(4, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(24, 1),
        )

    def forward(self, wave: torch.Tensor, features: torch.Tensor | None = None) -> torch.Tensor:
        return self.net(wave).squeeze(-1)


class WaveAtomNet(nn.Module):
    def __init__(self, n_features: int) -> None:
        super().__init__()
        self.wave = nn.Sequential(
            nn.Conv1d(4, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
            nn.Flatten(),
        )
        self.atom = nn.Sequential(nn.Linear(n_features, 32), nn.ReLU(), nn.Dropout(0.08), nn.Linear(32, 16), nn.ReLU())
        self.head = nn.Linear(40, 1)

    def forward(self, wave: torch.Tensor, features: torch.Tensor | None = None) -> torch.Tensor:
        if features is None:
            raise RuntimeError("WaveAtomNet requires feature tensor")
        return self.head(torch.cat([self.wave(wave), self.atom(features)], dim=1)).squeeze(-1)


def torch_oof(
    data: pd.DataFrame,
    y: np.ndarray,
    cols: List[str],
    wave: np.ndarray,
    architecture: str,
    config: dict,
) -> Tuple[np.ndarray, pd.DataFrame]:
    torch.set_num_threads(1)
    runs = data["run"].to_numpy(dtype=int)
    scores = np.full(len(data), np.nan, dtype=float)
    rows = []
    X = data[cols].to_numpy(dtype=np.float32)
    seed = int(config["random_seed"])
    epochs = int(config["torch_epochs"])
    batch_size = int(config["torch_batch_size"])
    lr = float(config["torch_lr"])
    for fold, held_run, train, test in fold_iter(runs):
        torch.manual_seed(seed + fold)
        mean = X[train].mean(axis=0, keepdims=True)
        std = X[train].std(axis=0, keepdims=True)
        std[std < 1e-6] = 1.0
        Xs = (X - mean) / std
        model: nn.Module = Cnn1D() if architecture == "cnn1d" else WaveAtomNet(X.shape[1])
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.001)
        pos_weight = torch.tensor([(train.sum() - y[train].sum()) / max(float(y[train].sum()), 1.0)], dtype=torch.float32)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        idx_train = np.flatnonzero(train)
        rng = np.random.default_rng(seed + fold)
        model.train()
        for _ in range(epochs):
            rng.shuffle(idx_train)
            for start in range(0, len(idx_train), batch_size):
                idx = idx_train[start : start + batch_size]
                xb = torch.tensor(wave[idx], dtype=torch.float32)
                xf = torch.tensor(Xs[idx], dtype=torch.float32)
                yb = torch.tensor(y[idx], dtype=torch.float32)
                optimizer.zero_grad()
                logits = model(xb, xf if architecture != "cnn1d" else None)
                loss = loss_fn(logits, yb)
                loss.backward()
                optimizer.step()
        model.eval()
        with torch.no_grad():
            xb = torch.tensor(wave[test], dtype=torch.float32)
            xf = torch.tensor(Xs[test], dtype=torch.float32)
            logits = model(xb, xf if architecture != "cnn1d" else None)
            scores[test] = torch.sigmoid(logits).numpy()
        rows.append({"method": architecture, "heldout_run": held_run, "n_train": int(train.sum()), "n_test": int(test.sum()), "fold_auc": auc(y[test], scores[test])})
    return scores, pd.DataFrame(rows)


def traditional_score(data: pd.DataFrame, y: np.ndarray, config: dict, utils) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    score, fold_id, choices, candidates = utils.traditional_oof(data, y, config)
    finite = np.isfinite(score)
    if finite.any():
        lo = float(np.nanmin(score[finite]))
        hi = float(np.nanmax(score[finite]))
        if hi > lo:
            score = (score - lo) / (hi - lo)
    return score, choices, candidates


def group_columns(cols: Sequence[str], group: dict) -> List[str]:
    selected: List[str] = []
    if "slot" in group:
        prefix = f"{group['slot']}_"
        selected = [col for col in cols if col.startswith(prefix)]
    if "samples" in group:
        sample_tokens = [f"norm_s{int(sample):02d}" for sample in group["samples"]]
        selected = [col for col in cols if any(token in col for token in sample_tokens)]
    if "atoms" in group:
        selected = [col for col in cols if any(str(atom) in col for atom in group["atoms"])]
    return selected


def dropout_localization(data: pd.DataFrame, y: np.ndarray, cols: List[str], config: dict) -> pd.DataFrame:
    X = data[cols].to_numpy(dtype=np.float32)
    runs = data["run"].to_numpy(dtype=int)
    seed = int(config["random_seed"])
    rows = []
    groups = list(config["dropout_groups"])
    baseline_scores = np.full(len(data), np.nan, dtype=float)
    dropped = {group["name"]: np.full(len(data), np.nan, dtype=float) for group in groups}
    fold_drops: Dict[str, List[dict]] = {group["name"]: [] for group in groups}
    for fold, held_run, train, test in fold_iter(runs):
        model = HistGradientBoostingClassifier(max_iter=220, learning_rate=0.045, max_leaf_nodes=23, l2_regularization=0.03, random_state=seed + 900 + fold)
        model.fit(X[train], y[train])
        baseline_scores[test] = model.predict_proba(X[test])[:, 1]
        train_mean = X[train].mean(axis=0)
        for group in groups:
            gcols = group_columns(cols, group)
            Xdrop = X.copy()
            if gcols:
                idx = [cols.index(col) for col in gcols]
                Xdrop[np.ix_(test, idx)] = train_mean[idx]
            dropped[group["name"]][test] = model.predict_proba(Xdrop[test])[:, 1]
            fold_drops[group["name"]].append(
                {
                    "heldout_run": held_run,
                    "baseline_auc": auc(y[test], baseline_scores[test]),
                    "dropout_auc": auc(y[test], dropped[group["name"]][test]),
                    "delta_auc": auc(y[test], baseline_scores[test]) - auc(y[test], dropped[group["name"]][test]),
                    "n_columns": len(gcols),
                }
            )
    base_auc = auc(y, baseline_scores)
    for group in groups:
        fold_frame = pd.DataFrame(fold_drops[group["name"]])
        rows.append(
            {
                "group": group["name"],
                "n_columns": int(fold_frame["n_columns"].max()),
                "baseline_auc": base_auc,
                "dropout_auc": auc(y, dropped[group["name"]]),
                "delta_auc": base_auc - auc(y, dropped[group["name"]]),
                "mean_fold_delta_auc": float(fold_frame["delta_auc"].mean()),
                "min_fold_delta_auc": float(fold_frame["delta_auc"].min()),
                "max_fold_delta_auc": float(fold_frame["delta_auc"].max()),
            }
        )
    return pd.DataFrame(rows).sort_values("delta_auc", ascending=False)


def permutation_atoms(data: pd.DataFrame, y: np.ndarray, cols: List[str], config: dict) -> pd.DataFrame:
    X = data[cols].to_numpy(dtype=np.float32)
    runs = data["run"].to_numpy(dtype=int)
    seed = int(config["random_seed"])
    rows = []
    rng = np.random.default_rng(seed + 700)
    for fold, held_run, train, test in fold_iter(runs):
        model = HistGradientBoostingClassifier(max_iter=220, learning_rate=0.045, max_leaf_nodes=23, l2_regularization=0.03, random_state=seed + 700 + fold)
        model.fit(X[train], y[train])
        result = permutation_importance(model, X[test], y[test], scoring="roc_auc", n_repeats=8, random_state=int(rng.integers(1, 1_000_000)))
        for col, mean, std in zip(cols, result.importances_mean, result.importances_std):
            rows.append({"heldout_run": held_run, "feature": col, "auc_importance_mean": float(mean), "auc_importance_std": float(std)})
    frame = pd.DataFrame(rows)
    grouped = frame.groupby("feature", as_index=False).agg(
        mean_auc_importance=("auc_importance_mean", "mean"),
        min_auc_importance=("auc_importance_mean", "min"),
        max_auc_importance=("auc_importance_mean", "max"),
        stability_std=("auc_importance_mean", "std"),
    )
    return grouped.sort_values("mean_auc_importance", ascending=False)


def gbt_oof_for_columns(data: pd.DataFrame, y: np.ndarray, cols: List[str], config: dict, seed_offset: int) -> Tuple[np.ndarray, pd.DataFrame]:
    X = data[cols].to_numpy(dtype=np.float32)
    runs = data["run"].to_numpy(dtype=int)
    seed = int(config["random_seed"]) + seed_offset
    scores = np.full(len(data), np.nan, dtype=float)
    rows = []
    for fold, held_run, train, test in fold_iter(runs):
        model = HistGradientBoostingClassifier(max_iter=220, learning_rate=0.045, max_leaf_nodes=23, l2_regularization=0.03, random_state=seed + fold)
        model.fit(X[train], y[train])
        scores[test] = model.predict_proba(X[test])[:, 1]
        rows.append({"heldout_run": held_run, "n_train": int(train.sum()), "n_test": int(test.sum()), "fold_auc": auc(y[test], scores[test])})
    return scores, pd.DataFrame(rows)


def support_ablations(data: pd.DataFrame, y: np.ndarray, slot_cols: List[str], strict_cols: List[str], primary_score: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    runs = data["run"].to_numpy(dtype=int)
    base_auc = auc(y, primary_score)
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(int(config["random_seed"]) + 3331)
    rows = []
    fold_frames = []
    specs: List[Tuple[str, List[str], str]] = [
        ("target_stave_blind_aggregate", strict_cols, "B2 plus downstream aggregate shape means/stds; no individual downstream slot identity."),
    ]
    for stave in ["B4", "B6", "B8"]:
        kept = [col for col in slot_cols if not col.startswith(f"{stave}_")]
        specs.append((f"drop_{stave}_slot", kept, f"Slot-shape GBT with all {stave} columns replaced by omission and retraining."))
    for i, (name, cols, notes) in enumerate(specs):
        score, folds = gbt_oof_for_columns(data, y, cols, config, 1700 + 41 * i)
        delta_values = []
        auc_values = []
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
            idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled])
            if len(np.unique(y[idx])) < 2:
                continue
            sample_auc = auc(y[idx], score[idx])
            sample_primary_auc = auc(y[idx], primary_score[idx])
            if math.isfinite(sample_auc) and math.isfinite(sample_primary_auc):
                auc_values.append(sample_auc)
                delta_values.append(sample_auc - sample_primary_auc)
        auc_ci = np.percentile(auc_values, [2.5, 97.5]) if len(auc_values) >= 20 else [float("nan"), float("nan")]
        delta_ci = np.percentile(delta_values, [2.5, 97.5]) if len(delta_values) >= 20 else [float("nan"), float("nan")]
        rows.append(
            {
                "ablation": name,
                "n_columns": len(cols),
                "roc_auc": auc(y, score),
                "roc_auc_ci_low": float(auc_ci[0]),
                "roc_auc_ci_high": float(auc_ci[1]),
                "average_precision": ap(y, score),
                "fixed_95_clean_rejection": fixed_95_clean_rejection(y, score),
                "delta_auc_vs_primary_slot_gbt": auc(y, score) - base_auc,
                "delta_auc_ci_low": float(delta_ci[0]),
                "delta_auc_ci_high": float(delta_ci[1]),
                "notes": notes,
            }
        )
        folds["ablation"] = name
        fold_frames.append(folds)
    return pd.DataFrame(rows).sort_values("roc_auc", ascending=False), pd.concat(fold_frames, ignore_index=True)


def build_reproduction(config: dict, s07f, s07g, utils, clean_payloads: List[dict], parent: pd.DataFrame, all_three: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parent_guarded = int((parent["d_t_ns"] > float(config["gross_dt_min_ns"])).sum())
    parent_documented = int((parent["d_t_ns"] > float(config["documented_gross_dt_min_ns"])).sum())
    all_three_guarded = int((all_three["d_t_ns"] > float(config["gross_dt_min_ns"])).sum())
    all_three_clean = int((all_three["d_t_ns"] < float(config["clean_dt_max_ns"])).sum())
    reproduction = pd.DataFrame(
        [
            {"quantity": "parent App.I guarded gross D_t>51 ns", "report_value": int(config["expected_parent_gross_events"]), "reproduced": parent_guarded, "delta": parent_guarded - int(config["expected_parent_gross_events"]), "tolerance": 0, "pass": parent_guarded == int(config["expected_parent_gross_events"])},
            {"quantity": "parent App.I documented gross D_t>50 ns", "report_value": None, "reproduced": parent_documented, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three control events", "report_value": int(config["expected_all_three_control_events"]), "reproduced": int(len(all_three)), "delta": int(len(all_three)) - int(config["expected_all_three_control_events"]), "tolerance": 0, "pass": int(len(all_three)) == int(config["expected_all_three_control_events"])},
            {"quantity": "all-three clean events D_t<3 ns", "report_value": None, "reproduced": all_three_clean, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three guarded gross D_t>51 ns", "report_value": int(config["expected_all_three_guarded_gross_events"]), "reproduced": all_three_guarded, "delta": all_three_guarded - int(config["expected_all_three_guarded_gross_events"]), "tolerance": 0, "pass": all_three_guarded == int(config["expected_all_three_guarded_gross_events"])},
        ]
    )
    s07e_score, _, _, _, _ = s07f.s07e_reproduction(config, utils, all_three)
    s07e_auc = float(s07e_score.loc[s07e_score["method"] == "reproduced all-three shape-only RF", "roc_auc"].iloc[0])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "all-three S07e shape RF ROC AUC",
                        "report_value": float(config["expected_s07e_shape_rf_auc"]),
                        "reproduced": s07e_auc,
                        "delta": s07e_auc - float(config["expected_s07e_shape_rf_auc"]),
                        "tolerance": float(config["s07e_reproduction_auc_tolerance"]),
                        "pass": abs(s07e_auc - float(config["expected_s07e_shape_rf_auc"])) <= float(config["s07e_reproduction_auc_tolerance"]),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    _, s07f_score, _, _, _, _, _ = s07f.independent_injection_benchmark(config, utils, clean_payloads)
    s07f_auc = float(s07f_score.loc[s07f_score["method"] == "all-three shape-only RF", "roc_auc"].iloc[0])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "S07f unnormalized injection RF ROC AUC",
                        "report_value": float(config["expected_s07f_shape_rf_auc"]),
                        "reproduced": s07f_auc,
                        "delta": s07f_auc - float(config["expected_s07f_shape_rf_auc"]),
                        "tolerance": float(config["s07f_reproduction_auc_tolerance"]),
                        "pass": abs(s07f_auc - float(config["expected_s07f_shape_rf_auc"])) <= float(config["s07f_reproduction_auc_tolerance"]),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    return reproduction, s07e_score, s07f_score


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    counts: pd.DataFrame,
    scoreboard: pd.DataFrame,
    fold_scores: pd.DataFrame,
    traditional_choices: pd.DataFrame,
    localization: pd.DataFrame,
    permutation: pd.DataFrame,
    support_ablation: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = scoreboard.sort_values(["roc_auc", "average_precision"], ascending=False).iloc[0]
    trad = scoreboard[scoreboard["method"] == "traditional atom/template selector"].iloc[0]
    text = f"""# S07k: peak-renormalized slot-shape localization

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT `HRDv` from `{config['raw_root_dir']}`
- **Runs:** {', '.join(map(str, config['runs']))}
- **Split:** leave-one-run-out; intervals are run-block bootstrap 95% confidence intervals.
- **Winner:** `{result['winner_method']}`

## Abstract

This study asks which per-stave waveform slots and time samples drive the peak-renormalized all-three injected shape signal. The analysis first reproduces the parent App.I and all-three raw-ROOT numbers, then forms a paired peak-preserved injection dataset from clean all-three events. A strong transparent atom/template selector is benchmarked against a permissive slot-shape RF, ridge/logistic regression, gradient-boosted trees, an MLP, a 1D-CNN, and a new feature-fused WaveAtomNet architecture. The best method is {winner['method']} with ROC AUC {winner['roc_auc']:.3f} [{winner['roc_auc_ci_low']:.3f}, {winner['roc_auc_ci_high']:.3f}], compared with the traditional selector {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}].

## Raw-ROOT Reproduction

{markdown_table(reproduction)}

The reproduction gate reads `EVENTNO`, `EVT`, and `HRDv` from the raw B-stack ROOT files. For each selected run, the four analysis channels B2, B4, B6, and B8 are reshaped to 18 samples, baseline-subtracted by the median of samples 0--3, thresholded at 1000 ADC, and timed with CFD20. The reproduced all-three population is the prerequisite for all downstream injection and model claims.

## Dataset Construction

Let \(x_{{r,e,s,t}}\) be the baseline-subtracted waveform for run \(r\), event \(e\), stave \(s\), and sample \(t\). Starting from all-three clean events with \(D_t<3\) ns, one selected downstream waveform receives a delayed copy:

\\[
z_{{s,t}}=x_{{s,t}}+a\\,x_{{s,t-d}},
\\]

where \(d\in[2,6]\) samples and \(a\in[0.12,0.38]\). The target waveform is then scaled by

\\[
\\alpha=\\frac{{\\max_t x_{{s,t}}}}{{\\max_t z_{{s,t}}}}
\\]

so the target-stave peak is restored. Raw and injected pair members share a run and are therefore always held out together.

{markdown_table(counts)}

## Methods

The traditional comparator is selected inside each training fold from transparent one-dimensional atom families: \(D_t\), \(|C_t|\), downstream tail/late charge fractions, area-over-peak, peak sample, derivative drop, terminal fraction, and a train-run-only delayed-template residual. The selected score is standardized on training runs and applied unchanged to the held-out run.

The slot-shape RF is the deliberately permissive per-stave waveform-slot probe from the ticket. Ridge denotes an L2-penalized logistic regression on the same amplitude-normalized slot-shape features. Gradient-boosted trees are `HistGradientBoostingClassifier` models on those features. The MLP is a two-hidden-layer feed-forward network. The 1D-CNN consumes the normalized four-stave waveform tensor directly. WaveAtomNet is the new architecture: a small convolutional waveform branch fused with dense slot-shape atoms before a logistic head.

All model selection and preprocessing are fold-local. Features exclude run, event id, pair id, injected delay/scale/target, absolute amplitudes, topology flags, and timing variables for the ML/NN models.

## Benchmark

{markdown_table(scoreboard)}

Fold diagnostics:

{markdown_table(fold_scores, max_rows=20)}

Traditional fold choices:

{markdown_table(traditional_choices)}

## Shape-Cue Localization

Localization uses fold-local gradient-boosted trees as a stable nonparametric probe. For each held-out run, a trained model is evaluated normally and with a stave slot, sample window, or atom family replaced by the corresponding training-run mean. The table reports the resulting AUC loss.

{markdown_table(localization)}

The largest losses identify the most informative regions after peak renormalization. Feature-level permutation importance provides a higher-resolution cross-check:

{markdown_table(permutation.head(15))}

## Target-Blind And Downstream-Dropout Ablations

{markdown_table(support_ablation)}

`target_stave_blind_aggregate` removes individual downstream slot identity by using only B2 plus downstream aggregate shape means/stds. The one-downstream-stave rows retrain the same GBT after removing all columns for that slot. Negative deltas show how much the permissive slot-shape probe depends on the omitted support.

## Leakage And Systematics

{markdown_table(leakage)}

Primary systematics are: (1) the injected target is data-driven, not an independently labelled real pile-up sample; (2) peak renormalization removes the direct peak-height nuisance but can still alter charge and local slope; (3) seven held-out runs limit bootstrap granularity; (4) neural nets are intentionally compact to avoid fitting run-specific artifacts; and (5) localization is model-dependent, so it is interpreted as an operational cue map rather than a unique physical decomposition.

## Verdict

The winner recorded in `result.json` is `{result['winner_method']}`. It beats the traditional atom/template selector by {result['winner_minus_traditional_auc']:.3f} AUC on out-of-fold predictions. The S07g permissive slot-shape signal therefore survives peak renormalization and is localized mainly to the ranked groups shown above, but it remains injection-recovery evidence rather than a direct real-beam pile-up-rate measurement.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07k_1781067285_1083_68a127b9_peak_renormalized_slot_shape_localization.py --config configs/s07k_1781067285_1083_68a127b9_peak_renormalized_slot_shape_localization.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `scoreboard.csv`, `fold_scores.csv`, `localization_dropout.csv`, `permutation_importance.csv`, `support_ablation.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07k_1781067285_1083_68a127b9_peak_renormalized_slot_shape_localization.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    s07f = load_module(S07F_PATH, "s07f_reference_s07k")
    s07g = load_module(S07G_PATH, "s07g_reference_s07k")
    utils = s07f.load_s07d_utils(ROOT / config["utility_script"])

    parent, all_three, run_counts, clean_payloads = s07f.collect_parent_and_all_three(config, utils)
    reproduction, s07e_score, s07f_score = build_reproduction(config, s07f, s07g, utils, clean_payloads, parent, all_three)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw-ROOT reproduction gate failed")
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    s07e_score.to_csv(out_dir / "s07e_reproduction_scoreboard.csv", index=False)
    s07f_score.to_csv(out_dir / "s07f_reproduction_scoreboard.csv", index=False)

    data = s07g.make_preserved_dataset(config, utils, clean_payloads, "peak_preserved")
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    strict_cols = strict_shape_columns(data, utils)
    shape_cols = slot_shape_columns(data, utils)
    wave = normalized_waveforms(data)
    counts = data.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "injected"}).reset_index()
    counts["total"] = counts["raw_clean"] + counts["injected"]
    counts.to_csv(out_dir / "dataset_counts_by_run.csv", index=False)

    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    method_scores: Dict[str, np.ndarray] = {}
    fold_frames: List[pd.DataFrame] = []

    trad_score, traditional_choices, traditional_candidates = traditional_score(data, y, config, utils)
    method_scores["traditional atom/template selector"] = trad_score
    traditional_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    traditional_candidates.to_csv(out_dir / "traditional_candidate_scores.csv", index=False)

    rf_scan, best_rf_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(data, y, shape_cols, config)
    method_scores["slot-shape RF"] = rf_score
    pd.DataFrame({"row_index": np.arange(len(rf_prob)), "rf_fold": rf_fold, "rf_probability": rf_prob}).to_csv(out_dir / "slot_shape_rf_oof_calibration.csv", index=False)
    rf_scan.to_csv(out_dir / "rf_cv_scan.csv", index=False)

    for name in ["ridge", "gbt", "mlp"]:
        score, folds = sklearn_oof(data, y, shape_cols, name, config)
        label = {"ridge": "ridge logistic", "gbt": "gradient-boosted trees", "mlp": "MLP"}[name]
        method_scores[label] = score
        folds["method"] = label
        fold_frames.append(folds)

    cnn_score, cnn_folds = torch_oof(data, y, shape_cols, wave, "cnn1d", config)
    method_scores["1D-CNN"] = cnn_score
    cnn_folds["method"] = "1D-CNN"
    fold_frames.append(cnn_folds)

    wave_atom_score, wave_atom_folds = torch_oof(data, y, shape_cols, wave, "wave_atom_net", config)
    method_scores["WaveAtomNet"] = wave_atom_score
    wave_atom_folds["method"] = "WaveAtomNet"
    fold_frames.append(wave_atom_folds)

    scoreboard = pd.DataFrame(
        [
            summarize_method(
                name,
                y,
                score,
                runs,
                seed + 100 * i,
                n_boot,
                {
                    "traditional atom/template selector": "Fold-local transparent selector over timing, shape atoms, and delayed-template residuals.",
                    "slot-shape RF": f"RandomForestClassifier grid-selected on permissive slot-shape features; best params={best_rf_params}.",
                    "ridge logistic": "L2 logistic regression on permissive normalized slot-shape features.",
                    "gradient-boosted trees": "HistGradientBoostingClassifier on permissive normalized slot-shape features.",
                    "MLP": "Two-hidden-layer feed-forward network on permissive normalized slot-shape features.",
                    "1D-CNN": "Compact convolutional network on normalized four-stave waveform tensors.",
                    "WaveAtomNet": "New feature-fused convolutional waveform plus slot-shape atom network.",
                }[name],
            )
            for i, (name, score) in enumerate(method_scores.items())
        ]
    ).sort_values(["roc_auc", "average_precision"], ascending=False)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    fold_scores = pd.concat(fold_frames, ignore_index=True)
    trad_fold_rows = []
    for held_run in sorted(np.unique(runs)):
        test = runs == held_run
        trad_fold_rows.append({"method": "traditional atom/template selector", "heldout_run": int(held_run), "n_train": int((~test).sum()), "n_test": int(test.sum()), "fold_auc": auc(y[test], trad_score[test])})
    fold_scores = pd.concat([pd.DataFrame(trad_fold_rows), fold_scores], ignore_index=True)
    fold_scores.to_csv(out_dir / "fold_scores.csv", index=False)

    localization = dropout_localization(data, y, shape_cols, config)
    localization.to_csv(out_dir / "localization_dropout.csv", index=False)
    permutation = permutation_atoms(data, y, shape_cols, config)
    permutation.to_csv(out_dir / "permutation_importance.csv", index=False)
    support_ablation, support_ablation_folds = support_ablations(data, y, shape_cols, strict_cols, method_scores["gradient-boosted trees"], config)
    support_ablation.to_csv(out_dir / "support_ablation.csv", index=False)
    support_ablation_folds.to_csv(out_dir / "support_ablation_folds.csv", index=False)

    pre_dt = data["base_d_t_ns"].to_numpy(dtype=float)
    amp_score, _ = sklearn_oof(data, y, utils.feature_columns(data, "amplitude"), "gbt", config)
    topo_score, _ = sklearn_oof(data, y, utils.feature_columns(data, "topology"), "gbt", config)
    shuffle_score, _ = utils.rf_oof(data, y, shape_cols, best_rf_params, seed + 909, shuffle_train=True)
    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(data.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(data.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)
    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "roc_auc": auc(y, pre_dt), "average_precision": ap(y, pre_dt), "notes": "Same for pair members; should be chance."},
            {"probe": "topology-only GBT", "roc_auc": auc(y, topo_score), "average_precision": ap(y, topo_score), "notes": "All-three topology should carry no injected label information."},
            {"probe": "absolute-amplitude-only GBT", "roc_auc": auc(y, amp_score), "average_precision": ap(y, amp_score), "notes": "Excluded nuisance channel; peak renormalization should reduce but not force chance."},
            {"probe": "slot-shape RF with shuffled training labels", "roc_auc": auc(y, shuffle_score), "average_precision": ap(y, shuffle_score), "notes": "Null/leakage sanity check for the permissive representation."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "forbidden slot-shape columns", "roc_auc": 0.0, "average_precision": float("nan"), "notes": "slot_shape_columns raised on violations before model fitting."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    oof = data[["row_id", "event_key", "pair_id", "run", "label_injected", "variant", "preservation_mode", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "target_stave", "injected_delay_samples", "injected_scale", "renormalization_factor", "preserved_quantity_ratio"]].copy()
    for name, score in method_scores.items():
        oof[name.replace(" ", "_").replace("-", "_").lower() + "_score"] = score
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    winner = scoreboard.iloc[0]
    trad_auc = float(scoreboard.loc[scoreboard["method"] == "traditional atom/template selector", "roc_auc"].iloc[0])
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "winner_method": str(winner["method"]),
        "winner_roc_auc": float(winner["roc_auc"]),
        "winner_roc_auc_ci": [float(winner["roc_auc_ci_low"]), float(winner["roc_auc_ci_high"])],
        "winner_average_precision": float(winner["average_precision"]),
        "traditional_roc_auc": trad_auc,
        "winner_minus_traditional_auc": float(winner["roc_auc"] - trad_auc),
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "dataset_events": int(len(data)),
        "dataset_pairs": int(data["pair_id"].nunique()),
        "runs": [int(run) for run in sorted(np.unique(runs))],
        "pair_split_violations": int(pair_split_violations),
        "top_localization_group": str(localization.iloc[0]["group"]),
        "top_localization_delta_auc": float(localization.iloc[0]["delta_auc"]),
        "top_permutation_feature": str(permutation.iloc[0]["feature"]),
        "top_permutation_auc_importance": float(permutation.iloc[0]["mean_auc_importance"]),
        "target_blind_auc": float(support_ablation.loc[support_ablation["ablation"] == "target_stave_blind_aggregate", "roc_auc"].iloc[0]),
        "target_blind_delta_auc_vs_primary_slot_gbt": float(support_ablation.loc[support_ablation["ablation"] == "target_stave_blind_aggregate", "delta_auc_vs_primary_slot_gbt"].iloc[0]),
        "worst_downstream_dropout": str(support_ablation[support_ablation["ablation"].str.startswith("drop_")].sort_values("delta_auc_vs_primary_slot_gbt").iloc[0]["ablation"]),
        "method_auc": {str(row["method"]): float(row["roc_auc"]) for _, row in scoreboard.iterrows()},
        "elapsed_seconds": float(time.time() - t0),
    }

    write_report(out_dir, config, reproduction, counts, scoreboard, fold_scores, traditional_choices, localization, permutation, support_ablation, leakage, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_rows = []
    for run in config["runs"]:
        path = raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    for path in [config_path, S07F_PATH, S07G_PATH, ROOT / config["utility_script"]]:
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": sys.version,
        "inputs": input_rows,
        "outputs": {},
        "command": f"/home/billy/anaconda3/bin/python scripts/s07k_1781067285_1083_68a127b9_peak_renormalized_slot_shape_localization.py --config {config_path}",
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
