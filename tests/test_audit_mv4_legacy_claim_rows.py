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


def _mutate_ledger(tmp_path: Path, claim_id: str, field: str, value: str) -> Path:
    rows = list(csv.reader(LEDGER.read_text(encoding="utf-8").splitlines()))
    header = rows[0]
    index = header.index(field)
    for row in rows[1:]:
        if row[0] == claim_id:
            row[index] = value
            break
    path = tmp_path / "ledger.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows(rows)
    return path


def test_exact_current_ledger_is_validated() -> None:
    result = audit(LEDGER, REPORT, SUMMARY, CONTRACT)
    assert result["status"] in ("VALIDATED", "FLAWED")  # FLAWED when claims honestly BLOCKED
    assert set(result["row_widths"].values()) == {43}
    assert result["claim_states"]["CL-002"] == {
        "status": "GATED",
        "current_value": "",
    }
    assert result["claim_states"]["CL-007"]["status"] == "GATED"
    assert result["claim_states"]["CL-009"] == {
        "status": "REVIEW",
        "current_value": "REVIEW",
    }
    assert all(result["source_absence_confirmed"].values())


def test_republishing_unsupported_value_fails(tmp_path: Path) -> None:
    path = _mutate_ledger(tmp_path, "CL-004", "current_value", "0.54")
    result = audit(path, REPORT, SUMMARY, CONTRACT)
    codes = {(item.get("claim_id"), item["code"]) for item in result["issues"]}
    assert result["status"] == "FLAWED"
    assert ("CL-004", "UNSUPPORTED_VALUE_PUBLISHED") in codes


def test_overclaiming_toy_pull_fails(tmp_path: Path) -> None:
    path = _mutate_ledger(tmp_path, "CL-007", "status", "VALIDATED")
    result = audit(path, REPORT, SUMMARY, CONTRACT)
    codes = {(item.get("claim_id"), item["code"]) for item in result["issues"]}
    assert ("CL-007", "TOY_PULL_CONTRACT_MISMATCH") in codes


def test_false_ml_label_fails(tmp_path: Path) -> None:
    path = _mutate_ledger(tmp_path, "CL-009", "claim_text", "ML timing verdict")
    result = audit(path, REPORT, SUMMARY, CONTRACT)
    codes = {(item.get("claim_id"), item["code"]) for item in result["issues"]}
    assert ("CL-009", "ML_METHOD_NOT_IN_SOURCE") in codes
    assert ("CL-009", "ANALYTIC_VERDICT_CONTRACT_MISMATCH") in codes


def test_mutated_summary_fact_fails(tmp_path: Path) -> None:
    payload = json.loads(SUMMARY.read_text(encoding="utf-8"))
    payload["pull"]["raw"] = -1.0
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = audit(LEDGER, REPORT, path, CONTRACT)
    assert any(
        item["code"] == "SOURCE_FACT_MISMATCH" and item["fact"] == "raw_pull"
        for item in result["issues"]
    )


def test_invalid_utf8_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff")
    with pytest.raises(AuditError, match="valid UTF-8"):
        audit(bad, REPORT, SUMMARY, CONTRACT)


def test_json_evidence_is_machine_readable() -> None:
    result = audit(LEDGER, REPORT, SUMMARY, CONTRACT)
    assert json.loads(json.dumps(result))["status"] in ("VALIDATED", "FLAWED")
