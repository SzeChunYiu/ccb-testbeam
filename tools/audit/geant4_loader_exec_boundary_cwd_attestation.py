#!/usr/bin/env python3
"""Record and attest the working-directory object around a direct exec transition.

The pre-exec record binds an opened cwd directory object to a Linux process
identity immediately before a launcher calls ``os.execv``.  A later runtime
receipt is composed using the invariant that exec preserves PID/starttime and
cwd while replacing the process image.  The launcher executable is therefore
not required to equal the post-exec executable; when an exec command is
provided, the intended target bytes/path are recorded separately and compared
with the runtime receipt.

This is bounded provenance.  It does not itself observe the kernel execve event,
exclude an intermediate exec chain, bind filesystem namespaces, resolve relative
input bytes, or validate Geant4 physics.
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


def _hash_regular_file(path: Path) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"cannot open intended exec target {path}: {exc}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"intended exec target {path} is not a regular file")
        digest = hashlib.sha256()
        total = 0
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block:
                break
            digest.update(block)
            total += len(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    before_id = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_id = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_id != after_id or total != before.st_size:
        raise ValueError(f"intended exec target {path} changed while being hashed")
    return {
        "path": os.fspath(path),
        "resolved_path": os.path.realpath(path),
        "bytes": total,
        "sha256": digest.hexdigest(),
        "st_dev": int(before.st_dev),
        "st_ino": int(before.st_ino),
        "st_mode": int(before.st_mode),
        "mtime_ns": int(before.st_mtime_ns),
        "ctime_ns": int(before.st_ctime_ns),
    }


def record_exec_boundary_cwd(
    *,
    proc_root: Path = Path("/proc"),
    cwd: Path | None = None,
    exec_argv: list[str] | None = None,
) -> dict[str, Any]:
    """Record cwd and launcher state immediately before a direct ``os.execv``.

    ``exec_argv`` is optional for backwards-compatible fixture construction. A
    production direct-exec record should supply it so the launcher executable
    and intended target executable are not conflated.
    """
    pid = os.getpid()
    proc_dir = proc_root / str(pid)
    starttime = _read_process_starttime(proc_dir)
    launcher_exe_link = _read_exe_link(proc_dir)
    if launcher_exe_link.endswith(" (deleted)"):
        raise ValueError("launcher executable is deleted")

    target = cwd if cwd is not None else Path(".")
    cwd_object = _open_directory_identity(target)
    try:
        spelling = os.getcwd()
    except OSError:
        spelling = None

    intent = None
    if exec_argv:
        argv = list(exec_argv)
        if not argv or not argv[0]:
            raise ValueError("direct exec argv must contain a non-empty argv[0]")
        target_record = _hash_regular_file(Path(argv[0]))
        intent = {
            "mode": "DIRECT_OS_EXECV",
            "argv": argv,
            "target": target_record,
        }

    body: dict[str, Any] = {
        "schema": EXEC_BOUNDARY_CWD_SCHEMA,
        "status": "RECORDED",
        "boundary": "IMMEDIATELY_BEFORE_DIRECT_EXECVE_NO_INTERVENING_CHDIR",
        "process": {
            "pid": pid,
            "starttime_ticks": starttime,
            "exe_link": launcher_exe_link,
        },
        "cwd_object": cwd_object,
        "cwd_spelling": spelling,
        "scientific_scope": "PRE_EXEC_CWD_OBJECT_AND_DIRECT_EXECV_INTENT",
        "interpretation": {
            "observation": "OPENED_DIRECTORY_OBJECT_BEFORE_DIRECT_EXECV",
            "launcher_executable": "PRE_EXEC_PROCESS_IMAGE_EXPECTED_TO_BE_REPLACED",
            "historical_execve_cwd": "BOUND_IF_LAUNCHER_EXEC_INTENT_COMPOSES_WITH_RUNTIME",
            "later_procfs_cwd": "NOT_RELIED_UPON_RECORD_BINDS_PRE_EXEC_CWD",
            "parent_shell_cwd": "NOT_AUTHORITATIVE_LAUNCHER_RECORD_IS_THE_BOUNDARY",
            "path_spelling": "AUXILIARY_OBJECT_IDENTITY_IS_AUTHORITATIVE",
        },
        "limitations": [
            "KERNEL_EXECVE_EVENT_NOT_OBSERVED_INTERMEDIATE_EXEC_CHAIN_NOT_EXCLUDED",
            "INTENDED_EXEC_TARGET_PATH_CAN_CHANGE_AFTER_PRE_EXEC_HASH_BEFORE_EXECV",
            "RENAME_OR_UNLINK_AFTER_EXEC_CHANGES_SPELLING_NOT_OBJECT_IDENTITY",
            "FILESYSTEM_ROOT_AND_MOUNT_NAMESPACE_NOT_BOUND_BY_THIS_RECORD",
            "SYMLINK_RESOLUTION_OF_RELATIVE_ARGUMENT_BYTES_NOT_BOUND",
            "EXACT_OPENED_INPUT_BYTES_NOT_CONSUMPTION_ATTESTED",
            "OUTPUT_PATH_CREATION_TIME_NOT_BOUND",
            "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_OBSERVABLE_VALIDATED",
        ],
    }
    if intent is not None:
        body["exec_intent"] = intent
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


def _verify_exec_intent_against_runtime(
    *, exec_receipt: dict[str, Any], runtime_receipt: dict[str, Any], runtime_exe: str
) -> dict[str, Any] | None:
    intent = exec_receipt.get("exec_intent")
    if intent is None:
        return None
    if not isinstance(intent, dict) or intent.get("mode") != "DIRECT_OS_EXECV":
        raise ValueError("exec-boundary record has unsupported exec intent")
    target = intent.get("target")
    if not isinstance(target, dict):
        raise ValueError("exec-boundary record has no intended target identity")
    process = runtime_receipt.get("process")
    runtime_binary = process.get("executable") if isinstance(process, dict) else None
    if not isinstance(runtime_binary, dict):
        raise ValueError("runtime receipt has no executable content identity")
    for field in ("bytes", "sha256"):
        if target.get(field) != runtime_binary.get(field):
            raise ValueError("runtime executable bytes differ from pre-exec intended target")
    target_resolved = target.get("resolved_path")
    if not isinstance(target_resolved, str) or not target_resolved:
        raise ValueError("pre-exec intended target resolved path is missing")
    if os.path.realpath(runtime_exe) != target_resolved:
        raise ValueError("runtime executable path differs from pre-exec intended target")
    return intent


def attest_exec_boundary_cwd(
    *,
    runtime_receipt: dict[str, Any],
    exec_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Compose a pre-exec cwd record with a post-exec runtime receipt."""
    del proc_root  # retained for API compatibility; runtime receipt already binds live procfs.
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
    exec_pid, exec_starttime, launcher_exe = _process_identity(
        exec_receipt, label="exec-boundary record"
    )
    if (exec_pid, exec_starttime) != (runtime_pid, runtime_starttime):
        raise ValueError("exec-boundary record and runtime receipt identify different processes")

    intent = _verify_exec_intent_against_runtime(
        exec_receipt=exec_receipt,
        runtime_receipt=runtime_receipt,
        runtime_exe=runtime_exe,
    )
    if intent is None and launcher_exe != runtime_exe:
        raise ValueError(
            "exec-boundary record lacks exec intent and executable links differ"
        )

    cwd_object = exec_receipt.get("cwd_object")
    if not isinstance(cwd_object, dict):
        raise ValueError("exec-boundary record has no cwd object")
    cwd_spelling = exec_receipt.get("cwd_spelling")

    historical_cwd = (
        "PROVEN_SAME_PROCESS_DIRECT_EXEC_PRESERVES_CWD"
        if intent is None
        else "DIRECT_EXECV_LAUNCHER_INTENT_NOT_KERNEL_EXEC_EVENT"
    )
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
        "exec_transition": {
            "launcher_exe_link": launcher_exe,
            "runtime_exe_link": runtime_exe,
            "same_pid_starttime": True,
            "exec_intent_bound": intent is not None,
            "kernel_execve_event_observed": False,
        },
        "cwd_object": cwd_object,
        "cwd_spelling": cwd_spelling,
        "scientific_scope": "COMPOSED_PRE_EXEC_CWD_AND_POST_EXEC_RUNTIME_IDENTITY",
        "interpretation": {
            "cwd_observation_boundary": "PRE_EXEC_RECORD_COMPOSED_WITH_SAME_PID_STARTTIME_RUNTIME",
            "historical_execve_cwd": historical_cwd,
            "process_identity_composition": "PID_AND_STARTTIME_STABLE_ACROSS_IMAGE_REPLACEMENT",
            "launcher_vs_runtime_executable": "EXPECTED_TO_DIFFER_AFTER_SUCCESSFUL_EXEC",
            "later_procfs_cwd": "NOT_RELIED_UPON_POST_EXEC_CHDIR_DISCRIMINATED",
            "parent_shell_or_wrapper_cwd": "NOT_AUTHORITATIVE_WRAPPER_CHDIR_DISCRIMINATED",
            "path_spelling": "AUXILIARY_OBJECT_IDENTITY_IS_AUTHORITATIVE",
        },
        "limitations": [
            "KERNEL_EXECVE_EVENT_NOT_OBSERVED_INTERMEDIATE_EXEC_CHAIN_NOT_EXCLUDED",
            "INTENDED_EXEC_TARGET_PATH_CAN_CHANGE_AFTER_PRE_EXEC_HASH_BEFORE_EXECV",
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

    record_p = sub.add_parser("record", help="write pre-exec cwd record")
    record_p.add_argument("--receipt-out", type=Path, required=True)
    record_p.add_argument("--proc-root", type=Path, default=Path("/proc"))
    record_p.add_argument(
        "--command", dest="exec_argv", nargs=argparse.REMAINDER, default=[]
    )

    attest_p = sub.add_parser("attest", help="compose record with runtime receipt")
    attest_p.add_argument("--runtime-receipt-json", type=Path, required=True)
    attest_p.add_argument("--exec-record-json", type=Path, required=True)
    attest_p.add_argument("--proc-root", type=Path, default=Path("/proc"))

    args = parser.parse_args()

    if args.command == "record":
        try:
            record = record_exec_boundary_cwd(
                proc_root=args.proc_root,
                exec_argv=list(args.exec_argv) if args.exec_argv else None,
            )
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
        print(json.dumps(record, indent=2, sort_keys=True), flush=True)
        if args.exec_argv:
            argv = list(args.exec_argv)
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
