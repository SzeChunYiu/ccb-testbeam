#!/usr/bin/env python3
"""S03f hierarchical shrinkage for signed inverse-amplitude timewalk scales."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
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
from scipy.optimize import lsq_linear
from sklearn.model_selection import GroupKFold

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b
import s03d_leave_one_run_s03ab_hgb_stability as s03d
import s03d_phys_signed_prior as s03d_phys


RUN65_EXPECTED = {
    "template_phase_base": 2.889152765080617,
    "s03a_amp_only": 1.494640076269676,
    "s03b_monotone_binned": 1.5695763825403084,
}

S03D_POOLED_EXPECTED = {
    "template_phase_base": 2.7414145300852155,
    "s03a_amp_only": 1.5510917109777833,
    "s03b_monotone_binned": 1.6451494274970766,
    "phys_signed_inverse_amp": 1.6043573218297749,
    "hgb_timewalk": 1.3929711020483486,
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


def inverse_amp_feature(pulses: pd.DataFrame, config: dict, power: float) -> np.ndarray:
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    scale = float(config["phys_prior"]["inverse_amp_scale_adc"])
    return np.power(scale / amp, float(power))


def hierarchical_columns(staves: List[str], train_runs: List[int]) -> Tuple[Dict[str, int], List[str], np.ndarray, np.ndarray]:
    names: List[str] = []
    idx: Dict[str, int] = {}

    for stave in staves:
        idx[f"intercept:{stave}"] = len(names)
        names.append(f"intercept_{stave}")
    for run in train_runs[1:]:
        idx[f"run_offset:{run}"] = len(names)
        names.append(f"run_offset_{run}")

    idx["slope:global"] = len(names)
    names.append("slope_global")
    for stave in staves:
        idx[f"slope_stave:{stave}"] = len(names)
        names.append(f"slope_stave_{stave}")
    for run in train_runs:
        for stave in staves:
            idx[f"slope_run_stave:{run}:{stave}"] = len(names)
            names.append(f"slope_run_{run}_{stave}")

    lower = np.full(len(names), -np.inf, dtype=float)
    upper = np.full(len(names), np.inf, dtype=float)
    for key, col in idx.items():
        if key.startswith("slope:") or key.startswith("slope_stave:") or key.startswith("slope_run_stave:"):
            lower[col] = 0.0
    return idx, names, lower, upper


def build_hierarchical_system(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    power: float,
    shrink_lambda: float,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, int], List[str], np.ndarray, np.ndarray, List[int]]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = sorted(int(r) for r in np.unique(pulses.loc[train_mask, "run"].to_numpy(dtype=int)))
    idx, names, lower, upper = hierarchical_columns(staves, train_runs)
    x = inverse_amp_feature(pulses, config, power)
    stave_arr = pulses["stave"].to_numpy()
    run_arr = pulses["run"].to_numpy(dtype=int)
    fit_idx = np.flatnonzero(train_mask & np.isfinite(targets) & np.isfinite(x))

    X = np.zeros((len(fit_idx), len(names)), dtype=float)
    for row, pulse_i in enumerate(fit_idx):
        stave = str(stave_arr[pulse_i])
        run = int(run_arr[pulse_i])
        X[row, idx[f"intercept:{stave}"]] = 1.0
        if f"run_offset:{run}" in idx:
            X[row, idx[f"run_offset:{run}"]] = 1.0
        X[row, idx[f"slope_run_stave:{run}:{stave}"]] = x[pulse_i]
    y = targets[fit_idx].astype(float)

    penalty_rows: List[np.ndarray] = []
    penalty_y: List[float] = []
    lam = float(shrink_lambda)
    if lam > 0.0:
        w = math.sqrt(lam)
        for run in train_runs:
            for stave in staves:
                row = np.zeros(len(names), dtype=float)
                row[idx[f"slope_run_stave:{run}:{stave}"]] = w
                row[idx[f"slope_stave:{stave}"]] = -w
                penalty_rows.append(row)
                penalty_y.append(0.0)
        for stave in staves:
            row = np.zeros(len(names), dtype=float)
            row[idx[f"slope_stave:{stave}"]] = w
            row[idx["slope:global"]] = -w
            penalty_rows.append(row)
            penalty_y.append(0.0)

    run_l2 = float(config["hierarchical"].get("run_offset_l2", 0.0))
    if run_l2 > 0.0:
        w = math.sqrt(run_l2)
        for run in train_runs[1:]:
            row = np.zeros(len(names), dtype=float)
            row[idx[f"run_offset:{run}"]] = w
            penalty_rows.append(row)
            penalty_y.append(0.0)

    if penalty_rows:
        X = np.vstack([X, np.vstack(penalty_rows)])
        y = np.concatenate([y, np.asarray(penalty_y, dtype=float)])

    return X, y, idx, names, lower, upper, train_runs


def fit_hierarchical_model(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    power: float,
    shrink_lambda: float,
) -> dict:
    X, y, idx, names, lower, upper, train_runs = build_hierarchical_system(
        pulses, targets, train_mask, config, power, shrink_lambda
    )
    fit = lsq_linear(X, y, bounds=(lower, upper), method="trf", lsmr_tol="auto", max_iter=2000)
    return {
        "coef": fit.x,
        "idx": idx,
        "names": names,
        "lower": lower,
        "upper": upper,
        "train_runs": train_runs,
        "power": float(power),
        "shrink_lambda": float(shrink_lambda),
        "cost": float(fit.cost),
        "status": int(fit.status),
    }


def predict_hierarchical(pulses: pd.DataFrame, config: dict, model: dict, use_run_slopes: bool = False) -> np.ndarray:
    idx = model["idx"]
    coef = model["coef"]
    x = inverse_amp_feature(pulses, config, float(model["power"]))
    stave_arr = pulses["stave"].to_numpy()
    run_arr = pulses["run"].to_numpy(dtype=int)
    pred = np.full(len(pulses), np.nan, dtype=float)
    for i, (stave_raw, run) in enumerate(zip(stave_arr, run_arr)):
        stave = str(stave_raw)
        value = coef[idx[f"intercept:{stave}"]]
        if f"run_offset:{int(run)}" in idx:
            value += coef[idx[f"run_offset:{int(run)}"]]
        slope_key = f"slope_run_stave:{int(run)}:{stave}"
        if use_run_slopes and slope_key in idx:
            slope = coef[idx[slope_key]]
        else:
            slope = coef[idx[f"slope_stave:{stave}"]]
        pred[i] = value + slope * x[i]
    return pred


def hierarchical_model_table(model: dict) -> pd.DataFrame:
    rows = []
    for name, value, lower in zip(model["names"], model["coef"], model["lower"]):
        rows.append(
            {
                "feature": name,
                "coefficient": float(value),
                "lower_bound": float(lower) if np.isfinite(lower) else "",
                "at_positive_bound": bool(np.isfinite(lower) and lower == 0.0 and np.isclose(value, 0.0)),
                "power": float(model["power"]),
                "shrink_lambda": float(model["shrink_lambda"]),
                "fit_status": int(model["status"]),
            }
        )
    return pd.DataFrame(rows)


def evaluate_corrected(
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
    pulses: pd.DataFrame, config: dict, base_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame, dict]:
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = list(config["timing"]["train_runs"])
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    groups = runs[train_mask]
    idx_train = np.flatnonzero(train_mask)
    n_splits = min(int(config["hierarchical"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": math.inf, "power": None, "shrink_lambda": None}

    for power in config["hierarchical"]["powers"]:
        for shrink_lambda in config["hierarchical"]["shrink_lambdas"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(idx_train, targets[train_mask], groups=groups)):
                fold_mask = np.zeros(len(pulses), dtype=bool)
                fold_mask[idx_train[tr]] = True
                model = fit_hierarchical_model(pulses, targets, fold_mask, config, float(power), float(shrink_lambda))
                pred = predict_hierarchical(pulses, config, model, use_run_slopes=False)
                corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
                va_idx = idx_train[va]
                va_runs = sorted(np.unique(runs[va_idx]).astype(int).tolist())
                vals = evaluate_corrected(pulses.iloc[va_idx].copy(), "hierarchical_cv", corrected[va_idx], config, va_runs)
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "power": float(power),
                        "shrink_lambda": float(shrink_lambda),
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": int(len(vals)),
                        "fit_status": int(model["status"]),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "power": float(power),
                    "shrink_lambda": float(shrink_lambda),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                    "fit_status": 0,
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "power": float(power), "shrink_lambda": float(shrink_lambda)}

    model = fit_hierarchical_model(
        pulses, targets, train_mask, config, float(best["power"]), float(best["shrink_lambda"])
    )
    pred = predict_hierarchical(pulses, config, model, use_run_slopes=False)
    out = pulses.copy()
    out["hierarchical_target_residual_ns"] = targets
    out["hierarchical_pred_residual_ns"] = pred
    out["t_hierarchical_signed_ns"] = out[f"t_{base_method}_ns"] - pred
    return out, pd.DataFrame(cv_rows), model, hierarchical_model_table(model), best


def run_hierarchical_shuffled_control(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> float:
    rng = np.random.default_rng(int(config["hierarchical"]["random_seed"]) + 709)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & np.isfinite(targets)
    shuffled = targets.copy()
    shuffled_train = shuffled[train_mask].copy()
    rng.shuffle(shuffled_train)
    shuffled[train_mask] = shuffled_train
    model = fit_hierarchical_model(
        pulses, shuffled, train_mask, config, float(best["power"]), float(best["shrink_lambda"])
    )
    pred = predict_hierarchical(pulses, config, model, use_run_slopes=False)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    vals = evaluate_corrected(
        pulses, "hierarchical_shuffled", corrected, config, list(config["timing"]["heldout_runs"])
    )
    return s02.sigma68(vals)


def bootstrap_rows(
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
            {"heldout_run": heldout_run, "method": label, "pairwise_residual_ns": float(value)}
            for value in vals
        )
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, config)

    s03a_pulses, s03a_cv, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    binned_pulses, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    phys_pulses, phys_cv, phys_models, phys_best = s03d_phys.scan_signed_prior(pulses, config, base_method)
    hier_pulses, hier_cv, _, hier_table, hier_best = scan_hierarchical(pulses, config, base_method)
    hgb_pulses, hgb_cv, hgb_best = s03d.run_hgb(pulses, config, base_method)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["t_phys_signed_inverse_amp_ns"] = phys_pulses["t_signed_prior_ns"].to_numpy(dtype=float)
    combined["t_hierarchical_signed_ns"] = hier_pulses["t_hierarchical_signed_ns"].to_numpy(dtype=float)
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only"),
            ("s03b_monotone_binned", "s03b_monotone_binned"),
            ("phys_signed_inverse_amp", "phys_signed_inverse_amp"),
            ("hierarchical_signed", "hierarchical_signed_shrinkage"),
            ("hgb_timewalk", "hgb_timewalk"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["s03a_candidate"] = s03a_candidate
    benchmark["s03a_alpha"] = s03a_alpha
    benchmark["s03b_mode"] = binned_best["mode"]
    benchmark["s03b_direction"] = binned_best["direction"]
    benchmark["s03b_n_bins"] = binned_best["n_bins"]
    benchmark["phys_signed_power"] = phys_best["power"]
    benchmark["phys_signed_cv_sigma68_ns"] = phys_best["score"]
    benchmark["hier_power"] = hier_best["power"]
    benchmark["hier_shrink_lambda"] = hier_best["shrink_lambda"]
    benchmark["hier_cv_sigma68_ns"] = hier_best["score"]
    benchmark["hgb_cv_sigma68_ns"] = hgb_best["score"]

    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(combined[combined["run"].isin([heldout_run])]["event_id"])
    leakage = pd.DataFrame(
        [
            {"heldout_run": heldout_run, "check": "train_heldout_event_id_overlap", "value": float(len(train_event_ids & heldout_event_ids)), "unit": "events"},
            {"heldout_run": heldout_run, "check": "phys_signed_shuffled_target_sigma68", "value": s03d_phys.run_signed_prior_shuffled_control(pulses, config, base_method, phys_best), "unit": "ns"},
            {"heldout_run": heldout_run, "check": "hierarchical_shuffled_target_sigma68", "value": run_hierarchical_shuffled_control(pulses, config, base_method, hier_best), "unit": "ns"},
            {"heldout_run": heldout_run, "check": "s03b_shuffled_target_sigma68", "value": s03b.run_shuffled_binned_control(pulses, config, base_method, binned_best), "unit": "ns"},
            {"heldout_run": heldout_run, "check": "hgb_shuffled_target_sigma68", "value": s03d.run_hgb_shuffled_control(pulses, config, base_method, hgb_best), "unit": "ns"},
            {"heldout_run": heldout_run, "check": "features_exclude_run_event_order_cross_stave_time", "value": 1.0, "unit": "bool"},
            {"heldout_run": heldout_run, "check": "final_models_use_heldout_rows", "value": 0.0, "unit": "bool"},
        ]
    )

    for frame in [s03a_cv, binned_cv, phys_cv, hier_cv, hgb_cv]:
        frame["heldout_run"] = heldout_run
    phys_table = s03d_phys.signed_prior_table(phys_models)
    phys_table["heldout_run"] = heldout_run
    hier_table["heldout_run"] = heldout_run
    binned_table = s03b.binned_model_table(binned_models)
    binned_table["heldout_run"] = heldout_run
    return benchmark, residuals, leakage, s03a_cv, binned_cv, phys_cv, hier_cv, hgb_cv, phys_table, hier_table


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


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, hier_table: pd.DataFrame) -> None:
    order = [
        "template_phase_base",
        "s03a_amp_only",
        "s03b_monotone_binned",
        "phys_signed_inverse_amp",
        "hierarchical_signed_shrinkage",
        "hgb_timewalk",
    ]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03f run-held-out timing width")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    sub = pooled.set_index("method").loc[order].reset_index()
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    xpos = np.arange(len(sub))
    ax.bar(xpos, sub["value"])
    ax.errorbar(xpos, sub["value"], yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(xpos)
    ax.set_xticklabels(sub["method"], rotation=25, ha="right")
    ax.set_ylabel("pooled LORO sigma68 (ns)")
    ax.set_title("Held-out run bootstrap interval")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_pooled_run_bootstrap.png", dpi=130)
    plt.close(fig)

    slope = hier_table[hier_table["feature"].str.startswith("slope_stave_")].copy()
    if len(slope):
        slope["stave"] = slope["feature"].str.replace("slope_stave_", "", regex=False)
        fig, ax = plt.subplots(figsize=(8.6, 4.4))
        for stave, sub in slope.groupby("stave"):
            ax.plot(sub["heldout_run"], sub["coefficient"], "o-", label=stave)
        ax.set_xlabel("held-out run")
        ax.set_ylabel("pooled nonnegative slope")
        ax.set_title("Hierarchical stave slopes used for unseen runs")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "fig_s03f_hierarchical_stave_slopes.png", dpi=130)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro_counts: pd.DataFrame,
    run65_repro: pd.DataFrame,
    s03d_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    phys_table: pd.DataFrame,
    hier_table: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    ordered = [
        "template_phase_base",
        "s03a_amp_only",
        "s03b_monotone_binned",
        "phys_signed_inverse_amp",
        "hierarchical_signed_shrinkage",
        "hgb_timewalk",
    ]
    pooled_view = pooled.set_index("method").loc[ordered].reset_index()
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    phys_b4 = phys_table[(phys_table["stave"] == "B4")][["heldout_run", "signed_slope_ns", "unconstrained_slope_ns", "slope_clipped_to_physical_sign"]]
    hier_stave = hier_table[hier_table["feature"].str.startswith("slope_stave_")][["heldout_run", "feature", "coefficient", "at_positive_bound", "power", "shrink_lambda"]]
    lines = [
        "# Study report: S03f - Hierarchical signed shrinkage",
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
        "Does partial pooling of physically signed inverse-amplitude slopes across staves and train runs rescue the B4 zero-slope clipping seen in S03d and improve the broad held-out run 61 without leakage?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun from raw ROOT before any model fitting.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "The S03a/S03b run-65 reference numbers and the prior S03d pooled headline were reproduced from the same raw-derived pulse table before accepting S03f.",
        "",
        run65_repro.to_markdown(index=False),
        "",
        s03d_repro.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "The S03f traditional method fits per-stave intercepts, train-run offsets, and nonnegative inverse-amplitude slopes. Run/stave slopes are shrunk toward pooled stave slopes, which are shrunk toward a global signed slope; held-out runs never get run-specific slope terms and use only the pooled stave slope. Power and shrinkage strength are chosen by grouped train-run CV.",
        "",
        "S03d B4 per-fold signed slopes:",
        "",
        phys_b4.to_markdown(index=False),
        "",
        "S03f pooled stave slopes used for unseen held-out runs:",
        "",
        hier_stave.to_markdown(index=False),
        "",
        "## 3. Run-held-out head-to-head",
        "",
        per_run[[
            "heldout_run",
            "method",
            "value",
            "ci_low",
            "ci_high",
            "n_pair_residuals",
            "phys_signed_power",
            "hier_power",
            "hier_shrink_lambda",
            "hier_cv_sigma68_ns",
            "hgb_cv_sigma68_ns",
        ]].sort_values(["heldout_run", "method"]).to_markdown(index=False),
        "",
        pooled_view[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## 4. Leakage checks",
        "",
        "All model selection is grouped by run. Final models are trained with the held-out run removed. Features exclude run number, event id, event order, other-stave timing, and held-out labels; run offsets are fit only for train runs and are unavailable to held-out runs.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 5. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"Hierarchical signed shrinkage pooled sigma68 is `{result['traditional']['hierarchical_signed_shrinkage']['value']:.3f} ns`; S03d signed prior is `{result['traditional']['phys_signed_inverse_amp']['value']:.3f} ns`; S03b is `{result['traditional']['s03b_monotone_binned']['value']:.3f} ns`; HGB is `{result['ml']['value']:.3f} ns`.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03f_1781020977_1287_077c1595_hierarchical_signed_shrinkage.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `s03d_headline_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, CV scans, model tables, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03f_hierarchical_signed_shrinkage_1781020977.yaml")
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

    run65_bench, _, _, _, _, _, _, _, _, _ = run_one_fold(pulses_all, config, 65, all_runs, rng)
    run65_repro = run65_bench[run65_bench["method"].isin(RUN65_EXPECTED)].copy()
    run65_repro["reference_value"] = run65_repro["method"].map(RUN65_EXPECTED)
    run65_repro["delta"] = run65_repro["value"] - run65_repro["reference_value"]
    run65_repro["pass"] = run65_repro["delta"].abs() < 1.0e-9
    run65_repro[["method", "value", "reference_value", "delta", "pass"]].to_csv(out_dir / "run65_reproduction.csv", index=False)
    if not bool(run65_repro["pass"].all()):
        raise RuntimeError("S03a/S03b run-65 reproduction gate failed")

    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    s03a_cv_parts = []
    s03b_cv_parts = []
    phys_cv_parts = []
    hier_cv_parts = []
    hgb_cv_parts = []
    phys_table_parts = []
    hier_table_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, s03a_cv, s03b_cv, phys_cv, hier_cv, hgb_cv, phys_table, hier_table = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        s03a_cv_parts.append(s03a_cv)
        s03b_cv_parts.append(s03b_cv)
        phys_cv_parts.append(phys_cv)
        hier_cv_parts.append(hier_cv)
        hgb_cv_parts.append(hgb_cv)
        phys_table_parts.append(phys_table)
        hier_table_parts.append(hier_table)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    s03a_cv = pd.concat(s03a_cv_parts, ignore_index=True)
    s03b_cv = pd.concat(s03b_cv_parts, ignore_index=True)
    phys_cv = pd.concat(phys_cv_parts, ignore_index=True)
    hier_cv = pd.concat(hier_cv_parts, ignore_index=True)
    hgb_cv = pd.concat(hgb_cv_parts, ignore_index=True)
    phys_table = pd.concat(phys_table_parts, ignore_index=True)
    hier_table = pd.concat(hier_table_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["hierarchical"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    s03a_cv.to_csv(out_dir / "s03a_amp_only_cv_scan.csv", index=False)
    s03b_cv.to_csv(out_dir / "s03b_monotone_cv_scan.csv", index=False)
    phys_cv.to_csv(out_dir / "phys_signed_cv_scan.csv", index=False)
    hier_cv.to_csv(out_dir / "hierarchical_cv_scan.csv", index=False)
    hgb_cv.to_csv(out_dir / "hgb_cv_scan.csv", index=False)
    phys_table.to_csv(out_dir / "phys_signed_model_table.csv", index=False)
    hier_table.to_csv(out_dir / "hierarchical_model_table.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled, hier_table)

    s03d_repro = pooled[pooled["method"].isin(S03D_POOLED_EXPECTED)].copy()
    s03d_repro["reference_value"] = s03d_repro["method"].map(S03D_POOLED_EXPECTED)
    s03d_repro["delta"] = s03d_repro["value"] - s03d_repro["reference_value"]
    s03d_repro["tolerance"] = np.where(s03d_repro["method"] == "hgb_timewalk", 5.0e-3, 1.0e-9)
    s03d_repro["pass"] = s03d_repro["delta"].abs() <= s03d_repro["tolerance"]
    s03d_repro[["method", "value", "reference_value", "delta", "tolerance", "pass"]].to_csv(out_dir / "s03d_headline_reproduction.csv", index=False)
    if not bool(s03d_repro["pass"].all()):
        raise RuntimeError("Prior S03d pooled headline reproduction gate failed")

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    s03a_row = pooled_idx.loc["s03a_amp_only"]
    s03b_row = pooled_idx.loc["s03b_monotone_binned"]
    phys_row = pooled_idx.loc["phys_signed_inverse_amp"]
    hier_row = pooled_idx.loc["hierarchical_signed_shrinkage"]
    hgb_row = pooled_idx.loc["hgb_timewalk"]
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    shuffle_min = float(leakage[leakage["check"].str.contains("shuffled_target_sigma68")]["value"].min())
    hgb_gain_vs_hier = float(hier_row["value"] - hgb_row["value"])
    looks_too_good = bool(hgb_gain_vs_hier > 0.5 or hgb_row["value"] < 0.8)
    leakage_flag = bool(event_overlap != 0 or shuffle_min < min(hier_row["value"], hgb_row["value"]) + 0.2)
    run61 = per_run[(per_run["heldout_run"] == 61)].set_index("method")
    verdict = (
        "hierarchical_shrinkage_improves_signed_prior_no_leakage"
        if hier_row["value"] < phys_row["value"] and event_overlap == 0 and not leakage_flag
        else "hierarchical_shrinkage_no_clear_gain_or_leakage_concern"
    )

    result = {
        "study": "S03f",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and run65_repro["pass"].all() and s03d_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "run65_s03a_s03b_pass": bool(run65_repro["pass"].all()),
            "s03d_pooled_headline_pass": bool(s03d_repro["pass"].all()),
        },
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "baseline": {"method": "template_phase", "value": float(base["value"]), "ci": [float(base["ci_low"]), float(base["ci_high"])]},
        "traditional": {
            "s03a_amp_only": {
                "method": "amp_only_ridge_residual_on_template_phase",
                "value": float(s03a_row["value"]),
                "ci": [float(s03a_row["ci_low"]), float(s03a_row["ci_high"])],
            },
            "s03b_monotone_binned": {
                "method": "per_stave_monotone_decreasing_binned_timewalk",
                "value": float(s03b_row["value"]),
                "ci": [float(s03b_row["ci_low"]), float(s03b_row["ci_high"])],
            },
            "phys_signed_inverse_amp": {
                "method": "s03d_per_stave_nonnegative_inverse_amplitude_prior",
                "value": float(phys_row["value"]),
                "ci": [float(phys_row["ci_low"]), float(phys_row["ci_high"])],
            },
            "hierarchical_signed_shrinkage": {
                "method": "bounded_partial_pooling_inverse_amplitude_slopes",
                "value": float(hier_row["value"]),
                "ci": [float(hier_row["ci_low"]), float(hier_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - hier_row["value"]),
                "delta_vs_phys_signed_inverse_amp_ns": float(phys_row["value"] - hier_row["value"]),
                "delta_vs_s03b_monotone_binned_ns": float(s03b_row["value"] - hier_row["value"]),
                "run61_value": float(run61.loc["hierarchical_signed_shrinkage", "value"]),
                "run61_delta_vs_phys_signed_inverse_amp_ns": float(run61.loc["phys_signed_inverse_amp", "value"] - run61.loc["hierarchical_signed_shrinkage", "value"]),
            },
        },
        "ml": {
            "method": "hist_gradient_boosting_residual_corrector_on_template_phase",
            "value": float(hgb_row["value"]),
            "ci": [float(hgb_row["ci_low"]), float(hgb_row["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - hgb_row["value"]),
            "gain_vs_hierarchical_signed_ns": hgb_gain_vs_hier,
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "final_models_use_heldout_rows": False,
            "shuffled_target_min_sigma68_ns": shuffle_min,
            "hgb_looks_too_good": looks_too_good,
            "leakage_flag": leakage_flag,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro_counts, run65_repro, s03d_repro, per_run, pooled, phys_table, hier_table, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03f",
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
                "phys_signed_inverse_amp": float(phys_row["value"]),
                "hierarchical_signed_shrinkage": float(hier_row["value"]),
                "hgb": float(hgb_row["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
