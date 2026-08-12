"""Step-size / Bragg convergence contract (issue #1095)."""
from __future__ import annotations

from typing import Any, Mapping, Optional

STATUS_UNDECLARED = "UNDECLARED_INHERITED_PHYSICS_LIST_STEP_POLICY"
STATUS_DECLARED = "DECLARED_APPLICATION_STEP_POLICY"
STATUS_STUDY_COMPLETE = "STEP_CONVERGENCE_STUDY_RECORDED"
AUTHORISING_STATUSES = frozenset({STATUS_STUDY_COMPLETE})


class StepConvergenceError(ValueError):
    """Fail-closed step-convergence gate."""


def current_application_status(
    *,
    has_user_limits: bool = False,
    has_step_limiter_physics: bool = False,
    has_step_function_override: bool = False,
    study_artifact_id: Optional[str] = None,
) -> dict[str, Any]:
    declared = bool(has_user_limits or has_step_limiter_physics or has_step_function_override)
    if study_artifact_id:
        status = STATUS_STUDY_COMPLETE
    elif declared:
        status = STATUS_DECLARED
    else:
        status = STATUS_UNDECLARED
    return {
        "issue": 1095,
        "status": status,
        "has_user_limits": bool(has_user_limits),
        "has_step_limiter_physics": bool(has_step_limiter_physics),
        "has_step_function_override": bool(has_step_function_override),
        "study_artifact_id": study_artifact_id,
        "authorising_bragg_birks_claims": status in AUTHORISING_STATUSES,
        "note": (
            "Condensed-history step partitioning is independent of production "
            "cuts (#1089). Missing step policy is not treated as convergence."
        ),
    }


def gate_authorising_bragg_claim(
    policy: Optional[Mapping[str, Any]] = None,
    *,
    claim_id: str = "bragg_or_birks_response",
) -> dict[str, Any]:
    pol = dict(policy) if policy is not None else current_application_status()
    status = str(pol.get("status", STATUS_UNDECLARED))
    if status not in AUTHORISING_STATUSES:
        return {
            "claim_id": claim_id,
            "decision": "BLOCKED",
            "reason": "STEP_CONVERGENCE_UNDECLARED_OR_INCOMPLETE",
            "policy_status": status,
            "authorising": False,
        }
    return {
        "claim_id": claim_id,
        "decision": "OK",
        "reason": "STEP_CONVERGENCE_STUDY_RECORDED",
        "policy_status": status,
        "authorising": True,
        "study_artifact_id": pol.get("study_artifact_id"),
    }
