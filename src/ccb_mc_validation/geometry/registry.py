"""Fail-closed geometry / mapping / kinematics profile registry.

Unresolved contradictions (#987 fibre count, #991 stave length, #992 spacing,
#989 deuteron energy scale) are published as named HYPOTHESIS profiles.
Selecting a profile documents an assumption; it does not silently pick "truth".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from ccb_mc_validation.exceptions import ConfigurationError

REGISTRY_VERSION: str = "2026.0-waveA-lane03"
_REGISTRY_REL = Path("configs/geometry/registry_index.yaml")


def _repo_root() -> Path:
    # src/ccb_mc_validation/geometry/registry.py -> repo root
    return Path(__file__).resolve().parents[3]


def _registry_path(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else _repo_root()
    return (root / _REGISTRY_REL).resolve()


@dataclass(frozen=True)
class GeometryProfile:
    """One registered geometry / kinematics hypothesis (or APPROVED ledger)."""

    profile_id: str
    status: str
    claims_authorized: bool
    parameters: dict[str, Any]
    raw: dict[str, Any]
    path: Path
    registry_version: str

    @property
    def kind(self) -> str | None:
        return self.parameters.get("kind")

    def stave_half_extents_cm(self) -> tuple[float, float, float]:
        """Return (half_x, half_y, half_z) in cm for single-stave optical profiles."""
        try:
            hx = float(self.parameters["stave_half_x_cm"])
            hy = float(self.parameters["stave_half_y_cm"])
            hz = float(self.parameters["stave_half_z_cm"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError(
                f"profile {self.profile_id!r} lacks stave_half_{{x,y,z}}_cm "
                f"required for beam intersection (kind={self.kind!r}): {exc}"
            ) from exc
        return hx, hy, hz


def load_registry_index(repo_root: Path | None = None) -> dict[str, Any]:
    """Load and validate the registry index document."""
    path = _registry_path(repo_root)
    if not path.is_file():
        raise ConfigurationError(f"geometry registry index missing: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigurationError(f"geometry registry index is not a mapping: {path}")
    if data.get("schema") != "ccb-geometry-registry/1":
        raise ConfigurationError(
            f"unsupported geometry registry schema: {data.get('schema')!r}"
        )
    version = data.get("registry_version")
    if version != REGISTRY_VERSION:
        raise ConfigurationError(
            f"geometry registry_version mismatch: file has {version!r}, "
            f"code expects {REGISTRY_VERSION!r}"
        )
    if data.get("default_profile_id") is not None:
        raise ConfigurationError(
            "geometry registry must keep default_profile_id: null "
            "(fail-closed; no silent default)"
        )
    if data.get("fail_closed_when_unset") is not True:
        raise ConfigurationError(
            "geometry registry must set fail_closed_when_unset: true"
        )
    return data


def list_profile_ids(repo_root: Path | None = None) -> list[str]:
    """Return registered profile ids in index order."""
    index = load_registry_index(repo_root)
    profiles = index.get("profiles", [])
    return [str(p["profile_id"]) for p in profiles]


def _load_profile_file(path: Path, *, registry_version: str) -> GeometryProfile:
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ConfigurationError(f"geometry profile is not a mapping: {path}")
    if raw.get("schema") != "ccb-geometry-profile/1":
        raise ConfigurationError(
            f"unsupported geometry profile schema in {path}: {raw.get('schema')!r}"
        )
    profile_id = raw.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id:
        raise ConfigurationError(f"geometry profile missing profile_id: {path}")
    status = str(raw.get("status", ""))
    if status not in {"HYPOTHESIS", "APPROVED", "WITHDRAWN"}:
        raise ConfigurationError(
            f"geometry profile {profile_id!r} has invalid status {status!r}"
        )
    claims = bool(raw.get("claims_authorized", False))
    if status != "APPROVED" and claims:
        raise ConfigurationError(
            f"geometry profile {profile_id!r}: claims_authorized requires status=APPROVED"
        )
    params = raw.get("parameters")
    if not isinstance(params, dict):
        raise ConfigurationError(f"geometry profile {profile_id!r} missing parameters")
    return GeometryProfile(
        profile_id=profile_id,
        status=status,
        claims_authorized=claims,
        parameters=dict(params),
        raw=raw,
        path=path,
        registry_version=registry_version,
    )


def load_geometry_profile(
    profile_id: str, *, repo_root: Path | None = None
) -> GeometryProfile:
    """Load one registered profile by id (does not accept unset/empty)."""
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ConfigurationError("geometry_profile_id must be a non-empty string")
    root = repo_root if repo_root is not None else _repo_root()
    index = load_registry_index(root)
    entries = {str(p["profile_id"]): p for p in index.get("profiles", [])}
    if profile_id not in entries:
        known = ", ".join(sorted(entries)) or "(none)"
        raise ConfigurationError(
            f"unknown geometry_profile_id {profile_id!r}; registered: {known}"
        )
    rel = entries[profile_id]["path"]
    path = (root / "configs" / "geometry" / rel).resolve()
    profile = _load_profile_file(path, registry_version=REGISTRY_VERSION)
    if profile.profile_id != profile_id:
        raise ConfigurationError(
            f"profile file {path} has profile_id {profile.profile_id!r}, "
            f"expected {profile_id!r}"
        )
    return profile


def _extract_profile_id(config: dict[str, Any] | None) -> str | None:
    if not config:
        return None
    if config.get("geometry_profile_id"):
        return str(config["geometry_profile_id"])
    geom = config.get("geometry")
    if isinstance(geom, dict) and geom.get("profile_id"):
        return str(geom["profile_id"])
    if isinstance(geom, dict) and geom.get("geometry_profile_id"):
        return str(geom["geometry_profile_id"])
    return None


def require_geometry_profile(
    config: dict[str, Any] | None = None,
    *,
    profile_id: str | None = None,
    repo_root: Path | None = None,
) -> GeometryProfile:
    """Resolve a geometry profile or fail closed.

    ``geometry_profile_id`` must be set on the config (or passed explicitly).
    There is no default: unset raises :class:`ConfigurationError`.
    """
    gid = profile_id if profile_id is not None else _extract_profile_id(config)
    if not gid:
        known = ", ".join(list_profile_ids(repo_root))
        raise ConfigurationError(
            "geometry_profile_id is unset. Physics-model contradictions "
            "(#987 fibre count, #989 deuteron energy scale, #991 stave length, "
            "#992 analysed-stave spacing) forbid silent defaults. Set "
            "geometry_profile_id to a registered hypothesis profile "
            f"(registry {REGISTRY_VERSION}). Known ids: {known}. "
            "See docs/adr/ADR-0002-geometry-kinematics-hypotheses.md."
        )
    return load_geometry_profile(gid, repo_root=repo_root)


def geometry_profile_digest(profile: GeometryProfile) -> str:
    """Stable SHA-256 digest of the profile payload (feeds provenance / #986)."""
    payload = {
        "registry_version": profile.registry_version,
        "profile_id": profile.profile_id,
        "status": profile.status,
        "claims_authorized": profile.claims_authorized,
        "parameters": profile.parameters,
        "source_type": profile.raw.get("source_type"),
        "issues": profile.raw.get("issues"),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()

def require_spacing_hypothesis_for_tof(config: Mapping[str, Any] | None) -> GeometryProfile:
    """Fail closed for TOF/range claims that need analysed-stave spacing (#992).

    Both 2 cm and 4 cm profiles remain HYPOTHESIS / non-authorising until a
    hardware-backed APPROVED spacing profile exists. Callers must still name an
    explicit ``geometry_profile_id``; this helper additionally rejects profiles
    that do not declare ``analysed_stave_spacing_cm`` and rejects any attempt to
    treat a HYPOTHESIS spacing profile as claim-authorising.
    """
    profile = require_geometry_profile(config)
    spacing = profile.parameters.get("analysed_stave_spacing_cm")
    if spacing is None:
        raise ConfigurationError(
            f"geometry profile {profile.profile_id!r} does not declare "
            "analysed_stave_spacing_cm; refuse TOF/range spacing use (#992)"
        )
    if profile.claims_authorized:
        return profile
    raise ConfigurationError(
        f"geometry profile {profile.profile_id!r} has analysed_stave_spacing_cm="
        f"{spacing} but claims_authorized=false (status={profile.status}); "
        "TOF/range claims remain BLOCKED pending hardware ledger closure (#992)"
    )

