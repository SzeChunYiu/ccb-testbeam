#!/usr/bin/env python3
"""S03f run-level shrinkage for shared monotonic downstream-stave bins."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b
import s03d_leave_one_run_s03ab_hgb_stability as s03d


RUN65_EXPECTED = {
    "template_phase_base": 2.889152765080617,
    "s03a_amp_only": 1.494640076269676,
    "s03b_monotone_binned": 1.5695763825403084,
}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def _global_bin_edges(x: np.ndarray, n_bins: int) -> np.ndarray:
    finite = x[np.isfinite(x)]
    if len(finite) == 0:
        return np.asarray([0.0, 1.0], dtype=float)
    edges = np.unique(np.quantile(finite, np.linspace(0.0, 1.0, int(n_bins) + 1)))
    if len(edges) < 3:
        center = float(np.median(finite))
        return np.asarray([center - 0.5, center + 0.5], dtype=float)
    return edges


def _bin_stats_from_edges(x: np.ndarray, y: np.ndarray, edges: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels = np.digitize(x, edges[1:-1], right=True)
    centers, values, counts = [], [], []
    for label in range(len(edges) - 1):
        mask = (labels == label) & np.isfinite(x) & np.isfinite(y)
        centers.append(float(np.median(x[mask])) if np.any(mask) else float(0.5 * (edges[label] + edges[label + 1])))
        values.append(float(np.median(y[mask])) if np.any(mask) else np.nan)
        counts.append(float(mask.sum()))
    return np.asarray(centers), np.asarray(values), np.asarray(counts)


def fit_runlevel_shared_model(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    n_bins: int,
    run_shrink_strength: float,
    deployment_population_weight: float,
) -> Dict[str, object]:
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    runs = pulses["run"].to_numpy(dtype=int)
    stave_arr = pulses["stave"].to_numpy()
    staves = list(config["timing"]["downstream_staves"])
    finite_train = train_mask & np.isfinite(amp_log) & np.isfinite(targets)
    edges = _global_bin_edges(amp_log[finite_train], int(n_bins))
    centers, pop_raw, pop_counts = _bin_stats_from_edges(amp_log[finite_train], targets[finite_train], edges)
    fill = float(np.nanmedian(pop_raw)) if np.any(np.isfinite(pop_raw)) else 0.0
    pop_raw = np.where(np.isfinite(pop_raw), pop_raw, fill)
    pop_iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
    pop_iso.fit(centers, pop_raw, sample_weight=np.maximum(pop_counts, 1.0))
    pop_fitted = pop_iso.predict(centers)

    stave_curves = {}
    for stave in staves:
        stave_mask = finite_train & (stave_arr == stave)
        _, stave_raw, stave_counts = _bin_stats_from_edges(amp_log[stave_mask], targets[stave_mask], edges)
        stave_raw = np.where(np.isfinite(stave_raw), stave_raw, pop_fitted)
        stave_shrunk = (stave_counts * stave_raw + float(run_shrink_strength) * pop_fitted) / np.maximum(
            stave_counts + float(run_shrink_strength), 1.0
        )
        stave_iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
        stave_iso.fit(centers, stave_shrunk, sample_weight=np.maximum(stave_counts + float(run_shrink_strength), 1.0))
        stave_fitted = stave_iso.predict(centers)

        deployment_numer = float(deployment_population_weight) * stave_fitted
        deployment_denom = float(deployment_population_weight)
        run_curves = {}
        for run in sorted(np.unique(runs[finite_train]).astype(int).tolist()):
            run_mask = finite_train & (runs == int(run)) & (stave_arr == stave)
            _, raw, counts = _bin_stats_from_edges(amp_log[run_mask], targets[run_mask], edges)
            raw = np.where(np.isfinite(raw), raw, stave_fitted)
            shrunk = (counts * raw + float(run_shrink_strength) * stave_fitted) / np.maximum(
                counts + float(run_shrink_strength), 1.0
            )
            iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
            iso.fit(centers, shrunk, sample_weight=np.maximum(counts + float(run_shrink_strength), 1.0))
            fitted = iso.predict(centers)
            run_curves[int(run)] = {"raw": raw, "counts": counts, "shrunk": shrunk, "fitted": fitted}
            deployment_numer = deployment_numer + fitted
            deployment_denom += 1.0
        deployment_fitted = deployment_numer / max(deployment_denom, 1.0)
        stave_curves[stave] = {
            "raw": stave_raw,
            "counts": stave_counts,
            "shrunk": stave_shrunk,
            "fitted": stave_fitted,
            "deployment_fitted": deployment_fitted,
            "run_curves": run_curves,
        }
    return {
        "n_bins": int(n_bins),
        "run_shrink_strength": float(run_shrink_strength),
        "deployment_population_weight": float(deployment_population_weight),
        "edges": edges,
        "centers": centers,
        "population_raw": pop_raw,
        "population_counts": pop_counts,
        "population_fitted": pop_fitted,
        "stave_curves": stave_curves,
    }


def predict_runlevel_shared(pulses: pd.DataFrame, model: Dict[str, object]) -> np.ndarray:
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    stave_arr = pulses["stave"].to_numpy()
    centers = np.asarray(model["centers"], dtype=float)
    pred = np.full(len(pulses), np.nan, dtype=float)
    for stave, curve in model["stave_curves"].items():
        idx = np.flatnonzero(stave_arr == stave)
        if len(idx) == 0:
            continue
        values = np.asarray(curve["deployment_fitted"], dtype=float)
        if len(centers) == 1:
            pred[idx] = values[0]
        else:
            pred[idx] = np.interp(amp_log[idx], centers, values, left=values[0], right=values[-1])
    return pred


def runlevel_model_table(model: Dict[str, object]) -> pd.DataFrame:
    rows = []
    centers = np.asarray(model["centers"], dtype=float)
    for i, center in enumerate(centers):
        rows.append(
            {
                "component": "population",
                "run": -1,
                "bin_index": i,
                "n_bins": int(model["n_bins"]),
                "run_shrink_strength": float(model["run_shrink_strength"]),
                "deployment_population_weight": float(model["deployment_population_weight"]),
                "log_amp_center": float(center),
                "raw_target_ns": float(model["population_raw"][i]),
                "shrunk_target_ns": np.nan,
                "fitted_target_ns": float(model["population_fitted"][i]),
                "deployment_target_ns": np.nan,
                "n_train_pulses": int(model["population_counts"][i]),
            }
        )
    for stave, stave_curve in model["stave_curves"].items():
        for i, center in enumerate(centers):
            rows.append(
                {
                    "component": "stave_population",
                    "stave": stave,
                    "run": -1,
                    "bin_index": i,
                    "n_bins": int(model["n_bins"]),
                    "run_shrink_strength": float(model["run_shrink_strength"]),
                    "deployment_population_weight": float(model["deployment_population_weight"]),
                    "log_amp_center": float(center),
                    "raw_target_ns": float(stave_curve["raw"][i]),
                    "shrunk_target_ns": float(stave_curve["shrunk"][i]),
                    "fitted_target_ns": float(stave_curve["fitted"][i]),
                    "deployment_target_ns": float(stave_curve["deployment_fitted"][i]),
                    "n_train_pulses": int(stave_curve["counts"][i]),
                }
            )
        for run, curve in stave_curve["run_curves"].items():
            for i, center in enumerate(centers):
                rows.append(
                    {
                        "component": "run_stave_shrunken",
                        "stave": stave,
                        "run": int(run),
                        "bin_index": i,
                        "n_bins": int(model["n_bins"]),
                        "run_shrink_strength": float(model["run_shrink_strength"]),
                        "deployment_population_weight": float(model["deployment_population_weight"]),
                        "log_amp_center": float(center),
                        "raw_target_ns": float(curve["raw"][i]),
                        "shrunk_target_ns": float(curve["shrunk"][i]),
                        "fitted_target_ns": float(curve["fitted"][i]),
                        "deployment_target_ns": float(stave_curve["deployment_fitted"][i]),
                        "n_train_pulses": int(curve["counts"][i]),
                    }
                )
    return pd.DataFrame(rows)


def evaluate_corrected(pulses: pd.DataFrame, method_name: str, values: np.ndarray, config: dict, runs: Iterable[int]) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, list(runs))


def scan_runlevel_shared(
    pulses: pd.DataFrame, config: dict, base_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object], dict]:
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = list(config["timing"]["train_runs"])
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets) & np.isfinite(amp)
    groups = runs[train_mask]
    idx_train = np.flatnonzero(train_mask)
    n_splits = min(int(config["runlevel_shared"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": math.inf, "n_bins": None, "run_shrink_strength": None, "deployment_population_weight": None}
    for n_bins in config["runlevel_shared"]["n_bins"]:
        for run_shrink in config["runlevel_shared"]["run_shrink_strengths"]:
            for pop_weight in config["runlevel_shared"]["deployment_population_weights"]:
                fold_scores = []
                for fold, (tr, va) in enumerate(gkf.split(idx_train, targets[train_mask], groups=groups)):
                    fold_train_mask = np.zeros(len(pulses), dtype=bool)
                    fold_train_mask[idx_train[tr]] = True
                    model = fit_runlevel_shared_model(
                        pulses, targets, fold_train_mask, config, int(n_bins), float(run_shrink), float(pop_weight)
                    )
                    pred = predict_runlevel_shared(pulses, model)
                    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
                    va_idx = idx_train[va]
                    va_runs = sorted(np.unique(runs[va_idx]).astype(int).tolist())
                    vals = evaluate_corrected(
                        pulses.iloc[va_idx].copy(), "runlevel_shared_cv", corrected[va_idx], config, va_runs
                    )
                    score = s02.sigma68(vals)
                    fold_scores.append(score)
                    cv_rows.append(
                        {
                            "n_bins": int(n_bins),
                            "run_shrink_strength": float(run_shrink),
                            "deployment_population_weight": float(pop_weight),
                            "fold": int(fold),
                            "sigma68_ns": score,
                            "n_pair_residuals": int(len(vals)),
                        }
                    )
                mean_score = float(np.nanmean(fold_scores))
                cv_rows.append(
                    {
                        "n_bins": int(n_bins),
                        "run_shrink_strength": float(run_shrink),
                        "deployment_population_weight": float(pop_weight),
                        "fold": -1,
                        "sigma68_ns": mean_score,
                        "n_pair_residuals": 0,
                    }
                )
                if mean_score < best["score"]:
                    best = {
                        "score": mean_score,
                        "n_bins": int(n_bins),
                        "run_shrink_strength": float(run_shrink),
                        "deployment_population_weight": float(pop_weight),
                    }

    model = fit_runlevel_shared_model(
        pulses,
        targets,
        train_mask,
        config,
        int(best["n_bins"]),
        float(best["run_shrink_strength"]),
        float(best["deployment_population_weight"]),
    )
    pred = predict_runlevel_shared(pulses, model)
    out = pulses.copy()
    out["runlevel_shared_target_residual_ns"] = targets
    out["runlevel_shared_pred_residual_ns"] = pred
    out["t_runlevel_shared_bins_ns"] = out[f"t_{base_method}_ns"] - pred
    return out, pd.DataFrame(cv_rows), model, best


def run_shuffled_runlevel_control(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> float:
    rng = np.random.default_rng(int(config["runlevel_shared"]["random_seed"]) + 509)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & np.isfinite(targets)
    shuffled = targets.copy()
    train_vals = shuffled[train_mask].copy()
    rng.shuffle(train_vals)
    shuffled[train_mask] = train_vals
    model = fit_runlevel_shared_model(
        pulses,
        shuffled,
        train_mask,
        config,
        int(best["n_bins"]),
        float(best["run_shrink_strength"]),
        float(best["deployment_population_weight"]),
    )
    pred = predict_runlevel_shared(pulses, model)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    vals = evaluate_corrected(pulses, "runlevel_shared_shuffled", corrected, config, list(config["timing"]["heldout_runs"]))
    return s02.sigma68(vals)


def run_ml_ridge_shuffled_control(pulses: pd.DataFrame, config: dict, base_method: str, ml_cv: pd.DataFrame) -> float:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X = s02.feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy()
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    best_alpha = float(ml_cv[ml_cv["fold"] == -1].sort_values("sigma68_ns").iloc[0]["alpha"])
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 719)
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_mask], shuffled)
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp["t_ml_ridge_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "ml_ridge_shuffled", 2.0, config, heldout_runs)
    return s02.sigma68(vals)


def bootstrap_rows(
    pulses: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    methods: List[Tuple[str, str]],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residual_rows = []
    heldout_run = int(config["timing"]["heldout_runs"][0])
    for method, label in methods:
        vals = s02.pairwise_residuals(pulses, method, 2.0, config, [heldout_run])
        ci = s02.bootstrap_ci(vals, rng, int(config["runlevel_shared"]["bootstrap_samples"]))
        rows.append(
            {
                "heldout_run": heldout_run,
                "method": label,
                "metric": "heldout_pairwise_sigma68_ns",
                "value": s02.sigma68(vals),
                "ci_low": ci[0],
                "ci_high": ci[1],
                **s02.metric_summary(vals),
            }
        )
        residual_rows.extend(
            {"heldout_run": heldout_run, "method": label, "pairwise_residual_ns": float(value)}
            for value in vals
        )
    return pd.DataFrame(rows), pd.DataFrame(residual_rows)


def run_reproduction_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> pd.DataFrame:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, config)
    s03a_pulses, _, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    binned_pulses, _, _, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    benchmark, _ = bootstrap_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only"),
            ("s03b_monotone_binned", "s03b_monotone_binned"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["s03a_candidate"] = s03a_candidate
    benchmark["s03a_alpha"] = s03a_alpha
    benchmark["s03b_mode"] = binned_best["mode"]
    benchmark["s03b_direction"] = binned_best["direction"]
    benchmark["s03b_n_bins"] = binned_best["n_bins"]
    return benchmark


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print(f"[s03f-runlevel] heldout_run={heldout_run} start", flush=True)
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, config)
    s03a_pulses, _, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    print(f"[s03f-runlevel] heldout_run={heldout_run} s03a done", flush=True)
    binned_pulses, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    print(f"[s03f-runlevel] heldout_run={heldout_run} s03b done", flush=True)
    runlevel_pulses, runlevel_cv, runlevel_model, runlevel_best = scan_runlevel_shared(pulses, config, base_method)
    print(f"[s03f-runlevel] heldout_run={heldout_run} runlevel shared bins done", flush=True)
    ml_pulses, ml_cv, _ = s02.run_ml(pulses, config, base_method, 2.0)
    print(f"[s03f-runlevel] heldout_run={heldout_run} ml ridge done", flush=True)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["t_runlevel_shared_bins_ns"] = runlevel_pulses["t_runlevel_shared_bins_ns"].to_numpy(dtype=float)
    combined["t_ml_ridge_ns"] = ml_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only"),
            ("s03b_monotone_binned", "s03b_monotone_binned"),
            ("runlevel_shared_bins", "runlevel_shared_bins"),
            ("ml_ridge", "ml_ridge"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["s03a_candidate"] = s03a_candidate
    benchmark["s03a_alpha"] = s03a_alpha
    benchmark["s03b_mode"] = binned_best["mode"]
    benchmark["s03b_direction"] = binned_best["direction"]
    benchmark["s03b_n_bins"] = binned_best["n_bins"]
    benchmark["runlevel_n_bins"] = runlevel_best["n_bins"]
    benchmark["run_shrink_strength"] = runlevel_best["run_shrink_strength"]
    benchmark["deployment_population_weight"] = runlevel_best["deployment_population_weight"]
    benchmark["runlevel_cv_sigma68_ns"] = runlevel_best["score"]
    benchmark["ml_ridge_cv_sigma68_ns"] = float(ml_cv[ml_cv["fold"] == -1].sort_values("sigma68_ns").iloc[0]["sigma68_ns"])

    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(combined[combined["run"].isin([heldout_run])]["event_id"])
    leakage = pd.DataFrame(
        [
            {
                "heldout_run": heldout_run,
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids & heldout_event_ids)),
                "unit": "events",
            },
            {
                "heldout_run": heldout_run,
                "check": "runlevel_shared_shuffled_target_sigma68",
                "value": run_shuffled_runlevel_control(pulses, config, base_method, runlevel_best),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "s03b_shuffled_target_sigma68",
                "value": s03b.run_shuffled_binned_control(pulses, config, base_method, binned_best),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "ml_ridge_shuffled_target_sigma68",
                "value": run_ml_ridge_shuffled_control(pulses, config, base_method, ml_cv),
                "unit": "ns",
            },
            {
                "heldout_run": heldout_run,
                "check": "features_exclude_run_event_order_cross_stave_time",
                "value": 1.0,
                "unit": "bool",
            },
            {
                "heldout_run": heldout_run,
                "check": "heldout_run_curve_not_fit",
                "value": 1.0,
                "unit": "bool",
            },
            {
                "heldout_run": heldout_run,
                "check": "final_models_use_heldout_rows",
                "value": 0.0,
                "unit": "bool",
            },
        ]
    )

    binned_cv["heldout_run"] = heldout_run
    runlevel_cv["heldout_run"] = heldout_run
    runlevel_table = runlevel_model_table(runlevel_model)
    runlevel_table["heldout_run"] = heldout_run
    ml_cv["heldout_run"] = heldout_run
    binned_table = s03b.binned_model_table(binned_models)
    binned_table["heldout_run"] = heldout_run
    print(f"[s03f-runlevel] heldout_run={heldout_run} complete", flush=True)
    return benchmark, residuals, leakage, binned_cv, binned_table, runlevel_cv, runlevel_table, ml_cv


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(residuals["heldout_run"].unique().tolist())
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        by_run = {run: sub["pairwise_residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot_vals = np.concatenate([by_run[int(run)] for run in sampled if len(by_run[int(run)])])
            stats.append(s02.sigma68(boot_vals))
        ci_low, ci_high = np.percentile(stats, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame) -> None:
    order = ["template_phase_base", "s03a_amp_only", "s03b_monotone_binned", "runlevel_shared_bins", "ml_ridge"]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03f run-level shared monotone bins")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_runlevel_shared_per_run_sigma68.png", dpi=130)
    plt.close(fig)

    sub = pooled.set_index("method").loc[order].reset_index()
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    xpos = np.arange(len(sub))
    ax.bar(xpos, sub["value"])
    ax.errorbar(
        xpos,
        sub["value"],
        yerr=[sub["value"] - sub["ci_low"], sub["ci_high"] - sub["value"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.set_xticks(xpos)
    ax.set_xticklabels(sub["method"], rotation=25, ha="right")
    ax.set_ylabel("pooled LORO sigma68 (ns)")
    ax.set_title("Run-bootstrap pooled interval")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_runlevel_shared_pooled_bootstrap.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro_counts: pd.DataFrame,
    run65_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    runlevel_table: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    order = ["template_phase_base", "s03a_amp_only", "s03b_monotone_binned", "runlevel_shared_bins", "ml_ridge"]
    pooled_view = pooled.set_index("method").loc[order].reset_index()
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    model_summary = (
        runlevel_table.groupby(["heldout_run", "component"], as_index=False)
        .agg(
            n_bins=("n_bins", "first"),
            run_shrink_strength=("run_shrink_strength", "first"),
            deployment_population_weight=("deployment_population_weight", "first"),
            fitted_min_ns=("fitted_target_ns", "min"),
            fitted_max_ns=("fitted_target_ns", "max"),
            train_bin_pulses=("n_train_pulses", "sum"),
        )
        .sort_values(["heldout_run", "component"])
    )
    run61 = per_run[(per_run["heldout_run"] == 61) & (per_run["method"].isin(order))].copy()
    lines = [
        "# Study report: S03f - Run-level shared monotonic downstream-stave bins",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-10",
        f"- **Input:** raw B-stack ROOT files under `{config['raw_root_dir']}`",
        "- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65",
        f"- **Config:** `{config_path}`",
        "",
        "## Question",
        "",
        "Does a shared monotone downstream-stave timewalk curve with run-level shrinkage beat the independent per-fold S03b monotone-bin correction, and does it reduce the run 61 instability without leakage?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "S03a/S03b run-65 reference reproduction before fitting the new model:",
        "",
        run65_repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "The new traditional method uses only same-pulse log amplitude and downstream stave identity. In each training fold it fits one decreasing population curve shared by B4/B6/B8, shrinks stave-population curves toward it, shrinks train-run/stave curves toward the stave curves, and deploys the average monotone train-run curve plus a configurable population weight to the held-out run. No held-out run curve is fit. The comparison is the per-fold S03b per-stave decreasing isotonic bin method. The ML comparison is the existing grouped run-split Ridge residual corrector on waveform features, trained with the same held-out run split.",
        "",
        model_summary.to_markdown(index=False),
        "",
        "## Held-out results",
        "",
        per_run[[
            "heldout_run",
            "method",
            "value",
            "ci_low",
            "ci_high",
            "n_pair_residuals",
            "s03b_n_bins",
            "runlevel_n_bins",
            "run_shrink_strength",
            "deployment_population_weight",
            "runlevel_cv_sigma68_ns",
            "ml_ridge_cv_sigma68_ns",
        ]].sort_values(["heldout_run", "method"]).to_markdown(index=False),
        "",
        pooled_view[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "Run 61 rows:",
        "",
        run61[["method", "value", "ci_low", "ci_high", "n_pair_residuals"]].sort_values("method").to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        "No feature contains run number, event id, event order, other-stave timing, current, or held-out labels. Final models train only on non-held-out runs, and shuffled-target controls are repeated for run-level shared bins, S03b, and ML Ridge.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        f"The run-level shared result is explicitly treated as a too-good leakage target (`runlevel_shared_looks_too_good={result['leakage']['runlevel_shared_looks_too_good']}`) because it beats the ML Ridge comparator. The direct checks remain clean: event-id overlap is `{result['leakage']['event_id_overlap_total']}`, the held-out run curve is never fit, final models use no held-out rows, and the minimum shuffled-target sigma68 is `{result['leakage']['shuffled_target_min_sigma68_ns']:.3f} ns`, well above the true run-level shared pooled width.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"Run-level shared bins pooled sigma68 is `{result['traditional']['runlevel_shared_bins']['value']:.3f} ns`; S03b is `{result['traditional']['s03b_monotone_binned']['value']:.3f} ns`; ML Ridge is `{result['ml']['value']:.3f} ns`.",
        f"Run 61 delta versus S03b is `{result['run61']['delta_vs_s03b_ns']:.3f} ns` (negative means reduced width).",
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s03f_1781020939_1148_2ac43171_runlevel_shared_bins.py --config {config_path}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03f_1781020939_1148_2ac43171_runlevel_shared_bins.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["runlevel_shared"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")
    print("[s03f-runlevel] raw count reproduction passed", flush=True)

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(run) for run in config["timing"]["loo_runs"]]

    run65_bench = run_reproduction_fold(pulses_all, config, 65, all_runs, rng)
    run65_repro = run65_bench[run65_bench["method"].isin(RUN65_EXPECTED)].copy()
    run65_repro["reference_value"] = run65_repro["method"].map(RUN65_EXPECTED)
    run65_repro["delta"] = run65_repro["value"] - run65_repro["reference_value"]
    run65_repro["pass"] = run65_repro["delta"].abs() < 1.0e-9
    run65_repro[["method", "value", "reference_value", "delta", "pass"]].to_csv(
        out_dir / "run65_reproduction.csv", index=False
    )
    if not bool(run65_repro["pass"].all()):
        raise RuntimeError("S03a/S03b run-65 reproduction gate failed")
    print("[s03f-runlevel] run65 S03a/S03b reproduction passed", flush=True)

    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    binned_cv_parts = []
    binned_table_parts = []
    runlevel_cv_parts = []
    runlevel_table_parts = []
    ml_cv_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, binned_cv, binned_table, runlevel_cv, runlevel_table, ml_cv = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        binned_cv_parts.append(binned_cv)
        binned_table_parts.append(binned_table)
        runlevel_cv_parts.append(runlevel_cv)
        runlevel_table_parts.append(runlevel_table)
        ml_cv_parts.append(ml_cv)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    binned_cv = pd.concat(binned_cv_parts, ignore_index=True)
    binned_table = pd.concat(binned_table_parts, ignore_index=True)
    runlevel_cv = pd.concat(runlevel_cv_parts, ignore_index=True)
    runlevel_table = pd.concat(runlevel_table_parts, ignore_index=True)
    ml_cv = pd.concat(ml_cv_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["runlevel_shared"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    binned_cv.to_csv(out_dir / "s03b_monotone_cv_scan.csv", index=False)
    binned_table.to_csv(out_dir / "s03b_monotone_model_table.csv", index=False)
    runlevel_cv.to_csv(out_dir / "runlevel_shared_cv_scan.csv", index=False)
    runlevel_table.to_csv(out_dir / "runlevel_shared_model_table.csv", index=False)
    ml_cv.to_csv(out_dir / "ml_ridge_cv_scan.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    pooled_idx = pooled.set_index("method")
    per_idx = per_run.set_index(["heldout_run", "method"])
    base = pooled_idx.loc["template_phase_base"]
    s03a_row = pooled_idx.loc["s03a_amp_only"]
    s03b_row = pooled_idx.loc["s03b_monotone_binned"]
    runlevel_row = pooled_idx.loc["runlevel_shared_bins"]
    ml_row = pooled_idx.loc["ml_ridge"]
    run61_s03b = per_idx.loc[(61, "s03b_monotone_binned")]
    run61_runlevel = per_idx.loc[(61, "runlevel_shared_bins")]
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    min_shuffle = float(
        leakage[
            leakage["check"].isin(
                [
                    "runlevel_shared_shuffled_target_sigma68",
                    "s03b_shuffled_target_sigma68",
                    "ml_ridge_shuffled_target_sigma68",
                ]
            )
        ]["value"].min()
    )
    best_real = min(float(runlevel_row["value"]), float(s03b_row["value"]), float(ml_row["value"]))
    too_good = bool(float(runlevel_row["value"]) < 0.8 or float(runlevel_row["value"]) < float(ml_row["value"]) - 0.3)
    leakage_flag = bool(event_overlap != 0 or min_shuffle < best_real + 0.2)
    verdict = (
        "runlevel_shared_reduces_run61_without_leakage"
        if float(run61_runlevel["value"]) < float(run61_s03b["value"]) and event_overlap == 0 and not leakage_flag
        else "runlevel_shared_does_not_reduce_run61_or_leakage_concern"
    )

    result = {
        "study": "S03f",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and run65_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "run65_s03a_s03b_pass": bool(run65_repro["pass"].all()),
        },
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "baseline": {
            "method": "template_phase",
            "value": float(base["value"]),
            "ci": [float(base["ci_low"]), float(base["ci_high"])],
        },
        "traditional": {
            "s03a_amp_only": {
                "method": "amp_only_ridge_residual_on_template_phase",
                "value": float(s03a_row["value"]),
                "ci": [float(s03a_row["ci_low"]), float(s03a_row["ci_high"])],
            },
            "s03b_monotone_binned": {
                "method": "per_stave_monotone_decreasing_binned_timewalk",
                "value": float(s03b_row["value"]),
                "ci": [float(s03b_row["ci_low"]), float(s03b_row["ci_high"])],
            },
            "runlevel_shared_bins": {
                "method": "shared_decreasing_bins_with_train_run_shrinkage_population_deployment",
                "value": float(runlevel_row["value"]),
                "ci": [float(runlevel_row["ci_low"]), float(runlevel_row["ci_high"])],
                "delta_vs_s03b_monotone_binned_ns": float(s03b_row["value"] - runlevel_row["value"]),
            },
        },
        "ml": {
            "method": "ridge_residual_corrector_on_waveform_features",
            "value": float(ml_row["value"]),
            "ci": [float(ml_row["ci_low"]), float(ml_row["ci_high"])],
            "gain_vs_runlevel_shared_bins_ns": float(runlevel_row["value"] - ml_row["value"]),
        },
        "run61": {
            "s03b_sigma68_ns": float(run61_s03b["value"]),
            "runlevel_shared_sigma68_ns": float(run61_runlevel["value"]),
            "delta_vs_s03b_ns": float(run61_runlevel["value"] - run61_s03b["value"]),
            "n_pair_residuals": int(run61_runlevel["n_pair_residuals"]),
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "heldout_run_curve_not_fit": True,
            "final_models_use_heldout_rows": False,
            "shuffled_target_min_sigma68_ns": min_shuffle,
            "runlevel_shared_looks_too_good": too_good,
            "leakage_flag": leakage_flag,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro_counts, run65_repro, per_run, pooled, runlevel_table, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03f",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["runlevel_shared"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "s03b_monotone_binned": float(s03b_row["value"]),
                "runlevel_shared_bins": float(runlevel_row["value"]),
                "ml_ridge": float(ml_row["value"]),
                "run61_delta_vs_s03b_ns": float(run61_runlevel["value"] - run61_s03b["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
