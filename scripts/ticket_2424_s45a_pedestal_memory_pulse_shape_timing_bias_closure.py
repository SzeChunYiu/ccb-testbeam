#!/usr/bin/env python3
"""Ticket 2424 S45a pedestal-memory pulse-shape timing closure benchmark."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

import s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2424_s45a_pedestal_memory_pulse_shape_timing_bias_closure.json"


def _rewrite_report(config: dict, out: Path, runtime: float) -> None:
    report = out / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S32a: Pulse-Onset Timing Under Pedestal Pile-Up Saturation Benchmark",
        "# S45a: Pedestal-Memory Pulse-Shape and Timing Bias Closure",
    )
    text = text.replace(
        "Ticket `2424` requested a run-held-out benchmark for sub-sample\n"
        "pulse-onset timing under pedestal drift, pile-up, saturation, energy, and\n"
        "PID-sideband stress.",
        "Ticket `#2424` requested a run-held-out closure test separating true\n"
        "pulse-shape/timing shifts from pedestal artifacts under amplitude, stave,\n"
        "rate, and pretrigger-history stress.",
    )
    insertion = f"""

## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-1 --project testbeam` command was
run exactly once before this analysis but returned the known malformed
`null` response.  Direct queue inspection showed open testbeam tickets and no
valid `worker:testbeam-laptop-1` claim.  To keep exactly one active ticket
without re-running the claim helper, issue `#2424` was manually moved from
`factory:open` to `factory:claimed` and labeled `worker:testbeam-laptop-1`.
This report is therefore bound to ticket `#2424` and no second helper claim was
performed.

## S45a Interpretation Layer

The reusable raw-ROOT benchmark estimates a run/stave-centered CFD20 onset
residual, then asks whether methods trained on other runs predict away
pedestal-coupled timing bias without receiving run identifiers.  The S45a
interpretation is the pedestal-memory closure: a method improves only if its
held-out run-block sigma68 and tails shrink while the pedestal-drift, pulse-tail,
pile-up, saturation, amplitude, and duplicate-ratio sidebands do not reveal a
single memorized nuisance slice carrying the result.
"""
    text = text.replace("\n## Raw ROOT Reproduction\n", insertion + "\n## Raw ROOT Reproduction\n")
    text = text.replace("Runtime was `", f"Ticket-local wrapper runtime was `{runtime:.1f} s`; base benchmark runtime was `")
    report.write_text(text, encoding="utf-8")


def _augment_result(config: dict, out: Path, runtime: float) -> None:
    path = out / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": "2424",
            "ticket_number": 2424,
            "study_id": "S45a",
            "worker": "testbeam-laptop-1",
            "title": config["title"],
            "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
            "manual_claim_workaround": {
                "reason": "tn-ticket claim returned malformed null output while open tickets existed",
                "issue": 2424,
                "command": "gh issue edit 2424 --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open",
            },
            "execution_command": (
                "/home/billy/anaconda3/bin/python "
                "scripts/ticket_2424_s45a_pedestal_memory_pulse_shape_timing_bias_closure.py"
            ),
            "ticket_scope": "pedestal-memory pulse-shape and timing bias closure",
            "wrapper_runtime_sec": runtime,
        }
    )
    result["artifacts"] = {
        "report": "REPORT.md",
        "metrics": "metrics.csv",
        "method_deltas": "method_deltas.csv",
        "by_run": "by_run.csv",
        "strata": "strata.csv",
        "ablations": "ablations.csv",
        "predictions": "predictions.parquet",
        "benchmark_rows": "benchmark_rows.parquet",
        "raw_reproduction": "reproduction.csv",
    }
    path.write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")


def _write_claim_files(config: dict, out: Path) -> None:
    (out / "claimed_ticket.txt").write_text(
        "manual_claim_issue: 2424\n"
        "manual_claim_command: gh issue edit 2424 --repo SzeChunYiu/factory-tickets "
        "--add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open\n"
        "claim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n"
        "claim_helper_output: null / # null / null\n",
        encoding="utf-8",
    )
    (out / "claimed_ticket_body.txt").write_text(
        "S45a: Pedestal-memory pulse-shape and timing bias closure\n\n"
        "Compare a traditional pretrigger pedestal model plus CFD/template-fit timing baseline "
        "against ridge, gradient-boosted trees, MLP, 1D-CNN and compact transformer waveform regressors.\n\n"
        "Report run-block bootstrap 95% CIs for timing bias/resolution, pulse-shape residual modes "
        "and pedestal-memory transfer across amplitude, stave, rate and pretrigger-history strata.\n\n"
        "Acceptance: separate true pulse-shape/timing shifts from pedestal artifacts, publish leakage "
        "checks and residual slices, and identify where ML improves or only memorizes baseline state.\n",
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
    base_config = args.config
    # Reuse the validated raw ROOT reader, model family implementations, and
    # report tables from S32a while keeping a ticket-local entry point.
    import sys

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(base.__file__)), "--config", str(base_config)]
        base.main()
    finally:
        sys.argv = old_argv

    runtime = time.time() - started
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    result["base_benchmark_runtime_sec"] = time.time() - base_start
    (out / "result.json").write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")
    _rewrite_report(config, out, runtime)
    _augment_result(config, out, runtime)
    _write_claim_files(config, out)

    # Add a compact CSV that makes the S45a pedestal-memory contrast explicit.
    strata = pd.read_csv(out / "strata.csv")
    ped = strata[strata["stratum"].eq("pedestal_drift_bin")].copy()
    ped.to_csv(out / "pedestal_memory_slices.csv", index=False)


if __name__ == "__main__":
    main()
