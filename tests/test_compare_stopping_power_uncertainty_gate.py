from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

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
        "1,9,1,10\n"
        "200,1,0,1\n"
    )


def write_simulation(path: Path, n_events: int = 1) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
        )
        for _ in range(n_events):
            writer.writerow(["proton", 1.0, 1.0, 1.0])


def test_direct_proton_point_estimate_cannot_authorize_acceptance(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "events.csv"
    output = tmp_path / "result.csv"
    write_reference(reference)
    write_simulation(simulation)

    results, ok = module.run_compare(
        simulation,
        reference,
        1.0,
        output,
        1e-9,
    )

    assert ok is False
    assert len(results) == 1
    result = results[0]
    assert result["ratio"] == 1.0
    assert result["numeric_within_tolerance"] is True
    assert result["physics_comparable"] is True
    assert result["uncertainty_method"] == "NOT_EVALUATED"
    assert result["uncertainty_evaluated"] is False
    assert result["pstar_primary_identity_ok"] is False
    assert result["acceptance_status"] == "NONCOMPARABLE_EVENT_TOTAL_TRACK_SCOPE"
    assert result["within_tolerance"] is False

    row = next(csv.DictReader(output.open()))
    assert row["uncertainty_method"] == "NOT_EVALUATED"
    assert row["uncertainty_evaluated"] == "False"
    assert row["pstar_primary_identity_ok"] == "False"
    assert row["acceptance_status"] == "NONCOMPARABLE_EVENT_TOTAL_TRACK_SCOPE"
    assert row["within_tolerance"] == "False"


def test_cli_never_prints_pass_for_point_estimate_only(tmp_path):
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
            "0.000001",
            "--out",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 1
    assert "POINT_ONLY" in process.stdout
    assert "NUMERICAL TOLERANCE: POINT_ESTIMATE_ONLY_NOT_ACCEPTED" in process.stdout
    assert "TRACK LENGTH SCOPE: EVENT_TOTAL_ALL_NON_OPTICAL" in process.stdout
    assert "PSTAR PRIMARY IDENTITY OK: False" in process.stdout
    assert "UNCERTAINTY EVALUATION: NOT_EVALUATED" in process.stdout
    assert "NUMERICAL TOLERANCE: PASS" not in process.stdout
    assert output.is_file()


def test_repeated_identical_events_do_not_substitute_for_uncertainty_model(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "events.csv"
    write_reference(reference)
    write_simulation(simulation, n_events=40)

    results, ok = module.run_compare(simulation, reference, 1.0, None, 1e-9)

    assert ok is False
    assert results[0]["n_events"] == 40
    assert results[0]["numeric_within_tolerance"] is True
    assert results[0]["uncertainty_evaluated"] is False
    assert results[0]["within_tolerance"] is False


def test_self_test_remains_arithmetic_only(tmp_path, capsys):
    module = load_module()
    reference = tmp_path / "reference.csv"
    write_reference(reference)

    assert module.self_test(reference) == 0
    captured = capsys.readouterr()
    assert "NUMERICAL TOLERANCE: POINT_ESTIMATE_ONLY_NOT_ACCEPTED" in captured.out
    assert "UNCERTAINTY EVALUATION: NOT_EVALUATED" in captured.out
    assert "SELF-TEST SCOPE: arithmetic and committed-reference path only" in captured.out
    assert "SELF-TEST: PASS" in captured.out
