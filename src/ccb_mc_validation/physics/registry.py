"""Versioned physics-list registry with fail-closed unset policy (#1006).

The Geant4 executable must receive an explicit ``--physics-list`` and must
abort if the factory cannot provide that reference list (no warning-fallback
to QGSP_BIC). This Python registry mirrors the provenance/applicability side
and refuses silent defaults so stopping-depth/PID claims cannot rely on an
unversioned hard-coded list.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from ccb_mc_validation.exceptions import ConfigurationError

REGISTRY_VERSION = "2026.0-waveB-lane03-physics-v1"

_ROOT = Path(__file__).resolve().parents[3]
_INDEX = _ROOT / "configs" / "physics" / "registry_index.yaml"
_PROFILES = _ROOT / "configs" / "physics" / "profiles"


@dataclass(frozen=True)
class PhysicsListProfile:
    profile_id: str
    status: str
    claims_authorized: bool
    geant4_reference_list: str
    applicability_note: str
    raw: Mapping[str, Any]

    @property
    def parameters(self) -> Mapping[str, Any]:
        return {
            "geant4_reference_list": self.geant4_reference_list,
            "status": self.status,
            "claims_authorized": self.claims_authorized,
        }


def _load_yaml(path: Path) -> Any:
    with path.open() as f:
        return yaml.safe_load(f)


def load_registry_index() -> dict:
    if not _INDEX.is_file():
        raise ConfigurationError(f"physics registry index missing: {_INDEX}")
    data = _load_yaml(_INDEX)
    if not isinstance(data, dict):
        raise ConfigurationError("physics registry index must be a mapping")
    if data.get("registry_version") != REGISTRY_VERSION:
        raise ConfigurationError(
            f"physics registry_version mismatch: got {data.get('registry_version')!r}, "
            f"expected {REGISTRY_VERSION!r}"
        )
    if data.get("default_profile_id") is not None:
        raise ConfigurationError(
            "physics registry must not set default_profile_id "
            "(fail closed when unset)"
        )
    if data.get("fail_closed_when_unset") is not True:
        raise ConfigurationError("physics registry must set fail_closed_when_unset: true")
    return data


def list_physics_list_ids() -> list[str]:
    index = load_registry_index()
    ids = index.get("profile_ids")
    if not isinstance(ids, list) or not ids:
        raise ConfigurationError("physics registry profile_ids missing/empty")
    return list(ids)


def load_physics_profile(profile_id: str) -> PhysicsListProfile:
    path = _PROFILES / f"{profile_id}.yaml"
    if not path.is_file():
        raise ConfigurationError(f"unknown physics_list_profile_id: {profile_id!r}")
    raw = _load_yaml(path)
    if not isinstance(raw, dict):
        raise ConfigurationError(f"physics profile {profile_id!r} must be a mapping")
    return PhysicsListProfile(
        profile_id=str(raw.get("profile_id", profile_id)),
        status=str(raw.get("status", "HYPOTHESIS")),
        claims_authorized=bool(raw.get("claims_authorized", False)),
        geant4_reference_list=str(raw["geant4_reference_list"]),
        applicability_note=str(raw.get("applicability_note", "")),
        raw=raw,
    )


def require_physics_list(config: Optional[Mapping[str, Any]]) -> PhysicsListProfile:
    """Fail closed when physics_list_profile_id is unset."""
    if config is None:
        raise ConfigurationError(
            "physics_list_profile_id is unset; refuse silent QGSP_BIC default "
            f"(registry {REGISTRY_VERSION})"
        )
    pid = config.get("physics_list_profile_id")
    if pid is None and isinstance(config.get("physics"), Mapping):
        pid = config["physics"].get("physics_list_profile_id")
    if pid is None or pid == "":
        raise ConfigurationError(
            "physics_list_profile_id is unset; refuse silent QGSP_BIC default "
            f"(registry {REGISTRY_VERSION})"
        )
    if not isinstance(pid, str):
        raise ConfigurationError(
            f"physics_list_profile_id must be a string, got {type(pid).__name__}"
        )
    known = set(list_physics_list_ids())
    if pid not in known:
        raise ConfigurationError(f"unknown physics_list_profile_id: {pid!r}")
    return load_physics_profile(pid)


def physics_list_digest(profile: PhysicsListProfile) -> str:
    payload = {
        "registry_version": REGISTRY_VERSION,
        "profile_id": profile.profile_id,
        "geant4_reference_list": profile.geant4_reference_list,
        "status": profile.status,
        "claims_authorized": profile.claims_authorized,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()
