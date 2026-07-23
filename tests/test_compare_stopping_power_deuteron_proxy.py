from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

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


def write_sim(path: Path, rows: list[list[object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
        )
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
            "--tolerance-pct",
            "0.000001",
            *extra,
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_deuteron_proxy_is_rejected_by_default(tmp_path):
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    output = tmp_path / "result.csv"
    write_reference(reference)
    write_sim(simulation, [["deuteron", 2.0, 1.0, 1.0]])
    process = run_cli(simulation, reference, "--out", str(output))
    assert process.returncode == 2
    assert "unvalidated equal-velocity proxy" in process.stderr
    assert "--allow-deuteron-proxy" in process.stderr
    assert "NUMERICAL TOLERANCE: PASS" not in process.stdout
    assert not output.exists()


def test_explicit_deuteron_proxy_is_labelled_and_nonaccepting(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    output = tmp_path / "result.csv"
    write_reference(reference)
    write_sim(simulation, [["deuteron", 2.0, 1.0, 1.0]])
    results, ok = module.run_compare(
        simulation,
        reference,
        1.0,
        output,
        1e-9,
        allow_deuteron_proxy=True,
    )
    assert ok is False
    result = results[0]
    assert result["reference_lookup_energy_MeV"] == 1.0
    assert result["reference_basis"] == module.DEUTERON_REFERENCE_PROXY
    assert result["reference_direct_pstar_comparable"] is False
    assert result["raw_pstar_comparable"] is True
    assert result["physics_comparable"] is False
    assert result["numeric_within_tolerance"] is True
    assert result["uncertainty_evaluated"] is False
    assert result["within_tolerance"] is False
    row = next(csv.DictReader(output.open()))
    assert row["reference_basis"] == module.DEUTERON_REFERENCE_PROXY
    assert row["reference_direct_pstar_comparable"] == "False"
    assert row["physics_comparable"] == "False"
    assert row["numeric_within_tolerance"] == "True"
    assert row["within_tolerance"] == "False"
    process = run_cli(simulation, reference, "--allow-deuteron-proxy")
    assert process.returncode == 1
    assert "DEUTERON REFERENCE BASIS: VELOCITY_SCALED_PROTON_PROXY" in process.stdout
    assert "NUMERICAL TOLERANCE: NOT_ACCEPTED_DEUTERON_PROXY" in process.stdout
    assert "NUMERICAL TOLERANCE: PASS" not in process.stdout


def test_direct_proton_reference_is_point_estimate_only(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    write_reference(reference)
    write_sim(simulation, [["proton", 1.0, 1.0, 1.0]])
    results, ok = module.run_compare(simulation, reference, 1.0, None, 1e-9)
    assert ok is False
    result = results[0]
    assert result["reference_basis"] == module.DIRECT_PROTON_REFERENCE
    assert result["reference_direct_pstar_comparable"] is True
    assert result["physics_comparable"] is True
    assert result["numeric_within_tolerance"] is True
    assert result["uncertainty_evaluated"] is False
    assert result["within_tolerance"] is False


def test_mixed_proton_and_deuteron_result_is_nonaccepting(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    write_reference(reference)
    write_sim(
        simulation,
        [
            ["proton", 1.0, 1.0, 1.0],
            ["deuteron", 2.0, 1.0, 1.0],
        ],
    )
    results, ok = module.run_compare(
        simulation,
        reference,
        1.0,
        None,
        1e-9,
        allow_deuteron_proxy=True,
    )
    assert ok is False
    by_particle = {result["particle"]: result for result in results}
    assert by_particle["proton"]["numeric_within_tolerance"] is True
    assert by_particle["proton"]["within_tolerance"] is False
    assert by_particle["deuteron"]["numeric_within_tolerance"] is True
    assert by_particle["deuteron"]["within_tolerance"] is False
