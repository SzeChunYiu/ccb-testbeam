#!/usr/bin/env python3
"""Validate selected WIKI front-door claims against the canonical claim ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

VERSION = "1.1.0"
MISSING_UNCERTAINTY_TOKEN = "CI_MISSING_BLOCKING"


class WikiClaimAuditError(ValueError):
    """Controlled input or schema error."""


class Binding(NamedTuple):
    wiki_label: str
    claim_id: str
    check_truth_type: bool = False


BINDINGS = (
    Binding("MV4 raw timing pull", "CL-007"),
    Binding("MC raw timing pull", "CL-007"),
    Binding("MV4 raw", "CL-007"),
    Binding("τeff (effective live-time)", "CL-011", check_truth_type=True),
)


def _read_utf8_snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WikiClaimAuditError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WikiClaimAuditError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _parse_ledger(text: str) -> dict[str, dict[str, str]]:
    reader = csv.DictReader(text.splitlines())
    required = {"claim_id", "status", "truth_type", "stat_unc", "syst_unc", "ci_status"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        missing = sorted(required.difference(reader.fieldnames or []))
        raise WikiClaimAuditError(f"claim ledger missing columns: {', '.join(missing)}")
    rows: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(reader, start=2):
        claim_id = (row.get("claim_id") or "").strip()
        if not claim_id:
            raise WikiClaimAuditError(f"claim ledger row {row_number} has no claim_id")
        if claim_id in rows:
            raise WikiClaimAuditError(f"duplicate claim_id {claim_id}")
        rows[claim_id] = {key: (value or "").strip() for key, value in row.items()}
    return rows


def _markdown_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _extract_status(cell: str) -> str | None:
    match = re.search(r"\*\*([A-Z][A-Z0-9_]*)\*\*", cell)
    return match.group(1) if match else None


def _row_status(cells: list[str]) -> str | None:
    for cell in reversed(cells[1:]):
        status = _extract_status(cell)
        if status:
            return status
    return None


def _normalize_truth_type(value: str) -> str:
    normalized = value.strip().lower().replace("_", " ")
    normalized = normalized.replace("+", " plus ")
    normalized = normalized.replace("-", " ")
    return " ".join(normalized.split())


def _truth_types_match(ledger_value: str, wiki_value: str) -> bool:
    ledger_norm = _normalize_truth_type(ledger_value)
    wiki_norm = _normalize_truth_type(wiki_value)
    aliases = {
        "data mc self consistent": {
            "data mc self consistent",
            "data plus mc self consistent",
        },
        "digitized mc": {"digitized mc"},
    }
    accepted = aliases.get(ledger_norm, {ledger_norm})
    return wiki_norm in accepted


def _legend_statuses(wiki_lines: list[str]) -> set[str]:
    statuses: set[str] = set()
    in_legend = False
    for line in wiki_lines:
        if line.strip() == "### Confidence-Status Legend":
            in_legend = True
            continue
        if in_legend and line.startswith("### "):
            break
        if not in_legend:
            continue
        cells = _markdown_cells(line)
        if cells:
            status = _extract_status(cells[0])
            if status:
                statuses.add(status)
    if not statuses:
        raise WikiClaimAuditError("confidence-status legend was not found")
    return statuses


def _find_rows(wiki_lines: list[str], label: str) -> list[list[str]]:
    matches: list[list[str]] = []
    for line in wiki_lines:
        cells = _markdown_cells(line)
        if cells and cells[0] == label:
            matches.append(cells)
    return matches


def _ledger_has_missing_uncertainty(rows: dict[str, dict[str, str]]) -> bool:
    fields = ("stat_unc", "syst_unc", "ci_status")
    return any(
        MISSING_UNCERTAINTY_TOKEN in row.get(field, "")
        for row in rows.values()
        for field in fields
    )


def audit(wiki_path: Path, ledger_path: Path) -> dict[str, Any]:
    wiki_text, wiki_provenance = _read_utf8_snapshot(wiki_path)
    ledger_text, ledger_provenance = _read_utf8_snapshot(ledger_path)
    wiki_lines = wiki_text.splitlines()
    ledger = _parse_ledger(ledger_text)
    legend = _legend_statuses(wiki_lines)
    issues: list[dict[str, Any]] = []

    for binding in BINDINGS:
        ledger_row = ledger.get(binding.claim_id)
        if ledger_row is None:
            raise WikiClaimAuditError(f"required claim {binding.claim_id} is absent")
        rows = _find_rows(wiki_lines, binding.wiki_label)
        if not rows:
            issues.append({
                "code": "MISSING_WIKI_CLAIM_ROW",
                "wiki_label": binding.wiki_label,
                "claim_id": binding.claim_id,
            })
            continue
        truth_type_checked = False
        for cells in rows:
            status = _row_status(cells)
            if status is None:
                issues.append({
                    "code": "MISSING_WIKI_STATUS",
                    "wiki_label": binding.wiki_label,
                    "claim_id": binding.claim_id,
                })
                continue
            if status not in legend:
                issues.append({
                    "code": "STATUS_OUTSIDE_LEGEND",
                    "wiki_label": binding.wiki_label,
                    "claim_id": binding.claim_id,
                    "wiki_status": status,
                    "legend_statuses": sorted(legend),
                })
            if status != ledger_row["status"]:
                issues.append({
                    "code": "STATUS_LEDGER_MISMATCH",
                    "wiki_label": binding.wiki_label,
                    "claim_id": binding.claim_id,
                    "wiki_status": status,
                    "ledger_status": ledger_row["status"],
                })
            if binding.check_truth_type and len(cells) >= 6:
                truth_type_checked = True
                if not _truth_types_match(ledger_row["truth_type"], cells[-2]):
                    issues.append({
                        "code": "TRUTH_TYPE_LEDGER_MISMATCH",
                        "wiki_label": binding.wiki_label,
                        "claim_id": binding.claim_id,
                        "wiki_truth_type": cells[-2],
                        "ledger_truth_type": ledger_row["truth_type"],
                    })
        if binding.check_truth_type and not truth_type_checked:
            issues.append({
                "code": "MISSING_WIKI_TRUTH_TYPE",
                "wiki_label": binding.wiki_label,
                "claim_id": binding.claim_id,
            })

    overclaim = "Every number has uncertainty." in wiki_text
    if overclaim and _ledger_has_missing_uncertainty(ledger):
        issues.append({
            "code": "OVERSTATED_UNCERTAINTY_COMPLETENESS",
            "statement": "Every number has uncertainty.",
            "ledger_token": MISSING_UNCERTAINTY_TOKEN,
        })

    return {
        "validator": "validate_wiki_claim_front_door.py",
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "wiki": wiki_provenance,
        "claim_ledger": ledger_provenance,
        "policy": "WIKI_FRONT_DOOR_MUST_MATCH_CANONICAL_LEDGER",
        "bindings_checked": [binding._asdict() for binding in BINDINGS],
        "legend_statuses": sorted(legend),
        "issues": issues,
        "n_issues": len(issues),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wiki", type=Path)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.wiki, args.claim_ledger)
    except WikiClaimAuditError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
