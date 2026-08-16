#!/usr/bin/env python3
"""Validate amplitude-convention evidence maps before physics use."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

TOOL_VERSION = "1.4.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LINE_FRAGMENT_RE = re.compile(r"^L([1-9][0-9]*)(?:-L([1-9][0-9]*))?$")
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


def _parse_reference(
    reference: str,
    digest: str,
) -> tuple[str, tuple[int, int] | None]:
    reference_file, separator, fragment = reference.partition("#")
    reference_file = reference_file.strip()
    if not reference_file:
        raise ValueError(
            f"evidence record for {digest} has no file path before evidence_reference fragment"
        )
    if not separator:
        return reference_file, None
    if not fragment:
        raise ValueError(
            f"evidence record for {digest} has an empty evidence_reference fragment"
        )
    match = LINE_FRAGMENT_RE.fullmatch(fragment)
    if not match:
        raise ValueError(
            f"evidence record for {digest} must use a canonical line fragment "
            "(#L<start> or #L<start>-L<end>)"
        )
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if end < start:
        raise ValueError(
            f"evidence record for {digest} has an evidence_reference line range "
            "whose end precedes its start"
        )
    return reference_file, (start, end)


def _resolve_reference_path(reference_file: str, evidence_root: Path, digest: str) -> Path:
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


def _verify_line_range(
    resolved: Path,
    line_range: tuple[int, int],
    digest: str,
) -> dict[str, int | str]:
    lines = resolved.read_bytes().splitlines(keepends=True)
    line_count = len(lines)
    start, end = line_range
    if end > line_count:
        raise ValueError(
            f"evidence record for {digest} references lines {start}-{end}, "
            f"but the supporting artifact has only {line_count} lines"
        )
    selected_lines = lines[start - 1:end]
    selected_bytes = b"".join(selected_lines)
    nonblank_lines = sum(bool(line.strip()) for line in selected_lines)
    if nonblank_lines == 0:
        raise ValueError(
            f"evidence record for {digest} references lines {start}-{end} containing "
            "only blank or whitespace content"
        )
    return {
        "line_count": line_count,
        "size_bytes": len(selected_bytes),
        "nonblank_lines": nonblank_lines,
        "sha256": hashlib.sha256(selected_bytes).hexdigest(),
    }


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
    reference_file, line_range = _parse_reference(reference, digest)

    reference_sha256 = _validate_sha256(
        record.get("evidence_reference_sha256"), "evidence_reference_sha256", digest
    )

    embedded_digest = record.get("sha256")
    if embedded_digest is not None and embedded_digest != digest:
        raise ValueError(f"evidence record for {digest} has mismatched sha256")

    normalized = dict(record)
    normalized["evidence_reference"] = reference
    normalized["evidence_reference_file"] = reference_file
    normalized["evidence_reference_scope"] = (
        "LINE_RANGE" if line_range is not None else "WHOLE_FILE"
    )
    normalized["evidence_reference_sha256"] = reference_sha256
    normalized["sha256"] = digest
    normalized["evidence_validator_version"] = TOOL_VERSION
    normalized["evidence_reference_verified"] = False
    normalized["evidence_reference_fragment_verified"] = False
    if line_range is not None:
        normalized["evidence_reference_line_start"] = line_range[0]
        normalized["evidence_reference_line_end"] = line_range[1]

    if evidence_root is not None:
        resolved = _resolve_reference_path(reference_file, evidence_root, digest)
        actual_reference_sha256 = file_sha256(resolved)
        if actual_reference_sha256 != reference_sha256:
            raise ValueError(
                f"evidence record for {digest} has evidence_reference_sha256 mismatch: "
                f"declared {reference_sha256}, measured {actual_reference_sha256}"
            )
        normalized["evidence_reference_verified"] = True
        normalized["evidence_reference_resolved_path"] = str(resolved)
        normalized["evidence_reference_measured_sha256"] = actual_reference_sha256
        if line_range is not None:
            fragment = _verify_line_range(resolved, line_range, digest)
            normalized["evidence_reference_line_count"] = fragment["line_count"]
            normalized["evidence_reference_fragment_size_bytes"] = fragment["size_bytes"]
            normalized["evidence_reference_fragment_nonblank_lines"] = fragment[
                "nonblank_lines"
            ]
            normalized["evidence_reference_fragment_sha256"] = fragment["sha256"]
            normalized["evidence_reference_fragment_verified"] = True

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
            "directory. References must resolve to files beneath this root. Optional "
            "fragments must be canonical line ranges such as #L12 or #L12-L18."
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
        "n_verified_line_fragments": sum(
            bool(record["evidence_reference_fragment_verified"])
            for record in normalized.values()
        ),
        "records": normalized,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"records={len(normalized)} "
        f"verified_references={result['n_verified_references']} "
        f"verified_line_fragments={result['n_verified_line_fragments']} validated=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
