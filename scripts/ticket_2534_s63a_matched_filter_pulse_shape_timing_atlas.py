#!/usr/bin/env python3
"""Ticket 2534 / S63a matched-filter pulse-shape timing atlas."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import s43b_1784349946_602_171c4316_waveform_derivative_pulse_shape_timing_benchmark as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2534_s63a_matched_filter_pulse_shape_timing_atlas.json"


def _metric(group: pd.DataFrame) -> dict:
    err = group["error_ns"].to_numpy(float)
    return {
        "n": int(len(group)),
        "bias_ns": float(np.median(err)),
        "sigma68_ns": float(0.5 * (np.percentile(err, 84) - np.percentile(err, 16))),
        "rms_ns": float(np.sqrt(np.mean(err**2))),
        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(err) > 5.0)),
    }


def _bootstrap_ci(group: pd.DataFrame, rng: np.random.Generator, reps: int) -> dict:
    runs = sorted(group["run"].unique())
    samples = {"sigma68_ns": [], "bias_ns": [], "tail_fraction_abs_gt_5ns": []}
    for _ in range(reps):
        take = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([group[group["run"].eq(r)] for r in take], ignore_index=True)
        vals = _metric(boot)
        for key in samples:
            samples[key].append(vals[key])
    return {
        f"{key}_ci_low": float(np.percentile(values, 2.5))
        for key, values in samples.items()
    } | {
        f"{key}_ci_high": float(np.percentile(values, 97.5))
        for key, values in samples.items()
    }


def _write_atlas_tables(out: Path, config: dict) -> dict:
    rng = np.random.default_rng(int(config["random_seed"]) + 6300)
    predictions = pd.read_csv(out / "predictions.csv.gz")
    rows = pd.read_csv(out / "benchmark_rows.csv.gz")
    joined = predictions.merge(
        rows[
            [
                "run",
                "event",
                "stave",
                "split",
                "amplitude",
                "baseline",
                "pretrigger_slope",
                "tail_fraction",
                "rise_time_sample",
            ]
        ],
        on=["run", "event", "stave", "split"],
        how="left",
    )
    held = joined[joined["split"].eq("heldout")].copy()
    held["current_stratum"] = np.where((held["run"].astype(int) % 2) == 0, "even_run_current_proxy", "odd_run_current_proxy")
    held["pedestal_window"] = pd.cut(
        held["baseline"],
        bins=[-np.inf, -35.0, 35.0, np.inf],
        labels=["negative_pedestal", "nominal_pedestal", "positive_pedestal"],
    ).astype(str)
    held["phase_window"] = pd.cut(
        held["rise_time_sample"],
        bins=[-np.inf, 1.0, 2.0, 3.5, np.inf],
        labels=["fast_phase", "nominal_phase", "slow_phase", "broad_phase"],
    ).astype(str)
    held["energy_window"] = pd.qcut(
        held["amplitude"],
        q=4,
        labels=["q1_low_energy", "q2_mid_energy", "q3_high_energy", "q4_highest_energy"],
        duplicates="drop",
    ).astype(str)

    axes = [
        "run",
        "current_stratum",
        "pedestal_window",
        "phase_window",
        "energy_window",
        "pulse_shape_class",
        "pileup_separation_bin",
        "saturation_onset_bin",
        "pid_sideband",
    ]
    atlas_rows = []
    for axis in axes:
        for (method, level), group in held.groupby(["method", axis], observed=False):
            vals = _metric(group)
            vals.update(_bootstrap_ci(group, rng, 200) if axis != "run" else {})
            atlas_rows.append({"axis": axis, "level": str(level), "method": str(method), **vals})
    atlas = pd.DataFrame(atlas_rows).sort_values(["axis", "level", "sigma68_ns", "method"]).reset_index(drop=True)
    atlas.to_csv(out / "pulse_shape_timing_atlas.csv", index=False)

    winner = json.loads((out / "result.json").read_text(encoding="utf-8"))["winner"]["method"]
    win = held[held["method"].eq(winner)].copy()
    systematics = []
    for axis in axes[1:]:
        grouped = win.groupby(axis, observed=False)
        metrics = []
        for level, group in grouped:
            row = {"level": str(level), **_metric(group)}
            metrics.append(row)
        mf = pd.DataFrame(metrics)
        if mf.empty:
            continue
        worst = mf.loc[mf["sigma68_ns"].idxmax()]
        best = mf.loc[mf["sigma68_ns"].idxmin()]
        systematics.append(
            {
                "axis": axis,
                "winner_method": winner,
                "levels": int(mf["level"].nunique()),
                "best_level": str(best["level"]),
                "best_sigma68_ns": float(best["sigma68_ns"]),
                "worst_level": str(worst["level"]),
                "worst_sigma68_ns": float(worst["sigma68_ns"]),
                "sigma68_span_ns": float(worst["sigma68_ns"] - best["sigma68_ns"]),
                "max_abs_bias_ns": float(mf["bias_ns"].abs().max()),
                "max_tail_fraction_abs_gt_5ns": float(mf["tail_fraction_abs_gt_5ns"].max()),
            }
        )
    pd.DataFrame(systematics).sort_values("sigma68_span_ns", ascending=False).to_csv(
        out / "systematics_summary.csv", index=False
    )

    surrogate = []
    for method, group in held.groupby("method", observed=False):
        sat = group[group["saturation_onset_bin"].astype(str).ne("unsaturated")]
        pile = group[group["pileup_separation_bin"].astype(str).ne("isolated")]
        pid = group[group["pid_sideband"].astype(str).ne("core")]
        surrogate.append(
            {
                "method": str(method),
                "pileup_false_positive_proxy": float(np.mean(np.abs(pile["error_ns"]) > 5.0)) if len(pile) else 0.0,
                "saturation_tag_leakage_proxy": float(np.mean(np.abs(sat["error_ns"]) > 5.0)) if len(sat) else 0.0,
                "energy_bias_proxy_ns_per_log_adc": float(np.polyfit(np.log1p(group["amplitude"]), group["error_ns"], 1)[0]),
                "pid_boundary_movement_proxy_ns": float(
                    pid["error_ns"].median() - group[group["pid_sideband"].astype(str).eq("core")]["error_ns"].median()
                )
                if len(pid) and len(group[group["pid_sideband"].astype(str).eq("core")])
                else 0.0,
            }
        )
    pd.DataFrame(surrogate).sort_values("method").to_csv(out / "surrogate_detector_metrics.csv", index=False)

    return {
        "pulse_shape_timing_atlas": "pulse_shape_timing_atlas.csv",
        "systematics_summary": "systematics_summary.csv",
        "surrogate_detector_metrics": "surrogate_detector_metrics.csv",
    }


def _rewrite_report(config: dict, out: Path, runtime: float) -> None:
    report = out / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S43b Waveform Derivative Pulse-Shape Timing Benchmark",
        "# S63a Matched-Filter Pulse-Shape Timing Atlas",
    )
    text = text.replace(
        "Ticket `2534` asks whether waveform derivative and curvature\n"
        "information improves arrival-time extraction under pedestal drift.",
        "Ticket `#2534` asks for a run-heldout pulse-shape and timing atlas under\n"
        "pedestal drift and pile-up occupancy.  The traditional comparator is the\n"
        "matched-filter/template chi2, constant-fraction timing, analytic time-walk,\n"
        "and derivative residual correction family, benchmarked against ridge,\n"
        "gradient-boosted trees, MLP, 1D-CNN, a compact transformer sequence encoder,\n"
        "and a derivative-gated transformer architecture.",
    )
    claim = f"""

## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-1 --project testbeam` command was
run exactly once.  The helper returned the malformed payload

```text
{config['claim_command_output'].rstrip()}
```

without moving an issue.  Read-only queue inspection showed open testbeam
tickets and no `worker:testbeam-laptop-1` claimed issue, so issue `#2534` was
bound by the same label swap the helper performs:

```text
{config['manual_claim_workaround']['command']}
```

No second `tn-ticket claim` invocation was run.
"""
    text = text.replace("\n## Raw ROOT Reproduction\n", claim + "\n## Raw ROOT Reproduction\n")
    text = text.replace(
        "The new architecture is sensible for this ticket because the hypothesis is not\n"
        "generic waveform learning; it is that edge and curvature channels localize\n"
        "pulse-shape timing changes under pedestal drift.",
        "The new architecture is sensible for this ticket because the hypothesis is not\n"
        "generic waveform learning; it is that edge and curvature channels localize\n"
        "pulse-shape timing changes under pedestal drift and pile-up occupancy.",
    )
    insert = """

## Pulse-Shape Timing Atlas

The ticket-specific atlas is written to `pulse_shape_timing_atlas.csv`.  It
crosses method performance with run, current proxy, pedestal window, phase
window, energy quartile, pulse-shape class, injected pile-up spacing,
saturation-onset tag, and PID-sideband proxy.  Non-run axes include run-block
bootstrap confidence intervals for `sigma68_ns`, median bias, and the
`|error| > 5 ns` tail fraction.

`systematics_summary.csv` compresses the winning method's axis spans; it is the
primary caveat table for pedestal, phase, pile-up, saturation, energy, and PID
movement.  `surrogate_detector_metrics.csv` reports the requested detector
surrogates: pile-up false-positive tail proxy, saturation-tag leakage proxy,
energy-bias slope proxy, and PID boundary movement proxy.  These are deliberately
named proxies because the raw HRDv waveform stream used here does not carry
external PID truth, independent energy calibration residuals, or hand-labeled
pile-up false positives for every pulse.
"""
    text = text.replace("\n## Derivative and Curvature Ablations\n", insert + "\n## Derivative and Curvature Ablations\n")
    text = text.replace(
        "Runtime was `",
        f"Ticket-local wrapper runtime was `{runtime:.1f} s`; benchmark runtime was `",
    )
    report.write_text(text, encoding="utf-8")


def _augment_result(config: dict, out: Path, runtime: float, atlas_artifacts: dict) -> None:
    path = out / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": str(config["ticket_id"]),
            "ticket_number": int(config["ticket_number"]),
            "study_id": config["study_id"],
            "worker": config["worker"],
            "title": config["title"],
            "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
            "claim_command_output": config["claim_command_output"],
            "manual_claim_workaround": config["manual_claim_workaround"],
            "ticket_scope": "run-heldout matched-filter pulse-shape timing atlas under pedestal drift and pile-up occupancy",
            "traditional_method": "matched-filter/template chi2 plus CFD timing, analytic time-walk, and derivative residual correction",
            "wrapper_script_sha256": base.sha256_path(Path(__file__)),
            "wrapper_runtime_sec": runtime,
            "surrogate_metric_note": "pile-up false-positive, saturation leakage, energy bias, and PID boundary movement are waveform-derived proxies, not external detector-truth measurements",
            "novel_tickets_appended": [],
            "next_tickets": [],
        }
    )
    result["artifacts"].update(atlas_artifacts)
    path.write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")


def _write_claim_files(config: dict, out: Path) -> None:
    text = (
        config["claimed_ticket_text"]
        + "\nclaim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n"
        + "claim_helper_output:\n"
        + config["claim_command_output"]
        + "\nmanual_claim_workaround:\n"
        + config["manual_claim_workaround"]["command"]
        + "\n"
    )
    (out / "claimed_ticket.txt").write_text(text, encoding="utf-8")
    (out / "claimed_ticket_body.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--reuse-existing-base", action="store_true")
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]

    required = ["predictions.csv.gz", "benchmark_rows.csv.gz", "result.json", "REPORT.md"]
    if not args.reuse_existing_base or not all((out / name).exists() for name in required):
        old_argv = sys.argv[:]
        try:
            sys.argv = [str(Path(base.__file__)), "--config", str(args.config)]
            base.main()
        finally:
            sys.argv = old_argv

    atlas_artifacts = _write_atlas_tables(out, config)
    runtime = time.time() - started
    _rewrite_report(config, out, runtime)
    _augment_result(config, out, runtime, atlas_artifacts)
    _write_claim_files(config, out)
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    (out / "manifest.json").write_text(json.dumps(base.artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
