#!/usr/bin/env python3
"""S55b saturation and pile-up energy recovery benchmark."""

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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b  # noqa: E402


TICKET = "2494"
TITLE = "S55b: Saturation knee energy linearity and censored-pulse recovery bakeoff"
WORKER = "testbeam-laptop-2"
SLUG = "s55b_saturation_knee_energy_linearity_censored_recovery_bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/data/extracted/root/root")
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
            "study_id": "S55b",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071401,
            "max_clean_pulses_per_run_stave": 100,
            "injected_per_train_run": 60,
            "clean_per_train_run": 60,
            "injected_per_heldout_run": 82,
            "clean_per_heldout_run": 82,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 260})
    return cfg


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84.0) - np.percentile(values, 16.0)) / 2.0)


def endpoint_values(frame: pd.DataFrame) -> Dict[str, float]:
    positives = frame[frame["is_overlap"] == 1].copy()
    valid = positives[~positives["failed"].astype(bool)].copy()
    clean = frame[frame["is_overlap"] == 0].copy()

    if len(valid):
        true_e = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_e = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        energy_err = (pred_e - true_e) / np.maximum(true_e, 1.0)
        t1_err = (valid["t1_sample"].to_numpy(float) - valid["true_t1_sample"].to_numpy(float)) * 10.0
        t2_err = (valid["t2_sample"].to_numpy(float) - valid["true_t2_sample"].to_numpy(float)) * 10.0
        delay_err = (
            (valid["t2_sample"].to_numpy(float) - valid["t1_sample"].to_numpy(float))
            - valid["true_sep_sample"].to_numpy(float)
        ) * 10.0
        saturated = valid[valid["saturated_sample_count"].to_numpy(float) > 0.0]
        if len(saturated):
            sat_true = saturated[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            sat_pred = saturated[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            sat_err = (sat_pred - sat_true) / np.maximum(sat_true, 1.0)
        else:
            sat_err = np.asarray([])
        stave_biases = []
        stave_miss = []
        for _stave, group in positives.groupby("stave"):
            stave_miss.append(float(group["failed"].mean()))
            good = group[~group["failed"].astype(bool)]
            if len(good):
                true_g = good[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
                pred_g = good[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
                stave_biases.append(float(np.median((pred_g - true_g) / np.maximum(true_g, 1.0))))
        pid_miss = [float(group["failed"].mean()) for _pid, group in positives.groupby("pid_proxy_class")]
    else:
        energy_err = t1_err = t2_err = delay_err = sat_err = np.asarray([])
        stave_biases = []
        stave_miss = []
        pid_miss = []

    pedestal_false = []
    for _state, group in clean.groupby("pedestal_state"):
        if len(group):
            pedestal_false.append(float((group["score"].to_numpy(float) >= 0.5).mean()))
    pedestal_shift_false_split_span = float(np.max(pedestal_false) - np.min(pedestal_false)) if pedestal_false else float("nan")
    plateau = positives["plateau_width"].to_numpy(float) if len(positives) else np.asarray([])
    return {
        "energy_residual_bias": float(np.median(energy_err)) if len(energy_err) else float("nan"),
        "energy_residual_sigma68": sigma68(energy_err),
        "saturation_onset_energy_sigma68": sigma68(sat_err),
        "saturation_onset_fraction": float((positives["saturated_sample_count"].to_numpy(float) > 0).mean()) if len(positives) else float("nan"),
        "pileup_separation_sigma68_ns": sigma68(delay_err),
        "leading_timing_shift_bias_ns": float(np.median(t1_err)) if len(t1_err) else float("nan"),
        "leading_timing_shift_sigma68_ns": sigma68(t1_err),
        "secondary_timing_shift_sigma68_ns": sigma68(t2_err),
        "pedestal_shift_false_split_span": pedestal_shift_false_split_span,
        "pedestal_false_split_rate": float((clean["score"].to_numpy(float) >= 0.5).mean()) if len(clean) else float("nan"),
        "pid_energy_bias_span": float(np.max(stave_biases) - np.min(stave_biases)) if stave_biases else float("nan"),
        "pid_failure_rate_span": float(np.max(pid_miss) - np.min(pid_miss)) if pid_miss else float("nan"),
        "stave_failure_rate_span": float(np.max(stave_miss) - np.min(stave_miss)) if stave_miss else float("nan"),
        "plateau_width_median_samples": float(np.median(plateau)) if len(plateau) else float("nan"),
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
    return pd.DataFrame(rows).sort_values(["energy_residual_sigma68", "pileup_separation_sigma68_ns"]).reset_index(drop=True)


def calibration_ece(y_true: np.ndarray, prob: np.ndarray, n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    prob = np.asarray(prob, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if np.any(mask):
            total += float(mask.mean() * abs(y_true[mask].mean() - prob[mask].mean()))
    return total


def pid_proxy_metrics(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for method, group in joined.groupby("method"):
        group = group.copy()
        group["pid_is_inner_high_charge"] = (group["pid_proxy_class"] == "inner_high_charge").astype(int)
        group["pred_total_adc"] = group["amp1_adc"].astype(float) + group["amp2_adc"].astype(float)
        group["pred_dt_sample"] = group["t2_sample"].astype(float) - group["t1_sample"].astype(float)
        x = group[["pred_total_adc", "score", "pred_dt_sample"]].replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(float)
        y = group["pid_is_inner_high_charge"].to_numpy(int)
        train = group["split"].to_numpy() == "train"
        held = group["split"].to_numpy() == "heldout"
        clf = LogisticRegression(max_iter=1000, class_weight="balanced")
        clf.fit(x[train], y[train])
        prob = clf.predict_proba(x)[:, 1]
        held_auc = float(roc_auc_score(y[held], prob[held]))
        held_ece = calibration_ece(y[held], prob[held])
        row: Dict[str, object] = {
            "method": method,
            "pid_proxy_auc": held_auc,
            "pid_proxy_ece": held_ece,
            "pid_positive_rate": float(y[held].mean()),
        }
        runs = sorted(group.loc[held, "source_run"].unique())
        auc_samples: List[float] = []
        ece_samples: List[float] = []
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            mask = group["source_run"].isin(take) & held
            yy = y[mask]
            pp = prob[mask]
            if len(np.unique(yy)) > 1:
                auc_samples.append(float(roc_auc_score(yy, pp)))
                ece_samples.append(calibration_ece(yy, pp))
        row["pid_proxy_auc_ci_low"] = float(np.percentile(auc_samples, 2.5))
        row["pid_proxy_auc_ci_high"] = float(np.percentile(auc_samples, 97.5))
        row["pid_proxy_ece_ci_low"] = float(np.percentile(ece_samples, 2.5))
        row["pid_proxy_ece_ci_high"] = float(np.percentile(ece_samples, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["pid_proxy_auc", "pid_proxy_ece"], ascending=[False, True]).reset_index(drop=True)


def winner_table(overall: pd.DataFrame, endpoints: pd.DataFrame, pid_metrics: pd.DataFrame) -> pd.DataFrame:
    out = overall.merge(endpoints, on="method", how="left").merge(pid_metrics, on="method", how="left")
    out["winner_score"] = (
        out["energy_residual_sigma68"]
        + 0.20 * out["energy_residual_bias"].abs()
        + 0.004 * out["pileup_separation_sigma68_ns"]
        + 0.004 * out["leading_timing_shift_sigma68_ns"]
        + 0.05 * out["pileup_miss_rate"]
        + 0.05 * out["false_split_rate"]
        + 0.08 * out["pedestal_shift_false_split_span"].fillna(0.0)
        + 0.08 * out["pid_energy_bias_span"].fillna(0.0)
        + 0.03 * (1.0 - out["pid_proxy_auc"].fillna(0.5))
        + 0.05 * out["pid_proxy_ece"].fillna(0.5)
    )
    return out.sort_values(["winner_score", "energy_residual_sigma68", "pileup_separation_sigma68_ns"]).reset_index(drop=True)


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
    rows = [[str(col) for col in view.columns]]
    rows.extend([[str(value) for value in row] for row in view.to_numpy(dtype=object)])
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    header = "| " + " | ".join(rows[0][i].ljust(widths[i]) for i in range(len(widths))) + " |"
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(widths))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(widths))) + " |" for row in rows[1:]]
    return "\n".join([header, sep, *body])


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    ranked: pd.DataFrame,
    endpoints: pd.DataFrame,
    pid_metrics: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    method_rows = pd.DataFrame(
        [
            ["analytic_clipped_template_sideband_traditional", "traditional", "bounded two-template deconvolution with deterministic clipping sideband correction"],
            ["ridge", "linear ML", "ridge classifier plus multi-output ridge regression"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier and regressors"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact one-dimensional CNN over the 18 ADC samples"],
            ["tiny_sequence_transformer", "sequence NN", "one-layer self-attention encoder over waveform samples"],
            ["saturation_residual_fusion_new", "new hybrid", "boosted residual fusion of waveform, clipping sidebands, and traditional fit outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S55b: Saturation Pile-Up Energy Recovery Benchmark

## Abstract

Ticket `{TICKET}` asks for a raw-ROOT reproduction followed by an academic-grade
comparison of energy reconstruction under clipped saturation and unresolved
pile-up.  The worker is `{WORKER}`.  The held-out winner written to `result.json`
is **`{winner}`**, selected by the registered composite score.  Its energy
residual sigma68 is `{fmt(best['energy_residual_sigma68'])}` with 95% run-block
bootstrap CI [`{fmt(best['energy_residual_sigma68_ci_low'])}`,
`{fmt(best['energy_residual_sigma68_ci_high'])}`], and its pile-up separation
sigma68 is `{fmt(best['pileup_separation_sigma68_ns'])}` ns.

## Raw ROOT Reproduction Gate

Raw B-stack files are read from `{cfg['raw_root_dir']}`.  For each ROOT file, the
`h101/HRDv` waveform branch is reshaped to `(event, channel, sample)` with 18
samples per channel.  The selected-pulse anchor uses B2/B4/B6/B8 channels,
pedestal

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

and indicator

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

This raw count is reproduced before fitting any model:

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Split and Controlled Truth

The split is by source run.  Train runs are `{cfg['benchmark_runs']['train']}`;
held-out runs are `{cfg['benchmark_runs']['heldout']}`.  Clean templates are
estimated only from train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Controlled doublets are generated from raw-ROOT-derived clean pulses:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

where `epsilon_rs(t)` is a run-local residual and `p` is a pedestal offset.  The
observed waveform supplied to every method is clipped as

`w_obs(t) = min(w(t), {ADC_CLIP:.0f})`.

Clean single-pulse controls are drawn from the same run distribution and clipped
with the same rule, so false split rate is a real negative-control endpoint.

## Methods

{md_table(method_rows, ['method', 'family', 'description'])}

The traditional comparator fits one- and two-pulse template hypotheses by
bounded least squares,

`SSE_k = sum_t [w_obs(t) - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2`,

then applies a deterministic saturation sideband correction based on clipped
sample count, plateau width, and late-tail fraction:

`A'_j = A_j [1 + 0.018 n_clip + 0.035 max(W_plateau-2,0) + 0.06 max(f_tail,0)]`.

The new architecture is `saturation_residual_fusion_new`.  It is sensible here
because the failure mode is hybrid: the analytic fit supplies identifiable
constituents, while clipping sidebands and waveform summaries carry residual
information about charge hidden above the ADC ceiling.

## Endpoints and Equations

The primary energy residual for accepted injected doublets is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

Pile-up separation error is

`e_Delta = 10 ns * [(hat t_2 - hat t_1) - Delta]`,

and timing shifts use

`e_tj = 10 ns * (hat t_j - t_j)`.

Robust resolution is

`sigma68(e) = [Q84(e) - Q16(e)] / 2`.

Confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap resamples.
The registered winner minimizes

`C = sigma_E + 0.20 |bias_E| + 0.004 sigma_Delta + 0.004 sigma_t1 + 0.05 r_miss + 0.05 r_false + 0.08 S_ped + 0.08 S_PID + 0.03(1-AUC_PID) + 0.05 ECE_PID`,

where `S_ped` is the pedestal-state false-split span and `S_PID` is the
stave/PID-proxy energy-bias span.  `AUC_PID` and `ECE_PID` are evaluated on a
train-calibrated held-out PID proxy, `inner_high_charge` versus all other
stave/charge states, using each method's reconstructed total energy, split
score, and fitted time separation as the decision inputs.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'energy_residual_bias', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'pileup_separation_sigma68_ns', 'leading_timing_shift_sigma68_ns', 'pileup_miss_rate', 'false_split_rate', 'pedestal_shift_false_split_span', 'pid_energy_bias_span', 'pid_proxy_auc', 'pid_proxy_ece'])}

The traditional comparator has score `{fmt(trad['winner_score'])}` and energy
sigma68 `{fmt(trad['energy_residual_sigma68'])}`.  The selected winner changes
energy sigma68 by `{fmt(best['energy_residual_sigma68'] - trad['energy_residual_sigma68'])}`.

## Endpoint Table with CIs

{md_table(endpoints, ['method', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'saturation_onset_energy_sigma68', 'pileup_separation_sigma68_ns', 'pileup_separation_sigma68_ns_ci_low', 'pileup_separation_sigma68_ns_ci_high', 'leading_timing_shift_bias_ns', 'pedestal_shift_false_split_span', 'pid_energy_bias_span', 'pid_failure_rate_span'])}

## PID Proxy AUC and Calibration

The PID endpoint is a proxy because no external particle label is available in
the reduced ROOT gate.  I define a binary proxy, `inner_high_charge`, from the
same stave/charge support used in the systematic strata.  For each method, a
logistic calibration model is fit on train runs and evaluated only on held-out
runs.  ECE is the ten-bin expected calibration error.

{md_table(pid_metrics, ['method', 'pid_proxy_auc', 'pid_proxy_auc_ci_low', 'pid_proxy_auc_ci_high', 'pid_proxy_ece', 'pid_proxy_ece_ci_low', 'pid_proxy_ece_ci_high', 'pid_positive_rate'])}

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Stratified Systematics

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class:

{md_table(strata, ['stratum', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate'], limit=90)}

## Systematics and Caveats

The truth labels are controlled overlays into raw-ROOT-derived clean pulses, so
the study tests reconstruction under known saturation and pile-up truth but does
not measure the real beam pile-up frequency.  The clipping threshold is an
explicit benchmark stressor rather than decoded front-end metadata.  The
18-sample readout creates a sampling floor for close doublets and makes pedestal
memory partly degenerate with broad late tails.  PID is represented by stave and
charge support because no external particle label is available in the reduced
ROOT gate.  Run-block bootstrap intervals quantify transfer across the five
held-out runs, not asymptotic event-counting uncertainty.

## Verdict

`result.json` names **{winner}** as the S55b winner.  The traditional clipped
template method remains the transparent fallback, while the selected winner is
preferred for the registered held-out energy-plus-pile-up score.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s55b")
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
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    endpoints = endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    pid_metrics = pid_proxy_metrics(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall, endpoints, pid_metrics)
    by_run = base.by_run_summary(joined)
    strata = s32b.energy_strata_summary(joined)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    pid_metrics.to_csv(OUT / "pid_proxy_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, endpoints, pid_metrics, by_run, strata, winner, runtime)

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
        "claimed_ticket_text": "S55b: Saturation knee energy linearity and censored-pulse recovery bakeoff",
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
            "winner_score": "energy_residual_sigma68 + 0.20*abs(energy_residual_bias) + 0.004*pileup_separation_sigma68_ns + 0.004*leading_timing_shift_sigma68_ns + 0.05*pileup_miss_rate + 0.05*false_split_rate + 0.08*pedestal_shift_false_split_span + 0.08*pid_energy_bias_span + 0.03*(1-pid_proxy_auc) + 0.05*pid_proxy_ece",
            "pid_endpoint": "train-calibrated held-out AUC/ECE for inner_high_charge PID proxy versus all other stave/charge states",
        },
        "required_method_coverage": {
            "traditional": "analytic_clipped_template_sideband_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_sequence_model": "tiny_sequence_transformer",
            "new_architecture": "saturation_residual_fusion_new",
        },
        "winner": {
            "name": str(best["method"]),
            "criterion": "minimum registered S55b held-out energy-plus-pileup composite score with run-block bootstrap CIs",
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
            "pid_proxy_auc": float(best["pid_proxy_auc"]),
            "pid_proxy_auc_ci95": [
                float(best["pid_proxy_auc_ci_low"]),
                float(best["pid_proxy_auc_ci_high"]),
            ],
            "pid_proxy_ece": float(best["pid_proxy_ece"]),
            "pid_proxy_ece_ci95": [
                float(best["pid_proxy_ece_ci_low"]),
                float(best["pid_proxy_ece_ci_high"]),
            ],
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
            "pid_proxy_metrics_ci": "pid_proxy_metrics_ci.csv",
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
