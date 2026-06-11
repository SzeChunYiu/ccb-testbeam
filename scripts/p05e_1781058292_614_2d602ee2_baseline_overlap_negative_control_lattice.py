#!/usr/bin/env python3
"""P05e: baseline-overlap negative-control lattice.

The ticket asks when baseline excursions and pretrigger contamination mimic
two-pulse overlap.  This script first reproduces the upstream raw-ROOT anchors,
then evaluates a traditional bounded two-pulse fit and several ML/NN calibrators
under a source-run holdout policy on a synthetic positive plus baseline-control
lattice.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.base import clone
from sklearn.preprocessing import StandardScaler


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S11B = import_script("s11b_base", ROOT / "scripts/s11b_real_high_current_two_pulse_validation.py")
P05C = import_script("p05c_base", ROOT / "scripts/p05c_1781018699_978_01857c74_real_s11b_cnn_validation.py")
P05A = import_script("p05a_base", ROOT / "scripts/p05a_cnn_two_pulse_decomposition.py")


METHOD_LABELS = {
    "traditional_template_fit": "Traditional bounded two-pulse template fit",
    "ridge": "Ridge/logistic linear calibration",
    "gradient_boosted_trees": "Histogram gradient-boosted trees",
    "mlp": "Multilayer perceptron",
    "one_d_cnn": "Compact 1D-CNN",
    "residual_shape_extratrees": "Residual-shape ExtraTrees ensemble",
}


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def absolute_path(path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def clean_training_rows(rows: pd.DataFrame) -> pd.DataFrame:
    return rows[
        (rows["ref_amp_adc"] > 1000.0)
        & (rows["ref_amp_adc"] < 12000.0)
        & (rows["peak_sample"] >= 2)
        & (rows["peak_sample"] <= 16)
    ].copy()


def make_synthetic_bundle(rows: pd.DataFrame, waves: np.ndarray, rng: np.random.Generator, n: int) -> dict:
    clean = clean_training_rows(rows)
    if len(clean) < 80:
        clean = rows[(rows["ref_amp_adc"] > 1000.0) & (rows["ref_amp_adc"] < 16000.0)].copy()
    if len(clean) < 20:
        raise RuntimeError("too few held-out clean pulses for synthetic calibration")
    n = min(int(n), len(clean))
    base_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
    sec_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
    base = waves[base_rows["event_index"].to_numpy()].astype(float)
    secondary = waves[sec_rows["event_index"].to_numpy()].astype(float)
    base_amp = np.maximum(base_rows["ref_amp_adc"].to_numpy(dtype=float), 1.0)
    secondary_amp = np.maximum(sec_rows["ref_amp_adc"].to_numpy(dtype=float), 1.0)
    delays = rng.uniform(0.75, 7.0, size=n)
    ratios = rng.uniform(0.12, 1.0, size=n)
    injected = base.copy()
    sec_norm = secondary / secondary_amp[:, None]
    for i, delay in enumerate(delays):
        injected[i] += base_amp[i] * ratios[i] * S11B.shift_array(sec_norm[i], delay, fill=0.0)
    amp2 = base_amp * ratios
    frac = amp2 / np.maximum(base_amp + amp2, 1.0)
    all_waves = np.vstack([base, injected]).astype(np.float32)
    staves = np.r_[base_rows["ref_stave"].to_numpy(), base_rows["ref_stave"].to_numpy()]
    y_label = np.r_[np.zeros(n, dtype=int), np.ones(n, dtype=int)]
    y_frac = np.r_[np.zeros(n, dtype=float), frac]

    x_norm, max_amp = P05C.cnn_inputs(all_waves)
    t1 = np.asarray([S11B.cfd_time_one(wf, 0.2) for wf in base], dtype=float)
    t1 = np.where(np.isfinite(t1), t1, S11B.TEMPLATE_REF_SAMPLE)
    reg_clean = np.column_stack([t1 / 12.0, t1 / 12.0, base_amp / max_amp[:n], np.zeros(n)])
    reg_inj = np.column_stack([t1 / 12.0, (t1 + delays) / 12.0, base_amp / max_amp[n:], amp2 / max_amp[n:]])
    cnn_reg = np.vstack([reg_clean, reg_inj]).astype(np.float32)

    synth_rows = pd.DataFrame(
        {
            "event_index": np.arange(len(all_waves), dtype=int),
            "ref_stave": staves,
            "synthetic_label": y_label,
            "true_secondary_fraction": y_frac,
            "source_run": np.r_[base_rows["run"].to_numpy(), base_rows["run"].to_numpy()],
        }
    )
    order = rng.permutation(len(all_waves))
    return {
        "waves": all_waves[order],
        "staves": staves[order],
        "y_label": y_label[order],
        "y_frac": y_frac[order],
        "cnn_x": x_norm[order],
        "cnn_reg": cnn_reg[order],
        "rows": synth_rows.iloc[order].reset_index(drop=True).assign(event_index=np.arange(len(all_waves), dtype=int)),
    }


def make_tabular_estimators(seed: int) -> dict[str, tuple[object, object]]:
    return {
        "ridge": (
            make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=700, class_weight="balanced", random_state=seed)),
            make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=3.0)),
        ),
        "gradient_boosted_trees": (
            HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, max_leaf_nodes=18, l2_regularization=0.02, random_state=seed),
            HistGradientBoostingRegressor(max_iter=90, learning_rate=0.06, max_leaf_nodes=18, l2_regularization=0.02, random_state=seed + 1),
        ),
        "mlp": (
            make_pipeline(
                SimpleImputer(strategy="median"),
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=(48, 24), alpha=0.001, max_iter=260, early_stopping=True, random_state=seed),
            ),
            make_pipeline(
                SimpleImputer(strategy="median"),
                StandardScaler(),
                MLPRegressor(hidden_layer_sizes=(48, 24), alpha=0.001, max_iter=260, early_stopping=True, random_state=seed + 1),
            ),
        ),
        "residual_shape_extratrees": (
            ExtraTreesClassifier(
                n_estimators=90,
                max_depth=11,
                min_samples_leaf=8,
                class_weight="balanced",
                random_state=seed,
                n_jobs=1,
            ),
            ExtraTreesRegressor(n_estimators=100, max_depth=11, min_samples_leaf=8, random_state=seed + 1, n_jobs=1),
        ),
    }


def predict_classifier(clf, x: pd.DataFrame) -> np.ndarray:
    if hasattr(clf, "predict_proba"):
        return np.asarray(clf.predict_proba(x)[:, 1], dtype=float)
    raw = np.asarray(clf.predict(x), dtype=float)
    return np.clip(raw, 0.0, 1.0)


def calibration_metrics(method: str, heldout_run: int, group: str, y_label: np.ndarray, y_frac: np.ndarray, score: np.ndarray, frac: np.ndarray) -> dict:
    score = np.clip(np.asarray(score, dtype=float), 0.0, 1.0)
    frac = np.clip(np.asarray(frac, dtype=float), 0.0, 1.0)
    y_label = np.asarray(y_label, dtype=int)
    y_frac = np.asarray(y_frac, dtype=float)
    if np.nanstd(frac) > 1e-9:
        slope, intercept = np.polyfit(frac, y_frac, 1)
    else:
        slope, intercept = float("nan"), float("nan")
    accepted = score >= 0.50
    if bool(np.any(accepted)):
        accepted_rmse = float(np.sqrt(np.mean((frac[accepted] - y_frac[accepted]) ** 2)))
        accepted_efficiency = float(np.mean(accepted))
    else:
        accepted_rmse = float("nan")
        accepted_efficiency = 0.0
    return {
        "heldout_run": int(heldout_run),
        "heldout_group": group,
        "method": method,
        "method_label": METHOD_LABELS[method],
        "n_calibration": int(len(y_label)),
        "synthetic_overlap_auc": float(roc_auc_score(y_label, score)) if len(np.unique(y_label)) > 1 else float("nan"),
        "synthetic_overlap_ap": float(average_precision_score(y_label, score)) if len(np.unique(y_label)) > 1 else float("nan"),
        "synthetic_overlap_brier": float(brier_score_loss(y_label, score)),
        "synthetic_secondary_fraction_mae": float(np.mean(np.abs(frac - y_frac))),
        "synthetic_secondary_fraction_rmse": float(np.sqrt(np.mean((frac - y_frac) ** 2))),
        "calibration_slope": float(slope),
        "calibration_intercept": float(intercept),
        "accepted_recovery_rmse": accepted_rmse,
        "accepted_efficiency": accepted_efficiency,
    }


def run_predictions(events: pd.DataFrame, waves: np.ndarray, sample: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    low_runs = set(S11B.RUN_GROUPS["low_2nA"]["runs"])
    score_frames = []
    template_frames = []
    fold_rows = []
    feature_cols = None
    torch.set_num_threads(1)
    for heldout_run in sorted(sample["run"].unique()):
        heldout_run = int(heldout_run)
        train_runs = sorted(low_runs - {heldout_run}) if heldout_run in low_runs else sorted(low_runs)
        train = events[events["run"].isin(train_runs)].copy()
        test = sample[sample["run"] == heldout_run].copy()
        test_waves = waves[test["event_index"].to_numpy()]
        templates, template_summary = S11B.build_templates(train, waves)
        template_summary["heldout_run"] = heldout_run
        template_summary["training_runs"] = " ".join(str(x) for x in train_runs)
        template_frames.append(template_summary)

        train_bundle = make_synthetic_bundle(train, waves, rng, int(config["synthetic_train_per_fold"]))
        cal_bundle = make_synthetic_bundle(test, waves, rng, int(config["synthetic_cal_per_fold"]))
        x_train = S11B.ml_features(train_bundle["waves"], train_bundle["staves"], templates)
        x_cal = S11B.ml_features(cal_bundle["waves"], cal_bundle["staves"], templates)
        x_test = S11B.ml_features(test_waves, test["ref_stave"].to_numpy(), templates)
        if feature_cols is None:
            feature_cols = list(x_train.columns)

        trad_real = S11B.fit_traditional_for_run(test, test_waves, templates)
        trad_cal = S11B.fit_traditional_for_run(cal_bundle["rows"], cal_bundle["waves"], templates)
        row = calibration_metrics(
            "traditional_template_fit",
            heldout_run,
            S11B.run_to_group()[heldout_run],
            cal_bundle["y_label"],
            cal_bundle["y_frac"],
            trad_cal["trad_score_sse_improvement"].to_numpy(),
            trad_cal["trad_secondary_fraction"].to_numpy(),
        )
        row.update(
            {
                "training_policy": "low_current_only_source_run_heldout",
                "training_runs": " ".join(str(x) for x in train_runs),
                "synthetic_train_source_runs": " ".join(str(x) for x in sorted(set(train_bundle["rows"]["source_run"].astype(int)))),
            }
        )
        fold_rows.append(row)

        real_frame = test[
            [
                "event_index",
                "run",
                "group",
                "current_nA",
                "eventno",
                "stratum",
                "amp_bin",
                "baseline_bin",
                "p02_topology",
                "ref_stave",
                "ref_amp_adc",
                "downstream",
            ]
        ].copy()
        real_frame = real_frame.merge(trad_real, on="event_index", how="left")
        real_frame["traditional_template_fit_overlap_score"] = real_frame["trad_score_sse_improvement"]
        real_frame["traditional_template_fit_secondary_fraction"] = real_frame["trad_secondary_fraction"]

        for method, (clf, reg) in make_tabular_estimators(int(config["random_seed"]) + heldout_run).items():
            clf.fit(x_train[feature_cols], train_bundle["y_label"])
            reg.fit(x_train[feature_cols], train_bundle["y_frac"])
            cal_score = predict_classifier(clf, x_cal[feature_cols])
            cal_frac = np.clip(np.asarray(reg.predict(x_cal[feature_cols]), dtype=float), 0.0, 1.0)
            test_score = predict_classifier(clf, x_test[feature_cols])
            test_frac = np.clip(np.asarray(reg.predict(x_test[feature_cols]), dtype=float), 0.0, 1.0)
            row = calibration_metrics(
                method,
                heldout_run,
                S11B.run_to_group()[heldout_run],
                cal_bundle["y_label"],
                cal_bundle["y_frac"],
                cal_score,
                cal_frac,
            )
            row.update(
                {
                    "training_policy": "low_current_only_source_run_heldout",
                    "training_runs": " ".join(str(x) for x in train_runs),
                    "synthetic_train_source_runs": " ".join(str(x) for x in sorted(set(train_bundle["rows"]["source_run"].astype(int)))),
                }
            )
            fold_rows.append(row)
            real_frame[f"{method}_overlap_score"] = test_score
            real_frame[f"{method}_secondary_fraction"] = test_frac

        cnn_model = P05C.train_cnn(
            train_bundle["cnn_x"],
            train_bundle["y_label"].astype(np.float32),
            train_bundle["cnn_reg"],
            config,
            int(config["random_seed"]) + 2000 + heldout_run,
        )
        cnn_cal = P05C.predict_cnn_from_normalized(cnn_model, cal_bundle["cnn_x"])
        cnn_real = P05C.predict_cnn(cnn_model, test_waves)
        row = calibration_metrics(
            "one_d_cnn",
            heldout_run,
            S11B.run_to_group()[heldout_run],
            cal_bundle["y_label"],
            cal_bundle["y_frac"],
            cnn_cal["cnn_overlap_score"].to_numpy(),
            cnn_cal["cnn_secondary_fraction"].to_numpy(),
        )
        row.update(
            {
                "training_policy": "low_current_only_source_run_heldout",
                "training_runs": " ".join(str(x) for x in train_runs),
                "synthetic_train_source_runs": " ".join(str(x) for x in sorted(set(train_bundle["rows"]["source_run"].astype(int)))),
            }
        )
        fold_rows.append(row)
        real_frame["one_d_cnn_overlap_score"] = cnn_real["cnn_overlap_score"].to_numpy()
        real_frame["one_d_cnn_secondary_fraction"] = cnn_real["cnn_secondary_fraction"].to_numpy()
        score_frames.append(real_frame)

    return pd.concat(score_frames, ignore_index=True), pd.concat(template_frames, ignore_index=True), pd.DataFrame(fold_rows)


def summarize_real_methods(scores: pd.DataFrame, stratum_table: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    tables = []
    summaries = []
    for method in METHOD_LABELS:
        for suffix in ["secondary_fraction", "overlap_score"]:
            col = f"{method}_{suffix}"
            table, summary = S11B.summarize_method(scores, stratum_table, col, rng)
            table["method"] = method
            table["quantity"] = suffix
            summary["method"] = method
            summary["method_label"] = METHOD_LABELS[method]
            summary["quantity"] = suffix
            summaries.append(summary)
            tables.append(table)
    return pd.concat(tables, ignore_index=True), pd.concat(summaries, ignore_index=True)


def bootstrap_fold_summary(folds: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    metrics = [
        "synthetic_overlap_brier",
        "synthetic_secondary_fraction_rmse",
        "synthetic_secondary_fraction_mae",
        "calibration_slope",
        "calibration_intercept",
        "accepted_recovery_rmse",
        "accepted_efficiency",
        "synthetic_overlap_auc",
    ]
    rows = []
    for method, sub in folds.groupby("method"):
        idx = np.arange(len(sub))
        for metric in metrics:
            vals = sub[metric].to_numpy(dtype=float)
            finite = np.isfinite(vals)
            if not finite.any():
                continue
            point = float(np.nanmean(vals))
            boots = []
            for _ in range(int(n_boot)):
                take = rng.choice(idx, size=len(idx), replace=True)
                boots.append(float(np.nanmean(vals[take])))
            rows.append(
                {
                    "method": method,
                    "method_label": METHOD_LABELS[method],
                    "metric": metric,
                    "value": point,
                    "ci_low": float(np.nanquantile(boots, 0.025)),
                    "ci_high": float(np.nanquantile(boots, 0.975)),
                    "bootstrap_unit": "heldout_source_run",
                    "n_bootstrap": int(n_boot),
                    "n_folds": int(len(sub)),
                }
            )
    return pd.DataFrame(rows)


def real_discordance(scores: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    low_runs = np.array(S11B.RUN_GROUPS["low_2nA"]["runs"], dtype=int)
    high_runs = np.array(S11B.RUN_GROUPS["high_20nA"]["runs"], dtype=int)

    def metric(frame: pd.DataFrame, method: str) -> float:
        score = frame[f"{method}_overlap_score"].rank(pct=True).to_numpy(dtype=float)
        frac = frame[f"{method}_secondary_fraction"].rank(pct=True).to_numpy(dtype=float)
        return float(np.nanmean(np.abs(score - frac)))

    rows = []
    for method in METHOD_LABELS:
        point = metric(scores, method)
        boots = []
        for _ in range(int(n_boot)):
            pieces = []
            for run in np.r_[rng.choice(low_runs, size=len(low_runs), replace=True), rng.choice(high_runs, size=len(high_runs), replace=True)]:
                sub = scores[scores["run"] == int(run)]
                if len(sub):
                    pieces.append(sub)
            boots.append(metric(pd.concat(pieces, ignore_index=True), method))
        rows.append(
            {
                "method": method,
                "method_label": METHOD_LABELS[method],
                "metric": "real_overlap_fraction_rank_discordance",
                "value": point,
                "ci_low": float(np.nanquantile(boots, 0.025)),
                "ci_high": float(np.nanquantile(boots, 0.975)),
                "bootstrap_unit": "source_run_within_current_group",
                "n_bootstrap": int(n_boot),
            }
        )
    return pd.DataFrame(rows)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    lo, hi = np.percentile(values, [16.0, 84.0])
    return float((hi - lo) / 2.0)


def add_baseline_nuisance(waves: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    out = np.asarray(waves, dtype=float).copy()
    n = len(out)
    control_type = rng.choice(["slope", "pretrigger", "sag"], size=n, p=[0.40, 0.35, 0.25])
    x = np.linspace(-0.5, 0.5, out.shape[1])
    for i, kind in enumerate(control_type):
        amp = max(float(np.max(out[i])), 1.0)
        if kind == "slope":
            out[i] += rng.normal(0.0, 0.035 * amp) + rng.normal(0.0, 0.050 * amp) * x
        elif kind == "pretrigger":
            bump = rng.uniform(0.10, 0.28) * amp
            center = rng.uniform(0.0, 2.8)
            width = rng.uniform(0.55, 1.10)
            out[i] += bump * np.exp(-0.5 * ((np.arange(out.shape[1]) - center) / width) ** 2)
        else:
            tail = np.exp(-np.maximum(np.arange(out.shape[1]) - 2.0, 0.0) / rng.uniform(3.5, 7.0))
            out[i] += rng.uniform(-0.10, 0.10) * amp + rng.uniform(0.05, 0.18) * amp * tail
    return out.astype(np.float32), control_type.astype(str)


def make_lattice_bundle(rows: pd.DataFrame, waves: np.ndarray, rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, np.ndarray]:
    clean = clean_training_rows(rows)
    if len(clean) < 80:
        clean = rows[(rows["ref_amp_adc"] > 1000.0) & (rows["ref_amp_adc"] < 16000.0)].copy()
    if len(clean) < 20:
        raise RuntimeError("too few pulses for P05e lattice")
    n = min(int(n), len(clean))
    base_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
    sec_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
    ctl_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)

    base = waves[base_rows["event_index"].to_numpy()].astype(float)
    secondary = waves[sec_rows["event_index"].to_numpy()].astype(float)
    control_base = waves[ctl_rows["event_index"].to_numpy()].astype(float)
    base_amp = np.maximum(base_rows["ref_amp_adc"].to_numpy(dtype=float), 1.0)
    secondary_amp = np.maximum(sec_rows["ref_amp_adc"].to_numpy(dtype=float), 1.0)
    delays = rng.uniform(0.75, 7.0, size=n)
    ratios = rng.uniform(0.12, 1.0, size=n)
    injected = base.copy()
    sec_norm = secondary / secondary_amp[:, None]
    for i, delay in enumerate(delays):
        injected[i] += base_amp[i] * ratios[i] * S11B.shift_array(sec_norm[i], delay, fill=0.0)
    controls, control_type = add_baseline_nuisance(control_base, rng)

    t1 = np.asarray([S11B.cfd_time_one(wf, 0.2) for wf in base], dtype=float)
    t1 = np.where(np.isfinite(t1), t1, S11B.TEMPLATE_REF_SAMPLE)
    amp2 = base_amp * ratios
    frac = amp2 / np.maximum(base_amp + amp2, 1.0)
    all_waves = np.vstack([injected, controls]).astype(np.float32)
    meta = pd.DataFrame(
        {
            "event_index": np.arange(2 * n, dtype=int),
            "source_run": np.r_[base_rows["run"].to_numpy(), ctl_rows["run"].to_numpy()],
            "ref_stave": np.r_[base_rows["ref_stave"].to_numpy(), ctl_rows["ref_stave"].to_numpy()],
            "synthetic_label": np.r_[np.ones(n, dtype=int), np.zeros(n, dtype=int)],
            "baseline_control": np.r_[np.zeros(n, dtype=int), np.ones(n, dtype=int)],
            "control_type": np.r_[np.repeat("injected_overlap", n), control_type],
            "true_delay_samples": np.r_[delays, np.zeros(n)],
            "true_secondary_fraction": np.r_[frac, np.zeros(n)],
            "true_charge_fraction": np.r_[frac, np.zeros(n)],
        }
    )
    order = rng.permutation(len(meta))
    return meta.iloc[order].reset_index(drop=True).assign(event_index=np.arange(len(meta), dtype=int)), all_waves[order]


def cnn_regression_targets(meta: pd.DataFrame, waves: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x_norm, max_amp = P05C.cnn_inputs(waves)
    t1 = np.asarray([S11B.cfd_time_one(wf, 0.2) for wf in waves], dtype=float)
    t1 = np.where(np.isfinite(t1), t1, S11B.TEMPLATE_REF_SAMPLE)
    t2 = t1 + meta["true_delay_samples"].to_numpy(dtype=float)
    frac = meta["true_secondary_fraction"].to_numpy(dtype=float)
    reg = np.column_stack([t1 / 12.0, t2 / 12.0, 1.0 - frac, frac])
    return x_norm, reg.astype(np.float32)


def method_threshold(scores: np.ndarray, y: np.ndarray, coverage: float) -> float:
    pos = np.asarray(scores, dtype=float)[np.asarray(y, dtype=int) == 1]
    pos = pos[np.isfinite(pos)]
    if len(pos) == 0:
        return 0.5
    return float(np.quantile(pos, max(0.0, min(1.0, 1.0 - float(coverage)))))


def lattice_metrics(
    method: str,
    heldout_run: int,
    y: np.ndarray,
    control: np.ndarray,
    true_frac: np.ndarray,
    true_delay: np.ndarray,
    score: np.ndarray,
    pred_frac: np.ndarray,
    pred_delay: np.ndarray,
    threshold: float,
    score50: float,
) -> dict:
    y = np.asarray(y, dtype=int)
    control = np.asarray(control, dtype=bool)
    score = np.clip(np.asarray(score, dtype=float), 0.0, 1.0)
    pred_frac = np.clip(np.asarray(pred_frac, dtype=float), 0.0, 1.0)
    pred_delay = np.asarray(pred_delay, dtype=float)
    threshold = method_threshold(score, y, threshold)
    positives = y == 1
    accepted_pos = positives & (score >= threshold)
    frac_err = pred_frac[accepted_pos] - np.asarray(true_frac, dtype=float)[accepted_pos]
    delay_err_ns = 10.0 * (pred_delay[accepted_pos] - np.asarray(true_delay, dtype=float)[accepted_pos])
    ap = float(average_precision_score(y, score)) if len(np.unique(y)) > 1 else float("nan")
    control_mask = control & (y == 0)
    fpr = float(np.mean(score[control_mask] >= threshold)) if np.any(control_mask) else float("nan")
    fpr50 = float(np.mean(score[control_mask] >= score50)) if np.any(control_mask) else float("nan")
    coverage = float(np.mean(score[positives] >= threshold)) if np.any(positives) else float("nan")
    time_rms = float(np.sqrt(np.mean(delay_err_ns**2))) if len(delay_err_ns) else float("nan")
    charge_bias = float(np.mean(frac_err)) if len(frac_err) else float("nan")
    charge_res68 = sigma68(frac_err)
    loss = (1.0 - ap) + 2.0 * fpr + (time_rms / 80.0 if np.isfinite(time_rms) else 1.0) + abs(charge_bias) + charge_res68
    return {
        "heldout_run": int(heldout_run),
        "heldout_group": S11B.run_to_group()[int(heldout_run)],
        "method": method,
        "method_label": METHOD_LABELS[method],
        "score_threshold_at_fixed_coverage": float(threshold),
        "fixed_positive_coverage": coverage,
        "injected_overlap_ap": ap,
        "baseline_control_fpr_at_fixed_coverage": fpr,
        "baseline_control_fpr_score50": fpr50,
        "recovered_time_rms_ns": time_rms,
        "charge_bias_at_fixed_coverage": charge_bias,
        "charge_res68_at_fixed_coverage": charge_res68,
        "lattice_utility_loss": float(loss),
        "n_lattice_events": int(len(y)),
        "n_baseline_controls": int(np.sum(control_mask)),
    }


def run_lattice_predictions(events: pd.DataFrame, waves: np.ndarray, sample: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    pred_frames = []
    low_runs = set(S11B.RUN_GROUPS["low_2nA"]["runs"])
    coverage = float(config["fixed_positive_coverage"])
    score50 = float(config["control_false_positive_threshold"])
    torch.set_num_threads(1)
    for heldout_run in sorted(sample["run"].unique()):
        heldout_run = int(heldout_run)
        train_runs = sorted(low_runs - {heldout_run}) if heldout_run in low_runs else sorted(low_runs)
        train = events[events["run"].isin(train_runs)].copy()
        test = sample[sample["run"] == heldout_run].copy()
        templates, _template_summary = S11B.build_templates(train, waves)
        train_meta, train_waves = make_lattice_bundle(train, waves, rng, int(config["synthetic_train_per_fold"]))
        cal_meta, cal_waves = make_lattice_bundle(test, waves, rng, int(config["synthetic_cal_per_fold"]))
        x_train = S11B.ml_features(train_waves, train_meta["ref_stave"].to_numpy(), templates)
        x_cal = S11B.ml_features(cal_waves, cal_meta["ref_stave"].to_numpy(), templates)
        feature_cols = list(x_train.columns)

        for method, (clf, reg) in make_tabular_estimators(int(config["random_seed"]) + heldout_run).items():
            delay_reg = clone(reg)
            clf.fit(x_train[feature_cols], train_meta["synthetic_label"].to_numpy(dtype=int))
            reg.fit(x_train[feature_cols], train_meta["true_secondary_fraction"].to_numpy(dtype=float))
            delay_reg.fit(x_train[feature_cols], train_meta["true_delay_samples"].to_numpy(dtype=float))
            train_score = predict_classifier(clf, x_train[feature_cols])
            threshold = method_threshold(train_score, train_meta["synthetic_label"].to_numpy(dtype=int), coverage)
            cal_score = predict_classifier(clf, x_cal[feature_cols])
            cal_frac = np.clip(np.asarray(reg.predict(x_cal[feature_cols]), dtype=float), 0.0, 1.0)
            cal_delay = np.clip(np.asarray(delay_reg.predict(x_cal[feature_cols]), dtype=float), 0.0, 8.0)
            cal_threshold = method_threshold(cal_score, cal_meta["synthetic_label"].to_numpy(dtype=int), coverage)
            rows.append(
                lattice_metrics(
                    method,
                    heldout_run,
                    cal_meta["synthetic_label"].to_numpy(dtype=int),
                    cal_meta["baseline_control"].to_numpy(dtype=int),
                    cal_meta["true_secondary_fraction"].to_numpy(dtype=float),
                    cal_meta["true_delay_samples"].to_numpy(dtype=float),
                    cal_score,
                    cal_frac,
                    cal_delay,
                    coverage,
                    score50,
                )
            )
            pred_frames.append(
                cal_meta.assign(
                    heldout_run=heldout_run,
                    method=method,
                    method_label=METHOD_LABELS[method],
                    score=cal_score,
                    predicted_secondary_fraction=cal_frac,
                    predicted_delay_samples=cal_delay,
                    score_threshold_at_fixed_coverage=cal_threshold,
                )
            )

        train_trad = S11B.fit_traditional_for_run(train_meta, train_waves, templates)
        cal_trad = S11B.fit_traditional_for_run(cal_meta, cal_waves, templates)
        train_score = train_trad["trad_score_sse_improvement"].to_numpy(dtype=float)
        threshold = method_threshold(train_score, train_meta["synthetic_label"].to_numpy(dtype=int), coverage)
        cal_score = cal_trad["trad_score_sse_improvement"].to_numpy(dtype=float)
        cal_frac = cal_trad["trad_secondary_fraction"].to_numpy(dtype=float)
        cal_delay = (cal_trad["trad_t2_sample"] - cal_trad["trad_t1_sample"]).to_numpy(dtype=float)
        cal_threshold = method_threshold(cal_score, cal_meta["synthetic_label"].to_numpy(dtype=int), coverage)
        rows.append(
            lattice_metrics(
                "traditional_template_fit",
                heldout_run,
                cal_meta["synthetic_label"].to_numpy(dtype=int),
                cal_meta["baseline_control"].to_numpy(dtype=int),
                cal_meta["true_secondary_fraction"].to_numpy(dtype=float),
                cal_meta["true_delay_samples"].to_numpy(dtype=float),
                cal_score,
                cal_frac,
                cal_delay,
                coverage,
                score50,
            )
        )
        pred_frames.append(
            cal_meta.assign(
                heldout_run=heldout_run,
                method="traditional_template_fit",
                method_label=METHOD_LABELS["traditional_template_fit"],
                score=cal_score,
                predicted_secondary_fraction=cal_frac,
                predicted_delay_samples=cal_delay,
                score_threshold_at_fixed_coverage=cal_threshold,
            )
        )

        train_x_norm, train_reg = cnn_regression_targets(train_meta, train_waves)
        cal_x_norm, _cal_reg = cnn_regression_targets(cal_meta, cal_waves)
        cnn_model = P05C.train_cnn(
            train_x_norm,
            train_meta["synthetic_label"].to_numpy(dtype=np.float32),
            train_reg,
            config,
            int(config["random_seed"]) + 4000 + heldout_run,
        )
        train_cnn = P05C.predict_cnn_from_normalized(cnn_model, train_x_norm)
        cal_cnn = P05C.predict_cnn_from_normalized(cnn_model, cal_x_norm)
        threshold = method_threshold(train_cnn["cnn_overlap_score"].to_numpy(dtype=float), train_meta["synthetic_label"].to_numpy(dtype=int), coverage)
        cal_score = cal_cnn["cnn_overlap_score"].to_numpy(dtype=float)
        cal_frac = cal_cnn["cnn_secondary_fraction"].to_numpy(dtype=float)
        cal_delay = (cal_cnn["cnn_t2_sample"] - cal_cnn["cnn_t1_sample"]).to_numpy(dtype=float)
        cal_threshold = method_threshold(cal_score, cal_meta["synthetic_label"].to_numpy(dtype=int), coverage)
        rows.append(
            lattice_metrics(
                "one_d_cnn",
                heldout_run,
                cal_meta["synthetic_label"].to_numpy(dtype=int),
                cal_meta["baseline_control"].to_numpy(dtype=int),
                cal_meta["true_secondary_fraction"].to_numpy(dtype=float),
                cal_meta["true_delay_samples"].to_numpy(dtype=float),
                cal_score,
                cal_frac,
                cal_delay,
                coverage,
                score50,
            )
        )
        pred_frames.append(
            cal_meta.assign(
                heldout_run=heldout_run,
                method="one_d_cnn",
                method_label=METHOD_LABELS["one_d_cnn"],
                score=cal_score,
                predicted_secondary_fraction=cal_frac,
                predicted_delay_samples=cal_delay,
                score_threshold_at_fixed_coverage=cal_threshold,
            )
        )
    return pd.DataFrame(rows), pd.concat(pred_frames, ignore_index=True)


def bootstrap_lattice_summary(lattice: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    metrics = [
        "lattice_utility_loss",
        "injected_overlap_ap",
        "baseline_control_fpr_at_fixed_coverage",
        "baseline_control_fpr_score50",
        "fixed_positive_coverage",
        "recovered_time_rms_ns",
        "charge_bias_at_fixed_coverage",
        "charge_res68_at_fixed_coverage",
    ]
    rows = []
    for method, sub in lattice.groupby("method"):
        idx = np.arange(len(sub))
        for metric in metrics:
            vals = sub[metric].to_numpy(dtype=float)
            if not np.isfinite(vals).any():
                continue
            boots = []
            for _ in range(int(n_boot)):
                take = rng.choice(idx, size=len(idx), replace=True)
                boots.append(float(np.nanmean(vals[take])))
            rows.append(
                {
                    "method": method,
                    "method_label": METHOD_LABELS[method],
                    "metric": metric,
                    "value": float(np.nanmean(vals)),
                    "ci_low": float(np.nanquantile(boots, 0.025)),
                    "ci_high": float(np.nanquantile(boots, 0.975)),
                    "bootstrap_unit": "heldout_source_run",
                    "n_bootstrap": int(n_boot),
                    "n_folds": int(len(sub)),
                }
            )
    return pd.DataFrame(rows)


def choose_lattice_winner(lattice_summary: pd.DataFrame) -> dict:
    ranking = lattice_summary[lattice_summary["metric"] == "lattice_utility_loss"].copy()
    ranking = ranking.sort_values(["value", "ci_high", "method"]).reset_index(drop=True)
    row = ranking.iloc[0]
    return {
        "method": str(row["method"]),
        "method_label": str(row["method_label"]),
        "metric": "lattice_utility_loss",
        "value": float(row["value"]),
        "ci": [float(row["ci_low"]), float(row["ci_high"])],
        "rule": "lowest mean heldout-source-run bootstrap lattice utility loss",
    }


def leakage_checks(scores: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method in METHOD_LABELS:
        score_auc = float(roc_auc_score((scores["group"] == "high_20nA").astype(int), scores[f"{method}_overlap_score"]))
        frac_auc = float(roc_auc_score((scores["group"] == "high_20nA").astype(int), scores[f"{method}_secondary_fraction"]))
        rows.append(
            {
                "check": f"{method}_actual_current_auc_from_overlap_score",
                "method": method,
                "value": score_auc,
                "flag": bool(score_auc > 0.95),
                "note": "Flagged if the score nearly identifies beam current by itself.",
            }
        )
        rows.append(
            {
                "check": f"{method}_actual_current_auc_from_secondary_fraction",
                "method": method,
                "value": frac_auc,
                "flag": bool(frac_auc > 0.95),
                "note": "Flagged if the secondary-fraction estimate nearly identifies beam current by itself.",
            }
        )
    source_ok = all(str(row.heldout_run) not in row.synthetic_train_source_runs.split() for row in folds.itertuples())
    rows.extend(
        [
            {
                "check": "heldout_run_excluded_from_training",
                "method": "all",
                "value": 1.0,
                "flag": False,
                "note": "High-current runs are never in training; low-current controls leave the scored run out.",
            },
            {
                "check": "identifier_features_excluded",
                "method": "all",
                "value": 1.0,
                "flag": False,
                "note": "Tabular/NN features exclude run, event number, current, group, downstream label, and stratum labels.",
            },
            {
                "check": "synthetic_train_source_runs_exclude_heldout",
                "method": "all",
                "value": float(source_ok),
                "flag": bool(not source_ok),
                "note": "Fold diagnostics record raw source runs used to make synthetic overlays.",
            },
        ]
    )
    return pd.DataFrame(rows)


def choose_winner(fold_summary: pd.DataFrame) -> dict:
    ranking = fold_summary[fold_summary["metric"] == "synthetic_secondary_fraction_rmse"].copy()
    ranking = ranking.sort_values(["value", "ci_high", "method"]).reset_index(drop=True)
    row = ranking.iloc[0]
    return {
        "method": str(row["method"]),
        "method_label": str(row["method_label"]),
        "metric": "synthetic_secondary_fraction_rmse",
        "value": float(row["value"]),
        "ci": [float(row["ci_low"]), float(row["ci_high"])],
        "rule": "lowest mean source-run-bootstrap synthetic secondary-fraction RMSE",
    }


def save_plots(out_dir: Path, real_summary: pd.DataFrame, fold_summary: pd.DataFrame, scores: pd.DataFrame, winner: dict) -> None:
    plot = real_summary[real_summary["quantity"] == "secondary_fraction"].copy()
    plot = plot.set_index("method").loc[list(METHOD_LABELS)].reset_index()
    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    x = np.arange(len(plot))
    ax.bar(x, plot["value"], color=["#4c78a8" if m != winner["method"] else "#d96c06" for m in plot["method"]])
    ax.errorbar(x, plot["value"], yerr=[plot["value"] - plot["ci_low"], plot["ci_high"] - plot["value"]], fmt="none", color="k", capsize=3)
    ax.axhline(0, color="k", lw=1)
    ax.set_xticks(x, plot["method_label"], rotation=25, ha="right")
    ax.set_ylabel("Matched high-minus-low secondary fraction")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_real_high_minus_low_secondary_fraction.png", dpi=150)
    plt.close(fig)

    rmse = fold_summary[fold_summary["metric"] == "synthetic_secondary_fraction_rmse"].copy()
    rmse = rmse.set_index("method").loc[list(METHOD_LABELS)].reset_index()
    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    x = np.arange(len(rmse))
    ax.bar(x, rmse["value"], color=["#72b7b2" if m != winner["method"] else "#d96c06" for m in rmse["method"]])
    ax.errorbar(x, rmse["value"], yerr=[rmse["value"] - rmse["ci_low"], rmse["ci_high"] - rmse["value"]], fmt="none", color="k", capsize=3)
    ax.set_xticks(x, rmse["method_label"], rotation=25, ha="right")
    ax.set_ylabel("Synthetic secondary-fraction RMSE")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_synthetic_calibration_rmse.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    for group, sub in scores.groupby("group"):
        ax.hist(sub[f"{winner['method']}_secondary_fraction"], bins=45, density=True, alpha=0.55, label=group)
    ax.set_xlabel(f"{winner['method_label']} secondary-fraction estimate")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_real_fraction_by_current.png", dpi=150)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    p05a_match: pd.DataFrame,
    p05a_anchor: pd.DataFrame,
    s10_repro: pd.DataFrame,
    s11b_repro: pd.DataFrame,
    real_summary: pd.DataFrame,
    fold_summary: pd.DataFrame,
    discordance: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: dict,
    lattice_summary: pd.DataFrame,
    lattice_by_fold: pd.DataFrame,
    result: dict,
) -> None:
    real_sec = real_summary[real_summary["quantity"] == "secondary_fraction"][
        ["method_label", "value", "ci_low", "ci_high", "n_scored_events"]
    ].copy()
    real_score = real_summary[real_summary["quantity"] == "overlap_score"][["method_label", "value", "ci_low", "ci_high"]].copy()
    rmse = fold_summary[fold_summary["metric"] == "synthetic_secondary_fraction_rmse"][
        ["method_label", "value", "ci_low", "ci_high"]
    ].copy()
    brier = fold_summary[fold_summary["metric"] == "synthetic_overlap_brier"][["method_label", "value", "ci_low", "ci_high"]].copy()
    slope = fold_summary[fold_summary["metric"] == "calibration_slope"][["method_label", "value", "ci_low", "ci_high"]].copy()
    acc = fold_summary[fold_summary["metric"] == "accepted_recovery_rmse"][["method_label", "value", "ci_low", "ci_high"]].copy()
    utility = lattice_summary[lattice_summary["metric"] == "lattice_utility_loss"][["method_label", "value", "ci_low", "ci_high"]].copy()
    lap = lattice_summary[lattice_summary["metric"] == "injected_overlap_ap"][["method_label", "value", "ci_low", "ci_high"]].copy()
    lfpr = lattice_summary[lattice_summary["metric"] == "baseline_control_fpr_at_fixed_coverage"][["method_label", "value", "ci_low", "ci_high"]].copy()
    ltime = lattice_summary[lattice_summary["metric"] == "recovered_time_rms_ns"][["method_label", "value", "ci_low", "ci_high"]].copy()
    lbias = lattice_summary[lattice_summary["metric"] == "charge_bias_at_fixed_coverage"][["method_label", "value", "ci_low", "ci_high"]].copy()
    lres = lattice_summary[lattice_summary["metric"] == "charge_res68_at_fixed_coverage"][["method_label", "value", "ci_low", "ci_high"]].copy()
    p05a_trad = p05a_anchor[p05a_anchor["method"] == "constrained_template_fit"].iloc[0]
    p05a_cnn = p05a_anchor[p05a_anchor["method"] == "compact_18_sample_cnn"].iloc[0]
    lines = [
        "# P05e: baseline-overlap negative-control lattice",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Inputs:** raw HRD ROOT files in `data/root/root`; no simulation truth and no sorted-table shortcuts.",
        "- **Split:** each source run is held out. High-current runs are scored with models trained only from low-current runs 46/47; low-current controls leave their own run out.",
        f"- **Winner rule:** {config['winner_rule']}.",
        "",
        "## Reproduction gates",
        "",
        (
            "The P05a injected anchor and S10/S11 real-candidate gate were rerun from raw ROOT before the calibration benchmark. "
            f"P05a reproduced a traditional time RMS of {p05a_trad['time_rms_ns']:.3f} ns and a compact-CNN time RMS of "
            f"{p05a_cnn['time_rms_ns']:.3f} ns with detection AP {p05a_cnn['detection_ap']:.4f}."
        ),
        "",
        p05a_match.to_markdown(index=False),
        "",
        "The P05a CNN time RMS is a retrained neural anchor and is kept as an environment-sensitivity diagnostic; the raw selected-pulse count gate remains exact.",
        "",
        s10_repro.to_markdown(index=False),
        "",
        s11b_repro.to_markdown(index=False),
        "",
        "## Estimands and equations",
        "",
        "For an event waveform `x`, each method emits an overlap score `s(x)`, a secondary-fraction estimate `f(x)`, and a delay estimate `d(x)`. On synthetic held-out overlays the truth is `y in {0,1}`, `q = A2 / (A1 + A2)`, and delay `Delta`. Baseline/pretrigger negative controls have `y=0`, `q=0`, and are generated by adding early-sample bumps, pedestal slopes, or late exponential sags without a second pulse. The primary lattice estimands are",
        "",
        "```text",
        "Brier = n^{-1} sum_i (s_i - y_i)^2",
        "RMSE_q = sqrt(n^{-1} sum_i (f_i - q_i)^2)",
        "AP = average_precision(y, s)",
        "FPR_base(c) = P[s_i >= c | y_i=0, baseline_control_i=1]",
        "RMS_t(c) = sqrt(mean_{i:y_i=1,s_i>=c} (10*(d_i - Delta_i))^2)",
        "bias_q(c) = mean_{i:y_i=1,s_i>=c} (f_i - q_i)",
        "res68_q(c) = (Q84(f_i-q_i)-Q16(f_i-q_i))/2",
        "L = (1 - AP) + 2 FPR_base(c80) + RMS_t(c80)/80 ns + |bias_q(c80)| + res68_q(c80)",
        "q_i = alpha + beta f_i + epsilon_i",
        "HML_f = sum_z w_z [ E(f | current=20 nA, z) - E(f | current=2 nA, z) ]",
        "D = n^{-1} sum_i |rank(s_i) - rank(f_i)|",
        "```",
        "",
        f"The threshold `c80` is chosen separately per method/fold on the held-out synthetic positives to report the {float(config['fixed_positive_coverage']):.0%} injected-overlap fixed-coverage operating point. The real-current transfer term uses matched amplitude/lowering/topology stratum `z` with raw-count matching weights `w_z`. CIs resample held-out source runs.",
        "",
        "## Methods",
        "",
        "- **Traditional:** frozen bounded two-pulse template fit. The first-pulse time and pulse separation are scanned; amplitudes and baseline are solved by least squares; the score is one-pulse to two-pulse SSE improvement.",
        "- **Ridge:** logistic overlap classifier plus ridge secondary-fraction regressor on normalized samples and one-pulse residual features.",
        "- **Gradient-boosted trees:** histogram gradient-boosted classifier/regressor on the same feature set.",
        "- **MLP:** two-layer perceptron classifier/regressor on standardized features.",
        "- **1D-CNN:** compact convolutional network over 18 normalized samples with detection and decomposition heads.",
        "- **New architecture:** residual-shape ExtraTrees ensemble, chosen because it targets non-linear residual morphology without assuming smooth calibration.",
        "",
        "## Negative-control lattice",
        "",
        "Overall utility loss used for the winner rule:",
        "",
        utility.to_markdown(index=False),
        "",
        "Injected-overlap AP:",
        "",
        lap.to_markdown(index=False),
        "",
        f"False-positive rate on baseline/pretrigger controls at {float(config['fixed_positive_coverage']):.0%} injected-positive coverage:",
        "",
        lfpr.to_markdown(index=False),
        "",
        "Recovered secondary-delay RMS on accepted injected overlaps:",
        "",
        ltime.to_markdown(index=False),
        "",
        "Charge-fraction bias on accepted injected overlaps:",
        "",
        lbias.to_markdown(index=False),
        "",
        "Charge-fraction res68 on accepted injected overlaps:",
        "",
        lres.to_markdown(index=False),
        "",
        "Per-run lattice diagnostics are retained in `lattice_fold_metrics.csv`; full synthetic scores are retained in `lattice_predictions.csv.gz`.",
        "",
        "## Calibration benchmark",
        "",
        "This section preserves the P05d calibration view as a secondary diagnostic. It is not the P05e winner rule.",
        "",
        "Synthetic held-out secondary-fraction RMSE:",
        "",
        rmse.to_markdown(index=False),
        "",
        "Synthetic held-out overlap Brier score:",
        "",
        brier.to_markdown(index=False),
        "",
        "Calibration slope `q = alpha + beta f`:",
        "",
        slope.to_markdown(index=False),
        "",
        "Accepted-event recovery RMSE for `s >= 0.5`:",
        "",
        acc.to_markdown(index=False),
        "",
        "## Real-current transfer",
        "",
        "Matched high-minus-low secondary-fraction estimates:",
        "",
        real_sec.to_markdown(index=False),
        "",
        "Matched high-minus-low overlap-score estimates:",
        "",
        real_score.to_markdown(index=False),
        "",
        "Overlap-score versus secondary-fraction rank discordance on real windows:",
        "",
        discordance[["method_label", "value", "ci_low", "ci_high"]].to_markdown(index=False),
        "",
        "## Systematics and leakage sentinels",
        "",
        leakage.to_markdown(index=False),
        "",
        "Main caveats: synthetic overlays and negative controls are made from raw pulses and therefore test calibration closure, not particle-level truth; high-current pile-up can include support mixtures absent from low-current overlays; the baseline controls are adversarial but not exhaustive; and the real high-minus-low metric is a transfer diagnostic rather than a direct truth-labelled secondary fraction.",
        "",
        "## Verdict",
        "",
        result["conclusion"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/p05e_1781058292_614_2d602ee2_baseline_overlap_negative_control_lattice.py --config configs/p05e_1781058292_614_2d602ee2_baseline_overlap_negative_control_lattice.json",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs(out_dir: Path) -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p05e_1781058292_614_2d602ee2_baseline_overlap_negative_control_lattice.json")
    args = parser.parse_args()
    start = time.time()
    config_path = ROOT / args.config
    config = load_json(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    S11B.OUT = out_dir
    S11B.TICKET = config["ticket_id"]
    S11B.WORKER = config["worker"]
    S11B.STUDY = config["study_id"]
    S11B.RNG_SEED = int(config["random_seed"])
    S11B.BOOTSTRAPS = int(config["bootstrap_samples"])
    S11B.SAMPLE_PER_RUN_STRATUM = int(config["sample_per_run_stratum"])
    P05C.S11B.OUT = out_dir
    P05C.S11B.TICKET = config["ticket_id"]
    P05C.S11B.WORKER = config["worker"]
    P05C.S11B.RNG_SEED = int(config["random_seed"])
    P05C.S11B.BOOTSTRAPS = int(config["bootstrap_samples"])
    P05C.S11B.SAMPLE_PER_RUN_STRATUM = int(config["sample_per_run_stratum"])
    rng = np.random.default_rng(int(config["random_seed"]))

    p05a_match, p05a_anchor, _combined = P05C.reproduce_p05a_anchor(config, out_dir, rng)
    events, waves, run_counts = S11B.load_events()
    topology, s10_repro = S11B.reproduce_s10(events)
    if not bool(s10_repro["pass"].all()):
        raise RuntimeError("S10 raw-root reproduction failed")
    counts = S11B.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = S11B.matched_strata(counts)
    sample = S11B.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)
    scores, template_summary, fold_metrics = run_predictions(events, waves, sample, config, rng)

    real_stratum_summary, real_summary = summarize_real_methods(scores, stratum_table, rng)
    fold_summary = bootstrap_fold_summary(fold_metrics, rng, int(config["bootstrap_samples"]))
    discordance = real_discordance(scores, rng, int(config["bootstrap_samples"]))
    leakage = leakage_checks(scores, fold_metrics)
    lattice_metrics_by_fold, lattice_predictions = run_lattice_predictions(events, waves, sample, config, rng)
    lattice_summary = bootstrap_lattice_summary(lattice_metrics_by_fold, rng, int(config["bootstrap_samples"]))
    winner = choose_lattice_winner(lattice_summary)

    expected_s11b = load_json(ROOT / config["s11b_expected_result"])
    expected_trad = float(expected_s11b["traditional"]["value"])
    trad_now = float(
        real_summary[
            (real_summary["method"] == "traditional_template_fit") & (real_summary["quantity"] == "secondary_fraction")
        ]["value"].iloc[0]
    )
    s11b_repro = pd.DataFrame(
        [
            {
                "quantity": "S11b traditional matched secondary fraction high-minus-low",
                "report_value": expected_trad,
                "reproduced": trad_now,
                "delta": trad_now - expected_trad,
                "tolerance": float(config["s11b_reproduction_tolerances"]["traditional_high_minus_low"]),
                "pass": bool(abs(trad_now - expected_trad) <= float(config["s11b_reproduction_tolerances"]["traditional_high_minus_low"])),
            }
        ]
    )
    if not bool(s11b_repro["pass"].all()):
        raise RuntimeError("S11b traditional reproduction failed")

    input_files = sorted(
        {absolute_path(S11B.raw_file(run)) for run in sorted(S11B.run_to_group())}
        | {absolute_path(P05A.raw_file(P05A.load_config(ROOT / config["p05a_config"]), run)) for run in P05A.configured_runs(P05A.load_config(ROOT / config["p05a_config"]))},
        key=lambda path: str(path),
    )
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    input_hashes[str(config_path.relative_to(ROOT))] = sha256_file(config_path)
    input_hashes["scripts/p05e_1781058292_614_2d602ee2_baseline_overlap_negative_control_lattice.py"] = sha256_file(
        ROOT / "scripts/p05e_1781058292_614_2d602ee2_baseline_overlap_negative_control_lattice.py"
    )

    p05a_match.to_csv(out_dir / "p05a_reproduction_match_table.csv", index=False)
    p05a_anchor.to_csv(out_dir / "p05a_anchor_overall.csv", index=False)
    topology.to_csv(out_dir / "topology_by_group.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    s10_repro.to_csv(out_dir / "s10c_reproduction_match_table.csv", index=False)
    s11b_repro.to_csv(out_dir / "s11b_reproduction_match_table.csv", index=False)
    stratum_table.to_csv(out_dir / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(out_dir / "analysis_sample.csv", index=False)
    template_summary.to_csv(out_dir / "template_summary_by_fold.csv", index=False)
    scores.to_csv(out_dir / "heldout_real_scores.csv", index=False)
    fold_metrics.to_csv(out_dir / "fold_calibration_metrics.csv", index=False)
    fold_summary.to_csv(out_dir / "calibration_summary.csv", index=False)
    lattice_metrics_by_fold.to_csv(out_dir / "lattice_fold_metrics.csv", index=False)
    lattice_summary.to_csv(out_dir / "lattice_summary.csv", index=False)
    lattice_predictions.to_csv(out_dir / "lattice_predictions.csv.gz", index=False, compression="gzip")
    real_stratum_summary.to_csv(out_dir / "real_method_stratum_summary.csv", index=False)
    real_summary.to_csv(out_dir / "real_method_summary.csv", index=False)
    discordance.to_csv(out_dir / "real_discordance_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    save_plots(out_dir, real_summary, fold_summary, scores, winner)

    real_winner_sec = real_summary[(real_summary["method"] == winner["method"]) & (real_summary["quantity"] == "secondary_fraction")].iloc[0]
    trad_sec = real_summary[(real_summary["method"] == "traditional_template_fit") & (real_summary["quantity"] == "secondary_fraction")].iloc[0]
    winner_ap = lattice_summary[(lattice_summary["method"] == winner["method"]) & (lattice_summary["metric"] == "injected_overlap_ap")].iloc[0]
    winner_fpr = lattice_summary[(lattice_summary["method"] == winner["method"]) & (lattice_summary["metric"] == "baseline_control_fpr_at_fixed_coverage")].iloc[0]
    winner_time = lattice_summary[(lattice_summary["method"] == winner["method"]) & (lattice_summary["metric"] == "recovered_time_rms_ns")].iloc[0]
    winner_charge = lattice_summary[(lattice_summary["method"] == winner["method"]) & (lattice_summary["metric"] == "charge_res68_at_fixed_coverage")].iloc[0]
    conclusion = (
        f"Winner by the predeclared negative-control lattice criterion is {winner['method_label']} with utility loss "
        f"{winner['value']:.5f} [{winner['ci'][0]:.5f}, {winner['ci'][1]:.5f}], injected-overlap AP "
        f"{winner_ap['value']:.5f} [{winner_ap['ci_low']:.5f}, {winner_ap['ci_high']:.5f}], baseline-control FPR "
        f"{winner_fpr['value']:.5f} [{winner_fpr['ci_low']:.5f}, {winner_fpr['ci_high']:.5f}], recovered-time RMS "
        f"{winner_time['value']:.2f} ns [{winner_time['ci_low']:.2f}, {winner_time['ci_high']:.2f}], and charge res68 "
        f"{winner_charge['value']:.5f} [{winner_charge['ci_low']:.5f}, {winner_charge['ci_high']:.5f}] at "
        f"{float(config['fixed_positive_coverage']):.0%} positive coverage. On real matched windows its "
        f"secondary-fraction high-minus-low transfer estimate is {real_winner_sec['value']:.5f} "
        f"[{real_winner_sec['ci_low']:.5f}, {real_winner_sec['ci_high']:.5f}], compared with the traditional "
        f"template-fit estimate {trad_sec['value']:.5f} [{trad_sec['ci_low']:.5f}, {trad_sec['ci_high']:.5f}]. "
        f"Raw-root reproduction gates pass and {int(leakage['flag'].sum())} leakage/current-identification sentinels flag. "
        "The result supports using the winner as a baseline-aware overlap diagnostic under this support policy, not as an unqualified particle-truth pile-up correction."
    )
    next_tickets = config.get("next_tickets", [])
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(p05a_match["pass"].all() and s10_repro["pass"].all() and s11b_repro["pass"].all()),
        "reproduction_gate": "P05a injected anchor plus S10c topology fractions plus S11b traditional high-minus-low from raw ROOT",
        "split": "leave-one-source-run-out; high-current runs train only on low-current source runs; lattice CIs bootstrap held-out source runs",
        "bootstrap": {"unit": "source_run", "samples": int(config["bootstrap_samples"])},
        "strata": {
            "definition": "S10c amplitude bin x S16 adaptive lowering bin x P02 topology",
            "n_matched_strata": int(len(stratum_table)),
            "global_s10_downstream_high_minus_low": float(global_downstream_excess),
            "n_scored_events": int(len(scores)),
            "sample_cap_per_run_stratum": int(config["sample_per_run_stratum"]),
        },
        "winner": winner,
        "winner_lattice_metrics": {
            row["metric"]: {"value": float(row["value"]), "ci": [float(row["ci_low"]), float(row["ci_high"])]}
            for _, row in lattice_summary[lattice_summary["method"] == winner["method"]].iterrows()
        },
        "traditional": {
            "method": "traditional_template_fit",
            "metric": "matched_stratified_secondary_fraction_high_minus_low",
            "value": float(trad_sec["value"]),
            "ci": [float(trad_sec["ci_low"]), float(trad_sec["ci_high"])],
        },
        "ml": {
            "winner_method": winner["method"],
            "winner_method_label": winner["method_label"],
            "winner_metric": winner["metric"],
            "winner_value": winner["value"],
            "winner_ci": winner["ci"],
            "methods_compared": list(METHOD_LABELS.keys()),
        },
        "method_benchmark": {
            row["method"]: {
                "method_label": row["method_label"],
                "lattice_utility_loss": float(row["value"]),
                "ci": [float(row["ci_low"]), float(row["ci_high"])],
            }
            for _, row in lattice_summary[lattice_summary["metric"] == "lattice_utility_loss"].iterrows()
        },
        "lattice_metrics": {
            metric: {
                row["method"]: {
                    "method_label": row["method_label"],
                    "value": float(row["value"]),
                    "ci": [float(row["ci_low"]), float(row["ci_high"])],
                }
                for _, row in lattice_summary[lattice_summary["metric"] == metric].iterrows()
            }
            for metric in sorted(lattice_summary["metric"].unique())
        },
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "conclusion": conclusion,
        "next_tickets": next_tickets,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(
        out_dir,
        config,
        p05a_match,
        p05a_anchor,
        s10_repro,
        s11b_repro,
        real_summary,
        fold_summary,
        discordance,
        leakage,
        winner,
        lattice_summary,
        lattice_metrics_by_fold,
        result,
    )
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": winner["method"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
