#!/usr/bin/env python3
"""Canonical digital constant-fraction discriminator (CFD) primitive.

All production timing studies must import from this module so left-censoring,
component-selection policy, and status codes stay synchronized (#1063).
"""
from __future__ import annotations

from typing import Literal

import numpy as np

OK = "OK"
NO_CROSSING = "NO_CROSSING"
NO_CROSSING_IN_WINDOW = "NO_CROSSING_IN_WINDOW"
INVALID_AMPLITUDE = "INVALID_AMPLITUDE"
NONPOSITIVE_BRACKET = "NONPOSITIVE_BRACKET"

AmplitudeMode = Literal["global_max", "first_local_peak"]


def _first_local_peak_selection(
    waveforms: np.ndarray,
    *,
    min_prominence_frac: float = 0.05,
) -> tuple[np.ndarray, np.ndarray]:
    """Return amplitudes and sample indices for the selected leading peak.

    The selection rule intentionally preserves the existing #1059 reduced
    model: choose the first interior local maximum above
    ``min_prominence_frac * global_max`` and fall back to the global maximum
    if no such interior peak exists. Returning the peak index as well as its
    amplitude lets the CFD crossing be bound to the same pulse component
    rather than scanning an earlier, rejected bump against the selected
    component's threshold.
    """
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D (n_pulses, n_samples)")
    n, n_samp = wave.shape
    amplitudes = np.empty(n, dtype=float)
    peak_indices = np.full(n, -1, dtype=int)
    for i in range(n):
        y = wave[i]
        global_amp = float(np.max(y)) if y.size else float("nan")
        if not np.isfinite(global_amp) or global_amp <= 0:
            amplitudes[i] = global_amp
            continue
        global_index = int(np.argmax(y))
        floor = min_prominence_frac * global_amp
        chosen_amp = global_amp
        chosen_index = global_index
        for j in range(1, n_samp - 1):
            if y[j] >= y[j - 1] and y[j] >= y[j + 1] and y[j] >= floor:
                chosen_amp = float(y[j])
                chosen_index = j
                break
        amplitudes[i] = chosen_amp
        peak_indices[i] = chosen_index
    return amplitudes, peak_indices


def first_local_peak_amplitudes(waveforms: np.ndarray, *, min_prominence_frac: float = 0.05) -> np.ndarray:
    """Amplitude of the first selected local maximum on each waveform.

    Used to reduce global-max component switching (#1059): CFD thresholds are
    formed from the leading pulse component rather than a later taller peak.
    Falls back to the global maximum when no interior local peak exists.
    """
    amplitudes, _ = _first_local_peak_selection(
        waveforms, min_prominence_frac=min_prominence_frac
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
            # Bind the crossing to the selected component: among samples before
            # its peak, take the last point below threshold. The following
            # sample is therefore the rising bracket nearest that selected peak.
            # If no such below-threshold sample exists, the selected component's
            # threshold crossing is genuinely left-censored by the window.
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

        # Historical global-max semantics: first threshold crossing anywhere in
        # the waveform. This is intentionally retained as a separate explicit
        # estimator rather than silently redefining it.
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
