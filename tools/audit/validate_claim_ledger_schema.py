#!/usr/bin/env python3
"""Validate claim-ledger CSV width before interpreting any claim fields."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS"
EXPECTED_FIELDS = (
    "claim_id",
    "chapter",
    "section",
    "claim_text",
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
    "truth_type",
    "status",
    "allowed_status_validated",
    "source_report",
    "source_script",
    "source_data",
    "source_config",
    "source_manifest",
    "figure_ids",
    "table_ids",
    "source_commit",
    "link_validated",
    "ci_status",
    "blocked_by",
    "supersedes",
    "notes",
)


class ClaimLedgerSchemaError(ValueError):
    """Controlled input or schema error."""


def _read_utf8_snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ClaimLedgerSchemaError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ClaimLedgerSchemaError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _read_csv_rows(text: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise ClaimLedgerSchemaError(f"invalid CSV: {exc}") from exc


def validate_text(text: str) -> dict[str, Any]:
    rows = _read_csv_rows(text)
    if not rows:
        raise ClaimLedgerSchemaError("claim ledger is empty")

    header = rows[0]
    expected = list(EXPECTED_FIELDS)
    if header != expected:
        raise ClaimLedgerSchemaError(
            "claim ledger header does not match the canonical 43-column schema"
        )

    issues: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    exact_width_claim_ids: list[str] = []
    row_widths: list[dict[str, Any]] = []
    width_counts: Counter[int] = Counter()

    for row_number, row in enumerate(rows[1:], start=2):
        width = len(row)
        width_counts[width] += 1
        claim_id = row[0].strip() if row else ""

        if not claim_id:
            issues.append({
                "code": "MISSING_CLAIM_ID",
                "row_number": row_number,
                "actual_columns": width,
            })
        elif claim_id in seen_ids:
            issues.append({
                "code": "DUPLICATE_CLAIM_ID",
                "row_number": row_number,
                "claim_id": claim_id,
            })
        else:
            seen_ids.add(claim_id)

        row_widths.append({
            "row_number": row_number,
            "claim_id": claim_id or None,
            "actual_columns": width,
            "schema_state": (
                "EXACT_WIDTH" if width == len(EXPECTED_FIELDS) else "WIDTH_MISMATCH"
            ),
            "field_interpretation": (
                "PERMITTED" if width == len(EXPECTED_FIELDS) else "WITHHELD"
            ),
        })

        if width != len(EXPECTED_FIELDS):
            issues.append({
                "code": "ROW_WIDTH_MISMATCH",
                "row_number": row_number,
                "claim_id": claim_id or None,
                "expected_columns": len(EXPECTED_FIELDS),
                "actual_columns": width,
                "missing_columns": max(0, len(EXPECTED_FIELDS) - width),
                "excess_columns": max(0, width - len(EXPECTED_FIELDS)),
                "field_interpretation": "WITHHELD",
            })
        elif claim_id:
            exact_width_claim_ids.append(claim_id)

    mismatch_issues = [
        issue for issue in issues if issue["code"] == "ROW_WIDTH_MISMATCH"
    ]
    return {
        "validator": "validate_claim_ledger_schema.py",
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "expected_columns": len(EXPECTED_FIELDS),
        "header": header,
        "data_rows": len(rows) - 1,
        "exact_width_rows": len(exact_width_claim_ids),
        "width_mismatch_rows": len(mismatch_issues),
        "exact_width_claim_ids": exact_width_claim_ids,
        "row_widths": row_widths,
        "width_histogram": {
            str(width): count for width, count in sorted(width_counts.items())
        },
        "issues": issues,
        "n_issues": len(issues),
    }


def audit(path: Path) -> dict[str, Any]:
    text, provenance = _read_utf8_snapshot(path)
    result = validate_text(text)
    result["claim_ledger"] = provenance
    return result


def _write_svg(path: Path, payload: dict[str, Any]) -> None:
    rows = payload["row_widths"]
    left = 150
    top = 70
    row_height = 24
    chart_width = 600
    min_width = 30
    max_width = 44
    scale = chart_width / (max_width - min_width)
    height = top + row_height * len(rows) + 90
    expected_x = left + (payload["expected_columns"] - min_width) * scale

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="820" height="{height}" '
        'viewBox="0 0 820 {height}" role="img" '
        'aria-labelledby="title desc">'.replace("{height}", str(height)),
        '<title id="title">Claim-ledger row width audit</title>',
        '<desc id="desc">Actual CSV column count for every claim row compared with '
        'the canonical 43-column schema. Mismatched rows are hatched and labelled.</desc>',
        '<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" '
        'stroke="#555" stroke-width="2"/></pattern></defs>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="20" y="28" font-family="sans-serif" font-size="20" '
        'font-weight="bold">Exact current claim-ledger row widths</text>',
        '<text x="20" y="50" font-family="sans-serif" font-size="13">'
        'Repository schema evidence; physics values are not interpreted for '
        'mismatched rows.</text>',
        f'<line x1="{expected_x:.1f}" y1="60" x2="{expected_x:.1f}" '
        f'y2="{top + row_height * len(rows)}" stroke="black" stroke-width="2"/>',
        f'<text x="{expected_x - 4:.1f}" y="63" text-anchor="end" '
        'font-family="sans-serif" font-size="12">expected 43</text>',
    ]

    for index, row in enumerate(rows):
        y = top + index * row_height
        claim_id = html.escape(str(row["claim_id"] or "(missing)"))
        width = row["actual_columns"]
        x = left + (width - min_width) * scale
        exact = row["schema_state"] == "EXACT_WIDTH"
        fill = "#d9d9d9" if exact else "url(#hatch)"
        label = "EXACT" if exact else "MISMATCH"
        parts.extend([
            f'<text x="20" y="{y + 15}" font-family="monospace" '
            f'font-size="12">{claim_id}</text>',
            f'<rect x="{left}" y="{y + 3}" width="{max(1, x - left):.1f}" '
            f'height="15" fill="{fill}" stroke="black"/>',
            f'<text x="{x + 7:.1f}" y="{y + 15}" font-family="sans-serif" '
            f'font-size="11">{width} — {label}</text>',
        ])

    axis_y = top + row_height * len(rows) + 18
    parts.append(
        f'<line x1="{left}" y1="{axis_y}" x2="{left + chart_width}" '
        f'y2="{axis_y}" stroke="black"/>'
    )
    for value in range(min_width, max_width + 1, 2):
        x = left + (value - min_width) * scale
        parts.extend([
            f'<line x1="{x:.1f}" y1="{axis_y}" x2="{x:.1f}" '
            f'y2="{axis_y + 5}" stroke="black"/>',
            f'<text x="{x:.1f}" y="{axis_y + 20}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="11">{value}</text>',
        ])
    parts.extend([
        f'<text x="{left + chart_width / 2:.1f}" y="{axis_y + 42}" '
        'text-anchor="middle" font-family="sans-serif" font-size="13">CSV columns</text>',
        f'<text x="20" y="{height - 18}" font-family="sans-serif" font-size="12">'
        f'Status: {payload["status"]}; exact rows: {payload["exact_width_rows"]}/'
        f'{payload["data_rows"]}; policy: {html.escape(payload["policy"])}</text>',
        '</svg>',
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)

    try:
        result = audit(args.claim_ledger)
    except ClaimLedgerSchemaError as exc:
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
