"""Direct falsifier for the legacy blocked permutation null in compare_data_mc.py."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))
import compare_data_mc as cmc

from tools.audit.research_weighted_null_cluster_contract import split_weighted_rows


def test_legacy_unit_weight_permutation_is_not_representation_invariant():
    rng = np.random.default_rng(7)
    data = rng.normal(0.0, 1.0, 30)
    model = rng.normal(0.5, 1.0, 25)
    data_weights = np.ones(data.size)
    model_weights = np.exp(-0.5 * model)
    clusters = np.arange(model.size)
    split_model, split_weights, _ = split_weighted_rows(
        model, model_weights, clusters, 5
    )

    base = cmc._weighted_ks_stat(
        data, model, data_weights, model_weights, n_bootstrap=200
    )
    split = cmc._weighted_ks_stat(
        data, split_model, data_weights, split_weights, n_bootstrap=200
    )

    assert base["p_value_status"] == "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION"
    assert split["p_value_status"] == "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION"
    assert base["p_value_method"] == "legacy_unit_weight_value_permutation"
    assert split["p_value_method"] == "legacy_unit_weight_value_permutation"
    assert base["D"] == pytest.approx(split["D"], abs=1e-12)
    assert base["p_value"] == pytest.approx(0.16)
    assert split["p_value"] == pytest.approx(0.025)
    assert abs(base["p_value"] - split["p_value"]) > 0.10
