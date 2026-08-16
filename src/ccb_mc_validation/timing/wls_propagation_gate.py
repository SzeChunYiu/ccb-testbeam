"""Fail-closed gate for the unvalidated v_WLS=17 cm/ns hypothesis (#1032)."""
from __future__ import annotations

from typing import Any

HYPOTHESIS_ID = "wls_effective_speed_17cm_per_ns_H1"
DEFAULT_SPEED_CM_PER_NS = 17.0
ADR = "docs/adr/ADR-0012-wls-propagation-speed-hypothesis.md"


def wls_speed_claim_status(
    *,
    speed_cm_per_ns: float | None = DEFAULT_SPEED_CM_PER_NS,
    authorising: bool = False,
    measured_model_bound: bool = False,
) -> dict[str, Any]:
    """Return authorisation status for a WLS effective-speed correction."""
    status = {
        "hypothesis_id": HYPOTHESIS_ID,
        "adr": ADR,
        "speed_cm_per_ns": speed_cm_per_ns,
        "issue": 1032,
    }
    if measured_model_bound:
        status.update(
            authorising=bool(authorising),
            label="MEASURED_OR_TRANSPORT_MODEL_BOUND",
            blocked=False,
        )
        return status
    if authorising:
        raise PermissionError(
            "Authorising WLS propagation timing corrections are BLOCKED under "
            f"{ADR} (#1032); bind a measured/optical-transport model or set "
            "authorising=False for a labelled diagnostic."
        )
    status.update(
        authorising=False,
        label="NONAUTHORISING_WLS_SPEED_HYPOTHESIS",
        blocked=True,
    )
    return status
