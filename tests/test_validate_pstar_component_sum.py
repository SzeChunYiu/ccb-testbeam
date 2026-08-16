from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "audit" / "validate_pstar_component_sum.py"
HEADER = (
    "energy_MeV,electronic_MeV_cm2_g,nuclear_MeV_cm2_g,"
    "total_MeV_cm2_g\n"
)


def load_module():
    spec = importlib.util.spec_from_file_location("validate_pstar_component_sum", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rounded_nist_style_rows_validate_with_exact_provenance(tmp_path):
    module = load_module()
    table = tmp_path / "pstar.csv"
    table.write_text(
        "# synthetic NIST-style rounding\n"
        + HEADER
        + "0.001,186,40.73,226.8\n"
        + "60,10.56,0.004425,10.57\n"
    )
    rows, result = module.read_validated_pstar_table(table)
    assert rows == [(0.001, 186.0, 40.73, 226.8), (60.0, 10.56, 0.004425, 10.57)]
    assert result["status"] == "VALIDATED"
    assert result["rows_validated"] == 2
    assert result["canonical_rows_returned"] == 2
    assert result["input_bytes"] == table.stat().st_size
    assert result["input_sha256"] == hashlib.sha256(table.read_bytes()).hexdigest()
    assert result["component_identity"] == "total = electronic + nuclear"
    assert result["all_rows_component_consistent"] is True


def test_scientific_notation_precision_is_respected(tmp_path):
    module = load_module()
    table = tmp_path / "pstar.csv"
    table.write_text(HEADER + "1e-3,1.00e2,2.0e1,1.20e2\n2e-3,9.0e1,1e1,1.0e2\n")
    assert module.validate_pstar_component_sum(table)["rows_validated"] == 2


def test_inconsistent_total_is_rejected_after_rounding_intervals(tmp_path):
    module = load_module()
    table = tmp_path / "pstar.csv"
    table.write_text(HEADER + "1,9,1,8\n2,4,1,5\n")
    with pytest.raises(module.PstarComponentError, match=r"line 2.*inconsistent"):
        module.validate_pstar_component_sum(table)


@pytest.mark.parametrize(
    "row, expected",
    [
        ("1,broken,1,10", "nonnumeric"),
        ("1,9,nan,10", "nonfinite"),
        ("1,-9,1,10", "nonphysical"),
    ],
)
def test_invalid_required_values_fail_closed(tmp_path, row, expected):
    module = load_module()
    table = tmp_path / "pstar.csv"
    table.write_text(HEADER + row + "\n2,4,1,5\n")
    with pytest.raises(module.PstarComponentError, match=expected):
        module.validate_pstar_component_sum(table)


def test_cli_failure_writes_no_json_and_prints_no_validated_status(tmp_path):
    table = tmp_path / "pstar.csv"
    output = tmp_path / "validation.json"
    table.write_text(HEADER + "1,9,1,8\n2,4,1,5\n")
    process = subprocess.run(
        [sys.executable, str(TOOL), str(table), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 2
    assert "inconsistent with electronic+nuclear" in process.stderr
    assert "status=VALIDATED" not in process.stdout
    assert not output.exists()


def test_cli_success_writes_machine_readable_validation(tmp_path):
    table = tmp_path / "pstar.csv"
    output = tmp_path / "validation.json"
    table.write_text(HEADER + "1,9,1,10\n2,4,1,5\n")
    process = subprocess.run(
        [sys.executable, str(TOOL), str(table), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0
    payload = json.loads(output.read_text())
    assert payload["status"] == "VALIDATED"
    assert payload["rows_validated"] == 2
    assert payload["tool_version"] == "1.1.0"
