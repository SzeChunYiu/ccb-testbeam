#!/usr/bin/env python3
"""Validate public WIKI binding of the canonical S10b live10 claim."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "WIKI_TAU_EFF_MUST_BIND_EXACT_S10B_ESTIMAND_AND_INTERVAL"
EXPECTED_COLUMNS = 43
CLAIM_ID = "CL-011"
CANONICAL_LABEL = "τeff (effective live-time)"
PILEUP_HEADING = "## 5. Pile-up Analysis"
EXPECTED = {
    "claim_text": "S10b run-average 10% template live-time relative to CFD20",
    "current_value": "124.79018394263471",
    "unit": "ns",
    "ci_low": "123.33094981246663",
    "ci_high": "126.35875117626817",
    "ci_level": "0.95",
    "ci_method": "run_mean_nonparametric_bootstrap_percentile",
    "bootstrap_unit": "run",
    "n_runs": "14",
    "n_data": "252266",
    "truth_type": "data_measurement",
    "status": "DONE_DATA_ONLY",
    "allowed_status_validated": "NO",
    "source_commit": "da9651c56ef6495ce9656d84b69b600daa6d8f86",
    "blocked_by": "BLK-S10B-001",
}
EXACT_VALUE_TEXT = "124.79018394263471 ns"
EXACT_CI_TEXT = "[123.33094981246663, 126.35875117626817] ns"
REQUIRED_PILEUP_PHRASES = (
    EXACT_VALUE_TEXT,
    EXACT_CI_TEXT,
    "run-bootstrap 95% interval",
    "14 runs",
    "252266 selected pulses",
    "run-average",
    "not a detector-wide universal dead time",
    "MV5 uses the value as an input rather than independently validating it",
    "BLK-S10B-001",
)
FORBIDDEN_STALE_PHRASES = (
    "τeff remains validated",
    "data + MC self-consistent",
    "| τeff (effective live-time) | 124.79 ns | 0.5 | 1.0 |",
    "| τeff (effective live-time) | 124.79 ns | **VALIDATED**",
    "The effective live-time estimate remains `124.79 ns`",
)


class AuditInputError(ValueError):
    """Controlled invalid-input or schema condition."""


def _snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditInputError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _parse_claim(text: str) -> tuple[list[str], dict[str, str]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise AuditInputError(f"invalid ledger CSV: {exc}") from exc
    if not rows:
        raise AuditInputError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise AuditInputError(
            f"claim ledger header has {len(header)} columns; expected {EXPECTED_COLUMNS}"
        )
    matches: list[list[str]] = []
    for row_number, row in enumerate(rows[1:], start=2):
        if not row or not any(cell.strip() for cell in row):
            continue
        if row[0].strip() != CLAIM_ID:
            continue
        if len(row) != EXPECTED_COLUMNS:
            raise AuditInputError(
                f"{CLAIM_ID} row {row_number} has {len(row)} columns; "
                f"expected {EXPECTED_COLUMNS}"
            )
        matches.append(row)
    if len(matches) != 1:
        raise AuditInputError(f"expected exactly one {CLAIM_ID} row; found {len(matches)}")
    return header, {
        key: value.strip() for key, value in zip(header, matches[0], strict=True)
    }


def _cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _unique_section(text: str, heading: str, next_level_prefix: str) -> str:
    lines = text.splitlines()
    indices = [index for index, line in enumerate(lines) if line.strip() == heading]
    if len(indices) != 1:
        raise AuditInputError(f"expected one {heading!r} heading; found {len(indices)}")
    start = indices[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith(next_level_prefix) and not line.startswith(next_level_prefix + "#"):
            end = index
            break
    return "\n".join(lines[start:end])


def _canonical_section(text: str) -> str:
    return _unique_section(text, "### Canonical Results Table", "### ")


def _pileup_section(text: str) -> str:
    return _unique_section(text, PILEUP_HEADING, "## ")


def _find_rows(section: str, label: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        cells = _cells(line)
        if cells and cells[0] == label:
            rows.append(cells)
    return rows


def _append_ledger_issues(row: dict[str, str], issues: list[dict[str, Any]]) -> None:
    for field, expected in EXPECTED.items():
        observed = row.get(field, "")
        if observed != expected:
            issues.append({
                "code": "LEDGER_CONTRACT_MISMATCH",
                "field": field,
                "expected": expected,
                "observed": observed,
            })
    for field in ("stat_unc", "syst_unc", "total_unc"):
        if row.get(field, ""):
            issues.append({
                "code": "UNSUPPORTED_UNCERTAINTY_COMPONENT",
                "field": field,
                "observed": row[field],
            })


def _append_canonical_row_issues(
    section: str,
    issues: list[dict[str, Any]],
) -> None:
    rows = _find_rows(section, CANONICAL_LABEL)
    if len(rows) != 1:
        issues.append({
            "code": "CANONICAL_ROW_CARDINALITY",
            "label": CANONICAL_LABEL,
            "count": len(rows),
        })
        return
    cells = rows[0]
    if len(cells) != 6:
        issues.append({
            "code": "CANONICAL_ROW_WIDTH",
            "expected": 6,
            "observed": len(cells),
        })
        return
    value, stat_unc, syst_unc, truth_type, status = cells[1:]
    for token in (EXACT_VALUE_TEXT, EXACT_CI_TEXT, "run-bootstrap 95% CI"):
        if token not in value:
            issues.append({
                "code": "CANONICAL_ROW_VALUE_BINDING_MISSING",
                "required": token,
                "observed": value,
            })
    if stat_unc != "—" or syst_unc != "—":
        issues.append({
            "code": "CANONICAL_ROW_UNSUPPORTED_COMPONENTS",
            "stat_unc": stat_unc,
            "syst_unc": syst_unc,
        })
    if truth_type != EXPECTED["truth_type"]:
        issues.append({
            "code": "CANONICAL_ROW_TRUTH_TYPE_MISMATCH",
            "expected": EXPECTED["truth_type"],
            "observed": truth_type,
        })
    if status != f"**{EXPECTED['status']}**":
        issues.append({
            "code": "CANONICAL_ROW_STATUS_MISMATCH",
            "expected": f"**{EXPECTED['status']}**",
            "observed": status,
        })


def _append_pileup_issues(section: str, issues: list[dict[str, Any]]) -> None:
    rows = _find_rows(section, CANONICAL_LABEL)
    if len(rows) != 1:
        issues.append({
            "code": "PILEUP_ROW_CARDINALITY",
            "label": CANONICAL_LABEL,
            "count": len(rows),
        })
    else:
        cells = rows[0]
        if len(cells) != 3:
            issues.append({
                "code": "PILEUP_ROW_WIDTH",
                "expected": 3,
                "observed": len(cells),
            })
        else:
            value, status = cells[1:]
            for token in (EXACT_VALUE_TEXT, EXACT_CI_TEXT, "run-bootstrap 95% CI"):
                if token not in value:
                    issues.append({
                        "code": "PILEUP_ROW_VALUE_BINDING_MISSING",
                        "required": token,
                        "observed": value,
                    })
            if status != f"**{EXPECTED['status']}**":
                issues.append({
                    "code": "PILEUP_ROW_STATUS_MISMATCH",
                    "expected": f"**{EXPECTED['status']}**",
                    "observed": status,
                })
    for phrase in REQUIRED_PILEUP_PHRASES:
        if phrase not in section:
            issues.append({
                "code": "PILEUP_SECTION_CAVEAT_MISSING",
                "required": phrase,
            })


def audit(wiki_path: Path, ledger_path: Path) -> dict[str, Any]:
    wiki_text, wiki_provenance = _snapshot(wiki_path)
    ledger_text, ledger_provenance = _snapshot(ledger_path)
    header, claim = _parse_claim(ledger_text)
    canonical = _canonical_section(wiki_text)
    pileup = _pileup_section(wiki_text)
    issues: list[dict[str, Any]] = []
    _append_ledger_issues(claim, issues)
    _append_canonical_row_issues(canonical, issues)
    _append_pileup_issues(pileup, issues)
    for phrase in FORBIDDEN_STALE_PHRASES:
        count = wiki_text.count(phrase)
        if count:
            issues.append({
                "code": "STALE_TAU_EFF_PUBLIC_TEXT",
                "phrase": phrase,
                "occurrences": count,
            })
    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "wiki": wiki_provenance,
        "claim_ledger": ledger_provenance,
        "claim_id": CLAIM_ID,
        "ledger_columns": len(header),
        "expected_contract": EXPECTED,
        "required_pileup_phrases": list(REQUIRED_PILEUP_PHRASES),
        "forbidden_stale_phrases": list(FORBIDDEN_STALE_PHRASES),
        "issues": issues,
        "n_issues": len(issues),
    }


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return os.path.abspath(left) == os.path.abspath(right)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wiki", type=Path)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output and (
        _same_file(args.output, args.wiki)
        or _same_file(args.output, args.claim_ledger)
    ):
        print("INPUT ERROR: output must not alias an input", file=sys.stderr)
        return 2
    try:
        result = audit(args.wiki, args.claim_ledger)
        if args.output:
            _write_json_atomic(args.output, result)
    except AuditInputError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
