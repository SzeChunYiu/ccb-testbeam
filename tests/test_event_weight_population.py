from __future__ import annotations

import math

import numpy as np
import pytest

from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.truth.event_weight_population import (
    EVENT_WEIGHT_POPULATION_POLICY_ID,
    SUMMATION_METHOD_ID,
    summarize_event_weight_population,
)


def test_empty_population_is_nonauthorising_not_fake_zero_ess() -> None:
    summary = summarize_event_weight_population([], expected_length=0)
    assert summary.measure_defined is False
    assert summary.effective_sample_size is None
    assert summary.effective_sample_fraction is None
    assert summary.max_weight_fraction is None
    assert summary.weight_scale is None
    assert summary.sum_w_over_scale is None
    assert summary.sum_w2_over_scale2 is None
    assert summary.sum_w == 0.0
    assert summary.sum_w2 == 0.0


def test_nonempty_all_zero_population_fails_closed() -> None:
    with pytest.raises(DataContractError, match="positive finite mass"):
        summarize_event_weight_population([0.0, 0.0, 0.0])


@pytest.mark.parametrize(
    "bad",
    (
        [1.0, -1.0],
        [1.0, np.nan],
        [1.0, np.inf],
        [1.0, -np.inf],
        [[1.0], [2.0]],
        [True, False],
        [True, 1.0],
        [1.0 + 2.0j],
        ["1.0", "2.0"],
    ),
)
def test_invalid_probability_measure_inputs_are_rejected(bad: object) -> None:
    with pytest.raises(DataContractError):
        summarize_event_weight_population(bad)


def test_masked_weight_cannot_silently_reappear_from_underlying_storage() -> None:
    masked = np.ma.array([1.0, 999.0], mask=[False, True])
    with pytest.raises(DataContractError, match="masked array"):
        summarize_event_weight_population(masked)


def test_expected_length_is_part_of_event_alignment_contract() -> None:
    with pytest.raises(DataContractError, match="length 2 != expected 3"):
        summarize_event_weight_population([1.0, 2.0], expected_length=3)


def test_equal_weights_recover_nominal_event_count() -> None:
    summary = summarize_event_weight_population([3.5, 3.5, 3.5, 3.5])
    assert summary.measure_defined is True
    assert summary.effective_sample_size == pytest.approx(4.0)
    assert summary.effective_sample_fraction == pytest.approx(1.0)
    assert summary.max_weight_fraction == pytest.approx(0.25)
    assert summary.weight_scale == 3.5
    assert summary.sum_w_over_scale == pytest.approx(4.0)
    assert summary.sum_w2_over_scale2 == pytest.approx(4.0)
    assert summary.n_positive == 4
    assert summary.n_zero == 0


def test_zero_weight_rows_are_retained_but_do_not_create_information() -> None:
    summary = summarize_event_weight_population([0.0, 5.0, 0.0])
    assert summary.effective_sample_size == pytest.approx(1.0)
    assert summary.effective_sample_fraction == pytest.approx(1.0 / 3.0)
    assert summary.max_weight_fraction == pytest.approx(1.0)
    assert summary.n_positive == 1
    assert summary.n_zero == 2


def test_positive_common_rescaling_preserves_ess_and_dominance() -> None:
    base = summarize_event_weight_population([1.0, 2.0, 7.0])
    scaled = summarize_event_weight_population([1.0e-9, 2.0e-9, 7.0e-9])
    assert scaled.effective_sample_size == pytest.approx(
        base.effective_sample_size, rel=0.0, abs=2e-15
    )
    assert scaled.max_weight_fraction == pytest.approx(
        base.max_weight_fraction, rel=0.0, abs=2e-15
    )
    assert scaled.sum_w == pytest.approx(base.sum_w * 1.0e-9)
    assert scaled.sum_w2 == pytest.approx(base.sum_w2 * 1.0e-18)


@pytest.mark.parametrize("factor", (1.0e300, 1.0e-300))
def test_extreme_common_rescaling_preserves_normalized_measure(factor: float) -> None:
    base = summarize_event_weight_population([1.0, 2.0, 7.0])
    scaled = summarize_event_weight_population(
        [1.0 * factor, 2.0 * factor, 7.0 * factor]
    )
    assert scaled.measure_defined is True
    assert scaled.effective_sample_size == pytest.approx(
        base.effective_sample_size, rel=0.0, abs=2e-15
    )
    assert scaled.max_weight_fraction == pytest.approx(
        base.max_weight_fraction, rel=0.0, abs=2e-15
    )
    assert scaled.sum_w_over_scale == pytest.approx(
        base.sum_w_over_scale, rel=0.0, abs=2e-15
    )
    assert scaled.sum_w2_over_scale2 == pytest.approx(
        base.sum_w2_over_scale2, rel=0.0, abs=2e-15
    )
    assert scaled.sum_w2 is None


def test_second_moment_overflow_does_not_reject_valid_measure() -> None:
    summary = summarize_event_weight_population([1.0e154, 1.0e154])
    assert summary.measure_defined is True
    assert summary.sum_w == pytest.approx(2.0e154)
    assert summary.sum_w2 is None
    assert summary.effective_sample_size == pytest.approx(2.0)
    assert summary.max_weight_fraction == pytest.approx(0.5)


def test_total_mass_overflow_does_not_reject_valid_normalized_measure() -> None:
    summary = summarize_event_weight_population([1.0e308, 1.0e308])
    assert summary.measure_defined is True
    assert summary.sum_w is None
    assert summary.sum_w2 is None
    assert summary.weight_scale == 1.0e308
    assert summary.sum_w_over_scale == pytest.approx(2.0)
    assert summary.sum_w2_over_scale2 == pytest.approx(2.0)
    assert summary.effective_sample_size == pytest.approx(2.0)
    assert summary.max_weight_fraction == pytest.approx(0.5)


def test_subnormal_equal_weights_remain_a_defined_measure() -> None:
    smallest = np.nextafter(0.0, 1.0)
    summary = summarize_event_weight_population([smallest, smallest])
    assert summary.measure_defined is True
    assert summary.sum_w > 0.0
    assert summary.sum_w2 is None
    assert summary.sum_w_over_scale == pytest.approx(2.0)
    assert summary.sum_w2_over_scale2 == pytest.approx(2.0)
    assert summary.effective_sample_size == pytest.approx(2.0)
    assert summary.max_weight_fraction == pytest.approx(0.5)


def test_permutation_invariant_fsum_records_exact_dynamic_range_fixture() -> None:
    forward = np.array([1.0e16, 1.0, 1.0], dtype=np.float64)
    reverse = forward[::-1].copy()

    # Negative control: the reduction used by PR #1169 is representation-order
    # sensitive on this finite, nonnegative fixture.
    assert float(np.sum(forward, dtype=np.float64)) != float(
        np.sum(reverse, dtype=np.float64)
    )

    a = summarize_event_weight_population(forward)
    b = summarize_event_weight_population(reverse)
    exact = math.fsum(float(value) for value in forward)
    assert a.sum_w == exact
    assert b.sum_w == exact
    assert a.sum_w == b.sum_w
    assert a.sum_w2 == b.sum_w2
    assert a.sum_w_over_scale == b.sum_w_over_scale
    assert a.sum_w2_over_scale2 == b.sum_w2_over_scale2
    assert a.effective_sample_size == b.effective_sample_size
    assert a.max_weight_fraction == b.max_weight_fraction


def test_one_dominant_weight_exposes_low_information_population() -> None:
    summary = summarize_event_weight_population([1000.0, 1.0, 1.0, 1.0])
    assert 1.0 < summary.effective_sample_size < 1.01
    assert summary.effective_sample_fraction < 0.26
    assert summary.max_weight_fraction > 0.99


def test_summary_serializes_declared_policy_without_nan_sentinels() -> None:
    summary = summarize_event_weight_population([1.0e308, 1.0e308])
    payload = summary.as_dict()
    assert payload["policy_id"] == EVENT_WEIGHT_POPULATION_POLICY_ID
    assert payload["summation_method"] == SUMMATION_METHOD_ID
    assert payload["statistical_unit"] == "generator_event"
    assert payload["measure_defined"] is True
    assert payload["sum_w"] is None
    assert payload["sum_w2"] is None
    assert all(
        value is None or not isinstance(value, float) or math.isfinite(value)
        for value in payload.values()
    )
