#!/usr/bin/env python3
"""Beginner-facing raw-waveform timing study with a plot-by-plot evidence trail.

The program has two deliberately separate lanes:

``physical-demo``
    Generates real pulse waveforms with known per-stave timing jitter.  It shows
    how linear dCFD interpolation can yield a sub-sample pair residual and how a
    three-stave variance model is checked against injected truth.

``artifact-demo``
    Generates a correct 8 x 18 channel-major frame with pulses only on B2 and
    its duplicate, then deliberately truncates each event to 128 words and
    reshapes it as 8 x 16.  Pedestal boundaries become repeatable pseudo-pulses.
    This lane demonstrates how a narrow ~0.1 ns core can be manufactured while
    the full residual remains broad.  Its outputs are always watermarked as
    non-physical.

``raw``
    Reads one or more ROOT files using a YAML configuration.  Every event is
    width-checked before stacking or reshaping.  Retracted polarity maps are
    refused in the physical lane.  An explicit legacy-artifact section may be
    enabled to reproduce a historical truncation path for diagnosis only.

The output is a numbered plot atlas, CSV tables, a JSON evidence record, and a
Markdown report written for a student who has not previously studied timing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy.optimize import nnls
from scipy.stats import norm

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:  # Canonical repository implementation. Raw mode requires this import.
    import digital_cfd as canonical_cfd
except ImportError:  # pragma: no cover - only used by the portable synthetic demo.
    canonical_cfd = None

try:
    from channel_polarity import load_polarity_map
except ImportError:  # pragma: no cover - only used by the portable synthetic demo.
    load_polarity_map = None

try:
    from tools.audit.validate_hrd_waveform_contract import validate_and_reshape_rows
except ImportError:  # pragma: no cover - raw mode refuses to continue.
    validate_and_reshape_rows = None

SCHEMA = "ccb-student-timing-walkthrough/v1"
DEFAULT_FRACTIONS = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60)
DEFAULT_STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
DEFAULT_TOF_NS = {"B2": 0.0, "B4": 0.312, "B6": 0.624, "B8": 0.936}
PHYSICAL_MAP = np.asarray([1, -1, 1, -1, 1, -1, 1, -1], dtype=float)
RETRACTED_ARTIFACT_MAP = np.asarray([1, -1, -1, 1, -1, 1, -1, 1], dtype=float)


@dataclass
class WaveformDataset:
    label: str
    runs: np.ndarray
    event_ids: np.ndarray
    waveforms: np.ndarray
    sample_period_ns: float
    channel_labels: list[str]
    word_counts: np.ndarray
    source_files: list[str] = field(default_factory=list)
    source_sha256: dict[str, str] = field(default_factory=dict)
    truth_times_ns: dict[str, np.ndarray] | None = None
    truth_sigma_ns: dict[str, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.runs = np.asarray(self.runs, dtype=int)
        self.event_ids = np.asarray(self.event_ids, dtype=np.int64)
        self.waveforms = np.asarray(self.waveforms, dtype=np.float32)
        self.word_counts = np.asarray(self.word_counts, dtype=int)
        if self.waveforms.ndim != 3:
            raise ValueError("waveforms must be shaped (event, channel, sample)")
        if len(self.runs) != self.waveforms.shape[0]:
            raise ValueError("runs length must match waveform event count")
        if len(self.event_ids) != self.waveforms.shape[0]:
            raise ValueError("event_ids length must match waveform event count")
        if len(self.channel_labels) != self.waveforms.shape[1]:
            raise ValueError("channel_labels length must match n_channels")
        if not np.isfinite(self.sample_period_ns) or self.sample_period_ns <= 0:
            raise ValueError("sample_period_ns must be finite and positive")


@dataclass
class LaneConfig:
    name: str
    description: str
    staves: dict[str, int]
    polarity: np.ndarray
    baseline_samples: tuple[int, ...]
    fractions: tuple[float, ...]
    analysis_fraction: float
    amplitude_cut_adc: float
    component_mode: str
    tof_ns: dict[str, float]
    calibration_runs: tuple[int, ...]
    test_runs: tuple[int, ...]
    authorising: bool
    source_frame_authorized: bool = False
    component_identity_authorized: bool = False
    resolution_model_authorized: bool = False
    watermark: str | None = None
    polarity_status: str | None = None


@dataclass
class LaneResult:
    config: LaneConfig
    dataset_label: str
    baseline_adc: np.ndarray
    baseline_rms_adc: np.ndarray
    baseline_slope_adc_per_ns: np.ndarray
    corrected: np.ndarray
    global_amplitude_adc: np.ndarray
    global_peak_sample: np.ndarray
    selected_amplitude_adc: np.ndarray
    selected_peak_sample: np.ndarray
    selected_to_global_ratio: np.ndarray
    selector_status: np.ndarray
    times_ns: dict[float, np.ndarray]
    cfd_status: dict[float, np.ndarray]
    crossing_slope_adc_per_ns: dict[float, np.ndarray]
    fractional_phase: dict[float, np.ndarray]
    cutflow: pd.DataFrame
    pair_metrics: pd.DataFrame
    pair_vectors: dict[tuple[str, str, float], np.ndarray]
    pair_event_tables: dict[tuple[str, str, float], pd.DataFrame]
    peak_offsets_samples: dict[str, float]
    inference: dict[str, Any]
    summary: dict[str, Any]


def sigma68(values: Iterable[float]) -> float:
    vector = np.asarray(list(values), dtype=float)
    vector = vector[np.isfinite(vector)]
    if vector.size == 0:
        return float("nan")
    q16, q84 = np.quantile(vector, [0.16, 0.84])
    return float(0.5 * (q84 - q16))


def robust_metrics(values: np.ndarray) -> dict[str, float | int]:
    vector = np.asarray(values, dtype=float)
    vector = vector[np.isfinite(vector)]
    if vector.size == 0:
        return {
            "n": 0,
            "mean_ns": float("nan"),
            "median_ns": float("nan"),
            "sigma68_ns": float("nan"),
            "rms_ns": float("nan"),
            "tail_gt1ns": float("nan"),
            "tail_gt2ns": float("nan"),
            "tail_gt5ns": float("nan"),
            "tail_gt10ns": float("nan"),
        }
    median = float(np.median(vector))
    centered = vector - median
    return {
        "n": int(vector.size),
        "mean_ns": float(np.mean(vector)),
        "median_ns": median,
        "sigma68_ns": sigma68(vector),
        "rms_ns": float(np.sqrt(np.mean(centered**2))),
        "tail_gt1ns": float(np.mean(np.abs(centered) > 1.0)),
        "tail_gt2ns": float(np.mean(np.abs(centered) > 2.0)),
        "tail_gt5ns": float(np.mean(np.abs(centered) > 5.0)),
        "tail_gt10ns": float(np.mean(np.abs(centered) > 10.0)),
    }


def gaussian_core_diagnostic(values: np.ndarray) -> dict[str, float]:
    vector = np.asarray(values, dtype=float)
    vector = vector[np.isfinite(vector)]
    if vector.size < 100:
        return {
            "core_sigma_ns": float("nan"),
            "core_mean_ns": float("nan"),
            "chi2_ndf": float("nan"),
        }
    median = float(np.median(vector))
    width = sigma68(vector)
    if not np.isfinite(width) or width <= 0:
        return {
            "core_sigma_ns": float("nan"),
            "core_mean_ns": float("nan"),
            "chi2_ndf": float("nan"),
        }
    core = vector[np.abs(vector - median) <= 2.0 * width]
    if core.size < 100:
        return {
            "core_sigma_ns": float("nan"),
            "core_mean_ns": float("nan"),
            "chi2_ndf": float("nan"),
        }
    mean, standard_deviation = norm.fit(core)
    bins = max(20, min(100, int(np.sqrt(core.size))))
    counts, edges = np.histogram(core, bins=bins)
    probabilities = np.diff(norm.cdf(edges, loc=mean, scale=standard_deviation))
    probability_sum = float(np.sum(probabilities))
    if probability_sum <= 0.0:
        return {
            "core_sigma_ns": float(standard_deviation),
            "core_mean_ns": float(mean),
            "chi2_ndf": float("nan"),
        }
    # The fit is evaluated only inside the selected core interval.  Renormalize
    # the Gaussian to that same interval; otherwise missing probability outside
    # the histogram range creates a spurious large chi2 even for normal data.
    probabilities = probabilities / probability_sum
    expected = probabilities * core.size
    valid = expected >= 5.0
    if np.count_nonzero(valid) <= 3:
        chi2_ndf = float("nan")
    else:
        chi2 = float(np.sum((counts[valid] - expected[valid]) ** 2 / expected[valid]))
        ndf = max(1, int(np.count_nonzero(valid) - 3))
        chi2_ndf = chi2 / ndf
    return {
        "core_sigma_ns": float(standard_deviation),
        "core_mean_ns": float(mean),
        "chi2_ndf": float(chi2_ndf),
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    """Convert numpy values and non-finite floats to strict JSON values."""
    if isinstance(value, dict):
        return {str(key): json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(child) for child in value]
    if isinstance(value, np.ndarray):
        return [json_safe(child) for child in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    return value


def fallback_first_local_peak_diagnostics(waveforms: np.ndarray) -> dict[str, np.ndarray]:
    wave = np.asarray(waveforms, dtype=float)
    if wave.ndim != 2:
        raise ValueError("waveforms must be 2-D")
    n_rows, n_samples = wave.shape
    global_amplitude = np.max(wave, axis=1)
    global_peak = np.argmax(wave, axis=1)
    selected_amplitude = np.full(n_rows, np.nan)
    selected_peak = np.full(n_rows, -1, dtype=int)
    selected_ratio = np.full(n_rows, np.nan)
    statuses = np.full(n_rows, "INVALID_AMPLITUDE", dtype=object)
    for row_index in range(n_rows):
        maximum = float(global_amplitude[row_index])
        if not np.isfinite(maximum) or maximum <= 0:
            continue
        floor = 0.05 * maximum
        selected = None
        for sample_index in range(1, n_samples - 1):
            value = wave[row_index, sample_index]
            if (
                value >= wave[row_index, sample_index - 1]
                and value >= wave[row_index, sample_index + 1]
                and value >= floor
            ):
                selected = sample_index
                break
        if selected is None:
            selected = int(global_peak[row_index])
            statuses[row_index] = "FALLBACK_GLOBAL_NO_ELIGIBLE_INTERIOR"
        else:
            statuses[row_index] = "FIRST_LOCAL_ABOVE_GLOBAL_FLOOR"
        selected_peak[row_index] = selected
        selected_amplitude[row_index] = wave[row_index, selected]
        selected_ratio[row_index] = selected_amplitude[row_index] / maximum
    return {
        "selected_amplitudes": selected_amplitude,
        "selected_peak_indices": selected_peak,
        "global_amplitudes": global_amplitude,
        "global_peak_indices": global_peak,
        "selected_to_global_ratio": selected_ratio,
        "statuses": statuses,
    }


def fallback_cfd_time_samples(
    waveforms: np.ndarray,
    fraction: float,
    selected_amplitudes: np.ndarray,
    selected_peak_indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    wave = np.asarray(waveforms, dtype=float)
    amplitudes = np.asarray(selected_amplitudes, dtype=float)
    peaks = np.asarray(selected_peak_indices, dtype=int)
    times = np.full(wave.shape[0], np.nan)
    statuses = np.full(wave.shape[0], "NO_CROSSING", dtype=object)
    for row_index in range(wave.shape[0]):
        amplitude = float(amplitudes[row_index])
        peak = int(peaks[row_index])
        if not np.isfinite(amplitude) or amplitude <= 0 or peak < 1:
            statuses[row_index] = "INVALID_AMPLITUDE"
            continue
        threshold = fraction * amplitude
        below = np.flatnonzero(wave[row_index, :peak] < threshold)
        if below.size == 0:
            statuses[row_index] = "NO_CROSSING_IN_WINDOW"
            continue
        right = int(below[-1]) + 1
        if right > peak or wave[row_index, right] < threshold:
            statuses[row_index] = "NO_CROSSING"
            continue
        y0 = float(wave[row_index, right - 1])
        y1 = float(wave[row_index, right])
        denominator = y1 - y0
        if denominator <= 0:
            statuses[row_index] = "NONPOSITIVE_BRACKET"
            continue
        times[row_index] = (right - 1) + (threshold - y0) / denominator
        statuses[row_index] = "OK"
    return times, statuses


def cfd_features(
    corrected: np.ndarray,
    fractions: Sequence[float],
    component_mode: str,
    sample_period_ns: float,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    dict[float, np.ndarray],
    dict[float, np.ndarray],
    dict[float, np.ndarray],
    dict[float, np.ndarray],
]:
    n_events, n_channels, n_samples = corrected.shape
    flat = corrected.reshape(n_events * n_channels, n_samples)
    if component_mode != "first_local_peak":
        raise ValueError("student walkthrough currently requires first_local_peak mode")
    if canonical_cfd is not None:
        selector = canonical_cfd.first_local_peak_diagnostics(flat)
    else:
        selector = fallback_first_local_peak_diagnostics(flat)

    selected_amplitude = np.asarray(selector["selected_amplitudes"], dtype=float)
    selected_peak = np.asarray(selector["selected_peak_indices"], dtype=int)
    global_amplitude = np.asarray(selector["global_amplitudes"], dtype=float)
    global_peak = np.asarray(selector["global_peak_indices"], dtype=int)
    selected_ratio = np.asarray(selector["selected_to_global_ratio"], dtype=float)
    selector_status = np.asarray(selector["statuses"], dtype=object)

    times: dict[float, np.ndarray] = {}
    statuses: dict[float, np.ndarray] = {}
    slopes: dict[float, np.ndarray] = {}
    phases: dict[float, np.ndarray] = {}
    for fraction in fractions:
        if canonical_cfd is not None:
            crossing_samples, crossing_status = canonical_cfd.cfd_time_samples(
                flat,
                None,
                float(fraction),
                amplitude_mode="first_local_peak",
                return_status=True,
            )
        else:
            crossing_samples, crossing_status = fallback_cfd_time_samples(
                flat,
                float(fraction),
                selected_amplitude,
                selected_peak,
            )
        crossing_samples = np.asarray(crossing_samples, dtype=float)
        crossing_status = np.asarray(crossing_status, dtype=object)
        slope = np.full_like(crossing_samples, np.nan, dtype=float)
        finite = np.isfinite(crossing_samples)
        right = np.floor(crossing_samples[finite]).astype(int) + 1
        right = np.clip(right, 1, n_samples - 1)
        row_indices = np.flatnonzero(finite)
        slope[finite] = (
            flat[row_indices, right] - flat[row_indices, right - 1]
        ) / sample_period_ns
        times[float(fraction)] = crossing_samples.reshape(n_events, n_channels) * sample_period_ns
        statuses[float(fraction)] = crossing_status.reshape(n_events, n_channels)
        slopes[float(fraction)] = slope.reshape(n_events, n_channels)
        phases[float(fraction)] = np.mod(crossing_samples, 1.0).reshape(n_events, n_channels)

    shape = (n_events, n_channels)
    return (
        global_amplitude.reshape(shape),
        global_peak.reshape(shape),
        selected_amplitude.reshape(shape),
        selected_peak.reshape(shape),
        selected_ratio.reshape(shape),
        selector_status.reshape(shape),
        times,
        statuses,
        slopes,
        phases,
    )
