"""Fail-closed authorization of raw-input bytes for scientific consumers.

A provenance row that was produced from one stable byte stream does not by
itself authorize a later independent pathname reopen.  This module binds a
consumer to the same manifest content identity and descriptor identity before
exposing a seekable binary stream.
"""
from __future__ import annotations

import errno
import hashlib
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator, Mapping


class RawInputAuthorizationError(RuntimeError):
    """Raised when a raw input cannot be authorized against its manifest row."""


_REQUIRED_INTEGER_FIELDS = (
    "bytes",
    "source_dev",
    "source_ino",
    "source_nlink",
    "source_mtime_ns",
    "source_ctime_ns",
)


def _manifest_identity(row: Mapping[str, object]) -> dict[str, object]:
    """Parse the strict identity subset used by the consumer boundary."""
    missing = [name for name in ("file", "sha256", *_REQUIRED_INTEGER_FIELDS) if name not in row]
    if missing:
        raise RawInputAuthorizationError(
            "raw input manifest row is missing fields: " + ", ".join(missing)
        )

    file_value = row["file"]
    if not isinstance(file_value, str) or not file_value:
        raise RawInputAuthorizationError("raw input manifest file must be a nonempty string")

    digest = row["sha256"]
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or digest.lower() != digest
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise RawInputAuthorizationError(
            "raw input manifest sha256 must be 64 lowercase hexadecimal characters"
        )

    parsed: dict[str, object] = {"file": file_value, "sha256": digest}
    for name in _REQUIRED_INTEGER_FIELDS:
        value = row[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise RawInputAuthorizationError(
                f"raw input manifest {name} must be an integer"
            )
        if value < 0:
            raise RawInputAuthorizationError(
                f"raw input manifest {name} must be nonnegative"
            )
        parsed[name] = value
    if int(parsed["source_nlink"]) < 1:
        raise RawInputAuthorizationError(
            "raw input manifest source_nlink must be at least one"
        )
    return parsed


def _descriptor_identity(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    """Return mutation/alias-sensitive identity fields for an opened source."""
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_nlink),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


def _expected_identity(row: Mapping[str, object]) -> tuple[int, int, int, int, int, int]:
    return (
        int(row["source_dev"]),
        int(row["source_ino"]),
        int(row["source_nlink"]),
        int(row["bytes"]),
        int(row["source_mtime_ns"]),
        int(row["source_ctime_ns"]),
    )


def _hash_descriptor(descriptor: int, block_size: int) -> tuple[str, int]:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    byte_count = 0
    while True:
        block = os.read(descriptor, block_size)
        if not block:
            break
        digest.update(block)
        byte_count += len(block)
    return digest.hexdigest(), byte_count


@contextmanager
def verified_raw_input_stream(
    path: Path,
    manifest_row: Mapping[str, object],
    block_size: int = 1 << 20,
) -> Iterator[BinaryIO]:
    """Yield one seekable stream authorized by a prior raw-input manifest row.

    The function opens ``path`` exactly once with ``O_NOFOLLOW``, verifies the
    opened regular file against the manifest digest and descriptor metadata,
    then yields a duplicate descriptor as a binary file-like object.  The
    original descriptor remains open as a guard and is re-checked after the
    consumer finishes.  Any mutation or alias-state change during the consumer
    transaction fails closed before that transaction may be treated as
    authorizing scientific output.

    The bounded contract assumes ordinary filesystem metadata semantics.  It
    does not claim protection from a privileged hostile writer capable of
    changing bytes while also forging/restoring inode metadata.
    """
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    expected = _manifest_identity(manifest_row)
    if str(path) != expected["file"]:
        raise RawInputAuthorizationError(
            "raw input path does not match the manifest row: "
            f"{path} != {expected['file']}"
        )

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise RawInputAuthorizationError(
            "raw consumer authorization requires os.O_NOFOLLOW"
        )
    try:
        descriptor = os.open(path, os.O_RDONLY | nofollow)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise RawInputAuthorizationError(
                f"raw input final path component must not be a symlink: {path}"
            ) from exc
        raise

    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RawInputAuthorizationError(f"raw input is not a regular file: {path}")
        if _descriptor_identity(before) != _expected_identity(expected):
            raise RawInputAuthorizationError(
                f"raw input descriptor identity does not match manifest: {path}"
            )

        digest, byte_count = _hash_descriptor(descriptor, block_size)
        verified = os.fstat(descriptor)
        if _descriptor_identity(verified) != _descriptor_identity(before):
            raise RawInputAuthorizationError(
                f"raw input changed while being verified for consumption: {path}"
            )
        if byte_count != int(expected["bytes"]) or digest != expected["sha256"]:
            raise RawInputAuthorizationError(
                f"raw input content does not match manifest: {path}"
            )

        os.lseek(descriptor, 0, os.SEEK_SET)
        consumer_descriptor = os.dup(descriptor)
        try:
            with os.fdopen(consumer_descriptor, "rb") as stream:
                try:
                    yield stream
                except BaseException:
                    raise
                else:
                    final = os.fstat(descriptor)
                    if _descriptor_identity(final) != _descriptor_identity(verified):
                        raise RawInputAuthorizationError(
                            f"raw input changed while consumer held authorized stream: {path}"
                        )
        except BaseException:
            raise
    finally:
        os.close(descriptor)
