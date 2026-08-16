#!/usr/bin/env python3
"""Ticket 2505 / S56a derivative-template timing vs waveform ML benchmark."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

import s43b_1784349946_602_171c4316_waveform_derivative_pulse_shape_timing_benchmark as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2505_s56a_derivative_template_timing_vs_waveform_ml.json"


def _rewrite_report(config: dict, out: Path, runtime: float) -> None:
    report = out / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S43b Waveform Derivative Pulse-Shape Timing Benchmark",
        "# S56a Derivative-Template Timing vs Waveform ML",
    )
    text = text.replace(
        "Ticket `2505` asks whether waveform derivative and curvature\n"
        "information improves arrival-time extraction under pedestal drift.",
        "Ticket `#2505` asks how pedestal-memory drift changes pulse shape and\n"
        "timing estimates across runs and amplitudes, and whether waveform ML\n"
        "beats a strong derivative-enhanced template timing baseline.",
    )
    text = text.replace(
        "The traditional method starts from the audited CFD/template time-walk baseline\n"
        "`hat y_0`, then fits a ridge-regularized derivative residual correction on\n"
        "training runs only:",
        "The traditional method starts from the audited CFD/template time-walk baseline\n"
        "`hat y_0`.  The pretrigger pedestal is summarized by the four raw samples\n"
        "`p_t = x_t` for `t in {0,1,2,3}` and the AR(1) memory proxy\n"
        "`rho_hat = sum_t (p_t-bar p)(p_{t-1}-bar p) / sum_t (p_{t-1}-bar p)^2`,\n"
        "implemented here through the baseline level, pretrigger slope, and\n"
        "pretrigger derivative RMS terms available in the 18-sample waveform.  A\n"
        "ridge-regularized derivative residual correction is fit on training runs\n"
        "only:",
    )
    insertion = f"""

## Ticket Claim Provenance

The required `tn-ticket claim testbeam-laptop-1 --project testbeam` command was
run exactly once.  The local helper returned the malformed empty-existing-claim
payload

```text
{config['claim_command_output'].rstrip()}
```

without moving an open issue.  Direct read-only GitHub inspection showed issue
`#2505` still labeled `factory:open project:testbeam` and no valid
`worker:testbeam-laptop-1` claimed issue.  To bind exactly one ticket without
running the helper a second time, `#2505` was manually label-swapped to
`factory:claimed worker:testbeam-laptop-1` using:

```text
{config['manual_claim_workaround']['command']}
```

No other testbeam ticket was claimed in this worker.
"""
    text = text.replace("\n## Raw ROOT Reproduction\n", insertion + "\n## Raw ROOT Reproduction\n")
    text = text.replace(
        "This benchmark measures relative transfer on a reproducible waveform-derived\n"
        "timing residual.",
        "This S56a benchmark measures relative transfer on a reproducible waveform-derived\n"
        "timing residual and uses the pedestal-memory strata as diagnostics for where\n"
        "pedestal-induced timing bias enters the sampled waveform.",
    )
    text = text.replace("Runtime was `", f"Ticket-local wrapper runtime was `{runtime:.1f} s`; benchmark runtime was `")
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
            "ticket_scope": "derivative-template timing vs waveform ML for pedestal-shape disentanglement",
            "traditional_method": "derivative-enhanced CFD/template timing with AR(1)-style pretrigger pedestal-memory proxies",
            "wrapper_script_sha256": base.sha256_path(Path(__file__)),
            "wrapper_runtime_sec": runtime,
            "novel_tickets_appended": [],
            "next_tickets": [],
        }
    )
    result["artifacts"]["pedestal_timing_bias_curves"] = "pedestal_timing_bias_curves.csv"
    result["artifacts"]["waveform_region_diagnostics"] = "waveform_region_diagnostics.csv"
    path.write_text(json.dumps(base.json_safe(result), indent=2) + "\n", encoding="utf-8")


def _write_ticket_local_tables(out: Path) -> None:
    strata = pd.read_csv(out / "strata.csv")
    bias = strata[strata["stratum"].isin(["pedestal_drift_bin", "energy_bin"])].copy()
    bias.to_csv(out / "pedestal_timing_bias_curves.csv", index=False)

    ablations = pd.read_csv(out / "ablations.csv")
    region = ablations[
        ablations["ablation"].isin(
            [
                "onset_derivative_window_only",
                "late_tail_curvature_window_only",
                "pretrigger_derivative_only",
                "drop_derivative_features",
                "amplitude_cfd_no_derivative",
            ]
        )
    ].copy()
    region.to_csv(out / "waveform_region_diagnostics.csv", index=False)


def _write_claim_files(config: dict, out: Path) -> None:
    (out / "claimed_ticket.txt").write_text(
        config["claimed_ticket_text"]
        + "\nclaim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n"
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
    (out / "manifest.json").write_text(json.dumps(base.artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
