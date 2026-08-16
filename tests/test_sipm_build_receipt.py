"""Deterministic build/executable provenance tests for #977."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "single_stave"
MOD_PATH = SCRIPTS / "sipm_build_receipt.py"
BUILD_IDENTITY = ROOT / "geant4" / "single_stave" / "src" / "BuildIdentity.cc"
CORE_DIGEST = ROOT / "geant4" / "single_stave" / "sipm" / "src" / "Digest.cc"


def _load():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("sipm_build_receipt", MOD_PATH)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules["sipm_build_receipt"] = mod
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


def _source_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """Create a clean superproject plus a genuinely checked-out gitlink worktree.

    A bare cacheinfo-only gitlink with no directory is reported as deleted by
    ``git status``.  The authorising receipt intentionally requires a clean
    source tree, so the fixture must model the recursive checkout used in CI
    rather than weaken the production cleanliness predicate.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "fixture")
    (repo / "README").write_text("fixture\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "initial")

    core = repo / "geant4" / "single_stave" / "sipm"
    core.mkdir(parents=True)
    _git(core, "init")
    _git(core, "config", "user.email", "core-fixture@example.invalid")
    _git(core, "config", "user.name", "core-fixture")
    (core / "CORE_README").write_text("core fixture\n")
    _git(core, "add", "CORE_README")
    _git(core, "commit", "-m", "core fixture")
    core_sha = _git(core, "rev-parse", "HEAD")

    _git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{core_sha},geant4/single_stave/sipm",
    )
    _git(repo, "commit", "-m", "add gitlink")
    assert _git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""
    return repo, _git(repo, "rev-parse", "HEAD"), core_sha


def _tool(path: Path, label: str) -> None:
    path.write_text(f"#!/usr/bin/env sh\necho {label}\n")
    path.chmod(0o755)


def _fake_build(tmp_path: Path, root_sha: str, core_sha: str) -> tuple[Path, Path]:
    build = tmp_path / "build"
    build.mkdir()
    cmake = build / "fake-cmake"
    cxx = build / "fake-cxx"
    _tool(cmake, "cmake-fixture")
    _tool(cxx, "cxx-fixture")
    g4 = build / "geant4"
    g4.mkdir()
    (g4 / "Geant4Config.cmake").write_text("set(Geant4_VERSION 11.fixture)\n")
    cache = build / "CMakeCache.txt"
    cache.write_text(
        f"CMAKE_COMMAND:INTERNAL={cmake}\n"
        f"CMAKE_CXX_COMPILER:FILEPATH={cxx}\n"
        "CMAKE_GENERATOR:INTERNAL=Unix Makefiles\n"
        f"Geant4_DIR:PATH={g4}\n"
    )
    exe = build / "ccb_stave_sim"
    exe.write_text(
        "#!/usr/bin/env python3\n"
        "import hashlib, json, pathlib, sys\n"
        f"root={root_sha!r}\n"
        f"core={core_sha!r}\n"
        f"cxx={str(cxx)!r}\n"
        "if sys.argv[1:] != ['--build-provenance-json']:\n"
        "    raise SystemExit(9)\n"
        "payload=pathlib.Path(__file__).read_bytes()\n"
        "print(json.dumps({\n"
        " 'schema':'ccb-single-stave-runtime-build-identity/1',\n"
        " 'superproject_commit':root,\n"
        " 'sipm_core_commit':core,\n"
        " 'source_tree_clean_at_configure':True,\n"
        " 'cmake_version':'fixture',\n"
        " 'cxx_compiler_id':'fixture',\n"
        " 'cxx_compiler_version':'fixture',\n"
        " 'cxx_compiler_path':cxx,\n"
        " 'geant4_version':'fixture',\n"
        " 'executable_sha256':hashlib.sha256(payload).hexdigest(),\n"
        " 'executable_bytes':len(payload),\n"
        " 'executable_identity_status':'PASS_SELF_SHA256',\n"
        "}, sort_keys=True, separators=(',', ':')))\n"
    )
    exe.chmod(0o755)
    return build, exe


def _receipt_fixture(tmp_path: Path):
    mod = _load()
    repo, root_sha, core_sha = _source_repo(tmp_path)
    build, exe = _fake_build(tmp_path, root_sha, core_sha)
    receipt = mod.create_receipt(repo_root=repo, build_dir=build, executable=exe)
    return mod, repo, build, exe, receipt


def test_runtime_build_identity_self_hashes_exact_executable(tmp_path: Path):
    compiler = shutil.which("c++")
    assert compiler is not None
    harness = tmp_path / "probe.cc"
    harness.write_text(
        '#include "BuildIdentity.hh"\n'
        '#include <iostream>\n'
        'int main() { std::cout << ccb::build::RenderBuildIdentityJson() << "\\n"; }\n'
    )
    exe = tmp_path / "probe"
    root_sha = "1" * 40
    compiler_path = str(Path(compiler))
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-I",
            str(ROOT / "geant4" / "single_stave" / "include"),
            "-I",
            str(ROOT / "geant4" / "single_stave" / "sipm" / "include"),
            f'-DCCB_BUILD_SUPERPROJECT_COMMIT="{root_sha}"',
            "-DCCB_BUILD_SOURCE_CLEAN_AT_CONFIGURE=1",
            '-DCCB_BUILD_CMAKE_VERSION="fixture"',
            '-DCCB_BUILD_CXX_COMPILER_ID="fixture"',
            '-DCCB_BUILD_CXX_COMPILER_VERSION="fixture"',
            f'-DCCB_BUILD_CXX_COMPILER_PATH="{compiler_path}"',
            '-DCCB_BUILD_GEANT4_VERSION="fixture"',
            str(BUILD_IDENTITY),
            str(CORE_DIGEST),
            str(harness),
            "-o",
            str(exe),
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    observed = json.loads(subprocess.run([str(exe)], check=True, text=True, capture_output=True).stdout)
    raw = exe.read_bytes()
    assert observed["superproject_commit"] == root_sha
    assert observed["sipm_core_commit"] == _compiled_core_sha()
    assert observed["source_tree_clean_at_configure"] is True
    assert observed["executable_sha256"] == hashlib.sha256(raw).hexdigest()
    assert observed["executable_bytes"] == len(raw)
    assert observed["executable_identity_status"] == "PASS_SELF_SHA256"


def _compiled_core_sha() -> str:
    text = (ROOT / "geant4" / "single_stave" / "include" / "SipmBuildProvenance.hh").read_text()
    return text.split('"')[1]


def test_build_receipt_binds_source_binary_cache_toolchain_and_geant4(tmp_path: Path):
    mod, repo, _build, exe, receipt = _receipt_fixture(tmp_path)
    core_path = repo / mod.campaign.CORE_PATH
    assert receipt["status"] == "PASS"
    assert receipt["source"]["superproject_commit"] == _git(repo, "rev-parse", "HEAD")
    assert receipt["source"]["ccb_sipm_core_commit"] == _git(core_path, "rev-parse", "HEAD")
    assert receipt["executable"]["sha256"] == hashlib.sha256(exe.read_bytes()).hexdigest()
    mod.verify_receipt(
        receipt=receipt,
        executable=exe,
        runtime_probe=True,
        campaign_manifest=None,
        campaign_sha256=None,
        repo_root=None,
    )


def test_stale_or_substituted_executable_fails_closed(tmp_path: Path):
    mod, _repo, _build, exe, receipt = _receipt_fixture(tmp_path)
    exe.write_text(exe.read_text() + "# substituted after receipt\n")
    with pytest.raises(mod.BuildReceiptError, match="executable changed since receipt"):
        mod.verify_receipt(
            receipt=receipt,
            executable=exe,
            runtime_probe=False,
            campaign_manifest=None,
            campaign_sha256=None,
            repo_root=None,
        )


def test_toolchain_sentinel_mutation_fails_closed(tmp_path: Path):
    mod, _repo, build, exe, receipt = _receipt_fixture(tmp_path)
    (build / "fake-cxx").write_text("#!/usr/bin/env sh\necho changed\n")
    (build / "fake-cxx").chmod(0o755)
    with pytest.raises(mod.BuildReceiptError, match=r"C\+\+ compiler changed since receipt"):
        mod.verify_receipt(
            receipt=receipt,
            executable=exe,
            runtime_probe=False,
            campaign_manifest=None,
            campaign_sha256=None,
            repo_root=None,
        )


def test_campaign_source_advance_rejects_stale_build_receipt(tmp_path: Path):
    mod, repo, _build, exe, receipt = _receipt_fixture(tmp_path)
    (repo / "README").write_text("new source\n")
    _git(repo, "add", "README")
    _git(repo, "commit", "-m", "advance source")
    new_root = _git(repo, "rev-parse", "HEAD")
    manifest = mod.campaign.build_manifest(
        repo_commit=new_root,
        core_commit=receipt["source"]["ccb_sipm_core_commit"],
        base_cli="--particle proton --energy 100",
        nevents_per_point=60,
        grid_sha256={"pde_scale": "a" * 64},
    )
    manifest_path = tmp_path / "campaign.json"
    raw = mod.campaign.canonical_manifest_bytes(manifest)
    manifest_path.write_bytes(raw)
    with pytest.raises(mod.BuildReceiptError, match="superproject commit != campaign"):
        mod.verify_receipt(
            receipt=receipt,
            executable=exe,
            runtime_probe=False,
            campaign_manifest=manifest_path,
            campaign_sha256=hashlib.sha256(raw).hexdigest(),
            repo_root=repo,
        )


def test_receipt_digest_and_canonical_bytes_fail_closed(tmp_path: Path):
    mod, _repo, _build, _exe, receipt = _receipt_fixture(tmp_path)
    path = tmp_path / "receipt.json"
    raw = mod._canonical_bytes(receipt)
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    loaded, observed_raw, observed_digest = mod.load_receipt(path, expected_sha256=digest)
    assert loaded == receipt
    assert observed_raw == raw
    assert observed_digest == digest
    path.write_bytes(raw + b" \n")
    with pytest.raises(mod.BuildReceiptError, match="digest mismatch"):
        mod.load_receipt(path, expected_sha256=digest)


def test_authorising_cmake_wires_post_build_receipt_and_clean_source_gate():
    cmake = (ROOT / "geant4" / "single_stave" / "CMakeLists.txt").read_text()
    assert "CCB_AUTHORISING_BUILD_RECEIPT" in cmake
    assert "requires Git and a completely clean source repository" in cmake
    assert "sipm_build_receipt.py" in cmake
    assert "add_custom_command(TARGET ccb_stave_sim POST_BUILD" in cmake
