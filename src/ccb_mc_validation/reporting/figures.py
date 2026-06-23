"""Figure registration and catalog records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class FigureRecord:
    """Metadata for a registered validation figure."""

    figure_id: str
    study_id: str
    path: str
    caption: str
    catalog_id: str | None = None
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_FIGURE_REGISTRY: dict[str, FigureRecord] = {}


def register_figure(record: FigureRecord) -> FigureRecord:
    """Register *record* in the in-process figure catalog."""
    key = f"{record.study_id}:{record.figure_id}"
    _FIGURE_REGISTRY[key] = record
    return record


def get_registered_figures(study_id: str | None = None) -> list[FigureRecord]:
    """Return registered figures, optionally filtered by study."""
    records = list(_FIGURE_REGISTRY.values())
    if study_id is not None:
        records = [record for record in records if record.study_id == study_id]
    return records


def clear_figure_registry() -> None:
    """Clear the in-process registry (primarily for tests)."""
    _FIGURE_REGISTRY.clear()
