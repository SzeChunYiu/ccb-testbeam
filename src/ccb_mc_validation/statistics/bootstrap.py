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

__all__ = ["cluster_bootstrap", "grouped_bootstrap", "weighted_cluster_bootstrap", "weighted_mean"]


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

def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """Normalised weighted mean; raises on empty / non-positive weight sum."""
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if values.shape != weights.shape:
        raise ValueError(
            f"values shape {values.shape} must match weights shape {weights.shape}"
        )
    if values.size == 0:
        raise ValueError("weighted_mean requires non-empty values")
    if not np.all(np.isfinite(values)):
        raise ValueError("weighted_mean values must be finite")
    if not np.all(np.isfinite(weights)) or np.any(weights < 0):
        raise ValueError("weighted_mean weights must be finite and nonnegative")
    total = float(np.sum(weights))
    if total <= 0.0:
        raise ValueError("weighted_mean weight sum must be positive")
    return float(np.sum(weights * values) / total)


def weighted_cluster_bootstrap(
    values: np.ndarray,
    weights: np.ndarray,
    clusters: np.ndarray,
    rng: np.random.Generator,
    *,
    n_boot: int = 500,
    alpha: float = 0.05,
) -> dict[str, object]:
    """Cluster bootstrap of a normalised weighted mean (issue #960).

    Each replicate resamples whole clusters with replacement (multiplicity
    preserved), concatenates member rows, and recomputes the full weighted
    mean with re-normalised weights. Degenerate designs raise ``ValueError``
    rather than emitting a zero-width interval.
    """
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    clusters = np.asarray(clusters, dtype=object)
    _validate_bootstrap_args(values, n_boot, alpha, values_name="values")
    if weights.shape != values.shape:
        raise ValueError(
            f"weights shape {weights.shape} must match values shape {values.shape}"
        )
    if clusters.shape != values.shape:
        raise ValueError(
            f"clusters shape {clusters.shape} must match values shape {values.shape}"
        )
    if not np.all(np.isfinite(weights)) or np.any(weights < 0):
        raise ValueError("weights must be finite and nonnegative")
    if float(np.sum(weights)) <= 0.0:
        raise ValueError("weight sum must be positive")

    cluster_keys, value_members = _group_values_by_label(values, clusters)
    _, weight_members = _group_values_by_label(weights, clusters)
    n_clusters = int(cluster_keys.size)
    if n_clusters < 2:
        raise ValueError(
            f"weighted cluster bootstrap requires >=2 clusters, got {n_clusters}"
        )

    point = weighted_mean(values, weights)
    stats = np.empty(int(n_boot), dtype=float)
    n_success = 0
    n_failure = 0
    for i in range(int(n_boot)):
        chosen = rng.choice(cluster_keys, size=n_clusters, replace=True)
        boot_values = np.concatenate([value_members[k] for k in chosen])
        boot_weights = np.concatenate([weight_members[k] for k in chosen])
        try:
            stats[n_success] = weighted_mean(boot_values, boot_weights)
            n_success += 1
        except ValueError:
            n_failure += 1
    if n_success < max(10, int(0.5 * int(n_boot))):
        raise ValueError(
            f"weighted cluster bootstrap NOT_ESTIMABLE: only {n_success}/{n_boot} "
            f"replicates succeeded ({n_failure} failures)"
        )
    stats = stats[:n_success]
    ess = float((np.sum(weights) ** 2) / np.sum(weights ** 2))
    return {
        "point": point,
        "ci_low": float(np.quantile(stats, alpha / 2.0)),
        "ci_high": float(np.quantile(stats, 1.0 - alpha / 2.0)),
        "n_boot_requested": int(n_boot),
        "n_boot_success": int(n_success),
        "n_boot_failure": int(n_failure),
        "n_clusters": n_clusters,
        "effective_sample_size": ess,
        "estimand": "pulse_ipw_accuracy",
        "resampling_unit": "(run,event)_cluster",
        "status": "OK",
    }
