#!/usr/bin/env python3
"""Fail closed when the global scientific-audit front door is incomplete.

This gate does not certify physics results. It enforces the minimum repository
machinery required while #1594 is open so public documentation cannot silently
present historical outputs as already-authorized detector measurements.
"""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "audit status": ROOT / "docs/SCIENTIFIC_AUDIT_STATUS.md",
    "number ledger": ROOT / "chatgpt_todo/NUMBER_AUDIT_LEDGER.csv",
    "physics ledger": ROOT / "chatgpt_todo/PHYSICS_JUSTIFICATION_LEDGER.csv",
    "figure ledger": ROOT / "chatgpt_todo/FIGURE_AUDIT_LEDGER.csv",
    "redo queue": ROOT / "chatgpt_todo/REDO_QUEUE.csv",
    "review protocol": ROOT / "chatgpt_todo/SCIENTIFIC_REVIEW_PROTOCOL.md",
    "pickup guide": ROOT / "chatgpt_todo/AI_SESSION_PICKUP_GUIDE_20260817_GLOBAL_AUDIT.md",
}

REQUIRED_LEDGER_COLUMNS = {
    "PHYSICS_JUSTIFICATION_LEDGER.csv": {
        "item_id",
        "item_type",
        "status",
        "source_location",
        "physics_quantity",
        "units",
        "justification_class",
        "assumptions_domain",
        "dependencies",
        "detector_review",
        "statistics_review",
        "simulation_review",
        "provenance_review",
    },
    "FIGURE_AUDIT_LEDGER.csv": {
        "figure_id",
        "source_location",
        "status",
        "evidence_class",
        "claim_ids",
        "source_artifacts",
        "generator",
        "units_present",
        "denominator_present",
        "uncertainty_present",
        "provenance_complete",
    },
    "REDO_QUEUE.csv": {
        "redo_id",
        "priority",
        "domain",
        "status",
        "blocked_by",
        "source_issue",
        "reason",
        "acceptance_evidence",
    },
}

FORBIDDEN_FRONT_DOOR_PHRASES = {
    "WIKI.md": [
        "Every claim is traceable to source.",
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


def main() -> int:
    errors: list[str] = []

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
                errors.append(
                    f"{rel} contains unverified front-door overclaim {phrase!r}; "
                    "replace it with an audit-in-progress statement"
                )

    if errors:
        print("GLOBAL_SCIENTIFIC_AUDIT_GATE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("GLOBAL_SCIENTIFIC_AUDIT_GATE: PASS")
    print("This validates audit governance only; it does not certify any physics result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
