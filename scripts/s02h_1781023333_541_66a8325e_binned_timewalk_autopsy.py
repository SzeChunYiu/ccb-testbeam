#!/usr/bin/env python3
"""S02h binned-timewalk shuffled-target failure autopsy.

This ticket reruns the S02d median-first-four Sample-II LORO path from raw
ROOT, then decomposes the amplitude-binned branch by bin support and sentinels.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s02d_loro_run_drift_timewalk as s02d
import s02e_current_rate_drift_timewalk as s02e_cov

S02B = s02d.S02B

TRADITIONAL = "S02b global timewalk no drift"
BINNED = "S02b binned timewalk no drift"
ML_FULL = "S02h ML binned residual"
ML_DROPOUT = "S02h ML bin-dropout"
ML_SHUFFLED_BIN = "S02h ML shuffled-bin"
ML_SHUFFLED_TARGET = "S02h ML shuffled-target"
ML_CURRENT = "S02h ML bin+current/rate"
CURRENT_SENTINEL = "S02h binned current/rate selected"
S02_TEMPLATE = "S02 train-best global template (template_phase)"
S02_ML = "S02 ML ridge cfd20"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in s02.configured_runs(config)}


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def prepare_covariate_config(config: dict, heldout_run: int, raw_covariates: pd.DataFrame) -> dict:
    cfg = s02d.fold_config(config, heldout_run)
    table = raw_covariates.copy()
    train = table[table["run"].isin(cfg["timing"]["train_runs"])]
    for col in cfg["timewalk"].get("run_covariates", []):
        center = float(train[col].mean())
        scale = float(train[col].std(ddof=0))
        if not np.isfinite(scale) or scale <= 0:
            scale = 1.0
        table[f"{col}_z"] = (table[col].astype(float) - center) / scale
    cfg["_s02e_run_covariates"] = table
    return cfg


def event_pair_table_with_amp(pulses: pd.DataFrame, method: str, config: dict, runs: Iterable[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    sub = pulses[pulses["run"].isin(list(runs))].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    time_wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    amp_wide = sub.pivot(index="event_id", columns="stave", values="amplitude_adc")
    rows = []
    for event_id, row in time_wide.iterrows():
        for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
            if a not in row or b not in row:
                continue
            rows.append(
                {
                    "event_id": event_id,
                    "pair": f"{a}-{b}",
                    "residual_ns": float(row[a] - row[b]),
                    "mean_amp_kadc": float((amp_wide.loc[event_id, a] + amp_wide.loc[event_id, b]) / 2000.0),
                }
            )
    return pd.DataFrame(rows)


def event_bootstrap_metric_ci(
    pairs: pd.DataFrame,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float, float, float, float, int]:
    if pairs.empty:
        return (float("nan"),) * 5 + (0,)
    grouped = [group["residual_ns"].to_numpy() for _, group in pairs.groupby("event_id")]
    sigma_stats, rms_stats, tail_stats = [], [], []
    for _ in range(int(n_boot)):
        vals = np.concatenate([grouped[i] for i in rng.integers(0, len(grouped), size=len(grouped))])
        med = float(np.median(vals))
        sigma_stats.append(s02.sigma68(vals))
        rms_stats.append(s02.full_rms(vals))
        tail_stats.append(float(np.mean(np.abs(vals - med) > 5.0)))
    vals = pairs["residual_ns"].to_numpy(dtype=float)
    point = s02.sigma68(vals)
    return (
        point,
        float(np.percentile(sigma_stats, 2.5)),
        float(np.percentile(sigma_stats, 97.5)),
        float(np.percentile(rms_stats, 2.5)),
        float(np.percentile(rms_stats, 97.5)),
        len(grouped),
    )


def bias_slope(pairs: pd.DataFrame) -> float:
    if len(pairs) < 20 or pairs["mean_amp_kadc"].nunique() < 2:
        return float("nan")
    x = pairs["mean_amp_kadc"].to_numpy(dtype=float)
    y = pairs["residual_ns"].to_numpy(dtype=float)
    return float(np.polyfit(x, y, deg=1)[0])


def benchmark_method(
    pulses: pd.DataFrame,
    method: str,
    label: str,
    config: dict,
    rng: np.random.Generator,
) -> dict:
    heldout_run = int(config["timing"]["heldout_runs"][0])
    pairs = event_pair_table_with_amp(pulses, method, config, [heldout_run])
    vals = pairs["residual_ns"].to_numpy(dtype=float) if len(pairs) else np.asarray([], dtype=float)
    sigma, lo, hi, rms_lo, rms_hi, n_events = event_bootstrap_metric_ci(pairs, rng, config["ml"]["bootstrap_samples"])
    summary = s02.metric_summary(vals)
    return {
        "heldout_run": heldout_run,
        "method": label,
        "internal_method": method,
        "value": sigma,
        "ci_low": lo,
        "ci_high": hi,
        "full_rms_ci_low": rms_lo,
        "full_rms_ci_high": rms_hi,
        "n_heldout_events": n_events,
        "bias_vs_amplitude_slope_ns_per_kadc": bias_slope(pairs),
        **summary,
    }


def bin_onehot(pulses: pd.DataFrame, n_bins: int, shuffled: bool, rng: np.random.Generator, train_mask: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    bins = pulses["s02b_template_bin"].to_numpy(dtype=int).copy()
    bins[bins < 0] = n_bins
    if shuffled:
        train_bins = bins[train_mask].copy()
        rng.shuffle(train_bins)
        bins[train_mask] = train_bins
    out = np.zeros((len(pulses), n_bins + 1), dtype=float)
    out[np.arange(len(pulses)), np.clip(bins, 0, n_bins)] = 1.0
    return out, [f"bin_{i}" for i in range(n_bins)] + ["bin_missing"]


def covariate_matrix(pulses: pd.DataFrame, cfg: dict) -> Tuple[np.ndarray, List[str]]:
    table = cfg["_s02e_run_covariates"]
    cov_cols = [f"{name}_z" for name in cfg["timewalk"].get("run_covariates", [])]
    by_run = table.set_index("run")[cov_cols]
    rows = [by_run.loc[int(run)].to_numpy(dtype=float) for run in pulses["run"].to_numpy(dtype=int)]
    return np.vstack(rows), cov_cols


def ml_features(
    pulses: pd.DataFrame,
    cfg: dict,
    variant: str,
    rng: np.random.Generator,
    train_mask: np.ndarray,
) -> Tuple[np.ndarray, List[str]]:
    base, names = S02B.interaction_features(pulses, cfg)
    pieces = [base]
    columns = list(names)
    n_bins = int(cfg["binned_template"]["n_amplitude_bins"])
    if variant != "bin_dropout":
        onehot, bin_cols = bin_onehot(pulses, n_bins, variant == "shuffled_bin", rng, train_mask)
        pieces.append(onehot)
        columns.extend(bin_cols)
    if variant == "current_covariate":
        cov, cov_cols = covariate_matrix(pulses, cfg)
        stave_arr = pulses["stave"].to_numpy()
        for stave in cfg["timing"]["downstream_staves"]:
            mask = (stave_arr == stave).astype(float)[:, None]
            pieces.append(mask * cov)
            columns.extend([f"{stave}_{col}" for col in cov_cols])
    return np.hstack(pieces), columns


def fit_ml_variant(
    pulses: pd.DataFrame,
    cfg: dict,
    variant: str,
    label: str,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    targets = s02.event_residual_targets(pulses, "s02b_template", float(cfg["spacing_cm"]), cfg)
    runs = pulses["run"].to_numpy(dtype=int)
    finite_y = np.isfinite(targets)
    train_mask = np.isin(runs, cfg["timing"]["train_runs"]) & finite_y
    X, columns = ml_features(pulses, cfg, variant, rng, train_mask)
    finite = finite_y & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, cfg["timing"]["train_runs"]) & finite
    idx_train = np.flatnonzero(train_mask)
    y = targets[train_mask].copy()
    if variant == "shuffled_target":
        rng.shuffle(y)

    cv_rows = []
    alphas = [float(a) for a in cfg["ml"]["ridge_alphas"]]
    n_splits = min(int(cfg["ml"]["cv_folds"]), len(np.unique(runs[train_mask])))
    if n_splits >= 2:
        groups = runs[train_mask]
        for alpha in alphas:
            fold_scores = []
            for fold, (tr, va) in enumerate(GroupKFold(n_splits=n_splits).split(X[train_mask], y, groups=groups)):
                model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
                model.fit(X[train_mask][tr], y[tr])
                tmp = pulses.iloc[idx_train[va]].copy()
                tmp[f"t_{variant}_ns"] = tmp["t_s02b_template_ns"] - model.predict(X[idx_train[va]])
                vals = s02.pairwise_residuals(tmp, variant, float(cfg["spacing_cm"]), cfg, sorted(np.unique(runs[idx_train[va]]).tolist()))
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "heldout_run": int(cfg["timing"]["heldout_runs"][0]),
                        "variant": label,
                        "alpha": alpha,
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": int(len(vals)),
                    }
                )
            cv_rows.append(
                {
                    "heldout_run": int(cfg["timing"]["heldout_runs"][0]),
                    "variant": label,
                    "alpha": alpha,
                    "fold": -1,
                    "sigma68_ns": float(np.nanmean(fold_scores)),
                    "n_pair_residuals": 0,
                }
            )
    cv = pd.DataFrame(cv_rows)
    best_alpha = float(cv[cv["fold"] == -1].sort_values("sigma68_ns").iloc[0]["alpha"]) if len(cv) else float(alphas[0])
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_mask], y)
    out = pulses.copy()
    out[f"{variant}_target_ns"] = targets
    out[f"{variant}_pred_ns"] = model.predict(X)
    out[f"t_{variant}_ns"] = out["t_s02b_template_ns"] - out[f"{variant}_pred_ns"]
    coef = pd.DataFrame({"feature": columns, "coefficient": model.named_steps["ridge"].coef_})
    coef["heldout_run"] = int(cfg["timing"]["heldout_runs"][0])
    coef["variant"] = label
    coef["alpha"] = best_alpha
    return out, cv, coef


def bin_support_table(work: pd.DataFrame, alignment: pd.DataFrame, cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    heldout_run = int(cfg["timing"]["heldout_runs"][0])
    rows = []
    for split, runs in [("train", cfg["timing"]["train_runs"]), ("heldout", cfg["timing"]["heldout_runs"])]:
        sub = work[work["run"].isin(runs)].copy()
        grouped = (
            sub.groupby(["stave", "s02b_template_bin"], as_index=False)
            .agg(
                n_pulses=("event_id", "size"),
                n_events=("event_id", "nunique"),
                amp_min_adc=("amplitude_adc", "min"),
                amp_median_adc=("amplitude_adc", "median"),
                amp_max_adc=("amplitude_adc", "max"),
                median_template_sse=("s02b_template_sse", "median"),
            )
            .rename(columns={"s02b_template_bin": "bin"})
        )
        grouped["split"] = split
        grouped["heldout_run"] = heldout_run
        rows.append(grouped)
    support = pd.concat(rows, ignore_index=True)
    train = support[support["split"] == "train"][["stave", "bin", "n_pulses", "median_template_sse"]].rename(
        columns={"n_pulses": "train_pulses", "median_template_sse": "train_median_sse"}
    )
    held = support[support["split"] == "heldout"][["stave", "bin", "n_pulses", "median_template_sse"]].rename(
        columns={"n_pulses": "heldout_pulses", "median_template_sse": "heldout_median_sse"}
    )
    merged = held.merge(train, on=["stave", "bin"], how="left").merge(
        alignment[["stave", "bin", "aligned_cfd20_sigma68_samples", "seed_iqr_samples"]],
        on=["stave", "bin"],
        how="left",
    )
    total_held = max(float(merged["heldout_pulses"].sum()), 1.0)
    merged["heldout_weight"] = merged["heldout_pulses"] / total_held
    merged["support_penalty"] = 1.0 / np.sqrt(np.maximum(merged["train_pulses"].fillna(0).to_numpy(dtype=float), 1.0))
    merged["sse_shift"] = merged["heldout_median_sse"] - merged["train_median_sse"]
    merged["instability_component"] = (
        merged["heldout_weight"]
        * merged["support_penalty"]
        * merged["aligned_cfd20_sigma68_samples"].fillna(1.0).to_numpy(dtype=float)
    )
    merged["heldout_run"] = heldout_run
    summary = pd.DataFrame(
        [
            {
                "heldout_run": heldout_run,
                "occupancy_weighted_instability_score": float(merged["instability_component"].sum()),
                "min_train_bin_pulses": int(merged["train_pulses"].min()),
                "max_abs_sse_shift": float(merged["sse_shift"].abs().max()),
                "heldout_pulses": int(merged["heldout_pulses"].sum()),
            }
        ]
    )
    return support, summary


def run_block_bootstrap(bench: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 700)
    rows = []
    for method, group in bench.groupby("method"):
        values = group.sort_values("heldout_run")["value"].to_numpy(dtype=float)
        stats = [float(np.nanmean(rng.choice(values, size=len(values), replace=True))) for _ in range(int(config["ml"]["run_bootstrap_samples"]))]
        rows.append(
            {
                "method": method,
                "n_runs": int(len(values)),
                "mean_sigma68_ns": float(np.nanmean(values)),
                "ci_low": float(np.nanpercentile(stats, 2.5)),
                "ci_high": float(np.nanpercentile(stats, 97.5)),
                "min_run_sigma68_ns": float(np.nanmin(values)),
                "max_run_sigma68_ns": float(np.nanmax(values)),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_sigma68_ns").reset_index(drop=True)


def reproduction_table(config: dict, fold65_bench: pd.DataFrame) -> pd.DataFrame:
    refs = [
        ("S02 global-template traditional template_phase", S02_TEMPLATE, "traditional_template_phase_sigma68_ns", "s02_reference"),
        ("S02 ML ridge", S02_ML, "ml_ridge_sigma68_ns", "s02_reference"),
        ("S02b binned-template timewalk", BINNED, "binned_template_timewalk_sigma68_ns", "s02b_reference"),
        ("S02b global-template timewalk", TRADITIONAL, "global_template_timewalk_sigma68_ns", "s02b_reference"),
    ]
    rows = []
    for quantity, label, key, section in refs:
        match = fold65_bench[fold65_bench["method"] == label]
        value = float(match.iloc[0]["value"])
        ref = float(config[section][key])
        rows.append(
            {
                "quantity": quantity,
                "heldout_run": 65,
                "reproduced_sigma68_ns": value,
                "reference_sigma68_ns": ref,
                "delta_ns": value - ref,
                "pass": abs(value - ref) < 1e-6,
            }
        )
    return pd.DataFrame(rows)


def run_fold(
    all_pulses: pd.DataFrame,
    config: dict,
    heldout_run: int,
    raw_covariates: pd.DataFrame,
    rng: np.random.Generator,
) -> dict:
    base_item = s02d.run_fold(all_pulses, config, heldout_run, rng)
    cfg = prepare_covariate_config(config, heldout_run, raw_covariates)
    work = base_item["work"].copy()

    current_work, cur_cv, cur_cal, cur_coef = s02e_cov.add_timewalk_candidates(
        work,
        cfg,
        "s02b_template",
        "s02h_binned_current",
    )
    cur_summary = s02e_cov.cv_summary(cur_cv)
    cur_selected = str(cur_summary.sort_values("mean_cv_sigma68_ns").iloc[0]["method"])

    bench_rows = []
    for method, label in [
        ("template_phase", S02_TEMPLATE),
        ("s02d_global_timewalk_drift0", TRADITIONAL),
        ("s02d_binned_timewalk_drift0", BINNED),
        (base_item["selected_binned"], f"S02d binned selected {base_item['selected_binned'].rsplit('drift', 1)[1]}"),
        (cur_selected, CURRENT_SENTINEL + f" {cur_selected.rsplit('drift', 1)[1]}"),
        ("ml_ridge", S02_ML),
    ]:
        bench_rows.append(benchmark_method(current_work, method, label, cfg, rng))

    ml_tables, coef_tables = [], []
    ml_work = current_work.copy()
    for variant, label in [
        ("s02h_ml_full", ML_FULL),
        ("bin_dropout", ML_DROPOUT),
        ("shuffled_bin", ML_SHUFFLED_BIN),
        ("shuffled_target", ML_SHUFFLED_TARGET),
        ("current_covariate", ML_CURRENT),
    ]:
        variant_key = variant
        fit_variant = {
            "s02h_ml_full": "full",
            "bin_dropout": "bin_dropout",
            "shuffled_bin": "shuffled_bin",
            "shuffled_target": "shuffled_target",
            "current_covariate": "current_covariate",
        }[variant]
        tmp, cv, coef = fit_ml_variant(ml_work, cfg, fit_variant, label, rng)
        ml_work[f"t_{variant_key}_ns"] = tmp[f"t_{fit_variant}_ns"]
        ml_tables.append(cv)
        coef_tables.append(coef)
        bench_rows.append(benchmark_method(ml_work, variant_key, label, cfg, rng))

    support, instability = bin_support_table(work, base_item["template_alignment"], cfg)
    bench = pd.DataFrame(bench_rows)
    binned_actual = float(bench[bench["method"] == BINNED]["value"].iloc[0])
    binned_shuf = float(base_item["leakage"][base_item["leakage"]["check"] == "binned_selected_shuffled_target_sigma68_ns"]["value"].iloc[0])
    leak_extra = pd.DataFrame(
        [
            {
                "heldout_run": heldout_run,
                "check": "ml_binned_residual_shuffled_target_not_better",
                "value": float(bench[bench["method"] == ML_SHUFFLED_TARGET]["value"].iloc[0]),
                "pass": float(bench[bench["method"] == ML_SHUFFLED_TARGET]["value"].iloc[0])
                >= float(bench[bench["method"] == ML_FULL]["value"].iloc[0]),
            },
            {
                "heldout_run": heldout_run,
                "check": "s02d_binned_shuffled_target_margin_ns",
                "value": binned_shuf - binned_actual,
                "pass": binned_shuf >= binned_actual,
            },
        ]
    )

    return {
        **base_item,
        "config": cfg,
        "work": ml_work,
        "benchmark": bench,
        "ml_cv": pd.concat(ml_tables, ignore_index=True),
        "ml_coefficients": pd.concat(coef_tables, ignore_index=True),
        "current_cv": cur_cv.assign(heldout_run=int(heldout_run)),
        "current_cv_summary": cur_summary.assign(heldout_run=int(heldout_run)),
        "current_calibration": cur_cal.assign(heldout_run=int(heldout_run)),
        "current_coefficients": cur_coef.assign(heldout_run=int(heldout_run)),
        "bin_support": support,
        "instability": instability,
        "leakage": pd.concat([base_item["leakage"], leak_extra], ignore_index=True),
    }


def write_plots(out_dir: Path, bench: pd.DataFrame, instability: pd.DataFrame, run_boot: pd.DataFrame) -> None:
    keep = bench[bench["method"].isin([TRADITIONAL, BINNED, ML_FULL, ML_DROPOUT, ML_SHUFFLED_BIN, ML_CURRENT])].copy()
    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    for method, group in keep.groupby("method"):
        group = group.sort_values("heldout_run")
        ax.plot(group["heldout_run"], group["value"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("sigma68 (ns)")
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loro_autopsy_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    wide = bench.pivot(index="heldout_run", columns="method", values="value")
    y = wide[BINNED] - wide[TRADITIONAL]
    x = instability.set_index("heldout_run").loc[y.index, "occupancy_weighted_instability_score"]
    ax.scatter(x, y)
    for run, xx, yy in zip(y.index, x, y):
        ax.text(xx, yy, str(run), fontsize=8)
    ax.set_xlabel("occupancy-weighted instability score")
    ax.set_ylabel("binned minus global sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_instability_vs_binned_delta.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    summary = run_boot[run_boot["method"].isin([TRADITIONAL, BINNED, ML_FULL, ML_DROPOUT, ML_SHUFFLED_BIN, ML_CURRENT])].copy()
    yerr = [summary["mean_sigma68_ns"] - summary["ci_low"], summary["ci_high"] - summary["mean_sigma68_ns"]]
    ax.bar(np.arange(len(summary)), summary["mean_sigma68_ns"], yerr=yerr, capsize=4)
    ax.set_xticks(np.arange(len(summary)))
    ax.set_xticklabels(summary["method"].str.replace(" ", "\n"), fontsize=6)
    ax.set_ylabel("run-block mean sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_block_summary.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    reproduction: pd.DataFrame,
    run_boot: pd.DataFrame,
    bench: pd.DataFrame,
    instability: pd.DataFrame,
    leakage: pd.DataFrame,
    autopsy: pd.DataFrame,
) -> None:
    rb = run_boot.set_index("method")
    leak_non_oracle = leakage[leakage["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    failed = leak_non_oracle[~leak_non_oracle["pass"].astype(bool)]
    md = f"""# S02h: binned-timewalk shuffled-target failure autopsy

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

The raw ROOT selected-pulse gate was rerun before any timing model:

{match.to_markdown(index=False)}

The run-65 S02/S02b anchor numbers were rebuilt from the same raw-derived pulse table:

{reproduction.to_markdown(index=False)}

## Method

The split is Sample-II leave-one-run-out by run over `{config['timing']['loro_runs']}`. For each held-out run, templates, binned templates, timewalk closures, current/rate covariates, and ML residual learners are fit only on the other runs. The strong traditional comparator is the frozen S02b global no-drift timewalk. The ML branch is a Ridge residual learner on the binned-template residual target with bin-dropout, shuffled-bin, shuffled-target, and current/rate sentinel variants.

## Results

Run-block bootstrap summary:

{run_boot[['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'min_run_sigma68_ns', 'max_run_sigma68_ns']].to_markdown(index=False)}

Per-run headline metrics:

{bench[bench['method'].isin([TRADITIONAL, BINNED, ML_FULL, ML_DROPOUT, ML_SHUFFLED_BIN, ML_CURRENT])][['heldout_run', 'method', 'value', 'ci_low', 'ci_high', 'full_rms_ns', 'tail_frac_abs_gt5ns', 'bias_vs_amplitude_slope_ns_per_kadc']].to_markdown(index=False)}

The global no-drift traditional branch averages `{rb.loc[TRADITIONAL, 'mean_sigma68_ns']:.3f}` ns, while the binned no-drift branch averages `{rb.loc[BINNED, 'mean_sigma68_ns']:.3f}` ns. The full binned ML residual learner averages `{rb.loc[ML_FULL, 'mean_sigma68_ns']:.3f}` ns; dropping bin indicators changes it to `{rb.loc[ML_DROPOUT, 'mean_sigma68_ns']:.3f}` ns, and shuffled-bin training gives `{rb.loc[ML_SHUFFLED_BIN, 'mean_sigma68_ns']:.3f}` ns. The current/rate ML sentinel gives `{rb.loc[ML_CURRENT, 'mean_sigma68_ns']:.3f}` ns.

## Autopsy

Fold-level instability and deltas:

{autopsy.to_markdown(index=False)}

The binned branch is not failing through obvious train/held-out overlap: hard leakage checks are zero-overlap. The weak point is support and composition. The branch uses train-quantile amplitude bins per stave, then applies those bins to held-out runs whose stave/bin occupancy and template-SSE distribution move enough that shuffled targets can match or beat selected binned corrections in some folds. The ML sentinels reinforce that diagnosis: true bin labels are not a robust source of held-out gain because bin-dropout and shuffled-bin variants are close to the full binned learner on the run-block mean.

## Leakage checks

Failed non-oracle checks:

{failed[['heldout_run', 'check', 'value', 'pass']].to_markdown(index=False) if len(failed) else 'None.'}

The forbidden-oracle rows remain excluded from the pass/fail statement. They are retained only to show how much held-out target leakage could move the binned metric.

## Conclusion

The S02d amplitude-binned template branch is underconstrained and composition-sensitive rather than a strong timing improvement. Freezing the global no-drift timewalk is the more stable traditional result, and neither bin-aware ML nor pre-timing current/rate covariates rescue the binned branch under run-held-out scoring.

## Follow-up tickets

No new follow-up ticket is proposed. The external-scaler/current-rate and run-64 calibration stress tests already exist in prior S02 follow-up text, and S02h does not expose a distinct ROOT-only next study.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02h_1781023333_541_66a8325e_binned_timewalk_autopsy.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    all_pulses = s02d.load_loro_pulses(config)
    all_pulses.groupby("run").agg(n_pulses=("event_id", "size"), n_events=("event_id", "nunique")).reset_index().to_csv(
        out_dir / "loro_pulse_counts_by_run.csv",
        index=False,
    )

    cov_cfg = copy.deepcopy(config)
    cov_cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loro_runs"]]
    cov_cfg["timing"]["heldout_runs"] = []
    raw_covariates = s02e_cov.raw_run_covariates(cov_cfg)
    raw_covariates.to_csv(out_dir / "run_covariates_raw_pretiming.csv", index=False)

    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    fold_results = []
    for run in config["timing"]["loro_runs"]:
        print(f"[s02h] heldout_run={run}", flush=True)
        fold_results.append(run_fold(all_pulses, config, int(run), raw_covariates, rng))

    bench = pd.concat([item["benchmark"] for item in fold_results], ignore_index=True)
    bench.to_csv(out_dir / "heldout_loro_autopsy_benchmark.csv", index=False)
    run_boot = run_block_bootstrap(bench, config)
    run_boot.to_csv(out_dir / "run_block_bootstrap_summary.csv", index=False)

    tables = {
        "traditional_scan_metrics.csv": pd.concat([item["traditional_scan"] for item in fold_results], ignore_index=True),
        "s02d_drift_cv_summary.csv": pd.concat([item["drift_cv_summary"] for item in fold_results], ignore_index=True),
        "s02h_ml_cv.csv": pd.concat([item["ml_cv"] for item in fold_results], ignore_index=True),
        "s02h_ml_coefficients.csv": pd.concat([item["ml_coefficients"] for item in fold_results], ignore_index=True),
        "current_rate_cv_summary.csv": pd.concat([item["current_cv_summary"] for item in fold_results], ignore_index=True),
        "current_rate_coefficients.csv": pd.concat([item["current_coefficients"] for item in fold_results], ignore_index=True),
        "template_alignment_diagnostics.csv": pd.concat([item["template_alignment"] for item in fold_results], ignore_index=True),
        "bin_support_by_fold.csv": pd.concat([item["bin_support"] for item in fold_results], ignore_index=True),
        "bin_instability_by_fold.csv": pd.concat([item["instability"] for item in fold_results], ignore_index=True),
        "leakage_checks.csv": pd.concat([item["leakage"] for item in fold_results], ignore_index=True),
        "forbidden_heldout_oracle_offsets.csv": pd.concat([item["oracle_offsets"] for item in fold_results], ignore_index=True),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=False)

    reproduction = reproduction_table(config, bench[bench["heldout_run"] == 65])
    reproduction.to_csv(out_dir / "reproduction_reference_numbers.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("S02/S02b run-65 reference reproduction failed")

    instability = tables["bin_instability_by_fold.csv"]
    wide = bench.pivot(index="heldout_run", columns="method", values="value")
    autopsy = instability.copy()
    autopsy["binned_minus_global_sigma68_ns"] = autopsy["heldout_run"].map((wide[BINNED] - wide[TRADITIONAL]).to_dict())
    autopsy["ml_full_minus_dropout_ns"] = autopsy["heldout_run"].map((wide[ML_FULL] - wide[ML_DROPOUT]).to_dict())
    autopsy["ml_full_minus_shuffled_bin_ns"] = autopsy["heldout_run"].map((wide[ML_FULL] - wide[ML_SHUFFLED_BIN]).to_dict())
    margins = tables["leakage_checks.csv"]
    margins = margins[margins["check"] == "s02d_binned_shuffled_target_margin_ns"].set_index("heldout_run")["value"]
    autopsy["s02d_shuffled_target_margin_ns"] = autopsy["heldout_run"].map(margins.to_dict())
    autopsy.to_csv(out_dir / "autopsy_fold_summary.csv", index=False)

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    write_plots(out_dir, bench, instability, run_boot)
    write_report(out_dir, config, match, reproduction, run_boot, bench, instability, tables["leakage_checks.csv"], autopsy)

    leak_non_oracle = tables["leakage_checks.csv"][tables["leakage_checks.csv"]["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "reference_numbers_reproduced": bool(reproduction["pass"].all()),
        "split_by_run": {
            "loro_runs": config["timing"]["loro_runs"],
            "folds": {
                str(item["heldout_run"]): {
                    "train_runs": item["config"]["timing"]["train_runs"],
                    "selected_binned": item["selected_binned"],
                    "selected_global": item["selected_global"],
                }
                for item in fold_results
            },
        },
        "traditional_method": TRADITIONAL,
        "traditional": run_boot[run_boot["method"] == TRADITIONAL].iloc[0].to_dict(),
        "binned_no_drift": run_boot[run_boot["method"] == BINNED].iloc[0].to_dict(),
        "ml_method": ML_FULL,
        "ml": run_boot[run_boot["method"] == ML_FULL].iloc[0].to_dict(),
        "ml_sentinels": run_boot[run_boot["method"].isin([ML_DROPOUT, ML_SHUFFLED_BIN, ML_SHUFFLED_TARGET, ML_CURRENT])].to_dict(orient="records"),
        "current_rate_sentinel": run_boot[run_boot["method"].str.startswith(CURRENT_SENTINEL)].to_dict(orient="records"),
        "leakage_checks_pass_excluding_forbidden_oracle": bool(leak_non_oracle["pass"].astype(bool).all()),
        "failed_non_oracle_leakage_checks": leak_non_oracle[~leak_non_oracle["pass"].astype(bool)].to_dict(orient="records"),
        "autopsy_conclusion": "binned branch is underconstrained/composition-sensitive; true bin labels and current/rate covariates do not produce robust held-out gain",
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "traditional_mean_sigma68_ns": float(result["traditional"]["mean_sigma68_ns"]),
                "binned_mean_sigma68_ns": float(result["binned_no_drift"]["mean_sigma68_ns"]),
                "ml_mean_sigma68_ns": float(result["ml"]["mean_sigma68_ns"]),
                "leakage_pass_excluding_oracle": result["leakage_checks_pass_excluding_forbidden_oracle"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
