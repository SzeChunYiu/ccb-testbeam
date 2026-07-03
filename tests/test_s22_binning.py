"""Synthetic-fixture tests for scripts/s22_timing_vs_amplitude.py.

Covers the three contract items:
  1. the sigma68 estimator,
  2. per-pair centering removes a constant (cable-delay-like) offset,
  3. the amplitude bin edges / assignment used for the min-pair-amplitude
     binning.
Plus a check of the rising-edge-constrained CFD20 on a synthetic waveform.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

s22 = pytest.importorskip("s22_timing_vs_amplitude")


# ---------------------------------------------------------------- sigma68
def test_sigma68_matches_manual_quantiles():
    rng = np.random.default_rng(7)
    values = rng.normal(3.0, 2.0, size=5001)
    q16, q84 = np.percentile(values, [16.0, 84.0])
    assert s22.sigma68(values) == pytest.approx(0.5 * (q84 - q16))


def test_sigma68_gaussian_recovers_sigma():
    rng = np.random.default_rng(20260703)
    values = rng.normal(0.0, 1.234, size=200_000)
    # For a Gaussian, (q84-q16)/2 ~= 0.9945 sigma; 1% tolerance at this n.
    assert s22.sigma68(values) == pytest.approx(1.234 * 0.99446, rel=0.01)


def test_sigma68_shift_invariant_and_edge_cases():
    rng = np.random.default_rng(11)
    values = rng.normal(0.0, 0.7, size=4000)
    assert s22.sigma68(values + 123.4) == pytest.approx(s22.sigma68(values))
    assert np.isnan(s22.sigma68(np.array([])))
    with_nan = np.concatenate([values, [np.nan, np.inf]])
    assert s22.sigma68(with_nan) == pytest.approx(s22.sigma68(values))


# ------------------------------------------------- per-pair centering
def test_centering_removes_constant_pair_offsets():
    """Two pairs with identical spread but different cable-delay offsets:
    pooling WITHOUT centering inflates sigma68; per-pair centering restores
    the single-pair value exactly (up to sampling noise)."""
    rng = np.random.default_rng(42)
    n = 20000
    base = rng.normal(0.0, 1.0, size=n)
    pair_a = base + 5.0      # +5 ns cable offset
    pair_b = rng.normal(0.0, 1.0, size=n) - 3.0
    values = np.concatenate([pair_a, pair_b])
    pair_key = np.array(["A"] * n + ["B"] * n)
    run_key = np.zeros(2 * n, dtype=int)

    pooled_uncentered = s22.sigma68(values)
    centered = s22.center_per_group(values, [pair_key, run_key])
    pooled_centered = s22.sigma68(centered)

    assert pooled_uncentered > 2.0            # offsets dominate the quantiles
    assert pooled_centered == pytest.approx(1.0, rel=0.03)
    # centering is exactly a per-group median shift
    assert np.median(centered[:n]) == pytest.approx(0.0, abs=1e-12)
    assert np.median(centered[n:]) == pytest.approx(0.0, abs=1e-12)
    # and sigma68 within each group is untouched (shift invariance)
    assert s22.sigma68(centered[:n]) == pytest.approx(s22.sigma68(pair_a))


def test_centering_per_run_removes_run_drift():
    rng = np.random.default_rng(1)
    v1 = rng.normal(0.0, 0.5, size=5000)
    v2 = rng.normal(0.0, 0.5, size=5000)
    values = np.concatenate([v1 + 2.0, v2 - 2.0])
    pair_key = np.array(["A"] * 10000)
    run_key = np.array([58] * 5000 + [65] * 5000)
    centered = s22.center_per_group(values, [pair_key, run_key])
    assert s22.sigma68(centered) == pytest.approx(0.5, rel=0.05)


# ------------------------------------------------- amplitude binning
def test_amp_bin_edges_cover_required_range():
    edges = s22.amp_bin_edges()
    assert edges[0] == 1000.0                       # starts at the anchor cut
    assert np.isinf(edges[-1])                      # open-ended overflow bin
    n_bins = len(edges) - 1
    assert n_bins >= 6                              # required binning depth
    assert edges[-2] >= 8000.0                      # covers 1000-8000+ ADC
    assert np.all(np.diff(edges[:-1]) > 0)          # strictly increasing


def test_assign_amp_bins_boundaries_and_overflow():
    edges = s22.amp_bin_edges()
    e0, e1 = edges[0], edges[1]
    last_finite = edges[-2]
    values = np.array([e0 - 0.1, e0, e1 - 0.1, e1, last_finite - 0.1, last_finite, 5.0e5])
    idx = s22.assign_amp_bins(values, edges)
    assert idx[0] == -1                             # below selection -> no bin
    assert idx[1] == 0                              # left edge inclusive
    assert idx[2] == 0                              # just below the next edge
    assert idx[3] == 1                              # right edge exclusive
    assert idx[4] == len(edges) - 3                 # last finite bin
    assert idx[5] == len(edges) - 2                 # overflow bin
    assert idx[6] == len(edges) - 2                 # deep overflow stays in it


def test_assign_amp_bins_min_amp_semantics():
    """Binning uses the MIN amplitude of the pair."""
    amp_left = np.array([1200.0, 9000.0, 3500.0])
    amp_right = np.array([2600.0, 1100.0, 3400.0])
    min_amp = np.minimum(amp_left, amp_right)
    idx = s22.assign_amp_bins(min_amp)
    edges = s22.amp_bin_edges()
    for k, v in zip(idx, min_amp):
        assert edges[k] <= v < edges[k + 1]


# ------------------------------------------------- rising-edge CFD20
def test_cfd20_rising_edge_synthetic_crossing():
    """Triangle pulse with known 20% crossing; a pre-signal noise blip above
    threshold before the true edge must NOT capture the pick (the fixed
    scan takes the last below->above crossing at or before the peak)."""
    nsamp = 18
    wf = np.zeros(nsamp)
    wf[6:11] = [500.0, 1500.0, 3000.0, 2000.0, 1000.0]   # rise 6->8, peak at 8
    amp = np.array([3000.0])                              # threshold = 600
    t, valid = s22.cfd20_rising_edge(wf[None, :], amp)
    # crossing between samples 6 (500) and 7 (1500): 6 + (600-500)/1000 = 6.1
    assert valid[0]
    assert t[0] == pytest.approx(6.1 * s22.SAMPLE_PERIOD_NS)

    # add an early noise blip above threshold at samples 1-2; the last
    # rising-edge crossing before the peak is still the true edge at 6.1
    wf2 = wf.copy()
    wf2[1] = 700.0
    wf2[2] = 650.0
    t2, valid2 = s22.cfd20_rising_edge(wf2[None, :], amp)
    assert valid2[0]
    assert t2[0] == pytest.approx(6.1 * s22.SAMPLE_PERIOD_NS)
