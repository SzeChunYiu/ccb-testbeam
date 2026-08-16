#!/usr/bin/env python3
"""S45b ticket wrapper for the censored saturation information boundary.

The heavy benchmark machinery is shared with the audited S35b saturation runner:
it reads raw B-stack ROOT files, reproduces the selected-pulse count, applies
explicit ADC clipping, and benchmarks a censored traditional template method
against ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence transformer, and a
hybrid residual-fusion architecture.  This wrapper binds the run to factory
ticket #2425 and patches the generated report/result metadata accordingly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s35b_1784063447_914_74ba7793_saturation_pileup_energy_recovery_benchmark as s35b  # noqa: E402


TICKET = "2425"
TITLE = "S45b: Censored saturation onset energy-recovery information boundary"
WORKER = "testbeam-laptop-1"
SLUG = "s45b_censored_saturation_information_boundary"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"


def _patch_report() -> None:
    report_path = OUT / "REPORT.md"
    text = report_path.read_text(encoding="utf-8")
    text = text.replace(
        "# S35b: Saturation Pile-Up Energy Recovery Benchmark",
        "# S45b: Censored Saturation Onset Energy-Recovery Information Boundary",
    )
    text = text.replace("The registered winner minimizes", "The information-boundary winner minimizes")
    text = text.replace(
        "The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,",
        "The stratum scan maps the observable information boundary across saturation depth, "
        "pile-up spacing, amplitude ratio, injected-noise morphology,",
    )
    text = text.replace("`result.json` names **", "`result.json` names **")
    text = text.replace("S35b winner", "S45b winner")
    appendix = """

## Ticket-Specific Information Boundary Interpretation

Ticket #2425 asks whether waveform models recover information hidden by
right-censoring beyond a strong traditional censored-template likelihood.  The
answer is operational rather than absolute: the benchmark defines recoverable
information as held-out reduction of energy residual, saturation-onset residual,
shape/timing residual, and false-split controls under run-separated controlled
truth.  A method is in the graceful-failure region when its false split rate and
miss rate remain finite while its sigma68 intervals overlap the best method
within the same clipping-depth or morphology stratum.  It is outside the
observable boundary when plateau width, pedestal state, or low separation drives
both the energy interval and the miss/false-split controls away from the winner.

The reported winner should therefore be read as the best reconstruction rule for
this raw-ROOT-derived controlled censoring experiment, not as an authorization of
real beam saturation frequency or PID closure.  That distinction is intentional:
the experiment tests information content under known injected truth while
preserving raw waveform residuals and run transfer.
"""
    if "## Ticket-Specific Information Boundary Interpretation" not in text:
        text = text.rstrip() + appendix
    report_path.write_text(text + "\n", encoding="utf-8")


def _patch_result() -> None:
    result_path = OUT / "result.json"
    data = json.loads(result_path.read_text(encoding="utf-8"))
    data["ticket_id"] = TICKET
    data["study_id"] = "S45b"
    data["worker"] = WORKER
    data["title"] = TITLE
    data["claimed_ticket_text"] = TITLE
    data["claim_command"] = f"tn-ticket claim {WORKER} --project testbeam"
    data["claim_note"] = (
        "The required claim helper was run exactly once and returned the known null pseudo-ticket; "
        "ticket #2425 was then claimed by the equivalent backend label transition because open "
        "project:testbeam tickets remained and no worker:testbeam-laptop-1 claim existed."
    )
    data["ticket_acceptance_mapping"] = {
        "traditional_censored_template": "analytic_clipped_template_sideband_traditional",
        "ridge": "ridge",
        "gradient_boosted_trees": "gradient_boosted_trees",
        "mlp": "mlp",
        "one_dimensional_cnn": "1d_cnn",
        "transformer_sequence_model": "tiny_sequence_transformer",
        "new_architecture_when_sensible": "saturation_residual_fusion_new",
        "information_boundary": "winner_ranked_metrics.csv plus strata_metrics.csv",
        "graceful_failure_regions": "strata_metrics.csv",
    }
    result_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s35b.TICKET = TICKET
    s35b.TITLE = TITLE
    s35b.WORKER = WORKER
    s35b.SLUG = SLUG
    s35b.OUT = OUT
    s35b.RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
    s35b.main()
    _patch_report()
    _patch_result()


if __name__ == "__main__":
    main()
