#!/usr/bin/env python3
"""S04c pathology-stratified timing-resolution tail table.

This ticket reuses the already-reviewed raw ROOT loaders from S04b/S16f, then
adds a run-held-out residual benchmark and fixed pathology-axis tail ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def load_module(name: str, rel_path: str):
    path = Path(__file__).resolve().parents[1] / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {rel_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S04B = load_module("s04b_base", "scripts/s04b_1781009378_adaptive_lowering_covariates.py")
S16F = load_module("s16f_base", "scripts/s16f_1781015168_1090_5b553d2a_tail_mechanism.py")


TAIL_COL = "tail_abs_gt_threshold"
TRAD_FEATURES = [
    "delta_lowering_adc",
    "abs_delta_lowering_adc",
    "max_lowering_adc",
    "delta_log_amp",
    "delta_peak_sample",
    "mean_peak_sample",
    "mean_area_over_amp",
    "max_pretrigger_abs_adc",
    "max_late_abs_adc",
    "most_negative_postpeak_adc",
    "pair",
    "s16_lowering_axis",
    "peak_phase_axis",
]
ML_FEATURES = [
    "delta_lowering_adc",
    "abs_delta_lowering_adc",
    "max_lowering_adc",
    "sum_lowering_adc",
    "delta_lowering_frac",
    "max_lowering_frac",
    "delta_log_amp",
    "min_log_amp",
    "delta_peak_sample",
    "mean_peak_sample",
    "delta_area_over_amp",
    "mean_area_over_amp",
    "delta_positive_area_over_amp",
    "mean_positive_area_over_amp",
    "max_tail_area_frac",
    "delta_tail_area_frac",
    "max_width20_samples",
    "delta_width20_samples",
    "max_width50_samples",
    "max_pretrigger_abs_adc",
    "delta_pretrigger_abs_adc",
    "max_pretrigger_ptp_adc",
    "max_late_abs_adc",
    "delta_late_abs_adc",
    "most_negative_postpeak_adc",
    "has_pretrigger_anomaly",
    "has_late_anomaly",
    "pair",
    "s16_lowering_axis",
    "pretrigger_axis",
    "p07_saturation_axis",
    "s10_two_pulse_axis",
    "dropout_jagged_axis",
    "peak_phase_axis",
    "p09_taxon_proxy",
]
PATHOLOGY_AXES = [
    "s16_lowering_axis",
    "pretrigger_axis",
    "p07_saturation_axis",
    "s10_two_pulse_axis",
    "dropout_jagged_axis",
    "peak_phase_axis",
    "p09_taxon_proxy",
]
CATEGORICAL_FEATURES = {"pair", *PATHOLOGY_AXES}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def output_hashes(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def analysis_config_for_loader(config: dict) -> dict:
    out = json.loads(json.dumps(config))
    runs = [int(r) for r in config["timing"]["analysis_runs"]]
    out["timing"]["train_runs"] = runs
    out["timing"]["heldout_runs"] = []
    return out


def add_pathology_axes(pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    p = pairs.copy()
    th = config["pathology_thresholds"]
    p["s16_lowering_axis"] = pd.cut(
        p["max_lowering_adc"],
        bins=[-np.inf, 0.0, float(th["medium_lowering_adc"]), float(th["large_lowering_adc"]), np.inf],
        labels=["none", "small", "medium", "large"],
        right=True,
    ).astype(str)
    p["pretrigger_axis"] = pd.cut(
        p["max_pretrigger_abs_adc"],
        bins=[-np.inf, float(th["pretrigger_medium_adc"]), float(th["pretrigger_large_adc"]), np.inf],
        labels=["quiet", "moderate", "large"],
        right=False,
    ).astype(str)
    sat_high = (p["max_width50_samples"] >= float(th["saturation_width50_high_samples"])) | (
        p["max_width20_samples"] >= float(th["saturation_width20_high_samples"])
    )
    sat_mid = p["max_width50_samples"] >= float(th["saturation_width50_mid_samples"])
    p["p07_saturation_axis"] = np.select(
        [sat_high.to_numpy(), sat_mid.to_numpy()],
        ["wide_plateau", "shoulder_wide"],
        default="narrower",
    )
    two_high = (p["max_tail_area_frac"] >= float(th["tail_area_frac_high"])) | (p["max_late_abs_adc"] >= float(th["late_abs_adc"]))
    two_mid = p["max_tail_area_frac"] >= float(th["tail_area_frac_mid"])
    p["s10_two_pulse_axis"] = np.select(
        [two_high.to_numpy(), two_mid.to_numpy()],
        ["high_broad_late", "mid_broad_late"],
        default="low_broad_late",
    )
    drop = p["most_negative_postpeak_adc"] <= float(th["dropout_postpeak_adc"])
    p["dropout_jagged_axis"] = np.where(drop, "negative_dropout", "not_dropout")
    p["peak_phase_axis"] = pd.cut(
        p["mean_peak_sample"],
        bins=[-np.inf, float(th["peak_early"]), float(th["peak_late"]), np.inf],
        labels=["early_peak", "nominal_peak", "late_peak"],
        right=False,
    ).astype(str)
    taxon = np.full(len(p), "ordinary_shape", dtype=object)
    taxon[drop.to_numpy()] = "dropout_or_jagged"
    taxon[sat_high.to_numpy()] = "saturation_boundary"
    taxon[two_high.to_numpy()] = "delayed_or_two_pulse"
    taxon[(p["pretrigger_axis"] == "large").to_numpy()] = "baseline_excursion"
    p["p09_taxon_proxy"] = taxon
    return p


def center_with_train_median(train: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    med = train.groupby("pair")["residual_ns"].median()
    global_med = float(train["residual_ns"].median())
    centers = np.asarray([float(med.get(pair, global_med)) for pair in frame["pair"]], dtype=float)
    return frame["residual_ns"].to_numpy(dtype=float) - centers


def rf_regressor(config: dict, seed: int) -> RandomForestRegressor:
    params = config["ml"]["random_forest"]
    return RandomForestRegressor(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        random_state=int(seed),
        n_jobs=1,
    )


def rf_classifier(config: dict, seed: int) -> RandomForestClassifier:
    params = config["ml"]["random_forest"]
    return RandomForestClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        class_weight="balanced_subsample",
        random_state=int(seed),
        n_jobs=1,
    )


def make_preprocessor(feature_cols: List[str]) -> ColumnTransformer:
    numeric = [col for col in feature_cols if col not in CATEGORICAL_FEATURES]
    categorical = [col for col in feature_cols if col in CATEGORICAL_FEATURES]
    return ColumnTransformer(
        [
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ]
    )


def oof_models(pairs: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    out = pairs.copy().reset_index(drop=True)
    for col in [
        "centered_train_residual_ns",
        "residual_traditional_corrected_ns",
        "residual_ml_corrected_ns",
        "residual_ml_shuffled_corrected_ns",
        "residual_ml_oracle_corrected_ns",
        "ml_tail_probability",
        "ml_tail_probability_shuffled",
    ]:
        out[col] = np.nan
    groups = out["run"].to_numpy(dtype=int)
    runs = np.unique(groups)
    n_splits = min(int(config["ml"]["cv_folds"]), len(runs))
    fold_rows = []
    clf_rows = []
    for fold, (tr, va) in enumerate(GroupKFold(n_splits=n_splits).split(out, groups=groups), start=1):
        train = out.iloc[tr].copy()
        valid = out.iloc[va].copy()
        y_train = center_with_train_median(train, train)
        y_valid_center = center_with_train_median(train, valid)
        out.loc[va, "centered_train_residual_ns"] = y_valid_center

        trad = make_pipeline(make_preprocessor(TRAD_FEATURES), Ridge(alpha=float(config["traditional"]["ridge_alpha"])))
        trad.fit(train[TRAD_FEATURES], y_train)
        trad_pred = trad.predict(valid[TRAD_FEATURES])
        out.loc[va, "residual_traditional_corrected_ns"] = y_valid_center - trad_pred

        ml = make_pipeline(make_preprocessor(ML_FEATURES), rf_regressor(config, int(config["ml"]["random_seed"]) + fold))
        ml.fit(train[ML_FEATURES], y_train)
        ml_pred = ml.predict(valid[ML_FEATURES])
        out.loc[va, "residual_ml_corrected_ns"] = y_valid_center - ml_pred

        shuffled_y = rng.permutation(y_train)
        shuffled = make_pipeline(make_preprocessor(ML_FEATURES), rf_regressor(config, int(config["ml"]["random_seed"]) + 100 + fold))
        shuffled.fit(train[ML_FEATURES], shuffled_y)
        out.loc[va, "residual_ml_shuffled_corrected_ns"] = y_valid_center - shuffled.predict(valid[ML_FEATURES])

        train_oracle = train.assign(centered_oracle_ns=y_train)
        valid_oracle = valid.assign(centered_oracle_ns=y_valid_center)
        oracle_cols = ML_FEATURES + ["centered_oracle_ns"]
        oracle = make_pipeline(make_preprocessor(oracle_cols), rf_regressor(config, int(config["ml"]["random_seed"]) + 200 + fold))
        oracle.fit(train_oracle[oracle_cols], y_train)
        out.loc[va, "residual_ml_oracle_corrected_ns"] = y_valid_center - oracle.predict(valid_oracle[oracle_cols])

        y_tail = train[TAIL_COL].astype(int).to_numpy()
        clf_base = make_pipeline(make_preprocessor(ML_FEATURES), rf_classifier(config, int(config["ml"]["random_seed"]) + 300 + fold))
        clf = CalibratedClassifierCV(clf_base, method="sigmoid", cv=3)
        clf.fit(train[ML_FEATURES], y_tail)
        prob = clf.predict_proba(valid[ML_FEATURES])[:, 1]
        out.loc[va, "ml_tail_probability"] = prob

        shuf_tail = rng.permutation(y_tail)
        clf_shuf_base = make_pipeline(make_preprocessor(ML_FEATURES), rf_classifier(config, int(config["ml"]["random_seed"]) + 400 + fold))
        clf_shuf = CalibratedClassifierCV(clf_shuf_base, method="sigmoid", cv=3)
        clf_shuf.fit(train[ML_FEATURES], shuf_tail)
        out.loc[va, "ml_tail_probability_shuffled"] = clf_shuf.predict_proba(valid[ML_FEATURES])[:, 1]

        yh = valid[TAIL_COL].astype(int).to_numpy()
        clf_rows.append(
            {
                "fold": fold,
                "heldout_runs": ",".join(str(int(r)) for r in sorted(valid["run"].unique())),
                "n": int(len(valid)),
                "tail_rate": float(yh.mean()),
                "auc": float(roc_auc_score(yh, prob)) if len(np.unique(yh)) > 1 else np.nan,
                "average_precision": float(average_precision_score(yh, prob)) if yh.sum() else np.nan,
                "brier": float(brier_score_loss(yh, prob)),
                "shuffled_auc": float(roc_auc_score(yh, out.loc[va, "ml_tail_probability_shuffled"])) if len(np.unique(yh)) > 1 else np.nan,
            }
        )
        fold_rows.append(
            {
                "fold": fold,
                "heldout_runs": ",".join(str(int(r)) for r in sorted(valid["run"].unique())),
                "train_rows": int(len(train)),
                "heldout_rows": int(len(valid)),
                "raw_sigma68_ns": S16F.sigma68(y_valid_center),
                "traditional_sigma68_ns": S16F.sigma68(out.loc[va, "residual_traditional_corrected_ns"].to_numpy(dtype=float)),
                "ml_sigma68_ns": S16F.sigma68(out.loc[va, "residual_ml_corrected_ns"].to_numpy(dtype=float)),
            }
        )

    row_scores = []
    for tr, va in KFold(n_splits=5, shuffle=True, random_state=int(config["ml"]["random_seed"]) + 900).split(out):
        train = out.iloc[tr].copy()
        valid = out.iloc[va].copy()
        y_train = train["centered_residual_ns"].to_numpy(dtype=float)
        model = make_pipeline(make_preprocessor(ML_FEATURES), rf_regressor(config, int(config["ml"]["random_seed"]) + 901))
        model.fit(train[ML_FEATURES], y_train)
        corrected = valid["centered_residual_ns"].to_numpy(dtype=float) - model.predict(valid[ML_FEATURES])
        row_scores.append(S16F.sigma68(corrected))
    fold_df = pd.DataFrame(fold_rows)
    cv_summary = {
        "run_cv_ml_sigma68_ns": float(fold_df["ml_sigma68_ns"].mean()),
        "row_cv_ml_sigma68_ns": float(np.mean(row_scores)),
        "row_minus_run_cv_ml_sigma68_ns": float(np.mean(row_scores) - fold_df["ml_sigma68_ns"].mean()),
        "tail_classifier_auc_mean": float(np.nanmean([r["auc"] for r in clf_rows])),
        "tail_classifier_ap_mean": float(np.nanmean([r["average_precision"] for r in clf_rows])),
        "tail_classifier_brier_mean": float(np.nanmean([r["brier"] for r in clf_rows])),
        "tail_classifier_shuffled_auc_mean": float(np.nanmean([r["shuffled_auc"] for r in clf_rows])),
    }
    return out, fold_df, pd.DataFrame(clf_rows), cv_summary


def metric_summary(frame: pd.DataFrame, residual_col: str, config: dict) -> Dict[str, float]:
    out = S04B.metric_summary(frame, residual_col, config)
    vals = frame[residual_col].to_numpy(dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals):
        med = float(np.median(vals))
        abs_centered = np.abs(vals - med)
        prob = frame["ml_tail_probability"].to_numpy(dtype=float) if "ml_tail_probability" in frame else np.full(len(frame), np.nan)
        out["pull_width_ml_tail_prob"] = float(np.sqrt(np.mean((abs_centered / np.sqrt(np.maximum(prob[: len(vals)], 1e-3))) ** 2)))
    else:
        out["pull_width_ml_tail_prob"] = np.nan
    return out


def run_block_bootstrap(frame: pd.DataFrame, residual_col: str, config: dict, rng: np.random.Generator) -> Dict[str, float]:
    boot = S04B.run_event_bootstrap(frame, residual_col, config, rng)
    return {
        "sigma68_ci_low": boot["sigma68_ci_low"],
        "sigma68_ci_high": boot["sigma68_ci_high"],
        "full_rms_ci_low": boot["full_rms_ci_low"],
        "full_rms_ci_high": boot["full_rms_ci_high"],
        "tail_ci_low": boot["tail_ci_low"],
        "tail_ci_high": boot["tail_ci_high"],
    }


def benchmark_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for method, col in [
        ("raw_cfd20_pair_centered", "centered_train_residual_ns"),
        ("traditional_ridge_pathology", "residual_traditional_corrected_ns"),
        ("ml_rf_pathology", "residual_ml_corrected_ns"),
        ("ml_shuffled_target_control", "residual_ml_shuffled_corrected_ns"),
        ("ml_intentional_oracle", "residual_ml_oracle_corrected_ns"),
    ]:
        rows.append({"method": method, **metric_summary(oof, col, config), **run_block_bootstrap(oof, col, config, rng)})
    return pd.DataFrame(rows)


def pathology_tail_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    small_boot = json.loads(json.dumps(config))
    small_boot["ml"]["bootstrap_samples"] = min(160, int(config["ml"]["bootstrap_samples"]))
    methods = [
        ("raw_cfd20_pair_centered", "centered_train_residual_ns"),
        ("traditional_ridge_pathology", "residual_traditional_corrected_ns"),
        ("ml_rf_pathology", "residual_ml_corrected_ns"),
    ]
    for axis in PATHOLOGY_AXES:
        for stratum, sub in oof.groupby(axis, dropna=False):
            if len(sub) < 20:
                continue
            for method, col in methods:
                rows.append(
                    {
                        "axis": axis,
                        "stratum": str(stratum),
                        "method": method,
                        **metric_summary(sub, col, config),
                        **run_block_bootstrap(sub, col, small_boot, rng),
                        "mean_ml_tail_probability": float(sub["ml_tail_probability"].mean()),
                    }
                )
    return pd.DataFrame(rows)


def axis_summary(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    raw = table[table["method"] == "raw_cfd20_pair_centered"]
    for axis, group in raw.groupby("axis"):
        if group.empty:
            continue
        worst = group.sort_values(["tail_frac_abs_gt5ns", "full_rms_ns"], ascending=False).iloc[0]
        best = group.sort_values(["tail_frac_abs_gt5ns", "full_rms_ns"], ascending=True).iloc[0]
        rows.append(
            {
                "axis": axis,
                "worst_stratum": worst["stratum"],
                "worst_tail_frac": float(worst["tail_frac_abs_gt5ns"]),
                "worst_sigma68_ns": float(worst["sigma68_ns"]),
                "best_stratum": best["stratum"],
                "best_tail_frac": float(best["tail_frac_abs_gt5ns"]),
                "tail_frac_range": float(worst["tail_frac_abs_gt5ns"] - best["tail_frac_abs_gt5ns"]),
                "sigma68_range_ns": float(worst["sigma68_ns"] - best["sigma68_ns"]),
            }
        )
    return pd.DataFrame(rows).sort_values("tail_frac_range", ascending=False)


def heldout_by_run(oof: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for run, sub in oof.groupby("run"):
        for method, col in [
            ("raw_cfd20_pair_centered", "centered_train_residual_ns"),
            ("traditional_ridge_pathology", "residual_traditional_corrected_ns"),
            ("ml_rf_pathology", "residual_ml_corrected_ns"),
        ]:
            rows.append({"run": int(run), "method": method, **metric_summary(sub, col, config)})
    return pd.DataFrame(rows)


def leakage_checks(oof: pd.DataFrame, bench: pd.DataFrame, cv_summary: dict) -> pd.DataFrame:
    raw = bench[bench["method"] == "raw_cfd20_pair_centered"].iloc[0]
    ml = bench[bench["method"] == "ml_rf_pathology"].iloc[0]
    shuf = bench[bench["method"] == "ml_shuffled_target_control"].iloc[0]
    oracle = bench[bench["method"] == "ml_intentional_oracle"].iloc[0]
    forbidden = {"run", "event_id", "eventno", "evt", "residual_ns", "centered_residual_ns", TAIL_COL}
    feature_overlap = set(ML_FEATURES) & forbidden
    return pd.DataFrame(
        [
            {"check": "all_rows_have_run_heldout_oof_predictions", "value": int(np.isfinite(oof["residual_ml_corrected_ns"]).sum()), "pass": bool(np.isfinite(oof["residual_ml_corrected_ns"]).all())},
            {"check": "ml_features_exclude_identifiers_and_labels", "value": ",".join(sorted(feature_overlap)), "pass": len(feature_overlap) == 0},
            {"check": "shuffled_regression_not_better_than_actual_ml", "value": float(shuf["sigma68_ns"] - ml["sigma68_ns"]), "pass": bool(shuf["sigma68_ns"] >= ml["sigma68_ns"])},
            {"check": "intentional_oracle_is_obviously_leaky", "value": float(oracle["sigma68_ns"]), "pass": bool(oracle["sigma68_ns"] < ml["sigma68_ns"])},
            {"check": "row_cv_not_much_better_than_run_cv", "value": float(cv_summary["run_cv_ml_sigma68_ns"] - cv_summary["row_cv_ml_sigma68_ns"]), "pass": bool((cv_summary["run_cv_ml_sigma68_ns"] - cv_summary["row_cv_ml_sigma68_ns"]) < 1.0)},
            {"check": "tail_classifier_shuffled_auc_near_random", "value": float(cv_summary["tail_classifier_shuffled_auc_mean"]), "pass": bool(cv_summary["tail_classifier_shuffled_auc_mean"] < 0.65)},
            {"check": "actual_ml_improvement_under_one_ns", "value": float(raw["sigma68_ns"] - ml["sigma68_ns"]), "pass": bool((raw["sigma68_ns"] - ml["sigma68_ns"]) < 1.0)},
        ]
    )


def plot_outputs(out_dir: Path, bench: pd.DataFrame, axis: pd.DataFrame) -> None:
    shown = bench[~bench["method"].str.contains("oracle")].copy()
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(shown))
    ax.errorbar(
        x,
        shown["sigma68_ns"],
        yerr=[shown["sigma68_ns"] - shown["sigma68_ci_low"], shown["sigma68_ci_high"] - shown["sigma68_ns"]],
        fmt="o",
        capsize=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(shown["method"], rotation=25, ha="right")
    ax.set_ylabel("run-held-out sigma68 [ns]")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head_sigma68.png", dpi=150)
    plt.close(fig)

    top = axis.head(7).copy()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(np.arange(len(top)), top["tail_frac_range"])
    ax.set_xticks(np.arange(len(top)))
    ax.set_xticklabels(top["axis"], rotation=25, ha="right")
    ax.set_ylabel("raw tail-fraction range")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pathology_tail_ranges.png", dpi=150)
    plt.close(fig)


def markdown_table(df: pd.DataFrame, cols: List[str]) -> str:
    return df[cols].to_markdown(index=False)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    reproduction: pd.DataFrame,
    bench: pd.DataFrame,
    axis: pd.DataFrame,
    table: pd.DataFrame,
    leakage: pd.DataFrame,
    cv_summary: dict,
    result: dict,
) -> None:
    raw = bench[bench["method"] == "raw_cfd20_pair_centered"].iloc[0]
    trad = bench[bench["method"] == "traditional_ridge_pathology"].iloc[0]
    ml = bench[bench["method"] == "ml_rf_pathology"].iloc[0]
    top_axis = axis.iloc[0]
    top_rows = table[(table["axis"] == top_axis["axis"]) & (table["method"] == "raw_cfd20_pair_centered")].sort_values("tail_frac_abs_gt5ns", ascending=False).head(8)
    lines = [
        "# S04c: Pathology-Stratified Timing-Resolution Tail Table",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT `h101/HRDv` under `data/root/root`",
        "- **Split:** grouped by run; five OOF folds, then run-block/event bootstrap CIs",
        f"- **Config:** `{config_path}`",
        "",
        "## Reproduction First",
        "",
        "The first executable step rescans raw ROOT with the standard S00/S04 B-stave selection.",
        "",
        markdown_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## Methods",
        "",
        "Residuals use all-downstream B4/B6/B8 pair CFD20 timing after the 2 cm TOF correction. The tail cut is fixed at `|pair-centered residual| > 5 ns`.",
        "",
        "Traditional: the conventional S04 CFD20 pair-centered Gaussian-core/tail table, stratified by fixed pathology axes. A transparent Ridge pathology residual correction is included as a non-ML stress test, but it is not adopted if it worsens the conventional table.",
        "",
        "ML: RandomForest residual correction and sigmoid-calibrated RandomForest tail probability using waveform/pathology summaries only. Features exclude run, event identifiers, residuals, and tail labels.",
        "",
        "## Head-To-Head",
        "",
        markdown_table(
            bench[~bench["method"].str.contains("oracle")],
            ["method", "n_pair_residuals", "sigma68_ns", "sigma68_ci_low", "sigma68_ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "tail_ci_low", "tail_ci_high", "core_chi2_ndf", "pull_width_ml_tail_prob"],
        ),
        "",
        "## Pathology Axes",
        "",
        markdown_table(axis, ["axis", "worst_stratum", "worst_tail_frac", "best_stratum", "best_tail_frac", "tail_frac_range", "sigma68_range_ns"]),
        "",
        f"The largest raw tail separation is `{top_axis['axis']}`. Its raw strata are:",
        "",
        markdown_table(top_rows, ["stratum", "n_pair_residuals", "n_events", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "tail_ci_low", "tail_ci_high", "mean_ml_tail_probability"]),
        "",
        "## Leakage Checks",
        "",
        markdown_table(leakage, ["check", "value", "pass"]),
        "",
        "Run-vs-row CV sentinel: ML run-CV sigma68 `{:.3f} ns`, row-CV sigma68 `{:.3f} ns`; calibrated tail AP `{:.3f}`, Brier `{:.4f}`, shuffled AUC `{:.3f}`.".format(
            cv_summary["run_cv_ml_sigma68_ns"],
            cv_summary["row_cv_ml_sigma68_ns"],
            cv_summary["tail_classifier_ap_mean"],
            cv_summary["tail_classifier_brier_mean"],
            cv_summary["tail_classifier_shuffled_auc_mean"],
        ),
        "",
        "## Verdict",
        "",
        result["conclusion"],
        "",
        "The ML residual correction is not adopted as a new timing baseline here: it changes sigma68 by `{:.3f} ns` versus the traditional CFD20 table and `{:.3f} ns` versus the Ridge stress-test correction, while the pathology tail ranking is the more useful output.".format(
            raw["sigma68_ns"] - ml["sigma68_ns"],
            trad["sigma68_ns"] - ml["sigma68_ns"],
        ),
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s04c_1781018820_3826_39cd42b6_pathology_tail_table.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `pair_residuals_oof.csv.gz`, `head_to_head_benchmark.csv`, `pathology_tail_table.csv`, `axis_summary.csv`, `heldout_by_run.csv`, `ml_fold_diagnostics.csv`, `ml_tail_classifier_cv.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config_path = args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / config_path.name).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    reproduction = S04B.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    loader_config = analysis_config_for_loader(config)
    pulses = S16F.load_downstream_pulses(loader_config)
    S16F.add_cfd_times(pulses, loader_config)
    pairs = S16F.pair_table(pulses, config["timing"]["base_method"], loader_config, list(config["timing"]["analysis_runs"]))
    pairs = add_pathology_axes(pairs, config)
    pairs.to_csv(out_dir / "pair_residuals_raw.csv.gz", index=False)

    oof, folds, tail_cv, cv_summary = oof_models(pairs, config, rng)
    oof.to_csv(out_dir / "pair_residuals_oof.csv.gz", index=False)
    folds.to_csv(out_dir / "ml_fold_diagnostics.csv", index=False)
    tail_cv.to_csv(out_dir / "ml_tail_classifier_cv.csv", index=False)

    bench = benchmark_table(oof, config, rng)
    tail = pathology_tail_table(oof, config, rng)
    axis = axis_summary(tail)
    by_run = heldout_by_run(oof, config)
    checks = leakage_checks(oof, bench, cv_summary)
    bench.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    tail.to_csv(out_dir / "pathology_tail_table.csv", index=False)
    axis.to_csv(out_dir / "axis_summary.csv", index=False)
    by_run.to_csv(out_dir / "heldout_by_run.csv", index=False)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.DataFrame([cv_summary]).to_csv(out_dir / "ml_summary.csv", index=False)
    plot_outputs(out_dir, bench, axis)

    input_rows = []
    for run in S04B.configured_runs(config):
        path = S04B.raw_file(config, int(run))
        input_rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    raw = bench[bench["method"] == "raw_cfd20_pair_centered"].iloc[0]
    trad = bench[bench["method"] == "traditional_ridge_pathology"].iloc[0]
    ml = bench[bench["method"] == "ml_rf_pathology"].iloc[0]
    top_axis = axis.iloc[0]
    conclusion = (
        "The non-core timing tails are dominated by fixed morphology/pathology atoms rather than by a single correctable timing model. "
        f"The strongest separator is {top_axis['axis']} ({top_axis['worst_stratum']} tail fraction {top_axis['worst_tail_frac']:.3f} versus {top_axis['best_stratum']} {top_axis['best_tail_frac']:.3f}). "
        f"The conventional CFD20 S04 table gives sigma68 {raw['sigma68_ns']:.3f} ns, the transparent Ridge stress test gives {trad['sigma68_ns']:.3f} ns, and ML gives {ml['sigma68_ns']:.3f} ns. S04 consumers should use the stratum table as a veto/uncertainty ledger, not replace the timing correction solely from this ML gain."
    )
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "raw_root_reproduction": {
            "total_selected_pulses": int(reproduction[reproduction["quantity"] == "total selected B-stave pulses"]["reproduced"].iloc[0]),
            "pass": bool(reproduction["pass"].all()),
        },
        "split": {
            "unit": "run",
            "runs": [int(r) for r in config["timing"]["analysis_runs"]],
            "folds": int(config["ml"]["cv_folds"]),
            "bootstrap_unit": "run_then_event",
        },
        "baseline": {
            "method": "raw_cfd20_pair_centered",
            "sigma68_ns": float(raw["sigma68_ns"]),
            "ci": [float(raw["sigma68_ci_low"]), float(raw["sigma68_ci_high"])],
            "full_rms_ns": float(raw["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(raw["tail_frac_abs_gt5ns"]),
            "core_chi2_ndf": float(raw["core_chi2_ndf"]),
        },
        "traditional": {
            "method": "conventional CFD20 pair-centered S04 pathology table",
            "sigma68_ns": float(raw["sigma68_ns"]),
            "ci": [float(raw["sigma68_ci_low"]), float(raw["sigma68_ci_high"])],
            "full_rms_ns": float(raw["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(raw["tail_frac_abs_gt5ns"]),
            "core_chi2_ndf": float(raw["core_chi2_ndf"]),
        },
        "traditional_ridge_stress_test": {
            "method": "run-held-out Ridge pathology residual correction",
            "sigma68_ns": float(trad["sigma68_ns"]),
            "ci": [float(trad["sigma68_ci_low"]), float(trad["sigma68_ci_high"])],
            "full_rms_ns": float(trad["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(trad["tail_frac_abs_gt5ns"]),
            "gain_vs_conventional_cfd20_ns": float(raw["sigma68_ns"] - trad["sigma68_ns"]),
        },
        "ml": {
            "method": "run-held-out RF pathology residual and calibrated tail model",
            "sigma68_ns": float(ml["sigma68_ns"]),
            "ci": [float(ml["sigma68_ci_low"]), float(ml["sigma68_ci_high"])],
            "full_rms_ns": float(ml["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(ml["tail_frac_abs_gt5ns"]),
            "gain_vs_raw_ns": float(raw["sigma68_ns"] - ml["sigma68_ns"]),
            "tail_classifier_auc": float(cv_summary["tail_classifier_auc_mean"]),
            "tail_classifier_average_precision": float(cv_summary["tail_classifier_ap_mean"]),
            "tail_classifier_brier": float(cv_summary["tail_classifier_brier_mean"]),
        },
        "pathology": {
            "top_axis": str(top_axis["axis"]),
            "worst_stratum": str(top_axis["worst_stratum"]),
            "worst_tail_frac": float(top_axis["worst_tail_frac"]),
            "best_stratum": str(top_axis["best_stratum"]),
            "best_tail_frac": float(top_axis["best_tail_frac"]),
            "tail_frac_range": float(top_axis["tail_frac_range"]),
        },
        "leakage_checks_pass": bool(checks["pass"].all()),
        "conclusion": conclusion,
        "input_sha256": hashlib.sha256("".join(row["sha256"] for row in input_rows).encode("ascii")).hexdigest(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, config_path, config, reproduction, bench, axis, tail, checks, cv_summary, result)
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": " ".join([sys.executable] + sys.argv),
        "config": str(config_path),
        "runtime_sec": round(time.time() - t0, 2),
        "input_sha256": input_rows,
        "output_sha256": output_hashes(out_dir),
        "ml_features": ML_FEATURES,
        "traditional_features": TRAD_FEATURES,
        "pathology_axes": PATHOLOGY_AXES,
        "random_seed": int(config["ml"]["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "raw_sigma68": float(raw["sigma68_ns"]), "traditional_sigma68": float(trad["sigma68_ns"]), "ml_sigma68": float(ml["sigma68_ns"]), "top_axis": str(top_axis["axis"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
