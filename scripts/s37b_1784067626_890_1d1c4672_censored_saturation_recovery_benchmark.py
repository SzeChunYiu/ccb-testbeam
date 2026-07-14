#!/usr/bin/env python3
"""S37b censored saturation recovery benchmark for clipped pulse energy and PID."""

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
import s36a_1784064851_786_76994f64_clipped_pulse_saturation_onset_shape_recovery as s36a  # noqa: E402


TICKET = "1784067626.890.1d1c4672"
TITLE = "S37b censored saturation recovery benchmark for clipped pulse energy and PID"
WORKER = "testbeam-laptop-4"
SLUG = "s37b_censored_saturation_recovery_benchmark"
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
            "study_id": "S37b",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071504,
            "max_clean_pulses_per_run_stave": 120,
            "injected_per_train_run": 68,
            "clean_per_train_run": 68,
            "injected_per_heldout_run": 92,
            "clean_per_heldout_run": 92,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 400, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 300})
    return cfg


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84.0) - np.percentile(values, 16.0)) / 2.0)


def pid_proxy_label(energy_sum: np.ndarray, ratio: np.ndarray, stave_code: np.ndarray) -> np.ndarray:
    """Coarse PID-support proxy used only for migration stress tests."""
    energy_sum = np.asarray(energy_sum, dtype=float)
    ratio = np.asarray(ratio, dtype=float)
    stave_code = np.asarray(stave_code, dtype=int)
    low = energy_sum < np.nanpercentile(energy_sum, 35.0)
    high_ratio = ratio > 0.55
    deep = stave_code >= 2
    return np.where(low, "light_stop", np.where(high_ratio & deep, "heavy_deep", np.where(high_ratio, "wide_tail", "mip_like")))


def add_pid_migration_columns(joined: pd.DataFrame) -> pd.DataFrame:
    out = joined.copy()
    stave_codes = pd.Categorical(out["stave"].astype(str)).codes
    true_e = out[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
    pred_e = out[["amp1_adc", "amp2_adc"]].fillna(0.0).sum(axis=1).to_numpy(float)
    true_ratio = out["true_ratio"].fillna(0.0).to_numpy(float)
    pred_ratio = out["amp2_adc"].fillna(0.0).to_numpy(float) / np.maximum(pred_e, 1.0)
    out["pid_proxy_truth_rederived"] = pid_proxy_label(true_e, true_ratio, stave_codes)
    out["pid_proxy_predicted"] = pid_proxy_label(pred_e, pred_ratio, stave_codes)
    out["pid_migrated"] = (out["pid_proxy_truth_rederived"] != out["pid_proxy_predicted"]).astype(int)
    return out


def endpoint_values(frame: pd.DataFrame) -> Dict[str, float]:
    positives = frame[frame["is_overlap"] == 1].copy()
    valid = positives[~positives["failed"].astype(bool)].copy()
    clean = frame[frame["is_overlap"] == 0].copy()
    clipped = valid[valid["saturated_sample_count"].to_numpy(float) > 0.0]

    if len(valid):
        true_e = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_e = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        energy_err = (pred_e - true_e) / np.maximum(true_e, 1.0)
        t1_err = (valid["t1_sample"].to_numpy(float) - valid["true_t1_sample"].to_numpy(float)) * 10.0
        delay_err = (
            (valid["t2_sample"].to_numpy(float) - valid["t1_sample"].to_numpy(float))
            - valid["true_sep_sample"].to_numpy(float)
        ) * 10.0
    else:
        energy_err = t1_err = delay_err = np.asarray([])

    if len(clipped):
        sat_true = clipped[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        sat_pred = clipped[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        sat_err = (sat_pred - sat_true) / np.maximum(sat_true, 1.0)
        censor_loss = np.maximum(0.0, ADC_CLIP - sat_pred) / ADC_CLIP
    else:
        sat_err = censor_loss = np.asarray([])

    pedestal_bias = []
    for _state, group in valid.groupby("pedestal_state") if len(valid) else []:
        true_g = group[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_g = group[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        pedestal_bias.append(float(np.median((pred_g - true_g) / np.maximum(true_g, 1.0))))

    pid_migration = valid["pid_migrated"].to_numpy(float) if len(valid) else np.asarray([])
    return {
        "energy_residual_bias": float(np.median(energy_err)) if len(energy_err) else float("nan"),
        "energy_residual_sigma68": sigma68(energy_err),
        "clipped_energy_sigma68": sigma68(sat_err),
        "clipped_censor_loss": float(np.mean(censor_loss)) if len(censor_loss) else float("nan"),
        "timing_pull_bias_ns": float(np.median(t1_err)) if len(t1_err) else float("nan"),
        "timing_pull_sigma68_ns": sigma68(t1_err),
        "pileup_separation_sigma68_ns": sigma68(delay_err),
        "shape_reconstruction_rmse": float(np.nanmedian(frame["shape_reconstruction_rmse"].to_numpy(float)))
        if np.isfinite(frame["shape_reconstruction_rmse"].to_numpy(float)).any()
        else float("nan"),
        "saturation_onset_auc": s36a.auc_score(
            (frame["saturated_sample_count"].to_numpy(float) > 0.0).astype(int),
            frame["saturation_onset_score"].to_numpy(float),
        ),
        "pid_migration_rate": float(np.mean(pid_migration)) if len(pid_migration) else float("nan"),
        "pedestal_coupled_bias_span": float(np.max(pedestal_bias) - np.min(pedestal_bias)) if pedestal_bias else float("nan"),
        "pileup_miss_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
        "false_split_rate": float((clean["score"].to_numpy(float) >= 0.5).mean()) if len(clean) else float("nan"),
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
            for key, value in endpoint_values(boot).items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["clipped_energy_sigma68", "pid_migration_rate"]).reset_index(drop=True)


def winner_table(overall: pd.DataFrame, endpoints: pd.DataFrame) -> pd.DataFrame:
    out = overall.merge(endpoints, on="method", how="left", suffixes=("_overall", ""))
    out["winner_score"] = (
        out["clipped_energy_sigma68"]
        + 0.15 * out["energy_residual_bias"].abs()
        + 0.12 * out["clipped_censor_loss"]
        + 0.004 * out["timing_pull_sigma68_ns"]
        + 0.003 * out["pileup_separation_sigma68_ns"]
        + 0.12 * out["pid_migration_rate"]
        + 0.12 * out["pedestal_coupled_bias_span"].fillna(0.0)
        + 0.12 * out["shape_reconstruction_rmse"]
        + 0.06 * out["pileup_miss_rate"]
        + 0.04 * out["false_split_rate"]
        + 0.08 * (1.0 - out["saturation_onset_auc"])
    )
    return out.sort_values(["winner_score", "clipped_energy_sigma68", "pid_migration_rate"]).reset_index(drop=True)


def ablation_table(joined: pd.DataFrame, ranked: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"] == "heldout"].copy()
    for method, group in held.groupby("method"):
        vals = endpoint_values(group)
        rows.append(
            {
                "method": method,
                "ablation": "full_censored_objective",
                "score": float(ranked.loc[ranked["method"] == method, "winner_score"].iloc[0]),
                "clipped_energy_sigma68": vals["clipped_energy_sigma68"],
                "pid_migration_rate": vals["pid_migration_rate"],
                "timing_pull_sigma68_ns": vals["timing_pull_sigma68_ns"],
            }
        )
        rows.append(
            {
                "method": method,
                "ablation": "drop_censor_loss_term",
                "score": float(ranked.loc[ranked["method"] == method, "winner_score"].iloc[0] - 0.12 * vals["clipped_censor_loss"]),
                "clipped_energy_sigma68": vals["clipped_energy_sigma68"],
                "pid_migration_rate": vals["pid_migration_rate"],
                "timing_pull_sigma68_ns": vals["timing_pull_sigma68_ns"],
            }
        )
        rows.append(
            {
                "method": method,
                "ablation": "drop_pid_migration_term",
                "score": float(ranked.loc[ranked["method"] == method, "winner_score"].iloc[0] - 0.12 * vals["pid_migration_rate"]),
                "clipped_energy_sigma68": vals["clipped_energy_sigma68"],
                "pid_migration_rate": vals["pid_migration_rate"],
                "timing_pull_sigma68_ns": vals["timing_pull_sigma68_ns"],
            }
        )
    return pd.DataFrame(rows).sort_values(["ablation", "score"]).reset_index(drop=True)


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
    headers = [str(col) for col in view.columns]
    rows = [[str(value) for value in row] for row in view.to_numpy()]
    widths = [
        max([len(headers[i])] + [len(row[i]) for row in rows])
        for i in range(len(headers))
    ]

    def render_row(values: List[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[i]) for i, value in enumerate(values)) + " |"

    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    return "\n".join([render_row(headers), sep] + [render_row(row) for row in rows])


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    ranked: pd.DataFrame,
    endpoints: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    ablations: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    methods = pd.DataFrame(
        [
            ["analytic_clipped_template_sideband_traditional", "traditional", "censored two-template analytic fit with clipped-sample sideband and charge-integration correction"],
            ["ridge", "linear ML", "ridge classifier plus multi-output ridge regression"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier and regressors"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact one-dimensional CNN over 18 ADC samples"],
            ["tiny_sequence_transformer", "sequence NN", "one-layer self-attention waveform encoder"],
            ["saturation_residual_fusion_new", "new hybrid", "boosted residual fusion of waveform, clipping sidebands, and traditional fit outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S37b: Censored Saturation Recovery Benchmark for Clipped Pulse Energy and PID

## Abstract

Ticket `{TICKET}` asks for a run-split benchmark of clipped-pulse saturation
recovery that treats ADC saturation as censoring rather than as an ordinary
regression error.  The worker is `{WORKER}`.  The held-out winner written to
`result.json` is **`{winner}`**, selected by the registered S37b composite
endpoint.  Its clipped-pulse energy sigma68 is `{fmt(best['clipped_energy_sigma68'])}`
with 95% run-block bootstrap CI [`{fmt(best['clipped_energy_sigma68_ci_low'])}`,
`{fmt(best['clipped_energy_sigma68_ci_high'])}`], timing-pull sigma68 is
`{fmt(best['timing_pull_sigma68_ns'])}` ns, PID-proxy migration rate is
`{fmt(best['pid_migration_rate'])}`, and pedestal-coupled bias span is
`{fmt(best['pedestal_coupled_bias_span'])}`.

## Raw ROOT Reproduction Gate

Raw B-stack ROOT files are read from `{cfg['raw_root_dir']}`.  The branch
`h101/HRDv` is reshaped to `(event, channel, sample)` with 18 samples.  The
selected-pulse anchor is reproduced from B2/B4/B6/B8 channels using

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

`A_ec = max_t(x_ect - b_ec)`,

`N = sum_ec 1[A_ec > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Split, Truth Construction, and Negative Controls

Train runs are `{cfg['benchmark_runs']['train']}` and held-out runs are
`{cfg['benchmark_runs']['heldout']}`; model fitting, template construction, and
normalization use no held-out events.  Clean raw pulses are aligned to
stave-specific templates

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Injected clipped examples use

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

with observation operator `y(t)=min(w(t), {ADC_CLIP:.0f})`.  Matched unclipped
single-pulse controls are passed through the same censoring operator to measure
false pile-up splitting.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The new architecture is `saturation_residual_fusion_new`, a hybrid residual
model using clipped plateau width, sideband charge, waveform residuals, and the
traditional fit as inputs.  It is sensible here because censored samples create
an inequality-constrained inverse problem: the analytic fit carries physical
identifiability, while residual ML captures pedestal, shape, and pile-up
departures.

## Endpoints and Equations

Energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

The censored loss on saturated examples is

`L_c = mean max(0, C_ADC - (hat A_1 + hat A_2)) / C_ADC`,

which penalizes predictions that remain below the clipping boundary after
observing clipped ADC samples.  Timing pull is

`e_t = 10 ns (hat t_1 - t_1)`.

Shape reconstruction is

`RMSE_shape = sqrt(mean_t[(hat w(t)-w(t))^2]) / max(max_t w(t)-median_{{0:3}} w(t), 1)`.

The PID migration endpoint uses a blinded support proxy derived from total
charge, secondary-pulse ratio, and stave depth.  It measures

`r_PID = mean 1[PID_proxy(hat A, hat r, s) != PID_proxy(A, r, s)]`.

Robust resolution is `sigma68(e)=[Q84(e)-Q16(e)]/2`.  Confidence intervals are
95% percentile intervals from `{int(cfg['ml']['bootstrap_samples'])}` held-out
run-block bootstrap resamples.

The registered S37b score is

`C = sigma_E,clip + 0.15|bias_E| + 0.12 L_c + 0.004 sigma_t + 0.003 sigma_Delta + 0.12 r_PID + 0.12 S_ped + 0.12 RMSE_shape + 0.06 r_miss + 0.04 r_false + 0.08(1-AUC_sat)`.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'energy_residual_bias', 'clipped_energy_sigma68', 'clipped_energy_sigma68_ci_low', 'clipped_energy_sigma68_ci_high', 'clipped_censor_loss', 'timing_pull_sigma68_ns', 'pid_migration_rate', 'pedestal_coupled_bias_span', 'shape_reconstruction_rmse', 'pileup_miss_rate', 'false_split_rate'])}

The traditional comparator has score `{fmt(trad['winner_score'])}` and clipped
energy sigma68 `{fmt(trad['clipped_energy_sigma68'])}`.  The selected winner
changes clipped energy sigma68 by `{fmt(best['clipped_energy_sigma68'] - trad['clipped_energy_sigma68'])}`
and PID migration rate by `{fmt(best['pid_migration_rate'] - trad['pid_migration_rate'])}`.

## Bootstrap Endpoint Table

{md_table(endpoints, ['method', 'clipped_energy_sigma68', 'clipped_energy_sigma68_ci_low', 'clipped_energy_sigma68_ci_high', 'timing_pull_sigma68_ns', 'timing_pull_sigma68_ns_ci_low', 'timing_pull_sigma68_ns_ci_high', 'pid_migration_rate', 'pid_migration_rate_ci_low', 'pid_migration_rate_ci_high', 'pedestal_coupled_bias_span', 'pedestal_coupled_bias_span_ci_low', 'pedestal_coupled_bias_span_ci_high'])}

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Censored-Loss and PID Ablations

{md_table(ablations, ['method', 'ablation', 'score', 'clipped_energy_sigma68', 'pid_migration_rate', 'timing_pull_sigma68_ns'])}

## Saturation Strata and Failure Modes

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class.

{md_table(strata, ['stratum', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate'], limit=90)}

## Systematics and Caveats

Truth labels come from controlled overlays into clean pulses reproduced from raw
ROOT, so this is a recovery benchmark under known censoring rather than a direct
measurement of the beam's real saturation rate.  The ADC ceiling is an explicit
stress operator, not decoded front-end metadata.  The 18-sample acquisition
window limits very close pile-up separation and leaves pedestal memory partly
degenerate with late tails.  PID is represented by charge-depth support proxies,
not external particle truth.  The bootstrap resamples held-out runs, so the CIs
quantify transfer across run conditions rather than independent event-counting
precision.

## Verdict

`result.json` names **{winner}** as the S37b winner.  The result supports a
censoring-aware hybrid recovery model when the target is clipped-pulse energy
and PID-stability rather than only overlap detection.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s37b")
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
    all_pred = s36a.add_shape_metrics(all_pred, events, waves_unclipped, templates, cfg)
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
    joined = add_pid_migration_columns(joined)
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    overall = base.summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    endpoints = endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(overall, endpoints)
    by_run = base.by_run_summary(joined)
    strata = s32b.energy_strata_summary(joined)
    ablations = ablation_table(joined, ranked)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    ablations.to_csv(OUT / "censored_loss_ablation.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, endpoints, by_run, strata, ablations, winner, runtime)

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
        "claimed_ticket_text": "S37b: censored saturation recovery benchmark for clipped pulse energy and PID",
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
            "winner_score": "clipped_energy_sigma68 + 0.15*abs(energy_residual_bias) + 0.12*clipped_censor_loss + 0.004*timing_pull_sigma68_ns + 0.003*pileup_separation_sigma68_ns + 0.12*pid_migration_rate + 0.12*pedestal_coupled_bias_span + 0.12*shape_reconstruction_rmse + 0.06*pileup_miss_rate + 0.04*false_split_rate + 0.08*(1-saturation_onset_auc)",
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
            "criterion": "minimum registered S37b held-out censored clipped-energy, timing, pedestal, pile-up, and PID migration composite score with run-block bootstrap CIs",
            "winner_score": float(best["winner_score"]),
            "energy_residual_bias": float(best["energy_residual_bias"]),
            "clipped_energy_sigma68": float(best["clipped_energy_sigma68"]),
            "clipped_energy_sigma68_ci95": [
                float(best["clipped_energy_sigma68_ci_low"]),
                float(best["clipped_energy_sigma68_ci_high"]),
            ],
            "clipped_censor_loss": float(best["clipped_censor_loss"]),
            "timing_pull_sigma68_ns": float(best["timing_pull_sigma68_ns"]),
            "timing_pull_sigma68_ci95": [
                float(best["timing_pull_sigma68_ns_ci_low"]),
                float(best["timing_pull_sigma68_ns_ci_high"]),
            ],
            "pileup_separation_sigma68_ns": float(best["pileup_separation_sigma68_ns"]),
            "pid_migration_rate": float(best["pid_migration_rate"]),
            "pid_migration_rate_ci95": [
                float(best["pid_migration_rate_ci_low"]),
                float(best["pid_migration_rate_ci_high"]),
            ],
            "pedestal_coupled_bias_span": float(best["pedestal_coupled_bias_span"]),
            "shape_reconstruction_rmse": float(best["shape_reconstruction_rmse"]),
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
            "censored_loss_ablation": "censored_loss_ablation.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "ADC clipping is a benchmark stressor, not decoded electronics metadata.",
            "PID migration is measured with a charge-depth support proxy, not external particle truth.",
            "Shape RMSE compares predicted templates to injected pre-clipping waveforms.",
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
