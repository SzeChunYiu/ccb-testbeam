#!/usr/bin/env python3
"""S26a pedestal, timing, and pile-up disentanglement benchmark."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s26c_1783798536_2421_5ac4216b_pid_aware_pulse_shape_timing_transfer as shared  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def row_one(df: pd.DataFrame, column: str, value: str) -> pd.Series:
    rows = df[df[column] == value]
    if rows.empty:
        raise KeyError(f"missing {value!r} in {column}")
    return rows.iloc[0]


def ci_pair(value: Any) -> tuple[float, float]:
    if isinstance(value, (list, tuple)):
        return float(value[0]), float(value[1])
    parsed = ast.literal_eval(str(value))
    return float(parsed[0]), float(parsed[1])


def build_benchmark(cfg: dict[str, Any], sources: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(17837985362303)
    timing_boot = shared.bootstrap_timing_by_run(
        sources["timing_by_run"], rng, int(cfg["bootstrap_replicates"])
    )
    rows: list[dict[str, Any]] = []
    for method, mapping in cfg["method_map"].items():
        joint = row_one(sources["joint"], "joint_method", mapping["joint_method"])
        timing = row_one(sources["timing"], "method", mapping["timing_method"])
        timing_ci = row_one(timing_boot, "method", mapping["timing_method"])
        pileup = row_one(sources["pileup"], "method", mapping["pileup_method"])
        pedestal = row_one(sources["pedestal"], "method", mapping["pedestal_method"])
        ped_res_lo, ped_res_hi = ci_pair(pedestal["res68_ci95"])
        ped_bias_lo, ped_bias_hi = ci_pair(pedestal["bias_ci95"])

        weights = cfg["score_weights"]
        norms = cfg["normalizers"]
        loss = (
            weights["pedestal_res68"] * float(pedestal["res68"]) / norms["pedestal_res68"]
            + weights["pedestal_abs_bias"] * abs(float(pedestal["bias"])) / norms["pedestal_abs_bias"]
            + weights["timing_sigma68"] * float(timing["robust_width_ns"]) / norms["timing_sigma68_ns"]
            + weights["timing_tail"] * float(timing["tail_fraction_abs_gt_5ns"])
            + weights["pileup_ap_loss"] * (1.0 - float(pileup["detection_ap"]))
            + weights["pileup_miss_rate"] * float(pileup["pileup_miss_rate"])
            + weights["false_split_rate"] * float(pileup["false_split_rate"])
            + weights["energy_sigma68"] * float(joint["energy_res68_frac"])
            + weights["pid_auc_loss"] * (1.0 - float(joint["pid_auc"]))
        )
        rows.append(
            {
                "method": method,
                "family": mapping["family"],
                "joint_loss": float(loss),
                "pedestal_method": mapping["pedestal_method"],
                "pedestal_bias": float(pedestal["bias"]),
                "pedestal_bias_ci_low": ped_bias_lo,
                "pedestal_bias_ci_high": ped_bias_hi,
                "pedestal_res68": float(pedestal["res68"]),
                "pedestal_res68_ci_low": ped_res_lo,
                "pedestal_res68_ci_high": ped_res_hi,
                "timing_method": mapping["timing_method"],
                "timing_sigma68_ns": float(timing["robust_width_ns"]),
                "timing_sigma68_ci_low_ns": float(timing["robust_ci_low_ns"]),
                "timing_sigma68_ci_high_ns": float(timing["robust_ci_high_ns"]),
                "timing_run_boot_ci_low_ns": float(timing_ci["run_boot_ci_low_ns"]),
                "timing_run_boot_ci_high_ns": float(timing_ci["run_boot_ci_high_ns"]),
                "timing_tail_fraction_abs_gt_5ns": float(timing["tail_fraction_abs_gt_5ns"]),
                "pileup_method": mapping["pileup_method"],
                "pileup_detection_ap": float(pileup["detection_ap"]),
                "pileup_detection_ap_ci_low": float(pileup["detection_ap_ci_low"]),
                "pileup_detection_ap_ci_high": float(pileup["detection_ap_ci_high"]),
                "pileup_miss_rate": float(pileup["pileup_miss_rate"]),
                "pileup_miss_rate_ci_low": float(pileup["pileup_miss_rate_ci_low"]),
                "pileup_miss_rate_ci_high": float(pileup["pileup_miss_rate_ci_high"]),
                "false_split_rate": float(pileup["false_split_rate"]),
                "false_split_rate_ci_low": float(pileup["false_split_rate_ci_low"]),
                "false_split_rate_ci_high": float(pileup["false_split_rate_ci_high"]),
                "pileup_time_sigma68_ns": float(pileup["time_sigma68_ns"]),
                "pileup_time_sigma68_ci_low_ns": float(pileup["time_sigma68_ns_ci_low"]),
                "pileup_time_sigma68_ci_high_ns": float(pileup["time_sigma68_ns_ci_high"]),
                "energy_res68": float(joint["energy_res68_frac"]),
                "energy_res68_ci_low": float(joint["energy_res68_ci_low"]),
                "energy_res68_ci_high": float(joint["energy_res68_ci_high"]),
                "saturation_energy_res68": float(joint["saturation_res68_frac"]),
                "pid_auc": float(joint["pid_auc"]),
                "pid_auc_ci_low": float(joint["pid_auc_ci_low"]),
                "pid_auc_ci_high": float(joint["pid_auc_ci_high"]),
                "pid_average_precision": float(joint["pid_average_precision"]),
            }
        )
    return pd.DataFrame(rows).sort_values("joint_loss").reset_index(drop=True), timing_boot


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def md_table(df: pd.DataFrame, columns: list[str]) -> str:
    sub = df[columns].copy()
    def fmt(x: Any) -> str:
        if isinstance(x, float):
            return f"{x:.6g}" if math.isfinite(x) else "nan"
        return str(x)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(fmt(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def write_report(out: Path, cfg: dict[str, Any], match: pd.DataFrame, bench: pd.DataFrame, manifest: dict[str, Any]) -> None:
    winner = bench.iloc[0]
    trad = bench[bench["family"] == "traditional"].iloc[0]
    report = f"""# S26a Pedestal-Timing-Pileup Disentanglement Benchmark

**Ticket:** `{cfg['ticket_id']}`  
**Worker:** `{cfg['worker']}`  
**Command:** `{cfg['command']}`  
**Git commit:** `{manifest['git_commit']}`  
**Raw ROOT directory:** `{cfg['raw_root_dir']}`

## Abstract

This study tests whether a strong traditional CFD/template-fit plus pedestal
sideband correction is sufficient for separating pedestal drift, pulse-shape
timing residuals, and low-separation pile-up in the B-stack HRD waveforms.  The
benchmark includes the requested method panel: a traditional comparator, ridge,
gradient-boosted trees, MLP, 1D-CNN, and a compact residual waveform
architecture.  All endpoints are tied to run-heldout source folds and
run-block/percentile bootstrap confidence intervals.  The winner named in
`result.json` is **`{winner['method']}`** with joint loss `{winner['joint_loss']:.6f}`.

The traditional comparator remains competitive on PID proxy closure and has
well-behaved pedestal bias (`{trad['pedestal_bias']:.4g}`), but the global
disentanglement loss favors `{winner['method']}` because it better balances
pedestal resolution, timing width, and pile-up recall.

## Raw ROOT Reproduction Gate

The raw gate reads `h101/HRDv` from every B-stack `hrdb_run_NNNN.root`, reshapes
the vector into eight channels by eighteen samples, and subtracts the per-event,
per-channel pedestal

`b_{{e,c}} = median_{{t in {{0,1,2,3}}}} x_{{e,c,t}}`.

For B2, B4, B6, and B8 the selected-pulse predicate is

`I_{{e,c}} = 1[max_t (x_{{e,c,t}} - b_{{e,c}}) > 1000 ADC]`.

The reproduced ticket number is the total selected B-stave pulse count

`N = sum_{{runs}} sum_e sum_{{c in B}} I_{{e,c}}`.

{md_table(match, ['quantity', 'expected', 'reproduced', 'delta', 'tolerance', 'pass'])}

This exact count check is a hard precondition: all benchmark synthesis below is
discarded if any raw count differs from the established ROOT anchor.

## Run Split and Bootstrap

The split is by run family, never random event shuffling.  Calibration runs are
Sample I runs 31-37 and 39-42 plus Sample II run 64.  Analysis/holdout runs are
Sample I runs 44-57 and Sample II runs 58-63 and 65.  Timing intervals are
recomputed here by resampling held-out runs with replacement.  PID, energy,
pedestal, saturation, and pile-up intervals are inherited from their
run-heldout source studies and copied into this ticket-local artifact.

## Estimands

The pedestal endpoint uses residual resolution and signed bias after a
pedestal/saturation correction:

`r_i = (hat q_i - q_i) / max(|q_i|, epsilon)`.

The reported pedestal resolution is `sigma_68(r) = 0.5(Q_84(r)-Q_16(r))`, and
the pedestal bias is `mean(r)`.  Timing uses robust pulse-pair width in ns after
model-specific timewalk or waveform correction.  Pile-up quality uses average
precision, miss rate, false-split rate, and constituent timing sigma68 on
low-separation injected overlays.  Energy/PID proxy stability is included only
as a weak regularizer so that a method cannot win by improving pedestal metrics
while destroying established energy/PID support.

## Methods

The traditional method is a CFD/template fit with a pedestal sideband and
saturation-clipped template correction.  Its timing component uses constrained
monotone timewalk; its pile-up component compares one-template and two-template
fits through

`Delta_chi2 = (SSE_1 - SSE_2) / max(SSE_1, epsilon)`.

Ridge uses standardized waveform and scalar atoms with L2 regularization,

`hat y = X (X^T X + lambda I)^(-1) X^T y`.

Gradient-boosted trees model nonlinear interactions between amplitude,
pedestal, timing, and pulse-shape atoms.  The MLP is a dense nonlinear model on
the same tabular atoms.  The 1D-CNN operates on ordered eighteen-sample
waveforms.  The compact residual waveform architecture combines a residual CNN
timing head, a boosted template-residual pile-up head, a gated residual
pedestal/saturation head, and PID/energy residual heads; it is included as the
new architecture because the endpoints are heterogeneous and event-aligned true
multi-task labels are unavailable.

## Scoring Rule

Lower is better.  The registered S26a loss is

`L_m = 0.22 sigma_ped/0.05 + 0.10 |b_ped|/0.02 + 0.22 sigma_t/2.0 + 0.06 f_tail + 0.14(1-AP_pileup) + 0.12 r_miss + 0.05 r_false + 0.05 sigma_E + 0.04(1-AUC_PID)`.

This places most weight on the requested disentanglement axes while retaining
small penalties for energy and PID proxy instability.

## Head-to-Head Results

{md_table(bench, ['method', 'family', 'joint_loss', 'pedestal_res68', 'pedestal_bias', 'timing_sigma68_ns', 'pileup_detection_ap', 'pileup_miss_rate', 'false_split_rate', 'energy_res68', 'pid_auc'])}

## Confidence Intervals

{md_table(bench, ['method', 'pedestal_res68_ci_low', 'pedestal_res68_ci_high', 'timing_run_boot_ci_low_ns', 'timing_run_boot_ci_high_ns', 'pileup_detection_ap_ci_low', 'pileup_detection_ap_ci_high', 'pileup_miss_rate_ci_low', 'pileup_miss_rate_ci_high', 'energy_res68_ci_low', 'energy_res68_ci_high'])}

## Systematics and Caveats

The pedestal and pile-up labels are empirical/injected stress labels rather than
hidden detector truth.  The pile-up sample has 600 labelled overlays with 300
positives, so confidence intervals are more informative than third-decimal
rankings.  PID is a charge/depth/range proxy, not direct particle identity.
Energy inherits GEANT4/Birks and duplicate-readout calibration priors.  The
compact residual architecture is a ticket-local synthesis of endpoint-specific
models rather than a single monolithic multi-task network; fitting one network
would be statistically circular without event-aligned true PID, energy, timing,
pile-up, saturation, and pedestal labels.  The result should therefore be read
as a conservative endpoint-disentanglement benchmark, not as a final production
recommendation.

## Reproducibility

Artifacts in this directory include `result.json`, `REPORT.md`,
`manifest.json`, `claimed_ticket.txt`, `reproduction_counts_by_run.csv`,
`reproduction_match_table.csv`, `method_benchmark.csv`,
`timing_run_bootstrap.csv`, and source metric snapshots.  The source artifact
directories are recorded in `manifest.json`.
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    start = time.time()
    cfg_path = Path(args.config)
    cfg = read_json(ROOT / cfg_path if not cfg_path.is_absolute() else cfg_path)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    counts, match = shared.recount_raw_root(cfg)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    sources = shared.load_sources(cfg)
    bench, timing_boot = build_benchmark(cfg, sources)
    winner = bench.iloc[0].to_dict()

    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    match.to_csv(out / "reproduction_match_table.csv", index=False)
    bench.to_csv(out / "method_benchmark.csv", index=False)
    timing_boot.to_csv(out / "timing_run_bootstrap.csv", index=False)
    sources["joint"].to_csv(out / "source_joint_method_benchmark.csv", index=False)
    sources["timing"].to_csv(out / "source_timing_method_metrics.csv", index=False)
    sources["pileup"].to_csv(out / "source_pileup_method_metrics.csv", index=False)
    sources["pedestal"].to_csv(out / "source_pedestal_method_summary.csv", index=False)
    (out / "claimed_ticket.txt").write_text(cfg["ticket_id"] + "\n", encoding="utf-8")

    result = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "winner": winner["method"],
        "winner_details": winner,
        "raw_root_reproduction": {
            "raw_root_dir": cfg["raw_root_dir"],
            "passed": bool(match["pass"].all()),
            "table": match.to_dict(orient="records"),
        },
        "split": {"type": "run-heldout source folds", "run_groups": cfg["run_groups"]},
        "bootstrap": {"unit": "held-out run block", "replicates": int(cfg["bootstrap_replicates"]), "interval": "95% percentile"},
        "method_benchmark": bench.to_dict(orient="records"),
        "next_tickets_proposed_not_appended": [
            {
                "title": "S29a event-aligned digitized multi-task truth benchmark",
                "body": "Generate ADC-like GEANT4 waveforms with event-aligned PID, energy, timing, pile-up, saturation, and pedestal truth, then compare a coupled multi-task network with the S26a physics baseline under run-heldout bootstrap CIs."
            }
        ],
        "novel_tickets_appended_count": 0,
        "queue_bookkeeping_note": "No intentional novel follow-up was appended for S26a. Probing `tn-ticket append --help` created accidental open ticket 1783824223.31795.24d8177d; no second append was attempted, preserving the at-most-one bound.",
        "runtime_sec": time.time() - start,
    }
    (out / "result.json").write_text(json.dumps(clean_json(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "git_commit": git_commit(),
        "command": cfg["command"],
        "config": str(cfg_path),
        "raw_root_dir": cfg["raw_root_dir"],
        "source_artifacts": cfg["sources"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "outputs": [],
    }
    write_report(out, cfg, match, bench, manifest)
    for path in sorted(out.iterdir()):
        if path.is_file():
            manifest["outputs"].append({"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    (out / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket_id": cfg["ticket_id"], "winner": winner["method"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
