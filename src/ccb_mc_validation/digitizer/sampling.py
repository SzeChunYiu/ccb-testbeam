"""Integrate light curve into 18 samples at fixed ns spacing."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.digitizer.scintillation import exponential_kernel_cdf

DEFAULT_N_SAMPLES = 18
DEFAULT_SAMPLE_SPACING_NS = 10.0


def integrate_samples(
    edep_mev: float,
    t0_ns: float,
    sample_spacing_ns: float = DEFAULT_SAMPLE_SPACING_NS,
    n_samples: int = DEFAULT_N_SAMPLES,
    tau_rise_ns: float = 2.0,
    tau_decay_ns: float = 35.0,
) -> np.ndarray:
    """
    Integrate the scintillation light curve of a delta deposit at t0_ns over a
    FIXED acquisition grid (sample i spans [i, i+1) * sample_spacing_ns on the
    detector clock).

    Returns light yield in MeV-equivalent units per sample bin: non-negative,
    summing to edep_mev for a pulse fully contained in the window. Shifting
    t0_ns shifts the pulse across samples (fixed 2026-07-03: the previous
    implementation cancelled t0 exactly and diffed a peak-normalized kernel
    instead of its cumulative integral, yielding a one-sample spike followed
    by negative samples — see EXTERNAL_REVIEW_2026-07-02.md).
    """
    edges = np.arange(n_samples + 1, dtype=np.float64) * sample_spacing_ns
    cdf_edges = exponential_kernel_cdf(edges - t0_ns, tau_rise_ns, tau_decay_ns)
    return edep_mev * np.diff(cdf_edges)
