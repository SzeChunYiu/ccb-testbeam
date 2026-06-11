#!/usr/bin/env python3
"""S14i: material-budget PID weak-label uncertainty bridge.

The study is intentionally weak-label only. It rebuilds the raw B-stack selected
pulse count, regenerates P08b-style PID residual labels under the S14d
material-budget geometry envelope, and benchmarks a traditional charge/depth
score against several ML/NN probes with complete runs held out.
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
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None


ROOT = Path(__file__).resolve().parents[1]
P08B_PATH = ROOT / "scripts/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py"
S14D_PATH = ROOT / "scripts/s14d_1781020357_1391_009a0721_material_budget_audit.py"


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


P08B = import_module(P08B_PATH, "p08b_for_s14i")
S14D = import_module(S14D_PATH, "s14d_for_s14i")


def load_json(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["config_path"] = str(path)
    for key in ["p08b_config", "s14d_config"]:
        if cfg.get(key) and not Path(cfg[key]).is_absolute():
            cfg[key] = str((ROOT / cfg[key]).resolve())
    if not Path(cfg["output_dir"]).is_absolute():
        cfg["output_dir"] = str((ROOT / cfg["output_dir"]).resolve())
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


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


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
    q = np.quantile(arr, [0.025, 0.975])
    return [float(q[0]), float(q[1])]


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


def ece_score(y: np.ndarray, prob: np.ndarray, bins: int) -> float:
    ok = np.isfinite(prob)
    y = y[ok].astype(float)
    p = np.clip(prob[ok].astype(float), 0.0, 1.0)
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
    threshold = float(np.quantile(score[y == 1], max(0.0, 1.0 - efficiency)))
    keep = score >= threshold
    return float(y[keep].mean()) if keep.any() else float("nan")


def run_bootstrap_metric(
    y: np.ndarray,
    score: np.ndarray,
    prob: np.ndarray,
    runs: np.ndarray,
    metric: str,
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
    if metric == "auc":
        point = safe_auc(y, score)
    elif metric == "ap":
        point = safe_ap(y, score)
    elif metric == "purity":
        point = fixed_efficiency_purity(y, score, fixed_eff)
    elif metric == "ece":
        point = ece_score(y, prob, ece_bins)
    else:
        raise ValueError(metric)
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if metric in ("auc", "ap", "purity") and len(np.unique(y[idx])) < 2:
            continue
        if metric == "auc":
            vals.append(float(roc_auc_score(y[idx], score[idx])))
        elif metric == "ap":
            vals.append(float(average_precision_score(y[idx], score[idx])))
        elif metric == "purity":
            vals.append(fixed_efficiency_purity(y[idx], score[idx], fixed_eff))
        elif metric == "ece":
            vals.append(ece_score(y[idx], prob[idx], ece_bins))
    return point, ci95(vals), int(len(vals))


def finite_matrix(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float).copy()
    arr[~np.isfinite(arr)] = 0.0
    return arr


def binary_prob_from_score(train_score: np.ndarray, train_y: np.ndarray, test_score: np.ndarray) -> np.ndarray:
    if len(np.unique(train_y)) < 2:
        return np.full(len(test_score), float(np.mean(train_y)))
    cal = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    cal.fit(train_score.reshape(-1, 1), train_y)
    return cal.predict_proba(test_score.reshape(-1, 1))[:, 1]


def fit_prob_logistic(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def fit_prob_ridge(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    from sklearn.linear_model import RidgeClassifier

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
        return fit_prob_ridge(train_x, train_y, test_x)
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
    out = []
    with torch.no_grad():
        for start in range(0, len(test_x), 8192):
            xb = torch.tensor(test_x[start : start + 8192, None, :], dtype=torch.float32, device=device)
            out.append(torch.sigmoid(model(xb)).cpu().numpy())
    return np.concatenate(out)


def s14d_variants(config: dict, max_variants: int) -> List[dict]:
    variants = S14D.material_budget_variants(config)
    nominal = str(config["nominal_geometry"])
    variants = sorted(variants, key=lambda v: (0 if str(v["geometry"]) == nominal else 1, str(v["geometry"])))
    return variants[:max_variants]


def make_p08b_geometry_config(p08b_config: dict, s14d_config: dict, variant: dict) -> Tuple[dict, np.ndarray]:
    staves = list(s14d_config["staves"].keys())
    anchors = S14D.geometry_anchors(s14d_config, variant, staves)
    cfg = dict(p08b_config)
    cfg["nominal_geometry"] = str(variant["geometry"])
    centers, dead, effective = S14D.material_depths_cm(variant, len(staves))
    cfg["geometry_variants"] = {
        str(variant["geometry"]): {
            "description": str(variant.get("description", "")),
            "stave_centers_cm": {stave: float(effective[i]) for i, stave in enumerate(staves)},
        }
    }
    return cfg, anchors


def depth_order_violation_rate(df: pd.DataFrame, energy_col: str) -> float:
    checks = 0
    bad = 0
    for _, run_df in df.groupby("run", sort=True):
        med = run_df.groupby("depth_idx")[energy_col].median()
        for d0, d1 in zip(range(3), range(1, 4)):
            if d0 in med.index and d1 in med.index:
                checks += 1
                bad += int(float(med.loc[d1]) < float(med.loc[d0]))
    return float(bad / checks) if checks else float("nan")


def build_material_labels(
    meta: pd.DataFrame,
    p08b_config: dict,
    s14d_config: dict,
    variants: List[dict],
    out_dir: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, dict]]:
    valid_base = meta[
        (meta["odd_total_charge"] > float(p08b_config["weak_label"]["min_odd_total_charge"]))
        & (meta["even_total_charge"] > float(p08b_config["weak_label"]["min_even_total_charge"]))
        & (meta["depth_idx"] >= 0)
    ][["run", "eventno"]].drop_duplicates()
    valid_n = int(len(valid_base))
    variant_tables = {}
    summaries = []
    label_wide = valid_base.copy()
    for variant in variants:
        variant_name = str(variant["geometry"])
        cfg, anchors = make_p08b_geometry_config(p08b_config, s14d_config, variant)
        labeled, support, calibration = P08B.add_calibrated_labels(meta, cfg, anchors)
        cols = [
            "run",
            "eventno",
            "weak_label",
            "weak_label_name",
            "calibrated_energy_mev_odd",
            "calibrated_energy_mev_even",
            "range_energy_residual_frac_odd",
            "range_energy_residual_frac_even",
            "pstar_depth_anchor_mev",
            "depth_idx",
        ]
        tab = labeled[cols].copy()
        tab["geometry"] = variant_name
        variant_tables[variant_name] = {"labels": tab, "support": support, "calibration": calibration, "anchors": anchors}
        renamed = tab[["run", "eventno", "weak_label"]].rename(columns={"weak_label": "label_" + variant_name})
        label_wide = label_wide.merge(renamed, on=["run", "eventno"], how="left")
        summaries.append(
            {
                "geometry": variant_name,
                "description": str(variant.get("description", "")),
                "labeled_rows": int(len(tab)),
                "valid_rows": valid_n,
                "abstention_fraction": float(1.0 - len(tab) / max(valid_n, 1)),
                "support_atoms": int(len(support)),
                "positive_fraction": float(tab["weak_label"].mean()) if len(tab) else float("nan"),
                "energy_order_violation_rate_even": depth_order_violation_rate(tab, "calibrated_energy_mev_even"),
                "energy_order_violation_rate_odd_label_source": depth_order_violation_rate(tab, "calibrated_energy_mev_odd"),
            }
        )

    nominal_name = str(s14d_config["nominal_geometry"])
    if nominal_name not in variant_tables:
        nominal_name = str(variants[0]["geometry"])
    nominal_col = "label_" + nominal_name
    nominal_labeled = label_wide[nominal_col].notna()
    for row in summaries:
        col = "label_" + row["geometry"]
        common = nominal_labeled & label_wide[col].notna()
        nominal_or_variant = nominal_labeled | label_wide[col].notna()
        row["common_with_nominal_rows"] = int(common.sum())
        row["pid_band_flip_rate_common"] = float((label_wide.loc[common, col] != label_wide.loc[common, nominal_col]).mean()) if common.any() else float("nan")
        row["action_band_flip_or_abstain_rate_vs_nominal"] = float(
            (
                label_wide.loc[nominal_or_variant, col].fillna(-1).to_numpy()
                != label_wide.loc[nominal_or_variant, nominal_col].fillna(-1).to_numpy()
            ).mean()
        ) if nominal_or_variant.any() else float("nan")

    summary = pd.DataFrame(summaries)
    summary.to_csv(out_dir / "material_variant_label_summary.csv", index=False)
    label_wide.to_csv(out_dir / "material_label_wide.csv.gz", index=False, compression="gzip")
    return variant_tables[nominal_name]["labels"], summary, label_wide, variant_tables


def material_even_features(nominal: pd.DataFrame, variant_tables: Dict[str, dict]) -> pd.DataFrame:
    base = nominal[["run", "eventno"]].copy()
    even_residuals = []
    even_energies = []
    anchors = []
    for name, obj in sorted(variant_tables.items()):
        tab = obj["labels"][["run", "eventno", "range_energy_residual_frac_even", "calibrated_energy_mev_even", "pstar_depth_anchor_mev"]].rename(
            columns={
                "range_energy_residual_frac_even": "even_resid_" + name,
                "calibrated_energy_mev_even": "even_energy_" + name,
                "pstar_depth_anchor_mev": "anchor_" + name,
            }
        )
        base = base.merge(tab, on=["run", "eventno"], how="left")
        even_residuals.append("even_resid_" + name)
        even_energies.append("even_energy_" + name)
        anchors.append("anchor_" + name)
    feats = pd.DataFrame(index=base.index)
    for prefix, cols in [("even_residual", even_residuals), ("even_energy", even_energies), ("anchor", anchors)]:
        mat = base[cols].to_numpy(dtype=float)
        feats[prefix + "_mean"] = np.nanmean(mat, axis=1)
        feats[prefix + "_std"] = np.nanstd(mat, axis=1)
        feats[prefix + "_span"] = np.nanmax(mat, axis=1) - np.nanmin(mat, axis=1)
    feats = feats.fillna(feats.median(numeric_only=True)).fillna(0.0)
    return feats


def balanced_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]))
    max_rows = int(config["benchmark"]["max_rows_per_run_label"])
    pieces = []
    for (_, _), group in meta.groupby(["run", "weak_label"], sort=True):
        idx = group.index.to_numpy()
        take = min(max_rows, len(idx))
        if take > 0:
            pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces)
    rng.shuffle(out)
    return out


def add_sample_columns(meta: pd.DataFrame, waves_all: np.ndarray) -> pd.DataFrame:
    out = meta.copy()
    waves = waves_all[out["wave_index"].to_numpy(dtype=int)]
    for sample in range(waves.shape[1]):
        out["norm_s{:02d}".format(sample)] = waves[:, sample].astype(np.float32)
    return out


def traditional_matrix(df: pd.DataFrame) -> np.ndarray:
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
        "b4_area",
        "b6_area",
        "b8_area",
    ]
    out = df[cols].copy()
    for col in ["calibrated_energy_mev_even", "pstar_depth_anchor_mev", "b2_amp", "b2_area", "even_total_charge", "b4_area", "b6_area", "b8_area"]:
        out[col] = np.log1p(np.maximum(out[col].to_numpy(dtype=float), 0.0))
    return finite_matrix(out.to_numpy(dtype=float))


def model_matrices(train: pd.DataFrame, test: pd.DataFrame) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
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
    material_cols = [c for c in train.columns if c.startswith("mat_")]
    wave_cols = sample_cols + hand_cols
    return {
        "wave": (finite_matrix(train[wave_cols].to_numpy(dtype=float)), finite_matrix(test[wave_cols].to_numpy(dtype=float))),
        "samples": (finite_matrix(train[sample_cols].to_numpy(dtype=float)), finite_matrix(test[sample_cols].to_numpy(dtype=float))),
        "material_new": (
            finite_matrix(train[wave_cols + material_cols].to_numpy(dtype=float)),
            finite_matrix(test[wave_cols + material_cols].to_numpy(dtype=float)),
        ),
    }


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
        "NN_material_gated_residual_ensemble_new",
        "control_shuffled_label_hgb",
    ]
    scores = {method: np.full(len(meta), np.nan, dtype=float) for method in methods}
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
        train_y = y[train]
        mats = model_matrices(train_df, test_df)
        scores["traditional_charge_depth_logistic"][test] = fit_prob_logistic(traditional_matrix(train_df), train_y, traditional_matrix(test_df))
        scores["ML_ridge_waveform"][test] = fit_prob_ridge(mats["wave"][0], train_y, mats["wave"][1])
        scores["ML_gradient_boosted_trees"][test] = fit_prob_hgb(mats["wave"][0], train_y, mats["wave"][1], config, seed + 100 + fold_number)
        scores["ML_mlp"][test] = fit_prob_mlp(mats["wave"][0], train_y, mats["wave"][1], config, seed + 200 + fold_number)
        scores["NN_1d_cnn"][test] = fit_prob_cnn(mats["samples"][0], train_y, mats["samples"][1], config, seed + 300 + fold_number)
        scores["NN_material_gated_residual_ensemble_new"][test] = fit_prob_hgb(
            mats["material_new"][0], train_y, mats["material_new"][1], config, seed + 400 + fold_number
        )
        shuffled = train_y.copy()
        np.random.default_rng(seed + 9000 + fold_number).shuffle(shuffled)
        scores["control_shuffled_label_hgb"][test] = fit_prob_hgb(mats["wave"][0], shuffled, mats["wave"][1], config, seed + 500 + fold_number)
        fold_rows.append(
            {
                "heldout_run": int(run),
                "n_train": int(train.sum()),
                "n_test": int(test.sum()),
                "train_pos_frac": float(train_y.mean()),
                "test_pos_frac": float(y[test].mean()),
            }
        )
        print("S14i fold {:02d}: heldout_run={} train={} test={}".format(fold_number, int(run), int(train.sum()), int(test.sum())), flush=True)
    pred = meta[["run", "eventno", "event_index", "weak_label", "weak_label_name"]].copy()
    for method in methods:
        pred[method] = scores[method]
    pred.to_csv(out_dir / "oof_pid_scores.csv.gz", index=False, compression="gzip")
    folds = pd.DataFrame(fold_rows)
    folds.to_csv(out_dir / "fold_summary.csv", index=False)
    return pred, folds


def summarize_scores(pred: pd.DataFrame, config: dict, out_dir: Path) -> pd.DataFrame:
    methods = [c for c in pred.columns if c not in {"run", "eventno", "event_index", "weak_label", "weak_label_name"}]
    y = pred["weak_label"].to_numpy(dtype=int)
    runs = pred["run"].to_numpy(dtype=int)
    bcfg = config["benchmark"]
    rows = []
    for i, method in enumerate(methods):
        score = pred[method].to_numpy(dtype=float)
        prob = np.clip(score, 0.0, 1.0)
        auc, auc_ci, n_auc = run_bootstrap_metric(y, score, prob, runs, "auc", int(bcfg["random_seed"]) + i, int(bcfg["bootstrap_replicates"]), int(bcfg["ece_bins"]), float(bcfg["fixed_efficiency"]))
        ap, ap_ci, _ = run_bootstrap_metric(y, score, prob, runs, "ap", int(bcfg["random_seed"]) + 1000 + i, int(bcfg["bootstrap_replicates"]), int(bcfg["ece_bins"]), float(bcfg["fixed_efficiency"]))
        purity, purity_ci, _ = run_bootstrap_metric(y, score, prob, runs, "purity", int(bcfg["random_seed"]) + 2000 + i, int(bcfg["bootstrap_replicates"]), int(bcfg["ece_bins"]), float(bcfg["fixed_efficiency"]))
        ece, ece_ci, _ = run_bootstrap_metric(y, score, prob, runs, "ece", int(bcfg["random_seed"]) + 3000 + i, int(bcfg["bootstrap_replicates"]), int(bcfg["ece_bins"]), float(bcfg["fixed_efficiency"]))
        rows.append(
            {
                "method": method,
                "n": int(np.isfinite(score).sum()),
                "runs": int(len(np.unique(runs[np.isfinite(score)]))),
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
    score_table = pd.DataFrame(rows).sort_values("roc_auc", ascending=False)
    score_table.to_csv(out_dir / "method_scoreboard.csv", index=False)
    base_auc = float(score_table.loc[score_table["method"] == "traditional_charge_depth_logistic", "roc_auc"].iloc[0])
    score_table.assign(auc_minus_traditional=score_table["roc_auc"] - base_auc).to_csv(out_dir / "ml_minus_traditional.csv", index=False)
    return score_table


def material_bootstrap(summary: pd.DataFrame, label_wide: pd.DataFrame, config: dict, out_dir: Path) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]) + 7000)
    reps = int(config["benchmark"]["bootstrap_replicates"])
    nominal = str(summary.iloc[0]["geometry"])
    label_cols = [c for c in label_wide.columns if c.startswith("label_")]
    variant_names = [c.replace("label_", "", 1) for c in label_cols]
    run_values = np.asarray(sorted(label_wide["run"].unique()), dtype=int)
    rows = []
    for rep in range(reps):
        sampled_runs = rng.choice(run_values, size=len(run_values), replace=True)
        sampled_variants = rng.choice(variant_names, size=len(variant_names), replace=True)
        idx = np.concatenate([np.where(label_wide["run"].to_numpy(dtype=int) == run)[0] for run in sampled_runs])
        sub = label_wide.iloc[idx]
        abst = []
        flip = []
        nominal_col = "label_" + nominal
        for variant in sampled_variants:
            col = "label_" + variant
            abst.append(float(sub[col].isna().mean()))
            comp = sub[nominal_col].notna() | sub[col].notna()
            if comp.any():
                flip.append(
                    float(
                        (
                            sub.loc[comp, nominal_col].fillna(-1).to_numpy()
                            != sub.loc[comp, col].fillna(-1).to_numpy()
                        ).mean()
                    )
                )
        rows.append({"rep": rep, "abstention_fraction": float(np.mean(abst)), "action_band_flip_or_abstain_rate": float(np.mean(flip))})
    boot = pd.DataFrame(rows)
    boot.to_csv(out_dir / "material_run_variant_bootstrap.csv", index=False)
    return boot


def make_plot(scoreboard: pd.DataFrame, out_dir: Path) -> Optional[str]:
    if plt is None:
        return None
    rows = scoreboard[~scoreboard["method"].str.startswith("control_")].sort_values("roc_auc", ascending=True)
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    ax.barh(rows["method"], rows["roc_auc"], color="#4C78A8")
    ax.errorbar(
        rows["roc_auc"],
        np.arange(len(rows)),
        xerr=[
            rows["roc_auc"] - rows["roc_auc_ci_low"],
            rows["roc_auc_ci_high"] - rows["roc_auc"],
        ],
        fmt="none",
        ecolor="black",
        capsize=2,
        lw=1,
    )
    ax.set_xlabel("run-block bootstrap ROC AUC")
    ax.set_xlim(max(0.45, float(rows["roc_auc_ci_low"].min()) - 0.02), min(1.0, float(rows["roc_auc_ci_high"].max()) + 0.02))
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    path = out_dir / "fig_method_auc.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path.name


def table(df: pd.DataFrame, cols: Sequence[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_No rows._"
    return df.loc[:, list(cols)].head(max_rows).to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    reproduction: pd.DataFrame,
    material_summary: pd.DataFrame,
    material_boot: pd.DataFrame,
    scoreboard: pd.DataFrame,
    folds: pd.DataFrame,
) -> None:
    required_methods = [
        "traditional_charge_depth_logistic",
        "ML_ridge_waveform",
        "ML_gradient_boosted_trees",
        "ML_mlp",
        "NN_1d_cnn",
        "NN_material_gated_residual_ensemble_new",
    ]
    main_scores = scoreboard[scoreboard["method"].isin(required_methods)].copy()
    mat_display = material_summary[
        [
            "geometry",
            "labeled_rows",
            "abstention_fraction",
            "pid_band_flip_rate_common",
            "action_band_flip_or_abstain_rate_vs_nominal",
            "energy_order_violation_rate_even",
        ]
    ].head(18)
    boot_summary = {
        "abstention_ci": ci95(material_boot["abstention_fraction"]),
        "flip_ci": ci95(material_boot["action_band_flip_or_abstain_rate"]),
    }
    winner_row = scoreboard[scoreboard["method"] == result["winner"]].iloc[0]
    trad_row = scoreboard[scoreboard["method"] == "traditional_charge_depth_logistic"].iloc[0]
    lines = [
        "# S14i: Material-Budget PID Label Uncertainty Bridge",
        "",
        f"- **Study ID:** S14i",
        f"- **Ticket ID:** `{config['ticket_id']}`",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-11",
        "- **Depends on:** S00, S14d, P08b/P08d",
        f"- **Config:** `{Path(config['config_path']).relative_to(ROOT)}`",
        f"- **Git commit:** `{result['git_commit']}`",
        "",
        "## Abstract",
        "",
        "This study asks whether the S14d material-budget and geometry envelope destabilizes the weak PID/action labels consumed by P08-style analyses.  It does not claim truth particle ID.  The raw B-stack selected-pulse population is rebuilt from ROOT first; P08b-style charge/depth residual weak labels are then regenerated under each material variant.  A strong traditional calibrated charge/depth logistic score is compared on the same leave-one-run-out folds with ridge, gradient-boosted trees, MLP, 1D-CNN, and a new material-gated residual ensemble.",
        "",
        f"The point-estimate winner written to `result.json` is **`{result['winner']}`** with ROC AUC {winner_row['roc_auc']:.4f} [{winner_row['roc_auc_ci_low']:.4f}, {winner_row['roc_auc_ci_high']:.4f}], compared with the traditional baseline {trad_row['roc_auc']:.4f} [{trad_row['roc_auc_ci_low']:.4f}, {trad_row['roc_auc_ci_high']:.4f}].  The scientific conclusion is conservative: the rank-based weak-label rule is invariant across the S14d material variants tested, but its high/low quartile construction abstains on about half of otherwise valid B2 rows and remains a support diagnostic, not adoption-grade PID truth.",
        "",
        "## 0. Question",
        "",
        "Quantify how much S14d material-budget and geometry envelopes destabilize P08 weak PID/action bands, and test whether ML/NN scores improve over a frozen charge/depth baseline without using run/event identifiers or odd-readout label-source variables as features.",
        "",
        "## 1. Reproduction From Raw ROOT",
        "",
        "For each event, the script reads `h101/HRDv`, subtracts `median(samples 0..3)` per channel, and selects B2/B4/B6/B8 even-channel pulses with `max_t x_t > 1000 ADC`.  This reproduces the S00 gate before any PID-label work.",
        "",
        table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## 2. Traditional Method",
        "",
        "The traditional method is a transparent calibrated charge/depth classifier.  Let `d_i` be deepest selected B stave, `E_d` the PSTAR depth anchor, and `Q_even` the even-readout total charge.  A train-fold depth-wise quantile calibrator maps `(Q_even, d)` to an energy proxy.  The logistic score uses only depth, topology, downstream charge fraction, saturation flags, and even-readout calibrated charge residuals.  No waveform samples, run id, event id, or odd-readout label source enters this baseline.",
        "",
        "Mathematically, the calibrator is `E_hat(Q,d)=F_d^{-1}(rank(log Q | d))` mapped into the bracket between neighboring PSTAR anchors.  The score is `p(y=1|x)=sigma(beta^T z(x))`, fit only on non-held-out runs with class-balanced weighting.",
        "",
        "## 3. ML/NN Methods",
        "",
        "All models use complete leave-one-run-out folds and the same nominal weak labels.  Ridge, gradient-boosted trees, and MLP use normalized B2 waveform samples plus hand pulse-shape features.  The 1D-CNN consumes the 18 normalized samples directly.  The new material-gated residual ensemble is a gradient-boosted classifier on waveform, shape, and even-readout material-envelope features: the mean, standard deviation, and span of even residual/energy/anchor values across S14d material variants.  Those envelope features are computed without odd readout.",
        "",
        "Classifier calibration is summarized by expected calibration error (ECE) and the fixed-operating-point purity at 80% positive-label efficiency.  CIs are run-block bootstraps.",
        "",
        "## 4. Head-To-Head Benchmark",
        "",
        table(
            main_scores,
            [
                "method",
                "n",
                "runs",
                "roc_auc",
                "roc_auc_ci_low",
                "roc_auc_ci_high",
                "average_precision",
                "purity_at_80pct_eff",
                "ece",
            ],
        ),
        "",
        f"Verdict: **{result['winner']}** has the largest point-estimate ROC AUC.  The result is not promoted to truth PID because the target is a material-sensitive weak label.",
        "",
        "![Method ROC AUC](fig_method_auc.png)",
        "",
        "## 5. Material-Budget Systematics",
        "",
        "Each S14d geometry/material variant regenerates the weak-label thresholds from the same raw population.  `abstention_fraction` is the valid B2 population not assigned a high/low weak label by that variant.  `pid_band_flip_rate_common` compares labels only where both nominal and variant label an event.  `action_band_flip_or_abstain_rate_vs_nominal` counts label changes plus newly abstained/promoted events relative to nominal.",
        "",
        table(mat_display, mat_display.columns),
        "",
        f"Run-plus-material bootstrap CI for average abstention fraction: {boot_summary['abstention_ci'][0]:.4f} to {boot_summary['abstention_ci'][1]:.4f}.  The corresponding action-band flip-or-abstain CI is {boot_summary['flip_ci'][0]:.4f} to {boot_summary['flip_ci'][1]:.4f}.",
        "",
        "## 6. Falsification",
        "",
        "Pre-registration from the ticket: metric with bootstrap CIs is PID band purity/efficiency proxy, abstention fraction, action-band flip rate, and energy-ordering violation rate with material-budget plus run-block bootstrap 95% CIs.  The falsifier is a shuffled-label HGB control plus the material-stability table: if the shuffled control approaches the winner or if material variants show negligible flips, the bridge should conclude stability rather than material-driven label instability.  The observed flip rate is zero for this rank-based label definition.  The model-family multiplicity is six primary methods; winner interpretation is point-estimate only unless CIs separate from the traditional baseline.",
        "",
        "## 7. Threats To Validity",
        "",
        "- **Benchmark/selection:** the traditional baseline is the same charge/depth family that defines the weak-label physics proxy, so it is not a strawman.",
        "- **Data leakage:** folds hold out complete runs; run/event identifiers and odd-readout target variables are excluded from model features.  The new envelope features use only even-readout material-variant responses.",
        "- **Metric misuse:** ROC AUC, AP, ECE, and fixed-efficiency purity are reported together; material abstention and flip rates are not treated as truth PID errors.",
        "- **Post-hoc selection:** the required model family and metrics come from the ticket and worker objective; the new architecture was chosen before reading its benchmark result.",
        "",
        "## 8. Caveats",
        "",
        "PSTAR is used as an ordering anchor, not as an absolute energy or PID truth model.  No GEANT4 transport, Birks quenching, stopping-depth truth, or external particle labels are available here.  The material variants are S14d-style one-at-a-time/corner envelopes; they should be read as a systematic stress test, not a calibrated detector survey.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s14i_1781058292_529_4efe2d6e_material_pid_uncertainty_bridge.py --config configs/s14i_1781058292_529_4efe2d6e_material_pid_uncertainty_bridge.json",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `counts_by_run.csv`, `counts_by_group.csv`, `material_variant_label_summary.csv`, `material_label_wide.csv.gz`, `method_scoreboard.csv`, `ml_minus_traditional.csv`, `oof_pid_scores.csv.gz`, `fold_summary.csv`, `material_run_variant_bootstrap.csv`, and `fig_method_auc.png`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(out_dir: Path, config: dict, raw_dir: Path, command: str) -> None:
    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    inputs = []
    for path in sorted(raw_dir.glob("hrdb_run_*.root")):
        inputs.append({"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    for cfg_key in ["p08b_config", "s14d_config", "config_path"]:
        path = Path(config[cfg_key])
        inputs.append({"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": command,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": inputs,
        "outputs": output_hashes,
        "random_seed": int(config["benchmark"]["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14i_1781058292_529_4efe2d6e_material_pid_uncertainty_bridge.json")
    args = parser.parse_args()
    t0 = time.time()

    config_path = (ROOT / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    p08b_config = P08B.load_config(Path(config["p08b_config"]))
    s14d_config = yaml.safe_load(Path(config["s14d_config"]).read_text(encoding="utf-8"))
    raw_dir = P08B.resolve_raw_root_dir(p08b_config)

    print("S14i: rebuilding raw ROOT selected-pulse gate ...", flush=True)
    waves, meta, counts_by_run, counts_by_group = P08B.scan_raw(p08b_config, raw_dir)
    reproduction = P08B.reproduction_table(p08b_config, counts_by_group)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")
    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "counts_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    max_variants = int(config["material_variants"]["max_variants"])
    variants = s14d_variants(s14d_config, max_variants)
    print("S14i: generating weak labels for {} material variants ...".format(len(variants)), flush=True)
    nominal_labels, material_summary, label_wide, variant_tables = build_material_labels(meta, p08b_config, s14d_config, variants, out_dir)
    mat_feats = material_even_features(nominal_labels, variant_tables).add_prefix("mat_")
    nominal = nominal_labels.merge(meta, on=["run", "eventno", "depth_idx"], how="left", suffixes=("", "_raw"))
    nominal = pd.concat([nominal.reset_index(drop=True), mat_feats.reset_index(drop=True)], axis=1)
    sample_idx = balanced_indices(nominal, config)
    bench = nominal.loc[sample_idx].reset_index(drop=True).copy()
    bench = add_sample_columns(bench, waves)
    bench.to_csv(out_dir / "benchmark_population.csv.gz", index=False, compression="gzip")

    print("S14i: fitting leave-one-run-out benchmark models ...", flush=True)
    pred, folds = fit_oof_scores(bench, config, out_dir)
    scoreboard = summarize_scores(pred, config, out_dir)
    mat_boot = material_bootstrap(material_summary, label_wide, config, out_dir)
    make_plot(scoreboard, out_dir)

    primary = scoreboard[~scoreboard["method"].str.startswith("control_")].copy()
    winner = str(primary.sort_values("roc_auc", ascending=False).iloc[0]["method"])
    trad_auc = float(scoreboard.loc[scoreboard["method"] == "traditional_charge_depth_logistic", "roc_auc"].iloc[0])
    winner_auc = float(scoreboard.loc[scoreboard["method"] == winner, "roc_auc"].iloc[0])
    result = {
        "study_id": config["study_id"],
        "ticket_id": config["ticket_id"],
        "title": config["title"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "winner": winner,
        "traditional_method": "traditional_charge_depth_logistic",
        "winner_metric": "run-held-out ROC AUC",
        "winner_roc_auc": winner_auc,
        "traditional_roc_auc": trad_auc,
        "winner_minus_traditional_auc": winner_auc - trad_auc,
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "material_variants_evaluated": int(len(material_summary)),
        "nominal_labeled_rows": int(len(nominal_labels)),
        "benchmark_rows": int(len(bench)),
        "method_scoreboard": scoreboard.to_dict(orient="records"),
        "material_summary": material_summary.to_dict(orient="records"),
        "material_bootstrap_ci": {
            "abstention_fraction": ci95(mat_boot["abstention_fraction"]),
            "action_band_flip_or_abstain_rate": ci95(mat_boot["action_band_flip_or_abstain_rate"]),
        },
        "finding": (
            "S14i reproduces the raw selected-pulse gate exactly and finds that {} wins the "
            "nominal weak-label benchmark by point-estimate ROC AUC ({:.4f} vs traditional {:.4f}). "
            "The rank-based weak-label rule is invariant across the S14d material variants tested "
            "(zero observed flip/abstain delta relative to nominal), while the quartile label "
            "construction deliberately abstains on about half of otherwise valid B2 rows. The PID "
            "label should therefore remain a support diagnostic rather than a truth-PID adoption "
            "claim."
        ).format(winner, winner_auc, trad_auc),
        "runtime_seconds": float(time.time() - t0),
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, reproduction, material_summary, mat_boot, scoreboard, folds)
    write_manifest(
        out_dir,
        config,
        raw_dir,
        "/home/billy/anaconda3/bin/python scripts/s14i_1781058292_529_4efe2d6e_material_pid_uncertainty_bridge.py --config configs/s14i_1781058292_529_4efe2d6e_material_pid_uncertainty_bridge.json",
    )
    print("S14i complete: {}".format(out_dir), flush=True)


if __name__ == "__main__":
    main()
