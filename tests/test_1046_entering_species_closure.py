"""Tests for the #1046 entering-species paper-result closure.

Contract under test (issue #1046 acceptance):
- the producer emits H2 (unique-track flux), H3 (event-presence) and H4
  (EDep-contribution) compositions as SEPARATE annotated blocks -- a species
  fraction without its estimator is not a well-defined observable;
- H2 fractions carry an event-level bootstrap CI (MC event = sampling unit);
- the committed 2M-campaign result is provenance-bound and internally
  consistent.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import mc01_trigger_split_truth as producer  # noqa: E402

RESULT = (REPO_ROOT / "reports/issue_1046_entering_species"
          / "cmc_2m_regenerated_20260814/mc_trigger_split_summary.json")
PROV = REPO_ROOT / "reports/issue_1046_entering_species/provenance.json"


# --- unit: event-level bootstrap ---

def test_bootstrap_point_is_exact_fraction():
    records = [{"B": {"d": 3, "p": 1}}, {"B": {"d": 1, "p": 1}}, {"B": {"d": 2}}]
    out = producer.bootstrap_enter_fractions(records)
    assert out["B"]["point_fraction"]["d"] == pytest.approx(6 / 8)
    assert out["B"]["point_fraction"]["p"] == pytest.approx(2 / 8)


def test_bootstrap_deterministic_and_brackets_point():
    records = [{"B": {"d": 1, "p": 0}}, {"B": {"d": 0, "p": 1}}] * 10
    a = producer.bootstrap_enter_fractions(records, n_boot=200)
    b = producer.bootstrap_enter_fractions(records, n_boot=200)
    assert a == b  # seed-bound determinism
    for lab, pt in a["B"]["point_fraction"].items():
        lo, hi = a["B"]["ci68"][lab]
        assert lo <= pt <= hi


def test_bootstrap_single_species_degenerate():
    out = producer.bootstrap_enter_fractions([{"B": {"d": 2}}] * 5)
    assert out["B"]["point_fraction"]["d"] == 1.0
    assert out["B"]["ci68"]["d"] == [1.0, 1.0]


def test_bootstrap_empty_arm_absent():
    out = producer.bootstrap_enter_fractions([{"B": {"d": 1}}])
    assert "B" in out and "A" not in out


# --- integration: committed 2M campaign result ---

@pytest.fixture(scope="module")
def result():
    if not RESULT.exists():
        pytest.skip("2M campaign result not present")
    return json.loads(RESULT.read_text())


def test_estimator_blocks_separate_and_annotated(result):
    for s in ("I", "II"):
        S = result["samples"][s]
        assert S["enter_pid_statistical_unit"] == "unique_truth_track"
        for arm in ("B", "A"):
            h2 = S[f"enter_{arm}_pid_fraction"]
            h3 = S[f"enter_{arm}_pid_fraction_event_presence"]
            h4 = S[f"enter_{arm}_pid_fraction_edep"]
            assert h3["statistical_unit"] == "event_presence"
            assert h4["statistical_unit"] == "deposited_energy"
            for blk in (h2, h3["fractions"], h4["fractions"]):
                assert abs(sum(blk.values()) - 1.0) < 0.01


def test_bootstrap_consistent_with_point(result):
    for s in ("I", "II"):
        b = result["samples"][s]["enter_pid_bootstrap"]
        assert b["estimator"] == "unique_truth_track (H2)"
        assert b["n_boot"] == 1000 and b["seed"] == 1046 and b["ci_level"] == 68
        for arm in ("B", "A"):
            for lab, pt in b[arm]["point_fraction"].items():
                lo, hi = b[arm]["ci68"][lab]
                assert lo - 1e-9 <= pt <= hi + 1e-9
                if pt > 0.005:  # bootstrap point reproduces the plain H2 fraction
                    assert pt == pytest.approx(
                        result["samples"][s][f"enter_{arm}_pid_fraction"][lab], abs=1e-4)


def test_sample_structure_and_unit_weights(result):
    assert result["n_events_read"] == 2_000_000
    assert result["samples"]["II"]["n_events"] > result["samples"]["I"]["n_events"] > 0
    for s in ("I", "II"):
        S = result["samples"][s]
        # MODE_DIRECT_UNIT: weighted estimator identical to unweighted
        assert S["enter_B_pid_fraction"] == S["enter_B_pid_fraction_weighted"]
        # B-arm bootstrap resamples every sample event (enterB defines membership)
        assert S["enter_pid_bootstrap"]["B"]["n_events_bootstrapped"] == S["n_events"]


def test_provenance_binds_producer_input_campaign():
    if not PROV.exists():
        pytest.skip("provenance manifest not present")
    p = json.loads(PROV.read_text())
    assert p["campaign_id"] == "cmc_2m_regenerated_20260814"
    assert p["input"]["sha256"] == "0d8c827502b3ce8f5bbe419e1c11a2905db55015b94a741a11ec7e52f292afe1"
    assert p["input"]["n_events"] == 2_000_000 and p["input"]["random_seed"] == 3500420
    assert p["producer"]["path"] == "scripts/mc01_trigger_split_truth.py"
    script = REPO_ROOT / p["producer"]["path"]
    assert hashlib.sha256(script.read_bytes()).hexdigest() == p["producer"]["sha256"]
    assert p["gating"]["status"] == "GATED" and 1045 in p["gating"]["blocked_by"]
