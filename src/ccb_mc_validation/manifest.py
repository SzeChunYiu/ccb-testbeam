"""Manifest read/write helpers for MC validation artifact directories."""

from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import Any

from ccb_mc_validation.config import sha256_file
from ccb_mc_validation.exceptions import ManifestError
from ccb_mc_validation.schemas import ManifestRecord


def _git_value(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_manifest_record(
    *,
    study_id: str,
    ticket: str,
    config_path: Path,
    out_dir: Path,
    inputs: dict[str, Path] | None = None,
    outputs: list[str] | None = None,
) -> ManifestRecord:
    """Construct a :class:`ManifestRecord` from runtime provenance."""
    repo_root = config_path.resolve().parents[2] if "configs" in config_path.parts else Path.cwd()
    input_pairs: list[tuple[str, str]] = []
    for label, path in (inputs or {}).items():
        resolved = path.resolve()
        digest = sha256_file(resolved) if resolved.is_file() else "missing"
        input_pairs.append((f"{label}:{resolved.name}", digest))

    if outputs is None:
        outputs = sorted(p.name for p in out_dir.iterdir() if p.is_file() and p.name != "manifest.json")
    output_records: list[dict[str, Any]] = []
    for _out_name in outputs:
        _out_fp = out_dir / _out_name
        if _out_fp.is_file():
            output_records.append({"name": _out_name, "size_bytes": _out_fp.stat().st_size, "sha256": sha256_file(_out_fp)})
        else:
            output_records.append({"name": _out_name, "size_bytes": None, "sha256": "missing"})

    return ManifestRecord(
        study_id=study_id,
        ticket=ticket,
        config_path=str(config_path.resolve()),
        config_sha256=sha256_file(config_path),
        git_head=_git_value(["rev-parse", "HEAD"], repo_root),
        git_branch=_git_value(["rev-parse", "--abbrev-ref", "HEAD"], repo_root),
        python_version=platform.python_version(),
        inputs=tuple(input_pairs),
        outputs=tuple(output_records),
    )


def write_manifest(out_dir: str | Path, record: ManifestRecord) -> Path:
    """Write ``manifest.json`` under *out_dir*."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "manifest.json"
    path.write_text(json.dumps(record.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load a manifest JSON file."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise ManifestError(f"manifest not found: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ManifestError("manifest root must be a mapping")
    return payload


def verify_manifest(path: str | Path, *, expected_study_id: str | None = None, strict_outputs: bool = True) -> bool:
    """Verify manifest structure, study id, and output integrity (fail-closed).

    Output records (new format) carry {name, size_bytes, sha256}; each is re-hashed
    and compared, and missing outputs raise. Legacy name-only outputs cannot be
    proven and raise under ``strict_outputs`` (default).
    """
    payload = load_manifest(path)
    required = {"study_id", "config_path", "config_sha256", "outputs"}
    missing = required - set(payload)
    if missing:
        raise ManifestError(f"manifest missing keys: {sorted(missing)}")
    if expected_study_id is not None and payload["study_id"] != expected_study_id:
        raise ManifestError(
            f"manifest study_id mismatch: expected {expected_study_id!r}, got {payload['study_id']!r}"
        )
    outputs = payload["outputs"]
    if not isinstance(outputs, list):
        raise ManifestError("manifest.outputs must be a list")
    manifest_dir = Path(path).resolve().parent
    for rec in outputs:
        if isinstance(rec, dict):
            name = rec.get("name")
            exp_sha = rec.get("sha256")
            fp = manifest_dir / name
            if not fp.is_file():
                raise ManifestError(f"output missing: {name}")
            if exp_sha and exp_sha != "missing":
                actual = sha256_file(fp)
                if actual != exp_sha:
                    raise ManifestError(f"output altered (sha256 mismatch): {name}")
        elif isinstance(rec, str):
            if strict_outputs:
                raise ManifestError(f"legacy unhashed output cannot be verified (strict): {rec}")
            fp = manifest_dir / rec
            if not fp.is_file():
                raise ManifestError(f"output missing: {rec}")
    return True
