#!/usr/bin/env python3
"""Bind exact pre-exec launch state for a Geant4 executable.

This Linux/POSIX provenance primitive closes the gap between a validated final
build receipt and a later runtime receipt. It opens and re-hashes the exact
final executable, snapshots a canonical complete environment map, binds the
working directory by an opened directory descriptor, atomically writes a
self-digested READY_TO_EXEC receipt, then replaces the launcher with the target
through descriptor-based ``execve``.

The receipt is deliberately not a proof that exec succeeded. A later runtime
attestation must compose it with the same ``(pid, starttime_ticks)`` and exact
executable identity. Descriptor-based execution removes pathname-rebinding
ambiguity but cannot stop another writer from mutating the executable inode
between the final recheck and exec; immutable-consumption remains a child atom.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "ccb_geant4_preexec_launch_v1"
FINAL_RECEIPT_SCHEMA = "ccb_geant4_build_binding_final_v1"
IMPLEMENTATION_ID = "linux_fd_execve_preexec_binding_v1"
LOADER_EXACT_NAMES = frozenset({"GLIBC_TUNABLES"})


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


def _verify_final_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != FINAL_RECEIPT_SCHEMA:
        raise ValueError("unsupported or missing final build-binding receipt schema")
    if receipt.get("status") != "PASS":
        raise ValueError("final build-binding receipt is not PASS")
    observed = receipt.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError("final build-binding receipt is missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    if _digest_body(body) != observed:
        raise ValueError("final build-binding receipt digest mismatch")


def _stat_identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _hash_open_regular_fd(fd: int, *, label: str) -> dict[str, Any]:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular file")
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    total = 0
    prefix = bytearray()
    while True:
        block = os.read(fd, 1024 * 1024)
        if not block:
            break
        if len(prefix) < 4:
            prefix.extend(block[: 4 - len(prefix)])
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
        "elf_magic": bytes(prefix) == b"\x7fELF",
    }


def _read_process_starttime(proc_dir: Path = Path("/proc/self")) -> int:
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
        value = int(tail[19], 10)
    except ValueError as exc:
        raise ValueError("process stat starttime is not an integer") from exc
    if value < 0:
        raise ValueError("process stat starttime must be nonnegative")
    return value


def _loader_control_name(name: bytes) -> bool:
    return name.startswith(b"LD_") or name in {
        item.encode("ascii") for item in LOADER_EXACT_NAMES
    }


def _validate_environment(environment: Mapping[bytes, bytes]) -> dict[bytes, bytes]:
    result: dict[bytes, bytes] = {}
    for raw_name, raw_value in environment.items():
        if not isinstance(raw_name, bytes) or not isinstance(raw_value, bytes):
            raise ValueError("environment names and values must be bytes")
        if not raw_name or b"=" in raw_name or b"\0" in raw_name:
            raise ValueError(f"invalid environment name bytes: {raw_name!r}")
        if b"\0" in raw_value:
            raise ValueError(f"environment value contains NUL for {raw_name!r}")
        if raw_name in result:
            raise ValueError(f"duplicate environment name: {raw_name!r}")
        result[raw_name] = raw_value
    if not result:
        raise ValueError("launch environment must not be empty")
    return dict(sorted(result.items()))


def _environment_record(environment: Mapping[bytes, bytes]) -> dict[str, Any]:
    env = _validate_environment(environment)
    block = b"".join(name + b"=" + value + b"\0" for name, value in env.items())
    controls = []
    for name, value in env.items():
        if not _loader_control_name(name):
            continue
        controls.append(
            {
                "name_ascii": name.decode("ascii"),
                "value_bytes": len(value),
                "value_sha256": hashlib.sha256(value).hexdigest(),
                "value_base64": base64.b64encode(value).decode("ascii"),
                "value_utf8": _utf8_or_none(value),
            }
        )
    return {
        "ordering": "BYTEWISE_NAME_SORT_ASCENDING",
        "entry_count": len(env),
        "canonical_nul_block_bytes": len(block),
        "canonical_nul_block_sha256": hashlib.sha256(block).hexdigest(),
        "loader_controls": controls,
    }


def _utf8_or_none(value: bytes) -> str | None:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _argv_record(argv: Sequence[bytes]) -> dict[str, Any]:
    if not argv:
        raise ValueError("argv must contain at least argv[0]")
    if argv[0] == b"":
        raise ValueError("argv[0] must not be empty")
    records = []
    canonical = bytearray()
    for index, value in enumerate(argv):
        if not isinstance(value, bytes):
            raise ValueError("argv entries must be bytes")
        if b"\0" in value:
            raise ValueError(f"argv[{index}] contains NUL")
        canonical.extend(value)
        canonical.append(0)
        records.append(
            {
                "index": index,
                "bytes": len(value),
                "sha256": hashlib.sha256(value).hexdigest(),
                "base64": base64.b64encode(value).decode("ascii"),
                "utf8": _utf8_or_none(value),
            }
        )
    return {
        "ordering": "ARGV_INDEX_ORDER",
        "entries": records,
        "canonical_nul_block_bytes": len(canonical),
        "canonical_nul_block_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _open_bound_cwd(cwd: Path) -> tuple[int, dict[str, Any]]:
    if not cwd.is_absolute():
        raise ValueError("launch cwd must be an absolute path")
    try:
        lst = cwd.lstat()
    except OSError as exc:
        raise ValueError(f"cannot inspect launch cwd {cwd}: {exc}") from exc
    if stat.S_ISLNK(lst.st_mode):
        raise ValueError("launch cwd must not be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_CLOEXEC
    try:
        fd = os.open(cwd, flags)
    except OSError as exc:
        raise ValueError(f"cannot open launch cwd {cwd}: {exc}") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode):
            raise ValueError("launch cwd descriptor does not refer to a directory")
        resolved = str(cwd.resolve(strict=True))
        record = {
            "path": resolved,
            "device_major": os.major(st.st_dev),
            "device_minor": os.minor(st.st_dev),
            "inode": st.st_ino,
            "mode": stat.S_IMODE(st.st_mode),
        }
        return fd, record
    except Exception:
        os.close(fd)
        raise


def _same_directory(fd: int, record: dict[str, Any]) -> bool:
    st = os.fstat(fd)
    return (
        os.major(st.st_dev),
        os.minor(st.st_dev),
        st.st_ino,
        stat.S_IMODE(st.st_mode),
    ) == (
        record["device_major"],
        record["device_minor"],
        record["inode"],
        record["mode"],
    )


def _open_final_executable(
    final_receipt: dict[str, Any],
) -> tuple[int, dict[str, Any], str]:
    _verify_final_receipt(final_receipt)
    record = final_receipt.get("executable")
    if not isinstance(record, dict):
        raise ValueError("final build-binding receipt has no executable record")
    raw_path = record.get("path")
    expected_bytes = record.get("bytes")
    expected_sha256 = record.get("sha256")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("final executable path is invalid")
    if not isinstance(expected_bytes, int) or expected_bytes < 0:
        raise ValueError("final executable byte count is invalid")
    if not isinstance(expected_sha256, str):
        raise ValueError("final executable SHA-256 is invalid")

    path = Path(raw_path)
    if not path.is_absolute():
        raise ValueError("final executable path must be absolute")
    flags = os.O_RDONLY | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"cannot open final executable {path}: {exc}") from exc
    try:
        observed = _hash_open_regular_fd(fd, label="final executable")
        if (observed["bytes"], observed["sha256"]) != (
            expected_bytes,
            expected_sha256,
        ):
            raise ValueError("final executable bytes differ from build-binding receipt")
        if not observed["elf_magic"]:
            raise ValueError("final executable is not an ELF file")
        if observed["mode"] & 0o111 == 0:
            raise ValueError("final executable has no execute permission bits")
        return fd, observed, str(path.resolve(strict=True))
    except Exception:
        os.close(fd)
        raise


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    if not path.is_absolute():
        raise ValueError("receipt output path must be absolute")
    parent = path.parent
    if not parent.is_dir():
        raise ValueError("receipt output parent directory does not exist")
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp, path)
        except FileExistsError as exc:
            raise ValueError(f"receipt output already exists: {path}") from exc
        temp.unlink()
        dir_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise


def prepare_launch(
    *,
    final_receipt: dict[str, Any],
    cwd: Path,
    argv: Sequence[bytes],
    environment: Mapping[bytes, bytes],
) -> tuple[dict[str, Any], int, int, dict[bytes, bytes]]:
    """Prepare a READY_TO_EXEC receipt and keep executable/cwd descriptors open."""
    if os.name != "posix" or not Path("/proc/self/stat").exists():
        raise ValueError("pre-exec launch attestation requires Linux procfs")
    if os.execve not in os.supports_fd:
        raise ValueError("this Python/platform cannot execve an open file descriptor")

    env = _validate_environment(environment)
    exe_fd, exe_record, exe_path = _open_final_executable(final_receipt)
    try:
        cwd_fd, cwd_record = _open_bound_cwd(cwd)
    except Exception:
        os.close(exe_fd)
        raise
    try:
        pid = os.getpid()
        starttime = _read_process_starttime()
        body = {
            "schema": SCHEMA,
            "status": "READY_TO_EXEC",
            "implementation_id": IMPLEMENTATION_ID,
            "parent_final_build_receipt_sha256": final_receipt["receipt_sha256"],
            "process": {
                "pid": pid,
                "starttime_ticks": starttime,
                "uid": os.getuid(),
                "euid": os.geteuid(),
                "gid": os.getgid(),
                "egid": os.getegid(),
            },
            "target_executable": {
                "receipt_path": final_receipt["executable"]["path"],
                "resolved_path_at_open": exe_path,
                **exe_record,
            },
            "cwd": cwd_record,
            "argv": _argv_record(argv),
            "environment": _environment_record(env),
            "scientific_scope": "EXACT_PREEXEC_ARGV_ENV_CWD_AND_TARGET_BINDING_ONLY",
            "limitations": [
                "READY_TO_EXEC_IS_NOT_PROOF_EXECVE_SUCCEEDED_RUNTIME_CHILD_REQUIRED",
                "OPEN_EXECUTABLE_FD_PREVENTS_PATH_REBINDING_NOT_INPLACE_INODE_MUTATION",
                "DYNAMIC_LOADER_INTERPRETER_LIBC_CACHE_CONFIG_AND_TOKEN_RESOLUTION_SEPARATE",
                (
                    "FILE_DESCRIPTOR_TABLE_SIGNAL_MASK_RLIMIT_NAMESPACE_AND_"
                    "CREDENTIAL_TRANSITIONS_NOT_BOUND"
                ),
                "ENVIRONMENT_ARRAY_ORDER_NOT_PART_OF_OS_EXECVE_MAPPING_CONTRACT",
                "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_OBSERVABLE_VALIDATED",
            ],
        }
        return _with_digest(body), exe_fd, cwd_fd, env
    except Exception:
        os.close(cwd_fd)
        os.close(exe_fd)
        raise


def launch(
    *,
    final_receipt: dict[str, Any],
    receipt_out: Path,
    cwd: Path,
    argv: Sequence[bytes],
    environment: Mapping[bytes, bytes],
) -> None:
    receipt, exe_fd, cwd_fd, env = prepare_launch(
        final_receipt=final_receipt,
        cwd=cwd,
        argv=argv,
        environment=environment,
    )
    try:
        target_identity = (
            receipt["target_executable"]["bytes"],
            receipt["target_executable"]["sha256"],
        )
        cwd_record = receipt["cwd"]

        os.fchdir(cwd_fd)
        if not _same_directory(cwd_fd, cwd_record):
            raise ValueError("launch cwd changed before exec")

        recheck = _hash_open_regular_fd(
            exe_fd, label="final executable pre-exec recheck"
        )
        if (recheck["bytes"], recheck["sha256"]) != target_identity:
            raise ValueError("final executable changed before exec")

        starttime = _read_process_starttime()
        if (
            starttime != receipt["process"]["starttime_ticks"]
            or os.getpid() != receipt["process"]["pid"]
        ):
            raise ValueError("launcher process identity changed before exec")

        _atomic_write_json(receipt_out, receipt)
        os.execve(exe_fd, list(argv), env)
        raise AssertionError("successful execve unexpectedly returned")
    finally:
        os.close(cwd_fd)
        os.close(exe_fd)


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load {label} JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} JSON must contain an object")
    return value


def _argv_from_cli(values: Sequence[str]) -> list[bytes]:
    if not values:
        raise ValueError("at least one target argv entry is required after --")
    return [os.fsencode(item) for item in values]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-receipt-json", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("target_argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    target_argv = list(args.target_argv)
    if target_argv and target_argv[0] == "--":
        target_argv = target_argv[1:]
    try:
        final_receipt = _load_json_object(
            args.final_receipt_json, label="final build-binding receipt"
        )
        argv = _argv_from_cli(target_argv)
        environment = dict(os.environb)
        launch(
            final_receipt=final_receipt,
            receipt_out=args.receipt_out,
            cwd=args.cwd,
            argv=argv,
            environment=environment,
        )
    except (KeyError, NotImplementedError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
