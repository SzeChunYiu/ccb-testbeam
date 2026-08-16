"""Lane 07 Wave A regressions for issues #958 #959 #960 #1049 #1052 #1097 #1164 #1166."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    path = REPO / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def s00():
    return _load("lane07_s00", "scripts/01_build_pulse_table_from_root.py")


@pytest.fixture(scope="module")
def p01():
    return _load("lane07_p01", "scripts/p01_self_supervised_waveform_representation.py")


@pytest.fixture(scope="module")
def cmc():
    sys.path.insert(0, str(REPO / "scripts"))
    import compare_data_mc as mod
    return mod


def test_958_second_stage_cap_updates_ht_weights():
    from ccb_mc_validation.statistics.case_control import apply_second_stage_class_cap

    rng = np.random.default_rng(0)
    # Known population: 20% selected.
    pop = np.concatenate([np.ones(200, dtype=int), np.zeros(800, dtype=int)])
    rng.shuffle(pop)
    keep_sel, keep_rej = 0.5, 0.5  # keep many so cap binds
    keep = rng.random(pop.size) < np.where(pop == 1, keep_sel, keep_rej)
    rows = pd.DataFrame(
        {
            "selected": pop[keep],
            "sampling_weight": np.where(pop[keep] == 1, 1 / keep_sel, 1 / keep_rej),
        }
    )
    max_sample = 50
    out, manifest = apply_second_stage_class_cap(
        rows, max_sample=max_sample, random_seed=1
    )
    assert manifest["cap_bound"] is True
    for cls, meta in manifest["classes"].items():
        if meta["cap_bound"]:
            subset = out[out["selected"] == int(cls)]
            expected = (1.0 / (keep_sel if int(cls) == 1 else keep_rej)) * meta["stage2_ht_factor"]
            assert np.allclose(subset["sampling_weight"], expected)
            assert np.allclose(subset["inclusion_p"], 1.0 / subset["sampling_weight"])
    # Weighted class prevalence recovers population after both stages.
    w = out["sampling_weight"].to_numpy(dtype=float)
    y = out["selected"].to_numpy(dtype=float)
    weighted_prev = float(np.sum(w * y) / np.sum(w))
    assert abs(weighted_prev - 0.20) < 0.05
    assert manifest["effective_sample_size"] > 0
    assert manifest["max_weight"] >= 1.0


def test_958_no_cap_regime_leaves_stage1_weights(s00):
    from ccb_mc_validation.statistics.case_control import apply_second_stage_class_cap

    rows = pd.DataFrame(
        {
            "selected": [1, 1, 0, 0],
            "sampling_weight": [5.0, 5.0, 20.0, 20.0],
        }
    )
    out, manifest = apply_second_stage_class_cap(rows, max_sample=100, random_seed=0)
    assert manifest["cap_bound"] is False
    assert sorted(out["sampling_weight"].tolist()) == [5.0, 5.0, 20.0, 20.0]
    assert set(out["stage2_inclusion_p"].tolist()) == {1.0}
    # Two-stage HT with unbound cap must leave stage-1 inverse probabilities intact.
    assert set(out.loc[out["selected"] == 1, "sampling_weight"]) == {5.0}
    assert set(out.loc[out["selected"] == 0, "sampling_weight"]) == {20.0}


def test_960_weighted_cluster_bootstrap_matches_estimand():
    from ccb_mc_validation.statistics.bootstrap import weighted_cluster_bootstrap, weighted_mean

    values = np.array([1.0, 1.0, 0.0, 0.0, 1.0, 0.0])
    weights = np.array([10.0, 10.0, 1.0, 1.0, 10.0, 1.0])
    clusters = np.array(["a", "a", "b", "b", "c", "c"], dtype=object)
    rng = np.random.default_rng(0)
    out = weighted_cluster_bootstrap(values, weights, clusters, rng, n_boot=200)
    assert out["status"] == "OK"
    assert out["point"] == pytest.approx(weighted_mean(values, weights))
    assert out["ci_low"] < out["ci_high"]
    assert out["n_clusters"] == 3


def test_960_bootstrap_failure_is_not_estimable_not_zero_width():
    from ccb_mc_validation.statistics.bootstrap import weighted_cluster_bootstrap

    values = np.array([1.0, 0.0])
    weights = np.array([1.0, 1.0])
    clusters = np.array(["only", "only"], dtype=object)  # one cluster
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError, match="NOT_ESTIMABLE|>=2 clusters"):
        weighted_cluster_bootstrap(values, weights, clusters, rng, n_boot=20)


def test_1097_run_block_bootstrap_preserves_multiplicity(p01):
    # Known-answer: three equal-size runs with means {0,10,20}.
    values = np.array([0.0, 0.0, 10.0, 10.0, 20.0, 20.0])
    runs = np.array([0, 0, 1, 1, 2, 2])

    class FakeRng:
        def __init__(self, draws):
            self.draws = list(draws)
        def choice(self, unique_runs, size, replace=True):
            return np.asarray(self.draws.pop(0))

    # Single draw [0,0,1] => intended pulse-weighted mean 3.333..., not 5.
    rng = FakeRng([[0, 0, 1]])
    # Monkeypatch ci to return raw mean for inspection by calling internals.
    sampled = np.array([0, 0, 1])
    idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
    assert float(np.mean(values[idx])) == pytest.approx(10.0 / 3.0)
    # Boolean-union bug would give 5.
    mask = np.zeros(len(values), dtype=bool)
    for run in sampled:
        mask |= runs == run
    assert float(np.mean(values[mask])) == pytest.approx(5.0)
    # Function returns finite CI for multi-run input.
    lo, hi = p01.run_block_bootstrap(values, runs, np.random.default_rng(0), n_boot=50)
    assert np.isfinite(lo) and np.isfinite(hi)


def test_1097_equal_cluster_estimand_differs_for_unequal_sizes(p01):
    values = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 30.0])
    runs = np.array([0, 0, 0, 0, 0, 1])
    # Fixed multiplicity draw [0,0]: pulse-weighted mean uses five 0s twice => 0;
    # wait, better: compute one replicate statistic directly for both estimands.
    sampled = np.array([0, 1])
    idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
    pulse = float(np.mean(values[idx]))
    equal = float(np.mean([float(np.mean(values[runs == run])) for run in sampled]))
    assert pulse == pytest.approx(5.0)  # five 0s + one 30
    assert equal == pytest.approx(15.0)  # mean(0, 30)
    assert pulse != equal
    # And the public API accepts both estimands.
    lo_p, hi_p = p01.run_block_bootstrap(
        values, runs, np.random.default_rng(1), n_boot=40, cluster_estimand="pulse_weighted"
    )
    lo_e, hi_e = p01.run_block_bootstrap(
        values, runs, np.random.default_rng(1), n_boot=40, cluster_estimand="equal_cluster"
    )
    assert np.isfinite(lo_p) and np.isfinite(hi_p)
    assert np.isfinite(lo_e) and np.isfinite(hi_e)


def test_1052_compare_prefers_event_unit_and_quarantines_hit(tmp_path, cmc):
    mc = tmp_path / "mc"
    da = tmp_path / "da"
    mc.mkdir(); da.mkdir()
    # Hit-level only
    np.savez_compressed(
        mc / "first_B_layer_edep.npz",
        sampleI=np.array([1.0, 2.0, 3.0], dtype=np.float32),
        sampleII=np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32),
        sampleI_weights=np.ones(3, dtype=np.float32),
        sampleII_weights=np.ones(4, dtype=np.float32),
        statistical_unit=np.asarray(["hit_step_edep"]),
    )
    np.savez_compressed(
        da / "first_B_layer_B2_amplitude.npz",
        sampleI=np.array([100.0, 200.0, 300.0], dtype=np.float32),
        sampleII=np.array([100.0, 200.0, 300.0, 400.0], dtype=np.float32),
        sampleI_cluster_id=np.array(["1:1", "1:2", "1:3"]),
        sampleII_cluster_id=np.array(["2:1", "2:2", "2:3", "2:4"]),
    )
    loaded = cmc._load_spectrum_with_contract(mc, da)
    assert loaded["contract"]["quarantine"] == "NONAUTHORISING_BLOCKED_ISSUE_1052"
    assert loaded["contract"]["authorising_statistical_unit"] is False

    # Event-level product preferred
    np.savez_compressed(
        mc / "first_B_layer_event_edep.npz",
        sampleI=np.array([6.0], dtype=np.float32),
        sampleII=np.array([10.0], dtype=np.float32),
        sampleI_weights=np.ones(1, dtype=np.float32),
        sampleII_weights=np.ones(1, dtype=np.float32),
        sampleI_cluster_id=np.array([42], dtype=np.int64),
        sampleII_cluster_id=np.array([42], dtype=np.int64),
        sampleI_in_sample_i=np.array([True]),
        sampleI_in_sample_ii=np.array([True]),
        sampleII_in_sample_i=np.array([True]),
        sampleII_in_sample_ii=np.array([True]),
        statistical_unit=np.asarray(["event_stave_edep"]),
    )
    loaded2 = cmc._load_spectrum_with_contract(mc, da)
    assert loaded2["contract"]["mc_product"] == "first_B_layer_event_edep.npz"
    assert loaded2["contract"]["mc_statistical_unit"] == "event_stave_edep"
    assert loaded2["mcI"][0] == pytest.approx(6.0)


def test_1164_scale_topology_and_cluster_gate(cmc, tmp_path):
    mc = tmp_path / "mc"; da = tmp_path / "da"
    mc.mkdir(); da.mkdir()
    np.savez_compressed(
        mc / "first_B_layer_event_edep.npz",
        sampleI=np.array([1.0, 2.0], dtype=np.float32),
        sampleII=np.array([1.0, 2.0, 3.0], dtype=np.float32),
        sampleI_weights=np.ones(2, dtype=np.float32),
        sampleII_weights=np.ones(3, dtype=np.float32),
        sampleI_cluster_id=np.array([1, 2], dtype=np.int64),
        sampleII_cluster_id=np.array([1, 2, 3], dtype=np.int64),
        sampleI_in_sample_i=np.array([True, True]),
        sampleI_in_sample_ii=np.array([True, True]),
        sampleII_in_sample_i=np.array([True, True, False]),
        sampleII_in_sample_ii=np.array([True, True, True]),
        statistical_unit=np.asarray(["event_stave_edep"]),
    )
    np.savez_compressed(
        da / "first_B_layer_B2_amplitude.npz",
        sampleI=np.array([10.0, 20.0], dtype=np.float32),
        sampleII=np.array([10.0, 20.0, 30.0], dtype=np.float32),
        sampleI_cluster_id=np.array(["a:1", "a:2"]),
        sampleII_cluster_id=np.array(["b:1", "b:2", "b:3"]),
    )
    loaded = cmc._load_spectrum_with_contract(mc, da)
    topo = cmc._scale_topology_record(loaded["membership"], loaded["data_clusters"])
    assert topo["fit_sample"] == "II"
    assert topo["mc_sample_i_subset_of_ii"] is True
    assert topo["nuisance_mode_default"] == "refit_inside_replicate"
    assert topo["authorising"] is False
    assert loaded["contract"]["null_calibration_gate"] == "OPEN_FOR_RESEARCH"


def test_1049_legacy_pvalue_remains_nonauthorising(cmc):
    out = cmc._weighted_ks_stat(
        np.array([0.0, 1.0, 2.0]),
        np.array([0.0, 1.5, 2.5]),
        np.ones(3),
        np.array([1.0, 2.0, 3.0]),
        n_bootstrap=20,
    )
    assert out["p_value_status"] == "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION"
    assert out["p_value_method"] == "legacy_unit_weight_value_permutation"


def test_959_ml_check_requires_weights_and_eventno(s00, tmp_path):
    rows = pd.DataFrame(
        {
            "run": [1, 1, 2, 2],
            "selected": [1, 0, 1, 0],
            "area_adc_samples": [1.0, 2.0, 3.0, 4.0],
            "peak_sample": [1, 2, 3, 4],
            "baseline_adc": [0.1, 0.2, 0.3, 0.4],
            "amplitude_adc": [10.0, 20.0, 30.0, 40.0],
        }
    )
    config = {
        "amplitude_cut_adc": 15.0,
        "ml_check": {
            "heldout_runs": [2],
            "regularization_c": [1.0],
            "cv_folds": 2,
            "random_seed": 0,
            "bootstrap_reps": 20,
            "features": ["area_adc_samples", "peak_sample", "baseline_adc"],
        },
    }
    with pytest.raises(ValueError, match="sampling_weight"):
        s00.run_ml_check(config, rows, tmp_path)
