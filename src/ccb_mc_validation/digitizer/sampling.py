"""Integrate light curve into 18 samples at fixed ns spacing."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.digitizer.scintillation import normalized_exponential_kernel

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
    Convolve normalized scintillation kernel with delta edep at t0_ns.

    Returns light yield in MeV-equivalent units per sample bin.
    """
    edges = t0_ns + np.arange(n_samples + 1, dtype=np.float64) * sample_spacing_ns
    k_edges = normalized_exponential_kernel(edges - t0_ns, tau_rise_ns, tau_decay_ns)
    return edep_mev * np.diff(k_edges)
