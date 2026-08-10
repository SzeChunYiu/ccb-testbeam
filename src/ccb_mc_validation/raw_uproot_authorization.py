"""Manifest-bound Uproot access for raw scientific consumers.

This adapter keeps the verified raw-input stream alive for the complete Uproot
object lifetime.  It is intentionally small: raw byte authorization belongs to
``raw_input_authorization``; this module only prevents a scientific consumer
from falling back to a second pathname open after verification.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import uproot

from ccb_mc_validation.raw_input_authorization import (
    RawInputAuthorizationError,
    verified_raw_input_stream,
)


class RawManifestIndexError(RawInputAuthorizationError):
    """Raised when run-to-manifest binding is missing, ambiguous, or malformed."""


def manifest_rows_by_run(
    rows: Iterable[Mapping[str, object]],
) -> dict[int, Mapping[str, object]]:
    """Return one and only one manifest row for each integer run identifier."""
    indexed: dict[int, Mapping[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise RawManifestIndexError("raw manifest rows must be mappings")
        if "run" not in row:
            raise RawManifestIndexError("raw manifest row is missing run")
        run = row["run"]
        if isinstance(run, bool) or not isinstance(run, int) or run < 0:
            raise RawManifestIndexError("raw manifest run must be a nonnegative integer")
        if run in indexed:
            raise RawManifestIndexError(f"duplicate raw manifest row for run {run}")
        indexed[run] = row
    return indexed


def require_manifest_rows(
    rows: Iterable[Mapping[str, object]],
    required_runs: Iterable[int],
) -> dict[int, Mapping[str, object]]:
    """Fail closed unless every required run has exactly one manifest row."""
    indexed = manifest_rows_by_run(rows)
    required: list[int] = []
    for run in required_runs:
        if isinstance(run, bool) or not isinstance(run, int) or run < 0:
            raise RawManifestIndexError("required run must be a nonnegative integer")
        required.append(run)
    missing = sorted(set(required) - set(indexed))
    if missing:
        joined = ", ".join(str(run) for run in missing)
        raise RawManifestIndexError(f"raw manifest is missing required runs: {joined}")
    return {run: indexed[run] for run in sorted(set(required))}


@contextmanager
def open_verified_uproot(
    path: Path,
    manifest_row: Mapping[str, object],
    *,
    block_size: int = 1 << 20,
) -> Iterator[object]:
    """Open Uproot on the exact stream authorized by ``manifest_row``.

    The verified descriptor context encloses the complete Uproot file lifetime.
    No pathname is passed to Uproot, so a later independent pathname reopen is
    not part of this authorization path.  Mutation-sensitive descriptor state
    is checked again when the scientific consumer exits the context.
    """
    with verified_raw_input_stream(path, manifest_row, block_size=block_size) as stream:
        with uproot.open(stream) as root_file:
            yield root_file
