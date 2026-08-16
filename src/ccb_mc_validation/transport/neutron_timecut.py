"""QGSP_BIC neutron tracking-time cut provenance (issue #1091).

The Geant4 Physics List Guide documents a 10 microsecond default neutron
tracking-time cut for QGSP_BIC. That boundary must be explicit and
provenance-bound; 'QGSP_BIC' alone is insufficient.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ccb_mc_validation.exceptions import ConfigurationError, StudyBlockedError

POLICY_VERSION = "2026.1-issue1091-ladder"
QGSP_BIC_DEFAULT_NEUTRON_TIME_CUT_US = 10.0
_REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "transport"
    / "neutron_timecut_registry.json"
)


def load_neutron_timecut_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or _REGISTRY
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ConfigurationError("neutron_timecut_registry must be a mapping")
    if data.get("policy_version") != POLICY_VERSION:
        raise ConfigurationError(
            "neutron_timecut_registry policy_version mismatch: "
            f"got {data.get('policy_version')!r}, expected {POLICY_VERSION!r}"
        )
    return data


def require_neutron_timecut_policy(
    config: Mapping[str, Any] | None,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pin/record the neutron time-cut policy; fail closed if unset."""
    reg = dict(registry) if registry is not None else load_neutron_timecut_registry()
    cfg = dict(config or {})
    policy_id = cfg.get("neutron_timecut_policy_id")
    if not policy_id:
        raise ConfigurationError(
            "neutron_timecut_policy_id is unset; QGSP_BIC neutron tracking-time "
            "policy must be explicit (issue #1091 / ADR-0005)"
        )
    policies = reg.get("policies") or {}
    if policy_id not in policies:
        raise ConfigurationError(f"unknown neutron_timecut_policy_id {policy_id!r}")
    policy = dict(policies[policy_id])
    cut_us = policy.get("neutron_time_cut_us")
    if cut_us is None:
        raise ConfigurationError(
            f"policy {policy_id!r} missing neutron_time_cut_us"
        )
    record = {
        "policy_version": POLICY_VERSION,
        "neutron_timecut_policy_id": policy_id,
        "physics_list": policy.get("physics_list", "QGSP_BIC"),
        "neutron_time_cut_us": float(cut_us),
        "neutron_energy_cut_MeV": policy.get("neutron_energy_cut_MeV", 0.0),
        "source": policy.get("source"),
        "status": policy.get("status", "PINNED_REFERENCE_DEFAULT"),
        "claims_authorized": bool(policy.get("claims_authorized", False)),
        "sensitivity_study": policy.get("sensitivity_study"),
    }
    if "neutron_time_cut_us" in cfg and float(cfg["neutron_time_cut_us"]) != float(
        cut_us
    ):
        raise ConfigurationError(
            f"caller neutron_time_cut_us={cfg['neutron_time_cut_us']!r} disagrees "
            f"with policy {policy_id!r} value {cut_us!r}"
        )
    return record


def authorize_neutron_timecut_sensitivity_claim(
    config: Mapping[str, Any] | None,
    *,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Sensitivity / negligibility claims require a registered study digest."""
    bound = require_neutron_timecut_policy(config, registry=registry)
    study = bound.get("sensitivity_study") or {}
    digest = study.get("digest")
    if not digest or not bound["claims_authorized"]:
        raise StudyBlockedError(
            f"neutron time-cut sensitivity claim BLOCKED for policy "
            f"{bound['neutron_timecut_policy_id']!r}: no registered "
            "default-vs-extended convergence digest (issue #1091)"
        )
    bound["status"] = "AUTHORIZED"
    return bound
