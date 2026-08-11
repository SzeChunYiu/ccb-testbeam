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


def first_local_peak_amplitudes(waveforms: np.ndarray, *, min_prominence_frac: float = 0.05) -> np.ndarray:
    """Amplitude of the first local maximum on each waveform.

    Used to reduce global-max component switching (#1059): CFD thresholds are
    formed from the leading pulse component rather than a later taller peak.
    Falls back to the global maximum when no interior local peak exists.
    """
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D (n_pulses, n_samples)")
    n, n_samp = wave.shape
    out = np.empty(n, dtype=float)
    for i in range(n):
        y = wave[i]
        global_amp = float(np.max(y)) if y.size else float("nan")
        if not np.isfinite(global_amp) or global_amp <= 0:
            out[i] = global_amp
            continue
        floor = min_prominence_frac * global_amp
        chosen = global_amp
        for j in range(1, n_samp - 1):
            if y[j] >= y[j - 1] and y[j] >= y[j + 1] and y[j] >= floor:
                chosen = float(y[j])
                break
        out[i] = chosen
    return out


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

    Left-censored crossings (sample 0 already at/above threshold) are reported
    as ``NO_CROSSING_IN_WINDOW`` with time ``nan`` (#1060). They are never
    coerced to ``t=0``.
    """
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D (n_pulses, n_samples)")
    frac = float(fraction)
    if not np.isfinite(frac) or not (0.0 < frac < 1.0):
        raise ValueError("fraction must be finite and in (0, 1)")
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
        # Already above threshold at the first sample: left-censored.
        if y[0] >= thr:
            statuses[i] = NO_CROSSING_IN_WINDOW
            continue
        ge = y >= thr
        if not np.any(ge):
            statuses[i] = NO_CROSSING
            continue
        j = int(np.argmax(ge))
        if j <= 0:
            # Defensive: should be covered by y[0] >= thr above.
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
