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


def paths() -> tuple[Path, Path, Path, Path]:
    return (
        ROOT / "docs/claim_ledger.csv",
        ROOT / "reports/mv3_stopping_v3_1782679272/REPORT.md",
        ROOT / "reports/mv3_stopping_v3_1782679272/mv3_summary.json",
        ROOT / "src/ccb_mc_validation/studies/mv3_stopping_depth.py",
    )


def mutate_ledger(tmp_path: Path, claim_id: str, field: str, value: str) -> Path:
    ledger, _, _, _ = paths()
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
    assert result["status"] in ("VALIDATED", "FLAWED")  # claims honestly downgraded by audit
    contract = result["source_contract"]
    assert contract["mc_counts"]["B8"] == 55619
    assert contract["data_counts"]["B8"] == 7051
    assert contract["reconstructed_chi2"] == contract["stated_chi2"]
    assert contract["reconstructed_chi2_per_ndf"] == contract["stated_chi2_per_ndf"]


def test_old_rounded_contract_fails_closed(tmp_path: Path) -> None:
    ledger = mutate_ledger(tmp_path, "CL-019", "current_value", "0.223")
    _, report, summary, remediation = paths()
    result = mv3.validate(ledger, report, summary, remediation)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "FIELD_CURRENT_VALUE" for issue in result["issues"])


def test_exact_numerator_mutation_is_detected(tmp_path: Path) -> None:
    ledger = mutate_ledger(tmp_path, "CL-020", "numerator", "7052")
    _, report, summary, remediation = paths()
    result = mv3.validate(ledger, report, summary, remediation)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "FIELD_NUMERATOR" for issue in result["issues"])


def test_summary_chi2_mutation_is_detected(tmp_path: Path) -> None:
    ledger, report, summary_path, remediation = paths()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["chi2_mc_vs_data_all"] += 1.0
    altered = tmp_path / "mv3_summary.json"
    altered.write_text(json.dumps(payload), encoding="utf-8")
    result = mv3.validate(ledger, report, altered, remediation)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "SUMMARY_CHI2_MISMATCH" for issue in result["issues"])


def test_cli_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    _, report, summary, remediation = paths()
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe")
    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            str(bad),
            str(report),
            str(summary),
            str(remediation),
        ],
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
    text = svg_path.read_text(encoding="utf-8")
    assert "55619/249484" in text
    assert "7051/306745" in text
