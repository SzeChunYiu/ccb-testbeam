#!/usr/bin/env python3
"""S29b saturation-pedestal energy recovery frontier.

This ticket-local runner reuses the validated raw-ROOT reproduction and
architecture bakeoff path from the S26b frontier study, but writes independent
S29b artifacts and adds endpoint-level tables named in the ticket: pile-up
separation, saturation recovery, pedestal robustness, energy closure,
pulse-shape residuals, and PID boundary shifts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s26b_1783805896_7017_69544aca_pileup_saturation_recovery_frontier as runner  # noqa: E402


TICKET = "1783823997.52190.04e85489"
WORKER = "testbeam-laptop-1"
SLUG = "s29b_saturation_pedestal_energy_recovery_frontier"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
TITLE = "S29b saturation-pedestal energy recovery frontier"


_original_load_config = runner.load_config


def load_config() -> dict:
    cfg = _original_load_config()
    cfg.update(
        {
            "study_id": "S29b",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "output_dir": str(OUT),
            "random_seed": 2026071205,
        }
    )
    return cfg


def _ci(values: pd.Series) -> str:
    lo = values.get(values.name + "_ci_low", np.nan)
    hi = values.get(values.name + "_ci_high", np.nan)
    val = values.get(values.name, np.nan)
    if not np.isfinite(val):
        return "nan"
    if np.isfinite(lo) and np.isfinite(hi):
        return f"{val:.4g} [{lo:.4g}, {hi:.4g}]"
    return f"{val:.4g}"


def _format_float(x: object) -> str:
    try:
        y = float(x)
    except Exception:
        return str(x)
    return f"{y:.4g}" if np.isfinite(y) else "nan"


def md_table(df: pd.DataFrame, columns: list[str]) -> str:
    view = df.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(_format_float)
    return view.to_markdown(index=False)


def endpoint_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = pd.read_csv(OUT / "method_metrics.csv")
    strata = pd.read_csv(OUT / "strata_metrics.csv")
    events = pd.read_csv(OUT / "event_predictions.csv")

    rows = []
    for row in metrics.to_dict("records"):
        s = pd.Series(row)
        rows.extend(
            [
                {
                    "endpoint": "pile-up separation",
                    "method": row["method"],
                    "primary_metric": "detection AP",
                    "value_ci95": _ci(s.rename("detection_ap")),
                    "secondary_metric": "miss / false split",
                    "secondary_value": f"{row['pileup_miss_rate']:.4g} / {row['false_split_rate']:.4g}",
                    "interpretation": "ability to find injected doublets without splitting clean controls",
                },
                {
                    "endpoint": "saturation recovery",
                    "method": row["method"],
                    "primary_metric": "fractional energy sigma68",
                    "value_ci95": _ci(s.rename("energy_fractional_sigma68")),
                    "secondary_metric": "fractional energy bias",
                    "secondary_value": f"{row['energy_fractional_bias']:.4g}",
                    "interpretation": "resolution of total constituent amplitude in high-charge mixtures",
                },
                {
                    "endpoint": "energy closure",
                    "method": row["method"],
                    "primary_metric": "fractional energy bias",
                    "value_ci95": _ci(s.rename("energy_fractional_bias")),
                    "secondary_metric": "fractional energy sigma68",
                    "secondary_value": f"{row['energy_fractional_sigma68']:.4g}",
                    "interpretation": "median closure of recovered sum amplitude against injection truth",
                },
                {
                    "endpoint": "pulse-shape residuals",
                    "method": row["method"],
                    "primary_metric": "late-tail |dt|>15 ns rate",
                    "value_ci95": _ci(s.rename("late_tail_rate_abs_gt_15ns")),
                    "secondary_metric": "timing sigma68 ns",
                    "secondary_value": f"{row['time_sigma68_ns']:.4g}",
                    "interpretation": "timing harm exposed by residual pulse-shape mismatch",
                },
            ]
        )
    endpoint = pd.DataFrame(rows)

    ped = strata[strata["stratum"] == "saturated_proxy"].copy()
    ped["endpoint"] = np.where(
        ped["value"].astype(str).eq("True"),
        "saturation-proxy high-amplitude closure",
        "pedestal robustness clean-amplitude closure",
    )
    ped = ped[
        [
            "endpoint",
            "value",
            "method",
            "energy_fractional_bias",
            "energy_fractional_sigma68",
            "time_sigma68_ns",
            "pileup_miss_rate",
        ]
    ].sort_values(["endpoint", "method"])

    pid = strata[strata["stratum"] == "stave"].copy()
    pivot = pid.pivot_table(
        index="method",
        columns="value",
        values="energy_fractional_bias",
        aggfunc="first",
    )
    pid_rows = []
    for method, row in pivot.iterrows():
        finite = row.dropna().astype(float)
        pid_rows.append(
            {
                "endpoint": "PID boundary shifts",
                "method": method,
                "stave_bias_min": float(finite.min()) if len(finite) else np.nan,
                "stave_bias_max": float(finite.max()) if len(finite) else np.nan,
                "max_abs_stave_energy_bias": float(finite.abs().max()) if len(finite) else np.nan,
                "stave_bias_span": float(finite.max() - finite.min()) if len(finite) else np.nan,
                "interpretation": "stave-conditioned energy bias as a PID-boundary proxy",
            }
        )
    pid_shift = pd.DataFrame(pid_rows).sort_values("max_abs_stave_energy_bias")

    # Add a direct waveform residual diagnostic from event-level predictions.
    positives = events[(events["split"] == "heldout") & (events["is_overlap"] == 1) & (~events["failed"].astype(bool))].copy()
    positives["energy_error"] = (
        positives["amp1_adc"]
        + positives["amp2_adc"]
        - positives["true_amp1_adc"]
        - positives["true_amp2_adc"]
    ) / np.maximum(positives["true_amp1_adc"] + positives["true_amp2_adc"], 1.0)
    positives["time_error_ns"] = 10.0 * (
        (positives["t1_sample"] - positives["true_t1_sample"]).abs()
        + (positives["t2_sample"] - positives["true_t2_sample"]).abs()
    ) / 2.0
    residual_rows = []
    for method, group in positives.groupby("method"):
        residual_rows.append(
            {
                "endpoint": "event-level closure residuals",
                "method": method,
                "median_abs_energy_error": float(group["energy_error"].abs().median()),
                "p90_abs_energy_error": float(group["energy_error"].abs().quantile(0.90)),
                "median_abs_time_error_ns": float(group["time_error_ns"].median()),
                "p90_abs_time_error_ns": float(group["time_error_ns"].quantile(0.90)),
            }
        )
    residual = pd.DataFrame(residual_rows).sort_values("p90_abs_energy_error")
    return endpoint, ped, pd.concat([pid_shift, residual], ignore_index=True, sort=False)


def append_s29b_report_sections() -> None:
    endpoint, pedestal, boundary = endpoint_tables()
    endpoint.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    pedestal.to_csv(OUT / "pedestal_saturation_strata.csv", index=False)
    boundary.to_csv(OUT / "pid_boundary_and_residual_checks.csv", index=False)

    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    winner = str(ranked.iloc[0]["method"])
    text = f"""

## S29b endpoint synthesis

The S29b ticket asks for six named endpoint families.  The primary model ranking
still uses the predeclared composite score in `winner_ranked_metrics.csv`, while
the table below maps each method to endpoint-specific quantities with run-block
95% bootstrap intervals where the summary statistic supports them.  The winner
reported in `result.json` is `{winner}`.

{md_table(endpoint, ['endpoint', 'method', 'primary_metric', 'value_ci95', 'secondary_metric', 'secondary_value'])}

### Pedestal robustness and saturation strata

Pedestal robustness is assessed indirectly through the clean-amplitude/saturation
proxy split retained by the controlled-injection generator.  The low-amplitude
side is most sensitive to baseline excursions because the same run-local residual
pool is injected before saturation clipping; the high-amplitude side stresses the
clipped-template recovery regime.

{md_table(pedestal, ['endpoint', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate'])}

### PID boundary and residual diagnostics

The B-stave label is used as a PID-boundary proxy because this raw ROOT benchmark
does not carry a final downstream PID decision.  A method that only improves
global energy resolution while shifting one stave family would be unsafe for a
PID boundary analysis, so the table reports the span and maximum absolute
stave-conditioned energy bias.  Event-level residual checks summarize the same
held-out positive events without bootstrap aggregation.

{md_table(boundary, ['endpoint', 'method', 'max_abs_stave_energy_bias', 'stave_bias_span', 'p90_abs_energy_error', 'p90_abs_time_error_ns'])}

## Additional S29b caveats

The study is deliberately conservative about what can be learned from the
available raw ROOT branches.  The benchmark truth is controlled injection truth,
not online pile-up truth, and the saturation label is an amplitude-ceiling proxy.
Pedestal robustness is tested through run-local residual injection and the
clean-amplitude sideband rather than a dedicated pedestal scan.  PID boundary
shifts are represented by stave-conditioned closure because no final PID boundary
label is present in the ROOT waveform tree.  These limitations are carried into
`result.json` and should be treated as systematics, not implementation details.
"""
    report = OUT / "REPORT.md"
    report_text = report.read_text(encoding="utf-8")
    report_text = report_text.replace(
        "# S26b: saturation energy recovery architecture bakeoff",
        f"# {TITLE}",
        1,
    )
    report.write_text(report_text + text, encoding="utf-8")

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["ticket_id"] = TICKET
    result["title"] = TITLE
    result["worker"] = WORKER
    result["study_id"] = "S29b"
    result["required_endpoint_coverage"] = {
        "pile_up_separation": "endpoint_metrics_ci.csv rows for detection AP, miss rate, false split rate",
        "saturation_recovery": "endpoint_metrics_ci.csv fractional energy sigma68 and saturated-proxy strata",
        "pedestal_robustness": "pedestal_saturation_strata.csv clean-amplitude sideband with run-local residuals",
        "energy_closure": "endpoint_metrics_ci.csv energy bias plus event-level closure residuals",
        "pulse_shape_residuals": "late-tail timing rate and event-level absolute timing residuals",
        "pid_boundary_shifts": "pid_boundary_and_residual_checks.csv stave-conditioned bias span",
    }
    result["artifacts"].update(
        {
            "endpoint_metrics_ci": "endpoint_metrics_ci.csv",
            "pedestal_saturation_strata": "pedestal_saturation_strata.csv",
            "pid_boundary_and_residual_checks": "pid_boundary_and_residual_checks.csv",
        }
    )
    result["caveats"].extend(
        [
            "Pedestal robustness is inferred from run-local residual injection and low-amplitude sidebands.",
            "PID boundary shifts are approximated by stave-conditioned energy closure; no final PID label is stored in the waveform tree.",
        ]
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def refresh_manifest() -> None:
    manifest_path = OUT / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["title"] = TITLE
    manifest["worker"] = WORKER
    manifest["study_id"] = "S29b"
    manifest["command"] = (
        f"{sys.executable} "
        "scripts/s29b_1783823997_52190_04e85489_saturation_pedestal_energy_recovery_frontier.py"
    )
    manifest["postprocess_note"] = "S29b endpoint synthesis appended after base runner completion."
    manifest["outputs_sha256"] = {
        p.name: runner.base.sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    runner.TICKET = TICKET
    runner.SLUG = SLUG
    runner.WORKER = WORKER
    runner.OUT = OUT
    runner.load_config = load_config
    runner.main()
    append_s29b_report_sections()
    refresh_manifest()


if __name__ == "__main__":
    main()
