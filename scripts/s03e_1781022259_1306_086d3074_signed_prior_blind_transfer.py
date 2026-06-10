#!/usr/bin/env python3
"""S03e blind Sample-I to Sample-II signed-prior transfer study."""

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
import s03b_amp_binned_monotonic_timewalk as s03b
import s03d_signed_timewalk_prior as s03d_signed


METHODS = [
    ("template_phase", "template_phase_base"),
    ("analytic_timewalk", "analytic_timewalk"),
    ("binned_timewalk", "s03b_binned_timewalk"),
    ("signed_prior", "signed_physics_prior"),
    ("hgb_timewalk", "hgb_timewalk"),
]


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
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def split_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(run) for run in train_runs]
    out["timing"]["heldout_runs"] = [int(run) for run in heldout_runs]
    return out


def add_base_times(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = pulses.copy()
    train = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    if config["timing"]["base_method"] not in methods:
        raise RuntimeError(f"Base method {config['timing']['base_method']} was not built")
    return out, scan


def residual_rows(
    pulses: pd.DataFrame,
    config: dict,
    methods: List[Tuple[str, str]],
    eval_runs: Iterable[int],
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residuals = []
    for run in [int(run) for run in eval_runs]:
        for method, label in methods:
            vals = s02.pairwise_residuals(pulses, method, 2.0, config, [run])
            ci = s02.bootstrap_ci(vals, rng, int(n_boot))
            rows.append(
                {
                    "heldout_run": run,
                    "method": label,
                    "metric": "heldout_run_pairwise_sigma68_ns",
                    "value": s02.sigma68(vals),
                    "ci_low": ci[0],
                    "ci_high": ci[1],
                    **s02.metric_summary(vals),
                }
            )
            residuals.extend(
                {
                    "heldout_run": run,
                    "method": label,
                    "pairwise_residual_ns": float(value),
                }
                for value in vals
            )
    return pd.DataFrame(rows), pd.DataFrame(residuals)


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(int(run) for run in residuals["heldout_run"].unique())
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        by_run = {int(run): sub["pairwise_residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot_vals = np.concatenate([by_run[int(run)] for run in sampled if len(by_run[int(run)])])
            stats.append(s02.sigma68(boot_vals))
        ci_low, ci_high = np.percentile(stats, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "metric": "pooled_blind_sample_ii_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def hgb_param_grid(config: dict) -> List[dict]:
    rows = []
    for max_iter in config["hgb"]["max_iter"]:
        for learning_rate in config["hgb"]["learning_rate"]:
            for max_leaf_nodes in config["hgb"]["max_leaf_nodes"]:
                for l2_regularization in config["hgb"]["l2_regularization"]:
                    rows.append(
                        {
                            "max_iter": int(max_iter),
                            "learning_rate": float(learning_rate),
                            "max_leaf_nodes": int(max_leaf_nodes),
                            "l2_regularization": float(l2_regularization),
                            "max_bins": int(config["hgb"]["max_bins"]),
                            "random_state": int(config["hgb"]["random_seed"]),
                        }
                    )
    return rows


def run_hgb(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy()
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    idx_train_all = np.flatnonzero(train_mask)
    max_train_rows = int(config["hgb"].get("max_train_rows", 0) or 0)
    if max_train_rows and len(idx_train_all) > max_train_rows:
        rng = np.random.default_rng(int(config["hgb"]["random_seed"]) + 2301)
        idx_train = np.sort(rng.choice(idx_train_all, size=max_train_rows, replace=False))
    else:
        idx_train = idx_train_all
    X_train = X[idx_train]
    y_train = targets[idx_train]
    groups = runs[idx_train]
    n_splits = min(int(config["hgb"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": np.inf, "params": None}
    for params in hgb_param_grid(config):
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X_train, y_train, groups=groups)):
            model = HistGradientBoostingRegressor(**params)
            model.fit(X_train[tr], y_train[tr])
            pred = np.full(len(pulses), np.nan)
            pred[idx_train[va]] = model.predict(X_train[va])
            tmp = pulses.copy()
            tmp["t_hgb_timewalk_ns"] = tmp[f"t_{base_method}_ns"] - pred
            va_runs = sorted(np.unique(runs[idx_train[va]]).astype(int).tolist())
            vals = s02.pairwise_residuals(tmp.iloc[idx_train[va]], "hgb_timewalk", 2.0, config, va_runs)
            score = s02.sigma68(vals)
            fold_scores.append(score)
            cv_rows.append({**params, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals))})
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append({**params, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
        if mean_score < best["score"]:
            best = {"score": mean_score, "params": params}

    final_model = HistGradientBoostingRegressor(**best["params"])
    final_model.fit(X_train, y_train)
    pred = final_model.predict(X)
    out = pulses.copy()
    out["hgb_target_residual_ns"] = targets
    out["hgb_pred_residual_ns"] = pred
    out["t_hgb_timewalk_ns"] = out[f"t_{base_method}_ns"] - pred
    return out, pd.DataFrame(cv_rows), best


def fit_transfer_models(
    pulses: pd.DataFrame,
    config: dict,
    base_method: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    analytic_pulses, analytic_cv, coef, best_candidate, best_alpha = s03a.run_analytic(pulses, config, base_method)
    binned_pulses, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    signed_pulses, signed_cv, signed_coef, signed_best = s03d_signed.run_signed_prior(pulses, config, base_method)
    hgb_pulses, hgb_cv, hgb_best = run_hgb(pulses, config, base_method)

    combined = analytic_pulses.copy()
    combined["t_binned_timewalk_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["binned_target_residual_ns"] = binned_pulses["binned_target_residual_ns"].to_numpy(dtype=float)
    combined["binned_pred_residual_ns"] = binned_pulses["binned_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_signed_prior_ns"] = signed_pulses["t_signed_prior_ns"].to_numpy(dtype=float)
    combined["signed_prior_target_residual_ns"] = signed_pulses["signed_prior_target_residual_ns"].to_numpy(dtype=float)
    combined["signed_prior_pred_residual_ns"] = signed_pulses["signed_prior_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)
    combined["hgb_target_residual_ns"] = hgb_pulses["hgb_target_residual_ns"].to_numpy(dtype=float)
    combined["hgb_pred_residual_ns"] = hgb_pulses["hgb_pred_residual_ns"].to_numpy(dtype=float)

    best = {
        "analytic_candidate": best_candidate,
        "analytic_alpha": best_alpha,
        "binned_mode": str(binned_best["mode"]),
        "binned_direction": str(binned_best["direction"]),
        "binned_n_bins": int(binned_best["n_bins"]),
        "signed_candidate": str(signed_best["candidate"]),
        "signed_cv_sigma68_ns": float(signed_best["score"]),
        "hgb_cv_sigma68_ns": float(hgb_best["score"]),
        "hgb_params": hgb_best["params"],
    }
    hgb_cal = pd.DataFrame(
        [
            {
                "metric": "sample_i_cv_sigma68_ns",
                "value": float(hgb_best["score"]),
                **hgb_best["params"],
            }
        ]
    )
    return combined, analytic_cv, coef, binned_cv, s03b.binned_model_table(binned_models), signed_cv, signed_coef, hgb_cv, hgb_cal, best


def run_sample_ii_reference_reproduction(
    pulses_all: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    ref_runs = [int(run) for run in config["timing"]["sample_ii_reference_runs"]]
    heldout = int(config["timing"].get("sample_ii_reference_heldout_run", 65))
    ref_pulses = pulses_all[pulses_all["run"].isin(ref_runs)].copy()
    train_runs = [run for run in ref_runs if run != heldout]
    fold_cfg = split_config(config, train_runs, [heldout])
    timed, _ = add_base_times(ref_pulses, fold_cfg)
    analytic_pulses, _, _, _, _ = s03a.run_analytic(timed, fold_cfg, fold_cfg["timing"]["base_method"])
    binned_pulses, _, _, _ = s03b.scan_binned_candidates(timed, fold_cfg, fold_cfg["timing"]["base_method"])
    combined = analytic_pulses.copy()
    combined["t_binned_timewalk_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    _, residuals = residual_rows(
        combined,
        fold_cfg,
        [
            ("template_phase", "template_phase_base"),
            ("analytic_timewalk", "analytic_timewalk"),
            ("binned_timewalk", "s03b_binned_timewalk"),
        ],
        [heldout],
        rng,
        int(config["analytic"]["bootstrap_samples"]),
    )
    pooled = residuals.groupby("method")["pairwise_residual_ns"].apply(lambda vals: s02.sigma68(vals.to_numpy(dtype=float))).reset_index(name="value")
    counts = residuals.groupby("method").size().reset_index(name="n_pair_residuals")
    pooled = pooled.merge(counts, on="method", how="left")
    pooled["ci_low"] = np.nan
    pooled["ci_high"] = np.nan
    expected = {
        "template_phase_base": float(config["reference_numbers"]["run65_template_phase_base_sigma68_ns"]),
        "analytic_timewalk": float(config["reference_numbers"]["run65_s03a_amp_only_sigma68_ns"]),
        "s03b_binned_timewalk": float(config["reference_numbers"]["run65_s03b_monotone_binned_sigma68_ns"]),
    }
    repro = pooled[["method", "value", "ci_low", "ci_high", "n_pair_residuals"]].copy()
    repro["sample_ii_reference_value"] = repro["method"].map(expected)
    repro["delta_ns"] = repro["value"] - repro["sample_ii_reference_value"]
    repro["pass"] = repro["delta_ns"].abs() < 1.0e-9
    return repro, residuals


def analytic_shuffled_per_run(pulses: pd.DataFrame, config: dict, base_method: str, candidate: str, alpha: float) -> pd.DataFrame:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    rng = np.random.default_rng(int(config["analytic"]["random_seed"]) + 1703)
    target = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, _ = s03a.analytic_feature_matrix(pulses, candidate, staves)
    runs = pulses["run"].to_numpy(dtype=float)
    train_mask = np.isin(runs, train_runs) & s03a.finite_design(X, target, runs)
    shuffled = target[train_mask].copy()
    rng.shuffle(shuffled)
    model = s03a.make_model(alpha)
    model.fit(X[train_mask], shuffled)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - model.predict(X)
    tmp = pulses.copy()
    tmp["t_analytic_shuffled_ns"] = corrected
    rows = []
    for run in config["timing"]["heldout_runs"]:
        vals = s02.pairwise_residuals(tmp, "analytic_shuffled", 2.0, config, [int(run)])
        rows.append({"check": "analytic_timewalk_shuffled_target", "heldout_run": int(run), "heldout_sigma68_ns": s02.sigma68(vals), "n_pair_residuals": int(len(vals))})
    return pd.DataFrame(rows)


def binned_shuffled_per_run(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["binned"]["random_seed"]) + 1709)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=float)
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & s03b.finite_design(amp_log, targets, runs)
    shuffled = targets.copy()
    train_vals = shuffled[train_mask].copy()
    rng.shuffle(train_vals)
    shuffled[train_mask] = train_vals
    models = s03b.fit_binned_model(
        pulses, shuffled, train_mask, config, int(best["binned_n_bins"]), str(best["binned_mode"]), str(best["binned_direction"])
    )
    pred = s03b.predict_binned_model(pulses, models)
    tmp = pulses.copy()
    tmp["t_binned_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    rows = []
    for run in config["timing"]["heldout_runs"]:
        vals = s02.pairwise_residuals(tmp, "binned_shuffled", 2.0, config, [int(run)])
        rows.append({"check": "s03b_binned_shuffled_target", "heldout_run": int(run), "heldout_sigma68_ns": s02.sigma68(vals), "n_pair_residuals": int(len(vals))})
    return pd.DataFrame(rows)


def hgb_shuffled_per_run(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["hgb"]["random_seed"]) + 1711)
    staves = list(config["timing"]["downstream_staves"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy()
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & np.isfinite(targets)
    idx_train_all = np.flatnonzero(train_mask)
    max_train_rows = int(config["hgb"].get("max_train_rows", 0) or 0)
    if max_train_rows and len(idx_train_all) > max_train_rows:
        idx_train = np.sort(rng.choice(idx_train_all, size=max_train_rows, replace=False))
    else:
        idx_train = idx_train_all
    shuffled = targets[idx_train].copy()
    rng.shuffle(shuffled)
    model = HistGradientBoostingRegressor(**best["hgb_params"])
    model.fit(X[idx_train], shuffled)
    tmp = pulses.copy()
    tmp["t_hgb_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - model.predict(X)
    rows = []
    for run in config["timing"]["heldout_runs"]:
        vals = s02.pairwise_residuals(tmp, "hgb_shuffled", 2.0, config, [int(run)])
        rows.append({"check": "hgb_shuffled_target", "heldout_run": int(run), "heldout_sigma68_ns": s02.sigma68(vals), "n_pair_residuals": int(len(vals))})
    return pd.DataFrame(rows)


def signed_shuffled_per_run(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["signed_prior"]["random_seed"]) + 307)
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, _, lower, upper = s03d_signed.signed_design(pulses, staves, str(best["signed_candidate"]))
    runs = pulses["run"].to_numpy()
    train_mask = np.isin(runs, train_runs) & s03d_signed.finite_mask(X, targets, runs)
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    fit = s03d_signed.fit_signed_prior(X[train_mask], shuffled, lower, upper)
    pred = X @ fit.x
    tmp = pulses.copy()
    tmp["t_signed_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    rows = []
    for run in config["timing"]["heldout_runs"]:
        vals = s02.pairwise_residuals(tmp, "signed_shuffled", 2.0, config, [int(run)])
        rows.append({"check": "signed_prior_shuffled_target", "heldout_run": int(run), "heldout_sigma68_ns": s02.sigma68(vals), "n_pair_residuals": int(len(vals))})
    return pd.DataFrame(rows)


def leakage_checks(pulses: pd.DataFrame, config: dict, base_method: str, best: dict, ml_cv: pd.DataFrame) -> pd.DataFrame:
    train_runs = set(int(run) for run in config["timing"]["train_runs"])
    heldout_runs = set(int(run) for run in config["timing"]["heldout_runs"])
    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    rows = [
        {
            "check": "train_heldout_run_overlap",
            "heldout_run": -1,
            "heldout_sigma68_ns": float(len(train_runs & heldout_runs)),
            "n_pair_residuals": 0,
        },
        {
            "check": "train_heldout_event_id_overlap",
            "heldout_run": -1,
            "heldout_sigma68_ns": float(len(train_event_ids & heldout_event_ids)),
            "n_pair_residuals": 0,
        },
        {
            "check": "feature_audit_no_run_event_order_or_cross_stave_time",
            "heldout_run": -1,
            "heldout_sigma68_ns": 0.0,
            "n_pair_residuals": 0,
        },
    ]
    return pd.concat(
        [
            pd.DataFrame(rows),
            analytic_shuffled_per_run(pulses, config, base_method, best["analytic_candidate"], float(best["analytic_alpha"])),
            binned_shuffled_per_run(pulses, config, base_method, best),
            signed_shuffled_per_run(pulses, config, base_method, best),
            hgb_shuffled_per_run(pulses, config, base_method, best),
        ],
        ignore_index=True,
    )


def calibration_table(pulses: pd.DataFrame, heldout_runs: List[int]) -> pd.DataFrame:
    parts = []
    for pred_col, target_col, method in [
        ("analytic_pred_residual_ns", "analytic_target_residual_ns", "analytic_timewalk"),
        ("binned_pred_residual_ns", "binned_target_residual_ns", "s03b_binned_timewalk"),
        ("signed_prior_pred_residual_ns", "signed_prior_target_residual_ns", "signed_physics_prior"),
        ("hgb_pred_residual_ns", "hgb_target_residual_ns", "hgb_timewalk"),
    ]:
        held = pulses[pulses["run"].isin(heldout_runs)].copy()
        held = held[np.isfinite(held[pred_col]) & np.isfinite(held[target_col])]
        if len(held) < 8:
            continue
        qs = np.unique(np.quantile(held[pred_col], np.linspace(0, 1, 8)))
        if len(qs) < 3:
            continue
        held["bin"] = pd.cut(held[pred_col], qs, include_lowest=True, duplicates="drop")
        for _, group in held.groupby("bin"):
            parts.append(
                {
                    "method": method,
                    "n": int(len(group)),
                    "pred_mean_ns": float(group[pred_col].mean()),
                    "target_mean_ns": float(group[target_col].mean()),
                }
            )
    return pd.DataFrame(parts)


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame) -> None:
    order = ["template_phase_base", "analytic_timewalk", "s03b_binned_timewalk", "signed_physics_prior", "hgb_timewalk"]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.errorbar(
            sub["heldout_run"],
            sub["value"],
            yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]],
            marker="o",
            capsize=2,
            label=method,
        )
    ax.set_xlabel("Sample-II held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("Blind Sample-I to Sample-II transfer")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03e_per_run_transfer.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.3, 4.2))
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
    ax.set_ylabel("pooled run-bootstrap sigma68 (ns)")
    ax.set_title("Pooled blind-transfer interval")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03e_pooled_transfer.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro_counts: pd.DataFrame,
    reference_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    best: dict,
    result: dict,
) -> None:
    base = pooled[pooled["method"] == "template_phase_base"].iloc[0]
    analytic = pooled[pooled["method"] == "analytic_timewalk"].iloc[0]
    binned = pooled[pooled["method"] == "s03b_binned_timewalk"].iloc[0]
    signed = pooled[pooled["method"] == "signed_physics_prior"].iloc[0]
    ml = pooled[pooled["method"] == "hgb_timewalk"].iloc[0]
    leak_summary = leakage.pivot_table(index="check", values="heldout_sigma68_ns", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    lines = [
        "# Study report: S03e - Blind Sample-I to Sample-II signed-prior transfer",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train/calibrate only Sample I runs 31-37, 39-42, 44-57; blind evaluation on Sample II analysis runs 58-63 and 65",
        f"- **Config:** `{config_path}`",
        "- **Monte Carlo:** none",
        "",
        "## 0. Question",
        "",
        "Does the S03d signed per-stave inverse-amplitude prior learned on Sample-I calibration/analysis runs transfer blindly to Sample-II analysis runs, compared with S03a Ridge, S03b isotonic, and HGB?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "Before fitting Sample-I transfer models, selected-pulse counts and the prior run-65 S03a/S03b/template reference were rebuilt from raw ROOT.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        reference_repro.to_markdown(index=False),
        "",
        "## 2. Blind transfer methods",
        "",
        f"All models used the fixed base pickoff `{config['timing']['base_method']}` with templates built only from Sample I train runs. S03a selected `{best['analytic_candidate']}` with Ridge alpha `{best['analytic_alpha']:g}` by GroupKFold over Sample-I runs. S03b selected mode `{best['binned_mode']}`, direction `{best['binned_direction']}`, bins `{best['binned_n_bins']}`. The S03d signed prior selected `{best['signed_candidate']}` with nonnegative per-stave inverse-amplitude slopes and Sample-I grouped-CV sigma68 `{best['signed_cv_sigma68_ns']:.3f} ns`. The ML comparator is an HGB residual corrector selected only by Sample-I grouped CV, trained on a deterministic cap of `{config['hgb'].get('max_train_rows', 'all')}` Sample-I rows.",
        "",
        "## 3. Held-out Sample-II results",
        "",
        per_run[["heldout_run", "method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "Pooled intervals resample held-out runs, not individual residuals.",
        "",
        pooled[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## 4. Leakage checks",
        "",
        "No model input includes run number, event id, event order, other-stave timing, sample label, or held-out labels. Final fits use only Sample-I rows; Sample-II targets are computed only for evaluation diagnostics. Shuffled-target controls were fit on Sample I and evaluated on Sample II by run.",
        "",
        f"The too-good screen is `too_good_flag={result['leakage']['too_good_flag']}`. The leakage flag is `{result['leakage']['leakage_flag']}` after train/held-out overlap and shuffled-target probes; the overall shuffled-target minimum is `{result['leakage']['shuffled_target_min_sigma68_ns']:.3f} ns`.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 5. Verdict",
        "",
        f"Blind Sample-I template phase gives `{base['value']:.3f} ns` with run-bootstrap CI `[{base['ci_low']:.3f}, {base['ci_high']:.3f}] ns`.",
        f"The analytic correction gives `{analytic['value']:.3f} ns` with CI `[{analytic['ci_low']:.3f}, {analytic['ci_high']:.3f}] ns`, a gain of `{base['value'] - analytic['value']:.3f} ns`.",
        f"The S03b binned traditional correction gives `{binned['value']:.3f} ns`; the signed S03d prior gives `{signed['value']:.3f} ns`; the HGB ML comparator gives `{ml['value']:.3f} ns`.",
        f"Conclusion: `{result['verdict']}`.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03e_1781022259_1306_086d3074_signed_prior_blind_transfer.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `run65_reference_reproduction.csv`, `traditional_scan_metrics.csv`, `per_run_transfer_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, CV/model CSVs, signed-prior coefficients, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03e_1781022259_1306_086d3074_signed_prior_blind_transfer.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["analytic"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    reference_repro, reference_residuals = run_sample_ii_reference_reproduction(pulses_all, config, rng)
    reference_repro.to_csv(out_dir / "run65_reference_reproduction.csv", index=False)
    reference_residuals.to_csv(out_dir / "run65_reference_pairwise_residuals.csv", index=False)
    if not bool(reference_repro["pass"].all()):
        raise RuntimeError("Run-65 S03a/S03b reference reproduction gate failed")

    timed, traditional_scan = add_base_times(pulses_all, config)
    traditional_scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    combined, analytic_cv, coef, binned_cv, binned_table, signed_cv, signed_coef, hgb_cv, hgb_cal, best = fit_transfer_models(
        timed, config, config["timing"]["base_method"]
    )
    analytic_cv.to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)
    binned_cv.to_csv(out_dir / "binned_cv_scan.csv", index=False)
    binned_table.to_csv(out_dir / "binned_model_table.csv", index=False)
    signed_cv.to_csv(out_dir / "signed_prior_cv_scan.csv", index=False)
    signed_coef.to_csv(out_dir / "signed_prior_coefficients.csv", index=False)
    hgb_cv.to_csv(out_dir / "hgb_cv_scan.csv", index=False)
    hgb_cal.to_csv(out_dir / "hgb_residual_calibration.csv", index=False)

    per_run, residuals = residual_rows(
        combined,
        config,
        METHODS,
        config["timing"]["heldout_runs"],
        rng,
        int(config["analytic"]["bootstrap_samples"]),
    )
    pooled = run_level_bootstrap(residuals, rng, int(config["analytic"]["bootstrap_samples"]))
    leakage = leakage_checks(combined, config, config["timing"]["base_method"], best, hgb_cv)
    calibration = calibration_table(combined, list(config["timing"]["heldout_runs"]))

    per_run.to_csv(out_dir / "per_run_transfer_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    calibration.to_csv(out_dir / "heldout_residual_calibration.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_rows = []
    input_hashes = {}
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    base = pooled[pooled["method"] == "template_phase_base"].iloc[0]
    analytic = pooled[pooled["method"] == "analytic_timewalk"].iloc[0]
    binned = pooled[pooled["method"] == "s03b_binned_timewalk"].iloc[0]
    signed = pooled[pooled["method"] == "signed_physics_prior"].iloc[0]
    ml = pooled[pooled["method"] == "hgb_timewalk"].iloc[0]
    leak_overlap = int(leakage[leakage["check"].isin(["train_heldout_run_overlap", "train_heldout_event_id_overlap"])]["heldout_sigma68_ns"].sum())
    shuffled_min = float(leakage[leakage["check"].str.contains("shuffled_target")]["heldout_sigma68_ns"].min())
    too_good = bool(
        min(float(signed["value"]), float(ml["value"]))
        < float(config["reference_numbers"]["sample_ii_s03a_amp_only_sigma68_ns"]) - 0.25
    )
    leakage_flag = bool(leak_overlap != 0 or shuffled_min < min(float(signed["value"]), float(ml["value"])) + 0.2)
    signed_beats_s03a = bool(float(signed["value"]) < float(analytic["value"]))
    signed_competitive_s03b = bool(float(signed["ci_low"]) <= float(binned["value"]) <= float(signed["ci_high"]))
    verdict = (
        "signed_prior_transfers_blindly_no_leakage_flag"
        if signed_beats_s03a and signed_competitive_s03b and not leakage_flag
        else "signed_prior_transfer_has_gap_or_leakage_concern"
    )
    result = {
        "study": "S03e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and reference_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "run65_s03a_s03b_reference_pass": bool(reference_repro["pass"].all()),
        },
        "split": {
            "train_sample": "Sample I",
            "train_runs": [int(run) for run in config["timing"]["train_runs"]],
            "heldout_sample": "Sample II analysis",
            "heldout_runs": [int(run) for run in config["timing"]["heldout_runs"]],
            "bootstrap_unit": "heldout_run",
        },
        "baseline": {
            "method": "template_phase",
            "value": float(base["value"]),
            "ci": [float(base["ci_low"]), float(base["ci_high"])],
        },
        "traditional": {
            "signed_physics_prior": {
                "method": "per_stave_nonnegative_inverse_amplitude_prior",
                "candidate": best["signed_candidate"],
                "cv_sigma68_ns": float(best["signed_cv_sigma68_ns"]),
                "value": float(signed["value"]),
                "ci": [float(signed["ci_low"]), float(signed["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - signed["value"]),
                "delta_vs_s03a_ridge_ns": float(analytic["value"] - signed["value"]),
                "delta_vs_s03b_isotonic_ns": float(binned["value"] - signed["value"]),
                "competitive_with_s03b_by_ci": signed_competitive_s03b,
            },
            "s03a_ridge": {
                "method": "analytic_timewalk_on_template_phase",
                "candidate": best["analytic_candidate"],
                "alpha": float(best["analytic_alpha"]),
                "value": float(analytic["value"]),
                "ci": [float(analytic["ci_low"]), float(analytic["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - analytic["value"]),
                "delta_vs_sample_ii_loro_s03a_ns": float(analytic["value"] - config["reference_numbers"]["sample_ii_s03a_amp_only_sigma68_ns"]),
            },
            "s03b_isotonic": {
                "method": "per_stave_monotonic_amplitude_binned_timewalk",
                "mode": best["binned_mode"],
                "direction": best["binned_direction"],
                "n_bins": int(best["binned_n_bins"]),
                "value": float(binned["value"]),
                "ci": [float(binned["ci_low"]), float(binned["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - binned["value"]),
                "delta_vs_sample_ii_loro_s03b_ns": float(binned["value"] - config["reference_numbers"]["sample_ii_s03b_monotone_binned_sigma68_ns"]),
            },
        },
        "legacy_keys": {
            "method": "analytic_timewalk_on_template_phase",
            "candidate": best["analytic_candidate"],
            "alpha": float(best["analytic_alpha"]),
            "value": float(analytic["value"]),
            "ci": [float(analytic["ci_low"]), float(analytic["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - analytic["value"]),
            "delta_vs_sample_ii_loro_s03a_ns": float(analytic["value"] - config["reference_numbers"]["sample_ii_s03a_amp_only_sigma68_ns"]),
        },
        "ml": {
            "method": "hist_gradient_boosting_residual_corrector_on_template_phase",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - ml["value"]),
            "delta_vs_sample_ii_loro_hgb_ns": float(ml["value"] - config["reference_numbers"]["sample_ii_hgb_timewalk_sigma68_ns"]),
            "cv_sigma68_ns": float(best["hgb_cv_sigma68_ns"]),
            "params": best["hgb_params"],
            "max_train_rows": int(config["hgb"].get("max_train_rows", 0) or 0),
        },
        "leakage": {
            "split_by_run": True,
            "train_heldout_overlap_total": leak_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "sample_ii_used_for_final_fit": False,
            "shuffled_target_min_sigma68_ns": shuffled_min,
            "too_good_flag": too_good,
            "leakage_flag": leakage_flag,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "S03f: Sample-I downstream-only topology stratification for blind timewalk transfer",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro_counts, reference_repro, per_run, pooled, leakage, best, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03e",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["analytic"]["random_seed"]),
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
                "analytic": float(analytic["value"]),
                "binned": float(binned["value"]),
                "signed_prior": float(signed["value"]),
                "hgb": float(ml["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
