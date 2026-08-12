"""Authorising S00 reads must consume verified snapshots (#1149)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ccb_mc_validation.s00_verified_read import (
    S00VerifiedArtifactSnapshot,
    verified_artifact_snapshot,
)


@contextmanager
def authorising_artifact_snapshot(
    pointer_path: Path,
    generation_root: Path,
    logical_name: str,
    *,
    scratch_dir: Path | None = None,
) -> Iterator[S00VerifiedArtifactSnapshot]:
    """Only authorising entry point: private snapshot, never generation pathname.

    Callers must not reopen the generation path after hashing. This wrapper is
    the Wave D contract surface for #1149.
    """
    with verified_artifact_snapshot(
        pointer_path,
        generation_root,
        logical_name,
        scratch_dir=scratch_dir,
    ) as snapshot:
        yield snapshot


def forbid_generation_path_for_authorising_read(path: Path, generation_root: Path) -> None:
    """Fail closed if a caller attempts to authorise from the mutable generation path."""
    path = Path(path).resolve()
    root = Path(generation_root).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return
    raise RuntimeError(
        f"refusing authorising read of mutable generation pathname {path} under "
        f"{root}; use authorising_artifact_snapshot (#1149)"
    )
