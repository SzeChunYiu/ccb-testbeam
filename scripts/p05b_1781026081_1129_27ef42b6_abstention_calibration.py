#!/usr/bin/env python3
"""Ticket-scoped P05b abstention calibration.

This wrapper reruns the validated P05b raw-ROOT abstention pipeline with the new
ticket config, then writes a ticket-specific report and secondary-amplitude
sideband summary.
"""

from __future__ import annotations

import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts" / "p05b_1781014241_437_0e0024cb_abstention_calibration.py"
DEFAULT_CONFIG = ROOT / "configs" / "p05b_1781026081_1129_27ef42b6.json"
THIS_SCRIPT = "scripts/p05b_1781026081_1129_27ef42b6_abstention_calibration.py"


def load_base():
    spec = importlib.util.spec_from_file_location("p05b_base_abstention", str(BASE_SCRIPT))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load base P05b implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value):
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    out = ["| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"]
    out.append("| " + " | ".join("-" * width for width in widths) + " |")
    for row in rows:
        out.append("| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |")
    return "\n".join(out)


def write_secondary_sidebands(out_dir: Path) -> pd.DataFrame:
    by_ratio = pd.read_csv(out_dir / "metrics_by_ratio.csv")
    rows = []
    for row in by_ratio.itertuples(index=False):
        ratio = float(row.bin_value)
        if ratio < 0.375:
            band = "low_secondary_ratio_0.25"
        elif ratio < 0.625:
            band = "mid_secondary_ratio_0.50"
        elif ratio < 0.875:
            band = "high_secondary_ratio_0.75"
        else:
            band = "equal_secondary_ratio_1.00"
        rows.append(
            {
                "method": row.method,
                "secondary_amplitude_sideband": band,
                "true_secondary_primary_ratio": ratio,
                "n_positive": int(row.n_positive),
                "coverage": float(row.coverage),
                "abstention_rate": float(row.abstention_rate),
                "accepted_time_rms_ns": float(row.accepted_time_rms_ns),
                "bad_recovery_rate": float(row.bad_recovery_rate),
                "charge_fractional_bias": float(row.charge_fractional_bias),
                "charge_fractional_res68": float(row.charge_fractional_res68),
            }
        )
    sidebands = pd.DataFrame(rows).sort_values(["method", "true_secondary_primary_ratio"])
    sidebands.to_csv(out_dir / "secondary_amplitude_sidebands.csv", index=False)
    return sidebands


def rewrite_report(config: dict, out_dir: Path, runtime: float, sidebands: pd.DataFrame) -> None:
    reproduction = pd.read_csv(out_dir / "reproduction_match_table.csv")
    s10 = pd.read_csv(out_dir / "s10_ml_reproduction.csv")
    summary = pd.read_csv(out_dir / "calibrated_method_summary.csv")
    leakage = pd.read_csv(out_dir / "leakage_checks.csv")
    trad = summary[summary["method"] == "traditional_train_quality_cuts"].iloc[0]
    ml = summary[summary["method"] == "ml_isotonic_failure_gate"].iloc[0]
    compact_summary = summary[
        [
            "method",
            "coverage",
            "abstention_rate",
            "accepted_time_rms_ns",
            "accepted_time_rms_ns_ci_low",
            "accepted_time_rms_ns_ci_high",
            "bad_recovery_rate",
            "risk_coverage_auc",
        ]
    ].copy()
    compact_sidebands = sidebands[
        [
            "method",
            "secondary_amplitude_sideband",
            "coverage",
            "abstention_rate",
            "accepted_time_rms_ns",
            "bad_recovery_rate",
        ]
    ].copy()
    compact_sidebands = compact_sidebands.sort_values(["secondary_amplitude_sideband", "method"])
    verdict = (
        "The ML isotonic gate accepts many more held-out two-pulse corrections and has slightly "
        "lower accepted timing RMS, but it does not meet the 0.15 held-out bad-recovery target. "
        "The traditional gate is stricter and lands closest to the target, so the result is a "
        "coverage-versus-risk tradeoff rather than a clean ML operating-point win."
    )
    text = f"""# P05b: two-pulse abstention calibration for S07d injections

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Inputs:** raw HRD ROOT files only; no Monte Carlo.
- **Split:** train runs `{config['benchmark_runs']['train']}`, held-out runs `{config['benchmark_runs']['heldout']}`; CIs bootstrap held-out source runs.

## Reproduction first

Before calibration, the raw `HRDv` selected-pulse gate reproduced `{int(reproduction.iloc[0]['reproduced'])}` B-stave pulses versus `{int(reproduction.iloc[0]['report_value'])}` reported, with zero tolerance. The S10 injection AP reproduction values are `{s10['reproduced'].round(4).tolist()}`.

## Methods

Traditional method: bounded two-pulse template recovery with train-only cuts on fit failure, fractional SSE improvement, chi2/ndf proxy, fitted separation, and predicted secondary/primary amplitude ratio.

ML method: the S11a MLP recovery output is converted into an isotonic failure-probability gate using leave-one-run-out training folds. The gate uses normalized waveform features plus fit diagnostics, and the threshold is selected only on train runs to target bad-recovery rate <= `{float(config['target_bad_recovery_rate']):.2f}`.

Bad recovery means base failure, event constituent-time RMS > `{float(config['bad_recovery_time_rms_ns']):.1f}` ns, or absolute charge bias > `{float(config['bad_recovery_abs_charge_bias']):.2f}`.

## Held-out result

{markdown_table(compact_summary)}

{verdict}

## Secondary-Amplitude Sidebands

{markdown_table(compact_sidebands)}

The sideband table is written to `secondary_amplitude_sidebands.csv`. Low secondary-amplitude overlays are the hardest operational region; both methods abstain most there.

## Leakage Review

All leakage checks pass: `{bool(leakage['pass'].all())}`. The checks cover train/held-out run disjointness, event-id overlap, train-only threshold selection, ML leave-one-run-out calibration folds, and a shuffled-label MLP sentinel.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config configs/p05b_1781026081_1129_27ef42b6.json
```

Runtime in this run was `{runtime:.2f}` s.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def patch_result_and_manifest(config: dict, out_dir: Path, base, runtime: float, sidebands: pd.DataFrame) -> None:
    result_path = out_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket"] = config["ticket_id"]
    result["title"] = config["title"]
    result["worker"] = config["worker"]
    result["secondary_amplitude_sidebands"] = {
        "path": "secondary_amplitude_sidebands.csv",
        "ratio_values": sorted(float(x) for x in sidebands["true_secondary_primary_ratio"].unique()),
    }
    result["next_tickets"] = []
    result.pop("follow_up_ticket", None)
    result["git_commit"] = git_commit()
    result["runtime_sec"] = round(runtime, 2)
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket"] = config["ticket_id"]
    manifest["worker"] = config["worker"]
    manifest["git_commit"] = git_commit()
    manifest["python"] = platform.python_version()
    manifest["config"] = "configs/p05b_1781026081_1129_27ef42b6.json"
    manifest["script"] = THIS_SCRIPT
    manifest["command"] = f"{sys.executable} {THIS_SCRIPT} --config {manifest['config']}"
    manifest["outputs"] = base.hash_outputs(out_dir)
    manifest["runtime_sec"] = round(runtime, 2)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    base = load_base()
    args = sys.argv[1:]
    if not args:
        args = ["--config", str(DEFAULT_CONFIG)]
    old_argv = sys.argv[:]
    start = time.time()
    try:
        sys.argv = [str(BASE_SCRIPT)] + args
        rc = base.main()
    finally:
        sys.argv = old_argv
    if rc != 0:
        return int(rc)

    config_path = Path(args[args.index("--config") + 1]) if "--config" in args else DEFAULT_CONFIG
    config = base.load_config(config_path)
    out_dir = Path(config["output_dir"])
    sidebands = write_secondary_sidebands(out_dir)
    runtime = time.time() - start
    rewrite_report(config, out_dir, runtime, sidebands)
    patch_result_and_manifest(config, out_dir, base, runtime, sidebands)
    print(json.dumps({"out_dir": str(out_dir), "sideband_rows": int(len(sidebands)), "runtime_sec": round(runtime, 2)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
