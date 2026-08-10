from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "geant4/src_patch/ScatteringGenerator.cc"
PATCH = ROOT / "geant4/src_patch/patch_scatter.py"


def test_external_patch_injects_cmath_required_by_isfinite_and_sqrt() -> None:
    cpp = CPP.read_text(encoding="utf-8")
    patch = PATCH.read_text(encoding="utf-8")

    assert "#include <cmath>" in cpp
    assert "#include <cmath>" in patch
    for text in (cpp, patch):
        assert "std::isfinite" in text
        assert "std::sqrt" in text
