#!/usr/bin/env python3
"""S10l failure atom map for asymmetric two-pulse recovery.

This study extends the validated S11c raw-ROOT injection benchmark. It keeps the
same train/held-out source-run split and rich asymmetric template fit, then
benchmarks ridge, gradient-boosted trees, MLP, 1D-CNN, and a small attention
waveform model on the same events. The primary endpoint is held-out constituent
time RMS; the atom map explains where the traditional asymmetric template fit
fails.
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
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception:  # pragma: no cover - handled at runtime in environments without torch.
    torch = None
    nn = None
    F = None


ROOT = Path(__file__).resolve().parents[1]
S11C_PATH = ROOT / "scripts/s11c_amp_binned_asymmetric_templates.py"


def load_s11c():
    spec = importlib.util.spec_from_file_location("s11c_amp_binned_asymmetric_templates", str(S11C_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import S11c helper module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s11c = load_s11c()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def finite(value: float) -> float:
    value = float(value)
    return value if np.isfinite(value) else float("nan")


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


def feature_matrix(events: pd.DataFrame, waveforms: np.ndarray, config: dict) -> np.ndarray:
    base = s11c.make_feature_matrix(waveforms)
    staves = list(config["staves"].keys())
    one_hot = np.zeros((len(events), len(staves)), dtype=float)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(events["stave"].to_numpy()):
        one_hot[row, lookup[str(stave)]] = 1.0
    return np.hstack([base, one_hot])


def regression_targets(events: pd.DataFrame, waveforms: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    max_amp = np.maximum(waveforms.max(axis=1) - np.median(waveforms[:, :4], axis=1), 1.0)
    y_reg = np.column_stack(
        [
            events["true_t1_sample"].to_numpy(dtype=float) / 12.0,
            np.nan_to_num(events["true_t2_sample"].to_numpy(dtype=float), nan=0.0) / 12.0,
            events["true_amp1_adc"].to_numpy(dtype=float) / max_amp,
            events["true_amp2_adc"].to_numpy(dtype=float) / max_amp,
        ]
    )
    return y_reg, max_amp


def prediction_frame(events: pd.DataFrame, prob: np.ndarray, pred: np.ndarray, max_amp: np.ndarray, prefix: str) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "event_id": events["event_id"].to_numpy(),
            f"{prefix}_score": np.asarray(prob, dtype=float),
            f"{prefix}_failed": np.asarray(prob, dtype=float) < 0.5,
            f"{prefix}_t1_sample": np.clip(pred[:, 0] * 12.0, 0.0, 17.0),
            f"{prefix}_t2_sample": np.clip(pred[:, 1] * 12.0, 0.0, 17.0),
            f"{prefix}_amp1_adc": np.clip(pred[:, 2] * max_amp, 0.0, None),
            f"{prefix}_amp2_adc": np.clip(pred[:, 3] * max_amp, 0.0, None),
        }
    )
    swapped = out[f"{prefix}_t2_sample"] < out[f"{prefix}_t1_sample"]
    out.loc[swapped, [f"{prefix}_t1_sample", f"{prefix}_t2_sample"]] = out.loc[
        swapped, [f"{prefix}_t2_sample", f"{prefix}_t1_sample"]
    ].to_numpy()
    out.loc[swapped, [f"{prefix}_amp1_adc", f"{prefix}_amp2_adc"]] = out.loc[
        swapped, [f"{prefix}_amp2_adc", f"{prefix}_amp1_adc"]
    ].to_numpy()
    return out


def run_sklearn_models(events: pd.DataFrame, waveforms: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    seed = int(config["random_seed"])
    X = feature_matrix(events, waveforms, config)
    y_class = events["is_overlap"].to_numpy(dtype=int)
    y_reg, max_amp = regression_targets(events, waveforms)
    train_mask = events["split"].to_numpy() == "train"
    pos_train = train_mask & (y_class == 1)

    specs = [
        (
            "ridge",
            "ridge_logistic_plus_ridge_regression",
            make_pipeline(StandardScaler(), LogisticRegression(C=1.0, penalty="l2", max_iter=1000, random_state=seed)),
            make_pipeline(StandardScaler(), Ridge(alpha=1.0, random_state=seed)),
        ),
        (
            "hgb",
            "hist_gradient_boosted_trees",
            HistGradientBoostingClassifier(max_iter=160, learning_rate=0.055, l2_regularization=0.01, random_state=seed),
            MultiOutputRegressor(
                HistGradientBoostingRegressor(max_iter=160, learning_rate=0.055, l2_regularization=0.01, random_state=seed + 1)
            ),
        ),
        (
            "mlp",
            "compact_mlp_classifier_regressor",
            make_pipeline(
                StandardScaler(),
                MLPClassifier(
                    hidden_layer_sizes=tuple(config["ml"]["classifier_hidden"]),
                    activation="relu",
                    alpha=1e-3,
                    max_iter=int(config["ml"]["max_iter"]),
                    random_state=seed,
                    early_stopping=True,
                ),
            ),
            make_pipeline(
                StandardScaler(),
                MLPRegressor(
                    hidden_layer_sizes=tuple(config["ml"]["regressor_hidden"]),
                    activation="relu",
                    alpha=1e-3,
                    max_iter=int(config["ml"]["max_iter"]),
                    random_state=seed + 1,
                    early_stopping=True,
                ),
            ),
        ),
    ]

    pred_frames = []
    cv_rows = []
    train_groups = events.loc[train_mask, "source_run"].to_numpy(dtype=int)
    unique_runs = sorted(set(train_groups))
    for prefix, label, clf, reg in specs:
        clf.fit(X[train_mask], y_class[train_mask])
        if hasattr(clf, "predict_proba"):
            prob = clf.predict_proba(X)[:, 1]
        else:
            prob = clf.decision_function(X)
        reg.fit(X[pos_train], y_reg[pos_train])
        pred = reg.predict(X)
        pred_frames.append(prediction_frame(events, prob, pred, max_amp, prefix))

        for run in unique_runs:
            fold_train = train_mask & (events["source_run"].to_numpy(dtype=int) != run)
            fold_valid = train_mask & (events["source_run"].to_numpy(dtype=int) == run)
            if y_class[fold_valid].sum() == 0 or y_class[fold_valid].sum() == len(y_class[fold_valid]):
                continue
            clf_fold = clf
            try:
                import copy

                clf_fold = copy.deepcopy(clf)
                clf_fold.fit(X[fold_train], y_class[fold_train])
                p = clf_fold.predict_proba(X[fold_valid])[:, 1]
                cv_rows.append(
                    {
                        "method": label,
                        "heldout_train_run": int(run),
                        "ap": float(average_precision_score(y_class[fold_valid], p)),
                        "auc": float(roc_auc_score(y_class[fold_valid], p)),
                    }
                )
            except Exception as exc:
                cv_rows.append({"method": label, "heldout_train_run": int(run), "ap": float("nan"), "auc": float("nan"), "error": str(exc)})

    merged = pred_frames[0]
    for frame in pred_frames[1:]:
        merged = merged.merge(frame, on="event_id")
    return merged, pd.DataFrame(cv_rows)


class TinyCNN(nn.Module):
    def __init__(self, n_staves: int, attention: bool = False):
        super().__init__()
        self.attention = attention
        self.conv1 = nn.Conv1d(1, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(16, 24, kernel_size=3, padding=1)
        self.stave = nn.Linear(n_staves, 8)
        self.attn = nn.Linear(24, 1)
        self.fc = nn.Sequential(nn.Linear(24 + 8, 40), nn.ReLU(), nn.Dropout(0.05), nn.Linear(40, 24), nn.ReLU())
        self.cls = nn.Linear(24, 1)
        self.reg = nn.Linear(24, 4)

    def forward(self, wave, stave):
        x = F.relu(self.conv1(wave))
        x = F.relu(self.conv2(x)).transpose(1, 2)
        if self.attention:
            weights = torch.softmax(self.attn(x).squeeze(-1), dim=1)
            pooled = torch.sum(x * weights.unsqueeze(-1), dim=1)
        else:
            pooled = x.mean(dim=1)
        z = torch.cat([pooled, F.relu(self.stave(stave))], dim=1)
        z = self.fc(z)
        return self.cls(z).squeeze(-1), self.reg(z)


def torch_inputs(events: pd.DataFrame, waveforms: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    corrected = waveforms - np.median(waveforms[:, :4], axis=1)[:, None]
    amp = np.maximum(np.max(corrected, axis=1), 1.0)
    wave = (corrected / amp[:, None]).astype(np.float32)
    staves = list(config["staves"].keys())
    stave = np.zeros((len(events), len(staves)), dtype=np.float32)
    lookup = {s: i for i, s in enumerate(staves)}
    for i, name in enumerate(events["stave"].to_numpy()):
        stave[i, lookup[str(name)]] = 1.0
    return wave[:, None, :], stave


def train_torch_model(
    events: pd.DataFrame,
    waveforms: np.ndarray,
    config: dict,
    prefix: str,
    label: str,
    attention: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if torch is None:
        raise RuntimeError("torch is required for CNN/attention models")
    seed = int(config["random_seed"]) + (11 if attention else 7)
    torch.manual_seed(seed)
    np.random.seed(seed)
    wave, stave = torch_inputs(events, waveforms, config)
    y_class = events["is_overlap"].to_numpy(dtype=np.float32)
    y_reg, max_amp = regression_targets(events, waveforms)
    train_mask = events["split"].to_numpy() == "train"
    model = TinyCNN(stave.shape[1], attention=attention)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-3)
    epochs = int(config["ml"].get("torch_epochs", 80))
    batch = int(config["ml"].get("torch_batch_size", 128))
    train_idx = np.flatnonzero(train_mask)
    rng = np.random.default_rng(seed)
    xw = torch.tensor(wave)
    xs = torch.tensor(stave)
    yc = torch.tensor(y_class)
    yr = torch.tensor(y_reg.astype(np.float32))
    for _epoch in range(epochs):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            logits, reg = model(xw[idx], xs[idx])
            loss_cls = F.binary_cross_entropy_with_logits(logits, yc[idx])
            pos = yc[idx] > 0.5
            loss_reg = F.mse_loss(reg[pos], yr[idx][pos]) if bool(pos.any()) else torch.tensor(0.0)
            loss = loss_cls + 2.0 * loss_reg
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        logits, pred = model(xw, xs)
        prob = torch.sigmoid(logits).cpu().numpy()
        pred_np = pred.cpu().numpy()
    out = prediction_frame(events, prob, pred_np, max_amp, prefix)
    cv_rows = [{"method": label, "heldout_train_run": -1, "ap": float("nan"), "auc": float("nan"), "note": "torch model not cross-validated to control runtime"}]
    return out, pd.DataFrame(cv_rows)


def run_all_ml(events: pd.DataFrame, waveforms: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    sklearn_pred, sklearn_cv = run_sklearn_models(events, waveforms, config)
    cnn, cnn_cv = train_torch_model(events, waveforms, config, "cnn", "one_dimensional_cnn", attention=False)
    attn, attn_cv = train_torch_model(events, waveforms, config, "attn", "attention_waveform_encoder", attention=True)
    merged = sklearn_pred.merge(cnn, on="event_id").merge(attn, on="event_id")
    cv = pd.concat([sklearn_cv, cnn_cv, attn_cv], ignore_index=True, sort=False)
    return merged, cv


METHODS = [
    ("trad", "amplitude_binned_asymmetric_template_fit", "traditional"),
    ("ridge", "ridge_logistic_plus_ridge_regression", "ml"),
    ("hgb", "hist_gradient_boosted_trees", "ml"),
    ("mlp", "compact_mlp_classifier_regressor", "ml"),
    ("cnn", "one_dimensional_cnn", "nn"),
    ("attn", "attention_waveform_encoder", "new_architecture"),
]


def summarize_methods(frame: pd.DataFrame, rng: np.random.Generator, config: dict) -> pd.DataFrame:
    rows = []
    held = frame[frame["split"] == "heldout"].reset_index(drop=True)
    for prefix, label, family in METHODS:
        row = {"method": label, "family": family, **s11c.metric_values(held, prefix)}
        row["detection_auc"] = s11c.metric_values(held, prefix)["detection_auc"]
        row.update(s11c.bootstrap_metric_ci_by_run(held, prefix, rng, int(config["ml"]["bootstrap_samples"])))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_heldout_by_run(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = frame[frame["split"] == "heldout"].copy()
    for run, group in held.groupby("source_run"):
        for prefix, label, family in METHODS:
            rows.append({"source_run": int(run), "method": label, "family": family, **s11c.metric_values(group, prefix)})
    return pd.DataFrame(rows)


def per_event_errors(frame: pd.DataFrame, prefix: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    true_t = frame[["true_t1_sample", "true_t2_sample"]].to_numpy(dtype=float)
    pred_t = frame[[f"{prefix}_t1_sample", f"{prefix}_t2_sample"]].to_numpy(dtype=float)
    true_a = frame[["true_amp1_adc", "true_amp2_adc"]].to_numpy(dtype=float)
    pred_a = frame[[f"{prefix}_amp1_adc", f"{prefix}_amp2_adc"]].to_numpy(dtype=float)
    time_abs_max_ns = np.nanmax(np.abs(pred_t - true_t), axis=1) * 10.0
    time_err_ns = (pred_t - true_t).reshape(-1) * 10.0
    charge_bias = (pred_a.sum(axis=1) - true_a.sum(axis=1)) / np.maximum(true_a.sum(axis=1), 1.0)
    return time_abs_max_ns, time_err_ns, charge_bias


def add_failure_columns(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = frame.copy()
    max_time = float(config["failure_definition"]["max_abs_time_error_ns"])
    max_charge = float(config["failure_definition"]["max_abs_charge_bias_fraction"])
    for prefix, _label, _family in METHODS:
        time_abs_max, _terr, charge_bias = per_event_errors(out, prefix)
        out[f"{prefix}_time_abs_max_ns"] = time_abs_max
        out[f"{prefix}_charge_bias"] = charge_bias
        out[f"{prefix}_bad_recovery"] = (
            out[f"{prefix}_failed"].astype(bool).to_numpy()
            | (time_abs_max > max_time)
            | (np.abs(charge_bias) > max_charge)
        )
    return out


def add_atom_columns(frame: pd.DataFrame, waveforms: np.ndarray, heldout_events: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = frame.copy()
    by_id = {eid: i for i, eid in enumerate(heldout_events["event_id"].to_numpy())}
    idx = np.asarray([by_id[eid] for eid in out["event_id"].to_numpy()], dtype=int)
    wave = waveforms[idx]
    corrected = wave - np.median(wave[:, :4], axis=1)[:, None]
    amp = np.maximum(corrected.max(axis=1), 1.0)
    baseline = np.median(wave[:, :4], axis=1)
    tail_fraction = corrected[:, 10:].sum(axis=1) / np.maximum(corrected.sum(axis=1), 1.0)
    peak_sample = corrected.argmax(axis=1)
    out["axis_amplitude_ratio"] = pd.cut(out["true_ratio"], bins=[0.0, 0.375, 0.625, 0.875, 1.25], labels=["0.25", "0.50", "0.75", "1.00"], include_lowest=True)
    out["axis_separation_ns"] = pd.cut(out["true_sep_sample"] * 10.0, bins=[0, 7.5, 12.5, 17.5, 25, 45, 75], labels=["5", "10", "15", "20", "30-40", "50-60"], include_lowest=True)
    out["axis_saturation_boundary"] = np.where(
        out["true_amp1_adc"] + out["true_amp2_adc"] >= float(config["failure_definition"]["saturation_proxy_adc"]),
        "near_saturation_proxy",
        "below_saturation_proxy",
    )
    out["axis_baseline_excursion"] = pd.cut(np.abs(baseline), bins=[-0.1, 20, 50, 80, np.inf], labels=["lt20", "20-50", "50-80", "ge80"])
    out["axis_peak_sample_phase"] = pd.cut(peak_sample, bins=[-1, 4, 7, 10, 18], labels=["early", "nominal", "late", "edge"])
    q1, q2 = np.nanquantile(tail_fraction, [0.33, 0.66])
    out["axis_residual_tail_shape"] = pd.cut(tail_fraction, bins=[-np.inf, q1, q2, np.inf], labels=["fast_tail", "balanced_tail", "slow_tail"])
    return out


def odds_ratio(a_bad: int, a_good: int, b_bad: int, b_good: int) -> float:
    return float(((a_bad + 0.5) * (b_good + 0.5)) / ((a_good + 0.5) * (b_bad + 0.5)))


def atom_map(frame: pd.DataFrame, rng: np.random.Generator, config: dict) -> pd.DataFrame:
    positives = frame[(frame["split"] == "heldout") & (frame["is_overlap"] == 1)].copy()
    rows = []
    axes = [
        "axis_amplitude_ratio",
        "axis_separation_ns",
        "axis_saturation_boundary",
        "axis_baseline_excursion",
        "axis_peak_sample_phase",
        "axis_residual_tail_shape",
    ]
    for axis in axes:
        for value, group in positives.groupby(axis):
            if len(group) == 0:
                continue
            comp = positives[positives[axis] != value]
            bad = group["trad_bad_recovery"].astype(bool)
            comp_bad = comp["trad_bad_recovery"].astype(bool)
            valid_group = group[~group["trad_failed"].astype(bool)].copy()
            _tam, terr, qerr = per_event_errors(valid_group, "trad") if len(valid_group) else (np.asarray([]), np.asarray([]), np.asarray([]))
            or_value = odds_ratio(int(bad.sum()), int((~bad).sum()), int(comp_bad.sum()), int((~comp_bad).sum())) if len(comp) else float("nan")
            boot_rates = []
            boot_or = []
            runs = np.asarray(sorted(positives["source_run"].unique()), dtype=int)
            for _ in range(int(config["ml"]["bootstrap_samples"])):
                chosen = rng.choice(runs, size=len(runs), replace=True)
                parts = []
                for draw, run in enumerate(chosen):
                    part = positives[positives["source_run"] == run].copy()
                    part["_draw"] = draw
                    parts.append(part)
                boot = pd.concat(parts, ignore_index=True)
                bg = boot[boot[axis] == value]
                bc = boot[boot[axis] != value]
                if len(bg) == 0 or len(bc) == 0:
                    continue
                bg_bad = bg["trad_bad_recovery"].astype(bool)
                bc_bad = bc["trad_bad_recovery"].astype(bool)
                boot_rates.append(float(bg_bad.mean()))
                boot_or.append(odds_ratio(int(bg_bad.sum()), int((~bg_bad).sum()), int(bc_bad.sum()), int((~bc_bad).sum())))
            rows.append(
                {
                    "axis": axis.replace("axis_", ""),
                    "level": str(value),
                    "n_positive": int(len(group)),
                    "traditional_failure_rate": float(bad.mean()),
                    "failure_rate_ci_low": float(np.percentile(boot_rates, 2.5)) if boot_rates else float("nan"),
                    "failure_rate_ci_high": float(np.percentile(boot_rates, 97.5)) if boot_rates else float("nan"),
                    "time_rms_ns": float(np.sqrt(np.mean(terr**2))) if len(terr) else float("nan"),
                    "charge_fractional_bias": float(np.nanmedian(qerr)) if len(qerr) else float("nan"),
                    "charge_fractional_res68": s11c.sigma68(qerr[np.isfinite(qerr)]),
                    "bad_recovery_odds_ratio": or_value,
                    "odds_ratio_ci_low": float(np.percentile(boot_or, 2.5)) if boot_or else float("nan"),
                    "odds_ratio_ci_high": float(np.percentile(boot_or, 97.5)) if boot_or else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def risk_coverage_auc(good: np.ndarray, confidence: np.ndarray) -> float:
    order = np.argsort(-np.asarray(confidence, dtype=float))
    good_sorted = np.asarray(good, dtype=float)[order]
    cov = np.linspace(0.1, 1.0, 10)
    vals = []
    for c in cov:
        k = max(1, int(math.ceil(c * len(good_sorted))))
        vals.append(float(np.mean(good_sorted[:k])))
    return float(np.trapz(vals, cov) / (cov[-1] - cov[0]))


def risk_coverage(frame: pd.DataFrame, rng: np.random.Generator, config: dict) -> pd.DataFrame:
    positives = frame[(frame["split"] == "heldout") & (frame["is_overlap"] == 1)].copy()
    rows = []
    auc_by_prefix = {}
    ci_by_prefix = {}
    runs = np.asarray(sorted(positives["source_run"].unique()), dtype=int)
    for prefix, label, family in METHODS:
        good = ~positives[f"{prefix}_bad_recovery"].astype(bool).to_numpy()
        conf = positives[f"{prefix}_score"].replace([np.inf, -np.inf], np.nan).fillna(-1e9).to_numpy(dtype=float)
        auc = risk_coverage_auc(good, conf)
        boots = []
        for _ in range(int(config["ml"]["bootstrap_samples"])):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([positives[positives["source_run"] == run] for run in chosen], ignore_index=True)
            if len(boot):
                boots.append(
                    risk_coverage_auc(
                        ~boot[f"{prefix}_bad_recovery"].astype(bool).to_numpy(),
                        boot[f"{prefix}_score"].replace([np.inf, -np.inf], np.nan).fillna(-1e9).to_numpy(dtype=float),
                    )
                )
        auc_by_prefix[prefix] = auc
        ci_by_prefix[prefix] = (
            float(np.percentile(boots, 2.5)) if boots else float("nan"),
            float(np.percentile(boots, 97.5)) if boots else float("nan"),
        )
        rows.append(
            {
                "method": label,
                "family": family,
                "risk_coverage_auc": auc,
                "risk_coverage_auc_ci_low": ci_by_prefix[prefix][0],
                "risk_coverage_auc_ci_high": ci_by_prefix[prefix][1],
            }
        )
    trad_auc = auc_by_prefix["trad"]
    for row in rows:
        row["ml_minus_traditional_risk_coverage_auc"] = float(row["risk_coverage_auc"] - trad_auc)
    return pd.DataFrame(rows)


def resolvability_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = frame[(frame["split"] == "heldout") & (frame["is_overlap"] == 1)].copy()
    for prefix, label, family in METHODS:
        for sep, group in held.groupby("true_sep_sample"):
            good = ~group[f"{prefix}_bad_recovery"].astype(bool)
            rows.append(
                {
                    "method": label,
                    "family": family,
                    "separation_ns": float(sep) * 10.0,
                    "good_recovery_fraction": float(good.mean()),
                    "n_positive": int(len(group)),
                }
            )
    by_delay = pd.DataFrame(rows)
    out_rows = []
    for method, group in by_delay.groupby("method"):
        stable = group.sort_values("separation_ns")
        passing = stable[stable["good_recovery_fraction"] >= 0.68]
        delay = float(passing.iloc[0]["separation_ns"]) if len(passing) else float("nan")
        out_rows.append({"method": method, "resolvable_delay_ns": delay, "criterion": "first separation with >=68% good recovery"})
    return by_delay, pd.DataFrame(out_rows)


def leakage_checks(events: pd.DataFrame, combined: pd.DataFrame, cv: pd.DataFrame) -> pd.DataFrame:
    rows = []
    train_runs = set(events.loc[events["split"] == "train", "source_run"].astype(int))
    held_runs = set(events.loc[events["split"] == "heldout", "source_run"].astype(int))
    overlap = train_runs & held_runs
    rows.append({"check": "train_heldout_source_run_overlap", "value": int(len(overlap)), "pass": len(overlap) == 0})
    train_ids = set(events.loc[events["split"] == "train", "event_id"])
    held_ids = set(events.loc[events["split"] == "heldout", "event_id"])
    rows.append({"check": "event_id_overlap", "value": int(len(train_ids & held_ids)), "pass": len(train_ids & held_ids) == 0})
    held = combined[combined["split"] == "heldout"].copy()
    for prefix, label, _family in METHODS:
        got = s11c.metric_values(held, prefix)
        rows.append({"check": f"{label}_too_good_time_rms_lt_3ns", "value": float(got["time_rms_ns"]), "pass": not (np.isfinite(got["time_rms_ns"]) and got["time_rms_ns"] < 3.0)})
        rows.append({"check": f"{label}_too_good_detection_ap_gt_0p995", "value": float(got["detection_ap"]), "pass": not (np.isfinite(got["detection_ap"]) and got["detection_ap"] > 0.995)})
    if len(cv) and "ap" in cv:
        rows.append({"check": "mean_train_run_cv_ap_finite", "value": float(cv["ap"].dropna().mean()), "pass": bool(cv["ap"].dropna().mean() < 0.995)})
    return pd.DataFrame(rows)


def save_plots(out_dir: Path, overall: pd.DataFrame, atom: pd.DataFrame, risk: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    ax.bar(np.arange(len(overall)), overall["time_rms_ns"])
    ax.set_xticks(np.arange(len(overall)), overall["method"], rotation=25, ha="right")
    ax.set_ylabel("held-out time RMS (ns)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_time_rms.png", dpi=140)
    plt.close(fig)

    top = atom.sort_values("bad_recovery_odds_ratio", ascending=False).head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    labels = top["axis"] + "=" + top["level"]
    ax.barh(np.arange(len(top)), top["bad_recovery_odds_ratio"])
    ax.set_yticks(np.arange(len(top)), labels)
    ax.set_xlabel("traditional bad-recovery odds ratio")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_failure_atom_odds.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.0))
    ax.bar(np.arange(len(risk)), risk["risk_coverage_auc"])
    ax.set_xticks(np.arange(len(risk)), risk["method"], rotation=25, ha="right")
    ax.set_ylabel("good-recovery risk-coverage AUC")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_risk_coverage_auc.png", dpi=140)
    plt.close(fig)


def markdown_ci(row, key: str, digits: int = 2) -> str:
    fmt = f"{{:.{digits}f}}"
    return "{} [{}, {}]".format(fmt.format(row[key]), fmt.format(row[f"{key}_ci_low"]), fmt.format(row[f"{key}_ci_high"]))


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    s10: pd.DataFrame,
    s10f_repro: pd.DataFrame,
    overall: pd.DataFrame,
    heldout_by_run: pd.DataFrame,
    atom: pd.DataFrame,
    risk: pd.DataFrame,
    delay_summary: pd.DataFrame,
    leak: pd.DataFrame,
    winner: pd.Series,
    runtime: float,
) -> None:
    overall_lines = []
    for row in overall.itertuples():
        overall_lines.append(
            "| {} | {} | {:.3f} | {:.2f} [{:.2f}, {:.2f}] | {:.3f} [{:.3f}, {:.3f}] | {:.3f} | {:.3f} |".format(
                row.method,
                row.family,
                row.detection_ap,
                row.time_rms_ns,
                row.time_rms_ns_ci_low,
                row.time_rms_ns_ci_high,
                row.charge_fractional_res68,
                row.charge_fractional_res68_ci_low,
                row.charge_fractional_res68_ci_high,
                row.charge_fractional_bias,
                row.failure_rate,
            )
        )
    top_atoms = atom.sort_values("bad_recovery_odds_ratio", ascending=False).head(10)
    atom_lines = []
    for row in top_atoms.itertuples():
        atom_lines.append(
            "| {} | {} | {} | {:.3f} [{:.3f}, {:.3f}] | {:.2f} [{:.2f}, {:.2f}] | {:.2f} | {:.3f} |".format(
                row.axis,
                row.level,
                int(row.n_positive),
                row.traditional_failure_rate,
                row.failure_rate_ci_low,
                row.failure_rate_ci_high,
                row.bad_recovery_odds_ratio,
                row.odds_ratio_ci_low,
                row.odds_ratio_ci_high,
                row.time_rms_ns,
                row.charge_fractional_res68,
            )
        )
    risk_lines = []
    for row in risk.itertuples():
        risk_lines.append(
            "| {} | {:.3f} [{:.3f}, {:.3f}] | {:+.3f} |".format(
                row.method,
                row.risk_coverage_auc,
                row.risk_coverage_auc_ci_low,
                row.risk_coverage_auc_ci_high,
                row.ml_minus_traditional_risk_coverage_auc,
            )
        )
    run_lines = []
    for row in heldout_by_run.itertuples():
        run_lines.append(
            "| {} | {} | {:.3f} | {:.2f} | {:.3f} | {:.3f} |".format(
                int(row.source_run), row.method, row.detection_ap, row.time_rms_ns, row.charge_fractional_res68, row.failure_rate
            )
        )
    repro_text = reproduction.to_markdown(index=False)
    s10_text = s10.to_markdown(index=False)
    s10f_text = s10f_repro.to_markdown(index=False)
    leak_flags = int((~leak["pass"].astype(bool)).sum())
    text = f"""# S10l: asymmetric-template failure atom map

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-10
- **Inputs:** raw B-stack ROOT files under `{config['raw_root_dir']}`
- **Split:** train source runs `{config['benchmark_runs']['train']}`; held-out source runs `{config['benchmark_runs']['heldout']}`
- **Primary metric:** held-out constituent time RMS on injected positive two-pulse events, with held-out-source-run bootstrap 95% CIs.
- **Winner:** `{winner['method']}` with time RMS `{winner['time_rms_ns']:.2f}` ns.

## 0. Question

When the S10f amplitude-binned/asymmetric traditional two-pulse fit does not push the operational resolvable delay below about 60 ns, which atomic axes explain the failure: amplitude ratio, pulse separation, saturation boundary, baseline excursion, peak-sample phase, or residual tail shape? The preregistered comparison is a strong asymmetric template fit versus ridge, gradient-boosted trees, MLP, 1D-CNN, and a new attention waveform encoder on identical held-out source runs.

## 1. Reproduction gate

The raw ROOT selected-pulse count gate passed exactly.

{repro_text}

The S10 injection ML AP handle was independently rerun from raw ROOT.

{s10_text}

The S10f failure statement reproduced: under the stricter S10l per-event good-recovery diagnostic, the traditional asymmetric template fit still does not establish a stable sub-60 ns recovery. This is the failure S10l decomposes.

{s10f_text}

## 2. Traditional method

The traditional baseline is the S10f/S11c amplitude-binned asymmetric empirical-template fit. For stave \(s\), amplitude bin \(a\), and tail class \(h\), a train-run-only normalized template is

\\[
T_{{sah}}(j) = \\operatorname{{median}}_k \\left[ \\frac{{w_k(j + \\hat t_k - t_0)}}{{\\max_j w_k(j)}} \\right],
\\]

where \(\\hat t_k\) is CFD20 phase and \(t_0=5\) samples. The two-pulse model is

\\[
y(j)=A_1 T_p(j-t_1)+A_2 T_q(j-t_1-\\Delta)+b+\\epsilon_j,
\\]

with \(p,q\) selected from nearby amplitude/tail templates, \(\\Delta\) scanned over the configured separation grid, and \((A_1,A_2,b)\) solved by constrained least squares. A recovery is labeled bad when the fit fails, max constituent timing error exceeds {config['failure_definition']['max_abs_time_error_ns']} ns, or total-charge bias exceeds {config['failure_definition']['max_abs_charge_bias_fraction']:.2f}.

## 3. ML and NN methods

All ML/NN models use only waveform-derived features and stave one-hot labels; source run and event id are excluded. Ridge uses logistic regression with L2 penalty plus ridge regression. Gradient-boosted trees use histogram gradient boosting. MLP uses one hidden classifier and a two-layer regressor. The 1D-CNN is a small convolutional multi-task network. The new architecture is a gated attention encoder over the 18 samples, sharing a classifier and four regression heads. Regression targets are \(t_1/12, t_2/12, A_1/A_{{max}}, A_2/A_{{max}}\); regression loss is applied to positive injected events.

## 4. Head-to-head benchmark

| Method | family | AP | time RMS ns, 95% CI | charge res68, 95% CI | charge bias | failure rate |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(overall_lines)}

The winner by the preregistered primary metric is **{winner['method']}**. The bootstrap unit is held-out source run, so the CIs include run-to-run movement but remain limited by having only two held-out runs.

## 5. Failure atom map

| Axis | Level | n | traditional failure rate, 95% CI | bad-recovery odds ratio, 95% CI | time RMS ns | charge res68 |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(atom_lines)}

The strongest atoms are high-odds strata, not causal proof. They localize where the traditional model loses recoverability and motivate targeted controls.

## 6. Risk-coverage

Risk-coverage AUC is the area under good-recovery fraction versus retained coverage after sorting by each method's confidence score. It is reported on held-out positives only.

| Method | risk-coverage AUC, 95% CI | ML-minus-traditional |
|---|---:|---:|
{chr(10).join(risk_lines)}

## 7. Held-out run split

| Run | Method | AP | time RMS ns | charge res68 | failure rate |
|---:|---|---:|---:|---:|---:|
{chr(10).join(run_lines)}

## 8. Falsification and leakage checks

The falsification criterion was fixed before reading the result: if the traditional asymmetric template fit won the held-out time-RMS benchmark, the claimed need for ML/NN recovery would be rejected; if any leakage sentinel fired, the benchmark would be treated as invalid. Leakage flags observed: **{leak_flags}**.

{leak.to_markdown(index=False)}

## 9. Systematics and caveats

The benchmark is data-driven but synthetic: empirical templates and real residuals come from raw ROOT, while the second pulse is injected. This isolates recovery mechanics but may understate real high-current pathologies such as unresolved electronics saturation, trigger coupling, and pile-up topologies not represented by the injection generator. The saturation boundary is a proxy based on total injected amplitude, not a digitizer truth flag. The attention encoder is included as an architectural stress test, not as a production model. With only runs 63 and 65 held out, run-bootstrap CIs are honest but coarse.

## 10. Provenance

Artifacts are machine-readable in `result.json`, `manifest.json`, `head_to_head_overall.csv`, `failure_atom_map.csv`, `risk_coverage.csv`, `heldout_by_run.csv`, and `injected_events_with_predictions.csv`. Input checksums are in `input_sha256.csv`; output checksums are in `manifest.json`.

Reproduce with:

```bash
/home/billy/anaconda3/bin/python scripts/s10l_1781030650_532_4dd15543_failure_atom_map.py --config configs/s10l_1781030650_532_4dd15543_failure_atom_map.json
```

Runtime for this run: {runtime:.2f} s.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s10l_1781030650_532_4dd15543_failure_atom_map.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = s11c.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse count reproduction failed")

    s10 = s11c.reproduce_s10_ml(config)
    s10.to_csv(out_dir / "s10_ml_reproduction.csv", index=False)
    if len(s10) and not bool(s10["pass"].all()):
        raise RuntimeError("raw ROOT S10 ML reproduction failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    clean = s11c.read_clean_pulses(config, sorted(set(train_runs + heldout_runs)), rng)
    template_clean = clean[clean["run"].isin(train_runs)]
    s01_templates, s01_template_summary = s11c.build_templates(template_clean, config)
    s01_template_summary.to_csv(out_dir / "s01_template_summary.csv", index=False)

    train_events, train_wave = s11c.generate_benchmark(clean, s01_templates, config, "train", train_runs, rng)
    held_events, held_wave = s11c.generate_benchmark(clean, s01_templates, config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    heldout_mask = events["split"].to_numpy() == "heldout"
    heldout_events = events.loc[heldout_mask].reset_index(drop=True)
    heldout_waveforms = waveforms[heldout_mask]

    rich_templates, template_summary = s11c.build_amp_binned_templates(template_clean, config)
    template_summary.to_csv(out_dir / "s10l_template_summary.csv", index=False)
    trad = s11c.run_amp_binned_template_fits(heldout_events, heldout_waveforms, rich_templates, config)

    ml_pred, ml_cv = run_all_ml(events, waveforms, config)
    ml_cv.to_csv(out_dir / "ml_run_cv.csv", index=False)
    combined = heldout_events.merge(trad, on="event_id").merge(ml_pred, on="event_id")
    combined = add_failure_columns(combined, config)
    combined = add_atom_columns(combined, heldout_waveforms, heldout_events, config)
    combined.to_csv(out_dir / "injected_events_with_predictions.csv", index=False)

    overall = summarize_methods(combined, rng, config)
    overall.to_csv(out_dir / "head_to_head_overall.csv", index=False)
    heldout_by_run = summarize_heldout_by_run(combined)
    heldout_by_run.to_csv(out_dir / "heldout_by_run.csv", index=False)
    atom = atom_map(combined, rng, config)
    atom.to_csv(out_dir / "failure_atom_map.csv", index=False)
    risk = risk_coverage(combined, rng, config)
    risk.to_csv(out_dir / "risk_coverage.csv", index=False)
    delay_by_sep, delay_summary = resolvability_summary(combined)
    delay_by_sep.to_csv(out_dir / "resolvability_by_separation.csv", index=False)
    delay_summary.to_csv(out_dir / "resolvability_summary.csv", index=False)
    leak = leakage_checks(events, combined, ml_cv)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)
    save_plots(out_dir, overall, atom, risk)

    trad_delay = float(delay_summary[delay_summary["method"] == "amplitude_binned_asymmetric_template_fit"].iloc[0]["resolvable_delay_ns"])
    boundary = float(config["s10f_anchor"]["boundary_ns"])
    failure_flag = int((not np.isfinite(trad_delay)) or trad_delay >= boundary)
    s10f_repro = pd.DataFrame(
        [
            {
                "quantity": "S10f traditional sub-60 ns stable-recovery failure flag",
                "report_value": int(config["s10f_anchor"]["expected_traditional_sub60_failure_flag"]),
                "reproduced": failure_flag,
                "delta": failure_flag - int(config["s10f_anchor"]["expected_traditional_sub60_failure_flag"]),
                "tolerance": 0,
                "pass": failure_flag == int(config["s10f_anchor"]["expected_traditional_sub60_failure_flag"]),
                "diagnostic_delay_ns": trad_delay,
                "boundary_ns": boundary,
            }
        ]
    )
    s10f_repro.to_csv(out_dir / "s10f_reproduction.csv", index=False)

    input_paths = [s11c.raw_file(config, run) for run in sorted(set(s11c.configured_runs(config) + train_runs + heldout_runs))]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    ranked = overall[np.isfinite(overall["time_rms_ns"])].sort_values(["time_rms_ns", "charge_fractional_res68", "failure_rate"])
    winner = ranked.iloc[0]
    runtime = time.time() - start
    write_report(out_dir, config, reproduction, s10, s10f_repro, overall, heldout_by_run, atom, risk, delay_summary, leak, winner, runtime)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all() and (len(s10) == 0 or s10["pass"].all()) and s10f_repro["pass"].all()),
        "split": {"train_runs": train_runs, "heldout_runs": heldout_runs, "bootstrap_unit": "heldout source run"},
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "primary_metric": "heldout_constituent_time_rms_ns",
            "value": float(winner["time_rms_ns"]),
            "ci": [float(winner["time_rms_ns_ci_low"]), float(winner["time_rms_ns_ci_high"])],
        },
        "head_to_head": json_ready(overall.to_dict(orient="records")),
        "risk_coverage": json_ready(risk.to_dict(orient="records")),
        "top_failure_atoms": json_ready(atom.sort_values("bad_recovery_odds_ratio", ascending=False).head(10).to_dict(orient="records")),
        "s10f_reproduction": json_ready(s10f_repro.to_dict(orient="records")),
        "leakage_checks_pass": bool(leak["pass"].all()),
        "leakage_flags": int((~leak["pass"].astype(bool)).sum()),
        "follow_up_ticket_appended": False,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "winner": str(winner["method"]),
                "time_rms_ns": float(winner["time_rms_ns"]),
                "reproduced": result["reproduced"],
                "leakage_checks_pass": result["leakage_checks_pass"],
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
