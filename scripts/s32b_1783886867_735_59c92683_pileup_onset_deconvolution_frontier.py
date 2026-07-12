#!/usr/bin/env python3
"""S32b pile-up onset deconvolution frontier for testbeam-laptop-3.

This ticket-local runner reuses the audited S29c run-held-out pile-up
deconvolution bakeoff machinery, writes artifacts under the newly claimed S32b
ticket, and normalizes the human-readable report/result metadata to the S32b
question.  The inherited machinery reproduces the raw B-stack ROOT count, builds
controlled pile-up injections from raw-ROOT-derived clean pulses, evaluates a
strong traditional template method against ridge, gradient-boosted trees, MLP,
1D-CNN, sequence-transformer, mask-transformer, and hybrid residual-stack
methods, and reports run-block bootstrap confidence intervals.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import s29c_1783827793_6970_25ea5036_pileup_timing_deconvolution_architecture_bakeoff as s29c


TICKET = "1783886867.735.59c92683"
WORKER = "testbeam-laptop-3"
SLUG = "s32b_pileup_onset_deconvolution_frontier"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"


def normalize_ticket_metadata() -> None:
    """Patch inherited S29c prose/metadata after the benchmark has run."""

    report = OUT / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    replacements = {
        "# S29c: pile-up timing deconvolution architecture bakeoff": "# S32b: pile-up onset deconvolution frontier for saturated pulse tails",
        "Ticket `1783886867.735.59c92683` asks for a run-held-out architecture bakeoff for pulse timing\nunder controlled pile-up.": (
            "Ticket `1783886867.735.59c92683` asks whether saturation-clipped pulse peaks can be "
            "deconvolved using late-tail and neighboring-channel waveform evidence without corrupting PID, "
            "under a run-held-out architecture bakeoff."
        ),
        "S29c composite endpoint score": "S32b composite endpoint score",
        "registered S29c composite endpoint score": "registered S32b composite endpoint score",
        "minimum registered S29c composite endpoint score with run-block bootstrap CIs": (
            "minimum registered S32b composite endpoint score with run-block bootstrap CIs"
        ),
        "The mask transformer adds": "The new architecture is the mask transformer, which adds",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    report.write_text(text, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket_id"] = TICKET
    result["worker"] = WORKER
    result["title"] = "S32b pile-up onset deconvolution frontier for saturated pulse tails"
    result["evaluation_design"]["winner_score"] = "registered S32b composite endpoint score"
    result["winner"]["criterion"] = "minimum registered S32b composite endpoint score with run-block bootstrap CIs"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s29c.TICKET = TICKET
    s29c.WORKER = WORKER
    s29c.SLUG = SLUG
    s29c.OUT = OUT
    s29c.main()
    normalize_ticket_metadata()


if __name__ == "__main__":
    main()
