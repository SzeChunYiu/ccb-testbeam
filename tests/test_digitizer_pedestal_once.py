"""Regression tests for MV0 waveform-level electronics semantics."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline


def _pedestal_only_pipe() -> DigitizerPipeline:
    return DigitizerPipeline(
        electronics=ElectronicsConfig(
            gain_adc_per_mev=100.0,
            noise_adc_rms=0.0,
            adc_ceiling=7000,
            pedestal_adc=300.0,
        ),
        transport_sigma_ns=0.0,
    )


def test_zero_signal_multiple_hits_get_one_pedestal_realization() -> None:
    pipe = _pedestal_only_pipe()
    one = pipe.run([{"edep_mev": 0.0, "time_ns": 0.0}], event_id=123)["adc"]
    two = pipe.run(
        [
            {"edep_mev": 0.0, "time_ns": 0.0},
            {"edep_mev": 0.0, "time_ns": 5.0},
        ],
        event_id=123,
    )["adc"]

    np.testing.assert_array_equal(two, one)
    np.testing.assert_array_equal(two, np.full(pipe.n_samples, 300, dtype=np.int16))


def test_analog_hit_signals_add_before_single_quantization() -> None:
    pipe = _pedestal_only_pipe()
    one = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=456)["adc"].astype(float)
    two = pipe.run([{"edep_mev": 2.0, "time_ns": 0.0}], event_id=456)["adc"].astype(float)
    pair = pipe.run(
        [
            {"edep_mev": 1.0, "time_ns": 0.0},
            {"edep_mev": 1.0, "time_ns": 0.0},
        ],
        event_id=456,
    )["adc"].astype(float)

    np.testing.assert_array_equal(pair, two)
    np.testing.assert_allclose(pair - 300.0, 2.0 * (one - 300.0), atol=1.0)
