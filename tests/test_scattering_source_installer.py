from __future__ import annotations

from pathlib import Path

import pytest

from geant4.src_patch.patch_scatter import install_reviewed_sources


ROOT = Path(__file__).resolve().parents[1]
TRACKED = ROOT / "geant4/src_patch"


def _make_external_tree(tmp_path: Path) -> Path:
    root = tmp_path / "hibeam_g4"
    (root / "include").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    (root / "include/ScatteringGenerator.hh").write_text("legacy header\n")
    (root / "src/ScatteringGenerator.cc").write_text("legacy source\n")
    return root


def test_installer_copies_reviewed_sources_byte_for_byte(tmp_path: Path) -> None:
    external = _make_external_tree(tmp_path)

    records = install_reviewed_sources(external)

    assert (external / "include/ScatteringGenerator.hh").read_bytes() == (
        TRACKED / "ScatteringGenerator.hh"
    ).read_bytes()
    assert (external / "src/ScatteringGenerator.cc").read_bytes() == (
        TRACKED / "ScatteringGenerator.cc"
    ).read_bytes()
    assert {record["path"] for record in records} == {
        "include/ScatteringGenerator.hh",
        "src/ScatteringGenerator.cc",
    }
    for record in records:
        assert len(record["sha256"]) == 64
        assert record["bytes"] > 0


def test_installer_fails_closed_when_external_layout_is_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="target directory does not exist"):
        install_reviewed_sources(tmp_path / "missing-tree")
