"""Source contracts for issue #1088: WLS fluorescence multiplicity model.

CI has no Geant4 build, so these assert the C++ SOURCES wire the three-mode
multiplicity contract exactly (precedent: test_lane08_waveC_contracts.py).
The runtime known-answer test (three modes, one seed, ratio == mode mean)
lives at geant4/single_stave/tests/test_wls_multiplicity.py and runs via
ctest where a build exists.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_1088_fibre_core_sets_property_only_in_poisson_mode():
    src = _src("geant4/single_stave/src/DetectorConstruction.cc")
    start = src.index("BuildFibreCore")
    core = src[start:]
    assert core.count('AddConstProperty("WLSMEANNUMBERPHOTONS"') == 1
    guard = 'if (cfg_.wls_fluorescence_model == "geant4_poisson_mean") {'
    assert guard in core
    # the AddConstProperty must come AFTER the guard, inside its braces
    assert core.index(guard) < core.index('AddConstProperty("WLSMEANNUMBERPHOTONS"')
    # the three modes are documented at the site
    for mode in ("geant4_default_one_secondary", "geant4_poisson_mean",
                 "bernoulli_thinned"):
        assert mode in core


def test_1088_digest_is_optical_v2_with_model_and_yield():
    src = _src("geant4/single_stave/src/DetectorConstruction.cc")
    start = src.index("DetectorConstruction::DetectorConstruction")
    end = src.index("DetectorConstruction::~DetectorConstruction")
    ctor = src[start:end]
    assert 'os << "schema=optical_v2"' in ctor
    assert ";wls_fluorescence_model=" in ctor
    assert ";wls_fluorescence_yield=" in ctor
    # v1 must be gone from the ctor
    assert "schema=optical_v1" not in ctor


def test_1088_appconfig_fields_and_cli():
    hh = _src("geant4/single_stave/include/AppConfig.hh")
    assert "double wls_fluorescence_yield = 0.70;" in hh
    cc = _src("geant4/single_stave/src/AppConfig.cc")
    for arg in ("--wls-fluorescence-model", "--wls-fluorescence-yield",
                "--wls-mean-number-photons"):
        assert f'eq(a, "{arg}")' in cc
    # fail-closed validation
    assert "--wls-fluorescence-yield must be in [0,1] for bernoulli_thinned" in cc
    assert "--wls-mean-number-photons must be > 0 for geant4_poisson_mean" in cc
    # status is DERIVED from the mode so metadata cannot disagree
    assert 'wls_fluorescence_status = "EXPLICIT_POISSON_MEAN"' in cc
    assert 'wls_fluorescence_status = "EXTERNAL_QE_PRIOR"' in cc


def test_1088_bernoulli_thinning_in_stacking_action():
    src = _src("geant4/single_stave/src/StackingAction.cc")
    assert 'cfg_.wls_fluorescence_model == "bernoulli_thinned"' in src
    assert "cfg_.wls_fluorescence_yield < 1.0" in src  # q=1 leaves RNG stream intact
    assert 'GetProcessName() == "OpWLS"' in src
    assert "G4UniformRand()" in src


def test_1088_absorption_counter_pipeline():
    sim = _src("geant4/single_stave/include/SimData.hh")
    assert "long n_wls_absorbed    = 0;" in sim
    assert "n_wls_generated = n_wls_absorbed = n_cerenkov_generated = 0;" in sim
    ta = _src("geant4/single_stave/src/TrackingAction.cc")
    assert "PostUserTrackingAction" in ta
    assert "n_wls_absorbed" in ta
    ra = _src("geant4/single_stave/src/RunAction.cc")
    assert 'CreateNtupleIColumn("n_wls_absorbed")' in ra
    assert "(int)e.n_wls_absorbed" in ra
    assert '\\"wls_fluorescence_yield\\": ' in ra


def test_1088_ledger_records_sourced_yield():
    ledger = _src("configs/optical/optical_constants_ledger.conf")
    assert "wls_fluorescence_yield = 0.70" in ledger
    assert "Pla-Dalmau" in ledger
    assert "arXiv:1911.03790" in ledger


def test_1088_known_answer_test_registered():
    cml = _src("geant4/single_stave/CMakeLists.txt")
    assert "ccb_stave_wls_multiplicity" in cml
    assert (ROOT / "geant4/single_stave/tests/test_wls_multiplicity.py").is_file()


def test_1088_contract_doc_and_paper_note_exist():
    doc = _src("docs/contracts/WLS_FLUORESCENCE_MULTIPLICITY.md")
    assert "geant4_default_one_secondary" in doc
    assert "Poisson" in doc and "Bernoulli" in doc
    assert "533d58e8" in doc  # grid provenance consequence recorded
    paper = _src("publication/chapters/08_optical_response.tex")
    # Editorial pass removed internal issue ids from reader-facing prose; the
    # paper-note invariant is now pinned on the de-identified phrasing that
    # carries the same content (default-one label + three-mode correction).
    assert "three-mode" in paper
    assert "default-one" in paper
