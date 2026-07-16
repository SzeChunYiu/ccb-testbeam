#!/usr/bin/env python3
"""S39b clipped-template energy recovery vs neural saturation inversion."""

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
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b  # noqa: E402
import s35b_1784063447_914_74ba7793_saturation_pileup_energy_recovery_benchmark as s35b  # noqa: E402


TICKET = "1784176169.768.033348a9"
TITLE = "S39b: clipped-template energy recovery vs neural saturation inversion"
WORKER = "testbeam-laptop-2"
SLUG = "s39b_clipped_template_energy_recovery_vs_neural_saturation_inversion"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
CLAIMED_TICKET = """1784176169.768.033348a9
# S39b: clipped-template energy recovery vs neural saturation inversion

Academic-grade study: test whether a traditional clipped-template likelihood with pedestal-corrected charge integration can recover saturated pulse energy as robustly as learned saturation inversion. Compare the traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN, and transformer/temporal-attention models where waveform length permits. Require synthetic injection plus held-out run validation, bootstrap CIs for energy bias/resolution and saturation-onset thresholds, and stratification by pedestal, pile-up proximity, pulse shape, and ADC clipping depth. Emphasize interpretable failure maps that improve understanding of saturation and energy reconstruction.
"""


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S39b",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071602,
            "max_clean_pulses_per_run_stave": 104,
            "injected_per_train_run": 64,
            "clean_per_train_run": 64,
            "injected_per_heldout_run": 86,
            "clean_per_heldout_run": 86,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 260})
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


def endpoint_values(frame: pd.DataFrame) -> Dict[str, float]:
    positives = frame[frame["is_overlap"] == 1].copy()
    valid = positives[~positives["failed"].astype(bool)].copy()
    clean = frame[frame["is_overlap"] == 0].copy()

    if len(valid):
        true_e = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_e = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        err = (pred_e - true_e) / np.maximum(true_e, 1.0)
        saturated = valid[valid["saturated_sample_count"].to_numpy(float) > 0.0]
        if len(saturated):
            sat_true = saturated[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            sat_pred = saturated[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            sat_err = (sat_pred - sat_true) / np.maximum(sat_true, 1.0)
        else:
            sat_err = np.asarray([])
        t1_err = (valid["t1_sample"].to_numpy(float) - valid["true_t1_sample"].to_numpy(float)) * 10.0
        sep_err = (
            (valid["t2_sample"].to_numpy(float) - valid["t1_sample"].to_numpy(float))
            - valid["true_sep_sample"].to_numpy(float)
        ) * 10.0
        stave_bias = []
        for _stave, group in valid.groupby("stave"):
            gt = group[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            gp = group[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            stave_bias.append(float(np.median((gp - gt) / np.maximum(gt, 1.0))))
    else:
        err = sat_err = t1_err = sep_err = np.asarray([])
        stave_bias = []

    true_onset = positives[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float) > 11000.0
    pred_onset = positives[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float) > 11000.0
    false_split = float((clean["score"].to_numpy(float) >= 0.5).mean()) if len(clean) else float("nan")
    return {
        "energy_bias": float(np.median(err)) if len(err) else float("nan"),
        "energy_sigma68": s35b.sigma68(err),
        "saturated_energy_sigma68": s35b.sigma68(sat_err),
        "saturated_fraction": float((positives["saturated_sample_count"].to_numpy(float) > 0.0).mean()) if len(positives) else float("nan"),
        "saturation_onset_accuracy": float(np.mean(true_onset == pred_onset)) if len(positives) else float("nan"),
        "saturation_onset_calibration_abs": float(abs(np.mean(pred_onset) - np.mean(true_onset))) if len(positives) else float("nan"),
        "timing_shift_sigma68_ns": s35b.sigma68(t1_err),
        "pileup_separation_sigma68_ns": s35b.sigma68(sep_err),
        "pileup_merge_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
        "false_split_rate": false_split,
        "pid_proxy_energy_bias_span": float(np.max(stave_bias) - np.min(stave_bias)) if stave_bias else float("nan"),
    }


def endpoint_bootstrap(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    rows: List[Dict[str, object]] = []
    for method, group in held.groupby("method"):
        row: Dict[str, object] = {"method": method, **endpoint_values(group)}
        runs = np.asarray(sorted(group["source_run"].unique()))
        samples: Dict[str, List[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            for key, value in endpoint_values(boot).items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["energy_sigma68", "saturated_energy_sigma68"]).reset_index(drop=True)


def winner_table(endpoints: pd.DataFrame) -> pd.DataFrame:
    out = endpoints.copy()
    out["winner_score"] = (
        out["energy_sigma68"]
        + 0.20 * out["energy_bias"].abs()
        + 0.35 * out["saturation_onset_calibration_abs"]
        + 0.004 * out["pileup_separation_sigma68_ns"]
        + 0.004 * out["timing_shift_sigma68_ns"]
        + 0.05 * out["pileup_merge_rate"]
        + 0.05 * out["false_split_rate"]
        + 0.08 * out["pid_proxy_energy_bias_span"].fillna(0.0)
    )
    return out.sort_values(["winner_score", "energy_sigma68", "saturated_energy_sigma68"]).reset_index(drop=True)


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    methods = pd.DataFrame(
        [
            ["analytic_clipped_template_sideband_traditional", "traditional", "bounded clipped-template likelihood with pedestal-corrected charge and sideband saturation correction"],
            ["ridge", "linear ML", "ridge classifier plus ridge multi-output amplitude/time regression"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier and regressors on waveform features"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact convolution over the 18 ADC samples"],
            ["tiny_sequence_transformer", "temporal attention", "one-layer self-attention encoder over samples"],
            ["saturation_residual_fusion_new", "new hybrid", "boosted residual fusion of waveform, clipping sidebands, and traditional fit outputs"],
        ],
        columns=["method", "family", "description"],
    )
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    text = f"""# S39b: Clipped-Template Energy Recovery vs Neural Saturation Inversion

## Abstract

Ticket `{TICKET}` asks whether a strong traditional clipped-template likelihood
with pedestal-corrected charge integration can recover saturated pulse energy as
robustly as learned saturation inversion.  The raw selected-pulse anchor was
reproduced from ROOT before model training.  The held-out winner written to
`result.json` is **`{winner}`**, with score `{fmt(best['winner_score'])}`,
energy sigma68 `{fmt(best['energy_sigma68'])}` and 95% run-block bootstrap CI
[`{fmt(best['energy_sigma68_ci_low'])}`, `{fmt(best['energy_sigma68_ci_high'])}`].

## Raw ROOT Reproduction

The B-stack ROOT files were read from `{cfg['raw_root_dir']}`.  The repository
`data/` directory is empty in this worker checkout, so the documented extracted
ROOT data folder under `/home/billy/ccb-data` was used.  The reproduction gate
uses B2/B4/B6/B8 waveforms with pedestal

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`

and selected-pulse indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Experimental Design

The split is by source run.  Training runs are `{cfg['benchmark_runs']['train']}`;
held-out validation runs are `{cfg['benchmark_runs']['heldout']}`.  Synthetic
doublets and matched clean controls are generated from raw-ROOT-derived clean
pulses, then clipped at `{s32b.ADC_CLIP:.0f}` ADC:

`w_obs(t) = min(A_1 T_s(t-t_1) + A_2 T_s(t-t_2) + epsilon_rs(t) + p, ADC_clip)`.

Templates are estimated only from training runs:

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The traditional comparator minimizes

`SSE_k = sum_t [w_obs(t) - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2`

over one- and two-pulse hypotheses and then applies an interpretable saturation
sideband correction from clipped sample count, plateau width, and late-tail
fraction.  The new architecture is sensible because the traditional fit
identifies pulse constituents, while waveform and clipping sidebands carry
residual information about charge hidden above the ADC ceiling.

## Endpoints and Winner Rule

The energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Robust resolution is `sigma68(e) = [Q84(e) - Q16(e)] / 2`.  Saturation onset is
the controlled high-amplitude proxy `A_1 + A_2 > 11000 ADC`; the calibration
error is the absolute predicted-minus-true onset fraction.  The winner minimizes

`C = sigma_E + 0.20 |bias_E| + 0.35 cal_sat + 0.004 sigma_Delta + 0.004 sigma_t + 0.05 r_merge + 0.05 r_false + 0.08 S_PID`.

Confidence intervals are 95% percentile intervals from `{int(cfg['ml']['bootstrap_samples'])}`
held-out run-block bootstrap resamples.

## Main Results

{md_table(ranked, ['method', 'winner_score', 'energy_bias', 'energy_bias_ci_low', 'energy_bias_ci_high', 'energy_sigma68', 'energy_sigma68_ci_low', 'energy_sigma68_ci_high', 'saturated_energy_sigma68', 'saturation_onset_accuracy', 'saturation_onset_calibration_abs', 'pileup_merge_rate', 'false_split_rate', 'pid_proxy_energy_bias_span'])}

The traditional comparator score is `{fmt(trad['winner_score'])}`.  The winning
method changes energy sigma68 relative to the traditional comparator by
`{fmt(best['energy_sigma68'] - trad['energy_sigma68'])}`.

## Held-Out Run Stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Stratified Failure Maps

The systematic scan covers pedestal state, pile-up proximity, pulse-shape tail
state, ADC clipping depth, amplitude ratio, stave, and PID proxy support:

{md_table(strata, ['stratum', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate'], limit=120)}

## Systematics and Caveats

Truth is controlled-injection truth, not hand-labeled beam truth.  The saturation
threshold is an explicit ADC clipping stressor and onset proxy rather than a
decoded hardware flag.  The 18-sample waveform is short for attention models;
therefore the transformer is a compact temporal-attention comparator rather than
a large sequence model.  PID migration is approximated by B-stave and charge
support because external particle labels are unavailable in this raw ROOT gate.
Run-block bootstrap intervals quantify transfer across held-out runs and are
not event-counting errors.

## Verdict

`result.json` names **{winner}** as the S39b winner.  The interpretable
clipped-template method remains the audit baseline; the winner is preferred only
for the declared held-out energy, saturation-onset, and pile-up score.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(CLAIMED_TICKET, encoding="utf-8")
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
    waves = s32b.apply_adc_clipping(np.vstack([train_waves, held_waves]))
    events = s32b.add_clip_columns(events, waves)

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
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    endpoints = endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(endpoints)
    by_run = base.by_run_summary(joined)
    strata = s32b.energy_strata_summary(joined)

    endpoints.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, by_run, strata, winner, runtime)

    best = ranked.iloc[0]
    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
        "claimed_ticket_text": CLAIMED_TICKET,
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
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
            "adc_clip": s32b.ADC_CLIP,
            "synthetic_injection": "raw-ROOT-derived clean pulses plus run-local residuals and matched clean controls",
            "bootstrap": "held-out source_run percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "strata": ["pedestal_state", "spacing_bin", "morphology_state", "saturation_bin", "ratio_bin", "stave", "pid_proxy_class"],
            "winner_score": "energy_sigma68 + 0.20*abs(energy_bias) + 0.35*saturation_onset_calibration_abs + 0.004*pileup_separation_sigma68_ns + 0.004*timing_shift_sigma68_ns + 0.05*pileup_merge_rate + 0.05*false_split_rate + 0.08*pid_proxy_energy_bias_span",
        },
        "required_method_coverage": {
            "traditional": "analytic_clipped_template_sideband_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_temporal_attention": "tiny_sequence_transformer",
            "new_architecture": "saturation_residual_fusion_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum S39b held-out energy, saturation-onset, timing, and pile-up composite score",
            "winner_score": float(best["winner_score"]),
            "energy_bias": float(best["energy_bias"]),
            "energy_bias_ci95": [float(best["energy_bias_ci_low"]), float(best["energy_bias_ci_high"])],
            "energy_sigma68": float(best["energy_sigma68"]),
            "energy_sigma68_ci95": [float(best["energy_sigma68_ci_low"]), float(best["energy_sigma68_ci_high"])],
            "saturated_energy_sigma68": float(best["saturated_energy_sigma68"]),
            "saturation_onset_accuracy": float(best["saturation_onset_accuracy"]),
            "saturation_onset_calibration_abs": float(best["saturation_onset_calibration_abs"]),
            "pileup_merge_rate": float(best["pileup_merge_rate"]),
            "false_split_rate": float(best["false_split_rate"]),
            "pid_proxy_energy_bias_span": float(best["pid_proxy_energy_bias_span"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled synthetic injection into raw-ROOT-derived clean pulses.",
            "Saturation onset uses a high-amplitude ADC proxy rather than decoded electronics flags.",
            "PID migration is represented by stave and charge-support stability proxies.",
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
