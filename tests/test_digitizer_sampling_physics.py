"""Physics regression tests for the digitizer sampling stage.

These guard the 2026-07-03 fix of integrate_samples (hit time previously
cancelled exactly and the peak-normalized kernel was diffed instead of its
cumulative integral, producing a one-sample spike followed by negative
samples). See EXTERNAL_REVIEW_2026-07-02.md.
"""

import numpy as np
import pytest

from ccb_mc_validation.digitizer.sampling import integrate_samples
from ccb_mc_validation.digitizer.scintillation import exponential_kernel_cdf


def test_samples_are_non_negative():
    light = integrate_samples(10.0, t0_ns=30.0)
    assert np.all(light >= 0.0)


def test_shifting_t0_shifts_the_peak_sample():
    peaks = [int(np.argmax(integrate_samples(10.0, t0_ns=t0))) for t0 in (0.0, 50.0, 100.0)]
    assert peaks[0] < peaks[1] < peaks[2]


def test_distinct_t0_produce_distinct_waveforms():
    a = integrate_samples(10.0, t0_ns=50.0)
    b = integrate_samples(10.0, t0_ns=55.0)
    assert not np.allclose(a, b)


def test_contained_pulse_integral_closes_to_edep():
    # t0 early in the window, decay 35 ns: >97% of light within the remaining
    # 160 ns; allow the small out-of-window tail.
    edep = 7.5
    light = integrate_samples(edep, t0_ns=20.0)
    assert light.sum() == pytest.approx(edep, rel=0.03)


def test_sub_bin_t0_moves_light_between_bins():
    a = integrate_samples(10.0, t0_ns=40.0)
    b = integrate_samples(10.0, t0_ns=45.0)
    assert int(np.argmax(a)) == int(np.argmax(b) )or not np.allclose(a, b)
    assert not np.allclose(a, b)


def test_cdf_is_monotone_and_normalized():
    t = np.linspace(-10.0, 500.0, 2000)
    cdf = exponential_kernel_cdf(t, tau_rise_ns=2.0, tau_decay_ns=35.0)
    assert np.all(np.diff(cdf) >= -1e-12)
    assert cdf[t < 0].max(initial=0.0) == 0.0
    assert cdf[-1] == pytest.approx(1.0, abs=1e-4)


def test_pipeline_channels_get_independent_noise():
    from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline

    pipe = DigitizerPipeline()
    hits = [{"edep_mev": 5.0, "time_ns": 30.0}]
    w0 = pipe.run(hits, event_id=7, channel=0)["adc"]
    w1 = pipe.run(hits, event_id=7, channel=1)["adc"]
    assert not np.array_equal(w0, w1)
    # determinism per (event, channel) still holds
    w0b = pipe.run(hits, event_id=7, channel=0)["adc"]
    assert np.array_equal(w0, w0b)
