"""Persistent registry of MC validation study results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ResultRegistry:
    """JSON-backed registry of study summaries."""

    schema_version: str = "1.0.0"
    studies: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> ResultRegistry:
        registry_path = Path(path)
        if not registry_path.is_file():
            return cls()
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("registry root must be a mapping")
        schema_version = str(payload.get("schema_version", "1.0.0"))
        studies = payload.get("studies", {})
        if not isinstance(studies, dict):
            raise ValueError("registry.studies must be a mapping")
        return cls(schema_version=schema_version, studies={str(k): dict(v) for k, v in studies.items()})

    def save(self, path: str | Path) -> Path:
        registry_path = Path(path)
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.schema_version,
            "studies": self.studies,
        }
        registry_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return registry_path

    def upsert(self, study_id: str, summary: dict[str, Any]) -> None:
        self.studies[str(study_id)] = dict(summary)

    def get(self, study_id: str) -> dict[str, Any] | None:
        return self.studies.get(str(study_id))
