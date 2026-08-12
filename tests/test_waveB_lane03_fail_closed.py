"""Wave B Lane 03 fail-closed contracts (#1006/#1046/#985/#1076/#1100)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.exceptions import ConfigurationError
from ccb_mc_validation.physics import (
    REGISTRY_VERSION,
    list_physics_list_ids,
    physics_list_digest,
    require_physics_list,
)
from ccb_mc_validation.physics.registry import load_registry_index
from ccb_mc_validation.response_surface import summarize_nuisance_sweep
from ccb_mc_validation.strict_bool import PARSER_VERSION, parse_strict_bool
from ccb_mc_validation.truth.entering_species import (
    accumulate_entering_species,
    entering_species_report,
)
from ccb_mc_validation.waveform_ratios import (
    AREA_EPS,
    assert_no_epsilon_projection,
    late_and_peak_ratios,
)


# ---------------------------------------------------------------------------
# #1006 physics list registry
# ---------------------------------------------------------------------------
def test_physics_registry_fail_closed_defaults():
    index = load_registry_index()
    assert index["registry_version"] == REGISTRY_VERSION
    assert index["default_profile_id"] is None
    assert index["fail_closed_when_unset"] is True
    ids = list_physics_list_ids()
    assert "hyp_qgsp_bic_legacy_hardcoded" in ids
    assert "hyp_qgsp_inclxx_candidate" in ids


def test_require_physics_list_unset_fails_closed():
    with pytest.raises(ConfigurationError, match="physics_list_profile_id is unset"):
        require_physics_list({})
    with pytest.raises(ConfigurationError, match="physics_list_profile_id is unset"):
        require_physics_list(None)
    with pytest.raises(ConfigurationError, match="physics_list_profile_id is unset"):
        require_physics_list({"physics": {}})


def test_require_physics_list_unknown_fails():
    with pytest.raises(ConfigurationError, match="unknown physics_list_profile_id"):
        require_physics_list({"physics_list_profile_id": "not_a_real_list"})


def test_physics_hypotheses_not_authorized_and_disagree():
    bic = require_physics_list(
        {"physics_list_profile_id": "hyp_qgsp_bic_legacy_hardcoded"}
    )
    incl = require_physics_list(
        {"physics_list_profile_id": "hyp_qgsp_inclxx_candidate"}
    )
    assert bic.status == "HYPOTHESIS"
    assert incl.status == "HYPOTHESIS"
    assert bic.claims_authorized is False
    assert incl.claims_authorized is False
    assert bic.geant4_reference_list == "QGSP_BIC"
    assert incl.geant4_reference_list == "QGSP_INCLXX"
    assert physics_list_digest(bic) != physics_list_digest(incl)


# ---------------------------------------------------------------------------
# #1076 strict bool
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("false", False),
        ("FALSE", False),
        ("yes", True),
        ("no", False),
        ("on", True),
        ("off", False),
        ("1", True),
        ("0", False),
    ],
)
def test_parse_strict_bool_accepted(value, expected):
    assert parse_strict_bool(value, field="apply_birks") is expected


@pytest.mark.parametrize("value", ["flase", "maybe", "", 2, -1, 0.5, [], {}])
def test_parse_strict_bool_rejects_ambiguous(value):
    with pytest.raises(ConfigurationError):
        parse_strict_bool(value, field="apply_birks")


def test_digitizer_from_config_string_false_disables_birks():
    # Regression: bool("false") was True before #1076.
    pipe = DigitizerPipeline.from_config({"apply_birks": "false"})
    assert pipe.apply_birks is False
    prov = pipe.bool_provenance()["apply_birks"]
    assert prov["effective"] is False
    assert prov["requested"] == "false"
    assert prov["parser_version"] == PARSER_VERSION


def test_digitizer_from_config_string_true_enables_birks():
    pipe = DigitizerPipeline.from_config({
        "apply_birks": "true",
        "birks_kB_cm_per_MeV": 0.008,
    })
    assert pipe.apply_birks is True


def test_digitizer_from_config_typo_fails_closed():
    with pytest.raises(ConfigurationError, match="apply_birks"):
        DigitizerPipeline.from_config({"apply_birks": "flase"})


def test_digitizer_from_config_native_bool():
    assert DigitizerPipeline.from_config({"apply_birks": False}).apply_birks is False
    assert DigitizerPipeline.from_config({
        "apply_birks": True,
        "birks_kB_cm_per_MeV": 0.008,
    }).apply_birks is True
    assert DigitizerPipeline.from_config({}).apply_birks is False


# ---------------------------------------------------------------------------
# #1046 entering species unit
# ---------------------------------------------------------------------------
def test_entering_species_dedupes_multi_step_track():
    # One physical deuteron with 5 first-layer step records must count once.
    pdg = np.array([1000010020] * 5 + [2212] * 2)
    tid = np.array([7] * 5 + [8, 8])
    edep = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 0.5, 0.5])
    mask = np.ones(len(pdg), dtype=bool)
    acc = accumulate_entering_species(
        pdg=pdg, track_id=tid, edep=edep, first_layer_mask=mask, event_weight=1.0
    )
    assert acc["record_counts"]["d"] == 5.0
    assert acc["record_counts"]["p"] == 2.0
    assert acc["track_counts"]["d"] == 1.0
    assert acc["track_counts"]["p"] == 1.0
    report = entering_species_report(
        record_counts=acc["record_counts"],
        track_counts=acc["track_counts"],
        event_presence=acc["event_presence"],
        edep_weights=acc["edep_weights"],
    )
    # H1 would say 5/7 deuterons; H2 says 1/2.
    assert report["first_layer_record_fraction"]["fractions"]["d"] == pytest.approx(
        5 / 7, abs=1e-6
    )
    assert report["enter_pid_fraction"]["fractions"]["d"] == pytest.approx(0.5)
    assert report["enter_pid_fraction"]["statistical_unit"] == "unique_truth_track"


def test_entering_species_record_duplication_invariant_for_tracks():
    pdg = np.array([2212, 2212, 1000010020])
    tid = np.array([1, 1, 2])
    edep = np.ones(3)
    base = accumulate_entering_species(
        pdg=pdg, track_id=tid, edep=edep, first_layer_mask=np.ones(3, dtype=bool)
    )
    # Duplicate every proton record artificially
    pdg2 = np.array([2212, 2212, 2212, 2212, 1000010020])
    tid2 = np.array([1, 1, 1, 1, 2])
    edep2 = np.ones(5)
    dup = accumulate_entering_species(
        pdg=pdg2, track_id=tid2, edep=edep2, first_layer_mask=np.ones(5, dtype=bool)
    )
    assert base["track_counts"] == dup["track_counts"]
    assert base["record_counts"] != dup["record_counts"]


# ---------------------------------------------------------------------------
# #985 response surface
# ---------------------------------------------------------------------------
def test_response_surface_recovers_linear_local_slope():
    xs = np.linspace(1.0, 5.0, 5)
    ys = 2.0 * xs + 3.0
    s = summarize_nuisance_sweep(xs, ys)
    assert s["global_linear_misleading"] is False
    assert s["recommended_slope"] == pytest.approx(2.0, abs=1e-9)


def test_response_surface_flags_saturation_and_excludes_from_slope():
    xs = np.array([1.0, 2.0, 3.0, 4.0])
    ys = np.array([10.0, 20.0, 3895.0, 3895.0])  # clipped plateau
    clips = np.array([0.0, 0.0, 0.9, 0.95])
    s = summarize_nuisance_sweep(xs, ys, frac_clipped=clips)
    assert s["global_linear_misleading"] is True
    assert "saturated_points_present" in s["misleading_reasons"]
    assert s["n_saturated_points"] == 2
    # Local slope on unsaturated bracket near nominal should be ~10.
    assert s["recommended_slope"] == pytest.approx(10.0, abs=1e-9)


def test_response_surface_flags_quadratic_curvature():
    xs = np.linspace(0.0, 4.0, 9)
    ys = xs**2
    s = summarize_nuisance_sweep(xs, ys)
    assert s["global_linear_misleading"] is True
    assert any("quadratic" in r for r in s["misleading_reasons"])


def test_response_surface_flags_non_monotonic():
    xs = np.array([1.0, 2.0, 3.0, 4.0])
    ys = np.array([1.0, 3.0, 2.0, 4.0])
    s = summarize_nuisance_sweep(xs, ys)
    assert s["global_linear_misleading"] is True
    assert "non_monotonic_unsaturated_response" in s["misleading_reasons"]


# ---------------------------------------------------------------------------
# #1100 waveform ratios
# ---------------------------------------------------------------------------
def test_waveform_ratio_positive_pulse_finite():
    # Monotone decaying positive pulse after peak at sample 0.
    w = np.array([[1.0, 0.8, 0.5, 0.3] + [0.1] * 14], dtype=float)
    amp = np.array([1.0])
    r = late_and_peak_ratios(w, late_start=12, normalize_by=amp)
    assert r["denominator_valid_signed"][0]
    assert math.isfinite(r["late_signed_fraction_v1"][0])
    assert 0.0 <= r["late_signed_fraction_v1"][0] <= 1.0


def test_waveform_ratio_zero_area_is_nan_not_epsilon_artifact():
    w = np.zeros((1, 18), dtype=float)
    r = late_and_peak_ratios(w, late_start=12)
    assert not r["denominator_valid_signed"][0]
    assert math.isnan(r["late_signed_fraction_v1"][0])
    assert math.isnan(r["peak_to_area_signed_v1"][0])
    assert_no_epsilon_projection(r["area_signed"], r["late_signed_fraction_v1"])


def test_waveform_ratio_negative_area_is_nan_not_million():
    # Positive early samples cancelled by negative late undershoot → small/neg area.
    w = np.array([[1.0] * 6 + [-1.0] * 12], dtype=float)
    r = late_and_peak_ratios(w, late_start=12)
    # area_signed = 6 - 12 = -6; valid signed fraction is finite and negative.
    # Construct near-zero negative via tiny residual:
    w2 = np.array([[1.0] * 9 + [-1.0] * 9], dtype=float)  # area ~ 0
    r2 = late_and_peak_ratios(w2, late_start=12)
    assert abs(r2["area_signed"][0]) <= AREA_EPS * max(1.0, abs(r2["area_signed"][0]) + 1)
    # For exact cancel, should be invalid / NaN
    assert math.isnan(r2["late_signed_fraction_v1"][0]) or abs(
        r2["late_signed_fraction_v1"][0]
    ) < 1e3
    assert_no_epsilon_projection(r2["area_signed"], r2["late_signed_fraction_v1"])
    # Explicit tiny negative area must not become O(1e6)
    w3 = np.full((1, 18), 1e-9)
    w3[0, 0] = -1.8e-8  # sum slightly negative tiny
    r3 = late_and_peak_ratios(w3, late_start=12)
    if not r3["denominator_valid_signed"][0]:
        assert math.isnan(r3["late_signed_fraction_v1"][0])
    assert_no_epsilon_projection(r3["area_signed"], r3["late_signed_fraction_v1"])


def test_waveform_ratio_undershoot_does_not_fabricate_million():
    # Equal late morphology but negative total area from undershoot.
    w = np.zeros((1, 18))
    w[0, :5] = 0.2
    w[0, 12:] = -0.5  # strong undershoot → negative area
    r = late_and_peak_ratios(w, late_start=12)
    val = r["late_signed_fraction_v1"][0]
    if r["denominator_valid_signed"][0]:
        assert abs(val) < 1e3
    else:
        assert math.isnan(val)
    assert_no_epsilon_projection(r["area_signed"], np.array([val]))
