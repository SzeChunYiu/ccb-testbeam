"""Adversarial contract tests for the weighted empirical CDF used by compare_data_mc."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import ks_2samp

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))
import compare_data_mc as cmc


def _brute_force_ecdf(x: np.ndarray, w: np.ndarray, points: np.ndarray) -> np.ndarray:
    total = float(np.sum(w))
    return np.array([np.sum(w[x <= point]) / total for point in points], dtype=float)


def test_two_point_ecdf_is_constant_between_support_points():
    support, cdf = cmc._weighted_ecdf(np.array([0.0, 1.0]), np.ones(2))
    points = np.array([-1.0, 0.0, 0.25, 0.5, 0.999, 1.0, 2.0])
    got = cmc._evaluate_weighted_ecdf(support, cdf, points)
    np.testing.assert_allclose(got, [0.0, 0.5, 0.5, 0.5, 0.5, 1.0, 1.0])


def test_tied_support_is_collapsed_into_one_weighted_jump():
    x = np.array([1.0, 1.0, 1.0, 2.0, 2.0, 7.0])
    w = np.array([1.0, 2.0, 3.0, 1.0, 3.0, 10.0])
    support, cdf = cmc._weighted_ecdf(x, w)
    np.testing.assert_array_equal(support, [1.0, 2.0, 7.0])
    np.testing.assert_allclose(cdf, [6.0 / 20.0, 10.0 / 20.0, 1.0])


def test_all_tied_values_form_single_unit_jump():
    support, cdf = cmc._weighted_ecdf(np.full(8, 7000.0), np.arange(1.0, 9.0))
    np.testing.assert_array_equal(support, [7000.0])
    np.testing.assert_array_equal(cdf, [1.0])
    got = cmc._evaluate_weighted_ecdf(support, cdf, np.array([6999.0, 7000.0, 7001.0]))
    np.testing.assert_array_equal(got, [0.0, 1.0, 1.0])


def test_weighted_ecdf_matches_direct_indicator_sum_oracle():
    x = np.array([0.0, 0.0, 1.0, 3.0, 3.0, 7.0])
    w = np.array([0.5, 1.5, 2.0, 0.25, 0.75, 5.0])
    points = np.array([-1.0, 0.0, 0.5, 1.0, 2.0, 3.0, 6.0, 7.0, 8.0])
    support, cdf = cmc._weighted_ecdf(x, w)
    got = cmc._evaluate_weighted_ecdf(support, cdf, points)
    expected = _brute_force_ecdf(x, w, points)
    np.testing.assert_allclose(got, expected, rtol=0.0, atol=1e-15)


def test_weighted_row_splitting_preserves_ecdf_and_distance():
    data = np.array([0.0, 1.0, 2.0, 3.0])
    model = np.array([0.0, 1.0, 3.0])
    w_data = np.ones(4)
    w_model = np.array([1.0, 5.0, 2.0])

    d_original = cmc._weighted_ks_distance(data, model, w_data, w_model)

    split_model = np.repeat(model, 10)
    split_weights = np.repeat(w_model / 10.0, 10)
    d_split = cmc._weighted_ks_distance(data, split_model, w_data, split_weights)

    support_a, cdf_a = cmc._weighted_ecdf(model, w_model)
    support_b, cdf_b = cmc._weighted_ecdf(split_model, split_weights)
    np.testing.assert_array_equal(support_a, support_b)
    np.testing.assert_allclose(cdf_a, cdf_b, rtol=0.0, atol=1e-15)
    assert d_split == pytest.approx(d_original, abs=1e-15)


def test_tie_permutation_does_not_change_ecdf_or_distance():
    rng = np.random.default_rng(20260810)
    x = np.array([0.0, 0.0, 1.0, 1.0, 1.0, 7000.0, 7000.0])
    w = np.array([1.0, 4.0, 2.0, 3.0, 5.0, 7.0, 11.0])
    reference = cmc._weighted_ecdf(x, w)
    for _ in range(20):
        order = rng.permutation(x.size)
        got = cmc._weighted_ecdf(x[order], w[order])
        np.testing.assert_array_equal(got[0], reference[0])
        np.testing.assert_allclose(got[1], reference[1], rtol=0.0, atol=1e-15)


def test_equal_weight_distance_matches_scipy_ks_statistic():
    rng = np.random.default_rng(91437)
    for n_data, n_model in ((7, 11), (31, 29), (100, 80)):
        data = rng.normal(loc=0.1, scale=1.2, size=n_data)
        model = rng.normal(loc=-0.2, scale=0.9, size=n_model)
        got = cmc._weighted_ks_distance(
            data,
            model,
            np.ones(n_data),
            np.ones(n_model),
        )
        expected = float(ks_2samp(data, model, method="asymp").statistic)
        assert got == pytest.approx(expected, abs=1e-15)


def test_saturation_spike_and_quantized_tail_match_indicator_oracle():
    data = np.array([0, 1, 1, 2, 3, 4, 7000, 7000, 7000, 7000], dtype=float)
    model = np.array([0, 1, 2, 2, 3, 4, 5, 7000], dtype=float)
    w_data = np.ones(data.size)
    w_model = np.array([1.0, 1.0, 2.0, 3.0, 1.0, 1.0, 1.0, 5.0])
    support = np.union1d(data, model)

    sd, fd = cmc._weighted_ecdf(data, w_data)
    sm, fm = cmc._weighted_ecdf(model, w_model)
    got_d = cmc._evaluate_weighted_ecdf(sd, fd, support)
    got_m = cmc._evaluate_weighted_ecdf(sm, fm, support)
    exp_d = _brute_force_ecdf(data, w_data, support)
    exp_m = _brute_force_ecdf(model, w_model, support)

    np.testing.assert_allclose(got_d, exp_d, rtol=0.0, atol=1e-15)
    np.testing.assert_allclose(got_m, exp_m, rtol=0.0, atol=1e-15)
    assert cmc._weighted_ks_distance(data, model, w_data, w_model) == pytest.approx(
        np.max(np.abs(exp_d - exp_m)),
        abs=1e-15,
    )


@pytest.mark.parametrize(
    ("x", "w", "message"),
    [
        ([], [], "at least one observation"),
        ([1.0, 2.0], [1.0], "weight size"),
        ([1.0, np.nan], [1.0, 1.0], "values must be finite"),
        ([1.0, 2.0], [1.0, np.inf], "weights must be finite"),
        ([1.0, 2.0], [1.0, -1.0], "weights must be nonnegative"),
        ([1.0, 2.0], [0.0, 0.0], "weight sum must be positive"),
    ],
)
def test_weighted_ecdf_fails_closed_on_invalid_measure(x, w, message):
    with pytest.raises(ValueError, match=message):
        cmc._weighted_ecdf(x, w)


def test_p_value_is_explicitly_non_authorising_until_issue_1049():
    result = cmc._weighted_ks_stat(
        np.array([0.0, 1.0, 2.0]),
        np.array([0.0, 2.0, 3.0]),
        np.ones(3),
        np.array([1.0, 2.0, 1.0]),
        n_bootstrap=10,
    )
    assert result["cdf_convention"] == "right_continuous"
    assert result["ecdf_support"] == "unique_tie_aggregated"
    assert result["p_value_status"] == "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION"
    assert result["p_value_method"] == "legacy_unit_weight_value_permutation"
