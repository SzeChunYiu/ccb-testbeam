from __future__ import annotations

import csv
import importlib.util
import io
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools/audit/validate_mv3_legacy_claim_rows.py"
RENDER_PATH = ROOT / "tools/audit/render_mv3_legacy_claim_evidence.py"

spec = importlib.util.spec_from_file_location("mv3_validator", VALIDATOR_PATH)
assert spec and spec.loader
mv3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mv3)


def paths() -> tuple[Path, Path, Path]:
    return (
        ROOT / "docs/claim_ledger.csv",
        ROOT / "reports/mv3_stopping_v3_1782679272/REPORT.md",
        ROOT / "src/ccb_mc_validation/studies/mv3_stopping_depth.py",
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


def test_exact_current_contract_validates() -> None:
    result = mv3.validate(*paths())
    assert result["status"] == "VALIDATED"
    assert result["n_issues"] == 0
    assert result["source_contract"]["data_fraction_sum"] == 1.001
    assert result["rounding_identifiability"]["mc_b8"]["possible_numerator_count"] == 249
    assert result["rounding_identifiability"]["data_b8"]["possible_numerator_count"] == 307


def test_old_width_mismatch_fails_closed() -> None:
    ledger, report, remediation = paths()
    result = mv3.validate(ROOT / "docs/claim_ledger.current.csv", report, remediation)
    assert result["status"] == "FLAWED"
    assert {issue["code"] for issue in result["issues"]} == {"ROW_WIDTH"}


def test_exact_numerator_is_rejected_when_source_omits_it(tmp_path: Path) -> None:
    ledger = mutate_ledger(tmp_path, "CL-019", "numerator", "55635")
    _, report, remediation = paths()
    result = mv3.validate(ledger, report, remediation)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "UNSUPPORTED_QUANTITATIVE_FIELD" for issue in result["issues"])


def test_chi2_label_mutation_is_detected(tmp_path: Path) -> None:
    ledger = mutate_ledger(tmp_path, "CL-021", "current_value", "68269")
    _, report, remediation = paths()
    result = mv3.validate(ledger, report, remediation)
    assert result["status"] == "FLAWED"
    assert any(issue["claim_id"] == "CL-021" for issue in result["issues"])


def test_report_mutation_is_detected(tmp_path: Path) -> None:
    ledger, report, remediation = paths()
    altered = tmp_path / "REPORT.md"
    altered.write_text(
        report.read_text(encoding="utf-8").replace("| B8 | 0.223", "| B8 | 0.224"),
        encoding="utf-8",
    )
    result = mv3.validate(ledger, altered, remediation)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "MC_B8" for issue in result["issues"])


def test_cli_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    _, report, remediation = paths()
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe")
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(bad), str(report), str(remediation)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "INPUT ERROR" in completed.stderr


def test_rendered_svg_is_well_formed(tmp_path: Path) -> None:
    validation = mv3.validate(*paths())
    json_path = tmp_path / "validation.json"
    svg_path = tmp_path / "evidence.svg"
    json_path.write_text(json.dumps(validation), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(RENDER_PATH), str(json_path), str(svg_path)],
        check=False,
    )
    assert completed.returncode == 0
    root = ET.parse(svg_path).getroot()
    assert root.tag.endswith("svg")
