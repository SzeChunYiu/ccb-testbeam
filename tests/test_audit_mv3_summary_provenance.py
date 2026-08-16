from __future__ import annotations

import csv
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDITOR_PATH = ROOT / "tools/audit/audit_mv3_summary_provenance.py"

spec = importlib.util.spec_from_file_location("mv3_summary_audit", AUDITOR_PATH)
assert spec and spec.loader
mv3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mv3)


def paths() -> tuple[Path, Path, Path]:
    return (
        ROOT / "docs/claim_ledger.csv",
        ROOT / "reports/mv3_stopping_v3_1782679272/REPORT.md",
        ROOT / "reports/mv3_stopping_v3_1782679272/mv3_summary.json",
    )


def mutate_ledger(tmp_path: Path, claim_id: str, field: str, value: str) -> Path:
    ledger, _, _ = paths()
    rows = list(csv.reader(io.StringIO(ledger.read_text(encoding="utf-8"))))
    index = {name: pos for pos, name in enumerate(rows[0])}
    for row in rows[1:]:
        if row[0] == claim_id:
            row[index[field]] = value
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\n").writerows(rows)
    path = tmp_path / "claim_ledger.csv"
    path.write_text(out.getvalue(), encoding="utf-8")
    return path


def test_exact_current_ledger_validates_against_tracked_summary() -> None:
    result = mv3.audit(*paths())
    assert result["status"] == "VALIDATED"
    assert result["n_issues"] == 0
    contract = result["source_contract"]
    assert contract["mc_counts"]["B8"] == 55619
    assert contract["data_counts"]["B8"] == 7051
    assert contract["reconstructed_chi2"] == contract["stated_chi2"]
    assert contract["reconstructed_chi2_per_ndf"] == contract["stated_chi2_per_ndf"]


def test_rounded_ledger_regression_is_detected(tmp_path: Path) -> None:
    ledger = mutate_ledger(tmp_path, "CL-019", "current_value", "0.223")
    _, report, summary = paths()
    result = mv3.audit(ledger, report, summary)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "LEDGER_CURRENT_VALUE" for issue in result["issues"])


def test_mutated_summary_chi2_is_detected(tmp_path: Path) -> None:
    ledger, report, summary_path = paths()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["chi2_mc_vs_data_all"] += 1.0
    altered = tmp_path / "mv3_summary.json"
    altered.write_text(json.dumps(payload), encoding="utf-8")
    result = mv3.audit(ledger, report, altered)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "SUMMARY_CHI2_MISMATCH" for issue in result["issues"])


def test_count_fraction_mismatch_is_detected(tmp_path: Path) -> None:
    ledger, report, summary_path = paths()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["mc"]["fractions"]["B8"] = 0.223
    altered = tmp_path / "mv3_summary.json"
    altered.write_text(json.dumps(payload), encoding="utf-8")
    result = mv3.audit(ledger, report, altered)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "SUMMARY_MC_FRACTION" for issue in result["issues"])


def test_cli_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    _, report, summary = paths()
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe")
    completed = subprocess.run(
        [sys.executable, str(AUDITOR_PATH), str(bad), str(report), str(summary)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "INPUT ERROR" in completed.stderr
