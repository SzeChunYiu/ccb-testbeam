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

VERSION = "1.2.0"
EXPECTED_LEDGER_COLUMNS = 43
MISSING_UNCERTAINTY_TOKEN = "CI_MISSING_BLOCKING"


class WikiClaimAuditError(ValueError):
    """Controlled input or schema error."""


class Binding(NamedTuple):
    wiki_label: str
    claim_id: str
    check_truth_type: bool = False
    withhold_unit_when_blank: bool = False
    check_status: bool = True


BINDINGS = (
    Binding("MV4 raw timing pull", "CL-007"),
    Binding("MC raw timing pull", "CL-007"),
    Binding("MV4 raw", "CL-007"),
    Binding("τeff (effective live-time)", "CL-011", True),
    Binding("Rmax (pile-up tolerance)", "CL-010", True, True),
    Binding("MV5", "CL-010"),
    Binding("4.22 MHz", "CL-012", False, True, False),
    Binding("Duplicate-readout model", "CL-015", True),
    Binding("Duplicate readout", "CL-015"),
    Binding("ML duplicate-readout", "CL-015"),
    Binding("Saturation-recovery model", "CL-016", True),
    Binding("Saturation recovery", "CL-016"),
    Binding("ML saturation recovery", "CL-016"),
)

FORBIDDEN_PUBLIC_PHRASES = (
    ("3.044–3.05 MHz", "WITHHELD_RMAX_VALUE_PUBLISHED"),
    ("~3.05 MHz", "WITHHELD_RMAX_VALUE_PUBLISHED"),
    ("μ_max ≈ 0.38", "UNRESOLVED_RMAX_THRESHOLD_PUBLISHED"),
    (
        "Rmax = 0.38 / 124.79 ns = 3.04 MHz",
        "UNRESOLVED_RMAX_DERIVATION_PUBLISHED",
    ),
    (
        "| ML wins | Duplicate readout, saturation recovery |",
        "UNSUPPORTED_COMBINED_ML_WIN_CLAIM",
    ),
    ("**ML wins**", "UNSUPPORTED_ML_WIN_CLAIM"),
    ("Confirmed win domain", "UNSUPPORTED_ML_WIN_CLAIM"),
    (
        "ML excels where the missing information is genuinely in waveform shape "
        "(saturation recovery, duplicate-readout closure).",
        "UNSUPPORTED_ML_WIN_CLAIM",
    ),
)

REQUIRED_PUBLIC_STATEMENTS = (
    "Rmax is withheld pending S-STAT-003",
    "No production duplicate-readout or saturation correction is authorized.",
)


class ParsedLedger(NamedTuple):
    rows: dict[str, dict[str, str]]
    widths: dict[str, int]
    expected_width: int


def _read_utf8_snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WikiClaimAuditError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WikiClaimAuditError(f"{path} is not valid UTF-8") from exc
    provenance = {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    return text, provenance


def _parse_ledger(text: str) -> ParsedLedger:
    parsed = list(csv.reader(text.splitlines()))
    if not parsed:
        raise WikiClaimAuditError("claim ledger is empty")
    header = [value.strip() for value in parsed[0]]
    if len(header) != EXPECTED_LEDGER_COLUMNS:
        raise WikiClaimAuditError(
            f"claim ledger header has {len(header)} columns; "
            f"expected {EXPECTED_LEDGER_COLUMNS}"
        )
    required = {
        "claim_id",
        "current_value",
        "unit",
        "status",
        "truth_type",
        "stat_unc",
        "syst_unc",
        "ci_status",
    }
    missing = sorted(required.difference(header))
    if missing:
        raise WikiClaimAuditError(f"claim ledger missing columns: {', '.join(missing)}")
    if len(set(header)) != len(header):
        raise WikiClaimAuditError("claim ledger has duplicate column names")

    rows: dict[str, dict[str, str]] = {}
    widths: dict[str, int] = {}
    for row_number, fields in enumerate(parsed[1:], start=2):
        if not fields or not any(value.strip() for value in fields):
            continue
        claim_id = fields[0].strip()
        if not claim_id:
            raise WikiClaimAuditError(f"claim ledger row {row_number} has no claim_id")
        if claim_id in widths:
            raise WikiClaimAuditError(f"duplicate claim_id {claim_id}")
        widths[claim_id] = len(fields)
        if len(fields) == EXPECTED_LEDGER_COLUMNS:
            rows[claim_id] = {
                key: value.strip() for key, value in zip(header, fields, strict=True)
            }
    return ParsedLedger(rows, widths, len(header))


def _markdown_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _extract_status(cell: str) -> str | None:
    match = re.search(r"\*\*([A-Z][A-Z0-9_]*)\*\*", cell)
    return match.group(1) if match else None


def _row_status(cells: list[str]) -> str | None:
    return next(
        (status for cell in reversed(cells[1:]) if (status := _extract_status(cell))),
        None,
    )


def _normalize_truth_type(value: str) -> str:
    value = value.strip().lower().replace("_", " ").replace("+", " plus ")
    return " ".join(value.replace("-", " ").split())


def _truth_types_match(ledger_value: str, wiki_value: str) -> bool:
    ledger = _normalize_truth_type(ledger_value)
    wiki = _normalize_truth_type(wiki_value)
    aliases = {
        "data mc self consistent": {
            "data mc self consistent",
            "data plus mc self consistent",
        }
    }
    return wiki in aliases.get(ledger, {ledger})


def _legend_statuses(lines: list[str]) -> set[str]:
    statuses: set[str] = set()
    in_legend = False
    for line in lines:
        if line.strip() == "### Confidence-Status Legend":
            in_legend = True
            continue
        if in_legend and line.startswith("### "):
            break
        if in_legend and (cells := _markdown_cells(line)):
            if status := _extract_status(cells[0]):
                statuses.add(status)
    if not statuses:
        raise WikiClaimAuditError("confidence-status legend was not found")
    return statuses


def _find_rows(lines: list[str], label: str) -> list[list[str]]:
    return [
        cells
        for line in lines
        if (cells := _markdown_cells(line)) and cells[0] == label
    ]


def _required_row(ledger: ParsedLedger, claim_id: str) -> dict[str, str]:
    width = ledger.widths.get(claim_id)
    if width is None:
        raise WikiClaimAuditError(f"required claim {claim_id} is absent")
    if width != ledger.expected_width:
        raise WikiClaimAuditError(
            f"required claim {claim_id} has {width} columns; "
            f"expected {ledger.expected_width}"
        )
    return ledger.rows[claim_id]


def _append_binding_issues(
    binding: Binding,
    ledger_row: dict[str, str],
    rows: list[list[str]],
    legend: set[str],
    issues: list[dict[str, Any]],
) -> None:
    if not rows:
        issues.append({
            "code": "MISSING_WIKI_CLAIM_ROW",
            "wiki_label": binding.wiki_label,
            "claim_id": binding.claim_id,
        })
        return
    truth_checked = False
    for cells in rows:
        if binding.check_status:
            status = _row_status(cells)
            if status is None:
                issues.append({
                    "code": "MISSING_WIKI_STATUS",
                    "wiki_label": binding.wiki_label,
                    "claim_id": binding.claim_id,
                })
            else:
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
            truth_checked = True
            if not _truth_types_match(ledger_row["truth_type"], cells[-2]):
                issues.append({
                    "code": "TRUTH_TYPE_LEDGER_MISMATCH",
                    "wiki_label": binding.wiki_label,
                    "claim_id": binding.claim_id,
                    "wiki_truth_type": cells[-2],
                    "ledger_truth_type": ledger_row["truth_type"],
                })
        if binding.withhold_unit_when_blank and not ledger_row["current_value"]:
            wiki_value = cells[1] if len(cells) > 1 else ""
            unit = ledger_row["unit"]
            if unit and unit.casefold() in wiki_value.casefold():
                issues.append({
                    "code": "VALUE_PRESENT_WHEN_LEDGER_WITHHOLDS",
                    "wiki_label": binding.wiki_label,
                    "claim_id": binding.claim_id,
                    "wiki_value": wiki_value,
                    "ledger_unit": unit,
                })
    if binding.check_truth_type and not truth_checked:
        issues.append({
            "code": "MISSING_WIKI_TRUTH_TYPE",
            "wiki_label": binding.wiki_label,
            "claim_id": binding.claim_id,
        })


def audit(wiki_path: Path, ledger_path: Path) -> dict[str, Any]:
    wiki_text, wiki_provenance = _read_utf8_snapshot(wiki_path)
    ledger_text, ledger_provenance = _read_utf8_snapshot(ledger_path)
    lines = wiki_text.splitlines()
    ledger = _parse_ledger(ledger_text)
    legend = _legend_statuses(lines)
    required_rows = {
        claim_id: _required_row(ledger, claim_id)
        for claim_id in dict.fromkeys(binding.claim_id for binding in BINDINGS)
    }
    issues: list[dict[str, Any]] = []
    for binding in BINDINGS:
        _append_binding_issues(
            binding,
            required_rows[binding.claim_id],
            _find_rows(lines, binding.wiki_label),
            legend,
            issues,
        )

    missing_uncertainty = any(
        MISSING_UNCERTAINTY_TOKEN in row.get(field, "")
        for row in required_rows.values()
        for field in ("stat_unc", "syst_unc", "ci_status")
    )
    if "Every number has uncertainty." in wiki_text and missing_uncertainty:
        issues.append({
            "code": "OVERSTATED_UNCERTAINTY_COMPLETENESS",
            "statement": "Every number has uncertainty.",
            "ledger_token": MISSING_UNCERTAINTY_TOKEN,
        })
    for phrase, code in FORBIDDEN_PUBLIC_PHRASES:
        if count := wiki_text.count(phrase):
            issues.append({"code": code, "phrase": phrase, "occurrences": count})
    for statement in REQUIRED_PUBLIC_STATEMENTS:
        if statement not in wiki_text:
            issues.append({
                "code": "MISSING_REQUIRED_PUBLIC_CAVEAT",
                "statement": statement,
            })

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "wiki": wiki_provenance,
        "claim_ledger": ledger_provenance,
        "policy": "WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS",
        "expected_ledger_columns": ledger.expected_width,
        "required_claim_widths": {
            claim_id: ledger.widths[claim_id] for claim_id in required_rows
        },
        "bindings_checked": [binding._asdict() for binding in BINDINGS],
        "legend_statuses": sorted(legend),
        "forbidden_public_phrases": [phrase for phrase, _ in FORBIDDEN_PUBLIC_PHRASES],
        "required_public_statements": list(REQUIRED_PUBLIC_STATEMENTS),
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
