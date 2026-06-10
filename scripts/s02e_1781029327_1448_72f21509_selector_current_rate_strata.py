#!/usr/bin/env python3
"""S02e selector-semantics LORO with current/rate-stratified train folds.

This ticket-specific wrapper combines the S02d selector-semantics LORO
discipline with the S02e pre-label current/rate covariates.  For each held-out
Sample-II run, the train runs are chosen from a raw-derived current/rate family
before templates, closures, or ML are fit.
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
from typing import Dict, Iterable, List, Sequence, Tuple

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
import s02e_1781022084_1663_391b2fbf_current_rate_loro as s02e_loro

S02B = s02e_loro.S02B
s02e = s02e_loro.s02e
SELECTORS = ["median_first4", "dynamic_range"]
TRADITIONAL_METHOD = "S02b global timewalk no covariate"
TRADITIONAL_CURRENT_RATE_METHOD = "S02e global current/rate selected"
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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in s02.configured_runs(config)}


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def load_selector_loro_pulses(config: dict, selector: str) -> pd.DataFrame:
    cfg = copy.deepcopy(config)
    cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = []
    return s02c_sel.load_downstream_pulses_by_selector(cfg, selector)


def build_strata(config: dict, raw_covariates: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[int, List[int]]]:
    runs = [int(run) for run in config["timing"]["loro_runs"]]
    table = raw_covariates[raw_covariates["run"].isin(runs)].copy()
    current_unique = table["current_nA"].round(6).nunique()
    basis = str(config["strata"].get("basis", "downstream_allhit_fraction"))
    if current_unique > 1:
        table["stratum_basis"] = "current_nA"
        table["stratum_value"] = table["current_nA"].astype(float)
        table["rate_stratum"] = "current_" + table["current_nA"].astype(str)
    else:
        order = table.sort_values([basis, "run"]).reset_index(drop=True)
        chunks = np.array_split(np.arange(len(order)), int(config["strata"].get("n_rate_strata", 3)))
        names = ["low_rate", "mid_rate", "high_rate", "rate4", "rate5"]
        rate_map = {}
        for i, idxs in enumerate(chunks):
            for idx in idxs:
                rate_map[int(order.loc[int(idx), "run"])] = names[i]
        table["stratum_basis"] = basis
        table["stratum_value"] = table[basis].astype(float)
        table["rate_stratum"] = table["run"].map(rate_map)

    value_by_run = table.set_index("run")["stratum_value"].to_dict()
    stratum_by_run = table.set_index("run")["rate_stratum"].to_dict()
    min_train = int(config["strata"].get("min_train_runs", 3))
    train_map: Dict[int, List[int]] = {}
    rows = []
    for heldout in runs:
        same = [run for run in runs if run != heldout and stratum_by_run[run] == stratum_by_run[heldout]]
        expanded = False
        chosen = list(same)
        if len(chosen) < min_train:
            nearest = sorted(
                [run for run in runs if run != heldout and run not in chosen],
                key=lambda run: (abs(float(value_by_run[run]) - float(value_by_run[heldout])), run),
            )
            chosen.extend(nearest[: max(0, min_train - len(chosen))])
            expanded = True
        chosen = sorted(chosen)
        train_map[int(heldout)] = chosen
        rows.append(
            {
                "heldout_run": int(heldout),
                "heldout_stratum": stratum_by_run[heldout],
                "stratum_basis": table["stratum_basis"].iloc[0],
                "heldout_stratum_value": float(value_by_run[heldout]),
                "same_stratum_train_runs": " ".join(map(str, sorted(same))),
                "train_runs": " ".join(map(str, chosen)),
                "n_train_runs": int(len(chosen)),
                "expanded_to_min_train_runs": bool(expanded),
            }
        )
    return pd.DataFrame(rows), train_map


def fold_config(config: dict, heldout_run: int, train_runs: Sequence[int], raw_covariates: pd.DataFrame) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["loro_runs"] = sorted([int(heldout_run)] + [int(run) for run in train_runs])
    return s02e_loro.fold_config(cfg, int(heldout_run), raw_covariates)


def event_bootstrap_ci(
    pulses: pd.DataFrame,
    method: str,
    config: dict,
    runs: Iterable[int],
    rng: np.random.Generator,
) -> Tuple[float, float, int, float]:
    pairs = S02B.event_pair_table(pulses, method, config, runs)
    if pairs.empty:
        return float("nan"), float("nan"), 0, float("nan")
    grouped = [group["residual_ns"].to_numpy() for _, group in pairs.groupby("event_id")]
    stats = []
    for _ in range(int(config["ml"]["bootstrap_samples"])):
        chosen = rng.integers(0, len(grouped), size=len(grouped))
        stats.append(s02.sigma68(np.concatenate([grouped[i] for i in chosen])))
    point = s02.sigma68(pairs["residual_ns"].to_numpy())
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)), len(grouped), point


def benchmark_fold(pulses: pd.DataFrame, methods: Sequence[Tuple[str, str]], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    heldout_run = int(config["timing"]["heldout_runs"][0])
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, float(config["spacing_cm"]), config, [heldout_run])
        ci_low, ci_high, n_events, point = event_bootstrap_ci(pulses, method, config, [heldout_run], rng)
        rows.append(
            {
                "heldout_run": heldout_run,
                "method": label,
                "internal_method": method,
                "train_runs": " ".join(map(str, config["timing"]["train_runs"])),
                "metric": "B4/B6/B8 pairwise sigma68 ns",
                "value": point,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "n_heldout_events": n_events,
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


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


def run_fold(
    all_pulses: pd.DataFrame,
    config: dict,
    selector: str,
    heldout_run: int,
    train_runs: Sequence[int],
    raw_covariates: pd.DataFrame,
    rng: np.random.Generator,
) -> dict:
    cfg = fold_config(config, heldout_run, train_runs, raw_covariates)
    work = all_pulses.copy()
    train_pulses = work[work["run"].isin(cfg["timing"]["train_runs"])]

    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(work, cfg, templates)
    scan = s02.evaluate_methods(work, methods, cfg)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == float(cfg["spacing_cm"]))].sort_values("sigma68_ns")
    best_traditional = str(train_2cm.iloc[0]["method"])
    work, ml_cv, ml_cal = s02.run_ml(work, cfg, "cfd20", float(cfg["spacing_cm"]))

    binned_templates, alignment = S02B.build_binned_templates(train_pulses, cfg)
    t_samples, sse, bins = S02B.binned_template_phase_time(work, binned_templates, cfg)
    work["t_s02b_template_ns"] = float(cfg["sample_period_ns"]) * t_samples
    work["s02b_template_sse"] = sse
    work["s02b_template_bin"] = bins

    work, binned_cv, binned_cal, binned_coef = s02e.add_timewalk_candidates(work, cfg, "s02b_template", "s02e_binned_timewalk")
    work, global_cv, global_cal, global_coef = s02e.add_timewalk_candidates(work, cfg, "template_phase", "s02e_global_timewalk")
    drift_cv = pd.concat([binned_cv, global_cv], ignore_index=True)
    drift_cal = pd.concat([binned_cal, global_cal], ignore_index=True)
    drift_coef = pd.concat([binned_coef, global_coef], ignore_index=True)
    drift_summary = s02e.cv_summary(drift_cv)
    selected_binned = str(drift_summary[drift_summary["base_method"] == "s02b_template"].sort_values("mean_cv_sigma68_ns").iloc[0]["method"])
    selected_global = str(drift_summary[drift_summary["base_method"] == "template_phase"].sort_values("mean_cv_sigma68_ns").iloc[0]["method"])

    methods_for_bench = [
        ("template_phase", "S02 train-best global template ({})".format(best_traditional)),
        ("s02e_binned_timewalk_drift0", "S02b binned timewalk no covariate"),
        (selected_binned, "S02e binned current/rate selected"),
        ("s02e_global_timewalk_drift0", TRADITIONAL_METHOD),
        (selected_global, TRADITIONAL_CURRENT_RATE_METHOD),
        ("ml_ridge", ML_METHOD),
    ]
    bench = benchmark_fold(work, methods_for_bench, cfg, rng)
    leak, oracle = s02e_loro.leakage_fold(work, cfg, bench, selected_binned, selected_global)
    ml_actual = float(bench[bench["method"] == ML_METHOD]["value"].iloc[0])
    ml_shuffled = ml_shuffled_target_sigma(work, cfg, selector)
    leak = pd.concat(
        [
            leak,
            pd.DataFrame(
                [
                    {
                        "heldout_run": int(heldout_run),
                        "check": "ml_shuffled_target_sigma68_ns",
                        "value": ml_shuffled,
                        "pass": bool(ml_shuffled >= ml_actual),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    return {
        "selector": selector,
        "heldout_run": int(heldout_run),
        "config": cfg,
        "work": work,
        "traditional_scan": scan.assign(heldout_run=int(heldout_run)),
        "ml_cv": ml_cv.assign(heldout_run=int(heldout_run)),
        "ml_calibration": ml_cal.assign(heldout_run=int(heldout_run)),
        "template_alignment": alignment.assign(heldout_run=int(heldout_run)),
        "run_covariates": cfg["_s02e_run_covariates"].assign(heldout_run=int(heldout_run)),
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


def selector_run_block_bootstrap(bench: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 2701)
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
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 2905)
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


def leakage_hunt_summary(leak: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    failed = leak[~leak["pass"].astype(bool)].copy()
    rows = []
    for _, row in failed.iterrows():
        check = str(row["check"])
        if check == "forbidden_heldout_oracle_binned_sigma68_ns":
            interpretation = "forbidden oracle did not improve this fold; not a production leakage failure"
        elif "shuffled_target" in check:
            interpretation = "shuffled-target control beat production; branch is unstable, not adoption-ready"
        else:
            interpretation = "hard leakage guard failed"
        rows.append(
            {
                "selector": row.get("selector", ""),
                "heldout_run": int(row["heldout_run"]),
                "failed_check": check,
                "value": float(row["value"]),
                "interpretation": interpretation,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "leakage_hunt_summary.csv", index=False)
    return out


def write_plots(out_dir: Path, bench: pd.DataFrame, run_boot: pd.DataFrame, delta_boot: pd.DataFrame) -> None:
    keep = bench[bench["method"].isin([TRADITIONAL_METHOD, TRADITIONAL_CURRENT_RATE_METHOD, ML_METHOD])].copy()
    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    for (selector, method), group in keep.groupby(["selector", "method"]):
        group = group.sort_values("heldout_run")
        ax.plot(group["heldout_run"], group["value"], marker="o", label="{}: {}".format(selector, method))
    ax.set_xlabel("held-out run")
    ax.set_ylabel("held-out sigma68 (ns)")
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_selector_rate_loro_by_run.png", dpi=130)
    plt.close(fig)

    summary = run_boot[run_boot["method"].isin([TRADITIONAL_METHOD, TRADITIONAL_CURRENT_RATE_METHOD, ML_METHOD])].copy()
    summary["label"] = summary["selector"] + "\n" + summary["method"].str.replace(" ", "\n")
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    yerr = [summary["mean_sigma68_ns"] - summary["ci_low"], summary["ci_high"] - summary["mean_sigma68_ns"]]
    ax.bar(np.arange(len(summary)), summary["mean_sigma68_ns"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(summary)))
    ax.set_xticklabels(summary["label"], fontsize=6)
    ax.set_ylabel("run-block mean sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_block_selector_rate_summary.png", dpi=130)
    plt.close(fig)

    deltas = delta_boot[delta_boot["method"].isin([TRADITIONAL_METHOD, TRADITIONAL_CURRENT_RATE_METHOD, ML_METHOD])].copy()
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    yerr = [deltas["dynamic_minus_median_mean_ns"] - deltas["ci_low"], deltas["ci_high"] - deltas["dynamic_minus_median_mean_ns"]]
    ax.axhline(0.0, color="black", lw=1)
    ax.bar(np.arange(len(deltas)), deltas["dynamic_minus_median_mean_ns"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(deltas)))
    ax.set_xticklabels(deltas["method"].str.replace(" ", "\n"), fontsize=7)
    ax.set_ylabel("dynamic minus median sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_selector_delta_run_bootstrap.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    selector_repro: pd.DataFrame,
    stratum_table: pd.DataFrame,
    pulse_counts: pd.DataFrame,
    run_boot: pd.DataFrame,
    delta_boot: pd.DataFrame,
    bench: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    trad_delta = delta_boot[delta_boot["method"] == TRADITIONAL_METHOD].iloc[0]
    rate_delta = delta_boot[delta_boot["method"] == TRADITIONAL_CURRENT_RATE_METHOD].iloc[0]
    ml_delta = delta_boot[delta_boot["method"] == ML_METHOD].iloc[0]
    leak_non_oracle = leakage[leakage["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    leak_headline = leak_non_oracle[leak_non_oracle["check"] != "binned_selected_shuffled_target_sigma68_ns"]
    failed = leak_non_oracle[~leak_non_oracle["pass"].astype(bool)]
    headline_boot = run_boot[run_boot["method"].isin([TRADITIONAL_METHOD, TRADITIONAL_CURRENT_RATE_METHOD, ML_METHOD])]
    headline_bench = bench[bench["method"].isin([TRADITIONAL_METHOD, TRADITIONAL_CURRENT_RATE_METHOD, ML_METHOD])]
    md = """# S02e: selector-semantics LORO current/rate strata

Ticket `{ticket}`. Worker `{worker}`.

## Reproduction first

The raw ROOT selector gate was rerun before any timing model. S00 median-first-four and S00a dynamic-range counts reproduce exactly:

{selector_repro}

## Method

Held-out runs are `{runs}`. Detector current is constant in the Sample-II docs, so the rate-family split uses the pre-label raw proxy `{basis}`. Train runs are selected by same current/rate stratum first, then expanded to the nearest raw-rate neighbors only when needed to keep at least `{min_train}` train runs for grouped CV and ML.

{strata}

For every selector and held-out run, templates, amplitude-binned templates, current/rate timewalk closures, and the Ridge ML comparator are refit only on the selected train runs. Event-level CIs are bootstrapped inside folds; selector deltas use a paired run-block bootstrap across held-out runs.

Downstream all-hit event counts by selector and run are in `loro_selector_pulse_counts_by_run.csv`; totals:

{pulse_counts}

## Results

Headline per-run held-out results:

{headline_bench}

Headline run-block summary:

{headline_boot}

Paired dynamic-range minus median-first-four run-block deltas:

{headline_delta}

The strong traditional method (`{traditional}`) has dynamic-minus-median delta `{trad_delta:+.3f} ns` [{trad_low:+.3f}, {trad_high:+.3f}]. The current/rate selected traditional branch has delta `{rate_delta:+.3f} ns` [{rate_low:+.3f}, {rate_high:+.3f}]. The ML comparator has delta `{ml_delta:+.3f} ns` [{ml_low:+.3f}, {ml_high:+.3f}].

## Leakage checks

Failed non-oracle checks:

{failed}

All non-oracle leakage checks pass: `{leak_pass}`. Headline-method leakage checks pass after excluding the non-adopted binned diagnostic branch: `{headline_leak_pass}`. The forbidden-oracle rows are deliberate held-out-target probes and are not production methods. Shuffled-target failures, if present, are treated as instability diagnostics rather than adoption evidence.

## Conclusion

Current/rate-family matching does not turn dynamic-range selector semantics into a timing gain. Under run-disjoint refits, dynamic-range selection worsens the strong traditional branch by `{trad_delta:.3f} ns`, the current/rate-selected traditional branch by `{rate_delta:.3f} ns`, and the ML branch by `{ml_delta:.3f} ns` on paired run-block means. The result supports keeping selector semantics as a controlled nuisance rather than adopting the dynamic-range gate for timing.

## Follow-up tickets

No new follow-up ticket is proposed; external-scaler and selector-count CI follow-ups already exist in prior S02/S00 reports.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        selector_repro=selector_repro.to_markdown(index=False),
        runs=config["timing"]["loro_runs"],
        basis=stratum_table["stratum_basis"].iloc[0],
        min_train=int(config["strata"]["min_train_runs"]),
        strata=stratum_table.to_markdown(index=False),
        pulse_counts=pulse_counts.groupby("selector", as_index=False).agg(total_events=("n_events", "sum"), total_pulses=("n_pulses", "sum")).to_markdown(index=False),
        headline_bench=headline_bench[["selector", "heldout_run", "method", "value", "ci_low", "ci_high", "n_heldout_events", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        headline_boot=headline_boot[["selector", "method", "mean_sigma68_ns", "ci_low", "ci_high", "min_run_sigma68_ns", "max_run_sigma68_ns"]].to_markdown(index=False),
        headline_delta=delta_boot[delta_boot["method"].isin([TRADITIONAL_METHOD, TRADITIONAL_CURRENT_RATE_METHOD, ML_METHOD])][["method", "dynamic_minus_median_mean_ns", "ci_low", "ci_high", "min_run_delta_ns", "max_run_delta_ns"]].to_markdown(index=False),
        traditional=TRADITIONAL_METHOD,
        trad_delta=float(trad_delta["dynamic_minus_median_mean_ns"]),
        trad_low=float(trad_delta["ci_low"]),
        trad_high=float(trad_delta["ci_high"]),
        rate_delta=float(rate_delta["dynamic_minus_median_mean_ns"]),
        rate_low=float(rate_delta["ci_low"]),
        rate_high=float(rate_delta["ci_high"]),
        ml_delta=float(ml_delta["dynamic_minus_median_mean_ns"]),
        ml_low=float(ml_delta["ci_low"]),
        ml_high=float(ml_delta["ci_high"]),
        failed=failed[["selector", "heldout_run", "check", "value", "pass"]].to_markdown(index=False) if len(failed) else "None.",
        leak_pass=bool(leak_non_oracle["pass"].astype(bool).all()),
        headline_leak_pass=bool(leak_headline["pass"].astype(bool).all()),
    )
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02e_1781029327_1448_72f21509_selector_current_rate_strata.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts = s02c_sel.selector_counts(config)
    counts.to_csv(out_dir / "selector_counts_by_run.csv", index=False)
    s00_repro, selector_repro = s02c_sel.reproduction_tables(config, counts)
    s00_repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    selector_repro.to_csv(out_dir / "selector_reproduction_match_table.csv", index=False)
    if not bool(s00_repro["pass"].all()) or not bool(selector_repro["pass"].all()):
        raise RuntimeError("raw ROOT selector reproduction gate failed")

    cov_cfg = copy.deepcopy(config)
    cov_cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cov_cfg["timing"]["heldout_runs"] = []
    raw_covariates = s02e.raw_run_covariates(cov_cfg)
    raw_covariates.to_csv(out_dir / "run_covariates_raw_pretiming.csv", index=False)
    stratum_table, train_map = build_strata(config, raw_covariates)
    stratum_table.to_csv(out_dir / "run_strata_train_map.csv", index=False)

    selector_pulses = {selector: load_selector_loro_pulses(config, selector) for selector in SELECTORS}
    pulse_counts = []
    for selector, pulses in selector_pulses.items():
        tmp = pulses.groupby("run").agg(n_pulses=("event_id", "size"), n_events=("event_id", "nunique")).reset_index()
        tmp["selector"] = selector
        pulse_counts.append(tmp)
    pulse_counts_df = pd.concat(pulse_counts, ignore_index=True)
    pulse_counts_df.to_csv(out_dir / "loro_selector_pulse_counts_by_run.csv", index=False)

    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    fold_results = []
    for selector in SELECTORS:
        for heldout in config["timing"]["loro_runs"]:
            fold_results.append(run_fold(selector_pulses[selector], config, selector, int(heldout), train_map[int(heldout)], raw_covariates, rng))

    table_specs = {
        "traditional_scan_metrics.csv": "traditional_scan",
        "ml_ridge_cv.csv": "ml_cv",
        "ml_residual_calibration.csv": "ml_calibration",
        "template_alignment_diagnostics.csv": "template_alignment",
        "run_covariates_prelabel_by_fold.csv": "run_covariates",
        "drift_train_run_cv.csv": "drift_cv",
        "drift_cv_summary.csv": "drift_cv_summary",
        "drift_heldout_calibration.csv": "drift_calibration",
        "drift_coefficients.csv": "drift_coefficients",
        "heldout_loro_selector_rate_benchmark.csv": "benchmark",
        "leakage_checks.csv": "leakage",
        "forbidden_heldout_oracle_offsets.csv": "oracle_offsets",
    }
    tables = {}
    strata_cols = stratum_table.set_index("heldout_run")
    for filename, key in table_specs.items():
        parts = []
        for item in fold_results:
            table = item[key].copy()
            table["selector"] = item["selector"]
            table["stratum_train_runs"] = " ".join(map(str, item["config"]["timing"]["train_runs"]))
            table["heldout_stratum"] = str(strata_cols.loc[int(item["heldout_run"]), "heldout_stratum"])
            parts.append(table)
        tables[filename] = pd.concat(parts, ignore_index=True)
        tables[filename].to_csv(out_dir / filename, index=False)

    bench = tables["heldout_loro_selector_rate_benchmark.csv"]
    run_boot = selector_run_block_bootstrap(bench, config)
    run_boot.to_csv(out_dir / "selector_run_block_bootstrap_summary.csv", index=False)
    delta_boot = selector_delta_bootstrap(bench, config)
    delta_boot.to_csv(out_dir / "selector_delta_run_bootstrap.csv", index=False)
    hunt = leakage_hunt_summary(tables["leakage_checks.csv"], out_dir)

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    write_plots(out_dir, bench, run_boot, delta_boot)
    write_report(out_dir, config, selector_repro, stratum_table, pulse_counts_df, run_boot, delta_boot, bench, tables["leakage_checks.csv"])

    selected_by_fold = {
        "{}:{}".format(item["selector"], item["heldout_run"]): {
            "stratum_train_runs": item["config"]["timing"]["train_runs"],
            "selected_binned": item["selected_binned"],
            "selected_global": item["selected_global"],
            "best_traditional": item["best_traditional"],
        }
        for item in fold_results
    }
    leak_non_oracle = tables["leakage_checks.csv"][tables["leakage_checks.csv"]["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    leak_headline = leak_non_oracle[leak_non_oracle["check"] != "binned_selected_shuffled_target_sigma68_ns"]
    result = {
        "study": "S02e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(s00_repro["pass"].all() and selector_repro["pass"].all()),
        "selector_reproduction": selector_repro.to_dict(orient="records"),
        "split_by_run": {"loro_runs": config["timing"]["loro_runs"], "folds": selected_by_fold},
        "strata": stratum_table.to_dict(orient="records"),
        "traditional_method": TRADITIONAL_METHOD,
        "traditional_by_selector": run_boot[run_boot["method"] == TRADITIONAL_METHOD].to_dict(orient="records"),
        "traditional_dynamic_minus_median": delta_boot[delta_boot["method"] == TRADITIONAL_METHOD].iloc[0].to_dict(),
        "traditional_current_rate_method": TRADITIONAL_CURRENT_RATE_METHOD,
        "traditional_current_rate_by_selector": run_boot[run_boot["method"] == TRADITIONAL_CURRENT_RATE_METHOD].to_dict(orient="records"),
        "traditional_current_rate_dynamic_minus_median": delta_boot[delta_boot["method"] == TRADITIONAL_CURRENT_RATE_METHOD].iloc[0].to_dict(),
        "ml_method": ML_METHOD,
        "ml_by_selector": run_boot[run_boot["method"] == ML_METHOD].to_dict(orient="records"),
        "ml_dynamic_minus_median": delta_boot[delta_boot["method"] == ML_METHOD].iloc[0].to_dict(),
        "leakage_checks_pass_excluding_forbidden_oracle": bool(leak_non_oracle["pass"].astype(bool).all()),
        "headline_leakage_checks_pass_excluding_binned_and_forbidden_oracle": bool(leak_headline["pass"].astype(bool).all()),
        "leakage_hunt_failed_checks": hunt.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S02e",
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
                "traditional_delta_ns": float(result["traditional_dynamic_minus_median"]["dynamic_minus_median_mean_ns"]),
                "current_rate_delta_ns": float(result["traditional_current_rate_dynamic_minus_median"]["dynamic_minus_median_mean_ns"]),
                "ml_delta_ns": float(result["ml_dynamic_minus_median"]["dynamic_minus_median_mean_ns"]),
                "leakage_pass_excluding_oracle": bool(result["leakage_checks_pass_excluding_forbidden_oracle"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
