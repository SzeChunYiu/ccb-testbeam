"""Tests for the #954 measured per-run polarity study.

Contract under test (issue #954 acceptance):
- sign-flipped synthetic truth is recovered by both the locked module and the
  independent MAD-vote estimator;
- low-SNR noise fails CLOSED (sign 0 / UNMEASURED, authorising False), never +1;
- single-sample low-word dropouts do not flip an established sign;
- amplitude extraction refuses UNKNOWN polarity;
- the locked v1 map is complete (all 8 channels +-1, even channels = B staves);
- stationarity aggregation is exact on synthetic per-run inputs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "real_data"))

import channel_polarity as cp  # noqa: E402
import issue_954_polarity_measurement as study  # noqa: E402

TRUTH = [1, -1, 1, -1, 1, -1, 1, -1]


# --- synthetic truth recovery (#954 negative controls) ---

def test_synthetic_truth_recovered_by_both_estimators():
    batch = study.toy_batch(TRUTH)
    pol, diag = cp.infer_channel_polarity(batch, study.BASELINE_SAMPLES)
    assert [int(pol[ch]) for ch in range(8)] == TRUTH
    assert all(diag["channels"][str(ch)]["authorising"] for ch in range(8))
    indep = study.independent_sign_stats(batch)
    assert [indep[str(ch)]["sign"] for ch in range(8)] == TRUTH


def test_sign_flipped_truth_recovered():
    batch = study.toy_batch([-s for s in TRUTH], seed=955)
    pol, _ = cp.infer_channel_polarity(batch, study.BASELINE_SAMPLES)
    assert [int(pol[ch]) for ch in range(8)] == [-s for s in TRUTH]


def test_low_snr_fails_closed_not_default_positive():
    noise = np.full((200, 8, 16), 5000.0)
    noise += np.random.default_rng(1).normal(0, 2.0, noise.shape)
    pol, diag = cp.infer_channel_polarity(noise, study.BASELINE_SAMPLES)
    assert all(pol[ch] == 0 for ch in range(8))
    # fail-closed accepts either closure status; what matters is pol=0 + non-authorising
    assert all(diag["channels"][str(ch)]["status"] in ("AMBIGUOUS", "UNMEASURED_LOW_SNR")
               for ch in range(8))
    assert all(not diag["channels"][str(ch)]["authorising"] for ch in range(8))


def test_dropout_does_not_flip_sign():
    batch = study.toy_batch(TRUTH, n_events=300, seed=956).copy()
    batch[:, 0::2, 9] = -16383.0  # low-word dropout on the positive channels
    pol, _ = cp.infer_channel_polarity(batch, study.BASELINE_SAMPLES)
    assert [int(pol[ch]) for ch in range(8)] == TRUTH
    indep = study.independent_sign_stats(batch)
    assert [indep[str(ch)]["sign"] for ch in range(8)] == TRUTH


def test_undershoot_does_not_flip_sign():
    # large slow undershoot after the pulse must not outvote the prompt peak
    batch = study.toy_batch(TRUTH, seed=957).copy()
    batch[:, 0::2, 14:] -= 300.0
    pol, _ = cp.infer_channel_polarity(batch, study.BASELINE_SAMPLES)
    assert [int(pol[ch]) for ch in range(8)] == TRUTH


# --- fail-closed extraction ---

def test_amplitude_refuses_unknown_polarity():
    w = np.arange(16, dtype=float)
    with pytest.raises(ValueError, match="must be ±1"):
        cp.apply_polarity(w.reshape(1, 1, 16), np.array([0.0]))


def test_polarity_for_channel_rejects_bad_map_values():
    m = cp.ChannelPolarityMap(
        version="t", sample_period_ns=10.0, baseline_samples=[0, 1, 2, 3],
        channel_polarity={"0": 0}, stave_channel={}, status="t", provenance={})
    with pytest.raises(ValueError, match="±1"):
        m.polarity_for_channel(0)


# --- locked map integrity ---

def test_v1_map_complete_and_even_channels_are_b_staves():
    m = cp.load_polarity_map(REPO_ROOT / "configs" / "channel_polarity_v1.json")
    assert m.status == "LOCKED_FROM_DUPLICATE_READOUT_CONVENTION"
    assert sorted(int(k) for k in m.channel_polarity) == list(range(8))
    assert all(m.polarity_for_channel(ch) in (-1, 1) for ch in range(8))
    assert m.stave_channel == {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
    # #869/#953 cross-validation: the four B-stave channels are the even ones
    assert [m.polarity_for_channel(m.stave_channel[s]) for s in ("B2", "B4", "B6", "B8")] == [1, 1, 1, 1]


# --- stationarity aggregation ---

def test_stationarity_detects_flip_and_ambiguity():
    def run_result(module_signs, indep_signs):
        return {
            "module": {str(ch): {"assigned": module_signs[ch]} for ch in range(8)},
            "independent": {str(ch): {"sign": indep_signs[ch]} for ch in range(8)},
        }
    stable = stationarity_over({"31": run_result(TRUTH, TRUTH), "32": run_result(TRUTH, TRUTH)})
    assert all(stable[str(ch)]["module_stationary"] and stable[str(ch)]["estimators_agree"]
               for ch in range(8))
    flipped = stationarity_over({"31": run_result(TRUTH, TRUTH), "32": run_result([-s for s in TRUTH], TRUTH)})
    assert not flipped["0"]["module_stationary"]
    assert not flipped["0"]["estimators_agree"]
    unmeasured = stationarity_over({"31": run_result([0] * 8, TRUTH)})
    assert not unmeasured["0"]["module_stationary"]


def stationarity_over(per_run):
    return study.stationarity(per_run)


def test_negative_controls_bundle_all_pass():
    c = study.negative_controls()
    assert c["synthetic_truth_recovered"]
    assert c["sign_flipped_truth_recovered"]
    assert c["low_snr_fails_closed"]
    assert c["dropout_does_not_flip_module"]
    assert c["dropout_does_not_flip_independent"]


# --- v2 measured map + builder gate (close-out) ---

V2_STATUS = "RETRACTED_20260816_TRUNCATED_STAGING_DESYNC"
MEASURED_MAP = {"0": 1, "1": -1, "2": -1, "3": 1, "4": -1, "5": 1, "6": -1, "7": 1}


def test_v2_map_file_retracted_with_forensic_record():
    data = json.loads((REPO_ROOT / "configs" / "channel_polarity_v2.json").read_text())
    assert data["status"] == V2_STATUS
    assert data["channel_polarity"] == MEASURED_MAP
    assert data["stave_channel"] == {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
    prov = data["provenance"]
    assert prov["audit_issue"] == 954
    ret = prov["retraction"]
    assert ret["audit_issues"] == [952, 953, 954]
    assert "128 WORDS" in ret["root_cause"] and "144-word" in ret["root_cause"]
    # The retraction voids the v1-falsification claim; v1 stays operative.
    v1 = json.loads((REPO_ROOT / "configs" / "channel_polarity_v1.json").read_text())
    assert v1["status"] == "LOCKED_FROM_DUPLICATE_READOUT_CONVENTION"
    assert set(prov["v1_falsified_for_channels"]) == {"2", "3", "4", "5", "6", "7"}
    assert prov["v1_confirmed_for_channels"] == ["0", "1"]


def test_v2_map_matches_measurement_result():
    result_path = REPO_ROOT / "reports/studies/paper_954_polarity/result.json"
    if not result_path.exists():
        pytest.skip("measurement result not generated")
    agreement = json.loads(result_path.read_text())["agreement_with_locked_map"]
    measured = {ch: row["measured_module"][0] for ch, row in agreement.items()}
    assert measured == MEASURED_MAP


def test_load_polarity_map_status_gate(tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "real_data"))
    import build_8x16_event_product as builder

    good = tmp_path / "good.json"
    for status in ("LOCKED_FROM_DUPLICATE_READOUT_CONVENTION",):
        good.write_text(json.dumps({"status": status, "channel_polarity": MEASURED_MAP}))
        assert builder.load_polarity_map(good) == MEASURED_MAP

    retracted = tmp_path / "retracted.json"
    retracted.write_text(json.dumps({"status": V2_STATUS, "channel_polarity": MEASURED_MAP}))
    with pytest.raises(ValueError, match="unresolved polarity"):
        builder.load_polarity_map(retracted)

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"status": "DRAFT", "channel_polarity": MEASURED_MAP}))
    with pytest.raises(ValueError, match="unresolved polarity"):
        builder.load_polarity_map(bad)


def test_falsification_json_v1_arm_reproduces_1318():
    path = REPO_ROOT / "reports/studies/paper_954_polarity/depth_profile_falsification.json"
    if not path.exists():
        pytest.skip("falsification artifact not generated")
    data = json.loads(path.read_text())["profiles"]["0"]
    assert data["I"]["v1"]["normalized"]["B2"] == pytest.approx(0.8740, abs=2e-4)
    assert data["II"]["v1"]["normalized"]["B2"] == pytest.approx(0.7267, abs=2e-4)
    # under the measured map the entrance-concentration claim must NOT hold
    assert data["I"]["meas_even"]["normalized"]["B2"] < 0.5
    assert data["II"]["meas_even"]["b8_over_b2"] > data["I"]["meas_even"]["b8_over_b2"]
