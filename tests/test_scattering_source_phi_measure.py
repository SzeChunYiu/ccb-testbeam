from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CPP = ROOT / "geant4/src_patch/ScatteringGenerator.cc"
MODEL = ROOT / "geant4/src_patch/scattering_source_model_v1.json"

PHI_BLOCK_START = "// Randomly generate phi across the full physical azimuthal range."
PHI_BLOCK_END = "//particle 1 at vertex A"


def _phi_block() -> str:
    cpp = CPP.read_text(encoding="utf-8")
    assert PHI_BLOCK_START in cpp
    assert PHI_BLOCK_END in cpp
    return cpp.split(PHI_BLOCK_START, 1)[1].split(PHI_BLOCK_END, 1)[0]


def _mapped_pair(u_phi: float, proton_gets_pi: bool) -> tuple[float, float]:
    base = math.tau * u_phi
    phi_p = base + math.pi if proton_gets_pi else base
    phi_d = base if proton_gets_pi else base + math.pi
    return phi_p % math.tau, phi_d % math.tau


def test_phi_measure_is_declared_in_source_model() -> None:
    """The tracked source-model contract declares full, unpreselected azimuth."""
    model = json.loads(MODEL.read_text(encoding="utf-8"))

    assert model["target_azimuthal_density"] == "p(phi) = 1/(2*pi) on [0,2*pi)"
    assert model["source_phi_measure"] == "uniform_full_2pi_v1"
    assert model["support_phi_rad"] == [0.0, math.tau]
    assert model["detector_surrogate_phi_preselection"] is False
    retired = model["hard_coded_detector_surrogate_phi_preacceptance"]
    assert retired["present"] is False
    assert retired["authorising_for_detector_claims"] is False
    assert retired["issue"] == 1057


def test_phi_code_implements_full_2pi_without_detector_surrogate() -> None:
    """Freeze the source implementation that realizes the declared H1 measure."""
    cpp = CPP.read_text(encoding="utf-8")
    block = _phi_block()

    assert "source_phi_measure = uniform_full_2pi_v1" in block
    assert "G4double phi3 = 2*pi*G4UniformRand();" in block
    assert "G4double phi4 = phi3;" in block
    assert "if(fiftyfifty<0.5){ phi3+=pi; }" in block
    assert "else{ phi4+=pi; }" in block

    assert "det_size" not in cpp
    assert "det_distance" not in cpp
    assert "phi_max" not in cpp


def test_phi_change_preserves_two_rng_draws_per_event() -> None:
    """Keep the legacy phi-stage RNG draw cardinality for paired-seed studies.

    The historical implementation used one draw for the narrow base azimuth and
    one draw for the 50/50 proton/deuteron branch. Keeping two draws means the
    next event starts at the same RNG-stream position when all other source
    paths are unchanged, so a seeded full-phi versus legacy comparison can
    isolate the azimuthal-measure change instead of silently shifting every
    later event's random inputs.
    """
    block = _phi_block()

    assert block.count("G4UniformRand()") == 2
    assert "G4double fiftyfifty = G4UniformRand();" in block


def test_full_phi_pair_map_is_uniform_and_back_to_back() -> None:
    """Deterministically falsify gaps, marginal bias, and lost coplanarity."""
    n_grid = 4096
    n_bins = 64
    proton_counts = [0] * n_bins
    deuteron_counts = [0] * n_bins

    for i in range(n_grid):
        u_phi = (i + 0.5) / n_grid
        for proton_gets_pi in (False, True):
            phi_p, phi_d = _mapped_pair(u_phi, proton_gets_pi)

            separation = (phi_d - phi_p) % math.tau
            assert math.isclose(separation, math.pi, rel_tol=0.0, abs_tol=1e-12)

            proton_counts[int(phi_p / math.tau * n_bins)] += 1
            deuteron_counts[int(phi_d / math.tau * n_bins)] += 1

    expected_per_bin = 2 * n_grid // n_bins
    assert proton_counts == [expected_per_bin] * n_bins
    assert deuteron_counts == [expected_per_bin] * n_bins
