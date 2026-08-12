#!/usr/bin/env python3
"""Validate one MC weight vector and report summary statistics.

Provides ``summarize_weights`` for weight-distribution diagnostics and
``validate_audit`` for fail-closed policy gates.  Used by
``compare_data_mc`` and the MC validation pipeline to reject degraded or
invalid weight vectors before they enter physics inference.

Issue #1174: signed weights define a different measure from the nonnegative
probability contract (``nonnegative_event_measure_v2``). This module may
*diagnose* signed vectors, but probability-ECDF consumers must keep
``require_nonnegative=True``. Scale-stable signed diagnostics use
``m = max|w|`` so common positive rescaling cannot overflow raw moments.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

VERSION = "1.1.0"
POLICY = (
    "WEIGHT_VECTOR_MUST_CONTAIN_FINITE_VALUES_WITHIN_DOMINANCE_AND_ESS_LIMITS;"
    "SIGNED_WEIGHTS_REQUIRE_EXPLICIT_POLICY_AND_ARE_NONAUTHORISING_FOR_PROBABILITY_ECDF"
)
SIGNED_DIAGNOSTIC_METHOD_ID = "max_abs_scaled_signed_diagnostic_v1"


@dataclass(frozen=True)
class WeightAudit:
    n: int
    n_finite: int
    n_zero: int
    n_positive: int
    n_negative: int
    sum_w: float
    sum_abs_w: float
    sum_w2: float
    signed_effective_sample_size: float
    absolute_effective_sample_size: float
    max_abs_weight_fraction: float
    all_unit_weights: bool
    signed_weights_present: bool
    cancellation_fraction: float
    coefficient_of_variation_abs: float
    # Scale-stable signed diagnostics (#1174). Raw-unit moments above remain
    # convenience provenance; dimensionless fields use max-|w| scaling.
    weight_scale: float
    signed_mass_over_scale: float
    total_variation_over_scale: float
    squared_mass_over_scale2: float
    cancellation_severity: float
    signed_mass_orientation: int
    signed_diagnostic_method_id: str


def summarise_weights(weights: Any) -> WeightAudit:
    """Analyse a 1-D weight vector and return a ``WeightAudit``."""
    arr = np.asarray(weights, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"weights must be 1-D, got shape {arr.shape}")
    if arr.size == 0:
        raise ValueError("empty weight vector")
    if not np.any(np.isfinite(arr)):
        raise ValueError("no finite weight values")
    return _summarize(arr)


def summarize_weights(weights: Any) -> WeightAudit:
    """Canonical public entry point (aliased from ``summarise_weights``)."""
    return summarise_weights(weights)


def _summarize(arr: np.ndarray) -> WeightAudit:
    finite = np.isfinite(arr)
    finite_arr = arr[finite]
    n_finite = int(finite_arr.size)

    sum_w = math.fsum(float(v) for v in finite_arr)
    sum_abs_w = math.fsum(float(abs(v)) for v in finite_arr)
    sum_w2 = math.fsum(float(v) * float(v) for v in finite_arr)
    sum_abs_w2 = math.fsum(float(abs(v)) * float(abs(v)) for v in finite_arr)

    n_negative = int((finite_arr < 0.0).sum())
    n_zero = int((finite_arr == 0.0).sum())
    n_positive = n_finite - n_negative - n_zero

    abs_ess = sum_abs_w * sum_abs_w / sum_abs_w2 if sum_abs_w2 > 0.0 else 0.0
    signed_ess = sum_w * sum_w / sum_w2 if sum_w2 > 0.0 else 0.0

    max_abs = float(np.max(np.abs(finite_arr))) if n_finite > 0 else 0.0
    max_abs_fraction = max_abs / sum_abs_w if sum_abs_w > 0.0 else 0.0

    all_unit = bool(
        n_finite > 0
        and n_negative == 0
        and n_zero == 0
        and bool(np.allclose(finite_arr, 1.0))
    )

    # Bounded cancellation severity: 1 - |S|/A in [0, 1]. Legacy 1-S/A is not a
    # fraction under all-negative orientation (#1174).
    cancellation = (
        1.0 - abs(sum_w) / sum_abs_w if sum_abs_w > 0.0 else 0.0
    )
    cancellation = min(1.0, max(0.0, float(cancellation)))
    orientation = 1 if sum_w > 0.0 else -1 if sum_w < 0.0 else 0

    if max_abs > 0.0:
        scaled = finite_arr / max_abs
        signed_mass_over_scale = math.fsum(float(v) for v in scaled)
        total_variation_over_scale = math.fsum(abs(float(v)) for v in scaled)
        squared_mass_over_scale2 = math.fsum(float(v) * float(v) for v in scaled)
    else:
        signed_mass_over_scale = 0.0
        total_variation_over_scale = 0.0
        squared_mass_over_scale2 = 0.0

    mean_abs = sum_abs_w / n_finite if n_finite > 0 else 0.0
    cv = float(np.std(np.abs(finite_arr)) / mean_abs) if mean_abs > 0.0 else 0.0

    return WeightAudit(
        n=int(arr.size),
        n_finite=n_finite,
        n_zero=n_zero,
        n_positive=n_positive,
        n_negative=n_negative,
        sum_w=sum_w,
        sum_abs_w=sum_abs_w,
        sum_w2=sum_w2,
        signed_effective_sample_size=signed_ess,
        absolute_effective_sample_size=abs_ess,
        max_abs_weight_fraction=max_abs_fraction,
        all_unit_weights=all_unit,
        signed_weights_present=n_negative > 0,
        cancellation_fraction=cancellation,
        coefficient_of_variation_abs=cv,
        weight_scale=max_abs,
        signed_mass_over_scale=float(signed_mass_over_scale),
        total_variation_over_scale=float(total_variation_over_scale),
        squared_mass_over_scale2=float(squared_mass_over_scale2),
        cancellation_severity=cancellation,
        signed_mass_orientation=orientation,
        signed_diagnostic_method_id=SIGNED_DIAGNOSTIC_METHOD_ID,
    )


Finding = Dict[str, Any]


def _finding(code: str, blocking: bool = False, **meta: Any) -> Finding:
    return {"code": code, "blocking": blocking, **meta}


def validate_audit(
    audit: WeightAudit,
    *,
    require_nonnegative: bool = False,
    require_nonzero_sum: bool = True,
    max_abs_weight_fraction: float | None = None,
    min_absolute_ess: float | None = None,
) -> tuple[bool, list[Finding]]:
    """Apply policy gates to a ``WeightAudit``.

    Default gates allow signed weights with a non-blocking finding. Probability
    consumers (for example DATA↔MC ECDFs) must pass ``require_nonnegative=True``.
    """
    findings: list[Finding] = []

    if not np.isfinite(audit.sum_w) or not np.isfinite(audit.sum_w2):
        findings.append(_finding("NONFINITE_WEIGHT", blocking=True))

    if audit.n_finite != audit.n:
        findings.append(
            _finding(
                "NONFINITE_WEIGHT",
                blocking=True,
                n_total=audit.n,
                n_finite=audit.n_finite,
            )
        )

    if audit.n_negative > 0:
        findings.append(
            _finding(
                "SIGNED_WEIGHTS_PRESENT",
                blocking=False,
                n_negative=audit.n_negative,
                scientific_status="NONAUTHORISING_FOR_PROBABILITY_ECDF",
                signed_diagnostic_method_id=audit.signed_diagnostic_method_id,
            )
        )
        if require_nonnegative:
            findings.append(
                _finding(
                    "NEGATIVE_WEIGHT_FORBIDDEN",
                    blocking=True,
                    n_negative=audit.n_negative,
                )
            )

    # All-zero means zero total variation. All-negative vectors have nonzero
    # absolute mass and must not be misclassified as ALL_ZERO (#1174).
    if audit.sum_abs_w == 0.0 and audit.n_finite > 0:
        findings.append(
            _finding(
                "ALL_ZERO_WEIGHTS",
                blocking=True,
                n_finite=audit.n_finite,
            )
        )

    if audit.sum_w == 0.0 and require_nonzero_sum:
        findings.append(
            _finding(
                "ZERO_SIGNED_SUM",
                blocking=True,
                sum_w=audit.sum_w,
            )
        )

    if max_abs_weight_fraction is not None:
        if audit.max_abs_weight_fraction > max_abs_weight_fraction:
            findings.append(
                _finding(
                    "WEIGHT_DOMINANCE_LIMIT",
                    blocking=True,
                    max_abs_weight_fraction=audit.max_abs_weight_fraction,
                    limit=max_abs_weight_fraction,
                )
            )

    if min_absolute_ess is not None:
        if audit.absolute_effective_sample_size < min_absolute_ess:
            findings.append(
                _finding(
                    "ABS_ESS_BELOW_MINIMUM",
                    blocking=True,
                    absolute_ess=audit.absolute_effective_sample_size,
                    minimum=min_absolute_ess,
                )
            )

    passed = not any(f["blocking"] for f in findings)
    return passed, findings
