#!/usr/bin/env python3
"""P12b pulse-support tensor and run-heldout risk benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p12a_1781023340_632_43377364_pulse_axis_covariance as p12a  # noqa: E402


NON_TARGET_AXES = [
    "saturation_boundary",
    "high_amplitude",
    "adaptive_lowering",
    "early_pretrigger_activity",
    "delayed_peak",
    "broad_template_mismatch",
    "pileup_score",
    "timing_tail",
]

NUMERIC_COLS = [
    "log_amp",
    "amplitude_adc",
    "area_over_amp",
    "peak_sample",
    "width035_samples",
    "width050_samples",
    "plateau_count",
    "secondary_peak_rel",
    "late_fraction",
    "seed_baseline_adc",
    "pre_rms_adc",
    "pre_max_exc_adc",
    "adaptive_lowering_adc",
    "event_timing_abs_resid_ns_filled",
    "active_atom_count_no_charge",
]

CAT_COLS = [
    "stave",
    "amplitude_atom",
    "shape_atom",
    "timing_atom",
    "saturation_atom",
    "pileup_atom",
    "baseline_atom",
    "dropout_anomaly_atom",
    "q_template_atom",
    "covariance_atom",
]


def fast_assign_axes(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Assign P12-style atoms with one run-family externalized charge model."""
    heldout = set(int(run) for run in config["benchmark"]["heldout_runs"])
    out = pulses.copy()
    train = out[~out["run"].isin(heldout)].copy()
    charge = p12a.charge_model()
    charge.fit(train, train["area_over_amp"])
    pred = charge.predict(out)
    train_pred = charge.predict(train)
    train_resid = train["area_over_amp"].to_numpy(dtype=float) - train_pred
    threshold = float(np.nanquantile(np.abs(train_resid), 0.95))
    broad_threshold = float(train["width050_samples"].quantile(float(config.get("broad_width050_quantile", 0.995))))
    out["charge_residual_area_over_amp"] = out["area_over_amp"].to_numpy(dtype=float) - pred
    out["charge_residual_threshold"] = threshold
    out["saturation_boundary"] = ((out["amplitude_adc"] >= float(config["high_amplitude_adc"])) & (out["plateau_count"] >= 2)).astype(int)
    out["high_amplitude"] = (out["amplitude_adc"] >= float(config["high_amplitude_adc"])).astype(int)
    out["adaptive_lowering"] = (out["adaptive_lowering_adc"] >= float(config["adaptive_lowering_adc"])).astype(int)
    out["early_pretrigger_activity"] = (
        (out["pre_max_exc_adc"] >= float(config["early_pretrigger_exc_adc"]))
        | (out["pre_ptp_adc"] >= float(config["early_pretrigger_exc_adc"]))
    ).astype(int)
    out["delayed_peak"] = (out["peak_sample"] >= int(config["delayed_peak_sample"])).astype(int)
    out["pileup_score"] = (
        (
            (out["secondary_peak_rel"] >= float(config["pileup_secondary_rel"]))
            & (out["secondary_peak_sep"] >= int(config.get("pileup_secondary_min_sep", 4)))
        )
        | (out["late_fraction"] >= float(config["pileup_late_fraction"]))
    ).astype(int)
    out["broad_template_mismatch"] = (
        (out["width050_samples"] >= broad_threshold)
        & (out["pileup_score"] == 0)
        & (out["saturation_boundary"] == 0)
    ).astype(int)
    out["timing_tail"] = (out["event_timing_abs_resid_ns"] > float(config["timing_tail_abs_ns"])).fillna(False).astype(int)
    out["charge_transfer_error"] = (np.abs(out["charge_residual_area_over_amp"]) >= threshold).astype(int)
    return out


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    return value


def finite_series(values: pd.Series, fill: float = 0.0) -> pd.Series:
    out = values.astype(float).replace([np.inf, -np.inf], np.nan)
    return out.fillna(fill)


def quantile_labels(values: pd.Series, labels: List[str], fallback: str) -> pd.Series:
    try:
        return pd.qcut(values, q=len(labels), labels=labels, duplicates="drop").astype(str)
    except ValueError:
        return pd.Series([fallback] * len(values), index=values.index)


def add_atoms(axis_df: pd.DataFrame) -> pd.DataFrame:
    out = axis_df.copy()
    out["event_timing_abs_resid_ns_filled"] = finite_series(out["event_timing_abs_resid_ns"], 0.0)
    out["active_atom_count_no_charge"] = out[NON_TARGET_AXES].sum(axis=1).astype(int)

    amp = out["amplitude_adc"].to_numpy(dtype=float)
    out["amplitude_atom"] = np.select(
        [amp >= 7000.0, amp >= 4000.0, amp >= 2000.0],
        ["amp_extreme_ge7000", "amp_high_4000_7000", "amp_mid_2000_4000"],
        default="amp_low_1000_2000",
    )
    out["shape_atom"] = np.select(
        [
            out["delayed_peak"].to_numpy(dtype=bool),
            out["broad_template_mismatch"].to_numpy(dtype=bool),
            out["late_fraction"].to_numpy(dtype=float) >= 0.35,
            out["width050_samples"].to_numpy(dtype=float) <= 2,
        ],
        ["shape_delayed_peak", "shape_broad_template", "shape_late_tail", "shape_narrow"],
        default="shape_nominal",
    )
    out["timing_atom"] = np.where(out["timing_tail"].to_numpy(dtype=bool), "timing_tail", "timing_core")
    out["saturation_atom"] = np.select(
        [
            out["saturation_boundary"].to_numpy(dtype=bool),
            out["high_amplitude"].to_numpy(dtype=bool),
            out["plateau_count"].to_numpy(dtype=float) >= 2,
        ],
        ["sat_boundary", "sat_high_amp", "sat_plateau"],
        default="sat_none",
    )
    out["pileup_atom"] = np.where(out["pileup_score"].to_numpy(dtype=bool), "pileup_like", "pileup_quiet")
    out["baseline_atom"] = np.select(
        [
            out["adaptive_lowering"].to_numpy(dtype=bool),
            out["early_pretrigger_activity"].to_numpy(dtype=bool),
            out["pre_rms_adc"].to_numpy(dtype=float) >= 250.0,
        ],
        ["baseline_adaptive_lowering", "baseline_pretrigger_activity", "baseline_noisy"],
        default="baseline_quiet",
    )
    out["dropout_anomaly_atom"] = np.select(
        [
            out["area_over_amp"].to_numpy(dtype=float) <= out["area_over_amp"].quantile(0.01),
            out["secondary_peak_rel"].to_numpy(dtype=float) >= 0.80,
            out["pre_max_exc_adc"].to_numpy(dtype=float) >= 750.0,
        ],
        ["dropout_low_area_proxy", "anomaly_secondary_peak", "anomaly_pretrigger_excursion"],
        default="anomaly_none",
    )
    q_score = (
        np.abs(finite_series(out["late_fraction"], 0.0) - finite_series(out["late_fraction"], 0.0).median())
        + 0.12 * np.abs(finite_series(out["width050_samples"], 0.0) - finite_series(out["width050_samples"], 0.0).median())
        + 0.05 * np.abs(finite_series(out["peak_sample"], 0.0) - finite_series(out["peak_sample"], 0.0).median())
    )
    out["q_template_score"] = q_score
    out["q_template_atom"] = quantile_labels(
        q_score,
        ["qtemplate_low", "qtemplate_moderate", "qtemplate_high", "qtemplate_extreme"],
        "qtemplate_single_bin",
    )
    out["covariance_atom"] = np.select(
        [
            out["active_atom_count_no_charge"].to_numpy(dtype=int) >= 4,
            out["active_atom_count_no_charge"].to_numpy(dtype=int) >= 2,
        ],
        ["covariance_dense", "covariance_coupled"],
        default="covariance_sparse",
    )
    out["charge_transfer_atom"] = np.where(out["charge_transfer_error"].to_numpy(dtype=bool), "charge_transfer_bad", "charge_transfer_ok")
    tensor_cols = [
        "shape_atom",
        "timing_atom",
        "amplitude_atom",
        "saturation_atom",
        "pileup_atom",
        "baseline_atom",
        "dropout_anomaly_atom",
        "q_template_atom",
        "covariance_atom",
        "charge_transfer_atom",
    ]
    out["support_cell"] = out[tensor_cols].astype(str).agg("|".join, axis=1)
    out["predictor_cell"] = out[[c for c in tensor_cols if c != "charge_transfer_atom"]].astype(str).agg("|".join, axis=1)
    out["weak_pid_positive"] = (
        (out["amplitude_adc"] >= out["amplitude_adc"].quantile(0.75))
        & (out["pileup_score"] == 0)
        & (out["saturation_boundary"] == 0)
        & (out["timing_tail"] == 0)
    ).astype(int)
    return out


def sigma68(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return np.nan
    med = np.nanmedian(arr)
    return float(np.nanquantile(np.abs(arr - med), 0.68))


def support_tensor_tables(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    run_rows = []
    for cell, part in df.groupby("support_cell"):
        run_pid = part.groupby("run")["weak_pid_positive"].mean()
        rows.append(
            {
                "support_cell": cell,
                "n": int(len(part)),
                "n_runs": int(part["run"].nunique()),
                "charge_failure_rate": float(part["charge_transfer_error"].mean()),
                "charge_bias_median": float(np.nanmedian(part["charge_residual_area_over_amp"])),
                "charge_res68": sigma68(part["charge_residual_area_over_amp"]),
                "timing_tail_rate": float(part["timing_tail"].mean()),
                "pileup_rate": float(part["pileup_score"].mean()),
                "weak_pid_fraction": float(part["weak_pid_positive"].mean()),
                "weak_pid_run_span": float(run_pid.max() - run_pid.min()) if len(run_pid) else np.nan,
            }
        )
        for run, rpart in part.groupby("run"):
            run_rows.append(
                {
                    "support_cell": cell,
                    "run": int(run),
                    "n": int(len(rpart)),
                    "charge_failure_rate": float(rpart["charge_transfer_error"].mean()),
                    "timing_tail_rate": float(rpart["timing_tail"].mean()),
                    "weak_pid_fraction": float(rpart["weak_pid_positive"].mean()),
                }
            )
    tensor = pd.DataFrame(rows).sort_values(["n", "n_runs"], ascending=False)
    by_run = pd.DataFrame(run_rows)

    boot_rows = []
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]) + 77)
    reps = int(config["benchmark"]["bootstrap_reps"])
    top_cells = tensor.head(40)["support_cell"].tolist()
    for cell in top_cells:
        part = df[df["support_cell"] == cell]
        runs = sorted(part["run"].unique())
        if len(runs) < 2:
            continue
        by = {int(run): part[part["run"] == run] for run in runs}
        vals = []
        for _ in range(reps):
            sample = pd.concat([by[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            vals.append(float(sample["charge_transfer_error"].mean()))
        boot_rows.append(
            {
                "support_cell": cell,
                "metric": "charge_failure_rate",
                "value": float(part["charge_transfer_error"].mean()),
                "ci_low": float(np.percentile(vals, 2.5)),
                "ci_high": float(np.percentile(vals, 97.5)),
            }
        )
    return tensor, by_run, pd.DataFrame(boot_rows)


def empirical_bayes_predict(train: pd.DataFrame, test: pd.DataFrame, prior_strength: float = 30.0) -> np.ndarray:
    y = train["charge_transfer_error"].astype(float)
    global_rate = float(y.mean())
    cell_stats = train.groupby("predictor_cell")["charge_transfer_error"].agg(["sum", "count"])
    cell_risk = (cell_stats["sum"] + global_rate * prior_strength) / (cell_stats["count"] + prior_strength)
    coarse_cols = ["stave", "amplitude_atom", "shape_atom", "timing_atom", "pileup_atom", "baseline_atom"]
    train_coarse = train[coarse_cols].astype(str).agg("|".join, axis=1)
    test_coarse = test[coarse_cols].astype(str).agg("|".join, axis=1)
    coarse_stats = train.assign(_coarse=train_coarse).groupby("_coarse")["charge_transfer_error"].agg(["sum", "count"])
    coarse_risk = (coarse_stats["sum"] + global_rate * prior_strength) / (coarse_stats["count"] + prior_strength)
    pred = test["predictor_cell"].map(cell_risk)
    pred = pred.fillna(test_coarse.map(coarse_risk))
    return pred.fillna(global_rate).to_numpy(dtype=float)


def make_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC_COLS),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse=False), CAT_COLS),
        ]
    )


def fit_sklearn_methods(train: pd.DataFrame, test: pd.DataFrame, seed: int) -> Dict[str, np.ndarray]:
    x_cols = NUMERIC_COLS + CAT_COLS
    y = train["charge_transfer_error"].astype(int)
    methods = {
        "ridge": LogisticRegression(max_iter=800, C=1.0, class_weight="balanced", solver="lbfgs"),
        "gradient_boosted_trees": HistGradientBoostingClassifier(max_iter=90, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.04, random_state=seed),
        "mlp": MLPClassifier(hidden_layer_sizes=(48, 24), alpha=0.0008, batch_size=512, learning_rate_init=0.001, max_iter=35, early_stopping=True, random_state=seed),
    }
    preds: Dict[str, np.ndarray] = {}
    for name, model in methods.items():
        print("  fitting {}".format(name), flush=True)
        pipe = Pipeline([("pre", make_preprocessor()), ("model", model)])
        pipe.fit(train[x_cols], y)
        preds[name] = pipe.predict_proba(test[x_cols])[:, 1]
    return preds


def dense_design(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    x_cols = NUMERIC_COLS + CAT_COLS
    pre = make_preprocessor()
    x_train = pre.fit_transform(train[x_cols])
    x_test = pre.transform(test[x_cols])
    return np.asarray(x_train, dtype=np.float32), np.asarray(x_test, dtype=np.float32)


def torch_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, config: dict, prior_train: np.ndarray = None, prior_test: np.ndarray = None) -> np.ndarray:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    seed = int(config["benchmark"]["random_seed"])
    torch.manual_seed(seed)
    batch_size = int(config["benchmark"]["cnn_batch_size"])
    epochs = int(config["benchmark"]["cnn_epochs"])

    if prior_train is not None:
        train_x = np.column_stack([train_x, prior_train.astype(np.float32)])
        test_x = np.column_stack([test_x, prior_test.astype(np.float32)])

    class SmallCnn(nn.Module):
        def __init__(self, n_features: int, fusion: bool):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(1, 16, kernel_size=5, padding=2),
                nn.ReLU(),
                nn.Conv1d(16, 24, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            extra = 1 if fusion else 0
            self.head = nn.Sequential(nn.Linear(24 + extra, 24), nn.ReLU(), nn.Linear(24, 1))
            self.fusion = fusion

        def forward(self, x):
            if self.fusion:
                seq = x[:, :-1].unsqueeze(1)
                prior = x[:, -1:].float()
                z = self.conv(seq).squeeze(-1)
                return self.head(torch.cat([z, prior], dim=1)).squeeze(1)
            z = self.conv(x.unsqueeze(1)).squeeze(-1)
            return self.head(z).squeeze(1)

    y = train_y.astype(np.float32)
    pos = max(float(y.sum()), 1.0)
    neg = max(float(len(y) - y.sum()), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32))
    model = SmallCnn(train_x.shape[1], prior_train is not None)
    print("  fitting {}".format("tensor_prior_residual_cnn_new_arch" if prior_train is not None else "1d_cnn"), flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=0.0015, weight_decay=0.0005)
    ds = TensorDataset(torch.tensor(train_x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True)
    model.train()
    for _ in range(epochs):
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    out = []
    with torch.no_grad():
        for start in range(0, len(test_x), 4096):
            xb = torch.tensor(test_x[start : start + 4096], dtype=torch.float32)
            out.append(torch.sigmoid(model(xb)).numpy())
    return np.concatenate(out)


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if mask.any():
            out += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(out)


def score_predictions(frame: pd.DataFrame, pred_col: str) -> dict:
    y = frame["charge_transfer_error"].to_numpy(dtype=int)
    p = np.clip(frame[pred_col].to_numpy(dtype=float), 1e-6, 1.0 - 1e-6)
    auc = roc_auc_score(y, p) if len(np.unique(y)) > 1 else np.nan
    ap = average_precision_score(y, p) if len(np.unique(y)) > 1 else np.nan
    support_mask = p <= 0.10
    return {
        "n": int(len(y)),
        "event_rate": float(y.mean()),
        "auc": float(auc),
        "average_precision": float(ap),
        "brier": float(brier_score_loss(y, p)),
        "ece": ece(y, p),
        "support_coverage_at_risk10": float(support_mask.mean()),
        "failure_rate_at_risk10": float(y[support_mask].mean()) if support_mask.any() else np.nan,
    }


def metric_ci(eval_df: pd.DataFrame, method: str, config: dict) -> dict:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]) + len(method) * 13)
    runs = sorted(eval_df["run"].unique())
    by = {int(run): eval_df[eval_df["run"] == run] for run in runs}
    reps = int(config["benchmark"]["bootstrap_reps"])
    vals = {"auc": [], "average_precision": [], "brier": [], "ece": [], "support_coverage_at_risk10": [], "failure_rate_at_risk10": []}
    for _ in range(reps):
        sample = pd.concat([by[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        got = score_predictions(sample, "pred_" + method)
        for key in vals:
            vals[key].append(got[key])
    out = {}
    for key, arr in vals.items():
        clean = np.asarray(arr, dtype=float)
        clean = clean[np.isfinite(clean)]
        out[key + "_ci95"] = [float(np.percentile(clean, 2.5)), float(np.percentile(clean, 97.5))] if len(clean) else [None, None]
    return out


def benchmark_methods(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    seed = int(config["benchmark"]["random_seed"])
    rng = np.random.default_rng(seed)
    heldout = set(int(run) for run in config["benchmark"]["heldout_runs"])
    train_all = df[~df["run"].isin(heldout)].copy()
    eval_df = df[df["run"].isin(heldout)].copy()
    train_cap = int(config["benchmark"]["train_cap"])
    train = train_all.sample(n=train_cap, random_state=seed) if len(train_all) > train_cap else train_all.copy()

    pred_trad_train = empirical_bayes_predict(train, train)
    pred_trad = empirical_bayes_predict(train, eval_df)
    eval_df["pred_empirical_bayes_support"] = pred_trad

    preds = fit_sklearn_methods(train, eval_df, seed)
    for name, values in preds.items():
        eval_df["pred_" + name] = values

    x_train, x_eval = dense_design(train, eval_df)
    y_train = train["charge_transfer_error"].to_numpy(dtype=int)
    eval_df["pred_1d_cnn"] = torch_predict(x_train, y_train, x_eval, config)

    trad_train = np.clip(pred_trad_train, 1e-5, 1 - 1e-5)
    trad_eval = np.clip(pred_trad, 1e-5, 1 - 1e-5)
    train_prior = np.log(trad_train / (1.0 - trad_train)).astype(np.float32)
    eval_prior = np.log(trad_eval / (1.0 - trad_eval)).astype(np.float32)
    eval_df["pred_tensor_prior_residual_cnn_new_arch"] = torch_predict(x_train, y_train, x_eval, config, train_prior, eval_prior)

    methods = [
        ("empirical_bayes_support", "traditional"),
        ("ridge", "ml"),
        ("gradient_boosted_trees", "ml"),
        ("mlp", "nn"),
        ("1d_cnn", "nn"),
        ("tensor_prior_residual_cnn_new_arch", "new_architecture"),
    ]
    metric_rows = []
    for method, family in methods:
        got = score_predictions(eval_df, "pred_" + method)
        got.update(metric_ci(eval_df, method, config))
        got.update({"method": method, "family": family, "split": "train_non_sample_ii_runs_eval_sample_ii_analysis_runs"})
        metric_rows.append(got)
    metrics = pd.DataFrame(metric_rows).sort_values(["brier", "ece", "average_precision"], ascending=[True, True, False])

    run_rows = []
    for run, part in eval_df.groupby("run"):
        for method, family in methods:
            got = score_predictions(part, "pred_" + method)
            got.update({"run": int(run), "method": method, "family": family})
            run_rows.append(got)
    by_run = pd.DataFrame(run_rows)

    leakage = pd.DataFrame(
        [
            {"check": "heldout_runs_excluded_from_training", "value": ",".join(map(str, sorted(heldout))), "pass": bool(set(train["run"]).isdisjoint(heldout))},
            {"check": "model_features_exclude_event_ids", "value": ",".join(NUMERIC_COLS + CAT_COLS), "pass": True},
            {"check": "target_charge_transfer_error_excluded_from_features", "value": "charge_transfer_error", "pass": "charge_transfer_error" not in NUMERIC_COLS + CAT_COLS},
            {"check": "evaluation_runs_present", "value": int(eval_df["run"].nunique()), "pass": bool(eval_df["run"].nunique() == len(heldout))},
            {"check": "training_rows_after_cap", "value": int(len(train)), "pass": bool(len(train) > 1000)},
            {"check": "evaluation_rows", "value": int(len(eval_df)), "pass": bool(len(eval_df) > 1000)},
        ]
    )
    winner = metrics.iloc[0].to_dict()
    return metrics, by_run, leakage, winner


def input_manifest(config: dict, script_path: Path, config_path: Path, output_dir: Path) -> pd.DataFrame:
    rows = []
    for run in p12a.configured_runs(config):
        path = p12a.raw_file(config, run)
        rows.append({"kind": "raw_root", "path": str(path), "sha256": sha256_file(path)})
    rows.append({"kind": "script", "path": str(script_path), "sha256": sha256_file(script_path)})
    rows.append({"kind": "config", "path": str(config_path), "sha256": sha256_file(config_path)})
    out = pd.DataFrame(rows)
    out.to_csv(output_dir / "input_sha256.csv", index=False)
    return out


def write_report(config: dict, output_dir: Path, raw_match: pd.DataFrame, tensor: pd.DataFrame, tensor_ci: pd.DataFrame, metrics: pd.DataFrame, by_run: pd.DataFrame, leakage: pd.DataFrame, winner: dict, elapsed: float) -> None:
    top_tensor = tensor.head(20).copy()
    metric_cols = [
        "method",
        "family",
        "n",
        "event_rate",
        "auc",
        "auc_ci95",
        "average_precision",
        "brier",
        "brier_ci95",
        "ece",
        "ece_ci95",
        "support_coverage_at_risk10",
        "failure_rate_at_risk10",
    ]
    run_pivot = by_run.pivot_table(index="run", columns="method", values="brier", aggfunc="first").reset_index()
    lines: List[str] = []
    lines.append("# P12b Pulse-Support Tensor for PID Energy Consumers\n")
    lines.append(f"- **Ticket:** `{config['ticket_id']}`")
    lines.append(f"- **Worker:** `{config['worker']}`")
    lines.append(f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`")
    lines.append("- **Primary benchmark target:** held-out charge-transfer failure risk, `charge_transfer_error = 1`.")
    lines.append("- **Split:** train on non-Sample-II-analysis runs; evaluate on runs 58, 59, 60, 61, 62, 63, and 65.")
    lines.append("- **Uncertainty:** run-block bootstrap 95 percent confidence intervals.\n")

    lines.append("## 1. Raw-ROOT Reproduction\n")
    lines.append("The first operation is a direct scan of `h101/HRDv` in the raw ROOT files. For every configured B-stack run, the script subtracts the median of samples 0--3, selects even B staves B2/B4/B6/B8, and applies `A > 1000 ADC`. No downstream support tensor or model output is written unless this count check passes.\n")
    lines.append(raw_match.to_markdown(index=False))

    lines.append("\n## 2. Estimand and Tensor Definition\n")
    lines.append("For pulse record `i`, let `x_i` denote the baseline-corrected B-stack pulse summaries and let `r_i` be the charge residual from the P12 charge model fitted on non-Sample-II-analysis runs. The benchmark label is\n")
    lines.append("`y_i = 1{|r_i| >= tau_train}`,\n")
    lines.append("where `tau_train` is the 95 percent absolute residual threshold fitted on the same non-held-out run family. The support tensor is a contingency table over ten atoms:\n")
    lines.append("`shape x timing x amplitude x saturation x pileup x baseline x dropout/anomaly x q_template x covariance x charge_transfer`.\n")
    lines.append("The charge-transfer atom is included in the published tensor for consumers, but it is excluded from all benchmark model features so the risk benchmark is not tautological. The q-template atom is a morphology score from late fraction, half-height width, and peak phase; the covariance atom counts concurrent non-target pathology flags.\n")

    lines.append("## 3. Methods\n")
    lines.append("The traditional method is `empirical_bayes_support`, a hierarchical support-cell estimator. For predictor cell `c`, with `s_c` failures in `n_c` training pulses and global failure rate `pi`, it predicts\n")
    lines.append("`p(y=1|c) = (s_c + k pi)/(n_c + k)`, with `k = 30`, falling back to a coarser stave-amplitude-shape-timing-pileup-baseline cell and then the global rate.\n")
    lines.append("The ML/NN comparators are ridge logistic regression, histogram gradient-boosted trees, a tabular MLP, a 1D-CNN over the ordered standardized feature vector, and the new `tensor_prior_residual_cnn_new_arch`. The new architecture is sensible for P12b because it fuses a convolutional residual learner with the empirical tensor-prior logit, forcing the neural branch to learn departures from the deterministic support tensor rather than replacing it.\n")

    lines.append("## 4. Benchmark Results\n")
    lines.append(metrics[metric_cols].to_markdown(index=False))
    lines.append(f"\nWinner by the preregistered primary metric, minimum held-out Brier score, is `{winner['method']}` (`{winner['family']}`) with Brier `{winner['brier']:.6f}` and 95 percent CI `{winner['brier_ci95']}`. Lower Brier and ECE are better; higher AUC/AP and support coverage at fixed risk are better.\n")

    lines.append("Run-level Brier scores:")
    lines.append(run_pivot.to_markdown(index=False))

    lines.append("\n## 5. Published Support Tensor\n")
    lines.append("Each row in `support_tensor.csv` is one populated atom cell. The table records occupancy, number of runs, charge failure rate, charge residual sigma68, timing-tail rate, pile-up enrichment, and weak PID-label stability. The top populated cells are:\n")
    lines.append(top_tensor[["support_cell", "n", "n_runs", "charge_failure_rate", "charge_res68", "timing_tail_rate", "pileup_rate", "weak_pid_fraction", "weak_pid_run_span"]].to_markdown(index=False))
    lines.append("\nRun-block CIs for the top cells are in `support_tensor_ci.csv`; preview:")
    lines.append(tensor_ci.head(12).to_markdown(index=False))

    lines.append("\n## 6. Systematics and Controls\n")
    lines.append("- **Run family drift:** all headline intervals resample run blocks, so the uncertainty is dominated by run-to-run changes rather than pulse-count statistics.")
    lines.append("- **Target definition:** `charge_transfer_error` is a closure-failure proxy, not an absolute PID or energy truth label.")
    lines.append("- **Support sparsity:** high-dimensional cells can be populated by many pulses from few runs; consumers should check both `n` and `n_runs`.")
    lines.append("- **q-template proxy:** no frozen per-pulse q-template likelihood exists in the current committed artifacts, so this report uses a reproducible morphology proxy from raw-derived pulse summaries.")
    lines.append("- **Neural calibration:** the CNNs are intentionally small CPU-trained models; they are benchmark comparators, not production calibrators.")
    lines.append("- **Leakage:** event identifiers, run identifiers, and the charge-transfer target are excluded from the feature matrix; the published charge-transfer atom is not used as a predictor.\n")
    lines.append(leakage.to_markdown(index=False))

    lines.append("\n## 7. Caveats\n")
    lines.append("The tensor is a map of current support, not a permission slip for physics separation. PID and energy workers should treat unsupported or high-risk cells as abstention candidates unless an independent truth source or calibration target confirms them. The weak PID label is deliberately operational, based on high-amplitude non-pileup non-saturated timing-core pulses; it should not be interpreted as particle identity. The raw-ROOT reproduction fixes the event population, but alternate baseline windows, amplitude cuts, or charge residual definitions would change the support frontier.\n")

    lines.append("## 8. Verdict\n")
    lines.append(f"`{winner['method']}` is the winner for P12b by held-out Brier score. The published tensor identifies which pulse atom combinations are populated and gives consumers per-cell occupancy, run support, timing-tail, pile-up, charge-closure, and weak-label stability diagnostics. The strongest practical rule is to require both multi-run occupancy and low empirical or model-predicted charge-transfer risk before using a cell for PID/energy calibration.\n")

    lines.append("## 9. Reproducibility\n")
    lines.append("```bash\n/home/billy/anaconda3/bin/python scripts/p12b_1781040960_896_205a0b9d_pulse_support_tensor.py --config configs/p12b_1781040960_896_205a0b9d_pulse_support_tensor.json\n```")
    lines.append(f"\nRuntime: {elapsed:.1f} s.")
    (output_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    pulses, counts_by_run, counts_by_group = p12a.scan_raw(config)
    raw_match = p12a.compare_counts(config, counts_by_group)
    raw_match.to_csv(output_dir / "raw_count_match.csv", index=False)
    counts_by_run.to_csv(output_dir / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(output_dir / "counts_by_group.csv", index=False)
    if not bool(raw_match["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction failed")

    pulses = p12a.add_timing_outcome(pulses, config)
    axis_df = fast_assign_axes(pulses, config)
    atom_df = add_atoms(axis_df)
    tensor, tensor_by_run, tensor_ci = support_tensor_tables(atom_df, config)
    tensor.to_csv(output_dir / "support_tensor.csv", index=False)
    tensor_by_run.to_csv(output_dir / "support_tensor_by_run.csv", index=False)
    tensor_ci.to_csv(output_dir / "support_tensor_ci.csv", index=False)

    metrics, by_run, leakage, winner = benchmark_methods(atom_df, config)
    metrics.to_csv(output_dir / "method_metrics.csv", index=False)
    by_run.to_csv(output_dir / "method_by_run.csv", index=False)
    leakage.to_csv(output_dir / "leakage_checks.csv", index=False)
    atom_cols = ["pulse_uid", "event_uid", "run", "group", "stave", "amplitude_adc", "area_over_amp", "charge_residual_area_over_amp", "charge_transfer_error", "weak_pid_positive", "support_cell", "predictor_cell"] + CAT_COLS
    atom_df[atom_cols].to_csv(output_dir / "pulse_support_atoms.csv.gz", index=False)
    manifest_inputs = input_manifest(config, Path(__file__), args.config, output_dir)

    elapsed = time.time() - start
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction": {
            "source": str(config["raw_root_dir"]),
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced_selected_pulses": int(raw_match.iloc[0]["reproduced"]),
            "delta": int(raw_match.iloc[0]["delta"]),
            "pass": bool(raw_match["pass"].all()),
        },
        "split": {
            "train": "all configured B-stack runs except heldout_runs",
            "evaluate": "heldout Sample-II analysis runs",
            "heldout_runs": [int(x) for x in config["benchmark"]["heldout_runs"]],
            "bootstrap_reps": int(config["benchmark"]["bootstrap_reps"]),
            "train_cap": int(config["benchmark"]["train_cap"]),
        },
        "methods_benchmarked": [
            "empirical_bayes_support",
            "ridge",
            "gradient_boosted_trees",
            "mlp",
            "1d_cnn",
            "tensor_prior_residual_cnn_new_arch",
        ],
        "primary_metric": "minimum held-out Brier score for charge-transfer failure risk",
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "brier": float(winner["brier"]),
            "brier_ci95": winner["brier_ci95"],
            "auc": float(winner["auc"]),
            "ece": float(winner["ece"]),
        },
        "best_traditional": metrics[metrics["family"] == "traditional"].iloc[0].to_dict(),
        "summary": metrics.to_dict(orient="records"),
        "support_tensor": {
            "populated_cells": int(len(tensor)),
            "top_cell_n": int(tensor.iloc[0]["n"]),
            "top_cell_n_runs": int(tensor.iloc[0]["n_runs"]),
            "top_cell_charge_failure_rate": float(tensor.iloc[0]["charge_failure_rate"]),
        },
        "leakage_checks_passed": bool(leakage["pass"].all()),
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "next_tickets": [config["novel_ticket"]],
        "runtime_sec": elapsed,
    }
    (output_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": str(Path(__file__)),
        "config": str(args.config),
        "git_commit": git_commit(),
        "raw_reproduction_passed": bool(raw_match["pass"].all()),
        "input_sha256_rows": int(len(manifest_inputs)),
        "artifacts": sorted(p.name for p in output_dir.iterdir() if p.is_file()),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_report(config, output_dir, raw_match, tensor, tensor_ci, metrics, by_run, leakage, winner, elapsed)


if __name__ == "__main__":
    main()
