from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "studies" / "mv3_selection_matched.py"
SPEC = importlib.util.spec_from_file_location("mv3_selection_matched", MODULE_PATH)
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _add(bag, weight, stave):
    MOD._accumulate(
        bag,
        weight=weight,
        observable_depth=stave,
        truth_depth=stave,
        truth_term="stop",
        d_e=1.0,
        e_res=2.0,
        entry_ekin=100.0,
    )


def test_weight_contract_fails_closed():
    assert MOD._event_weight([2.5], 0) == 2.5
    for value, error in [([], "CARDINALITY"), ([1, 2], "CARDINALITY"),
                         ([np.nan], "NONFINITE"), ([-1], "NEGATIVE")]:
        with pytest.raises(MOD.ContractError, match=error):
            MOD._event_weight(value, 0)


def test_weighted_primary_and_unweighted_sensitivity():
    bag = MOD._new_bag()
    _add(bag, 1.0, "B2")
    _add(bag, 9.0, "B8")
    out = MOD._finalize_bag(bag)
    assert out["stop_depth_frac"]["B2"] == pytest.approx(0.1)
    assert out["stop_depth_frac"]["B8"] == pytest.approx(0.9)
    assert out["unweighted_stop_depth_frac"]["B2"] == pytest.approx(0.5)
    assert out["sum_w"] == 10.0
    assert out["sum_w2"] == 82.0
    assert out["effective_sample_size"] == pytest.approx(100 / 82)


def test_zero_total_weight_rejected():
    bag = MOD._new_bag()
    _add(bag, 0.0, "B2")
    with pytest.raises(MOD.ContractError, match="NONPOSITIVE_SELECTION_WEIGHT_SUM"):
        MOD._finalize_bag(bag)


def test_same_target_selection_ablation():
    mc = {
        "unselected": {"stop_depth_frac": dict(B2=.5, B4=.2, B6=.2, B8=.1)},
        "sample_i": {"stop_depth_frac": dict(B2=.8, B4=.1, B6=.05, B8=.05)},
    }
    data = {"sample_i": {
        "stop_depth_counts": dict(B2=90, B4=5, B6=3, B8=2),
        "stop_depth_frac": dict(B2=.9, B4=.05, B6=.03, B8=.02),
    }}
    out = MOD._same_target_metrics(mc, data)
    assert out["comparison_policy"] == "SAME_DATA_TARGET_FOR_SELECTION_ABLATION"
    ratio = (out["unselected_vs_sample_i"]["chi2_per_ndf"] /
             out["sample_i_vs_sample_i"]["chi2_per_ndf"])
    assert out["chi2_improvement_factor"] == pytest.approx(ratio)


def test_atomic_json_preserves_prior_output_on_nan(tmp_path):
    target = tmp_path / "summary.json"
    MOD._atomic_json(target, {"value": 1.0})
    before = target.read_bytes()
    with pytest.raises(ValueError):
        MOD._atomic_json(target, {"bad": float("nan")})
    assert target.read_bytes() == before
    assert json.loads(target.read_text()) == {"value": 1.0}


def test_source_uses_canonical_charge_and_applies_weights():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "is_charged" in source
    assert "pdg_charge(int(p)) >= 1" not in source
    assert "else 1.0" not in source
    assert '"primaryweight_applied": True' in source
