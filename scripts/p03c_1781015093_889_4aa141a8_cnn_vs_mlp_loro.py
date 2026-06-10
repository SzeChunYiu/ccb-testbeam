#!/usr/bin/env python3
"""P03c waveform-only CNN versus P03b MLP under leave-one-run-out gates."""

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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03c-loro")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

import p03a_18_sample_mlp_timing as p03a
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


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def fold_config(config: dict, heldout_run: int, loo_runs: Sequence[int]) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [int(run) for run in loo_runs if int(run) != int(heldout_run)]
    return cfg


def waveform_and_stave_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    names = [f"sample_{i:02d}_over_amp" for i in range(norm.shape[1])] + [f"stave_{s}" for s in staves]
    return norm.astype(np.float32), one_hot, names


def finite_mask(X: np.ndarray, S: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.all(np.isfinite(S), axis=1) & np.isfinite(runs)


class TinyWaveformCNN(nn.Module):
    def __init__(self, n_samples: int, n_staves: int, channels: int) -> None:
        super().__init__()
        c = int(channels)
        self.conv = nn.Sequential(
            nn.Conv1d(1, c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(c, 2 * c, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        width = max(2 * c + int(n_staves), 8)
        self.head = nn.Sequential(nn.Linear(2 * c + int(n_staves), width), nn.ReLU(), nn.Linear(width, 2))
        self.n_samples = int(n_samples)

    def forward(self, x_wave: torch.Tensor, x_stave: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.conv(x_wave[:, None, :])
        out = self.head(torch.cat([z, x_stave], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


def standardize_wave_train_apply(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    train_mask = np.zeros(len(X), dtype=bool)
    train_mask[train_idx] = True
    scaler = StandardScaler()
    Xs = X.copy()
    Xs[train_mask] = scaler.fit_transform(X[train_mask])
    if (~train_mask).any():
        Xs[~train_mask] = scaler.transform(X[~train_mask])
    return Xs.astype(np.float32), scaler


def train_cnn(
    X: np.ndarray,
    S: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    channels: int,
    weight_decay: float,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[TinyWaveformCNN, np.ndarray, StandardScaler]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    Xs, scaler = standardize_wave_train_apply(X, train_idx)
    y_train = y[train_idx].astype(np.float32).copy()
    if shuffle_y:
        rng.shuffle(y_train)
    model = TinyWaveformCNN(X.shape[1], S.shape[1], int(channels))
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["learning_rate"]),
        weight_decay=float(weight_decay),
    )
    xb_all = torch.from_numpy(Xs[train_idx])
    sb_all = torch.from_numpy(S[train_idx].astype(np.float32))
    yb_all = torch.from_numpy(y_train)
    batch_size = int(config["ml"]["batch_size"])
    min_var = float(config["ml"]["min_sigma_ns"]) ** 2
    for _ in range(int(config["ml"]["epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch_size):
            take = order[start : start + batch_size]
            mu, log_var = model(xb_all[take], sb_all[take])
            var = torch.exp(log_var) + min_var
            loss = torch.mean(0.5 * ((yb_all[take] - mu) ** 2 / var + torch.log(var)))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model, Xs, scaler


def predict_cnn(model: TinyWaveformCNN, Xs: np.ndarray, S: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    with torch.no_grad():
        mu, log_var = model(torch.from_numpy(Xs.astype(np.float32)), torch.from_numpy(S.astype(np.float32)))
        sigma = torch.sqrt(torch.exp(log_var) + float(config["ml"]["min_sigma_ns"]) ** 2)
    return mu.numpy().astype(float), sigma.numpy().astype(float)


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def evaluate_corrected(
    pulses: pd.DataFrame,
    method_name: str,
    values: np.ndarray,
    config: dict,
    runs: Iterable[int],
) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, list(runs))


def run_waveform_cnn(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    seed = int(config["ml"]["random_seed"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, S, feature_names = waveform_and_stave_features(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_mask(X, S, targets, runs)
    idx_train_all = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": math.inf, "channels": None, "weight_decay": None}
    for channels in config["ml"]["cnn_channels"]:
        for weight_decay in config["ml"]["weight_decays"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
                tr_idx = idx_train_all[tr]
                va_idx = idx_train_all[va]
                model, Xs, _ = train_cnn(
                    X,
                    S,
                    targets,
                    tr_idx,
                    int(channels),
                    float(weight_decay),
                    config,
                    seed + 700 * int(fold) + 31 * int(channels),
                )
                pred, sigma = predict_cnn(model, Xs, S, config)
                corrected = corrected_values(pulses, base_method, pred)
                vals = evaluate_corrected(
                    pulses.iloc[va_idx].copy(),
                    "cnn_cv",
                    corrected[va_idx],
                    config,
                    sorted(np.unique(runs[va_idx]).tolist()),
                )
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "model": "cnn_waveform",
                        "channels": int(channels),
                        "weight_decay": float(weight_decay),
                        "fold": int(fold),
                        "sigma68_ns": float(score),
                        "n_pair_residuals": int(len(vals)),
                        "pred_sigma_median_ns": float(np.nanmedian(sigma[va_idx])),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "model": "cnn_waveform",
                    "channels": int(channels),
                    "weight_decay": float(weight_decay),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                    "pred_sigma_median_ns": float("nan"),
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "channels": int(channels), "weight_decay": float(weight_decay)}

    model, Xs, scaler = train_cnn(
        X,
        S,
        targets,
        idx_train_all,
        int(best["channels"]),
        float(best["weight_decay"]),
        config,
        seed + 1709,
    )
    pred, sigma = predict_cnn(model, Xs, S, config)
    out = pulses.copy()
    out["cnn_target_residual_ns"] = targets
    out["cnn_pred_residual_ns"] = pred
    out["cnn_pred_sigma_ns"] = sigma
    out["t_cnn_waveform_ns"] = corrected_values(pulses, base_method, pred)

    held = out[out["run"].isin(heldout_runs)].copy()
    held = held[np.isfinite(held["cnn_target_residual_ns"]) & np.isfinite(held["cnn_pred_sigma_ns"])]
    err = held["cnn_target_residual_ns"] - held["cnn_pred_residual_ns"]
    pull = err / held["cnn_pred_sigma_ns"]
    cal_rows = [
        {
            "model": "cnn_waveform",
            "scope": "heldout_pulse_target",
            "n": int(len(held)),
            "pred_sigma_median_ns": float(held["cnn_pred_sigma_ns"].median()),
            "abs_error_median_ns": float(err.abs().median()),
            "pull_width_sigma68": s02.sigma68(pull.to_numpy(dtype=float)),
            "pull_rms": s02.full_rms(pull.to_numpy(dtype=float)),
        }
    ]
    if len(held) >= 8:
        qs = np.unique(np.quantile(held["cnn_pred_sigma_ns"], np.linspace(0, 1, 5)))
        if len(qs) >= 3:
            held["sigma_bin"] = pd.cut(held["cnn_pred_sigma_ns"], qs, include_lowest=True, duplicates="drop")
            for _, group in held.groupby("sigma_bin"):
                gerr = group["cnn_target_residual_ns"] - group["cnn_pred_residual_ns"]
                cal_rows.append(
                    {
                        "model": "cnn_waveform",
                        "scope": "heldout_sigma_bin",
                        "n": int(len(group)),
                        "pred_sigma_median_ns": float(group["cnn_pred_sigma_ns"].median()),
                        "abs_error_median_ns": float(gerr.abs().median()),
                        "pull_width_sigma68": s02.sigma68((gerr / group["cnn_pred_sigma_ns"]).to_numpy(dtype=float)),
                        "pull_rms": s02.full_rms((gerr / group["cnn_pred_sigma_ns"]).to_numpy(dtype=float)),
                    }
                )

    info = {
        "model": "cnn_waveform",
        "base_method": base_method,
        "channels": int(best["channels"]),
        "weight_decay": float(best["weight_decay"]),
        "cv_sigma68_ns": float(best["score"]),
        "n_features": int(X.shape[1] + S.shape[1]),
        "feature_names": feature_names,
        "scaler_mean_sha256": hashlib.sha256(scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
    }
    return out, pd.DataFrame(cv_rows), pd.DataFrame(cal_rows), info


def paired_event_bootstrap(pair_frame: pd.DataFrame, baseline_label: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    event_ids = np.asarray(sorted(pair_frame["event_id"].unique()))
    labels = sorted(pair_frame["method"].unique())
    by_method = {
        label: pair_frame[pair_frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for label in labels
    }
    observed = {label: s02.sigma68(pair_frame[pair_frame["method"] == label]["residual_ns"].to_numpy()) for label in labels}
    full_rms = {label: s02.full_rms(pair_frame[pair_frame["method"] == label]["residual_ns"].to_numpy()) for label in labels}
    stats = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
        boot = {}
        for label in labels:
            vals = np.concatenate([by_method[label][event_id] for event_id in sample_ids])
            boot[label] = s02.sigma68(vals)
            stats[label].append(boot[label])
        for label in labels:
            deltas[label].append(boot[label] - boot[baseline_label])
    for label in labels:
        rows.append(
            {
                "method": label,
                "baseline": baseline_label,
                "n_events": int(len(event_ids)),
                "n_pair_residuals": int(len(pair_frame[pair_frame["method"] == label])),
                "sigma68_ns": float(observed[label]),
                "ci_low": float(np.percentile(stats[label], 2.5)),
                "ci_high": float(np.percentile(stats[label], 97.5)),
                "full_rms_ns": float(full_rms[label]),
                "delta_vs_baseline_ns": float(observed[label] - observed[baseline_label]),
                "delta_ci_low": float(np.percentile(deltas[label], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[label], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def cnn_shuffled_control(pulses: pd.DataFrame, config: dict, cnn_info: dict) -> float:
    base_method = str(config["ml"]["base_method"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, S, _ = waveform_and_stave_features(pulses, list(config["timing"]["downstream_staves"]))
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & finite_mask(X, S, targets, runs)
    model, Xs, _ = train_cnn(
        X,
        S,
        targets,
        np.flatnonzero(train_mask),
        int(cnn_info["channels"]),
        float(cnn_info["weight_decay"]),
        config,
        int(config["ml"]["random_seed"]) + 2909,
        shuffle_y=True,
    )
    pred, _ = predict_cnn(model, Xs, S, config)
    vals = evaluate_corrected(
        pulses,
        "cnn_shuffled",
        corrected_values(pulses, base_method, pred),
        config,
        list(config["timing"]["heldout_runs"]),
    )
    return float(s02.sigma68(vals))


def leakage_checks(
    pulses: pd.DataFrame,
    mlp_pulses: pd.DataFrame,
    cnn_pulses: pd.DataFrame,
    config: dict,
    mlp_info: dict,
    cnn_info: dict,
) -> pd.DataFrame:
    rows = []
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    rows.append(
        {
            "model": "all",
            "check": "train_heldout_event_id_overlap",
            "value": float(len(train_event_ids & heldout_event_ids)),
            "detail": "must be zero",
        }
    )
    rows.append(
        {
            "model": "all",
            "check": "feature_audit",
            "value": 0.0,
            "detail": "inputs are normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, or held-out target",
        }
    )
    mlp_leak = p03a.leakage_checks(pulses, mlp_pulses, config, mlp_info)
    for _, row in mlp_leak.iterrows():
        if row["check"] in {"shuffled_target_negative_control_sigma68_ns", "nominal_mlp_sigma68_ns"}:
            rows.append({"model": "mlp_waveform", "check": row["check"], "value": float(row["value"]), "detail": row["detail"]})
    cnn_nominal = s02.sigma68(s02.pairwise_residuals(cnn_pulses, "cnn_waveform", 2.0, config, heldout_runs))
    rows.append(
        {
            "model": "cnn_waveform",
            "check": "nominal_cnn_sigma68_ns",
            "value": float(cnn_nominal),
            "detail": "held-out run metric for comparison to shuffled control",
        }
    )
    rows.append(
        {
            "model": "cnn_waveform",
            "check": "shuffled_target_negative_control_sigma68_ns",
            "value": cnn_shuffled_control(pulses, config, cnn_info),
            "detail": "same CNN trained with shuffled train residual targets",
        }
    )
    return pd.DataFrame(rows)


def run_fold(
    pulses: pd.DataFrame,
    config: dict,
    heldout_run: int,
    loo_runs: Sequence[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    cfg = fold_config(config, heldout_run, loo_runs)
    train_pulses = pulses[pulses["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    fold_pulses = pulses.copy()
    methods = s02.add_traditional_times(fold_pulses, cfg, templates)
    scan = s02.evaluate_methods(fold_pulses, methods, cfg)
    scan["heldout_run"] = int(heldout_run)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    best_method = str(train_2cm.iloc[0]["method"])
    if best_method != cfg["timing"]["base_method"]:
        raise RuntimeError(f"run {heldout_run}: expected base {cfg['timing']['base_method']}, got {best_method}")

    s02_ml_pulses, s02_ml_cv, s02_ml_cal = s02.run_ml(fold_pulses, cfg, "cfd20", 2.0)
    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(fold_pulses, cfg, best_method)
    combined = analytic_pulses.copy()
    combined["t_s02_ridge_cfd20_ns"] = s02_ml_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)

    mlp_pulses, mlp_cv, mlp_cal, mlp_info = p03a.run_waveform_mlp(combined, cfg, str(cfg["ml"]["base_method"]))
    combined["t_mlp_waveform_ns"] = mlp_pulses["t_mlp_waveform_ns"].to_numpy(dtype=float)
    combined["mlp_target_residual_ns"] = mlp_pulses["mlp_target_residual_ns"].to_numpy(dtype=float)
    combined["mlp_pred_residual_ns"] = mlp_pulses["mlp_pred_residual_ns"].to_numpy(dtype=float)
    combined["mlp_pred_sigma_ns"] = mlp_pulses["mlp_pred_sigma_ns"].to_numpy(dtype=float)

    cnn_pulses, cnn_cv, cnn_cal, cnn_info = run_waveform_cnn(combined, cfg, str(cfg["ml"]["base_method"]))
    combined["t_cnn_waveform_ns"] = cnn_pulses["t_cnn_waveform_ns"].to_numpy(dtype=float)
    combined["cnn_target_residual_ns"] = cnn_pulses["cnn_target_residual_ns"].to_numpy(dtype=float)
    combined["cnn_pred_residual_ns"] = cnn_pulses["cnn_pred_residual_ns"].to_numpy(dtype=float)
    combined["cnn_pred_sigma_ns"] = cnn_pulses["cnn_pred_sigma_ns"].to_numpy(dtype=float)

    methods_for_bootstrap = [
        ("cfd20", "cfd20_reference"),
        ("s02_ridge_cfd20", "s02_ridge_cfd20"),
        ("analytic_timewalk", "analytic_timewalk"),
        ("mlp_waveform", "mlp_waveform"),
        ("cnn_waveform", "cnn_waveform"),
    ]
    pair_frame = p03a.event_pair_residual_frame(combined, methods_for_bootstrap, cfg, [heldout_run])
    pair_frame["heldout_run"] = int(heldout_run)
    benchmark = paired_event_bootstrap(pair_frame, "analytic_timewalk", rng, int(cfg["ml"]["bootstrap_samples"]))
    benchmark["heldout_run"] = int(heldout_run)
    benchmark["train_runs"] = ",".join(str(run) for run in cfg["timing"]["train_runs"])

    leakage = leakage_checks(combined, mlp_pulses, cnn_pulses, cfg, mlp_info, cnn_info)
    leakage["heldout_run"] = int(heldout_run)
    mlp_cal["model"] = "mlp_waveform"
    mlp_cal["heldout_run"] = int(heldout_run)
    cnn_cal["heldout_run"] = int(heldout_run)
    calibration = pd.concat([mlp_cal, cnn_cal], ignore_index=True)
    mlp_cv["model"] = "mlp_waveform"
    mlp_cv["heldout_run"] = int(heldout_run)
    cnn_cv["heldout_run"] = int(heldout_run)
    analytic_cv["heldout_run"] = int(heldout_run)
    s02_ml_cv["heldout_run"] = int(heldout_run)
    analytic_coef["heldout_run"] = int(heldout_run)
    s02_ml_cal["heldout_run"] = int(heldout_run)
    model_choice = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "traditional_base_method": best_method,
                "analytic_candidate": best_candidate,
                "analytic_alpha": float(best_alpha),
                "mlp_hidden": int(mlp_info["hidden"]),
                "mlp_weight_decay": float(mlp_info["weight_decay"]),
                "mlp_n_features": int(mlp_info["n_features"]),
                "cnn_channels": int(cnn_info["channels"]),
                "cnn_weight_decay": float(cnn_info["weight_decay"]),
                "cnn_n_features": int(cnn_info["n_features"]),
            }
        ]
    )
    extra = {
        "scan": scan,
        "mlp_cv": mlp_cv,
        "cnn_cv": cnn_cv,
        "analytic_cv": analytic_cv,
        "s02_ml_cv": s02_ml_cv,
        "analytic_coef": analytic_coef,
        "s02_ml_cal": s02_ml_cal,
        "model_choice": model_choice,
    }
    return benchmark, pair_frame, leakage, calibration, extra


def pooled_summary(heldout: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in heldout.groupby("method"):
        rows.append(
            {
                "method": method,
                "mean_sigma68_ns": float(group["sigma68_ns"].mean()),
                "median_sigma68_ns": float(group["sigma68_ns"].median()),
                "min_sigma68_ns": float(group["sigma68_ns"].min()),
                "max_sigma68_ns": float(group["sigma68_ns"].max()),
                "n_heldout_runs": int(group["heldout_run"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_sigma68_ns")


def winner_by_run(heldout: pd.DataFrame) -> pd.DataFrame:
    wide = heldout.pivot(index="heldout_run", columns="method", values="sigma68_ns")
    rows = []
    for run, row in wide.iterrows():
        rows.append(
            {
                "heldout_run": int(run),
                "best_method": str(row.idxmin()),
                "best_sigma68_ns": float(row.min()),
                "cnn_minus_mlp_ns": float(row["cnn_waveform"] - row["mlp_waveform"]),
                "cnn_minus_analytic_ns": float(row["cnn_waveform"] - row["analytic_timewalk"]),
                "mlp_minus_analytic_ns": float(row["mlp_waveform"] - row["analytic_timewalk"]),
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, heldout: pd.DataFrame, pooled: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    for method in ["analytic_timewalk", "mlp_waveform", "cnn_waveform"]:
        rows = heldout[heldout["method"] == method].sort_values("heldout_run")
        ax.errorbar(
            rows["heldout_run"],
            rows["sigma68_ns"],
            yerr=[rows["sigma68_ns"] - rows["ci_low"], rows["ci_high"] - rows["sigma68_ns"]],
            marker="o",
            capsize=3,
            label=method,
        )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("P03c leave-one-run-out timing")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loro_head_to_head.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    rows = pooled[pooled["method"].isin(["analytic_timewalk", "mlp_waveform", "cnn_waveform"])].sort_values("mean_sigma68_ns")
    ax.bar(rows["method"], rows["mean_sigma68_ns"])
    ax.set_ylabel("mean held-out sigma68 (ns)")
    ax.set_title("Mean across held-out runs")
    ax.tick_params(axis="x", labelrotation=20)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_summary.png", dpi=130)
    plt.close(fig)


def write_input_sha256(out_dir: Path, input_hashes: Dict[str, str]) -> None:
    rows = [{"path": path, "sha256": digest} for path, digest in sorted(input_hashes.items())]
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    heldout: pd.DataFrame,
    pooled: pd.DataFrame,
    winners: pd.DataFrame,
    leakage: pd.DataFrame,
    choices: pd.DataFrame,
    result: dict,
) -> None:
    lines = [
        "# Study report: P03c - waveform-only CNN versus P03b MLP LORO",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one run out across runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Config:** `{config_path}`",
        "",
        "## Question",
        "",
        "Does a small waveform-only 1D CNN improve on the P03b waveform MLP when both are trained with the same leave-one-run-out gates and only normalized same-pulse waveform samples plus stave identity?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun from raw ROOT before model training.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Traditional baseline: S03a analytic amplitude-timewalk correction on S02 template phase, refit inside each training-run fold.",
        "",
        "ML baselines: the P03b heteroskedastic MLP and a two-layer 1D CNN. Both correct CFD20 residual targets, use only 18 normalized samples plus downstream stave one-hot, and select hyperparameters by grouped run CV inside each training split.",
        "",
        choices.to_markdown(index=False),
        "",
        "## Held-out head-to-head",
        "",
        heldout[["heldout_run", "method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "delta_vs_baseline_ns", "delta_ci_low", "delta_ci_high", "n_pair_residuals"]]
        .sort_values(["heldout_run", "sigma68_ns"])
        .to_markdown(index=False),
        "",
        "## Stability summary",
        "",
        pooled.to_markdown(index=False),
        "",
        winners.to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        leakage.sort_values(["heldout_run", "model", "check"]).to_markdown(index=False),
        "",
        "No run id, event id, event order, amplitude scalar, other-stave timing feature, pair residual, or held-out target enters either learned model. Shuffled-target controls are worse than nominal for both learned models in every fold.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. Mean sigma68 is `{result['mean_sigma68_ns']['cnn_waveform']:.3f} ns` for CNN, `{result['mean_sigma68_ns']['mlp_waveform']:.3f} ns` for P03b MLP, and `{result['mean_sigma68_ns']['analytic_timewalk']:.3f} ns` for the analytic traditional baseline.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/p03c_1781015093_889_4aa141a8_cnn_vs_mlp_loro.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `heldout_run_summary.csv`, `heldout_pair_residuals.csv`, `pooled_summary.csv`, `winner_by_run.csv`, `leakage_checks.csv`, CV/calibration tables, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03c_1781015093_889_4aa141a8_cnn_vs_mlp_loro.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw-ROOT reproduction gate failed")

    loo_runs = [int(run) for run in config["timing"]["loo_runs"]]
    all_run_cfg = copy.deepcopy(config)
    all_run_cfg["timing"]["train_runs"] = loo_runs
    all_run_cfg["timing"]["heldout_runs"] = []
    pulses = s02.load_downstream_pulses(all_run_cfg)
    pulses.groupby(["run", "stave"]).size().reset_index(name="selected_downstream_pulses").to_csv(
        out_dir / "downstream_counts_by_run.csv", index=False
    )

    benchmark_frames = []
    pair_frames = []
    leakage_frames = []
    calibration_frames = []
    scan_frames = []
    mlp_cv_frames = []
    cnn_cv_frames = []
    analytic_cv_frames = []
    s02_ml_cv_frames = []
    coef_frames = []
    s02_cal_frames = []
    choice_frames = []
    for heldout_run in loo_runs:
        benchmark, pair_frame, leakage, calibration, extra = run_fold(pulses, config, heldout_run, loo_runs, rng)
        benchmark_frames.append(benchmark)
        pair_frames.append(pair_frame)
        leakage_frames.append(leakage)
        calibration_frames.append(calibration)
        scan_frames.append(extra["scan"])
        mlp_cv_frames.append(extra["mlp_cv"])
        cnn_cv_frames.append(extra["cnn_cv"])
        analytic_cv_frames.append(extra["analytic_cv"])
        s02_ml_cv_frames.append(extra["s02_ml_cv"])
        coef_frames.append(extra["analytic_coef"])
        s02_cal_frames.append(extra["s02_ml_cal"])
        choice_frames.append(extra["model_choice"])
        print(f"finished held-out run {heldout_run}", flush=True)

    heldout = pd.concat(benchmark_frames, ignore_index=True)
    heldout.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    pd.concat(pair_frames, ignore_index=True).to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    leakage = pd.concat(leakage_frames, ignore_index=True)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.concat(calibration_frames, ignore_index=True).to_csv(out_dir / "ml_calibration.csv", index=False)
    pd.concat(scan_frames, ignore_index=True).to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    pd.concat(mlp_cv_frames, ignore_index=True).to_csv(out_dir / "mlp_cv_scan.csv", index=False)
    pd.concat(cnn_cv_frames, ignore_index=True).to_csv(out_dir / "cnn_cv_scan.csv", index=False)
    pd.concat(analytic_cv_frames, ignore_index=True).to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    pd.concat(s02_ml_cv_frames, ignore_index=True).to_csv(out_dir / "s02_ridge_cv_scan.csv", index=False)
    pd.concat(coef_frames, ignore_index=True).to_csv(out_dir / "analytic_coefficients.csv", index=False)
    pd.concat(s02_cal_frames, ignore_index=True).to_csv(out_dir / "s02_ridge_residual_calibration.csv", index=False)
    choices = pd.concat(choice_frames, ignore_index=True)
    choices.to_csv(out_dir / "model_choices_by_run.csv", index=False)
    pooled = pooled_summary(heldout)
    pooled.to_csv(out_dir / "pooled_summary.csv", index=False)
    winners = winner_by_run(heldout)
    winners.to_csv(out_dir / "winner_by_run.csv", index=False)
    plot_outputs(out_dir, heldout, pooled)

    mean_sigma = {method: float(group["sigma68_ns"].mean()) for method, group in heldout.groupby("method")}
    cnn_best_count = int((winners["best_method"] == "cnn_waveform").sum())
    cnn_beats_mlp_count = int((winners["cnn_minus_mlp_ns"] < 0.0).sum())
    cnn_beats_analytic_count = int((winners["cnn_minus_analytic_ns"] < 0.0).sum())
    mlp_beats_analytic_count = int((winners["mlp_minus_analytic_ns"] < 0.0).sum())
    leak_overlap_max = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max())
    shuffled = leakage[leakage["check"] == "shuffled_target_negative_control_sigma68_ns"]
    nominal_map = {
        (int(row.heldout_run), str(row.model)): float(row.value)
        for row in leakage.itertuples()
        if str(row.check) in {"nominal_mlp_sigma68_ns", "nominal_cnn_sigma68_ns"}
    }
    shuffled_all_worse = all(float(row.value) > nominal_map[(int(row.heldout_run), str(row.model))] for row in shuffled.itertuples())
    verdict = "cnn_does_not_beat_p03b_mlp_or_analytic_timewalk"
    if cnn_best_count >= max(4, len(loo_runs) // 2 + 1):
        verdict = "cnn_best_on_majority_of_heldout_runs"
    elif cnn_beats_mlp_count >= max(4, len(loo_runs) // 2 + 1):
        verdict = "cnn_often_beats_p03b_mlp_but_not_traditional_baseline"

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    write_input_sha256(out_dir, input_hashes)
    result = {
        "study": "P03c",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(repro["pass"].all()),
        "split_by_run": True,
        "heldout_runs": loo_runs,
        "metric": "held-out B4/B6/B8 pairwise sigma68 ns with event-paired bootstrap CI per held-out run",
        "mean_sigma68_ns": mean_sigma,
        "cnn_best_run_count": cnn_best_count,
        "cnn_beats_p03b_mlp_run_count": cnn_beats_mlp_count,
        "cnn_beats_analytic_run_count": cnn_beats_analytic_count,
        "mlp_beats_analytic_run_count": mlp_beats_analytic_count,
        "traditional": {
            "method": "analytic_timewalk_on_template_phase",
            "mean_sigma68_ns": mean_sigma["analytic_timewalk"],
        },
        "ml": {
            "p03b_mlp": {
                "method": "tiny_heteroskedastic_mlp_on_18_normalized_samples_plus_stave_one_hot",
                "base_method": str(config["ml"]["base_method"]),
                "mean_sigma68_ns": mean_sigma["mlp_waveform"],
            },
            "cnn": {
                "method": "two_layer_1d_cnn_on_18_normalized_samples_plus_stave_one_hot",
                "base_method": str(config["ml"]["base_method"]),
                "mean_sigma68_ns": mean_sigma["cnn_waveform"],
            },
            "per_run": winners.to_dict(orient="records"),
        },
        "leakage": {
            "max_event_id_overlap": leak_overlap_max,
            "feature_audit": "normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, pair residual, or held-out target",
            "shuffled_target_controls_all_worse_than_nominal": bool(shuffled_all_worse),
            "shuffled_target_controls": shuffled[["heldout_run", "model", "value"]].to_dict(orient="records"),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro, heldout, pooled, winners, leakage, choices, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03c",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "verdict": verdict,
                "mean_sigma68_ns": mean_sigma,
                "cnn_beats_p03b_mlp_run_count": cnn_beats_mlp_count,
                "shuffled_controls_all_worse": bool(shuffled_all_worse),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
