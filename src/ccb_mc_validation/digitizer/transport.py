"""WLS/fibre transit smearing (minimal Gaussian transport)."""

from __future__ import annotations

import numpy as np


def smear_time(
    time_ns: np.ndarray,
    rng: np.random.Generator,
    sigma_ns: float,
) -> np.ndarray:
    """Add Gaussian transit-time jitter to hit times."""
    t = np.asarray(time_ns, dtype=np.float64)
    return t + rng.normal(0.0, sigma_ns, size=t.shape)
