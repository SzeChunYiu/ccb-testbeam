#!/usr/bin/env python3
"""S02d selector-semantics LORO timing over Sample II.

This ticket combines the S02c selector-semantics gate with the S02d
leave-one-run-out timing discipline.  Each selector/fold rebuilds templates,
timewalk closures, and the ML comparator using only train runs.
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
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s02c_selector_semantics as s02c_sel
import s02d_loro_run_drift_timewalk as s02d


SELECTORS = ["median_first4", "dynamic_range"]
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
    hashes = {}
    for run in s02.configured_runs(config):
        path = Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"
        hashes[str(path)] = sha256_file(path)
    return hashes


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def load_selector_loro_pulses(config: dict, selector: str) -> pd.DataFrame:
    cfg = copy.deepcopy(config)
    cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = []
    return s02c_sel.load_downstream_pulses_by_selector(cfg, selector)


def selector_run_block_bootstrap(bench: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 1701)
    rows = []
    for (selector, method), group in bench.groupby(["selector", "method"]):
        per_run = group.sort_values("heldout_run")["value"].to_numpy(dtype=float)
        stats = []
        for _ in range(int(config["ml"]["run_bootstrap_samples"])):
            stats.append(float(np.nanmean(rng.choice(per_run, size=len(per_run), replace=True))))
        rows.append(
            {
                "selector": selector,
                "method": method,
                "n_runs": int(len(per_run)),
                "mean_sigma68_ns": float(np.nanmean(per_run)),
                "ci_low": float(np.nanpercentile(stats, 2.5)),
                "ci_high": float(np.nanpercentile(stats, 97.5)),
                "min_run_sigma68_ns": float(np.nanmin(per_run)),
                "max_run_sigma68_ns": float(np.nanmax(per_run)),
            }
        )
    return pd.DataFrame(rows).sort_values(["method", "selector"]).reset_index(drop=True)


def selector_delta_bootstrap(bench: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 1905)
    rows = []
    for method, group in bench.groupby("method"):
        wide = group.pivot(index="heldout_run", columns="selector", values="value").dropna()
        if not set(SELECTORS).issubset(wide.columns) or wide.empty:
            continue
        deltas = (wide["dynamic_range"] - wide["median_first4"]).to_numpy(dtype=float)
        stats = []
        for _ in range(int(config["ml"]["run_bootstrap_samples"])):
            stats.append(float(np.nanmean(rng.choice(deltas, size=len(deltas), replace=True))))
        rows.append(
            {
                "method": method,
                "n_runs": int(len(deltas)),
                "dynamic_minus_median_mean_ns": float(np.nanmean(deltas)),
                "ci_low": float(np.nanpercentile(stats, 2.5)),
                "ci_high": float(np.nanpercentile(stats, 97.5)),
                "min_run_delta_ns": float(np.nanmin(deltas)),
                "max_run_delta_ns": float(np.nanmax(deltas)),
            }
        )
    return pd.DataFrame(rows).sort_values("dynamic_minus_median_mean_ns").reset_index(drop=True)


def ml_shuffled_target_sigma(work: pd.DataFrame, config: dict, selector: str) -> float:
    heldout_run = int(config["timing"]["heldout_runs"][0])
    seed = int(config["ml"]["permutation_seed"]) + 1000 + heldout_run + (53 if selector == "dynamic_range" else 0)
    rng = np.random.default_rng(seed)
    targets = s02.event_residual_targets(work, "cfd20", float(config["spacing_cm"]), config)
    X = s02.feature_matrix(work, list(config["timing"]["downstream_staves"]))
    runs = work["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, config["timing"]["train_runs"]) & finite
    y = targets[train_mask].copy()
    rng.shuffle(y)
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ml"]["ridge_alphas"][-1])))
    model.fit(X[train_mask], y)
    tmp = work.copy()
    tmp["t_ml_ridge_shuffled_ns"] = tmp["t_cfd20_ns"] - model.predict(X)
    vals = s02.pairwise_residuals(tmp, "ml_ridge_shuffled", float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def add_ml_leakage_check(item: dict) -> None:
    bench = item["benchmark"]
    actual = float(bench[bench["method"] == ML_METHOD]["value"].iloc[0])
    shuffled = ml_shuffled_target_sigma(item["work"], item["config"], item["selector"])
    row = {
        "heldout_run": int(item["heldout_run"]),
        "check": "ml_shuffled_target_sigma68_ns",
        "value": shuffled,
        "pass": shuffled >= actual,
    }
    item["leakage"] = pd.concat([item["leakage"], pd.DataFrame([row])], ignore_index=True)


def write_plots(out_dir: Path, bench: pd.DataFrame, run_boot: pd.DataFrame, delta_boot: pd.DataFrame) -> None:
    keep = bench[bench["method"].isin([TRADITIONAL_METHOD, ML_METHOD, "S02b binned timewalk no drift"])].copy()
    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    for (selector, method), group in keep.groupby(["selector", "method"]):
        group = group.sort_values("heldout_run")
        ax.plot(group["heldout_run"], group["value"], marker="o", label=f"{selector}: {method}")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("held-out sigma68 (ns)")
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_selector_loro_by_run.png", dpi=130)
    plt.close(fig)

    summary = run_boot[run_boot["method"].isin([TRADITIONAL_METHOD, ML_METHOD])].copy()
    summary["label"] = summary["selector"] + "\n" + summary["method"].str.replace(" ", "\n")
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    yerr = [summary["mean_sigma68_ns"] - summary["ci_low"], summary["ci_high"] - summary["mean_sigma68_ns"]]
    ax.bar(np.arange(len(summary)), summary["mean_sigma68_ns"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(summary)))
    ax.set_xticklabels(summary["label"], fontsize=7)
    ax.set_ylabel("run-block mean sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_block_selector_summary.png", dpi=130)
    plt.close(fig)

    deltas = delta_boot[delta_boot["method"].isin([TRADITIONAL_METHOD, ML_METHOD])].copy()
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    yerr = [deltas["dynamic_minus_median_mean_ns"] - deltas["ci_low"], deltas["ci_high"] - deltas["dynamic_minus_median_mean_ns"]]
    ax.axhline(0.0, color="black", lw=1)
    ax.bar(np.arange(len(deltas)), deltas["dynamic_minus_median_mean_ns"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(deltas)))
    ax.set_xticklabels(deltas["method"].str.replace(" ", "\n"), fontsize=7)
    ax.set_ylabel("dynamic minus median sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_selector_delta_bootstrap.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    selector_repro: pd.DataFrame,
    reference: pd.DataFrame,
    pulse_counts: pd.DataFrame,
    bench: pd.DataFrame,
    run_boot: pd.DataFrame,
    delta_boot: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    trad_delta = delta_boot[delta_boot["method"] == TRADITIONAL_METHOD].iloc[0]
    ml_delta = delta_boot[delta_boot["method"] == ML_METHOD].iloc[0]
    trad_summary = run_boot[run_boot["method"] == TRADITIONAL_METHOD]
    ml_summary = run_boot[run_boot["method"] == ML_METHOD]
    leak_non_oracle = leakage[leakage["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    leak_pass = bool(leak_non_oracle["pass"].astype(bool).all())
    reported_checks = leak_non_oracle[
        ~leak_non_oracle["check"].isin(["binned_selected_shuffled_target_sigma68_ns"])
    ]
    reported_leak_pass = bool(reported_checks["pass"].astype(bool).all())
    headline_bench = bench[bench["method"].isin([TRADITIONAL_METHOD, ML_METHOD])].copy()
    headline_boot = run_boot[run_boot["method"].isin([TRADITIONAL_METHOD, ML_METHOD])].copy()
    headline_delta = delta_boot[delta_boot["method"].isin([TRADITIONAL_METHOD, ML_METHOD])].copy()
    failed_leak = leak_non_oracle[~leak_non_oracle["pass"].astype(bool)].copy()

    md = f"""# S02d: leave-one-run-out selector-semantics timing

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

The raw ROOT selector gate was rerun before any timing model. The S00 median-first-four count and S00a dynamic-range count both reproduce exactly:

{selector_repro.to_markdown(index=False)}

The median-first-four run-65 S02/S02b anchors were also rebuilt from raw ROOT before the LORO selector scan:

{reference.to_markdown(index=False)}

Sample-II LORO downstream event counts by selector are in `loro_selector_pulse_counts_by_run.csv`; the per-run event totals range from `{int(pulse_counts['n_events'].min())}` to `{int(pulse_counts['n_events'].max())}`.

{pulse_counts.groupby('selector', as_index=False).agg(total_events=('n_events', 'sum'), total_pulses=('n_pulses', 'sum')).to_markdown(index=False)}

## Method

Held-out runs are `{config['timing']['loro_runs']}`. For every held-out run and selector, templates, amplitude-binned templates, timewalk/drift closures, and the Ridge ML comparator are fit only on the other Sample-II analysis runs. The split key is run; event ids and waveform hashes are checked between train and held-out sets. CIs inside each fold are event bootstraps; selector deltas use a paired run-block bootstrap over the seven held-out runs.

## Results

Headline per-run held-out bootstrap results:

{headline_bench[['selector', 'heldout_run', 'method', 'value', 'ci_low', 'ci_high', 'n_heldout_events', 'tail_frac_abs_gt5ns']].to_markdown(index=False)}

Headline run-block summary:

{headline_boot[['selector', 'method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'min_run_sigma68_ns', 'max_run_sigma68_ns']].to_markdown(index=False)}

Paired dynamic-range minus median-first-four deltas for headline methods:

{headline_delta[['method', 'dynamic_minus_median_mean_ns', 'ci_low', 'ci_high', 'min_run_delta_ns', 'max_run_delta_ns']].to_markdown(index=False)}

The strong traditional method (`{TRADITIONAL_METHOD}`) has dynamic-minus-median delta `{float(trad_delta['dynamic_minus_median_mean_ns']):+.3f} ns` [{float(trad_delta['ci_low']):+.3f}, {float(trad_delta['ci_high']):+.3f}]. The ML comparator (`{ML_METHOD}`) has delta `{float(ml_delta['dynamic_minus_median_mean_ns']):+.3f} ns` [{float(ml_delta['ci_low']):+.3f}, {float(ml_delta['ci_high']):+.3f}].

Traditional summaries:

{trad_summary[['selector', 'mean_sigma68_ns', 'ci_low', 'ci_high']].to_markdown(index=False)}

ML summaries:

{ml_summary[['selector', 'mean_sigma68_ns', 'ci_low', 'ci_high']].to_markdown(index=False)}

Full method and diagnostic tables are in `heldout_loro_selector_benchmark.csv`, `selector_run_block_bootstrap_summary.csv`, `selector_delta_run_bootstrap.csv`, and `leakage_checks.csv`.

## Leakage checks

Failed non-oracle checks:

{failed_leak[['selector', 'heldout_run', 'check', 'value', 'pass']].to_markdown(index=False) if len(failed_leak) else 'None.'}

Non-oracle leakage checks pass: `{leak_pass}`. Reported-method leakage checks pass after excluding the non-adopted binned branch: `{reported_leak_pass}`. The forbidden-oracle rows are deliberately not production methods; they show how much better the metric could look if held-out targets leaked into a correction. The binned branch has shuffled-target failures and is not used for the headline selector claim.

## Conclusion

Dynamic-range selection increases the raw selected-pulse population, but under run-disjoint refits it worsens the strong traditional method by `{float(trad_delta['dynamic_minus_median_mean_ns']):.3f} ns` and worsens the ML comparator by `{float(ml_delta['dynamic_minus_median_mean_ns']):.3f} ns` on the paired run-block mean. The selector semantics are therefore a gate-composition nuisance rather than an adoption-ready timing gain.

## Follow-up tickets

- S02e: constrain selector-semantics LORO by detector-current or trigger-rate strata before timing fits.
- S00c: add a raw-ROOT CI gate that recomputes median-first-four and dynamic-range selected counts and fails on selector drift.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02d_1781013144_325e4c97_selector_semantics_loro.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    counts = s02c_sel.selector_counts(config)
    counts.to_csv(out_dir / "selector_counts_by_run.csv", index=False)
    s00_repro, selector_repro = s02c_sel.reproduction_tables(config, counts)
    s00_repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    selector_repro.to_csv(out_dir / "selector_reproduction_match_table.csv", index=False)
    if not bool(s00_repro["pass"].all()) or not bool(selector_repro["pass"].all()):
        raise RuntimeError("raw ROOT selector reproduction gate failed")

    selector_pulses = {selector: load_selector_loro_pulses(config, selector) for selector in SELECTORS}
    pulse_counts = []
    for selector, pulses in selector_pulses.items():
        tmp = pulses.groupby("run").agg(n_pulses=("event_id", "size"), n_events=("event_id", "nunique")).reset_index()
        tmp["selector"] = selector
        pulse_counts.append(tmp)
    pulse_counts_df = pd.concat(pulse_counts, ignore_index=True)
    pulse_counts_df.to_csv(out_dir / "loro_selector_pulse_counts_by_run.csv", index=False)

    fold_results = []
    for selector in SELECTORS:
        for run in config["timing"]["loro_runs"]:
            item = s02d.run_fold(selector_pulses[selector], config, int(run), rng)
            item["selector"] = selector
            add_ml_leakage_check(item)
            fold_results.append(item)

    table_specs = {
        "traditional_scan_metrics.csv": "traditional_scan",
        "ml_ridge_cv.csv": "ml_cv",
        "ml_residual_calibration.csv": "ml_calibration",
        "template_alignment_diagnostics.csv": "template_alignment",
        "drift_train_run_cv.csv": "drift_cv",
        "drift_cv_summary.csv": "drift_cv_summary",
        "drift_heldout_calibration.csv": "drift_calibration",
        "drift_coefficients.csv": "drift_coefficients",
        "heldout_loro_selector_benchmark.csv": "benchmark",
        "leakage_checks.csv": "leakage",
        "forbidden_heldout_oracle_offsets.csv": "oracle_offsets",
    }
    tables = {}
    for filename, key in table_specs.items():
        parts = []
        for item in fold_results:
            table = item[key].copy()
            table["selector"] = item["selector"]
            parts.append(table)
        tables[filename] = pd.concat(parts, ignore_index=True)
        tables[filename].to_csv(out_dir / filename, index=False)

    bench = tables["heldout_loro_selector_benchmark.csv"]
    run_boot = selector_run_block_bootstrap(bench, config)
    run_boot.to_csv(out_dir / "selector_run_block_bootstrap_summary.csv", index=False)
    delta_boot = selector_delta_bootstrap(bench, config)
    delta_boot.to_csv(out_dir / "selector_delta_run_bootstrap.csv", index=False)

    median_fold65 = bench[(bench["selector"] == "median_first4") & (bench["heldout_run"] == 65)]
    reference = s02d.reproduction_table(config, median_fold65)
    reference.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    if not bool(reference["pass"].all()):
        raise RuntimeError("median-first-four run-65 reference reproduction failed")

    leakage = tables["leakage_checks.csv"]
    leakage_non_oracle = leakage[leakage["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    leakage_reported = leakage_non_oracle[
        ~leakage_non_oracle["check"].isin(["binned_selected_shuffled_target_sigma68_ns"])
    ]
    leakage_failed = leakage_non_oracle[~leakage_non_oracle["pass"].astype(bool)].copy()
    leakage_failed.to_csv(out_dir / "leakage_hunt_failed_non_oracle.csv", index=False)

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    write_plots(out_dir, bench, run_boot, delta_boot)
    write_report(out_dir, config, selector_repro, reference, pulse_counts_df, bench, run_boot, delta_boot, leakage)

    selected_by_fold = {
        f"{item['selector']}:{item['heldout_run']}": {
            "train_runs": item["config"]["timing"]["train_runs"],
            "selected_binned": item["selected_binned"],
            "selected_global": item["selected_global"],
            "best_traditional": item["best_traditional"],
        }
        for item in fold_results
    }
    result = {
        "study": "S02d",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(s00_repro["pass"].all() and selector_repro["pass"].all()),
        "reference_numbers_reproduced": bool(reference["pass"].all()),
        "split_by_run": {"loro_runs": config["timing"]["loro_runs"], "folds": selected_by_fold},
        "traditional_method": TRADITIONAL_METHOD,
        "traditional_by_selector": run_boot[run_boot["method"] == TRADITIONAL_METHOD].to_dict(orient="records"),
        "traditional_dynamic_minus_median": delta_boot[delta_boot["method"] == TRADITIONAL_METHOD].iloc[0].to_dict(),
        "ml_method": ML_METHOD,
        "ml_by_selector": run_boot[run_boot["method"] == ML_METHOD].to_dict(orient="records"),
        "ml_dynamic_minus_median": delta_boot[delta_boot["method"] == ML_METHOD].iloc[0].to_dict(),
        "leakage_checks_pass_excluding_forbidden_oracle": bool(leakage_non_oracle["pass"].astype(bool).all()),
        "reported_method_leakage_checks_pass": bool(leakage_reported["pass"].astype(bool).all()),
        "leakage_hunt_failed_non_oracle": leakage_failed.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [
            "S02e: constrain selector-semantics LORO by detector-current or trigger-rate strata before timing fits.",
            "S00c: add a raw-ROOT CI gate that recomputes median-first-four and dynamic-range selected counts and fails on selector drift.",
        ],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02d",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "traditional_delta_ns": result["traditional_dynamic_minus_median"]["dynamic_minus_median_mean_ns"],
                "ml_delta_ns": result["ml_dynamic_minus_median"]["dynamic_minus_median_mean_ns"],
                "leakage_pass_excluding_oracle": result["leakage_checks_pass_excluding_forbidden_oracle"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
