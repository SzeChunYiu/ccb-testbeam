#!/usr/bin/env python3
"""Validate the external hibeam_g4 source overlay before compilation.

The reviewed CCB ``ScatteringGenerator`` pair is installed into an external
``hibeam_g4`` checkout. That means a useful pre-build contract cannot simply
require ``git status`` to be clean: the reviewed overlay is itself an expected
working-tree delta unless the pinned upstream commit already contains identical
bytes.

This validator therefore binds two layers separately:

1. the external repository baseline is an exact approved HEAD commit/tree;
2. every visible Git delta is restricted to the two reviewed source paths,
   remains unstaged, and those paths equal the exact repository payload bytes.

Any extra tracked change, staged change, untracked file, wrong baseline, source
symlink, or partial/incorrect overlay fails closed. Passing this validator is a
pre-build source-identity condition only; it does not compile or run Geant4 and
therefore cannot authorise generator or detector claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "ccb_geant4_external_overlay_v1"
PAYLOADS = {
    "include/ScatteringGenerator.hh": Path(
        "geant4/src_patch/ScatteringGenerator.hh"
    ),
    "src/ScatteringGenerator.cc": Path("geant4/src_patch/ScatteringGenerator.cc"),
}


def _git(root: Path, *args: str, text: bool = True) -> str | bytes:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=text,
    )
    if proc.returncode != 0:
        if text:
            stderr = proc.stderr.strip()
        else:
            stderr = proc.stderr.decode(errors="replace").strip()
        raise ValueError(f"git {' '.join(args)} failed: {stderr}")
    return proc.stdout.strip() if text else proc.stdout


def _identity(st: os.stat_result) -> tuple[int, int, int, int, int]:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _regular_file_bytes(path: Path) -> bytes:
    try:
        st = path.lstat()
    except OSError as exc:
        raise ValueError(f"cannot inspect required file {path}: {exc}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"required file must be a regular non-symlink file: {path}")

    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        data = stream.read()
        after = os.fstat(stream.fileno())
    final = path.lstat()

    if _identity(before) != _identity(after) or _identity(after) != _identity(final):
        raise ValueError(f"required file changed while being verified: {path}")
    if len(data) != before.st_size:
        raise ValueError(f"short/long read while verifying required file: {path}")
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _status_entries(root: Path) -> list[tuple[str, str]]:
    raw = _git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        text=False,
    )
    assert isinstance(raw, bytes)
    entries: list[tuple[str, str]] = []
    parts = raw.split(b"\0")
    index = 0
    while index < len(parts):
        entry = parts[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4:
            raise ValueError("malformed git status entry")
        code = entry[:2].decode("ascii", errors="strict")
        path = entry[3:].decode("utf-8", errors="surrogateescape")
        if "R" in code or "C" in code:
            if index >= len(parts) or not parts[index]:
                raise ValueError("malformed rename/copy git status entry")
            other = parts[index].decode("utf-8", errors="surrogateescape")
            index += 1
            path = f"{path} -> {other}"
        entries.append((code, path))
    return entries


def validate_external_overlay(
    external_root: Path,
    repo_root: Path,
    expected_commit: str,
    expected_tree: str,
) -> dict[str, Any]:
    external_root = external_root.resolve()
    repo_root = repo_root.resolve()
    if not external_root.is_dir():
        raise ValueError(f"external root is not a directory: {external_root}")
    if not repo_root.is_dir():
        raise ValueError(f"repository root is not a directory: {repo_root}")

    inside = _git(external_root, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        raise ValueError("external root is not inside a Git work tree")

    head = _git(external_root, "rev-parse", "--verify", "HEAD")
    tree = _git(external_root, "rev-parse", "HEAD^{tree}")
    assert isinstance(head, str) and isinstance(tree, str)
    if head != expected_commit:
        raise ValueError(
            f"external HEAD mismatch: expected {expected_commit}, observed {head}"
        )
    if tree != expected_tree:
        raise ValueError(
            f"external HEAD tree mismatch: expected {expected_tree}, observed {tree}"
        )

    allowed = set(PAYLOADS)
    status_entries = _status_entries(external_root)
    for code, path in status_entries:
        if code == "??":
            raise ValueError(f"untracked external source path is not allowed: {path}")
        if code[0] != " ":
            raise ValueError(f"staged/index mutation is not allowed: {code} {path}")
        if code != " M":
            raise ValueError(
                f"unsupported external work-tree mutation: {code} {path}"
            )
        if path not in allowed:
            raise ValueError(
                f"external work-tree mutation outside reviewed overlay: {path}"
            )

    source_records: list[dict[str, Any]] = []
    for external_rel, reviewed_rel in PAYLOADS.items():
        reviewed = _regular_file_bytes(repo_root / reviewed_rel)
        installed = _regular_file_bytes(external_root / external_rel)
        if installed != reviewed:
            raise ValueError(f"reviewed source byte mismatch: {external_rel}")
        source_records.append(
            {
                "external_path": external_rel,
                "reviewed_path": str(reviewed_rel),
                "bytes": len(reviewed),
                "sha256": _sha256(reviewed),
                "git_status": next(
                    (
                        code
                        for code, path in status_entries
                        if path == external_rel
                    ),
                    "CLEAN",
                ),
            }
        )

    # Re-read Git status after the byte checks so a mutation during verification
    # cannot disappear behind the first status snapshot.
    final_status = _status_entries(external_root)
    if final_status != status_entries:
        raise ValueError(
            "external Git status changed while overlay provenance was being verified"
        )

    return {
        "schema": SCHEMA,
        "status": "PASS",
        "external_root": str(external_root),
        "baseline": {
            "head_commit": head,
            "head_tree": tree,
        },
        "overlay": {
            "allowed_paths": sorted(allowed),
            "visible_git_deltas": [
                {"status": code, "path": path} for code, path in status_entries
            ],
            "source_pair": source_records,
            "index_clean": True,
            "no_untracked_paths": True,
            "no_other_worktree_mutations": True,
        },
        "scientific_scope": (
            "PREBUILD_SOURCE_IDENTITY_ONLY_COMPILED_RUNTIME_VALIDATION_REQUIRED"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-tree", required=True)
    args = parser.parse_args()

    try:
        result = validate_external_overlay(
            args.external_root,
            args.repo_root,
            args.expected_commit,
            args.expected_tree,
        )
    except (OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "BLOCKED",
                    "error": str(exc),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
