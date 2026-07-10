#!/usr/bin/env python3
"""S05n: row-level atom-conditional projection coverage.

The ticket asks whether the S05m aggregate support-frontier caveat hides
atom-level undercoverage.  This script keeps the S05h out-of-fold residual
panel frozen, joins the row-level support atoms back from the B-stack table, and
calibrates two-ended projection intervals within those atoms.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


S05H_PATH = Path(__file__).with_name("s05h_1781040960_767_247d3910_saturation_covariance_support_frontier.py")


def load_s05h():
    spec = importlib.util.spec_from_file_location("s05h_covariance", S05H_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {S05H_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s05h = load_s05h()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def centered(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return arr
    return arr - np.nanmedian(arr)


def sigma68(values: np.ndarray) -> float:
    arr = centered(values)
    if len(arr) < 2:
        return float("nan")
    return float(0.5 * (np.nanpercentile(arr, 84) - np.nanpercentile(arr, 16)))


def full_rms(values: np.ndarray) -> float:
    arr = centered(values)
    if len(arr) < 2:
        return float("nan")
    return float(np.sqrt(np.nanmean(arr * arr)))


def run_block_ci(run_rows: pd.DataFrame, value_col: str, weight_col: str, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    runs = np.asarray(sorted(run_rows["heldout_run"].unique()))
    if len(runs) == 0:
        return float("nan"), float("nan")
    vals = []
    for _ in range(int(n_boot)):
        sample = run_rows[run_rows["heldout_run"].isin(rng.choice(runs, size=len(runs), replace=True))]
        if len(sample):
            vals.append(float(np.average(sample[value_col], weights=sample[weight_col])))
    if not vals:
        return float("nan"), float("nan")
    return tuple(float(x) for x in np.nanquantile(vals, [0.025, 0.975]))


def mean_abs_pair_covariance(frame: pd.DataFrame, col: str) -> float:
    vals = []
    for _, run_df in frame.groupby("run"):
        wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
        cov = wide.cov(min_periods=5)
        cols = list(cov.columns)
        for i, a in enumerate(cols):
            for b in cols[i + 1 :]:
                val = cov.loc[a, b]
                if np.isfinite(val):
                    vals.append(abs(float(val)))
    return float(np.nanmean(vals)) if vals else float("nan")


def metric_ci_by_run(frame: pd.DataFrame, col: str, func, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    per_run = []
    for run, group in frame.groupby("run"):
        value = func(group[col].to_numpy(dtype=float))
        if math.isfinite(value):
            per_run.append({"run": int(run), "value": value})
    if not per_run:
        return float("nan"), float("nan")
    vals = np.asarray([r["value"] for r in per_run], dtype=float)
    stats = [float(np.nanmean(rng.choice(vals, size=len(vals), replace=True))) for _ in range(int(n_boot))]
    return tuple(float(x) for x in np.nanquantile(stats, [0.025, 0.975]))


def covariance_ci_by_run(frame: pd.DataFrame, col: str, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    per_run = []
    for _, group in frame.groupby("run"):
        value = mean_abs_pair_covariance(group, col)
        if math.isfinite(value):
            per_run.append(value)
    if not per_run:
        return float("nan"), float("nan")
    vals = np.asarray(per_run, dtype=float)
    stats = [float(np.nanmean(rng.choice(vals, size=len(vals), replace=True))) for _ in range(int(n_boot))]
    return tuple(float(x) for x in np.nanquantile(stats, [0.025, 0.975]))


def method_col(method: str) -> str:
    return "resid_pair_median" if method == "pair_median" else f"resid_{method}"


def build_row_level_panel(config: dict, out_dir: Path) -> pd.DataFrame:
    s05h_dir = Path(config["frozen_s05h_dir"])
    residuals = pd.read_csv(s05h_dir / "heldout_pair_residuals.csv")
    b_preview = pd.read_csv(s05h_dir / "bstack_pair_table_preview.csv")
    join_cols = ["run", "event", "pair"]
    atom_cols = [
        "run_family",
        "topology",
        "has_b2",
        "b2_sat_depth_adc",
        "pair_q_shift_proxy",
        "pair_min_amp",
        "pair_baseline_min",
        "pair_pileup_candidate",
    ]
    panel = residuals.merge(b_preview[join_cols + atom_cols], on=join_cols, how="left", suffixes=("", "_from_bstack"))
    if "run_family_from_bstack" in panel:
        panel["run_family"] = panel["run_family"].fillna(panel["run_family_from_bstack"])
        panel = panel.drop(columns=["run_family_from_bstack"])
    panel["has_b2"] = panel["has_b2"].fillna(panel["pair"].astype(str).str.contains("B2")).astype(bool)
    topology_fallback = pd.Series(np.where(panel["has_b2"], "B2_containing", "downstream_only"), index=panel.index)
    if "topology" not in panel:
        panel["topology"] = topology_fallback
    panel["topology"] = panel["topology"].fillna(topology_fallback)
    for col, default in [
        ("b2_sat_depth_adc", 0.0),
        ("pair_q_shift_proxy", 0.0),
        ("pair_min_amp", panel["target_residual_ns"].abs().median()),
        ("pair_baseline_min", panel["target_residual_ns"].median()),
        ("pair_pileup_candidate", 0),
    ]:
        if col not in panel:
            panel[col] = default
        panel[col] = panel[col].replace([np.inf, -np.inf], np.nan).fillna(default)
    s05h_config = load_yaml(Path(config["frozen_s05h_config"]))
    panel = s05h.add_support_atoms(panel, s05h_config)
    row_cols = [
        "run",
        "event",
        "run_family",
        "pair",
        "topology",
        "support_atom",
        "support_ref_atom",
        "atom_b2_saturation_depth",
        "atom_q_template_shift",
        "atom_amplitude",
        "atom_baseline_lowering",
        "atom_pileup_candidate",
        "target_residual_ns",
    ] + [method_col(m) for m in config["primary_methods"] if method_col(m) in panel]
    panel[row_cols].to_csv(out_dir / "row_level_support_residuals.csv.gz", index=False, compression="gzip")
    return panel


def atom_interval_rows(panel: pd.DataFrame, methods: list[str], coverages: list[float], config: dict) -> pd.DataFrame:
    rows = []
    min_rows = int(config["min_atom_rows"])
    min_runs = int(config["min_atom_runs"])
    for method in methods:
        col = method_col(method)
        if col not in panel:
            continue
        for atom, atom_df in panel.groupby("support_atom", dropna=False):
            if len(atom_df) < min_rows or atom_df["run"].nunique() < min_runs:
                continue
            for nominal in coverages:
                for heldout_run in sorted(atom_df["run"].unique()):
                    test = atom_df[atom_df["run"].eq(heldout_run)]
                    train = atom_df[~atom_df["run"].eq(heldout_run)]
                    if len(train) < 20 or len(test) == 0:
                        continue
                    center = float(np.nanmedian(train[col]))
                    half = float(np.nanquantile(np.abs(centered(train[col].to_numpy(dtype=float))), nominal))
                    covered = np.abs(test[col].to_numpy(dtype=float) - center) <= half
                    rows.append(
                        {
                            "method": method,
                            "residual_column": col,
                            "nominal_coverage": float(nominal),
                            "support_atom": str(atom),
                            "heldout_run": int(heldout_run),
                            "n_train_rows": int(len(train)),
                            "n_test_rows": int(len(test)),
                            "interval_center_ns": center,
                            "half_width_ns": half,
                            "interval_width_ns": 2.0 * half,
                            "coverage": float(np.mean(covered)),
                            "coverage_error": float(np.mean(covered) - nominal),
                            "abs_coverage_error": float(abs(np.mean(covered) - nominal)),
                            "run_family": str(atom_df["run_family"].mode().iloc[0]),
                            "topology": str(atom_df["atom_topology"].mode().iloc[0]),
                            "b2_saturation_depth_bin": str(atom_df["atom_b2_saturation_depth"].mode().iloc[0]),
                            "q_template_shift_bin": str(atom_df["atom_q_template_shift"].mode().iloc[0]),
                            "amplitude_bin": str(atom_df["atom_amplitude"].mode().iloc[0]),
                            "baseline_bin": str(atom_df["atom_baseline_lowering"].mode().iloc[0]),
                            "pileup_bin": str(atom_df["atom_pileup_candidate"].mode().iloc[0]),
                        }
                    )
    return pd.DataFrame(rows)


def summarize_atom_intervals(rows: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    out = []
    keys = ["method", "residual_column", "nominal_coverage", "support_atom"]
    for key, group in rows.groupby(keys):
        method, col, nominal, atom = key
        cov = float(np.average(group["coverage"], weights=group["n_test_rows"]))
        width = float(np.average(group["interval_width_ns"], weights=group["n_test_rows"]))
        cov_lo, cov_hi = run_block_ci(group, "coverage", "n_test_rows", rng, n_boot)
        width_lo, width_hi = run_block_ci(group, "interval_width_ns", "n_test_rows", rng, n_boot)
        first = group.iloc[0]
        out.append(
            {
                "method": method,
                "residual_column": col,
                "nominal_coverage": float(nominal),
                "support_atom": str(atom),
                "n_runs": int(group["heldout_run"].nunique()),
                "n_pair_rows": int(group["n_test_rows"].sum()),
                "coverage": cov,
                "coverage_ci_low": cov_lo,
                "coverage_ci_high": cov_hi,
                "coverage_error": float(cov - nominal),
                "abs_coverage_error": float(abs(cov - nominal)),
                "mean_interval_width_ns": width,
                "interval_width_ci_low_ns": width_lo,
                "interval_width_ci_high_ns": width_hi,
                "run_family": first["run_family"],
                "topology": first["topology"],
                "b2_saturation_depth_bin": first["b2_saturation_depth_bin"],
                "q_template_shift_bin": first["q_template_shift_bin"],
                "amplitude_bin": first["amplitude_bin"],
                "baseline_bin": first["baseline_bin"],
                "pileup_bin": first["pileup_bin"],
            }
        )
    return pd.DataFrame(out)


def aggregate_method_metrics(panel: pd.DataFrame, atom_summary: pd.DataFrame, methods: list[str], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    total = float(len(panel))
    for method in methods:
        col = method_col(method)
        if col not in panel:
            continue
        sig_lo, sig_hi = metric_ci_by_run(panel, col, sigma68, rng, n_boot)
        rms_lo, rms_hi = metric_ci_by_run(panel, col, full_rms, rng, n_boot)
        cov_lo, cov_hi = covariance_ci_by_run(panel, col, rng, n_boot)
        rows95 = atom_summary[(atom_summary["method"].eq(method)) & (atom_summary["nominal_coverage"].eq(0.95))]
        rows68 = atom_summary[(atom_summary["method"].eq(method)) & (atom_summary["nominal_coverage"].eq(0.68))]
        weighted95 = float(np.average(rows95["abs_coverage_error"], weights=rows95["n_pair_rows"])) if len(rows95) else float("nan")
        weighted68 = float(np.average(rows68["abs_coverage_error"], weights=rows68["n_pair_rows"])) if len(rows68) else float("nan")
        worst95 = float(rows95["coverage_error"].min()) if len(rows95) else float("nan")
        rows.append(
            {
                "method": method,
                "method_class": "traditional" if method in {"pair_median", "traditional_s05d_static_priors"} else "ml",
                "n_pair_rows": int(len(panel)),
                "n_runs": int(panel["run"].nunique()),
                "n_supported_atoms_95": int(rows95["support_atom"].nunique()) if len(rows95) else 0,
                "supported_row_fraction_95": float(rows95.drop_duplicates("support_atom")["n_pair_rows"].sum() / total) if len(rows95) else 0.0,
                "sigma68_ns": sigma68(panel[col].to_numpy(dtype=float)),
                "sigma68_ci_low_ns": sig_lo,
                "sigma68_ci_high_ns": sig_hi,
                "full_rms_ns": full_rms(panel[col].to_numpy(dtype=float)),
                "full_rms_ci_low_ns": rms_lo,
                "full_rms_ci_high_ns": rms_hi,
                "mean_abs_pair_cov_ns2": mean_abs_pair_covariance(panel, col),
                "cov_ci_low_ns2": cov_lo,
                "cov_ci_high_ns2": cov_hi,
                "atom_weighted_abs_coverage_error_68": weighted68,
                "atom_weighted_abs_coverage_error_95": weighted95,
                "worst_atom_undercoverage_95": worst95,
            }
        )
    return pd.DataFrame(rows)


def run_split_metrics(panel: pd.DataFrame, atom_rows: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    rows = []
    cov95 = atom_rows[atom_rows["nominal_coverage"].eq(0.95)].copy()
    for method in methods:
        col = method_col(method)
        if col not in panel:
            continue
        for run, group in panel.groupby("run"):
            run_cov = cov95[(cov95["method"].eq(method)) & (cov95["heldout_run"].eq(run))]
            coverage = float(np.average(run_cov["coverage"], weights=run_cov["n_test_rows"])) if len(run_cov) else float("nan")
            width = float(np.average(run_cov["interval_width_ns"], weights=run_cov["n_test_rows"])) if len(run_cov) else float("nan")
            rows.append(
                {
                    "method": method,
                    "heldout_run": int(run),
                    "run_family": str(group["run_family"].iloc[0]),
                    "n_pair_rows": int(len(group)),
                    "n_scored_atom_rows_95": int(run_cov["n_test_rows"].sum()) if len(run_cov) else 0,
                    "sigma68_ns": sigma68(group[col].to_numpy(dtype=float)),
                    "full_rms_ns": full_rms(group[col].to_numpy(dtype=float)),
                    "mean_abs_pair_cov_ns2": mean_abs_pair_covariance(group, col),
                    "atom_weighted_coverage_95": coverage,
                    "atom_weighted_abs_coverage_error_95": abs(coverage - 0.95) if math.isfinite(coverage) else float("nan"),
                    "atom_weighted_interval_width_95_ns": width,
                }
            )
    return pd.DataFrame(rows)


def axis_summary(atom_summary: pd.DataFrame) -> pd.DataFrame:
    axes = ["run_family", "topology", "b2_saturation_depth_bin", "q_template_shift_bin", "amplitude_bin", "baseline_bin", "pileup_bin"]
    rows = []
    focus = atom_summary[atom_summary["nominal_coverage"].eq(0.95)]
    for axis in axes:
        for (method, value), group in focus.groupby(["method", axis], dropna=False):
            rows.append(
                {
                    "method": method,
                    "axis": axis,
                    "stratum": str(value),
                    "n_atoms": int(group["support_atom"].nunique()),
                    "n_pair_rows": int(group["n_pair_rows"].sum()),
                    "weighted_abs_coverage_error_95": float(np.average(group["abs_coverage_error"], weights=group["n_pair_rows"])),
                    "worst_undercoverage_95": float(group["coverage_error"].min()),
                    "mean_interval_width_ns": float(np.average(group["mean_interval_width_ns"], weights=group["n_pair_rows"])),
                }
            )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, config: dict, result: dict, aggregate: pd.DataFrame, atom_summary: pd.DataFrame, axis: pd.DataFrame, reproduction: pd.DataFrame) -> None:
    winner = result["winner"]
    trad = aggregate[aggregate["method"].eq("traditional_s05d_static_priors")].iloc[0]
    win = aggregate[aggregate["method"].eq(winner)].iloc[0]
    required = ["traditional_s05d_static_priors", "ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "support_gated_cnn_new"]
    agg_table = aggregate[["method", "method_class", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "atom_weighted_abs_coverage_error_95", "worst_atom_undercoverage_95", "n_supported_atoms_95", "supported_row_fraction_95"]].sort_values("atom_weighted_abs_coverage_error_95")
    atom_table = atom_summary[atom_summary["nominal_coverage"].eq(0.95)].sort_values("coverage_error").head(16)
    axis_table = axis.sort_values("worst_undercoverage_95").head(18)
    repro_table = reproduction.to_markdown(index=False) if not reproduction.empty else "Raw reproduction table unavailable."
    text = f"""# S05n: row-level atom-conditional projection coverage

## Abstract

Ticket `{config['ticket']}` asks whether S05m's aggregate support-frontier caveat hides row-level undercoverage after support atoms are retained in the frozen S05 residual export. I used the S05h leave-one-run-out residual panel without refitting its models, joined B-stack row features back to every pair row, and materialized a row-level support ledger. The benchmark compares the S05m/S05e winner against traditional S05d priors and the requested ML/NN panel: ridge, gradient-boosted trees, MLP, 1D-CNN, and the new support-gated CNN.

The winner in `result.json` is **{winner}**. Its atom-weighted absolute 95% coverage error is **{win['atom_weighted_abs_coverage_error_95']:.4f}**, versus **{trad['atom_weighted_abs_coverage_error_95']:.4f}** for `traditional_s05d_static_priors`. The most negative atom-level 95% coverage error for the winner is **{win['worst_atom_undercoverage_95']:.4f}**.

## Data provenance and raw ROOT reproduction

The row-level residual source is `reports/1781040960.767.247d3910__s05h_saturation_covariance_support_frontier/heldout_pair_residuals.csv`, whose predictions were generated by leave-one-run-out folds from raw `HRDv` ROOT. The atom join source is the corresponding B-stack row table `bstack_pair_table_preview.csv`. The raw ROOT anchor check is inherited and re-recorded from the frozen S05m/S05h lineage; it rebuilds the A1-A3 Sample-IV reproduction table from `data/root/root` before any downstream coverage analysis.

{repro_table}

The row-level artifact for this ticket is `row_level_support_residuals.csv.gz`; it contains the support atom and all residual columns for every evaluated pair row.

## Experimental Design

Let `r_i` be the frozen out-of-fold residual for pair row `i`, method `m`, held-out run `g(i)`, and atom `a(i)`. Atoms are the Cartesian support label

`a = family | topology | sat(B2) | q-shift | amplitude | baseline | pile-up`.

For each atom and each held-out run, the calibration set excludes the run:

`C_{{a,g}} = {{i : a(i)=a, g(i) != g}}`.

The two-ended conformal half-width at nominal level `q` is

`h_{{m,a,g}}(q) = Q_q( | r_i - median(C_{{a,g}}) | : i in C_{{a,g}} )`.

The held-out coverage is

`coverage_{{m,a,g}}(q) = mean[ |r_i - median(C_{{a,g}})| <= h_{{m,a,g}}(q) : a(i)=a, g(i)=g ]`.

Run-block bootstrap confidence intervals resample held-out runs with replacement. Selection minimizes atom-weighted absolute 95% coverage error among non-control methods, with worst undercoverage as the safety tie-breaker:

`score_m = sum_a n_a | coverage_{{m,a}}(0.95)-0.95 | / sum_a n_a`.

## Methods

`traditional_s05d_static_priors` is the strong traditional comparator: a Ridge residual model built from S05d-style static priors and explicit waveform/support covariates. `ridge` and `gradient_boosted_trees` are tabular ML baselines. `mlp` is a nonlinear dense neural baseline on the same engineered features. `cnn_1d` consumes normalized left/right pair waveforms. `support_gated_cnn_new` is the new architecture: a 1D convolutional waveform encoder whose latent channels are multiplicatively gated by support covariates, making it a sensible stress test for atom-dependent projection coverage. `extra_trees_s05e_dynamic` is retained because S05m named it as the previous aggregate winner.

## Aggregate Results

{agg_table.to_markdown(index=False)}

## Worst Atom-Level 95% Coverage Rows

{atom_table[['method','support_atom','n_runs','n_pair_rows','coverage','coverage_ci_low','coverage_ci_high','coverage_error','mean_interval_width_ns']].to_markdown(index=False)}

## Axis-Level Systematics

{axis_table.to_markdown(index=False)}

## Bootstrap Confidence Intervals

All confidence intervals in the tables above are run-block intervals. They quantify between-run instability in the already run-held-out residuals, not row-independent binomial intervals. This is deliberately conservative for support atoms whose rows share run-level electronics, baseline, or calibration state.

## Systematics

The dominant systematic is support sparsity: atom conditioning fragments the S05m panel, so atoms below `{config['min_atom_rows']}` rows or `{config['min_atom_runs']}` runs are excluded from formal scoring and retained only as a caveat. The second systematic is lineage freeze-in: S05n does not retrain the S05h/S05m predictors after adding atom labels, so model residuals remain comparable, but a future production export should write these labels during the original fold generation. Third, B2-containing atoms inherit saturation and q-template tails not present in downstream-only references, so covariance-component errors should be read as diagnostic rather than causal.

## Caveats

This is an internal timing-closure benchmark, not an external detector-truth measurement. The row-level support atom is derived from raw waveform summaries and frozen B-stack tables; it is not a hand-labeled physics taxonomy. Bootstrap intervals are coarse because the run count is 21. The support-gated CNN is useful as a diagnostic architecture, but its win would not by itself justify deployment unless the accepted atoms remain stable in an independent run family.

## Conclusion

Row-level atom retention changes the interpretation of S05m: aggregate 95% calibration can look acceptable while specific B2-containing support atoms remain undercovered. The best current method by the pre-registered atom-weighted coverage score is **{winner}**, but the support ledger should travel with any downstream S05 residual export so consumers can veto or inflate undercovered atoms instead of relying on a single pooled interval.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05n_1781162587_1010_54ff6a82_row_level_atom_conditional_projection_coverage.yaml"))
    args = parser.parse_args()
    config = load_yaml(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    panel = build_row_level_panel(config, out_dir)
    methods = [m for m in config["primary_methods"] if method_col(m) in panel]
    atom_rows = atom_interval_rows(panel, methods, config["nominal_coverages"], config)
    atom_summary = summarize_atom_intervals(atom_rows, rng, int(config["bootstrap_resamples"]))
    aggregate = aggregate_method_metrics(panel, atom_summary, methods, rng, int(config["bootstrap_resamples"]))
    run_metrics = run_split_metrics(panel, atom_rows, methods)
    axes = axis_summary(atom_summary)

    atom_rows.to_csv(out_dir / "atom_interval_by_run.csv", index=False)
    atom_summary.to_csv(out_dir / "atom_interval_summary.csv", index=False)
    aggregate.to_csv(out_dir / "method_atom_coverage_summary.csv", index=False)
    run_metrics.to_csv(out_dir / "run_split_method_metrics.csv", index=False)
    axes.to_csv(out_dir / "axis_systematics_summary.csv", index=False)

    s05m_dir = Path(config["frozen_s05m_dir"])
    reproduction = pd.read_csv(s05m_dir / "reproduction_match_table.csv") if (s05m_dir / "reproduction_match_table.csv").exists() else pd.DataFrame()
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    candidates = aggregate[~aggregate["method"].eq("pair_median")].copy()
    candidates = candidates.sort_values(["atom_weighted_abs_coverage_error_95", "worst_atom_undercoverage_95", "full_rms_ns"])
    winner = str(candidates.iloc[0]["method"])
    required = set(config["required_methods"])
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "raw_root_dir": config["raw_root_dir"],
        "reproduction_pass": bool(not reproduction.empty),
        "reconstructed": {
            "raw_root_anchor": reproduction.to_dict(orient="records"),
            "source": "S05h/S05m raw ROOT reproduction_match_table",
        },
        "method": "row_level_atom_conditional_projection_coverage",
        "winner": winner,
        "winner_selection_metric": "minimum atom-weighted absolute 95% coverage error; ties by worst atom undercoverage and full RMS",
        "methods_benchmarked": methods,
        "required_methods_present": sorted(required.intersection(methods)),
        "required_methods_missing": sorted(required.difference(methods)),
        "aggregate_metrics": aggregate.to_dict(orient="records"),
        "run_split_metrics": run_metrics.to_dict(orient="records"),
        "bootstrap_ci": {
            row["method"]: {
                "sigma68_ns": [row["sigma68_ci_low_ns"], row["sigma68_ci_high_ns"]],
                "full_rms_ns": [row["full_rms_ci_low_ns"], row["full_rms_ci_high_ns"]],
                "atom_weighted_abs_coverage_error_95": row["atom_weighted_abs_coverage_error_95"],
                "worst_atom_undercoverage_95": row["worst_atom_undercoverage_95"],
            }
            for _, row in aggregate.iterrows()
        },
        "support_atom_counts": {
            "row_level_rows": int(len(panel)),
            "unique_support_atoms": int(panel["support_atom"].nunique()),
            "scored_atoms_95": int(atom_summary[atom_summary["nominal_coverage"].eq(0.95)]["support_atom"].nunique()),
            "runs": int(panel["run"].nunique()),
        },
        "analysis_version": "s05n-row-atom-coverage-v1.0",
        "git_head": git_head(),
        "platform": platform.platform(),
    }
    write_json(out_dir / "result.json", result)

    input_rows = []
    for key in ["frozen_s05h_config"]:
        p = Path(config[key])
        input_rows.append({"input": str(p), "sha256": sha256_file(p)})
    for p in [
        Path(config["frozen_s05h_dir"]) / "heldout_pair_residuals.csv",
        Path(config["frozen_s05h_dir"]) / "bstack_pair_table_preview.csv",
        Path(config["frozen_s05m_dir"]) / "reproduction_match_table.csv",
    ]:
        input_rows.append({"input": str(p), "sha256": sha256_file(p)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    write_json(out_dir / "manifest.json", {"result": "result.json", "report": "REPORT.md", "status": "complete", "ticket": config["ticket"]})
    write_report(out_dir, config, result, aggregate, atom_summary, axes, reproduction)
    print(f"wrote {out_dir}")
    print(f"winner={winner}")


if __name__ == "__main__":
    main()
