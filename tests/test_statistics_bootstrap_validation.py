"""Regression tests for the scientific audit findings STAT-001 and STAT-002.

STAT-001: every bootstrap entry point must fail-closed (raise ``ValueError``)
on malformed inputs -- empty / non-finite data, alpha outside (0, 1), n_boot<1,
or value/cluster length mismatch -- instead of silently returning a degenerate
or NaN interval.

STAT-002: a cluster bootstrap keyed by ``(run, event)`` must resample whole
clusters with replacement so rows from one cluster always move together.
"""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.statistics.bootstrap import cluster_bootstrap, grouped_bootstrap
from ccb_mc_validation.statistics.metrics import (
    bootstrap_ci,
    build_cluster_metric_record,
    build_grouped_metric_record,
    build_metric_record,
)

RNG = np.random.default_rng(0)


# ---------------------------------------------------------------------------
# STAT-001: fail-closed input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_n_boot",
    [0, -1, 1.5, "500", None, True],
)
def test_bootstrap_ci_rejects_invalid_n_boot(bad_n_boot):
    values = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="n_boot"):
        bootstrap_ci(values, np.mean, RNG, n_boot=bad_n_boot)


@pytest.mark.parametrize("bad_alpha", [0.0, 1.0, -0.1, 1.5, np.nan, np.inf])
def test_bootstrap_ci_rejects_alpha_outside_open_unit_interval(bad_alpha):
    values = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="alpha"):
        bootstrap_ci(values, np.mean, RNG, alpha=bad_alpha)


def test_bootstrap_ci_rejects_empty_values():
    with pytest.raises(ValueError, match="non-empty"):
        bootstrap_ci(np.array([]), np.mean, RNG)


def test_bootstrap_ci_rejects_nan_values():
    with pytest.raises(ValueError, match="non-finite"):
        bootstrap_ci(np.array([1.0, np.nan, 3.0]), np.mean, RNG)


def test_bootstrap_ci_rejects_non_finite_values():
    with pytest.raises(ValueError, match="non-finite"):
        bootstrap_ci(np.array([1.0, np.inf, 3.0]), np.mean, RNG)


def test_bootstrap_ci_rejects_non_1d_values():
    with pytest.raises(ValueError, match="1-D"):
        bootstrap_ci(np.array([[1.0, 2.0], [3.0, 4.0]]), np.mean, RNG)


def test_bootstrap_ci_accepts_single_observation_as_zero_width_interval():
    # A deterministic 1-point sample has no resampling variance; the honest
    # representation is a zero-width interval around the point (NOT a fake CI).
    point, lo, hi = bootstrap_ci(np.array([42.0]), np.mean, RNG, n_boot=10)
    assert point == lo == hi == 42.0


def test_bootstrap_ci_returns_finite_triple_on_valid_input():
    values = np.arange(1.0, 21.0)
    point, lo, hi = bootstrap_ci(values, np.mean, RNG, n_boot=200, alpha=0.05)
    assert np.isfinite(point) and np.isfinite(lo) and np.isfinite(hi)
    assert lo <= point <= hi


def test_grouped_bootstrap_rejects_value_group_length_mismatch():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    groups = np.array(["a", "a", "b", "b"])  # one short
    with pytest.raises(ValueError, match="length mismatch"):
        grouped_bootstrap(values, groups, np.mean, RNG)


def test_grouped_bootstrap_rejects_empty_and_bad_alpha_and_bad_n_boot():
    values = np.array([1.0, 2.0])
    groups = np.array(["a", "b"])
    with pytest.raises(ValueError, match="non-empty"):
        grouped_bootstrap(np.array([]), np.array([]), np.mean, RNG)
    with pytest.raises(ValueError, match="alpha"):
        grouped_bootstrap(values, groups, np.mean, RNG, alpha=0.0)
    with pytest.raises(ValueError, match="n_boot"):
        grouped_bootstrap(values, groups, np.mean, RNG, n_boot=0)


def test_cluster_bootstrap_rejects_cluster_value_length_mismatch():
    values = np.array([1.0, 2.0, 3.0])
    clusters = np.array(["e0", "e0"], dtype=object)  # one short
    with pytest.raises(ValueError, match="length mismatch"):
        cluster_bootstrap(values, clusters, np.mean, RNG)


@pytest.mark.parametrize("builder", ["metric", "grouped", "cluster"])
def test_build_metric_record_helpers_propagate_validation(builder):
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        if builder == "metric":
            build_metric_record("m", np.array([]), np.mean, rng)
        elif builder == "grouped":
            build_grouped_metric_record(
                "m", np.array([1.0, 2.0]), np.array(["a"]), np.mean, rng
            )
        else:
            build_cluster_metric_record(
                "m", np.array([1.0, 2.0]), np.array(["a"]), np.mean, rng
            )


# ---------------------------------------------------------------------------
# STAT-002: cluster bootstrap resamples whole clusters, not individual rows
# ---------------------------------------------------------------------------


def test_cluster_bootstrap_keeps_cluster_rows_together():
    """Two clusters, constant within cluster: replicate means can only be one
    of {0.0, 0.5, 1.0}. A row bootstrap would concentrate near 0.5; the cluster
    bootstrap spans the full [0, 1] range because it picks whole clusters."""
    values = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    clusters = np.array(["e0", "e0", "e0", "e1", "e1", "e1"], dtype=object)
    rng = np.random.default_rng(0)
    lo, hi = cluster_bootstrap(values, clusters, np.mean, rng, n_boot=2000, alpha=0.05)
    assert lo <= 0.0 + 1e-9
    assert hi >= 1.0 - 1e-9


def test_cluster_bootstrap_wider_than_row_bootstrap_under_intra_cluster_corr():
    """When rows are perfectly correlated within clusters, the row bootstrap
    severely understates uncertainty. The cluster CI must be (much) wider."""
    rng_seed = 0
    # 20 clusters of 5 identical rows each; half the clusters are 0, half are 1.
    cluster_val = np.tile(np.repeat([0.0, 1.0], 10), 5)
    clusters = np.repeat(np.arange(20), 5).astype(object)
    # Cluster bootstrap CI
    rng_c = np.random.default_rng(rng_seed)
    clo, chi = cluster_bootstrap(cluster_val, clusters, np.mean, rng_c, n_boot=2000)
    # Row bootstrap CI (resampling 100 individual rows independently)
    rng_r = np.random.default_rng(rng_seed)
    stats = np.empty(2000)
    for i in range(2000):
        idx = rng_r.integers(0, cluster_val.size, cluster_val.size)
        stats[i] = np.mean(cluster_val[idx])
    rlo, rhi = np.quantile(stats, [0.025, 0.975])
    # Under perfect intra-cluster correlation the cluster CI must be STRICTLY
    # wider than the row CI (which treats correlated rows as independent and
    # understates uncertainty). Observed ratio is ~2x for this setup.
    assert (chi - clo) > 1.5 * (rhi - rlo)
    assert (chi - clo) > 0.3  # non-trivial absolute width


def test_grouped_bootstrap_resamples_whole_groups():
    """Groups move as blocks: with groups [a,a,b,b] constant within group, the
    replicate mean is exactly one of {0.0, 0.5, 1.0}."""
    values = np.array([0.0, 0.0, 1.0, 1.0])
    groups = np.array(["a", "a", "b", "b"])
    rng = np.random.default_rng(1)
    lo, hi = grouped_bootstrap(values, groups, np.mean, rng, n_boot=2000, alpha=0.05)
    assert lo <= 0.0 + 1e-9
    assert hi >= 1.0 - 1e-9
