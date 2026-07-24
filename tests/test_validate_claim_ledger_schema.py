from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools/audit/validate_claim_ledger_schema.py"
SPEC = importlib.util.spec_from_file_location("validate_claim_ledger_schema", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def canonical_row(claim_id: str) -> list[str]:
    row = [""] * len(MODULE.EXPECTED_FIELDS)
    row[0] = claim_id
    row[1] = "Timing"
    row[2] = "4"
    row[3] = "Synthetic claim"
    row[27] = "data_only"
    row[28] = "VALIDATED"
    row[29] = "YES"
    return row


def write_rows(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(MODULE.EXPECTED_FIELDS)
        writer.writerows(rows)


def test_exact_canonical_rows_validate(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    write_rows(ledger, [canonical_row("CL-001"), canonical_row("CL-002")])

    result = MODULE.audit(ledger)

    assert result["status"] == "VALIDATED"
    assert result["data_rows"] == 2
    assert result["exact_width_rows"] == 2
    assert result["width_mismatch_rows"] == 0
    assert result["exact_width_claim_ids"] == ["CL-001", "CL-002"]
    assert result["issues"] == []


def test_short_row_is_not_interpreted_as_canonical_fields(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    write_rows(ledger, [canonical_row("CL-001")[:-5]])

    result = MODULE.audit(ledger)
    issue = result["issues"][0]

    assert result["status"] == "FLAWED"
    assert result["width_mismatch_rows"] == 1
    assert issue["code"] == "ROW_WIDTH_MISMATCH"
    assert issue["actual_columns"] == 38
    assert issue["missing_columns"] == 5
    assert issue["field_interpretation"] == "WITHHELD"
    assert "mapped_fields" not in issue


def test_missing_middle_field_would_shift_dictreader_but_is_withheld(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    shifted = canonical_row("CL-001")
    del shifted[27]
    write_rows(ledger, [shifted])

    unsafe_row = next(csv.DictReader(io.StringIO(ledger.read_text(encoding="utf-8"))))
    result = MODULE.audit(ledger)

    assert unsafe_row["truth_type"] == "VALIDATED"
    assert unsafe_row["status"] == "YES"
    assert result["status"] == "FLAWED"
    assert result["row_widths"][0]["field_interpretation"] == "WITHHELD"


def test_duplicate_claim_id_is_reported(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    write_rows(ledger, [canonical_row("CL-001"), canonical_row("CL-001")])

    result = MODULE.audit(ledger)

    assert result["status"] == "FLAWED"
    assert [issue["code"] for issue in result["issues"]] == [
        "DUPLICATE_CLAIM_ID"
    ]


def test_noncanonical_header_is_controlled_error(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    ledger.write_text("claim_id,status\nCL-001,VALIDATED\n", encoding="utf-8")

    with pytest.raises(MODULE.ClaimLedgerSchemaError, match="43-column"):
        MODULE.audit(ledger)


def test_malformed_csv_is_controlled_error(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    header = ",".join(MODULE.EXPECTED_FIELDS)
    ledger.write_text(header + '\nCL-001,"unterminated\n', encoding="utf-8")

    with pytest.raises(MODULE.ClaimLedgerSchemaError, match="invalid CSV"):
        MODULE.audit(ledger)


def test_cli_writes_machine_readable_flaw_record(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    output = tmp_path / "validation.json"
    write_rows(ledger, [canonical_row("CL-001")[:-1]])

    status = MODULE.main([str(ledger), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert status == 1
    assert payload["status"] == "FLAWED"
    assert payload["width_mismatch_rows"] == 1
    assert payload["policy"] == (
        "NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS"
    )


def test_cli_writes_accessible_svg(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    svg = tmp_path / "validation.svg"
    write_rows(ledger, [canonical_row("CL-001")[:-1]])

    status = MODULE.main([str(ledger), "--svg", str(svg)])
    text = svg.read_text(encoding="utf-8")

    assert status == 1
    assert "Claim-ledger row width audit" in text
    assert "expected 43" in text
    assert "MISMATCH" in text
    assert "physics values are not interpreted" in text


def test_invalid_utf8_returns_status_two(tmp_path: Path) -> None:
    ledger = tmp_path / "claim_ledger.csv"
    ledger.write_bytes(b"\xff")

    assert MODULE.main([str(ledger)]) == 2
