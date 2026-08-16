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
    assert result["amplitude_convention"] == "net"
    assert result["amplitude_polarity"] is None
    assert result["amplitude_transform"] == "identity"
    assert result["n_events_composite_key"] == 3
    assert result["physical_events_with_multiple_eventno_values"] == 1
    assert result["eventno_values_spanning_multiple_events"] == 1
    assert result["events_that_eventno_only_join_would_corrupt"] == 3
    assert result["stopping_distribution"] == {"B4": 1, "B8": 1, "B2": 1}
    assert result["stopping_distribution_total"] == 3


def test_bare_amplitude_adc_requires_measured_convention() -> None:
    pulses = pd.DataFrame(
        {
            "run": [7],
            "evt": [1],
            "eventno": [1],
            "stave": ["B2"],
            "amplitude_adc": [6750.0],
            "baseline_adc": [6752.0],
        }
    )

    with pytest.raises(ValueError, match="table-dependent semantics"):
        MODULE.build_event_table(pulses, source_file_id="fixture")
    with pytest.raises(ValueError, match="requires amplitude_convention"):
        MODULE.build_event_table(
            pulses,
            source_file_id="fixture",
            amplitude_column="amplitude_adc",
        )


def test_absolute_amplitude_requires_measured_polarity() -> None:
    pulses = pd.DataFrame(
        {
            "run": [7],
            "evt": [1],
            "eventno": [1],
            "stave": ["B2"],
            "amplitude_adc": [6400.0],
            "baseline_adc": [6752.0],
        }
    )

    with pytest.raises(ValueError, match="requires amplitude_polarity"):
        MODULE.build_event_table(
            pulses,
            source_file_id="fixture",
            amplitude_column="amplitude_adc",
            amplitude_convention="absolute",
        )


def test_negative_going_absolute_codes_are_converted_without_abs() -> None:
    pulses = pd.DataFrame(
        {
            "run": [7, 7],
            "evt": [1, 2],
            "eventno": [1, 2],
            "stave": ["B2", "B2"],
            "amplitude_adc": [6750.0, 6400.0],
            "baseline_adc": [6752.0, 6752.0],
        }
    )

    wide, result = MODULE.build_event_table(
        pulses,
        source_file_id="fixture",
        threshold_adc=200.0,
        amplitude_column="amplitude_adc",
        amplitude_convention="absolute",
        amplitude_polarity="negative",
    )

    assert list(wide["amp_B2"]) == [2.0, 352.0]
    assert result["amplitude_convention"] == "absolute"
    assert result["amplitude_polarity"] == "negative"
    assert result["amplitude_transform"] == "baseline_adc - amplitude_adc"
    assert result["stopping_distribution"] == {"none": 1, "B2": 1}


def test_positive_going_absolute_codes_are_converted_without_abs() -> None:
    pulses = pd.DataFrame(
        {
            "run": [7],
            "evt": [1],
            "eventno": [1],
            "stave": ["B2"],
            "amplitude_adc": [7105.0],
            "baseline_adc": [6752.0],
        }
    )

    wide, result = MODULE.build_event_table(
        pulses,
        source_file_id="fixture",
        threshold_adc=200.0,
        amplitude_column="amplitude_adc",
        amplitude_convention="absolute",
        amplitude_polarity="positive",
    )

    assert list(wide["amp_B2"]) == [353.0]
    assert result["amplitude_transform"] == "amplitude_adc - baseline_adc"
    assert result["stopping_distribution"] == {"B2": 1}


def test_absolute_conversion_rejects_opposite_polarity_rows() -> None:
    pulses = pd.DataFrame(
        {
            "run": [7],
            "evt": [1],
            "eventno": [1],
            "stave": ["B2"],
            "amplitude_adc": [6400.0],
            "baseline_adc": [6752.0],
        }
    )

    with pytest.raises(ValueError, match="violate positive-going pulse polarity"):
        MODULE.build_event_table(
            pulses,
            source_file_id="fixture",
            amplitude_column="amplitude_adc",
            amplitude_convention="absolute",
            amplitude_polarity="positive",
        )


def test_absolute_conversion_rejects_nonfinite_rows() -> None:
    pulses = pd.DataFrame(
        {
            "run": [7],
            "evt": [1],
            "eventno": [1],
            "stave": ["B2"],
            "amplitude_adc": [float("nan")],
            "baseline_adc": [6752.0],
        }
    )

    with pytest.raises(ValueError, match="requires finite numeric values"):
        MODULE.build_event_table(
            pulses,
            source_file_id="fixture",
            amplitude_column="amplitude_adc",
            amplitude_convention="absolute",
            amplitude_polarity="negative",
        )


def test_net_amplitude_adc_is_used_without_subtraction() -> None:
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
        amplitude_convention="net",
    )

    assert list(wide["amp_B2"]) == [0.0, 201.0]
    assert result["amplitude_convention"] == "net"
    assert result["amplitude_polarity"] is None
    assert result["amplitude_transform"] == "identity"

    with pytest.raises(ValueError, match="only valid for absolute"):
        MODULE.build_event_table(
            pulses,
            source_file_id="fixture",
            amplitude_column="amplitude_adc",
            amplitude_convention="net",
            amplitude_polarity="negative",
        )


def test_absolute_amplitude_requires_baseline() -> None:
    pulses = pd.DataFrame(
        {
            "run": [1],
            "evt": [1],
            "eventno": [1],
            "stave": ["B2"],
            "amplitude_adc": [6750.0],
        }
    )

    with pytest.raises(ValueError, match="requires baseline_adc"):
        MODULE.build_event_table(
            pulses,
            source_file_id="fixture",
            amplitude_column="amplitude_adc",
            amplitude_convention="absolute",
            amplitude_polarity="negative",
        )


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
    assert result["amplitude_convention"] == "net"
