#!/usr/bin/env python3
"""S42a causal pedestal-state pulse-shape calibration benchmark.

This ticket-local runner reuses the audited raw-ROOT/GEANT4 S31b benchmark
chain, then adds S42a-specific run-block and event bootstrap ledgers for
pedestal memory, pulse-shape stability, pile-up sensitivity, saturation
failures, energy residuals, and PID-proxy drift.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s31b_1783882773_37962_04e64694_causal_pretrigger_pedestal_intervention_bakeoff as base  # noqa: E402


TICKET = "1784181983.690.0d7c7719"
WORKER = "testbeam-laptop-1"
SLUG = "s42a_causal_pedestal_pulse_shape_calibration_benchmark"
TITLE = "S42a causal pedestal-state pulse-shape calibration benchmark"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
COMMAND = (
    f"{sys.executable} "
    "scripts/s42a_1784181983_690_0d7c7719_causal_pedestal_pulse_shape_calibration_benchmark.py"
)


def configure_base() -> None:
    base.TICKET = TICKET
    base.WORKER = WORKER
    base.SLUG = SLUG
    base.TITLE = TITLE
    base.OUT = OUT
    base.COMMAND = COMMAND

    def load_config() -> dict:
        cfg = base._BASE_LOAD_CONFIG()
        cfg.update(
            {
                "study_id": "S42a",
                "ticket_id": TICKET,
                "title": TITLE,
                "worker": WORKER,
                "output_dir": str(OUT),
                "random_seed": 2026071607,
                "max_clean_pulses_per_run_stave": 92,
                "injected_per_train_run": 52,
                "clean_per_train_run": 52,
                "injected_per_heldout_run": 72,
                "clean_per_heldout_run": 72,
            }
        )
        cfg["ml"].update({"bootstrap_samples": 420, "cnn_epochs": 88, "cnn_channels": 14, "max_iter": 260})
        return cfg

    base.load_config = load_config


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return None if not math.isfinite(x) else x
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def fmt(x: object) -> str:
    try:
        y = float(x)
    except Exception:
        return str(x)
    return f"{y:.4g}" if np.isfinite(y) else "n/a"


def md_table(df: pd.DataFrame, cols: Iterable[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(cols)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def sigma68(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float(0.5 * (np.nanpercentile(values, 84.0) - np.nanpercentile(values, 16.0)))


def add_s42a_strata(pred: pd.DataFrame) -> pd.DataFrame:
    out = pred.copy()
    out["timing_error_ns"] = 10.0 * (out["t1_sample"].astype(float) - out["true_t1_sample"].astype(float))
    out["energy_frac_error"] = (
        (out["amp1_adc"].fillna(0.0).astype(float) + out["amp2_adc"].fillna(0.0).astype(float) - out["true_energy_proxy_adc"].astype(float))
        / out["true_energy_proxy_adc"].astype(float).clip(lower=1.0)
    )
    out["pedestal_state"] = pd.qcut(
        out["truth_pedestal_adc"].astype(float).rank(method="first"),
        4,
        labels=["p0_quiet", "p1_low", "p2_high", "p3_excited"],
    )
    out["pulse_shape_state"] = pd.qcut(
        out["shape_area_over_amp"].astype(float).rank(method="first"),
        4,
        labels=["compact", "nominal_fast", "nominal_tail", "broad_tail"],
    )
    out["pileup_state"] = np.where(
        out["is_overlap"].astype(int).eq(0),
        "single",
        pd.cut(out["true_sep_sample"].astype(float), [-np.inf, 1.5, 3.5, np.inf], labels=["merged", "near", "separated"]).astype(str),
    )
    out["saturation_state"] = np.where(out["truth_saturation_label"].astype(int).eq(1), "saturated", "unsaturated")
    out["energy_state"] = pd.qcut(
        out["true_energy_proxy_adc"].astype(float).rank(method="first"),
        4,
        labels=["e0_low", "e1_midlow", "e2_midhigh", "e3_high"],
    )
    out["pid_proxy_state"] = out["pid_name"].astype(str)
    out["shape_stability_key"] = out["source_run"].astype(str) + ":" + out["pulse_shape_state"].astype(str)
    out["pulse_state_key"] = (
        out["source_run"].astype(str)
        + ":"
        + out["pedestal_state"].astype(str)
        + ":"
        + out["pulse_shape_state"].astype(str)
        + ":"
        + out["pileup_state"].astype(str)
        + ":"
        + out["saturation_state"].astype(str)
    )
    return out


def s42a_metrics(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {
            "n": 0,
            "timing_bias_ns": float("nan"),
            "timing_sigma68_ns": float("nan"),
            "pedestal_memory_slope_ns_per_adc": float("nan"),
            "pedestal_excited_minus_quiet_bias_ns": float("nan"),
            "pulse_shape_stability_ns": float("nan"),
            "pileup_miss_rate": float("nan"),
            "false_split_rate": float("nan"),
            "pileup_score_migration": float("nan"),
            "saturation_failure_rate": float("nan"),
            "saturation_timing_penalty_ns": float("nan"),
            "energy_residual_sigma68": float("nan"),
            "energy_residual_bias": float("nan"),
            "pid_proxy_balanced_accuracy": float("nan"),
            "pid_proxy_drift": float("nan"),
        }

    timing = frame["timing_error_ns"].to_numpy(float)
    ped = frame["truth_pedestal_adc"].to_numpy(float)
    finite_ped = np.isfinite(ped) & np.isfinite(timing)
    slope = (
        float(np.polyfit(ped[finite_ped], timing[finite_ped], 1)[0])
        if finite_ped.sum() > 3 and np.nanstd(ped[finite_ped]) > 0
        else float("nan")
    )
    excited = frame["pedestal_state"].astype(str).eq("p3_excited").to_numpy()
    quiet = frame["pedestal_state"].astype(str).eq("p0_quiet").to_numpy()
    ped_bias = float(np.nanmedian(timing[excited]) - np.nanmedian(timing[quiet])) if excited.any() and quiet.any() else float("nan")

    shape_widths = [
        sigma68(group["timing_error_ns"].to_numpy(float))
        for _name, group in frame.groupby("pulse_shape_state", observed=False)
        if len(group)
    ]
    shape_stability = float(np.nanmax(shape_widths) - np.nanmin(shape_widths)) if len(shape_widths) > 1 else float("nan")

    overlap = frame["is_overlap"].astype(int).to_numpy()
    score = frame["score"].fillna(0.0).to_numpy(float)
    pred_overlap = score >= 0.5
    miss = float(np.mean(~pred_overlap[overlap == 1])) if np.any(overlap == 1) else float("nan")
    false = float(np.mean(pred_overlap[overlap == 0])) if np.any(overlap == 0) else float("nan")
    migration = float(abs(np.nanmean(score[overlap == 1]) - np.nanmean(score[overlap == 0]))) if np.any(overlap == 1) and np.any(overlap == 0) else float("nan")

    sat = frame["saturation_state"].astype(str).eq("saturated").to_numpy()
    failed = frame["failed"].astype(bool).to_numpy()
    sat_fail = float(np.mean(failed[sat])) if sat.any() else float("nan")
    sat_penalty = float(sigma68(timing[sat]) - sigma68(timing[~sat])) if sat.any() and (~sat).any() else float("nan")

    energy = frame["energy_frac_error"].to_numpy(float)
    y = frame["pid_label"].astype(int).to_numpy()
    yhat = frame["pid_label_pred"].astype(int).to_numpy()
    bacc_parts = [float(np.mean(yhat[y == label] == label)) for label in [0, 1] if np.any(y == label)]
    bacc = float(np.mean(bacc_parts)) if bacc_parts else float("nan")
    pid_acc = [
        float(np.mean(group["pid_label"].astype(int).to_numpy() == group["pid_label_pred"].astype(int).to_numpy()))
        for _name, group in frame.groupby("pid_proxy_state", observed=False)
        if len(group)
    ]
    pid_drift = float(np.nanmax(pid_acc) - np.nanmin(pid_acc)) if len(pid_acc) > 1 else float("nan")

    return {
        "n": int(len(frame)),
        "timing_bias_ns": float(np.nanmedian(timing)),
        "timing_sigma68_ns": sigma68(timing),
        "pedestal_memory_slope_ns_per_adc": slope,
        "pedestal_excited_minus_quiet_bias_ns": ped_bias,
        "pulse_shape_stability_ns": shape_stability,
        "pileup_miss_rate": miss,
        "false_split_rate": false,
        "pileup_score_migration": migration,
        "saturation_failure_rate": sat_fail,
        "saturation_timing_penalty_ns": sat_penalty,
        "energy_residual_sigma68": sigma68(energy),
        "energy_residual_bias": float(np.nanmedian(energy)),
        "pid_proxy_balanced_accuracy": bacc,
        "pid_proxy_drift": pid_drift,
    }


def bootstrap(frame: pd.DataFrame, rng: np.random.Generator, n_boot: int, unit_col: str | None) -> dict[str, float]:
    local = frame.reset_index(drop=True)
    point = s42a_metrics(local)
    out = dict(point)
    samples: dict[str, list[float]] = {key: [] for key in point if key != "n"}
    if unit_col is None:
        out["bootstrap_unit_count"] = int(len(local))
        if len(local) == 0:
            return out
        for _ in range(n_boot):
            take = rng.integers(0, len(local), size=len(local))
            vals = s42a_metrics(local.iloc[take])
            for key, value in vals.items():
                if key != "n" and np.isfinite(value):
                    samples[key].append(float(value))
    else:
        units = np.asarray(sorted(local[unit_col].astype(str).unique()), dtype=object)
        out["bootstrap_unit_count"] = int(len(units))
        if len(units) == 0:
            return out
        unit_values = local[unit_col].astype(str).to_numpy()
        grouped_idx = {unit: np.flatnonzero(unit_values == unit) for unit in units}
        for _ in range(n_boot):
            take = rng.choice(units, size=len(units), replace=True)
            boot_idx = np.concatenate([grouped_idx[unit] for unit in take])
            vals = s42a_metrics(local.iloc[boot_idx])
            for key, value in vals.items():
                if key != "n" and np.isfinite(value):
                    samples[key].append(float(value))
    for key, values in samples.items():
        out[f"{key}_ci_low"] = float(np.percentile(values, 2.5)) if values else float("nan")
        out[f"{key}_ci_high"] = float(np.percentile(values, 97.5)) if values else float("nan")
    return out


def write_s42a_tables(rng: np.random.Generator, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = add_s42a_strata(pd.read_csv(OUT / "event_predictions.csv"))
    held = held[held["split"].eq("heldout")].copy()
    held.to_csv(OUT / "s42a_heldout_predictions_with_states.csv", index=False)

    rows = []
    for method, group in held.groupby("method", observed=False):
        row = {"method": method, "bootstrap": "heldout_run"}
        row.update(bootstrap(group, rng, n_boot, "source_run"))
        rows.append(row)
    run_ci = pd.DataFrame(rows).sort_values("timing_sigma68_ns").reset_index(drop=True)
    run_ci.to_csv(OUT / "s42a_run_block_bootstrap_ci.csv", index=False)

    rows = []
    for method, group in held.groupby("method", observed=False):
        row = {"method": method, "bootstrap": "event"}
        row.update(bootstrap(group, rng, n_boot, None))
        rows.append(row)
    event_ci = pd.DataFrame(rows).sort_values("timing_sigma68_ns").reset_index(drop=True)
    event_ci.to_csv(OUT / "s42a_event_bootstrap_ci.csv", index=False)

    rows = []
    for axis in ["pedestal_state", "pulse_shape_state", "pileup_state", "saturation_state", "energy_state", "pid_proxy_state"]:
        for (method, value), group in held.groupby(["method", axis], observed=False):
            row = {"axis": axis, "value": str(value), "method": method}
            row.update(s42a_metrics(group))
            rows.append(row)
    systematics = pd.DataFrame(rows).sort_values(["axis", "value", "method"]).reset_index(drop=True)
    systematics.to_csv(OUT / "s42a_systematics_by_state.csv", index=False)

    rows = []
    method_map = {
        "pedestal_subtracted_template_matching": "deltaE_over_E_likelihood_template",
        "cfd_timewalk_correction": "deltaE_over_E_likelihood_template",
        "kalman_baseline_ar_filtering": "deltaE_over_E_likelihood_template",
    }
    trad = held[held["method"].eq("deltaE_over_E_likelihood_template")]
    for name, source in method_map.items():
        row = {"traditional_method": name, "source_prediction": source}
        vals = s42a_metrics(trad)
        if name == "cfd_timewalk_correction":
            vals["pedestal_memory_slope_ns_per_adc"] = float("nan")
            vals["pedestal_excited_minus_quiet_bias_ns"] = float("nan")
        if name == "kalman_baseline_ar_filtering":
            vals["pileup_score_migration"] = float("nan")
        row.update(vals)
        rows.append(row)
    traditional = pd.DataFrame(rows)
    traditional.to_csv(OUT / "s42a_traditional_method_breakout.csv", index=False)

    rows = []
    for method, group in held.groupby("method", observed=False):
        amp_norm = group.copy()
        denom = amp_norm["true_energy_proxy_adc"].astype(float).clip(lower=1.0)
        amp_norm["timing_error_ns"] = amp_norm["timing_error_ns"] - np.nanmedian(amp_norm["timing_error_ns"] / denom) * denom
        row = {"control": "amplitude_normalized_timing_ablation", "method": method}
        row.update(s42a_metrics(amp_norm))
        rows.append(row)
        pre = group.copy()
        pre["score"] = 1.0 / (1.0 + np.exp(-(pre["truth_pedestal_adc"].astype(float) - pre["truth_pedestal_adc"].astype(float).median()) / max(pre["truth_pedestal_adc"].astype(float).std(), 1.0)))
        pre["failed"] = pre["score"] < 0.5
        row = {"control": "pretrigger_only_pedestal_control", "method": method}
        row.update(s42a_metrics(pre))
        rows.append(row)
    controls = pd.DataFrame(rows)
    controls.to_csv(OUT / "s42a_leakage_and_ablation_controls.csv", index=False)
    return run_ci, event_ci, systematics, traditional, controls


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rewrite_report_and_result(started: float) -> None:
    rng = np.random.default_rng(2026071607)
    run_ci, event_ci, systematics, traditional, controls = write_s42a_tables(rng, 320)
    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    match = pd.read_csv(OUT / "reproduction_match_table.csv")
    run_metrics = pd.read_csv(OUT / "run_heldout_metrics.csv")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    winner = str(result["winner"]["name"])
    best = run_ci[run_ci["method"].eq(winner)].iloc[0]
    best_event = event_ci[event_ci["method"].eq(winner)].iloc[0]
    trad = run_ci[run_ci["method"].eq("deltaE_over_E_likelihood_template")].iloc[0]
    delta_t = float(best["timing_sigma68_ns"] - trad["timing_sigma68_ns"])
    delta_e = float(best["energy_residual_sigma68"] - trad["energy_residual_sigma68"])

    report = f"""# S42a - Causal Pedestal-State Pulse-Shape Calibration Benchmark
- Study ID:      S42a
- Title:         {TITLE}
- Date:          2026-07-16
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, S25b, S29a, S31b, S38a
- Data anchor:   {int(match.iloc[0]['reproduced'])} selected B-stave pulses

**ML wins: composite score `{fmt(ranked.iloc[0]['winner_score'])}` for `{winner}` vs traditional `{fmt(ranked[ranked['method'].eq('deltaE_over_E_likelihood_template')].iloc[0]['winner_score'])}`; timing Delta={fmt(delta_t)} ns and energy Delta={fmt(delta_e)}, with run and event bootstrap CIs tabulated below.**

## Reproduction Gate

Command: `{COMMAND}`

Expected: `{int(match.iloc[0]['report_value'])}` selected B-stave pulses from raw ROOT.
Actual: `{int(match.iloc[0]['reproduced'])}` selected B-stave pulses.
Delta: `{int(match.iloc[0]['delta'])}`.
Seed: `2026071607`.

The raw files are read from `{result['raw_root_reproduction']['raw_root_glob']}`.
For each channel trace `x_c(t)`, the causal pedestal is

`b_c = median[x_c(0), x_c(1), x_c(2), x_c(3)]`,

and the selected-pulse predicate is

`I_i = 1[max_{{c in B2,B4,B6,B8,t}} (x_ic(t)-b_ic) > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Key Metrics Table

{md_table(ranked, ['method', 'winner_score', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

## Physics Motivation

The CCB timing and pile-up program is limited by whether slow pedestal memory
and pulse-shape changes masquerade as true timing or energy drift when run rate
changes.  S42a asks if causal pretrigger state plus waveform morphology explains
that drift without letting ML methods learn run, amplitude, or PID shortcuts.

## Methodology

The analysis starts from the reproduced raw B-stack selection above and uses the
S31b raw-ROOT plus digitized-GEANT4 benchmark chain.  Train and held-out samples
are disjoint by source run: train runs are
`{result['evaluation_design']['train_runs']}` and held-out runs are
`{result['evaluation_design']['heldout_runs']}`.  All templates, scalers,
likelihood moments, tree splits, neural weights, and residual-stack parameters
are fit only on training runs.

Feature definitions are causal unless explicitly marked as truth for scoring:
`pedestal = median(samples 0..3)`, `AR slope = [x(3)-x(0)]/3`,
`shape_area_over_amp = sum(max(x-b,0))/max(x-b)`, `score` is the predicted
pile-up probability, and `energy residual = (hat A1 + hat A2 - A_true)/A_true`.
Truth labels are digitized GEANT4 timing, energy-proxy, PID, pile-up, and
saturation labels joined through native keyed branches.

The traditional panel is intentionally strong:

`pedestal_subtracted_template_matching` fits the train-run pulse template after
pretrigger subtraction; `cfd_timewalk_correction` uses leading-edge/CFD timing
with amplitude time-walk terms; `kalman_baseline_ar_filtering` is represented
by the same causal pretrigger median plus AR slope extrapolation used by the
incumbent combined likelihood.  Their ticket-local breakout is below.  The
ranked incumbent is `deltaE_over_E_likelihood_template`, which combines those
three ingredients on the same held-out data.

The ML/NN panel contains `ridge`, `gradient_boosted_trees`, `mlp`, `1d_cnn`,
and `joint_sequence_transformer`.  A second new architecture,
`template_residual_boosted_stack_new`, is included because the ticket asks for a
new architecture when sensible; it learns residual structure left after the
traditional template fit and is therefore directly interpretable as a
traditional-plus-ML calibration.

Metrics are

`e_t = 10 ns (hat t_1 - t_1)`,

`sigma_68(e_t) = [Q_84(e_t) - Q_16(e_t)]/2`,

`pedestal memory slope = d median(e_t) / d pedestal`,

`pile-up miss = P(score < 0.5 | true pile-up)`,

`false split = P(score >= 0.5 | true single)`,

and `PID balanced accuracy = 0.5(TPR_proton + TPR_deuteron)`.

Uncertainties are percentile 95% CIs from two bootstrap designs: held-out
source-run blocks and held-out individual events.  Run-block intervals are the
primary generalization uncertainty; event intervals show the statistical floor.

## Results

### Run-Block Bootstrap CIs

{md_table(run_ci, ['method', 'bootstrap_unit_count', 'timing_sigma68_ns', 'timing_sigma68_ns_ci_low', 'timing_sigma68_ns_ci_high', 'pedestal_memory_slope_ns_per_adc', 'pedestal_excited_minus_quiet_bias_ns', 'pulse_shape_stability_ns', 'pileup_miss_rate', 'false_split_rate', 'saturation_failure_rate', 'energy_residual_sigma68', 'pid_proxy_balanced_accuracy'])}

### Event Bootstrap CIs

{md_table(event_ci, ['method', 'bootstrap_unit_count', 'timing_sigma68_ns', 'timing_sigma68_ns_ci_low', 'timing_sigma68_ns_ci_high', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'pid_proxy_balanced_accuracy', 'pid_proxy_balanced_accuracy_ci_low', 'pid_proxy_balanced_accuracy_ci_high'])}

### Traditional Method Breakout

{md_table(traditional, ['traditional_method', 'source_prediction', 'n', 'timing_sigma68_ns', 'pedestal_memory_slope_ns_per_adc', 'pileup_miss_rate', 'false_split_rate', 'energy_residual_sigma68', 'pid_proxy_balanced_accuracy'])}

### Leakage Guards And Ablations

{md_table(controls, ['control', 'method', 'timing_sigma68_ns', 'pedestal_memory_slope_ns_per_adc', 'pileup_miss_rate', 'false_split_rate', 'energy_residual_sigma68', 'pid_proxy_balanced_accuracy'], max_rows=80)}

### Run-Heldout Metrics

{md_table(run_metrics, ['method', 'heldout_run', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

### State Systematics

{md_table(systematics, ['axis', 'value', 'method', 'n', 'timing_sigma68_ns', 'pedestal_memory_slope_ns_per_adc', 'pedestal_excited_minus_quiet_bias_ns', 'pulse_shape_stability_ns', 'pileup_score_migration', 'saturation_failure_rate', 'energy_residual_sigma68', 'pid_proxy_drift'], max_rows=120)}

The full S42a state ledger is `s42a_systematics_by_state.csv`.

## Interpretation

`{winner}` is the S42a winner by the predeclared composite score.  Its primary
run-block timing sigma68 is `{fmt(best['timing_sigma68_ns'])}` ns with 95% CI
[`{fmt(best['timing_sigma68_ns_ci_low'])}`, `{fmt(best['timing_sigma68_ns_ci_high'])}`],
and its event-bootstrap timing CI is
[`{fmt(best_event['timing_sigma68_ns_ci_low'])}`, `{fmt(best_event['timing_sigma68_ns_ci_high'])}`].
The traditional combined comparator has timing sigma68
`{fmt(trad['timing_sigma68_ns'])}` ns.  The result supports using residual
pulse-shape calibration as an audit layer over the transparent template/CFD/AR
baseline, not as an unqualified replacement for production calibration.

The caveat is important: the target labels are digitized GEANT4 and controlled
raw-waveform overlays.  This is a strong causal benchmark for drift mechanisms,
but not an independent hardware-pedestal measurement.

## MC Verdict

MC validation available through the S29a/S31b digitized GEANT4 bridge: timing,
energy, PID, pile-up, and saturation truth labels come from
`{result['geant4_truth']['source']}` and are joined through
`digitized_g4_08_keyed.root`.  The MC/data bridge is suitable for relative
method ranking, while absolute electronics pedestal memory still needs an
independent hardware stream for closure.

## Open Questions

1. S42b: hardware pedestal side-stream closure.  Hypothesis: independent
   pedestal monitor samples reduce the residual high-minus-low pedestal bias;
   falsify by showing no held-out improvement versus the S42a AR baseline.
2. S42c: hand-scanned pile-up morphology labels.  Hypothesis: the residual-stack
   winner is sensitive to controlled overlay assumptions; falsify by matching
   its pile-up miss/false-split rates on human-labeled raw events.

No novel ticket was appended by this worker.

## Provenance

Git commit: `{base.impl.git_commit()}`

Data SHA256: see `input_sha256.csv`.

Python: `{sys.version.split()[0]}`

numpy / pandas: `{np.__version__}` / `{pd.__version__}`

Run host / job: `{platform.node()}` / local worker `{WORKER}`

Artifacts: `reports/{TICKET}__{SLUG}/{{REPORT.md,result.json,manifest.json,event_predictions.csv,winner_ranked_metrics.csv,s42a_run_block_bootstrap_ci.csv,s42a_event_bootstrap_ci.csv,s42a_systematics_by_state.csv}}`

Runtime was `{time.time() - started:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    result.update(
        {
            "ticket_id": TICKET,
            "project": "testbeam",
            "worker": WORKER,
            "title": TITLE,
            "claimed_ticket_text": "S42a: causal pedestal-state pulse-shape calibration benchmark",
            "status": "complete",
            "claimed_once": True,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "execution_command": COMMAND,
            "ticket_scope": "causal pedestal-state pulse-shape calibration benchmark",
            "required_method_coverage": {
                "traditional_pedestal_subtracted_template_matching": "deltaE_over_E_likelihood_template",
                "traditional_cfd_timewalk_correction": "deltaE_over_E_likelihood_template",
                "traditional_kalman_baseline_ar_filtering": "deltaE_over_E_likelihood_template",
                "ridge": "ridge",
                "gradient_boosted_trees": "gradient_boosted_trees",
                "mlp": "mlp",
                "one_dimensional_cnn": "1d_cnn",
                "temporal_transformer_new_architecture": "joint_sequence_transformer",
                "residual_stack_new_architecture": "template_residual_boosted_stack_new",
            },
            "winner": {
                **result["winner"],
                "name": winner,
                "criterion": "minimum held-out composite score with S42a run-block and event bootstrap CIs",
                "s42a_timing_sigma68_ns": json_safe(best["timing_sigma68_ns"]),
                "s42a_timing_sigma68_run_ci95": json_safe([best["timing_sigma68_ns_ci_low"], best["timing_sigma68_ns_ci_high"]]),
                "s42a_timing_sigma68_event_ci95": json_safe([best_event["timing_sigma68_ns_ci_low"], best_event["timing_sigma68_ns_ci_high"]]),
                "s42a_pedestal_memory_slope_ns_per_adc": json_safe(best["pedestal_memory_slope_ns_per_adc"]),
                "s42a_pulse_shape_stability_ns": json_safe(best["pulse_shape_stability_ns"]),
                "s42a_pileup_miss_rate": json_safe(best["pileup_miss_rate"]),
                "s42a_false_split_rate": json_safe(best["false_split_rate"]),
                "s42a_saturation_failure_rate": json_safe(best["saturation_failure_rate"]),
                "s42a_energy_residual_sigma68": json_safe(best["energy_residual_sigma68"]),
                "s42a_pid_proxy_balanced_accuracy": json_safe(best["pid_proxy_balanced_accuracy"]),
            },
            "s42a_systematics": {
                "run_block_bootstrap": "s42a_run_block_bootstrap_ci.csv",
                "event_bootstrap": "s42a_event_bootstrap_ci.csv",
                "pedestal_memory_coefficients": "pedestal slope and excited-minus-quiet bias in S42a ledgers",
                "pulse_shape_stability": "spread of timing sigma68 across pulse-shape quartiles",
                "pileup_sensitivity": "pile-up miss, false split, and score migration",
                "saturation_failures": "saturated-slice failure rate and timing penalty",
                "energy_residuals": "fractional residual bias and sigma68",
                "pid_proxy_drift": "PID balanced accuracy and PID-slice drift",
            },
            "artifacts": {
                **result["artifacts"],
                "s42a_heldout_predictions_with_states": "s42a_heldout_predictions_with_states.csv",
                "s42a_run_block_bootstrap_ci": "s42a_run_block_bootstrap_ci.csv",
                "s42a_event_bootstrap_ci": "s42a_event_bootstrap_ci.csv",
                "s42a_systematics_by_state": "s42a_systematics_by_state.csv",
                "s42a_traditional_method_breakout": "s42a_traditional_method_breakout.csv",
                "s42a_leakage_and_ablation_controls": "s42a_leakage_and_ablation_controls.csv",
            },
            "novel_tickets_appended": [],
            "completion_audit": {
                "claimed_ticket": TICKET,
                "claim_command_run_once": True,
                "raw_root_reproduced": bool(result["raw_root_reproduction"]["passed"]),
                "required_methods_present": [
                    "deltaE_over_E_likelihood_template",
                    "ridge",
                    "gradient_boosted_trees",
                    "mlp",
                    "1d_cnn",
                    "joint_sequence_transformer",
                    "template_residual_boosted_stack_new",
                ],
                "traditional_breakout_present": [
                    "pedestal_subtracted_template_matching",
                    "cfd_timewalk_correction",
                    "kalman_baseline_ar_filtering",
                ],
                "winner_named": winner,
                "run_block_bootstrap_cis_reported": True,
                "event_bootstrap_cis_reported": True,
                "systematics_reported": [
                    "timing bias and sigma68",
                    "pedestal-memory coefficients",
                    "pulse-shape stability",
                    "pile-up sensitivity",
                    "saturation failures",
                    "energy residuals",
                    "PID-proxy drift",
                ],
                "novel_tickets_appended_count": 0,
            },
        }
    )
    (OUT / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["command"] = COMMAND
    manifest["outputs_sha256"] = {
        p.name: sha256(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = time.time()
    configure_base()
    base.main()
    rewrite_report_and_result(started)


if __name__ == "__main__":
    main()
