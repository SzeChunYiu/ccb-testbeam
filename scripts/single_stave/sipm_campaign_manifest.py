#!/usr/bin/env python3
"""Create and verify immutable SiPM sensitivity campaign intent manifests.

The manifest binds the expected ccb-sipm-core revision to the superproject
Gitlink at ``geant4/single_stave/sipm``. Callers never supply the expected
core SHA directly. A canonical SHA-256 over the manifest bytes is passed to
Slurm jobs so a post-submission manifest edit fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "ccb-sipm-campaign-intent/1"
CORE_PATH = "geant4/single_stave/sipm"
CORE_SOURCE = f"SUPERPROJECT_GITLINK:{CORE_PATH}"
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(RuntimeError):
    """Campaign intent is absent, mutable, malformed, or source-unbound."""


def canonical_git_sha(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not HEX40_RE.fullmatch(value) or value == "0" * 40:
        raise ManifestError(f"{field}: require canonical lowercase nonzero 40-hex Git SHA")
    return value


def canonical_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not HEX64_RE.fullmatch(value) or value == "0" * 64:
        raise ManifestError(f"{field}: require canonical lowercase nonzero 64-hex SHA-256")
    return value


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    text = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return (text + "\n").encode()


def _git(repo_root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ManifestError(f"git {' '.join(args)} failed: {detail.strip()}") from exc
    return proc.stdout.strip()


def require_clean_worktree(repo_root: Path) -> None:
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        first = status.splitlines()[0]
        raise ManifestError(
            "campaign intent requires a clean repository working tree; "
            f"first dirty entry: {first}"
        )


def repo_identities(repo_root: Path) -> tuple[str, str]:
    repo_commit = canonical_git_sha(
        _git(repo_root, "rev-parse", "HEAD"), field="superproject_commit"
    )
    row = _git(repo_root, "ls-tree", "HEAD", CORE_PATH)
    parts = row.split()
    if len(parts) < 3 or parts[1] != "commit":
        raise ManifestError(f"{CORE_PATH}: expected gitlink entry, got {row!r}")
    core_commit = canonical_git_sha(parts[2], field="ccb_sipm_core_commit")
    return repo_commit, core_commit


def selected_grid_files(grids_dir: Path, knobs: Iterable[str]) -> dict[str, str]:
    wanted = [k for k in knobs if k]
    if wanted:
        paths = [(k, grids_dir / f"points_{k}.csv") for k in sorted(set(wanted))]
    else:
        paths = [
            (p.stem.removeprefix("points_"), p)
            for p in sorted(grids_dir.glob("points_*.csv"))
        ]
    if not paths:
        raise ManifestError(f"no points_*.csv files found in {grids_dir}")
    out: dict[str, str] = {}
    for knob, path in paths:
        if not path.is_file():
            raise ManifestError(f"missing grid for knob {knob}: {path}")
        out[knob] = sha256_bytes(path.read_bytes())
    return out


def build_manifest(
    *,
    repo_commit: str,
    core_commit: str,
    base_cli: str,
    nevents_per_point: int,
    grid_sha256: dict[str, str],
) -> dict[str, Any]:
    repo_commit = canonical_git_sha(repo_commit, field="superproject_commit")
    core_commit = canonical_git_sha(core_commit, field="ccb_sipm_core_commit")
    if nevents_per_point <= 0:
        raise ManifestError("nevents_per_point must be positive")
    if not grid_sha256:
        raise ManifestError("grid_sha256 must contain at least one knob")
    grids: dict[str, str] = {}
    for knob in sorted(grid_sha256):
        if not knob or "/" in knob or knob in {".", ".."}:
            raise ManifestError(f"invalid knob name: {knob!r}")
        grids[knob] = canonical_sha256(grid_sha256[knob], field=f"grid_sha256[{knob}]")
    return {
        "schema": SCHEMA,
        "campaign_id": "SIPM-P2-001",
        "superproject_commit": repo_commit,
        "expected_core": {
            "path": CORE_PATH,
            "commit": core_commit,
            "source": CORE_SOURCE,
            "authorising_source": True,
        },
        "execution_intent": {
            "base_cli": base_cli,
            "nevents_per_point": int(nevents_per_point),
            "threads": 1,
        },
        "grid_sha256": grids,
    }


def validate_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a JSON object")
    if manifest.get("schema") != SCHEMA:
        raise ManifestError(f"schema must be {SCHEMA!r}")
    if manifest.get("campaign_id") != "SIPM-P2-001":
        raise ManifestError("campaign_id must be 'SIPM-P2-001'")
    canonical_git_sha(manifest.get("superproject_commit"), field="superproject_commit")
    expected = manifest.get("expected_core")
    if not isinstance(expected, dict):
        raise ManifestError("expected_core block missing")
    if expected.get("path") != CORE_PATH:
        raise ManifestError(f"expected_core.path must be {CORE_PATH!r}")
    canonical_git_sha(expected.get("commit"), field="expected_core.commit")
    if expected.get("source") != CORE_SOURCE or expected.get("authorising_source") is not True:
        raise ManifestError("expected core must be source-bound to the superproject gitlink")
    intent = manifest.get("execution_intent")
    if not isinstance(intent, dict) or not isinstance(intent.get("base_cli"), str):
        raise ManifestError("execution_intent.base_cli missing")
    nevents = intent.get("nevents_per_point")
    if not isinstance(nevents, int) or isinstance(nevents, bool) or nevents <= 0:
        raise ManifestError("execution_intent.nevents_per_point must be a positive integer")
    if intent.get("threads") != 1:
        raise ManifestError("execution_intent.threads must be exactly 1 for this campaign")
    grids = manifest.get("grid_sha256")
    if not isinstance(grids, dict) or not grids:
        raise ManifestError("grid_sha256 block missing or empty")
    for knob, digest in grids.items():
        if not isinstance(knob, str) or not knob or "/" in knob:
            raise ManifestError(f"invalid grid knob {knob!r}")
        canonical_sha256(digest, field=f"grid_sha256[{knob}]")
    return manifest


def load_and_verify_manifest(
    path: Path, *, expected_sha256: str | None = None
) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    actual_digest = sha256_bytes(raw)
    if expected_sha256 is not None:
        expected_digest = canonical_sha256(expected_sha256, field="expected manifest SHA-256")
        if actual_digest != expected_digest:
            raise ManifestError(
                "manifest byte digest mismatch: "
                f"actual {actual_digest} != expected {expected_digest}"
            )
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid manifest JSON: {exc}") from exc
    validate_manifest(manifest)
    if raw != canonical_manifest_bytes(manifest):
        raise ManifestError("manifest bytes are not canonical JSON for ccb-sipm-campaign-intent/1")
    return manifest, actual_digest


def write_manifest_once(path: Path, manifest: dict[str, Any]) -> str:
    validate_manifest(manifest)
    data = canonical_manifest_bytes(manifest)
    digest = sha256_bytes(data)
    if path.exists():
        if path.read_bytes() != data:
            raise ManifestError(f"refusing to overwrite different existing campaign intent: {path}")
        return digest
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o444)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
    return digest


def expected_core_sha(manifest: dict[str, Any]) -> str:
    validate_manifest(manifest)
    return canonical_git_sha(manifest["expected_core"]["commit"], field="expected_core.commit")


def verify_execution_intent(
    manifest: dict[str, Any],
    *,
    base_cli: str | None = None,
    nevents_per_point: int | None = None,
    threads: int | None = None,
) -> None:
    """Check runtime knobs against the frozen campaign execution intent."""
    validate_manifest(manifest)
    intent = manifest["execution_intent"]
    if base_cli is not None and base_cli != intent["base_cli"]:
        raise ManifestError(
            f"runtime base_cli {base_cli!r} != manifest {intent['base_cli']!r}"
        )
    if nevents_per_point is not None and nevents_per_point != intent["nevents_per_point"]:
        raise ManifestError(
            f"runtime nevents {nevents_per_point} != manifest {intent['nevents_per_point']}"
        )
    if threads is not None and threads != intent["threads"]:
        raise ManifestError(f"runtime threads {threads} != manifest {intent['threads']}")


def verify_source_binding(manifest: dict[str, Any], repo_root: Path) -> str:
    """Verify the declared expected core against its recorded superproject commit."""
    validate_manifest(manifest)
    repo_commit = canonical_git_sha(
        manifest["superproject_commit"], field="superproject_commit"
    )
    row = _git(repo_root, "ls-tree", repo_commit, CORE_PATH)
    parts = row.split()
    if len(parts) < 3 or parts[1] != "commit":
        raise ManifestError(
            f"{repo_commit}:{CORE_PATH}: expected gitlink entry, got {row!r}"
        )
    source_core = canonical_git_sha(parts[2], field="source gitlink core commit")
    expected = expected_core_sha(manifest)
    if source_core != expected:
        raise ManifestError(
            f"manifest expected core {expected} != gitlink {source_core} "
            f"at superproject commit {repo_commit}"
        )
    return expected


def _cmd_create(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    grids_dir = Path(args.grids_dir).resolve()
    manifest_path = Path(args.manifest).resolve()
    digest_path = Path(args.digest_file).resolve()
    require_clean_worktree(repo_root)
    repo_commit, core_commit = repo_identities(repo_root)
    grids = selected_grid_files(grids_dir, args.knobs or [])
    manifest = build_manifest(
        repo_commit=repo_commit,
        core_commit=core_commit,
        base_cli=args.base_cli,
        nevents_per_point=args.nevents,
        grid_sha256=grids,
    )
    digest = write_manifest_once(manifest_path, manifest)
    if digest_path.exists():
        existing = digest_path.read_text().strip()
        if existing != digest:
            raise ManifestError(f"refusing to overwrite different digest file: {digest_path}")
    else:
        digest_path.write_text(digest + "\n")
        digest_path.chmod(0o444)
    print(expected_core_sha(manifest))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    manifest, digest = load_and_verify_manifest(
        Path(args.manifest), expected_sha256=args.expected_sha256
    )
    source_core = verify_source_binding(manifest, Path(args.repo_root).resolve())
    verify_execution_intent(
        manifest,
        base_cli=args.base_cli,
        nevents_per_point=args.nevents,
        threads=args.threads,
    )
    if args.digest_file:
        recorded = Path(args.digest_file).read_text().strip()
        canonical_sha256(recorded, field="digest file")
        if digest != recorded:
            raise ManifestError(f"manifest digest {digest} != digest file {recorded}")
    if (args.grid_knob is None) != (args.grid_file is None):
        raise ManifestError("--grid-knob and --grid-file must be supplied together")
    if args.grid_knob is not None:
        grids = manifest["grid_sha256"]
        if args.grid_knob not in grids:
            raise ManifestError(f"grid knob {args.grid_knob!r} is not declared in manifest")
        actual_grid = sha256_bytes(Path(args.grid_file).read_bytes())
        expected_grid = grids[args.grid_knob]
        if actual_grid != expected_grid:
            raise ManifestError(
                f"grid digest mismatch for {args.grid_knob}: "
                f"actual {actual_grid} != expected {expected_grid}"
            )
    print(source_core)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="derive immutable campaign intent from repository bytes")
    c.add_argument("--repo-root", required=True)
    c.add_argument("--grids-dir", required=True)
    c.add_argument("--manifest", required=True)
    c.add_argument("--digest-file", required=True)
    c.add_argument("--base-cli", required=True)
    c.add_argument("--nevents", required=True, type=int)
    c.add_argument("--knobs", nargs="*", default=None)
    c.set_defaults(func=_cmd_create)

    v = sub.add_parser("verify", help="verify manifest bytes and source-bound core identity")
    v.add_argument("--repo-root", required=True)
    v.add_argument("--manifest", required=True)
    v.add_argument("--expected-sha256", default=None)
    v.add_argument("--digest-file", default=None)
    v.add_argument("--base-cli", default=None)
    v.add_argument("--nevents", type=int, default=None)
    v.add_argument("--threads", type=int, default=None)
    v.add_argument("--grid-knob", default=None)
    v.add_argument("--grid-file", default=None)
    v.set_defaults(func=_cmd_verify)

    args = ap.parse_args()
    try:
        return int(args.func(args))
    except (ManifestError, OSError) as exc:
        print(f"error: campaign manifest provenance gate failed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
