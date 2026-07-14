#!/usr/bin/env python3
"""S38a pedestal-state timing correction benchmark.

This ticket-local wrapper reuses the audited S31b/S29a raw-ROOT and model
benchmark chain, then adds the S38a-specific held-out pulse-stratum bootstrap
ledger for pedestal-state timing, pile-up migration, saturation, energy-proxy,
and PID-proxy stability.
"""

from __future__ import annotations

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


TICKET = "1784069109.866.75ec7063"
WORKER = "testbeam-laptop-3"
SLUG = "s38a_pedestal_state_timing_correction"
TITLE = "S38a pedestal-state timing correction across pulse shape and pile-up regimes"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
COMMAND = f"{sys.executable} scripts/s38a_1784069109_866_75ec7063_pedestal_state_timing_correction.py"


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
                "study_id": "S38a",
                "ticket_id": TICKET,
                "title": TITLE,
                "worker": WORKER,
                "output_dir": str(OUT),
                "random_seed": 2026071503,
                "max_clean_pulses_per_run_stave": 88,
                "injected_per_train_run": 48,
                "clean_per_train_run": 48,
                "injected_per_heldout_run": 68,
                "clean_per_heldout_run": 68,
            }
        )
        cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 82, "cnn_channels": 12, "max_iter": 250})
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
    return f"{y:.4g}" if np.isfinite(y) else "nan"


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


def add_s38a_strata(pred: pd.DataFrame) -> pd.DataFrame:
    out = pred.copy()
    out["timing_error_ns"] = 10.0 * (out["t1_sample"].astype(float) - out["true_t1_sample"].astype(float))
    out["energy_frac_error"] = (
        (out["amp1_adc"].fillna(0.0).astype(float) + out["amp2_adc"].fillna(0.0).astype(float) - out["true_energy_proxy_adc"].astype(float))
        / out["true_energy_proxy_adc"].astype(float).clip(lower=1.0)
    )
    out["pedestal_state"] = pd.qcut(
        out["truth_pedestal_adc"].astype(float).rank(method="first"),
        3,
        labels=["low_pedestal", "mid_pedestal", "high_pedestal"],
    )
    out["pulse_shape_regime"] = pd.qcut(
        out["shape_area_over_amp"].astype(float).rank(method="first"),
        3,
        labels=["narrow_fast_shape", "nominal_shape", "broad_tail_shape"],
    )
    out["pileup_regime"] = np.where(
        out["is_overlap"].astype(int).eq(0),
        "single",
        pd.cut(out["true_sep_sample"].astype(float), [-np.inf, 1.5, 3.5, np.inf], labels=["merged_pileup", "near_pileup", "separated_pileup"]).astype(str),
    )
    out["saturation_slice"] = np.where(out["truth_saturation_label"].astype(int).eq(1), "saturated", "unsaturated")
    out["energy_proxy_slice"] = pd.qcut(
        out["true_energy_proxy_adc"].astype(float).rank(method="first"),
        3,
        labels=["low_energy_proxy", "mid_energy_proxy", "high_energy_proxy"],
    )
    out["pid_proxy_slice"] = out["pid_name"].astype(str)
    out["pulse_stratum"] = (
        out["source_run"].astype(str)
        + ":"
        + out["pedestal_state"].astype(str)
        + ":"
        + out["pulse_shape_regime"].astype(str)
        + ":"
        + out["pileup_regime"].astype(str)
        + ":"
        + out["saturation_slice"].astype(str)
    )
    return out


def s38a_metrics(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {
            "n": 0,
            "timing_residual_sigma68_ns": float("nan"),
            "timing_residual_bias_ns": float("nan"),
            "pedestal_high_minus_low_bias_ns": float("nan"),
            "pedestal_error_slope_ns_per_adc": float("nan"),
            "pileup_score_migration": float("nan"),
            "pileup_miss_rate": float("nan"),
            "false_split_rate": float("nan"),
            "saturation_slice_stability_ns": float("nan"),
            "energy_proxy_drift": float("nan"),
            "pid_proxy_stability": float("nan"),
        }
    timing = frame["timing_error_ns"].to_numpy(float)
    ped = frame["truth_pedestal_adc"].to_numpy(float)
    high = frame["pedestal_state"].astype(str).eq("high_pedestal").to_numpy()
    low = frame["pedestal_state"].astype(str).eq("low_pedestal").to_numpy()
    if high.any() and low.any():
        ped_bias = float(np.nanmedian(timing[high]) - np.nanmedian(timing[low]))
    else:
        ped_bias = float("nan")
    ped_slope = float(np.polyfit(ped, timing, 1)[0]) if len(frame) > 3 and np.nanstd(ped) > 0 else float("nan")

    overlap = frame["is_overlap"].astype(int).to_numpy()
    score = frame["score"].fillna(0.0).to_numpy(float)
    pred_overlap = score >= 0.5
    miss = float(np.mean(~pred_overlap[overlap == 1])) if np.any(overlap == 1) else float("nan")
    false = float(np.mean(pred_overlap[overlap == 0])) if np.any(overlap == 0) else float("nan")
    pile_migration = float(abs(np.nanmean(score[overlap == 1]) - np.nanmean(score[overlap == 0]))) if np.any(overlap == 1) and np.any(overlap == 0) else float("nan")

    sat_widths = []
    for _name, group in frame.groupby("saturation_slice", observed=False):
        sat_widths.append(sigma68(group["timing_error_ns"].to_numpy(float)))
    sat_stability = float(np.nanmax(sat_widths) - np.nanmin(sat_widths)) if len(sat_widths) > 1 else float("nan")

    energy_medians = []
    for _name, group in frame.groupby("energy_proxy_slice", observed=False):
        energy_medians.append(float(np.nanmedian(group["energy_frac_error"].to_numpy(float))))
    energy_drift = float(np.nanmax(energy_medians) - np.nanmin(energy_medians)) if len(energy_medians) > 1 else float("nan")

    pid_acc = []
    for _name, group in frame.groupby("pid_proxy_slice", observed=False):
        y = group["pid_label"].astype(int).to_numpy()
        yhat = group["pid_label_pred"].astype(int).to_numpy()
        if len(y):
            pid_acc.append(float(np.mean(y == yhat)))
    pid_stability = float(np.nanmax(pid_acc) - np.nanmin(pid_acc)) if len(pid_acc) > 1 else float("nan")

    return {
        "n": int(len(frame)),
        "timing_residual_sigma68_ns": sigma68(timing),
        "timing_residual_bias_ns": float(np.nanmedian(timing)),
        "pedestal_high_minus_low_bias_ns": ped_bias,
        "pedestal_error_slope_ns_per_adc": ped_slope,
        "pileup_score_migration": pile_migration,
        "pileup_miss_rate": miss,
        "false_split_rate": false,
        "saturation_slice_stability_ns": sat_stability,
        "energy_proxy_drift": energy_drift,
        "pid_proxy_stability": pid_stability,
    }


def bootstrap_by_unit(frame: pd.DataFrame, unit_col: str, rng: np.random.Generator, n_boot: int) -> dict[str, float]:
    local = frame.reset_index(drop=True)
    unit_values = local[unit_col].astype(str)
    units = np.asarray(sorted(unit_values.unique()), dtype=object)
    point = s38a_metrics(local)
    out = dict(point)
    out["bootstrap_unit_count"] = int(len(units))
    samples: dict[str, list[float]] = {key: [] for key in point if key != "n"}
    if len(units) == 0:
        return out
    grouped_idx = {unit: np.flatnonzero(unit_values.to_numpy() == unit) for unit in units}
    for _ in range(n_boot):
        take = rng.choice(units, size=len(units), replace=True)
        boot_idx = np.concatenate([grouped_idx[unit] for unit in take])
        boot = local.iloc[boot_idx]
        vals = s38a_metrics(boot)
        for key, value in vals.items():
            if key != "n" and np.isfinite(value):
                samples[key].append(float(value))
    for key, values in samples.items():
        out[f"{key}_ci_low"] = float(np.percentile(values, 2.5)) if values else float("nan")
        out[f"{key}_ci_high"] = float(np.percentile(values, 97.5)) if values else float("nan")
    return out


def write_s38a_tables(rng: np.random.Generator, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = add_s38a_strata(pd.read_csv(OUT / "event_predictions.csv"))
    held = held[held["split"].eq("heldout")].copy()
    held.to_csv(OUT / "s38a_heldout_predictions_with_strata.csv", index=False)

    rows = []
    for method, group in held.groupby("method", observed=False):
        row = {"method": method, "bootstrap_unit": "heldout_run"}
        row.update(bootstrap_by_unit(group, "source_run", rng, n_boot))
        rows.append(row)
    run_ci = pd.DataFrame(rows).sort_values("timing_residual_sigma68_ns").reset_index(drop=True)
    run_ci.to_csv(OUT / "s38a_run_bootstrap_ci.csv", index=False)

    rows = []
    for method, group in held.groupby("method", observed=False):
        row = {"method": method, "bootstrap_unit": "source_run:pedestal:shape:pileup:saturation"}
        row.update(bootstrap_by_unit(group, "pulse_stratum", rng, n_boot))
        rows.append(row)
    strata_ci = pd.DataFrame(rows).sort_values("timing_residual_sigma68_ns").reset_index(drop=True)
    strata_ci.to_csv(OUT / "s38a_pulse_strata_bootstrap_ci.csv", index=False)

    rows = []
    for axis in ["pedestal_state", "pulse_shape_regime", "pileup_regime", "saturation_slice", "energy_proxy_slice", "pid_proxy_slice"]:
        for (method, value), group in held.groupby(["method", axis], observed=False):
            row = {"axis": axis, "value": str(value), "method": method}
            row.update(s38a_metrics(group))
            rows.append(row)
    sidebands = pd.DataFrame(rows).sort_values(["axis", "value", "method"]).reset_index(drop=True)
    sidebands.to_csv(OUT / "s38a_systematics_by_pulse_stratum.csv", index=False)
    return run_ci, strata_ci, sidebands


def rewrite_report_and_result(started: float) -> None:
    rng = np.random.default_rng(2026071503)
    run_ci, strata_ci, sidebands = write_s38a_tables(rng, 260)
    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    match = pd.read_csv(OUT / "reproduction_match_table.csv")
    run_metrics = pd.read_csv(OUT / "run_heldout_metrics.csv")
    view = pd.read_csv(OUT / "s31b_input_view_metrics.csv")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    winner = str(result["winner"]["name"])
    best = run_ci[run_ci["method"].eq(winner)].iloc[0]
    best_strata = strata_ci[strata_ci["method"].eq(winner)].iloc[0]
    trad = run_ci[run_ci["method"].eq("deltaE_over_E_likelihood_template")].iloc[0]

    report = f"""# S38a: pedestal-state timing correction across pulse shape and pile-up regimes

## Abstract

Ticket `{TICKET}` asks whether pedestal-state and pretrigger-memory modeling can
reduce timing bias without leaking amplitude or PID proxies.  The raw B-stack
selected-pulse count is reproduced directly from ROOT, then a strong
traditional adaptive-pedestal plus leading-edge/constant-fraction/template
time-walk correction is benchmarked against ridge, gradient-boosted trees, MLP,
1D-CNN, and a causal waveform transformer.  A physics-residual boosted stack is
kept as a second new architecture because it tests whether the transparent
traditional correction leaves structured residuals.

The winner named in `result.json` is **`{winner}`**.  Its held-out timing
sigma68 is `{fmt(best['timing_residual_sigma68_ns'])}` ns with run-bootstrap
95% CI [`{fmt(best['timing_residual_sigma68_ns_ci_low'])}`,
`{fmt(best['timing_residual_sigma68_ns_ci_high'])}`] and pulse-stratum bootstrap
95% CI [`{fmt(best_strata['timing_residual_sigma68_ns_ci_low'])}`,
`{fmt(best_strata['timing_residual_sigma68_ns_ci_high'])}`].  The traditional
comparator timing sigma68 is `{fmt(trad['timing_residual_sigma68_ns'])}` ns.

## Raw ROOT Reproduction

Raw B-stack ROOT files are read from
`{result['raw_root_reproduction']['raw_root_glob']}`.  For each event-channel
trace `x_c(t)`, the pretrigger pedestal is

`b_c = median[x_c(0), x_c(1), x_c(2), x_c(3)]`,

and the selected-pulse predicate is

`I_i = 1[max_{{c in B2,B4,B6,B8,t}} (x_ic(t)-b_ic) > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Data, Split, And Leakage Controls

The benchmark uses raw-ROOT-derived B-stave waveforms joined to digitized
GEANT4 event labels for timing, PID, and energy proxy targets.  Training and
held-out sets are disjoint by source run: train runs are
`{result['evaluation_design']['train_runs']}` and held-out runs are
`{result['evaluation_design']['heldout_runs']}`.  Templates, scalers,
likelihood parameters, and neural weights are fit only on training runs.  The
reported intervals resample held-out runs and, separately, held-out
`source_run:pedestal_state:pulse_shape:pileup_regime:saturation_slice` strata.

The leakage guard is conceptual and tabular: run IDs are split, not used as
features; amplitude and PID proxies are evaluated as downstream stability
metrics rather than allowed to define the timing residual target.  Energy-proxy
drift and PID-proxy stability are reported explicitly in the S38a systematics
ledger.

## Methods

The traditional method, `deltaE_over_E_likelihood_template`, estimates a
causal pedestal with the pretrigger median and a first-order AR-style slope,
then applies leading-edge, CFD, and template time-walk corrections.  In the
pulse window,

`b_AR(t) = b_0 + s(t - 1.5),    s = [x(3)-x(0)]/3`.

The ML/NN panel is fixed before ranking: `ridge`, `gradient_boosted_trees`,
`mlp`, `1d_cnn`, and `joint_sequence_transformer`.  The transformer is the
causal waveform architecture: an attention encoder over the short ADC sequence
with sample-position embeddings and no held-out run information.  The
additional `template_residual_boosted_stack_new` architecture models residuals
after the traditional template fit.

For timing residuals,

`e_t = 10 ns (hat t_1 - t_1)`,

`sigma_68(e_t) = [Q_84(e_t) - Q_16(e_t)] / 2`.

Pedestal bias is `median(e_t | high pedestal) - median(e_t | low pedestal)`.
Pile-up migration is `|E[score | true pile-up] - E[score | single]|`.
Saturation stability is the spread of timing sigma68 across saturation slices.
Energy drift is the spread of median fractional energy error across energy
proxy tertiles.  PID stability is the spread of PID-proxy accuracy across PID
proxy slices.

## Overall Benchmark With Run CIs

{md_table(ranked, ['method', 'winner_score', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

## S38a Run-Block Bootstrap Ledger

{md_table(run_ci, ['method', 'timing_residual_sigma68_ns', 'timing_residual_sigma68_ns_ci_low', 'timing_residual_sigma68_ns_ci_high', 'timing_residual_bias_ns', 'pedestal_high_minus_low_bias_ns', 'pileup_score_migration', 'saturation_slice_stability_ns', 'energy_proxy_drift', 'pid_proxy_stability'])}

## Pulse-Stratum Bootstrap Ledger

{md_table(strata_ci, ['method', 'bootstrap_unit_count', 'timing_residual_sigma68_ns', 'timing_residual_sigma68_ns_ci_low', 'timing_residual_sigma68_ns_ci_high', 'pedestal_high_minus_low_bias_ns', 'pedestal_high_minus_low_bias_ns_ci_low', 'pedestal_high_minus_low_bias_ns_ci_high', 'pileup_score_migration', 'energy_proxy_drift', 'pid_proxy_stability'])}

## Input Views And Causal Pedestal Intervention

{md_table(view, ['input_view', 'methods', 'n', 'timing_pull_sigma68', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68', 'pid_balanced_accuracy'])}

## Run-Heldout Metrics

{md_table(run_metrics, ['method', 'heldout_run', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Systematics By Pulse Stratum

{md_table(sidebands, ['axis', 'value', 'method', 'n', 'timing_residual_sigma68_ns', 'pedestal_high_minus_low_bias_ns', 'pileup_score_migration', 'saturation_slice_stability_ns', 'energy_proxy_drift', 'pid_proxy_stability'], max_rows=120)}

The full table is `s38a_systematics_by_pulse_stratum.csv`; the report shows
the leading rows to keep the manuscript readable.

## Systematics And Caveats

This is a controlled benchmark, not a final detector calibration.  GEANT4
provides timing, PID, and energy proxy labels; ADC morphology comes from
raw-ROOT residual/template pools.  Saturation and pile-up are controlled
benchmark labels rather than independent electronics flags.  The pretrigger
window has only four samples, so the adaptive pedestal model is deliberately
low-order; a more expressive pedestal fit would risk absorbing pulse-shape
information.  Pulse-stratum bootstrap intervals quantify sensitivity to
pedestal, shape, pile-up, and saturation composition, but not GEANT4
physics-list or material-budget uncertainty.

No novel ticket is appended from S38a.  The immediate next question would need
an independent hardware pedestal stream or hand-scanned pile-up labels rather
than another architecture-only follow-up.

Runtime was `{time.time() - started:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    result.update(
        {
            "ticket_id": TICKET,
            "project": "testbeam",
            "worker": WORKER,
            "title": TITLE,
            "claimed_ticket_text": (
                "S38a: pedestal-state timing correction across pulse shape and pile-up regimes"
            ),
            "status": "complete",
            "claimed_once": True,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "execution_command": COMMAND,
            "ticket_scope": "pedestal-state timing correction across pulse-shape and pile-up regimes",
            "required_method_coverage": {
                "strong_traditional": "deltaE_over_E_likelihood_template",
                "ridge": "ridge",
                "gradient_boosted_trees": "gradient_boosted_trees",
                "mlp": "mlp",
                "one_dimensional_cnn": "1d_cnn",
                "causal_waveform_transformer": "joint_sequence_transformer",
                "new_architecture": "template_residual_boosted_stack_new",
            },
            "winner": {
                **result["winner"],
                "name": winner,
                "criterion": "minimum held-out composite score with S38a run and pulse-stratum timing/systematics CIs reported",
                "s38a_timing_residual_sigma68_ns": json_safe(best["timing_residual_sigma68_ns"]),
                "s38a_timing_residual_sigma68_run_ci95": json_safe(
                    [best["timing_residual_sigma68_ns_ci_low"], best["timing_residual_sigma68_ns_ci_high"]]
                ),
                "s38a_timing_residual_sigma68_pulse_strata_ci95": json_safe(
                    [
                        best_strata["timing_residual_sigma68_ns_ci_low"],
                        best_strata["timing_residual_sigma68_ns_ci_high"],
                    ]
                ),
                "s38a_pedestal_high_minus_low_bias_ns": json_safe(best["pedestal_high_minus_low_bias_ns"]),
                "s38a_pileup_score_migration": json_safe(best["pileup_score_migration"]),
                "s38a_saturation_slice_stability_ns": json_safe(best["saturation_slice_stability_ns"]),
                "s38a_energy_proxy_drift": json_safe(best["energy_proxy_drift"]),
                "s38a_pid_proxy_stability": json_safe(best["pid_proxy_stability"]),
            },
            "s38a_systematics": {
                "timing_residual": "s38a_run_bootstrap_ci.csv and s38a_pulse_strata_bootstrap_ci.csv",
                "pedestal_bias": "high-minus-low pedestal timing bias with CIs",
                "pileup_score_migration": "held-out score separation between true pile-up and singles",
                "saturation_slice_stability": "spread of timing sigma68 across saturation slices",
                "energy_proxy_drift": "spread of median fractional energy error across energy-proxy tertiles",
                "pid_proxy_stability": "spread of PID-proxy accuracy across PID proxy slices",
            },
            "artifacts": {
                **result["artifacts"],
                "s38a_run_bootstrap_ci": "s38a_run_bootstrap_ci.csv",
                "s38a_pulse_strata_bootstrap_ci": "s38a_pulse_strata_bootstrap_ci.csv",
                "s38a_systematics_by_pulse_stratum": "s38a_systematics_by_pulse_stratum.csv",
                "s38a_heldout_predictions_with_strata": "s38a_heldout_predictions_with_strata.csv",
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
                "winner_named": winner,
                "run_bootstrap_cis_reported": True,
                "pulse_strata_bootstrap_cis_reported": True,
                "systematics_reported": [
                    "timing residual",
                    "pedestal bias",
                    "pile-up score migration",
                    "saturation slice stability",
                    "energy-proxy drift",
                    "PID-proxy stability",
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
        p.name: base.impl.sha256(p)
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
