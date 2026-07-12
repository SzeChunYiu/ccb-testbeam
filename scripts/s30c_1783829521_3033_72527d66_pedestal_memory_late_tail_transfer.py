#!/usr/bin/env python3
"""S30c pedestal-memory and late-tail pulse-shape transfer benchmark.

This ticket-specific wrapper reuses the validated raw-ROOT reproduction and
GEANT4-aligned multi-task benchmark used by the S29/S30 family, then adds
S30c-specific audits for pedestal memory, late-tail transfer, pile-up false
positives, saturation leakage, energy-scale shifts, and PID stability.
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


TICKET = "1783829521.3033.72527d66"
WORKER = "testbeam-laptop-4"
SLUG = "s30c_pedestal_memory_late_tail_pulse_shape_transfer"
TITLE = "S30c pedestal memory and late-tail pulse-shape transfer study"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
COMMAND = (
    f"{sys.executable} "
    "scripts/s30c_1783829521_3033_72527d66_pedestal_memory_late_tail_transfer.py"
)

_BASE_LOAD_CONFIG = impl.load_config


def load_config() -> dict:
    cfg = _BASE_LOAD_CONFIG()
    cfg.update(
        {
            "study_id": "S30c",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "output_dir": str(OUT),
            "random_seed": 2026071232,
            "max_clean_pulses_per_run_stave": 88,
            "injected_per_train_run": 48,
            "clean_per_train_run": 48,
            "injected_per_heldout_run": 68,
            "clean_per_heldout_run": 68,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 82, "cnn_channels": 12, "max_iter": 250})
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


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return np.nan
    return float((np.nanpercentile(values, 84) - np.nanpercentile(values, 16)) / 2.0)


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {
            "n": 0,
            "timing_pull_sigma68": np.nan,
            "late_tail_rate_abs_gt_15ns": np.nan,
            "pileup_miss_rate": np.nan,
            "false_split_rate": np.nan,
            "saturation_leakage_rate": np.nan,
            "energy_fractional_bias": np.nan,
            "energy_fractional_sigma68": np.nan,
            "pid_balanced_accuracy": np.nan,
        }
    overlap = frame["is_overlap"].astype(int).to_numpy()
    pred_overlap = (frame["score"].to_numpy(float) >= 0.5).astype(int)
    miss = float(np.mean(pred_overlap[overlap == 1] == 0)) if np.any(overlap == 1) else np.nan
    false = float(np.mean(pred_overlap[overlap == 0] == 1)) if np.any(overlap == 0) else np.nan
    sat = frame["truth_saturation_label"].astype(int).to_numpy()
    sat_leak = float(np.mean(pred_overlap[sat == 1] == 1)) if np.any(sat == 1) else np.nan

    pos = frame[frame["is_overlap"].astype(int) == 1]
    if len(pos):
        time_resid = (pos["t1_sample"].to_numpy(float) - pos["true_t1_sample"].to_numpy(float)) * 10.0
        timing_sigma = sigma68(time_resid)
        late_tail_rate = float(np.mean(np.abs(time_resid) > 15.0))
        true_e = np.maximum(pos["true_energy_proxy_adc"].to_numpy(float), 1.0)
        pred_e = pos["amp1_adc"].to_numpy(float) + pos["amp2_adc"].to_numpy(float)
        e_resid = (pred_e - true_e) / true_e
        energy_bias = float(np.nanmedian(e_resid))
        energy_sigma = sigma68(e_resid)
    else:
        timing_sigma = late_tail_rate = energy_bias = energy_sigma = np.nan

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
        "late_tail_rate_abs_gt_15ns": late_tail_rate,
        "pileup_miss_rate": miss,
        "false_split_rate": false,
        "saturation_leakage_rate": sat_leak,
        "energy_fractional_bias": energy_bias,
        "energy_fractional_sigma68": energy_sigma,
        "pid_balanced_accuracy": bacc,
    }


def add_bands(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["pedestal_memory_band"] = pd.qcut(
        out["truth_pedestal_adc"],
        3,
        labels=["low_pedestal_memory", "mid_pedestal_memory", "high_pedestal_memory"],
        duplicates="drop",
    )
    out["late_tail_band"] = pd.qcut(
        out["shape_area_over_amp"],
        3,
        labels=["compact_tail", "nominal_tail", "late_tail"],
        duplicates="drop",
    )
    out["run_epoch"] = np.where(out["source_run"].astype(int) <= 57, "sample_i_like", "sample_ii_heldout")
    out["pileup_spacing_band"] = pd.cut(
        out["true_sep_sample"], [-np.inf, 1.5, 3.5, np.inf], labels=["merged", "near", "separated"]
    )
    out["saturation_onset"] = np.where(out["truth_saturation_label"].astype(int) == 1, "saturated", "unsaturated")
    out["pid_truth"] = np.where(out["pid_label"].astype(int) == 1, "deuteron", "proton")
    out["memory_tail_cell"] = out["pedestal_memory_band"].astype(str) + "__" + out["late_tail_band"].astype(str)
    return out


def s30c_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    joined = pd.read_csv(OUT / "event_predictions.csv")
    held = add_bands(joined[joined["split"] == "heldout"].copy())
    all_split = add_bands(joined.copy())

    rows = []
    for sideband in [
        "pedestal_memory_band",
        "late_tail_band",
        "memory_tail_cell",
        "run_epoch",
        "pileup_spacing_band",
        "saturation_onset",
        "pid_truth",
    ]:
        for (method, value), group in held.groupby(["method", sideband], observed=False):
            row = {"sideband": sideband, "value": str(value), "method": method}
            row.update(metric_values(group))
            rows.append(row)
    sidebands = pd.DataFrame(rows).sort_values(["sideband", "value", "method"])
    sidebands.to_csv(OUT / "s30c_pedestal_tail_sidebands.csv", index=False)

    transfer_rows = []
    for (method, split, run), group in all_split.groupby(["method", "split", "source_run"], observed=False):
        ped = group["truth_pedestal_adc"].to_numpy(float)
        tail = group["shape_area_over_amp"].to_numpy(float)
        row = {
            "method": method,
            "split": split,
            "source_run": int(run),
            "median_pedestal_adc": float(np.nanmedian(ped)),
            "pedestal_iqr_adc": float(np.nanpercentile(ped, 75) - np.nanpercentile(ped, 25)),
            "median_area_over_peak": float(np.nanmedian(tail)),
            "late_tail_fraction_top_tertile": float(np.mean(group["late_tail_band"].astype(str) == "late_tail")),
        }
        row.update(metric_values(group))
        transfer_rows.append(row)
    transfer = pd.DataFrame(transfer_rows).sort_values(["method", "split", "source_run"])
    transfer.to_csv(OUT / "s30c_run_transfer_metrics.csv", index=False)

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
    views = pd.DataFrame(view_rows)
    views.to_csv(OUT / "s30c_input_view_metrics.csv", index=False)
    return sidebands, transfer, views


def rewrite_metadata(started: float) -> None:
    sidebands, transfer, views = s30c_tables()
    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    run_metrics = pd.read_csv(OUT / "run_heldout_metrics.csv")
    match = pd.read_csv(OUT / "reproduction_match_table.csv")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    winner = str(best["method"])

    report = f"""# S30c: pedestal memory and late-tail pulse-shape transfer study

## Abstract

Ticket `{TICKET}` asks for a raw-ROOT-reproduced benchmark comparing a strong
traditional baseline-window subtraction plus exponential/template tail fit with
ridge, gradient-boosted trees, MLP, 1D-CNN, and a new sequence architecture.  The
claimed worker is `{WORKER}`.

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

The split is by source run.  Train runs are
`{result['evaluation_design']['train_runs']}` and held-out runs are
`{result['evaluation_design']['heldout_runs']}`.  No run appears in both sets.
Templates, pedestal summaries, scalers, likelihood moments, neural normalizers,
and architecture weights are fit on training runs only.  Confidence intervals
are percentile intervals from `{result['evaluation_design']['bootstrap_replicates']}`
held-out run-block bootstrap resamples.

The target observables are designed around the ticket.  Pedestal memory is the
raw pretrigger median

`p_i = median_{{t=0,1,2,3}} x_i(t)`,

stratified into low/mid/high tertiles on held-out events.  Late-tail transfer is
measured by the area-over-peak statistic

`L_i = sum_t y_i(t) / max_t y_i(t)`,

also split into tertiles.  Timing tails use

`r_t = 10 ns (hat t_1 - t_1)`,

and the late-tail failure rate is `Pr(|r_t|>15 ns)`.  Energy-scale shift is the
median of

`r_E = [(hat A_1 + hat A_2) - A_GEANT4] / A_GEANT4`.

## Methods

The strong traditional baseline is `deltaE_over_E_likelihood_template`: a
baseline-window subtraction, train-run template fit, CFD timing estimate,
two-pulse exponential/template tail decomposition, and diagonal Gaussian PID
likelihood.  For standardized feature vector `z` and class `y`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML panel contains ridge, histogram gradient-boosted trees, MLP, `1d_cnn`,
and the new `joint_sequence_transformer`.  A physics-residual architecture,
`template_residual_boosted_stack_new`, is included because this ticket explicitly
tests whether learned residuals can repair pedestal-memory and late-tail failure
modes after the traditional fit.

For any residual `u`,

`sigma_68(u) = [Q_84(u) - Q_16(u)] / 2`.

Pile-up sensitivity is the held-out miss rate for true overlaps plus the false
split rate for singles.  Saturation leakage is the fraction of saturated events
classified as pile-up by the given method.  PID stability is balanced accuracy
within pedestal-memory, late-tail, saturation, and PID truth strata.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

Relative to the traditional baseline, `{winner}` changes energy sigma68 by
`{fmt(best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68'])}`,
timing sigma68 by `{fmt(best['time_sigma68_ns'] - trad['time_sigma68_ns'])}` ns,
and PID balanced accuracy by `{fmt(best['pid_balanced_accuracy'] - trad['pid_balanced_accuracy'])}`.

## Raw Versus Pedestal-Subtracted Views

{md_table(views, ['input_view', 'methods', 'n', 'timing_pull_sigma68', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'saturation_leakage_rate', 'energy_fractional_bias', 'energy_fractional_sigma68', 'pid_balanced_accuracy'])}

## Run-Heldout Stability

{md_table(run_metrics, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Pedestal-Memory And Late-Tail Transfer

{md_table(transfer, ['method', 'split', 'source_run', 'median_pedestal_adc', 'pedestal_iqr_adc', 'median_area_over_peak', 'late_tail_fraction_top_tertile', 'timing_pull_sigma68', 'late_tail_rate_abs_gt_15ns', 'saturation_leakage_rate', 'energy_fractional_bias', 'pid_balanced_accuracy'])}

## Sideband Systematics

{md_table(sidebands, ['sideband', 'value', 'method', 'n', 'timing_pull_sigma68', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'saturation_leakage_rate', 'energy_fractional_bias', 'energy_fractional_sigma68', 'pid_balanced_accuracy'])}

## Systematics And Caveats

The endpoint is an architecture and method bakeoff, not a final detector
calibration.  GEANT4 supplies event-aligned PID, energy, and timing labels, while
the ADC morphology is derived from raw B-stack templates and residual pools.
The ADC/MeV scale is fixed for ranking and is not an external calibration.
Pedestal memory is represented by the four-sample pretrigger median, so any
memory component outside the recorded 18-sample window is only indirectly
visible through tail broadening and timing residuals.  Saturation and pile-up
labels are controlled labels in the digitized benchmark, not independent
hardware flags.  The bootstrap intervals resample held-out runs and therefore
cover run-transfer uncertainty, not GEANT4 physics-list, detector material, or
absolute calibration uncertainty.

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
            "ticket_scope": "pedestal memory and late-tail pulse-shape transfer",
            "pedestal_memory_late_tail": {
                "pedestal_memory_definition": "per-event raw pretrigger median truth_pedestal_adc, tertile sidebands",
                "late_tail_definition": "pedestal-subtracted area_over_peak shape_area_over_amp, tertile sidebands",
                "late_tail_failure": "Pr(|10 ns*(t1_sample-true_t1_sample)| > 15 ns) on true overlaps",
                "energy_scale_shift": "median ((amp1_adc+amp2_adc)-true_energy_proxy_adc)/true_energy_proxy_adc",
                "evidence_tables": [
                    "s30c_pedestal_tail_sidebands.csv",
                    "s30c_run_transfer_metrics.csv",
                    "s30c_input_view_metrics.csv",
                ],
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
                "evidence_table": "s30c_input_view_metrics.csv",
            },
            "sideband_audits": {
                "pedestal_memory": "pedestal_memory_band",
                "late_tail_transfer": "late_tail_band",
                "pedestal_tail_interaction": "memory_tail_cell",
                "pileup_sensitivity": "pileup_spacing_band",
                "saturation_leakage": "saturation_onset",
                "energy_scale_shifts": "energy_fractional_bias",
                "pid_stability": "pid_truth and sideband balanced accuracy",
                "evidence_table": "s30c_pedestal_tail_sidebands.csv",
            },
            "artifacts": {
                **result["artifacts"],
                "s30c_sidebands": "s30c_pedestal_tail_sidebands.csv",
                "s30c_run_transfer": "s30c_run_transfer_metrics.csv",
                "s30c_input_view_metrics": "s30c_input_view_metrics.csv",
            },
            "completion_audit": {
                "claimed_ticket": TICKET,
                "raw_root_reproduced": bool(result["raw_root_reproduction"]["passed"]),
                "required_methods_present": result["required_method_coverage"],
                "winner_named": winner,
                "run_bootstrap_cis_reported": True,
                "pedestal_memory_reported": True,
                "late_tail_transfer_reported": True,
                "pileup_false_positives_reported": True,
                "saturation_leakage_reported": True,
                "energy_scale_shifts_reported": True,
                "pid_stability_reported": True,
                "novel_tickets_appended": [],
            },
        }
    )
    result["winner"]["name"] = winner
    result["winner"]["criterion"] = "minimum held-out composite GEANT4-truth PID/energy/timing score"
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
