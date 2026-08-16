"""Wave B Lane 06: H3 weighted stopping-depth estimand (#1047)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ccb_mc_validation.truth.stop_depth import (
    summarize_stop_depth_by_species,
    summarize_stop_depth_h3,
)


def test_one_stop_nine_escape_equal_weights_conditional_is_one():
    """Legacy bug mixed H1/H2: weighted B2 fraction became 0.1; H3 stays 1.0."""
    term = ["stop"] + ["escape"] * 9
    layers = [2] + [float("nan")] * 9
    out = summarize_stop_depth_h3(
        termination=term, stop_layer=layers, weights=[1.0] * 10, n_layers=8
    )
    assert out["termination_prob_weighted"]["stop"] == pytest.approx(0.1)
    assert out["termination_prob_weighted"]["escape"] == pytest.approx(0.9)
    assert out["stop_distribution_weighted"][2] == pytest.approx(1.0)
    assert out["mean_stop_layer_weighted"] == pytest.approx(2.0)
    assert out["mean_stop_layer_weighted_status"] == "ok"
    assert out["stop_distribution_weighted_sum"] == pytest.approx(1.0)
    assert out["termination_prob_weighted_sum"] == pytest.approx(1.0)


def test_unequal_weights_only_stop_has_large_weight():
    term = ["stop", "escape", "escape"]
    layers = [1, float("nan"), float("nan")]
    weights = [9.0, 1.0, 1.0]
    out = summarize_stop_depth_h3(
        termination=term, stop_layer=layers, weights=weights, n_layers=8
    )
    assert out["termination_prob_weighted"]["stop"] == pytest.approx(9.0 / 11.0)
    assert out["stop_distribution_weighted"][1] == pytest.approx(1.0)
    assert out["mean_stop_layer_weighted"] == pytest.approx(1.0)


def test_all_escape_mean_unavailable_not_zero():
    term = ["escape", "escape"]
    layers = [float("nan"), float("nan")]
    out = summarize_stop_depth_h3(
        termination=term, stop_layer=layers, weights=[1.0, 1.0], n_layers=8
    )
    assert out["n_stop"] == 0
    assert out["mean_stop_layer_weighted"] is None
    assert out["mean_stop_layer_weighted_status"] == "unavailable"
    assert out["mean_stop_layer_weighted_reason"] == "no_stopping_tracks"
    assert out["termination_prob_weighted"]["escape"] == pytest.approx(1.0)
    assert sum(out["stop_distribution_weighted"].values()) == pytest.approx(0.0)


def test_all_censored_same_as_all_escape_for_depth():
    term = ["censored", "censored"]
    layers = [float("nan"), float("nan")]
    out = summarize_stop_depth_h3(
        termination=term, stop_layer=layers, n_layers=8
    )
    assert out["mean_stop_layer_weighted"] is None
    assert out["termination_prob_weighted"]["censored"] == pytest.approx(1.0)


def test_invalid_weights_fail_closed():
    with pytest.raises(ValueError, match="finite"):
        summarize_stop_depth_h3(
            termination=["stop"],
            stop_layer=[0],
            weights=[float("nan")],
        )
    with pytest.raises(ValueError, match="non-negative"):
        summarize_stop_depth_h3(
            termination=["stop"],
            stop_layer=[0],
            weights=[-1.0],
        )


def test_duplicate_track_weight_split_invariant():
    base = summarize_stop_depth_h3(
        termination=["stop", "escape"],
        stop_layer=[3, float("nan")],
        weights=[2.0, 2.0],
        n_layers=8,
    )
    split = summarize_stop_depth_h3(
        termination=["stop", "stop", "escape"],
        stop_layer=[3, 3, float("nan")],
        weights=[1.0, 1.0, 2.0],
        n_layers=8,
    )
    assert base["mean_stop_layer_weighted"] == pytest.approx(
        split["mean_stop_layer_weighted"]
    )
    assert base["stop_distribution_weighted"][3] == pytest.approx(
        split["stop_distribution_weighted"][3]
    )
    assert base["termination_prob_weighted"]["stop"] == pytest.approx(
        split["termination_prob_weighted"]["stop"]
    )


def test_by_species_masks_pdg():
    tracks = {
        "pdg": [2212, 2212, 1000010020],
        "termination": ["stop", "escape", "stop"],
        "stop_layer": [2, float("nan"), 0],
        "weight": [1.0, 1.0, 1.0],
    }
    out = summarize_stop_depth_by_species(
        tracks, species_pdg={"p": 2212, "d": 1000010020}, n_layers=8
    )
    assert out["p"]["n_tracks"] == 2
    assert out["p"]["stop_distribution_weighted"][2] == pytest.approx(1.0)
    assert out["d"]["stop_distribution_weighted"][0] == pytest.approx(1.0)


def test_nonfinite_stop_layer_on_stop_fails():
    with pytest.raises(ValueError, match="finite"):
        summarize_stop_depth_h3(
            termination=["stop"],
            stop_layer=[float("nan")],
            weights=[1.0],
        )


def test_unknown_termination_fails():
    with pytest.raises(ValueError, match="unknown termination"):
        summarize_stop_depth_h3(
            termination=["fly"],
            stop_layer=[0],
        )


def test_probs_sum_to_one_with_mixed_states():
    term = ["stop", "escape", "censored", "stop"]
    layers = [0, float("nan"), float("nan"), 4]
    weights = [1.0, 2.0, 3.0, 4.0]
    out = summarize_stop_depth_h3(
        termination=term, stop_layer=layers, weights=weights, n_layers=8
    )
    assert out["termination_prob_weighted_sum"] == pytest.approx(1.0)
    assert out["stop_distribution_weighted_sum"] == pytest.approx(1.0)
    assert out["mean_stop_layer_weighted"] == pytest.approx((1 * 0 + 4 * 4) / 5)
    assert not math.isnan(out["mean_stop_layer_weighted"])
