"""Unit tests for the Phase-4 Birks quenching (digitizer/birks.py).

Guards the physics required by the Phase-4 deliverable:
  * proton MIP-like hit barely quenched (<10%),
  * C12 recoil quenched by more than 5x,
  * light output monotone (non-increasing) in dE/dx,
  * edep conserved exactly for kB = 0,
plus the dE/dx lookup sanity (PSTAR/ASTAR anchors) and the pipeline wiring
(per-hit dedx/pdg/ekin keys reach the quench).
"""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.digitizer.birks import (
    KB_CM_PER_MEV,
    KB_G_PER_MEV_CM2,
    MIP_DEDX_MEV_PER_CM,
    POLYSTYRENE_DENSITY_G_CM3,
    birks_quench,
    dedx_polystyrene_mev_per_cm,
)
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline

PDG_P = 2212
PDG_D = 1000010020
PDG_ALPHA = 1000020040
PDG_C12 = 1000060120


def test_kb_constant_is_standard_polystyrene_value():
    assert KB_G_PER_MEV_CM2 == pytest.approx(0.0126)
    assert KB_CM_PER_MEV == pytest.approx(0.0126 / POLYSTYRENE_DENSITY_G_CM3)
    assert KB_CM_PER_MEV == pytest.approx(0.011887, rel=1e-3)


def test_proton_mip_like_hit_barely_quenched():
    # 150 MeV pd-elastic proton: dE/dx ~ 5.6 MeV/cm -> ~6% quench
    edep = 2.0
    light = birks_quench(edep, pdg=PDG_P, ekin_mev=150.0)
    assert light > 0.9 * edep, "MIP-like proton hit must lose <10% of its light"
    # true MIP plateau: <3%
    light_mip = birks_quench(edep, dedx_mev_per_cm=MIP_DEDX_MEV_PER_CM)
    assert light_mip > 0.97 * edep


def test_c12_recoil_quenched_more_than_5x():
    # few-MeV carbon recoil (the MV6 candidate class): dE/dx O(10^3-10^4) MeV/cm
    edep = 3.0
    light = birks_quench(edep, pdg=PDG_C12, ekin_mev=3.0)
    assert light < edep / 5.0, "C12 recoil must be quenched by more than 5x"
    # and with a truth-measured recoil dE/dx too
    light2 = birks_quench(edep, dedx_mev_per_cm=4000.0)
    assert light2 < edep / 5.0


def test_light_monotone_nonincreasing_in_dedx():
    edep = 10.0
    dedx_grid = np.logspace(-1, 4.3, 60)  # 0.1 .. 2e4 MeV/cm
    light = np.array([birks_quench(edep, dedx_mev_per_cm=d) for d in dedx_grid])
    assert np.all(np.diff(light) < 0.0)
    assert np.all(light > 0.0)
    assert np.all(light <= edep)


def test_edep_conserved_for_zero_kb():
    for edep in (0.1, 1.0, 25.0):
        for dedx in (2.2, 100.0, 8000.0):
            assert birks_quench(edep, dedx_mev_per_cm=dedx, k_b_cm_per_mev=0.0) == pytest.approx(edep)
    assert birks_quench(5.0, pdg=PDG_C12, ekin_mev=3.0, k_b_cm_per_mev=0.0) == pytest.approx(5.0)


def test_zero_and_negative_edep():
    assert birks_quench(0.0, dedx_mev_per_cm=100.0) == 0.0
    assert birks_quench(-1.0, dedx_mev_per_cm=100.0) == 0.0


def test_dedx_lookup_pstar_astar_anchors():
    # proton anchors (PSTAR-scaled polystyrene, MeV/cm)
    assert dedx_polystyrene_mev_per_cm(PDG_P, 100.0) == pytest.approx(7.54, rel=0.05)
    assert dedx_polystyrene_mev_per_cm(PDG_P, 10.0) == pytest.approx(47.2, rel=0.05)
    # deuteron = proton at half the energy (same velocity, same charge)
    assert dedx_polystyrene_mev_per_cm(PDG_D, 200.0) == pytest.approx(
        dedx_polystyrene_mev_per_cm(PDG_P, 100.0), rel=0.02
    )
    # alpha at 5 MeV: ASTAR water ~890 MeV cm^2/g -> polystyrene ~920 MeV/cm
    assert dedx_polystyrene_mev_per_cm(PDG_ALPHA, 5.0) == pytest.approx(920.0, rel=0.15)
    # C12 recoil regime: thousands of MeV/cm (order-of-magnitude guard)
    c12 = dedx_polystyrene_mev_per_cm(PDG_C12, 3.0)
    assert 2000.0 < c12 < 30000.0
    # dE/dx ordering at equal kinetic energy: C12 >> alpha >> d > p (10 MeV)
    vals = [dedx_polystyrene_mev_per_cm(p, 10.0) for p in (PDG_P, PDG_D, PDG_ALPHA, PDG_C12)]
    assert vals[0] < vals[1] < vals[2] < vals[3]


def test_dedx_lookup_defaults_and_neutrals():
    # species defaults are used when energy is unknown
    assert dedx_polystyrene_mev_per_cm(PDG_P, None) == pytest.approx(
        dedx_polystyrene_mev_per_cm(PDG_P, 150.0)
    )
    # neutral / electron fall back to the MIP-like value
    assert dedx_polystyrene_mev_per_cm(2112, 10.0) == pytest.approx(MIP_DEDX_MEV_PER_CM)
    assert dedx_polystyrene_mev_per_cm(22, 1.0) == pytest.approx(MIP_DEDX_MEV_PER_CM)
    assert dedx_polystyrene_mev_per_cm(11, 5.0) == pytest.approx(MIP_DEDX_MEV_PER_CM)


def test_legacy_single_argument_call_is_nearly_unquenched():
    # backward compat: birks_quench(edep) uses the MIP default (~2.5% quench)
    edep = 12.0
    light = birks_quench(edep)
    assert 0.95 * edep < light < edep


def test_explicit_dedx_wins_over_species_lookup():
    edep = 4.0
    via_dedx = birks_quench(edep, dedx_mev_per_cm=5000.0, pdg=PDG_P, ekin_mev=150.0)
    via_species = birks_quench(edep, pdg=PDG_P, ekin_mev=150.0)
    assert via_dedx < via_species


def test_pipeline_quenches_c12_hit_far_below_proton_hit():
    pipe = DigitizerPipeline(apply_birks=True, transport_sigma_ns=0.0)
    pipe.electronics.noise_adc_rms = 0.0
    edep = 5.0
    proton_hit = [{"edep_mev": edep, "time_ns": 50.0, "pdg": PDG_P, "ekin_mev": 150.0}]
    c12_hit = [{"edep_mev": edep, "time_ns": 50.0, "pdg": PDG_C12, "ekin_mev": 3.0}]
    amp_p = float(np.max(pipe.run(proton_hit, event_id=1)["adc"]))
    amp_c = float(np.max(pipe.run(c12_hit, event_id=1)["adc"]))
    ped = pipe.electronics.pedestal_adc
    assert (amp_c - ped) < (amp_p - ped) / 5.0
    # and an explicit truth dE/dx through the hit dict is honoured
    c12_dedx_hit = [{"edep_mev": edep, "time_ns": 50.0, "dedx_mev_per_cm": 4000.0}]
    amp_cd = float(np.max(pipe.run(c12_dedx_hit, event_id=1)["adc"]))
    assert (amp_cd - ped) < (amp_p - ped) / 5.0


def test_pipeline_birks_off_leaves_edep_untouched():
    pipe_on = DigitizerPipeline(apply_birks=True, transport_sigma_ns=0.0)
    pipe_off = DigitizerPipeline(apply_birks=False, transport_sigma_ns=0.0)
    for p in (pipe_on, pipe_off):
        p.electronics.noise_adc_rms = 0.0
    hit = [{"edep_mev": 5.0, "time_ns": 50.0, "pdg": PDG_C12, "ekin_mev": 3.0}]
    amp_on = float(np.max(pipe_on.run(hit, event_id=7)["adc"]))
    amp_off = float(np.max(pipe_off.run(hit, event_id=7)["adc"]))
    assert amp_on < amp_off
