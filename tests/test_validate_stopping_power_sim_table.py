from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
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


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def valid_header() -> list[str]:
    return ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]


def test_valid_raw_table_records_exact_provenance(tmp_path):
    module = load_module()
    path = tmp_path / "events.csv"
    write_csv(path, valid_header(), [["proton", 10, 2.5, 4], ["d", 20, 3.0, 5]])

    result = module.validate_simulation_table(path)

    assert result["status"] == "VALIDATED"
    assert result["primary_stopping_authorising"] is False
    assert result["estimator_id"] == "all_particle_edep_over_path_diagnostic_v1"
    assert result["rows_validated"] == 2
    assert result["particle_counts"] == {"deuteron": 1, "proton": 1}
    assert result["energy_deposit_basis"] == "UNQUENCHED_RAW"
    assert result["raw_pstar_comparable"] is True
    assert result["input_bytes"] == path.stat().st_size
    assert result["input_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (["", 10, 1, 1], "no particle value"),
        (["photon", 10, 1, 1], "unsupported particle"),
        (["proton", "", 1, 1], "no energy value"),
        (["proton", "nan", 1, 1], "nonfinite energy"),
        (["proton", 0, 1, 1], "nonpositive energy"),
        (["proton", 10, "", 1], "no energy-deposit value"),
        (["proton", 10, "inf", 1], "nonfinite energy deposit"),
        (["proton", 10, -1, 1], "negative energy deposit"),
        (["proton", 10, 1, ""], "no track length value"),
        (["proton", 10, 1, 0], "nonpositive track length"),
    ],
)
def test_invalid_rows_fail_closed(tmp_path, row, message):
    module = load_module()
    path = tmp_path / "events.csv"
    write_csv(path, valid_header(), [row])

    with pytest.raises(module.SimulationTableError, match=message):
        module.validate_simulation_table(path)


def test_multiple_aliases_are_rejected(tmp_path):
    module = load_module()
    path = tmp_path / "events.csv"
    write_csv(
        path,
        [
            "particle",
            "ke_MeV",
            "energy_MeV",
            "edep_scint_raw_MeV",
            "track_len_scint_mm",
        ],
        [["proton", 10, 10, 1, 1]],
    )

    with pytest.raises(module.SimulationTableError, match="ambiguous energy aliases"):
        module.validate_simulation_table(path)


def test_same_row_raw_and_quenched_fields_are_rejected(tmp_path):
    module = load_module()
    path = tmp_path / "events.csv"
    write_csv(
        path,
        [
            "particle",
            "ke_MeV",
            "edep_scint_raw_MeV",
            "edep_scint_MeV",
            "track_len_scint_mm",
        ],
        [["proton", 10, 1, 0.8, 1]],
    )

    with pytest.raises(module.SimulationTableError, match="raw and quenched"):
        module.validate_simulation_table(path, allow_quenched_proxy=True)


def test_mixed_row_bases_are_rejected(tmp_path):
    module = load_module()
    path = tmp_path / "events.csv"
    write_csv(
        path,
        [
            "particle",
            "ke_MeV",
            "edep_scint_raw_MeV",
            "edep_scint_MeV",
            "track_len_scint_mm",
        ],
        [["proton", 10, 1, "", 1], ["proton", 10, "", 0.8, 1]],
    )

    with pytest.raises(module.SimulationTableError, match="mixes unquenched and quenched"):
        module.validate_simulation_table(path, allow_quenched_proxy=True)


def test_quenched_proxy_is_labelled_and_nonaccepting(tmp_path):
    module = load_module()
    path = tmp_path / "events.csv"
    write_csv(
        path,
        ["particle", "ke_MeV", "edep_scint_MeV", "track_len_scint_mm"],
        [["proton", 10, 0.8, 1]],
    )

    with pytest.raises(module.SimulationTableError, match="provides only quenched"):
        module.validate_simulation_table(path)

    result = module.validate_simulation_table(path, allow_quenched_proxy=True)
    assert result["status"] == "DIAGNOSTIC_ONLY"
    assert result["raw_pstar_comparable"] is False

    output = tmp_path / "result.json"
    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(path),
            "--allow-quenched-proxy",
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 1
    assert json.loads(output.read_text())["status"] == "DIAGNOSTIC_ONLY"


def test_cli_rejects_malformed_middle_row_without_success_output(tmp_path):
    path = tmp_path / "events.csv"
    output = tmp_path / "result.json"
    write_csv(
        path,
        valid_header(),
        [["proton", 10, 1, 1], ["proton", "", 1, 1], ["proton", 10, 1, 1]],
    )

    process = subprocess.run(
        [sys.executable, str(SCRIPT), str(path), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 2
    assert "line 3 has no energy value" in process.stderr
    assert "status=VALIDATED" not in process.stdout
    assert not output.exists()


def test_cm_track_length_is_supported_and_converted_for_validation(tmp_path):
    module = load_module()
    path = tmp_path / "events.csv"
    write_csv(
        path,
        ["particle", "energy_MeV", "edep_raw_MeV", "track_length_scint_cm"],
        [["p", 5, 1, 0.25]],
    )

    result = module.validate_simulation_table(path)
    assert result["rows_validated"] == 1
    assert result["energy_min_MeV"] == 5
