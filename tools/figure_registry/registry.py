"""Paper-figure registry schema and scientific build dispositions.

The registry separates scientific evidence state from build behaviour.  A status
is never silently promoted merely because a result or image exists on disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ALLOWED_STATUSES: frozenset[str] = frozenset(
    {
        "VALIDATED",
        "PRELIMINARY",
        "TENSION",
        "SIMULATION_RESULT",
        "MC_METHOD_CLOSURE",
        "PARTIAL",
        "GATED",
        "BLOCKED",
        "SUPERSEDED",
        "EXTERNAL_BLOCKER",
        "ILLUSTRATIVE",
    }
)

ALLOWED_KINDS: frozenset[str] = frozenset(
    {"quantitative", "figure_sourced", "illustrative"}
)

STATUS_DISPOSITIONS: dict[str, str] = {
    "VALIDATED": "BUILD",
    "TENSION": "BUILD",
    "PRELIMINARY": "CONDITIONAL",
    "SIMULATION_RESULT": "QUARANTINED",
    "MC_METHOD_CLOSURE": "QUARANTINED",
    "PARTIAL": "QUARANTINED",
    "GATED": "QUARANTINED",
    "BLOCKED": "QUARANTINED",
    "SUPERSEDED": "QUARANTINED",
    "EXTERNAL_BLOCKER": "BLOCKED",
    "ILLUSTRATIVE": "ILLUSTRATIVE",
}

_PAPER_QUANTITATIVE_STATUSES: frozenset[str] = frozenset(
    {"VALIDATED", "TENSION", "PRELIMINARY"}
)
_BLOCKED_STATUSES: frozenset[str] = frozenset({"EXTERNAL_BLOCKER"})
_QUARANTINED_STATUSES: frozenset[str] = frozenset(
    {
        "SIMULATION_RESULT",
        "MC_METHOD_CLOSURE",
        "PARTIAL",
        "GATED",
        "BLOCKED",
        "SUPERSEDED",
    }
)

DEFAULT_UNCERTAINTY_KEY = "uncertainty"


@dataclass
class Entry:
    """A single registry entry."""

    id: str
    result: str
    status: str
    kind: str
    caption: str
    source_figure: str | None = None
    table: str | None = None
    input_sha256: str | None = None
    uncertainty_key: str = DEFAULT_UNCERTAINTY_KEY
    value_key: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_quantitative(self) -> bool:
        return self.kind == "quantitative"

    @property
    def is_figure_sourced(self) -> bool:
        return self.kind == "figure_sourced"

    @property
    def is_illustrative(self) -> bool:
        return self.kind == "illustrative"

    @property
    def disposition(self) -> str:
        return STATUS_DISPOSITIONS.get(self.status, "INVALID")


def load_registry(path: str | Path) -> list[Entry]:
    """Load a YAML registry while deferring structural errors to validation."""

    registry_path = Path(path)
    with registry_path.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    if not isinstance(document, dict):
        raise ValueError(
            f"registry {registry_path} must be a top-level mapping of id -> entry, "
            f"got {type(document).__name__}"
        )

    entries: list[Entry] = []
    for entry_id, body in document.items():
        body = body or {}
        if not isinstance(body, dict):
            entries.append(
                Entry(
                    id=str(entry_id),
                    result="",
                    status="",
                    kind="",
                    caption="",
                    raw={"_malformed": body},
                )
            )
            continue
        entries.append(
            Entry(
                id=str(entry_id),
                result=str(body.get("result", "") or ""),
                status=str(body.get("status", "") or ""),
                kind=str(body.get("kind", "") or ""),
                caption=str(body.get("caption", "") or ""),
                source_figure=(
                    str(body["source_figure"]) if body.get("source_figure") else None
                ),
                table=(str(body["table"]) if body.get("table") else None),
                input_sha256=(
                    str(body["input_sha256"]) if body.get("input_sha256") else None
                ),
                uncertainty_key=str(
                    body.get("uncertainty_key") or DEFAULT_UNCERTAINTY_KEY
                ),
                value_key=(str(body["value_key"]) if body.get("value_key") else None),
                raw=dict(body),
            )
        )
    return entries


def validate_registry(entries: list[Entry]) -> list[str]:
    """Return structural problems; an empty list means the schema is clean."""

    problems: list[str] = []
    seen: dict[str, int] = {}
    for entry in entries:
        if not entry.id:
            problems.append("entry with empty id")
            continue
        seen[entry.id] = seen.get(entry.id, 0) + 1
    for entry_id, count in seen.items():
        if count > 1:
            problems.append(f"{entry_id}: duplicate id appears {count} times")

    for entry in entries:
        tag = entry.id or "<no-id>"
        if entry.raw.get("_malformed") is not None:
            problems.append(f"{tag}: entry body is not a mapping")
            continue
        if not entry.caption:
            problems.append(f"{tag}: missing required 'caption'")
        if not entry.status:
            problems.append(f"{tag}: missing required 'status'")
        elif entry.status not in ALLOWED_STATUSES:
            problems.append(
                f"{tag}: status {entry.status!r} not in allowed set "
                f"{sorted(ALLOWED_STATUSES)}"
            )
        if not entry.kind:
            problems.append(f"{tag}: missing required 'kind'")
        elif entry.kind not in ALLOWED_KINDS:
            problems.append(
                f"{tag}: kind {entry.kind!r} not in {sorted(ALLOWED_KINDS)}"
            )

        if entry.status == "ILLUSTRATIVE" and entry.kind != "illustrative":
            problems.append(
                f"{tag}: status ILLUSTRATIVE requires kind 'illustrative'"
            )
        if entry.kind == "illustrative" and entry.status != "ILLUSTRATIVE":
            problems.append(
                f"{tag}: kind 'illustrative' requires status ILLUSTRATIVE"
            )

        if entry.kind in {"illustrative", "figure_sourced"}:
            if not entry.source_figure:
                problems.append(
                    f"{tag}: kind {entry.kind!r} requires 'source_figure' path"
                )
        elif entry.kind == "quantitative":
            if entry.disposition in {"BUILD", "CONDITIONAL"} and not entry.result:
                problems.append(
                    f"{tag}: build-authorized quantitative entry requires 'result' path"
                )

        if entry.input_sha256 and not entry.table:
            problems.append(f"{tag}: input_sha256 given but no 'table' to hash")

    return problems
