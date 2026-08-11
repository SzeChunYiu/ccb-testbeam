#!/usr/bin/env python3
"""Attest the executable code objects mapped by a live Linux process.

This is a bounded runtime-provenance primitive for the CCB Geant4 chain.  It
binds a live process to a previously validated
``ccb_geant4_build_binding_final_v1`` executable, snapshots Linux
``/proc/<pid>/maps``, and records exact SHA-256 identities for every regular
file-backed object that has at least one executable mapping.  Dynamic-loader
control variables are captured from the process's initial environment.

The receipt establishes *file-backing identity at one stable observation
boundary*.  It does not hash in-memory executable pages, prove linker command
lines, exclude later ``dlopen`` activity, bind wrapper child processes, or
validate any Geant4 physics observable.
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"
FINAL_RECEIPT_SCHEMA = "ccb_geant4_build_binding_final_v1"
DEFAULT_LOADER_ENV_KEYS = (
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "LD_AUDIT",
    "LD_BIND_NOW",
    "LD_DEBUG",
    "LD_DEBUG_OUTPUT",
    "LD_HWCAP_MASK",
    "GLIBC_TUNABLES",
)
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

    def projection(self) -> tuple[Any, ...]:
        return (
            self.start,
            self.end,
            self.perms,
            self.offset,
            self.dev_major,
            self.dev_minor,
            self.inode,
            self.pathname,
        )


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


def _verify_receipt_digest(receipt: dict[str, Any], *, label: str) -> None:
    observed = receipt.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError(f"{label} is missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    if observed != _digest_body(body):
        raise ValueError(f"{label} digest mismatch")


def _stat_identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _hash_open_fd(fd: int, *, label: str) -> dict[str, Any]:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular file")
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while True:
        block = os.read(fd, 1024 * 1024)
        if not block:
            break
        digest.update(block)
        total += len(block)
    after = os.fstat(fd)
    if _stat_identity(before) != _stat_identity(after):
        raise ValueError(f"{label} changed while being hashed")
    if total != before.st_size:
        raise ValueError(f"short/long read while hashing {label}")
    return {
        "bytes": total,
        "sha256": digest.hexdigest(),
        "device_major": os.major(before.st_dev),
        "device_minor": os.minor(before.st_dev),
        "inode": before.st_ino,
        "mode": stat.S_IMODE(before.st_mode),
        "mtime_ns": before.st_mtime_ns,
        "ctime_ns": before.st_ctime_ns,
    }


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
    # tail[0] is field 3 (state); starttime is field 22 => tail index 19.
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


def _executable_projection(entries: list[MapEntry]) -> tuple[tuple[Any, ...], ...]:
    return tuple(sorted(entry.projection() for entry in entries if entry.executable))


def _normalise_requirements(requirements: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if not requirements:
        raise ValueError("at least one required runtime object pattern is required")
    labels: set[str] = set()
    result: list[tuple[str, str]] = []
    for raw_label, raw_pattern in requirements:
        label = raw_label.strip()
        pattern = raw_pattern.strip()
        if not label or not pattern:
            raise ValueError("runtime object label and pattern must be non-empty")
        if label in labels:
            raise ValueError(f"duplicate runtime object requirement label: {label}")
        if pattern in {"*", "**"}:
            raise ValueError("runtime object requirement pattern must be discriminating")
        labels.add(label)
        result.append((label, pattern))
    return sorted(result)


def _parse_environment(payload: bytes, keys: list[str]) -> dict[str, Any]:
    wanted = set(keys)
    seen: dict[str, bytes] = {}
    for item in payload.split(b"\0"):
        if not item:
            continue
        name_raw, sep, value = item.partition(b"=")
        if not sep:
            continue
        try:
            name = name_raw.decode("ascii")
        except UnicodeDecodeError:
            continue
        if name not in wanted:
            continue
        if name in seen:
            raise ValueError(f"duplicate tracked environment key: {name}")
        seen[name] = value

    result: dict[str, Any] = {}
    for key in sorted(wanted):
        value = seen.get(key)
        if value is None:
            result[key] = {"present": False}
            continue
        record: dict[str, Any] = {
            "present": True,
            "bytes": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
            "base64": base64.b64encode(value).decode("ascii"),
        }
        try:
            record["utf8"] = value.decode("utf-8")
        except UnicodeDecodeError:
            record["utf8"] = None
        result[key] = record
    return result


def _open_process_executable(proc_dir: Path) -> tuple[int, str]:
    exe_link = proc_dir / "exe"
    try:
        link_text = os.readlink(exe_link)
        fd = os.open(exe_link, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        raise ValueError(f"cannot open process executable {exe_link}: {exc}") from exc
    return fd, link_text


def _collect_executable_objects(
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
        if entry.pathname is None:
            raise ValueError("file-backed executable mapping has no pathname")
        if entry.pathname.endswith(" (deleted)"):
            raise ValueError(
                "file-backed executable mapping is deleted and cannot be path-attested: "
                f"{entry.pathname}"
            )
        if "\\012" in entry.pathname:
            raise ValueError(
                "file-backed executable pathname contains ambiguous procfs newline escape"
            )
        if not entry.pathname.startswith("/"):
            raise ValueError(
                "file-backed executable mapping does not expose an absolute pathname: "
                f"{entry.pathname}"
            )
        key = (entry.dev_major, entry.dev_minor, entry.inode)
        group = groups.setdefault(
            key,
            {
                "device_major": entry.dev_major,
                "device_minor": entry.dev_minor,
                "inode": entry.inode,
                "paths": set(),
                "segments": [],
            },
        )
        group["paths"].add(entry.pathname)
        group["segments"].append(
            {
                "start": entry.start,
                "end": entry.end,
                "perms": entry.perms,
                "offset": entry.offset,
            }
        )
    if not groups:
        raise ValueError("process has no attestable file-backed executable mappings")
    return groups


def _hash_mapped_group(group: dict[str, Any]) -> dict[str, Any]:
    paths = sorted(group["paths"])
    expected_dev = (group["device_major"], group["device_minor"])
    expected_inode = group["inode"]
    reference: dict[str, Any] | None = None

    for path_text in paths:
        path = Path(path_text)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
        except OSError as exc:
            raise ValueError(f"cannot open mapped executable object {path}: {exc}") from exc
        try:
            record = _hash_open_fd(fd, label=f"mapped executable object {path}")
        finally:
            os.close(fd)
        observed_dev = (record["device_major"], record["device_minor"])
        if observed_dev != expected_dev or record["inode"] != expected_inode:
            raise ValueError(
                "mapped executable object path no longer names the mapped inode: "
                f"{path} expected dev={expected_dev} inode={expected_inode}, "
                f"observed dev={observed_dev} inode={record['inode']}"
            )
        try:
            final = path.stat()
        except OSError as exc:
            raise ValueError(f"cannot re-stat mapped executable object {path}: {exc}") from exc
        if (
            os.major(final.st_dev),
            os.minor(final.st_dev),
            final.st_ino,
            final.st_size,
            final.st_mtime_ns,
            final.st_ctime_ns,
        ) != (
            record["device_major"],
            record["device_minor"],
            record["inode"],
            record["bytes"],
            record["mtime_ns"],
            record["ctime_ns"],
        ):
            raise ValueError(f"mapped executable object path changed after hashing: {path}")
        if reference is None:
            reference = record
        elif (record["bytes"], record["sha256"]) != (
            reference["bytes"],
            reference["sha256"],
        ):
            raise ValueError("hardlink-equivalent mapped paths produced different bytes")

    assert reference is not None
    return {
        "device_major": group["device_major"],
        "device_minor": group["device_minor"],
        "inode": group["inode"],
        "paths": paths,
        "bytes": reference["bytes"],
        "sha256": reference["sha256"],
        "segments": sorted(
            group["segments"], key=lambda item: (item["start"], item["end"], item["offset"])
        ),
    }


def attest_runtime_dependencies(
    *,
    final_receipt: dict[str, Any],
    pid: int,
    requirements: list[tuple[str, str]],
    extra_env_keys: list[str] | None = None,
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Create a content-bound receipt for live executable-code dependencies."""
    if os.name != "posix":
        raise ValueError("runtime dependency attestation requires POSIX/Linux procfs")
    if pid <= 0:
        raise ValueError("pid must be positive")
    if final_receipt.get("schema") != FINAL_RECEIPT_SCHEMA:
        raise ValueError("unsupported or missing final build-binding receipt schema")
    if final_receipt.get("status") != "PASS":
        raise ValueError("final build-binding receipt is not PASS")
    _verify_receipt_digest(final_receipt, label="final build-binding receipt")

    parent_executable = final_receipt.get("executable")
    if not isinstance(parent_executable, dict):
        raise ValueError("final build-binding receipt has no executable record")
    parent_path = parent_executable.get("path")
    parent_sha = parent_executable.get("sha256")
    parent_bytes = parent_executable.get("bytes")
    if not isinstance(parent_path, str) or not isinstance(parent_sha, str):
        raise ValueError("final executable record is incomplete")
    if not isinstance(parent_bytes, int) or parent_bytes < 0:
        raise ValueError("final executable byte count is invalid")

    normalised_requirements = _normalise_requirements(requirements)
    env_keys = list(DEFAULT_LOADER_ENV_KEYS)
    for key in extra_env_keys or []:
        key = key.strip()
        if not key:
            raise ValueError("tracked environment key must be non-empty")
        if "=" in key or "\0" in key:
            raise ValueError(f"invalid tracked environment key: {key!r}")
        if key not in env_keys:
            env_keys.append(key)

    proc_dir = proc_root / str(pid)
    start_before = _read_process_starttime(proc_dir)
    exe_fd, exe_link_before = _open_process_executable(proc_dir)
    try:
        exe_before = _hash_open_fd(exe_fd, label="live process executable")
        if (exe_before["bytes"], exe_before["sha256"]) != (parent_bytes, parent_sha):
            raise ValueError("live process executable bytes differ from final build receipt")

        expected_path = str(Path(parent_path).resolve())
        live_path = exe_link_before.removesuffix(" (deleted)")
        if exe_link_before.endswith(" (deleted)"):
            raise ValueError("live process executable has been deleted after execution")
        if str(Path(live_path).resolve()) != expected_path:
            raise ValueError(
                "live process executable path differs from final build receipt; "
                "relocation can change loader semantics"
            )

        maps_before_payload = _read_proc_bytes(proc_dir, "maps", label="process maps")
        entries_before = _parse_maps(maps_before_payload)
        exec_projection_before = _executable_projection(entries_before)
        groups = _collect_executable_objects(entries_before)
        objects = [_hash_mapped_group(group) for _, group in sorted(groups.items())]

        environment = _parse_environment(
            _read_proc_bytes(proc_dir, "environ", label="process environment"), env_keys
        )

        matches: dict[str, list[int]] = {}
        for label, pattern in normalised_requirements:
            matched: list[int] = []
            for index, record in enumerate(objects):
                if any(
                    fnmatch.fnmatchcase(Path(path).name, pattern)
                    or fnmatch.fnmatchcase(path, pattern)
                    for path in record["paths"]
                ):
                    matched.append(index)
            if not matched:
                raise ValueError(
                    f"required runtime object pattern matched nothing: {label}={pattern}"
                )
            matches[label] = matched

        maps_after_payload = _read_proc_bytes(proc_dir, "maps", label="process maps recheck")
        entries_after = _parse_maps(maps_after_payload)
        if _executable_projection(entries_after) != exec_projection_before:
            raise ValueError("executable mapping set changed during runtime attestation")

        exe_after = _hash_open_fd(exe_fd, label="live process executable recheck")
        if exe_after != exe_before:
            raise ValueError("live process executable changed during runtime attestation")
        start_after = _read_process_starttime(proc_dir)
        if start_after != start_before:
            raise ValueError("process identity changed during runtime attestation")
        try:
            exe_link_after = os.readlink(proc_dir / "exe")
        except OSError as exc:
            raise ValueError(f"cannot re-read process executable link: {exc}") from exc
        if exe_link_after != exe_link_before:
            raise ValueError("process executable link changed during runtime attestation")
    finally:
        os.close(exe_fd)

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_final_build_receipt_sha256": final_receipt["receipt_sha256"],
        "process": {
            "pid": pid,
            "starttime_ticks": start_before,
            "exe_link": exe_link_before,
            "executable": exe_before,
        },
        "loader_environment": environment,
        "mapped_executable_objects": objects,
        "required_object_matches": {
            label: {
                "pattern": dict(normalised_requirements)[label],
                "object_indexes": indexes,
            }
            for label, indexes in matches.items()
        },
        "maps_sha256": hashlib.sha256(maps_before_payload).hexdigest(),
        "executable_mapping_projection_stable": True,
        "scientific_scope": "LIVE_FILE_BACKED_EXECUTABLE_MAPPING_IDENTITY_ONLY",
        "limitations": [
            "LINUX_PROCFS_REQUIRED",
            "MAPPED_FILE_BACKING_BYTES_NOT_IN_MEMORY_PAGE_CONTENT",
            "LATE_DLOPEN_OR_UNLOAD_AFTER_ATTESTATION_NOT_BOUND",
            "LINKER_COMMAND_AND_DT_NEEDED_RPATH_RUNPATH_NOT_YET_ATTESTED",
            "WRAPPER_AND_DESCENDANT_PROCESS_IDENTITIES_NOT_BOUND",
            "INITIAL_LOADER_ENVIRONMENT_ONLY_NOT_POST_START_ENV_MUTATION",
            "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_OBSERVABLE_VALIDATED",
        ],
    }
    return _with_receipt_digest(body)


def _parse_requirement(value: str) -> tuple[str, str]:
    label, separator, pattern = value.partition("=")
    if not separator or not label or not pattern:
        raise argparse.ArgumentTypeError("requirement must have form LABEL=GLOB")
    return label, pattern


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
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--require-object", type=_parse_requirement, action="append", required=True)
    parser.add_argument("--capture-env", action="append", default=[])
    args = parser.parse_args()
    try:
        result = attest_runtime_dependencies(
            final_receipt=_load_json_object(
                args.final_receipt_json, label="final build-binding receipt"
            ),
            pid=args.pid,
            requirements=args.require_object,
            extra_env_keys=args.capture_env,
        )
    except (KeyError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
