"""Fail-closed electronics-response claim authority (issue #1010).

A generic CR-RC prior or the MV0 parametric white-noise path may be used for
software development, but it cannot authorize detector timing / pile-up /
waveform morphology claims until a measured or identified CCB front-end
transfer is bound (ADR-0010).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class ElectronicsResponseClass(str, Enum):
    """Provenance class for the electronics impulse / noise model."""

    ASSUMPTION_GENERIC_CRRC_NOT_MEASURED = "ASSUMPTION_GENERIC_CRRC_NOT_MEASURED"
    MV0_PARAMETRIC_WHITE_NOISE = "MV0_PARAMETRIC_WHITE_NOISE"
    CUSTOM_UNVALIDATED = "CUSTOM_UNVALIDATED"
    DATA_FIT = "DATA_FIT"
    BENCH_MEASURED = "BENCH_MEASURED"


class ElectronicsResponseAuthorityError(ValueError):
    """Raised when a claim requests unauthorized electronics provenance."""


_AUTHORIZED_FOR_DETECTOR_CLAIMS = frozenset(
    {
        ElectronicsResponseClass.BENCH_MEASURED,
        ElectronicsResponseClass.DATA_FIT,
    }
)

_BLOCKED_REASON = (
    "CCB front-end transfer function is BLOCKED (ADR-0010 / issue #1010): "
    "no measured/identified impulse is bound. Generic CR-RC / parametric "
    "MV0 electronics cannot authorize detector timing, pile-up, or waveform "
    "morphology claims."
)


@dataclass(frozen=True)
class ElectronicsResponseProvenance:
    """Self-describing electronics-response identity for a study/output."""

    response_class: ElectronicsResponseClass
    impulse_digest: str | None = None
    source_id: str | None = None
    notes: str = ""

    @property
    def authorizes_detector_performance_claims(self) -> bool:
        if self.response_class not in _AUTHORIZED_FOR_DETECTOR_CLAIMS:
            return False
        return bool(self.impulse_digest)


def parse_response_class(value: str | ElectronicsResponseClass) -> ElectronicsResponseClass:
    if isinstance(value, ElectronicsResponseClass):
        return value
    try:
        return ElectronicsResponseClass(str(value))
    except ValueError as exc:
        raise ElectronicsResponseAuthorityError(
            f"unknown electronics response class {value!r}"
        ) from exc


def default_unmeasured_provenance() -> ElectronicsResponseProvenance:
    """Repository default: generic CR-RC, explicitly not measured."""
    return ElectronicsResponseProvenance(
        response_class=ElectronicsResponseClass.ASSUMPTION_GENERIC_CRRC_NOT_MEASURED,
        impulse_digest=None,
        source_id=None,
        notes="default ccb-sipm-core / MV0 prior; not CCB-bench calibrated",
    )


def assert_detector_claim_authorized(
    provenance: ElectronicsResponseProvenance | Mapping[str, Any],
    *,
    claim: str,
) -> ElectronicsResponseProvenance:
    """Fail closed unless provenance can authorize a detector-performance claim."""
    if isinstance(provenance, Mapping):
        provenance = ElectronicsResponseProvenance(
            response_class=parse_response_class(provenance["response_class"]),
            impulse_digest=provenance.get("impulse_digest"),
            source_id=provenance.get("source_id"),
            notes=str(provenance.get("notes", "")),
        )
    if provenance.authorizes_detector_performance_claims:
        return provenance
    raise ElectronicsResponseAuthorityError(
        f"claim {claim!r} refused: {_BLOCKED_REASON} "
        f"(response_class={provenance.response_class.value}, "
        f"impulse_digest={provenance.impulse_digest!r})"
    )


def claim_gate_status(
    provenance: ElectronicsResponseProvenance | None = None,
) -> dict[str, Any]:
    """Machine-readable gate status for manifests / plot provenance."""
    prov = provenance or default_unmeasured_provenance()
    authorized = prov.authorizes_detector_performance_claims
    return {
        "issue": 1010,
        "adr": "ADR-0010",
        "status": "AUTHORIZED" if authorized else "BLOCKED",
        "response_class": prov.response_class.value,
        "impulse_digest": prov.impulse_digest,
        "authorizes_detector_performance_claims": authorized,
        "reason": None if authorized else _BLOCKED_REASON,
    }
