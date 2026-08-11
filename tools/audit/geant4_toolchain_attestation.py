#!/usr/bin/env python3
"""Attest the CMake-selected Geant4 build toolchain from measured local state.

This is a bounded provenance primitive. It verifies a final
``ccb_geant4_build_binding_final_v1`` receipt, re-hashes the bound executable,
reads ``CMakeCache.txt`` from one regular byte stream, and independently records
the CMake-selected C++ compiler, CMake command, generator, requested cache
entries, and package-config sentinel files.

The result is evidence about the configured build tree at the observation
boundary. It does not prove that every compiler invocation consumed an
immutable source snapshot, that the measured dynamic libraries were the ones
loaded at runtime, or that any Geant4 physics observable is correct.
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

SCHEMA = "ccb_geant4_cmake_toolchain_attestation_v1"
FINAL_RECEIPT_SCHEMA = "ccb_geant4_build_binding_final_v1"
MAX_PROBE_BYTES = 65536


def _identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
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
    expected = _digest_body(body)
    if observed != expected:
        raise ValueError(f"{label} digest mismatch")


def _read_regular_bytes(path: Path, *, label: str) -> tuple[bytes, dict[str, Any]]:
    """Read one regular non-symlink file once and bind bytes to file identity."""
    try:
        lst = path.lstat()
    except OSError as exc:
        raise ValueError(f"cannot inspect {label} {path}: {exc}") from exc
    if not stat.S_ISREG(lst.st_mode):
        raise ValueError(f"{label} must be a regular non-symlink file: {path}")

    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        payload = stream.read()
        after = os.fstat(stream.fileno())
    final = path.lstat()

    if _identity(before) != _identity(after) or _identity(after) != _identity(final):
        raise ValueError(f"{label} changed while being read: {path}")
    if len(payload) != before.st_size:
        raise ValueError(f"short/long read while reading {label}: {path}")

    record = {
        "path": str(path.resolve()),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    return payload, record


def _resolved_file_record(path: Path, *, label: str) -> dict[str, Any]:
    """Record a path plus the regular file reached after symlink resolution."""
    try:
        original = path.lstat()
        resolved = path.resolve(strict=True)
        resolved_lstat = resolved.lstat()
    except OSError as exc:
        raise ValueError(f"cannot resolve {label} {path}: {exc}") from exc

    if not stat.S_ISREG(resolved_lstat.st_mode):
        raise ValueError(f"{label} must resolve to a regular file: {path}")

    _, record = _read_regular_bytes(resolved, label=f"resolved {label}")
    result = {
        "path": str(path.absolute()),
        "resolved_path": str(resolved),
        "resolved_bytes": record["bytes"],
        "resolved_sha256": record["sha256"],
        "path_is_symlink": stat.S_ISLNK(original.st_mode),
    }
    if stat.S_ISLNK(original.st_mode):
        result["symlink_target"] = os.readlink(path)
    return result


def _parse_cmake_cache_bytes(payload: bytes) -> dict[str, list[dict[str, str]]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"CMake cache is not valid UTF-8: {exc}") from exc

    entries: dict[str, list[dict[str, str]]] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        left, sep, value = raw_line.partition("=")
        if not sep:
            continue
        key, colon, value_type = left.partition(":")
        if not colon or not key:
            continue
        entries.setdefault(key, []).append(
            {"type": value_type, "value": value, "line": str(line_number)}
        )
    return entries


def _require_cache_entry(
    entries: dict[str, list[dict[str, str]]], key: str
) -> dict[str, str]:
    matches = entries.get(key, [])
    if not matches:
        raise ValueError(f"required CMake cache key is missing: {key}")
    if len(matches) != 1:
        lines = ",".join(item["line"] for item in matches)
        raise ValueError(f"duplicate CMake cache key {key} at lines {lines}")
    entry = matches[0]
    value = entry["value"]
    if not value or value.endswith("-NOTFOUND"):
        raise ValueError(f"required CMake cache key is unresolved: {key}={value!r}")
    return entry


def _cmake_list_first(value: str, *, key: str) -> tuple[str, list[str]]:
    if "\\;" in value:
        raise ValueError(
            f"{key} uses an escaped semicolon; this attestor will not guess "
            "CMake-list escaping"
        )
    parts = value.split(";")
    if not parts[0]:
        raise ValueError(f"{key} has an empty executable element")
    if any(part == "" for part in parts[1:]):
        raise ValueError(f"{key} has an empty implicit-argument element")
    return parts[0], parts[1:]


def _probe_tool(path: Path, *, label: str) -> dict[str, Any]:
    executable = _resolved_file_record(path, label=label)
    resolved = Path(executable["resolved_path"])
    if not os.access(resolved, os.X_OK):
        raise ValueError(f"{label} is not executable: {resolved}")
    try:
        proc = subprocess.run(
            [str(path), "--version"],
            check=False,
            capture_output=True,
            timeout=30,
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

    executable["probe_argv"] = [str(path), "--version"]
    executable["probe_returncode"] = proc.returncode
    executable["probe_stdout"] = proc.stdout.decode("utf-8", errors="replace")
    executable["probe_stderr"] = proc.stderr.decode("utf-8", errors="replace")
    executable["probe_stdout_sha256"] = hashlib.sha256(proc.stdout).hexdigest()
    executable["probe_stderr_sha256"] = hashlib.sha256(proc.stderr).hexdigest()
    return executable


def _normalise_package_specs(
    package_specs: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    if not package_specs:
        raise ValueError("at least one package sentinel is required")
    labels: set[str] = set()
    result: list[tuple[str, str, str]] = []
    for label, cache_key, relative_path in package_specs:
        label = label.strip()
        cache_key = cache_key.strip()
        if not label or not cache_key or not relative_path:
            raise ValueError("package label, cache key, and relative path must be non-empty")
        if label in labels:
            raise ValueError(f"duplicate package label: {label}")
        rel = Path(relative_path)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(
                f"package sentinel must stay below its cache root: {relative_path}"
            )
        labels.add(label)
        result.append((label, cache_key, relative_path))
    return sorted(result)


def attest_cmake_toolchain(
    *,
    final_receipt: dict[str, Any],
    cmake_cache: Path,
    required_cache_keys: list[str],
    package_specs: list[tuple[str, str, str]],
) -> dict[str, Any]:
    """Create a content-bound attestation of the configured CMake toolchain."""
    if final_receipt.get("schema") != FINAL_RECEIPT_SCHEMA:
        raise ValueError("unsupported or missing final build-binding receipt schema")
    if final_receipt.get("status") != "PASS":
        raise ValueError("final build-binding receipt is not PASS")
    _verify_receipt_digest(final_receipt, label="final build-binding receipt")

    executable_path = Path(final_receipt["executable"]["path"])
    _, executable_now = _read_regular_bytes(
        executable_path, label="build-binding executable"
    )
    if executable_now != final_receipt["executable"]:
        raise ValueError(
            "bound executable identity changed after final build-binding receipt"
        )

    cache_payload, cache_record = _read_regular_bytes(
        cmake_cache, label="CMakeCache.txt"
    )
    entries = _parse_cmake_cache_bytes(cache_payload)

    mandatory_keys = ["CMAKE_COMMAND", "CMAKE_CXX_COMPILER", "CMAKE_GENERATOR"]
    requested_keys: list[str] = []
    seen: set[str] = set()
    for key in [*mandatory_keys, *required_cache_keys]:
        key = key.strip()
        if not key:
            raise ValueError("required cache key must be non-empty")
        if key not in seen:
            seen.add(key)
            requested_keys.append(key)

    selected_cache = {
        key: _require_cache_entry(entries, key) for key in requested_keys
    }

    cmake_raw = selected_cache["CMAKE_COMMAND"]["value"]
    cmake_path_string, cmake_implicit = _cmake_list_first(
        cmake_raw, key="CMAKE_COMMAND"
    )
    if cmake_implicit:
        raise ValueError("CMAKE_COMMAND unexpectedly contains implicit arguments")
    cmake_path = Path(cmake_path_string)
    if not cmake_path.is_absolute():
        raise ValueError("CMAKE_COMMAND must be an absolute path for attestation")

    cxx_raw = selected_cache["CMAKE_CXX_COMPILER"]["value"]
    cxx_path_string, cxx_implicit = _cmake_list_first(
        cxx_raw, key="CMAKE_CXX_COMPILER"
    )
    cxx_path = Path(cxx_path_string)
    if not cxx_path.is_absolute():
        raise ValueError("CMAKE_CXX_COMPILER must resolve to an absolute path")

    tools = {
        "cmake": _probe_tool(cmake_path, label="CMake command"),
        "cxx_compiler": _probe_tool(cxx_path, label="C++ compiler"),
    }
    tools["cxx_compiler"]["cmake_implicit_args"] = cxx_implicit

    packages: list[dict[str, Any]] = []
    for label, cache_key, relative_path in _normalise_package_specs(package_specs):
        entry = _require_cache_entry(entries, cache_key)
        root = Path(entry["value"])
        if not root.is_absolute():
            raise ValueError(
                f"package cache root {cache_key} must be absolute: {entry['value']!r}"
            )
        sentinel = _resolved_file_record(
            root / relative_path, label=f"package sentinel {label!r}"
        )
        packages.append(
            {
                "label": label,
                "cache_key": cache_key,
                "cache_type": entry["type"],
                "cache_root": entry["value"],
                "relative_path": relative_path,
                "sentinel": sentinel,
            }
        )

    body = {
        "schema": SCHEMA,
        "status": "PASS",
        "final_build_binding_receipt_sha256": final_receipt["receipt_sha256"],
        "executable": executable_now,
        "cmake_cache": cache_record,
        "selected_cache_entries": selected_cache,
        "tools": tools,
        "packages": packages,
        "scientific_scope": (
            "CMAKE_CONFIGURED_TOOLCHAIN_AND_PACKAGE_SENTINEL_IDENTITY_ONLY"
        ),
        "limitations": [
            "CMAKE_CONFIGURATION_STATE_DOES_NOT_PROVE_EVERY_TOOL_INVOCATION",
            "TRANSIENT_SOURCE_OR_INPUT_MUTATION_DURING_BUILD_REMAINS_UNOBSERVED",
            "DYNAMIC_LIBRARY_LOAD_IDENTITY_NOT_YET_ATTESTED",
            "RUNTIME_RANDOM_THREAD_EVENT_OUTPUT_PROVENANCE_NOT_INCLUDED",
            "NO_GEANT4_PHYSICS_OBSERVABLE_VALIDATED",
        ],
    }
    return _with_receipt_digest(body)


def _parse_package(value: str) -> tuple[str, str, str]:
    label, eq, remainder = value.partition("=")
    cache_key, colon, relative_path = remainder.partition(":")
    if not eq or not colon or not label or not cache_key or not relative_path:
        raise argparse.ArgumentTypeError(
            "package must have form LABEL=CACHE_KEY:RELATIVE_SENTINEL"
        )
    return label, cache_key, relative_path


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
    parser.add_argument("--final-receipt-json", type=Path, required=True)
    parser.add_argument("--cmake-cache", type=Path, required=True)
    parser.add_argument("--require-cache-key", action="append", default=[])
    parser.add_argument("--package", type=_parse_package, action="append", required=True)
    args = parser.parse_args()

    try:
        result = attest_cmake_toolchain(
            final_receipt=_load_json_object(
                args.final_receipt_json, label="final build-binding receipt"
            ),
            cmake_cache=args.cmake_cache,
            required_cache_keys=args.require_cache_key,
            package_specs=args.package,
        )
    except (KeyError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
