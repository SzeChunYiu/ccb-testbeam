"""Lane 08 Wave C: Birks kB, geometry digests, qtemplate/grid fail-closed (#1079/#986/#965/#1064/#1007)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.timing.qtemplate_contract import (
    QTEMPLATE_STATUS,
    assert_qtemplate_non_authorising,
    qtemplate_provenance,
)
from ccb_mc_validation.timing.template_phase_grid import (
    TEMPLATE_PHASE_GRID_STEP_SAMPLES,
    assert_template_resolution_authorised,
    default_template_phase_grid,
    template_phase_grid_contract,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# #1079 Birks kB explicit config
# ---------------------------------------------------------------------------
def test_1079_apply_birks_requires_explicit_kb():
    with pytest.raises(ValueError, match="birks_kB_cm_per_MeV|birks_kB_mm_per_MeV|#1079"):
        DigitizerPipeline.from_config({"apply_birks": True})


def test_1079_mm_unit_converts_to_cm():
    pipe = DigitizerPipeline.from_config(
        {"apply_birks": True, "birks_kB_mm_per_MeV": 0.126}
    )
    assert pipe.birks_kB_cm_per_MeV == pytest.approx(0.0126)


def test_1079_requested_kb_reaches_executed_law():
    # Known-answer: E=10 MeV over 1 cm => dE/dx=10 MeV/cm
    # L = E / (1 + kB * dE/dx)
    hit = {"edep_mev": 10.0, "time_ns": 0.0, "step_length_cm": 1.0}
    kb = 0.008
    pipe = DigitizerPipeline.from_config(
        {"apply_birks": True, "birks_kB_cm_per_MeV": kb}
    )
    out = pipe._stage_birks(hit, np.random.default_rng(0), {"event_id": 1, "channel_id": 0})
    expected = 10.0 / (1.0 + kb * 10.0)
    assert out["edep_mev"] == pytest.approx(expected)


def test_1079_unit_negative_control_cm_vs_mm_differs_by_ten():
    hit = {"edep_mev": 10.0, "time_ns": 0.0, "step_length_cm": 1.0}
    as_cm = DigitizerPipeline.from_config(
        {"apply_birks": True, "birks_kB_cm_per_MeV": 0.126}
    )
    as_mm = DigitizerPipeline.from_config(
        {"apply_birks": True, "birks_kB_mm_per_MeV": 0.126}
    )
    ctx = {"event_id": 1, "channel_id": 0}
    rng = np.random.default_rng(0)
    e_cm = as_cm._stage_birks(hit, rng, ctx)["edep_mev"]
    e_mm = as_mm._stage_birks(hit, rng, ctx)["edep_mev"]
    assert e_cm != pytest.approx(e_mm)
    assert as_cm.birks_kB_cm_per_MeV == pytest.approx(10.0 * as_mm.birks_kB_cm_per_MeV)


def test_1079_birks_off_still_allows_missing_kb():
    pipe = DigitizerPipeline.from_config({"apply_birks": False})
    assert pipe.birks_kB_cm_per_MeV is None
    out = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=1)
    assert out["adc"].shape == (18,)


# ---------------------------------------------------------------------------
# #986 geometry / physics / optical digest split (source contract)
# ---------------------------------------------------------------------------
def test_986_geometry_ctor_excludes_birks_and_includes_far_end():
    src = (ROOT / "geant4/single_stave/src/DetectorConstruction.cc").read_text(encoding="utf-8")
    # Extract constructor body roughly
    start = src.index("DetectorConstruction::DetectorConstruction")
    end = src.index("DetectorConstruction::~DetectorConstruction")
    ctor = src[start:end]
    # GEOMETRY_DIGEST_V2 (#986): mass geometry vs physics_hash response knobs.
    assert "schema_version=2.0.0" in ctor
    assert "far_end_mode=" in ctor
    assert "coating_thk_mm=" in ctor
    assert "sensor_thk_mm=" in ctor
    assert "physics_hash_" in ctor
    assert "optical_hash_" in ctor
    geo_block = ctor.split("geometry_hash_ = Sha256::hex")[0]
    assert "birks_kB_mm_per_MeV" not in geo_block
    assert "scintillator_material" not in geo_block
    assert "PhysicsHash()" in (ROOT / "geant4/single_stave/include/DetectorConstruction.hh").read_text(
        encoding="utf-8"
    )


def test_986_run_sidecar_records_physics_and_optical_hash():
    body = (ROOT / "geant4/single_stave/src/RunAction.cc").read_text(encoding="utf-8")
    assert "physics_hash_" in body
    assert "optical_hash_" in body
    assert "WriteMetadataSidecar" in body


def test_986_adr_documents_digest_split():
    adr = (ROOT / "docs/adr/ADR-0005-geometry-physics-optical-digests.md").read_text(encoding="utf-8")
    assert "#986" in adr
    assert "far_end_mode" in adr
    assert "physics_hash" in adr


# ---------------------------------------------------------------------------
# #965 qtemplate heuristic gate
# ---------------------------------------------------------------------------
def test_965_qtemplate_is_heuristic_not_authorising():
    prov = qtemplate_provenance()
    assert prov["status"] == QTEMPLATE_STATUS
    assert prov["authorising"] is False
    with pytest.raises(ValueError, match="HEURISTIC_SCORE"):
        assert_qtemplate_non_authorising({"authorising": True})


def test_965_adr_or_contract_mentions_held_out():
    body = (ROOT / "src/ccb_mc_validation/timing/qtemplate_contract.py").read_text(encoding="utf-8")
    assert "held-out" in body.lower() or "HELD_OUT" in body


# ---------------------------------------------------------------------------
# #1064 template-phase grid quantization
# ---------------------------------------------------------------------------
def test_1064_default_grid_step_is_0_05_samples():
    grid = default_template_phase_grid()
    assert TEMPLATE_PHASE_GRID_STEP_SAMPLES == pytest.approx(0.05)
    assert grid[1] - grid[0] == pytest.approx(0.05)


def test_1064_contract_exposes_half_step_ns_at_10ns_clock():
    contract = template_phase_grid_contract(sample_period_ns=10.0)
    assert contract["grid_step_ns"] == pytest.approx(0.5)
    assert contract["grid_half_step_ns"] == pytest.approx(0.25)
    assert contract["interpolation"] == "NONE"
    assert contract["authorising_sub_grid_claims"] is False


def test_1064_rejects_authorising_finer_than_half_grid():
    with pytest.raises(ValueError, match="#1064"):
        assert_template_resolution_authorised(
            0.1, sample_period_ns=10.0, context={"authorising": True}
        )
    # Exploratory / non-authorising may still record a fine number.
    out = assert_template_resolution_authorised(
        0.1, sample_period_ns=10.0, context={"authorising": False}
    )
    assert out["authorising"] is False


# ---------------------------------------------------------------------------
# #1007 stopping-power diagnostic remains non-primary
# ---------------------------------------------------------------------------
def test_1007_compare_stopping_power_labels_event_total_mismatch():
    src = (ROOT / "scripts/single_stave/compare_stopping_power.py").read_text(encoding="utf-8")
    assert "AUDIT_ISSUE_1007" in src
    assert "EVENT_TOTAL_NOT_PRIMARY_STOPPING_POWER" in src
    assert "#1007" in src
