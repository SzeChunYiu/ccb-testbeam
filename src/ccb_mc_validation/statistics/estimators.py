"""Canonical statistical estimators for the CCB test-beam program.

This module is the single source of truth for the resolution estimators and
multiplicity-control procedures used across the study fleet. It exists because
the 2026-06 program shipped **three incompatible ``res68`` definitions** and an
iid bootstrap over linearly dependent pair residuals (External Review
2026-07-02, section 4). Every new study MUST import these implementations
instead of re-deriving them inline.

Definitions
-----------
``sigma68``
    Half the central 68% interquantile range, ``(q84 - q16) / 2`` with
    interpolated percentiles. For a Gaussian this equals ``0.9945 * sigma``
    (the 0.84 standard-normal quantile), i.e. approximately ``sigma``.
    Robust to symmetric location shifts of the *distribution shape* but NOT
    bias-free: it measures spread about the sample's own quantiles.

``res68_abs``
    The 68th percentile of ``|x|``. **Bias is included**: a residual sample
    with a nonzero median inflates this estimator relative to the centered
    variants. Use it when the figure of merit is "how far from zero", e.g.
    fractional charge-recovery error where a biased method must not be
    rewarded.

``res68_centered``
    The 68th percentile of ``|x - median(x)|``. Bias is removed via the
    sample median; measures pure spread. For a centered symmetric sample it
    coincides with ``res68_abs`` and (for a Gaussian) with ``sigma68``.

When reporting, always name the estimator explicitly; "res68" without a
qualifier is banned.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

__all__ = [
    "sigma68",
    "res68_abs",
    "res68_centered",
    "paired_delta_bootstrap",
    "bh_fdr",
]


def _as_clean_1d(x: object, name: str) -> np.ndarray:
    arr = np.asarray(x, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError(f"{name} is empty")
    if not np.isfinite(arr).all():
        raise ValueError(f"{name} contains non-finite values")
    return arr


def sigma68(x: object) -> float:
    """Half the central 68% interquantile range: ``(q84 - q16) / 2``.

    Percentiles are linearly interpolated. For a Gaussian sample this
    converges to ``~0.9945 * sigma``.
    """
    arr = _as_clean_1d(x, "x")
    q16, q84 = np.percentile(arr, [16.0, 84.0])
    return float((q84 - q16) / 2.0)


def res68_abs(x: object) -> float:
    """68th percentile of ``|x|``. **Bias included** — see module docstring."""
    arr = _as_clean_1d(x, "x")
    return float(np.percentile(np.abs(arr), 68.0))


def res68_centered(x: object) -> float:
    """68th percentile of ``|x - median(x)|`` (bias removed via the median)."""
    arr = _as_clean_1d(x, "x")
    return float(np.percentile(np.abs(arr - np.median(arr)), 68.0))


def paired_delta_bootstrap(
    a: object,
    b: object,
    clusters: object,
    *,
    statistic: Callable[[np.ndarray], float] = sigma68,
    n_boot: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Cluster bootstrap CI for the PAIRED difference ``statistic(a) - statistic(b)``.

    ``a`` and ``b`` are per-row results of two methods evaluated on the SAME
    rows (events / pair residuals); ``clusters`` gives the dependence unit for
    each row (event id for event-level resampling, run number for run-level).
    Whole clusters are resampled with replacement and the SAME resampled rows
    are used for both methods, so the between-method pairing — and the
    within-cluster dependence (e.g. the 3 linearly dependent pair residuals
    per event that the legacy iid bootstrap ignored) — is preserved.

    Returns ``(delta, lo, hi)``: the observed paired difference and the
    ``1 - alpha`` percentile CI. Percentile-only; for small numbers of
    clusters (e.g. 7 runs) the CI is anti-conservative — say so in the report.
    """
    a_arr = _as_clean_1d(a, "a")
    b_arr = _as_clean_1d(b, "b")
    cl = np.asarray(clusters).ravel()
    if not (a_arr.size == b_arr.size == cl.size):
        raise ValueError(
            f"a, b, clusters must have equal length; got {a_arr.size}, {b_arr.size}, {cl.size}"
        )
    if n_boot < 1:
        raise ValueError("n_boot must be >= 1")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")

    delta = float(statistic(a_arr) - statistic(b_arr))

    unique = np.unique(cl)
    if unique.size < 2:
        raise ValueError("need at least 2 clusters to bootstrap")
    # Row indices per cluster, computed once.
    members = {g: np.flatnonzero(cl == g) for g in unique}

    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        chosen = rng.choice(unique, size=unique.size, replace=True)
        idx = np.concatenate([members[g] for g in chosen])
        stats[i] = statistic(a_arr[idx]) - statistic(b_arr[idx])

    lo = float(np.percentile(stats, 100.0 * alpha / 2.0))
    hi = float(np.percentile(stats, 100.0 * (1.0 - alpha / 2.0)))
    return delta, lo, hi


def bh_fdr(pvals: Sequence[float], q: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Benjamini-Hochberg step-up FDR control.

    Parameters
    ----------
    pvals : sequence of p-values in [0, 1] (NaN treated as 1, i.e. never rejected).
    q : target false-discovery rate.

    Returns
    -------
    (reject, p_adjusted) : boolean rejection mask and monotone BH-adjusted
    p-values, both in the original input order. ``reject[i]`` is True iff
    ``p_adjusted[i] <= q``.
    """
    p = np.asarray(pvals, dtype=float).ravel()
    if p.size == 0:
        return np.zeros(0, dtype=bool), np.zeros(0, dtype=float)
    if not 0.0 < q < 1.0:
        raise ValueError("q must be in (0, 1)")
    p = np.where(np.isnan(p), 1.0, p)
    if ((p < 0.0) | (p > 1.0)).any():
        raise ValueError("p-values must lie in [0, 1]")

    m = p.size
    order = np.argsort(p, kind="stable")
    ranked = p[order]
    # BH adjusted p-values: cumulative minimum from the largest rank down.
    adj = ranked * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0.0, 1.0)

    p_adjusted = np.empty(m, dtype=float)
    p_adjusted[order] = adj
    reject = p_adjusted <= q
    return reject, p_adjusted
