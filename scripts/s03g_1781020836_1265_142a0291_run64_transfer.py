#!/usr/bin/env python3
"""S03g run-64 pure transfer diagnostic for S03e Sample-I timewalk models."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import s02_timing_pickoff as s02
import s03e_blind_sample_i_to_ii_transfer as s03e


METHODS = s03e.METHODS


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path, block_size=1024 * 1024):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_outputs(out_dir):
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def with_heldout_runs(config, heldout_runs):
    out = copy.deepcopy(config)
    out["timing"]["heldout_runs"] = [int(run) for run in heldout_runs]
    return out


def bootstrap_run64_delta(analysis_residuals, run64_residuals, rng, n_boot):
    rows = []
    analysis_runs = sorted(int(run) for run in analysis_residuals["heldout_run"].unique())
    for method in sorted(analysis_residuals["method"].unique()):
        analysis_group = analysis_residuals[analysis_residuals["method"] == method]
        run64_vals = run64_residuals[run64_residuals["method"] == method]["pairwise_residual_ns"].to_numpy(dtype=float)
        by_run = {
            int(run): sub["pairwise_residual_ns"].to_numpy(dtype=float)
            for run, sub in analysis_group.groupby("heldout_run")
        }
        deltas = []
        for _ in range(int(n_boot)):
            sampled_runs = rng.choice(analysis_runs, size=len(analysis_runs), replace=True)
            analysis_vals = np.concatenate([by_run[int(run)] for run in sampled_runs if len(by_run[int(run)])])
            sampled_run64 = rng.choice(run64_vals, size=len(run64_vals), replace=True)
            deltas.append(s02.sigma68(sampled_run64) - s02.sigma68(analysis_vals))
        ci_low, ci_high = np.percentile(deltas, [2.5, 97.5])
        analysis_value = s02.sigma68(analysis_group["pairwise_residual_ns"].to_numpy(dtype=float))
        run64_value = s02.sigma68(run64_vals)
        rows.append(
            {
                "method": method,
                "analysis_sigma68_ns": float(analysis_value),
                "run64_sigma68_ns": float(run64_value),
                "delta_run64_minus_analysis_ns": float(run64_value - analysis_value),
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                "bootstrap_unit": "analysis_run_blocks_plus_run64_pair_resample",
            }
        )
    return pd.DataFrame(rows)


def run64_rank_table(per_run):
    rows = []
    for method, group in per_run.groupby("method"):
        analysis = group[group["heldout_run"] != 64].copy()
        run64 = group[group["heldout_run"] == 64].iloc[0]
        better_or_equal = int((analysis["value"] <= float(run64["value"])).sum())
        rows.append(
            {
                "method": method,
                "run64_sigma68_ns": float(run64["value"]),
                "analysis_min_sigma68_ns": float(analysis["value"].min()),
                "analysis_median_sigma68_ns": float(analysis["value"].median()),
                "analysis_max_sigma68_ns": float(analysis["value"].max()),
                "run64_rank_ascending_among_8": int(better_or_equal + 1),
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir, per_run, comparison):
    order = ["template_phase_base", "analytic_timewalk", "s03b_binned_timewalk", "ml_ridge_on_template_phase"]
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
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
    ax.axvline(64, color="black", lw=1.0, ls="--")
    ax.set_xlabel("Sample-II run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("Run 64 pure-transfer diagnostic")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03g_run64_per_run_transfer.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    sub = comparison.set_index("method").loc[order].reset_index()
    xpos = np.arange(len(sub))
    ax.bar(xpos, sub["delta_run64_minus_analysis_ns"])
    ax.errorbar(
        xpos,
        sub["delta_run64_minus_analysis_ns"],
        yerr=[
            sub["delta_run64_minus_analysis_ns"] - sub["ci_low"],
            sub["ci_high"] - sub["delta_run64_minus_analysis_ns"],
        ],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.axhline(0.0, color="black", lw=1.0)
    ax.set_xticks(xpos)
    ax.set_xticklabels(sub["method"], rotation=25, ha="right")
    ax.set_ylabel("run64 minus analysis sigma68 (ns)")
    ax.set_title("Calibration-run drift contrast")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03g_run64_delta.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir,
    config_path,
    config,
    repro_counts,
    s03c_repro,
    per_run,
    pooled_analysis,
    comparison,
    ranks,
    leakage,
    best,
    result,
):
    leak_summary = leakage.pivot_table(index="check", values="heldout_sigma68_ns", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    primary = comparison[comparison["method"].isin(["analytic_timewalk", "ml_ridge_on_template_phase"])].copy()
    lines = [
        "# Study report: S03g - Run 64 pure transfer diagnostic",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Author:** `{config['worker']}`",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train/model-select only Sample I runs 31-37, 39-42, 44-57; evaluate Sample-II analysis runs 58-63 and 65 plus diagnostic run 64",
        f"- **Config:** `{config_path}`",
        "- **Monte Carlo:** none",
        "",
        "## 0. Question",
        "",
        "Does Sample-II calibration run 64 agree with the blind Sample-I-to-Sample-II S03e transfer pattern, or does it expose calibration-run drift?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "Before adding run 64, the S00 selected-pulse counts and the S03e/S03c Sample-II analysis reference numbers were rebuilt from raw ROOT.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        s03c_repro.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        f"The base timing is `{config['timing']['base_method']}`. Templates, the analytic traditional correction, the monotone binned traditional correction, and the ML Ridge residual corrector were all trained and selected only on Sample I runs. The selected analytic model was `{best['analytic_candidate']}` with Ridge alpha `{best['analytic_alpha']:g}`; the binned traditional table used `{best['binned_n_bins']}` monotone-decreasing amplitude bins.",
        "",
        "## 3. Run-held diagnostics",
        "",
        per_run[["heldout_run", "method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "Analysis-run pooled intervals resample held-out analysis runs 58-63 and 65.",
        "",
        pooled_analysis[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "The run64-minus-analysis contrast resamples analysis runs as blocks and resamples run64 pair residuals because run 64 is a single diagnostic run.",
        "",
        comparison.to_markdown(index=False),
        "",
        ranks.to_markdown(index=False),
        "",
        "## 4. Leakage checks",
        "",
        "No model input includes run number, event id, event order, cross-stave timing, sample label, or held-out labels. Final fits do not include run 64 or any Sample-II row. Shuffled-target controls were fit on Sample I and evaluated on every Sample-II run including 64.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 5. Verdict",
        "",
        primary[["method", "analysis_sigma68_ns", "run64_sigma68_ns", "delta_run64_minus_analysis_ns", "ci_low", "ci_high"]].to_markdown(index=False),
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        result["interpretation"],
        "",
        "No follow-up ticket was appended: this run64 diagnostic was itself the queued S03g follow-up, and nearby run-drift/topology variants already exist in completed S02/S03/P10 studies.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03g_1781020836_1265_142a0291_run64_transfer.py --config {config_path}",
        "```",
        "",
        "Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, transfer benchmarks, comparison tables, leakage checks, CV/model tables, pair residuals, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03g_1781020836_1265_142a0291_run64_transfer.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["analytic"]["random_seed"]))

    analysis_runs = [int(run) for run in config["timing"]["heldout_runs"]]
    diagnostic_runs = [int(run) for run in config["timing"]["diagnostic_runs"]]
    eval_runs = analysis_runs + diagnostic_runs
    pulse_load_config = with_heldout_runs(config, eval_runs)

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(pulse_load_config)
    s03c_repro, s03c_ref_residuals = s03e.run_s03c_reference_reproduction(pulses_all, config, rng)
    s03c_repro.to_csv(out_dir / "s03c_reference_reproduction.csv", index=False)
    s03c_ref_residuals.to_csv(out_dir / "s03c_reference_pairwise_residuals.csv", index=False)
    if not bool(s03c_repro["pass"].all()):
        raise RuntimeError("S03e/S03c reference reproduction gate failed")

    timed, traditional_scan = s03e.add_base_times(pulses_all, config)
    traditional_scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    combined, analytic_cv, coef, binned_cv, binned_table, ml_cv, ml_cal, best = s03e.fit_transfer_models(
        timed, config, config["timing"]["base_method"]
    )
    analytic_cv.to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)
    binned_cv.to_csv(out_dir / "binned_cv_scan.csv", index=False)
    binned_table.to_csv(out_dir / "binned_model_table.csv", index=False)
    ml_cv.to_csv(out_dir / "ml_ridge_cv.csv", index=False)
    ml_cal.to_csv(out_dir / "ml_residual_calibration.csv", index=False)

    per_run_analysis, residuals_analysis = s03e.residual_rows(
        combined, config, METHODS, analysis_runs, rng, int(config["analytic"]["bootstrap_samples"])
    )
    per_run_diag, residuals_diag = s03e.residual_rows(
        combined, config, METHODS, diagnostic_runs, rng, int(config["analytic"]["bootstrap_samples"])
    )
    per_run = pd.concat([per_run_analysis, per_run_diag], ignore_index=True)
    residuals = pd.concat([residuals_analysis, residuals_diag], ignore_index=True)
    pooled_analysis = s03e.run_level_bootstrap(residuals_analysis, rng, int(config["analytic"]["bootstrap_samples"]))
    comparison = bootstrap_run64_delta(residuals_analysis, residuals_diag, rng, int(config["analytic"]["bootstrap_samples"]))
    ranks = run64_rank_table(per_run)

    leakage_config = with_heldout_runs(config, eval_runs)
    leakage = s03e.leakage_checks(combined, leakage_config, config["timing"]["base_method"], best, ml_cv)
    calibration = s03e.calibration_table(combined, eval_runs)

    per_run.to_csv(out_dir / "per_run_transfer_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    pooled_analysis.to_csv(out_dir / "analysis_run_bootstrap.csv", index=False)
    comparison.to_csv(out_dir / "run64_vs_analysis_delta.csv", index=False)
    ranks.to_csv(out_dir / "run64_rank_table.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    calibration.to_csv(out_dir / "heldout_residual_calibration.csv", index=False)
    plot_outputs(out_dir, per_run, comparison)

    input_rows = []
    input_hashes = {}
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    def row_for(frame, method):
        return frame[frame["method"] == method].iloc[0]

    analytic_cmp = row_for(comparison, "analytic_timewalk")
    binned_cmp = row_for(comparison, "s03b_binned_timewalk")
    ml_cmp = row_for(comparison, "ml_ridge_on_template_phase")
    base_cmp = row_for(comparison, "template_phase_base")
    leak_overlap = int(
        leakage[leakage["check"].isin(["train_heldout_run_overlap", "train_heldout_event_id_overlap"])][
            "heldout_sigma68_ns"
        ].sum()
    )
    shuffled_min = float(leakage[leakage["check"].str.contains("shuffled_target")]["heldout_sigma68_ns"].min())
    too_good = bool(min(float(analytic_cmp["run64_sigma68_ns"]), float(ml_cmp["run64_sigma68_ns"])) < 0.9)
    primary_excludes_zero = (
        float(analytic_cmp["ci_low"]) > 0.0
        or float(analytic_cmp["ci_high"]) < 0.0
        or float(ml_cmp["ci_low"]) > 0.0
        or float(ml_cmp["ci_high"]) < 0.0
    )
    verdict = "run64_exposes_transfer_drift" if primary_excludes_zero else "run64_consistent_with_blind_transfer_pattern"
    interpretation = (
        "Run 64 differs from the analysis-run pool for at least one primary correction after the held-out contrast."
        if primary_excludes_zero
        else "Run 64 falls inside the analysis-run transfer envelope for the analytic and ML primary corrections; no calibration-run drift is resolved by this diagnostic."
    )

    result = {
        "study": "S03g",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and s03c_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "s03e_reference_reproduction_pass": bool(s03c_repro["pass"].all()),
        },
        "split": {
            "train_sample": "Sample I",
            "train_runs": [int(run) for run in config["timing"]["train_runs"]],
            "analysis_runs": analysis_runs,
            "diagnostic_runs": diagnostic_runs,
            "bootstrap_unit": "heldout_run for analysis pool; pair bootstrap within single diagnostic run 64",
            "run64_used_for_fit_or_selection": False,
        },
        "baseline": {
            "method": "template_phase",
            "analysis_sigma68_ns": float(base_cmp["analysis_sigma68_ns"]),
            "run64_sigma68_ns": float(base_cmp["run64_sigma68_ns"]),
            "delta_run64_minus_analysis_ns": float(base_cmp["delta_run64_minus_analysis_ns"]),
            "delta_ci": [float(base_cmp["ci_low"]), float(base_cmp["ci_high"])],
        },
        "traditional": {
            "method": "analytic_timewalk_on_template_phase",
            "candidate": best["analytic_candidate"],
            "alpha": float(best["analytic_alpha"]),
            "analysis_sigma68_ns": float(analytic_cmp["analysis_sigma68_ns"]),
            "run64_sigma68_ns": float(analytic_cmp["run64_sigma68_ns"]),
            "delta_run64_minus_analysis_ns": float(analytic_cmp["delta_run64_minus_analysis_ns"]),
            "delta_ci": [float(analytic_cmp["ci_low"]), float(analytic_cmp["ci_high"])],
        },
        "traditional_binned": {
            "method": "per_stave_monotonic_amplitude_binned_timewalk",
            "mode": best["binned_mode"],
            "direction": best["binned_direction"],
            "n_bins": int(best["binned_n_bins"]),
            "analysis_sigma68_ns": float(binned_cmp["analysis_sigma68_ns"]),
            "run64_sigma68_ns": float(binned_cmp["run64_sigma68_ns"]),
            "delta_run64_minus_analysis_ns": float(binned_cmp["delta_run64_minus_analysis_ns"]),
            "delta_ci": [float(binned_cmp["ci_low"]), float(binned_cmp["ci_high"])],
        },
        "ml": {
            "method": "ridge_residual_corrector_on_template_phase",
            "analysis_sigma68_ns": float(ml_cmp["analysis_sigma68_ns"]),
            "run64_sigma68_ns": float(ml_cmp["run64_sigma68_ns"]),
            "delta_run64_minus_analysis_ns": float(ml_cmp["delta_run64_minus_analysis_ns"]),
            "delta_ci": [float(ml_cmp["ci_low"]), float(ml_cmp["ci_high"])],
        },
        "leakage": {
            "split_by_run": True,
            "train_heldout_overlap_total": leak_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "sample_ii_or_run64_used_for_final_fit": False,
            "shuffled_target_min_sigma68_ns": shuffled_min,
            "too_good_flag": too_good,
        },
        "verdict": verdict,
        "interpretation": interpretation,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "follow_up_ticket_appended": False,
        "follow_up_skip_reason": "Skipped to avoid duplicating existing S02/S03/P10 run-drift and topology-transfer studies.",
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(
        out_dir,
        config_path,
        config,
        repro_counts,
        s03c_repro,
        per_run,
        pooled_analysis,
        comparison,
        ranks,
        leakage,
        best,
        result,
    )

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03g",
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
                "analytic_delta_run64_minus_analysis_ns": float(analytic_cmp["delta_run64_minus_analysis_ns"]),
                "ml_delta_run64_minus_analysis_ns": float(ml_cmp["delta_run64_minus_analysis_ns"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
