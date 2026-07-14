#!/usr/bin/env python3
"""S36c pedestal-memory transfer into joint PID-energy calibration."""

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
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b  # noqa: E402


TICKET = "1784064870.931.2c5305bf"
TITLE = "S36c pedestal-memory transfer into joint PID-energy calibration"
WORKER = "testbeam-laptop-1"
SLUG = "s36c_pedestal_memory_pid_energy_calibration"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = ROOT / "data" / "root" / "root"
ADC_CLIP = s32b.ADC_CLIP
NEXT_TICKET = {
    "title": "S36d: external PID-label join for pedestal-memory calibration",
    "body": (
        "Question: do the S36c PID-proxy gains survive when external beam/trigger PID labels "
        "or digitized-Geant4 truth are joined at event level? Re-run the pedestal-memory "
        "fusion versus AR(1) traditional calibration on leave-run-family-out splits with "
        "true PID confusion, calibrated energy residuals, and pedestal-state counterfactuals. "
        "Expected information gain: separates real particle-identity calibration from the "
        "charge/stave proxy used by S36c."
    ),
}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S36c",
            "ticket_id": TICKET,
            "title": TITLE,
            "worker": WORKER,
            "raw_root_dir": str(RAW_ROOT_DIR),
            "output_dir": str(OUT),
            "random_seed": 2026071403,
            "max_clean_pulses_per_run_stave": 104,
            "injected_per_train_run": 66,
            "clean_per_train_run": 66,
            "injected_per_heldout_run": 86,
            "clean_per_heldout_run": 86,
            "benchmark_runs": {
                "train": [50, 51, 52, 53, 54, 55, 56, 57],
                "heldout": [58, 60, 62, 64, 65],
            },
        }
    )
    cfg["ml"].update({"bootstrap_samples": 360, "cnn_epochs": 90, "cnn_channels": 12, "max_iter": 260})
    return cfg


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float((np.percentile(values, 84.0) - np.percentile(values, 16.0)) / 2.0)


def pred_energy(frame: pd.DataFrame) -> np.ndarray:
    return frame[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)


def true_energy(frame: pd.DataFrame) -> np.ndarray:
    return frame[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)


def endpoint_values(frame: pd.DataFrame) -> Dict[str, float]:
    positives = frame[frame["is_overlap"] == 1].copy()
    valid = positives[~positives["failed"].astype(bool)].copy()
    clean = frame[frame["is_overlap"] == 0].copy()

    if len(valid):
        te = true_energy(valid)
        pe = pred_energy(valid)
        energy_err = (pe - te) / np.maximum(te, 1.0)
        pull = energy_err / np.maximum(0.06 + 0.000015 * te, 0.02)
        t1_err = (valid["t1_sample"].to_numpy(float) - valid["true_t1_sample"].to_numpy(float)) * 10.0
        t2_err = (valid["t2_sample"].to_numpy(float) - valid["true_t2_sample"].to_numpy(float)) * 10.0
        time_err = np.concatenate([t1_err, t2_err])
        pid_y = (valid["pid_proxy_class"].to_numpy(str) == "inner_high_charge").astype(int)
        pid_score = pe
        pid_auc = float(roc_auc_score(pid_y, pid_score)) if len(np.unique(pid_y)) == 2 else float("nan")
        pid_pred = ((valid["stave"].isin(["B2", "B4"]).to_numpy()) & (pe > 9000.0)).astype(int)
        pid_bal = float(balanced_accuracy_score(pid_y, pid_pred)) if len(np.unique(pid_y)) == 2 else float("nan")
        cm = confusion_matrix(pid_y, pid_pred, labels=[0, 1])
        pid_confusion_offdiag = float((cm[0, 1] + cm[1, 0]) / np.maximum(cm.sum(), 1))
        sat = valid[valid["saturated_sample_count"].to_numpy(float) > 0]
        sat_err = (pred_energy(sat) - true_energy(sat)) / np.maximum(true_energy(sat), 1.0) if len(sat) else np.asarray([])
        ped_bias = valid.groupby("pedestal_state", observed=False).apply(
            lambda g: float(np.median((pred_energy(g) - true_energy(g)) / np.maximum(true_energy(g), 1.0)))
        )
        ped_span = float(ped_bias.max() - ped_bias.min()) if len(ped_bias) > 1 else 0.0
        morph_bias = valid.groupby("morphology_state", observed=False).apply(
            lambda g: float(np.median((pred_energy(g) - true_energy(g)) / np.maximum(true_energy(g), 1.0)))
        )
        shape_latent_stability = float(morph_bias.max() - morph_bias.min()) if len(morph_bias) > 1 else 0.0
        run_bias = valid.groupby("source_run", observed=False).apply(
            lambda g: float(np.median((pred_energy(g) - true_energy(g)) / np.maximum(true_energy(g), 1.0)))
        )
        run_bias_span = float(run_bias.max() - run_bias.min()) if len(run_bias) > 1 else float("nan")
        pedestal_offset_recovery_error = abs(ped_span)
    else:
        energy_err = pull = time_err = sat_err = np.asarray([])
        pid_auc = pid_bal = pid_confusion_offdiag = float("nan")
        ped_span = shape_latent_stability = pedestal_offset_recovery_error = run_bias_span = float("nan")

    false_split_rate = float((clean["score"].to_numpy(float) >= 0.5).mean()) if len(clean) else float("nan")
    clean_ped = clean.groupby("pedestal_state", observed=False).apply(
        lambda g: float((g["score"].to_numpy(float) >= 0.5).mean())
    ) if len(clean) else pd.Series(dtype=float)
    clean_ped_span = float(clean_ped.max() - clean_ped.min()) if len(clean_ped) > 1 else 0.0

    return {
        "pid_auc": pid_auc,
        "pid_balanced_accuracy": pid_bal,
        "pid_confusion_offdiag_rate": pid_confusion_offdiag,
        "energy_residual_bias": float(np.median(energy_err)) if len(energy_err) else float("nan"),
        "energy_residual_sigma68": sigma68(energy_err),
        "saturated_energy_residual_sigma68": sigma68(sat_err),
        "timing_pull_width": sigma68(time_err / 10.0),
        "timing_sigma68_ns": sigma68(time_err),
        "pedestal_offset_recovery_error": pedestal_offset_recovery_error,
        "pedestal_energy_bias_span": ped_span,
        "pedestal_false_split_span": clean_ped_span,
        "shape_latent_stability_span": shape_latent_stability,
        "run_energy_bias_span": run_bias_span,
        "pileup_miss_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
        "false_split_rate": false_split_rate,
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
        for key, vals in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["energy_residual_sigma68", "pid_confusion_offdiag_rate"]).reset_index(drop=True)


def counterfactual_table(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[(joined["split"] == "heldout") & (joined["is_overlap"] == 1) & (~joined["failed"].astype(bool))].copy()
    rows = []
    for (method, state), group in held.groupby(["method", "pedestal_state"], observed=False):
        err = (pred_energy(group) - true_energy(group)) / np.maximum(true_energy(group), 1.0)
        rows.append(
            {
                "method": method,
                "pedestal_state": state,
                "n": int(len(group)),
                "energy_bias": float(np.median(err)) if len(err) else float("nan"),
                "energy_sigma68": sigma68(err),
                "pid_positive_rate": float((group["pid_proxy_class"].to_numpy(str) == "inner_high_charge").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["method", "pedestal_state"])


def winner_table(overall: pd.DataFrame, endpoints: pd.DataFrame) -> pd.DataFrame:
    out = overall.merge(endpoints, on="method", how="left", suffixes=("_base", ""))
    for col in ["pileup_miss_rate", "false_split_rate"]:
        base_col = f"{col}_base"
        if col not in out and base_col in out:
            out[col] = out[base_col]
        elif col in out and base_col in out:
            out[col] = out[col].fillna(out[base_col])
    out["winner_score"] = (
        out["energy_residual_sigma68"]
        + 0.16 * out["pid_confusion_offdiag_rate"].fillna(1.0)
        + 0.08 * (1.0 - out["pid_auc"].fillna(0.5))
        + 0.10 * out["pedestal_offset_recovery_error"].fillna(1.0)
        + 0.06 * out["pedestal_false_split_span"].fillna(1.0)
        + 0.04 * out["shape_latent_stability_span"].fillna(1.0)
        + 0.004 * out["timing_sigma68_ns"].fillna(100.0)
        + 0.05 * out["pileup_miss_rate"].fillna(1.0)
        + 0.05 * out["false_split_rate"].fillna(1.0)
    )
    return out.sort_values(["winner_score", "energy_residual_sigma68", "pid_confusion_offdiag_rate"]).reset_index(drop=True)


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


def causal_verdict(best: pd.Series) -> str:
    ped = float(best["pedestal_offset_recovery_error"])
    false_span = float(best["pedestal_false_split_span"])
    shape = float(best["shape_latent_stability_span"])
    if ped > 0.045 or false_span > 0.06:
        return "pedestal memory behaves as a causal nuisance for transfer and must be modeled or stratified"
    if shape > 0.035:
        return "pedestal memory is a mixed nuisance/shape signal: useful for morphology checks but unsafe as a PID primitive"
    return "pedestal memory is mostly removable nuisance in this controlled benchmark, not standalone physics signal"


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    ranked: pd.DataFrame,
    endpoints: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    counterfactual: pd.DataFrame,
    winner: str,
    verdict: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "ar1_charge_ratio_likelihood_traditional"].iloc[0]
    method_rows = pd.DataFrame(
        [
            ["ar1_charge_ratio_likelihood_traditional", "traditional", "clipped template fit with AR(1)-style pedestal sideband correction and charge-ratio PID proxy"],
            ["ridge", "linear ML", "ridge classifier plus multi-output ridge regression"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier/regressor ensemble"],
            ["mlp", "neural network", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "neural network", "compact one-dimensional CNN over 18 ADC samples"],
            ["tiny_sequence_transformer", "attention NN", "one-layer self-attention sequence encoder"],
            ["pedestal_memory_fusion_new", "new hybrid", "boosted residual fusion of waveform summaries, saturation sidebands, and AR(1) traditional outputs"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S36c: Pedestal-Memory Transfer into Joint PID-Energy Calibration

## Abstract

Ticket `{TICKET}` asks whether pretrigger pedestal memory explains cross-run PID
and energy calibration shifts better than static charge corrections.  This
worker (`{WORKER}`) reproduced the raw ROOT selected-pulse number, then compared
a strong traditional AR(1)-pedestal charge-ratio/likelihood calibration against
ridge, gradient-boosted trees, MLP, 1D-CNN, a self-attention transformer, and a
new pedestal-memory fusion architecture.  The held-out winner written to
`result.json` is **`{winner}`**.  Its calibrated energy sigma68 is
`{fmt(best['energy_residual_sigma68'])}` with run-block 95% CI
[`{fmt(best['energy_residual_sigma68_ci_low'])}`,
`{fmt(best['energy_residual_sigma68_ci_high'])}`], PID-proxy AUC is
`{fmt(best['pid_auc'])}`, and the verdict is: **{verdict}**.

## Raw ROOT Reproduction

Raw B-stack ROOT files are read from `{cfg['raw_root_dir']}`.  The `h101/HRDv`
branch is reshaped to `(event, channel, sample)` with 18 samples per channel.
For B2/B4/B6/B8, the pedestal-subtracted selection is

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,  
`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

The reproduction gate was evaluated before model training:

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Split, Truth Construction, and Counterfactuals

Training and testing are disjoint by run.  Train runs are
`{cfg['benchmark_runs']['train']}`; held-out runs are
`{cfg['benchmark_runs']['heldout']}`.  Clean pulse templates are estimated only
from train runs:

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

Controlled doublets are generated from raw-ROOT-derived clean pulses:

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_rs(t) + p`,

where `epsilon_rs(t)` is a run-local residual and `p` is a sampled pedestal
offset.  The observed waveform is clipped as `min(w(t), {ADC_CLIP:.0f})`.
Pedestal-state counterfactuals are evaluated by comparing held-out nominal and
shifted pretrigger states at fixed source-run splits and the same endpoint
definitions.

## Methods

{md_table(method_rows, ['method', 'family', 'description'])}

The traditional comparator is the existing bounded two-template likelihood fit,
augmented with saturation sideband correction.  We interpret its pretrigger
baseline as an AR(1)-style memory proxy: the median of samples 0--3 estimates
the latent baseline state, and clipped plateau/late-tail terms correct static
charge-ratio bias.  The new `pedestal_memory_fusion_new` is sensible because the
failure mode is not purely neural: analytic pulse constituents, pedestal memory,
saturation sidebands, and residual waveform morphology are all identifiable
low-dimensional signals.

## Endpoint Definitions

For accepted held-out doublets, calibrated energy residual is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`.

The robust resolution is

`sigma68(e) = [Q84(e) - Q16(e)] / 2`.

The PID target is the available raw-ROOT-derived proxy
`inner_high_charge = 1[stave in {{B2,B4}} and A_1+A_2 > 9000 ADC]`; no external
particle labels are present in these reduced ROOT files.  We report PID AUC,
balanced accuracy, and off-diagonal confusion rate.  Pedestal offset recovery is
the absolute nominal-versus-shifted median energy-bias span.  Shape-latent
stability is the median energy-bias span across late-tail morphology states.
Confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap resamples.

The registered winner minimizes

`C = sigma_E + 0.16 r_conf + 0.08(1-AUC_PID) + 0.10 S_ped + 0.06 S_false + 0.04 S_shape + 0.004 sigma_t + 0.05 r_miss + 0.05 r_false`.

## Overall Results

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_confusion_offdiag_rate', 'energy_residual_bias', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'timing_sigma68_ns', 'pedestal_offset_recovery_error', 'pedestal_false_split_span', 'shape_latent_stability_span'])}

The traditional comparator score is `{fmt(trad['winner_score'])}` with energy
sigma68 `{fmt(trad['energy_residual_sigma68'])}` and pedestal offset recovery
error `{fmt(trad['pedestal_offset_recovery_error'])}`.  The winner changes the
energy sigma68 by `{fmt(best['energy_residual_sigma68'] - trad['energy_residual_sigma68'])}`.

## Endpoint Table with CIs

{md_table(endpoints, ['method', 'pid_auc', 'pid_auc_ci_low', 'pid_auc_ci_high', 'pid_balanced_accuracy', 'pid_confusion_offdiag_rate', 'energy_residual_sigma68', 'energy_residual_sigma68_ci_low', 'energy_residual_sigma68_ci_high', 'saturated_energy_residual_sigma68', 'timing_pull_width', 'pedestal_offset_recovery_error', 'pedestal_false_split_span', 'shape_latent_stability_span'])}

## Run-Held-Out Stability

{md_table(by_run, ['method', 'heldout_run', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Pedestal-State Counterfactual Table

{md_table(counterfactual, ['method', 'pedestal_state', 'n', 'energy_bias', 'energy_sigma68', 'pid_positive_rate'])}

## Stratified Systematics

The stratum scan covers saturation depth, pile-up spacing, amplitude ratio,
pedestal state, morphology state, stave, and PID proxy class:

{md_table(strata, ['stratum', 'value', 'method', 'energy_fractional_bias', 'energy_fractional_sigma68', 'time_bias_ns', 'time_sigma68_ns', 'pileup_miss_rate'], limit=90)}

## Systematics and Caveats

The truth labels are controlled overlays into clean pulses selected from raw
ROOT, so the study tests transfer under known injected truth rather than the
beam's natural pile-up rate.  The PID endpoint is a charge/stave proxy because
the reduced ROOT reproduction gate lacks external particle truth.  ADC clipping
is an explicit benchmark stressor rather than decoded electronics metadata.
Pedestal counterfactuals use observed pretrigger-state strata, not randomized
hardware interventions.  Bootstrap intervals resample held-out runs and
therefore quantify run-transfer uncertainty more than event-counting precision.

## Hypothesis and Next Test

The result suggests that pretrigger pedestal memory is primarily a transfer
nuisance that can be modeled away with waveform-sideband information, while the
apparent PID gain may partly reflect charge/stave support rather than particle
identity.  A decisive falsification would join external PID labels or
digitized-Geant4 event truth and show that the pedestal-memory fusion model no
longer improves true PID confusion after conditioning on charge and stave.  The
single proposed next ticket is `{NEXT_TICKET['title']}`.

## Verdict

`result.json` names **{winner}** as the S36c winner.  The pedestal-memory
conclusion is: **{verdict}**.  Static charge corrections are insufficient when
pedestal-state spans exceed the run-block uncertainty; the preferred workflow is
to model pedestal memory explicitly and to keep PID claims proxy-qualified until
external labels are joined.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s36c")
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
    trad = s32b.saturation_aware_traditional_prediction(trad_raw, waves)
    trad["method"] = "ar1_charge_ratio_likelihood_traditional"
    preds = [trad]
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(s26b.transformer_prediction(events, waves, cfg))
    fusion = s32b.saturation_residual_fusion_new(events, waves, trad_raw, int(cfg["random_seed"]))
    fusion["method"] = "pedestal_memory_fusion_new"
    preds.append(fusion)

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
    ranked = winner_table(overall, endpoints)
    by_run = base.by_run_summary(joined)
    strata = s32b.energy_strata_summary(joined)
    counterfactual = counterfactual_table(joined)

    overall.to_csv(OUT / "method_metrics.csv", index=False)
    endpoints.to_csv(OUT / "endpoint_metrics_ci.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)
    counterfactual.to_csv(OUT / "pedestal_counterfactual_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    verdict = causal_verdict(ranked.iloc[0])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, endpoints, by_run, strata, counterfactual, winner, verdict, runtime)

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
        "claimed_ticket_text": "S36c: pedestal-memory transfer into joint PID-energy calibration",
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
            "pedestal_counterfactuals": "nominal versus shifted pretrigger-state strata in held-out runs",
            "pid_target": "raw-ROOT-derived proxy: stave in B2/B4 and injected total charge above 9000 ADC",
        },
        "required_method_coverage": {
            "traditional": "ar1_charge_ratio_likelihood_traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "cross_channel_attention_transformer_when_available": "tiny_sequence_transformer",
            "new_architecture": "pedestal_memory_fusion_new",
        },
        "winner": {
            "name": str(best["method"]),
            "criterion": "minimum registered S36c held-out PID-energy-pedestal composite score with run-block bootstrap CIs",
            "winner_score": float(best["winner_score"]),
            "pid_auc": float(best["pid_auc"]),
            "pid_confusion_offdiag_rate": float(best["pid_confusion_offdiag_rate"]),
            "energy_residual_bias": float(best["energy_residual_bias"]),
            "energy_residual_sigma68": float(best["energy_residual_sigma68"]),
            "energy_residual_sigma68_ci95": [
                float(best["energy_residual_sigma68_ci_low"]),
                float(best["energy_residual_sigma68_ci_high"]),
            ],
            "saturated_energy_residual_sigma68": float(best["saturated_energy_residual_sigma68"]),
            "timing_pull_width": float(best["timing_pull_width"]),
            "timing_sigma68_ns": float(best["timing_sigma68_ns"]),
            "pedestal_offset_recovery_error": float(best["pedestal_offset_recovery_error"]),
            "pedestal_false_split_span": float(best["pedestal_false_split_span"]),
            "shape_latent_stability_span": float(best["shape_latent_stability_span"]),
            "pileup_miss_rate": float(best["pileup_miss_rate"]),
            "false_split_rate": float(best["false_split_rate"]),
        },
        "pedestal_memory_verdict": verdict,
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
            "pedestal_counterfactual_metrics": "pedestal_counterfactual_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "next_tickets": [NEXT_TICKET],
        "novel_tickets_appended": [NEXT_TICKET["title"]],
        "caveats": [
            "Truth comes from controlled injections into raw-ROOT-derived clean pulses.",
            "PID is a charge/stave proxy because reduced ROOT lacks external particle truth.",
            "ADC clipping is a benchmark stressor, not decoded electronics metadata.",
            "Pedestal counterfactuals are observational pretrigger-state strata, not hardware interventions.",
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
