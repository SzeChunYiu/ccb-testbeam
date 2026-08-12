"""Wave B Lane 05: quenching/material/window hypotheses + digitizer domains.

Issues: #1008 #1090 #994 #1080 #1094
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.exceptions import ConfigurationError, DataContractError
from ccb_mc_validation.response.digitizer_domains import (
    VALID_CONTROL,
    DigitizerDomainError,
    preflight_digitizer_config,
)
from ccb_mc_validation.response.observation_window import (
    ObservationSemanticClass,
    classify_quantity_name,
    require_matched_observation_domains,
)
from ccb_mc_validation.response.quantity_dictionary import (
    assert_public_short_labels_compatible,
    load_adc_mev_dictionary,
    require_quantity,
)
from ccb_mc_validation.response.registry import (
    REGISTRY_VERSION,
    list_profile_ids,
    load_registry_index,
    load_response_profile,
    require_fibre_clad_profile,
    require_observation_window_profile,
    require_quenching_profile,
)

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Registry fail-closed (#1008 / #1094 / #1090)
# ---------------------------------------------------------------------------
def test_registry_index_fail_closed_defaults():
    idx = load_registry_index(REPO)
    assert idx["registry_version"] == REGISTRY_VERSION
    assert idx["default_quenching_profile_id"] is None
    assert idx["default_fibre_clad_profile_id"] is None
    assert idx["default_observation_window_profile_id"] is None
    assert idx["fail_closed_when_unset"] is True


def test_unset_quenching_profile_raises():
    with pytest.raises(ConfigurationError, match="quenching_profile_id is unset"):
        require_quenching_profile({}, repo_root=REPO)


def test_unset_fibre_clad_profile_raises():
    with pytest.raises(ConfigurationError, match="fibre_outer_clad_profile_id is unset"):
        require_fibre_clad_profile({}, repo_root=REPO)


def test_unset_observation_window_profile_raises():
    with pytest.raises(ConfigurationError, match="observation_window_profile_id is unset"):
        require_observation_window_profile({}, repo_root=REPO)


def test_birks_nominal_is_hypothesis_not_authorized():
    p = require_quenching_profile(
        {"quenching_profile_id": "hyp_geant4_birks_kb_0p126_mm_per_MeV"},
        repo_root=REPO,
    )
    assert p.status == "HYPOTHESIS"
    assert p.claims_authorized is False
    assert p.parameters["model_form"] == "birks"
    assert p.parameters["kB_mm_per_MeV"] == pytest.approx(0.126)


def test_chou_and_literature_profiles_are_hypotheses():
    for pid in (
        "hyp_chou_like_second_order_placeholder",
        "hyp_literature_poschl2021_model_ensemble",
        "hyp_birks_kb_scan_grid_mm_per_MeV",
    ):
        p = load_response_profile(pid, repo_root=REPO)
        assert p.kind == "quenching"
        assert p.status == "HYPOTHESIS"
        assert p.claims_authorized is False


def test_fibre_clad_pmma_proxy_vs_fluorinated_contradiction():
    a = require_fibre_clad_profile(
        {"fibre_outer_clad_profile_id": "hyp_fibre_outer_clad_pmma_density_1p19_proxy"},
        repo_root=REPO,
    )
    b = require_fibre_clad_profile(
        {
            "fibre_outer_clad_profile_id": "hyp_fibre_outer_clad_fluorinated_polymer_1p43"
        },
        repo_root=REPO,
    )
    assert a.parameters["density_g_per_cm3"] == pytest.approx(1.19)
    assert b.parameters["density_g_per_cm3"] == pytest.approx(1.43)
    assert a.parameters["optical_rindex"] == b.parameters["optical_rindex"]
    assert a.claims_authorized is False and b.claims_authorized is False
    assert "hyp_fibre_outer_clad_fluorinated_polymer_1p43" in a.raw["contradicts"]


def test_observation_window_profiles_distinct_semantics():
    full = require_observation_window_profile(
        {"observation_window_profile_id": "hyp_obs_window_full_transport"},
        repo_root=REPO,
    )
    acq = require_observation_window_profile(
        {
            "observation_window_profile_id": "hyp_obs_window_sipm_core_minus20_to_250_ns"
        },
        repo_root=REPO,
    )
    assert full.parameters["semantic_class"] == "FULL_TRANSPORT"
    assert acq.parameters["semantic_class"] == "ACQUISITION_WINDOW"
    assert acq.parameters["window_start_ns"] == pytest.approx(-20.0)
    assert acq.parameters["window_end_ns"] == pytest.approx(250.0)
    assert acq.parameters["hardware_binding"] == "REPRESENTATIVE_ASSUMED"


def test_wrong_kind_rejected():
    with pytest.raises(ConfigurationError, match="expected .quenching"):
        require_quenching_profile(
            {
                "quenching_profile_id": "hyp_obs_window_full_transport"
            },
            repo_root=REPO,
        )


def test_list_profiles_by_kind():
    q = list_profile_ids(REPO, kind="quenching")
    assert "hyp_geant4_birks_kb_0p126_mm_per_MeV" in q
    assert "hyp_fibre_outer_clad_pmma_density_1p19_proxy" not in q


# ---------------------------------------------------------------------------
# Observation domain matching (#1090)
# ---------------------------------------------------------------------------
def test_classify_full_vs_acquisition():
    assert classify_quantity_name("edep_scint_MeV") == ObservationSemanticClass.FULL_TRANSPORT
    assert (
        classify_quantity_name("full_transport_edep_MeV")
        == ObservationSemanticClass.FULL_TRANSPORT
    )
    assert (
        classify_quantity_name("daq_window_edep_MeV")
        == ObservationSemanticClass.ACQUISITION_WINDOW
    )
    assert (
        classify_quantity_name("production_adc")
        == ObservationSemanticClass.ACQUISITION_WINDOW
    )


def test_refuse_unmatched_adc_over_full_edep():
    with pytest.raises(DataContractError, match="unmatched observation domains"):
        require_matched_observation_domains("production_adc", "edep_scint_MeV")


def test_allow_explicit_cross_domain_opt_in():
    require_matched_observation_domains(
        "production_adc",
        "edep_scint_MeV",
        allow_explicit_cross_domain=True,
    )


def test_matched_daq_window_ratio_ok():
    require_matched_observation_domains("daq_window_adc", "daq_window_edep_MeV")


def test_249_vs_251_ns_window_membership_contract():
    """Known-answer: only t<=250 ns is inside representative acquisition window."""
    acq = load_response_profile(
        "hyp_obs_window_sipm_core_minus20_to_250_ns", repo_root=REPO
    )
    start = float(acq.parameters["window_start_ns"])
    end = float(acq.parameters["window_end_ns"])

    def in_window(t: float) -> bool:
        return start <= t <= end

    assert in_window(249.0) is True
    assert in_window(251.0) is False
    assert in_window(-20.0) is True
    assert in_window(-20.1) is False


# ---------------------------------------------------------------------------
# ADC/MeV quantity dictionary (#994)
# ---------------------------------------------------------------------------
def test_quantity_dictionary_loads_and_versions():
    table = load_adc_mev_dictionary(REPO)
    assert "mc_digitizer_peak_adc_per_visible_MeV_nominal" in table
    assert "data_mc_median_match_peak_adc_per_truth_edep_MeV_proxy_cl013" in table
    q = require_quantity(
        "data_mc_median_match_peak_adc_per_truth_edep_MeV_proxy_cl013",
        repo_root=REPO,
    )
    assert q.nominal_value == pytest.approx(92.0)
    assert q.claims_authorized is False
    assert q.raw["uncertainty_envelope_relative"] == pytest.approx(0.30)


def test_unset_quantity_id_fails_closed():
    with pytest.raises(ConfigurationError, match="quantity_id is unset"):
        require_quantity("", repo_root=REPO)


def test_compatible_short_labels_same_truth_type_ok():
    # Single id is always fine.
    assert_public_short_labels_compatible(
        ["mc_digitizer_peak_adc_per_visible_MeV_nominal"],
        repo_root=REPO,
    )


def test_incompatible_shared_short_label_detected(tmp_path, monkeypatch):
    # Simulate two distinct truth types forced onto one short_label.
    table = load_adc_mev_dictionary(REPO)
    a = table["mc_digitizer_peak_adc_per_visible_MeV_nominal"]
    b = table["data_mc_median_match_peak_adc_per_truth_edep_MeV_proxy_cl013"]
    assert a.short_label != b.short_label
    # Compatibility helper compares truth_type_key within a shared label;
    # construct a synthetic collision via monkeypatch of loaded entries.
    from ccb_mc_validation.response import quantity_dictionary as qd

    collided = {
        a.quantity_id: a,
        b.quantity_id: type(b)(
            quantity_id=b.quantity_id,
            short_label=a.short_label,  # forced collision
            domain=b.domain,
            input_energy_type=b.input_energy_type,
            output_adc_definition=b.output_adc_definition,
            estimator=b.estimator,
            nominal_value=b.nominal_value,
            unit=b.unit,
            claims_authorized=False,
            raw=b.raw,
        ),
    }

    monkeypatch.setattr(qd, "load_adc_mev_dictionary", lambda repo_root=None: collided)
    with pytest.raises(DataContractError, match="shared by incompatible truth"):
        assert_public_short_labels_compatible(
            [a.quantity_id, b.quantity_id], repo_root=REPO
        )


# ---------------------------------------------------------------------------
# Digitizer domain preflight (#1080)
# ---------------------------------------------------------------------------
def test_preflight_accepts_production_digitizer_yaml_defaults():
    cfg = {
        "n_samples": 18,
        "sample_spacing_ns": 10.0,
        "tau_rise_ns": 2.0,
        "tau_decay_ns": 35.0,
        "transport_sigma_ns": 0.5,
        "gain_adc_per_mev": 120.0,
        "noise_adc_rms": 8.0,
        "pedestal_adc": 300.0,
        "adc_ceiling": 7000,
        "apply_birks": False,
    }
    resolved = preflight_digitizer_config(cfg)
    assert resolved["status"] == "PREFLIGHT_OK"
    pipe = DigitizerPipeline.from_config(cfg)
    out = pipe.run([{"edep_mev": 1.0, "time_ns": 5.0}], event_id=1)
    assert out["adc"].shape == (18,)


@pytest.mark.parametrize("n_samples", [0, -1])
def test_preflight_rejects_nonpositive_n_samples(n_samples):
    with pytest.raises(DigitizerDomainError, match="n_samples"):
        DigitizerPipeline.from_config({"n_samples": n_samples})


@pytest.mark.parametrize("spacing", [0.0, -1.0])
def test_preflight_rejects_nonpositive_sample_spacing(spacing):
    with pytest.raises(DigitizerDomainError, match="sample_spacing_ns"):
        DigitizerPipeline.from_config({"sample_spacing_ns": spacing})


def test_preflight_rejects_negative_transport_sigma():
    with pytest.raises(DigitizerDomainError, match="transport_sigma_ns"):
        DigitizerPipeline.from_config({"transport_sigma_ns": -0.1})


def test_preflight_accepts_zero_transport_as_control():
    resolved = preflight_digitizer_config({"transport_sigma_ns": 0.0})
    assert resolved["classification"]["transport_sigma_ns"] == VALID_CONTROL


def test_preflight_accepts_zero_noise_as_control():
    resolved = preflight_digitizer_config({"noise_adc_rms": 0.0})
    assert resolved["classification"]["electronics.noise_adc_rms"] == VALID_CONTROL


@pytest.mark.parametrize(
    "field,value",
    [
        ("gain_adc_per_mev", math.nan),
        ("gain_adc_per_mev", math.inf),
        ("sample_spacing_ns", math.nan),
        ("noise_adc_rms", -1.0),
        ("adc_bits", 3.5),
        ("adc_bits", "14"),
        ("n_samples", "18"),
    ],
)
def test_preflight_rejects_nonfinite_and_typos(field, value):
    with pytest.raises(DigitizerDomainError):
        DigitizerPipeline.from_config({field: value})


def test_invalid_config_does_not_emit_waveform():
    with pytest.raises(DigitizerDomainError):
        pipe = DigitizerPipeline.from_config({"n_samples": 0})
        pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=0)


def test_electronics_quantize_still_rejects_nonfinite():
    cfg = ElectronicsConfig()
    with pytest.raises(ValueError, match="non-finite"):
        from ccb_mc_validation.digitizer.electronics import quantize_adc

        quantize_adc(np.array([1.0, np.nan]), cfg)
