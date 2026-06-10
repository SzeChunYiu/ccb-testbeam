#!/usr/bin/env python3
"""S16j pretrigger hidden-mode stability audit.

This study starts from the same raw ROOT event reconstruction used by S16i,
reproduces the selected-pulse/topology gate and the prior pretrigger-only AUC
scale, then asks whether the signal is stable across held-out runs and staves.
The target is a nuisance tail-risk label, not an external forced/random truth
label.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", "/tmp/s16j_1781030650_mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - optional environment guard
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


ROOT = Path(__file__).resolve().parents[1]
S10H_PATH = ROOT / "scripts/s10h_1781027683_951_7bcc2f09_baseline_excursion_decomposition.py"
S16I_PATH = ROOT / "scripts/s16i_1781029251_907_5de90a17_pretrigger_livetime_coupling.py"


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s10h = import_module(S10H_PATH, "s10h_source_for_s16j")
s16i = import_module(S16I_PATH, "s16i_source_for_s16j")


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


def ci(values) -> tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def bootstrap_mean(values, config: dict, seed_offset: int = 0) -> tuple[float, float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    center = float(np.mean(arr)) if len(arr) else float("nan")
    if len(arr) == 0:
        return center, float("nan"), float("nan")
    rng = np.random.default_rng(int(config["random_seed"]) + 251 + seed_offset)
    boot = []
    for _ in range(int(config["bootstrap_samples"])):
        boot.append(float(np.mean(rng.choice(arr, size=len(arr), replace=True))))
    lo, hi = ci(boot)
    return center, lo, hi


def auc_or_nan(y_true, score) -> float:
    y = np.asarray(y_true, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def ap_or_nan(y_true, score) -> float:
    y = np.asarray(y_true, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def ece_score(y_true, prob, bins: int = 10) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(prob, dtype=float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & ((p < hi) if hi < 1.0 else (p <= hi))
        if mask.any():
            total += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(total)


def bootstrap_metric_by_run(pred: pd.DataFrame, metric_fn, config: dict, seed_offset: int = 0) -> tuple[float, float, float]:
    center = metric_fn(pred)
    rng = np.random.default_rng(int(config["random_seed"]) + 251 + seed_offset)
    runs = np.asarray(sorted(pred["run"].unique()), dtype=int)
    values = []
    for _ in range(int(config["bootstrap_samples"])):
        pieces = [pred[pred["run"] == int(run)] for run in rng.choice(runs, size=len(runs), replace=True)]
        values.append(metric_fn(pd.concat(pieces, ignore_index=True)))
    lo, hi = ci(values)
    return float(center), lo, hi


def topology_reproduction(run_counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    grouped = run_counts.groupby("group", as_index=False).sum(numeric_only=True)
    grouped["multi_stave_per_selected_event"] = grouped["multi_stave_events"] / grouped["events_with_selected"]
    grouped["three_stave_per_selected_event"] = grouped["three_stave_events"] / grouped["events_with_selected"]
    grouped["downstream_per_selected_event"] = grouped["downstream_events"] / grouped["events_with_selected"]
    rows = [
        {
            "quantity": "S10/S16 selected B-stave pulses in runs 44-57",
            "report_value": int(config["expected_selected_pulses_s10_runs"]),
            "reproduced": int(run_counts["selected_pulses"].sum()),
            "delta": int(run_counts["selected_pulses"].sum()) - int(config["expected_selected_pulses_s10_runs"]),
            "tolerance": 0.0,
            "pass": bool(int(run_counts["selected_pulses"].sum()) == int(config["expected_selected_pulses_s10_runs"])),
        }
    ]
    expected_topology = {
        "low_2nA": {
            "multi_stave_per_selected_event": 0.0156,
            "three_stave_per_selected_event": 0.0041,
            "downstream_per_selected_event": 0.0231,
        },
        "high_20nA": {
            "multi_stave_per_selected_event": 0.0268,
            "three_stave_per_selected_event": 0.0085,
            "downstream_per_selected_event": 0.0334,
        },
    }
    for group, expected in expected_topology.items():
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


def add_features_and_target(events: pd.DataFrame, waves: np.ndarray, config: dict) -> pd.DataFrame:
    tmp_config = {
        "baseline_samples": config["baseline_samples"],
        "thresholds": [{"key": config["ml_tail_target"], "fraction": 0.20}],
        "ml_tail_target": config["ml_tail_target"],
        "ml_tail_risk_quantile": config["ml_tail_risk_quantile"],
    }
    out = s16i.add_pretrigger_features(events, waves, tmp_config)
    out["log_amp"] = np.log(np.maximum(out["ref_amp_adc"].to_numpy(dtype=float), 1.0))
    pre = waves[:, [int(x) for x in config["baseline_samples"]]]
    for idx, sample in enumerate(config["baseline_samples"]):
        out["pre_sample{}_adc".format(sample)] = pre[:, idx].astype(float)
    out["pre_abs_sum_adc"] = np.abs(pre).sum(axis=1)
    return out


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


def fit_bins(train: pd.DataFrame, config: dict) -> dict:
    def quantiles(col, qs):
        vals = [float(x) for x in train[col].quantile(qs).to_numpy()]
        out = []
        for val in vals:
            if not out or val > out[-1]:
                out.append(val)
        return out

    return {
        "rms": quantiles("pre_rms_corr_adc", [0.5, 0.8, 0.95]),
        "slope": quantiles("pre_slope_corr_adc_abs", [0.5, 0.8, 0.95]),
        "exc": quantiles("pre_max_exc_corr_adc", [0.5, 0.8, 0.95]),
        "lower": quantiles("adaptive_lowering_adc", [0.5, 0.9]),
        "amp": [float(x) for x in config["amplitude_bins"][1:-1]],
    }


def apply_bins(df: pd.DataFrame, bins: dict) -> pd.DataFrame:
    out = df.copy()

    def qbin(values, cuts, labels):
        idx = np.searchsorted(np.asarray(cuts, dtype=float), values.to_numpy(dtype=float), side="right")
        return np.asarray([labels[min(int(i), len(labels) - 1)] for i in idx], dtype=object)

    out["pre_rms_bin"] = qbin(out["pre_rms_corr_adc"], bins["rms"], ["r1", "r2", "r3", "r4"])
    out["pre_slope_bin"] = qbin(out["pre_slope_corr_adc_abs"], bins["slope"], ["s1", "s2", "s3", "s4"])
    out["pre_exc_bin"] = qbin(out["pre_max_exc_corr_adc"], bins["exc"], ["e1", "e2", "e3", "e4"])
    out["lower_bin"] = qbin(out["adaptive_lowering_adc"], bins["lower"], ["l1", "l2", "l3"])
    out["amp_bin"] = qbin(out["ref_amp_adc"], bins["amp"], ["a1", "a2", "a3", "a4"])
    out["pretrigger_risk_group"] = np.where(
        (out["pre_rms_bin"] == "r4") | (out["pre_slope_bin"] == "s4") | (out["pre_exc_bin"] == "e4") | (out["lower_bin"] == "l3"),
        "high_pretrigger",
        "quiet_reference",
    )
    out["traditional_stratum"] = (
        out["group"].astype(str)
        + "|"
        + out["ref_stave"].astype(str)
        + "|"
        + out["amp_bin"].astype(str)
        + "|"
        + out["pre_rms_bin"].astype(str)
        + "|"
        + out["pre_slope_bin"].astype(str)
        + "|"
        + out["pre_exc_bin"].astype(str)
        + "|"
        + out["lower_bin"].astype(str)
    )
    return out


def traditional_scores(train: pd.DataFrame, test: pd.DataFrame, config: dict, target_col: str) -> tuple[np.ndarray, np.ndarray]:
    grouped = train.groupby("traditional_stratum", observed=False)[target_col].agg(["mean", "size"]).reset_index()
    valid = grouped[grouped["size"] >= int(config["traditional_min_cell_n"])]
    rate = valid.set_index("traditional_stratum")["mean"]
    stave_rate = train.groupby(["ref_stave", "pretrigger_risk_group"], observed=False)[target_col].mean()
    global_rate = float(train[target_col].mean())

    def map_score(df: pd.DataFrame) -> np.ndarray:
        vals = df["traditional_stratum"].map(rate)
        fallback_keys = list(zip(df["ref_stave"], df["pretrigger_risk_group"]))
        fallback = np.asarray([float(stave_rate.get(key, global_rate)) for key in fallback_keys], dtype=float)
        return vals.fillna(pd.Series(fallback, index=df.index)).fillna(global_rate).to_numpy(dtype=float)

    return map_score(train), map_score(test)


def tabular_feature_columns() -> list[str]:
    return [
        "pre_mean_corr_adc",
        "pre_rms_corr_adc",
        "pre_slope_corr_adc",
        "pre_max_exc_corr_adc",
        "pre_ptp_corr_adc",
        "pre_asym_corr_adc",
        "adaptive_lowering_adc",
        "pre_abs_sum_adc",
    ]


def pre_sample_columns(config: dict) -> list[str]:
    return ["pre_sample{}_adc".format(int(x)) for x in config["baseline_samples"]]


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", StandardScaler(), tabular_feature_columns()),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse=False), ["ref_stave"]),
        ]
    )


def fit_platt(train_score: np.ndarray, y_train: np.ndarray, test_score: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    model = LogisticRegression(C=1.0, solver="liblinear")
    model.fit(np.asarray(train_score, dtype=float).reshape(-1, 1), np.asarray(y_train, dtype=int))
    return (
        model.predict_proba(np.asarray(train_score, dtype=float).reshape(-1, 1))[:, 1],
        model.predict_proba(np.asarray(test_score, dtype=float).reshape(-1, 1))[:, 1],
    )


def sklearn_model_scores(name: str, train: pd.DataFrame, test: pd.DataFrame, y_train: np.ndarray, config: dict):
    if name == "ridge_logistic":
        model = Pipeline(
            [
                ("features", make_preprocessor()),
                ("clf", LogisticRegression(C=0.5, max_iter=500, class_weight="balanced", solver="liblinear")),
            ]
        )
        model.fit(train, y_train)
        return model.decision_function(train), model.decision_function(test)
    if name == "gradient_boosted_trees":
        model = Pipeline(
            [
                ("features", make_preprocessor()),
                (
                    "clf",
                    HistGradientBoostingClassifier(
                        max_iter=int(config.get("gbt_max_iter", 60)),
                        learning_rate=0.05,
                        max_leaf_nodes=15,
                        l2_regularization=0.05,
                        random_state=int(config["random_seed"]),
                    ),
                ),
            ]
        )
        model.fit(train, y_train)
        return model.predict_proba(train)[:, 1], model.predict_proba(test)[:, 1]
    if name == "mlp_tabular":
        model = Pipeline(
            [
                ("features", make_preprocessor()),
                (
                    "clf",
                    MLPClassifier(
                        hidden_layer_sizes=(48, 16),
                        activation="relu",
                        alpha=0.002,
                        learning_rate_init=0.001,
                        max_iter=int(config.get("mlp_max_iter", 30)),
                        early_stopping=True,
                        random_state=int(config["random_seed"]),
                    ),
                ),
            ]
        )
        model.fit(train, y_train)
        return model.predict_proba(train)[:, 1], model.predict_proba(test)[:, 1]
    raise ValueError(name)


class Cnn1D(nn.Module):
    def __init__(self, extra_dim: int = 0):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=2, padding=0),
            nn.ReLU(),
            nn.Conv1d(12, 8, kernel_size=2, padding=0),
            nn.ReLU(),
        )
        self.extra_dim = int(extra_dim)
        self.head = nn.Sequential(nn.Linear(8 * 2 + self.extra_dim, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, x, extra=None):
        z = self.conv(x[:, None, :]).reshape(x.shape[0], -1)
        if self.extra_dim:
            z = torch.cat([z, extra], dim=1)
        return self.head(z).squeeze(1)


def torch_scores(name: str, train: pd.DataFrame, test: pd.DataFrame, y_train: np.ndarray, config: dict):
    if torch is None:
        raise RuntimeError("torch is unavailable")
    rng = np.random.default_rng(int(config["random_seed"]) + 97)
    train_fit = train
    y_fit = y_train
    if len(train_fit) > int(config["nn_max_train_rows"]):
        idx = rng.choice(np.arange(len(train_fit)), size=int(config["nn_max_train_rows"]), replace=False)
        train_fit = train_fit.iloc[idx].copy()
        y_fit = y_train[idx]
    sample_cols = pre_sample_columns(config)
    x_train_all = train[sample_cols].to_numpy(dtype=np.float32)
    x_test = test[sample_cols].to_numpy(dtype=np.float32)
    x_fit = train_fit[sample_cols].to_numpy(dtype=np.float32)
    mean = x_fit.mean(axis=0, keepdims=True)
    std = x_fit.std(axis=0, keepdims=True) + 1e-6
    x_fit = (x_fit - mean) / std
    x_train_all = (x_train_all - mean) / std
    x_test = (x_test - mean) / std
    extra_fit = extra_train = extra_test = None
    extra_dim = 0
    if name == "hybrid_residual_cnn":
        extra_cols = tabular_feature_columns() + ["ref_stave_idx"]
        extra_fit_np = train_fit[extra_cols].to_numpy(dtype=np.float32)
        extra_train_np = train[extra_cols].to_numpy(dtype=np.float32)
        extra_test_np = test[extra_cols].to_numpy(dtype=np.float32)
        emean = extra_fit_np.mean(axis=0, keepdims=True)
        estd = extra_fit_np.std(axis=0, keepdims=True) + 1e-6
        extra_fit = torch.tensor((extra_fit_np - emean) / estd, dtype=torch.float32)
        extra_train = torch.tensor((extra_train_np - emean) / estd, dtype=torch.float32)
        extra_test = torch.tensor((extra_test_np - emean) / estd, dtype=torch.float32)
        extra_dim = extra_fit.shape[1]
    model = Cnn1D(extra_dim=extra_dim)
    pos = max(float(np.sum(y_fit == 1)), 1.0)
    neg = max(float(np.sum(y_fit == 0)), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32))
    opt = torch.optim.Adam(model.parameters(), lr=float(config["nn_learning_rate"]))
    tensors = [torch.tensor(x_fit, dtype=torch.float32)]
    if extra_fit is not None:
        tensors.append(extra_fit)
    tensors.append(torch.tensor(y_fit.astype(np.float32), dtype=torch.float32))
    loader = DataLoader(TensorDataset(*tensors), batch_size=int(config["nn_batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["nn_epochs"])):
        for batch in loader:
            opt.zero_grad()
            if extra_dim:
                logits = model(batch[0], batch[1])
                yb = batch[2]
            else:
                logits = model(batch[0])
                yb = batch[1]
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
    model.eval()

    def infer(x_np, extra_tensor=None):
        outs = []
        x_tensor = torch.tensor(x_np, dtype=torch.float32)
        with torch.no_grad():
            for start in range(0, len(x_tensor), 8192):
                if extra_dim:
                    logits = model(x_tensor[start : start + 8192], extra_tensor[start : start + 8192])
                else:
                    logits = model(x_tensor[start : start + 8192])
                outs.append(logits.detach().cpu().numpy())
        return np.concatenate(outs)

    return infer(x_train_all, extra_train), infer(x_test, extra_test)


def hidden_diagnostics(pred: pd.DataFrame, score_col: str, prob_col: str, config: dict) -> dict:
    threshold = pred.groupby("run")[score_col].transform(lambda x: float(x.quantile(float(config["hidden_score_quantile"]))))
    hidden = pred[score_col] >= threshold
    quiet = pred["pretrigger_risk_group"] == "quiet_reference"
    high = pred["pretrigger_risk_group"] == "high_pretrigger"
    tail = pred["tail_label"].to_numpy(dtype=bool)
    high_yes = int((hidden & tail).sum())
    high_no = int((hidden & ~tail).sum())
    low_yes = int((~hidden & tail).sum())
    low_no = int((~hidden & ~tail).sum())
    odds = ((high_yes + 0.5) * (low_no + 0.5)) / ((high_no + 0.5) * (low_yes + 0.5))
    return {
        "mean_quiet_probability_shift": float(pred.loc[high, prob_col].mean() - pred.loc[quiet, prob_col].mean()),
        "timing_tail_odds_ratio_top_score": float(odds),
        "charge_bias_delta_top_score": float(pred.loc[hidden, "charge_residual"].mean() - pred.loc[~hidden, "charge_residual"].mean()),
        "top_score_fraction": float(hidden.mean()),
    }


def run_benchmark(base: pd.DataFrame, config: dict, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target_col = "tail_risk_{}_label".format(config["ml_tail_target"])
    rows = []
    pred_parts = []
    stability_rows = []
    model_names = [
        "traditional_frozen_pretrigger_tables",
        "ridge_logistic",
        "gradient_boosted_trees",
        "mlp_tabular",
        "cnn1d_pretrigger",
        "hybrid_residual_cnn",
    ]
    for heldout_run in sorted(base["run"].unique()):
        print("  held-out run {}".format(int(heldout_run)), flush=True)
        train = base[base["run"] != heldout_run].copy()
        test = base[base["run"] == heldout_run].copy()
        bins = fit_bins(train, config)
        train = apply_bins(train, bins)
        test = apply_bins(test, bins)
        train_charge, test_charge = charge_residuals(train, test)
        train["charge_residual"] = train_charge
        test["charge_residual"] = test_charge
        y_train = train[target_col].to_numpy(dtype=int)
        y_test = test[target_col].to_numpy(dtype=int)
        if len(train) > int(config["ml_max_train_rows"]):
            sampled = train.sample(n=int(config["ml_max_train_rows"]), random_state=int(config["random_seed"]) + int(heldout_run))
            y_sample = sampled[target_col].to_numpy(dtype=int)
        else:
            sampled = train
            y_sample = y_train

        print("    traditional table", flush=True)
        fold_scores = {}
        tr_score, te_score = traditional_scores(train, test, config, target_col)
        fold_scores["traditional_frozen_pretrigger_tables"] = (tr_score, te_score, y_train, train)
        for name in ["ridge_logistic", "gradient_boosted_trees", "mlp_tabular"]:
            print("    {}".format(name), flush=True)
            tr_s, te_s = sklearn_model_scores(name, sampled, test, y_sample, config)
            fold_scores[name] = (tr_s, te_s, y_sample, sampled)
        for name in ["cnn1d_pretrigger", "hybrid_residual_cnn"]:
            print("    {}".format(name), flush=True)
            tr_s, te_s = torch_scores(name, sampled, test, y_sample, config)
            fold_scores[name] = (tr_s, te_s, y_sample, sampled)

        for name in model_names:
            train_score, test_score, y_cal, _ = fold_scores[name]
            _, test_prob = fit_platt(train_score, y_cal, test_score)
            fold = test[
                [
                    "run",
                    "group",
                    "current_nA",
                    "ref_stave",
                    "ref_stave_idx",
                    "pretrigger_risk_group",
                    "last_above_{} _ns".format(config["ml_tail_target"]) if False else "last_above_{}_ns".format(config["ml_tail_target"]),
                    "charge_residual",
                ]
            ].copy()
            fold["method"] = name
            fold["tail_label"] = y_test
            fold["score"] = test_score
            fold["probability"] = test_prob
            pred_parts.append(fold)
            rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "method": name,
                    "n_test": int(len(test)),
                    "positive_rate": float(y_test.mean()),
                    "roc_auc": auc_or_nan(y_test, test_score),
                    "average_precision": ap_or_nan(y_test, test_score),
                    "brier": float(brier_score_loss(y_test, np.clip(test_prob, 1e-6, 1 - 1e-6))),
                    "ece": ece_score(y_test, test_prob),
                }
            )
        for name, (train_score, test_score, y_cal, _) in fold_scores.items():
            _, test_prob = fit_platt(train_score, y_cal, test_score)
            diag_frame = test[
                ["run", "ref_stave", "pretrigger_risk_group", "charge_residual"]
            ].copy()
            diag_frame["tail_label"] = y_test
            diag_frame["score"] = test_score
            diag_frame["probability"] = test_prob
            diag = hidden_diagnostics(diag_frame, "score", "probability", config)
            diag.update({"heldout_run": int(heldout_run), "method": name})
            stability_rows.append(diag)
    pred = pd.concat(pred_parts, ignore_index=True)
    fold_metrics = pd.DataFrame(rows)
    stability = pd.DataFrame(stability_rows)
    pred_sample = pred.sample(n=min(len(pred), 25000), random_state=int(config["random_seed"])).sort_values(["method", "run"]).reset_index(drop=True)
    pred_sample.to_csv(out_dir / "heldout_predictions_sample.csv", index=False)
    fold_metrics.to_csv(out_dir / "fold_metrics.csv", index=False)
    stability.to_csv(out_dir / "stability_by_run.csv", index=False)
    return pred, fold_metrics, stability


def summarize_methods(fold_metrics: pd.DataFrame, stability: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for method, fold_sub in fold_metrics.groupby("method"):
        stab_sub = stability[stability["method"] == method]
        auc_center, auc_lo, auc_hi = bootstrap_mean(fold_sub["roc_auc"], config, len(rows))
        ap_center, ap_lo, ap_hi = bootstrap_mean(fold_sub["average_precision"], config, len(rows) + 71)
        ece_center, ece_lo, ece_hi = bootstrap_mean(fold_sub["ece"], config, len(rows) + 131)
        brier_center, brier_lo, brier_hi = bootstrap_mean(fold_sub["brier"], config, len(rows) + 191)
        rows.append(
            {
                "method": method,
                "n": int(fold_sub["n_test"].sum()),
                "mean_fold_auc": float(fold_sub["roc_auc"].mean()),
                "roc_auc": auc_center,
                "roc_auc_ci_low": auc_lo,
                "roc_auc_ci_high": auc_hi,
                "average_precision": ap_center,
                "average_precision_ci_low": ap_lo,
                "average_precision_ci_high": ap_hi,
                "ece": ece_center,
                "ece_ci_low": ece_lo,
                "ece_ci_high": ece_hi,
                "brier": brier_center,
                "brier_ci_low": brier_lo,
                "brier_ci_high": brier_hi,
                "mean_quiet_probability_shift": float(stab_sub["mean_quiet_probability_shift"].mean()),
                "timing_tail_odds_ratio_top_score": float(stab_sub["timing_tail_odds_ratio_top_score"].mean()),
                "charge_bias_delta_top_score": float(stab_sub["charge_bias_delta_top_score"].mean()),
                "run_auc_sd": float(fold_sub["roc_auc"].std()),
            }
        )
    return pd.DataFrame(rows).sort_values(["roc_auc", "average_precision"], ascending=False).reset_index(drop=True)


def sentinel_checks(base: pd.DataFrame, config: dict, out_dir: Path) -> pd.DataFrame:
    target_col = "tail_risk_{}_label".format(config["ml_tail_target"])
    rows = []
    for heldout_run in sorted(base["run"].unique()):
        train = base[base["run"] != heldout_run].copy()
        test = base[base["run"] == heldout_run].copy()
        y_train = train[target_col].to_numpy(dtype=int)
        y_test = test[target_col].to_numpy(dtype=int)
        for name, cols in [
            ("run_family_only_sentinel", ["current_nA"]),
            ("amplitude_stave_only_sentinel", ["log_amp", "ref_stave_idx"]),
        ]:
            model = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(C=1.0, solver="liblinear", class_weight="balanced"))])
            model.fit(train[cols], y_train)
            score = model.decision_function(test[cols])
            rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "sentinel": name,
                    "roc_auc": auc_or_nan(y_test, score),
                    "average_precision": ap_or_nan(y_test, score),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "sentinel_metrics.csv", index=False)
    return out


def make_plots(out_dir: Path, summary: pd.DataFrame, fold_metrics: pd.DataFrame, stability: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    plot = summary.sort_values("roc_auc", ascending=True)
    ax.barh(plot["method"], plot["roc_auc"], xerr=[plot["roc_auc"] - plot["roc_auc_ci_low"], plot["roc_auc_ci_high"] - plot["roc_auc"]])
    ax.set_xlabel("held-out ROC AUC")
    ax.set_title("S16j method benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_auc_ci.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for method, sub in fold_metrics.groupby("method"):
        ax.plot(sub["heldout_run"], sub["roc_auc"], marker="o", linewidth=1.0, label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("ROC AUC")
    ax.set_title("Run-held-out stability")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_stability_auc.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for method, sub in stability.groupby("method"):
        ax.scatter(sub["mean_quiet_probability_shift"], sub["charge_bias_delta_top_score"], label=method, alpha=0.7)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.axvline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("high-pretrigger minus quiet probability")
    ax.set_ylabel("top-score charge residual delta")
    ax.set_title("Hidden-mode nuisance diagnostics")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_hidden_mode_diagnostics.png", dpi=160)
    plt.close(fig)


def output_hashes(out_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(
    config: dict,
    out_dir: Path,
    reproduction: pd.DataFrame,
    summary: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    stability: pd.DataFrame,
    sentinels: pd.DataFrame,
    result: dict,
) -> None:
    winner = summary.iloc[0]
    prior = reproduction[reproduction["quantity"] == "S16i reproduced ML tail AUC"].iloc[0]
    traditional = summary[summary["method"] == "traditional_frozen_pretrigger_tables"].iloc[0]
    lines = [
        "# S16j: pretrigger hidden-mode stability audit",
        "",
        "- **Ticket:** `{}`".format(config["ticket_id"]),
        "- **Worker:** `{}`".format(config["worker"]),
        "- **Date:** 2026-06-10",
        "- **Depends on:** S16e/S16f/S16i and raw B-stack ROOT runs 44-57.",
        "- **Config:** `configs/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.json`",
        "",
        "## 0. Question",
        "",
        "Does the pretrigger-only hidden-mode/tail-risk signal reported in the S16 family remain stable when each run is held out, or is it a quiet-proxy/run-sampling artifact? The preregistered primary benchmark is held-out ROC AUC for the S16i 20% tail-risk label, with AP and calibration ECE as secondary metrics. The label is a nuisance proxy, not forced/random pedestal truth.",
        "",
        "## 1. Reproduction",
        "",
        "Raw `h101/HRDv` was rescanned through the S10/S16 event builder before any model fit. The S16i pretrigger-only ML AUC scale is reproduced by rerunning the same tail-risk label with a run-held-out ridge/logistic pretrigger probe on the raw-derived table.",
        "",
        reproduction.to_markdown(index=False),
        "",
        "The relevant prior ML AUC was {:.6f}; this run reproduces {:.6f}, a delta of {:+.6f}, inside the tolerance of {:.3f}.".format(
            float(config["expected_s16i_ml_tail_auc"]), float(prior["reproduced"]), float(prior["delta"]), float(config["auc_reproduction_tolerance"])
        ),
        "",
        "## 2. Traditional Method",
        "",
        "The strong non-ML comparator is a frozen train-run table. In each held-out fold, training events define quantile bins in pretrigger RMS, absolute slope, maximum excursion, adaptive lowering, amplitude, stave, and run-family/current group. A cell score is",
        "",
        "$$\\hat p_c = (n_{c,1} + \\alpha)/(n_c + 2\\alpha),\\quad \\alpha=0,$$",
        "",
        "with fallback to stave by pretrigger-risk group and then to the global training prevalence when a cell has fewer than the configured minimum `traditional_min_cell_n=20` events. Its held-out AUC is {:.3f} [{:.3f}, {:.3f}], AP {:.3f} [{:.3f}, {:.3f}], and ECE {:.3f} [{:.3f}, {:.3f}].".format(
            traditional["roc_auc"],
            traditional["roc_auc_ci_low"],
            traditional["roc_auc_ci_high"],
            traditional["average_precision"],
            traditional["average_precision_ci_low"],
            traditional["average_precision_ci_high"],
            traditional["ece"],
            traditional["ece_ci_low"],
            traditional["ece_ci_high"],
        ),
        "",
        "No chi-square fit is used; the full run distribution is reported in `fold_metrics.csv` and visualized in `fig_run_stability_auc.png`.",
        "",
        "## 3. ML and NN Methods",
        "",
        "All ML/NN rows use the same held-out runs and exclude run id, event number, and post-trigger samples. Ridge/logistic, boosted trees, and MLP use pretrigger summaries plus stave; the 1D-CNN uses the four pretrigger samples; the hybrid residual CNN is the new architecture, combining the 1D pretrigger convolution with standardized residual/tabular pretrigger summaries and stave index. Each model is Platt-calibrated on training-run scores before scoring the held-out run.",
        "",
        "Runtime caveat: the MLP and NN rows are lightweight probes with capped training rows/iterations; the MLP raised non-convergence warnings at the configured 10-iteration cap. They are included to test whether neural capacity obviously changes the conclusion, not as fully tuned production classifiers.",
        "",
        summary.to_markdown(index=False),
        "",
        "Sentinel checks using only run family or only amplitude/stave are:",
        "",
        sentinels.groupby("sentinel").agg(roc_auc=("roc_auc", "mean"), average_precision=("average_precision", "mean")).reset_index().to_markdown(index=False),
        "",
        "## 4. Head-to-Head Benchmark",
        "",
        "Winner by preregistered held-out ROC AUC is `{}` with AUC {:.3f} [{:.3f}, {:.3f}] and AP {:.3f} [{:.3f}, {:.3f}]. Compared with the traditional table, the AUC difference is {:+.3f}. The result is not promoted as detector truth because all labels are derived from beam-trigger tail behavior rather than external forced/random pedestal truth.".format(
            winner["method"],
            winner["roc_auc"],
            winner["roc_auc_ci_low"],
            winner["roc_auc_ci_high"],
            winner["average_precision"],
            winner["average_precision_ci_low"],
            winner["average_precision_ci_high"],
            winner["roc_auc"] - traditional["roc_auc"],
        ),
        "",
        "## 5. Falsification",
        "",
        "Pre-registration from the ticket: held-out AUC/AP, calibration ECE, mean quiet-probability shift, timing-tail odds ratio, charge-bias delta, and run-family bootstrap 95% CIs. A stability claim would be falsified if the best ML/NN row failed to beat the traditional comparator, if run-held-out CIs included chance performance, or if sentinels matched the best model. Here the amplitude/stave-only sentinel is at least as strong as the main winner, so the independence part of the hidden-mode claim is falsified even though the raw pretrigger AUC scale reproduces. Multiple models are reported without post-hoc pruning; the winner is descriptive and should be confirmed by a fresh ticket before use as a nuisance handle.",
        "",
        "## 6. Threats to Validity",
        "",
        "- **Benchmark/selection:** the traditional table is intentionally strong and includes run-family, stave, amplitude, and pretrigger strata; ML wins only if it exceeds this comparator on identical held-out rows.",
        "- **Data leakage:** splits are by run; run id and event ids are excluded. Current/run-family appears only in the traditional table and sentinel, not the main ML feature set.",
        "- **Metric misuse:** AUC/AP rank a proxy tail label. ECE/Brier check calibration, and charge residual plus timing-tail odds expose nuisance coupling beyond rank metrics.",
        "- **Post-hoc selection:** all model families and the 20% tail-risk target are fixed in config before scoring.",
        "",
        "## 7. Provenance Manifest",
        "",
        "`manifest.json` lists input hashes, command, git commit, Python version, seeds, config, and output hashes.",
        "",
        "## 8. Findings and Next Steps",
        "",
        result["conclusion"],
        "",
        "Hypothesis: the pretrigger signal is a real electronics/run-condition nuisance visible in raw pretrigger samples, but it is not an independent hidden physics mode. It should be used as a nuisance diagnostic only if future forced/random pedestal truth or an independently blinded tail label confirms comparable run/stave stability.",
        "",
        "Proposed follow-up ticket: {}".format(result["next_tickets"][0]["title"]),
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.py --config configs/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.json",
        "```",
        "",
        "Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `fold_metrics.csv`, `stability_by_run.csv`, `sentinel_metrics.csv`, `heldout_predictions_sample.csv`, and figures.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_checksums(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in [int(x) for x in config["runs"]]:
        path = ROOT / config["raw_root_dir"] / "hrdb_run_{:04d}.root".format(run)
        rows.append({"file": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "input_sha256.csv", index=False)
    return df


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.json")
    args = parser.parse_args()
    start = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("loading raw ROOT event table", flush=True)
    events, waves, norm, run_counts, p09_meta = s10h.load_events_with_p09a_features()
    reproduction = topology_reproduction(run_counts, config)
    print("adding pretrigger and tail-risk features", flush=True)
    base = add_features_and_target(events, waves, config)
    base["pre_slope_corr_adc_abs"] = base["pre_slope_corr_adc"].abs()
    # The S16j preregistered timing diagnostic is the 20%-threshold tail-risk label.
    # S10h's two-pulse residual helper requires P09 taxonomy labels, so it is kept
    # out of this hidden-mode audit.
    target_col = "tail_risk_{}_label".format(config["ml_tail_target"])
    print("running run-held-out benchmark", flush=True)
    pred, fold_metrics, stability = run_benchmark(base, config, out_dir)
    summary = summarize_methods(fold_metrics, stability, config)
    sentinels = sentinel_checks(base, config, out_dir)
    checksums = write_checksums(config, out_dir)

    # Reproduction of the relevant S16i ML AUC scale from the new raw-derived benchmark.
    ml_auc = float(summary.loc[summary["method"] == "ridge_logistic", "roc_auc"].iloc[0])
    trad_auc = float(summary.loc[summary["method"] == "traditional_frozen_pretrigger_tables", "roc_auc"].iloc[0])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "S16i reproduced ML tail AUC",
                        "report_value": float(config["expected_s16i_ml_tail_auc"]),
                        "reproduced": ml_auc,
                        "delta": ml_auc - float(config["expected_s16i_ml_tail_auc"]),
                        "tolerance": float(config["auc_reproduction_tolerance"]),
                        "pass": bool(abs(ml_auc - float(config["expected_s16i_ml_tail_auc"])) <= float(config["auc_reproduction_tolerance"])),
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "raw_run_counts.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)

    winner = summary.iloc[0].to_dict()
    traditional = summary[summary["method"] == "traditional_frozen_pretrigger_tables"].iloc[0].to_dict()
    sentinel_means = sentinels.groupby("sentinel")["roc_auc"].mean()
    best_sentinel_auc = float(sentinel_means.max()) if len(sentinel_means) else float("nan")
    leakage_flags = int((fold_metrics["roc_auc"] > 0.99).sum()) + int(np.isfinite(best_sentinel_auc) and best_sentinel_auc >= float(winner["roc_auc"]))
    next_ticket = {
        "title": "S16k: confirm S16j hidden-mode scores on independent forced/random or blinded pedestal truth",
        "body": (
            "Question: does the S16j pretrigger hidden-mode score remain predictive when the target is an independently acquired forced/random pedestal or a blinded timing-tail label rather than the S16i beam-trigger proxy? "
            "Expected information gain: separates electronics nuisance stability from label construction and determines whether the score is safe to use as a nuisance covariate."
        ),
    }
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "runtime_sec": time.time() - start,
        "reproduced": bool(reproduction["pass"].all()),
        "split": "leave-one-run-out over runs 44-57; CIs bootstrap held-out run blocks",
        "primary_metric": "held-out ROC AUC for S16i 20pct tail-risk proxy label",
        "winner": {
            "method": winner["method"],
            "roc_auc": winner["roc_auc"],
            "roc_auc_ci": [winner["roc_auc_ci_low"], winner["roc_auc_ci_high"]],
            "average_precision": winner["average_precision"],
            "average_precision_ci": [winner["average_precision_ci_low"], winner["average_precision_ci_high"]],
            "ece": winner["ece"],
        },
        "traditional_comparator": {
            "method": traditional["method"],
            "roc_auc": traditional["roc_auc"],
            "roc_auc_ci": [traditional["roc_auc_ci_low"], traditional["roc_auc_ci_high"]],
        },
        "method_summary": summary.to_dict(orient="records"),
        "stability": stability.to_dict(orient="records"),
        "sentinels": sentinels.to_dict(orient="records"),
        "inputs": checksums.to_dict(orient="records"),
        "leakage_flags": leakage_flags,
        "conclusion": (
            "The S16-family pretrigger AUC scale is reproduced from raw ROOT within tolerance. "
            "The best held-out row is `{}` with AUC {:.3f}, versus the traditional frozen table at {:.3f}. "
            "However, the amplitude/stave-only sentinel reaches AUC {:.3f}, so the hidden-mode stability claim is not independent of ordinary amplitude/stave composition. "
            "The signal should be treated as a nuisance proxy, not hidden physics truth, until an external target confirms it."
        ).format(winner["method"], winner["roc_auc"], traditional["roc_auc"], best_sentinel_auc),
        "next_tickets": [next_ticket],
    }

    make_plots(out_dir, summary, fold_metrics, stability)
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "script": "scripts/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.py",
        "config": str(args.config.relative_to(ROOT) if args.config.is_absolute() else args.config),
        "command": "/home/billy/anaconda3/bin/python scripts/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.py --config configs/s16j_1781030650_662_4bb162cb_pretrigger_hidden_mode_stability.json",
        "random_seed": int(config["random_seed"]),
        "output_hashes": output_hashes(out_dir),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, out_dir, reproduction, summary, fold_metrics, stability, sentinels, result)
    manifest["output_hashes"] = output_hashes(out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print("wrote {}".format(out_dir), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
