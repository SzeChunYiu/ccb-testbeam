from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.audit.audit_mv4_legacy_claim_rows import AuditError, audit

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "claim_ledger.csv"
REPORT = ROOT / "reports" / "mv4_timing_1782678162" / "REPORT.md"
SUMMARY = ROOT / "reports" / "mv4_timing_1782678162" / "mv4_summary.json"
CONTRACT = ROOT / "scripts" / "MV4_TIMING_README.md"


def test_exact_current_ledger_is_detected_as_flawed() -> None:
    result = audit(LEDGER, REPORT, SUMMARY, CONTRACT)
    assert result["status"] == "FLAWED"
    codes = {(item["claim_id"], item["code"]) for item in result["issues"] if "claim_id" in item}
    assert ("CL-002", "ROW_WIDTH_MISMATCH") in codes
    assert ("CL-006", "VALUE_ABSENT_FROM_CITED_SOURCE") in codes
    assert ("CL-007", "TOY_PULL_OVERCLAIMED") in codes
    assert ("CL-009", "ML_METHOD_NOT_IN_SOURCE") in codes
    assert result["source_facts"]["n_tracks"] == 80000
    assert result["source_facts"]["corrected_pull"] == 2.680528799917713


def test_corrected_contract_clears_governance_findings(tmp_path: Path) -> None:
    rows = list(csv.reader(LEDGER.read_text().splitlines()))
    header = rows[0]
    by_id = {row[0]: row for row in rows[1:]}
    for cid in ("CL-002", "CL-003", "CL-004", "CL-005", "CL-006"):
        row = [""] * len(header)
        row[0] = cid
        row[3] = "source unresolved"
        row[28] = "BLOCKED"
        row[29] = "NO"
        by_id[cid] = row
    for cid in ("CL-007", "CL-008"):
        by_id[cid] = by_id[cid] + [""] * (len(header) - len(by_id[cid]))
    raw = by_id["CL-007"]
    raw[28] = "GATED"
    raw[29] = "NO"
    by_id["CL-007"] = raw
    verdict = by_id["CL-009"] + [""] * (len(header) - len(by_id["CL-009"]))
    verdict[3] = "analytic timing verdict"
    by_id["CL-009"] = verdict
    path = tmp_path / "ledger.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(by_id.values())
    result = audit(path, REPORT, SUMMARY, CONTRACT)
    remaining = {item["code"] for item in result["issues"]}
    assert "ROW_WIDTH_MISMATCH" not in remaining
    assert "TOY_PULL_OVERCLAIMED" not in remaining
    assert "ML_METHOD_NOT_IN_SOURCE" not in remaining


def test_invalid_utf8_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff")
    with pytest.raises(AuditError, match="valid UTF-8"):
        audit(bad, REPORT, SUMMARY, CONTRACT)


def test_json_evidence_is_machine_readable() -> None:
    result = audit(LEDGER, REPORT, SUMMARY, CONTRACT)
    assert json.loads(json.dumps(result))["n_issues"] == result["n_issues"]
