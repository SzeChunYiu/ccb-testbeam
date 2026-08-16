from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

WRAPPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "single_stave"
    / "issues879_880_887_mc_study_strict.py"
)
SPEC = importlib.util.spec_from_file_location("strict_issue880_producer", WRAPPER_PATH)
assert SPEC and SPEC.loader
producer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(producer)


def synthetic_inputs() -> tuple[dict[int, np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    energy = {
        0: np.array([1.0, 3.0, 7.0, 9.0]),
        1: np.array([2.0, 4.0, 8.0, 10.0]),
    }
    for layer in range(2, 8):
        energy[layer] = np.zeros(4)
    weights = np.array([1.0, 2.0, 1.0, 6.0])
    entering_pdg = np.array([2212, 1000010020, 2212, 1000010020])
    entering_charged = np.array([True, True, True, True])
    return energy, weights, entering_pdg, entering_charged


def test_study_880_uses_explicit_direction_and_denominator_fields() -> None:
    energy, weights, entering_pdg, entering_charged = synthetic_inputs()
    result = producer.study_880_strict(
        energy,
        weights,
        entering_pdg,
        entering_charged,
    )
    mean = result["first_B_layer_mean"]
    assert mean["unweighted_legacy"] == pytest.approx(5.0)
    assert mean["weighted"] == pytest.approx(6.8)
    assert mean["weighted_minus_unweighted"] == pytest.approx(1.8)
    assert mean["weighted_minus_unweighted_pct_of_abs_unweighted"] == pytest.approx(36.0)
    assert mean["legacy_overstatement_pct_of_abs_weighted"] == pytest.approx(
        -100.0 * 1.8 / 6.8
    )

    fraction = result["deuteron_fraction_entering_B"]
    assert fraction["unweighted_legacy"] == pytest.approx(0.5)
    assert fraction["weighted"] == pytest.approx(0.8)
    assert fraction["weighted_minus_unweighted_percentage_points"] == pytest.approx(30.0)
    assert result["weight_validation"]["n_weights"] == 4
    assert result["weight_validation"]["ess"] == pytest.approx(100.0 / 42.0)


def test_study_880_rejects_nonfinite_negative_and_misaligned_weights() -> None:
    energy, weights, entering_pdg, entering_charged = synthetic_inputs()
    bad = weights.copy()
    bad[1] = np.nan
    with pytest.raises(producer.strict.WeightValidationError, match="nonfinite"):
        producer.study_880_strict(energy, bad, entering_pdg, entering_charged)
    bad = weights.copy()
    bad[1] = -1.0
    with pytest.raises(producer.strict.WeightValidationError, match="negative"):
        producer.study_880_strict(energy, bad, entering_pdg, entering_charged)
    with pytest.raises(producer.strict.WeightValidationError, match="expected 4"):
        producer.study_880_strict(energy, weights[:3], entering_pdg, entering_charged)


def test_study_880_rejects_empty_species_selection_and_zero_variance() -> None:
    energy, weights, entering_pdg, entering_charged = synthetic_inputs()
    with pytest.raises(producer.strict.WeightValidationError, match="no charged"):
        producer.study_880_strict(
            energy,
            weights,
            entering_pdg,
            np.zeros_like(entering_charged),
        )
    energy[1] = np.ones(4)
    with pytest.raises(producer.strict.WeightValidationError, match="zero variance"):
        producer.study_880_strict(energy, weights, entering_pdg, entering_charged)


def test_strict_histogram_overlap_rejects_zero_weight_subsample() -> None:
    with pytest.raises(producer.strict.WeightValidationError, match="no positive"):
        producer._strict_bhattacharyya_overlap(
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
            np.array([0.0, 0.0]),
            np.array([1.0, 1.0]),
            np.array([0.0, 2.5, 5.0]),
            None,
        )


def test_output_contract_requires_explicit_overwrite(tmp_path: Path) -> None:
    existing = tmp_path / "issues879_880_887_result.json"
    existing.write_text("{}\n", encoding="utf-8")
    with pytest.raises(producer.strict.WeightValidationError, match="--overwrite"):
        producer._ensure_output_contract(tmp_path, overwrite=False)
    producer._ensure_output_contract(tmp_path, overwrite=True)


def test_source_has_no_unit_weight_coercion_or_unweighted_fallbacks() -> None:
    source = WRAPPER_PATH.read_text(encoding="utf-8")
    assert "np.where(np.isfinite(w_evt), w_evt, 1.0)" not in source
    assert "if sw > 0 else" not in source
    assert "max(abs(float(first_b.mean())), 1e-9)" not in source
    assert producer.PRODUCER_POLICY in source
    assert "SHA256_BEFORE_AND_AFTER_ROOT_READ_MUST_MATCH" in source
    assert "tracked working tree is dirty" in source
