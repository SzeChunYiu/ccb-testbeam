"""Digitizer determinism: same event_id seed → identical 18-sample ADC."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline


def test_digitizer_same_seed_same_adc():
    pipe = DigitizerPipeline()
    hits = [{"edep_mev": 3.0, "time_ns": 5.0}]
    event_id = 12345
    a = pipe.run(hits, event_id=event_id)
    b = pipe.run(hits, event_id=event_id)
    assert a["adc"].shape == (18,)
    assert b["adc"].shape == (18,)
    np.testing.assert_array_equal(a["adc"], b["adc"])
    np.testing.assert_array_equal(a["saturated"], b["saturated"])


def test_digitizer_different_seed_different_adc():
    pipe = DigitizerPipeline()
    hits = [{"edep_mev": 3.0, "time_ns": 5.0}]
    a = pipe.run(hits, event_id=1)
    b = pipe.run(hits, event_id=2)
    assert not np.array_equal(a["adc"], b["adc"])
