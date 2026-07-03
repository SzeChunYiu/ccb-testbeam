"""Fixture tests for the S23 double-ratio computation.

The double ratio DR = [f(B2,I)/f(B2,II)]_data / [f(B2,I)/f(B2,II)]_mc is the
gain/geometry-robust observable of the Sample I/II study. These tests pin:
  * the exact value on a hand-computed fixture;
  * invariance under a sample-wide multiplicative factor (the gain/geometry
    cancellation that justifies the observable);
  * DR = 1 with a covering CI when MC reproduces the data enrichment;
  * the direction and CI ordering of the log-normal interval;
  * degenerate-count handling (NaN, not a crash);
  * Wilson/occupancy chi2 helpers used by the same report.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import s23_sample12_data_mc_comparison as s23  # noqa: E402

# Hand-built fixture: data B2 occupancy 60/100 (I) vs 30/100 (II) -> R_data=2;
# MC 40/100 vs 20/100 -> R_mc=2 -> DR=1.
FIX_MATCH = dict(kI_d=60, nI_d=100, kII_d=30, nII_d=100,
                 kI_m=40, nI_m=100, kII_m=20, nII_m=100)


def test_double_ratio_exact_value():
    rec = s23.double_ratio(kI_d=90, nI_d=100, kII_d=30, nII_d=100,
                           kI_m=60, nI_m=100, kII_m=40, nII_m=100)
    # R_data = 0.9/0.3 = 3, R_mc = 0.6/0.4 = 1.5, DR = 2
    assert rec["ratio_data"][0] == pytest.approx(3.0)
    assert rec["ratio_mc"][0] == pytest.approx(1.5)
    assert rec["dr"] == pytest.approx(2.0)


def test_double_ratio_ci_is_lognormal_and_ordered():
    rec = s23.double_ratio(**FIX_MATCH)
    assert rec["dr_lo"] < rec["dr"] < rec["dr_hi"]
    # log-normal CI: symmetric in log space
    assert math.log(rec["dr"] / rec["dr_lo"]) == pytest.approx(
        math.log(rec["dr_hi"] / rec["dr"]))
    # width matches the analytic propagation var(log f) = (1-f)/k
    s = math.sqrt(sum((1 - k / n) / k for k, n in
                      [(60, 100), (30, 100), (40, 100), (20, 100)]))
    assert rec["dr_hi"] / rec["dr"] == pytest.approx(math.exp(s23.Z95 * s))


def test_double_ratio_unity_when_mc_matches_and_ci_covers_one():
    rec = s23.double_ratio(**FIX_MATCH)
    assert rec["dr"] == pytest.approx(1.0)
    assert rec["dr_lo"] < 1.0 < rec["dr_hi"]
    assert abs(rec["z_vs_1"]) < 1e-9


def test_double_ratio_gain_geometry_invariance():
    """Scaling every stave count within a sample by a common acceptance/gain
    factor must leave DR untouched — the cancellation the study relies on."""
    base = s23.double_ratio(**FIX_MATCH)
    scaled = s23.double_ratio(kI_d=60 * 7, nI_d=100 * 7, kII_d=30 * 3, nII_d=100 * 3,
                              kI_m=40 * 5, nI_m=100 * 5, kII_m=20 * 2, nII_m=100 * 2)
    assert scaled["dr"] == pytest.approx(base["dr"])


def test_double_ratio_detects_mc_deficit():
    """If MC under-produces the Sample-I enrichment, DR > 1 and z > 0."""
    rec = s23.double_ratio(kI_d=6000, nI_d=10000, kII_d=3000, nII_d=10000,
                           kI_m=4000, nI_m=10000, kII_m=3900, nII_m=10000)
    assert rec["dr"] > 1.5
    assert rec["z_vs_1"] > 3.0
    assert rec["dr_lo"] > 1.0


def test_double_ratio_degenerate_counts_nan():
    rec = s23.double_ratio(kI_d=0, nI_d=100, kII_d=30, nII_d=100,
                           kI_m=40, nI_m=100, kII_m=20, nII_m=100)
    assert math.isnan(rec["dr"])


def test_ratio_ci_center_and_coverage_direction():
    r, lo, hi = s23.ratio_ci(50, 100, 25, 100)
    assert r == pytest.approx(2.0)
    assert lo < 2.0 < hi


def test_wilson_ci_basics():
    lo, hi = s23.wilson_ci(50, 100)
    assert lo < 0.5 < hi
    assert 0.0 <= lo and hi <= 1.0
    lo0, hi0 = s23.wilson_ci(0, 100)
    assert lo0 == pytest.approx(0.0, abs=1e-12) and hi0 < 0.05


def test_occupancy_chi2_zero_for_identical_shares():
    counts = {"B2": 800, "B4": 120, "B6": 60, "B8": 20}
    res = s23.occupancy_chi2(counts, {k: 3 * v for k, v in counts.items()})
    assert res["chi2"] == pytest.approx(0.0, abs=1e-12)
    assert res["dof"] == 3


def test_ks_distance_matches_known_case():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([3.0, 4.0, 5.0, 6.0])
    assert s23.ks_distance(x, y) == pytest.approx(0.5)
    assert s23.ks_distance(x, x) == 0.0
