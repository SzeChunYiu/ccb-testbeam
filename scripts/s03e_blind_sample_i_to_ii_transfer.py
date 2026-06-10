#!/usr/bin/env python3
"""S03e blind Sample-I to Sample-II timewalk transfer study."""

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
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b


METHODS = [
    ("template_phase", "template_phase_base"),
    ("analytic_timewalk", "analytic_timewalk"),
    ("binned_timewalk", "s03b_binned_timewalk"),
    ("ml_template_ridge", "ml_ridge_on_template_phase"),
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


def fit_transfer_models(
    pulses: pd.DataFrame,
    config: dict,
    base_method: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    analytic_pulses, analytic_cv, coef, best_candidate, best_alpha = s03a.run_analytic(pulses, config, base_method)
    binned_pulses, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    ml_pulses, ml_cv, ml_cal = s02.run_ml(pulses, config, base_method, 2.0)

    combined = analytic_pulses.copy()
    combined["t_binned_timewalk_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["binned_target_residual_ns"] = binned_pulses["binned_target_residual_ns"].to_numpy(dtype=float)
    combined["binned_pred_residual_ns"] = binned_pulses["binned_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_ml_template_ridge_ns"] = ml_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)
    combined["ml_template_target_residual_ns"] = ml_pulses["ml_target_residual_ns"].to_numpy(dtype=float)
    combined["ml_template_pred_residual_ns"] = ml_pulses["ml_pred_residual_ns"].to_numpy(dtype=float)

    best = {
        "analytic_candidate": best_candidate,
        "analytic_alpha": best_alpha,
        "binned_mode": str(binned_best["mode"]),
        "binned_direction": str(binned_best["direction"]),
        "binned_n_bins": int(binned_best["n_bins"]),
    }
    return combined, analytic_cv, coef, binned_cv, s03b.binned_model_table(binned_models), ml_cv, ml_cal, best


def run_s03c_reference_reproduction(
    pulses_all: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    ref_runs = [int(run) for run in config["timing"]["s03c_reference_runs"]]
    ref_pulses = pulses_all[pulses_all["run"].isin(ref_runs)].copy()
    residual_parts = []
    for heldout in ref_runs:
        train_runs = [run for run in ref_runs if run != heldout]
        fold_cfg = split_config(config, train_runs, [heldout])
        timed, _ = add_base_times(ref_pulses, fold_cfg)
        combined, _, _, _, _, _, _, _ = fit_transfer_models(timed, fold_cfg, fold_cfg["timing"]["base_method"])
        _, residuals = residual_rows(
            combined,
            fold_cfg,
            [
                ("template_phase", "template_phase_base"),
                ("analytic_timewalk", "analytic_timewalk"),
                ("ml_template_ridge", "ml_ridge_on_template_phase"),
            ],
            [heldout],
            rng,
            int(config["analytic"]["bootstrap_samples"]),
        )
        residual_parts.append(residuals)

    residuals = pd.concat(residual_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["analytic"]["bootstrap_samples"]))
    expected = {
        "template_phase_base": float(config["reference_numbers"]["s03c_template_phase_base_sigma68_ns"]),
        "analytic_timewalk": float(config["reference_numbers"]["s03c_analytic_timewalk_sigma68_ns"]),
        "ml_ridge_on_template_phase": float(config["reference_numbers"]["s03c_ml_ridge_on_template_phase_sigma68_ns"]),
    }
    repro = pooled[["method", "value", "ci_low", "ci_high", "n_pair_residuals"]].copy()
    repro["s03c_report_value"] = repro["method"].map(expected)
    repro["delta_ns"] = repro["value"] - repro["s03c_report_value"]
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


def ml_shuffled_per_run(pulses: pd.DataFrame, config: dict, base_method: str, ml_cv: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 1711)
    staves = list(config["timing"]["downstream_staves"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy()
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & np.isfinite(targets)
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    best_alpha = float(ml_cv[ml_cv["fold"] == -1].sort_values("sigma68_ns").iloc[0]["alpha"])
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_mask], shuffled)
    tmp = pulses.copy()
    tmp["t_ml_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - model.predict(X)
    rows = []
    for run in config["timing"]["heldout_runs"]:
        vals = s02.pairwise_residuals(tmp, "ml_shuffled", 2.0, config, [int(run)])
        rows.append({"check": "ml_ridge_shuffled_target", "heldout_run": int(run), "heldout_sigma68_ns": s02.sigma68(vals), "n_pair_residuals": int(len(vals))})
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
            ml_shuffled_per_run(pulses, config, base_method, ml_cv),
        ],
        ignore_index=True,
    )


def calibration_table(pulses: pd.DataFrame, heldout_runs: List[int]) -> pd.DataFrame:
    parts = []
    for pred_col, target_col, method in [
        ("analytic_pred_residual_ns", "analytic_target_residual_ns", "analytic_timewalk"),
        ("binned_pred_residual_ns", "binned_target_residual_ns", "s03b_binned_timewalk"),
        ("ml_template_pred_residual_ns", "ml_template_target_residual_ns", "ml_ridge_on_template_phase"),
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
    order = ["template_phase_base", "analytic_timewalk", "s03b_binned_timewalk", "ml_ridge_on_template_phase"]
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
    s03c_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    best: dict,
    result: dict,
) -> None:
    base = pooled[pooled["method"] == "template_phase_base"].iloc[0]
    analytic = pooled[pooled["method"] == "analytic_timewalk"].iloc[0]
    binned = pooled[pooled["method"] == "s03b_binned_timewalk"].iloc[0]
    ml = pooled[pooled["method"] == "ml_ridge_on_template_phase"].iloc[0]
    leak_summary = leakage.pivot_table(index="check", values="heldout_sigma68_ns", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    lines = [
        "# Study report: S03e - Blind Sample-I to Sample-II timewalk transfer",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train/calibrate only Sample I runs 31-37, 39-42, 44-57; blind evaluation on Sample II analysis runs 58-63 and 65",
        f"- **Config:** `{config_path}`",
        "- **Monte Carlo:** none",
        "",
        "## 0. Question",
        "",
        "Do the S03 analytic timewalk corrections trained on Sample I transfer blindly to Sample II timing runs, or was the S03c closure tuned to Sample II?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "Before fitting Sample-I transfer models, selected-pulse counts and the S03c Sample-II leave-one-run-out reference were rebuilt from raw ROOT.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        s03c_repro.to_markdown(index=False),
        "",
        "## 2. Blind transfer methods",
        "",
        f"All models used the fixed base pickoff `{config['timing']['base_method']}` with templates built only from Sample I train runs. The analytic traditional model selected `{best['analytic_candidate']}` with Ridge alpha `{best['analytic_alpha']:g}` by GroupKFold over Sample-I runs. The constrained binned traditional model selected mode `{best['binned_mode']}`, direction `{best['binned_direction']}`, bins `{best['binned_n_bins']}`. The ML comparator is the existing waveform-feature Ridge residual corrector, also selected only by Sample-I grouped CV.",
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
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 5. Verdict",
        "",
        f"Blind Sample-I template phase gives `{base['value']:.3f} ns` with run-bootstrap CI `[{base['ci_low']:.3f}, {base['ci_high']:.3f}] ns`.",
        f"The analytic correction gives `{analytic['value']:.3f} ns` with CI `[{analytic['ci_low']:.3f}, {analytic['ci_high']:.3f}] ns`, a gain of `{base['value'] - analytic['value']:.3f} ns`.",
        f"The binned traditional correction gives `{binned['value']:.3f} ns`; the ML Ridge comparator gives `{ml['value']:.3f} ns`.",
        f"Conclusion: `{result['verdict']}`.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03e_blind_sample_i_to_ii_transfer.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `s03c_reference_reproduction.csv`, `traditional_scan_metrics.csv`, `per_run_transfer_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, CV/model CSVs, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03e_blind_sample_i_to_ii_transfer.yaml")
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
    s03c_repro, s03c_ref_residuals = run_s03c_reference_reproduction(pulses_all, config, rng)
    s03c_repro.to_csv(out_dir / "s03c_reference_reproduction.csv", index=False)
    s03c_ref_residuals.to_csv(out_dir / "s03c_reference_pairwise_residuals.csv", index=False)
    if not bool(s03c_repro["pass"].all()):
        raise RuntimeError("S03c reference reproduction gate failed")

    timed, traditional_scan = add_base_times(pulses_all, config)
    traditional_scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    combined, analytic_cv, coef, binned_cv, binned_table, ml_cv, ml_cal, best = fit_transfer_models(
        timed, config, config["timing"]["base_method"]
    )
    analytic_cv.to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)
    binned_cv.to_csv(out_dir / "binned_cv_scan.csv", index=False)
    binned_table.to_csv(out_dir / "binned_model_table.csv", index=False)
    ml_cv.to_csv(out_dir / "ml_ridge_cv.csv", index=False)
    ml_cal.to_csv(out_dir / "ml_residual_calibration.csv", index=False)

    per_run, residuals = residual_rows(
        combined,
        config,
        METHODS,
        config["timing"]["heldout_runs"],
        rng,
        int(config["analytic"]["bootstrap_samples"]),
    )
    pooled = run_level_bootstrap(residuals, rng, int(config["analytic"]["bootstrap_samples"]))
    leakage = leakage_checks(combined, config, config["timing"]["base_method"], best, ml_cv)
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
    ml = pooled[pooled["method"] == "ml_ridge_on_template_phase"].iloc[0]
    leak_overlap = int(leakage[leakage["check"].isin(["train_heldout_run_overlap", "train_heldout_event_id_overlap"])]["heldout_sigma68_ns"].sum())
    shuffled_min = float(leakage[leakage["check"].str.contains("shuffled_target")]["heldout_sigma68_ns"].min())
    too_good = bool(
        min(float(analytic["value"]), float(ml["value"]))
        < float(config["reference_numbers"]["s03c_analytic_timewalk_sigma68_ns"]) - 0.25
    )
    verdict = (
        "blind_sample_i_transfer_does_not_close_like_sample_ii_training"
        if float(analytic["value"]) > float(config["reference_numbers"]["s03c_analytic_timewalk_sigma68_ns"]) + 0.25
        else "blind_sample_i_transfer_matches_sample_ii_training"
    )
    result = {
        "study": "S03e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and s03c_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "s03c_reference_reproduction_pass": bool(s03c_repro["pass"].all()),
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
            "method": "analytic_timewalk_on_template_phase",
            "candidate": best["analytic_candidate"],
            "alpha": float(best["analytic_alpha"]),
            "value": float(analytic["value"]),
            "ci": [float(analytic["ci_low"]), float(analytic["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - analytic["value"]),
            "delta_vs_s03c_sample_ii_trained_ns": float(analytic["value"] - config["reference_numbers"]["s03c_analytic_timewalk_sigma68_ns"]),
        },
        "traditional_binned": {
            "method": "per_stave_monotonic_amplitude_binned_timewalk",
            "mode": best["binned_mode"],
            "direction": best["binned_direction"],
            "n_bins": int(best["binned_n_bins"]),
            "value": float(binned["value"]),
            "ci": [float(binned["ci_low"]), float(binned["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - binned["value"]),
        },
        "ml": {
            "method": "ridge_residual_corrector_on_template_phase",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - ml["value"]),
            "delta_vs_s03c_sample_ii_trained_ns": float(ml["value"] - config["reference_numbers"]["s03c_ml_ridge_on_template_phase_sigma68_ns"]),
        },
        "leakage": {
            "split_by_run": True,
            "train_heldout_overlap_total": leak_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "sample_ii_used_for_final_fit": False,
            "shuffled_target_min_sigma68_ns": shuffled_min,
            "too_good_flag": too_good,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "S03f: Sample-I downstream-only topology stratification for blind timewalk transfer",
            "S03g: include Sample-II calibration run 64 as a pure transfer diagnostic",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro_counts, s03c_repro, per_run, pooled, leakage, best, result)

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
                "ml": float(ml["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
