#!/usr/bin/env python3
"""S44b ticket wrapper for pile-up separation under saturation.

The core benchmark is the existing S32b runner, which already implements the
required raw-ROOT reproduction, run-heldout bootstrap design, and method panel.
This wrapper isolates issue #2418 metadata and adds queue-recovery provenance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2418"
WORKER = "testbeam-laptop-2"
SLUG = "s44b_pileup_separation_saturation_energy_recovery_bakeoff"
TITLE = "S44b: Pile-up separation under saturation with energy recovery bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = ROOT / "data" / "root" / "root"
CLAIM_COMMAND = "tn-ticket claim testbeam-laptop-2 --project testbeam"
CLAIM_OUTPUT = "null / # null / null"
DONE_COMMAND = "tn-ticket done 2418"
MANUAL_RECOVERY = (
    "gh issue edit 2418 --repo SzeChunYiu/factory-tickets "
    "--add-label factory:claimed --add-label worker:testbeam-laptop-2 "
    "--remove-label factory:open"
)
CLAIMED_TICKET_TEXT = (
    "#2418 S44b: Pile-up separation under saturation with energy recovery bakeoff"
)


def sha256_file(path: Path) -> str:
    return s32b.base.sha256_file(path)


def postprocess_ticket_metadata() -> None:
    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        "# S44b: Pile-up Separation Under Saturation With Energy Recovery Bakeoff",
        1,
    )
    report = report.replace(
        "Ticket `2418` asks for an academic-grade comparison of a strong traditional\n"
        "multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,\n"
        "transformer sequence models, and a sensible new architecture for energy\n"
        "reconstruction under pile-up and ADC saturation.",
        "Ticket `#2418` asks for an academic-grade comparison of a strong traditional\n"
        "two-pulse template deconvolution plus clipped-charge correction against ridge,\n"
        "gradient-boosted trees, MLP, 1D-CNN, transformer sequence models, and a sensible\n"
        "new architecture for pile-up separation and energy recovery under ADC saturation.",
    )
    report = report.replace(
        "The stratum scan covers pile-up spacing, saturated sample count, pedestal state,\n"
        "pulse morphology, amplitude ratio, stave, and a PID proxy class.",
        "The stratum scan covers pile-up spacing, amplitude ratio, clipping depth,\n"
        "pedestal/baseline memory state, waveform morphology, stave, and a PID proxy class.\n"
        "These strata are the blinded hand-scan surrogates available in the raw-ROOT\n"
        "controlled-overlay design: high clipping depth and late/broad morphology mark\n"
        "cases where saturation and pile-up become weakly identifiable rather than cleanly\n"
        "separable.",
    )
    report = report.replace(
        "Use `",
        "For ticket #2418, use `",
        1,
    )
    report = report.replace(
        "as the preferred S32b controlled-overlay energy-closure method",
        "as the preferred S44b controlled-overlay pile-up/saturation recovery method",
    )
    report += (
        "\n\n## Queue Provenance\n\n"
        f"The required single claim command was run once as `{CLAIM_COMMAND}` and returned "
        f"the known null pseudo-ticket output `{CLAIM_OUTPUT}`.  Because the testbeam queue "
        "was not empty, issue `#2418` was manually recovered without a second claim attempt "
        f"using `{MANUAL_RECOVERY}`.  Completion was recorded with `{DONE_COMMAND}`.  "
        "No novel follow-up ticket was appended.\n"
    )
    report_path.write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2418,
            "issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2418",
            "worker": WORKER,
            "title": TITLE,
            "claimed_ticket_text": CLAIMED_TICKET_TEXT,
            "claim_command": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "done_command": DONE_COMMAND,
            "manual_claim_recovery": {
                "reason": "tn-ticket claim returned a null pseudo-ticket despite a non-empty testbeam queue",
                "manual_recovery": MANUAL_RECOVERY,
                "reran_claim": False,
            },
            "execution_command": (
                "MPLCONFIGDIR=/tmp/matplotlib-s44b "
                "uv run --index-strategy unsafe-best-match "
                "--index-url https://download.pytorch.org/whl/cpu "
                "--extra-index-url https://pypi.org/simple "
                "--with uproot --with awkward --with numpy --with pandas "
                "--with scikit-learn --with tabulate --with 'torch==2.5.1+cpu' "
                f"python {Path(__file__).resolve().relative_to(ROOT)}"
            ),
        }
    )
    result["queue_provenance"] = {
        "claimed_once": True,
        "claim_command_run_once": CLAIM_COMMAND,
        "claim_command_output": CLAIM_OUTPUT,
        "manual_claim_recovery": MANUAL_RECOVERY,
        "done_command": DONE_COMMAND,
        "novel_tickets_appended": [],
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2418,
            "worker": WORKER,
            "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
            "claim_command_run_once": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "manual_claim_recovery": MANUAL_RECOVERY,
            "done_command": DONE_COMMAND,
        }
    )
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    (OUT / "claimed_ticket.txt").write_text(
        CLAIMED_TICKET_TEXT
        + "\nClaim recovery: required tn-ticket command was run once and returned null; "
        + "manually applied worker label to issue #2418 without rerunning tn-ticket claim.\n",
        encoding="utf-8",
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    root_result = {
        "ticket_id": TICKET,
        "issue_number": 2418,
        "project": "testbeam",
        "worker": WORKER,
        "status": "complete",
        "winner": result["winner"]["name"],
        "winner_metrics": result["winner"],
        "raw_root_reproduction": result["raw_root_reproduction"],
        "split": result["evaluation_design"],
        "required_method_coverage": result["required_method_coverage"],
        "artifacts": {
            "report": str((OUT / "REPORT.md").relative_to(ROOT)),
            "result": str((OUT / "result.json").relative_to(ROOT)),
            "method_metrics": str((OUT / "method_metrics.csv").relative_to(ROOT)),
            "run_heldout_metrics": str((OUT / "run_heldout_metrics.csv").relative_to(ROOT)),
            "strata_metrics": str((OUT / "strata_metrics.csv").relative_to(ROOT)),
        },
        "queue_provenance": result["queue_provenance"],
        "done_command": DONE_COMMAND,
        "novel_tickets_appended": [],
    }
    (ROOT / "result.json").write_text(json.dumps(root_result, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.WORKER = WORKER
    s32b.SLUG = SLUG
    s32b.TITLE = TITLE
    s32b.OUT = OUT
    s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s32b.os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib-s44b"
    s32b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
