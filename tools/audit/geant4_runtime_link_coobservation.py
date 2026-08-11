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
        if not block:
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
            int(record["device_minor"]),
            int(record["inode"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"runtime object {index} has invalid inode identity") from exc
    return key


def _coobserve_object(record: dict[str, Any], *, index: int) -> dict[str, Any]:
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
        raise ValueError(
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


def _stable_absolute_resolution(path_text: str, *, label: str) -> dict[str, Any]:
    if not path_text.startswith("/"):
        raise ValueError(f"{label} is not an absolute path: {path_text}")
    key = _path_key(path_text, label=label)
    return {
        "path": path_text,
        "device_major": key[0],
        "device_minor": key[1],
        "inode": key[2],
    }


def _object_key(record: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(record["device_major"]),
        int(record["device_minor"]),
        int(record["inode"]),
    )


def _match_absolute_path(
    path_text: str,
    *,
    label: str,
    objects: list[dict[str, Any]],
) -> tuple[int, dict[str, Any]]:
    before = _stable_absolute_resolution(path_text, label=label)
    key = _object_key(before)
    matches = [
        index for index, record in enumerate(objects) if _object_key(record) == key
    ]
    after = _stable_absolute_resolution(path_text, label=f"{label} recheck")
    if after != before:
        raise ValueError(f"{label} resolution changed during attestation")
    if len(matches) != 1:
        raise ValueError(
            f"{label} matched {len(matches)} mapped objects; expected exactly one"
        )
    return matches[0], before


def attest_runtime_link_coobservation(
    *,
    final_receipt: dict[str, Any],
    runtime_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Attest same-descriptor ELF metadata and direct-link closure."""
    if os.name != "posix":
        raise ValueError("runtime link co-observation requires POSIX/Linux procfs")

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

    final_executable = final_receipt.get("executable")
    if not isinstance(final_executable, dict):
        raise ValueError("final build-binding receipt has no executable record")
    final_bytes = final_executable.get("bytes")
    final_sha = final_executable.get("sha256")
    if not isinstance(final_bytes, int) or final_bytes < 0 or not isinstance(final_sha, str):
        raise ValueError("final executable content identity is incomplete")

    process = runtime_receipt.get("process")
    if not isinstance(process, dict):
        raise ValueError("runtime receipt has no process record")
    pid = process.get("pid")
    expected_starttime = process.get("starttime_ticks")
    process_executable = process.get("executable")
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("runtime receipt pid is invalid")
    if not isinstance(expected_starttime, int) or expected_starttime < 0:
        raise ValueError("runtime receipt starttime is invalid")
    if not isinstance(process_executable, dict):
        raise ValueError("runtime receipt has no process executable record")
    if (
        process_executable.get("bytes"),
        process_executable.get("sha256"),
    ) != (final_bytes, final_sha):
        raise ValueError("runtime executable identity differs from final build receipt")
    try:
        process_executable_key = (
            int(process_executable["device_major"]),
            int(process_executable["device_minor"]),
            int(process_executable["inode"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("runtime process executable inode identity is invalid") from exc

    receipt_projection = _projection_from_receipt(runtime_receipt)
    comparable_receipt = {
        key: {"paths": value["paths"], "segments": value["segments"]}
        for key, value in receipt_projection.items()
    }

    proc_dir = proc_root / str(pid)
    start_before = _read_process_starttime(proc_dir)
    if start_before != expected_starttime:
        raise ValueError("process identity differs from runtime receipt")
    maps_before_payload = _read_proc_bytes(proc_dir, "maps", label="process maps")
    projection_before = _projection_from_maps(_parse_maps(maps_before_payload))
    if projection_before != comparable_receipt:
        raise ValueError("executable mapping projection differs from runtime receipt")

    raw_objects = runtime_receipt.get("mapped_executable_objects")
    if not isinstance(raw_objects, list) or not raw_objects:
        raise ValueError("runtime receipt has no mapped executable objects")
    objects = [
        _coobserve_object(record, index=index)
        for index, record in enumerate(raw_objects)
        if isinstance(record, dict)
    ]
    if len(objects) != len(raw_objects):
        raise ValueError("runtime mapped object record is not an object")

    executable_matches = [
        index
        for index, record in enumerate(objects)
        if _object_key(record) == process_executable_key
        and (record["bytes"], record["sha256"])
        == (process_executable.get("bytes"), process_executable.get("sha256"))
    ]
    if len(executable_matches) != 1:
        raise ValueError(
            "runtime process executable matched "
            f"{len(executable_matches)} mapped objects; expected exactly one"
        )
    executable_index = executable_matches[0]
    executable_elf = objects[executable_index]["elf"]
    if executable_elf is None:
        raise ValueError("runtime process executable is not a supported ELF object")

    unique_needed = list(dict.fromkeys(executable_elf["dt_needed"]))
    direct_dependency_matches: dict[str, int] = {}
    absolute_dependency_resolutions: dict[str, dict[str, Any]] = {}
    for dependency in unique_needed:
        if "/" in dependency:
            if not dependency.startswith("/"):
                raise ValueError(
                    "relative DT_NEEDED path requires cwd provenance: "
                    f"{dependency}"
                )
            matched_index, resolution = _match_absolute_path(
                dependency,
                label=f"absolute DT_NEEDED {dependency}",
                objects=objects,
            )
            absolute_dependency_resolutions[dependency] = resolution
        else:
            matches = [
                index
                for index, record in enumerate(objects)
                if record["elf"] is not None
                and record["elf"]["dt_soname"] == dependency
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"DT_NEEDED {dependency!r} matched {len(matches)} mapped objects; "
                    "expected exactly one"
                )
            matched_index = matches[0]
        direct_dependency_matches[dependency] = matched_index

    interpreter_object_index: int | None = None
    interpreter_resolution: dict[str, Any] | None = None
    interpreter = executable_elf["interpreter"]
    if interpreter is not None:
        if not interpreter.startswith("/"):
            raise ValueError("PT_INTERP is not an absolute path")
        interpreter_object_index, interpreter_resolution = _match_absolute_path(
            interpreter,
            label="PT_INTERP",
            objects=objects,
        )

    maps_after_payload = _read_proc_bytes(proc_dir, "maps", label="process maps recheck")
    projection_after = _projection_from_maps(_parse_maps(maps_after_payload))
    if projection_after != projection_before:
        raise ValueError("executable mapping projection changed during co-observation")
    start_after = _read_process_starttime(proc_dir)
    if start_after != start_before:
        raise ValueError("process identity changed during co-observation")

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_final_build_receipt_sha256": final_receipt["receipt_sha256"],
        "parent_runtime_dependency_receipt_sha256": runtime_receipt["receipt_sha256"],
        "process": {
            "pid": pid,
            "starttime_ticks": start_before,
            "executable_object_index": executable_index,
            "executable_elf": executable_elf,
        },
        "objects": objects,
        "direct_dependency_matches": direct_dependency_matches,
        "absolute_dependency_resolutions": absolute_dependency_resolutions,
        "interpreter_object_index": interpreter_object_index,
        "interpreter_resolution": interpreter_resolution,
        "maps_sha256": hashlib.sha256(maps_before_payload).hexdigest(),
        "executable_mapping_projection_stable": True,
        "scientific_scope": "LIVE_MAPPED_OBJECT_SAME_FD_ELF_METADATA_ONLY",
        "limitations": [
            "MAPPED_OBJECTS_ARE_NOT_OBSERVED_SIMULTANEOUSLY",
            "HISTORICAL_LOADER_SEARCH_DECISION_NOT_BOUND",
            "LINK_COMMAND_STATIC_ARCHIVES_AND_RESPONSE_FILES_NOT_BOUND",
            "LATE_DLOPEN_OR_UNLOAD_AFTER_SNAPSHOT_NOT_BOUND",
            "NONEXECUTABLE_RELOCATION_GOT_PLT_STATE_NOT_BOUND",
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
    parser.add_argument("--final-receipt-json", type=Path, required=True)
    parser.add_argument("--runtime-receipt-json", type=Path, required=True)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    args = parser.parse_args()

    try:
        result = attest_runtime_link_coobservation(
            final_receipt=_load_json_object(
                args.final_receipt_json, label="final build-binding receipt"
            ),
            runtime_receipt=_load_json_object(
                args.runtime_receipt_json, label="runtime dependency receipt"
            ),
            proc_root=args.proc_root,
        )
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
