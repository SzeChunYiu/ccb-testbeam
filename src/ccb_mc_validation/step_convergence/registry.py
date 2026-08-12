"""Fail-closed step-convergence hypothesis registry (#1095).

Physical step limits are NOT invented. Profiles only force studies to declare
which unvalidated step policy they assume before any authorizing claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from ccb_mc_validation.exceptions import ConfigurationError, StudyBlockedError

REGISTRY_VERSION = "2026.0-waveC-lane05"
_REGISTRY_REL = Path("configs/step_convergence/registry_index.yaml")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _registry_path(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else _repo_root()
    return (root / _REGISTRY_REL).resolve()


@dataclass(frozen=True)
class StepConvergenceProfile:
    profile_id: str
    status: str
    claims_authorized: bool
    parameters: dict[str, Any]
    raw: dict[str, Any]


def load_registry_index(repo_root: Path | None = None) -> dict[str, Any]:
    path = _registry_path(repo_root)
    if not path.is_file():
        raise ConfigurationError(f"step-convergence registry missing: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ConfigurationError(f"invalid step-convergence registry: {path}")
    if data.get("registry_version") != REGISTRY_VERSION:
        raise ConfigurationError(
            f"step-convergence registry_version mismatch: "
            f"got {data.get('registry_version')!r}, expected {REGISTRY_VERSION!r}"
        )
    if data.get("fail_closed_when_unset") is not True:
        raise ConfigurationError(
            "step-convergence registry must set fail_closed_when_unset: true"
        )
    if data.get("default_step_convergence_profile_id") is not None:
        raise ConfigurationError(
            "default_step_convergence_profile_id must be null (fail-closed)"
        )
    return data


def list_profile_ids(repo_root: Path | None = None) -> list[str]:
    idx = load_registry_index(repo_root)
    profiles = idx.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ConfigurationError("step-convergence registry has no profiles")
    return [str(p) for p in profiles]


def load_step_convergence_profile(
    profile_id: str, *, repo_root: Path | None = None
) -> StepConvergenceProfile:
    root = repo_root if repo_root is not None else _repo_root()
    ids = list_profile_ids(root)
    if profile_id not in ids:
        raise ConfigurationError(
            f"unknown step_convergence_profile_id={profile_id!r}; "
            f"known={ids}"
        )
    path = root / "configs/step_convergence/profiles" / f"{profile_id}.yaml"
    if not path.is_file():
        raise ConfigurationError(f"missing step-convergence profile file: {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ConfigurationError(f"invalid profile YAML: {path}")
    status = str(raw.get("status", ""))
    authorized = bool(raw.get("claims_authorized", False))
    if status != "APPROVED" and authorized:
        raise ConfigurationError(
            f"profile {profile_id!r} cannot authorize claims while status={status!r}"
        )
    params = raw.get("parameters") or {}
    if not isinstance(params, dict):
        raise ConfigurationError(f"profile {profile_id!r} parameters must be a mapping")
    return StepConvergenceProfile(
        profile_id=str(raw.get("profile_id", profile_id)),
        status=status,
        claims_authorized=authorized,
        parameters=dict(params),
        raw=raw,
    )


def require_step_convergence_profile(
    config: Mapping[str, Any] | None = None,
    *,
    repo_root: Path | None = None,
    authorizing: bool = True,
) -> StepConvergenceProfile:
    """Fail closed when profile id is unset; block authorizing HYPOTHESIS claims."""
    cfg = dict(config or {})
    pid = cfg.get("step_convergence_profile_id")
    if pid is None or (isinstance(pid, str) and not pid.strip()):
        raise ConfigurationError(
            "step_convergence_profile_id is unset (#1095); refusing to treat "
            "Geant4 step-wise visible energy as a converged detector observable"
        )
    profile = load_step_convergence_profile(str(pid).strip(), repo_root=repo_root)
    if authorizing and not profile.claims_authorized:
        raise StudyBlockedError(
            f"step_convergence_profile_id={profile.profile_id!r} has "
            f"status={profile.status!r} and claims_authorized=false (#1095); "
            "Bragg/quenching authorizing claims remain BLOCKED until a "
            "documented convergence study promotes an APPROVED profile"
        )
    return profile
