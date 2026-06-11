#!/usr/bin/env python3
"""P04u: root cause of A-stack real-versus-shuffled charge-transfer parity."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)),
    }


def run_block_ci(frame: pd.DataFrame, value_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {"bias_ci95": [None, None], "res68_ci95": [None, None], "full_rms_ci95": [None, None]}
    by_run = {run: frame[frame["run"] == run] for run in runs}
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    for idx in range(reps):
        sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        got = robust_metrics(sample[value_col].to_numpy(), sample[pred_col].to_numpy())
        bias[idx] = got["bias_median_frac"]
        res68[idx] = got["res68_abs_frac"]
        rms[idx] = got["full_rms_frac"]
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
    }


def delta_ci(
    frame: pd.DataFrame,
    value_col: str,
    method_col: str,
    control_col: str,
    rng: np.random.Generator,
    reps: int,
) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {"delta_res68_ci95": [None, None], "delta_full_rms_ci95": [None, None]}
    by_run = {run: frame[frame["run"] == run] for run in runs}
    d_res68 = np.empty(reps, dtype=float)
    d_rms = np.empty(reps, dtype=float)
    for idx in range(reps):
        sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        y = sample[value_col].to_numpy()
        denom = np.maximum(y, 1.0)
        frac_m = (sample[method_col].to_numpy() - y) / denom
        frac_c = (sample[control_col].to_numpy() - y) / denom
        d_res68[idx] = np.percentile(np.abs(frac_m), 68) - np.percentile(np.abs(frac_c), 68)
        d_rms[idx] = np.sqrt(np.mean(frac_m * frac_m)) - np.sqrt(np.mean(frac_c * frac_c))
    return {
        "delta_res68_ci95": [float(np.percentile(d_res68, 2.5)), float(np.percentile(d_res68, 97.5))],
        "delta_full_rms_ci95": [float(np.percentile(d_rms, 2.5)), float(np.percentile(d_rms, 97.5))],
    }


def support_cell(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["a_topology"].astype(str)
        + "|"
        + frame["topology_pattern"].astype(str)
        + "|"
        + frame["b2_amp_bin"].astype(str)
        + "|"
        + frame["saturation_stratum"].astype(str)
        + "|"
        + frame["anomaly_stratum"].astype(str)
        + "|"
        + frame["downstream_coincidence"].astype(str)
    )


def prepare_frame(p04h, frame: pd.DataFrame, wave: np.ndarray, config: dict) -> pd.DataFrame:
    out = p04h.add_support_strata(frame, wave, config)
    out["topology"] = out["a_topology"]
    out["target_charge"] = out["target_a_charge"]
    out["support_cell"] = support_cell(out)
    return out


def make_knockoff_matrix(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    knock = x.copy()
    for col in range(knock.shape[1]):
        rng.shuffle(knock[:, col])
    return knock


def conformal_coverage(y_train: np.ndarray, pred_train: np.ndarray, y_test: np.ndarray, pred_test: np.ndarray) -> Tuple[float, np.ndarray]:
    q68 = float(np.percentile(np.abs((pred_train - y_train) / np.maximum(y_train, 1.0)), 68))
    cover = np.abs((pred_test - y_test) / np.maximum(y_test, 1.0)) <= q68
    return q68, cover


def fit_models(config: dict, p04h, p04t, frame: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    methods = [
        "adaptive_template_ridge",
        "ridge_log_charge_support",
        "gradient_boosted_trees",
        "extra_trees_waveform",
        "random_forest_waveform",
        "mlp_waveform",
        "cnn1d_waveform",
        "hybrid_support_gate_cnn",
        "knockoff_extra_trees",
        "shuffled_target_extra_trees",
    ]
    work = frame.copy()
    for method in methods:
        work[f"pred_{method}"] = np.nan
        work[f"cover68_{method}"] = np.nan
        work[f"conformal_q68_{method}"] = np.nan

    x_charge = p04t.b_charge_features(work).astype(np.float64)
    x_wave = p04t.waveform_features(work, wave).astype(np.float64)
    x_scalar = p04h.scalar_wave_features(work, wave).astype(np.float64)
    y = work["target_charge"].to_numpy(dtype=float)
    y_log = np.log(np.maximum(y, 1.0))
    wave_nn = np.clip(wave, -5000.0, 25000.0).astype(np.float32)
    wave_center = np.nanmedian(wave_nn, axis=(0, 2), keepdims=True)
    wave_scale = np.nanstd(wave_nn, axis=(0, 2), keepdims=True) + 1e-6
    wave_nn = ((wave_nn - wave_center) / wave_scale).astype(np.float32)

    fold_rows: List[dict] = []
    for heldout_run in sorted(work["run"].unique()):
        print(f"  P04u fold heldout run {int(heldout_run)}", flush=True)
        train_mask = work["run"].to_numpy() != int(heldout_run)
        held_mask = ~train_mask
        train_idx = np.where(train_mask)[0]
        held_idx = np.where(held_mask)[0]
        if len(train_idx) > int(config["ml_max_train_rows"]):
            train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)

        train_frame = work.loc[train_mask].reset_index(drop=True)
        held_frame = work.loc[held_mask].reset_index(drop=True)
        train_wave = wave[train_mask]
        held_wave = wave[held_mask]
        x_template_train = np.column_stack(
            [x_scalar[train_mask], p04h.template_diagnostics(train_frame, train_wave, train_frame, train_wave)]
        )
        x_template_held = np.column_stack(
            [x_scalar[held_mask], p04h.template_diagnostics(train_frame, train_wave, held_frame, held_wave)]
        )
        template = make_pipeline(StandardScaler(), Ridge(alpha=12.0))
        template.fit(x_template_train, y_log[train_mask])
        pred_train = np.exp(template.predict(x_template_train))
        pred_held = np.exp(template.predict(x_template_held))
        work.loc[held_mask, "pred_adaptive_template_ridge"] = pred_held
        q68, cover = conformal_coverage(y[train_mask], pred_train, y[held_mask], pred_held)
        work.loc[held_mask, "cover68_adaptive_template_ridge"] = cover
        work.loc[held_mask, "conformal_q68_adaptive_template_ridge"] = q68

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        ridge.fit(x_charge[train_mask], y_log[train_mask])
        pred_train = np.exp(ridge.predict(x_charge[train_mask]))
        pred_held = np.exp(ridge.predict(x_charge[held_mask]))
        work.loc[held_mask, "pred_ridge_log_charge_support"] = pred_held
        q68, cover = conformal_coverage(y[train_mask], pred_train, y[held_mask], pred_held)
        work.loc[held_mask, "cover68_ridge_log_charge_support"] = cover
        work.loc[held_mask, "conformal_q68_ridge_log_charge_support"] = q68

        hgb = HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=0.055,
            max_iter=50,
            max_leaf_nodes=11,
            min_samples_leaf=10,
            l2_regularization=0.05,
            max_bins=64,
            random_state=int(config["random_seed"]) + int(heldout_run) * 17,
        )
        hgb.fit(x_wave[train_idx], y_log[train_idx])
        pred_train = np.exp(hgb.predict(x_wave[train_mask]))
        pred_held = np.exp(hgb.predict(x_wave[held_mask]))
        work.loc[held_mask, "pred_gradient_boosted_trees"] = pred_held
        q68, cover = conformal_coverage(y[train_mask], pred_train, y[held_mask], pred_held)
        work.loc[held_mask, "cover68_gradient_boosted_trees"] = cover
        work.loc[held_mask, "conformal_q68_gradient_boosted_trees"] = q68

        et = ExtraTreesRegressor(
            n_estimators=48,
            max_depth=7,
            min_samples_leaf=3,
            max_features=0.7,
            n_jobs=1,
            random_state=int(config["random_seed"]) + int(heldout_run) * 19,
        )
        et.fit(x_wave[train_idx], y_log[train_idx])
        pred_train = np.exp(et.predict(x_wave[train_mask]))
        pred_held = np.exp(et.predict(x_wave[held_mask]))
        work.loc[held_mask, "pred_extra_trees_waveform"] = pred_held
        q68, cover = conformal_coverage(y[train_mask], pred_train, y[held_mask], pred_held)
        work.loc[held_mask, "cover68_extra_trees_waveform"] = cover
        work.loc[held_mask, "conformal_q68_extra_trees_waveform"] = q68

        rf = RandomForestRegressor(
            n_estimators=36,
            max_depth=8,
            min_samples_leaf=3,
            max_features=0.7,
            n_jobs=1,
            random_state=int(config["random_seed"]) + int(heldout_run) * 23,
        )
        rf.fit(x_wave[train_idx], y_log[train_idx])
        pred_train = np.exp(rf.predict(x_wave[train_mask]))
        pred_held = np.exp(rf.predict(x_wave[held_mask]))
        work.loc[held_mask, "pred_random_forest_waveform"] = pred_held
        q68, cover = conformal_coverage(y[train_mask], pred_train, y[held_mask], pred_held)
        work.loc[held_mask, "cover68_random_forest_waveform"] = cover
        work.loc[held_mask, "conformal_q68_random_forest_waveform"] = q68

        nn_idx = train_idx
        if len(nn_idx) > int(config["nn_max_train_rows"]):
            nn_idx = rng.choice(nn_idx, size=int(config["nn_max_train_rows"]), replace=False)
        mlp = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(48, 24),
                activation="relu",
                alpha=0.002,
                learning_rate_init=0.002,
                    max_iter=160,
                early_stopping=True,
                validation_fraction=0.20,
                n_iter_no_change=12,
                random_state=int(config["random_seed"]) + int(heldout_run) * 29,
            ),
        )
        mlp.fit(x_wave[nn_idx], y_log[nn_idx])
        pred_train = np.exp(mlp.predict(x_wave[train_mask]))
        pred_held = np.exp(mlp.predict(x_wave[held_mask]))
        work.loc[held_mask, "pred_mlp_waveform"] = pred_held
        q68, cover = conformal_coverage(y[train_mask], pred_train, y[held_mask], pred_held)
        work.loc[held_mask, "cover68_mlp_waveform"] = cover
        work.loc[held_mask, "conformal_q68_mlp_waveform"] = q68

        for torch_method in ["cnn1d_waveform", "hybrid_support_gate_cnn"]:
            pred_held, meta = p04t.fit_torch_regressor(
                torch_method,
                wave_nn[nn_idx],
                x_charge[nn_idx],
                y_log[nn_idx],
                wave_nn[held_idx],
                x_charge[held_idx],
                config,
                int(config["random_seed"]) + int(heldout_run) * 31 + (0 if torch_method == "cnn1d_waveform" else 1000),
            )
            work.loc[held_mask, f"pred_{torch_method}"] = pred_held
            fold_rows.append({"heldout_run": int(heldout_run), "method": torch_method, **meta})

        knock_rng = np.random.default_rng(int(config["random_seed"]) + int(heldout_run) * 37)
        knock_train = make_knockoff_matrix(x_wave[train_idx], knock_rng)
        knock_held = make_knockoff_matrix(x_wave[held_idx], np.random.default_rng(int(config["random_seed"]) + int(heldout_run) * 37 + 1))
        knock = ExtraTreesRegressor(
            n_estimators=36,
            max_depth=7,
            min_samples_leaf=3,
            max_features=0.7,
            n_jobs=1,
            random_state=int(config["random_seed"]) + int(heldout_run) * 41,
        )
        knock.fit(knock_train, y_log[train_idx])
        work.loc[held_mask, "pred_knockoff_extra_trees"] = np.exp(knock.predict(knock_held))

        shuffled = y_log[train_idx].copy()
        rng.shuffle(shuffled)
        sentinel = ExtraTreesRegressor(
            n_estimators=36,
            max_depth=7,
            min_samples_leaf=3,
            max_features=0.7,
            n_jobs=1,
            random_state=int(config["random_seed"]) + int(heldout_run) * 43,
        )
        sentinel.fit(x_wave[train_idx], shuffled)
        work.loc[held_mask, "pred_shuffled_target_extra_trees"] = np.exp(sentinel.predict(x_wave[held_mask]))

    ci_rng = np.random.default_rng(int(config["random_seed"]) + 900)
    summary_rows = []
    for method in methods:
        row = {
            "method": method,
            "method_family": "control"
            if method in {"knockoff_extra_trees", "shuffled_target_extra_trees"}
            else "traditional"
            if method in {"adaptive_template_ridge"}
            else "ml_nn",
        }
        row.update(robust_metrics(work["target_charge"].to_numpy(), work[f"pred_{method}"].to_numpy()))
        row.update(run_block_ci(work, "target_charge", f"pred_{method}", ci_rng, int(config["bootstrap_reps"])))
        if work[f"cover68_{method}"].notna().any():
            row["conformal_coverage68"] = float(work[f"cover68_{method}"].mean())
            row["conformal_q68_median"] = float(work[f"conformal_q68_{method}"].median())
        else:
            row["conformal_coverage68"] = None
            row["conformal_q68_median"] = None
        summary_rows.append(row)

    by_run_rows = []
    for run, sub in work.groupby("run"):
        for method in methods:
            row = {"run": int(run), "method": method}
            row.update(robust_metrics(sub["target_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
            by_run_rows.append(row)

    delta_rng = np.random.default_rng(int(config["random_seed"]) + 1900)
    delta_rows = []
    for method in methods:
        if method == "shuffled_target_extra_trees":
            continue
        row = {"method": method, "control": "shuffled_target_extra_trees"}
        row.update(delta_ci(work, "target_charge", f"pred_{method}", "pred_shuffled_target_extra_trees", delta_rng, int(config["bootstrap_reps"])))
        m = robust_metrics(work["target_charge"].to_numpy(), work[f"pred_{method}"].to_numpy())
        c = robust_metrics(work["target_charge"].to_numpy(), work["pred_shuffled_target_extra_trees"].to_numpy())
        row["delta_res68_vs_shuffled"] = float(m["res68_abs_frac"] - c["res68_abs_frac"])
        row["delta_full_rms_vs_shuffled"] = float(m["full_rms_frac"] - c["full_rms_frac"])
        delta_rows.append(row)

    return work, pd.DataFrame(summary_rows), pd.DataFrame(by_run_rows), pd.DataFrame(delta_rows), pd.DataFrame(fold_rows)


def summarize_root_causes(config: dict, pred: pd.DataFrame, summary: pd.DataFrame, by_run: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    real_methods = summary.loc[~summary["method_family"].eq("control"), "method"].tolist()
    best_method = str(summary[summary["method"].isin(real_methods)].sort_values(["res68_abs_frac", "full_rms_frac"]).iloc[0]["method"])
    categories = [
        "a_topology",
        "topology_pattern",
        "b2_amp_bin",
        "saturation_stratum",
        "anomaly_stratum",
        "downstream_coincidence",
        "support_cell",
    ]
    rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 2900)
    for category in categories:
        for value, sub in pred.groupby(category):
            if len(sub) < int(config["min_support_rows"]):
                continue
            method_metrics = {
                method: robust_metrics(sub["target_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy())
                for method in real_methods
            }
            best = min(method_metrics.items(), key=lambda item: (item[1]["res68_abs_frac"], item[1]["full_rms_frac"]))
            shuffle_m = robust_metrics(sub["target_charge"].to_numpy(), sub["pred_shuffled_target_extra_trees"].to_numpy())
            knock_m = robust_metrics(sub["target_charge"].to_numpy(), sub["pred_knockoff_extra_trees"].to_numpy())
            row = {
                "category": category,
                "stratum": str(value),
                "n": int(len(sub)),
                "runs": int(sub["run"].nunique()),
                "best_real_method": best[0],
                "best_real_res68": best[1]["res68_abs_frac"],
                "shuffled_res68": shuffle_m["res68_abs_frac"],
                "knockoff_res68": knock_m["res68_abs_frac"],
                "best_minus_shuffled_res68": best[1]["res68_abs_frac"] - shuffle_m["res68_abs_frac"],
                "best_minus_knockoff_res68": best[1]["res68_abs_frac"] - knock_m["res68_abs_frac"],
                "median_target_charge": float(np.median(sub["target_charge"].to_numpy())),
            }
            if sub["run"].nunique() >= 2:
                row.update(delta_ci(sub, "target_charge", f"pred_{best[0]}", "pred_shuffled_target_extra_trees", rng, int(config["bootstrap_reps"])))
            else:
                row.update({"delta_res68_ci95": [None, None], "delta_full_rms_ci95": [None, None]})
            strong = len(sub) >= int(config["strong_support_rows"]) and sub["run"].nunique() >= int(config["strong_support_runs"])
            informative = row["best_minus_shuffled_res68"] <= float(config["identifiability_delta_res68"])
            if strong and informative:
                row["root_cause_call"] = "candidate_identifiable_atom"
            elif strong:
                row["root_cause_call"] = "strong_support_control_parity"
            else:
                row["root_cause_call"] = "limited_support"
            rows.append(row)

    run_best = by_run[by_run["method"].eq(best_method)].merge(
        by_run[by_run["method"].eq("shuffled_target_extra_trees")][["run", "res68_abs_frac"]].rename(
            columns={"res68_abs_frac": "shuffled_res68_abs_frac"}
        ),
        on="run",
        how="left",
    )
    run_best["best_method"] = best_method
    run_best["best_minus_shuffled_res68"] = run_best["res68_abs_frac"] - run_best["shuffled_res68_abs_frac"]
    run_best["passes_delta_gate"] = run_best["best_minus_shuffled_res68"] <= float(config["identifiability_delta_res68"])
    return (
        pd.DataFrame(rows).sort_values(["root_cause_call", "best_minus_shuffled_res68", "n"], ascending=[True, True, False]),
        run_best.sort_values("run"),
    )


def table(df: pd.DataFrame, cols: List[str], max_rows: int = None) -> str:
    view = df[cols].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    p04c_summary: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run_gate: pd.DataFrame,
    root_causes: pd.DataFrame,
    result: dict,
) -> None:
    p04c_ridge = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    p04c_et = p04c_summary[p04c_summary["method"] == "b_waveform_extra_trees"].iloc[0]
    lines = [
        "# P04u A-Stack Shuffled-Sentinel Root Cause",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.",
        "- **Split:** leave-one-run-out by run for every prediction; bootstrap intervals resample complete run blocks.",
        "- **Primary estimand:** selected A1/A3 positive-lobe charge matched to B-stack events by `(run, EVT)`, using only B-stack waveform/support features.",
        "- **Preregistered identifiability gate:** best real minus shuffled `res68 <= -0.03` in at least three held-out runs.",
        "",
        "## Abstract",
        "",
        result["abstract"],
        "",
        "## Raw-ROOT Reproduction",
        "",
        f"B-stack S00 selected-pulse count: reproduced `{int(b_counts['selected_pulses'].sum()):,}` versus expected `{int(config['expected_b_s00_selected_pulses']):,}`.",
        "",
        table(a_counts, ["sample", "events_with_selected", "selected_pulses", "A1", "A3"]),
        "",
        f"P04c event-matched charge-transfer reproduction: `{int(p04c_ridge['n'])}` rows, ridge res68 `{p04c_ridge['res68_abs_frac']:.6f}`, waveform ExtraTrees res68 `{p04c_et['res68_abs_frac']:.6f}`.",
        "",
        "## Methods",
        "",
        "For event `i`, the target is",
        "",
        "`Q_i^A = I(A1_i) q_{i,A1} + I(A3_i) q_{i,A3}`,",
        "",
        "where the indicator requires an A-stack amplitude above 1000 ADC and `q` is baseline-subtracted positive-lobe charge. Models fit `z_i = log(max(Q_i^A,1))` on training runs and report `Qhat_i = exp(zhat_i)` on the held-out run.",
        "",
        "The fractional residual is",
        "",
        "`r_i(m) = (Qhat_i(m) - Q_i^A) / max(Q_i^A, 1)`.",
        "",
        "The primary width is `res68_m = quantile_0.68(|r_i(m)|)`, with median bias, full RMS, within-10%, within-25%, and train-fold conformal 68% coverage as secondary diagnostics. The traditional comparator is a train-fold adaptive-template ridge using B2 template residual diagnostics plus scalar B-stack support summaries. The required ML/NN panel contains ridge, gradient-boosted trees, ExtraTrees, random forest, MLP, 1D-CNN, and the new hybrid support-gated CNN. Root-cause controls are shuffled-target ExtraTrees and column-knockoff ExtraTrees.",
        "",
        "## Head-To-Head Benchmark",
        "",
        table(
            summary,
            [
                "method",
                "method_family",
                "n",
                "bias_median_frac",
                "bias_ci95",
                "res68_abs_frac",
                "res68_ci95",
                "full_rms_frac",
                "full_rms_ci95",
                "within_25pct",
                "conformal_coverage68",
            ],
        ),
        "",
        "## Real Minus Shuffled Deltas",
        "",
        table(
            deltas,
            [
                "method",
                "control",
                "delta_res68_vs_shuffled",
                "delta_res68_ci95",
                "delta_full_rms_vs_shuffled",
                "delta_full_rms_ci95",
            ],
        ),
        "",
        "## Held-Out Run Gate",
        "",
        table(
            by_run_gate,
            [
                "run",
                "best_method",
                "n",
                "res68_abs_frac",
                "shuffled_res68_abs_frac",
                "best_minus_shuffled_res68",
                "passes_delta_gate",
            ],
        ),
        "",
        "## Root-Cause Strata",
        "",
        table(
            root_causes,
            [
                "category",
                "stratum",
                "n",
                "runs",
                "best_real_method",
                "best_real_res68",
                "shuffled_res68",
                "knockoff_res68",
                "best_minus_shuffled_res68",
                "delta_res68_ci95",
                "root_cause_call",
            ],
            max_rows=40,
        ),
        "",
        "## Systematics And Caveats",
        "",
        "- The estimand is selected A-stack charge, not deposited energy. A-stack selection and acceptance are inside the target definition.",
        "- The row set is constrained to `(run, EVT)` matches with selected B2 and selected A1 or A3. Unmatched triggers and quiet A-stack events are outside scope.",
        "- Run-block bootstrap intervals quantify transfer across the available runs, but cannot cover unavailable beam conditions or unmounted acquisition metadata.",
        "- Shuffled and knockoff controls are intentionally model-matched to the tree regressors. If a future neural control is required, it should use the same run split and support-cell matching before any physics-facing claim.",
        "- CNN predictions are clipped on the log scale to train-fold target quantiles before exponentiation. This prevents non-finite back-transforms but can make neural full RMS optimistic in extreme tails.",
        "- A real model beating shuffled in one sparse cell is not sufficient: the preregistered gate requires a margin of `-0.03` in at least three held-out runs.",
        "",
        "## Verdict",
        "",
        result["finding"],
        "",
        f"Winner recorded in `result.json`: `{result['winner']}`.",
        "",
        "## Artifacts",
        "",
        "`result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `b_s00_counts_by_run.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `method_summary.csv`, `method_deltas_vs_shuffled.csv`, `by_run_metrics.csv`, `run_identifiability_gate.csv`, `root_cause_strata.csv`, `predictions.csv`, and `torch_fold_audit.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04u_1781063920_599_196428b2_astack_shuffled_sentinel_root_cause.yaml")
    args = parser.parse_args()
    t0 = time.time()

    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p04c = load_module("p04c_ab_event_matched_charge_transfer", Path(config["p04c_script"]))
    p04h = load_module("p04h_support_map", Path(config["p04h_script"]))
    p04t = load_module("p04t_topology_lower_bound", Path(config["p04t_script"]))

    print("1/7 reproducing raw ROOT gates ...", flush=True)
    b_counts = p04c.count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "b_s00_counts_by_run.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    if got_b != expected_b:
        raise RuntimeError(f"B-stack selected-pulse reproduction failed: {got_b} != {expected_b}")

    a_counts = p04c.count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A-stack event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A-stack pulse gate failed for {row['sample']}")

    print("2/7 extracting event-matched A/B rows ...", flush=True)
    frame, wave, ab_counts = p04c.extract_ab_rows(config)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)
    if len(frame) != int(config["expected_p04c_rows"]):
        raise RuntimeError(f"P04c row reproduction failed: {len(frame)} != {config['expected_p04c_rows']}")
    frame = prepare_frame(p04h, frame, wave, config)

    print("3/7 reproducing P04c broad number ...", flush=True)
    p04c_summary, p04c_by_run, p04c_by_amp, _p04c_leakage = p04c.fit_leave_one_run(config, frame.copy(), wave)
    p04c_summary.to_csv(out_dir / "p04c_reproduction_summary.csv", index=False)
    p04c_by_run.to_csv(out_dir / "p04c_reproduction_by_run.csv", index=False)
    p04c_by_amp.to_csv(out_dir / "p04c_reproduction_by_b2_amp.csv", index=False)
    p04c_ridge = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    if abs(float(p04c_ridge["res68_abs_frac"]) - float(config["expected_p04c_charge_transfer_ridge_res68"])) > float(config["expected_p04c_tolerance_res68"]):
        raise RuntimeError("P04c ridge res68 reproduction failed")

    print("4/7 fitting P04u leave-one-run-out method panel ...", flush=True)
    pred, summary, by_run, deltas, torch_audit = fit_models(config, p04h, p04t, frame, wave)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    by_run.to_csv(out_dir / "by_run_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas_vs_shuffled.csv", index=False)
    torch_audit.to_csv(out_dir / "torch_fold_audit.csv", index=False)

    print("5/7 summarizing root-cause strata and gate ...", flush=True)
    root_causes, run_gate = summarize_root_causes(config, pred, summary, by_run)
    root_causes.to_csv(out_dir / "root_cause_strata.csv", index=False)
    run_gate.to_csv(out_dir / "run_identifiability_gate.csv", index=False)
    pred_cols = [
        "run",
        "evt",
        "target_charge",
        "a_topology",
        "topology_pattern",
        "b2_amp_bin",
        "saturation_stratum",
        "anomaly_stratum",
        "downstream_coincidence",
        "support_cell",
    ] + [col for col in pred.columns if col.startswith("pred_")]
    pred[pred_cols].to_csv(out_dir / "predictions.csv", index=False)

    print("6/7 selecting winner and writing report ...", flush=True)
    real = summary[~summary["method_family"].eq("control")].copy()
    real_ranking = real.sort_values(["res68_abs_frac", "full_rms_frac", "method"]).reset_index(drop=True)
    controls = summary[summary["method_family"].eq("control")].set_index("method")
    best_real = real_ranking.iloc[0]
    shuffled = controls.loc["shuffled_target_extra_trees"]
    knockoff = controls.loc["knockoff_extra_trees"]
    pass_runs = int(run_gate["passes_delta_gate"].sum())
    gate_pass = pass_runs >= int(config["identifiability_min_runs"]) and float(best_real["res68_abs_frac"] - shuffled["res68_abs_frac"]) <= float(config["identifiability_delta_res68"])
    candidate_atoms = root_causes[root_causes["root_cause_call"].eq("candidate_identifiable_atom")]
    if gate_pass and len(candidate_atoms):
        winner = str(best_real["method"])
        finding = (
            f"The best real method `{winner}` passes the run gate in {pass_runs} runs and has global real-minus-shuffled "
            f"res68 delta {float(best_real['res68_abs_frac'] - shuffled['res68_abs_frac']):.4f}. Candidate support atoms are present, "
            "so P04h parity is partly a support-cell mixing problem."
        )
    else:
        winner = "null_control_parity"
        finding = (
            f"No model passes the preregistered identifiability gate. The best real method is `{best_real['method']}` "
            f"with res68 {float(best_real['res68_abs_frac']):.4f}, while shuffled-target ExtraTrees is {float(shuffled['res68_abs_frac']):.4f} "
            f"and knockoff ExtraTrees is {float(knockoff['res68_abs_frac']):.4f}; only {pass_runs} held-out runs meet the "
            f"{float(config['identifiability_delta_res68']):.2f} delta threshold. The P04h null is therefore best explained by "
            "B-to-A waveform non-identifiability under the current event match, not by an omitted off-the-shelf ML architecture."
        )
    abstract = (
        f"P04u reproduces the raw B-stack selected-pulse count ({got_b:,}), A-stack analysis gates, and P04c "
        f"event-matched ridge res68 ({float(p04c_ridge['res68_abs_frac']):.6f}) before fitting models. The strongest real "
        f"method is `{best_real['method']}` but the operational winner is `{winner}` because the real-versus-shuffled "
        "margin does not satisfy the preregistered run-level identifiability gate."
    )
    result = {
        "study": "P04u",
        "title": config["title"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "winner": winner,
        "point_estimate_best_real_method": str(best_real["method"]),
        "winner_selection": {
            "score_definition": "promote best real method only if global best-minus-shuffled res68 <= gate and at least three held-out runs pass the same delta gate; otherwise null_control_parity wins",
            "identifiability_delta_res68": float(config["identifiability_delta_res68"]),
            "identifiability_min_runs": int(config["identifiability_min_runs"]),
            "heldout_runs_passing_gate": pass_runs,
            "real_method_ranking": json.loads(real_ranking.to_json(orient="records")),
        },
        "abstract": abstract,
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "astack_analysis_counts": json.loads(a_counts.to_json(orient="records")),
            "p04c_expected_rows": int(config["expected_p04c_rows"]),
            "p04c_reproduced_rows": int(len(frame)),
            "p04c_expected_charge_transfer_ridge_res68": float(config["expected_p04c_charge_transfer_ridge_res68"]),
            "p04c_reproduced_charge_transfer_ridge_res68": float(p04c_ridge["res68_abs_frac"]),
            "p04c_reproduction_pass": True,
        },
        "row_definition": {
            "match_key": "(run, EVT)",
            "source_gate": "B2 amplitude > 1000 ADC",
            "target_gate": "A1 or A3 amplitude > 1000 ADC",
            "target": "selected A1/A3 positive-lobe charge",
            "features": "B-stack even-channel waveforms and charge/support summaries only",
        },
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "methods": {
            "traditional": ["adaptive_template_ridge"],
            "required_ml_nn": ["ridge_log_charge_support", "gradient_boosted_trees", "mlp_waveform", "cnn1d_waveform"],
            "additional_ml": ["extra_trees_waveform", "random_forest_waveform"],
            "new_architecture": "hybrid_support_gate_cnn",
            "controls": ["knockoff_extra_trees", "shuffled_target_extra_trees"],
        },
        "method_summary": json.loads(summary.to_json(orient="records")),
        "method_deltas_vs_shuffled": json.loads(deltas.to_json(orient="records")),
        "run_identifiability_gate": json.loads(run_gate.to_json(orient="records")),
        "root_cause_strata_head": json.loads(root_causes.head(80).to_json(orient="records")),
        "finding": finding,
        "next_tickets": [
            {
                "title": "P04v: neural matched-controls for A/B charge-transfer non-identifiability",
                "question": "Do shuffled-target and B-waveform knockoff neural controls match the P04u CNN and support-gated CNN under the same leave-one-run-out support-cell gates?",
                "expected_information_gain": "Tests whether the remaining P04u neural point estimates are architecture-specific leakage/control artifacts or genuine waveform information without adding A-side target leakage.",
            }
        ],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, p04c_summary, summary, deltas, run_gate, root_causes, result)

    print("7/7 writing hashes and manifest ...", flush=True)
    input_runs = sorted(set(p04c.configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": "P04u",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/p04u_1781063920_599_196428b2_astack_shuffled_sentinel_root_cause.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": "scripts/p04u_1781063920_599_196428b2_astack_shuffled_sentinel_root_cause.py",
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
            "p04c_script_sha256": sha256_file(Path(config["p04c_script"])),
            "p04h_script_sha256": sha256_file(Path(config["p04h_script"])),
            "p04t_script_sha256": sha256_file(Path(config["p04t_script"])),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
