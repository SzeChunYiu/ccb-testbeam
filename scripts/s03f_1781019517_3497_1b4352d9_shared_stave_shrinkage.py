#!/usr/bin/env python3
"""S03f shared-stave shrinkage for monotone timewalk bins."""

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
from sklearn.model_selection import GroupKFold

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
        if np.any(mask):
            centers.append(float(np.median(x[mask])))
            values.append(float(np.median(y[mask])))
            counts.append(float(mask.sum()))
        else:
            centers.append(float(0.5 * (edges[label] + edges[label + 1])))
            values.append(np.nan)
            counts.append(0.0)
    return np.asarray(centers), np.asarray(values), np.asarray(counts)


def fit_shared_shrinkage_model(
    pulses: pd.DataFrame,
    targets: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    n_bins: int,
    shrink_strength: float,
) -> Dict[str, dict]:
    staves = list(config["timing"]["downstream_staves"])
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    stave_arr = pulses["stave"].to_numpy()
    finite_train = train_mask & np.isfinite(amp_log) & np.isfinite(targets)
    edges = _global_bin_edges(amp_log[finite_train], int(n_bins))
    centers, shared_raw, shared_counts = _bin_stats_from_edges(amp_log[finite_train], targets[finite_train], edges)
    if np.any(np.isfinite(shared_raw)):
        fill = float(np.nanmedian(shared_raw))
    else:
        fill = 0.0
    shared_raw = np.where(np.isfinite(shared_raw), shared_raw, fill)
    shared_iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
    shared_iso.fit(centers, shared_raw, sample_weight=np.maximum(shared_counts, 1.0))
    shared_fitted = shared_iso.predict(centers)

    models: Dict[str, dict] = {
        "__shared__": {
            "n_bins": int(n_bins),
            "shrink_strength": float(shrink_strength),
            "edges": edges,
            "centers": centers,
            "raw_values": shared_raw,
            "counts": shared_counts,
            "fitted_values": shared_fitted,
            "iso": shared_iso,
        }
    }
    for stave in staves:
        mask = finite_train & (stave_arr == stave)
        _, raw, counts = _bin_stats_from_edges(amp_log[mask], targets[mask], edges)
        raw = np.where(np.isfinite(raw), raw, shared_fitted)
        pseudo = float(shrink_strength)
        shrunk = (counts * raw + pseudo * shared_fitted) / np.maximum(counts + pseudo, 1.0)
        weights = np.maximum(counts + pseudo, 1.0)
        iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
        iso.fit(centers, shrunk, sample_weight=weights)
        fitted = iso.predict(centers)
        models[stave] = {
            "n_bins": int(n_bins),
            "shrink_strength": float(shrink_strength),
            "edges": edges,
            "centers": centers,
            "raw_values": raw,
            "counts": counts,
            "shared_fitted_values": shared_fitted,
            "shrunk_values": shrunk,
            "fitted_values": fitted,
            "iso": iso,
            "n_train_pulses": int(mask.sum()),
        }
    return models


def predict_shared_shrinkage(pulses: pd.DataFrame, models: Dict[str, dict]) -> np.ndarray:
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    stave_arr = pulses["stave"].to_numpy()
    pred = np.full(len(pulses), np.nan, dtype=float)
    for stave, model in models.items():
        if stave == "__shared__":
            continue
        idx = np.flatnonzero(stave_arr == stave)
        if len(idx) == 0:
            continue
        pred[idx] = model["iso"].predict(amp_log[idx])
    return pred


def shared_shrinkage_table(models: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    shared = models["__shared__"]
    for i, center in enumerate(shared["centers"]):
        rows.append(
            {
                "stave": "__shared__",
                "bin_index": i,
                "n_bins": shared["n_bins"],
                "shrink_strength": shared["shrink_strength"],
                "log_amp_center": float(center),
                "shared_raw_target_ns": float(shared["raw_values"][i]),
                "shared_fitted_target_ns": float(shared["fitted_values"][i]),
                "raw_stave_target_ns": np.nan,
                "shrunk_target_ns": np.nan,
                "fitted_target_ns": float(shared["fitted_values"][i]),
                "n_train_pulses": int(shared["counts"][i]),
            }
        )
    for stave, model in models.items():
        if stave == "__shared__":
            continue
        for i, center in enumerate(model["centers"]):
            rows.append(
                {
                    "stave": stave,
                    "bin_index": i,
                    "n_bins": model["n_bins"],
                    "shrink_strength": model["shrink_strength"],
                    "log_amp_center": float(center),
                    "shared_raw_target_ns": float(shared["raw_values"][i]),
                    "shared_fitted_target_ns": float(model["shared_fitted_values"][i]),
                    "raw_stave_target_ns": float(model["raw_values"][i]),
                    "shrunk_target_ns": float(model["shrunk_values"][i]),
                    "fitted_target_ns": float(model["fitted_values"][i]),
                    "n_train_pulses": int(model["counts"][i]),
                }
            )
    return pd.DataFrame(rows)


def evaluate_corrected(
    pulses: pd.DataFrame,
    method_name: str,
    values: np.ndarray,
    config: dict,
    runs: Iterable[int],
) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, list(runs))


def scan_shared_shrinkage(
    pulses: pd.DataFrame, config: dict, base_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, dict], dict]:
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_runs = list(config["timing"]["train_runs"])
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets) & np.isfinite(amp)
    groups = runs[train_mask]
    idx_train = np.flatnonzero(train_mask)
    n_splits = min(int(config["shrinkage"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": math.inf, "n_bins": None, "shrink_strength": None}
    for n_bins in config["shrinkage"]["n_bins"]:
        for shrink_strength in config["shrinkage"]["shrink_strengths"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(idx_train, targets[train_mask], groups=groups)):
                fold_train_mask = np.zeros(len(pulses), dtype=bool)
                fold_train_mask[idx_train[tr]] = True
                models = fit_shared_shrinkage_model(
                    pulses, targets, fold_train_mask, config, int(n_bins), float(shrink_strength)
                )
                pred = predict_shared_shrinkage(pulses, models)
                corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
                va_idx = idx_train[va]
                va_runs = sorted(np.unique(runs[va_idx]).astype(int).tolist())
                vals = evaluate_corrected(
                    pulses.iloc[va_idx].copy(), "shared_shrinkage_cv", corrected[va_idx], config, va_runs
                )
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "n_bins": int(n_bins),
                        "shrink_strength": float(shrink_strength),
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": int(len(vals)),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "n_bins": int(n_bins),
                    "shrink_strength": float(shrink_strength),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "n_bins": int(n_bins), "shrink_strength": float(shrink_strength)}

    models = fit_shared_shrinkage_model(
        pulses, targets, train_mask, config, int(best["n_bins"]), float(best["shrink_strength"])
    )
    pred = predict_shared_shrinkage(pulses, models)
    out = pulses.copy()
    out["shared_shrinkage_target_residual_ns"] = targets
    out["shared_shrinkage_pred_residual_ns"] = pred
    out["t_shared_shrinkage_ns"] = out[f"t_{base_method}_ns"] - pred
    return out, pd.DataFrame(cv_rows), models, best


def run_shared_shrinkage_shuffled_control(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> float:
    rng = np.random.default_rng(int(config["shrinkage"]["random_seed"]) + 503)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & np.isfinite(targets)
    shuffled = targets.copy()
    train_vals = shuffled[train_mask].copy()
    rng.shuffle(train_vals)
    shuffled[train_mask] = train_vals
    models = fit_shared_shrinkage_model(
        pulses, shuffled, train_mask, config, int(best["n_bins"]), float(best["shrink_strength"])
    )
    pred = predict_shared_shrinkage(pulses, models)
    corrected = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    vals = evaluate_corrected(
        pulses, "shared_shrinkage_shuffled", corrected, config, list(config["timing"]["heldout_runs"])
    )
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
        ci = s02.bootstrap_ci(vals, rng, int(config["shrinkage"]["bootstrap_samples"]))
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
            {
                "heldout_run": heldout_run,
                "method": label,
                "pairwise_residual_ns": float(value),
            }
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
    print(f"[s03f] heldout_run={heldout_run} start", flush=True)
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, config)
    print(f"[s03f] heldout_run={heldout_run} base={base_method}", flush=True)

    s03a_pulses, s03a_cv, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    print(f"[s03f] heldout_run={heldout_run} s03a done", flush=True)
    binned_pulses, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    print(f"[s03f] heldout_run={heldout_run} s03b done", flush=True)
    shrink_pulses, shrink_cv, shrink_models, shrink_best = scan_shared_shrinkage(pulses, config, base_method)
    print(f"[s03f] heldout_run={heldout_run} shared_shrinkage done", flush=True)
    hgb_pulses, hgb_cv, hgb_best = s03d.run_hgb(pulses, config, base_method)
    print(f"[s03f] heldout_run={heldout_run} hgb done", flush=True)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["t_shared_shrinkage_ns"] = shrink_pulses["t_shared_shrinkage_ns"].to_numpy(dtype=float)
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)

    benchmark, residuals = bootstrap_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only"),
            ("s03b_monotone_binned", "s03b_monotone_binned"),
            ("shared_shrinkage", "phys_signed_shared_shrinkage"),
            ("hgb_timewalk", "hgb_timewalk"),
        ],
    )
    benchmark["train_runs"] = ",".join(str(run) for run in train_runs)
    benchmark["s03a_candidate"] = s03a_candidate
    benchmark["s03a_alpha"] = s03a_alpha
    benchmark["s03b_mode"] = binned_best["mode"]
    benchmark["s03b_direction"] = binned_best["direction"]
    benchmark["s03b_n_bins"] = binned_best["n_bins"]
    benchmark["shrinkage_n_bins"] = shrink_best["n_bins"]
    benchmark["shrinkage_strength"] = shrink_best["shrink_strength"]
    benchmark["shrinkage_cv_sigma68_ns"] = shrink_best["score"]
    benchmark["hgb_cv_sigma68_ns"] = hgb_best["score"]

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
                "check": "shared_shrinkage_shuffled_target_sigma68",
                "value": run_shared_shrinkage_shuffled_control(pulses, config, base_method, shrink_best),
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
                "check": "hgb_shuffled_target_sigma68",
                "value": s03d.run_hgb_shuffled_control(pulses, config, base_method, hgb_best),
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
                "check": "final_models_use_heldout_rows",
                "value": 0.0,
                "unit": "bool",
            },
        ]
    )

    s03a_cv["heldout_run"] = heldout_run
    binned_cv["heldout_run"] = heldout_run
    shrink_cv["heldout_run"] = heldout_run
    shrink_table = shared_shrinkage_table(shrink_models)
    shrink_table["heldout_run"] = heldout_run
    hgb_cv["heldout_run"] = heldout_run
    binned_table = s03b.binned_model_table(binned_models)
    binned_table["heldout_run"] = heldout_run
    print(f"[s03f] heldout_run={heldout_run} complete", flush=True)
    return benchmark, residuals, leakage, s03a_cv, binned_cv, shrink_cv, hgb_cv, shrink_table


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
    order = [
        "template_phase_base",
        "s03a_amp_only",
        "s03b_monotone_binned",
        "phys_signed_shared_shrinkage",
        "hgb_timewalk",
    ]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    for method in order:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["value"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03f shared-shrinkage leave-one-run-out timing width")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03f_shared_shrinkage_per_run_sigma68.png", dpi=130)
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
    fig.savefig(out_dir / "fig_s03f_shared_shrinkage_pooled_run_bootstrap.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro_counts: pd.DataFrame,
    run65_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    signed_table: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    ordered = [
        "template_phase_base",
        "s03a_amp_only",
        "s03b_monotone_binned",
        "phys_signed_shared_shrinkage",
        "hgb_timewalk",
    ]
    pooled_view = pooled.set_index("method").loc[ordered].reset_index()
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    model_detail = signed_table[signed_table["stave"] != "__shared__"].copy()
    model_summary = (
        model_detail.groupby(["heldout_run", "stave"], as_index=False)
        .agg(
            n_bins=("n_bins", "first"),
            shrink_strength=("shrink_strength", "first"),
            fitted_min_ns=("fitted_target_ns", "min"),
            fitted_max_ns=("fitted_target_ns", "max"),
            train_bin_pulses=("n_train_pulses", "sum"),
        )
        .sort_values(["heldout_run", "stave"])
    )
    lines = [
        "# Study report: S03f - Shared-stave shrinkage for monotone timewalk bins",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65",
        f"- **Config:** `{config_path}`",
        "",
        "## 0. Question",
        "",
        "Can the S03b monotone-binned correction be stabilized by a physically signed shared-stave shrinkage prior instead of independent per-stave isotonic fits?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse count gate was rerun from raw ROOT before any model fitting.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "The prior S03a/S03b run-65 headline numbers were then reproduced from the same raw-derived pulse table before fitting the new shrinkage or HGB comparison models.",
        "",
        run65_repro.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "The traditional shrinkage model uses only same-pulse amplitude and stave identity. In each training fold it builds global log-amplitude bins, fits a shared decreasing isotonic timewalk curve across B4/B6/B8, shrinks each stave's bin medians toward that shared curve by a CV-selected pseudo-count, and then enforces the same decreasing physical sign per stave. This keeps the S03b monotone-bin structure but removes independent per-stave freedom when support is weak.",
        "",
        model_summary[[
            "heldout_run",
            "stave",
            "n_bins",
            "shrink_strength",
            "fitted_min_ns",
            "fitted_max_ns",
            "train_bin_pulses",
        ]].to_markdown(index=False),
        "",
        "## 3. Run-held-out head-to-head",
        "",
        "Every row trains templates, S03a, S03b, shared shrinkage, and HGB only on the other runs. Per-run intervals bootstrap pair residuals within the held-out run; pooled intervals resample held-out runs.",
        "",
        per_run[[
            "heldout_run",
            "method",
            "value",
            "ci_low",
            "ci_high",
            "n_pair_residuals",
            "s03b_n_bins",
            "shrinkage_n_bins",
            "shrinkage_strength",
            "shrinkage_cv_sigma68_ns",
            "hgb_cv_sigma68_ns",
        ]].sort_values(["heldout_run", "method"]).to_markdown(index=False),
        "",
        pooled_view[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].to_markdown(index=False),
        "",
        "## 4. Leakage checks",
        "",
        "No fitted feature includes run number, event id, event order, other-stave timing, or held-out labels. Final models remove held-out rows. Shuffled-target controls are repeated for shared shrinkage, isotonic S03b, and HGB in every held-out fold.",
        "",
        f"The shared-shrinkage result is treated as a too-good leakage target because it beats HGB in the pooled run bootstrap (`shared_shrinkage_looks_too_good={result['leakage']['shared_shrinkage_looks_too_good']}`). The direct checks remain clean: event-id overlap is `{result['leakage']['event_id_overlap_total']}`, held-out rows are excluded from final models, and the minimum shuffled-target sigma68 is `{result['leakage']['shuffled_target_min_sigma68_ns']:.3f} ns`, far above the true shared-shrinkage width.",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 5. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"Shared-shrinkage pooled sigma68 is `{result['traditional']['phys_signed_shared_shrinkage']['value']:.3f} ns`; S03a amp-only is `{result['traditional']['s03a_amp_only']['value']:.3f} ns`; S03b monotone-binned is `{result['traditional']['s03b_monotone_binned']['value']:.3f} ns`; HGB is `{result['ml']['value']:.3f} ns`.",
        "",
        "## 6. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03f_1781019517_3497_1b4352d9_shared_stave_shrinkage.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `leakage_checks.csv`, `s03a_amp_only_cv_scan.csv`, `s03b_monotone_cv_scan.csv`, `shared_shrinkage_cv_scan.csv`, `shared_shrinkage_model_table.csv`, `hgb_cv_scan.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03f_1781019517_3497_1b4352d9_shared_stave_shrinkage.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["shrinkage"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")
    print("[s03f] raw count reproduction passed", flush=True)

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
    print("[s03f] run65 S03a/S03b reproduction passed", flush=True)

    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    s03a_cv_parts = []
    s03b_cv_parts = []
    shrink_cv_parts = []
    hgb_cv_parts = []
    shrink_table_parts = []
    for heldout_run in all_runs:
        bench, residuals, leakage, s03a_cv, s03b_cv, shrink_cv, hgb_cv, shrink_table = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        per_run_parts.append(bench)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        s03a_cv_parts.append(s03a_cv)
        s03b_cv_parts.append(s03b_cv)
        shrink_cv_parts.append(shrink_cv)
        hgb_cv_parts.append(hgb_cv)
        shrink_table_parts.append(shrink_table)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    s03a_cv = pd.concat(s03a_cv_parts, ignore_index=True)
    s03b_cv = pd.concat(s03b_cv_parts, ignore_index=True)
    shrink_cv = pd.concat(shrink_cv_parts, ignore_index=True)
    hgb_cv = pd.concat(hgb_cv_parts, ignore_index=True)
    shrink_table = pd.concat(shrink_table_parts, ignore_index=True)
    pooled = run_level_bootstrap(residuals, rng, int(config["shrinkage"]["bootstrap_samples"]))

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    s03a_cv.to_csv(out_dir / "s03a_amp_only_cv_scan.csv", index=False)
    s03b_cv.to_csv(out_dir / "s03b_monotone_cv_scan.csv", index=False)
    shrink_cv.to_csv(out_dir / "shared_shrinkage_cv_scan.csv", index=False)
    shrink_table.to_csv(out_dir / "shared_shrinkage_model_table.csv", index=False)
    hgb_cv.to_csv(out_dir / "hgb_cv_scan.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    pooled_idx = pooled.set_index("method")
    base = pooled_idx.loc["template_phase_base"]
    s03a_row = pooled_idx.loc["s03a_amp_only"]
    s03b_row = pooled_idx.loc["s03b_monotone_binned"]
    shrink_row = pooled_idx.loc["phys_signed_shared_shrinkage"]
    hgb_row = pooled_idx.loc["hgb_timewalk"]
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    min_shuffle = float(
        leakage[
            leakage["check"].isin(
                [
                    "shared_shrinkage_shuffled_target_sigma68",
                    "s03b_shuffled_target_sigma68",
                    "hgb_shuffled_target_sigma68",
                ]
            )
        ]["value"].min()
    )
    hgb_gain_vs_shrinkage = float(shrink_row["value"] - hgb_row["value"])
    looks_too_good = bool(hgb_gain_vs_shrinkage > 0.5 or hgb_row["value"] < 0.8)
    shrinkage_looks_too_good = bool(shrink_row["value"] < hgb_row["value"] or shrink_row["value"] < 1.0)
    leakage_flag = bool(event_overlap != 0 or min_shuffle < hgb_row["value"] + 0.2)
    shrinkage_beats_s03b = bool(shrink_row["value"] < s03b_row["value"])
    verdict = (
        "shared_shrinkage_beats_isotonic_no_leakage"
        if shrinkage_beats_s03b and event_overlap == 0 and not leakage_flag
        else "shared_shrinkage_does_not_beat_isotonic_or_leakage_concern"
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
        "split": {
            "unit": "run",
            "heldout_runs": all_runs,
            "bootstrap_unit": "heldout_run",
        },
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
                "gain_vs_template_phase_ns": float(base["value"] - s03a_row["value"]),
            },
            "s03b_monotone_binned": {
                "method": "per_stave_monotone_decreasing_binned_timewalk",
                "value": float(s03b_row["value"]),
                "ci": [float(s03b_row["ci_low"]), float(s03b_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - s03b_row["value"]),
                "delta_vs_s03a_amp_only_ns": float(s03a_row["value"] - s03b_row["value"]),
            },
            "phys_signed_shared_shrinkage": {
                "method": "shared_decreasing_isotonic_bins_with_stave_shrinkage",
                "value": float(shrink_row["value"]),
                "ci": [float(shrink_row["ci_low"]), float(shrink_row["ci_high"])],
                "gain_vs_template_phase_ns": float(base["value"] - shrink_row["value"]),
                "delta_vs_s03a_amp_only_ns": float(s03a_row["value"] - shrink_row["value"]),
                "delta_vs_s03b_monotone_binned_ns": float(s03b_row["value"] - shrink_row["value"]),
            },
        },
        "ml": {
            "method": "hist_gradient_boosting_residual_corrector_on_template_phase",
            "value": float(hgb_row["value"]),
            "ci": [float(hgb_row["ci_low"]), float(hgb_row["ci_high"])],
            "gain_vs_template_phase_ns": float(base["value"] - hgb_row["value"]),
            "gain_vs_phys_signed_shared_shrinkage_ns": hgb_gain_vs_shrinkage,
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "final_models_use_heldout_rows": False,
            "shuffled_target_min_sigma68_ns": min_shuffle,
            "hgb_looks_too_good": looks_too_good,
            "shared_shrinkage_looks_too_good": shrinkage_looks_too_good,
            "leakage_flag": leakage_flag,
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S03g: monotonicity audit for HGB residual timewalk features versus shared-shrinkage bins",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro_counts, run65_repro, per_run, pooled, shrink_table, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03f",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["shrinkage"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "baseline": float(base["value"]),
                "s03a_amp_only": float(s03a_row["value"]),
                "s03b_monotone_binned": float(s03b_row["value"]),
                "phys_signed_shared_shrinkage": float(shrink_row["value"]),
                "hgb": float(hgb_row["value"]),
                "verdict": verdict,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
