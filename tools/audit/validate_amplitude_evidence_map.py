#!/usr/bin/env python3
"""Validate amplitude-convention evidence maps before physics use."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TOOL_VERSION = "1.1.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACCEPTED_CONVENTIONS = {"ABSOLUTE", "NET"}
ACCEPTED_EVIDENCE_BASES = {
    "EXPLICIT_SCHEMA_METADATA",
    "PRODUCER_CODE_PROVENANCE",
    "INDEPENDENTLY_REVIEWED_PEDESTAL_EVIDENCE",
}


def _validate_sha256(value: Any, field: str, digest: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(
            f"evidence record for {digest} requires canonical lowercase hexadecimal {field}"
        )
    return value


def validate_record(digest: str, record: Any) -> dict[str, Any]:
    """Return a normalized record or raise ValueError for non-traceable evidence."""
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise ValueError(
            "evidence-map keys must be lowercase 64-character hexadecimal SHA-256 strings"
        )
    if not isinstance(record, dict):
        raise ValueError(f"evidence record for {digest} must be an object")

    convention = record.get("convention")
    if convention not in ACCEPTED_CONVENTIONS:
        raise ValueError(f"evidence record for {digest} has invalid convention")

    basis = record.get("evidence_basis")
    if basis not in ACCEPTED_EVIDENCE_BASES:
        raise ValueError(f"evidence record for {digest} has invalid evidence_basis")

    reference = record.get("evidence_reference")
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError(
            f"evidence record for {digest} requires a non-empty evidence_reference"
        )

    reference_sha256 = _validate_sha256(
        record.get("evidence_reference_sha256"), "evidence_reference_sha256", digest
    )

    embedded_digest = record.get("sha256")
    if embedded_digest is not None and embedded_digest != digest:
        raise ValueError(f"evidence record for {digest} has mismatched sha256")

    normalized = dict(record)
    normalized["evidence_reference"] = reference.strip()
    normalized["evidence_reference_sha256"] = reference_sha256
    normalized["sha256"] = digest
    return normalized


def validate_payload(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("evidence map must be a JSON object keyed by SHA-256")
    return {digest: validate_record(digest, record) for digest, record in payload.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_map", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = json.loads(args.evidence_map.read_text(encoding="utf-8"))
    normalized = validate_payload(payload)
    result = {
        "tool": "tools/audit/validate_amplitude_evidence_map.py",
        "tool_version": TOOL_VERSION,
        "evidence_map": str(args.evidence_map),
        "n_records": len(normalized),
        "records": normalized,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"records={len(normalized)} validated=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
