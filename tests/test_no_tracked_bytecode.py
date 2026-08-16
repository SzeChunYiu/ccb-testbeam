from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

PYCACHE_PATHSPEC = ":(glob)**/__pycache__/**"
PYC_PATHSPEC = "*.pyc"


def _tracked(repo_root: Path, pathspec: str) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--", pathspec],
        cwd=repo_root, check=True, capture_output=True, text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def test_no_tracked_pycache_or_pyc() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if not (repo_root / ".git").exists():
        pytest.skip("requires a Git checkout to inspect tracked paths")
    tracked = _tracked(repo_root, PYCACHE_PATHSPEC) + _tracked(repo_root, PYC_PATHSPEC)
    assert not tracked, (
        "compiled bytecode is tracked; untrack it (__pycache__/ is already "
        f"gitignored). Tracked paths: {tracked[:10]}"
    )
