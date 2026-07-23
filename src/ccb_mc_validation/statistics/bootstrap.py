"""Grouped (block) and cluster bootstrap resampling with fail-closed validation.

Audit STAT-001/STAT-002 (scientific audit): the previous routines silently
returned ``NaN`` or a degenerate ``(point, point, point)`` interval when handed
empty / non-finite data or nonsensical ``alpha`` / ``n_boot``. That is
fail-OPEN: a caller gets a plausible-looking number instead of a loud error.
Every entry point here now raises ``ValueError`` so malformed inputs surface at
the call site, and a cluster bootstrap (resampling whole clusters with
replacement) is provided so rows correlated within a ``(run, event)`` block move
together instead of being treated as independent.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

__all__ = ["cluster_bootstrap", "grouped_bootstrap"]


def _validate_bootstrap_args(
    values: np.ndarray,
    n_boot: int,
    alpha: float,
    *,
    values_name: str = "values",
) -> None:
    """Shared fail-closed validation for every bootstrap entry point."""
    if isinstance(n_boot, bool) or not isinstance(n_boot, (int, np.integer)):
        raise ValueError(f"n_boot must be a positive integer, got {n_boot!r}")
    if int(n_boot) < 1:
        raise ValueError(f"n_boot must be >= 1, got {n_boot!r}")
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float, np.floating, np.integer)):
        raise ValueError(f"alpha must be a real number in (0, 1), got {alpha!r}")
    a = float(alpha)
    if not np.isfinite(a) or not (0.0 < a < 1.0):
        raise ValueError(f"alpha must satisfy 0 < alpha < 1, got {alpha!r}")
    if values.ndim != 1:
        raise ValueError(f"{values_name} must be 1-D, got shape {values.shape}")
    if values.size == 0:
        raise ValueError(f"{values_name} must be non-empty")
    if not np.all(np.isfinite(values)):
        n_bad = int(np.sum(~np.isfinite(values)))
        raise ValueError(
            f"{values_name} contains {n_bad} non-finite value(s) (NaN/inf); "
            "bootstrap requires finite data"
        )


def _group_values_by_label(
    values: np.ndarray, labels: np.ndarray
) -> tuple[np.ndarray, dict[object, np.ndarray]]:
    """One-pass ``{label: values_array}`` for any hashable cluster/group label.

    Needed because ``labels == k`` does an element-wise broadcast for tuple
    labels (e.g. ``(run, event)``) instead of a cluster-level membership test;
    this avoids that pitfall entirely and preserves label-equality semantics.
    """
    groups: dict[object, list[float]] = {}
    order: list[object] = []
    labels_list = labels.tolist()
    values_list = values.tolist()
    for label, val in zip(labels_list, values_list):
        bucket = groups.get(label)
        if bucket is None:
            groups[label] = [val]
            order.append(label)
        else:
            bucket.append(val)
    keys = np.empty(len(order), dtype=object)
    keys[:] = order
    members = {k: np.asarray(groups[k], dtype=float) for k in order}
    return keys, members

def grouped_bootstrap(
    values: np.ndarray,
    groups: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    *,
    n_boot: int = 500,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Two-level block bootstrap: resample groups with replacement AND resample
    within each resampled group.

    Returns ``(ci_low, ci_high)`` at ``1 - alpha`` coverage.

    Raises ``ValueError`` on malformed inputs (see
    :func:`_validate_bootstrap_args`) or when ``groups`` and ``values`` lengths
    disagree (audit STAT-001).
    """
    values = np.asarray(values, dtype=float)
    groups = np.asarray(groups)
    _validate_bootstrap_args(values, n_boot, alpha, values_name="values")
    if groups.shape != values.shape:
        raise ValueError(
            f"groups shape {groups.shape} must match values shape {values.shape} "
            "(cluster/value length mismatch)"
        )

    # One-pass grouping that works for any hashable label (incl. tuples); avoids
    # the ``groups == g`` broadcast pitfall for tuple labels.
    group_keys, by_group = _group_values_by_label(values, groups)
    stats = np.empty(int(n_boot), dtype=float)

    for i in range(int(n_boot)):
        pieces: list[np.ndarray] = []
        chosen = rng.choice(group_keys, size=len(group_keys), replace=True)
        for g in chosen:
            vals = by_group[g]
            pieces.append(rng.choice(vals, size=len(vals), replace=True))
        stats[i] = metric(np.concatenate(pieces))

    return (
        float(np.quantile(stats, alpha / 2.0)),
        float(np.quantile(stats, 1.0 - alpha / 2.0)),
    )


def cluster_bootstrap(
    values: np.ndarray,
    clusters: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    *,
    n_boot: int = 500,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Cluster (block) bootstrap keyed by ``clusters`` (audit STAT-002).

    Resample whole clusters WITH REPLACEMENT and use every member row of each
    chosen cluster (NO within-cluster sub-resample). Rows that share a cluster
    label always move together across replicates, preserving the within-cluster
    dependence of the sampling design -- this is the correct resampling unit
    when rows are correlated within e.g. ``(run, event)``; an ordinary row
    bootstrap would treat those rows as independent and understate uncertainty.

    Returns ``(ci_low, ci_high)`` at ``1 - alpha`` coverage.

    Raises ``ValueError`` on malformed inputs or cluster/value length mismatch.
    """
    values = np.asarray(values, dtype=float)
    clusters = np.asarray(clusters, dtype=object)
    _validate_bootstrap_args(values, n_boot, alpha, values_name="values")
    if clusters.shape != values.shape:
        raise ValueError(
            f"clusters shape {clusters.shape} must match values shape {values.shape} "
            "(cluster/value length mismatch)"
        )

    # One-pass grouping; works for tuple labels like (run, event) (STAT-002).
    cluster_keys, members = _group_values_by_label(values, clusters)
    stats = np.empty(int(n_boot), dtype=float)
    for i in range(int(n_boot)):
        chosen = rng.choice(cluster_keys, size=cluster_keys.size, replace=True)
        stats[i] = metric(np.concatenate([members[k] for k in chosen]))
    return (
        float(np.quantile(stats, alpha / 2.0)),
        float(np.quantile(stats, 1.0 - alpha / 2.0)),
    )
