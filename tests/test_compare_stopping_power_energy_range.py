from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "single_stave" / "compare_stopping_power.py"


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
        "10,1,0,1\n"
    )


def write_sim(path: Path, particle: str, energy: float, mass_stopping: float) -> None:
    density = 1.0
    edep_mev = mass_stopping * density / 10.0
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
        )
        writer.writerow([particle, energy, edep_mev, 1.0])


def test_interpolation_accepts_edges_but_rejects_extrapolation():
    module = load_module()
    table = [(1.0, 0.0, 0.0, 10.0), (10.0, 0.0, 0.0, 1.0)]

    assert module.interp_loglog(table, 1.0) == 10.0
    assert module.interp_loglog(table, 10.0) == 1.0
    with pytest.raises(module.StoppingPowerInputError, match="outside.*range"):
        module.interp_loglog(table, 0.5)
    with pytest.raises(module.StoppingPowerInputError, match="outside.*range"):
        module.interp_loglog(table, 20.0)


def test_deuteron_range_gate_uses_proton_equivalent_energy():
    module = load_module()
    table = [(1.0, 0.0, 0.0, 10.0), (10.0, 0.0, 0.0, 1.0)]

    with pytest.raises(
        module.StoppingPowerInputError,
        match=r"deuteron energy 1\.5 MeV maps.*0\.75 MeV.*outside",
    ):
        module.reference_for("deuteron", 1.5, table)


def test_cli_fails_instead_of_clamping_out_of_range_energy(tmp_path):
    ref = tmp_path / "reference.csv"
    sim = tmp_path / "sim.csv"
    write_reference(ref)
    write_sim(sim, "proton", 0.5, mass_stopping=10.0)

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--sim",
            str(sim),
            "--reference",
            str(ref),
            "--material-density",
            "1.0",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "outside the committed PSTAR range [1, 10] MeV" in proc.stderr
    assert "NUMERICAL TOLERANCE: PASS" not in proc.stdout


def test_deuteron_result_records_range_but_is_nonaccepting(tmp_path):
    module = load_module()
    ref = tmp_path / "reference.csv"
    sim = tmp_path / "sim.csv"
    out = tmp_path / "result.csv"
    write_reference(ref)
    write_sim(sim, "deuteron", 4.0, mass_stopping=5.0)

    results, ok = module.run_compare(
        sim,
        ref,
        1.0,
        out,
        1e-9,
        allow_deuteron_proxy=True,
    )

    assert ok is False
    assert len(results) == 1
    result = results[0]
    assert result["reference_lookup_energy_MeV"] == 2.0
    assert result["reference_range_min_MeV"] == 1.0
    assert result["reference_range_max_MeV"] == 10.0
    assert result["reference_in_range"] is True
    assert result["reference_basis"] == module.DEUTERON_REFERENCE_PROXY
    assert result["reference_direct_pstar_comparable"] is False
    assert result["physics_comparable"] is False
    assert result["numeric_within_tolerance"] is True
    assert result["within_tolerance"] is False
    header = out.read_text().splitlines()[0]
    assert "reference_lookup_energy_MeV" in header
    assert "reference_basis" in header
    assert "physics_comparable" in header
