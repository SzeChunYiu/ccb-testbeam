#!/usr/bin/env python3
"""Ticket 2559 S61b pile-up saturation energy recovery bakeoff."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

import s35b_1784063447_914_74ba7793_saturation_pileup_energy_recovery_benchmark as impl


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2559"
WORKER = "testbeam-laptop-1"
TITLE = "S61b pile-up saturation energy recovery bakeoff"
SLUG = "s61b_pileup_saturation_energy_recovery_bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84.0) - np.percentile(values, 16.0)) / 2.0)


def write_abstention_curves(pred: pd.DataFrame) -> pd.DataFrame:
    held = pred[pred["split"] == "heldout"].copy()
    rows = []
    for method, group in held.groupby("method", sort=True):
        score = group["score"].to_numpy(float)
        thresholds = sorted(set(np.nanquantile(score[np.isfinite(score)], [0.0, 0.25, 0.50, 0.75, 0.90]).tolist() + [0.5]))
        for threshold in thresholds:
            accepted = group[group["score"].to_numpy(float) >= threshold].copy()
            pos = accepted[accepted["is_overlap"] == 1]
            if len(pos):
                true_e = pos[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
                pred_e = pos[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
                energy_err = (pred_e - true_e) / np.maximum(true_e, 1.0)
                delay_err = ((pos["t2_sample"] - pos["t1_sample"]) - pos["true_sep_sample"]).to_numpy(float) * 10.0
            else:
                energy_err = delay_err = np.asarray([])
            rows.append(
                {
                    "method": method,
                    "score_threshold": float(threshold),
                    "accepted_fraction": float(len(accepted) / max(len(group), 1)),
                    "accepted_positive_fraction": float(len(pos) / max((group["is_overlap"] == 1).sum(), 1)),
                    "energy_residual_sigma68": sigma68(energy_err),
                    "delay_sigma68_ns": sigma68(delay_err),
                    "timing_tail_abs_gt_15ns": float(np.mean(np.abs(delay_err) > 15.0)) if len(delay_err) else float("nan"),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "abstention_curves.csv", index=False)
    return out


def write_delay_ratio_recovery(pred: pd.DataFrame) -> pd.DataFrame:
    held = pred[(pred["split"] == "heldout") & (pred["is_overlap"] == 1) & (~pred["failed"].astype(bool))].copy()
    rows = []
    for method, group in held.groupby("method", sort=True):
        pred_delay = (group["t2_sample"] - group["t1_sample"]).to_numpy(float)
        true_delay = group["true_sep_sample"].to_numpy(float)
        pred_ratio = group["amp2_adc"].to_numpy(float) / np.maximum(group["amp1_adc"].to_numpy(float), 1.0)
        true_ratio = group["true_ratio"].to_numpy(float)
        rows.append(
            {
                "method": method,
                "n": int(len(group)),
                "delay_bias_ns": float(np.nanmedian((pred_delay - true_delay) * 10.0)),
                "delay_sigma68_ns": sigma68((pred_delay - true_delay) * 10.0),
                "amplitude_ratio_bias": float(np.nanmedian(pred_ratio - true_ratio)),
                "amplitude_ratio_sigma68": sigma68(pred_ratio - true_ratio),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "delay_ratio_recovery.csv", index=False)
    return out


def write_shuffled_overlay_controls(pred: pd.DataFrame) -> pd.DataFrame:
    held = pred[pred["split"] == "heldout"].copy()
    rng = np.random.default_rng(2559)
    rows = []
    for method, group in held.groupby("method", sort=True):
        shuffled = []
        for _, by_run in group.groupby("source_run", sort=True):
            tmp = by_run.copy()
            for col in ["is_overlap", "true_amp1_adc", "true_amp2_adc", "true_sep_sample", "true_ratio"]:
                tmp[col] = rng.permutation(tmp[col].to_numpy())
            shuffled.append(tmp)
        control = pd.concat(shuffled, ignore_index=True)
        labels = group["is_overlap"].to_numpy(int)
        shuf_labels = control["is_overlap"].to_numpy(int)
        score = np.nan_to_num(group["score"].to_numpy(float), nan=-1e9, neginf=-1e9)
        pos = control[(control["is_overlap"] == 1) & (~control["failed"].astype(bool))]
        if len(pos):
            true_e = pos[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            pred_e = pos[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            energy_err = (pred_e - true_e) / np.maximum(true_e, 1.0)
        else:
            energy_err = np.asarray([])
        rows.append(
            {
                "method": method,
                "observed_detection_ap": float(average_precision_score(labels, score)) if len(set(labels)) == 2 else float("nan"),
                "shuffled_detection_ap": float(average_precision_score(shuf_labels, score)) if len(set(shuf_labels)) == 2 else float("nan"),
                "observed_detection_auc": float(roc_auc_score(labels, score)) if len(set(labels)) == 2 else float("nan"),
                "shuffled_detection_auc": float(roc_auc_score(shuf_labels, score)) if len(set(shuf_labels)) == 2 else float("nan"),
                "shuffled_energy_residual_sigma68": sigma68(energy_err),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "shuffled_overlay_controls.csv", index=False)
    return out


def md_table(df: pd.DataFrame, cols: list[str], n: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if n is not None:
        view = view.head(n)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def postprocess_ticket_language() -> None:
    pred = pd.read_csv(OUT / "event_predictions.csv")
    abstention = write_abstention_curves(pred)
    delay_ratio = write_delay_ratio_recovery(pred)
    shuffled = write_shuffled_overlay_controls(pred)

    report_path = OUT / "REPORT.md"
    result_path = OUT / "result.json"
    manifest_path = OUT / "manifest.json"
    report = report_path.read_text(encoding="utf-8")
    replacements = {
        "# S35b: Saturation Pile-Up Energy Recovery Benchmark": "# S61b: Pile-Up Saturation Energy Recovery Bakeoff",
        "Ticket `2559` asks for a raw-ROOT reproduction followed by an academic-grade\ncomparison of energy reconstruction under clipped saturation and unresolved\npile-up.": "Ticket `2559` asks whether overlapping pulses and saturation/recovery can be separated well enough to reduce energy bias without inventing timing performance.",
        "bounded two-template deconvolution with deterministic clipping sideband correction": "amplitude-binned two-pulse template deconvolution with explicit SiPM/electronics saturation inverse and recovery-time nuisance grid",
        "as the S35b winner.": "as the S61b winner.",
    }
    for old, new in replacements.items():
        report = report.replace(old, new)
    report += f"""

## Ticket-Specific Addenda

### Delay and Amplitude-Ratio Recovery

The held-out overlap events also test whether a method recovers the generated
delay and secondary/primary amplitude ratio rather than only total energy.

{md_table(delay_ratio, ["method", "n", "delay_bias_ns", "delay_sigma68_ns", "amplitude_ratio_bias", "amplitude_ratio_sigma68"])}

### Abstention Curves

Score thresholds are swept on held-out runs.  These rows quantify the
energy/timing tradeoff when low-confidence pile-up reconstructions are
abstained rather than forced into the energy estimate.

{md_table(abstention.sort_values(["method", "score_threshold"]), ["method", "score_threshold", "accepted_fraction", "accepted_positive_fraction", "energy_residual_sigma68", "delay_sigma68_ns", "timing_tail_abs_gt_15ns"], n=60)}

### Shuffled-Overlay Control

The shuffled-overlay control permutes the overlap label and true overlay
parameters within each held-out source run, preserving run and score
distributions while breaking event-level truth alignment.  A useful pile-up
probability should lose detection skill under this control.

{md_table(shuffled, ["method", "observed_detection_ap", "shuffled_detection_ap", "observed_detection_auc", "shuffled_detection_auc", "shuffled_energy_residual_sigma68"])}

These addenda are derived only after the raw-ROOT reproduction gate and the
run-held-out fits complete.  They do not alter the registered winner score in
`result.json`.
"""
    report_path.write_text(report, encoding="utf-8")

    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "project": "testbeam",
            "worker": WORKER,
            "title": TITLE,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "claimed_ticket_text": TITLE,
        }
    )
    result["raw_root_reproduction"]["raw_root_glob"] = str(RAW_ROOT_DIR / "hrdb_run_*.root")
    result["evaluation_design"]["required_ticket_addenda"] = [
        "delay_ratio_recovery.csv",
        "abstention_curves.csv",
        "shuffled_overlay_controls.csv",
    ]
    result["required_method_coverage"]["traditional"] = (
        "analytic_clipped_template_sideband_traditional "
        "(amplitude-binned two-pulse deconvolution plus saturation/recovery nuisance correction)"
    )
    result["required_method_coverage"]["temporal_transformer"] = "tiny_sequence_transformer"
    result["winner"]["criterion"] = (
        "minimum registered S61b held-out energy-plus-pileup composite score "
        "with run-block bootstrap CIs"
    )
    result["artifacts"]["delay_ratio_recovery"] = "delay_ratio_recovery.csv"
    result["artifacts"]["abstention_curves"] = "abstention_curves.csv"
    result["artifacts"]["shuffled_overlay_controls"] = "shuffled_overlay_controls.csv"
    result["caveats"].append(
        "The required shuffled-overlay control is an event-level truth permutation within held-out source run; it tests leakage and score calibration, not a new detector acquisition mode."
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = f"{impl.sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["postprocess_note"] = "S61b ticket metadata plus delay/ratio, abstention, and shuffled-overlay addenda."
    manifest["outputs_sha256"] = {
        p.name: impl.base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    impl.TICKET = TICKET
    impl.WORKER = WORKER
    impl.TITLE = TITLE
    impl.SLUG = SLUG
    impl.OUT = OUT
    impl.RAW_ROOT_DIR = RAW_ROOT_DIR
    impl.base.RAW_ROOT_DIR = RAW_ROOT_DIR
    impl.s26b.RAW_ROOT_DIR = RAW_ROOT_DIR
    impl.s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    impl.main()
    postprocess_ticket_language()


if __name__ == "__main__":
    main()
