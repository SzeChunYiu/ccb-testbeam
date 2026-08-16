#!/usr/bin/env python3
"""Bind Linux dynamic-loader secure-execution state to runtime receipts.

This bounded provenance primitive composes an existing live runtime-dependency
receipt with the same-process runtime/ELF co-observation receipt, then reads the
process auxiliary vector while the process start-time identity is held stable.
It records the kernel-provided AT_SECURE value and the launch UID/GID auxiliary
entries needed to interpret whether loader-control environment variables may be
scientifically treated as eligible search inputs.

It does not reconstruct the complete historical loader search decision, prove
initial working directory, parse ld.so.cache/config, bind hwcaps/token
expansion, or validate any Geant4 physics observable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_loader_secure_state_attestation_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"
COOBS_RECEIPT_SCHEMA = "ccb_geant4_runtime_link_coobservation_v1"

AT_NULL = 0
AT_UID = 11
AT_EUID = 12
AT_GID = 13
AT_EGID = 14
AT_SECURE = 23

SECURITY_RELEVANT_ENV = ("LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT")


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


def parse_auxv_elf64_le(payload: bytes) -> dict[int, int]:
    """Parse Linux /proc/PID/auxv for the already-attested ELF64 LE process."""
    entry_size = 16
    if not payload or len(payload) % entry_size != 0:
        raise ValueError("process auxv length is not a nonzero multiple of ELF64 entries")
    result: dict[int, int] = {}
    seen_null = False
    for offset in range(0, len(payload), entry_size):
        key, value = struct.unpack_from("<QQ", payload, offset)
        if seen_null:
            if key != AT_NULL or value != 0:
                raise ValueError("nonzero auxiliary-vector entry follows AT_NULL")
            continue
        if key == AT_NULL:
            if value != 0:
                raise ValueError("AT_NULL auxiliary-vector value must be zero")
            seen_null = True
            continue
        if key in result:
            raise ValueError(f"duplicate auxiliary-vector key: {key}")
        result[key] = value
    if not seen_null:
        raise ValueError("process auxv has no AT_NULL terminator")
    return result


def _process_identity(receipt: dict[str, Any], *, label: str) -> tuple[int, int]:
    process = receipt.get("process")
    if not isinstance(process, dict):
        raise ValueError(f"{label} has no process record")
    pid = process.get("pid")
    starttime = process.get("starttime_ticks")
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError(f"{label} pid is invalid")
    if not isinstance(starttime, int) or starttime < 0:
        raise ValueError(f"{label} starttime is invalid")
    return pid, starttime


def _env_utf8(runtime_receipt: dict[str, Any], key: str) -> str | None:
    env = runtime_receipt.get("loader_environment")
    if not isinstance(env, dict):
        raise ValueError("runtime receipt has no loader_environment record")
    record = env.get(key)
    if not isinstance(record, dict):
        raise ValueError(f"runtime receipt does not track loader environment key {key}")
    present = record.get("present")
    if present is False:
        return None
    if present is not True:
        raise ValueError(f"runtime loader environment key {key} has invalid presence state")
    value = record.get("utf8")
    if value is None:
        raise ValueError(f"runtime loader environment key {key} is not UTF-8")
    if not isinstance(value, str):
        raise ValueError(f"runtime loader environment key {key} has invalid utf8 value")
    return value


def attest_loader_secure_state(
    *,
    runtime_receipt: dict[str, Any],
    coobservation_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Attest the secure-execution input that governs loader-env semantics."""
    _verify_receipt(
        runtime_receipt,
        schema=RUNTIME_RECEIPT_SCHEMA,
        label="runtime dependency receipt",
    )
    _verify_receipt(
        coobservation_receipt,
        schema=COOBS_RECEIPT_SCHEMA,
        label="runtime link co-observation receipt",
    )
    if (
        coobservation_receipt.get("parent_runtime_dependency_receipt_sha256")
        != runtime_receipt["receipt_sha256"]
    ):
        raise ValueError("co-observation receipt belongs to another runtime receipt")

    pid, expected_starttime = _process_identity(runtime_receipt, label="runtime receipt")
    co_pid, co_starttime = _process_identity(
        coobservation_receipt, label="co-observation receipt"
    )
    if (co_pid, co_starttime) != (pid, expected_starttime):
        raise ValueError("runtime and co-observation receipts identify different processes")

    proc_dir = proc_root / str(pid)
    start_before = _read_process_starttime(proc_dir)
    if start_before != expected_starttime:
        raise ValueError("process identity differs from attested runtime process")
    auxv_payload = _read_proc_bytes(proc_dir, "auxv", label="process auxiliary vector")
    auxv = parse_auxv_elf64_le(auxv_payload)
    start_after = _read_process_starttime(proc_dir)
    if start_after != start_before:
        raise ValueError("process identity changed while reading auxiliary vector")

    if AT_SECURE not in auxv:
        raise ValueError("process auxiliary vector is missing AT_SECURE")
    at_secure = auxv[AT_SECURE]
    if at_secure not in (0, 1):
        raise ValueError(f"AT_SECURE is not boolean: {at_secure}")

    launch_ids = {
        "uid": auxv.get(AT_UID),
        "euid": auxv.get(AT_EUID),
        "gid": auxv.get(AT_GID),
        "egid": auxv.get(AT_EGID),
    }
    environment_semantics: dict[str, dict[str, Any]] = {}
    for key in SECURITY_RELEVANT_ENV:
        value = _env_utf8(runtime_receipt, key)
        environment_semantics[key] = {
            "present_in_runtime_receipt": value is not None,
            "kernel_at_secure": at_secure,
            "interpretation": (
                "RESTRICTED_OR_IGNORED_DO_NOT_USE_AS_LOADER_SEARCH_AUTHORITY"
                if at_secure
                else (
                    "UNRESOLVED_DO_NOT_USE_AS_LOADER_SEARCH_AUTHORITY_"
                    "UNTIL_PRE_EXEC_STATE_IS_BOUND"
                )
            ),
        }

    effective_state = (
        "SECURE_CONFIRMED_BY_KERNEL_AT_SECURE"
        if at_secure
        else "UNRESOLVED_KERNEL_AT_SECURE_ZERO"
    )

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_runtime_dependency_receipt_sha256": runtime_receipt["receipt_sha256"],
        "parent_runtime_link_coobservation_receipt_sha256": coobservation_receipt[
            "receipt_sha256"
        ],
        "process": {
            "pid": pid,
            "starttime_ticks": start_before,
        },
        "auxv": {
            "encoding": "ELF64_LITTLE_ENDIAN_U64_PAIRS",
            "sha256": hashlib.sha256(auxv_payload).hexdigest(),
            "bytes": len(auxv_payload),
            "at_secure": at_secure,
            "launch_ids": launch_ids,
        },
        "effective_loader_secure_state": effective_state,
        "loader_environment_semantics": environment_semantics,
        "scientific_scope": "LINUX_DYNAMIC_LOADER_SECURE_EXECUTION_STATE_ONLY",
        "limitations": [
            "AT_SECURE_ONE_CONFIRMS_KERNEL_SECURE_EXECUTION_BUT_ZERO_DOES_NOT_"
            "EXCLUDE_LIBC_ENABLE_SECURE",
            "POST_START_ENVIRONMENT_CANNOT_PROVE_PRE_EXEC_GLIBC_TUNABLES_AFTER_LOADER_SANITIZATION",
            "INITIAL_WORKING_DIRECTORY_NOT_BOUND",
            "LD_SO_CACHE_AND_CONFIGURATION_NOT_BOUND",
            "ORIGIN_LIB_PLATFORM_TOKEN_EXPANSION_NOT_BOUND",
            "GLIBC_HWCAPS_SEARCH_NOT_BOUND",
            "PRELOAD_AUDIT_OBJECT_CONTENT_AND_ORDER_NOT_BOUND",
            "LATE_DLOPEN_OR_UNLOAD_NOT_BOUND",
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
    parser.add_argument("--coobservation-receipt-json", type=Path, required=True)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    args = parser.parse_args()
    try:
        result = attest_loader_secure_state(
            runtime_receipt=_load_json_object(
                args.runtime_receipt_json, label="runtime dependency receipt"
            ),
            coobservation_receipt=_load_json_object(
                args.coobservation_receipt_json,
                label="runtime link co-observation receipt",
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
