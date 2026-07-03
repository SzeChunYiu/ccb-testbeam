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


def exponential_kernel_cdf(
    t_ns: np.ndarray,
    tau_rise_ns: float,
    tau_decay_ns: float,
) -> np.ndarray:
    """
    Cumulative fraction of total light emitted by time t for the kernel
    k(t) = (1 - exp(-t/tau_rise)) * exp(-t/tau_decay), t >= 0.

    With tau_c = tau_rise*tau_decay/(tau_rise+tau_decay):
        Int_0^T k dt = tau_decay*(1 - exp(-T/tau_decay)) - tau_c*(1 - exp(-T/tau_c))
    normalized by the total area (tau_decay - tau_c). Values for t < 0 are 0;
    the function rises monotonically to 1.
    """
    tau_r = max(float(tau_rise_ns), 1e-6)
    tau_d = max(float(tau_decay_ns), 1e-6)
    tau_c = tau_r * tau_d / (tau_r + tau_d)
    area = tau_d - tau_c
    t = np.asarray(t_ns, dtype=np.float64)
    out = np.zeros_like(t)
    pos = t >= 0.0
    tp = t[pos]
    out[pos] = (
        tau_d * (1.0 - np.exp(-tp / tau_d)) - tau_c * (1.0 - np.exp(-tp / tau_c))
    ) / max(area, 1e-12)
    return out
