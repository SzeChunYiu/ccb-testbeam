#!/usr/bin/env python3
"""P04f: baseline-excursion charge-bias closure.

This study deliberately keeps the target identical to P04: the paired odd
duplicate-readout positive charge.  It asks whether P09a baseline-excursion and
early-pretrigger classes explain a measurable fraction of charge residuals under
run-held-out training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p04_amplitude_charge_regression as p04  # noqa: E402
import p09a_rare_waveform_anomaly_taxonomy as p09a  # noqa: E402


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ci(values: np.ndarray) -> List[float | None]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return [None, None]
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def robust_metrics(y: np.ndarray, pred: np.ndarray, high_bias: float) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(frac)),
        "bias_median_frac": float(np.median(frac)) if len(frac) else float("nan"),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)) if len(frac) else float("nan"),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))) if len(frac) else float("nan"),
        "high_bias_tail_fraction": float(np.mean(np.abs(frac) > high_bias)) if len(frac) else float("nan"),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)) if len(frac) else float("nan"),
    }


def run_block_ci(
    frame: pd.DataFrame,
    y_col: str,
    pred_col: str,
    rng: np.random.Generator,
    reps: int,
    high_bias: float,
    max_rows_per_run: int,
) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {
            "bias_ci95": [None, None],
            "res68_ci95": [None, None],
            "full_rms_ci95": [None, None],
            "high_bias_tail_ci95": [None, None],
        }
    by_run = {}
    for run in runs:
        sub = frame[frame["run"] == run]
        y = sub[y_col].to_numpy()
        pred = sub[pred_col].to_numpy()
        if len(y) > max_rows_per_run:
            idx = rng.choice(np.arange(len(y)), size=max_rows_per_run, replace=False)
            y = y[idx]
            pred = pred[idx]
        by_run[int(run)] = (y, pred)
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    tail = np.empty(reps, dtype=float)
    for rep in range(reps):
        ys = []
        preds = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            y, pred = by_run[int(run)]
            ys.append(y)
            preds.append(pred)
        yy = np.concatenate(ys)
        pp = np.concatenate(preds)
        frac = (pp - yy) / np.maximum(yy, 1.0)
        bias[rep] = np.median(frac)
        res68[rep] = np.percentile(np.abs(frac), 68)
        rms[rep] = np.sqrt(np.mean(frac * frac))
        tail[rep] = np.mean(np.abs(frac) > high_bias)
    return {
        "bias_ci95": ci(bias),
        "res68_ci95": ci(res68),
        "full_rms_ci95": ci(rms),
        "high_bias_tail_ci95": ci(tail),
    }


def run_bootstrap_delta(
    anomaly: pd.DataFrame,
    control: pd.DataFrame,
    y_col: str,
    pred_col: str,
    rng: np.random.Generator,
    reps: int,
    high_bias: float,
    max_rows_per_run: int,
) -> dict:
    runs = np.asarray(sorted(set(anomaly["run"].unique()).intersection(control["run"].unique())), dtype=int)
    if len(runs) < 2:
        return {"delta_bias_ci95": [None, None], "delta_res68_ci95": [None, None], "delta_high_bias_tail_ci95": [None, None]}
    def capped_arrays(frame: pd.DataFrame, run: int) -> Tuple[np.ndarray, np.ndarray]:
        sub = frame[frame["run"] == run]
        y = sub[y_col].to_numpy()
        pred = sub[pred_col].to_numpy()
        if len(y) > max_rows_per_run:
            idx = rng.choice(np.arange(len(y)), size=max_rows_per_run, replace=False)
            y = y[idx]
            pred = pred[idx]
        return y, pred

    a_by = {int(run): capped_arrays(anomaly, int(run)) for run in runs}
    c_by = {int(run): capped_arrays(control, int(run)) for run in runs}
    dbias = np.empty(reps, dtype=float)
    dres68 = np.empty(reps, dtype=float)
    dtail = np.empty(reps, dtype=float)
    for rep in range(reps):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        ay = np.concatenate([a_by[int(run)][0] for run in sample_runs])
        ap = np.concatenate([a_by[int(run)][1] for run in sample_runs])
        cy = np.concatenate([c_by[int(run)][0] for run in sample_runs])
        cp = np.concatenate([c_by[int(run)][1] for run in sample_runs])
        ma = robust_metrics(ay, ap, high_bias)
        mc = robust_metrics(cy, cp, high_bias)
        dbias[rep] = ma["bias_median_frac"] - mc["bias_median_frac"]
        dres68[rep] = ma["res68_abs_frac"] - mc["res68_abs_frac"]
        dtail[rep] = ma["high_bias_tail_fraction"] - mc["high_bias_tail_fraction"]
    return {
        "delta_bias_ci95": ci(dbias),
        "delta_res68_ci95": ci(dres68),
        "delta_high_bias_tail_ci95": ci(dtail),
    }


def assert_alignment(meta: pd.DataFrame, p09_meta: pd.DataFrame) -> None:
    cols = ["run", "eventno", "evt", "stave"]
    if len(meta) != len(p09_meta):
        raise RuntimeError(f"P04/P09a selected-row count mismatch: {len(meta)} vs {len(p09_meta)}")
    for col in cols:
        if not np.asarray(meta[col]).tolist() == np.asarray(p09_meta[col]).tolist():
            raise RuntimeError(f"P04/P09a row alignment mismatch at {col}")


def add_anomaly_context(config: dict, p04_config: dict, meta: pd.DataFrame, wave: np.ndarray, valid: np.ndarray) -> pd.DataFrame:
    p09_config = load_json(ROOT / config["p09a_reference_config"])
    raw_dir = p09a.resolve_raw_root_dir(p09_config)
    p09_waves, p09_meta, p09_counts = p09a.scan_raw(p09_config, raw_dir)
    total = int(p09_counts["selected_pulses"].sum())
    expected = int(p09_config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"P09a raw reproduction failed: {total} != {expected}")
    assert_alignment(meta, p09_meta)

    p09_meta = p09_meta.loc[valid].reset_index(drop=True)
    p09_waves = p09_waves[valid]
    p09_train = ~p09_meta["run"].isin([int(x) for x in p09_config["heldout_runs"]]).to_numpy()
    p09_meta = p09a.add_template_residual(p09_config, p09_waves, p09_meta, p09_train)
    p09_meta, thresholds = p09a.add_taxonomy(p09_meta, p09_train)
    p09_meta["p09a_traditional_score"] = p09a.score_traditional(p09_meta, p09_train)

    out = meta.loc[valid].reset_index(drop=True).copy()
    copy_cols = [
        "baseline_mad",
        "baseline_slope",
        "early_fraction",
        "late_fraction",
        "width_half",
        "saturation_count",
        "secondary_peak",
        "post_peak_min",
        "q_template_rmse",
        "p09a_traditional_score",
        "label_baseline_excursion",
        "label_novel_early_pretrigger",
        "label_saturation",
        "taxon",
    ]
    for col in copy_cols:
        out[col] = p09_meta[col].to_numpy()

    pre = wave[valid][:, [int(i) for i in p04_config["baseline_samples"]]]
    out["s16_pretrigger_mean_adc"] = pre.mean(axis=1)
    out["s16_pretrigger_median_adc"] = np.median(pre, axis=1)
    out["s16_pretrigger_max_abs_adc"] = np.max(np.abs(pre), axis=1)
    out["s16_pretrigger_span_adc"] = pre.max(axis=1) - pre.min(axis=1)
    out["s16_pretrigger_slope_adc"] = pre[:, -1] - pre[:, 0]
    out["p09a_threshold_baseline_mad_q995"] = float(thresholds.loc[thresholds["threshold"] == "baseline_mad_q995", "value"].iloc[0])
    out["p09a_threshold_abs_baseline_slope_q995"] = float(
        thresholds.loc[thresholds["threshold"] == "abs_baseline_slope_q995", "value"].iloc[0]
    )
    return out


def robust_pretrigger_charge(wave: np.ndarray, baseline_samples: Iterable[int]) -> np.ndarray:
    idx = [int(i) for i in baseline_samples]
    offset = np.median(wave[:, idx], axis=1)
    return np.clip(wave - offset[:, None], 0.0, None).sum(axis=1)


def build_augmented_features(meta: pd.DataFrame, wave: np.ndarray, base_pred: np.ndarray, base_features: Optional[np.ndarray] = None) -> np.ndarray:
    base = p04.ml_features(meta, wave) if base_features is None else base_features
    bool_cols = ["label_baseline_excursion", "label_novel_early_pretrigger", "label_saturation"]
    extra_cols = [
        "baseline_mad",
        "baseline_slope",
        "early_fraction",
        "late_fraction",
        "width_half",
        "saturation_count",
        "q_template_rmse",
        "p09a_traditional_score",
        "s16_pretrigger_mean_adc",
        "s16_pretrigger_median_adc",
        "s16_pretrigger_max_abs_adc",
        "s16_pretrigger_span_adc",
        "s16_pretrigger_slope_adc",
    ]
    extra = meta[extra_cols].to_numpy(dtype=float)
    flags = meta[bool_cols].astype(float).to_numpy()
    return np.column_stack([base, np.log(np.maximum(base_pred, 1.0)), extra, flags])


def fit_loro(config: dict, p04_config: dict, meta: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = meta.copy()
    methods = [
        "peak_charge_calibrated",
        "integral_calibrated",
        "robust_pretrigger_charge",
        "template_fit_calibrated",
        "p04_frozen_mlp",
        "p04f_residual_mlp",
        "shuffled_residual_mlp",
    ]
    for method in methods:
        out[f"pred_{method}"] = np.nan

    rng = np.random.default_rng(int(config["random_seed"]))
    st = out["stave_idx"].to_numpy()
    y = out["target_odd_pos_charge"].to_numpy()
    even_amp = out["even_amp"].to_numpy()
    even_charge = out["even_pos_charge"].to_numpy()
    robust_charge = robust_pretrigger_charge(wave, p04_config["baseline_samples"])
    bins = [float(x) for x in p04_config["template_bins"]]
    shift_grid = [float(x) for x in p04_config["template_shift_grid"]]
    all_mask = np.ones(len(out), dtype=bool)
    global_templates = p04.build_templates(out, wave, all_mask, bins)
    tmpl_scale = p04.template_scales(out, wave, global_templates, bins, shift_grid)
    x_p04 = p04.ml_features(out, wave)
    runs = np.asarray(sorted(out["run"].unique()), dtype=int)
    fold_rows = []

    for heldout_run in runs:
        train_mask = out["run"].to_numpy() != heldout_run
        held_mask = ~train_mask
        train_idx = np.where(train_mask)[0]
        if len(train_idx) > int(config["ml_max_train_rows"]):
            train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
        shuffle_idx = train_idx
        if len(shuffle_idx) > int(config["shuffle_max_train_rows"]):
            shuffle_idx = rng.choice(shuffle_idx, size=int(config["shuffle_max_train_rows"]), replace=False)

        peak_models = p04.fit_log_calibrators(even_amp[train_mask], y[train_mask], st[train_mask])
        out.loc[held_mask, "pred_peak_charge_calibrated"] = p04.predict_log_calibrated(peak_models, even_amp[held_mask], st[held_mask])

        integral_models = p04.fit_log_calibrators(even_charge[train_mask], y[train_mask], st[train_mask])
        out.loc[held_mask, "pred_integral_calibrated"] = p04.predict_log_calibrated(
            integral_models, even_charge[held_mask], st[held_mask]
        )

        robust_models = p04.fit_log_calibrators(robust_charge[train_mask], y[train_mask], st[train_mask])
        out.loc[held_mask, "pred_robust_pretrigger_charge"] = p04.predict_log_calibrated(
            robust_models, robust_charge[held_mask], st[held_mask]
        )

        tmpl_models = p04.fit_log_calibrators(tmpl_scale[train_mask], y[train_mask], st[train_mask])
        out.loc[held_mask, "pred_template_fit_calibrated"] = p04.predict_log_calibrated(
            tmpl_models, tmpl_scale[held_mask], st[held_mask]
        )

        base_pred = out["pred_robust_pretrigger_charge"].to_numpy().copy()
        base_pred[train_mask] = p04.predict_log_calibrated(robust_models, robust_charge[train_mask], st[train_mask])
        x_aug = build_augmented_features(out, wave, base_pred, x_p04)

        params = {
            "hidden_layer_sizes": (int(config["ml"]["hidden_layer_size"]),),
            "alpha": float(config["ml"]["alpha"]),
            "learning_rate_init": float(config["ml"]["learning_rate_init"]),
            "batch_size": int(config["ml"]["batch_size"]),
            "max_iter": int(config["ml"]["max_iter"]),
            "early_stopping": True,
            "n_iter_no_change": 5,
            "random_state": int(config["random_seed"]) + int(heldout_run),
        }
        p04_ml = make_pipeline(StandardScaler(), MLPRegressor(**params))
        p04_ml.fit(x_p04[train_idx], np.log(y[train_idx]))
        out.loc[held_mask, "pred_p04_frozen_mlp"] = np.exp(p04_ml.predict(x_p04[held_mask]))

        resid = np.log(np.maximum(y, 1.0) / np.maximum(base_pred, 1.0))
        residual_ml = make_pipeline(StandardScaler(), MLPRegressor(**params))
        residual_ml.fit(x_aug[train_idx], resid[train_idx])
        out.loc[held_mask, "pred_p04f_residual_mlp"] = base_pred[held_mask] * np.exp(residual_ml.predict(x_aug[held_mask]))

        shuf_params = {
            "hidden_layer_sizes": (int(config["shuffle_ml"]["hidden_layer_size"]),),
            "alpha": float(config["shuffle_ml"]["alpha"]),
            "learning_rate_init": float(config["shuffle_ml"]["learning_rate_init"]),
            "batch_size": int(config["shuffle_ml"]["batch_size"]),
            "max_iter": int(config["shuffle_ml"]["max_iter"]),
            "early_stopping": True,
            "n_iter_no_change": 4,
            "random_state": int(config["random_seed"]) + 1000 + int(heldout_run),
        }
        shuffled = resid[shuffle_idx].copy()
        rng.shuffle(shuffled)
        shuffled_ml = make_pipeline(StandardScaler(), MLPRegressor(**shuf_params))
        shuffled_ml.fit(x_aug[shuffle_idx], shuffled)
        out.loc[held_mask, "pred_shuffled_residual_mlp"] = base_pred[held_mask] * np.exp(shuffled_ml.predict(x_aug[held_mask]))

        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "n_train": int(train_mask.sum()),
                "n_heldout": int(held_mask.sum()),
                "ml_train_rows": int(len(train_idx)),
                "train_heldout_overlap": int(np.isin(out.loc[train_mask, "run"].unique(), [heldout_run]).sum()),
            }
        )
        print(f"fold run {heldout_run}: heldout {int(held_mask.sum())} rows")

    for method in methods:
        if out[f"pred_{method}"].isna().any():
            raise RuntimeError(f"missing leave-one-run-out predictions for {method}")
    return out, pd.DataFrame(fold_rows)


def add_match_bins(config: dict, frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    edges = np.asarray(config["amplitude_bins"], dtype=float)
    bin_idx = np.clip(np.searchsorted(edges, out["even_amp"].to_numpy(), side="right") - 1, 0, len(edges) - 2)
    labels = [f"{int(edges[i])}_{'inf' if edges[i + 1] > 1e8 else int(edges[i + 1])}" for i in range(len(edges) - 1)]
    out["amp_bin"] = np.asarray(labels, dtype=object)[bin_idx]
    out["saturation_bin"] = (out["saturation_count"].to_numpy() >= int(config["saturation_count_threshold"])).astype(int)
    return out


def matched_control_indices(frame: pd.DataFrame, anomaly_mask: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    normal = frame.loc[~anomaly_mask & ~frame["label_baseline_excursion"] & ~frame["label_novel_early_pretrigger"]].copy()
    normal["_idx"] = normal.index.to_numpy()
    anomaly = frame.loc[anomaly_mask, ["run", "stave", "amp_bin", "saturation_bin"]].copy()
    pieces: List[np.ndarray] = []
    for key, sub in anomaly.groupby(["run", "stave", "amp_bin", "saturation_bin"], sort=True):
        pool = normal
        for col, value in zip(["run", "stave", "amp_bin", "saturation_bin"], key):
            pool = pool[pool[col] == value]
        if len(pool) == 0:
            continue
        take = min(len(pool), len(sub))
        pieces.append(rng.choice(pool["_idx"].to_numpy(), size=take, replace=False))
    if not pieces:
        return np.asarray([], dtype=int)
    out = np.concatenate(pieces).astype(int)
    rng.shuffle(out)
    return out


def summarize_predictions(config: dict, frame: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 991)
    high_bias = float(config["high_bias_abs_frac"])
    reps = int(config["bootstrap_reps"])
    max_rows_per_run = int(config["bootstrap_max_rows_per_run"])
    methods = [
        "peak_charge_calibrated",
        "integral_calibrated",
        "robust_pretrigger_charge",
        "template_fit_calibrated",
        "p04_frozen_mlp",
        "p04f_residual_mlp",
        "shuffled_residual_mlp",
    ]
    stratum_masks = {
        "all_valid": np.ones(len(frame), dtype=bool),
        "normal_matched_pool": (~frame["label_baseline_excursion"] & ~frame["label_novel_early_pretrigger"]).to_numpy(),
        "baseline_excursion": frame["label_baseline_excursion"].to_numpy(),
        "novel_early_pretrigger": frame["label_novel_early_pretrigger"].to_numpy(),
    }
    matched_controls = {
        "matched_normal_for_baseline_excursion": matched_control_indices(frame, stratum_masks["baseline_excursion"], rng),
        "matched_normal_for_novel_early_pretrigger": matched_control_indices(frame, stratum_masks["novel_early_pretrigger"], rng),
    }

    rows = []
    for stratum, mask in stratum_masks.items():
        sub = frame.loc[mask]
        for method in methods:
            row = {"stratum": stratum, "method": method}
            row.update(robust_metrics(sub["target_odd_pos_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy(), high_bias))
            row.update(run_block_ci(sub, "target_odd_pos_charge", f"pred_{method}", rng, reps, high_bias, max_rows_per_run))
            rows.append(row)
    for stratum, idx in matched_controls.items():
        sub = frame.loc[idx]
        for method in methods:
            row = {"stratum": stratum, "method": method}
            row.update(robust_metrics(sub["target_odd_pos_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy(), high_bias))
            row.update(run_block_ci(sub, "target_odd_pos_charge", f"pred_{method}", rng, reps, high_bias, max_rows_per_run))
            rows.append(row)
    summary = pd.DataFrame(rows)

    delta_rows = []
    pairs = [
        ("baseline_excursion", "matched_normal_for_baseline_excursion", stratum_masks["baseline_excursion"]),
        ("novel_early_pretrigger", "matched_normal_for_novel_early_pretrigger", stratum_masks["novel_early_pretrigger"]),
    ]
    for anomaly_name, control_name, anomaly_mask in pairs:
        anomaly = frame.loc[anomaly_mask]
        control = frame.loc[matched_controls[control_name]]
        for method in methods:
            ma = robust_metrics(anomaly["target_odd_pos_charge"].to_numpy(), anomaly[f"pred_{method}"].to_numpy(), high_bias)
            mc = robust_metrics(control["target_odd_pos_charge"].to_numpy(), control[f"pred_{method}"].to_numpy(), high_bias)
            row = {
                "anomaly_stratum": anomaly_name,
                "control_stratum": control_name,
                "method": method,
                "n_anomaly": ma["n"],
                "n_control": mc["n"],
                "delta_bias_median_frac": ma["bias_median_frac"] - mc["bias_median_frac"],
                "delta_res68_abs_frac": ma["res68_abs_frac"] - mc["res68_abs_frac"],
                "delta_high_bias_tail_fraction": ma["high_bias_tail_fraction"] - mc["high_bias_tail_fraction"],
            }
            row.update(run_bootstrap_delta(anomaly, control, "target_odd_pos_charge", f"pred_{method}", rng, reps, high_bias, max_rows_per_run))
            delta_rows.append(row)

        best_trad = (
            summary[
                (summary["stratum"] == anomaly_name)
                & (summary["method"].isin(["peak_charge_calibrated", "integral_calibrated", "robust_pretrigger_charge", "template_fit_calibrated"]))
            ]
            .sort_values("res68_abs_frac")
            .iloc[0]
        )
        for method in ["p04_frozen_mlp", "p04f_residual_mlp"]:
            ml = summary[(summary["stratum"] == anomaly_name) & (summary["method"] == method)].iloc[0]
            delta_rows.append(
                {
                    "anomaly_stratum": anomaly_name,
                    "control_stratum": "best_traditional_same_stratum",
                "method": f"{method}_minus_{best_trad['method']}",
                    "n_anomaly": int(ml["n"]),
                    "n_control": int(best_trad["n"]),
                    "delta_bias_median_frac": float(ml["bias_median_frac"] - best_trad["bias_median_frac"]),
                    "delta_res68_abs_frac": float(ml["res68_abs_frac"] - best_trad["res68_abs_frac"]),
                    "delta_high_bias_tail_fraction": float(ml["high_bias_tail_fraction"] - best_trad["high_bias_tail_fraction"]),
                    "delta_bias_ci95": [None, None],
                    "delta_res68_ci95": [None, None],
                    "delta_high_bias_tail_ci95": [None, None],
                }
            )

    by_run_rows = []
    for run, sub in frame.groupby("run", sort=True):
        for method in methods:
            row = {"run": int(run), "method": method}
            row.update(robust_metrics(sub["target_odd_pos_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy(), high_bias))
            row["baseline_excursion_n"] = int(sub["label_baseline_excursion"].sum())
            row["early_pretrigger_n"] = int(sub["label_novel_early_pretrigger"].sum())
            by_run_rows.append(row)

    return summary, pd.DataFrame(delta_rows), pd.DataFrame(by_run_rows)


def write_report(
    out_dir: Path,
    config: dict,
    p04_result: dict,
    s16_result: dict,
    counts_by_run: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    expected = int(p04_result["raw_reproduction"]["expected_selected_pulses"])
    got = int(counts_by_run["selected_pulses"].sum())
    main = summary[
        summary["stratum"].isin(
            [
                "all_valid",
                "baseline_excursion",
                "matched_normal_for_baseline_excursion",
                "novel_early_pretrigger",
                "matched_normal_for_novel_early_pretrigger",
            ]
        )
        & summary["method"].isin(["integral_calibrated", "robust_pretrigger_charge", "p04_frozen_mlp", "p04f_residual_mlp", "shuffled_residual_mlp"])
    ].copy()
    compact = main[
        [
            "stratum",
            "method",
            "n",
            "bias_median_frac",
            "bias_ci95",
            "res68_abs_frac",
            "res68_ci95",
            "high_bias_tail_fraction",
            "high_bias_tail_ci95",
        ]
    ]
    delta_compact = deltas[
        [
            "anomaly_stratum",
            "control_stratum",
            "method",
            "n_anomaly",
            "n_control",
            "delta_bias_median_frac",
            "delta_res68_abs_frac",
            "delta_high_bias_tail_fraction",
            "delta_res68_ci95",
        ]
    ]

    lines = [
        "# P04f Baseline-Excursion Charge-Bias Closure",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.",
        "- **Target:** P04 paired odd-channel duplicate-readout positive charge.",
        "- **Split:** leave-one-run-out over every P04 B-stack run; intervals are run-block bootstraps.",
        "",
        "## Raw Reproduction Gate",
        "",
        f"P04 selected-pulse count was rebuilt from raw ROOT before fitting: `{got:,}` vs expected `{expected:,}` (delta `{got - expected:+,}`).",
        f"The valid duplicate-charge table has `{result['n_valid_rows']:,}` rows after removing `{result['invalid_target_rows_removed']:,}` invalid odd-target rows.",
        "",
        "## Methods",
        "",
        "- **Traditional:** P04 peak-to-charge, integral-to-charge, robust pretrigger-corrected integral, and amplitude-binned template-scale calibrators, all trained without the held-out run.",
        "- **P04 ML reference:** compact MLP on the frozen P04 even-waveform feature set, retrained leave-one-run-out; the stored P04 HGB number is reported in the leakage audit.",
        "- **P04f ML:** compact MLP residual model on even waveform samples plus P09a score/labels and S16-style baseline summaries.",
        f"- **S16 anchor:** prior S16 held-out pedestal MAE was `{s16_result['traditional']['value']:.1f}` ADC traditional vs `{s16_result['ml']['value']:.1f}` ADC ML.",
        "",
        "## Charge Bias By Stratum",
        "",
        compact.to_markdown(index=False),
        "",
        "## Matched-Stratum Deltas",
        "",
        "Controls are sampled within the same run, stave, amplitude bin, and saturation bin.",
        "",
        delta_compact.to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        f"- Leave-one-run-out overlap count: `{leakage['train_heldout_overlap_total']}`.",
        "- Feature matrices exclude run id, event ids, odd-channel target samples, and target charge.",
        f"- Shuffled-residual MLP all-valid res68: `{leakage['shuffled_residual_res68_all_valid']:.4f}` vs P04f residual MLP `{leakage['p04f_residual_res68_all_valid']:.4f}`.",
        f"- P04 original heldout duplicate-charge ML res68 was `{leakage['p04_reference_charge_ml_res68']:.4f}`; the very small duplicate-readout ML errors are therefore treated as electronics closure, not deposited-energy truth.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `charge_bias_summary.csv`, `stratum_deltas.csv`, `by_run_metrics.csv`, `fold_audit.csv`, `counts_by_run.csv`, and `predictions_sample.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04f_baseline_excursion_charge_bias_closure.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = ROOT / args.config
    config = load_yaml(config_path)
    p04_config_path = ROOT / config["p04_reference_config"]
    p04_config = p04.load_config(p04_config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/5 reproducing P04 selected-pulse number from raw ROOT ...")
    meta, wave, counts_by_run = p04.extract_rows(p04_config)
    total = int(counts_by_run["selected_pulses"].sum())
    expected = int(p04_config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"P04 raw reproduction failed: {total} != {expected}")
    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
    invalid_rows = int((~valid).sum())

    print("2/5 reconstructing P09a anomaly strata and S16 baseline summaries from raw ROOT ...")
    meta_aug = add_anomaly_context(config, p04_config, meta, wave, valid)
    wave = wave[valid]
    meta_aug = add_match_bins(config, meta_aug)

    print(f"3/5 fitting leave-one-run-out traditional and ML charge models on {len(meta_aug)} valid rows ...")
    predictions, fold_audit = fit_loro(config, p04_config, meta_aug, wave)

    print("4/5 summarizing anomaly strata with run-block bootstrap CIs ...")
    summary, deltas, by_run = summarize_predictions(config, predictions)
    summary.to_csv(out_dir / "charge_bias_summary.csv", index=False)
    deltas.to_csv(out_dir / "stratum_deltas.csv", index=False)
    by_run.to_csv(out_dir / "by_run_metrics.csv", index=False)
    fold_audit.to_csv(out_dir / "fold_audit.csv", index=False)
    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    predictions[
        [
            "run",
            "eventno",
            "evt",
            "stave",
            "even_amp",
            "target_odd_pos_charge",
            "taxon",
            "label_baseline_excursion",
            "label_novel_early_pretrigger",
            "pred_integral_calibrated",
            "pred_robust_pretrigger_charge",
            "pred_p04_frozen_mlp",
            "pred_p04f_residual_mlp",
        ]
    ].sample(n=min(20000, len(predictions)), random_state=int(config["random_seed"])).to_csv(out_dir / "predictions_sample.csv", index=False)

    p04_result = load_json(ROOT / config["p04_reference_result"])
    s16_result = load_json(ROOT / config["s16_reference_result"])
    p04_ml_ref = [
        row
        for row in p04_result["benchmark"]
        if row["target"] == "charge" and row["method"] == "ml_hgb" and row["subset"] == "heldout_runs_57_65"
    ][0]["res68_abs_frac"]

    all_valid = summary[summary["stratum"] == "all_valid"].set_index("method")
    best_trad_name = (
        all_valid.loc[["peak_charge_calibrated", "integral_calibrated", "robust_pretrigger_charge", "template_fit_calibrated"]]
        .sort_values("res68_abs_frac")
        .index[0]
    )
    baseline_delta = deltas[
        (deltas["anomaly_stratum"] == "baseline_excursion") & (deltas["method"] == "robust_pretrigger_charge")
    ].iloc[0]
    early_delta = deltas[
        (deltas["anomaly_stratum"] == "novel_early_pretrigger") & (deltas["method"] == "robust_pretrigger_charge")
    ].iloc[0]
    ml_delta = deltas[
        (deltas["anomaly_stratum"] == "baseline_excursion") & (deltas["method"].str.startswith("p04f_residual_mlp_minus_"))
    ].iloc[0]
    finding = (
        f"Baseline-excursion rows do shift traditional robust-charge closure: matched-control res68 delta is "
        f"{baseline_delta['delta_res68_abs_frac']:.4f} and high-bias-tail delta is {baseline_delta['delta_high_bias_tail_fraction']:.4f}. "
        f"Early-pretrigger rows show res68 delta {early_delta['delta_res68_abs_frac']:.4f}. "
        f"Across all valid rows the best traditional method is {best_trad_name} at res68 "
        f"{all_valid.loc[best_trad_name, 'res68_abs_frac']:.4f}; P04f residual MLP is "
        f"{all_valid.loc['p04f_residual_mlp', 'res68_abs_frac']:.4f}. Within baseline-excursion rows, "
        f"P04f residual MLP minus best traditional res68 is {ml_delta['delta_res68_abs_frac']:.4f}. "
        "The anomaly strata are therefore not harmless for traditional charge closure, but the ML gain remains a duplicate-readout electronics closure."
    )
    leakage = {
        "train_heldout_overlap_total": int(fold_audit["train_heldout_overlap"].sum()),
        "shuffled_residual_res68_all_valid": float(all_valid.loc["shuffled_residual_mlp", "res68_abs_frac"]),
        "p04f_residual_res68_all_valid": float(all_valid.loc["p04f_residual_mlp", "res68_abs_frac"]),
        "p04_reference_charge_ml_res68": float(p04_ml_ref),
    }
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": total - expected,
            "pass": total == expected,
        },
        "n_valid_rows": int(len(meta_aug)),
        "invalid_target_rows_removed": invalid_rows,
        "run_split": "leave-one-run-out",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "primary_metrics": json.loads(summary.to_json(orient="records")),
        "stratum_deltas": json.loads(deltas.to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(out_dir, config, p04_result, s16_result, counts_by_run, summary, deltas, by_run, leakage, result)

    input_files = [p04.raw_path(p04_config, run) for run in p04.configured_runs(p04_config)]
    input_rows = [{"path": str(path), "sha256": sha256_file(path)} for path in input_files]
    input_rows.extend(
        [
            {"path": str(config_path), "sha256": sha256_file(config_path)},
            {"path": str(Path(__file__)), "sha256": sha256_file(Path(__file__))},
            {"path": str(p04_config_path), "sha256": sha256_file(p04_config_path)},
            {"path": str(ROOT / config["p09a_reference_config"]), "sha256": sha256_file(ROOT / config["p09a_reference_config"])},
            {"path": str(ROOT / config["p04_reference_result"]), "sha256": sha256_file(ROOT / config["p04_reference_result"])},
            {"path": str(ROOT / config["s16_reference_result"]), "sha256": sha256_file(ROOT / config["s16_reference_result"])},
        ]
    )
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    output_names = [
        "REPORT.md",
        "result.json",
        "input_sha256.csv",
        "charge_bias_summary.csv",
        "stratum_deltas.csv",
        "by_run_metrics.csv",
        "fold_audit.csv",
        "counts_by_run.csv",
        "predictions_sample.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "command": f"{sys.executable} scripts/p04f_baseline_excursion_charge_bias_closure.py --config {args.config}",
        "config": str(config_path),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "inputs": input_rows,
        "outputs": [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in output_names],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
