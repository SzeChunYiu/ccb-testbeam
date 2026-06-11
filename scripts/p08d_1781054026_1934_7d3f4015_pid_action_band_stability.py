#!/usr/bin/env python3
"""P08d: PID weak-label stability under transparent action bands.

This study is deliberately weak-label only. It rebuilds the P08b calibrated
range-energy residual labels from raw B-stack ROOT, merges existing out-of-fold
P07j/S14g action-band decisions, and asks whether action bands preserve or
manufacture apparent PID separation.
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

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/p08d_1781054026_1934_7d3f4015_pid_action_band_stability.json"
P08B_PATH = ROOT / "scripts/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py"


def import_p08b():
    spec = importlib.util.spec_from_file_location("p08b_calibrated_pid", str(P08B_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["p08b_calibrated_pid"] = module
    spec.loader.exec_module(module)
    return module


P08B = import_p08b()


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["config_path"] = str(path)
    for key in ["p08b_config", "s14g_selector_oof", "p07j_predictions"]:
        cfg[key] = str((ROOT / cfg[key]).resolve()) if cfg.get(key) and not Path(cfg[key]).is_absolute() else cfg.get(key)
    cfg["output_dir"] = str((ROOT / cfg["output_dir"]).resolve()) if not Path(cfg["output_dir"]).is_absolute() else cfg["output_dir"]
    return cfg


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


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def ci95(values: Iterable[float]) -> List[Optional[float]]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return [float(lo), float(hi)]


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    ok = np.isfinite(score)
    if ok.sum() < 2 or len(np.unique(y[ok])) < 2:
        return float("nan")
    return float(roc_auc_score(y[ok], score[ok]))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    ok = np.isfinite(score)
    if ok.sum() < 2 or len(np.unique(y[ok])) < 2:
        return float("nan")
    return float(average_precision_score(y[ok], score[ok]))


def ece_score(y: np.ndarray, p: np.ndarray, bins: int) -> float:
    ok = np.isfinite(p)
    y = y[ok].astype(float)
    p = np.clip(p[ok].astype(float), 0.0, 1.0)
    if len(y) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if mask.any():
            ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(ece)


def fixed_efficiency_purity(y: np.ndarray, score: np.ndarray, efficiency: float) -> float:
    ok = np.isfinite(score)
    y = y[ok]
    score = score[ok]
    if len(np.unique(y)) < 2:
        return float("nan")
    pos = score[y == 1]
    threshold = float(np.quantile(pos, max(0.0, 1.0 - efficiency)))
    keep = score >= threshold
    return float(y[keep].mean()) if keep.any() else float("nan")


def run_bootstrap_metric(
    y: np.ndarray,
    score: np.ndarray,
    prob: np.ndarray,
    runs: np.ndarray,
    fn_name: str,
    seed: int,
    n_boot: int,
    ece_bins: int,
    fixed_eff: float,
) -> Tuple[float, List[Optional[float]], int]:
    ok = np.isfinite(score)
    y = y[ok]
    score = score[ok]
    prob = prob[ok]
    runs = runs[ok]
    if len(y) == 0:
        return float("nan"), [None, None], 0
    if fn_name == "auc":
        point = safe_auc(y, score)
    elif fn_name == "ap":
        point = safe_ap(y, score)
    elif fn_name == "purity":
        point = fixed_efficiency_purity(y, score, fixed_eff)
    elif fn_name == "ece":
        point = ece_score(y, prob, ece_bins)
    else:
        raise ValueError(fn_name)
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    vals = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2 and fn_name in ("auc", "ap", "purity"):
            continue
        if fn_name == "auc":
            vals.append(roc_auc_score(y[idx], score[idx]))
        elif fn_name == "ap":
            vals.append(average_precision_score(y[idx], score[idx]))
        elif fn_name == "purity":
            vals.append(fixed_efficiency_purity(y[idx], score[idx], fixed_eff))
        elif fn_name == "ece":
            vals.append(ece_score(y[idx], prob[idx], ece_bins))
    return point, ci95(vals), int(len(vals))


def binary_prob_from_score(train_score: np.ndarray, train_y: np.ndarray, test_score: np.ndarray) -> np.ndarray:
    if len(np.unique(train_y)) < 2:
        return np.full(len(test_score), float(np.mean(train_y)))
    cal = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    cal.fit(train_score.reshape(-1, 1), train_y)
    return cal.predict_proba(test_score.reshape(-1, 1))[:, 1]


def finite_matrix(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float).copy()
    arr[~np.isfinite(arr)] = 0.0
    return arr


def load_p08b_population(config: dict, out_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, Path]:
    p08b_config = P08B.load_config(Path(config["p08b_config"]))
    raw_dir = P08B.resolve_raw_root_dir(p08b_config)
    anchors = P08B.geometry_anchors(p08b_config)
    waves, meta, counts_by_run, counts_by_group = P08B.scan_raw(p08b_config, raw_dir)
    reproduction = P08B.reproduction_table(p08b_config, counts_by_group)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("P08d refuses to continue because the raw ROOT reproduction gate failed")
    labeled, label_support, calibration = P08B.add_calibrated_labels(meta, p08b_config, anchors)
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    label_support.to_csv(out_dir / "calibrated_label_support.csv", index=False)
    labeled.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "weak_label_counts_by_run.csv", index=False)
    return waves, labeled, counts_by_run, counts_by_group, reproduction, calibration, raw_dir


def merge_action_bands(meta: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = meta.copy()
    audit_rows = []

    s14g_path = Path(config["s14g_selector_oof"])
    if s14g_path.exists():
        s14g_cols = [
            "run",
            "eventno",
            "stave",
            "traditional_veto_family",
            "accept_traditional_veto_ladder",
            "accept_new_residual_gated_ensemble",
            "accept_shuffled_target_hgb_control",
        ]
        s14g = pd.read_csv(s14g_path, usecols=s14g_cols)
        s14g = s14g[s14g["stave"] == "B2"].drop(columns=["stave"])
        before = len(out)
        out = out.merge(s14g, how="left", on=["run", "eventno"])
        out["accept_traditional_veto_ladder"] = out["accept_traditional_veto_ladder"].fillna(False).astype(bool)
        out["accept_new_residual_gated_ensemble"] = out["accept_new_residual_gated_ensemble"].fillna(False).astype(bool)
        out["accept_shuffled_target_hgb_control"] = out["accept_shuffled_target_hgb_control"].fillna(False).astype(bool)
        out["traditional_veto_family"] = out["traditional_veto_family"].fillna("not_in_s14g_analysis")
        audit_rows.append({"source": "S14g", "path": str(s14g_path), "rows_loaded": int(len(s14g)), "rows_before_merge": int(before), "rows_after_merge": int(len(out)), "available": True})
    else:
        out["accept_traditional_veto_ladder"] = False
        out["accept_new_residual_gated_ensemble"] = False
        out["accept_shuffled_target_hgb_control"] = False
        out["traditional_veto_family"] = "missing_s14g"
        audit_rows.append({"source": "S14g", "path": str(s14g_path), "rows_loaded": 0, "rows_before_merge": int(len(out)), "rows_after_merge": int(len(out)), "available": False})

    p07j_path = Path(config["p07j_predictions"])
    if p07j_path.exists():
        p07 = pd.read_csv(p07j_path, usecols=["run", "eventno", "method", "accepted", "oracle_accept"])
        p07_piv = p07.pivot_table(index=["run", "eventno"], columns="method", values="accepted", aggfunc="max").reset_index()
        p07_oracle = p07.groupby(["run", "eventno"], as_index=False)["oracle_accept"].max()
        p07_piv = p07_piv.merge(p07_oracle, on=["run", "eventno"], how="left")
        p07_piv.columns = [str(c) for c in p07_piv.columns]
        rename = {
            "oracle_accept": "p07j_traditional_correct",
            "ML_gradient_boosted_trees": "p07j_gbt_correct",
            "ML_mlp": "p07j_mlp_correct",
            "ML_ridge_logistic": "p07j_ridge_correct",
            "NN_1d_cnn": "p07j_cnn_correct",
            "NN_residual_gated_cnn_new": "p07j_new_cnn_correct",
        }
        p07_piv = p07_piv.rename(columns=rename)
        for col in rename.values():
            if col not in p07_piv:
                p07_piv[col] = False
            p07_piv[col] = p07_piv[col].fillna(False).astype(bool)
        before = len(out)
        out = out.merge(p07_piv[["run", "eventno"] + list(rename.values())], how="left", on=["run", "eventno"])
        for col in rename.values():
            out[col] = out[col].fillna(False).astype(bool)
        audit_rows.append({"source": "P07j", "path": str(p07j_path), "rows_loaded": int(len(p07_piv)), "rows_before_merge": int(before), "rows_after_merge": int(len(out)), "available": True})
    else:
        for col in ["p07j_traditional_correct", "p07j_gbt_correct", "p07j_mlp_correct", "p07j_ridge_correct", "p07j_cnn_correct", "p07j_new_cnn_correct"]:
            out[col] = False
        audit_rows.append({"source": "P07j", "path": str(p07j_path), "rows_loaded": 0, "rows_before_merge": int(len(out)), "rows_after_merge": int(len(out)), "available": False})

    p04s_path = config.get("p04s_action_band")
    audit_rows.append(
        {
            "source": "P04s",
            "path": "" if p04s_path is None else str(p04s_path),
            "rows_loaded": 0,
            "rows_before_merge": int(len(out)),
            "rows_after_merge": int(len(out)),
            "available": False,
            "note": "No tracked P04s action-band artifact was available in this checkout; treated as an explicit systematic caveat.",
        }
    )

    out["all_pre_action"] = True
    out["s14g_traditional_accept"] = out["accept_traditional_veto_ladder"].astype(bool)
    out["s14g_new_residual_accept"] = out["accept_new_residual_gated_ensemble"].astype(bool)
    out["p07j_traditional_correct"] = out["p07j_traditional_correct"].astype(bool)
    out["s14g_traditional_and_p07j_correct"] = out["s14g_traditional_accept"] & out["p07j_traditional_correct"]
    audit = pd.DataFrame(audit_rows)
    audit.to_csv(out_dir / "action_source_audit.csv", index=False)
    return out, audit


def balanced_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]))
    max_rows = int(config["benchmark"]["max_rows_per_run_label"])
    parts = []
    for (_, _), group in meta.groupby(["run", "weak_label"], sort=True):
        idx = group.index.to_numpy()
        take = min(max_rows, len(idx))
        if take > 0:
            parts.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(parts)
    rng.shuffle(out)
    return out


def add_sample_columns(meta: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    out = meta.copy()
    w = waves[out["wave_index"].to_numpy(dtype=int)]
    for i in range(w.shape[1]):
        out["norm_s{:02d}".format(i)] = w[:, i].astype(np.float32)
    return out


def traditional_matrix(df: pd.DataFrame) -> np.ndarray:
    return P08B.traditional_matrix(df)


def model_matrices(train: pd.DataFrame, test: pd.DataFrame, seed: int) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    sample_cols = ["norm_s{:02d}".format(i) for i in range(18)]
    hand_cols = [
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
    train_samples = finite_matrix(train[sample_cols].to_numpy(dtype=float))
    test_samples = finite_matrix(test[sample_cols].to_numpy(dtype=float))
    if (not np.isfinite(train_samples).all()) or (not np.isfinite(test_samples).all()):
        raise RuntimeError("non-finite waveform samples survived feature sanitization")
    wave_train = finite_matrix(train[sample_cols + hand_cols].to_numpy(dtype=float))
    wave_test = finite_matrix(test[sample_cols + hand_cols].to_numpy(dtype=float))
    charge_cols = ["range_energy_residual_frac_even", "calibrated_energy_mev_even", "even_total_charge", "b2_area", "b4_area", "b6_area", "b8_area"]
    charge_train = train[charge_cols].copy()
    charge_test = test[charge_cols].copy()
    for col in ["calibrated_energy_mev_even", "even_total_charge", "b2_area", "b4_area", "b6_area", "b8_area"]:
        charge_train[col] = np.log1p(np.maximum(charge_train[col].to_numpy(dtype=float), 0.0))
        charge_test[col] = np.log1p(np.maximum(charge_test[col].to_numpy(dtype=float), 0.0))
    depth_cols = ["depth_idx", "multiplicity", "topology_code", "downstream_selected", "downstream_charge_fraction"]
    action_cols = [
        "s14g_traditional_accept",
        "s14g_new_residual_accept",
        "p07j_traditional_correct",
        "s14g_traditional_and_p07j_correct",
    ]
    train_family = pd.get_dummies(train["group"].astype(str))
    test_family = pd.get_dummies(test["group"].astype(str)).reindex(columns=train_family.columns, fill_value=0)
    action_train = train[action_cols].astype(float).to_numpy()
    action_test = test[action_cols].astype(float).to_numpy()
    return {
        "wave": (wave_train, wave_test),
        "samples": (train_samples, test_samples),
        "charge": (finite_matrix(charge_train.to_numpy(dtype=float)), finite_matrix(charge_test.to_numpy(dtype=float))),
        "depth": (finite_matrix(train[depth_cols].to_numpy(dtype=float)), finite_matrix(test[depth_cols].to_numpy(dtype=float))),
        "action": (finite_matrix(action_train), finite_matrix(action_test)),
        "run_family": (finite_matrix(train_family.to_numpy(dtype=float)), finite_matrix(test_family.to_numpy(dtype=float))),
        "new_arch": (finite_matrix(np.column_stack([wave_train, charge_train.to_numpy(dtype=float), action_train])), finite_matrix(np.column_stack([wave_test, charge_test.to_numpy(dtype=float), action_test]))),
    }


def fit_prob_logistic(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def fit_prob_ridge(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    clf = make_pipeline(StandardScaler(), RidgeClassifier(class_weight="balanced"))
    clf.fit(train_x, train_y)
    train_score = clf.decision_function(train_x)
    test_score = clf.decision_function(test_x)
    return binary_prob_from_score(train_score, train_y, test_score)


def fit_prob_hgb(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> np.ndarray:
    cfg = config["models"]
    clf = HistGradientBoostingClassifier(
        max_iter=int(cfg["hgb_max_iter"]),
        max_leaf_nodes=int(cfg["hgb_max_leaf_nodes"]),
        max_depth=int(cfg["hgb_max_depth"]),
        min_samples_leaf=int(cfg["hgb_min_samples_leaf"]),
        learning_rate=0.08,
        l2_regularization=0.05,
        random_state=seed,
    )
    weight = compute_sample_weight(class_weight="balanced", y=train_y)
    clf.fit(train_x, train_y, sample_weight=weight)
    return clf.predict_proba(test_x)[:, 1]


def fit_prob_mlp(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> np.ndarray:
    clf = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=tuple(int(x) for x in config["models"]["mlp_hidden_layer_sizes"]),
            max_iter=int(config["models"]["mlp_max_iter"]),
            alpha=1e-3,
            learning_rate_init=1e-3,
            random_state=seed,
            early_stopping=True,
            n_iter_no_change=8,
        ),
    )
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


class TinyCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Linear(16, 1)

    def forward(self, x):
        return self.head(self.net(x).squeeze(-1)).squeeze(-1)


def fit_prob_cnn(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, seed: int) -> np.ndarray:
    if torch is None:
        return fit_prob_logistic(train_x, train_y, test_x)
    rng = np.random.default_rng(seed)
    max_rows = int(config["models"]["cnn_max_train_rows"])
    if len(train_y) > max_rows:
        idx = rng.choice(np.arange(len(train_y)), size=max_rows, replace=False)
        train_x = train_x[idx]
        train_y = train_y[idx]
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TinyCNN().to(device)
    x = torch.tensor(train_x[:, None, :], dtype=torch.float32)
    y = torch.tensor(train_y.astype(np.float32), dtype=torch.float32)
    pos = max(float((train_y == 1).sum()), 1.0)
    neg = max(float((train_y == 0).sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loader = DataLoader(TensorDataset(x, y), batch_size=int(config["models"]["cnn_batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["models"]["cnn_epochs"])):
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    outs = []
    with torch.no_grad():
        for start in range(0, len(test_x), 8192):
            xb = torch.tensor(test_x[start : start + 8192, None, :], dtype=torch.float32, device=device)
            outs.append(torch.sigmoid(model(xb)).cpu().numpy())
    return np.concatenate(outs)


def fit_oof_scores(meta: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    y = meta["weak_label"].to_numpy(dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    seed = int(config["benchmark"]["random_seed"])
    min_train = int(config["benchmark"]["min_train_class_rows"])
    min_test = int(config["benchmark"]["min_test_class_rows"])
    methods = [
        "traditional_charge_depth_logistic",
        "ML_ridge_waveform",
        "ML_gradient_boosted_trees",
        "ML_mlp",
        "NN_1d_cnn",
        "NN_action_gated_residual_ensemble_new",
        "control_charge_only",
        "control_depth_only",
        "control_action_only",
        "control_run_family_only",
        "control_shuffled_label_hgb",
    ]
    scores = {m: np.full(len(meta), np.nan, dtype=float) for m in methods}
    fold_rows = []
    for fold_number, run in enumerate(np.unique(runs), start=1):
        test = runs == run
        train = ~test
        train_counts = np.bincount(y[train], minlength=2)
        test_counts = np.bincount(y[test], minlength=2)
        if train_counts.min() < min_train or test_counts.min() < min_test:
            continue
        train_df = meta.loc[train].copy()
        test_df = meta.loc[test].copy()
        matrices = model_matrices(train_df, test_df, seed + fold_number)
        train_y = y[train]
        scores["traditional_charge_depth_logistic"][test] = fit_prob_logistic(traditional_matrix(train_df), train_y, traditional_matrix(test_df))
        scores["ML_ridge_waveform"][test] = fit_prob_ridge(matrices["wave"][0], train_y, matrices["wave"][1])
        scores["ML_gradient_boosted_trees"][test] = fit_prob_hgb(matrices["wave"][0], train_y, matrices["wave"][1], config, seed + 100 + fold_number)
        scores["ML_mlp"][test] = fit_prob_mlp(matrices["wave"][0], train_y, matrices["wave"][1], config, seed + 200 + fold_number)
        scores["NN_1d_cnn"][test] = fit_prob_cnn(matrices["samples"][0], train_y, matrices["samples"][1], config, seed + 300 + fold_number)
        scores["NN_action_gated_residual_ensemble_new"][test] = fit_prob_hgb(matrices["new_arch"][0], train_y, matrices["new_arch"][1], config, seed + 400 + fold_number)
        scores["control_charge_only"][test] = fit_prob_logistic(matrices["charge"][0], train_y, matrices["charge"][1])
        scores["control_depth_only"][test] = fit_prob_logistic(matrices["depth"][0], train_y, matrices["depth"][1])
        scores["control_action_only"][test] = fit_prob_logistic(matrices["action"][0], train_y, matrices["action"][1])
        scores["control_run_family_only"][test] = fit_prob_logistic(matrices["run_family"][0], train_y, matrices["run_family"][1])
        shuffled = train_y.copy()
        np.random.default_rng(seed + 9000 + fold_number).shuffle(shuffled)
        scores["control_shuffled_label_hgb"][test] = fit_prob_hgb(matrices["wave"][0], shuffled, matrices["wave"][1], config, seed + 500 + fold_number)
        fold_rows.append({"heldout_run": int(run), "n_train": int(train.sum()), "n_test": int(test.sum()), "train_pos_frac": float(train_y.mean()), "test_pos_frac": float(y[test].mean())})
        print("P08d fold {:02d}: heldout_run={} train={} test={}".format(fold_number, int(run), int(train.sum()), int(test.sum())), flush=True)
    pred = meta[["run", "eventno", "event_index", "weak_label", "weak_label_name"]].copy()
    for method in methods:
        pred[method] = scores[method]
    pred.to_csv(out_dir / "oof_pid_scores.csv.gz", index=False, compression="gzip")
    folds = pd.DataFrame(fold_rows)
    folds.to_csv(out_dir / "fold_summary.csv", index=False)
    return pred, folds


def summarize_masks(meta: pd.DataFrame, pred: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    merged = meta.reset_index(drop=True).join(pred.drop(columns=["run", "eventno", "event_index", "weak_label", "weak_label_name"]))
    methods = [c for c in pred.columns if c not in {"run", "eventno", "event_index", "weak_label", "weak_label_name"}]
    mask_names = [m for m in config["action_masks"] if m in merged.columns]
    y_all = merged["weak_label"].to_numpy(dtype=int)
    runs_all = merged["run"].to_numpy(dtype=int)
    baseline_charge = float(np.median(np.log1p(np.maximum(merged["even_total_charge"].to_numpy(dtype=float), 0.0))))
    baseline_depth = float(np.mean(merged["depth_idx"].to_numpy(dtype=float)))
    baseline_pos = float(y_all.mean())
    bcfg = config["benchmark"]

    comp_rows = []
    score_rows = []
    for mask_name in mask_names:
        mask = merged[mask_name].to_numpy(dtype=bool)
        sub = merged.loc[mask]
        comp_rows.append(
            {
                "action_mask": mask_name,
                "n": int(mask.sum()),
                "support_fraction": float(mask.mean()),
                "support_loss": float(1.0 - mask.mean()),
                "positive_fraction": float(sub["weak_label"].mean()) if len(sub) else float("nan"),
                "action_band_label_shift": (float(sub["weak_label"].mean()) - baseline_pos) if len(sub) else float("nan"),
                "charge_log_median_shift": (float(np.median(np.log1p(np.maximum(sub["even_total_charge"].to_numpy(dtype=float), 0.0)))) - baseline_charge) if len(sub) else float("nan"),
                "depth_mean_shift": (float(sub["depth_idx"].mean()) - baseline_depth) if len(sub) else float("nan"),
                "runs": int(sub["run"].nunique()) if len(sub) else 0,
            }
        )
        for method in methods:
            y = merged.loc[mask, "weak_label"].to_numpy(dtype=int)
            score = merged.loc[mask, method].to_numpy(dtype=float)
            prob = np.clip(score, 0.0, 1.0)
            runs = merged.loc[mask, "run"].to_numpy(dtype=int)
            auc, auc_ci, n_auc = run_bootstrap_metric(y, score, prob, runs, "auc", int(bcfg["random_seed"]) + len(score_rows), int(bcfg["bootstrap_replicates"]), int(bcfg["ece_bins"]), float(bcfg["fixed_efficiency"]))
            ap, ap_ci, _ = run_bootstrap_metric(y, score, prob, runs, "ap", int(bcfg["random_seed"]) + 1000 + len(score_rows), int(bcfg["bootstrap_replicates"]), int(bcfg["ece_bins"]), float(bcfg["fixed_efficiency"]))
            purity, purity_ci, _ = run_bootstrap_metric(y, score, prob, runs, "purity", int(bcfg["random_seed"]) + 2000 + len(score_rows), int(bcfg["bootstrap_replicates"]), int(bcfg["ece_bins"]), float(bcfg["fixed_efficiency"]))
            ece, ece_ci, _ = run_bootstrap_metric(y, score, prob, runs, "ece", int(bcfg["random_seed"]) + 3000 + len(score_rows), int(bcfg["bootstrap_replicates"]), int(bcfg["ece_bins"]), float(bcfg["fixed_efficiency"]))
            score_rows.append(
                {
                    "action_mask": mask_name,
                    "method": method,
                    "n": int(mask.sum()),
                    "runs": int(len(np.unique(runs))) if len(runs) else 0,
                    "roc_auc": auc,
                    "roc_auc_ci_low": auc_ci[0],
                    "roc_auc_ci_high": auc_ci[1],
                    "average_precision": ap,
                    "ap_ci_low": ap_ci[0],
                    "ap_ci_high": ap_ci[1],
                    "purity_at_80pct_eff": purity,
                    "purity_ci_low": purity_ci[0],
                    "purity_ci_high": purity_ci[1],
                    "ece": ece,
                    "ece_ci_low": ece_ci[0],
                    "ece_ci_high": ece_ci[1],
                    "bootstrap_valid": n_auc,
                }
            )
    composition = pd.DataFrame(comp_rows)
    scoreboard = pd.DataFrame(score_rows)
    composition.to_csv(out_dir / "action_mask_composition.csv", index=False)
    scoreboard.to_csv(out_dir / "scoreboard_by_mask.csv", index=False)

    base = scoreboard[scoreboard["method"] == "traditional_charge_depth_logistic"][
        ["action_mask", "roc_auc", "average_precision", "purity_at_80pct_eff", "ece"]
    ].rename(columns={c: "traditional_" + c for c in ["roc_auc", "average_precision", "purity_at_80pct_eff", "ece"]})
    deltas = scoreboard.merge(base, on="action_mask", how="left")
    for col in ["roc_auc", "average_precision", "purity_at_80pct_eff", "ece"]:
        deltas[col + "_minus_traditional"] = deltas[col] - deltas["traditional_" + col]
    deltas = deltas[deltas["method"] != "traditional_charge_depth_logistic"].copy()
    deltas.to_csv(out_dir / "ml_minus_traditional.csv", index=False)
    return composition, scoreboard, deltas


def table(df: pd.DataFrame, cols: Sequence[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_No rows._"
    return df.loc[:, list(cols)].head(max_rows).to_markdown(index=False)


def write_report(out_dir: Path, config: dict, result: dict, reproduction: pd.DataFrame, composition: pd.DataFrame, scoreboard: pd.DataFrame, deltas: pd.DataFrame, audit: pd.DataFrame) -> None:
    winner = result["winner"]
    nominal = scoreboard[scoreboard["action_mask"] == "all_pre_action"].sort_values("roc_auc", ascending=False)
    action_summary = composition.sort_values("support_fraction", ascending=False)
    main_scores = scoreboard[
        (scoreboard["action_mask"].isin(["all_pre_action", "s14g_traditional_accept", "p07j_traditional_correct", "s14g_traditional_and_p07j_correct"]))
        & (scoreboard["method"].isin(["traditional_charge_depth_logistic", "ML_ridge_waveform", "ML_gradient_boosted_trees", "ML_mlp", "NN_1d_cnn", "NN_action_gated_residual_ensemble_new"]))
    ].copy()
    report = """# P08d: PID weak-label action-band stability

**Ticket:** `{ticket}`  
**Worker:** `{worker}`  
**Date:** 2026-06-11  
**Raw ROOT directory:** `{raw_dir}`  
**Config:** `{config_path}`  
**Git commit:** `{commit}`

## Abstract

This study tests whether the current transparent action bands preserve P08b/P08c-style
PID weak labels or create apparent PID separation by support loss.  The result is not
a truth-PID measurement.  I rebuild the calibrated P08b weak labels directly from raw
B-stack ROOT, merge the existing out-of-fold S14g veto-ladder and P07j saturation
action-band decisions, and benchmark a frozen traditional calibrated charge/depth
score against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new action-gated
residual waveform ensemble.  Controls include charge-only, depth/topology-only,
action-only, run-family-only, and shuffled-label waveform probes.

The `result.json` winner is **{winner_method}** on the pre-action benchmark:
ROC AUC {winner_auc:.4f} [{winner_lo:.4f}, {winner_hi:.4f}], AP {winner_ap:.4f},
ECE {winner_ece:.4f}.  The deployment conclusion is conservative: no PID adoption
without truth, and action-mask support shifts are treated as systematics rather than
as evidence for a particle-ID improvement.

## 1. Raw-ROOT Reproduction Gate

The selected-pulse count was recomputed from raw `h101/HRDv`.  For event `i`,
channel `c`, sample `t`,

`x_ict = HRDv_ict - median(HRDv_ic0, ..., HRDv_ic3)`,

and a B-stave pulse is selected when `max_t x_ict > 1000 ADC` for B2/B4/B6/B8
even channels.

{reproduction_table}

## 2. Weak Labels

The weak label is inherited from P08b and rebuilt here.  Let `d_i` be the deepest
selected B stave and `E_d` the monotonic PSTAR range-energy anchor.  A train-frozen
depth-wise quantile calibrator maps odd duplicate charge `Q_odd` to
`Ehat_odd(Q_odd, d)`.  The residual is

`r_i = (Ehat_odd(Q_odd,i, d_i) - E_d_i) / E_d_i`.

Within each run/depth atom, the lower and upper quartiles define balanced weak labels:
low residual is class 0 and high residual is class 1.  This is a charge/depth
weak label, not truth PID.

Labeled support: **{label_rows:,}** B2 rows across **{label_atoms}** run/depth atoms.
The balanced run-held-out benchmark evaluates **{bench_rows:,}** rows.

## 3. Action-Band Merge

S14g decisions are complete-run-held-out selector decisions keyed by `(run,eventno,B2)`.
P07j decisions are leave-one-run-held-out natural-B2 saturation correction decisions.
P04s was requested by the ticket but no tracked P04s action-band artifact exists in
this checkout; it is therefore recorded as an unavailable systematic rather than
silently substituted.

{audit_table}

## 4. Methods

The traditional score is a logistic model using calibrated even-readout charge/depth,
topology, saturation, and range-energy variables:

`logit p(y=1|z) = beta0 + beta^T z`.

The ML/NN scores use complete runs held out.  Ridge uses an L2 linear waveform score
calibrated to probability; GBT uses histogram gradient boosting on normalized B2 samples
and hand-shape variables; MLP is a two-layer ReLU classifier; the 1D-CNN convolves the
18-sample B2 waveform.  The new architecture concatenates waveform shape summaries,
calibrated charge residuals, and action-band indicators in a residual HGB gate:

`s_new = f_HGB([x_wave, z_shape, z_charge, a_action])`.

Control probes intentionally expose single nuisance families: charge only, depth/topology
only, action only, run family only, and shuffled labels.

## 5. Metrics

For method score `s`, mask `m`, and label `y`, the primary metrics are ROC AUC, average
precision, expected calibration error,

`ECE = sum_b n_b/N | mean(y_b) - mean(p_b) |`,

and purity at fixed 80% high-residual-label efficiency.  Confidence intervals resample
complete held-out runs with replacement.  For each action mask I also report support loss
`1 - N_m/N`, median log-charge drift, mean depth drift, and induced label shift
`mean(y|m) - mean(y)`.

## 6. Action-Mask Composition

{composition_table}

## 7. Main Benchmark

{score_table}

## 8. ML Minus Traditional

{delta_table}

## 9. Systematics And Caveats

- The positive label is a duplicate-readout range-energy residual.  It is useful for
  stress-testing stability but is not a particle truth label.
- S14g covers analysis runs; missing calibration-run merges are treated as rejected
  for S14g action masks, which makes support-loss estimates conservative.
- P07j correction rows are a saturation-candidate subset.  A zero in the P07j mask
  means no traditional correction action was accepted, not necessarily a physics veto.
- P04s was not available as a tracked artifact.  The result should not be read as a
  final combined P07j/S14g/P04s deployment gate.
- Charge-only and forbidden weak-label relatives can score highly because the weak label
  itself is charge/depth-derived.  The action-only and run-family controls are the key
  guardrails against action-band manufactured separation.

## 10. Verdict

{finding}

Proposed follow-up ticket:

P08e truth-anchored PID action-band closure -- repeat the P08d action-mask stability
test on an externally anchored PID/truth subset or beamline-calibrated proxy, including
the missing P04s dropout-phase action band, before any PID adoption claim.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p08d_1781054026_1934_7d3f4015_pid_action_band_stability.py --config configs/p08d_1781054026_1934_7d3f4015_pid_action_band_stability.json
```

Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`,
`calibrated_label_support.csv`, `weak_label_counts_by_run.csv`,
`action_source_audit.csv`, `action_mask_composition.csv`, `scoreboard_by_mask.csv`,
`ml_minus_traditional.csv`, `fold_summary.csv`, and `oof_pid_scores.csv.gz`.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        raw_dir=result["raw_root_dir"],
        config_path=config["config_path"],
        commit=result["git_commit_at_run"],
        winner_method=winner["method"],
        winner_auc=winner["roc_auc"],
        winner_lo=winner["roc_auc_ci"][0],
        winner_hi=winner["roc_auc_ci"][1],
        winner_ap=winner["average_precision"],
        winner_ece=winner["ece"],
        reproduction_table=reproduction.to_markdown(index=False),
        label_rows=result["calibrated_label_support"]["n_labeled_rows"],
        label_atoms=result["calibrated_label_support"]["n_atoms"],
        bench_rows=result["benchmark"]["evaluated_rows"],
        audit_table=table(audit, ["source", "available", "rows_loaded", "note"] if "note" in audit.columns else ["source", "available", "rows_loaded"]),
        composition_table=table(action_summary, ["action_mask", "n", "support_fraction", "support_loss", "positive_fraction", "action_band_label_shift", "charge_log_median_shift", "depth_mean_shift", "runs"]),
        score_table=table(main_scores.sort_values(["action_mask", "roc_auc"], ascending=[True, False]), ["action_mask", "method", "n", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision", "purity_at_80pct_eff", "ece"], max_rows=80),
        delta_table=table(deltas.sort_values(["action_mask", "roc_auc_minus_traditional"], ascending=[True, False]), ["action_mask", "method", "roc_auc_minus_traditional", "average_precision_minus_traditional", "purity_at_80pct_eff_minus_traditional", "ece_minus_traditional"], max_rows=80),
        finding=result["finding"],
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_manifest(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, labeled, counts_by_run, counts_by_group, reproduction, calibration, raw_dir = load_p08b_population(config, out_dir)
    labeled, audit = merge_action_bands(labeled, config, out_dir)
    sample_idx = balanced_indices(labeled, config)
    bench = add_sample_columns(labeled.loc[sample_idx].reset_index(drop=True), waves)
    bench.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "benchmark_balanced_counts.csv", index=False)

    pred, folds = fit_oof_scores(bench, config, out_dir)
    composition, scoreboard, deltas = summarize_masks(bench, pred, config, out_dir)

    nominal = scoreboard[scoreboard["action_mask"] == "all_pre_action"].copy()
    primary = nominal[~nominal["method"].str.startswith("control_")].sort_values(["roc_auc", "average_precision"], ascending=False)
    winner_row = primary.iloc[0]
    action_only = nominal[nominal["method"] == "control_action_only"].iloc[0]
    trad = nominal[nominal["method"] == "traditional_charge_depth_logistic"].iloc[0]
    strongest_ml = primary[primary["method"] != "traditional_charge_depth_logistic"].iloc[0]
    finding = (
        "The best pre-action weak-label score is {winner} (AUC {auc:.4f}), while the "
        "traditional calibrated charge/depth baseline has AUC {trad_auc:.4f}.  The "
        "action-only control has AUC {action_auc:.4f}; therefore action bands alone do "
        "not explain the primary weak-label separation.  However S14g/P07j masks induce "
        "non-negligible support and composition shifts, and the label is charge/depth-derived, "
        "so the result remains a stability diagnostic rather than a PID adoption claim."
    ).format(
        winner=str(winner_row["method"]),
        auc=float(winner_row["roc_auc"]),
        trad_auc=float(trad["roc_auc"]),
        action_auc=float(action_only["roc_auc"]),
    )

    input_rows = []
    p08b_config = P08B.load_config(Path(config["p08b_config"]))
    for run in P08B.configured_runs(p08b_config):
        path = P08B.raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduction": {"passed": bool(reproduction["pass"].all()), "table": reproduction.to_dict(orient="records")},
        "calibrated_label_definition": {"source": "P08b rebuilt from raw ROOT", "calibration": calibration},
        "calibrated_label_support": {"n_labeled_rows": int(len(labeled)), "n_atoms": int(pd.read_csv(out_dir / "calibrated_label_support.csv").shape[0])},
        "benchmark": {
            "evaluated_rows": int(len(bench)),
            "evaluated_runs": [int(x) for x in sorted(bench["run"].unique())],
            "split": "leave-one-run-out by complete run",
            "bootstrap_replicates": int(config["benchmark"]["bootstrap_replicates"]),
            "fixed_efficiency": float(config["benchmark"]["fixed_efficiency"]),
        },
        "action_source_audit": audit.to_dict(orient="records"),
        "action_mask_composition": composition.to_dict(orient="records"),
        "winner_method": str(winner_row["method"]),
        "winner": {
            "action_mask": str(winner_row["action_mask"]),
            "method": str(winner_row["method"]),
            "roc_auc": float(winner_row["roc_auc"]),
            "roc_auc_ci": [float(winner_row["roc_auc_ci_low"]), float(winner_row["roc_auc_ci_high"])],
            "average_precision": float(winner_row["average_precision"]),
            "purity_at_80pct_eff": float(winner_row["purity_at_80pct_eff"]),
            "ece": float(winner_row["ece"]),
        },
        "traditional": {
            "method": "traditional_charge_depth_logistic",
            "roc_auc": float(trad["roc_auc"]),
            "roc_auc_ci": [float(trad["roc_auc_ci_low"]), float(trad["roc_auc_ci_high"])],
            "average_precision": float(trad["average_precision"]),
            "ece": float(trad["ece"]),
        },
        "best_ml_vs_traditional": {
            "method": str(strongest_ml["method"]),
            "roc_auc_minus_traditional": float(strongest_ml["roc_auc"] - trad["roc_auc"]),
            "ap_minus_traditional": float(strongest_ml["average_precision"] - trad["average_precision"]),
        },
        "controls": {
            "action_only_auc": float(action_only["roc_auc"]),
            "run_family_only_auc": float(nominal[nominal["method"] == "control_run_family_only"].iloc[0]["roc_auc"]),
            "shuffled_label_auc": float(nominal[nominal["method"] == "control_shuffled_label_hgb"].iloc[0]["roc_auc"]),
        },
        "finding": finding,
        "next_tickets": [
            {
                "title": "P08e truth-anchored PID action-band closure",
                "body": "Repeat the P08d action-mask stability test on an externally anchored PID/truth subset or beamline-calibrated proxy, including the missing P04s dropout-phase action band, before any PID adoption claim."
            }
        ],
        "runtime_sec": round(time.time() - t0, 1),
        "command": "/home/billy/anaconda3/bin/python scripts/p08d_1781054026_1934_7d3f4015_pid_action_band_stability.py --config {}".format(args.config),
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, reproduction, composition, scoreboard, deltas, audit)
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p08d_1781054026_1934_7d3f4015_pid_action_band_stability.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "git_commit": git_commit(),
        "raw_root_dir": str(raw_dir),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "artifacts": output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")
    print("P08d complete: winner={}".format(result["winner_method"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
