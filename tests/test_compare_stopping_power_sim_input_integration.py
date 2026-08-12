from __future__ import annotations

import csv
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "single_stave" / "compare_stopping_power.py"


def load_module():
    spec = importlib.util.spec_from_file_location("compare_stopping_power", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_reference(path: Path) -> None:
    path.write_text(
        "energy_MeV,electronic_MeV_cm2_g,nuclear_MeV_cm2_g,total_MeV_cm2_g\n"
        "1,10,0,10\n10,1,0,1\n"
    )


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def test_compare_reader_rejects_missing_middle_row(tmp_path):
    module = load_module()
    simulation = tmp_path / "events.csv"
    write_csv(
        simulation,
        ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"],
        [["proton", 2, 0.5, 1], ["proton", "", 0.5, 1], ["proton", 2, 0.5, 1]],
    )
    with pytest.raises(module.StoppingPowerInputError, match=r"line 3.*no energy value"):
        module.read_sim(simulation)


def test_compare_reader_rejects_ambiguous_aliases(tmp_path):
    module = load_module()
    simulation = tmp_path / "events.csv"
    write_csv(
        simulation,
        ["particle", "ke_MeV", "energy_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"],
        [["proton", 2, 2, 0.5, 1]],
    )
    with pytest.raises(module.StoppingPowerInputError, match="ambiguous energy aliases"):
        module.read_sim(simulation)


def test_cli_rejects_bad_sim_without_numerical_pass(tmp_path):
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "events.csv"
    write_reference(reference)
    write_csv(
        simulation,
        ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"],
        [["proton", 2, 0.5, 1], ["proton", "", 0.5, 1]],
    )
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--sim", str(simulation), "--reference", str(reference)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 2
    assert "line 3 has no energy value" in process.stderr
    assert "NUMERICAL TOLERANCE: PASS" not in process.stdout


def test_valid_comparison_records_shared_validator_provenance(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "events.csv"
    output = tmp_path / "result.csv"
    write_reference(reference)
    write_csv(
        simulation,
        ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"],
        [["p", 2, 0.5, 1], ["proton", 2, 0.5, 1]],
    )
    results, _ = module.run_compare(simulation, reference, 1.0, output, 100.0)
    result = results[0]
    assert result["particle"] == "proton"
    assert result["n_events"] == 2
    assert result["simulation_rows_validated"] == 2
    assert result["simulation_input_bytes"] == simulation.stat().st_size
    assert result["simulation_input_sha256"] == hashlib.sha256(simulation.read_bytes()).hexdigest()
    assert result["simulation_validator_version"] == "1.3.0-waveC-lane05"  # sim-table TOOL_VERSION bumped
    header = output.read_text().splitlines()[0]
    assert "simulation_input_sha256" in header
    assert "simulation_rows_validated" in header
