from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


BUILD_PATHSPEC = ":(glob)geant4/**/build/**"


def tracked_geant4_build_artifacts(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--", BUILD_PATHSPEC],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def test_no_tracked_geant4_build_artifacts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if not (repo_root / ".git").exists():
        pytest.skip("requires a Git checkout to inspect tracked paths")

    tracked = tracked_geant4_build_artifacts(repo_root)
    assert not tracked, (
        "generated Geant4 build artifacts are tracked; remove them and keep "
        f"build trees ignored. Tracked paths: {tracked}"
    )
