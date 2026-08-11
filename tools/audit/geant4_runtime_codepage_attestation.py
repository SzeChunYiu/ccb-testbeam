#!/usr/bin/env python3
"""Compare live executable mapping bytes with their attested file backing.

This is a bounded Linux runtime-provenance primitive for the CCB Geant4
chain. It consumes a validated ``ccb_geant4_runtime_dependency_attestation_v1``
receipt, re-identifies the same live process and executable mapping set, reads
those executable virtual-address ranges through ``/proc/<pid>/mem``, and
compares every byte with the corresponding offset in the already-attested
backing file. A partial final file page is compared against the Linux mmap
zero-fill rule; whole pages beyond backing EOF are rejected.

The receipt establishes equality between *observed executable memory bytes*
and *current bytes of the same dev/inode backing object* while the executable
mapping projection is stable. It does not identify the mechanism if the bytes
differ, prove linker commands, bind non-executable relocated data, exclude
later runtime modification/dlopen, or validate Geant4 physics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_runtime_codepage_attestation_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"
KERNEL_EXECUTABLE_PSEUDO_MAPPINGS = frozenset({"[vdso]", "[vsyscall]"})


@dataclass(frozen=True)
class MapEntry:
    start: int
    end: int
    perms: str
    offset: int
    dev_major: int
    dev_minor: int
    inode: int
    pathname: str | None

    @property
    def executable(self) -> bool:
        return "x" in self.perms

    @property
    def file_backed(self) -> bool:
        return self.inode != 0


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


def _verify_runtime_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != RUNTIME_RECEIPT_SCHEMA:
        raise ValueError("unsupported runtime dependency receipt schema")
    if receipt.get("status") != "PASS":
        raise ValueError("runtime dependency receipt is not PASS")
    observed = receipt.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError("runtime dependency receipt is missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    if _digest_body(body) != observed:
        raise ValueError("runtime dependency receipt digest mismatch")


def _read_proc_bytes(proc_dir: Path, name: str, *, label: str) -> bytes:
    path = proc_dir / name
    try:
        with path.open("rb") as stream:
            return stream.read()
    except OSError as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc


def _read_process_starttime(proc_dir: Path) -> int:
    raw = _read_proc_bytes(proc_dir, "stat", label="process stat")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("process stat is not ASCII") from exc
    close = text.rfind(")")
    if close < 0:
        raise ValueError("process stat has no closing command delimiter")
    tail = text[close + 1 :].strip().split()
    if len(tail) <= 19:
        raise ValueError("process stat is too short to contain starttime")
    try:
        starttime = int(tail[19], 10)
    except ValueError as exc:
        raise ValueError("process stat starttime is not an integer") from exc
    if starttime < 0:
        raise ValueError("process stat starttime must be nonnegative")
    return starttime


def _parse_maps(payload: bytes) -> list[MapEntry]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("process maps is not valid UTF-8") from exc

    result: list[MapEntry] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        parts = line.split(maxsplit=5)
        if len(parts) < 5:
            raise ValueError(f"malformed /proc maps line {line_number}: {line!r}")
        address, perms, offset_text, dev_text, inode_text = parts[:5]
        pathname = parts[5] if len(parts) == 6 else None
        start_text, dash, end_text = address.partition("-")
        major_text, colon, minor_text = dev_text.partition(":")
        if not dash or not colon or len(perms) != 4:
            raise ValueError(f"malformed /proc maps line {line_number}: {line!r}")
        try:
            entry = MapEntry(
                start=int(start_text, 16),
                end=int(end_text, 16),
                perms=perms,
                offset=int(offset_text, 16),
                dev_major=int(major_text, 16),
                dev_minor=int(minor_text, 16),
                inode=int(inode_text, 10),
                pathname=pathname,
            )
        except ValueError as exc:
            raise ValueError(
                f"invalid numeric field in /proc maps line {line_number}: {line!r}"
            ) from exc
        if entry.start >= entry.end:
            raise ValueError(f"non-positive mapping extent on line {line_number}")
        result.append(entry)
    if not result:
        raise ValueError("process maps is empty")
    return result


def _projection_from_maps(
    entries: list[MapEntry],
) -> dict[tuple[int, int, int], dict[str, Any]]:
    groups: dict[tuple[int, int, int], dict[str, Any]] = {}
    for entry in entries:
        if not entry.executable:
            continue
        if not entry.file_backed:
            if entry.pathname in KERNEL_EXECUTABLE_PSEUDO_MAPPINGS:
                continue
            raise ValueError(
                "unattributed anonymous executable mapping is present: "
                f"{entry.pathname or '<anonymous>'} "
                f"{entry.start:x}-{entry.end:x}"
            )
        if entry.pathname is None or not entry.pathname.startswith("/"):
            raise ValueError("file-backed executable mapping has no absolute pathname")
        if entry.pathname.endswith(" (deleted)"):
            raise ValueError("file-backed executable mapping is deleted")
        key = (entry.dev_major, entry.dev_minor, entry.inode)
        group = groups.setdefault(key, {"paths": set(), "segments": []})
        group["paths"].add(entry.pathname)
        group["segments"].append((entry.start, entry.end, entry.perms, entry.offset))
    if not groups:
        raise ValueError("process has no attestable file-backed executable mappings")
    return {
        key: {
            "paths": tuple(sorted(group["paths"])),
            "segments": tuple(sorted(group["segments"])),
        }
        for key, group in groups.items()
    }


def _projection_from_receipt(
    receipt: dict[str, Any],
) -> dict[tuple[int, int, int], dict[str, Any]]:
    raw_objects = receipt.get("mapped_executable_objects")
    if not isinstance(raw_objects, list) or not raw_objects:
        raise ValueError("runtime receipt has no mapped executable objects")

    groups: dict[tuple[int, int, int], dict[str, Any]] = {}
    for index, record in enumerate(raw_objects):
        if not isinstance(record, dict):
            raise ValueError(f"runtime object {index} is not an object")
        try:
            key = (
                int(record["device_major"]),
                int(record["device_minor"]),
                int(record["inode"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"runtime object {index} has invalid inode identity") from exc
        if key in groups:
            raise ValueError("runtime receipt duplicates a mapped inode object")
        paths = record.get("paths")
        segments = record.get("segments")
        if (
            not isinstance(paths, list)
            or not paths
            or not all(isinstance(path, str) and path.startswith("/") for path in paths)
        ):
            raise ValueError(f"runtime object {index} has invalid paths")
        if not isinstance(segments, list) or not segments:
            raise ValueError(f"runtime object {index} has no executable segments")
        parsed_segments: list[tuple[int, int, str, int]] = []
        for raw in segments:
            if not isinstance(raw, dict):
                raise ValueError(f"runtime object {index} has malformed segment")
            try:
                start = int(raw["start"])
                end = int(raw["end"])
                perms = str(raw["perms"])
                offset = int(raw["offset"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"runtime object {index} has malformed segment") from exc
            if start < 0 or end <= start or offset < 0 or "x" not in perms:
                raise ValueError(f"runtime object {index} has invalid executable segment")
            parsed_segments.append((start, end, perms, offset))
        groups[key] = {
            "paths": tuple(sorted(set(paths))),
            "segments": tuple(sorted(parsed_segments)),
            "record": record,
            "index": index,
        }
    return groups


def _stat_identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _hash_open_fd(fd: int, *, label: str) -> dict[str, Any]:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular file")
    digest = hashlib.sha256()
    total = 0
    offset = 0
    while offset < before.st_size:
        block = os.pread(fd, min(1024 * 1024, before.st_size - offset), offset)
        if not block:
            raise ValueError(f"short read while hashing {label}")
        digest.update(block)
        total += len(block)
        offset += len(block)
    after = os.fstat(fd)
    if _stat_identity(before) != _stat_identity(after):
        raise ValueError(f"{label} changed while being hashed")
    return {
        "bytes": total,
        "sha256": digest.hexdigest(),
        "device_major": os.major(before.st_dev),
        "device_minor": os.minor(before.st_dev),
        "inode": before.st_ino,
        "mtime_ns": before.st_mtime_ns,
        "ctime_ns": before.st_ctime_ns,
    }


def _pread_exact(fd: int, size: int, offset: int, *, label: str) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    cursor = offset
    while remaining:
        try:
            block = os.pread(fd, remaining, cursor)
        except OSError as exc:
            raise ValueError(f"cannot read {label} at offset {cursor}: {exc}") from exc
        if not block:
            raise ValueError(f"short read from {label} at offset {cursor}")
        chunks.append(block)
        remaining -= len(block)
        cursor += len(block)
    return b"".join(chunks)


def _open_bound_backing(
    key: tuple[int, int, int],
    group: dict[str, Any],
) -> tuple[int, dict[str, Any], str]:
    record = group["record"]
    expected_bytes = record.get("bytes")
    expected_sha = record.get("sha256")
    if not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise ValueError("runtime object byte count is invalid")
    if not isinstance(expected_sha, str):
        raise ValueError("runtime object sha256 is missing")

    last_error: Exception | None = None
    for path_text in group["paths"]:
        try:
            fd = os.open(path_text, os.O_RDONLY | os.O_CLOEXEC)
        except OSError as exc:
            last_error = exc
            continue
        try:
            identity = _hash_open_fd(fd, label=f"runtime backing {path_text}")
        except Exception:
            os.close(fd)
            raise
        observed_key = (
            identity["device_major"],
            identity["device_minor"],
            identity["inode"],
        )
        if observed_key != key:
            os.close(fd)
            continue
        if (identity["bytes"], identity["sha256"]) != (expected_bytes, expected_sha):
            os.close(fd)
            raise ValueError(
                "runtime backing file content differs from attested runtime receipt"
            )
        return fd, identity, path_text

    detail = f": {last_error}" if last_error is not None else ""
    raise ValueError(f"no runtime receipt path still names mapped inode{detail}")


def attest_runtime_codepages(
    *,
    runtime_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Create a receipt comparing live executable bytes with file backing."""
    if os.name != "posix":
        raise ValueError("runtime code-page attestation requires POSIX/Linux procfs")
    _verify_runtime_receipt(runtime_receipt)

    process = runtime_receipt.get("process")
    if not isinstance(process, dict):
        raise ValueError("runtime receipt has no process record")
    pid = process.get("pid")
    expected_starttime = process.get("starttime_ticks")
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("runtime receipt pid is invalid")
    if not isinstance(expected_starttime, int) or expected_starttime < 0:
        raise ValueError("runtime receipt starttime is invalid")

    page_size = os.sysconf("SC_PAGE_SIZE")
    if not isinstance(page_size, int) or page_size <= 0:
        raise ValueError("cannot determine a positive system page size")

    receipt_projection = _projection_from_receipt(runtime_receipt)
    proc_dir = proc_root / str(pid)

    start_before = _read_process_starttime(proc_dir)
    if start_before != expected_starttime:
        raise ValueError("process identity differs from runtime receipt")

    maps_before = _parse_maps(_read_proc_bytes(proc_dir, "maps", label="process maps"))
    projection_before = _projection_from_maps(maps_before)
    comparable_receipt = {
        key: {"paths": value["paths"], "segments": value["segments"]}
        for key, value in receipt_projection.items()
    }
    if projection_before != comparable_receipt:
        raise ValueError("executable mapping projection differs from runtime receipt")

    try:
        mem_fd = os.open(proc_dir / "mem", os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        raise ValueError(f"cannot open process memory {proc_dir / 'mem'}: {exc}") from exc

    object_results: list[dict[str, Any]] = []
    try:
        for key, group in sorted(receipt_projection.items()):
            backing_fd, backing_identity, backing_path = _open_bound_backing(key, group)
            try:
                segment_results: list[dict[str, Any]] = []
                for start, end, perms, file_offset in group["segments"]:
                    length = end - start
                    file_size = backing_identity["bytes"]
                    if file_offset >= file_size:
                        raise ValueError(
                            "executable mapping begins at or beyond backing EOF"
                        )
                    rounded_eof = ((file_size + page_size - 1) // page_size) * page_size
                    if file_offset + length > rounded_eof:
                        raise ValueError(
                            "executable mapping spans a whole page beyond backing EOF"
                        )
                    file_bytes = min(length, file_size - file_offset)
                    memory_bytes = _pread_exact(
                        mem_fd,
                        length,
                        start,
                        label=f"process memory {start:x}-{end:x}",
                    )
                    backing_bytes = _pread_exact(
                        backing_fd,
                        file_bytes,
                        file_offset,
                        label=f"runtime backing {backing_path}",
                    )
                    zero_fill_bytes = length - file_bytes
                    expected_memory = backing_bytes + (b"\0" * zero_fill_bytes)
                    if memory_bytes != expected_memory:
                        first_difference = next(
                            index
                            for index, pair in enumerate(
                                zip(memory_bytes, expected_memory, strict=True)
                            )
                            if pair[0] != pair[1]
                        )
                        raise ValueError(
                            "live executable bytes differ from file backing at "
                            f"virtual address 0x{start + first_difference:x}"
                        )
                    segment_results.append(
                        {
                            "start": start,
                            "end": end,
                            "perms": perms,
                            "file_offset": file_offset,
                            "bytes": length,
                            "file_bytes": file_bytes,
                            "zero_fill_bytes": zero_fill_bytes,
                            "memory_sha256": hashlib.sha256(memory_bytes).hexdigest(),
                            "expected_backing_sha256": hashlib.sha256(
                                expected_memory
                            ).hexdigest(),
                        }
                    )
                backing_after = _hash_open_fd(
                    backing_fd, label=f"runtime backing recheck {backing_path}"
                )
                if backing_after != backing_identity:
                    raise ValueError(
                        "runtime backing file changed during code-page attestation"
                    )
            finally:
                os.close(backing_fd)

            object_results.append(
                {
                    "runtime_object_index": group["index"],
                    "device_major": key[0],
                    "device_minor": key[1],
                    "inode": key[2],
                    "backing_path": backing_path,
                    "backing_bytes": backing_identity["bytes"],
                    "backing_sha256": backing_identity["sha256"],
                    "executable_segments": segment_results,
                }
            )

        maps_after = _parse_maps(
            _read_proc_bytes(proc_dir, "maps", label="process maps recheck")
        )
        if _projection_from_maps(maps_after) != projection_before:
            raise ValueError("executable mapping projection changed during attestation")
        start_after = _read_process_starttime(proc_dir)
        if start_after != start_before:
            raise ValueError("process identity changed during attestation")
    finally:
        os.close(mem_fd)

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_runtime_receipt_sha256": runtime_receipt["receipt_sha256"],
        "process": {"pid": pid, "starttime_ticks": start_before},
        "objects": sorted(object_results, key=lambda item: item["runtime_object_index"]),
        "executable_mapping_projection_stable": True,
        "scientific_scope": "LIVE_EXECUTABLE_MEMORY_EQUALS_ATTESTED_FILE_BACKING_ONLY",
        "limitations": [
            "LINUX_PROCFS_AND_PTRACE_MEM_ACCESS_REQUIRED",
            "ONLY_FILE_BACKED_EXECUTABLE_MAPPINGS_ARE_COMPARED",
            "NONEXECUTABLE_RELOCATED_DATA_AND_GOT_PLT_STATE_NOT_BOUND",
            "LATE_DLOPEN_UNLOAD_OR_RUNTIME_PATCH_AFTER_ATTESTATION_NOT_BOUND",
            "MISMATCH_MECHANISM_NOT_IDENTIFIED_BY_THIS_TEST",
            "LINKER_COMMAND_STATIC_ARCHIVES_AND_RUNTIME_INPUTS_NOT_BOUND",
            "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_OBSERVABLE_VALIDATED",
        ],
    }
    return _with_receipt_digest(body)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {label} JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-receipt-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = attest_runtime_codepages(
            runtime_receipt=_load_json_object(
                args.runtime_receipt_json, label="runtime dependency receipt"
            )
        )
    except (KeyError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
