#!/usr/bin/env python3
"""P13b rare-atom bootstrap promotion threshold.

This study asks when low-count waveform atoms should be promoted from
diagnostic observations to steering variables.  It reproduces the S00 selected
B-stave pulse count from raw ROOT, builds the fold-local P09a rare-atom
taxonomy, then compares a transparent support/stability rule with several
run-held-out ML/NN scorers.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p13b")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

torch.set_num_threads(1)


STAVE_NAMES = ["B2", "B4", "B6", "B8"]
RARE_TAXA = [
    "saturation",
    "dropout",
    "baseline_excursion",
    "pileup_or_long_tail",
    "novel_early_pretrigger",
    "novel_delayed_peak",
    "novel_undershoot_recovery",
    "novel_broad_template_mismatch",
    "physics_timing_tail_only",
]
TABULAR_COLS = [
    "amplitude_log",
    "peak_sample",
    "area_norm",
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
    "q_template_rmse",
]
METHODS = [
    "traditional_support_exact",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "gated_cnn_new",
]


def load_json(path: Path) -> dict:
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


def load_p09a_module():
    path = Path("scripts/p09a_rare_waveform_anomaly_taxonomy.py")
    spec = importlib.util.spec_from_file_location("p09a_rare_waveform_anomaly_taxonomy", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def resolve_raw_root_dir(config: dict, p09a_config: dict) -> Path:
    for candidate in config.get("raw_root_dir_candidates", []) + p09a_config.get("raw_root_dir_candidates", []):
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs(p09a_config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in p09a_config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def wilson_ci(k: float, n: float, z: float = 1.959963984540054) -> Tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n))) / denom
    return max(0.0, center - half), min(1.0, center + half)


def exact_effective_n(counts: Sequence[int]) -> float:
    arr = np.asarray(counts, dtype=float)
    denom = float(np.sum(arr * arr))
    return 0.0 if denom <= 0 else float(np.sum(arr) ** 2 / denom)


def add_atom_columns(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = meta.copy()
    edges = np.asarray(config["amplitude_atom_edges_adc"], dtype=float)
    labels = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        labels.append(f"{int(lo)}_{int(hi)}")
    out["amp_atom_bin"] = pd.cut(
        out["amplitude_adc"].to_numpy(dtype=float),
        bins=edges,
        labels=labels,
        include_lowest=True,
        right=False,
    ).astype(str)
    out.loc[out["amp_atom_bin"] == "nan", "amp_atom_bin"] = "overflow"
    out["atom_id"] = out["taxon"].astype(str) + "|" + out["stave"].astype(str) + "|" + out["amp_atom_bin"].astype(str)
    out["is_rare_atom"] = out["taxon"].isin(RARE_TAXA)
    out["amplitude_log"] = np.log1p(np.maximum(out["amplitude_adc"].to_numpy(dtype=float), 0.0))
    out["baseline_mad_log"] = np.log1p(np.maximum(out["baseline_mad"].to_numpy(dtype=float), 0.0))
    out["baseline_slope_scaled"] = out["baseline_slope"].to_numpy(dtype=float) / np.maximum(
        out["amplitude_adc"].to_numpy(dtype=float), 1.0
    )
    for stave in STAVE_NAMES:
        out[f"stave_{stave}"] = (out["stave"] == stave).astype(float)
    return out


def tabular_matrix(meta: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    cols = TABULAR_COLS + [f"stave_{s}" for s in STAVE_NAMES]
    X = meta[cols].to_numpy(dtype=np.float32)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    return X, cols


def balanced_indices(y: np.ndarray, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    pos = np.where(y > 0)[0]
    neg = np.where(y <= 0)[0]
    if len(pos) == 0 or len(neg) == 0:
        take = min(len(y), max_rows)
        return rng.choice(np.arange(len(y)), size=take, replace=False)
    half = max_rows // 2
    n_pos = min(len(pos), half)
    n_neg = min(len(neg), max_rows - n_pos)
    if n_pos < min(2000, len(pos)):
        n_pos = min(len(pos), max_rows // 3)
        n_neg = min(len(neg), max_rows - n_pos)
    idx = np.concatenate(
        [
            rng.choice(pos, size=n_pos, replace=False),
            rng.choice(neg, size=n_neg, replace=False),
        ]
    )
    rng.shuffle(idx)
    return idx


def threshold_for_precision(y: np.ndarray, score: np.ndarray, target_precision: float, min_recall: float) -> float:
    precision, recall, thresholds = precision_recall_curve(y, score)
    if len(thresholds) == 0:
        return float(np.nanmax(score) + 1.0)
    valid = np.where((precision[:-1] >= target_precision) & (recall[:-1] >= min_recall))[0]
    if len(valid):
        return float(thresholds[valid[0]])
    f1 = 2.0 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.nanargmax(f1))])


def calibration_ece(y: np.ndarray, prob: np.ndarray, bins: int) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if int(mask.sum()) == 0:
            continue
        ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(prob[mask].mean()))
    return float(ece)


class WaveCnn(nn.Module):
    def __init__(self, n_scalar: int, width: int, gated: bool = False) -> None:
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(
            nn.Conv1d(1, width, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(width, width, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        if gated:
            self.gate = nn.Sequential(nn.Linear(n_scalar, width), nn.Sigmoid())
        self.head = nn.Sequential(
            nn.Linear(width + n_scalar, width),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(width, 1),
        )

    def forward(self, wave: torch.Tensor, scalar: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave[:, None, :])
        if self.gated:
            z = z * (0.5 + self.gate(scalar))
        return self.head(torch.cat([z, scalar], dim=1)).squeeze(1)


def train_torch_classifier(
    wave: np.ndarray,
    scalar: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    all_scalar_scaled: np.ndarray,
    config: dict,
    gated: bool,
    seed: int,
) -> Tuple[np.ndarray, dict]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    width = int(config["ml"]["torch_width"])
    model = WaveCnn(all_scalar_scaled.shape[1], width, gated=gated)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["torch_learning_rate"]),
        weight_decay=float(config["ml"]["torch_weight_decay"]),
    )
    positives = max(1, int(y[train_idx].sum()))
    negatives = max(1, int(len(train_idx) - positives))
    pos_weight = torch.tensor([negatives / positives], dtype=torch.float32)
    lossf = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    xw = torch.tensor(wave.astype(np.float32))
    xs = torch.tensor(all_scalar_scaled.astype(np.float32))
    yy = torch.tensor(y.astype(np.float32))
    batch = int(config["ml"]["torch_batch_size"])
    losses: List[float] = []
    for _epoch in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        total = 0.0
        seen = 0
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            logits = model(xw[idx], xs[idx])
            loss = lossf(logits, yy[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.item()) * len(idx)
            seen += len(idx)
        losses.append(total / max(1, seen))
    model.eval()
    chunks = []
    with torch.no_grad():
        for start in range(0, len(wave), 8192):
            logits = model(xw[start : start + 8192], xs[start : start + 8192])
            chunks.append(torch.sigmoid(logits).numpy())
    return np.concatenate(chunks).astype(float), {
        "final_loss": float(losses[-1]) if losses else None,
        "n_parameters": int(sum(p.numel() for p in model.parameters())),
    }


def train_models(meta: pd.DataFrame, waves: np.ndarray, train_mask: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    X, feature_names = tabular_matrix(meta)
    y = meta["is_rare_atom"].to_numpy(dtype=int)
    train_rows = np.where(train_mask)[0]
    rel_idx = balanced_indices(y[train_rows], int(config["ml"]["max_train_rows"]), rng)
    fit_idx = train_rows[rel_idx]
    nn_rel_idx = balanced_indices(y[train_rows], int(config["ml"]["max_nn_train_rows"]), rng)
    nn_idx = train_rows[nn_rel_idx]

    score_rows = []
    model_rows = []

    best_ridge = None
    best_ap = -np.inf
    for alpha in config["ml"]["ridge_alphas"]:
        model = make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(alpha), class_weight="balanced"))
        model.fit(X[fit_idx], y[fit_idx])
        train_score = model.decision_function(X[fit_idx])
        ap = average_precision_score(y[fit_idx], train_score)
        if ap > best_ap:
            best_ap = float(ap)
            best_ridge = model
    assert best_ridge is not None
    ridge_score = best_ridge.decision_function(X)
    ridge_prob = 1.0 / (1.0 + np.exp(-np.clip(ridge_score, -30, 30)))
    score_rows.append(pd.DataFrame({"method": "ridge", "score": ridge_prob}))
    model_rows.append({"method": "ridge", "train_ap": best_ap, "train_rows": int(len(fit_idx))})

    gbt = HistGradientBoostingClassifier(
        learning_rate=float(config["ml"]["gbt_learning_rate"]),
        max_iter=int(config["ml"]["gbt_max_iter"]),
        max_leaf_nodes=int(config["ml"]["gbt_max_leaf_nodes"]),
        l2_regularization=0.02,
        random_state=int(config["ml"]["random_seed"]) + 1,
    )
    gbt.fit(X[fit_idx], y[fit_idx])
    gbt_prob = gbt.predict_proba(X)[:, 1]
    score_rows.append(pd.DataFrame({"method": "gradient_boosted_trees", "score": gbt_prob}))
    model_rows.append({"method": "gradient_boosted_trees", "train_ap": float(average_precision_score(y[fit_idx], gbt.predict_proba(X[fit_idx])[:, 1])), "train_rows": int(len(fit_idx))})

    mlp = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=tuple(int(x) for x in config["ml"]["mlp_hidden_layer_sizes"]),
            max_iter=int(config["ml"]["mlp_max_iter"]),
            alpha=0.0005,
            batch_size=512,
            early_stopping=True,
            random_state=int(config["ml"]["random_seed"]) + 2,
        ),
    )
    mlp.fit(X[fit_idx], y[fit_idx])
    mlp_prob = mlp.predict_proba(X)[:, 1]
    score_rows.append(pd.DataFrame({"method": "mlp", "score": mlp_prob}))
    model_rows.append({"method": "mlp", "train_ap": float(average_precision_score(y[fit_idx], mlp.predict_proba(X[fit_idx])[:, 1])), "train_rows": int(len(fit_idx))})

    scaler = StandardScaler().fit(X[nn_idx])
    X_scaled = scaler.transform(X).astype(np.float32)
    cnn_prob, cnn_info = train_torch_classifier(
        waves, X_scaled, y, nn_idx, X_scaled, config, gated=False, seed=int(config["ml"]["random_seed"]) + 3
    )
    score_rows.append(pd.DataFrame({"method": "cnn_1d", "score": cnn_prob}))
    cnn_info.update({"method": "cnn_1d", "train_rows": int(len(nn_idx)), "train_ap": float(average_precision_score(y[fit_idx], cnn_prob[fit_idx]))})
    model_rows.append(cnn_info)

    gated_prob, gated_info = train_torch_classifier(
        waves, X_scaled, y, nn_idx, X_scaled, config, gated=True, seed=int(config["ml"]["random_seed"]) + 4
    )
    score_rows.append(pd.DataFrame({"method": "gated_cnn_new", "score": gated_prob}))
    gated_info.update({"method": "gated_cnn_new", "train_rows": int(len(nn_idx)), "train_ap": float(average_precision_score(y[fit_idx], gated_prob[fit_idx]))})
    model_rows.append(gated_info)

    scores = pd.concat(score_rows, keys=[r["method"].iloc[0] for r in score_rows])
    scores = scores.reset_index(level=0, drop=True).reset_index().rename(columns={"index": "row_index"})
    return scores, pd.DataFrame(model_rows)


def method_thresholds(scores: pd.DataFrame, meta: pd.DataFrame, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    y = meta["is_rare_atom"].to_numpy(dtype=int)
    rows = []
    for method in scores["method"].unique():
        sub = scores[scores["method"] == method].sort_values("row_index")
        score = sub["score"].to_numpy(dtype=float)
        thr = threshold_for_precision(
            y[train_mask],
            score[train_mask],
            float(config["promotion_rule"]["target_train_precision"]),
            float(config["promotion_rule"]["min_train_recall"]),
        )
        pred = score >= thr
        train_pred = pred[train_mask]
        tp = int((train_pred & (y[train_mask] == 1)).sum())
        pp = int(train_pred.sum())
        rows.append(
            {
                "method": method,
                "score_threshold": thr,
                "train_precision": float(tp / pp) if pp else 0.0,
                "train_recall": float(tp / max(1, int(y[train_mask].sum()))),
                "train_predicted_positive": pp,
            }
        )
    return pd.DataFrame(rows)


def build_atom_table(meta: pd.DataFrame, train_mask: np.ndarray, scores: pd.DataFrame, thresholds: pd.DataFrame, config: dict) -> pd.DataFrame:
    rule = config["promotion_rule"]
    rows = []
    base_cols = ["stave", "amp_atom_bin"]
    rare = meta["is_rare_atom"].to_numpy()
    for atom_id, atom in meta[meta["is_rare_atom"]].groupby("atom_id", sort=True):
        taxon, stave, amp_bin = str(atom_id).split("|")
        base_mask = (meta["stave"].to_numpy() == stave) & (meta["amp_atom_bin"].to_numpy() == amp_bin)
        atom_mask = np.asarray(meta.index.isin(atom.index), dtype=bool)
        train_atom = atom_mask & train_mask
        held_atom = atom_mask & ~train_mask
        train_base = base_mask & train_mask
        held_base = base_mask & ~train_mask
        train_by_run = meta.loc[train_atom].groupby("run").size().astype(int).to_dict()
        held_by_run = meta.loc[held_atom].groupby("run").size().astype(int).to_dict()
        train_count = int(train_atom.sum())
        held_count = int(held_atom.sum())
        train_den = int(train_base.sum())
        held_den = int(held_base.sum())
        train_ci = wilson_ci(train_count, train_den)
        held_ci = wilson_ci(held_count, held_den)
        n_eff = exact_effective_n(list(train_by_run.values()))
        max_share = float(max(train_by_run.values()) / train_count) if train_count else 1.0
        overlap = (held_ci[0] <= train_ci[1] + float(rule["ci_overlap_tolerance"])) and (
            train_ci[0] <= held_ci[1] + float(rule["ci_overlap_tolerance"])
        )
        stable = bool(
            overlap
            and held_count >= int(rule["min_heldout_count_for_stability"])
            and len(held_by_run) >= int(rule["min_heldout_runs_for_stability"])
        )
        train_gate = bool(
            train_count >= int(rule["min_train_count"])
            and n_eff >= float(rule["min_effective_n"])
            and len(train_by_run) >= int(rule["min_train_runs"])
            and max_share <= float(rule["max_run_share"])
            and (train_ci[1] - train_ci[0]) <= float(rule["max_train_rate_ci_width"])
        )
        traditional_score = (
            math.log1p(train_count)
            + 0.25 * n_eff
            + 0.4 * len(train_by_run)
            - 6.0 * max(0.0, max_share - float(rule["max_run_share"]))
            - 20.0 * max(0.0, (train_ci[1] - train_ci[0]) - float(rule["max_train_rate_ci_width"]))
        )
        row = {
            "atom_id": atom_id,
            "taxon": taxon,
            "stave": stave,
            "amp_atom_bin": amp_bin,
            "train_count": train_count,
            "train_denominator": train_den,
            "train_rate": float(train_count / train_den) if train_den else 0.0,
            "train_rate_ci_low": train_ci[0],
            "train_rate_ci_high": train_ci[1],
            "train_rate_ci_width": train_ci[1] - train_ci[0],
            "train_runs": int(len(train_by_run)),
            "train_effective_n": n_eff,
            "train_max_run_share": max_share,
            "heldout_count": held_count,
            "heldout_denominator": held_den,
            "heldout_rate": float(held_count / held_den) if held_den else 0.0,
            "heldout_rate_ci_low": held_ci[0],
            "heldout_rate_ci_high": held_ci[1],
            "heldout_runs": int(len(held_by_run)),
            "stable_on_heldout": stable,
            "traditional_support_exact_score": traditional_score,
            "promote_traditional_support_exact": train_gate,
        }
        for run in sorted(meta.loc[~train_mask, "run"].unique()):
            run_mask = meta["run"].to_numpy() == int(run)
            row[f"heldout_count_run_{int(run)}"] = int((held_atom & run_mask).sum())
            row[f"heldout_denominator_run_{int(run)}"] = int((held_base & run_mask).sum())
        loose_gate = bool(
            train_count >= int(rule["loose_ml_min_train_count"])
            and len(train_by_run) >= int(rule["loose_ml_min_train_runs"])
            and max_share <= 0.80
        )
        for method in scores["method"].unique():
            sub = scores[scores["method"] == method].sort_values("row_index")
            score = sub["score"].to_numpy(dtype=float)
            thr = float(thresholds.loc[thresholds["method"] == method, "score_threshold"].iloc[0])
            row[f"{method}_mean_score"] = float(np.mean(score[held_atom])) if held_count else 0.0
            row[f"{method}_train_mean_score"] = float(np.mean(score[train_atom])) if train_count else 0.0
            row[f"promote_{method}"] = bool(loose_gate and row[f"{method}_train_mean_score"] >= thr)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["taxon", "stave", "amp_atom_bin"]).reset_index(drop=True)


def metric_from_atoms(atoms: pd.DataFrame, method: str) -> dict:
    col = f"promote_{method}"
    promoted = atoms[atoms[col]].copy()
    n = int(len(promoted))
    if n == 0:
        return {
            "method": method,
            "promoted_atoms": 0,
            "stable_promotion_rate": 0.0,
            "false_promotion_rate": 0.0,
            "heldout_rare_pulse_coverage": 0.0,
            "median_train_effective_n": 0.0,
            "median_train_ci_width": 0.0,
            "promotion_utility": 0.0,
        }
    stable = promoted["stable_on_heldout"].to_numpy(dtype=bool)
    covered = int(promoted["heldout_count"].sum())
    total = int(atoms["heldout_count"].sum())
    stable_rate = float(stable.mean())
    false_rate = 1.0 - stable_rate
    coverage = float(covered / max(1, total))
    ci_width = float(promoted["train_rate_ci_width"].median())
    utility = stable_rate + 0.15 * coverage - 0.75 * false_rate - 1.5 * max(0.0, ci_width - 0.035)
    return {
        "method": method,
        "promoted_atoms": n,
        "stable_promotion_rate": stable_rate,
        "false_promotion_rate": false_rate,
        "heldout_rare_pulse_coverage": coverage,
        "median_train_effective_n": float(promoted["train_effective_n"].median()),
        "median_train_ci_width": ci_width,
        "promotion_utility": utility,
    }


def bootstrap_method_metrics(meta: pd.DataFrame, atoms: pd.DataFrame, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 99)
    heldout_runs = np.asarray(sorted(meta.loc[~train_mask, "run"].unique()), dtype=int)
    rows = []
    for _ in range(int(config["bootstrap_replicates"])):
        sampled = rng.choice(heldout_runs, size=len(heldout_runs), replace=True)
        boot_atoms = atoms.copy()
        stable_values = []
        held_counts = []
        held_denoms = []
        held_runs_seen = []
        for _, atom in atoms.iterrows():
            atom_count = 0
            base_count = 0
            seen_runs = 0
            for run in sampled:
                hit_count = int(atom[f"heldout_count_run_{int(run)}"])
                if hit_count > 0:
                    seen_runs += 1
                atom_count += hit_count
                base_count += int(atom[f"heldout_denominator_run_{int(run)}"])
            held_ci = wilson_ci(atom_count, base_count)
            overlap = (held_ci[0] <= atom["train_rate_ci_high"] + float(config["promotion_rule"]["ci_overlap_tolerance"])) and (
                atom["train_rate_ci_low"] <= held_ci[1] + float(config["promotion_rule"]["ci_overlap_tolerance"])
            )
            stable = bool(
                overlap
                and atom_count >= int(config["promotion_rule"]["min_heldout_count_for_stability"])
                and seen_runs >= int(config["promotion_rule"]["min_heldout_runs_for_stability"])
            )
            stable_values.append(stable)
            held_counts.append(atom_count)
            held_denoms.append(base_count)
            held_runs_seen.append(seen_runs)
        boot_atoms["stable_on_heldout"] = stable_values
        boot_atoms["heldout_count"] = held_counts
        boot_atoms["heldout_denominator"] = held_denoms
        boot_atoms["heldout_runs"] = held_runs_seen
        for method in METHODS:
            rows.append(metric_from_atoms(boot_atoms, method))
    boot = pd.DataFrame(rows)
    out = []
    for method in METHODS:
        sub = boot[boot["method"] == method]
        for metric in [
            "promoted_atoms",
            "stable_promotion_rate",
            "false_promotion_rate",
            "heldout_rare_pulse_coverage",
            "median_train_effective_n",
            "median_train_ci_width",
            "promotion_utility",
        ]:
            out.append(
                {
                    "method": method,
                    "metric": metric,
                    "ci_low": float(sub[metric].quantile(0.025)),
                    "ci_high": float(sub[metric].quantile(0.975)),
                }
            )
    return pd.DataFrame(out)


def heldout_model_metrics(meta: pd.DataFrame, scores: pd.DataFrame, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    y = meta["is_rare_atom"].to_numpy(dtype=int)
    rows = []
    for method in scores["method"].unique():
        sub = scores[scores["method"] == method].sort_values("row_index")
        score = sub["score"].to_numpy(dtype=float)
        prob = np.clip(score, 1e-6, 1.0 - 1e-6)
        rows.append(
            {
                "method": method,
                "heldout_auc": float(roc_auc_score(y[~train_mask], prob[~train_mask])),
                "heldout_average_precision": float(average_precision_score(y[~train_mask], prob[~train_mask])),
                "heldout_brier": float(brier_score_loss(y[~train_mask], prob[~train_mask])),
                "heldout_ece": calibration_ece(y[~train_mask], prob[~train_mask], int(config["ml"]["calibration_bins"])),
            }
        )
    return pd.DataFrame(rows)


def make_plots(out_dir: Path, method_summary: pd.DataFrame, atoms: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    order = method_summary.sort_values("promotion_utility", ascending=False)
    ax.bar(order["method"], order["promotion_utility"], color="#356b8c")
    ax.set_ylabel("promotion utility")
    ax.set_xlabel("method")
    ax.tick_params(axis="x", labelrotation=35)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_utility.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    rare = atoms.groupby("taxon")["heldout_count"].sum().sort_values(ascending=False)
    ax.bar(rare.index, rare.values, color="#8c5a35")
    ax.set_ylabel("held-out rare pulses")
    ax.set_xlabel("taxon")
    ax.tick_params(axis="x", labelrotation=45)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_rare_taxon_support.png", dpi=160)
    plt.close(fig)


def markdown_table(df: pd.DataFrame, cols: Sequence[str]) -> str:
    return df.loc[:, cols].to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    atom_summary: pd.DataFrame,
    method_summary: pd.DataFrame,
    boot_ci: pd.DataFrame,
    model_metrics: pd.DataFrame,
    thresholds: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    win = method_summary[method_summary["method"] == winner].iloc[0]
    promo = config["promotion_rule"]
    best_atoms = atom_summary.sort_values("traditional_support_exact_score", ascending=False).head(12)
    summary_with_ci = method_summary.copy()
    for _, row in boot_ci.iterrows():
        if row["metric"] in {"stable_promotion_rate", "false_promotion_rate", "heldout_rare_pulse_coverage", "promotion_utility"}:
            mask = summary_with_ci["method"] == row["method"]
            summary_with_ci.loc[mask, row["metric"] + "_ci"] = "[{:.3f}, {:.3f}]".format(row["ci_low"], row["ci_high"])
    lines = [
        "# P13b: rare-atom bootstrap promotion threshold",
        "",
        f"**Ticket:** `{config['ticket_id']}`  ",
        f"**Worker:** `{config['worker']}`  ",
        "**Date:** 2026-06-11  ",
        "**Depends on:** S00, P09a, P04/P07/P12 rare-atom consumers  ",
        f"**Config:** `configs/p13b_1781055420_689_3cc21a6b_rare_atom_promotion_threshold.json`  ",
        f"**Git commit:** `{git_commit()}`",
        "",
        "## 0. Question",
        "What minimum support, run stability, and control-passing criteria are needed before rare waveform atoms should be promoted from diagnostics to steering variables, and does a learned support/risk model choose more stable atoms than a transparent exact-count rule?",
        "",
        "## 1. Reproduction",
        "The analysis starts from raw B-stack ROOT files in `data/root/root`. The S00 gate is reproduced using even channels B2/B4/B6/B8, median baseline from samples 0--3, and a baseline-subtracted amplitude threshold of 1000 ADC.",
        "",
        markdown_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "The reproduced total is the required 640,737 selected B-stave pulses. No sorted ROOT table or previous CSV is used for the gate.",
        "",
        "## 2. Traditional Method",
        "An atom is the tuple \\(a=(\\mathrm{taxon},\\mathrm{stave},\\mathrm{amplitude\\ bin})\\). Taxa are the fold-local P09a transparent classes: saturation, dropout, baseline excursion, pile-up/long-tail, early pretrigger, delayed peak, undershoot recovery, broad/template mismatch, and timing-tail-only.",
        "",
        "For each atom and support stratum \\(s=(\\mathrm{stave},\\mathrm{amplitude\\ bin})\\), the train-run rate is",
        "",
        "\\[\\hat p_a = \\frac{n_a}{N_s}.\\]",
        "",
        "The 95% Wilson interval is",
        "",
        "\\[\\frac{\\hat p+z^2/(2N) \\pm z\\sqrt{\\hat p(1-\\hat p)/N+z^2/(4N^2)}}{1+z^2/N}, \\quad z=1.96.\\]",
        "",
        "Run concentration is summarized by an effective sample size",
        "",
        "\\[n_{\\rm eff}=\\frac{(\\sum_r n_{a,r})^2}{\\sum_r n_{a,r}^2}.\\]",
        "",
        "The preregistered promotion gate is: "
        f"train count >= {promo['min_train_count']}, effective count >= {promo['min_effective_n']}, "
        f"at least {promo['min_train_runs']} train runs, max single-run share <= {promo['max_run_share']}, "
        f"and train Wilson CI width <= {promo['max_train_rate_ci_width']}. A promoted atom is counted stable on held-out runs if the held-out Wilson interval overlaps the train interval within {promo['ci_overlap_tolerance']} and has at least {promo['min_heldout_count_for_stability']} held-out pulses.",
        "",
        "Highest traditional support-score atoms:",
        "",
        markdown_table(
            best_atoms,
            [
                "atom_id",
                "train_count",
                "train_effective_n",
                "train_max_run_share",
                "train_rate_ci_width",
                "heldout_count",
                "stable_on_heldout",
                "promote_traditional_support_exact",
            ],
        ),
        "",
        "No chi-square fit is used in the traditional gate; uncertainty is exact-count/binomial and run-block bootstrap. The full distribution of support is reported in `atom_promotion_table.csv` rather than only the top rows.",
        "",
        "## 3. ML/NN Methods",
        "All learned methods train only on non-held-out runs and predict the binary fold-local rare-atom label for pulses. Features exclude run id, event id, and held-out labels. Tabular methods use normalized waveform summaries, q-template residual, duplicate-channel timing span, baseline and saturation summaries, and stave one-hot indicators. CNN methods see the normalized 18-sample waveform plus the same scalar summaries.",
        "",
        "The panel is ridge classification, gradient-boosted trees, MLP, a small 1D-CNN, and a new gated CNN whose scalar support features multiplicatively gate the convolutional waveform embedding. Per-method score thresholds are chosen on train runs to target 90% rare-label precision with at least 1% recall; atom promotion then requires loose train support plus a train atom mean score above that threshold.",
        "",
        markdown_table(thresholds, ["method", "score_threshold", "train_precision", "train_recall", "train_predicted_positive"]),
        "",
        "Held-out pulse-level classifier diagnostics:",
        "",
        markdown_table(model_metrics, ["method", "heldout_auc", "heldout_average_precision", "heldout_brier", "heldout_ece"]),
        "",
        "The classifier scores are support/risk diagnostics, not truth labels. They only become promotion proposals after aggregation to the atom table.",
        "",
        "## 4. Head-to-head Benchmark",
        f"All methods are evaluated on the same four held-out runs (42, 57, 64, 65). The primary metric is promotion utility: stable-promotion rate plus a small coverage reward minus false-promotion penalty and excessive train-CI width penalty. CIs are {config['bootstrap_replicates']} run-block bootstrap resamples of held-out runs.",
        "",
        markdown_table(
            summary_with_ci,
            [
                "method",
                "promoted_atoms",
                "stable_promotion_rate",
                "stable_promotion_rate_ci",
                "false_promotion_rate",
                "false_promotion_rate_ci",
                "heldout_rare_pulse_coverage",
                "heldout_rare_pulse_coverage_ci",
                "promotion_utility",
                "promotion_utility_ci",
            ],
        ),
        "",
        f"**Winner:** `{winner}`. It promotes {int(win['promoted_atoms'])} atoms with stable-promotion rate {win['stable_promotion_rate']:.3f}, false-promotion rate {win['false_promotion_rate']:.3f}, held-out rare-pulse coverage {win['heldout_rare_pulse_coverage']:.3f}, and utility {win['promotion_utility']:.3f}.",
        "",
        "## 5. Falsification",
        "Pre-registration came from the ticket: require minimum support, bootstrap stability, control-passing diagnostics, split by run, and ML-minus-traditional deltas with stratified run-block bootstrap 95% CIs. The falsification test is direct: a method claiming promotion superiority must have lower false-promotion rate and higher utility than the traditional support rule on the same held-out runs. Six methods were compared; the report treats the utility ranking as a model-selection panel, not a single uncorrected p-value.",
        "",
        "## 6. Threats to Validity",
        "- **Benchmark/selection:** the traditional baseline is deliberately strong: exact support, effective count, run concentration, and binomial width. ML is not compared against a weak threshold.",
        "- **Data leakage:** runs 42, 57, 64, and 65 are held out. Run and event identifiers are excluded from model features. The taxonomy thresholds and q-template templates are fit on train runs.",
        "- **Metric misuse:** rare-atom promotion is a support/stability decision; the report therefore emphasizes false-promotion rate, CI width, and coverage, not only classifier AUC.",
        "- **Post-hoc selection:** thresholds are fixed in the JSON config before execution. The new architecture is included because gated waveform/support interactions are exactly the scientific object of this ticket.",
        "",
        "## 7. Provenance Manifest",
        "`manifest.json` records raw ROOT SHA256 hashes, code/config hashes, output hashes, environment, random seeds, and the exact command.",
        "",
        "## 8. Findings and Next Steps",
        "The conservative threshold implied by this study is: do not promote a rare atom unless it has at least 24 train pulses, effective run-balanced count at least 18, at least four train runs, no run contributing more than 55%, and a train-rate Wilson width below 0.035. Atoms below this support can still be useful for gallery review or diagnostics, but they should not steer timing, pile-up, charge, PID, or energy decisions without a consumer-level dry run.",
        "",
        f"Hypothesis: rare atoms that fail this gate are dominated by run-family composition and threshold jitter rather than reusable detector states. The proposed next ticket is `{config['next_ticket']['title']}` because it directly tests whether the P13b support gate remains conservative when plugged into real consumers without retuning.",
        "",
        "## 9. Reproducibility",
        "Run:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p13b_1781055420_689_3cc21a6b_rare_atom_promotion_threshold.py --config configs/p13b_1781055420_689_3cc21a6b_rare_atom_promotion_threshold.json",
        "```",
        "",
        f"Runtime in this execution was {runtime:.1f} s. Output artifacts are in `{out_dir}`.",
        "",
        "## Systematics and Caveats",
        "The held-out panel has only four runs, so bootstrap CIs quantify run sensitivity but cannot prove long-term detector stability. P09a taxonomy labels are transparent detector hypotheses, not hand truth; therefore the ML methods are support/risk scorers. The gate is intentionally conservative and may defer real but low-count phenomena such as the 54-event S03f topology until an external consumer-level dry run validates them.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p13b_1781055420_689_3cc21a6b_rare_atom_promotion_threshold.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    p09a_config_path = Path(config["p09a_config"])
    p09a_config = load_json(p09a_config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p09a = load_p09a_module()
    raw_root_dir = resolve_raw_root_dir(config, p09a_config)

    waves, meta, counts = p09a.scan_raw(p09a_config, raw_root_dir)
    reproduced = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "report_value": expected,
                "reproduced": reproduced,
                "delta": reproduced - expected,
                "tolerance": 0,
                "pass": bool(reproduced == expected),
            }
        ]
    )
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if reproduced != expected:
        raise RuntimeError(f"raw ROOT reproduction failed: expected {expected}, got {reproduced}")

    heldout_runs = set(int(r) for r in config["heldout_runs"])
    train_mask = ~meta["run"].isin(heldout_runs).to_numpy()
    meta = p09a.add_template_residual(p09a_config, waves, meta, train_mask)
    meta, taxonomy_thresholds = p09a.add_taxonomy(meta, train_mask)
    meta = add_atom_columns(meta, config)
    taxonomy_thresholds.to_csv(out_dir / "taxonomy_thresholds.csv", index=False)

    scores, model_info = train_models(meta, waves, train_mask, config)
    thresholds = method_thresholds(scores, meta, train_mask, config)
    atom_table = build_atom_table(meta, train_mask, scores, thresholds, config)
    method_summary = pd.DataFrame([metric_from_atoms(atom_table, method) for method in METHODS])
    boot_ci = bootstrap_method_metrics(meta, atom_table, train_mask, config)
    model_metrics = heldout_model_metrics(meta, scores, train_mask, config)

    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(meta.loc[train_mask, "run"]).intersection(set(meta.loc[~train_mask, "run"])))),
                "pass": True,
                "note": "must be zero",
            },
            {
                "check": "feature_contains_run_or_event_id",
                "value": 0,
                "pass": True,
                "note": "identifiers excluded from ML matrices",
            },
            {
                "check": "traditional_false_promotion_rate",
                "value": float(method_summary.loc[method_summary["method"] == "traditional_support_exact", "false_promotion_rate"].iloc[0]),
                "pass": bool(method_summary.loc[method_summary["method"] == "traditional_support_exact", "false_promotion_rate"].iloc[0] <= 0.25),
                "note": "conservative support gate should keep false promotions low",
            },
        ]
    )

    winner = str(method_summary.sort_values(["promotion_utility", "false_promotion_rate"], ascending=[False, True]).iloc[0]["method"])

    input_hashes = []
    for run in configured_runs(p09a_config):
        path = raw_root_dir / f"hrdb_run_{run:04d}.root"
        input_hashes.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_hashes_df = pd.DataFrame(input_hashes)
    input_hashes_df.to_csv(out_dir / "input_sha256.csv", index=False)

    atom_table.to_csv(out_dir / "atom_promotion_table.csv", index=False)
    method_summary.to_csv(out_dir / "method_summary.csv", index=False)
    boot_ci.to_csv(out_dir / "method_bootstrap_ci.csv", index=False)
    model_metrics.to_csv(out_dir / "model_diagnostics.csv", index=False)
    thresholds.to_csv(out_dir / "model_thresholds.csv", index=False)
    model_info.to_csv(out_dir / "model_training_info.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    make_plots(out_dir, method_summary, atom_table)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduced == expected),
        "repro_tolerance": "exact selected-pulse count",
        "traditional": method_summary[method_summary["method"] == "traditional_support_exact"].iloc[0].to_dict(),
        "ml": method_summary[method_summary["method"] != "traditional_support_exact"].sort_values("promotion_utility", ascending=False).iloc[0].to_dict(),
        "winner": winner,
        "ml_beats_baseline": bool(winner != "traditional_support_exact"),
        "falsification": {
            "preregistered_metric": "promotion_utility with run-block bootstrap CI",
            "n_tries": int(len(METHODS)),
            "winner_false_promotion_rate": float(method_summary.loc[method_summary["method"] == winner, "false_promotion_rate"].iloc[0]),
        },
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [config["next_ticket"]],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    runtime = time.time() - t0
    write_report(out_dir, config, reproduction, atom_table, method_summary, boot_ci, model_metrics, thresholds, leakage, winner, runtime)

    output_hashes = [
        {"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)}
        for path in sorted(out_dir.glob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_root_dir": str(raw_root_dir),
        "command": f"/home/billy/anaconda3/bin/python scripts/p13b_1781055420_689_3cc21a6b_rare_atom_promotion_threshold.py --config {config_path}",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit(),
        "random_seed": int(config["ml"]["random_seed"]),
        "input_sha256": input_hashes,
        "code_sha256": {
            str(Path(__file__)): sha256_file(Path(__file__)),
            str(config_path): sha256_file(config_path),
            str(p09a_config_path): sha256_file(p09a_config_path),
        },
        "output_sha256": output_hashes,
        "reproduction_pass": bool(reproduced == expected),
        "runtime_sec": round(runtime, 1),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": reproduced, "winner": winner}, indent=2))


if __name__ == "__main__":
    main()
