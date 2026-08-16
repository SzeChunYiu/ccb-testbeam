from __future__ import annotations

import csv
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
        "1,10,0,10\n"
        "2,5,0,5\n"
    )


def write_simulation(path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
        )
        writer.writerow(["proton", "1.01", "1.0", "1.0"])
        writer.writerow(["proton", "1.04", "1.0", "1.0"])


def test_aggregate_keeps_distinct_configured_energies_separate():
    module = load_module()
    rows = [
        ("proton", 1.01, 1.0, 1.0),
        ("proton", 1.04, 1.0, 1.0),
    ]
    results = module.aggregate(rows, rho=1.0)
    assert [row["energy_MeV"] for row in results] == [1.01, 1.04]
    assert [row["n_events"] for row in results] == [1, 1]
    assert {row["energy_grouping"] for row in results} == {
        "EXACT_CONFIGURED_ENERGY"
    }


def test_identical_numeric_energy_tokens_still_group_together(tmp_path):
    module = load_module()
    simulation = tmp_path / "events.csv"
    with simulation.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
        )
        writer.writerow(["proton", "1.0", "1.0", "1.0"])
        writer.writerow(["proton", "1.00", "1.0", "1.0"])
    rows, basis = module.read_sim(simulation)
    results = module.aggregate(rows, rho=1.0, energy_deposit_basis=basis)
    assert len(results) == 1
    assert results[0]["energy_MeV"] == 1.0
    assert results[0]["n_events"] == 2


def test_cli_writes_one_row_per_exact_energy_but_remains_nonaccepting(tmp_path):
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "events.csv"
    output = tmp_path / "result.csv"
    write_reference(reference)
    write_simulation(simulation)

    process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sim",
            str(simulation),
            "--reference",
            str(reference),
            "--material-density",
            "1.0",
            "--tolerance-pct",
            "1000",
            "--out",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 1, process.stderr
    rows = list(csv.DictReader(output.open()))
    assert [float(row["energy_MeV"]) for row in rows] == pytest.approx([1.01, 1.04])
    assert [int(row["n_events"]) for row in rows] == [1, 1]
    assert {row["energy_grouping"] for row in rows} == {
        "EXACT_CONFIGURED_ENERGY"
    }
    assert {row["uncertainty_method"] for row in rows} == {"NOT_EVALUATED"}
    assert {row["within_tolerance"] for row in rows} == {"False"}
    assert "ENERGY GROUPING: EXACT_CONFIGURED_ENERGY" in process.stdout
    assert "NUMERICAL TOLERANCE: PASS" not in process.stdout
