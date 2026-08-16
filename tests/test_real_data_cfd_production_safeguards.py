from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "scripts" / "real_data_cfd_contract.py"
PRODUCER_PATH = ROOT / "scripts" / "real_data_cfd_timing.py"
REPORT_PATH = ROOT / "reports" / "real_data_cfd_timing" / "REPORT.md"
RESULT_PATH = ROOT / "reports" / "real_data_cfd_timing" / "result.json"


def _load_contract():
    scripts = str(CONTRACT_PATH.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import real_data_cfd_contract

    return real_data_cfd_contract


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "run": [1, 1, 2, 2],
            "event_id": [7, 7, 7, 7],
            "stave": ["B6", "B8", "B6", "B8"],
            "peak_sample": [10.0, 10.2, 20.0, 25.0],
            "t": [1.0, 0.0, 101.0, 100.0],
        }
    )


def test_composite_event_key_prevents_cross_run_collapse() -> None:
    contract = _load_contract()
    wide = contract.pivot_by_event(_frame(), "t")
    assert list(wide.index.names) == ["run", "event_id"]
    assert len(wide) == 2
    assert np.allclose((wide["B6"] - wide["B8"]).to_numpy(), [1.0, 1.0])


def test_in_time_selection_uses_run_and_event_id() -> None:
    contract = _load_contract()
    frame = pd.DataFrame(
        {
            "run": [1, 1, 2, 2, 3, 3],
            "event_id": [7, 7, 7, 7, 7, 7],
            "stave": ["B6", "B8", "B6", "B8", "B6", "B8"],
            "peak_sample": [-1.0, -1.0, 0.0, 10.0, 1.0, 1.0],
        }
    )
    kept, offsets, count = contract.select_in_time_rows(frame, ["B6", "B8"], 1.0)
    assert count == 2
    keys = set(map(tuple, kept[["run", "event_id"]].drop_duplicates().to_numpy()))
    assert keys == {(1, 7), (3, 7)}
    assert offsets == {"B6": 0.0, "B8": 1.0}


def test_duplicate_stave_rows_fail_closed() -> None:
    contract = _load_contract()
    duplicate = pd.concat([_frame(), _frame().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        contract.pivot_by_event(duplicate, "t")


def test_residual_plot_record_is_centered_and_counts_tails() -> None:
    contract = _load_contract()
    centered, record = contract.residual_plot_record(
        [-100.0, -2.0, -1.0, 0.0, 1.0, 2.0, 100.0],
        "control",
        core_half_width_ns=5.0,
    )
    assert np.median(centered) == 0.0
    assert record.full_underflow == 0
    assert record.full_overflow == 0
    assert record.core_displayed == 5
    assert record.core_underflow == 1
    assert record.core_overflow == 1
    assert record.q16_centered_ns < 0 < record.q84_centered_ns


def test_pair_only_contract_denies_sqrt2_inference() -> None:
    contract = _load_contract()
    inference = contract.pair_only_inference_contract()
    assert inference["authorized"] is False
    assert "sqrt(2)" in inference["reason"]
    assert "covariance" in " ".join(inference["required_for_individual_stave"])


def test_producer_source_has_no_single_stave_division_or_event_id_only_pivot() -> None:
    source = PRODUCER_PATH.read_text(encoding="utf-8")
    ast.parse(source)
    forbidden = ["/ np.sqrt(2)", "/1.4142", 'pivot(index="event_id"', "pivot(index='event_id'"]
    assert not any(token in source for token in forbidden)
    assert "select_in_time_rows" in source
    assert "pair_residual_vector" in source
    assert '"individual_stave_authorized": False' in source
    assert "allow_nan=False" in source


def test_optional_nonfinite_fit_metrics_are_serialized_as_null() -> None:
    source = PRODUCER_PATH.read_text(encoding="utf-8")
    assert "def _optional_finite" in source
    assert '"core_sigma_ns": _optional_finite' in source
    assert "allow_nan=False" in source


def test_published_legacy_bundle_is_quarantined_not_reinterpreted() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    report = REPORT_PATH.read_text(encoding="utf-8")
    assert result["acceptance"]["status"] == "FLAWED_LEGACY_OUTPUT_QUARANTINED"
    assert result["single_stave_inference"]["authorized"] is False
    assert result["event_identity"]["legacy_generator_key"] == ["event_id"]
    assert result["visualization_status"]["residual_pngs_authorized"] is False
    assert "Quarantined Legacy Output" in report
    assert "Single-stave estimate" not in report
    assert "does not identify" in report
