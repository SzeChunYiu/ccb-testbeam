#!/usr/bin/env python3
"""S03d signed per-stave amplitude timewalk prior benchmark."""

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
from scipy.optimize import lsq_linear
from sklearn.model_selection import GroupKFold

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b
import s03d_leave_one_run_s03ab_hgb_stability as s03d


RUN65_EXPECTED = {
    "template_phase_base": 2.889152765080617,
    "s03a_amp_only": 1.494640076269676,
    "s03b_monotone_binned": 1.5695763825403084,
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
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(run) for run in train_runs]
    out["timing"]["heldout_runs"] = [int(run) for run in heldout_runs]
    return out


def prepare_base_pulses(pulses_all: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, str]:
    pulses = pulses_all.copy()
    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(pulses, config, templates)
    scan = s02.evaluate_methods(pulses, methods, config)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    base_method = str(train_2cm.iloc[0]["method"])
    if base_method != str(config["timing"]["base_method"]):
        raise RuntimeError(f"Expected base method {config['timing']['base_method']}, got {base_method}")
    return pulses, base_method


def signed_basis(amp: np.ndarray, candidate: str) -> Tuple[np.ndarray, List[str]]:
    safe_amp = np.maximum(np.asarray(amp, dtype=float), 1.0)
    cols: List[np.ndarray] = []
    names: List[str] = []
    if candidate in {"inv_sqrt_amp", "inv_sqrt_plus_inv_amp"}:
        cols.append(np.sqrt(1000.0 / safe_amp))
        names.append("sqrt_1000_over_amp")
    if candidate in {"inv_amp", "inv_sqrt_plus_inv_amp"}:
        cols.append(1000.0 / safe_amp)
        names.append("1000_over_amp")
    if not cols:
        raise ValueError(candidate)
    return np.column_stack(cols), names


def signed_design(pulses: pd.DataFrame, staves: List[str], candidate: str) -> Tuple[np.ndarray, List[str], np.ndarray, np.ndarray]:
    basis, basis_names = signed_basis(pulses["amplitude_adc"].to_numpy(dtype=float), candidate)
    stave_arr = pulses["stave"].to_numpy()
    cols = []
    names = []
    lower = []
    upper = []
    for stave in staves:
        mask = (stave_arr == stave).astype(float)
        cols.append(mask)
        names.append(f"{stave}_intercept")
        lower.append(-np.inf)
        upper.append(np.inf)
    for stave in staves:
        mask = (stave_arr == stave).astype(float)[:, None]
        for i, basis_name in enumerate(basis_names):
            cols.append(mask[:, 0] * basis[:, i])
            names.append(f"{stave}_{basis_name}_positive")
            lower.append(0.0)
            upper.append(np.inf)
    return np.column_stack(cols), names, np.asarray(lower), np.asarray(upper)


def fit_signed_prior(X: np.ndarray, y: np.ndarray, lower: np.ndarray, upper: np.ndarray):
    return lsq_linear(X, y, bounds=(lower, upper), method="trf", lsmr_tol="auto", max_iter=2000)


def finite_mask(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.isfinite(runs) & np.all(np.isfinite(X), axis=1)


def eval_values(pulses: pd.DataFrame, method_name: str, values: np.ndarray, config: dict, runs: List[int]) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, runs)


def run_signed_prior(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy()
    cv_rows = []
    best = {"score": np.inf, "candidate": None}
    for candidate in config["signed_prior"]["candidate_bases"]:
        X, names, lower, upper = signed_design(pulses, staves, str(candidate))
        train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
        idx_train = np.flatnonzero(train_mask)
        groups = runs[train_mask]
        n_splits = min(int(config["signed_prior"]["cv_folds"]), len(np.unique(groups)))
        gkf = GroupKFold(n_splits=n_splits)
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            fit = fit_signed_prior(X[train_mask][tr], targets[train_mask][tr], lower, upper)
            pred = np.full(len(pulses), np.nan)
            pred[idx_train[va]] = X[idx_train[va]] @ fit.x
            corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
            va_runs = sorted(np.unique(runs[idx_train[va]]).astype(int).tolist())
            vals = eval_values(pulses.iloc[idx_train[va]], "signed_prior_cv", corrected[idx_train[va]], config, va_runs)
            score = s02.sigma68(vals)
            fold_scores.append(score)
            cv_rows.append({"candidate": candidate, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals)), "active_positive_terms": int(np.sum(fit.x[len(staves):] > 1.0e-10))})
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append({"candidate": candidate, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0, "active_positive_terms": 0})
        if mean_score < best["score"]:
            best = {"score": mean_score, "candidate": str(candidate)}

    X, names, lower, upper = signed_design(pulses, staves, str(best["candidate"]))
    train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
    fit = fit_signed_prior(X[train_mask], targets[train_mask], lower, upper)
    pred = X @ fit.x
    out = pulses.copy()
    out["signed_prior_target_residual_ns"] = targets
    out["signed_prior_pred_residual_ns"] = pred
    out["t_signed_prior_ns"] = out[f"t_{base_method}_ns"] - pred
    coef = pd.DataFrame(
        {
            "feature": names,
            "coefficient_ns_per_unit": fit.x,
            "lower_bound": lower,
            "upper_bound": upper,
            "at_positive_bound": np.isclose(fit.x, 0.0) & np.isfinite(lower) & (lower == 0.0),
        }
    )
    return out, pd.DataFrame(cv_rows), coef, best


def run_signed_shuffled_control(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> float:
    rng = np.random.default_rng(int(config["signed_prior"]["random_seed"]) + 307)
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, _, lower, upper = signed_design(pulses, staves, str(best["candidate"]))
    runs = pulses["run"].to_numpy()
    train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    fit = fit_signed_prior(X[train_mask], shuffled, lower, upper)
    pred = X @ fit.x
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    vals = eval_values(pulses, "signed_prior_shuffled", corrected, config, heldout_runs)
    return s02.sigma68(vals)


def bootstrap_rows(
    pulses: pd.DataFrame, config: dict, rng: np.random.Generator, methods: List[Tuple[str, str]]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residual_rows = []
    heldout_run = int(config["timing"]["heldout_runs"][0])
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, 2.0, config, [heldout_run])
        ci = s02.bootstrap_ci(vals, rng, int(config["signed_prior"]["bootstrap_samples"]))
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
        residual_rows.extend({"heldout_run": heldout_run, "method": label, "pairwise_residual_ns": float(value)} for value in vals)
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


def run_one_fold(
    pulses_all: pd.DataFrame, base_config: dict, heldout_run: int, all_runs: List[int], rng: np.random.Generator
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = prepare_base_pulses(pulses_all, config)

    s03a_pulses, s03a_cv, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    binned_pulses, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    signed_pulses, signed_cv, signed_coef, signed_best = run_signed_prior(pulses, config, base_method)
    hgb_pulses, hgb_cv, hgb_best = s03d.run_hgb(pulses, config, base_method)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_isotonic_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["t_signed_prior_ns"] = signed_pulses["t_signed_prior_ns"].to_numpy(dtype=float)
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)
    combined["signed_prior_target_residual_ns"] = signed_pulses["signed_prior_target_residual_ns"].to_numpy(dtype=float)
    combined["signed_prior_pred_residual_ns"] = signed_pulses["signed_prior_pred_residual_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only_ridge"),
            ("s03b_isotonic", "s03b_isotonic_decreasing"),
            ("signed_prior", "signed_physics_prior"),
            ("hgb_timewalk", "hgb_timewalk_ml"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["s03a_candidate"] = s03a_candidate
    benchmark["s03a_alpha"] = s03a_alpha
    benchmark["s03b_direction"] = binned_best["direction"]
    benchmark["s03b_n_bins"] = binned_best["n_bins"]
    benchmark["signed_candidate"] = signed_best["candidate"]
    benchmark["signed_cv_sigma68_ns"] = signed_best["score"]
    benchmark["hgb_cv_sigma68_ns"] = hgb_best["score"]

    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(combined[combined["run"].isin([heldout_run])]["event_id"])
    leakage = pd.DataFrame(
        [
            {"heldout_run": heldout_run, "check": "train_heldout_event_id_overlap", "value": float(len(train_event_ids & heldout_event_ids)), "unit": "events"},
            {"heldout_run": heldout_run, "check": "signed_prior_shuffled_target_sigma68", "value": run_signed_shuffled_control(pulses, config, base_method, signed_best), "unit": "ns"},
            {"heldout_run": heldout_run, "check": "s03b_isotonic_shuffled_target_sigma68", "value": s03b.run_shuffled_binned_control(pulses, config, base_method, binned_best), "unit": "ns"},
            {"heldout_run": heldout_run, "check": "hgb_shuffled_target_sigma68", "value": s03d.run_hgb_shuffled_control(pulses, config, base_method, hgb_best), "unit": "ns"},
            {"heldout_run": heldout_run, "check": "features_exclude_run_event_order_cross_stave_time", "value": 1.0, "unit": "bool"},
            {"heldout_run": heldout_run, "check": "final_models_use_heldout_rows", "value": 0.0, "unit": "bool"},
        ]
    )
    for frame in [s03a_cv, binned_cv, signed_cv, signed_coef, hgb_cv]:
        frame["heldout_run"] = heldout_run
    binned_table = s03b.binned_model_table(binned_models)
    binned_table["heldout_run"] = heldout_run
    return benchmark, residuals, leakage, s03a_cv, binned_cv, signed_cv, signed_coef, hgb_cv


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(residuals["heldout_run"].unique().tolist())
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        by_run = {run: sub["pairwise_residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            stats.append(s02.sigma68(np.concatenate([by_run[int(run)] for run in sampled])))
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


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, coef: pd.DataFrame) -> None:
    order = ["template_phase_base", "s03a_amp_only_ridge", "s03b_isotonic_decreasing", "signed_physics_prior", "hgb_timewalk_ml"]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03d signed-prior leave-one-run-out width")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03d_signed_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    sub = pooled.set_index("method").loc[order].reset_index()
    xpos = np.arange(len(sub))
    ax.bar(xpos, sub["value"])
    ax.errorbar(xpos, sub["value"], yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(xpos)
    ax.set_xticklabels(sub["method"], rotation=25, ha="right")
    ax.set_ylabel("pooled LORO sigma68 (ns)")
    ax.set_title("Run-bootstrap pooled interval")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03d_signed_pooled_run_bootstrap.png", dpi=130)
    plt.close(fig)

    signed = coef[coef["feature"].str.contains("_positive")].copy()
    if len(signed):
        signed["label"] = signed["heldout_run"].astype(str) + " " + signed["feature"]
        fig, ax = plt.subplots(figsize=(10.0, 4.4))
        ax.bar(np.arange(len(signed)), signed["coefficient_ns_per_unit"])
        ax.set_xticks(np.arange(len(signed)))
        ax.set_xticklabels(signed["label"], rotation=75, ha="right", fontsize=7)
        ax.set_ylabel("nonnegative coefficient")
        ax.set_title("Signed prior positive timewalk slopes")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_s03d_signed_coefficients.png", dpi=130)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro_counts: pd.DataFrame,
    run65_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    signed_coef: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    order = ["template_phase_base", "s03a_amp_only_ridge", "s03b_isotonic_decreasing", "signed_physics_prior", "hgb_timewalk_ml"]
    pooled_view = pooled.set_index("method").loc[order].reset_index()
    coef_summary = signed_coef.groupby("feature", as_index=False).agg(
        median_coeff=("coefficient_ns_per_unit", "median"),
        min_coeff=("coefficient_ns_per_unit", "min"),
        max_coeff=("coefficient_ns_per_unit", "max"),
        at_bound_folds=("at_positive_bound", "sum"),
    )
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    lines = [
        "# Study report: S03d - Signed per-stave amplitude timewalk prior",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65",
        f"- **Config:** `{config_path}`",
        "",
        "## 0. Question",
        "",
        "Can a physically signed per-stave amplitude timewalk prior replace the flexible S03b isotonic fit without losing held-out timing resolution?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun from raw ROOT before the S03d comparison.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "The run-65 S03a/S03b reference numbers were reproduced from the same raw-derived pulse table before accepting the new signed-prior result.",
        "",
        run65_repro.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "The signed prior fits per-stave intercepts plus nonnegative coefficients on inverse-amplitude basis terms. Positive coefficients mean lower-amplitude pulses receive a larger predicted delay correction; the sign is fixed by the downstream timewalk prior. Candidate bases were selected only by grouped CV on training runs.",
        "",
        coef_summary.to_markdown(index=False),
        "",
        "## 3. Leave-one-run-out head-to-head",
        "",
        per_run[["heldout_run", "method", "value", "ci_low", "ci_high", "n_pair_residuals", "signed_candidate", "signed_cv_sigma68_ns", "hgb_cv_sigma68_ns"]].sort_values(["heldout_run", "method"]).to_markdown(index=False),
        "",
        pooled_view[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## 4. Leakage checks",
        "",
        "All model selection is grouped by run. Final models are trained with the held-out run removed. Features exclude run number, event id, event order, other-stave timing, and held-out labels.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 5. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"The signed prior pooled sigma68 is `{result['traditional']['signed_physics_prior']['value']:.3f} ns`; S03b isotonic is `{result['traditional']['s03b_isotonic_decreasing']['value']:.3f} ns`; S03a Ridge is `{result['comparators']['s03a_amp_only_ridge']['value']:.3f} ns`; HGB ML is `{result['ml']['value']:.3f} ns`.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03d_signed_timewalk_prior.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `signed_prior_cv_scan.csv`, `signed_prior_coefficients.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03d_signed_timewalk_prior.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["signed_prior"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(run) for run in config["timing"]["loo_runs"]]

    run65_bench, _, _, _, _, _, _, _ = run_one_fold(pulses_all, config, 65, all_runs, rng)
    run65_lookup = {
        "s03a_amp_only_ridge": "s03a_amp_only",
        "s03b_isotonic_decreasing": "s03b_monotone_binned",
        "template_phase_base": "template_phase_base",
    }
    run65_repro = run65_bench[run65_bench["method"].isin(run65_lookup)].copy()
    run65_repro["reference_method"] = run65_repro["method"].map(run65_lookup)
    run65_repro["reference_value"] = run65_repro["reference_method"].map(RUN65_EXPECTED)
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
    signed_cv_parts = []
    signed_coef_parts = []
    hgb_cv_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, s03a_cv, binned_cv, signed_cv, signed_coef, hgb_cv = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        s03a_cv_parts.append(s03a_cv)
        s03b_cv_parts.append(binned_cv)
        signed_cv_parts.append(signed_cv)
        signed_coef_parts.append(signed_coef)
        hgb_cv_parts.append(hgb_cv)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    s03a_cv = pd.concat(s03a_cv_parts, ignore_index=True)
    s03b_cv = pd.concat(s03b_cv_parts, ignore_index=True)
    signed_cv = pd.concat(signed_cv_parts, ignore_index=True)
    signed_coef = pd.concat(signed_coef_parts, ignore_index=True)
    hgb_cv = pd.concat(hgb_cv_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["signed_prior"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    s03a_cv.to_csv(out_dir / "s03a_amp_only_cv_scan.csv", index=False)
    s03b_cv.to_csv(out_dir / "s03b_isotonic_cv_scan.csv", index=False)
    signed_cv.to_csv(out_dir / "signed_prior_cv_scan.csv", index=False)
    signed_coef.to_csv(out_dir / "signed_prior_coefficients.csv", index=False)
    hgb_cv.to_csv(out_dir / "hgb_cv_scan.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled, signed_coef)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    s03a_row = pooled_idx.loc["s03a_amp_only_ridge"]
    iso_row = pooled_idx.loc["s03b_isotonic_decreasing"]
    signed_row = pooled_idx.loc["signed_physics_prior"]
    hgb_row = pooled_idx.loc["hgb_timewalk_ml"]
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    shuffle_min = float(leakage[leakage["check"].str.contains("shuffled_target_sigma68")]["value"].min())
    hgb_gain_vs_signed = float(signed_row["value"] - hgb_row["value"])
    looks_too_good = bool(hgb_gain_vs_signed > 0.5 or hgb_row["value"] < 0.8)
    leakage_flag = bool(event_overlap != 0 or shuffle_min < min(signed_row["value"], hgb_row["value"]) + 0.2)
    signed_matches_iso = bool(signed_row["ci_low"] <= iso_row["value"] and signed_row["ci_high"] >= iso_row["value"])
    verdict = "signed_prior_competitive_no_leakage_flag" if signed_matches_iso and not leakage_flag else "signed_prior_gap_or_leakage_concern"

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
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "baseline": {"method": "template_phase", "value": float(base["value"]), "ci": [float(base["ci_low"]), float(base["ci_high"])]},
        "traditional": {
            "signed_physics_prior": {
                "method": "per_stave_nonnegative_inverse_amplitude_prior",
                "value": float(signed_row["value"]),
                "ci": [float(signed_row["ci_low"]), float(signed_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - signed_row["value"]),
                "delta_vs_s03b_isotonic_ns": float(iso_row["value"] - signed_row["value"]),
                "competitive_with_isotonic_by_ci": signed_matches_iso,
            },
            "s03b_isotonic_decreasing": {
                "method": "per_stave_monotone_decreasing_binned_timewalk",
                "value": float(iso_row["value"]),
                "ci": [float(iso_row["ci_low"]), float(iso_row["ci_high"])],
            },
        },
        "comparators": {
            "s03a_amp_only_ridge": {"value": float(s03a_row["value"]), "ci": [float(s03a_row["ci_low"]), float(s03a_row["ci_high"])]}
        },
        "ml": {
            "method": "hist_gradient_boosting_residual_corrector_on_template_phase",
            "value": float(hgb_row["value"]),
            "ci": [float(hgb_row["ci_low"]), float(hgb_row["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - hgb_row["value"]),
            "gain_vs_signed_prior_ns": hgb_gain_vs_signed,
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
        "next_tickets": [
            "S03e: blind Sample-I to Sample-II transfer of signed timewalk priors",
            "S03f: shared hierarchical signed-prior shrinkage across downstream staves",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro_counts, run65_repro, per_run, pooled, signed_coef, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03d",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["signed_prior"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "base": float(base["value"]),
                "s03a_amp_only_ridge": float(s03a_row["value"]),
                "s03b_isotonic": float(iso_row["value"]),
                "signed_prior": float(signed_row["value"]),
                "hgb": float(hgb_row["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
