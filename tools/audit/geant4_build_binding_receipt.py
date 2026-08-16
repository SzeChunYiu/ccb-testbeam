#!/usr/bin/env python3
"""Bind a validated external Geant4 source/input snapshot to a built executable.

This module closes one provenance gap after ``validate_geant4_external_overlay``:
a pre-build source check alone does not show that the source and staged runtime
inputs observed before a build are still the same at build completion.  The
receipt implemented here therefore has two phases:

* ``begin`` validates the exact external baseline/reviewed overlay and records
  same-stream SHA-256/byte-count identities for every declared staged input;
* ``finalize`` validates the external source again, re-hashes every staged
  input, rejects any visible change, and records the resulting executable.

The receipt is self-digested with canonical JSON so accidental/tampered receipt
changes fail closed.  This is a *two-observation integrity contract*, not an
immutable build sandbox: a mutation that occurs after ``begin`` and is restored
before ``finalize`` is not observable here.  Compiler/toolchain identity,
runtime seeds/threading, output identity, and detector validation remain
separate child atoms.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from tools.audit.validate_geant4_external_overlay import validate_external_overlay

BEGIN_SCHEMA = "ccb_geant4_build_binding_begin_v1"
FINAL_SCHEMA = "ccb_geant4_build_binding_final_v1"


def _identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _regular_file_record(path: Path, *, label: str) -> dict[str, Any]:
    """Hash one regular, non-symlink file from one opened byte stream."""
    try:
        lst = path.lstat()
    except OSError as exc:
        raise ValueError(f"cannot inspect {label} file {path}: {exc}") from exc
    if not stat.S_ISREG(lst.st_mode):
        raise ValueError(f"{label} must be a regular non-symlink file: {path}")

    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            count += len(block)
        after = os.fstat(stream.fileno())
    final = path.lstat()

    if _identity(before) != _identity(after) or _identity(after) != _identity(final):
        raise ValueError(f"{label} changed while being hashed: {path}")
    if count != before.st_size:
        raise ValueError(f"short/long read while hashing {label}: {path}")

    return {
        "path": str(path.resolve()),
        "bytes": count,
        "sha256": digest.hexdigest(),
    }


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


def _verify_receipt_digest(receipt: dict[str, Any]) -> None:
    observed = receipt.get("receipt_sha256")
    if not isinstance(observed, str):
        raise ValueError("begin receipt is missing receipt_sha256")
    body = dict(receipt)
    del body["receipt_sha256"]
    expected = _digest_body(body)
    if observed != expected:
        raise ValueError(
            "begin receipt digest mismatch: receipt content changed after creation"
        )


def _source_projection(source: dict[str, Any]) -> dict[str, Any]:
    """Keep source identity fields that must remain invariant across the build."""
    return {
        "baseline": source["baseline"],
        "visible_git_deltas": source["overlay"]["visible_git_deltas"],
        "source_pair": source["overlay"]["source_pair"],
    }


def _normalise_inputs(inputs: Iterable[tuple[str, Path]]) -> list[tuple[str, Path]]:
    result: list[tuple[str, Path]] = []
    labels: set[str] = set()
    resolved_paths: set[Path] = set()
    for label, path in inputs:
        label = label.strip()
        if not label:
            raise ValueError("input label must be non-empty")
        if label in labels:
            raise ValueError(f"duplicate input label: {label}")
        resolved = path.resolve()
        if resolved in resolved_paths:
            raise ValueError(f"same staged input path declared more than once: {resolved}")
        labels.add(label)
        resolved_paths.add(resolved)
        result.append((label, path))
    if not result:
        raise ValueError("at least one staged input is required")
    return sorted(result, key=lambda item: item[0])


def begin_build_binding(
    *,
    external_root: Path,
    repo_root: Path,
    expected_commit: str,
    expected_tree: str,
    inputs: Iterable[tuple[str, Path]],
    build_contract: dict[str, Any],
) -> dict[str, Any]:
    """Record the exact pre-build source and staged-input identities."""
    if not isinstance(build_contract, dict) or not build_contract:
        raise ValueError("build_contract must be a non-empty JSON object")

    source = validate_external_overlay(
        external_root, repo_root, expected_commit, expected_tree
    )
    input_records = []
    for label, path in _normalise_inputs(inputs):
        record = _regular_file_record(path, label=f"staged input {label!r}")
        record["label"] = label
        input_records.append(record)

    body = {
        "schema": BEGIN_SCHEMA,
        "status": "PASS",
        "source": source,
        "staged_inputs": input_records,
        "build_contract": build_contract,
        "scientific_scope": (
            "PREBUILD_SOURCE_AND_INPUT_IDENTITY_ONLY_FINAL_EXECUTABLE_BINDING_REQUIRED"
        ),
    }
    return _with_receipt_digest(body)


def finalize_build_binding(
    *,
    begin_receipt: dict[str, Any],
    external_root: Path,
    repo_root: Path,
    expected_commit: str,
    expected_tree: str,
    inputs: Iterable[tuple[str, Path]],
    executable: Path,
) -> dict[str, Any]:
    """Re-observe source/inputs and bind them to the resulting executable."""
    if begin_receipt.get("schema") != BEGIN_SCHEMA:
        raise ValueError("unsupported or missing begin receipt schema")
    if begin_receipt.get("status") != "PASS":
        raise ValueError("begin receipt is not PASS")
    _verify_receipt_digest(begin_receipt)

    source = validate_external_overlay(
        external_root, repo_root, expected_commit, expected_tree
    )
    if _source_projection(source) != _source_projection(begin_receipt["source"]):
        raise ValueError("external source identity changed between begin and finalize")

    current_inputs = []
    for label, path in _normalise_inputs(inputs):
        record = _regular_file_record(path, label=f"staged input {label!r}")
        record["label"] = label
        current_inputs.append(record)
    if current_inputs != begin_receipt["staged_inputs"]:
        raise ValueError("staged input identity changed between begin and finalize")

    executable_record = _regular_file_record(executable, label="built executable")
    begin_digest = begin_receipt["receipt_sha256"]
    body = {
        "schema": FINAL_SCHEMA,
        "status": "PASS",
        "begin_receipt_sha256": begin_digest,
        "source": source,
        "staged_inputs": current_inputs,
        "build_contract": begin_receipt["build_contract"],
        "executable": executable_record,
        "limitations": [
            "TWO_OBSERVATION_CHECK_CANNOT_EXCLUDE_TRANSIENT_MUTATE_AND_RESTORE",
            "TOOLCHAIN_IDENTITY_NOT_YET_INDEPENDENTLY_ATTESTED",
            "RUNTIME_SEED_THREAD_EVENT_OUTPUT_PROVENANCE_NOT_INCLUDED",
        ],
        "scientific_scope": (
            "BUILD_SOURCE_INPUT_EXECUTABLE_IDENTITY_ONLY_RUNTIME_VALIDATION_REQUIRED"
        ),
    }
    return _with_receipt_digest(body)


def _parse_input(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if not separator or not label or not path:
        raise argparse.ArgumentTypeError("input must have form LABEL=PATH")
    return label, Path(path)


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
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--external-root", type=Path, required=True)
        subparser.add_argument("--repo-root", type=Path, default=Path("."))
        subparser.add_argument("--expected-commit", required=True)
        subparser.add_argument("--expected-tree", required=True)
        subparser.add_argument("--input", type=_parse_input, action="append", required=True)

    begin = subparsers.add_parser("begin")
    add_common(begin)
    begin.add_argument("--build-contract-json", type=Path, required=True)

    finalize = subparsers.add_parser("finalize")
    add_common(finalize)
    finalize.add_argument("--begin-receipt-json", type=Path, required=True)
    finalize.add_argument("--executable", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "begin":
            result = begin_build_binding(
                external_root=args.external_root,
                repo_root=args.repo_root,
                expected_commit=args.expected_commit,
                expected_tree=args.expected_tree,
                inputs=args.input,
                build_contract=_load_json_object(
                    args.build_contract_json, label="build contract"
                ),
            )
        else:
            result = finalize_build_binding(
                begin_receipt=_load_json_object(
                    args.begin_receipt_json, label="begin receipt"
                ),
                external_root=args.external_root,
                repo_root=args.repo_root,
                expected_commit=args.expected_commit,
                expected_tree=args.expected_tree,
                inputs=args.input,
                executable=args.executable,
            )
    except (KeyError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
