"""Study manifest writer and verifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ccb_mc_validation.exceptions import ManifestError
from ccb_mc_validation.io.artifact_store import atomic_write, write_json
from ccb_mc_validation.provenance.environment import capture_environment
from ccb_mc_validation.provenance.hashing import sha256_file


def write_manifest(
    out_dir: Path | str,
    *,
    study: str,
    inputs: dict[str, Path | str] | None = None,
    commands: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write ``manifest.json`` with environment, input hashes, and output checksums."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    input_files = inputs or {}
    input_sha = {
        str(path): {
            "sha256": sha256_file(path),
            "bytes": Path(path).stat().st_size,
        }
        for path in sorted(input_files.values(), key=str)
    }

    payload: dict[str, Any] = {
        "study": study,
        "environment": capture_environment(),
        "commands": list(commands or []),
        "input_files": input_sha,
        "metadata": dict(metadata or {}),
        "output_sha256": {},
    }

    write_json(manifest_path, payload)

    outputs = sorted(p for p in out_dir.iterdir() if p.is_file() and p.name != "manifest.json")
    payload["output_sha256"] = {p.name: sha256_file(p) for p in outputs}
    write_json(manifest_path, payload)
    return manifest_path


def verify_manifest(manifest_path: Path | str) -> dict[str, Any]:
    """Verify output files listed in a manifest still match recorded digests."""
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise ManifestError(f"manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = manifest_path.parent
    recorded = manifest.get("output_sha256", {})
    mismatches: list[dict[str, str]] = []
    missing: list[str] = []

    for name, expected in recorded.items():
        path = out_dir / name
        if not path.exists():
            missing.append(name)
            continue
        actual = sha256_file(path)
        if actual != expected:
            mismatches.append({"file": name, "expected": expected, "actual": actual})

    ok = not mismatches and not missing
    report = {
        "ok": ok,
        "n_checked": len(recorded),
        "missing": missing,
        "mismatches": mismatches,
    }
    if not ok:
        raise ManifestError(f"manifest verification failed: {report}")
    return report
