#!/usr/bin/env python3
"""S28b late-tail memory and afterpulse separation benchmark."""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import s25b_1783775623_7070_7bfe60c5_pedestal_nonstationarity_audit as base


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def fit_exponential_tail(waves: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit log-positive samples 8-17 to a per-pulse exponential tail."""
    t = np.arange(waves.shape[1], dtype=np.float64)
    tail_idx = np.arange(8, waves.shape[1], dtype=int)
    pos = np.clip(waves[:, tail_idx], 1e-5, None).astype(np.float64)
    y = np.log(pos)
    x = t[tail_idx]
    xm = x.mean()
    xc = x - xm
    denom = float((xc**2).sum())
    slope = ((y - y.mean(axis=1, keepdims=True)) * xc[None, :]).sum(axis=1) / max(denom, 1e-9)
    intercept = y.mean(axis=1) - slope * xm
    fitted = np.exp(intercept[:, None] + slope[:, None] * x[None, :])
    resid = waves[:, tail_idx] - fitted
    return slope.astype(np.float32), fitted.astype(np.float32), resid.astype(np.float32)


def ar1_residual_score(waves: np.ndarray) -> np.ndarray:
    x = waves.astype(np.float64)
    prev = x[:, 7:16]
    nxt = x[:, 8:17]
    phi = (prev * nxt).sum(axis=1) / np.maximum((prev * prev).sum(axis=1), 1e-8)
    pred = phi[:, None] * x[:, 8:17]
    resid = x[:, 9:18] - pred
    return np.sqrt(np.mean(resid * resid, axis=1)).astype(np.float32)


def late_tail_labels(waves: np.ndarray, meta: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    pos = np.clip(waves, 0.0, None).astype(np.float64)
    total = np.maximum(pos.sum(axis=1), 1e-9)
    tail_10_17 = pos[:, 10:].sum(axis=1) / total
    tail_12_17 = pos[:, 12:].sum(axis=1) / total
    early_0_5 = pos[:, :6].sum(axis=1) / total
    peak = waves.argmax(axis=1)
    slope, exp_fit, exp_resid = fit_exponential_tail(waves)
    late_resid_max = exp_resid[:, 2:].max(axis=1)
    late_resid_sum = np.clip(exp_resid[:, 2:], 0.0, None).sum(axis=1)
    ar_rms = ar1_residual_score(waves)
    event_mult = meta.groupby(["run", "event_index"])["stave_idx"].transform("size").to_numpy(dtype=np.int16)
    late_tail_threshold = float(np.quantile(tail_12_17, float(config["tail_memory_quantile"])))
    afterpulse_threshold = float(np.quantile(late_resid_max, float(config["afterpulse_residual_quantile"])))
    afterpulse = (
        (event_mult >= 2)
        | (late_resid_max >= afterpulse_threshold)
        | ((peak >= int(config["late_peak_sample_min"])) & (tail_10_17 >= late_tail_threshold))
    )
    memory_like = (tail_12_17 >= late_tail_threshold) & ~afterpulse
    labels = pd.DataFrame(
        {
            "tail_10_17_over_total": tail_10_17.astype(np.float32),
            "tail_12_17_over_total": tail_12_17.astype(np.float32),
            "early_0_5_over_total": early_0_5.astype(np.float32),
            "exp_tail_log_slope": slope,
            "exp_tail_residual_max": late_resid_max.astype(np.float32),
            "exp_tail_positive_residual_sum": late_resid_sum.astype(np.float32),
            "ar1_tail_residual_rms": ar_rms,
            "event_selected_stave_multiplicity": event_mult,
            "late_tail_memory_threshold": late_tail_threshold,
            "afterpulse_residual_threshold": afterpulse_threshold,
            "late_tail_memory_like": memory_like.astype(np.int8),
            "afterpulse_or_pileup": afterpulse.astype(np.int8),
        }
    )
    diag = pd.DataFrame(
        {
            "sample": np.arange(8, waves.shape[1], dtype=int),
            "mean_exponential_fit": exp_fit.mean(axis=0),
            "mean_exponential_residual": exp_resid.mean(axis=0),
            "p90_positive_residual": np.quantile(np.clip(exp_resid, 0.0, None), 0.90, axis=0),
        }
    )
    return labels, diag


def tail_proxy_shift_cis(meta: pd.DataFrame, labels: pd.DataFrame, feats: pd.DataFrame, runs: np.ndarray, test_mask: np.ndarray, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    y = labels["afterpulse_or_pileup"].to_numpy(dtype=bool)
    centered = pd.DataFrame(
        {
            "tail_shape_parameter_exp_slope": labels["exp_tail_log_slope"].to_numpy(dtype=float),
            "tail_shape_parameter_ar_rms": labels["ar1_tail_residual_rms"].to_numpy(dtype=float),
            "timing_shift_mean_time_sample": feats["mean_time"].to_numpy(dtype=float),
            "pileup_confusion_event_multiplicity": labels["event_selected_stave_multiplicity"].to_numpy(dtype=float),
            "saturation_recovery_late_tail_fraction": labels["tail_12_17_over_total"].to_numpy(dtype=float),
            "pedestal_drift_sensitivity_adc": meta["baseline_adc"].to_numpy(dtype=float)
            - meta.groupby(["run", "stave_idx"])["baseline_adc"].transform("median").to_numpy(dtype=float),
            "energy_bias_log10_amplitude": feats["log10_amplitude"].to_numpy(dtype=float),
            "pid_confusion_duplicate_readout_adc": meta["target_odd_neg_amp"].to_numpy(dtype=float),
        }
    )
    for col in centered.columns:
        centered[col] = centered[col] - pd.Series(centered[col]).groupby([meta["run"], meta["stave_idx"]]).transform("median").to_numpy(dtype=float)
    labels_for_report = {
        "tail_shape_parameter_exp_slope": "tail-shape exponential slope",
        "tail_shape_parameter_ar_rms": "tail-shape AR residual RMS",
        "timing_shift_mean_time_sample": "timing shift",
        "pileup_confusion_event_multiplicity": "pile-up confusion",
        "saturation_recovery_late_tail_fraction": "saturation recovery",
        "pedestal_drift_sensitivity_adc": "pedestal drift sensitivity",
        "energy_bias_log10_amplitude": "energy bias proxy",
        "pid_confusion_duplicate_readout_adc": "PID confusion proxy",
    }
    idx_by_run = {int(run): np.where((runs == int(run)) & test_mask)[0] for run in np.sort(np.unique(runs[test_mask]))}
    heldout_runs = np.asarray(sorted(idx_by_run), dtype=int)
    rows = []
    for col in centered.columns:
        values = centered[col].to_numpy(dtype=float)
        heldout_idx = np.concatenate([idx_by_run[int(run)] for run in heldout_runs])
        def shift(indices: np.ndarray) -> float:
            pos = indices[y[indices]]
            neg = indices[~y[indices]]
            if len(pos) == 0 or len(neg) == 0:
                return float("nan")
            return float(np.median(values[pos]) - np.median(values[neg]))
        est = shift(heldout_idx)
        boot = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(heldout_runs, size=len(heldout_runs), replace=True)
            idx = np.concatenate([idx_by_run[int(run)] for run in sampled])
            boot.append(shift(idx))
        arr = np.asarray([v for v in boot if np.isfinite(v)], dtype=float)
        lo, hi = (np.quantile(arr, [0.025, 0.975]) if len(arr) else (float("nan"), float("nan")))
        rows.append(
            {
                "metric": col,
                "interpretation": labels_for_report[col],
                "heldout_rows": int(len(heldout_idx)),
                "heldout_positive_rows": int(y[heldout_idx].sum()),
                "afterpulse_minus_memory_median_shift": est,
                "ci_low": float(lo),
                "ci_high": float(hi),
                "bootstrap_replicates": int(n_boot),
            }
        )
    return pd.DataFrame(rows)


def perturbation_negative_controls(waves: np.ndarray, labels: pd.DataFrame, perturbation_adc: float, amplitudes: np.ndarray) -> pd.DataFrame:
    amp = np.maximum(amplitudes.astype(np.float64), 1.0)
    scaled = float(perturbation_adc) / amp
    y = labels["afterpulse_or_pileup"].to_numpy(dtype=bool)
    rows = []
    for sign in [-1.0, 1.0]:
        perturbed = waves + sign * scaled[:, None]
        perturbed = perturbed / np.maximum(perturbed.max(axis=1, keepdims=True), 1e-6)
        p_labels, _ = late_tail_labels(perturbed, pd.DataFrame({"run": 0, "event_index": np.arange(len(waves)), "stave_idx": 0}), {"tail_memory_quantile": 0.55, "afterpulse_residual_quantile": 0.78, "late_peak_sample_min": 10})
        flip = p_labels["afterpulse_or_pileup"].to_numpy(dtype=bool) != y
        dist = np.sqrt(((perturbed - waves) ** 2).mean(axis=1))
        rows.append(
            {
                "perturbation_adc": sign * float(perturbation_adc),
                "rows": int(len(waves)),
                "shape_l2_median": float(np.median(dist)),
                "shape_l2_p95": float(np.quantile(dist, 0.95)),
                "label_flip_fraction": float(flip.mean()),
                "afterpulse_flip_fraction": float(flip[y].mean()) if y.any() else float("nan"),
                "memory_flip_fraction": float(flip[~y].mean()) if (~y).any() else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def time_shuffle_negative_controls(waves: np.ndarray, meta: pd.DataFrame, labels: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Re-label deliberately unphysical time-order variants as negative controls."""
    y = labels["afterpulse_or_pileup"].to_numpy(dtype=bool)
    n_rows, n_samples = waves.shape
    perm = np.vstack([rng.permutation(n_samples) for _ in range(n_rows)])
    controls = [
        ("time_reversal", waves[:, ::-1], "reverse the waveform sample order"),
        ("circular_roll_plus3", np.roll(waves, 3, axis=1), "roll each waveform three samples later"),
        ("per_pulse_random_permutation", np.take_along_axis(waves, perm, axis=1), "shuffle sample order independently per pulse"),
    ]
    rows = []
    for name, transformed, description in controls:
        p_labels, _ = late_tail_labels(transformed, meta, config)
        p = p_labels["afterpulse_or_pileup"].to_numpy(dtype=bool)
        flip = p != y
        dist = np.sqrt(((transformed - waves) ** 2).mean(axis=1))
        rows.append(
            {
                "control": name,
                "description": description,
                "rows": int(n_rows),
                "shape_l2_median": float(np.median(dist)),
                "shape_l2_p95": float(np.quantile(dist, 0.95)),
                "original_afterpulse_fraction": float(y.mean()),
                "control_afterpulse_fraction": float(p.mean()),
                "label_flip_fraction": float(flip.mean()),
                "afterpulse_flip_fraction": float(flip[y].mean()) if y.any() else float("nan"),
                "memory_flip_fraction": float(flip[~y].mean()) if (~y).any() else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, result: dict, primary: pd.DataFrame, traditional: pd.DataFrame, per_run: pd.DataFrame) -> None:
    top_trad = traditional.head(12)
    lines = [
        "# S28b - Late-Tail Memory and Afterpulse Separation Study",
        "",
        f"- Ticket: `{result['ticket_id']}`",
        f"- Worker: `{result['worker']}`",
        f"- Raw ROOT directory: `{result['raw_root_dir']}`",
        f"- Status: DONE",
        "",
        "## Abstract",
        "",
        "This study separates smooth late-tail memory from true afterpulse/pile-up-like structure in raw B-stack waveforms. Raw ROOT files are rescanned from `HRDv`; the selected-pulse count is reproduced exactly before any modeling. The benchmark compares a physically motivated exponential-tail plus autoregressive residual score family against ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact causal sequence mixer. The winner by held-out run-block ROC AUC is **{}** with AUC **{:.4f}** [{:.4f}, {:.4f}].".format(result["winner"]["method"], result["winner"]["roc_auc"], result["winner"]["auc_ci_low"], result["winner"]["auc_ci_high"]),
        "",
        "## Raw ROOT Reproduction",
        "",
        "For each raw ROOT event, `HRDv` is reshaped to `(8,18)`. The baseline for each channel is the median of samples 0-3. B-stave even channels B2/B4/B6/B8 are selected when the baseline-subtracted amplitude exceeds 1000 ADC.",
        "",
        "| quantity | expected | reproduced | delta |",
        "|---|---:|---:|---:|",
        "| selected B-stave pulses | {:,} | {:,} | {} |".format(result["reproduction"]["expected_selected_pulses"], result["reproduction"]["selected_pulses"], result["reproduction"]["delta"]),
        "",
        "## Task Definition",
        "",
        "Let `x_i(t)` be the normalized baseline-subtracted waveform for selected pulse `i`. A smooth late-tail memory hypothesis is modeled as an exponential tail over samples 8-17:",
        "",
        "`log(max(x_i(t), eps)) = alpha_i + beta_i t + epsilon_i(t)`.",
        "",
        "An autoregressive residual proxy is computed on the late tail as",
        "",
        "`phi_i = sum_t x_i(t)x_i(t+1) / sum_t x_i(t)^2`, and `r_i(t+1)=x_i(t+1)-phi_i x_i(t)`.",
        "",
        "The weak positive class `afterpulse_or_pileup` is defined when any of the following holds: the event has more than one selected B-stave pulse, the maximum positive exponential residual in samples 10-17 exceeds the configured quantile, or a late peak occurs with high late-tail fraction. Negative examples are smooth single-pulse late-tail-memory candidates. This target is deliberately conservative: it tests separability of abrupt late structure from smooth memory, not external particle truth.",
        "",
        "| split | rows | positives | positive fraction |",
        "|---|---:|---:|---:|",
    ]
    for row in result["label_counts"]:
        lines.append("| {} | {:,} | {:,} | {:.4f} |".format(row["split"], row["rows"], row["positives"], row["positive_fraction"]))
    lines += [
        "",
        "Training and held-out partitions are by complete runs. Held-out runs are `{}`. Confidence intervals use {} bootstrap resamples of whole held-out runs.".format(", ".join(map(str, result["split"]["heldout_runs"])), result["split"]["bootstrap_replicates"]),
        "",
        "## Traditional Tail Model",
        "",
        "The traditional baseline is the best scalar or multivariate member of an interpretable scorecard: exponential-tail slope, exponential residual maximum and sum, AR(1) tail residual RMS, charge-comparison tail fractions, rise/width features, derivative zero-crossing counts, moment/FFT/Haar features, matched-template chi2, Gatti waveform score, and Fisher/Gatti engineered-feature discriminant. Scalar scores are oriented on training runs only.",
        "",
        "| rank | method | family | AUC | 95% CI | AP |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for rank, (_, row) in enumerate(top_trad.iterrows(), start=1):
        lines.append("| {} | {} | {} | {:.4f} | [{:.4f}, {:.4f}] | {:.4f} |".format(rank, row["method"], row.get("family", ""), row["roc_auc"], row["auc_ci_low"], row["auc_ci_high"], row["average_precision"]))
    lines += [
        "",
        "## ML/NN Panel",
        "",
        "Ridge, gradient-boosted trees, and MLP receive normalized waveform samples, all engineered traditional variables, exponential/AR tail variables, and stave one-hot context. The 1D-CNN receives waveform plus stave context. The new architecture is a causal compact sequence mixer: residual temporal convolutions over ordered samples, channel squeeze gating, and global average/max pooling. It is used instead of a large unconstrained transformer because the sequence length is only 18 samples.",
        "",
        "| method | role | AUC | 95% CI | AP | rows | positives |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in primary.iterrows():
        lines.append("| {} | {} | {:.4f} | [{:.4f}, {:.4f}] | {:.4f} | {:,} | {:,} |".format(row["method"], row.get("role", ""), row["roc_auc"], row["auc_ci_low"], row["auc_ci_high"], row["average_precision"], int(row["n"]), int(row["positives"])))
    lines += [
        "",
        "## Systematic Shifts",
        "",
        "The table reports afterpulse-minus-memory median shifts in held-out rows, centered by run and stave before differencing.",
        "",
        "| metric | shift | 95% CI | held-out positives |",
        "|---|---:|---:|---:|",
    ]
    for row in result["systematic_bootstrap_cis"]:
        lines.append("| {} | {:.6f} | [{:.6f}, {:.6f}] | {:,} |".format(row["interpretation"], row["afterpulse_minus_memory_median_shift"], row["ci_low"], row["ci_high"], row["heldout_positive_rows"]))
    lines += [
        "",
        "Negative-control constant pedestal perturbations before renormalization:",
        "",
        "| perturbation ADC | median L2 | p95 L2 | label flip fraction | afterpulse flip | memory flip |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["perturbation_negative_controls"]:
        lines.append("| {:.1f} | {:.6f} | {:.6f} | {:.4f} | {:.4f} | {:.4f} |".format(row["perturbation_adc"], row["shape_l2_median"], row["shape_l2_p95"], row["label_flip_fraction"], row["afterpulse_flip_fraction"], row["memory_flip_fraction"]))
    lines += [
        "",
        "Negative-control time shuffles intentionally destroy the physical late-sample ordering before reapplying the same weak-label construction:",
        "",
        "| control | median L2 | p95 L2 | original positive fraction | control positive fraction | label flip fraction |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in result["time_shuffle_negative_controls"]:
        lines.append("| {} | {:.6f} | {:.6f} | {:.4f} | {:.4f} | {:.4f} |".format(row["control"], row["shape_l2_median"], row["shape_l2_p95"], row["original_afterpulse_fraction"], row["control_afterpulse_fraction"], row["label_flip_fraction"]))
    lines += [
        "",
        "## Per-Run Stability",
        "",
        "| method | mean per-run AUC | min | max | finite runs |",
        "|---|---:|---:|---:|---:|",
    ]
    for method, group in per_run[per_run["method"].isin(result["primary_methods"])].groupby("method", sort=True):
        finite = group["roc_auc"].dropna()
        lines.append("| {} | {:.4f} | {:.4f} | {:.4f} | {} |".format(method, float(finite.mean()), float(finite.min()), float(finite.max()), int(len(finite))))
    lines += [
        "",
        "## Caveats",
        "",
        "- The afterpulse/pile-up label is weak and derived from waveform morphology plus same-event multiplicity, not an external particle-truth label.",
        "- Run-heldout splits prevent random-row leakage but cannot remove all acquisition-era correlations.",
        "- Duplicate-readout amplitude is used only as a diagnostic PID proxy in systematic tables, not as a training label.",
        "- The causal sequence mixer is intentionally compact; a full attention transformer would be poorly constrained for 18 samples without stronger labels.",
        "",
        "## Verdict",
        "",
        "`result.json` names **{}** as winner. The best traditional method is **{}**. The conclusion is therefore: {}.".format(result["winner"]["method"], result["best_traditional"]["method"], result["verdict"]),
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s28b_1783797017_25295_3bed5b6b_late_tail_afterpulse.py --config configs/s28b_1783797017_25295_3bed5b6b_late_tail_afterpulse.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s28b_1783797017_25295_3bed5b6b_late_tail_afterpulse.json")
    args = parser.parse_args()
    t0 = time.time()
    config = base.load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_dir = base.resolve_raw_root_dir(config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, meta, counts_by_run = base.scan_raw(config, raw_dir)
    selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError(f"raw reproduction failed: selected {selected}, expected {expected}")
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame([{"quantity": "selected B-stave pulses", "report_value": expected, "reproduced": selected, "delta": selected - expected, "pass": selected == expected}]).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    sample_idx = base.balanced_sample(meta, int(config["max_per_run_stave"]), rng)
    sample_idx.sort()
    bench_waves = waves[sample_idx]
    bench_meta = meta.iloc[sample_idx].reset_index(drop=True)
    runs = bench_meta["run"].to_numpy(dtype=int)
    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    train_mask = ~np.isin(runs, heldout_runs)
    test_mask = np.isin(runs, heldout_runs)

    feats, feature_roles = base.classic_features(bench_waves, bench_meta)
    labels, exp_diag = late_tail_labels(bench_waves, bench_meta, config)
    for col in ["tail_10_17_over_total", "tail_12_17_over_total", "exp_tail_log_slope", "exp_tail_residual_max", "exp_tail_positive_residual_sum", "ar1_tail_residual_rms", "event_selected_stave_multiplicity"]:
        feats[col] = labels[col].to_numpy(dtype=np.float32)
    extra_roles = pd.DataFrame(
        [{"feature": col, "family": "exponential_tail_ar_residual"} for col in ["exp_tail_log_slope", "exp_tail_residual_max", "exp_tail_positive_residual_sum", "ar1_tail_residual_rms"]]
        + [{"feature": "event_selected_stave_multiplicity", "family": "pileup_event_context"}]
    )
    feature_roles = pd.concat([feature_roles, extra_roles], ignore_index=True)
    y = labels["afterpulse_or_pileup"].to_numpy(dtype=int)

    exp_diag.to_csv(out_dir / "exponential_tail_diagnostics.csv", index=False)
    sample_table = pd.concat([bench_meta[["run", "group", "event_index", "eventno", "stave", "stave_idx", "amplitude_adc", "target_odd_neg_amp", "peak_sample"]], labels], axis=1)
    sample_table.to_csv(out_dir / "late_tail_afterpulse_labels.csv", index=False)
    feature_roles.to_csv(out_dir / "traditional_feature_families.csv", index=False)

    split_rows = []
    for name, mask in [("train", train_mask), ("heldout", test_mask), ("all", np.ones(len(y), dtype=bool))]:
        split_rows.append({"split": name, "rows": int(mask.sum()), "positives": int(y[mask].sum()), "positive_fraction": float(y[mask].mean())})
    pd.DataFrame(split_rows).to_csv(out_dir / "label_counts.csv", index=False)

    syst = tail_proxy_shift_cis(bench_meta, labels, feats, runs, test_mask, rng, int(config["bootstrap_replicates"]))
    syst.to_csv(out_dir / "systematic_bootstrap_cis.csv", index=False)
    neg = perturbation_negative_controls(bench_waves, labels, float(config["perturbation_adc"]), bench_meta["amplitude_adc"].to_numpy(dtype=float))
    neg.to_csv(out_dir / "tail_perturbation_negative_controls.csv", index=False)
    time_neg = time_shuffle_negative_controls(bench_waves, bench_meta, labels, config, rng)
    time_neg.to_csv(out_dir / "time_shuffle_negative_controls.csv", index=False)

    predictions = []
    feature_family = dict(zip(feature_roles["feature"], feature_roles["family"]))
    template = base.template_scores(bench_waves, train_mask, y[train_mask])
    for name, score in template.items():
        feats[name] = score
        feature_family[name] = "matched_filter_template_chi2"
    for col in feats.columns:
        if col in {"stave_idx", "log10_amplitude"}:
            continue
        score, direction, train_auc = base.orient_score(y[train_mask], feats.loc[train_mask, col].to_numpy(dtype=float), feats[col].to_numpy(dtype=float))
        predictions.append(pd.DataFrame({"method": "traditional_scalar__" + col, "run": runs[test_mask].astype(int), "row_index": np.where(test_mask)[0].astype(np.int64), "y_true": y[test_mask].astype(int), "score": score[test_mask], "role": "traditional_scalar", "family": feature_family.get(col, "traditional_scalar"), "train_orientation": int(direction), "train_auc_oriented": train_auc}))
    wave_gatti = base.gatti_score(bench_waves[train_mask], y[train_mask], bench_waves)
    wave_gatti, _, _ = base.orient_score(y[train_mask], wave_gatti[train_mask], wave_gatti)
    predictions.append(pd.DataFrame({"method": "traditional_exponential_ar_gatti_waveform", "run": runs[test_mask].astype(int), "row_index": np.where(test_mask)[0].astype(np.int64), "y_true": y[test_mask].astype(int), "score": wave_gatti[test_mask], "role": "traditional_multivariate", "family": "exponential_tail_ar_gatti"}))
    trad_cols = [c for c in feats.columns if c != "stave_idx"]
    trad_x = feats[trad_cols].to_numpy(dtype=np.float32)
    fisher = base.make_pipeline(base.StandardScaler(), base.LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"))
    fisher.fit(trad_x[train_mask], y[train_mask])
    predictions.append(pd.DataFrame({"method": "traditional_exponential_ar_fisher_all_features", "run": runs[test_mask].astype(int), "row_index": np.where(test_mask)[0].astype(np.int64), "y_true": y[test_mask].astype(int), "score": fisher.decision_function(trad_x[test_mask]), "role": "traditional_multivariate", "family": "exponential_tail_ar_fisher"}))

    x_supervised = base.make_supervised_matrix(bench_waves, feats, bench_meta)
    predictions.extend(base.fit_sklearn_methods(x_supervised, y, runs, train_mask, test_mask))
    predictions.extend(base.fit_torch_methods(bench_waves, bench_meta, y, runs, train_mask, test_mask, config))

    pred = pd.concat(predictions, ignore_index=True)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    summary, per_run = base.summarize_predictions(pred, rng, int(config["bootstrap_replicates"]))
    role_family = pred.groupby("method", sort=False)[["role", "family"]].first().reset_index()
    summary = summary.merge(role_family, on="method", how="left")
    summary.to_csv(out_dir / "method_summary_all.csv", index=False)
    per_run.to_csv(out_dir / "run_heldout_metrics.csv", index=False)
    traditional = summary[summary["role"].str.startswith("traditional", na=False)].sort_values("roc_auc", ascending=False).copy()
    traditional.to_csv(out_dir / "traditional_method_summary.csv", index=False)
    primary_methods = [str(traditional.iloc[0]["method"]), "ML_ridge_classifier", "ML_gradient_boosted_trees", "ML_mlp", "NN_1d_cnn", "NN_transformer_sequence_encoder_new"]
    primary = summary[summary["method"].isin(primary_methods)].sort_values("roc_auc", ascending=False).copy()
    primary.to_csv(out_dir / "primary_method_summary.csv", index=False)
    base.plot_auc(out_dir, summary, primary_methods)

    winner = primary.iloc[0].to_dict()
    best_traditional = traditional.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit": base.git_commit(),
        "runtime_sec": time.time() - t0,
        "python": platform.python_version(),
        "reproduction": {"selected_pulses": selected, "expected_selected_pulses": expected, "delta": selected - expected, "passed": selected == expected},
        "split": {"heldout_runs": [int(r) for r in heldout_runs], "train_rows": int(train_mask.sum()), "heldout_rows": int(test_mask.sum()), "bootstrap_replicates": int(config["bootstrap_replicates"])},
        "label": {"name": "afterpulse_or_pileup", "late_tail_memory_threshold": float(labels["late_tail_memory_threshold"].iloc[0]), "afterpulse_residual_threshold": float(labels["afterpulse_residual_threshold"].iloc[0])},
        "label_counts": split_rows,
        "systematic_bootstrap_cis": syst.to_dict(orient="records"),
        "perturbation_negative_controls": neg.to_dict(orient="records"),
        "time_shuffle_negative_controls": time_neg.to_dict(orient="records"),
        "best_traditional": best_traditional,
        "winner": winner,
        "primary_methods": primary_methods,
        "verdict": ("ML/NN model beats the strongest traditional exponential-tail/AR baseline by held-out AUC" if winner["method"] != best_traditional["method"] else "strong traditional exponential-tail/AR baseline wins the held-out benchmark"),
        "ticket_cli_append_audit": {
            "intentional_testbeam_follow_up_appended": bool(config.get("appended_follow_up_ticket_id")),
            "accidental_default_project_append_id": "1783807740.5591.289d7cf0",
            "accidental_default_project": "grocery",
            "note": str(config.get("ticket_cli_append_note", "")),
        },
        "next_tickets": [
            {
                "appended_ticket_id": config.get("appended_follow_up_ticket_id"),
                "title": "Validate S28b afterpulse labels against random-trigger no-pulse windows",
                "body": "Build an external negative-control label set from random-trigger/no-pulse windows and rerun the S28b late-tail afterpulse separator with identical run-block bootstrap CIs.",
            }
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, primary, traditional, per_run)
    base.write_manifest(out_dir, config)
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": winner["method"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
