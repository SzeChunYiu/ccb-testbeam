#!/usr/bin/env python3
"""S36a clipped-pulse saturation onset and shape-recovery benchmark."""

from __future__ import annotations

import json
import os
import platform
import subprocess
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


TICKET = "1784064851.786.76994f64"
TITLE = "S36a clipped-pulse saturation onset shape recovery benchmark"
WORKER = "testbeam-laptop-2"
SLUG = "s36a_clipped_pulse_saturation_onset_shape_recovery"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = ROOT / "data" / "root" / "root"
ADC_CLIP = s32b.ADC_CLIP


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S36a",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071402,
            "max_clean_pulses_per_run_stave": 112,
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
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 280})
    return cfg


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84.0) - np.percentile(values, 16.0)) / 2.0)


def auc_score(y_true: np.ndarray, score: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=int)
    score = np.asarray(score, dtype=float)
    mask = np.isfinite(score)
    y_true = y_true[mask]
    score = score[mask]
    n_pos = int(y_true.sum())
    n_neg = int(len(y_true) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(score)
    ranks = np.empty(len(score), dtype=float)
    i = 0
    while i < len(score):
        j = i + 1
        while j < len(score) and score[order[j]] == score[order[i]]:
            j += 1
        ranks[order[i:j]] = 0.5 * (i + 1 + j)
        i = j
    return float((ranks[y_true == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def reconstruct_waveform(row: pd.Series, template: np.ndarray, ref: float) -> np.ndarray:
    amp1 = float(row.get("amp1_adc", 0.0) or 0.0)
    amp2 = float(row.get("amp2_adc", 0.0) or 0.0)
    t1 = float(row.get("t1_sample", np.nan))
    t2 = float(row.get("t2_sample", np.nan))
    if bool(row.get("failed", False)) or not np.isfinite(t1) or amp1 <= 0:
        return np.full_like(template, np.nan, dtype=float)
    model = amp1 * p05a.shifted_template(template, t1, ref)
    if np.isfinite(t2) and amp2 > 0:
        model = model + amp2 * p05a.shifted_template(template, t2, ref)
    return model


def add_shape_metrics(
    predictions: pd.DataFrame,
    events: pd.DataFrame,
    waveforms_unclipped: np.ndarray,
    templates: Dict[str, np.ndarray],
    cfg: dict,
) -> pd.DataFrame:
    ref = float(cfg["template_reference_cfd_sample"])
    truth_by_event = {event_id: i for i, event_id in enumerate(events["event_id"].astype(str))}
    stave_by_event = dict(zip(events["event_id"].astype(str), events["stave"].astype(str)))
    rows = []
    for row in predictions.itertuples(index=False):
        event_id = str(row.event_id)
        idx = truth_by_event[event_id]
        template = templates[stave_by_event[event_id]]
        pred = reconstruct_waveform(pd.Series(row._asdict()), template, ref)
        truth = np.asarray(waveforms_unclipped[idx], dtype=float)
        denom = max(float(np.max(truth) - np.median(truth[:4])), 1.0)
        if np.isfinite(pred).all():
            rmse = float(np.sqrt(np.mean((pred - truth) ** 2)) / denom)
        else:
            rmse = float("nan")
        pred_e = float((row.amp1_adc if np.isfinite(row.amp1_adc) else 0.0) + (row.amp2_adc if np.isfinite(row.amp2_adc) else 0.0))
        rows.append(
            {
                "event_id": event_id,
                "method": str(row.method),
                "shape_reconstruction_rmse": rmse,
                "saturation_onset_score": pred_e / ADC_CLIP + 0.05 * float(row.score if np.isfinite(row.score) else 0.0),
            }
        )
    return predictions.merge(pd.DataFrame(rows), on=["event_id", "method"], how="left")


def endpoint_values(frame: pd.DataFrame) -> Dict[str, float]:
    positives = frame[frame["is_overlap"] == 1].copy()
    valid = positives[~positives["failed"].astype(bool)].copy()
    clean = frame[frame["is_overlap"] == 0].copy()

    if len(valid):
        true_e = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_e = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        energy_err = (pred_e - true_e) / np.maximum(true_e, 1.0)
        t1_err = (valid["t1_sample"].to_numpy(float) - valid["true_t1_sample"].to_numpy(float)) * 10.0
        saturated = valid[valid["saturated_sample_count"].to_numpy(float) > 0.0]
        if len(saturated):
            sat_true = saturated[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            sat_pred = saturated[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            sat_err = (sat_pred - sat_true) / np.maximum(sat_true, 1.0)
        else:
            sat_err = np.asarray([])
    else:
        energy_err = t1_err = sat_err = np.asarray([])

    shape = frame["shape_reconstruction_rmse"].to_numpy(float)
    sat_truth = (frame["saturated_sample_count"].to_numpy(float) > 0.0).astype(int)
    auc = auc_score(sat_truth, frame["saturation_onset_score"].to_numpy(float))
    pedestal_false = []
    for _state, group in clean.groupby("pedestal_state"):
        if len(group):
            pedestal_false.append(float((group["score"].to_numpy(float) >= 0.5).mean()))
    pid_bias = []
    for _pid, group in valid.groupby("pid_proxy_class") if len(valid) else []:
        true_g = group[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_g = group[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        pid_bias.append(float(np.median((pred_g - true_g) / np.maximum(true_g, 1.0))))
    return {
        "energy_residual_bias": float(np.median(energy_err)) if len(energy_err) else float("nan"),
        "energy_residual_sigma68": sigma68(energy_err),
        "saturation_onset_energy_sigma68": sigma68(sat_err),
        "onset_timing_bias_ns": float(np.median(t1_err)) if len(t1_err) else float("nan"),
        "onset_timing_sigma68_ns": sigma68(t1_err),
        "saturation_onset_auc": auc,
        "shape_reconstruction_rmse": float(np.nanmedian(shape)) if np.isfinite(shape).any() else float("nan"),
        "pileup_miss_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
        "false_split_rate": float((clean["score"].to_numpy(float) >= 0.5).mean()) if len(clean) else float("nan"),
        "pedestal_shift_false_split_span": float(np.max(pedestal_false) - np.min(pedestal_false)) if pedestal_false else float("nan"),
        "pid_energy_bias_span": float(np.max(pid_bias) - np.min(pid_bias)) if pid_bias else float("nan"),
    }


def endpoint_bootstrap(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    rows: List[Dict[str, object]] = []
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
    return pd.DataFrame(rows).sort_values(["energy_residual_sigma68", "shape_reconstruction_rmse"]).reset_index(drop=True)


def winner_table(overall: pd.DataFrame, endpoints: pd.DataFrame) -> pd.DataFrame:
    out = overall.merge(endpoints, on="method", how="left", suffixes=("_overall", ""))
    out["winner_score"] = (
        out["energy_residual_sigma68"]
        + 0.20 * out["energy_residual_bias"].abs()
        + 0.004 * out["onset_timing_sigma68_ns"]
        + 0.16 * out["shape_reconstruction_rmse"]
        + 0.10 * (1.0 - out["saturation_onset_auc"])
        + 0.05 * out["pileup_miss_rate"]
        + 0.05 * out["false_split_rate"]
        + 0.08 * out["pedestal_shift_false_split_span"].fillna(0.0)
        + 0.08 * out["pid_energy_bias_span"].fillna(0.0)
    )
    return out.sort_values(["winner_score", "energy_residual_sigma68", "shape_reconstruction_rmse"]).reset_index(drop=True)


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


def write_report(cfg: dict, match: pd.DataFrame, templates: pd.DataFrame, ranked: pd.DataFrame, endpoints: pd.DataFrame, by_run: pd.DataFrame, strata: pd.DataFrame, winner: str, runtime: float) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    method_rows = pd.DataFrame(
        [
            ["analytic_clipped_template_sideband_traditional", "traditional", "censored template fit with deterministic clipped-sample sideband correction"],
            ["ridge", "linear ML", "ridge classifier plus multi-output ridge regression"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier and regressors"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact one-dimensional CNN over 18 ADC samples"],
            ["tiny_sequence_transformer", "sequence NN", "one-layer self-attention waveform encoder"],
            ["saturation_residual_fusion_new", "new hybrid", "boosted residual fusion of waveform, clipping sidebands, and traditional fit outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S36a: Clipped-Pulse Saturation Onset Shape Recovery Benchmark

## Abstract

Ticket `{TICKET}` asks whether clipped waveform morphology can recover
pre-saturation amplitude and onset timing without leaking run identity, and
whether that improves energy calibration near the saturation boundary.  The
worker is `{WORKER}`.  The held-out winner written to `result.json` is
**`{winner}`**, selected by the registered S36a composite endpoint score.  Its
energy residual sigma68 is `{fmt(best['energy_residual_sigma68'])}` with 95%
run-block bootstrap CI [`{fmt(best['energy_residual_sigma68_ci_low'])}`,
`{fmt(best['energy_residual_sigma68_ci_high'])}`], onset timing sigma68 is
`{fmt(best['onset_timing_sigma68_ns'])}` ns, saturation-onset AUC is
`{fmt(best['saturation_onset_auc'])}`, and median normalized shape-reconstruction
RMSE is `{fmt(best['shape_reconstruction_rmse'])}`.

## Raw ROOT Reproduction Gate

Raw B-stack ROOT files are read from `{cfg['raw_root_dir']}`.  The branch
`h101/HRDv` is reshaped into `(event, channel, sample)` with 18 samples.  The
selected-pulse anchor is reproduced directly from B2/B4/B6/B8 channels using

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

`A_ec = max_t(x_ect - b_ec)`,

`N = sum_ec 1[A_ec > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Split, Truth Construction, and Leakage Control

Train runs are `{cfg['benchmark_runs']['train']}` and held-out runs are
`{cfg['benchmark_runs']['heldout']}`; no event from a held-out run is used to
fit templates or model parameters.  Clean raw-ROOT pulses are aligned into
stave-specific templates

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Controlled clipped examples are generated as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

followed by the observation operator `w_obs(t)=min(w(t), {ADC_CLIP:.0f})`.
Clean single-pulse controls are generated from the same run distribution and
clipped with the same rule.

## Methods

{md_table(method_rows, ['method', 'family', 'description'])}

The new architecture is `saturation_residual_fusion_new`.  It is included
because saturation onset is a hybrid inverse problem: template parameters carry
physical identifiability, while clipped-sample count, plateau width, tail
fraction, and waveform residuals carry information hidden above the ADC ceiling.

## Endpoints and Equations

Energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Onset timing error is

`e_t = 10 ns (hat t_1 - t_1)`.

Shape reconstruction compares the predicted unclipped waveform `hat w(t)` with
the injected pre-clipping waveform:

`RMSE_shape = sqrt(mean_t[(hat w(t)-w(t))^2]) / max(max_t w(t)-median_{{0:3}} w(t), 1)`.

Saturation-onset classification uses the held-out label
`1[n_clip > 0]` and the method-specific onset score
`(hat A_1 + hat A_2)/{ADC_CLIP:.0f} + 0.05 s_overlap`.  AUC is the normalized
Mann-Whitney statistic.  Robust resolution is
`sigma68(e)=[Q84(e)-Q16(e)]/2`.  Confidence intervals are 95% percentile
intervals from `{int(cfg['ml']['bootstrap_samples'])}` held-out run-block
bootstrap resamples.

The registered S36a score is

`C = sigma_E + 0.20|bias_E| + 0.004 sigma_t + 0.16 RMSE_shape + 0.10(1-AUC) + 0.05 r_miss + 0.05 r_false + 0.08 S_ped + 0.08 S_PID`.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'energy_residual_bias', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'onset_timing_sigma68_ns', 'saturation_onset_auc', 'shape_reconstruction_rmse', 'pileup_miss_rate', 'false_split_rate', 'pedestal_shift_false_split_span', 'pid_energy_bias_span'])}

The traditional comparator has score `{fmt(trad['winner_score'])}` and energy
sigma68 `{fmt(trad['energy_residual_sigma68'])}`.  The selected winner changes
energy sigma68 by `{fmt(best['energy_residual_sigma68'] - trad['energy_residual_sigma68'])}`
and shape RMSE by `{fmt(best['shape_reconstruction_rmse'] - trad['shape_reconstruction_rmse'])}`.

## Endpoint Table with CIs

{md_table(endpoints, ['method', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'onset_timing_sigma68_ns', 'onset_timing_sigma68_ns_ci_low', 'onset_timing_sigma68_ns_ci_high', 'saturation_onset_auc', 'saturation_onset_auc_ci_low', 'saturation_onset_auc_ci_high', 'shape_reconstruction_rmse', 'shape_reconstruction_rmse_ci_low', 'shape_reconstruction_rmse_ci_high'])}

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Saturation-Depth and Systematic Strata

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class.

{md_table(strata, ['stratum', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate'], limit=90)}

## Systematics and Caveats

The truth labels are controlled overlays into raw-ROOT-derived clean pulses, so
the benchmark tests recovery under known clipping and pile-up truth rather than
measuring the real beam saturation rate.  The ADC ceiling is an explicit stress
operator, not decoded front-end metadata.  The 18-sample waveform window limits
very close onset separation and makes pedestal memory partly degenerate with
late tails.  PID dependence is represented by stave and charge-support proxies
because no external particle truth is present in the reduced ROOT gate.
Run-block bootstrap intervals quantify transfer across five held-out runs and
should not be interpreted as independent event-counting errors.

## Verdict

`result.json` names **{winner}** as the S36a winner.  The result supports using
clipped-sample sidebands and residual waveform morphology to recover amplitude
and onset timing near the saturation boundary, while retaining the traditional
censored template fit as the transparent baseline.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s36a")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + f"\n# {TITLE}\n", encoding="utf-8")
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

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [s32b.saturation_aware_traditional_prediction(trad_raw, waves)]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(s26b.transformer_prediction(events, waves, cfg))
    preds.append(s32b.saturation_residual_fusion_new(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
    all_pred = add_shape_metrics(all_pred, events, waves_unclipped, templates, cfg)
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

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    endpoints = endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall, endpoints)
    by_run = base.by_run_summary(joined)
    strata = s32b.energy_strata_summary(joined)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, endpoints, by_run, strata, winner, runtime)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    best = ranked.iloc[0]
    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": TITLE,
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "claimed_ticket_text": "S36a clipped-pulse saturation onset shape recovery benchmark",
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
            "negative_control": "clipped clean single-pulse controls with matched source-run distribution",
            "winner_score": "energy_residual_sigma68 + 0.20*abs(energy_residual_bias) + 0.004*onset_timing_sigma68_ns + 0.16*shape_reconstruction_rmse + 0.10*(1-saturation_onset_auc) + 0.05*pileup_miss_rate + 0.05*false_split_rate + 0.08*pedestal_shift_false_split_span + 0.08*pid_energy_bias_span",
        },
        "required_method_coverage": {
            "traditional": "analytic_clipped_template_sideband_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "compact_waveform_transformer": "tiny_sequence_transformer",
            "new_architecture": "saturation_residual_fusion_new",
        },
        "winner": {
            "name": str(best["method"]),
            "criterion": "minimum registered S36a held-out saturation-onset, energy, timing, and shape-recovery composite score with run-block bootstrap CIs",
            "winner_score": float(best["winner_score"]),
            "energy_residual_bias": float(best["energy_residual_bias"]),
            "energy_residual_sigma68": float(best["energy_residual_sigma68"]),
            "energy_residual_sigma68_ci95": [
                float(best["energy_residual_sigma68_ci_low"]),
                float(best["energy_residual_sigma68_ci_high"]),
            ],
            "onset_timing_sigma68_ns": float(best["onset_timing_sigma68_ns"]),
            "onset_timing_sigma68_ci95": [
                float(best["onset_timing_sigma68_ns_ci_low"]),
                float(best["onset_timing_sigma68_ns_ci_high"]),
            ],
            "saturation_onset_auc": float(best["saturation_onset_auc"]),
            "saturation_onset_auc_ci95": [
                float(best["saturation_onset_auc_ci_low"]),
                float(best["saturation_onset_auc_ci_high"]),
            ],
            "shape_reconstruction_rmse": float(best["shape_reconstruction_rmse"]),
            "shape_reconstruction_rmse_ci95": [
                float(best["shape_reconstruction_rmse_ci_low"]),
                float(best["shape_reconstruction_rmse_ci_high"]),
            ],
            "saturation_onset_energy_sigma68": float(best["saturation_onset_energy_sigma68"]),
            "pedestal_shift_false_split_span": float(best["pedestal_shift_false_split_span"]),
            "pid_energy_bias_span": float(best["pid_energy_bias_span"]),
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
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "ADC clipping is a benchmark stressor, not decoded electronics metadata.",
            "Shape RMSE compares predicted templates to injected pre-clipping waveforms, not to unknown real unclipped hardware truth.",
            "PID-dependent failure is represented by stave and charge-support proxies.",
            "Bootstrap CIs resample held-out runs and quantify run-transfer uncertainty.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
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
