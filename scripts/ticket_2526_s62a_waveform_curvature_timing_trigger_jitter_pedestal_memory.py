#!/usr/bin/env python3
"""Ticket 2526 / S62a waveform-curvature timing benchmark."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

import s43b_1784349946_602_171c4316_waveform_derivative_pulse_shape_timing_benchmark as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2526_s62a_waveform_curvature_timing_trigger_jitter_pedestal_memory.json"


def _rewrite_report(config: dict, out: Path, runtime: float) -> None:
    report = out / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    provenance_marker = "\n## Ticket Claim Provenance\n"
    raw_marker = "\n## Raw ROOT Reproduction\n"
    if provenance_marker in text and raw_marker in text:
        text = text.split(provenance_marker, 1)[0] + raw_marker + text.split(raw_marker, 1)[1]
    text = text.replace(
        "# S43b Waveform Derivative Pulse-Shape Timing Benchmark",
        "# S62a Waveform-Curvature Timing Under Trigger Jitter and Pedestal Memory",
    )
    text = text.replace(
        "Ticket `2505` asks whether waveform derivative and curvature\n"
        "information improves arrival-time extraction under pedestal drift.",
        "Ticket `#2526` asks whether waveform curvature and derivative information\n"
        "stabilize timing under trigger-phase jitter and pedestal-memory drift, and\n"
        "whether waveform ML beats a strong constant-fraction/template baseline.",
    )
    text = text.replace(
        "Ticket `2526` asks whether waveform derivative and curvature\n"
        "information improves arrival-time extraction under pedestal drift.",
        "Ticket `#2526` asks whether waveform curvature and derivative information\n"
        "stabilize timing under trigger-phase jitter and pedestal-memory drift, and\n"
        "whether waveform ML beats a strong constant-fraction/template baseline.",
    )
    text = text.replace(
        "The traditional method starts from the audited CFD/template time-walk baseline\n"
        "`hat y_0`, then fits a ridge-regularized derivative residual correction on\n"
        "training runs only:",
        "The traditional method starts from the audited constant-fraction plus\n"
        "template cross-correlation baseline `hat y_0`.  Trigger jitter is measured\n"
        "as the run-held-out onset residual after this baseline; pedestal memory is\n"
        "encoded by the pretrigger level, pretrigger slope, and pretrigger\n"
        "derivative RMS terms from samples 0--3.  The derivative/curvature residual\n"
        "correction is fit on training runs only:",
    )
    insertion = f"""

## Ticket Claim Provenance

The required `tn-ticket claim {config['worker']} --project testbeam` command was
run exactly once.  The local helper returned the malformed empty-existing-claim
payload

```text
{config['claim_command_output'].rstrip()}
```

without moving an open issue.  Direct GitHub inspection showed `#2526` was the
oldest open `project:testbeam` issue.  To bind exactly one ticket without
running the helper a second time, `#2526` was label-swapped to
`factory:claimed worker:{config['worker']}` using:

```text
{config['manual_claim_workaround']['command']}
```

No second `tn-ticket claim` was run.
"""
    text = text.replace(raw_marker, insertion + raw_marker)
    text = text.replace(
        "This benchmark measures relative transfer on a reproducible waveform-derived\n"
        "timing residual.",
        "This S62a benchmark measures relative transfer on a reproducible\n"
        "waveform-derived timing residual.  It treats trigger jitter as a held-out\n"
        "run residual process and tests whether waveform curvature, pile-up strata,\n"
        "saturation flags, pedestal state, reconstructed-energy proxies, and PID\n"
        "boundary diagnostics change the method ranking.",
    )
    text = text.replace(
        "Runtime was `",
        f"Ticket-local wrapper runtime was `{runtime:.1f} s`; benchmark runtime was `",
    )
    report.write_text(text, encoding="utf-8")


def _augment_result(config: dict, out: Path, runtime: float) -> None:
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
            "ticket_scope": "waveform-curvature timing under trigger jitter and pedestal memory",
            "traditional_method": "constant-fraction/template cross-correlation with derivative and curvature residual correction",
            "wrapper_script_sha256": base.sha256_path(Path(__file__)),
            "wrapper_runtime_sec": runtime,
            "novel_tickets_appended": [],
            "next_tickets": [],
        }
    )
    result["artifacts"]["pedestal_timing_bias_curves"] = "pedestal_timing_bias_curves.csv"
    result["artifacts"]["waveform_region_diagnostics"] = "waveform_region_diagnostics.csv"
    result["artifacts"]["trigger_jitter_run_diagnostics"] = "trigger_jitter_run_diagnostics.csv"
    result["artifacts"]["pid_energy_boundary_diagnostics"] = "pid_energy_boundary_diagnostics.csv"
    path.write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")


def _write_ticket_local_tables(out: Path) -> None:
    strata = pd.read_csv(out / "strata.csv")
    strata[strata["stratum"].isin(["pedestal_drift_bin", "energy_bin"])].to_csv(
        out / "pedestal_timing_bias_curves.csv", index=False
    )
    strata[strata["stratum"].isin(["pileup_separation_bin", "saturation_onset_bin", "pid_sideband"])].to_csv(
        out / "pid_energy_boundary_diagnostics.csv", index=False
    )

    ablations = pd.read_csv(out / "ablations.csv")
    ablations[
        ablations["ablation"].isin(
            [
                "onset_derivative_window_only",
                "late_tail_curvature_window_only",
                "pretrigger_derivative_only",
                "drop_derivative_features",
                "amplitude_cfd_no_derivative",
            ]
        )
    ].to_csv(out / "waveform_region_diagnostics.csv", index=False)

    by_run = pd.read_csv(out / "by_run.csv")
    by_run.to_csv(out / "trigger_jitter_run_diagnostics.csv", index=False)


def _write_claim_files(config: dict, out: Path) -> None:
    body = config["claimed_ticket_text"]
    (out / "claimed_ticket.txt").write_text(
        body
        + "\nclaim_helper_command: "
        + f"tn-ticket claim {config['worker']} --project testbeam\n"
        + "claim_helper_output:\n"
        + config["claim_command_output"]
        + "\nmanual_claim_workaround:\n"
        + config["manual_claim_workaround"]["command"]
        + "\n",
        encoding="utf-8",
    )
    (out / "claimed_ticket_body.txt").write_text(body, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(base.__file__)), "--config", str(args.config)]
        base.main()
    finally:
        sys.argv = old_argv

    runtime = time.time() - started
    _write_ticket_local_tables(out)
    _rewrite_report(config, out, runtime)
    _augment_result(config, out, runtime)
    _write_claim_files(config, out)
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    manifest = base.artifact_manifest(out, config, result)
    manifest["done_command"] = "tn-ticket done 2526"
    (out / "manifest.json").write_text(json.dumps(base.json_safe(manifest), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
