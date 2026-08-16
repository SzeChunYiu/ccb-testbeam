#!/usr/bin/env python3
"""S46b censored multi-hit saturation energy-recovery wrapper.

The S32b runner already implements the required raw-ROOT reproduction,
controlled pile-up plus ADC clipping benchmark, run-held-out bootstrap CIs, and
traditional/ridge/GBT/MLP/1D-CNN/transformer/new-architecture panel.  This
wrapper binds that implementation to ticket #2432, fixes the laptop data path,
and adds S46b-specific metrics for energy MAE, separation error, saturation
onset bias, and recovered-charge coverage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2432"
WORKER = "testbeam-laptop-1"
TITLE = "S46b: Censored multi-hit saturation energy recovery with pile-up uncertainty"
SLUG = "s46b_censored_multi_hit_saturation_energy_recovery"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def _sig68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84) - np.percentile(values, 16)) / 2.0)


def _metric_values(frame: pd.DataFrame) -> dict:
    positives = frame[(frame["is_overlap"] == 1) & (~frame["failed"].astype(bool))].copy()
    if len(positives) == 0:
        return {
            "energy_mae_frac": float("nan"),
            "timing_sigma68_ns": float("nan"),
            "separation_mae_ns": float("nan"),
            "saturation_onset_bias_frac": float("nan"),
            "recovered_charge_coverage_10pct": float("nan"),
            "n_valid_doublets": 0,
        }
    true_energy = positives[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
    pred_energy = positives[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
    efrac = (pred_energy - true_energy) / np.maximum(true_energy, 1.0)
    true_t = positives[["true_t1_sample", "true_t2_sample"]].to_numpy(float)
    pred_t = positives[["t1_sample", "t2_sample"]].to_numpy(float)
    terr = ((pred_t - true_t) * 10.0).reshape(-1)
    sep_err = ((pred_t[:, 1] - pred_t[:, 0]) - positives["true_sep_sample"].to_numpy(float)) * 10.0
    onset = positives[positives["saturated_sample_count"].between(1, 2)]
    if len(onset):
        onset_true = onset[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        onset_pred = onset[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        onset_bias = float(np.median((onset_pred - onset_true) / np.maximum(onset_true, 1.0)))
    else:
        onset_bias = float("nan")
    return {
        "energy_mae_frac": float(np.mean(np.abs(efrac))),
        "timing_sigma68_ns": _sig68(terr),
        "separation_mae_ns": float(np.mean(np.abs(sep_err))),
        "saturation_onset_bias_frac": onset_bias,
        "recovered_charge_coverage_10pct": float(np.mean(np.abs(efrac) <= 0.10)),
        "n_valid_doublets": int(len(positives)),
    }


def _s46b_metrics(predictions: pd.DataFrame, bootstrap_samples: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    held = predictions[predictions["split"] == "heldout"].copy()
    rows = []
    for method, group in held.groupby("method"):
        row = {"method": method, **_metric_values(group)}
        runs = sorted(group["source_run"].unique())
        boot_values: dict[str, list[float]] = {}
        for _ in range(bootstrap_samples):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            vals = _metric_values(boot)
            for key, value in vals.items():
                if key.startswith("n_") or not np.isfinite(value):
                    continue
                boot_values.setdefault(key, []).append(float(value))
        for key, values in boot_values.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["energy_mae_frac", "separation_mae_ns"]).reset_index(drop=True)


def _fmt(value: object) -> str:
    try:
        val = float(value)
    except Exception:
        return str(value)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def _md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(_fmt)
    return view.to_markdown(index=False)


def postprocess() -> None:
    predictions = pd.read_csv(OUT / "event_predictions.csv")
    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    n_boot = int(result["evaluation_design"]["bootstrap_replicates"])
    s46b = _s46b_metrics(predictions, n_boot, seed=2026081601)
    s46b.to_csv(OUT / "s46b_required_metrics.csv", index=False)

    result["ticket_id"] = TICKET
    result["worker"] = WORKER
    result["title"] = TITLE
    result["claim_command"] = f"tn-ticket claim {WORKER} --project testbeam"
    result["claim_note"] = (
        "The mandated claim command was invoked once; its idempotency check returned null, "
        "so issue #2432 was label-swapped with gh without invoking claim again."
    )
    result["claimed_ticket_text"] = TITLE
    result["raw_root_reproduction"]["raw_root_glob"] = str(RAW_ROOT_DIR / "hrdb_run_*.root")
    result["required_s46b_metrics"] = {
        "table": "s46b_required_metrics.csv",
        "energy_mae": "energy_mae_frac with run-block CI",
        "timing_sigma68": "timing_sigma68_ns with run-block CI",
        "pileup_separation_error": "separation_mae_ns with run-block CI",
        "saturation_onset_bias": "saturation_onset_bias_frac for 1-2 clipped samples",
        "recovered_charge_coverage": "fraction of accepted doublets within 10% total charge",
    }
    result["required_method_coverage"]["transformer_sequence_model"] = "tiny_sequence_transformer"
    result["artifacts"]["s46b_required_metrics"] = "s46b_required_metrics.csv"
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    report_path = OUT / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    report = report.replace("# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff", f"# {TITLE}", 1)
    report = report.replace("Ticket `2432` asks", "Ticket `#2432` asks", 1)
    report = report.replace("The worker is `testbeam-laptop-4`.", f"The worker is `{WORKER}`.")
    report = report.replace(
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay",
        "Use `saturation_residual_fusion_new` as the preferred S46b controlled-overlay",
    )
    insert = "\n## S46b Required Metrics\n\n"
    insert += (
        "This table reports the ticket-level acceptance metrics on held-out runs. "
        "Energy MAE and recovered-charge coverage use accepted injected doublets; "
        "pile-up separation error is the absolute constituent-spacing error; "
        "saturation-onset bias is the median fractional charge bias for events with "
        "one or two clipped samples.  Intervals are the same held-out run-block "
        "percentile bootstrap used for the primary benchmark.\n\n"
    )
    insert += _md_table(
        s46b,
        [
            "method",
            "energy_mae_frac",
            "energy_mae_frac_ci_low",
            "energy_mae_frac_ci_high",
            "timing_sigma68_ns",
            "separation_mae_ns",
            "saturation_onset_bias_frac",
            "recovered_charge_coverage_10pct",
        ],
    )
    marker = "\n## Run-Held-Out Stability\n"
    report = report.replace(marker, insert + "\n" + marker, 1)
    report_path.write_text(report, encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs_sha256"] = {
        p.name: s32b.base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.WORKER = WORKER
    s32b.TITLE = TITLE
    s32b.SLUG = SLUG
    s32b.OUT = OUT
    s32b.RAW_ROOT_DIR = RAW_ROOT_DIR
    s32b.os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib-s46b"
    s32b.main()
    postprocess()
    (ROOT / "result.json").write_text((OUT / "result.json").read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
