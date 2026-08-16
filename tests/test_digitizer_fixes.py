"""Regression tests for confirmed digitizer defects DIG-001..DIG-007.

Each test block re-validates one finding from the audit against the current
code, locking in the fix so the defect cannot regress.
"""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.digitizer.birks import birks_quench
from ccb_mc_validation.digitizer.electronics import ElectronicsConfig, quantize_adc
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.digitizer.sampling import integrate_samples
from ccb_mc_validation.digitizer.scintillation import (
    exponential_kernel_cdf,
    exponential_kernel_pdf,
)

# numpy>=2 renamed trapz -> trapezoid; keep both for portability.
_trapezoid = getattr(np, "trapezoid", None) or np.trapz


# ===========================================================================
# DIG-001: hit time must not cancel out (time-translation invariance + causality)
# ===========================================================================
def test_dig001_time_translation_shifts_waveform_by_expected_amount():
    # Shifting t0 by k sample bins shifts the resulting charge profile by k bins.
    n, dt = 18, 10.0
    w0 = integrate_samples(1.0, t0_ns=0.0, n_samples=n, sample_spacing_ns=dt)
    w3 = integrate_samples(1.0, t0_ns=3 * dt, n_samples=n, sample_spacing_ns=dt)
    # A delay by 3 bins shifts the whole pulse 3 bins to the right: w3[k:] == w0[:n-k].
    np.testing.assert_allclose(w3[3:], w0[: n - 3], atol=1e-12)
    # The leading 3 bins of the delayed waveform are causally zero.
    np.testing.assert_array_equal(w3[:3], np.zeros(3))


def test_dig001_hit_time_changes_output():
    # Direct negation of the original bug: different t0 must give different output.
    a = integrate_samples(1.0, t0_ns=0.0)
    b = integrate_samples(1.0, t0_ns=30.0)
    assert not np.allclose(a, b)


def test_dig001_causality_bins_entirely_before_hit_are_zero():
    # t0=50ns, 10ns spacing: bins whose right edge <= 50ns (i.e. first 5 bins) are
    # fully before the hit and must carry zero charge.
    w = integrate_samples(1.0, t0_ns=50.0, n_samples=18, sample_spacing_ns=10.0)
    np.testing.assert_array_equal(w[:5], np.zeros(5))


def test_dig001_charge_is_non_negative():
    w = integrate_samples(2.5, t0_ns=4.0)
    assert (w >= 0).all()


# ===========================================================================
# DIG-002: proper normalized impulse (CDF/PDF), non-negativity, charge conservation
# ===========================================================================
def test_dig002_pdf_unit_integral():
    t = np.linspace(0, 2000, 400001)
    pdf = exponential_kernel_pdf(t, 2.0, 35.0)
    assert _trapezoid(pdf, t) == pytest.approx(1.0, abs=1e-6)


def test_dig002_pdf_non_negative():
    t = np.linspace(-10, 500, 100001)
    pdf = exponential_kernel_pdf(t, 2.0, 35.0)
    assert (pdf >= 0).all()


def test_dig002_cdf_monotonic_unit_asymptote_causal():
    t = np.linspace(-50, 2000, 200001)
    cdf = exponential_kernel_cdf(t, 2.0, 35.0)
    # Monotonic non-decreasing.
    assert (np.diff(cdf) >= -1e-12).all()
    # Causality: zero before t=0.
    assert cdf[0] == 0.0
    # Unit asymptote.
    assert cdf[-1] == pytest.approx(1.0, abs=1e-6)
    # Bounded into [0, 1].
    assert (cdf >= 0).all() and (cdf <= 1).all()


def test_dig002_cdf_matches_numerical_pdf_integral():
    tau_r, tau_d = 2.0, 35.0
    for T in [5.0, 20.0, 50.0, 200.0, 1000.0]:
        ts = np.linspace(0, T, 80001)
        numerical = _trapezoid(exponential_kernel_pdf(ts, tau_r, tau_d), ts)
        analytic = float(exponential_kernel_cdf(np.array([T]), tau_r, tau_d)[0])
        assert analytic == pytest.approx(numerical, abs=1e-4)


def test_dig002_integrate_samples_conserves_charge_over_wide_window():
    # A wide-enough window captures the whole pulse: sum -> edep_mev.
    big = integrate_samples(
        1.0,
        t0_ns=0.0,
        n_samples=4000,
        sample_spacing_ns=1.0,
        tau_rise_ns=2.0,
        tau_decay_ns=35.0,
    )
    assert big.sum() == pytest.approx(1.0, abs=1e-6)


def test_dig002_integrate_samples_non_negative():
    w = integrate_samples(1.0, t0_ns=0.0, n_samples=18, sample_spacing_ns=10.0)
    # Per-bin charge is a CDF difference, so it can never be negative.
    assert (w >= 0).all()


# ===========================================================================
# DIG-003: independent deterministic RNG streams per channel/stage
# ===========================================================================
def test_dig003_same_inputs_reproduce():
    pipe = DigitizerPipeline(global_seed=42)
    hits = [{"edep_mev": 3.0, "time_ns": 5.0}]
    a = pipe.run(hits, event_id=123, channel_id=7)
    b = pipe.run(hits, event_id=123, channel_id=7)
    np.testing.assert_array_equal(a["adc"], b["adc"])
    np.testing.assert_array_equal(a["saturated"], b["saturated"])


def test_dig003_different_channels_have_independent_noise():
    # Same event, two channels: electronics-noise realisations must differ.
    pipe = DigitizerPipeline(
        global_seed=42,
        transport_sigma_ns=0.0,
        electronics=ElectronicsConfig(noise_adc_rms=50.0),
    )
    hits = [{"edep_mev": 3.0, "time_ns": 5.0}]
    a = pipe.run(hits, event_id=123, channel_id=0)
    b = pipe.run(hits, event_id=123, channel_id=1)
    assert not np.array_equal(a["adc"], b["adc"])


def test_dig003_different_events_independent():
    pipe = DigitizerPipeline(global_seed=42)
    hits = [{"edep_mev": 3.0, "time_ns": 5.0}]
    a = pipe.run(hits, event_id=1)
    b = pipe.run(hits, event_id=2)
    assert not np.array_equal(a["adc"], b["adc"])


def test_dig003_per_stage_streams_are_independent():
    # The spawned child streams for distinct stages must produce uncorrelated draws.
    pipe = DigitizerPipeline(global_seed=1)
    rngs = pipe._stage_rngs(event_id=10, source_id=0, run_id=0, channel_id=4)
    draws_t = rngs["transport"].random(50)
    draws_e = rngs["electronics"].random(50)
    assert not np.allclose(draws_t, draws_e)


def test_dig003_channel_id_zero_is_defaulted_and_reproducible():
    pipe = DigitizerPipeline(global_seed=7)
    hits = [{"edep_mev": 1.0, "time_ns": 0.0}]
    explicit = pipe.run(hits, event_id=5, channel_id=0)
    implicit = pipe.run(hits, event_id=5)  # channel_id defaults to 0
    np.testing.assert_array_equal(explicit["adc"], implicit["adc"])


# ===========================================================================
# DIG-004: missing/non-finite hit fields fail closed with identifiers
# ===========================================================================
def test_dig004_missing_edep_fails_closed():
    pipe = DigitizerPipeline()
    with pytest.raises(ValueError, match=r"missing required field 'edep_mev'"):
        pipe.run([{"time_ns": 1.0}], event_id=1, channel_id=2)


def test_dig004_missing_time_fails_closed():
    pipe = DigitizerPipeline()
    with pytest.raises(ValueError, match=r"missing required field 'time_ns'"):
        pipe.run([{"edep_mev": 1.0}], event_id=1, channel_id=2)


def test_dig004_nonfinite_edep_fails_closed():
    pipe = DigitizerPipeline()
    with pytest.raises(ValueError, match="non-finite"):
        pipe.run([{"edep_mev": float("nan"), "time_ns": 0.0}], event_id=99)


def test_dig004_nonfinite_time_fails_closed():
    pipe = DigitizerPipeline()
    with pytest.raises(ValueError, match="non-finite"):
        pipe.run([{"edep_mev": 1.0, "time_ns": float("inf")}], event_id=99)


def test_dig004_error_message_contains_event_and_channel_ids():
    pipe = DigitizerPipeline()
    with pytest.raises(ValueError) as ei:
        pipe.run([{"time_ns": 1.0}], event_id=777, channel_id=3)
    msg = str(ei.value)
    assert "777" in msg
    assert "3" in msg


# ===========================================================================
# DIG-005: saturation flag matches the effective clipping threshold
# ===========================================================================
def test_dig005_flag_matches_clip_when_ceiling_above_full_scale():
    # adc_ceiling=7000 > full_scale=4095 (12-bit): effective ceiling is 4095 and
    # the saturation flag must follow that, not the raw adc_ceiling.
    cfg = ElectronicsConfig(adc_bits=12, adc_ceiling=7000)
    q, sat = quantize_adc(np.array([5000.0, 4094.0, 4095.1, 4096.0]), cfg)
    # 5000 > effective 4095 -> saturated
    assert bool(sat[0]) is True
    # 4094 within range -> not saturated
    assert bool(sat[1]) is False
    # 4095.1 and 4096 > effective 4095 -> saturated
    assert bool(sat[2]) is True
    assert bool(sat[3]) is True
    # And the clipped value never exceeds the effective ceiling.
    assert int(q.max()) <= 4095


def test_dig005_no_false_saturation_below_ceiling():
    # full_scale=16383 (14-bit) > adc_ceiling=7000: flag follows effective=7000.
    cfg = ElectronicsConfig(adc_bits=14, adc_ceiling=7000)
    _, sat = quantize_adc(np.array([6999.0, 7000.0, 7001.0]), cfg)
    assert bool(sat[0]) is False
    assert bool(sat[1]) is False  # exactly at ceiling is not saturated
    assert bool(sat[2]) is True


# ===========================================================================
# DIG-006: ADC dtype follows configured bit width; finite + legal range enforced
# ===========================================================================
@pytest.mark.parametrize(
    "bits,expected",
    # Smallest SIGNED dtype whose positive range holds 0..2**bits - 1:
    # int8 reaches 127 (<=7-bit ADCs), int16 reaches 32767 (8..15-bit ADCs),
    # int32 for 16..31-bit, int64 for 32..63-bit.
    [(4, np.int8), (7, np.int8), (8, np.int16), (14, np.int16), (16, np.int32), (32, np.int64)],
)
def test_dig006_dtype_follows_adc_bits(bits, expected):
    cfg = ElectronicsConfig(adc_bits=bits, adc_ceiling=(1 << bits) - 1)
    q, _ = quantize_adc(np.array([42.0]), cfg)
    assert q.dtype == np.dtype(expected)


def test_dig006_rejects_nonfinite_input():
    cfg = ElectronicsConfig()
    with pytest.raises(ValueError, match="non-finite"):
        quantize_adc(np.array([100.0, np.inf]), cfg)


def test_dig006_rejects_invalid_bit_width():
    with pytest.raises(ValueError):
        quantize_adc(np.array([1.0]), ElectronicsConfig(adc_bits=0))


# ===========================================================================
# DIG-007: Birks requires step length / dE/dx (no dimensional shortcut)
# ===========================================================================
def test_dig007_birks_requires_step_info():
    with pytest.raises(ValueError, match=r"step_length_cm|dedx_mev_per_cm"):
        birks_quench(1.0)


def test_dig007_birks_rejects_both_step_and_dedx():
    with pytest.raises(ValueError, match="exactly one"):
        birks_quench(1.0, step_length_cm=1.0, dedx_mev_per_cm=1.0)


def test_dig007_birks_with_step_length():
    # E=1, dx=1cm -> dedx=1 MeV/cm; k_B=0.008 cm/MeV -> L = 1/(1+0.008).
    val = birks_quench(1.0, step_length_cm=1.0, k_b_cm_per_mev=0.008)
    assert val == pytest.approx(1.0 / 1.008, abs=1e-12)


def test_dig007_birks_with_explicit_dedx():
    val = birks_quench(2.0, dedx_mev_per_cm=10.0, k_b_cm_per_mev=0.008)
    assert val == pytest.approx(2.0 / (1.0 + 0.08), abs=1e-12)


def test_dig007_explicit_dedx_matches_step_length():
    # E=2, dx=0.5cm -> dedx=4 MeV/cm, same as passing dedx_mev_per_cm=4 directly.
    a = birks_quench(2.0, step_length_cm=0.5, k_b_cm_per_mev=0.01)
    b = birks_quench(2.0, dedx_mev_per_cm=4.0, k_b_cm_per_mev=0.01)
    assert a == pytest.approx(b, abs=1e-12)


def test_dig007_pipeline_birks_stage_fails_closed_without_step_info():
    pipe = DigitizerPipeline(apply_birks=True, birks_kB_cm_per_MeV=0.008)
    with pytest.raises(ValueError, match="birks stage cannot run"):
        pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=5)


def test_dig007_pipeline_birks_runs_when_step_length_provided():
    pipe = DigitizerPipeline(
        apply_birks=True,
        birks_kB_cm_per_MeV=0.008,
        transport_sigma_ns=0.0,
        electronics=ElectronicsConfig(noise_adc_rms=0.0, gain_adc_per_mev=1.0, pedestal_adc=0.0),
    )
    out = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0, "step_length_cm": 1.0}], event_id=5)
    assert out["adc"].shape == (18,)
