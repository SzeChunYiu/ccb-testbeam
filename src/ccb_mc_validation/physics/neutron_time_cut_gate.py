"""Fail-closed gate for the implicit QGSP_BIC neutron tracking-time cut (#1091)."""
from __future__ import annotations

from typing import Any

IMPLICIT_CUT_US = 10.0
ADR = "docs/adr/ADR-0013-neutron-tracking-time-cut.md"
META_VALUE = "IMPLICIT_QGSP_BIC_DEFAULT_10_UNVALIDATED"


def neutron_time_cut_metadata() -> dict[str, Any]:
    """Provenance block for run sidecars / Python consumers."""
    return {
        "neutron_tracking_time_cut_us": META_VALUE,
        "neutron_tracking_time_cut_numeric_us_hypothesis": IMPLICIT_CUT_US,
        "neutron_tracking_time_cut_status": "BLOCKED_ISSUE_1091",
        "adr": ADR,
        "issue": 1091,
        "claims_authorized": False,
    }


def assert_late_neutron_claims_allowed(*, authorising: bool, sensitivity_done: bool) -> None:
    """Refuse authorising late-neutron claims without a sensitivity study."""
    if authorising and not sensitivity_done:
        raise PermissionError(
            "Late-neutron / capture / activation claims are BLOCKED under "
            f"{ADR} (#1091) until an explicit cut is configured and sensitivity "
            "is measured."
        )
