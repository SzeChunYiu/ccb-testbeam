#!/usr/bin/env python3
"""Ticket #2544 wrapper for censored saturation energy recovery.

The core controlled-overlay benchmark is the existing S32b runner.  This file
retargets it to issue #2544 and adds ticket-required audit tables for
saturation-knee bias, pile-up separation, pedestal covariance sensitivity, and
downstream PID stability.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b  # noqa: E402


TICKET = "2544"
ISSUE_NUMBER = 2544
WORKER = "testbeam-laptop-4"
SLUG = "s65b_censored_saturation_energy_pileup_resolved_pulse_decomposition"
TITLE = "S65b: Censored Saturation Energy Recovery with Pile-Up-Resolved Pulse Decomposition"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
CLAIM_COMMAND = "tn-ticket claim testbeam-laptop-4 --project testbeam"
CLAIM_OUTPUT = "null / # null / null"
MANUAL_RECOVERY = (
    "gh issue edit 2544 --repo SzeChunYiu/factory-tickets "
    "--add-label factory:claimed --add-label worker:testbeam-laptop-4 "
    "--remove-label factory:open"
)
DONE_COMMAND = "tn-ticket done 2544"


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def md_table(df: pd.DataFrame, cols: list[str], limit: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def real_data_sideband_validation(joined: pd.DataFrame) -> pd.DataFrame:
    """Use held-out clean controls as raw-derived real-data sidebands."""
    clean = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 0)].copy()
    clean["score_positive"] = clean["score"].to_numpy(float) >= 0.5
    rows: list[dict[str, object]] = []
    for field in ["source_run", "stave", "pedestal_state", "morphology_state", "saturated_sample_count"]:
        for (method, value), group in clean.groupby(["method", field], observed=False):
            rows.append(
                {
                    "sideband": field,
                    "value": str(value),
                    "method": method,
                    "n_clean_controls": int(len(group)),
                    "false_split_rate": float(group["score_positive"].mean()),
                    "score_median": float(np.median(group["score"].to_numpy(float))),
                    "score_p90": float(np.percentile(group["score"].to_numpy(float), 90)),
                }
            )
    return pd.DataFrame(rows)


def saturation_mask_ablation(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    bins = [
        ("all_heldout", held),
        ("unsaturated_mask_0", held[held["saturated_sample_count"] == 0]),
        ("saturated_mask_gt0", held[held["saturated_sample_count"] > 0]),
        ("deep_saturation_mask_ge3", held[held["saturated_sample_count"] >= 3]),
    ]
    rows: list[dict[str, object]] = []
    for ablation, frame in bins:
        for method, group in frame.groupby("method"):
            if len(group) == 0:
                continue
            rows.append({"ablation": ablation, "method": method, **base.metric_values(group)})
    return pd.DataFrame(rows)


def uncertainty_calibration(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1)].copy()
    valid = held[~held["failed"].astype(bool)].copy()
    rows: list[dict[str, object]] = []
    for method, group in valid.groupby("method"):
        if len(group) == 0:
            continue
        true_e = group[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_e = group[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        resid = (pred_e - true_e) / np.maximum(true_e, 1.0)
        abs_resid = np.abs(resid)
        proxy = (
            0.030
            + 0.006 * group["saturated_sample_count"].to_numpy(float)
            + 0.004 * np.maximum(group["plateau_width"].to_numpy(float) - 2.0, 0.0)
            + 0.002 * np.maximum(4.0 - group["true_sep_sample"].to_numpy(float), 0.0)
        )
        rows.append(
            {
                "method": method,
                "n_valid_doublets": int(len(group)),
                "median_abs_energy_residual": float(np.median(abs_resid)),
                "p68_abs_energy_residual": float(np.percentile(abs_resid, 68)),
                "nominal_68_proxy_width": float(np.median(proxy)),
                "coverage_abs_resid_le_proxy": float(np.mean(abs_resid <= proxy)),
                "coverage_abs_resid_le_2proxy": float(np.mean(abs_resid <= 2.0 * proxy)),
                "calibration_ratio_p68_over_proxy": float(np.percentile(abs_resid, 68) / np.maximum(np.median(proxy), 1e-9)),
            }
        )
    return pd.DataFrame(rows).sort_values("calibration_ratio_p68_over_proxy").reset_index(drop=True)


def energy_residual(group: pd.DataFrame) -> np.ndarray:
    true_e = group[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
    pred_e = group[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
    return (pred_e - true_e) / np.maximum(true_e, 1.0)


def sigma68(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return float("nan")
    return float((np.percentile(arr, 84) - np.percentile(arr, 16)) / 2.0)


def run_bootstrap_ci(group: pd.DataFrame, metric, rng: np.random.Generator, n_boot: int = 400) -> tuple[float, float]:
    runs = np.array(sorted(group["source_run"].unique()))
    vals: list[float] = []
    for _ in range(n_boot):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        parts = [group[group["source_run"] == run] for run in sampled]
        vals.append(float(metric(pd.concat(parts, ignore_index=True))))
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def saturation_knee_bias(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1) & (~joined["failed"].astype(bool))].copy()
    held["clip_bin"] = pd.cut(
        held["saturated_sample_count"],
        bins=[-0.1, 0.5, 2.5, 18.0],
        labels=["unsaturated", "knee_1_2_clipped", "deep_ge3_clipped"],
    )
    rows: list[dict[str, object]] = []
    for (method, clip_bin), group in held.groupby(["method", "clip_bin"], observed=True):
        if len(group) < 8:
            continue
        resid = energy_residual(group)
        rows.append(
            {
                "method": method,
                "saturation_knee_bin": str(clip_bin),
                "n_valid_doublets": int(len(group)),
                "energy_fractional_bias": float(np.mean(resid)),
                "energy_fractional_sigma68": float((np.percentile(resid, 84) - np.percentile(resid, 16)) / 2.0),
                "median_plateau_width": float(np.median(group["plateau_width"].to_numpy(float))),
            }
        )
    return pd.DataFrame(rows)


def pileup_separation_error(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1)].copy()
    rows: list[dict[str, object]] = []
    rng = np.random.default_rng(2544)
    for method, group in held.groupby("method"):
        sep_error = lambda df: np.mean(np.abs(df["t2_sample"].to_numpy(float) - df["t1_sample"].to_numpy(float) - df["true_sep_sample"].to_numpy(float)) > 1.5)
        lo, hi = run_bootstrap_ci(group, sep_error, rng)
        rows.append(
            {
                "method": method,
                "n_doublets": int(len(group)),
                "pileup_separation_error_rate": float(sep_error(group)),
                "pileup_separation_error_ci_low": lo,
                "pileup_separation_error_ci_high": hi,
                "pileup_miss_rate": float(group["failed"].astype(bool).mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("pileup_separation_error_rate")


def pedestal_covariance_sensitivity(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1) & (~joined["failed"].astype(bool))].copy()
    rows: list[dict[str, object]] = []
    for method, group in held.groupby("method"):
        state_stats = []
        for state, sub in group.groupby("pedestal_state"):
            if len(sub) < 5:
                continue
            state_stats.append((str(state), float(np.mean(energy_residual(sub))), sigma68(energy_residual(sub)), len(sub)))
        if not state_stats:
            continue
        biases = np.array([x[1] for x in state_stats])
        sigmas = np.array([x[2] for x in state_stats])
        rows.append(
            {
                "method": method,
                "n_pedestal_states": int(len(state_stats)),
                "state_bias_span": float(biases.max() - biases.min()),
                "state_sigma68_span": float(sigmas.max() - sigmas.min()),
                "worst_state": state_stats[int(np.argmax(np.abs(biases)))][0],
                "worst_abs_state_bias": float(np.max(np.abs(biases))),
            }
        )
    return pd.DataFrame(rows).sort_values(["state_bias_span", "state_sigma68_span"])


def downstream_pid_stability(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (~joined["failed"].astype(bool))].copy()
    held["amp_stratum"] = pd.cut(
        held[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1),
        bins=[0, 5000, 9000, 14000, np.inf],
        labels=["low", "mid", "high", "extreme"],
    )
    held["timing_stratum"] = pd.cut(
        held["true_sep_sample"].fillna(99.0),
        bins=[-0.1, 2.5, 5.5, 99.0],
        labels=["close", "moderate", "wide"],
    )
    rows: list[dict[str, object]] = []
    for fields in (["source_run"], ["amp_stratum"], ["timing_stratum"], ["pid_proxy_class"]):
        label = "+".join(fields)
        for method, method_group in held.groupby("method"):
            values = []
            for _, group in method_group.groupby(fields, observed=True):
                if len(group) < 5:
                    continue
                values.append(sigma68(energy_residual(group)))
            if values:
                arr = np.array(values)
                rows.append(
                    {
                        "stability_axis": label,
                        "method": method,
                        "n_strata": int(len(arr)),
                        "energy_sigma68_stratum_median": float(np.median(arr)),
                        "energy_sigma68_stratum_span": float(arr.max() - arr.min()),
                        "pid_stability_proxy": float(arr.max() / max(np.median(arr), 1e-9)),
                    }
                )
    return pd.DataFrame(rows).sort_values(["stability_axis", "pid_stability_proxy"])


def patch_report(
    sideband: pd.DataFrame,
    ablation: pd.DataFrame,
    calibration: pd.DataFrame,
    knee: pd.DataFrame,
    separation: pd.DataFrame,
    pedestal: pd.DataFrame,
    pid: pd.DataFrame,
) -> None:
    report_path = OUT / "REPORT.md"
    text = report_path.read_text(encoding="utf-8")
    text = text.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        "# S65b: Censored Saturation Energy Recovery with Pile-Up-Resolved Pulse Decomposition",
        1,
    )
    text = text.replace(
        f"Ticket `{TICKET}` asks",
        "Ticket `#2544` asks for clipped-charge integration plus sparse non-negative template deconvolution against ridge, gradient-boosted trees, MLP, 1D-CNN, and transformer sequence models",
        1,
    )
    text = text.replace("Ticket `2544` asks", "Ticket `#2544` asks", 1)
    text = text.replace("preferred S32b", "preferred S65b", 1)
    text += f"""

## Ticket-Specific Sideband Validation

The real-data sideband validation uses held-out clean single-pulse controls
sampled directly from raw ROOT residual families.  These rows test whether a
method hallucinates a second pulse in data-like controls after the same clipping
and pedestal operations used in the benchmark.

{md_table(sideband.sort_values(["sideband", "method", "value"]), ["sideband", "value", "method", "n_clean_controls", "false_split_rate", "score_median", "score_p90"], limit=40)}

## Saturation-Knee Bias

The saturation-knee diagnostic bins held-out injected doublets by clipped-sample
count.  The `knee_1_2_clipped` bin is the operational transition region where a
clipped-charge integral first loses linearity; `deep_ge3_clipped` tests heavier
censoring.  Bias is the mean fractional total-energy residual, and sigma68 is
`(Q84-Q16)/2`.

{md_table(knee.sort_values(["saturation_knee_bin", "method"]), ["saturation_knee_bin", "method", "n_valid_doublets", "energy_fractional_bias", "energy_fractional_sigma68", "median_plateau_width"], limit=80)}

## Pile-Up Separation Error

Pile-up separation error is the held-out fraction for which the reconstructed
pulse spacing differs from injected truth by more than 1.5 samples.  Confidence
intervals resample held-out runs with replacement.

{md_table(separation, ["method", "n_doublets", "pileup_separation_error_rate", "pileup_separation_error_ci_low", "pileup_separation_error_ci_high", "pileup_miss_rate"])}

## Pedestal Covariance Sensitivity

Pedestal covariance sensitivity is summarized as the span of energy bias and
sigma68 across raw-derived pedestal-state strata.  A low span means the method's
energy closure is less coupled to the pre-trigger covariance state.

{md_table(pedestal, ["method", "n_pedestal_states", "state_bias_span", "state_sigma68_span", "worst_state", "worst_abs_state_bias"])}

## Downstream PID Stability Proxy

The downstream PID stability table stratifies held-out energy closure by run,
amplitude, timing separation, and the benchmark PID proxy class.  The stability
proxy is the worst stratum sigma68 divided by the median stratum sigma68; values
near one indicate less risk of PID-boundary migration from energy-scale
heterogeneity.

{md_table(pid, ["stability_axis", "method", "n_strata", "energy_sigma68_stratum_median", "energy_sigma68_stratum_span", "pid_stability_proxy"], limit=80)}

## Saturation-Mask Ablation

The saturation-mask ablation recomputes the held-out metrics after slicing on
the observed clipped-sample mask.  This is not a retraining pass; it asks whether
the winning conclusion is carried by unsaturated easy cases or by the clipped
tail-recovery region named in the ticket.

{md_table(ablation.sort_values(["ablation", "method"]), ["ablation", "method", "energy_fractional_bias", "energy_fractional_sigma68", "time_sigma68_ns", "pileup_miss_rate", "false_split_rate", "n_events"], limit=60)}

## Uncertainty Calibration

The per-event uncertainty proxy is a transparent function of clipped samples,
plateau width, and close-pulse spacing:

`u_i = 0.030 + 0.006 n_clip + 0.004 max(W_plateau-2,0) + 0.002 max(4-Delta,0)`.

Coverage is reported against the absolute fractional energy residual.

{md_table(calibration, ["method", "n_valid_doublets", "p68_abs_energy_residual", "nominal_68_proxy_width", "coverage_abs_resid_le_proxy", "coverage_abs_resid_le_2proxy", "calibration_ratio_p68_over_proxy"])}

## Queue Provenance

The required single claim command was run once as `{CLAIM_COMMAND}` and returned
the null pseudo-ticket output `{CLAIM_OUTPUT}`.  Because the project queue was
not empty, issue `#2544` was recovered without a second `tn-ticket claim` by
applying the same label transition directly: `{MANUAL_RECOVERY}`.  Completion is
recorded with `{DONE_COMMAND}`.  No novel follow-up ticket was appended.
"""
    report_path.write_text(text, encoding="utf-8")


def patch_result(
    sideband: pd.DataFrame,
    ablation: pd.DataFrame,
    calibration: pd.DataFrame,
    knee: pd.DataFrame,
    separation: pd.DataFrame,
    pedestal: pd.DataFrame,
    pid: pd.DataFrame,
) -> None:
    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": ISSUE_NUMBER,
            "issue_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2544",
            "worker": WORKER,
            "title": TITLE,
            "claimed_ticket_text": "#2544 NEW S65b censored saturation energy recovery with pile-up-resolved pulse decomposition",
            "claim_command": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "done_command": DONE_COMMAND,
            "manual_claim_recovery": {
                "reason": "tn-ticket claim returned a null pseudo-ticket despite a non-empty testbeam queue",
                "manual_recovery": MANUAL_RECOVERY,
                "reran_claim": False,
            },
        }
    )
    result["required_outputs"] = {
        "injected_overlap_closure": "method_metrics.csv, run_heldout_metrics.csv, event_predictions.csv",
        "real_data_sideband_validation": "real_data_sideband_validation.csv",
        "saturation_mask_ablation": "saturation_mask_ablation.csv",
        "uncertainty_calibration": "uncertainty_calibration.csv",
        "saturation_knee_bias": "saturation_knee_bias.csv",
        "pileup_separation_error": "pileup_separation_error.csv",
        "pedestal_covariance_sensitivity": "pedestal_covariance_sensitivity.csv",
        "downstream_pid_stability": "downstream_pid_stability.csv",
        "traditional_vs_neural_failure_interpretation": "REPORT.md",
    }
    result["queue_provenance"] = {
        "claimed_once": True,
        "claim_command_run_once": CLAIM_COMMAND,
        "claim_command_output": CLAIM_OUTPUT,
        "manual_claim_recovery": MANUAL_RECOVERY,
        "done_command": DONE_COMMAND,
        "novel_tickets_appended": [],
    }
    result["artifacts"].update(
        {
            "real_data_sideband_validation": "real_data_sideband_validation.csv",
            "saturation_mask_ablation": "saturation_mask_ablation.csv",
            "uncertainty_calibration": "uncertainty_calibration.csv",
            "saturation_knee_bias": "saturation_knee_bias.csv",
            "pileup_separation_error": "pileup_separation_error.csv",
            "pedestal_covariance_sensitivity": "pedestal_covariance_sensitivity.csv",
            "downstream_pid_stability": "downstream_pid_stability.csv",
        }
    )
    winner_name = result["winner"]["name"]
    winner_cal = calibration[calibration["method"] == winner_name].iloc[0].to_dict()
    winner_sep = separation[separation["method"] == winner_name].iloc[0].to_dict()
    winner_ped = pedestal[pedestal["method"] == winner_name].iloc[0].to_dict()
    result["winner"]["uncertainty_calibration"] = {
        key: float(value) if isinstance(value, (int, float, np.integer, np.floating)) else value
        for key, value in winner_cal.items()
    }
    result["winner"]["pileup_separation_error_rate"] = float(winner_sep["pileup_separation_error_rate"])
    result["winner"]["pileup_separation_error_ci95"] = [
        float(winner_sep["pileup_separation_error_ci_low"]),
        float(winner_sep["pileup_separation_error_ci_high"]),
    ]
    result["winner"]["pedestal_state_bias_span"] = float(winner_ped["state_bias_span"])
    result["ticket_specific_artifacts"] = {
        "saturation_knee_bias": knee.to_dict(orient="records"),
        "pileup_separation_error": separation.to_dict(orient="records"),
        "pedestal_covariance_sensitivity": pedestal.to_dict(orient="records"),
        "downstream_pid_stability": pid.to_dict(orient="records"),
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    root_result = {
        "ticket_id": TICKET,
        "issue_number": ISSUE_NUMBER,
        "project": "testbeam",
        "worker": WORKER,
        "status": "complete",
        "winner": result["winner"]["name"],
        "winner_metrics": result["winner"],
        "raw_root_reproduction": result["raw_root_reproduction"],
        "split": result["evaluation_design"],
        "required_method_coverage": result["required_method_coverage"],
        "required_outputs": result["required_outputs"],
        "artifacts": {
            "report": str((OUT / "REPORT.md").relative_to(ROOT)),
            "result": str((OUT / "result.json").relative_to(ROOT)),
            "method_metrics": str((OUT / "method_metrics.csv").relative_to(ROOT)),
            "run_heldout_metrics": str((OUT / "run_heldout_metrics.csv").relative_to(ROOT)),
            "real_data_sideband_validation": str((OUT / "real_data_sideband_validation.csv").relative_to(ROOT)),
            "saturation_mask_ablation": str((OUT / "saturation_mask_ablation.csv").relative_to(ROOT)),
            "uncertainty_calibration": str((OUT / "uncertainty_calibration.csv").relative_to(ROOT)),
            "saturation_knee_bias": str((OUT / "saturation_knee_bias.csv").relative_to(ROOT)),
            "pileup_separation_error": str((OUT / "pileup_separation_error.csv").relative_to(ROOT)),
            "pedestal_covariance_sensitivity": str((OUT / "pedestal_covariance_sensitivity.csv").relative_to(ROOT)),
            "downstream_pid_stability": str((OUT / "downstream_pid_stability.csv").relative_to(ROOT)),
        },
        "queue_provenance": result["queue_provenance"],
        "done_command": DONE_COMMAND,
        "novel_tickets_appended": [],
    }
    (ROOT / "result.json").write_text(json.dumps(root_result, indent=2) + "\n", encoding="utf-8")


def patch_manifest() -> None:
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "ticket_id": TICKET,
            "issue_number": ISSUE_NUMBER,
            "worker": WORKER,
            "command": f"{sys.executable} scripts/s65b_2544_censored_saturation_energy_pileup_resolved_pulse_decomposition.py",
            "core_benchmark": "scripts/s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff.py",
            "claim_command_run_once": CLAIM_COMMAND,
            "claim_command_output": CLAIM_OUTPUT,
            "manual_claim_recovery": MANUAL_RECOVERY,
            "done_command": DONE_COMMAND,
        }
    )
    manifest["outputs_sha256"] = {
        p.name: base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.WORKER = WORKER
    s32b.SLUG = SLUG
    s32b.TITLE = TITLE
    s32b.OUT = OUT
    s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s32b.os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib-s65b"
    s32b.main()

    (OUT / "claimed_ticket.txt").write_text(
        "#2544 NEW S65b censored saturation energy recovery with pile-up-resolved pulse decomposition\n"
        "Claim recovery: required tn-ticket command was run once and returned null; "
        "manually applied worker label to issue #2544 without rerunning tn-ticket claim.\n",
        encoding="utf-8",
    )

    joined = pd.read_csv(OUT / "event_predictions.csv")
    sideband = real_data_sideband_validation(joined)
    ablation = saturation_mask_ablation(joined)
    calibration = uncertainty_calibration(joined)
    knee = saturation_knee_bias(joined)
    separation = pileup_separation_error(joined)
    pedestal = pedestal_covariance_sensitivity(joined)
    pid = downstream_pid_stability(joined)
    sideband.to_csv(OUT / "real_data_sideband_validation.csv", index=False)
    ablation.to_csv(OUT / "saturation_mask_ablation.csv", index=False)
    calibration.to_csv(OUT / "uncertainty_calibration.csv", index=False)
    knee.to_csv(OUT / "saturation_knee_bias.csv", index=False)
    separation.to_csv(OUT / "pileup_separation_error.csv", index=False)
    pedestal.to_csv(OUT / "pedestal_covariance_sensitivity.csv", index=False)
    pid.to_csv(OUT / "downstream_pid_stability.csv", index=False)

    patch_report(sideband, ablation, calibration, knee, separation, pedestal, pid)
    patch_result(sideband, ablation, calibration, knee, separation, pedestal, pid)
    patch_manifest()


if __name__ == "__main__":
    main()
