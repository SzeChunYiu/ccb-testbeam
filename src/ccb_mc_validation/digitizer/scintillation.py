"""Normalized exponential scintillation light yield kernel."""

from __future__ import annotations

import numpy as np


def normalized_exponential_kernel(
    t_ns: np.ndarray,
    tau_rise_ns: float,
    tau_decay_ns: float,
) -> np.ndarray:
    """
    Single-exponential rise × exponential decay, normalized to unit peak.

    Parameters
    ----------
    t_ns
        Time samples in nanoseconds (may be negative; values before zero are zero).
    tau_rise_ns, tau_decay_ns
        Rise and decay time constants in ns.
    """
    t = np.asarray(t_ns, dtype=np.float64)
    out = np.zeros_like(t)
    pos = t >= 0.0
    tp = t[pos]
    raw = (1.0 - np.exp(-tp / max(tau_rise_ns, 1e-6))) * np.exp(-tp / max(tau_decay_ns, 1e-6))
    peak = raw.max() if raw.size else 1.0
    out[pos] = raw / max(peak, 1e-12)
    return out
