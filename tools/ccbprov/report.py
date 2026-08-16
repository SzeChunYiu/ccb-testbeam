"""Report-directory scaffolding for the project-completion protocol.

Per AI_SESSION_MASTER_PROMPT.md ("Commit and reporting protocol" / "Phase 0"),
each report directory must contain REPORT.md, closure_matrix.csv,
manifest.json, commands.log, and a figures/ subdirectory.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["init_report_dir", "utc_stamp_now", "REPORT_ARTIFACTS"]

# The five files an initialized report dir must contain (plus figures/).
REPORT_ARTIFACTS: tuple[str, ...] = (
    "REPORT.md",
    "closure_matrix.csv",
    "manifest.json",
    "commands.log",
)
_FIGURES_SUBDIR = "figures"


def utc_stamp_now() -> str:
    """Compact UTC stamp: YYYYMMDDTHHMMSSZ."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def init_report_dir(
    base_reports_dir: str | os.PathLike[str],
    task_slug: str,
    utc_stamp: str | None = None,
) -> Path:
    """Create ``<base>/project_completion_<UTCSTAMP>/`` and its artifacts.

    Never overwrites an existing directory: if the target already exists, a
    numeric suffix (``_1``, ``_2``, ...) is appended until a free name is
    found. The directory name follows the fixed ``project_completion_<STAMP>``
    convention; ``task_slug`` is accepted for the caller's bookkeeping and is
    intentionally not written into the (empty) artifact files. Returns the
    created Path.
    """
    # task_slug is part of the documented signature but the artifacts are
    # created empty per the Definition of Done; reference it to avoid it
    # reading as dead.
    _ = task_slug
    stamp = utc_stamp if utc_stamp is not None else utc_stamp_now()
    base = Path(base_reports_dir)
    base.mkdir(parents=True, exist_ok=True)

    name = f"project_completion_{stamp}"
    target = base / name
    suffix = 1
    while target.exists():
        target = base / f"{name}_{suffix}"
        suffix += 1

    target.mkdir(parents=False, exist_ok=False)
    (target / _FIGURES_SUBDIR).mkdir()

    # All five report artifacts start empty; the caller fills them in.
    for artifact in REPORT_ARTIFACTS:
        (target / artifact).write_text("", encoding="utf-8")

    return target
