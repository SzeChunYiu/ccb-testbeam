#!/usr/bin/env python3
"""Ticket 2542 / S65a pedestal-synchronized pulse-shape timing benchmark."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

import s43b_1784349946_602_171c4316_waveform_derivative_pulse_shape_timing_benchmark as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2542_s65a_pedestal_synchronized_timing_pileup_gain_sag.json"


def _write_ticket_local_tables(out: Path) -> None:
    strata = pd.read_csv(out / "strata.csv")
    timing_bias = strata[
        strata["stratum"].isin(
            [
                "pedestal_drift_bin",
                "pileup_separation_bin",
                "saturation_onset_bin",
                "energy_bin",
                "pid_sideband",
            ]
        )
    ].copy()
    timing_bias.to_csv(out / "pedestal_pileup_gain_sag_timing_bias.csv", index=False)

    axes = pd.read_csv(out / "frontier_axis_summary.csv")
    axes[
        axes["axis"].isin(
            [
                "pedestal_drift_bin",
                "pileup_separation_bin",
                "saturation_onset_bin",
                "energy_bin",
                "pid_sideband",
                "late_tail_morphology",
            ]
        )
    ].to_csv(out / "systematic_axis_summary.csv", index=False)

    ablations = pd.read_csv(out / "ablations.csv")
    ablations[
        ablations["ablation"].isin(
            [
                "full_derivative_gradient_boosted_trees",
                "drop_derivative_features",
                "onset_derivative_window_only",
                "late_tail_curvature_window_only",
                "pretrigger_derivative_only",
                "amplitude_cfd_no_derivative",
            ]
        )
    ].to_csv(out / "pulse_region_gain_sag_ablations.csv", index=False)


def _rewrite_report(config: dict, out: Path, runtime: float) -> None:
    report = out / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S43b Waveform Derivative Pulse-Shape Timing Benchmark",
        "# S65a Pedestal-Synchronized Pulse-Shape Timing Under Pile-Up and Gain Sag",
    )
    text = text.replace(
        "Ticket `2542` asks whether waveform derivative and curvature\n"
        "information improves arrival-time extraction under pedestal drift.",
        "Ticket `#2542` asks whether a strong CFD/template timing baseline or\n"
        "waveform ML better preserves leading-edge timing when pedestal memory,\n"
        "late pile-up, saturation onset, and gain-sag proxies move between\n"
        "run-held-out acquisition periods.",
    )
    text = text.replace(
        "Ticket `2542` asks whether waveform derivative and curvature information improves arrival-time extraction under pedestal drift.",
        "Ticket `#2542` asks whether a strong CFD/template timing baseline or waveform ML better preserves leading-edge timing when pedestal memory, late pile-up, saturation onset, and gain-sag proxies move between run-held-out acquisition periods.",
    )
    text = text.replace(
        "This benchmark measures relative transfer on a reproducible waveform-derived\n"
        "timing residual.",
        "This S65a benchmark measures relative transfer on a reproducible waveform-derived\n"
        "timing residual.  It treats pretrigger baseline displacement as the\n"
        "pedestal-memory proxy, late-tail morphology and post-peak structure as the\n"
        "pile-up spacing proxy, and high-amplitude/saturation-onset strata as the\n"
        "gain-sag stress proxy.",
    )
    text = text.replace(
        "The requested strata are amplitude, pedestal state, and late-tail morphology.",
        "The requested strata are amplitude, energy/PID sideband, pedestal state,\n"
        "pile-up spacing proxy, and saturation/gain-sag proxy.",
    )
    text = text.replace(
        "The new architecture is sensible for this ticket because the hypothesis is not\n"
        "generic waveform learning; it is that edge and curvature channels localize\n"
        "pulse-shape timing changes under pedestal drift.",
        "The new architecture is sensible for this ticket because the hypothesis is not\n"
        "generic waveform learning; it is that edge and curvature channels localize\n"
        "leading-edge motion and late-tail deformation under pedestal drift,\n"
        "pile-up, and gain-sag stress.",
    )
    insertion = f"""

## Ticket Claim Provenance

The required `tn-ticket claim {config['worker']} --project testbeam` command was
run exactly once.  It returned the malformed null payload

```text
{config['claim_command_output'].rstrip()}
```

without labeling a ticket for this worker.  Direct GitHub inspection showed
open `project:testbeam` tickets and no `worker:{config['worker']}` issue.  To
bind exactly one ticket without running the helper a second time, issue
`#{config['ticket_number']}` was manually label-swapped using:

```text
{config['manual_claim_workaround']['command']}
```

No other testbeam ticket was claimed in this worker.
"""
    text = text.replace("\n## Raw ROOT Reproduction\n", insertion + "\n## Raw ROOT Reproduction\n")
    text = text.replace(
        "Runtime was `",
        f"Ticket-local wrapper runtime was `{runtime:.1f} s`; benchmark runtime was `",
    )
    extra = """

## Ticket-Specific Diagnostic Files

`pedestal_pileup_gain_sag_timing_bias.csv` extracts the held-out timing-bias
tables for pedestal drift, pile-up spacing, saturation onset, energy, and
PID-sideband strata.  `systematic_axis_summary.csv` compresses the same axes to
best/worst strata by method.  `pulse_region_gain_sag_ablations.csv` isolates
whether onset derivatives, pretrigger derivatives, late-tail curvature, or
amplitude/CFD features carry the gain-sag and pile-up sensitivity.
"""
    text = text.replace("\n## Interpretation, Systematics, and Caveats\n", extra + "\n## Interpretation, Systematics, and Caveats\n")
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
            "done_command": f"tn-ticket done {config['ticket_id']}",
            "ticket_scope": "pedestal-synchronized pulse-shape timing under pile-up and gain-sag proxies",
            "traditional_method": "CFD/template cross-correlation time-walk baseline with derivative, curvature, and pedestal-memory correction",
            "wrapper_script_sha256": base.sha256_path(Path(__file__)),
            "wrapper_runtime_sec": runtime,
            "novel_tickets_appended": [],
            "next_tickets": [],
        }
    )
    result["required_method_coverage"] = {
        "traditional": "traditional_cfd_template_derivative",
        "ridge": "ridge",
        "gradient_boosted_trees": "gradient_boosted_trees",
        "mlp": "mlp",
        "one_dimensional_cnn": "1d_cnn",
        "compact_transformer": "compact_waveform_transformer",
        "new_architecture": "derivative_gate_transformer_new",
    }
    result["ticket_specific_artifacts"] = {
        "pedestal_pileup_gain_sag_timing_bias": "pedestal_pileup_gain_sag_timing_bias.csv",
        "systematic_axis_summary": "systematic_axis_summary.csv",
        "pulse_region_gain_sag_ablations": "pulse_region_gain_sag_ablations.csv",
    }
    path.write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")


def _write_claim_files(config: dict, out: Path) -> None:
    (out / "claimed_ticket.txt").write_text(
        config["claimed_ticket_text"]
        + f"\nclaim_helper_command: tn-ticket claim {config['worker']} --project testbeam\n"
        + "claim_helper_output:\n"
        + config["claim_command_output"]
        + "\nmanual_claim_workaround:\n"
        + config["manual_claim_workaround"]["command"]
        + "\n",
        encoding="utf-8",
    )
    (out / "claimed_ticket_body.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")


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
    manifest["done_command"] = f"tn-ticket done {config['ticket_id']}"
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
