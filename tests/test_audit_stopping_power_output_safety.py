from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.audit.audit_stopping_power_output_safety import (
    OutputSafetyAuditError,
    audit_source,
)


VULNERABLE = '''
def run_compare(sim_path, ref_path, out_path):
    read_sim(sim_path)
    read_reference(ref_path)
    if out_path is not None:
        with out_path.open("w", newline="") as handle:
            handle.write("report")
'''

FIXED = '''
import os

def _validate_output_path(out_path, sim_path, ref_path):
    if out_path.resolve() in {sim_path.resolve(), ref_path.resolve()}:
        raise ValueError("output aliases input")

def _write_report_atomically(out_path, rows):
    temporary = out_path.with_suffix(out_path.suffix + ".tmp")
    temporary.write_text("report", encoding="utf-8")
    os.replace(temporary, out_path)

def run_compare(sim_path, ref_path, out_path):
    _validate_output_path(out_path, sim_path, ref_path)
    _write_report_atomically(out_path, [])
'''


def write_source(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "compare_stopping_power.py"
    path.write_text(source, encoding="utf-8")
    return path


def test_vulnerable_direct_write_is_flawed(tmp_path: Path) -> None:
    result = audit_source(write_source(tmp_path, VULNERABLE))
    assert result["status"] == "FLAWED"
    assert result["direct_final_write"] is True
    assert result["output_alias_guard"] is False
    assert result["atomic_report_write"] is False
    assert result["findings"] == [
        "DIRECT_REPORT_WRITE_TO_FINAL_PATH",
        "OUTPUT_PATH_ALIAS_NOT_REJECTED",
        "REPORT_WRITE_NOT_ATOMIC",
    ]


def test_fixed_helper_contract_is_validated(tmp_path: Path) -> None:
    result = audit_source(write_source(tmp_path, FIXED))
    assert result["status"] == "VALIDATED"
    assert result["direct_final_write"] is False
    assert result["output_alias_guard"] is True
    assert result["atomic_report_write"] is True
    assert result["findings"] == []


def test_alias_guard_without_atomic_write_remains_flawed(tmp_path: Path) -> None:
    source = VULNERABLE.replace(
        "    read_sim(sim_path)\n",
        "    _validate_output_path(out_path, sim_path, ref_path)\n    read_sim(sim_path)\n",
    )
    result = audit_source(write_source(tmp_path, source))
    assert result["output_alias_guard"] is True
    assert "REPORT_WRITE_NOT_ATOMIC" in result["findings"]


def test_invalid_source_is_controlled(tmp_path: Path) -> None:
    path = tmp_path / "bad.py"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(OutputSafetyAuditError, match="valid UTF-8"):
        audit_source(path)


def test_cli_writes_machine_readable_flaw_record(tmp_path: Path) -> None:
    source_path = write_source(tmp_path, VULNERABLE)
    output_path = tmp_path / "audit.json"
    tool_path = (
        Path(__file__).parents[1]
        / "tools"
        / "audit"
        / "audit_stopping_power_output_safety.py"
    )
    completed = subprocess.run(
        [sys.executable, str(tool_path), str(source_path), "--output", str(output_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "status=FLAWED" in completed.stdout
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["policy"] == "NO_INPUT_OUTPUT_ALIAS_AND_ATOMIC_REPORT_WRITE"
    assert payload["status"] == "FLAWED"
