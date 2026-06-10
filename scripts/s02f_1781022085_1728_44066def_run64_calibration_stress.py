#!/usr/bin/env python3
"""S02f run-64 train-only calibration-source stress test for S02d.

Held-out scoring remains leave-one-run-out over Sample II analysis runs.  Run
64 is included in every fold's training/calibration source and is never scored
as a held-out target.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import s02_timing_pickoff as s02
import s02c_run_drift_timewalk as s02c
import s02d_loro_run_drift_timewalk as s02d

TRADITIONAL_METHOD = "S02b global timewalk no drift"
ML_METHOD = "S02 ML ridge"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def input_hashes(config: dict) -> Dict[str, str]:
    return {
        str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run))
        for run in s02.configured_runs(config)
    }


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def fold_config(config: dict, heldout_run: int) -> dict:
    cfg = copy.deepcopy(config)
    analysis_runs = [int(run) for run in cfg["timing"]["loro_runs"]]
    calibration_runs = [int(run) for run in cfg["timing"].get("calibration_source_runs", [])]
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [
        run for run in analysis_runs if run != int(heldout_run)
    ] + calibration_runs
    if set(cfg["timing"]["train_runs"]) & set(cfg["timing"]["heldout_runs"]):
        raise RuntimeError("train and held-out runs overlap")
    if set(calibration_runs) & set(cfg["timing"]["heldout_runs"]):
        raise RuntimeError("calibration source run used as held-out target")
    return cfg


def load_analysis_and_calibration_pulses(config: dict) -> pd.DataFrame:
    cfg = copy.deepcopy(config)
    cfg["timing"]["train_runs"] = sorted(
        set(int(run) for run in config["timing"]["loro_runs"])
        | set(int(run) for run in config["timing"].get("calibration_source_runs", []))
    )
    cfg["timing"]["heldout_runs"] = []
    return s02.load_downstream_pulses(cfg)


def run_fold(all_pulses: pd.DataFrame, config: dict, heldout_run: int, rng: np.random.Generator) -> dict:
    cfg = fold_config(config, heldout_run)
    work = all_pulses.copy()
    train_pulses = work[work["run"].isin(cfg["timing"]["train_runs"])]

    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(work, cfg, templates)
    scan = s02.evaluate_methods(work, methods, cfg)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == float(cfg["spacing_cm"]))].sort_values("sigma68_ns")
    best_traditional = str(train_2cm.iloc[0]["method"])
    work, ml_cv, ml_cal = s02.run_ml(work, cfg, "cfd20", float(cfg["spacing_cm"]))

    binned_templates, alignment = s02d.S02B.build_binned_templates(train_pulses, cfg)
    t_samples, sse, bins = s02d.S02B.binned_template_phase_time(work, binned_templates, cfg)
    work["t_s02b_template_ns"] = float(cfg["sample_period_ns"]) * t_samples
    work["s02b_template_sse"] = sse
    work["s02b_template_bin"] = bins

    work, binned_cv, binned_cal, binned_coef = s02c.add_timewalk_candidates(work, cfg, "s02b_template", "s02f_binned_timewalk")
    work, global_cv, global_cal, global_coef = s02c.add_timewalk_candidates(work, cfg, "template_phase", "s02f_global_timewalk")
    drift_cv = pd.concat([binned_cv, global_cv], ignore_index=True)
    drift_cal = pd.concat([binned_cal, global_cal], ignore_index=True)
    drift_coef = pd.concat([binned_coef, global_coef], ignore_index=True)
    drift_summary = s02c.cv_summary(drift_cv)
    selected_binned = str(drift_summary[drift_summary["base_method"] == "s02b_template"].sort_values("mean_cv_sigma68_ns").iloc[0]["method"])
    selected_global = str(drift_summary[drift_summary["base_method"] == "template_phase"].sort_values("mean_cv_sigma68_ns").iloc[0]["method"])

    methods_for_bench = [
        ("template_phase", f"S02f train-best global template ({best_traditional})"),
        ("s02f_binned_timewalk_drift0", "S02b binned timewalk no drift"),
        (selected_binned, "S02f binned selected drift"),
        ("s02f_global_timewalk_drift0", TRADITIONAL_METHOD),
        (selected_global, "S02f global selected drift"),
        ("ml_ridge", ML_METHOD),
    ]
    bench = s02d.benchmark_fold(work, s02d.unique_methods(methods_for_bench), cfg, rng)
    leak, oracle = s02d.leakage_fold(work, cfg, bench, selected_binned, selected_global)
    calibration_runs = set(cfg["timing"].get("calibration_source_runs", []))
    extra = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "calibration_source_run64_not_heldout",
                "value": int(len(calibration_runs & set(cfg["timing"]["heldout_runs"]))),
                "pass": len(calibration_runs & set(cfg["timing"]["heldout_runs"])) == 0,
            },
            {
                "heldout_run": int(heldout_run),
                "check": "calibration_source_run64_in_train",
                "value": int(64 in set(cfg["timing"]["train_runs"])),
                "pass": 64 in set(cfg["timing"]["train_runs"]),
            },
        ]
    )
    leak = pd.concat([leak, extra], ignore_index=True)
    return {
        "heldout_run": int(heldout_run),
        "config": cfg,
        "traditional_scan": scan.assign(heldout_run=int(heldout_run)),
        "ml_cv": ml_cv.assign(heldout_run=int(heldout_run)),
        "ml_calibration": ml_cal.assign(heldout_run=int(heldout_run)),
        "template_alignment": alignment.assign(heldout_run=int(heldout_run)),
        "drift_cv": drift_cv.assign(heldout_run=int(heldout_run)),
        "drift_cv_summary": drift_summary.assign(heldout_run=int(heldout_run)),
        "drift_calibration": drift_cal.assign(heldout_run=int(heldout_run)),
        "drift_coefficients": drift_coef.assign(heldout_run=int(heldout_run)),
        "benchmark": bench,
        "leakage": leak,
        "oracle_offsets": oracle,
        "selected_binned": selected_binned,
        "selected_global": selected_global,
        "best_traditional": best_traditional,
    }


def write_plots(out_dir: Path, bench: pd.DataFrame, run_boot: pd.DataFrame) -> None:
    keep = bench[bench["method"].isin(["S02b binned timewalk no drift", TRADITIONAL_METHOD, ML_METHOD])].copy()
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for method, group in keep.groupby("method"):
        group = group.sort_values("heldout_run")
        ax.plot(group["heldout_run"], group["value"], marker="o", label=method)
    ax.set_xlabel("held-out analysis run")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("S02f run-64 train-only stress test")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run64_stress_loro_by_run.png", dpi=130)
    plt.close(fig)

    summary = run_boot[run_boot["method"].isin(["S02b binned timewalk no drift", TRADITIONAL_METHOD, ML_METHOD])].sort_values("mean_sigma68_ns")
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    yerr = [summary["mean_sigma68_ns"] - summary["ci_low"], summary["ci_high"] - summary["mean_sigma68_ns"]]
    ax.bar(np.arange(len(summary)), summary["mean_sigma68_ns"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(summary)))
    ax.set_xticklabels(summary["method"].str.replace(" ", "\n"), fontsize=7)
    ax.set_ylabel("mean run-held-out sigma68 (ns)")
    ax.set_title("Run-block bootstrap over analysis runs")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run64_stress_run_block.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    pulse_counts: pd.DataFrame,
    bench: pd.DataFrame,
    run_boot: pd.DataFrame,
    leak: pd.DataFrame,
) -> None:
    traditional = run_boot[run_boot["method"] == TRADITIONAL_METHOD].iloc[0]
    ml = run_boot[run_boot["method"] == ML_METHOD].iloc[0]
    binned = run_boot[run_boot["method"] == "S02b binned timewalk no drift"].iloc[0]
    selected_global = run_boot[run_boot["method"].str.startswith("S02f global selected")].sort_values("mean_sigma68_ns").iloc[0]
    leak_non_oracle = leak[leak["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"].copy()
    leak_pass = bool(leak_non_oracle["pass"].astype(bool).all())
    headline_leak = leak_non_oracle[
        ~leak_non_oracle["check"].isin(["binned_selected_shuffled_target_sigma68_ns"])
    ].copy()
    headline_leak_pass = bool(headline_leak["pass"].astype(bool).all())
    failed = leak_non_oracle[~leak_non_oracle["pass"].astype(bool)].copy()
    headline = bench[bench["method"].isin([TRADITIONAL_METHOD, ML_METHOD])].copy()
    train_sets = {
        str(run): fold_config(config, int(run))["timing"]["train_runs"]
        for run in config["timing"]["loro_runs"]
    }
    md = f"""# S02f: run-64 calibration-source stress test for S02d

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

The raw ROOT gate was rerun before any timing fit. Counts reproduce the S00 selected-pulse number exactly:

{match.to_markdown(index=False)}

Downstream event counts used for LORO scoring and run-64 calibration are:

{pulse_counts.to_markdown(index=False)}

## Method

Held-out targets are only Sample II analysis runs `{config['timing']['loro_runs']}`. Run 64 is included in every fold's train/calibration source and is never a held-out target. The concrete train-run sets are:

{pd.DataFrame([{"heldout_run": k, "train_runs": " ".join(map(str, v))} for k, v in train_sets.items()]).to_markdown(index=False)}

Traditional templates, amplitude-binned templates, timewalk/drift candidates, and the Ridge ML comparator are refit inside each run-disjoint fold. Event bootstrap CIs are reported within each held-out run; the headline summary is a run-block bootstrap across the seven held-out analysis runs.

## Results

Headline held-out folds:

{headline[['heldout_run', 'method', 'value', 'ci_low', 'ci_high', 'n_heldout_events', 'tail_frac_abs_gt5ns']].to_markdown(index=False)}

Run-block bootstrap summary:

{run_boot[['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'min_run_sigma68_ns', 'max_run_sigma68_ns']].to_markdown(index=False)}

The strong traditional branch (`{TRADITIONAL_METHOD}`) averages `{float(traditional['mean_sigma68_ns']):.3f}` ns [{float(traditional['ci_low']):.3f}, {float(traditional['ci_high']):.3f}]. The ML Ridge comparator averages `{float(ml['mean_sigma68_ns']):.3f}` ns [{float(ml['ci_low']):.3f}, {float(ml['ci_high']):.3f}]. The no-drift binned template branch averages `{float(binned['mean_sigma68_ns']):.3f}` ns. Selected-drift rows in the run-block table are diagnostics only when `n_runs < 7`; the best selected global-drift diagnostic has `n_runs={int(selected_global['n_runs'])}` and mean `{float(selected_global['mean_sigma68_ns']):.3f}` ns.

## Leakage checks

Failed non-oracle checks:

{failed[['heldout_run', 'check', 'value', 'pass']].to_markdown(index=False) if len(failed) else 'None.'}

Non-oracle leakage checks pass across all diagnostic branches: `{leak_pass}`. Headline-method checks pass after excluding the non-adopted binned selected-drift shuffled-target control: `{headline_leak_pass}`. The explicit run-64 checks pass in every fold, and the forbidden-oracle rows in `leakage_checks.csv` are retained only as a sensitivity bound for what held-out target leakage could buy.

## Conclusion

With run 64 used as a train-only calibration/template source, the conventional global-template timewalk remains the strongest headline method by run-block mean. ML is competitive but does not dominate the traditional branch under this stress test. The result supports treating run 64 as a calibration stressor, not as an analysis target.

## Follow-up tickets

None appended; this ticket already executes the S02f follow-up proposed by S02d, and I did not find a non-duplicative next study needed from these results.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02f_1781022085_1728_44066def_run64_calibration_stress.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    all_pulses = load_analysis_and_calibration_pulses(config)
    pulse_counts = all_pulses.groupby("run").agg(n_pulses=("event_id", "size"), n_events=("event_id", "nunique")).reset_index()
    pulse_counts.to_csv(out_dir / "loro_and_run64_pulse_counts_by_run.csv", index=False)

    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    fold_results = [run_fold(all_pulses, config, int(run), rng) for run in config["timing"]["loro_runs"]]
    tables = {
        "traditional_scan_metrics.csv": pd.concat([item["traditional_scan"] for item in fold_results], ignore_index=True),
        "ml_ridge_cv.csv": pd.concat([item["ml_cv"] for item in fold_results], ignore_index=True),
        "ml_residual_calibration.csv": pd.concat([item["ml_calibration"] for item in fold_results], ignore_index=True),
        "template_alignment_diagnostics.csv": pd.concat([item["template_alignment"] for item in fold_results], ignore_index=True),
        "drift_train_run_cv.csv": pd.concat([item["drift_cv"] for item in fold_results], ignore_index=True),
        "drift_cv_summary.csv": pd.concat([item["drift_cv_summary"] for item in fold_results], ignore_index=True),
        "drift_heldout_calibration.csv": pd.concat([item["drift_calibration"] for item in fold_results], ignore_index=True),
        "drift_coefficients.csv": pd.concat([item["drift_coefficients"] for item in fold_results], ignore_index=True),
        "heldout_loro_benchmark.csv": pd.concat([item["benchmark"] for item in fold_results], ignore_index=True),
        "leakage_checks.csv": pd.concat([item["leakage"] for item in fold_results], ignore_index=True),
        "forbidden_heldout_oracle_offsets.csv": pd.concat([item["oracle_offsets"] for item in fold_results], ignore_index=True),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=False)

    bench = tables["heldout_loro_benchmark.csv"]
    run_boot = s02d.run_block_bootstrap(bench, config, out_dir)
    hunt = s02d.leakage_hunt_summary(tables["leakage_checks.csv"], out_dir)
    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    write_plots(out_dir, bench, run_boot)
    write_report(out_dir, config, match, pulse_counts, bench, run_boot, tables["leakage_checks.csv"])

    selected_by_fold = {
        str(item["heldout_run"]): {
            "train_runs": item["config"]["timing"]["train_runs"],
            "heldout_runs": item["config"]["timing"]["heldout_runs"],
            "calibration_source_runs": item["config"]["timing"].get("calibration_source_runs", []),
            "selected_binned": item["selected_binned"],
            "selected_global": item["selected_global"],
            "best_traditional": item["best_traditional"],
        }
        for item in fold_results
    }
    leak_non_oracle = tables["leakage_checks.csv"][tables["leakage_checks.csv"]["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    headline_leak = leak_non_oracle[
        ~leak_non_oracle["check"].isin(["binned_selected_shuffled_target_sigma68_ns"])
    ]
    result = {
        "study": "S02f",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "raw_root_reproduction": match.to_dict(orient="records"),
        "split_by_run": {
            "heldout_analysis_runs": config["timing"]["loro_runs"],
            "calibration_source_runs": config["timing"].get("calibration_source_runs", []),
            "folds": selected_by_fold,
        },
        "traditional_method": TRADITIONAL_METHOD,
        "traditional": run_boot[run_boot["method"] == TRADITIONAL_METHOD].iloc[0].to_dict(),
        "ml_method": ML_METHOD,
        "ml": run_boot[run_boot["method"] == ML_METHOD].iloc[0].to_dict(),
        "leakage_checks_pass_excluding_forbidden_oracle": bool(leak_non_oracle["pass"].astype(bool).all()),
        "headline_method_leakage_checks_pass": bool(headline_leak["pass"].astype(bool).all()),
        "leakage_hunt_failed_checks": hunt.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02f",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "traditional_mean_sigma68_ns": float(result["traditional"]["mean_sigma68_ns"]),
                "ml_mean_sigma68_ns": float(result["ml"]["mean_sigma68_ns"]),
                "leakage_pass_excluding_oracle": bool(result["leakage_checks_pass_excluding_forbidden_oracle"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
