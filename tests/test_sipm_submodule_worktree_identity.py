"""Atomic source-worktree provenance regressions for #977 / PR #1285 child."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "single_stave"
MOD_PATH = SCRIPTS / "sipm_build_receipt.py"
CORE_PATH = Path("geant4/single_stave/sipm")


def _load():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("sipm_build_receipt_worktree_test", MOD_PATH)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _source_repo(tmp_path: Path) -> tuple[Path, Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "fixture")
    (repo / "README").write_text("root fixture\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "root fixture")

    core = repo / CORE_PATH
    core.mkdir(parents=True)
    _git(core, "init")
    _git(core, "config", "user.email", "core@example.invalid")
    _git(core, "config", "user.name", "core fixture")
    (core / "CORE_README").write_text("core v1\n")
    _git(core, "add", "CORE_README")
    _git(core, "commit", "-m", "core v1")
    core_sha = _git(core, "rev-parse", "HEAD")

    _git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{core_sha},{CORE_PATH.as_posix()}",
    )
    _git(repo, "commit", "-m", "pin core gitlink")
    root_sha = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
    return repo, core, root_sha, core_sha


def test_source_identity_records_materialized_exact_core_worktree(tmp_path: Path):
    mod = _load()
    repo, _core, root_sha, core_sha = _source_repo(tmp_path)
    identity = mod.source_identity(repo, require_clean=True)
    assert identity["superproject_commit"] == root_sha
    assert identity["ccb_sipm_core_commit"] == core_sha
    assert identity["ccb_sipm_core_worktree_head"] == core_sha
    assert identity["source_tree_clean_at_receipt"] is True
    assert identity["ccb_sipm_core_worktree_clean_at_receipt"] is True
    assert mod.SCHEMA == "ccb-single-stave-build-receipt/2"


def test_empty_gitlink_directory_is_rejected_despite_clean_superproject(tmp_path: Path):
    mod = _load()
    repo, core, _root_sha, _core_sha = _source_repo(tmp_path)
    shutil.rmtree(core)
    core.mkdir(parents=True)

    # Critical negative control: the outer status alone is still clean.
    assert _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
    with pytest.raises(mod.BuildReceiptError, match="independent Git worktree"):
        mod.source_identity(repo, require_clean=True)


def test_non_git_content_at_gitlink_is_rejected_despite_clean_superproject(tmp_path: Path):
    mod = _load()
    repo, core, _root_sha, _core_sha = _source_repo(tmp_path)
    shutil.rmtree(core)
    core.mkdir(parents=True)
    (core / "lookalike.cc").write_text("not a checked-out submodule\n")

    # Gitlink entries suppress ordinary descendant tracking in the superproject.
    assert _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
    with pytest.raises(mod.BuildReceiptError, match="independent Git worktree"):
        mod.source_identity(repo, require_clean=True)


def test_nested_head_mismatch_is_rejected_explicitly(tmp_path: Path):
    mod = _load()
    repo, core, _root_sha, pinned_core_sha = _source_repo(tmp_path)
    (core / "CORE_README").write_text("core v2\n")
    _git(core, "add", "CORE_README")
    _git(core, "commit", "-m", "core v2 not repinned")
    assert _git(core, "rev-parse", "HEAD") != pinned_core_sha

    with pytest.raises(mod.BuildReceiptError, match="worktree HEAD does not equal superproject gitlink"):
        mod.source_identity(repo, require_clean=False)


def test_dirty_nested_worktree_is_rejected_at_nested_contract(tmp_path: Path):
    mod = _load()
    repo, core, _root_sha, _core_sha = _source_repo(tmp_path)
    (core / "CORE_README").write_text("dirty tracked source\n")

    with pytest.raises(mod.BuildReceiptError, match="clean ccb-sipm-core worktree"):
        mod.source_identity(repo, require_clean=True)


def test_legacy_receipt_schema_is_non_authorising_after_contract_upgrade():
    mod = _load()
    with pytest.raises(mod.BuildReceiptError, match="receipt must be PASS schema"):
        mod.validate_receipt({"schema": "ccb-single-stave-build-receipt/1", "status": "PASS"})
