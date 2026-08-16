#!/usr/bin/env python3
"""Research-only fitted-scale/null-topology falsifiers for issue #1166.

This module does not produce an authorising CCB p-value. It isolates two
nuisance-design questions in the equal-weight limit:

1. a scale fitted from the same sample must be re-estimated inside null
   replicates (or replaced by a genuinely held-out calibration design);
2. the fit/test membership graph matters: the current MC Sample I is a subset
   of Sample II, whereas canonical DATA Sample-I/II run families are disjoint.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json

import numpy as np

from tools.audit.research_weighted_null_cluster_contract import weighted_ecdf_distance


@dataclass(frozen=True)
class ScaleRefitCoverageResult:
    n_trials: int
    n_data: int
    n_model: int
    n_bootstrap: int
    seed: int
    true_scale_adc_per_model_unit: float
    alpha_005_fixed_rejection_fraction: float
    alpha_005_refit_rejection_fraction: float
    alpha_010_fixed_rejection_fraction: float
    alpha_010_refit_rejection_fraction: float
    mean_p_fixed: float
    mean_p_refit: float
    mean_observed_d: float
    mean_fixed_null_d: float
    mean_refit_null_d: float
    mean_scale_hat: float


@dataclass(frozen=True)
class OverlapTopologyResult:
    n_trials: int
    seed: int
    n_sample_ii: int
    sample_i_probability: float
    mean_sample_i_n: float
    corr_scale_mci_median_overlap: float
    corr_scale_mci_median_broken_independent: float
    mean_d_overlap: float
    mean_d_broken_independent: float
    q95_d_overlap: float
    q95_d_broken_independent: float


def _weighted_median(values, weights):
    x = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    if x.ndim != 1 or w.ndim != 1 or x.size != w.size or x.size == 0:
        raise ValueError("weighted median requires aligned nonempty 1D arrays")
    if not np.isfinite(x).all() or not np.isfinite(w).all() or np.any(w < 0):
        raise ValueError("weighted median requires finite values and nonnegative weights")
    if not float(np.sum(w)) > 0.0:
        raise ValueError("weighted median requires positive total weight")
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    ws = w[order]
    cumulative = np.cumsum(ws, dtype=float) / float(np.sum(ws))
    return float(xs[np.searchsorted(cumulative, 0.5, side="left")])


def median_ratio_scale(data, model, model_weights):
    """CCB-style Sample-II median ratio used as a research nuisance estimator."""
    data = np.asarray(data, dtype=float)
    if data.ndim != 1 or data.size == 0 or not np.isfinite(data).all():
        raise ValueError("data median requires a nonempty finite 1D array")
    model_ref = _weighted_median(model, model_weights)
    if model_ref == 0.0:
        raise ValueError("model weighted median must be nonzero")
    return float(np.median(data) / model_ref)


def run_scale_refit_type1_fixture(
    *,
    n_trials=200,
    n_data=80,
    n_model=160,
    n_bootstrap=99,
    seed=20260810,
    true_scale=90.0,
):
    """Compare fixed versus refitted nuisance calibration under a known null.

    DATA = true_scale * LogNormal(0, 0.5), MC = LogNormal(0, 0.5), with unit
    weights to isolate nuisance fitting from importance-weight semantics.
    """
    if min(n_trials, n_data, n_model, n_bootstrap) <= 0:
        raise ValueError("fixture counts must be positive")
    if n_data < 2 or n_model < 2 or not np.isfinite(true_scale) or true_scale <= 0:
        raise ValueError("fixture requires sample sizes >=2 and positive finite scale")

    p_fixed = []
    p_refit = []
    observed = []
    fixed_means = []
    refit_means = []
    scale_hats = []
    for trial in range(int(n_trials)):
        rng = np.random.default_rng(int(seed) + trial)
        model = rng.lognormal(0.0, 0.5, int(n_model))
        data = float(true_scale) * rng.lognormal(0.0, 0.5, int(n_data))
        model_weights = np.ones(model.size, dtype=float)
        data_weights = np.ones(data.size, dtype=float)
        scale_hat = median_ratio_scale(data, model, model_weights)
        d_obs = weighted_ecdf_distance(
            data, scale_hat * model, data_weights, model_weights
        )
        fixed = np.empty(int(n_bootstrap), dtype=float)
        refit = np.empty(int(n_bootstrap), dtype=float)
        for rep in range(int(n_bootstrap)):
            model_rep = rng.lognormal(0.0, 0.5, int(n_model))
            data_rep = scale_hat * rng.lognormal(0.0, 0.5, int(n_data))
            model_rep_weights = np.ones(model_rep.size, dtype=float)
            fixed[rep] = weighted_ecdf_distance(
                data_rep,
                scale_hat * model_rep,
                np.ones(data_rep.size, dtype=float),
                model_rep_weights,
            )
            scale_rep = median_ratio_scale(data_rep, model_rep, model_rep_weights)
            refit[rep] = weighted_ecdf_distance(
                data_rep,
                scale_rep * model_rep,
                np.ones(data_rep.size, dtype=float),
                model_rep_weights,
            )
        p_fixed.append(float((1 + np.count_nonzero(fixed >= d_obs)) / (n_bootstrap + 1)))
        p_refit.append(float((1 + np.count_nonzero(refit >= d_obs)) / (n_bootstrap + 1)))
        observed.append(d_obs)
        fixed_means.append(float(np.mean(fixed)))
        refit_means.append(float(np.mean(refit)))
        scale_hats.append(scale_hat)

    pf = np.asarray(p_fixed, dtype=float)
    pr = np.asarray(p_refit, dtype=float)
    return ScaleRefitCoverageResult(
        n_trials=int(n_trials),
        n_data=int(n_data),
        n_model=int(n_model),
        n_bootstrap=int(n_bootstrap),
        seed=int(seed),
        true_scale_adc_per_model_unit=float(true_scale),
        alpha_005_fixed_rejection_fraction=float(np.mean(pf <= 0.05)),
        alpha_005_refit_rejection_fraction=float(np.mean(pr <= 0.05)),
        alpha_010_fixed_rejection_fraction=float(np.mean(pf <= 0.10)),
        alpha_010_refit_rejection_fraction=float(np.mean(pr <= 0.10)),
        mean_p_fixed=float(np.mean(pf)),
        mean_p_refit=float(np.mean(pr)),
        mean_observed_d=float(np.mean(observed)),
        mean_fixed_null_d=float(np.mean(fixed_means)),
        mean_refit_null_d=float(np.mean(refit_means)),
        mean_scale_hat=float(np.mean(scale_hats)),
    )


def run_overlap_topology_fixture(
    *,
    n_trials=2000,
    n_sample_ii=160,
    sample_i_probability=0.4,
    seed=20260811,
    true_scale=90.0,
):
    """Show that preserving MC-I subset-of-MC-II changes the Sample-I null law."""
    if n_trials <= 0 or n_sample_ii < 2:
        raise ValueError("fixture requires positive trials and n_sample_ii >= 2")
    if not 0.0 < sample_i_probability < 1.0:
        raise ValueError("sample_i_probability must lie strictly between 0 and 1")

    scale_hats = []
    overlap_medians = []
    broken_medians = []
    overlap_d = []
    broken_d = []
    sample_i_counts = []
    for trial in range(int(n_trials)):
        rng = np.random.default_rng(int(seed) + trial)
        model_ii = rng.lognormal(0.0, 0.5, int(n_sample_ii))
        mask = rng.random(int(n_sample_ii)) < float(sample_i_probability)
        if np.count_nonzero(mask) < 2:
            continue
        model_i = model_ii[mask]
        n_i = int(model_i.size)
        model_i_broken = rng.lognormal(0.0, 0.5, n_i)
        data_ii = float(true_scale) * rng.lognormal(0.0, 0.5, int(n_sample_ii))
        data_i = float(true_scale) * rng.lognormal(0.0, 0.5, n_i)
        scale_hat = median_ratio_scale(
            data_ii, model_ii, np.ones(model_ii.size, dtype=float)
        )
        scale_hats.append(scale_hat)
        overlap_medians.append(float(np.median(model_i)))
        broken_medians.append(float(np.median(model_i_broken)))
        overlap_d.append(
            weighted_ecdf_distance(
                data_i,
                scale_hat * model_i,
                np.ones(data_i.size),
                np.ones(model_i.size),
            )
        )
        broken_d.append(
            weighted_ecdf_distance(
                data_i,
                scale_hat * model_i_broken,
                np.ones(data_i.size),
                np.ones(model_i_broken.size),
            )
        )
        sample_i_counts.append(n_i)

    scale_hats = np.asarray(scale_hats, dtype=float)
    overlap_d = np.asarray(overlap_d, dtype=float)
    broken_d = np.asarray(broken_d, dtype=float)
    return OverlapTopologyResult(
        n_trials=int(scale_hats.size),
        seed=int(seed),
        n_sample_ii=int(n_sample_ii),
        sample_i_probability=float(sample_i_probability),
        mean_sample_i_n=float(np.mean(sample_i_counts)),
        corr_scale_mci_median_overlap=float(
            np.corrcoef(scale_hats, np.asarray(overlap_medians))[0, 1]
        ),
        corr_scale_mci_median_broken_independent=float(
            np.corrcoef(scale_hats, np.asarray(broken_medians))[0, 1]
        ),
        mean_d_overlap=float(np.mean(overlap_d)),
        mean_d_broken_independent=float(np.mean(broken_d)),
        q95_d_overlap=float(np.quantile(overlap_d, 0.95)),
        q95_d_broken_independent=float(np.quantile(broken_d, 0.95)),
    )


def main():
    payload = {
        "status": "RESEARCH_ONLY_NONAUTHORISING",
        "issue": 1166,
        "same_sample_scale_refit": asdict(run_scale_refit_type1_fixture()),
        "fit_test_overlap_topology": asdict(run_overlap_topology_fixture()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
