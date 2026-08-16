#!/usr/bin/env python3
"""Audit paper figure-registry vocabulary and structural self-consistency."""
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

import yaml

POLICY = "FIGURE_REGISTRY_SCHEMA_MUST_ACCEPT_ITS_SHIPPED_VOCABULARY"
VERSION = "1.0.0"


@dataclass(frozen=True)
class Snapshot:
    path: str
    data: bytes
    text: str

    @property
    def size_bytes(self) -> int:
        return len(self.data)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def snapshot_utf8(path: Path) -> Snapshot:
    data = path.read_bytes()
    return Snapshot(str(path), data, data.decode("utf-8"))


def issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "message": message}
    if details:
        item["details"] = details
    return item


def _literal_string_set(node: ast.AST) -> set[str] | None:
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None
    if isinstance(value, (set, frozenset, list, tuple)) and all(
        isinstance(item, str) for item in value
    ):
        return set(value)
    return None


def _assigned_frozenset(tree: ast.Module, name: str) -> set[str]:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Name) and t.id == name for t in targets):
            continue
        value = node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id == "frozenset" and len(value.args) == 1:
                parsed = _literal_string_set(value.args[0])
                return parsed or set()
        parsed = _literal_string_set(value)
        return parsed or set()
    return set()


def _test_frozen_statuses(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "test_allowed_statuses_frozen":
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                if child.func.id == "frozenset" and len(child.args) == 1:
                    parsed = _literal_string_set(child.args[0])
                    if parsed is not None:
                        return parsed
    return set()


def _has_unconditional_result_requirement(source: str) -> bool:
    compact = " ".join(source.split())
    return "if not e.result:" in source and "missing required 'result' path" in compact


def _input_record(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "path": snapshot.path,
        "size_bytes": snapshot.size_bytes,
        "sha256": snapshot.sha256,
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def atomic_write_json(path: Path, payload: dict[str, Any], protected: set[Path]) -> None:
    resolved = path.resolve()
    if resolved in protected:
        raise ValueError("output JSON path aliases an input path")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{resolved.name}.", dir=resolved.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, resolved)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def audit(
    registry_source_path: Path,
    registry_yaml_path: Path,
    test_source_path: Path,
    output_json: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    input_paths = [registry_source_path, registry_yaml_path, test_source_path]
    protected = {path.resolve() for path in input_paths}
    if output_json is not None and output_json.resolve() in protected:
        return 2, {
            "policy": POLICY,
            "tool_version": VERSION,
            "status": "INPUT_ERROR",
            "issues": [
                issue("OUTPUT_ALIASES_INPUT", "output JSON path aliases an input path")
            ],
        }

    try:
        registry_source = snapshot_utf8(registry_source_path)
        registry_yaml = snapshot_utf8(registry_yaml_path)
        test_source = snapshot_utf8(test_source_path)
        registry_tree = ast.parse(registry_source.text)
        test_tree = ast.parse(test_source.text)
        document = yaml.safe_load(registry_yaml.text) or {}
        if not isinstance(document, dict):
            raise ValueError("registry YAML top level must be a mapping")
    except (OSError, UnicodeDecodeError, SyntaxError, yaml.YAMLError, ValueError) as exc:
        payload = {
            "policy": POLICY,
            "tool_version": VERSION,
            "status": "INPUT_ERROR",
            "issues": [issue("INPUT_ERROR", str(exc))],
        }
        if output_json is not None:
            atomic_write_json(output_json, payload, protected)
        return 2, payload

    allowed_statuses = _assigned_frozenset(registry_tree, "ALLOWED_STATUSES")
    allowed_kinds = _assigned_frozenset(registry_tree, "ALLOWED_KINDS")
    frozen_test_statuses = _test_frozen_statuses(test_tree)
    used_statuses: set[str] = set()
    used_kinds: set[str] = set()
    missing_result_illustrative: list[str] = []
    malformed_entries: list[str] = []

    for entry_id, body in document.items():
        if not isinstance(body, dict):
            malformed_entries.append(str(entry_id))
            continue
        status = body.get("status")
        kind = body.get("kind")
        if isinstance(status, str) and status:
            used_statuses.add(status)
        if isinstance(kind, str) and kind:
            used_kinds.add(kind)
        if kind == "illustrative" and not body.get("result"):
            missing_result_illustrative.append(str(entry_id))

    issues: list[dict[str, Any]] = []
    for status in sorted(used_statuses - allowed_statuses):
        issues.append(
            issue(
                "REGISTRY_STATUS_UNSUPPORTED",
                f"shipped registry uses status {status!r} outside ALLOWED_STATUSES",
                status=status,
            )
        )
    for kind in sorted(used_kinds - allowed_kinds):
        issues.append(
            issue(
                "REGISTRY_KIND_UNSUPPORTED",
                f"shipped registry uses kind {kind!r} outside ALLOWED_KINDS",
                kind=kind,
            )
        )
    if malformed_entries:
        issues.append(
            issue(
                "REGISTRY_ENTRY_MALFORMED",
                "shipped registry contains non-mapping entries",
                entries=sorted(malformed_entries),
            )
        )
    if missing_result_illustrative and _has_unconditional_result_requirement(
        registry_source.text
    ):
        issues.append(
            issue(
                "ILLUSTRATIVE_RESULT_FALSE_REQUIREMENT",
                "illustrative source_figure entries are rejected for lacking a result path",
                entries=sorted(missing_result_illustrative),
            )
        )
    if frozen_test_statuses and frozen_test_statuses != allowed_statuses:
        issues.append(
            issue(
                "TEST_STATUS_SET_DRIFT",
                "test frozen status set differs from implementation ALLOWED_STATUSES",
                implementation=sorted(allowed_statuses),
                test=sorted(frozen_test_statuses),
            )
        )
    if frozen_test_statuses and used_statuses - frozen_test_statuses:
        issues.append(
            issue(
                "TEST_FREEZES_OBSOLETE_STATUS_SET",
                "test freezes a status vocabulary that excludes shipped registry statuses",
                excluded=sorted(used_statuses - frozen_test_statuses),
            )
        )

    payload = {
        "policy": POLICY,
        "tool_version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "issues": issues,
        "summary": {
            "allowed_statuses": sorted(allowed_statuses),
            "used_statuses": sorted(used_statuses),
            "allowed_kinds": sorted(allowed_kinds),
            "used_kinds": sorted(used_kinds),
            "frozen_test_statuses": sorted(frozen_test_statuses),
            "missing_result_illustrative_entries": sorted(missing_result_illustrative),
        },
        "inputs": {
            "registry_source": _input_record(registry_source),
            "registry_yaml": _input_record(registry_yaml),
            "test_source": _input_record(test_source),
        },
        "acceptance_boundary": (
            "This audit validates schema alignment only. It does not validate any figure's "
            "scientific claim, source value, uncertainty, or detector performance."
        ),
    }
    if output_json is not None:
        atomic_write_json(output_json, payload, protected)
    return (0 if not issues else 1), payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_source", type=Path)
    parser.add_argument("registry_yaml", type=Path)
    parser.add_argument("test_source", type=Path)
    parser.add_argument("--output-json", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    status, payload = audit(
        args.registry_source, args.registry_yaml, args.test_source, args.output_json
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
