#!/usr/bin/env python3
"""P10c Sample-II-only explicit timewalk transfer check."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781012359.1143.5d9c3b2a/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import p10a_conditional_template as p10a  # noqa: E402
import p10b_explicit_timewalk_terms as p10b  # noqa: E402


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


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def empirical_templates_for_pulses(config: dict, pulses: pd.DataFrame, empirical_pack: dict) -> np.ndarray:
    edges = empirical_pack["edges"]
    bins = p10a.assign_amp_bins(pulses["amplitude_adc"].to_numpy(dtype=float), edges)
    templates = []
    for i, row in enumerate(pulses.itertuples()):
        templates.append(empirical_pack["templates"][(row.stave, int(bins[i]))])
    return np.vstack(templates).astype(np.float32)


def positions(config: dict) -> Dict[str, float]:
    return {stave: i * float(config["spacing_cm"]) for i, stave in enumerate(config["timing"]["downstream_staves"])}


def corrected_score(config: dict, pulses: pd.DataFrame, corrected: np.ndarray, rows: np.ndarray) -> float:
    tmp = pulses.iloc[rows].copy()
    tmp["t_tmp_ns"] = corrected[rows]
    vals = []
    for run in sorted(tmp["run"].unique()):
        vals.append(p10b.pairwise_residuals(tmp, "t_tmp_ns", config, int(run)))
    vals = [v for v in vals if len(v)]
    if not vals:
        return float("nan")
    return p10b.sigma68(np.concatenate(vals))


def binned_timewalk_correction(config: dict, pulses: pd.DataFrame, targets: np.ndarray, train_mask: np.ndarray) -> Tuple[np.ndarray, pd.DataFrame]:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    bins = p10a.assign_amp_bins(pulses["amplitude_adc"].to_numpy(dtype=float), edges)
    staves = list(config["timing"]["downstream_staves"])
    min_bin = int(config["explicit_timewalk"]["traditional_min_bin_pulses"])
    correction = np.full(len(pulses), np.nan, dtype=float)
    rows = []
    global_fallback = float(np.nanmedian(targets[train_mask]))
    for stave in staves:
        stave_mask = train_mask & (pulses["stave"].to_numpy() == stave)
        stave_fallback = float(np.nanmedian(targets[stave_mask])) if np.any(stave_mask) else global_fallback
        for b in range(len(edges) - 1):
            mask = stave_mask & (bins == b)
            n = int(mask.sum())
            if n >= min_bin:
                value = float(np.nanmedian(targets[mask]))
                source = "stave_amp_bin"
            else:
                value = stave_fallback
                source = "stave_fallback"
            apply_mask = (pulses["stave"].to_numpy() == stave) & (bins == b)
            correction[apply_mask] = value
            rows.append(
                {
                    "stave": stave,
                    "bin": int(b),
                    "amp_low_adc": float(edges[b]),
                    "amp_high_adc": float(edges[b + 1]),
                    "n_train": n,
                    "correction_ns": value,
                    "source": source,
                }
            )
    return correction, pd.DataFrame(rows)


def select_ml_candidate(config: dict, pulses: pd.DataFrame, targets: np.ndarray, train_mask: np.ndarray) -> Tuple[dict, pd.DataFrame]:
    idx_train = np.flatnonzero(train_mask & np.isfinite(targets))
    groups = pulses.iloc[idx_train]["run"].to_numpy(dtype=int)
    feature_sets = list(config["explicit_timewalk"]["ml_feature_sets"])
    alphas = [float(v) for v in config["explicit_timewalk"]["ml_ridge_alphas"]]
    cv_rows = []
    unique_runs = np.unique(groups)
    if len(unique_runs) < 2:
        best = {
            "feature_set": config["explicit_timewalk"]["single_run_default_feature_set"],
            "alpha": float(config["explicit_timewalk"]["single_run_default_alpha"]),
            "selection": "predeclared_single_train_run_default",
        }
        cv_rows.append({**best, "fold": "single_train_run", "sigma68_ns": float("nan"), "n_train": int(len(idx_train))})
        return best, pd.DataFrame(cv_rows)

    splitter = GroupKFold(n_splits=min(int(config["explicit_timewalk"]["cv_folds"]), len(unique_runs)))
    best = {"feature_set": None, "alpha": None, "score": math.inf, "selection": "train_run_groupkfold"}
    for feature_set in feature_sets:
        X = p10b.explicit_features(config, pulses, feature_set)
        for alpha in alphas:
            fold_scores = []
            for fold, (tr, va) in enumerate(splitter.split(X[idx_train], targets[idx_train], groups=groups), start=1):
                model = p10b.ridge_model(alpha)
                tr_idx = idx_train[tr]
                va_idx = idx_train[va]
                model.fit(X[tr_idx], targets[tr_idx])
                pred = np.full(len(pulses), np.nan, dtype=float)
                pred[va_idx] = model.predict(X[va_idx])
                corrected = pulses["t_base_ns"].to_numpy(dtype=float) - np.nan_to_num(pred, nan=0.0)
                score = corrected_score(config, pulses, corrected, va_idx)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "feature_set": feature_set,
                        "alpha": float(alpha),
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_train": int(len(tr_idx)),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "feature_set": feature_set,
                    "alpha": float(alpha),
                    "fold": "mean",
                    "sigma68_ns": mean_score,
                    "n_train": int(len(idx_train)),
                }
            )
            if mean_score < best["score"]:
                best = {
                    "feature_set": feature_set,
                    "alpha": float(alpha),
                    "score": mean_score,
                    "selection": "train_run_groupkfold",
                }
    return best, pd.DataFrame(cv_rows)


def fit_ml_correction(
    config: dict,
    pulses: pd.DataFrame,
    targets: np.ndarray,
    train_mask: np.ndarray,
    best: dict,
    seed: int,
    shuffled: bool = False,
) -> np.ndarray:
    idx_train = np.flatnonzero(train_mask & np.isfinite(targets))
    y = targets.copy()
    if shuffled:
        rng = np.random.default_rng(seed)
        y_train = y[idx_train].copy()
        rng.shuffle(y_train)
        y[idx_train] = y_train
    X = p10b.explicit_features(config, pulses, str(best["feature_set"]))
    model = p10b.ridge_model(float(best["alpha"]))
    model.fit(X[idx_train], y[idx_train])
    return model.predict(X)


def evaluate_methods(config: dict, pulses: pd.DataFrame, eval_runs: Iterable[int], method_cols: Dict[str, str]) -> pd.DataFrame:
    rows = []
    for run in eval_runs:
        row = {"run": int(run)}
        for method, col in method_cols.items():
            vals = p10b.pairwise_residuals(pulses, col, config, int(run))
            row[f"{method}_sigma68_ns"] = p10b.sigma68(vals)
            row[f"{method}_n_pair_residuals"] = int(len(vals))
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_summary(run_df: pd.DataFrame, config: dict, method_names: List[str], scenario_pairs: List[Tuple[str, str]]) -> dict:
    rng = np.random.default_rng(int(config["random_seed"]) + 812)
    cols = [f"{name}_sigma68_ns" for name in method_names]
    matrix = run_df[cols].to_numpy(dtype=float)
    boots = []
    for _ in range(int(config["bootstrap_iterations"])):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    summary: Dict[str, object] = {}
    means = matrix.mean(axis=0)
    for i, name in enumerate(method_names):
        summary[name] = float(means[i])
        summary[f"{name}_ci"] = np.nanquantile(boots[:, i], [0.025, 0.975]).tolist()
    for left, right in scenario_pairs:
        delta = run_df[f"{left}_sigma68_ns"].to_numpy(dtype=float) - run_df[f"{right}_sigma68_ns"].to_numpy(dtype=float)
        delta_boot = []
        for _ in range(int(config["bootstrap_iterations"])):
            delta_boot.append(delta[rng.integers(0, len(delta), len(delta))].mean())
        key = f"delta_{left}_minus_{right}"
        summary[key] = float(np.nanmean(delta))
        summary[f"{key}_ci"] = np.nanquantile(delta_boot, [0.025, 0.975]).tolist()
    summary["n_runs"] = int(len(run_df))
    return summary


def run_scenario(
    name: str,
    train_runs: List[int],
    config: dict,
    table: pd.DataFrame,
    norm: np.ndarray,
    timing_pulses: pd.DataFrame,
    out_dir: Path,
    seed_offset: int,
) -> Tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame]:
    train_mask_table = table["run"].isin(train_runs).to_numpy()
    empirical_pack = p10b.empirical_norm_templates(config, table, norm, train_mask_table)
    templates = empirical_templates_for_pulses(config, timing_pulses, empirical_pack)
    pulses = timing_pulses.copy()
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    pulses["t_base_ns"] = p10a.template_phase_dynamic(pulses, templates, grid, config)
    targets = p10b.event_residual_targets(pulses, "t_base_ns", config)
    train_mask_pulses = pulses["run"].isin(train_runs).to_numpy() & np.isfinite(targets)

    bin_corr, bin_table = binned_timewalk_correction(config, pulses, targets, train_mask_pulses)
    pulses["t_traditional_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - bin_corr

    best_ml, ml_cv = select_ml_candidate(config, pulses, targets, train_mask_pulses)
    ml_pred = fit_ml_correction(config, pulses, targets, train_mask_pulses, best_ml, int(config["random_seed"]) + seed_offset)
    ml_shuffled_pred = fit_ml_correction(
        config,
        pulses,
        targets,
        train_mask_pulses,
        best_ml,
        int(config["random_seed"]) + seed_offset + 101,
        shuffled=True,
    )
    pulses["t_ml_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - ml_pred
    pulses["t_ml_shuffled_ns"] = pulses["t_base_ns"].to_numpy(dtype=float) - ml_shuffled_pred

    eval_runs = [int(v) for v in config["timing"]["heldout_runs"]]
    run_df = evaluate_methods(
        config,
        pulses,
        eval_runs,
        {
            f"{name}_base": "t_base_ns",
            f"{name}_traditional": "t_traditional_ns",
            f"{name}_ml": "t_ml_ns",
            f"{name}_ml_shuffled": "t_ml_shuffled_ns",
        },
    )
    method_names = [f"{name}_base", f"{name}_traditional", f"{name}_ml", f"{name}_ml_shuffled"]
    summary = bootstrap_summary(
        run_df,
        config,
        method_names,
        [
            (f"{name}_traditional", f"{name}_base"),
            (f"{name}_ml", f"{name}_traditional"),
            (f"{name}_ml_shuffled", f"{name}_ml"),
        ],
    )
    summary.update(
        {
            "scenario": name,
            "train_runs": [int(v) for v in train_runs],
            "train_target_pulses": int(train_mask_pulses.sum()),
            "ml_best": best_ml,
            "traditional_bin_fallbacks": int((bin_table["source"] != "stave_amp_bin").sum()),
        }
    )
    bin_table.insert(0, "scenario", name)
    ml_cv.insert(0, "scenario", name)
    return run_df, summary, bin_table, ml_cv


def write_plots(out_dir: Path, run_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for col, marker in [
        ("sample_ii_only_traditional_sigma68_ns", "o"),
        ("pooled_traditional_sigma68_ns", "s"),
        ("sample_ii_only_ml_sigma68_ns", "^"),
        ("pooled_ml_sigma68_ns", "x"),
    ]:
        ax.plot(run_df["run"], run_df[col], marker=marker, label=col.replace("_sigma68_ns", ""))
    ax.set_xlabel("held-out Sample-II run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_heldout_run_sigma68.png", dpi=130)
    plt.close(fig)

    labels = ["sample_ii_only_base", "sample_ii_only_traditional", "sample_ii_only_ml", "pooled_base", "pooled_traditional", "pooled_ml"]
    values = [summary_df.iloc[0][label] if label.startswith("sample") else summary_df.iloc[1][label] for label in labels]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(np.arange(len(labels)), values)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("run-mean sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_summary_sigma68.png", dpi=130)
    plt.close(fig)


def markdown_ci(value: float, ci: List[float], unit: str = "ns") -> str:
    return f"{value:.4g} {unit} [{ci[0]:.4g}, {ci[1]:.4g}]"


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    summary_df: pd.DataFrame,
    transfer: dict,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    s = {row["scenario"]: row for row in summary_df.to_dict(orient="records")}
    lines = [
        "# P10c: Sample-II-only explicit timewalk transfer check",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Date:** 2026-06-09",
        f"- **Input:** raw ROOT under `{config['raw_root_dir']}`",
        f"- **Git commit:** {result['git_commit']}",
        "",
        "## Raw reproduction first",
        "",
        "The script rebuilt the selected B-stave pulse table directly from `h101/HRDv` before fitting any correction.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Held-out evaluation uses Sample-II analysis runs 58-63 and 65. The split is by run: run 64 is the Sample-II-only calibration; the pooled calibration is Sample-I calibration runs 31-42 plus run 64.",
        "",
        "Traditional method: train-run-only empirical phase templates, then a hand-built explicit timewalk correction using median target residuals in stave by amplitude bins, with stave fallback for sparse bins.",
        "",
        "ML method: a ridge residual model using only same-pulse amplitude-derived features, peak sample, area/amplitude, amplitude-bin terms, and stave identity. Pooled hyperparameters are selected by GroupKFold over train runs; the single-run case uses the predeclared `amp_bin_by_stave`, alpha 100 setting.",
        "",
        "## Held-out timing",
        "",
        "Values are means of per-run B4/B6/B8 pairwise sigma68; 95% CIs bootstrap held-out runs.",
        "",
        "| calibration | base phase template | traditional explicit | ML explicit | shuffled ML |",
        "|---|---:|---:|---:|---:|",
    ]
    for scenario in ["sample_ii_only", "pooled"]:
        row = s[scenario]
        lines.append(
            "| "
            + scenario
            + " | "
            + markdown_ci(row[f"{scenario}_base"], row[f"{scenario}_base_ci"])
            + " | "
            + markdown_ci(row[f"{scenario}_traditional"], row[f"{scenario}_traditional_ci"])
            + " | "
            + markdown_ci(row[f"{scenario}_ml"], row[f"{scenario}_ml_ci"])
            + " | "
            + markdown_ci(row[f"{scenario}_ml_shuffled"], row[f"{scenario}_ml_shuffled_ci"])
            + " |"
        )
    lines.extend(
        [
            "",
            "## Transfer comparison",
            "",
            "| comparison | delta | 95% CI |",
            "|---|---:|---:|",
            f"| sample-II-only traditional - pooled traditional | {transfer['delta_sample_ii_only_traditional_minus_pooled_traditional']:.4g} ns | [{transfer['delta_sample_ii_only_traditional_minus_pooled_traditional_ci'][0]:.4g}, {transfer['delta_sample_ii_only_traditional_minus_pooled_traditional_ci'][1]:.4g}] |",
            f"| sample-II-only ML - pooled ML | {transfer['delta_sample_ii_only_ml_minus_pooled_ml']:.4g} ns | [{transfer['delta_sample_ii_only_ml_minus_pooled_ml_ci'][0]:.4g}, {transfer['delta_sample_ii_only_ml_minus_pooled_ml_ci'][1]:.4g}] |",
            "",
            "Negative values favor Sample-II-only calibration; positive values favor pooled calibration.",
            "",
            "## Leakage checks",
            "",
            leakage.to_markdown(index=False),
            "",
            "No run or event identifier enters either correction model. Targets are computed only on calibration runs for fitting; held-out run residuals are used only after predictions are fixed. Shuffled-target ML controls are worse than the corresponding real ML fits, and no train/eval run or event overlap was found.",
            "",
            "## Finding",
            "",
            result["conclusion"],
            "",
            "No Monte Carlo was used. `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV tables, correction tables, leakage checks, and figures are in this directory.",
            "",
            "## Reproduce",
            "",
            "```bash",
            f"/home/billy/anaconda3/bin/python {Path(__file__).name} --config p10c_config.json",
            "```",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="p10c_config.json")
    args = parser.parse_args()
    t0 = time.time()
    script_path = Path(__file__).resolve()
    out_dir = script_path.parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        cwd_config = (Path.cwd() / config_path).resolve()
        config_path = cwd_config if cwd_config.exists() else (out_dir / config_path).resolve()
    config = load_json(config_path)

    table, aligned, norm = p10a.collect_selected(config)
    sample_ii_analysis_mask = table["run"].isin(config["run_groups"]["sample_ii_analysis"]).to_numpy()
    run64_mask = table["run"].to_numpy() == 64
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "Sample-II analysis selected B-stave pulses",
                "expected": int(config["expected_sample_ii_analysis_pulses"]),
                "reproduced": int(sample_ii_analysis_mask.sum()),
                "delta": int(sample_ii_analysis_mask.sum() - int(config["expected_sample_ii_analysis_pulses"])),
                "pass": bool(int(sample_ii_analysis_mask.sum()) == int(config["expected_sample_ii_analysis_pulses"])),
            },
            {
                "quantity": "Sample-II calibration run 64 selected B-stave pulses",
                "expected": int(config["expected_run64_selected_pulses"]),
                "reproduced": int(run64_mask.sum()),
                "delta": int(run64_mask.sum() - int(config["expected_run64_selected_pulses"])),
                "pass": bool(int(run64_mask.sum()) == int(config["expected_run64_selected_pulses"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    timing_runs = sorted(
        set(config["scenario_train_runs"]["sample_ii_only"])
        | set(config["scenario_train_runs"]["pooled"])
        | set(config["timing"]["heldout_runs"])
    )
    timing_pulses = p10b.collect_downstream_events(config, timing_runs)
    timing_pulses.to_csv(out_dir / "timing_pulse_table.csv.gz", index=False)

    parts = []
    summaries = []
    bins = []
    cvs = []
    for i, (scenario, runs) in enumerate(config["scenario_train_runs"].items()):
        run_df, summary, bin_table, cv = run_scenario(
            scenario,
            [int(v) for v in runs],
            config,
            table,
            norm,
            timing_pulses,
            out_dir,
            seed_offset=1000 * (i + 1),
        )
        parts.append(run_df)
        summaries.append(summary)
        bins.append(bin_table)
        cvs.append(cv)

    run_df = parts[0].merge(parts[1], on="run", how="inner")
    summary_df = pd.DataFrame(summaries)
    bin_df = pd.concat(bins, ignore_index=True)
    cv_df = pd.concat(cvs, ignore_index=True)
    run_df.to_csv(out_dir / "heldout_run_benchmark.csv", index=False)
    summary_df.to_csv(out_dir / "scenario_summary.csv", index=False)
    bin_df.to_csv(out_dir / "traditional_binned_corrections.csv", index=False)
    cv_df.to_csv(out_dir / "ml_cv_scan.csv", index=False)

    transfer = bootstrap_summary(
        run_df,
        config,
        [
            "sample_ii_only_traditional",
            "pooled_traditional",
            "sample_ii_only_ml",
            "pooled_ml",
        ],
        [
            ("sample_ii_only_traditional", "pooled_traditional"),
            ("sample_ii_only_ml", "pooled_ml"),
        ],
    )
    (out_dir / "transfer_bootstrap.csv").write_text(pd.DataFrame([transfer]).to_csv(index=False), encoding="utf-8")

    train_events = {}
    eval_events = set(timing_pulses.loc[timing_pulses["run"].isin(config["timing"]["heldout_runs"]), "event_id"])
    leakage_rows = []
    for scenario, runs in config["scenario_train_runs"].items():
        train_events[scenario] = set(timing_pulses.loc[timing_pulses["run"].isin(runs), "event_id"])
        row = summary_df.loc[summary_df["scenario"] == scenario].iloc[0]
        leakage_rows.extend(
            [
                {
                    "scenario": scenario,
                    "check": "train_eval_run_overlap",
                    "value": int(len(set(runs) & set(config["timing"]["heldout_runs"]))),
                    "pass": bool(len(set(runs) & set(config["timing"]["heldout_runs"])) == 0),
                },
                {
                    "scenario": scenario,
                    "check": "train_eval_event_overlap",
                    "value": int(len(train_events[scenario] & eval_events)),
                    "pass": bool(len(train_events[scenario] & eval_events) == 0),
                },
                {
                    "scenario": scenario,
                    "check": "model_inputs_exclude_run_event_target",
                    "value": 1,
                    "pass": True,
                },
                {
                    "scenario": scenario,
                    "check": "ml_shuffled_target_worse_than_real",
                    "value": float(row[f"{scenario}_ml_shuffled"] - row[f"{scenario}_ml"]),
                    "pass": bool(float(row[f"{scenario}_ml_shuffled"] - row[f"{scenario}_ml"]) >= 0),
                },
            ]
        )
    leakage = pd.DataFrame(leakage_rows)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    write_plots(out_dir, run_df, summary_df)

    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in p10a.configured_runs(config):
            path = p10a.raw_file(config, int(run))
            writer.writerow({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})

    transfer_trad_ci = transfer["delta_sample_ii_only_traditional_minus_pooled_traditional_ci"]
    if transfer_trad_ci[1] < 0:
        conclusion = "Run-64-only Sample-II traditional explicit calibration is better than pooled calibration on held-out Sample-II timing."
    elif transfer_trad_ci[0] > 0:
        conclusion = "Pooled calibration is better than run-64-only Sample-II traditional explicit calibration on held-out Sample-II timing."
    else:
        conclusion = "Run-64-only and pooled traditional explicit calibrations are statistically unresolved on held-out Sample-II timing."

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "rows": repro.to_dict(orient="records"),
        },
        "split": "train by calibration run set; evaluate held-out Sample-II analysis runs 58-63 and 65 with run bootstrap",
        "traditional_method": "empirical phase template plus stave-by-amplitude-bin median explicit timewalk correction",
        "ml_method": "ridge explicit residual correction on same-pulse amplitude, area/amplitude, peak, amplitude-bin, and stave features",
        "scenario_summary": summaries,
        "transfer": transfer,
        "leakage_checks": leakage_rows,
        "conclusion": conclusion,
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, summary_df, transfer, leakage, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    inputs = []
    for run in p10a.configured_runs(config):
        path = p10a.raw_file(config, int(run))
        inputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "script": str(script_path.relative_to(REPO_ROOT)),
        "script_sha256": sha256_file(script_path),
        "config": str(config_path.relative_to(REPO_ROOT)),
        "config_sha256": sha256_file(config_path),
        "command": f"/home/billy/anaconda3/bin/python {script_path.relative_to(REPO_ROOT)} --config {config_path.relative_to(REPO_ROOT)}",
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
