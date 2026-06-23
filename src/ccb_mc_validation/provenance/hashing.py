"""SHA-256 helpers for pinned study inputs and outputs."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path | str, *, chunk_size: int = 1 << 20) -> str:
    """Return hex SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return hex SHA-256 digest of a byte string."""
    return hashlib.sha256(data).hexdigest()
