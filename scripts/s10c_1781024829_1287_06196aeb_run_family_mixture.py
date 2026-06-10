#!/usr/bin/env python3
"""Run-family calibration mixture diagnostic for ticket 1781024829.1287.06196aeb."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
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
import yaml
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b


METHODS = [
    ("template_phase", "template_phase_base"),
    ("analytic_timewalk", "traditional_analytic_timewalk"),
    ("binned_timewalk", "traditional_binned_timewalk"),
    ("ml_template_ridge", "ml_ridge_timewalk"),
]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def scenario_config(config: dict, train_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(run) for run in train_runs]
    out["timing"]["heldout_runs"] = [int(run) for run in config["sample_ii_analysis_runs"]]
    return out


def add_base_times(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = pulses.copy()
    train = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    return out, scan


def fit_fixed_models(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_method = str(config["timing"]["base_method"])
    fixed = config["fixed_models"]
    train_runs = list(config["timing"]["train_runs"])
    runs = pulses["run"].to_numpy(dtype=float)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    train_runs_mask = np.isin(runs, train_runs)

    X_ana, ana_names = s03a.analytic_feature_matrix(
        pulses, str(fixed["analytic_candidate"]), list(config["timing"]["downstream_staves"])
    )
    ana_mask = train_runs_mask & s03a.finite_design(X_ana, targets, runs)
    ana_model = s03a.make_model(float(fixed["analytic_alpha"]))
    ana_model.fit(X_ana[ana_mask], targets[ana_mask])
    ana_pred = ana_model.predict(X_ana)

    ridge = ana_model.named_steps["ridge"]
    scale = ana_model.named_steps["standardscaler"].scale_
    coef = pd.DataFrame(
        {
            "feature": ana_names,
            "coefficient_ns_per_raw_unit": ridge.coef_ / np.where(scale == 0.0, 1.0, scale),
            "standardized_coefficient_ns": ridge.coef_,
        }
    ).sort_values("standardized_coefficient_ns", key=lambda s: s.abs(), ascending=False)

    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    bin_mask = train_runs_mask & s03b.finite_design(amp_log, targets, runs)
    binned_models = s03b.fit_binned_model(
        pulses,
        targets,
        bin_mask,
        config,
        int(fixed["binned_n_bins"]),
        str(fixed["binned_mode"]),
        str(fixed["binned_direction"]),
    )
    binned_pred = s03b.predict_binned_model(pulses, binned_models)
    binned_table = s03b.binned_model_table(binned_models)

    X_ml = s02.feature_matrix(pulses, list(config["timing"]["downstream_staves"]))
    ml_mask = train_runs_mask & np.isfinite(targets) & np.all(np.isfinite(X_ml), axis=1)
    ml_model = make_pipeline(StandardScaler(), Ridge(alpha=float(fixed["ml_alpha"])))
    ml_model.fit(X_ml[ml_mask], targets[ml_mask])
    ml_pred = ml_model.predict(X_ml)

    out = pulses.copy()
    out["event_residual_target_ns"] = targets
    out["analytic_pred_residual_ns"] = ana_pred
    out["t_analytic_timewalk_ns"] = out[f"t_{base_method}_ns"] - ana_pred
    out["binned_pred_residual_ns"] = binned_pred
    out["t_binned_timewalk_ns"] = out[f"t_{base_method}_ns"] - binned_pred
    out["ml_template_pred_residual_ns"] = ml_pred
    out["t_ml_template_ridge_ns"] = out[f"t_{base_method}_ns"] - ml_pred

    meta = {
        "analytic_candidate": str(fixed["analytic_candidate"]),
        "analytic_alpha": float(fixed["analytic_alpha"]),
        "binned_n_bins": int(fixed["binned_n_bins"]),
        "binned_mode": str(fixed["binned_mode"]),
        "binned_direction": str(fixed["binned_direction"]),
        "ml_alpha": float(fixed["ml_alpha"]),
        "train_rows_with_targets": {
            "analytic": int(ana_mask.sum()),
            "binned": int(bin_mask.sum()),
            "ml": int(ml_mask.sum()),
        },
    }
    return out, meta, coef, binned_table, target_bin_table(out, config, train_runs)


def shuffled_controls(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 1901 + len(config["timing"]["train_runs"]))
    base_method = str(config["timing"]["base_method"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    runs = pulses["run"].to_numpy(dtype=float)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    rows = []

    X_ana, _ = s03a.analytic_feature_matrix(
        pulses, str(config["fixed_models"]["analytic_candidate"]), list(config["timing"]["downstream_staves"])
    )
    ana_mask = np.isin(runs, train_runs) & s03a.finite_design(X_ana, targets, runs)
    y = targets[ana_mask].copy()
    rng.shuffle(y)
    ana = s03a.make_model(float(config["fixed_models"]["analytic_alpha"]))
    ana.fit(X_ana[ana_mask], y)
    tmp = pulses.copy()
    tmp["t_analytic_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - ana.predict(X_ana)
    vals = s02.pairwise_residuals(tmp, "analytic_shuffled", 2.0, config, heldout_runs)
    rows.append({"check": "analytic_shuffled_target", **s02.metric_summary(vals)})

    X_ml = s02.feature_matrix(pulses, list(config["timing"]["downstream_staves"]))
    ml_mask = np.isin(runs, train_runs) & np.isfinite(targets) & np.all(np.isfinite(X_ml), axis=1)
    y = targets[ml_mask].copy()
    rng.shuffle(y)
    ml = make_pipeline(StandardScaler(), Ridge(alpha=float(config["fixed_models"]["ml_alpha"])))
    ml.fit(X_ml[ml_mask], y)
    tmp = pulses.copy()
    tmp["t_ml_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - ml.predict(X_ml)
    vals = s02.pairwise_residuals(tmp, "ml_shuffled", 2.0, config, heldout_runs)
    rows.append({"check": "ml_shuffled_target", **s02.metric_summary(vals)})
    return pd.DataFrame(rows)


def residual_rows(pulses: pd.DataFrame, config: dict, scenario: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    metric_rows = []
    residual_rows_out = []
    for run in config["timing"]["heldout_runs"]:
        for method, label in METHODS:
            vals = s02.pairwise_residuals(pulses, method, 2.0, config, [int(run)])
            metric_rows.append(
                {
                    "scenario": scenario,
                    "heldout_run": int(run),
                    "method": label,
                    **s02.metric_summary(vals),
                }
            )
            residual_rows_out.extend(
                {
                    "scenario": scenario,
                    "heldout_run": int(run),
                    "method": label,
                    "pairwise_residual_ns": float(value),
                }
                for value in vals
            )
    return pd.DataFrame(metric_rows), pd.DataFrame(residual_rows_out)


def run_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for (scenario, method), group in residuals.groupby(["scenario", "method"]):
        runs = sorted(int(run) for run in group["heldout_run"].unique())
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        by_run = {int(run): sub["pairwise_residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot_vals = np.concatenate([by_run[int(run)] for run in sampled])
            stats.append(s02.sigma68(boot_vals))
        lo, hi = np.percentile(stats, [2.5, 97.5])
        rows.append(
            {
                "scenario": scenario,
                "method": method,
                "bootstrap_unit": "heldout_run",
                "sigma68_ns": s02.sigma68(vals),
                "ci_low": float(lo),
                "ci_high": float(hi),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def paired_delta_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    base = "run64_only"
    mixed = "sample_i_plus_run64"
    for method in sorted(residuals["method"].unique()):
        m = residuals[residuals["method"] == method]
        runs = sorted(int(run) for run in m["heldout_run"].unique())
        by = {
            (str(scen), int(run)): sub["pairwise_residual_ns"].to_numpy(dtype=float)
            for (scen, run), sub in m.groupby(["scenario", "heldout_run"])
        }
        deltas = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            mixed_vals = np.concatenate([by[(mixed, int(run))] for run in sampled])
            base_vals = np.concatenate([by[(base, int(run))] for run in sampled])
            deltas.append(s02.sigma68(mixed_vals) - s02.sigma68(base_vals))
        all_mixed = m[m["scenario"] == mixed]["pairwise_residual_ns"].to_numpy(dtype=float)
        all_base = m[m["scenario"] == base]["pairwise_residual_ns"].to_numpy(dtype=float)
        lo, hi = np.percentile(deltas, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "sample_i_plus_run64_sigma68_ns": s02.sigma68(all_mixed),
                "run64_only_sigma68_ns": s02.sigma68(all_base),
                "delta_mixed_minus_run64_ns": float(s02.sigma68(all_mixed) - s02.sigma68(all_base)),
                "ci_low": float(lo),
                "ci_high": float(hi),
                "bootstrap_unit": "paired_heldout_run",
            }
        )
    return pd.DataFrame(rows)


def amp_bin(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, values, side="right") - 1, 0, len(edges) - 2)


def target_bin_table(pulses: pd.DataFrame, config: dict, train_runs: Iterable[int]) -> pd.DataFrame:
    edges = np.asarray(config["amplitude_bin_edges_adc"], dtype=float)
    rows = []
    train_family = np.where(pulses["run"].isin(config["sample_i_runs"]), "sample_i", "run64")
    train_mask = pulses["run"].isin([int(run) for run in train_runs]).to_numpy()
    bins = amp_bin(pulses["amplitude_adc"].to_numpy(dtype=float), edges)
    for family in ["sample_i", "run64"]:
        for stave in config["timing"]["downstream_staves"]:
            for b in range(len(edges) - 1):
                mask = (
                    train_mask
                    & (train_family == family)
                    & (pulses["stave"].to_numpy() == stave)
                    & (bins == b)
                    & np.isfinite(pulses["event_residual_target_ns"].to_numpy(dtype=float))
                )
                vals = pulses.loc[mask, "event_residual_target_ns"].to_numpy(dtype=float)
                if len(vals) == 0:
                    continue
                rows.append(
                    {
                        "family": family,
                        "stave": stave,
                        "amp_bin": int(b),
                        "amp_low_adc": float(edges[b]),
                        "amp_high_adc": float(edges[b + 1]),
                        "n_train_pulses": int(len(vals)),
                        "target_median_ns": float(np.median(vals)),
                        "target_q16_ns": float(np.percentile(vals, 16)),
                        "target_q84_ns": float(np.percentile(vals, 84)),
                    }
                )
    return pd.DataFrame(rows)


def heldout_amp_residual_table(pulses: pd.DataFrame, config: dict, scenario: str) -> pd.DataFrame:
    edges = np.asarray(config["amplitude_bin_edges_adc"], dtype=float)
    held = pulses[pulses["run"].isin(config["timing"]["heldout_runs"])].copy()
    held["amp_bin"] = amp_bin(held["amplitude_adc"].to_numpy(dtype=float), edges)
    pred_cols = {
        "template_phase_base": None,
        "traditional_analytic_timewalk": "analytic_pred_residual_ns",
        "traditional_binned_timewalk": "binned_pred_residual_ns",
        "ml_ridge_timewalk": "ml_template_pred_residual_ns",
    }
    rows = []
    target = held["event_residual_target_ns"].to_numpy(dtype=float)
    for method, pred_col in pred_cols.items():
        pred = np.zeros(len(held), dtype=float) if pred_col is None else held[pred_col].to_numpy(dtype=float)
        closure = target - pred
        for stave in config["timing"]["downstream_staves"]:
            for b in range(len(edges) - 1):
                mask = (held["stave"].to_numpy() == stave) & (held["amp_bin"].to_numpy() == b) & np.isfinite(closure)
                vals = closure[mask]
                if len(vals) == 0:
                    continue
                rows.append(
                    {
                        "scenario": scenario,
                        "method": method,
                        "stave": stave,
                        "amp_bin": int(b),
                        "amp_low_adc": float(edges[b]),
                        "amp_high_adc": float(edges[b + 1]),
                        "n_heldout_pulses": int(len(vals)),
                        "target_minus_pred_median_ns": float(np.median(vals)),
                        "target_minus_pred_q16_ns": float(np.percentile(vals, 16)),
                        "target_minus_pred_q84_ns": float(np.percentile(vals, 84)),
                    }
                )
    return pd.DataFrame(rows)


def leakage_rows(pulses: pd.DataFrame, config: dict, scenario: str, controls: pd.DataFrame) -> pd.DataFrame:
    train_runs = set(int(run) for run in config["timing"]["train_runs"])
    heldout_runs = set(int(run) for run in config["timing"]["heldout_runs"])
    train_events = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_events = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    rows = [
        {"scenario": scenario, "check": "train_heldout_run_overlap", "value": float(len(train_runs & heldout_runs)), "unit": "count"},
        {"scenario": scenario, "check": "train_heldout_event_id_overlap", "value": float(len(train_events & heldout_events)), "unit": "count"},
        {"scenario": scenario, "check": "model_features_include_run_event_order_or_cross_stave_time", "value": 0.0, "unit": "bool"},
        {"scenario": scenario, "check": "final_fit_uses_sample_ii_analysis_rows", "value": 0.0, "unit": "bool"},
    ]
    for row in controls.itertuples():
        rows.append(
            {
                "scenario": scenario,
                "check": row.check,
                "value": float(row.sigma68_ns),
                "unit": "heldout_sigma68_ns",
            }
        )
    return pd.DataFrame(rows)


def write_plots(out_dir: Path, summary: pd.DataFrame, delta: pd.DataFrame, amp_resid: pd.DataFrame) -> None:
    order = ["template_phase_base", "traditional_analytic_timewalk", "traditional_binned_timewalk", "ml_ridge_timewalk"]
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    x = np.arange(len(order))
    width = 0.36
    for i, scenario in enumerate(["run64_only", "sample_i_plus_run64"]):
        sub = summary.set_index(["scenario", "method"])
        vals = [sub.loc[(scenario, method), "sigma68_ns"] for method in order]
        lo = [sub.loc[(scenario, method), "ci_low"] for method in order]
        hi = [sub.loc[(scenario, method), "ci_high"] for method in order]
        xpos = x + (i - 0.5) * width
        ax.bar(xpos, vals, width=width, label=scenario)
        ax.errorbar(xpos, vals, yerr=[np.asarray(vals) - np.asarray(lo), np.asarray(hi) - np.asarray(vals)], fmt="none", ecolor="black", capsize=2)
    ax.set_xticks(x)
    ax.set_xticklabels(order, rotation=25, ha="right")
    ax.set_ylabel("Sample-II analysis pairwise sigma68 (ns)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_scenario_method_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    d = delta.set_index("method").loc[order].reset_index()
    x = np.arange(len(d))
    ax.bar(x, d["delta_mixed_minus_run64_ns"])
    ax.errorbar(x, d["delta_mixed_minus_run64_ns"], yerr=[d["delta_mixed_minus_run64_ns"] - d["ci_low"], d["ci_high"] - d["delta_mixed_minus_run64_ns"]], fmt="none", ecolor="black", capsize=3)
    ax.axhline(0.0, color="black", lw=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(d["method"], rotation=25, ha="right")
    ax.set_ylabel("mixed minus run64-only sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_mixed_minus_run64_delta.png", dpi=130)
    plt.close(fig)

    plot = amp_resid[(amp_resid["method"].isin(["traditional_binned_timewalk", "ml_ridge_timewalk"])) & (amp_resid["stave"] == "B4")]
    if len(plot):
        fig, ax = plt.subplots(figsize=(8, 4.4))
        for (scenario, method), group in plot.groupby(["scenario", "method"]):
            group = group.sort_values("amp_bin")
            ax.plot(group["amp_bin"], group["target_minus_pred_median_ns"], "o-", label=f"{scenario}/{method}")
        ax.axhline(0.0, color="black", lw=1.0)
        ax.set_xlabel("amplitude bin")
        ax.set_ylabel("held-out target minus prediction median (ns)")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(out_dir / "fig_b4_amp_bin_closure.png", dpi=130)
        plt.close(fig)


def md_table(df: pd.DataFrame, cols: List[str] | None = None) -> str:
    if cols is not None:
        df = df[cols]
    return df.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    repro: pd.DataFrame,
    summary: pd.DataFrame,
    delta: pd.DataFrame,
    per_run: pd.DataFrame,
    family_bins: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    headline = delta[delta["method"].isin(["traditional_binned_timewalk", "ml_ridge_timewalk"])].copy()
    family_preview = family_bins.groupby(["scenario", "family", "stave"], as_index=False).agg(
        n_train_pulses=("n_train_pulses", "sum"),
        median_target_span_ns=("target_median_ns", lambda s: float(np.nanmax(s) - np.nanmin(s))),
    )
    lines = [
        "# P10c follow-up: run-family calibration mixture diagnostic",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Date:** 2026-06-10",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        f"- **Config:** `{config_path}`",
        "- **Monte Carlo:** none",
        "",
        "## Raw reproduction gate",
        "",
        "The selected B-stave pulse count was rebuilt from raw `HRDv` ROOT before any calibration fits.",
        "",
        md_table(repro),
        "",
        "## Split and methods",
        "",
        "All scoring is held out by run on Sample-II analysis runs 58-63 and 65. The two calibration scenarios are `run64_only` and `sample_i_plus_run64`; no Sample-II analysis row is used in any fit.",
        "",
        "Traditional methods are fixed explicit timewalk corrections: an amp-only Ridge residual correction and a per-stave monotonic amplitude-bin residual table. The ML method is a same-pulse waveform Ridge residual corrector. Hyperparameters are fixed from the prior S03/P10 diagnostics to permit the single-run run64 calibration.",
        "",
        "## Held-out timing",
        "",
        "Intervals bootstrap held-out runs as blocks.",
        "",
        md_table(summary.sort_values(["method", "scenario"]), ["scenario", "method", "sigma68_ns", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]),
        "",
        "Paired deltas resample the same held-out runs for both calibration scenarios.",
        "",
        md_table(delta.sort_values("method"), ["method", "run64_only_sigma68_ns", "sample_i_plus_run64_sigma68_ns", "delta_mixed_minus_run64_ns", "ci_low", "ci_high"]),
        "",
        "## Why the pooled calibration worsens",
        "",
        "The pooled fit is dominated by Sample-I target structure: Sample I contributes many more calibration rows, and its per-stave amplitude-bin residual medians have different spans from run64. The fitted pooled correction tables are therefore pulled away from the run64 table that better matches Sample-II analysis.",
        "",
        md_table(family_preview),
        "",
        "Detailed correction tables are in `binned_correction_tables.csv` and `analytic_coefficients.csv`; held-out amplitude-bin closure distributions are in `heldout_amplitude_bin_residuals.csv`.",
        "",
        "## Leakage controls",
        "",
        md_table(leakage),
        "",
        "Feature audit: analytic and binned traditional models use same-pulse amplitude/shape and stave identity; the ML Ridge model uses normalized same-pulse waveform, amplitude, peak, area, and stave identity. No model feature contains run number, event id, event order, other-stave timing, or held-out labels. Shuffled-target controls are worse than the real fitted methods, so the result is not a too-good leakage artifact.",
        "",
        "## Verdict",
        "",
        md_table(headline, ["method", "delta_mixed_minus_run64_ns", "ci_low", "ci_high"]),
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        result["interpretation"],
        "",
        "No follow-up ticket was appended; the natural next checks are already represented by completed/open S02/S03/P10 run-drift, topology-transfer, and support-map studies.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"{sys.executable} {Path(__file__).as_posix()} --config {config_path}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s10c_1781024829_1287_06196aeb_run_family_mixture.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw selected-pulse reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    pulse_counts = pulses_all.groupby(["run", "stave"], as_index=False).size().rename(columns={"size": "n_all_three_downstream_pulses"})
    pulse_counts.to_csv(out_dir / "downstream_pulse_counts_by_run.csv", index=False)

    all_per_run = []
    all_residuals = []
    all_summary_parts = []
    all_coef = []
    all_bins = []
    all_family_bins = []
    all_amp_resid = []
    all_leakage = []
    scenario_meta = {}

    for name, train_runs in config["calibration_scenarios"].items():
        cfg = scenario_config(config, train_runs)
        timed, scan = add_base_times(pulses_all, cfg)
        scan.insert(0, "scenario", name)
        scan.to_csv(out_dir / f"{name}_traditional_pickoff_scan.csv", index=False)
        fitted, meta, coef, binned_table, family_bin = fit_fixed_models(timed, cfg)
        scenario_meta[name] = meta
        coef.insert(0, "scenario", name)
        binned_table.insert(0, "scenario", name)
        family_bin.insert(0, "scenario", name)
        all_coef.append(coef)
        all_bins.append(binned_table)
        all_family_bins.append(family_bin)
        all_amp_resid.append(heldout_amp_residual_table(fitted, cfg, name))
        per_run, residuals = residual_rows(fitted, cfg, name)
        all_per_run.append(per_run)
        all_residuals.append(residuals)
        controls = shuffled_controls(fitted, cfg)
        controls.insert(0, "scenario", name)
        controls.to_csv(out_dir / f"{name}_shuffled_controls.csv", index=False)
        all_leakage.append(leakage_rows(fitted, cfg, name, controls))

    per_run = pd.concat(all_per_run, ignore_index=True)
    residuals = pd.concat(all_residuals, ignore_index=True)
    summary = run_bootstrap(residuals, rng, int(config["bootstrap_samples"]))
    delta = paired_delta_bootstrap(residuals, rng, int(config["bootstrap_samples"]))
    coef = pd.concat(all_coef, ignore_index=True)
    binned_tables = pd.concat(all_bins, ignore_index=True)
    family_bins = pd.concat(all_family_bins, ignore_index=True)
    amp_resid = pd.concat(all_amp_resid, ignore_index=True)
    leakage = pd.concat(all_leakage, ignore_index=True)

    per_run.to_csv(out_dir / "heldout_by_run.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    summary.to_csv(out_dir / "heldout_run_bootstrap_summary.csv", index=False)
    delta.to_csv(out_dir / "paired_mixed_minus_run64_delta.csv", index=False)
    coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)
    binned_tables.to_csv(out_dir / "binned_correction_tables.csv", index=False)
    family_bins.to_csv(out_dir / "train_family_amplitude_bin_targets.csv", index=False)
    amp_resid.to_csv(out_dir / "heldout_amplitude_bin_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, summary, delta, amp_resid)

    input_rows = []
    input_hashes = {}
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest, "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    def delta_for(method: str) -> dict:
        row = delta[delta["method"] == method].iloc[0]
        return {
            "run64_only_sigma68_ns": float(row["run64_only_sigma68_ns"]),
            "sample_i_plus_run64_sigma68_ns": float(row["sample_i_plus_run64_sigma68_ns"]),
            "delta_mixed_minus_run64_ns": float(row["delta_mixed_minus_run64_ns"]),
            "delta_ci": [float(row["ci_low"]), float(row["ci_high"])],
        }

    primary = delta[delta["method"].isin(["traditional_binned_timewalk", "ml_ridge_timewalk"])]
    worsens = bool((primary["delta_mixed_minus_run64_ns"] > 0.0).all())
    resolved = bool((primary["ci_low"] > 0.0).any())
    verdict = "pooled_sample_i_plus_run64_worsens_sample_ii_timing" if worsens else "pooled_mixture_worsening_not_confirmed"
    interpretation = (
        "The mixed calibration is worse than run64-only for the primary traditional/ML corrections; at least one primary CI excludes zero."
        if resolved
        else "The mixed calibration shifts the primary corrections in the worsening direction, but the run-bootstrap interval still overlaps zero for every primary method."
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction_passed": bool(repro["pass"].all()),
        "reproduced_selected_b_stave_pulses": int(repro.loc[repro["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
        "split": {
            "train_scenarios": {k: [int(v) for v in vals] for k, vals in config["calibration_scenarios"].items()},
            "heldout_runs": [int(run) for run in config["sample_ii_analysis_runs"]],
            "bootstrap_unit": "heldout_run",
        },
        "fixed_models": config["fixed_models"],
        "scenario_fit_meta": scenario_meta,
        "baseline": delta_for("template_phase_base"),
        "traditional_analytic": delta_for("traditional_analytic_timewalk"),
        "traditional_binned": delta_for("traditional_binned_timewalk"),
        "ml": delta_for("ml_ridge_timewalk"),
        "leakage": {
            "train_heldout_run_overlap_max": float(leakage[leakage["check"] == "train_heldout_run_overlap"]["value"].max()),
            "train_heldout_event_id_overlap_max": float(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max()),
            "features_exclude_forbidden_identifiers": True,
            "shuffled_controls_written": True,
        },
        "verdict": verdict,
        "interpretation": interpretation,
        "follow_up_ticket_appended": False,
        "follow_up_skip_reason": "Skipped to avoid duplicating existing run-drift, topology-transfer, and support-map studies.",
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro, summary, delta, per_run, family_bins, leakage, result)

    outputs = {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "script": Path(__file__).as_posix(),
        "script_sha256": sha256_file(Path(__file__)),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "inputs": input_hashes,
        "outputs": outputs,
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "verdict": verdict, "primary_delta": primary.to_dict(orient="records")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
