#!/usr/bin/env python3
"""Attest a stable Linux /proc/PID/cwd current-directory observation.

This bounded provenance primitive composes the live runtime-dependency receipt
with its procfs argument-region child and observes the same process's current
working directory via ``/proc/<pid>/cwd``.  It intentionally does *not* call
that observation the process's initial/exec-time cwd: ``execve`` preserves cwd,
but the target can subsequently change it with ``chdir``/``fchdir``.

Two path-link observations and two opened-directory object identities must
agree while PID/starttime/executable identity remains stable.  This excludes
simple transitions during the attestation window but not an ABA cwd change
between equal observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_loader_cwd_attestation_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"
ARGV_RECEIPT_SCHEMA = "ccb_geant4_loader_argv_attestation_v1"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest_body(body: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(body)).hexdigest()


def _with_digest(body: dict[str, Any]) -> dict[str, Any]:
    result = dict(body)
    result["receipt_sha256"] = _digest_body(body)
    return result


def _verify_receipt(receipt: dict[str, Any], *, schema: str, label: str) -> None:
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


def _read_link(proc_dir: Path, name: str, *, label: str) -> str:
    try:
        return os.readlink(proc_dir / name)
    except OSError as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc


def _process_identity(receipt: dict[str, Any], *, label: str) -> tuple[int, int, str]:
    process = receipt.get("process")
    if not isinstance(process, dict):
        raise ValueError(f"{label} has no process record")
    pid = process.get("pid")
    starttime = process.get("starttime_ticks")
    exe_link = process.get("exe_link")
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError(f"{label} pid is invalid")
    if not isinstance(starttime, int) or starttime < 0:
        raise ValueError(f"{label} starttime is invalid")
    if not isinstance(exe_link, str) or not exe_link:
        raise ValueError(f"{label} executable link is invalid")
    return pid, starttime, exe_link


def _opened_cwd_identity(proc_dir: Path) -> dict[str, int]:
    flags = getattr(os, "O_PATH", os.O_RDONLY)
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(proc_dir / "cwd", flags)
    except OSError as exc:
        raise ValueError(f"cannot open process cwd directory object: {exc}") from exc
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("process cwd object is not a directory")
    return {
        "st_dev": int(info.st_dev),
        "st_ino": int(info.st_ino),
        "st_mode": int(info.st_mode),
    }


def attest_loader_cwd(
    *,
    runtime_receipt: dict[str, Any],
    argv_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Bind a stable current-working-directory observation for one process."""
    _verify_receipt(
        runtime_receipt,
        schema=RUNTIME_RECEIPT_SCHEMA,
        label="runtime dependency receipt",
    )
    _verify_receipt(
        argv_receipt,
        schema=ARGV_RECEIPT_SCHEMA,
        label="loader argv receipt",
    )
    if (
        argv_receipt.get("parent_runtime_dependency_receipt_sha256")
        != runtime_receipt["receipt_sha256"]
    ):
        raise ValueError("argv receipt belongs to another runtime receipt")

    pid, expected_starttime, expected_exe = _process_identity(
        runtime_receipt, label="runtime receipt"
    )
    argv_pid, argv_starttime, argv_exe = _process_identity(
        argv_receipt, label="argv receipt"
    )
    if (argv_pid, argv_starttime, argv_exe) != (
        pid,
        expected_starttime,
        expected_exe,
    ):
        raise ValueError("runtime and argv receipts identify different processes")

    proc_dir = proc_root / str(pid)
    start_before = _read_process_starttime(proc_dir)
    if start_before != expected_starttime:
        raise ValueError("process identity differs from attested runtime process")
    exe_before = _read_link(proc_dir, "exe", label="process executable link")
    if exe_before != expected_exe:
        raise ValueError("process executable link differs from attested runtime process")

    cwd_link_before = _read_link(proc_dir, "cwd", label="process cwd link")
    cwd_object_before = _opened_cwd_identity(proc_dir)
    cwd_object_after = _opened_cwd_identity(proc_dir)
    cwd_link_after = _read_link(proc_dir, "cwd", label="process cwd link recheck")
    if cwd_link_after != cwd_link_before:
        raise ValueError("process cwd link changed during attestation")
    if cwd_object_after != cwd_object_before:
        raise ValueError("process cwd directory object changed during attestation")

    start_after = _read_process_starttime(proc_dir)
    if start_after != start_before:
        raise ValueError("process identity changed during cwd attestation")
    exe_after = _read_link(proc_dir, "exe", label="process executable link recheck")
    if exe_after != exe_before:
        raise ValueError("process executable link changed during cwd attestation")

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_runtime_dependency_receipt_sha256": runtime_receipt["receipt_sha256"],
        "parent_loader_argv_receipt_sha256": argv_receipt["receipt_sha256"],
        "process": {
            "pid": pid,
            "starttime_ticks": start_before,
            "exe_link": exe_before,
        },
        "cwd_observation": {
            "source": "/proc/<pid>/cwd",
            "link_text": cwd_link_before,
            "opened_directory_identity": cwd_object_before,
            "stable_across_two_link_and_object_observations": True,
        },
        "scientific_scope": "STABLE_CURRENT_WORKING_DIRECTORY_OBJECT_OBSERVATION_ONLY",
        "interpretation": {
            "relative_path_starting_point_at_observation": "CURRENT_WORKING_DIRECTORY",
            "historical_execve_cwd": "NOT_PROVEN_TARGET_CAN_CHDIR_OR_FCHDIR_AFTER_EXEC",
            "lexical_path_spelling": "PROCFS_LINK_TEXT_OBSERVATION_NOT_LAUNCH_SHELL_PWD",
            "directory_object_identity": "LOCAL_KERNEL_ST_DEV_ST_INO_OBSERVATION_NOT_CONTENT_ID",
        },
        "limitations": [
            "CHDIR_OR_FCHDIR_CAN_CHANGE_CWD_AFTER_EXECVE",
            "ABA_CWD_TRANSITION_BETWEEN_EQUAL_OBSERVATIONS_NOT_EXCLUDED",
            "INITIAL_EXECVE_CWD_NOT_ATTESTED",
            "PROCESS_ROOT_AND_MOUNT_NAMESPACE_NOT_BOUND_BY_THIS_RECEIPT",
            "RELATIVE_ARGUMENT_INPUT_BYTES_NOT_BOUND_BY_THIS_RECEIPT",
            "SYMLINK_AND_ABSOLUTE_TARGET_RESOLUTION_NOT_BOUND",
            "OUTPUT_PATH_CREATION_TIME_NOT_BOUND",
            "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_OBSERVABLE_VALIDATED",
        ],
    }
    return _with_digest(body)


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
    parser.add_argument("--argv-receipt-json", type=Path, required=True)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    args = parser.parse_args()
    try:
        result = attest_loader_cwd(
            runtime_receipt=_load_json_object(
                args.runtime_receipt_json, label="runtime dependency receipt"
            ),
            argv_receipt=_load_json_object(
                args.argv_receipt_json, label="loader argv receipt"
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
