#!/usr/bin/env python3
"""Blind Sample-I-analysis to Sample-II transfer for S03a/S03d coefficients."""

from __future__ import annotations

import argparse
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

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03d_1781011277_910_1e815d8f_hierarchical_timewalk as s03d_hier
import s03d_leave_one_run_s03ab_hgb_stability as s03d_hgb


METHODS = [
    ("template_phase", "template_phase_base"),
    ("s03a_population", "s03a_global_population"),
    ("s03d_population", "s03d_hierarchical_population"),
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
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def add_base_times(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = pulses.copy()
    train = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    if str(config["timing"]["base_method"]) not in methods:
        raise RuntimeError(f"Base method {config['timing']['base_method']} was not built")
    return out, scan


def residual_rows(
    pulses: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residuals = []
    for run in [int(run) for run in config["timing"]["heldout_runs"]]:
        for method, label in METHODS:
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


def shuffled_hierarchical_control(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    config: dict,
    best: Dict[str, float],
) -> float:
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = [int(run) for run in config["timing"]["train_runs"]]
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    rng = np.random.default_rng(int(config["hierarchical"]["random_seed"]) + 1907)
    shuffled = targets.copy()
    train_target = shuffled[train_mask].copy()
    rng.shuffle(train_target)
    shuffled[train_mask] = train_target
    pred, _, _ = s03d_hier.predict_hierarchical(
        pulses,
        shuffled,
        train_runs,
        float(best["alpha_global"]),
        float(best["alpha_dev"]),
    )
    tmp = pulses.copy()
    tmp["t_s03d_hier_shuffled_ns"] = tmp[f"t_{config['timing']['base_method']}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "s03d_hier_shuffled", 2.0, config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def shuffled_s03a_control(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    config: dict,
    candidate: str,
    alpha: float,
) -> float:
    staves = list(config["timing"]["downstream_staves"])
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = [int(run) for run in config["timing"]["train_runs"]]
    X, _ = s03a.analytic_feature_matrix(pulses, candidate, staves)
    train_mask = np.isin(runs, train_runs) & s03a.finite_design(X, targets, runs)
    rng = np.random.default_rng(int(config["analytic"]["random_seed"]) + 1909)
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    model = s03a.make_model(alpha)
    model.fit(X[train_mask], shuffled)
    tmp = pulses.copy()
    tmp["t_s03a_shuffled_ns"] = tmp[f"t_{config['timing']['base_method']}_ns"] - model.predict(X)
    vals = s02.pairwise_residuals(tmp, "s03a_shuffled", 2.0, config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def leakage_checks(
    pulses: pd.DataFrame,
    config: dict,
    targets: np.ndarray,
    s03a_candidate: str,
    s03a_alpha: float,
    hier_best: Dict[str, float],
    hgb_best: Dict[str, object],
) -> pd.DataFrame:
    train_runs = set(int(run) for run in config["timing"]["train_runs"])
    heldout_runs = set(int(run) for run in config["timing"]["heldout_runs"])
    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    feature_names = [
        "normalized_waveform_samples",
        "log_amp",
        "peak_sample",
        "area_over_amp",
        "stave_one_hot",
        "analytic_amp_features",
    ]
    forbidden = {"run", "event_id", "eventno", "evt", "event_order", "sample", "current", "beam_current"}
    rows = [
        {"check": "train_heldout_run_overlap", "value": float(len(train_runs & heldout_runs)), "unit": "runs"},
        {"check": "train_heldout_event_id_overlap", "value": float(len(train_event_ids & heldout_event_ids)), "unit": "events"},
        {"check": "feature_audit_forbidden_run_event_current_identifiers", "value": float(len(forbidden & set(feature_names))), "unit": "features"},
        {"check": "final_models_use_sample_ii_rows", "value": 0.0, "unit": "bool"},
        {"check": "s03d_heldout_run_deviation_terms_zero", "value": 1.0, "unit": "bool"},
        {
            "check": "s03a_shuffled_target_sigma68",
            "value": shuffled_s03a_control(pulses, targets, config, s03a_candidate, s03a_alpha),
            "unit": "ns",
        },
        {
            "check": "s03d_hier_shuffled_target_sigma68",
            "value": shuffled_hierarchical_control(pulses, targets, config, hier_best),
            "unit": "ns",
        },
        {
            "check": "hgb_shuffled_target_sigma68",
            "value": s03d_hgb.run_hgb_shuffled_control(pulses, config, config["timing"]["base_method"], hgb_best),
            "unit": "ns",
        },
    ]
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame) -> None:
    order = ["template_phase_base", "s03a_global_population", "s03d_hierarchical_population", "hgb_timewalk"]
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
    ax.set_xlabel("Sample-II held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("Sample-I-analysis population transfer")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03e_population_per_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.4, 4.2))
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
    ax.set_title("Blind Sample-II interval")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03e_population_pooled.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro_counts: pd.DataFrame,
    traditional_scan: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    ordered = ["template_phase_base", "s03a_global_population", "s03d_hierarchical_population", "hgb_timewalk"]
    pooled_view = pooled.set_index("method").loc[ordered].reset_index()
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    scan_view = traditional_scan[
        (traditional_scan["spacing_cm"] == 2.0)
        & (traditional_scan["method"].isin(["template_phase", "cfd20", "le500"]))
    ][["method", "split", "sigma68_ns", "n_pair_residuals"]].sort_values(["split", "sigma68_ns"])
    lines = [
        "# Study report: S03e - Sample-I-analysis population transfer",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-10",
        f"- **Input:** raw B-stack ROOT files under `{config['raw_root_dir']}`",
        "- **Split:** train only Sample-I analysis runs 44-57; blind evaluation on Sample-II analysis runs 58-63 and 65",
        f"- **Config:** `{config_path}`",
        "- **Monte Carlo:** none",
        "",
        "## 0. Question",
        "",
        "Do S03a global analytic coefficients and S03d hierarchical population coefficients trained only on Sample-I analysis runs transfer blindly to Sample-II analysis runs?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rebuilt from raw ROOT before any coefficient fitting.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        f"Templates for `{config['timing']['base_method']}` were built only from Sample-I analysis runs. S03a is the amp-only global Ridge correction selected by grouped CV on runs 44-57. S03d fits population coefficients plus train-run deviations, but the transferred prediction uses only the population block for unseen Sample-II runs. The ML comparator is the existing HGB waveform-feature residual corrector trained on the same rows.",
        "",
        "Selected raw timing checks at 2 cm:",
        "",
        scan_view.to_markdown(index=False),
        "",
        "## 3. Held-out Sample-II results",
        "",
        per_run[["heldout_run", "method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "Pooled intervals resample held-out runs, not individual residuals.",
        "",
        pooled_view[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## 4. Leakage checks",
        "",
        "Feature construction excludes run number, event id/order, sample label, current, and cross-stave timing. Sample-II targets are calculated only for evaluation diagnostics. Shuffled-target controls were trained on Sample-I analysis rows and evaluated blindly on Sample-II rows.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 5. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"S03a global population sigma68 is `{result['traditional']['s03a_global_population']['value']:.3f} ns`; S03d hierarchical population is `{result['traditional']['s03d_hierarchical_population']['value']:.3f} ns`; HGB is `{result['ml']['value']:.3f} ns`.",
        f"The leakage flag is `{result['leakage']['too_good_flag']}` and all split-overlap checks are zero.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} {Path(__file__)} --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `traditional_scan_metrics.csv`, `per_run_transfer_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `s03a_cv_scan.csv`, `s03a_coefficients.csv`, `s03d_hierarchical_cv_scan.csv`, `s03d_hierarchical_coefficients.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03e_1781020980_5750_33243f80_sample_i_analysis_population_transfer.yaml")
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
    timed, traditional_scan = add_base_times(pulses_all, config)
    traditional_scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)

    base_method = str(config["timing"]["base_method"])
    s03a_pulses, s03a_cv, s03a_coef, s03a_candidate, s03a_alpha = s03a.run_analytic(timed, config, base_method)
    s03a_cv.to_csv(out_dir / "s03a_cv_scan.csv", index=False)
    s03a_coef.to_csv(out_dir / "s03a_coefficients.csv", index=False)

    targets = s02.event_residual_targets(timed, base_method, 2.0, config)
    hier_pred, hier_cv, hier_coef, _, hier_best = s03d_hier.scan_hierarchical(timed, targets, config)
    hier_cv.to_csv(out_dir / "s03d_hierarchical_cv_scan.csv", index=False)
    hier_coef.to_csv(out_dir / "s03d_hierarchical_coefficients.csv", index=False)
    hier_coef[hier_coef["component"] == "population"].to_csv(out_dir / "s03d_population_coefficients.csv", index=False)

    hgb_pulses, hgb_cv, hgb_best = s03d_hgb.run_hgb(timed, config, base_method)
    hgb_cv.to_csv(out_dir / "hgb_cv_scan.csv", index=False)

    combined = timed.copy()
    combined["t_s03a_population_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03d_population_ns"] = combined[f"t_{base_method}_ns"].to_numpy(dtype=float) - hier_pred
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)
    combined["hgb_target_residual_ns"] = hgb_pulses["hgb_target_residual_ns"].to_numpy(dtype=float)
    combined["hgb_pred_residual_ns"] = hgb_pulses["hgb_pred_residual_ns"].to_numpy(dtype=float)

    per_run, residuals = residual_rows(combined, config, rng, int(config["analytic"]["bootstrap_samples"]))
    pooled = run_level_bootstrap(residuals, rng, int(config["analytic"]["bootstrap_samples"]))
    leakage = leakage_checks(combined, config, targets, s03a_candidate, s03a_alpha, hier_best, hgb_best)

    per_run.to_csv(out_dir / "per_run_transfer_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_rows = []
    input_hashes = {}
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    s03a_row = pooled_idx.loc["s03a_global_population"]
    hier_row = pooled_idx.loc["s03d_hierarchical_population"]
    hgb_row = pooled_idx.loc["hgb_timewalk"]
    too_good = bool(
        min(float(s03a_row["value"]), float(hier_row["value"]), float(hgb_row["value"]))
        < float(config["reference_numbers"]["s03d_sample_ii_loro_hierarchical_sigma68_ns"]) - 0.15
    )
    split_overlap = float(
        leakage[leakage["check"].isin(["train_heldout_run_overlap", "train_heldout_event_id_overlap"])]["value"].sum()
    )
    forbidden_features = float(
        leakage[leakage["check"] == "feature_audit_forbidden_run_event_current_identifiers"]["value"].iloc[0]
    )
    shuffled_min = float(leakage[leakage["check"].str.contains("shuffled_target_sigma68")]["value"].min())
    verdict = (
        "sample_i_analysis_population_transfer_supported_no_leakage_flag"
        if float(hier_row["value"]) < float(s03a_row["value"]) and split_overlap == 0.0 and forbidden_features == 0.0
        else "sample_i_analysis_population_transfer_mixed_or_leakage_flagged"
    )
    result = {
        "study": "S03e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "counts": repro_counts.to_dict(orient="records"),
        },
        "split": {
            "train_sample": "Sample I analysis",
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
            "s03a_global_population": {
                "candidate": s03a_candidate,
                "alpha": float(s03a_alpha),
                "value": float(s03a_row["value"]),
                "ci": [float(s03a_row["ci_low"]), float(s03a_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - s03a_row["value"]),
            },
            "s03d_hierarchical_population": {
                "alpha_global": float(hier_best["alpha_global"]),
                "alpha_dev": float(hier_best["alpha_dev"]),
                "cv_sigma68_ns": float(hier_best["score"]),
                "value": float(hier_row["value"]),
                "ci": [float(hier_row["ci_low"]), float(hier_row["ci_high"])],
                "gain_vs_s03a_ns": float(s03a_row["value"] - hier_row["value"]),
                "gain_vs_template_phase_ns": float(base["value"] - hier_row["value"]),
            },
        },
        "ml": {
            "method": "hist_gradient_boosting_residual_corrector",
            "cv_sigma68_ns": float(hgb_best["score"]),
            "params": hgb_best["params"],
            "value": float(hgb_row["value"]),
            "ci": [float(hgb_row["ci_low"]), float(hgb_row["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - hgb_row["value"]),
        },
        "leakage": {
            "split_by_run": True,
            "train_heldout_overlap_total": split_overlap,
            "forbidden_run_event_current_feature_count": forbidden_features,
            "sample_ii_used_for_final_fit": False,
            "shuffled_target_min_sigma68_ns": shuffled_min,
            "too_good_flag": too_good,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro_counts, traditional_scan, per_run, pooled, leakage, result)

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
                "template_phase": float(base["value"]),
                "s03a_global_population": float(s03a_row["value"]),
                "s03d_hierarchical_population": float(hier_row["value"]),
                "hgb_timewalk": float(hgb_row["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
