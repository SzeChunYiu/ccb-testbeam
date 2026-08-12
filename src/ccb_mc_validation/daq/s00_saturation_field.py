"""Fail-closed field-level saturation contract for the S00 pulse table.

This module does not choose the CCB digitizer hardware or a physical clipping
threshold.  Issue #1073 deliberately keeps those questions open because the
repository currently contains mutually incompatible ADC worlds.  The purpose
here is narrower: make it impossible for the legacy S00 ``saturation`` boolean
to acquire hardware-authorising meaning merely because it is present in a
canonical pulse table.

The historical S00 computation ``peak_code_adc >= 16383`` is retained only as
World-A diagnostic semantics.  Consumers that need a physical saturation /
censoring claim must call :func:`require_authorising_saturation_contract`,
which fails closed until the DAQ transfer contract is resolved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .adc_saturation_registry import (
    AdcSaturationContractError,
    STATUS_BLOCKED,
    authorising_saturation_threshold,
    diagnostic_saturation_flag,
    registry_snapshot,
)

SCHEMA = "ccb-s00-saturation-field/1"
LEGACY_DIAGNOSTIC_WORLD = "A"
FIELD_NAME = "saturation"
STATUS_DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY_ADC_WORLD_UNRESOLVED"


@dataclass(frozen=True)
class S00SaturationFieldContract:
    """Machine-readable meaning of the legacy S00 saturation field."""

    schema: str
    field_name: str
    semantic_class: str
    diagnostic_world_id: str
    authorising: bool
    hardware_censoring_claim: bool
    registry_status: str
    parent_issue: int
    issue: int
    notes: str


def field_contract() -> dict[str, Any]:
    """Return the non-authorising S00 saturation-field contract.

    This function is intentionally independent of raw ROOT availability.  It
    describes the *meaning* of the field, not a measured saturation rate.
    """

    snap = registry_snapshot()
    contract = S00SaturationFieldContract(
        schema=SCHEMA,
        field_name=FIELD_NAME,
        semantic_class=STATUS_DIAGNOSTIC_ONLY,
        diagnostic_world_id=LEGACY_DIAGNOSTIC_WORLD,
        authorising=False,
        hardware_censoring_claim=False,
        registry_status=str(snap["status"]),
        parent_issue=int(snap["parent_issue"]),
        issue=int(snap["issue"]),
        notes=(
            "Legacy S00 >=16383 semantics are a named World-A diagnostic only. "
            "They do not identify a physical ADC rail or clipping mechanism."
        ),
    )
    return asdict(contract)


def legacy_world_a_diagnostic(peak_code_adc):
    """Evaluate the historical S00 World-A flag with explicit provenance.

    Returns ``(flags, metadata)``.  ``flags`` is numerically identical to the
    historical ``peak_code_adc >= 16383`` map, but metadata makes the critical
    distinction that the result is non-authorising while #1073/#1014 remain
    unresolved.
    """

    flags, registry_meta = diagnostic_saturation_flag(
        peak_code_adc, world_id=LEGACY_DIAGNOSTIC_WORLD
    )
    meta = {
        **field_contract(),
        "threshold_adc_code": int(registry_meta["threshold"]),
        "registry_world_label": str(registry_meta["label"]),
        "registry_authorising": bool(registry_meta["authorising"]),
    }
    # Defensive closure: a future registry edit must not silently authorize
    # this legacy helper without an explicit schema transition.
    if meta["registry_authorising"] or meta["registry_status"] != STATUS_BLOCKED:
        raise AdcSaturationContractError(
            "legacy S00 saturation helper requires an explicit contract/schema "
            "review before any transition out of diagnostic-only state"
        )
    return np.asarray(flags, dtype=bool), meta


def require_authorising_saturation_contract() -> dict[str, Any]:
    """Return an authorising saturation contract or fail closed.

    At present this necessarily raises through the #1073 registry.  The wrapper
    exists so S00/downstream consumers have one stable API to call when they
    require a physical clipping/censoring interpretation.
    """

    threshold = int(authorising_saturation_threshold())
    # Reaching this line means the parent registry has changed.  Do not infer a
    # complete field contract from a scalar threshold alone: force a deliberate
    # implementation update binding rails, polarity and transfer semantics.
    raise AdcSaturationContractError(
        "registry supplied an authorising threshold but ccb-s00-saturation-field/1 "
        f"has no resolved rail/transfer schema for threshold={threshold}; update "
        "the field contract explicitly before authorising S00 saturation claims"
    )
