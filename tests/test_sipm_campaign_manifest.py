"""Deterministic tests for source-bound SiPM campaign intent manifests (#977)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "scripts" / "single_stave" / "sipm_campaign_manifest.py"
REPO = "4" * 40
CORE = "3" * 40
GRID_A = "a" * 64
GRID_B = "b" * 64


def _load():
    spec = importlib.util.spec_from_file_location("sipm_campaign_manifest", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["sipm_campaign_manifest"] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _repo_with_gitlink(tmp_path: Path, core: str = CORE) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "fixture")
    (repo / "README").write_text("fixture\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "initial")
    _git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{core},geant4/single_stave/sipm",
    )
    _git(repo, "commit", "-m", "add gitlink")
    return repo


def _manifest(mod):
    return mod.build_manifest(
        repo_commit=REPO,
        core_commit=CORE,
        base_cli="--particle proton --energy 100",
        nevents_per_point=60,
        grid_sha256={"crosstalk": GRID_A, "recovery": GRID_B},
    )


def test_expected_core_is_gitlink_sourced_not_operator_label():
    mod = _load()
    manifest = _manifest(mod)
    assert manifest["expected_core"] == {
        "path": mod.CORE_PATH,
        "commit": CORE,
        "source": mod.CORE_SOURCE,
        "authorising_source": True,
    }
    assert mod.expected_core_sha(manifest) == CORE


def test_operator_or_mutable_source_is_rejected():
    mod = _load()
    manifest = _manifest(mod)
    manifest["expected_core"]["source"] = "OPERATOR_CLI"
    with pytest.raises(mod.ManifestError, match="source-bound"):
        mod.validate_manifest(manifest)


def test_manifest_digest_detects_post_submission_mutation(tmp_path: Path):
    mod = _load()
    path = tmp_path / "campaign_intent.json"
    manifest = _manifest(mod)
    digest = mod.write_manifest_once(path, manifest)
    mutated = json.loads(path.read_text())
    mutated["expected_core"]["commit"] = "f" * 40
    path.chmod(0o644)
    path.write_bytes(mod.canonical_manifest_bytes(mutated))
    with pytest.raises(mod.ManifestError, match="digest mismatch"):
        mod.load_and_verify_manifest(path, expected_sha256=digest)


def test_manifest_bytes_are_canonical_and_key_order_invariant(tmp_path: Path):
    mod = _load()
    manifest = _manifest(mod)
    canonical = mod.canonical_manifest_bytes(manifest)
    reordered = dict(reversed(list(manifest.items())))
    assert mod.canonical_manifest_bytes(reordered) == canonical
    path = tmp_path / "campaign_intent.json"
    digest = mod.write_manifest_once(path, manifest)
    loaded, observed = mod.load_and_verify_manifest(path, expected_sha256=digest)
    assert loaded == manifest
    assert observed == digest


def test_existing_different_campaign_intent_cannot_be_overwritten(tmp_path: Path):
    mod = _load()
    path = tmp_path / "campaign_intent.json"
    manifest = _manifest(mod)
    mod.write_manifest_once(path, manifest)
    other = _manifest(mod)
    other["execution_intent"]["nevents_per_point"] = 61
    with pytest.raises(mod.ManifestError, match="refusing to overwrite"):
        mod.write_manifest_once(path, other)


def test_noncanonical_or_wrong_gitlink_contract_fails_closed():
    mod = _load()
    manifest = _manifest(mod)
    manifest["expected_core"]["commit"] = "DEADBEEF"
    with pytest.raises(mod.ManifestError, match="canonical lowercase"):
        mod.validate_manifest(manifest)
    manifest = _manifest(mod)
    manifest["expected_core"]["path"] = "some/other/path"
    with pytest.raises(mod.ManifestError, match="expected_core.path"):
        mod.validate_manifest(manifest)


def test_grid_digest_is_part_of_verified_campaign_intent(tmp_path: Path):
    mod = _load()
    grid = tmp_path / "points_crosstalk.csv"
    grid.write_text("label,seed\ncrosstalk=0,1\n")
    digest = mod.sha256_bytes(grid.read_bytes())
    manifest = mod.build_manifest(
        repo_commit=REPO,
        core_commit=CORE,
        base_cli="--particle proton --energy 100",
        nevents_per_point=60,
        grid_sha256={"crosstalk": digest},
    )
    path = tmp_path / "campaign_intent.json"
    manifest_digest = mod.write_manifest_once(path, manifest)
    loaded, observed = mod.load_and_verify_manifest(path, expected_sha256=manifest_digest)
    assert loaded["grid_sha256"]["crosstalk"] == digest
    assert observed == manifest_digest
    grid.write_text("label,seed\ncrosstalk=1,1\n")
    assert mod.sha256_bytes(grid.read_bytes()) != loaded["grid_sha256"]["crosstalk"]


def test_source_label_cannot_hide_wrong_core_for_recorded_superproject(tmp_path: Path):
    mod = _load()
    repo = _repo_with_gitlink(tmp_path)
    repo_commit, source_core = mod.repo_identities(repo)
    assert source_core == CORE
    manifest = mod.build_manifest(
        repo_commit=repo_commit,
        core_commit="f" * 40,
        base_cli="--particle proton --energy 100",
        nevents_per_point=60,
        grid_sha256={"crosstalk": GRID_A},
    )
    with pytest.raises(mod.ManifestError, match="!= gitlink"):
        mod.verify_source_binding(manifest, repo)


def test_execution_intent_mismatch_fails_closed():
    mod = _load()
    manifest = _manifest(mod)
    mod.verify_execution_intent(
        manifest,
        base_cli="--particle proton --energy 100",
        nevents_per_point=60,
        threads=1,
    )
    with pytest.raises(mod.ManifestError, match="runtime base_cli"):
        mod.verify_execution_intent(manifest, base_cli="--particle proton --energy 90")
    with pytest.raises(mod.ManifestError, match="runtime nevents"):
        mod.verify_execution_intent(manifest, nevents_per_point=61)
    with pytest.raises(mod.ManifestError, match="runtime threads"):
        mod.verify_execution_intent(manifest, threads=2)


def test_campaign_creation_requires_clean_repository(tmp_path: Path):
    mod = _load()
    repo = tmp_path / "clean_repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "fixture")
    (repo / "README").write_text("fixture\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "initial")
    mod.require_clean_worktree(repo)
    (repo / "dirty.txt").write_text("uncommitted\n")
    with pytest.raises(mod.ManifestError, match="clean repository working tree"):
        mod.require_clean_worktree(repo)


def test_env_regrid_is_external_content_bound_and_leaves_source_clean(tmp_path: Path):
    """A documented grid override must not dirty tracked source before manifest freeze."""
    # The repository-wide CI intentionally creates logs, bytecode and editable-install
    # metadata before pytest. Exercise the launcher in a fresh worktree instead of
    # weakening its production clean-source gate to accommodate CI side effects.
    source = tmp_path / "source"
    subprocess.run(
        ["git", "-C", str(ROOT), "worktree", "add", "--detach", str(source), "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        before = _git(source, "status", "--porcelain=v1", "--untracked-files=all")
        assert before == ""

        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        sbatch = fake_bin / "sbatch"
        sbatch.write_text("#!/usr/bin/env bash\necho 'Submitted batch job 424242'\n")
        sbatch.chmod(0o755)

        build = tmp_path / "build"
        build.mkdir()
        outdir = tmp_path / "campaign"
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{fake_bin}:{env['PATH']}",
                "CCB_CAMPASSIGN_BUILD": str(build),
                "CCB_CAMPASSIGN_OUTDIR": str(outdir),
                "CCB_CAMPASSIGN_KNOBS": "pde_scale",
                "CCB_GRID_PDE_SCALE": "0.95 1.05",
                "CCB_CAMPASSIGN_SEED_REPLICATES": "1000 1001",
            }
        )
        run_script = source / "geant4" / "single_stave" / "slurm" / "run_sensitivity_campaign.sh"
        proc = subprocess.run(
            ["bash", str(run_script)],
            cwd=source,
            env=env,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert "submitted 1 knob arrays" in proc.stdout

        grid = outdir / "grids" / "points_pde_scale.csv"
        assert grid.is_file()
        text = grid.read_text()
        assert "pde_scale=0.95__rep=1000" in text
        assert "pde_scale=1.05__rep=1001" in text

        manifest_path = outdir / "campaign_intent.json"
        manifest = json.loads(manifest_path.read_text())
        expected_grid_digest = hashlib.sha256(grid.read_bytes()).hexdigest()
        assert manifest["grid_sha256"] == {"pde_scale": expected_grid_digest}
        assert manifest["execution_intent"]["nevents_per_point"] == 60

        after = _git(source, "status", "--porcelain=v1", "--untracked-files=all")
        assert after == before
    finally:
        subprocess.run(
            ["git", "-C", str(ROOT), "worktree", "remove", "--force", str(source)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
