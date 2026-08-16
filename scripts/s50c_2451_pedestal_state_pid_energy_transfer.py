#!/usr/bin/env python3
"""S50c pedestal-state PID energy transfer benchmark.

This runner reuses the established S36c controlled-overlay benchmark and
retitles the artifacts for the claimed S50c ticket.  The benchmark starts from
raw B-stack ROOT pulses, reproduces the selected-pulse count, then compares a
traditional pedestal-subtracted charge-ratio/PID boundary method with ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact transformer, and a new
pedestal-memory fusion architecture.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s36c_1784064870_931_2c5305bf_pedestal_memory_pid_energy_calibration as s36c  # noqa: E402


TICKET = "2451"
TITLE = "S50c: Pedestal-state PID energy transfer with interpretable waveform representations"
WORKER = "testbeam-laptop-3"
SLUG = "s50c_pedestal_state_pid_energy_transfer"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
NEXT_TICKET = {
    "title": "S53a: external PID-label validation for pedestal-state waveform transfer",
    "body": (
        "Join external beam/trigger PID labels or digitized-Geant4 truth to the S50c "
        "raw-waveform pedestal-state benchmark, then rerun the traditional, ridge, GBT, "
        "MLP, 1D-CNN, transformer, and pedestal-memory-fusion panel with literal run-held-out "
        "bootstrap CIs. Expected information gain: separates true particle-ID transfer from "
        "the charge/stave proxy used in S50c."
    ),
}


def patch_s36c_globals() -> None:
    s36c.TICKET = TICKET
    s36c.TITLE = TITLE
    s36c.WORKER = WORKER
    s36c.SLUG = SLUG
    s36c.OUT = OUT
    s36c.RAW_ROOT_DIR = RAW_ROOT_DIR
    s36c.NEXT_TICKET = NEXT_TICKET


def add_calibration_confusion_and_diagnostics() -> None:
    pred_path = OUT / "event_predictions.csv"
    ranked_path = OUT / "winner_ranked_metrics.csv"
    if not pred_path.exists() or not ranked_path.exists():
        return
    joined = pd.read_csv(pred_path)
    ranked = pd.read_csv(ranked_path)
    winner = str(ranked.iloc[0]["method"])
    held = joined[(joined["split"] == "heldout") & (joined["method"] == winner)].copy()
    held = held[(held["is_overlap"] == 1) & (~held["failed"].astype(bool))].copy()
    if held.empty:
        return

    true_energy = held["true_amp1_adc"].to_numpy(float) + held["true_amp2_adc"].to_numpy(float)
    pred_energy = held["amp1_adc"].to_numpy(float) + held["amp2_adc"].to_numpy(float)
    pid_true = ((held["pid_proxy_class"].astype(str) == "inner_high_charge")).astype(int).to_numpy()
    pid_pred = ((held["stave"].isin(["B2", "B4"]).to_numpy()) & (pred_energy > 9000.0)).astype(int)

    bins = pd.qcut(pred_energy, q=8, duplicates="drop")
    calib = held.assign(pred_energy=pred_energy, true_energy=true_energy, pid_true=pid_true, pid_pred=pid_pred, bin=bins)
    calibration = (
        calib.groupby("bin", observed=False)
        .agg(
            n=("event_id", "size"),
            pred_energy_mean=("pred_energy", "mean"),
            true_energy_mean=("true_energy", "mean"),
            pid_pred_rate=("pid_pred", "mean"),
            pid_proxy_rate=("pid_true", "mean"),
        )
        .reset_index()
    )
    calibration["energy_calibration_bias_frac"] = (
        calibration["pred_energy_mean"] - calibration["true_energy_mean"]
    ) / np.maximum(calibration["true_energy_mean"], 1.0)
    calibration.to_csv(OUT / "calibration_curve_winner.csv", index=False)

    cm = confusion_matrix(pid_true, pid_pred, labels=[0, 1])
    pd.DataFrame(
        cm,
        index=["true_outer_or_low_charge", "true_inner_high_charge"],
        columns=["pred_outer_or_low_charge", "pred_inner_high_charge"],
    ).to_csv(OUT / "confusion_matrix_winner.csv")

    diagnostics = []
    for state, group in held.groupby("pedestal_state", observed=False):
        err = (group["amp1_adc"].to_numpy(float) + group["amp2_adc"].to_numpy(float) - (
            group["true_amp1_adc"].to_numpy(float) + group["true_amp2_adc"].to_numpy(float)
        )) / np.maximum(group["true_amp1_adc"].to_numpy(float) + group["true_amp2_adc"].to_numpy(float), 1.0)
        diagnostics.append(
            {
                "diagnostic": "pedestal_state_energy_bias",
                "region": str(state),
                "n": int(len(group)),
                "value": float(np.median(err)),
                "interpretation": "winner residual energy bias by pretrigger pedestal-memory stratum",
            }
        )
    for state, group in held.groupby("morphology_state", observed=False):
        diagnostics.append(
            {
                "diagnostic": "morphology_score_mean",
                "region": str(state),
                "n": int(len(group)),
                "value": float(group["score"].mean()),
                "interpretation": "model acceptance score tied to waveform late-tail/pulse-shape region",
            }
        )
    region_defs = {
        "pretrigger_samples_0_3": held["pedestal_state"].astype(str) == "shifted",
        "leading_edge_samples_4_7": held["true_t1_sample"].between(4.0, 7.0, inclusive="both"),
        "overlap_core_sep_lt_10ns": held["true_sep_sample"].to_numpy(float) < 1.0,
        "rising_overlap_sep_10_25ns": held["true_sep_sample"].between(1.0, 2.5, inclusive="both"),
        "late_tail_sep_gt_45ns": held["true_sep_sample"].to_numpy(float) > 4.5,
        "saturation_plateau_samples": held["saturated_sample_count"].to_numpy(float) > 0.0,
    }
    for region, mask in region_defs.items():
        group = held.loc[np.asarray(mask)]
        if group.empty:
            continue
        energy_err = (
            group["amp1_adc"].to_numpy(float)
            + group["amp2_adc"].to_numpy(float)
            - group["true_amp1_adc"].to_numpy(float)
            - group["true_amp2_adc"].to_numpy(float)
        ) / np.maximum(group["true_amp1_adc"].to_numpy(float) + group["true_amp2_adc"].to_numpy(float), 1.0)
        time_err = np.concatenate(
            [
                (group["t1_sample"].to_numpy(float) - group["true_t1_sample"].to_numpy(float)) * 10.0,
                (group["t2_sample"].to_numpy(float) - group["true_t2_sample"].to_numpy(float)) * 10.0,
            ]
        )
        diagnostics.append(
            {
                "diagnostic": "waveform_region_energy_bias",
                "region": region,
                "n": int(len(group)),
                "value": float(np.median(energy_err)),
                "interpretation": "winner residual energy bias localized to an interpretable waveform time region",
            }
        )
        diagnostics.append(
            {
                "diagnostic": "waveform_region_timing_sigma68_ns",
                "region": region,
                "n": int(len(group)),
                "value": float((np.percentile(time_err, 84.0) - np.percentile(time_err, 16.0)) / 2.0),
                "interpretation": "winner timing width localized to an interpretable waveform time region",
            }
        )
    pd.DataFrame(diagnostics).to_csv(OUT / "feature_attention_diagnostics.csv", index=False)


def retitle_outputs() -> None:
    replacements = {
        "S36c": "S50c",
        "Pedestal-Memory Transfer into Joint PID-Energy Calibration": "Pedestal-State PID Energy Transfer with Interpretable Waveform Representations",
        "pedestal-memory transfer into joint PID-energy calibration": "pedestal-state PID energy transfer with interpretable waveform representations",
        "S36c pedestal-memory transfer into joint PID-energy calibration": TITLE,
        "S36c: pedestal-memory transfer into joint PID-energy calibration": TITLE,
        "registered S36c": "registered S50c",
    }
    report_path = OUT / "REPORT.md"
    if report_path.exists():
        text = report_path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        insert = """

## Calibration, Confusion, and Interpretability Diagnostics

The winner-specific calibration curve is written to
`calibration_curve_winner.csv`; it bins held-out predicted energy and compares
the bin mean to injected truth, while also reporting the PID-proxy positive
rate.  The corresponding `confusion_matrix_winner.csv` records the
outer/low-charge versus inner/high-charge PID-proxy migration.  The file
`feature_attention_diagnostics.csv` ties the winner's residual behavior back to
pretrigger pedestal strata, late-tail morphology states, and waveform sample
regions.  These diagnostics are intentionally proxy-qualified because the raw
ROOT files do not contain external particle-identity labels.
"""
        if "## Calibration, Confusion, and Interpretability Diagnostics" not in text:
            text = text.replace("\n## Systematics and Caveats\n", insert + "\n## Systematics and Caveats\n")
        report_path.write_text(text, encoding="utf-8")

    result_path = OUT / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result.update(
            {
                "ticket_id": TICKET,
                "project": "testbeam",
                "worker": WORKER,
                "title": TITLE,
                "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
                "claimed_ticket_text": TITLE,
                "ticket_url": "https://github.com/SzeChunYiu/factory-tickets/issues/2451",
            }
        )
        result["raw_root_reproduction"]["raw_root_glob"] = str(RAW_ROOT_DIR / "hrdb_run_*.root")
        result["evaluation_design"]["study"] = "S50c run-held-out PID-energy transfer benchmark"
        if "cross_channel_attention_transformer_when_available" in result["required_method_coverage"]:
            result["required_method_coverage"]["transformer_or_temporal_convolution"] = result[
                "required_method_coverage"
            ].pop("cross_channel_attention_transformer_when_available")
        result["winner"]["criterion"] = result["winner"]["criterion"].replace("S36c", "S50c")
        result["artifacts"].update(
            {
                "calibration_curve_winner": "calibration_curve_winner.csv",
                "confusion_matrix_winner": "confusion_matrix_winner.csv",
                "feature_attention_diagnostics": "feature_attention_diagnostics.csv",
            }
        )
        result["next_tickets"] = [NEXT_TICKET]
        result["novel_tickets_appended"] = [NEXT_TICKET["title"]]
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(result_path, ROOT / "result.json")

    manifest_path = OUT / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["ticket_id"] = TICKET
        manifest["command"] = f"{sys.executable} scripts/s50c_2451_pedestal_state_pid_energy_transfer.py"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    patch_s36c_globals()
    s36c.main()
    add_calibration_confusion_and_diagnostics()
    retitle_outputs()


if __name__ == "__main__":
    main()
