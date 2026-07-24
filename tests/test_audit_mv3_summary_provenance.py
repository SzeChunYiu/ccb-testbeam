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


def _corrected_ledger(tmp_path: Path) -> Path:
    ledger, _, summary_path = paths()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = list(csv.reader(io.StringIO(ledger.read_text(encoding="utf-8"))))
    index = {name: pos for pos, name in enumerate(rows[0])}
    updates = {
        "CL-019": {
            "current_value": repr(summary["mc"]["fractions"]["B8"]),
            "numerator": str(summary["mc"]["counts"]["B8"]),
            "denominator": str(summary["mc"]["n_above_threshold"]),
            "source_data": mv3.SUMMARY_PATH,
            "ci_method": "fixed_exact_summary_count_fraction",
            "ci_status": "NOT_APPLICABLE_FIXED_EXACT_COUNTS_SYSTEMATICS_UNEVALUATED",
            "notes": (
                "The tracked summary records exact B8 counts 55619/249484 and the exact "
                "fraction. This fixed legacy thresholded-MC output has no accepted sampling "
                "or detector-systematics model and is not a production stopping-profile closure."
            ),
        },
        "CL-020": {
            "current_value": repr(summary["data"]["all"]["fractions"]["B8"]),
            "numerator": str(summary["data"]["all"]["counts"]["B8"]),
            "denominator": str(summary["data"]["all"]["n_events"]),
            "source_data": mv3.SUMMARY_PATH,
            "ci_method": "fixed_exact_summary_count_fraction",
            "ci_status": "NOT_APPLICABLE_FIXED_EXACT_COUNTS_SYSTEMATICS_UNEVALUATED",
            "notes": (
                "The tracked summary records exact B8 counts 7051/306745 and the exact "
                "fraction. This fixed selected-data output has no accepted selection or "
                "detector-systematics model and is not a production stopping-profile closure."
            ),
        },
        "CL-021": {
            "current_value": repr(summary["chi2_per_ndf"]),
            "source_data": mv3.SUMMARY_PATH,
            "ci_method": "pearson_chi2_from_data_counts_vs_mc_fraction_expected_counts",
            "ci_status": "NOT_APPLICABLE_FIXED_PEARSON_CHI2_SYSTEMATICS_UNEVALUATED",
            "notes": (
                "The tracked summary records Pearson chi2 204808.2179684494 with 3 degrees "
                "of freedom, giving chi2/ndf 68269.40598948313 from exact data counts and MC "
                "fraction expected counts. The calculation is reproducible but remains a "
                "flawed legacy diagnostic, not a calibrated goodness-of-fit, because geometry, "
                "selection transfer, covariance, and detector systematics are unresolved."
            ),
        },
    }
    for row in rows[1:]:
        if row and row[0] in updates:
            for field, value in updates[row[0]].items():
                row[index[field]] = value
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\n").writerows(rows)
    path = tmp_path / "corrected.csv"
    path.write_text(out.getvalue(), encoding="utf-8")
    return path


def test_current_ledger_is_flagged_against_tracked_summary() -> None:
    result = mv3.audit(*paths())
    assert result["status"] == "FLAWED"
    codes = {issue["code"] for issue in result["issues"]}
    assert "LEDGER_NUMERATOR" in codes
    assert "LEDGER_SOURCE_DATA" in codes
    assert "LEDGER_DENIES_TRACKED_SUMMARY" in codes
    contract = result["source_contract"]
    assert contract["reconstructed_chi2"] == contract["stated_chi2"]
    assert contract["reconstructed_chi2_per_ndf"] == contract["stated_chi2_per_ndf"]


def test_corrected_contract_validates(tmp_path: Path) -> None:
    ledger = _corrected_ledger(tmp_path)
    _, report, summary = paths()
    result = mv3.audit(ledger, report, summary)
    assert result["status"] == "VALIDATED"
    assert result["n_issues"] == 0


def test_mutated_summary_chi2_is_detected(tmp_path: Path) -> None:
    ledger = _corrected_ledger(tmp_path)
    _, report, summary_path = paths()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["chi2_mc_vs_data_all"] += 1.0
    bad_summary = tmp_path / "bad_summary.json"
    bad_summary.write_text(json.dumps(payload), encoding="utf-8")
    result = mv3.audit(ledger, report, bad_summary)
    assert result["status"] == "FLAWED"
    assert any(issue["code"] == "SUMMARY_CHI2_MISMATCH" for issue in result["issues"])


def test_count_fraction_mismatch_is_detected(tmp_path: Path) -> None:
    ledger = _corrected_ledger(tmp_path)
    _, report, summary_path = paths()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["mc"]["fractions"]["B8"] = 0.223
    bad_summary = tmp_path / "bad_fraction.json"
    bad_summary.write_text(json.dumps(payload), encoding="utf-8")
    result = mv3.audit(ledger, report, bad_summary)
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
