#!/usr/bin/env python3
"""Fail closed when tracked Git gitlinks and .gitmodules disagree."""
from __future__ import annotations

import argparse
import configparser
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "TRACKED_GITLINKS_EQUAL_CONFIGURED_SUBMODULE_PATHS"


class ContractError(ValueError):
    """Controlled repository-metadata failure."""


def parse_index_records(raw: bytes) -> dict[str, str]:
    """Return path -> object SHA for stage-0 mode-160000 index records."""
    gitlinks: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            meta, path_raw = record.split(b"\t", 1)
            mode, sha, stage = meta.decode("ascii").split(" ")
            path = path_raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ContractError("malformed git ls-files --stage -z record") from exc
        if stage != "0":
            raise ContractError(f"non-stage-0 index record for {path!r}")
        if mode == "160000":
            if path in gitlinks:
                raise ContractError(f"duplicate gitlink index path: {path}")
            gitlinks[path] = sha
    return gitlinks


def parse_gitmodules_text(text: str) -> set[str]:
    """Return configured submodule paths, rejecting ambiguous metadata."""
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        parser.read_file(io.StringIO(text), source=".gitmodules")
    except configparser.Error as exc:
        raise ContractError(f"invalid .gitmodules: {exc}") from exc

    paths: list[str] = []
    for section in parser.sections():
        if not section.startswith("submodule "):
            raise ContractError(f"unexpected .gitmodules section: {section}")
        if not parser.has_option(section, "path"):
            raise ContractError(f"missing path in .gitmodules section: {section}")
        path = parser.get(section, "path").strip()
        if not path:
            raise ContractError(f"empty path in .gitmodules section: {section}")
        paths.append(path)

    if len(paths) != len(set(paths)):
        raise ContractError("duplicate submodule path in .gitmodules")
    return set(paths)


def tracked_gitlinks(root: Path) -> dict[str, str]:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--stage", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError(f"cannot enumerate Git index at {root}: {exc}") from exc
    return parse_index_records(proc.stdout)


def configured_submodules(root: Path) -> set[str]:
    path = root / ".gitmodules"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read {path}: {exc}") from exc
    return parse_gitmodules_text(text)


def local_worktrees_ignored(root: Path) -> bool:
    """Check recurrence prevention without requiring the path to exist."""
    try:
        proc = subprocess.run(
            [
                "git",
                "check-ignore",
                "--quiet",
                "--no-index",
                ".claude/worktrees/synthetic-agent",
            ],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise ContractError(f"cannot run git check-ignore at {root}: {exc}") from exc
    return proc.returncode == 0


def evaluate_contract(
    gitlinks: dict[str, str],
    configured_paths: set[str],
    *,
    worktrees_ignored: bool,
) -> dict[str, Any]:
    tracked_paths = set(gitlinks)
    orphan_gitlinks = sorted(tracked_paths - configured_paths)
    configured_without_gitlink = sorted(configured_paths - tracked_paths)
    issues: list[dict[str, Any]] = []
    if orphan_gitlinks:
        issues.append({"code": "ORPHAN_GITLINK", "paths": orphan_gitlinks})
    if configured_without_gitlink:
        issues.append(
            {
                "code": "CONFIGURED_SUBMODULE_NOT_GITLINK",
                "paths": configured_without_gitlink,
            }
        )
    if not worktrees_ignored:
        issues.append(
            {
                "code": "LOCAL_WORKTREE_PATH_NOT_IGNORED",
                "path": ".claude/worktrees/",
            }
        )
    return {
        "version": VERSION,
        "policy": POLICY,
        "ok": not issues,
        "tracked_gitlinks": [
            {"path": path, "sha": gitlinks[path]} for path in sorted(gitlinks)
        ],
        "configured_submodule_paths": sorted(configured_paths),
        "local_worktrees_ignored": worktrees_ignored,
        "issues": issues,
    }


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    return evaluate_contract(
        tracked_gitlinks(root),
        configured_submodules(root),
        worktrees_ignored=local_worktrees_ignored(root),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = audit(args.root)
    except ContractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print("PASS: tracked gitlinks match configured submodule paths")
    else:
        for issue in result["issues"]:
            print(f"FAIL: {issue}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
