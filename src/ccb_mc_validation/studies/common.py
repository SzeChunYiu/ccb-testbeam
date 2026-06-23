"""Shared study result types, cutflow recording, and persistence helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


class StudyStatus(str, Enum):
    """Lifecycle status for an MV study run."""

    NOT_RUN = "NOT_RUN"
    BLOCKED = "BLOCKED"
    FIXTURE = "FIXTURE"
    PRODUCTION = "PRODUCTION"


class StudyBlockedError(Exception):
    """Raised when a study cannot proceed (missing dependency, config, etc.)."""


@dataclass
class StudyResult:
    """Structured output from an MV study."""

    study_id: str
    status: StudyStatus
    metrics: dict[str, Any] = field(default_factory=dict)
    cutflow: dict[str, int] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


class CutflowRecorder:
    """Append-only counter map for selection stages."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def record(self, stage: str, count: int) -> None:
        self._counts[stage] = int(count)

    def increment(self, stage: str, delta: int = 1) -> None:
        self._counts[stage] = self._counts.get(stage, 0) + int(delta)

    def as_dict(self) -> dict[str, int]:
        return dict(self._counts)


def write_study_result(result: StudyResult, out_dir: str | Path) -> Path:
    """Write ``StudyResult`` JSON to ``out_dir/study_result.json``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "study_result.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(result.to_dict(), handle, indent=2)
    return path


def not_run_template(study_id: str, reason: str, **extra: Any) -> StudyResult:
    """Return a NOT_RUN skeleton result with a documented blocker reason."""
    return StudyResult(
        study_id=study_id,
        status=StudyStatus.NOT_RUN,
        metrics={"reason": reason, **extra},
        notes=[reason],
    )


def blocked_template(study_id: str, reason: str, **extra: Any) -> StudyResult:
    """Return a BLOCKED skeleton result."""
    return StudyResult(
        study_id=study_id,
        status=StudyStatus.BLOCKED,
        metrics={"reason": reason, **extra},
        notes=[reason],
    )


def merge_provenance(result: StudyResult, **kwargs: Any) -> StudyResult:
    """Return a copy of *result* with extra provenance keys."""
    merged = dict(result.provenance)
    merged.update(kwargs)
    result.provenance = merged
    return result


def require_keys(records: Mapping[str, Any], keys: tuple[str, ...]) -> None:
    missing = [k for k in keys if k not in records]
    if missing:
        raise ValueError(f"track records missing required keys: {missing}")
