#!/usr/bin/env python3
"""Fail closed when a PR head does not contain the current protected-base commit.

This is a local Git-graph provenance check. It deliberately does not inspect
GitHub status/check APIs; those are a separate authorization layer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "pr_base_freshness_v1"


class GitInspectionError(RuntimeError):
    """Raised when the requested refs cannot be inspected unambiguously."""


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"git exited {proc.returncode}"
        raise GitInspectionError(f"git {' '.join(args)} failed: {detail}")
    return proc


def _resolve(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").stdout.strip()


def inspect_base_freshness(repo: Path, base_ref: str, head_ref: str) -> dict[str, object]:
    repo = repo.resolve()
    base_sha = _resolve(repo, base_ref)
    head_sha = _resolve(repo, head_ref)
    merge_base_sha = _git(repo, "merge-base", base_sha, head_sha).stdout.strip()

    counts = _git(repo, "rev-list", "--left-right", "--count", f"{base_sha}...{head_sha}")
    fields = counts.stdout.split()
    if len(fields) != 2:
        raise GitInspectionError(
            f"unexpected rev-list count output for {base_sha}...{head_sha}: {counts.stdout!r}"
        )
    behind_by, ahead_by = map(int, fields)

    ancestry = _git(repo, "merge-base", "--is-ancestor", base_sha, head_sha, check=False)
    if ancestry.returncode not in (0, 1):
        detail = ancestry.stderr.strip() or ancestry.stdout.strip()
        raise GitInspectionError(f"git merge-base --is-ancestor failed: {detail}")
    base_is_ancestor = ancestry.returncode == 0

    authorising = base_is_ancestor and behind_by == 0 and merge_base_sha == base_sha
    return {
        "schema": SCHEMA,
        "repository": str(repo),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_base_sha": merge_base_sha,
        "behind_by": behind_by,
        "ahead_by": ahead_by,
        "base_is_ancestor_of_head": base_is_ancestor,
        "authorising_current_base": authorising,
        "status": "CURRENT_BASE" if authorising else "STALE_OR_DIVERGED_BASE",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether HEAD contains the exact current protected-base commit. "
            "Exit 0 only for current-base ancestry, 2 for stale/diverged ancestry, "
            "and 3 when Git inspection itself cannot be completed."
        )
    )
    parser.add_argument("--repo", type=Path, default=Path("."), help="Git repository path")
    parser.add_argument("--base-ref", required=True, help="Current protected-base ref/SHA")
    parser.add_argument("--head-ref", required=True, help="PR head ref/SHA")
    parser.add_argument("--output", type=Path, help="Optional JSON result path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = inspect_base_freshness(args.repo, args.base_ref, args.head_ref)
    except GitInspectionError as exc:
        failure = {
            "schema": SCHEMA,
            "status": "INSPECTION_FAILED",
            "authorising_current_base": False,
            "error": str(exc),
        }
        text = json.dumps(failure, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(text)
        sys.stdout.write(text)
        return 3

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    sys.stdout.write(text)
    return 0 if result["authorising_current_base"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
