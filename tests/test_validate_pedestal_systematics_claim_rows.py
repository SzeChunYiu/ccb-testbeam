from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audit.validate_pedestal_systematics_claim_rows import (
    ClaimRowValidationError,
    audit,
    validate_text,
)

HEADER = [
    "claim_id", "chapter", "section", "claim_text", "current_value", "unit",
    "stat_unc", "syst_unc", "total_unc", "ci_low", "ci_high", "ci_level",
    "ci_method", "bootstrap_unit", "n_events", "n_runs", "n_data", "n_mc",
    "numerator", "denominator", "p_value", "effect_size", "baseline_value",
    "baseline_unc", "delta_vs_baseline", "delta_ci_low", "delta_ci_high",
    "truth_type", "status", "allowed_status_validated", "source_report",
    "source_script", "source_data", "source_config", "source_manifest",
    "figure_ids", "table_ids", "source_commit", "link_validated", "ci_status",
    "blocked_by", "supersedes", "notes",
]

SOURCE = """No forced-trigger zero-signal events exist in the current dataset.
The total is shown as Total (add in quadrature).
This remains blocked until a forced-trigger S16 pedestal sample is acquired.
"""


def _row(claim_id: str) -> dict[str, str]:
    common = {
        "status": "BLOCKED",
        "allowed_status_validated": "NO",
        "source_report": "docs/SYSTEMATIC_UNCERTAINTIES.md",
        "source_commit": "779740b15c66842144fd191e304a28d7eb31bad5",
        "link_validated": "YES",
        "ci_status": "NOT_APPLICABLE_WITH_REASON",
    }
    if claim_id == "CL-025":
        return {
            "claim_id": claim_id,
            "chapter": "Pedestal",
            "section": "11",
            "claim_text": "Forced-trigger pedestal truth unavailable",
            "truth_type": "data_availability",
            "blocked_by": "BLK-PED-001",
            "notes": (
                "There are no forced-trigger zero-signal events. A fixed baseline is not an "
                "independently measured pedestal truth; no pedestal-truth number or uncertainty "
                "is authorized."
            ),
            **common,
        }
    return {
        "claim_id": claim_id,
        "chapter": "Systematics",
        "section": "11",
        "claim_text": "Systematic uncertainty propagation incomplete",
        "truth_type": "uncertainty_budget_incomplete",
        "blocked_by": "BLK-SYST-001",
        "notes": (
            "A claim-specific nuisance model, covariance treatment, and reproducible propagation "
            "code are missing; the inventory is not blanket authorization."
        ),
        **common,
    }


def _ledger(*, mutate: tuple[str, str, str] | None = None, width_delta: int = 0) -> str:
    rows = []
    for claim_id in ("CL-025", "CL-026"):
        values = _row(claim_id)
        if mutate and mutate[0] == claim_id:
            values[mutate[1]] = mutate[2]
        row = [values.get(field, "") for field in HEADER]
        if width_delta and claim_id == "CL-025":
            row = row[:width_delta]
        rows.append(row)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows)
    return stream.getvalue()


def test_valid_rows_and_source_pass() -> None:
    result = validate_text(_ledger(), SOURCE)
    assert result["status"] == "VALIDATED"
    assert result["n_issues"] == 0


def test_width_mismatch_fails_closed() -> None:
    with pytest.raises(ClaimRowValidationError, match="CL-025 has 42 columns"):
        validate_text(_ledger(width_delta=-1), SOURCE)


def test_blocked_row_cannot_publish_number() -> None:
    result = validate_text(_ledger(mutate=("CL-025", "current_value", "6752")), SOURCE)
    assert result["status"] == "FLAWED"
    assert result["issues"][0]["code"] == "BLOCKED_ROW_PUBLISHES_QUANTITATIVE_VALUE"


def test_missing_source_evidence_is_reported() -> None:
    result = validate_text(_ledger(), "Total (add in quadrature) only")
    codes = {issue["code"] for issue in result["issues"]}
    assert result["status"] == "FLAWED"
    assert "SOURCE_EVIDENCE_MISSING" in codes


def test_wrong_status_or_truth_type_is_reported() -> None:
    result = validate_text(_ledger(mutate=("CL-026", "status", "VALIDATED")), SOURCE)
    assert result["status"] == "FLAWED"
    assert any(issue.get("field") == "status" for issue in result["issues"])


def test_invalid_utf8_is_controlled(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    source = tmp_path / "source.md"
    ledger.write_bytes(b"\xff")
    source.write_text(SOURCE, encoding="utf-8")
    with pytest.raises(ClaimRowValidationError, match="not valid UTF-8"):
        audit(ledger, source)


def test_cli_writes_machine_readable_evidence(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.csv"
    source = tmp_path / "source.md"
    output = tmp_path / "result.json"
    svg = tmp_path / "result.svg"
    ledger.write_text(_ledger(), encoding="utf-8")
    source.write_text(SOURCE, encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "tools/audit/validate_pedestal_systematics_claim_rows.py",
            str(ledger),
            str(source),
            "--output",
            str(output),
            "--svg",
            str(svg),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "VALIDATED"
    assert "synthetic validation diagram" in svg.read_text(encoding="utf-8")
