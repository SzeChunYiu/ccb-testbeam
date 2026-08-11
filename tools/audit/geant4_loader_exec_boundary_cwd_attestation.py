#!/usr/bin/env python3
"""Record and attest the working directory at the HIBEAM exec boundary.

This bounded provenance primitive addresses the gap left by the later procfs
current-cwd observation: ``/proc/<pid>/cwd`` reflects the *current* directory,
which the target may change after exec with ``chdir``/``fchdir``.  Here the
working-directory object is recorded by the launcher process itself immediately
before a direct ``execve`` of the target image.

Because ``execve`` preserves both the process identity (PID, start-time) and the
current working directory, and because the launcher performs no ``chdir``
between recording the opened ``.`` object and the exec transition, the recorded
object is the cwd at the actual exec boundary for the exact process that later
carries the runtime dependency receipt.  This is the positive direct-exec case;
wrapper/pre-exec and target/post-exec ``chdir`` are discriminated by the hostile
fixtures in the test module.

The receipt is a *record*, not a kernel log: it binds one opened directory
object identity and the process that opens it immediately before exec.  It does
not by itself prove filesystem root/mount namespace equivalence, symlink
resolution, or that any relative input bytes were actually consumed; those
remain explicit downstream gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_loader_exec_boundary_cwd_attestation_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"
EXEC_BOUNDARY_CWD_SCHEMA = "ccb_geant4_loader_exec_boundary_cwd_record_v1"


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


def _read_exe_link(proc_dir: Path) -> str:
    try:
        return os.readlink(proc_dir / "exe")
    except OSError as exc:
        raise ValueError(f"cannot read process executable link: {exc}") from exc


def _open_directory_identity(path: Path) -> dict[str, int]:
    flags = getattr(os, "O_PATH", os.O_RDONLY)
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except NotADirectoryError as exc:
        raise ValueError(f"path {path} is not a directory object") from exc
    except OSError as exc:
        raise ValueError(f"cannot open directory object {path}: {exc}") from exc
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"path {path} is not a directory object")
    return {
        "st_dev": int(info.st_dev),
        "st_ino": int(info.st_ino),
        "st_mode": int(info.st_mode),
    }


def record_exec_boundary_cwd(
    *,
    proc_root: Path = Path("/proc"),
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Record the opened cwd object for the process about to exec.

    Call this *immediately before* ``os.execv`` and perform no ``chdir``/``fchdir``
    in between, so the recorded object is the exec-boundary cwd of the same,
    unchanged process.  The process identity (pid, starttime, exe link) is
    preserved by ``execve`` and therefore binds this record to the exec'd image's
    runtime identity.
    """
    pid = os.getpid()
    proc_dir = proc_root / str(pid)
    starttime = _read_process_starttime(proc_dir)
    exe_link = _read_exe_link(proc_dir)
    if exe_link.endswith(" (deleted)"):
        raise ValueError("launcher executable is deleted")

    target = cwd if cwd is not None else Path(".")
    cwd_object = _open_directory_identity(target)
    try:
        spelling = os.getcwd()
    except OSError as exc:
        spelling = None

    body = {
        "schema": EXEC_BOUNDARY_CWD_SCHEMA,
        "status": "RECORDED",
        "boundary": "IMMEDIATELY_BEFORE_DIRECT_EXECVE_NO_INTERVENING_CHDIR",
        "process": {
            "pid": pid,
            "starttime_ticks": starttime,
            "exe_link": exe_link,
        },
        "cwd_object": cwd_object,
        "cwd_spelling": spelling,
        "scientific_scope": "EXEC_BOUNDARY_CWD_OBJECT_RECORD_ONLY",
        "interpretation": {
            "observation": "OPENED_DIRECTORY_OBJECT_BEFORE_EXECVE",
            "historical_execve_cwd": "PROVEN_SAME_PROCESS_DIRECT_EXEC_PRESERVES_CWD",
            "later_procfs_cwd": "NOT_RELIED_UPON_RECORD_BINDS_EXEC_BOUNDARY",
            "parent_shell_cwd": "NOT_AUTHORITATIVE_LAUNCHER_RECORD_IS_THE_BOUNDARY",
            "path_spelling": "AUXILIARY_OBJECT_IDENTITY_IS_AUTHORITATIVE",
        },
        "limitations": [
            "RENAME_OR_UNLINK_AFTER_EXEC_CHANGES_SPELLING_NOT_OBJECT_IDENTITY",
            "FILESYSTEM_ROOT_AND_MOUNT_NAMESPACE_NOT_BOUND_BY_THIS_RECORD",
            "SYMLINK_RESOLUTION_OF_RELATIVE_ARGUMENT_BYTES_NOT_BOUND",
            "EXACT_OPENED_INPUT_BYTES_NOT_CONSUMPTION_ATTESTED",
            "OUTPUT_PATH_CREATION_TIME_NOT_BOUND",
            "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_OBSERVABLE_VALIDATED",
        ],
    }
    return _with_digest(body)


def _verify_receipt(receipt: dict[str, Any], *, schema: str, label: str) -> None:
    if receipt.get("schema") != schema:
        raise ValueError(f"{label} has unsupported schema")
    if receipt.get("status") not in ("PASS", "RECORDED"):
        raise ValueError(f"{label} has no authoritative status")
    observed = receipt.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError(f"{label} is missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    if _digest_body(body) != observed:
        raise ValueError(f"{label} digest mismatch")


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


def attest_exec_boundary_cwd(
    *,
    runtime_receipt: dict[str, Any],
    exec_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Compose the exec-boundary cwd record with the runtime dependency receipt."""
    _verify_receipt(
        runtime_receipt,
        schema=RUNTIME_RECEIPT_SCHEMA,
        label="runtime dependency receipt",
    )
    _verify_receipt(
        exec_receipt,
        schema=EXEC_BOUNDARY_CWD_SCHEMA,
        label="exec-boundary cwd record",
    )

    runtime_pid, runtime_starttime, runtime_exe = _process_identity(
        runtime_receipt, label="runtime receipt"
    )
    exec_pid, exec_starttime, exec_exe = _process_identity(
        exec_receipt, label="exec-boundary record"
    )
    if (exec_pid, exec_starttime, exec_exe) != (
        runtime_pid,
        runtime_starttime,
        runtime_exe,
    ):
        raise ValueError("exec-boundary record and runtime receipt identify different processes")

    cwd_object = exec_receipt.get("cwd_object")
    if not isinstance(cwd_object, dict):
        raise ValueError("exec-boundary record has no cwd object")
    cwd_spelling = exec_receipt.get("cwd_spelling")

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_runtime_dependency_receipt_sha256": runtime_receipt["receipt_sha256"],
        "parent_exec_boundary_cwd_record_sha256": exec_receipt["receipt_sha256"],
        "process": {
            "pid": runtime_pid,
            "starttime_ticks": runtime_starttime,
            "exe_link": runtime_exe,
        },
        "cwd_object": cwd_object,
        "cwd_spelling": cwd_spelling,
        "scientific_scope": "COMPOSED_EXEC_BOUNDARY_CWD_OBJECT",
        "interpretation": {
            "cwd_observation_boundary": "EXEC_BOUNDARY_RECORDED_BEFORE_EXECVE",
            "historical_execve_cwd": "PROVEN_SAME_PROCESS_DIRECT_EXEC_PRESERVES_CWD",
            "process_identity_composition": "EXEC_RECORD_EQUALS_RUNTIME_RECEIPT",
            "later_procfs_cwd": "NOT_RELIED_UPON_POST_EXEC_CHDIR_DISCRIMINATED",
            "parent_shell_or_wrapper_cwd": "NOT_AUTHORITATIVE_WRAPPER_CHDIR_DISCRIMINATED",
            "path_spelling": "AUXILIARY_OBJECT_IDENTITY_IS_AUTHORITATIVE",
        },
        "limitations": [
            "RENAME_OR_UNLINK_AFTER_EXEC_CHANGES_SPELLING_NOT_OBJECT_IDENTITY",
            "FILESYSTEM_ROOT_AND_MOUNT_NAMESPACE_NOT_BOUND_THIS_LEAF_PASSES_OBJECT_ONLY",
            "SYMLINK_RESOLUTION_OF_RELATIVE_ARGUMENT_BYTES_NOT_BOUND",
            "EXACT_OPENED_INPUT_BYTES_NOT_CONSUMPTION_ATTESTED",
            "OUTPUT_PATH_CREATION_TIME_NOT_BOUND",
            "RELATIVE_ARGUMENT_PATHS_REQUIRE_NAMESPACE_AND_INPUT_CONSUMPTION_LEAVES",
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
    sub = parser.add_subparsers(dest="command", required=True)

    record_p = sub.add_parser("record", help="write exec-boundary cwd record")
    record_p.add_argument("--receipt-out", type=Path, required=True)
    record_p.add_argument("--proc-root", type=Path, default=Path("/proc"))
    record_p.add_argument("--command", dest="exec_argv", nargs=argparse.REMAINDER, default=[])

    attest_p = sub.add_parser("attest", help="compose record with runtime receipt")
    attest_p.add_argument("--runtime-receipt-json", type=Path, required=True)
    attest_p.add_argument("--exec-record-json", type=Path, required=True)
    attest_p.add_argument("--proc-root", type=Path, default=Path("/proc"))

    args = parser.parse_args()

    if args.command == "record":
        try:
            record = record_exec_boundary_cwd(proc_root=args.proc_root)
        except (KeyError, OSError, ValueError) as exc:
            print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
            return 2
        try:
            args.receipt_out.write_text(
                json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
            )
        except OSError as exc:
            print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
            return 2
        print(json.dumps(record, indent=2, sort_keys=True))
        if args.exec_argv:
            argv = list(args.exec_argv)
            if argv:
                os.execv(argv[0], argv)
        return 0

    if args.command == "attest":
        try:
            result = attest_exec_boundary_cwd(
                runtime_receipt=_load_json_object(
                    args.runtime_receipt_json, label="runtime dependency receipt"
                ),
                exec_receipt=_load_json_object(
                    args.exec_record_json, label="exec-boundary cwd record"
                ),
                proc_root=args.proc_root,
            )
        except (KeyError, OSError, TypeError, ValueError) as exc:
            print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
            return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())