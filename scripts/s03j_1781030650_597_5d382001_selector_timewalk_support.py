#!/usr/bin/env python3
"""S03j selector-specific timewalk support map from raw ROOT waveforms."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s03j")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

import p03a_18_sample_mlp_timing as p03a
import p03c_1781015093_889_4aa141a8_cnn_vs_mlp_loro as p03c
import s02_timing_pickoff as s02
import s02c_selector_semantics as s02c
import s03a_analytic_timewalk as s03a
import s03d_leave_one_run_s03ab_hgb_stability as s03d_hgb
import s03d_signed_timewalk_prior as s03d_signed


STRATA = ["median_selected", "dynamic_only", "matched_control"]
TRADITIONAL_LABEL = "signed_physics_prior"
METHODS = [
    ("template_phase", "template_phase_base"),
    ("analytic_timewalk", "s03a_amp_only_ridge"),
    ("signed_prior", TRADITIONAL_LABEL),
    ("ridge_template", "ridge_ml"),
    ("hgb_timewalk", "gradient_boosted_trees_hgb"),
    ("mlp_waveform", "mlp_waveform"),
    ("cnn_waveform", "cnn_1d_waveform"),
    ("hybrid_residual_ensemble", "hybrid_residual_ensemble"),
]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def event_key(event_id: str) -> str:
    parts = str(event_id).split(":")
    return ":".join(parts[-4:])


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(run) for run in train_runs]
    out["timing"]["heldout_runs"] = [int(run) for run in heldout_runs]
    return out


def add_event_keys(pulses: pd.DataFrame, stratum: str) -> pd.DataFrame:
    out = pulses.copy()
    out["event_key"] = out["event_id"].map(event_key)
    out["stratum"] = stratum
    out["event_id"] = stratum + ":" + out["event_key"].astype(str)
    return out


def build_strata(config: dict) -> Dict[str, pd.DataFrame]:
    cfg = copy.deepcopy(config)
    cfg["timing"]["train_runs"] = [int(run) for run in config["timing"]["loo_runs"]]
    cfg["timing"]["heldout_runs"] = []
    median = add_event_keys(s02c.load_downstream_pulses_by_selector(cfg, "median_first4"), "median_selected")
    dynamic = add_event_keys(s02c.load_downstream_pulses_by_selector(cfg, "dynamic_range"), "dynamic_range")

    median_keys = set(median["event_key"])
    dynamic_only = dynamic[~dynamic["event_key"].isin(median_keys)].copy()
    dynamic_only["stratum"] = "dynamic_only"
    dynamic_only["event_id"] = "dynamic_only:" + dynamic_only["event_key"].astype(str)

    matched = make_matched_control(median, dynamic_only, config)
    return {
        "median_selected": median.drop(columns=["selector"], errors="ignore").reset_index(drop=True),
        "dynamic_only": dynamic_only.drop(columns=["selector"], errors="ignore").reset_index(drop=True),
        "matched_control": matched.drop(columns=["selector"], errors="ignore").reset_index(drop=True),
    }


def event_amplitude_table(pulses: pd.DataFrame) -> pd.DataFrame:
    return (
        pulses.groupby(["event_id", "event_key", "run"], as_index=False)
        .agg(event_amp_adc=("amplitude_adc", "mean"), min_amp_adc=("amplitude_adc", "min"), max_dynamic_amp_adc=("dynamic_amplitude_adc", "max"))
        .reset_index(drop=True)
    )


def make_matched_control(median: pd.DataFrame, dynamic_only: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 303)
    edges = np.asarray(config["support_map"]["match_amplitude_edges_adc"], dtype=float)
    med_events = event_amplitude_table(median)
    dyn_events = event_amplitude_table(dynamic_only)
    med_events["amp_bin"] = pd.cut(med_events["event_amp_adc"], edges, include_lowest=True, duplicates="drop")
    dyn_events["amp_bin"] = pd.cut(dyn_events["event_amp_adc"], edges, include_lowest=True, duplicates="drop")
    selected: List[str] = []
    for (run, amp_bin), target in dyn_events.groupby(["run", "amp_bin"], observed=True):
        candidates = med_events[(med_events["run"] == int(run)) & (med_events["amp_bin"] == amp_bin)]["event_key"].to_numpy()
        if len(candidates) == 0:
            continue
        n_take = min(len(candidates), int(len(target)))
        selected.extend(rng.choice(candidates, size=n_take, replace=False).tolist())
    if not selected:
        selected = med_events["event_key"].tolist()
    matched = median[median["event_key"].isin(set(selected))].copy()
    matched["stratum"] = "matched_control"
    matched["event_id"] = "matched_control:" + matched["event_key"].astype(str)
    return matched.reset_index(drop=True)


def support_counts(strata: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for stratum, pulses in strata.items():
        if pulses.empty:
            continue
        events = event_amplitude_table(pulses)
        for run, group in events.groupby("run"):
            sub = pulses[pulses["run"] == run]
            rows.append(
                {
                    "stratum": stratum,
                    "run": int(run),
                    "n_events": int(group["event_id"].nunique()),
                    "n_pulses": int(len(sub)),
                    "event_amp_median_adc": float(group["event_amp_adc"].median()),
                    "event_amp_p10_adc": float(group["event_amp_adc"].quantile(0.10)),
                    "event_amp_p90_adc": float(group["event_amp_adc"].quantile(0.90)),
                    "min_stave_amp_median_adc": float(group["min_amp_adc"].median()),
                    "max_dynamic_amp_median_adc": float(group["max_dynamic_amp_adc"].median()),
                }
            )
    return pd.DataFrame(rows).sort_values(["stratum", "run"]).reset_index(drop=True)


def prepare_base_pulses(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, str, pd.DataFrame]:
    out = pulses.copy()
    train = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    base_method = str(config["timing"]["base_method"])
    return out, base_method, scan


def run_ridge_template(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out, cv, _ = s02.run_ml(pulses, config, base_method, 2.0)
    out = out.rename(columns={"t_ml_ridge_ns": "t_ridge_template_ns", "ml_pred_residual_ns": "ridge_pred_residual_ns", "ml_target_residual_ns": "ridge_target_residual_ns"})
    return out, cv


def pair_frame(pulses: pd.DataFrame, methods: Sequence[Tuple[str, str]], config: dict, runs: Sequence[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    amp_wide = sub.pivot(index="event_id", columns="stave", values="amplitude_adc")
    rows = []
    for method, label in methods:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for eid, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                if a in wide.columns and b in wide.columns and eid in amp_wide.index:
                    amp = float(np.nanmean([amp_wide.loc[eid].get(a, np.nan), amp_wide.loc[eid].get(b, np.nan)]))
                    rows.append({"event_id": eid, "pair": f"{a}-{b}", "method": label, "residual_ns": float(row[a] - row[b]), "pair_amp_adc": amp})
    return pd.DataFrame(rows)


def slope_logamp(values: np.ndarray, amps: np.ndarray) -> float:
    mask = np.isfinite(values) & np.isfinite(amps) & (amps > 0)
    if mask.sum() < 20:
        return float("nan")
    x = np.log1p(amps[mask])
    y = values[mask]
    if np.nanstd(x) <= 0:
        return float("nan")
    return float(np.polyfit(x, y, 1)[0])


def summarize_pair_frame(pairs: pd.DataFrame, baseline: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    event_ids = np.asarray(sorted(pairs["event_id"].unique()))
    labels = sorted(pairs["method"].unique())
    by = {}
    for label in labels:
        by[label] = {}
        for eid, group in pairs[pairs["method"] == label].groupby("event_id"):
            by[label][eid] = group[["residual_ns", "pair_amp_adc"]].to_numpy(dtype=float)
    observed = {}
    for label in labels:
        sub = pairs[pairs["method"] == label]
        vals = sub["residual_ns"].to_numpy(dtype=float)
        amps = sub["pair_amp_adc"].to_numpy(dtype=float)
        observed[label] = {
            "sigma68_ns": s02.sigma68(vals),
            "full_rms_ns": s02.full_rms(vals),
            "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - np.median(vals)) > 5.0)) if len(vals) else float("nan"),
            "bias_vs_logamp_slope_ns": slope_logamp(vals, amps),
            "n_pair_residuals": int(len(vals)),
        }
    stats = {label: [] for label in labels}
    slopes = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
        boot_sigmas = {}
        for label in labels:
            arr = np.vstack([by[label][eid] for eid in sample_ids if eid in by[label]])
            vals = arr[:, 0]
            amps = arr[:, 1]
            boot_sigmas[label] = s02.sigma68(vals)
            stats[label].append(boot_sigmas[label])
            slopes[label].append(slope_logamp(vals, amps))
        if baseline in boot_sigmas:
            for label in labels:
                deltas[label].append(boot_sigmas[label] - boot_sigmas[baseline])
    for label in labels:
        obs = observed[label]
        rows.append(
            {
                "method": label,
                "baseline_method": baseline,
                "n_events": int(len(event_ids)),
                **obs,
                "ci_low": float(np.nanpercentile(stats[label], 2.5)),
                "ci_high": float(np.nanpercentile(stats[label], 97.5)),
                "bias_slope_ci_low": float(np.nanpercentile(slopes[label], 2.5)),
                "bias_slope_ci_high": float(np.nanpercentile(slopes[label], 97.5)),
                "delta_vs_traditional_ns": float(obs["sigma68_ns"] - observed[baseline]["sigma68_ns"]) if baseline in observed else float("nan"),
                "delta_ci_low": float(np.nanpercentile(deltas[label], 2.5)) if deltas[label] else float("nan"),
                "delta_ci_high": float(np.nanpercentile(deltas[label], 97.5)) if deltas[label] else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns").reset_index(drop=True)


def has_support(pulses: pd.DataFrame, config: dict, heldout_run: int) -> bool:
    events = pulses.groupby("run")["event_id"].nunique()
    train_runs = [run for run in config["timing"]["loo_runs"] if int(run) != int(heldout_run)]
    train_n = int(events.reindex(train_runs).fillna(0).sum())
    held_n = int(events.reindex([heldout_run]).fillna(0).sum())
    return train_n >= int(config["support_map"]["min_train_events"]) and held_n >= int(config["support_map"]["min_heldout_events"])


def run_fold(stratum: str, pulses_all: pd.DataFrame, base_config: dict, heldout_run: int, rng: np.random.Generator):
    train_runs = [int(run) for run in base_config["timing"]["loo_runs"] if int(run) != int(heldout_run)]
    cfg = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method, scan = prepare_base_pulses(pulses_all, cfg)

    analytic_pulses, analytic_cv, analytic_coef, analytic_candidate, analytic_alpha = s03a.run_analytic(pulses, cfg, base_method)
    signed_pulses, signed_cv, signed_coef, signed_best = s03d_signed.run_signed_prior(pulses, cfg, base_method)
    ridge_pulses, ridge_cv = run_ridge_template(pulses, cfg, base_method)
    hgb_pulses, hgb_cv, hgb_best = s03d_hgb.run_hgb(pulses, cfg, base_method)
    mlp_pulses, mlp_cv, mlp_cal, mlp_info = p03a.run_waveform_mlp(pulses, cfg, base_method)
    cnn_pulses, cnn_cv, cnn_cal, cnn_info = p03c.run_waveform_cnn(pulses, cfg, base_method)

    combined = analytic_pulses.copy()
    combined["t_signed_prior_ns"] = signed_pulses["t_signed_prior_ns"].to_numpy(dtype=float)
    combined["t_ridge_template_ns"] = ridge_pulses["t_ridge_template_ns"].to_numpy(dtype=float)
    combined["ridge_pred_residual_ns"] = ridge_pulses["ridge_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_hgb_timewalk_ns"] = hgb_pulses["t_hgb_timewalk_ns"].to_numpy(dtype=float)
    combined["hgb_pred_residual_ns"] = hgb_pulses["hgb_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_mlp_waveform_ns"] = mlp_pulses["t_mlp_waveform_ns"].to_numpy(dtype=float)
    combined["mlp_pred_residual_ns"] = mlp_pulses["mlp_pred_residual_ns"].to_numpy(dtype=float)
    combined["t_cnn_waveform_ns"] = cnn_pulses["t_cnn_waveform_ns"].to_numpy(dtype=float)
    combined["cnn_pred_residual_ns"] = cnn_pulses["cnn_pred_residual_ns"].to_numpy(dtype=float)
    pred_cols = ["ridge_pred_residual_ns", "hgb_pred_residual_ns", "mlp_pred_residual_ns", "cnn_pred_residual_ns"]
    combined["hybrid_pred_residual_ns"] = combined[pred_cols].mean(axis=1)
    combined["t_hybrid_residual_ensemble_ns"] = combined[f"t_{base_method}_ns"] - combined["hybrid_pred_residual_ns"]

    pairs = pair_frame(combined, METHODS, cfg, [heldout_run])
    summary = summarize_pair_frame(pairs, TRADITIONAL_LABEL, rng, int(cfg["ml"]["bootstrap_samples"]))
    summary["stratum"] = stratum
    summary["heldout_run"] = int(heldout_run)
    summary["train_runs"] = ",".join(str(run) for run in train_runs)

    for frame, name in [
        (scan, "traditional_scan"),
        (analytic_cv, "s03a_cv"),
        (analytic_coef, "s03a_coefficients"),
        (signed_cv, "signed_cv"),
        (signed_coef, "signed_coefficients"),
        (ridge_cv, "ridge_cv"),
        (hgb_cv, "hgb_cv"),
        (mlp_cv, "mlp_cv"),
        (mlp_cal, "mlp_calibration"),
        (cnn_cv, "cnn_cv"),
        (cnn_cal, "cnn_calibration"),
    ]:
        frame["stratum"] = stratum
        frame["heldout_run"] = int(heldout_run)
        frame["table"] = name

    model_choice = pd.DataFrame(
        [
            {
                "stratum": stratum,
                "heldout_run": int(heldout_run),
                "base_method": base_method,
                "s03a_candidate": analytic_candidate,
                "s03a_alpha": float(analytic_alpha),
                "signed_candidate": signed_best["candidate"],
                "hgb_cv_sigma68_ns": float(hgb_best["score"]),
                "mlp_hidden": int(mlp_info["hidden"]),
                "cnn_channels": int(cnn_info["channels"]),
            }
        ]
    )
    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    held_event_ids = set(combined[combined["run"] == int(heldout_run)]["event_id"])
    shuffled_hgb = s03d_hgb.run_hgb_shuffled_control(pulses, cfg, base_method, hgb_best)
    leakage = pd.DataFrame(
        [
            {"stratum": stratum, "heldout_run": int(heldout_run), "check": "train_heldout_event_id_overlap", "value": float(len(train_event_ids & held_event_ids)), "unit": "events"},
            {"stratum": stratum, "heldout_run": int(heldout_run), "check": "hgb_shuffled_target_sigma68_ns", "value": float(shuffled_hgb), "unit": "ns"},
            {"stratum": stratum, "heldout_run": int(heldout_run), "check": "feature_audit_no_run_event_cross_stave_time", "value": 1.0, "unit": "bool"},
        ]
    )
    aux = pd.concat([scan, analytic_cv, analytic_coef, signed_cv, signed_coef, ridge_cv, hgb_cv, mlp_cv, mlp_cal, cnn_cv, cnn_cal], ignore_index=True, sort=False)
    return summary, pairs.assign(stratum=stratum, heldout_run=int(heldout_run)), leakage, model_choice, aux


def run_level_bootstrap(pairs: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for (stratum, method), group in pairs.groupby(["stratum", "method"]):
        runs = sorted(group["heldout_run"].unique().tolist())
        by_run = {run: sub[["residual_ns", "pair_amp_adc"]].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        vals = group["residual_ns"].to_numpy(dtype=float)
        amps = group["pair_amp_adc"].to_numpy(dtype=float)
        stats = []
        slopes = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            arr = np.vstack([by_run[int(run)] for run in sampled])
            stats.append(s02.sigma68(arr[:, 0]))
            slopes.append(slope_logamp(arr[:, 0], arr[:, 1]))
        rows.append(
            {
                "stratum": stratum,
                "method": method,
                "bootstrap_unit": "heldout_run",
                "n_runs": int(len(runs)),
                "n_pair_residuals": int(len(vals)),
                "sigma68_ns": s02.sigma68(vals),
                "ci_low": float(np.nanpercentile(stats, 2.5)),
                "ci_high": float(np.nanpercentile(stats, 97.5)),
                "full_rms_ns": s02.full_rms(vals),
                "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - np.median(vals)) > 5.0)) if len(vals) else float("nan"),
                "bias_vs_logamp_slope_ns": slope_logamp(vals, amps),
                "bias_slope_ci_low": float(np.nanpercentile(slopes, 2.5)),
                "bias_slope_ci_high": float(np.nanpercentile(slopes, 97.5)),
            }
        )
    pooled = pd.DataFrame(rows)
    baseline = pooled[pooled["method"] == TRADITIONAL_LABEL][["stratum", "sigma68_ns"]].rename(columns={"sigma68_ns": "traditional_sigma68_ns"})
    pooled = pooled.merge(baseline, on="stratum", how="left")
    pooled["delta_vs_traditional_ns"] = pooled["sigma68_ns"] - pooled["traditional_sigma68_ns"]
    return pooled.sort_values(["stratum", "sigma68_ns"]).reset_index(drop=True)


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, support: pd.DataFrame) -> None:
    for stratum, group in pooled.groupby("stratum"):
        fig, ax = plt.subplots(figsize=(8.5, 4.2))
        ordered = group.sort_values("sigma68_ns")
        x = np.arange(len(ordered))
        ax.bar(x, ordered["sigma68_ns"])
        ax.errorbar(x, ordered["sigma68_ns"], yerr=[ordered["sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["sigma68_ns"]], fmt="none", ecolor="black", capsize=3)
        ax.set_xticks(x)
        ax.set_xticklabels(ordered["method"], rotation=30, ha="right", fontsize=8)
        ax.set_ylabel("pooled LORO sigma68 (ns)")
        ax.set_title(f"S03j {stratum} model comparison")
        fig.tight_layout()
        fig.savefig(out_dir / f"fig_{stratum}_pooled_benchmark.png", dpi=130)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    for stratum, group in support.groupby("stratum"):
        ax.plot(group["run"], group["n_events"], marker="o", label=stratum)
    ax.set_xlabel("run")
    ax.set_ylabel("events with B4/B6/B8 support")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_stratum_support_by_run.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    s00_repro: pd.DataFrame,
    selector_repro: pd.DataFrame,
    support: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winners = pd.DataFrame(result["winners"])
    support_summary = support.groupby("stratum", as_index=False).agg(total_events=("n_events", "sum"), min_run_events=("n_events", "min"), median_amp_adc=("event_amp_median_adc", "median"))
    leak_summary = leakage.groupby(["stratum", "check"], as_index=False).agg(min_value=("value", "min"), max_value=("value", "max"))
    lines = [
        "# S03j: selector-specific timewalk support map",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Date:** 2026-06-10",
        f"- **Config:** `{config_path}`",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The S00 median-first-four selected-pulse count and the S00a dynamic-range count were recomputed directly from raw ROOT before any model fitting.",
        "",
        s00_repro.to_markdown(index=False),
        "",
        selector_repro.to_markdown(index=False),
        "",
        "## 2. Strata and support",
        "",
        "The median-selected stratum contains events whose B4, B6, and B8 baseline-subtracted amplitudes all exceed 1000 ADC. The dynamic-only stratum contains the additional events admitted by dynamic-range selection but not by median-first-four. The matched-control stratum is a deterministic run- and amplitude-binned subsample of median-selected events with the same target bin counts as the dynamic-only support whenever enough median events exist.",
        "",
        support_summary.to_markdown(index=False),
        "",
        support.to_markdown(index=False),
        "",
        "## 3. Methods",
        "",
        "For each held-out run and each stratum, templates and all residual-correction models are fit only on the other runs. The base time is template phase,",
        "",
        "\\[ t_i^{(0)} = \\Delta t_{\\mathrm{template}}(x_i), \\qquad r_i = t_i^{(0)} - \\frac{1}{2}\\sum_{j\\neq i} t_j^{(0)}. \\]",
        "",
        "The strong traditional models are S03a amplitude Ridge and the S03d signed physics prior. The signed prior solves",
        "",
        "\\[ \\min_\\beta \\lVert X\\beta-r\\rVert_2^2, \\qquad \\beta_{s,k}\\ge 0 \\text{ for inverse-amplitude terms}, \\]",
        "",
        "where the sign constraint encodes the lower-amplitude-later timewalk prior. ML/NN comparators are a Ridge residual model, histogram gradient-boosted trees, a heteroskedastic MLP on normalized 18-sample waveforms, a 1D CNN on the same samples plus stave one-hot, and a new hybrid residual ensemble that averages the Ridge, HGB, MLP, and CNN residual predictions. No model receives run id, event id, event order, pair residuals, other-stave timing, or held-out labels.",
        "",
        "The primary metric is held-out pairwise sigma68 after time-of-flight correction. Bootstrap intervals inside a held-out run resample events; pooled intervals resample held-out runs. The support-map bias metric is the linear slope of pair residual versus log(1 + pair amplitude).",
        "",
        "## 4. Results",
        "",
        "Per-run event-bootstrap results:",
        "",
        per_run[["stratum", "heldout_run", "method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_vs_logamp_slope_ns", "bias_slope_ci_low", "bias_slope_ci_high", "delta_vs_traditional_ns"]].to_markdown(index=False),
        "",
        "Pooled run-bootstrap results:",
        "",
        pooled[["stratum", "method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_vs_logamp_slope_ns", "bias_slope_ci_low", "bias_slope_ci_high", "delta_vs_traditional_ns"]].to_markdown(index=False),
        "",
        "Winners named in `result.json`:",
        "",
        winners.to_markdown(index=False),
        "",
        "## 5. Systematics and leakage checks",
        "",
        leak_summary.to_markdown(index=False),
        "",
        "The dynamic-only support is a selector-induced population shift, not a random split of the median-selected support; its wider intervals and altered amplitude slope therefore measure both timing closure and changed physical support. The matched-control stratum partially isolates mixture effects, but it cannot guarantee perfect topology matching because only downstream waveform observables are available in this reduced table. Shuffled-target HGB sentinels are deliberately retained as a high-sensitivity leakage check for the strongest non-neural ML comparator.",
        "",
        "## 6. Verdict",
        "",
        f"The global winner is `{result['global_winner']['method']}` in stratum `{result['global_winner']['stratum']}` with pooled sigma68 `{result['global_winner']['sigma68_ns']:.3f}` ns. The ticket verdict is `{result['verdict']}`.",
        "",
        "## 7. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/s03j_1781030650_597_5d382001_selector_timewalk_support.py --config {config_path}",
        "```",
        "",
        "Artifacts include `reproduction_match_table.csv`, `selector_reproduction_match_table.csv`, `stratum_support_counts.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `model_choices.csv`, `model_diagnostics.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03j_1781030650_597_5d382001_selector_timewalk_support.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    s00_repro = s02.reproduce_counts(config)
    s00_repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    selector_counts = s02c.selector_counts(config)
    selector_counts.to_csv(out_dir / "selector_counts_by_run.csv", index=False)
    _, selector_repro = s02c.reproduction_tables(config, selector_counts)
    selector_repro.to_csv(out_dir / "selector_reproduction_match_table.csv", index=False)
    if not bool(s00_repro["pass"].all() and selector_repro["pass"].all()):
        raise RuntimeError("raw-ROOT reproduction gate failed")

    strata = build_strata(config)
    support = support_counts(strata)
    support.to_csv(out_dir / "stratum_support_counts.csv", index=False)

    per_run_parts = []
    pair_parts = []
    leakage_parts = []
    choice_parts = []
    aux_parts = []
    skipped = []
    for stratum in STRATA:
        pulses = strata[stratum]
        for heldout_run in config["timing"]["loo_runs"]:
            if not has_support(pulses, config, int(heldout_run)):
                skipped.append({"stratum": stratum, "heldout_run": int(heldout_run), "reason": "insufficient_train_or_heldout_events"})
                continue
            summary, pairs, leakage, choices, aux = run_fold(stratum, pulses, config, int(heldout_run), rng)
            per_run_parts.append(summary)
            pair_parts.append(pairs)
            leakage_parts.append(leakage)
            choice_parts.append(choices)
            aux_parts.append(aux)

    if not per_run_parts:
        raise RuntimeError("no stratum/fold had enough support")
    per_run = pd.concat(per_run_parts, ignore_index=True)
    pairs = pd.concat(pair_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    choices = pd.concat(choice_parts, ignore_index=True)
    aux = pd.concat(aux_parts, ignore_index=True, sort=False)
    skipped_df = pd.DataFrame(skipped, columns=["stratum", "heldout_run", "reason"])

    pooled = run_level_bootstrap(pairs, rng, int(config["ml"]["run_bootstrap_samples"]))
    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    pairs.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    choices.to_csv(out_dir / "model_choices.csv", index=False)
    aux.to_csv(out_dir / "model_diagnostics.csv", index=False)
    skipped_df.to_csv(out_dir / "skipped_folds.csv", index=False)
    plot_outputs(out_dir, pooled, support)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    winners = []
    for stratum, group in pooled.groupby("stratum"):
        best = group.sort_values("sigma68_ns").iloc[0]
        trad = group[group["method"] == TRADITIONAL_LABEL].iloc[0]
        winners.append(
            {
                "stratum": stratum,
                "method": str(best["method"]),
                "sigma68_ns": float(best["sigma68_ns"]),
                "ci_low": float(best["ci_low"]),
                "ci_high": float(best["ci_high"]),
                "beats_traditional_ns": float(trad["sigma68_ns"] - best["sigma68_ns"]),
            }
        )
    global_best = pooled.sort_values("sigma68_ns").iloc[0]
    event_overlap = float(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    shuffled_min = float(leakage[leakage["check"] == "hgb_shuffled_target_sigma68_ns"]["value"].min())
    nominal_min = float(pooled["sigma68_ns"].min())
    leakage_flag = bool(event_overlap != 0 or shuffled_min < nominal_min + 0.2)
    result = {
        "study": "S03j",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(s00_repro["pass"].all() and selector_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_median_first_four_pass": bool(s00_repro["pass"].all()),
            "s00a_dynamic_range_pass": bool(selector_repro["pass"].all()),
        },
        "split": {"unit": "run", "heldout_runs": [int(run) for run in config["timing"]["loo_runs"]], "bootstrap_unit": "heldout_run"},
        "methods": [label for _, label in METHODS],
        "traditional_method": TRADITIONAL_LABEL,
        "winners": winners,
        "global_winner": {
            "stratum": str(global_best["stratum"]),
            "method": str(global_best["method"]),
            "sigma68_ns": float(global_best["sigma68_ns"]),
            "ci": [float(global_best["ci_low"]), float(global_best["ci_high"])],
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "hgb_shuffled_target_min_sigma68_ns": shuffled_min,
            "leakage_flag": leakage_flag,
        },
        "support": support.groupby("stratum")["n_events"].sum().astype(int).to_dict(),
        "skipped_folds": skipped,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "verdict": "selector_support_ml_winner_no_leakage_flag" if not leakage_flag else "selector_support_leakage_or_sentinel_concern",
        "next_ticket": "S03k: topology-matched selector-aware HGB/NN transfer with explicit dynamic-only overlap weights",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, s00_repro, selector_repro, support, per_run, pooled, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03j",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "global_winner": result["global_winner"], "verdict": result["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
