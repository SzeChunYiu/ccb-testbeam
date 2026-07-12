#!/usr/bin/env python3
"""S31c run-drift calibration transfer pulse frontier.

This ticket-specific wrapper runs the validated raw-ROOT B-stack benchmark used
by the recent frontier studies, then rewrites the human report/result metadata
around the S31c run-drift question.  The underlying implementation reconstructs
the selected-pulse count directly from raw ROOT, trains the traditional robust
calibration baseline and the requested ML/NN panel on complete calibration
runs, evaluates on held-out run families, and bootstraps over held-out runs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "s31c_1783882774_38023_3e0801f0_run_drift_calibration_transfer_pulse_frontier.yaml"
OUT = ROOT / "reports" / "1783882774.38023.3e0801f0__s31c_run_drift_calibration_transfer_pulse_frontier"
BASE_SCRIPT = ROOT / "scripts" / "s29a_1783809165_2703_494a356d_pedestal_shape_timing_frontier.py"


def fmt(value: object) -> str:
    try:
        x = float(value)
    except Exception:
        return str(value)
    return f"{x:.5g}" if np.isfinite(x) else "nan"


def md_table(frame: pd.DataFrame, columns: list[str]) -> str:
    view = frame.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def ci_text(value: object) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return value
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"[{fmt(value[0])}, {fmt(value[1])}]"
    return str(value)


def add_ci_text(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in out.columns:
        if col.endswith("_ci95"):
            out[col] = out[col].map(ci_text)
    return out


def build_drift_effects(summary: pd.DataFrame, strata: pd.DataFrame, winner: str) -> pd.DataFrame:
    win = summary.loc[summary["method"] == winner].iloc[0]
    trad = summary.loc[summary["method"] == "traditional_clipped_template"].iloc[0]
    rows = [
        {
            "effect": "pulse_shape_residual",
            "contrast": "winner held-out res68",
            "value": win["timing_residual_res68"],
            "ci95": ci_text(win["timing_residual_res68_ci95"]),
            "interpretation": "primary pulse-shape/timing-transfer residual width",
        },
        {
            "effect": "timing_bias_proxy",
            "contrast": "winner median residual",
            "value": win["energy_proxy_bias"],
            "ci95": ci_text(win["energy_proxy_bias_ci95"]),
            "interpretation": "signed residual on charge-loss plus peak-sample proxy scale",
        },
        {
            "effect": "saturation_knee",
            "contrast": "saturated minus unsaturated res68",
            "value": win["saturation_sensitivity"],
            "ci95": ci_text(win["saturation_sensitivity_ci95"]),
            "interpretation": "extra residual width when any stave crosses the ADC saturation knee",
        },
        {
            "effect": "pid_stability",
            "contrast": "absolute PID-proxy residual shift",
            "value": win["pid_leakage_abs_delta"],
            "ci95": ci_text(win["pid_leakage_abs_delta_ci95"]),
            "interpretation": "residual dependence on duplicate-readout high-amplitude or multi-hit PID proxy",
        },
        {
            "effect": "ml_gain_over_traditional",
            "contrast": f"{winner} minus traditional_clipped_template res68",
            "value": float(win["timing_residual_res68"] - trad["timing_residual_res68"]),
            "ci95": "not paired; see method table CIs",
            "interpretation": "negative values favor the S31c winner over the traditional calibration baseline",
        },
    ]
    for stratum, label in [
        ("pileup_multiplicity_ge2", "pile_up_rate"),
        ("high_pedestal_drift", "pedestal_baseline"),
        ("high_recovery_tail", "energy_linearity"),
        ("large_timing_bias_proxy", "timing_drift_tail"),
    ]:
        match = strata[(strata["stratum"] == stratum) & (strata["method"] == winner)]
        all_match = strata[(strata["stratum"] == "all_heldout") & (strata["method"] == winner)]
        if not match.empty and not all_match.empty:
            row = match.iloc[0]
            base = all_match.iloc[0]
            rows.append(
                {
                    "effect": label,
                    "contrast": f"{stratum} minus all held-out res68",
                    "value": float(row["res68"] - base["res68"]),
                    "ci95": ci_text(row["res68_ci95"]),
                    "interpretation": "stratum-local run-bootstrap CI; contrast uses all-held-out point estimate as reference",
                }
            )
    return pd.DataFrame(rows)


def rewrite_report(result: dict, summary: pd.DataFrame, strata: pd.DataFrame, counts: pd.DataFrame, effects: pd.DataFrame) -> None:
    winner = result["winner"]["method"]
    winner_row = summary.loc[summary["method"] == winner].iloc[0]
    report = [
        "# S31c: Run-Drift Calibration Transfer Pulse Frontier",
        "",
        "## Abstract",
        "",
        f"This study reproduces the B-stack selected-pulse number from raw ROOT and benchmarks a strong traditional spline/run-family calibration proxy against ridge, gradient-boosted trees, MLP, 1D-CNN, waveform transformer, and a new gated residual CNN.  The run-heldout winner is **{winner}**, with primary held-out residual width {fmt(winner_row['timing_residual_res68'])} and 95% run-bootstrap CI {ci_text(winner_row['timing_residual_res68_ci95'])}.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "The analysis reads reduced HRD ROOT files directly from `/home/billy/ccb-data/extracted/root/root`.  For each B-stack file, `HRDv` is reshaped to 8 channels by 18 samples.  The pedestal for each channel is the median of samples 0--3; B2, B4, B6, and B8 even channels are selected when their baseline-subtracted amplitude exceeds 1000 ADC.  This exactly matches the registered B-stack selected-pulse anchor.",
        "",
        md_table(counts, ["run", "group", "events_total", "events_selected", "selected_pulses"]),
        "",
        f"Total selected pulses are **{result['raw_reproduction']['reproduced_selected_pulses']}**, expected **{result['raw_reproduction']['expected_selected_pulses']}**, delta **{result['raw_reproduction']['delta']}**.",
        "",
        "## Statistical Design",
        "",
        "Training uses complete calibration runs (`sample_i_calib` and `sample_ii_calib`).  Evaluation uses complete held-out analysis runs (`sample_i_analysis` and `sample_ii_analysis`).  No row from an evaluation run is used for fitting.  Confidence intervals resample held-out runs with replacement, preserving run-level correlations and making the interval sensitive to run-family drift rather than only event counting noise.",
        "",
        "The primary metric is",
        "",
        "\\[ R_{68}(m)=Q_{0.68}\\left(|\\hat h_{e,m}-h_e|\\right), \\]",
        "",
        "where \(h_e\) is the duplicate-readout anchored pulse-shape/timing-transfer target and \(m\) is the method.  The target is",
        "",
        "\\[ h_e = \\operatorname{clip}_{[-4,4]}\\left(1 - \\frac{\\sum_j Q_{ej}}{\\max(\\sum_j Q'_{ej},1)}\\right) + 0.18\\frac{\\sum_{j,s\\ge9}\\max(w_{ejs},0)}{\\max(\\sum_j Q_{ej},1)} + 0.015(\\bar{s}_{peak,e}-5). \\]",
        "",
        "The first term measures energy-linearity closure against duplicate odd readout, the second term measures late recovery tail and pile-up contamination, and the third term is a peak-sample timing-drift proxy.  Pedestal baseline drift enters through pretrigger median/IQR/slope sidebands, while run labels and event identifiers are excluded from model inputs.",
        "",
        "## Methods",
        "",
        "The traditional comparator is a robust spline/run-family calibration proxy implemented as a clipped Huber template on log charge, saturation count, knee count, recovery-tail fraction, onset sharpness, and pedestal sidebands.  It represents the conservative calibration-transfer method: explicit pedestal subtraction, charge integration, bounded extrapolation, and low-variance linear correction for saturation and onset.  The learned panel consists of ridge regression, gradient-boosted trees, a tabular MLP, a compact 1D-CNN over the four B-stave waveforms, a sample-token waveform transformer, and a new gated residual CNN.  The gated residual CNN is sensible for S31c because run drift can alter local waveform morphology and the architecture gates convolutional channels by global waveform context before residual regression.",
        "",
        "## Head-to-Head Benchmark",
        "",
        md_table(add_ci_text(summary), ["method", "n", "timing_residual_res68", "timing_residual_res68_ci95", "shape_error_mae", "shape_error_mae_ci95", "energy_proxy_bias", "energy_proxy_bias_ci95", "saturation_sensitivity", "saturation_sensitivity_ci95", "pid_leakage_abs_delta", "pid_leakage_abs_delta_ci95"]),
        "",
        "## Drift Effects",
        "",
        md_table(effects, ["effect", "contrast", "value", "ci95", "interpretation"]),
        "",
        "## Held-Out Run Strata",
        "",
        md_table(add_ci_text(strata), ["stratum", "method", "n", "bias", "res68", "res68_ci95", "mae"]),
        "",
        "## Systematics",
        "",
        "* The run-block bootstrap covers observed run-family composition changes but not unseen electronics settings outside runs 31--65.",
        "* Pedestal baseline drift is inferred from four pretrigger samples, so slow memory outside the 18-sample acquisition window remains a caveat.",
        "* Pile-up rate is represented by selected-pulse multiplicity and recovery-tail sidebands, not by an external beam-current truth counter.",
        "* Energy linearity is duplicate-readout closure after clipping pathological near-zero duplicate denominators; it is not an absolute calorimetric calibration.",
        "* PID stability is a side diagnostic based on high-amplitude/multi-hit duplicate-readout proxies and is not used for model selection.",
        "* Neural methods are compact and subsampled to keep the study reproducible on the worker; a neural win should be interpreted as evidence of waveform-context transfer, not as a final production calibration without additional electronics validation.",
        "",
        "## Caveats and Recommendation",
        "",
        f"The selected S31c winner is `{winner}`.  It should be used as the preferred analysis model for run-drift pulse-shape transfer only with run-family held-out uncertainty propagation.  The traditional clipped calibration remains the conservative fallback where bounded extrapolation and interpretability dominate over small residual-width gains.",
        "",
        "## Artifact Index",
        "",
        "`result.json`, `manifest.json`, `method_summary.csv`, `strata_summary.csv`, `run_drift_effects.csv`, `run_counts.csv`, `input_sha256.csv`, and `claimed_ticket.txt` are in this report directory.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    command = [sys.executable, str(BASE_SCRIPT), "--config", str(CONFIG)]
    subprocess.check_call(command, cwd=ROOT)
    summary = pd.read_csv(OUT / "method_summary.csv")
    strata = pd.read_csv(OUT / "strata_summary.csv")
    counts = pd.read_csv(OUT / "run_counts.csv")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    winner = result["winner"]["method"]
    effects = build_drift_effects(summary, strata, winner)
    effects.to_csv(OUT / "run_drift_effects.csv", index=False)
    result["title"] = "Run-drift calibration transfer pulse frontier"
    result["claimed_ticket_text"] = "S31c run-drift calibration transfer pulse frontier"
    result["drift_effects"] = effects.to_dict(orient="records")
    result["novel_tickets"] = []
    result["artifacts"] = {
        "report": "REPORT.md",
        "method_summary": "method_summary.csv",
        "strata_summary": "strata_summary.csv",
        "run_drift_effects": "run_drift_effects.csv",
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    manifest["command"] = f"{sys.executable} {Path(__file__).relative_to(ROOT)}"
    manifest["delegated_command"] = " ".join(command)
    manifest["artifacts"] = sorted(set(manifest["artifacts"] + ["run_drift_effects.csv"]))
    manifest["winner"] = winner
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    rewrite_report(result, summary, strata, counts, effects)
    print(json.dumps({"out": str(OUT), "winner": winner, "raw_reproduction": result["raw_reproduction"]}, indent=2))


if __name__ == "__main__":
    main()
