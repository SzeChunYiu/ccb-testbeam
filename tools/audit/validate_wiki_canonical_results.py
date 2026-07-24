#!/usr/bin/env python3
"""Validate the WIKI canonical-results table against exact-width claim rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "WIKI_CANONICAL_RESULTS_MUST_MATCH_EXACT_WIDTH_LEDGER_ROWS"
EXPECTED_COLUMNS = 43
MISSING_VALUE_TOKENS = {"", "—", "-", "n/a", "na"}


class WikiCanonicalResultsError(ValueError):
    """Controlled input or schema error."""


@dataclass(frozen=True)
class Binding:
    wiki_label: str
    claim_id: str
    check_value: bool = True
    check_uncertainties: bool = True
    require_withheld_when_blank: bool = True


BINDINGS = (
    Binding("B6 single-stave σ₆₈", "CL-002"),
    Binding("Combined 3-stave σ (B4+B6+B8)", "CL-004"),
    Binding("Pair covariance", "CL-006"),
    Binding("τeff (effective live-time)", "CL-011"),
    Binding("Digitizer gain (MV0 v2)", "CL-013"),
    Binding("p/d PID AUC", "CL-017"),
    Binding("C12-like anomaly fraction in truth-labelled MC", "CL-022", False),
    Binding("MV3 legacy B8 fractions / profile statistic", "CL-021", False),
    Binding("MV4 raw timing pull", "CL-007"),
    Binding("MV4 corrected timing pull", "CL-008"),
    Binding("ML timing", "CL-009"),
)

REQUIRED_PCA_TEXT = (
    "PCA 3 PCs 72.546%, 8 PCs 82.188% (synthetic-waveform MC only)"
)
FORBIDDEN_STALE_TEXT = (
    "B6 single-stave σ₆₈ | 0.68–0.75 ns",
    "Combined 3-stave σ (B4+B6+B8) | 0.54–0.56 ns",
    "Pair covariance | −0.127 ns²",
    "PCA 3 PCs 89%, 8 PCs 99.7% | Needs canonical rerun",
)


def _snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WikiCanonicalResultsError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WikiCanonicalResultsError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _parse_ledger(text: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise WikiCanonicalResultsError(f"invalid ledger CSV: {exc}") from exc
    if not rows:
        raise WikiCanonicalResultsError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise WikiCanonicalResultsError(
            f"claim ledger header has {len(header)} columns; expected {EXPECTED_COLUMNS}"
        )
    required = {
        "claim_id",
        "current_value",
        "unit",
        "stat_unc",
        "syst_unc",
        "truth_type",
        "status",
    }
    missing = sorted(required.difference(header))
    if missing:
        raise WikiCanonicalResultsError(
            f"claim ledger missing columns: {', '.join(missing)}"
        )
    parsed: dict[str, dict[str, str]] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if not row or not any(cell.strip() for cell in row):
            continue
        claim_id = row[0].strip()
        if len(row) != EXPECTED_COLUMNS:
            if claim_id in {binding.claim_id for binding in BINDINGS}:
                raise WikiCanonicalResultsError(
                    f"required claim {claim_id} has {len(row)} columns; "
                    f"expected {EXPECTED_COLUMNS}"
                )
            continue
        if claim_id in parsed:
            raise WikiCanonicalResultsError(f"duplicate claim_id {claim_id}")
        parsed[claim_id] = {
            key: value.strip() for key, value in zip(header, row, strict=True)
        }
    for binding in BINDINGS:
        if binding.claim_id not in parsed:
            raise WikiCanonicalResultsError(
                f"required claim {binding.claim_id} is absent"
            )
    return header, parsed


def _cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _canonical_table(wiki_text: str) -> dict[str, list[str]]:
    lines = wiki_text.splitlines()
    in_table = False
    table: dict[str, list[str]] = {}
    for line in lines:
        if line.strip() == "### Canonical Results Table":
            in_table = True
            continue
        if in_table and line.startswith("### "):
            break
        if not in_table:
            continue
        cells = _cells(line)
        if not cells or len(cells) != 6:
            continue
        if cells[0] in {"Claim", "---"}:
            continue
        table[cells[0]] = cells
    if not table:
        raise WikiCanonicalResultsError("canonical results table was not found")
    return table


def _legend(wiki_text: str) -> set[str]:
    lines = wiki_text.splitlines()
    in_legend = False
    statuses: set[str] = set()
    for line in lines:
        if line.strip() == "### Confidence-Status Legend":
            in_legend = True
            continue
        if in_legend and line.startswith("### "):
            break
        if not in_legend:
            continue
        cells = _cells(line)
        if not cells:
            continue
        match = re.fullmatch(r"\*\*([A-Z][A-Z0-9_]*)\*\*", cells[0])
        if match:
            statuses.add(match.group(1))
    if not statuses:
        raise WikiCanonicalResultsError("confidence-status legend was not found")
    return statuses


def _status(cell: str) -> str | None:
    match = re.fullmatch(r"\*\*([A-Z][A-Z0-9_]*)\*\*", cell.strip())
    return match.group(1) if match else None


def _normalize(value: str) -> str:
    value = value.strip().lower().replace("_", " ").replace("+", " plus ")
    value = value.replace("/", " ")
    return " ".join(value.replace("-", " ").split())


def _truth_match(ledger_value: str, wiki_value: str) -> bool:
    ledger = _normalize(ledger_value)
    wiki = _normalize(wiki_value)
    aliases = {
        "data mc self consistent": {
            "data mc self consistent",
            "data plus mc self consistent",
        },
        "mc truth only": {"mc truth only", "truth level mc only"},
        "synthetic waveform mc": {
            "synthetic waveform mc",
            "mc truth only",
        },
        "legacy toy digitizer diagnostic": {
            "legacy toy digitizer diagnostic",
            "legacy toy diagnostic",
        },
        "legacy data mc profile diagnostic": {
            "legacy data mc profile diagnostic",
            "legacy data mc diagnostic",
        },
        "data mc calibration proxy": {
            "data mc calibration proxy",
            "data plus mc calibration proxy",
            "data mc calibration",
        },
    }
    return wiki in aliases.get(ledger, {ledger})


def _first_number(value: str) -> float | None:
    normalized = value.replace("−", "-").replace(",", "")
    match = re.search(r"(?<![A-Za-z0-9])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", normalized)
    return float(match.group(0)) if match else None


def _numeric_match(ledger_value: str, wiki_value: str) -> bool:
    try:
        expected = float(ledger_value)
    except ValueError:
        return _normalize(ledger_value) in _normalize(wiki_value)
    observed = _first_number(wiki_value)
    if observed is None:
        return False
    tolerance = max(5e-3, abs(expected) * 5e-4)
    return math.isclose(observed, expected, rel_tol=0.0, abs_tol=tolerance)


def _missing_display(value: str) -> bool:
    return value.strip().lower() in MISSING_VALUE_TOKENS


def audit(wiki_path: Path, ledger_path: Path) -> dict[str, Any]:
    wiki_text, wiki_provenance = _snapshot(wiki_path)
    ledger_text, ledger_provenance = _snapshot(ledger_path)
    header, ledger = _parse_ledger(ledger_text)
    table = _canonical_table(wiki_text)
    legend = _legend(wiki_text)
    issues: list[dict[str, Any]] = []

    for binding in BINDINGS:
        row = ledger[binding.claim_id]
        cells = table.get(binding.wiki_label)
        if cells is None:
            issues.append({
                "code": "MISSING_WIKI_CLAIM_ROW",
                "wiki_label": binding.wiki_label,
                "claim_id": binding.claim_id,
            })
            continue
        wiki_value, wiki_stat, wiki_syst, wiki_truth, wiki_status_cell = cells[1:]
        wiki_status = _status(wiki_status_cell)
        if wiki_status is None:
            issues.append({
                "code": "MISSING_WIKI_STATUS",
                "wiki_label": binding.wiki_label,
            })
        else:
            if wiki_status not in legend:
                issues.append({
                    "code": "STATUS_OUTSIDE_LEGEND",
                    "wiki_label": binding.wiki_label,
                    "wiki_status": wiki_status,
                })
            if wiki_status != row["status"]:
                issues.append({
                    "code": "STATUS_LEDGER_MISMATCH",
                    "wiki_label": binding.wiki_label,
                    "claim_id": binding.claim_id,
                    "wiki_status": wiki_status,
                    "ledger_status": row["status"],
                })
        if not _truth_match(row["truth_type"], wiki_truth):
            issues.append({
                "code": "TRUTH_TYPE_LEDGER_MISMATCH",
                "wiki_label": binding.wiki_label,
                "claim_id": binding.claim_id,
                "wiki_truth_type": wiki_truth,
                "ledger_truth_type": row["truth_type"],
            })
        if binding.check_value:
            if not row["current_value"]:
                if binding.require_withheld_when_blank and "withheld" not in wiki_value.lower():
                    issues.append({
                        "code": "VALUE_NOT_WITHHELD",
                        "wiki_label": binding.wiki_label,
                        "claim_id": binding.claim_id,
                        "wiki_value": wiki_value,
                    })
            elif not _numeric_match(row["current_value"], wiki_value):
                issues.append({
                    "code": "VALUE_LEDGER_MISMATCH",
                    "wiki_label": binding.wiki_label,
                    "claim_id": binding.claim_id,
                    "wiki_value": wiki_value,
                    "ledger_value": row["current_value"],
                })
        if binding.check_uncertainties:
            for field, wiki_cell in (("stat_unc", wiki_stat), ("syst_unc", wiki_syst)):
                ledger_value = row[field]
                if not ledger_value and not _missing_display(wiki_cell):
                    issues.append({
                        "code": "UNSUPPORTED_WIKI_UNCERTAINTY",
                        "wiki_label": binding.wiki_label,
                        "claim_id": binding.claim_id,
                        "field": field,
                        "wiki_value": wiki_cell,
                    })
                elif ledger_value and not _numeric_match(ledger_value, wiki_cell):
                    issues.append({
                        "code": "UNCERTAINTY_LEDGER_MISMATCH",
                        "wiki_label": binding.wiki_label,
                        "claim_id": binding.claim_id,
                        "field": field,
                        "wiki_value": wiki_cell,
                        "ledger_value": ledger_value,
                    })

    if "REVIEW" not in legend:
        issues.append({
            "code": "MISSING_REVIEW_LEGEND_STATUS",
            "required_status": "REVIEW",
        })
    if REQUIRED_PCA_TEXT not in wiki_text:
        issues.append({
            "code": "MISSING_CURRENT_PCA_CORRECTION",
            "required_text": REQUIRED_PCA_TEXT,
        })
    for stale in FORBIDDEN_STALE_TEXT:
        if stale in wiki_text:
            issues.append({
                "code": "STALE_PUBLIC_CLAIM_PRESENT",
                "phrase": stale,
            })

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "wiki": wiki_provenance,
        "claim_ledger": ledger_provenance,
        "ledger_columns": len(header),
        "bindings_checked": [binding.__dict__ for binding in BINDINGS],
        "legend_statuses": sorted(legend),
        "required_pca_text": REQUIRED_PCA_TEXT,
        "forbidden_stale_text": list(FORBIDDEN_STALE_TEXT),
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
    except WikiCanonicalResultsError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
