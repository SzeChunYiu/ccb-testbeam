"""Paper-figure registry schema and scientific build dispositions.

The registry separates scientific evidence state from build behaviour. A status is
never silently promoted merely because a result or image exists on disk.
"""
from __future__ import annotations

import hashlib
import re
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
        "MC_MODEL_DEPENDENT",
        "DONE_DATA_ONLY",
        "SUPERSEDED",
        "EXTERNAL_BLOCKER",
        "ILLUSTRATIVE",
        "MC_MODEL_DEPENDENT",
        "DONE_DATA_ONLY",
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
    # data/MC-distinction statuses used by the 1303 and 956 registrations:
    # completed on data or single-model MC but not cross-closed -> quarantined
    # from auto paper-promotion until their named gates close.
    "MC_MODEL_DEPENDENT": "QUARANTINED",
    "DONE_DATA_ONLY": "QUARANTINED",
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
REGISTRY_SNAPSHOT_METHOD = "SINGLE_READ_STRICT_UTF8_DUPLICATE_KEY_REJECTING_YAML"
_SAFE_ENTRY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class RegistryFormatError(ValueError):
    """Raised when registry bytes cannot be interpreted without ambiguity."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys at every depth."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        if not isinstance(node, yaml.MappingNode):
            raise RegistryFormatError(
                f"expected a YAML mapping node, got {type(node).__name__}"
            )
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        first_marks: dict[Any, yaml.error.Mark] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                line = key_node.start_mark.line + 1
                column = key_node.start_mark.column + 1
                raise RegistryFormatError(
                    f"unhashable YAML mapping key at line {line}, column {column}"
                ) from exc
            if duplicate:
                first = first_marks[key]
                line = key_node.start_mark.line + 1
                column = key_node.start_mark.column + 1
                raise RegistryFormatError(
                    f"duplicate YAML key {key!r} at line {line}, column {column}; "
                    f"first defined at line {first.line + 1}, column {first.column + 1}"
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
            first_marks[key] = key_node.start_mark
        return mapping


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


@dataclass(frozen=True)
class RegistrySnapshot:
    """Parsed registry entries bound to one immutable byte snapshot."""

    path: str
    raw: bytes = field(repr=False)
    sha256: str
    size_bytes: int
    entries: tuple[Entry, ...]
    snapshot_method: str = REGISTRY_SNAPSHOT_METHOD


def _entries_from_document(document: Any, registry_path: Path) -> list[Entry]:
    if not isinstance(document, dict):
        raise RegistryFormatError(
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


def load_registry_snapshot(path: str | Path) -> RegistrySnapshot:
    """Read once, decode strictly, reject duplicate keys, and parse the registry."""

    registry_path = Path(path)
    try:
        raw = registry_path.read_bytes()
    except OSError as exc:
        raise RegistryFormatError(f"could not read registry {registry_path}: {exc}") from exc
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RegistryFormatError(
            f"registry {registry_path} is not strict UTF-8: {exc}"
        ) from exc
    try:
        document = yaml.load(text, Loader=_UniqueKeySafeLoader) or {}
    except RegistryFormatError as exc:
        raise RegistryFormatError(f"registry {registry_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise RegistryFormatError(f"registry {registry_path} is invalid YAML: {exc}") from exc

    entries = _entries_from_document(document, registry_path)
    return RegistrySnapshot(
        path=str(registry_path),
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        entries=tuple(entries),
    )


def load_registry(path: str | Path) -> list[Entry]:
    """Load a duplicate-key-safe registry while preserving the public list API."""

    return list(load_registry_snapshot(path).entries)


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
        if entry.id and not _SAFE_ENTRY_ID.fullmatch(entry.id):
            problems.append(
                f"{tag}: id must match {_SAFE_ENTRY_ID.pattern!r} for safe output paths"
            )
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
