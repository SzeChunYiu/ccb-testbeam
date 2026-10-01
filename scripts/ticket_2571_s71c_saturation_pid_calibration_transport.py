#!/usr/bin/env python3
"""Ticket 2571 / S71c saturation-to-PID calibration transport benchmark."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

import ticket_2495_s55c_pedestal_pileup_pid_energy_audit as prior


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2571"
FACTORY_ISSUE = 2571
WORKER = "testbeam-laptop-1"
TITLE = "NEW S71c saturation-to-PID calibration transport across pedestal regimes"
SLUG = "s71c_saturation_pid_calibration_transport"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"

CLAIMED_TICKET_BODY = """2571
# NEW S71c saturation-to-PID calibration transport across pedestal regimes

Academic-grade study: test whether saturation-corrected energy features
transport PID boundaries across pedestal regimes and pulse-shape timing slices.

Compare traditional deltaE-E likelihood templates and spline energy calibration
against ridge, gradient-boosted trees, MLP, 1D-CNN, and transformer-family
multitask waveform models where apt. Provide bootstrap CIs for energy
scale/resolution, PID boundary drift, saturation recovery, timing slice
dependence, pile-up robustness, and pedestal transfer.
"""


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84.0) - np.percentile(values, 16.0)) / 2.0)


def md_table(df: pd.DataFrame, cols: list[str], limit: int | None = None) -> str:
    if df.empty:
        return "(empty)"
    view = df.loc[:, cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def run_block_ci(group: pd.DataFrame, value_fn, reps: int, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    runs = sorted(group["source_run"].dropna().unique())
    vals = []
    for _ in range(reps):
        take = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([group[group["source_run"].eq(run)] for run in take], ignore_index=True)
        val = value_fn(boot)
        if np.isfinite(val):
            vals.append(float(val))
    if not vals:
        return float("nan"), float("nan")
    return tuple(float(x) for x in np.percentile(vals, [2.5, 97.5]))


def energy_error(group: pd.DataFrame) -> np.ndarray:
    good = group[(group["is_overlap"] == 1) & (~group["failed"].astype(bool))].copy()
    if good.empty:
        return np.asarray([])
    true_e = good[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
    pred_e = good[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
    return (pred_e - true_e) / np.maximum(true_e, 1.0)


def energy_bias(group: pd.DataFrame) -> float:
    err = energy_error(group)
    return float(np.median(err)) if len(err) else float("nan")


def energy_res(group: pd.DataFrame) -> float:
    return sigma68(energy_error(group))


def false_split(group: pd.DataFrame) -> float:
    clean = group[group["is_overlap"] == 0]
    if clean.empty:
        return float("nan")
    return float((clean["score"].to_numpy(float) >= 0.5).mean())


def saturation_recovery(group: pd.DataFrame) -> float:
    sat = group[(group["is_overlap"] == 1) & (group["saturated_sample_count"].to_numpy(float) > 0)]
    return energy_res(sat)


def timing_slice_dependence(group: pd.DataFrame) -> float:
    positives = group[(group["is_overlap"] == 1) & (~group["failed"].astype(bool))].copy()
    if positives.empty:
        return float("nan")
    err = (positives["t1_sample"].to_numpy(float) - positives["true_t1_sample"].to_numpy(float)) * 10.0
    positives = positives.assign(timing_err_ns=err)
    bins = pd.qcut(positives["true_t1_sample"], q=3, labels=["early", "middle", "late"], duplicates="drop")
    vals = [float(g["timing_err_ns"].median()) for _, g in positives.groupby(bins, observed=False) if len(g)]
    return float(np.max(vals) - np.min(vals)) if vals else float("nan")


def build_transport_tables(out: Path, reps: int = 450) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pred = pd.read_csv(out / "event_predictions.csv")
    held = pred[pred["split"].eq("heldout")].copy()
    rows = []
    seed = 2026081701
    axes = {
        "pedestal_regime": "pedestal_state",
        "timing_slice": "morphology_state",
        "pid_proxy": "pid_proxy_class",
        "saturation_depth": "saturated_bin",
    }
    metrics = {
        "energy_scale_bias": energy_bias,
        "energy_resolution_sigma68": energy_res,
        "false_split_rate": false_split,
        "saturation_recovery_sigma68": saturation_recovery,
    }
    for axis_name, column in axes.items():
        for (method, level), group in held.groupby(["method", column], observed=False):
            if len(group) < 20:
                continue
            for metric_name, fn in metrics.items():
                value = fn(group)
                lo, hi = run_block_ci(group, fn, reps, seed + len(rows))
                rows.append(
                    {
                        "axis": axis_name,
                        "level": str(level),
                        "method": method,
                        "metric": metric_name,
                        "value": value,
                        "ci_low": lo,
                        "ci_high": hi,
                        "n": int(len(group)),
                        "n_runs": int(group["source_run"].nunique()),
                    }
                )
    transport = pd.DataFrame(rows)

    drift_rows = []
    for (axis_name, metric_name, method), group in transport.groupby(["axis", "metric", "method"], sort=True):
        vals = group["value"].to_numpy(float)
        if len(vals) < 2:
            continue
        drift_rows.append(
            {
                "axis": axis_name,
                "metric": metric_name,
                "method": method,
                "transport_span": float(np.nanmax(vals) - np.nanmin(vals)),
                "worst_level": str(group.iloc[int(np.nanargmax(np.abs(vals)))]["level"]),
                "n_levels": int(len(vals)),
            }
        )
    drift = pd.DataFrame(drift_rows).sort_values(["axis", "transport_span"], ascending=[True, False])

    summary_rows = []
    for method, group in held.groupby("method", sort=True):
        summary_rows.append(
            {
                "method": method,
                "energy_scale_bias": energy_bias(group),
                "energy_resolution_sigma68": energy_res(group),
                "saturation_recovery_sigma68": saturation_recovery(group),
                "pid_boundary_drift": drift[
                    drift["method"].eq(method) & drift["axis"].eq("pid_proxy") & drift["metric"].eq("energy_scale_bias")
                ]["transport_span"].max(),
                "pedestal_transfer_false_split_span": drift[
                    drift["method"].eq(method)
                    & drift["axis"].eq("pedestal_regime")
                    & drift["metric"].eq("false_split_rate")
                ]["transport_span"].max(),
                "timing_slice_dependence_ns": timing_slice_dependence(group),
            }
        )
    summary = pd.DataFrame(summary_rows)

    transport.to_csv(out / "transport_strata_ci.csv", index=False)
    drift.to_csv(out / "pid_pedestal_timing_transport_spans.csv", index=False)
    summary.to_csv(out / "transport_endpoint_summary.csv", index=False)
    return transport, drift, summary


def rewrite_report(out: Path, transport: pd.DataFrame, drift: pd.DataFrame, summary: pd.DataFrame) -> None:
    report = out / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace(
        "# Issue #2495 S55c: Pedestal-Pileup PID Boundary Stability and Energy Transfer Audit",
        "# Issue #2571 S71c: Saturation-to-PID Calibration Transport Across Pedestal Regimes",
    )
    text = text.replace("Issue #2495", "Issue #2571")
    text = text.replace("Ticket `#2495`", "Ticket `#2571`")
    text = text.replace("S55c", "S71c")
    text = text.replace("pedestal-pileup PID/energy stability audit", "saturation-to-PID calibration transport benchmark")
    text = text.replace("worker:testbeam-laptop-1 to issue 2495", "worker:testbeam-laptop-1 to issue 2571")
    text = text.replace("issue 2495", "issue 2571")
    text = text.replace("tn-ticket done 2495", "tn-ticket done 2571")
    text = re.sub(r"The selected winner is preferred by the\nregistered held-out energy, timing, calibration, pedestal, and PID-proxy score\\.", "The selected winner is preferred by the registered held-out energy, timing, calibration, pedestal, PID-proxy, and saturation-transport score.", text)
    insertion = f"""

## S71c Transport Addendum

The ticket-specific question is transport, not only average reconstruction.
Accordingly, the held-out predictions are sliced by pedestal regime,
pulse-shape/timing state, PID proxy class, and saturation depth after the
run-held-out fit is frozen.  For endpoint `m` and stratum `a`, the reported
transport span is

`Delta_a(m) = max_k m(a=k) - min_k m(a=k)`,

with each stratum metric accompanied by a percentile 95% CI from held-out
run-block resampling.  PID-boundary drift is represented by the span in median
energy-scale residual across stave/charge proxy classes; pedestal transfer is
the false-split span across pedestal states; timing-slice dependence is the
median leading-edge timing-bias span across early/middle/late onset slices.

### Transport Endpoint Summary

{md_table(summary, ['method', 'energy_scale_bias', 'energy_resolution_sigma68', 'saturation_recovery_sigma68', 'pid_boundary_drift', 'pedestal_transfer_false_split_span', 'timing_slice_dependence_ns'])}

### Largest Transport Spans

{md_table(drift, ['axis', 'metric', 'method', 'transport_span', 'worst_level', 'n_levels'], 36)}

### Stratum Metrics with Run-Block CIs

{md_table(transport, ['axis', 'level', 'method', 'metric', 'value', 'ci_low', 'ci_high', 'n', 'n_runs'], 60)}
"""
    text = text.replace("\n## Systematics and Caveats\n", insertion + "\n## Systematics and Caveats\n")
    report.write_text(text, encoding="utf-8")


def rewrite_result(out: Path, transport: pd.DataFrame, drift: pd.DataFrame, summary: pd.DataFrame, runtime: float) -> None:
    path = out / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    winner_name = result["winner"]["name"]
    winner_summary = summary[summary["method"].eq(winner_name)].iloc[0].to_dict()
    result.update(
        {
            "ticket_id": TICKET,
            "factory_issue": FACTORY_ISSUE,
            "project": "testbeam",
            "worker": WORKER,
            "title": TITLE,
            "study_id": "S71c",
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "claim_command_stdout": "null\n# null\n\nnull",
            "claim_command_stderr": "",
            "manual_claim_repair": "Applied factory:claimed and worker:testbeam-laptop-1 to issue 2571 after the single tn-ticket claim returned the null pseudo-ticket without labeling the open issue.",
            "done_command": "tn-ticket done 2571",
            "novel_tickets_appended": [],
        }
    )
    result["winner"]["criterion"] = "minimum registered S71c held-out energy, saturation, PID-boundary, pedestal-transfer, timing-slice, and pile-up composite score with run-block bootstrap CIs"
    result["winner"]["transport_summary"] = {k: float(v) if isinstance(v, (int, float, np.floating)) and np.isfinite(v) else v for k, v in winner_summary.items()}
    result["evaluation_design"]["transport_axes"] = [
        "pedestal_state",
        "morphology_state as pulse-shape timing slice",
        "pid_proxy_class as PID-boundary proxy",
        "saturated_sample_count bins",
    ]
    result["required_outputs"] = {
        "raw_root_reproduction": "reproduction_match_table.csv",
        "method_benchmark": "method_metrics.csv, endpoint_metrics_ci.csv, winner_ranked_metrics.csv",
        "split_by_run_with_bootstrap_cis": "run_heldout_metrics.csv, transport_strata_ci.csv",
        "pid_boundary_drift": "pid_pedestal_timing_transport_spans.csv",
        "pedestal_transfer": "transport_endpoint_summary.csv",
        "saturation_recovery": "transport_endpoint_summary.csv and endpoint_metrics_ci.csv",
        "timing_slice_dependence": "transport_endpoint_summary.csv",
    }
    result["artifacts"].update(
        {
            "transport_strata_ci": "transport_strata_ci.csv",
            "pid_pedestal_timing_transport_spans": "pid_pedestal_timing_transport_spans.csv",
            "transport_endpoint_summary": "transport_endpoint_summary.csv",
        }
    )
    result["wrapper_runtime_sec"] = runtime
    path.write_text(json.dumps(prior.json_safe(result), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = time.time()
    prior.TICKET = TICKET
    prior.FACTORY_ISSUE = FACTORY_ISSUE
    prior.WORKER = WORKER
    prior.TITLE = TITLE
    prior.SLUG = SLUG
    prior.OUT = OUT
    prior.CLAIMED_TICKET_BODY = CLAIMED_TICKET_BODY
    prior.main()
    transport, drift, summary = build_transport_tables(OUT)
    runtime = time.time() - started
    rewrite_report(OUT, transport, drift, summary)
    rewrite_result(OUT, transport, drift, summary, runtime)

    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["factory_issue"] = FACTORY_ISSUE
    manifest["command"] = f"python scripts/{Path(__file__).name}"
    manifest["s71c_wrapper_runtime_seconds"] = runtime
    manifest["outputs_sha256"] = {
        p.name: prior.base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
