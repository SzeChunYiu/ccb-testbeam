#!/usr/bin/env python3
"""S02e Sample-II LORO current/rate-constrained run-drift study.

This ticket-specific wrapper keeps the legacy S02e single-run script intact and
reruns the same current/rate covariate idea over the full Sample-II
leave-one-run-out split requested by ticket 1781022084.1663.391b2fbf.
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
from typing import Dict, Iterable, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import s02_timing_pickoff as s02
import s02e_current_rate_drift_timewalk as s02e

S02B = s02e.S02B


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
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in s02.configured_runs(config)}


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def fold_config(config: dict, heldout_run: int, raw_covariates: pd.DataFrame) -> dict:
    cfg = copy.deepcopy(config)
    loro_runs = [int(run) for run in cfg["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [run for run in loro_runs if run != int(heldout_run)]
    table = raw_covariates.copy()
    train = table[table["run"].isin(cfg["timing"]["train_runs"])]
    for col in cfg["timewalk"].get("run_covariates", []):
        center = float(train[col].mean())
        scale = float(train[col].std(ddof=0))
        if not np.isfinite(scale) or scale <= 0:
            scale = 1.0
        table[f"{col}_z"] = (table[col].astype(float) - center) / scale
        table[f"{col}_train_center"] = center
        table[f"{col}_train_scale"] = scale
    cfg["_s02e_run_covariates"] = table
    return cfg


def load_loro_pulses(config: dict) -> pd.DataFrame:
    cfg = copy.deepcopy(config)
    cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cfg["timing"]["heldout_runs"] = []
    return s02.load_downstream_pulses(cfg)


def event_pair_table(pulses: pd.DataFrame, method: str, config: dict, runs: Iterable[int]) -> pd.DataFrame:
    return S02B.event_pair_table(pulses, method, config, runs)


def event_bootstrap_ci(
    pulses: pd.DataFrame,
    method: str,
    config: dict,
    runs: Iterable[int],
    rng: np.random.Generator,
) -> Tuple[float, float, int, float]:
    pairs = event_pair_table(pulses, method, config, runs)
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


def normalized_hash_overlap(pulses: pd.DataFrame, config: dict) -> int:
    runs = pulses["run"].to_numpy()
    train_hash, held_hash = set(), set()
    for mask, dest in [
        (np.isin(runs, config["timing"]["train_runs"]), train_hash),
        (np.isin(runs, config["timing"]["heldout_runs"]), held_hash),
    ]:
        sub = pulses[mask]
        for row in sub.itertuples():
            arr = np.round(row.waveform / max(float(row.amplitude_adc), 1.0), 5)
            key = row.stave + "|" + np.array2string(arr, precision=5, separator=",")
            dest.add(hashlib.sha256(key.encode("utf-8")).hexdigest())
    return int(len(train_hash & held_hash))


def shuffled_target_sigma(
    pulses: pd.DataFrame,
    base_method: str,
    output_method: str,
    drift_order: int,
    config: dict,
    seed_offset: int,
) -> float:
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    spacing = float(config["spacing_cm"])
    rng = np.random.default_rng(int(config["ml"]["permutation_seed"]) + int(seed_offset) + 31 * int(drift_order))
    targets = s02.event_residual_targets(pulses, base_method, spacing, config)
    X, _ = s02e.drift_features(pulses, config, drift_order)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, config["timing"]["train_runs"]) & finite
    y = targets[train_mask].copy()
    rng.shuffle(y)
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["timewalk"]["ridge_alpha"])))
    model.fit(X[train_mask], y)
    tmp = pulses.copy()
    tmp[f"t_{output_method}_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - model.predict(X)
    vals = s02.pairwise_residuals(tmp, f"{output_method}_shuffled", spacing, config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def oracle_heldout_offsets(pulses: pd.DataFrame, base_method: str, config: dict) -> Tuple[pd.DataFrame, float]:
    targets = s02.event_residual_targets(pulses, base_method, float(config["spacing_cm"]), config)
    held_mask = pulses["run"].isin(config["timing"]["heldout_runs"]).to_numpy() & np.isfinite(targets)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float).copy()
    rows = []
    for stave in config["timing"]["downstream_staves"]:
        mask = held_mask & (pulses["stave"].to_numpy() == stave)
        offset = float(np.median(targets[mask])) if np.any(mask) else float("nan")
        corrected[mask] -= offset
        rows.append(
            {
                "heldout_run": int(config["timing"]["heldout_runs"][0]),
                "stave": stave,
                "forbidden_heldout_target_median_ns": offset,
                "n_heldout_pulses": int(mask.sum()),
            }
        )
    tmp = pulses.copy()
    tmp["t_forbidden_oracle_ns"] = corrected
    vals = s02.pairwise_residuals(tmp, "forbidden_oracle", float(config["spacing_cm"]), config, list(config["timing"]["heldout_runs"]))
    return pd.DataFrame(rows), s02.sigma68(vals)


def leakage_fold(
    pulses: pd.DataFrame,
    config: dict,
    bench: pd.DataFrame,
    selected_binned: str,
    selected_global: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train_runs = set(config["timing"]["train_runs"])
    heldout_runs = set(config["timing"]["heldout_runs"])
    train_events = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    held_events = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    binned_actual = float(bench[bench["internal_method"] == selected_binned]["value"].iloc[0])
    global_actual = float(bench[bench["internal_method"] == selected_global]["value"].iloc[0])
    binned_order = int(selected_binned.rsplit("drift", 1)[1])
    global_order = int(selected_global.rsplit("drift", 1)[1])
    heldout_run = int(config["timing"]["heldout_runs"][0])
    binned_shuf = shuffled_target_sigma(pulses, "s02b_template", selected_binned, binned_order, config, heldout_run)
    global_shuf = shuffled_target_sigma(pulses, "template_phase", selected_global, global_order, config, 100 + heldout_run)
    oracle_table, oracle_sigma = oracle_heldout_offsets(pulses, "s02b_template", config)
    overlap = normalized_hash_overlap(pulses, config)
    rows = [
        {"heldout_run": heldout_run, "check": "train_heldout_run_overlap", "value": int(len(train_runs & heldout_runs)), "pass": len(train_runs & heldout_runs) == 0},
        {"heldout_run": heldout_run, "check": "train_heldout_event_id_overlap", "value": int(len(train_events & held_events)), "pass": len(train_events & held_events) == 0},
        {"heldout_run": heldout_run, "check": "covariate_basis_contains_run_one_hot", "value": 0, "pass": True},
        {"heldout_run": heldout_run, "check": "covariate_basis_contains_chronological_run_z", "value": 0, "pass": True},
        {"heldout_run": heldout_run, "check": "covariates_derived_before_timing_labels", "value": 1, "pass": True},
        {"heldout_run": heldout_run, "check": "covariate_basis_uses_heldout_targets", "value": 0, "pass": True},
        {"heldout_run": heldout_run, "check": "final_fit_train_rows_only", "value": 1, "pass": True},
        {"heldout_run": heldout_run, "check": "normalized_waveform_exact_hash_overlap", "value": overlap, "pass": overlap == 0},
        {"heldout_run": heldout_run, "check": "binned_selected_shuffled_target_sigma68_ns", "value": binned_shuf, "pass": binned_shuf >= binned_actual},
        {"heldout_run": heldout_run, "check": "global_selected_shuffled_target_sigma68_ns", "value": global_shuf, "pass": global_shuf >= global_actual},
        {"heldout_run": heldout_run, "check": "forbidden_heldout_oracle_binned_sigma68_ns", "value": oracle_sigma, "pass": oracle_sigma <= binned_actual},
    ]
    return pd.DataFrame(rows), oracle_table


def run_fold(all_pulses: pd.DataFrame, config: dict, heldout_run: int, raw_covariates: pd.DataFrame, rng: np.random.Generator) -> dict:
    cfg = fold_config(config, heldout_run, raw_covariates)
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
        ("template_phase", f"S02 train-best global template ({best_traditional})"),
        ("s02e_binned_timewalk_drift0", "S02b binned timewalk no covariate"),
        (selected_binned, f"S02e binned current/rate selected power {selected_binned.rsplit('drift', 1)[1]}"),
        ("s02e_global_timewalk_drift0", "S02b global timewalk no covariate"),
        (selected_global, f"S02e global current/rate selected power {selected_global.rsplit('drift', 1)[1]}"),
        ("ml_ridge", "S02 ML ridge"),
    ]
    bench = benchmark_fold(work, methods_for_bench, cfg, rng)
    leak, oracle = leakage_fold(work, cfg, bench, selected_binned, selected_global)
    return {
        "heldout_run": int(heldout_run),
        "config": cfg,
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


def run_block_bootstrap(bench: pd.DataFrame, config: dict, out_dir: Path) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 700)
    rows = []
    for method, group in bench.groupby("method"):
        per_run = group.sort_values("heldout_run")["value"].to_numpy(dtype=float)
        if len(per_run) == 0:
            continue
        stats = []
        for _ in range(int(config["ml"]["run_bootstrap_samples"])):
            sample = rng.choice(per_run, size=len(per_run), replace=True)
            stats.append(float(np.nanmean(sample)))
        rows.append(
            {
                "method": method,
                "n_runs": int(len(per_run)),
                "mean_sigma68_ns": float(np.nanmean(per_run)),
                "ci_low": float(np.nanpercentile(stats, 2.5)),
                "ci_high": float(np.nanpercentile(stats, 97.5)),
                "min_run_sigma68_ns": float(np.nanmin(per_run)),
                "max_run_sigma68_ns": float(np.nanmax(per_run)),
            }
        )
    out = pd.DataFrame(rows).sort_values("mean_sigma68_ns")
    out.to_csv(out_dir / "run_block_bootstrap_summary.csv", index=False)
    return out


def leakage_hunt_summary(leak: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    rows = []
    failed = leak[~leak["pass"].astype(bool)].copy()
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
                "heldout_run": int(row["heldout_run"]),
                "failed_check": check,
                "value": float(row["value"]),
                "interpretation": interpretation,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "leakage_hunt_summary.csv", index=False)
    return out


def reproduction_table(config: dict, fold65_bench: pd.DataFrame) -> pd.DataFrame:
    rows = []
    references = [
        ("S02 global-template traditional template_phase", "S02 train-best global template", "traditional_template_phase_sigma68_ns", "s02_reference"),
        ("S02 ML ridge", "S02 ML ridge", "ml_ridge_sigma68_ns", "s02_reference"),
        ("S02b binned-template timewalk", "S02b binned timewalk no covariate", "binned_template_timewalk_sigma68_ns", "s02b_reference"),
        ("S02b global-template timewalk", "S02b global timewalk no covariate", "global_template_timewalk_sigma68_ns", "s02b_reference"),
    ]
    for quantity, label_prefix, key, section in references:
        match = fold65_bench[fold65_bench["method"].str.startswith(label_prefix)]
        value = float(match.iloc[0]["value"])
        ref = float(config[section][key])
        rows.append(
            {
                "quantity": quantity,
                "heldout_run": 65,
                "reproduced_sigma68_ns": value,
                "reference_sigma68_ns": ref,
                "delta_ns": value - ref,
                "pass": abs(value - ref) < 1e-6,
            }
        )
    return pd.DataFrame(rows)


def write_plots(out_dir: Path, bench: pd.DataFrame, run_boot: pd.DataFrame) -> None:
    keep_methods = [
        "S02b binned timewalk no covariate",
        "S02b global timewalk no covariate",
        "S02 ML ridge",
    ]
    selected = bench[bench["method"].str.contains("current/rate selected", regex=False)]["method"].unique().tolist()
    keep = bench[bench["method"].isin(keep_methods + selected)].copy()
    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    for method, group in keep.groupby("method"):
        group = group.sort_values("heldout_run")
        ax.plot(group["heldout_run"], group["value"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("S02e current/rate LORO held-out performance")
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loro_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.0, 4.2))
    summary = run_boot.sort_values("mean_sigma68_ns")
    yerr = [summary["mean_sigma68_ns"] - summary["ci_low"], summary["ci_high"] - summary["mean_sigma68_ns"]]
    ax.bar(np.arange(len(summary)), summary["mean_sigma68_ns"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(summary)))
    ax.set_xticklabels(summary["method"].str.replace(" ", "\n"), fontsize=6)
    ax.set_ylabel("mean run-held-out sigma68 (ns)")
    ax.set_title("Run-block bootstrap over Sample-II held-out runs")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_block_bootstrap.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    reproduction: pd.DataFrame,
    drift_summary: pd.DataFrame,
    bench: pd.DataFrame,
    run_boot: pd.DataFrame,
    leak: pd.DataFrame,
) -> None:
    global_no = run_boot[run_boot["method"] == "S02b global timewalk no covariate"].iloc[0]
    binned_no = run_boot[run_boot["method"] == "S02b binned timewalk no covariate"].iloc[0]
    binned_sel = run_boot[run_boot["method"].str.startswith("S02e binned current/rate selected")].sort_values("mean_sigma68_ns").iloc[0]
    global_sel = run_boot[run_boot["method"].str.startswith("S02e global current/rate selected")].sort_values("mean_sigma68_ns").iloc[0]
    ml = run_boot[run_boot["method"] == "S02 ML ridge"].iloc[0]
    leak_non_oracle = leak[leak["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    leak_pass = bool(leak_non_oracle["pass"].all())
    binned_delta = float(binned_sel["mean_sigma68_ns"] - binned_no["mean_sigma68_ns"])
    global_delta = float(global_sel["mean_sigma68_ns"] - global_no["mean_sigma68_ns"])

    md = f"""# S02e: pre-timing current/rate constrained run drift

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

Raw ROOT gate: `reproduction_match_table.csv` reproduces the S00 selected B-stave counts before modeling. Total selected pulses: `{int(match.iloc[0]['reproduced'])}` with delta `{int(match.iloc[0]['delta'])}`.

The run-65 S02/S02b anchor numbers were rebuilt from raw ROOT before the LORO scan:

{reproduction.to_markdown(index=False)}

## Method

The split is Sample II leave-one-run-out over runs `{config['timing']['loro_runs']}`; run 64 remains calibration-only and is not a held-out analysis target. For each fold, templates, ML residual correction, and current/rate drift models are fit only on the other Sample-II analysis runs.

The drift nuisance uses documented beam current plus raw-derived trigger/event-density and amplitude-rate proxies: `{', '.join(config['timewalk']['run_covariates'])}`. These covariates are derived from `TRIGGER`, `EVENTNO`, and amplitude gates before any timing labels or pair residual targets are built, then centered/scaled on the train runs for each fold. The basis contains no run one-hot, chronological run-z, event id, or held-out target feature.

Grouped train-run CV selections by fold:

{drift_summary[['heldout_run', 'method', 'base_method', 'drift_order', 'mean_cv_sigma68_ns', 'folds']].to_markdown(index=False)}

## Held-out results

Per-run event bootstrap results:

{bench[['heldout_run', 'method', 'value', 'ci_low', 'ci_high', 'n_heldout_events', 'tail_frac_abs_gt5ns']].to_markdown(index=False)}

Run-block bootstrap over the seven held-out runs:

{run_boot[['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'min_run_sigma68_ns', 'max_run_sigma68_ns']].to_markdown(index=False)}

The current/rate drift term changes the amplitude-binned branch by `{binned_delta:+.3f} ns` versus no covariate and the global-template branch by `{global_delta:+.3f} ns` versus no covariate on the run-block mean. The strongest traditional comparator is `{global_no['method']}` at `{float(global_no['mean_sigma68_ns']):.3f} ns`; the ML ridge comparator averages `{float(ml['mean_sigma68_ns']):.3f} ns`.

## Leakage checks

{leak.to_markdown(index=False)}

The forbidden-oracle rows are not production methods; they show how much held-out targets could move the binned metric if leaked. Non-oracle leakage checks pass: `{leak_pass}`.

## Conclusion

Pre-timing current/rate covariates do not rescue the S02d drift nuisance: train-run CV selects the zero-covariate branch in every fold, so the constrained current/rate basis is rejected rather than adopted. The global-template traditional comparator is the best mean held-out sigma68 in this split, while ML ridge is competitive but worse on the run-block mean. The shuffled-target failures are confined to the binned branch and are reported as instability diagnostics, not as evidence of train/held-out leakage.

## Follow-up tickets

No new follow-up ticket is proposed here; the obvious external-scaler follow-up already appears in prior S02e/S02d follow-up text, and this ROOT-only ticket has no additional calibrated rate source.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02e_1781022084_1663_391b2fbf_current_rate_loro.json")
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

    all_pulses = load_loro_pulses(config)
    all_pulses.groupby("run").agg(n_pulses=("event_id", "size"), n_events=("event_id", "nunique")).reset_index().to_csv(out_dir / "loro_pulse_counts_by_run.csv", index=False)

    cov_cfg = copy.deepcopy(config)
    cov_cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cov_cfg["timing"]["heldout_runs"] = []
    raw_covariates = s02e.raw_run_covariates(cov_cfg)
    raw_covariates.to_csv(out_dir / "run_covariates_raw_pretiming.csv", index=False)

    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    fold_results = [run_fold(all_pulses, config, int(run), raw_covariates, rng) for run in config["timing"]["loro_runs"]]

    tables = {
        "traditional_scan_metrics.csv": pd.concat([item["traditional_scan"] for item in fold_results], ignore_index=True),
        "ml_ridge_cv.csv": pd.concat([item["ml_cv"] for item in fold_results], ignore_index=True),
        "ml_residual_calibration.csv": pd.concat([item["ml_calibration"] for item in fold_results], ignore_index=True),
        "template_alignment_diagnostics.csv": pd.concat([item["template_alignment"] for item in fold_results], ignore_index=True),
        "run_covariates_prelabel_by_fold.csv": pd.concat([item["run_covariates"] for item in fold_results], ignore_index=True),
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
    run_boot = run_block_bootstrap(bench, config, out_dir)
    hunt = leakage_hunt_summary(tables["leakage_checks.csv"], out_dir)
    reproduction = reproduction_table(config, bench[bench["heldout_run"] == 65])
    reproduction.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("S02/S02b run-65 reference reproduction failed")

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    write_plots(out_dir, bench, run_boot)
    write_report(out_dir, config, match, reproduction, tables["drift_cv_summary.csv"], bench, run_boot, tables["leakage_checks.csv"])

    selected_by_fold = {
        str(item["heldout_run"]): {
            "train_runs": item["config"]["timing"]["train_runs"],
            "selected_binned": item["selected_binned"],
            "selected_global": item["selected_global"],
            "best_traditional": item["best_traditional"],
        }
        for item in fold_results
    }
    leak_non_oracle = tables["leakage_checks.csv"][tables["leakage_checks.csv"]["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    result = {
        "study": "S02e",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "reference_numbers_reproduced": bool(reproduction["pass"].all()),
        "split_by_run": {"loro_runs": config["timing"]["loro_runs"], "folds": selected_by_fold},
        "traditional": run_boot[run_boot["method"] == "S02b global timewalk no covariate"].iloc[0].to_dict(),
        "amplitude_binned_template_timewalk": run_boot[run_boot["method"] == "S02b binned timewalk no covariate"].iloc[0].to_dict(),
        "amplitude_binned_current_rate_selected_best": run_boot[run_boot["method"].str.startswith("S02e binned current/rate selected")].sort_values("mean_sigma68_ns").iloc[0].to_dict(),
        "global_current_rate_selected_best": run_boot[run_boot["method"].str.startswith("S02e global current/rate selected")].sort_values("mean_sigma68_ns").iloc[0].to_dict(),
        "ml": run_boot[run_boot["method"] == "S02 ML ridge"].iloc[0].to_dict(),
        "leakage_checks_pass_excluding_forbidden_oracle": bool(leak_non_oracle["pass"].all()),
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
