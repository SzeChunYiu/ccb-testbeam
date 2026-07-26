#!/usr/bin/env python3
"""Fail-closed source audit for DeltaE event-table publication."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

POLICY = "DELTAE_EVENT_TABLE_OUTPUT_MUST_FAIL_CLOSED_AND_NOT_ALIAS_INPUT"
PUBLICATION = "SAME_DIRECTORY_TEMP_FSYNC_OS_REPLACE"
FALLBACK = "CSV_GZIP_ONLY_WHEN_PARQUET_ENGINE_UNAVAILABLE"
AUDIT_VERSION = "1.0.0"


class AuditInputError(RuntimeError):
    """Raised for malformed audit inputs or unsafe output requests."""


def _snapshot(path: Path) -> tuple[bytes, str]:
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"invalid UTF-8 in {path}: {exc}") from exc
    return raw, text


def _paths_alias(left: Path, right: Path) -> bool:
    left_resolved = Path(left).resolve()
    right_resolved = Path(right).resolve()
    if left_resolved == right_resolved:
        return True
    try:
        return left_resolved.exists() and right_resolved.exists() and os.path.samefile(
            left_resolved,
            right_resolved,
        )
    except OSError:
        return False


def _function_source(text: str, tree: ast.Module, name: str) -> str | None:
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            end = getattr(node, "end_lineno", node.lineno)
            return "\n".join(lines[node.lineno - 1 : end])
    return None


def _has_core_writer_binding(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "_core"
            and target.attr == "_write_table"
        ):
            continue
        return isinstance(node.value, ast.Name) and node.value.id == "_write_table"
    return False


def _former_behavior_control() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        parquet = root / "events.parquet"
        csv_path = root / "events.csv.gz"
        calls: list[str] = []

        class Frame:
            def to_parquet(self, path: Path, index: bool = False) -> None:
                calls.append("parquet")
                Path(path).write_bytes(b"partial")
                raise PermissionError("synthetic permission failure")

            def to_csv(self, path: Path, index: bool = False) -> None:
                calls.append("csv")
                Path(path).write_bytes(b"fallback")

        frame = Frame()
        try:
            frame.to_parquet(parquet, index=False)
            published = parquet
        except Exception:
            frame.to_csv(csv_path, index=False)
            published = csv_path
        return {
            "injected_failure": "PermissionError",
            "writer_calls": calls,
            "published_path": published.name,
            "parquet_partial_exists": parquet.exists(),
            "csv_fallback_exists": csv_path.exists(),
            "demonstrates_broad_fallback": calls == ["parquet", "csv"],
        }


def audit_source(path: Path) -> dict[str, Any]:
    raw, text = _snapshot(path)
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise AuditInputError(f"invalid Python source: {exc}") from exc

    findings: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition:
            findings.append({"code": code, "message": message})

    write_source = _function_source(text, tree, "_write_table")
    atomic_source = _function_source(text, tree, "_atomic_table_write")
    contract_source = _function_source(text, tree, "_event_table_output_contract")
    analyze_source = _function_source(text, tree, "analyze")
    manifest_source = _function_source(text, tree, "write_manifest")

    require(POLICY in text, "MISSING_POLICY", "output policy is not declared")
    require(PUBLICATION in text, "MISSING_PUBLICATION_POLICY", "atomic policy is absent")
    require(FALLBACK in text, "MISSING_FALLBACK_POLICY", "fallback policy is absent")
    require(write_source is not None, "MISSING_STRICT_WRITER", "front door has no writer override")
    require(
        _has_core_writer_binding(tree),
        "CORE_WRITER_NOT_OVERRIDDEN",
        "retained core writer remains active",
    )

    if write_source is not None:
        require(
            "_reject_output_aliases" in write_source,
            "MISSING_ALIAS_GATE",
            "writer does not reject input/output aliasing",
        )
        require(
            "_atomic_table_write" in write_source,
            "MISSING_ATOMIC_WRITE",
            "writer does not use atomic publication",
        )
        require(
            "except ImportError as exc" in write_source
            and "_parquet_engine_unavailable" in write_source,
            "BROAD_OR_UNSCOPED_FALLBACK",
            "CSV fallback is not limited to a missing Parquet engine",
        )
        require(
            "stale alternate-format event table exists" in write_source,
            "MISSING_STALE_ALTERNATE_GATE",
            "writer does not reject stale alternate-format output",
        )
        require(
            "except Exception:" not in write_source,
            "BROAD_FALLBACK_REMAINS",
            "writer still catches every Parquet failure for fallback",
        )

    if atomic_source is not None:
        require(
            "os.fsync" in atomic_source or "_fsync_file" in atomic_source,
            "MISSING_FSYNC",
            "temporary file is not fsynced",
        )
        require(
            "os.replace" in atomic_source,
            "MISSING_REPLACE",
            "final publication does not use os.replace",
        )
        require(
            "temporary.unlink(missing_ok=True)" in atomic_source,
            "MISSING_TEMP_CLEANUP",
            "failed temporary output is not removed",
        )
    else:
        findings.append(
            {"code": "MISSING_ATOMIC_HELPER", "message": "atomic helper is absent"}
        )

    require(
        contract_source is not None and "EVENT_TABLE_OUTPUT_POLICY" in contract_source,
        "MISSING_CONTRACT_OBJECT",
        "machine-readable output contract is absent",
    )
    require(
        analyze_source is not None and "event_table_output_contract" in analyze_source,
        "RESULT_CONTRACT_NOT_PUBLISHED",
        "result.json contract is absent",
    )
    require(
        manifest_source is not None and "event_table_output_contract" in manifest_source,
        "MANIFEST_CONTRACT_NOT_PUBLISHED",
        "manifest contract is absent",
    )

    return {
        "schema": "ccb-deltae-table-output-audit/1",
        "audit_version": AUDIT_VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "source": {
            "path": str(Path(path)),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        "findings": findings,
        "finding_count": len(findings),
        "former_behavior_control": _former_behavior_control(),
        "acceptance": {
            "software_contract": "VALIDATED" if not findings else "FLAWED",
            "physics_result": "NOT_AUTHORIZED",
        },
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output is not None and _paths_alias(args.source, args.output):
        print("audit input and output must not alias", flush=True)
        return 2
    try:
        payload = audit_source(args.source)
        if args.output is not None:
            _atomic_json(args.output, payload)
    except (AuditInputError, OSError) as exc:
        print(f"input error: {exc}", flush=True)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
