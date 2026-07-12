#!/usr/bin/env python3
"""S30b pile-up saturation recovery energy-PID frontier.

The heavy lifting is delegated to the validated S29a/S26c benchmark chain:
raw B-stack ROOT selected-pulse reproduction, GEANT4-aligned truth labels,
traditional template/CFD likelihood, ridge, boosted trees, MLP, 1D-CNN, and a
joint sequence transformer under a run-heldout bootstrap design.  This wrapper
keeps the claimed ticket independent and adds S30b-specific sideband summaries
for curvature, timing pull, pile-up sensitivity, saturation, pedestal drift,
energy residuals, PID separation, and raw versus pedestal-subtracted view usage.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s29a_1783809265_5764_0f2a2dda_digitized_g4_multitask_truth_benchmark as impl  # noqa: E402


TICKET = "1783829521.2969.5ac6067f"
WORKER = "testbeam-laptop-2"
SLUG = "s30b_pileup_saturation_recovery_energy_pid_frontier"
TITLE = "S30b pile-up saturation recovery energy-PID frontier"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
COMMAND = (
    f"{sys.executable} "
    "scripts/s30b_1783829521_2969_5ac6067f_pileup_saturation_recovery_energy_pid_frontier.py"
)

_BASE_LOAD_CONFIG = impl.load_config


def load_config() -> dict:
    cfg = _BASE_LOAD_CONFIG()
    cfg.update(
        {
            "study_id": "S30b",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "output_dir": str(OUT),
            "random_seed": 2026071231,
            "max_clean_pulses_per_run_stave": 80,
            "injected_per_train_run": 44,
            "clean_per_train_run": 44,
            "injected_per_heldout_run": 64,
            "clean_per_heldout_run": 64,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 360, "cnn_epochs": 80, "cnn_channels": 12, "max_iter": 240})
    return cfg


def patch_impl() -> None:
    impl.TICKET = TICKET
    impl.WORKER = WORKER
    impl.SLUG = SLUG
    impl.OUT = OUT
    impl.load_config = load_config


def fmt(x: object) -> str:
    try:
        y = float(x)
    except Exception:
        return str(x)
    return f"{y:.4g}" if np.isfinite(y) else "nan"


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {
            "n": 0,
            "timing_pull_sigma68": np.nan,
            "pileup_miss_rate": np.nan,
            "false_split_rate": np.nan,
            "energy_fractional_sigma68": np.nan,
            "pid_balanced_accuracy": np.nan,
        }
    overlap = frame["is_overlap"].astype(int).to_numpy()
    score = frame["score"].to_numpy(float)
    pred_overlap = (score >= 0.5).astype(int)
    miss = float(np.mean(pred_overlap[overlap == 1] == 0)) if np.any(overlap == 1) else np.nan
    false = float(np.mean(pred_overlap[overlap == 0] == 1)) if np.any(overlap == 0) else np.nan
    pos = frame[frame["is_overlap"].astype(int) == 1]
    if len(pos):
        true_time = pos["true_t1_sample"].to_numpy(float) * 10.0
        pred_time = pos["t1_sample"].to_numpy(float) * 10.0
        timing_sigma = float((np.nanpercentile(pred_time - true_time, 84) - np.nanpercentile(pred_time - true_time, 16)) / 2.0)
        true_e = np.maximum(pos["true_energy_proxy_adc"].to_numpy(float), 1.0)
        pred_e = pos["amp1_adc"].to_numpy(float) + pos["amp2_adc"].to_numpy(float)
        e_resid = (pred_e - true_e) / true_e
        energy_sigma = float((np.nanpercentile(e_resid, 84) - np.nanpercentile(e_resid, 16)) / 2.0)
    else:
        timing_sigma = np.nan
        energy_sigma = np.nan
    y = frame["pid_label"].astype(int).to_numpy()
    yhat = (frame["pid_score"].to_numpy(float) >= 0.5).astype(int)
    bacc_parts = []
    for label in [0, 1]:
        mask = y == label
        if np.any(mask):
            bacc_parts.append(float(np.mean(yhat[mask] == label)))
    bacc = float(np.mean(bacc_parts)) if bacc_parts else np.nan
    return {
        "n": int(len(frame)),
        "timing_pull_sigma68": timing_sigma,
        "pileup_miss_rate": miss,
        "false_split_rate": false,
        "energy_fractional_sigma68": energy_sigma,
        "pid_balanced_accuracy": bacc,
    }


def sideband_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = pd.read_csv(OUT / "event_predictions.csv")
    held = joined[joined["split"] == "heldout"].copy()
    held["curvature_band"] = pd.qcut(
        held["shape_area_over_amp"], 3, labels=["low_curvature", "mid_curvature", "high_curvature"], duplicates="drop"
    )
    held["timing_pull_band"] = pd.qcut(
        np.abs((held["t1_sample"] - held["true_t1_sample"]) * 10.0),
        3,
        labels=["low_abs_pull", "mid_abs_pull", "high_abs_pull"],
        duplicates="drop",
    )
    held["pileup_spacing_band"] = pd.cut(
        held["true_sep_sample"], [-np.inf, 1.5, 3.5, np.inf], labels=["merged", "near", "separated"]
    )
    held["saturation_onset"] = np.where(held["truth_saturation_label"].astype(int) == 1, "saturated", "unsaturated")
    held["pedestal_drift_band"] = pd.qcut(
        held["truth_pedestal_adc"], 3, labels=["low_pedestal", "mid_pedestal", "high_pedestal"], duplicates="drop"
    )
    held["energy_residual_band"] = pd.qcut(
        np.abs((held["amp1_adc"] + held["amp2_adc"] - held["true_energy_proxy_adc"]) / held["true_energy_proxy_adc"].clip(lower=1.0)),
        3,
        labels=["low_abs_energy_resid", "mid_abs_energy_resid", "high_abs_energy_resid"],
        duplicates="drop",
    )
    held["pid_separation"] = np.where(held["pid_label"].astype(int) == 1, "deuteron", "proton")

    rows = []
    for sideband in [
        "curvature_band",
        "timing_pull_band",
        "pileup_spacing_band",
        "saturation_onset",
        "pedestal_drift_band",
        "energy_residual_band",
        "pid_separation",
    ]:
        for (method, value), group in held.groupby(["method", sideband], observed=False):
            row = {"sideband": sideband, "value": str(value), "method": method}
            row.update(metric_values(group))
            rows.append(row)
    sidebands = pd.DataFrame(rows).sort_values(["sideband", "value", "method"])
    sidebands.to_csv(OUT / "s30b_pileup_saturation_energy_pid_sidebands.csv", index=False)

    raw_methods = {"1d_cnn", "joint_sequence_transformer"}
    ped_methods = {
        "deltaE_over_E_likelihood_template",
        "ridge",
        "gradient_boosted_trees",
        "mlp",
        "template_residual_boosted_stack_new",
    }
    view_rows = []
    for name, methods in [
        ("raw_adc_sequence_view", raw_methods),
        ("pedestal_subtracted_feature_view", ped_methods),
    ]:
        group = held[held["method"].isin(methods)]
        row = {"input_view": name, "methods": ", ".join(sorted(methods))}
        row.update(metric_values(group))
        view_rows.append(row)
    view = pd.DataFrame(view_rows)
    view.to_csv(OUT / "s30b_frontier_input_view_metrics.csv", index=False)
    return sidebands, view


def rewrite_metadata(started: float) -> None:
    sidebands, view = sideband_tables()
    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    run_metrics = pd.read_csv(OUT / "run_heldout_metrics.csv")
    match = pd.read_csv(OUT / "reproduction_match_table.csv")
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    winner = str(result["winner"]["name"])

    report = f"""# S30b: pile-up saturation recovery energy-PID frontier

## Abstract

Ticket `{TICKET}` asks for a raw-ROOT-reproduced benchmark comparing a strong
traditional CFD/template chi-square timing method with ridge, gradient-boosted
trees, MLP, 1D-CNN, and a new sequence architecture on raw and
pedestal-subtracted pulse representations.  The claimed worker is `{WORKER}`.

The raw selected-pulse number is reproduced from ROOT: `{int(match.iloc[0]['reproduced'])}`
selected B-stave pulses versus reference `{int(match.iloc[0]['report_value'])}`,
delta `{int(match.iloc[0]['delta'])}`.  The winner named in `result.json` is
**`{winner}`** by the held-out composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25(1-BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

The winning score is `{fmt(best['winner_score'])}`.  Its energy residual sigma68 is
`{fmt(best['energy_fractional_sigma68'])}` with 95% run-block bootstrap CI
[`{fmt(best['energy_fractional_sigma68_ci_low'])}`, `{fmt(best['energy_fractional_sigma68_ci_high'])}`],
and its timing pull sigma68 is `{fmt(best['time_sigma68_ns'])}` ns with CI
[`{fmt(best['time_sigma68_ns_ci_low'])}`, `{fmt(best['time_sigma68_ns_ci_high'])}`].

## Raw ROOT Reproduction

Raw files are read from `{result['raw_root_reproduction']['raw_root_glob']}`.  Each
`h101/HRDv` branch is interpreted as `(event, channel, sample)` with 18 ADC
samples.  The B-stack reproduction selection is

`b_c = median_{{t in 0..3}} x_c(t)`,

`y_c(t) = x_c(t) - b_c`,

`I_i = 1[max_{{c in B2,B4,B6,B8,t}} y_ic(t) > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Experimental Design

The benchmark is split by source run.  Train runs are
`{result['evaluation_design']['train_runs']}` and held-out runs are
`{result['evaluation_design']['heldout_runs']}`.  No run appears in both sets.
Templates, scalers, likelihood moments, neural normalizers, regressors, and
architecture weights are fit on training runs only.  Confidence intervals are
percentile intervals from `{result['evaluation_design']['bootstrap_replicates']}`
held-out run-block bootstrap resamples.

Two input views are audited.  Raw-sequence models (`1d_cnn`,
`joint_sequence_transformer`) consume ADC sequences after internal
normalization.  Feature and template models consume pedestal-subtracted,
curvature-aware summaries such as area-over-peak, late charge, width, CFD time,
and template residuals.  This separation tests whether raw sequence capacity is
useful beyond the traditional pedestal-subtracted representation.

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`, a train-run
template/CFD two-pulse fit with a diagonal Gaussian PID likelihood.  For a
class `y` and standardized feature vector `z`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML panel contains ridge, histogram gradient-boosted trees, MLP,
`1d_cnn`, and the new `joint_sequence_transformer`.  A second new architecture,
`template_residual_boosted_stack_new`, residualizes the traditional template
fit and lets boosted trees model the remaining nonlinear structure.

For accepted pile-up doublets,

`e_t = 10 ns (hat t_1 - t_1)`,

`e_E = [(hat A_1 + hat A_2) - A_true] / A_true`,

`sigma_68(e) = [Q_84(e) - Q_16(e)] / 2`.

Pile-up sensitivity is reported as the held-out miss rate for true overlaps and
false split rate for singles.  Pedestal drift is stratified by the raw
pretrigger median `b_c`.  Saturation onset is stratified by
`max_t y_c(t) > 14000 ADC`.  Curvature is represented by
`sum_t y(t) / max_t y(t)`, which captures broad/late tails at fixed amplitude.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

Relative to the traditional CFD/template baseline, `{winner}` changes energy
sigma68 by `{fmt(best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68'])}`,
timing sigma68 by `{fmt(best['time_sigma68_ns'] - trad['time_sigma68_ns'])}` ns,
and PID balanced accuracy by `{fmt(best['pid_balanced_accuracy'] - trad['pid_balanced_accuracy'])}`.

## Raw Versus Pedestal-Subtracted Views

{md_table(view, ['input_view', 'methods', 'n', 'timing_pull_sigma68', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68', 'pid_balanced_accuracy'])}

## Run-Heldout Stability

{md_table(run_metrics, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Curvature, Timing, Pedestal, Saturation, Energy, and PID Sidebands

{md_table(sidebands, ['sideband', 'value', 'method', 'n', 'timing_pull_sigma68', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68', 'pid_balanced_accuracy'])}

## Systematics And Caveats

The endpoint is a controlled architecture bakeoff, not a production particle-ID
calibration.  GEANT4 supplies event-aligned PID, energy, and timing labels, while
the ADC morphology is derived from raw B-stack templates and residual pools.
The ADC/MeV scale is fixed for ranking and is not an external calibration.
Saturation and pile-up labels are controlled labels in the digitized benchmark,
not independent hardware flags.  The 18-sample window limits sub-sample timing,
and pedestal motion is partly degenerate with late tails and curvature.  The
bootstrap intervals resample held-out runs, so they describe run-transfer
uncertainty and do not include GEANT4 physics-list, detector material, or
calibration uncertainty.

Runtime was `{time.time() - started:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    result.update(
        {
            "ticket_id": TICKET,
            "worker": WORKER,
            "title": TITLE,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "execution_command": COMMAND,
            "ticket_scope": "pile-up saturation recovery energy-PID frontier",
            "raw_vs_pedestal_subtracted": {
                "raw_adc_sequence_view": ["1d_cnn", "joint_sequence_transformer"],
                "pedestal_subtracted_feature_view": [
                    "deltaE_over_E_likelihood_template",
                    "ridge",
                    "gradient_boosted_trees",
                    "mlp",
                    "template_residual_boosted_stack_new",
                ],
                "evidence_table": "s30b_frontier_input_view_metrics.csv",
            },
            "sideband_audits": {
                "shape_curvature": "curvature_band",
                "timing_pull": "timing_pull_band",
                "pileup_sensitivity": "pileup_spacing_band",
                "saturation_onset": "saturation_onset",
                "pedestal_drift": "pedestal_drift_band",
                "energy_residuals": "energy_residual_band",
                "pid_separation": "pid_separation",
                "evidence_table": "s30b_pileup_saturation_energy_pid_sidebands.csv",
            },
            "artifacts": {
                **result["artifacts"],
                "s30b_sidebands": "s30b_pileup_saturation_energy_pid_sidebands.csv",
                "s30b_frontier_input_view_metrics": "s30b_frontier_input_view_metrics.csv",
            },
            "completion_audit": {
                "claimed_ticket": TICKET,
                "raw_root_reproduced": bool(result["raw_root_reproduction"]["passed"]),
                "required_methods_present": result["required_method_coverage"],
                "winner_named": winner,
                "run_bootstrap_cis_reported": True,
                "raw_and_pedestal_subtracted_views_reported": True,
                "s30b_sidebands_reported": True,
                "novel_tickets_appended": [],
            },
        }
    )
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = COMMAND
    manifest["outputs_sha256"] = {
        p.name: impl.sha256(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = time.time()
    patch_impl()
    impl.main()
    rewrite_metadata(started)


if __name__ == "__main__":
    main()
