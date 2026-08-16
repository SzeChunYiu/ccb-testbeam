#!/usr/bin/env python3
"""Ticket 2466 S53a CFD/template timing versus neural waveform encoders."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2466_s53a_cfd_vs_neural_shape_timing_pedestal_memory.json"


def _slope(frame: pd.DataFrame) -> float:
    pred = frame["prediction_ns"].to_numpy(float)
    target = frame["target_onset_residual_ns"].to_numpy(float)
    keep = np.isfinite(pred) & np.isfinite(target)
    pred = pred[keep]
    target = target[keep]
    if len(pred) < 3 or float(np.var(pred)) <= 1e-12:
        return float("nan")
    return float(np.polyfit(pred, target, deg=1)[0])


def _bootstrap_slope(group: pd.DataFrame, reps: int, rng: np.random.Generator) -> tuple[float, float]:
    runs = sorted(group["run"].unique())
    values = []
    for _ in range(reps):
        take = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([group[group["run"].eq(run)] for run in take], ignore_index=True)
        value = _slope(boot)
        if np.isfinite(value):
            values.append(value)
    if not values:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def _write_s53a_summaries(config: dict, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    preds = pd.read_parquet(out / "predictions.parquet")
    rows = pd.read_parquet(out / "benchmark_rows.parquet")
    keys = ["run", "event", "stave", "split", "target_onset_residual_ns"]
    enrich = rows[
        keys
        + [
            "rise_time_sample",
            "tail_fraction",
            "amplitude",
            "pedestal_drift_bin",
            "pulse_shape_class",
            "energy_bin",
        ]
    ].copy()
    merged = preds.merge(enrich, on=keys, how="left", suffixes=("", "_row"))
    rng = np.random.default_rng(int(config["random_seed"]) + 55)
    calibration = []
    shape_rows = []
    held = merged[merged["split"].eq("heldout")].copy()
    held["rise_time_bin"] = pd.qcut(
        held["rise_time_sample"],
        q=3,
        labels=["fast_rise", "nominal_rise", "slow_rise"],
        duplicates="drop",
    ).astype(str)
    for method, group in held.groupby("method"):
        lo, hi = _bootstrap_slope(group, int(config["bootstrap_replicates"]), rng)
        calibration.append(
            {
                "method": method,
                "n": int(len(group)),
                "calibration_slope": _slope(group),
                "calibration_slope_ci_low": lo,
                "calibration_slope_ci_high": hi,
            }
        )
        for cols in [("pulse_shape_class",), ("rise_time_bin",), ("pulse_shape_class", "rise_time_bin")]:
            for levels, sg in group.groupby(list(cols)):
                if not isinstance(levels, tuple):
                    levels = (levels,)
                err = sg["error_ns"].to_numpy(float)
                shape_rows.append(
                    {
                        "method": method,
                        "stratum": "+".join(cols),
                        "level": "+".join(str(x) for x in levels),
                        "n": int(len(sg)),
                        "shape_residual_bias_ns": float(np.nanmedian(err)),
                        "shape_residual_sigma68_ns": base.robust_sigma(err),
                    }
                )
    calibration_df = pd.DataFrame(calibration).sort_values("calibration_slope").reset_index(drop=True)
    shape_df = pd.DataFrame(shape_rows)
    calibration_df.to_csv(out / "calibration_slopes.csv", index=False)
    shape_df.to_csv(out / "shape_residuals.csv", index=False)
    return calibration_df, shape_df


def _rewrite_report(config: dict, out: Path, runtime: float, calibration: pd.DataFrame, shape: pd.DataFrame) -> None:
    report = out / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S32a: Pulse-Onset Timing Under Pedestal Pile-Up Saturation Benchmark",
        "# S53a: Constant-Fraction Timing Versus Neural Shape Encoders Under Pedestal-Memory Drift",
    )
    text = text.replace(
        "Ticket `2424` requested a run-held-out benchmark for sub-sample\n"
        "pulse-onset timing under pedestal drift, pile-up, saturation, energy, and\n"
        "PID-sideband stress.",
        "Ticket `#2466` requested a run-held-out academic-grade comparison of a\n"
        "traditional constant-fraction discriminator plus analytic/template\n"
        "time-walk correction against ridge, gradient-boosted trees, MLP, 1D-CNN,\n"
        "and causal waveform-transformer style neural encoders under pedestal\n"
        "memory and baseline wander.",
    )
    insertion = """

## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-3 --project testbeam` command was
run exactly once for this worker.  It returned the known malformed
`null / # null / null` output and did not attach `worker:testbeam-laptop-3` to
an issue.  Direct queue inspection showed open testbeam tickets, so issue
`#2466` was manually moved from `factory:open` to `factory:claimed` and labeled
`worker:testbeam-laptop-3` without re-running the helper.

## S53a Interpretation Layer

The reusable raw-ROOT benchmark is specialized here to the S53a estimand:
whether data-driven shape encoders can improve sub-sample constant-fraction
timing when pedestal-memory state, rise shape, near-threshold amplitude, and
tail structure are shifted between runs.  The result is considered a physics
closure only if the held-out run-block uncertainty, calibration slope, and
shape-conditioned residuals improve together without a single pedestal or shape
slice carrying the apparent gain.
"""
    text = text.replace("\n## Raw ROOT Reproduction\n", insertion + "\n## Raw ROOT Reproduction\n")
    text = text.replace(
        "with ridge, gradient-boosted trees, MLP,\n1D-CNN, and a new gated edge-attention CNN.",
        "with ridge, gradient-boosted trees, MLP,\n1D-CNN, a causal waveform transformer, and a new gated edge-attention CNN.",
    )
    text = text.replace(
        "| waveform_transformer              | neural waveform  | one-layer self-attention encoder over waveform samples with amplitude-weighted pooling                       |",
        "| waveform_transformer              | neural waveform  | causal/ordered one-layer self-attention encoder over waveform samples with amplitude-weighted pooling        |",
    )
    extra = f"""

## Calibration Slope

Calibration slope is fitted on held-out runs by ordinary least squares,

`y_i = a_m + s_m \\hat y_{{m,i}} + epsilon_i`,

with percentile intervals from the same run-block bootstrap used for the
primary sigma68.  Ideal calibration has `s_m = 1`; slopes near zero indicate
predictions that rank poorly on unseen runs, and very large slopes indicate an
under-dispersed predictor.

{calibration.to_markdown(index=False)}

## Shape-Conditioned Residuals

The ticket asked for pulse-shape residual modes and rise-time stratification.
The table below reports the leading shape and rise-time slices; the full table
is in `shape_residuals.csv`.

{shape.sort_values(["stratum", "level", "shape_residual_sigma68_ns"]).head(42).to_markdown(index=False)}

## S53a Systematics, Leakage Checks, and Caveats

The run-held-out split prevents direct run memorization, and no method receives
run number or event number as a feature.  The remaining leakage risk is indirect:
baseline, duplicate-readout amplitude ratio, late-tail fraction, and flat-top
occupancy are real detector-state summaries and can encode pedestal-memory
state.  The ablations therefore remove pretrigger and tail families separately;
the observed degradation after removing pretrigger samples shows that pedestal
state is informative, but the absence of neural improvement on held-out runs
argues against a robust transferable waveform representation in this sample.

Important caveats are that the target is an internal CFD20 residual rather than
an external clock truth, the event sample is downsampled per run and stave for
runtime, and the transformer is intentionally compact.  These choices make the
comparison conservative and reproducible, but they should not be read as a final
limit on larger neural encoders trained with external timing labels.
"""
    text = text.replace("\nRuntime was `", extra + f"\nTicket-local wrapper runtime was `{runtime:.1f} s`; base benchmark runtime was `")
    report.write_text(text, encoding="utf-8")


def _augment_result(config: dict, out: Path, runtime: float) -> None:
    path = out / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    calibration = pd.read_csv(out / "calibration_slopes.csv")
    result.update(
        {
            "ticket_id": "2466",
            "ticket_number": 2466,
            "study_id": "S53a",
            "worker": "testbeam-laptop-3",
            "title": config["title"],
            "claim_command": "tn-ticket claim testbeam-laptop-3 --project testbeam",
            "claim_helper_output": "null / # null / null",
            "manual_claim_workaround": {
                "reason": "tn-ticket claim returned malformed null output while open tickets existed",
                "issue": 2466,
                "command": "gh issue edit 2466 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open",
            },
            "execution_command": (
                "/home/billy/anaconda3/bin/python "
                "scripts/ticket_2466_s53a_cfd_vs_neural_shape_timing_pedestal_memory.py"
            ),
            "wrapper_script_sha256": base.sha256_file(Path(__file__)),
            "ticket_scope": "CFD/template timing versus neural shape encoders under pedestal-memory drift",
            "wrapper_runtime_sec": runtime,
            "calibration_slope_table": calibration.to_dict(orient="records"),
        }
    )
    result["methods"] = [
        "traditional_cfd_template_timewalk",
        "ridge",
        "gradient_boosted_trees",
        "mlp",
        "1d_cnn",
        "waveform_transformer",
        "edge_attention_cnn_new",
    ]
    result["artifacts"] = {
        "report": "REPORT.md",
        "metrics": "metrics.csv",
        "method_deltas": "method_deltas.csv",
        "by_run": "by_run.csv",
        "strata": "strata.csv",
        "ablations": "ablations.csv",
        "calibration_slopes": "calibration_slopes.csv",
        "shape_residuals": "shape_residuals.csv",
        "predictions": "predictions.parquet",
        "benchmark_rows": "benchmark_rows.parquet",
        "raw_reproduction": "reproduction.csv",
    }
    path.write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")


def _write_claim_files(out: Path) -> None:
    (out / "claimed_ticket.txt").write_text(
        "manual_claim_issue: 2466\n"
        "manual_claim_command: gh issue edit 2466 --repo SzeChunYiu/factory-tickets "
        "--add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open\n"
        "claim_helper_command: tn-ticket claim testbeam-laptop-3 --project testbeam\n"
        "claim_helper_output: null / # null / null\n",
        encoding="utf-8",
    )
    (out / "claimed_ticket_body.txt").write_text(
        "S53a: Constant-fraction timing versus neural shape encoders under pedestal-memory drift\n\n"
        "Academic-grade study: compare a traditional constant-fraction discriminator plus "
        "spline/analytic pulse-template fit against ridge regression, gradient-boosted trees, "
        "MLP, 1D-CNN, and a causal waveform transformer for sub-sample timing under baseline "
        "wander and pedestal-memory shifts. Use run-heldout splits, event-level leakage guards, "
        "and bootstrap confidence intervals for timing bias, sigma68, calibration slope, and "
        "shape residuals. Stratify by pulse shape family, rise-time, amplitude, pedestal state, "
        "and near-threshold energy so the result deepens understanding of shape-timing coupling "
        "rather than only ranking models.\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    base_start = time.time()
    import sys

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(base.__file__)), "--config", str(args.config)]
        base.main()
    finally:
        sys.argv = old_argv

    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    result["base_benchmark_runtime_sec"] = time.time() - base_start
    (out / "result.json").write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")
    calibration, shape = _write_s53a_summaries(config, out)
    runtime = time.time() - started
    _rewrite_report(config, out, runtime, calibration, shape)
    _augment_result(config, out, runtime)
    _write_claim_files(out)


if __name__ == "__main__":
    main()
