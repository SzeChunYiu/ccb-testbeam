#!/usr/bin/env python3
"""Attest a stable Linux /proc/PID/environ initial-environment snapshot.

This bounded provenance primitive composes the live runtime-dependency receipt
with its loader secure-state child, then re-observes ``/proc/<pid>/environ``
while process identity remains stable. Linux procfs defines that file as the
initial environment region associated with the currently executing image, not
as a generic view of later ``setenv``/``putenv`` changes.

The receipt deliberately does *not* claim an immutable historical ``execve``
envp: the target may overwrite or relocate that environment region after exec.
Presence is therefore direct evidence at the attestation boundary; absence is
not promoted to proof that a variable was absent at exec. Explicit dynamic
loader command-line options, loader/cache configuration, token expansion and
late ``dlopen`` activity are separate atoms.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_loader_initial_environment_attestation_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"
SECURE_RECEIPT_SCHEMA = "ccb_geant4_loader_secure_state_attestation_v1"
SECURITY_RELEVANT_ENV = (
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "LD_AUDIT",
    "GLIBC_TUNABLES",
)


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


def _tracked_environment(payload: bytes, keys: set[str]) -> dict[str, bytes | None]:
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
        if name not in keys:
            continue
        if name in seen:
            raise ValueError(f"duplicate tracked initial-environment key: {name}")
        seen[name] = value
    return {key: seen.get(key) for key in sorted(keys)}


def _receipt_environment_values(runtime_receipt: dict[str, Any]) -> dict[str, bytes | None]:
    env = runtime_receipt.get("loader_environment")
    if not isinstance(env, dict) or not env:
        raise ValueError("runtime receipt has no loader_environment record")
    result: dict[str, bytes | None] = {}
    for key, record in env.items():
        if not isinstance(key, str) or not key:
            raise ValueError("runtime receipt has invalid loader environment key")
        try:
            key.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("runtime loader environment key must be ASCII") from exc
        if not isinstance(record, dict):
            raise ValueError(f"runtime loader environment key {key} has invalid record")
        present = record.get("present")
        if present is False:
            result[key] = None
            continue
        if present is not True:
            raise ValueError(f"runtime loader environment key {key} has invalid presence")
        encoded = record.get("base64")
        if not isinstance(encoded, str):
            raise ValueError(f"runtime loader environment key {key} lacks base64 bytes")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError(f"runtime loader environment key {key} has invalid base64") from exc
        expected_bytes = record.get("bytes")
        expected_sha = record.get("sha256")
        if expected_bytes != len(raw):
            raise ValueError(f"runtime loader environment key {key} byte count mismatch")
        if expected_sha != hashlib.sha256(raw).hexdigest():
            raise ValueError(f"runtime loader environment key {key} digest mismatch")
        result[key] = raw
    return result


def attest_loader_initial_environment(
    *,
    runtime_receipt: dict[str, Any],
    secure_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Bind a stable procfs initial-environment-region observation."""
    _verify_receipt(
        runtime_receipt,
        schema=RUNTIME_RECEIPT_SCHEMA,
        label="runtime dependency receipt",
    )
    _verify_receipt(
        secure_receipt,
        schema=SECURE_RECEIPT_SCHEMA,
        label="loader secure-state receipt",
    )
    if (
        secure_receipt.get("parent_runtime_dependency_receipt_sha256")
        != runtime_receipt["receipt_sha256"]
    ):
        raise ValueError("secure-state receipt belongs to another runtime receipt")

    pid, expected_starttime = _process_identity(runtime_receipt, label="runtime receipt")
    secure_pid, secure_starttime = _process_identity(
        secure_receipt, label="secure-state receipt"
    )
    if (secure_pid, secure_starttime) != (pid, expected_starttime):
        raise ValueError("runtime and secure-state receipts identify different processes")

    receipt_values = _receipt_environment_values(runtime_receipt)
    tracked_keys = set(receipt_values)
    proc_dir = proc_root / str(pid)
    start_before = _read_process_starttime(proc_dir)
    if start_before != expected_starttime:
        raise ValueError("process identity differs from attested runtime process")

    environ_before = _read_proc_bytes(
        proc_dir, "environ", label="process initial environment region"
    )
    observed_values = _tracked_environment(environ_before, tracked_keys)
    for key in sorted(tracked_keys):
        if observed_values[key] != receipt_values[key]:
            raise ValueError(
                f"initial-environment value differs from runtime receipt for {key}"
            )

    environ_after = _read_proc_bytes(
        proc_dir, "environ", label="process initial environment region recheck"
    )
    if environ_after != environ_before:
        raise ValueError("process initial environment region changed during attestation")
    start_after = _read_process_starttime(proc_dir)
    if start_after != start_before:
        raise ValueError("process identity changed during initial-environment attestation")

    auxv = secure_receipt.get("auxv")
    if not isinstance(auxv, dict):
        raise ValueError("secure-state receipt has no auxv record")
    at_secure = auxv.get("at_secure")
    if at_secure not in (0, 1):
        raise ValueError("secure-state receipt has invalid AT_SECURE")

    key_semantics: dict[str, dict[str, Any]] = {}
    for key in sorted(tracked_keys):
        present = observed_values[key] is not None
        record: dict[str, Any] = {
            "present_in_stable_proc_initial_environment_region": present,
            "presence_inference": (
                "OBSERVED_AT_ATTESTATION_BOUNDARY"
                if present
                else "ABSENT_AT_OBSERVATION_NOT_PROOF_OF_EXECVE_ABSENCE"
            ),
        }
        if key in SECURITY_RELEVANT_ENV:
            if at_secure == 1 and key in {"LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT"}:
                record["loader_search_interpretation"] = (
                    "KERNEL_SECURE_MODE_RESTRICTS_OR_IGNORES_ENV_INPUT"
                )
            elif at_secure == 0:
                record["loader_search_interpretation"] = (
                    "KERNEL_ZERO_ENV_REGION_EVIDENCE_ONLY_EFFECTIVE_LOADER_DECISION_UNRESOLVED"
                )
            else:
                record["loader_search_interpretation"] = (
                    "RECORDED_ENV_REGION_EVIDENCE_ONLY"
                )
        key_semantics[key] = record

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_runtime_dependency_receipt_sha256": runtime_receipt["receipt_sha256"],
        "parent_loader_secure_state_receipt_sha256": secure_receipt["receipt_sha256"],
        "process": {"pid": pid, "starttime_ticks": start_before},
        "proc_initial_environment": {
            "source": "/proc/<pid>/environ",
            "kernel_contract": "INITIAL_ENVIRONMENT_REGION_FOR_CURRENT_EXECUTING_IMAGE",
            "bytes": len(environ_before),
            "sha256": hashlib.sha256(environ_before).hexdigest(),
            "stable_across_attestation": True,
        },
        "tracked_key_semantics": key_semantics,
        "scientific_scope": "LINUX_PROCFS_INITIAL_ENVIRONMENT_REGION_OBSERVATION_ONLY",
        "limitations": [
            "TARGET_CAN_OVERWRITE_INITIAL_ENVIRONMENT_BYTES_AFTER_EXEC",
            "TARGET_CAN_RELOCATE_PROC_ENVIRONMENT_REGION_WITH_PR_SET_MM",
            "ABSENCE_AT_OBSERVATION_IS_NOT_IMMUTABLE_EXECVE_ABSENCE_PROOF",
            "EXPLICIT_DYNAMIC_LOADER_COMMAND_LINE_OPTIONS_NOT_BOUND",
            "EXACT_LIBC_LOADER_BUILD_AND_TUNABLE_SEMANTICS_NOT_BOUND_BY_THIS_RECEIPT",
            "INITIAL_WORKING_DIRECTORY_NOT_BOUND",
            "LD_SO_CACHE_AND_CONFIGURATION_NOT_BOUND",
            "TOKEN_AND_GLIBC_HWCAPS_EXPANSION_NOT_BOUND",
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
    parser.add_argument("--secure-receipt-json", type=Path, required=True)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    args = parser.parse_args()
    try:
        result = attest_loader_initial_environment(
            runtime_receipt=_load_json_object(
                args.runtime_receipt_json, label="runtime dependency receipt"
            ),
            secure_receipt=_load_json_object(
                args.secure_receipt_json, label="loader secure-state receipt"
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
