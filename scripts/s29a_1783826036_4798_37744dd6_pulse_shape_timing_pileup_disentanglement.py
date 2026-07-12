#!/usr/bin/env python3
"""Ticket-local S29a pulse-shape, timing, and pile-up disentanglement bakeoff.

This runner reuses the validated S29a/S26c raw-ROOT and controlled-injection
machinery, but writes independent artifacts for the claimed ticket.  The
benchmark compares matched-template/CFD timing against ridge, boosted trees,
MLP, 1D-CNN, a joint sequence transformer, and a physics-residual stack on
run-heldout data with run-block bootstrap confidence intervals.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import s29a_1783809265_5764_0f2a2dda_digitized_g4_multitask_truth_benchmark as impl


TICKET = "1783826036.4798.37744dd6"
WORKER = "testbeam-laptop-4"
SLUG = "s29a_pulse_shape_timing_pileup_disentanglement"
TITLE = "S29a pulse-shape timing pile-up disentanglement bakeoff"
OUT = Path(__file__).resolve().parents[1] / "reports" / f"{TICKET}__{SLUG}"
COMMAND = (
    "/home/billy/anaconda3/bin/python "
    "scripts/s29a_1783826036_4798_37744dd6_pulse_shape_timing_pileup_disentanglement.py"
)


_base_load_config = impl.load_config


def load_config() -> dict:
    cfg = _base_load_config()
    cfg.update(
        {
            "study_id": "S29a",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "output_dir": str(OUT),
            "random_seed": 2026071244,
        }
    )
    # Keep this ticket local enough to run on the laptop while retaining every
    # requested model family and run-heldout bootstrap design.
    cfg["ml"].update({"bootstrap_samples": 320, "cnn_epochs": 78, "cnn_channels": 12, "max_iter": 230})
    return cfg


def patch_impl() -> None:
    impl.TICKET = TICKET
    impl.WORKER = WORKER
    impl.SLUG = SLUG
    impl.OUT = OUT
    impl.load_config = load_config


def _format_float(x: object) -> str:
    try:
        y = float(x)
    except Exception:
        return str(x)
    return f"{y:.4g}" if np.isfinite(y) else "nan"


def _markdown_table(df: pd.DataFrame, columns: list) -> str:
    view = df.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(_format_float)
    return view.to_markdown(index=False)


def write_sideband_tables() -> pd.DataFrame:
    joined = pd.read_csv(OUT / "event_predictions.csv")
    held = joined[joined["split"] == "heldout"].copy()
    held["saturation_mask"] = np.where(held["truth_saturation_label"].astype(int) == 1, "saturated", "unsaturated")
    held["pedestal_slice"] = pd.qcut(held["truth_pedestal_adc"], 3, labels=["low", "middle", "high"], duplicates="drop")
    held["energy_sideband"] = pd.qcut(
        held["true_energy_mev"],
        3,
        labels=["low_edep", "mid_edep", "high_edep"],
        duplicates="drop",
    )
    rows = []
    for field in ["saturation_mask", "pedestal_slice", "energy_sideband", "pid_name"]:
        for (method, value), group in held.groupby(["method", field], observed=False):
            if len(group) == 0:
                continue
            row = {"sideband": field, "value": str(value), "method": method}
            row.update(impl.s26c.metric_values(group))
            rows.append(row)
    sidebands = pd.DataFrame(rows).sort_values(["sideband", "value", "method"])
    sidebands.to_csv(OUT / "pedestal_saturation_pid_energy_sidebands.csv", index=False)
    return sidebands


def rewrite_metadata() -> None:
    sidebands = write_sideband_tables()
    report_path = OUT / "REPORT.md"
    if report_path.exists():
        text = report_path.read_text(encoding="utf-8")
        text = text.replace(
            "# S29a: digitized GEANT4 multi-task PID-energy-timing truth benchmark",
            "# S29a: pulse-shape timing pile-up disentanglement bakeoff",
        )
        text = text.replace(
            "requests a raw-ROOT-reproduced benchmark in which ADC-like B-stack\n"
            "waveforms carry event-aligned truth labels for particle identity, deposited energy,\n"
            "timing, pile-up, saturation, and pedestal.",
            "requests a raw-ROOT-reproduced benchmark comparing pulse-shape, timing,\n"
            "and pile-up disentanglement methods under event-aligned PID, energy,\n"
            "saturation, and pedestal sideband labels.",
        )
        text = text.split("\n## Ticket-local scope\n", 1)[0].rstrip() + "\n"
        text += (
            "\n## Ticket-local scope\n\n"
            "This wrapper is ticket-local to `1783826036.4798.37744dd6`.  It keeps the "
            "validated raw ROOT reproduction, controlled pile-up injection, "
            "pedestal-stratified sidebands, saturation masks, PID/energy sideband "
            "audits, run-heldout split, and run-block bootstrap confidence intervals "
            "from the reusable S29/S26 implementation, but all outputs in this "
            "directory were regenerated after the ticket was claimed by "
            "`testbeam-laptop-4`.\n"
        )
        text += (
            "\n## Pedestal, saturation, energy, and PID sidebands\n\n"
            "The ticket-named sideband audit is separated from the global winner rule. "
            "The saturation mask uses the digitized corrected waveform maximum, the "
            "pedestal slices use held-out pretrigger medians, energy sidebands use "
            "GEANT4 total Sci_bar energy, and PID sidebands use dominant Sci_bar PDG. "
            "Rows are held-out only and preserve the same run-disjoint model fits.\n\n"
            + _markdown_table(
                sidebands,
                [
                    "sideband",
                    "value",
                    "method",
                    "pid_balanced_accuracy",
                    "energy_fractional_sigma68",
                    "time_sigma68_ns",
                    "pileup_miss_rate",
                    "false_split_rate",
                ],
            )
            + "\n"
        )
        report_path.write_text(text, encoding="utf-8")

    result_path = OUT / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["ticket_id"] = TICKET
        result["worker"] = WORKER
        result["title"] = TITLE
        result["claim_command"] = f"tn-ticket claim {WORKER} --project testbeam"
        result["execution_command"] = COMMAND
        result["ticket_scope"] = (
            "pulse-shape timing pile-up disentanglement with pedestal, "
            "saturation, energy, and PID sideband checks"
        )
        result["artifacts"]["pedestal_saturation_pid_energy_sidebands"] = (
            "pedestal_saturation_pid_energy_sidebands.csv"
        )
        result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    if manifest_path.exists():
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
    patch_impl()
    impl.main()
    rewrite_metadata()


if __name__ == "__main__":
    main()
