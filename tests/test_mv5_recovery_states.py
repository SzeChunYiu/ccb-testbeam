"""Regression tests for ARU-MV5-RECOVERY-FAILURE-SEMANTICS-001 (#1118).

The defect: ``recover_two_pulse`` collapses "no second pulse detected" and
"valid zero-separation estimate" into the same numeric sentinel ``rec_sep=0``.
The caller then counts a miss as success whenever ``|0 - dt_true| < 30 ns``, so
a missed second pulse at ``dt_true < 30 ns`` is falsely credited as resolved.

Fix: recovery returns a *typed* state first, and the scientific failure rule is
``state != RESOLVED_VALID`` OR ``|dt_hat - dt_true| > epsilon`` (state checked
before numeric error). This removes the artificial 30 ns discontinuity.

These tests exercise the pure helpers only (``sim_waveform``, ``clip_adc``,
``recover_two_pulse``); they do not need the MV5 truth tracks or a full run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "mv5_pileup_study.py"

# Load the module at module level so all helper functions can reference it.
if not SCRIPT_PATH.exists():
    pytest.skip(f"{SCRIPT_PATH} not found", allow_module_level=True)
spec = importlib.util.spec_from_file_location("mv5_recovery_states", SCRIPT_PATH)
mv = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mv
spec.loader.exec_module(mv)  # type: ignore[union-attr]

#: Physical constants mirrored from the script (kept local so a regression in
#: the script's own constants cannot silently change what these tests assert).
PED = 350.0
DT = 10.0  # ns / sample
EPSILON = 30.0  # allowed recovered-vs-truth separation error (ERR_FAIL_NS)


# ---------------------------------------------------------------------------
# Recovery-state universe (the typed contract #1118 requires)
# ---------------------------------------------------------------------------


def test_recovery_states_are_typed_and_exhaustive():
    """The recovery result must be a typed object whose state distinguishes a
    valid two-pulse resolution from a missed second pulse (no numeric collapse)."""
    res = mv.recover_two_pulse(np.full(mv.NSAMP, float(PED)))  # flat, no pulse
    assert res.state == mv.RecoveryState.NO_PULSE
    assert res.n_candidates == 0
    assert res.dt_hat_ns is None  # no numeric partition that could fake a value


def _single_peak_wave(rng, edep_mev=1.0, time_ns=20.0):
    """A deliberate single-pulse waveform (one rising edge -> one candidate)."""
    wave = mv.sim_waveform(edep_mev, time_ns, rng, with_noise=False)
    return mv.clip_adc(wave)


def _peaks(wave):
    return mv.find_rising_peaks(wave)


# ---------------------------------------------------------------------------
# Discriminating one-peak tests (10 / 29.9 / 30.1 ns) -- the discontinuity
# CURRENT code exhibits: a missed second pulse at dt_true < 30 ns is counted as
# success because rec_sep=0 sits numerically close to truth.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dt_true", [10.0, 29.9, 30.1])
def test_single_peak_miss_is_not_resolved_valid(dt_true):
    """A waveform that yields fewer than two candidates must NOT be credited as
    successful two-pulse recovery, regardless of how close dt_true sits to the
    ``rec_sep=0`` sentinel. This is the core S00-…-001 acceptance criterion."""
    rng = np.random.default_rng(42)
    wave = _single_peak_wave(rng)
    assert len(_peaks(wave)) < 2  # detection invariant: only ONE candidate present
    res = mv.recover_two_pulse(wave)
    assert res.state != mv.RecoveryState.RESOLVED_VALID
    # And the failure rule must trip on STATE first, not numeric error.
    assert mv.recovery_is_failure(res, dt_true=dt_true) is True


def test_single_peak_miss_no_30ns_discontinuity():
    """The three one-peak cases must all be failures with NO discontinuity at
    the 30 ns boundary: 10, 29.9 and 30.1 ns are indistinguishable when the
    second pulse is simply absent."""
    outcomes = [
        mv.recovery_is_failure(mv.recover_two_pulse(_single_peak_wave(np.random.default_rng(42))), dt_true=d)
        for d in (10.0, 29.9, 30.1)
    ]
    assert outcomes == [True, True, True], "no artificial 30 ns discontinuity"


# ---------------------------------------------------------------------------
# Positive / accuracy controls
# ---------------------------------------------------------------------------


def _two_peak_wave(rng, sep_ns, edep_a=1.0, edep_b=1.0, t0_ns=20.0):
    """Two well-separated pulses at physical separation ``sep_ns``."""
    w1 = mv.sim_waveform(edep_a, t0_ns, rng, with_noise=False)
    w2 = mv.sim_waveform(edep_b, t0_ns + sep_ns, rng, with_noise=False)
    return mv.clip_adc(w1 + w2 - PED)


def test_two_clean_peaks_50ns_resolves():
    """Perfect-separation limit: two high-SNR peaks at 50 ns must resolve to a
    valid estimate with dt_hat ~ dt_true (invariant 2)."""
    rng = np.random.default_rng(7)
    wave = _two_peak_wave(rng, sep_ns=50.0)
    assert len(_peaks(wave)) >= 2
    res = mv.recover_two_pulse(wave)
    assert res.state == mv.RecoveryState.RESOLVED_VALID
    assert res.dt_hat_ns is not None
    assert abs(res.dt_hat_ns - 50.0) < 1e-6
    assert mv.recovery_is_failure(res, dt_true=50.0) is False


def test_two_peaks_40ns_error_resolved_but_failed():
    """Two peaks ARE resolved (state=RESOLVED_VALID) but the recovered
    separation carries a 40 ns error -> accuracy-failed. State and error are
    decoupled: a valid resolution can still fail on accuracy."""
    rng = np.random.default_rng(11)
    # Truth separation 50 ns, but the recovered separation is forced to 90 ns
    # (9 samples) by constructing well-separated edges 90 ns apart.
    wave = _two_peak_wave(rng, sep_ns=90.0)
    assert len(_peaks(wave)) >= 2
    res = mv.recover_two_pulse(wave)
    assert res.state == mv.RecoveryState.RESOLVED_VALID
    assert abs(res.dt_hat_ns - 90.0) < 1e-6
    # 40 ns error vs truth 50 ns -> accuracy failure, even though state resolved.
    assert abs(res.dt_hat_ns - 50.0) > EPSILON
    assert mv.recovery_is_failure(res, dt_true=50.0) is True


# ---------------------------------------------------------------------------
# Negative controls: ambiguity / saturation must not yield a fake zero
# ---------------------------------------------------------------------------


def test_saturated_merged_pulse_is_not_precise_zero():
    """A merged/saturated pulse must not silently become a precise zero-separation
    estimate (invariant 3 / discriminating test 7). If only one candidate is
    recoverable, the state must be UNRESOLVED, not RESOLVED_VALID with dt_hat=0."""
    rng = np.random.default_rng(3)
    # Two arrivals at the SAME time -> a single merged pulse (one rising edge).
    w1 = mv.sim_waveform(1.0, 20.0, rng, with_noise=False)
    w2 = mv.sim_waveform(1.0, 20.0, rng, with_noise=False)
    wave = mv.clip_adc(w1 + w2 - PED)
    assert len(_peaks(wave)) < 2
    res = mv.recover_two_pulse(wave)
    assert res.state != mv.RecoveryState.RESOLVED_VALID
    assert res.dt_hat_ns is None


def test_three_peaks_is_ambiguous_not_resolved():
    """Three candidates hit an explicit ambiguity policy (discriminating test 6):
    >2 candidates must not be collapsed to a single RESOLVED_VALID estimate."""
    rng = np.random.default_rng(5)
    w1 = mv.sim_waveform(1.0, 20.0, rng, with_noise=False)
    w2 = mv.sim_waveform(1.0, 40.0, rng, with_noise=False)
    w3 = mv.sim_waveform(1.0, 80.0, rng, with_noise=False)
    wave = mv.clip_adc(w1 + w2 + w3 - 2.0 * PED)
    assert len(_peaks(wave)) >= 3
    res = mv.recover_two_pulse(wave)
    assert res.state == mv.RecoveryState.AMBIGUOUS_MULTIPLE
    assert mv.recovery_is_failure(res, dt_true=40.0) is True