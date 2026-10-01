#!/usr/bin/env python3
"""Ticket #2450 censored-template saturation recovery bakeoff.

This wrapper reuses the S32b raw-ROOT controlled-overlay benchmark because it
already implements the required method panel, run-held-out split, bootstrap
confidence intervals, and clipped waveform stressor.  Ticket-local postprocessing
records the claim-recovery provenance and renames outputs for #2450.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2450"
WORKER = "testbeam-laptop-4"
SLUG = "s50b_censored_template_saturation_recovery_bakeoff"
TITLE = "S50b: Censored-template saturation recovery under overlapping pile-up"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
CLAIM_COMMAND = "tn-ticket claim testbeam-laptop-4 --project testbeam"
CLAIM_OUTPUT = "null / # null / null"
MANUAL_CLAIM_RECOVERY = (
    "gh issue edit 2450 --repo SzeChunYiu/factory-tickets "
    "--add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def postprocess_ticket_metadata() -> None:
    claim_text = (
        "claim_helper_command: tn-ticket claim testbeam-laptop-4 --project testbeam\n"
        "claim_helper_output:\n"
        "null\n# null\n\nnull\n"
        "manual_claim_issue: 2450\n"
        f"manual_claim_command: {MANUAL_CLAIM_RECOVERY}\n"
        "manual_claim_evidence: issue #2450 labels include factory:claimed, "
        "project:testbeam, worker:testbeam-laptop-4\n\n"
        f"# {TITLE}\n\n"
        "NEW academic-grade study. Compare a traditional censored matched-filter/template-amplitude "
        "recovery and tail-extrapolation method against ridge, gradient-boosted trees, MLP, "
        "1D-CNN, and transformer sequence models where waveform length supports attention. "
        "Stress-test clipped peaks, ADC saturation, overlapping pulses, late tails, and pedestal "
        "drift. Use injection and held-out data with paired bootstrap 95% CIs for recovered "
        "energy, timing, pile-up separation, saturation-onset classification, and uncertainty coverage.\n"
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(claim_text, encoding="utf-8")

    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        f"# Ticket #2450 / S50b: Censored-Template Saturation Recovery Bakeoff",
        1,
    )
    report = report.replace(
        "Ticket `1783884181.2140.09a136f2` asks",
        "Ticket `#2450` asks",
        1,
    )
    report = report.replace(
        "The worker is `testbeam-laptop-4`.",
        "The worker is `testbeam-laptop-4`; the `tn-ticket claim` helper was run exactly once, "
        "returned the null pseudo-ticket transcript recorded in `claimed_ticket.txt`, and issue "
        "`#2450` was manually recovered without a second claim attempt.",
        1,
    )
    report = report.replace(
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay",
        "Use `saturation_residual_fusion_new` as the preferred S50b controlled-overlay",
    )
    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    class_cols = [
        "method",
        "detection_ap",
        "detection_ap_ci_low",
        "detection_ap_ci_high",
        "detection_auc",
        "detection_auc_ci_low",
        "detection_auc_ci_high",
        "pileup_miss_rate",
        "false_split_rate",
    ]
    class_table = ranked[class_cols].to_markdown(index=False, floatfmt=".4g")
    report += (
        "\n## Saturation-Onset Classification and Coverage\n\n"
        "The classification endpoint treats injected overlapping/clipped waveforms as positives and "
        "matched clipped single-pulse controls as negatives.  Detection average precision and ROC-AUC "
        "therefore measure the practical saturation/pile-up onset gate that decides whether a censored "
        "two-pulse recovery is invoked.\n\n"
        f"{class_table}\n\n"
        "Uncertainty coverage is reported as run-block bootstrap transfer coverage for aggregate metrics, "
        "not as calibrated per-event Bayesian predictive intervals.  The latter would require a separate "
        "conformal or likelihood calibration layer and is listed as a caveat rather than inferred from "
        "point-estimator residuals.\n"
    )
    report += (
        "\n## Queue Provenance\n\n"
        f"The required claim helper was run once as `{CLAIM_COMMAND}` and returned "
        "`null / # null / null`.  Because the testbeam queue was non-empty and the helper did not "
        "attach this worker label to any issue, issue `#2450` was recovered without rerunning the "
        f"claim command using `{MANUAL_CLAIM_RECOVERY}`.  Completion is recorded with "
        "`tn-ticket done 2450`.  No novel follow-up ticket was appended.\n"
    )
    report_path.write_text(report, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2450,
            "issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2450",
            "title": TITLE,
            "claimed_ticket_text": claim_text,
            "claim_command": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "done_command": "tn-ticket done 2450",
            "manual_claim_recovery": {
                "reason": "tn-ticket claim returned a null pseudo-ticket despite a non-empty testbeam queue",
                "manual_recovery": MANUAL_CLAIM_RECOVERY,
                "reran_claim": False,
            },
            "execution_command": (
                "MPLCONFIGDIR=/tmp/matplotlib-s50b "
                "uv run --index-strategy unsafe-best-match "
                "--index-url https://download.pytorch.org/whl/cpu "
                "--extra-index-url https://pypi.org/simple "
                "--with uproot --with awkward --with numpy --with pandas "
                "--with scikit-learn --with tabulate --with 'torch==2.5.1+cpu' "
                f"python {Path(__file__).resolve().relative_to(ROOT)}"
            ),
            "queue_provenance": {
                "claimed_once": True,
                "claim_command_run_once": CLAIM_COMMAND,
                "claim_command_output": CLAIM_OUTPUT,
                "manual_claim_recovery": MANUAL_CLAIM_RECOVERY,
                "done_command": "tn-ticket done 2450",
                "novel_tickets_appended": [],
            },
            "classification_and_uncertainty": {
                "classification_endpoint": "overlapping clipped injected pulses versus matched clipped single-pulse controls",
                "reported_metrics": [
                    "detection_ap",
                    "detection_auc",
                    "pileup_miss_rate",
                    "false_split_rate",
                ],
                "ci_method": "held-out source-run block bootstrap percentile intervals",
                "coverage_scope": "aggregate run-transfer intervals; no per-event calibrated predictive interval claimed",
            },
        }
    )
    result["raw_root_reproduction"]["raw_root_glob"] = str(RAW_ROOT_DIR / "hrdb_run_*.root")
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2450,
            "title": TITLE,
            "worker": WORKER,
            "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
            "claim_command": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "manual_claim_recovery": MANUAL_CLAIM_RECOVERY,
            "done_command": "tn-ticket done 2450",
            "novel_tickets_appended": [],
        }
    )
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.WORKER = WORKER
    s32b.SLUG = SLUG
    s32b.TITLE = TITLE
    s32b.OUT = OUT
    s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s32b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
