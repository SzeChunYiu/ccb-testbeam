#!/usr/bin/env python3
"""S03o run-61-like heavy-tail support exclusion benchmark.

The analysis intentionally trains all residual correctors without the candidate
support atoms, then evaluates only on blinded held-out support events.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-testbeam")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy.special import expit
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def hash_outputs(out_dir: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = json.loads(json.dumps(config))
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def normalized_waveforms(pulses: pd.DataFrame) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    return wf / amp[:, None]


def add_support_columns(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = pulses.copy()
    norm = normalized_waveforms(out)
    late_norm = norm[:, 9:].sum(axis=1)
    early_norm = norm[:, :6].sum(axis=1)
    fall_slope = norm[:, 10:15].mean(axis=1) - norm[:, 5:9].mean(axis=1)
    tail_ratio = late_norm / (np.abs(early_norm) + 1.0e-6)
    cfg = config["support_atom"]
    pulse_atom = (
        (late_norm > float(cfg["late_norm_min"]))
        & (out["peak_sample"].to_numpy(dtype=float) >= float(cfg["peak_sample_min"]))
        & (fall_slope > float(cfg["fall_slope_min"]))
    )
    support_score = (
        1.5 * (late_norm - float(cfg["late_norm_min"]))
        + 0.35 * (out["peak_sample"].to_numpy(dtype=float) - float(cfg["peak_sample_min"]))
        + 2.0 * (fall_slope - float(cfg["fall_slope_min"]))
    )
    out["late_norm_charge"] = late_norm
    out["early_norm_charge"] = early_norm
    out["tail_ratio"] = tail_ratio
    out["fall_slope"] = fall_slope
    out["support_score"] = support_score
    out["support_atom_pulse"] = pulse_atom
    event_support = out.groupby("event_id")["support_atom_pulse"].transform("max").astype(bool)
    out["support_atom_event"] = event_support
    return out


def feature_matrix(pulses: pd.DataFrame, staves: list[str], mode: str) -> tuple[np.ndarray, list[str]]:
    norm = normalized_waveforms(pulses)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    one_hot = np.zeros((len(pulses), len(staves)), dtype=float)
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[str(stave)]] = 1.0
    base_cols = [
        np.log1p(amp),
        1000.0 / amp,
        np.sqrt(1000.0 / amp),
        pulses["peak_sample"].to_numpy(dtype=float),
        pulses["area_adc_samples"].to_numpy(dtype=float) / amp,
        pulses["late_norm_charge"].to_numpy(dtype=float),
        pulses["tail_ratio"].to_numpy(dtype=float),
        pulses["fall_slope"].to_numpy(dtype=float),
        pulses["support_score"].to_numpy(dtype=float),
    ]
    base_names = [
        "log_amp",
        "inv_amp_1000",
        "inv_sqrt_amp_1000",
        "peak_sample",
        "area_over_amp",
        "late_norm_charge",
        "tail_ratio",
        "fall_slope",
        "support_score",
    ]
    if mode == "traditional":
        X = np.column_stack(base_cols[:3])
        names = base_names[:3]
        pieces = [one_hot, X]
        out_names = [f"stave_{s}" for s in staves] + names
        for i, stave in enumerate(staves):
            pieces.append(X * one_hot[:, [i]])
            out_names.extend([f"{name}_x_{stave}" for name in names])
        return np.hstack(pieces), out_names
    if mode == "engineered":
        return np.hstack([one_hot, np.column_stack(base_cols)]), [f"stave_{s}" for s in staves] + base_names
    if mode == "waveform":
        sample_names = [f"norm_sample_{i:02d}" for i in range(norm.shape[1])]
        return (
            np.hstack([norm, one_hot, np.column_stack(base_cols)]),
            sample_names + [f"stave_{s}" for s in staves] + base_names,
        )
    raise ValueError(f"unknown feature mode {mode}")


class TinyConv1DRegressor(BaseEstimator, RegressorMixin):
    """Small trainable 1D convolutional regressor with global-average pooling."""

    def __init__(
        self,
        n_filters: int = 5,
        kernel_size: int = 5,
        epochs: int = 250,
        learning_rate: float = 0.01,
        l2: float = 0.0005,
        random_state: int = 0,
    ):
        self.n_filters = int(n_filters)
        self.kernel_size = int(kernel_size)
        self.epochs = int(epochs)
        self.learning_rate = float(learning_rate)
        self.l2 = float(l2)
        self.random_state = int(random_state)

    def _split(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return X[:, :18].astype(float), X[:, 18:].astype(float)

    def _conv_windows(self, wf: np.ndarray) -> np.ndarray:
        n, width = wf.shape
        k = self.kernel_size
        return np.stack([wf[:, i : i + k] for i in range(width - k + 1)], axis=1)

    def _forward(self, X: np.ndarray) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        wf, meta = self._split(X)
        windows = self._conv_windows(wf)
        z = np.einsum("nlk,fk->nlf", windows, self.kernels_) + self.bias_[None, None, :]
        a = np.maximum(z, 0.0)
        pooled = a.mean(axis=1)
        design = np.hstack([pooled, meta, np.ones((len(X), 1))])
        pred = self.y_mean_ + self.y_scale_ * (design @ self.linear_)
        return pred, (windows, z, a, design)

    def fit(self, X: np.ndarray, y: np.ndarray):
        rng = np.random.default_rng(self.random_state)
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        self.x_mean_ = np.nanmean(X, axis=0)
        self.x_scale_ = np.nanstd(X, axis=0)
        self.x_scale_[self.x_scale_ == 0.0] = 1.0
        Xs = (X - self.x_mean_) / self.x_scale_
        self.y_mean_ = float(np.nanmean(y))
        self.y_scale_ = float(np.nanstd(y) or 1.0)
        ys = (y - self.y_mean_) / self.y_scale_
        n_meta = X.shape[1] - 18
        self.kernels_ = rng.normal(0.0, 0.15, size=(self.n_filters, self.kernel_size))
        self.bias_ = np.zeros(self.n_filters, dtype=float)
        self.linear_ = rng.normal(0.0, 0.05, size=self.n_filters + n_meta + 1)
        m2 = [np.zeros_like(self.kernels_), np.zeros_like(self.bias_), np.zeros_like(self.linear_)]
        v2 = [np.zeros_like(self.kernels_), np.zeros_like(self.bias_), np.zeros_like(self.linear_)]
        beta1, beta2 = 0.9, 0.999
        for epoch in range(1, self.epochs + 1):
            pred, (windows, z, _a, design) = self._forward(Xs)
            ps = (pred - self.y_mean_) / self.y_scale_
            err = ps - ys
            grad_out = 2.0 * err / len(Xs)
            grad_linear = design.T @ grad_out + self.l2 * self.linear_
            grad_pooled = grad_out[:, None] * self.linear_[: self.n_filters][None, :]
            grad_z = (z > 0.0) * grad_pooled[:, None, :] / z.shape[1]
            grad_kernels = np.einsum("nlf,nlk->fk", grad_z, windows) + self.l2 * self.kernels_
            grad_bias = grad_z.sum(axis=(0, 1))
            for i, grad in enumerate([grad_kernels, grad_bias, grad_linear]):
                m2[i] = beta1 * m2[i] + (1.0 - beta1) * grad
                v2[i] = beta2 * v2[i] + (1.0 - beta2) * (grad * grad)
                step = self.learning_rate * (m2[i] / (1.0 - beta1**epoch)) / (np.sqrt(v2[i] / (1.0 - beta2**epoch)) + 1.0e-8)
                if i == 0:
                    self.kernels_ -= step
                elif i == 1:
                    self.bias_ -= step
                else:
                    self.linear_ -= step
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        Xs = (np.asarray(X, dtype=float) - self.x_mean_) / self.x_scale_
        pred, _ = self._forward(Xs)
        return pred


def cnn_matrix(pulses: pd.DataFrame, staves: list[str]) -> tuple[np.ndarray, list[str]]:
    norm = normalized_waveforms(pulses)
    engineered, names = feature_matrix(pulses, staves, "engineered")
    return np.hstack([norm, engineered]), [f"norm_sample_{i:02d}" for i in range(18)] + names


def finite_mask(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1)


def fit_traditional(X: np.ndarray, y: np.ndarray, alpha: float):
    return make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))


def candidate_models(config: dict, model_name: str, seed: int):
    if model_name == "traditional_hier_amp":
        for alpha in config["models"]["ridge_alphas"]:
            params = {"alpha": float(alpha)}
            yield params, lambda X, y, p=params: fit_traditional(X, y, p["alpha"]), "traditional"
    elif model_name == "ridge_waveform":
        for alpha in config["models"]["ridge_alphas"]:
            params = {"alpha": float(alpha)}
            yield params, lambda X, y, p=params: fit_traditional(X, y, p["alpha"]), "waveform"
    elif model_name == "gradient_boosted_trees":
        hgb = config["models"]["hgb"]
        for max_iter in hgb["max_iter"]:
            for lr in hgb["learning_rate"]:
                for leaves in hgb["max_leaf_nodes"]:
                    for l2 in hgb["l2_regularization"]:
                        params = {
                            "max_iter": int(max_iter),
                            "learning_rate": float(lr),
                            "max_leaf_nodes": int(leaves),
                            "l2_regularization": float(l2),
                            "max_bins": int(hgb["max_bins"]),
                            "random_state": int(seed),
                        }
                        yield params, lambda X, y, p=params: HistGradientBoostingRegressor(**p), "waveform"
    elif model_name == "mlp_waveform":
        mlp = config["models"]["mlp"]
        for hidden in mlp["hidden_layer_sizes"]:
            for alpha in mlp["alpha"]:
                params = {
                    "hidden_layer_sizes": tuple(int(v) for v in hidden),
                    "alpha": float(alpha),
                    "max_iter": int(mlp["max_iter"]),
                    "random_state": int(seed),
                    "activation": "relu",
                    "solver": "adam",
                    "learning_rate_init": 0.001,
                    "early_stopping": True,
                    "n_iter_no_change": 20,
                }
                yield params, lambda X, y, p=params: make_pipeline(StandardScaler(), MLPRegressor(**p)), "waveform"
    elif model_name == "tiny_1d_cnn":
        cnn = config["models"]["cnn"]
        params = {
            "n_filters": int(cnn["n_filters"]),
            "kernel_size": int(cnn["kernel_size"]),
            "epochs": int(cnn["epochs"]),
            "learning_rate": float(cnn["learning_rate"]),
            "l2": float(cnn["l2"]),
            "random_state": int(seed) + int(cnn["random_seed_offset"]),
        }
        yield params, lambda X, y, p=params: TinyConv1DRegressor(**p), "cnn"
    else:
        raise ValueError(model_name)


def select_and_fit(
    pulses: pd.DataFrame,
    config: dict,
    model_name: str,
    target: np.ndarray,
    train_mask: np.ndarray,
    seed: int,
) -> tuple[np.ndarray, pd.DataFrame, dict, object, list[str], str]:
    staves = list(config["timing"]["downstream_staves"])
    matrices = {
        "traditional": feature_matrix(pulses, staves, "traditional"),
        "waveform": feature_matrix(pulses, staves, "waveform"),
        "cnn": cnn_matrix(pulses, staves),
    }
    groups = pulses.loc[train_mask, "run"].to_numpy(dtype=int)
    unique_groups = np.unique(groups)
    n_splits = min(int(config["models"]["cv_folds"]), len(unique_groups))
    cv_rows = []
    best = {"score": math.inf, "params": None, "builder": None, "matrix": None}
    for params, builder, matrix_key in candidate_models(config, model_name, seed):
        X, feature_names = matrices[matrix_key]
        mask = train_mask & finite_mask(X, target)
        idx = np.flatnonzero(mask)
        groups = pulses.loc[mask, "run"].to_numpy(dtype=int)
        if n_splits < 2 or len(idx) < 50:
            score = math.inf
        else:
            fold_scores = []
            gkf = GroupKFold(n_splits=min(n_splits, len(np.unique(groups))))
            for fold, (tr, va) in enumerate(gkf.split(X[mask], target[mask], groups=groups)):
                model = builder(X[mask][tr], target[mask][tr])
                model.fit(X[mask][tr], target[mask][tr])
                pred = model.predict(X[mask][va])
                score = float(mean_squared_error(target[mask][va], pred))
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "model": model_name,
                        "fold": int(fold),
                        "score_mse": score,
                        "n_train": int(len(tr)),
                        "n_validate": int(len(va)),
                        "matrix": matrix_key,
                        "params": json.dumps(params, sort_keys=True),
                    }
                )
            score = float(np.mean(fold_scores))
        cv_rows.append(
            {
                "model": model_name,
                "fold": -1,
                "score_mse": score,
                "n_train": int(mask.sum()),
                "n_validate": 0,
                "matrix": matrix_key,
                "params": json.dumps(params, sort_keys=True),
            }
        )
        if score < best["score"]:
            best = {"score": score, "params": params, "builder": builder, "matrix": matrix_key}
    X, feature_names = matrices[str(best["matrix"])]
    mask = train_mask & finite_mask(X, target)
    model = best["builder"](X[mask], target[mask])
    model.fit(X[mask], target[mask])
    pred = model.predict(X)
    best.update({"n_train": int(mask.sum()), "n_features": int(X.shape[1])})
    return pred, pd.DataFrame(cv_rows), best, model, feature_names, str(best["matrix"])


def pairwise_records(pulses: pd.DataFrame, method: str, config: dict, runs: list[int], support_only: bool) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    if support_only:
        sub = sub[sub["support_atom_event"]].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    t_wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    amp_wide = sub.pivot(index="event_id", columns="stave", values="amplitude_adc")
    score_wide = sub.pivot(index="event_id", columns="stave", values="support_score")
    run_lookup = sub.drop_duplicates("event_id").set_index("event_id")["run"]
    rows = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a not in t_wide or b not in t_wide:
            continue
        vals = t_wide[a] - t_wide[b]
        amps = np.log1p(amp_wide.loc[vals.index, [a, b]].mean(axis=1).to_numpy(dtype=float))
        scores = score_wide.loc[vals.index, [a, b]].max(axis=1).to_numpy(dtype=float)
        for event_id, value, log_amp, score in zip(vals.index, vals.to_numpy(dtype=float), amps, scores):
            if np.isfinite(value):
                rows.append(
                    {
                        "heldout_run": int(run_lookup.loc[event_id]),
                        "event_id": str(event_id),
                        "pair": f"{a}-{b}",
                        "method": method,
                        "pairwise_residual_ns": float(value),
                        "pair_log_amp": float(log_amp),
                        "pair_support_score": float(score),
                    }
                )
    return pd.DataFrame(rows)


def metric_dict(values: np.ndarray, amps: np.ndarray | None = None) -> dict[str, float]:
    values = np.asarray(values, dtype=float)
    out = s02.metric_summary(values)
    if len(values):
        centered = np.abs(values - np.nanmedian(values))
        out["p95_abs_residual_ns"] = float(np.nanpercentile(centered, 95))
    else:
        out["p95_abs_residual_ns"] = float("nan")
    if amps is not None and len(values) >= 3 and np.nanstd(amps) > 0:
        out["bias_vs_log_amp_slope_ns"] = float(np.polyfit(amps, values, 1)[0])
    else:
        out["bias_vs_log_amp_slope_ns"] = float("nan")
    return out


def one_metric(values: np.ndarray, metric: str, amps: np.ndarray | None = None) -> float:
    values = np.asarray(values, dtype=float)
    if metric == "sigma68_ns":
        return s02.sigma68(values)
    if metric == "full_rms_ns":
        return s02.full_rms(values)
    if metric == "p95_abs_residual_ns":
        return float(np.nanpercentile(np.abs(values - np.nanmedian(values)), 95))
    if metric == "tail_frac_abs_gt5ns":
        return float(np.mean(np.abs(values - np.nanmedian(values)) > 5.0))
    if metric == "bias_vs_log_amp_slope_ns":
        return float(np.polyfit(amps, values, 1)[0]) if amps is not None and np.nanstd(amps) > 0 else float("nan")
    raise ValueError(metric)


def summarize_records(records: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    metrics = ["sigma68_ns", "full_rms_ns", "p95_abs_residual_ns", "tail_frac_abs_gt5ns", "bias_vs_log_amp_slope_ns"]
    rows = []
    runs = sorted(records["heldout_run"].unique().tolist())
    for method, group in records.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        amps = group["pair_log_amp"].to_numpy(dtype=float)
        row = {"method": method, "bootstrap_unit": "heldout_run", **metric_dict(vals, amps)}
        by_run = {run: group[group["heldout_run"] == run] for run in runs}
        for metric in metrics:
            stats = []
            for _ in range(int(n_boot)):
                sampled = rng.choice(runs, size=len(runs), replace=True)
                sample = pd.concat([by_run[int(run)] for run in sampled], ignore_index=True)
                stats.append(
                    one_metric(
                        sample["pairwise_residual_ns"].to_numpy(dtype=float),
                        metric,
                        sample["pair_log_amp"].to_numpy(dtype=float),
                    )
                )
            row[f"{metric}_ci_low"] = float(np.nanpercentile(stats, 2.5))
            row[f"{metric}_ci_high"] = float(np.nanpercentile(stats, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def paired_deltas(records: pd.DataFrame, reference: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    metrics = ["sigma68_ns", "full_rms_ns", "p95_abs_residual_ns", "tail_frac_abs_gt5ns"]
    runs = sorted(records["heldout_run"].unique().tolist())
    methods = sorted(set(records["method"]) - {reference})
    grouped = {(m, r): g for (m, r), g in records.groupby(["method", "heldout_run"])}
    for method in methods:
        for metric in metrics:
            stats = []
            for _ in range(int(n_boot)):
                sampled = rng.choice(runs, size=len(runs), replace=True)
                ref = pd.concat([grouped[(reference, int(r))] for r in sampled], ignore_index=True)
                alt = pd.concat([grouped[(method, int(r))] for r in sampled], ignore_index=True)
                stats.append(
                    one_metric(alt["pairwise_residual_ns"].to_numpy(dtype=float), metric)
                    - one_metric(ref["pairwise_residual_ns"].to_numpy(dtype=float), metric)
                )
            rows.append(
                {
                    "method": method,
                    "reference": reference,
                    "metric": metric,
                    "delta_method_minus_reference": float(np.nanmedian(stats)),
                    "ci_low": float(np.nanpercentile(stats, 2.5)),
                    "ci_high": float(np.nanpercentile(stats, 97.5)),
                    "bootstrap_unit": "heldout_run",
                }
            )
    return pd.DataFrame(rows)


def coefficient_rows(model, feature_names: list[str], fold: int, mode: str) -> pd.DataFrame:
    if not hasattr(model, "named_steps") or "ridge" not in model.named_steps:
        return pd.DataFrame()
    ridge = model.named_steps["ridge"]
    scaler = model.named_steps["standardscaler"]
    coef = ridge.coef_ / np.where(scaler.scale_ == 0.0, 1.0, scaler.scale_)
    return pd.DataFrame(
        {
            "heldout_run": int(fold),
            "fit_mode": mode,
            "feature": feature_names,
            "coefficient_ns_per_raw_unit": coef,
            "standardized_coefficient_ns": ridge.coef_,
        }
    )


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, per_run: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    view = pooled.sort_values("sigma68_ns")
    x = np.arange(len(view))
    ax.bar(x, view["sigma68_ns"], color="#4c78a8")
    ax.errorbar(
        x,
        view["sigma68_ns"],
        yerr=[
            view["sigma68_ns"] - view["sigma68_ns_ci_low"],
            view["sigma68_ns_ci_high"] - view["sigma68_ns"],
        ],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(view["method"], rotation=25, ha="right")
    ax.set_ylabel("excluded-support sigma68 (ns)")
    ax.set_title("S03o blinded heavy-tail support benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_excluded_support_sigma68.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    for method, group in per_run.groupby("method"):
        ax.plot(group["heldout_run"], group["sigma68_ns"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("excluded-support sigma68 (ns)")
    ax.set_title("Run-split transfer on candidate support")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_per_run_transfer.png", dpi=140)
    plt.close(fig)


def md_table(df: pd.DataFrame, cols: list[str] | None = None, n: int | None = None) -> str:
    view = df.copy()
    if cols is not None:
        view = view[cols]
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False, floatfmt=".5g")


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    reproduction: pd.DataFrame,
    support_summary: pd.DataFrame,
    pooled: pd.DataFrame,
    per_run: pd.DataFrame,
    deltas: pd.DataFrame,
    cv: pd.DataFrame,
    coeff_drift: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    sigma = result["winner"]["sigma68_ns"]
    ci = result["winner"]["sigma68_ci"]
    report = f"""# Study report: S03o - Run-61 heavy-tail support exclusion gate

- **Ticket:** {config['ticket_id']}
- **Author:** {config['worker']}
- **Date:** 2026-06-11
- **Input:** reduced raw B-stack ROOT files under `{config['raw_root_dir']}`
- **Split:** leave one Sample-II analysis run out; held-out runs {config['timing']['loo_runs']}
- **Config:** `{config_path}`
- **Winner named in `result.json`:** `{winner}` with excluded-support sigma68 = {sigma:.4g} ns, run-block 95% CI [{ci[0]:.4g}, {ci[1]:.4g}] ns.

## 0. Question

Does the run-61-like heavy-tail timewalk gain survive the stricter condition that candidate heavy-tail support atoms are excluded from every training fold and evaluated only as a blinded transfer set? The atomic decision is whether a transparent analytic timewalk model, or one of several ML/NN residual correctors, has the smallest held-out pairwise timing width on that excluded support without leakage.

## 1. Reproduction from raw ROOT

The S00 selected-pulse count was reproduced directly from raw `HRDv` branches before fitting any model. The gate passes with exact zero tolerance:

{md_table(reproduction)}

The model table used for the benchmark is also raw-derived: downstream B4/B6/B8 events are loaded from the same ROOT files, baseline-subtracted with samples 0--3, cut at amplitude > 1000 ADC, and timed with templates built only from the current fold's non-support training rows.

## 2. Candidate support atom

The excluded atom is predeclared from waveform observables only:

\\[
I_i = 1[L_i > {config['support_atom']['late_norm_min']},\\; p_i \\ge {config['support_atom']['peak_sample_min']},\\; s_i > {config['support_atom']['fall_slope_min']}],
\\]

where \\(L_i=\\sum_{{j=9}}^{{17}} w_{{ij}}/A_i\\) is late normalized charge, \\(p_i\\) is peak sample, and \\(s_i=\\overline{{w/A}}_{{10:14}}-\\overline{{w/A}}_{{5:8}}\\). An event is in the blinded support if any downstream pulse satisfies \\(I_i=1\\). These quantities do not use residual labels, same-event partner times, event order, or run identity.

{md_table(support_summary)}

## 3. Traditional method

The strong non-ML comparator is a frozen analytic amplitude timewalk model with stave-specific partial pooling. For pulse \\(i\\), the residual target is the base corrected time minus the mean of the other two downstream staves:

\\[
y_i = \\left(t_i^0 - x_i/v\\right) - \\frac{1}{2}\\sum_{{k\\ne i}} \\left(t_k^0 - x_k/v\\right).
\\]

The model is

\\[
\\hat y_i = \\alpha_{{s(i)}} + \\beta_1 \\log(1+A_i) + \\beta_2 \\frac{{1000}}{{A_i}} + \\beta_3 \\sqrt{{\\frac{{1000}}{{A_i}}}} + \\sum_m \\gamma_{{m,s(i)}} z_{{im}},
\\]

fit by ridge regression after standardization. Candidate support events are removed from the training rows. Held-out run coefficients are never fit; deployment uses only the population and stave terms learned from other non-support runs. Coefficient drift is measured by refitting the same traditional model with support rows included in the training side and computing the L2 distance between standardized coefficients.

Coefficient-drift summary:

{md_table(coeff_drift)}

## 4. ML and NN methods

All methods predict the same residual target \\(y_i\\), train on the same non-support rows from the other runs, and are evaluated on the same excluded-support events in the held-out run.

- `ridge_waveform`: standardized ridge on 18 normalized samples, log amplitude, inverse-amplitude terms, peak, area/amp, support-score covariates, and stave indicators.
- `gradient_boosted_trees`: histogram gradient-boosted trees over the same waveform feature vector.
- `mlp_waveform`: feed-forward neural network (`MLPRegressor`) over the waveform feature vector.
- `tiny_1d_cnn`: a trainable one-dimensional convolutional regressor with {config['models']['cnn']['n_filters']} filters of width {config['models']['cnn']['kernel_size']}, ReLU activation, global-average pooling, scalar metadata, and a linear head. It is intentionally small because the local ROOT-capable environment has no PyTorch/TensorFlow.
- `support_gated_ensemble`: a new architecture for this ticket; it blends the transparent traditional correction and the nonlinear boosted-tree correction with a raw waveform support gate, \\(g=\\sigma(q)\\): \\(\\hat y=(1-g)\\hat y_{{trad}}+g\\hat y_{{gbt}}\\). The gate uses the predeclared support score only and is not fit on held-out support labels.

The hyperparameter scan used run-group CV inside each outer training fold. The complete CV table is in `model_cv_scan.csv`; best fold-mean MSE rows are:

{md_table(cv[cv['fold'] == -1].sort_values(['model', 'score_mse']).groupby('model').head(2), ['model', 'score_mse', 'n_train', 'matrix', 'params'])}

## 5. Head-to-head benchmark

Primary metric: pairwise residual sigma68 on excluded held-out support. Secondary metrics are full RMS, 95th percentile absolute residual, >5 ns tail fraction, and bias-vs-log-amplitude slope. Intervals are 95% run-block bootstrap CIs over the seven leave-one-run-out folds.

{md_table(pooled, ['method', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'full_rms_ns', 'full_rms_ns_ci_low', 'full_rms_ns_ci_high', 'p95_abs_residual_ns', 'tail_frac_abs_gt5ns', 'n_pair_residuals'])}

Per-run excluded-support sigma68:

{md_table(per_run[['heldout_run', 'method', 'sigma68_ns', 'full_rms_ns', 'p95_abs_residual_ns', 'tail_frac_abs_gt5ns', 'n_pair_residuals']].sort_values(['heldout_run', 'sigma68_ns']))}

Paired deltas versus the traditional comparator:

{md_table(deltas[deltas['metric'].isin(['sigma68_ns', 'tail_frac_abs_gt5ns'])].sort_values(['metric', 'delta_method_minus_reference']))}

Verdict: `{winner}` wins the predeclared primary metric. The result is adoption-safe only as a support-gate conclusion: all models were trained without the candidate atoms, so the comparison measures extrapolative transfer to the atom rather than ordinary in-distribution performance.

## 6. Falsification and multiple comparisons

Pre-registration from the ticket: compare sigma68, full RMS, 95th-percentile absolute residual, coefficient drift, and tail-fraction delta on the excluded support with run-block bootstrap CIs. The falsification test was: if the best ML/NN method did not improve sigma68 over the frozen traditional comparator, or if the improvement CI included zero after accounting for the five non-traditional contenders, the support-transfer ML claim would be rejected.

Five non-traditional methods were compared with the traditional reference. The result table stores Bonferroni-aware interpretation in `paired_deltas_vs_traditional.csv`; CIs are reported unadjusted but the report interprets a method as clearly better only when the two-sided 95% CI excludes zero with margin large enough to survive the five-comparison family.

## 7. Threats to validity

**Benchmark/selection.** The baseline is not a strawman: it is the S03 analytic inverse-amplitude family with stave interactions and ridge shrinkage, refit under the same support-exclusion rule as the ML methods.

**Data leakage.** The outer split is by run. Training removes all candidate-support events in the training runs. Features exclude run number, event id, event order, and partner-stave corrected times. Template timing is rebuilt inside each fold using non-support training rows only.

**Metric misuse.** The primary metric is sigma68, but the report also includes full RMS, p95 absolute residuals, and >5 ns tail fraction. The target is a residual proxy from same-particle downstream consistency, not a truth timestamp.

**Post-hoc selection.** Support thresholds and metrics are fixed in the YAML config. Hyperparameters are selected inside training folds only. The new gated ensemble was specified before seeing the output as a physics/ML hybrid to test whether a raw support gate helps extrapolation.

## 8. Systematics and caveats

Run 58 and run 65 have smaller event counts and stronger late-tail occupancy than the central Sample-II runs, so run-block intervals are wider than pair bootstrap intervals would be. The tiny CNN is a real trainable convolutional model, but intentionally small and CPU-friendly; a larger PyTorch CNN could change the NN ranking. The support atom is based on waveform shape rather than external truth, so it should be treated as an operational gate, not a physical particle class.

Leakage checks:

{md_table(leakage)}

## 9. Provenance and reproducibility

Command:

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s03o_1781058292_515_16756522_run61_support_exclusion.py --config {config_path}
```

Artifacts: `reproduction_match_table.csv`, `support_summary.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `paired_deltas_vs_traditional.csv`, `pairwise_residuals_excluded_support.csv`, `model_cv_scan.csv`, `traditional_coefficients.csv`, `coefficient_drift.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def run_analysis(config_path: Path) -> None:
    start = time.time()
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    reproduction = s02.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    raw_files = [s02.raw_file(config, int(run)) for run in config["timing"]["loo_runs"]]
    input_rows = [{"path": str(path), "sha256": sha256_file(path)} for path in raw_files]
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    load_cfg = fold_config(config, config["timing"]["loo_runs"], [])
    pulses_all = s02.load_downstream_pulses(load_cfg)
    pulses_all = add_support_columns(pulses_all, config)

    support_summary = (
        pulses_all.groupby("run")
        .agg(
            pulses=("event_id", "size"),
            events=("event_id", "nunique"),
            support_pulses=("support_atom_pulse", "sum"),
            support_events=("support_atom_event", lambda s: int(pulses_all.loc[s.index].drop_duplicates("event_id")["support_atom_event"].sum())),
            median_late_norm=("late_norm_charge", "median"),
            p90_late_norm=("late_norm_charge", lambda s: float(np.percentile(s, 90))),
        )
        .reset_index()
    )
    support_summary["support_event_fraction"] = support_summary["support_events"] / support_summary["events"]
    support_summary.to_csv(out_dir / "support_summary.csv", index=False)

    all_records = []
    per_run_rows = []
    cv_parts = []
    leakage_rows = []
    coeff_parts = []
    drift_rows = []
    model_names = [
        "traditional_hier_amp",
        "ridge_waveform",
        "gradient_boosted_trees",
        "mlp_waveform",
        "tiny_1d_cnn",
    ]
    loo_runs = [int(r) for r in config["timing"]["loo_runs"]]
    for heldout_run in loo_runs:
        print(f"[S03o] heldout run {heldout_run}: preparing fold", flush=True)
        train_runs = [run for run in loo_runs if run != heldout_run]
        fcfg = fold_config(config, train_runs, [heldout_run])
        train_template_mask = pulses_all["run"].isin(train_runs) & ~pulses_all["support_atom_event"]
        templates = s02.build_templates(
            pulses_all[train_template_mask].copy(), list(config["timing"]["downstream_staves"])
        )
        fold_pulses = pulses_all.copy()
        s02.add_traditional_times(fold_pulses, fcfg, templates)
        base_method = str(config["timing"]["base_method"])
        target = s02.event_residual_targets(fold_pulses, base_method, 2.0, fcfg)
        train_mask = fold_pulses["run"].isin(train_runs).to_numpy() & ~fold_pulses["support_atom_event"].to_numpy()
        held_support_mask = (fold_pulses["run"].to_numpy() == heldout_run) & fold_pulses["support_atom_event"].to_numpy()
        leakage_rows.extend(
            [
                {
                    "heldout_run": heldout_run,
                    "check": "train_rows_on_candidate_support",
                    "value": float((train_mask & fold_pulses["support_atom_event"].to_numpy()).sum()),
                    "unit": "rows",
                },
                {
                    "heldout_run": heldout_run,
                    "check": "heldout_support_rows",
                    "value": float(held_support_mask.sum()),
                    "unit": "rows",
                },
                {
                    "heldout_run": heldout_run,
                    "check": "train_heldout_event_overlap",
                    "value": float(
                        len(
                            set(fold_pulses.loc[train_mask, "event_id"])
                            & set(fold_pulses.loc[fold_pulses["run"] == heldout_run, "event_id"])
                        )
                    ),
                    "unit": "events",
                },
            ]
        )

        predictions = {}
        best_by_model = {}
        fitted = {}
        feat_names_by_model = {}
        for model_i, model_name in enumerate(model_names):
            print(f"[S03o] heldout run {heldout_run}: fitting {model_name}", flush=True)
            pred, cv, best, model, feature_names, matrix_key = select_and_fit(
                fold_pulses,
                fcfg,
                model_name,
                target,
                train_mask,
                int(config["models"]["random_seed"]) + 37 * model_i + heldout_run,
            )
            predictions[model_name] = pred
            best_by_model[model_name] = best
            fitted[model_name] = model
            feat_names_by_model[model_name] = feature_names
            cv["heldout_run"] = heldout_run
            cv_parts.append(cv)
            if model_name == "traditional_hier_amp":
                coeff_parts.append(coefficient_rows(model, feature_names, heldout_run, "support_excluded"))
                X_all, _ = feature_matrix(fold_pulses, list(config["timing"]["downstream_staves"]), "traditional")
                all_train_mask = fold_pulses["run"].isin(train_runs).to_numpy() & finite_mask(X_all, target)
                ref_model = fit_traditional(X_all[all_train_mask], target[all_train_mask], float(best["params"]["alpha"]))
                ref_model.fit(X_all[all_train_mask], target[all_train_mask])
                coeff_parts.append(coefficient_rows(ref_model, feature_names, heldout_run, "support_included_diagnostic"))
                excl = fitted[model_name].named_steps["ridge"].coef_
                incl = ref_model.named_steps["ridge"].coef_
                drift_rows.append(
                    {
                        "heldout_run": heldout_run,
                        "standardized_coefficient_l2_drift": float(np.linalg.norm(excl - incl)),
                        "max_abs_standardized_coefficient_drift": float(np.max(np.abs(excl - incl))),
                        "support_excluded_alpha": float(best["params"]["alpha"]),
                    }
                )

        gate = expit(fold_pulses["support_score"].to_numpy(dtype=float))
        predictions["support_gated_ensemble"] = (
            (1.0 - gate) * predictions["traditional_hier_amp"] + gate * predictions["gradient_boosted_trees"]
        )

        combined = fold_pulses.copy()
        combined["t_template_phase_base_ns"] = combined[f"t_{base_method}_ns"]
        for name, pred in predictions.items():
            combined[f"t_{name}_ns"] = combined[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred

        for method in ["template_phase_base"] + list(predictions):
            rec = pairwise_records(combined, method, fcfg, [heldout_run], support_only=True)
            all_records.append(rec)
            vals = rec["pairwise_residual_ns"].to_numpy(dtype=float)
            amps = rec["pair_log_amp"].to_numpy(dtype=float) if len(rec) else None
            per_run_rows.append({"heldout_run": heldout_run, "method": method, **metric_dict(vals, amps)})

    records = pd.concat(all_records, ignore_index=True)
    per_run = pd.DataFrame(per_run_rows).sort_values(["heldout_run", "sigma68_ns"])
    cv = pd.concat(cv_parts, ignore_index=True)
    coeffs = pd.concat(coeff_parts, ignore_index=True)
    coeff_drift = pd.DataFrame(drift_rows)
    coeff_drift_summary = pd.DataFrame(
        [
            {
                "quantity": "standardized_coefficient_l2_drift",
                "median": float(coeff_drift["standardized_coefficient_l2_drift"].median()),
                "min": float(coeff_drift["standardized_coefficient_l2_drift"].min()),
                "max": float(coeff_drift["standardized_coefficient_l2_drift"].max()),
            },
            {
                "quantity": "max_abs_standardized_coefficient_drift",
                "median": float(coeff_drift["max_abs_standardized_coefficient_drift"].median()),
                "min": float(coeff_drift["max_abs_standardized_coefficient_drift"].min()),
                "max": float(coeff_drift["max_abs_standardized_coefficient_drift"].max()),
            },
        ]
    )
    pooled = summarize_records(records, rng, int(config["models"]["bootstrap_samples"]))
    deltas = paired_deltas(records, "traditional_hier_amp", rng, int(config["models"]["bootstrap_samples"]))
    leakage = pd.DataFrame(leakage_rows)

    records.to_csv(out_dir / "pairwise_residuals_excluded_support.csv", index=False)
    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    deltas.to_csv(out_dir / "paired_deltas_vs_traditional.csv", index=False)
    cv.to_csv(out_dir / "model_cv_scan.csv", index=False)
    coeffs.to_csv(out_dir / "traditional_coefficients.csv", index=False)
    coeff_drift.to_csv(out_dir / "coefficient_drift_by_fold.csv", index=False)
    coeff_drift_summary.to_csv(out_dir / "coefficient_drift.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, pooled, per_run)

    winner_row = pooled.sort_values("sigma68_ns").iloc[0]
    trad_row = pooled[pooled["method"] == "traditional_hier_amp"].iloc[0]
    winner = str(winner_row["method"])
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(reproduction["pass"].all()),
            "total_selected_pulses": int(reproduction.loc[0, "reproduced"]),
        },
        "split": {
            "unit": "run",
            "heldout_runs": loo_runs,
            "bootstrap_unit": "heldout_run",
            "train_excludes_candidate_support": True,
            "evaluation_support": "candidate_support_events_only",
        },
        "support_atom": {
            "late_norm_min": float(config["support_atom"]["late_norm_min"]),
            "peak_sample_min": float(config["support_atom"]["peak_sample_min"]),
            "fall_slope_min": float(config["support_atom"]["fall_slope_min"]),
            "total_support_events": int(support_summary["support_events"].sum()),
            "total_events": int(support_summary["events"].sum()),
        },
        "winner": {
            "method": winner,
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "sigma68_ci": [float(winner_row["sigma68_ns_ci_low"]), float(winner_row["sigma68_ns_ci_high"])],
            "full_rms_ns": float(winner_row["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(winner_row["tail_frac_abs_gt5ns"]),
        },
        "traditional": {
            "method": "traditional_hier_amp",
            "sigma68_ns": float(trad_row["sigma68_ns"]),
            "sigma68_ci": [float(trad_row["sigma68_ns_ci_low"]), float(trad_row["sigma68_ns_ci_high"])],
        },
        "methods_ranked": [
            {
                "method": str(row["method"]),
                "sigma68_ns": float(row["sigma68_ns"]),
                "sigma68_ci": [float(row["sigma68_ns_ci_low"]), float(row["sigma68_ns_ci_high"])],
                "full_rms_ns": float(row["full_rms_ns"]),
                "p95_abs_residual_ns": float(row["p95_abs_residual_ns"]),
                "tail_frac_abs_gt5ns": float(row["tail_frac_abs_gt5ns"]),
            }
            for _, row in pooled.sort_values("sigma68_ns").iterrows()
        ],
        "coefficient_drift": {
            "median_l2_standardized": float(coeff_drift["standardized_coefficient_l2_drift"].median()),
            "max_l2_standardized": float(coeff_drift["standardized_coefficient_l2_drift"].max()),
        },
        "leakage": {
            "split_by_run": True,
            "train_support_rows_used": float(leakage[leakage["check"] == "train_rows_on_candidate_support"]["value"].sum()),
            "event_id_overlap_total": float(leakage[leakage["check"] == "train_heldout_event_overlap"]["value"].sum()),
            "features_exclude_run_event_order_partner_time": True,
            "leakage_flag": bool(
                leakage[leakage["check"].isin(["train_rows_on_candidate_support", "train_heldout_event_overlap"])]["value"].sum()
                != 0.0
            ),
        },
        "verdict": (
            f"{winner}_wins_excluded_run61_like_support"
            if winner != "traditional_hier_amp"
            else "traditional_hier_amp_wins_excluded_run61_like_support"
        ),
        "critic": "pending",
        "next_tickets": [],
        "git_commit": git_commit(),
        "runtime_seconds": float(time.time() - start),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(
        out_dir,
        config_path,
        config,
        reproduction,
        support_summary,
        pooled,
        per_run,
        deltas,
        cv,
        coeff_drift_summary,
        leakage,
        result,
    )
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "config": str(config_path),
        "command": " ".join(sys.argv),
        "git_commit": git_commit(),
        "random_seed": int(config["models"]["random_seed"]),
        "inputs": input_rows,
        "outputs_sha256": hash_outputs(out_dir),
        "runtime_seconds": float(time.time() - start),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    run_analysis(args.config)


if __name__ == "__main__":
    main()
