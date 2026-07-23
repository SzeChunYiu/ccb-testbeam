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
    """Integrate a normalized causal scintillation impulse over absolute bins.

    The sampling grid is anchored at the absolute digitizer-window start
    (``t = 0``); a hit at ``t0_ns`` shifts the impulse forward in time.  The
    per-sample charge is the integral of the unit-area impulse PDF over each
    bin, computed as the difference of the analytic CDF at the bin edges.  The
    result is therefore non-negative and causally zero for any bin that lies
    entirely before ``t0_ns``.

    Returns per-sample charge in MeV-equivalent units.  Over an infinite window
    the sum equals ``edep_mev`` (charge/energy conservation); a finite window
    captures only the fraction of the pulse that falls inside it.
    """
    edges = np.arange(n_samples + 1, dtype=np.float64) * float(sample_spacing_ns)
    cdf_vals = exponential_kernel_cdf(
        edges - float(t0_ns),
        tau_rise_ns,
        tau_decay_ns,
    )
    return float(edep_mev) * np.diff(cdf_vals)
