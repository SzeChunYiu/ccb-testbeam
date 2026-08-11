from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.audit.geant4_build_binding_receipt import (
    begin_build_binding,
    finalize_build_binding,
)
from tools.audit.validate_geant4_external_overlay import PAYLOADS

REPO_ROOT = Path(".")
BUILD_CONTRACT = {
    "configure_argv": ["cmake", "-DVGM_DIR=/fixture/vgm", ".."],
    "build_argv": ["cmake", "--build", ".", "--parallel", "4"],
    "compiler_id": "fixture-cxx",
    "cmake_id": "fixture-cmake",
    "geant4_id": "fixture-geant4",
    "vgm_id": "fixture-vgm",
}


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _fixture_external(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "external"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.name", "CCB build-binding fixture")
    _git(root, "config", "user.email", "ccb-fixture@example.invalid")
    for external_rel in PAYLOADS:
        path = root / external_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"upstream {external_rel}\n", encoding="utf-8")
    (root / "README.fixture").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture baseline")
    commit = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    for external_rel, reviewed_rel in PAYLOADS.items():
        shutil.copyfile(REPO_ROOT / reviewed_rel, root / external_rel)
    return root, commit, tree


def _staged_inputs(tmp_path: Path) -> list[tuple[str, Path]]:
    config = tmp_path / "krakow.config"
    macro = tmp_path / "run_krakow.mac"
    source = tmp_path / "sigma_pd_cm_190.txt"
    config.write_text("Config fixture\n", encoding="utf-8")
    macro.write_text("/run/beamOn 10\n", encoding="utf-8")
    source.write_text("26.49 1.0 0.1\n", encoding="utf-8")
    return [("config", config), ("macro", macro), ("cross_section", source)]


def _begin(
    root: Path,
    commit: str,
    tree: str,
    inputs: list[tuple[str, Path]],
) -> dict[str, object]:
    return begin_build_binding(
        external_root=root,
        repo_root=REPO_ROOT,
        expected_commit=commit,
        expected_tree=tree,
        inputs=inputs,
        build_contract=BUILD_CONTRACT,
    )


def test_unchanged_source_inputs_bind_to_exact_executable(tmp_path: Path) -> None:
    root, commit, tree = _fixture_external(tmp_path)
    inputs = _staged_inputs(tmp_path)
    begin = _begin(root, commit, tree, inputs)
    executable = tmp_path / "hibeam_g4"
    executable.write_bytes(b"ELF fixture bytes\n")

    result = finalize_build_binding(
        begin_receipt=begin,
        external_root=root,
        repo_root=REPO_ROOT,
        expected_commit=commit,
        expected_tree=tree,
        inputs=inputs,
        executable=executable,
    )

    assert result["status"] == "PASS"
    assert result["begin_receipt_sha256"] == begin["receipt_sha256"]
    assert result["executable"]["bytes"] == len(b"ELF fixture bytes\n")
    assert len(result["executable"]["sha256"]) == 64
    assert result["staged_inputs"] == begin["staged_inputs"]


def test_source_mutation_between_begin_and_finalize_fails_closed(tmp_path: Path) -> None:
    root, commit, tree = _fixture_external(tmp_path)
    inputs = _staged_inputs(tmp_path)
    begin = _begin(root, commit, tree, inputs)
    first = root / next(iter(PAYLOADS))
    first.write_text("mutated after begin\n", encoding="utf-8")
    executable = tmp_path / "hibeam_g4"
    executable.write_bytes(b"fixture\n")

    with pytest.raises(ValueError, match="reviewed source byte mismatch"):
        finalize_build_binding(
            begin_receipt=begin,
            external_root=root,
            repo_root=REPO_ROOT,
            expected_commit=commit,
            expected_tree=tree,
            inputs=inputs,
            executable=executable,
        )


def test_staged_input_mutation_between_begin_and_finalize_fails_closed(
    tmp_path: Path,
) -> None:
    root, commit, tree = _fixture_external(tmp_path)
    inputs = _staged_inputs(tmp_path)
    begin = _begin(root, commit, tree, inputs)
    inputs[1][1].write_text("/run/beamOn 999\n", encoding="utf-8")
    executable = tmp_path / "hibeam_g4"
    executable.write_bytes(b"fixture\n")

    with pytest.raises(ValueError, match="staged input identity changed"):
        finalize_build_binding(
            begin_receipt=begin,
            external_root=root,
            repo_root=REPO_ROOT,
            expected_commit=commit,
            expected_tree=tree,
            inputs=inputs,
            executable=executable,
        )


def test_symlinked_input_fails_closed(tmp_path: Path) -> None:
    root, commit, tree = _fixture_external(tmp_path)
    inputs = _staged_inputs(tmp_path)
    target = tmp_path / "target.config"
    target.write_text("target\n", encoding="utf-8")
    inputs[0][1].unlink()
    inputs[0][1].symlink_to(target)

    with pytest.raises(ValueError, match="regular non-symlink"):
        _begin(root, commit, tree, inputs)


def test_symlinked_executable_fails_closed(tmp_path: Path) -> None:
    root, commit, tree = _fixture_external(tmp_path)
    inputs = _staged_inputs(tmp_path)
    begin = _begin(root, commit, tree, inputs)
    real_executable = tmp_path / "real_hibeam_g4"
    real_executable.write_bytes(b"fixture\n")
    executable = tmp_path / "hibeam_g4"
    executable.symlink_to(real_executable)

    with pytest.raises(ValueError, match="built executable must be a regular"):
        finalize_build_binding(
            begin_receipt=begin,
            external_root=root,
            repo_root=REPO_ROOT,
            expected_commit=commit,
            expected_tree=tree,
            inputs=inputs,
            executable=executable,
        )


def test_tampered_begin_receipt_fails_before_final_binding(tmp_path: Path) -> None:
    root, commit, tree = _fixture_external(tmp_path)
    inputs = _staged_inputs(tmp_path)
    begin = _begin(root, commit, tree, inputs)
    begin["build_contract"] = {"configure_argv": ["malicious replacement"]}
    executable = tmp_path / "hibeam_g4"
    executable.write_bytes(b"fixture\n")

    with pytest.raises(ValueError, match="receipt digest mismatch"):
        finalize_build_binding(
            begin_receipt=begin,
            external_root=root,
            repo_root=REPO_ROOT,
            expected_commit=commit,
            expected_tree=tree,
            inputs=inputs,
            executable=executable,
        )


def test_duplicate_label_or_path_and_empty_contract_fail_closed(tmp_path: Path) -> None:
    root, commit, tree = _fixture_external(tmp_path)
    inputs = _staged_inputs(tmp_path)

    with pytest.raises(ValueError, match="duplicate input label"):
        begin_build_binding(
            external_root=root,
            repo_root=REPO_ROOT,
            expected_commit=commit,
            expected_tree=tree,
            inputs=[("same", inputs[0][1]), ("same", inputs[1][1])],
            build_contract=BUILD_CONTRACT,
        )
    with pytest.raises(ValueError, match="same staged input path"):
        begin_build_binding(
            external_root=root,
            repo_root=REPO_ROOT,
            expected_commit=commit,
            expected_tree=tree,
            inputs=[("a", inputs[0][1]), ("b", inputs[0][1])],
            build_contract=BUILD_CONTRACT,
        )
    with pytest.raises(ValueError, match="build_contract"):
        begin_build_binding(
            external_root=root,
            repo_root=REPO_ROOT,
            expected_commit=commit,
            expected_tree=tree,
            inputs=inputs,
            build_contract={},
        )


def test_receipt_is_canonical_json_serialisable(tmp_path: Path) -> None:
    root, commit, tree = _fixture_external(tmp_path)
    receipt = _begin(root, commit, tree, _staged_inputs(tmp_path))

    encoded = json.dumps(receipt, sort_keys=True)

    assert "ccb_geant4_build_binding_begin_v1" in encoded
    assert len(receipt["receipt_sha256"]) == 64
