from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "single_stave" / "compare_stopping_power.py"
REFERENCE_HEADER = (
    "energy_MeV,electronic_MeV_cm2_g,nuclear_MeV_cm2_g,"
    "total_MeV_cm2_g\n"
)


def load_module():
    spec = importlib.util.spec_from_file_location("compare_stopping_power", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_reference(path: Path) -> None:
    path.write_text(REFERENCE_HEADER + "1,9,1,10\n2,4,1,5\n")


def write_sim(path: Path, fieldnames: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)


def run_cli(sim: Path, reference: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sim",
            str(sim),
            "--reference",
            str(reference),
            "--material-density",
            "1.0",
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_quenched_only_input_is_rejected_by_default(tmp_path):
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    write_reference(reference)
    write_sim(
        simulation,
        ["particle", "ke_MeV", "edep_scint_MeV", "track_len_scint_mm"],
        [["proton", 1.0, 1.0, 1.0]],
    )
    process = run_cli(simulation, reference)
    assert process.returncode == 2
    assert "provides only quenched energy deposit" in process.stderr
    assert "NUMERICAL TOLERANCE: PASS" not in process.stdout


def test_explicit_quenched_proxy_is_labelled_and_nonaccepting(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    output = tmp_path / "result.csv"
    write_reference(reference)
    write_sim(
        simulation,
        ["particle", "ke_MeV", "edep_scint_MeV", "track_len_scint_mm"],
        [["proton", 1.0, 1.0, 1.0]],
    )
    results, ok = module.run_compare(
        simulation,
        reference,
        1.0,
        output,
        1e-9,
        allow_quenched_proxy=True,
    )
    assert ok is False
    assert results[0]["energy_deposit_basis"] == "QUENCHED_PROXY"
    assert results[0]["raw_pstar_comparable"] is False
    assert results[0]["numeric_within_tolerance"] is True
    assert results[0]["uncertainty_evaluated"] is False
    assert results[0]["within_tolerance"] is False
    row = next(csv.DictReader(output.open()))
    assert row["energy_deposit_basis"] == "QUENCHED_PROXY"
    assert row["raw_pstar_comparable"] == "False"
    assert row["numeric_within_tolerance"] == "True"
    assert row["within_tolerance"] == "False"
    process = run_cli(
        simulation,
        reference,
        "--allow-quenched-proxy",
        "--out",
        str(tmp_path / "cli.csv"),
    )
    assert process.returncode == 1
    assert "ENERGY DEPOSIT BASIS: QUENCHED_PROXY" in process.stdout
    assert "NUMERICAL TOLERANCE: NOT_ACCEPTED_QUENCHED_PROXY" in process.stdout
    assert "NUMERICAL TOLERANCE: PASS" not in process.stdout


def test_mixed_raw_and_quenched_rows_are_rejected_even_when_opted_in(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    write_reference(reference)
    write_sim(
        simulation,
        [
            "particle",
            "ke_MeV",
            "edep_scint_raw_MeV",
            "edep_scint_MeV",
            "track_len_scint_mm",
        ],
        [
            ["proton", 1.0, 1.0, "", 1.0],
            ["proton", 1.0, "", 1.0, 1.0],
        ],
    )
    with pytest.raises(module.StoppingPowerInputError, match="mixes unquenched and quenched"):
        module.run_compare(
            simulation,
            reference,
            1.0,
            None,
            1e-9,
            allow_quenched_proxy=True,
        )


def test_raw_input_is_point_estimate_only_and_nonaccepting(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    write_reference(reference)
    write_sim(
        simulation,
        ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"],
        [["proton", 1.0, 1.0, 1.0]],
    )
    results, ok = module.run_compare(simulation, reference, 1.0, None, 1e-9)
    assert ok is False
    assert results[0]["energy_deposit_basis"] == "UNQUENCHED_RAW"
    assert results[0]["raw_pstar_comparable"] is True
    assert results[0]["numeric_within_tolerance"] is True
    assert results[0]["uncertainty_evaluated"] is False
    assert results[0]["pstar_primary_identity_ok"] is False
    assert results[0]["acceptance_status"] == "NONCOMPARABLE_EVENT_TOTAL_TRACK_SCOPE"
    assert results[0]["within_tolerance"] is False
