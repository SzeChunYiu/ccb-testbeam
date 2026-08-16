#!/usr/bin/env python3
"""Fail-closed event-weight validation and weighted summary primitives.

This module is intentionally independent of ROOT/uproot.  Nonnegative
probability-measure validation delegates to the canonical package contract so
weight units / common normalization cannot change authorisation.  Raw generator
weight-carrier semantics remain upstream of this module.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.truth.event_weight_population import (
    EVENT_WEIGHT_POPULATION_POLICY_ID,
    SUMMATION_METHOD_ID,
    EventWeightPopulationSummary,
    summarize_event_weight_population,
)

POLICY = "MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED"
POPULATION_POLICY = EVENT_WEIGHT_POPULATION_POLICY_ID
VERSION = "2.0.0"
SUMMATION_METHOD = SUMMATION_METHOD_ID
WEIGHTED_MEDIAN_METHOD = "SORTED_NUMPY_CUMSUM_LINEAR_INTERPOLATION"


class WeightValidationError(ValueError):
    """Raised when a weighted analysis cannot satisfy the strict contract."""


def _as_float_vector(values: Any, *, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise WeightValidationError(
            f"{name} must be one-dimensional; received shape {array.shape}"
        )
    if array.size == 0:
        raise WeightValidationError(f"{name} must not be empty")
    if not np.all(np.isfinite(array)):
        bad = np.flatnonzero(~np.isfinite(array))[:5].tolist()
        raise WeightValidationError(f"{name} contains nonfinite values at indices {bad}")
    return array


def _validated_weight_array_and_summary(
    weights: Any,
    *,
    expected_length: int | None = None,
    name: str = "event_weights",
) -> tuple[np.ndarray, EventWeightPopulationSummary]:
    try:
        summary = summarize_event_weight_population(
            weights,
            expected_length=expected_length,
        )
    except DataContractError as exc:
        message = str(exc).replace("event_weight", name).replace("non-finite", "nonfinite")
        if "no positive finite mass" in message:
            message = f"{name} has no positive weight"
        raise WeightValidationError(message) from exc

    if summary.n_rows == 0:
        raise WeightValidationError(f"{name} must not be empty")
    if not summary.measure_defined or summary.weight_scale is None:
        raise WeightValidationError(f"{name} has no positive weight")

    array = np.asarray(weights, dtype=np.float64)
    return np.array(array, dtype=np.float64, copy=True), summary


def _scaled_weights(
    weight_array: np.ndarray,
    summary: EventWeightPopulationSummary,
) -> np.ndarray:
    assert summary.weight_scale is not None
    return weight_array / summary.weight_scale


def validate_event_weights(
    weights: Any,
    *,
    expected_length: int | None = None,
    name: str = "event_weights",
) -> np.ndarray:
    """Return a defensive copy after canonical nonnegative-population validation."""
    array, _summary = _validated_weight_array_and_summary(
        weights,
        expected_length=expected_length,
        name=name,
    )
    return array


def _validated_values_and_weights(
    values: Any,
    weights: Any,
    *,
    value_name: str,
    minimum_size: int = 1,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, EventWeightPopulationSummary]:
    value_array = _as_float_vector(values, name=value_name)
    if value_array.size < minimum_size:
        raise WeightValidationError(
            f"{value_name} requires at least {minimum_size} entries; received {value_array.size}"
        )
    weight_array, summary = _validated_weight_array_and_summary(
        weights,
        expected_length=value_array.size,
    )
    return value_array, weight_array, _scaled_weights(weight_array, summary), summary


def weighted_mean(values: Any, weights: Any) -> float:
    value_array, _weight_array, scaled_weights, summary = _validated_values_and_weights(
        values, weights, value_name="values"
    )
    assert summary.sum_w_over_scale is not None
    numerator = math.fsum(
        float(weight) * float(value)
        for value, weight in zip(value_array, scaled_weights, strict=True)
    )
    result = numerator / summary.sum_w_over_scale
    if not math.isfinite(result):
        raise WeightValidationError("weighted mean is nonfinite")
    return float(result)


def weighted_median(values: Any, weights: Any) -> float:
    value_array, _weight_array, scaled_weights, summary = _validated_values_and_weights(
        values, weights, value_name="values"
    )
    order = np.argsort(value_array, kind="mergesort")
    sorted_values = value_array[order]
    sorted_weights = scaled_weights[order]
    assert summary.sum_w_over_scale is not None
    cumulative = np.cumsum(sorted_weights, dtype=float) / summary.sum_w_over_scale
    result = float(np.interp(0.5, cumulative, sorted_values))
    if not math.isfinite(result):
        raise WeightValidationError("weighted median is nonfinite")
    return result


def weighted_fraction(mask: Any, weights: Any) -> float:
    mask_array = np.asarray(mask)
    if mask_array.ndim != 1:
        raise WeightValidationError(
            f"mask must be one-dimensional; received shape {mask_array.shape}"
        )
    if mask_array.size == 0:
        raise WeightValidationError("mask must not be empty")
    mask_bool = mask_array.astype(bool, copy=False)
    weight_array, summary = _validated_weight_array_and_summary(
        weights,
        expected_length=mask_bool.size,
    )
    scaled_weights = _scaled_weights(weight_array, summary)
    numerator = math.fsum(
        float(weight)
        for selected, weight in zip(mask_bool, scaled_weights, strict=True)
        if selected
    )
    assert summary.sum_w_over_scale is not None
    result = numerator / summary.sum_w_over_scale
    if not 0.0 <= result <= 1.0 or not math.isfinite(result):
        raise WeightValidationError("weighted fraction is outside [0, 1] or nonfinite")
    return float(result)


def weighted_correlation(x: Any, y: Any, weights: Any) -> float:
    x_array = _as_float_vector(x, name="x")
    y_array = _as_float_vector(y, name="y")
    if x_array.size != y_array.size:
        raise WeightValidationError(
            f"x/y length mismatch: {x_array.size} versus {y_array.size}"
        )
    if x_array.size < 2:
        raise WeightValidationError("weighted correlation requires at least two entries")
    weight_array, summary = _validated_weight_array_and_summary(
        weights,
        expected_length=x_array.size,
    )
    scaled_weights = _scaled_weights(weight_array, summary)
    assert summary.sum_w_over_scale is not None
    denominator_weight = summary.sum_w_over_scale
    mean_x = math.fsum(
        float(weight) * float(value)
        for value, weight in zip(x_array, scaled_weights, strict=True)
    ) / denominator_weight
    mean_y = math.fsum(
        float(weight) * float(value)
        for value, weight in zip(y_array, scaled_weights, strict=True)
    ) / denominator_weight
    covariance = math.fsum(
        float(weight) * (float(x_value) - mean_x) * (float(y_value) - mean_y)
        for x_value, y_value, weight in zip(x_array, y_array, scaled_weights, strict=True)
    ) / denominator_weight
    variance_x = math.fsum(
        float(weight) * (float(x_value) - mean_x) ** 2
        for x_value, weight in zip(x_array, scaled_weights, strict=True)
    ) / denominator_weight
    variance_y = math.fsum(
        float(weight) * (float(y_value) - mean_y) ** 2
        for y_value, weight in zip(y_array, scaled_weights, strict=True)
    ) / denominator_weight
    if variance_x <= 0.0 or variance_y <= 0.0:
        raise WeightValidationError("weighted correlation is undefined for zero variance")
    result = covariance / math.sqrt(variance_x * variance_y)
    if not math.isfinite(result):
        raise WeightValidationError("weighted correlation is nonfinite")
    tolerance = 16.0 * np.finfo(float).eps
    if result < -1.0 - tolerance or result > 1.0 + tolerance:
        raise WeightValidationError(f"weighted correlation is outside [-1, 1]: {result}")
    return float(min(1.0, max(-1.0, result)))


def effective_sample_size(weights: Any) -> float:
    _weight_array, summary = _validated_weight_array_and_summary(weights)
    result = summary.effective_sample_size
    if result is None:
        raise WeightValidationError("effective sample size is undefined")
    return float(result)


def _raw_std_or_none(
    weight_array: np.ndarray,
    summary: EventWeightPopulationSummary,
) -> float | None:
    scaled = _scaled_weights(weight_array, summary)
    assert summary.sum_w_over_scale is not None
    scaled_mean = summary.sum_w_over_scale / summary.n_rows
    scaled_variance = math.fsum(
        (float(value) - scaled_mean) ** 2 for value in scaled
    ) / summary.n_rows
    scaled_std = math.sqrt(max(0.0, scaled_variance))
    assert summary.weight_scale is not None
    raw_std = scaled_std * summary.weight_scale
    return float(raw_std) if math.isfinite(raw_std) else None


def summarize_weights(weights: Any, *, expected_length: int | None = None) -> dict[str, Any]:
    weight_array, summary = _validated_weight_array_and_summary(
        weights,
        expected_length=expected_length,
    )
    raw_mean = (
        float(summary.sum_w / summary.n_rows)
        if summary.sum_w is not None
        else None
    )
    return {
        "policy": POLICY,
        "population_policy_id": summary.policy_id,
        "validator_version": VERSION,
        "summation_method": summary.summation_method,
        "statistical_unit": summary.statistical_unit,
        "n_weights": summary.n_rows,
        "n_zero": summary.n_zero,
        "n_positive": summary.n_positive,
        "min": float(np.min(weight_array)),
        "max": float(np.max(weight_array)),
        "mean": raw_mean,
        "std": _raw_std_or_none(weight_array, summary),
        "weight_scale": summary.weight_scale,
        "sum_w_over_scale": summary.sum_w_over_scale,
        "sum_w2_over_scale2": summary.sum_w2_over_scale2,
        "sum_w": summary.sum_w,
        "sum_w2": summary.sum_w2,
        "ess": summary.effective_sample_size,
        "ess_fraction": summary.effective_sample_fraction,
        "max_weight_fraction": summary.max_weight_fraction,
        "measure_defined": summary.measure_defined,
    }


def direction_explicit_comparison(
    unweighted: float,
    weighted: float,
    *,
    unit: str,
) -> dict[str, Any]:
    unweighted_value = float(unweighted)
    weighted_value = float(weighted)
    if not math.isfinite(unweighted_value) or not math.isfinite(weighted_value):
        raise WeightValidationError("comparison endpoints must be finite")
    weighted_minus_unweighted = weighted_value - unweighted_value
    legacy_minus_weighted = -weighted_minus_unweighted
    weighted_relative = (
        100.0 * weighted_minus_unweighted / abs(unweighted_value)
        if unweighted_value != 0.0
        else None
    )
    legacy_relative = (
        100.0 * legacy_minus_weighted / abs(weighted_value)
        if weighted_value != 0.0
        else None
    )
    return {
        "unit": unit,
        "unweighted_legacy": unweighted_value,
        "weighted": weighted_value,
        "weighted_minus_unweighted": weighted_minus_unweighted,
        "weighted_minus_unweighted_pct_of_abs_unweighted": weighted_relative,
        "legacy_unweighted_minus_weighted": legacy_minus_weighted,
        "legacy_overstatement_pct_of_abs_weighted": legacy_relative,
        "relative_denominator_zero_policy": (
            "NULL_NOT_ZERO"
            if None in (weighted_relative, legacy_relative)
            else "NOT_APPLICABLE"
        ),
    }


def fraction_comparison(unweighted: float, weighted: float) -> dict[str, Any]:
    comparison = direction_explicit_comparison(unweighted, weighted, unit="fraction")
    comparison["weighted_minus_unweighted_percentage_points"] = (
        100.0 * comparison["weighted_minus_unweighted"]
    )
    comparison["legacy_unweighted_minus_weighted_percentage_points"] = (
        100.0 * comparison["legacy_unweighted_minus_weighted"]
    )
    return comparison


def file_sha256(path: Path | str, *, chunk_size: int = 1024 * 1024) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve(strict=True)
    digest = hashlib.sha256()
    size = 0
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return {
        "path": str(file_path),
        "bytes": int(size),
        "sha256": digest.hexdigest(),
    }


def atomic_write_json(
    path: Path | str,
    payload: Mapping[str, Any],
    *,
    protected_paths: Sequence[Path | str] = (),
) -> dict[str, Any]:
    final_path = Path(path).expanduser().resolve()
    for protected in protected_paths:
        protected_path = Path(protected).expanduser().resolve()
        if final_path == protected_path:
            raise WeightValidationError(
                f"refusing to overwrite protected input path: {protected_path}"
            )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=final_path.parent,
            prefix=f".{final_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, final_path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return file_sha256(final_path)
