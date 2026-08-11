"""Atomic regressions for component-bound first-local-peak CFD timing (#1059)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import digital_cfd


def test_first_local_peak_crossing_is_bound_to_selected_component():
    """An earlier rejected bump must not provide the selected peak's crossing.

    Global max is 1000, so the 5% selection floor is 50.  The 40-ADC bump at
    sample 1 is intentionally rejected.  The first admitted local peak is
    100 ADC at sample 4; at CFD20 its threshold is 20 ADC.  The historical
    implementation scanned from sample 0 and returned 0.5 on the rejected
    40-ADC bump.  The component-bound estimator must instead use the rising
    bracket immediately before the selected 100-ADC component: samples 2->3,
    giving 2 + 20/50 = 2.4 samples.
    """
    wave = np.asarray(
        [[0.0, 40.0, 0.0, 50.0, 100.0, 50.0, 0.0, 0.0, 500.0, 1000.0, 500.0]],
        dtype=float,
    )
    amplitude = digital_cfd.first_local_peak_amplitudes(wave)
    assert amplitude[0] == pytest.approx(100.0)

    times, statuses = digital_cfd.cfd_time_samples(
        wave,
        None,
        0.2,
        amplitude_mode="first_local_peak",
        return_status=True,
    )
    assert statuses[0] == digital_cfd.OK
    assert times[0] == pytest.approx(2.4)
    assert times[0] != pytest.approx(0.5)


def test_component_bound_and_global_agree_for_clean_single_pulse():
    """Negative control: a clean unimodal pulse has one physical crossing."""
    wave = np.asarray([[0.0, 50.0, 100.0, 50.0, 0.0]], dtype=float)
    t_global = digital_cfd.cfd_time_samples(
        wave, None, 0.2, amplitude_mode="global_max"
    )
    t_component = digital_cfd.cfd_time_samples(
        wave, None, 0.2, amplitude_mode="first_local_peak"
    )
    assert t_global[0] == pytest.approx(0.4)
    assert t_component[0] == pytest.approx(t_global[0])


def test_global_max_estimator_keeps_historical_first_crossing_semantics():
    """The repair must not silently redefine the explicitly separate global CFD."""
    wave = np.asarray([[0.0, 40.0, 0.0, 50.0, 100.0, 50.0, 0.0, 0.0, 500.0, 1000.0, 500.0]])
    times = digital_cfd.cfd_time_samples(
        wave, None, 0.02, amplitude_mode="global_max"
    )
    # Global threshold is 20 ADC, so the historical first crossing is the
    # earlier 40-ADC bump at sample 0->1.
    assert times[0] == pytest.approx(0.5)
