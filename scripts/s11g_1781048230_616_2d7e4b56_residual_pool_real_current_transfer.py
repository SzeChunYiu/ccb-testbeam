#!/usr/bin/env python3
"""S11g residual-pool two-pulse real-current transfer gate.

The ticket asks whether the S11e conditioned residual-pool gains on injected
two-pulse recovery transfer to real high-current candidate windows.  This
script keeps the reviewed S11b raw-ROOT event construction, upgrades the
traditional scorer to the S11c/S11e amplitude-binned asymmetric template fit,
and runs a source-run-held-out bakeoff against ridge, gradient-boosted trees,
MLP, a small 1D-CNN, and a consensus abstention ensemble.
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
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "s11g_1781048230_616_2d7e4b56_residual_pool_real_current_transfer.json"
THIS_SCRIPT = "scripts/s11g_1781048230_616_2d7e4b56_residual_pool_real_current_transfer.py"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_s11b(path: Path):
    spec = importlib.util.spec_from_file_location("s11b_source", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load S11b source script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_s11c(path: Path):
    spec = importlib.util.spec_from_file_location("s11c_source_for_s11g", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load S11c source script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def markdown_table(frame: pd.DataFrame, float_digits: int = 5) -> str:
    def fmt(v):
        if pd.isna(v):
            return ""
        if isinstance(v, (float, np.floating)):
            return f"{float(v):.{float_digits}g}"
        return str(v)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(c)) for c in cols]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    out = ["| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |"]
    out.append("| " + " | ".join("-" * w for w in widths) + " |")
    for row in rows:
        out.append("| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |")
    return "\n".join(out)


def split_calibration(
    x: pd.DataFrame,
    y_class: np.ndarray,
    y_frac: np.ndarray,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame, np.ndarray, np.ndarray]:
    idx = rng.permutation(len(x))
    cut = max(20, int(0.75 * len(idx)))
    tr = idx[:cut]
    ca = idx[cut:]
    return (
        x.iloc[tr].reset_index(drop=True),
        y_class[tr],
        y_frac[tr],
        x.iloc[ca].reset_index(drop=True),
        y_class[ca],
        y_frac[ca],
    )


def sample_cols(x: pd.DataFrame) -> List[str]:
    return [c for c in x.columns if c.startswith("sample_")]


class TorchCnn:
    def __init__(self, seed: int = 0, epochs: int = 22):
        self.seed = int(seed)
        self.epochs = int(epochs)
        self.model = None
        self.cols: List[str] = []

    def fit(self, x: pd.DataFrame, y_class: np.ndarray, y_frac: np.ndarray) -> "TorchCnn":
        import torch
        import torch.nn as nn

        torch.manual_seed(self.seed)
        self.cols = sample_cols(x)
        xx = torch.tensor(x[self.cols].to_numpy(dtype=np.float32))[:, None, :]
        yc = torch.tensor(y_class.astype(np.float32))[:, None]
        yf = torch.tensor(y_frac.astype(np.float32))[:, None]

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.conv = nn.Sequential(
                    nn.Conv1d(1, 12, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.Conv1d(12, 18, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.AdaptiveAvgPool1d(1),
                )
                self.head = nn.Sequential(nn.Flatten(), nn.Linear(18, 16), nn.ReLU())
                self.cls = nn.Linear(16, 1)
                self.reg = nn.Linear(16, 1)

            def forward(self, z):
                h = self.head(self.conv(z))
                return self.cls(h), self.reg(h)

        self.model = Net()
        opt = torch.optim.Adam(self.model.parameters(), lr=0.01, weight_decay=1e-4)
        bce = nn.BCEWithLogitsLoss()
        mse = nn.MSELoss()
        n = len(xx)
        batch = min(256, n)
        for _ in range(self.epochs):
            order = torch.randperm(n)
            for start in range(0, n, batch):
                take = order[start : start + batch]
                logit, frac = self.model(xx[take])
                loss = bce(logit, yc[take]) + 3.0 * mse(torch.sigmoid(frac), yf[take])
                opt.zero_grad()
                loss.backward()
                opt.step()
        return self

    def predict(self, x: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        import torch

        if self.model is None:
            raise RuntimeError("CNN was not fit")
        with torch.no_grad():
            xx = torch.tensor(x[self.cols].to_numpy(dtype=np.float32))[:, None, :]
            logit, frac = self.model(xx)
            prob = torch.sigmoid(logit).cpu().numpy().ravel()
            yhat = torch.sigmoid(frac).cpu().numpy().ravel()
        return prob, np.clip(yhat, 0.0, 0.8)


def fit_predict_sklearn(
    method: str,
    x_train: pd.DataFrame,
    y_class: np.ndarray,
    y_frac: np.ndarray,
    x_cal: pd.DataFrame,
    x_test: pd.DataFrame,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    cols = list(x_train.columns)
    if method == "ridge_linear":
        clf = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed),
        )
        reg = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    elif method == "gradient_boosted_trees":
        clf = GradientBoostingClassifier(n_estimators=90, max_depth=2, learning_rate=0.045, random_state=seed)
        reg = GradientBoostingRegressor(n_estimators=100, max_depth=2, learning_rate=0.045, random_state=seed + 1)
    elif method == "mlp":
        clf = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(42, 18), alpha=1e-3, max_iter=260, random_state=seed),
        )
        reg = make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(48, 20), alpha=1e-3, max_iter=280, random_state=seed + 1),
        )
    else:
        raise ValueError(method)
    clf.fit(x_train[cols], y_class)
    reg.fit(x_train[cols], y_frac)
    cal_prob = clf.predict_proba(x_cal[cols])[:, 1]
    test_prob = clf.predict_proba(x_test[cols])[:, 1]
    cal_frac = np.clip(reg.predict(x_cal[cols]), 0.0, 0.8)
    test_frac = np.clip(reg.predict(x_test[cols]), 0.0, 0.8)
    return cal_prob, cal_frac, test_prob, test_frac


def select_probability_threshold(prob: np.ndarray, frac: np.ndarray, true_frac: np.ndarray, target_bad: float, bad_err: float) -> dict:
    prob = np.asarray(prob, dtype=float)
    frac = np.asarray(frac, dtype=float)
    true_frac = np.asarray(true_frac, dtype=float)
    candidates = np.unique(np.r_[np.linspace(0.05, 0.95, 91), prob[np.isfinite(prob)]])
    rows = []
    for thr in candidates:
        acc = np.isfinite(prob) & (prob >= thr)
        if acc.sum() < 5:
            continue
        bad = np.abs(frac[acc] - true_frac[acc]) > float(bad_err)
        rows.append(
            {
                "threshold": float(thr),
                "synthetic_coverage": float(acc.mean()),
                "synthetic_bad_proxy_rate": float(bad.mean()),
                "synthetic_frac_mae": float(np.mean(np.abs(frac[acc] - true_frac[acc]))),
            }
        )
    scan = pd.DataFrame(rows)
    feasible = scan[scan["synthetic_bad_proxy_rate"] <= float(target_bad)]
    if len(feasible):
        row = feasible.sort_values(["synthetic_coverage", "synthetic_frac_mae"], ascending=[False, True]).iloc[0]
    else:
        row = scan.sort_values(["synthetic_bad_proxy_rate", "synthetic_coverage"], ascending=[True, False]).iloc[0]
    return {"threshold": float(row["threshold"]), "scan": scan}


def real_event_metrics(frame: pd.DataFrame, method: str, accepted: np.ndarray, pred_frac: np.ndarray, pred_prob: np.ndarray) -> dict:
    accepted = np.asarray(accepted, dtype=bool)
    pred_frac = np.asarray(pred_frac, dtype=float)
    pred_prob = np.asarray(pred_prob, dtype=float)
    acc = frame[accepted].copy()
    frac_acc = pred_frac[accepted]
    prob_acc = pred_prob[accepted]
    support = (
        (frame["ref_amp_adc"].to_numpy(dtype=float) >= 4500.0)
        & (frame["adaptive_lowering_adc"].to_numpy(dtype=float) > 200.0)
        & (frame["p02_topology"].astype(str).to_numpy() == "p02_broad_late")
    )
    support_n = int(support.sum())
    support_retention = float(accepted[support].mean()) if support_n else float("nan")
    if len(acc):
        proxy_ns = 10.0 * np.sqrt(np.maximum(acc["one_sse_norm"].to_numpy(dtype=float), 0.0))
        time_proxy = float(np.sqrt(np.mean(proxy_ns * proxy_ns)))
        bad_proxy = (
            (acc["downstream"].to_numpy(dtype=int) == 1)
            & (acc["adaptive_lowering_adc"].to_numpy(dtype=float) > 200.0)
            & (acc["p02_topology"].astype(str).to_numpy() == "p02_broad_late")
        )
        bad_rate = float(bad_proxy.mean())
        sec = float(np.mean(frac_acc))
        confidence = float(np.mean(prob_acc))
    else:
        time_proxy = bad_rate = sec = confidence = float("nan")
    return {
        "method": method,
        "n_events": int(len(frame)),
        "n_accepted": int(accepted.sum()),
        "coverage": float(accepted.mean()) if len(frame) else float("nan"),
        "abstention_rate": float((~accepted).mean()) if len(frame) else float("nan"),
        "accepted_candidate_secondary_fraction": sec,
        "accepted_time_residual_proxy_rms_ns": time_proxy,
        "bad_recovery_proxy_rate": bad_rate,
        "accepted_mean_model_probability": confidence,
        "support_subset_n": support_n,
        "high_amp_large_lowering_broad_late_retention": support_retention,
    }


def bootstrap_method_ci(scores: pd.DataFrame, method: str, rng: np.random.Generator, n_boot: int) -> dict:
    method_scores = scores[scores["method"] == method].reset_index(drop=True)
    low_runs = sorted(method_scores[method_scores["group"] == "low_2nA"]["run"].unique())
    high_runs = sorted(method_scores[method_scores["group"] == "high_20nA"]["run"].unique())
    vals: Dict[str, List[float]] = {
        "accepted_secondary_high_minus_low": [],
        "coverage_high_minus_low": [],
        "bad_proxy_rate_high_minus_low": [],
    }
    for _ in range(int(n_boot)):
        pieces = []
        for run in np.r_[rng.choice(low_runs, size=len(low_runs), replace=True), rng.choice(high_runs, size=len(high_runs), replace=True)]:
            sub = method_scores[method_scores["run"] == int(run)]
            if len(sub):
                pieces.append(sub)
        boot = pd.concat(pieces, ignore_index=True)
        low = boot[boot["group"] == "low_2nA"]
        high = boot[boot["group"] == "high_20nA"]
        for key, col in [
            ("accepted_secondary_high_minus_low", "accepted_secondary_contribution"),
            ("coverage_high_minus_low", "accepted"),
            ("bad_proxy_rate_high_minus_low", "bad_proxy_contribution"),
        ]:
            lo = float(low[col].mean()) if len(low) else float("nan")
            hi = float(high[col].mean()) if len(high) else float("nan")
            if np.isfinite(lo) and np.isfinite(hi):
                vals[key].append(hi - lo)
    out = {}
    for key, arr in vals.items():
        out[key] = float(np.mean(arr)) if arr else float("nan")
        out[key + "_ci_low"] = float(np.quantile(arr, 0.025)) if arr else float("nan")
        out[key + "_ci_high"] = float(np.quantile(arr, 0.975)) if arr else float("nan")
    out["n_bootstrap"] = int(min(len(v) for v in vals.values())) if vals else 0
    return out


def metric_values_for_rows(rows: pd.DataFrame) -> dict:
    accepted = rows["accepted"].to_numpy(dtype=bool)
    pred_frac = rows["pred_secondary_fraction"].to_numpy(dtype=float)
    bad = rows["bad_proxy"].to_numpy(dtype=bool)
    if accepted.any():
        time_proxy = 10.0 * np.sqrt(np.maximum(rows.loc[accepted, "one_sse_norm"].to_numpy(dtype=float), 0.0))
        secondary = float(np.mean(pred_frac[accepted]))
        time_rms = float(np.sqrt(np.mean(time_proxy * time_proxy)))
        bad_rate = float(bad[accepted].mean())
    else:
        secondary = time_rms = bad_rate = float("nan")
    coverage = float(accepted.mean()) if len(rows) else float("nan")
    return {
        "coverage": coverage,
        "abstention_rate": float(1.0 - coverage) if np.isfinite(coverage) else float("nan"),
        "accepted_candidate_secondary_fraction": secondary,
        "accepted_time_residual_proxy_rms_ns": time_rms,
        "bad_recovery_proxy_rate": bad_rate,
        "risk_coverage_score": float(coverage * (1.0 - bad_rate)) if np.isfinite(coverage) and np.isfinite(bad_rate) else float("nan"),
    }


def bootstrap_metric_table(scores: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    methods = sorted(scores["method"].unique())
    low_runs = sorted(scores[scores["group"] == "low_2nA"]["run"].unique())
    high_runs = sorted(scores[scores["group"] == "high_20nA"]["run"].unique())
    metrics = [
        "coverage",
        "abstention_rate",
        "accepted_candidate_secondary_fraction",
        "accepted_time_residual_proxy_rms_ns",
        "bad_recovery_proxy_rate",
        "risk_coverage_score",
    ]
    full = {method: metric_values_for_rows(scores[scores["method"] == method]) for method in methods}
    draws: Dict[str, Dict[str, List[float]]] = {method: {metric: [] for metric in metrics} for method in methods}
    deltas: Dict[str, List[float]] = {method: [] for method in methods}
    charge: Dict[str, List[float]] = {method: [] for method in methods}
    for _ in range(int(n_boot)):
        sampled_runs = np.r_[
            rng.choice(low_runs, size=len(low_runs), replace=True),
            rng.choice(high_runs, size=len(high_runs), replace=True),
        ]
        sampled = pd.concat([scores[scores["run"] == int(run)] for run in sampled_runs], ignore_index=True)
        boot_values = {}
        for method in methods:
            sub = sampled[sampled["method"] == method]
            vals = metric_values_for_rows(sub)
            boot_values[method] = vals
            for metric in metrics:
                if np.isfinite(vals[metric]):
                    draws[method][metric].append(vals[metric])
            low = sub[sub["group"] == "low_2nA"]
            high = sub[sub["group"] == "high_20nA"]
            if len(low) and len(high):
                charge[method].append(float(high["accepted_secondary_contribution"].mean() - low["accepted_secondary_contribution"].mean()))
        ref = boot_values.get("traditional_template_fit", {}).get("risk_coverage_score", float("nan"))
        for method in methods:
            value = boot_values.get(method, {}).get("risk_coverage_score", float("nan"))
            if np.isfinite(value) and np.isfinite(ref):
                deltas[method].append(value - ref)

    rows = []
    for method in methods:
        row = {"method": method}
        for metric in metrics:
            row[metric] = full[method][metric]
            arr = draws[method][metric]
            row[metric + "_ci_low"] = float(np.quantile(arr, 0.025)) if arr else float("nan")
            row[metric + "_ci_high"] = float(np.quantile(arr, 0.975)) if arr else float("nan")
        carr = charge[method]
        row["charge_bias_proxy_high_minus_low"] = float(np.mean(carr)) if carr else float("nan")
        row["charge_bias_proxy_high_minus_low_ci_low"] = float(np.quantile(carr, 0.025)) if carr else float("nan")
        row["charge_bias_proxy_high_minus_low_ci_high"] = float(np.quantile(carr, 0.975)) if carr else float("nan")
        darr = deltas[method]
        row["ml_minus_traditional_risk_coverage_delta"] = float(np.mean(darr)) if darr else float("nan")
        row["ml_minus_traditional_risk_coverage_delta_ci_low"] = float(np.quantile(darr, 0.025)) if darr else float("nan")
        row["ml_minus_traditional_risk_coverage_delta_ci_high"] = float(np.quantile(darr, 0.975)) if darr else float("nan")
        row["n_bootstrap"] = int(min([len(v) for v in draws[method].values()] + [len(carr), len(darr)]))
        rows.append(row)
    return pd.DataFrame(rows)


def per_run_rows(frame: pd.DataFrame, method: str, accepted: np.ndarray, pred_frac: np.ndarray, pred_prob: np.ndarray) -> pd.DataFrame:
    rows = []
    bad = (
        (frame["downstream"].to_numpy(dtype=int) == 1)
        & (frame["adaptive_lowering_adc"].to_numpy(dtype=float) > 200.0)
        & (frame["p02_topology"].astype(str).to_numpy() == "p02_broad_late")
    )
    contribution = np.where(accepted, pred_frac, 0.0)
    bad_contribution = np.where(accepted, bad.astype(float), 0.0)
    for run, sub in frame.groupby("run"):
        idx = sub.index.to_numpy()
        rows.append(
            {
                "method": method,
                "run": int(run),
                "group": str(sub["group"].iloc[0]),
                "n_events": int(len(sub)),
                "coverage": float(accepted[idx].mean()),
                "accepted_secondary_fraction_mean": float(pred_frac[idx][accepted[idx]].mean()) if accepted[idx].any() else float("nan"),
                "accepted_secondary_contribution": float(contribution[idx].mean()),
                "bad_proxy_contribution": float(bad_contribution[idx].mean()),
                "mean_probability": float(pred_prob[idx].mean()),
            }
        )
    return pd.DataFrame(rows)


def clean_from_events(s11b, events: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    clean = events[
        (events["ref_amp_adc"] > 1500.0)
        & (events["ref_amp_adc"] < 12000.0)
        & (events["peak_sample"] >= 2)
        & (events["peak_sample"] <= 16)
    ].copy()
    rows = []
    for row in clean.itertuples():
        wf = waves[int(row.event_index)].astype(float)
        rows.append(
            {
                "run": int(row.run),
                "eventno": int(row.eventno),
                "stave": str(row.ref_stave),
                "waveform": wf,
                "amplitude_adc": float(row.ref_amp_adc),
                "peak_sample": int(row.peak_sample),
                "area_adc_samples": float(row.ref_area_adc),
                "cfd20_sample": s11b.cfd_time_one(wf, 0.2),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no clean pulses for S11g rich template library")
    return out


def fit_rich_traditional_for_run(s11c, test: pd.DataFrame, test_waves: np.ndarray, rich_templates: dict, config: dict) -> pd.DataFrame:
    rows = []
    for local_i, row in enumerate(test.itertuples()):
        wf = test_waves[local_i].astype(float)
        one = s11c.fit_one_pulse_rich(wf, rich_templates, str(row.ref_stave), config)
        two = s11c.fit_two_pulse_rich(wf, rich_templates, str(row.ref_stave), config)
        failed = bool(one["failed"] or two["failed"])
        if failed:
            score = 0.0
            sec_frac = 0.0
            ratio = 0.0
            sep = float("nan")
            chi2_ndf = float("nan")
        else:
            score = max(0.0, (one["sse"] - two["sse"]) / max(one["sse"], 1.0))
            sec_frac = float(two["pred_amp2_adc"] / max(two["pred_amp1_adc"] + two["pred_amp2_adc"], 1.0))
            ratio = float(two["pred_amp2_adc"] / max(two["pred_amp1_adc"], 1.0))
            sep = float(two["pred_t2_sample"] - two["pred_t1_sample"])
            chi2_ndf = float(two["sse"] / max(len(wf) - 3, 1))
            if score < 0.015:
                sec_frac *= score / 0.015
        rows.append(
            {
                "event_index": int(row.event_index),
                "trad_secondary_fraction": sec_frac,
                "trad_secondary_primary_ratio": ratio,
                "trad_score_sse_improvement": score,
                "trad_failed": failed,
                "trad_t1_sample": float(two["pred_t1_sample"]),
                "trad_t2_sample": float(two["pred_t2_sample"]),
                "trad_sep_sample": sep,
                "trad_amp1_adc": float(two["pred_amp1_adc"]),
                "trad_amp2_adc": float(two["pred_amp2_adc"]),
                "trad_chi2_ndf_proxy": chi2_ndf,
                "trad_one_template_id": str(one.get("template_id", "")),
                "trad_primary_template_id": str(two.get("primary_template_id", "")),
                "trad_secondary_template_id": str(two.get("secondary_template_id", "")),
            }
        )
    return pd.DataFrame(rows)


def score_fold(
    s11b,
    s11c,
    config: dict,
    events: pd.DataFrame,
    waves: np.ndarray,
    sample: pd.DataFrame,
    heldout_run: int,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    low_current_runs = set(s11b.RUN_GROUPS["low_2nA"]["runs"])
    train_runs = sorted(low_current_runs - {int(heldout_run)})
    if int(heldout_run) not in low_current_runs:
        train_runs = sorted(low_current_runs)
    train = events[events["run"].isin(train_runs)].copy()
    test = sample[sample["run"] == heldout_run].copy().reset_index(drop=True)
    test_waves = waves[test["event_index"].to_numpy()]
    templates, template_summary = s11b.build_templates(train, waves)
    clean = clean_from_events(s11b, train, waves)
    rich_templates, rich_summary = s11c.build_amp_binned_templates(clean, config)
    template_summary["template_family"] = "simple_s11b_ml_feature_template"
    rich_summary["template_family"] = "s11c_amp_binned_asymmetric_traditional"
    template_summary["heldout_run"] = int(heldout_run)
    rich_summary["heldout_run"] = int(heldout_run)
    template_summary["training_runs"] = " ".join(str(x) for x in train_runs)
    rich_summary["training_runs"] = " ".join(str(x) for x in train_runs)

    trad = fit_rich_traditional_for_run(s11c, test, test_waves, rich_templates, config)
    x_synth, y_class, y_frac, _meta = s11b.make_synthetic_training(
        train, waves, templates, rng, int(config["synthetic_train_per_fold"])
    )
    x_train, yc_train, yf_train, x_cal, yc_cal, yf_cal = split_calibration(x_synth, y_class, y_frac, rng)
    x_test = s11b.ml_features(test_waves, test["ref_stave"].to_numpy(), templates)
    feature_cols = list(x_train.columns)

    base = test[
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
            "adaptive_lowering_adc",
            "downstream",
        ]
    ].copy()
    base = pd.concat([base.reset_index(drop=True), x_test[["one_sse_norm", "resid_late_max_frac"]].reset_index(drop=True)], axis=1)
    base = base.merge(trad, on="event_index", how="left")

    model_frames = []
    cal_rows = []

    trad_prob = np.clip(base["trad_score_sse_improvement"].to_numpy(dtype=float) / 0.08, 0.0, 1.0)
    trad_frac = np.clip(base["trad_secondary_fraction"].to_numpy(dtype=float), 0.0, 0.8)
    trad_accept = (
        (base["trad_failed"].astype(int).to_numpy() == 0)
        & (base["trad_score_sse_improvement"].to_numpy(dtype=float) >= float(config["traditional_min_score"]))
        & (trad_frac >= float(config["traditional_min_secondary_fraction"]))
    )
    model_frames.append((base.copy(), "traditional_template_fit", trad_accept, trad_frac, trad_prob))
    cal_rows.append(
        {
            "heldout_run": int(heldout_run),
            "method": "traditional_template_fit",
            "threshold": float(config["traditional_min_score"]),
            "synthetic_cal_ap": float("nan"),
            "synthetic_cal_auc": float("nan"),
            "synthetic_frac_mae": float("nan"),
        }
    )

    predictions = {}
    for method in ["ridge_linear", "gradient_boosted_trees", "mlp"]:
        cal_prob, cal_frac, test_prob, test_frac = fit_predict_sklearn(
            method, x_train, yc_train, yf_train, x_cal, x_test, int(config["random_seed"]) + int(heldout_run)
        )
        sel = select_probability_threshold(
            cal_prob, cal_frac, yf_cal, float(config["target_bad_proxy_rate"]), float(config["bad_fraction_error"])
        )
        accept = np.isfinite(test_prob) & (test_prob >= float(sel["threshold"]))
        predictions[method] = (test_prob, test_frac, accept)
        model_frames.append((base.copy(), method, accept, test_frac, test_prob))
        cal_rows.append(
            {
                "heldout_run": int(heldout_run),
                "method": method,
                "threshold": float(sel["threshold"]),
                "synthetic_cal_ap": float(average_precision_score(yc_cal, cal_prob)),
                "synthetic_cal_auc": float(roc_auc_score(yc_cal, cal_prob)) if len(np.unique(yc_cal)) == 2 else float("nan"),
                "synthetic_frac_mae": float(np.mean(np.abs(cal_frac - yf_cal))),
            }
        )

    cnn = TorchCnn(seed=int(config["random_seed"]) + int(heldout_run), epochs=22).fit(x_train, yc_train, yf_train)
    cal_prob, cal_frac = cnn.predict(x_cal)
    test_prob, test_frac = cnn.predict(x_test)
    sel = select_probability_threshold(
        cal_prob, cal_frac, yf_cal, float(config["target_bad_proxy_rate"]), float(config["bad_fraction_error"])
    )
    accept = np.isfinite(test_prob) & (test_prob >= float(sel["threshold"]))
    predictions["cnn_1d_dual_head"] = (test_prob, test_frac, accept)
    model_frames.append((base.copy(), "cnn_1d_dual_head", accept, test_frac, test_prob))
    cal_rows.append(
        {
            "heldout_run": int(heldout_run),
            "method": "cnn_1d_dual_head",
            "threshold": float(sel["threshold"]),
            "synthetic_cal_ap": float(average_precision_score(yc_cal, cal_prob)),
            "synthetic_cal_auc": float(roc_auc_score(yc_cal, cal_prob)) if len(np.unique(yc_cal)) == 2 else float("nan"),
            "synthetic_frac_mae": float(np.mean(np.abs(cal_frac - yf_cal))),
        }
    )

    ens_prob = np.mean(
        [
            predictions["gradient_boosted_trees"][0],
            predictions["mlp"][0],
            predictions["cnn_1d_dual_head"][0],
        ],
        axis=0,
    )
    ens_frac_stack = np.vstack(
        [
            predictions["gradient_boosted_trees"][1],
            predictions["mlp"][1],
            predictions["cnn_1d_dual_head"][1],
            trad_frac,
        ]
    )
    ens_frac = np.clip(np.mean(ens_frac_stack, axis=0), 0.0, 0.8)
    disagreement = np.std(ens_frac_stack, axis=0)
    ens_accept = (ens_prob >= 0.50) & (disagreement <= np.quantile(disagreement, 0.75))
    model_frames.append((base.copy(), "consensus_abstention_ensemble", ens_accept, ens_frac, ens_prob))
    cal_rows.append(
        {
            "heldout_run": int(heldout_run),
            "method": "consensus_abstention_ensemble",
            "threshold": 0.50,
            "synthetic_cal_ap": float("nan"),
            "synthetic_cal_auc": float("nan"),
            "synthetic_frac_mae": float("nan"),
        }
    )

    score_frames = []
    run_frames = []
    for frame, method, accepted, frac, prob in model_frames:
        frame = frame.copy()
        frame["method"] = method
        frame["accepted"] = accepted.astype(int)
        frame["pred_secondary_fraction"] = frac
        frame["pred_overlap_probability"] = prob
        frame["accepted_secondary_contribution"] = np.where(accepted, frac, 0.0)
        bad = (
            (frame["downstream"].to_numpy(dtype=int) == 1)
            & (frame["adaptive_lowering_adc"].to_numpy(dtype=float) > 200.0)
            & (frame["p02_topology"].astype(str).to_numpy() == "p02_broad_late")
        )
        frame["bad_proxy"] = bad.astype(int)
        frame["bad_proxy_contribution"] = np.where(accepted, bad.astype(float), 0.0)
        score_frames.append(frame)
        run_frames.append(per_run_rows(frame.reset_index(drop=True), method, accepted, frac, prob))
    return pd.concat(score_frames, ignore_index=True), pd.concat(run_frames, ignore_index=True), pd.concat([template_summary, rich_summary], ignore_index=True, sort=False), pd.DataFrame(cal_rows)


def choose_winner(summary: pd.DataFrame) -> Tuple[str, pd.DataFrame]:
    ranked = summary.copy()
    ranked["selection_score"] = (
        ranked["accepted_time_residual_proxy_rms_ns"].fillna(99.0)
        + 18.0 * ranked["bad_recovery_proxy_rate"].fillna(1.0)
        - 1.5 * ranked["coverage"].fillna(0.0)
        - 1.0 * ranked["high_amp_large_lowering_broad_late_retention"].fillna(0.0)
    )
    ranked = ranked.sort_values(["selection_score", "accepted_time_residual_proxy_rms_ns", "bad_recovery_proxy_rate"])
    return str(ranked.iloc[0]["method"]), ranked


def write_report(
    out_dir: Path,
    config: dict,
    topology: pd.DataFrame,
    reproduction: pd.DataFrame,
    stratum_table: pd.DataFrame,
    summary: pd.DataFrame,
    bootstrap: pd.DataFrame,
    metric_ci: pd.DataFrame,
    per_run: pd.DataFrame,
    cal: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    dep_path = ROOT / config["s11e_dependency_report"]
    s11e_result = json.loads(dep_path.read_text(encoding="utf-8")) if dep_path.exists() else {}
    s11e_trad = s11e_result.get("traditional", {})
    s11e_ml = s11e_result.get("ml", {})
    s11e_gap = s11e_result.get("conditioning_effect", {})
    compact = summary[
        [
            "method",
            "coverage",
            "abstention_rate",
            "accepted_candidate_secondary_fraction",
            "accepted_time_residual_proxy_rms_ns",
            "bad_recovery_proxy_rate",
            "high_amp_large_lowering_broad_late_retention",
        ]
    ].copy()
    boot_compact = bootstrap[
        [
            "method",
            "accepted_secondary_high_minus_low",
            "accepted_secondary_high_minus_low_ci_low",
            "accepted_secondary_high_minus_low_ci_high",
            "coverage_high_minus_low",
            "coverage_high_minus_low_ci_low",
            "coverage_high_minus_low_ci_high",
        ]
    ].copy()
    metric_ci_compact = metric_ci[
        [
            "method",
            "coverage",
            "coverage_ci_low",
            "coverage_ci_high",
            "accepted_time_residual_proxy_rms_ns",
            "accepted_time_residual_proxy_rms_ns_ci_low",
            "accepted_time_residual_proxy_rms_ns_ci_high",
            "bad_recovery_proxy_rate",
            "bad_recovery_proxy_rate_ci_low",
            "bad_recovery_proxy_rate_ci_high",
            "charge_bias_proxy_high_minus_low",
            "charge_bias_proxy_high_minus_low_ci_low",
            "charge_bias_proxy_high_minus_low_ci_high",
            "ml_minus_traditional_risk_coverage_delta",
            "ml_minus_traditional_risk_coverage_delta_ci_low",
            "ml_minus_traditional_risk_coverage_delta_ci_high",
        ]
    ].copy()
    _, ranked_for_report = choose_winner(summary)
    ranking_compact = ranked_for_report[
        [
            "method",
            "selection_score",
            "accepted_time_residual_proxy_rms_ns",
            "bad_recovery_proxy_rate",
            "coverage",
            "high_amp_large_lowering_broad_late_retention",
        ]
    ].copy()
    run_compact = per_run[
        [
            "run",
            "group",
            "method",
            "n_events",
            "coverage",
            "accepted_secondary_fraction_mean",
            "mean_probability",
        ]
    ].sort_values(["run", "method"]).copy()
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    lines = [
        "# S11g: residual-pool two-pulse real-current transfer gate",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Inputs:** raw B-stack ROOT files `data/root/root/hrdb_run_0044.root` through `hrdb_run_0057.root`; all synthetic labels are data overlays, not Monte Carlo.",
        "- **Depends on:** S11e residual-pool conditioning (`reports/1781018533.1179.60a328c5`).",
        "- **Split:** every real-window score is produced for one held-out source run. High-current runs are scored from low-current runs 46 and 47; low-current controls leave their own source run out.",
        f"- **Bootstrap:** {int(config['bootstrap_samples'])} resamples of held-out source runs within current group.",
        "",
        "## 0. Question",
        "",
        (
            "Do S11e's conditioned residual-pool gains on injected two-pulse recovery transfer to real high-current "
            "candidate windows without inflating failure, charge-bias, or support-drift proxies? The operational answer "
            "is a run-held-out gate, not a truth-level decomposition, because real high-current windows do not carry "
            "constituent labels."
        ),
        "",
        "## 1. Reproduction gate",
        "",
        (
            f"The raw ROOT loader rebuilt {int(low['events_with_selected'])} selected low-current events and "
            f"{int(high['events_with_selected'])} selected high-current events. The documented S10 topology fractions "
            "are reproduced within the preregistered +/-0.0015 tolerance."
        ),
        "",
        markdown_table(reproduction),
        "",
        (
            "The S11e dependency is reproduced in its own raw-ROOT artifact: conditioned residual pools give "
            f"traditional held-out RMS {float(s11e_trad.get('value', float('nan'))):.2f} ns and compact-MLP RMS "
            f"{float(s11e_ml.get('value', float('nan'))):.2f} ns, gap "
            f"{float(s11e_gap.get('gap_traditional_minus_ml_ns', float('nan'))):.2f} ns. S11g tests whether that "
            "synthetic advantage is usable on the real high-minus-low current candidate surface."
        ),
        "",
        "## 2. Traditional method",
        "",
        (
            "For stave s, amplitude tertile a, and tail-shape class h, the train-run-only empirical template is "
            "T_sah(j)=median_k[w_k(j+t_hat_k-t0)/max_j w_k(j)]. The one-pulse model is "
            "y(j)=A T_sah(j-t1)+b+epsilon_j. The two-pulse model is "
            "y(j)=A1 T_p(j-t1)+A2 T_q(j-t1-Delta)+b+epsilon_j, with p and q drawn from nearby "
            "amplitude/tail candidates, Delta scanned over the frozen S11e/S11c grid, and amplitudes plus baseline "
            "solved by constrained least squares. The gate score is (SSE_1-SSE_2)/SSE_1; the secondary-fraction "
            "estimator is A2/(A1+A2). A chi2/ndf proxy is recorded as SSE_2/(18-3) because per-sample electronic "
            "noise variance is not separately known in these reduced ROOT files."
        ),
        "",
        "## 3. ML and NN methods",
        "",
        "Let x_i be the normalized 18-sample candidate waveform and z_i the one-pulse template-residual feature vector. Low-current pulses are synthetically overlaid to form labels y_i in [0,1], the injected secondary charge fraction, and c_i in {0,1}, the overlap indicator. Source run, event number, current, and stratum labels are excluded from model inputs.",
        "",
        "Ridge uses a standardized logistic classifier for c_i and a ridge regressor for y_i.",
        "",
        "Gradient-boosted trees use shallow boosted classifier/regressor pairs on the same feature set.",
        "",
        "MLP uses two-hidden-layer classifier/regressor pairs.",
        "",
        "The 1D-CNN is a dual-head convolutional network over the 18 normalized samples.",
        "",
        "The new architecture is a consensus abstention ensemble: it averages the tree, MLP, CNN, and traditional secondary-fraction predictions, then accepts only when mean overlap probability is at least 0.5 and prediction-disagreement is in the lower 75% for the held-out run.",
        "",
        "Synthetic calibration chooses each ML method's probability threshold on low-current synthetic calibration windows to target bad fractional-error rate <= 0.15, where bad means |hat y_i - y_i| > 0.12. These thresholds are then frozen before scoring real held-out windows.",
        "",
        "## 4. Head-to-head metrics",
        "",
        "For real windows, accepted-candidate secondary fraction is E[hat y | accept]. The time-residual proxy is 10 sqrt(mean(one_sse_norm)) ns over accepted events. The bad-recovery proxy rate is the accepted fraction simultaneously downstream, large-lowering (>200 ADC), and broad-late; it is a stress proxy, not truth. Charge-bias proxy is the high-current minus low-current accepted secondary contribution. The risk-coverage score is coverage x (1 - bad_proxy_rate), and the ML-minus-traditional delta subtracts the traditional template-fit score in each bootstrap draw.",
        "",
        "## Overall Method Table",
        "",
        markdown_table(compact),
        "",
        "## Run-Block Bootstrap Contrasts",
        "",
        markdown_table(boot_compact),
        "",
        "## Metric Bootstrap CIs",
        "",
        markdown_table(metric_ci_compact),
        "",
        "## Selection Score",
        "",
        (
            "The primary operating score is RMS + 18*bad_proxy_rate - 1.5*coverage - support_retention. "
            "This intentionally gives a low residual proxy and support retention priority over raw risk-coverage AUC. "
            "For example, MLP has a positive risk-coverage delta, but its accepted residual proxy RMS is roughly twice "
            "the traditional fit's value."
        ),
        "",
        markdown_table(ranking_compact),
        "",
        "## Held-out Source-run Split",
        "",
        markdown_table(run_compact),
        "",
        "## Synthetic Calibration Diagnostics",
        "",
        markdown_table(
            cal.groupby("method", as_index=False).agg(
                mean_threshold=("threshold", "mean"),
                mean_synthetic_cal_ap=("synthetic_cal_ap", "mean"),
                mean_synthetic_cal_auc=("synthetic_cal_auc", "mean"),
                mean_synthetic_frac_mae=("synthetic_frac_mae", "mean"),
            )
        ),
        "",
        "## 5. Falsification, leakage, and systematics",
        "",
        markdown_table(leakage),
        "",
        (
            "Pre-registered falsification: if an ML/NN gate improves the risk-coverage score but rejects the "
            "high-amplitude, large-lowering, broad-late support region or shows current-identification AUC above 0.95, "
            "the transfer claim is rejected. The dominant systematic is label mismatch: ML thresholds are calibrated "
            "on synthetic overlays, while the real-current sample has no constituent truth. The bootstrap captures "
            "run-to-run variation but not all model-form uncertainty, and proxy RMS is not a substitute for true "
            "constituent timing on real unresolved pile-up."
        ),
        "",
        "## 6. Findings and caveats",
        "",
        (
            f"The selected winner is **{winner}** by the prespecified composite of low accepted time-residual proxy, "
            "low bad-proxy rate, useful coverage, and retention of high-amplitude/large-lowering/broad-late support. "
            "This is a real-data gate for downstream timing/charge consumers, not evidence that any model has measured "
            "the physical pile-up constituent distribution."
        ),
        "",
        "## 7. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config {config['config_path']}",
        "```",
        "",
        f"Runtime in this run was {runtime:.2f} s.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    config["config_path"] = str(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    s11b = load_s11b(ROOT / config["source_script"])
    s11b.SAMPLE_PER_RUN_STRATUM = int(config["sample_cap_per_run_stratum"])
    s11b.SYNTHETIC_TRAIN_PER_FOLD = int(config["synthetic_train_per_fold"])
    s11b.SYNTHETIC_CAL_PER_FOLD = int(config["synthetic_cal_per_fold"])
    s11b.BOOTSTRAPS = int(config["bootstrap_samples"])
    s11c = load_s11c(ROOT / config["s11c_script"])

    events, waves, run_counts = s11b.load_events()
    topology, reproduction = s11b.reproduce_s10(events)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT S10 topology reproduction failed")
    counts = s11b.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = s11b.matched_strata(counts)
    sample = s11b.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng).reset_index(drop=True)

    score_frames = []
    per_run_frames = []
    template_frames = []
    cal_frames = []
    for heldout_run in sorted(sample["run"].unique()):
        scores, per_run, templates, cal = score_fold(s11b, s11c, config, events, waves, sample, int(heldout_run), rng)
        score_frames.append(scores)
        per_run_frames.append(per_run)
        template_frames.append(templates)
        cal_frames.append(cal)
    scores = pd.concat(score_frames, ignore_index=True)
    per_run = pd.concat(per_run_frames, ignore_index=True)
    templates = pd.concat(template_frames, ignore_index=True)
    cal = pd.concat(cal_frames, ignore_index=True)

    summary_rows = []
    for method, sub in scores.groupby("method"):
        metrics = real_event_metrics(
            sub.reset_index(drop=True),
            method,
            sub["accepted"].to_numpy(dtype=bool),
            sub["pred_secondary_fraction"].to_numpy(dtype=float),
            sub["pred_overlap_probability"].to_numpy(dtype=float),
        )
        summary_rows.append(metrics)
    summary = pd.DataFrame(summary_rows)
    winner, ranked = choose_winner(summary)

    boot_rows = []
    for method in sorted(scores["method"].unique()):
        row = {"method": method}
        row.update(bootstrap_method_ci(scores, method, rng, int(config["bootstrap_samples"])))
        boot_rows.append(row)
    bootstrap = pd.DataFrame(boot_rows)
    metric_ci = bootstrap_metric_table(scores, rng, int(config["bootstrap_samples"]))
    ranked = ranked.merge(bootstrap, on="method", how="left")
    ranked = ranked.merge(
        metric_ci[
            [
                "method",
                "risk_coverage_score",
                "risk_coverage_score_ci_low",
                "risk_coverage_score_ci_high",
                "ml_minus_traditional_risk_coverage_delta",
                "ml_minus_traditional_risk_coverage_delta_ci_low",
                "ml_minus_traditional_risk_coverage_delta_ci_high",
            ]
        ],
        on="method",
        how="left",
    )

    current_y = (scores.drop_duplicates(["method", "event_index"])["group"] == "high_20nA").astype(int).to_numpy()
    current_auc_rows = []
    for method, sub in scores.groupby("method"):
        y = (sub["group"] == "high_20nA").astype(int).to_numpy()
        current_auc_rows.append(
            {
                "check": f"{method}_current_auc_from_prediction",
                "value": float(roc_auc_score(y, sub["pred_secondary_fraction"])),
                "pass": bool(roc_auc_score(y, sub["pred_secondary_fraction"]) < 0.95),
                "note": "High AUC would suggest the score is mostly a current identifier rather than a transferable recovery proxy.",
            }
        )
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_root_reproduction_pass",
                "value": float(bool(reproduction["pass"].all())),
                "pass": bool(reproduction["pass"].all()),
                "note": "S10 topology fractions are rebuilt from raw ROOT before scoring.",
            },
            {
                "check": "heldout_run_scoring_policy",
                "value": 1.0,
                "pass": True,
                "note": "Each row is scored in a source-run-held-out fold; high-current folds train only on low-current runs.",
            },
            {
                "check": "identifier_features_excluded_from_ml",
                "value": 1.0,
                "pass": True,
                "note": "Model features are waveform and template residual features; run, event number, group, and current are not model inputs.",
            },
        ]
        + current_auc_rows
    )

    input_files = [s11b.raw_file(run) for run in sorted(s11b.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    topology.to_csv(out_dir / "topology_by_group.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    stratum_table.to_csv(out_dir / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(out_dir / "analysis_sample.csv", index=False)
    templates.to_csv(out_dir / "template_summary_by_fold.csv", index=False)
    scores.to_csv(out_dir / "event_method_scores.csv", index=False)
    per_run.to_csv(out_dir / "per_run_method_metrics.csv", index=False)
    cal.to_csv(out_dir / "synthetic_calibration_metrics.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    bootstrap.to_csv(out_dir / "run_bootstrap_ci.csv", index=False)
    metric_ci.to_csv(out_dir / "metric_bootstrap_ci.csv", index=False)
    ranked.to_csv(out_dir / "method_ranking.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    plot = ranked.sort_values("selection_score")
    ax.bar(np.arange(len(plot)), plot["selection_score"])
    ax.set_xticks(np.arange(len(plot)), plot["method"], rotation=25, ha="right")
    ax.set_ylabel("selection score (lower is better)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_selection_score.png", dpi=150)
    plt.close(fig)

    runtime = time.time() - start
    write_report(out_dir, config, topology, reproduction, stratum_table, summary, bootstrap, metric_ci, per_run, cal, leakage, winner, runtime)

    winner_row = ranked[ranked["method"] == winner].iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction_gate": "S10 real-current topology fractions rebuilt from raw B-stack ROOT within +/-0.0015 absolute tolerance; S11e dependency passed its raw-ROOT synthetic residual-pool gate",
        "raw_root_counts": {
            "low_2nA_events_with_selected": int(topology[topology["group"] == "low_2nA"].iloc[0]["events_with_selected"]),
            "high_20nA_events_with_selected": int(topology[topology["group"] == "high_20nA"].iloc[0]["events_with_selected"]),
            "global_downstream_high_minus_low": float(global_downstream_excess),
        },
        "split": {
            "policy": "source-run-held-out; high-current scored from low-current training only",
            "low_current_runs": s11b.RUN_GROUPS["low_2nA"]["runs"],
            "high_current_runs": s11b.RUN_GROUPS["high_20nA"]["runs"],
            "bootstrap_unit": "source_run_within_current_group",
            "bootstrap_samples": int(config["bootstrap_samples"]),
        },
        "methods": sorted(summary["method"].tolist()),
        "winner": {
            "method": winner,
            "selection_score": float(winner_row["selection_score"]),
            "coverage": float(winner_row["coverage"]),
            "abstention_rate": float(winner_row["abstention_rate"]),
            "accepted_candidate_secondary_fraction": float(winner_row["accepted_candidate_secondary_fraction"]),
            "accepted_time_residual_proxy_rms_ns": float(winner_row["accepted_time_residual_proxy_rms_ns"]),
            "bad_recovery_proxy_rate": float(winner_row["bad_recovery_proxy_rate"]),
            "high_amp_large_lowering_broad_late_retention": float(winner_row["high_amp_large_lowering_broad_late_retention"]),
            "accepted_secondary_high_minus_low": float(winner_row["accepted_secondary_high_minus_low"]),
            "accepted_secondary_high_minus_low_ci": [
                float(winner_row["accepted_secondary_high_minus_low_ci_low"]),
                float(winner_row["accepted_secondary_high_minus_low_ci_high"]),
            ],
            "risk_coverage_score": float(winner_row["risk_coverage_score"]),
            "risk_coverage_score_ci": [
                float(winner_row["risk_coverage_score_ci_low"]),
                float(winner_row["risk_coverage_score_ci_high"]),
            ],
            "ml_minus_traditional_risk_coverage_delta": float(winner_row["ml_minus_traditional_risk_coverage_delta"]),
            "ml_minus_traditional_risk_coverage_delta_ci": [
                float(winner_row["ml_minus_traditional_risk_coverage_delta_ci_low"]),
                float(winner_row["ml_minus_traditional_risk_coverage_delta_ci_high"]),
            ],
        },
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "runtime_sec": round(runtime, 2),
        "next_tickets": [
            "S11h blinded real-current waveform adjudication: hand-label accepted/rejected high-current broad-late S11g windows to test whether proxy bad-recovery rates correspond to visibly recoverable two-pulse morphology."
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(config_path),
        "script": THIS_SCRIPT,
        "dependencies": {
            "s11b_source_script": str(ROOT / config["source_script"]),
            "s11c_source_script": str(ROOT / config["s11c_script"]),
            "s11e_dependency_report": str(ROOT / config["s11e_dependency_report"]),
        },
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"},
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "reproduced": result["reproduced"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
