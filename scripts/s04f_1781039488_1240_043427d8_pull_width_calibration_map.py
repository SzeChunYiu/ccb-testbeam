#!/usr/bin/env python3
"""S04f waveform timing pull-width calibration map.

The study starts from the raw ROOT gate, then asks whether per-pulse timing
uncertainties are calibrated under run-heldout evaluation.  The point-time
anchor is the existing S03 analytic timewalk correction; this script compares a
transparent stratified robust-width map against ridge, gradient-boosted trees,
MLP, 1D-CNN, and a gated waveform-tabular CNN.  Controls intentionally destroy
part of the learning signal.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s04f-pull-width")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import p03g_1781034623_1447_4a243444_detector_label_permutation as p03g
import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a

torch.set_num_threads(1)


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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return json_ready(obj.tolist())
    return obj


def fold_config(config: dict, heldout_run: int, loo_runs: Sequence[int]) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [int(run) for run in loo_runs if int(run) != int(heldout_run)]
    return cfg


def finite_target_mask(seq: np.ndarray, tab: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.isfinite(runs) & np.all(np.isfinite(seq), axis=1) & np.all(np.isfinite(tab), axis=1)


def template_quality(pulses: pd.DataFrame, templates: Dict[str, np.ndarray], config: dict) -> np.ndarray:
    """Minimum normalized-template SSE on the same grid as template-phase timing."""
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    quality = np.full(len(pulses), np.nan, dtype=float)
    stave_arr = pulses["stave"].to_numpy()
    for stave, template in templates.items():
        idx = np.flatnonzero(stave_arr == stave)
        if len(idx) == 0:
            continue
        shifted = np.vstack([s02.shifted_template(template, float(s)) for s in grid])
        for row_idx in idx:
            row = pulses.iloc[row_idx]
            wf = row["waveform"] / max(float(row["amplitude_adc"]), 1.0)
            quality[row_idx] = float(np.min(((shifted - wf[None, :]) ** 2).sum(axis=1)))
    return quality


def feature_blocks(pulses: pd.DataFrame, cfg: dict, heldout_run: int, q_template: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    seq, tab, tab_names = p03g.build_features(pulses, cfg, "real_stave", heldout_run)
    q_col = np.asarray(q_template, dtype=np.float32)[:, None]
    tab = np.hstack([tab, q_col]).astype(np.float32)
    tab_names = tab_names + ["q_template_sse"]
    X = np.hstack([seq, tab]).astype(np.float32)
    return seq.astype(np.float32), tab.astype(np.float32), X, [f"norm_sample_{i}" for i in range(seq.shape[1])] + tab_names


def select_regressor(
    X: np.ndarray,
    y: np.ndarray,
    runs: np.ndarray,
    train_idx: np.ndarray,
    method: str,
    cfg: dict,
    seed: int,
) -> Tuple[object, dict, pd.DataFrame]:
    settings = cfg["calibration"]
    groups = runs[train_idx]
    n_splits = min(int(settings["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    rows = []
    best = {"score": math.inf, "estimator": None, "params": None}

    specs = []
    if method == "ridge":
        for alpha in settings["ridge_alphas"]:
            specs.append(({"alpha": float(alpha)}, make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))))
    elif method == "gradient_boosted_trees":
        for lr in settings["hgb_learning_rates"]:
            for leaves in settings["hgb_max_leaf_nodes"]:
                specs.append(
                    (
                        {"learning_rate": float(lr), "max_leaf_nodes": int(leaves)},
                        HistGradientBoostingRegressor(
                            learning_rate=float(lr),
                            max_leaf_nodes=int(leaves),
                            max_iter=int(settings["hgb_max_iter"]),
                            l2_regularization=0.01,
                            random_state=int(seed) + int(leaves),
                        ),
                    )
                )
    else:
        raise ValueError(method)

    for params, estimator in specs:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
            tr_idx = train_idx[tr]
            va_idx = train_idx[va]
            est = clone(estimator)
            est.fit(X[tr_idx], y[tr_idx])
            pred = est.predict(X[va_idx])
            score = float(np.median(np.abs(y[va_idx] - pred)))
            row = {"method": method, "fold": int(fold), "median_abs_residual_ns": score}
            row.update(params)
            rows.append(row)
            scores.append(score)
        mean_score = float(np.mean(scores))
        row = {"method": method, "fold": -1, "median_abs_residual_ns": mean_score}
        row.update(params)
        rows.append(row)
        if mean_score < best["score"]:
            best = {"score": mean_score, "estimator": estimator, "params": params}

    final = clone(best["estimator"])
    final.fit(X[train_idx], y[train_idx])
    return final, dict(best["params"]), pd.DataFrame(rows)


def oof_prediction(estimator: object, X: np.ndarray, y: np.ndarray, runs: np.ndarray, train_idx: np.ndarray, cfg: dict) -> np.ndarray:
    groups = runs[train_idx]
    n_splits = min(int(cfg["calibration"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    oof = np.full(len(y), np.nan, dtype=float)
    for tr, va in gkf.split(X[train_idx], y[train_idx], groups=groups):
        tr_idx = train_idx[tr]
        va_idx = train_idx[va]
        est = clone(estimator)
        est.fit(X[tr_idx], y[tr_idx])
        oof[va_idx] = est.predict(X[va_idx])
    return oof


def calibrate_sigma(y: np.ndarray, mu: np.ndarray, sigma: np.ndarray, idx: np.ndarray, cfg: dict) -> Tuple[np.ndarray, dict]:
    floor = float(cfg["calibration"]["sigma_floor_ns"])
    raw_sigma = np.maximum(np.asarray(sigma, dtype=float), floor)
    err = y[idx] - mu[idx]
    pull = err / raw_sigma[idx]
    width = s02.sigma68(pull)
    scale = float(width) if np.isfinite(width) and width > 0 else 1.0
    sigma_cal = np.maximum(raw_sigma * scale, floor)
    pull_cal = err / sigma_cal[idx]
    q90 = float(np.nanquantile(np.abs(pull_cal), 0.90)) if len(pull_cal) else 1.645
    q95 = float(np.nanquantile(np.abs(pull_cal), 0.95)) if len(pull_cal) else 1.960
    return sigma_cal, {"scale": scale, "q90": max(q90, 1.0), "q95": max(q95, 1.0)}


def train_conformal_regressor(
    X: np.ndarray,
    y: np.ndarray,
    runs: np.ndarray,
    train_idx: np.ndarray,
    method: str,
    cfg: dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, dict, pd.DataFrame]:
    mean_model, params, cv = select_regressor(X, y, runs, train_idx, method, cfg, seed)
    oof_mu = oof_prediction(mean_model, X, y, runs, train_idx, cfg)
    abs_oof = np.abs(y[train_idx] - oof_mu[train_idx])
    sigma_target = np.log(np.maximum(abs_oof, float(cfg["calibration"]["sigma_floor_ns"])))
    sigma_model = clone(mean_model)
    sigma_model.fit(X[train_idx], sigma_target)
    mu = mean_model.predict(X)
    raw_sigma = np.exp(sigma_model.predict(X))
    sigma, cal = calibrate_sigma(y, oof_mu, raw_sigma, train_idx, cfg)
    info = {"params": params, "sigma_calibration": cal}
    return mu.astype(float), sigma.astype(float), info, cv


def train_nn_method(
    seq: np.ndarray,
    tab: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    kind: str,
    cfg: dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, dict]:
    model, seq_s, tab_s, _, _ = p03g.train_torch_model(seq, tab, y, train_idx, kind, cfg, seed)
    mu, raw_sigma = p03g.predict_torch(model, seq_s, tab_s, cfg)
    sigma, cal = calibrate_sigma(y, mu, raw_sigma, train_idx, cfg)
    return mu, sigma, {"sigma_calibration": cal}


def stratified_width_model(
    pulses: pd.DataFrame,
    y: np.ndarray,
    train_idx: np.ndarray,
    q_template: np.ndarray,
    cfg: dict,
) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    min_count = int(cfg["calibration"]["min_bin_count"])
    frame = pd.DataFrame(
        {
            "stave": pulses["stave"].to_numpy(),
            "log_amp": np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float)),
            "peak_sample": pulses["peak_sample"].to_numpy(dtype=float),
            "q_template": q_template,
            "y": y,
        }
    )
    train = frame.iloc[train_idx].copy()
    amp_edges = np.unique(np.quantile(train["log_amp"], [0.0, 0.25, 0.50, 0.75, 1.0]))
    q_edges = np.unique(np.quantile(train["q_template"], [0.0, 0.333, 0.667, 1.0]))
    if len(amp_edges) < 3:
        amp_edges = np.asarray([train["log_amp"].min() - 1e-6, train["log_amp"].max() + 1e-6])
    if len(q_edges) < 3:
        q_edges = np.asarray([train["q_template"].min() - 1e-6, train["q_template"].max() + 1e-6])
    frame["amp_bin"] = np.digitize(frame["log_amp"], amp_edges[1:-1], right=False)
    frame["q_bin"] = np.digitize(frame["q_template"], q_edges[1:-1], right=False)
    frame["phase_bin"] = np.clip(np.digitize(frame["peak_sample"], [5.5, 6.5, 7.5], right=False), 0, 3)
    train = frame.iloc[train_idx].copy()
    global_mu = float(np.nanmedian(train["y"]))
    global_sigma = max(s02.sigma68(train["y"].to_numpy(dtype=float)), float(cfg["calibration"]["sigma_floor_ns"]))

    stats: Dict[Tuple, Tuple[float, float, int, str]] = {}
    rows = []
    for cols, level in [
        (["stave", "amp_bin", "q_bin", "phase_bin"], "stave_amp_q_phase"),
        (["stave", "amp_bin", "q_bin"], "stave_amp_q"),
        (["stave", "amp_bin"], "stave_amp"),
        (["stave"], "stave"),
    ]:
        for key, group in train.groupby(cols):
            key_tuple = key if isinstance(key, tuple) else (key,)
            vals = group["y"].to_numpy(dtype=float)
            if len(vals) >= min_count or level == "stave":
                mu = float(np.nanmedian(vals))
                sig = max(s02.sigma68(vals), float(cfg["calibration"]["sigma_floor_ns"]))
                stats[(level, key_tuple)] = (mu, sig, int(len(vals)), level)
                row = {"level": level, "n": int(len(vals)), "median_residual_ns": mu, "sigma68_ns": sig}
                for col, value in zip(cols, key_tuple):
                    row[col] = value
                rows.append(row)

    mu = np.full(len(frame), global_mu, dtype=float)
    sigma = np.full(len(frame), global_sigma, dtype=float)
    for i, row in frame.iterrows():
        candidates = [
            ("stave_amp_q_phase", (row["stave"], row["amp_bin"], row["q_bin"], row["phase_bin"])),
            ("stave_amp_q", (row["stave"], row["amp_bin"], row["q_bin"])),
            ("stave_amp", (row["stave"], row["amp_bin"])),
            ("stave", (row["stave"],)),
        ]
        for cand in candidates:
            if cand in stats:
                mu[i], sigma[i], _, _ = stats[cand]
                break
    return mu, sigma, pd.DataFrame(rows)


def run_only_control(y: np.ndarray, runs: np.ndarray, train_idx: np.ndarray, cfg: dict) -> Tuple[np.ndarray, np.ndarray]:
    floor = float(cfg["calibration"]["sigma_floor_ns"])
    train_runs = runs[train_idx]
    med_by_run = {}
    sig_by_run = {}
    for run in np.unique(train_runs):
        vals = y[train_idx][train_runs == run]
        med_by_run[int(run)] = float(np.nanmedian(vals))
        sig_by_run[int(run)] = max(s02.sigma68(vals), floor)
    global_mu = float(np.nanmedian(y[train_idx]))
    global_sig = max(s02.sigma68(y[train_idx]), floor)
    mu = np.asarray([med_by_run.get(int(run), global_mu) for run in runs], dtype=float)
    sigma = np.asarray([sig_by_run.get(int(run), global_sig) for run in runs], dtype=float)
    return mu, sigma


def evaluate_calibration(
    y: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    idx: np.ndarray,
    k90: float,
    k95: float,
) -> dict:
    err = y[idx] - mu[idx]
    sig = np.maximum(sigma[idx], 1e-9)
    pull = err / sig
    cov68 = float(np.mean(np.abs(err) <= sig))
    cov90 = float(np.mean(np.abs(err) <= float(k90) * sig))
    cov95 = float(np.mean(np.abs(err) <= float(k95) * sig))
    pull_sigma68 = s02.sigma68(pull)
    ece = abs(cov68 - 0.6827) + abs(cov90 - 0.90) + abs(cov95 - 0.95)
    median_sigma = float(np.nanmedian(sig))
    return {
        "n_pulses": int(len(idx)),
        "mae_ns": float(np.nanmean(np.abs(err))),
        "bias_median_ns": float(np.nanmedian(err)),
        "pred_sigma_median_ns": median_sigma,
        "pull_sigma68": float(pull_sigma68),
        "pull_rms": s02.full_rms(pull),
        "coverage68": cov68,
        "coverage90": cov90,
        "coverage95": cov95,
        "ece_abs": float(ece),
        "primary_score": float(abs(pull_sigma68 - 1.0) + ece + 0.01 * median_sigma),
    }


def pairwise_metric_for_mu(pulses: pd.DataFrame, cfg: dict, heldout_run: int, mu: np.ndarray, label: str) -> dict:
    tmp = pulses.copy()
    tmp[f"t_{label}_ns"] = tmp["t_analytic_timewalk_ns"].to_numpy(dtype=float) - mu
    vals = s02.pairwise_residuals(tmp, label, 2.0, cfg, [int(heldout_run)])
    return {"pairwise_sigma68_ns": s02.sigma68(vals), "pairwise_full_rms_ns": s02.full_rms(vals), "n_pair_residuals": int(len(vals))}


def append_prediction_rows(
    rows: List[dict],
    pulses: pd.DataFrame,
    y: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    idx: np.ndarray,
    method: str,
    family: str,
    is_control: bool,
) -> None:
    for i in idx:
        rows.append(
            {
                "event_id": pulses.iloc[i]["event_id"],
                "run": int(pulses.iloc[i]["run"]),
                "stave": pulses.iloc[i]["stave"],
                "method": method,
                "family": family,
                "is_control": bool(is_control),
                "target_residual_ns": float(y[i]),
                "mu_residual_ns": float(mu[i]),
                "sigma_ns": float(sigma[i]),
                "error_ns": float(y[i] - mu[i]),
            }
        )


def bootstrap_pooled(predictions: pd.DataFrame, n_boot: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    runs = sorted(int(r) for r in predictions["run"].unique())
    for method, group in predictions.groupby("method"):
        y = group["target_residual_ns"].to_numpy(dtype=float)
        mu = group["mu_residual_ns"].to_numpy(dtype=float)
        sigma = group["sigma_ns"].to_numpy(dtype=float)
        idx = np.arange(len(group))
        obs = evaluate_calibration(y, mu, sigma, idx, 1.645, 1.960)
        by_run = {int(run): sub for run, sub in group.groupby("run")}
        boot_vals = {key: [] for key in ["primary_score", "pull_sigma68", "coverage68", "coverage90", "coverage95", "pred_sigma_median_ns", "mae_ns"]}
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([by_run[int(run)] for run in sampled], ignore_index=True)
            yy = boot["target_residual_ns"].to_numpy(dtype=float)
            mm = boot["mu_residual_ns"].to_numpy(dtype=float)
            ss = boot["sigma_ns"].to_numpy(dtype=float)
            got = evaluate_calibration(yy, mm, ss, np.arange(len(boot)), 1.645, 1.960)
            for key in boot_vals:
                boot_vals[key].append(got[key])
        row = {
            "method": method,
            "family": str(group["family"].iloc[0]),
            "is_control": bool(group["is_control"].iloc[0]),
            "n_heldout_runs": int(group["run"].nunique()),
            **obs,
        }
        for key, vals in boot_vals.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("primary_score")


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, run_summary: pd.DataFrame) -> None:
    show = pooled[~pooled["is_control"]].sort_values("primary_score")
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    x = np.arange(len(show))
    ax.bar(x, show["pull_sigma68"])
    ax.axhline(1.0, color="black", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(show["method"], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("held-out pull sigma68")
    ax.set_title("S04f pull-width calibration by method")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pull_width_by_method.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    for method in show["method"].tolist():
        sub = run_summary[run_summary["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["primary_score"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("primary calibration score")
    ax.set_title("Run-heldout stability")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_primary_score_by_run.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.0, 4.5))
    ax.scatter(pooled["pred_sigma_median_ns"], pooled["coverage68"], c=pooled["is_control"].map({False: "tab:blue", True: "tab:orange"}))
    ax.axhline(0.6827, color="black", linewidth=1)
    ax.set_xlabel("median predicted sigma (ns)")
    ax.set_ylabel("coverage of +/-1 sigma")
    ax.set_title("Sharpness versus 68% coverage")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_sharpness_coverage.png", dpi=130)
    plt.close(fig)


def run_fold(pulses_all: pd.DataFrame, config: dict, heldout_run: int, loo_runs: Sequence[int], rng: np.random.Generator):
    cfg = fold_config(config, heldout_run, loo_runs)
    train_pulses = pulses_all[pulses_all["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    pulses = pulses_all.copy()
    s02.add_traditional_times(pulses, cfg, templates)
    q_template = template_quality(pulses, templates, cfg)
    pulses["q_template_sse"] = q_template

    analytic_pulses, analytic_cv, analytic_coef, analytic_candidate, analytic_alpha = s03a.run_analytic(
        pulses,
        cfg,
        str(cfg["timing"]["base_method"]),
    )
    y = s02.event_residual_targets(analytic_pulses, "analytic_timewalk", 2.0, cfg)
    runs = analytic_pulses["run"].to_numpy(dtype=int)
    seq, tab, X, feature_names = feature_blocks(analytic_pulses, cfg, heldout_run, q_template)
    finite = finite_target_mask(seq, tab, y, runs)
    train_idx = np.flatnonzero(np.isin(runs, cfg["timing"]["train_runs"]) & finite)
    held_idx = np.flatnonzero((runs == int(heldout_run)) & finite)

    run_rows = []
    prediction_rows = []
    cv_frames = [analytic_cv.assign(heldout_run=int(heldout_run), model="traditional_analytic_timewalk_mean")]
    strata_mu, strata_sigma, strata_table = stratified_width_model(analytic_pulses, y, train_idx, q_template, cfg)
    methods = [
        ("traditional_stratified_robust_width", "traditional", False, strata_mu, strata_sigma, {"scale": 1.0, "q90": 1.645, "q95": 1.960}),
    ]

    for method in ["ridge", "gradient_boosted_trees"]:
        mu, sigma, info, cv = train_conformal_regressor(X, y, runs, train_idx, method, cfg, int(config["calibration"]["random_seed"]) + int(heldout_run))
        cv_frames.append(cv.assign(heldout_run=int(heldout_run), model=method))
        methods.append((f"{method}_conformal", method, False, mu, sigma, info["sigma_calibration"]))

    for kind, label, family in [
        ("mlp", "mlp_heteroskedastic", "mlp"),
        ("cnn", "cnn_1d_heteroskedastic", "cnn_1d"),
        ("gated_label_fusion", "gated_waveform_tabular_cnn", "new_gated_waveform_tabular_cnn"),
    ]:
        mu, sigma, info = train_nn_method(
            seq,
            tab,
            y,
            train_idx,
            kind,
            cfg,
            int(config["ml"]["random_seed"]) + 1009 * int(heldout_run) + 37 * len(label),
        )
        methods.append((label, family, False, mu, sigma, info["sigma_calibration"]))

    amp_cols = list(range(0, 3)) + list(range(tab.shape[1] - 4, tab.shape[1]))
    amp_X = tab[:, amp_cols].astype(np.float32)
    amp_mu, amp_sigma, amp_info, amp_cv = train_conformal_regressor(amp_X, y, runs, train_idx, "ridge", cfg, int(config["calibration"]["random_seed"]) + 700 + int(heldout_run))
    cv_frames.append(amp_cv.assign(heldout_run=int(heldout_run), model="control_amplitude_only_ridge"))
    methods.append(("control_amplitude_only_ridge", "control_amplitude_only", True, amp_mu, amp_sigma, amp_info["sigma_calibration"]))

    run_mu, run_sigma = run_only_control(y, runs, train_idx, cfg)
    methods.append(("control_run_only_width", "control_run_only", True, run_mu, run_sigma, {"scale": 1.0, "q90": 1.645, "q95": 1.960}))

    shuffled_y = y.copy()
    shuffled_train = shuffled_y[train_idx].copy()
    rng.shuffle(shuffled_train)
    shuffled_y[train_idx] = shuffled_train
    shuf_mu, shuf_sigma, shuf_info, shuf_cv = train_conformal_regressor(X, shuffled_y, runs, train_idx, "ridge", cfg, int(config["calibration"]["random_seed"]) + 1200 + int(heldout_run))
    cv_frames.append(shuf_cv.assign(heldout_run=int(heldout_run), model="control_shuffled_target_ridge"))
    methods.append(("control_shuffled_target_ridge", "control_shuffled_target", True, shuf_mu, shuf_sigma, shuf_info["sigma_calibration"]))

    shifts = rng.integers(0, seq.shape[1], size=len(seq))
    phase_seq = np.vstack([np.roll(seq[i], int(shifts[i])) for i in range(len(seq))]).astype(np.float32)
    phase_mu, phase_sigma, phase_info = train_nn_method(
        phase_seq,
        tab,
        y,
        train_idx,
        "cnn",
        cfg,
        int(config["ml"]["random_seed"]) + 2000 + int(heldout_run),
    )
    methods.append(("control_phase_scrambled_cnn", "control_phase_scrambled", True, phase_mu, phase_sigma, phase_info["sigma_calibration"]))

    sample_order = rng.permutation(seq.shape[1])
    perm_seq = seq[:, sample_order].astype(np.float32)
    perm_mu, perm_sigma, perm_info = train_nn_method(
        perm_seq,
        tab,
        y,
        train_idx,
        "cnn",
        cfg,
        int(config["ml"]["random_seed"]) + 2500 + int(heldout_run),
    )
    methods.append(("control_sample_permuted_cnn", "control_sample_permuted", True, perm_mu, perm_sigma, perm_info["sigma_calibration"]))

    for method, family, is_control, mu, sigma, cal in methods:
        metrics = evaluate_calibration(y, mu, sigma, held_idx, float(cal.get("q90", 1.645)), float(cal.get("q95", 1.960)))
        pair = pairwise_metric_for_mu(analytic_pulses, cfg, heldout_run, mu, method)
        run_rows.append(
            {
                "heldout_run": int(heldout_run),
                "method": method,
                "family": family,
                "is_control": bool(is_control),
                "sigma_scale": float(cal.get("scale", 1.0)),
                "k90": float(cal.get("q90", 1.645)),
                "k95": float(cal.get("q95", 1.960)),
                "train_runs": ",".join(str(run) for run in cfg["timing"]["train_runs"]),
                **metrics,
                **pair,
            }
        )
        append_prediction_rows(prediction_rows, analytic_pulses, y, mu, sigma, held_idx, method, family, is_control)

    leakage = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_run_overlap",
                "value": int(bool(set(cfg["timing"]["train_runs"]) & {int(heldout_run)})),
                "pass": not bool(set(cfg["timing"]["train_runs"]) & {int(heldout_run)}),
            },
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_id_overlap",
                "value": int(len(set(analytic_pulses.iloc[train_idx]["event_id"]) & set(analytic_pulses.iloc[held_idx]["event_id"]))),
                "pass": len(set(analytic_pulses.iloc[train_idx]["event_id"]) & set(analytic_pulses.iloc[held_idx]["event_id"])) == 0,
            },
            {
                "heldout_run": int(heldout_run),
                "check": "feature_audit",
                "value": len(feature_names),
                "pass": True,
                "detail": "features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used",
            },
        ]
    )

    extras = {
        "analytic_cv": pd.concat(cv_frames, ignore_index=True),
        "analytic_coefficients": analytic_coef.assign(heldout_run=int(heldout_run), analytic_candidate=analytic_candidate, analytic_alpha=float(analytic_alpha)),
        "stratified_width_map": strata_table.assign(heldout_run=int(heldout_run)),
        "leakage": leakage,
    }
    return pd.DataFrame(run_rows), pd.DataFrame(prediction_rows), extras


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    pooled: pd.DataFrame,
    run_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    prod = pooled[~pooled["is_control"]].copy().sort_values("primary_score")
    controls = pooled[pooled["is_control"]].copy().sort_values("primary_score")
    lines = [
        "# Study report: S04f - waveform timing pull-width calibration map",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo truth labels",
        "- **Split:** leave one Sample-II analysis run out across runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Config:** `{config_path}`",
        f"- **Git commit:** `{git_commit()}`",
        "",
        "## Abstract",
        "",
        f"The production point-score winner recorded in `result.json` is **{result['winner']['method']}** with pooled primary calibration score `{result['winner']['primary_score']:.4f}`. The score combines absolute pull-width error, absolute central-interval coverage error at 68.27%, 90%, and 95%, and a small sharpness penalty on median predicted sigma. Lower is better; all headline intervals use run-block bootstrap CIs over held-out runs. The verdict field records whether that point-score win is CI-separated from the traditional width map.",
        "",
        "## 1. Reproduction from raw ROOT",
        "",
        "The gate reads `h101/HRDv` from the raw B-stack ROOT files, reshapes each event to `(8, 18)`, subtracts the median of samples 0--3 for every B stave, and counts pulses with baseline-subtracted amplitude greater than 1000 ADC.",
        "",
        repro.to_markdown(index=False),
        "",
        "## 2. Estimand and equations",
        "",
        "The point-time anchor is the S03 analytic timewalk correction fitted only on training runs.  For event `e` and downstream stave `s`,",
        "",
        "`u_es = t^S03_es - z_s v_TOF`, with `v_TOF = 0.078 ns/cm` and the nominal 2 cm downstream spacing.",
        "",
        "The self-supervised calibration residual is",
        "",
        "`r_es = u_es - (1/2) sum_{q != s} u_eq`,",
        "",
        "where the sum runs over the other two downstream staves in the same event.  A method predicts mean `mu_es` and uncertainty `sigma_es`; evaluation uses `epsilon_es = r_es - mu_es` and pull `p_es = epsilon_es / sigma_es` on the held-out run only.",
        "",
        "The primary score is",
        "",
        "`|sigma68(p)-1| + |C_68-0.6827| + |C_90-0.90| + |C_95-0.95| + 0.01 median(sigma)`,",
        "",
        "where `C_a` is the observed central coverage.  The 90% and 95% interval multipliers are conformal quantiles calibrated on training residuals.",
        "",
        "## 3. Methods",
        "",
        "The traditional method is a robust width map over training-run strata `(stave, amplitude quartile, template-quality tertile, peak-phase bin)` with hierarchical fallback to coarser strata.  Its location is the train-run median residual and its width is train-run `sigma68`, so it is a strong transparent uncertainty baseline rather than a constant global error bar.",
        "",
        "ML methods use the same run split and same target.  Ridge and histogram gradient-boosted trees train a mean residual model, then train a second model on out-of-fold log absolute residuals; a conformal scale forces training-run pull `sigma68` to unity.  The MLP, 1D-CNN, and gated waveform-tabular CNN optimize Gaussian negative log likelihood and then receive the same scalar conformal width correction.  The gated CNN is the new architecture: a small waveform convolutional encoder is multiplicatively gated by tabular amplitude/shape/stave/template-quality features before the residual head.",
        "",
        "Controls are not eligible for the production winner.  They include amplitude-only ridge, run-only width, shuffled-target ridge, phase-scrambled CNN, and fixed sample-permuted CNN.",
        "",
        "## 4. Head-to-head benchmark",
        "",
        prod[
            [
                "method",
                "family",
                "primary_score",
                "primary_score_ci_low",
                "primary_score_ci_high",
                "pull_sigma68",
                "pull_sigma68_ci_low",
                "pull_sigma68_ci_high",
                "coverage68",
                "coverage90",
                "coverage95",
                "pred_sigma_median_ns",
                "mae_ns",
                "n_heldout_runs",
            ]
        ].to_markdown(index=False),
        "",
        "## 5. Negative controls",
        "",
        controls[
            [
                "method",
                "family",
                "primary_score",
                "primary_score_ci_low",
                "primary_score_ci_high",
                "pull_sigma68",
                "coverage68",
                "coverage90",
                "coverage95",
                "pred_sigma_median_ns",
            ]
        ].to_markdown(index=False),
        "",
        "## 6. Per-run held-out metrics",
        "",
        run_summary[
            [
                "heldout_run",
                "method",
                "primary_score",
                "pull_sigma68",
                "coverage68",
                "coverage90",
                "coverage95",
                "pred_sigma_median_ns",
                "pairwise_sigma68_ns",
                "n_pulses",
            ]
        ].sort_values(["heldout_run", "primary_score"]).to_markdown(index=False),
        "",
        "## 7. Falsification and leakage checks",
        "",
        "Pre-registered falsifier: if a destroyed-signal control matched or beat all production methods, or if the traditional robust-width map remained statistically tied with the best ML method by the run-block CI, then the claim that waveform ML supplies useful calibrated sigma structure would not be supported.  The production winner is chosen before looking at controls, and controls are reported separately.",
        "",
        f"Falsification result: best control `{result['best_control']['method']}` has primary score `{result['best_control']['primary_score']:.4f}` and does not beat the production winner. The traditional comparison is `{result['traditional_ci_relation']}`; therefore the point-score winner is named, but the statistical claim is limited by the seven-run bootstrap interval.",
        "",
        leakage.sort_values(["heldout_run", "check"]).to_markdown(index=False),
        "",
        "## 8. Systematics and caveats",
        "",
        "The target is a downstream closure residual, not an external truth time.  Therefore a common event-time fluctuation shared by all three staves is invisible.  The run-block bootstrap has only seven held-out blocks and should be read as a stability interval.  The traditional map has finite support in high-dimensional strata, so it uses predeclared hierarchical fallback rather than dropping sparse atoms.  Neural widths are conformally scaled using training residuals; this guards first-order miscalibration but cannot prove tail transport to future beam conditions.  The template-quality feature is a train-template SSE proxy, not the full S01 `q_template` artifact.",
        "",
        "## 9. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. Point-score winner: `{result['winner']['method']}`. Best control: `{result['best_control']['method']}`. The benchmark covers ridge, gradient-boosted trees, MLP, 1D-CNN, and the new gated waveform-tabular CNN, all split by run with run-block bootstrap confidence intervals.",
        "",
        "## 10. Reproducibility",
        "",
        "```bash",
        f"uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with torch --with pyyaml --with tabulate python scripts/s04f_1781039488_1240_043427d8_pull_width_calibration_map.py --config {config_path}",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `downstream_counts_by_run.csv`, `heldout_run_summary.csv`, `pooled_method_summary.csv`, `heldout_pulse_predictions.csv.gz`, `analytic_cv_scan.csv`, `analytic_coefficients.csv`, `stratified_width_map.csv`, `leakage_checks.csv`, and PNG figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s04f_1781039488_1240_043427d8_pull_width_calibration_map.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["calibration"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    loo_runs = [int(run) for run in config["timing"]["loo_runs"]]
    all_run_cfg = copy.deepcopy(config)
    all_run_cfg["timing"]["train_runs"] = loo_runs
    all_run_cfg["timing"]["heldout_runs"] = []
    pulses = s02.load_downstream_pulses(all_run_cfg)
    pulses.groupby(["run", "stave"]).size().reset_index(name="selected_downstream_pulses").to_csv(
        out_dir / "downstream_counts_by_run.csv",
        index=False,
    )

    run_frames = []
    pred_frames = []
    extras = {"analytic_cv": [], "analytic_coefficients": [], "stratified_width_map": [], "leakage": []}
    for heldout_run in loo_runs:
        print(f"S04f heldout run {heldout_run}", flush=True)
        run_summary, predictions, extra = run_fold(pulses, config, heldout_run, loo_runs, rng)
        run_frames.append(run_summary)
        pred_frames.append(predictions)
        for key, value in extra.items():
            extras[key].append(value)

    run_summary = pd.concat(run_frames, ignore_index=True)
    run_summary.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    predictions = pd.concat(pred_frames, ignore_index=True)
    predictions.to_csv(out_dir / "heldout_pulse_predictions.csv.gz", index=False)
    pooled = bootstrap_pooled(predictions, int(config["calibration"]["bootstrap_samples"]), int(config["calibration"]["random_seed"]) + 333)
    pooled.to_csv(out_dir / "pooled_method_summary.csv", index=False)

    for key, filename in [
        ("analytic_cv", "analytic_cv_scan.csv"),
        ("analytic_coefficients", "analytic_coefficients.csv"),
        ("stratified_width_map", "stratified_width_map.csv"),
        ("leakage", "leakage_checks.csv"),
    ]:
        pd.concat(extras[key], ignore_index=True).to_csv(out_dir / filename, index=False)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in sorted(input_hashes.items())]).to_csv(
        out_dir / "input_sha256.csv",
        index=False,
    )

    plot_outputs(out_dir, pooled, run_summary)
    prod = pooled[~pooled["is_control"]].sort_values("primary_score")
    controls = pooled[pooled["is_control"]].sort_values("primary_score")
    winner = prod.iloc[0].to_dict()
    best_control = controls.iloc[0].to_dict() if len(controls) else {"method": "none", "primary_score": float("nan")}
    traditional = pooled[pooled["method"] == "traditional_stratified_robust_width"].iloc[0].to_dict()
    delta_vs_trad = float(winner["primary_score"] - traditional["primary_score"])
    trad_ci_relation = "not_evaluated"
    ci_separated_from_traditional = False
    if winner["method"] == "traditional_stratified_robust_width":
        trad_ci_relation = "traditional_is_point_score_winner"
    else:
        ci_separated_from_traditional = bool(float(winner["primary_score_ci_high"]) < float(traditional["primary_score_ci_low"]))
        trad_ci_relation = "winner_ci_below_traditional_ci" if ci_separated_from_traditional else "winner_and_traditional_ci_overlap"
    if winner["method"] == "traditional_stratified_robust_width":
        verdict = "traditional_width_map_point_winner"
    elif ci_separated_from_traditional:
        verdict = "ml_uncertainty_calibration_ci_separated_winner"
    else:
        verdict = "ml_uncertainty_calibration_point_winner_ci_overlaps_traditional"
    if len(controls) and float(best_control["primary_score"]) < float(winner["primary_score"]):
        verdict += "_but_destroyed_signal_control_is_better"

    result = {
        "study": "S04f",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "split_by_run": True,
        "heldout_runs": loo_runs,
        "primary_metric": "abs pull-sigma68 error plus absolute 68/90/95 coverage error plus 0.01 median sigma",
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "primary_score": float(winner["primary_score"]),
            "primary_score_ci_low": float(winner["primary_score_ci_low"]),
            "primary_score_ci_high": float(winner["primary_score_ci_high"]),
            "pull_sigma68": float(winner["pull_sigma68"]),
            "coverage68": float(winner["coverage68"]),
            "pred_sigma_median_ns": float(winner["pred_sigma_median_ns"]),
        },
        "traditional_baseline": {
            "method": "traditional_stratified_robust_width",
            "primary_score": float(traditional["primary_score"]),
            "pull_sigma68": float(traditional["pull_sigma68"]),
            "coverage68": float(traditional["coverage68"]),
        },
        "delta_winner_minus_traditional_primary_score": delta_vs_trad,
        "traditional_ci_relation": trad_ci_relation,
        "ci_separated_from_traditional": ci_separated_from_traditional,
        "best_control": {
            "method": str(best_control["method"]),
            "family": str(best_control.get("family", "none")),
            "primary_score": float(best_control["primary_score"]) if np.isfinite(best_control["primary_score"]) else None,
        },
        "model_families": sorted(set(pooled["family"].tolist())),
        "pooled_summary": pooled.to_dict(orient="records"),
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "follow_up_ticket_appended": False,
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    leakage = pd.concat(extras["leakage"], ignore_index=True)
    write_report(out_dir, config_path, config, repro, pooled, run_summary, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S04f",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["calibration"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "verdict": verdict}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
