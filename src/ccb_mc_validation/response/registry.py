"""Fail-closed quenching / fibre-clad / observation-window hypothesis registry.

Unresolved contradictions (#1008 Birks model-form, #1094 fibre outer cladding
transport material, #1090 full-transport vs acquisition window) are published as
named HYPOTHESIS profiles. Selecting a profile documents an assumption; it does
not silently pick "truth".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ccb_mc_validation.exceptions import ConfigurationError

REGISTRY_VERSION: str = "2026.0-waveB-lane05"
_REGISTRY_REL = Path("configs/response/registry_index.yaml")

_VALID_KINDS = frozenset(
    {"quenching", "fibre_outer_clad_transport", "observation_window"}
)
_VALID_STATUS = frozenset({"HYPOTHESIS", "APPROVED", "WITHDRAWN"})


def _repo_root() -> Path:
    # src/ccb_mc_validation/response/registry.py -> repo root
    return Path(__file__).resolve().parents[3]


def _registry_path(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else _repo_root()
    return (root / _REGISTRY_REL).resolve()


@dataclass(frozen=True)
class ResponseProfile:
    """One registered response / material / window hypothesis."""

    profile_id: str
    kind: str
    status: str
    claims_authorized: bool
    parameters: dict[str, Any]
    raw: dict[str, Any]
    path: Path
    registry_version: str


def load_registry_index(repo_root: Path | None = None) -> dict[str, Any]:
    """Load and validate the response registry index document."""
    path = _registry_path(repo_root)
    if not path.is_file():
        raise ConfigurationError(f"response registry index missing: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigurationError(f"response registry index is not a mapping: {path}")
    if data.get("schema") != "ccb-response-registry/1":
        raise ConfigurationError(
            f"unsupported response registry schema: {data.get('schema')!r}"
        )
    version = data.get("registry_version")
    if version != REGISTRY_VERSION:
        raise ConfigurationError(
            f"response registry_version mismatch: file has {version!r}, "
            f"code expects {REGISTRY_VERSION!r}"
        )
    for key in (
        "default_quenching_profile_id",
        "default_fibre_clad_profile_id",
        "default_observation_window_profile_id",
    ):
        if data.get(key) is not None:
            raise ConfigurationError(
                f"response registry must keep {key}: null "
                "(fail-closed; no silent default)"
            )
    if data.get("fail_closed_when_unset") is not True:
        raise ConfigurationError(
            "response registry must set fail_closed_when_unset: true"
        )
    return data


def list_profile_ids(
    repo_root: Path | None = None, *, kind: str | None = None
) -> list[str]:
    """Return registered profile ids in index order, optionally filtered by kind."""
    index = load_registry_index(repo_root)
    out: list[str] = []
    for entry in index.get("profiles", []):
        if kind is not None and str(entry.get("kind")) != kind:
            continue
        out.append(str(entry["profile_id"]))
    return out


def _load_profile_file(path: Path, *, registry_version: str) -> ResponseProfile:
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ConfigurationError(f"response profile is not a mapping: {path}")
    if raw.get("schema") != "ccb-response-profile/1":
        raise ConfigurationError(
            f"unsupported response profile schema in {path}: {raw.get('schema')!r}"
        )
    profile_id = raw.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id:
        raise ConfigurationError(f"response profile missing profile_id: {path}")
    kind = str(raw.get("kind", ""))
    if kind not in _VALID_KINDS:
        raise ConfigurationError(
            f"response profile {profile_id!r} has invalid kind {kind!r}"
        )
    status = str(raw.get("status", ""))
    if status not in _VALID_STATUS:
        raise ConfigurationError(
            f"response profile {profile_id!r} has invalid status {status!r}"
        )
    claims = bool(raw.get("claims_authorized", False))
    if status != "APPROVED" and claims:
        raise ConfigurationError(
            f"response profile {profile_id!r}: claims_authorized requires status=APPROVED"
        )
    params = raw.get("parameters")
    if not isinstance(params, dict):
        raise ConfigurationError(f"response profile {profile_id!r} missing parameters")
    return ResponseProfile(
        profile_id=profile_id,
        kind=kind,
        status=status,
        claims_authorized=claims,
        parameters=dict(params),
        raw=raw,
        path=path,
        registry_version=registry_version,
    )


def load_response_profile(
    profile_id: str, *, repo_root: Path | None = None
) -> ResponseProfile:
    """Load one registered profile by id (does not accept unset/empty)."""
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ConfigurationError("response profile_id must be a non-empty string")
    root = repo_root if repo_root is not None else _repo_root()
    index = load_registry_index(root)
    entries = {str(p["profile_id"]): p for p in index.get("profiles", [])}
    if profile_id not in entries:
        known = ", ".join(sorted(entries)) or "(none)"
        raise ConfigurationError(
            f"unknown response profile_id {profile_id!r}; registered: {known}"
        )
    rel = entries[profile_id]["path"]
    path = (root / "configs" / "response" / rel).resolve()
    profile = _load_profile_file(path, registry_version=REGISTRY_VERSION)
    if profile.profile_id != profile_id:
        raise ConfigurationError(
            f"profile file {path} has profile_id {profile.profile_id!r}, "
            f"expected {profile_id!r}"
        )
    return profile


def _extract_id(config: dict[str, Any] | None, *keys: str) -> str | None:
    if not config:
        return None
    for key in keys:
        if config.get(key):
            return str(config[key])
    nested = config.get("response")
    if isinstance(nested, dict):
        for key in keys:
            if nested.get(key):
                return str(nested[key])
    return None


def _require_kind(
    *,
    kind: str,
    config_keys: tuple[str, ...],
    config: dict[str, Any] | None,
    profile_id: str | None,
    issue_blurb: str,
    repo_root: Path | None,
) -> ResponseProfile:
    gid = profile_id if profile_id is not None else _extract_id(config, *config_keys)
    if not gid:
        known = ", ".join(list_profile_ids(repo_root, kind=kind))
        raise ConfigurationError(
            f"{config_keys[0]} is unset. {issue_blurb} forbid silent defaults. "
            f"Set {config_keys[0]} to a registered {kind} hypothesis profile "
            f"(registry {REGISTRY_VERSION}). Known ids: {known}. "
            "See docs/adr/ADR-0004-quenching-material-obs-window-hypotheses.md."
        )
    profile = load_response_profile(gid, repo_root=repo_root)
    if profile.kind != kind:
        raise ConfigurationError(
            f"profile {gid!r} has kind {profile.kind!r}, expected {kind!r}"
        )
    return profile


def require_quenching_profile(
    config: dict[str, Any] | None = None,
    *,
    profile_id: str | None = None,
    repo_root: Path | None = None,
) -> ResponseProfile:
    """Resolve a quenching-model profile or fail closed (#1008)."""
    return _require_kind(
        kind="quenching",
        config_keys=("quenching_profile_id", "quenching_model_id"),
        config=config,
        profile_id=profile_id,
        issue_blurb="Birks model-form contradictions (#1008)",
        repo_root=repo_root,
    )


def require_fibre_clad_profile(
    config: dict[str, Any] | None = None,
    *,
    profile_id: str | None = None,
    repo_root: Path | None = None,
) -> ResponseProfile:
    """Resolve fibre outer-cladding transport material profile or fail closed (#1094)."""
    return _require_kind(
        kind="fibre_outer_clad_transport",
        config_keys=("fibre_outer_clad_profile_id", "fibre_clad_profile_id"),
        config=config,
        profile_id=profile_id,
        issue_blurb="Fibre outer-cladding transport/optical contradictions (#1094)",
        repo_root=repo_root,
    )


def require_observation_window_profile(
    config: dict[str, Any] | None = None,
    *,
    profile_id: str | None = None,
    repo_root: Path | None = None,
) -> ResponseProfile:
    """Resolve observation-window semantic profile or fail closed (#1090)."""
    return _require_kind(
        kind="observation_window",
        config_keys=("observation_window_profile_id", "obs_window_profile_id"),
        config=config,
        profile_id=profile_id,
        issue_blurb=(
            "Full-transport vs acquisition-window observation-domain contradictions (#1090)"
        ),
        repo_root=repo_root,
    )
