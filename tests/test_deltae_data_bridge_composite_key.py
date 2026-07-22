from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "single_stave" / "deltaE_E_data_bridge.py"
SPEC = importlib.util.spec_from_file_location("deltae_bridge", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_composite_key_never_splits_on_eventno() -> None:
    pulses = pd.DataFrame(
        {
            "run": [1, 1, 1, 1, 1, 2],
            "evt": [10, 10, 10, 11, 11, 10],
            # Physical event (run=1, evt=10) deliberately has two eventno
            # values. The old bridge emitted two rows for this one event.
            "eventno": [100, 101, 101, 100, 100, 100],
            "stave": ["B2", "B4", "B4", "B2", "B8", "B2"],
            "median_amp_adc": [250.0, 300.0, 275.0, 50.0, 500.0, 400.0],
        }
    )

    wide, result = MODULE.build_event_table(
        pulses,
        source_file_id="fixture",
        threshold_adc=200.0,
    )

    assert len(wide) == 3
    assert not wide.duplicated(["source_file_id", "run", "evt"]).any()
    assert "eventno" not in wide.columns
    assert result["amplitude_column"] == "median_amp_adc"
    assert result["amplitude_column_explicitly_requested"] is False
    assert result["n_events_composite_key"] == 3
    assert result["physical_events_with_multiple_eventno_values"] == 1
    assert result["eventno_values_spanning_multiple_events"] == 1
    assert result["events_that_eventno_only_join_would_corrupt"] == 3
    assert result["stopping_distribution"] == {"B4": 1, "B8": 1, "B2": 1}
    assert result["stopping_distribution_total"] == 3
    assert sum(result["stopping_distribution"].values()) == 3


def test_bare_amplitude_adc_is_rejected_by_default() -> None:
    pulses = pd.DataFrame(
        {
            "run": [7],
            "evt": [1],
            "eventno": [1],
            "stave": ["B2"],
            "amplitude_adc": [201.0],
        }
    )

    with pytest.raises(ValueError, match="schema-ambiguous"):
        MODULE.build_event_table(pulses, source_file_id="fixture")


def test_ambiguous_amplitude_can_only_be_used_by_explicit_override() -> None:
    pulses = pd.DataFrame(
        {
            "run": [7, 7],
            "evt": [1, 2],
            "eventno": [1, 2],
            "stave": ["B2", "B2"],
            "amplitude_adc": [0.0, 201.0],
        }
    )

    wide, result = MODULE.build_event_table(
        pulses,
        source_file_id="fixture",
        threshold_adc=200.0,
        amplitude_column="amplitude_adc",
    )

    assert list(wide["amp_B4"]) == [0.0, 0.0]
    assert result["amplitude_column"] == "amplitude_adc"
    assert result["amplitude_column_explicitly_requested"] is True
    assert result["stopping_distribution"] == {"none": 1, "B2": 1}


def test_multiple_explicit_amplitude_columns_require_selection() -> None:
    pulses = pd.DataFrame(
        {
            "run": [1],
            "evt": [1],
            "eventno": [1],
            "stave": ["B2"],
            "median_amp_adc": [210.0],
            "peak_height_adc": [205.0],
        }
    )

    with pytest.raises(ValueError, match="multiple explicit amplitude columns"):
        MODULE.build_event_table(pulses, source_file_id="fixture")

    _, result = MODULE.build_event_table(
        pulses,
        source_file_id="fixture",
        amplitude_column="peak_height_adc",
    )
    assert result["amplitude_column"] == "peak_height_adc"
    assert result["amplitude_column_explicitly_requested"] is True
