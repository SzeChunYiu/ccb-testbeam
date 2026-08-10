"""Same-bytes verified-read snapshots for authoritative S00 artifacts.

A content-bound publication pointer proves that an authoritative file had the
expected bytes when it was verified. Returning that mutable pathname is not, by
itself, a same-bytes read guarantee because a writer can mutate or replace the
file before a downstream consumer opens it.

This module closes that read-side TOCTOU gap for authorising consumers by
materialising a private snapshot while hashing the exact bytes copied. The
consumer receives the snapshot only when its digest equals the digest committed
in the publication pointer. Later mutation of the generation path, including
through a hard-link alias, cannot change the already materialised snapshot.

Threat model: protect scientific readers against concurrent/cooperating
filesystem mutation and ordinary pathname replacement. This is not a defence
against a privileged attacker that can alter the reader's private temporary
file or process memory.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import tempfile
from typing import Iterator

from ccb_mc_validation.s00_publication import (
    S00PublicationError,
    S00PublicationPointer,
    _validated_artifact_path,
    read_publication_pointer,
)


@dataclass(frozen=True)
class S00VerifiedArtifactSnapshot:
    """One private, content-verified snapshot of an authoritative artifact."""

    path: Path
    pointer: S00PublicationPointer
    logical_name: str
    sha256: str
    source_device: int
    source_inode: int
    source_nlink: int
    source_size: int


def _snapshot_suffix(relative_path: str) -> str:
    """Preserve compound suffixes such as ``.csv.gz`` for downstream readers."""
    return "".join(Path(relative_path).suffixes)


def _open_source_no_follow(path: Path) -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise S00PublicationError(
            f"failed to open authoritative artifact without following links: {path}: {exc}"
        ) from exc
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(fd)
        raise S00PublicationError(
            f"authoritative artifact must be a regular file: {path}"
        )
    return fd


@contextmanager
def verified_artifact_snapshot(
    pointer_path: Path,
    generation_root: Path,
    logical_name: str,
    *,
    scratch_dir: Path | None = None,
    block_size: int = 1024 * 1024,
) -> Iterator[S00VerifiedArtifactSnapshot]:
    """Yield a private snapshot containing exactly the pointer-authorised bytes.

    The publication pointer is read once, defining one old-or-new authority
    snapshot. The named generation file is physically validated, opened with
    ``O_NOFOLLOW`` when the platform exposes it, and copied into a securely
    created temporary file. SHA-256 is accumulated over the exact copied bytes.
    The snapshot is yielded only if that digest matches the digest in the pointer.

    Because downstream consumption occurs from the private snapshot rather than
    by reopening the generation pathname, mutation of the source after the copy
    cannot change the consumed bytes. A mutation before or during copying either
    reproduces the authorised digest exactly or fails closed.
    """
    if not isinstance(block_size, int) or isinstance(block_size, bool) or block_size < 1:
        raise S00PublicationError("block_size must be a positive integer")

    pointer_path = Path(pointer_path)
    generation_root = Path(generation_root)
    pointer = read_publication_pointer(pointer_path)
    if logical_name not in pointer.artifacts:
        raise S00PublicationError(f"unknown logical artifact {logical_name!r}")

    relative_path = pointer.artifacts[logical_name]
    generation = generation_root / pointer.generation_id
    source_path = _validated_artifact_path(
        generation,
        relative_path,
        logical_name=logical_name,
    )
    expected_sha256 = pointer.artifact_sha256[logical_name]

    if scratch_dir is not None:
        scratch = Path(scratch_dir)
        if not scratch.is_dir():
            raise S00PublicationError(
                f"verified-read scratch_dir does not exist or is not a directory: {scratch}"
            )
    else:
        scratch = None

    source_fd = _open_source_no_follow(source_path)
    source_metadata = os.fstat(source_fd)
    snapshot_path: Path | None = None
    snapshot_fd: int | None = None
    try:
        snapshot_fd, snapshot_name = tempfile.mkstemp(
            prefix=".s00-verified-",
            suffix=_snapshot_suffix(relative_path),
            dir=scratch,
        )
        snapshot_path = Path(snapshot_name)
        digest = hashlib.sha256()
        with os.fdopen(source_fd, "rb", closefd=True) as source_handle:
            source_fd = -1
            with os.fdopen(snapshot_fd, "wb", closefd=True) as snapshot_handle:
                snapshot_fd = -1
                while True:
                    block = source_handle.read(block_size)
                    if not block:
                        break
                    digest.update(block)
                    snapshot_handle.write(block)
                snapshot_handle.flush()
                os.fsync(snapshot_handle.fileno())

        observed_sha256 = digest.hexdigest()
        if observed_sha256 != expected_sha256:
            raise S00PublicationError(
                "verified snapshot content hash mismatch for "
                f"{logical_name!r}: expected {expected_sha256}, "
                f"observed {observed_sha256}"
            )

        os.chmod(snapshot_path, 0o400)
        yield S00VerifiedArtifactSnapshot(
            path=snapshot_path,
            pointer=pointer,
            logical_name=logical_name,
            sha256=observed_sha256,
            source_device=int(source_metadata.st_dev),
            source_inode=int(source_metadata.st_ino),
            source_nlink=int(source_metadata.st_nlink),
            source_size=int(source_metadata.st_size),
        )
    finally:
        if source_fd is not None and source_fd >= 0:
            os.close(source_fd)
        if snapshot_fd is not None and snapshot_fd >= 0:
            os.close(snapshot_fd)
        if snapshot_path is not None:
            try:
                snapshot_path.unlink(missing_ok=True)
            except OSError as exc:
                raise S00PublicationError(
                    f"failed to remove verified snapshot {snapshot_path}: {exc}"
                ) from exc
