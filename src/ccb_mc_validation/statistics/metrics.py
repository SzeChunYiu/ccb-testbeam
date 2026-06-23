"""Metric records and bootstrap confidence intervals."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import numpy as np

from ccb_mc_validation.statistics.bootstrap import grouped_bootstrap


@dataclass
class MetricRecord:
    """Single scalar metric with optional bootstrap CI."""

    name: str
    value: float
    n: int
    ci_low: float | None = None
    ci_high: float | None = None
    unit: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def bootstrap_ci(
    values: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    *,
    n_boot: int = 500,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Bootstrap CI for an i.i.d. sample.

    Returns ``(point_estimate, ci_low, ci_high)``.
    """
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return float("nan"), float("nan"), float("nan")
    point = float(metric(arr))
    if arr.size == 1 or n_boot <= 0:
        return point, point, point

    stats = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample = rng.choice(arr, size=arr.size, replace=True)
        stats[i] = metric(sample)
    lo = float(np.quantile(stats, alpha / 2.0))
    hi = float(np.quantile(stats, 1.0 - alpha / 2.0))
    return point, lo, hi


def build_metric_record(
    name: str,
    values: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    *,
    n_boot: int = 500,
    unit: str = "",
    meta: dict[str, Any] | None = None,
) -> MetricRecord:
    """Construct a :class:`MetricRecord` with bootstrap CI."""
    point, lo, hi = bootstrap_ci(values, metric, rng, n_boot=n_boot)
    return MetricRecord(
        name=name,
        value=point,
        n=int(np.asarray(values).size),
        ci_low=lo,
        ci_high=hi,
        unit=unit,
        meta=dict(meta or {}),
    )


def build_grouped_metric_record(
    name: str,
    values: np.ndarray,
    groups: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    *,
    n_boot: int = 500,
    unit: str = "",
) -> MetricRecord:
    """Construct a metric record using block/group bootstrap."""
    point = float(metric(np.asarray(values, dtype=float)))
    lo, hi = grouped_bootstrap(values, groups, metric, rng, n_boot=n_boot)
    return MetricRecord(
        name=name,
        value=point,
        n=int(np.asarray(values).size),
        ci_low=lo,
        ci_high=hi,
        unit=unit,
    )
