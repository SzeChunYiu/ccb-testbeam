from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from tools.audit.research_sigma_cm_source_uncertainty import (
    POINT_TO_POINT_FRACTION,
    audit_source_uncertainty,
    ratio_box_extreme,
)


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"
SOURCE = ROOT / "geant4/src_patch/sigma_pd_cm_190.source.json"


@pytest.fixture(scope="module")
def source_audit() -> dict[str, object]:
    # The 10,001-point box scan is intentionally nontrivial; compute it once for
    # this module so independent semantic assertions do not multiply CI cost.
    return audit_source_uncertainty(TABLE)


def test_source_uncertainty_audit_binds_exact_table_and_nominal_model(
    source_audit: dict[str, object],
) -> None:
    result = source_audit

    assert result["input"]["sha256"] == (
        "0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc"
    )
    assert result["input"]["rows"] == 28
    assert result["input"]["support_theta_cm_deg"] == pytest.approx([26.49, 169.78])
    assert result["nominal_source_model"]["normalization"] == pytest.approx(
        1.19776307651449,
        abs=2e-15,
    )
    assert result["nominal_source_model"]["mean_theta_cm_deg"] == pytest.approx(
        56.78396200051643,
        abs=1e-12,
    )


def test_common_source_normalization_cancels_from_normalized_shape(
    source_audit: dict[str, object],
) -> None:
    control = source_audit["deterministic_sensitivity"]["common_scale_bound_control"]

    assert control["relative_scale"] == 1.045
    assert control["max_abs_normalized_cdf_delta"] <= 1e-15


def test_three_percent_nodewise_box_is_explicitly_nonprobabilistic(
    source_audit: dict[str, object],
) -> None:
    box = source_audit["deterministic_sensitivity"]["nodewise_relative_box_3pct_sensitivity_v1"]

    assert POINT_TO_POINT_FRACTION == 0.03
    assert box["status"] == "NONPROBABILISTIC_ENVELOPE"
    assert box["max_cdf_upward_excursion"] == pytest.approx(
        0.01430729974634637,
        abs=2e-15,
    )
    assert box["max_cdf_downward_excursion"] == pytest.approx(
        0.014380572923809676,
        abs=2e-15,
    )
    assert box["theta_cm_deg_at_max_upward_excursion"] == pytest.approx(46.951812)
    assert box["theta_cm_deg_at_max_downward_excursion"] == pytest.approx(46.951812)
    assert box["min_mean_theta_cm_deg"] == pytest.approx(56.050251002153615, abs=1e-12)
    assert box["max_mean_theta_cm_deg"] == pytest.approx(57.5322672970398, abs=1e-12)


def test_systematic_correlation_structure_is_not_identified_by_one_percentage(
    source_audit: dict[str, object],
) -> None:
    box = source_audit["deterministic_sensitivity"]["nodewise_relative_box_3pct_sensitivity_v1"]
    alternating = source_audit["deterministic_sensitivity"]["alternating_3pct_controls"]

    assert alternating["plus_minus_max_abs_cdf_delta"] == pytest.approx(
        0.0014567989868344983,
        abs=2e-15,
    )
    assert alternating["minus_plus_max_abs_cdf_delta"] == pytest.approx(
        0.0014569781233605278,
        abs=2e-15,
    )
    assert alternating["plus_minus_max_abs_cdf_delta"] < box["max_cdf_upward_excursion"]
    assert alternating["minus_plus_max_abs_cdf_delta"] < box["max_cdf_downward_excursion"]


def test_diagonal_statistical_reference_is_conditional_not_systematic_covariance(
    source_audit: dict[str, object],
) -> None:
    statistical = source_audit["conditional_diagonal_statistical_reference"]

    assert statistical["status"] == "DELTA_METHOD_CONDITIONAL_ON_INDEPENDENT_ROW_STATISTICS"
    assert statistical["max_pointwise_cdf_standard_uncertainty"] == pytest.approx(
        0.0004453566889758832,
        abs=2e-15,
    )
    assert statistical["theta_cm_deg_at_max_pointwise_cdf_standard_uncertainty"] == pytest.approx(
        49.488045
    )
    assert statistical["mean_theta_cm_standard_uncertainty_deg"] == pytest.approx(
        0.02252797870713097,
        abs=1e-14,
    )


def test_linear_fractional_box_solver_matches_small_exact_corner_oracle() -> None:
    numerator = [0.0, 1.0]
    denominator = [1.0, 1.0]
    central = [2.0, 3.0]
    epsilon = 0.1

    corners = [
        [central[0] * (1.0 + sign0 * epsilon), central[1] * (1.0 + sign1 * epsilon)]
        for sign0 in (-1.0, 1.0)
        for sign1 in (-1.0, 1.0)
    ]
    ratios = [values[1] / math.fsum(values) for values in corners]

    assert ratio_box_extreme(
        numerator,
        denominator,
        central,
        epsilon,
        maximize=False,
    ) == pytest.approx(min(ratios), abs=1e-15)
    assert ratio_box_extreme(
        numerator,
        denominator,
        central,
        epsilon,
        maximize=True,
    ) == pytest.approx(max(ratios), abs=1e-15)


def test_box_solver_rejects_invalid_uncertainty_domain() -> None:
    with pytest.raises(ValueError, match=r"\[0,1\)"):
        ratio_box_extreme([1.0], [1.0], [1.0], 1.0, maximize=True)
    with pytest.raises(ValueError, match="positive"):
        ratio_box_extreme([1.0], [1.0], [0.0], 0.03, maximize=True)
    with pytest.raises(ValueError, match="nonnegative"):
        ratio_box_extreme([1.0], [-1.0], [1.0], 0.03, maximize=True)


def test_source_sidecar_does_not_invent_systematic_covariance() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    uncertainty = source["source_uncertainty_note"]

    assert uncertainty["point_to_point_systematic_fraction"] == 0.03
    assert uncertainty["total_systematic_fraction_bound"] == "<0.045"
    assert uncertainty["point_to_point_source_section"] == "IV D"
    assert uncertainty["published_row_covariance_matrix"] is False
    boundary = uncertainty["analysis_boundary"].lower()
    assert "does not" in boundary
    assert "independent gaussian" in boundary
    assert "covariance" in boundary
    assert "explicit model choices" in boundary
