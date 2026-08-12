#!/usr/bin/env python3
"""Deterministic CFD fraction-transition diagnostics for two-pulse waveforms (#1059).

This module documents when global-maximum CFD retargets a later pulse as the
fraction crosses approximately ``A_early / A_late``.  It is a software
measurand diagnostic only; it does not authorize beam-data timing performance.
"""
from __future__ import annotations

from typing import Literal

import numpy as np

import digital_cfd

TRANSITION_PROFILE = "cfd_fraction_transition_deterministic_v1"
TRANSITION_STATUS = "SYNTHETIC_ALGORITHMIC_ONLY_NONAUTHORISING"
REAL_DATA_SCHEMA_GATE = "BLOCKED_UNTIL_993_WAVEFORM_LINEAGE_CLOSES"

AmplitudeMode = Literal["global_max", "first_local_peak"]


def synthetic_two_pulse_triangle(
    *,
    early_amplitude: float,
    late_amplitude: float,
    early_center: float = 3.0,
    late_center: float = 10.0,
    half_width: float = 0.8,
    n_samples: int = 16,
) -> np.ndarray:
    """Build a deterministic separated two-triangle waveform."""
    samples = np.arange(n_samples, dtype=float)

    def triangle(center: float, amplitude: float) -> np.ndarray:
        return amplitude * np.maximum(
            1.0 - np.abs(samples - center) / half_width,
            0.0,
        )

    return triangle(early_center, early_amplitude) + triangle(
        late_center,
        late_amplitude,
    )


def fraction_transition_scan(
    waveforms: np.ndarray,
    fractions: np.ndarray | list[float],
    *,
    amplitude_mode: AmplitudeMode = "global_max",
) -> dict[str, object]:
    """Scan CFD crossing times and report discrete component-switch events."""
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D (n_pulses, n_samples)")
    frac_list = [float(f) for f in fractions]
    if not frac_list:
        raise ValueError("fractions must be non-empty")

    rows: list[dict[str, object]] = []
    switch_events: list[dict[str, object]] = []
    for pulse_index in range(wave.shape[0]):
        previous_time: float | None = None
        for fraction in frac_list:
            times, statuses = digital_cfd.cfd_time_samples(
                wave[pulse_index : pulse_index + 1],
                None,
                fraction,
                amplitude_mode=amplitude_mode,
                return_status=True,
            )
            time = float(times[0])
            status = str(statuses[0])
            row = {
                "pulse_index": pulse_index,
                "fraction": fraction,
                "time_samples": time,
                "status": status,
                "amplitude_mode": amplitude_mode,
            }
            if (
                previous_time is not None
                and np.isfinite(previous_time)
                and np.isfinite(time)
                and abs(time - previous_time) > 1e-9
            ):
                switch_events.append(
                    {
                        "pulse_index": pulse_index,
                        "fraction": fraction,
                        "previous_time_samples": previous_time,
                        "time_samples": time,
                        "delta_samples": time - previous_time,
                        "amplitude_mode": amplitude_mode,
                    }
                )
            rows.append(row)
            if np.isfinite(time):
                previous_time = time

    return {
        "profile_id": TRANSITION_PROFILE,
        "evidence_status": TRANSITION_STATUS,
        "authorising_timing": False,
        "real_data_schema_gate": REAL_DATA_SCHEMA_GATE,
        "amplitude_mode": amplitude_mode,
        "fractions": frac_list,
        "rows": rows,
        "switch_events": switch_events,
        "n_switch_events": len(switch_events),
    }


def expected_global_max_switch_fraction(
    early_amplitude: float,
    late_amplitude: float,
) -> float:
    """Analytic crossing threshold where global-max CFD retargets (#1059)."""
    if late_amplitude <= 0.0:
        raise ValueError("late_amplitude must be positive")
    return float(early_amplitude) / float(late_amplitude)
