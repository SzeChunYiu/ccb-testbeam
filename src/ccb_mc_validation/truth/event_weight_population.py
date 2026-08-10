"""Fail-closed contract for a derived nonnegative event-weight population.

The raw generator representation is intentionally out of scope here. A
source-specific adapter must first produce exactly one derived analysis weight
per final generator-event row. This module validates the resulting population
before any normalized weighted estimator or effective-sample-size diagnostic
is authorised.

Signed-weight generators define a different measure and must use a separate
contract; they are not silently coerced into this nonnegative probability
measure.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any, Iterable

import numpy as np

from ccb_mc_validation.exceptions import DataContractError

EVENT_WEIGHT_POPULATION_POLICY_ID = "nonnegative_event_measure_v2"
SUMMATION_METHOD_ID = "python_math_fsum_max_scaled_binary64_v2"
STATISTICAL_UNIT = "generator_event"


@dataclass(frozen=True)
class EventWeightPopulationSummary:
    """Sufficient statistics for one event-aligned nonnegative weight vector."""

    policy_id: str
    summation_method: str
    statistical_unit: str
    n_rows: int
    n_positive: int
    n_zero: int
    weight_scale: float | None
    sum_w_over_scale: float | None
    sum_w2_over_scale2: float | None
    sum_w: float | None
    sum_w2: float | None
    effective_sample_size: float | None
    effective_sample_fraction: float | None
    max_weight_fraction: float | None
    measure_defined: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready representation without NaN/Inf sentinels."""
        return asdict(self)


def _as_weight_vector(weights: Any, *, expected_length: int | None) -> np.ndarray:
    if np.ma.isMaskedArray(weights):
        raise DataContractError(
            "event_weight must not be a masked array; missing weights need an explicit policy"
        )

    # A production caller normally supplies a NumPy numeric vector; keep that
    # path O(n) without boxing millions of event weights. For generic Python
    # sequences, inspect the original scalar types before NumPy can silently
    # coerce booleans/text/complex values into a plausible float dtype.
    if isinstance(weights, np.ndarray):
        raw = weights
    else:
        original = np.asarray(weights, dtype=object)
        if original.ndim != 1:
            raise DataContractError(
                f"event_weight must be one-dimensional, got shape {original.shape}"
            )
        invalid = [
            index
            for index, value in enumerate(original)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
        ]
        if invalid:
            raise DataContractError(
                "event_weight must contain real numeric non-boolean scalars; "
                f"invalid indices={invalid[:5]}"
            )
        raw = np.asarray(weights)

    if raw.ndim != 1:
        raise DataContractError(
            f"event_weight must be one-dimensional, got shape {raw.shape}"
        )
    if raw.dtype.kind not in "iuf":
        raise DataContractError(
            "event_weight must use a real numeric integer/unsigned/float dtype"
        )
    array = raw.astype(np.float64, copy=False)
    if expected_length is not None:
        if isinstance(expected_length, bool) or not isinstance(
            expected_length, (int, np.integer)
        ):
            raise DataContractError("expected_length must be a non-negative integer")
        expected = int(expected_length)
        if expected < 0:
            raise DataContractError("expected_length must be a non-negative integer")
        if array.size != expected:
            raise DataContractError(
                f"event_weight length {array.size} != expected {expected}"
            )
    if array.size and not np.all(np.isfinite(array)):
        bad = np.flatnonzero(~np.isfinite(array))[:5].tolist()
        raise DataContractError(
            f"event_weight contains non-finite values at indices {bad}"
        )
    if array.size and np.any(array < 0.0):
        bad = np.flatnonzero(array < 0.0)[:5].tolist()
        raise DataContractError(
            f"event_weight contains negative values at indices {bad}"
        )
    return np.array(array, dtype=np.float64, copy=True)


def _positive_fsum_or_none(values: Iterable[float]) -> float | None:
    """Return a positive finite raw-unit sum, or ``None`` if binary64 cannot."""

    try:
        total = math.fsum(values)
    except OverflowError:
        return None
    if not math.isfinite(total) or total <= 0.0:
        return None
    return float(total)


def summarize_event_weight_population(
    weights: Any,
    *,
    expected_length: int | None = None,
) -> EventWeightPopulationSummary:
    """Validate and summarize one derived event-weight population.

    An empty population is a valid *empty diagnostic product* but does not
    define a normalized weighted empirical measure, so ESS and dominance are
    returned as ``None``. A non-empty population must contain positive total
    mass; an all-zero population fails closed.

    The normalized measure and ESS are invariant under a common positive
    rescaling of all weights. They are therefore evaluated after dividing by
    the maximum positive weight. ``math.fsum`` is then applied to scaled first
    and second moments whose terms lie in [0, 1], avoiding avoidable
    overflow/underflow from a mere change of weight units or normalization.

    Raw-unit ``sum_w`` and ``sum_w2`` are retained as convenience provenance
    when each has a positive finite binary64 representation. If a valid measure
    has a raw moment outside binary64 range, that convenience field is ``None``;
    the authoritative scale-normalized triplet
    ``(weight_scale, sum_w_over_scale, sum_w2_over_scale2)`` remains available.
    """

    array = _as_weight_vector(weights, expected_length=expected_length)
    n_rows = int(array.size)
    if n_rows == 0:
        return EventWeightPopulationSummary(
            policy_id=EVENT_WEIGHT_POPULATION_POLICY_ID,
            summation_method=SUMMATION_METHOD_ID,
            statistical_unit=STATISTICAL_UNIT,
            n_rows=0,
            n_positive=0,
            n_zero=0,
            weight_scale=None,
            sum_w_over_scale=None,
            sum_w2_over_scale2=None,
            sum_w=0.0,
            sum_w2=0.0,
            effective_sample_size=None,
            effective_sample_fraction=None,
            max_weight_fraction=None,
            measure_defined=False,
        )

    weight_scale = float(np.max(array))
    if not math.isfinite(weight_scale) or weight_scale <= 0.0:
        raise DataContractError(
            "non-empty event_weight population has no positive finite mass"
        )

    scaled = array / weight_scale
    sum_w_over_scale = math.fsum(float(value) for value in scaled)
    sum_w2_over_scale2 = math.fsum(
        float(value) * float(value) for value in scaled
    )
    if not math.isfinite(sum_w_over_scale) or sum_w_over_scale <= 0.0:
        raise DataContractError("invalid scale-normalized event_weight total mass")
    if not math.isfinite(sum_w2_over_scale2) or sum_w2_over_scale2 <= 0.0:
        raise DataContractError(
            "invalid scale-normalized event_weight squared-weight sum"
        )

    ess = sum_w_over_scale * sum_w_over_scale / sum_w2_over_scale2
    tolerance = 64.0 * np.finfo(np.float64).eps * max(1, n_rows)
    if not math.isfinite(ess) or ess < 1.0 - tolerance or ess > n_rows + tolerance:
        raise DataContractError(
            f"effective sample size {ess!r} violates 1 <= ESS <= n_rows={n_rows}"
        )
    ess = min(float(n_rows), max(1.0, float(ess)))

    max_weight_fraction = 1.0 / sum_w_over_scale
    if (
        not math.isfinite(max_weight_fraction)
        or max_weight_fraction <= 0.0
        or max_weight_fraction > 1.0 + tolerance
    ):
        raise DataContractError(
            f"invalid max_weight_fraction {max_weight_fraction!r}"
        )
    max_weight_fraction = min(1.0, float(max_weight_fraction))

    sum_w = _positive_fsum_or_none(float(value) for value in array)
    sum_w2 = _positive_fsum_or_none(
        float(value) * float(value) for value in array
    )

    n_positive = int(np.count_nonzero(array > 0.0))
    n_zero = int(n_rows - n_positive)
    return EventWeightPopulationSummary(
        policy_id=EVENT_WEIGHT_POPULATION_POLICY_ID,
        summation_method=SUMMATION_METHOD_ID,
        statistical_unit=STATISTICAL_UNIT,
        n_rows=n_rows,
        n_positive=n_positive,
        n_zero=n_zero,
        weight_scale=weight_scale,
        sum_w_over_scale=float(sum_w_over_scale),
        sum_w2_over_scale2=float(sum_w2_over_scale2),
        sum_w=sum_w,
        sum_w2=sum_w2,
        effective_sample_size=ess,
        effective_sample_fraction=float(ess / n_rows),
        max_weight_fraction=max_weight_fraction,
        measure_defined=True,
    )
