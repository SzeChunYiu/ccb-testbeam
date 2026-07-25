#!/usr/bin/env python3
"""Fail-closed event-weight validation and weighted summary primitives.

This module is intentionally independent of ROOT/uproot so the numerical
contract can be tested with small synthetic arrays.  Analysis entry points are
expected to validate a complete event-aligned weight vector once and to call
these helpers for every downstream weighted estimator.
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

POLICY = "MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED"
VERSION = "1.0.0"
SUMMATION_METHOD = "PYTHON_MATH_FSUM_BINARY64"
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


def validate_event_weights(
    weights: Any,
    *,
    expected_length: int | None = None,
    name: str = "event_weights",
) -> np.ndarray:
    """Return a defensive 1-D float copy after strict event-weight validation."""
    array = _as_float_vector(weights, name=name)
    if expected_length is not None and array.size != int(expected_length):
        raise WeightValidationError(
            f"{name} has {array.size} entries; expected {int(expected_length)}"
        )
    if np.any(array < 0.0):
        bad = np.flatnonzero(array < 0.0)[:5].tolist()
        raise WeightValidationError(f"{name} contains negative values at indices {bad}")
    if not np.any(array > 0.0):
        raise WeightValidationError(f"{name} has no positive weight")
    total = math.fsum(float(value) for value in array)
    squares = math.fsum(float(value) * float(value) for value in array)
    if not math.isfinite(total) or total <= 0.0:
        raise WeightValidationError(f"{name} has nonpositive or nonfinite total weight")
    if not math.isfinite(squares) or squares <= 0.0:
        raise WeightValidationError(f"{name} has nonpositive or nonfinite squared-weight sum")
    return array.copy()


def _validated_values_and_weights(
    values: Any,
    weights: Any,
    *,
    value_name: str,
    minimum_size: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    value_array = _as_float_vector(values, name=value_name)
    if value_array.size < minimum_size:
        raise WeightValidationError(
            f"{value_name} requires at least {minimum_size} entries; received {value_array.size}"
        )
    weight_array = validate_event_weights(weights, expected_length=value_array.size)
    return value_array, weight_array


def weighted_mean(values: Any, weights: Any) -> float:
    value_array, weight_array = _validated_values_and_weights(
        values, weights, value_name="values"
    )
    numerator = math.fsum(
        float(weight) * float(value)
        for value, weight in zip(value_array, weight_array, strict=True)
    )
    denominator = math.fsum(float(weight) for weight in weight_array)
    result = numerator / denominator
    if not math.isfinite(result):
        raise WeightValidationError("weighted mean is nonfinite")
    return float(result)


def weighted_median(values: Any, weights: Any) -> float:
    value_array, weight_array = _validated_values_and_weights(
        values, weights, value_name="values"
    )
    order = np.argsort(value_array, kind="mergesort")
    sorted_values = value_array[order]
    sorted_weights = weight_array[order]
    total = math.fsum(float(weight) for weight in sorted_weights)
    cumulative = np.cumsum(sorted_weights, dtype=float) / total
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
    weight_array = validate_event_weights(weights, expected_length=mask_bool.size)
    numerator = math.fsum(
        float(weight) for selected, weight in zip(mask_bool, weight_array, strict=True) if selected
    )
    denominator = math.fsum(float(weight) for weight in weight_array)
    result = numerator / denominator
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
    weight_array = validate_event_weights(weights, expected_length=x_array.size)
    mean_x = weighted_mean(x_array, weight_array)
    mean_y = weighted_mean(y_array, weight_array)
    denominator_weight = math.fsum(float(weight) for weight in weight_array)
    covariance = math.fsum(
        float(weight) * (float(x_value) - mean_x) * (float(y_value) - mean_y)
        for x_value, y_value, weight in zip(x_array, y_array, weight_array, strict=True)
    ) / denominator_weight
    variance_x = math.fsum(
        float(weight) * (float(x_value) - mean_x) ** 2
        for x_value, weight in zip(x_array, weight_array, strict=True)
    ) / denominator_weight
    variance_y = math.fsum(
        float(weight) * (float(y_value) - mean_y) ** 2
        for y_value, weight in zip(y_array, weight_array, strict=True)
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
    weight_array = validate_event_weights(weights)
    total = math.fsum(float(weight) for weight in weight_array)
    squares = math.fsum(float(weight) * float(weight) for weight in weight_array)
    result = total * total / squares
    if not math.isfinite(result) or result <= 0.0 or result > weight_array.size + 1e-9:
        raise WeightValidationError(f"invalid effective sample size: {result}")
    return float(result)


def summarize_weights(weights: Any, *, expected_length: int | None = None) -> dict[str, Any]:
    weight_array = validate_event_weights(weights, expected_length=expected_length)
    total = math.fsum(float(weight) for weight in weight_array)
    squares = math.fsum(float(weight) * float(weight) for weight in weight_array)
    ess_value = total * total / squares
    return {
        "policy": POLICY,
        "validator_version": VERSION,
        "summation_method": SUMMATION_METHOD,
        "n_weights": int(weight_array.size),
        "n_zero": int(np.count_nonzero(weight_array == 0.0)),
        "n_positive": int(np.count_nonzero(weight_array > 0.0)),
        "min": float(np.min(weight_array)),
        "max": float(np.max(weight_array)),
        "mean": float(np.mean(weight_array)),
        "std": float(np.std(weight_array)),
        "sum_w": float(total),
        "sum_w2": float(squares),
        "ess": float(ess_value),
        "ess_fraction": float(ess_value / weight_array.size),
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
