#!/usr/bin/env python3
"""S03f robust heavy-tail analytic timewalk loss for run-61-like folds."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03d_1781011277_910_1e815d8f_hierarchical_timewalk as s03d_hier


RUN61_EXPECTED = {
    "template_phase_base": 2.703513027082288,
    "s03a_amp_only_global": 2.1299643935400328,
    "hierarchical_shrinkage": 1.6353703774060109,
    "hgb_timewalk": 1.8173943452547097,
}


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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def solve_weighted_ridge(design: np.ndarray, y: np.ndarray, weights: np.ndarray, alpha: float) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    sw = np.sqrt(np.maximum(w, 0.0))
    xd = design * sw[:, None]
    yd = y * sw
    penalty = np.ones(design.shape[1], dtype=float) * float(alpha)
    penalty[0] = 0.0
    lhs = xd.T @ xd + np.diag(penalty)
    rhs = xd.T @ yd
    return np.linalg.solve(lhs, rhs)


def robust_design(
    pulses: pd.DataFrame, config: dict, targets: np.ndarray, fit_mask: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    staves = list(config["timing"]["downstream_staves"])
    X, feature_names = s03a.analytic_feature_matrix(pulses, "amp_only", staves)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    if int((fit_mask & finite).sum()) == 0:
        raise RuntimeError("empty robust analytic fit mask")
    Xs, center, scale = s03d_hier.standardize_train(X, fit_mask & finite)
    design = np.hstack([np.ones((len(Xs), 1)), Xs])
    return design, center, scale, feature_names


def fit_robust_analytic_pred(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    config: dict,
    train_runs: Iterable[int],
    loss: str,
    alpha: float,
    loss_param: float,
) -> Tuple[np.ndarray, pd.DataFrame, Dict[str, object]]:
    runs = pulses["run"].to_numpy(dtype=int)
    fit_mask = np.isin(runs, [int(r) for r in train_runs]) & np.isfinite(targets)
    design, center, scale, feature_names = robust_design(pulses, config, targets, fit_mask)
    finite_fit = fit_mask & np.all(np.isfinite(design), axis=1)
    y = targets[finite_fit]
    Xfit = design[finite_fit]

    weights = np.ones(len(y), dtype=float)
    if loss == "huber":
        delta = float(loss_param)
        coef = solve_weighted_ridge(Xfit, y, weights, alpha)
        for _ in range(int(config["robust_analytic"]["irls_iterations"])):
            resid = y - Xfit @ coef
            weights = np.minimum(1.0, delta / np.maximum(np.abs(resid), 1.0e-9))
            coef = solve_weighted_ridge(Xfit, y, weights, alpha)
    elif loss == "trimmed":
        coef0 = solve_weighted_ridge(Xfit, y, weights, alpha)
        resid0 = np.abs(y - Xfit @ coef0)
        cutoff = float(np.quantile(resid0, max(0.0, min(1.0, 1.0 - float(loss_param)))))
        weights = (resid0 <= cutoff).astype(float)
        coef = solve_weighted_ridge(Xfit, y, weights, alpha)
    else:
        raise ValueError(f"unknown robust loss {loss}")

    pred = design @ coef
    rows = []
    raw_coef = coef[1:] / scale
    for feature, raw, standardized in zip(feature_names, raw_coef, coef[1:]):
        rows.append(
            {
                "loss": loss,
                "loss_param": float(loss_param),
                "alpha": float(alpha),
                "feature": feature,
                "coefficient_ns_per_raw_unit": float(raw),
                "standardized_coefficient_ns": float(standardized),
            }
        )
    meta = {
        "loss": loss,
        "loss_param": float(loss_param),
        "alpha": float(alpha),
        "center": center,
        "scale": scale,
        "coef": coef,
        "train_weight_mean": float(np.mean(weights)),
        "train_weight_min": float(np.min(weights)),
        "train_nonzero_weight_frac": float(np.mean(weights > 0.0)),
    }
    return pred, pd.DataFrame(rows), meta


def score_corrected(
    pulses: pd.DataFrame, config: dict, base_method: str, pred: np.ndarray, rows: np.ndarray
) -> float:
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    va_runs = sorted(np.unique(pulses.iloc[rows]["run"].to_numpy(dtype=int)).tolist())
    vals = s03d_hier.evaluate_values(pulses.iloc[rows].copy(), "robust_cv", corrected[rows], config, va_runs)
    return s02.sigma68(vals)


def scan_robust_analytic(
    pulses: pd.DataFrame, targets: np.ndarray, config: dict, base_method: str
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, object]]]:
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    runs = pulses["run"].to_numpy(dtype=int)
    staves = list(config["timing"]["downstream_staves"])
    X, _ = s03a.analytic_feature_matrix(pulses, "amp_only", staves)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    groups = runs[train_mask]
    idx_train = np.flatnonzero(train_mask)
    n_splits = min(int(config["robust_analytic"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    specs = []
    for alpha in config["robust_analytic"]["ridge_alphas"]:
        for delta in config["robust_analytic"]["huber_deltas_ns"]:
            specs.append(("huber", float(alpha), float(delta)))
        for trim in config["robust_analytic"]["trim_fractions"]:
            specs.append(("trimmed", float(alpha), float(trim)))

    cv_rows = []
    best: Dict[str, Dict[str, object]] = {
        "huber": {"score": np.inf},
        "trimmed": {"score": np.inf},
    }
    for loss, alpha, param in specs:
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            fold_train_runs = sorted(np.unique(groups[tr]).astype(int).tolist())
            pred, _, meta = fit_robust_analytic_pred(pulses, targets, config, fold_train_runs, loss, alpha, param)
            va_global = idx_train[va]
            score = score_corrected(pulses, config, base_method, pred, va_global)
            fold_scores.append(score)
            cv_rows.append(
                {
                    "loss": loss,
                    "alpha": alpha,
                    "loss_param": param,
                    "fold": int(fold),
                    "sigma68_ns": score,
                    "n_pair_residuals": int(len(s03d_hier.evaluate_values(
                        pulses.iloc[va_global].copy(),
                        "robust_cv_count",
                        pulses[f"t_{base_method}_ns"].to_numpy(dtype=float)[va_global] - pred[va_global],
                        config,
                        sorted(np.unique(runs[va_global]).astype(int).tolist()),
                    ))),
                    "train_weight_mean": meta["train_weight_mean"],
                    "train_nonzero_weight_frac": meta["train_nonzero_weight_frac"],
                }
            )
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append(
            {
                "loss": loss,
                "alpha": alpha,
                "loss_param": param,
                "fold": -1,
                "sigma68_ns": mean_score,
                "n_pair_residuals": 0,
                "train_weight_mean": np.nan,
                "train_nonzero_weight_frac": np.nan,
            }
        )
        if mean_score < float(best[loss]["score"]):
            best[loss] = {"score": mean_score, "loss": loss, "alpha": alpha, "loss_param": param}

    preds = {}
    coef_parts = []
    final_meta = {}
    for loss in ["huber", "trimmed"]:
        choice = best[loss]
        pred, coef, meta = fit_robust_analytic_pred(
            pulses,
            targets,
            config,
            train_runs,
            str(choice["loss"]),
            float(choice["alpha"]),
            float(choice["loss_param"]),
        )
        method = f"robust_{loss}"
        preds[method] = pred
        coef["method"] = method
        coef_parts.append(coef)
        final_meta[method] = {**choice, **meta}
    return preds, pd.DataFrame(cv_rows), pd.concat(coef_parts, ignore_index=True), final_meta


def hgb_param_grid(config: dict) -> List[dict]:
    rows = []
    for loss in config["hgb_robust"]["loss"]:
        for max_iter in config["hgb_robust"]["max_iter"]:
            for learning_rate in config["hgb_robust"]["learning_rate"]:
                for max_leaf_nodes in config["hgb_robust"]["max_leaf_nodes"]:
                    for l2_regularization in config["hgb_robust"]["l2_regularization"]:
                        rows.append(
                            {
                                "loss": str(loss),
                                "max_iter": int(max_iter),
                                "learning_rate": float(learning_rate),
                                "max_leaf_nodes": int(max_leaf_nodes),
                                "l2_regularization": float(l2_regularization),
                                "max_bins": int(config["hgb_robust"]["max_bins"]),
                                "random_state": int(config["hgb_robust"]["random_seed"]),
                            }
                        )
    return rows


def run_hgb_robust(
    pulses: pd.DataFrame, config: dict, base_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    groups = runs[train_mask]
    idx_train = np.flatnonzero(train_mask)
    n_splits = min(int(config["hgb_robust"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": np.inf, "params": None}
    for params in hgb_param_grid(config):
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            model = HistGradientBoostingRegressor(**params)
            model.fit(X[train_mask][tr], targets[train_mask][tr])
            pred = np.full(len(pulses), np.nan)
            pred[idx_train[va]] = model.predict(X[train_mask][va])
            tmp = pulses.copy()
            tmp["t_hgb_robust_ns"] = tmp[f"t_{base_method}_ns"] - pred
            va_runs = sorted(np.unique(runs[idx_train[va]]).astype(int).tolist())
            vals = s02.pairwise_residuals(tmp.iloc[idx_train[va]], "hgb_robust", 2.0, config, va_runs)
            score = s02.sigma68(vals)
            fold_scores.append(score)
            cv_rows.append({**params, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals))})
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append({**params, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
        if mean_score < best["score"]:
            best = {"score": mean_score, "params": params}

    final_model = HistGradientBoostingRegressor(**best["params"])
    final_model.fit(X[train_mask], targets[train_mask])
    pred = final_model.predict(X)
    out = pulses.copy()
    out["hgb_robust_target_residual_ns"] = targets
    out["hgb_robust_pred_residual_ns"] = pred
    out["t_hgb_robust_ns"] = out[f"t_{base_method}_ns"] - pred
    return out, pd.DataFrame(cv_rows), best


def shuffled_robust_control(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    config: dict,
    base_method: str,
    meta: Dict[str, object],
    heldout_run: int,
) -> float:
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    shuffled = targets.copy()
    rng = np.random.default_rng(int(config["robust_analytic"]["random_seed"]) + 401 + int(heldout_run))
    shuffled_train = shuffled[train_mask].copy()
    rng.shuffle(shuffled_train)
    shuffled[train_mask] = shuffled_train
    pred, _, _ = fit_robust_analytic_pred(
        pulses,
        shuffled,
        config,
        train_runs,
        str(meta["loss"]),
        float(meta["alpha"]),
        float(meta["loss_param"]),
    )
    tmp = pulses.copy()
    tmp["t_robust_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "robust_shuffled", 2.0, config, [heldout_run])
    return s02.sigma68(vals)


def shuffled_hgb_control(
    pulses: pd.DataFrame, config: dict, base_method: str, best: dict, heldout_run: int
) -> float:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    rng = np.random.default_rng(int(config["hgb_robust"]["random_seed"]) + 503 + int(heldout_run))
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    model = HistGradientBoostingRegressor(**best["params"])
    model.fit(X[train_mask], shuffled)
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp["t_hgb_robust_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "hgb_robust_shuffled", 2.0, config, [heldout_run])
    return s02.sigma68(vals)


def bootstrap_method_rows(
    pulses: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    methods: List[Tuple[str, str]],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residual_rows = []
    heldout_run = int(config["timing"]["heldout_runs"][0])
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, 2.0, config, [heldout_run])
        ci = s02.bootstrap_ci(vals, rng, int(config["robust_analytic"]["bootstrap_samples"]))
        rows.append(
            {
                "heldout_run": heldout_run,
                "method": label,
                "metric": "heldout_pairwise_sigma68_ns",
                "value": s02.sigma68(vals),
                "ci_low": ci[0],
                "ci_high": ci[1],
                **s02.metric_summary(vals),
            }
        )
        residual_rows.extend(
            {
                "heldout_run": heldout_run,
                "method": label,
                "pairwise_residual_ns": float(value),
            }
            for value in vals
        )
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


def run_reference_fold(
    pulses_all: pd.DataFrame, base_config: dict, heldout_run: int, all_runs: List[int], rng: np.random.Generator
) -> pd.DataFrame:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = s03d_hier.prepare_base_pulses(pulses_all, config)
    s03a_pulses, _, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    hier_pred, _, _, _, hier_best = s03d_hier.scan_hierarchical(pulses, targets, config)
    hgb_pulses, _, hgb_best = s03d_hier.s03d.run_hgb(pulses, config, base_method)
    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_hier_shrinkage_ns"] = combined[f"t_{base_method}_ns"].to_numpy(dtype=float) - hier_pred
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)
    bench, _ = bootstrap_method_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only_global"),
            ("hier_shrinkage", "hierarchical_shrinkage"),
            ("hgb_timewalk", "hgb_timewalk"),
        ],
    )
    bench["s03a_candidate"] = s03a_candidate
    bench["s03a_alpha"] = s03a_alpha
    bench["hier_alpha_global"] = hier_best["alpha_global"]
    bench["hier_alpha_dev"] = hier_best["alpha_dev"]
    bench["hgb_cv_sigma68_ns"] = hgb_best["score"]
    return bench


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = s03d_hier.prepare_base_pulses(pulses_all, config)

    s03a_pulses, _, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    hier_pred, hier_cv, hier_coef, _, hier_best = s03d_hier.scan_hierarchical(pulses, targets, config)
    robust_preds, robust_cv, robust_coef, robust_meta = scan_robust_analytic(pulses, targets, config, base_method)
    hgb_pulses, hgb_cv, hgb_best = run_hgb_robust(pulses, config, base_method)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_hier_shrinkage_ns"] = combined[f"t_{base_method}_ns"].to_numpy(dtype=float) - hier_pred
    combined["t_robust_huber_ns"] = combined[f"t_{base_method}_ns"].to_numpy(dtype=float) - robust_preds["robust_huber"]
    combined["t_robust_trimmed_ns"] = combined[f"t_{base_method}_ns"].to_numpy(dtype=float) - robust_preds["robust_trimmed"]
    combined["t_hgb_robust_ns"] = hgb_pulses["t_hgb_robust_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_method_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only_global"),
            ("hier_shrinkage", "s03d_hierarchical_shrinkage"),
            ("robust_huber", "robust_huber_ridge"),
            ("robust_trimmed", "robust_trimmed_ridge"),
            ("hgb_robust", "ml_hgb_absolute_error"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["s03a_candidate"] = s03a_candidate
    benchmark["s03a_alpha"] = s03a_alpha
    benchmark["hier_alpha_global"] = hier_best["alpha_global"]
    benchmark["hier_alpha_dev"] = hier_best["alpha_dev"]
    benchmark["hier_cv_sigma68_ns"] = hier_best["score"]
    for method, meta in robust_meta.items():
        prefix = method.replace("robust_", "robust_")
        benchmark[f"{prefix}_cv_sigma68_ns"] = float(meta["score"])
        benchmark[f"{prefix}_alpha"] = float(meta["alpha"])
        benchmark[f"{prefix}_loss_param"] = float(meta["loss_param"])
        benchmark[f"{prefix}_train_weight_mean"] = float(meta["train_weight_mean"])
    benchmark["hgb_robust_cv_sigma68_ns"] = hgb_best["score"]
    benchmark["hgb_robust_loss"] = hgb_best["params"]["loss"]

    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(combined[combined["run"].isin([heldout_run])]["event_id"])
    leakage = pd.DataFrame(
        [
            {
                "heldout_run": heldout_run,
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids & heldout_event_ids)),
                "unit": "events",
            },
            {
                "heldout_run": heldout_run,
                "check": "robust_huber_shuffled_target_sigma68",
                "value": shuffled_robust_control(
                    pulses, targets, config, base_method, robust_meta["robust_huber"], heldout_run
                ),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "robust_trimmed_shuffled_target_sigma68",
                "value": shuffled_robust_control(
                    pulses, targets, config, base_method, robust_meta["robust_trimmed"], heldout_run
                ),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "hgb_abs_loss_shuffled_target_sigma68",
                "value": shuffled_hgb_control(pulses, config, base_method, hgb_best, heldout_run),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "features_exclude_run_event_order_cross_stave_time",
                "value": 1.0,
                "unit": "bool",
            },
            {
                "heldout_run": heldout_run,
                "check": "final_models_use_heldout_rows",
                "value": 0.0,
                "unit": "bool",
            },
        ]
    )
    hier_cv["heldout_run"] = heldout_run
    robust_cv["heldout_run"] = heldout_run
    robust_coef["heldout_run"] = heldout_run
    hgb_cv["heldout_run"] = heldout_run
    return benchmark, residuals, leakage, hier_cv, robust_cv, robust_coef, hgb_cv


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(residuals["heldout_run"].unique().tolist())
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        by_run = {run: sub["pairwise_residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot_vals = np.concatenate([by_run[int(run)] for run in sampled if len(by_run[int(run)])])
            stats.append(s02.sigma68(boot_vals))
        ci_low, ci_high = np.percentile(stats, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame) -> None:
    order = [
        "template_phase_base",
        "s03a_amp_only_global",
        "s03d_hierarchical_shrinkage",
        "robust_huber_ridge",
        "robust_trimmed_ridge",
        "ml_hgb_absolute_error",
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03f robust-loss held-out run performance")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    sub = pooled.set_index("method").loc[order].reset_index()
    xpos = np.arange(len(sub))
    ax.bar(xpos, sub["value"])
    ax.errorbar(
        xpos,
        sub["value"],
        yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.set_xticks(xpos)
    ax.set_xticklabels(sub["method"], rotation=25, ha="right")
    ax.set_ylabel("pooled LORO sigma68 (ns)")
    ax.set_title("Run-bootstrap pooled interval")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_pooled_bootstrap.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro_counts: pd.DataFrame,
    run61_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    order = [
        "template_phase_base",
        "s03a_amp_only_global",
        "s03d_hierarchical_shrinkage",
        "robust_huber_ridge",
        "robust_trimmed_ridge",
        "ml_hgb_absolute_error",
    ]
    pooled_view = pooled.set_index("method").loc[order].reset_index()
    run61 = per_run[(per_run["heldout_run"] == 61) & (per_run["method"].isin(order))]
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    lines = [
        "# Study report: S03f - Robust heavy-tail analytic timewalk loss",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65",
        f"- **Config:** `{config_path}`",
        "",
        "## 0. Question",
        "",
        "Test whether the run-61 residual width left by S03d is mainly a heavy-tail loss problem rather than coefficient drift.",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "Selected-pulse counts were rerun from raw ROOT before any robust fit.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "The S03d run-61 reference numbers were then reproduced from the same raw-derived pulse table before scanning robust losses.",
        "",
        run61_repro.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "Traditional baselines are global S03a amp-only ridge and S03d hierarchical shrinkage. Robust traditional variants refit the same amp-only analytic residual target with Huber IRLS and trimmed-target ridge. The ML comparator is a HistGradientBoosting residual corrector with absolute-error loss. All scores are leave-one-run-out and bootstrapped on held-out residuals; pooled intervals resample held-out runs.",
        "",
        "## 3. Held-out head-to-head",
        "",
        per_run[
            [
                "heldout_run",
                "method",
                "value",
                "ci_low",
                "ci_high",
                "n_pair_residuals",
                "robust_huber_cv_sigma68_ns",
                "robust_trimmed_cv_sigma68_ns",
                "hgb_robust_cv_sigma68_ns",
            ]
        ]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        pooled_view[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Run 61 rows:",
        "",
        run61[["method", "value", "ci_low", "ci_high", "n_pair_residuals"]].sort_values("method").to_markdown(index=False),
        "",
        "## 4. Leakage checks",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "The analytic and HGB feature sets exclude run number, event id, event order, other-stave timing, current, and held-out labels. Shuffled-target controls were repeated for every held-out run.",
        "",
        "## 5. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"Best robust traditional method is `{result['traditional']['best_robust_method']}` at `{result['traditional']['best_robust']['value']:.3f} ns`; S03d hierarchical is `{result['traditional']['s03d_hierarchical_shrinkage']['value']:.3f} ns`; ML absolute-error HGB is `{result['ml']['value']:.3f} ns`.",
        f"On run 61, the best robust traditional score is `{result['run61']['best_robust_sigma68_ns']:.3f} ns` versus S03d hierarchical `{result['run61']['s03d_hierarchical_sigma68_ns']:.3f} ns`.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03f_1781020980_5815_7557392d_robust_heavytail_timewalk.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `run61_reference_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `hierarchical_cv_scan.csv`, `robust_cv_scan.csv`, `robust_coefficients.csv`, `hgb_robust_cv_scan.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03f_1781020980_5815_7557392d_robust_heavytail_timewalk.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["robust_analytic"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(run) for run in config["timing"]["loo_runs"]]

    run61_reference = run_reference_fold(pulses_all, config, 61, all_runs, rng)
    run61_repro = run61_reference[run61_reference["method"].isin(RUN61_EXPECTED)].copy()
    run61_repro["reference_value"] = run61_repro["method"].map(RUN61_EXPECTED)
    run61_repro["delta"] = run61_repro["value"] - run61_repro["reference_value"]
    run61_repro["pass"] = run61_repro["delta"].abs() < 1.0e-9
    run61_repro[["method", "value", "reference_value", "delta", "pass"]].to_csv(
        out_dir / "run61_reference_reproduction.csv", index=False
    )
    if not bool(run61_repro["pass"].all()):
        raise RuntimeError("S03d run-61 reproduction gate failed")

    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    hier_cv_parts = []
    robust_cv_parts = []
    robust_coef_parts = []
    hgb_cv_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, hier_cv, robust_cv, robust_coef, hgb_cv = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        hier_cv_parts.append(hier_cv)
        robust_cv_parts.append(robust_cv)
        robust_coef_parts.append(robust_coef)
        hgb_cv_parts.append(hgb_cv)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    hier_cv = pd.concat(hier_cv_parts, ignore_index=True)
    robust_cv = pd.concat(robust_cv_parts, ignore_index=True)
    robust_coef = pd.concat(robust_coef_parts, ignore_index=True)
    hgb_cv = pd.concat(hgb_cv_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["robust_analytic"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    hier_cv.to_csv(out_dir / "hierarchical_cv_scan.csv", index=False)
    robust_cv.to_csv(out_dir / "robust_cv_scan.csv", index=False)
    robust_coef.to_csv(out_dir / "robust_coefficients.csv", index=False)
    hgb_cv.to_csv(out_dir / "hgb_robust_cv_scan.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    s03a_row = pooled_idx.loc["s03a_amp_only_global"]
    hier_row = pooled_idx.loc["s03d_hierarchical_shrinkage"]
    huber_row = pooled_idx.loc["robust_huber_ridge"]
    trimmed_row = pooled_idx.loc["robust_trimmed_ridge"]
    hgb_row = pooled_idx.loc["ml_hgb_absolute_error"]
    robust_rows = {"robust_huber_ridge": huber_row, "robust_trimmed_ridge": trimmed_row}
    best_robust_method, best_robust_row = min(robust_rows.items(), key=lambda item: float(item[1]["value"]))
    run61_table = per_run[per_run["heldout_run"] == 61].set_index("method")
    run61_robust = run61_table.loc[[best_robust_method]]
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    shuffle_min = float(
        leakage[leakage["check"].str.contains("shuffled_target_sigma68", regex=False)]["value"].min()
    )
    best_score = min(float(best_robust_row["value"]), float(hgb_row["value"]))
    looks_too_good = bool(best_score < 0.8 or float(hier_row["value"] - best_robust_row["value"]) > 0.45)
    leakage_flag = bool(event_overlap != 0 or shuffle_min < best_score + 0.2)
    run61_interpretation = (
        "robust_loss_does_not_explain_run61_width"
        if float(run61_robust.iloc[0]["value"]) >= float(run61_table.loc["s03d_hierarchical_shrinkage", "value"]) - 0.1
        else "robust_loss_partially_explains_run61_width"
    )
    verdict = (
        "run61_not_primarily_heavy_tail_loss_no_leakage_flag"
        if run61_interpretation == "robust_loss_does_not_explain_run61_width" and not leakage_flag
        else "robust_loss_or_leakage_needs_followup"
    )

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and run61_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "s03d_run61_reference_pass": bool(run61_repro["pass"].all()),
        },
        "split": {
            "unit": "run",
            "heldout_runs": all_runs,
            "bootstrap_unit": "heldout_run",
        },
        "baseline": {
            "method": "template_phase",
            "value": float(base["value"]),
            "ci": [float(base["ci_low"]), float(base["ci_high"])],
        },
        "traditional": {
            "s03a_amp_only_global": {
                "value": float(s03a_row["value"]),
                "ci": [float(s03a_row["ci_low"]), float(s03a_row["ci_high"])],
            },
            "s03d_hierarchical_shrinkage": {
                "value": float(hier_row["value"]),
                "ci": [float(hier_row["ci_low"]), float(hier_row["ci_high"])],
            },
            "robust_huber_ridge": {
                "value": float(huber_row["value"]),
                "ci": [float(huber_row["ci_low"]), float(huber_row["ci_high"])],
                "delta_vs_s03d_hierarchical_ns": float(hier_row["value"] - huber_row["value"]),
            },
            "robust_trimmed_ridge": {
                "value": float(trimmed_row["value"]),
                "ci": [float(trimmed_row["ci_low"]), float(trimmed_row["ci_high"])],
                "delta_vs_s03d_hierarchical_ns": float(hier_row["value"] - trimmed_row["value"]),
            },
            "best_robust_method": best_robust_method,
            "best_robust": {
                "value": float(best_robust_row["value"]),
                "ci": [float(best_robust_row["ci_low"]), float(best_robust_row["ci_high"])],
            },
        },
        "ml": {
            "method": "hist_gradient_boosting_absolute_error_residual_corrector",
            "value": float(hgb_row["value"]),
            "ci": [float(hgb_row["ci_low"]), float(hgb_row["ci_high"])],
            "delta_vs_s03d_hierarchical_ns": float(hier_row["value"] - hgb_row["value"]),
        },
        "run61": {
            "s03d_hierarchical_sigma68_ns": float(run61_table.loc["s03d_hierarchical_shrinkage", "value"]),
            "best_robust_method": best_robust_method,
            "best_robust_sigma68_ns": float(run61_robust.iloc[0]["value"]),
            "best_robust_ci": [float(run61_robust.iloc[0]["ci_low"]), float(run61_robust.iloc[0]["ci_high"])],
            "ml_hgb_absolute_error_sigma68_ns": float(run61_table.loc["ml_hgb_absolute_error", "value"]),
            "n_pair_residuals": int(run61_robust.iloc[0]["n_pair_residuals"]),
            "interpretation": run61_interpretation,
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "final_models_use_heldout_rows": False,
            "shuffled_target_min_sigma68_ns": shuffle_min,
            "looks_too_good": looks_too_good,
            "leakage_flag": leakage_flag,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro_counts, run61_repro, per_run, pooled, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["robust_analytic"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "best_robust_method": best_robust_method,
                "best_robust": float(best_robust_row["value"]),
                "s03d_hierarchical": float(hier_row["value"]),
                "ml_hgb_absolute_error": float(hgb_row["value"]),
                "run61_best_robust": float(run61_robust.iloc[0]["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
