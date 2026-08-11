"""Normalized exponential scintillation light yield kernel."""

from __future__ import annotations

import math

import numpy as np


def _require_positive_tau(tau: float, name: str) -> float:
    """Fail closed on non-physical rise/decay constants (#1075).

    Physical time constants must be finite and strictly positive. Silent
    clamping of ``tau <= 0`` (or non-finite values) to ``1e-12`` would
    substitute a near-delta impulse for an invalid configuration.
    """
    try:
        value = float(tau)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite float > 0, got {tau!r}") from exc
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0 ns, got {tau!r}")
    return value


def _safe_tau(tau: float) -> float:
    """Deprecated alias retained for import compatibility; now fail-closed.

    Prefer :func:`_require_positive_tau`. This name historically silent-clamped
    non-physical inputs; that policy is rejected for production (#1075).
    """
    return _require_positive_tau(tau, "tau")


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

    Raises
    ------
    ValueError
        If either time constant is non-finite or ``<= 0``.
    """
    tau_r = _require_positive_tau(tau_rise_ns, "tau_rise_ns")
    tau_d = _require_positive_tau(tau_decay_ns, "tau_decay_ns")
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

    Raises
    ------
    ValueError
        If either time constant is non-finite or ``<= 0``.
    """
    tau_r = _require_positive_tau(tau_rise_ns, "tau_rise_ns")
    tau_d = _require_positive_tau(tau_decay_ns, "tau_decay_ns")
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

    Raises
    ------
    ValueError
        If either time constant is non-finite or ``<= 0``.
    """
    tau_r = _require_positive_tau(tau_rise_ns, "tau_rise_ns")
    tau_d = _require_positive_tau(tau_decay_ns, "tau_decay_ns")
    t = np.asarray(t_ns, dtype=np.float64)
    out = np.zeros_like(t)
    pos = t >= 0.0
    tp = t[pos]
    raw = (1.0 - np.exp(-tp / tau_r)) * np.exp(-tp / tau_d)
    peak = raw.max() if raw.size else 1.0
    out[pos] = raw / max(peak, 1e-12)
    return out
