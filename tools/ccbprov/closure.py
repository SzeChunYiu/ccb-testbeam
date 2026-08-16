"""Closure-matrix helpers.

A closure matrix is the project-completion ledger: one row per task, each
carrying a status from the closure enum, its evidence, and acceptance
criteria. See schemas/closure_record.schema.json.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Any

__all__ = ["CLOSURE_STATUSES", "ClosureRow", "write_closure_matrix"]

# Must match the enum in schemas/closure_record.schema.json.
CLOSURE_STATUSES: tuple[str, ...] = (
    "READY",
    "IN_PROGRESS",
    "DONE",
    "CORRECTED",
    "BLOCKED_COMPUTE",
    "BLOCKED_EXTERNAL",
    "SUPERSEDED",
    "FAILED_INFORMATIVE",
)

CSV_HEADER: tuple[str, ...] = (
    "task_id",
    "status",
    "issue",
    "dependencies",
    "evidence",
    "notes",
    "n_acceptance",
    "n_passed",
)


@dataclass
class ClosureRow:
    """One task's closure state.

    acceptance is a list of {criterion, passed, evidence?} dicts.
    """

    task_id: str
    status: str
    issue: str | None = None
    dependencies: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    acceptance: list[dict[str, Any]] = field(default_factory=list)
    notes: str | None = None

    def _validate(self) -> None:
        if not self.task_id:
            raise ValueError("ClosureRow.task_id must be non-empty")
        if self.status not in CLOSURE_STATUSES:
            raise ValueError(
                f"invalid closure status {self.status!r}; "
                f"must be one of {', '.join(CLOSURE_STATUSES)}"
            )
        for i, acc in enumerate(self.acceptance):
            if "criterion" not in acc or "passed" not in acc:
                raise ValueError(
                    f"acceptance[{i}] must have 'criterion' and 'passed' keys"
                )
            if not isinstance(acc["passed"], bool):
                raise ValueError(f"acceptance[{i}]['passed'] must be a bool")

    @property
    def n_acceptance(self) -> int:
        return len(self.acceptance)

    @property
    def n_passed(self) -> int:
        return sum(1 for a in self.acceptance if a.get("passed") is True)

    def to_record(self) -> dict[str, Any]:
        """Return the full closure record (schema-shaped)."""
        self._validate()
        rec: dict[str, Any] = {
            "task_id": self.task_id,
            "status": self.status,
            "issue": self.issue,
            "dependencies": list(self.dependencies),
            "evidence": list(self.evidence),
            "acceptance": [dict(a) for a in self.acceptance],
        }
        if self.notes is not None:
            rec["notes"] = self.notes
        return rec

    def to_csv_row(self) -> dict[str, Any]:
        self._validate()
        return {
            "task_id": self.task_id,
            "status": self.status,
            "issue": self.issue or "",
            "dependencies": ";".join(self.dependencies),
            "evidence": ";".join(self.evidence),
            "notes": self.notes or "",
            "n_acceptance": self.n_acceptance,
            "n_passed": self.n_passed,
        }


def write_closure_matrix(
    rows: list[ClosureRow],
    csv_path: str | os.PathLike[str],
    json_path: str | os.PathLike[str],
) -> tuple[str, str]:
    """Write both a flat CSV and a full-record JSON array.

    Validates every row's status against the enum first; raises ValueError on
    an invalid row before any file is written.
    """
    # Validate all rows up front (fail before writing anything).
    records = [r.to_record() for r in rows]
    csv_rows = [r.to_csv_row() for r in rows]

    csv_p = os.fspath(csv_path)
    json_p = os.fspath(json_path)
    for p in (csv_p, json_p):
        parent = os.path.dirname(p)
        if parent:
            os.makedirs(parent, exist_ok=True)

    with open(csv_p, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_HEADER))
        writer.writeheader()
        for row in csv_rows:
            writer.writerow(row)

    with open(json_p, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, sort_keys=True)
        fh.write("\n")

    return csv_p, json_p
