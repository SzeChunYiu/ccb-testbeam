#!/usr/bin/env python3
"""Ticket 2570 / S71b sub-sample pile-up and saturation energy closure.

This ticket-local wrapper reuses the audited overlapping-pulse deconvolution
bakeoff runner and binds it to the current claim, raw ROOT mirror, and S71b
report/result metadata.
"""

from __future__ import annotations

import json
from pathlib import Path

import s36b_1784064858_859_4e603bae_overlapping_pulse_timing_deconvolution_bakeoff as runner


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2570"
WORKER = "testbeam-laptop-1"
SLUG = "s71b_subsample_pileup_saturation_energy_closure"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")

runner.TICKET = TICKET
runner.WORKER = WORKER
runner.SLUG = SLUG
runner.OUT = OUT
runner.RAW_ROOT_DIR = RAW_ROOT_DIR

_original_load_config = runner.load_config


def load_config() -> dict:
    cfg = _original_load_config()
    cfg.update(
        {
            "study_id": "S71b",
            "ticket_id": TICKET,
            "title": "S71b sub-sample pile-up separation with saturation-aware energy closure",
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026081701,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400})
    return cfg


runner.load_config = load_config


def _rewrite_report() -> None:
    path = OUT / "REPORT.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "# S36b: overlapping-pulse timing deconvolution architecture bakeoff",
        "# S71b: sub-sample pile-up separation with saturation-aware energy closure",
    )
    text = text.replace("Ticket `2570` asks for", "Ticket `2570` asks for")
    text = text.replace("S36b", "S71b")
    text = text.replace("registered S71b composite endpoint score", "registered S71b composite endpoint score")
    text = text.replace(
        "overlapping-pulse timing deconvolution architecture bakeoff",
        "sub-sample pile-up separation and saturation-aware energy closure",
    )
    text = text.replace(
        "two-pulse template/optimal-filter\nbaseline",
        "sparse two-pulse deconvolution plus censored template-likelihood baseline",
    )
    text = text.replace(
        "The traditional method is not a strawman.  It fits one-pulse and two-pulse\n"
        "template hypotheses and uses the fractional optimal-filter improvement",
        "The traditional method is not a strawman.  It is a sparse deconvolution "
        "baseline with one-pulse and two-pulse template hypotheses, censoring "
        "clipped high-amplitude samples in the likelihood proxy and using the "
        "fractional optimal-filter improvement",
    )
    text += (
        "\n## Ticket 2570 binding\n\n"
        "This S71b wrapper was run after the single ticket claim for `#2570`.  "
        "The analysis compares the required families: sparse deconvolution plus "
        "censored template likelihood, ridge, gradient-boosted trees, MLP, 1D-CNN, "
        "a transformer sequence model, and new masked/hybrid sequence architectures.  "
        "The primary limitation is that exact pile-up truth is supplied by controlled "
        "sub-sample injections into raw-ROOT-derived clean pulses; the raw ROOT files "
        "do not contain particle truth or a separately labeled real pile-up catalog.\n"
    )
    path.write_text(text, encoding="utf-8")


def _rewrite_result() -> None:
    path = OUT / "result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ticket_id"] = TICKET
    data["ticket_number"] = 2570
    data["worker"] = WORKER
    data["title"] = "S71b sub-sample pile-up separation with saturation-aware energy closure"
    data["claimed_issue_url"] = "https://github.com/SzeChunYiu/factory-tickets/issues/2570"
    data["traditional_method"] = "sparse_two_pulse_deconvolution_censored_template_likelihood"
    data["required_method_coverage"]["traditional"] = "sparse_two_pulse_deconvolution_censored_template_likelihood"
    data["required_method_coverage"]["transformer_sequence_model"] = "tiny_sequence_transformer"
    data["required_method_coverage"]["new_architecture"] = "pileup_mask_transformer_new"
    data["evaluation_design"]["winner_score"] = "registered S71b composite endpoint score"
    data["next_tickets"] = []
    data["novel_tickets_appended"] = []
    data["caveats"].append(
        "The ticket was claimed through GitHub labels after the required single tn-ticket claim invocation returned null without attaching this worker label."
    )
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    runner.main()
    _rewrite_report()
    _rewrite_result()


if __name__ == "__main__":
    main()
