"""Research-contract tests for issue #1049 weighted-null clustering."""
from __future__ import annotations

import numpy as np
import pytest

from tools.audit.research_weighted_null_cluster_contract import (
    NullDesignContractError,
    centered_bootstrap_statistics,
    run_split_invariance_fixture,
    split_weighted_rows,
    weighted_ecdf_distance,
)


def test_weighted_distance_is_invariant_to_row_splitting():
    data = np.array([0.0, 1.0, 2.0])
    model = np.array([0.0, 1.5])
    wd = np.ones(3)
    wm = np.array([1.0, 3.0])
    clusters = np.array([10, 11])
    split_x, split_w, _ = split_weighted_rows(model, wm, clusters, 10)
    assert weighted_ecdf_distance(data, model, wd, wm) == pytest.approx(
        weighted_ecdf_distance(data, split_x, wd, split_w)
    )


def test_cluster_bootstrap_preserves_split_representation_but_row_bootstrap_does_not():
    result = run_split_invariance_fixture()
    assert result.observed_d_split == pytest.approx(result.observed_d_unsplit)
    assert result.cluster_bootstrap_max_abs_delta < 1e-12
    assert result.row_bootstrap_max_abs_delta > 0.05
    assert result.row_bootstrap_mean_split != pytest.approx(
        result.row_bootstrap_mean_unsplit, abs=0.02
    )


def test_cluster_resampling_requires_aligned_cluster_ids():
    with pytest.raises(NullDesignContractError, match="must align"):
        centered_bootstrap_statistics(
            [0.0, 1.0],
            [0.5, 1.5],
            [1.0, 1.0],
            [1.0, 1.0],
            [1],
            [10, 11],
            n_bootstrap=5,
            seed=1,
            resampling_unit="cluster",
        )


@pytest.mark.parametrize("factor", [0, -1, 1.5, True])
def test_split_factor_contract_rejects_invalid_values(factor):
    with pytest.raises(NullDesignContractError, match="positive integer"):
        split_weighted_rows([1.0], [1.0], [1], factor)
