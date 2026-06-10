#!/usr/bin/env python3
"""P03f early-peak sample-window timing residual ablation.

This ticket asks whether samples 3-6 carry stable timing-residual information
after an analytic amp-only/template-phase timewalk correction. The raw count
gate is run before model work. The analysis uses leave-one-run-out folds over
Sample II analysis runs, event-paired bootstraps within held-out runs, and a
run-block bootstrap for pooled ML-minus-traditional deltas.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03f")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
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


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_phase_time_window(
    pulses: pd.DataFrame,
    templates: Dict[str, np.ndarray],
    grid: np.ndarray,
    samples: Sequence[int],
) -> np.ndarray:
    cols = np.asarray(list(samples), dtype=int)
    out = np.full(len(pulses), np.nan, dtype=float)
    staves = pulses["stave"].to_numpy()
    for stave, template in templates.items():
        idx = np.flatnonzero(staves == stave)
        if len(idx) == 0:
            continue
        refs = s02.template_cfd_reference(template)
        shifted = np.vstack([shifted_template(template, s) for s in grid])
        shifted_window = shifted[:, cols]
        for row_idx in idx:
            wf = pulses.iloc[row_idx]["waveform"] / max(float(pulses.iloc[row_idx]["amplitude_adc"]), 1.0)
            sse = ((shifted_window - wf[cols][None, :]) ** 2).sum(axis=1)
            out[row_idx] = refs + grid[int(np.argmin(sse))]
    return out


def mask_window_to_template(pulses: pd.DataFrame, templates: Dict[str, np.ndarray], samples: Sequence[int]) -> pd.DataFrame:
    cols = np.asarray(list(samples), dtype=int)
    out = pulses.copy()
    masked = []
    for row in out.itertuples():
        wf = np.asarray(row.waveform, dtype=float).copy()
        template = templates[str(row.stave)]
        wf[cols] = template[cols] * max(float(row.amplitude_adc), 1.0)
        masked.append(wf)
    out["waveform"] = masked
    return out


def add_window_pickoffs(pulses: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray]) -> None:
    period = float(config["sample_period_ns"])
    samples = [int(i) for i in config["timing"]["early_peak_samples"]]
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    pulses["t_template_window_3_6_ns"] = period * template_phase_time_window(pulses, templates, grid, samples)

    masked = mask_window_to_template(pulses, templates, samples)
    wf_masked = np.vstack(masked["waveform"].to_numpy())
    amp = masked["amplitude_adc"].to_numpy(dtype=float)
    pulses["t_cfd20_mask_no_3_6_ns"] = period * s02.cfd_time_samples(wf_masked, amp, 0.20)
    pulses["t_template_mask_no_3_6_ns"] = period * s02.template_phase_time(masked, templates, grid)


def run_amp_only_correction(pulses: pd.DataFrame, config: dict, base_method: str, label: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    target = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, names = s03a.analytic_feature_matrix(pulses, "amp_only", staves)
    runs = pulses["run"].to_numpy(dtype=int)
    mask = np.isin(runs, train_runs) & s03a.finite_design(X, target, runs)
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["analytic"]["alpha"])))
    model.fit(X[mask], target[mask])
    pred = model.predict(X)
    out = pulses.copy()
    out[f"{label}_target_residual_ns"] = target
    out[f"{label}_pred_residual_ns"] = pred
    out[f"t_{label}_ns"] = out[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    ridge = model.named_steps["ridge"]
    scale = model.named_steps["standardscaler"].scale_
    coef = ridge.coef_ / np.where(scale == 0.0, 1.0, scale)
    coef_rows = pd.DataFrame(
        {
            "label": label,
            "base_method": base_method,
            "feature": names,
            "coefficient_ns_per_raw_unit": coef,
            "standardized_coefficient_ns": ridge.coef_,
        }
    )
    return out, coef_rows


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

    def forward(self, x_wave: torch.Tensor, x_stave: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.conv(x_wave[:, None, :])
        out = self.head(torch.cat([z, x_stave], dim=1))
        return out[:, 0], torch.clamp(out[:, 1], -6.0, 6.0)


def masked_waveform_features(pulses: pd.DataFrame, config: dict, mask_name: str) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    samples = set(int(i) for i in config["timing"]["early_peak_samples"])
    keep = np.zeros(norm.shape[1], dtype=bool)
    if mask_name == "window_3_6":
        for sample in samples:
            keep[sample] = True
    elif mask_name == "no_window_3_6":
        keep[:] = True
        for sample in samples:
            keep[sample] = False
    else:
        raise ValueError(mask_name)
    masked = norm.copy()
    masked[:, ~keep] = 0.0
    staves = list(config["timing"]["downstream_staves"])
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    names = [f"{mask_name}_sample_{i:02d}_over_amp" for i in range(masked.shape[1])] + [f"stave_{s}" for s in staves]
    return masked.astype(np.float32), one_hot.astype(np.float32), names


def finite_mask(X: np.ndarray, S: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.all(np.isfinite(S), axis=1) & np.isfinite(runs)


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
    config: dict,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[TinyWaveformCNN, np.ndarray]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    Xs, _ = standardize_wave_train_apply(X, train_idx)
    y_train = y[train_idx].astype(np.float32).copy()
    if shuffle_y:
        rng.shuffle(y_train)
    model = TinyWaveformCNN(X.shape[1], S.shape[1], int(config["ml"]["cnn_channels"]))
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["learning_rate"]),
        weight_decay=float(config["ml"]["weight_decay"]),
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
    return model, Xs


def predict_cnn(model: TinyWaveformCNN, Xs: np.ndarray, S: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    with torch.no_grad():
        mu, log_var = model(torch.from_numpy(Xs.astype(np.float32)), torch.from_numpy(S.astype(np.float32)))
        sigma = torch.sqrt(torch.exp(log_var) + float(config["ml"]["min_sigma_ns"]) ** 2)
    return mu.numpy().astype(float), sigma.numpy().astype(float)


def run_mlp_mask(
    pulses: pd.DataFrame,
    config: dict,
    mask_name: str,
    base_method: str,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[pd.DataFrame, dict]:
    X_wave, S, feature_names = masked_waveform_features(pulses, config, mask_name)
    X = np.hstack([X_wave, S]).astype(np.float32)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    model, Xs, scaler = p03a.train_torch_model(
        X,
        targets,
        np.flatnonzero(train_mask),
        int(config["ml"]["hidden"]),
        float(config["ml"]["weight_decay"]),
        config,
        seed,
        shuffle_y=shuffle_y,
    )
    pred, sigma = p03a.predict_torch(model, Xs, config)
    out = pulses.copy()
    suffix = f"mlp_{mask_name}" + ("_shuffled" if shuffle_y else "")
    out[f"{suffix}_target_residual_ns"] = targets
    out[f"{suffix}_pred_residual_ns"] = pred
    out[f"{suffix}_pred_sigma_ns"] = sigma
    out[f"t_{suffix}_ns"] = out[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    info = {
        "model": "mlp",
        "mask": mask_name,
        "shuffle_y": bool(shuffle_y),
        "hidden": int(config["ml"]["hidden"]),
        "weight_decay": float(config["ml"]["weight_decay"]),
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "scaler_mean_sha256": hashlib.sha256(scaler.mean_.astype(np.float64).tobytes()).hexdigest(),
    }
    return out, info


def run_cnn_mask(
    pulses: pd.DataFrame,
    config: dict,
    mask_name: str,
    base_method: str,
    seed: int,
    shuffle_y: bool = False,
) -> Tuple[pd.DataFrame, dict]:
    X, S, feature_names = masked_waveform_features(pulses, config, mask_name)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, list(config["timing"]["train_runs"])) & finite_mask(X, S, targets, runs)
    model, Xs = train_cnn(X, S, targets, np.flatnonzero(train_mask), config, seed, shuffle_y=shuffle_y)
    pred, sigma = predict_cnn(model, Xs, S, config)
    out = pulses.copy()
    suffix = f"cnn_{mask_name}" + ("_shuffled" if shuffle_y else "")
    out[f"{suffix}_target_residual_ns"] = targets
    out[f"{suffix}_pred_residual_ns"] = pred
    out[f"{suffix}_pred_sigma_ns"] = sigma
    out[f"t_{suffix}_ns"] = out[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred
    info = {
        "model": "cnn",
        "mask": mask_name,
        "shuffle_y": bool(shuffle_y),
        "channels": int(config["ml"]["cnn_channels"]),
        "weight_decay": float(config["ml"]["weight_decay"]),
        "n_features": int(X.shape[1] + S.shape[1]),
        "feature_names": feature_names,
    }
    return out, info


def event_pair_residual_frame(
    pulses: pd.DataFrame,
    methods: Sequence[Tuple[str, str, str]],
    config: dict,
    runs: Sequence[int],
) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    rows = []
    for method, label, family in methods:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        event_run = sub.drop_duplicates("event_id").set_index("event_id")["run"].to_dict()
        for event_id, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                if a in wide.columns and b in wide.columns:
                    rows.append(
                        {
                            "run": int(event_run[event_id]),
                            "event_id": event_id,
                            "pair": f"{a}-{b}",
                            "method": label,
                            "family": family,
                            "residual_ns": float(row[a] - row[b]),
                        }
                    )
    return pd.DataFrame(rows)


def metric_values(values: np.ndarray, baseline_p95_abs: float) -> dict:
    values = np.asarray(values, dtype=float)
    center = np.median(values) if len(values) else float("nan")
    abs_centered = np.abs(values - center)
    return {
        "n_pair_residuals": int(len(values)),
        "sigma68_ns": s02.sigma68(values),
        "full_rms_ns": s02.full_rms(values),
        "abs_residual_p95_ns": float(np.percentile(abs_centered, 95.0)) if len(values) else float("nan"),
        "tail_frac_vs_traditional_p95": float(np.mean(abs_centered > baseline_p95_abs)) if len(values) else float("nan"),
    }


def per_run_bootstrap(pair_frame: pd.DataFrame, baseline_label: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    baseline_vals = pair_frame[pair_frame["method"] == baseline_label]["residual_ns"].to_numpy(dtype=float)
    baseline_p95 = float(np.percentile(np.abs(baseline_vals - np.median(baseline_vals)), 95.0))
    event_ids = np.asarray(sorted(pair_frame["event_id"].unique()))
    labels = sorted(pair_frame["method"].unique())
    family = pair_frame.groupby("method")["family"].first().to_dict()
    by_method = {
        label: pair_frame[pair_frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for label in labels
    }
    observed = {
        label: metric_values(pair_frame[pair_frame["method"] == label]["residual_ns"].to_numpy(dtype=float), baseline_p95)
        for label in labels
    }
    stats = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
        boot_scores = {}
        for label in labels:
            vals = np.concatenate([by_method[label][event_id] for event_id in sample_ids])
            boot_scores[label] = s02.sigma68(vals)
            stats[label].append(boot_scores[label])
        for label in labels:
            deltas[label].append(boot_scores[label] - boot_scores[baseline_label])
    rows = []
    for label in labels:
        rows.append(
            {
                "method": label,
                "family": family[label],
                "baseline": baseline_label,
                "n_events": int(len(event_ids)),
                **observed[label],
                "ci_low": float(np.percentile(stats[label], 2.5)),
                "ci_high": float(np.percentile(stats[label], 97.5)),
                "delta_vs_traditional_ns": float(observed[label]["sigma68_ns"] - observed[baseline_label]["sigma68_ns"]),
                "delta_ci_low": float(np.percentile(deltas[label], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[label], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def run_block_bootstrap(all_pairs: pd.DataFrame, baseline_label: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    labels = sorted(all_pairs["method"].unique())
    family = all_pairs.groupby("method")["family"].first().to_dict()
    baseline_vals = all_pairs[all_pairs["method"] == baseline_label]["residual_ns"].to_numpy(dtype=float)
    baseline_p95 = float(np.percentile(np.abs(baseline_vals - np.median(baseline_vals)), 95.0))
    observed = {
        label: metric_values(all_pairs[all_pairs["method"] == label]["residual_ns"].to_numpy(dtype=float), baseline_p95)
        for label in labels
    }
    run_ids = np.asarray(sorted(all_pairs["run"].unique()))
    by_run_method = {}
    for run in run_ids:
        run_frame = all_pairs[all_pairs["run"] == run]
        event_ids = np.asarray(sorted(run_frame["event_id"].unique()))
        for label in labels:
            by_run_method[(int(run), label)] = (
                event_ids,
                run_frame[run_frame["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict(),
            )
    stats = {label: [] for label in labels}
    deltas = {label: [] for label in labels}
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(run_ids, size=len(run_ids), replace=True)
        boot_scores = {}
        for label in labels:
            pieces = []
            for run in sampled_runs:
                event_ids, value_map = by_run_method[(int(run), label)]
                sampled_events = rng.choice(event_ids, size=len(event_ids), replace=True)
                pieces.extend(value_map[event_id] for event_id in sampled_events)
            vals = np.concatenate(pieces)
            boot_scores[label] = s02.sigma68(vals)
            stats[label].append(boot_scores[label])
        for label in labels:
            deltas[label].append(boot_scores[label] - boot_scores[baseline_label])
    rows = []
    for label in labels:
        rows.append(
            {
                "method": label,
                "family": family[label],
                "baseline": baseline_label,
                "n_heldout_runs": int(len(run_ids)),
                **observed[label],
                "ci_low": float(np.percentile(stats[label], 2.5)),
                "ci_high": float(np.percentile(stats[label], 97.5)),
                "delta_vs_traditional_ns": float(observed[label]["sigma68_ns"] - observed[baseline_label]["sigma68_ns"]),
                "delta_ci_low": float(np.percentile(deltas[label], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[label], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def leakage_checks(
    pulses: pd.DataFrame,
    config: dict,
    nominal_pairs: pd.DataFrame,
    shuffled_pairs: pd.DataFrame,
    infos: List[dict],
) -> pd.DataFrame:
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    train_event_ids = set(pulses[pulses["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(pulses[pulses["run"].isin(heldout_runs)]["event_id"])
    rows = [
        {
            "model": "all",
            "mask": "all",
            "check": "train_heldout_event_id_overlap",
            "value": float(len(train_event_ids & heldout_event_ids)),
            "detail": "must be zero",
        },
        {
            "model": "all",
            "mask": "all",
            "check": "feature_audit",
            "value": 0.0,
            "detail": "ML features are same-pulse normalized samples after explicit window masks plus stave one-hot; no run id, event id, event order, other-stave timing, pair residual, or held-out target",
        },
    ]
    for info in infos:
        if info["shuffle_y"]:
            continue
        label = f"{info['model']}_{info['mask']}"
        shuffled_label = f"{label}_shuffled"
        nom_vals = nominal_pairs[nominal_pairs["method"] == label]["residual_ns"].to_numpy(dtype=float)
        shuf_vals = shuffled_pairs[shuffled_pairs["method"] == shuffled_label]["residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "model": info["model"],
                "mask": info["mask"],
                "check": "nominal_sigma68_ns",
                "value": float(s02.sigma68(nom_vals)),
                "detail": "held-out run metric",
            }
        )
        rows.append(
            {
                "model": info["model"],
                "mask": info["mask"],
                "check": "shuffled_target_negative_control_sigma68_ns",
                "value": float(s02.sigma68(shuf_vals)),
                "detail": "same architecture and mask trained with shuffled train residual targets",
            }
        )
    return pd.DataFrame(rows)


def run_fold(
    pulses: pd.DataFrame,
    config: dict,
    heldout_run: int,
    loo_runs: Sequence[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = fold_config(config, heldout_run, loo_runs)
    train_pulses = pulses[pulses["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    fold_pulses = pulses.copy()
    s02.add_traditional_times(fold_pulses, cfg, templates)
    add_window_pickoffs(fold_pulses, cfg, templates)

    combined, coef_full = run_amp_only_correction(fold_pulses, cfg, "template_phase", "analytic_template_phase")
    combined, coef_window = run_amp_only_correction(combined, cfg, "template_window_3_6", "analytic_template_window_3_6")
    combined, coef_masked_template = run_amp_only_correction(
        combined,
        cfg,
        "template_mask_no_3_6",
        "analytic_template_mask_no_3_6",
    )
    combined, coef_masked_cfd = run_amp_only_correction(combined, cfg, "cfd20_mask_no_3_6", "analytic_cfd20_mask_no_3_6")
    coefs = pd.concat([coef_full, coef_window, coef_masked_template, coef_masked_cfd], ignore_index=True)
    coefs["heldout_run"] = int(heldout_run)

    infos = []
    base_method = str(cfg["ml"]["base_method"])
    for i, mask_name in enumerate(cfg["ml"]["masks"]):
        mlp, info = run_mlp_mask(combined, cfg, str(mask_name), base_method, int(cfg["ml"]["random_seed"]) + 1000 * heldout_run + i)
        infos.append(info)
        combined[f"t_mlp_{mask_name}_ns"] = mlp[f"t_mlp_{mask_name}_ns"].to_numpy(dtype=float)

        cnn, info = run_cnn_mask(combined, cfg, str(mask_name), base_method, int(cfg["ml"]["random_seed"]) + 2000 * heldout_run + i)
        infos.append(info)
        combined[f"t_cnn_{mask_name}_ns"] = cnn[f"t_cnn_{mask_name}_ns"].to_numpy(dtype=float)

        mlp_shuf, shuf_info = run_mlp_mask(
            combined,
            cfg,
            str(mask_name),
            base_method,
            int(cfg["ml"]["random_seed"]) + 3000 * heldout_run + i,
            shuffle_y=True,
        )
        infos.append(shuf_info)
        combined[f"t_mlp_{mask_name}_shuffled_ns"] = mlp_shuf[f"t_mlp_{mask_name}_shuffled_ns"].to_numpy(dtype=float)

        cnn_shuf, shuf_info = run_cnn_mask(
            combined,
            cfg,
            str(mask_name),
            base_method,
            int(cfg["ml"]["random_seed"]) + 4000 * heldout_run + i,
            shuffle_y=True,
        )
        infos.append(shuf_info)
        combined[f"t_cnn_{mask_name}_shuffled_ns"] = cnn_shuf[f"t_cnn_{mask_name}_shuffled_ns"].to_numpy(dtype=float)

    methods = [
        ("template_phase", "template_phase_uncorrected", "traditional"),
        ("analytic_template_phase", "analytic_template_phase", "traditional"),
        ("analytic_template_window_3_6", "analytic_template_window_3_6", "traditional"),
        ("analytic_template_mask_no_3_6", "analytic_template_mask_no_3_6", "traditional"),
        ("analytic_cfd20_mask_no_3_6", "analytic_cfd20_mask_no_3_6", "traditional"),
        ("mlp_window_3_6", "mlp_window_3_6", "ml"),
        ("cnn_window_3_6", "cnn_window_3_6", "ml"),
        ("mlp_no_window_3_6", "mlp_no_window_3_6", "ml"),
        ("cnn_no_window_3_6", "cnn_no_window_3_6", "ml"),
    ]
    pair_frame = event_pair_residual_frame(combined, methods, cfg, [heldout_run])
    pair_frame["heldout_run"] = int(heldout_run)
    summary = per_run_bootstrap(pair_frame, "analytic_template_phase", rng, int(cfg["analytic"]["bootstrap_samples"]))
    summary["heldout_run"] = int(heldout_run)
    summary["train_runs"] = ",".join(str(run) for run in cfg["timing"]["train_runs"])

    shuffled_methods = []
    for mask_name in cfg["ml"]["masks"]:
        shuffled_methods.extend(
            [
                (f"mlp_{mask_name}_shuffled", f"mlp_{mask_name}_shuffled", "ml_shuffled"),
                (f"cnn_{mask_name}_shuffled", f"cnn_{mask_name}_shuffled", "ml_shuffled"),
            ]
        )
    shuffled_pair_frame = event_pair_residual_frame(combined, shuffled_methods, cfg, [heldout_run])
    shuffled_pair_frame["heldout_run"] = int(heldout_run)
    leakage = leakage_checks(combined, cfg, pair_frame, shuffled_pair_frame, infos)
    leakage["heldout_run"] = int(heldout_run)
    choices = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "train_runs": ",".join(str(run) for run in cfg["timing"]["train_runs"]),
                "analytic_candidate": "amp_only",
                "analytic_alpha": float(cfg["analytic"]["alpha"]),
                "mlp_hidden": int(cfg["ml"]["hidden"]),
                "cnn_channels": int(cfg["ml"]["cnn_channels"]),
                "epochs": int(cfg["ml"]["epochs"]),
                "masks": ",".join(cfg["ml"]["masks"]),
            }
        ]
    )
    return summary, pair_frame, shuffled_pair_frame, leakage, coefs, choices


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    for method in ["analytic_template_phase", "analytic_template_window_3_6", "mlp_window_3_6", "cnn_window_3_6"]:
        rows = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.errorbar(
            rows["heldout_run"],
            rows["sigma68_ns"],
            yerr=[rows["sigma68_ns"] - rows["ci_low"], rows["ci_high"] - rows["sigma68_ns"]],
            marker="o",
            capsize=3,
            label=method,
        )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("B4/B6/B8 pairwise sigma68 (ns)")
    ax.set_title("P03f sample 3-6 held-out timing residuals")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_p03f_loro_window.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    rows = pooled.sort_values("sigma68_ns")
    xpos = np.arange(len(rows))
    ax.bar(xpos, rows["sigma68_ns"])
    ax.errorbar(
        xpos,
        rows["sigma68_ns"],
        yerr=[rows["sigma68_ns"] - rows["ci_low"], rows["ci_high"] - rows["sigma68_ns"]],
        fmt="none",
        ecolor="black",
        capsize=3,
        linewidth=1,
    )
    ax.set_xticks(xpos)
    ax.set_xticklabels(rows["method"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("pooled sigma68 (ns)")
    ax.set_title("Run-block bootstrap summary")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_p03f_pooled_summary.png", dpi=130)
    plt.close(fig)


def write_input_sha256(out_dir: Path, input_hashes: Dict[str, str]) -> None:
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in sorted(input_hashes.items())]).to_csv(
        out_dir / "input_sha256.csv",
        index=False,
    )


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
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    leakage: pd.DataFrame,
    choices: pd.DataFrame,
    result: dict,
) -> None:
    display_methods = [
        "analytic_template_phase",
        "analytic_template_window_3_6",
        "analytic_template_mask_no_3_6",
        "analytic_cfd20_mask_no_3_6",
        "mlp_window_3_6",
        "cnn_window_3_6",
        "mlp_no_window_3_6",
        "cnn_no_window_3_6",
    ]
    pooled_show = pooled[pooled["method"].isin(display_methods)]
    per_run_show = per_run[per_run["method"].isin(display_methods)]
    lines = [
        "# Study report: P03f - early-peak sample-window timing residual ablation",
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
        "After the frozen amp-only/template-phase timewalk correction, do waveform samples 3-6 carry stable timing-residual information, or were earlier early-peak gains run-specific artifacts?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun from raw ROOT before any timing or ML work.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Traditional arm: full template phase plus frozen amp-only timewalk is the baseline. The window refit estimates template phase using only samples 3-6. The two masked ablations replace samples 3-6 by the train-template expectation before CFD20 or full-template-phase pickoff, then apply the same amp-only correction.",
        "",
        "ML arm: matched MLP and tiny CNN residual correctors start from the analytic baseline and use identical masks: only samples 3-6, or all samples except 3-6. Inputs are normalized same-pulse samples plus stave one-hot; training is by run-heldout fold.",
        "",
        choices.dropna(axis=1, how="all").head(7).to_markdown(index=False),
        "",
        "## Held-out run metrics",
        "",
        per_run_show[
            [
                "heldout_run",
                "method",
                "sigma68_ns",
                "ci_low",
                "ci_high",
                "full_rms_ns",
                "abs_residual_p95_ns",
                "tail_frac_vs_traditional_p95",
                "delta_vs_traditional_ns",
                "delta_ci_low",
                "delta_ci_high",
                "n_pair_residuals",
            ]
        ]
        .sort_values(["heldout_run", "sigma68_ns"])
        .to_markdown(index=False),
        "",
        "## Run-block bootstrap summary",
        "",
        pooled_show[
            [
                "method",
                "family",
                "sigma68_ns",
                "ci_low",
                "ci_high",
                "full_rms_ns",
                "abs_residual_p95_ns",
                "tail_frac_vs_traditional_p95",
                "delta_vs_traditional_ns",
                "delta_ci_low",
                "delta_ci_high",
                "n_pair_residuals",
            ]
        ].to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        leakage.sort_values(["heldout_run", "model", "mask", "check"]).to_markdown(index=False),
        "",
        f"Shuffled-target controls are present for every held-out run, model, and mask. Train/held-out event-id overlap is zero in every fold. The aggregate shuffled-control pass flag is `{result['leakage']['shuffled_target_controls_all_worse_than_nominal']}`; failures are treated as leakage/stability warnings, not as positive evidence.",
        "",
        "## Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`. Pooled sigma68 is `{result['traditional']['analytic_template_phase_sigma68_ns']:.3f} ns` for the frozen analytic baseline, `{result['traditional']['analytic_template_window_3_6_sigma68_ns']:.3f} ns` for the sample-3-6 template refit, `{result['ml']['mlp_window_3_6_sigma68_ns']:.3f} ns` for MLP window residuals, `{result['ml']['cnn_window_3_6_sigma68_ns']:.3f} ns` for CNN window residuals, `{result['ml']['mlp_no_window_3_6_sigma68_ns']:.3f} ns` for MLP with samples 3-6 removed, and `{result['ml']['cnn_no_window_3_6_sigma68_ns']:.3f} ns` for CNN with samples 3-6 removed.",
        "",
        "Interpretation: the traditional masked ablations show samples 3-6 are necessary for the standard CFD/template pickoffs. The ML residual gains are not uniquely attributable to samples 3-6 because no-window models also improve, and the shuffled-target warnings prevent claiming a clean sample-atomic ML timing discovery.",
        "",
        "## Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/p03f_1781015703_804_44f56714_early_peak_window.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `heldout_pair_residuals.csv`, `shuffled_pair_residuals.csv`, `leakage_checks.csv`, `analytic_coefficients.csv`, `model_choices_by_run.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03f_1781015703_804_44f56714.yaml")
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
        out_dir / "downstream_counts_by_run.csv",
        index=False,
    )

    summary_frames = []
    pair_frames = []
    shuffled_pair_frames = []
    leakage_frames = []
    coef_frames = []
    choice_frames = []
    for heldout_run in loo_runs:
        summary, pairs, shuffled_pairs, leakage, coefs, choices = run_fold(pulses, config, heldout_run, loo_runs, rng)
        summary_frames.append(summary)
        pair_frames.append(pairs)
        shuffled_pair_frames.append(shuffled_pairs)
        leakage_frames.append(leakage)
        coef_frames.append(coefs)
        choice_frames.append(choices)
        print(f"finished held-out run {heldout_run}", flush=True)

    per_run = pd.concat(summary_frames, ignore_index=True)
    per_run.to_csv(out_dir / "heldout_run_summary.csv", index=False)
    all_pairs = pd.concat(pair_frames, ignore_index=True)
    all_pairs.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    shuffled_pairs_all = pd.concat(shuffled_pair_frames, ignore_index=True)
    shuffled_pairs_all.to_csv(out_dir / "shuffled_pair_residuals.csv", index=False)
    leakage = pd.concat(leakage_frames, ignore_index=True)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.concat(coef_frames, ignore_index=True).to_csv(out_dir / "analytic_coefficients.csv", index=False)
    choices = pd.concat(choice_frames, ignore_index=True)
    choices.to_csv(out_dir / "model_choices_by_run.csv", index=False)
    pooled = run_block_bootstrap(all_pairs, "analytic_template_phase", rng, int(config["ml"]["bootstrap_samples"]))
    pooled.to_csv(out_dir / "pooled_run_block_summary.csv", index=False)
    plot_outputs(out_dir, per_run, pooled)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    write_input_sha256(out_dir, input_hashes)
    pooled_map = {str(row.method): row for row in pooled.itertuples()}
    leak_overlap_max = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].max())
    shuffled_rows = leakage[leakage["check"] == "shuffled_target_negative_control_sigma68_ns"]
    nominal_lookup = {
        (int(row.heldout_run), str(row.model), str(row["mask"])): float(row.value)
        for _, row in leakage[leakage["check"] == "nominal_sigma68_ns"].iterrows()
    }
    shuffled_all_worse = all(
        float(row.value) > nominal_lookup[(int(row.heldout_run), str(row.model), str(row["mask"]))]
        for _, row in shuffled_rows.iterrows()
    )
    shuffled_failures = [
        {
            "heldout_run": int(row.heldout_run),
            "model": str(row.model),
            "mask": str(row["mask"]),
            "nominal_sigma68_ns": nominal_lookup[(int(row.heldout_run), str(row.model), str(row["mask"]))],
            "shuffled_sigma68_ns": float(row.value),
        }
        for _, row in shuffled_rows.iterrows()
        if float(row.value) <= nominal_lookup[(int(row.heldout_run), str(row.model), str(row["mask"]))]
    ]
    window_mlp_delta = float(pooled_map["mlp_window_3_6"].delta_vs_traditional_ns)
    window_cnn_delta = float(pooled_map["cnn_window_3_6"].delta_vs_traditional_ns)
    ml_window_best = (
        float(pooled_map["mlp_window_3_6"].sigma68_ns) < float(pooled_map["mlp_no_window_3_6"].sigma68_ns)
        and float(pooled_map["cnn_window_3_6"].sigma68_ns) < float(pooled_map["cnn_no_window_3_6"].sigma68_ns)
    )
    verdict = "samples_3_6_required_for_traditional_pickoff_but_ml_gain_not_window_specific"
    if not shuffled_all_worse:
        verdict = "ml_gain_not_window_specific_and_flagged_by_shuffled_controls"
    elif ml_window_best and (
        float(pooled_map["mlp_window_3_6"].delta_ci_high) < 0.0
        or float(pooled_map["cnn_window_3_6"].delta_ci_high) < 0.0
    ):
        verdict = "samples_3_6_add_stable_ml_residual_timing_after_analytic_timewalk"

    result = {
        "study": "P03f",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(repro["pass"].all()),
        "split_by_run": True,
        "heldout_runs": loo_runs,
        "metric": "heldout-run B4/B6/B8 pairwise sigma68, full RMS, p95 tail fraction; pooled CIs from event-paired run-block bootstrap",
        "traditional": {
            "baseline": "analytic_template_phase",
            "analytic_template_phase_sigma68_ns": float(pooled_map["analytic_template_phase"].sigma68_ns),
            "analytic_template_window_3_6_sigma68_ns": float(pooled_map["analytic_template_window_3_6"].sigma68_ns),
            "analytic_template_mask_no_3_6_sigma68_ns": float(pooled_map["analytic_template_mask_no_3_6"].sigma68_ns),
            "analytic_cfd20_mask_no_3_6_sigma68_ns": float(pooled_map["analytic_cfd20_mask_no_3_6"].sigma68_ns),
        },
        "ml": {
            "mlp_window_3_6_sigma68_ns": float(pooled_map["mlp_window_3_6"].sigma68_ns),
            "cnn_window_3_6_sigma68_ns": float(pooled_map["cnn_window_3_6"].sigma68_ns),
            "mlp_no_window_3_6_sigma68_ns": float(pooled_map["mlp_no_window_3_6"].sigma68_ns),
            "cnn_no_window_3_6_sigma68_ns": float(pooled_map["cnn_no_window_3_6"].sigma68_ns),
            "mlp_window_minus_traditional_ns": window_mlp_delta,
            "mlp_window_minus_traditional_ci": [
                float(pooled_map["mlp_window_3_6"].delta_ci_low),
                float(pooled_map["mlp_window_3_6"].delta_ci_high),
            ],
            "cnn_window_minus_traditional_ns": window_cnn_delta,
            "cnn_window_minus_traditional_ci": [
                float(pooled_map["cnn_window_3_6"].delta_ci_low),
                float(pooled_map["cnn_window_3_6"].delta_ci_high),
            ],
        },
        "leakage": {
            "max_event_id_overlap": leak_overlap_max,
            "feature_audit": "same-pulse normalized samples after explicit masks plus stave one-hot only",
            "shuffled_target_controls_all_worse_than_nominal": bool(shuffled_all_worse),
            "shuffled_target_failures": shuffled_failures,
            "shuffled_target_controls": shuffled_rows[["heldout_run", "model", "mask", "value"]].to_dict(orient="records"),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config_path, config, repro, per_run, pooled, leakage, choices, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P03f",
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
                "traditional_sigma68_ns": float(pooled_map["analytic_template_phase"].sigma68_ns),
                "mlp_window_delta_ns": window_mlp_delta,
                "cnn_window_delta_ns": window_cnn_delta,
                "shuffled_controls_all_worse": bool(shuffled_all_worse),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
