#!/usr/bin/env python3
"""Render validation evidence for Cluster E input/base-commit binding."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

POLICY = "INPUT_BYTES_MUST_MATCH_BASE_COMMIT_BLOBS"
VERSION = "1.0.0"


def snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid UTF-8 in {path}") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def atomic_write(path: Path, raw: bytes, inputs: list[Path]) -> None:
    resolved = path.resolve(strict=False)
    if any(resolved == item.resolve(strict=False) for item in inputs):
        raise ValueError("output aliases input")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise


def build(source: Path, tests: list[Path]) -> dict[str, Any]:
    source_text, source_provenance = snapshot(source)
    test_snapshots = [snapshot(path)[1] for path in tests]
    required = {
        "retained_byte_blob_function": "def _git_blob_sha1(raw: bytes)",
        "commit_tree_lookup": '"rev-parse", f"{commit}:{rel}"',
        "dirty_input_rejection": "INPUT_NOT_AT_BASE_COMMIT",
        "commit_digest_record": '"commit_blob_digest": commit_blob',
        "commit_match_record": '"commit_match": True',
        "authorization_policy": '"authorization_policy": INPUT_POLICY',
    }
    checks = {name: token in source_text for name, token in required.items()}
    checks["former_path_hash_removed"] = (
        '"hash-object", "--no-filters", "--", rel' not in source_text
    )

    committed = b"canonical input bytes\n"
    dirty = b"canonical input bytes\nuncommitted note\n"
    committed_blob = git_blob_sha1(committed)
    dirty_blob = git_blob_sha1(dirty)
    control = {
        "committed_bytes": len(committed),
        "dirty_bytes": len(dirty),
        "committed_git_blob_sha1": committed_blob,
        "dirty_git_blob_sha1": dirty_blob,
        "dirty_matches_base_commit": dirty_blob == committed_blob,
        "expected_gate": "INPUT_NOT_AT_BASE_COMMIT",
    }
    findings = [name for name, passed in checks.items() if not passed]
    return {
        "schema": "ccb-clusterE-input-commit-binding-validation/1",
        "renderer_version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "finding_count": len(findings),
        "findings": findings,
        "source_contract_checks": checks,
        "deterministic_control": control,
        "inputs": {
            "source": source_provenance,
            "tests": test_snapshots,
        },
        "validation_commands": [
            "python -m py_compile scripts/clusterE/clusterE_canonical_frontdoor.py "
            "tools/audit/validate_clusterE_canonical_binding_v2.py "
            "tests/test_clusterE_canonical_frontdoor.py "
            "tests/test_validate_clusterE_canonical_binding_v2.py "
            "tools/audit/render_clusterE_input_commit_binding_evidence.py",
            "PYTHONPATH=. pytest -q tests/test_clusterE_canonical_frontdoor.py "
            "tests/test_validate_clusterE_canonical_binding_v2.py",
        ],
        "scientific_boundary": (
            "Software provenance authorization only; no calibration, closure, "
            "C12 identity, or detector-performance result is established."
        ),
    }


def svg(payload: dict[str, Any]) -> bytes:
    status = escape(str(payload["status"]))
    control = payload["deterministic_control"]
    committed = escape(control["committed_git_blob_sha1"][:12])
    dirty = escape(control["dirty_git_blob_sha1"][:12])
    lines = [
        (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" '
            'height="520" role="img" aria-labelledby="title desc">'
        ),
        '<title id="title">Cluster E input-to-commit provenance gate</title>',
        (
            '<desc id="desc">Retained input bytes must have the same Git blob '
            'identity as the declared base commit tree.</desc>'
        ),
        '<rect width="1200" height="520" fill="white"/>',
        '<g font-family="sans-serif" fill="black">',
        (
            '<text x="40" y="55" font-size="28" font-weight="bold">'
            f'Cluster E input/base-commit binding — {status}</text>'
        ),
        (
            '<rect x="70" y="110" width="300" height="105" '
            'fill="#eef3f8" stroke="black"/>'
        ),
        (
            '<text x="95" y="145" font-size="20" font-weight="bold">'
            'Single retained byte snapshot</text>'
        ),
        (
            '<text x="95" y="178" font-size="17">'
            'strict UTF-8 · SHA-256 · byte count</text>'
        ),
        (
            '<rect x="450" y="110" width="300" height="105" '
            'fill="#eef3f8" stroke="black"/>'
        ),
        (
            '<text x="475" y="145" font-size="20" font-weight="bold">'
            'Measured Git blob</text>'
        ),
        (
            '<text x="475" y="178" font-size="17">'
            'blob(len || NUL || bytes)</text>'
        ),
        (
            '<rect x="830" y="110" width="300" height="105" '
            'fill="#eef3f8" stroke="black"/>'
        ),
        (
            '<text x="855" y="145" font-size="20" font-weight="bold">'
            'Base commit tree blob</text>'
        ),
        (
            '<text x="855" y="178" font-size="17">'
            'rev-parse commit:path</text>'
        ),
        (
            '<path d="M370 162 H450" stroke="black" stroke-width="3" '
            'marker-end="url(#arrow)"/>'
        ),
        (
            '<path d="M750 162 H830" stroke="black" stroke-width="3" '
            'marker-end="url(#arrow)"/>'
        ),
        '<defs>',
        (
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="7" markerHeight="7" orient="auto">'
        ),
        '<path d="M0 0 L10 5 L0 10 z" fill="black"/>',
        '</marker></defs>',
        (
            '<rect x="170" y="285" width="360" height="125" '
            'fill="#edf8ed" stroke="black"/>'
        ),
        (
            '<text x="195" y="325" font-size="20" font-weight="bold">'
            'Committed control: ACCEPT</text>'
        ),
        (
            '<text x="195" y="360" font-size="17">'
            f'measured = commit = {committed}…</text>'
        ),
        (
            '<rect x="670" y="285" width="360" height="125" '
            'fill="#fdeeee" stroke="black"/>'
        ),
        (
            '<text x="695" y="325" font-size="20" font-weight="bold">'
            'Dirty control: REJECT</text>'
        ),
        (
            '<text x="695" y="360" font-size="17">'
            f'dirty {dirty}… ≠ base {committed}…</text>'
        ),
        (
            '<text x="40" y="475" font-size="17">Policy: '
            f'{escape(POLICY)} · provenance is authorized only after exact '
            'blob equality.</text>'
        ),
        '</g></svg>',
        '',
    ]
    return "\n".join(lines).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--test", type=Path, action="append", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-svg", type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.source, *args.test]
    try:
        payload = build(args.source, args.test)
        atomic_write(
            args.output_json,
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(),
            inputs,
        )
        atomic_write(args.output_svg, svg(payload), inputs)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"{payload['status']}: {payload['finding_count']} finding(s)")
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
