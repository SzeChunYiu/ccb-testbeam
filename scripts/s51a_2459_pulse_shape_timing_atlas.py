#!/usr/bin/env python3
"""Ticket #2459 pulse-shape timing atlas benchmark."""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as seqbase  # noqa: E402
import s36b_1784064858_859_4e603bae_overlapping_pulse_timing_deconvolution_bakeoff as s36b  # noqa: E402


TICKET = "2459"
TITLE = "S51a: Constant-fraction timing versus waveform ML for pile-up aware pulse-shape atlas"
WORKER = "testbeam-laptop-1"
SLUG = "s51a_constant_fraction_waveform_ml_pulse_shape_timing_atlas"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S51a",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026081601,
            "max_clean_pulses_per_run_stave": 96,
            "injected_per_train_run": 56,
            "clean_per_train_run": 56,
            "injected_per_heldout_run": 76,
            "clean_per_heldout_run": 76,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 88, "cnn_channels": 12, "max_iter": 260})
    return cfg


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def md_table(df: pd.DataFrame, cols: List[str], limit: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def timing_atlas_rank(overall: pd.DataFrame, endpoints: pd.DataFrame) -> pd.DataFrame:
    merged = overall.merge(endpoints, on="method", how="left")
    merged["winner_score"] = (
        merged["leading_edge_time_sigma68_ns"] / 18.0
        + merged["secondary_pulse_delay_sigma68_ns"] / 24.0
        + 1.35 * merged["shape_residual_proxy_median"]
        + 2.5 * merged["energy_proxy_distortion_sigma68"]
        + 0.55 * merged["pileup_miss_rate"]
        + 0.55 * merged["false_split_rate"]
        + 1.5 * merged["pedestal_shift_false_split_rate"].fillna(0.0)
        + 2.0 * merged["pid_confusion_stave_bias_span"].fillna(0.0)
    )
    return merged.sort_values(["winner_score", "leading_edge_time_sigma68_ns", "time_sigma68_ns"]).reset_index(drop=True)


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    overall: pd.DataFrame,
    endpoints: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    source_ci: pd.DataFrame,
    calibration: pd.DataFrame,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "two_pulse_template_cfd_baseline"].iloc[0]
    methods = pd.DataFrame(
        [
            ["two_pulse_template_cfd_baseline", "traditional", "constant-fraction initialized aligned template/time-warp fit"],
            ["ridge", "linear ML", "ridge classifier and multi-output ridge regression on hand pulse features"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier and regressors"],
            ["mlp", "neural network", "multilayer perceptron on normalized waveform summaries"],
            ["1d_cnn", "neural network", "compact one-dimensional CNN over 18 ADC samples"],
            ["temporal_convolution_tcn", "neural sequence", "dilated temporal CNN with timing-scale head"],
            ["tiny_sequence_transformer", "neural sequence", "one-layer self-attention encoder over the waveform window"],
            ["pileup_mask_transformer_new", "new architecture", "attention encoder with deterministic late-curvature pile-up mask"],
            ["template_residual_boosted_stack_new", "new hybrid", "boosted residual stack on top of template/time-warp outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S51a: Constant-Fraction Timing Versus Waveform ML Pulse-Shape Atlas

## Abstract

Ticket `#{TICKET}` requested a raw-ROOT-anchored, academic-grade benchmark of
traditional leading-edge/constant-fraction and template time-warp timing against
ridge, gradient-boosted trees, MLP, 1D-CNN, transformer-style sequence models,
and a sensible new architecture.  Worker `{WORKER}` claimed the ticket for
project `testbeam`.  The selected winner in `result.json` is
**`{best['method']}`**, with registered atlas score `{fmt(best['winner_score'])}`,
leading-edge timing sigma68 `{fmt(best['leading_edge_time_sigma68_ns'])}` ns
and 95% run-block CI
[`{fmt(best['leading_edge_time_sigma68_ns_ci_low'])}`,
`{fmt(best['leading_edge_time_sigma68_ns_ci_high'])}`].

## Raw ROOT Reproduction

Raw inputs are `{cfg['raw_root_dir']}/hrdb_run_*.root`.  Each file is read from
`h101/HRDv` and reshaped to `(event, channel, sample)`.  The B2/B4/B6/B8 anchor
uses pedestal

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`

and selected-pulse indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Split, Templates, And Synthetic Truth

Train and test units are disjoint by source run.  Train runs are
`{cfg['benchmark_runs']['train']}` and held-out runs are
`{cfg['benchmark_runs']['heldout']}`.  Stave templates are estimated only from
train-run clean pulses:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Controlled pulse pairs are injected as

`w(t)=A_1T_s(t-t_1)+rA_1T_s(t-t_1-Delta)+epsilon_rs(t)+p`,

where `epsilon_rs(t)` is a run-local raw-pulse residual and `p` is a pedestal
excursion.  Clean single-pulse controls use the same residual and amplitude
spectrum.  This design gives exact timing, shape, pile-up, and saturation-onset
truth while preserving raw waveform noise and run structure.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The traditional comparator fits one- and two-pulse hypotheses by

`SSE_k = sum_t [w(t)-b-sum_{{j=1}}^k A_j T_s(t-t_j)]^2`,

using constant-fraction/optimal-filter seeds and a bounded time-warp grid.  The
new architecture is `pileup_mask_transformer_new`; it supplies attention with a
label-free late-curvature mask beginning just after the observed primary peak,
which is sensible for unresolved second-pulse timing.

## Metrics And Uncertainty

Leading timing error is `e_1 = 10 ns (hat t_1-t_1)`.  Secondary separation error
is `e_Delta = 10 ns [(hat t_2-hat t_1)-Delta]`.  Robust width is

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

The atlas shape residual is

`R_shape = median sqrt((e_1/20)^2 + (e_2/20)^2 + (e_E/0.20)^2)`.

Bootstrap CIs are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` resamples of held-out runs.  The
registered winner minimizes

`C = sigma_1/18 + sigma_Delta/24 + 1.35 R_shape + 2.5 sigma_E + 0.55 r_miss + 0.55 r_false + 1.5 r_ped + 2 B_stave`.

## Overall Held-Out Metrics

{md_table(overall, ['method', 'detection_ap', 'detection_auc', 'time_bias_ns', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

## Endpoint Table With CIs

{md_table(endpoints, ['method', 'leading_edge_time_sigma68_ns', 'leading_edge_time_sigma68_ns_ci_low', 'leading_edge_time_sigma68_ns_ci_high', 'secondary_pulse_delay_sigma68_ns', 'secondary_pulse_delay_sigma68_ns_ci_low', 'secondary_pulse_delay_sigma68_ns_ci_high', 'shape_residual_proxy_median', 'saturation_interaction_energy_sigma68', 'pedestal_shift_false_split_rate', 'energy_proxy_distortion_sigma68', 'pid_confusion_stave_bias_span'])}

## Winner Table

{md_table(ranked, ['method', 'winner_score', 'leading_edge_time_sigma68_ns', 'secondary_pulse_delay_sigma68_ns', 'shape_residual_proxy_median', 'energy_proxy_distortion_sigma68', 'pileup_miss_rate', 'false_split_rate', 'pedestal_shift_false_split_rate', 'pid_confusion_stave_bias_span'])}

The traditional template/time-warp baseline scored `{fmt(trad['winner_score'])}`
with leading-edge sigma68 `{fmt(trad['leading_edge_time_sigma68_ns'])}` ns.  The
winner changes leading-edge sigma68 by
`{fmt(best['leading_edge_time_sigma68_ns'] - trad['leading_edge_time_sigma68_ns'])}`
ns and secondary-delay sigma68 by
`{fmt(best['secondary_pulse_delay_sigma68_ns'] - trad['secondary_pulse_delay_sigma68_ns'])}`
ns.

## Run-Stratified Stability

{md_table(by_run, ['method', 'heldout_run', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

## Source-Unit Bootstrap

Source units are `source_run:stave:is_overlap:spacing_bin:ratio_bin`, preserving
run residuals, stave/PID proxy, overlap status, delay family, and amplitude-ratio
family.

{md_table(source_ci, ['method', 'n_source_units', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'detection_ap', 'detection_ap_ci_low', 'detection_ap_ci_high', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high'])}

## Timing-Uncertainty Calibration

{md_table(calibration, ['method', 'n_detected_overlap', 'median_predicted_timing_uncertainty_ns', 'empirical_coverage_1sigma', 'empirical_coverage_2sigma', 'mean_abs_timing_error_ns'])}

## Strata And Systematics

The stratum scan covers pile-up spacing, amplitude ratio, stave, and overlap
state:

{md_table(strata, ['stratum', 'value', 'method', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'], limit=80)}

The main caveat is that truth comes from controlled injections into
raw-ROOT-derived clean pulses; the study quantifies reconstruction capability,
not the real beam pile-up rate.  Saturation onset is an amplitude-ceiling stress
test, not decoded front-end metadata.  Pedestal drift is represented through
run-local residuals and clean-control false splitting, and PID movement is a
stave-conditioned proxy because external species labels are absent in the raw
gate.  With 18 samples per window, sub-sample timing below one digitizer tick is
model-dependent and should be promoted only with independent hardware truth.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(f"{TICKET}\n# {TITLE}\n", encoding="utf-8")
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

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [base.template_prediction(trad_raw)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(s36b.tcn_prediction(events, waves, cfg))
    preds.append(seqbase.transformer_prediction(events, waves, cfg))
    preds.append(s36b.pileup_mask_transformer_prediction(events, waves, cfg))
    preds.append(base.add_residual_stack(events, waves, trad_raw, int(cfg["random_seed"])))

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
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    endpoints = s36b.endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = timing_atlas_rank(overall, endpoints)
    by_run = base.by_run_summary(joined)
    strata = base.strata_summary(joined)
    source_ci = s36b.source_unit_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    calibration = s36b.uncertainty_calibration(joined)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    source_ci.to_csv(OUT / "injection_source_bootstrap_ci.csv", index=False)
    calibration.to_csv(OUT / "uncertainty_calibration.csv", index=False)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    runtime = time.time() - started
    write_report(cfg, match, template_summary, overall, endpoints, ranked, by_run, strata, source_ci, calibration, runtime)

    best = ranked.iloc[0]
    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "manual_claim_repair": "tn-ticket claim returned null|null|null because its existing-claim jq emits null fields; issue #2459 was label-swapped once with gh.",
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
            "run_block_bootstrap": "held-out source_run percentile 95% CI",
            "source_unit_bootstrap": "source_run:stave:is_overlap:spacing_bin:ratio_bin percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control": "clean single-pulse controls with matched source-run distribution",
            "winner_score": "S51a timing atlas score: sigma1/18 + sigmaDelta/24 + 1.35*shape + 2.5*energy + penalties for miss, false split, pedestal, and stave/PID proxy bias",
        },
        "required_method_coverage": {
            "traditional": "two_pulse_template_cfd_baseline",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "temporal_convolution_tcn": "temporal_convolution_tcn",
            "sequence_transformer": "tiny_sequence_transformer",
            "new_architecture": "pileup_mask_transformer_new",
            "hybrid_new_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": str(best["method"]),
            "criterion": "minimum S51a run-held-out timing-atlas composite score with bootstrap CIs reported",
            "winner_score": float(best["winner_score"]),
            "leading_edge_time_sigma68_ns": float(best["leading_edge_time_sigma68_ns"]),
            "leading_edge_time_sigma68_ci95": [
                float(best["leading_edge_time_sigma68_ns_ci_low"]),
                float(best["leading_edge_time_sigma68_ns_ci_high"]),
            ],
            "secondary_pulse_delay_sigma68_ns": float(best["secondary_pulse_delay_sigma68_ns"]),
            "secondary_pulse_delay_sigma68_ci95": [
                float(best["secondary_pulse_delay_sigma68_ns_ci_low"]),
                float(best["secondary_pulse_delay_sigma68_ns_ci_high"]),
            ],
            "shape_residual_proxy_median": float(best["shape_residual_proxy_median"]),
            "time_sigma68_ns": float(best["time_sigma68_ns"]),
            "energy_proxy_distortion_sigma68": float(best["energy_proxy_distortion_sigma68"]),
            "pileup_miss_rate": float(best["pileup_miss_rate"]),
            "false_split_rate": float(best["false_split_rate"]),
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
            "injection_source_bootstrap_ci": "injection_source_bootstrap_ci.csv",
            "uncertainty_calibration": "uncertainty_calibration.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "Saturation onset is represented by an amplitude-ceiling proxy rather than electronics flags.",
            "PID deltas use stave-conditioned energy-bias movement because external species truth is absent.",
            "Run-block bootstrap covers observed held-out runs, not unobserved beam configurations.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": TICKET,
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


if __name__ == "__main__":
    main()
