"""Unit tests for the S25 (B-M4) covariance PSD-projection + inverse-variance
combination math. The heavy data pipeline (uproot / s22 loaders) is imported
lazily inside the script's ``main``; loading the module here exercises only the
pure-numpy helpers.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_s25():
    path = ROOT / "scripts" / "s25_covariance_timing.py"
    spec = importlib.util.spec_from_file_location("s25_covariance_timing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s25 = _load_s25()


# --------------------------------------------------------------------------
# nearest_psd
# --------------------------------------------------------------------------
def test_nearest_psd_idempotent_on_psd():
    rng = np.random.default_rng(0)
    a = rng.standard_normal((3, 4))
    psd = a @ a.T  # PSD by construction
    out = s25.nearest_psd(psd)
    assert np.allclose(out, psd, atol=1e-9)
    # eigenvalues all non-negative
    assert np.min(np.linalg.eigvalsh(out)) >= -1e-9


def test_nearest_psd_fixes_indefinite():
    # the WITHDRAWN pathology: diagonal small, huge off-diagonal -> indefinite
    bad = np.array([[0.52, 16.0, 16.0],
                    [16.0, 2.10, 16.0],
                    [16.0, 16.0, 0.93]])
    assert np.min(np.linalg.eigvalsh(bad)) < 0  # confirm indefinite
    out = s25.nearest_psd(bad)
    assert np.min(np.linalg.eigvalsh(out)) >= -1e-9
    assert np.allclose(out, out.T)


def test_nearest_psd_symmetrises():
    m = np.array([[1.0, 0.4, 0.0], [0.2, 1.0, 0.1], [0.0, 0.1, 1.0]])
    out = s25.nearest_psd(m)
    assert np.allclose(out, out.T)


# --------------------------------------------------------------------------
# triangle_variances
# --------------------------------------------------------------------------
def test_triangle_recovers_known_variances():
    s = {"B4": 1.45, "B6": 0.72, "B8": 0.93}
    v = {"B4-B6": s["B4"] ** 2 + s["B6"] ** 2,
         "B4-B8": s["B4"] ** 2 + s["B8"] ** 2,
         "B6-B8": s["B6"] ** 2 + s["B8"] ** 2}
    tri = s25.triangle_variances(v)
    for k in s:
        assert tri[k] == pytest.approx(s[k] ** 2, rel=1e-9)


def test_triangle_negative_when_correlated():
    # if a pair variance is suppressed by positive correlation the triangle can
    # return a negative per-stave variance (flagged by the caller)
    v = {"B4-B6": 0.10, "B4-B8": 0.10, "B6-B8": 4.0}
    tri = s25.triangle_variances(v)
    assert tri["B4"] < 0  # (0.1 + 0.1 - 4)/2 = -1.9


# --------------------------------------------------------------------------
# inverse_variance_combined
# --------------------------------------------------------------------------
def test_inverse_variance_diagonal_matches_formula():
    var = [1.45 ** 2, 0.72 ** 2, 0.93 ** 2]
    res = s25.inverse_variance_combined(var)
    expected = 1.0 / sum(1.0 / v for v in var)
    assert res["combined_var"] == pytest.approx(expected, rel=1e-9)
    assert res["combined_sigma"] == pytest.approx(math.sqrt(expected), rel=1e-9)
    # weights sum to 1 and favour the smallest variance
    assert sum(res["weights"]) == pytest.approx(1.0, rel=1e-9)
    assert res["weights"][1] == max(res["weights"])  # B6 smallest sigma


def test_inverse_variance_gls_equals_diagonal_when_uncorrelated():
    var = np.array([1.45 ** 2, 0.72 ** 2, 0.93 ** 2])
    diag = s25.inverse_variance_combined(var)
    gls = s25.inverse_variance_combined(var, cov=np.diag(var))
    assert gls["combined_var"] == pytest.approx(diag["combined_var"], rel=1e-9)


def test_inverse_variance_gls_matches_known_2x2():
    # closed form for a 2x2 with correlation rho:
    # combined var (GLS, estimating a common mean) =
    #   (s1^2 s2^2 (1-rho^2)) / (s1^2 + s2^2 - 2 rho s1 s2)
    s1, s2, rho = 1.0, 2.0, 0.5
    cov = np.array([[s1 ** 2, rho * s1 * s2], [rho * s1 * s2, s2 ** 2]])
    res = s25.inverse_variance_combined([s1 ** 2, s2 ** 2], cov=cov)
    expected = (s1 ** 2 * s2 ** 2 * (1 - rho ** 2)) / (s1 ** 2 + s2 ** 2 - 2 * rho * s1 * s2)
    assert res["combined_var"] == pytest.approx(expected, rel=1e-9)


# --------------------------------------------------------------------------
# cauchy_schwarz_bounds
# --------------------------------------------------------------------------
def test_cauchy_schwarz_orders_bounds():
    sig = [1.45, 0.72, 0.93]
    b = s25.cauchy_schwarz_bounds(sig)
    assert b["psd_floor_sigma"] <= b["independence_sigma"] <= b["fully_correlated_sigma"]
    # fully-correlated upper equals sum of weighted sigmas
    inv = 1.0 / np.array(sig) ** 2
    w = inv / inv.sum()
    assert b["fully_correlated_sigma"] == pytest.approx(float(np.sum(w * np.array(sig))), rel=1e-9)


# --------------------------------------------------------------------------
# robust_cov3 + sigma68
# --------------------------------------------------------------------------
def test_robust_cov3_recovers_correlation():
    rng = np.random.default_rng(1)
    n = 200_000
    common = rng.standard_normal(n) * 1.5  # common mode
    y = np.column_stack([
        common + rng.standard_normal(n) * 1.0,
        common + rng.standard_normal(n) * 0.7,
        common + rng.standard_normal(n) * 0.9,
    ])
    cov = s25.nearest_psd(s25.robust_cov3(y))
    # off-diagonals should all be ~ Var(common) = 2.25
    assert cov[0, 1] == pytest.approx(2.25, abs=0.15)
    assert cov[0, 2] == pytest.approx(2.25, abs=0.15)
    assert cov[1, 2] == pytest.approx(2.25, abs=0.15)
    # triangle recovers the intrinsic variances (common mode cancels)
    tri = s25.triangle_variances(s25.pairwise_variances(y))
    assert tri["B4"] == pytest.approx(1.0, abs=0.1)
    assert tri["B6"] == pytest.approx(0.49, abs=0.1)
    assert tri["B8"] == pytest.approx(0.81, abs=0.1)


def test_sigma68_gaussian():
    rng = np.random.default_rng(2)
    x = rng.standard_normal(500_000)
    assert s25.sigma68(x) == pytest.approx(1.0, abs=0.02)
