"""Grouped (block) bootstrap resampling."""

from __future__ import annotations

from typing import Callable

import numpy as np


def grouped_bootstrap(
    values: np.ndarray,
    groups: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    *,
    n_boot: int = 500,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Resample whole groups with replacement, then resample within each group.

    Returns ``(ci_low, ci_high)`` at ``1-alpha`` coverage.
    """
    values = np.asarray(values, dtype=float)
    groups = np.asarray(groups)
    if values.size == 0:
        return float("nan"), float("nan")

    by_group: dict[object, np.ndarray] = {}
    for g in np.unique(groups):
        by_group[g] = values[groups == g]

    group_keys = np.array(list(by_group.keys()), dtype=object)
    stats = np.empty(n_boot, dtype=float)

    for i in range(n_boot):
        pieces: list[np.ndarray] = []
        chosen = rng.choice(group_keys, size=len(group_keys), replace=True)
        for g in chosen:
            vals = by_group[g]
            pieces.append(rng.choice(vals, size=len(vals), replace=True))
        stats[i] = metric(np.concatenate(pieces))

    return float(np.quantile(stats, alpha / 2.0)), float(np.quantile(stats, 1.0 - alpha / 2.0))
