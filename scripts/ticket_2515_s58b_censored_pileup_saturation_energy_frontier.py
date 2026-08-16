#!/usr/bin/env python3
"""Ticket 2515 S58b censored pile-up saturation energy recovery frontier."""

from __future__ import annotations

import json
from pathlib import Path

import s35b_1784063447_914_74ba7793_saturation_pileup_energy_recovery_benchmark as impl


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2515"
WORKER = "testbeam-laptop-4"
TITLE = "NEW S58b censored pile-up saturation energy recovery frontier"
SLUG = "s58b_censored_pileup_saturation_energy_frontier"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def postprocess_ticket_language() -> None:
    report = OUT / "REPORT.md"
    result_path = OUT / "result.json"
    manifest_path = OUT / "manifest.json"

    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# S35b: Saturation Pile-Up Energy Recovery Benchmark",
        "# S58b: Censored Pile-Up Saturation Energy Recovery Frontier",
    )
    text = text.replace(
        "Ticket `2515` asks for a raw-ROOT reproduction followed by an academic-grade\n"
        "comparison of energy reconstruction under clipped saturation and unresolved\n"
        "pile-up.",
        "Ticket `2515` asks how much saturated, overlapping-pulse energy is\n"
        "recoverable once ADC clipping and pile-up timing are modeled explicitly,\n"
        "starting from raw ROOT reproduction and ending in a run-held-out recovery\n"
        "frontier.",
    )
    text = text.replace(
        "| analytic_clipped_template_sideband_traditional | traditional    | bounded two-template deconvolution with deterministic clipping sideband correction   |",
        "| analytic_clipped_template_sideband_traditional | traditional    | censored template deconvolution with response-curve saturation correction   |",
    )
    text = text.replace(
        "then applies a deterministic saturation sideband correction based on clipped\n"
        "sample count, plateau width, and late-tail fraction:",
        "then applies a response-curve saturation correction based on clipped sample\n"
        "count, plateau width, and late-tail fraction.  This is the strong\n"
        "traditional censored deconvolution frontier used for S58b:",
    )
    text = text.replace(
        "The new architecture is `saturation_residual_fusion_new`.  It is sensible here\n"
        "because the failure mode is hybrid: the analytic fit supplies identifiable\n"
        "constituents, while clipping sidebands and waveform summaries carry residual\n"
        "information about charge hidden above the ADC ceiling.",
        "The new architecture is `saturation_residual_fusion_new`.  It is sensible for\n"
        "S58b because the recoverable information is hybrid: the analytic fit supplies\n"
        "identifiable pulse constituents, while clipping depth, plateau width,\n"
        "pedestal state, and waveform residual summaries carry information about\n"
        "charge hidden above the ADC ceiling.",
    )
    text = text.replace(
        "## Stratified Systematics",
        "## Recovery Frontier and Stratified Systematics",
    )
    text = text.replace(
        "The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,\n"
        "pedestal state, morphology state, stave, and PID proxy class:",
        "The recovery frontier is reported as the stratum scan over clip depth,\n"
        "pile-up spacing, amplitude ratio, pedestal state, morphology state, stave,\n"
        "and PID proxy class:",
    )
    text = text.replace("as the S35b winner", "as the S58b winner")
    text = text.replace("S35b winner", "S58b winner")
    report.write_text(text, encoding="utf-8")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["claimed_ticket_text"] = TITLE
    result["winner"]["criterion"] = (
        "minimum registered S58b held-out energy-plus-pileup recovery-frontier "
        "score with run-block bootstrap CIs"
    )
    result["required_method_coverage"]["traditional"] = (
        "analytic_clipped_template_sideband_traditional "
        "(censored template deconvolution with response-curve saturation correction)"
    )
    result["required_outputs"] = {
        "raw_root_reproduction": "reproduction_match_table.csv",
        "method_benchmark": "method_metrics.csv, endpoint_metrics_ci.csv, winner_ranked_metrics.csv",
        "run_split_bootstrap": "run_heldout_metrics.csv with endpoint_metrics_ci.csv",
        "recovery_frontier": "strata_metrics.csv",
        "systematics_and_caveats": "REPORT.md",
    }
    result["queue_provenance"] = {
        "claimed_once": True,
        "claim_command_run_once": f"tn-ticket claim {WORKER} --project testbeam",
        "claim_command_output": "null / # null / null",
        "manual_claim_recovery": (
            "gh issue edit 2515 --repo SzeChunYiu/factory-tickets "
            "--add-label factory:claimed --add-label worker:testbeam-laptop-4 "
            "--remove-label factory:open"
        ),
        "done_command": "tn-ticket done 2515",
        "novel_tickets_appended": [],
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = f"{impl.sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["postprocess_note"] = (
        "S58b ticket metadata and censored pile-up saturation recovery-frontier "
        "wording applied after reused S35b benchmark engine."
    )
    manifest["outputs_sha256"] = {
        p.name: impl.base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    impl.TICKET = TICKET
    impl.WORKER = WORKER
    impl.TITLE = TITLE
    impl.SLUG = SLUG
    impl.OUT = OUT
    impl.RAW_ROOT_DIR = RAW_ROOT_DIR
    impl.base.RAW_ROOT_DIR = RAW_ROOT_DIR
    impl.s26b.RAW_ROOT_DIR = RAW_ROOT_DIR
    impl.s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    impl.main()
    postprocess_ticket_language()


if __name__ == "__main__":
    main()
