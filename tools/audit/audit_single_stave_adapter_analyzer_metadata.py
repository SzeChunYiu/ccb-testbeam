#!/usr/bin/env python3
"""Audit adapter metadata against the current single-stave analyzer contract."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

VERSION = "1.1.0"
POLICY = "ADAPTER_METADATA_MUST_MATCH_CURRENT_ANALYZER_OPTICAL_CONTRACT"
EXPECTED_ANALYZER_VERSION = "2.1.0"
EXPECTED_ANALYZER_POLICY = (
    "ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL_AND_DECLARE_EXPLICIT_ENERGY_TARGET"
)
EXPECTED_COMPATIBILITY = "SCHEMA_AND_OPTICAL_BOOKKEEPING_COMPATIBLE"
EXPECTED_CONTRACT = "CURRENT_COMPONENT_SUM"
EXPECTED_DENOMINATOR = "n_optical_generated_total"
EXPECTED_ACCEPTANCE = "SOFTWARE_CONTRACT_VALIDATED_REAL_ROOT_PENDING"
STALE_PHRASES = (
    "still validates arrivals against",
    "n_scint_generated alone",
    "must use n_optical_generated_total",
)


def _read_utf8(path: Path) -> tuple[str, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path}: invalid UTF-8 at byte {exc.start}") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _constant(tree: ast.AST, name: str) -> str | None:
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    return None


def _payload_string_values(tree: ast.AST) -> dict[str, str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        has_payload_target = any(
            isinstance(target, ast.Name) and target.id == "payload"
            for target in node.targets
        )
        if not has_payload_target:
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        values: dict[str, str] = {}
        for key, value in zip(node.value.keys, node.value.values):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                continue
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                values[key.value] = value.value
        return values
    return {}


def _function_source(text: str, tree: ast.AST, name: str) -> str:
    lines = text.splitlines()
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            end = getattr(node, "end_lineno", node.lineno)
            return "\n".join(lines[node.lineno - 1 : end])
    return ""


def audit_sources(adapter: str, analyzer: str, contract: str) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    adapter_tree = ast.parse(adapter)
    analyzer_tree = ast.parse(analyzer)

    analyzer_version = _constant(analyzer_tree, "VERSION")
    analyzer_policy = _constant(analyzer_tree, "POLICY")
    if analyzer_version != EXPECTED_ANALYZER_VERSION:
        findings.append(
            {
                "code": "ANALYZER_VERSION_MISMATCH",
                "detail": f"expected {EXPECTED_ANALYZER_VERSION}, got {analyzer_version!r}",
            }
        )
    if analyzer_policy != EXPECTED_ANALYZER_POLICY:
        findings.append(
            {
                "code": "ANALYZER_POLICY_MISMATCH",
                "detail": f"expected {EXPECTED_ANALYZER_POLICY}, got {analyzer_policy!r}",
            }
        )

    denominator_source = _function_source(analyzer, analyzer_tree, "generated_optical_denominator")
    collection_source = _function_source(analyzer, analyzer_tree, "collection_efficiency_frame")
    if "return OPTICAL_TOTAL, contract" not in denominator_source:
        findings.append(
            {
                "code": "ANALYZER_TOTAL_DENOMINATOR_NOT_PROVEN",
                "detail": "current-contract branch does not visibly return OPTICAL_TOTAL",
            }
        )
    if 'selected["n_end_selected"] / selected[denominator]' not in collection_source:
        findings.append(
            {
                "code": "ANALYZER_COLLECTION_DENOMINATOR_NOT_BOUND",
                "detail": (
                    "collection efficiency is not visibly divided by the selected "
                    "denominator"
                ),
            }
        )

    payload = _payload_string_values(adapter_tree)
    compatibility = payload.get("analysis_compatibility")
    if compatibility != EXPECTED_COMPATIBILITY:
        findings.append(
            {
                "code": "ADAPTER_COMPATIBILITY_STALE",
                "detail": f"expected {EXPECTED_COMPATIBILITY}, got {compatibility!r}",
            }
        )

    lower_adapter = adapter.lower()
    for phrase in STALE_PHRASES:
        if phrase in lower_adapter:
            findings.append(
                {
                    "code": "STALE_ANALYZER_BLOCKER_PUBLISHED",
                    "detail": phrase,
                }
            )

    required_tokens = {
        "analyzer version": EXPECTED_ANALYZER_VERSION,
        "analyzer policy": EXPECTED_ANALYZER_POLICY,
        "optical contract": EXPECTED_CONTRACT,
        "collection denominator": EXPECTED_DENOMINATOR,
        "acceptance": EXPECTED_ACCEPTANCE,
    }
    for label, token in required_tokens.items():
        if token not in adapter:
            findings.append(
                {
                    "code": "ADAPTER_METADATA_TOKEN_MISSING",
                    "detail": f"{label}: {token}",
                }
            )

    contract_normalized = " ".join(contract.lower().split())
    if "analyzer version 2.0.0" not in contract_normalized:
        findings.append(
            {
                "code": "CONTRACT_ANALYZER_VERSION_MISSING",
                "detail": "EVENT_CONTRACT.md does not bind analyzer version 2.0.0",
            }
        )
    if "uses the exact total-optical count" not in contract_normalized:
        findings.append(
            {
                "code": "CONTRACT_TOTAL_DENOMINATOR_MISSING",
                "detail": "EVENT_CONTRACT.md does not state exact total-optical use",
            }
        )

    return {
        "schema": "ccb-single-stave-adapter-analyzer-metadata-audit/1",
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "finding_count": len(findings),
        "findings": findings,
        "observed": {
            "analyzer_version": analyzer_version,
            "analyzer_policy": analyzer_policy,
            "adapter_analysis_compatibility": compatibility,
        },
        "expected": {
            "analysis_compatibility": EXPECTED_COMPATIBILITY,
            "analyzer_version": EXPECTED_ANALYZER_VERSION,
            "analyzer_policy": EXPECTED_ANALYZER_POLICY,
            "optical_generation_contract": EXPECTED_CONTRACT,
            "collection_efficiency_denominator": EXPECTED_DENOMINATOR,
            "acceptance": EXPECTED_ACCEPTANCE,
        },
        "scientific_boundary": (
            "Software/documentation provenance only; no immutable real ROOT execution, "
            "optical-yield measurement, calibration, resolution, PID, or detector-performance "
            "claim is established."
        ),
    }


def _write_json_atomic(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(fd)
    temp = Path(name)
    try:
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--analyzer", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resolved = [args.adapter.resolve(), args.analyzer.resolve(), args.contract.resolve()]
    if args.output_json is not None and args.output_json.resolve() in resolved:
        raise SystemExit("output JSON must not alias an input")
    try:
        adapter, adapter_meta = _read_utf8(resolved[0])
        analyzer, analyzer_meta = _read_utf8(resolved[1])
        contract, contract_meta = _read_utf8(resolved[2])
        payload = audit_sources(adapter, analyzer, contract)
    except (OSError, ValueError, SyntaxError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, sort_keys=True))
        return 2
    payload["inputs"] = {
        "adapter": adapter_meta,
        "analyzer": analyzer_meta,
        "contract": contract_meta,
    }
    if args.output_json is not None:
        _write_json_atomic(payload, args.output_json)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
