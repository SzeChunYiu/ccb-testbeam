"""Versioned Geant4 transport-stepping policy (issue #1095).

Records EM constructor / StepFunction intent. Claims of step-convergence
are fail-closed until a registered convergence-study digest exists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ccb_mc_validation.exceptions import ConfigurationError, StudyBlockedError

POLICY_VERSION = "2026.0-waveB-lane06"
_REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "transport"
    / "step_policy_registry.json"
)


def load_step_policy_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or _REGISTRY
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ConfigurationError("step_policy_registry must be a mapping")
    if data.get("policy_version") != POLICY_VERSION:
        raise ConfigurationError(
            "step_policy_registry policy_version mismatch: "
            f"got {data.get('policy_version')!r}, expected {POLICY_VERSION!r}"
        )
    return data


def require_step_policy(
    config: Mapping[str, Any] | None,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Require an explicit step-policy id; no silent inherited-default claim."""
    reg = dict(registry) if registry is not None else load_step_policy_registry()
    cfg = dict(config or {})
    policy_id = cfg.get("step_policy_id")
    if not policy_id:
        raise ConfigurationError(
            "step_policy_id is unset; Geant4 stepping/Birks convergence "
            "claims must declare an explicit policy (issue #1095 / ADR-0005)"
        )
    policies = reg.get("policies") or {}
    if policy_id not in policies:
        raise ConfigurationError(f"unknown step_policy_id {policy_id!r}")
    policy = dict(policies[policy_id])
    return {
        "policy_version": POLICY_VERSION,
        "step_policy_id": policy_id,
        "policy": policy,
        "claims_authorized": bool(policy.get("claims_authorized", False)),
        "status": policy.get("status", "HYPOTHESIS"),
    }


def authorize_step_convergence_claim(
    config: Mapping[str, Any] | None,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed: 'step-converged' requires a registered study digest."""
    bound = require_step_policy(config, registry=registry)
    policy = bound["policy"]
    digest = (policy.get("convergence_study") or {}).get("digest")
    if not digest or not bound["claims_authorized"]:
        raise StudyBlockedError(
            f"step-convergence claim BLOCKED for policy "
            f"{bound['step_policy_id']!r}: missing registered convergence "
            "study digest over the declared energy/material/geometry domain "
            "(issue #1095)"
        )
    bound["status"] = "AUTHORIZED"
    bound["convergence_study_digest"] = digest
    return bound
