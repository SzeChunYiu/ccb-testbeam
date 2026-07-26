#!/usr/bin/env python3
"""Audit lossless CSV handling for DeltaE composite event identifiers."""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

SCHEMA = "ccb-deltae-csv-key-identity-audit/1"
POLICY = "DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT"
KEY_COLS = ("source_file_id", "run_id", "event_id")


class AuditInputError(RuntimeError):
    """Controlled invalid-input failure."""


def snapshot_utf8(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    try:
        return raw, raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"invalid UTF-8 in {path}: {exc}") from exc


def _calls_in_function(tree: ast.AST, name: str) -> list[ast.Call]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return [child for child in ast.walk(node) if isinstance(child, ast.Call)]
    raise AuditInputError(f"source does not define {name}()")


def inspect_reader_contract(text: str) -> dict[str, bool]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise AuditInputError(f"source is not valid Python: {exc}") from exc

    calls = _calls_in_function(tree, "read_table")
    read_csv_calls = [
        call
        for call in calls
        if isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "pd"
        and call.func.attr == "read_csv"
    ]
    if not read_csv_calls:
        raise AuditInputError("read_table() does not call pandas.read_csv()")

    has_dtype_keyword = any(
        keyword.arg == "dtype" for call in read_csv_calls for keyword in call.keywords
    )
    has_read_bytes = any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "read_bytes"
        for call in calls
    )
    has_decode = any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "decode"
        for call in calls
    )
    has_policy = POLICY in text
    key_tokens_present = all(repr(key) in text or f'"{key}"' in text for key in KEY_COLS)
    return {
        "read_csv_has_dtype": has_dtype_keyword,
        "single_read_bytes_present": has_read_bytes,
        "strict_decode_present": has_decode and "utf-8" in text and "strict" in text,
        "policy_present": has_policy,
        "all_key_tokens_present": key_tokens_present,
    }


def _control_csv(source_file_id: str) -> str:
    return (
        "source_file_id,run_id,event_id,amp_B2,sample,trigger_definition\n"
        f"{source_file_id},7,9,120,I,beam_v1\n"
    )


def run_controls() -> dict[str, Any]:
    distinct_csv = (
        "source_file_id,run_id,event_id,amp_B2,sample,trigger_definition\n"
        "001,7,9,120,I,beam_v1\n"
        "1,7,9,130,I,beam_v1\n"
    )
    default_distinct = pd.read_csv(io.StringIO(distinct_csv))
    lossless_distinct = pd.read_csv(
        io.StringIO(distinct_csv), dtype={key: "string" for key in KEY_COLS}
    )

    default_data = pd.read_csv(io.StringIO(_control_csv("001")))
    default_mc = pd.read_csv(io.StringIO(_control_csv("1")))
    lossless_data = pd.read_csv(
        io.StringIO(_control_csv("001")), dtype={key: "string" for key in KEY_COLS}
    )
    lossless_mc = pd.read_csv(
        io.StringIO(_control_csv("1")), dtype={key: "string" for key in KEY_COLS}
    )

    default_matches = default_data.merge(default_mc, on=list(KEY_COLS), how="inner")
    lossless_matches = lossless_data.merge(lossless_mc, on=list(KEY_COLS), how="inner")
    return {
        "pandas_version": pd.__version__,
        "raw_source_file_tokens": ["001", "1"],
        "default_inferred_tokens": [
            str(value) for value in default_distinct["source_file_id"].tolist()
        ],
        "lossless_text_tokens": lossless_distinct["source_file_id"].tolist(),
        "default_distinct_composite_keys": int(
            default_distinct[list(KEY_COLS)].drop_duplicates().shape[0]
        ),
        "lossless_distinct_composite_keys": int(
            lossless_distinct[list(KEY_COLS)].drop_duplicates().shape[0]
        ),
        "default_false_cross_file_matches": int(len(default_matches)),
        "lossless_cross_file_matches": int(len(lossless_matches)),
    }


def audit_source(source_path: Path) -> dict[str, Any]:
    raw, text = snapshot_utf8(source_path)
    contract = inspect_reader_contract(text)
    controls = run_controls()
    findings: list[dict[str, str]] = []

    if not contract["read_csv_has_dtype"]:
        findings.append(
            {
                "code": "CSV_KEY_DTYPE_MISSING",
                "message": "read_table() calls pandas.read_csv without an explicit key dtype.",
            }
        )
    if not (
        contract["single_read_bytes_present"]
        and contract["strict_decode_present"]
    ):
        findings.append(
            {
                "code": "CSV_NOT_SINGLE_READ_STRICT_UTF8",
                "message": (
                    "CSV bytes are not snapshotted once and decoded as strict UTF-8 "
                    "before parsing."
                ),
            }
        )
    if not contract["policy_present"]:
        findings.append(
            {
                "code": "CSV_KEY_POLICY_MISSING",
                "message": f"source does not declare policy {POLICY}.",
            }
        )
    if not contract["read_csv_has_dtype"] and controls["default_distinct_composite_keys"] != 2:
        findings.append(
            {
                "code": "DISTINCT_COMPOSITE_KEYS_COLLAPSE",
                "message": (
                    "default CSV inference collapses exact source_file_id tokens "
                    "'001' and '1' into one composite key."
                ),
            }
        )
    if not contract["read_csv_has_dtype"] and controls["default_false_cross_file_matches"] != 0:
        findings.append(
            {
                "code": "FALSE_CROSS_FILE_MATCH",
                "message": (
                    "default CSV inference creates a false data/MC match between "
                    "distinct exact source_file_id tokens."
                ),
            }
        )

    status = "VALIDATED" if not findings else "FLAWED"
    return {
        "schema": SCHEMA,
        "policy": POLICY,
        "status": status,
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
            "required_key_dtypes": {key: "string" for key in KEY_COLS},
            "required_snapshot": "SINGLE_READ_STRICT_UTF8",
            "expected_distinct_keys": 2,
            "expected_false_cross_file_matches": 0,
        },
        "environment": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
        },
        "scientific_boundary": (
            "This audit validates event-identifier integrity only; it does not validate "
            "A-002 amplitudes, stopping fractions, PID, calibration, or detector performance."
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
    tmp = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
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
