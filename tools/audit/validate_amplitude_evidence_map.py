#!/usr/bin/env python3
"""Validate amplitude-convention evidence maps before physics use."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

TOOL_VERSION = "1.2.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACCEPTED_CONVENTIONS = {"ABSOLUTE", "NET"}
ACCEPTED_EVIDENCE_BASES = {
    "EXPLICIT_SCHEMA_METADATA",
    "PRODUCER_CODE_PROVENANCE",
    "INDEPENDENTLY_REVIEWED_PEDESTAL_EVIDENCE",
}


class ValidatedEvidenceMap(dict[str, dict[str, Any]]):
    """Evidence map carrying whether supporting-artifact bytes were verified."""

    def __init__(
        self,
        *args: Any,
        references_verified: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.references_verified = references_verified


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sha256(value: Any, field: str, digest: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(
            f"evidence record for {digest} requires canonical lowercase hexadecimal {field}"
        )
    return value


def _resolve_reference_path(reference: str, evidence_root: Path, digest: str) -> Path:
    reference_file = reference.split("#", 1)[0].strip()
    if not reference_file:
        raise ValueError(
            f"evidence record for {digest} has no file path before evidence_reference fragment"
        )
    relative = Path(reference_file)
    if relative.is_absolute():
        raise ValueError(
            f"evidence record for {digest} must use a relative evidence_reference path"
        )
    root = evidence_root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"evidence record for {digest} escapes the configured evidence root"
        ) from exc
    if not resolved.is_file():
        raise ValueError(
            f"evidence record for {digest} references missing file {reference_file!r}"
        )
    return resolved


def validate_record(
    digest: str,
    record: Any,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
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
    reference = reference.strip()

    reference_sha256 = _validate_sha256(
        record.get("evidence_reference_sha256"), "evidence_reference_sha256", digest
    )

    embedded_digest = record.get("sha256")
    if embedded_digest is not None and embedded_digest != digest:
        raise ValueError(f"evidence record for {digest} has mismatched sha256")

    normalized = dict(record)
    normalized["evidence_reference"] = reference
    normalized["evidence_reference_sha256"] = reference_sha256
    normalized["sha256"] = digest
    normalized["evidence_reference_verified"] = False

    if evidence_root is not None:
        resolved = _resolve_reference_path(reference, evidence_root, digest)
        actual_reference_sha256 = file_sha256(resolved)
        if actual_reference_sha256 != reference_sha256:
            raise ValueError(
                f"evidence record for {digest} has evidence_reference_sha256 mismatch: "
                f"declared {reference_sha256}, measured {actual_reference_sha256}"
            )
        normalized["evidence_reference_verified"] = True
        normalized["evidence_reference_resolved_path"] = str(resolved)
        normalized["evidence_reference_measured_sha256"] = actual_reference_sha256

    return normalized


def validate_payload(
    payload: Any,
    evidence_root: Path | None = None,
) -> ValidatedEvidenceMap:
    if not isinstance(payload, dict):
        raise ValueError("evidence map must be a JSON object keyed by SHA-256")
    return ValidatedEvidenceMap(
        {
            digest: validate_record(digest, record, evidence_root=evidence_root)
            for digest, record in payload.items()
        },
        references_verified=evidence_root is not None,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_map", type=Path)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=None,
        help=(
            "Root directory for evidence_reference paths. Defaults to the evidence-map "
            "directory. References must resolve to files beneath this root."
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = json.loads(args.evidence_map.read_text(encoding="utf-8"))
    evidence_root = args.evidence_root or args.evidence_map.parent
    normalized = validate_payload(payload, evidence_root=evidence_root)
    result = {
        "tool": "tools/audit/validate_amplitude_evidence_map.py",
        "tool_version": TOOL_VERSION,
        "evidence_map": str(args.evidence_map),
        "evidence_root": str(evidence_root.resolve()),
        "n_records": len(normalized),
        "n_verified_references": sum(
            bool(record["evidence_reference_verified"])
            for record in normalized.values()
        ),
        "records": normalized,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"records={len(normalized)} "
        f"verified_references={result['n_verified_references']} validated=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
