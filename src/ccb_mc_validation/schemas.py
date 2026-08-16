"""Frozen schema records shared across MC validation studies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanonicalBranchSpec:
    """Expected ROOT branch contract for HiBeam MC truth trees."""

    tree_name: str
    branch: str
    dtype: str
    unit: str
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class ResolvedBranch:
    """Branch metadata after schema resolution against an input file."""

    spec: CanonicalBranchSpec
    present: bool
    observed_dtype: str | None = None


@dataclass(frozen=True)
class SchemaFingerprint:
    """Hashable fingerprint for a resolved schema contract."""

    schema_version: str
    tree_name: str
    branch_names: tuple[str, ...]
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tree_name": self.tree_name,
            "branch_names": list(self.branch_names),
            "digest": self.digest,
        }


@dataclass(frozen=True)
class MetricRecord:
    """Single scalar metric emitted by a validation study."""

    study_id: str
    metric_name: str
    value: float
    unit: str
    tolerance: float | None = None
    passed: bool | None = None


@dataclass(frozen=True)
class ManifestRecord:
    """Pinned provenance block for a study artifact directory."""

    study_id: str
    ticket: str
    config_path: str
    config_sha256: str
    git_head: str
    git_branch: str
    python_version: str
    inputs: tuple[tuple[str, str], ...]
    outputs: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "ticket": self.ticket,
            "config_path": self.config_path,
            "config_sha256": self.config_sha256,
            "git_head": self.git_head,
            "git_branch": self.git_branch,
            "python_version": self.python_version,
            "inputs": {path: digest for path, digest in self.inputs},
            "outputs": list(self.outputs),
        }


@dataclass(frozen=True)
class StudyStatus:
    """Lifecycle status for an MV study line."""

    study_id: str
    phase: str
    state: str
    blocked_by: str | None = None
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "phase": self.phase,
            "state": self.state,
            "blocked_by": self.blocked_by,
            "message": self.message,
        }
