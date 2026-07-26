#!/usr/bin/env python3
"""Audit run/event identity handling in real-data CFD timing analysis."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

VERSION = "1.0.0"
POLICY = "REAL_DATA_CFD_EVENTS_MUST_USE_RUN_AND_EVENT_ID_TOGETHER"


class AuditInputError(RuntimeError):
    """Controlled input/publication failure."""


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
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        finally:
            raise
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "publication": "SAME_DIRECTORY_TEMP_FLUSH_FSYNC_OS_REPLACE",
    }


def _literal_value(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _pivot_indexes(tree: ast.AST) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    current_function = "<module>"

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            nonlocal current_function
            previous = current_function
            current_function = node.name
            self.generic_visit(node)
            current_function = previous

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr == "pivot":
                index = None
                for keyword in node.keywords:
                    if keyword.arg == "index":
                        index = _literal_value(keyword.value)
                out.append(
                    {
                        "function": current_function,
                        "lineno": node.lineno,
                        "index": index,
                    }
                )
            self.generic_visit(node)

    Visitor().visit(tree)
    return out


def _event_id_only_isin(tree: ast.AST) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    current_function = "<module>"

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            nonlocal current_function
            previous = current_function
            current_function = node.name
            self.generic_visit(node)
            current_function = previous

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "isin":
                target = func.value
                if isinstance(target, ast.Subscript):
                    key = _literal_value(target.slice)
                    if key == "event_id":
                        out.append(
                            {
                                "function": current_function,
                                "lineno": node.lineno,
                            }
                        )
            self.generic_visit(node)

    Visitor().visit(tree)
    return out


def _load_contract_has_run_and_event(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {_literal_value(key) for key in node.keys if key is not None}
        if {"run", "event_id", "stave"}.issubset(keys):
            return True
    return False


def behavioral_controls() -> dict[str, Any]:
    false_pair = pd.DataFrame(
        [
            {
                "run": 58,
                "event_id": 7,
                "stave": "B6",
                "peak_sample": 7.0,
                "tcorr": 1.0,
            },
            {
                "run": 59,
                "event_id": 7,
                "stave": "B8",
                "peak_sample": 11.0,
                "tcorr": 2.0,
            },
        ]
    )
    offsets = {
        stave: float(
            false_pair.loc[false_pair["stave"] == stave, "peak_sample"].median()
        )
        for stave in ("B6", "B8")
    }
    work = false_pair.copy()
    work["peak_al"] = work["peak_sample"] - work["stave"].map(offsets)

    current_peak = work.pivot(index="event_id", columns="stave", values="peak_al")
    current_keep = current_peak.dropna().index
    current_selected = work[work["event_id"].isin(current_keep)]
    current_residual = false_pair.pivot(
        index="event_id", columns="stave", values="tcorr"
    )

    composite_peak = work.pivot(
        index=["run", "event_id"], columns="stave", values="peak_al"
    )
    composite_keep = composite_peak.dropna().index
    composite_selected = work.set_index(["run", "event_id"]).loc[
        work.set_index(["run", "event_id"]).index.isin(composite_keep)
    ]
    composite_residual = false_pair.pivot(
        index=["run", "event_id"], columns="stave", values="tcorr"
    ).dropna()

    duplicate_rows = pd.DataFrame(
        [
            {"run": 58, "event_id": 9, "stave": "B6", "tcorr": 1.0},
            {"run": 58, "event_id": 9, "stave": "B8", "tcorr": 2.0},
            {"run": 59, "event_id": 9, "stave": "B6", "tcorr": 3.0},
            {"run": 59, "event_id": 9, "stave": "B8", "tcorr": 4.0},
        ]
    )
    current_duplicate_outcome = "accepted"
    try:
        duplicate_rows.pivot(index="event_id", columns="stave", values="tcorr")
    except ValueError:
        current_duplicate_outcome = "ValueError"
    composite_duplicate_pairs = len(
        duplicate_rows.pivot(
            index=["run", "event_id"], columns="stave", values="tcorr"
        ).dropna()
    )

    return {
        "false_cross_run_pair": {
            "current_event_id_only_selected_rows": int(len(current_selected)),
            "current_event_id_only_pair_count": int(len(current_residual.dropna())),
            "composite_key_selected_rows": int(len(composite_selected)),
            "composite_key_pair_count": int(len(composite_residual)),
            "interpretation": (
                "The event_id-only contract pairs B6 from run 58 with B8 "
                "from run 59. "
                "The composite (run,event_id) contract rejects the pair."
            ),
        },
        "duplicate_event_id": {
            "current_event_id_only_outcome": current_duplicate_outcome,
            "composite_key_pair_count": composite_duplicate_pairs,
            "interpretation": (
                "Two legitimate run-local pairs sharing EVENTNO cannot be "
                "pivoted by event_id alone."
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

    pivots = _pivot_indexes(tree)
    event_only_pivots = [item for item in pivots if item["index"] == "event_id"]
    event_only_filters = _event_id_only_isin(tree)
    has_composite_input = _load_contract_has_run_and_event(tree)
    findings: list[dict[str, Any]] = []

    if has_composite_input and event_only_pivots:
        for item in event_only_pivots:
            findings.append(
                {
                    "code": "RUN_DROPPED_FROM_PIVOT_KEY",
                    "function": item["function"],
                    "line": item["lineno"],
                    "detail": "Input rows carry run and event_id, but pivot uses event_id alone.",
                }
            )
    if has_composite_input and event_only_filters:
        for item in event_only_filters:
            findings.append(
                {
                    "code": "RUN_DROPPED_FROM_SELECTION_FILTER",
                    "function": item["function"],
                    "line": item["lineno"],
                    "detail": "Selected keys are reapplied through event_id.isin without run.",
                }
            )

    controls = behavioral_controls()
    if event_only_pivots or event_only_filters:
        findings.extend(
            [
                {
                    "code": "SYNTHETIC_FALSE_CROSS_RUN_PAIR",
                    "detail": controls["false_cross_run_pair"]["interpretation"],
                },
                {
                    "code": "RUN_LOCAL_EVENT_ID_COLLISION_CAN_ABORT",
                    "detail": controls["duplicate_event_id"]["interpretation"],
                },
            ]
        )

    return {
        "schema": "ccb-real-data-cfd-event-identity-audit/1",
        "version": VERSION,
        "policy": POLICY,
        "status": "FLAWED" if findings else "VALIDATED",
        "finding_count": len(findings),
        "findings": findings,
        "source": {
            "path": str(source),
            "scope": source_scope,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "repository_ref": source_ref,
            "git_blob": source_blob,
            "snapshot_method": "SINGLE_READ_STRICT_UTF8_EXACT_BYTES",
        },
        "contract_observation": {
            "input_rows_include_run_event_stave": has_composite_input,
            "pivot_calls": pivots,
            "event_id_only_filters": event_only_filters,
            "required_event_key": ["run", "event_id"],
        },
        "behavioral_controls": controls,
        "scientific_boundary": (
            "This audit tests event identity and pairing semantics. It does not validate waveform "
            "calibration, channel mapping, CFD bias, selection efficiency, timing "
            "resolution, or CL-002."
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
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--pr-head")
    parser.add_argument("--pr-state")
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
            "pull_request": args.pr_number,
            "pull_request_head": args.pr_head,
            "pull_request_state": args.pr_state,
            "source_path": args.source_path_in_repo,
        }
        if args.output:
            _atomic_write_json(args.output, result)
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
