#!/usr/bin/env python3
"""Fail closed when public Birks-kB headlines are not canonically claim-bound."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

VERSION = "1.1.0"
EXPECTED_LEDGER_COLUMNS = 43
BIRKS_TOKEN = "birks"
BIRKS_VALUE_RE = re.compile(
    r"(?<![0-9.])(?P<value>[0-9]+(?:\.[0-9]+)?)\s*"
    r"(?P<unit>cm|mm)\s*/\s*MeV",
    re.IGNORECASE,
)
CANONICAL_STATUSES = {
    "VALIDATED",
    "DONE_DATA_ONLY",
    "TRUTH_LEVEL_MC_ONLY",
    "TENSION",
    "FAIL",
    "FLAWED",
    "CORRECTED",
    "BLOCKED",
    "GATED",
    "REVIEW",
    "SUPERSEDED",
}
NON_AUTHORISING_STATUSES = {
    "TRUTH_LEVEL_MC_ONLY",
    "TENSION",
    "FAIL",
    "FLAWED",
    "CORRECTED",
    "BLOCKED",
    "GATED",
    "REVIEW",
    "SUPERSEDED",
}


class BirksClaimAuditError(ValueError):
    """Controlled input or schema error."""


class Snapshot(NamedTuple):
    text: str
    provenance: dict[str, Any]


class ParsedLedger(NamedTuple):
    rows: list[dict[str, str]]
    widths: dict[str, int]
    header: list[str]


class BirksValue(NamedTuple):
    raw_value: float
    raw_unit: str
    cm_per_mev: float


def _read_utf8_snapshot(path: Path) -> Snapshot:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise BirksClaimAuditError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BirksClaimAuditError(f"{path} is not valid UTF-8") from exc
    return Snapshot(
        text,
        {
            "path": str(path),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "snapshot_method": "SINGLE_READ_EXACT_BYTES",
        },
    )


def _parse_csv(text: str, *, source: str) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        raise BirksClaimAuditError(f"{source} is empty")
    header = [field.strip() for field in rows[0]]
    if len(set(header)) != len(header):
        raise BirksClaimAuditError(f"{source} has duplicate column names")
    return header, rows[1:]


def _parse_ledger(text: str) -> ParsedLedger:
    header, raw_rows = _parse_csv(text, source="claim ledger")
    if len(header) != EXPECTED_LEDGER_COLUMNS:
        raise BirksClaimAuditError(
            f"claim ledger header has {len(header)} columns; expected {EXPECTED_LEDGER_COLUMNS}"
        )
    required = {
        "claim_id",
        "claim_text",
        "current_value",
        "unit",
        "truth_type",
        "status",
        "source_report",
        "source_script",
        "source_commit",
        "ci_status",
        "blocked_by",
    }
    missing = sorted(required.difference(header))
    if missing:
        raise BirksClaimAuditError(f"claim ledger missing columns: {', '.join(missing)}")

    rows: list[dict[str, str]] = []
    widths: dict[str, int] = {}
    for row_number, fields in enumerate(raw_rows, start=2):
        if not fields or not any(value.strip() for value in fields):
            continue
        claim_id = fields[0].strip()
        if not claim_id:
            raise BirksClaimAuditError(f"claim ledger row {row_number} has no claim_id")
        if claim_id in widths:
            raise BirksClaimAuditError(f"duplicate claim_id {claim_id}")
        widths[claim_id] = len(fields)
        if len(fields) != EXPECTED_LEDGER_COLUMNS:
            raise BirksClaimAuditError(
                f"claim {claim_id} has {len(fields)} columns; expected {EXPECTED_LEDGER_COLUMNS}"
            )
        rows.append({key: value.strip() for key, value in zip(header, fields, strict=True)})
    return ParsedLedger(rows, widths, header)


def _birks_ledger_rows(ledger: ParsedLedger) -> list[dict[str, str]]:
    return [row for row in ledger.rows if BIRKS_TOKEN in row["claim_text"].casefold()]


def _parse_claim_table(text: str) -> list[dict[str, str]]:
    header, raw_rows = _parse_csv(text, source="cluster-E claim table")
    required = {"claim", "headline", "evidence_class", "status", "source", "claim_id"}
    missing = sorted(required.difference(header))
    if missing:
        raise BirksClaimAuditError(
            f"cluster-E claim table missing columns: {', '.join(missing)}"
        )
    parsed: list[dict[str, str]] = []
    for row_number, fields in enumerate(raw_rows, start=2):
        if not fields or not any(value.strip() for value in fields):
            continue
        if len(fields) != len(header):
            raise BirksClaimAuditError(
                f"cluster-E claim table row {row_number} has {len(fields)} columns; "
                f"expected {len(header)}"
            )
        parsed.append({key: value.strip() for key, value in zip(header, fields, strict=True)})
    return parsed


def _markdown_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _extract_statuses(line: str) -> list[str]:
    tokens = re.findall(r"\b[A-Z][A-Z0-9_]+\b", line)
    result = [token for token in tokens if token in CANONICAL_STATUSES or token == "PASS"]
    return list(dict.fromkeys(result))


def _parse_birks_values(text: str) -> list[BirksValue]:
    values: list[BirksValue] = []
    for match in BIRKS_VALUE_RE.finditer(text):
        raw_value = float(match.group("value"))
        raw_unit = match.group("unit").casefold()
        cm_per_mev = raw_value if raw_unit == "cm" else raw_value / 10.0
        values.append(BirksValue(raw_value, raw_unit, cm_per_mev))
    return values


def _public_birks_lines(text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if BIRKS_TOKEN not in line.casefold():
            continue
        values = _parse_birks_values(line)
        if not values:
            continue
        hits.append(
            {
                "line": number,
                "text": line.strip(),
                "statuses": _extract_statuses(line),
                "values_cm_per_mev": [value.cm_per_mev for value in values],
                "cells": _markdown_cells(line),
            }
        )
    return hits


def _source_claim_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if BIRKS_TOKEN in row["claim"].casefold()
        or BIRKS_TOKEN in row["headline"].casefold()
    ]


def _ledger_value_cm_per_mev(row: dict[str, str]) -> float | None:
    try:
        value = float(row["current_value"])
    except ValueError:
        return None
    unit = row["unit"].casefold().replace(" ", "")
    if unit == "cm/mev":
        return value
    if unit == "mm/mev":
        return value / 10.0
    return None


def _same_value(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-15)


def _append_public_issues(
    *,
    name: str,
    text: str,
    hits: list[dict[str, Any]],
    canonical_row: dict[str, str] | None,
    canonical_value: float | None,
    source_rows: list[dict[str, str]],
    issues: list[dict[str, Any]],
) -> None:
    if not hits:
        return
    if canonical_row is None:
        issues.append(
            {
                "code": "PUBLIC_BIRKS_NUMERIC_CLAIM_UNBOUND",
                "document": name,
                "occurrences": len(hits),
                "lines": [hit["line"] for hit in hits],
            }
        )
    if not source_rows and (
        "clusterE/claims_table.csv" in text
        or "clusterE/claims_table.csv`" in text
        or "claims_table.csv" in text and "reproduced" in text.casefold()
    ):
        issues.append(
            {
                "code": "DECLARED_SOURCE_TABLE_MISSING_BIRKS",
                "document": name,
                "occurrences": len(hits),
            }
        )
    if canonical_row is None:
        return

    ledger_status = canonical_row["status"]
    for hit in hits:
        statuses = hit["statuses"]
        if canonical_value is not None and any(
            not _same_value(value, canonical_value)
            for value in hit["values_cm_per_mev"]
        ):
            issues.append(
                {
                    "code": "PUBLIC_BIRKS_VALUE_MISMATCH",
                    "document": name,
                    "line": hit["line"],
                    "public_values_cm_per_mev": hit["values_cm_per_mev"],
                    "ledger_value_cm_per_mev": canonical_value,
                }
            )
        if "PASS" in statuses and ledger_status != "VALIDATED":
            issues.append(
                {
                    "code": "PUBLIC_STATUS_STRONGER_THAN_LEDGER",
                    "document": name,
                    "line": hit["line"],
                    "public_status": "PASS",
                    "ledger_status": ledger_status,
                }
            )
        canonical_public = [status for status in statuses if status in CANONICAL_STATUSES]
        if canonical_public and ledger_status not in canonical_public:
            issues.append(
                {
                    "code": "PUBLIC_STATUS_LEDGER_MISMATCH",
                    "document": name,
                    "line": hit["line"],
                    "public_statuses": canonical_public,
                    "ledger_status": ledger_status,
                }
            )
        if ledger_status in NON_AUTHORISING_STATUSES and not statuses:
            issues.append(
                {
                    "code": "NONAUTHORISING_BIRKS_VALUE_WITHOUT_STATUS_CAVEAT",
                    "document": name,
                    "line": hit["line"],
                    "ledger_status": ledger_status,
                }
            )


def _validate_canonical_row(
    row: dict[str, str],
    source_rows: list[dict[str, str]],
    issues: list[dict[str, Any]],
) -> float | None:
    required_nonblank = (
        "current_value",
        "unit",
        "truth_type",
        "status",
        "source_report",
        "source_script",
        "source_commit",
        "ci_status",
    )
    for field in required_nonblank:
        if not row[field]:
            issues.append(
                {
                    "code": "BIRKS_LEDGER_REQUIRED_FIELD_BLANK",
                    "claim_id": row["claim_id"],
                    "field": field,
                }
            )
    if row["status"] in NON_AUTHORISING_STATUSES and not row["blocked_by"]:
        issues.append(
            {
                "code": "BIRKS_LEDGER_BLOCKERS_MISSING",
                "claim_id": row["claim_id"],
                "status": row["status"],
            }
        )
    canonical_value = _ledger_value_cm_per_mev(row)
    if canonical_value is None or not math.isfinite(canonical_value) or canonical_value < 0:
        issues.append(
            {
                "code": "BIRKS_LEDGER_VALUE_UNIT_INVALID",
                "claim_id": row["claim_id"],
                "value": row["current_value"],
                "unit": row["unit"],
            }
        )
        canonical_value = None

    matching_source = [source for source in source_rows if source["claim_id"] == row["claim_id"]]
    if len(matching_source) != 1:
        issues.append(
            {
                "code": "BIRKS_LEDGER_SOURCE_TABLE_BINDING_NOT_UNIQUE",
                "claim_id": row["claim_id"],
                "matches": len(matching_source),
            }
        )
        return canonical_value
    source = matching_source[0]
    if source["status"] != row["status"]:
        issues.append(
            {
                "code": "BIRKS_SOURCE_TABLE_STATUS_MISMATCH",
                "claim_id": row["claim_id"],
                "source_status": source["status"],
                "ledger_status": row["status"],
            }
        )
    source_values = _parse_birks_values(source["headline"])
    if canonical_value is not None and (
        len(source_values) != 1
        or not _same_value(source_values[0].cm_per_mev, canonical_value)
    ):
        issues.append(
            {
                "code": "BIRKS_SOURCE_TABLE_VALUE_MISMATCH",
                "claim_id": row["claim_id"],
                "headline": source["headline"],
                "ledger_value_cm_per_mev": canonical_value,
            }
        )
    return canonical_value


def audit(
    readme_path: Path,
    wiki_path: Path,
    narrative_path: Path,
    ledger_path: Path,
    claims_table_path: Path,
) -> dict[str, Any]:
    docs = {
        "README.md": _read_utf8_snapshot(readme_path),
        "WIKI.md": _read_utf8_snapshot(wiki_path),
        "docs/PUBLICATION_NARRATIVE.md": _read_utf8_snapshot(narrative_path),
    }
    ledger_snapshot = _read_utf8_snapshot(ledger_path)
    source_snapshot = _read_utf8_snapshot(claims_table_path)
    ledger = _parse_ledger(ledger_snapshot.text)
    birks_rows = _birks_ledger_rows(ledger)
    if len(birks_rows) > 1:
        ids = ", ".join(row["claim_id"] for row in birks_rows)
        raise BirksClaimAuditError(f"multiple canonical Birks claim rows: {ids}")
    canonical_row = birks_rows[0] if birks_rows else None
    source_rows_all = _parse_claim_table(source_snapshot.text)
    source_rows = _source_claim_rows(source_rows_all)

    issues: list[dict[str, Any]] = []
    canonical_value = None
    if canonical_row is not None:
        canonical_value = _validate_canonical_row(canonical_row, source_rows, issues)

    public_hits: dict[str, list[dict[str, Any]]] = {}
    for name, snapshot in docs.items():
        hits = _public_birks_lines(snapshot.text)
        public_hits[name] = hits
        _append_public_issues(
            name=name,
            text=snapshot.text,
            hits=hits,
            canonical_row=canonical_row,
            canonical_value=canonical_value,
            source_rows=source_rows,
            issues=issues,
        )

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": "PUBLIC_NUMERIC_BIRKS_CLAIMS_REQUIRE_EXACT_CANONICAL_BINDING",
        "documents": {name: snapshot.provenance for name, snapshot in docs.items()},
        "claim_ledger": ledger_snapshot.provenance,
        "clusterE_claims_table": source_snapshot.provenance,
        "canonical_birks_claim_id": canonical_row["claim_id"] if canonical_row else None,
        "canonical_birks_status": canonical_row["status"] if canonical_row else None,
        "canonical_birks_value_cm_per_mev": canonical_value,
        "source_birks_rows": [row.get("claim_id", "") for row in source_rows],
        "public_occurrences": {
            name: [
                {
                    "line": hit["line"],
                    "text": hit["text"],
                    "statuses": hit["statuses"],
                    "values_cm_per_mev": hit["values_cm_per_mev"],
                }
                for hit in hits
            ]
            for name, hits in public_hits.items()
        },
        "issues": issues,
        "n_issues": len(issues),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("readme", type=Path)
    parser.add_argument("wiki", type=Path)
    parser.add_argument("publication_narrative", type=Path)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("clusterE_claims_table", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(
            args.readme,
            args.wiki,
            args.publication_narrative,
            args.claim_ledger,
            args.clusterE_claims_table,
        )
    except BirksClaimAuditError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
