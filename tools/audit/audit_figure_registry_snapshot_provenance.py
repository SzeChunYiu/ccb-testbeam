#!/usr/bin/env python3
"""Audit paper-figure artifact provenance for single-read byte consistency."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES"


class AuditInputError(RuntimeError):
    """Controlled input or publication failure."""


def _read_snapshot(path: Path) -> tuple[bytes, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditInputError(f"cannot read source: {exc}") from exc
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"source is not strict UTF-8: {exc}") from exc
    return raw, text


def _same_file(left: Path, right: Path) -> bool:
    try:
        if left.resolve() == right.resolve():
            return True
    except OSError:
        pass
    try:
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "publication": "SAME_DIRECTORY_TEMP_FLUSH_FSYNC_OS_REPLACE",
    }


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _functions(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _source_segment(text: str, node: ast.AST) -> str:
    return ast.get_source_segment(text, node) or ""


def _current_patterns(tree: ast.AST, text: str) -> dict[str, Any]:
    functions = _functions(tree)
    load_result = functions.get("_load_result")
    emit_quantitative = functions.get("_emit_quantitative")
    emit_existing = functions.get("_emit_existing_artifact")

    load_result_reads_path = False
    result_rehashed_later = False
    source_copied_from_path = False
    source_rehashed_later = False
    source_restat_later = False

    if load_result:
        load_text = _source_segment(text, load_result)
        load_result_reads_path = ".read_text(" in load_text or ".read_bytes(" in load_text
    if emit_quantitative:
        for node in ast.walk(emit_quantitative):
            if not isinstance(node, ast.Call) or _call_name(node) != "sha256_file":
                continue
            segment = _source_segment(text, node)
            if "entry.result" in segment:
                result_rehashed_later = True
    if emit_existing:
        existing_text = _source_segment(text, emit_existing)
        source_copied_from_path = "shutil.copy2(source, target)" in existing_text
        source_rehashed_later = "sha256_file(source)" in existing_text
        source_restat_later = "source.stat().st_size" in existing_text

    return {
        "load_result_reads_path": load_result_reads_path,
        "result_rehashed_later": result_rehashed_later,
        "source_copied_from_path": source_copied_from_path,
        "source_rehashed_later": source_rehashed_later,
        "source_restat_later": source_restat_later,
    }


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def behavioral_controls() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)

        result_path = root / "result.json"
        result_v1 = b'{"value": 1.0, "uncertainty": [0.9, 1.1]}\n'
        result_v2 = b'{"value": 99.0, "uncertainty": [98.0, 100.0]}\n'
        result_path.write_bytes(result_v1)
        parsed_v1 = json.loads(result_path.read_text(encoding="utf-8"))
        result_path.write_bytes(result_v2)
        later_result_hash = _sha256(result_path.read_bytes())

        retained_result = result_v1
        corrected_parsed = json.loads(retained_result.decode("utf-8"))
        corrected_result_hash = _sha256(retained_result)

        source_path = root / "source.png"
        target_path = root / "copied.png"
        source_v1 = b"source-artifact-v1"
        source_v2 = b"source-artifact-v2-with-different-size"
        source_path.write_bytes(source_v1)
        shutil.copy2(source_path, target_path)
        source_path.write_bytes(source_v2)
        later_source_hash = _sha256(source_path.read_bytes())
        later_source_size = source_path.stat().st_size
        target_hash = _sha256(target_path.read_bytes())

        retained_source = source_v1
        corrected_target = root / "corrected.png"
        corrected_target.write_bytes(retained_source)
        corrected_source_hash = _sha256(retained_source)

        return {
            "result_path_replacement": {
                "numeric_value_used": parsed_v1["value"],
                "bytes_used_sha256": _sha256(result_v1),
                "later_reported_sha256": later_result_hash,
                "later_hash_matches_used_bytes": later_result_hash == _sha256(result_v1),
                "corrected_numeric_value": corrected_parsed["value"],
                "corrected_reported_sha256": corrected_result_hash,
                "corrected_hash_matches_used_bytes": corrected_result_hash
                == _sha256(retained_result),
                "interpretation": (
                    "Reading JSON first and hashing the path later can pair a figure value "
                    "with replacement bytes. Parsing and hashing one retained byte snapshot "
                    "keeps the value and provenance identical."
                ),
            },
            "source_artifact_replacement": {
                "copied_target_sha256": target_hash,
                "later_reported_source_sha256": later_source_hash,
                "later_reported_source_size": later_source_size,
                "later_metadata_matches_copied_target": later_source_hash == target_hash,
                "corrected_target_sha256": _sha256(corrected_target.read_bytes()),
                "corrected_reported_sha256": corrected_source_hash,
                "corrected_metadata_matches_target": corrected_source_hash
                == _sha256(corrected_target.read_bytes()),
                "interpretation": (
                    "Copying a source path and hashing/statting it later can describe different "
                    "bytes from the copied artifact. A single retained source snapshot avoids "
                    "that time-of-check/time-of-use provenance split."
                ),
            },
        }


def audit_source(
    source: Path,
    *,
    source_ref: str | None = None,
    source_blob: str | None = None,
    source_scope: str = "LOCAL_SOURCE_FILE",
) -> dict[str, Any]:
    raw, text = _read_snapshot(source)
    try:
        tree = ast.parse(text, filename=str(source))
    except SyntaxError as exc:
        raise AuditInputError(f"source is not valid Python: {exc}") from exc

    patterns = _current_patterns(tree, text)
    controls = behavioral_controls()
    findings: list[dict[str, Any]] = []

    if patterns["load_result_reads_path"] and patterns["result_rehashed_later"]:
        findings.append(
            {
                "code": "RESULT_VALUE_AND_HASH_CAN_REFERENCE_DIFFERENT_BYTES",
                "detail": (
                    "The result JSON is parsed from one path read, but provenance is later "
                    "computed by hashing the path again."
                ),
            }
        )
    if patterns["source_copied_from_path"] and patterns["source_rehashed_later"]:
        findings.append(
            {
                "code": "COPIED_SOURCE_AND_HASH_CAN_REFERENCE_DIFFERENT_BYTES",
                "detail": (
                    "The source artifact is copied before the source path is hashed again."
                ),
            }
        )
    if patterns["source_copied_from_path"] and patterns["source_restat_later"]:
        findings.append(
            {
                "code": "COPIED_SOURCE_AND_SIZE_CAN_REFERENCE_DIFFERENT_BYTES",
                "detail": (
                    "The copied artifact is produced before the source path is statted again."
                ),
            }
        )

    return {
        "schema": "ccb-figure-registry-snapshot-provenance-audit/1",
        "version": VERSION,
        "policy": POLICY,
        "status": "FLAWED" if findings else "VALIDATED",
        "finding_count": len(findings),
        "findings": findings,
        "source": {
            "path": str(source),
            "scope": source_scope,
            "bytes": len(raw),
            "sha256": _sha256(raw),
            "repository_ref": source_ref,
            "git_blob": source_blob,
            "snapshot_method": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
        },
        "source_contract_observation": patterns,
        "behavioral_controls": controls,
        "required_remediation": {
            "result_json": (
                "Read exact bytes once, decode and parse those bytes, and record byte count and "
                "SHA-256 from the retained snapshot used for numeric extraction."
            ),
            "source_artifact": (
                "Read exact bytes once, hash and size that snapshot, publish the target "
                "atomically from those bytes, and record the same snapshot provenance."
            ),
            "publication": (
                "Do not let a later path replacement alter metadata for an already rendered or "
                "copied artifact."
            ),
        },
        "scientific_boundary": (
            "This audit validates paper-artifact byte provenance and publication semantics. It "
            "does not validate any underlying scientific value, uncertainty, calibration, PID, "
            "timing, stopping profile, or detector-performance claim."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-ref")
    parser.add_argument("--source-blob")
    parser.add_argument("--source-scope", default="LOCAL_SOURCE_FILE")
    parser.add_argument("--repository")
    parser.add_argument("--initial-main")
    parser.add_argument("--source-path-in-repo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.output and _same_file(args.source, args.output):
        print("INPUT_ERROR: output aliases source", file=os.sys.stderr)
        return 2
    try:
        result = audit_source(
            args.source,
            source_ref=args.source_ref,
            source_blob=args.source_blob,
            source_scope=args.source_scope,
        )
        result["repository_context"] = {
            "repository": args.repository,
            "initial_main": args.initial_main,
            "source_path": args.source_path_in_repo,
        }
        if args.output:
            result["output_publication"] = _atomic_write_json(args.output, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "VALIDATED" else 1
    except AuditInputError as exc:
        print(f"INPUT_ERROR: {exc}", file=os.sys.stderr)
        return 2
    except OSError as exc:
        print(f"OUTPUT_ERROR: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
