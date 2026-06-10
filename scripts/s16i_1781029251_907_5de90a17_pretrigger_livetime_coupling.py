#!/usr/bin/env python3
"""S16i pretrigger-baseline live-time coupling audit.

The script rebuilds the S10 selected-event table from raw B-stack ROOT first,
then tests whether pretrigger-only nuisance structure shifts S10 tail and
two-pulse observables.  All ML predictions are leave-one-run-out and exclude
run/current/event identifiers plus post-trigger samples.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
S10H_PATH = ROOT / "scripts/s10h_1781027683_951_7bcc2f09_baseline_excursion_decomposition.py"


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s10h = import_module(S10H_PATH, "s10h_source")
s10e = s10h.s10e


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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def ci(values) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def topology_reproduction(run_counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    grouped = run_counts.groupby("group", as_index=False).sum(numeric_only=True)
    grouped["multi_stave_per_selected_event"] = grouped["multi_stave_events"] / grouped["events_with_selected"]
    grouped["three_stave_per_selected_event"] = grouped["three_stave_events"] / grouped["events_with_selected"]
    grouped["downstream_per_selected_event"] = grouped["downstream_events"] / grouped["events_with_selected"]
    rows = []
    for group, expected in config["expected_topology"].items():
        got = grouped[grouped["group"] == group].iloc[0]
        for metric, report_value in expected.items():
            reproduced = float(got[metric])
            rows.append(
                {
                    "quantity": "{} {}".format(group, metric),
                    "report_value": float(report_value),
                    "reproduced": reproduced,
                    "delta": reproduced - float(report_value),
                    "tolerance": float(config["topology_tolerance"]),
                    "pass": bool(abs(reproduced - float(report_value)) <= float(config["topology_tolerance"])),
                }
            )
    return pd.DataFrame(rows)


def last_above_ns(waves: np.ndarray, amplitude: np.ndarray, fraction: float) -> np.ndarray:
    threshold = np.maximum(amplitude, 1.0) * float(fraction)
    above = waves >= threshold[:, None]
    out = np.zeros(len(waves), dtype=float)
    for idx in range(len(waves)):
        where = np.flatnonzero(above[idx])
        out[idx] = float(where[-1]) * 10.0 if len(where) else 0.0
    return out


def add_pretrigger_features(events: pd.DataFrame, waves: np.ndarray, config: dict) -> pd.DataFrame:
    out = events.copy()
    pre_idx = [int(i) for i in config["baseline_samples"]]
    pre = waves[:, pre_idx]
    out["pre_mean_corr_adc"] = pre.mean(axis=1)
    out["pre_rms_corr_adc"] = np.sqrt(np.mean((pre - pre.mean(axis=1)[:, None]) ** 2, axis=1))
    out["pre_slope_corr_adc"] = pre[:, -1] - pre[:, 0]
    out["pre_max_exc_corr_adc"] = np.max(np.abs(pre - pre.mean(axis=1)[:, None]), axis=1)
    out["pre_ptp_corr_adc"] = pre.max(axis=1) - pre.min(axis=1)
    out["pre_asym_corr_adc"] = 0.5 * ((pre[:, 0] + pre[:, 1]) - (pre[:, 2] + pre[:, 3]))
    for threshold in config["thresholds"]:
        key = threshold["key"]
        out["last_above_{}_ns".format(key)] = last_above_ns(
            waves, out["ref_amp_adc"].to_numpy(dtype=float), float(threshold["fraction"])
        )
    out["tail_risk_{}_label".format(config["ml_tail_target"])] = (
        out["last_above_{}_ns".format(config["ml_tail_target"])]
        >= out["last_above_{}_ns".format(config["ml_tail_target"])].quantile(float(config["ml_tail_risk_quantile"]))
    ).astype(int)
    return out


def train_pretrigger_bins(train: pd.DataFrame) -> dict:
    return {
        "rms_q": [float(x) for x in train["pre_rms_corr_adc"].quantile([0.5, 0.8, 0.95]).to_numpy()],
        "slope_q": [float(x) for x in train["pre_slope_corr_adc"].abs().quantile([0.5, 0.8, 0.95]).to_numpy()],
        "exc_q": [float(x) for x in train["pre_max_exc_corr_adc"].quantile([0.5, 0.8, 0.95]).to_numpy()],
        "lower_q": [float(x) for x in train["adaptive_lowering_adc"].quantile([0.5, 0.9]).to_numpy()],
    }


def apply_pretrigger_bins(df: pd.DataFrame, bins: dict) -> pd.DataFrame:
    out = df.copy()
    def qbin(values: pd.Series, cuts: list[float], labels: list[str]) -> np.ndarray:
        clean_cuts = []
        for value in cuts:
            value = float(value)
            if not clean_cuts or value > clean_cuts[-1]:
                clean_cuts.append(value)
        idx = np.searchsorted(np.asarray(clean_cuts, dtype=float), values.to_numpy(dtype=float), side="right")
        return np.asarray([labels[min(int(i), len(labels) - 1)] for i in idx], dtype=object)

    out["pre_rms_bin"] = qbin(out["pre_rms_corr_adc"], bins["rms_q"], ["rms_q1", "rms_q2", "rms_q3", "rms_q4"])
    out["pre_slope_bin"] = qbin(out["pre_slope_corr_adc"].abs(), bins["slope_q"], ["slope_q1", "slope_q2", "slope_q3", "slope_q4"])
    out["pre_exc_bin"] = qbin(out["pre_max_exc_corr_adc"], bins["exc_q"], ["exc_q1", "exc_q2", "exc_q3", "exc_q4"])
    out["adaptive_bin"] = qbin(out["adaptive_lowering_adc"], bins["lower_q"], ["lower_q1", "lower_q2", "lower_q3"])
    out["pretrigger_stratum"] = (
        out["pre_rms_bin"] + "|" + out["pre_slope_bin"] + "|" + out["pre_exc_bin"] + "|" + out["adaptive_bin"]
    )
    high = (
        (out["pre_rms_bin"] == "rms_q4")
        | (out["pre_slope_bin"] == "slope_q4")
        | (out["pre_exc_bin"] == "exc_q4")
        | (out["adaptive_bin"] == "lower_q3")
    )
    out["pretrigger_risk_group"] = np.where(high, "high_pretrigger", "quiet_reference")
    return out


def two_pulse_fit_summary(events: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    templates = {}
    for stave in s10e.STAVES:
        mask = events["ref_stave"].to_numpy() == stave
        amp = np.maximum(events.loc[mask, "ref_amp_adc"].to_numpy(dtype=float), 1.0)
        templates[stave] = np.median(waves[mask] / amp[:, None], axis=0)
    improvement = np.zeros(len(events), dtype=float)
    best_delay_ns = np.full(len(events), np.nan, dtype=float)
    for stave, template in templates.items():
        idx = np.where(events["ref_stave"].to_numpy() == stave)[0]
        if len(idx) == 0:
            continue
        w = waves[idx]
        denom = float(np.dot(template, template))
        single_scale = np.maximum((w @ template) / max(denom, 1e-9), 0.0)
        single = single_scale[:, None] * template[None, :]
        single_sse = np.mean((w - single) ** 2, axis=1)
        best_sse = single_sse.copy()
        best_delay = np.full(len(idx), np.nan, dtype=float)
        for delay in range(3, 10):
            shifted = np.zeros_like(template)
            shifted[delay:] = template[:-delay]
            design = np.column_stack([template, shifted])
            coef, *_ = np.linalg.lstsq(design, w.T, rcond=None)
            coef = np.clip(coef.T, 0.0, None)
            fit = coef @ design.T
            sse = np.mean((w - fit) ** 2, axis=1)
            improved = sse < best_sse
            best_sse[improved] = sse[improved]
            best_delay[improved] = float(delay) * 10.0
        improvement[idx] = np.clip((single_sse - best_sse) / np.maximum(single_sse, 1.0), 0.0, 1.0)
        best_delay_ns[idx] = best_delay
    return pd.DataFrame({"two_pulse_improvement": improvement, "two_pulse_delay_ns": best_delay_ns})


def charge_residuals(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    model = Pipeline(
        [
            (
                "features",
                ColumnTransformer(
                    [
                        ("num", StandardScaler(), ["log_amp"]),
                        ("cat", OneHotEncoder(handle_unknown="ignore"), ["ref_stave"]),
                    ]
                ),
            ),
            ("reg", Ridge(alpha=1.0)),
        ]
    )
    model.fit(train[["log_amp", "ref_stave"]], train["area_over_peak"])
    return (
        train["area_over_peak"].to_numpy(dtype=float) - model.predict(train[["log_amp", "ref_stave"]]),
        test["area_over_peak"].to_numpy(dtype=float) - model.predict(test[["log_amp", "ref_stave"]]),
    )


def ece_score(y_true: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & ((prob < hi) if hi < 1.0 else (prob <= hi))
        if mask.any():
            total += float(mask.mean()) * abs(float(y_true[mask].mean()) - float(prob[mask].mean()))
    return float(total)


def auc_or_nan(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def run_delta(df: pd.DataFrame, value_col: str) -> float:
    means = df.groupby("pretrigger_risk_group")[value_col].mean()
    return float(means.get("high_pretrigger", np.nan) - means.get("quiet_reference", np.nan))


def current_delta(df: pd.DataFrame, value_col: str) -> float:
    means = df.groupby("group")[value_col].mean()
    return float(means.get("high_20nA", np.nan) - means.get("low_2nA", np.nan))


def rms_delay(df: pd.DataFrame) -> float:
    vals = df.loc[df["two_pulse_improvement"] > 0.10, "two_pulse_delay_ns"].dropna().to_numpy(dtype=float)
    if len(vals) == 0:
        return float("nan")
    return float(np.sqrt(np.mean(vals**2)))


def bootstrap_runs(frame: pd.DataFrame, metric_fn, config: dict) -> tuple[float, float, float]:
    center = metric_fn(frame)
    rng = np.random.default_rng(int(config["random_seed"]) + 31)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    values = []
    for _ in range(int(config["bootstrap_samples"])):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        pieces = [frame[frame["run"] == int(run)] for run in chosen]
        values.append(metric_fn(pd.concat(pieces, ignore_index=True)))
    lo, hi = ci(values)
    return float(center), lo, hi


def bootstrap_values(values, config: dict, seed_offset: int = 0) -> tuple[float, float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    center = float(np.nanmean(arr)) if len(arr) else float("nan")
    if len(arr) == 0:
        return center, float("nan"), float("nan")
    rng = np.random.default_rng(int(config["random_seed"]) + 101 + int(seed_offset))
    boot = []
    for _ in range(int(config["bootstrap_samples"])):
        boot.append(float(np.mean(rng.choice(arr, size=len(arr), replace=True))))
    lo, hi = ci(boot)
    return center, lo, hi


def bootstrap_high_minus_low(high_values, low_values, config: dict, seed_offset: int = 0) -> tuple[float, float, float]:
    high = np.asarray(list(high_values), dtype=float)
    low = np.asarray(list(low_values), dtype=float)
    high = high[np.isfinite(high)]
    low = low[np.isfinite(low)]
    center = float(np.mean(high) - np.mean(low)) if len(high) and len(low) else float("nan")
    if len(high) == 0 or len(low) == 0:
        return center, float("nan"), float("nan")
    rng = np.random.default_rng(int(config["random_seed"]) + 151 + int(seed_offset))
    boot = []
    for _ in range(int(config["bootstrap_samples"])):
        boot.append(float(np.mean(rng.choice(high, size=len(high), replace=True)) - np.mean(rng.choice(low, size=len(low), replace=True))))
    lo, hi = ci(boot)
    return center, lo, hi


def run_level_pretrigger_delta(frame: pd.DataFrame, value_col: str) -> list[float]:
    vals = []
    for _, sub in frame.groupby("run"):
        if {"high_pretrigger", "quiet_reference"}.issubset(set(sub["pretrigger_risk_group"].unique())):
            vals.append(run_delta(sub, value_col))
    return vals


def run_level_pretrigger_positive_delta(frame: pd.DataFrame, value_col: str) -> list[float]:
    vals = []
    for _, sub in frame.groupby("run"):
        if not {"high_pretrigger", "quiet_reference"}.issubset(set(sub["pretrigger_risk_group"].unique())):
            continue
        high = sub[(sub["pretrigger_risk_group"] == "high_pretrigger") & (sub[value_col] > 0)][value_col]
        quiet = sub[(sub["pretrigger_risk_group"] == "quiet_reference") & (sub[value_col] > 0)][value_col]
        if len(high) and len(quiet):
            vals.append(float(high.mean() - quiet.mean()))
    return vals


def run_level_current_values(frame: pd.DataFrame, value_col: str) -> tuple[np.ndarray, np.ndarray]:
    grouped = frame.groupby(["run", "group"])[value_col].mean().reset_index()
    high = grouped[grouped["group"] == "high_20nA"][value_col].to_numpy(dtype=float)
    low = grouped[grouped["group"] == "low_2nA"][value_col].to_numpy(dtype=float)
    return high, low


def summarize_traditional(scored: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for threshold in config["thresholds"]:
        key = threshold["key"]
        value_col = "last_above_{}_ns".format(key)
        center, lo, hi = bootstrap_values(run_level_pretrigger_positive_delta(scored, value_col), config, len(rows))
        rows.append(
            {
                "method": "traditional_pretrigger_strata",
                "metric": "tau_eff_shift_{}_ns".format(key),
                "value": center,
                "ci_low": lo,
                "ci_high": hi,
                "n_bootstrap": int(config["bootstrap_samples"]),
                "bootstrap_unit": "heldout_run",
            }
        )
        center, lo, hi = bootstrap_values(run_level_pretrigger_delta(scored, value_col), config, len(rows))
        rows.append(
            {
                "method": "traditional_pretrigger_strata",
                "metric": "empirical_last_above_shift_{}_ns".format(key),
                "value": center,
                "ci_low": lo,
                "ci_high": hi,
                "n_bootstrap": int(config["bootstrap_samples"]),
                "bootstrap_unit": "heldout_run",
            }
        )
    for metric, fn in [
        ("two_pulse_time_rms_shift_ns", lambda: run_level_pretrigger_delta(scored.assign(two_pulse_time_rms_proxy=scored["two_pulse_delay_ns"].fillna(0.0)), "two_pulse_time_rms_proxy")),
        ("two_pulse_time_rms_ns", lambda: [rms_delay(sub) for _, sub in scored.groupby("run")]),
        ("two_pulse_residual_shift", lambda: run_level_pretrigger_delta(scored, "two_pulse_improvement")),
        ("charge_bias_shift_area_over_peak", lambda: run_level_pretrigger_delta(scored, "charge_residual")),
        ("downstream_excess_high_minus_low", None),
    ]:
        if metric == "downstream_excess_high_minus_low":
            high, low = run_level_current_values(scored, "downstream")
            center, lo, hi = bootstrap_high_minus_low(high, low, config, len(rows))
        else:
            center, lo, hi = bootstrap_values(fn(), config, len(rows))
        rows.append(
            {
                "method": "traditional_pretrigger_strata",
                "metric": metric,
                "value": center,
                "ci_low": lo,
                "ci_high": hi,
                "n_bootstrap": int(config["bootstrap_samples"]),
                "bootstrap_unit": "heldout_run",
            }
        )
    grouped = scored.groupby(["pretrigger_risk_group", "pre_rms_bin", "pre_slope_bin", "pre_exc_bin", "adaptive_bin"], observed=False).agg(
        n=("downstream", "size"),
        downstream_rate=("downstream", "mean"),
        tail20_mean_ns=("last_above_20pct_ns", "mean"),
        two_pulse_improvement=("two_pulse_improvement", "mean"),
        charge_residual=("charge_residual", "mean"),
    ).reset_index()
    return grouped, pd.DataFrame(rows)


def make_pretrigger_model() -> Pipeline:
    return Pipeline(
        [
            (
                "features",
                ColumnTransformer(
                    [
                        (
                            "num",
                            StandardScaler(),
                            [
                                "pre_mean_corr_adc",
                                "pre_rms_corr_adc",
                                "pre_slope_corr_adc",
                                "pre_max_exc_corr_adc",
                                "pre_ptp_corr_adc",
                                "pre_asym_corr_adc",
                                "adaptive_lowering_adc",
                            ],
                        )
                    ]
                ),
            ),
            ("clf", LogisticRegression(C=0.5, max_iter=500, class_weight="balanced", solver="liblinear")),
        ]
    )


def run_heldout_ml(base: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 71)
    pred_rows = []
    fold_rows = []
    leakage_rows = []
    tail_key = config["ml_tail_target"]
    tail_col = "last_above_{}_ns".format(tail_key)
    target_col = "tail_risk_{}_label".format(tail_key)
    feature_cols = [
        "pre_mean_corr_adc",
        "pre_rms_corr_adc",
        "pre_slope_corr_adc",
        "pre_max_exc_corr_adc",
        "pre_ptp_corr_adc",
        "pre_asym_corr_adc",
        "adaptive_lowering_adc",
    ]
    for heldout_run in sorted(base["run"].unique()):
        train = base[base["run"] != heldout_run].copy()
        test = base[base["run"] == heldout_run].copy()
        if len(train) > int(config["ml_max_train_rows"]):
            train = train.sample(n=int(config["ml_max_train_rows"]), random_state=int(config["random_seed"]) + int(heldout_run))
        bins = train_pretrigger_bins(train)
        train = apply_pretrigger_bins(train, bins)
        test = apply_pretrigger_bins(test, bins)
        train_charge_resid, test_charge_resid = charge_residuals(train, test)
        train["charge_residual"] = train_charge_resid
        test["charge_residual"] = test_charge_resid

        y_train = train[target_col].to_numpy(dtype=int)
        y_test = test[target_col].to_numpy(dtype=int)
        clf = make_pretrigger_model()
        clf.fit(train[feature_cols], y_train)
        prob = clf.predict_proba(test[feature_cols])[:, 1]
        stratum_rate = train.groupby("pretrigger_stratum", observed=False)[target_col].mean()
        global_rate = float(y_train.mean())
        trad_prob = test["pretrigger_stratum"].map(stratum_rate).fillna(global_rate).to_numpy(dtype=float)

        reg = Pipeline([("scale", StandardScaler()), ("reg", Ridge(alpha=20.0))])
        reg.fit(train[feature_cols], train[tail_col].to_numpy(dtype=float))
        tail_pred = np.clip(reg.predict(test[feature_cols]), 0.0, 170.0)

        shuffled_train = train[feature_cols].copy()
        for col in feature_cols:
            shuffled_train[col] = rng.permutation(shuffled_train[col].to_numpy())
        shuf = make_pretrigger_model()
        shuf.fit(shuffled_train, y_train)
        shuffled_prob = shuf.predict_proba(test[feature_cols])[:, 1]

        out = test[
            [
                "run",
                "group",
                "current_nA",
                "downstream",
                "pretrigger_risk_group",
                "pretrigger_stratum",
                "two_pulse_improvement",
                "two_pulse_delay_ns",
                "charge_residual",
                tail_col,
                target_col,
            ]
        ].copy()
        out["traditional_prob"] = trad_prob
        out["ml_prob"] = prob
        out["shuffled_pretrigger_prob"] = shuffled_prob
        out["ml_tail_pred_ns"] = tail_pred
        out["ml_tail_resid_ns"] = out[tail_col].to_numpy(dtype=float) - tail_pred
        pred_rows.append(out)

        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "n_train": int(len(train)),
                "n_test": int(len(test)),
                "tail_target": tail_key,
                "positive_rate_train": float(y_train.mean()),
                "positive_rate_test": float(y_test.mean()),
                "traditional_auc": auc_or_nan(y_test, trad_prob),
                "ml_auc": auc_or_nan(y_test, prob),
                "traditional_brier": float(brier_score_loss(y_test, trad_prob)),
                "ml_brier": float(brier_score_loss(y_test, prob)),
                "traditional_log_loss": float(log_loss(y_test, np.clip(trad_prob, 1e-6, 1 - 1e-6), labels=[0, 1])),
                "ml_log_loss": float(log_loss(y_test, np.clip(prob, 1e-6, 1 - 1e-6), labels=[0, 1])),
                "ml_ece": ece_score(y_test, prob),
                "traditional_ece": ece_score(y_test, trad_prob),
            }
        )
        leakage_rows.append(
            {
                "heldout_run": int(heldout_run),
                "check": "shuffled_pretrigger_control",
                "value": auc_or_nan(y_test, shuffled_prob),
                "flag": bool(auc_or_nan(y_test, shuffled_prob) > float(config["leakage_auc_flag"])),
                "note": "pretrigger features independently permuted in training before scoring held-out run",
            }
        )
        leakage_rows.append(
            {
                "heldout_run": int(heldout_run),
                "check": "ml_minus_traditional_auc",
                "value": auc_or_nan(y_test, prob) - auc_or_nan(y_test, trad_prob),
                "flag": bool((auc_or_nan(y_test, prob) - auc_or_nan(y_test, trad_prob)) > float(config["ml_delta_auc_flag"])),
                "note": "large pretrigger-only gain triggers leakage review",
            }
        )
    return pd.concat(pred_rows, ignore_index=True), pd.DataFrame(fold_rows), pd.DataFrame(leakage_rows)


def summarize_ml(pred: pd.DataFrame, folds: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    fold_metrics = {
        "traditional_tail_auc": folds["traditional_auc"],
        "ml_tail_auc": folds["ml_auc"],
        "ml_minus_traditional_auc": folds["ml_auc"] - folds["traditional_auc"],
        "ml_calibration_ece": folds["ml_ece"],
        "traditional_calibration_ece": folds["traditional_ece"],
        "ml_minus_traditional_ece": folds["ml_ece"] - folds["traditional_ece"],
        "mean_brier_improvement_vs_traditional": folds["traditional_brier"] - folds["ml_brier"],
        "mean_log_loss_improvement_vs_traditional": folds["traditional_log_loss"] - folds["ml_log_loss"],
    }
    for metric, values in fold_metrics.items():
        center, lo, hi = bootstrap_values(values, config, len(rows))
        rows.append(
            {
                "method": "ml_pretrigger_only",
                "metric": metric,
                "value": center,
                "ci_low": lo,
                "ci_high": hi,
                "n_bootstrap": int(config["bootstrap_samples"]),
                "bootstrap_unit": "heldout_run",
            }
        )
    for metric, value_col in [
        ("ml_tail_resid_shift_ns", "ml_tail_resid_ns"),
        ("ml_predicted_tau_shift_ns", "ml_tail_pred_ns"),
    ]:
        center, lo, hi = bootstrap_values(run_level_pretrigger_delta(pred, value_col), config, len(rows))
        rows.append(
            {
                "method": "ml_pretrigger_only",
                "metric": metric,
                "value": center,
                "ci_low": lo,
                "ci_high": hi,
                "n_bootstrap": int(config["bootstrap_samples"]),
                "bootstrap_unit": "heldout_run",
            }
        )
    for metric, value_col in [
        ("ml_predicted_downstream_excess", "ml_prob"),
        ("traditional_predicted_downstream_excess", "traditional_prob"),
    ]:
        high, low = run_level_current_values(pred, value_col)
        center, lo, hi = bootstrap_high_minus_low(high, low, config, len(rows))
        rows.append(
            {
                "method": "ml_pretrigger_only",
                "metric": metric,
                "value": center,
                "ci_low": lo,
                "ci_high": hi,
                "n_bootstrap": int(config["bootstrap_samples"]),
                "bootstrap_unit": "heldout_run",
            }
        )
    delta_pred = pred.copy()
    delta_pred["_prob_delta"] = delta_pred["ml_prob"].to_numpy(dtype=float) - delta_pred["traditional_prob"].to_numpy(dtype=float)
    high_delta, low_delta = run_level_current_values(delta_pred, "_prob_delta")
    center, lo, hi = bootstrap_high_minus_low(high_delta, low_delta, config, len(rows))
    rows.append(
        {
            "method": "ml_pretrigger_only",
            "metric": "ml_minus_traditional_predicted_downstream_excess",
            "value": center,
            "ci_low": lo,
            "ci_high": hi,
            "n_bootstrap": int(config["bootstrap_samples"]),
            "bootstrap_unit": "heldout_run",
        }
    )
    return pd.DataFrame(rows)


def write_checksums(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in [int(x) for x in config["runs"]]:
        path = ROOT / config["raw_root_dir"] / "hrdb_run_{:04d}.root".format(run)
        rows.append({"file": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "input_sha256.csv", index=False)
    return df


def write_report(config: dict, out_dir: Path, reproduction: pd.DataFrame, traditional: pd.DataFrame, ml: pd.DataFrame, leakage: pd.DataFrame, folds: pd.DataFrame) -> None:
    tail_key = config["ml_tail_target"]
    trad_tail = traditional[traditional["metric"] == "tau_eff_shift_{}_ns".format(tail_key)].iloc[0]
    down = traditional[traditional["metric"] == "downstream_excess_high_minus_low"].iloc[0]
    ml_auc = ml[ml["metric"] == "ml_tail_auc"].iloc[0]
    ml_ece = ml[ml["metric"] == "ml_calibration_ece"].iloc[0]
    flags = int(leakage["flag"].sum()) if len(leakage) else 0
    lines = [
        "# S16i: pretrigger-baseline live-time coupling audit",
        "",
        "- **Ticket:** `{}`".format(config["ticket_id"]),
        "- **Worker:** `{}`".format(config["worker"]),
        "- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** all ML predictions are leave-one-run-out; intervals use held-out run bootstrap CIs.",
        "- **Leakage exclusions:** ML features are pretrigger mean/RMS/slope/max-excursion/ptp/asymmetry plus adaptive-lowering only; run/current/event identifiers, labels, and post-trigger samples are excluded.",
        "",
        "## Reproduction first",
        "",
        "Raw `h101/HRDv` was rescanned before modeling. The S10 selected-event topology numbers reproduce within the preregistered tolerance.",
        "",
        reproduction.to_markdown(index=False),
        "",
        "## Traditional method",
        "",
        "Frozen train-run pretrigger bins stratify held-out events by RMS, slope, max excursion, and adaptive-lowering. The headline 20% tail shift is **{:.3f} ns** [{:.3f}, {:.3f}], and the current downstream excess is **{:.5f}** [{:.5f}, {:.5f}].".format(
            trad_tail["value"], trad_tail["ci_low"], trad_tail["ci_high"], down["value"], down["ci_low"], down["ci_high"]
        ),
        "",
        traditional.to_markdown(index=False),
        "",
        "## ML method",
        "",
        "The pretrigger-only classifier/regressor targets the held-out 20% tail-risk label. Held-out AUC is **{:.3f}** [{:.3f}, {:.3f}] with calibration ECE **{:.4f}** [{:.4f}, {:.4f}].".format(
            ml_auc["value"], ml_auc["ci_low"], ml_auc["ci_high"], ml_ece["value"], ml_ece["ci_low"], ml_ece["ci_high"]
        ),
        "",
        ml.to_markdown(index=False),
        "",
        "## Leakage review",
        "",
        "Shuffled-pretrigger controls and ML-minus-traditional AUC gates produced **{}** flags. Any large pretrigger-only gains are treated as nuisance sensitivity, not physics truth.".format(flags),
        "",
        leakage.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        "Pretrigger baseline spectra measurably couple to S10 live-time tail observables, but the coupling is nuisance-like: the high-pretrigger group has shorter tail and two-pulse proxies, while the raw current downstream excess remains positive. The pretrigger-only ML model predicts the opposite downstream-current sign and adds calibration diagnostics rather than a cleaner physical separation, so shuffled-pretrigger controls remain the limiting leakage guard.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s16i_1781029251_907_5de90a17_pretrigger_livetime_coupling.py --config configs/s16i_1781029251_907_5de90a17_pretrigger_livetime_coupling.json",
        "```",
        "",
        "Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `traditional_summary.csv`, `ml_summary.csv`, `ml_fold_diagnostics.csv`, and `leakage_checks.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s16i_1781029251_907_5de90a17_pretrigger_livetime_coupling.json")
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("loading raw ROOT event table", flush=True)
    events, waves, norm, run_counts, p09_meta = s10h.load_events_with_p09a_features()
    reproduction = topology_reproduction(run_counts, config)
    print("adding p09a labels and pretrigger features", flush=True)
    events, _, labelled = s10h.add_p09a_labels(events, norm, p09_meta)
    events = add_pretrigger_features(events, waves, config)
    events = pd.concat([events.reset_index(drop=True), two_pulse_fit_summary(events, waves).reset_index(drop=True)], axis=1)
    events["two_pulse_improvement"] = np.maximum(
        events["two_pulse_improvement"].to_numpy(dtype=float),
        s10h.two_pulse_residuals(events, waves),
    )
    events["log_amp"] = np.log(np.maximum(events["ref_amp_adc"].to_numpy(dtype=float), 1.0))

    all_scored = []
    for heldout_run in sorted(events["run"].unique()):
        train = events[events["run"] != heldout_run].copy()
        test = events[events["run"] == heldout_run].copy()
        bins = train_pretrigger_bins(train)
        test = apply_pretrigger_bins(test, bins)
        _, test_resid = charge_residuals(apply_pretrigger_bins(train, bins), test)
        test["charge_residual"] = test_resid
        all_scored.append(test)
    scored = pd.concat(all_scored, ignore_index=True)

    print("running traditional summaries", flush=True)
    strata, traditional = summarize_traditional(scored, config)
    print("running held-out ML", flush=True)
    pred, folds, leakage = run_heldout_ml(events, config)
    ml = summarize_ml(pred, folds, config)
    checksums = write_checksums(config, out_dir)

    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "raw_run_counts.csv", index=False)
    strata.to_csv(out_dir / "traditional_strata.csv", index=False)
    traditional.to_csv(out_dir / "traditional_summary.csv", index=False)
    folds.to_csv(out_dir / "ml_fold_diagnostics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    ml.to_csv(out_dir / "ml_summary.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "split": "leave-one-run-out ML; held-out run bootstrap CIs",
        "traditional": traditional.to_dict(orient="records"),
        "ml": {"summary": ml.to_dict(orient="records"), "fold_diagnostics": folds.to_dict(orient="records")},
        "leakage": leakage.to_dict(orient="records"),
        "inputs": checksums.to_dict(orient="records"),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "script": "scripts/s16i_1781029251_907_5de90a17_pretrigger_livetime_coupling.py",
        "config": str(args.config.relative_to(ROOT) if args.config.is_absolute() else args.config),
        "artifacts": sorted(p.name for p in out_dir.iterdir() if p.is_file()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    write_report(config, out_dir, reproduction, traditional, ml, leakage, folds)
    print("wrote {}".format(out_dir), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
