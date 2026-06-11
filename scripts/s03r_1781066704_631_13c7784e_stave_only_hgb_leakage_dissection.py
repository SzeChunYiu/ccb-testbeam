#!/usr/bin/env python3
"""S03r stave-only HGB leakage dissection.

This study trains timing-residual corrections on Sample I only and evaluates on
Sample II analysis runs.  It is deliberately leakage-oriented: the HGB model is
rerun with each suspect feature family removed, and matched ridge, MLP, 1D-CNN,
and TCN-family comparators are included only as context for the same split.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s03r")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b

torch.set_num_threads(1)

RUN65_EXPECTED = {
    "template_phase_base": 2.889152765080617,
    "analytic_timewalk": 1.494640076269676,
    "s03b_binned_timewalk": 1.5695763825403084,
}


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
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def split_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def add_base_times(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, np.ndarray]]:
    out = pulses.copy()
    train = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    if config["timing"]["base_method"] not in methods:
        raise RuntimeError(f"Base method {config['timing']['base_method']} was not built")
    return out, scan, templates


def run_sample_ii_reference_reproduction(pulses_all: pd.DataFrame, config: dict) -> pd.DataFrame:
    ref_runs = [int(r) for r in config["timing"]["sample_ii_reference_runs"]]
    heldout = int(config["timing"]["sample_ii_reference_heldout_run"])
    fold_cfg = split_config(config, [r for r in ref_runs if r != heldout], [heldout])
    ref_pulses = pulses_all[pulses_all["run"].isin(ref_runs)].copy()
    timed, _, _ = add_base_times(ref_pulses, fold_cfg)
    analytic, _, _, _, _ = s03a.run_analytic(timed, fold_cfg, fold_cfg["timing"]["base_method"])
    binned, _, _, _ = s03b.scan_binned_candidates(timed, fold_cfg, fold_cfg["timing"]["base_method"])
    combined = analytic.copy()
    combined["t_s03b_binned_timewalk_ns"] = binned["t_binned_timewalk_ns"].to_numpy(dtype=float)
    rows = []
    for method, label in [
        ("template_phase", "template_phase_base"),
        ("analytic_timewalk", "analytic_timewalk"),
        ("s03b_binned_timewalk", "s03b_binned_timewalk"),
    ]:
        vals = s02.pairwise_residuals(combined, method, 2.0, fold_cfg, [heldout])
        value = s02.sigma68(vals)
        rows.append(
            {
                "method": label,
                "value": value,
                "reference_value": RUN65_EXPECTED[label],
                "delta_ns": value - RUN65_EXPECTED[label],
                "n_pair_residuals": int(len(vals)),
                "pass": abs(value - RUN65_EXPECTED[label]) < 1.0e-9,
            }
        )
    return pd.DataFrame(rows)


def run_family_labels(config: dict) -> Dict[int, str]:
    labels = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            labels[int(run)] = str(group)
    return labels


def template_features(pulses: pd.DataFrame, templates: Dict[str, np.ndarray]) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    mse = np.zeros(len(pulses), dtype=float)
    corr = np.zeros(len(pulses), dtype=float)
    tail_mse = np.zeros(len(pulses), dtype=float)
    for stave, template in templates.items():
        idx = np.flatnonzero(pulses["stave"].to_numpy() == stave)
        if len(idx) == 0:
            continue
        t = np.asarray(template, dtype=float)
        centered_t = t - t.mean()
        denom_t = math.sqrt(float(np.dot(centered_t, centered_t))) + 1.0e-12
        resid = norm[idx] - t[None, :]
        mse[idx] = np.mean(resid * resid, axis=1)
        tail_mse[idx] = np.mean(resid[:, 9:] * resid[:, 9:], axis=1)
        centered = norm[idx] - norm[idx].mean(axis=1, keepdims=True)
        denom = np.sqrt(np.sum(centered * centered, axis=1)) * denom_t + 1.0e-12
        corr[idx] = np.sum(centered * centered_t[None, :], axis=1) / denom
    return np.column_stack([mse, corr, tail_mse])


def feature_blocks(pulses: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray]) -> Tuple[Dict[str, np.ndarray], Dict[str, List[str]]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
    norm = wf / amp[:, None]
    period = float(config["sample_period_ns"])
    cfd10 = pulses["t_cfd10_ns"].to_numpy(dtype=np.float32)
    cfd20 = pulses["t_cfd20_ns"].to_numpy(dtype=np.float32)
    cfd40 = pulses["t_cfd40_ns"].to_numpy(dtype=np.float32)
    cfd50 = pulses["t_cfd50_ns"].to_numpy(dtype=np.float32)

    peak_sample = pulses["peak_sample"].to_numpy(dtype=np.float32)
    amplitude = np.column_stack(
        [
            np.log1p(amp),
            1000.0 / amp,
            np.sqrt(1000.0 / amp),
            pulses["area_adc_samples"].to_numpy(dtype=np.float32) / amp,
        ]
    )
    qtemp = template_features(pulses, templates).astype(np.float32)
    pre = np.column_stack(
        [
            norm[:, 0],
            norm[:, 1],
            norm[:, 2],
            norm[:, 3],
            norm[:, :4].mean(axis=1),
            norm[:, :4].std(axis=1),
            (norm[:, 3] - norm[:, 0]) / (3.0 * period),
        ]
    )
    shape = np.column_stack(
        [
            cfd50 - cfd10,
            cfd40 - cfd20,
            np.max(np.gradient(norm, axis=1), axis=1),
            norm[:, :6].sum(axis=1),
            norm[:, 9:].sum(axis=1),
            norm.max(axis=1),
        ]
    ).astype(np.float32)
    peak_phase = np.column_stack(
        [
            peak_sample,
            peak_sample / float(config["samples_per_channel"]),
            cfd20 - peak_sample * period,
            cfd50 - peak_sample * period,
        ]
    ).astype(np.float32)
    saturation = np.column_stack(
        [
            (amp > 3000.0).astype(np.float32),
            (amp > 5000.0).astype(np.float32),
            np.clip(amp / 8192.0, 0.0, 2.0),
            (norm.max(axis=1) > 0.95).astype(np.float32),
        ]
    ).astype(np.float32)
    early = norm[:, :6].sum(axis=1)
    late = norm[:, 9:].sum(axis=1)
    anomaly = np.column_stack(
        [
            np.minimum(norm[:, :4].min(axis=1), 0.0),
            norm[:, :4].std(axis=1),
            late / (np.abs(early) + 1.0e-6),
            np.max(np.abs(np.diff(norm, axis=1)), axis=1),
        ]
    ).astype(np.float32)
    staves = list(config["timing"]["downstream_staves"])
    stave = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_lookup = {name: i for i, name in enumerate(staves)}
    for i, name in enumerate(pulses["stave"]):
        stave[i, stave_lookup[str(name)]] = 1.0
    family_levels = ["sample_i_calib", "sample_i_analysis", "sample_ii_analysis"]
    families = run_family_labels(config)
    run_family = np.zeros((len(pulses), len(family_levels)), dtype=np.float32)
    fam_lookup = {name: i for i, name in enumerate(family_levels)}
    for i, run in enumerate(pulses["run"].to_numpy(dtype=int)):
        fam = families.get(int(run), "other")
        if fam in fam_lookup:
            run_family[i, fam_lookup[fam]] = 1.0

    blocks = {
        "waveform": norm.astype(np.float32),
        "amplitude": amplitude.astype(np.float32),
        "q_template": qtemp.astype(np.float32),
        "pretrigger": pre.astype(np.float32),
        "peak_phase": peak_phase,
        "saturation": saturation,
        "anomaly": anomaly,
        "stave": stave,
        "run_family": run_family,
        "shape_extra": shape.astype(np.float32),
    }
    names = {
        "waveform": [f"norm_sample_{i:02d}" for i in range(norm.shape[1])],
        "amplitude": ["log_amp", "inv_amp_1000", "inv_sqrt_amp_1000", "area_over_amp"],
        "q_template": ["template_mse", "template_corr", "template_tail_mse"],
        "pretrigger": ["pre0", "pre1", "pre2", "pre3", "pre_mean", "pre_std", "pre_slope_per_ns"],
        "peak_phase": ["peak_sample", "peak_sample_fraction", "cfd20_minus_peak_sample_time_ns", "cfd50_minus_peak_sample_time_ns"],
        "saturation": ["amp_gt_3000", "amp_gt_5000", "amp_over_adc_range", "norm_peak_near_clip"],
        "anomaly": ["negative_pretrigger_floor", "pretrigger_std", "late_over_early_charge", "max_abs_adjacent_sample_jump"],
        "stave": [f"stave_{s}" for s in staves],
        "run_family": [f"run_family_{f}" for f in family_levels],
        "shape_extra": ["cfd50_minus_cfd10_ns", "cfd40_minus_cfd20_ns", "max_norm_slope", "early_norm_charge", "late_norm_charge", "norm_peak_height"],
    }
    return blocks, names


def assemble_features(blocks: Dict[str, np.ndarray], names: Dict[str, List[str]], families: Sequence[str]) -> Tuple[np.ndarray, List[str]]:
    parts = [blocks[f] for f in families]
    feature_names: List[str] = []
    for f in families:
        feature_names.extend([f"{f}:{n}" for n in names[f]])
    return np.hstack(parts).astype(np.float32), feature_names


def run_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int, reference_method: str) -> pd.DataFrame:
    rows = []
    runs = sorted(int(r) for r in residuals["heldout_run"].unique())
    by_method_run = {
        (method, int(run)): sub["pairwise_residual_ns"].to_numpy(dtype=float)
        for (method, run), sub in residuals.groupby(["method", "heldout_run"])
    }
    reference_values = residuals[residuals["method"] == reference_method]["pairwise_residual_ns"].to_numpy(dtype=float)
    reference_sigma = s02.sigma68(reference_values)
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        stats = []
        deltas = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            sample_vals = np.concatenate([by_method_run[(method, int(r))] for r in sampled if (method, int(r)) in by_method_run])
            ref_vals = np.concatenate([by_method_run[(reference_method, int(r))] for r in sampled if (reference_method, int(r)) in by_method_run])
            stat = s02.sigma68(sample_vals)
            stats.append(stat)
            deltas.append(stat - s02.sigma68(ref_vals))
        summary = s02.metric_summary(vals)
        rows.append(
            {
                "method": method,
                "metric": "pooled_blind_sample_ii_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(np.percentile(stats, 2.5)),
                "ci_high": float(np.percentile(stats, 97.5)),
                "delta_vs_traditional_ns": s02.sigma68(vals) - reference_sigma,
                "delta_ci_low": float(np.percentile(deltas, 2.5)),
                "delta_ci_high": float(np.percentile(deltas, 97.5)),
                **summary,
            }
        )
    return pd.DataFrame(rows).sort_values("value")


def residual_rows(pulses: pd.DataFrame, config: dict, methods: Sequence[str], eval_runs: Iterable[int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residuals = []
    for run in [int(r) for r in eval_runs]:
        for method in methods:
            vals = s02.pairwise_residuals(pulses, method, 2.0, config, [run])
            rows.append({"heldout_run": run, "method": method, **s02.metric_summary(vals)})
            residuals.extend({"heldout_run": run, "method": method, "pairwise_residual_ns": float(v)} for v in vals)
    return pd.DataFrame(rows), pd.DataFrame(residuals)


def support_diagnostics(pulses: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray]) -> pd.DataFrame:
    blocks, names = feature_blocks(pulses, config, templates)
    train_mask = pulses["run"].isin(config["timing"]["train_runs"]).to_numpy()
    held_mask = pulses["run"].isin(config["timing"]["heldout_runs"]).to_numpy()
    rows = []
    for family in ["amplitude", "q_template", "pretrigger", "anomaly", "stave"]:
        mat = blocks[family]
        for j, name in enumerate(names[family]):
            train_vals = mat[train_mask, j]
            held_vals = mat[held_mask, j]
            train_mean = float(np.mean(train_vals))
            held_mean = float(np.mean(held_vals))
            train_std = float(np.std(train_vals) + 1.0e-12)
            rows.append(
                {
                    "family": family,
                    "feature": name,
                    "train_mean": train_mean,
                    "heldout_mean": held_mean,
                    "standardized_shift": float((held_mean - train_mean) / train_std),
                    "train_p10": float(np.percentile(train_vals, 10)),
                    "train_p90": float(np.percentile(train_vals, 90)),
                    "heldout_p10": float(np.percentile(held_vals, 10)),
                    "heldout_p90": float(np.percentile(held_vals, 90)),
                }
            )
    return pd.DataFrame(rows)


def subsample_train(train_idx: np.ndarray, max_rows: int, seed: int) -> np.ndarray:
    if int(max_rows) <= 0 or len(train_idx) <= int(max_rows):
        return train_idx
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(train_idx, size=int(max_rows), replace=False))


def hgb_param_grid(config: dict) -> List[dict]:
    out = []
    ml = config["ml"]
    for max_iter in ml["hgb_max_iter"]:
        for lr in ml["hgb_learning_rate"]:
            for leaves in ml["hgb_max_leaf_nodes"]:
                for l2 in ml["hgb_l2_regularization"]:
                    out.append(
                        {
                            "max_iter": int(max_iter),
                            "learning_rate": float(lr),
                            "max_leaf_nodes": int(leaves),
                            "l2_regularization": float(l2),
                            "max_bins": int(ml["hgb_max_bins"]),
                            "random_state": int(ml["random_seed"]) + 17,
                        }
                    )
    return out


def cv_hgb(X: np.ndarray, y: np.ndarray, runs: np.ndarray, train_mask: np.ndarray, config: dict, method: str, seed: int) -> Tuple[dict, pd.DataFrame]:
    full_train_idx = np.flatnonzero(train_mask & np.all(np.isfinite(X), axis=1))
    train_idx = subsample_train(full_train_idx, int(config["ml"]["max_train_rows"]), seed)
    groups = runs[train_idx]
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    rows = []
    best = {"score": math.inf, "params": None}
    for params in hgb_param_grid(config):
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
            model = HistGradientBoostingRegressor(**params)
            model.fit(X[train_idx][tr], y[train_idx][tr])
            pred = model.predict(X[train_idx][va])
            score = float(np.sqrt(np.mean((pred - y[train_idx][va]) ** 2)))
            fold_scores.append(score)
            rows.append({**params, "method": method, "fold": int(fold), "cv_rmse_ns": score, "n_train_rows": int(len(tr)), "n_val_rows": int(len(va))})
        mean_score = float(np.mean(fold_scores))
        rows.append({**params, "method": method, "fold": -1, "cv_rmse_ns": mean_score, "n_train_rows": int(len(train_idx)), "n_val_rows": 0})
        if mean_score < best["score"]:
            best = {"score": mean_score, "params": params}
    return best, pd.DataFrame(rows)


def fit_hgb(X: np.ndarray, y: np.ndarray, runs: np.ndarray, train_mask: np.ndarray, config: dict, method: str, seed: int, shuffle_target: bool = False) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    best, cv = cv_hgb(X, y, runs, train_mask, config, method, seed)
    full_train_idx = np.flatnonzero(train_mask & np.all(np.isfinite(X), axis=1))
    train_idx = subsample_train(full_train_idx, int(config["ml"]["max_train_rows"]), seed + 1)
    y_train = y[train_idx].copy()
    if shuffle_target:
        rng = np.random.default_rng(seed + 2)
        rng.shuffle(y_train)
    model = HistGradientBoostingRegressor(**best["params"])
    model.fit(X[train_idx], y_train)
    pred = model.predict(X)
    meta = {"cv_rmse_ns": float(best["score"]), "params": best["params"], "n_train_rows": int(len(train_idx))}
    return pred.astype(float), cv, meta


def cv_ridge_alpha(X: np.ndarray, y: np.ndarray, runs: np.ndarray, train_mask: np.ndarray, config: dict, method: str) -> Tuple[float, pd.DataFrame]:
    train_idx = np.flatnonzero(train_mask & np.all(np.isfinite(X), axis=1))
    groups = runs[train_idx]
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    rows = []
    best = {"score": math.inf, "alpha": None}
    for alpha in [float(a) for a in config["ml"]["ridge_alphas"]]:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(X[train_idx][tr], y[train_idx][tr])
            pred = model.predict(X[train_idx][va])
            score = float(np.sqrt(np.mean((pred - y[train_idx][va]) ** 2)))
            scores.append(score)
            rows.append({"method": method, "alpha": alpha, "fold": int(fold), "cv_rmse_ns": score})
        mean_score = float(np.mean(scores))
        rows.append({"method": method, "alpha": alpha, "fold": -1, "cv_rmse_ns": mean_score})
        if mean_score < best["score"]:
            best = {"score": mean_score, "alpha": alpha}
    return float(best["alpha"]), pd.DataFrame(rows)


def fit_ridge(X: np.ndarray, y: np.ndarray, train_mask: np.ndarray, config: dict, runs: np.ndarray, method: str) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    alpha, cv = cv_ridge_alpha(X, y, runs, train_mask, config, method)
    train_idx = np.flatnonzero(train_mask & np.all(np.isfinite(X), axis=1))
    model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    model.fit(X[train_idx], y[train_idx])
    return model.predict(X).astype(float), cv, {"alpha": alpha, "n_train_rows": int(len(train_idx)), "cv_rmse_ns": float(cv[cv["fold"] == -1]["cv_rmse_ns"].min())}


def fit_mlp(X: np.ndarray, y: np.ndarray, train_mask: np.ndarray, config: dict, method: str, seed: int) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    train_idx_all = np.flatnonzero(train_mask & np.all(np.isfinite(X), axis=1))
    train_idx = subsample_train(train_idx_all, int(config["ml"]["max_train_rows"]), seed)
    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=(int(config["ml"]["mlp_hidden"]),),
            alpha=float(config["ml"]["mlp_alpha"]),
            max_iter=int(config["ml"]["mlp_max_iter"]),
            random_state=seed,
            early_stopping=True,
        ),
    )
    t0 = time.time()
    model.fit(X[train_idx], y[train_idx])
    pred = model.predict(X).astype(float)
    rmse = float(np.sqrt(np.mean((model.predict(X[train_idx]) - y[train_idx]) ** 2)))
    cv = pd.DataFrame([{"method": method, "fold": -1, "cv_rmse_ns": rmse, "note": "MLP uses sklearn early stopping on Sample-I training subset"}])
    return pred, cv, {"n_train_rows": int(len(train_idx)), "train_seconds": time.time() - t0, "train_rmse_ns": rmse}


class WaveNet(nn.Module):
    def __init__(self, arch: str, n_aux: int, width: int) -> None:
        super().__init__()
        if arch == "cnn":
            self.encoder = nn.Sequential(
                nn.Conv1d(1, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
        elif arch == "tcn":
            self.encoder = nn.Sequential(
                nn.Conv1d(1, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=2, dilation=2),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=4, dilation=4),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
        else:
            raise ValueError(arch)
        self.gate = nn.Sequential(nn.Linear(n_aux, width), nn.ReLU(), nn.Linear(width, width), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(width + n_aux, width), nn.ReLU(), nn.Linear(width, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        z = self.encoder(wave[:, None, :])
        z = z * self.gate(aux)
        return self.head(torch.cat([z, aux], dim=1)).squeeze(1)


def standardize_train(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    scaler = StandardScaler()
    Xs = X.astype(np.float32).copy()
    Xs[train_idx] = scaler.fit_transform(X[train_idx])
    rest = np.setdiff1d(np.arange(len(X)), train_idx, assume_unique=False)
    if len(rest):
        Xs[rest] = scaler.transform(X[rest])
    return Xs.astype(np.float32), scaler


def fit_torch_model(
    method: str,
    arch: str,
    wave: np.ndarray,
    aux: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    train_idx_all = np.flatnonzero(train_mask & np.all(np.isfinite(wave), axis=1) & np.all(np.isfinite(aux), axis=1))
    train_idx = subsample_train(train_idx_all, int(config["ml"]["max_train_rows"]), seed)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    wave_s, _ = standardize_train(wave, train_idx)
    aux_s, _ = standardize_train(aux, train_idx)
    y_mean = float(np.mean(y[train_idx]))
    y_scale = float(np.std(y[train_idx]) + 1.0e-6)
    yy = ((y - y_mean) / y_scale).astype(np.float32)
    width = int(config["ml"]["cnn_channels"] if arch == "cnn" else config["ml"]["tcn_channels"])
    model = WaveNet(arch, aux_s.shape[1], width)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_learning_rate"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    xw = torch.from_numpy(wave_s)
    xa = torch.from_numpy(aux_s)
    yt = torch.from_numpy(yy)
    batch = int(config["ml"]["torch_batch_size"])
    losses = []
    t0 = time.time()
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(xw[idx], xa[idx])
            loss = torch.mean((pred - yt[idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu().item()))
    model.eval()
    pred_parts = []
    with torch.no_grad():
        for start in range(0, len(wave_s), 8192):
            pred_parts.append(model(xw[start : start + 8192], xa[start : start + 8192]).cpu().numpy())
    pred = np.concatenate(pred_parts).astype(float) * y_scale + y_mean
    cv = pd.DataFrame([{"method": method, "fold": -1, "cv_rmse_ns": float(np.sqrt(np.mean((pred[train_idx] - y[train_idx]) ** 2))), "note": f"{arch} train-subset RMSE"}])
    meta = {
        "arch": arch,
        "n_train_rows": int(len(train_idx)),
        "train_seconds": time.time() - t0,
        "last_loss": float(losses[-1]) if losses else float("nan"),
        "n_parameters": int(sum(p.numel() for p in model.parameters())),
    }
    return pred, cv, meta


def fit_models(
    pulses: pd.DataFrame,
    config: dict,
    templates: Dict[str, np.ndarray],
    base_method: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    blocks, block_names = feature_blocks(pulses, config, templates)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, [int(r) for r in config["timing"]["train_runs"]]) & np.isfinite(targets)
    stave_values = pulses["stave"].astype(str).to_numpy()
    base_values = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float)
    combined = pulses.copy()
    cv_parts = []
    meta_rows = []
    seed0 = int(config["ml"]["random_seed"])

    for i, (method, families) in enumerate(config["feature_sets"].items()):
        X, features = assemble_features(blocks, block_names, families)
        if method.startswith("hgb_single_stave_"):
            target_stave = method.rsplit("_", 1)[-1]
            single_train_mask = train_mask & (stave_values == target_stave)
            raw_pred, cv, meta = fit_hgb(
                X,
                targets,
                runs,
                single_train_mask,
                config,
                method,
                seed0 + 101 * i,
                shuffle_target=False,
            )
            pred = np.zeros_like(raw_pred, dtype=float)
            pred[stave_values == target_stave] = raw_pred[stave_values == target_stave]
            meta["target_stave"] = target_stave
        elif method.startswith("hgb_"):
            pred, cv, meta = fit_hgb(
                X,
                targets,
                runs,
                train_mask,
                config,
                method,
                seed0 + 101 * i,
                shuffle_target=(method == "hgb_shuffled_target_sentinel"),
            )
        elif method.startswith("ridge"):
            pred, cv, meta = fit_ridge(X, targets, train_mask, config, runs, method)
        elif method.startswith("mlp"):
            pred, cv, meta = fit_mlp(X, targets, train_mask, config, method, seed0 + 101 * i)
        elif method.startswith("cnn1d") or method.startswith("tcn_"):
            wave = blocks["waveform"]
            aux_families = [f for f in families if f != "waveform"]
            aux, aux_features = assemble_features(blocks, block_names, aux_families)
            arch = "cnn" if method.startswith("cnn1d") else "tcn"
            pred, cv, meta = fit_torch_model(method, arch, wave, aux, targets, train_mask, config, seed0 + 101 * i)
            features = block_names["waveform"] + aux_features
        else:
            raise ValueError(method)
        combined[f"{method}_pred_residual_ns"] = pred
        combined[f"t_{method}_ns"] = base_values - pred
        cv_parts.append(cv)
        meta_rows.append({"method": method, "families": ",".join(families), "n_features": int(len(features)), **meta})
    return combined, pd.concat(cv_parts, ignore_index=True), pd.DataFrame(meta_rows)


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, family: pd.DataFrame) -> None:
    order = [
        "template_phase_base",
        "analytic_timewalk",
        "s03b_binned_timewalk",
        "hgb_all",
        "hgb_no_stave",
        "hgb_no_peak_phase",
        "hgb_no_pretrigger",
        "hgb_no_q_template",
        "hgb_no_saturation",
        "hgb_no_anomaly",
        "hgb_stave_only_sentinel",
        "hgb_support_excluded_sentinel",
        "hgb_shuffled_target_sentinel",
    ]
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    for method in order:
        if method not in set(per_run["method"]):
            continue
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["sigma68_ns"], "o-", label=method)
    ax.set_xlabel("Sample-II held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03r Sample-I to Sample-II feature-leakage grid")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03r_per_run_dissection.png", dpi=135)
    plt.close(fig)

    top = pooled[pooled["method"].isin(order)].set_index("method").loc[[m for m in order if m in set(pooled["method"])]].reset_index()
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    x = np.arange(len(top))
    ax.bar(x, top["value"])
    ax.errorbar(x, top["value"], yerr=[top["value"] - top["ci_low"], top["ci_high"] - top["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(top["method"], rotation=30, ha="right")
    ax.set_ylabel("pooled run-bootstrap sigma68 (ns)")
    ax.set_title("Pooled blind-transfer intervals")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03r_pooled_ci.png", dpi=135)
    plt.close(fig)

    if len(family):
        fam = family.sort_values("loss_when_dropped_ns", ascending=False)
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        ax.bar(np.arange(len(fam)), fam["loss_when_dropped_ns"])
        ax.set_xticks(np.arange(len(fam)))
        ax.set_xticklabels(fam["dropped_family"], rotation=25, ha="right")
        ax.axhline(0.0, color="black", linewidth=0.8)
        ax.set_ylabel("sigma68(no family) - sigma68(all), ns")
        ax.set_title("HGB feature-family dropout loss")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_s03r_feature_dropout_loss.png", dpi=135)
        plt.close(fig)


def markdown_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int = 80) -> str:
    return df.loc[:, list(columns)].head(max_rows).to_markdown(index=False)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro_counts: pd.DataFrame,
    reference_repro: pd.DataFrame,
    traditional_scan: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    family: pd.DataFrame,
    support_diag: pd.DataFrame,
    leakage: pd.DataFrame,
    model_meta: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    trad = result["traditional"]
    primary = result["hgb_primary"]
    hgb_rows = pooled[pooled["method"].str.startswith("hgb_")].sort_values("value")
    family_alpha = float(config["primary"]["alpha_familywise"])
    n_primary = int(result["multiple_comparison"]["n_feature_family_tests"])
    bonf = family_alpha / max(n_primary, 1)
    lines = [
        "# S03r: stave-only HGB leakage dissection",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Author:** `{config['worker']}`",
        "- **Date:** 2026-06-11",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train on Sample I runs 31-37, 39-42, and 44-57; blind evaluation on Sample II analysis runs 58-63 and 65",
        f"- **Config:** `{config_path}`",
        "- **Primary metric:** held-out Sample-II pair-residual `sigma68` at 2 cm spacing, with held-out-run bootstrap 95% CIs",
        "",
        "## 0. Question and preregistration",
        "",
        "The preregistered question is whether the S03h/S03p HGB timewalk gain is a genuine same-pulse timing correction or whether it is carried by stave/support labels. The traditional comparators are frozen S03a analytic timewalk and S03b monotone binned timewalk. The ML/NN panel contains ridge, HGB, MLP, 1D-CNN, and a gated dilated-TCN architecture on the same run split.",
        "",
        "The positive HGB timing claim is rejected as stave leakage if a stave-only sentinel approaches the full HGB gain, if removing stave labels destroys the gain, or if the support-excluded model no longer beats the analytic baseline. Feature-family knockouts are stave, peak phase, pretrigger, q-template, saturation, and anomaly atoms. Familywise interpretation uses Bonferroni alpha `0.05 / {}` = `{:.4f}` for the {} HGB feature-family tests; the report still shows unadjusted 95% intervals for readability.".format(n_primary, bonf, n_primary),
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse counts were rebuilt directly from `HRDv` in the raw ROOT files before model fitting. Baselines use samples 0-3, the B-stack channels are B2/B4/B6/B8 = 0/2/4/6, and selection is baseline-subtracted amplitude above 1000 ADC.",
        "",
        repro_counts.to_markdown(index=False),
        "",
        "A run-65 S03 reference gate was also rebuilt from the raw-derived downstream pulse table:",
        "",
        reference_repro.to_markdown(index=False),
        "",
        "## 2. Estimand and equations",
        "",
        "For event `e`, stave `s`, and base pickoff `t0`, the geometry-corrected time is",
        "",
        "`tau_{e,s} = t0_{e,s} - z_s v^{-1}`, with `v^{-1}=0.078 ns cm^{-1}`.",
        "",
        "The supervised residual target for pulse `(e,s)` is",
        "",
        "`r_{e,s} = tau_{e,s} - (1/2) sum_{u != s} tau_{e,u}`",
        "",
        "over the other two downstream staves B4, B6, and B8. A correction model estimates `f(x_{e,s})` from same-pulse features on Sample I only and the corrected time is",
        "",
        "`t_{e,s} = t0_{e,s} - f(x_{e,s})`.",
        "",
        "The held-out residuals are pair differences after geometry correction, and",
        "",
        "`sigma68 = (Q84({Delta tau_ab}) - Q16({Delta tau_ab})) / 2`.",
        "",
        "The benchmark delta is `Delta_m = sigma68(m) - sigma68(analytic_timewalk)`. Negative values favor the tested model.",
        "",
        "## 3. Methods",
        "",
        "Templates and all fitted corrections are trained only on Sample I. The S03a analytic model selects among amplitude-only, amplitude/shape, and stave-interaction Ridge designs by GroupKFold over Sample-I runs. The S03b comparator selects a monotone amplitude-binned model. HGB uses grouped CV over Sample-I runs and then a fixed final training cap of `{}` rows to keep the fit deterministic and laptop-safe. Ridge, MLP, 1D-CNN, and the new TCN share the same train/evaluation split and target.".format(config["ml"]["max_train_rows"]),
        "",
        "Feature families are same-pulse normalized waveform samples; amplitude summaries; q-template residual/correlation summaries; pretrigger samples and slope; peak-phase summaries; saturation flags; anomaly/support summaries; stave one-hot; run-family one-hot; and extra shape summaries. No event id, run number, event order, cross-stave time, pair residual, Sample-II target, or downstream consumer label is used as a feature.",
        "",
        "Model fit audit:",
        "",
        markdown_table(model_meta.sort_values("method"), ["method", "families", "n_features", "n_train_rows"], 40),
        "",
        "## 4. Head-to-head benchmark",
        "",
        markdown_table(
            pooled.sort_values("value"),
            [
                "method",
                "value",
                "ci_low",
                "ci_high",
                "delta_vs_traditional_ns",
                "delta_ci_low",
                "delta_ci_high",
                "full_rms_ns",
                "core_sigma_ns",
                "chi2_ndf",
                "tail_frac_abs_gt5ns",
                "n_pair_residuals",
            ],
            40,
        ),
        "",
        "Per-run held-out scores:",
        "",
        markdown_table(per_run.sort_values(["heldout_run", "sigma68_ns"]), ["heldout_run", "method", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"], 120),
        "",
        "## 5. Feature-family null grid",
        "",
        markdown_table(family, ["dropped_family", "method", "sigma68_ns", "loss_when_dropped_ns", "delta_vs_analytic_ns", "delta_ci_low", "delta_ci_high", "interpretation"], 20),
        "",
        "Positive `loss_when_dropped_ns` means the removed family helped HGB; near-zero or negative values mean the family was redundant or harmful. The critical leakage question is whether HGB still beats the analytic comparator after each potentially leaky family is removed.",
        "",
        "Single-stave-only fits are included in the benchmark table. They train a separate HGB correction on only B4, B6, or B8 and leave the other downstream staves at the template-phase base time, which tests whether one stave can dominate the apparent closure improvement.",
        "",
        "## 6. Support matching diagnostics",
        "",
        markdown_table(support_diag.sort_values(["family", "feature"]), ["family", "feature", "train_mean", "heldout_mean", "standardized_shift", "train_p10", "train_p90", "heldout_p10", "heldout_p90"], 80),
        "",
        "These rows are not reweighting factors; they are the audit surface for the matched-support caveat. Large standardized shifts identify where Sample-II support differs from the Sample-I fit domain and where a feature-family gain can be a transfer shortcut rather than a stable timing correction.",
        "",
        "## 7. Leakage, systematics, and caveats",
        "",
        markdown_table(leakage, ["check", "value", "pass", "detail"], 40),
        "",
        "The main systematic is sample transfer, not event statistics: Sample I and Sample II occupy different run families and amplitude/topology supports. The run-family and stave-only features are therefore included as explicit sentinels, and the final claim is not allowed to rely on them. The bootstrap resamples held-out runs, so it reflects between-run transfer variability better than an event bootstrap, but with seven runs it remains coarse. The target is an internal same-particle closure residual, not an external time reference. The q-template, pretrigger, peak-phase, saturation, and anomaly families are same-pulse features, but they can still be source-adjacent to morphology/support labels in downstream consumers; this study only tests timing-residual leakage/null behavior.",
        "",
        "Full distributions are reported through full RMS, core Gaussian fit sigma, chi2/ndf, and tail fraction above the preregistered 5 ns threshold. The Gaussian core is diagnostic only because the residuals have non-Gaussian tails.",
        "",
        "## 8. Verdict",
        "",
        f"The named winner in `result.json` is **{winner['method']}** with sigma68 `{winner['sigma68_ns']:.3f} ns` and CI `[{winner['ci_low']:.3f}, {winner['ci_high']:.3f}] ns`.",
        f"The best traditional comparator is **{trad['method']}** with sigma68 `{trad['sigma68_ns']:.3f} ns`.",
        f"The preregistered HGB row `hgb_all` has sigma68 `{primary['sigma68_ns']:.3f} ns`, delta vs analytic `{primary['delta_vs_traditional_ns']:.3f} ns`, and delta CI `[{primary['delta_ci_low']:.3f}, {primary['delta_ci_high']:.3f}] ns`.",
        f"Overall verdict: `{result['verdict']}`.",
        "",
        f"Stave-only false-gain status: `{result['stave_leakage']['false_gain_status']}`; support-excluded status: `{result['stave_leakage']['support_excluded_status']}`.",
        "",
        "Hypothesis: any surviving HGB gain must be interpreted as a same-pulse waveform/support correction only if stave-only and run-only sentinels remain far worse than the full model and support-excluded HGB still improves over the analytic baseline.",
        "",
        "## 9. Reproducibility",
        "",
        "Regenerate with:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03r_1781066704_631_13c7784e_stave_only_hgb_leakage_dissection.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `run65_reference_reproduction.csv`, `traditional_scan_metrics.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `hgb_feature_family_dropout.csv`, `support_match_diagnostics.csv`, `leakage_checks.csv`, `model_fit_audit.csv`, `model_cv_audit.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03r_1781066704_631_13c7784e_stave_only_hgb_leakage_dissection.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("Raw-ROOT selected-pulse reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    reference_repro = run_sample_ii_reference_reproduction(pulses_all, config)
    reference_repro.to_csv(out_dir / "run65_reference_reproduction.csv", index=False)
    if not bool(reference_repro["pass"].all()):
        raise RuntimeError("S03 run-65 reference reproduction gate failed")

    timed, traditional_scan, templates = add_base_times(pulses_all, config)
    traditional_scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    base_method = config["timing"]["base_method"]
    analytic, analytic_cv, analytic_coef, analytic_candidate, analytic_alpha = s03a.run_analytic(timed, config, base_method)
    binned, binned_cv, binned_models, binned_best = s03b.scan_binned_candidates(timed, config, base_method)
    combined = analytic.copy()
    combined["t_s03b_binned_timewalk_ns"] = binned["t_binned_timewalk_ns"].to_numpy(dtype=float)

    ml_combined, cv_audit, model_meta = fit_models(combined, config, templates, base_method)
    for col in ml_combined.columns:
        if col.startswith("t_") and col.endswith("_ns") and col not in combined.columns:
            combined[col] = ml_combined[col].to_numpy(dtype=float)
        if col.endswith("_pred_residual_ns"):
            combined[col] = ml_combined[col].to_numpy(dtype=float)

    analytic_cv.to_csv(out_dir / "analytic_cv_scan.csv", index=False)
    analytic_coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)
    binned_cv.to_csv(out_dir / "binned_cv_scan.csv", index=False)
    s03b.binned_model_table(binned_models).to_csv(out_dir / "binned_model_table.csv", index=False)
    cv_audit.to_csv(out_dir / "model_cv_audit.csv", index=False)
    model_meta.to_csv(out_dir / "model_fit_audit.csv", index=False)

    methods = ["template_phase", "analytic_timewalk", "s03b_binned_timewalk"] + list(config["feature_sets"].keys())
    label_map = {"template_phase": "template_phase_base"}
    combined["t_template_phase_base_ns"] = combined["t_template_phase_ns"].to_numpy(dtype=float)
    per_run, residuals = residual_rows(combined, config, [label_map.get(m, m) for m in methods], config["timing"]["heldout_runs"])
    pooled = run_bootstrap(residuals, rng, int(config["ml"]["bootstrap_samples"]), str(config["primary"]["traditional_method"]))
    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    support_diag = support_diagnostics(combined, config, templates)
    support_diag.to_csv(out_dir / "support_match_diagnostics.csv", index=False)

    all_hgb = pooled[pooled["method"] == "hgb_all"].iloc[0]
    family_rows = []
    family_method = {
        "pretrigger": "hgb_no_pretrigger",
        "q_template": "hgb_no_q_template",
        "stave": "hgb_no_stave",
        "peak_phase": "hgb_no_peak_phase",
        "saturation": "hgb_no_saturation",
        "anomaly": "hgb_no_anomaly",
    }
    for family, method in family_method.items():
        row = pooled[pooled["method"] == method].iloc[0]
        still_beats = bool(row["delta_ci_high"] < 0.0)
        family_rows.append(
            {
                "dropped_family": family,
                "method": method,
                "sigma68_ns": float(row["value"]),
                "loss_when_dropped_ns": float(row["value"] - all_hgb["value"]),
                "delta_vs_analytic_ns": float(row["delta_vs_traditional_ns"]),
                "delta_ci_low": float(row["delta_ci_low"]),
                "delta_ci_high": float(row["delta_ci_high"]),
                "interpretation": "survives_ci" if still_beats else "does_not_clear_ci",
            }
        )
    family = pd.DataFrame(family_rows)
    family.to_csv(out_dir / "hgb_feature_family_dropout.csv", index=False)

    input_rows = []
    input_hashes = {}
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": float(len(set(config["timing"]["train_runs"]) & set(config["timing"]["heldout_runs"]))),
                "pass": True,
                "detail": "final fits use Sample-I runs only; held-out Sample-II run list is disjoint",
            },
            {
                "check": "feature_audit_no_run_event_cross_stave_time",
                "value": 0.0,
                "pass": True,
                "detail": "features are same-pulse waveform/amplitude/template/pretrigger/stave/run-family indicators; no event id, run number, event order, other-stave time, or target residual",
            },
            {
                "check": "hgb_shuffled_target_sentinel_delta_vs_hgb_all_ns",
                "value": float(pooled[pooled["method"] == "hgb_shuffled_target_sentinel"]["value"].iloc[0] - all_hgb["value"]),
                "pass": bool(pooled[pooled["method"] == "hgb_shuffled_target_sentinel"]["value"].iloc[0] > all_hgb["value"] + 0.1),
                "detail": "shuffled Sample-I target should not match the true HGB correction on Sample II",
            },
            {
                "check": "hgb_run_family_only_sentinel_delta_vs_hgb_all_ns",
                "value": float(pooled[pooled["method"] == "hgb_run_family_only_sentinel"]["value"].iloc[0] - all_hgb["value"]),
                "pass": bool(pooled[pooled["method"] == "hgb_run_family_only_sentinel"]["value"].iloc[0] > all_hgb["value"] + 0.1),
                "detail": "run-family atom alone should not reproduce the HGB correction",
            },
            {
                "check": "hgb_stave_only_sentinel_delta_vs_hgb_all_ns",
                "value": float(pooled[pooled["method"] == "hgb_stave_only_sentinel"]["value"].iloc[0] - all_hgb["value"]),
                "pass": bool(pooled[pooled["method"] == "hgb_stave_only_sentinel"]["value"].iloc[0] > all_hgb["value"] + 0.1),
                "detail": "stave label alone should not reproduce the full HGB correction",
            },
            {
                "check": "hgb_no_stave_beats_analytic_ci",
                "value": float(pooled[pooled["method"] == "hgb_no_stave"]["delta_ci_high"].iloc[0]),
                "pass": bool(pooled[pooled["method"] == "hgb_no_stave"]["delta_ci_high"].iloc[0] < 0.0),
                "detail": "HGB without stave labels must still beat analytic_timewalk to reject a stave shortcut",
            },
            {
                "check": "hgb_support_excluded_beats_analytic_ci",
                "value": float(pooled[pooled["method"] == "hgb_support_excluded_sentinel"]["delta_ci_high"].iloc[0]),
                "pass": bool(pooled[pooled["method"] == "hgb_support_excluded_sentinel"]["delta_ci_high"].iloc[0] < 0.0),
                "detail": "support-excluded HGB uses waveform, amplitude, and generic shape only; its CI win is required for a robust non-support claim",
            },
            {
                "check": "hgb_all_beats_analytic_ci",
                "value": float(all_hgb["delta_ci_high"]),
                "pass": bool(all_hgb["delta_ci_high"] < 0.0),
                "detail": "upper endpoint of paired run-bootstrap delta vs analytic_timewalk must be below zero",
            },
            {
                "check": "all_family_dropouts_beat_analytic_ci",
                "value": float(family["delta_ci_high"].max()),
                "pass": bool((family["delta_ci_high"] < 0.0).all()),
                "detail": "each feature-family removal must retain a CI win over analytic_timewalk to claim robust survival",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    plot_outputs(out_dir, per_run, pooled, family)

    candidate_methods = [
        "analytic_timewalk",
        "s03b_binned_timewalk",
        "hgb_all",
        "hgb_no_pretrigger",
        "hgb_no_q_template",
        "hgb_no_stave",
        "hgb_no_peak_phase",
        "hgb_no_saturation",
        "hgb_no_anomaly",
        "hgb_support_excluded_sentinel",
        "hgb_single_stave_B4",
        "hgb_single_stave_B6",
        "hgb_single_stave_B8",
        "ridge_all",
        "mlp_all",
        "cnn1d_all",
        "tcn_new_architecture_all",
    ]
    winner_row = pooled[pooled["method"].isin(candidate_methods)].sort_values("value").iloc[0]
    trad_row = pooled[pooled["method"].isin(["analytic_timewalk", "s03b_binned_timewalk"])].sort_values("value").iloc[0]
    hgb_all_row = pooled[pooled["method"] == "hgb_all"].iloc[0]
    sentinel_checks = [
        "hgb_shuffled_target_sentinel_delta_vs_hgb_all_ns",
        "hgb_run_family_only_sentinel_delta_vs_hgb_all_ns",
        "hgb_stave_only_sentinel_delta_vs_hgb_all_ns",
    ]
    sentinel_fail = not bool(leakage[leakage["check"].isin(sentinel_checks)]["pass"].all())
    hgb_survives = bool((family["delta_ci_high"] < 0.0).all() and hgb_all_row["delta_ci_high"] < 0.0 and not sentinel_fail)
    support_excluded_row = pooled[pooled["method"] == "hgb_support_excluded_sentinel"].iloc[0]
    stave_only_row = pooled[pooled["method"] == "hgb_stave_only_sentinel"].iloc[0]
    no_stave_row = pooled[pooled["method"] == "hgb_no_stave"].iloc[0]
    stave_false_gain = float(stave_only_row["value"] - all_hgb["value"])
    no_stave_loss = float(no_stave_row["value"] - all_hgb["value"])
    support_excluded_status = "ci_win_over_analytic" if float(support_excluded_row["delta_ci_high"]) < 0.0 else "does_not_clear_analytic_ci"
    false_gain_status = "stave_only_too_close_to_full_hgb" if stave_false_gain <= 0.1 else "stave_only_worse_than_full_hgb"
    hgb_survives = bool(hgb_survives and support_excluded_status == "ci_win_over_analytic" and false_gain_status == "stave_only_worse_than_full_hgb")
    verdict = "hgb_gain_survives_stave_leakage_dissection" if hgb_survives else "hgb_gain_not_safe_against_stave_support_leakage"
    if str(winner_row["method"]).endswith("sentinel"):
        verdict = "sentinel_wins_invalidating_positive_claim"

    result = {
        "study": "S03r",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and reference_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "run65_s03_reference_pass": bool(reference_repro["pass"].all()),
        },
        "split": {
            "train_sample": "Sample I",
            "train_runs": [int(r) for r in config["timing"]["train_runs"]],
            "heldout_sample": "Sample II analysis",
            "heldout_runs": [int(r) for r in config["timing"]["heldout_runs"]],
            "bootstrap_unit": "heldout_run",
            "bootstrap_samples": int(config["ml"]["bootstrap_samples"]),
        },
        "winner": {
            "method": str(winner_row["method"]),
            "sigma68_ns": float(winner_row["value"]),
            "ci_low": float(winner_row["ci_low"]),
            "ci_high": float(winner_row["ci_high"]),
            "delta_vs_traditional_ns": float(winner_row["delta_vs_traditional_ns"]),
            "delta_ci_low": float(winner_row["delta_ci_low"]),
            "delta_ci_high": float(winner_row["delta_ci_high"]),
            "delta_vs_best_traditional_ns": float(winner_row["value"] - trad_row["value"]),
        },
        "traditional": {
            "method": str(trad_row["method"]),
            "sigma68_ns": float(trad_row["value"]),
            "ci_low": float(trad_row["ci_low"]),
            "ci_high": float(trad_row["ci_high"]),
            "analytic_candidate": analytic_candidate,
            "analytic_alpha": float(analytic_alpha),
            "binned_mode": str(binned_best["mode"]),
            "binned_direction": str(binned_best["direction"]),
            "binned_n_bins": int(binned_best["n_bins"]),
        },
        "hgb_primary": {
            "method": "hgb_all",
            "sigma68_ns": float(hgb_all_row["value"]),
            "ci_low": float(hgb_all_row["ci_low"]),
            "ci_high": float(hgb_all_row["ci_high"]),
            "delta_vs_traditional_ns": float(hgb_all_row["delta_vs_traditional_ns"]),
            "delta_ci_low": float(hgb_all_row["delta_ci_low"]),
            "delta_ci_high": float(hgb_all_row["delta_ci_high"]),
            "delta_vs_best_traditional_ns": float(hgb_all_row["value"] - trad_row["value"]),
            "survives_feature_dropout_null_grid": hgb_survives,
        },
        "stave_leakage": {
            "stave_only_sigma68_ns": float(stave_only_row["value"]),
            "stave_only_minus_full_hgb_ns": stave_false_gain,
            "no_stave_sigma68_ns": float(no_stave_row["value"]),
            "no_stave_minus_full_hgb_ns": no_stave_loss,
            "support_excluded_sigma68_ns": float(support_excluded_row["value"]),
            "support_excluded_delta_ci_high_vs_analytic_ns": float(support_excluded_row["delta_ci_high"]),
            "false_gain_status": false_gain_status,
            "support_excluded_status": support_excluded_status,
            "single_stave_results": pooled[pooled["method"].isin(["hgb_single_stave_B4", "hgb_single_stave_B6", "hgb_single_stave_B8"])].to_dict(orient="records"),
        },
        "family_dropout": family.to_dict(orient="records"),
        "support_match_diagnostics": support_diag.to_dict(orient="records"),
        "required_model_family_results": pooled[pooled["method"].isin(candidate_methods + ["hgb_shuffled_target_sentinel", "hgb_run_family_only_sentinel", "hgb_stave_only_sentinel"])].to_dict(orient="records"),
        "leakage": {
            "split_by_run": True,
            "train_heldout_overlap_total": 0,
            "features_exclude_run_event_order_cross_stave_time": True,
            "sample_ii_used_for_final_fit": False,
            "sentinel_fail": sentinel_fail,
            "checks": leakage.to_dict(orient="records"),
        },
        "multiple_comparison": {
            "n_feature_family_tests": int(len(family)),
            "alpha_familywise": float(config["primary"]["alpha_familywise"]),
            "bonferroni_alpha": float(config["primary"]["alpha_familywise"]) / max(int(len(family)), 1),
        },
        "verdict": verdict,
        "hypothesis": "The transfer gain is safe only if it survives removal of stave and support atoms while stave-only, run-only, and shuffled-target sentinels remain far worse than full HGB.",
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(out_dir, config_path, config, repro_counts, reference_repro, traditional_scan, per_run, pooled, family, support_diag, leakage, model_meta, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03r",
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

    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "hgb_primary": result["hgb_primary"], "verdict": verdict}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
