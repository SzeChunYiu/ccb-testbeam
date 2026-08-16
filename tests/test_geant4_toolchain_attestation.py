from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.audit.geant4_toolchain_attestation import attest_cmake_toolchain


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _with_digest(body: dict[str, object]) -> dict[str, object]:
    result = dict(body)
    result["receipt_sha256"] = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return result


def _make_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _final_receipt(executable: Path) -> dict[str, object]:
    payload = executable.read_bytes()
    body: dict[str, object] = {
        "schema": "ccb_geant4_build_binding_final_v1",
        "status": "PASS",
        "begin_receipt_sha256": "b" * 64,
        "source": {"fixture": True},
        "staged_inputs": [{"label": "fixture"}],
        "build_contract": {"compiler_id": "declared-only-string"},
        "executable": {
            "path": str(executable.resolve()),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        "limitations": ["fixture"],
        "scientific_scope": "fixture",
    }
    return _with_digest(body)


def _fixture(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    cmake = tmp_path / "cmake"
    cxx = tmp_path / "cxx"
    _make_executable(cmake, "#!/bin/sh\necho 'cmake version fixture-1.0'\n")
    _make_executable(cxx, "#!/bin/sh\necho 'fixture-cxx 9.1'\n")

    g4_dir = tmp_path / "g4"
    vgm_dir = tmp_path / "vgm"
    g4_dir.mkdir()
    vgm_dir.mkdir()
    (g4_dir / "Geant4Config.cmake").write_text(
        "set(Geant4_VERSION 11.2.2)\n", encoding="utf-8"
    )
    (vgm_dir / "VGMConfig.cmake").write_text(
        "set(VGM_VERSION 5.4.0)\n", encoding="utf-8"
    )

    cache = tmp_path / "CMakeCache.txt"
    cache.write_text(
        "\n".join(
            [
                "// fixture cache",
                f"CMAKE_COMMAND:INTERNAL={cmake}",
                f"CMAKE_CXX_COMPILER:FILEPATH={cxx}",
                "CMAKE_GENERATOR:INTERNAL=Unix Makefiles",
                f"Geant4_DIR:PATH={g4_dir}",
                f"VGM_DIR:PATH={vgm_dir}",
                "ROOT_DIR:PATH=/fixture/root",
                "",
            ]
        ),
        encoding="utf-8",
    )

    built = tmp_path / "hibeam_g4"
    built.write_bytes(b"ELF fixture output\n")
    return cache, built, g4_dir, vgm_dir, cmake, cxx


def _attest(tmp_path: Path):
    cache, built, *_ = _fixture(tmp_path)
    return attest_cmake_toolchain(
        final_receipt=_final_receipt(built),
        cmake_cache=cache,
        required_cache_keys=["Geant4_DIR", "VGM_DIR"],
        package_specs=[
            ("geant4", "Geant4_DIR", "Geant4Config.cmake"),
            ("vgm", "VGM_DIR", "VGMConfig.cmake"),
        ],
    )


def test_attestation_binds_cache_selected_tools_packages_and_executable(
    tmp_path: Path,
) -> None:
    result = _attest(tmp_path)

    assert result["status"] == "PASS"
    assert result["schema"] == "ccb_geant4_cmake_toolchain_attestation_v1"
    assert result["selected_cache_entries"]["CMAKE_GENERATOR"]["value"] == (
        "Unix Makefiles"
    )
    assert result["tools"]["cmake"]["probe_returncode"] == 0
    assert "cmake version fixture-1.0" in result["tools"]["cmake"]["probe_stdout"]
    assert "fixture-cxx 9.1" in result["tools"]["cxx_compiler"]["probe_stdout"]
    assert [item["label"] for item in result["packages"]] == ["geant4", "vgm"]
    assert len(result["receipt_sha256"]) == 64


def test_declared_compiler_string_does_not_override_measured_cache_identity(
    tmp_path: Path,
) -> None:
    cache, built, *_, cxx = _fixture(tmp_path)
    receipt = _final_receipt(built)
    assert receipt["build_contract"]["compiler_id"] == "declared-only-string"

    result = attest_cmake_toolchain(
        final_receipt=receipt,
        cmake_cache=cache,
        required_cache_keys=[],
        package_specs=[("geant4", "Geant4_DIR", "Geant4Config.cmake")],
    )

    assert result["tools"]["cxx_compiler"]["resolved_path"] == str(cxx.resolve())
    assert result["tools"]["cxx_compiler"]["resolved_sha256"] == hashlib.sha256(
        cxx.read_bytes()
    ).hexdigest()


def test_executable_mutation_after_final_receipt_fails_closed(tmp_path: Path) -> None:
    cache, built, *_ = _fixture(tmp_path)
    receipt = _final_receipt(built)
    built.write_bytes(b"different executable\n")

    with pytest.raises(ValueError, match="bound executable identity changed"):
        attest_cmake_toolchain(
            final_receipt=receipt,
            cmake_cache=cache,
            required_cache_keys=[],
            package_specs=[("geant4", "Geant4_DIR", "Geant4Config.cmake")],
        )


def test_duplicate_or_missing_required_cache_key_fails_closed(tmp_path: Path) -> None:
    cache, built, *_ = _fixture(tmp_path)
    cache.write_text(
        cache.read_text(encoding="utf-8")
        + "CMAKE_CXX_COMPILER:FILEPATH=/another/compiler\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate CMake cache key CMAKE_CXX_COMPILER"):
        attest_cmake_toolchain(
            final_receipt=_final_receipt(built),
            cmake_cache=cache,
            required_cache_keys=[],
            package_specs=[("geant4", "Geant4_DIR", "Geant4Config.cmake")],
        )

    cache2, built2, *_ = _fixture(tmp_path / "second")
    with pytest.raises(ValueError, match="required CMake cache key is missing: MISSING_KEY"):
        attest_cmake_toolchain(
            final_receipt=_final_receipt(built2),
            cmake_cache=cache2,
            required_cache_keys=["MISSING_KEY"],
            package_specs=[("geant4", "Geant4_DIR", "Geant4Config.cmake")],
        )


def test_nonzero_tool_version_probe_fails_closed(tmp_path: Path) -> None:
    cache, built, *_, cxx = _fixture(tmp_path)
    _make_executable(cxx, "#!/bin/sh\necho broken >&2\nexit 7\n")

    with pytest.raises(ValueError, match="version probe returned 7"):
        attest_cmake_toolchain(
            final_receipt=_final_receipt(built),
            cmake_cache=cache,
            required_cache_keys=[],
            package_specs=[("geant4", "Geant4_DIR", "Geant4Config.cmake")],
        )


def test_package_sentinel_must_be_rooted_below_absolute_cache_path(
    tmp_path: Path,
) -> None:
    cache, built, *_ = _fixture(tmp_path)
    cache.write_text(
        cache.read_text(encoding="utf-8").replace(
            f"Geant4_DIR:PATH={tmp_path / 'g4'}", "Geant4_DIR:PATH=relative/g4"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="package cache root Geant4_DIR must be absolute"):
        attest_cmake_toolchain(
            final_receipt=_final_receipt(built),
            cmake_cache=cache,
            required_cache_keys=[],
            package_specs=[("geant4", "Geant4_DIR", "Geant4Config.cmake")],
        )


def test_symlinked_package_sentinel_records_target_identity(tmp_path: Path) -> None:
    cache, built, g4_dir, *_ = _fixture(tmp_path)
    sentinel = g4_dir / "Geant4Config.cmake"
    target = g4_dir / "Geant4Config.real.cmake"
    sentinel.rename(target)
    sentinel.symlink_to(target.name)

    result = attest_cmake_toolchain(
        final_receipt=_final_receipt(built),
        cmake_cache=cache,
        required_cache_keys=[],
        package_specs=[("geant4", "Geant4_DIR", "Geant4Config.cmake")],
    )

    record = result["packages"][0]["sentinel"]
    assert record["path_is_symlink"] is True
    assert record["symlink_target"] == target.name
    assert record["resolved_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
