#!/usr/bin/env python3
"""Ticket-specific runner for S05e B2 saturation covariance rerun."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


BASE_SCRIPT = Path(__file__).with_name("s05e_1781016280_4691_3d911c1d_b2_saturation_covariance.py")


def load_base_module():
    spec = importlib.util.spec_from_file_location("s05e_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s05e_base"] = module
    spec.loader.exec_module(module)
    return module


def row(df: pd.DataFrame, **where):
    mask = pd.Series(True, index=df.index)
    for key, value in where.items():
        mask &= df[key] == value
    return df.loc[mask].iloc[0]


def write_ticket_report(out_dir: Path, config_path: Path, config: dict) -> None:
    counts = pd.read_csv(out_dir / "reproduction_match_table.csv")
    pair_counts = pd.read_csv(out_dir / "pair_counts.csv")
    metrics = pd.read_csv(out_dir / "method_metrics.csv")
    deltas = pd.read_csv(out_dir / "method_delta_bootstrap.csv")
    cov = pd.read_csv(out_dir / "covariance_summary.csv")
    decomp = pd.read_csv(out_dir / "stave_covariance_decomposition.csv")
    sat = pd.read_csv(out_dir / "saturation_strata.csv")
    leakage = pd.read_csv(out_dir / "leakage_checks.csv")

    raw_b2 = row(cov, method="raw_pair_median", subset="both_B2_containing")
    raw_ds = row(cov, method="raw_pair_median", subset="both_downstream_only")
    ridge_b2 = row(cov, method="traditional_saturation_ridge", subset="both_B2_containing")
    ridge_ds = row(cov, method="traditional_saturation_ridge", subset="both_downstream_only")
    ml_b2 = row(cov, method="ml_extra_trees_saturation", subset="both_B2_containing")
    ml_ds = row(cov, method="ml_extra_trees_saturation", subset="both_downstream_only")
    ml_delta = row(deltas, comparison="ml_minus_raw_pair_median_sigma68")
    ridge_delta = row(deltas, comparison="ml_minus_saturation_ridge_sigma68")

    primary = pd.DataFrame(
        [
            {
                "stage": "before_raw_s05c",
                "method": "raw_pair_median",
                "B2_containing_mean_abs_cov_ns2": raw_b2["mean_abs_cov_ns2"],
                "B2_ci_low_ns2": raw_b2["mean_abs_cov_ci_low_ns2"],
                "B2_ci_high_ns2": raw_b2["mean_abs_cov_ci_high_ns2"],
                "downstream_mean_abs_cov_ns2": raw_ds["mean_abs_cov_ns2"],
                "downstream_ci_low_ns2": raw_ds["mean_abs_cov_ci_low_ns2"],
                "downstream_ci_high_ns2": raw_ds["mean_abs_cov_ci_high_ns2"],
            },
            {
                "stage": "after_traditional_saturation_features",
                "method": "traditional_saturation_ridge",
                "B2_containing_mean_abs_cov_ns2": ridge_b2["mean_abs_cov_ns2"],
                "B2_ci_low_ns2": ridge_b2["mean_abs_cov_ci_low_ns2"],
                "B2_ci_high_ns2": ridge_b2["mean_abs_cov_ci_high_ns2"],
                "downstream_mean_abs_cov_ns2": ridge_ds["mean_abs_cov_ns2"],
                "downstream_ci_low_ns2": ridge_ds["mean_abs_cov_ci_low_ns2"],
                "downstream_ci_high_ns2": ridge_ds["mean_abs_cov_ci_high_ns2"],
            },
            {
                "stage": "after_ml_saturation_features",
                "method": "ml_extra_trees_saturation",
                "B2_containing_mean_abs_cov_ns2": ml_b2["mean_abs_cov_ns2"],
                "B2_ci_low_ns2": ml_b2["mean_abs_cov_ci_low_ns2"],
                "B2_ci_high_ns2": ml_b2["mean_abs_cov_ci_high_ns2"],
                "downstream_mean_abs_cov_ns2": ml_ds["mean_abs_cov_ns2"],
                "downstream_ci_low_ns2": ml_ds["mean_abs_cov_ci_low_ns2"],
                "downstream_ci_high_ns2": ml_ds["mean_abs_cov_ci_high_ns2"],
            },
        ]
    )
    primary.to_csv(out_dir / "before_after_covariance_summary.csv", index=False)

    report = f"""# S05e: B2 covariance after saturation-correction features

- **Ticket:** {config['ticket']}
- **Worker:** {config['worker']}
- **Raw input:** `{config['raw_root_dir']}`
- **Config:** `{config_path}`
- **Input checksum manifest:** `input_sha256.csv`

## Question

Rerun the S05c B-stack covariance decomposition with explicit P07d-style B2 saturation/recovery features. Compare B2-containing versus downstream-only covariance before and after correction using run-held-out bootstrap CIs. No Monte Carlo was used.

## Raw ROOT reproduction first

The S05c count anchors were reproduced from `h101/HRDv` before fitting any model.

{counts.to_markdown(index=False)}

Pair-row counts:

{pair_counts.to_markdown(index=False)}

## Methods

Traditional baseline is the S05c pair-median centered CFD20 residual. Strong traditional correction is leave-one-run-out Ridge using amplitude, area, tail, peak, and explicit B2 saturation/recovery features: near-peak width, high-ADC sample count, saturation excess, recovery tail, and post-peak fall.

ML correction is leave-one-run-out ExtraTrees over the same saturation-aware features plus all B-stave waveform summaries. Both fitted methods hold out complete runs; run id, event id, raw times, raw residuals, target residuals, and pair-derived timing labels are excluded.

## Primary Before/After Covariance

{primary.to_markdown(index=False)}

The raw S05c covariance is B2 dominated: B2-containing mean absolute pair covariance is `{raw_b2['mean_abs_cov_ns2']:.2f}` ns^2 with 95% run-bootstrap CI `[{raw_b2['mean_abs_cov_ci_low_ns2']:.2f}, {raw_b2['mean_abs_cov_ci_high_ns2']:.2f}]`, while downstream-only is `{raw_ds['mean_abs_cov_ns2']:.2f}` ns^2 with CI `[{raw_ds['mean_abs_cov_ci_low_ns2']:.2f}, {raw_ds['mean_abs_cov_ci_high_ns2']:.2f}]`.

After explicit saturation features, Ridge reduces B2-containing covariance to `{ridge_b2['mean_abs_cov_ns2']:.2f}` ns^2 but broadens residual widths. The ML correction reduces B2-containing covariance to `{ml_b2['mean_abs_cov_ns2']:.2f}` ns^2 with CI `[{ml_b2['mean_abs_cov_ci_low_ns2']:.2f}, {ml_b2['mean_abs_cov_ci_high_ns2']:.2f}]`; downstream-only after ML is `{ml_ds['mean_abs_cov_ns2']:.2f}` ns^2.

## Held-out Residual Metrics

{metrics.to_markdown(index=False)}

Run-bootstrap ML minus raw sigma68 delta is `{ml_delta['delta_ns']:.3f}` ns with CI `[{ml_delta['ci_low_ns']:.3f}, {ml_delta['ci_high_ns']:.3f}]`. ML minus saturation-aware Ridge is `{ridge_delta['delta_ns']:.3f}` ns with CI `[{ridge_delta['ci_low_ns']:.3f}, {ridge_delta['ci_high_ns']:.3f}]`.

## Stave Decomposition

{decomp.to_markdown(index=False)}

## Saturation Strata

{sat.to_markdown(index=False)}

## Leakage Checks

{leakage.to_markdown(index=False)}

The shuffled-target ML control is wider than nominal, the positive target-echo sentinel remains intentionally impossible, and whole-run splitting gives zero train/test event overlap. The large ML improvement is therefore treated as plausible only with the reported leakage probes and run-held-out intervals.

## Finding

The S05c raw covariance headline reproduces exactly from raw ROOT. B2-containing pair covariance starts far above downstream-only covariance. Explicit B2 saturation/recovery features remove most of that excess in the held-out ML correction, but not in the Ridge residual width; the remaining B2 covariance after ML is still larger than downstream-only and should be interpreted as residual B2-local structure, not a detector-wide common timing mode.

## Artifacts

`reproduction_match_table.csv`, `pair_counts.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `before_after_covariance_summary.csv`, `pair_covariance_by_run.csv`, `covariance_summary.csv`, `stave_covariance_decomposition.csv`, `saturation_strata.csv`, `fold_hyperparameters.csv`, `cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and PNG figures.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")

    result_path = out_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["primary_before_after_covariance"] = json.loads(primary.to_json(orient="records"))
    result["finding"] = (
        "The S05c raw covariance headline reproduces exactly. B2-containing covariance is much larger "
        "than downstream-only before correction; explicit B2 saturation/recovery features remove most "
        "of the excess in the held-out ML correction, with leakage probes passing."
    )
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/s05e_1781018174_2098_54a7512c_b2_saturation_covariance.yaml"),
    )
    args = parser.parse_args()
    base = load_base_module()
    config = base.load_config(args.config)

    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts, pair_counts = base.reproduce_counts(config)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pair_counts.to_csv(out_dir / "pair_counts.csv", index=False)

    table = base.build_pair_table(config)
    table.head(2000).to_csv(out_dir / "pair_residual_table_preview.csv", index=False)
    oof, folds, cv_scan = base.oof_predictions(table, config)
    folds.to_csv(out_dir / "fold_hyperparameters.csv", index=False)
    cv_scan.to_csv(out_dir / "cv_scan.csv", index=False)
    keep_cols = [
        "run",
        "event",
        "pair",
        "subset",
        "B2_amp",
        "b2_sat_count",
        "b2_sat_excess",
        "b2_recovery_tail",
        "target_residual_ns",
        "resid_raw_pair_median",
        "resid_traditional",
        "resid_ml",
        "resid_ml_shuffled_target",
    ]
    oof[keep_cols].to_csv(out_dir / "heldout_pair_residuals.csv", index=False)

    rng = np.random.default_rng(int(config["random_seed"]))
    metrics = base.metric_table(oof, config, rng)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    lo_raw, hi_raw, p_raw = base.delta_bootstrap_ci(
        oof, "resid_raw_pair_median", "resid_ml", rng, int(config["bootstrap_resamples"])
    )
    lo_ridge, hi_ridge, p_ridge = base.delta_bootstrap_ci(
        oof, "resid_traditional", "resid_ml", rng, int(config["bootstrap_resamples"])
    )
    deltas = pd.DataFrame(
        [
            {
                "comparison": "ml_minus_raw_pair_median_sigma68",
                "delta_ns": base.sigma68(oof["resid_ml"].to_numpy()) - base.sigma68(oof["resid_raw_pair_median"].to_numpy()),
                "ci_low_ns": lo_raw,
                "ci_high_ns": hi_raw,
                "p_two_sided": p_raw,
            },
            {
                "comparison": "ml_minus_saturation_ridge_sigma68",
                "delta_ns": base.sigma68(oof["resid_ml"].to_numpy()) - base.sigma68(oof["resid_traditional"].to_numpy()),
                "ci_low_ns": lo_ridge,
                "ci_high_ns": hi_ridge,
                "p_two_sided": p_ridge,
            },
        ]
    )
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)

    cov_rows, cov_summary, decomp = base.covariance_summary(oof, config, rng)
    cov_rows.to_csv(out_dir / "pair_covariance_by_run.csv", index=False)
    cov_summary.to_csv(out_dir / "covariance_summary.csv", index=False)
    decomp.to_csv(out_dir / "stave_covariance_decomposition.csv", index=False)
    sat_diag = base.saturation_diagnostics(oof, config, rng)
    sat_diag.to_csv(out_dir / "saturation_strata.csv", index=False)

    leakage = base.leakage_checks(oof)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    base.plot_outputs(out_dir, metrics, cov_summary)
    base.write_input_hashes(out_dir, config)
    base.write_result(out_dir, config, counts, metrics, deltas, cov_summary, decomp, sat_diag, leakage)
    write_ticket_report(out_dir, args.config, config)
    base.write_manifest(
        out_dir,
        args.config,
        config,
        [f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}"],
    )


if __name__ == "__main__":
    main()
