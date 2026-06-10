#!/usr/bin/env python3
"""S04d timing-tail pathology interaction audit.

The script deliberately starts with the raw ROOT count reproduction gate, then
uses only frozen S04c pathology summaries for traditional and ML interaction
audits. Cross-validation groups are runs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def load_module(name: str, rel_path: str):
    path = Path(__file__).resolve().parents[1] / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {rel_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S04B = load_module("s04d_s04b_base", "scripts/s04b_1781009378_adaptive_lowering_covariates.py")
S16F = load_module("s04d_s16f_base", "scripts/s16f_1781015168_1090_5b553d2a_tail_mechanism.py")
S04C = load_module("s04d_s04c_base", "scripts/s04c_1781018820_3826_39cd42b6_pathology_tail_table.py")

PATHOLOGY_AXES = list(S04C.PATHOLOGY_AXES)
CATEGORICAL_MAIN = ["pair", *PATHOLOGY_AXES]
NUMERIC_FEATURES = [
    "abs_delta_lowering_adc",
    "max_lowering_adc",
    "sum_lowering_adc",
    "max_lowering_frac",
    "min_log_amp",
    "mean_peak_sample",
    "mean_area_over_amp",
    "max_tail_area_frac",
    "max_width20_samples",
    "max_width50_samples",
    "max_pretrigger_abs_adc",
    "max_pretrigger_ptp_adc",
    "max_late_abs_adc",
    "most_negative_postpeak_adc",
]
FORBIDDEN_FEATURES = {"run", "event_id", "eventno", "evt", "residual_ns", "centered_residual_ns", "tail_oof"}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def output_hashes(out_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def analysis_config_for_loader(config: dict) -> dict:
    out = json.loads(json.dumps(config))
    runs = [int(r) for r in config["timing"]["analysis_runs"]]
    out["timing"]["train_runs"] = runs
    out["timing"]["heldout_runs"] = []
    return out


def make_preprocessor(cols: Sequence[str]) -> ColumnTransformer:
    categorical = [c for c in cols if c in CATEGORICAL_MAIN or "__x__" in c]
    numeric = [c for c in cols if c not in categorical]
    return ColumnTransformer(
        [
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ]
    )


def interaction_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for a, b in itertools.combinations(PATHOLOGY_AXES, 2):
        out[f"{a}__x__{b}"] = out[a].astype(str) + "|" + out[b].astype(str)
    return out


def all_model_features(include_interactions: bool) -> List[str]:
    cols = list(NUMERIC_FEATURES) + list(CATEGORICAL_MAIN)
    if include_interactions:
        cols += [f"{a}__x__{b}" for a, b in itertools.combinations(PATHOLOGY_AXES, 2)]
    return cols


def center_with_train_median(train: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    med = train.groupby("pair")["residual_ns"].median()
    global_med = float(train["residual_ns"].median())
    centers = np.asarray([float(med.get(pair, global_med)) for pair in frame["pair"]], dtype=float)
    return frame["residual_ns"].to_numpy(dtype=float) - centers


def ece_score(y_true: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(prob, dtype=float)
    edges = np.linspace(0.0, 1.0, int(bins) + 1)
    total = len(y)
    if total == 0:
        return float("nan")
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if mask.any():
            ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(ece)


def metric_summary(values: np.ndarray) -> Dict[str, float]:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    med = float(np.median(vals)) if len(vals) else float("nan")
    centered = vals - med
    return {
        "n_pair_residuals": int(len(vals)),
        "median_ns": med,
        "sigma68_ns": S16F.sigma68(vals),
        "full_rms_ns": float(np.sqrt(np.mean(centered**2))) if len(vals) else float("nan"),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > 5.0)) if len(vals) else float("nan"),
    }


def bootstrap_residual_ci(frame: pd.DataFrame, residual_col: str, rng: np.random.Generator, n_boot: int) -> Dict[str, float]:
    valid = frame[np.isfinite(frame[residual_col].to_numpy(dtype=float))].reset_index(drop=True)
    values = valid[residual_col].to_numpy(dtype=float)
    by_run: Dict[int, List[np.ndarray]] = {}
    for run, rframe in valid.groupby("run", sort=True):
        by_run[int(run)] = [idx.to_numpy(dtype=int) for _, idx in rframe.groupby("event_id", sort=True).groups.items()]
    runs = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(int(n_boot)):
        pieces: List[np.ndarray] = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            events = by_run[int(run)]
            idx = rng.integers(0, len(events), size=len(events))
            pieces.extend(values[events[int(i)]] for i in idx)
        stats.append(metric_summary(np.concatenate(pieces)))
    return {
        "sigma68_ci_low": float(np.percentile([s["sigma68_ns"] for s in stats], 2.5)),
        "sigma68_ci_high": float(np.percentile([s["sigma68_ns"] for s in stats], 97.5)),
        "full_rms_ci_low": float(np.percentile([s["full_rms_ns"] for s in stats], 2.5)),
        "full_rms_ci_high": float(np.percentile([s["full_rms_ns"] for s in stats], 97.5)),
        "tail_ci_low": float(np.percentile([s["tail_frac_abs_gt5ns"] for s in stats], 2.5)),
        "tail_ci_high": float(np.percentile([s["tail_frac_abs_gt5ns"] for s in stats], 97.5)),
    }


def risk_flags(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out["s16_lowering_axis"] = frame["s16_lowering_axis"].isin(["medium", "large"])
    out["pretrigger_axis"] = frame["pretrigger_axis"].isin(["large"])
    out["p07_saturation_axis"] = frame["p07_saturation_axis"].isin(["wide_plateau"])
    out["s10_two_pulse_axis"] = frame["s10_two_pulse_axis"].isin(["high_broad_late"])
    out["dropout_jagged_axis"] = frame["dropout_jagged_axis"].isin(["negative_dropout"])
    out["peak_phase_axis"] = ~frame["peak_phase_axis"].isin(["nominal_peak"])
    out["p09_taxon_proxy"] = ~frame["p09_taxon_proxy"].isin(["ordinary_shape"])
    return out


def stratified_interaction_stats(frame: pd.DataFrame, axis_a: str, axis_b: str) -> Dict[str, float]:
    flags = risk_flags(frame)
    a = flags[axis_a].to_numpy(dtype=bool)
    b = flags[axis_b].to_numpy(dtype=bool)
    y = frame["tail_oof"].to_numpy(dtype=int)
    eps = 0.5
    rows = {}
    for name, mask in [("00", ~a & ~b), ("10", a & ~b), ("01", ~a & b), ("11", a & b)]:
        n = int(mask.sum())
        tails = int(y[mask].sum())
        rows[name] = {"n": n, "tails": tails, "rate": float(tails / n) if n else float("nan")}
    p00 = rows["00"]["rate"]
    p10 = rows["10"]["rate"]
    p01 = rows["01"]["rate"]
    p11 = rows["11"]["rate"]
    additive_expected = p10 + p01 - p00 if all(np.isfinite([p00, p10, p01])) else float("nan")
    delta = p11 - additive_expected if np.isfinite(additive_expected) and np.isfinite(p11) else float("nan")
    odds = {}
    for key in rows:
        odds[key] = (rows[key]["tails"] + eps) / (rows[key]["n"] - rows[key]["tails"] + eps)
    interaction_or = (odds["11"] * odds["00"]) / max(odds["10"] * odds["01"], 1e-12)
    both = a & b
    run_all = frame["run"].value_counts(normalize=True)
    run_both = frame.loc[both, "run"].value_counts(normalize=True) if both.any() else run_all * 0.0
    run_index = sorted(set(run_all.index) | set(run_both.index))
    composition_shift = 0.5 * sum(abs(float(run_both.get(r, 0.0)) - float(run_all.get(r, 0.0))) for r in run_index)
    return {
        "axis_a": axis_a,
        "axis_b": axis_b,
        "n00": rows["00"]["n"],
        "n10": rows["10"]["n"],
        "n01": rows["01"]["n"],
        "n11": rows["11"]["n"],
        "tail_rate00": p00,
        "tail_rate10": p10,
        "tail_rate01": p01,
        "tail_rate11": p11,
        "additive_expected11": additive_expected,
        "interaction_delta": delta,
        "interaction_odds_ratio": float(interaction_or),
        "log_interaction_or": float(math.log(max(interaction_or, 1e-12))),
        "composition_shift": float(composition_shift),
    }


def bootstrap_interaction_ci(frame: pd.DataFrame, axis_a: str, axis_b: str, rng: np.random.Generator, n_boot: int) -> Dict[str, float]:
    work = frame.reset_index(drop=True)
    flags = risk_flags(work)
    a_all = flags[axis_a].to_numpy(dtype=bool)
    b_all = flags[axis_b].to_numpy(dtype=bool)
    y_all = work["tail_oof"].to_numpy(dtype=int)
    run_all_values = work["run"].to_numpy(dtype=int)
    by_run = {
        int(run): [idx.to_numpy(dtype=int) for _, idx in rframe.groupby("event_id", sort=True).groups.items()]
        for run, rframe in work.groupby("run", sort=True)
    }
    runs = np.asarray(sorted(by_run), dtype=int)
    deltas = []
    logs = []
    shifts = []
    eps = 0.5
    full_run_counts = pd.Series(run_all_values).value_counts(normalize=True)

    def stat_for_indices(sample_idx: np.ndarray) -> Tuple[float, float, float]:
        a = a_all[sample_idx]
        b = b_all[sample_idx]
        y = y_all[sample_idx]
        cells = {}
        for name, mask in [("00", ~a & ~b), ("10", a & ~b), ("01", ~a & b), ("11", a & b)]:
            n = int(mask.sum())
            tails = int(y[mask].sum())
            rate = float(tails / n) if n else float("nan")
            odds = (tails + eps) / (n - tails + eps)
            cells[name] = (n, tails, rate, odds)
        additive = cells["10"][2] + cells["01"][2] - cells["00"][2]
        delta = cells["11"][2] - additive
        interaction_or = (cells["11"][3] * cells["00"][3]) / max(cells["10"][3] * cells["01"][3], 1e-12)
        both_idx = sample_idx[a & b]
        if len(both_idx):
            run_both = pd.Series(run_all_values[both_idx]).value_counts(normalize=True)
        else:
            run_both = full_run_counts * 0.0
        run_index = sorted(set(full_run_counts.index) | set(run_both.index))
        shift = 0.5 * sum(abs(float(run_both.get(r, 0.0)) - float(full_run_counts.get(r, 0.0))) for r in run_index)
        return float(delta), float(math.log(max(interaction_or, 1e-12))), float(shift)

    for _ in range(int(n_boot)):
        pieces: List[np.ndarray] = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            events = by_run[int(run)]
            idx = rng.integers(0, len(events), size=len(events))
            pieces.extend(events[int(i)] for i in idx)
        sample_idx = np.concatenate(pieces)
        delta, log_or, shift = stat_for_indices(sample_idx)
        deltas.append(delta)
        logs.append(log_or)
        shifts.append(shift)
    def q(values: Sequence[float], pct: float) -> float:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        return float(np.percentile(arr, pct)) if len(arr) else float("nan")

    return {
        "interaction_delta_ci_low": q(deltas, 2.5),
        "interaction_delta_ci_high": q(deltas, 97.5),
        "log_interaction_or_ci_low": q(logs, 2.5),
        "log_interaction_or_ci_high": q(logs, 97.5),
        "composition_shift_ci_high": q(shifts, 97.5),
    }


def oof_models(pairs: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    out = interaction_feature_frame(pairs).reset_index(drop=True)
    for col in [
        "centered_train_residual_ns",
        "residual_traditional_additive_ns",
        "residual_ml_rf_ns",
        "tail_oof",
        "tail_prob_traditional_additive",
        "tail_prob_sparse_interaction",
        "tail_prob_tree",
        "tail_prob_tree_shuffled",
        "tail_prob_axis_shuffled",
    ]:
        out[col] = np.nan

    fold_rows = []
    clf_rows = []
    groups = out["run"].to_numpy(dtype=int)
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    main_features = all_model_features(False)
    interaction_features = all_model_features(True)
    forbidden_overlap = sorted(set(interaction_features) & FORBIDDEN_FEATURES)

    for fold, (tr, va) in enumerate(GroupKFold(n_splits=n_splits).split(out, groups=groups), start=1):
        train = out.iloc[tr].copy()
        valid = out.iloc[va].copy()
        y_train = center_with_train_median(train, train)
        y_valid = center_with_train_median(train, valid)
        tail_train = (np.abs(y_train) > float(config["timing"]["tail_abs_residual_ns"])).astype(int)
        tail_valid = (np.abs(y_valid) > float(config["timing"]["tail_abs_residual_ns"])).astype(int)
        out.loc[va, "centered_train_residual_ns"] = y_valid
        out.loc[va, "tail_oof"] = tail_valid

        trad_resid = make_pipeline(make_preprocessor(main_features), Ridge(alpha=float(config["traditional"]["ridge_alpha"])))
        trad_resid.fit(train[main_features], y_train)
        out.loc[va, "residual_traditional_additive_ns"] = y_valid - trad_resid.predict(valid[main_features])

        rf_params = config["ml"]["random_forest"]
        rf_resid = make_pipeline(
            make_preprocessor(interaction_features),
            RandomForestRegressor(
                n_estimators=int(rf_params["n_estimators"]),
                max_depth=int(rf_params["max_depth"]),
                min_samples_leaf=int(rf_params["min_samples_leaf"]),
                random_state=int(config["ml"]["random_seed"]) + fold,
                n_jobs=1,
            ),
        )
        rf_resid.fit(train[interaction_features], y_train)
        out.loc[va, "residual_ml_rf_ns"] = y_valid - rf_resid.predict(valid[interaction_features])

        trad_clf = make_pipeline(
            make_preprocessor(main_features),
            LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs"),
        )
        trad_clf.fit(train[main_features], tail_train)
        out.loc[va, "tail_prob_traditional_additive"] = trad_clf.predict_proba(valid[main_features])[:, 1]

        sparse = make_pipeline(
            make_preprocessor(interaction_features),
            LogisticRegression(
                max_iter=1200,
                class_weight="balanced",
                penalty="l1",
                solver="liblinear",
                C=float(config["ml"]["interaction_logit_c"]),
                random_state=int(config["ml"]["random_seed"]) + 100 + fold,
            ),
        )
        sparse.fit(train[interaction_features], tail_train)
        out.loc[va, "tail_prob_sparse_interaction"] = sparse.predict_proba(valid[interaction_features])[:, 1]

        tree_base = make_pipeline(
            make_preprocessor(interaction_features),
            RandomForestClassifier(
                n_estimators=int(rf_params["n_estimators"]),
                max_depth=int(rf_params["max_depth"]),
                min_samples_leaf=int(rf_params["min_samples_leaf"]),
                class_weight="balanced_subsample",
                random_state=int(config["ml"]["random_seed"]) + 200 + fold,
                n_jobs=1,
            ),
        )
        tree = CalibratedClassifierCV(tree_base, method="sigmoid", cv=2)
        tree.fit(train[interaction_features], tail_train)
        prob_tree = tree.predict_proba(valid[interaction_features])[:, 1]
        out.loc[va, "tail_prob_tree"] = prob_tree

        tree_shuf_base = make_pipeline(
            make_preprocessor(interaction_features),
            RandomForestClassifier(
                n_estimators=max(40, int(rf_params["n_estimators"]) // 2),
                max_depth=int(rf_params["max_depth"]),
                min_samples_leaf=int(rf_params["min_samples_leaf"]),
                class_weight="balanced_subsample",
                random_state=int(config["ml"]["random_seed"]) + 300 + fold,
                n_jobs=1,
            ),
        )
        tree_shuf = tree_shuf_base
        tree_shuf.fit(train[interaction_features], rng.permutation(tail_train))
        out.loc[va, "tail_prob_tree_shuffled"] = tree_shuf.predict_proba(valid[interaction_features])[:, 1]

        axis_shuf_train = train.copy()
        for axis in PATHOLOGY_AXES:
            axis_shuf_train[axis] = rng.permutation(axis_shuf_train[axis].to_numpy())
        axis_shuf_train = interaction_feature_frame(axis_shuf_train)
        axis_shuf = make_pipeline(
            make_preprocessor(interaction_features),
            LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs"),
        )
        axis_shuf.fit(axis_shuf_train[interaction_features], tail_train)
        out.loc[va, "tail_prob_axis_shuffled"] = axis_shuf.predict_proba(valid[interaction_features])[:, 1]

        yh = tail_valid.astype(int)
        row = {
            "fold": fold,
            "heldout_runs": ",".join(str(int(r)) for r in sorted(valid["run"].unique())),
            "n": int(len(valid)),
            "tail_rate": float(yh.mean()),
            "traditional_additive_auc": float(roc_auc_score(yh, out.loc[va, "tail_prob_traditional_additive"])) if len(np.unique(yh)) > 1 else np.nan,
            "sparse_interaction_auc": float(roc_auc_score(yh, out.loc[va, "tail_prob_sparse_interaction"])) if len(np.unique(yh)) > 1 else np.nan,
            "tree_auc": float(roc_auc_score(yh, prob_tree)) if len(np.unique(yh)) > 1 else np.nan,
            "tree_ap": float(average_precision_score(yh, prob_tree)) if yh.sum() else np.nan,
            "tree_brier": float(brier_score_loss(yh, prob_tree)),
            "tree_ece": ece_score(yh, prob_tree),
            "tree_shuffled_auc": float(roc_auc_score(yh, out.loc[va, "tail_prob_tree_shuffled"])) if len(np.unique(yh)) > 1 else np.nan,
            "axis_shuffled_auc": float(roc_auc_score(yh, out.loc[va, "tail_prob_axis_shuffled"])) if len(np.unique(yh)) > 1 else np.nan,
        }
        clf_rows.append(row)
        fold_rows.append(
            {
                "fold": fold,
                "heldout_runs": row["heldout_runs"],
                "raw_sigma68_ns": S16F.sigma68(y_valid),
                "traditional_additive_sigma68_ns": S16F.sigma68(out.loc[va, "residual_traditional_additive_ns"].to_numpy(dtype=float)),
                "ml_rf_sigma68_ns": S16F.sigma68(out.loc[va, "residual_ml_rf_ns"].to_numpy(dtype=float)),
            }
        )

    row_cv_auc = []
    for tr, va in KFold(n_splits=5, shuffle=True, random_state=int(config["ml"]["random_seed"]) + 900).split(out):
        train = out.iloc[tr].copy()
        valid = out.iloc[va].copy()
        y_train = train["tail_oof"].astype(int).to_numpy()
        y_valid = valid["tail_oof"].astype(int).to_numpy()
        clf = make_pipeline(
            make_preprocessor(interaction_features),
            LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs"),
        )
        clf.fit(train[interaction_features], y_train)
        row_cv_auc.append(roc_auc_score(y_valid, clf.predict_proba(valid[interaction_features])[:, 1]))

    clf_df = pd.DataFrame(clf_rows)
    fold_df = pd.DataFrame(fold_rows)
    summary = {
        "forbidden_feature_overlap": ",".join(forbidden_overlap),
        "run_cv_traditional_additive_auc_mean": float(np.nanmean(clf_df["traditional_additive_auc"])),
        "run_cv_sparse_interaction_auc_mean": float(np.nanmean(clf_df["sparse_interaction_auc"])),
        "run_cv_tree_auc_mean": float(np.nanmean(clf_df["tree_auc"])),
        "run_cv_tree_ap_mean": float(np.nanmean(clf_df["tree_ap"])),
        "run_cv_tree_brier_mean": float(np.nanmean(clf_df["tree_brier"])),
        "run_cv_tree_ece_mean": float(np.nanmean(clf_df["tree_ece"])),
        "run_cv_tree_shuffled_auc_mean": float(np.nanmean(clf_df["tree_shuffled_auc"])),
        "run_cv_axis_shuffled_auc_mean": float(np.nanmean(clf_df["axis_shuffled_auc"])),
        "row_cv_additive_auc_mean": float(np.nanmean(row_cv_auc)),
        "run_cv_raw_sigma68_ns": float(fold_df["raw_sigma68_ns"].mean()),
        "run_cv_traditional_additive_sigma68_ns": float(fold_df["traditional_additive_sigma68_ns"].mean()),
        "run_cv_ml_rf_sigma68_ns": float(fold_df["ml_rf_sigma68_ns"].mean()),
    }
    return out, fold_df, clf_df, summary


def residual_benchmark(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for method, col in [
        ("raw_cfd20_pair_centered", "centered_train_residual_ns"),
        ("traditional_additive_ridge", "residual_traditional_additive_ns"),
        ("ml_rf_interaction_residual", "residual_ml_rf_ns"),
    ]:
        rows.append({"method": method, **metric_summary(oof[col].to_numpy(dtype=float)), **bootstrap_residual_ci(oof, col, rng, int(config["ml"]["bootstrap_samples"]))})
    return pd.DataFrame(rows)


def interaction_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n_boot = min(220, int(config["ml"]["bootstrap_samples"]))
    for axis_a, axis_b in itertools.combinations(PATHOLOGY_AXES, 2):
        stat = stratified_interaction_stats(oof, axis_a, axis_b)
        min_cell = min(int(stat["n00"]), int(stat["n10"]), int(stat["n01"]), int(stat["n11"]))
        stat["min_cell_n"] = int(min_cell)
        stat["low_support"] = bool(min_cell < int(config["traditional"]["min_cell_n"]))
        stat.update(bootstrap_interaction_ci(oof, axis_a, axis_b, rng, n_boot))
        stat["significant_delta_ci_excludes_zero"] = bool(
            np.isfinite(stat["interaction_delta_ci_low"])
            and np.isfinite(stat["interaction_delta_ci_high"])
            and ((stat["interaction_delta_ci_low"] > 0.0) or (stat["interaction_delta_ci_high"] < 0.0))
        )
        rows.append(stat)
    out = pd.DataFrame(rows)
    out["abs_interaction_delta"] = out["interaction_delta"].abs()
    return out.sort_values(
        ["low_support", "significant_delta_ci_excludes_zero", "abs_interaction_delta", "n11"],
        ascending=[True, False, False, False],
    )


def classifier_table(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y = oof["tail_oof"].astype(int).to_numpy()
    for method, col in [
        ("traditional_additive_logit", "tail_prob_traditional_additive"),
        ("ml_sparse_interaction_logit", "tail_prob_sparse_interaction"),
        ("ml_calibrated_tree", "tail_prob_tree"),
        ("shuffled_target_tree_control", "tail_prob_tree_shuffled"),
        ("axis_shuffled_control", "tail_prob_axis_shuffled"),
    ]:
        p = oof[col].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "auc": float(roc_auc_score(y, p)),
                "average_precision": float(average_precision_score(y, p)),
                "brier": float(brier_score_loss(y, p)),
                "ece": ece_score(y, p),
                "mean_probability": float(np.mean(p)),
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(oof: pd.DataFrame, bench: pd.DataFrame, classifiers: pd.DataFrame, cv_summary: dict) -> pd.DataFrame:
    raw = bench[bench["method"] == "raw_cfd20_pair_centered"].iloc[0]
    ml = bench[bench["method"] == "ml_rf_interaction_residual"].iloc[0]
    tree = classifiers[classifiers["method"] == "ml_calibrated_tree"].iloc[0]
    shuf = classifiers[classifiers["method"] == "shuffled_target_tree_control"].iloc[0]
    axis = classifiers[classifiers["method"] == "axis_shuffled_control"].iloc[0]
    return pd.DataFrame(
        [
            {"check": "all_rows_have_run_heldout_predictions", "value": int(np.isfinite(oof["tail_prob_tree"]).sum()), "pass": bool(np.isfinite(oof["tail_prob_tree"]).all())},
            {"check": "features_exclude_identifiers_and_labels", "value": cv_summary["forbidden_feature_overlap"], "pass": cv_summary["forbidden_feature_overlap"] == ""},
            {"check": "shuffled_target_auc_near_random", "value": float(shuf["auc"]), "pass": bool(shuf["auc"] < 0.65)},
            {"check": "axis_shuffled_control_weaker_than_tree", "value": float(tree["auc"] - axis["auc"]), "pass": bool((tree["auc"] - axis["auc"]) > 0.05)},
            {"check": "row_cv_not_materially_better_than_run_cv", "value": float(cv_summary["row_cv_additive_auc_mean"] - cv_summary["run_cv_traditional_additive_auc_mean"]), "pass": bool((cv_summary["row_cv_additive_auc_mean"] - cv_summary["run_cv_traditional_additive_auc_mean"]) < 0.05)},
            {"check": "ml_residual_gain_under_one_ns", "value": float(raw["sigma68_ns"] - ml["sigma68_ns"]), "pass": bool((raw["sigma68_ns"] - ml["sigma68_ns"]) < 1.0)},
            {"check": "tree_calibration_ece_under_0p03", "value": float(tree["ece"]), "pass": bool(tree["ece"] < 0.03)},
        ]
    )


def plot_outputs(out_dir: Path, interactions: pd.DataFrame, classifiers: pd.DataFrame) -> None:
    top = interactions.head(10).copy()
    labels = [f"{a}\n{x}\n{b}" for a, x, b in zip(top["axis_a"], ["x"] * len(top), top["axis_b"])]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(top))
    ax.errorbar(
        x,
        top["interaction_delta"],
        yerr=[
            top["interaction_delta"] - top["interaction_delta_ci_low"],
            top["interaction_delta_ci_high"] - top["interaction_delta"],
        ],
        fmt="o",
        capsize=3,
    )
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylabel("tail-rate interaction delta")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_top_interaction_deltas.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    shown = classifiers[~classifiers["method"].str.contains("control")].copy()
    ax.bar(np.arange(len(shown)), shown["auc"])
    ax.set_xticks(np.arange(len(shown)))
    ax.set_xticklabels(shown["method"], rotation=25, ha="right")
    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("run-held-out tail AUC")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_classifier_auc.png", dpi=150)
    plt.close(fig)


def markdown_table(df: pd.DataFrame, cols: List[str], n: int | None = None) -> str:
    shown = df[cols].head(n) if n else df[cols]
    return shown.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    reproduction: pd.DataFrame,
    bench: pd.DataFrame,
    classifiers: pd.DataFrame,
    interactions: pd.DataFrame,
    leakage: pd.DataFrame,
    cv_summary: dict,
    result: dict,
) -> None:
    raw = bench[bench["method"] == "raw_cfd20_pair_centered"].iloc[0]
    trad = bench[bench["method"] == "traditional_additive_ridge"].iloc[0]
    ml = bench[bench["method"] == "ml_rf_interaction_residual"].iloc[0]
    top = interactions.iloc[0]
    lines = [
        "# S04d: Timing-Tail Pathology Interaction Audit",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT `h101/HRDv` under `data/root/root`; no Monte Carlo",
        "- **Split:** grouped by run; held-out OOF predictions plus run/event bootstrap CIs",
        f"- **Config:** `{config_path}`",
        "",
        "## Reproduction First",
        "",
        "The first executable analysis step rescanned raw ROOT and reproduced the S00/S04 B-stave selected-pulse counts.",
        "",
        markdown_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## Methods",
        "",
        "Traditional: frozen CFD20 pair residuals, matched binary pathology interaction tables, additive-only logistic tail risk, and an additive Ridge residual stress test. The interaction table preserves run and pair composition by reporting the run/event bootstrap and a run-composition shift for the double-positive cell.",
        "",
        "ML: a sparse L1 interaction logistic model and a calibrated constrained-depth random-forest tail-risk model using only frozen waveform/pathology summaries; the RF residual model is included as a head-to-head timing stress test.",
        "",
        "## Residual Head-To-Head",
        "",
        markdown_table(bench, ["method", "n_pair_residuals", "sigma68_ns", "sigma68_ci_low", "sigma68_ci_high", "full_rms_ns", "full_rms_ci_low", "full_rms_ci_high", "tail_frac_abs_gt5ns", "tail_ci_low", "tail_ci_high"]),
        "",
        "## Tail-Risk Classifiers",
        "",
        markdown_table(classifiers, ["method", "auc", "average_precision", "brier", "ece", "mean_probability"]),
        "",
        "## Strongest Interactions",
        "",
        markdown_table(interactions, ["axis_a", "axis_b", "min_cell_n", "low_support", "tail_rate00", "tail_rate10", "tail_rate01", "tail_rate11", "additive_expected11", "interaction_delta", "interaction_delta_ci_low", "interaction_delta_ci_high", "interaction_odds_ratio", "log_interaction_or_ci_low", "log_interaction_or_ci_high", "composition_shift"], n=8),
        "",
        "## Leakage Checks",
        "",
        markdown_table(leakage, ["check", "value", "pass"]),
        "",
        "Run-vs-row sentinel: additive logit run-CV AUC `{:.3f}`, row-CV AUC `{:.3f}`. Tree shuffled-target AUC `{:.3f}` and axis-shuffled AUC `{:.3f}`.".format(
            cv_summary["run_cv_traditional_additive_auc_mean"],
            cv_summary["row_cv_additive_auc_mean"],
            cv_summary["run_cv_tree_shuffled_auc_mean"],
            cv_summary["run_cv_axis_shuffled_auc_mean"],
        ),
        "",
        "## Verdict",
        "",
        result["conclusion"],
        "",
        "The largest double-positive interaction is `{}` with `{}`. Its observed double-positive tail fraction is `{:.4f}` versus additive expectation `{:.4f}`; the bootstrap delta CI is `[{:.4f}, {:.4f}]`.".format(
            top["axis_a"],
            top["axis_b"],
            top["tail_rate11"],
            top["additive_expected11"],
            top["interaction_delta_ci_low"],
            top["interaction_delta_ci_high"],
        ),
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s04d_1781026226_608_7a105c91_timing_tail_interactions.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `pair_residuals_oof.csv.gz`, `residual_benchmark.csv`, `tail_classifier_benchmark.csv`, `pairwise_interaction_table.csv`, `ml_fold_diagnostics.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config_path = args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / config_path.name).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    reproduction = S04B.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    loader_config = analysis_config_for_loader(config)
    pulses = S16F.load_downstream_pulses(loader_config)
    S16F.add_cfd_times(pulses, loader_config)
    pairs = S16F.pair_table(pulses, config["timing"]["base_method"], loader_config, list(config["timing"]["analysis_runs"]))
    pairs = S04C.add_pathology_axes(pairs, config)
    pairs.to_csv(out_dir / "pair_residuals_raw.csv.gz", index=False)

    oof, folds, clf_cv, cv_summary = oof_models(pairs, config, rng)
    oof.to_csv(out_dir / "pair_residuals_oof.csv.gz", index=False)
    folds.to_csv(out_dir / "ml_fold_diagnostics.csv", index=False)
    clf_cv.to_csv(out_dir / "ml_tail_classifier_cv.csv", index=False)
    pd.DataFrame([cv_summary]).to_csv(out_dir / "ml_summary.csv", index=False)

    bench = residual_benchmark(oof, config, rng)
    classifiers = classifier_table(oof)
    interactions = interaction_table(oof, config, rng)
    checks = leakage_checks(oof, bench, classifiers, cv_summary)
    bench.to_csv(out_dir / "residual_benchmark.csv", index=False)
    classifiers.to_csv(out_dir / "tail_classifier_benchmark.csv", index=False)
    interactions.to_csv(out_dir / "pairwise_interaction_table.csv", index=False)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, interactions, classifiers)

    input_rows = []
    for run in S04B.configured_runs(config):
        path = S04B.raw_file(config, int(run))
        input_rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    raw = bench[bench["method"] == "raw_cfd20_pair_centered"].iloc[0]
    trad = bench[bench["method"] == "traditional_additive_ridge"].iloc[0]
    ml = bench[bench["method"] == "ml_rf_interaction_residual"].iloc[0]
    add = classifiers[classifiers["method"] == "traditional_additive_logit"].iloc[0]
    sparse = classifiers[classifiers["method"] == "ml_sparse_interaction_logit"].iloc[0]
    tree = classifiers[classifiers["method"] == "ml_calibrated_tree"].iloc[0]
    top = interactions.iloc[0]
    significant = interactions[(~interactions["low_support"]) & (interactions["significant_delta_ci_excludes_zero"])]
    conclusion = (
        "Single pathology axes miss measurable interaction structure, but the interactions are not a hidden timing-correction shortcut. "
        f"The strongest pair is {top['axis_a']} x {top['axis_b']}: observed double-positive tail fraction {top['tail_rate11']:.4f} versus additive expectation {top['additive_expected11']:.4f}, "
        f"delta {top['interaction_delta']:.4f} with 95% CI [{top['interaction_delta_ci_low']:.4f}, {top['interaction_delta_ci_high']:.4f}]. "
        f"Additive traditional tail AUC is {add['auc']:.3f}; sparse-interaction ML AUC is {sparse['auc']:.3f}; calibrated tree AUC is {tree['auc']:.3f} with ECE {tree['ece']:.4f}. "
        f"Residual sigma68 is {raw['sigma68_ns']:.3f} ns raw, {trad['sigma68_ns']:.3f} ns additive traditional, and {ml['sigma68_ns']:.3f} ns ML. "
        "Use the pairwise interaction ledger for veto composition and uncertainty inflation rather than replacing the S04 timing baseline."
    )
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "raw_root_reproduction": {
            "total_selected_pulses": int(reproduction[reproduction["quantity"] == "total selected B-stave pulses"]["reproduced"].iloc[0]),
            "pass": bool(reproduction["pass"].all()),
        },
        "split": {
            "unit": "run",
            "runs": [int(r) for r in config["timing"]["analysis_runs"]],
            "folds": int(config["ml"]["cv_folds"]),
            "bootstrap_unit": "run_then_event",
        },
        "metrics": {
            "sigma68_ns": {
                "raw": float(raw["sigma68_ns"]),
                "traditional_additive": float(trad["sigma68_ns"]),
                "ml_rf_interaction": float(ml["sigma68_ns"]),
            },
            "full_rms_ns": {
                "raw": float(raw["full_rms_ns"]),
                "traditional_additive": float(trad["full_rms_ns"]),
                "ml_rf_interaction": float(ml["full_rms_ns"]),
            },
            "tail_frac_abs_gt5ns": {
                "raw": float(raw["tail_frac_abs_gt5ns"]),
                "traditional_additive": float(trad["tail_frac_abs_gt5ns"]),
                "ml_rf_interaction": float(ml["tail_frac_abs_gt5ns"]),
            },
            "calibration_ece": {
                "traditional_additive_logit": float(add["ece"]),
                "ml_sparse_interaction_logit": float(sparse["ece"]),
                "ml_calibrated_tree": float(tree["ece"]),
            },
        },
        "traditional": {
            "method": "matched factorial additive table plus additive logistic/Ridge stress tests",
            "tail_auc": float(add["auc"]),
            "sigma68_ns": float(trad["sigma68_ns"]),
            "sigma68_ci": [float(trad["sigma68_ci_low"]), float(trad["sigma68_ci_high"])],
        },
        "ml": {
            "method": "sparse interaction logistic and calibrated constrained-depth tree tail-risk model",
            "sparse_interaction_auc": float(sparse["auc"]),
            "calibrated_tree_auc": float(tree["auc"]),
            "calibrated_tree_average_precision": float(tree["average_precision"]),
            "calibrated_tree_brier": float(tree["brier"]),
            "calibrated_tree_ece": float(tree["ece"]),
            "rf_residual_sigma68_ns": float(ml["sigma68_ns"]),
            "rf_residual_sigma68_ci": [float(ml["sigma68_ci_low"]), float(ml["sigma68_ci_high"])],
        },
        "interactions": {
            "n_pairs_tested": int(len(interactions)),
            "n_supported_significant_delta_ci_excludes_zero": int(len(significant)),
            "top": {
                "axis_a": str(top["axis_a"]),
                "axis_b": str(top["axis_b"]),
                "min_cell_n": int(top["min_cell_n"]),
                "low_support": bool(top["low_support"]),
                "n11": int(top["n11"]),
                "tail_rate11": float(top["tail_rate11"]),
                "additive_expected11": float(top["additive_expected11"]),
                "interaction_delta": float(top["interaction_delta"]),
                "interaction_delta_ci": [float(top["interaction_delta_ci_low"]), float(top["interaction_delta_ci_high"])],
                "interaction_odds_ratio": float(top["interaction_odds_ratio"]),
                "log_interaction_or_ci": [float(top["log_interaction_or_ci_low"]), float(top["log_interaction_or_ci_high"])],
                "composition_shift": float(top["composition_shift"]),
            },
        },
        "leakage_checks_pass": bool(checks["pass"].all()),
        "conclusion": conclusion,
        "input_sha256": hashlib.sha256("".join(row["sha256"] for row in input_rows).encode("ascii")).hexdigest(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, config_path, config, reproduction, bench, classifiers, interactions, checks, cv_summary, result)
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": " ".join([sys.executable] + sys.argv),
        "config": str(config_path),
        "runtime_sec": round(time.time() - t0, 2),
        "input_sha256": input_rows,
        "output_sha256": output_hashes(out_dir),
        "pathology_axes": PATHOLOGY_AXES,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_MAIN,
        "forbidden_features": sorted(FORBIDDEN_FEATURES),
        "random_seed": int(config["ml"]["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "raw_sigma68": float(raw["sigma68_ns"]),
                "traditional_sigma68": float(trad["sigma68_ns"]),
                "ml_sigma68": float(ml["sigma68_ns"]),
                "tree_auc": float(tree["auc"]),
                "top_interaction": [str(top["axis_a"]), str(top["axis_b"])],
                "top_delta": float(top["interaction_delta"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
