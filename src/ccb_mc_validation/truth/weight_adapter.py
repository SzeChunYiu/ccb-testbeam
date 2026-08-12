"""Source-aware raw→event weight adapters (issue #880).

A branch named ``PrimaryWeight`` is not by itself a physical event measure.
Callers must bind a versioned ``generator_measure_mode`` and matching
``weight_adapter_id``. Arbitrary ``weights[0]`` extraction is rejected.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.exceptions import DataContractError

WEIGHT_ADAPTER_SCHEMA = "ccb-raw-event-weight-adapter/v1"

# Supported adapter identities. Each maps to a distinct generator world.
ADAPTER_SCALAR_EVENT = "scalar_event_weight_v1"
ADAPTER_COMMON_REPLICATED = "common_replicated_primary_weight_v1"
ADAPTER_DIRECT_UNIT = "direct_sampling_unit_weight_v1"

MODE_SCALAR = "scalar_event_weight"
MODE_COMMON_REPLICATED = "common_replicated_primary"
MODE_DIRECT_UNIT = "direct_sampling_unit_weight"

_MODE_TO_ADAPTER = {
    MODE_SCALAR: ADAPTER_SCALAR_EVENT,
    MODE_COMMON_REPLICATED: ADAPTER_COMMON_REPLICATED,
    MODE_DIRECT_UNIT: ADAPTER_DIRECT_UNIT,
}


def _as_1d(name: str, values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    if arr.ndim != 1:
        raise DataContractError(f"{name} must be 1-D, got shape {arr.shape}")
    return arr


def resolve_adapter_id(
    *,
    generator_measure_mode: str | None,
    weight_adapter_id: str | None = None,
) -> str:
    if not generator_measure_mode:
        raise DataContractError(
            "generator_measure_mode is required to adapt PrimaryWeight; "
            "arbitrary weights[0] is unauthorized (#880)"
        )
    mode = str(generator_measure_mode)
    if mode not in _MODE_TO_ADAPTER:
        raise DataContractError(
            f"unsupported generator_measure_mode {mode!r}; "
            f"supported={sorted(_MODE_TO_ADAPTER)}"
        )
    expected = _MODE_TO_ADAPTER[mode]
    if weight_adapter_id is not None and str(weight_adapter_id) != expected:
        raise DataContractError(
            f"weight_adapter_id {weight_adapter_id!r} does not match "
            f"generator_measure_mode {mode!r} (expected {expected!r})"
        )
    return expected


def adapt_raw_primary_weight(
    primary_weights: Any,
    *,
    generator_measure_mode: str | None,
    weight_adapter_id: str | None = None,
    apply_weight: bool = True,
) -> dict[str, Any]:
    """Return one derived event weight with adapter provenance.

    Parameters
    ----------
    primary_weights
        Raw generator payload for one event (scalar or vector).
    generator_measure_mode
        Declared generator world; required whenever ``apply_weight`` is true.
    """
    if not apply_weight:
        return {
            "schema_version": WEIGHT_ADAPTER_SCHEMA,
            "generator_measure_mode": "unweighted_diagnostic",
            "weight_adapter_id": "unit_weight_diagnostic_v1",
            "event_weight": 1.0,
            "authorising": False,
        }

    adapter = resolve_adapter_id(
        generator_measure_mode=generator_measure_mode,
        weight_adapter_id=weight_adapter_id,
    )
    mode = str(generator_measure_mode)
    weights = _as_1d("PrimaryWeight", primary_weights)

    if adapter == ADAPTER_DIRECT_UNIT:
        # Direct-sampling world: analysis weight is identically 1; a stale
        # non-unit raw branch must not be consumed as a measure.
        if weights.size == 0:
            raise DataContractError("PrimaryWeight empty under direct-sampling mode")
        if not np.all(np.isfinite(weights)):
            raise DataContractError("PrimaryWeight non-finite under direct-sampling mode")
        if np.any(np.abs(weights - 1.0) > 0.0):
            raise DataContractError(
                "direct_sampling_unit_weight mode forbids non-unit raw PrimaryWeight "
                f"(got min={float(np.min(weights))}, max={float(np.max(weights))})"
            )
        event_weight = 1.0
    elif adapter == ADAPTER_SCALAR_EVENT:
        if weights.size != 1:
            raise DataContractError(
                "scalar_event_weight mode requires exactly one PrimaryWeight value; "
                f"got {weights.size}"
            )
        event_weight = float(weights[0])
    elif adapter == ADAPTER_COMMON_REPLICATED:
        if weights.size == 0:
            raise DataContractError("PrimaryWeight empty under common-replicated mode")
        if not np.all(np.isfinite(weights)):
            raise DataContractError("PrimaryWeight non-finite under common-replicated mode")
        # Collapse only after proving every sibling value is identical.
        if not np.all(weights == weights[0]):
            raise DataContractError(
                "common_replicated_primary mode requires identical sibling weights; "
                f"got unique={sorted({float(x) for x in weights})}"
            )
        event_weight = float(weights[0])
    else:  # pragma: no cover - resolve_adapter_id already gates
        raise DataContractError(f"unhandled weight_adapter_id {adapter!r}")

    if not np.isfinite(event_weight):
        raise DataContractError("adapted event_weight is non-finite")
    if event_weight < 0.0:
        raise DataContractError("adapted event_weight is negative")

    return {
        "schema_version": WEIGHT_ADAPTER_SCHEMA,
        "generator_measure_mode": mode,
        "weight_adapter_id": adapter,
        "event_weight": float(event_weight),
        "authorising": True,
    }


def require_weight_provenance(meta: Mapping[str, Any]) -> tuple[str, str]:
    """Extract and validate weight provenance fields from run/product metadata."""
    mode = meta.get("generator_measure_mode")
    adapter = meta.get("weight_adapter_id")
    resolved = resolve_adapter_id(
        generator_measure_mode=None if mode is None else str(mode),
        weight_adapter_id=None if adapter is None else str(adapter),
    )
    return str(mode), resolved
