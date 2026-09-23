#!/usr/bin/env python3
"""Validate the repository-wide scientific-audit governance contract.

Default mode is suitable for CI while #1594 is active: it verifies that the
required ledgers/protocols exist and that their schemas match the committed
files. ``--strict-front-door`` additionally fails on known public-documentation
overclaims/stale statements that are still being repaired under #1598.

Passing this gate never certifies a physics result.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "audit status": ROOT / "docs/SCIENTIFIC_AUDIT_STATUS.md",
    "physics reference baseline": ROOT / "docs/PHYSICS_REFERENCE_BASELINE.md",
    "physics derivation baseline": ROOT / "docs/PHYSICS_DERIVATIONS_BASELINE.md",
    "ML validation standard": ROOT / "docs/ML_VALIDATION_STANDARD.md",
    "scientific figure standard": ROOT / "docs/SCIENTIFIC_FIGURE_STANDARD.md",
    "number ledger": ROOT / "chatgpt_todo/NUMBER_AUDIT_LEDGER.csv",
    "physics ledger": ROOT / "chatgpt_todo/PHYSICS_JUSTIFICATION_LEDGER.csv",
    "figure ledger": ROOT / "chatgpt_todo/FIGURE_AUDIT_LEDGER.csv",
    "ML validation ledger": ROOT / "chatgpt_todo/ML_VALIDATION_LEDGER.csv",
    "redo queue": ROOT / "chatgpt_todo/REDO_QUEUE.csv",
    "review protocol": ROOT / "chatgpt_todo/SCIENTIFIC_REVIEW_PROTOCOL.md",
    "pickup guide": ROOT / "chatgpt_todo/AI_SESSION_PICKUP_GUIDE_20260817_GLOBAL_AUDIT.md",
    "external handoff": ROOT / "chatgpt_todo/REMAINING_USER_ACTIONS_20260817.md",
}

REQUIRED_LEDGER_COLUMNS = {
    "NUMBER_AUDIT_LEDGER.csv": {
        "audit_id", "quantity", "value_as_printed", "units", "evidence_class",
        "source", "selection_denominator", "uncertainty", "systematics",
        "reproduction", "cross_check", "trust_state", "reason",
    },
    "PHYSICS_JUSTIFICATION_LEDGER.csv": {
        "item_id", "item_type", "location", "claim_or_equation", "physical_quantity",
        "units", "justification_class", "primary_reference_or_derivation",
        "assumptions", "validity_domain", "detector_review", "statistics_review",
        "simulation_review", "provenance_review", "status", "redo_dependency",
    },
    "FIGURE_AUDIT_LEDGER.csv": {
        "figure_id", "location", "claim_ids", "evidence_class", "source_artifact",
        "source_hash", "generator_script", "n_or_denominator", "uncertainty_model",
        "data_mc_label", "provenance_complete", "scientific_context_complete",
        "status", "redo_dependency",
    },
    "ML_VALIDATION_LEDGER.csv": {
        "ml_id", "study_or_claim", "domain", "model_or_winner", "target_definition",
        "label_independence", "leakage_controls", "split_unit", "split_independence",
        "multiplicity_policy", "untouched_validation", "strong_baseline",
        "uncertainty_dependence", "transfer_slice_review", "provenance", "status",
        "blocked_by", "notes",
    },
    "REDO_QUEUE.csv": {
        "priority", "redo_id", "domain", "study_or_claim", "reason", "status",
        "blocked_by", "earliest_valid_input", "required_outputs", "issue",
    },
}

# These are known stale/over-authorizing statements, not generic keyword bans.
# They stay warnings in the default gate while #1598 repairs the WIKI, and become
# blocking under --strict-front-door.
FORBIDDEN_FRONT_DOOR_PHRASES = {
    "WIKI.md": [
        "Every claim is traceable to source.",
        "The raw beam ROOT (`hrdb_run_*.root`, runs 12–65) is now staged on LUNARC at `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/` and analysed directly.",
        "Waveform | 8 channels; located raw product 8×16 samples at 10 ns nominal | `MEASURED` / lineage gated",
    ],
}

README_REQUIRED = [
    "Repository-wide scientific revalidation is in progress",
    "docs/SCIENTIFIC_AUDIT_STATUS.md",
    "MC_METHOD_CLOSURE",
]


def _read_csv_header(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        try:
            return {cell.strip() for cell in next(reader)}
        except StopIteration as exc:
            raise ValueError(f"empty CSV: {path}") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict-front-door",
        action="store_true",
        help="also fail on known WIKI/front-door scientific overclaims/stale statements",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    errors: list[str] = []
    warnings: list[str] = []

    for label, path in REQUIRED_FILES.items():
        if not path.is_file():
            errors.append(f"missing required {label}: {path.relative_to(ROOT)}")

    for filename, expected in REQUIRED_LEDGER_COLUMNS.items():
        path = ROOT / "chatgpt_todo" / filename
        if not path.is_file():
            continue
        try:
            header = _read_csv_header(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        missing = sorted(expected - header)
        if missing:
            errors.append(f"{filename} missing required columns: {missing}")

    readme = ROOT / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        for marker in README_REQUIRED:
            if marker not in text:
                errors.append(f"README.md missing global-audit marker: {marker!r}")

    for rel, phrases in FORBIDDEN_FRONT_DOOR_PHRASES.items():
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase in text:
                message = (
                    f"{rel} contains known stale/over-authorizing statement {phrase!r}; "
                    "repair under #1598"
                )
                if args.strict_front_door:
                    errors.append(message)
                else:
                    warnings.append(message)

    if warnings:
        print("GLOBAL_SCIENTIFIC_AUDIT_GATE: WARNINGS")
        for warning in warnings:
            print(f"- {warning}")

    if errors:
        print("GLOBAL_SCIENTIFIC_AUDIT_GATE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("GLOBAL_SCIENTIFIC_AUDIT_GATE: PASS")
    if not args.strict_front_door:
        print("Known front-door defects are warnings until #1598 repairs them; strict mode fails them.")
    print("This validates audit governance only; it does not certify any physics result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
