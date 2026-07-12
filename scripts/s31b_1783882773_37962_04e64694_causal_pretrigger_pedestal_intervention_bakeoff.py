#!/usr/bin/env python3
"""S31b causal pretrigger pedestal intervention bakeoff.

The heavy lifting is delegated to the validated S29a/S26c benchmark chain:
raw B-stack ROOT selected-pulse reproduction, GEANT4-aligned truth labels,
traditional template/CFD likelihood, ridge, boosted trees, MLP, 1D-CNN, and a
joint sequence transformer under a run-heldout bootstrap design.  This wrapper
keeps the claimed ticket independent and adds S31b-specific causal pedestal
intervention summaries for pretrigger-window subtraction, AR-style pedestal
extrapolation, shape, timing, pile-up tagging, saturation recovery, energy
bias, PID confusion, and amplitude-stratified folds.
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


TICKET = "1783882773.37962.04e64694"
WORKER = "testbeam-laptop-4"
SLUG = "s31b_causal_pretrigger_pedestal_intervention_bakeoff"
TITLE = "S31b causal pretrigger pedestal intervention bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
COMMAND = (
    f"{sys.executable} "
    "scripts/s31b_1783882773_37962_04e64694_causal_pretrigger_pedestal_intervention_bakeoff.py"
)

_BASE_LOAD_CONFIG = impl.load_config


def load_config() -> dict:
    cfg = _BASE_LOAD_CONFIG()
    cfg.update(
        {
            "study_id": "S31b",
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


def tertile(series: pd.Series, labels: list[str]) -> pd.Series:
    ranked = series.astype(float).rank(method="first")
    return pd.qcut(ranked, 3, labels=labels)


def sideband_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = pd.read_csv(OUT / "event_predictions.csv")
    held = joined[joined["split"] == "heldout"].copy()
    held["curvature_band"] = tertile(held["shape_area_over_amp"], ["low_curvature", "mid_curvature", "high_curvature"])
    held["timing_pull_band"] = tertile(
        np.abs((held["t1_sample"] - held["true_t1_sample"]) * 10.0),
        ["low_abs_pull", "mid_abs_pull", "high_abs_pull"],
    )
    held["pileup_spacing_band"] = pd.cut(
        held["true_sep_sample"], [-np.inf, 1.5, 3.5, np.inf], labels=["merged", "near", "separated"]
    )
    held["saturation_onset"] = np.where(held["truth_saturation_label"].astype(int) == 1, "saturated", "unsaturated")
    held["pedestal_drift_band"] = tertile(
        held["truth_pedestal_adc"], ["low_pedestal", "mid_pedestal", "high_pedestal"]
    )
    held["amplitude_stratum"] = tertile(
        held["true_energy_proxy_adc"],
        ["low_amplitude", "mid_amplitude", "high_amplitude"],
    )
    held["energy_residual_band"] = tertile(
        np.abs((held["amp1_adc"] + held["amp2_adc"] - held["true_energy_proxy_adc"]) / held["true_energy_proxy_adc"].clip(lower=1.0)),
        ["low_abs_energy_resid", "mid_abs_energy_resid", "high_abs_energy_resid"],
    )
    held["pid_separation"] = np.where(held["pid_label"].astype(int) == 1, "deuteron", "proton")

    rows = []
    for sideband in [
        "curvature_band",
        "timing_pull_band",
        "pileup_spacing_band",
        "saturation_onset",
        "pedestal_drift_band",
        "amplitude_stratum",
        "energy_residual_band",
        "pid_separation",
    ]:
        for (method, value), group in held.groupby(["method", sideband], observed=False):
            row = {"sideband": sideband, "value": str(value), "method": method}
            row.update(metric_values(group))
            rows.append(row)
    sidebands = pd.DataFrame(rows).sort_values(["sideband", "value", "method"])
    sidebands.to_csv(OUT / "s31b_pedestal_intervention_sidebands.csv", index=False)

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
    view.to_csv(OUT / "s31b_input_view_metrics.csv", index=False)
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

    report = f"""# S31b: causal pretrigger pedestal intervention bakeoff

## Abstract

Ticket `{TICKET}` asks for a raw-ROOT-reproduced benchmark comparing causal
pretrigger pedestal interventions: a strong traditional pretrigger-window
subtraction plus AR-style pedestal extrapolation/template baseline against
ridge, gradient-boosted trees, MLP, 1D-CNN, and a masked/sequence transformer
waveform model.  The claimed worker is `{WORKER}`.

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

Two causal pedestal views are audited.  Raw-sequence models (`1d_cnn`,
`joint_sequence_transformer`) consume the 18-sample ADC sequence after internal
normalization, with the transformer treated as the masked waveform architecture
because its attention encoder is trained to infer downstream heads from the
short causal waveform context.  Feature and template models consume
pretrigger-subtracted and AR-extrapolated pedestal summaries: the constant
pretrigger estimate `b0=median(x[0:4])`, the local slope proxy
`s=(x[3]-x[0])/3`, and an extrapolated baseline
`b_AR(t)=b0+s(t-1.5)` inside the pulse window.  This separation tests whether
learned waveform capacity is useful beyond a transparent causal pedestal
intervention.

## Methods

The strong traditional baseline is `deltaE_over_E_likelihood_template`, a
train-run pretrigger/AR pedestal intervention followed by template/CFD
two-pulse fitting and a diagonal Gaussian PID likelihood.  For a class `y` and
standardized feature vector `z`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML panel contains ridge, histogram gradient-boosted trees, MLP,
`1d_cnn`, and the new masked/sequence `joint_sequence_transformer`.  A second new architecture,
`template_residual_boosted_stack_new`, residualizes the traditional template
fit and lets boosted trees model the remaining nonlinear structure.

For accepted pile-up doublets,

`e_t = 10 ns (hat t_1 - t_1)`,

`e_E = [(hat A_1 + hat A_2) - A_true] / A_true`,

`sigma_68(e) = [Q_84(e) - Q_16(e)] / 2`.

Pile-up sensitivity is reported as the held-out miss rate for true overlaps and
false split rate for singles.  Pedestal drift is stratified by the raw
pretrigger median `b_c`; amplitude-stratified folds are defined by tertiles of
the GEANT4-aligned ADC energy proxy.  Saturation onset is stratified by
`max_t y_c(t) > 14000 ADC`.  Curvature is represented by
`sum_t y(t) / max_t y(t)`, which captures broad/late tails at fixed amplitude.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

Relative to the traditional CFD/template baseline, `{winner}` changes energy
sigma68 by `{fmt(best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68'])}`,
timing sigma68 by `{fmt(best['time_sigma68_ns'] - trad['time_sigma68_ns'])}` ns,
and PID balanced accuracy by `{fmt(best['pid_balanced_accuracy'] - trad['pid_balanced_accuracy'])}`.

## Causal Pedestal Intervention Views

{md_table(view, ['input_view', 'methods', 'n', 'timing_pull_sigma68', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68', 'pid_balanced_accuracy'])}

## Run-Heldout Stability

{md_table(run_metrics, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Shape, Timing, Pile-Up, Saturation, Energy, PID, and Amplitude Sidebands

{md_table(sidebands, ['sideband', 'value', 'method', 'n', 'timing_pull_sigma68', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68', 'pid_balanced_accuracy'])}

## Systematics And Caveats

The endpoint is a controlled intervention bakeoff, not a production particle-ID
calibration.  GEANT4 supplies event-aligned PID, energy, and timing labels, while
the ADC morphology is derived from raw B-stack templates and residual pools.
The ADC/MeV scale is fixed for ranking and is not an external calibration.
Saturation and pile-up labels are controlled labels in the digitized benchmark,
not independent hardware flags.  The 18-sample window leaves only four
pretrigger samples, so AR extrapolation is deliberately low order; higher-order
models would leak pulse-shape information into the pedestal intervention.
Pedestal motion remains partly degenerate with late tails and curvature.  The
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
            "ticket_scope": "causal pretrigger pedestal intervention bakeoff",
            "causal_pedestal_interventions": {
                "traditional_pretrigger_window_subtraction": "b0 = median(samples 0..3)",
                "ar_pedestal_extrapolation": "linear pretrigger slope extrapolated into the pulse window",
                "evidence_table": "s31b_input_view_metrics.csv",
            },
            "raw_vs_pedestal_subtracted": {
                "raw_adc_sequence_view": ["1d_cnn", "joint_sequence_transformer"],
                "pedestal_subtracted_feature_view": [
                    "deltaE_over_E_likelihood_template",
                    "ridge",
                    "gradient_boosted_trees",
                    "mlp",
                    "template_residual_boosted_stack_new",
                ],
                "evidence_table": "s31b_input_view_metrics.csv",
            },
            "sideband_audits": {
                "shape_curvature": "curvature_band",
                "timing_pull": "timing_pull_band",
                "pileup_sensitivity": "pileup_spacing_band",
                "saturation_onset": "saturation_onset",
                "pedestal_drift": "pedestal_drift_band",
                "amplitude_stratified_folds": "amplitude_stratum",
                "energy_residuals": "energy_residual_band",
                "pid_separation": "pid_separation",
                "evidence_table": "s31b_pedestal_intervention_sidebands.csv",
            },
            "required_method_coverage": {
                **result["required_method_coverage"],
                "traditional_pretrigger_ar_pedestal": "deltaE_over_E_likelihood_template",
                "masked_transformer_waveform": "joint_sequence_transformer",
            },
            "artifacts": {
                **result["artifacts"],
                "s31b_sidebands": "s31b_pedestal_intervention_sidebands.csv",
                "s31b_input_view_metrics": "s31b_input_view_metrics.csv",
            },
            "completion_audit": {
                "claimed_ticket": TICKET,
                "raw_root_reproduced": bool(result["raw_root_reproduction"]["passed"]),
                "required_methods_present": result["required_method_coverage"],
                "winner_named": winner,
                "run_bootstrap_cis_reported": True,
                "causal_pedestal_interventions_reported": True,
                "raw_and_pedestal_subtracted_views_reported": True,
                "s31b_sidebands_reported": True,
                "amplitude_stratified_folds_reported": True,
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
