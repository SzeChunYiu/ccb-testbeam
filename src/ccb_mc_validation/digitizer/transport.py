"""WLS/fibre transit smearing (minimal Gaussian transport)."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.digitizer.config_types import require_nonnegative_float


def smear_time(
    time_ns: np.ndarray,
    rng: np.random.Generator,
    sigma_ns: float,
) -> np.ndarray:
    """Add Gaussian transit-time jitter to hit times.

    ``sigma_ns == 0`` is a VALID_CONTROL (deterministic). ``sigma_ns < 0`` is
    INVALID_INPUT and rejected before sampling (#1080).
    """
    sigma = require_nonnegative_float(sigma_ns, field_name="transport_sigma_ns")
    t = np.asarray(time_ns, dtype=np.float64)
    if sigma == 0.0:
        return t.copy()
    return t + rng.normal(0.0, sigma, size=t.shape)
