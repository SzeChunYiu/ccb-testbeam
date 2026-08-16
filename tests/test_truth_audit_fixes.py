"""Regression tests for the truth-extraction / PDG / geometry audit fixes
(TRU-001..010, ML-005, GEO-001).  Each test maps to a confirmed finding."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ccb_mc_validation.exceptions import (
    ConfigurationError,
    DataContractError,
    MCValidationError,
    UnitValidationError,
)
from ccb_mc_validation.truth import features as F
from ccb_mc_validation.truth.event_builder import (
    build_event_rows,
    compute_content_fingerprint,
    stable_event_id,
)
from ccb_mc_validation.truth.geometry import (
    DEFAULT_B_STAVES,
    DEFAULT_LAYER_MERGE_POLICY,
    READOUT_CONTRACT_VERSION,
    GeometryRegistry,
    build_layer_to_stave,
)
from ccb_mc_validation.truth.pdg import (
    kinetic_energy_from_branch_momentum,
    kinetic_energy_from_momentum,
    mass_of,
    pdg_charge,
)
from ccb_mc_validation.truth.track_builder import build_track_records
from ccb_mc_validation.truth.trigger import classify_event, process_chunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _proton_chunk(*, momentum_gev, layers=(0, 1), n_b_layers=8):
    """One proton track, single hit per listed layer at ``momentum_gev`` GeV/c."""
    layers = list(layers)
    n = len(layers)
    return {
        "Sci_bar_TrackID": np.array([np.zeros(n, dtype=int)], dtype=object),
        "Sci_bar_LayerID": np.array([np.array(layers, dtype=int)], dtype=object),
        "Sci_bar_LayerID1": np.array([np.ones(n, dtype=int)], dtype=object),
        "Sci_bar_PDG": np.array([np.full(n, 2212, dtype=int)], dtype=object),
        "Sci_bar_EDep": np.array([np.full(n, 1.0)], dtype=object),
        "Sci_bar_TrackLength": np.array([np.full(n, 10.0)], dtype=object),
        "Sci_bar_Momentum_X": np.array([np.full(n, float(momentum_gev))], dtype=object),
        "Sci_bar_Momentum_Y": np.array([np.zeros(n)], dtype=object),
        "Sci_bar_Momentum_Z": np.array([np.zeros(n)], dtype=object),
    }, n_b_layers


# ===========================================================================
# TRU-001 / TRU-002: momentum units (GeV/c -> MeV/c) and analytic KE
# ===========================================================================
@pytest.mark.parametrize(
    "pdg, mass, p_gev",
    [
        (2212, 938.272, 0.1),       # 100 MeV/c proton
        (2212, 938.272, 0.435),     # ~100 MeV KE proton regime
        (1000010020, 1875.613, 0.5),  # 500 MeV/c deuteron
    ],
)
def test_tru001_known_particle_kinetic_energy(pdg, mass, p_gev) -> None:
    """Known-particle KE matches the analytic relativistic formula."""
    got = kinetic_energy_from_branch_momentum(p_gev, pdg, momentum_unit="GeV")
    p_mev = p_gev * 1000.0
    expected = math.sqrt(p_mev * p_mev + mass * mass) - mass
    assert got == pytest.approx(expected, rel=1e-12)


def test_tru001_wrong_unit_would_underestimate_ke() -> None:
    """Reading 0.1 GeV/c as MeV/c gives KE~=0.005 MeV (the #864 bug); as GeV it
    gives the correct ~5.31 MeV.  Guards against the regression."""
    correct = kinetic_energy_from_branch_momentum(0.1, 2212, momentum_unit="GeV")
    wrong = kinetic_energy_from_branch_momentum(0.1, 2212, momentum_unit="MeV")
    assert correct == pytest.approx(5.3139, rel=1e-3)
    assert wrong < 6e-3  # ~1000x underestimate if units are wrong


def test_tru001_unknown_momentum_unit_raises() -> None:
    with pytest.raises(UnitValidationError):
        kinetic_energy_from_branch_momentum(0.1, 2212, momentum_unit="keV")


def test_tru001_kinetic_energy_primitive_is_mev_c() -> None:
    # primitive expects MeV/c already
    assert kinetic_energy_from_momentum(100.0, 2212) == pytest.approx(5.3139, rel=1e-3)


def test_tru002_track_builder_uses_gev_default() -> None:
    chunk, _ = _proton_chunk(momentum_gev=0.1, layers=(0, 1))
    rec = build_track_records(chunk, source="x.root")
    assert rec[0]["ekin"] == pytest.approx(5.3139, rel=1e-3)
    assert rec[0]["momentum_unit"] == "GeV"  # krakow default encoded


# ===========================================================================
# TRU-003: deepest observed layer != stopping layer
# ===========================================================================
def test_tru003_escaped_track_is_not_stop() -> None:
    chunk, n = _proton_chunk(momentum_gev=0.3, layers=tuple(range(8)))  # punches through
    rec = build_track_records(chunk, source="x.root", n_b_layers=n)
    assert rec[0]["termination"] == "escape"
    assert rec[0]["stop_layer"] is None
    assert rec[0]["last_observed_layer"] == 7


def test_tru003_stopping_track_labelled_from_ke() -> None:
    # Ranges out in layer 2; last residual momentum tiny -> sub-threshold KE.
    layers = (0, 1, 2)
    n = len(layers)
    chunk = {
        "Sci_bar_TrackID": np.array([np.zeros(n, dtype=int)], dtype=object),
        "Sci_bar_LayerID": np.array([np.array(layers, dtype=int)], dtype=object),
        "Sci_bar_LayerID1": np.array([np.ones(n, dtype=int)], dtype=object),
        "Sci_bar_PDG": np.array([np.full(n, 2212, dtype=int)], dtype=object),
        "Sci_bar_EDep": np.array([np.full(n, 5.0)], dtype=object),
        "Sci_bar_TrackLength": np.array([np.full(n, 10.0)], dtype=object),
        "Sci_bar_Momentum_X": np.array([np.array([0.2, 0.05, 0.001])], dtype=object),
        "Sci_bar_Momentum_Y": np.array([np.zeros(n)], dtype=object),
        "Sci_bar_Momentum_Z": np.array([np.zeros(n)], dtype=object),
    }
    rec = build_track_records(chunk, source="x.root", n_b_layers=8)
    assert rec[0]["termination"] == "stop"
    assert rec[0]["stop_layer"] == 2
    assert rec[0]["ekin_last_observed"] <= 1.0


# ===========================================================================
# TRU-004: MC event/track weights propagated (canonical builder)
# ===========================================================================
def test_tru004_weights_propagated_when_branch_present() -> None:
    chunk, _ = _proton_chunk(momentum_gev=0.1, layers=(0, 1))
    chunk["PrimaryWeight"] = np.array([np.array([2.5])], dtype=object)
    rec = build_track_records(chunk, source="x.root")
    assert rec[0]["weighted"] is True
    assert rec[0]["event_weight"] == 2.5
    assert rec[0]["track_weight"] == 2.5


def test_tru004_weights_explicitly_unweighted_when_absent() -> None:
    chunk, _ = _proton_chunk(momentum_gev=0.1, layers=(0, 1))
    rec = build_track_records(chunk, source="x.root")
    # Not silently discarded: the record declares weighted=False, weight=1.
    assert rec[0]["weighted"] is False
    assert rec[0]["event_weight"] == 1.0


# ===========================================================================
# TRU-005: identifiers + provenance are mandatory columns
# ===========================================================================
def test_tru005_identifiers_and_provenance_present() -> None:
    chunk, _ = _proton_chunk(momentum_gev=0.1, layers=(0, 1))
    rec = build_track_records(chunk, source="/data/mc.root", entry_offset=42)
    for key in ("track_id", "event_index", "source", "pdg", "ekin"):
        assert key in rec[0]
    assert rec[0]["source"] == "/data/mc.root"
    assert rec[0]["event_index"] == 42


# ===========================================================================
# TRU-006: unknown elementary particle must not inherit pion mass
# ===========================================================================
def test_tru006_unknown_elementary_mass_raises() -> None:
    # 3222 (Sigma+) is charged but not in our vetted table -> fail closed.
    with pytest.raises(MCValidationError):
        mass_of(3222)


def test_tru006_known_species_have_vetted_masses() -> None:
    assert mass_of(2212) == 938.272
    assert mass_of(211) == pytest.approx(139.570)   # pion now explicit, not default
    assert mass_of(-211) == pytest.approx(139.570)  # anti-pion same mass
    assert mass_of(11) == pytest.approx(0.510999)
    assert mass_of(1000010020) == 1875.613


# ===========================================================================
# TRU-007: anti-nucleus charge sign
# ===========================================================================
@pytest.mark.parametrize(
    "pdg, expected",
    [
        (2212, 1.0),
        (-2212, -1.0),            # anti-proton
        (1000010020, 1.0),
        (-1000010020, -1.0),      # anti-deuteron
        (1000020040, 2.0),
        (-1000020040, -2.0),      # anti-alpha
    ],
)
def test_tru007_anti_nucleus_charge_sign(pdg, expected) -> None:
    assert pdg_charge(pdg) == expected


# ===========================================================================
# TRU-008: stable event id is content+tree+entry (path-independent)
# ===========================================================================
def test_tru008_event_id_path_independent(tmp_path) -> None:
    fp = "deadbeef" * 8  # 64-hex sha-256-like
    a = stable_event_id(fp, "hibeam", 7)
    b = stable_event_id(fp, "hibeam", 7)
    assert a == b
    # Different entry -> different id
    assert stable_event_id(fp, "hibeam", 8) != a
    # Content fingerprint drives the id, not the path
    chunk = _empty_safe_chunk()
    r1 = build_event_rows(chunk, content_fingerprint=fp, coinc_ns=15.0, source="/a/x.root")
    r2 = build_event_rows(chunk, content_fingerprint=fp, coinc_ns=15.0, source="/different/y.root")
    assert r1[0]["event_id"] == r2[0]["event_id"]


def test_tru008_content_fingerprint_changes_with_bytes(tmp_path) -> None:
    f1 = tmp_path / "a.root"
    f2 = tmp_path / "b.root"
    f1.write_bytes(b"hello")
    f2.write_bytes(b"hello!")
    assert compute_content_fingerprint(f1) != compute_content_fingerprint(f2)


# ===========================================================================
# TRU-009: empty/zero-hit truth entries retained
# ===========================================================================
def test_tru009_zero_hit_events_retained() -> None:
    chunk = {
        "Sci_bar_LayerID": np.array([np.array([0, 0]), np.array([]), np.array([0])], dtype=object),
        "Sci_bar_LayerID1": np.array([np.array([1, 2]), np.array([]), np.array([1])], dtype=object),
        "Sci_bar_PDG": np.array(
            [np.array([2212, 2212]), np.array([]), np.array([2212])], dtype=object
        ),
        "Sci_bar_Time": np.array(
            [np.array([10.0, 12.0]), np.array([]), np.array([4.0])], dtype=object
        ),
    }
    rows = build_event_rows(chunk, content_fingerprint="c" * 64, coinc_ns=15.0)
    assert len(rows) == 3
    assert rows[1]["n_hits"] == 0
    assert rows[1]["has_hits"] is False
    assert rows[1]["sample_II"] is False


# ===========================================================================
# TRU-010: jagged lengths + coincidence validated
# ===========================================================================
def test_tru010_bad_coincidence_rejected() -> None:
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises((ConfigurationError, DataContractError)):
            classify_event(True, True, 0.0, 5.0, bad)


def test_tru010_jagged_length_mismatch_rejected() -> None:
    with pytest.raises(DataContractError):
        process_chunk(
            np.array([np.array([0, 0])], dtype=object),
            np.array([np.array([1])], dtype=object),       # wrong length
            np.array([np.array([2212, 2212])], dtype=object),
            np.array([np.array([1.0, 2.0])], dtype=object),
            15.0,
        )


def test_tru010_nonfinite_time_rejected() -> None:
    with pytest.raises(DataContractError):
        process_chunk(
            np.array([np.array([0])], dtype=object),
            np.array([np.array([1])], dtype=object),
            np.array([np.array([2212])], dtype=object),
            np.array([np.array([float("nan")])], dtype=object),
            15.0,
        )


# ===========================================================================
# ML-005: no target leakage in feature vectors
# ===========================================================================
def test_ml005_features_never_include_target() -> None:
    assert "ekin" not in F.MV1_FEATURE_NAMES
    assert "ekin" not in F.MV2_FEATURE_NAMES
    track = {
        "edep_l0": 1.0, "edep_l1": 2.0, "edep_tot": 3.0,
        "last_observed_layer": 2, "nlayers": 3, "tracklen_sum": 30.0,
        "ekin": 85.0,
    }
    x = F.extract_mv2_features(track)
    assert "ekin" not in F.MV2_FEATURE_NAMES
    assert F.extract_mv2_target(track) == 85.0
    assert 85.0 not in x.tolist()
    with pytest.raises(ValueError):
        F.assert_no_target_leakage(("ekin",))


def test_ml005_mv1_uses_observed_layer() -> None:
    track = {
        "edep_l0": 1.0, "edep_l1": 2.0, "edep_tot": 3.0,
        "last_observed_layer": 2,
    }
    x = F.extract_mv1_features(track)
    assert x[-1] == 2.0
    assert F.MV1_FEATURE_NAMES[-1] == "last_observed_layer"


# ===========================================================================
# GEO-001: versioned, fail-closed geometry contract
# ===========================================================================
def test_geo001_default_policy_is_pair_merge_and_versioned() -> None:
    reg = GeometryRegistry.from_config({})
    assert reg.layer_merge_policy == DEFAULT_LAYER_MERGE_POLICY == "pair_merge"
    assert reg.readout_contract_version == READOUT_CONTRACT_VERSION
    # 8 krakow B layers merge in pairs to B2/B4/B6/B8
    assert reg.stave_for_layer(0) == "B2"
    assert reg.stave_for_layer(1) == "B2"
    assert reg.stave_for_layer(7) == "B8"


def test_geo001_ambiguous_mapping_fails_closed() -> None:
    # 8 layers + one_to_one policy is inconsistent -> must not silently guess
    with pytest.raises(ConfigurationError):
        build_layer_to_stave(DEFAULT_B_STAVES, n_b_layers=8, policy="one_to_one")
    with pytest.raises(ConfigurationError):
        build_layer_to_stave(DEFAULT_B_STAVES, n_b_layers=4, policy="pair_merge")


def test_geo001_one_to_one_still_supported() -> None:
    m = build_layer_to_stave(DEFAULT_B_STAVES, n_b_layers=4, policy="one_to_one")
    assert m == {0: "B2", 1: "B4", 2: "B6", 3: "B8"}


def _empty_safe_chunk():
    return {
        "Sci_bar_LayerID": np.array([np.array([0])], dtype=object),
        "Sci_bar_LayerID1": np.array([np.array([1])], dtype=object),
        "Sci_bar_PDG": np.array([np.array([2212])], dtype=object),
        "Sci_bar_Time": np.array([np.array([5.0])], dtype=object),
    }
