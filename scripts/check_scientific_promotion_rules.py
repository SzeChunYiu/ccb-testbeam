#!/usr/bin/env python3
"""Fail closed when an audit ledger promotes incomplete scientific evidence.

This validator deliberately permits incomplete REVIEW/GATED/BLOCKED rows. It
only becomes strict when a row claims SUPPORT/VALIDATION, preventing a status
label from outrunning the evidence fields.
"""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TODO = ROOT / "chatgpt_todo"

PROMOTED = {"SUPPORTED", "VALIDATED", "VALIDATED_TRANSFER", "COMPLETE"}
ACCEPT = {"ACCEPT", "PASS", "YES", "COMPLETE"}
PLACEHOLDERS = {"", "N/A", "NA", "NONE", "TBD", "PENDING", "UNKNOWN", "OPEN"}


def rows(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


def bad(value: str | None) -> bool:
    return (value or "").strip().upper() in PLACEHOLDERS


def check_physics(errors: list[str]) -> None:
    path = TODO / "PHYSICS_JUSTIFICATION_LEDGER.csv"
    for row in rows(path):
        status = (row.get("status") or "").strip().upper()
        if status not in PROMOTED:
            continue
        item = row.get("item_id", "<unknown>")
        required = [
            "location",
            "claim_or_equation",
            "physical_quantity",
            "units",
            "justification_class",
            "primary_reference_or_derivation",
            "assumptions",
            "validity_domain",
            "independent_falsifier",
        ]
        for field in required:
            if bad(row.get(field)):
                errors.append(f"{item}: promoted physics row missing {field}")
        for field in (
            "detector_review",
            "statistics_review",
            "simulation_review",
            "provenance_review",
        ):
            value = (row.get(field) or "").strip().upper()
            if value not in ACCEPT:
                errors.append(
                    f"{item}: promoted physics row requires accepting {field}; got {value!r}"
                )


def check_figures(errors: list[str]) -> None:
    path = TODO / "FIGURE_AUDIT_LEDGER.csv"
    for row in rows(path):
        status = (row.get("status") or "").strip().upper()
        if status not in PROMOTED:
            continue
        item = row.get("figure_id", "<unknown>")
        required = [
            "location",
            "claim_ids",
            "evidence_class",
            "source_artifact",
            "source_hash",
            "generator_script",
            "config_or_commit",
            "n_or_denominator",
            "selection",
            "uncertainty_model",
            "data_mc_label",
        ]
        for field in required:
            if bad(row.get(field)):
                errors.append(f"{item}: promoted figure missing {field}")
        if (row.get("provenance_complete") or "").strip().upper() not in {"YES", "TRUE", "COMPLETE"}:
            errors.append(f"{item}: promoted figure lacks complete provenance")
        if (row.get("scientific_context_complete") or "").strip().upper() not in {"YES", "TRUE", "COMPLETE"}:
            errors.append(f"{item}: promoted figure lacks complete scientific context")


def check_numbers(errors: list[str]) -> None:
    path = TODO / "NUMBER_AUDIT_LEDGER.csv"
    for row in rows(path):
        status = (row.get("trust_state") or "").strip().upper()
        if status not in PROMOTED:
            continue
        item = row.get("audit_id", "<unknown>")
        required = [
            "quantity",
            "value_as_printed",
            "units",
            "evidence_class",
            "source",
            "producer",
            "inputs",
            "selection_denominator",
            "estimator",
            "uncertainty",
            "systematics",
            "independence",
            "reproduction",
            "cross_check",
            "reason",
        ]
        for field in required:
            if bad(row.get(field)):
                errors.append(f"{item}: promoted numerical atom missing {field}")
        if (row.get("reproduction") or "").strip().upper() not in ACCEPT:
            errors.append(f"{item}: promoted numerical atom is not independently reproduced")
        if (row.get("cross_check") or "").strip().upper() not in ACCEPT:
            errors.append(f"{item}: promoted numerical atom lacks accepting cross-check")


def main() -> int:
    errors: list[str] = []
    check_physics(errors)
    check_figures(errors)
    check_numbers(errors)
    if errors:
        print("SCIENTIFIC_PROMOTION_RULES: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SCIENTIFIC_PROMOTION_RULES: PASS")
    print("No promoted audit row outruns its required evidence fields.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
