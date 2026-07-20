"""Result registry: load + validate the paper-figure YAML registry.

The registry is the single source of truth that binds every quantitative paper
figure to a *validated result file* (JSON) and, optionally, a source table with
a recorded sha256.  No quantitative paper figure may read a hand-entered
constant -- this module is what enforces that at build time (see ``builder``).

Governance: KNOWN_CODE_DEFECTS.md + v2 governance finding #10 flagged
``scripts/generate_publication_figures.py`` for (a) embedding headline values as
Python constants and (b) mixing illustrative schematics with quantitative
figures.  The registry fixes both: quantitative entries are driven only by
result files, and illustrative schematics are a separate ``kind`` kept apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Status + kind vocabulary (explicit, per task spec)
# ---------------------------------------------------------------------------

#: Every status the registry recognises.  Anything outside this set is a hard
#: error (the figure cannot be built or blocked -- the registry is malformed).
ALLOWED_STATUSES: frozenset[str] = frozenset(
    {"VALIDATED", "PRELIMINARY", "TENSION", "EXTERNAL_BLOCKER", "ILLUSTRATIVE"}
)

#: Quantitative statuses that render a real figure driven by a result file.
#: PRELIMINARY only renders when ``--allow-preliminary`` is passed.
_PAPER_QUANTITATIVE_STATUSES: frozenset[str] = frozenset(
    {"VALIDATED", "TENSION", "PRELIMINARY"}
)

#: Statuses that are reported BLOCKED (not FAIL) -- results legitimately absent
#: because an upstream compute step has not produced them yet.
_BLOCKED_STATUSES: frozenset[str] = frozenset({"EXTERNAL_BLOCKER"})

ALLOWED_KINDS: frozenset[str] = frozenset({"quantitative", "illustrative"})

DEFAULT_UNCERTAINTY_KEY = "uncertainty"


@dataclass
class Entry:
    """A single registry entry (one paper figure)."""

    id: str
    result: str
    status: str
    kind: str
    caption: str
    table: str | None = None
    input_sha256: str | None = None
    uncertainty_key: str = DEFAULT_UNCERTAINTY_KEY
    value_key: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_quantitative(self) -> bool:
        return self.kind == "quantitative"

    @property
    def is_illustrative(self) -> bool:
        return self.kind == "illustrative"


def load_registry(path: str | Path) -> list[Entry]:
    """Load a YAML registry file into a list of :class:`Entry`.

    The YAML top level is a mapping ``{id: {result, status, kind, ...}}``.
    Missing structural keys are tolerated here (surfaced by
    :func:`validate_registry`) so that validation reports *all* problems at
    once rather than crashing on the first malformed row.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}

    if not isinstance(doc, dict):
        raise ValueError(
            f"registry {path} must be a top-level mapping of id -> entry, "
            f"got {type(doc).__name__}"
        )

    entries: list[Entry] = []
    for entry_id, body in doc.items():
        body = body or {}
        if not isinstance(body, dict):
            # Keep a placeholder so validate_registry can report it.
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
    """Return a list of human-readable structural problems (empty == clean).

    This checks *shape* only -- it does not touch the filesystem or the result
    JSON.  Filesystem / value checks (missing result, missing uncertainty,
    sha256 mismatch) happen in :func:`builder.build`.
    """
    problems: list[str] = []

    seen: dict[str, int] = {}
    for e in entries:
        if not e.id:
            problems.append("entry with empty id")
            continue
        seen[e.id] = seen.get(e.id, 0) + 1

    for eid, count in seen.items():
        if count > 1:
            problems.append(f"{eid}: duplicate id appears {count} times")

    for e in entries:
        tag = e.id or "<no-id>"

        if e.raw.get("_malformed") is not None:
            problems.append(f"{tag}: entry body is not a mapping")
            continue

        if not e.result:
            problems.append(f"{tag}: missing required 'result' path")
        if not e.caption:
            problems.append(f"{tag}: missing required 'caption'")

        if not e.status:
            problems.append(f"{tag}: missing required 'status'")
        elif e.status not in ALLOWED_STATUSES:
            problems.append(
                f"{tag}: status {e.status!r} not in allowed set "
                f"{sorted(ALLOWED_STATUSES)}"
            )

        if not e.kind:
            problems.append(f"{tag}: missing required 'kind'")
        elif e.kind not in ALLOWED_KINDS:
            problems.append(
                f"{tag}: kind {e.kind!r} not in {sorted(ALLOWED_KINDS)}"
            )

        # Separation invariant: schematic <-> illustrative, one implies the other.
        if e.status == "ILLUSTRATIVE" and e.kind and e.kind != "illustrative":
            problems.append(
                f"{tag}: status ILLUSTRATIVE requires kind 'illustrative' "
                f"(got {e.kind!r}) -- schematics must be kept separate from "
                f"quantitative figures"
            )
        if e.kind == "illustrative" and e.status and e.status != "ILLUSTRATIVE":
            problems.append(
                f"{tag}: kind 'illustrative' requires status ILLUSTRATIVE "
                f"(got {e.status!r})"
            )

        # A recorded input hash is meaningless without a table to hash.
        if e.input_sha256 and not e.table:
            problems.append(
                f"{tag}: input_sha256 given but no 'table' to hash"
            )

    return problems
