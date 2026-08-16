from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "single_stave"
    / "strict_event_weights.py"
)
SPEC = importlib.util.spec_from_file_location("strict_event_weights", MODULE_PATH)
assert SPEC and SPEC.loader
strict = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(strict)


def test_valid_weighted_statistics_and_provenance() -> None:
    values = np.array([1.0, 2.0, 10.0])
    weights = np.array([1.0, 2.0, 1.0])

    assert strict.weighted_mean(values, weights) == pytest.approx(3.75)
    assert strict.weighted_median(values, weights) == pytest.approx(1.5)
    assert strict.weighted_fraction(values > 1.5, weights) == pytest.approx(0.75)
    assert strict.effective_sample_size(weights) == pytest.approx(16.0 / 6.0)

    summary = strict.summarize_weights(weights, expected_length=3)
    assert summary["policy"] == strict.POLICY
    assert summary["population_policy_id"] == strict.POPULATION_POLICY
    assert summary["summation_method"] == strict.SUMMATION_METHOD
    assert summary["n_weights"] == 3
    assert summary["n_zero"] == 0
    assert summary["sum_w"] == pytest.approx(4.0)
    assert summary["sum_w2"] == pytest.approx(6.0)
    assert summary["sum_w_over_scale"] == pytest.approx(2.0)
    assert summary["sum_w2_over_scale2"] == pytest.approx(1.5)
    assert summary["max_weight_fraction"] == pytest.approx(0.5)


def test_weighted_correlation_matches_perfect_linear_relation() -> None:
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = 4.0 * x - 7.0
    weights = np.array([0.5, 1.0, 3.0, 2.0])
    assert strict.weighted_correlation(x, y, weights) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "scale",
    [1.0, 1e300, 1e-300],
)
def test_normalized_estimators_are_invariant_to_positive_common_scale(scale: float) -> None:
    values = np.array([1.0, 2.0, 10.0])
    weights = scale * np.array([1.0, 2.0, 7.0])
    x = np.array([0.0, 1.0, 3.0])
    y = np.array([-1.0, 4.0, 8.0])

    assert strict.weighted_mean(values, weights) == pytest.approx(7.5)
    assert strict.weighted_median(values, weights) == pytest.approx(4.285714285714286)
    assert strict.weighted_fraction(values > 1.5, weights) == pytest.approx(0.9)
    assert strict.effective_sample_size(weights) == pytest.approx(100.0 / 54.0)
    assert strict.weighted_correlation(x, y, weights) == pytest.approx(
        strict.weighted_correlation(x, y, np.array([1.0, 2.0, 7.0]))
    )

    summary = strict.summarize_weights(weights)
    assert summary["ess"] == pytest.approx(100.0 / 54.0)
    assert summary["ess_fraction"] == pytest.approx((100.0 / 54.0) / 3.0)
    assert summary["max_weight_fraction"] == pytest.approx(0.7)
    assert summary["sum_w_over_scale"] == pytest.approx(10.0 / 7.0)
    assert summary["sum_w2_over_scale2"] == pytest.approx(54.0 / 49.0)


def test_extreme_equal_weights_remain_valid_when_raw_moments_are_unrepresentable() -> None:
    values = np.array([1.0, 3.0])
    for weights in (
        np.array([1e154, 1e154]),
        np.array([1e308, 1e308]),
        np.array([np.nextafter(0.0, 1.0), np.nextafter(0.0, 1.0)]),
    ):
        assert strict.weighted_mean(values, weights) == pytest.approx(2.0)
        assert strict.weighted_fraction([False, True], weights) == pytest.approx(0.5)
        assert strict.effective_sample_size(weights) == pytest.approx(2.0)
        summary = strict.summarize_weights(weights)
        assert summary["ess"] == pytest.approx(2.0)
        assert summary["max_weight_fraction"] == pytest.approx(0.5)
        assert summary["sum_w_over_scale"] == pytest.approx(2.0)
        assert summary["sum_w2_over_scale2"] == pytest.approx(2.0)
        assert summary["sum_w2"] is None

    overflow_summary = strict.summarize_weights(np.array([1e308, 1e308]))
    assert overflow_summary["sum_w"] is None
    assert overflow_summary["mean"] is None


@pytest.mark.parametrize(
    "weights, message",
    [
        ([1.0, float("nan"), 2.0], "nonfinite"),
        ([1.0, -0.1, 2.0], "negative"),
        ([0.0, 0.0, 0.0], "no positive"),
        ([[1.0, 2.0]], "one-dimensional"),
    ],
)
def test_invalid_weights_fail_closed(weights: object, message: str) -> None:
    with pytest.raises(strict.WeightValidationError, match=message):
        strict.validate_event_weights(weights)


def test_event_alignment_and_value_integrity_fail_closed() -> None:
    with pytest.raises(strict.WeightValidationError, match="expected 3"):
        strict.validate_event_weights([1.0, 2.0], expected_length=3)
    with pytest.raises(strict.WeightValidationError, match="nonfinite"):
        strict.weighted_mean([1.0, math.inf], [1.0, 1.0])
    with pytest.raises(strict.WeightValidationError, match="length mismatch"):
        strict.weighted_correlation([1.0, 2.0], [1.0], [1.0, 1.0])
    with pytest.raises(strict.WeightValidationError, match="zero variance"):
        strict.weighted_correlation([1.0, 1.0], [2.0, 3.0], [1.0, 1.0])


def test_directional_comparison_names_both_denominators() -> None:
    result = strict.direction_explicit_comparison(
        6.674567424757,
        2.134364334727324,
        unit="MeV",
    )
    assert result["weighted_minus_unweighted_pct_of_abs_unweighted"] == pytest.approx(
        -68.02243203341332
    )
    assert result["legacy_overstatement_pct_of_abs_weighted"] == pytest.approx(
        212.7192164972955
    )
    assert result["weighted_minus_unweighted"] == pytest.approx(-4.540203090029676)
    assert result["legacy_unweighted_minus_weighted"] == pytest.approx(4.540203090029676)

    fraction = strict.fraction_comparison(
        0.5719111928400914,
        0.16606032425392264,
    )
    assert fraction["weighted_minus_unweighted_percentage_points"] == pytest.approx(
        -40.585086858616876
    )
    assert fraction["legacy_unweighted_minus_weighted_percentage_points"] == pytest.approx(
        40.585086858616876
    )
    assert fraction["legacy_overstatement_pct_of_abs_weighted"] == pytest.approx(
        244.39966043037631
    )


def test_zero_denominator_relative_results_are_null_not_zero() -> None:
    result = strict.direction_explicit_comparison(0.0, 1.0, unit="MeV")
    assert result["weighted_minus_unweighted_pct_of_abs_unweighted"] is None
    assert result["legacy_overstatement_pct_of_abs_weighted"] == pytest.approx(-100.0)
    assert result["relative_denominator_zero_policy"] == "NULL_NOT_ZERO"


def test_atomic_json_publication_and_alias_protection(tmp_path: Path) -> None:
    protected = tmp_path / "input.root"
    protected.write_bytes(b"root-bytes")
    output = tmp_path / "result.json"
    metadata = strict.atomic_write_json(
        output,
        {"value": 1.25, "policy": strict.POLICY},
        protected_paths=[protected],
    )
    assert metadata["path"] == str(output.resolve())
    assert metadata["bytes"] == output.stat().st_size
    assert len(metadata["sha256"]) == 64
    assert json.loads(output.read_text(encoding="utf-8"))["value"] == 1.25
    assert not list(tmp_path.glob(".result.json.*.tmp"))

    with pytest.raises(strict.WeightValidationError, match="protected input"):
        strict.atomic_write_json(protected, {"bad": True}, protected_paths=[protected])
    assert protected.read_bytes() == b"root-bytes"


def test_atomic_json_rejects_nonfinite_payload_without_final_artifact(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    with pytest.raises(ValueError, match="Out of range float values"):
        strict.atomic_write_json(output, {"value": float("nan")})
    assert not output.exists()
