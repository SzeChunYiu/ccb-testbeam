#!/usr/bin/env python3
"""Attest a stable Linux /proc/PID/cmdline argument-region snapshot.

This bounded provenance primitive composes a validated live-runtime receipt
with a same-process observation of ``/proc/<pid>/cmdline``.  The raw bytes and
per-argument bytes are preserved exactly.  Linux procfs does not make these
bytes an immutable historical ``execve(argv)`` log: a process can rewrite the
argument strings and, with ``PR_SET_MM_ARG_START/END``, can relocate the region
that procfs exposes.

The receipt therefore means only that two consecutive command-line reads were
byte-equal at the attestation boundary; an ABA mutation between reads is not
excluded.  ``argv[0]`` is not used as executable
identity; the parent runtime receipt's content-bound ``/proc/<pid>/exe``
observation remains authoritative for that separate question.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_loader_argv_attestation_v1"
RUNTIME_RECEIPT_SCHEMA = "ccb_geant4_runtime_dependency_attestation_v1"


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


def _verify_runtime_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != RUNTIME_RECEIPT_SCHEMA:
        raise ValueError("runtime dependency receipt has unsupported schema")
    if receipt.get("status") != "PASS":
        raise ValueError("runtime dependency receipt is not PASS")
    observed = receipt.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError("runtime dependency receipt is missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    if _digest_body(body) != observed:
        raise ValueError("runtime dependency receipt digest mismatch")


def _runtime_process_identity(receipt: dict[str, Any]) -> tuple[int, int, str]:
    process = receipt.get("process")
    if not isinstance(process, dict):
        raise ValueError("runtime dependency receipt has no process record")
    pid = process.get("pid")
    starttime = process.get("starttime_ticks")
    exe_link = process.get("exe_link")
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("runtime dependency receipt pid is invalid")
    if not isinstance(starttime, int) or starttime < 0:
        raise ValueError("runtime dependency receipt starttime is invalid")
    if not isinstance(exe_link, str) or not exe_link:
        raise ValueError("runtime dependency receipt exe_link is invalid")
    if exe_link.endswith(" (deleted)"):
        raise ValueError("runtime dependency receipt executable is deleted")
    return pid, starttime, exe_link


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


def _parse_argument_region(payload: bytes) -> list[bytes]:
    if not payload:
        raise ValueError("process command-line region is empty")
    slots = payload.split(b"\0")
    if payload.endswith(b"\0"):
        slots = slots[:-1]
    if not slots:
        raise ValueError("process command-line region contains no NUL-delimited slots")
    return slots


def attest_loader_argv(
    *,
    runtime_receipt: dict[str, Any],
    proc_root: Path = Path("/proc"),
) -> dict[str, Any]:
    """Bind one stable process-visible Linux argument-region observation."""
    _verify_runtime_receipt(runtime_receipt)
    pid, expected_starttime, expected_exe_link = _runtime_process_identity(runtime_receipt)
    proc_dir = proc_root / str(pid)

    start_before = _read_process_starttime(proc_dir)
    if start_before != expected_starttime:
        raise ValueError("process identity differs from runtime dependency receipt")
    exe_before = _read_exe_link(proc_dir)
    if exe_before != expected_exe_link:
        raise ValueError("process executable link differs from runtime dependency receipt")

    cmdline_before = _read_proc_bytes(proc_dir, "cmdline", label="process command line")
    slots = _parse_argument_region(cmdline_before)
    cmdline_after = _read_proc_bytes(
        proc_dir, "cmdline", label="process command line recheck"
    )
    if cmdline_after != cmdline_before:
        raise ValueError("process command-line region changed during attestation")

    start_after = _read_process_starttime(proc_dir)
    if start_after != start_before:
        raise ValueError("process identity changed during command-line attestation")
    exe_after = _read_exe_link(proc_dir)
    if exe_after != exe_before:
        raise ValueError("process executable link changed during command-line attestation")

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "parent_runtime_dependency_receipt_sha256": runtime_receipt["receipt_sha256"],
        "process": {
            "pid": pid,
            "starttime_ticks": start_before,
            "exe_link": exe_before,
        },
        "cmdline_region": {
            **_byte_record(cmdline_before),
            "trailing_nul_observed": cmdline_before.endswith(b"\0"),
            "nul_delimited_slot_count_observed": len(slots),
            "nul_delimited_slots": [
                {"index": index, **_byte_record(slot)}
                for index, slot in enumerate(slots)
            ],
        },
        "scientific_scope": "STABLE_PROCFS_ARGUMENT_REGION_OBSERVATION_ONLY",
        "interpretation": {
            "observation": "TWO_CONSECUTIVE_READS_BYTE_EQUAL_NOT_CONTINUOUS_STABILITY",
            "slot_semantics": "NUL_DELIMITER_INTERPRETATION_NOT_PROVEN_ARGV",
            "historical_execve_argv": "NOT_PROVEN_ARGUMENT_REGION_IS_MUTABLE",
            "argv0_executable_identity": (
                "NOT_AUTHORITATIVE_PARENT_PROC_EXE_CONTENT_IDENTITY_IS_SEPARATE"
            ),
            "explicit_loader_invocation": (
                "PARENT_RUNTIME_RECEIPT_BINDS_PROC_EXE_TO_FINAL_BUILD_EXECUTABLE"
            ),
        },
        "limitations": [
            "ARGV_STRINGS_CAN_BE_REWRITTEN_AFTER_EXECVE",
            "ABA_MUTATION_BETWEEN_EQUAL_READS_NOT_EXCLUDED",
            "PROCFS_CMDLINE_FORMAT_CAN_BE_OVERWRITTEN_SLOT_COUNT_IS_NOT_PROVEN_ARGC",
            "PR_SET_MM_ARG_START_END_CAN_RELOCATE_PROCFS_ARGUMENT_REGION",
            "PR_SET_MM_EXE_FILE_MUTATION_NOT_EXCLUDED_BY_THIS_CHILD",
            "RELATIVE_ARGUMENT_PATHS_REQUIRE_INITIAL_CWD_ATTESTATION",
            "ARGUMENT_SEMANTICS_CONFIG_MACRO_OUTPUT_REQUIRE_VERSIONED_RUN_CONTRACT",
            "NO_GEANT4_EVENT_SOURCE_TRANSPORT_OR_DETECTOR_OBSERVABLE_VALIDATED",
        ],
    }
    return _with_digest(body)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load runtime receipt JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("runtime receipt JSON must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-receipt-json", type=Path, required=True)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    args = parser.parse_args()
    try:
        result = attest_loader_argv(
            runtime_receipt=_load_json_object(args.runtime_receipt_json),
            proc_root=args.proc_root,
        )
    except (KeyError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
