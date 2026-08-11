#!/usr/bin/env python3
"""Bind tool version probes to the exact opened executable bytes.

This is a Linux/POSIX provenance refinement for
``ccb_geant4_cmake_toolchain_attestation_v1``. The parent attestation records
CMake-selected tool paths and target hashes, but its version probe may traverse
an alias path after the hash observation. This module opens the already
resolved target, hashes that open file description, executes the same open file
through ``/proc/self/fd/<fd>``, then re-hashes the same descriptor and rechecks
the original path/target projection.

The receipt proves a bounded software invariant: the executable entrypoint
used for the probe is the same open regular file whose bytes were hashed. It
does not bind dynamic-loader inputs, wrapper subprocesses, compiler invocations,
or any Geant4 physics result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_tool_probe_binding_v1"
PARENT_SCHEMA = "ccb_geant4_cmake_toolchain_attestation_v1"
MAX_PROBE_BYTES = 65536
PROC_FD_ROOT = Path("/proc/self/fd")


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


def _identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _hash_open_fd(fd: int, *, label: str) -> dict[str, Any]:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be an opened regular file")
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        total += len(chunk)
    after = os.fstat(fd)
    if _identity(before) != _identity(after):
        raise ValueError(f"{label} changed while being hashed")
    if total != before.st_size:
        raise ValueError(f"short/long read while hashing {label}")
    return {
        "bytes": total,
        "sha256": digest.hexdigest(),
        "device": before.st_dev,
        "inode": before.st_ino,
        "mode": stat.S_IMODE(before.st_mode),
    }


def _resolved_record(path: Path, *, label: str) -> dict[str, Any]:
    try:
        original = path.lstat()
        resolved = path.resolve(strict=True)
        resolved_lstat = resolved.lstat()
    except OSError as exc:
        raise ValueError(f"cannot resolve {label} {path}: {exc}") from exc
    if not stat.S_ISREG(resolved_lstat.st_mode):
        raise ValueError(f"{label} must resolve to a regular file: {path}")
    with resolved.open("rb") as stream:
        payload = stream.read()
        after = os.fstat(stream.fileno())
    final = resolved.lstat()
    if _identity(resolved_lstat) != _identity(after) or _identity(after) != _identity(final):
        raise ValueError(f"resolved {label} changed while being read: {resolved}")
    result = {
        "path": str(path.absolute()),
        "resolved_path": str(resolved),
        "resolved_bytes": len(payload),
        "resolved_sha256": hashlib.sha256(payload).hexdigest(),
        "path_is_symlink": stat.S_ISLNK(original.st_mode),
    }
    if stat.S_ISLNK(original.st_mode):
        result["symlink_target"] = os.readlink(path)
    return result


def _expected_projection(record: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "path",
        "resolved_path",
        "resolved_bytes",
        "resolved_sha256",
        "path_is_symlink",
    ]
    result = {key: record.get(key) for key in keys}
    if record.get("path_is_symlink"):
        result["symlink_target"] = record.get("symlink_target")
    return result


def _probe_bound_tool(path: Path, *, label: str, expected: dict[str, Any]) -> dict[str, Any]:
    before = _resolved_record(path, label=label)
    if before != _expected_projection(expected):
        raise ValueError(f"{label} path/target identity differs from parent attestation")

    resolved = Path(before["resolved_path"])
    if not PROC_FD_ROOT.is_dir():
        raise ValueError("/proc/self/fd is unavailable; cannot bind probe to opened bytes")

    try:
        fd = os.open(resolved, os.O_RDONLY)
    except OSError as exc:
        raise ValueError(f"cannot open resolved {label} {resolved}: {exc}") from exc

    try:
        fd_before = _hash_open_fd(fd, label=f"opened {label}")
        if (
            fd_before["bytes"] != before["resolved_bytes"]
            or fd_before["sha256"] != before["resolved_sha256"]
        ):
            raise ValueError(f"opened {label} bytes differ from resolved path observation")
        if fd_before["mode"] & 0o111 == 0:
            raise ValueError(f"{label} has no executable permission bits: {resolved}")

        exec_path = PROC_FD_ROOT / str(fd)
        try:
            proc = subprocess.run(
                [str(exec_path), "--version"],
                check=False,
                capture_output=True,
                timeout=30,
                pass_fds=(fd,),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError(f"{label} version probe failed to execute: {exc}") from exc

        if proc.returncode != 0:
            raise ValueError(
                f"{label} version probe returned {proc.returncode}: "
                f"{proc.stderr[:256]!r}"
            )
        if len(proc.stdout) > MAX_PROBE_BYTES or len(proc.stderr) > MAX_PROBE_BYTES:
            raise ValueError(f"{label} version probe exceeded {MAX_PROBE_BYTES} bytes")

        fd_after = _hash_open_fd(fd, label=f"opened {label} after probe")
        if fd_after != fd_before:
            raise ValueError(f"opened {label} changed during version probe")
    finally:
        os.close(fd)

    after = _resolved_record(path, label=label)
    if after != before:
        raise ValueError(f"{label} path or resolved target changed during version probe")

    return {
        **before,
        "opened_device": fd_before["device"],
        "opened_inode": fd_before["inode"],
        "opened_mode": fd_before["mode"],
        "probe_exec_binding": "LINUX_PROC_SELF_FD_OPEN_FILE_V1",
        "probe_argv_template": ["/proc/self/fd/{BOUND_FD}", "--version"],
        "probe_returncode": proc.returncode,
        "probe_stdout": proc.stdout.decode("utf-8", errors="replace"),
        "probe_stderr": proc.stderr.decode("utf-8", errors="replace"),
        "probe_stdout_sha256": hashlib.sha256(proc.stdout).hexdigest(),
        "probe_stderr_sha256": hashlib.sha256(proc.stderr).hexdigest(),
        "path_target_stable_pre_post": True,
        "opened_bytes_stable_pre_post": True,
    }


def bind_tool_probes(parent_attestation: dict[str, Any]) -> dict[str, Any]:
    if parent_attestation.get("schema") != PARENT_SCHEMA:
        raise ValueError("unsupported or missing parent toolchain attestation schema")
    if parent_attestation.get("status") != "PASS":
        raise ValueError("parent toolchain attestation is not PASS")
    _verify_receipt_digest(parent_attestation, label="parent toolchain attestation")

    parent_tools = parent_attestation.get("tools")
    if not isinstance(parent_tools, dict):
        raise ValueError("parent toolchain attestation has no tools object")

    tools: dict[str, Any] = {}
    for key, label in (("cmake", "CMake command"), ("cxx_compiler", "C++ compiler")):
        expected = parent_tools.get(key)
        if not isinstance(expected, dict):
            raise ValueError(f"parent toolchain attestation is missing tool {key}")
        path_value = expected.get("path")
        if not isinstance(path_value, str) or not path_value:
            raise ValueError(f"parent tool {key} is missing path")
        tools[key] = _probe_bound_tool(Path(path_value), label=label, expected=expected)

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_toolchain_attestation_sha256": parent_attestation["receipt_sha256"],
        "tools": tools,
        "scientific_scope": "TOOL_VERSION_PROBE_ENTRYPOINT_BYTES_ONLY",
        "limitations": [
            "LINUX_PROCFS_REQUIRED_FOR_OPEN_FILE_EXECUTION_BINDING",
            "DYNAMIC_LOADER_AND_SHARED_LIBRARY_IDENTITIES_NOT_BOUND",
            "EXECUTABLE_WRAPPER_CHILD_PROCESSES_NOT_BOUND",
            "COMPILER_AND_LINKER_BUILD_INVOCATIONS_NOT_ATTESTED",
            "NO_GEANT4_EVENT_OR_DETECTOR_OBSERVABLE_VALIDATED",
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
    parser.add_argument("--toolchain-attestation-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = bind_tool_probes(
            _load_json_object(
                args.toolchain_attestation_json, label="toolchain attestation"
            )
        )
    except (KeyError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
