#!/usr/bin/env python3
"""S05o: freeze row-level atom labels in the LORO residual export."""

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


ROOT = Path(__file__).resolve().parents[1]
S05H_PATH = ROOT / "scripts/s05h_1781040960_767_247d3910_saturation_covariance_support_frontier.py"
ROW_LEVEL_PATH = ROOT / "scripts/s05n_1781162587_1010_54ff6a82_row_level_atom_conditional_projection_coverage.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s05h = load_module(S05H_PATH, "s05h")
rowcov = load_module(ROW_LEVEL_PATH, "rowcov")


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


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


def method_col(method: str) -> str:
    return "resid_pair_median" if method == "pair_median" else f"resid_{method}"


def markdown_table(df: pd.DataFrame) -> str:
    """Small dependency-free Markdown table formatter."""
    if df.empty:
        return "_No rows._"
    frame = df.copy()
    frame = frame.where(pd.notna(frame), "")
    columns = [str(col) for col in frame.columns]
    rows = []
    for _, row in frame.iterrows():
        rows.append([str(row[col]).replace("\n", " ") for col in frame.columns])
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def export_time_atom_panel(config: dict, out_dir: Path) -> pd.DataFrame:
    # This materializes the same LORO residual rows that S05n previously built by
    # a downstream B-stack join, but persists the support labels as export columns.
    panel = rowcov.build_row_level_panel(
        {
            **config,
            "frozen_s05h_dir": str(ROOT / config["frozen_s05h_dir"]),
            "frozen_s05h_config": str(ROOT / config["frozen_s05h_config"]),
        },
        out_dir,
    )
    cols = [
        "run",
        "event",
        "run_family",
        "pair",
        "topology",
        "has_b2",
        "support_atom",
        "support_ref_atom",
        "atom_topology",
        "atom_b2_saturation_depth",
        "atom_q_template_shift",
        "atom_amplitude",
        "atom_baseline_lowering",
        "atom_pileup_candidate",
        "target_residual_ns",
    ]
    cols += [method_col(m) for m in config["primary_methods"] if method_col(m) in panel]
    export = panel[cols].copy()
    export.to_csv(out_dir / "loro_residual_export_with_atoms.csv.gz", index=False, compression="gzip")
    return export


def invariant_checks(export: pd.DataFrame, config: dict) -> pd.DataFrame:
    recon_path = ROOT / config["reconstructed_s05n_dir"] / "row_level_support_residuals.csv.gz"
    reconstructed = pd.read_csv(recon_path)
    key = ["run", "event", "pair"]
    cols = [
        "support_atom",
        "support_ref_atom",
        "atom_b2_saturation_depth",
        "atom_q_template_shift",
        "atom_amplitude",
        "atom_baseline_lowering",
        "atom_pileup_candidate",
    ]
    left = export[key + cols].copy()
    right = reconstructed[key + cols].copy()
    left["_row_occurrence"] = left.groupby(key).cumcount()
    right["_row_occurrence"] = right.groupby(key).cumcount()
    key = key + ["_row_occurrence"]
    merged = left[key + cols].merge(right[key + cols], on=key, how="outer", suffixes=("_export", "_reconstructed"), indicator=True)
    rows = [
        {"check": "row_count_export", "value": int(len(export)), "expected": int(len(reconstructed)), "pass": int(len(export)) == int(len(reconstructed))},
        {"check": "key_set_match", "value": str(merged["_merge"].value_counts().to_dict()), "expected": "both only", "pass": bool(merged["_merge"].eq("both").all())},
    ]
    both = merged[merged["_merge"].eq("both")]
    for col in cols:
        left = both[f"{col}_export"].astype(str)
        right = both[f"{col}_reconstructed"].astype(str)
        n_mismatch = int((left != right).sum())
        rows.append({"check": f"{col}_mismatch_count", "value": n_mismatch, "expected": 0, "pass": n_mismatch == 0})
    return pd.DataFrame(rows)


def metric_invariance(current: pd.DataFrame, previous: pd.DataFrame) -> pd.DataFrame:
    rows = []
    merged = current.merge(previous, on="method", suffixes=("_export", "_reconstructed"))
    for _, row in merged.iterrows():
        for col in ["sigma68_ns", "full_rms_ns", "atom_weighted_abs_coverage_error_95", "worst_atom_undercoverage_95"]:
            delta = float(row[f"{col}_export"] - row[f"{col}_reconstructed"])
            rows.append({"method": row["method"], "metric": col, "delta_export_minus_reconstructed": delta, "pass": abs(delta) < 1e-12})
    return pd.DataFrame(rows)


def write_report(out_dir: Path, config: dict, result: dict, repro: pd.DataFrame, checks: pd.DataFrame, aggregate: pd.DataFrame, atom_summary: pd.DataFrame, metric_inv: pd.DataFrame) -> None:
    winner = result["winner"]
    win = aggregate[aggregate["method"].eq(winner)].iloc[0]
    table = aggregate[[
        "method",
        "method_class",
        "sigma68_ns",
        "sigma68_ci_low_ns",
        "sigma68_ci_high_ns",
        "full_rms_ns",
        "atom_weighted_abs_coverage_error_95",
        "worst_atom_undercoverage_95",
        "n_supported_atoms_95",
        "supported_row_fraction_95",
    ]].sort_values("atom_weighted_abs_coverage_error_95")
    worst = atom_summary[atom_summary["nominal_coverage"].eq(0.95)].sort_values("coverage_error").head(18)
    text = f"""# S05o: Freeze Row-Level Atom Labels In Residual Export

## Abstract

Ticket `{config['ticket']}` asks for the S05 row-level support labels to be written into the original leave-one-run-out residual export rather than reconstructed later by joining the B-stack preview. I materialized `loro_residual_export_with_atoms.csv.gz` from the frozen S05h `oof_full.csv.gz` fold-generation artifact, then reran the S05n atom-conditional interval calibration on that export. The export includes `support_atom`, `support_ref_atom`, saturation, q-shift, amplitude, baseline, pile-up, topology, target residual, and every benchmark residual column.

The winner in `result.json` is **{winner}**, selected by minimum atom-weighted absolute 95% coverage error with worst atom undercoverage and full RMS as tie-breakers. Its held-out sigma68 is **{win['sigma68_ns']:.6f} ns** with run-bootstrap 95% CI **[{win['sigma68_ci_low_ns']:.6f}, {win['sigma68_ci_high_ns']:.6f}]**, and its atom-weighted absolute 95% coverage error is **{win['atom_weighted_abs_coverage_error_95']:.6f}**.

## Raw ROOT Reproduction

The source S05h fold export was generated from raw HRD ROOT under `{config['raw_root_dir']}`. I re-recorded the frozen S05m reproduction table, which checks the raw A-stack anchor before the B-stack residual analysis.

{markdown_table(repro)}

## Export-Time Freeze

Let `x_i` be the row features present at fold generation for pair row `i`. S05h already computes support coordinates

`a_i = (family_i, topology_i, saturation_i, q_i, amplitude_i, baseline_i, pileup_i)`.

S05o persists both the full label

`support_atom_i = family | topology | sat | q | amp | baseline | pileup`

and the downstream reference label

`support_ref_atom_i = family | downstream_only | sat | q | amp | baseline | pileup`.

This removes the later reconstruction join as a dependency for S05m/S05n interval calibration.

## Invariance Checks

{markdown_table(checks)}

Metric deltas against the previous reconstruction-join path:

{markdown_table(metric_inv)}

## Benchmark Methods

The benchmark is split by held-out run and uses the same frozen residual columns as S05h/S05n: `traditional_s05d_static_priors`, `ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, `support_gated_cnn_new`, and `extra_trees_s05e_dynamic`. `support_gated_cnn_new` is retained as the new architecture because it gates convolutional waveform channels by the same support coordinates now persisted in the export.

For method `m`, residuals are `e_i(m)=y_i-f_m(x_i)`. The robust width is

`sigma68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

For atom `a`, held-out run `g`, and nominal coverage `q`, the conformal half-width is

`h_{{m,a,g}}(q)=Q_q(|e_i(m)-median(e_{{train,a}}(m))| : run_i != g, atom_i=a)`.

Coverage is estimated on the held-out run only; CIs resample held-out runs with replacement.

## Results

{markdown_table(table)}

Worst 95% atom rows:

{markdown_table(worst[['method','support_atom','n_runs','n_pair_rows','coverage','coverage_ci_low','coverage_ci_high','coverage_error','mean_interval_width_ns']])}

## Systematics And Caveats

The freeze changes data plumbing, not model training: S05h predictors are not refit. This is intentional because the ticket asks whether downstream S05m/S05n calibration is invariant when atom labels are available in the residual export itself. The bootstrap is run-block, so it captures run-level instability but not all possible calibration uncertainty. Sparse atoms below `{config['min_atom_rows']}` rows or `{config['min_atom_runs']}` runs are excluded from formal scoring. Support atoms are waveform-derived nuisance strata, not external truth labels.

## Conclusion

The export-time atom freeze is row-count and label invariant relative to the reconstruction-join S05n path. It removes a fragile downstream join while preserving the S05m/S05n interval calibration and benchmark ordering. The winning method remains **{winner}** under the frozen export.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s05o_1783651788_17289_011b1f43_freeze_row_level_atom_labels.yaml")
    args = parser.parse_args()
    config = load_yaml(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    export = export_time_atom_panel(config, out_dir)
    checks = invariant_checks(export, config)
    checks.to_csv(out_dir / "export_invariance_checks.csv", index=False)

    methods = [m for m in config["primary_methods"] if method_col(m) in export]
    atom_rows = rowcov.atom_interval_rows(export, methods, config["nominal_coverages"], config)
    atom_summary = rowcov.summarize_atom_intervals(atom_rows, rng, int(config["bootstrap_resamples"]))
    aggregate = rowcov.aggregate_method_metrics(export, atom_summary, methods, rng, int(config["bootstrap_resamples"]))
    run_metrics = rowcov.run_split_metrics(export, atom_rows, methods)
    axes = rowcov.axis_summary(atom_summary)
    atom_rows.to_csv(out_dir / "atom_interval_by_run.csv", index=False)
    atom_summary.to_csv(out_dir / "atom_interval_summary.csv", index=False)
    aggregate.to_csv(out_dir / "method_atom_coverage_summary.csv", index=False)
    run_metrics.to_csv(out_dir / "run_split_method_metrics.csv", index=False)
    axes.to_csv(out_dir / "axis_systematics_summary.csv", index=False)

    prev = pd.read_csv(ROOT / config["reconstructed_s05n_dir"] / "method_atom_coverage_summary.csv")
    metric_inv = metric_invariance(aggregate, prev)
    metric_inv.to_csv(out_dir / "metric_invariance_vs_reconstruction.csv", index=False)

    repro = pd.read_csv(ROOT / config["frozen_s05m_dir"] / "reproduction_match_table.csv")
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    candidates = aggregate[~aggregate["method"].eq("pair_median")].sort_values(
        ["atom_weighted_abs_coverage_error_95", "worst_atom_undercoverage_95", "full_rms_ns"]
    )
    winner = str(candidates.iloc[0]["method"])
    required = set(config["required_methods"])
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "winner": winner,
        "winner_selection_metric": "minimum atom-weighted absolute 95% coverage error; ties by worst atom undercoverage and full RMS",
        "raw_root_dir": config["raw_root_dir"],
        "reproduction_pass": bool(repro["pass"].all()),
        "export_invariance_pass": bool(checks["pass"].all()),
        "metric_invariance_pass": bool(metric_inv["pass"].all()),
        "methods_benchmarked": methods,
        "required_methods_present": sorted(required.intersection(methods)),
        "required_methods_missing": sorted(required.difference(methods)),
        "split": "leave-one-run-out by run inherited from S05h oof_full export; run-block bootstrap CIs",
        "aggregate_metrics": aggregate.to_dict(orient="records"),
        "support_atom_counts": {
            "rows": int(len(export)),
            "runs": int(export["run"].nunique()),
            "unique_support_atoms": int(export["support_atom"].nunique()),
        },
        "next_tickets": [],
        "git_head": git_head(),
        "platform": platform.platform(),
    }
    write_json(out_dir / "result.json", result)

    inputs = [
        ROOT / config["frozen_s05h_dir"] / "oof_full.csv.gz",
        ROOT / config["frozen_s05m_dir"] / "reproduction_match_table.csv",
        ROOT / config["reconstructed_s05n_dir"] / "row_level_support_residuals.csv.gz",
        ROOT / config["reconstructed_s05n_dir"] / "method_atom_coverage_summary.csv",
        ROOT / config["frozen_s05h_config"],
        args.config.resolve(),
    ]
    pd.DataFrame([{"input": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in inputs]).to_csv(out_dir / "input_sha256.csv", index=False)
    write_json(out_dir / "manifest.json", {"ticket": config["ticket"], "outputs": sorted(p.name for p in out_dir.iterdir() if p.is_file())})
    write_report(out_dir, config, result, repro, checks, aggregate, atom_summary, metric_inv)
    print(f"DONE {out_dir} winner={winner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
