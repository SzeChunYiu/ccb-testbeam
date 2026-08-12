"""Deterministic nuisance-sensitivity controls for the first-local CFD selector."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import cfd_selector_sensitivity
import digital_cfd


def _selected_index(waveform: np.ndarray) -> int:
    diagnostics = digital_cfd.first_local_peak_diagnostics(
        np.asarray([waveform], dtype=float)
    )
    return int(diagnostics["selected_peak_indices"][0])


def test_linf_certificate_matches_near_floor_adversarial_switch():
    wave = np.asarray([0.0, 25.0, 49.9, 25.0, 0.0, 0.0, 500.0, 1000.0, 500.0])
    diagnostics = cfd_selector_sensitivity.first_local_peak_linf_stability_diagnostics(
        wave[None, :]
    )
    radius = float(diagnostics["identity_radius_adc"][0])
    expected = 0.1 / 1.05
    assert radius == pytest.approx(expected)
    assert _selected_index(wave) == 7

    below = 0.999 * expected
    above = 1.001 * expected
    wave_below = wave.copy()
    wave_below[2] += below
    wave_below[7] -= below
    wave_above = wave.copy()
    wave_above[2] += above
    wave_above[7] -= above
    assert _selected_index(wave_below) == 7
    assert _selected_index(wave_above) == 2


def test_common_mode_baseline_shift_can_change_selector_identity():
    wave = np.asarray([0.0, 20.0, 40.0, 20.0, 0.0, 0.0, 500.0, 1000.0, 500.0])
    alpha = digital_cfd.FIRST_LOCAL_PEAK_DEFAULT_FLOOR_FRAC
    # (40+b) = alpha*(1000+b) -> b = 10/(1-alpha).
    threshold = 10.0 / (1.0 - alpha)
    assert threshold == pytest.approx(10.526315789473685)
    assert _selected_index(wave + (threshold - 1e-8)) == 7
    assert _selected_index(wave + (threshold + 1e-8)) == 2


def test_clipping_later_global_peak_can_retarget_unchanged_early_peak():
    wave = np.asarray([0.0, 20.0, 40.0, 20.0, 0.0, 0.0, 500.0, 1000.0, 500.0])
    assert _selected_index(wave) == 7
    assert _selected_index(np.minimum(wave, 801.0)) == 7
    # At C=800 the global floor is 40, so the unchanged early 40-ADC peak is admitted.
    assert _selected_index(np.minimum(wave, 800.0)) == 2
    assert _selected_index(np.minimum(wave, 700.0)) == 2


def _triangle(samples: np.ndarray, *, center: float, amplitude: float, half_width: float):
    return amplitude * np.maximum(1.0 - np.abs(samples - center) / half_width, 0.0)


def _phase_fixture(phase: float) -> np.ndarray:
    sample = np.arange(16, dtype=float) + float(phase)
    early = _triangle(sample, center=3.2, amplitude=55.0, half_width=0.8)
    late = _triangle(sample, center=10.2, amplitude=1000.0, half_width=2.0)
    return early + late


def test_subsample_phase_scan_changes_discrete_component_assignment():
    expected = {0.0: 10, 0.2: 3, 0.5: 10, 0.8: 9}
    for phase, index in expected.items():
        assert _selected_index(_phase_fixture(phase)) == index

    # Deterministic support scan only. Counts are not a detector probability because
    # no physical sampling-phase distribution is assumed or fitted here.
    phases = np.linspace(0.0, 1.0, 1001, endpoint=False)
    indices = np.asarray([_selected_index(_phase_fixture(p)) for p in phases])
    unique, counts = np.unique(indices, return_counts=True)
    assert dict(zip(unique.tolist(), counts.tolist(), strict=True)) == {
        3: 229,
        9: 300,
        10: 472,
    }


def test_clean_high_margin_pulse_has_positive_sufficient_radius():
    wave = np.asarray([[0.0, 50.0, 100.0, 50.0, 0.0]])
    diagnostics = cfd_selector_sensitivity.first_local_peak_linf_stability_diagnostics(wave)
    assert diagnostics["selected_peak_indices"][0] == 2
    assert diagnostics["identity_radius_adc"][0] == pytest.approx(25.0)
    assert diagnostics["certificate_statuses"][0] == "LOCAL_SELECTED_SUFFICIENT_RADIUS"


def test_plateau_has_zero_exact_index_robustness_certificate():
    wave = np.asarray([[0.0, 50.0, 100.0, 100.0, 100.0, 50.0, 0.0]])
    diagnostics = cfd_selector_sensitivity.first_local_peak_linf_stability_diagnostics(wave)
    assert diagnostics["selected_peak_indices"][0] == 2
    assert diagnostics["identity_radius_adc"][0] == pytest.approx(0.0)
    assert diagnostics["selected_right_radius_adc"][0] == pytest.approx(0.0)


def test_monotonic_fallback_certificate_includes_argmax_gap():
    wave = np.asarray([[0.0, 10.0, 20.0, 30.0, 40.0]])
    diagnostics = cfd_selector_sensitivity.first_local_peak_linf_stability_diagnostics(wave)
    assert diagnostics["selected_peak_indices"][0] == 4
    assert diagnostics["selection_statuses"][0] == digital_cfd.SELECT_FALLBACK_GLOBAL
    assert diagnostics["argmax_radius_adc"][0] == pytest.approx(5.0)
    assert diagnostics["identity_radius_adc"][0] == pytest.approx(5.0)
