#!/usr/bin/env python3
"""Record and attest Linux filesystem lookup state at a direct-exec boundary.

This bounded provenance primitive records the current-working-directory object,
process root object, mount-namespace identity, and exact /proc/PID/mountinfo
bytes in a controlled launcher immediately before a direct ``os.execv``.  A
later runtime receipt is composed using PID/starttime continuity and, when a
command is supplied, exact intended-target content identity.

The receipt binds userspace pre-exec filesystem state.  It is not a kernel
exec-event log and does not prove which config/macro bytes the target later
opens: post-exec chdir/fchdir, chroot/pivot_root, setns/unshare, mount changes,
symlink replacement, and ordinary file replacement remain separate provenance
leaves.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import threading
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_loader_exec_boundary_fs_attestation_v1"
EXEC_BOUNDARY_FS_SCHEMA = "ccb_geant4_loader_exec_boundary_fs_record_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"

_NS_LINK_RE = re.compile(r"mnt:\[(\d+)\]\Z")


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


def _read_link(path: Path, *, label: str) -> str:
    try:
        return os.readlink(path)
    except OSError as exc:
        raise ValueError(f"cannot read {label} {path}: {exc}") from exc


def _open_directory_identity(path: Path) -> dict[str, int]:
    flags = getattr(os, "O_PATH", os.O_RDONLY)
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
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


def _mount_namespace_identity(proc_dir: Path) -> dict[str, Any]:
    path = proc_dir / "ns" / "mnt"
    link = _read_link(path, label="mount namespace link")
    match = _NS_LINK_RE.fullmatch(link)
    if match is None:
        raise ValueError(f"unexpected mount namespace link spelling: {link!r}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"cannot open mount namespace handle {path}: {exc}") from exc
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    link_inode = int(match.group(1), 10)
    if int(info.st_ino) != link_inode:
        raise ValueError("mount namespace link inode disagrees with opened namespace handle")
    return {
        "link_text": link,
        "st_dev": int(info.st_dev),
        "st_ino": int(info.st_ino),
        "st_mode": int(info.st_mode),
    }


def _mountinfo_snapshot(raw: bytes) -> dict[str, Any]:
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "line_count": len(raw.splitlines()),
        "content_base64": base64.b64encode(raw).decode("ascii"),
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


def _single_thread_identity(proc_dir: Path) -> dict[str, Any]:
    native_tid = threading.get_native_id()
    pid = os.getpid()
    if native_tid != pid:
        raise ValueError("exec-boundary recorder must run on the thread-group leader")
    task_dir = proc_dir / "task"
    try:
        tids = sorted(int(item.name) for item in task_dir.iterdir() if item.name.isdigit())
    except OSError as exc:
        raise ValueError(f"cannot enumerate process tasks {task_dir}: {exc}") from exc
    return {
        "pid": pid,
        "native_tid": native_tid,
        "thread_count": len(tids),
        "observed_tids": tids,
        "caller_is_thread_group_leader": True,
    }


def record_exec_boundary_fs(
    *,
    proc_root: Path = Path("/proc"),
    cwd: Path | None = None,
    root_path: Path = Path("/"),
    exec_argv: list[str] | None = None,
) -> dict[str, Any]:
    """Record filesystem lookup state before a controlled direct exec."""
    pid = os.getpid()
    proc_dir = proc_root / str(pid)
    thread_state = _single_thread_identity(proc_dir)

    start_before = _read_process_starttime(proc_dir)
    exe_before = _read_link(proc_dir / "exe", label="launcher executable link")
    if exe_before.endswith(" (deleted)"):
        raise ValueError("launcher executable is deleted")

    cwd_path = cwd if cwd is not None else Path(".")
    cwd_before = _open_directory_identity(cwd_path)
    root_before = _open_directory_identity(root_path)
    root_link_before = _read_link(proc_dir / "root", label="process root link")
    ns_before = _mount_namespace_identity(proc_dir)
    mountinfo_before = _read_proc_bytes(proc_dir, "mountinfo", label="mountinfo")

    # Repeat the mutable lookup-state observations. Equality excludes simple
    # transitions during this userspace snapshot; an ABA transition is kept as
    # an explicit limitation below.
    mountinfo_after = _read_proc_bytes(proc_dir, "mountinfo", label="mountinfo recheck")
    ns_after = _mount_namespace_identity(proc_dir)
    root_after = _open_directory_identity(root_path)
    root_link_after = _read_link(proc_dir / "root", label="process root link recheck")
    cwd_after = _open_directory_identity(cwd_path)
    start_after = _read_process_starttime(proc_dir)
    exe_after = _read_link(proc_dir / "exe", label="launcher executable link recheck")

    if mountinfo_after != mountinfo_before:
        raise ValueError("mountinfo changed during exec-boundary filesystem snapshot")
    if ns_after != ns_before:
        raise ValueError("mount namespace identity changed during filesystem snapshot")
    if root_after != root_before:
        raise ValueError("process root directory object changed during filesystem snapshot")
    if cwd_after != cwd_before:
        raise ValueError("process cwd directory object changed during filesystem snapshot")
    if start_after != start_before:
        raise ValueError("process identity changed during filesystem snapshot")
    if exe_after != exe_before:
        raise ValueError("launcher executable changed during filesystem snapshot")

    intent = None
    if exec_argv:
        argv = list(exec_argv)
        if not argv or not argv[0]:
            raise ValueError("direct exec argv must contain a non-empty argv[0]")
        intent = {
            "mode": "DIRECT_OS_EXECV",
            "argv": argv,
            "target": _hash_regular_file(Path(argv[0])),
        }

    try:
        cwd_spelling = os.getcwd()
    except OSError:
        cwd_spelling = None

    body: dict[str, Any] = {
        "schema": EXEC_BOUNDARY_FS_SCHEMA,
        "status": "RECORDED",
        "boundary": "USERSPACE_PRE_EXEC_DIRECT_EXECV_FILESYSTEM_SNAPSHOT",
        "process": {
            "pid": pid,
            "starttime_ticks": start_before,
            "exe_link": exe_before,
        },
        "thread_state": thread_state,
        "cwd": {
            "spelling": cwd_spelling,
            "object": cwd_before,
        },
        "root": {
            "link_text_before": root_link_before,
            "link_text_after": root_link_after,
            "object": root_before,
        },
        "mount_namespace": ns_before,
        "mountinfo": _mountinfo_snapshot(mountinfo_before),
        "stability_checks": {
            "two_mountinfo_reads_identical": True,
            "two_mount_namespace_observations_identical": True,
            "two_root_object_observations_identical": True,
            "two_cwd_object_observations_identical": True,
            "process_identity_stable": True,
            "launcher_executable_link_stable": True,
        },
        "scientific_scope": "PRE_EXEC_CWD_ROOT_MOUNT_NAMESPACE_AND_MOUNT_TABLE_STATE",
        "interpretation": {
            "relative_lookup_start": "CWD_OBJECT_AT_USERSPACE_PRE_EXEC_SNAPSHOT",
            "absolute_and_absolute_symlink_root": "ROOT_OBJECT_AT_USERSPACE_PRE_EXEC_SNAPSHOT",
            "mount_view": "MOUNT_NAMESPACE_HANDLE_PLUS_EXACT_MOUNTINFO_BYTES_AT_PRE_EXEC_SNAPSHOT",
            "execve_inheritance": (
                "CWD_ROOT_AND_MOUNT_NAMESPACE_ARE_EXPECTED_TO_"
                "SURVIVE_SUCCESSFUL_EXECVE"
            ),
            "actual_input_open_state": "NOT_PROVEN_TARGET_CAN_CHANGE_FS_STATE_AFTER_EXEC",
        },
        "limitations": [
            "KERNEL_EXECVE_EVENT_NOT_OBSERVED_INTERMEDIATE_EXEC_CHAIN_NOT_EXCLUDED",
            "INTENDED_EXEC_TARGET_PATH_CAN_CHANGE_AFTER_PRE_EXEC_HASH_BEFORE_EXECV",
            "ABA_MOUNT_OR_ROOT_TRANSITION_BETWEEN_EQUAL_OBSERVATIONS_NOT_EXCLUDED",
            "MULTITHREADED_OR_SHARED_MOUNT_NAMESPACE_MUTATION_OUTSIDE_SNAPSHOT_WINDOW_NOT_EXCLUDED",
            "POST_EXEC_CHDIR_FCHDIR_CHROOT_PIVOT_ROOT_SETNS_UNSHARE_OR_MOUNT_CHANGES_NOT_EXCLUDED",
            "RELATIVE_CONFIG_MACRO_AND_AUXILIARY_INPUT_OPEN_EVENTS_NOT_OBSERVED",
            "SYMLINK_TARGET_AND_FILE_CONTENT_REPLACEMENT_AFTER_SNAPSHOT_NOT_EXCLUDED",
            "OUTPUT_PATH_CREATION_TIME_AND_TARGET_OBJECT_NOT_BOUND",
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
    *, exec_record: dict[str, Any], runtime_receipt: dict[str, Any], runtime_exe: str
) -> dict[str, Any] | None:
    intent = exec_record.get("exec_intent")
    if intent is None:
        return None
    if not isinstance(intent, dict) or intent.get("mode") != "DIRECT_OS_EXECV":
        raise ValueError("exec-boundary filesystem record has unsupported exec intent")
    target = intent.get("target")
    if not isinstance(target, dict):
        raise ValueError("exec-boundary filesystem record has no target identity")
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


def attest_exec_boundary_fs(
    *, runtime_receipt: dict[str, Any], exec_fs_record: dict[str, Any]
) -> dict[str, Any]:
    """Compose one pre-exec filesystem snapshot with a post-exec runtime receipt."""
    _verify_receipt(
        runtime_receipt,
        schema=RUNTIME_RECEIPT_SCHEMA,
        label="runtime dependency receipt",
    )
    _verify_receipt(
        exec_fs_record,
        schema=EXEC_BOUNDARY_FS_SCHEMA,
        label="exec-boundary filesystem record",
    )
    runtime_pid, runtime_starttime, runtime_exe = _process_identity(
        runtime_receipt, label="runtime receipt"
    )
    record_pid, record_starttime, launcher_exe = _process_identity(
        exec_fs_record, label="exec-boundary filesystem record"
    )
    if (record_pid, record_starttime) != (runtime_pid, runtime_starttime):
        raise ValueError("filesystem record and runtime receipt identify different processes")

    intent = _verify_exec_intent_against_runtime(
        exec_record=exec_fs_record,
        runtime_receipt=runtime_receipt,
        runtime_exe=runtime_exe,
    )
    if intent is None and launcher_exe != runtime_exe:
        raise ValueError("record lacks exec intent and executable links differ")

    for key in ("cwd", "root", "mount_namespace", "mountinfo", "stability_checks"):
        if not isinstance(exec_fs_record.get(key), dict):
            raise ValueError(f"exec-boundary filesystem record is missing {key}")

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_runtime_dependency_receipt_sha256": runtime_receipt["receipt_sha256"],
        "parent_exec_boundary_fs_record_sha256": exec_fs_record["receipt_sha256"],
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
        "cwd": exec_fs_record["cwd"],
        "root": exec_fs_record["root"],
        "mount_namespace": exec_fs_record["mount_namespace"],
        "mountinfo": exec_fs_record["mountinfo"],
        "scientific_scope": "COMPOSED_PRE_EXEC_FILESYSTEM_LOOKUP_STATE_AND_RUNTIME_IDENTITY",
        "interpretation": {
            "exec_time_lookup_state": (
                "BOUNDED_BY_USERSPACE_PRE_EXEC_SNAPSHOT_AND_"
                "SAME_PID_STARTTIME_DIRECT_EXEC_INTENT"
            ),
            "mount_namespace_identity": "NSFS_DEVICE_AND_INODE_PLUS_MNT_LINK_TEXT",
            "mount_table": "EXACT_PRE_EXEC_PROC_MOUNTINFO_BYTES_DIGEST_AND_CONTENT",
            "root_and_cwd": "OPENED_DIRECTORY_OBJECT_IDENTITIES_NOT_PATH_SPELLINGS",
            "actual_relative_input_consumption": (
                "NOT_ATTESTED_REQUIRES_OPEN_EVENT_AND_OPENED_BYTES_CHILD"
            ),
        },
        "limitations": list(exec_fs_record.get("limitations", [])),
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
    sub = parser.add_subparsers(dest="subcommand", required=True)

    record_p = sub.add_parser("record", help="write pre-exec filesystem-state record")
    record_p.add_argument("--receipt-out", type=Path, required=True)
    record_p.add_argument("--proc-root", type=Path, default=Path("/proc"))
    record_p.add_argument(
        "--command", dest="exec_argv", nargs=argparse.REMAINDER, default=[]
    )

    attest_p = sub.add_parser("attest", help="compose filesystem record with runtime receipt")
    attest_p.add_argument("--runtime-receipt-json", type=Path, required=True)
    attest_p.add_argument("--exec-fs-record-json", type=Path, required=True)

    args = parser.parse_args()

    if args.subcommand == "record":
        try:
            record = record_exec_boundary_fs(
                proc_root=args.proc_root,
                exec_argv=list(args.exec_argv) if args.exec_argv else None,
            )
            args.receipt_out.write_text(
                json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
            )
        except (KeyError, OSError, TypeError, ValueError) as exc:
            print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
            return 2
        print(json.dumps(record, indent=2, sort_keys=True), flush=True)
        if args.exec_argv:
            argv = list(args.exec_argv)
            os.execv(argv[0], argv)
        return 0

    if args.subcommand == "attest":
        try:
            result = attest_exec_boundary_fs(
                runtime_receipt=_load_json_object(
                    args.runtime_receipt_json, label="runtime dependency receipt"
                ),
                exec_fs_record=_load_json_object(
                    args.exec_fs_record_json, label="exec-boundary filesystem record"
                ),
            )
        except (KeyError, OSError, TypeError, ValueError) as exc:
            print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
            return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
