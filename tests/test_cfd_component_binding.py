"""Atomic regressions for component-bound CFD and selector identity (#1059)."""
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


def test_component_bound_censoring_is_relative_to_selected_component():
    wave = np.asarray(
        [[30.0, 0.0, 50.0, 100.0, 50.0, 0.0, 250.0, 500.0, 250.0]],
        dtype=float,
    )
    times, statuses = digital_cfd.cfd_time_samples(
        wave,
        None,
        0.2,
        amplitude_mode="first_local_peak",
        return_status=True,
    )
    assert statuses[0] == digital_cfd.OK
    assert times[0] == pytest.approx(1.4)


def test_component_bound_and_global_agree_for_clean_single_pulse():
    wave = np.asarray([[0.0, 50.0, 100.0, 50.0, 0.0]], dtype=float)
    t_global = digital_cfd.cfd_time_samples(
        wave, None, 0.2, amplitude_mode="global_max"
    )
    t_component = digital_cfd.cfd_time_samples(
        wave, None, 0.2, amplitude_mode="first_local_peak"
    )
    assert t_global[0] == pytest.approx(0.4)
    assert t_component[0] == pytest.approx(t_global[0])


def test_component_bound_is_left_censored_only_if_selected_rise_is_unseen():
    wave = np.asarray([[30.0, 40.0, 100.0, 50.0, 0.0]], dtype=float)
    times, statuses = digital_cfd.cfd_time_samples(
        wave,
        None,
        0.2,
        amplitude_mode="first_local_peak",
        return_status=True,
    )
    assert statuses[0] == digital_cfd.NO_CROSSING_IN_WINDOW
    assert not np.isfinite(times[0])


def test_global_max_estimator_keeps_historical_first_crossing_semantics():
    wave = np.asarray(
        [[0.0, 40.0, 0.0, 50.0, 100.0, 50.0, 0.0, 0.0, 500.0, 1000.0, 500.0]]
    )
    times = digital_cfd.cfd_time_samples(
        wave, None, 0.02, amplitude_mode="global_max"
    )
    assert times[0] == pytest.approx(0.5)


def test_selector_exposes_global_fraction_floor_not_prominence():
    """A one-ADC-prominence early peak passes the global-height floor.

    Global max is 1000, so alpha=0.05 sets a 50-ADC absolute-height floor.
    The early peak is 51 ADC. Its left basin minimum is 0, but before the first
    higher peak to the right the basin minimum is 50, so the higher base is 50
    and the topographic prominence is only 1 ADC. The selector still admits it.
    """
    wave = np.asarray(
        [[0.0, 50.0, 51.0, 50.0, 50.0, 500.0, 1000.0, 500.0]],
        dtype=float,
    )
    diagnostic = digital_cfd.first_local_peak_diagnostics(wave)
    assert diagnostic["profile_id"] == "first_local_peak_global_fraction_floor_v1"
    assert diagnostic["authorising_component_identity"] is False
    assert diagnostic["selected_peak_indices"][0] == 2
    assert diagnostic["selected_amplitudes"][0] == pytest.approx(51.0)
    assert diagnostic["selection_floors"][0] == pytest.approx(50.0)
    assert diagnostic["selected_to_global_ratio"][0] == pytest.approx(0.051)

    # For this fixture the first higher point to the right is sample 5 (500).
    left_base = float(np.min(wave[0, :2]))
    right_base = float(np.min(wave[0, 3:5]))
    prominence = 51.0 - max(left_base, right_base)
    assert prominence == pytest.approx(1.0)
    assert prominence < diagnostic["selection_floors"][0]


def test_selector_has_discontinuous_identity_at_global_floor_boundary():
    """A 0.2-ADC perturbation can flip the selected component at the 5% floor."""
    wave = np.asarray(
        [
            [0.0, 25.0, 49.9, 25.0, 0.0, 0.0, 500.0, 1000.0, 500.0],
            [0.0, 25.0, 50.1, 25.0, 0.0, 0.0, 500.0, 1000.0, 500.0],
        ],
        dtype=float,
    )
    diagnostic = digital_cfd.first_local_peak_diagnostics(wave)
    assert list(diagnostic["selected_peak_indices"]) == [7, 2]
    assert list(diagnostic["statuses"]) == [
        digital_cfd.SELECT_LOCAL_ABOVE_GLOBAL_FLOOR,
        digital_cfd.SELECT_LOCAL_ABOVE_GLOBAL_FLOOR,
    ]
    assert diagnostic["selected_to_global_ratio"][0] == pytest.approx(1.0)
    assert diagnostic["selected_to_global_ratio"][1] == pytest.approx(0.0501)


def test_selector_reports_plateau_and_multiple_eligible_local_maxima():
    wave = np.asarray([[0.0, 50.0, 100.0, 100.0, 100.0, 50.0, 0.0]])
    diagnostic = digital_cfd.first_local_peak_diagnostics(wave)
    assert diagnostic["selected_peak_indices"][0] == 2
    assert diagnostic["eligible_local_peak_counts"][0] == 3
    assert bool(diagnostic["selected_plateau_member"][0])


def test_selector_reports_silent_fallback_to_boundary_global_peak():
    wave = np.asarray([[0.0, 10.0, 20.0, 30.0, 40.0]])
    diagnostic = digital_cfd.first_local_peak_diagnostics(wave)
    assert diagnostic["selected_peak_indices"][0] == 4
    assert diagnostic["eligible_local_peak_counts"][0] == 0
    assert diagnostic["statuses"][0] == digital_cfd.SELECT_FALLBACK_GLOBAL


def test_selector_rejects_out_of_domain_or_nonfinite_floor_fraction():
    wave = np.asarray([[0.0, 1.0, 0.0]])
    for alpha in (-0.1, 1.1, np.nan, np.inf):
        with pytest.raises(ValueError, match=r"finite and in \[0, 1\]"):
            digital_cfd.first_local_peak_diagnostics(
                wave,
                min_prominence_frac=alpha,
            )
