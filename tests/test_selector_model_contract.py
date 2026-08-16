"""Regression tests for S00 selector amplitude-map equivalence (#1136)."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.selector import select_amplitude, selectors_available
from ccb_mc_validation.selector_model_contract import (
    aliases_for_amplitude_map,
    amplitude_map_id,
    amplitude_maps_available,
    collapse_method_names,
    method_contract,
    validity_policies_available,
)


def test_registry_covers_every_public_selector_method() -> None:
    for method in selectors_available():
        assert method_contract(method).method == method


def test_candidate_universe_collapses_to_three_unique_amplitude_maps() -> None:
    assert amplitude_maps_available() == [
        "first_four_median_v1",
        "range_max_minus_min_v1",
        "full_window_p10_v1",
    ]
    grouped = collapse_method_names(selectors_available())
    assert grouped["range_max_minus_min_v1"] == ("dynamic_range", "rolling_min")
    assert len(grouped) == 3


def test_dynamic_range_and_rolling_min_share_one_map_id() -> None:
    assert amplitude_map_id("dynamic_range") == "range_max_minus_min_v1"
    assert amplitude_map_id("rolling_min") == "range_max_minus_min_v1"
    assert aliases_for_amplitude_map("range_max_minus_min_v1") == (
        "dynamic_range",
        "rolling_min",
    )


def test_validity_policies_remain_distinct_from_amplitude_maps() -> None:
    policies = validity_policies_available()
    assert len(policies) == len(selectors_available())
    assert len(set(policies)) == len(policies)
    assert (
        method_contract("dynamic_range").validity_policy_id
        != method_contract("rolling_min").validity_policy_id
    )


def test_range_aliases_are_exactly_equal_on_random_finite_waveforms() -> None:
    rng = np.random.default_rng(20260810)
    waveforms = rng.normal(loc=1000.0, scale=250.0, size=(250, 18))
    thresholds = rng.uniform(0.0, 2000.0, size=len(waveforms))

    for waveform, threshold in zip(waveforms, thresholds):
        dynamic = select_amplitude(waveform, cut_adc=float(threshold), method="dynamic_range")
        rolling = select_amplitude(waveform, cut_adc=float(threshold), method="rolling_min")
        assert dynamic.pedestal.pedestal_adc == rolling.pedestal.pedestal_adc
        assert dynamic.amplitude_adc == rolling.amplitude_adc
        assert dynamic.selected is rolling.selected


def test_bipolar_fixture_separates_diagnostic_policy_not_amplitude() -> None:
    waveform = np.full(18, 100.0)
    waveform[5] = -2000.0
    waveform[9] = 5000.0

    dynamic = select_amplitude(waveform, cut_adc=1000.0, method="dynamic_range")
    rolling = select_amplitude(waveform, cut_adc=1000.0, method="rolling_min")

    assert dynamic.amplitude_adc == 7000.0
    assert rolling.amplitude_adc == 7000.0
    assert dynamic.selected is True
    assert rolling.selected is True
    assert dynamic.validity != rolling.validity


def test_p10_is_a_genuinely_distinct_negative_control() -> None:
    waveform = np.array(
        [0.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0,
         5000.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    )
    range_result = select_amplitude(waveform, cut_adc=0.0, method="dynamic_range")
    p10_result = select_amplitude(waveform, cut_adc=0.0, method="early_robust_p10")

    assert range_result.amplitude_adc == 5000.0
    assert p10_result.amplitude_adc != range_result.amplitude_adc
    assert amplitude_map_id("early_robust_p10") != amplitude_map_id("dynamic_range")


def test_duplicate_method_names_do_not_inflate_candidate_count() -> None:
    grouped = collapse_method_names(
        ["dynamic_range", "rolling_min", "dynamic_range", "v1", "rolling_min"]
    )
    assert grouped == {
        "range_max_minus_min_v1": ("dynamic_range", "rolling_min"),
        "first_four_median_v1": ("v1",),
    }
