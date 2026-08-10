from __future__ import annotations

from pathlib import Path

import pytest

from tools.audit.research_sigma_cm_interpolation_sensitivity import audit_interpolation

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"


@pytest.fixture(scope="module")
def audit() -> dict[str, object]:
    return audit_interpolation(TABLE)


def test_interpolation_sensitivity_binds_exact_source(audit: dict[str, object]) -> None:
    assert audit["input"]["sha256"] == (
        "0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc"
    )
    assert audit["input"]["rows"] == 28
    assert audit["input"]["support_theta_cm_deg"] == pytest.approx([26.49, 169.78])


def test_interpolation_order_changes_normalized_source_shape(
    audit: dict[str, object],
) -> None:
    comparison = audit["comparison"]
    assert comparison["max_abs_normalized_cdf_difference"] == pytest.approx(
        0.0010129801982659559, abs=2e-15
    )
    assert comparison["theta_cm_deg_at_max_abs_cdf_difference"] == pytest.approx(
        43.94458149140975, abs=1e-11
    )
    assert comparison["alternative_minus_current_mean_theta_cm_deg"] == pytest.approx(
        -0.024267831224125052, abs=1e-12
    )


def test_alternative_interpolation_is_invariant_to_redundant_sigma_knots(
    audit: dict[str, object],
) -> None:
    refinement = audit["representation_refinement_control"]
    assert refinement["alternative_mode_max_abs_cdf_change"] <= 2e-15
    assert refinement["current_mode_max_abs_cdf_change"] == pytest.approx(
        0.000768558730840585, abs=2e-15
    )
    assert refinement["current_mode_max_abs_cdf_change"] > 500 * refinement[
        "alternative_mode_max_abs_cdf_change"
    ]


def test_sensitivity_result_remains_nonauthorising(audit: dict[str, object]) -> None:
    boundary = audit["scientific_boundary"].lower()
    assert "central-value source sensitivity" in boundary
    assert "no off-support extrapolation" in boundary
    assert "detector-level claim" in boundary
