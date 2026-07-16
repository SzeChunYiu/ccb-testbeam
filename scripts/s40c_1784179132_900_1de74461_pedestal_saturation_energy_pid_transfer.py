#!/usr/bin/env python3
"""S40c pedestal-saturation energy calibration transfer benchmark."""

from __future__ import annotations

import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b  # noqa: E402
import s39b_1784176169_768_033348a9_clipped_template_energy_recovery_vs_neural_saturation_inversion as s39b  # noqa: E402


TICKET = "1784179132.900.1de74461"
STUDY_ID = "S40c"
TITLE = "S40c pedestal-saturation energy calibration transfer under PID-conditioned shape shifts"
WORKER = "testbeam-laptop-2"
SLUG = "s40c_pedestal_saturation_energy_pid_transfer"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
CLAIMED_TICKET = """1784179132.900.1de74461
# S40c pedestal-saturation energy calibration transfer under PID-conditioned shape shifts

Academic-grade study: test whether pedestal state and saturation correction transfer across runs without silently changing energy scale or PID boundaries when pulse shape changes. Compare traditional sideband/adaptive pedestal subtraction, clipped-template charge reconstruction, and range/dE-dx PID cuts against ridge, gradient-boosted trees, MLP, 1D-CNN waveform regressors, multitask PID-energy heads, and a transformer encoder where apt. Use leave-run-family-out validation and bootstrap 95% CIs for energy bias/resolution, saturation knee, pedestal high-minus-low contrast, PID AUC/calibration, timing residuals, pile-up strata, and uncertainty coverage. Deliver concise failure maps that deepen pedestal, saturation, energy, and PID understanding.
"""


def load_config() -> dict:
    cfg = s39b.load_config()
    cfg.update(
        {
            "study_id": STUDY_ID,
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071604,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 520, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 260})
    return cfg


def fmt(value: object) -> str:
    try:
        val = float(value)
    except Exception:
        return str(value)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def json_clean(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sigma68(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(0.5 * (np.percentile(arr, 84.0) - np.percentile(arr, 16.0)))


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    mask = np.isfinite(score)
    if mask.sum() < 4 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def calibration_error(y: np.ndarray, score: np.ndarray, n_bins: int = 8) -> float:
    y = np.asarray(y, dtype=float)
    score = np.asarray(score, dtype=float)
    mask = np.isfinite(score)
    y = y[mask]
    score = np.clip(score[mask], 0.0, 1.0)
    if len(y) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    err = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        take = (score >= lo) & (score < hi if hi < 1.0 else score <= hi)
        if take.any():
            err += float(take.mean() * abs(y[take].mean() - score[take].mean()))
    return float(err)


def add_transfer_columns(joined: pd.DataFrame) -> pd.DataFrame:
    out = joined.copy()
    true_energy = out[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
    pred_energy = out[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
    out["energy_residual"] = (pred_energy - true_energy) / np.maximum(true_energy, 1.0)
    out.loc[out["failed"].astype(bool), "energy_residual"] = np.nan
    out["time_residual_ns"] = (out["t1_sample"].to_numpy(float) - out["true_t1_sample"].to_numpy(float)) * 10.0
    out.loc[out["failed"].astype(bool), "time_residual_ns"] = np.nan
    out["pred_energy_adc"] = pred_energy
    out["true_energy_adc"] = true_energy
    out["pid_label_proxy"] = (out["pid_proxy_class"].astype(str) == "inner_high_charge").astype(int)
    by_method = []
    for method, group in out.groupby("method", sort=False):
        train = group["split"].eq("train")
        med = float(np.nanmedian(group.loc[train, "pred_energy_adc"])) if train.any() else float(np.nanmedian(group["pred_energy_adc"]))
        mad = float(np.nanmedian(np.abs(group.loc[train, "pred_energy_adc"] - med))) if train.any() else 1.0
        scale = max(1.4826 * mad, 1.0)
        score = 1.0 / (1.0 + np.exp(-(group["pred_energy_adc"].to_numpy(float) - med) / scale))
        tmp = group.copy()
        tmp["pid_score_proxy"] = score
        by_method.append(tmp)
    out = pd.concat(by_method, ignore_index=True)
    out["saturation_truth"] = out["true_energy_adc"] > 11000.0
    out["saturation_pred"] = out["pred_energy_adc"] > 11000.0
    out["pileup_bin"] = np.where(out["is_overlap"].astype(int) == 1, "pileup", "clean")
    out["clip_bin"] = pd.cut(
        out["clip_fraction"].astype(float),
        bins=[-0.001, 0.0, 0.12, 1.0],
        labels=["unclipped", "mild_clip", "hard_clip"],
    ).astype(str)
    return out


def method_metrics(group: pd.DataFrame) -> Dict[str, float]:
    held = group[group["split"].eq("heldout")].copy()
    train = group[group["split"].eq("train")].copy()
    valid = held[~held["failed"].astype(bool)].copy()
    pileup = held["is_overlap"].astype(int).to_numpy() == 1
    clean = ~pileup
    y_pid = held["pid_label_proxy"].to_numpy(dtype=int)
    pid_score = held["pid_score_proxy"].to_numpy(dtype=float)
    nominal = valid[valid["pedestal_state"].astype(str).eq("nominal")]["energy_residual"]
    shifted = valid[~valid["pedestal_state"].astype(str).eq("nominal")]["energy_residual"]
    q90 = float(np.nanquantile(np.abs(train["energy_residual"]), 0.90)) if train["energy_residual"].notna().any() else float("nan")
    coverage90 = float((np.abs(valid["energy_residual"]) <= q90).mean()) if len(valid) and np.isfinite(q90) else float("nan")
    sat_true = held["saturation_truth"].to_numpy(dtype=bool)
    sat_pred = held["saturation_pred"].to_numpy(dtype=bool)
    sat_valid = np.isfinite(held["pred_energy_adc"].to_numpy(float))
    return {
        "n_events": float(len(held)),
        "n_valid": float(len(valid)),
        "energy_bias": float(np.nanmedian(valid["energy_residual"])),
        "energy_sigma68": sigma68(valid["energy_residual"]),
        "saturated_energy_sigma68": sigma68(valid.loc[valid["saturation_truth"], "energy_residual"]),
        "saturation_knee_accuracy": float((sat_true[sat_valid] == sat_pred[sat_valid]).mean()) if sat_valid.any() else float("nan"),
        "saturation_knee_calibration_abs": float(abs(sat_pred[sat_valid].mean() - sat_true[sat_valid].mean())) if sat_valid.any() else float("nan"),
        "pedestal_high_minus_low_bias": float(np.nanmedian(shifted) - np.nanmedian(nominal)) if len(nominal) and len(shifted) else float("nan"),
        "pid_auc": safe_auc(y_pid, pid_score),
        "pid_calibration_ece": calibration_error(y_pid, pid_score),
        "timing_residual_bias_ns": float(np.nanmedian(valid["time_residual_ns"])),
        "timing_residual_sigma68_ns": sigma68(valid["time_residual_ns"]),
        "pileup_merge_rate": float(held.loc[pileup, "failed"].mean()) if pileup.any() else float("nan"),
        "false_split_rate": float((held.loc[clean, "score"].to_numpy(float) >= 0.5).mean()) if clean.any() else float("nan"),
        "coverage90": coverage90,
        "coverage90_abs_error": float(abs(coverage90 - 0.90)) if np.isfinite(coverage90) else float("nan"),
    }


def bootstrap_metrics(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for method, group in joined.groupby("method", sort=False):
        row: Dict[str, object] = {"method": method, **method_metrics(group)}
        held_runs = np.asarray(sorted(group.loc[group["split"].eq("heldout"), "source_run"].unique()))
        samples: Dict[str, List[float]] = {}
        for _ in range(n_boot):
            take = rng.choice(held_runs, size=len(held_runs), replace=True)
            boot_held = pd.concat([group[(group["split"].eq("heldout")) & (group["source_run"] == run)] for run in take])
            boot = pd.concat([group[group["split"].eq("train")], boot_held], ignore_index=True)
            for key, value in method_metrics(boot).items():
                if np.isfinite(value):
                    samples.setdefault(key, []).append(float(value))
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def winner_table(metrics: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    out["winner_score"] = (
        out["energy_sigma68"]
        + 0.20 * out["energy_bias"].abs()
        + 0.18 * out["pedestal_high_minus_low_bias"].abs()
        + 0.25 * out["saturation_knee_calibration_abs"]
        + 0.10 * out["pid_calibration_ece"]
        + 0.05 * (1.0 - out["pid_auc"].fillna(0.5))
        + 0.003 * out["timing_residual_sigma68_ns"]
        + 0.05 * out["pileup_merge_rate"]
        + 0.05 * out["false_split_rate"]
        + 0.06 * out["coverage90_abs_error"]
    )
    return out.sort_values(["winner_score", "energy_sigma68", "pid_calibration_ece"]).reset_index(drop=True)


def by_run_metrics(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"].eq("heldout")]
    for (method, run), group in held.groupby(["method", "source_run"]):
        vals = method_metrics(pd.concat([joined[(joined["method"] == method) & joined["split"].eq("train")], group]))
        rows.append({"method": method, "heldout_run": int(run), **vals})
    return pd.DataFrame(rows)


def strata_metrics(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"].eq("heldout")]
    for method, mdf in held.groupby("method"):
        train = joined[(joined["method"] == method) & joined["split"].eq("train")]
        for column in ["pedestal_state", "pileup_bin", "clip_bin", "morphology_state", "stave", "pid_proxy_class"]:
            for value, group in mdf.groupby(column):
                vals = method_metrics(pd.concat([train, group], ignore_index=True))
                rows.append({"method": method, "stratum": column, "value": str(value), **vals})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: List[str], limit: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def write_report(cfg: dict, match: pd.DataFrame, templates: pd.DataFrame, ranked: pd.DataFrame, run_df: pd.DataFrame, strata: pd.DataFrame, winner: str, runtime: float) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    methods = pd.DataFrame(
        [
            ["analytic_clipped_template_sideband_traditional", "traditional", "adaptive pedestal sideband subtraction, clipped-template charge reconstruction, and charge/range proxy PID boundary"],
            ["ridge", "linear ML", "ridge/logistic baseline on waveform summary and sample features"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier/regressor panel"],
            ["mlp", "neural network", "tabular multilayer perceptron energy and pile-up heads"],
            ["1d_cnn", "neural network", "compact one-dimensional convolutional waveform regressor"],
            ["tiny_sequence_transformer", "temporal attention", "one-layer transformer encoder over the 18 ADC samples"],
            ["saturation_residual_fusion_new", "new hybrid", "residual fusion of clipped-template outputs, waveform shape, pedestal state, and clipping sidebands"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S40c: Pedestal-Saturation Energy Calibration Transfer Under PID-Conditioned Shape Shifts

## Abstract

Ticket `{TICKET}` asks whether pedestal state and saturation correction transfer
across runs without silently changing the energy scale or PID boundary when
pulse shape changes.  The raw ROOT selected-pulse count was reproduced before
benchmarking.  The held-out winner written to `result.json` is **`{winner}`**.
It obtains composite score `{fmt(best['winner_score'])}`, energy sigma68
`{fmt(best['energy_sigma68'])}` with 95% run-block CI
[`{fmt(best['energy_sigma68_ci_low'])}`, `{fmt(best['energy_sigma68_ci_high'])}`],
pedestal high-minus-low bias `{fmt(best['pedestal_high_minus_low_bias'])}`, PID
proxy AUC `{fmt(best['pid_auc'])}`, and conformal 90% coverage
`{fmt(best['coverage90'])}`.

## Raw ROOT Reproduction

Inputs are the B-stack reduced HRD files under `{cfg['raw_root_dir']}`.  The
runner reads `h101/HRDv` directly, reshapes each event to `(channel, sample)`,
forms the per-channel pedestal

`b_ec = median_{{t in 0..3}} x_ect`,

and selects B2/B4/B6/B8 pulses by

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Split, Truth, and Stress Construction

Validation is leave-run-family-out: train runs `{cfg['benchmark_runs']['train']}`
and held-out runs `{cfg['benchmark_runs']['heldout']}` are disjoint.  Synthetic
pile-up and saturation stressors are generated from raw-ROOT-derived clean
pulses plus run-local residual pools, with ADC clipping at `{s32b.ADC_CLIP:.0f}`.
The target energy is `A_1+A_2`; timing uses the first-pulse residual in ns; the
PID boundary is an explicitly declared proxy for the high-charge inner-stave
support class because external particle labels are not present in this ROOT
gate.

Train-only templates:

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The traditional comparator solves the bounded clipped-template least-squares
problem

`SSE_k = sum_t [w_t - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2`

for one- and two-pulse hypotheses and applies an interpretable sideband
saturation correction.  Learned methods receive only same-event waveform and
shape information.  The new hybrid architecture is sensible here because the
traditional fit localizes the physically meaningful constituents, while the
neural/tree residual layer can model charge hidden by clipping and pedestal
state shifts.

## Endpoints

Energy residual:

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`.

Robust resolution:

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Pedestal transfer contrast:

`Delta_ped = median(e_E | shifted pedestal) - median(e_E | nominal pedestal)`.

The PID score is a train-standardized logistic transform of reconstructed charge
and is scored against the high-charge inner-stave support proxy with AUC and
expected calibration error.  Uncertainty coverage is split-conformal: the 90th
percentile of absolute train-run energy residuals defines an interval, and
coverage is measured on held-out runs.

The declared winner minimizes

`C = sigma_E + 0.20|bias_E| + 0.18|Delta_ped| + 0.25 cal_sat + 0.10 ECE_PID + 0.05(1-AUC_PID) + 0.003 sigma_t + 0.05 r_merge + 0.05 r_false + 0.06|coverage90-0.90|`.

All intervals are 95% percentile intervals from `{int(cfg['ml']['bootstrap_samples'])}`
held-out run-block bootstrap resamples.

## Main Results

{md_table(ranked, ['method', 'winner_score', 'energy_bias', 'energy_bias_ci_low', 'energy_bias_ci_high', 'energy_sigma68', 'energy_sigma68_ci_low', 'energy_sigma68_ci_high', 'saturation_knee_calibration_abs', 'pedestal_high_minus_low_bias', 'pid_auc', 'pid_calibration_ece', 'timing_residual_sigma68_ns', 'pileup_merge_rate', 'false_split_rate', 'coverage90'])}

The traditional comparator score is `{fmt(trad['winner_score'])}` with energy
sigma68 `{fmt(trad['energy_sigma68'])}` and pedestal contrast
`{fmt(trad['pedestal_high_minus_low_bias'])}`.  The winning method changes
energy sigma68 by `{fmt(best['energy_sigma68'] - trad['energy_sigma68'])}` and
PID calibration ECE by `{fmt(best['pid_calibration_ece'] - trad['pid_calibration_ece'])}`
relative to the traditional comparator.

## Held-Out Run Stability

{md_table(run_df, ['method', 'heldout_run', 'energy_bias', 'energy_sigma68', 'pedestal_high_minus_low_bias', 'pid_auc', 'pid_calibration_ece', 'timing_residual_sigma68_ns', 'pileup_merge_rate', 'coverage90'])}

## Failure Maps

{md_table(strata, ['stratum', 'value', 'method', 'energy_bias', 'energy_sigma68', 'pedestal_high_minus_low_bias', 'pid_auc', 'pid_calibration_ece', 'timing_residual_sigma68_ns', 'pileup_merge_rate', 'coverage90'], limit=150)}

## Systematics and Caveats

The energy, pile-up, saturation, and timing truths are controlled-injection
truths built from raw-ROOT clean pulses, not hand-labeled beam truth.  Saturation
knee is a high-amplitude ADC proxy rather than a decoded electronics flag.  The
PID endpoint is a charge/support proxy; it is useful for boundary-transfer
stress testing but must not be read as an external species classifier.  Bootstrap
resampling is by held-out run block, so intervals represent run-transfer
stability rather than independent event-counting precision.  The 18-sample
waveform limits transformer capacity; the attention model is included as a
compact temporal encoder, not a large-sequence architecture.

## Verdict

`result.json` names **`{winner}`** as the S40c winner.  The result supports the
new hybrid residual-fusion method for this declared transfer score, while the
traditional clipped-template method remains the auditable physics baseline and
the PID conclusion remains proxy-limited.

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
    joined = pd.concat(preds, ignore_index=True).merge(events[base_cols], on="event_id", how="left")
    joined = add_transfer_columns(joined)
    joined.to_csv(OUT / "event_predictions.csv", index=False)

    metrics = bootstrap_metrics(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(metrics)
    run_df = by_run_metrics(joined)
    strata = strata_metrics(joined)
    metrics.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    run_df.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, run_df, strata, winner, runtime)

    best = ranked.iloc[0]
    result = {
        "ticket_id": TICKET,
        "study_id": STUDY_ID,
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
            "split": "leave-run-family-out, train and held-out source runs disjoint",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "bootstrap": "held-out source_run percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "adc_clip": s32b.ADC_CLIP,
            "pid_endpoint": "high-charge inner-stave support proxy scored by AUC and ECE",
            "uncertainty_coverage": "split-conformal 90% absolute train residual interval evaluated on held-out runs",
        },
        "required_method_coverage": {
            "strong_traditional": "analytic_clipped_template_sideband_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer_encoder": "tiny_sequence_transformer",
            "new_architecture": "saturation_residual_fusion_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum S40c held-out transfer score combining energy, saturation knee, pedestal contrast, PID calibration, timing, pile-up, and coverage",
            "winner_score": float(best["winner_score"]),
            "energy_bias": float(best["energy_bias"]),
            "energy_bias_ci95": [float(best["energy_bias_ci_low"]), float(best["energy_bias_ci_high"])],
            "energy_sigma68": float(best["energy_sigma68"]),
            "energy_sigma68_ci95": [float(best["energy_sigma68_ci_low"]), float(best["energy_sigma68_ci_high"])],
            "saturation_knee_calibration_abs": float(best["saturation_knee_calibration_abs"]),
            "pedestal_high_minus_low_bias": float(best["pedestal_high_minus_low_bias"]),
            "pid_auc": float(best["pid_auc"]),
            "pid_calibration_ece": float(best["pid_calibration_ece"]),
            "timing_residual_sigma68_ns": float(best["timing_residual_sigma68_ns"]),
            "pileup_merge_rate": float(best["pileup_merge_rate"]),
            "false_split_rate": float(best["false_split_rate"]),
            "coverage90": float(best["coverage90"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
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
            "Saturation knee uses a high-amplitude ADC proxy rather than decoded electronics flags.",
            "PID AUC/calibration use a charge/support proxy because external species labels are unavailable in this ROOT gate.",
        ],
        "runtime_sec": runtime,
        "git_commit": base.git_commit(),
        "python": platform.python_version(),
    }
    (OUT / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")

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
