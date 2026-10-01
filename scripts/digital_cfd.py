#!/usr/bin/env python3
"""Canonical digital constant-fraction discriminator (CFD) primitive.

All production timing studies must import from this module so left-censoring,
component-selection policy, and status codes stay synchronized (#1063).
"""
from __future__ import annotations

try:
    from typing import Literal
except ImportError:  # Python 3.7 compatibility for the analysis environment.
    from typing_extensions import Literal

import numpy as np

OK = "OK"
NO_CROSSING = "NO_CROSSING"
NO_CROSSING_IN_WINDOW = "NO_CROSSING_IN_WINDOW"
INVALID_AMPLITUDE = "INVALID_AMPLITUDE"
NONPOSITIVE_BRACKET = "NONPOSITIVE_BRACKET"

AmplitudeMode = Literal["global_max", "first_local_peak"]

FIRST_LOCAL_PEAK_SELECTOR_PROFILE = "first_local_peak_global_fraction_floor_v1"
FIRST_LOCAL_PEAK_SELECTOR_STATUS = "HYPOTHESIS_UNVALIDATED_COMPONENT_IDENTITY"
FIRST_LOCAL_PEAK_SELECTOR_AUTHORISING = False
FIRST_LOCAL_PEAK_DEFAULT_FLOOR_FRAC = 0.05

SELECT_LOCAL_ABOVE_GLOBAL_FLOOR = "FIRST_LOCAL_ABOVE_GLOBAL_FLOOR"
SELECT_FALLBACK_GLOBAL = "FALLBACK_GLOBAL_NO_ELIGIBLE_INTERIOR"
SELECT_INVALID = "INVALID_AMPLITUDE"


def first_local_peak_diagnostics(
    waveforms: np.ndarray,
    *,
    min_prominence_frac: float = FIRST_LOCAL_PEAK_DEFAULT_FLOOR_FRAC,
) -> dict[str, object]:
    """Return the exact selector state used by ``first_local_peak``.

    ``min_prominence_frac`` is retained for API compatibility, but the
    implemented quantity is *not* topographic peak prominence. It is a simple
    amplitude floor ``alpha * global_max``. The first interior sample satisfying
    the local-maximum inequalities and that floor is selected; if none exists,
    the selector silently collapses to the global maximum.

    The returned diagnostics intentionally expose that heuristic rather than
    interpreting the selected sample as a validated physical pulse component.
    """
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D (n_pulses, n_samples)")
    alpha = float(min_prominence_frac)
    if not np.isfinite(alpha) or not (0.0 <= alpha <= 1.0):
        raise ValueError("min_prominence_frac must be finite and in [0, 1]")

    n, n_samp = wave.shape
    selected_amplitudes = np.full(n, np.nan, dtype=float)
    selected_peak_indices = np.full(n, -1, dtype=int)
    global_amplitudes = np.full(n, np.nan, dtype=float)
    global_peak_indices = np.full(n, -1, dtype=int)
    selection_floors = np.full(n, np.nan, dtype=float)
    eligible_local_peak_counts = np.zeros(n, dtype=int)
    selected_to_global_ratio = np.full(n, np.nan, dtype=float)
    selected_plateau_member = np.zeros(n, dtype=bool)
    statuses = np.full(n, SELECT_INVALID, dtype=object)

    for i in range(n):
        y = wave[i]
        global_amp = float(np.max(y)) if y.size else float("nan")
        global_amplitudes[i] = global_amp
        if not np.isfinite(global_amp) or global_amp <= 0.0:
            selected_amplitudes[i] = global_amp
            continue

        global_index = int(np.argmax(y))
        global_peak_indices[i] = global_index
        floor = alpha * global_amp
        selection_floors[i] = floor

        eligible: list[int] = []
        for j in range(1, n_samp - 1):
            if y[j] >= y[j - 1] and y[j] >= y[j + 1] and y[j] >= floor:
                eligible.append(j)
        eligible_local_peak_counts[i] = len(eligible)

        if eligible:
            selected_index = int(eligible[0])
            status = SELECT_LOCAL_ABOVE_GLOBAL_FLOOR
        else:
            selected_index = global_index
            status = SELECT_FALLBACK_GLOBAL

        selected_amp = float(y[selected_index])
        selected_peak_indices[i] = selected_index
        selected_amplitudes[i] = selected_amp
        selected_to_global_ratio[i] = selected_amp / global_amp
        statuses[i] = status
        if 0 < selected_index < n_samp - 1:
            selected_plateau_member[i] = bool(
                y[selected_index] == y[selected_index - 1]
                or y[selected_index] == y[selected_index + 1]
            )

    return {
        "profile_id": FIRST_LOCAL_PEAK_SELECTOR_PROFILE,
        "evidence_status": FIRST_LOCAL_PEAK_SELECTOR_STATUS,
        "authorising_component_identity": FIRST_LOCAL_PEAK_SELECTOR_AUTHORISING,
        "global_fraction_floor": alpha,
        "selected_amplitudes": selected_amplitudes,
        "selected_peak_indices": selected_peak_indices,
        "global_amplitudes": global_amplitudes,
        "global_peak_indices": global_peak_indices,
        "selection_floors": selection_floors,
        "eligible_local_peak_counts": eligible_local_peak_counts,
        "selected_to_global_ratio": selected_to_global_ratio,
        "selected_plateau_member": selected_plateau_member,
        "statuses": statuses,
    }


def _first_local_peak_selection(
    waveforms: np.ndarray,
    *,
    min_prominence_frac: float = FIRST_LOCAL_PEAK_DEFAULT_FLOOR_FRAC,
) -> tuple[np.ndarray, np.ndarray]:
    """Return amplitudes and sample indices for the selected leading peak."""
    diagnostic = first_local_peak_diagnostics(
        waveforms,
        min_prominence_frac=min_prominence_frac,
    )
    return (
        np.asarray(diagnostic["selected_amplitudes"], dtype=float),
        np.asarray(diagnostic["selected_peak_indices"], dtype=int),
    )


def first_local_peak_amplitudes(
    waveforms: np.ndarray,
    *,
    min_prominence_frac: float = FIRST_LOCAL_PEAK_DEFAULT_FLOOR_FRAC,
) -> np.ndarray:
    """Amplitude of the first selected local maximum on each waveform.

    The legacy keyword name ``min_prominence_frac`` is misleading: the selector
    uses a global-amplitude fraction floor and does not calculate peak
    prominence. Diagnostics and authorization state are available through
    :func:`first_local_peak_diagnostics` (#1059).
    """
    amplitudes, _ = _first_local_peak_selection(
        waveforms,
        min_prominence_frac=min_prominence_frac,
    )
    return amplitudes


def resolve_amplitudes(
    waveforms: np.ndarray,
    amplitudes: np.ndarray | None,
    amplitude_mode: AmplitudeMode = "global_max",
) -> np.ndarray:
    wave = np.asarray(waveforms, dtype=float)
    if amplitude_mode == "global_max":
        if amplitudes is None:
            return np.max(wave, axis=1)
        return np.asarray(amplitudes, dtype=float)
    if amplitude_mode == "first_local_peak":
        return first_local_peak_amplitudes(wave)
    raise ValueError(f"unknown amplitude_mode: {amplitude_mode}")


def cfd_time_samples(
    waveforms: np.ndarray,
    amplitudes: np.ndarray | None = None,
    fraction: float = 0.2,
    *,
    amplitude_mode: AmplitudeMode = "global_max",
    return_status: bool = False,
):
    """Linear-interpolated constant-fraction crossing times in sample units.

    Left-censored crossings are reported as ``NO_CROSSING_IN_WINDOW`` with
    time ``nan`` (#1060); they are never coerced to ``t=0``.

    For ``first_local_peak`` the threshold and crossing are bound to the same
    selected pulse component (#1059): starting from that peak, the algorithm
    uses the nearest earlier below-threshold sample and interpolates the
    following bracket. Earlier above-threshold activity does not itself imply
    left-censoring if the waveform subsequently drops below threshold before
    the selected peak. ``global_max`` retains the historical first-crossing
    semantics.
    """
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D (n_pulses, n_samples)")
    frac = float(fraction)
    if not np.isfinite(frac) or not (0.0 < frac < 1.0):
        raise ValueError("fraction must be finite and in (0, 1)")

    component_peak_indices: np.ndarray | None = None
    if amplitude_mode == "first_local_peak":
        amp, component_peak_indices = _first_local_peak_selection(wave)
    else:
        amp = resolve_amplitudes(wave, amplitudes, amplitude_mode)
    if amp.shape != (wave.shape[0],):
        raise ValueError("amplitudes must have shape (n_pulses,)")

    n = wave.shape[0]
    times = np.full(n, np.nan, dtype=float)
    statuses = np.full(n, NO_CROSSING, dtype=object)

    for i in range(n):
        a = float(amp[i])
        if not np.isfinite(a) or a <= 0.0:
            statuses[i] = INVALID_AMPLITUDE
            continue
        thr = a * frac
        y = wave[i]

        if component_peak_indices is not None:
            peak_index = int(component_peak_indices[i])
            if peak_index < 0:
                statuses[i] = INVALID_AMPLITUDE
                continue
            below = np.flatnonzero(y[:peak_index] < thr)
            if below.size == 0:
                statuses[i] = NO_CROSSING_IN_WINDOW
                continue
            j = int(below[-1]) + 1
            if j > peak_index or y[j] < thr:
                statuses[i] = NO_CROSSING
                continue
            y0 = float(y[j - 1])
            y1 = float(y[j])
            denom = y1 - y0
            if denom <= 0.0:
                statuses[i] = NONPOSITIVE_BRACKET
                times[i] = float(j)
                continue
            times[i] = (j - 1) + (thr - y0) / denom
            statuses[i] = OK
            continue

        # Historical global-max semantics are retained as a separate explicit
        # estimator rather than silently redefined by the component-bound mode.
        if y[0] >= thr:
            statuses[i] = NO_CROSSING_IN_WINDOW
            continue
        ge = y >= thr
        if not np.any(ge):
            statuses[i] = NO_CROSSING
            continue
        j = int(np.argmax(ge))
        if j <= 0:
            statuses[i] = NO_CROSSING_IN_WINDOW
            continue
        y0 = float(y[j - 1])
        y1 = float(y[j])
        denom = y1 - y0
        if denom <= 0.0:
            statuses[i] = NONPOSITIVE_BRACKET
            times[i] = float(j)
            continue
        times[i] = (j - 1) + (thr - y0) / denom
        statuses[i] = OK

    if return_status:
        return times, statuses
    return times


def leading_edge_time_samples(
    waveforms: np.ndarray,
    threshold_adc: float,
    *,
    return_status: bool = False,
):
    """Fixed-threshold leading-edge timing with the same censoring contract."""
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D (n_pulses, n_samples)")
    thr = float(threshold_adc)
    if not np.isfinite(thr):
        raise ValueError("threshold_adc must be finite")
    n = wave.shape[0]
    times = np.full(n, np.nan, dtype=float)
    statuses = np.full(n, NO_CROSSING, dtype=object)
    for i in range(n):
        y = wave[i]
        if y[0] >= thr:
            statuses[i] = NO_CROSSING_IN_WINDOW
            continue
        ge = y >= thr
        if not np.any(ge):
            statuses[i] = NO_CROSSING
            continue
        j = int(np.argmax(ge))
        if j <= 0:
            statuses[i] = NO_CROSSING_IN_WINDOW
            continue
        y0 = float(y[j - 1])
        y1 = float(y[j])
        denom = y1 - y0
        if denom <= 0.0:
            statuses[i] = NONPOSITIVE_BRACKET
            times[i] = float(j)
            continue
        times[i] = (j - 1) + (thr - y0) / denom
        statuses[i] = OK
    if return_status:
        return times, statuses
    return times
