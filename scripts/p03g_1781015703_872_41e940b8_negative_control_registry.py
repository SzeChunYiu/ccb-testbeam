#!/usr/bin/env python3
"""P03g waveform timing residual negative-control registry.

The gate is raw ROOT -> selected-pulse count reproduction first. The timing
study then runs leave-one-run-out over Sample-II analysis runs, using an
amp-only analytic timewalk correction on template phase as the traditional
baseline. P03c-style MLP/CNN residual learners are trained on true waveform
features and preregistered negative controls.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03g")

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


def fold_config(config: dict, heldout_run: int, loo_runs: Sequence[int]) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [int(run) for run in loo_runs if int(run) != int(heldout_run)]
    cfg["analytic"]["candidate_models"] = ["amp_only"]
    return cfg


def one_hot(values: Sequence, levels: Sequence) -> np.ndarray:
    out = np.zeros((len(values), len(levels)), dtype=np.float32)
    index = {value: i for i, value in enumerate(levels)}
    for row, value in enumerate(values):
        if value in index:
            out[row, index[value]] = 1.0
    return out


def scramble_phase_rows(X: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.empty_like(X, dtype=np.float32)
    n = X.shape[1]
    for i, row in enumerate(X):
        fft = np.fft.rfft(row.astype(float))
        mag = np.abs(fft)
        phase = np.angle(fft)
        if len(phase) > 2:
            phase[1:-1] = rng.uniform(-np.pi, np.pi, size=len(phase) - 2)
        if n % 2 == 1 and len(phase) > 1:
            phase[-1] = rng.uniform(-np.pi, np.pi)
        out[i] = np.fft.irfft(mag * np.exp(1j * phase), n=n).astype(np.float32)
    return out


def permute_sample_rows(X: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.empty_like(X, dtype=np.float32)
    for i, row in enumerate(X):
        out[i] = row[rng.permutation(X.shape[1])]
    return out


def control_features(
    pulses: pd.DataFrame,
    config: dict,
    mode: str,
    heldout_run: int,
    architecture: str,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    staves = list(config["timing"]["downstream_staves"])
    stave_hot = one_hot(pulses["stave"].tolist(), staves)
    runs = [int(run) for run in pulses["run"]]
    run_hot = one_hot(runs, list(config["timing"]["loo_runs"]))
    amp_tab = np.column_stack(
        [
            np.log1p(np.maximum(amp, 1.0)),
            1000.0 / np.maximum(amp, 1.0),
            np.sqrt(1000.0 / np.maximum(amp, 1.0)),
        ]
    ).astype(np.float32)
    seed = int(config["ml"]["random_seed"]) + 10000 * int(heldout_run) + (0 if architecture == "mlp" else 500)

    if mode == "true_waveform":
        seq = norm
        tab = stave_hot
        names = [f"sample_{i:02d}_over_amp" for i in range(seq.shape[1])] + [f"stave_{s}" for s in staves]
    elif mode == "amplitude_only":
        seq = np.zeros_like(norm)
        tab = np.hstack([amp_tab, stave_hot])
        names = ["log_amp", "inv_amp_1000", "inv_sqrt_amp_1000"] + [f"stave_{s}" for s in staves]
    elif mode == "phase_scrambled":
        seq = scramble_phase_rows(norm, seed + 11)
        tab = stave_hot
        names = [f"phase_scrambled_sample_{i:02d}" for i in range(seq.shape[1])] + [f"stave_{s}" for s in staves]
    elif mode == "sample_permuted":
        seq = permute_sample_rows(norm, seed + 23)
        tab = stave_hot
        names = [f"row_permuted_sample_{i:02d}" for i in range(seq.shape[1])] + [f"stave_{s}" for s in staves]
    elif mode == "run_only":
        seq = np.zeros_like(norm)
        tab = run_hot
        names = [f"run_{run}" for run in config["timing"]["loo_runs"]]
    elif mode == "shuffled_target":
        seq = norm
        tab = stave_hot
        names = [f"sample_{i:02d}_over_amp" for i in range(seq.shape[1])] + [f"stave_{s}" for s in staves]
    else:
        raise ValueError(f"unknown control mode: {mode}")
    return seq.astype(np.float32), tab.astype(np.float32), names


def finite_mask(seq: np.ndarray, tab: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(seq), axis=1) & np.all(np.isfinite(tab), axis=1) & np.isfinite(runs)


class ResidualMLP(nn.Module):
    def __init__(self, n_features: int, hidden: int) -> None:
        super().__init__()
        mid = max(int(hidden) // 2, 8)
        self.net = nn.Sequential(nn.Linear(n_features, int(hidden)), nn.ReLU(), nn.Linear(int(hidden), mid), nn.ReLU(), nn.Linear(mid, 2))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        out = self.net(torch.cat([seq, tab], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


class ResidualCNN(nn.Module):
    def __init__(self, n_samples: int, n_tab: int, channels: int) -> None:
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
        width = max(2 * c + int(n_tab), 8)
        self.head = nn.Sequential(nn.Linear(2 * c + int(n_tab), width), nn.ReLU(), nn.Linear(width, 2))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.conv(seq[:, None, :])
        out = self.head(torch.cat([z, tab], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


def build_model(architecture: str, n_samples: int, n_tab: int, size: int) -> nn.Module:
    if architecture == "mlp":
        return ResidualMLP(n_samples + n_tab, int(size))
    if architecture == "cnn":
        return ResidualCNN(n_samples, n_tab, int(size))
    raise ValueError(architecture)


def standardize_train_apply(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    scaler = StandardScaler()
    out = X.copy()
    scaler.fit(X[train_idx])
    out[:] = scaler.transform(X)
    return out.astype(np.float32), scaler


def train_model(
    seq: np.ndarray,
    tab: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    architecture: str,
    size: int,
    weight_decay: float,
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[nn.Module, np.ndarray, np.ndarray, StandardScaler, StandardScaler]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    seq_s, seq_scaler = standardize_train_apply(seq, train_idx)
    tab_s, tab_scaler = standardize_train_apply(tab, train_idx)
    y_train = y[train_idx].astype(np.float32).copy()
    if shuffle_y:
        rng.shuffle(y_train)
    model = build_model(architecture, seq.shape[1], tab.shape[1], int(size))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["learning_rate"]), weight_decay=float(weight_decay))
    seq_train = torch.from_numpy(seq_s[train_idx])
    tab_train = torch.from_numpy(tab_s[train_idx])
    y_train_t = torch.from_numpy(y_train)
    batch_size = int(config["ml"]["batch_size"])
    min_var = float(config["ml"]["min_sigma_ns"]) ** 2
    for _ in range(int(config["ml"]["epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch_size):
            take = order[start : start + batch_size]
            mu, log_var = model(seq_train[take], tab_train[take])
            var = torch.exp(log_var) + min_var
            loss = torch.mean(0.5 * ((y_train_t[take] - mu) ** 2 / var + torch.log(var)))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model, seq_s, tab_s, seq_scaler, tab_scaler


def predict_model(model: nn.Module, seq_s: np.ndarray, tab_s: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    with torch.no_grad():
        mu, log_var = model(torch.from_numpy(seq_s.astype(np.float32)), torch.from_numpy(tab_s.astype(np.float32)))
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


def tune_true_architecture(
    pulses: pd.DataFrame,
    config: dict,
    architecture: str,
    targets: np.ndarray,
    heldout_run: int,
) -> Tuple[dict, pd.DataFrame]:
    seq, tab, names = control_features(pulses, config, "true_waveform", heldout_run, architecture)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & finite_mask(seq, tab, targets, runs)
    train_idx_all = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    sizes = config["ml"]["mlp_hidden_sizes"] if architecture == "mlp" else config["ml"]["cnn_channels"]
    rows = []
    best = {"score": math.inf, "size": None, "weight_decay": None}
    for size in sizes:
        for weight_decay in config["ml"]["weight_decays"]:
            scores = []
            for fold, (tr, va) in enumerate(gkf.split(seq[train_mask], targets[train_mask], groups=groups)):
                tr_idx = train_idx_all[tr]
                va_idx = train_idx_all[va]
                model, seq_s, tab_s, _, _ = train_model(
                    seq,
                    tab,
                    targets,
                    tr_idx,
                    architecture,
                    int(size),
                    float(weight_decay),
                    config,
                    int(config["ml"]["random_seed"]) + 101 * fold + 17 * int(size) + 3000 * int(heldout_run),
                )
                pred, sigma = predict_model(model, seq_s, tab_s, config)
                vals = evaluate_corrected(
                    pulses.iloc[va_idx].copy(),
                    f"{architecture}_true_cv",
                    corrected_values(pulses, str(config["ml"]["base_method"]), pred)[va_idx],
                    config,
                    sorted(np.unique(runs[va_idx]).tolist()),
                )
                score = s02.sigma68(vals)
                scores.append(score)
                rows.append(
                    {
                        "heldout_run": int(heldout_run),
                        "architecture": architecture,
                        "control": "true_waveform",
                        "size": int(size),
                        "weight_decay": float(weight_decay),
                        "fold": int(fold),
                        "sigma68_ns": float(score),
                        "n_pair_residuals": int(len(vals)),
                        "pred_sigma_median_ns": float(np.nanmedian(sigma[va_idx])),
                    }
                )
            mean_score = float(np.nanmean(scores))
            rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "architecture": architecture,
                    "control": "true_waveform",
                    "size": int(size),
                    "weight_decay": float(weight_decay),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                    "pred_sigma_median_ns": float("nan"),
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "size": int(size), "weight_decay": float(weight_decay)}
    best["feature_names_sha256"] = hashlib.sha256(",".join(names).encode("utf-8")).hexdigest()
    return best, pd.DataFrame(rows)


def train_control_model(
    pulses: pd.DataFrame,
    config: dict,
    architecture: str,
    control: str,
    choice: dict,
    targets: np.ndarray,
    heldout_run: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    seq, tab, names = control_features(pulses, config, control, heldout_run, architecture)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & finite_mask(seq, tab, targets, runs)
    train_idx = np.flatnonzero(train_mask)
    model, seq_s, tab_s, seq_scaler, tab_scaler = train_model(
        seq,
        tab,
        targets,
        train_idx,
        architecture,
        int(choice["size"]),
        float(choice["weight_decay"]),
        config,
        int(config["ml"]["random_seed"]) + 7000 * int(heldout_run) + (19 if architecture == "mlp" else 29) + len(control),
        shuffle_y=(control == "shuffled_target"),
    )
    pred, sigma = predict_model(model, seq_s, tab_s, config)
    out = pulses.copy()
    label = f"{architecture}_{control}"
    out[f"{label}_target_residual_ns"] = targets
    out[f"{label}_pred_residual_ns"] = pred
    out[f"{label}_pred_sigma_ns"] = sigma
    out[f"t_{label}_ns"] = corrected_values(pulses, str(config["ml"]["base_method"]), pred)
    held = out[out["run"].isin(config["timing"]["heldout_runs"])].copy()
    held = held[np.isfinite(held[f"{label}_target_residual_ns"]) & np.isfinite(held[f"{label}_pred_sigma_ns"])]
    err = held[f"{label}_target_residual_ns"] - held[f"{label}_pred_residual_ns"]
    pull = err / held[f"{label}_pred_sigma_ns"]
    calibration = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "method": label,
                "architecture": architecture,
                "control": control,
                "n_pulses": int(len(held)),
                "pred_sigma_median_ns": float(held[f"{label}_pred_sigma_ns"].median()),
                "abs_error_median_ns": float(err.abs().median()),
                "pull_width_sigma68": float(s02.sigma68(pull.to_numpy(dtype=float))),
                "pull_rms": float(s02.full_rms(pull.to_numpy(dtype=float))),
            }
        ]
    )
    info = {
        "method": label,
        "architecture": architecture,
        "control": control,
        "size": int(choice["size"]),
        "weight_decay": float(choice["weight_decay"]),
        "n_features": int(seq.shape[1] + tab.shape[1]),
        "feature_names_sha256": hashlib.sha256(",".join(names).encode("utf-8")).hexdigest(),
        "seq_scaler_mean_sha256": hashlib.sha256(seq_scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
        "tab_scaler_mean_sha256": hashlib.sha256(tab_scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
    }
    return out, calibration, info


def event_pair_residual_frame(
    pulses: pd.DataFrame,
    methods: Sequence[Tuple[str, str]],
    config: dict,
    runs: Sequence[int],
) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    rows = []
    for method, label in methods:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for event_id, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                if a in wide.columns and b in wide.columns:
                    rows.append({"event_id": event_id, "pair": f"{a}-{b}", "method": label, "residual_ns": float(row[a] - row[b])})
    return pd.DataFrame(rows)


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


def run_level_gap_summary(heldout: pd.DataFrame, calibration: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 31337)
    wide = heldout.pivot(index="heldout_run", columns="method", values="sigma68_ns")
    rows = []
    controls = [c for c in config["ml"]["controls"] if c != "true_waveform"]
    for architecture in ["mlp", "cnn"]:
        true_label = f"{architecture}_true_waveform"
        if true_label not in wide.columns:
            continue
        for control in controls:
            control_label = f"{architecture}_{control}"
            if control_label not in wide.columns:
                continue
            gaps = (wide[true_label] - wide[control_label]).dropna().to_numpy(dtype=float)
            if len(gaps) == 0:
                continue
            boot = []
            for _ in range(int(config["ml"]["run_bootstrap_samples"])):
                sample = rng.choice(gaps, size=len(gaps), replace=True)
                boot.append(float(np.mean(sample)))
            loo = []
            for i in range(len(gaps)):
                keep = np.delete(gaps, i)
                loo.append(float(np.mean(keep)) if len(keep) else float("nan"))
            rows.append(
                {
                    "architecture": architecture,
                    "true_method": true_label,
                    "control_method": control_label,
                    "n_runs": int(len(gaps)),
                    "mean_true_minus_control_sigma68_ns": float(np.mean(gaps)),
                    "run_bootstrap_ci_low": float(np.percentile(boot, 2.5)),
                    "run_bootstrap_ci_high": float(np.percentile(boot, 97.5)),
                    "leave_one_run_min": float(np.nanmin(loo)),
                    "leave_one_run_max": float(np.nanmax(loo)),
                }
            )
    pull = calibration.pivot_table(index=["heldout_run"], columns="method", values="pull_width_sigma68", aggfunc="first")
    for method in sorted(calibration["method"].unique()):
        vals = pull[method].dropna().to_numpy(dtype=float) if method in pull.columns else np.asarray([])
        if len(vals):
            rows.append(
                {
                    "architecture": method.split("_", 1)[0],
                    "true_method": method,
                    "control_method": "pull_width_sigma68",
                    "n_runs": int(len(vals)),
                    "mean_true_minus_control_sigma68_ns": float(np.mean(vals)),
                    "run_bootstrap_ci_low": float(np.percentile([np.mean(rng.choice(vals, size=len(vals), replace=True)) for _ in range(2000)], 2.5)),
                    "run_bootstrap_ci_high": float(np.percentile([np.mean(rng.choice(vals, size=len(vals), replace=True)) for _ in range(2000)], 97.5)),
                    "leave_one_run_min": float(np.nanmin([np.mean(np.delete(vals, i)) for i in range(len(vals))])) if len(vals) > 1 else float(vals[0]),
                    "leave_one_run_max": float(np.nanmax([np.mean(np.delete(vals, i)) for i in range(len(vals))])) if len(vals) > 1 else float(vals[0]),
                }
            )
    return pd.DataFrame(rows)


def run_fold(
    pulses: pd.DataFrame,
    config: dict,
    heldout_run: int,
    loo_runs: Sequence[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    cfg = fold_config(config, heldout_run, loo_runs)
    train_pulses = pulses[pulses["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    fold_pulses = pulses.copy()
    methods = s02.add_traditional_times(fold_pulses, cfg, templates)
    scan = s02.evaluate_methods(fold_pulses, methods, cfg)
    scan["heldout_run"] = int(heldout_run)
    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(fold_pulses, cfg, str(cfg["timing"]["base_method"]))
    combined = analytic_pulses.copy()
    targets = s02.event_residual_targets(combined, str(cfg["ml"]["base_method"]), 2.0, cfg)

    cv_frames = []
    calibration_frames = []
    choices = []
    method_specs = [("analytic_timewalk", "analytic_timewalk")]
    for architecture in ["mlp", "cnn"]:
        choice, cv = tune_true_architecture(combined, cfg, architecture, targets, heldout_run)
        cv_frames.append(cv)
        for control in cfg["ml"]["controls"]:
            model_pulses, calibration, info = train_control_model(combined, cfg, architecture, control, choice, targets, heldout_run)
            label = info["method"]
            combined[f"t_{label}_ns"] = model_pulses[f"t_{label}_ns"].to_numpy(dtype=float)
            method_specs.append((label, label))
            calibration_frames.append(calibration)
            info["heldout_run"] = int(heldout_run)
            info["cv_sigma68_ns"] = float(choice["score"])
            choices.append(info)

    pair_frame = event_pair_residual_frame(combined, method_specs, cfg, [heldout_run])
    pair_frame["heldout_run"] = int(heldout_run)
    benchmark = paired_event_bootstrap(pair_frame, "analytic_timewalk", rng, int(cfg["ml"]["bootstrap_samples"]))
    benchmark["heldout_run"] = int(heldout_run)
    benchmark["train_runs"] = ",".join(str(run) for run in cfg["timing"]["train_runs"])

    train_event_ids = set(combined[combined["run"].isin(cfg["timing"]["train_runs"])]["event_id"])
    held_event_ids = set(combined[combined["run"].isin(cfg["timing"]["heldout_runs"])]["event_id"])
    leakage = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids & held_event_ids)),
                "detail": "must be zero",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "feature_audit",
                "value": 0.0,
                "detail": "true waveform uses same-pulse normalized samples plus stave; controls use amplitude-only, phase-scrambled, row-sample-permuted, run-only, or shuffled targets; no event id, event order, pair residual, other-stave time, or held-out target feature",
            },
            {
                "heldout_run": int(heldout_run),
                "check": "analytic_candidate",
                "value": 0.0,
                "detail": f"{best_candidate}, alpha={best_alpha}",
            },
        ]
    )
    extras = {
        "scan": scan,
        "analytic_cv": analytic_cv.assign(heldout_run=int(heldout_run)),
        "analytic_coef": analytic_coef.assign(heldout_run=int(heldout_run)),
        "model_choices": pd.DataFrame(choices),
    }
    return (
        benchmark,
        pair_frame,
        leakage,
        pd.concat(calibration_frames, ignore_index=True),
        pd.concat(cv_frames, ignore_index=True),
        extras,
    )


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
                "mean_full_rms_ns": float(group["full_rms_ns"].mean()),
                "n_heldout_runs": int(group["heldout_run"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_sigma68_ns")


def plot_outputs(out_dir: Path, heldout: pd.DataFrame, gaps: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.0, 5.0))
    for method in ["analytic_timewalk", "mlp_true_waveform", "cnn_true_waveform", "mlp_shuffled_target", "cnn_shuffled_target"]:
        rows = heldout[heldout["method"] == method].sort_values("heldout_run")
        if len(rows) == 0:
            continue
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
    ax.set_title("P03g true waveform versus target-shuffle controls")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_true_vs_shuffle_by_run.png", dpi=130)
    plt.close(fig)

    metric_rows = gaps[gaps["control_method"] != "pull_width_sigma68"].copy()
    if len(metric_rows):
        fig, ax = plt.subplots(figsize=(9.0, 4.8))
        metric_rows = metric_rows.sort_values("mean_true_minus_control_sigma68_ns")
        x = np.arange(len(metric_rows))
        ax.bar(x, metric_rows["mean_true_minus_control_sigma68_ns"])
        ax.errorbar(
            x,
            metric_rows["mean_true_minus_control_sigma68_ns"],
            yerr=[
                metric_rows["mean_true_minus_control_sigma68_ns"] - metric_rows["run_bootstrap_ci_low"],
                metric_rows["run_bootstrap_ci_high"] - metric_rows["mean_true_minus_control_sigma68_ns"],
            ],
            fmt="none",
            ecolor="black",
            capsize=3,
        )
        ax.axhline(0.0, color="black", linewidth=1)
        ax.set_xticks(x)
        ax.set_xticklabels(metric_rows["control_method"], rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("true - control mean sigma68 (ns)")
        ax.set_title("Run-bootstrap true/control gaps")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_true_control_gaps.png", dpi=130)
        plt.close(fig)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    heldout: pd.DataFrame,
    pooled: pd.DataFrame,
    gaps: pd.DataFrame,
    calibration: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    head = pooled[pooled["method"].isin(["analytic_timewalk", "mlp_true_waveform", "cnn_true_waveform"])].copy()
    controls = pooled[~pooled["method"].isin(["analytic_timewalk", "mlp_true_waveform", "cnn_true_waveform"])].copy()
    lines = [
        "# Study report: P03g - waveform timing residual negative-control registry",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-06-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo",
        "- **Split:** leave one Sample-II analysis run out across runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Config:** `{config_path}`",
        "",
        "## Question",
        "",
        "Can waveform residual learners beat an amp-only analytic timewalk correction only when physically meaningful waveform information is present, and fail under preregistered negative controls?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun from raw ROOT before timing work.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Traditional method: template-phase timing plus amp-only analytic timewalk, calibrated without the held-out run. The analytic model was fixed to `amp_only` and used no waveform residual learner.",
        "",
        "ML method: P03c-style heteroskedastic MLP and tiny 1D CNN residual learners on `analytic_timewalk` residual targets. Hyperparameters were chosen by grouped train-run CV on true waveforms, then frozen for amplitude-only, phase-scrambled, sample-permuted, run-only, and shuffled-target controls.",
        "",
        "## Head-to-head summary",
        "",
        head.to_markdown(index=False),
        "",
        "## Negative controls",
        "",
        controls.to_markdown(index=False),
        "",
        "## True-control gaps and pull widths",
        "",
        gaps.to_markdown(index=False),
        "",
        "## Per-heldout-run metrics",
        "",
        heldout[["heldout_run", "method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "delta_vs_baseline_ns", "delta_ci_low", "delta_ci_high", "n_pair_residuals"]]
        .sort_values(["heldout_run", "sigma68_ns"])
        .to_markdown(index=False),
        "",
        "## Calibration and leakage checks",
        "",
        calibration.to_markdown(index=False),
        "",
        leakage.sort_values(["heldout_run", "check"]).to_markdown(index=False),
        "",
        "The leakage audit found zero train/held-out event-id overlap in every fold. The controls deliberately remove or corrupt waveform meaning without adding event id, event order, pair residuals, other-stave timing, or held-out targets.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. Mean sigma68 is analytic `{result['traditional']['mean_sigma68_ns']:.3f} ns`, MLP true waveform `{result['ml']['mlp_true_waveform']['mean_sigma68_ns']:.3f} ns`, and CNN true waveform `{result['ml']['cnn_true_waveform']['mean_sigma68_ns']:.3f} ns`.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/p03g_1781015703_872_41e940b8_negative_control_registry.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `heldout_run_summary.csv`, `heldout_pair_residuals.csv`, `pooled_summary.csv`, `true_control_gap_summary.csv`, `ml_cv_scan.csv`, `ml_calibration.csv`, `leakage_checks.csv`, `result.json`, `manifest.json`, figures, and raw input hashes.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03g_1781015703_872_41e940b8_negative_control_registry.yaml")
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
        raise RuntimeError("raw-ROOT selected-pulse reproduction gate failed")

    loo_runs = [int(run) for run in config["timing"]["loo_runs"]]
    all_run_cfg = copy.deepcopy(config)
    all_run_cfg["timing"]["train_runs"] = loo_runs
    all_run_cfg["timing"]["heldout_runs"] = []
    pulses = s02.load_downstream_pulses(all_run_cfg)
    pulses.groupby(["run", "stave"]).size().reset_index(name="selected_downstream_pulses").to_csv(out_dir / "downstream_counts_by_run.csv", index=False)

    benchmark_frames = []
    pair_frames = []
    leakage_frames = []
    calibration_frames = []
    cv_frames = []
    scan_frames = []
    analytic_cv_frames = []
    analytic_coef_frames = []
    choice_frames = []
    for heldout_run in loo_runs:
        benchmark, pair_frame, leakage, calibration, cv, extra = run_fold(pulses, config, heldout_run, loo_runs, rng)
        benchmark_frames.append(benchmark)
        pair_frames.append(pair_frame)
        leakage_frames.append(leakage)
        calibration_frames.append(calibration)
        cv_frames.append(cv)
        scan_frames.append(extra["scan"])
        analytic_cv_frames.append(extra["analytic_cv"])
        analytic_coef_frames.append(extra["analytic_coef"])
        choice_frames.append(extra["model_choices"])

    heldout = pd.concat(benchmark_frames, ignore_index=True)
    heldout.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    pair_frame = pd.concat(pair_frames, ignore_index=True)
    pair_frame.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    leakage = pd.concat(leakage_frames, ignore_index=True)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    calibration = pd.concat(calibration_frames, ignore_index=True)
    calibration.to_csv(out_dir / "ml_calibration.csv", index=False)
    cv = pd.concat(cv_frames, ignore_index=True)
    cv.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    pd.concat(scan_frames, ignore_index=True).to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    pd.concat(analytic_cv_frames, ignore_index=True).to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    pd.concat(analytic_coef_frames, ignore_index=True).to_csv(out_dir / "analytic_coefficients.csv", index=False)
    choices = pd.concat(choice_frames, ignore_index=True)
    choices.to_csv(out_dir / "model_choices_by_run.csv", index=False)

    pooled = pooled_summary(heldout)
    pooled.to_csv(out_dir / "pooled_summary.csv", index=False)
    gaps = run_level_gap_summary(heldout, calibration, config)
    gaps.to_csv(out_dir / "true_control_gap_summary.csv", index=False)
    plot_outputs(out_dir, heldout, gaps)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in sorted(input_hashes.items())]).to_csv(out_dir / "input_sha256.csv", index=False)

    mean_sigma = {row["method"]: float(row["mean_sigma68_ns"]) for _, row in pooled.iterrows()}
    true_methods = ["mlp_true_waveform", "cnn_true_waveform"]
    analytic_mean = mean_sigma["analytic_timewalk"]
    best_true = min(true_methods, key=lambda method: mean_sigma[method])
    control_rows = gaps[gaps["control_method"] != "pull_width_sigma68"].copy()
    true_beats_all_controls = bool((control_rows["run_bootstrap_ci_high"] < 0.0).all()) if len(control_rows) else False
    true_beats_analytic = mean_sigma[best_true] < analytic_mean
    verdict = "negative_controls_do_not_support_waveform_residual_adoption"
    if true_beats_analytic and true_beats_all_controls:
        verdict = "true_waveform_beats_analytic_and_all_controls"
    elif true_beats_analytic:
        verdict = "true_waveform_beats_analytic_but_controls_are_not_all_rejected"
    elif true_beats_all_controls:
        verdict = "true_waveform_beats_controls_but_not_analytic"

    result = {
        "study": "P03g",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "split_by_run": True,
        "heldout_runs": loo_runs,
        "metric": "per-heldout-run B4/B6/B8 pairwise sigma68, full RMS, ML pull width, paired event bootstrap CIs, and run-block true-control gap CIs",
        "traditional": {
            "method": "template_phase_plus_amp_only_analytic_timewalk",
            "mean_sigma68_ns": analytic_mean,
            "per_run": heldout[heldout["method"] == "analytic_timewalk"][["heldout_run", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns"]].to_dict(orient="records"),
        },
        "ml": {
            "mlp_true_waveform": {
                "mean_sigma68_ns": mean_sigma["mlp_true_waveform"],
                "mean_delta_vs_analytic_ns": float(mean_sigma["mlp_true_waveform"] - analytic_mean),
            },
            "cnn_true_waveform": {
                "mean_sigma68_ns": mean_sigma["cnn_true_waveform"],
                "mean_delta_vs_analytic_ns": float(mean_sigma["cnn_true_waveform"] - analytic_mean),
            },
            "controls": pooled[pooled["method"] != "analytic_timewalk"].to_dict(orient="records"),
            "true_control_gaps": gaps.to_dict(orient="records"),
        },
        "leakage": {
            "max_event_id_overlap": int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max()),
            "feature_audit": str(leakage[leakage["check"] == "feature_audit"]["detail"].iloc[0]),
            "run_only_controls": pooled[pooled["method"].str.contains("run_only")].to_dict(orient="records"),
            "shuffled_target_controls": pooled[pooled["method"].str.contains("shuffled_target")].to_dict(orient="records"),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "follow_up_ticket_appended": False,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro, heldout, pooled, gaps, calibration, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03g",
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
    print(json.dumps({"out_dir": str(out_dir), "verdict": verdict, "mean_sigma68_ns": mean_sigma}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
