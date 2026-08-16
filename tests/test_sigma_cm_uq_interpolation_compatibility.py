from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit.research_sigma_cm_uq_interpolation_compatibility import (
    ALTERNATIVE_MODE,
    CURRENT_MODE,
    audit_compatibility,
)

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"
RESULT = ROOT / "results/research/sigma_cm_uq_interpolation_compatibility_v1.json"


@pytest.fixture(scope="module")
def audit() -> dict[str, object]:
    return audit_compatibility(TABLE)


def test_committed_result_is_exact_audit_serialization(audit: dict[str, object]) -> None:
    assert json.loads(RESULT.read_text(encoding="utf-8")) == audit


def test_current_mode_reproduces_prior_uq_contract(audit: dict[str, object]) -> None:
    current = audit["node_box_by_interpolation"][CURRENT_MODE]
    assert current["max_upward_cdf_excursion_from_own_nominal"]["value"] == pytest.approx(
        0.01430729974634637, abs=2e-15
    )
    assert current["max_downward_cdf_excursion_from_own_nominal"]["value"] == pytest.approx(
        0.014380572923809676, abs=2e-15
    )


def test_interpolation_and_node_box_do_not_collapse_to_one_nuisance(
    audit: dict[str, object],
) -> None:
    cross = audit["cross_atom_compatibility"]
    assert cross["alternative_nominal_max_violation_of_current_box"] == 0.0
    assert cross["alternative_box_max_upper_extension_beyond_current_box"][
        "value"
    ] == pytest.approx(0.0010650343985590949, abs=2e-15)
    assert cross["alternative_box_max_lower_extension_beyond_current_box"][
        "value"
    ] == pytest.approx(0.0002537872354466675, abs=2e-15)


def test_union_envelope_is_cross_model_not_confidence_interval(
    audit: dict[str, object],
) -> None:
    union = audit["cross_atom_compatibility"]["union_envelope_relative_to_current_nominal"]
    assert union["max_upward_cdf_excursion"]["value"] == pytest.approx(
        0.015299817076167732, abs=2e-15
    )
    assert union["max_downward_cdf_excursion"]["value"] == pytest.approx(
        0.014380572923809676, abs=2e-15
    )
    boundary = audit["scientific_boundary"].lower()
    assert "not a confidence region" in boundary
    assert "do not add" in boundary


def test_alternative_statistical_reference_is_close_but_distinct(
    audit: dict[str, object],
) -> None:
    refs = audit["conditional_diagonal_statistical_reference"]
    assert refs[CURRENT_MODE]["max_pointwise_cdf_standard_uncertainty"][
        "value"
    ] == pytest.approx(0.0004453566889758832, abs=2e-15)
    assert refs[ALTERNATIVE_MODE]["max_pointwise_cdf_standard_uncertainty"][
        "value"
    ] == pytest.approx(0.0004435837618530407, abs=2e-15)
