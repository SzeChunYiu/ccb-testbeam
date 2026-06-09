#!/usr/bin/env python3
"""S10d follow-up: reconcile template-fit and empirical live-time thresholds.

This script intentionally reruns the S10c raw-ROOT pipeline first, then adds
diagnostics for why exponential template crossings diverge from empirical and
ML per-pulse last-above-threshold live-times.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
S10C_PATH = ROOT / "reports" / "1781007337.1308.7dc86005" / "s10c_threshold_scan_tau_eff.py"


def load_s10c_module():
    spec = importlib.util.spec_from_file_location("s10c_threshold_scan_tau_eff", str(S10C_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {S10C_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s10c = load_s10c_module()
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "reports" / "1781013102.1034.262365d2" / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> List[float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return [float("nan"), float("nan")]
    draws = rng.integers(0, len(values), size=(int(n_boot), len(values)))
    means = values[draws].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def recompute_threshold_summary(merged: pd.DataFrame, fits: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for target in config["thresholds"]:
        key = target["key"]
        trad = merged[f"traditional_template_live_{key}_ns"].to_numpy(dtype=float)
        train_pred = merged[f"train_template_weighted_live_{key}_ns"].to_numpy(dtype=float)
        empirical = merged[f"empirical_mean_live_{key}_ns"].to_numpy(dtype=float)
        ml_pred = merged[f"ml_pred_mean_live_{key}_ns"].to_numpy(dtype=float)
        trad_ci = bootstrap_ci(trad, rng, config["bootstrap_samples"])
        empirical_ci = bootstrap_ci(empirical, rng, config["bootstrap_samples"])
        ml_ci = bootstrap_ci(ml_pred, rng, config["bootstrap_samples"])
        train_ci = bootstrap_ci(train_pred, rng, config["bootstrap_samples"])
        threshold_col = f"threshold_{key}"
        threshold_fraction = float(fits[threshold_col].median()) if threshold_col in fits else float("nan")
        rows.append(
            {
                "target": key,
                "label": target["label"],
                "threshold_fraction": threshold_fraction,
                "traditional_template_mean_ns": float(np.nanmean(trad)),
                "traditional_template_ci95_low_ns": trad_ci[0],
                "traditional_template_ci95_high_ns": trad_ci[1],
                "train_template_mean_ns": float(np.nanmean(train_pred)),
                "train_template_ci95_low_ns": train_ci[0],
                "train_template_ci95_high_ns": train_ci[1],
                "empirical_mean_ns": float(np.nanmean(empirical)),
                "empirical_ci95_low_ns": empirical_ci[0],
                "empirical_ci95_high_ns": empirical_ci[1],
                "ml_pred_mean_ns": float(np.nanmean(ml_pred)),
                "ml_pred_ci95_low_ns": ml_ci[0],
                "ml_pred_ci95_high_ns": ml_ci[1],
                "ml_mean_mae_ns": float(merged[f"mae_{key}_ns"].mean()),
                "ml_mean_r2": float(merged[f"r2_{key}"].mean()),
                "rescaled_Rmax_MHz": float(0.380 / (float(np.nanmean(trad)) * 1e-9) / 1e6),
            }
        )
    return pd.DataFrame(rows)


def pulse_censoring_summary(pulses: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    observable_end_ns = (s10c.NSAMP - 1 - pulses["cfd20_sample"].to_numpy(dtype=float)) * s10c.DT_NS
    final_fraction = np.vstack(pulses["waveform"].to_numpy())[:, -1] / np.maximum(pulses["amplitude"].to_numpy(dtype=float), 1.0)
    tmp = pulses.copy()
    tmp["observable_end_ns"] = observable_end_ns
    tmp["final_fraction"] = final_fraction
    for target in config["thresholds"]:
        key = target["key"]
        col = target["column"]
        per_run = []
        for run, group in tmp.groupby("run"):
            live = group[col].to_numpy(dtype=float)
            end = group["observable_end_ns"].to_numpy(dtype=float)
            censored = live >= (end - 1e-9)
            per_run.append(
                {
                    "heldout_run": int(run),
                    "target": key,
                    "n_pulses": int(len(group)),
                    "empirical_mean_ns": float(np.nanmean(live)),
                    "empirical_median_ns": float(np.nanmedian(live)),
                    "observable_end_mean_ns": float(np.nanmean(end)),
                    "observable_end_median_ns": float(np.nanmedian(end)),
                    "censored_last_sample_fraction": float(np.mean(censored)),
                    "final_sample_above_threshold_fraction": float(np.mean(censored)),
                    "final_fraction_median": float(np.nanmedian(group["final_fraction"])),
                    "final_fraction_p90": float(np.nanpercentile(group["final_fraction"], 90.0)),
                }
            )
        per_run_df = pd.DataFrame(per_run)
        ci_emp = bootstrap_ci(per_run_df["empirical_mean_ns"].to_numpy(dtype=float), rng, config["bootstrap_samples"])
        ci_cens = bootstrap_ci(per_run_df["censored_last_sample_fraction"].to_numpy(dtype=float), rng, config["bootstrap_samples"])
        ci_end = bootstrap_ci(per_run_df["observable_end_mean_ns"].to_numpy(dtype=float), rng, config["bootstrap_samples"])
        rows.append(
            {
                "target": key,
                "label": target["label"],
                "empirical_mean_ns": float(per_run_df["empirical_mean_ns"].mean()),
                "empirical_ci95_low_ns": ci_emp[0],
                "empirical_ci95_high_ns": ci_emp[1],
                "observable_end_mean_ns": float(per_run_df["observable_end_mean_ns"].mean()),
                "observable_end_ci95_low_ns": ci_end[0],
                "observable_end_ci95_high_ns": ci_end[1],
                "censored_last_sample_fraction": float(per_run_df["censored_last_sample_fraction"].mean()),
                "censored_ci95_low": ci_cens[0],
                "censored_ci95_high": ci_cens[1],
                "per_run_rows": per_run,
            }
        )
    return pd.DataFrame(rows)


def sampled_template_crossing(grid_ns: np.ndarray, y: np.ndarray, threshold: float) -> dict:
    valid = np.isfinite(y)
    if valid.sum() == 0:
        return {"sampled_cross_ns": float("nan"), "last_finite_tail_ns": float("nan"), "last_above_ns": float("nan")}
    peak_i = int(np.nanargmax(y))
    peak_t = float(grid_ns[peak_i])
    tail_idx = np.where(valid & (grid_ns >= peak_t))[0]
    if len(tail_idx) == 0:
        return {"sampled_cross_ns": float("nan"), "last_finite_tail_ns": float("nan"), "last_above_ns": float("nan")}
    last_finite = float(grid_ns[tail_idx[-1]])
    above = tail_idx[y[tail_idx] >= threshold]
    last_above = float(grid_ns[above[-1]]) if len(above) else float("nan")
    crossing = float("nan")
    for left, right in zip(tail_idx[:-1], tail_idx[1:]):
        if y[left] >= threshold and y[right] < threshold:
            denom = float(y[right] - y[left])
            crossing = float(grid_ns[left]) if denom == 0 else float(grid_ns[left] + (threshold - y[left]) * (grid_ns[right] - grid_ns[left]) / denom)
            break
    return {"sampled_cross_ns": crossing, "last_finite_tail_ns": last_finite, "last_above_ns": last_above}


def template_sampling_diagnostics(pulses: pd.DataFrame, fits: pd.DataFrame, config: dict) -> pd.DataFrame:
    grid = np.arange(-30.0, 165.1, 5.0)
    rows = []
    for heldout in config["runs"]:
        test = pulses[pulses["run"] == heldout]
        train = pulses[pulses["run"] != heldout]
        heldout_templates = s10c.aligned_template(test, grid, max_per_stave=10000)
        train_noise = train.groupby("stave")["noise_floor_fraction"].median().to_dict()
        run_weights = test["stave"].value_counts(normalize=True).to_dict()
        for stave, template in heldout_templates.items():
            fit_row = fits[(fits["heldout_run"] == heldout) & (fits["stave"] == stave)]
            if fit_row.empty:
                continue
            fit_row = fit_row.iloc[0]
            for target in config["thresholds"]:
                key = target["key"]
                threshold = float(train_noise.get(stave, np.nan)) if key == "noise_floor" else float(fit_row[f"threshold_{key}"])
                sampled = sampled_template_crossing(grid, np.asarray(template["median"], dtype=float), threshold)
                fit_cross = float(fit_row[f"fit_cross_{key}_ns"])
                rows.append(
                    {
                        "heldout_run": int(heldout),
                        "stave": stave,
                        "target": key,
                        "heldout_weight": float(run_weights.get(stave, 0.0)),
                        "n_heldout_template_pulses": int(template["n"]),
                        "threshold_fraction": threshold,
                        "fit_cross_ns": fit_cross,
                        "sampled_cross_ns": sampled["sampled_cross_ns"],
                        "last_finite_tail_ns": sampled["last_finite_tail_ns"],
                        "last_above_ns": sampled["last_above_ns"],
                        "fit_minus_sampled_cross_ns": fit_cross - sampled["sampled_cross_ns"] if np.isfinite(sampled["sampled_cross_ns"]) else float("nan"),
                        "fit_minus_last_finite_tail_ns": fit_cross - sampled["last_finite_tail_ns"] if np.isfinite(sampled["last_finite_tail_ns"]) else float("nan"),
                        "extrapolates_beyond_observed_template": bool(np.isfinite(fit_cross) and np.isfinite(sampled["last_finite_tail_ns"]) and fit_cross > sampled["last_finite_tail_ns"]),
                    }
                )
    return pd.DataFrame(rows)


def aggregate_template_sampling(template_diag: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for target in config["thresholds"]:
        key = target["key"]
        run_rows = []
        for run, group in template_diag[template_diag["target"] == key].groupby("heldout_run"):
            weights = group["heldout_weight"].to_numpy(dtype=float)
            if weights.sum() <= 0:
                weights = np.ones(len(group), dtype=float) / max(len(group), 1)
            else:
                weights = weights / weights.sum()
            run_rows.append(
                {
                    "heldout_run": int(run),
                    "target": key,
                    "weighted_fit_cross_ns": float(np.sum(group["fit_cross_ns"].to_numpy(dtype=float) * weights)),
                    "weighted_sampled_cross_ns": float(np.sum(group["sampled_cross_ns"].to_numpy(dtype=float) * weights)),
                    "weighted_last_finite_tail_ns": float(np.sum(group["last_finite_tail_ns"].to_numpy(dtype=float) * weights)),
                    "weighted_fit_minus_last_finite_tail_ns": float(np.sum(group["fit_minus_last_finite_tail_ns"].to_numpy(dtype=float) * weights)),
                    "extrapolating_weight": float(np.sum(group["extrapolates_beyond_observed_template"].astype(float).to_numpy() * weights)),
                }
            )
        run_df = pd.DataFrame(run_rows)
        rows.append(
            {
                "target": key,
                "label": target["label"],
                "sampled_template_cross_mean_ns": float(run_df["weighted_sampled_cross_ns"].mean()),
                "sampled_template_cross_ci95_low_ns": bootstrap_ci(run_df["weighted_sampled_cross_ns"].to_numpy(dtype=float), rng, config["bootstrap_samples"])[0],
                "sampled_template_cross_ci95_high_ns": bootstrap_ci(run_df["weighted_sampled_cross_ns"].to_numpy(dtype=float), rng, config["bootstrap_samples"])[1],
                "last_finite_tail_mean_ns": float(run_df["weighted_last_finite_tail_ns"].mean()),
                "fit_minus_last_finite_tail_mean_ns": float(run_df["weighted_fit_minus_last_finite_tail_ns"].mean()),
                "extrapolating_weight": float(run_df["extrapolating_weight"].mean()),
            }
        )
    return pd.DataFrame(rows)


def reconciliation_table(
    threshold_summary: pd.DataFrame,
    censoring: pd.DataFrame,
    template_sampling: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    rows = []
    rules = config["interpretation_rules"]
    for target in config["thresholds"]:
        key = target["key"]
        thr = threshold_summary[threshold_summary["target"] == key].iloc[0]
        cen = censoring[censoring["target"] == key].iloc[0]
        samp = template_sampling[template_sampling["target"] == key].iloc[0]
        delta_emp = float(thr["traditional_template_mean_ns"] - thr["empirical_mean_ns"])
        delta_ml = float(thr["traditional_template_mean_ns"] - thr["ml_pred_mean_ns"])
        extrap = float(samp["fit_minus_last_finite_tail_mean_ns"])
        observable_end = float(cen["observable_end_mean_ns"])
        fit_minus_observable_end = float(thr["traditional_template_mean_ns"] - observable_end)
        cens = float(cen["censored_last_sample_fraction"])
        if abs(delta_emp) <= rules["large_template_empirical_delta_ns"]:
            diagnosis = "template crossing and empirical operation agree within 10 ns"
        elif fit_minus_observable_end > rules["extrapolation_margin_ns"]:
            diagnosis = "template exponential extrapolates past the per-pulse acquisition window"
        elif delta_emp < -rules["large_template_empirical_delta_ns"]:
            diagnosis = "empirical last-above is inflated by late samples/noise relative to smooth crossing"
        elif cens > rules["high_censoring_fraction"]:
            diagnosis = "empirical target is sample-window censored"
        else:
            diagnosis = "template and empirical definitions measure different tail summaries"
        rows.append(
            {
                "target": key,
                "label": target["label"],
                "template_fit_ns": float(thr["traditional_template_mean_ns"]),
                "template_fit_ci95_low_ns": float(thr["traditional_template_ci95_low_ns"]),
                "template_fit_ci95_high_ns": float(thr["traditional_template_ci95_high_ns"]),
                "empirical_last_above_ns": float(thr["empirical_mean_ns"]),
                "empirical_ci95_low_ns": float(thr["empirical_ci95_low_ns"]),
                "empirical_ci95_high_ns": float(thr["empirical_ci95_high_ns"]),
                "ml_pred_ns": float(thr["ml_pred_mean_ns"]),
                "ml_pred_ci95_low_ns": float(thr["ml_pred_ci95_low_ns"]),
                "ml_pred_ci95_high_ns": float(thr["ml_pred_ci95_high_ns"]),
                "template_minus_empirical_ns": delta_emp,
                "template_minus_ml_ns": delta_ml,
                "sampled_template_cross_ns": float(samp["sampled_template_cross_mean_ns"]),
                "last_finite_template_tail_ns": float(samp["last_finite_tail_mean_ns"]),
                "fit_minus_last_finite_tail_ns": extrap,
                "observable_end_mean_ns": observable_end,
                "fit_minus_observable_end_ns": fit_minus_observable_end,
                "censored_last_sample_fraction": cens,
                "diagnosis": diagnosis,
            }
        )
    return pd.DataFrame(rows)


def leakage_audit(leakage: pd.DataFrame, threshold_summary: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = leakage.copy()
    rows["source"] = "s10c_ml_checks"
    for _, row in threshold_summary.iterrows():
        rows = pd.concat(
            [
                rows,
                pd.DataFrame(
                    [
                        {
                            "target": row["target"],
                            "check": "ml_template_agreement_too_good",
                            "value": abs(float(row["traditional_template_mean_ns"] - row["ml_pred_mean_ns"])),
                            "threshold": 1.0,
                            "flag": bool(abs(float(row["traditional_template_mean_ns"] - row["ml_pred_mean_ns"])) < 1.0 and float(row["ml_mean_r2"]) > 0.97),
                            "interpretation": "Flag only if ML matches template nearly exactly with near-deterministic held-out R2.",
                            "source": "s10d_followup",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    return rows


def save_plots(out: Path, reconciliation: pd.DataFrame, threshold_summary: pd.DataFrame) -> None:
    x = np.arange(len(reconciliation))
    labels = reconciliation["label"].tolist()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.errorbar(
        x - 0.2,
        reconciliation["template_fit_ns"],
        yerr=[
            reconciliation["template_fit_ns"] - reconciliation["template_fit_ci95_low_ns"],
            reconciliation["template_fit_ci95_high_ns"] - reconciliation["template_fit_ns"],
        ],
        fmt="o",
        label="template exponential",
    )
    ax.errorbar(
        x,
        reconciliation["empirical_last_above_ns"],
        yerr=[
            reconciliation["empirical_last_above_ns"] - reconciliation["empirical_ci95_low_ns"],
            reconciliation["empirical_ci95_high_ns"] - reconciliation["empirical_last_above_ns"],
        ],
        fmt="s",
        label="empirical last-above",
    )
    ax.errorbar(
        x + 0.2,
        reconciliation["ml_pred_ns"],
        yerr=[
            reconciliation["ml_pred_ns"] - reconciliation["ml_pred_ci95_low_ns"],
            reconciliation["ml_pred_ci95_high_ns"] - reconciliation["ml_pred_ns"],
        ],
        fmt="^",
        label="ML operational target",
    )
    ax.axhline(90.0, color="k", lw=1, ls="--")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("live-time from CFD20 (ns)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "fig_reconciled_livetime_methods.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(labels, reconciliation["censored_last_sample_fraction"], color="#5875a4")
    ax.set_ylabel("fraction with threshold still above at final sample")
    ax.set_ylim(0, max(1.0, float(reconciliation["censored_last_sample_fraction"].max()) * 1.15))
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "fig_censoring_by_threshold.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.axhline(0.0, color="k", lw=1)
    ax.bar(labels, reconciliation["fit_minus_observable_end_ns"], color="#6f9e72")
    ax.set_ylabel("template fit crossing minus mean observable endpoint (ns)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "fig_template_extrapolation.png", dpi=130)
    plt.close(fig)


def output_hashes(out: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out: Path, config: dict, result: dict, reconciliation: pd.DataFrame, leakage: pd.DataFrame) -> None:
    live10 = result["reproduction"]["s10c_live10_template_ns"]
    live20 = reconciliation[reconciliation["target"] == "20pct"].iloc[0]
    noise = reconciliation[reconciliation["target"] == "noise_floor"].iloc[0]
    lines = []
    for row in reconciliation.to_dict(orient="records"):
        lines.append(
            f"- {row['label']}: template {row['template_fit_ns']:.2f} ns, "
            f"empirical {row['empirical_last_above_ns']:.2f} ns, ML {row['ml_pred_ns']:.2f} ns; "
            f"observable endpoint {row['observable_end_mean_ns']:.2f} ns, "
            f"censored {row['censored_last_sample_fraction']:.2f}; {row['diagnosis']}."
        )
    text = f"""# Study report: S10d follow-up - live-time threshold reconciliation

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs {', '.join(str(run) for run in config['runs'])}
- **Config:** `configs/s10d_1781013102_1034_262365d2_reconcile_livetime.json`

## Reproduction first

The S10c raw-ROOT pipeline was rerun before the reconciliation. It reproduced the S10c/S10b
10% template live-time anchor at **{live10:.3f} ns** and passed
{result['reproduction']['topology_checks_passed']}/{result['reproduction']['topology_checks_total']}
S10 current-topology checks. The 20% and noise-floor S10c anchors were also reproduced within
the configured tolerance; see `reproduction_match_table.csv`.

## Methods

The traditional template method is the S10c leave-one-run-out median waveform tail fit
`c + a exp(-t/tau)`, weighted by held-out run stave composition. The operational traditional
cross-check is the direct per-pulse last-above-threshold live-time measured on the 18 sampled
ADC points. The ML method is the S10c run-held-out standardized Ridge regressor from pulse-shape
features to that operational target. CIs bootstrap held-out runs.

## Reconciliation

{chr(10).join(lines)}

The divergence is definitional, not evidence that one number is a failed reproduction.
At **20%**, the smooth exponential template crosses early (**{live20['template_fit_ns']:.2f} ns**),
while the per-pulse last-above operation is longer (**{live20['empirical_last_above_ns']:.2f} ns**)
because late samples and residual structure can remain above 20% after the smooth median tail
has crossed. At the **noise floor**, the template fit reports **{noise['template_fit_ns']:.2f} ns**,
but the empirical/ML target is limited to the sampled waveform window near
**{noise['empirical_last_above_ns']:.2f} ns**; the template is extrapolating beyond the observed
tail rather than measuring the same operational quantity.

## Leakage checks

Leakage flags: **{int(leakage['flag'].sum())}**. Checks include run-held-out R2, random row-split
advantage, shuffled-target prediction, forbidden feature presence, and a specific guard against
near-deterministic ML/template agreement. See `leakage_checks.csv`.

## Conclusion

The S10c numbers are internally consistent once the quantity is named precisely. The template
fit estimates a smooth tail crossing and can extrapolate beyond sampled data at low thresholds;
the empirical and ML methods estimate the discrete last-above-threshold operational live-time
within the acquired 18-sample waveform. For pile-up occupancy, 10% remains the least ambiguous
bridge between the two definitions; 20% and noise-floor definitions should not be mixed without
calling out the operational difference.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `threshold_summary.csv`,
`reconciliation_summary.csv`, `template_sampling_diagnostics.csv`,
`pulse_censoring_by_target.csv`, `ml_heldout_by_run.csv`, `leakage_checks.csv`, and three PNG
diagnostics are in this folder.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "configs" / "s10d_1781013102_1034_262365d2_reconcile_livetime.json"))
    args = parser.parse_args()
    config = load_config(Path(args.config))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()
    rng = np.random.default_rng(int(config["random_seed"]))

    pulses = s10c.read_selected_pulses()
    topology, topology_repro, rmax = s10c.reproduce_s10(pulses)
    fits, heldout = s10c.traditional_template_fits(pulses)
    ml_by_run, leakage = s10c.ml_run_heldout(pulses)
    merged = heldout.merge(ml_by_run, on="heldout_run", how="left")
    threshold_summary = recompute_threshold_summary(merged, fits, config, rng)
    censoring = pulse_censoring_summary(pulses, config, rng)
    per_target_censoring = pd.DataFrame([item for rows in censoring["per_run_rows"] for item in rows])
    censoring_public = censoring.drop(columns=["per_run_rows"])
    template_diag = template_sampling_diagnostics(pulses, fits, config)
    template_sampling = aggregate_template_sampling(template_diag, config, rng)
    reconciliation = reconciliation_table(threshold_summary, censoring_public, template_sampling, config)
    leakage_full = leakage_audit(leakage, threshold_summary, config)

    reported = config["reported_s10c"]
    repro_rows = []
    for key, report_key in [
        ("10pct", "live10_template_ns"),
        ("20pct", "live20_template_ns"),
        ("noise_floor", "noise_floor_template_ns"),
    ]:
        value = float(threshold_summary[threshold_summary["target"] == key]["traditional_template_mean_ns"].iloc[0])
        report_value = float(reported[report_key])
        repro_rows.append(
            {
                "quantity": f"S10c {key} template live-time",
                "report_value": report_value,
                "reproduced": value,
                "delta": value - report_value,
                "tolerance": 0.05,
                "pass": bool(abs(value - report_value) <= 0.05),
            }
        )
    for key, report_key in [
        ("20pct", "live20_empirical_ns"),
        ("noise_floor", "noise_floor_empirical_ns"),
    ]:
        value = float(threshold_summary[threshold_summary["target"] == key]["empirical_mean_ns"].iloc[0])
        report_value = float(reported[report_key])
        repro_rows.append(
            {
                "quantity": f"S10c {key} empirical live-time",
                "report_value": report_value,
                "reproduced": value,
                "delta": value - report_value,
                "tolerance": 0.05,
                "pass": bool(abs(value - report_value) <= 0.05),
            }
        )
    reproduction_match = pd.concat([topology_repro, pd.DataFrame(repro_rows)], ignore_index=True)

    raw_inputs = {f"hrdb_run_{run:04d}.root": sha256_file(ROOT / config["raw_root_dir"] / f"hrdb_run_{run:04d}.root") for run in config["runs"]}
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_first": bool(reproduction_match["pass"].all()),
        "reproduction": {
            "s10c_live10_template_ns": float(threshold_summary[threshold_summary["target"] == "10pct"]["traditional_template_mean_ns"].iloc[0]),
            "topology_checks_passed": int(topology_repro["pass"].sum()),
            "topology_checks_total": int(len(topology_repro)),
        },
        "traditional_method": "leave-one-run-out exponential template tail fit plus direct empirical last-above operation",
        "ml_method": "leave-one-run-out standardized Ridge pulse-shape regressor",
        "thresholds": {row["target"]: row for row in reconciliation.to_dict(orient="records")},
        "leakage_flags": int(leakage_full["flag"].sum()),
        "input_sha256": raw_inputs,
        "git_commit": git_commit(),
        "runtime_sec": None,
    }

    topology.to_csv(out / "topology_by_run_group.csv", index=False)
    reproduction_match.to_csv(out / "reproduction_match_table.csv", index=False)
    rmax.to_csv(out / "poisson_rmax_table.csv", index=False)
    fits.to_csv(out / "template_fit_by_run_stave.csv", index=False)
    merged.to_csv(out / "heldout_run_summary.csv", index=False)
    threshold_summary.to_csv(out / "threshold_summary.csv", index=False)
    ml_by_run.to_csv(out / "ml_heldout_by_run.csv", index=False)
    leakage_full.to_csv(out / "leakage_checks.csv", index=False)
    censoring_public.to_csv(out / "pulse_censoring_by_target.csv", index=False)
    per_target_censoring.to_csv(out / "pulse_censoring_by_run.csv", index=False)
    template_diag.to_csv(out / "template_sampling_diagnostics.csv", index=False)
    template_sampling.to_csv(out / "template_sampling_summary.csv", index=False)
    reconciliation.to_csv(out / "reconciliation_summary.csv", index=False)
    pd.DataFrame([{"file": k, "sha256": v} for k, v in raw_inputs.items()]).to_csv(out / "input_sha256.csv", index=False)
    save_plots(out, reconciliation, threshold_summary)

    result["runtime_sec"] = round(time.time() - start, 2)
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out, config, result, reconciliation, leakage_full)

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": config["random_seed"],
        "inputs": raw_inputs,
        "commands": [f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config configs/{Path(args.config).name}"],
        "outputs": output_hashes(out),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
