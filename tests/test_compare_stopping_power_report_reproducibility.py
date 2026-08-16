from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "single_stave" / "compare_stopping_power.py"
SPEC = importlib.util.spec_from_file_location("compare_stopping_power", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _reference_summary() -> dict[str, object]:
    return {
        "input_sha256": "a" * 64,
        "input_bytes": 123,
        "rows_validated": 2,
        "tool_version": "test-pstar",
        "component_identity": "total = electronic + nuclear",
        "all_rows_component_consistent": True,
    }


def _simulation_summary(n_rows: int) -> dict[str, object]:
    return {
        "input_sha256": "b" * 64,
        "input_bytes": 456,
        "rows_validated": n_rows,
        "tool_version": "test-sim",
        "energy_deposit_basis": MODULE.RAW_BASIS,
    }


def test_report_contains_sufficient_statistics_and_configuration(
    tmp_path, monkeypatch
) -> None:
    rows = [
        ("proton", 1.0, 0.4, 2.0),
        ("proton", 1.0, 0.8, 3.0),
    ]
    reference = [(0.1, 0.0, 0.0, 2.0), (10.0, 0.0, 0.0, 2.0)]
    monkeypatch.setattr(
        MODULE,
        "_read_reference_with_summary",
        lambda _path: (reference, _reference_summary()),
    )
    monkeypatch.setattr(
        MODULE,
        "_read_sim_with_summary",
        lambda _path, _allow=False: (rows, _simulation_summary(len(rows))),
    )
    output = tmp_path / "comparison.csv"
    rho = 1.23456789
    tolerance = 2.3456789

    results, accepted = MODULE.run_compare(
        tmp_path / "sim.csv",
        tmp_path / "reference.csv",
        rho=rho,
        out_path=output,
        tol_pct=tolerance,
    )

    assert accepted is False
    assert len(results) == 1
    result = results[0]
    assert result["deposit_sum_MeV"] == pytest.approx(1.2)
    assert result["track_length_sum_mm"] == 5.0
    assert result["material_density_g_cm3"] == rho
    assert result["tolerance_percent"] == tolerance
    assert result["mass_stopping_estimator"] == MODULE.MASS_STOPPING_ESTIMATOR
    reconstructed = (
        float(result["deposit_sum_MeV"])
        / float(result["track_length_sum_mm"])
        * 10.0
        / float(result["material_density_g_cm3"])
    )
    assert reconstructed == float(result["sim_total_MeV_cm2_g"])
    assert bool(result["numeric_within_tolerance"]) == (
        abs(float(result["delta_percent"])) <= float(result["tolerance_percent"])
    )

    with output.open(newline="") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 1
    row = written[0]
    for key in (
        "deposit_sum_MeV",
        "track_length_sum_mm",
        "material_density_g_cm3",
        "tolerance_percent",
    ):
        assert float(row[key]) == float(result[key])
    assert row["mass_stopping_estimator"] == MODULE.MASS_STOPPING_ESTIMATOR


def test_density_and_tolerance_are_not_implicit(monkeypatch, tmp_path) -> None:
    rows = [("proton", 1.0, 1.0, 1.0)]
    reference = [(0.1, 0.0, 0.0, 10.0), (10.0, 0.0, 0.0, 10.0)]
    monkeypatch.setattr(
        MODULE,
        "_read_reference_with_summary",
        lambda _path: (reference, _reference_summary()),
    )
    monkeypatch.setattr(
        MODULE,
        "_read_sim_with_summary",
        lambda _path, _allow=False: (rows, _simulation_summary(1)),
    )

    first, _ = MODULE.run_compare(
        tmp_path / "sim.csv",
        tmp_path / "reference.csv",
        rho=1.0,
        out_path=None,
        tol_pct=1.0,
    )
    second, _ = MODULE.run_compare(
        tmp_path / "sim.csv",
        tmp_path / "reference.csv",
        rho=2.0,
        out_path=None,
        tol_pct=60.0,
    )

    assert first[0]["sim_total_MeV_cm2_g"] == 10.0
    assert second[0]["sim_total_MeV_cm2_g"] == 5.0
    assert first[0]["material_density_g_cm3"] == 1.0
    assert second[0]["material_density_g_cm3"] == 2.0
    assert first[0]["numeric_within_tolerance"] is True
    assert second[0]["numeric_within_tolerance"] is True
    assert first[0]["tolerance_percent"] == 1.0
    assert second[0]["tolerance_percent"] == 60.0
