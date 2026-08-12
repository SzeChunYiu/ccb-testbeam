"""Deterministic tests for source-bound SiPM campaign intent manifests (#977)."""
from __future__ import annotations

import importlib.util
import json
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
