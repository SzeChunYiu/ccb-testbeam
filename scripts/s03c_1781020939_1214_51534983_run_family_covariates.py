#!/usr/bin/env python3
"""S03c follow-up: train-only run-family nuisance summaries for Ridge timing."""

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
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03c_multi_heldout_timewalk_stability as s03c


S03C_REFERENCE = {
    "ticket": "1781011359.822.3751464b",
    "baseline_sigma68_ns": 2.7414145300852155,
    "traditional_sigma68_ns": 1.5510917109777833,
    "ml_sigma68_ns": 1.5369230041797883,
    "ml_gain_vs_template_phase_ns": 1.2044915259054272,
}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def run_to_family(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for family, runs in config.get("run_families", {}).items():
        for run in runs:
            out[int(run)] = str(family)
    return out


def make_model(alpha: float):
    return make_pipeline(StandardScaler(), Ridge(alpha=max(float(alpha), 1.0e-12)))


def finite_design(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def prepare_fold_pulses(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, str]:
    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    out = pulses.copy()
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    if best_method != config["timing"]["base_method"]:
        raise RuntimeError(f"Expected base method {config['timing']['base_method']}, got {best_method}")
    return out, best_method


def family_summary_features(
    pulses: pd.DataFrame,
    target: np.ndarray,
    config: dict,
    summary_train_runs: Iterable[int],
    target_for_summary: np.ndarray | None = None,
) -> Tuple[np.ndarray, List[str], pd.DataFrame]:
    """Return per-pulse run-family summaries computed from summary_train_runs only."""
    if target_for_summary is None:
        target_for_summary = target
    runs = pulses["run"].to_numpy(dtype=int)
    staves = pulses["stave"].to_numpy()
    families = run_to_family(config)
    pulse_family = np.asarray([families.get(int(run), "unknown") for run in runs], dtype=object)
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    area_over_amp = pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(
        pulses["amplitude_adc"].to_numpy(dtype=float), 1.0
    )
    peak = pulses["peak_sample"].to_numpy(dtype=float)
    train_mask = np.isin(runs, [int(r) for r in summary_train_runs]) & np.isfinite(target_for_summary)
    names = [
        "family_target_median_ns",
        "family_target_iqr_ns",
        "family_log_amp_median",
        "family_log_amp_iqr",
        "family_area_over_amp_median",
        "family_peak_median",
        "family_log_support",
    ]
    global_by_stave: Dict[str, np.ndarray] = {}
    by_key: Dict[Tuple[str, str], np.ndarray] = {}
    rows = []

    def summarize(mask: np.ndarray) -> np.ndarray:
        if not np.any(mask):
            return np.zeros(len(names), dtype=float)
        y = target_for_summary[mask]
        la = amp_log[mask]
        aoa = area_over_amp[mask]
        pk = peak[mask]
        return np.asarray(
            [
                float(np.nanmedian(y)),
                float(np.nanpercentile(y, 75) - np.nanpercentile(y, 25)),
                float(np.nanmedian(la)),
                float(np.nanpercentile(la, 75) - np.nanpercentile(la, 25)),
                float(np.nanmedian(aoa)),
                float(np.nanmedian(pk)),
                float(np.log1p(np.sum(mask))),
            ],
            dtype=float,
        )

    for stave in config["timing"]["downstream_staves"]:
        stave_mask = train_mask & (staves == stave)
        global_by_stave[str(stave)] = summarize(stave_mask)
        rows.append({"family": "__global__", "stave": stave, **dict(zip(names, global_by_stave[str(stave)]))})
        for family in sorted(set(families.values())):
            mask = stave_mask & (pulse_family == family)
            values = summarize(mask) if np.any(mask) else global_by_stave[str(stave)]
            by_key[(family, str(stave))] = values
            rows.append({"family": family, "stave": stave, **dict(zip(names, values)), "direct_support": int(np.sum(mask))})

    X = np.zeros((len(pulses), len(names)), dtype=float)
    fallback_count = 0
    for i, (family, stave) in enumerate(zip(pulse_family, staves)):
        key = (str(family), str(stave))
        if key in by_key:
            X[i] = by_key[key]
        else:
            fallback_count += 1
            X[i] = global_by_stave.get(str(stave), np.zeros(len(names), dtype=float))
    table = pd.DataFrame(rows)
    table["summary_train_runs"] = ",".join(str(int(r)) for r in summary_train_runs)
    table["fallback_pulses"] = int(fallback_count)
    return X, names, table


def design_matrix(
    pulses: pd.DataFrame,
    target: np.ndarray,
    config: dict,
    summary_train_runs: Iterable[int],
    kind: str,
    target_for_summary: np.ndarray | None = None,
) -> Tuple[np.ndarray, List[str], pd.DataFrame]:
    staves = list(config["timing"]["downstream_staves"])
    if kind == "traditional_family_ridge":
        candidate = str(config["family_ridge"]["traditional_candidate"])
        base, base_names = s03a.analytic_feature_matrix(pulses, candidate, staves)
    elif kind == "ml_family_ridge":
        base = s02.feature_matrix(pulses, staves)
        base_names = [f"waveform_norm_{i}" for i in range(int(config["samples_per_channel"]))]
        base_names += ["log_amp", "peak_sample", "area_over_amp"] + [f"stave_{stave}" for stave in staves]
    else:
        raise ValueError(kind)
    fam, fam_names, table = family_summary_features(pulses, target, config, summary_train_runs, target_for_summary)
    return np.hstack([base, fam]), base_names + fam_names, table


def evaluate_corrected(
    pulses: pd.DataFrame,
    method_name: str,
    values: np.ndarray,
    config: dict,
    runs: Iterable[int],
) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, [int(r) for r in runs])


def run_family_ridge(
    pulses: pd.DataFrame,
    config: dict,
    base_method: str,
    kind: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, float]:
    target = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    alphas = [float(a) for a in config["family_ridge"]["ridge_alphas"]]
    groups_all = runs[np.isin(runs, train_runs) & np.isfinite(target)]
    n_splits = min(int(config["family_ridge"]["cv_folds"]), len(np.unique(groups_all)))
    cv_rows = []
    best = {"score": math.inf, "alpha": None}

    train_base_mask = np.isin(runs, train_runs) & np.isfinite(target)
    idx_base = np.flatnonzero(train_base_mask)
    groups = runs[train_base_mask]
    gkf = GroupKFold(n_splits=n_splits)
    for alpha in alphas:
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(idx_base, target[train_base_mask], groups=groups)):
            inner_train_runs = sorted(np.unique(runs[idx_base[tr]]).astype(int).tolist())
            X, names, _ = design_matrix(pulses, target, config, inner_train_runs, kind)
            mask = np.isin(runs, inner_train_runs) & finite_design(X, target, runs)
            model = make_model(alpha)
            model.fit(X[mask], target[mask])
            pred = np.full(len(pulses), np.nan, dtype=float)
            va_idx = idx_base[va]
            pred[va_idx] = model.predict(X[va_idx])
            corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
            va_runs = sorted(np.unique(runs[va_idx]).astype(int).tolist())
            vals = evaluate_corrected(pulses.iloc[va_idx].copy(), f"{kind}_cv", corrected[va_idx], config, va_runs)
            score = s02.sigma68(vals)
            fold_scores.append(score)
            cv_rows.append(
                {
                    "method": kind,
                    "alpha": alpha,
                    "fold": int(fold),
                    "sigma68_ns": score,
                    "n_pair_residuals": int(len(vals)),
                    "n_features": int(len(names)),
                    "summary_train_runs": ",".join(str(r) for r in inner_train_runs),
                }
            )
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append(
            {
                "method": kind,
                "alpha": alpha,
                "fold": -1,
                "sigma68_ns": mean_score,
                "n_pair_residuals": 0,
                "n_features": int(len(names)),
                "summary_train_runs": "inner_cv_train_only",
            }
        )
        if mean_score < best["score"]:
            best = {"score": mean_score, "alpha": alpha}

    best_alpha = float(best["alpha"])
    X, names, summary_table = design_matrix(pulses, target, config, train_runs, kind)
    mask = np.isin(runs, train_runs) & finite_design(X, target, runs)
    model = make_model(best_alpha)
    model.fit(X[mask], target[mask])
    pred = model.predict(X)
    out = pulses.copy()
    suffix = "trad_family_ridge" if kind == "traditional_family_ridge" else "ml_family_ridge"
    out[f"{suffix}_target_residual_ns"] = target
    out[f"{suffix}_pred_residual_ns"] = pred
    out[f"t_{suffix}_ns"] = out[f"t_{base_method}_ns"] - pred

    ridge = model.named_steps["ridge"]
    scale = model.named_steps["standardscaler"].scale_
    coef = ridge.coef_ / np.where(scale == 0.0, 1.0, scale)
    coef_rows = pd.DataFrame(
        {
            "method": kind,
            "alpha": best_alpha,
            "feature": names,
            "coefficient_ns_per_raw_unit": coef,
            "standardized_coefficient_ns": ridge.coef_,
        }
    ).sort_values("standardized_coefficient_ns", key=lambda s: s.abs(), ascending=False)
    return out, pd.DataFrame(cv_rows), coef_rows, summary_table, best_alpha


def run_shuffled_family_control(
    pulses: pd.DataFrame,
    config: dict,
    base_method: str,
    kind: str,
    alpha: float,
) -> float:
    target = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    rng = np.random.default_rng(int(config["family_ridge"]["random_seed"]) + (101 if kind == "traditional_family_ridge" else 211))
    shuffled = target.copy()
    train_mask_target = np.isin(runs, train_runs) & np.isfinite(target)
    train_vals = shuffled[train_mask_target].copy()
    rng.shuffle(train_vals)
    shuffled[train_mask_target] = train_vals
    X, _, _ = design_matrix(pulses, target, config, train_runs, kind, target_for_summary=shuffled)
    mask = np.isin(runs, train_runs) & finite_design(X, shuffled, runs)
    model = make_model(alpha)
    model.fit(X[mask], shuffled[mask])
    pred = model.predict(X)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    vals = evaluate_corrected(pulses, f"{kind}_shuffled", corrected, config, config["timing"]["heldout_runs"])
    return s02.sigma68(vals)


def run_no_family_ml(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out, cv, _ = s02.run_ml(pulses, config, base_method, 2.0)
    return out.rename(columns={"t_ml_ridge_ns": "t_ml_no_family_ridge_ns"}), cv


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
        ci = s02.bootstrap_ci(vals, rng, int(config["family_ridge"]["bootstrap_samples"]))
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
            {"heldout_run": heldout_run, "method": label, "pairwise_residual_ns": float(v)}
            for v in vals
        )
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if int(run) != int(heldout_run)]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = prepare_fold_pulses(pulses_all, config)
    analytic_pulses, analytic_cv, analytic_coef, analytic_candidate, analytic_alpha = s03a.run_analytic(
        pulses, config, base_method
    )
    ml_no_family, ml_no_family_cv = run_no_family_ml(pulses, config, base_method)
    trad_family, trad_family_cv, trad_coef, summary_table, trad_alpha = run_family_ridge(
        pulses, config, base_method, "traditional_family_ridge"
    )
    ml_family, ml_family_cv, ml_coef, ml_summary_table, ml_alpha = run_family_ridge(
        pulses, config, base_method, "ml_family_ridge"
    )

    combined = analytic_pulses.copy()
    combined["t_ml_no_family_ridge_ns"] = ml_no_family["t_ml_no_family_ridge_ns"].to_numpy(dtype=float)
    combined["t_trad_family_ridge_ns"] = trad_family["t_trad_family_ridge_ns"].to_numpy(dtype=float)
    combined["trad_family_ridge_pred_residual_ns"] = trad_family["trad_family_ridge_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_ml_family_ridge_ns"] = ml_family["t_ml_family_ridge_ns"].to_numpy(dtype=float)
    combined["ml_family_ridge_pred_residual_ns"] = ml_family["ml_family_ridge_pred_residual_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("analytic_timewalk", "analytic_timewalk"),
            ("ml_no_family_ridge", "ml_ridge_no_family"),
            ("trad_family_ridge", "traditional_family_summary_ridge"),
            ("ml_family_ridge", "ml_waveform_family_summary_ridge"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["analytic_candidate"] = analytic_candidate
    benchmark["analytic_alpha"] = float(analytic_alpha)
    benchmark["traditional_family_alpha"] = trad_alpha
    benchmark["ml_family_alpha"] = ml_alpha

    leakage = s03a.run_negative_controls(pulses, config, base_method, analytic_candidate, analytic_alpha)
    leakage["heldout_run"] = heldout_run
    leakage = pd.concat(
        [
            leakage,
            pd.DataFrame(
                [
                    {
                        "check": "traditional_family_summary_shuffled_target",
                        "heldout_sigma68_ns": run_shuffled_family_control(
                            pulses, config, base_method, "traditional_family_ridge", trad_alpha
                        ),
                        "n_pair_residuals": int(
                            benchmark[benchmark["method"] == "traditional_family_summary_ridge"]["n_pair_residuals"].iloc[0]
                        ),
                        "heldout_run": heldout_run,
                    },
                    {
                        "check": "ml_family_summary_shuffled_target",
                        "heldout_sigma68_ns": run_shuffled_family_control(
                            pulses, config, base_method, "ml_family_ridge", ml_alpha
                        ),
                        "n_pair_residuals": int(
                            benchmark[benchmark["method"] == "ml_waveform_family_summary_ridge"]["n_pair_residuals"].iloc[0]
                        ),
                        "heldout_run": heldout_run,
                    },
                    {
                        "check": "feature_audit_no_run_event_order_or_cross_stave_time",
                        "heldout_sigma68_ns": 0.0,
                        "n_pair_residuals": 0,
                        "heldout_run": heldout_run,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    cv = pd.concat(
        [
            analytic_cv.assign(method="analytic_timewalk", heldout_run=heldout_run),
            ml_no_family_cv.assign(method="ml_ridge_no_family", heldout_run=heldout_run),
            trad_family_cv.assign(heldout_run=heldout_run),
            ml_family_cv.assign(heldout_run=heldout_run),
        ],
        ignore_index=True,
        sort=False,
    )
    coefficients = pd.concat(
        [
            analytic_coef.assign(method="analytic_timewalk", alpha=float(analytic_alpha), heldout_run=heldout_run),
            trad_coef.assign(heldout_run=heldout_run),
            ml_coef.assign(heldout_run=heldout_run),
        ],
        ignore_index=True,
        sort=False,
    )
    summary_table = pd.concat(
        [
            summary_table.assign(method="traditional_family_summary_ridge", heldout_run=heldout_run),
            ml_summary_table.assign(method="ml_waveform_family_summary_ridge", heldout_run=heldout_run),
        ],
        ignore_index=True,
        sort=False,
    )
    prediction_preview = combined[
        [
            "event_id",
            "run",
            "stave",
            "amplitude_adc",
            "trad_family_ridge_pred_residual_ns",
            "ml_family_ridge_pred_residual_ns",
        ]
    ].head(250)
    return benchmark, residuals, leakage, cv, coefficients, summary_table, prediction_preview


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
        "analytic_timewalk",
        "ml_ridge_no_family",
        "traditional_family_summary_ridge",
        "ml_waveform_family_summary_ridge",
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("Train-only run-family covariate stress test")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 4.3))
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
    ax.set_xticklabels(sub["method"], rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("pooled sigma68 (ns)")
    ax.set_title("Held-out run bootstrap")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_run_bootstrap.png", dpi=130)
    plt.close(fig)


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


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro_counts: pd.DataFrame,
    s03a_repro: pd.DataFrame,
    reference_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    no_family = pooled_idx.loc["ml_ridge_no_family"]
    trad = pooled_idx.loc["traditional_family_summary_ridge"]
    ml = pooled_idx.loc["ml_waveform_family_summary_ridge"]
    leak_summary = leakage.pivot_table(index="check", values="heldout_sigma68_ns", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_sigma68_ns", "median_sigma68_ns", "max_sigma68_ns"]
    lines = [
        "# S03c follow-up: train-only run-family covariates",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Follow-up to:** {S03C_REFERENCE['ticket']}",
        f"- **Worker:** {config['worker']}",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65",
        "- **Bootstrap:** resample held-out runs, not individual residuals",
        f"- **Config:** `{config_path}`",
        "",
        "## Question",
        "",
        "Does the S03c Ridge residual correction gain persist after adding run-family nuisance summaries, when those summaries are computed only from training runs for every held-out-run fold?",
        "",
        "## Raw reproduction gate",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "The S03a run-65 anchor was reproduced from the same raw pass.",
        "",
        s03a_repro.to_markdown(index=False),
        "",
        "The prior S03c follow-up number was then rederived before the new covariate test.",
        "",
        reference_repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "The traditional comparator is the established analytic timewalk Ridge plus a low-dimensional analytic Ridge using amplitude/rise/stave features and train-only run-family summaries. The ML method is the waveform-feature Ridge residual corrector with the same train-only summary block. Summary covariates include per-family, per-stave training residual medians/IQRs and amplitude/shape support summaries; no held-out run rows enter these summaries, including inside inner CV.",
        "",
        "## Held-out run results",
        "",
        per_run[
            [
                "heldout_run",
                "method",
                "value",
                "ci_low",
                "ci_high",
                "n_pair_residuals",
                "analytic_candidate",
                "analytic_alpha",
                "traditional_family_alpha",
                "ml_family_alpha",
            ]
        ]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "Pooled intervals resample the seven held-out runs.",
        "",
        pooled[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]]
        .sort_values("value")
        .to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        "Every promoted split is by run. The family summaries are recomputed from training runs only, event-id train/held-out overlap is audited, and shuffled-target controls rebuild both the fitted target and target-derived summary covariates from shuffled training targets.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## Verdict",
        "",
        f"Template phase is `{base['value']:.3f} ns` with run-bootstrap CI `[{base['ci_low']:.3f}, {base['ci_high']:.3f}] ns`.",
        f"The no-family S03c Ridge reproduction is `{no_family['value']:.3f} ns`, matching the prior `{S03C_REFERENCE['ml_sigma68_ns']:.3f} ns` reference within `{abs(no_family['value'] - S03C_REFERENCE['ml_sigma68_ns']):.3g} ns`.",
        f"The traditional family-summary Ridge is `{trad['value']:.3f} ns` with CI `[{trad['ci_low']:.3f}, {trad['ci_high']:.3f}] ns`.",
        f"The ML waveform family-summary Ridge is `{ml['value']:.3f} ns` with CI `[{ml['ci_low']:.3f}, {ml['ci_high']:.3f}] ns`, a gain of `{base['value'] - ml['value']:.3f} ns` versus template phase.",
        f"Conclusion: `{result['verdict']}`.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s03c_1781020939_1214_51534983_run_family_covariates.py --config {config_path}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03c_1781020939_1214_51534983_run_family_covariates.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["family_ridge"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    s03a_repro, _ = s03c.run_s03a_reproduction(pulses_all, config, rng)
    s03a_repro.to_csv(out_dir / "s03a_run65_reproduction.csv", index=False)
    if not bool(s03a_repro["pass"].all()):
        raise RuntimeError("S03a run-65 reproduction gate failed")

    all_runs = [int(run) for run in config["timing"]["loo_runs"]]
    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    cv_parts = []
    coef_parts = []
    summary_parts = []
    preview_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, cv, coefficients, summary_table, preview = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        cv_parts.append(cv)
        coef_parts.append(coefficients)
        summary_parts.append(summary_table)
        preview_parts.append(preview.assign(heldout_run=heldout_run))

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    cv = pd.concat(cv_parts, ignore_index=True, sort=False)
    coefficients = pd.concat(coef_parts, ignore_index=True, sort=False)
    summary_table = pd.concat(summary_parts, ignore_index=True, sort=False)
    preview = pd.concat(preview_parts, ignore_index=True, sort=False)
    pooled = run_level_bootstrap(residuals, rng, int(config["family_ridge"]["bootstrap_samples"]))

    reference_rows = []
    for method, value in [
        ("template_phase_base", S03C_REFERENCE["baseline_sigma68_ns"]),
        ("ml_ridge_no_family", S03C_REFERENCE["ml_sigma68_ns"]),
    ]:
        observed = float(pooled[pooled["method"] == method]["value"].iloc[0])
        reference_rows.append(
            {
                "method": method,
                "s03c_reference_value": value,
                "reproduced_value": observed,
                "delta_ns": observed - value,
                "pass": abs(observed - value) < 1.0e-9,
            }
        )
    reference_repro = pd.DataFrame(reference_rows)

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    cv.to_csv(out_dir / "cv_scan.csv", index=False)
    coefficients.to_csv(out_dir / "ridge_coefficients.csv", index=False)
    summary_table.to_csv(out_dir / "run_family_summary_covariates.csv", index=False)
    preview.to_csv(out_dir / "prediction_preview.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    reference_repro.to_csv(out_dir / "s03c_reference_reproduction.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    analytic = pooled_idx.loc["analytic_timewalk"]
    no_family = pooled_idx.loc["ml_ridge_no_family"]
    trad_family = pooled_idx.loc["traditional_family_summary_ridge"]
    ml_family = pooled_idx.loc["ml_waveform_family_summary_ridge"]
    leakage_event_overlap = int(
        leakage[leakage["check"] == "train_heldout_event_id_overlap"]["heldout_sigma68_ns"].sum()
    )
    shuffled_checks = leakage[
        leakage["check"].isin(
            [
                "analytic_timewalk_shuffled_target",
                "traditional_family_summary_shuffled_target",
                "ml_family_summary_shuffled_target",
            ]
        )
    ]
    shuffled_min = float(shuffled_checks["heldout_sigma68_ns"].min())
    family_gain = float(base["value"] - ml_family["value"])
    no_family_reproduced = bool(reference_repro["pass"].all())
    too_good_flag = bool(float(no_family["value"] - ml_family["value"]) > 0.35)
    leakage_pass = bool(
        leakage_event_overlap == 0
        and shuffled_min > float(ml_family["value"]) + 0.5
        and no_family_reproduced
    )
    verdict = (
        "ridge_gain_persists_with_train_only_run_family_covariates_no_leakage_flag"
        if family_gain > 0.75 and leakage_pass and not too_good_flag
        else "ridge_gain_not_adopted_with_run_family_covariates"
    )
    result = {
        "study": "S03c",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "follow_up_to": S03C_REFERENCE["ticket"],
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "s03a_run65_reproduction_pass": bool(s03a_repro["pass"].all()),
            "s03c_prior_number_reproduced": no_family_reproduced,
            "s03c_reference": S03C_REFERENCE,
        },
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "baseline": {
            "method": "template_phase",
            "value": float(base["value"]),
            "ci": [float(base["ci_low"]), float(base["ci_high"])],
        },
        "traditional": {
            "method": "analytic_timewalk",
            "value": float(analytic["value"]),
            "ci": [float(analytic["ci_low"]), float(analytic["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - analytic["value"]),
        },
        "traditional_family_summary_ridge": {
            "method": "amp_rise_shape_by_stave_plus_train_only_run_family_summaries",
            "value": float(trad_family["value"]),
            "ci": [float(trad_family["ci_low"]), float(trad_family["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - trad_family["value"]),
        },
        "ml_no_family_reproduction": {
            "method": "waveform_ridge_no_family",
            "value": float(no_family["value"]),
            "ci": [float(no_family["ci_low"]), float(no_family["ci_high"])],
            "delta_vs_s03c_reference_ns": float(no_family["value"] - S03C_REFERENCE["ml_sigma68_ns"]),
        },
        "ml": {
            "method": "waveform_ridge_plus_train_only_run_family_summaries",
            "value": float(ml_family["value"]),
            "ci": [float(ml_family["ci_low"]), float(ml_family["ci_high"])],
            "gain_vs_template_phase_ns": family_gain,
            "delta_vs_no_family_ridge_ns": float(ml_family["value"] - no_family["value"]),
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": leakage_event_overlap,
            "family_summaries_training_runs_only": True,
            "inner_cv_summaries_training_folds_only": True,
            "features_exclude_run_event_order_cross_stave_time": True,
            "shuffled_target_min_sigma68_ns": shuffled_min,
            "too_good_flag": too_good_flag,
            "leakage_pass": leakage_pass,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro_counts, s03a_repro, reference_repro, per_run, pooled, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03c",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["family_ridge"]["random_seed"]),
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
                "ml_no_family": float(no_family["value"]),
                "ml_family": float(ml_family["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
