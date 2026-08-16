#!/usr/bin/env python3
"""S54b Wiener-tail deconvolution versus neural late-pile-up recovery.

Ticket #2479 asks for an academic-grade raw-ROOT anchored benchmark of a strong
traditional Wiener/template-tail method against ridge, boosted trees, MLP,
1D-CNN, and neural sequence models for late pile-up and saturation recovery.
The implementation deliberately reuses the audited S25/S26/S40 controlled
two-pulse machinery so the new ticket changes only the registered endpoint and
method panel, not the raw selector semantics.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as seqbase  # noqa: E402
import s40b_1784179132_836_139e76b1_pileup_onset_timing_resolution_frontier as s40b  # noqa: E402

TICKET = "2479"
ISSUE_TITLE = "S54b: Wiener-tail deconvolution versus neural late-pile-up saturation recovery"
WORKER = "testbeam-laptop-2"
SLUG = "s54b_wiener_tail_deconvolution_neural_late_pileup_saturation_recovery"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S54b",
            "ticket_id": TICKET,
            "title": ISSUE_TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026081602,
            "max_clean_pulses_per_run_stave": 100,
            "injected_per_train_run": 64,
            "clean_per_train_run": 64,
            "injected_per_heldout_run": 84,
            "clean_per_heldout_run": 84,
            "benchmark_runs": {
                "train": [44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 55, 56],
                "heldout": [50, 57, 58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 180, "cnn_epochs": 70, "cnn_channels": 12, "max_iter": 240})
    return cfg


def wiener_tail_deconvolution_prediction(events: pd.DataFrame, waveforms: np.ndarray, trad: pd.DataFrame) -> pd.DataFrame:
    """Traditional Wiener-like tail suppressor around the bounded template fit.

    The reduced waveform is only 18 samples, so the method uses a short
    train-free frequency-domain tail attenuation rather than a large estimated
    noise covariance.  The deterministic filter preserves the primary rise,
    damps late high-frequency residuals, and combines the filtered late-tail
    energy with the two-pulse template improvement.
    """

    corrected = waveforms - np.median(waveforms[:, :4], axis=1, keepdims=True)
    n = corrected.shape[1]
    freqs = np.fft.rfftfreq(n)
    signal_power = np.abs(np.fft.rfft(corrected, axis=1)) ** 2
    noise_floor = np.median(signal_power[:, -3:], axis=1, keepdims=True)
    gain = signal_power / np.maximum(signal_power + noise_floor + 1e-9, 1e-9)
    tail_taper = 1.0 / (1.0 + (freqs / 0.22) ** 4)
    filtered = np.fft.irfft(np.fft.rfft(corrected, axis=1) * gain * tail_taper[None, :], n=n, axis=1)

    peak = np.argmax(filtered, axis=1)
    tail_ratio = []
    curvature_tail = []
    for i, p in enumerate(peak):
        body = filtered[i, max(0, int(p) - 2) : min(n, int(p) + 4)]
        tail = filtered[i, min(n - 1, int(p) + 4) :]
        tail_ratio.append(float(np.maximum(tail, 0.0).sum() / max(np.maximum(body, 0.0).sum(), 1.0)))
        curvature_tail.append(float(np.abs(np.diff(tail, n=2)).sum()) if len(tail) >= 3 else 0.0)
    tail_ratio = np.asarray(tail_ratio)
    curvature_tail = np.asarray(curvature_tail)

    template_score = np.nan_to_num(trad["trad_score"].to_numpy(float), nan=-0.5, neginf=-0.5)
    score = 1.0 / (1.0 + np.exp(-9.0 * (template_score + 0.72 * tail_ratio + 0.0004 * curvature_tail - 0.095)))
    max_amp = np.maximum(corrected.max(axis=1), 1.0)
    amp2 = np.clip(max_amp * np.clip(0.18 + 1.15 * tail_ratio, 0.0, 1.05), 0.0, None)
    out = base.template_prediction(trad).copy()
    out["method"] = "wiener_tail_deconvolution_traditional"
    out["score"] = score
    out["failed"] = np.asarray(score < 0.5) | trad["trad_failed"].to_numpy(bool)
    out["amp2_adc"] = np.where(out["failed"], out["amp2_adc"], 0.55 * out["amp2_adc"] + 0.45 * amp2)
    out["amp1_adc"] = np.clip(max_amp - 0.22 * out["amp2_adc"], 0.0, None)
    out["t2_sample"] = np.clip(out["t1_sample"].to_numpy(float) + 1.8 + 4.0 * np.clip(tail_ratio, 0.0, 1.0), 0.0, 17.0)
    return out


def merge_predictions(events: pd.DataFrame, preds: List[pd.DataFrame]) -> pd.DataFrame:
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
    ]
    return all_pred.merge(events[base_cols], on="event_id", how="left")


def evaluate_method_panel(events: pd.DataFrame, waveforms: np.ndarray, templates: Dict[str, np.ndarray], cfg: dict) -> pd.DataFrame:
    trad_raw = p05a.run_template_fits(events, waveforms, templates, cfg)
    preds = [
        wiener_tail_deconvolution_prediction(events, waveforms, trad_raw),
        s40b.template_likelihood_prediction(trad_raw),
        s40b.leading_edge_cfd_prediction(events, waveforms),
        s40b.residual_tail_veto_prediction(events, waveforms, trad_raw),
    ]
    preds.extend(base.run_sklearn_methods(events, waveforms, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waveforms, cfg))
    preds.append(seqbase.transformer_prediction(events, waveforms, cfg))
    preds.append(s40b.causal_window_transformer_prediction(events, waveforms, cfg))
    preds.append(base.add_residual_stack(events, waveforms, trad_raw, int(cfg["random_seed"])))
    return merge_predictions(events, preds)


def endpoint_values(frame: pd.DataFrame) -> Dict[str, float]:
    vals = s40b.endpoint_values(frame)
    positives = frame[frame["is_overlap"] == 1]
    valid = positives[~positives["failed"].astype(bool)].copy()
    if len(valid):
        true_e = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_e = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        eerr = (pred_e - true_e) / np.maximum(true_e, 1.0)
        late = valid[valid["true_sep_sample"].to_numpy(float) >= 3.0]
        if len(late):
            pred_delay = (late["t2_sample"].to_numpy(float) - late["t1_sample"].to_numpy(float)) * 10.0
            true_delay = late["true_sep_sample"].to_numpy(float) * 10.0
            late_delay_err = pred_delay - true_delay
        else:
            late_delay_err = np.asarray([])
    else:
        eerr = late_delay_err = np.asarray([])
    vals.update(
        {
            "saturated_sample_energy_recovery_sigma68": vals["saturation_interaction_energy_sigma68"],
            "late_pileup_delay_bias_ns": float(np.median(late_delay_err)) if len(late_delay_err) else float("nan"),
            "late_pileup_delay_sigma68_ns": s40b.sigma68(late_delay_err),
            "failure_tail_rate": vals["false_merge_rate"],
            "tail_residual_sigma68": s40b.sigma68(eerr),
            "pedestal_dependence": vals["pedestal_shift_false_split_rate"],
        }
    )
    return vals


def endpoint_bootstrap(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    rows = []
    for method, group in held.groupby("method"):
        row: Dict[str, object] = {"method": method, **endpoint_values(group)}
        runs = sorted(group["source_run"].unique())
        samples: Dict[str, List[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            vals = endpoint_values(boot)
            for key, value in vals.items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def winner_table(overall: pd.DataFrame, endpoints: pd.DataFrame) -> pd.DataFrame:
    merged = overall.merge(endpoints, on="method", how="left")
    merged["winner_score"] = (
        1.3 * merged["late_pileup_delay_sigma68_ns"] / 30.0
        + merged["leading_edge_time_sigma68_ns"] / 25.0
        + 2.8 * merged["saturated_sample_energy_recovery_sigma68"]
        + 1.5 * merged["tail_residual_sigma68"]
        + 0.8 * merged["failure_tail_rate"]
        + 0.7 * merged["false_split_rate"]
        + 1.5 * merged["pid_confusion_stave_bias_span"].fillna(0.0)
    )
    return merged.sort_values(["winner_score", "late_pileup_delay_sigma68_ns", "saturated_sample_energy_recovery_sigma68"]).reset_index(drop=True)


def md_table(df: pd.DataFrame, cols: List[str], max_rows: int | None = None) -> str:
    view = df[cols].head(max_rows).copy() if max_rows else df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    overall: pd.DataFrame,
    endpoints: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    stress: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "wiener_tail_deconvolution_traditional"].iloc[0]
    methods = pd.DataFrame(
        [
            ["wiener_tail_deconvolution_traditional", "traditional", "bounded template deconvolution plus short-record Wiener tail attenuation"],
            ["two_pulse_template_likelihood_traditional", "traditional", "two-pulse template likelihood with CFD initialization"],
            ["leading_edge_cfd_traditional", "traditional", "single-pulse CFD onset with deterministic tail split score"],
            ["residual_tail_veto_traditional", "traditional", "template likelihood plus late-residual veto"],
            ["ridge", "linear ML", "ridge classifier and multi-output ridge regressor"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier/regressors"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact one-dimensional convolutional waveform model"],
            ["tiny_sequence_transformer", "neural sequence", "one-layer self-attention waveform encoder"],
            ["causal_window_transformer_new", "new neural sequence", "attention model with deterministic late-window mask channel"],
            ["template_residual_boosted_stack_new", "new hybrid", "boosted residual correction using traditional deconvolver coordinates"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S54b: Wiener-tail deconvolution versus neural late-pile-up saturation recovery

## Abstract

Ticket `#{TICKET}` asks whether a strong traditional Wiener-tail/template
deconvolver remains competitive with modern ML/NN methods for late pile-up and
clipped-pulse recovery.  The worker is `{WORKER}`.  The benchmark first
reproduced the B-stack selected-pulse count directly from raw ROOT, then compared
traditional template/Wiener methods against ridge, gradient-boosted trees, MLP,
1D-CNN, a compact transformer, and a new late-window transformer/hybrid residual
architecture.  The winner written to `result.json` is `{winner}` with composite
score `{best['winner_score']:.4g}`.  The primary traditional comparator
`wiener_tail_deconvolution_traditional` has score `{trad['winner_score']:.4g}`.

## Raw ROOT Reproduction

Input files were read from `{cfg['raw_root_dir']}/hrdb_run_*.root`.  Each
`h101/HRDv` branch was reshaped to `(event, channel, sample)`.  The four B-stack
analysis channels are B2, B4, B6, and B8.  For waveform `x_c(t)` on channel `c`,
the raw selection is

`b_c = median(x_c(0), x_c(1), x_c(2), x_c(3))`

and

`max_t [x_c(t) - b_c] > 1000 ADC`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

This gate is evaluated before model fitting and the same raw files are hashed in
`input_sha256.csv`.

## Controlled Benchmark Design

The split is by source run.  Train runs are `{cfg['benchmark_runs']['train']}`;
held-out runs are `{cfg['benchmark_runs']['heldout']}`.  Train-only clean
templates are estimated per stave:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Synthetic-over-real doublets are generated on raw-ROOT single-pulse residuals:

`w(t)=A_1 T_s(t-t_1)+rA_1 T_s(t-t_1-Delta)+epsilon_r(t)+p`,

where `Delta` is the controlled secondary-pulse spacing, `r` is the secondary
amplitude ratio, `epsilon_r(t)` is a run-local residual sampled from real clean
pulses, and `p` is a pedestal offset.  Clean negative controls share the same
source-run and amplitude support but omit the second pulse.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The traditional Wiener-tail method starts from the bounded template fit and
filters the short waveform in the frequency domain.  For frequency bin `f`,

`G(f)=S(f)/(S(f)+N) * [1+(f/f_c)^4]^-1`,

where `S(f)=|FFT(w-b)|^2`, `N` is the median high-frequency power, and the
second factor suppresses late high-frequency tail residuals.  The filtered
post-peak tail energy and curvature are combined with the template improvement

`I=(SSE_1-SSE_2)/SSE_1`,

with

`SSE_k=sum_t [w(t)-b-sum_{{j=1}}^k A_j T_s(t-t_j)]^2`.

Neural models see the same run-held-out training labels.  The new architecture
is `causal_window_transformer_new`: a compact attention encoder with a
deterministic late-window mask channel.  A hybrid `template_residual_boosted_stack_new`
is also included because this problem is plausibly helped by using the physics
fit as a low-variance coordinate system.

## Metrics and Confidence Intervals

Confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` bootstrap resamples of held-out runs:

`CI_95(theta)=[q_0.025(theta_b), q_0.975(theta_b)]`.

The registered score is

`C_m = 1.3 sigma_late/30 + sigma_lead/25 + 2.8 sigma_E + 1.5 sigma_tail + 0.8 r_fail + 0.7 r_false + 1.5 B_stave`,

where `sigma_late` is late secondary-delay sigma68, `sigma_lead` is leading-edge
timing sigma68, `sigma_E` is saturated-sample energy-recovery sigma68,
`sigma_tail` is tail residual energy sigma68, `r_fail` is false-merge/failure
tail rate, `r_false` is clean-control false split rate, and `B_stave` is a
stave/PID-proxy energy-bias span.

## Primary Held-Out Results

{md_table(overall, ['method', 'detection_ap', 'detection_auc', 'time_bias_ns', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

## Endpoint Table

{md_table(endpoints, ['method', 'late_pileup_delay_bias_ns', 'late_pileup_delay_sigma68_ns', 'late_pileup_delay_sigma68_ns_ci_low', 'late_pileup_delay_sigma68_ns_ci_high', 'saturated_sample_energy_recovery_sigma68', 'saturated_sample_energy_recovery_sigma68_ci_low', 'saturated_sample_energy_recovery_sigma68_ci_high', 'tail_residual_sigma68', 'failure_tail_rate', 'pedestal_dependence', 'pid_confusion_stave_bias_span'])}

## Winner Ranking

{md_table(ranked, ['method', 'winner_score', 'late_pileup_delay_sigma68_ns', 'leading_edge_time_sigma68_ns', 'saturated_sample_energy_recovery_sigma68', 'tail_residual_sigma68', 'failure_tail_rate', 'false_split_rate', 'pid_confusion_stave_bias_span'])}

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

## Strata and Systematics

The strata table resolves spacing, amplitude ratio, stave/PID proxy, and
saturation-proxy behavior.

{md_table(strata, ['stratum', 'value', 'method', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'energy_fractional_sigma68'], max_rows=120)}

Stress slices include clean pedestal controls, tight pile-up, high summed
amplitude, phase-shuffled controls, and high-charge amplitude sentinels.

{md_table(stress, ['stress', 'method', 'n_events', 'leading_edge_time_sigma68_ns', 'secondary_pulse_delay_sigma68_ns', 'pileup_miss_rate', 'false_split_rate', 'energy_proxy_distortion_sigma68'])}

## Interpretation, Caveats, and Use

The result should be read as a controlled raw-data benchmark, not a direct
measurement of natural beam pile-up frequency.  The truth labels are exact for
the injected second-pulse delay and amplitude, but the residual field comes from
real raw-ROOT single-pulse windows.  Saturation is represented by a high summed
amplitude proxy because electronics saturation truth flags are not present in
the reduced ROOT branch.  Pedestal dependence is measured through clean-control
false splitting and run-local residuals.  PID behavior is a stave-conditioned
energy-boundary proxy, not particle-truth PID confusion.  Finally, the waveform
has only 18 samples, so all models inherit a digitizer-sampling floor for
sub-sample deconvolution.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(
        f"{TICKET}\n# {ISSUE_TITLE}\n\nClaimed by {WORKER}; initial tn-ticket helper returned null, then the same label transition was applied to issue #{TICKET}.\n",
        encoding="utf-8",
    )
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
    waves = np.vstack([train_waves, held_waves])

    joined = evaluate_method_panel(events, waves, templates, cfg)
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    endpoints = endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall, endpoints)
    by_run = base.by_run_summary(joined)
    strata = base.strata_summary(joined)
    ablations, stress = s40b.ablation_tables(joined, joined)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    ablations.to_csv(OUT / "ablation_window_metrics.csv", index=False)
    stress.to_csv(OUT / "ablation_stress_slices.csv", index=False)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, overall, endpoints, ranked, by_run, strata, stress, winner, runtime)

    result = {
        "ticket_id": TICKET,
        "github_issue": 2479,
        "project": "testbeam",
        "worker": WORKER,
        "title": ISSUE_TITLE,
        "status": "complete",
        "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "claim_note": "The helper command was run once and returned null; issue #2479 was then claimed by applying the intended factory:open to factory:claimed plus worker label transition.",
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
            "bootstrap": "held-out source_run percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control": "clean single-pulse controls with matched source-run distribution",
            "strata": ["delta_t", "clipped/saturated proxy", "pedestal/false split", "deposited-energy proxy", "PID/stave proxy"],
        },
        "required_method_coverage": {
            "strong_traditional": "wiener_tail_deconvolution_traditional",
            "traditional_template": "two_pulse_template_likelihood_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_encoder": "tiny_sequence_transformer",
            "new_architecture": "causal_window_transformer_new",
            "new_hybrid_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum S54b composite late-pileup saturation recovery score with run-block bootstrap CIs",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "late_pileup_delay_sigma68_ns": float(ranked.iloc[0]["late_pileup_delay_sigma68_ns"]),
            "late_pileup_delay_sigma68_ci95": [
                float(ranked.iloc[0]["late_pileup_delay_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["late_pileup_delay_sigma68_ns_ci_high"]),
            ],
            "saturated_sample_energy_recovery_sigma68": float(ranked.iloc[0]["saturated_sample_energy_recovery_sigma68"]),
            "saturated_sample_energy_recovery_sigma68_ci95": [
                float(ranked.iloc[0]["saturated_sample_energy_recovery_sigma68_ci_low"]),
                float(ranked.iloc[0]["saturated_sample_energy_recovery_sigma68_ci_high"]),
            ],
            "tail_residual_sigma68": float(ranked.iloc[0]["tail_residual_sigma68"]),
            "failure_tail_rate": float(ranked.iloc[0]["failure_tail_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "endpoint_metrics_ci": "endpoint_metrics_ci.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
            "ablation_window_metrics": "ablation_window_metrics.csv",
            "ablation_stress_slices": "ablation_stress_slices.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth labels come from controlled injections into raw-ROOT-derived clean pulses.",
            "Saturation is a high summed-amplitude proxy, not a hardware saturation flag.",
            "PID behavior is represented by stave-conditioned energy-boundary proxies.",
            "The 18-sample waveform imposes a sampling floor on sub-sample deconvolution.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": TICKET,
        "github_issue": 2479,
        "git_commit": base.git_commit(),
        "command": f"{sys.executable} scripts/{Path(__file__).name}",
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
    print(json.dumps({"out": str(OUT.relative_to(ROOT)), "winner": winner, "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    main()
