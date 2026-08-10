from __future__ import annotations

from pathlib import Path

import pytest

from tools.audit.research_sigma_cm_sampler_contract import audit_sampler


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"


def test_current_sampler_is_piecewise_constant_inside_cdf_intervals() -> None:
    result = audit_sampler(TABLE)

    assert result["input"]["sha256"] == (
        "0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc"
    )
    assert result["current_algorithm"]["resulting_within_interval_density"] == (
        "piecewise_constant_interval_average"
    )

    assert result["probability_below_measured_support"] == pytest.approx(
        0.3394630084684921,
        abs=1e-15,
    )
    assert result["probability_above_measured_support"] == pytest.approx(
        0.003869284858232269,
        abs=1e-15,
    )
    assert result["probability_outside_measured_support"] == pytest.approx(
        0.3433322933267244,
        abs=1e-15,
    )


def test_linear_inverse_cdf_does_not_sample_the_trapezoid_node_pdf() -> None:
    result = audit_sampler(TABLE)

    assert result["max_cdf_deviation_interval_index"] == 0
    assert result["max_cdf_deviation_theta_cm_deg"] == pytest.approx(13.245, abs=1e-12)
    assert result["max_cdf_deviation_vs_linear_node_pdf"] == pytest.approx(
        0.08486575211712302,
        abs=1e-15,
    )
