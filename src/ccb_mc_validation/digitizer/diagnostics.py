"""Digitizer diagnostic helpers."""

from __future__ import annotations

import numpy as np


def amplitude_spectrum(waveforms: np.ndarray) -> dict[str, float]:
    """Summary stats of peak ADC per waveform."""
    peaks = waveforms.max(axis=1)
    return {
        "mean_peak_adc": float(peaks.mean()),
        "median_peak_adc": float(np.median(peaks)),
        "p95_peak_adc": float(np.percentile(peaks, 95)),
    }


def saturation_fraction(saturated_flags: np.ndarray) -> float:
    return float(np.mean(saturated_flags.astype(bool)))
