from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "geant4/src_patch/ScatteringGenerator.cc"


def test_reviewed_cpp_includes_math_dependencies_required_by_sampler() -> None:
    cpp = CPP.read_text(encoding="utf-8")

    assert "#include <cmath>" in cpp
    assert "std::isfinite" in cpp
    assert "std::sqrt" in cpp
