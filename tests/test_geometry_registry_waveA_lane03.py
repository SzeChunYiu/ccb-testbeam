"""Wave A Lane 03: geometry hypothesis registry + beam intersection (#987/#989/#991/#992/#999)."""

from __future__ import annotations

import math

import pytest

from ccb_mc_validation.exceptions import ConfigurationError
from ccb_mc_validation.geometry import (
    REGISTRY_VERSION,
    geometry_profile_digest,
    list_profile_ids,
    load_registry_index,
    require_geometry_profile,
    validate_beam_intersection,
)
from ccb_mc_validation.geometry.registry import load_geometry_profile


def test_registry_index_fail_closed_defaults() -> None:
    index = load_registry_index()
    assert index["registry_version"] == REGISTRY_VERSION
    assert index["default_profile_id"] is None
    assert index["fail_closed_when_unset"] is True
    ids = list_profile_ids()
    assert "hyp_mc_single_stave_50cm_2fibre" in ids
    assert "hyp_docs_stave_100cm_1fibre" in ids
    assert "hyp_bstack_spacing_4cm_newer_report" in ids
    assert "hyp_bstack_spacing_2cm_timing_note" in ids
    assert "hyp_deuteron_ke_105MeV_elastic_kinematics" in ids
    assert "hyp_deuteron_like_15p8MeV_bstack_note" in ids


def test_require_geometry_profile_unset_fails_closed() -> None:
    with pytest.raises(ConfigurationError, match="geometry_profile_id is unset"):
        require_geometry_profile({})
    with pytest.raises(ConfigurationError, match="geometry_profile_id is unset"):
        require_geometry_profile(None)
    with pytest.raises(ConfigurationError, match="geometry_profile_id is unset"):
        require_geometry_profile({"geometry": {}})


def test_require_geometry_profile_unknown_fails() -> None:
    with pytest.raises(ConfigurationError, match="unknown geometry_profile_id"):
        require_geometry_profile({"geometry_profile_id": "not_a_real_profile"})


def test_length_hypotheses_disagree_and_are_not_approved() -> None:
    mc = require_geometry_profile(
        {"geometry_profile_id": "hyp_mc_single_stave_50cm_2fibre"}
    )
    docs = require_geometry_profile(
        {"geometry_profile_id": "hyp_docs_stave_100cm_1fibre"}
    )
    assert mc.status == "HYPOTHESIS"
    assert docs.status == "HYPOTHESIS"
    assert mc.claims_authorized is False
    assert docs.claims_authorized is False
    assert mc.parameters["stave_length_cm"] == 50.0
    assert docs.parameters["stave_length_cm"] == 100.0
    assert mc.parameters["n_fibres"] == 2
    assert docs.parameters["n_fibres"] == 1
    assert "hyp_docs_stave_100cm_1fibre" in mc.raw["contradicts"]
    assert "hyp_mc_single_stave_50cm_2fibre" in docs.raw["contradicts"]
    assert geometry_profile_digest(mc) != geometry_profile_digest(docs)


def test_spacing_hypotheses_disagree() -> None:
    s4 = load_geometry_profile("hyp_bstack_spacing_4cm_newer_report")
    s2 = load_geometry_profile("hyp_bstack_spacing_2cm_timing_note")
    assert s4.parameters["analysed_stave_spacing_cm"] == 4.0
    assert s2.parameters["analysed_stave_spacing_cm"] == 2.0
    assert s4.claims_authorized is False
    assert s2.claims_authorized is False


def test_kinematics_estimands_are_distinct() -> None:
    e105 = load_geometry_profile("hyp_deuteron_ke_105MeV_elastic_kinematics")
    e15 = load_geometry_profile("hyp_deuteron_like_15p8MeV_bstack_note")
    assert e105.parameters["estimand"] != e15.parameters["estimand"]
    assert e105.parameters["value_MeV"] == 105.0
    assert e15.parameters["value_MeV"] == 15.8
    assert e105.parameters["range_source_valid_for_deuterons"] is False
    for key in (
        "incident_kinetic",
        "entry_kinetic",
        "deposited",
        "visible_birks",
        "reconstructed_calibrated",
        "residual",
    ):
        assert key in e105.parameters["energy_dictionary_required_types"]
        assert key in e15.parameters["energy_dictionary_required_types"]


def test_beam_central_normal_incidence_passes() -> None:
    profile = load_geometry_profile("hyp_mc_single_stave_50cm_2fibre")
    result = validate_beam_intersection(
        hit_x_cm=0.0, hit_y_cm=0.0, theta_deg=0.0, phi_deg=0.0, profile=profile
    )
    assert result.intersects
    assert result.enters_neg_z_face
    assert result.path_length_cm == pytest.approx(2.0, rel=1e-6)
    assert result.reason == "ok"


@pytest.mark.parametrize(
    "hit_x,hit_y,should_pass",
    [
        (24.9, 0.0, True),
        (25.0, 0.0, True),
        (25.1, 0.0, False),
        (0.0, 2.59, True),
        (0.0, 2.60, False),
    ],
)
def test_beam_hit_edge_cases(hit_x, hit_y, should_pass) -> None:
    profile = load_geometry_profile("hyp_mc_single_stave_50cm_2fibre")
    if should_pass:
        result = validate_beam_intersection(
            hit_x_cm=hit_x, hit_y_cm=hit_y, theta_deg=0.0, phi_deg=0.0, profile=profile
        )
        assert result.intersects
    else:
        with pytest.raises(ConfigurationError, match="outside stave face|misses"):
            validate_beam_intersection(
                hit_x_cm=hit_x,
                hit_y_cm=hit_y,
                theta_deg=0.0,
                phi_deg=0.0,
                profile=profile,
            )


@pytest.mark.parametrize("theta,should_pass", [(89.0, True), (90.0, False), (91.0, False)])
def test_beam_theta_gate(theta, should_pass) -> None:
    profile = load_geometry_profile("hyp_mc_single_stave_50cm_2fibre")
    if should_pass:
        result = validate_beam_intersection(
            hit_x_cm=0.0, hit_y_cm=0.0, theta_deg=theta, phi_deg=0.0, profile=profile
        )
        assert result.intersects
    else:
        with pytest.raises(ConfigurationError, match="theta_deg"):
            validate_beam_intersection(
                hit_x_cm=0.0, hit_y_cm=0.0, theta_deg=theta, phi_deg=0.0, profile=profile
            )


def test_beam_large_angle_can_miss_box() -> None:
    profile = load_geometry_profile("hyp_mc_single_stave_50cm_2fibre")
    # Launch just inside the +x edge with a near-grazing +x tilt so the ray
    # crosses the +x face before the -z entry face (no valid -z entry).
    with pytest.raises(ConfigurationError, match="misses|neg_z|outside"):
        validate_beam_intersection(
            hit_x_cm=24.95,
            hit_y_cm=0.0,
            theta_deg=89.0,
            phi_deg=0.0,
            profile=profile,
        )


def test_allow_miss_accepts_intentional_miss() -> None:
    profile = load_geometry_profile("hyp_mc_single_stave_50cm_2fibre")
    result = validate_beam_intersection(
        hit_x_cm=100.0,
        hit_y_cm=0.0,
        theta_deg=0.0,
        phi_deg=0.0,
        profile=profile,
        allow_miss=True,
    )
    assert result.reason.startswith("allowed_miss:")
    assert result.intersects is False


def test_beam_requires_profile_or_extents() -> None:
    with pytest.raises(ConfigurationError, match="profile or explicit half_extents"):
        validate_beam_intersection(
            hit_x_cm=0.0, hit_y_cm=0.0, theta_deg=0.0, phi_deg=0.0
        )


def test_docs_100cm_profile_extents_for_intersection() -> None:
    profile = load_geometry_profile("hyp_docs_stave_100cm_1fibre")
    # Inside 100 cm face, outside 50 cm face — must pass under docs hypothesis.
    result = validate_beam_intersection(
        hit_x_cm=40.0, hit_y_cm=0.0, theta_deg=0.0, phi_deg=0.0, profile=profile
    )
    assert result.intersects
    assert result.path_length_cm == pytest.approx(2.0, rel=1e-6)


def test_nested_geometry_profile_id_key() -> None:
    p = require_geometry_profile(
        {"geometry": {"profile_id": "hyp_bstack_spacing_4cm_newer_report"}}
    )
    assert p.profile_id == "hyp_bstack_spacing_4cm_newer_report"


def test_digest_stable() -> None:
    p = load_geometry_profile("hyp_mc_single_stave_50cm_2fibre")
    assert geometry_profile_digest(p) == geometry_profile_digest(p)
    assert len(geometry_profile_digest(p)) == 64
