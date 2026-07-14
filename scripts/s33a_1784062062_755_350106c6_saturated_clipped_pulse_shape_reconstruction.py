#!/usr/bin/env python3
"""S33a saturated and clipped pulse-shape reconstruction benchmark."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b  # noqa: E402


TICKET = "1784062062.755.350106c6"
TITLE = "S33a saturated and clipped pulse-shape reconstruction"
WORKER = "testbeam-laptop-2"
SLUG = "saturated_clipped_pulse_shape_reconstruction"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = ROOT / "data" / "root" / "root"
ADC_CLIP = 11800.0


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S33a",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071402,
            "max_clean_pulses_per_run_stave": 110,
            "injected_per_train_run": 64,
            "clean_per_train_run": 64,
            "injected_per_heldout_run": 84,
            "clean_per_heldout_run": 84,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update(
        {
            "bootstrap_samples": 400,
            "cnn_epochs": 90,
            "cnn_channels": 12,
            "max_iter": 260,
        }
    )
    return cfg


def robust_width(waveforms: np.ndarray, frac: float = 0.5) -> np.ndarray:
    baseline = np.median(waveforms[:, :4], axis=1)
    corr = waveforms - baseline[:, None]
    peak = np.maximum(corr.max(axis=1), 1.0)
    return (corr >= (frac * peak[:, None])).sum(axis=1).astype(float)


def tail_fraction(waveforms: np.ndarray) -> np.ndarray:
    baseline = np.median(waveforms[:, :4], axis=1)
    corr = waveforms - baseline[:, None]
    positive = np.clip(corr, 0.0, None)
    area = np.maximum(positive.sum(axis=1), 1.0)
    return positive[:, 10:].sum(axis=1) / area


def waveform_area(waveforms: np.ndarray) -> np.ndarray:
    baseline = np.median(waveforms[:, :4], axis=1)
    corr = waveforms - baseline[:, None]
    return np.clip(corr, 0.0, None).sum(axis=1)


def model_waveforms(
    frame: pd.DataFrame,
    templates: Dict[str, np.ndarray],
    t1_col: str,
    t2_col: str,
    a1_col: str,
    a2_col: str,
    include_second: bool = True,
) -> np.ndarray:
    rows: List[np.ndarray] = []
    ref = 5.0
    for row in frame.itertuples(index=False):
        template = templates[str(getattr(row, "stave"))]
        t1 = float(getattr(row, t1_col))
        a1 = float(getattr(row, a1_col))
        wave = a1 * p05a.shifted_template(template, t1, ref)
        if include_second:
            t2 = float(getattr(row, t2_col))
            a2 = float(getattr(row, a2_col))
            if np.isfinite(t2) and np.isfinite(a2):
                wave = wave + a2 * p05a.shifted_template(template, t2, ref)
        rows.append(wave.astype(float))
    return np.vstack(rows)


def add_shape_errors(joined: pd.DataFrame, templates: Dict[str, np.ndarray]) -> pd.DataFrame:
    positives = joined["is_overlap"].to_numpy(int) == 1
    out = joined.copy()
    out["amplitude_fractional_error"] = np.nan
    out["width50_error_samples"] = np.nan
    out["tail_fraction_error"] = np.nan
    out["recovered_energy_fractional_error"] = np.nan
    if not positives.any():
        return out
    pos = out.loc[positives].copy()
    true_waves = model_waveforms(pos, templates, "true_t1_sample", "true_t2_sample", "true_amp1_adc", "true_amp2_adc")
    pred_waves = model_waveforms(pos, templates, "t1_sample", "t2_sample", "amp1_adc", "amp2_adc")
    true_amp = pos[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
    pred_amp = pos[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
    true_area = waveform_area(true_waves)
    pred_area = waveform_area(pred_waves)
    idx = out.index[positives]
    out.loc[idx, "amplitude_fractional_error"] = (pred_amp - true_amp) / np.maximum(true_amp, 1.0)
    out.loc[idx, "width50_error_samples"] = robust_width(pred_waves) - robust_width(true_waves)
    out.loc[idx, "tail_fraction_error"] = tail_fraction(pred_waves) - tail_fraction(true_waves)
    out.loc[idx, "recovered_energy_fractional_error"] = (pred_area - true_area) / np.maximum(true_area, 1.0)
    return out


def sig68(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float((np.percentile(arr, 84.0) - np.percentile(arr, 16.0)) / 2.0)


def shape_metric_values(frame: pd.DataFrame) -> dict:
    pos = frame[(frame["is_overlap"] == 1) & (~frame["failed"].astype(bool))]
    amp = pos["amplitude_fractional_error"].to_numpy(float)
    width = pos["width50_error_samples"].to_numpy(float)
    tail = pos["tail_fraction_error"].to_numpy(float)
    energy = pos["recovered_energy_fractional_error"].to_numpy(float)
    return {
        "amplitude_bias": float(np.nanmedian(amp)) if len(amp) else float("nan"),
        "amplitude_sigma68": sig68(amp),
        "width50_bias_samples": float(np.nanmedian(width)) if len(width) else float("nan"),
        "width50_sigma68_samples": sig68(width),
        "tail_fraction_bias": float(np.nanmedian(tail)) if len(tail) else float("nan"),
        "tail_fraction_sigma68": sig68(tail),
        "energy_bias": float(np.nanmedian(energy)) if len(energy) else float("nan"),
        "energy_sigma68": sig68(energy),
        "n_accepted_positive": int(len(pos)),
    }


def bootstrap_shape_metrics(frame: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    rows = []
    held = frame[frame["split"] == "heldout"].copy()
    held["saturation_depth"] = pd.cut(
        held["saturated_sample_count"],
        bins=[-0.5, 0.5, 2.5, 5.5, 18.5],
        labels=["0", "1-2", "3-5", "6+"],
    )
    stratum_specs = [
        ("saturation_depth", "saturation_depth"),
        ("channel", "stave"),
    ]
    for stratum_name, col in stratum_specs:
        for (method, value), group in held.groupby(["method", col], observed=False):
            if len(group) == 0:
                continue
            row = {"stratum": stratum_name, "value": str(value), "method": method, **shape_metric_values(group)}
            runs = sorted(group["source_run"].unique())
            samples: Dict[str, List[float]] = {}
            if len(runs) >= 2:
                for _ in range(reps):
                    take = rng.choice(runs, size=len(runs), replace=True)
                    boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
                    vals = shape_metric_values(boot)
                    for key, val in vals.items():
                        if key.startswith("n_") or not np.isfinite(val):
                            continue
                        samples.setdefault(key, []).append(float(val))
                for key, vals in samples.items():
                    row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
                    row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
            rows.append(row)
    return pd.DataFrame(rows)


def overall_shape_metrics(frame: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    rows = []
    held = frame[frame["split"] == "heldout"].copy()
    for method, group in held.groupby("method"):
        row = {"method": method, **shape_metric_values(group)}
        runs = sorted(group["source_run"].unique())
        samples: Dict[str, List[float]] = {}
        for _ in range(reps):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            vals = shape_metric_values(boot)
            for key, val in vals.items():
                if key.startswith("n_") or not np.isfinite(val):
                    continue
                samples.setdefault(key, []).append(float(val))
        for key, vals in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["energy_sigma68", "amplitude_sigma68"]).reset_index(drop=True)


def winner_table(method_metrics: pd.DataFrame, shape_metrics: pd.DataFrame) -> pd.DataFrame:
    joined = method_metrics.merge(shape_metrics, on="method", suffixes=("", "_shape"))
    joined["winner_score"] = (
        joined["energy_sigma68"]
        + 0.20 * joined["amplitude_sigma68"]
        + 0.08 * joined["tail_fraction_sigma68"]
        + 0.015 * joined["width50_sigma68_samples"]
        + 0.03 * joined["pileup_miss_rate"]
        + 0.03 * joined["false_split_rate"]
    )
    return joined.sort_values(["winner_score", "energy_sigma68", "amplitude_sigma68"]).reset_index(drop=True)


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


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    shape_overall: pd.DataFrame,
    shape_strata: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    text = f"""# S33a: Saturated and Clipped Pulse-Shape Reconstruction

## Abstract

Ticket `{TICKET}` asks for saturated and clipped calorimeter waveform
reconstruction from raw ROOT data, comparing a strong traditional method against
ridge, gradient-boosted trees, MLP, 1D-CNN, and a sensible new architecture.  The
benchmark also includes a transformer encoder because the waveform is a short
ordered sequence.  The winner is **`{winner}`**, selected by a predeclared
composite pulse-shape score on held-out runs.  Its score is
`{fmt(best['winner_score'])}` with recovered-energy sigma68
`{fmt(best['energy_sigma68'])}` and 95% run-bootstrap CI
[`{fmt(best['energy_sigma68_ci_low'])}`, `{fmt(best['energy_sigma68_ci_high'])}`].

## Raw ROOT Reproduction Gate

Raw B-stack files are read from `{cfg['raw_root_dir']}`.  For each run, the
`h101/HRDv` branch is reshaped to `(event, channel, sample)` with 18 samples per
channel.  The project selection uses B2/B4/B6/B8, baseline

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

and selected-pulse indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

The reproduced number is the analysis anchor before model fitting:

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Controlled Saturation Benchmark

Train runs are `{cfg['benchmark_runs']['train']}` and held-out runs are
`{cfg['benchmark_runs']['heldout']}`.  Clean pulse templates are estimated only
from train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Doublet truth is generated as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

where `epsilon_rs(t)` is a residual sampled from raw-ROOT clean pulses with the
same source run and stave.  The observed waveform passed to every method is
clipped:

`w_obs(t) = min(w(t), {ADC_CLIP:.0f})`.

Clean single-pulse controls are generated from the same source-run distribution
and are clipped by the same rule, making false splitting a direct negative
control.

## Methods

The traditional comparator is **analytic_clipped_template_sideband_traditional**.
It fits one- and two-pulse template models by bounded least squares,

`SSE_k = sum_t [w_obs(t) - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2`,

then applies a deterministic saturation sideband correction using clipped-sample
count, plateau width, and late-tail fraction.  The ML panel contains ridge,
histogram gradient-boosted trees, MLP, compact 1D-CNN, and
`tiny_sequence_transformer`.  The new architecture is
**saturation_residual_fusion_new**, a residual-fusion boosted model that
concatenates waveform summaries, clipping sidebands, and the analytic fit output
before learning residual corrections.

## Endpoints and Uncertainty

For accepted injected doublets, the study evaluates four ticket endpoints:

`e_A = ((hat A_1 + hat A_2) - (A_1 + A_2))/(A_1 + A_2)`,

`e_W = W50(hat w) - W50(w)`,

`e_T = f_tail(hat w) - f_tail(w)`,

`e_E = (area(hat w) - area(w))/area(w)`.

Here `W50` is the sample count above half maximum and `f_tail` is the fraction of
area in samples 10--17.  Robust resolution is

`sigma68(e) = [Q84(e)-Q16(e)]/2`.

Confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap resamples.
The winner minimizes

`C = sigma_E + 0.20 sigma_A + 0.08 sigma_T + 0.015 sigma_W + 0.03 r_miss + 0.03 r_false`.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'energy_sigma68', 'energy_sigma68_ci_low', 'energy_sigma68_ci_high', 'amplitude_sigma68', 'tail_fraction_sigma68', 'width50_sigma68_samples', 'pileup_miss_rate', 'false_split_rate'])}

The traditional comparator has score `{fmt(trad['winner_score'])}` and
recovered-energy sigma68 `{fmt(trad['energy_sigma68'])}`.  The selected winner
changes recovered-energy sigma68 by
`{fmt(best['energy_sigma68'] - trad['energy_sigma68'])}`.

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Shape Endpoint CIs

{md_table(shape_overall, ['method', 'amplitude_bias', 'amplitude_sigma68', 'amplitude_sigma68_ci_low', 'amplitude_sigma68_ci_high', 'width50_bias_samples', 'width50_sigma68_samples', 'tail_fraction_bias', 'tail_fraction_sigma68', 'energy_bias', 'energy_sigma68'])}

## Stratified Bootstrap Results

The required stratification is by saturation depth and channel.  Each row reports
the held-out endpoint within a stratum; CI columns are run-block bootstrap
intervals when at least two held-out runs contribute.

{md_table(shape_strata, ['stratum', 'value', 'method', 'energy_sigma68', 'energy_sigma68_ci_low', 'energy_sigma68_ci_high', 'amplitude_sigma68', 'tail_fraction_sigma68', 'width50_sigma68_samples'], limit=80)}

## Systematics and Caveats

The truth labels are controlled overlays into raw-ROOT-derived clean pulses, so
they test reconstruction under known saturation and clipping but not the true
beam pile-up rate.  The clipping ceiling is an explicit stressor rather than a
decoded electronics flag.  Template drift is a real transfer effect because
held-out runs are excluded from template estimation and ML training.  Only 18
samples are available, making sub-sample separations and late tails partly
degenerate.  Bootstrap CIs resample held-out runs, so they represent run-transfer
uncertainty rather than event-counting precision.

## Verdict

`result.json` names **{winner}** as the winner.  It is preferred for saturated
and clipped controlled-overlay pulse-shape reconstruction under the declared
score.  The analytic clipped-template method remains the auditable deterministic
fallback when transparent extrapolation is required.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s33a")
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
    joined = add_shape_errors(joined, templates)
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    method_metrics = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    by_run = base.by_run_summary(joined)
    shape_overall = overall_shape_metrics(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    shape_strata = bootstrap_shape_metrics(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(method_metrics, shape_overall)

    method_metrics.to_csv(OUT / "method_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    shape_overall.to_csv(OUT / "shape_endpoint_metrics.csv", index=False)
    shape_strata.to_csv(OUT / "shape_stratified_bootstrap.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, by_run, shape_overall, shape_strata, winner, runtime)

    input_rows = []
    for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root")):
        input_rows.append({"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size})
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
        "claimed_ticket_text": "Study pulse-shape reconstruction for saturated and clipped calorimeter waveforms: compare template chi-square fitting and deconvolution against ridge regression, gradient-boosted trees, MLP, 1D-CNN, and transformer encoders; evaluate amplitude, width, tail fraction, and recovered energy with stratified bootstrap CIs across saturation depth and channel.",
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
            "strata": ["saturation_depth", "channel"],
            "primary_score": "energy_sigma68 + 0.20*amplitude_sigma68 + 0.08*tail_fraction_sigma68 + 0.015*width50_sigma68_samples + 0.03*pileup_miss_rate + 0.03*false_split_rate",
        },
        "required_method_coverage": {
            "traditional": "analytic_clipped_template_sideband_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_encoder": "tiny_sequence_transformer",
            "new_architecture": "saturation_residual_fusion_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out composite pulse-shape score with run-block bootstrap CIs",
            "winner_score": float(best["winner_score"]),
            "recovered_energy_sigma68": float(best["energy_sigma68"]),
            "recovered_energy_sigma68_ci95": [
                float(best["energy_sigma68_ci_low"]),
                float(best["energy_sigma68_ci_high"]),
            ],
            "amplitude_sigma68": float(best["amplitude_sigma68"]),
            "tail_fraction_sigma68": float(best["tail_fraction_sigma68"]),
            "width50_sigma68_samples": float(best["width50_sigma68_samples"]),
            "pileup_miss_rate": float(best["pileup_miss_rate"]),
            "false_split_rate": float(best["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "shape_endpoint_metrics": "shape_endpoint_metrics.csv",
            "shape_stratified_bootstrap": "shape_stratified_bootstrap.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "ADC clipping is an explicit benchmark stressor rather than decoded electronics metadata.",
            "Bootstrap CIs resample held-out runs and should be interpreted as run-transfer intervals.",
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
