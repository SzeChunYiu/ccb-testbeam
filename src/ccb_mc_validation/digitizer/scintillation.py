"""Normalized exponential scintillation light yield kernel."""

from __future__ import annotations

import numpy as np


def _safe_tau(tau: float) -> float:
    """Clamp time constants away from zero to avoid division blow-up."""
    return max(float(tau), 1e-12)


def exponential_kernel_pdf(
    t_ns: np.ndarray,
    tau_rise_ns: float,
    tau_decay_ns: float,
) -> np.ndarray:
    """Unit-integral impulse response (probability density of photon arrival).

    Shape: ``(1 - exp(-t/tau_rise)) * exp(-t/tau_decay)`` for ``t >= 0``, zero
    otherwise.  Non-negative everywhere; integrates to 1 over ``(-inf, inf)``.
    The raw shape integrates to ``tau_decay**2 / (tau_rise + tau_decay)`` which
    we divide out, so this is a proper PDF rather than a peak-normalised shape.
    """
    tau_r = _safe_tau(tau_rise_ns)
    tau_d = _safe_tau(tau_decay_ns)
    t = np.asarray(t_ns, dtype=np.float64)
    out = np.zeros_like(t)
    pos = t >= 0.0
    tp = t[pos]
    raw = (1.0 - np.exp(-tp / tau_r)) * np.exp(-tp / tau_d)
    norm = (tau_d * tau_d) / (tau_r + tau_d)
    out[pos] = raw / norm
    return out


def exponential_kernel_cdf(
    t_ns: np.ndarray,
    tau_rise_ns: float,
    tau_decay_ns: float,
) -> np.ndarray:
    """Analytic CDF of :func:`exponential_kernel_pdf`.

    For ``T >= 0``::

        CDF(T) = ((tau_r + tau_d) / tau_d) * (1 - exp(-T/tau_d))
                 - (tau_r / tau_d) * (1 - exp(-T * (1/tau_r + 1/tau_d)))

    and ``0`` for ``T < 0`` (causal).  Monotonically non-decreasing with
    ``CDF(inf) = 1`` and ``CDF(0) = 0``.  Use this (not the peak-normalised
    shape) when integrating charge over absolute bin edges.
    """
    tau_r = _safe_tau(tau_rise_ns)
    tau_d = _safe_tau(tau_decay_ns)
    t = np.asarray(t_ns, dtype=np.float64)
    out = np.zeros_like(t)
    pos = t >= 0.0
    tp = t[pos]
    a = 1.0 / tau_r + 1.0 / tau_d  # combined decay rate
    term1 = ((tau_r + tau_d) / tau_d) * (1.0 - np.exp(-tp / tau_d))
    term2 = (tau_r / tau_d) * (1.0 - np.exp(-tp * a))
    out[pos] = term1 - term2
    # Numerical guard against tiny float overshoot outside [0, 1].
    return np.clip(out, 0.0, 1.0)


def normalized_exponential_kernel(
    t_ns: np.ndarray,
    tau_rise_ns: float,
    tau_decay_ns: float,
) -> np.ndarray:
    """DEPRECATED: peak-normalised impulse shape.

    Kept for backward compatibility only.  Differencing this peak-normalised
    shape as if it were a CDF is incorrect (it is not monotonic, does not
    integrate to 1, and yields negative per-bin "charge").  Use
    :func:`exponential_kernel_pdf` (unit integral) or
    :func:`exponential_kernel_cdf` for charge-conserving sampling.
    """
    tau_r = _safe_tau(tau_rise_ns)
    tau_d = _safe_tau(tau_decay_ns)
    t = np.asarray(t_ns, dtype=np.float64)
    out = np.zeros_like(t)
    pos = t >= 0.0
    tp = t[pos]
    raw = (1.0 - np.exp(-tp / tau_r)) * np.exp(-tp / tau_d)
    peak = raw.max() if raw.size else 1.0
    out[pos] = raw / max(peak, 1e-12)
    return out
