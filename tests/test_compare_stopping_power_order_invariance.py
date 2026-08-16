from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "single_stave" / "compare_stopping_power.py"
SPEC = importlib.util.spec_from_file_location("compare_stopping_power_order", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _old_sequential_sum(values: list[float]) -> float:
    total = 0.0
    for value in values:
        total += value
    return total


def _rows() -> list[tuple[str, float, float, float]]:
    return [("proton", 1.0, 1.0, 1.0)] + [
        ("proton", 1.0, 1e-16, 1.0) for _ in range(10)
    ]


def test_old_sequential_aggregation_depends_on_row_order() -> None:
    deposits = [row[2] for row in _rows()]
    assert _old_sequential_sum(deposits) == 1.0
    assert _old_sequential_sum(list(reversed(deposits))) == 1.000000000000001


def test_compensated_aggregation_is_row_order_invariant() -> None:
    forward = MODULE.aggregate(_rows(), rho=1.0)
    reverse = MODULE.aggregate(list(reversed(_rows())), rho=1.0)

    assert forward == reverse
    assert forward[0]["deposit_sum_MeV"] == 1.000000000000001
    assert forward[0]["track_length_sum_mm"] == 11.0
    assert forward[0]["summation_method"] == MODULE.SUMMATION_METHOD
    assert forward[0]["sim_total_MeV_cm2_g"] == pytest.approx(
        1.000000000000001 / 11.0 * 10.0
    )


def test_report_records_compensated_summation_method(tmp_path, monkeypatch) -> None:
    rows = _rows()
    reference = [(0.1, 0.0, 0.0, 1.0), (10.0, 0.0, 0.0, 1.0)]
    ref_summary = {
        "input_sha256": "a" * 64,
        "input_bytes": 123,
        "rows_validated": 2,
        "tool_version": "test-pstar",
        "component_identity": "total = electronic + nuclear",
        "all_rows_component_consistent": True,
    }
    sim_summary = {
        "input_sha256": "b" * 64,
        "input_bytes": 456,
        "rows_validated": len(rows),
        "tool_version": "test-sim",
        "energy_deposit_basis": MODULE.RAW_BASIS,
    }
    monkeypatch.setattr(
        MODULE,
        "_read_reference_with_summary",
        lambda _path: (reference, ref_summary),
    )
    monkeypatch.setattr(
        MODULE,
        "_read_sim_with_summary",
        lambda _path, _allow=False: (rows, sim_summary),
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
    assert results[0]["summation_method"] == MODULE.SUMMATION_METHOD
    with output.open(newline="") as handle:
        written = list(csv.DictReader(handle))
    assert written[0]["summation_method"] == MODULE.SUMMATION_METHOD
