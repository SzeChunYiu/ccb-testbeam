#!/usr/bin/env python3
"""Audit whether figure-registry builds can leave stale managed artifacts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

POLICY = "FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS"


@dataclass(frozen=True)
class SourceSnapshot:
    path: str
    raw: bytes
    sha256: str
    size_bytes: int
    text: str


class AuditInputError(RuntimeError):
    """Raised for controlled input or publication errors."""


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


def _read_source(path: Path) -> SourceSnapshot:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditInputError(f"could not read builder source {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"builder source is not strict UTF-8: {exc}") from exc
    return SourceSnapshot(
        path=str(path),
        raw=raw,
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        text=text,
    )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise AuditInputError(f"could not publish audit JSON {path}: {exc}") from exc


def _function_map(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _call_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Name):
            names.add(item.func.id)
        elif isinstance(item.func, ast.Attribute):
            names.add(item.func.attr)
    return names


def _cleanup_like(names: set[str]) -> set[str]:
    matched: set[str] = set()
    for name in names:
        lowered = name.lower()
        destructive = any(token in lowered for token in ("clean", "remove", "purge"))
        managed = any(token in lowered for token in ("artifact", "output", "entry"))
        if destructive and managed:
            matched.add(name)
        if "reconcile" in lowered and any(
            token in lowered for token in ("artifact", "output", "entry", "registry")
        ):
            matched.add(name)
    return matched


def _contains_disposition_return(
    node: ast.FunctionDef | ast.AsyncFunctionDef, disposition: str
) -> bool:
    for item in ast.walk(node):
        if not isinstance(item, ast.If):
            continue
        comparison_text = ast.unparse(item.test) if hasattr(ast, "unparse") else ""
        if disposition not in comparison_text:
            continue
        if any(isinstance(child, ast.Return) for child in ast.walk(item)):
            return True
    return False


def _except_cleanup_calls(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.ExceptHandler):
            names.update(_call_names(item))
    return _cleanup_like(names)


def _run_behavioral_control(cleanup: bool) -> dict[str, Any]:
    scenarios: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for scenario in ("blocked", "failed", "removed"):
            scenario_dir = root / scenario
            scenario_dir.mkdir()
            managed = [scenario_dir / "Q.png", scenario_dir / "Q_source_data.csv"]
            for index, path in enumerate(managed):
                path.write_bytes(f"prior-{scenario}-{index}".encode("ascii"))
            before = sorted(path.name for path in scenario_dir.iterdir())
            if cleanup:
                for path in managed:
                    path.unlink(missing_ok=True)
            after = sorted(path.name for path in scenario_dir.iterdir())
            scenarios[scenario] = {
                "managed_before": before,
                "managed_after": after,
                "stale_count": len(after),
            }
    return scenarios


def audit_source(snapshot: SourceSnapshot) -> dict[str, Any]:
    try:
        tree = ast.parse(snapshot.text, filename=snapshot.path)
    except SyntaxError as exc:
        raise AuditInputError(f"builder source is not valid Python: {exc}") from exc

    functions = _function_map(tree)
    process = functions.get("_process_entry")
    build = functions.get("build")
    if process is None or build is None:
        raise AuditInputError("builder source must define _process_entry and build")

    process_cleanup = _cleanup_like(_call_names(process))
    build_cleanup = _cleanup_like(_call_names(build))
    except_cleanup = _except_cleanup_calls(build)

    findings: list[dict[str, str]] = []
    if not process_cleanup:
        findings.append(
            {
                "code": "NO_ENTRY_OUTPUT_CLEANUP",
                "detail": "_process_entry has no managed-artifact cleanup call.",
            }
        )
    if (
        _contains_disposition_return(process, "BLOCKED")
        or _contains_disposition_return(process, "QUARANTINED")
    ) and not process_cleanup:
        findings.append(
            {
                "code": "NONPASS_DISPOSITION_CAN_RETAIN_STALE_ARTIFACTS",
                "detail": (
                    "BLOCKED or QUARANTINED entries return without removing prior "
                    "figure/source-data outputs."
                ),
            }
        )
    if not except_cleanup:
        findings.append(
            {
                "code": "FAILED_ENTRY_CAN_RETAIN_STALE_ARTIFACTS",
                "detail": (
                    "The per-entry FigureRegistryError handler records FAIL without "
                    "removing prior managed outputs."
                ),
            }
        )
    if not any("reconcile" in name.lower() for name in build_cleanup):
        findings.append(
            {
                "code": "REMOVED_ENTRY_CAN_RETAIN_STALE_ARTIFACTS",
                "detail": (
                    "build does not reconcile prior managed outputs against current "
                    "registry entry IDs."
                ),
            }
        )

    current_control = _run_behavioral_control(cleanup=False)
    corrected_control = _run_behavioral_control(cleanup=True)
    status = "VALIDATED" if not findings else "FLAWED"
    return {
        "schema": "ccb-figure-registry-stale-artifact-audit/1",
        "policy": POLICY,
        "status": status,
        "source": {
            "path": snapshot.path,
            "sha256": snapshot.sha256,
            "size_bytes": snapshot.size_bytes,
            "snapshot_method": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
        },
        "source_contract": {
            "process_cleanup_calls": sorted(process_cleanup),
            "build_cleanup_calls": sorted(build_cleanup),
            "failure_handler_cleanup_calls": sorted(except_cleanup),
        },
        "findings": findings,
        "controls": {
            "current_no_cleanup_model": current_control,
            "corrected_cleanup_model": corrected_control,
        },
        "interpretation": (
            "A non-PASS or removed entry must not leave an older paper artifact at a "
            "managed output path. The audit is a software/provenance check and does "
            "not validate any scientific value."
        ),
        "required_remediation": [
            "Define the complete set of managed output paths per registry entry.",
            "Remove or quarantine prior managed outputs before recording non-PASS.",
            "Reconcile outputs for entry IDs removed from the current registry.",
            "Publish the report and managed artifact set as one fail-closed build state.",
            "Add regressions for PASS-to-BLOCKED, PASS-to-FAIL, and removed entries.",
        ],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--builder-source", required=True)
    parser.add_argument("--output-json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    source = Path(args.builder_source)
    output = Path(args.output_json)
    if _same_file(source, output):
        print("AuditInputError: output JSON aliases builder source", file=os.sys.stderr)
        return 2
    try:
        snapshot = _read_source(source)
        payload = audit_source(snapshot)
        _atomic_write_json(output, payload)
    except AuditInputError as exc:
        print(f"AuditInputError: {exc}", file=os.sys.stderr)
        return 2
    print(f"status: {payload['status']}")
    print(f"findings: {len(payload['findings'])}")
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
