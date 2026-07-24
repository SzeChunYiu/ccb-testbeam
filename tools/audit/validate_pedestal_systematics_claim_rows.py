#!/usr/bin/env python3
"""Validate CL-025 and CL-026 against exact-width schema and source evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "BLOCKED_GOVERNANCE_CLAIMS_REQUIRE_EXACT_WIDTH_AND_SOURCE_EVIDENCE"
EXPECTED_COLUMNS = 43
REQUIRED_SOURCE_COMMIT = "779740b15c66842144fd191e304a28d7eb31bad5"


class ClaimRowValidationError(ValueError):
    """Controlled input or schema error."""


def _read_utf8_snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ClaimRowValidationError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClaimRowValidationError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _parse_ledger(text: str) -> tuple[list[str], list[list[str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise ClaimRowValidationError(f"invalid ledger CSV: {exc}") from exc
    if not rows:
        raise ClaimRowValidationError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise ClaimRowValidationError(
            f"claim ledger header has {len(header)} columns, expected {EXPECTED_COLUMNS}"
        )
    if len(set(header)) != len(header):
        raise ClaimRowValidationError("claim ledger header contains duplicate field names")
    return header, rows[1:]


def _find_row(header: list[str], rows: list[list[str]], claim_id: str) -> dict[str, str]:
    matches = [row for row in rows if row and row[0].strip() == claim_id]
    if len(matches) != 1:
        raise ClaimRowValidationError(
            f"expected exactly one {claim_id} row, found {len(matches)}"
        )
    row = matches[0]
    if len(row) != len(header):
        raise ClaimRowValidationError(
            f"{claim_id} has {len(row)} columns, expected {len(header)}"
        )
    return dict(zip(header, row, strict=True))


def _require_equal(
    issues: list[dict[str, Any]],
    row: dict[str, str],
    claim_id: str,
    field: str,
    expected: str,
) -> None:
    actual = row.get(field, "")
    if actual != expected:
        issues.append(
            {
                "code": "FIELD_MISMATCH",
                "claim_id": claim_id,
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def _require_blank_quantities(
    issues: list[dict[str, Any]], row: dict[str, str], claim_id: str
) -> None:
    fields = (
        "current_value",
        "unit",
        "stat_unc",
        "syst_unc",
        "total_unc",
        "ci_low",
        "ci_high",
        "ci_level",
        "ci_method",
        "bootstrap_unit",
        "n_events",
        "n_runs",
        "n_data",
        "n_mc",
        "numerator",
        "denominator",
        "p_value",
        "effect_size",
        "baseline_value",
        "baseline_unc",
        "delta_vs_baseline",
        "delta_ci_low",
        "delta_ci_high",
    )
    nonblank = {field: row[field] for field in fields if row.get(field, "")}
    if nonblank:
        issues.append(
            {
                "code": "BLOCKED_ROW_PUBLISHES_QUANTITATIVE_VALUE",
                "claim_id": claim_id,
                "nonblank_fields": nonblank,
            }
        )


def _require_notes(
    issues: list[dict[str, Any]],
    row: dict[str, str],
    claim_id: str,
    required_phrases: tuple[str, ...],
) -> None:
    notes = row.get("notes", "").lower()
    missing = [phrase for phrase in required_phrases if phrase.lower() not in notes]
    if missing:
        issues.append(
            {
                "code": "MISSING_REQUIRED_CAVEAT",
                "claim_id": claim_id,
                "missing_phrases": missing,
            }
        )


def validate_text(ledger_text: str, source_text: str) -> dict[str, Any]:
    header, rows = _parse_ledger(ledger_text)
    cl025 = _find_row(header, rows, "CL-025")
    cl026 = _find_row(header, rows, "CL-026")
    issues: list[dict[str, Any]] = []

    common = {
        "status": "BLOCKED",
        "allowed_status_validated": "NO",
        "source_report": "docs/SYSTEMATIC_UNCERTAINTIES.md",
        "source_commit": REQUIRED_SOURCE_COMMIT,
        "link_validated": "YES",
        "ci_status": "NOT_APPLICABLE_WITH_REASON",
    }
    expected_by_claim = {
        "CL-025": {
            "chapter": "Pedestal",
            "section": "11",
            "claim_text": "Forced-trigger pedestal truth unavailable",
            "truth_type": "data_availability",
            "blocked_by": "BLK-PED-001",
            **common,
        },
        "CL-026": {
            "chapter": "Systematics",
            "section": "11",
            "claim_text": "Systematic uncertainty propagation incomplete",
            "truth_type": "uncertainty_budget_incomplete",
            "blocked_by": "BLK-SYST-001",
            **common,
        },
    }

    for claim_id, row in (("CL-025", cl025), ("CL-026", cl026)):
        for field, expected in expected_by_claim[claim_id].items():
            _require_equal(issues, row, claim_id, field, expected)
        _require_blank_quantities(issues, row, claim_id)

    _require_notes(
        issues,
        cl025,
        "CL-025",
        (
            "no forced-trigger zero-signal events",
            "not an independently measured pedestal truth",
            "no pedestal-truth number or uncertainty is authorized",
        ),
    )
    _require_notes(
        issues,
        cl026,
        "CL-026",
        (
            "claim-specific nuisance model",
            "covariance treatment",
            "reproducible propagation code",
            "not blanket authorization",
        ),
    )

    source_requirements = (
        "No forced-trigger zero-signal events exist",
        "until a forced-trigger S16 pedestal sample is acquired",
        "Total (add in quadrature)",
    )
    for phrase in source_requirements:
        if phrase not in source_text:
            issues.append(
                {
                    "code": "SOURCE_EVIDENCE_MISSING",
                    "source": "docs/SYSTEMATIC_UNCERTAINTIES.md",
                    "required_phrase": phrase,
                }
            )

    return {
        "validator": "validate_pedestal_systematics_claim_rows.py",
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "expected_columns": EXPECTED_COLUMNS,
        "validated_claim_ids": ["CL-025", "CL-026"],
        "source_commit_required": REQUIRED_SOURCE_COMMIT,
        "issues": issues,
        "n_issues": len(issues),
    }


def audit(ledger_path: Path, source_path: Path) -> dict[str, Any]:
    ledger_text, ledger_provenance = _read_utf8_snapshot(ledger_path)
    source_text, source_provenance = _read_utf8_snapshot(source_path)
    result = validate_text(ledger_text, source_text)
    result["claim_ledger"] = ledger_provenance
    result["source_document"] = source_provenance
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_svg(path: Path, payload: dict[str, Any]) -> None:
    status = html.escape(payload["status"])
    policy = html.escape(payload["policy"])
    issue_count = payload["n_issues"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="430" '
        'viewBox="0 0 900 430" role="img" aria-labelledby="title desc">',
        '<title id="title">Pedestal and systematics claim-row gate</title>',
        '<desc id="desc">Synthetic schema-and-provenance diagram showing malformed '
        'blocked rows repaired to the canonical 43-column contract.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="38" font-family="sans-serif" font-size="22" '
        'font-weight="bold">Blocked governance claims: exact-width repair</text>',
        '<text x="30" y="64" font-family="sans-serif" font-size="13">'
        'Repository schema/provenance evidence; no detector measurement is created.</text>',
        '<text x="80" y="115" font-family="monospace" font-size="18">CL-025</text>',
        '<rect x="190" y="90" width="185" height="42" fill="white" '
        'stroke="black" stroke-dasharray="6 4"/>',
        '<text x="282" y="116" text-anchor="middle" font-family="sans-serif" '
        'font-size="15">37 columns / withheld</text>',
        '<line x1="390" y1="111" x2="505" y2="111" stroke="black" '
        'stroke-width="2" marker-end="url(#arrow)"/>',
        '<rect x="520" y="90" width="250" height="42" fill="#e5e5e5" stroke="black"/>',
        '<text x="645" y="108" text-anchor="middle" font-family="sans-serif" '
        'font-size="14">43 columns / BLOCKED</text>',
        '<text x="645" y="125" text-anchor="middle" font-family="sans-serif" '
        'font-size="12">no pedestal truth authorized</text>',
        '<text x="80" y="190" font-family="monospace" font-size="18">CL-026</text>',
        '<rect x="190" y="165" width="185" height="42" fill="white" '
        'stroke="black" stroke-dasharray="6 4"/>',
        '<text x="282" y="191" text-anchor="middle" font-family="sans-serif" '
        'font-size="15">35 columns / withheld</text>',
        '<line x1="390" y1="186" x2="505" y2="186" stroke="black" '
        'stroke-width="2" marker-end="url(#arrow)"/>',
        '<rect x="520" y="165" width="250" height="42" fill="#e5e5e5" stroke="black"/>',
        '<text x="645" y="183" text-anchor="middle" font-family="sans-serif" '
        'font-size="14">43 columns / BLOCKED</text>',
        '<text x="645" y="200" text-anchor="middle" font-family="sans-serif" '
        'font-size="12">no propagated budget authorized</text>',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" '
        'refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" '
        'fill="black"/></marker></defs>',
        '<rect x="80" y="245" width="690" height="92" fill="white" stroke="black"/>',
        '<text x="100" y="273" font-family="sans-serif" font-size="14">'
        'Source evidence: no forced-trigger zero-signal events; simple quadrature '
        'inventory only.</text>',
        '<text x="100" y="300" font-family="sans-serif" font-size="14">'
        'Required next evidence: immutable pedestal sample and claim-specific nuisance '
        'propagation.</text>',
        '<text x="100" y="327" font-family="sans-serif" font-size="13">'
        f'Policy: {policy}</text>',
        '<text x="30" y="390" font-family="sans-serif" font-size="14">'
        f'Status: {status}; issues: {issue_count}; synthetic validation diagram, not data.</text>',
        '</svg>',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("source_document", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.claim_ledger, args.source_document)
    except ClaimRowValidationError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        _write_json(args.output, result)
    if args.svg:
        _write_svg(args.svg, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
