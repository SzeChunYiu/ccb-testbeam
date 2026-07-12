#!/usr/bin/env python3
"""S33c PID, energy, and timing multitask pulse representation audit.

This ticket-specific runner reuses the established S26c/S29c raw-ROOT
benchmark machinery, then adds explicit S33c ablation/stress tables for
pedestal-sensitive pulses, pile-up masking, and saturation-proxy samples.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26c_1783800116_3081_430d48e6_pulse_pid_energy_timing_joint_inference_bakeoff as s26c  # noqa: E402


TICKET = "1783888239.874.72877e21"
SLUG = "s33c_pid_energy_timing_multitask_pulse_representation_audit"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
WORKER = "testbeam-laptop-1"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
_S26C_LOAD_CONFIG = s26c.load_config


def sha256(path: Path) -> str:
    return base.sha256_file(path)


def load_config() -> dict:
    cfg = _S26C_LOAD_CONFIG()
    cfg.update(
        {
            "study_id": "S33c",
            "ticket_id": TICKET,
            "title": "PID energy timing multitask pulse representation audit",
            "worker": WORKER,
            "output_dir": str(OUT),
            "raw_root_dir": str(RAW_ROOT_DIR),
            "random_seed": 2026071233,
            "max_clean_pulses_per_run_stave": 96,
            "injected_per_train_run": 58,
            "clean_per_train_run": 58,
            "injected_per_heldout_run": 78,
            "clean_per_heldout_run": 78,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 440, "cnn_epochs": 88, "cnn_channels": 14, "max_iter": 280})
    return cfg


def _fmt(value: float) -> str:
    return f"{value:.4g}" if np.isfinite(value) else "nan"


def _summarize_frame(frame: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for method, group in frame.groupby("method"):
        row = {"method": method, **s26c.metric_values(group)}
        runs = sorted(group["source_run"].unique())
        samples: dict[str, list[float]] = {}
        if runs:
            for _ in range(n_boot):
                take = rng.choice(runs, size=len(runs), replace=True)
                boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
                vals = s26c.metric_values(boot)
                for key, value in vals.items():
                    if key.startswith("n_") or not np.isfinite(value):
                        continue
                    samples.setdefault(key, []).append(float(value))
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def build_ablation_tables(joined: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    held = joined[joined["split"] == "heldout"].copy()
    rng = np.random.default_rng(int(cfg["random_seed"]) + 707)
    n_boot = int(cfg["ml"]["bootstrap_samples"])

    rows = []
    definitions = [
        {
            "ablation": "nominal",
            "mask": np.ones(len(held), dtype=bool),
            "note": "standard run-held-out evaluation with per-method pile-up accept/reject mask",
        },
        {
            "ablation": "pedestal_sensitive_tail_shape_top_quartile",
            "mask": held["shape_area_over_amp"] >= held["shape_area_over_amp"].quantile(0.75),
            "note": "stress slice for events most sensitive to pedestal subtraction and late-tail baseline motion",
        },
        {
            "ablation": "saturation_proxy_high_energy_top_quartile",
            "mask": held["true_energy_proxy_adc"] >= held["true_energy_proxy_adc"].quantile(0.75),
            "note": "stress slice for high-amplitude events closest to ADC saturation and recovery nonlinearities",
        },
    ]
    for spec in definitions:
        sub = held.loc[spec["mask"]].copy()
        summary = _summarize_frame(sub, rng, n_boot)
        summary.insert(0, "ablation", spec["ablation"])
        summary["note"] = spec["note"]
        rows.append(summary)

    unmasked = held.copy()
    unmasked["failed"] = False
    summary = _summarize_frame(unmasked, rng, n_boot)
    summary.insert(0, "ablation", "pileup_mask_removed_accept_all_candidates")
    summary["note"] = "accepts every scored event to isolate the effect of the learned/template pile-up mask"
    rows.append(summary)

    ablations = pd.concat(rows, ignore_index=True)
    ranked_nominal = s26c.rank_methods(
        ablations[ablations["ablation"] == "nominal"].drop(columns=["ablation", "note"])
    )
    winner = str(ranked_nominal.iloc[0]["method"])
    winner_ablation = ablations[ablations["method"] == winner].copy()
    winner_ablation["winner_score"] = (
        winner_ablation["energy_fractional_sigma68"]
        + 0.01 * winner_ablation["time_sigma68_ns"]
        + 0.25 * (1.0 - winner_ablation["pid_balanced_accuracy"])
        + 0.05 * winner_ablation["pileup_miss_rate"]
        + 0.05 * winner_ablation["false_split_rate"]
    )
    return ablations, winner_ablation


def _table(df: pd.DataFrame, cols: list[str], limit: int | None = None) -> str:
    view = df[cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(_fmt)
    return view.to_markdown(index=False)


def write_s33c_report(cfg: dict, runtime: float) -> None:
    match = pd.read_csv(OUT / "reproduction_match_table.csv")
    templates = pd.read_csv(OUT / "template_summary.csv")
    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    by_run = pd.read_csv(OUT / "run_heldout_metrics.csv")
    strata = pd.read_csv(OUT / "strata_metrics.csv")
    ablations = pd.read_csv(OUT / "ablation_metrics.csv")
    winner_ablation = pd.read_csv(OUT / "winner_ablation_metrics.csv")

    best = ranked.iloc[0]
    winner = str(best["method"])
    trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    method_cols = [
        "method",
        "winner_score",
        "pid_auc",
        "pid_balanced_accuracy",
        "pid_balanced_accuracy_ci_low",
        "pid_balanced_accuracy_ci_high",
        "energy_fractional_sigma68",
        "energy_fractional_sigma68_ci_low",
        "energy_fractional_sigma68_ci_high",
        "time_sigma68_ns",
        "time_sigma68_ns_ci_low",
        "time_sigma68_ns_ci_high",
        "pileup_miss_rate",
        "false_split_rate",
    ]
    ablation_cols = [
        "ablation",
        "method",
        "pid_balanced_accuracy",
        "pid_balanced_accuracy_ci_low",
        "pid_balanced_accuracy_ci_high",
        "energy_fractional_sigma68",
        "energy_fractional_sigma68_ci_low",
        "energy_fractional_sigma68_ci_high",
        "time_sigma68_ns",
        "time_sigma68_ns_ci_low",
        "time_sigma68_ns_ci_high",
        "pileup_miss_rate",
        "false_split_rate",
    ]
    text = f"""# S33c: PID energy timing multitask pulse representation audit

## Abstract

Ticket `{TICKET}` asks for a raw-ROOT-reproduced benchmark of shared pulse
representations for PID, energy, and timing.  The worker was `{WORKER}`.  The
study compares a strong traditional charge-ratio/time-over-threshold/template
method with ridge, gradient-boosted trees, MLP, 1D-CNN, and a new multitask
sequence architecture under a grouped split by run.

The raw selected-pulse anchor is reproduced directly from ROOT:
`{int(match.iloc[0]['reproduced'])}` selected B-stave pulses versus reference
`{int(match.iloc[0]['report_value'])}`, delta `{int(match.iloc[0]['delta'])}`.

The winner named in `result.json` is **`{winner}`**, selected by the held-out
composite score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy fractional sigma68 `{_fmt(best['energy_fractional_sigma68'])}`
with 95% run-block bootstrap CI
[{_fmt(best['energy_fractional_sigma68_ci_low'])}, {_fmt(best['energy_fractional_sigma68_ci_high'])}],
timing sigma68 `{_fmt(best['time_sigma68_ns'])}` ns with CI
[{_fmt(best['time_sigma68_ns_ci_low'])}, {_fmt(best['time_sigma68_ns_ci_high'])}],
and PID balanced accuracy `{_fmt(best['pid_balanced_accuracy'])}` with CI
[{_fmt(best['pid_balanced_accuracy_ci_low'])}, {_fmt(best['pid_balanced_accuracy_ci_high'])}].

## Raw ROOT Reproduction

Raw files were read from `{cfg['raw_root_dir']}`.  Each `h101/HRDv` branch is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The selected
B-stack pulse count is reproduced using B2/B4/B6/B8, pedestal

`b_c = median_t x_c(t), t in {{0,1,2,3}}`,

corrected waveform

`y_c(t)=x_c(t)-b_c`,

and selected-pulse condition

`max_t y_c(t)>1000 ADC`.

{_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Split, Labels, And Leakage Controls

The grouped split is by source run: train runs `{cfg['benchmark_runs']['train']}`
and held-out runs `{cfg['benchmark_runs']['heldout']}`.  No source run appears in
both sets.  Templates, scalers, likelihood moments, boosted trees, ridge heads,
MLP heads, CNN weights, and transformer weights are fitted on train-run events
only.  Run and event identifiers are retained for grouping and audit but are not
used as model features.

The PID endpoint is a deterministic raw-waveform proxy, not external particle
truth.  Controlled doublets are injected into raw clean-pulse residuals; the
deuteron-like positive class is fixed by total injected energy, stave depth, and
area-over-peak shape.  This makes the benchmark reproducible and leakage-audited
while limiting claims to architecture ranking.

For injected doublets,

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{{r,s}}(t) + p`,

where `T_s` is the train-run stave template, `epsilon_{{r,s}}` is a raw residual
sampled from source run `r` and stave `s`, and `p` is the retained pedestal term.

Train-only template summaries:

{_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`.  It combines a
bounded two-pulse template/CFD recovery for timing and energy with a diagonal
Gaussian likelihood-ratio PID model over charge-ratio, time-over-threshold, tail,
late-fraction, peak-sample, stave-depth, and dE/dx-like variables.  With
standardized features `z_j`,

`log p(z | y) = -1/2 sum_j [(z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel contains:

| family | implementation |
|---|---|
| Ridge | standardized ridge classifier plus multi-output ridge recovery head |
| Gradient-boosted trees | histogram gradient-boosted PID, pile-up, and recovery heads |
| MLP | two-hidden-layer MLP classifiers/regressors with early stopping |
| 1D-CNN | compact waveform convolutional encoder with a separate PID head |
| New architecture | `joint_sequence_transformer`, a shared waveform transformer with pile-up, PID, and recovery heads |
| Physics-residual architecture | `template_residual_boosted_stack_new`, boosted residual heads using the traditional fit as first stage |

For accepted injected doublets, residuals are

`e_t = 10 ns (hat t - t_true)`,

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`,

and

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap resamples.

## Overall Held-Out Results

{_table(ranked, method_cols)}

Relative to the traditional baseline, `{winner}` changes energy sigma68 by
`{_fmt(best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68'])}`,
timing sigma68 by `{_fmt(best['time_sigma68_ns'] - trad['time_sigma68_ns'])}` ns,
and PID balanced accuracy by
`{_fmt(best['pid_balanced_accuracy'] - trad['pid_balanced_accuracy'])}`.

## Ablations And Stress Tests

Three explicit ablation/stress views are reported in addition to the nominal
ranking.  `pileup_mask_removed_accept_all_candidates` is a direct post-fit
ablation of the per-method pile-up accept/reject mask.  The pedestal and
saturation entries are held-out robustness slices: top-quartile
`shape_area_over_amp` isolates pulses most sensitive to pedestal subtraction and
late-tail baseline motion, while top-quartile `true_energy_proxy_adc` isolates
the highest-amplitude saturation-proxy events.  These are not external hardware
truth flags.

Winner ablation summary:

{_table(winner_ablation, ablation_cols)}

Full method ablation metrics are written to `ablation_metrics.csv`; the first
rows are:

{_table(ablations.sort_values(['ablation', 'method']), ablation_cols, limit=20)}

## Run-Held-Out Stability

{_table(by_run, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Strata, Systematics, And Caveats

The stratum scan covers injected pulse spacing, total energy proxy, stave/depth,
and PID class.  It tests whether a method wins only in an easy spacing regime,
one stave, or one ionization class.

{_table(strata, ['stratum', 'value', 'method', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate'], limit=48)}

The leading systematic is the deterministic PID proxy.  It is useful for a
controlled architecture audit, but it is not external particle identification.
Pile-up and saturation conditions are controlled injections and high-amplitude
stress proxies inside raw ROOT residuals, not independent hardware labels.  The
18-sample window constrains sub-sample timing and makes pedestal motion partly
degenerate with late tails.  Bootstrap intervals resample held-out runs, so they
describe run-transfer uncertainty rather than event-level asymptotic precision.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    s26c.TICKET = TICKET
    s26c.SLUG = SLUG
    s26c.OUT = OUT
    s26c.WORKER = WORKER
    s26c.RAW_ROOT_DIR = RAW_ROOT_DIR
    s26c.load_config = load_config
    s26c.main()

    cfg = load_config()
    joined = pd.read_csv(OUT / "event_predictions.csv")
    ablations, winner_ablation = build_ablation_tables(joined, cfg)
    ablations.to_csv(OUT / "ablation_metrics.csv", index=False)
    winner_ablation.to_csv(OUT / "winner_ablation_metrics.csv", index=False)

    ranked = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    runtime = time.time() - started
    write_s33c_report(cfg, runtime)

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    winner = ranked.iloc[0]
    result.update(
        {
            "title": cfg["title"],
            "status": "complete",
            "worker": WORKER,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "ablation_design": {
                "pedestal_subtraction": "top-quartile shape_area_over_amp stress slice for pedestal-sensitive late-tail baseline motion",
                "pileup_masking": "post-fit accept-all-candidates ablation with failed set to false",
                "saturated_samples": "top-quartile true_energy_proxy_adc high-amplitude saturation-proxy stress slice",
                "bootstrap": "same held-out run-block percentile 95% CI machinery as nominal metrics",
            },
            "winner": {
                "name": str(winner["method"]),
                "criterion": "minimum held-out composite joint PID/energy/timing score with run-block bootstrap CIs reported",
                "winner_score": float(winner["winner_score"]),
                "pid_auc": float(winner["pid_auc"]),
                "pid_balanced_accuracy": float(winner["pid_balanced_accuracy"]),
                "pid_balanced_accuracy_ci95": [
                    float(winner["pid_balanced_accuracy_ci_low"]),
                    float(winner["pid_balanced_accuracy_ci_high"]),
                ],
                "pid_efficiency": float(winner["pid_efficiency"]),
                "pid_purity": float(winner["pid_purity"]),
                "energy_fractional_sigma68": float(winner["energy_fractional_sigma68"]),
                "energy_fractional_sigma68_ci95": [
                    float(winner["energy_fractional_sigma68_ci_low"]),
                    float(winner["energy_fractional_sigma68_ci_high"]),
                ],
                "time_sigma68_ns": float(winner["time_sigma68_ns"]),
                "time_sigma68_ci95": [
                    float(winner["time_sigma68_ns_ci_low"]),
                    float(winner["time_sigma68_ns_ci_high"]),
                ],
                "pileup_miss_rate": float(winner["pileup_miss_rate"]),
                "false_split_rate": float(winner["false_split_rate"]),
            },
            "artifacts": {
                **result["artifacts"],
                "ablation_metrics": "ablation_metrics.csv",
                "winner_ablation_metrics": "winner_ablation_metrics.csv",
            },
            "novel_tickets_appended": [],
            "completion_audit": {
                "raw_root_reproduced": bool(result["raw_root_reproduction"]["passed"]),
                "required_methods_present": sorted(result["required_method_coverage"].values()),
                "winner_named": str(winner["method"]),
                "run_bootstrap_cis_reported": all(
                    col in ranked.columns
                    for col in [
                        "pid_balanced_accuracy_ci_low",
                        "pid_balanced_accuracy_ci_high",
                        "energy_fractional_sigma68_ci_low",
                        "energy_fractional_sigma68_ci_high",
                        "time_sigma68_ns_ci_low",
                        "time_sigma68_ns_ci_high",
                    ]
                ),
                "ablation_tables_written": True,
                "runtime_seconds_including_wrapper": runtime,
            },
        }
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["command"] = (
        f"{sys.executable} "
        "scripts/s33c_1783888239_874_72877e21_pid_energy_timing_multitask_pulse_representation_audit.py"
    )
    manifest["runtime_seconds"] = runtime
    manifest["outputs_sha256"] = {
        p.name: sha256(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
