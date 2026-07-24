#!/usr/bin/env python3
"""Audit legacy MV4 timing claim rows against tracked source artifacts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "LEGACY_MV4_TIMING_REQUIRES_STRICT_INPUTS_AND_SOURCE_BOUND_CLAIMS"
TARGET = tuple(f"CL-{n:03d}" for n in range(2, 10))
UNSUPPORTED = ("CL-002", "CL-003", "CL-004", "CL-005", "CL-006")
LEGACY_VALUES = {
    "CL-002": "0.68",
    "CL-003": "0.75",
    "CL-004": "0.54",
    "CL-005": "0.56",
    "CL-006": "-0.127",
}


class AuditError(ValueError):
    """Controlled input error."""


def snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def read_rows(text: str) -> tuple[list[str], dict[str, list[str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise AuditError(f"invalid ledger CSV: {exc}") from exc
    if not rows or len(rows[0]) != 43:
        raise AuditError("claim ledger header is not the canonical 43-column schema")
    return rows[0], {row[0]: row for row in rows[1:] if row}


def audit(ledger: Path, report: Path, summary: Path, contract: Path) -> dict[str, Any]:
    ledger_text, ledger_meta = snapshot(ledger)
    report_text, report_meta = snapshot(report)
    summary_text, summary_meta = snapshot(summary)
    contract_text, contract_meta = snapshot(contract)
    header, rows = read_rows(ledger_text)
    try:
        summary_json = json.loads(summary_text)
    except json.JSONDecodeError as exc:
        raise AuditError(f"invalid MV4 summary JSON: {exc}") from exc

    issues: list[dict[str, Any]] = []
    widths = {cid: len(rows.get(cid, [])) for cid in TARGET}
    for cid, width in widths.items():
        if width != len(header):
            issues.append({
                "code": "ROW_WIDTH_MISMATCH",
                "claim_id": cid,
                "expected_columns": len(header),
                "actual_columns": width,
            })

    source_text = report_text + "\n" + summary_text
    for cid, value in LEGACY_VALUES.items():
        if value not in source_text:
            issues.append({
                "code": "VALUE_ABSENT_FROM_CITED_SOURCE",
                "claim_id": cid,
                "legacy_value": value,
            })

    raw = rows.get("CL-007", [])
    if len(raw) == 43 and (raw[28] == "VALIDATED" or raw[29] == "YES"):
        issues.append({
            "code": "TOY_PULL_OVERCLAIMED",
            "claim_id": "CL-007",
            "detail": "pull uses hard-coded anchor and assumed 0.10 ns uncertainty",
        })

    verdict = rows.get("CL-009", [])
    if verdict and "ML" in verdict[3]:
        issues.append({
            "code": "ML_METHOD_NOT_IN_SOURCE",
            "claim_id": "CL-009",
            "detail": "source tests CFD20 and analytic A+B/sqrt(amplitude) only",
        })

    missing_paths = []
    for path in ("results.json", "configs/mv4_timing.yaml"):
        if path not in source_text:
            missing_paths.append(path)

    facts = {
        "n_tracks": summary_json.get("n_tracks"),
        "n_events_scanned": summary_json.get("n_events_scanned"),
        "raw_sigma68_ns": summary_json.get("sigma68_ns", {}).get("raw"),
        "raw_bootstrap_se_ns": summary_json.get("sigma68_ns", {}).get("raw_unc"),
        "corrected_sigma68_ns": summary_json.get("sigma68_ns", {}).get(
            "corrected_test_half"
        ),
        "corrected_bootstrap_se_ns": summary_json.get("sigma68_ns", {}).get(
            "corrected_unc"
        ),
        "raw_pull": summary_json.get("pull", {}).get("raw"),
        "corrected_pull": summary_json.get("pull", {}).get("corrected"),
        "assumed_data_unc_ns": summary_json.get("data_reference", {}).get(
            "assumed_data_unc"
        ),
        "gain_adc_per_mev": summary_json.get("digitizer_params", {}).get(
            "gain_adc_per_mev"
        ),
    }
    contract_ok = all(
        phrase in contract_text
        for phrase in ("TOY_DIAGNOSTIC", "--strict", "run/block-level")
    )
    if not contract_ok:
        issues.append({"code": "CURRENT_FAIL_CLOSED_CONTRACT_NOT_FOUND"})

    return {
        "auditor": "audit_mv4_legacy_claim_rows.py",
        "version": VERSION,
        "status": "FLAWED" if issues else "VALIDATED",
        "policy": POLICY,
        "claim_ledger": ledger_meta,
        "legacy_report": report_meta,
        "legacy_summary": summary_meta,
        "current_contract": contract_meta,
        "target_claim_ids": list(TARGET),
        "row_widths": widths,
        "source_facts": facts,
        "missing_cited_paths": missing_paths,
        "issues": issues,
        "n_issues": len(issues),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.ledger, args.report, args.summary, args.contract)
    except AuditError as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if result["status"] == "FLAWED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
