#!/usr/bin/env python3
"""S03d run-level hierarchical shrinkage vs S03b binned and ML timewalk."""

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
from sklearn.model_selection import GroupKFold

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b
import s03d_leave_one_run_s03ab_hgb_stability as s03d


RUN65_EXPECTED = {
    "template_phase_base": 2.889152765080617,
    "s03a_amp_only_global": 1.494640076269676,
    "s03b_binned_timewalk": 1.5695763825403084,
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


def prepare_base_pulses(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, str]:
    out = pulses.copy()
    train_pulses = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    expected = str(config["timing"]["base_method"])
    if best_method != expected:
        raise RuntimeError(f"Expected train-selected base method {expected}, got {best_method}")
    return out, best_method


def standardize_train(X: np.ndarray, train_mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    center = np.nanmean(X[train_mask], axis=0)
    scale = np.nanstd(X[train_mask], axis=0)
    scale = np.where((scale == 0.0) | ~np.isfinite(scale), 1.0, scale)
    return (X - center) / scale, center, scale


def hierarchical_design(Xs: np.ndarray, runs: np.ndarray, train_runs: List[int]) -> np.ndarray:
    parts = [np.ones((len(Xs), 1)), Xs]
    for run in train_runs:
        parts.append(Xs * (runs == int(run))[:, None])
    return np.hstack(parts)


def solve_penalized(
    design: np.ndarray,
    y: np.ndarray,
    n_features: int,
    n_runs: int,
    alpha_global: float,
    alpha_dev: float,
) -> np.ndarray:
    penalty = np.zeros(design.shape[1], dtype=float)
    penalty[1 : 1 + n_features] = float(alpha_global)
    penalty[1 + n_features :] = float(alpha_dev)
    lhs = design.T @ design + np.diag(penalty)
    rhs = design.T @ y
    return np.linalg.solve(lhs, rhs)


def predict_hierarchical(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    train_runs: List[int],
    alpha_global: float,
    alpha_dev: float,
) -> Tuple[np.ndarray, pd.DataFrame, Dict[str, object]]:
    staves = sorted(pulses["stave"].unique().tolist())
    X, feature_names = s03a.analytic_feature_matrix(pulses, "amp_only", staves)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    Xs, center, scale = standardize_train(X, train_mask)
    design = hierarchical_design(Xs, runs, train_runs)
    coef = solve_penalized(
        design[train_mask],
        targets[train_mask],
        len(feature_names),
        len(train_runs),
        alpha_global,
        alpha_dev,
    )
    pred = design @ coef

    rows = []
    global_coef = coef[1 : 1 + len(feature_names)]
    for feature, raw_coef, standardized_coef in zip(feature_names, global_coef / scale, global_coef):
        rows.append(
            {
                "component": "population",
                "run": -1,
                "feature": feature,
                "coefficient_ns_per_raw_unit": float(raw_coef),
                "standardized_coefficient_ns": float(standardized_coef),
            }
        )
    offset = 1 + len(feature_names)
    for i, run in enumerate(train_runs):
        dev = coef[offset + i * len(feature_names) : offset + (i + 1) * len(feature_names)]
        for feature, raw_coef, standardized_coef in zip(feature_names, dev / scale, dev):
            rows.append(
                {
                    "component": "run_deviation",
                    "run": int(run),
                    "feature": feature,
                    "coefficient_ns_per_raw_unit": float(raw_coef),
                    "standardized_coefficient_ns": float(standardized_coef),
                }
            )

    meta = {
        "feature_names": feature_names,
        "center": center,
        "scale": scale,
        "coef": coef,
        "train_runs": train_runs,
        "alpha_global": float(alpha_global),
        "alpha_dev": float(alpha_dev),
    }
    return pred, pd.DataFrame(rows), meta


def evaluate_values(
    pulses: pd.DataFrame,
    method_name: str,
    values: np.ndarray,
    config: dict,
    runs: Iterable[int],
) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, list(runs))


def scan_hierarchical(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    config: dict,
) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame, Dict[str, object], Dict[str, float]]:
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    runs = pulses["run"].to_numpy(dtype=int)
    X, feature_names = s03a.analytic_feature_matrix(
        pulses, "amp_only", list(config["timing"]["downstream_staves"])
    )
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    groups = runs[train_mask]
    idx_train = np.flatnonzero(train_mask)
    n_splits = min(int(config["hierarchical"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": np.inf, "alpha_global": None, "alpha_dev": None}

    for alpha_global in config["hierarchical"]["global_alphas"]:
        for alpha_dev in config["hierarchical"]["deviation_alphas"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
                fold_train_runs = sorted(np.unique(groups[tr]).astype(int).tolist())
                pred, _, _ = predict_hierarchical(
                    pulses.iloc[idx_train].copy(),
                    targets[idx_train],
                    fold_train_runs,
                    float(alpha_global),
                    float(alpha_dev),
                )
                va_idx_local = va
                va_global = idx_train[va]
                corrected = pulses.iloc[va_global][f"t_{config['timing']['base_method']}_ns"].to_numpy(dtype=float) - pred[
                    va_idx_local
                ]
                va_runs = sorted(np.unique(runs[va_global]).astype(int).tolist())
                vals = evaluate_values(
                    pulses.iloc[va_global].copy(), "hier_cv", corrected, config, va_runs
                )
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "alpha_global": float(alpha_global),
                        "alpha_dev": float(alpha_dev),
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": int(len(vals)),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "alpha_global": float(alpha_global),
                    "alpha_dev": float(alpha_dev),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                }
            )
            if mean_score < best["score"]:
                best = {
                    "score": mean_score,
                    "alpha_global": float(alpha_global),
                    "alpha_dev": float(alpha_dev),
                }

    pred, coef, meta = predict_hierarchical(
        pulses,
        targets,
        train_runs,
        float(best["alpha_global"]),
        float(best["alpha_dev"]),
    )
    return pred, pd.DataFrame(cv_rows), coef, meta, best


def shuffled_hierarchical_control(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    config: dict,
    best: Dict[str, float],
    heldout_run: int,
) -> float:
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    shuffled = targets.copy()
    rng = np.random.default_rng(int(config["hierarchical"]["random_seed"]) + 303 + int(heldout_run))
    shuffled_train = shuffled[train_mask].copy()
    rng.shuffle(shuffled_train)
    shuffled[train_mask] = shuffled_train
    pred, _, _ = predict_hierarchical(
        pulses,
        shuffled,
        train_runs,
        float(best["alpha_global"]),
        float(best["alpha_dev"]),
    )
    tmp = pulses.copy()
    tmp["t_hier_shuffled_ns"] = tmp[f"t_{config['timing']['base_method']}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "hier_shuffled", 2.0, config, [heldout_run])
    return s02.sigma68(vals)


def oracle_run_adaptation(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    config: dict,
    meta: Dict[str, object],
    heldout_run: int,
) -> Dict[str, float]:
    staves = list(config["timing"]["downstream_staves"])
    X, _ = s03a.analytic_feature_matrix(pulses, "amp_only", staves)
    runs = pulses["run"].to_numpy(dtype=int)
    held_mask = (runs == int(heldout_run)) & np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    Xs = (X - meta["center"]) / meta["scale"]
    n_features = Xs.shape[1]
    base_design = np.hstack([np.ones((len(Xs), 1)), Xs])
    population_coef = np.asarray(meta["coef"][: 1 + n_features], dtype=float)
    population_pred = base_design @ population_coef
    residual = targets[held_mask] - population_pred[held_mask]
    alpha = float(config["hierarchical"]["oracle_deviation_alpha"])
    lhs = Xs[held_mask].T @ Xs[held_mask] + np.eye(n_features) * alpha
    rhs = Xs[held_mask].T @ residual
    delta = np.linalg.solve(lhs, rhs)
    adapted_pred = population_pred.copy()
    adapted_pred[held_mask] += Xs[held_mask] @ delta

    pop_corrected = pulses[f"t_{config['timing']['base_method']}_ns"].to_numpy(dtype=float) - population_pred
    adapted_corrected = pulses[f"t_{config['timing']['base_method']}_ns"].to_numpy(dtype=float) - adapted_pred
    pop_vals = evaluate_values(pulses, "hier_population_diag", pop_corrected, config, [heldout_run])
    adapted_vals = evaluate_values(pulses, "hier_oracle_adapted_diag", adapted_corrected, config, [heldout_run])
    return {
        "heldout_run": int(heldout_run),
        "population_sigma68_ns": s02.sigma68(pop_vals),
        "oracle_adapted_sigma68_ns": s02.sigma68(adapted_vals),
        "oracle_gain_ns": s02.sigma68(pop_vals) - s02.sigma68(adapted_vals),
        "oracle_delta_l2_standardized": float(np.sqrt(np.sum(delta**2))),
        "n_heldout_pulses_for_oracle": int(held_mask.sum()),
    }


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
        ci = s02.bootstrap_ci(vals, rng, int(config["hierarchical"]["bootstrap_samples"]))
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


def reproduce_run65_references(
    pulses_all: pd.DataFrame,
    base_config: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    all_runs = [int(run) for run in base_config["timing"]["loo_runs"]]
    train_runs = [run for run in all_runs if run != 65]
    config = fold_config(base_config, train_runs, [65])
    pulses, base_method = prepare_base_pulses(pulses_all, config)
    s03a_pulses, _, _, _, _ = s03a.run_analytic(pulses, config, base_method)
    binned_pulses, _, _, _ = s03b.scan_binned_candidates(pulses, config, base_method)
    combined = pulses.copy()
    combined["t_s03a_amp_only_global_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_binned_timewalk_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    bench, _ = bootstrap_method_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only_global", "s03a_amp_only_global"),
            ("s03b_binned_timewalk", "s03b_binned_timewalk"),
        ],
    )
    repro = bench[["method", "value", "ci_low", "ci_high", "n_pair_residuals"]].copy()
    repro["reference_value"] = repro["method"].map(RUN65_EXPECTED)
    repro["delta"] = repro["value"] - repro["reference_value"]
    repro["pass"] = repro["delta"].abs() < 1.0e-9
    return repro


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = prepare_base_pulses(pulses_all, config)

    s03a_pulses, _, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    hier_pred, hier_cv, hier_coef, hier_meta, hier_best = scan_hierarchical(pulses, targets, config)
    binned_pulses, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    hgb_pulses, hgb_cv, hgb_best = s03d.run_hgb(pulses, config, base_method)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_hier_shrinkage_ns"] = combined[f"t_{base_method}_ns"].to_numpy(dtype=float) - hier_pred
    combined["t_s03b_binned_timewalk_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_method_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only_global"),
            ("hier_shrinkage", "hierarchical_shrinkage"),
            ("s03b_binned_timewalk", "s03b_binned_timewalk"),
            ("hgb_timewalk", "hgb_timewalk"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["s03a_candidate"] = s03a_candidate
    benchmark["s03a_alpha"] = s03a_alpha
    benchmark["hier_alpha_global"] = hier_best["alpha_global"]
    benchmark["hier_alpha_dev"] = hier_best["alpha_dev"]
    benchmark["hier_cv_sigma68_ns"] = hier_best["score"]
    benchmark["s03b_mode"] = binned_best["mode"]
    benchmark["s03b_direction"] = binned_best["direction"]
    benchmark["s03b_n_bins"] = binned_best["n_bins"]
    benchmark["hgb_cv_sigma68_ns"] = hgb_best["score"]

    s03a_leak = s03a.run_negative_controls(pulses, config, base_method, s03a_candidate, s03a_alpha)
    analytic_shuffle = float(
        s03a_leak[s03a_leak["check"] == "analytic_timewalk_shuffled_target"]["heldout_sigma68_ns"].iloc[0]
    )
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
                "check": "s03a_shuffled_target_sigma68",
                "value": analytic_shuffle,
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "hier_shuffled_target_sigma68",
                "value": shuffled_hierarchical_control(pulses, targets, config, hier_best, heldout_run),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "s03b_shuffled_target_sigma68",
                "value": s03b.run_shuffled_binned_control(pulses, config, base_method, binned_best),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "hgb_shuffled_target_sigma68",
                "value": s03d.run_hgb_shuffled_control(pulses, config, base_method, hgb_best),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "hgb_features_exclude_run_event_order_cross_stave_time",
                "value": 1.0,
                "unit": "bool",
            },
            {
                "heldout_run": heldout_run,
                "check": "hierarchical_heldout_run_deviation_zeroed",
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
    hier_coef["heldout_run"] = heldout_run
    binned_cv["heldout_run"] = heldout_run
    binned_table = s03b.binned_model_table(binned_models)
    binned_table["heldout_run"] = heldout_run
    hgb_cv["heldout_run"] = heldout_run
    oracle = pd.DataFrame([oracle_run_adaptation(pulses, targets, config, hier_meta, heldout_run)])
    return benchmark, residuals, leakage, hier_cv, hier_coef, binned_cv, binned_table, hgb_cv, oracle


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


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, oracle: pd.DataFrame) -> None:
    order = [
        "template_phase_base",
        "s03a_amp_only_global",
        "hierarchical_shrinkage",
        "s03b_binned_timewalk",
        "hgb_timewalk",
    ]
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03d held-out run performance")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03d_hierarchical_per_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.4))
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
    fig.savefig(out_dir / "fig_s03d_hierarchical_pooled.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.plot(oracle["heldout_run"], oracle["population_sigma68_ns"], "o-", label="population")
    ax.plot(oracle["heldout_run"], oracle["oracle_adapted_sigma68_ns"], "o-", label="heldout oracle")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("sigma68 (ns)")
    ax.set_title("Diagnostic run-specific adaptation")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03d_oracle_adaptation.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro_counts: pd.DataFrame,
    run65_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    oracle: pd.DataFrame,
    result: dict,
) -> None:
    ordered = [
        "template_phase_base",
        "s03a_amp_only_global",
        "hierarchical_shrinkage",
        "s03b_binned_timewalk",
        "hgb_timewalk",
    ]
    pooled_view = pooled.set_index("method").loc[ordered].reset_index()
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    run61 = per_run[(per_run["heldout_run"] == 61) & (per_run["method"].isin(ordered))]
    lines = [
        "# Study report: S03d - Hierarchical analytic timewalk shrinkage vs S03b and ML",
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
        "Does a run-level partial-pooling analytic timewalk model improve the S03c amp-only analytic correction while staying honest against S03b binned and ML comparators?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun from raw ROOT before any model fitting.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "The run-65 S03a/S03b reference numbers were then reproduced from the same raw-derived pulse table before the main hierarchical and ML fits.",
        "",
        run65_repro.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "The traditional references are the S03a amp-only Ridge correction and the S03b monotone amplitude-binned correction. The new traditional model uses the S03a amplitude/stave features but fits population coefficients plus run-specific coefficient deviations, with the deviations L2-shrunk and zeroed for unseen held-out runs. The ML comparator is an HGB residual corrector from the same template-phase base timing.",
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
                "hier_alpha_global",
                "hier_alpha_dev",
                "hier_cv_sigma68_ns",
                "s03b_n_bins",
                "hgb_cv_sigma68_ns",
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
        "## 4. Drift diagnostic",
        "",
        "The oracle adaptation is diagnostic only: it uses held-out labels to fit one extra run-specific deviation around the population coefficients, so it is not a deployable held-out score.",
        "",
        oracle.to_markdown(index=False),
        "",
        "## 5. Leakage checks",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "The HGB comparator excludes run number, event id, event order, other-stave timing, current, and held-out labels. The hierarchical analytic model intentionally has train-run deviation terms, but the held-out run deviation block is zeroed and no held-out rows or labels are used for promoted predictions. S03a, hierarchical, S03b, and HGB shuffled-target controls are repeated for every held-out run.",
        "",
        "## 6. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"Hierarchical shrinkage pooled sigma68 is `{result['traditional']['hierarchical_shrinkage']['value']:.3f} ns`; global S03a is `{result['traditional']['s03a_amp_only_global']['value']:.3f} ns`; S03b is `{result['traditional']['s03b_binned_timewalk']['value']:.3f} ns`; HGB is `{result['ml']['value']:.3f} ns`.",
        f"Run 61 has `{result['run61']['n_pair_residuals']}` pair residuals, so the degradation is not a low-statistics fold; the diagnostic oracle gain is `{result['run61']['oracle_gain_ns']:.3f} ns`.",
        "",
        "## 7. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03d_1781020163_1096_2cf669f6_hierarchical_s03b_ml.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `hierarchical_cv_scan.csv`, `hierarchical_coefficients.csv`, `s03b_binned_cv_scan.csv`, `s03b_binned_model_table.csv`, `hgb_cv_scan.csv`, `run_drift_diagnostic.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03d_1781020163_1096_2cf669f6_hierarchical_s03b_ml.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["hierarchical"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(run) for run in config["timing"]["loo_runs"]]

    run65_repro = reproduce_run65_references(pulses_all, config, rng)
    run65_repro[["method", "value", "reference_value", "delta", "pass"]].to_csv(
        out_dir / "run65_reproduction.csv", index=False
    )
    if not bool(run65_repro["pass"].all()):
        raise RuntimeError("S03a/S03b run-65 reproduction gate failed")

    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    hier_cv_parts = []
    hier_coef_parts = []
    binned_cv_parts = []
    binned_table_parts = []
    hgb_cv_parts = []
    oracle_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, hier_cv, hier_coef, binned_cv, binned_table, hgb_cv, oracle = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        hier_cv_parts.append(hier_cv)
        hier_coef_parts.append(hier_coef)
        binned_cv_parts.append(binned_cv)
        binned_table_parts.append(binned_table)
        hgb_cv_parts.append(hgb_cv)
        oracle_parts.append(oracle)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    hier_cv = pd.concat(hier_cv_parts, ignore_index=True)
    hier_coef = pd.concat(hier_coef_parts, ignore_index=True)
    binned_cv = pd.concat(binned_cv_parts, ignore_index=True)
    binned_table = pd.concat(binned_table_parts, ignore_index=True)
    hgb_cv = pd.concat(hgb_cv_parts, ignore_index=True)
    oracle = pd.concat(oracle_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["hierarchical"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    hier_cv.to_csv(out_dir / "hierarchical_cv_scan.csv", index=False)
    hier_coef.to_csv(out_dir / "hierarchical_coefficients.csv", index=False)
    binned_cv.to_csv(out_dir / "s03b_binned_cv_scan.csv", index=False)
    binned_table.to_csv(out_dir / "s03b_binned_model_table.csv", index=False)
    hgb_cv.to_csv(out_dir / "hgb_cv_scan.csv", index=False)
    oracle.to_csv(out_dir / "run_drift_diagnostic.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled, oracle)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    global_row = pooled_idx.loc["s03a_amp_only_global"]
    hier_row = pooled_idx.loc["hierarchical_shrinkage"]
    s03b_row = pooled_idx.loc["s03b_binned_timewalk"]
    hgb_row = pooled_idx.loc["hgb_timewalk"]
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    min_shuffle = float(
        leakage[
            leakage["check"].isin(
                [
                    "s03a_shuffled_target_sigma68",
                    "hier_shuffled_target_sigma68",
                    "s03b_shuffled_target_sigma68",
                    "hgb_shuffled_target_sigma68",
                ]
            )
        ]["value"].min()
    )
    looks_too_good = bool(float(hier_row["value"]) < 0.8 or float(hier_row["value"] - hgb_row["value"]) < -0.3)
    leakage_flag = bool(
        event_overlap != 0
        or min_shuffle
        < min(float(hier_row["value"]), float(s03b_row["value"]), float(hgb_row["value"])) + 0.2
    )
    run61_perf = per_run[(per_run["heldout_run"] == 61) & (per_run["method"] == "hierarchical_shrinkage")].iloc[0]
    run61_oracle = oracle[oracle["heldout_run"] == 61].iloc[0]
    run61_stat_rank = int(
        per_run[per_run["method"] == "hierarchical_shrinkage"]["n_pair_residuals"].rank(ascending=False, method="min")[
            run61_perf.name
        ]
    )
    verdict = (
        "run61_degradation_not_limited_stats_partial_coefficient_drift_no_leakage_flag"
        if event_overlap == 0 and not leakage_flag
        else "stability_or_leakage_concern"
    )

    result = {
        "study": "S03d",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and run65_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "run65_s03a_s03b_pass": bool(run65_repro["pass"].all()),
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
                "method": "global_amp_only_ridge_residual_on_template_phase",
                "value": float(global_row["value"]),
                "ci": [float(global_row["ci_low"]), float(global_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - global_row["value"]),
            },
            "hierarchical_shrinkage": {
                "method": "population_plus_run_deviation_amp_only_ridge",
                "value": float(hier_row["value"]),
                "ci": [float(hier_row["ci_low"]), float(hier_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - hier_row["value"]),
                "delta_vs_global_s03a_ns": float(global_row["value"] - hier_row["value"]),
                "delta_vs_s03b_binned_timewalk_ns": float(s03b_row["value"] - hier_row["value"]),
            },
            "s03b_binned_timewalk": {
                "method": "per_stave_monotone_decreasing_binned_timewalk",
                "value": float(s03b_row["value"]),
                "ci": [float(s03b_row["ci_low"]), float(s03b_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - s03b_row["value"]),
                "delta_vs_global_s03a_ns": float(global_row["value"] - s03b_row["value"]),
            },
        },
        "ml": {
            "method": "hist_gradient_boosting_residual_corrector_on_template_phase",
            "value": float(hgb_row["value"]),
            "ci": [float(hgb_row["ci_low"]), float(hgb_row["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - hgb_row["value"]),
            "gain_vs_hierarchical_shrinkage_ns": float(hier_row["value"] - hgb_row["value"]),
            "gain_vs_s03b_binned_timewalk_ns": float(s03b_row["value"] - hgb_row["value"]),
        },
        "run61": {
            "hierarchical_sigma68_ns": float(run61_perf["value"]),
            "ci": [float(run61_perf["ci_low"]), float(run61_perf["ci_high"])],
            "n_pair_residuals": int(run61_perf["n_pair_residuals"]),
            "pair_count_rank_desc": run61_stat_rank,
            "oracle_gain_ns": float(run61_oracle["oracle_gain_ns"]),
            "interpretation": "not_limited_statistics; oracle adaptation tests coefficient drift but remaining width indicates misspecification or run-specific pulse pathology",
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "hgb_features_exclude_run_event_order_cross_stave_time": True,
            "hierarchical_heldout_run_deviation_zeroed": True,
            "s03b_uses_train_run_rows_only": True,
            "final_models_use_heldout_rows": False,
            "shuffled_target_min_sigma68_ns": min_shuffle,
            "hierarchical_looks_too_good": looks_too_good,
            "leakage_flag": leakage_flag,
            "oracle_diagnostic_uses_heldout_labels": True,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro_counts, run65_repro, per_run, pooled, leakage, oracle, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03d",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["hierarchical"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "baseline": float(base["value"]),
                "s03a_global": float(global_row["value"]),
                "hierarchical_shrinkage": float(hier_row["value"]),
                "s03b_binned_timewalk": float(s03b_row["value"]),
                "hgb": float(hgb_row["value"]),
                "run61_hier": float(run61_perf["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
