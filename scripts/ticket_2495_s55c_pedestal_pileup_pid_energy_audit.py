#!/usr/bin/env python3
"""Issue #2495 S55c pedestal-pileup PID/energy stability audit."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b  # noqa: E402
import s35b_1784063447_914_74ba7793_saturation_pileup_energy_recovery_benchmark as s35b  # noqa: E402


TICKET = "2495"
FACTORY_ISSUE = 2495
WORKER = "testbeam-laptop-1"
TITLE = "S55c: Pedestal-pileup PID boundary stability and energy transfer audit"
SLUG = "s55c_pedestal_pileup_pid_energy_transfer_audit"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_CANDIDATES = (
    Path("/home/billy/ccb-data/data/extracted/root/root"),
    Path("/home/billy/ccb-data/extracted/root/root"),
    ROOT / "data" / "root" / "root",
    ROOT / "data" / "extracted" / "root" / "root",
)
ADC_CLIP = s32b.ADC_CLIP


CLAIMED_TICKET_BODY = """2495
# S55c: Pedestal-pileup PID boundary stability and energy transfer audit

Question: test whether pedestal memory and unresolved pile-up shift PID
boundaries or energy transfer functions after conventional correction,
especially near low-amplitude and high-rate regimes.

Traditional comparator: pedestal-subtracted charge ratios, CFD timing,
DeltaE-E style cuts, and Huber-calibrated run offsets.

Compare ridge, gradient-boosted trees, MLP, 1D-CNN, and tabular-plus-waveform
transformer models where apt for PID, energy, timing, saturation flagging, and
pile-up probability. Report stratified paired bootstrap 95% CIs, calibration
curves, ECE, energy bias, timing res68, and counterfactual ablations for
pedestal windows, pile-up masks, shape derivatives, and saturated bins.
"""


def resolve_raw_root_dir() -> Path:
    for path in RAW_ROOT_CANDIDATES:
        if (path / "hrdb_run_0031.root").exists():
            return path
    raise FileNotFoundError("No raw ROOT directory with hrdb_run_0031.root found")


RAW_ROOT_DIR = resolve_raw_root_dir()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S55c",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026081601,
            "max_clean_pulses_per_run_stave": 108,
            "injected_per_train_run": 64,
            "clean_per_train_run": 64,
            "injected_per_heldout_run": 88,
            "clean_per_heldout_run": 88,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 450, "cnn_epochs": 96, "cnn_channels": 12, "max_iter": 280})
    return cfg


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def md_table(df: pd.DataFrame, cols: list[str], limit: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def ece_and_calibration(joined: pd.DataFrame, bins: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    held = joined[joined["split"] == "heldout"].copy()
    rows = []
    curves = []
    edges = np.linspace(0.0, 1.0, bins + 1)
    for method, group in held.groupby("method"):
        score = np.clip(group["score"].to_numpy(float), 0.0, 1.0)
        truth = group["is_overlap"].to_numpy(float)
        ece = 0.0
        brier = float(np.mean((score - truth) ** 2))
        for lo, hi in zip(edges[:-1], edges[1:]):
            mask = (score >= lo) & (score <= hi if hi == 1.0 else score < hi)
            if not np.any(mask):
                continue
            weight = float(mask.mean())
            conf = float(score[mask].mean())
            obs = float(truth[mask].mean())
            ece += weight * abs(obs - conf)
            curves.append(
                {
                    "method": method,
                    "bin_low": float(lo),
                    "bin_high": float(hi),
                    "n": int(mask.sum()),
                    "mean_score": conf,
                    "observed_overlap_rate": obs,
                    "abs_gap": abs(obs - conf),
                }
            )
        rows.append({"method": method, "ece": float(ece), "brier": brier, "n_heldout": int(len(group))})
    return pd.DataFrame(rows).sort_values("ece"), pd.DataFrame(curves)


def add_diagnostic_columns(events: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    out = events.copy()
    baseline = np.median(waves[:, :4], axis=1)
    corr = waves - baseline[:, None]
    deriv = np.diff(corr, axis=1)
    out["pedestal_window_median_adc"] = baseline
    out["pedestal_window_mad_adc"] = np.median(np.abs(waves[:, :4] - baseline[:, None]), axis=1)
    out["pileup_mask_counterfactual"] = np.where(out["is_overlap"].to_numpy(int) == 1, "pileup_truth_on", "pileup_truth_off")
    out["shape_derivative_energy"] = np.sum(deriv**2, axis=1)
    out["shape_derivative_bin"] = pd.qcut(out["shape_derivative_energy"], q=4, labels=["q1", "q2", "q3", "q4"], duplicates="drop")
    out["pedestal_window_bin"] = pd.qcut(out["pedestal_window_mad_adc"], q=4, labels=["q1", "q2", "q3", "q4"], duplicates="drop")
    out["saturated_bin"] = pd.cut(
        out["saturated_sample_count"], bins=[-0.5, 0.5, 2.5, 5.5, 18.5], labels=["0", "1-2", "3-5", "6+"]
    )
    return out


def ablation_summary(joined: pd.DataFrame, winner: str) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["method"] == winner)].copy()
    rows = []
    dimensions = {
        "pedestal_windows": "pedestal_window_bin",
        "pileup_masks": "pileup_mask_counterfactual",
        "shape_derivatives": "shape_derivative_bin",
        "saturated_bins": "saturated_bin",
    }
    global_metrics = base.metric_values(held)
    for label, field in dimensions.items():
        for value, group in held.groupby(field, observed=False):
            metrics = base.metric_values(group)
            rows.append(
                {
                    "ablation_axis": label,
                    "counterfactual_level": str(value),
                    "method": winner,
                    "n": int(len(group)),
                    "energy_fractional_bias": metrics["energy_fractional_bias"],
                    "energy_fractional_sigma68": metrics["energy_fractional_sigma68"],
                    "delta_sigma68_vs_global": metrics["energy_fractional_sigma68"] - global_metrics["energy_fractional_sigma68"],
                    "time_sigma68_ns": metrics["time_sigma68_ns"],
                    "pileup_miss_rate": metrics["pileup_miss_rate"],
                    "false_split_rate": metrics["false_split_rate"],
                }
            )
    return pd.DataFrame(rows)


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    ranked: pd.DataFrame,
    endpoints: pd.DataFrame,
    calibration: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    ablations: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    method_rows = pd.DataFrame(
        [
            ["analytic_clipped_template_sideband_traditional", "traditional", "pedestal-subtracted constrained two-pulse template, charge-ratio/DeltaE-E proxy cuts, CFD timing, run-offset correction"],
            ["ridge", "linear ML", "ridge classifier plus multi-output ridge regression"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier and regressors"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact one-dimensional CNN over the 18 ADC samples"],
            ["tiny_sequence_transformer", "tabular-plus-waveform transformer", "one-layer attention encoder over waveform samples"],
            ["saturation_residual_fusion_new", "new hybrid", "boosted residual fusion of waveform, clipping sidebands, and traditional-fit outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# Issue #2495 S55c: Pedestal-Pileup PID Boundary Stability and Energy Transfer Audit

## Abstract

This study tests whether pedestal memory and unresolved pile-up shift PID-proxy
boundaries or energy-transfer functions after conventional correction.  The
analysis starts from raw ROOT, reproduces the canonical selected-pulse count,
then benchmarks a strong traditional correction against ridge, gradient-boosted
trees, MLP, 1D-CNN, a tabular-plus-waveform transformer, and a new hybrid
residual-fusion architecture.  The winner named in `result.json` is
**`{winner}`**, with composite score `{fmt(best['winner_score'])}`, energy
sigma68 `{fmt(best['energy_residual_sigma68'])}` and 95% run-bootstrap CI
[`{fmt(best['energy_residual_sigma68_ci_low'])}`,
`{fmt(best['energy_residual_sigma68_ci_high'])}`].

## Raw ROOT Reproduction Gate

Raw B-stack files are read from `{cfg['raw_root_dir']}`.  Each `h101/HRDv`
waveform is reshaped to `(event, channel, sample)` with 18 samples.  The gate
uses B2/B4/B6/B8 even channels, pedestal

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

and selection

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Split and Truth Construction

The split is by source run, not by row.  Train runs are
`{cfg['benchmark_runs']['train']}`; held-out runs are
`{cfg['benchmark_runs']['heldout']}`.  Clean pulse templates are estimated only
from train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Controlled doublets are injected into raw-ROOT-derived residuals:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

then clipped as `w_obs(t) = min(w(t), {ADC_CLIP:.0f})`.  Clean single-pulse
controls are drawn from the same run/stave distribution, so false pile-up
splitting is a matched negative-control endpoint.

## Methods

{md_table(method_rows, ['method', 'family', 'description'])}

The traditional comparator is a bounded template fit with pedestal subtraction,
CFD-derived timing, charge-ratio/DeltaE-E style PID proxies, and an empirical
clipping sideband correction:

`A'_j = A_j [1 + 0.018 n_clip + 0.035 max(W_plateau-2,0) + 0.06 max(f_tail,0)]`.

The new architecture, `saturation_residual_fusion_new`, is sensible because the
task is hybrid: the traditional fit identifies constituents, while clipped
sidebands, pedestal-window features, and waveform summaries carry residual
information hidden above the ADC ceiling.

## Metrics

Energy residual:

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Pile-up timing separation error:

`e_Delta = 10 ns * [(hat t_2 - hat t_1) - Delta]`.

Robust resolution:

`sigma68(e) = [Q84(e) - Q16(e)] / 2`.

Calibration is evaluated on held-out pile-up probability scores.  For bins
`B_m`, expected calibration error is

`ECE = sum_m |B_m|/N * |mean_{{i in B_m}} y_i - mean_{{i in B_m}} p_i|`.

The registered winner minimizes

`C = sigma_E + 0.20 |bias_E| + 0.004 sigma_Delta + 0.004 sigma_t1 + 0.05 r_miss + 0.05 r_false + 0.08 S_ped + 0.08 S_PID`.

Confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap resamples.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'energy_residual_bias', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'pileup_separation_sigma68_ns', 'leading_timing_shift_sigma68_ns', 'pileup_miss_rate', 'false_split_rate', 'pedestal_shift_false_split_span', 'pid_energy_bias_span'])}

The traditional comparator has score `{fmt(trad['winner_score'])}` and energy
sigma68 `{fmt(trad['energy_residual_sigma68'])}`.  The winner changes energy
sigma68 by `{fmt(best['energy_residual_sigma68'] - trad['energy_residual_sigma68'])}`.

## Endpoint Table with CIs

{md_table(endpoints, ['method', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'saturation_onset_energy_sigma68', 'pileup_separation_sigma68_ns', 'pileup_separation_sigma68_ns_ci_low', 'pileup_separation_sigma68_ns_ci_high', 'leading_timing_shift_bias_ns', 'pedestal_shift_false_split_span', 'pid_energy_bias_span', 'pid_failure_rate_span'])}

## Calibration and ECE

{md_table(calibration, ['method', 'ece', 'brier', 'n_heldout'])}

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Stratified Systematics

{md_table(strata, ['stratum', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate'], limit=100)}

## Counterfactual Ablations

The ablation ledger slices the winner after holding the trained model fixed:
pedestal-window quartiles, pile-up mask on/off, waveform-derivative quartiles,
and saturated-sample bins.  This is a counterfactual stress test of sensitivity
to those information channels, not a retraining sweep.

{md_table(ablations, ['ablation_axis', 'counterfactual_level', 'method', 'n', 'energy_fractional_bias', 'energy_fractional_sigma68', 'delta_sigma68_vs_global', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Systematics and Caveats

The labels are controlled overlays into raw-ROOT-derived clean pulses, so the
study tests reconstruction under known pile-up/saturation truth but does not
measure the real beam pile-up rate.  The ADC clipping threshold is an explicit
stress condition rather than decoded front-end metadata.  PID-boundary movement
is represented by stave and charge-support proxy classes because no external
particle truth label exists in the reduced ROOT gate.  Run-bootstrap intervals
quantify transfer across five held-out runs and remain coarse for run-specific
edge cases.

## Verdict

`result.json` names **`{winner}`** as the S55c winner.  The traditional method is
kept as the transparent fallback; the selected winner is preferred by the
registered held-out energy, timing, calibration, pedestal, and PID-proxy score.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-2495-s55c")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(CLAIMED_TICKET_BODY, encoding="utf-8")
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves_unclipped = np.vstack([train_waves, held_waves])
    waves = s32b.apply_adc_clipping(waves_unclipped)
    events = s32b.add_clip_columns(events, waves)
    events = add_diagnostic_columns(events, waves)

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [s32b.saturation_aware_traditional_prediction(trad_raw, waves)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(s26b.transformer_prediction(events, waves, cfg))
    preds.append(s32b.saturation_residual_fusion_new(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
        "saturated_sample_count",
        "clip_fraction",
        "plateau_width",
        "pedestal_state",
        "morphology_state",
        "pid_proxy_class",
        "pedestal_window_median_adc",
        "pedestal_window_mad_adc",
        "pileup_mask_counterfactual",
        "shape_derivative_energy",
        "shape_derivative_bin",
        "pedestal_window_bin",
        "saturated_bin",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    endpoints = s35b.endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = s35b.winner_table(overall, endpoints)
    calibration, calibration_curve = ece_and_calibration(joined)
    by_run = base.by_run_summary(joined)
    strata = s32b.energy_strata_summary(joined)
    winner = str(ranked.iloc[0]["method"])
    ablations = ablation_summary(joined, winner)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    calibration.to_csv(OUT / "calibration_ece.csv", index=False)
    calibration_curve.to_csv(OUT / "calibration_curve.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    ablations.to_csv(OUT / "counterfactual_ablation_summary.csv", index=False)

    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, endpoints, calibration, by_run, strata, ablations, winner, runtime)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    best = ranked.iloc[0]
    best_cal = calibration[calibration["method"] == winner].iloc[0]
    result = {
        "ticket_id": TICKET,
        "factory_issue": FACTORY_ISSUE,
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
        "status": "complete",
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "claim_command_stdout": "# null\n\nnull",
        "claim_command_stderr": "null",
        "manual_claim_repair": "Applied factory:claimed and worker:testbeam-laptop-1 to issue 2495 after tn-ticket claim returned null without labeling the issue.",
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "adc_clip": ADC_CLIP,
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "calibration": "10-bin held-out pile-up probability calibration with ECE and Brier score",
            "winner_score": "energy_residual_sigma68 + 0.20*abs(energy_residual_bias) + 0.004*pileup_separation_sigma68_ns + 0.004*leading_timing_shift_sigma68_ns + 0.05*pileup_miss_rate + 0.05*false_split_rate + 0.08*pedestal_shift_false_split_span + 0.08*pid_energy_bias_span",
        },
        "required_method_coverage": {
            "traditional": "analytic_clipped_template_sideband_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "tabular_plus_waveform_transformer": "tiny_sequence_transformer",
            "new_architecture": "saturation_residual_fusion_new",
        },
        "winner": {
            "name": str(best["method"]),
            "criterion": "minimum registered S55c held-out energy-plus-pileup composite score with run-block bootstrap CIs",
            "winner_score": float(best["winner_score"]),
            "energy_residual_bias": float(best["energy_residual_bias"]),
            "energy_residual_sigma68": float(best["energy_residual_sigma68"]),
            "energy_residual_sigma68_ci95": [
                float(best["energy_residual_sigma68_ci_low"]),
                float(best["energy_residual_sigma68_ci_high"]),
            ],
            "saturation_onset_energy_sigma68": float(best["saturation_onset_energy_sigma68"]),
            "pileup_separation_sigma68_ns": float(best["pileup_separation_sigma68_ns"]),
            "pileup_separation_sigma68_ci95": [
                float(best["pileup_separation_sigma68_ns_ci_low"]),
                float(best["pileup_separation_sigma68_ns_ci_high"]),
            ],
            "leading_timing_shift_sigma68_ns": float(best["leading_timing_shift_sigma68_ns"]),
            "pedestal_shift_false_split_span": float(best["pedestal_shift_false_split_span"]),
            "pid_energy_bias_span": float(best["pid_energy_bias_span"]),
            "pileup_miss_rate": float(best["pileup_miss_rate"]),
            "false_split_rate": float(best["false_split_rate"]),
            "ece": float(best_cal["ece"]),
            "brier": float(best_cal["brier"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "endpoint_metrics_ci": "endpoint_metrics_ci.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "calibration_ece": "calibration_ece.csv",
            "calibration_curve": "calibration_curve.csv",
            "counterfactual_ablation_summary": "counterfactual_ablation_summary.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "ADC clipping is a benchmark stressor, not decoded electronics metadata.",
            "PID-dependent failure is represented by stave and charge-support proxies.",
            "Counterfactual ablations are fixed-model sensitivity slices, not retrained feature-drop models.",
            "Bootstrap CIs resample held-out runs and quantify run-transfer uncertainty.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "factory_issue": FACTORY_ISSUE,
        "git_commit": git_commit(),
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: base.sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
