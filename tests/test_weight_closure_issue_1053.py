"""Issue #1053: Legacy weight retirement closure study.

Three closure items:
1. Direct-sampling vs corrected-legacy-reweighting closure with identical source table/support
2. Equal-distribution test on downstream truth observables (generator-level, no detector response)
3. Representation-splitting invariant: duplicate events with divided analysis weight
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy import stats

from ccb_mc_validation.truth.weight_adapter import (
    LEGACY_CM_EKIN_BEAM,
    LEGACY_CM_M1,
    LEGACY_CM_M2,
    LEGACY_CM_OFFSET,
    _interp_s21b,
    _read_sigma_table,
)

# Sigma table path (relative to repo root)
SIGMA_TABLE_PATH = Path(__file__).resolve().parent.parent / "geant4/src_patch/sigma_pd_cm_190.txt"


def _theta_cm_to_lab(theta_cm_deg: np.ndarray) -> np.ndarray:
    """Convert CM angle to lab angle via two-body kinematics (S21b exact)."""
    theta_cm_rad = np.radians(theta_cm_deg)
    e1 = LEGACY_CM_EKIN_BEAM + LEGACY_CM_M1
    p1 = math.sqrt(LEGACY_CM_EKIN_BEAM**2 + 2.0 * LEGACY_CM_EKIN_BEAM * LEGACY_CM_M1)
    beta = p1 / (e1 + LEGACY_CM_M2)
    
    # Relativistic aberration: cos(theta_lab) = (cos(theta_cm) + beta) / (1 + beta*cos(theta_cm))
    cos_theta_lab = (np.cos(theta_cm_rad) + beta) / (1.0 + beta * np.cos(theta_cm_rad))
    cos_theta_lab = np.clip(cos_theta_lab, -1.0, 1.0)
    theta_lab_rad = np.arccos(cos_theta_lab)
    return np.degrees(theta_lab_rad)


class DirectCDFSampler:
    """Direct-CDF sampler matching patched ScatteringGenerator.cc exactly.

    Samples theta_cm directly from a sigma*sin(theta) CDF with unit event weight,
    restricted to the measured support [26.49, 169.78] degrees.
    """

    def __init__(self, sigma_table_path: Path | None = None):
        if sigma_table_path is None:
            sigma_table_path = SIGMA_TABLE_PATH
        self.angles_deg, self.sigma, _ = _read_sigma_table(sigma_table_path)
        
        # Convert to radians for computation
        self.ang_rad = np.radians(self.angles_deg)
        
        # Compute PDF: p(theta) ∝ sigma(theta) * sin(theta)
        self.pdf = self.sigma * np.sin(self.ang_rad)
        
        # Build CDF using trapezoidal integration (matches C++ implementation)
        n = len(self.ang_rad)
        self.cdf = np.zeros(n)
        for i in range(1, n):
            width = self.ang_rad[i] - self.ang_rad[i-1]
            avg_pdf = 0.5 * (self.pdf[i-1] + self.pdf[i])
            self.cdf[i] = self.cdf[i-1] + avg_pdf * width
        
        # Normalize CDF to [0, 1]
        self.cdf /= self.cdf[-1]
        
        # Store support boundaries
        self.support_min_deg = float(self.angles_deg[0])
        self.support_max_deg = float(self.angles_deg[-1])

    def sample(self, n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
        """Sample n events using the exact piecewise-linear inverse CDF method."""
        u = rng.uniform(0.0, 1.0, n)
        theta_cm_rad = self._inverse_cdf_piecewise_linear(u)
        theta_cm_deg = np.degrees(theta_cm_rad)
        theta_lab_deg = _theta_cm_to_lab(theta_cm_deg)
        
        return {
            "theta_cm_deg": theta_cm_deg,
            "theta_lab_deg": theta_lab_deg,
            "event_weight": np.ones(n),
        }

    def _inverse_cdf_piecewise_linear(self, u: np.ndarray) -> np.ndarray:
        """Compute inverse CDF assuming piecewise-linear PDF (C++ method)."""
        result = np.empty_like(u)
        
        for idx, ui in enumerate(u):
            # Find the CDF bin
            bin_idx = np.searchsorted(self.cdf, ui)
            
            if bin_idx == 0:
                result[idx] = self.ang_rad[0]
            elif bin_idx >= len(self.ang_rad):
                result[idx] = self.ang_rad[-1]
            else:
                # Inverse CDF within the bin (piecewise-linear PDF)
                c0, c1 = self.cdf[bin_idx-1], self.cdf[bin_idx]
                if c1 <= c0:  # Degenerate bin
                    result[idx] = self.ang_rad[bin_idx-1]
                    continue
                
                frac = (ui - c0) / (c1 - c0)
                left, right = self.ang_rad[bin_idx-1], self.ang_rad[bin_idx]
                width = right - left
                a, b = self.pdf[bin_idx-1], self.pdf[bin_idx]
                
                # Mass of the entire interval
                interval_mass = 0.5 * (a + b) * width
                if interval_mass <= 0:
                    result[idx] = left
                    continue
                
                # Target mass from the left edge
                target_mass = frac * interval_mass
                
                # Solve: a*y + 0.5*slope*y^2 = target_mass, where y = x - left
                slope = (b - a) / width if width > 0 else 0
                
                discriminant = a*a + 2.0 * slope * target_mass
                if discriminant < 0:
                    if discriminant > -1e-14:
                        discriminant = 0.0
                    else:
                        result[idx] = left
                        continue
                
                root = math.sqrt(discriminant)
                if slope != 0:
                    y = (root - a) / slope
                else:
                    y = target_mass / a if a > 0 else 0
                
                result[idx] = left + np.clip(y, 0, width)
        
        return result


class LegacyUniformSampler:
    """Legacy uniform theta_cm sampler + corrected analysis weight.

    Uses uniform proposal q(theta_cm) = 1/pi over the MEASURED SUPPORT
    [26.49, 169.78] degrees with corrected weight
    w*(theta_cm) ∝ sigma_cm(theta_cm) * sin(theta_cm).
    
    This is restricted to the measured support for closure with the direct sampler.
    """

    def __init__(self, sigma_table_path: Path | None = None):
        if sigma_table_path is None:
            sigma_table_path = SIGMA_TABLE_PATH
        self.angles_deg, self.sigma, _ = _read_sigma_table(sigma_table_path)
        self.ang_rad = np.radians(self.angles_deg)
        self.sigma_vals = self.sigma
        
        # Store support boundaries (same as direct sampler)
        self.support_min_deg = float(self.angles_deg[0])
        self.support_max_deg = float(self.angles_deg[-1])

    def sample(self, n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
        """Sample n events from uniform theta_cm over measured support + corrected weight."""
        # Legacy proposal: theta_cm uniform over measured support
        theta_cm_deg = rng.uniform(self.support_min_deg, self.support_max_deg, n)
        
        # Compute corrected weight: w ∝ sigma_cm(theta_cm) * sin(theta_cm)
        theta_cm_rad = np.radians(theta_cm_deg)
        sigma_cm = _interp_s21b(theta_cm_rad, self.ang_rad, self.sigma_vals)
        sin_theta_cm = np.sin(theta_cm_rad)
        event_weight = sigma_cm * sin_theta_cm
        
        # Compute theta_lab using same kinematics
        theta_lab_deg = _theta_cm_to_lab(theta_cm_deg)
        
        return {
            "theta_cm_deg": theta_cm_deg,
            "theta_lab_deg": theta_lab_deg,
            "event_weight": event_weight,
        }


class UncorrectedLegacySampler:
    """Negative control: legacy sampler with WRONG weight.

    Uses sigma(theta_lab) without the sin(theta_cm) factor.
    This MUST FAIL the equal-distribution test.
    """

    def __init__(self, sigma_table_path: Path | None = None):
        if sigma_table_path is None:
            sigma_table_path = SIGMA_TABLE_PATH
        self.angles_deg, self.sigma, _ = _read_sigma_table(sigma_table_path)
        self.ang_rad = np.radians(self.angles_deg)
        self.sigma_vals = self.sigma
        
        self.support_min_deg = float(self.angles_deg[0])
        self.support_max_deg = float(self.angles_deg[-1])

    def sample(self, n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
        """Sample n events with the WRONG weight (negative control)."""
        theta_cm_deg = rng.uniform(self.support_min_deg, self.support_max_deg, n)
        theta_lab_deg = _theta_cm_to_lab(theta_cm_deg)
        theta_lab_rad = np.radians(theta_lab_deg)
        
        # WRONG: use sigma_cm (without sin factor) instead of sigma_cm*sin(theta_cm)
        sigma_cm = _interp_s21b(np.radians(theta_cm_deg), self.ang_rad, self.sigma_vals)
        event_weight = sigma_cm  # Missing sin(theta_cm) factor
        
        return {
            "theta_cm_deg": theta_cm_deg,
            "theta_lab_deg": theta_lab_deg,
            "event_weight": event_weight,
        }


def run_ks_test(
    sample1: np.ndarray, weight1: np.ndarray,
    sample2: np.ndarray, weight2: np.ndarray,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Run a two-sample KS test with weighted data using bootstrap."""
    def weighted_ecdf(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        sort_idx = np.argsort(values)
        sorted_values = values[sort_idx]
        sorted_weights = weights[sort_idx]
        cumsum = np.cumsum(sorted_weights)
        total = cumsum[-1] if cumsum[-1] > 0 else 1.0
        cumsum /= total
        return sorted_values, cumsum

    x1, f1 = weighted_ecdf(sample1, weight1)
    x2, f2 = weighted_ecdf(sample2, weight2)

    all_x = np.union1d(x1, x2)
    f1_interp = np.interp(all_x, x1, f1, left=0.0, right=1.0)
    f2_interp = np.interp(all_x, x2, f2, left=0.0, right=1.0)
    ks_observed = np.max(np.abs(f1_interp - f2_interp))

    # Bootstrap for p-value
    rng_bootstrap = np.random.default_rng(42)
    n1, n2 = len(sample1), len(sample2)
    ks_bootstrap = np.empty(n_bootstrap, dtype=float)
    
    pooled_values = np.concatenate([sample1, sample2])
    pooled_weights = np.concatenate([weight1, weight2])
    
    for i in range(n_bootstrap):
        idx1 = rng_bootstrap.choice(len(pooled_values), n1, replace=True)
        idx2 = rng_bootstrap.choice(len(pooled_values), n2, replace=True)
        
        rx1, rf1 = weighted_ecdf(pooled_values[idx1], pooled_weights[idx1])
        rx2, rf2 = weighted_ecdf(pooled_values[idx2], pooled_weights[idx2])
        
        rall_x = np.union1d(rx1, rx2)
        rf1_interp = np.interp(rall_x, rx1, rf1, left=0.0, right=1.0)
        rf2_interp = np.interp(rall_x, rx2, rf2, left=0.0, right=1.0)
        ks_bootstrap[i] = np.max(np.abs(rf1_interp - rf2_interp))
    
    p_value = np.mean(ks_bootstrap >= ks_observed)
    
    return {
        "ks_statistic": float(ks_observed),
        "p_value": float(p_value),
        "reject_null": bool(p_value < alpha),
        "alpha": alpha,
    }


def test_direct_vs_legacy_corrected_closure():
    """Closure item 1: direct-CDF vs corrected-legacy-reweighting."""
    rng = np.random.default_rng(1053)
    n_events = 10000
    
    direct = DirectCDFSampler().sample(n_events, rng)
    legacy = LegacyUniformSampler().sample(n_events, rng)
    
    ks_theta_cm = run_ks_test(
        direct["theta_cm_deg"], direct["event_weight"],
        legacy["theta_cm_deg"], legacy["event_weight"],
        n_bootstrap=500,
    )
    ks_theta_lab = run_ks_test(
        direct["theta_lab_deg"], direct["event_weight"],
        legacy["theta_lab_deg"], legacy["event_weight"],
        n_bootstrap=500,
    )
    
    assert ks_theta_cm["p_value"] > 0.05, (
        f"Direct vs legacy corrected theta_cm FAILED: p={ks_theta_cm['p_value']:.4f}"
    )
    assert ks_theta_lab["p_value"] > 0.05, (
        f"Direct vs legacy corrected theta_lab FAILED: p={ks_theta_lab['p_value']:.4f}"
    )
    
    test_direct_vs_legacy_corrected_closure.results = {
        "ks_theta_cm": ks_theta_cm,
        "ks_theta_lab": ks_theta_lab,
        "n_events": n_events,
    }


def test_negative_control_uncorrected_legacy():
    """Negative control: uncorrected legacy weight MUST FAIL."""
    rng = np.random.default_rng(1053)
    n_events = 10000
    
    direct = DirectCDFSampler().sample(n_events, rng)
    uncorrected = UncorrectedLegacySampler().sample(n_events, rng)
    
    ks_theta_cm = run_ks_test(
        direct["theta_cm_deg"], direct["event_weight"],
        uncorrected["theta_cm_deg"], uncorrected["event_weight"],
        n_bootstrap=500,
    )
    ks_theta_lab = run_ks_test(
        direct["theta_lab_deg"], direct["event_weight"],
        uncorrected["theta_lab_deg"], uncorrected["event_weight"],
        n_bootstrap=500,
    )
    
    assert ks_theta_cm["p_value"] < 0.01, (
        f"Negative control theta_cm lacks power: p={ks_theta_cm['p_value']:.4f}"
    )
    assert ks_theta_lab["p_value"] < 0.01, (
        f"Negative control theta_lab lacks power: p={ks_theta_lab['p_value']:.4f}"
    )
    
    test_negative_control_uncorrected_legacy.results = {
        "ks_theta_cm": ks_theta_cm,
        "ks_theta_lab": ks_theta_lab,
        "n_events": n_events,
    }


def test_representation_splitting_invariant():
    """Closure item 3: representation-splitting invariant."""
    rng = np.random.default_rng(1053)
    n_events = 5000
    k = 3
    
    original = DirectCDFSampler().sample(n_events, rng)
    
    split_theta_cm = np.repeat(original["theta_cm_deg"], k)
    split_theta_lab = np.repeat(original["theta_lab_deg"], k)
    split_weight = np.repeat(original["event_weight"] / k, k)
    
    ks_theta_cm = run_ks_test(
        original["theta_cm_deg"], original["event_weight"],
        split_theta_cm, split_weight,
        n_bootstrap=500,
    )
    ks_theta_lab = run_ks_test(
        original["theta_lab_deg"], original["event_weight"],
        split_theta_lab, split_weight,
        n_bootstrap=500,
    )
    
    assert ks_theta_cm["p_value"] > 0.05, (
        f"Representation splitting theta_cm FAILED: p={ks_theta_cm['p_value']:.4f}"
    )
    assert ks_theta_lab["p_value"] > 0.05, (
        f"Representation splitting theta_lab FAILED: p={ks_theta_lab['p_value']:.4f}"
    )
    
    test_representation_splitting_invariant.results = {
        "ks_theta_cm": ks_theta_cm,
        "ks_theta_lab": ks_theta_lab,
        "n_events": n_events,
        "k": k,
    }


def test_sigma_table_contract():
    """Verify the sigma table has the expected format and support."""
    angles_deg, sigma, stat_uncertainty = _read_sigma_table(SIGMA_TABLE_PATH)
    
    assert len(angles_deg) == 28, f"Expected 28 rows, got {len(angles_deg)}"
    assert angles_deg[0] == pytest.approx(26.49, abs=0.01)
    assert angles_deg[-1] == pytest.approx(169.78, abs=0.01)
    assert np.all(sigma > 0), "All sigma values must be positive"
    assert np.all(np.isfinite(sigma)), "All sigma values must be finite"
    assert np.all(np.diff(angles_deg) > 0), "Angles must be strictly increasing"
    
    test_sigma_table_contract.table_info = {
        "n_rows": len(angles_deg),
        "support_deg": (float(angles_deg[0]), float(angles_deg[-1])),
        "sigma_min": float(np.min(sigma)),
        "sigma_max": float(np.max(sigma)),
    }


@pytest.mark.parametrize("sample_size", [100, 1000, 10000])
def test_closure_holds_across_sample_sizes(sample_size):
    """Closure must hold across different sample sizes."""
    rng = np.random.default_rng(1053)
    
    direct = DirectCDFSampler().sample(sample_size, rng)
    legacy = LegacyUniformSampler().sample(sample_size, rng)
    
    ks = run_ks_test(
        direct["theta_cm_deg"], direct["event_weight"],
        legacy["theta_cm_deg"], legacy["event_weight"],
        n_bootstrap=200,
    )
    
    assert ks["p_value"] > 0.05, (
        f"Closure failed at sample_size={sample_size}: p={ks['p_value']:.4f}"
    )


def test_closure_summary_report() -> dict[str, Any]:
    """Aggregate all closure test results into a summary report."""
    summary = {
        "test_name": "weight_closure_issue_1053",
        "sigma_table": getattr(test_sigma_table_contract, "table_info", {}),
        "direct_vs_legacy_corrected": getattr(
            test_direct_vs_legacy_corrected_closure, "results", {}
        ),
        "negative_control": getattr(
            test_negative_control_uncorrected_legacy, "results", {}
        ),
        "representation_splitting": getattr(
            test_representation_splitting_invariant, "results", {}
        ),
    }
    
    verdict = "PASS" if all([
        summary["direct_vs_legacy_corrected"].get("ks_theta_cm", {}).get("p_value", 0) > 0.05,
        summary["direct_vs_legacy_corrected"].get("ks_theta_lab", {}).get("p_value", 0) > 0.05,
        summary["negative_control"].get("ks_theta_cm", {}).get("p_value", 1) < 0.01,
        summary["negative_control"].get("ks_theta_lab", {}).get("p_value", 1) < 0.01,
        summary["representation_splitting"].get("ks_theta_cm", {}).get("p_value", 0) > 0.05,
        summary["representation_splitting"].get("ks_theta_lab", {}).get("p_value", 0) > 0.05,
    ]) else "FAIL"
    
    summary["verdict"] = verdict
    summary["issue"] = "#1053"
    summary["description"] = (
        "Legacy PrimaryWeight=σ(theta_lab) retirement closure study"
    )
    
    return summary
