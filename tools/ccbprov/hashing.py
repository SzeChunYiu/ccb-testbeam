"""Content hashing helpers for provenance file records.

A "file record" is the {path, sha256, size_bytes} object referenced by the
run-manifest schema. Hashing is streamed so multi-GB Geant4 outputs do not
have to be held in memory.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

__all__ = ["sha256_file", "file_record"]

_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Return the hex SHA-256 digest of the file at *path*.

    Raises FileNotFoundError with a clear message if the path does not exist
    or is not a regular file.
    """
    p = os.fspath(path)
    if not os.path.exists(p):
        raise FileNotFoundError(f"sha256_file: no such file: {p!r}")
    if not os.path.isfile(p):
        raise FileNotFoundError(f"sha256_file: not a regular file: {p!r}")
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def file_record(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Return a provenance file record for *path*.

    Shape: {"path": str, "sha256": <64 hex>, "size_bytes": int}.
    The ``path`` is returned as given (caller decides absolute vs relative).
    Raises FileNotFoundError for a missing path.
    """
    p = os.fspath(path)
    digest = sha256_file(p)  # validates existence
    return {
        "path": str(path),
        "sha256": digest,
        "size_bytes": os.path.getsize(p),
    }
