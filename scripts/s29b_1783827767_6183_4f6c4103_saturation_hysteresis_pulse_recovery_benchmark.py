#!/usr/bin/env python3
"""S29b saturation hysteresis pulse recovery benchmark.

This ticket-local runner reuses the validated raw-ROOT reproduction,
controlled-injection, and architecture bakeoff machinery from the S26b/S29b
frontier studies.  It writes independent artifacts for the claimed ticket and
adds saturation-onset, recovery-bias, knee-location, pedestal-drift, and
pulse-window masking diagnostics requested by the S29b prompt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s26b_1783805896_7017_69544aca_pileup_saturation_recovery_frontier as runner  # noqa: E402


TICKET = "1783827767.6183.4f6c4103"
WORKER = "testbeam-laptop-1"
SLUG = "s29b_saturation_hysteresis_pulse_recovery_benchmark"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
TITLE = "S29b saturation hysteresis pulse recovery benchmark"
RAW_ROOT_DIR = ROOT / "data" / "root" / "root"

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
            "raw_root_dir": str(RAW_ROOT_DIR),
            "random_seed": 2026071217,
        }
    )
    cfg["ml"]["bootstrap_samples"] = int(cfg["ml"].get("bootstrap_samples", 400))
    return cfg


def _fmt(x: object) -> str:
    try:
        y = float(x)
    except Exception:
        return str(x)
    return f"{y:.4g}" if np.isfinite(y) else "nan"


def md_table(df: pd.DataFrame, columns: Iterable[str]) -> str:
    view = df.loc[:, list(columns)].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(_fmt)
    return view.to_markdown(index=False)


def _sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16.0, 84.0])
    return float(0.5 * (q84 - q16))


def _bootstrap_run_ci(
    frame: pd.DataFrame,
    runs: np.ndarray,
    rng: np.random.Generator,
    n_boot: int,
    fn,
) -> Tuple[float, float]:
    vals = []
    for _ in range(int(n_boot)):
        take = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([frame[frame["source_run"] == run] for run in take], ignore_index=True)
        val = float(fn(boot))
        if np.isfinite(val):
            vals.append(val)
    if not vals:
        return float("nan"), float("nan")
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def make_saturation_hysteresis_tables(n_boot: int, seed: int) -> Dict[str, pd.DataFrame]:
    events = pd.read_csv(OUT / "event_predictions.csv")
    held = events[(events["split"] == "heldout") & (~events["failed"].astype(bool))].copy()
    held["true_energy_adc"] = held["true_amp1_adc"].astype(float) + held["true_amp2_adc"].astype(float)
    held["pred_energy_adc"] = held["amp1_adc"].astype(float) + held["amp2_adc"].astype(float)
    held["energy_error_frac"] = (held["pred_energy_adc"] - held["true_energy_adc"]) / np.maximum(
        held["true_energy_adc"], 1.0
    )
    held["mean_abs_time_error_ns"] = 10.0 * (
        (held["t1_sample"].astype(float) - held["true_t1_sample"].astype(float)).abs()
        + (held["t2_sample"].astype(float) - held["true_t2_sample"].astype(float)).abs()
    ) / 2.0
    held["saturated_proxy"] = held["true_energy_adc"] >= np.percentile(held["true_energy_adc"], 80.0)
    held["close_pileup_proxy"] = held["true_sep_sample"].astype(float) <= 2.0
    held["tail_masked_proxy"] = held["true_sep_sample"].astype(float) <= 1.5
    held["pedestal_drift_proxy_adc"] = held["baseline_adc"].astype(float) if "baseline_adc" in held else 0.0
    held["pedestal_drift_high"] = held["pedestal_drift_proxy_adc"].abs() >= held["pedestal_drift_proxy_adc"].abs().median()

    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(held["source_run"].unique()))
    rows = []
    knee_rows = []
    window_rows = []
    bins = np.quantile(held["true_energy_adc"], np.linspace(0.0, 1.0, 7))
    bins = np.unique(bins)
    if len(bins) < 3:
        bins = np.linspace(float(held["true_energy_adc"].min()), float(held["true_energy_adc"].max()), 7)
    threshold = 0.08

    for method, group in held.groupby("method"):
        sat = group[group["saturated_proxy"]]
        unsat = group[~group["saturated_proxy"]]
        close = group[group["close_pileup_proxy"]]
        wide = group[~group["close_pileup_proxy"]]
        ped_hi = group[group["pedestal_drift_high"]]
        ped_lo = group[~group["pedestal_drift_high"]]

        def bias_delta(frame: pd.DataFrame) -> float:
            s = frame[frame["saturated_proxy"]]["energy_error_frac"].median()
            u = frame[~frame["saturated_proxy"]]["energy_error_frac"].median()
            return float(s - u)

        def sep_delta(frame: pd.DataFrame) -> float:
            c = frame[frame["close_pileup_proxy"]]["energy_error_frac"].median()
            w = frame[~frame["close_pileup_proxy"]]["energy_error_frac"].median()
            return float(c - w)

        def ped_delta(frame: pd.DataFrame) -> float:
            h = frame[frame["pedestal_drift_high"]]["energy_error_frac"].median()
            l = frame[~frame["pedestal_drift_high"]]["energy_error_frac"].median()
            return float(h - l)

        bias_lo, bias_hi = _bootstrap_run_ci(group, runs, rng, n_boot, bias_delta)
        sep_lo, sep_hi = _bootstrap_run_ci(group, runs, rng, n_boot, sep_delta)
        ped_lo_ci, ped_hi_ci = _bootstrap_run_ci(group, runs, rng, n_boot, ped_delta)
        rows.append(
            {
                "method": method,
                "saturation_onset_proxy_adc": float(np.percentile(group["true_energy_adc"], 80.0)),
                "saturated_energy_bias": float(sat["energy_error_frac"].median()),
                "unsaturated_energy_bias": float(unsat["energy_error_frac"].median()),
                "recovery_bias_delta": float(sat["energy_error_frac"].median() - unsat["energy_error_frac"].median()),
                "recovery_bias_delta_ci_low": bias_lo,
                "recovery_bias_delta_ci_high": bias_hi,
                "hysteresis_proxy_close_minus_wide_bias": float(
                    close["energy_error_frac"].median() - wide["energy_error_frac"].median()
                ),
                "hysteresis_proxy_ci_low": sep_lo,
                "hysteresis_proxy_ci_high": sep_hi,
                "pedestal_drift_bias_delta": float(
                    ped_hi["energy_error_frac"].median() - ped_lo["energy_error_frac"].median()
                ),
                "pedestal_drift_bias_delta_ci_low": ped_lo_ci,
                "pedestal_drift_bias_delta_ci_high": ped_hi_ci,
                "pileup_sensitivity_time_sigma68_ns": _sigma68(close["mean_abs_time_error_ns"].to_numpy()),
            }
        )

        by_bin = []
        for left, right in zip(bins[:-1], bins[1:]):
            b = group[(group["true_energy_adc"] >= left) & (group["true_energy_adc"] <= right)]
            if len(b) < 20:
                continue
            by_bin.append(
                {
                    "method": method,
                    "energy_bin_low_adc": float(left),
                    "energy_bin_high_adc": float(right),
                    "energy_bin_center_adc": float(0.5 * (left + right)),
                    "energy_fractional_sigma68": _sigma68(b["energy_error_frac"].to_numpy()),
                    "energy_fractional_bias": float(b["energy_error_frac"].median()),
                    "n_events": int(len(b)),
                }
            )
        bin_frame = pd.DataFrame(by_bin)
        if len(bin_frame):
            above = bin_frame[bin_frame["energy_fractional_sigma68"] >= threshold]
            knee = above.iloc[0]["energy_bin_center_adc"] if len(above) else bin_frame.iloc[-1]["energy_bin_center_adc"]
            knee_rows.append(
                {
                    "method": method,
                    "knee_definition": f"first true-energy bin with sigma68 >= {threshold:.2f}",
                    "saturation_knee_adc": float(knee),
                    "min_bin_sigma68": float(bin_frame["energy_fractional_sigma68"].min()),
                    "max_bin_sigma68": float(bin_frame["energy_fractional_sigma68"].max()),
                    "n_bins": int(len(bin_frame)),
                }
            )

        for mask_name, mask in [
            ("full_window", np.ones(len(group), dtype=bool)),
            ("tail_masked_close_pileup_proxy", group["tail_masked_proxy"].to_numpy(bool)),
            ("tail_retained_wide_pileup_proxy", (~group["tail_masked_proxy"]).to_numpy(bool)),
        ]:
            sub = group[mask]
            window_rows.append(
                {
                    "method": method,
                    "pulse_window_mask_proxy": mask_name,
                    "n_events": int(len(sub)),
                    "energy_fractional_sigma68": _sigma68(sub["energy_error_frac"].to_numpy()),
                    "time_sigma68_ns": _sigma68(sub["mean_abs_time_error_ns"].to_numpy()),
                    "late_tail_rate_abs_gt_15ns": float((sub["mean_abs_time_error_ns"] > 15.0).mean()) if len(sub) else np.nan,
                }
            )

    return {
        "saturation_hysteresis_summary": pd.DataFrame(rows).sort_values("recovery_bias_delta"),
        "saturation_knee_location": pd.DataFrame(knee_rows).sort_values("saturation_knee_adc"),
        "pulse_window_masking_ablation": pd.DataFrame(window_rows).sort_values(["method", "pulse_window_mask_proxy"]),
    }


def make_pid_boundary_table() -> pd.DataFrame:
    strata = pd.read_csv(OUT / "strata_metrics.csv")
    stave = strata[strata["stratum"] == "stave"].copy()
    rows = []
    for method, group in stave.groupby("method"):
        bias = group["energy_fractional_bias"].astype(float)
        leakage = group["late_tail_rate_abs_gt_15ns"].astype(float)
        rows.append(
            {
                "method": method,
                "pid_boundary_proxy": "B-stave conditioned energy and late-tail closure",
                "stave_bias_min": float(bias.min()),
                "stave_bias_max": float(bias.max()),
                "stave_bias_span": float(bias.max() - bias.min()),
                "max_abs_stave_energy_bias": float(bias.abs().max()),
                "late_tail_leakage_min": float(leakage.min()),
                "late_tail_leakage_max": float(leakage.max()),
                "late_tail_leakage_span": float(leakage.max() - leakage.min()),
                "n_stave_strata": int(len(group)),
            }
        )
    return pd.DataFrame(rows).sort_values(["max_abs_stave_energy_bias", "late_tail_leakage_span"])


def append_ticket_report_sections(tables: Dict[str, pd.DataFrame]) -> None:
    for name, table in tables.items():
        table.to_csv(OUT / f"{name}.csv", index=False)

    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    winner = str(ranked.iloc[0]["method"])
    report = OUT / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    text = text.replace("# S26b: saturation energy recovery architecture bakeoff", f"# {TITLE}", 1)
    text += f"""

## S29b saturation hysteresis endpoint synthesis

The S29b benchmark uses the same train/held-out run separation as the
controlled-injection architecture bakeoff, but evaluates endpoint families named
in the ticket: saturation onset, hysteresis/recovery bias, saturation-knee
location, pedestal drift, pulse-window masking, pile-up sensitivity, timing
residual, energy bias, and PID/stave leakage.  The raw ROOT reproduction gate
is `reproduction_match_table.csv`; the winning method written to `result.json`
is `{winner}`.

The controlled raw ROOT tree does not store a hardware hysteresis state bit, so
the hysteresis endpoint is an auditable proxy: close double-pulse separations
stress recovery after a preceding large pulse, while wide separations form the
release sideband.  Likewise, the saturation onset and knee are defined on true
injected total ADC, and pedestal drift is represented by run-local baseline
residual sidebands.  These definitions make the benchmark reproducible from the
data folder while keeping the limitations explicit.

The endpoint equations used in this section are the same as the main methods:
`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)]/(A_1 + A_2)`,
`e_t = 10 ns * (hat t - t_true)`, and
`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.  The recovery-bias equation is
`Delta_rec = median(e_E | saturated proxy) - median(e_E | unsaturated proxy)`;
the hysteresis proxy equation is
`Delta_hys = median(e_E | close pile-up) - median(e_E | wide pile-up)`.

{md_table(tables['saturation_hysteresis_summary'], ['method', 'saturation_onset_proxy_adc', 'saturated_energy_bias', 'unsaturated_energy_bias', 'recovery_bias_delta', 'recovery_bias_delta_ci_low', 'recovery_bias_delta_ci_high', 'hysteresis_proxy_close_minus_wide_bias', 'hysteresis_proxy_ci_low', 'hysteresis_proxy_ci_high', 'pedestal_drift_bias_delta', 'pileup_sensitivity_time_sigma68_ns'])}

### Saturation-knee location

The saturation-knee table scans true injected energy bins on the held-out runs.
The reported knee is the first bin center whose fractional energy sigma68
exceeds 0.08; if no bin crosses the threshold, the highest bin center is
reported as a right-censored knee estimate.

{md_table(tables['saturation_knee_location'], ['method', 'knee_definition', 'saturation_knee_adc', 'min_bin_sigma68', 'max_bin_sigma68', 'n_bins'])}

### Pulse-window masking ablation

Pulse-window masking is evaluated as a proxy ablation because the benchmark is
built from 18-sample raw waveforms.  The close-pileup sideband mimics a masked
late tail or ambiguous recovery window; the wide sideband retains a cleaner tail
constraint.  The table reports held-out energy and timing stability under these
window regimes.

{md_table(tables['pulse_window_masking_ablation'], ['method', 'pulse_window_mask_proxy', 'n_events', 'energy_fractional_sigma68', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns'])}

### PID leakage and boundary proxy

The raw waveform benchmark has no final downstream PID label.  To retain a
detector-facing leakage check, the study uses B-stave-conditioned energy closure
and late-tail timing leakage as the PID-boundary proxy.  This flags methods that
improve global recovery while moving one stave family differently from the
others.

{md_table(tables['pid_boundary_and_residual_checks'], ['method', 'pid_boundary_proxy', 'max_abs_stave_energy_bias', 'stave_bias_span', 'late_tail_leakage_span', 'n_stave_strata'])}

## Systematic limitations specific to this ticket

The result is a strong benchmark of recovery algorithms on raw-ROOT-derived
controlled injections, not a direct measurement of electronics memory.  The
available B-stack tree provides waveform samples, run IDs, event numbers, and
channels, but not an explicit saturation-latch or PID-boundary decision.  For
that reason, hysteresis is represented by separation-conditioned recovery bias,
PID leakage by stave-conditioned energy closure, and pedestal drift by baseline
sidebands.  The run-block bootstrap intervals quantify transfer across held-out
runs; they do not cover unobserved detector modes absent from the input ROOT
files.
"""
    report.write_text(text, encoding="utf-8")


def refresh_result_and_manifest(tables: Dict[str, pd.DataFrame]) -> None:
    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(
        {
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "study_id": "S29b",
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "raw_root_reproduction": {
                **result["raw_root_reproduction"],
                "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
                "data_folder": str(ROOT / "data"),
            },
        }
    )
    result["artifacts"].update(
        {
            "saturation_hysteresis_summary": "saturation_hysteresis_summary.csv",
            "saturation_knee_location": "saturation_knee_location.csv",
            "pulse_window_masking_ablation": "pulse_window_masking_ablation.csv",
            "pid_boundary_and_residual_checks": "pid_boundary_and_residual_checks.csv",
        }
    )
    result["required_endpoint_coverage"] = {
        "timing_residual": "method_metrics.csv time_bias_ns/time_sigma68_ns with run-block bootstrap CIs",
        "energy_bias": "method_metrics.csv energy_fractional_bias and energy_fractional_sigma68 with CIs",
        "pid_leakage": "pid_boundary_and_residual_checks.csv stave-conditioned energy and late-tail leakage proxy",
        "saturation_knee_location": "saturation_knee_location.csv first-bin sigma68 threshold scan",
        "pile_up_sensitivity": "method_metrics.csv pileup_miss_rate/false_split_rate and pulse_window_masking_ablation.csv",
        "saturation_onset_hysteresis_recovery": "saturation_hysteresis_summary.csv onset proxy, recovery-bias delta, close-vs-wide hysteresis proxy",
        "pedestal_drift_ablation": "saturation_hysteresis_summary.csv pedestal_drift_bias_delta and CIs",
        "pulse_window_masking_ablation": "pulse_window_masking_ablation.csv close/tail proxy sidebands",
    }
    result["winner"]["named_in_result_json"] = True
    result["winner"]["saturation_knee_adc"] = float(
        tables["saturation_knee_location"].set_index("method").loc[result["winner"]["name"], "saturation_knee_adc"]
    )
    result["winner"]["recovery_bias_delta"] = float(
        tables["saturation_hysteresis_summary"].set_index("method").loc[result["winner"]["name"], "recovery_bias_delta"]
    )
    result["winner"]["max_abs_stave_energy_bias"] = float(
        tables["pid_boundary_and_residual_checks"]
        .set_index("method")
        .loc[result["winner"]["name"], "max_abs_stave_energy_bias"]
    )
    result["caveats"].extend(
        [
            "Hysteresis is evaluated as a close-versus-wide pulse-separation recovery proxy because the ROOT tree has no explicit electronics hysteresis latch.",
            "Saturation-knee location is a controlled-injection energy-bin threshold, not a hardware scan of front-end saturation settings.",
            "Pulse-window masking is represented by separation-conditioned sidebands over the 18-sample waveform.",
        ]
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update(
        {
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "study_id": "S29b",
            "command": f"{sys.executable} scripts/{Path(__file__).name}",
            "postprocess_note": "S29b saturation hysteresis, knee, pedestal, and pulse-window endpoint tables appended after base runner completion.",
            "outputs_sha256": {
                p.name: runner.base.sha256_file(p)
                for p in sorted(OUT.iterdir())
                if p.is_file() and p.name != "manifest.json"
            },
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    runner.TICKET = TICKET
    runner.SLUG = SLUG
    runner.WORKER = WORKER
    runner.OUT = OUT
    runner.RAW_ROOT_DIR = RAW_ROOT_DIR
    runner.load_config = load_config
    runner.main()
    cfg = load_config()
    tables = make_saturation_hysteresis_tables(int(cfg["ml"]["bootstrap_samples"]), int(cfg["random_seed"]) + 17)
    tables["pid_boundary_and_residual_checks"] = make_pid_boundary_table()
    append_ticket_report_sections(tables)
    refresh_result_and_manifest(tables)


if __name__ == "__main__":
    main()
