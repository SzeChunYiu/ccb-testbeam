#!/usr/bin/env python3
"""Validate the executive-summary claim surface against exact-width ledger rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

VERSION = "1.0.0"
EXPECTED_LEDGER_COLUMNS = 43


class ExecutiveSummaryAuditError(ValueError):
    """Controlled input, encoding, or schema error."""


class Binding(NamedTuple):
    label: str
    claim_id: str
    required_status: str
    required_value_tokens: tuple[str, ...] = ()
    required_truth_tokens: tuple[str, ...] = ()


BINDINGS = (
    Binding(
        "Rmax (pile-up tolerance)",
        "CL-010",
        "BLOCKED",
        required_value_tokens=("Withheld", "unresolved"),
        required_truth_tokens=("derived", "conflicted"),
    ),
    Binding(
        "τeff (effective live-time)",
        "CL-011",
        "VALIDATED",
        required_truth_tokens=("data", "MC", "self-consistent"),
    ),
    Binding("MV4 raw timing pull", "CL-007", "VALIDATED"),
    Binding(
        "ML duplicate-readout selection",
        "CL-015",
        "GATED",
        required_value_tokens=("No canonical winner", "coverage"),
        required_truth_tokens=("data", "external duplicate readout"),
    ),
    Binding(
        "ML saturation recovery",
        "CL-016",
        "GATED",
        required_value_tokens=("Withheld", "worse than raw"),
        required_truth_tokens=("data", "external duplicate readout"),
    ),
)

FORBIDDEN_STATEMENTS = (
    "ML wins (confirmed)",
    "Pile-up tolerance Rmax ≈ 3.05 MHz",
    "C12 nuclear recoil anomaly fraction is 0.32% of tracks (MC-identified).",
)


def _read_utf8_snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ExecutiveSummaryAuditError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExecutiveSummaryAuditError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _parse_ledger(text: str) -> dict[str, dict[str, str]]:
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        raise ExecutiveSummaryAuditError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_LEDGER_COLUMNS:
        raise ExecutiveSummaryAuditError(
            f"claim ledger header has {len(header)} columns; expected {EXPECTED_LEDGER_COLUMNS}"
        )
    required = {"claim_id", "status", "truth_type"}
    if not required.issubset(header):
        missing = sorted(required.difference(header))
        raise ExecutiveSummaryAuditError(f"claim ledger missing columns: {', '.join(missing)}")
    index = {name: position for position, name in enumerate(header)}
    parsed: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if not row:
            continue
        claim_id = row[0].strip() if row else ""
        if claim_id not in {binding.claim_id for binding in BINDINGS}:
            continue
        if len(row) != EXPECTED_LEDGER_COLUMNS:
            message = (
                f"required claim {claim_id} has {len(row)} columns; "
                f"expected {EXPECTED_LEDGER_COLUMNS}"
            )
            raise ExecutiveSummaryAuditError(message)
        if claim_id in parsed:
            raise ExecutiveSummaryAuditError(f"duplicate claim_id {claim_id}")
        parsed[claim_id] = {
            "status": row[index["status"]].strip(),
            "truth_type": row[index["truth_type"]].strip(),
            "row_number": str(row_number),
        }
    for binding in BINDINGS:
        if binding.claim_id not in parsed:
            raise ExecutiveSummaryAuditError(f"required claim {binding.claim_id} is absent")
    return parsed


def _markdown_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _extract_status(cell: str) -> str | None:
    match = re.search(r"\*\*([A-Z][A-Z0-9_]*)\*\*", cell)
    return match.group(1) if match else None


def _find_row(lines: list[str], label: str) -> list[str] | None:
    matches = []
    for line in lines:
        cells = _markdown_cells(line)
        if cells and cells[0] == label:
            matches.append(cells)
    if len(matches) > 1:
        raise ExecutiveSummaryAuditError(f"duplicate executive-summary row {label}")
    return matches[0] if matches else None


def _contains_tokens(text: str, tokens: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return all(token.casefold() in folded for token in tokens)


def audit(summary_path: Path, ledger_path: Path) -> dict[str, Any]:
    summary_text, summary_provenance = _read_utf8_snapshot(summary_path)
    ledger_text, ledger_provenance = _read_utf8_snapshot(ledger_path)
    ledger = _parse_ledger(ledger_text)
    lines = summary_text.splitlines()
    issues: list[dict[str, Any]] = []

    for binding in BINDINGS:
        row = _find_row(lines, binding.label)
        if row is None:
            issues.append({
                "code": "MISSING_EXECUTIVE_CLAIM_ROW",
                "label": binding.label,
                "claim_id": binding.claim_id,
            })
            continue
        status = next(
            (candidate for cell in reversed(row) if (candidate := _extract_status(cell))),
            None,
        )
        ledger_status = ledger[binding.claim_id]["status"]
        if status != binding.required_status or status != ledger_status:
            issues.append({
                "code": "EXECUTIVE_STATUS_MISMATCH",
                "label": binding.label,
                "claim_id": binding.claim_id,
                "summary_status": status,
                "required_status": binding.required_status,
                "ledger_status": ledger_status,
            })
        value_cell = row[1] if len(row) > 1 else ""
        if not _contains_tokens(value_cell, binding.required_value_tokens):
            issues.append({
                "code": "EXECUTIVE_VALUE_CAVEAT_MISSING",
                "label": binding.label,
                "claim_id": binding.claim_id,
                "required_tokens": list(binding.required_value_tokens),
                "value": value_cell,
            })
        truth_cell = row[-3] if len(row) >= 7 else ""
        ledger_truth = ledger[binding.claim_id]["truth_type"]
        if binding.required_truth_tokens and not _contains_tokens(
            truth_cell, binding.required_truth_tokens
        ):
            issues.append({
                "code": "EXECUTIVE_TRUTH_TYPE_MISMATCH",
                "label": binding.label,
                "claim_id": binding.claim_id,
                "summary_truth_type": truth_cell,
                "ledger_truth_type": ledger_truth,
                "required_tokens": list(binding.required_truth_tokens),
            })

    for statement in FORBIDDEN_STATEMENTS:
        if statement in summary_text:
            issues.append({
                "code": "UNSUPPORTED_EXECUTIVE_STATEMENT",
                "statement": statement,
            })

    c12_rows = [
        _markdown_cells(line)
        for line in lines
        if "C12-like anomaly fraction in truth-labelled MC" in line
    ]
    c12_rows = [row for row in c12_rows if row]
    if len(c12_rows) != 1 or _extract_status(c12_rows[0][-1]) != "TRUTH_LEVEL_MC_ONLY":
        issues.append({
            "code": "C12_MC_TRUTH_STATUS_MISSING",
            "required_status": "TRUTH_LEVEL_MC_ONLY",
        })

    return {
        "validator": "validate_executive_summary_claims.py",
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": "EXECUTIVE_SUMMARY_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS",
        "summary": summary_provenance,
        "claim_ledger": ledger_provenance,
        "bindings_checked": [binding._asdict() for binding in BINDINGS],
        "issues": issues,
        "n_issues": len(issues),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.summary, args.claim_ledger)
    except ExecutiveSummaryAuditError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
