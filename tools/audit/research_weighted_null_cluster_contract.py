#!/usr/bin/env python3
"""Research-only resampling falsifiers for weighted DATA/MC null design.

This module does not produce an authorising p-value.  It exists to make one
dependency of issue #1049 executable: weighted rows that share a generator or
DAQ event must remain one resampling cluster.  Treating repeated rows as
independent changes the bootstrap law under representation splitting.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


class NullDesignContractError(ValueError):
    """Raised when a weighted-null research input violates its typed contract."""


@dataclass(frozen=True)
class SplitInvarianceResult:
    observed_d_unsplit: float
    observed_d_split: float
    cluster_bootstrap_max_abs_delta: float
    row_bootstrap_max_abs_delta: float
    cluster_bootstrap_mean_unsplit: float
    cluster_bootstrap_mean_split: float
    row_bootstrap_mean_unsplit: float
    row_bootstrap_mean_split: float
    n_bootstrap: int
    split_factor: int
    data_seed: int
    bootstrap_seed: int


def _validated_measure(values, weights, clusters, label):
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    c = np.asarray(clusters)
    if x.ndim != 1 or w.ndim != 1 or c.ndim != 1:
        raise NullDesignContractError(f"{label}: values, weights and clusters must be 1D")
    if not (x.size == w.size == c.size):
        raise NullDesignContractError(f"{label}: values, weights and clusters must align")
    if x.size == 0:
        raise NullDesignContractError(f"{label}: at least one row is required")
    if not np.isfinite(x).all():
        raise NullDesignContractError(f"{label}: values must be finite")
    if not np.isfinite(w).all() or np.any(w < 0):
        raise NullDesignContractError(f"{label}: weights must be finite and nonnegative")
    if not float(np.sum(w)) > 0.0:
        raise NullDesignContractError(f"{label}: weight sum must be positive")
    if c.dtype.kind == "f" and not np.isfinite(c).all():
        raise NullDesignContractError(f"{label}: cluster IDs must be finite")
    return x, w, c


def _ecdf_at(values, weights, points):
    order = np.argsort(values, kind="mergesort")
    x = values[order]
    w = weights[order]
    support, first = np.unique(x, return_index=True)
    mass = np.add.reduceat(w, first)
    cdf = np.cumsum(mass, dtype=float) / float(np.sum(w))
    idx = np.searchsorted(support, points, side="right") - 1
    out = np.zeros(points.shape, dtype=float)
    mask = idx >= 0
    out[mask] = cdf[idx[mask]]
    return out


def weighted_ecdf_distance(data, model, data_weights, model_weights):
    """Independent right-continuous weighted-ECDF distance oracle."""
    data, data_weights, _ = _validated_measure(
        data, data_weights, np.arange(len(data)), "data"
    )
    model, model_weights, _ = _validated_measure(
        model, model_weights, np.arange(len(model)), "model"
    )
    points = np.union1d(data, model)
    fd = _ecdf_at(data, data_weights, points)
    fm = _ecdf_at(model, model_weights, points)
    return float(np.max(np.abs(fd - fm)))


def _cluster_bootstrap_indices(clusters, rng):
    unique = np.unique(clusters)
    draws = rng.choice(unique, size=unique.size, replace=True)
    parts = [np.flatnonzero(clusters == cluster) for cluster in draws]
    return np.concatenate(parts)


def _row_bootstrap_indices(n_rows, rng):
    return rng.integers(0, n_rows, size=n_rows)


def centered_bootstrap_statistics(
    data,
    model,
    data_weights,
    model_weights,
    data_clusters,
    model_clusters,
    *,
    n_bootstrap,
    seed,
    resampling_unit,
):
    """Return research bootstrap statistics, not calibrated p-values.

    The bootstrap process is centered on each observed empirical measure:
    sup_x |(F_D* - F_D) - (F_M* - F_M)|.  It is used only to test whether a
    proposed resampling *unit* is invariant to row representation changes.
    """
    data, data_weights, data_clusters = _validated_measure(
        data, data_weights, data_clusters, "data"
    )
    model, model_weights, model_clusters = _validated_measure(
        model, model_weights, model_clusters, "model"
    )
    if n_bootstrap <= 0:
        raise NullDesignContractError("n_bootstrap must be positive")
    if resampling_unit not in {"cluster", "row"}:
        raise NullDesignContractError("resampling_unit must be 'cluster' or 'row'")

    rng = np.random.default_rng(seed)
    stats = np.empty(int(n_bootstrap), dtype=float)
    for i in range(int(n_bootstrap)):
        if resampling_unit == "cluster":
            idx_d = _cluster_bootstrap_indices(data_clusters, rng)
            idx_m = _cluster_bootstrap_indices(model_clusters, rng)
        else:
            idx_d = _row_bootstrap_indices(data.size, rng)
            idx_m = _row_bootstrap_indices(model.size, rng)

        points = np.union1d(
            np.union1d(data, model),
            np.union1d(data[idx_d], model[idx_m]),
        )
        fd = _ecdf_at(data, data_weights, points)
        fm = _ecdf_at(model, model_weights, points)
        fd_star = _ecdf_at(data[idx_d], data_weights[idx_d], points)
        fm_star = _ecdf_at(model[idx_m], model_weights[idx_m], points)
        stats[i] = float(np.max(np.abs((fd_star - fd) - (fm_star - fm))))
    return stats


def split_weighted_rows(values, weights, clusters, factor):
    """Split each row into equivalent copies sharing its original cluster ID."""
    values, weights, clusters = _validated_measure(values, weights, clusters, "rows")
    if not isinstance(factor, int) or isinstance(factor, bool) or factor < 1:
        raise NullDesignContractError("split factor must be a positive integer")
    return (
        np.repeat(values, factor),
        np.repeat(weights / factor, factor),
        np.repeat(clusters, factor),
    )


@dataclass(frozen=True)
class SyntheticCoverageResult:
    target: str
    proposal: str
    exact_weight: str
    n_trials: int
    n_data: int
    n_model: int
    n_bootstrap: int
    alpha_005_rejection_fraction: float
    alpha_010_rejection_fraction: float
    mean_p_value: float
    mean_model_ess: float
    model_ess_p10: float
    model_ess_p50: float
    model_ess_p90: float


def run_importance_sampling_type1_fixture(
    *,
    n_trials=200,
    n_data=80,
    n_model=160,
    n_bootstrap=99,
    bootstrap_seed_offset=100000,
):
    """Synthetic null calibration stress test for one candidate cluster bootstrap.

    DATA are iid N(0,1).  MC rows are iid N(1,1) proposal draws with the exact
    likelihood-ratio weight f/q = exp(-x + 1/2), so the weighted MC target is
    also N(0,1).  Each row is one synthetic event/cluster.  This is method
    research only: it does not validate the CCB detector, current NPZ products,
    nuisance-scale treatment, or real campaign weight lineage.
    """
    if n_trials <= 0 or n_data <= 1 or n_model <= 1 or n_bootstrap <= 0:
        raise NullDesignContractError("coverage fixture counts must be positive")

    p_values = []
    ess_values = []
    for trial_seed in range(int(n_trials)):
        rng = np.random.default_rng(trial_seed)
        data = rng.normal(0.0, 1.0, int(n_data))
        model = rng.normal(1.0, 1.0, int(n_model))
        data_weights = np.ones(data.size, dtype=float)
        model_weights = np.exp(-model + 0.5)
        observed = weighted_ecdf_distance(
            data, model, data_weights, model_weights
        )
        boot = centered_bootstrap_statistics(
            data,
            model,
            data_weights,
            model_weights,
            np.arange(data.size),
            np.arange(model.size),
            n_bootstrap=n_bootstrap,
            seed=trial_seed + int(bootstrap_seed_offset),
            resampling_unit="cluster",
        )
        p_values.append(
            float((1 + np.count_nonzero(boot >= observed)) / (n_bootstrap + 1))
        )
        sw = float(np.sum(model_weights))
        s2 = float(np.sum(model_weights * model_weights))
        ess_values.append(sw * sw / s2)

    p = np.asarray(p_values, dtype=float)
    ess = np.asarray(ess_values, dtype=float)
    return SyntheticCoverageResult(
        target="N(0,1)",
        proposal="N(1,1)",
        exact_weight="exp(-x + 0.5)",
        n_trials=int(n_trials),
        n_data=int(n_data),
        n_model=int(n_model),
        n_bootstrap=int(n_bootstrap),
        alpha_005_rejection_fraction=float(np.mean(p <= 0.05)),
        alpha_010_rejection_fraction=float(np.mean(p <= 0.10)),
        mean_p_value=float(np.mean(p)),
        mean_model_ess=float(np.mean(ess)),
        model_ess_p10=float(np.quantile(ess, 0.10)),
        model_ess_p50=float(np.quantile(ess, 0.50)),
        model_ess_p90=float(np.quantile(ess, 0.90)),
    )


def run_split_invariance_fixture(
    *,
    n_bootstrap=100,
    split_factor=5,
    data_seed=7,
    bootstrap_seed=99,
):
    """Execute the deterministic representation-splitting falsifier for #1049."""
    rng = np.random.default_rng(data_seed)
    data = rng.normal(0.0, 1.0, 30)
    model = rng.normal(0.5, 1.0, 25)
    data_weights = np.ones(data.size, dtype=float)
    model_weights = np.exp(-0.5 * model)
    data_clusters = np.arange(data.size)
    model_clusters = np.arange(model.size)

    split_model, split_weights, split_clusters = split_weighted_rows(
        model, model_weights, model_clusters, split_factor
    )
    observed = weighted_ecdf_distance(data, model, data_weights, model_weights)
    observed_split = weighted_ecdf_distance(
        data, split_model, data_weights, split_weights
    )
    cluster_unsplit = centered_bootstrap_statistics(
        data,
        model,
        data_weights,
        model_weights,
        data_clusters,
        model_clusters,
        n_bootstrap=n_bootstrap,
        seed=bootstrap_seed,
        resampling_unit="cluster",
    )
    cluster_split = centered_bootstrap_statistics(
        data,
        split_model,
        data_weights,
        split_weights,
        data_clusters,
        split_clusters,
        n_bootstrap=n_bootstrap,
        seed=bootstrap_seed,
        resampling_unit="cluster",
    )
    row_unsplit = centered_bootstrap_statistics(
        data,
        model,
        data_weights,
        model_weights,
        data_clusters,
        model_clusters,
        n_bootstrap=n_bootstrap,
        seed=bootstrap_seed,
        resampling_unit="row",
    )
    row_split = centered_bootstrap_statistics(
        data,
        split_model,
        data_weights,
        split_weights,
        data_clusters,
        split_clusters,
        n_bootstrap=n_bootstrap,
        seed=bootstrap_seed,
        resampling_unit="row",
    )
    return SplitInvarianceResult(
        observed_d_unsplit=observed,
        observed_d_split=observed_split,
        cluster_bootstrap_max_abs_delta=float(
            np.max(np.abs(cluster_unsplit - cluster_split))
        ),
        row_bootstrap_max_abs_delta=float(np.max(np.abs(row_unsplit - row_split))),
        cluster_bootstrap_mean_unsplit=float(np.mean(cluster_unsplit)),
        cluster_bootstrap_mean_split=float(np.mean(cluster_split)),
        row_bootstrap_mean_unsplit=float(np.mean(row_unsplit)),
        row_bootstrap_mean_split=float(np.mean(row_split)),
        n_bootstrap=int(n_bootstrap),
        split_factor=int(split_factor),
        data_seed=int(data_seed),
        bootstrap_seed=int(bootstrap_seed),
    )


def main():
    import argparse
    import json
    from dataclasses import asdict

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="also run the synthetic N(0,1) vs importance-sampled N(1,1) type-I fixture",
    )
    args = parser.parse_args()
    payload = {"split_invariance": asdict(run_split_invariance_fixture())}
    if args.coverage:
        payload["synthetic_importance_type1"] = asdict(
            run_importance_sampling_type1_fixture()
        )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
