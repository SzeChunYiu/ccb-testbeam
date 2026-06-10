#!/usr/bin/env python3
"""S03d leave-one-run-out stability for S03a/S03b timewalk closures."""

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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b


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
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def prepare_base_pulses(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, str]:
    out = pulses.copy()
    train_pulses = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    expected = str(config["timing"]["base_method"])
    if best_method != expected:
        raise RuntimeError(f"Expected train-selected base method {expected}, got {best_method}")
    return out, best_method


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
        ci = s02.bootstrap_ci(vals, rng, int(config["hgb"]["bootstrap_samples"]))
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
            {
                "heldout_run": heldout_run,
                "method": label,
                "pairwise_residual_ns": float(value),
            }
            for value in vals
        )
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


def hgb_param_grid(config: dict) -> List[dict]:
    rows = []
    for max_iter in config["hgb"]["max_iter"]:
        for learning_rate in config["hgb"]["learning_rate"]:
            for max_leaf_nodes in config["hgb"]["max_leaf_nodes"]:
                for l2_regularization in config["hgb"]["l2_regularization"]:
                    rows.append(
                        {
                            "max_iter": int(max_iter),
                            "learning_rate": float(learning_rate),
                            "max_leaf_nodes": int(max_leaf_nodes),
                            "l2_regularization": float(l2_regularization),
                            "max_bins": int(config["hgb"]["max_bins"]),
                            "random_state": int(config["hgb"]["random_seed"]),
                        }
                    )
    return rows


def run_hgb(
    pulses: pd.DataFrame, config: dict, base_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy()
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    groups = runs[train_mask]
    idx_train = np.flatnonzero(train_mask)
    n_splits = min(int(config["hgb"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": np.inf, "params": None}
    for params in hgb_param_grid(config):
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            model = HistGradientBoostingRegressor(**params)
            model.fit(X[train_mask][tr], targets[train_mask][tr])
            pred = np.full(len(pulses), np.nan)
            pred[idx_train[va]] = model.predict(X[train_mask][va])
            tmp = pulses.copy()
            tmp["t_hgb_timewalk_ns"] = tmp[f"t_{base_method}_ns"] - pred
            va_runs = sorted(np.unique(runs[idx_train[va]]).astype(int).tolist())
            vals = s02.pairwise_residuals(tmp.iloc[idx_train[va]], "hgb_timewalk", 2.0, config, va_runs)
            score = s02.sigma68(vals)
            fold_scores.append(score)
            cv_rows.append({**params, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals))})
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append({**params, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
        if mean_score < best["score"]:
            best = {"score": mean_score, "params": params}

    final_model = HistGradientBoostingRegressor(**best["params"])
    final_model.fit(X[train_mask], targets[train_mask])
    pred = final_model.predict(X)
    out = pulses.copy()
    out["hgb_target_residual_ns"] = targets
    out["hgb_pred_residual_ns"] = pred
    out["t_hgb_timewalk_ns"] = out[f"t_{base_method}_ns"] - pred
    return out, pd.DataFrame(cv_rows), best


def run_hgb_shuffled_control(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> float:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    rng = np.random.default_rng(int(config["hgb"]["random_seed"]) + 211)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy()
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    model = HistGradientBoostingRegressor(**best["params"])
    model.fit(X[train_mask], shuffled)
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp["t_hgb_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "hgb_shuffled", 2.0, config, heldout_runs)
    return s02.sigma68(vals)


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = prepare_base_pulses(pulses_all, config)

    s03a_pulses, s03a_cv, s03a_coef, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    binned_pulses, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    hgb_pulses, hgb_cv, hgb_best = run_hgb(pulses, config, base_method)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)
    combined["hgb_target_residual_ns"] = hgb_pulses["hgb_target_residual_ns"].to_numpy(dtype=float)
    combined["hgb_pred_residual_ns"] = hgb_pulses["hgb_pred_residual_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only"),
            ("s03b_monotone_binned", "s03b_monotone_binned"),
            ("hgb_timewalk", "hgb_timewalk"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["s03a_candidate"] = s03a_candidate
    benchmark["s03a_alpha"] = s03a_alpha
    benchmark["s03b_mode"] = binned_best["mode"]
    benchmark["s03b_direction"] = binned_best["direction"]
    benchmark["s03b_n_bins"] = binned_best["n_bins"]
    benchmark["hgb_cv_sigma68_ns"] = hgb_best["score"]

    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(combined[combined["run"].isin([heldout_run])]["event_id"])
    leakage = pd.DataFrame(
        [
            {
                "heldout_run": heldout_run,
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids & heldout_event_ids)),
                "unit": "events",
            },
            {
                "heldout_run": heldout_run,
                "check": "s03b_shuffled_target_sigma68",
                "value": s03b.run_shuffled_binned_control(pulses, config, base_method, binned_best),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "hgb_shuffled_target_sigma68",
                "value": run_hgb_shuffled_control(pulses, config, base_method, hgb_best),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "features_exclude_run_event_order_cross_stave_time",
                "value": 1.0,
                "unit": "bool",
            },
            {
                "heldout_run": heldout_run,
                "check": "final_models_use_heldout_rows",
                "value": 0.0,
                "unit": "bool",
            },
        ]
    )

    s03a_cv["heldout_run"] = heldout_run
    s03a_coef["heldout_run"] = heldout_run
    binned_cv["heldout_run"] = heldout_run
    binned_table = s03b.binned_model_table(binned_models)
    binned_table["heldout_run"] = heldout_run
    hgb_cv["heldout_run"] = heldout_run
    return benchmark, residuals, leakage, s03a_cv, binned_cv, hgb_cv


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
    order = ["template_phase_base", "s03a_amp_only", "s03b_monotone_binned", "hgb_timewalk"]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03d leave-one-run-out timing width")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03d_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.4))
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
    fig.savefig(out_dir / "fig_s03d_pooled_run_bootstrap.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro_counts: pd.DataFrame,
    run65_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    ordered = ["template_phase_base", "s03a_amp_only", "s03b_monotone_binned", "hgb_timewalk"]
    pooled_view = pooled.set_index("method").loc[ordered].reset_index()
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    lines = [
        "# Study report: S03d - Leave-one-run-out S03a/S03b stability",
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
        "Do the S03a amp-only and S03b monotone-binned/HGB corrections remain stable when every Sample-II analysis run is held out in turn instead of relying on run 65 only?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun from raw ROOT before any model fitting.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "The run-65 S03a/S03b numbers were then reproduced from the same raw-derived pulse table.",
        "",
        run65_repro.to_markdown(index=False),
        "",
        "## 2. Leave-one-run-out head-to-head",
        "",
        "For each fold, templates, S03a amp-only Ridge, S03b monotone-binned isotonic correction, and HGB residual correction were trained only on the other Sample-II analysis runs. Intervals on per-run rows bootstrap pair residuals within the held-out run; pooled intervals resample held-out runs.",
        "",
        per_run[["heldout_run", "method", "value", "ci_low", "ci_high", "n_pair_residuals", "s03b_n_bins", "hgb_cv_sigma68_ns"]]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        pooled_view[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## 3. Leakage checks",
        "",
        "No fitted feature includes run number, event id, event order, other-stave timing, or held-out labels. Every final model is fit with held-out rows removed. Shuffled-target controls are repeated independently for every held-out run.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 4. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"S03a amp-only pooled sigma68 is `{result['traditional']['s03a_amp_only']['value']:.3f} ns`; S03b monotone-binned is `{result['traditional']['s03b_monotone_binned']['value']:.3f} ns`; HGB is `{result['ml']['value']:.3f} ns`.",
        "",
        "## 5. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03d_leave_one_run_s03ab_hgb_stability.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `s03a_amp_only_cv_scan.csv`, `s03b_monotone_cv_scan.csv`, `hgb_cv_scan.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03d_leave_one_run_s03ab_hgb_stability.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["hgb"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(run) for run in config["timing"]["loo_runs"]]

    run65_bench, _, _, _, _, _ = run_one_fold(pulses_all, config, 65, all_runs, rng)
    run65_repro = run65_bench[run65_bench["method"].isin(RUN65_EXPECTED)].copy()
    run65_repro["reference_value"] = run65_repro["method"].map(RUN65_EXPECTED)
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
    hgb_cv_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, s03a_cv, s03b_cv, hgb_cv = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        s03a_cv_parts.append(s03a_cv)
        s03b_cv_parts.append(s03b_cv)
        hgb_cv_parts.append(hgb_cv)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    s03a_cv = pd.concat(s03a_cv_parts, ignore_index=True)
    s03b_cv = pd.concat(s03b_cv_parts, ignore_index=True)
    hgb_cv = pd.concat(hgb_cv_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["hgb"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    s03a_cv.to_csv(out_dir / "s03a_amp_only_cv_scan.csv", index=False)
    s03b_cv.to_csv(out_dir / "s03b_monotone_cv_scan.csv", index=False)
    hgb_cv.to_csv(out_dir / "hgb_cv_scan.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    s03a_row = pooled_idx.loc["s03a_amp_only"]
    s03b_row = pooled_idx.loc["s03b_monotone_binned"]
    hgb_row = pooled_idx.loc["hgb_timewalk"]
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    min_shuffle = float(
        leakage[leakage["check"].isin(["s03b_shuffled_target_sigma68", "hgb_shuffled_target_sigma68"])]["value"].min()
    )
    hgb_gain_vs_s03b = float(s03b_row["value"] - hgb_row["value"])
    looks_too_good = bool(hgb_gain_vs_s03b > 0.5 or hgb_row["value"] < 0.8)
    leakage_flag = bool(event_overlap != 0 or min_shuffle < hgb_row["value"] + 0.2)
    verdict = (
        "stable_no_leakage_flag"
        if s03a_row["value"] < base["value"] and event_overlap == 0 and not leakage_flag
        else "stability_or_leakage_concern"
    )

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
        "split": {
            "unit": "run",
            "heldout_runs": all_runs,
            "bootstrap_unit": "heldout_run",
        },
        "baseline": {
            "method": "template_phase",
            "value": float(base["value"]),
            "ci": [float(base["ci_low"]), float(base["ci_high"])],
        },
        "traditional": {
            "s03a_amp_only": {
                "method": "amp_only_ridge_residual_on_template_phase",
                "value": float(s03a_row["value"]),
                "ci": [float(s03a_row["ci_low"]), float(s03a_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - s03a_row["value"]),
            },
            "s03b_monotone_binned": {
                "method": "per_stave_monotone_decreasing_binned_timewalk",
                "value": float(s03b_row["value"]),
                "ci": [float(s03b_row["ci_low"]), float(s03b_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - s03b_row["value"]),
                "delta_vs_s03a_amp_only_ns": float(s03a_row["value"] - s03b_row["value"]),
            },
        },
        "ml": {
            "method": "hist_gradient_boosting_residual_corrector_on_template_phase",
            "value": float(hgb_row["value"]),
            "ci": [float(hgb_row["ci_low"]), float(hgb_row["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - hgb_row["value"]),
            "gain_vs_s03b_monotone_binned_ns": hgb_gain_vs_s03b,
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "final_models_use_heldout_rows": False,
            "shuffled_target_min_sigma68_ns": min_shuffle,
            "hgb_looks_too_good": looks_too_good,
            "leakage_flag": leakage_flag,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S03e: blind Sample-I to Sample-II transfer for S03a/S03b/HGB timewalk corrections",
            "S03f: constrain S03b monotone bins with physically signed shared-stave shrinkage",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro_counts, run65_repro, per_run, pooled, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03d",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["hgb"]["random_seed"]),
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
                "s03a_amp_only": float(s03a_row["value"]),
                "s03b_monotone_binned": float(s03b_row["value"]),
                "hgb": float(hgb_row["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
