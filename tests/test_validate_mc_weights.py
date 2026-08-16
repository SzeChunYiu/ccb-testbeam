from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "validate_mc_weights.py"
spec = importlib.util.spec_from_file_location("validate_mc_weights", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_unit_weights_have_ess_equal_n():
    audit = mod.summarize_weights(np.ones(10))
    assert audit.n == 10
    assert audit.sum_w == pytest.approx(10.0)
    assert audit.sum_w2 == pytest.approx(10.0)
    assert audit.signed_effective_sample_size == pytest.approx(10.0)
    assert audit.absolute_effective_sample_size == pytest.approx(10.0)
    assert audit.max_abs_weight_fraction == pytest.approx(0.1)
    assert audit.all_unit_weights is True
    assert audit.signed_mass_orientation == 1
    assert audit.cancellation_severity == pytest.approx(0.0)


def test_nonuniform_positive_weights_reduce_effective_sample_size():
    audit = mod.summarize_weights([1.0, 1.0, 8.0])
    expected = (10.0**2) / (1.0 + 1.0 + 64.0)
    assert audit.absolute_effective_sample_size == pytest.approx(expected)
    assert audit.absolute_effective_sample_size < audit.n
    assert audit.max_abs_weight_fraction == pytest.approx(0.8)


def test_signed_weights_report_cancellation_and_two_ess_definitions():
    audit = mod.summarize_weights([10.0, -9.0, 1.0])
    assert audit.n_negative == 1
    assert audit.signed_weights_present
    assert audit.sum_w == pytest.approx(2.0)
    assert audit.sum_abs_w == pytest.approx(20.0)
    assert audit.cancellation_fraction == pytest.approx(0.9)
    assert audit.cancellation_severity == pytest.approx(0.9)
    assert audit.signed_mass_orientation == 1
    assert audit.signed_effective_sample_size < audit.absolute_effective_sample_size
    assert audit.signed_diagnostic_method_id == mod.SIGNED_DIAGNOSTIC_METHOD_ID


def test_all_negative_weights_have_bounded_cancellation_and_are_not_all_zero():
    audit = mod.summarize_weights([-1.0, -2.0])
    assert audit.n_positive == 0
    assert audit.n_negative == 2
    assert audit.cancellation_fraction == pytest.approx(0.0)
    assert audit.cancellation_severity == pytest.approx(0.0)
    assert audit.signed_mass_orientation == -1
    assert audit.sum_abs_w == pytest.approx(3.0)

    passed, findings = mod.validate_audit(audit, require_nonzero_sum=False)
    assert passed
    assert not any(item["code"] == "ALL_ZERO_WEIGHTS" for item in findings)
    assert any(item["code"] == "SIGNED_WEIGHTS_PRESENT" for item in findings)


def test_scale_stable_signed_diagnostics_match_across_common_positive_scales():
    base = mod.summarize_weights([10.0, -9.0, 1.0])
    for scale in (1e300, 1e-300):
        got = mod.summarize_weights(scale * np.array([10.0, -9.0, 1.0]))
        assert got.cancellation_severity == pytest.approx(base.cancellation_severity)
        assert got.max_abs_weight_fraction == pytest.approx(base.max_abs_weight_fraction)
        assert got.signed_mass_orientation == base.signed_mass_orientation
        assert got.signed_mass_over_scale == pytest.approx(base.signed_mass_over_scale)
        assert got.total_variation_over_scale == pytest.approx(base.total_variation_over_scale)


def test_policy_text_matches_signed_capable_default_semantics():
    assert "SIGNED_WEIGHTS_REQUIRE_EXPLICIT_POLICY" in mod.POLICY
    assert "NONNEGATIVE" not in mod.POLICY.split(";")[0]


def test_nonfinite_weight_is_blocking():
    audit = mod.summarize_weights([1.0, np.nan, 2.0])
    passed, findings = mod.validate_audit(audit)
    assert not passed
    assert any(item["code"] == "NONFINITE_WEIGHT" and item["blocking"] for item in findings)


def test_negative_weight_can_be_reported_or_forbidden_by_policy():
    audit = mod.summarize_weights([1.0, -0.25, 2.0])
    passed, findings = mod.validate_audit(audit, require_nonnegative=False)
    assert passed
    assert any(item["code"] == "SIGNED_WEIGHTS_PRESENT" for item in findings)

    passed_strict, strict_findings = mod.validate_audit(audit, require_nonnegative=True)
    assert not passed_strict
    assert any(item["code"] == "NEGATIVE_WEIGHT_FORBIDDEN" for item in strict_findings)


def test_all_zero_weights_are_blocking():
    audit = mod.summarize_weights([0.0, 0.0, 0.0])
    passed, findings = mod.validate_audit(audit)
    assert not passed
    assert any(item["code"] == "ALL_ZERO_WEIGHTS" for item in findings)


def test_exact_signed_zero_sum_fails_by_default_but_can_be_allowed_explicitly():
    audit = mod.summarize_weights([1.0, -1.0])
    passed, findings = mod.validate_audit(audit)
    assert not passed
    assert any(item["code"] == "ZERO_SIGNED_SUM" for item in findings)

    passed_allowed, findings_allowed = mod.validate_audit(audit, require_nonzero_sum=False)
    assert passed_allowed
    assert not any(item["code"] == "ZERO_SIGNED_SUM" for item in findings_allowed)


def test_dominant_weight_policy_can_fail_closed():
    audit = mod.summarize_weights([1.0, 1.0, 98.0])
    passed, findings = mod.validate_audit(audit, max_abs_weight_fraction=0.5)
    assert not passed
    assert any(item["code"] == "WEIGHT_DOMINANCE_LIMIT" for item in findings)


def test_minimum_absolute_ess_policy_can_fail_closed():
    audit = mod.summarize_weights([1.0, 1.0, 8.0])
    passed, findings = mod.validate_audit(audit, min_absolute_ess=2.0)
    assert not passed
    assert any(item["code"] == "ABS_ESS_BELOW_MINIMUM" for item in findings)


def test_empty_and_non_1d_inputs_are_rejected():
    with pytest.raises(ValueError, match="empty"):
        mod.summarize_weights([])
    with pytest.raises(ValueError, match="1-D"):
        mod.summarize_weights(np.ones((2, 2)))


def test_no_finite_weights_is_controlled_error():
    with pytest.raises(ValueError, match="no finite"):
        mod.summarize_weights([np.nan, np.inf])


def test_absolute_ess_never_exceeds_finite_count_for_nonzero_real_weights():
    rng = np.random.default_rng(42)
    w = rng.lognormal(mean=0.0, sigma=1.0, size=1000)
    audit = mod.summarize_weights(w)
    assert audit.absolute_effective_sample_size <= audit.n_finite + 1e-10
    assert math.isfinite(audit.coefficient_of_variation_abs)
