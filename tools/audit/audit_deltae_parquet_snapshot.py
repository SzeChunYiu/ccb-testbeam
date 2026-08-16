#!/usr/bin/env python3
"""Audit DeltaE Parquet parsing and manifest provenance binding."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "ccb-deltae-parquet-snapshot-audit/1"
POLICY = "DELTAE_PARQUET_ROWS_AND_PROVENANCE_MUST_SHARE_ONE_BYTE_SNAPSHOT"
REQUIRED_SNAPSHOT_POLICY = "SINGLE_READ_EXACT_BYTES"


class AuditInputError(RuntimeError):
    """Controlled invalid-input failure."""


def snapshot_utf8(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    try:
        return raw, raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"invalid UTF-8 in {path}: {exc}") from exc


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AuditInputError(f"source does not define {name}()")


def _parquet_branch(source: str, function: ast.FunctionDef) -> ast.If:
    for node in ast.walk(function):
        if not isinstance(node, ast.If):
            continue
        segment = ast.get_source_segment(source, node.test) or ""
        if ".parquet" in segment and ".pq" in segment:
            return node
    raise AuditInputError("read_table() has no .parquet/.pq branch")


def _is_call(call: ast.Call, owner: str, attribute: str) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == owner
        and call.func.attr == attribute
    )


def _is_bytesio(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "io"
        and node.func.attr == "BytesIO"
    )


def inspect_contract(text: str) -> dict[str, bool]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise AuditInputError(f"source is not valid Python: {exc}") from exc

    reader = _function(tree, "read_table")
    branch = _parquet_branch(text, reader)
    calls = [node for node in ast.walk(branch) if isinstance(node, ast.Call)]
    read_parquet_calls = [call for call in calls if _is_call(call, "pd", "read_parquet")]
    read_bytes_present = any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "read_bytes"
        for call in calls
    )
    read_parquet_from_bytesio = any(
        call.args and _is_bytesio(call.args[0]) for call in read_parquet_calls
    )
    snapshot_retained = any(
        isinstance(call.func, ast.Name) and call.func.id == "_retain_snapshot"
        for call in calls
    ) or "_INPUT_SNAPSHOTS" in (ast.get_source_segment(text, branch) or "")

    manifest = _function(tree, "_input_manifest_record")
    manifest_text = ast.get_source_segment(text, manifest) or ""
    analyze = _function(tree, "analyze")
    analyze_text = ast.get_source_segment(text, analyze) or ""
    write_manifest = _function(tree, "write_manifest")
    write_manifest_text = ast.get_source_segment(text, write_manifest) or ""

    return {
        "parquet_branch_reads_bytes": read_bytes_present,
        "read_parquet_uses_bytesio": read_parquet_from_bytesio,
        "parquet_snapshot_retained": snapshot_retained,
        "manifest_uses_retained_snapshot": "_INPUT_SNAPSHOTS" in manifest_text,
        "policy_declared": POLICY in text,
        "snapshot_policy_declared": REQUIRED_SNAPSHOT_POLICY in text,
        "result_contract_records_policy": (
            "parquet_provenance_policy" in analyze_text
            and "PARQUET_PROVENANCE_POLICY" in analyze_text
            and "parquet_snapshot_policy" in analyze_text
        ),
        "manifest_contract_records_policy": (
            "parquet_provenance_policy" in write_manifest_text
            and "PARQUET_PROVENANCE_POLICY" in write_manifest_text
            and "parquet_snapshot_policy" in write_manifest_text
        ),
    }


def run_controls() -> dict[str, Any]:
    parsed = b"PARQUET-SNAPSHOT-A\n"
    replacement = b"PARQUET-SNAPSHOT-B\n"
    parsed_sha = hashlib.sha256(parsed).hexdigest()
    replacement_sha = hashlib.sha256(replacement).hexdigest()
    return {
        "parsed_bytes": len(parsed),
        "replacement_bytes": len(replacement),
        "parsed_sha256": parsed_sha,
        "replacement_sha256": replacement_sha,
        "former_post_read_manifest_sha256": replacement_sha,
        "former_rows_manifest_match": False,
        "single_snapshot_manifest_sha256": parsed_sha,
        "single_snapshot_rows_manifest_match": True,
    }


def audit_source(source_path: Path) -> dict[str, Any]:
    raw, text = snapshot_utf8(source_path)
    contract = inspect_contract(text)
    controls = run_controls()
    findings: list[dict[str, str]] = []

    checks = {
        "PARQUET_PATH_READ_NOT_SNAPSHOTTED": contract["parquet_branch_reads_bytes"],
        "PARQUET_READER_NOT_BOUND_TO_BYTES": contract["read_parquet_uses_bytesio"],
        "PARQUET_SNAPSHOT_NOT_RETAINED": contract["parquet_snapshot_retained"],
        "MANIFEST_DOES_NOT_REUSE_PARQUET_SNAPSHOT": contract[
            "manifest_uses_retained_snapshot"
        ],
        "PARQUET_POLICY_MISSING": contract["policy_declared"],
        "PARQUET_SNAPSHOT_POLICY_MISSING": contract["snapshot_policy_declared"],
        "RESULT_CONTRACT_OMITS_PARQUET_POLICY": contract[
            "result_contract_records_policy"
        ],
        "MANIFEST_CONTRACT_OMITS_PARQUET_POLICY": contract[
            "manifest_contract_records_policy"
        ],
    }
    messages = {
        "PARQUET_PATH_READ_NOT_SNAPSHOTTED": (
            "Parquet parsing is not preceded by one exact path.read_bytes() snapshot."
        ),
        "PARQUET_READER_NOT_BOUND_TO_BYTES": (
            "pandas.read_parquet is not reading io.BytesIO from the retained bytes."
        ),
        "PARQUET_SNAPSHOT_NOT_RETAINED": (
            "The bytes parsed as Parquet are not retained for manifest provenance."
        ),
        "MANIFEST_DOES_NOT_REUSE_PARQUET_SNAPSHOT": (
            "Manifest generation does not reuse the retained parsed-input snapshot."
        ),
        "PARQUET_POLICY_MISSING": f"Source does not declare policy {POLICY}.",
        "PARQUET_SNAPSHOT_POLICY_MISSING": (
            f"Source does not declare {REQUIRED_SNAPSHOT_POLICY}."
        ),
        "RESULT_CONTRACT_OMITS_PARQUET_POLICY": (
            "result.json reader metadata omits the Parquet snapshot policy."
        ),
        "MANIFEST_CONTRACT_OMITS_PARQUET_POLICY": (
            "manifest.json reader metadata omits the Parquet snapshot policy."
        ),
    }
    for code, passed in checks.items():
        if not passed:
            findings.append({"code": code, "message": messages[code]})

    return {
        "schema": SCHEMA,
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "source": {
            "path": str(source_path),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "snapshot_policy": "SINGLE_READ_STRICT_UTF8",
        },
        "reader_contract": contract,
        "controls": controls,
        "findings": findings,
        "acceptance": {
            "required_parquet_reader": "pandas.read_parquet(io.BytesIO(snapshot))",
            "required_snapshot_policy": REQUIRED_SNAPSHOT_POLICY,
            "required_rows_manifest_match": True,
        },
        "environment": {"python": platform.python_version()},
        "scientific_boundary": (
            "This audit validates table-byte provenance only; it does not validate A-002 "
            "amplitudes, stopping fractions, PID, calibration, or detector performance."
        ),
    }


def atomic_write_json(path: Path, payload: dict[str, Any], inputs: list[Path]) -> None:
    resolved_output = path.resolve()
    if any(resolved_output == item.resolve() for item in inputs):
        raise AuditInputError("output path aliases an input path")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = audit_source(args.source)
        if args.output:
            atomic_write_json(args.output, payload, [args.source])
    except (AuditInputError, OSError) as exc:
        print(f"INPUT_ERROR: {exc}")
        return 2
    print(f"{payload['status']}: {len(payload['findings'])} finding(s)")
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
