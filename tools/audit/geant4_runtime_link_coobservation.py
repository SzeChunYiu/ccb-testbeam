#!/usr/bin/env python3
"""Co-observe live mapped-object bytes and ELF link metadata.

This bounded Linux provenance primitive composes the validated final-build and
runtime-mapping receipts at one new stable observation boundary. For every
file-backed executable mapping it opens a pathname that still resolves to the
mapped device/inode, reads and hashes that *same file descriptor*, parses ELF
link metadata from the exact bytes just hashed, and then rechecks pathname
resolution, the executable mapping projection, and process identity.

It closes a time-of-check/time-of-use gap in the earlier two-step composition,
where file identity and ELF metadata could be obtained by separate path opens.
It does not prove the historical dynamic-loader search decision, linker command
or static inputs, late dlopen/unload behavior, non-executable relocation state,
or any Geant4 physics observable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from tools.audit.geant4_elf_link_attestation import (
    FINAL_RECEIPT_SCHEMA,
    parse_elf_link_metadata,
)
from tools.audit.geant4_runtime_codepage_attestation import (
    _projection_from_maps,
    _projection_from_receipt,
)
from tools.audit.geant4_runtime_dependency_attestation import (
    SCHEMA as RUNTIME_RECEIPT_SCHEMA,
)
from tools.audit.geant4_runtime_dependency_attestation import (
    _parse_maps,
    _read_proc_bytes,
    _read_process_starttime,
)

SCHEMA = "ccb_geant4_runtime_link_coobservation_v1"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest_body(body: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(body)).hexdigest()


def _with_receipt_digest(body: dict[str, Any]) -> dict[str, Any]:
    result = dict(body)
    result["receipt_sha256"] = _digest_body(body)
    return result


def _verify_receipt(
    receipt: dict[str, Any], *, schema: str, label: str
) -> None:
    if receipt.get("schema") != schema:
        raise ValueError(f"{label} has unsupported schema")
    if receipt.get("status") != "PASS":
        raise ValueError(f"{label} is not PASS")
    observed = receipt.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError(f"{label} is missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    if _digest_body(body) != observed:
        raise ValueError(f"{label} digest mismatch")


def _stat_identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _fd_snapshot(fd: int, *, label: str) -> tuple[bytes, dict[str, Any]]:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular file")

    digest = hashlib.sha256()
    chunks: list[bytes] = []
    offset = 0
    while offset < before.st_size:
        try:
            block = os.pread(fd, min(1024 * 1024, before.st_size - offset), offset)
        except OSError as exc:
            raise ValueError(f"cannot read {label} at offset {offset}: {exc}") from exc
        if not bloc:
            raise ValueError(f"short read while reading {label}")
        chunks.append(block)
        digest.update(block)
        offset += len(block)

    after = os.fstat(fd)
    if _stat_identity(before) != _stat_identity(after):
        raise ValueError(f"{label} changed while being read")
    if offset != before.st_size:
        raise ValueError(f"short/long read while reading {label}")

    record = {
        "bytes": offset,
        "sha256": digest.hexdigest(),
        "device_major": os.major(before.st_dev),
        "device_minor": os.minor(before.st_dev),
        "inode": before.st_ino,
        "mode": stat.S_IMODE(before.st_mode),
        "mtime_ns": before.st_mtime_ns,
        "ctime_ns": before.st_ctime_ns,
    }
    return b"".join(chunks), record


def _path_key(path_text: str, *, label: str) -> tuple[int, int, int]:
    try:
        st = os.stat(path_text)
    except OSError as exc:
        raise ValueError(f"cannot stat {label} {path_text}: {exc}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"{label} must resolve to a regular file: {path_text}")
    return (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)


def _runtime_object_key(record: dict[str, Any], *, index: int) -> tuple[int, int, int]:
    try:
        key = (
            int(record["device_major"]),
            int(record["inode"]),
            int(record["inode"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"runtime object {index} has invalid inode identity") from exc
    return key


def _coobserve_object(
    record: dict[str, Any], *, index: int
) -> dict[str, Any]:
    key = _runtime_object_key(record, index=index)
    paths = record.get("paths")
    if (
        not isinstance(paths, list)
        or not paths
        or not all(isinstance(path, str) and path.startswith("/") for path in paths)
    ):
        raise ValueError(f"runtime object {index} has invalid absolute paths")
    expected_bytes = record.get("bytes")
    expected_sha = record.get("sha256")
    if not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise ValueError(f"runtime object {index} has invalid byte count")
    if not isinstance(expected_sha, str):
        raise ValueError(f"runtime object {index} is missing sha256")

    pre_path_keys = {
        path: _path_key(path, label=f"runtime object {index} path") for path in paths
    }
    if any(observed != key for observed in pre_path_keys.values()):
        raise ValueError(f"runtime object {index} path no longer names mapped inode")

    selected_path: str | None = None
    selected_fd: int | None = None
    last_error: OSError | None = None
    for path in paths:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
        except OSError as exc:
            last_error = exc
            continue
        st = os.fstat(fd)
        observed_key = (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)
        if observed_key == key:
            selected_path = path
            selected_fd = fd
            break
        os.close(fd)

    if selected_fd is None or selected_path is None:
        detail = f": {last_error}" if last_error is not None else ""
        raise ValueError(f"cannot open mapped inode for runtime object {index}{detail}")

    try:
        data, identity = _fd_snapshot(
            selected_fd, label=f"runtime object {index} mapped backing"
        )
    finally:
        os.close(selected_fd)

    observed_key = (
        identity["device_major"],
        identity["device_minor"],
        identity["inode"],
    )
    if observed_key != key:
        raise ValueError(f"runtime object {index} open descriptor inode mismatch")
    if (identity["bytes"], identity["sha256"]) != (expected_bytes, expected_sha):
        raise ValueError(m)
            f"runtime object {index} content differs from runtime dependency receipt"
        )

    if data.startswith(b"\x7fELF"):
        elf = parse_elf_link_metadata(data)
    else:
        elf = None

    post_path_keys = {
        path: _path_key(path, label=f"runtime object {index} path recheck")
        for path in paths
    }
    if post_path_keys != pre_path_keys:
        raise ValueError(f"runtime object {index} pathname resolution changed")

    return {
        "runtime_object_index": index,
        "device_major": key[0],
        "device_minor": key[1],
        "inode": key[2],
        "paths": paths,
        "opened_path": selected_path,
        "bytes": identity["bytes"],
        "sha256": identity["sha256"],
        "mode": identity["mode"],
        "mtime_ns": identity["mtime_ns"],
        "ctime_ns": identity["ctime_ns"],
        "elf": elf,
    }


def _stable_absolute_resolution(
    path_text: str, *, label: str) -> dict[str, Any]:
    if not path_text.startswith("/"):
        raise ValueError(f"{label} is not an absolute path: {path_text}")
    key = _path_key(path_text, label=label)
    return {
        "path": path_text,
        "device_major": key[0],
        "device_minor": key[1],
        "inode": key[2],
    }


def attest_runtime_link_coobservation(
    *,
    final_receipt: dict[str, Any],
    runtime_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Attest same-descriptor ELF metadata and direct-link closure."""
    _verify_receipt(
        final_receipt,
        schema=FINAL_RECEIPT_SCHEMA,
        label="final build-binding receipt",
    )
    _verify_receipt(
        runtime_receipt,
        schema=RUNTIME_RECEIPT_SCHEMA,
        label="runtime dependency receipt",
    )
    if (
        runtime_receipt.get("parent_final_build_receipt_sha256")
        != final_receipt["receipt_sha256"]
    ):
        raise ValueError("runtime dependency receipt belongs to another final build")

    process = runtime_receipt.get("process")
    if not isinstance(process, dict):
        raise ValueError("runtime receipt has no process record")
    pid = process.get("pid")
    expected_starttime = process.get("starttime_ticks")
    process_executable = process.get("executable")
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("runtime receipt pid is invalid")
    if not isinstance(expected_starttime, int) or expected_starttime < 0:
        raise ValueError