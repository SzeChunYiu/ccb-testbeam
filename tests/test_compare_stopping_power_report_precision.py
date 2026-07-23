from __future__ import annotations

import csv
import importlib.util
import math
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


def _simulation_summary() -> dict[str, object]:
    return {
        "input_sha256": "b" * 64,
        "input_bytes": 456,
        "rows_validated": 2,
        "tool_version": "test-sim",
        "energy_deposit_basis": MODULE.RAW_BASIS,
    }


def test_legacy_six_digit_format_collapses_distinct_energies() -> None:
    energies = [1.0000001, 1.0000002]
    assert energies[0] != energies[1]
    assert [format(value, ".6g") for value in energies] == ["1", "1"]


def test_report_csv_preserves_every_float_exactly(tmp_path, monkeypatch, capsys) -> None:
    energies = [1.0000001, 1.0000002]
    rows = [("proton", energy, 1.0, 1.0) for energy in energies]
    reference = [(0.1, 0.0, 0.0, 10.0), (10.0, 0.0, 0.0, 10.0)]
    monkeypatch.setattr(
        MODULE,
        "_read_reference_with_summary",
        lambda _path: (reference, _reference_summary()),
    )
    monkeypatch.setattr(
        MODULE,
        "_read_sim_with_summary",
        lambda _path, _allow=False: (rows, _simulation_summary()),
    )
    output = tmp_path / "comparison.csv"

    results, accepted = MODULE.run_compare(
        tmp_path / "sim.csv",
        tmp_path / "reference.csv",
        rho=1.0,
        out_path=output,
        tol_pct=1.0,
    )

    assert accepted is False
    with output.open(newline="") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == 2
    tokens = [row["energy_MeV"] for row in written]
    assert tokens == [repr(value) for value in energies]
    assert len(set(tokens)) == 2
    assert [float(token) for token in tokens] == energies
    for result, row in zip(results, written, strict=True):
        for key, value in result.items():
            if isinstance(value, float):
                assert float(row[key]) == value
        assert row["report_float_serialization"] == MODULE.REPORT_FLOAT_SERIALIZATION

    stdout = capsys.readouterr().out
    assert repr(energies[0]) in stdout
    assert repr(energies[1]) in stdout
    assert (
        f"REPORT FLOAT SERIALIZATION: {MODULE.REPORT_FLOAT_SERIALIZATION}" in stdout
    )


def test_report_serializer_rejects_nonfinite_float() -> None:
    for value in (math.inf, -math.inf, math.nan):
        with pytest.raises(MODULE.StoppingPowerInputError, match="nonfinite"):
            MODULE._serialize_report_value(value)
