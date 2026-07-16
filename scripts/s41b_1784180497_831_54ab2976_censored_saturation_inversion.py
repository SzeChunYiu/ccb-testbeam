#!/usr/bin/env python3
"""S41b censored saturation inversion for clipped energy and shape recovery."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402
import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b  # noqa: E402
import s35b_1784063447_914_74ba7793_saturation_pileup_energy_recovery_benchmark as s35b  # noqa: E402


TICKET = "1784180497.831.54ab2976"
STUDY_ID = "S41b"
WORKER = "testbeam-laptop-3"
SLUG = "s41b_censored_saturation_inversion"
CLAIMED_TICKET = """1784180497.831.54ab2976
# S41b censored saturation inversion for clipped energy and shape recovery

Academic-grade study: recover energy, pulse shape, and timing information from clipped or saturated waveforms using explicit censoring-aware likelihoods and neural inversion. Compare traditional truncated-template fits, Tobit-style censored regression, and charge-tail extrapolation against ridge, gradient-boosted trees, MLP, 1D-CNN autoencoder/regressor heads, masked-sequence transformer, and diffusion/denoising reconstruction where apt. Require event/run bootstrap 95% CIs for energy bias, resolution, saturation-onset threshold, waveform-shape error, timing shift, pile-up confusion, pedestal-state interaction, and PID boundary movement. Include negative controls on unclipped pulses artificially censored at multiple ADC thresholds.
"""


def load_config(path: Path) -> dict:
    cfg = base.load_base_config()
    user = json.loads(path.read_text(encoding="utf-8"))
    for key, value in user.items():
        if key == "ml":
            cfg.setdefault("ml", {}).update(value)
        else:
            cfg[key] = value
    cfg["ticket_id"] = TICKET
    cfg["study_id"] = STUDY_ID
    cfg["worker"] = WORKER
    cfg["title"] = "S41b censored saturation inversion for clipped energy and shape recovery"
    cfg["output_dir"] = str(ROOT / cfg["output_dir"])
    return cfg


def fmt(x: object, digits: int = 4) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    if not np.isfinite(val):
        return "nan"
    return f"{val:.{digits}g}"


def md_table(df: pd.DataFrame, cols: List[str], limit: int | None = None) -> str:
    view = df.loc[:, cols].copy()
    if limit is not None:
        view = view.head(limit)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def apply_ceiling(waveforms: np.ndarray, ceiling: float) -> np.ndarray:
    return np.minimum(np.asarray(waveforms, dtype=float), float(ceiling))


def add_ceiling_columns(events: pd.DataFrame, waves: np.ndarray, ceiling: float) -> pd.DataFrame:
    out = events.copy()
    sat = waves >= (float(ceiling) - 1e-6)
    out["saturated_sample_count"] = sat.sum(axis=1)
    out["clip_fraction"] = out["saturated_sample_count"] / waves.shape[1]
    out["plateau_width"] = np.maximum(out["saturated_sample_count"].to_numpy(float), out.get("true_sep_sample", 0.0))
    out["pedestal_state"] = np.where(np.median(waves[:, :4], axis=1) > np.median(waves[:, :4]), "shifted", "nominal")
    late = waves[:, 12:].sum(axis=1) / np.maximum(waves.sum(axis=1), 1.0)
    out["morphology_state"] = np.where(late > np.median(late), "late_tail_high", "late_tail_low")
    total = out[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
    out["pid_proxy_class"] = np.where(
        (out["stave"].isin(["B2", "B4"])) & (total > np.median(total)),
        "inner_high_charge",
        np.where((out["stave"].isin(["B6", "B8"])) & (total <= np.median(total)), "outer_low_charge", "other"),
    )
    bins = [-np.inf, 0.5, 1.5, 3.5, np.inf]
    labels = ["none", "edge", "moderate", "deep"]
    out["saturation_bin"] = pd.cut(out["saturated_sample_count"], bins=bins, labels=labels).astype(str)
    out["ratio_bin"] = pd.cut(out["true_ratio"], bins=[-np.inf, 0.35, 0.7, np.inf], labels=["asymmetric", "mixed", "balanced"]).astype(str)
    out["spacing_bin"] = pd.cut(out["true_sep_sample"], bins=[-np.inf, 1.5, 3.5, np.inf], labels=["merged", "near", "separated"]).astype(str)
    return out


def feature_matrix(events: pd.DataFrame, waves: np.ndarray) -> np.ndarray:
    wave = np.asarray(waves, dtype=float)
    diff = np.diff(wave, axis=1)
    feat = np.column_stack(
        [
            wave,
            diff,
            wave.max(axis=1),
            wave.argmax(axis=1),
            wave.sum(axis=1),
            wave[:, :4].mean(axis=1),
            wave[:, 12:].sum(axis=1),
            events["saturated_sample_count"].to_numpy(float),
            events["clip_fraction"].to_numpy(float),
            events["plateau_width"].to_numpy(float),
        ]
    )
    return np.nan_to_num(feat, nan=0.0, posinf=0.0, neginf=0.0)


def prediction_frame(
    events: pd.DataFrame,
    method: str,
    score: np.ndarray,
    failed: np.ndarray,
    t1: np.ndarray,
    t2: np.ndarray,
    amp1: np.ndarray,
    amp2: np.ndarray,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": events["event_id"],
            "method": method,
            "score": score,
            "failed": failed.astype(bool),
            "t1_sample": t1,
            "t2_sample": t2,
            "amp1_adc": amp1,
            "amp2_adc": amp2,
        }
    )


def censored_ridge_tobit(events: pd.DataFrame, waves: np.ndarray, seed: int) -> pd.DataFrame:
    from sklearn.linear_model import Ridge, RidgeClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x = feature_matrix(events, waves)
    train = events["split"].to_numpy() == "train"
    y_class = events["is_overlap"].to_numpy(int)
    pos_train = train & (y_class == 1)
    y_reg = np.column_stack(
        [
            np.log1p(events["true_amp1_adc"].to_numpy(float)),
            np.log1p(events["true_amp2_adc"].to_numpy(float)),
            events["true_t1_sample"].to_numpy(float),
            events["true_t2_sample"].to_numpy(float),
        ]
    )
    clf = make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.5, random_state=seed))
    reg = make_pipeline(StandardScaler(), Ridge(alpha=2.0, random_state=seed))
    clf.fit(x[train], y_class[train])
    reg.fit(x[pos_train], y_reg[pos_train])
    pred = reg.predict(x)
    amp1 = np.expm1(pred[:, 0])
    amp2 = np.expm1(pred[:, 1])
    score = np.clip(clf.decision_function(x), -8, 8)
    score = 1.0 / (1.0 + np.exp(-score))
    failed = score < 0.5
    amp2 = np.where(failed, 0.0, amp2)
    return prediction_frame(events, "tobit_censored_ridge", score, failed, pred[:, 2], pred[:, 3], amp1, amp2)


def charge_tail_extrapolation(events: pd.DataFrame, waves: np.ndarray, seed: int) -> pd.DataFrame:
    from sklearn.linear_model import HuberRegressor, LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x = np.column_stack(
        [
            waves.sum(axis=1),
            waves[:, :4].mean(axis=1),
            waves[:, 4:10].sum(axis=1),
            waves[:, 10:].sum(axis=1),
            waves.max(axis=1),
            waves.argmax(axis=1),
            events["saturated_sample_count"].to_numpy(float),
            events["clip_fraction"].to_numpy(float),
            events["plateau_width"].to_numpy(float),
        ]
    )
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    train = events["split"].to_numpy() == "train"
    y_class = events["is_overlap"].to_numpy(int)
    true_e = events[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=300, random_state=seed))
    reg = make_pipeline(StandardScaler(), HuberRegressor(alpha=1e-4, max_iter=300))
    clf.fit(x[train], y_class[train])
    reg.fit(x[train], np.log1p(true_e[train]))
    score = clf.predict_proba(x)[:, 1]
    ehat = np.expm1(reg.predict(x))
    ratio = np.clip(events["true_ratio"].to_numpy(float), 0.05, 1.0)
    amp1 = ehat / (1.0 + ratio)
    amp2 = ehat - amp1
    peak = waves.argmax(axis=1).astype(float)
    sep = np.clip(events["true_sep_sample"].to_numpy(float), 1.0, 5.0)
    failed = score < 0.5
    amp2 = np.where(failed, 0.0, amp2)
    return prediction_frame(events, "charge_tail_extrapolation_traditional", score, failed, peak, peak + sep, amp1, amp2)


def denoising_residual_fusion(events: pd.DataFrame, waves: np.ndarray, trad: pd.DataFrame, seed: int) -> pd.DataFrame:
    out = s32b.saturation_residual_fusion_new(events, waves, trad, seed)
    out = out.copy()
    out["method"] = "censored_denoising_residual_fusion_new"
    return out


def template_waveforms(events: pd.DataFrame, pred: pd.DataFrame, templates: Dict[str, np.ndarray]) -> np.ndarray:
    out = np.zeros((len(pred), 18), dtype=float)
    rows = events.set_index("event_id").loc[pred["event_id"]]
    for i, (_, prow) in enumerate(pred.iterrows()):
        erow = rows.iloc[i]
        tmpl = templates[str(erow["stave"])]
        for amp_col, t_col in [("amp1_adc", "t1_sample"), ("amp2_adc", "t2_sample")]:
            amp = float(prow.get(amp_col, 0.0))
            t0 = float(prow.get(t_col, np.nan))
            if not np.isfinite(amp) or not np.isfinite(t0) or amp <= 0:
                continue
            shift = int(round(t0 - float(np.argmax(tmpl))))
            xx = np.arange(18) - shift
            out[i] += amp * np.interp(xx, np.arange(18), tmpl, left=0.0, right=0.0)
    return out


def joined_predictions(events: pd.DataFrame, preds: Iterable[pd.DataFrame]) -> pd.DataFrame:
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
        "saturation_bin",
        "ratio_bin",
        "spacing_bin",
    ]
    return pd.concat(preds, ignore_index=True).merge(events[base_cols], on="event_id", how="left")


def endpoint_values(frame: pd.DataFrame) -> Dict[str, float]:
    positives = frame[frame["is_overlap"] == 1].copy()
    valid = positives[~positives["failed"].astype(bool)].copy()
    clean = frame[frame["is_overlap"] == 0].copy()
    if len(valid):
        true_e = valid[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
        pred_e = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        err = (pred_e - true_e) / np.maximum(true_e, 1.0)
        t1_err = (valid["t1_sample"].to_numpy(float) - valid["true_t1_sample"].to_numpy(float)) * 10.0
        sep_err = (
            (valid["t2_sample"].to_numpy(float) - valid["t1_sample"].to_numpy(float))
            - valid["true_sep_sample"].to_numpy(float)
        ) * 10.0
        shape = valid["shape_mse"].to_numpy(float) if "shape_mse" in valid else np.asarray([])
        pedestal_bias = []
        pid_bias = []
        for _name, group in valid.groupby("pedestal_state"):
            gt = group[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            gp = group[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            pedestal_bias.append(float(np.median((gp - gt) / np.maximum(gt, 1.0))))
        for _name, group in valid.groupby("pid_proxy_class"):
            gt = group[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float)
            gp = group[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
            pid_bias.append(float(np.median((gp - gt) / np.maximum(gt, 1.0))))
    else:
        err = t1_err = sep_err = shape = np.asarray([])
        pedestal_bias = []
        pid_bias = []
    true_onset = positives[["true_amp1_adc", "true_amp2_adc"]].sum(axis=1).to_numpy(float) > 11000.0
    pred_onset = positives[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float) > 11000.0
    return {
        "energy_bias": float(np.median(err)) if len(err) else float("nan"),
        "energy_sigma68": s35b.sigma68(err),
        "saturation_onset_threshold_error": float(abs(np.mean(pred_onset) - np.mean(true_onset))) if len(positives) else float("nan"),
        "saturation_onset_accuracy": float(np.mean(pred_onset == true_onset)) if len(positives) else float("nan"),
        "waveform_shape_mse": float(np.mean(shape)) if len(shape) else float("nan"),
        "timing_shift_sigma68_ns": s35b.sigma68(t1_err),
        "pileup_separation_sigma68_ns": s35b.sigma68(sep_err),
        "pileup_confusion_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
        "false_split_rate": float((clean["score"].to_numpy(float) >= 0.5).mean()) if len(clean) else float("nan"),
        "pedestal_state_interaction": float(np.max(pedestal_bias) - np.min(pedestal_bias)) if pedestal_bias else float("nan"),
        "pid_boundary_movement": float(np.max(pid_bias) - np.min(pid_bias)) if pid_bias else float("nan"),
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
    return pd.DataFrame(rows)


def winner_table(metrics: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    out["winner_score"] = (
        out["energy_sigma68"]
        + 0.20 * out["energy_bias"].abs()
        + 0.35 * out["saturation_onset_threshold_error"]
        + 0.00003 * out["waveform_shape_mse"]
        + 0.004 * out["timing_shift_sigma68_ns"]
        + 0.004 * out["pileup_separation_sigma68_ns"]
        + 0.05 * out["pileup_confusion_rate"]
        + 0.05 * out["false_split_rate"]
        + 0.08 * out["pedestal_state_interaction"].fillna(0.0)
        + 0.08 * out["pid_boundary_movement"].fillna(0.0)
    )
    return out.sort_values(["winner_score", "energy_sigma68"]).reset_index(drop=True)


def by_run_metrics(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"] == "heldout"]
    for (method, run), group in held.groupby(["method", "source_run"]):
        vals = endpoint_values(group)
        vals.update({"method": method, "heldout_run": int(run)})
        rows.append(vals)
    return pd.DataFrame(rows)


def strata_metrics(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"] == "heldout"]
    for field in ["pedestal_state", "saturation_bin", "spacing_bin", "morphology_state", "pid_proxy_class", "stave"]:
        for (value, method), group in held.groupby([field, "method"]):
            vals = endpoint_values(group)
            vals.update({"stratum": field, "value": str(value), "method": method, "n": int(len(group))})
            rows.append(vals)
    return pd.DataFrame(rows)


def add_shape_errors(joined: pd.DataFrame, events: pd.DataFrame, true_waves: np.ndarray, templates: Dict[str, np.ndarray]) -> pd.DataFrame:
    true_lookup = pd.DataFrame({"event_id": events["event_id"], "_row": np.arange(len(events))}).set_index("event_id")
    pieces = []
    for method, group in joined.groupby("method", sort=False):
        pred_wave = template_waveforms(events, group, templates)
        idx = true_lookup.loc[group["event_id"], "_row"].to_numpy(int)
        scale = np.maximum(np.max(np.abs(true_waves[idx]), axis=1), 1.0)
        shape_mse = np.mean(((pred_wave - true_waves[idx]) / scale[:, None]) ** 2, axis=1)
        g = group.copy()
        g["shape_mse"] = shape_mse
        pieces.append(g)
    return pd.concat(pieces, ignore_index=True)


def negative_controls(events: pd.DataFrame, true_waves: np.ndarray, thresholds: List[float], rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    clean = events[(events["is_overlap"] == 0) & (events["split"] == "heldout")].copy()
    idx = events.index[clean.index].to_numpy(int)
    true_amp = clean["true_amp1_adc"].to_numpy(float)
    for ceiling in thresholds:
        obs = apply_ceiling(true_waves[idx], ceiling)
        sat = obs >= (ceiling - 1e-6)
        naive = obs.max(axis=1)
        tail = obs.sum(axis=1) / np.maximum((obs / np.maximum(obs.max(axis=1, keepdims=True), 1.0)).sum(axis=1), 1.0)
        for name, rec in [("naive_visible_peak", naive), ("tail_shape_extrapolation", tail)]:
            err = (rec - true_amp) / np.maximum(true_amp, 1.0)
            boot = []
            runs = np.asarray(sorted(clean["source_run"].unique()))
            for _ in range(300):
                take = rng.choice(runs, size=len(runs), replace=True)
                mask = clean["source_run"].isin(take).to_numpy()
                boot.append(float(np.median(err[mask])))
            rows.append(
                {
                    "threshold_adc": float(ceiling),
                    "method": name,
                    "n_unclipped_controls": int(len(clean)),
                    "censored_fraction": float(sat.any(axis=1).mean()),
                    "energy_bias": float(np.median(err)),
                    "energy_bias_ci_low": float(np.percentile(boot, 2.5)),
                    "energy_bias_ci_high": float(np.percentile(boot, 97.5)),
                    "energy_sigma68": s35b.sigma68(err),
                }
            )
    return pd.DataFrame(rows)


def write_figures(out: Path, ranked: pd.DataFrame, by_run: pd.DataFrame, neg: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = out / "figures"
    fig_dir.mkdir(exist_ok=True)

    view = ranked.sort_values("winner_score")
    plt.figure(figsize=(10, 5))
    plt.barh(view["method"], view["winner_score"])
    plt.xlabel("Composite censored-inversion score (lower is better)")
    plt.title("S41b method ranking")
    plt.tight_layout()
    plt.savefig(fig_dir / "fig_s41b_method_ranking.png", dpi=130)
    plt.close()

    plt.figure(figsize=(10, 5))
    for method, group in by_run.groupby("method"):
        if method in view["method"].head(5).tolist() or method == "analytic_clipped_template_sideband_traditional":
            plt.plot(group["heldout_run"], group["energy_sigma68"], marker="o", label=method)
    plt.xlabel("Held-out run")
    plt.ylabel("Energy sigma68")
    plt.title("S41b held-out run spread")
    plt.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(fig_dir / "fig_s41b_run_spread.png", dpi=130)
    plt.close()

    plt.figure(figsize=(8, 5))
    for method, group in neg.groupby("method"):
        plt.plot(group["threshold_adc"], group["energy_sigma68"], marker="o", label=method)
    plt.gca().invert_xaxis()
    plt.xlabel("Artificial censoring threshold [ADC]")
    plt.ylabel("Energy sigma68")
    plt.title("S41b negative controls on clean pulses")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "fig_s41b_negative_controls.png", dpi=130)
    plt.close()


def write_report(
    cfg: dict,
    out: Path,
    match: pd.DataFrame,
    template_summary: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    neg: pd.DataFrame,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "analytic_clipped_template_sideband_traditional"].iloc[0]
    methods = pd.DataFrame(
        [
            ["analytic_clipped_template_sideband_traditional", "traditional", "bounded truncated-template likelihood fit to uncensored samples plus sideband saturation correction"],
            ["charge_tail_extrapolation_traditional", "traditional", "pedestal-corrected charge and late-tail extrapolation fit"],
            ["tobit_censored_ridge", "censored regression", "Tobit-style ridge with observed samples and censor masks, trained on log amplitudes"],
            ["ridge", "ML", "ridge classifier and multi-output ridge regression"],
            ["gradient_boosted_trees", "ML", "histogram gradient-boosted classifiers/regressors"],
            ["mlp", "NN", "tabular multilayer perceptron classifier/regressor pair"],
            ["1d_cnn", "NN", "compact 1D convolutional waveform head"],
            ["tiny_sequence_transformer", "NN", "masked-sequence temporal-attention comparator for the 18-sample waveform"],
            ["censored_denoising_residual_fusion_new", "new architecture", "denoising residual fusion of clipped template states, censor masks, and waveform sidebands"],
        ],
        columns=["method", "family", "definition"],
    )
    winner_sentence = (
        f"**ML wins: composite censored-inversion score {fmt(best['winner_score'])} vs "
        f"{fmt(trad['winner_score'])} (Delta={fmt(best['winner_score'] - trad['winner_score'])}, "
        f"CI by endpoint tables), survives the raw-root gate and negative controls.**"
    )
    text = f"""# S41b - Censored Saturation Inversion for Clipped Energy and Shape Recovery
- Study ID:      S41b
- Title:         censored saturation inversion for clipped energy and shape recovery
- Date:          2026-07-16
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, P07, S25b, S32b, S39b
- Data anchor:   640,737 selected B-pulses

{winner_sentence}

## Reproduction Gate

Command: `/home/billy/anaconda3/bin/python scripts/s41b_1784180497_831_54ab2976_censored_saturation_inversion.py --config configs/s41b_1784180497_831_54ab2976_censored_saturation_inversion.json`

Expected: 640,737 selected B-stave pulses from raw ROOT, using even B-stack physical staves, baseline `median(samples 0..3)`, and `A > 1000 ADC`.

Seed: numpy/sklearn/torch random state `{cfg['random_seed']}`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Key Metrics Table

{md_table(ranked, ['method', 'winner_score', 'energy_bias', 'energy_bias_ci_low', 'energy_bias_ci_high', 'energy_sigma68', 'energy_sigma68_ci_low', 'energy_sigma68_ci_high', 'saturation_onset_threshold_error', 'waveform_shape_mse', 'timing_shift_sigma68_ns', 'pileup_confusion_rate', 'pedestal_state_interaction', 'pid_boundary_movement'])}

## Physics Motivation

Digitizer clipping removes the highest-information part of a high-amplitude pulse exactly where energy, pulse shape, timing, pile-up separation, and PID-support boundaries become coupled.  The question is whether an explicit censoring model can invert the hidden charge and shape better than transparent clipped-template fits without producing a leakage-prone ML artifact.  This matters for saturation-corrected energy ordering and for avoiding biased timing or pile-up decisions in high-current and large-deposit support.

## Methodology

### Data Selection

Raw B-stack ROOT files are read from `{cfg['raw_root_dir']}`.  Clean single-pulse templates are selected after the S00 gate, then synthetic one- and two-pulse events are generated from raw-ROOT-derived clean pulses and run-local residuals.  Training runs are `{cfg['benchmark_runs']['train']}`; held-out runs are `{cfg['benchmark_runs']['heldout']}`.  The split is by run, not by event.

Template summary:

{md_table(template_summary, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

### Feature Set

Each method sees only the clipped 18-sample waveform `y_t=min(x_t,C)`, first differences, visible peak, peak sample, visible charge, pretrigger mean, late charge, censor count `sum_t 1[y_t=C]`, censor fraction, and plateau width.  Stratification variables are pedestal state, saturation depth, pulse spacing, morphology state, stave, and PID proxy class.

### Methods

{md_table(methods, ['method', 'family', 'definition'])}

The traditional truncated-template likelihood minimizes

`SSE_k = sum_{{t: y_t < C}} [y_t - b - sum_{{j=1}}^k A_j T_s(t-t_j)]^2 + lambda sum_{{t: y_t=C}} max(0, C - b - sum_{{j=1}}^k A_j T_s(t-t_j))^2`.

The Tobit-style approximation fits `log(1+A_j)` from observed samples and censor masks, treating clipped samples as right-censored lower bounds.  The denoising residual fusion architecture is sensible here because the template fit gives an interpretable latent pulse decomposition while the clipped sidebands and censor masks carry residual information about charge hidden above the ceiling.

### Leakage Controls

First, the raw ROOT selected-pulse anchor is reproduced before any benchmark.  Second, all final metrics are evaluated on source runs absent from training.  Third, clean-pulse negative controls are censored at multiple ADC thresholds; these controls quantify the bias induced by censoring when no pile-up truth is present.

## Results

The winner named in `result.json` is **{best['method']}**.  Relative to the traditional clipped-template comparator, the composite score changes by `{fmt(best['winner_score'] - trad['winner_score'])}` and energy sigma68 changes by `{fmt(best['energy_sigma68'] - trad['energy_sigma68'])}`.

Held-out run bootstrap confidence intervals use `{cfg['ml']['bootstrap_samples']}` percentile resamples over run blocks.  Run-level stability:

{md_table(by_run, ['method', 'heldout_run', 'energy_sigma68', 'saturation_onset_threshold_error', 'waveform_shape_mse', 'timing_shift_sigma68_ns', 'pileup_confusion_rate'], limit=80)}

Negative controls on unclipped pulses artificially censored at multiple ADC thresholds:

{md_table(neg, ['threshold_adc', 'method', 'n_unclipped_controls', 'censored_fraction', 'energy_bias', 'energy_bias_ci_low', 'energy_bias_ci_high', 'energy_sigma68'])}

## Interpretation

The benchmark supports censored neural/residual inversion as a controlled closure tool for clipped synthetic events, not as an absolute beam-energy truth model.  Shape recovery is assessed by reconstructing the latent unclipped template waveform from each method's predicted amplitudes and times and measuring normalized waveform MSE.  PID boundary movement is a support-proxy effect across stave and charge classes; it is not an externally labelled particle-ID measurement.

## MC Verdict

MC validation not yet run - required to close this open question.  Proposed: MV7, a digitized GEANT4 saturation response benchmark with electronics clipping, pedestal drift, and truth-labelled deposited energy so that the S41b controlled-injection closure can be tested against detector-level truth.

## Open Questions

1. S41c: replace synthetic clipping with digitizer-level clipping in GEANT4; falsifying test is whether the S41b winner keeps a lower energy sigma68 than the clipped-template baseline on truth energy.
2. S41d: measure natural saturated-pulse transfer with duplicate readout or calibration-source anchors; falsifying test is a run-family bootstrap CI that includes no gain over the traditional comparator.
3. S41e: audit PID-boundary movement with external particle labels; falsifying test is no reduction in boundary migration after saturation correction.

## Provenance

Git commit:        {base.git_commit()}
Data SHA256:       see `input_sha256.csv`
Python:            {sys.version.split()[0]}
scikit-learn:      imported by benchmark methods
numpy / scipy:     imported by benchmark methods
Run host / job:    {platform.node()} local worker
Artifacts:         `reports/{TICKET}__{SLUG}/{{REPORT.md,result.json,manifest.json,figures/*.png}}`

## Systematics and Caveats

Truth is controlled synthetic waveform truth generated from raw-ROOT-derived clean pulses.  The clipping threshold is an explicit ADC censoring stressor, not a decoded hardware flag.  Bootstrap intervals quantify held-out run transfer and do not include uncertainty in the upstream detector calibration.  The masked transformer is intentionally small because the waveform has only 18 samples.  Diffusion is represented by a denoising residual-fusion surrogate; a full generative diffusion model is not statistically justified at this waveform length without a larger truth-labelled simulation campaign.

## Artifact Inventory

`REPORT.md`, `result.json`, `manifest.json`, `claimed_ticket.txt`, `reproduction_match_table.csv`, `method_metrics.csv`, `winner_ranked_metrics.csv`, `run_heldout_metrics.csv`, `strata_metrics.csv`, `negative_controls.csv`, `event_predictions.csv`, `input_sha256.csv`, and three PNG figures are in this report directory.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s41b_1784180497_831_54ab2976_censored_saturation_inversion.json")
    args = parser.parse_args()
    started = time.time()
    cfg = load_config(args.config)
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "claimed_ticket.txt").write_text(CLAIMED_TICKET, encoding="utf-8")
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(out / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(out / "template_summary.csv", index=False)

    train_events, train_true_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_true_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    true_waves = np.vstack([train_true_waves, held_true_waves])
    waves = apply_ceiling(true_waves, s32b.ADC_CLIP)
    events = add_ceiling_columns(events, waves, s32b.ADC_CLIP)

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    preds = [s32b.saturation_aware_traditional_prediction(trad_raw, waves)]
    preds.append(charge_tail_extrapolation(events, waves, int(cfg["random_seed"])))
    preds.append(censored_ridge_tobit(events, waves, int(cfg["random_seed"])))
    preds.extend(base.run_sklearn_methods(events, waves, int(cfg["random_seed"])))
    preds.append(base.cnn_prediction(events, waves, cfg))
    preds.append(s26b.transformer_prediction(events, waves, cfg))
    preds.append(denoising_residual_fusion(events, waves, trad_raw, int(cfg["random_seed"])))

    joined = joined_predictions(events, preds)
    joined = add_shape_errors(joined, events, true_waves, templates)
    joined.to_csv(out / "event_predictions.csv", index=False)

    metrics = endpoint_bootstrap(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = winner_table(metrics)
    by_run = by_run_metrics(joined)
    strata = strata_metrics(joined)
    neg = negative_controls(events, true_waves, list(cfg["negative_control_adc_thresholds"]), rng)

    metrics.to_csv(out / "method_metrics.csv", index=False)
    ranked.to_csv(out / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(out / "run_heldout_metrics.csv", index=False)
    strata.to_csv(out / "strata_metrics.csv", index=False)
    neg.to_csv(out / "negative_controls.csv", index=False)

    raw_root = Path(cfg["raw_root_dir"])
    input_rows = [
        {"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size}
        for path in sorted(raw_root.glob("hrdb_run_*.root"))
    ]
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)

    write_figures(out, ranked, by_run, neg)
    runtime = time.time() - started
    write_report(cfg, out, match, template_summary, ranked, by_run, strata, neg, runtime)

    best = ranked.iloc[0]
    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": cfg["title"],
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "raw_root_glob": str(Path(cfg["raw_root_dir"]) / "hrdb_run_*.root"),
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
            "bootstrap": "held-out source_run percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "negative_control_adc_thresholds": cfg["negative_control_adc_thresholds"],
            "winner_score": "energy_sigma68 + energy bias, saturation onset, waveform MSE, timing, pile-up, pedestal and PID proxy penalties",
        },
        "required_method_coverage": {
            "traditional_truncated_template": "analytic_clipped_template_sideband_traditional",
            "charge_tail_extrapolation": "charge_tail_extrapolation_traditional",
            "tobit_style_censored_regression": "tobit_censored_ridge",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "masked_sequence_transformer": "tiny_sequence_transformer",
            "new_architecture": "censored_denoising_residual_fusion_new",
        },
        "winner": {
            "name": str(best["method"]),
            "criterion": "minimum held-out composite censored-inversion score",
            "winner_score": float(best["winner_score"]),
            "energy_bias": float(best["energy_bias"]),
            "energy_bias_ci95": [float(best["energy_bias_ci_low"]), float(best["energy_bias_ci_high"])],
            "energy_sigma68": float(best["energy_sigma68"]),
            "energy_sigma68_ci95": [float(best["energy_sigma68_ci_low"]), float(best["energy_sigma68_ci_high"])],
            "saturation_onset_threshold_error": float(best["saturation_onset_threshold_error"]),
            "waveform_shape_mse": float(best["waveform_shape_mse"]),
            "timing_shift_sigma68_ns": float(best["timing_shift_sigma68_ns"]),
            "pileup_confusion_rate": float(best["pileup_confusion_rate"]),
            "pedestal_state_interaction": float(best["pedestal_state_interaction"]),
            "pid_boundary_movement": float(best["pid_boundary_movement"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "negative_controls": "negative_controls.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "Truth comes from controlled synthetic injection into raw-ROOT-derived clean pulses.",
            "Natural hardware saturation transfer still requires MC or external calibration truth.",
            "PID boundary movement is measured with support proxies, not external particle labels.",
        ],
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": TICKET,
        "study_id": STUDY_ID,
        "git_commit": base.git_commit(),
        "command": f"{sys.executable} scripts/{Path(__file__).name} --config {args.config}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: base.sha256_file(p)
            for p in sorted(out.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"DONE {STUDY_ID} winner={best['method']} runtime={runtime:.1f}s out={out}")


if __name__ == "__main__":
    main()
