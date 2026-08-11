from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tools.audit.validate_geant4_external_overlay import (
    PAYLOADS,
    validate_external_overlay,
)

REPO_ROOT = Path(".")


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _new_external_repo(tmp_path: Path, *, reviewed_baseline: bool) -> Path:
    root = tmp_path / "external"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "CCB fixture")
    _git(root, "config", "user.email", "ccb-fixture@example.invalid")

    for external_rel, reviewed_rel in PAYLOADS.items():
        destination = root / external_rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        if reviewed_baseline:
            shutil.copyfile(REPO_ROOT / reviewed_rel, destination)
        else:
            destination.write_text(
                f"upstream baseline for {external_rel}\n",
                encoding="utf-8",
            )

    (root / "README.fixture").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture baseline")
    return root


def _baseline_ids(root: Path) -> tuple[str, str]:
    return (
        _git(root, "rev-parse", "HEAD"),
        _git(root, "rev-parse", "HEAD^{tree}"),
    )


def _install_reviewed_pair(root: Path) -> None:
    for external_rel, reviewed_rel in PAYLOADS.items():
        shutil.copyfile(REPO_ROOT / reviewed_rel, root / external_rel)


def test_expected_two_file_unstaged_overlay_passes(tmp_path: Path) -> None:
    root = _new_external_repo(tmp_path, reviewed_baseline=False)
    commit, tree = _baseline_ids(root)
    _install_reviewed_pair(root)

    result = validate_external_overlay(root, REPO_ROOT, commit, tree)

    assert result["status"] == "PASS"
    assert result["baseline"] == {"head_commit": commit, "head_tree": tree}
    assert result["overlay"]["index_clean"] is True
    delta_paths = {item["path"] for item in result["overlay"]["visible_git_deltas"]}
    assert delta_paths == set(PAYLOADS)
    source_statuses = {item["git_status"] for item in result["overlay"]["source_pair"]}
    assert source_statuses == {" M"}


def test_clean_upstream_that_already_matches_reviewed_pair_passes(
    tmp_path: Path,
) -> None:
    root = _new_external_repo(tmp_path, reviewed_baseline=True)
    commit, tree = _baseline_ids(root)

    result = validate_external_overlay(root, REPO_ROOT, commit, tree)

    assert result["status"] == "PASS"
    assert result["overlay"]["visible_git_deltas"] == []
    source_statuses = {item["git_status"] for item in result["overlay"]["source_pair"]}
    assert source_statuses == {"CLEAN"}


def test_interrupted_one_file_overlay_fails_closed(tmp_path: Path) -> None:
    root = _new_external_repo(tmp_path, reviewed_baseline=False)
    commit, tree = _baseline_ids(root)
    external_rel, reviewed_rel = next(iter(PAYLOADS.items()))
    shutil.copyfile(REPO_ROOT / reviewed_rel, root / external_rel)

    with pytest.raises(ValueError, match="reviewed source byte mismatch"):
        validate_external_overlay(root, REPO_ROOT, commit, tree)


def test_extra_tracked_mutation_fails_closed(tmp_path: Path) -> None:
    root = _new_external_repo(tmp_path, reviewed_baseline=False)
    commit, tree = _baseline_ids(root)
    _install_reviewed_pair(root)
    (root / "README.fixture").write_text("mutated\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside reviewed overlay"):
        validate_external_overlay(root, REPO_ROOT, commit, tree)


def test_untracked_source_path_fails_closed(tmp_path: Path) -> None:
    root = _new_external_repo(tmp_path, reviewed_baseline=False)
    commit, tree = _baseline_ids(root)
    _install_reviewed_pair(root)
    (root / "unexpected.txt").write_text("not authorised\n", encoding="utf-8")

    with pytest.raises(ValueError, match="untracked external source path"):
        validate_external_overlay(root, REPO_ROOT, commit, tree)


def test_staged_overlay_fails_closed(tmp_path: Path) -> None:
    root = _new_external_repo(tmp_path, reviewed_baseline=False)
    commit, tree = _baseline_ids(root)
    _install_reviewed_pair(root)
    first_path = next(iter(PAYLOADS))
    _git(root, "add", first_path)

    with pytest.raises(ValueError, match="staged/index mutation"):
        validate_external_overlay(root, REPO_ROOT, commit, tree)


def test_clean_but_wrong_overlay_bytes_fail_closed(tmp_path: Path) -> None:
    root = _new_external_repo(tmp_path, reviewed_baseline=False)
    commit, tree = _baseline_ids(root)

    with pytest.raises(ValueError, match="reviewed source byte mismatch"):
        validate_external_overlay(root, REPO_ROOT, commit, tree)


def test_wrong_expected_head_or_tree_fails_closed(tmp_path: Path) -> None:
    root = _new_external_repo(tmp_path, reviewed_baseline=True)
    commit, tree = _baseline_ids(root)

    with pytest.raises(ValueError, match="HEAD mismatch"):
        validate_external_overlay(root, REPO_ROOT, "0" * len(commit), tree)
    with pytest.raises(ValueError, match="HEAD tree mismatch"):
        validate_external_overlay(root, REPO_ROOT, commit, "0" * len(tree))
