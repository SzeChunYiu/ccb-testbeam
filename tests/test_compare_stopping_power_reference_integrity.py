from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "single_stave" / "compare_stopping_power.py"
HEADER = (
    "energy_MeV,electronic_MeV_cm2_g,nuclear_MeV_cm2_g,"
    "total_MeV_cm2_g\n"
)


def load_module():
    spec = importlib.util.spec_from_file_location("compare_stopping_power", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_sim(path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
        )
        writer.writerow(["proton", 1.0, 1.0, 1.0])


def test_valid_reference_preserves_declared_order_and_allows_extra_columns(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    reference.write_text(
        "# provenance\n"
        "energy_MeV,electronic_MeV_cm2_g,nuclear_MeV_cm2_g,"
        "total_MeV_cm2_g,extra\n"
        "1,9,1,10,a\n"
        "2,4,1,5,b\n"
    )

    assert module.read_reference(reference) == [
        (1.0, 9.0, 1.0, 10.0),
        (2.0, 4.0, 1.0, 5.0),
    ]


def test_malformed_middle_row_is_rejected_instead_of_silently_skipped(tmp_path):
    module = load_module()
    reference = tmp_path / "reference.csv"
    reference.write_text(HEADER + "1,9,1,10\n2,broken,1,5\n3,2,1,3\n")

    with pytest.raises(module.StoppingPowerInputError, match=r"line 3.*nonnumeric"):
        module.read_reference(reference)


@pytest.mark.parametrize(
    "rows, expected",
    [
        ("1,9,1,10\n1,4,1,5\n", "strictly greater"),
        ("2,9,1,10\n1,4,1,5\n", "strictly greater"),
        ("1,9,1,10\n2,4,1,nan\n", "nonfinite"),
        ("1,9,1,10\n2,-4,1,5\n", "nonphysical"),
    ],
)
def test_invalid_reference_values_and_order_fail_closed(tmp_path, rows, expected):
    module = load_module()
    reference = tmp_path / "reference.csv"
    reference.write_text(HEADER + rows)

    with pytest.raises(module.StoppingPowerInputError, match=expected):
        module.read_reference(reference)


def test_cli_returns_input_error_without_numerical_pass_for_bad_reference(tmp_path):
    reference = tmp_path / "reference.csv"
    simulation = tmp_path / "sim.csv"
    reference.write_text(HEADER + "1,9,1,10\n2,broken,1,5\n3,2,1,3\n")
    write_sim(simulation)

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
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 2
    assert "nonnumeric required value" in process.stderr
    assert "NUMERICAL TOLERANCE: PASS" not in process.stdout
