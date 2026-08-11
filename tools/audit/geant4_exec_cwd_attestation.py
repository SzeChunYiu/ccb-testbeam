#!/usr/bin/env python3
"""Bind a direct ELF exec transition to the cwd directory object at exec time.

This Linux-only provenance primitive starts an isolated Python launcher in an
explicit working directory.  The launcher opens ``.`` and the direct ELF target,
records its own PID/starttime, cwd object, target object, and exact target argv,
sends that pre-exec record over a close-on-exec control pipe, and immediately
calls fd-based ``execve`` without an intervening cwd-changing operation.
Successful exec closes the pipe automatically.  The parent then requires the
same PID/starttime to expose the same executable object through
``/proc/<pid>/exe`` and requires the recorded cwd object to equal the directory
object selected by the parent before launch.

The receipt therefore binds one directory object to the direct exec boundary
for the launched process.  It does not by itself bind process root/mount
namespace, relative-path symlink resolution, exact config/macro bytes later
opened by the target, output creation, or any Geant4 physics observable.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import select
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "ccb_geant4_exec_cwd_attestation_v1"
BINDING_SCHEMA = "ccb_geant4_exec_cwd_runtime_binding_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"
_MAX_CONTROL_BYTES = 64 * 1024


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


def _byte_record(raw: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "base64": base64.b64encode(raw).decode("ascii"),
    }
    try:
        result["utf8"] = raw.decode("utf-8")
    except UnicodeDecodeError:
        result["utf8"] = None
    return result


def _file_object_identity(info: os.stat_result) -> dict[str, int]:
    return {
        "device_major": os.major(info.st_dev),
        "device_minor": os.minor(info.st_dev),
        "inode": int(info.st_ino),
        "mode": int(info.st_mode),
        "bytes": int(info.st_size),
    }


def _directory_object_identity(info: os.stat_result) -> dict[str, int]:
    return {
        "st_dev": int(info.st_dev),
        "st_ino": int(info.st_ino),
        "st_mode": int(info.st_mode),
    }


def _read_process_starttime(proc_dir: Path) -> int:
    try:
        raw = (proc_dir / "stat").read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read process stat: {exc}") from exc
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


def _open_directory(path: Path) -> int:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"cannot open launch cwd directory {path}: {exc}") from exc
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        os.close(fd)
        raise ValueError("launch cwd must be a directory")
    return fd


def _open_direct_elf(path: Path) -> int:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        raise ValueError(f"cannot open target executable {path}: {exc}") from exc
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise ValueError("target executable must be a regular file")
    if stat.S_IMODE(info.st_mode) & 0o111 == 0:
        os.close(fd)
        raise ValueError("target executable has no executable permission bits")
    try:
        magic = os.pread(fd, 4, 0)
    except OSError as exc:
        os.close(fd)
        raise ValueError(f"cannot inspect target executable header: {exc}") from exc
    if magic != b"\x7fELF":
        os.close(fd)
        raise ValueError("target must be a direct ELF executable; scripts/wrappers are excluded")
    return fd


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write to exec-boundary control pipe")
        view = view[written:]


def _best_effort_write(fd: int, payload: bytes) -> None:
    try:
        _write_all(fd, payload)
    except OSError:
        pass


def _control_frame(body: dict[str, Any]) -> bytes:
    payload = _canonical_bytes(_with_digest(body)) + b"\n"
    if len(payload) > _MAX_CONTROL_BYTES:
        raise ValueError("exec-boundary control frame exceeds maximum size")
    return payload


def _read_line_with_timeout(fd: int, *, timeout_s: float) -> tuple[bytes, bytes]:
    deadline = time.monotonic() + timeout_s
    payload = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("timed out waiting for pre-exec control frame")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            raise ValueError("timed out waiting for pre-exec control frame")
        chunk = os.read(fd, 4096)
        if not chunk:
            raise ValueError("launcher closed control pipe before pre-exec record")
        payload.extend(chunk)
        if len(payload) > _MAX_CONTROL_BYTES:
            raise ValueError("pre-exec control frame exceeds maximum size")
        newline = payload.find(b"\n")
        if newline >= 0:
            return bytes(payload[:newline]), bytes(payload[newline + 1 :])


def _read_until_eof_with_timeout(
    fd: int, *, timeout_s: float, initial: bytes = b""
) -> bytes:
    deadline = time.monotonic() + timeout_s
    payload = bytearray(initial)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("timed out waiting for direct exec transition")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            raise ValueError("timed out waiting for direct exec transition")
        chunk = os.read(fd, 4096)
        if not chunk:
            return bytes(payload)
        payload.extend(chunk)
        if len(payload) > _MAX_CONTROL_BYTES:
            raise ValueError("exec error control payload exceeds maximum size")


def _decode_control_record(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    observed = value.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError(f"{label} is missing receipt_sha256")
    body = dict(value)
    del body["receipt_sha256"]
    if _digest_body(body) != observed:
        raise ValueError(f"{label} digest mismatch")
    return value


def _same_file_object(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    keys = ("device_major", "device_minor", "inode")
    return all(left.get(key) == right.get(key) for key in keys)


def _same_directory_object(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    keys = ("st_dev", "st_ino")
    return all(left.get(key) == right.get(key) for key in keys)


def _environment_transfer_bytes(env: Mapping[bytes, bytes]) -> bytes:
    entries = [
        {
            "key_base64": base64.b64encode(key).decode("ascii"),
            "value_base64": base64.b64encode(value).decode("ascii"),
        }
        for key, value in sorted(env.items())
    ]
    return _canonical_bytes({"entries": entries})


def _decode_environment_transfer(payload: bytes) -> dict[bytes, bytes]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("target environment transfer is not valid JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
        raise ValueError("target environment transfer has invalid structure")
    result: dict[bytes, bytes] = {}
    for entry in value["entries"]:
        if not isinstance(entry, dict):
            raise ValueError("target environment transfer entry is invalid")
        try:
            key = base64.b64decode(entry["key_base64"], validate=True)
            item = base64.b64decode(entry["value_base64"], validate=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("target environment transfer entry is invalid") from exc
        if key in result:
            raise ValueError("target environment transfer contains a duplicate key")
        result[key] = item
    return _normalise_environment(result)


def _read_all_fd(fd: int, *, label: str) -> bytes:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > _MAX_CONTROL_BYTES * 16:
                raise ValueError(f"{label} exceeds maximum size")
        return b"".join(chunks)
    except OSError as exc:
        raise ValueError(f"cannot read {label}: {exc}") from exc


def _child_pre_exec_record(
    *,
    target_fd: int,
    target_path: Path,
    argv: Sequence[bytes],
    target_environment_sha256: str,
) -> dict[str, Any]:
    cwd_fd = _open_directory(Path("."))
    try:
        cwd_info = os.fstat(cwd_fd)
        target_info = os.fstat(target_fd)
        pid = os.getpid()
        proc_dir = Path("/proc") / str(pid)
        return {
            "stage": "PRE_EXEC_READY",
            "pid": pid,
            "starttime_ticks": _read_process_starttime(proc_dir),
            "cwd": {
                "procfs_link_text": os.readlink(proc_dir / "cwd"),
                "opened_directory_identity": _directory_object_identity(cwd_info),
            },
            "target": {
                "requested_path": os.fspath(target_path),
                "opened_file_identity": _file_object_identity(target_info),
                "direct_exec_mechanism": "FD_EXECVE_ELF_NO_PATH_REOPEN",
            },
            "argv": [
                {"index": index, **_byte_record(raw)} for index, raw in enumerate(argv)
            ],
            "target_environment_sha256": target_environment_sha256,
        }
    finally:
        os.close(cwd_fd)


def _internal_exec_child(
    *,
    control_fd: int,
    target_env_fd: int,
    target_path: Path,
    argv: Sequence[bytes],
) -> int:
    if sys.platform != "linux" or not Path("/proc").is_dir():
        return 126
    if os.execve not in os.supports_fd:
        return 126
    try:
        os.set_inheritable(control_fd, False)
        environment_payload = _read_all_fd(target_env_fd, label="target environment transfer")
        os.close(target_env_fd)
        target_environment = _decode_environment_transfer(environment_payload)
        environment_sha256 = hashlib.sha256(environment_payload).hexdigest()
        target_fd = _open_direct_elf(target_path)
        try:
            pre_exec = _child_pre_exec_record(
                target_fd=target_fd,
                target_path=target_path,
                argv=argv,
                target_environment_sha256=environment_sha256,
            )
            _write_all(control_fd, _control_frame(pre_exec))
            try:
                os.execve(target_fd, list(argv), target_environment)
            except OSError as exc:
                _best_effort_write(
                    control_fd,
                    _control_frame(
                        {"stage": "EXEC_ERROR", "errno": exc.errno, "error": str(exc)}
                    ),
                )
        finally:
            os.close(target_fd)
    except BaseException as exc:
        _best_effort_write(
            control_fd,
            _control_frame(
                {
                    "stage": "PRE_EXEC_ERROR",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            ),
        )
    return 126


def _open_proc_executable(proc_dir: Path) -> tuple[str, dict[str, int]]:
    try:
        link_text = os.readlink(proc_dir / "exe")
        fd = os.open(proc_dir / "exe", os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        raise ValueError(f"cannot open post-exec process executable: {exc}") from exc
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("post-exec process executable is not a regular file")
    return link_text, _file_object_identity(info)


def _observe_post_exec(
    *, pid: int, expected_starttime: int, target_object: dict[str, Any], timeout_s: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    proc_dir = Path("/proc") / str(pid)
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            starttime = _read_process_starttime(proc_dir)
            if starttime != expected_starttime:
                raise ValueError("process starttime changed across exec transition")
            exe_link, executable = _open_proc_executable(proc_dir)
            if not _same_file_object(executable, target_object):
                raise ValueError("post-exec executable object differs from direct target")
            return {
                "pid": pid,
                "starttime_ticks": starttime,
                "exe_link": exe_link,
                "executable_object": executable,
            }
        except ValueError as exc:
            last_error = str(exc)
        time.sleep(0.005)
    if last_error is None:
        last_error = "process was not observable after exec"
    raise ValueError(f"could not bind post-exec process identity: {last_error}")


def _pre_exec_process(record: dict[str, Any]) -> tuple[int, int, dict[str, Any]]:
    if record.get("stage") != "PRE_EXEC_READY":
        raise ValueError("launcher did not produce a PRE_EXEC_READY record")
    pid = record.get("pid")
    starttime = record.get("starttime_ticks")
    target = record.get("target")
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("pre-exec pid is invalid")
    if not isinstance(starttime, int) or starttime < 0:
        raise ValueError("pre-exec starttime is invalid")
    if not isinstance(target, dict):
        raise ValueError("pre-exec target record is missing")
    target_object = target.get("opened_file_identity")
    if not isinstance(target_object, dict):
        raise ValueError("pre-exec target object identity is missing")
    return pid, starttime, target_object


def _build_exec_cwd_receipt(
    *,
    requested_cwd: Path,
    expected_cwd_object: dict[str, Any],
    expected_target_object: dict[str, Any],
    expected_environment_sha256: str,
    pre_exec: dict[str, Any],
    post_exec: dict[str, Any],
) -> dict[str, Any]:
    pid, starttime, target_object = _pre_exec_process(pre_exec)
    if post_exec.get("pid") != pid or post_exec.get("starttime_ticks") != starttime:
        raise ValueError("pre/post exec process identities differ")
    executable = post_exec.get("executable_object")
    if not isinstance(executable, dict) or not _same_file_object(executable, target_object):
        raise ValueError("pre/post exec executable objects differ")
    if not _same_file_object(target_object, expected_target_object):
        raise ValueError("launcher target object differs from parent-selected target object")
    if pre_exec.get("target_environment_sha256") != expected_environment_sha256:
        raise ValueError("launcher target environment differs from parent-selected environment")
    cwd = pre_exec.get("cwd")
    if not isinstance(cwd, dict):
        raise ValueError("pre-exec cwd record is missing")
    cwd_object = cwd.get("opened_directory_identity")
    if not isinstance(cwd_object, dict):
        raise ValueError("pre-exec cwd object identity is missing")
    if not _same_directory_object(cwd_object, expected_cwd_object):
        raise ValueError("launcher cwd object differs from parent-selected cwd object")

    exec_boundary_cwd = {
        "requested_path": os.fspath(requested_cwd),
        **cwd,
    }
    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "pre_exec_record_sha256": pre_exec["receipt_sha256"],
        "process": {
            "pid": pid,
            "starttime_ticks": starttime,
            "exe_link": post_exec["exe_link"],
            "executable_object": executable,
        },
        "exec_boundary_cwd": exec_boundary_cwd,
        "target": pre_exec["target"],
        "argv_passed_to_execve": pre_exec["argv"],
        "target_environment": {
            "canonical_transfer_sha256": expected_environment_sha256,
            "values": "NOT_SERIALIZED_IN_THIS_RECEIPT",
        },
        "transition": {
            "isolated_python_helper": "-I -S",
            "helper_started_in_parent_selected_cwd": True,
            "target_environment_transferred_out_of_band_from_helper_startup": True,
            "helper_recorded_cwd_then_called_only_fd_execve": True,
            "control_pipe_close_on_exec_observed": True,
            "same_pid_and_starttime_across_final_exec": True,
            "same_opened_target_object_observed_via_proc_exe": True,
        },
        "platform": {
            "sys_platform": sys.platform,
            "uname": list(os.uname()),
        },
        "scientific_scope": "DIRECT_ELF_EXEC_BOUNDARY_CWD_OBJECT_ATTESTATION_ONLY",
        "interpretation": {
            "cwd_at_direct_exec_boundary": "BOUND_BY_HELPER_WITH_NO_POST_RECORD_CWD_MUTATOR",
            "argv_bytes_at_direct_exec_call": "BOUND_BY_LAUNCHER_PRE_EXEC_RECORD",
            "runtime_process_composition": "REQUIRES_SEPARATE_RUNTIME_RECEIPT_BINDING",
            "relative_path_resolution": "CWD_START_OBJECT_ONLY_NOT_FULL_FILESYSTEM_RESOLUTION",
        },
        "limitations": [
            "LINUX_PROCFS_AND_FD_EXECVE_REQUIRED",
            "HELPER_SOURCE_CONSUMPTION_IS_NOT_SEPARATELY_CONTENT_ATTESTED_BY_THIS_RECEIPT",
            "PROCESS_ROOT_AND_MOUNT_NAMESPACE_NOT_BOUND",
            "SYMLINK_RESOLUTION_OF_RELATIVE_ARGUMENTS_NOT_BOUND",
            "EXACT_CONFIG_MACRO_AND_OUTPUT_BYTES_AT_CONSUMPTION_NOT_BOUND",
            "TARGET_CAN_CHDIR_OR_FCHDIR_AFTER_EXEC_WITHOUT_INVALIDATING_EXEC_CWD_RECEIPT",
            "LATER_SECOND_EXEC_AFTER_OBSERVATION_NOT_EXCLUDED",
            "TARGET_EXECUTABLE_CONTENT_HASH_DEFERRED_TO_RUNTIME_FINAL_BUILD_RECEIPT",
            "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_OBSERVABLE_VALIDATED",
        ],
    }
    return _with_digest(body)


def _normalise_target_argv(argv: Sequence[bytes]) -> list[bytes]:
    if not argv:
        raise ValueError("argv must contain at least argv[0]")
    result: list[bytes] = []
    for item in argv:
        if not isinstance(item, (bytes, bytearray, memoryview)):
            raise TypeError("target argv entries must be bytes-like")
        raw = bytes(item)
        if b"\0" in raw:
            raise ValueError("argv entries cannot contain NUL bytes")
        result.append(raw)
    return result


def _normalise_environment(env: Mapping[bytes, bytes] | None) -> dict[bytes, bytes]:
    source = os.environb if env is None else env
    result: dict[bytes, bytes] = {}
    for key, value in source.items():
        if not isinstance(key, bytes) or not isinstance(value, bytes):
            raise TypeError("target environment keys and values must be bytes")
        if b"\0" in key or b"=" in key or b"\0" in value:
            raise ValueError("environment contains an invalid key/value for execve")
        result[key] = value
    return result


def launch_exec_cwd_attested(
    *,
    cwd: Path,
    executable: Path,
    argv: Sequence[bytes],
    env: Mapping[bytes, bytes] | None = None,
    timeout_s: float = 10.0,
) -> tuple[subprocess.Popen[bytes], dict[str, Any]]:
    """Launch one direct ELF process and return its process plus exec-cwd receipt."""
    if sys.platform != "linux" or not Path("/proc").is_dir():
        raise ValueError("exec-cwd attestation requires Linux procfs")
    if not cwd.is_absolute() or not executable.is_absolute():
        raise ValueError("cwd and executable must be absolute paths")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    if os.execve not in os.supports_fd:
        raise ValueError("this Python/Linux build does not support fd-based execve")

    argv_bytes = _normalise_target_argv(argv)
    env_bytes = _normalise_environment(env)
    environment_payload = _environment_transfer_bytes(env_bytes)
    environment_sha256 = hashlib.sha256(environment_payload).hexdigest()
    cwd_fd = _open_directory(cwd)
    target_fd = _open_direct_elf(executable)
    try:
        expected_cwd_object = _directory_object_identity(os.fstat(cwd_fd))
        expected_target_object = _file_object_identity(os.fstat(target_fd))
        if hasattr(os, "pipe2"):
            read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
        else:
            read_fd, write_fd = os.pipe()
            os.set_inheritable(read_fd, False)
            os.set_inheritable(write_fd, False)
        encoded_argv = [base64.b64encode(item).decode("ascii") for item in argv_bytes]
        with tempfile.TemporaryFile() as environment_file:
            environment_file.write(environment_payload)
            environment_file.flush()
            environment_file.seek(0)
            target_env_fd = environment_file.fileno()
            command = [
                sys.executable,
                "-I",
                "-S",
                os.fspath(Path(__file__).resolve()),
                "__exec-child",
                "--control-fd",
                str(write_fd),
                "--target-env-fd",
                str(target_env_fd),
                "--target",
                os.fspath(executable),
            ]
            for item in encoded_argv:
                command.extend(["--argv-b64", item])
            helper_env = dict(os.environb)
            helper_env.pop(b"LD_PRELOAD", None)
            helper_env.pop(b"LD_AUDIT", None)
            try:
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=helper_env,
                    pass_fds=(write_fd, target_env_fd),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError as exc:
                os.close(read_fd)
                os.close(write_fd)
                raise ValueError(f"cannot launch isolated exec helper: {exc}") from exc
        os.close(write_fd)
        try:
            pre_payload, buffered = _read_line_with_timeout(read_fd, timeout_s=timeout_s)
            pre_exec = _decode_control_record(pre_payload, label="pre-exec control record")
            if pre_exec.get("stage") != "PRE_EXEC_READY":
                raise ValueError(
                    "launcher pre-exec stage failed: "
                    f"{pre_exec.get('stage')} {pre_exec.get('error', '')}"
                )
            if pre_exec.get("pid") != process.pid:
                raise ValueError("pre-exec control record belongs to another pid")
            remainder = _read_until_eof_with_timeout(
                read_fd, timeout_s=timeout_s, initial=buffered
            )
            if remainder:
                lines = [line for line in remainder.splitlines() if line]
                details = [
                    _decode_control_record(line, label="exec error control record")
                    for line in lines
                ]
                raise ValueError(f"execve did not complete successfully: {details}")
            _, starttime, target_object = _pre_exec_process(pre_exec)
            post_exec = _observe_post_exec(
                pid=process.pid,
                expected_starttime=starttime,
                target_object=target_object,
                timeout_s=timeout_s,
            )
            receipt = _build_exec_cwd_receipt(
                requested_cwd=cwd,
                expected_cwd_object=expected_cwd_object,
                expected_target_object=expected_target_object,
                expected_environment_sha256=environment_sha256,
                pre_exec=pre_exec,
                post_exec=post_exec,
            )
            return process, receipt
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=max(timeout_s, 1.0))
            raise
        finally:
            os.close(read_fd)
    finally:
        os.close(cwd_fd)
        os.close(target_fd)


def bind_exec_cwd_to_runtime(
    *, exec_cwd_receipt: dict[str, Any], runtime_receipt: dict[str, Any]
) -> dict[str, Any]:
    """Bind the exec-boundary cwd receipt to the later runtime receipt."""
    _verify_receipt(exec_cwd_receipt, schema=SCHEMA, label="exec-cwd receipt")
    _verify_receipt(
        runtime_receipt, schema=RUNTIME_RECEIPT_SCHEMA, label="runtime dependency receipt"
    )
    launch_process = exec_cwd_receipt.get("process")
    runtime_process = runtime_receipt.get("process")
    if not isinstance(launch_process, dict) or not isinstance(runtime_process, dict):
        raise ValueError("receipt process record is missing")
    for key in ("pid", "starttime_ticks", "exe_link"):
        if runtime_process.get(key) != launch_process.get(key):
            raise ValueError(f"runtime process {key} differs from exec-cwd receipt")
    launch_executable = launch_process.get("executable_object")
    runtime_executable = runtime_process.get("executable")
    if not isinstance(launch_executable, dict) or not isinstance(runtime_executable, dict):
        raise ValueError("receipt executable object record is missing")
    if not _same_file_object(launch_executable, runtime_executable):
        raise ValueError("runtime executable object differs from exec-cwd receipt")

    body = {
        "schema": BINDING_SCHEMA,
        "status": "PASS",
        "parent_exec_cwd_receipt_sha256": exec_cwd_receipt["receipt_sha256"],
        "parent_runtime_dependency_receipt_sha256": runtime_receipt["receipt_sha256"],
        "process": {
            "pid": launch_process["pid"],
            "starttime_ticks": launch_process["starttime_ticks"],
            "exe_link": launch_process["exe_link"],
        },
        "exec_boundary_cwd": exec_cwd_receipt["exec_boundary_cwd"],
        "scientific_scope": "EXEC_BOUNDARY_CWD_COMPOSED_WITH_RUNTIME_PROCESS_IDENTITY_ONLY",
        "limitations": [
            "PROCESS_ROOT_AND_MOUNT_NAMESPACE_NOT_BOUND",
            "RELATIVE_INPUT_FILE_CONSUMPTION_NOT_BOUND",
            "OUTPUT_CREATION_PATH_NOT_BOUND",
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


def _parse_timeout(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be numeric") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("timeout must be positive")
    return parsed


def _decode_argv_items(items: Sequence[str]) -> list[bytes]:
    result: list[bytes] = []
    for item in items:
        try:
            result.append(base64.b64decode(item, validate=True))
        except ValueError as exc:
            raise argparse.ArgumentTypeError("invalid base64 target argv") from exc
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    child = subparsers.add_parser("__exec-child", help=argparse.SUPPRESS)
    child.add_argument("--control-fd", type=int, required=True)
    child.add_argument("--target-env-fd", type=int, required=True)
    child.add_argument("--target", type=Path, required=True)
    child.add_argument("--argv-b64", action="append", default=[])

    launch = subparsers.add_parser("launch")
    launch.add_argument("--cwd", type=Path, required=True)
    launch.add_argument("--executable", type=Path, required=True)
    launch.add_argument("--receipt-json", type=Path, required=True)
    launch.add_argument("--timeout-s", type=_parse_timeout, default=10.0)
    launch.add_argument("argv", nargs=argparse.REMAINDER)

    compose = subparsers.add_parser("compose")
    compose.add_argument("--exec-cwd-receipt-json", type=Path, required=True)
    compose.add_argument("--runtime-receipt-json", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "__exec-child":
        return _internal_exec_child(
            control_fd=args.control_fd,
            target_env_fd=args.target_env_fd,
            target_path=args.target,
            argv=_decode_argv_items(args.argv_b64),
        )
    if args.command == "compose":
        try:
            result = bind_exec_cwd_to_runtime(
                exec_cwd_receipt=_load_json_object(
                    args.exec_cwd_receipt_json, label="exec-cwd receipt"
                ),
                runtime_receipt=_load_json_object(
                    args.runtime_receipt_json, label="runtime dependency receipt"
                ),
            )
        except (KeyError, OSError, TypeError, ValueError) as exc:
            print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
            return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    argv = [os.fsencode(item) for item in args.argv]
    if argv and argv[0] == b"--":
        argv = argv[1:]
    if not argv:
        argv = [os.fsencode(os.fspath(args.executable))]
    try:
        process, result = launch_exec_cwd_attested(
            cwd=args.cwd,
            executable=args.executable,
            argv=argv,
            timeout_s=args.timeout_s,
        )
        args.receipt_json.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (KeyError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2

    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())