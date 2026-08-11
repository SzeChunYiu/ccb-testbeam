from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "geant4/src_patch/ScatteringGenerator.cc"


def test_phi_measure_is_uniform_full_2pi() -> None:
    """Freeze the H1 source phi measure: full physical azimuthal range.

    The source emits ejectile and recoil with phi uniformly distributed over
    [0, 2*pi) — no detector-surrogate pre-acceptance narrows the azimuthal
    measure. The 50/50 coplanar flip ensures both particles cover the full
    circle.
    """
    cpp = CPP.read_text(encoding="utf-8")

    # Source-model versioned ID — the phi measure is part of the explicit
    # source-model contract, matching the style of the CDF IDs.
    assert "source_phi_measure = uniform_full_2pi_v1" in cpp

    # Full 2*pi azimuthal generation — the core fix for #1057.
    # The literal `2*pi*G4UniformRand()` is the H1 primordial form; any
    # refactoring must preserve the uniform full-circle measure.
    assert "2*pi*G4UniformRand()" in cpp


def test_detector_surrogate_removed_from_phi_generation() -> None:
    """The detector-surrogate geometry (det_size, det_distance, phi_max) is
    completely removed from the source. The generator does not refer to either
    detector geometry or an azimuthal acceptance window.
    """
    cpp = CPP.read_text(encoding="utf-8")

    # The hard-coded detector-surrogate constants that constrained the
    # azimuthal range in the original H0 implementation. Their removal is
    # the defining structural change for ARU-MC-SOURCE-PHI-001.
    assert "det_size" not in cpp
    assert "det_distance" not in cpp
    assert "phi_max" not in cpp