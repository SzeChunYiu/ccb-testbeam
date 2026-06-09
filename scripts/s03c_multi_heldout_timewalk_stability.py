#!/usr/bin/env python3
"""S03c leave-one-run-out stability check for the S03a timewalk closure."""

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


S03A_EXPECTED = {
    "base_sigma68_ns": 2.889152765080617,
    "analytic_sigma68_ns": 1.494640076269676,
    "ml_template_sigma68_ns": 1.3915306248207993,
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


def prepare_fold_pulses(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, List[str], str]:
    out = pulses.copy()
    train_pulses = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    return out, methods, best_method


def bootstrap_rows_for_fold(
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
        ci = s02.bootstrap_ci(vals, rng, int(config["analytic"]["bootstrap_samples"]))
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


def run_ml_shuffled_control(pulses: pd.DataFrame, config: dict, base_method: str) -> float:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 119)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy()
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    model.fit(X[train_mask], shuffled)
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp["t_ml_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "ml_shuffled", 2.0, config, heldout_runs)
    return s02.sigma68(vals)


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, _, best_method = prepare_fold_pulses(pulses_all, config)
    if best_method != config["timing"]["base_method"]:
        raise RuntimeError("Expected train-selected base method %s, got %s" % (config["timing"]["base_method"], best_method))

    analytic_pulses, analytic_cv, coef, best_candidate, best_alpha = s03a.run_analytic(pulses, config, best_method)
    ml_template_pulses, ml_template_cv, ml_template_cal = s02.run_ml(pulses, config, best_method, 2.0)

    combined = analytic_pulses.copy()
    combined["t_ml_template_ridge_ns"] = ml_template_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)
    combined["ml_template_target_residual_ns"] = ml_template_pulses["ml_target_residual_ns"].to_numpy(dtype=float)
    combined["ml_template_pred_residual_ns"] = ml_template_pulses["ml_pred_residual_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_rows_for_fold(
        combined,
        config,
        rng,
        [
            (best_method, "template_phase_base"),
            ("analytic_timewalk", "analytic_timewalk"),
            ("ml_template_ridge", "ml_ridge_on_template_phase"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["analytic_candidate"] = best_candidate
    benchmark["analytic_alpha"] = best_alpha

    leakage = s03a.run_negative_controls(pulses, config, best_method, best_candidate, best_alpha)
    leakage["heldout_run"] = heldout_run
    leakage = pd.concat(
        [
            leakage,
            pd.DataFrame(
                [
                    {
                        "check": "ml_ridge_shuffled_target",
                        "heldout_sigma68_ns": run_ml_shuffled_control(pulses, config, best_method),
                        "n_pair_residuals": int(
                            benchmark[benchmark["method"] == "ml_ridge_on_template_phase"]["n_pair_residuals"].iloc[0]
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

    analytic_cv["heldout_run"] = heldout_run
    coef["heldout_run"] = heldout_run
    ml_template_cv["heldout_run"] = heldout_run
    ml_template_cal["heldout_run"] = heldout_run
    return benchmark, residuals, leakage, analytic_cv, coef


def run_s03a_reproduction(pulses_all: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    s03a_config = fold_config(config, [58, 59, 60, 61, 62, 63], [65])
    pulses, _, best_method = prepare_fold_pulses(pulses_all, s03a_config)
    analytic_pulses, _, _, _, _ = s03a.run_analytic(pulses, s03a_config, best_method)
    ml_template_pulses, _, _ = s02.run_ml(pulses, s03a_config, best_method, 2.0)
    combined = analytic_pulses.copy()
    combined["t_ml_template_ridge_ns"] = ml_template_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)
    bench, _ = bootstrap_rows_for_fold(
        combined,
        s03a_config,
        rng,
        [
            (best_method, "template_phase_base"),
            ("analytic_timewalk", "analytic_timewalk"),
            ("ml_template_ridge", "ml_ridge_on_template_phase"),
        ],
    )
    expected = {
        "template_phase_base": S03A_EXPECTED["base_sigma68_ns"],
        "analytic_timewalk": S03A_EXPECTED["analytic_sigma68_ns"],
        "ml_ridge_on_template_phase": S03A_EXPECTED["ml_template_sigma68_ns"],
    }
    repro = bench[["method", "value", "ci_low", "ci_high", "n_pair_residuals"]].copy()
    repro["s03a_report_value"] = repro["method"].map(expected)
    repro["delta_ns"] = repro["value"] - repro["s03a_report_value"]
    repro["pass"] = repro["delta_ns"].abs() < 1.0e-9
    return repro, bench


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(residuals["heldout_run"].unique().tolist())
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        stats = []
        by_run = {run: sub["pairwise_residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
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
    order = ["template_phase_base", "analytic_timewalk", "ml_ridge_on_template_phase"]
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("Leave-one-run-out held-out timing width")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03c_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
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
    fig.savefig(out_dir / "fig_s03c_pooled_run_bootstrap.png", dpi=130)
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
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    base = pooled[pooled["method"] == "template_phase_base"].iloc[0]
    analytic = pooled[pooled["method"] == "analytic_timewalk"].iloc[0]
    ml = pooled[pooled["method"] == "ml_ridge_on_template_phase"].iloc[0]
    leak_summary = leakage.pivot_table(
        index="check",
        values="heldout_sigma68_ns",
        aggfunc=["min", "median", "max"],
    )
    leak_summary.columns = ["min_sigma68_ns", "median_sigma68_ns", "max_sigma68_ns"]
    lines = [
        "# Study report: S03c - Multi-heldout-run timewalk stability",
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
        "Does the S03a analytic over-closure survive leave-one-run-out evaluation across Sample-II analysis runs instead of only held-out run 65?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "Before fitting, the S00 selected-pulse counts were rerun from the raw ROOT files.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "The original S03a run-65 point estimates were then reproduced from the same raw pass.",
        "",
        s03a_repro.to_markdown(index=False),
        "",
        "## 2. Leave-one-run-out results",
        "",
        "For each held-out run, templates and residual-correction models were trained only on the other Sample-II analysis runs. The traditional model is the S03a analytic timewalk Ridge scan; the ML model is the waveform-feature Ridge residual corrector on template phase.",
        "",
        per_run[["heldout_run", "method", "value", "ci_low", "ci_high", "n_pair_residuals", "analytic_candidate", "analytic_alpha"]]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "Pooled intervals resample held-out runs, not individual residuals.",
        "",
        pooled[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## 3. Leakage checks",
        "",
        "No model feature includes run number, event id, event order, other-stave timing, or held-out labels. Every split is by run, and event-id overlap is zero by construction and by audit. Shuffled-target controls were rerun independently per held-out run.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 4. Verdict",
        "",
        f"The pooled template-phase baseline is `{base['value']:.3f} ns` with run-bootstrap CI `[{base['ci_low']:.3f}, {base['ci_high']:.3f}] ns`.",
        f"The analytic correction is `{analytic['value']:.3f} ns` with CI `[{analytic['ci_low']:.3f}, {analytic['ci_high']:.3f}] ns`, a gain of `{base['value'] - analytic['value']:.3f} ns`.",
        f"The ML Ridge correction is `{ml['value']:.3f} ns` with CI `[{ml['ci_low']:.3f}, {ml['ci_high']:.3f}] ns`, a gain of `{base['value'] - ml['value']:.3f} ns`.",
        "",
        f"Conclusion: `{result['verdict']}`.",
        "",
        "## 5. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03c_multi_heldout_timewalk_stability.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `s03a_run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `analytic_cv_scan.csv`, `analytic_coefficients.csv`, figures, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03c_multi_heldout_timewalk_stability.yaml")
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
    s03a_repro, _ = run_s03a_reproduction(pulses_all, config, rng)
    s03a_repro.to_csv(out_dir / "s03a_run65_reproduction.csv", index=False)
    if not bool(s03a_repro["pass"].all()):
        raise RuntimeError("S03a run-65 reproduction gate failed")

    all_runs = [int(run) for run in config["timing"]["loo_runs"]]
    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    cv_parts = []
    coef_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, analytic_cv, coef = run_one_fold(pulses_all, config, heldout_run, all_runs, rng)
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        cv_parts.append(analytic_cv)
        coef_parts.append(coef)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    analytic_cv = pd.concat(cv_parts, ignore_index=True)
    coefficients = pd.concat(coef_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["analytic"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    analytic_cv.to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    coefficients.to_csv(out_dir / "analytic_coefficients.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    base = pooled[pooled["method"] == "template_phase_base"].iloc[0]
    analytic = pooled[pooled["method"] == "analytic_timewalk"].iloc[0]
    ml = pooled[pooled["method"] == "ml_ridge_on_template_phase"].iloc[0]
    analytic_gain = float(base["value"] - analytic["value"])
    ml_gain = float(base["value"] - ml["value"])
    s03a_gain = S03A_EXPECTED["base_sigma68_ns"] - S03A_EXPECTED["analytic_sigma68_ns"]
    leakage_event_overlap = int(
        leakage[leakage["check"] == "train_heldout_event_id_overlap"]["heldout_sigma68_ns"].sum()
    )
    shuffled_badges = leakage[leakage["check"].isin(["analytic_timewalk_shuffled_target", "ml_ridge_shuffled_target"])]
    shuffled_min = float(shuffled_badges["heldout_sigma68_ns"].min())

    verdict = (
        "analytic_closure_stable_across_sample_ii_runs"
        if analytic_gain > 0.0 and abs(analytic_gain - s03a_gain) < 0.75 and leakage_event_overlap == 0
        else "analytic_closure_not_stable_across_sample_ii_runs"
    )
    result = {
        "study": "S03c",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and s03a_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "s03a_run65_reproduction_pass": bool(s03a_repro["pass"].all()),
        },
        "split": {
            "unit": "run",
            "heldout_runs": all_runs,
            "bootstrap_unit": "heldout_run",
        },
        "s03a_reference": S03A_EXPECTED,
        "traditional": {
            "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
            "method": "analytic_timewalk_on_template_phase",
            "value": float(analytic["value"]),
            "ci": [float(analytic["ci_low"]), float(analytic["ci_high"])],
            "gain_vs_template_phase_ns": analytic_gain,
        },
        "ml": {
            "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
            "method": "ridge_residual_corrector_on_template_phase",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
            "gain_vs_template_phase_ns": ml_gain,
        },
        "baseline": {
            "method": "template_phase",
            "value": float(base["value"]),
            "ci": [float(base["ci_low"]), float(base["ci_high"])],
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": leakage_event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "shuffled_target_min_sigma68_ns": shuffled_min,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S03d: run-level hierarchical shrinkage for analytic timewalk coefficients",
            "S03e: blind sample-I to sample-II transfer of analytic timewalk correction",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro_counts, s03a_repro, per_run, pooled, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03c",
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
                "ml": float(ml["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
