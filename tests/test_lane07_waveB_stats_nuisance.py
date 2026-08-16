"""Lane 07 Wave B regressions for issues #1047 #984 #985."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    if str(REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO / "scripts"))
    path = REPO / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def h3():
    return _load("lane07_h3", "scripts/lane07/stopping_depth_h3.py")


@pytest.fixture(scope="module")
def resp():
    return _load("lane07_resp", "scripts/lane07/nuisance_response.py")


@pytest.fixture(scope="module")
def gen_points():
    return _load("lane07_gen_points", "geant4/single_stave/slurm/grids/generate_points.py")


# --- #1047 ---

def test_1047_one_stop_one_escape_conditional_is_unity(h3):
    out = h3.summarize_stopping_h3(
        ["stop", "escape"], [2, np.nan], [1.0, 1.0], n_layers=8
    )
    assert out["termination_probability_weighted"]["stop"] == pytest.approx(0.5)
    assert out["termination_probability_weighted"]["escape"] == pytest.approx(0.5)
    assert out["stop_depth_status"] == "OK"
    assert out["stop_distribution_weighted"][2] == pytest.approx(1.0)
    assert sum(out["stop_distribution_weighted"].values()) == pytest.approx(1.0)
    assert out["mean_stop_layer_weighted"] == pytest.approx(2.0)


def test_1047_nine_escape_one_stop_does_not_dilute_conditional(h3):
    term = ["stop"] + ["escape"] * 9
    layers = [2] + [np.nan] * 9
    w = [1.0] * 10
    out = h3.summarize_stopping_h3(term, layers, w, n_layers=8)
    # Unconditional stop prob is 0.1; conditional depth at B2 is 1.0
    assert out["termination_probability_weighted"]["stop"] == pytest.approx(0.1)
    assert out["stop_distribution_weighted"][2] == pytest.approx(1.0)
    assert out["mean_stop_layer_weighted"] == pytest.approx(2.0)


def test_1047_unequal_weights_conditional_mean(h3):
    out = h3.summarize_stopping_h3(
        ["stop", "stop", "escape"],
        [1, 3, np.nan],
        [9.0, 1.0, 5.0],
        n_layers=8,
    )
    assert out["mean_stop_layer_weighted"] == pytest.approx((9 * 1 + 1 * 3) / 10)
    assert out["termination_probability_weighted"]["stop"] == pytest.approx(10 / 15)


def test_1047_all_escape_unavailable_not_zero(h3):
    out = h3.summarize_stopping_h3(
        ["escape", "escape"], [np.nan, np.nan], [1.0, 2.0], n_layers=8
    )
    assert out["stop_depth_status"] == "UNAVAILABLE"
    assert out["mean_stop_layer_weighted"] is None
    assert out["stop_distribution_weighted"] is None
    assert out["termination_probability_weighted"]["escape"] == pytest.approx(1.0)


def test_1047_all_censored_unavailable(h3):
    out = h3.summarize_stopping_h3(
        ["censored"], [np.nan], [1.0], n_layers=8
    )
    assert out["stop_depth_status"] == "UNAVAILABLE"
    assert out["termination_probability_weighted"]["censored"] == pytest.approx(1.0)


def test_1047_negative_weights_blocked(h3):
    out = h3.summarize_stopping_h3(
        ["stop"], [1], [-1.0], n_layers=8
    )
    assert out["status"] == "BLOCKED"
    assert out["reason"] == "nonfinite_or_negative_weights"


def test_1047_duplicate_weight_invariance(h3):
    pair = h3.duplicate_weight_invariance(
        ["stop", "escape", "stop"],
        [2, np.nan, 5],
        [3.0, 1.0, 1.0],
        n_layers=8,
    )
    a, b = pair["a"], pair["b"]
    assert a["mean_stop_layer_weighted"] == pytest.approx(b["mean_stop_layer_weighted"])
    assert a["termination_probability_weighted"]["stop"] == pytest.approx(
        b["termination_probability_weighted"]["stop"]
    )


def test_1047_termination_probs_normalize(h3):
    out = h3.summarize_stopping_h3(
        ["stop", "escape", "censored"],
        [0, np.nan, np.nan],
        [2.0, 3.0, 5.0],
        n_layers=8,
    )
    p = out["termination_probability_weighted"]
    assert p["stop"] + p["escape"] + p["censored"] == pytest.approx(1.0)


# --- #985 ---

def test_985_recovers_exact_linear_local_slope(resp):
    xs = ["0.6", "0.8", "1.0", "1.2", "1.4"]
    ys = [6.0, 8.0, 10.0, 12.0, 14.0]
    out = resp.summarize_numeric_response(xs, ys, [0.0] * 5, preferred_nominal=1.0)
    assert out["local"]["status"] == "OK"
    assert out["local"]["local_slope"] == pytest.approx(10.0)
    assert out["global_linear_diagnostic"]["global_linear_misleading"] is False


def test_985_flags_saturating_response_as_misleading_global(resp):
    xs = ["0", "1", "2", "3", "4"]
    ys = [0.0, 0.2, 1.0, 1.8, 2.0]
    fcs = [0.0, 0.0, 0.0, 0.0, 0.7]  # endpoint clipped
    out = resp.summarize_numeric_response(xs, ys, fcs, preferred_nominal=2.0)
    assert out["global_linear_diagnostic"]["global_linear_misleading"] is True
    # Saturated endpoint must not be used for ADC local neighbors on the right
    # if only right neighbor is clipped, left still available.
    assert out["local"]["status"] == "OK"
    assert out["unsaturated_mask"][-1] is False


def test_985_nominal_saturated_blocks_adc_local(resp):
    xs = ["0.8", "1.0", "1.2"]
    ys = [100.0, 3895.0, 3895.0]
    fcs = [0.0, 0.9, 0.9]
    out = resp.summarize_numeric_response(xs, ys, fcs, preferred_nominal=1.0)
    assert out["local"]["status"] == "BLOCKED"
    assert out["local"]["reason"] == "nominal_point_adc_saturated"


def test_985_quadratic_curvature_flag(resp):
    xs = [str(x) for x in [0, 1, 2, 3, 4]]
    ys = [float(x * x) for x in range(5)]
    out = resp.summarize_numeric_response(xs, ys, [0.0] * 5, preferred_nominal=2.0)
    assert out["global_linear_diagnostic"]["curvature_flag"] is True
    assert out["global_linear_diagnostic"]["global_linear_misleading"] is True


# --- #984 ---

def test_984_emit_uses_same_seed_across_values(gen_points, tmp_path):
    # Align with landed main AF-036 / #984 CRN contract (explicit seed replicates).
    knob = gen_points.Knob(
        "pde_scale", "cli", "--pde-scale", "x", "test", [0.6, 1.0, 1.4]
    )
    path, _rows = gen_points.emit(knob, tmp_path, [1000, 1001, 1002])
    rows = []
    for ln in path.read_text().splitlines():
        if not ln or ln.startswith("#") or ln.startswith("label,"):
            continue
        rows.append(ln.split(","))
    assert len(rows) == 9  # 3 values x 3 replicates
    from collections import defaultdict
    by_seed = defaultdict(set)
    for label, seed, _nev, _cli, _env in rows:
        by_seed[seed].add(label.split("__rep=")[0])
        assert f"__rep={seed}" in label
        assert seed == label.rsplit("__rep=", 1)[1]
    assert set(by_seed) == {"1000", "1001", "1002"}
    assert all(len(vals) == 3 for vals in by_seed.values())
    assert by_seed["1000"] == by_seed["1001"] == by_seed["1002"]


def test_984_paired_replicate_effects(resp):
    # Labels use main's __rep=<seed> encoding (#984).
    values = ["1.0__rep=0", "1.2__rep=0", "1.0__rep=1", "1.2__rep=1"]
    ys = [10.0, 12.0, 11.0, 13.5]
    out = resp.paired_replicate_effects(values, ys, preferred_nominal=1.0)
    assert out["status"] == "OK"
    assert out["n_replicates"] == 2
    assert out["between_seed"]["1.2"]["mean_delta"] == pytest.approx(2.25)
    assert out["between_seed"]["1.2"]["n_replicates"] == 2


def test_984_checked_in_grids_are_paired():
    csv = REPO / "geant4/single_stave/slurm/grids/points_pde_scale.csv"
    text = csv.read_text()
    assert "paired_seed_design" in text or "common-random-number" in text
    assert "seed_replicates" in text
    assert "__rep=" in text
    rows = [
        ln.split(",")
        for ln in text.splitlines()
        if ln and not ln.startswith("#") and not ln.startswith("label,")
    ]
    from collections import defaultdict
    by_seed = defaultdict(set)
    for r in rows:
        label, seed = r[0], r[1]
        assert f"__rep={seed}" in label
        by_seed[seed].add(label.split("__rep=")[0])
    assert len(by_seed) >= 2
    vals = next(iter(by_seed.values()))
    assert all(v == vals for v in by_seed.values())
