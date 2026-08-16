"""Research-contract tests for fitted-scale/null topology issue #1166."""
from __future__ import annotations

import pytest

from tools.audit.research_weighted_null_scale_contract import (
    median_ratio_scale,
    run_overlap_topology_fixture,
    run_scale_refit_type1_fixture,
)


def test_median_ratio_scale_matches_declared_equal_weight_estimator():
    assert median_ratio_scale([180.0, 360.0], [1.0, 2.0], [1.0, 1.0]) == pytest.approx(270.0)


def test_same_sample_fixed_scale_is_falsified_in_equal_weight_null_fixture():
    result = run_scale_refit_type1_fixture()
    assert result.alpha_005_fixed_rejection_fraction == pytest.approx(0.0)
    assert result.alpha_005_refit_rejection_fraction == pytest.approx(0.06)
    assert result.alpha_010_fixed_rejection_fraction == pytest.approx(0.015)
    assert result.alpha_010_refit_rejection_fraction == pytest.approx(0.095)
    assert result.mean_fixed_null_d > result.mean_observed_d + 0.01
    assert abs(result.mean_refit_null_d - result.mean_observed_d) < 0.005
    assert result.mean_p_fixed > result.mean_p_refit + 0.10


def test_breaking_mc_sample_subset_relation_changes_scale_covariance_and_null_d():
    result = run_overlap_topology_fixture()
    assert result.corr_scale_mci_median_overlap < -0.30
    assert abs(result.corr_scale_mci_median_broken_independent) < 0.05
    assert result.mean_d_broken_independent > result.mean_d_overlap + 0.005
    assert result.q95_d_broken_independent > result.q95_d_overlap + 0.01


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"n_trials": 0}, "counts must be positive"),
        ({"n_data": 1}, "sample sizes >=2"),
        ({"true_scale": 0.0}, "positive finite scale"),
    ],
)
def test_scale_refit_fixture_rejects_invalid_contract(kwargs, message):
    with pytest.raises(ValueError, match=message):
        run_scale_refit_type1_fixture(**kwargs)


@pytest.mark.parametrize("probability", [0.0, 1.0, -0.1, 1.1])
def test_overlap_fixture_requires_strict_probability(probability):
    with pytest.raises(ValueError, match="strictly between"):
        run_overlap_topology_fixture(sample_i_probability=probability)
