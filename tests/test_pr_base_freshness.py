from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "validate_pr_base_freshness.py"
SPEC = importlib.util.spec_from_file_location("validate_pr_base_freshness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
inspect_base_freshness = MODULE.inspect_base_freshness


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _commit(repo: Path, name: str, content: str) -> str:
    (repo / name).write_text(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"commit {name}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def diverged_repo(tmp_path: Path) -> dict[str, object]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "CI Freshness Test")
    _git(repo, "config", "user.email", "ci-freshness@example.invalid")

    base0 = _commit(repo, "base0.txt", "base0\n")
    _git(repo, "switch", "-c", "feature")
    feature = _commit(repo, "feature.txt", "feature\n")
    _git(repo, "switch", "main")
    base1 = _commit(repo, "base1.txt", "base1\n")
    return {"repo": repo, "base0": base0, "base1": base1, "feature": feature}


def test_stale_feature_is_not_authorising(diverged_repo: dict[str, object]) -> None:
    repo = diverged_repo["repo"]
    assert isinstance(repo, Path)
    result = inspect_base_freshness(
        repo,
        str(diverged_repo["base1"]),
        str(diverged_repo["feature"]),
    )
    assert result["merge_base_sha"] == diverged_repo["base0"]
    assert result["behind_by"] == 1
    assert result["ahead_by"] == 1
    assert result["base_is_ancestor_of_head"] is False
    assert result["authorising_current_base"] is False
    assert result["status"] == "STALE_OR_DIVERGED_BASE"


def test_current_base_feature_is_authorising(diverged_repo: dict[str, object]) -> None:
    repo = diverged_repo["repo"]
    assert isinstance(repo, Path)
    _git(repo, "switch", "-c", "refreshed", str(diverged_repo["base1"]))
    refreshed = _commit(repo, "refreshed.txt", "refreshed\n")

    result = inspect_base_freshness(repo, str(diverged_repo["base1"]), refreshed)
    assert result["merge_base_sha"] == diverged_repo["base1"]
    assert result["behind_by"] == 0
    assert result["ahead_by"] == 1
    assert result["base_is_ancestor_of_head"] is True
    assert result["authorising_current_base"] is True
    assert result["status"] == "CURRENT_BASE"


def test_cli_exit_codes_and_json(diverged_repo: dict[str, object], tmp_path: Path) -> None:
    repo = diverged_repo["repo"]
    assert isinstance(repo, Path)
    out = tmp_path / "result.json"

    stale = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--base-ref",
            str(diverged_repo["base1"]),
            "--head-ref",
            str(diverged_repo["feature"]),
            "--output",
            str(out),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert stale.returncode == 2
    payload = json.loads(out.read_text())
    assert payload["authorising_current_base"] is False
    assert payload["behind_by"] == 1

    bad = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--repo",
            str(repo),
            "--base-ref",
            "definitely-missing-ref",
            "--head-ref",
            str(diverged_repo["feature"]),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 3
    assert json.loads(bad.stdout)["status"] == "INSPECTION_FAILED"
