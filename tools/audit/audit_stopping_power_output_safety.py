#!/usr/bin/env python3
"""Audit stopping-power report output-path and write-atomicity safeguards."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

TOOL_VERSION = "1.0.0"
POLICY = "NO_INPUT_OUTPUT_ALIAS_AND_ATOMIC_REPORT_WRITE"


class OutputSafetyAuditError(ValueError):
    """Raised when source bytes cannot be audited deterministically."""


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}"
        return node.func.attr
    return None


def _string_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_direct_final_write(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "open":
        return False
    if not isinstance(node.func.value, ast.Name) or node.func.value.id != "out_path":
        return False
    mode: str | None = None
    if node.args:
        mode = _string_value(node.args[0])
    for keyword in node.keywords:
        if keyword.arg == "mode":
            mode = _string_value(keyword.value)
    return mode is not None and any(flag in mode for flag in ("w", "a", "x", "+"))


def audit_source(path: Path) -> dict[str, Any]:
    """Return a machine-readable audit of the canonical report-write path."""
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        raise OutputSafetyAuditError(f"cannot read source {path}: {exc}") from exc
    try:
        source = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OutputSafetyAuditError(f"source is not valid UTF-8: {path}") from exc
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise OutputSafetyAuditError(f"source is not valid Python: {exc}") from exc

    run_compare = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "run_compare"
        ),
        None,
    )
    if run_compare is None:
        raise OutputSafetyAuditError("source does not define run_compare()")

    calls = [node for node in ast.walk(run_compare) if isinstance(node, ast.Call)]
    call_names = {_call_name(node) for node in calls}
    direct_final_write = any(_is_direct_final_write(node) for node in calls)
    alias_guard = "_validate_output_path" in call_names
    atomic_write = "_write_report_atomically" in call_names or "os.replace" in call_names

    findings: list[str] = []
    if direct_final_write:
        findings.append("DIRECT_REPORT_WRITE_TO_FINAL_PATH")
    if not alias_guard:
        findings.append("OUTPUT_PATH_ALIAS_NOT_REJECTED")
    if not atomic_write:
        findings.append("REPORT_WRITE_NOT_ATOMIC")

    status = "VALIDATED" if not findings else "FLAWED"
    return {
        "tool": "audit_stopping_power_output_safety",
        "tool_version": TOOL_VERSION,
        "policy": POLICY,
        "source_path": str(path),
        "source_bytes": len(source_bytes),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "run_compare_found": True,
        "direct_final_write": direct_final_write,
        "output_alias_guard": alias_guard,
        "atomic_report_write": atomic_write,
        "findings": findings,
        "status": status,
        "interpretation": (
            "Report output cannot alias either validated input and is published only by "
            "atomic replacement."
            if status == "VALIDATED"
            else "A report path can overwrite a validated input and/or a failed write can "
            "leave a partial final artifact."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = audit_source(args.source)
    except OutputSafetyAuditError as exc:
        print(f"OUTPUT-SAFETY AUDIT: ERROR: {exc}")
        return 2
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"OUTPUT-SAFETY AUDIT: status={result['status']}")
    for finding in result["findings"]:
        print(f"- {finding}")
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
