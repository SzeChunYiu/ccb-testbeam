from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit.research_sigma_cm_sampler_contract import (
    INTERPOLATION_MODE,
    SUPPORT_MODE,
    audit_sampler,
    inverse_linear_pdf_fraction,
)


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"
MODEL = ROOT / "geant4/src_patch/scattering_source_model_v1.json"
CPP = ROOT / "geant4/src_patch/ScatteringGenerator.cc"
HEADER = ROOT / "geant4/src_patch/ScatteringGenerator.hh"


def _recovered_mass_fraction(a: float, b: float, t: float) -> float:
    return (a * t + 0.5 * (b - a) * t * t) / (0.5 * (a + b))


def test_legacy_sampler_defect_remains_frozen_as_provenance() -> None:
    result = audit_sampler(TABLE)
    legacy = result["legacy_v1"]

    assert result["input"]["sha256"] == (
        "0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc"
    )
    assert legacy["resulting_within_interval_density"] == (
        "piecewise_constant_interval_average"
    )
    assert legacy["probability_below_measured_support"] == pytest.approx(
        0.3394630084684921,
        abs=1e-15,
    )
    assert legacy["probability_above_measured_support"] == pytest.approx(
        0.003869284858232269,
        abs=1e-15,
    )
    assert legacy["probability_outside_measured_support"] == pytest.approx(
        0.3433322933267244,
        abs=1e-15,
    )
    assert legacy["max_cdf_deviation_interval_index"] == 0
    assert legacy["max_cdf_deviation_theta_cm_deg"] == pytest.approx(13.245, abs=1e-12)
    assert legacy["max_cdf_deviation_vs_linear_node_pdf"] == pytest.approx(
        0.08486575211712302,
        abs=1e-15,
    )


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (2.0, 2.0),  # flat
        (1.0, 5.0),  # rising
        (5.0, 1.0),  # falling
        (0.0, 4.0),  # zero left endpoint
        (4.0, 0.0),  # zero right endpoint
    ],
)
@pytest.mark.parametrize("fraction", [0.001, 0.01, 0.1, 0.37, 0.5, 0.9, 0.99, 0.999])
def test_exact_linear_pdf_inverse_closes_off_node_mass(
    a: float,
    b: float,
    fraction: float,
) -> None:
    t = inverse_linear_pdf_fraction(a, b, fraction)
    assert 0.0 < t < 1.0
    assert _recovered_mass_fraction(a, b, t) == pytest.approx(fraction, abs=2e-15)


def test_exact_linear_pdf_inverse_has_fail_closed_domain() -> None:
    assert inverse_linear_pdf_fraction(2.0, 2.0, 0.0) == 0.0
    assert inverse_linear_pdf_fraction(2.0, 2.0, 1.0) == 1.0
    assert inverse_linear_pdf_fraction(2.0, 2.0, 0.37) == pytest.approx(0.37)

    with pytest.raises(ValueError, match="nonnegative"):
        inverse_linear_pdf_fraction(-1.0, 2.0, 0.5)
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        inverse_linear_pdf_fraction(1.0, 2.0, 1.1)
    with pytest.raises(ValueError, match="zero-mass"):
        inverse_linear_pdf_fraction(0.0, 0.0, 0.5)
    with pytest.raises(ValueError, match="finite"):
        inverse_linear_pdf_fraction(float("nan"), 2.0, 0.5)


def test_exact_inverse_is_invariant_to_positive_density_scale() -> None:
    # Only relative interval density matters. Raw quadratic products would
    # overflow at 1e300 and underflow at 1e-300, so these are adversarial units/
    # representation controls rather than alternate physical source models.
    base = inverse_linear_pdf_fraction(1.0, 5.0, 0.37)
    for scale in (1e-300, 1e-200, 1e200, 1e300):
        assert inverse_linear_pdf_fraction(scale, 5.0 * scale, 0.37) == pytest.approx(
            base,
            abs=2e-15,
        )


def test_implemented_reference_is_measured_support_exact_inverse() -> None:
    result = audit_sampler(TABLE)
    reference = result["implemented_reference"]

    assert reference["cross_section_interpolation_mode"] == INTERPOLATION_MODE
    assert reference["cross_section_support_mode"] == SUPPORT_MODE
    assert reference["normalization"] == pytest.approx(1.1977630765144902, abs=2e-15)
    assert reference["support_theta_cm_deg"] == pytest.approx([26.49, 169.78], abs=1e-12)
    assert reference["probability_outside_measured_support"] == 0.0
    assert reference["max_inverse_interval_mass_fraction_error"] <= 5e-15


def test_linear_node_refinement_does_not_change_same_continuous_interval_law() -> None:
    # A linearly rising PDF from 1 to 5 is the same continuous function whether
    # represented by two nodes or with an exact midpoint knot at density 3.
    a, mid, b = 1.0, 3.0, 5.0
    left_mass = 0.5 * (a + mid) * 0.5
    right_mass = 0.5 * (mid + b) * 0.5
    total_mass = 0.5 * (a + b)
    assert left_mass + right_mass == pytest.approx(total_mass)

    for global_fraction in (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99):
        direct_t = inverse_linear_pdf_fraction(a, b, global_fraction)
        target_mass = global_fraction * total_mass
        if target_mass <= left_mass:
            local_fraction = target_mass / left_mass
            refined_t = 0.5 * inverse_linear_pdf_fraction(a, mid, local_fraction)
        else:
            local_fraction = (target_mass - left_mass) / right_mass
            refined_t = 0.5 + 0.5 * inverse_linear_pdf_fraction(mid, b, local_fraction)
        assert refined_t == pytest.approx(direct_t, abs=2e-15)


def test_source_model_sidecar_binds_table_modes_support_and_event_weight() -> None:
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    assert model["cross_section_table"]["sha256"] == (
        "0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc"
    )
    assert model["cross_section_interpolation_mode"] == INTERPOLATION_MODE
    assert model["cross_section_support_mode"] == SUPPORT_MODE
    assert model["support_theta_cm_deg"] == [26.49, 169.78]
    assert model["event_weight_mode"] == "unit_direct_sampling_v1"
    assert model["event_weight"] == 1.0
    assert "NONAUTHORISING" in model["source_model_status"]


def test_tracked_cpp_declares_exact_sampler_contract() -> None:
    cpp = CPP.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")

    assert INTERPOLATION_MODE in cpp
    assert SUPPORT_MODE in cpp
    # Freeze executable inverse mechanics, not an incidental prose sentence.
    assert "targetMass" in cpp
    assert "discriminant" in cpp
    assert "std::sqrt(discriminant)" in cpp
    assert "2.0 * targetMass / denominator" in cpp
    assert "constant-extrapolated outside" not in cpp
    assert "cdfTheta[i-1] + frac * (cdfTheta[i] - cdfTheta[i-1])" not in cpp
    assert "densityScale" in cpp
    assert "cdfPdf" in cpp
    assert "cdfPdf" in header
