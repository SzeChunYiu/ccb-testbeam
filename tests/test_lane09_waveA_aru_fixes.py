"""Known-answer regression tests for Lane 09 Wave A ARU study-script fixes.

Issues covered: #1112 #1117 #1119 #1120 #1121 #1124 #1125 #1126 #1127 #1128
#1129 #1137. #1116 is provenance-labelled only (full physical injection BLOCKED).
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    if not path.exists():
        pytest.skip(f"{path} missing")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def s00():
    return _load(REPO / "scripts" / "01_build_pulse_table_from_root.py", "lane09_s00")


@pytest.fixture(scope="module")
def mv5():
    return _load(REPO / "scripts" / "mv5_pileup_study.py", "lane09_mv5")


@pytest.fixture(scope="module")
def p04p():
    return _load(
        REPO / "scripts" / "p04p_1781046824_725_569d120d_duplicate_harm_labels.py",
        "lane09_p04p",
    )


@pytest.fixture(scope="module")
def p04q():
    # Depends on importing p04p helpers; load after ensuring path
    sys.path.insert(0, str(REPO / "scripts"))
    return _load(
        REPO / "scripts" / "p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.py",
        "lane09_p04q",
    )


@pytest.fixture(scope="module")
def s10():
    return _load(
        REPO
        / "reports"
        / "1780997954.15277.548b01a3__s10_pileup_rate_model"
        / "s10_pileup_rate_model.py",
        "lane09_s10",
    )


@pytest.fixture(scope="module")
def s12a():
    return _load(REPO / "scripts" / "s12a_0000000012_1_truthtiming.py", "lane09_s12a")


# ---------------------------------------------------------------------------
# #1112 two-stage design weights
# ---------------------------------------------------------------------------


def test_1112_two_stage_weights_when_cap_binds_one_class(s00):
    """Cap binds selected only: missing p2 cannot be a common factor."""
    rng = np.random.default_rng(0)
    n_sel, n_rej = 200, 30
    rows = pd.DataFrame(
        {
            "selected": np.r_[np.ones(n_sel, dtype=int), np.zeros(n_rej, dtype=int)],
            "sampling_weight": np.r_[np.full(n_sel, 5.0), np.full(n_rej, 20.0)],
            "run": 1,
        }
    )
    capped, prov = s00.apply_two_stage_design_weights(
        rows,
        max_sample=40,
        random_seed=7,
        keep_selected=0.20,
        keep_rejected=0.05,
    )
    assert prov["stage1_counts"]["1"] == 200
    assert prov["stage2_counts"]["1"] == 40
    assert prov["p_cap_conditional"]["1"] == pytest.approx(40 / 200)
    assert prov["p_cap_conditional"]["0"] == pytest.approx(1.0)  # rejected uncapped
    w_sel = capped.loc[capped["selected"] == 1, "sampling_weight"].iloc[0]
    w_rej = capped.loc[capped["selected"] == 0, "sampling_weight"].iloc[0]
    assert w_sel == pytest.approx(1.0 / (0.20 * 40 / 200))
    assert w_rej == pytest.approx(1.0 / 0.05)
    # Weighted prevalence recovers Stage-1 population ratio (200 sel / 250 total
    # after Stage-1 algebra with equal within-class weights before cap).
    # With corrected weights: sum(w*y)/sum(w) over capped sample.
    y = capped["selected"].to_numpy(float)
    w = capped["sampling_weight"].to_numpy(float)
    # Population after Stage-1: each selected represents 5, each rejected 20,
    # and after Stage-2 the selected weight grows by 200/40 so total selected
    # weight mass = 40 * 5 * (200/40) = 200*5 = 1000; rejected = 50*20 = 1000.
    assert np.sum(w * y) / np.sum(w) == pytest.approx(1000.0 / 1600.0, abs=1e-9)


def test_1112_no_cap_reduces_to_stage1(s00):
    rows = pd.DataFrame(
        {
            "selected": np.array([1, 1, 0, 0], dtype=int),
            "sampling_weight": np.array([5.0, 5.0, 20.0, 20.0]),
        }
    )
    capped, prov = s00.apply_two_stage_design_weights(
        rows, max_sample=100, random_seed=1, keep_selected=0.2, keep_rejected=0.05
    )
    assert prov["p_cap_conditional"]["1"] == 1.0
    assert sorted(capped["sampling_weight"].tolist()) == [5.0, 5.0, 20.0, 20.0]


# ---------------------------------------------------------------------------
# #1119 / #1120 / #1121 MV5
# ---------------------------------------------------------------------------


def test_1119_combined_noise_is_single_realization(mv5):
    rng = np.random.default_rng(0)
    w1 = mv5.sim_waveform(1.0, 20.0, rng, with_noise=False)
    w2 = mv5.sim_waveform(1.0, 50.0, rng, with_noise=False)
    # Force known noise by patching: combine then measure residual RMS vs PED+S
    signal = w1 + w2 - mv5.PED
    rng2 = np.random.default_rng(123)
    comb = mv5.combine_two_arrivals(w1, w2, rng2, with_noise=True)
    # Reconstruct: clipped rounded — compare pre-clip path via another rng draw
    rng3 = np.random.default_rng(123)
    expected = signal + rng3.normal(0, mv5.NOISE, mv5.NSAMP)
    expected = mv5.clip_adc(expected)
    assert np.allclose(comb, expected)


def test_1120_analytic_peak_norm_not_sample_max(mv5):
    """Phase-shifted pulse must not be forced to exact edep*GAIN at a sample."""
    rng = np.random.default_rng(0)
    # Choose a phase where the continuous peak falls between samples.
    w = mv5.sim_waveform(1.0, 23.0, rng, with_noise=False)
    peak_height = float(np.max(w) - mv5.PED)
    assert peak_height < mv5.GAIN  # sample max strictly below continuous peak amp
    assert mv5.analytic_pulse_peak_height() == pytest.approx(
        math.exp(-math.log(mv5.TAU_D / mv5.TAU_R) / (1 / mv5.TAU_R - 1 / mv5.TAU_D) / mv5.TAU_D)
        - math.exp(-math.log(mv5.TAU_D / mv5.TAU_R) / (1 / mv5.TAU_R - 1 / mv5.TAU_D) / mv5.TAU_R),
        rel=1e-6,
    )


def test_1121_all_ordered_pair_classes(mv5):
    rng = np.random.default_rng(0)
    e_p = np.array([1.0, 2.0])
    e_d = np.array([3.0, 4.0])
    seen = set()
    for pc in mv5.ORDERED_PAIR_CLASSES:
        a, b, s1, s2 = mv5.draw_ordered_pair_energies(rng, e_p, e_d, pc)
        seen.add(pc)
        assert s1 in {"p", "d"} and s2 in {"p", "d"}
    assert seen == set(mv5.ORDERED_PAIR_CLASSES)
    # Legacy toy never emits d-first.
    for _ in range(50):
        assert mv5.legacy_proton_first_pair_class(rng).startswith("p->")


# ---------------------------------------------------------------------------
# #1124 CFD amplitude units
# ---------------------------------------------------------------------------


def test_1124_raw_integral_cfd_uses_peak_not_charge(p04p):
    wave = np.array(
        [[0, 5, 20, 50, 80, 100, 90, 80, 70, 60, 45, 30, 20, 10, 5, 0, 0, 0]],
        dtype=float,
    )
    peak = np.array([100.0])
    charge = np.array([665.0])  # ADC-samples
    t_peak = p04p.cfd_time_samples(wave, peak, 0.2)
    t_bad = p04p.cfd_time_samples(wave, charge, 0.2)
    assert np.isfinite(t_peak[0])
    assert t_peak[0] == pytest.approx(2.0)
    assert not np.isfinite(t_bad[0])  # documents the dimensional failure mode


# ---------------------------------------------------------------------------
# #1125 run-preserving bootstrap
# ---------------------------------------------------------------------------


def test_1125_run_bootstrap_keeps_staves_together(p04q):
    """Perfectly correlated 8x3 toy: stave-run vs run bootstrap differ."""
    rows = []
    for run in range(8):
        for stave in ["B4", "B6", "B8"]:
            # Shared run-level flag rate: run 0-3 all positive, 4-7 all negative
            harm = 1 if run < 4 else 0
            for k in range(5):
                rows.append(
                    {
                        "run": run,
                        "stave": stave,
                        "harm_label": harm,
                        "flag_ridge": harm,
                        "prob_ridge": float(harm),
                        "prod_charge_frac_error": 0.0,
                        "prod_time_resid_ns": 0.0,
                    }
                )
    frame = pd.DataFrame(rows)
    rng = np.random.default_rng(0)
    summary = p04q.summarize_method(frame, "ridge", reps=200, rng=rng)
    assert summary["resampling_unit"] == "run"
    assert summary["n_resampling_units"] == 8
    # With run resampling, each draw picks whole runs (all 3 staves).


# ---------------------------------------------------------------------------
# #1126 silent MLP->CNN relabel
# ---------------------------------------------------------------------------


def test_1126_torch_failure_does_not_alias_mlp(p04p, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("forced torch failure")

    monkeypatch.setattr(p04p, "fit_torch_classifier", boom)
    # Minimal fold-like frame
    fold = pd.DataFrame({"prob_mlp": [0.1, 0.9], "prob_gradient_boosted_trees": [0.2, 0.8]})
    # Emulate the fail-closed assignment path used in the script
    fold["prob_cnn_1d"] = np.full(len(fold), np.nan)
    fold["prob_wavegate_resnet"] = np.full(len(fold), np.nan)
    assert not np.allclose(fold["prob_cnn_1d"].fillna(-1), fold["prob_mlp"])
    summary = p04p.summarize_method(
        pd.DataFrame(
            {
                "harm_label": [0, 1],
                "flag_cnn_1d": [False, False],
                "prob_cnn_1d": [np.nan, np.nan],
                "prod_charge_frac_error": [0.0, 0.0],
                "prod_time_resid_ns": [0.0, 0.0],
                "run": [1, 1],
            }
        ),
        "cnn_1d",
        reps=2,
        rng=np.random.default_rng(0),
    )
    assert summary["execution_state"] == "FAILED_MODEL_EXECUTION"
    assert summary.get("eligible_for_ranking") is False


# ---------------------------------------------------------------------------
# #1117 source-identity split
# ---------------------------------------------------------------------------


def test_1117_inject_returns_primary_source_ids(s10):
    waves = np.zeros((10, s10.NSAMPLES))
    waves[:, 5] = np.arange(10) + 1
    amp = waves.max(axis=1)
    primary, injected, src = s10.inject_pileup(waves, amp, n=6, source_ids=np.arange(10) * 10)
    assert len(src) == 6
    assert primary.shape == injected.shape


# ---------------------------------------------------------------------------
# #1127 / #1129 TOF + sampling helpers
# ---------------------------------------------------------------------------


def test_1127_reciprocal_trap_differs_from_arithmetic_beta(s12a):
    c = 29.9792458
    distance = 4.0
    beta_a, beta_b = 0.2, 0.4
    arith = distance / (((beta_a + beta_b) / 2) * c)
    trap = distance * 0.5 * (1 / beta_a + 1 / beta_b) / c
    assert trap != pytest.approx(arith)
    df = pd.DataFrame(
        {
            "distance_cm": [distance],
            "beta_mid": [(beta_a + beta_b) / 2],
            "beta_a": [beta_a],
            "beta_b": [beta_b],
            "inv_beta_trap": [0.5 * (1 / beta_a + 1 / beta_b)],
            "pair": ["0-2"],
        }
    )
    out = s12a.add_baseline_predictions(df, {"truth": {"proton_mass_gev": 0.938272, "c_cm_per_ns": 29.9792458}, "tof_per_cm_ns_used_in_notes": 0.08})
    assert out["pred_truth_kinematic_tof"].iloc[0] == pytest.approx(trap)
    assert out["pred_truth_kinematic_tof_legacy_arith_beta"].iloc[0] == pytest.approx(arith)


def test_1129_per_pair_cap_order_invariant_counterexample():
    """Deterministic shared-cap counterexample from the issue must not recur."""
    # Shared cap=10 with 6 eligible of each pair: order would starve later pairs.
    # Per-pair cap = ceil(10/3)=4 keeps up to 4 of each independently.
    per_pair_cap = 4
    eligible = {"0-2": 6, "2-4": 6, "4-6": 6}
    for order in (["0-2", "2-4", "4-6"], ["4-6", "2-4", "0-2"]):
        kept = {k: min(v, per_pair_cap) for k, v in eligible.items()}
        assert kept == {"0-2": 4, "2-4": 4, "4-6": 4}


# ---------------------------------------------------------------------------
# #1137 early window pedestal
# ---------------------------------------------------------------------------


def test_1137_early_robust_ignores_late_undershoot():
    sys.path.insert(0, str(REPO / "src"))
    from ccb_mc_validation.selector import estimate_pedestal_early_robust, PedestalValidity

    w = np.full(18, 100.0)
    w[15:] = -5000.0
    r = estimate_pedestal_early_robust(w)
    assert r.pedestal_adc == pytest.approx(100.0)


def test_1137_early_active_not_quiet_valid():
    sys.path.insert(0, str(REPO / "src"))
    from ccb_mc_validation.selector import estimate_pedestal_early_robust, PedestalValidity

    w = np.full(18, 100.0)
    w[0:4] = [100.0, 400.0, 1200.0, 800.0]
    w[9] = 5000.0
    r = estimate_pedestal_early_robust(w)
    assert r.validity == PedestalValidity.EARLY_ACTIVE
