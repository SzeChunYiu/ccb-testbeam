from __future__ import annotations

import csv
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "audit" / "validate_stopping_power_sim_table.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_stopping_power_sim_table", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def csv_bytes(rows: list[list[object]]) -> bytes:
    import io

    handle = io.StringIO(newline="")
    writer = csv.writer(handle)
    writer.writerow(
        ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
    )
    writer.writerows(rows)
    return handle.getvalue().encode()


def test_rows_and_provenance_share_one_exact_byte_snapshot(tmp_path, monkeypatch):
    module = load_module()
    path = tmp_path / "events.csv"
    original_bytes = csv_bytes([["proton", 10, 1.25, 2]])
    mutated_bytes = csv_bytes([["proton", 20, 9.5, 7]])
    path.write_bytes(original_bytes)

    original_read_data_lines = module._read_data_lines

    def mutate_after_snapshot(*args):
        data_lines = original_read_data_lines(*args)
        path.write_bytes(mutated_bytes)
        return data_lines

    monkeypatch.setattr(module, "_read_data_lines", mutate_after_snapshot)
    rows, summary = module.read_validated_simulation_table(path)

    assert rows == [("proton", 10.0, 1.25, 2.0)]
    assert summary["input_bytes"] == len(original_bytes)
    assert summary["input_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert summary["input_snapshot_method"] == "SINGLE_READ_EXACT_BYTES"
    assert path.read_bytes() == mutated_bytes
    assert summary["input_sha256"] != hashlib.sha256(mutated_bytes).hexdigest()


def test_invalid_utf8_fails_as_controlled_input_error(tmp_path):
    module = load_module()
    path = tmp_path / "events.csv"
    path.write_bytes(b"particle,ke_MeV,edep_scint_raw_MeV,track_len_scint_mm\n\xff")

    with pytest.raises(module.SimulationTableError, match="not valid UTF-8"):
        module.validate_simulation_table(path)

    process = subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 2
    assert "not valid UTF-8" in process.stderr
    assert "Traceback" not in process.stderr
    assert "status=VALIDATED" not in process.stdout
