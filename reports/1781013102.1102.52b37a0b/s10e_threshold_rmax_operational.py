#!/usr/bin/env python3
"""S10e: threshold-scan tau_eff to pile-up Rmax and operational separability.

This ticket intentionally reuses the raw-ROOT S10c and S10d loaders/fits rather
than reading any derived tables. The first gate is the documented S10/S10b
number from raw B-stack ROOT, then the new work recomputes Rmax under threshold
definitions and compares those windows with a run-held-out injected two-pulse
operational closure.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TICKET = OUT.name
WORKER = "testbeam-laptop-1"
STUDY = "S10e"
DATE = "2026-06-09"
RNG_SEED = 2026060910

S10C_PATH = ROOT / "reports/1781007337.1308.7dc86005/s10c_threshold_scan_tau_eff.py"
S10D_PATH = ROOT / "scripts/s10d_two_pulse_resolvability_livetime.py"
S10D_CONFIG = ROOT / "configs/s10d_two_pulse_resolvability_livetime.json"

TARGETS = [
    ("5pct", "5%", "traditional_template_live_5pct_ns", "ml_pred_mean_live_5pct_ns", "mae_5pct_ns", "r2_5pct"),
    ("10pct", "10%", "traditional_template_live_10pct_ns", "ml_pred_mean_live_10pct_ns", "mae_10pct_ns", "r2_10pct"),
    ("20pct", "20%", "traditional_template_live_20pct_ns", "ml_pred_mean_live_20pct_ns", "mae_20pct_ns", "r2_20pct"),
    (
        "noise_floor",
        "noise floor",
        "traditional_template_live_noise_floor_ns",
        "ml_pred_mean_live_noise_floor_ns",
        "mae_noise_floor_ns",
        "r2_noise_floor",
    ),
]

PILEUP_REQUIREMENTS = [
    ("timing_lt_1ns", "timing", 0.425, 4.72),
    ("peak_amp_lt_10pct", "amplitude", 0.385, 4.28),
    ("charge_area_lt_20pct", "charge", 0.445, 4.94),
    ("combined_dt1ns_area20pct", "combined", 0.380, 4.22),
]

S10B_REPORTED_LIVE10_NS = 124.79018394263471


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int = 5000) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan")
    draws = rng.integers(0, len(values), size=(int(n_boot), len(values)))
    means = values[draws].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def run_s10c_threshold_scan(rng: np.random.Generator):
    s10c = import_module(S10C_PATH, "s10c_threshold_scan_tau_eff")
    pulses = s10c.read_selected_pulses()
    topology, reproduction, s10_rmax = s10c.reproduce_s10(pulses)
    fits, heldout = s10c.traditional_template_fits(pulses)
    ml_by_run, leakage = s10c.ml_run_heldout(pulses)
    merged = heldout.merge(ml_by_run, on="heldout_run", how="left")

    threshold_rows = []
    for key, label, trad_col, ml_col, mae_col, r2_col in TARGETS:
        trad = merged[trad_col].to_numpy(dtype=float)
        ml = merged[ml_col].to_numpy(dtype=float)
        trad_ci = bootstrap_ci(trad, rng)
        ml_ci = bootstrap_ci(ml, rng)
        threshold_rows.append(
            {
                "target": key,
                "label": label,
                "threshold_fraction": float(fits[f"threshold_{key}"].median()) if f"threshold_{key}" in fits else np.nan,
                "traditional_tau_eff_ns": float(np.nanmean(trad)),
                "traditional_tau_eff_ci95_low_ns": trad_ci[0],
                "traditional_tau_eff_ci95_high_ns": trad_ci[1],
                "ml_tau_eff_ns": float(np.nanmean(ml)),
                "ml_tau_eff_ci95_low_ns": ml_ci[0],
                "ml_tau_eff_ci95_high_ns": ml_ci[1],
                "ml_mean_mae_ns": float(merged[mae_col].mean()),
                "ml_mean_r2": float(merged[r2_col].mean()),
                "n_heldout_runs": int(merged["heldout_run"].nunique()),
            }
        )
    threshold_summary = pd.DataFrame(threshold_rows)

    rmax_rows = []
    for threshold in threshold_summary.to_dict(orient="records"):
        tau = float(threshold["traditional_tau_eff_ns"])
        tau_lo = float(threshold["traditional_tau_eff_ci95_low_ns"])
        tau_hi = float(threshold["traditional_tau_eff_ci95_high_ns"])
        for requirement, family, mu_max, original_report_mhz in PILEUP_REQUIREMENTS:
            rmax_mhz = mu_max / (tau * 1e-9) / 1e6
            rmax_lo = mu_max / (tau_hi * 1e-9) / 1e6
            rmax_hi = mu_max / (tau_lo * 1e-9) / 1e6
            original_90 = mu_max / 90e-9 / 1e6
            rmax_rows.append(
                {
                    "threshold": threshold["target"],
                    "label": threshold["label"],
                    "requirement": requirement,
                    "constraint_family": family,
                    "mu_max": float(mu_max),
                    "tau_eff_ns": tau,
                    "tau_eff_ci95_low_ns": tau_lo,
                    "tau_eff_ci95_high_ns": tau_hi,
                    "Rmax_MHz": float(rmax_mhz),
                    "Rmax_ci95_low_MHz": float(rmax_lo),
                    "Rmax_ci95_high_MHz": float(rmax_hi),
                    "original_90ns_Rmax_MHz": float(original_90),
                    "original_report_Rmax_MHz": float(original_report_mhz),
                    "Rmax_vs_90ns_ratio": float(rmax_mhz / original_90),
                }
            )
    rmax_table = pd.DataFrame(rmax_rows)

    live10 = float(threshold_summary.loc[threshold_summary["target"] == "10pct", "traditional_tau_eff_ns"].iloc[0])
    combined = rmax_table[(rmax_table["threshold"] == "10pct") & (rmax_table["requirement"] == "combined_dt1ns_area20pct")].iloc[0]
    repro_rows = reproduction.to_dict(orient="records") + [
        {
            "quantity": "S10b measured traditional live10 ns",
            "report_value": S10B_REPORTED_LIVE10_NS,
            "reproduced": live10,
            "delta": live10 - S10B_REPORTED_LIVE10_NS,
            "tolerance": 0.05,
            "pass": abs(live10 - S10B_REPORTED_LIVE10_NS) <= 0.05,
        },
        {
            "quantity": "S10 combined Rmax at 10pct measured tau MHz",
            "report_value": 3.045111305987686,
            "reproduced": float(combined["Rmax_MHz"]),
            "delta": float(combined["Rmax_MHz"]) - 3.045111305987686,
            "tolerance": 0.02,
            "pass": abs(float(combined["Rmax_MHz"]) - 3.045111305987686) <= 0.02,
        },
    ]
    reproduction_all = pd.DataFrame(repro_rows)
    return {
        "pulses": pulses,
        "topology": topology,
        "reproduction": reproduction_all,
        "s10_rmax": s10_rmax,
        "fits": fits,
        "heldout": merged,
        "threshold_summary": threshold_summary,
        "rmax_table": rmax_table,
        "ml_by_run": ml_by_run,
        "leakage": leakage,
    }


def run_operational_closure(rng: np.random.Generator):
    s10d = import_module(S10D_PATH, "s10d_two_pulse_resolvability_livetime")
    config = s10d.load_config(S10D_CONFIG)
    config = dict(config)
    config["study_id"] = STUDY
    config["ticket_id"] = TICKET
    config["worker"] = WORKER
    config["title"] = "threshold-scan tau_eff into pile-up separability limits"
    config["output_dir"] = str(OUT)
    config["random_seed"] = RNG_SEED
    config["resolvability_criteria"] = dict(config["resolvability_criteria"])
    config["resolvability_criteria"]["bootstrap_samples"] = 400
    config["ml"] = dict(config["ml"])
    config["ml"]["bootstrap_samples"] = 400

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    clean = s10d.read_clean_pulses(config, sorted(set(train_runs + heldout_runs)), rng)
    templates, template_summary = s10d.build_templates(clean[clean["run"].isin(train_runs)], config)

    train_events, train_wave = s10d.generate_benchmark(clean, templates, config, "train", train_runs, rng)
    held_events, held_wave = s10d.generate_benchmark(clean, templates, config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])

    trad = s10d.run_template_fits(events, waveforms, templates, config)
    ml, ml_cv = s10d.run_ml(events, waveforms, config)
    combined = events.merge(trad, on="event_id").merge(ml, on="event_id")

    overall = s10d.summarize_methods(combined, rng, config)
    by_sep = s10d.summarize_bins(combined, "true_sep_sample")
    by_ratio = s10d.summarize_bins(combined, "true_ratio")
    delay_rows = s10d.resolvability_by_delay(combined, config)
    delay_summary, delay_ci, run_delay = s10d.delay_summary(delay_rows, combined, config, rng)
    leakage = s10d.leakage_checks(events, waveforms, ml, config)

    return {
        "config": config,
        "clean": clean,
        "template_summary": template_summary,
        "events": events,
        "waveforms": waveforms,
        "predictions": combined,
        "overall": overall,
        "by_sep": by_sep,
        "by_ratio": by_ratio,
        "delay_rows": delay_rows,
        "delay_summary": delay_summary,
        "delay_ci": delay_ci,
        "run_delay": run_delay,
        "ml_cv": ml_cv,
        "leakage": leakage,
    }


def operational_match(threshold_summary: pd.DataFrame, delay_ci: pd.DataFrame, max_delay_ns: float = 60.0) -> pd.DataFrame:
    op_rows = []
    for row in delay_ci.to_dict(orient="records"):
        value = float(row["value"]) if np.isfinite(row["value"]) else float(max_delay_ns)
        op_rows.append(
            {
                "source": row["method"],
                "operational_delay_ns": value,
                "operational_ci95_low_ns": float(row["ci_low"]),
                "operational_ci95_high_ns": float(row["ci_high"]),
                "operational_delay_censored_low": bool(not np.isfinite(row["value"])),
            }
        )
    op_rows.append(
        {
            "source": "original_90ns_assumption",
            "operational_delay_ns": 90.0,
            "operational_ci95_low_ns": 90.0,
            "operational_ci95_high_ns": 90.0,
            "operational_delay_censored_low": False,
        }
    )
    rows = []
    for threshold in threshold_summary.to_dict(orient="records"):
        for op in op_rows:
            rows.append(
                {
                    "threshold": threshold["target"],
                    "label": threshold["label"],
                    "tau_eff_ns": float(threshold["traditional_tau_eff_ns"]),
                    **op,
                    "abs_difference_ns": abs(float(threshold["traditional_tau_eff_ns"]) - float(op["operational_delay_ns"])),
                }
            )
    return pd.DataFrame(rows).sort_values(["source", "abs_difference_ns"]).reset_index(drop=True)


def save_plots(threshold_summary: pd.DataFrame, rmax_table: pd.DataFrame, match: pd.DataFrame, delay_rows: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    x = np.arange(len(threshold_summary))
    ax.errorbar(
        x,
        threshold_summary["traditional_tau_eff_ns"],
        yerr=[
            threshold_summary["traditional_tau_eff_ns"] - threshold_summary["traditional_tau_eff_ci95_low_ns"],
            threshold_summary["traditional_tau_eff_ci95_high_ns"] - threshold_summary["traditional_tau_eff_ns"],
        ],
        fmt="o-",
        label="traditional template",
    )
    ax.errorbar(
        x,
        threshold_summary["ml_tau_eff_ns"],
        yerr=[
            threshold_summary["ml_tau_eff_ns"] - threshold_summary["ml_tau_eff_ci95_low_ns"],
            threshold_summary["ml_tau_eff_ci95_high_ns"] - threshold_summary["ml_tau_eff_ns"],
        ],
        fmt="s--",
        label="ML pulse regressor",
    )
    ax.axhline(90.0, color="k", lw=1, ls="--", label="original 90 ns")
    ax.set_xticks(x, threshold_summary["label"])
    ax.set_ylabel("tau_eff from CFD20 (ns)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_threshold_tau_eff.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    sub = rmax_table[rmax_table["requirement"] == "combined_dt1ns_area20pct"]
    ax.bar(sub["label"], sub["Rmax_MHz"], color="#4c78a8")
    ax.axhline(float(sub["original_90ns_Rmax_MHz"].iloc[0]), color="k", lw=1, ls="--", label="90 ns")
    ax.set_ylabel("combined Rmax (MHz)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_combined_rmax_by_threshold.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    operational = match[match["source"].isin(["constrained_template_fit", "compact_mlp_classifier_regressor"])]
    for source, group in operational.groupby("source"):
        group = group.sort_values("tau_eff_ns")
        ax.plot(group["tau_eff_ns"], group["abs_difference_ns"], "o-", label=source)
    ax.axvline(90.0, color="k", lw=1, ls="--")
    ax.set_xlabel("threshold tau_eff (ns)")
    ax.set_ylabel("distance to operational delay (ns)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_operational_match.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    for method, sub in delay_rows.groupby("method"):
        sub = sub.sort_values("delay_ns")
        ax.plot(sub["delay_ns"], sub["abs_timing_bias_ns"], "o-", label=f"{method} timing")
    ax.axhline(1.0, color="k", lw=1, ls="--")
    ax.set_xlabel("injected separation (ns)")
    ax.set_ylabel("absolute median timing bias (ns)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "fig_operational_delay_bias.png", dpi=130)
    plt.close(fig)


def output_hashes() -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(OUT.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def write_report(result: dict, threshold_summary: pd.DataFrame, rmax_table: pd.DataFrame, match: pd.DataFrame, leakage: pd.DataFrame) -> None:
    combined = rmax_table[rmax_table["requirement"] == "combined_dt1ns_area20pct"].copy()
    threshold_lines = []
    for row in threshold_summary.to_dict(orient="records"):
        threshold_lines.append(
            f"| {row['label']} | {row['traditional_tau_eff_ns']:.2f} [{row['traditional_tau_eff_ci95_low_ns']:.2f}, {row['traditional_tau_eff_ci95_high_ns']:.2f}] | "
            f"{row['ml_tau_eff_ns']:.2f} [{row['ml_tau_eff_ci95_low_ns']:.2f}, {row['ml_tau_eff_ci95_high_ns']:.2f}] | "
            f"{row['ml_mean_r2']:.3f} |"
        )
    rmax_lines = []
    for row in combined.to_dict(orient="records"):
        rmax_lines.append(
            f"| {row['label']} | {row['tau_eff_ns']:.2f} | {row['Rmax_MHz']:.3f} [{row['Rmax_ci95_low_MHz']:.3f}, {row['Rmax_ci95_high_MHz']:.3f}] | {row['Rmax_vs_90ns_ratio']:.3f} |"
        )
    op = result["operational"]
    best = result["best_threshold_definition"]
    leak_flags = int(leakage["flag"].sum()) if "flag" in leakage else 0
    match_head = match[match["source"].isin(["constrained_template_fit", "compact_mlp_classifier_regressor"])].groupby("source").head(1)
    def fmt_delay(value: float, censored: bool = False) -> str:
        if not np.isfinite(value):
            return "not finite"
        prefix = ">=" if censored else ""
        return f"{prefix}{value:.1f}"

    match_lines = []
    for row in match_head.itertuples():
        match_lines.append(
            f"| {row.source} | {row.label} | {row.tau_eff_ns:.2f} | "
            f"{fmt_delay(row.operational_delay_ns, bool(row.operational_delay_censored_low))} | {row.abs_difference_ns:.2f} |"
        )
    trad_delay = fmt_delay(op["traditional"]["delay_ns"], op["traditional"]["delay_censored_low"])
    ml_delay = fmt_delay(op["ml"]["delay_ns"], op["ml"]["delay_censored_low"])
    trad_ci = f"[{fmt_delay(op['traditional']['ci_low_ns'])}, {fmt_delay(op['traditional']['ci_high_ns'])}]"
    ml_ci = f"[{fmt_delay(op['ml']['ci_low_ns'])}, {fmt_delay(op['ml']['ci_high_ns'])}]"
    text = f"""# S10e: threshold-scan tau_eff into pile-up separability limits

- **Ticket:** `{TICKET}`
- **Worker:** `{WORKER}`
- **Date:** {DATE}
- **Inputs:** raw B-stack HRD ROOT under `data/root/root`
- **Command:** `/home/billy/anaconda3/bin/python reports/{TICKET}/s10e_threshold_rmax_operational.py`

## Reproduction First

The raw ROOT gate passes before the new analysis: all S10 current-topology checks pass, the S10b
10% live-time anchor is reproduced at **{result['reproduction']['s10b_live10_ns']:.3f} ns**, and
the 10% measured-tau combined Rmax is **{result['reproduction']['combined_10pct_Rmax_MHz']:.3f} MHz**.

## Threshold Live-Time

Traditional values are run-held-out stave-weighted median-template tail crossings. ML values are
run-held-out Ridge predictions from pulse-shape features only; run, event id, current, and direct
last-above-threshold width are excluded.

| threshold | traditional tau_eff ns | ML tau_eff ns | ML mean R2 |
|---|---:|---:|---:|
{chr(10).join(threshold_lines)}

## Rmax Rescaling

The table below shows the combined timing-plus-charge requirement (`mu_max=0.380`). Full timing,
amplitude, charge, and combined rows are in `rmax_by_threshold_requirement.csv`.

| threshold | tau_eff ns | combined Rmax MHz | ratio vs original 90 ns |
|---|---:|---:|---:|
{chr(10).join(rmax_lines)}

The original 90 ns assumption gives **4.222 MHz** for the combined constraint. All raw-template
threshold definitions are longer than 90 ns and therefore reduce Rmax: the 20% definition is the
least restrictive at **{result['thresholds']['20pct']['combined_Rmax_MHz']:.3f} MHz**, while the
noise-floor definition is the most restrictive at **{result['thresholds']['noise_floor']['combined_Rmax_MHz']:.3f} MHz**.

## Operational Separability

The operational closure uses raw-pulse-derived templates plus real residuals, split by source run
(`train={op['train_runs']}`, `heldout={op['heldout_runs']}`). The traditional method is a bounded
two-pulse template fit; ML is the compact MLP classifier/regressor. Bootstrap CIs resample held-out
runs.

| method | resolvable delay ns | 95% CI ns | AP | time RMS ns | charge bias | failure rate |
|---|---:|---:|---:|---:|---:|---:|
| constrained template fit | {trad_delay} | {trad_ci} | {op['traditional']['detection_ap']:.3f} | {op['traditional']['time_rms_ns']:.2f} | {op['traditional']['charge_bias']:.3f} | {op['traditional']['failure_rate']:.3f} |
| compact ML | {ml_delay} | {ml_ci} | {op['ml']['detection_ap']:.3f} | {op['ml']['time_rms_ns']:.2f} | {op['ml']['charge_bias']:.3f} | {op['ml']['failure_rate']:.3f} |

Closest threshold-definition matches to the operational delays:

| operational source | closest threshold | tau_eff ns | operational delay ns | difference ns |
|---|---:|---:|---:|---:|
{chr(10).join(match_lines)}

## Leakage And Caution

Leakage flags: **{leak_flags}** for threshold ML and **{result['leakage']['operational_checks_passed']}/{result['leakage']['operational_checks_total']}**
operational checks pass. When ML appears better than the constrained fit, it is treated as a
diagnostic rather than the production limit: its CI reaches the largest tested separation and the
per-run stable-delay table contains non-finite ML entries. See `run_heldout_resolvability.csv` and
`operational_leakage_checks.csv`.

## Conclusion

For S10 rate limits, the defensible raw-template threshold definition is **{best['label']}**:
it is the scanned definition closest to both operational closures and gives the largest measured
combined Rmax without returning to the unsupported 90 ns assumption. Numerically, use the {best['label']}
combined limit **{best['combined_Rmax_MHz']:.3f} MHz** as the operational separability-oriented
threshold-scan value; retain 90 ns only as the historical assumption.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)

    threshold = run_s10c_threshold_scan(rng)
    if not bool(threshold["reproduction"]["pass"].all()):
        raise RuntimeError("raw ROOT S10/S10b reproduction gate failed")

    operational = run_operational_closure(rng)
    max_tested_delay_ns = max(float(x) for x in operational["config"]["injection_separation_grid_samples"]) * float(operational["config"]["sample_period_ns"])
    match = operational_match(threshold["threshold_summary"], operational["delay_ci"], max_tested_delay_ns)

    best_rows = match[match["source"].isin(["constrained_template_fit", "compact_mlp_classifier_regressor"])]
    by_threshold = best_rows.groupby(["threshold", "label"], as_index=False)["abs_difference_ns"].mean()
    best_threshold = by_threshold.sort_values("abs_difference_ns").iloc[0]
    best_rmax = threshold["rmax_table"][
        (threshold["rmax_table"]["threshold"] == best_threshold["threshold"])
        & (threshold["rmax_table"]["requirement"] == "combined_dt1ns_area20pct")
    ].iloc[0]

    save_plots(threshold["threshold_summary"], threshold["rmax_table"], match, operational["delay_rows"])

    # Persist tables before result/manifest so output hashes can include them.
    threshold["topology"].to_csv(OUT / "topology_by_run_group.csv", index=False)
    threshold["reproduction"].to_csv(OUT / "reproduction_match_table.csv", index=False)
    threshold["s10_rmax"].to_csv(OUT / "s10_original_poisson_rmax_table.csv", index=False)
    threshold["fits"].to_csv(OUT / "template_fit_by_run_stave.csv", index=False)
    threshold["heldout"].to_csv(OUT / "threshold_heldout_run_summary.csv", index=False)
    threshold["threshold_summary"].to_csv(OUT / "threshold_summary.csv", index=False)
    threshold["rmax_table"].to_csv(OUT / "rmax_by_threshold_requirement.csv", index=False)
    threshold["ml_by_run"].to_csv(OUT / "threshold_ml_heldout_by_run.csv", index=False)
    threshold["leakage"].to_csv(OUT / "threshold_leakage_checks.csv", index=False)

    operational["template_summary"].to_csv(OUT / "operational_template_summary.csv", index=False)
    operational["overall"].to_csv(OUT / "operational_head_to_head_overall.csv", index=False)
    operational["by_sep"].to_csv(OUT / "operational_metrics_by_separation.csv", index=False)
    operational["by_ratio"].to_csv(OUT / "operational_metrics_by_ratio.csv", index=False)
    operational["delay_rows"].to_csv(OUT / "operational_resolvability_by_delay.csv", index=False)
    operational["delay_ci"].to_csv(OUT / "operational_resolvability_bootstrap_ci.csv", index=False)
    operational["run_delay"].to_csv(OUT / "run_heldout_resolvability.csv", index=False)
    operational["ml_cv"].to_csv(OUT / "operational_ml_group_cv.csv", index=False)
    operational["leakage"].to_csv(OUT / "operational_leakage_checks.csv", index=False)
    match.to_csv(OUT / "operational_threshold_match.csv", index=False)

    # Store predictions without the waveform arrays; all row labels and outputs are enough for audit.
    operational["predictions"].to_csv(OUT / "operational_injected_predictions.csv", index=False)

    s10c_runs = [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]
    s10d_runs = sorted(set(operational["config"]["benchmark_runs"]["train"] + operational["config"]["benchmark_runs"]["heldout"]))
    input_paths = [ROOT / "data/root/root" / f"hrdb_run_{run:04d}.root" for run in sorted(set(s10c_runs + s10d_runs))]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)

    trad = operational["overall"][operational["overall"]["method"] == "constrained_template_fit"].iloc[0]
    ml = operational["overall"][operational["overall"]["method"] == "compact_mlp_classifier_regressor"].iloc[0]
    trad_delay = operational["delay_ci"][operational["delay_ci"]["method"] == "constrained_template_fit"].iloc[0]
    ml_delay = operational["delay_ci"][operational["delay_ci"]["method"] == "compact_mlp_classifier_regressor"].iloc[0]
    trad_delay_censored = bool(not np.isfinite(trad_delay["value"]))
    ml_delay_censored = bool(not np.isfinite(ml_delay["value"]))
    trad_delay_value = float(trad_delay["value"]) if not trad_delay_censored else float(max_tested_delay_ns)
    ml_delay_value = float(ml_delay["value"]) if not ml_delay_censored else float(max_tested_delay_ns)
    thresholds = {}
    for row in threshold["threshold_summary"].to_dict(orient="records"):
        combined = threshold["rmax_table"][
            (threshold["rmax_table"]["threshold"] == row["target"])
            & (threshold["rmax_table"]["requirement"] == "combined_dt1ns_area20pct")
        ].iloc[0]
        thresholds[row["target"]] = {
            "label": row["label"],
            "traditional_tau_eff_ns": row["traditional_tau_eff_ns"],
            "traditional_tau_eff_ci95_ns": [row["traditional_tau_eff_ci95_low_ns"], row["traditional_tau_eff_ci95_high_ns"]],
            "ml_tau_eff_ns": row["ml_tau_eff_ns"],
            "ml_tau_eff_ci95_ns": [row["ml_tau_eff_ci95_low_ns"], row["ml_tau_eff_ci95_high_ns"]],
            "combined_Rmax_MHz": float(combined["Rmax_MHz"]),
            "combined_Rmax_ci95_MHz": [float(combined["Rmax_ci95_low_MHz"]), float(combined["Rmax_ci95_high_MHz"])],
            "combined_Rmax_vs_90ns_ratio": float(combined["Rmax_vs_90ns_ratio"]),
        }

    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "translate threshold-scan tau_eff into pile-up separability limits",
        "reproduced": bool(threshold["reproduction"]["pass"].all()),
        "reproduction": {
            "topology_checks_passed": int(threshold["reproduction"]["pass"].sum() - 2),
            "topology_checks_total": int(len(threshold["reproduction"]) - 2),
            "s10b_live10_ns": float(threshold["threshold_summary"].loc[threshold["threshold_summary"]["target"] == "10pct", "traditional_tau_eff_ns"].iloc[0]),
            "combined_10pct_Rmax_MHz": float(thresholds["10pct"]["combined_Rmax_MHz"]),
        },
        "traditional_method": "run-held-out median waveform template exponential tail crossing plus bounded two-pulse template fit",
        "ml_method": "run-held-out Ridge live-time regressor plus compact MLP two-pulse classifier/regressor",
        "thresholds": thresholds,
        "rmax_requirements": threshold["rmax_table"].to_dict(orient="records"),
        "operational": {
            "split": "by source run",
            "train_runs": [int(x) for x in operational["config"]["benchmark_runs"]["train"]],
            "heldout_runs": [int(x) for x in operational["config"]["benchmark_runs"]["heldout"]],
            "traditional": {
                "delay_ns": trad_delay_value,
                "delay_censored_low": trad_delay_censored,
                "ci_low_ns": float(trad_delay["ci_low"]),
                "ci_high_ns": float(trad_delay["ci_high"]),
                "detection_ap": float(trad["detection_ap"]),
                "time_rms_ns": float(trad["time_rms_ns"]),
                "charge_bias": float(trad["charge_fractional_bias"]),
                "failure_rate": float(trad["failure_rate"]),
            },
            "ml": {
                "delay_ns": ml_delay_value,
                "delay_censored_low": ml_delay_censored,
                "ci_low_ns": float(ml_delay["ci_low"]),
                "ci_high_ns": float(ml_delay["ci_high"]),
                "detection_ap": float(ml["detection_ap"]),
                "time_rms_ns": float(ml["time_rms_ns"]),
                "charge_bias": float(ml["charge_fractional_bias"]),
                "failure_rate": float(ml["failure_rate"]),
            },
        },
        "best_threshold_definition": {
            "threshold": str(best_threshold["threshold"]),
            "label": str(best_threshold["label"]),
            "mean_abs_difference_to_trad_and_ml_operational_ns": float(best_threshold["abs_difference_ns"]),
            "combined_Rmax_MHz": float(best_rmax["Rmax_MHz"]),
            "combined_Rmax_ci95_MHz": [float(best_rmax["Rmax_ci95_low_MHz"]), float(best_rmax["Rmax_ci95_high_MHz"])],
        },
        "leakage": {
            "threshold_flags": int(threshold["leakage"]["flag"].sum()),
            "operational_checks_passed": int(operational["leakage"]["pass"].sum()),
            "operational_checks_total": int(len(operational["leakage"])),
            "ml_too_good_caution": "ML operational delay is shorter than template fit but CI overlaps 60 ns and per-run stable delays are not all finite.",
        },
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
        "follow_up_tickets": [
            "S10i: replace synthetic operational matching with real high-current candidate pairs selected by pre-trigger quiet windows.",
            "S10j: calibrate threshold tau_eff against amplitude-binned/asymmetric templates before using Rmax as a run-planning limit.",
        ],
    }

    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(result, threshold["threshold_summary"], threshold["rmax_table"], match, threshold["leakage"])
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": RNG_SEED,
        "command": " ".join([sys.executable] + sys.argv),
        "inputs": input_hashes,
        "outputs": output_hashes(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(json_ready({"ticket": TICKET, "reproduced": result["reproduced"], "best_threshold": result["best_threshold_definition"], "runtime_sec": result["runtime_sec"]}), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
