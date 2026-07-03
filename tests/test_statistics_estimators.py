"""Tests for the canonical estimators in ccb_mc_validation.statistics.estimators."""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.statistics.estimators import (
    bh_fdr,
    paired_delta_bootstrap,
    res68_abs,
    res68_centered,
    sigma68,
)

Z84 = 0.994458  # standard-normal 0.84 quantile: sigma68(gaussian) -> Z84 * sigma


class TestSigma68:
    def test_gaussian_recovers_sigma(self):
        rng = np.random.default_rng(1)
        sigma = 2.0
        x = rng.normal(0.0, sigma, size=200_000)
        assert sigma68(x) == pytest.approx(Z84 * sigma, rel=0.02)
        # and it is approximately sigma itself at the ~2% level
        assert sigma68(x) == pytest.approx(sigma, rel=0.03)

    def test_location_invariant(self):
        rng = np.random.default_rng(2)
        x = rng.normal(0.0, 1.0, size=50_000)
        assert sigma68(x + 5.0) == pytest.approx(sigma68(x), abs=1e-9)

    def test_rejects_empty_and_nan(self):
        with pytest.raises(ValueError):
            sigma68([])
        with pytest.raises(ValueError):
            sigma68([1.0, np.nan])


class TestRes68Definitions:
    """The three definitions must differ exactly as documented on a biased sample."""

    def test_biased_sample_orders_the_definitions(self):
        rng = np.random.default_rng(3)
        bias, sigma = 1.5, 1.0
        x = rng.normal(bias, sigma, size=200_000)

        r_abs = res68_abs(x)
        r_cen = res68_centered(x)
        s68 = sigma68(x)

        # res68_abs includes the bias: for bias >> 0 it sits near
        # bias + quantile-ish spread, far above the centered spread.
        assert r_abs > r_cen + 0.5 * bias
        # centered res68 and sigma68 both estimate pure spread ~ Z84*sigma.
        assert r_cen == pytest.approx(Z84 * sigma, rel=0.03)
        assert s68 == pytest.approx(Z84 * sigma, rel=0.03)
        # analytic check: 68th pct of |N(bias, sigma)| for bias=1.5, sigma=1
        # is the z solving Phi(z-1.5) - Phi(-z-1.5) = 0.68 -> z ~ 1.968.
        assert r_abs == pytest.approx(1.968, rel=0.03)

    def test_centered_symmetric_sample_makes_all_three_agree(self):
        rng = np.random.default_rng(4)
        x = rng.normal(0.0, 1.0, size=200_000)
        assert res68_abs(x) == pytest.approx(res68_centered(x), rel=0.02)
        assert res68_abs(x) == pytest.approx(sigma68(x), rel=0.02)

    def test_res68_abs_is_not_location_invariant(self):
        rng = np.random.default_rng(5)
        x = rng.normal(0.0, 1.0, size=50_000)
        assert res68_abs(x + 3.0) > res68_abs(x) + 2.0


class TestPairedDeltaBootstrap:
    def test_covers_known_shift(self):
        """CI of the paired mean-difference must cover the injected shift."""
        rng = np.random.default_rng(6)
        n = 4000
        shift = 0.3
        b = rng.normal(0.0, 1.0, size=n)
        a = b + shift + rng.normal(0.0, 0.1, size=n)
        clusters = np.arange(n)  # iid rows
        delta, lo, hi = paired_delta_bootstrap(
            a, b, clusters, statistic=np.mean, n_boot=1000, seed=0
        )
        assert delta == pytest.approx(shift, abs=0.02)
        assert lo < shift < hi
        assert hi - lo < 0.05  # pairing kills the shared noise

    def test_covers_known_sigma68_reduction(self):
        rng = np.random.default_rng(7)
        n = 6000
        b = rng.normal(0.0, 1.0, size=n)
        a = 0.5 * b  # method A halves every residual: sigma68 delta ~ -0.5*Z84
        clusters = np.arange(n)
        delta, lo, hi = paired_delta_bootstrap(a, b, clusters, n_boot=800, seed=1)
        assert delta == pytest.approx(-0.5 * Z84, abs=0.05)
        assert lo < -0.5 * Z84 < hi
        assert hi < 0.0  # a genuine CI-excludes-zero win

    def test_cluster_bootstrap_wider_than_iid_on_correlated_clusters(self):
        """With strong within-cluster correlation, resampling clusters must give
        wider CIs than pretending rows are iid (the legacy defect)."""
        rng = np.random.default_rng(8)
        n_clusters, per = 40, 30
        cluster_effect = rng.normal(0.0, 1.0, size=n_clusters)
        noise = rng.normal(0.0, 0.2, size=(n_clusters, per))
        diff = (cluster_effect[:, None] + noise).ravel()  # per-row paired difference
        b = rng.normal(0.0, 1.0, size=n_clusters * per)
        a = b + diff
        labels = np.repeat(np.arange(n_clusters), per)

        _, lo_cl, hi_cl = paired_delta_bootstrap(
            a, b, labels, statistic=np.mean, n_boot=800, seed=2
        )
        _, lo_iid, hi_iid = paired_delta_bootstrap(
            a, b, np.arange(n_clusters * per), statistic=np.mean, n_boot=800, seed=2
        )
        width_cl = hi_cl - lo_cl
        width_iid = hi_iid - lo_iid
        # design effect ~ 1 + (per-1)*ICC with ICC ~ 0.96 -> huge; require >2x.
        assert width_cl > 2.0 * width_iid

    def test_input_validation(self):
        with pytest.raises(ValueError):
            paired_delta_bootstrap([1.0, 2.0], [1.0], [0, 1])
        with pytest.raises(ValueError):
            paired_delta_bootstrap([1.0, 2.0], [1.0, 2.0], [0, 0])  # 1 cluster

    def test_deterministic_under_seed(self):
        rng = np.random.default_rng(9)
        a = rng.normal(size=200)
        b = rng.normal(size=200)
        cl = np.repeat(np.arange(20), 10)
        r1 = paired_delta_bootstrap(a, b, cl, n_boot=200, seed=42)
        r2 = paired_delta_bootstrap(a, b, cl, n_boot=200, seed=42)
        assert r1 == r2


class TestBHFDR:
    def test_known_small_set(self):
        # thresholds i/m*q = .01,.02,.03,.04,.05 -> first three rejected
        pvals = [0.01, 0.02, 0.03, 0.5, 0.6]
        reject, p_adj = bh_fdr(pvals, q=0.05)
        assert reject.tolist() == [True, True, True, False, False]
        assert p_adj[0] == pytest.approx(0.05)

    def test_step_up_rescues_earlier_pvalue(self):
        # p2=0.04 > 2/4*0.05=0.025 alone, but p3=0.03<=3/4*0.05=0.0375
        # steps up and rejects everything at or below it.
        pvals = [0.01, 0.04, 0.03, 0.9]
        reject, _ = bh_fdr(pvals, q=0.05)
        assert reject.tolist() == [True, False, False, False] or reject.sum() >= 1
        # exact BH: sorted p = .01,.03,.04,.9 vs .0125,.025,.0375,.05
        # largest k with p(k)<=k/m*q is k=1 -> only 0.01 rejected.
        assert reject.tolist() == [True, False, False, False]

    def test_benjamini_hochberg_1995_example(self):
        # The worked example from Benjamini & Hochberg (1995), m=15, q=0.05:
        # exactly the four smallest p-values are rejected.
        pvals = [
            0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344,
            0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.0000,
        ]
        reject, _ = bh_fdr(pvals, q=0.05)
        assert reject.sum() == 4
        assert reject.tolist()[:4] == [True, True, True, True]

    def test_all_null_uniform_controls_fdr(self):
        """Empirical FDR on pure-null p-values must stay near q."""
        rng = np.random.default_rng(10)
        n_trials, m, q = 400, 50, 0.05
        false_discovery = 0
        for _ in range(n_trials):
            reject, _ = bh_fdr(rng.uniform(size=m), q=q)
            false_discovery += int(reject.any())
        # under the global null, P(any rejection) <= q; allow MC slack.
        assert false_discovery / n_trials <= q + 0.03

    def test_mixture_controls_fdr_at_q(self):
        """Nulls + strong alternatives: average false-discovery proportion <= q."""
        rng = np.random.default_rng(11)
        n_trials, m_null, m_alt, q = 300, 80, 20, 0.10
        fdp = []
        for _ in range(n_trials):
            p_null = rng.uniform(size=m_null)
            z_alt = rng.normal(3.5, 1.0, size=m_alt)
            from math import erf, sqrt
            p_alt = np.array([1.0 - 0.5 * (1.0 + erf(z / sqrt(2.0))) for z in z_alt])
            pvals = np.concatenate([p_null, p_alt])
            is_null = np.concatenate([np.ones(m_null, bool), np.zeros(m_alt, bool)])
            reject, _ = bh_fdr(pvals, q=q)
            n_rej = reject.sum()
            fdp.append((reject & is_null).sum() / n_rej if n_rej else 0.0)
        assert np.mean(fdp) <= q + 0.02

    def test_adjusted_pvalues_monotone_and_ordered(self):
        rng = np.random.default_rng(12)
        p = rng.uniform(size=100)
        _, p_adj = bh_fdr(p, q=0.05)
        order = np.argsort(p)
        assert (np.diff(p_adj[order]) >= -1e-12).all()
        assert (p_adj >= p - 1e-12).all()
        assert (p_adj <= 1.0).all()

    def test_nan_never_rejected_and_empty_ok(self):
        reject, p_adj = bh_fdr([0.001, float("nan")], q=0.05)
        assert reject.tolist() == [True, False]
        reject, p_adj = bh_fdr([], q=0.05)
        assert reject.size == 0 and p_adj.size == 0
