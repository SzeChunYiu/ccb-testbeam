"""Lane 04 Wave B fail-closed contracts: #1007 #1079 #986 #1077 #880."""

from __future__ import annotations

import pytest

from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.digitizer.stage_graph import resolve_stage_graph
from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.provenance.canonical_config_digests import (
    geometry_config_sha256,
    physics_config_sha256,
)
from ccb_mc_validation.truth.stopping_power_estimators import (
    StoppingPowerEstimatorError,
    event_calorimetric_ratio_mev_per_mm,
    primary_stopping_ratio_mev_per_mm,
)
from ccb_mc_validation.truth.weight_adapter import (
    ADAPTER_SCALAR_EVENT,
    adapt_raw_primary_weight,
)


def _geom(**overrides):
    base = dict(
        stave_half_x_mm=250.0,
        stave_half_y_mm=25.9,
        stave_half_z_mm=10.0,
        hole_radius_mm=0.7,
        fibre_radius_mm=0.5,
        fibre_half_x_mm=250.0,
        fibre_sep_mm=10.0,
        fibre_core_radius_mm=0.47,
        fibre_inner_clad_radius_mm=0.485,
        fibre_outer_radius_mm=0.5,
        coating_thickness_mm=0.25,
        sensor_thickness_mm=0.1,
        far_end_mode="instrumented",
    )
    base.update(overrides)
    return geometry_config_sha256(**base)


def test_986_far_end_mode_changes_geometry_digest_not_birks():
    a = _geom(far_end_mode="instrumented")
    b = _geom(far_end_mode="mirror")
    assert a != b
    # Birks is not a geometry field — physics digest absorbs it.
    p0 = physics_config_sha256(
        birks_kB_mm_per_MeV=0.126,
        production_cut_mm=0.1,
        optical_interface_model="UNKNOWN_EXTERNAL",
    )
    p1 = physics_config_sha256(
        birks_kB_mm_per_MeV=0.0,
        production_cut_mm=0.1,
        optical_interface_model="UNKNOWN_EXTERNAL",
    )
    assert p0 != p1
    assert _geom() == _geom()  # stable


def test_986_coating_and_sensor_thickness_change_geometry_digest():
    assert _geom(coating_thickness_mm=0.25) != _geom(coating_thickness_mm=0.50)
    assert _geom(sensor_thickness_mm=0.10) != _geom(sensor_thickness_mm=0.20)


def test_1079_pipeline_honors_requested_kb_not_helper_default():
    # Geant4-like 0.126 mm/MeV = 0.0126 cm/MeV vs helper default 0.008 cm/MeV.
    # High dE/dx separates the two kB values above ADC quantisation.
    hits = [{"edep_mev": 50.0, "time_ns": 0.0, "step_length_cm": 0.1}]  # 500 MeV/cm
    common = dict(
        apply_birks=True,
        transport_sigma_ns=0.0,
        electronics=ElectronicsConfig(
            noise_adc_rms=0.0, gain_adc_per_mev=100.0, pedestal_adc=0.0
        ),
    )
    a = DigitizerPipeline(birks_kB_cm_per_MeV=0.008, **common).run(hits, event_id=1)
    b = DigitizerPipeline(birks_kB_cm_per_MeV=0.0126, **common).run(hits, event_id=1)
    # Effective quenching scale is the configured cm/MeV value (#1079).
    assert a["birks_kB_cm_per_MeV_effective"] == pytest.approx(0.008)
    assert b["birks_kB_cm_per_MeV_effective"] == pytest.approx(0.0126)
    assert a["digitizer_config_sha256"] != b["digitizer_config_sha256"]
    assert int(a["adc"].sum()) != int(b["adc"].sum())


def test_1079_from_config_rejects_dual_unit_keys():
    with pytest.raises(ValueError, match="both birks_kB_cm_per_MeV and"):
        DigitizerPipeline.from_config(
            {
                "apply_birks": True,
                "birks_kB_mm_per_MeV": 0.126,
                "birks_kB_cm_per_MeV": 0.0126,
                "stages": ["birks", "scintillation", "transport", "sampling"],
            }
        )


def test_1077_omitting_sampling_fails_closed_no_hidden_fallback():
    with pytest.raises(ValueError, match="sampling"):
        resolve_stage_graph(["birks", "scintillation", "transport"])


def test_1077_electronics_stage_rejected_as_non_toggle():
    with pytest.raises(ValueError, match="deprecated"):
        resolve_stage_graph(
            ["birks", "scintillation", "transport", "sampling", "electronics"]
        )


def test_1077_resolved_graph_records_mandatory_daq_observation():
    g = resolve_stage_graph(["birks", "scintillation", "transport", "sampling"])
    assert g.resolved_stages[-1] == "daq_observation"
    assert "daq_observation" in g.mandatory_insertions
    out = DigitizerPipeline(stages=list(g.requested_stages)).run(
        [{"edep_mev": 1.0, "time_ns": 0.0}], event_id=7
    )
    assert out["stage_graph"]["graph_sha256"] == g.graph_sha256


def test_1077_duplicates_and_reorder_fail():
    with pytest.raises(ValueError, match="duplicate"):
        resolve_stage_graph(["sampling", "sampling"])
    with pytest.raises(ValueError, match="order"):
        resolve_stage_graph(["sampling", "transport"])


def test_1007_primary_estimator_rejects_legacy_and_secondary():
    with pytest.raises(StoppingPowerEstimatorError, match="primary_"):
        primary_stopping_ratio_mev_per_mm(
            {"edep_scint_raw_MeV": 1.0, "track_len_scint_mm": 1.0}
        )
    with pytest.raises(StoppingPowerEstimatorError, match="secondary"):
        primary_stopping_ratio_mev_per_mm(
            {
                "primary_edep_scint_raw_MeV": 1.0,
                "primary_track_len_scint_mm": 1.0,
                "secondary_scint_activity": 1,
            }
        )
    ok = primary_stopping_ratio_mev_per_mm(
        {
            "primary_edep_scint_raw_MeV": 2.0,
            "primary_track_len_scint_mm": 4.0,
            "secondary_scint_activity": 0,
        }
    )
    assert ok["authorising"] is True
    assert ok["ratio_MeV_per_mm"] == pytest.approx(0.5)
    diag = event_calorimetric_ratio_mev_per_mm(
        {"edep_scint_raw_MeV": 2.0, "track_len_scint_mm": 4.0}
    )
    assert diag["authorising"] is False


def test_880_rejects_arbitrary_weights0_without_measure_mode():
    with pytest.raises(DataContractError, match="generator_measure_mode"):
        adapt_raw_primary_weight([1.0, 2.0], generator_measure_mode=None)


def test_880_scalar_and_replicated_and_unit_adapters():
    s = adapt_raw_primary_weight(
        [3.0], generator_measure_mode="scalar_event_weight"
    )
    assert s["weight_adapter_id"] == ADAPTER_SCALAR_EVENT
    assert s["event_weight"] == pytest.approx(3.0)

    r = adapt_raw_primary_weight(
        [2.0, 2.0, 2.0], generator_measure_mode="common_replicated_primary"
    )
    assert r["event_weight"] == pytest.approx(2.0)
    with pytest.raises(DataContractError, match="identical"):
        adapt_raw_primary_weight(
            [2.0, 3.0], generator_measure_mode="common_replicated_primary"
        )

    u = adapt_raw_primary_weight(
        [1.0, 1.0], generator_measure_mode="direct_sampling_unit_weight"
    )
    assert u["event_weight"] == pytest.approx(1.0)
    with pytest.raises(DataContractError, match="non-unit"):
        adapt_raw_primary_weight(
            [1.0, 1.1], generator_measure_mode="direct_sampling_unit_weight"
        )
