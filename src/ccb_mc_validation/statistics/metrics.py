"""Metric records and bootstrap confidence intervals (fail-closed validation)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import numpy as np

from ccb_mc_validation.statistics.bootstrap import (
    _validate_bootstrap_args,
    cluster_bootstrap,
    grouped_bootstrap,
)

__all__ = [
    "MetricRecord",
    "bootstrap_ci",
    "build_cluster_metric_record",
    "build_grouped_metric_record",
    "build_metric_record",
]


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

    Fail-closed (audit STAT-001): raises ``ValueError`` on empty / non-finite
    data, ``alpha`` outside ``(0, 1)``, or ``n_boot < 1`` rather than silently
    returning a degenerate interval. A single-observation sample returns
    ``(point, point, point)`` -- a deterministic 1-point sample has no
    resampling variance, and the zero-width interval is reported honestly.
    """
    arr = np.asarray(values, dtype=float)
    _validate_bootstrap_args(arr, n_boot, alpha, values_name="values")
    point = float(metric(arr))
    if arr.size == 1:
        return point, point, point

    stats = np.empty(int(n_boot), dtype=float)
    for i in range(int(n_boot)):
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
    """Construct a :class:`MetricRecord` with an i.i.d. bootstrap CI."""
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
    """Construct a metric record using the two-level block/group bootstrap."""
    arr = np.asarray(values, dtype=float)
    point = float(metric(arr))
    lo, hi = grouped_bootstrap(values, groups, metric, rng, n_boot=n_boot)
    return MetricRecord(
        name=name,
        value=point,
        n=int(arr.size),
        ci_low=lo,
        ci_high=hi,
        unit=unit,
    )


def build_cluster_metric_record(
    name: str,
    values: np.ndarray,
    clusters: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    *,
    n_boot: int = 500,
    unit: str = "",
) -> MetricRecord:
    """Construct a metric record using the cluster bootstrap keyed by ``clusters``.

    Use this (audit STAT-002) when rows are correlated within a cluster such as
    ``(run, event)`` and an ordinary row bootstrap would understate uncertainty.
    """
    arr = np.asarray(values, dtype=float)
    point = float(metric(arr))
    lo, hi = cluster_bootstrap(values, clusters, metric, rng, n_boot=n_boot)
    return MetricRecord(
        name=name,
        value=point,
        n=int(arr.size),
        ci_low=lo,
        ci_high=hi,
        unit=unit,
    )
