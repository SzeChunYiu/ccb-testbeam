"""Event overlay for pile-up simulation skeleton."""

from __future__ import annotations

from typing import Any

import numpy as np


def overlay_hits(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    time_offset_ns: float,
) -> list[dict[str, Any]]:
    """Merge secondary hits into primary with time offset."""
    out = [dict(h) for h in primary]
    for h in secondary:
        hit = dict(h)
        hit["time_ns"] = float(hit.get("time_ns", 0.0)) + time_offset_ns
        out.append(hit)
    return out


def random_overlay_offset(
    rng: np.random.Generator,
    mean_spacing_ns: float,
) -> float:
    """Exponential inter-arrival spacing for pile-up overlay."""
    return float(rng.exponential(mean_spacing_ns))
