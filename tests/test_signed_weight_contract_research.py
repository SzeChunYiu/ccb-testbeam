from __future__ import annotations

import importlib.util
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "research_signed_weight_contract.py"
spec = importlib.util.spec_from_file_location("research_signed_weight_contract", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_small_fixture_matches_exact_rational_oracle():
    got = mod.stable_signed_diagnostic([10.0, -9.0, 1.0])
    assert got.signed_ess_like == pytest.approx(float(Fraction(2, 91)))
    assert got.absolute_ess == pytest.approx(float(Fraction(200, 91)))
    assert got.max_abs_weight_fraction == pytest.approx(0.5)
    assert got.cancellation_severity == pytest.approx(0.9)
    assert got.signed_mass_orientation == 1


@pytest.mark.parametrize("scale", [1.0, 1e300, 1e-300])
def test_dimensionless_signed_diagnostics_are_positive_scale_invariant(scale: float):
    got = mod.stable_signed_diagnostic(
        scale * np.array([10.0, -9.0, 1.0], dtype=np.float64)
    )
    ref = mod.stable_signed_diagnostic([10.0, -9.0, 1.0])
    assert got.signed_ess_like == pytest.approx(ref.signed_ess_like)
    assert got.absolute_ess == pytest.approx(ref.absolute_ess)
    assert got.max_abs_weight_fraction == pytest.approx(ref.max_abs_weight_fraction)
    assert got.cancellation_severity == pytest.approx(ref.cancellation_severity)
    assert got.signed_mass_orientation == ref.signed_mass_orientation


def test_global_sign_flip_changes_orientation_not_cancellation_severity():
    positive_orientation = mod.stable_signed_diagnostic([10.0, -9.0, 1.0])
    negative_orientation = mod.stable_signed_diagnostic([-10.0, 9.0, -1.0])
    assert positive_orientation.cancellation_severity == pytest.approx(
        negative_orientation.cancellation_severity
    )
    assert positive_orientation.absolute_ess == pytest.approx(
        negative_orientation.absolute_ess
    )
    assert positive_orientation.signed_ess_like == pytest.approx(
        negative_orientation.signed_ess_like
    )
    assert positive_orientation.signed_mass_orientation == 1
    assert negative_orientation.signed_mass_orientation == -1


def test_legacy_cancellation_fraction_is_not_a_fraction_for_all_negative_weights():
    legacy = mod.legacy_raw_diagnostic([-1.0, -2.0])
    stable = mod.stable_signed_diagnostic([-1.0, -2.0])
    assert legacy["legacy_cancellation_fraction"] == pytest.approx(2.0)
    assert legacy["legacy_all_zero_predicate"] is True
    assert stable.cancellation_severity == pytest.approx(0.0)
    assert stable.signed_mass_orientation == -1
    assert stable.n_negative == 2
    assert stable.n_positive == 0


def test_exact_cancellation_separates_sampling_mass_from_net_signed_mass():
    got = mod.stable_signed_diagnostic([1.0, -1.0])
    assert got.cancellation_severity == pytest.approx(1.0)
    assert got.signed_ess_like == pytest.approx(0.0)
    assert got.absolute_ess == pytest.approx(2.0)
    assert got.signed_mass_orientation == 0


def test_binary64_boundary_keeps_scaled_diagnostics_when_raw_moments_fail():
    large = mod.run_research()["diagnostics"]["binary64_large"]
    assert large["legacy"]["sum_abs_w"] == "OVERFLOW:OverflowError"
    assert large["legacy"]["sum_w2"] == "NONFINITE"
    assert large["stable"]["absolute_ess"] == pytest.approx(float(Fraction(200, 91)))
    assert large["stable"]["cancellation_severity"] == pytest.approx(0.9)

    tiny = mod.run_research()["diagnostics"]["binary64_subnormal"]
    assert tiny["stable"]["absolute_ess"] == pytest.approx(3.0)
    assert tiny["stable"]["cancellation_severity"] == pytest.approx(2.0 / 3.0)


def test_signed_cumulative_mass_is_not_a_probability_ecdf():
    counterexample = mod.signed_cdf_counterexample()
    assert counterexample["cumulative_normalized_signed_mass"] == [1.0, -1.0, 1.0]
    assert counterexample["monotone_non_decreasing"] is False
    assert counterexample["inside_unit_interval"] is False


@pytest.mark.parametrize(
    "weights, message",
    [
        ([], "nonempty"),
        ([0.0, 0.0], "nonzero"),
        ([1.0, np.nan], "finite"),
        ([[1.0, -1.0]], "one-dimensional"),
    ],
)
def test_research_helper_fails_closed_on_invalid_fixture(weights, message):
    with pytest.raises(ValueError, match=message):
        mod.stable_signed_diagnostic(weights)
