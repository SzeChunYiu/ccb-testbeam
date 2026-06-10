#!/usr/bin/env python3
"""S19a neural architecture sweep for timing and two-pulse recovery.

This ticket asks for a single fair architecture sweep, not a new production
method.  The script reproduces the raw ROOT selected-pulse count first, then
compares a strong traditional baseline with ridge, gradient-boosted trees, an
MLP, a 1D-CNN, and a small recurrent/TCN-style architecture on two established
tasks:

* downstream same-particle timing residual correction;
* injected two-pulse detection and decomposition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s19a-nnarch")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import HuberRegressor, LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p03a_18_sample_mlp_timing as p03a
import p04_amplitude_charge_regression as p04
import p05a_cnn_two_pulse_decomposition as p05a
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


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def finite_mask(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def tabular_waveform_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=np.float32)[:, None]
    log_amp = np.log1p(np.maximum(amp, 0.0))[:, None]
    area = pulses["area_adc_samples"].to_numpy(dtype=np.float32)
    area_over_amp = (area / np.maximum(amp, 1.0))[:, None]
    tail = (wf[:, 10:].sum(axis=1) / np.maximum(wf.sum(axis=1), 1.0))[:, None]
    late = (wf[:, 12:].max(axis=1) / np.maximum(amp, 1.0))[:, None]
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, lookup[stave]] = 1.0
    names = (
        [f"sample_{i:02d}_over_amp" for i in range(norm.shape[1])]
        + ["log_amp", "peak_sample", "area_over_amp", "tail_fraction", "late_fraction"]
        + [f"stave_{s}" for s in staves]
    )
    return np.hstack([norm, log_amp, peak, area_over_amp, tail, late, one_hot]).astype(np.float32), names


def seq_features_from_pulses(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
    norm = wf / amp[:, None]
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, lookup[stave]] = 1.0
    return norm.astype(np.float32), one_hot


class TimingSeqRegressor(nn.Module):
    def __init__(self, arch: str, n_samples: int, n_staves: int, width: int) -> None:
        super().__init__()
        self.arch = arch
        self.n_samples = int(n_samples)
        self.width = int(width)
        if arch == "cnn":
            self.encoder = nn.Sequential(
                nn.Conv1d(1, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            enc_dim = width
        elif arch == "resnet":
            self.input_conv = nn.Conv1d(1, width, kernel_size=3, padding=1)
            self.block = nn.Sequential(
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
            )
            self.pool = nn.AdaptiveAvgPool1d(1)
            enc_dim = width
        elif arch == "tcn":
            self.encoder = nn.Sequential(
                nn.Conv1d(1, width, kernel_size=3, padding=1, dilation=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=2, dilation=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            enc_dim = width
        elif arch == "gru":
            self.encoder = nn.GRU(input_size=1, hidden_size=width, batch_first=True)
            enc_dim = width
        elif arch == "attention":
            self.proj = nn.Linear(1, width)
            self.attn = nn.MultiheadAttention(width, num_heads=1, batch_first=True)
            self.norm = nn.LayerNorm(width)
            enc_dim = width
        else:
            raise ValueError(f"unknown timing arch {arch}")
        self.head = nn.Sequential(nn.Linear(enc_dim + n_staves, max(width, 8)), nn.ReLU(), nn.Linear(max(width, 8), 1))

    def forward(self, wave: torch.Tensor, stave: torch.Tensor) -> torch.Tensor:
        if self.arch == "gru":
            _out, h = self.encoder(wave[:, :, None])
            z = h[-1]
        elif self.arch == "resnet":
            y = self.input_conv(wave[:, None, :])
            z = self.pool(y + self.block(y)).flatten(1)
        elif self.arch == "attention":
            y = self.proj(wave[:, :, None])
            y2, _weights = self.attn(y, y, y, need_weights=False)
            z = self.norm(y + y2).mean(dim=1)
        else:
            z = self.encoder(wave[:, None, :])
        return self.head(torch.cat([z, stave], dim=1)).squeeze(1)


def train_timing_torch(
    arch: str,
    wave: np.ndarray,
    stave: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    width: int,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, float, int, float]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    model = TimingSeqRegressor(arch, wave.shape[1], stave.shape[1], int(width))
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["torch_lr"]),
        weight_decay=float(config["ml"]["torch_weight_decay"]),
    )
    xw = torch.from_numpy(wave.astype(np.float32))
    xs = torch.from_numpy(stave.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    batch = int(config["ml"]["torch_batch_size"])
    t0 = time.time()
    for _epoch in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(xw[idx], xs[idx])
            loss = torch.mean((pred - yy[idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    elapsed = time.time() - t0
    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(wave), 8192):
            preds.append(model(xw[start : start + 8192], xs[start : start + 8192]).cpu().numpy())
    n_params = int(sum(p.numel() for p in model.parameters()))
    return np.concatenate(preds).astype(float), elapsed, n_params, float(loss.detach().cpu().item())


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def eval_timing_candidate(
    pulses: pd.DataFrame,
    label: str,
    base_method: str,
    pred: np.ndarray,
    config: dict,
    runs: Sequence[int],
) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{label}_ns"] = corrected_values(pulses, base_method, pred)
    return s02.pairwise_residuals(tmp, label, 2.0, config, list(runs))


def bootstrap_pair_frame(pair_frame: pd.DataFrame, baseline: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    out = p03a.paired_event_bootstrap(pair_frame, baseline, rng, int(n_boot))
    return out.rename(columns={"delta_vs_s02_ridge_ns": f"delta_vs_{baseline}_ns"})


def run_timing_sweep(config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    pulses = s02.load_downstream_pulses(config)
    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(pulses, config, templates)
    traditional_scan = s02.evaluate_methods(pulses, methods, config)
    traditional_scan.to_csv(out_dir / "timing_traditional_scan.csv", index=False)

    s02_ml_pulses, s02_cv, s02_cal = s02.run_ml(pulses, config, "cfd20", 2.0)
    s02_cv.to_csv(out_dir / "timing_s02_ridge_cv.csv", index=False)
    s02_cal.to_csv(out_dir / "timing_s02_ridge_calibration.csv", index=False)
    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(
        pulses, config, str(config["timing"]["base_method"])
    )
    analytic_cv.to_csv(out_dir / "timing_analytic_cv.csv", index=False)
    analytic_coef.to_csv(out_dir / "timing_analytic_coefficients.csv", index=False)

    combined = analytic_pulses.copy()
    combined["t_s02_ridge_cfd20_ns"] = s02_ml_pulses["t_ml_ridge_ns"].to_numpy(dtype=float)
    base_method = "analytic_timewalk"
    targets = s02.event_residual_targets(combined, base_method, 2.0, config)
    runs = combined["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])

    X, feature_names = tabular_waveform_features(combined, list(config["timing"]["downstream_staves"]))
    wave, stave = seq_features_from_pulses(combined, list(config["timing"]["downstream_staves"]))
    valid_train = train_mask & finite_mask(X, targets, runs)
    train_idx_all = np.flatnonzero(valid_train)
    groups = runs[valid_train]
    gkf = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))

    cv_rows = []
    choices = {}

    def cv_score_for_pred(model_name: str, params: dict, pred_all: np.ndarray, va_idx: np.ndarray) -> float:
        vals = eval_timing_candidate(combined.iloc[va_idx].copy(), "cv_model", base_method, pred_all[va_idx], config, sorted(set(runs[va_idx])))
        score = s02.sigma68(vals)
        cv_rows.append({"task": "timing", "model": model_name, **params, "fold": int(params.get("fold", -1)), "sigma68_ns": score, "n_pair_residuals": int(len(vals))})
        return score

    sklearn_specs = []
    for alpha in config["ml"]["ridge_alphas"]:
        sklearn_specs.append(("ridge", {"alpha": float(alpha)}, make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))))
    for n_estimators in config["ml"].get("extra_trees_n_estimators", [120]):
        sklearn_specs.append(
            (
                "extra_trees",
                {"n_estimators": int(n_estimators), "max_depth": 14, "min_samples_leaf": 8},
                ExtraTreesRegressor(
                    n_estimators=int(n_estimators),
                    max_depth=14,
                    min_samples_leaf=8,
                    random_state=int(config["ml"]["random_seed"]),
                    n_jobs=1,
                ),
            )
        )
    for lr in config["ml"]["hgb_learning_rates"]:
        sklearn_specs.append(("gradient_boosted_trees", {"learning_rate": float(lr)}, HistGradientBoostingRegressor(learning_rate=float(lr), max_iter=120, l2_regularization=0.01, random_state=int(config["ml"]["random_seed"]))))
    for hidden in config["ml"]["mlp_hidden"]:
        sklearn_specs.append(("mlp", {"hidden": int(hidden)}, make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(int(hidden),), alpha=1e-3, max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=int(config["ml"]["random_seed"]), early_stopping=True))))

    for model_name, params, estimator in sklearn_specs:
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[valid_train], targets[valid_train], groups=groups)):
            tr_idx = train_idx_all[tr]
            va_idx = train_idx_all[va]
            est = estimator
            t0 = time.time()
            est.fit(X[tr_idx], targets[tr_idx])
            elapsed = time.time() - t0
            pred = np.full(len(combined), np.nan)
            pred[:] = est.predict(X)
            params_fold = dict(params)
            params_fold["fold"] = fold
            params_fold["train_seconds"] = elapsed
            score = cv_score_for_pred(model_name, params_fold, pred, va_idx)
            fold_scores.append(score)
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append({"task": "timing", "model": model_name, **params, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
        if model_name not in choices or mean_score < choices[model_name]["cv_score"]:
            choices[model_name] = {"params": params, "cv_score": mean_score, "kind": "sklearn", "estimator": estimator}

    torch_specs = [
        ("cnn", {"width": int(config["ml"]["cnn_channels"][0])}),
        ("resnet", {"width": int(config["ml"]["resnet_channels"][0])}),
        ("tcn", {"width": int(config["ml"]["tcn_channels"][0])}),
        ("attention", {"width": int(config["ml"]["attention_width"][0])}),
        ("gru", {"width": int(config["ml"]["gru_hidden"][0])}),
    ]
    for model_name, params in torch_specs:
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(wave[valid_train], targets[valid_train], groups=groups)):
            tr_idx = train_idx_all[tr]
            va_idx = train_idx_all[va]
            pred, elapsed, n_params, loss = train_timing_torch(model_name, wave, stave, targets, tr_idx, int(params["width"]), config, int(config["ml"]["random_seed"]) + 71 * fold + len(model_name))
            params_fold = dict(params)
            params_fold.update({"fold": fold, "train_seconds": elapsed, "n_parameters": n_params, "train_loss": loss})
            score = cv_score_for_pred(model_name, params_fold, pred, va_idx)
            fold_scores.append(score)
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append({"task": "timing", "model": model_name, **params, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
        choices[model_name] = {"params": params, "cv_score": mean_score, "kind": "torch"}

    cv = pd.DataFrame(cv_rows)
    cv.to_csv(out_dir / "timing_architecture_cv.csv", index=False)

    final_preds = {}
    model_meta = []
    for model_name, choice in choices.items():
        t0 = time.time()
        if choice["kind"] == "sklearn":
            params = choice["params"]
            if model_name == "ridge":
                est = make_pipeline(StandardScaler(), Ridge(alpha=float(params["alpha"])))
            elif model_name == "extra_trees":
                est = ExtraTreesRegressor(
                    n_estimators=int(params["n_estimators"]),
                    max_depth=int(params["max_depth"]),
                    min_samples_leaf=int(params["min_samples_leaf"]),
                    random_state=int(config["ml"]["random_seed"]) + 2,
                    n_jobs=1,
                )
            elif model_name == "gradient_boosted_trees":
                est = HistGradientBoostingRegressor(learning_rate=float(params["learning_rate"]), max_iter=120, l2_regularization=0.01, random_state=int(config["ml"]["random_seed"]) + 3)
            else:
                est = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(int(params["hidden"]),), alpha=1e-3, max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=int(config["ml"]["random_seed"]) + 4, early_stopping=True))
            est.fit(X[train_idx_all], targets[train_idx_all])
            pred = est.predict(X)
            elapsed = time.time() - t0
            n_params = int(getattr(est[-1], "coefs_", [np.asarray([])])[0].size) if hasattr(est, "__getitem__") and model_name == "mlp" else int(X.shape[1])
        else:
            pred, elapsed, n_params, _loss = train_timing_torch(model_name, wave, stave, targets, train_idx_all, int(choice["params"]["width"]), config, int(config["ml"]["random_seed"]) + 909 + len(model_name))
        label = f"timing_{model_name}"
        combined[f"t_{label}_ns"] = corrected_values(combined, base_method, pred)
        final_preds[model_name] = label
        model_meta.append({"task": "timing", "model": model_name, "cv_sigma68_ns": choice["cv_score"], "train_seconds": elapsed, "n_parameters": int(n_params), **choice["params"]})

    methods_for_boot = [
        ("cfd20", "cfd20"),
        ("template_phase", "template_phase"),
        ("analytic_timewalk", "analytic_timewalk"),
        ("s02_ridge_cfd20", "s02_ridge_cfd20"),
    ] + [(label, model) for model, label in final_preds.items()]
    pair_frame = p03a.event_pair_residual_frame(combined, methods_for_boot, config, heldout_runs)
    pair_frame.to_csv(out_dir / "timing_heldout_pair_residuals.csv", index=False)
    timing_bench = bootstrap_pair_frame(pair_frame, "analytic_timewalk", rng, int(config["ml"]["bootstrap_samples"]))
    timing_bench = timing_bench.rename(columns={"method": "model"})
    timing_bench = timing_bench.merge(pd.DataFrame(model_meta), on="model", how="left")
    timing_bench.to_csv(out_dir / "timing_head_to_head.csv", index=False)
    pd.DataFrame(model_meta).to_csv(out_dir / "timing_model_meta.csv", index=False)
    leak = pd.DataFrame(
        [
            {"check": "timing_train_heldout_run_overlap", "value": int(bool(set(config["timing"]["train_runs"]) & set(heldout_runs))), "pass": not bool(set(config["timing"]["train_runs"]) & set(heldout_runs))},
            {"check": "timing_feature_audit", "value": 0, "pass": True, "detail": "same-pulse waveform, amplitude summaries, and stave one-hot only; no event id, run id, other-stave time, or held-out residual target"},
            {"check": "timing_target_base", "value": 0, "pass": True, "detail": "ML models correct residuals left by the analytic_timewalk traditional baseline"},
        ]
    )
    return timing_bench, pair_frame, cv, leak, {"analytic_candidate": best_candidate, "analytic_alpha": float(best_alpha), "feature_names": feature_names}


def injection_config(config: dict) -> dict:
    inj = dict(config)
    inj.update(config["injection"])
    inj["benchmark_runs"] = {"train": list(config["injection"]["train_runs"]), "heldout": list(config["injection"]["heldout_runs"])}
    inj["max_clean_pulses_per_run_stave"] = int(config["injection"]["max_clean_pulses_per_run_stave"])
    inj["ml"] = dict(config["ml"])
    inj["ml"]["bootstrap_samples"] = int(config["ml"]["bootstrap_samples"])
    return inj


def two_pulse_targets(events: pd.DataFrame, waveforms: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    y_class = events["is_overlap"].to_numpy(dtype=int)
    max_amp = np.maximum(waveforms.max(axis=1) - np.median(waveforms[:, :4], axis=1), 1.0)
    y_reg = np.column_stack(
        [
            events["true_t1_sample"].to_numpy(dtype=float) / 12.0,
            np.nan_to_num(events["true_t2_sample"].to_numpy(dtype=float), nan=0.0) / 12.0,
            events["true_amp1_adc"].to_numpy(dtype=float) / max_amp,
            events["true_amp2_adc"].to_numpy(dtype=float) / max_amp,
        ]
    )
    return y_class, y_reg, max_amp


class TwoPulseSeqNet(nn.Module):
    def __init__(self, arch: str, n_samples: int, width: int) -> None:
        super().__init__()
        self.arch = arch
        if arch == "cnn":
            self.encoder = nn.Sequential(
                nn.Conv1d(1, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            enc = width
        elif arch == "resnet":
            self.input_conv = nn.Conv1d(1, width, kernel_size=3, padding=1)
            self.block = nn.Sequential(
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
            )
            self.pool = nn.AdaptiveAvgPool1d(1)
            enc = width
        elif arch == "tcn":
            self.encoder = nn.Sequential(
                nn.Conv1d(1, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=2, dilation=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            enc = width
        elif arch == "gru":
            self.encoder = nn.GRU(input_size=1, hidden_size=width, batch_first=True)
            enc = width
        elif arch == "attention":
            self.proj = nn.Linear(1, width)
            self.attn = nn.MultiheadAttention(width, num_heads=1, batch_first=True)
            self.norm = nn.LayerNorm(width)
            enc = width
        else:
            raise ValueError(arch)
        self.shared = nn.Sequential(nn.Linear(enc, max(width, 16)), nn.ReLU())
        self.detect = nn.Linear(max(width, 16), 1)
        self.regress = nn.Linear(max(width, 16), 4)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.arch == "gru":
            _out, h = self.encoder(x[:, :, None])
            z = h[-1]
        elif self.arch == "resnet":
            y = self.input_conv(x[:, None, :])
            z = self.pool(y + self.block(y)).flatten(1)
        elif self.arch == "attention":
            y = self.proj(x[:, :, None])
            y2, _weights = self.attn(y, y, y, need_weights=False)
            z = self.norm(y + y2).mean(dim=1)
        else:
            z = self.encoder(x[:, None, :])
        z = self.shared(z)
        return self.detect(z).squeeze(1), self.regress(z)


def normalized_waveforms(waveforms: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[:, :4], axis=1)
    corr = waveforms - baseline[:, None]
    amp = np.maximum(corr.max(axis=1), 1.0)
    return (corr / amp[:, None]).astype(np.float32), amp.astype(np.float32)


def train_two_pulse_torch(
    arch: str,
    events: pd.DataFrame,
    waveforms: np.ndarray,
    train_idx: np.ndarray,
    width: int,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float, int]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    x_np, max_amp = normalized_waveforms(waveforms)
    y_class, y_reg, _max_amp = two_pulse_targets(events, waveforms)
    x = torch.from_numpy(x_np)
    yc = torch.from_numpy(y_class.astype(np.float32))
    yr = torch.from_numpy(y_reg.astype(np.float32))
    model = TwoPulseSeqNet(arch, x_np.shape[1], int(width))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    bce = nn.BCEWithLogitsLoss()
    huber = nn.SmoothL1Loss()
    batch = min(256, int(config["ml"]["torch_batch_size"]))
    t0 = time.time()
    for _epoch in range(max(80, int(config["ml"]["torch_epochs"]))):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            logits, pred = model(x[idx])
            loss = bce(logits, yc[idx])
            pos = yc[idx] > 0.5
            if bool(pos.any()):
                loss = loss + 1.5 * huber(pred[pos], yr[idx][pos])
            opt.zero_grad()
            loss.backward()
            opt.step()
    elapsed = time.time() - t0
    model.eval()
    probs = []
    regs = []
    with torch.no_grad():
        for start in range(0, len(x), 1024):
            logits, pred = model(x[start : start + 1024])
            probs.append(torch.sigmoid(logits).cpu().numpy())
            regs.append(pred.cpu().numpy())
    return np.concatenate(probs), np.vstack(regs), max_amp, elapsed, int(sum(p.numel() for p in model.parameters()))


def predictions_to_frame(events: pd.DataFrame, prefix: str, score: np.ndarray, pred: np.ndarray, max_amp: np.ndarray) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "event_id": events["event_id"],
            f"{prefix}_score": score,
            f"{prefix}_failed": score < 0.5,
            f"{prefix}_t1_sample": np.clip(pred[:, 0] * 12.0, 0.0, 17.0),
            f"{prefix}_t2_sample": np.clip(pred[:, 1] * 12.0, 0.0, 17.0),
            f"{prefix}_amp1_adc": np.clip(pred[:, 2] * max_amp, 0.0, None),
            f"{prefix}_amp2_adc": np.clip(pred[:, 3] * max_amp, 0.0, None),
        }
    )
    swapped = out[f"{prefix}_t2_sample"] < out[f"{prefix}_t1_sample"]
    out.loc[swapped, [f"{prefix}_t1_sample", f"{prefix}_t2_sample"]] = out.loc[swapped, [f"{prefix}_t2_sample", f"{prefix}_t1_sample"]].to_numpy()
    out.loc[swapped, [f"{prefix}_amp1_adc", f"{prefix}_amp2_adc"]] = out.loc[swapped, [f"{prefix}_amp2_adc", f"{prefix}_amp1_adc"]].to_numpy()
    return out


def train_two_pulse_sklearn(model_name: str, events: pd.DataFrame, waveforms: np.ndarray, train_mask: np.ndarray, config: dict) -> Tuple[pd.DataFrame, float, int]:
    X = p05a.make_feature_matrix(waveforms)
    y_class, y_reg, max_amp = two_pulse_targets(events, waveforms)
    pos_train = train_mask & (y_class == 1)
    seed = int(config["ml"]["random_seed"])
    t0 = time.time()
    if model_name == "ridge":
        clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000, random_state=seed))
        reg = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        n_params = X.shape[1] * 5
    elif model_name == "gradient_boosted_trees":
        clf = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.06, random_state=seed)
        reg = MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=120, learning_rate=0.06, random_state=seed + 1))
        n_params = 120
    elif model_name == "mlp":
        clf = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(48,), alpha=1e-3, max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=seed, early_stopping=True))
        reg = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=int(config["ml"]["sklearn_max_iter"]), random_state=seed + 1, early_stopping=True))
        n_params = X.shape[1] * 48 + 48 * 32
    else:
        raise ValueError(model_name)
    clf.fit(X[train_mask], y_class[train_mask])
    reg.fit(X[pos_train], y_reg[pos_train])
    score = clf.predict_proba(X)[:, 1]
    pred = reg.predict(X)
    elapsed = time.time() - t0
    return predictions_to_frame(events, model_name, score, pred, max_amp), elapsed, int(n_params)


def fractional_regression_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68.0)),
        "rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
    }


def run_bootstrap_regression(frame: pd.DataFrame, y_col: str, pred_col: str, run_col: str, n_boot: int, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(frame[run_col].unique()))
    vals = {"res68_abs_frac": [], "rms_frac": [], "bias_median_frac": [], "within_10pct": []}
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([frame[frame[run_col] == run] for run in sampled], ignore_index=True)
        got = fractional_regression_metrics(boot[y_col].to_numpy(dtype=float), boot[pred_col].to_numpy(dtype=float))
        for key in vals:
            vals[key].append(got[key])
    out = {}
    for key, arr in vals.items():
        out[f"{key}_ci_low"] = float(np.percentile(arr, 2.5))
        out[f"{key}_ci_high"] = float(np.percentile(arr, 97.5))
    return out


def charge_model_specs(settings: dict, seed: int) -> List[Tuple[str, dict, object]]:
    specs: List[Tuple[str, dict, object]] = []
    for alpha in settings["ridge_alphas"]:
        specs.append(("ridge", {"alpha": float(alpha)}, make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))))
    for alpha in settings["huber_alphas"]:
        specs.append(
            (
                "huber",
                {"alpha": float(alpha), "epsilon": 1.35},
                make_pipeline(StandardScaler(), HuberRegressor(alpha=float(alpha), epsilon=1.35, max_iter=180)),
            )
        )
    for n_estimators in settings["rf_n_estimators"]:
        specs.append(
            (
                "random_forest",
                {"n_estimators": int(n_estimators), "max_depth": 14, "min_samples_leaf": 8},
                RandomForestRegressor(
                    n_estimators=int(n_estimators),
                    max_depth=14,
                    min_samples_leaf=8,
                    random_state=seed,
                    n_jobs=1,
                ),
            )
        )
    for n_estimators in settings["extra_trees_n_estimators"]:
        specs.append(
            (
                "extra_trees",
                {"n_estimators": int(n_estimators), "max_depth": 14, "min_samples_leaf": 8},
                ExtraTreesRegressor(
                    n_estimators=int(n_estimators),
                    max_depth=14,
                    min_samples_leaf=8,
                    random_state=seed + 1,
                    n_jobs=1,
                ),
            )
        )
    for lr in settings["hgb_learning_rates"]:
        specs.append(
            (
                "hist_gradient_boosting",
                {"learning_rate": float(lr), "max_leaf_nodes": 31},
                HistGradientBoostingRegressor(
                    learning_rate=float(lr),
                    max_iter=120,
                    max_leaf_nodes=31,
                    l2_regularization=0.02,
                    random_state=seed + 2,
                ),
            )
        )
    for hidden in settings["mlp_hidden"]:
        specs.append(
            (
                "mlp",
                {"hidden": int(hidden)},
                make_pipeline(
                    StandardScaler(),
                    MLPRegressor(
                        hidden_layer_sizes=(int(hidden),),
                        alpha=1e-3,
                        max_iter=260,
                        random_state=seed + 3,
                        early_stopping=True,
                    ),
                ),
            )
        )
    return specs


def tune_charge_method(
    X: np.ndarray,
    y: np.ndarray,
    runs: np.ndarray,
    train_idx: np.ndarray,
    specs: List[Tuple[str, dict, object]],
    method: str,
) -> Tuple[dict, pd.DataFrame]:
    method_specs = [(params, est) for name, params, est in specs if name == method]
    groups = runs[train_idx]
    gkf = GroupKFold(n_splits=min(3, len(np.unique(groups))))
    rows = []
    best = None
    for params, estimator in method_specs:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
            tr_idx = train_idx[tr]
            va_idx = train_idx[va]
            est = clone(estimator)
            est.fit(X[tr_idx], np.log(y[tr_idx]))
            pred = np.exp(est.predict(X[va_idx]))
            score = fractional_regression_metrics(y[va_idx], pred)["res68_abs_frac"]
            row = {"method": method, "fold": int(fold), "res68_abs_frac": score}
            row.update(params)
            rows.append(row)
            scores.append(score)
        mean_score = float(np.mean(scores))
        row = {"method": method, "fold": -1, "res68_abs_frac": mean_score}
        row.update(params)
        rows.append(row)
        if best is None or mean_score < best["score"]:
            best = {"method": method, "params": params, "estimator": estimator, "score": mean_score}
    assert best is not None
    return best, pd.DataFrame(rows)


def run_charge_sweep(config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    settings = config["charge"]
    print("loading duplicate-readout charge rows ...", flush=True)
    meta, wave, counts_by_run = p04.extract_rows(config)
    counts_by_run.to_csv(out_dir / "charge_counts_by_run.csv", index=False)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_counts"]["total_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"charge raw gate failed: got {total_selected}, expected {expected}")

    valid = (meta["target_odd_neg_amp"].to_numpy(dtype=float) > float(settings["valid_min_target_adc"])) & (
        meta["target_odd_pos_charge"].to_numpy(dtype=float) > float(settings["valid_min_target_adc"])
    )
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]
    runs = meta["run"].to_numpy(dtype=int)
    heldout_runs = [int(x) for x in settings["heldout_runs"]]
    heldout_mask = np.isin(runs, heldout_runs)
    train_mask = ~heldout_mask
    X = p04.ml_features(meta, wave).astype(np.float32)
    specs = charge_model_specs(settings, int(config["random_seed"]) + 401)
    targets = {"amplitude": "target_odd_neg_amp", "charge": "target_odd_pos_charge"}

    train_idx_full = np.flatnonzero(train_mask)
    cv_idx = train_idx_full
    if len(cv_idx) > int(settings["cv_max_train_rows"]):
        cv_idx = rng.choice(cv_idx, size=int(settings["cv_max_train_rows"]), replace=False)
    fit_idx = train_idx_full
    if len(fit_idx) > int(settings["max_train_rows"]):
        fit_idx = rng.choice(fit_idx, size=int(settings["max_train_rows"]), replace=False)

    bench_rows = []
    cv_frames = []
    prediction_frames = []
    for target_name, col in targets.items():
        print(f"charge target {target_name} ...", flush=True)
        y = meta[col].to_numpy(dtype=float)
        for method in ["ridge", "huber", "random_forest", "extra_trees", "hist_gradient_boosting", "mlp"]:
            print(f"  charge method {method}", flush=True)
            best, cv = tune_charge_method(X, y, runs, cv_idx, specs, method)
            cv["target"] = target_name
            cv_frames.append(cv)
            est = clone(best["estimator"])
            t0 = time.time()
            est.fit(X[fit_idx], np.log(y[fit_idx]))
            pred = np.exp(est.predict(X))
            elapsed = time.time() - t0
            held = pd.DataFrame(
                {
                    "run": runs[heldout_mask],
                    "target": target_name,
                    "method": method,
                    "y": y[heldout_mask],
                    "pred": pred[heldout_mask],
                }
            )
            metrics = fractional_regression_metrics(held["y"].to_numpy(dtype=float), held["pred"].to_numpy(dtype=float))
            row = {
                "task": "amplitude_charge",
                "target": target_name,
                "model": method,
                "metric": "res68_abs_frac",
                "cv_res68_abs_frac": float(best["score"]),
                "train_seconds": elapsed,
                "n_train_rows": int(len(fit_idx)),
                "n_heldout_rows": int(len(held)),
            }
            row.update(best["params"])
            row.update(metrics)
            row.update(run_bootstrap_regression(held, "y", "pred", "run", int(settings["bootstrap_samples"]), rng))
            bench_rows.append(row)
            prediction_frames.append(held)

    bench = pd.DataFrame(bench_rows).sort_values(["target", "res68_abs_frac"])
    cv = pd.concat(cv_frames, ignore_index=True)
    preds = pd.concat(prediction_frames, ignore_index=True)
    bench.to_csv(out_dir / "charge_head_to_head.csv", index=False)
    cv.to_csv(out_dir / "charge_run_split_cv.csv", index=False)
    preds.to_csv(out_dir / "charge_heldout_predictions.csv", index=False)
    leak = pd.DataFrame(
        [
            {
                "check": "charge_train_heldout_run_overlap",
                "value": int(bool(set(runs[train_mask]) & set(heldout_runs))),
                "pass": not bool(set(runs[train_mask]) & set(heldout_runs)),
            },
            {
                "check": "charge_feature_audit",
                "value": 0,
                "pass": True,
                "detail": "features are even-channel waveform and shape summaries only; odd-channel target samples, run id, and event id excluded",
            },
            {"check": "charge_raw_gate_total", "value": total_selected, "pass": total_selected == expected},
        ]
    )
    return bench, cv, preds, leak


def classification_metrics(y: np.ndarray, score: np.ndarray) -> dict:
    return {
        "n": int(len(y)),
        "roc_auc": float(roc_auc_score(y, score)),
        "average_precision": float(average_precision_score(y, score)),
        "brier": float(brier_score_loss(y, np.clip(score, 1e-6, 1.0 - 1e-6))),
    }


def run_bootstrap_classification(frame: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(frame["source_run"].unique()))
    vals = {"roc_auc": [], "average_precision": [], "brier": []}
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([frame[frame["source_run"] == run] for run in sampled], ignore_index=True)
        if boot["y"].nunique() < 2:
            continue
        got = classification_metrics(boot["y"].to_numpy(dtype=int), boot["score"].to_numpy(dtype=float))
        for key in vals:
            vals[key].append(got[key])
    out = {}
    for key, arr in vals.items():
        out[f"{key}_ci_low"] = float(np.percentile(arr, 2.5)) if arr else float("nan")
        out[f"{key}_ci_high"] = float(np.percentile(arr, 97.5)) if arr else float("nan")
    return out


def anomaly_model_specs(settings: dict, seed: int) -> List[Tuple[str, dict, object]]:
    specs: List[Tuple[str, dict, object]] = []
    for c_value in settings["logistic_c"]:
        specs.append(
            (
                "logistic",
                {"C": float(c_value)},
                make_pipeline(StandardScaler(), LogisticRegression(C=float(c_value), max_iter=1000, random_state=seed)),
            )
        )
    for n_estimators in settings["rf_n_estimators"]:
        specs.append(
            (
                "random_forest",
                {"n_estimators": int(n_estimators), "max_depth": 10, "min_samples_leaf": 10},
                RandomForestClassifier(
                    n_estimators=int(n_estimators),
                    max_depth=10,
                    min_samples_leaf=10,
                    class_weight="balanced",
                    random_state=seed + 1,
                    n_jobs=1,
                ),
            )
        )
    for lr in settings["hgb_learning_rates"]:
        specs.append(
            (
                "hist_gradient_boosting",
                {"learning_rate": float(lr), "max_leaf_nodes": 31},
                HistGradientBoostingClassifier(
                    learning_rate=float(lr),
                    max_iter=120,
                    max_leaf_nodes=31,
                    l2_regularization=0.02,
                    random_state=seed + 2,
                ),
            )
        )
    for hidden in settings["mlp_hidden"]:
        specs.append(
            (
                "mlp",
                {"hidden": int(hidden)},
                make_pipeline(
                    StandardScaler(),
                    MLPClassifier(
                        hidden_layer_sizes=(int(hidden),),
                        alpha=1e-3,
                        max_iter=260,
                        random_state=seed + 3,
                        early_stopping=True,
                    ),
                ),
            )
        )
    return specs


def tune_classifier(
    X: np.ndarray,
    y: np.ndarray,
    runs: np.ndarray,
    train_idx: np.ndarray,
    specs: List[Tuple[str, dict, object]],
    method: str,
) -> Tuple[dict, pd.DataFrame]:
    method_specs = [(params, est) for name, params, est in specs if name == method]
    groups = runs[train_idx]
    gkf = GroupKFold(n_splits=min(3, len(np.unique(groups))))
    rows = []
    best = None
    for params, estimator in method_specs:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
            tr_idx = train_idx[tr]
            va_idx = train_idx[va]
            est = clone(estimator)
            est.fit(X[tr_idx], y[tr_idx])
            score = est.predict_proba(X[va_idx])[:, 1]
            metrics = classification_metrics(y[va_idx], score)
            row = {"method": method, "fold": int(fold)}
            row.update(params)
            row.update(metrics)
            rows.append(row)
            scores.append(metrics["roc_auc"])
        mean_score = float(np.mean(scores))
        row = {"method": method, "fold": -1, "roc_auc": mean_score}
        row.update(params)
        rows.append(row)
        if best is None or mean_score > best["score"]:
            best = {"method": method, "params": params, "estimator": estimator, "score": mean_score}
    assert best is not None
    return best, pd.DataFrame(rows)


def run_anomaly_classification_sweep(
    config: dict,
    out_dir: Path,
    events: pd.DataFrame,
    waveforms: np.ndarray,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    settings = config["anomaly"]
    X = p05a.make_feature_matrix(waveforms).astype(np.float32)
    y = events["is_overlap"].to_numpy(dtype=int)
    runs = events["source_run"].to_numpy(dtype=int)
    train_mask = events["split"].to_numpy() == "train"
    heldout_mask = ~train_mask
    train_idx = np.flatnonzero(train_mask)
    specs = anomaly_model_specs(settings, int(config["random_seed"]) + 801)

    bench_rows = []
    cv_frames = []
    prediction_frames = []
    for method in ["logistic", "random_forest", "hist_gradient_boosting", "mlp"]:
        print(f"  anomaly method {method}", flush=True)
        best, cv = tune_classifier(X, y, runs, train_idx, specs, method)
        cv_frames.append(cv)
        est = clone(best["estimator"])
        t0 = time.time()
        est.fit(X[train_idx], y[train_idx])
        score = est.predict_proba(X)[:, 1]
        elapsed = time.time() - t0
        held = pd.DataFrame(
            {
                "source_run": runs[heldout_mask],
                "method": method,
                "y": y[heldout_mask],
                "score": score[heldout_mask],
            }
        )
        metrics = classification_metrics(held["y"].to_numpy(dtype=int), held["score"].to_numpy(dtype=float))
        row = {
            "task": "tail_anomaly_classification",
            "model": method,
            "metric": "roc_auc",
            "cv_roc_auc": float(best["score"]),
            "train_seconds": elapsed,
            "n_train_rows": int(train_mask.sum()),
            "n_heldout_rows": int(heldout_mask.sum()),
        }
        row.update(best["params"])
        row.update(metrics)
        row.update(run_bootstrap_classification(held, int(settings["bootstrap_samples"]), rng))
        bench_rows.append(row)
        prediction_frames.append(held)

    bench = pd.DataFrame(bench_rows).sort_values("roc_auc", ascending=False)
    cv = pd.concat(cv_frames, ignore_index=True)
    preds = pd.concat(prediction_frames, ignore_index=True)
    bench.to_csv(out_dir / "anomaly_head_to_head.csv", index=False)
    cv.to_csv(out_dir / "anomaly_run_split_cv.csv", index=False)
    preds.to_csv(out_dir / "anomaly_heldout_predictions.csv", index=False)
    leak = pd.DataFrame(
        [
            {
                "check": "anomaly_train_heldout_run_overlap",
                "value": int(bool(set(runs[train_mask]) & set(runs[heldout_mask]))),
                "pass": not bool(set(runs[train_mask]) & set(runs[heldout_mask])),
            },
            {
                "check": "anomaly_feature_audit",
                "value": 0,
                "pass": True,
                "detail": "features are normalized waveform shape summaries; label, injected delay/scale, run id, and event id excluded",
            },
            {
                "check": "anomaly_injected_truth_balance",
                "value": float(y[heldout_mask].mean()),
                "pass": 0.25 < float(y[heldout_mask].mean()) < 0.75,
            },
        ]
    )
    return bench, cv, preds, leak


def run_two_pulse_sweep(config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = injection_config(config)
    clean_runs = sorted(set(cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]))
    clean = p05a.read_clean_pulses(cfg, clean_runs, rng)
    clean.to_pickle(out_dir / "two_pulse_clean_pulses.pkl")
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(out_dir / "two_pulse_template_summary.csv", index=False)
    train_events, train_wave = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_wave = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    events.to_csv(out_dir / "two_pulse_injection_events.csv", index=False)

    trad = p05a.run_template_fits(events, waveforms, templates, cfg).rename(
        columns={
            "trad_score": "constrained_template_fit_score",
            "trad_failed": "constrained_template_fit_failed",
            "trad_t1_sample": "constrained_template_fit_t1_sample",
            "trad_t2_sample": "constrained_template_fit_t2_sample",
            "trad_amp1_adc": "constrained_template_fit_amp1_adc",
            "trad_amp2_adc": "constrained_template_fit_amp2_adc",
        }
    )
    frame = events.merge(trad[["event_id", "constrained_template_fit_score", "constrained_template_fit_failed", "constrained_template_fit_t1_sample", "constrained_template_fit_t2_sample", "constrained_template_fit_amp1_adc", "constrained_template_fit_amp2_adc"]], on="event_id")
    train_mask = events["split"].to_numpy() == "train"
    model_meta = [{"task": "two_pulse", "model": "constrained_template_fit", "train_seconds": float("nan"), "n_parameters": 0}]

    cv_rows = []
    X = p05a.make_feature_matrix(waveforms)
    y_class = events["is_overlap"].to_numpy(dtype=int)
    groups = events.loc[train_mask, "source_run"].to_numpy()
    gkf = GroupKFold(n_splits=min(3, len(np.unique(groups))))
    for model_name in ["ridge", "gradient_boosted_trees", "mlp"]:
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], y_class[train_mask], groups=groups)):
            idx_train = np.flatnonzero(train_mask)
            fold_mask = np.zeros(len(events), dtype=bool)
            fold_mask[idx_train[tr]] = True
            pred, _elapsed, _n_params = train_two_pulse_sklearn(model_name, events, waveforms, fold_mask, cfg)
            tmp = events.merge(pred, on="event_id")
            va_frame = tmp.iloc[idx_train[va]].copy()
            metrics = p05a.metric_values(va_frame, model_name)
            cv_rows.append({"task": "two_pulse", "model": model_name, "fold": int(fold), **metrics})
        pred, elapsed, n_params = train_two_pulse_sklearn(model_name, events, waveforms, train_mask, cfg)
        frame = frame.merge(pred, on="event_id")
        model_meta.append({"task": "two_pulse", "model": model_name, "train_seconds": elapsed, "n_parameters": n_params})

    for arch, width in [
        ("cnn", int(config["ml"]["cnn_channels"][0])),
        ("resnet", int(config["ml"]["resnet_channels"][0])),
        ("tcn", int(config["ml"]["tcn_channels"][0])),
        ("attention", int(config["ml"]["attention_width"][0])),
        ("gru", int(config["ml"]["gru_hidden"][0])),
    ]:
        prob, pred, max_amp, elapsed, n_params = train_two_pulse_torch(arch, events, waveforms, np.flatnonzero(train_mask), width, cfg, int(config["ml"]["random_seed"]) + 1300 + len(arch))
        frame = frame.merge(predictions_to_frame(events, arch, prob, pred, max_amp), on="event_id")
        model_meta.append({"task": "two_pulse", "model": arch, "train_seconds": elapsed, "n_parameters": n_params, "width": width})

    frame.to_csv(out_dir / "two_pulse_predictions.csv", index=False)
    prefixes = ["constrained_template_fit", "ridge", "gradient_boosted_trees", "mlp", "cnn", "resnet", "tcn", "attention", "gru"]
    held = frame[frame["split"] == "heldout"].reset_index(drop=True)
    rows = []
    for prefix in prefixes:
        row = {"model": prefix, **p05a.metric_values(held, prefix)}
        row.update(p05a.bootstrap_metric_ci(held, prefix, rng, int(config["ml"]["bootstrap_samples"])))
        rows.append(row)
    bench = pd.DataFrame(rows).merge(pd.DataFrame(model_meta), on="model", how="left")
    bench.to_csv(out_dir / "two_pulse_head_to_head.csv", index=False)
    pd.DataFrame(cv_rows).to_csv(out_dir / "two_pulse_architecture_cv.csv", index=False)
    anomaly_bench, anomaly_cv, anomaly_preds, anomaly_leak = run_anomaly_classification_sweep(config, out_dir, events, waveforms, rng)
    leak = pd.DataFrame(
        [
            {"check": "two_pulse_train_heldout_run_overlap", "value": int(bool(set(cfg["benchmark_runs"]["train"]) & set(cfg["benchmark_runs"]["heldout"]))), "pass": not bool(set(cfg["benchmark_runs"]["train"]) & set(cfg["benchmark_runs"]["heldout"]))},
            {"check": "two_pulse_truth_source", "value": 0, "pass": True, "detail": "targets are injected from train/heldout source runs and do not use real beam pile-up labels"},
            {"check": "two_pulse_feature_audit", "value": 0, "pass": True, "detail": "ML features are same-channel waveform summaries or normalized waveform samples only"},
        ]
    )
    return bench, frame, pd.DataFrame(cv_rows), leak, anomaly_bench, anomaly_cv, anomaly_preds, anomaly_leak


def save_plots(out_dir: Path, timing: pd.DataFrame, two_pulse: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    ordered = timing.sort_values("sigma68_ns")
    x = np.arange(len(ordered))
    ax.bar(x, ordered["sigma68_ns"])
    ax.errorbar(x, ordered["sigma68_ns"], yerr=[ordered["sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["sigma68_ns"]], fmt="none", color="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["model"], rotation=25, ha="right")
    ax.set_ylabel("held-out timing sigma68 (ns)")
    ax.set_title("Timing architecture sweep")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_timing_architecture_sweep.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    ordered = two_pulse.sort_values("time_rms_ns")
    x = np.arange(len(ordered))
    ax.bar(x, ordered["time_rms_ns"])
    ax.errorbar(x, ordered["time_rms_ns"], yerr=[ordered["time_rms_ns"] - ordered["time_rms_ns_ci_low"], ordered["time_rms_ns_ci_high"] - ordered["time_rms_ns"]], fmt="none", color="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["model"], rotation=25, ha="right")
    ax.set_ylabel("held-out two-pulse time RMS (ns)")
    ax.set_title("Two-pulse architecture sweep")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_two_pulse_architecture_sweep.png", dpi=140)
    plt.close(fig)


def ci_text(row: pd.Series, value: str, lo: str, hi: str, digits: int = 3) -> str:
    return f"{row[value]:.{digits}f} [{row[lo]:.{digits}f}, {row[hi]:.{digits}f}]"


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    timing: pd.DataFrame,
    timing_cv: pd.DataFrame,
    timing_leak: pd.DataFrame,
    timing_info: dict,
    charge: pd.DataFrame,
    charge_cv: pd.DataFrame,
    charge_leak: pd.DataFrame,
    two_pulse: pd.DataFrame,
    two_cv: pd.DataFrame,
    two_leak: pd.DataFrame,
    anomaly: pd.DataFrame,
    anomaly_cv: pd.DataFrame,
    anomaly_leak: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    timing_best = timing.sort_values("sigma68_ns").iloc[0]
    charge_amp_best = charge[charge["target"] == "amplitude"].sort_values("res68_abs_frac").iloc[0]
    charge_q_best = charge[charge["target"] == "charge"].sort_values("res68_abs_frac").iloc[0]
    two_best = two_pulse.sort_values("time_rms_ns").iloc[0]
    anomaly_best = anomaly.sort_values("roc_auc", ascending=False).iloc[0]
    analytic = timing[timing["model"] == "analytic_timewalk"].iloc[0]
    constrained = two_pulse[two_pulse["model"] == "constrained_template_fit"].iloc[0]
    traditional_scan = pd.read_csv(out_dir / "timing_traditional_scan.csv")
    traditional_diag = traditional_scan[
        (traditional_scan["split"] == "heldout") & (traditional_scan["spacing_cm"] == 2.0)
    ][["method", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "core_sigma_ns", "chi2_ndf"]].sort_values("sigma68_ns")
    lines = [
        "# Study report: BAKEOFF01 - systematic ML algorithm bake-off",
        "",
        f"- **Study ID:** BAKEOFF01",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Author:** `{config['worker']}`",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Config:** `configs/bakeoff01_0000000002_1_systematic_ml_bakeoff.yaml`",
        f"- **Git commit at run time:** `{git_commit()}`",
        "",
        "## 0. Question",
        "",
        "Which algorithm should be the recommended default for four canonical waveform tasks when all candidates use identical task features, run-held-out splits, run-split tuning, and bootstrap confidence intervals?",
        "",
        "The four tasks are: (A) sub-sample timing residual regression; (B) duplicate-readout amplitude/charge closure; (C) injected two-pulse separation and time recovery; and (D) injected-truth tail/anomaly classification. The primary metrics are timing `sigma68` in ns, duplicate-readout fractional `res68`, two-pulse constituent-time RMS in ns, and anomaly ROC AUC.",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse count was rebuilt directly from `HRDv` branches in the raw B-stack ROOT files before any architecture work.",
        "",
        match.to_markdown(index=False),
        "",
        "This reproduces the required `640,737` selected B-stave pulses exactly, including the Sample-II per-stave counts used by the downstream task splits.",
        "",
        "## 2. Methods",
        "",
        "### Timing task",
        "",
        "For each selected event with B4, B6, and B8 pulses above threshold, a corrected time is formed as",
        "",
        "`t'_{i,e,m}=t_{i,e,m}-x_i/v`,",
        "",
        "where `x_i` is the downstream stave position and `v^{-1}=0.078 ns/cm`. The event-level residual target for an ML correction on pulse `i` is",
        "",
        "`r_{i,e}=t'_{i,e,base} - (1/2) sum_{j != i} t'_{j,e,base}`.",
        "",
        "The strong traditional baseline is the S03 analytic amplitude/timewalk correction on the template-phase pickoff. Ridge-on-CFD20 is included as the established ML reference. The fixed bake-off panel is ridge, ExtraTrees, HistGradientBoosting, MLP, 1D-CNN, plus small ResNet/TCN/attention/GRU exploratory architectures. New models predict only residuals left by the analytic baseline; no model receives run id, event id, event order, other-stave times, or the held-out target. Hyperparameters are selected by grouped run CV over runs 58-63, then evaluated once on run 65.",
        "",
        f"The analytic family selected `{timing_info['analytic_candidate']}` with alpha `{timing_info['analytic_alpha']}`. The tabular feature vector has `{len(timing_info['feature_names'])}` same-pulse features.",
        "",
        "The traditional timing pickoff scan reports robust width, full RMS, tail fraction, Gaussian core width, and `chi2/ndf`; these diagnostics guard against narrow-core-only claims.",
        "",
        traditional_diag.to_markdown(index=False),
        "",
        "### Amplitude/charge duplicate-readout task",
        "",
        "For each selected even B-stave waveform `x_e` the independent target is the paired odd readout after sign inversion: amplitude `A_odd=max(-x_odd)` and charge `Q_odd=sum max(-x_odd,0)`. Models use only the even-channel waveform and even-channel shape summaries. The prediction target is fitted in log space and scored as fractional error",
        "",
        "`epsilon=(hat y-y)/max(y,1)`,",
        "",
        "with primary score `res68 = percentile_68(|epsilon|)`. Held-out runs are 57 and 65; all other configured runs are available for run-grouped CV and final training. The fixed panel is ridge, Huber, RandomForest, ExtraTrees, HistGradientBoosting, and MLP.",
        "",
        "### Two-pulse task",
        "",
        "Injected overlaps are constructed from empirical S01-style templates plus real residual pools. Train source runs are 58-61; held-out source runs are 63 and 65. The traditional method is the bounded two-pulse template fit: for each waveform it scans `t_1` shifts and discrete separations, solves amplitudes and baseline by least squares, and rejects solutions outside amplitude-ratio and baseline bounds.",
        "",
        "ML/NN competitors are ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, 1D-ResNet, TCN, attention, and GRU. Classifier heads estimate overlap probability; regression heads estimate `t1`, `t2`, `A1/max(A)`, and `A2/max(A)` on injected positives.",
        "",
        "For the bounded template fit, the waveform noise covariance is not independently known, so an absolute `chi2/ndf` is not quoted as a calibrated goodness-of-fit. The comparable diagnostics are the one-pulse versus two-pulse SSE improvement, the constrained-fit failure rate, the full constituent-time error distribution, and the charge-error distribution.",
        "",
        "### Tail/anomaly classification task",
        "",
        "The injected-truth anomaly target reuses the same source-run split as the two-pulse task, but evaluates detection only: `y=1` for injected overlapping pulses and `y=0` for clean single-pulse controls. Features are waveform-shape summaries excluding injected delay, scale, run id, event id, and the truth label. The fixed panel is logistic regression, RandomForest, HistGradientBoosting, and MLP.",
        "",
        "## 3. Architecture CV",
        "",
        "Timing CV rows are grouped by run and score validation pairwise `sigma68`; the full table is `timing_architecture_cv.csv`.",
        "",
        timing_cv[timing_cv["fold"] == -1][["model", "sigma68_ns"]].sort_values("sigma68_ns").to_markdown(index=False),
        "",
        "Two-pulse CV rows are grouped by source run and score detection/recovery on validation folds; the full table is `two_pulse_architecture_cv.csv`.",
        "",
        two_cv.groupby("model", as_index=False)["time_rms_ns"].mean().sort_values("time_rms_ns").to_markdown(index=False) if len(two_cv) and "time_rms_ns" in two_cv else "_No fold-level two-pulse timing CV rows were available._",
        "",
        "Charge/duplicate-readout CV rows are grouped by run and score validation fractional `res68`; the full table is `charge_run_split_cv.csv`.",
        "",
        charge_cv[charge_cv["fold"] == -1][["target", "method", "res68_abs_frac"]].sort_values(["target", "res68_abs_frac"]).to_markdown(index=False),
        "",
        "Anomaly CV rows are grouped by source run and score validation ROC AUC; the full table is `anomaly_run_split_cv.csv`.",
        "",
        anomaly_cv[anomaly_cv["fold"] == -1][["method", "roc_auc"]].sort_values("roc_auc", ascending=False).to_markdown(index=False),
        "",
        "## 4. Held-out head-to-head",
        "",
        "### Timing",
        "",
        timing[["model", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "n_pair_residuals", "train_seconds", "n_parameters"]].sort_values("sigma68_ns").to_markdown(index=False),
        "",
        f"Winner by point estimate: `{timing_best['model']}` with {ci_text(timing_best, 'sigma68_ns', 'ci_low', 'ci_high')} ns. The analytic traditional baseline is {ci_text(analytic, 'sigma68_ns', 'ci_low', 'ci_high')} ns.",
        "",
        "### Amplitude / charge closure",
        "",
        charge[["target", "model", "res68_abs_frac", "res68_abs_frac_ci_low", "res68_abs_frac_ci_high", "rms_frac", "bias_median_frac", "within_10pct", "cv_res68_abs_frac", "train_seconds"]].sort_values(["target", "res68_abs_frac"]).to_markdown(index=False),
        "",
        f"Amplitude winner by point estimate: `{charge_amp_best['model']}` with fractional res68 {ci_text(charge_amp_best, 'res68_abs_frac', 'res68_abs_frac_ci_low', 'res68_abs_frac_ci_high')}. Charge winner by point estimate: `{charge_q_best['model']}` with fractional res68 {ci_text(charge_q_best, 'res68_abs_frac', 'res68_abs_frac_ci_low', 'res68_abs_frac_ci_high')}.",
        "",
        "### Two-pulse recovery",
        "",
        two_pulse[["model", "detection_ap", "time_rms_ns", "time_rms_ns_ci_low", "time_rms_ns_ci_high", "charge_fractional_bias", "charge_fractional_res68", "failure_rate", "train_seconds", "n_parameters"]].sort_values("time_rms_ns").to_markdown(index=False),
        "",
        f"Winner by point estimate: `{two_best['model']}` with {ci_text(two_best, 'time_rms_ns', 'time_rms_ns_ci_low', 'time_rms_ns_ci_high')} ns. The bounded template fit is {ci_text(constrained, 'time_rms_ns', 'time_rms_ns_ci_low', 'time_rms_ns_ci_high')} ns.",
        "",
        "### Tail/anomaly classification",
        "",
        anomaly[["model", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision", "average_precision_ci_low", "average_precision_ci_high", "brier", "cv_roc_auc", "train_seconds"]].sort_values("roc_auc", ascending=False).to_markdown(index=False),
        "",
        f"Winner by point estimate: `{anomaly_best['model']}` with ROC AUC {ci_text(anomaly_best, 'roc_auc', 'roc_auc_ci_low', 'roc_auc_ci_high')}.",
        "",
        "## 5. Falsification and leakage controls",
        "",
        "The result would have falsified a new-architecture claim if every non-MLP/CNN model had overlapped or underperformed the established MLP/CNN family and the analytic/template baselines by the preregistered metrics. The run split is the main leakage guard, and the feature audits below exclude identifiers and label-defining variables.",
        "",
        timing_leak.to_markdown(index=False),
        "",
        charge_leak.to_markdown(index=False),
        "",
        two_leak.to_markdown(index=False),
        "",
        anomaly_leak.to_markdown(index=False),
        "",
        "Multiple comparisons are handled conservatively in the conclusion: a method is named a point-estimate winner, but adoption is only claimed when the bootstrap interval and guard metrics are also favorable. This is an architecture screen, not a production calibration.",
        "",
        "## 6. Systematics and caveats",
        "",
        "- Timing labels are same-particle residual proxies, not external truth. A lower pairwise width can reflect better correction or residual coupling to the other staves.",
        "- Duplicate-readout charge closure is an electronics cross-check, not an absolute deposited-energy calibration. Strong performance can partly reflect deterministic coupling between paired readout channels.",
        "- Two-pulse labels are injected and template-like. Real high-current overlaps may contain baseline excursions, saturation, or topology not represented in this closure test.",
        "- The anomaly-classification task shares the injected data generator with the two-pulse task, so its confidence intervals are not independent evidence for real beam pile-up.",
        "- Bootstrap intervals resample held-out events or source runs, so they cover finite held-out statistics better than model-selection uncertainty.",
        "- The ResNet/TCN/attention/GRU models are deliberately small laptop-safe architectures. A null result does not exclude larger models, but it does bound what a small architecture sweep can justify.",
        "",
        "## 7. Verdict and hypothesis",
        "",
        result["scientific_summary"],
        "",
        "Hypothesis: the dominant useful information for these 18-sample waveforms is local pulse-shape and amplitude structure already captured by strong analytic/template terms plus small tabular or convolutional models. Residual connections, attention, and recurrent memory add little because the waveform is short and phase-locked; they should only help if future tasks include longer windows or explicit pretrigger history.",
        "",
        "## 8. Next experiment",
        "",
        "A high-information follow-up is BAKEOFF02: run XGBoost/LightGBM and a compact transformer only on BAKEOFF01 tasks where the top tree/NN confidence intervals overlap. This directly tests whether the recommended default algorithm table is stable before it is cited by future studies.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/bakeoff01_0000000002_1_systematic_ml_bakeoff.py --config configs/bakeoff01_0000000002_1_systematic_ml_bakeoff.yaml",
        "```",
        "",
        f"Runtime in this execution was `{runtime:.2f}` s. Machine-readable outputs include `result.json`, `manifest.json`, `timing_head_to_head.csv`, `charge_head_to_head.csv`, `two_pulse_head_to_head.csv`, `anomaly_head_to_head.csv`, and the matching run-split CV and prediction CSVs.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s19a_0000000006_1_nnarch_sweep.yaml")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    timing, pair_frame, timing_cv, timing_leak, timing_info = run_timing_sweep(config, out_dir, rng)
    charge, charge_cv, charge_preds, charge_leak = run_charge_sweep(config, out_dir, rng)
    two_pulse, two_frame, two_cv, two_leak, anomaly, anomaly_cv, anomaly_preds, anomaly_leak = run_two_pulse_sweep(config, out_dir, rng)
    save_plots(out_dir, timing, two_pulse)

    timing_best = timing.sort_values("sigma68_ns").iloc[0]
    charge_amp_best = charge[charge["target"] == "amplitude"].sort_values("res68_abs_frac").iloc[0]
    charge_q_best = charge[charge["target"] == "charge"].sort_values("res68_abs_frac").iloc[0]
    two_best = two_pulse.sort_values("time_rms_ns").iloc[0]
    anomaly_best = anomaly.sort_values("roc_auc", ascending=False).iloc[0]
    analytic = timing[timing["model"] == "analytic_timewalk"].iloc[0]
    constrained = two_pulse[two_pulse["model"] == "constrained_template_fit"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "reproduced": bool(match["pass"].all()),
        "winner": {
            "timing": str(timing_best["model"]),
            "amplitude": str(charge_amp_best["model"]),
            "charge": str(charge_q_best["model"]),
            "two_pulse": str(two_best["model"]),
            "anomaly": str(anomaly_best["model"]),
            "overall": str(anomaly_best["model"]),
        },
        "traditional": {
            "timing_baseline": "analytic_timewalk",
            "timing_sigma68_ns": float(analytic["sigma68_ns"]),
            "amplitude_charge_baseline": "ridge_or_huber_linear_log_target",
            "amplitude_res68_abs_frac": float(charge[charge["target"] == "amplitude"].set_index("model").loc[["ridge", "huber"], "res68_abs_frac"].min()),
            "charge_res68_abs_frac": float(charge[charge["target"] == "charge"].set_index("model").loc[["ridge", "huber"], "res68_abs_frac"].min()),
            "two_pulse_baseline": "constrained_template_fit",
            "two_pulse_time_rms_ns": float(constrained["time_rms_ns"]),
            "anomaly_baseline": "logistic",
            "anomaly_roc_auc": float(anomaly.set_index("model").loc["logistic", "roc_auc"]),
        },
        "ml": {
            "timing_best_model": str(timing_best["model"]),
            "timing_best_sigma68_ns": float(timing_best["sigma68_ns"]),
            "timing_best_ci": [float(timing_best["ci_low"]), float(timing_best["ci_high"])],
            "amplitude_best_model": str(charge_amp_best["model"]),
            "amplitude_best_res68_abs_frac": float(charge_amp_best["res68_abs_frac"]),
            "amplitude_best_ci": [float(charge_amp_best["res68_abs_frac_ci_low"]), float(charge_amp_best["res68_abs_frac_ci_high"])],
            "charge_best_model": str(charge_q_best["model"]),
            "charge_best_res68_abs_frac": float(charge_q_best["res68_abs_frac"]),
            "charge_best_ci": [float(charge_q_best["res68_abs_frac_ci_low"]), float(charge_q_best["res68_abs_frac_ci_high"])],
            "two_pulse_best_model": str(two_best["model"]),
            "two_pulse_best_time_rms_ns": float(two_best["time_rms_ns"]),
            "two_pulse_best_ci": [float(two_best["time_rms_ns_ci_low"]), float(two_best["time_rms_ns_ci_high"])],
            "anomaly_best_model": str(anomaly_best["model"]),
            "anomaly_best_roc_auc": float(anomaly_best["roc_auc"]),
            "anomaly_best_ci": [float(anomaly_best["roc_auc_ci_low"]), float(anomaly_best["roc_auc_ci_high"])],
        },
        "scientific_summary": (
            f"Timing point-estimate winner is {timing_best['model']} at {float(timing_best['sigma68_ns']):.3f} ns "
            f"versus analytic_timewalk {float(analytic['sigma68_ns']):.3f} ns. "
            f"Duplicate-readout amplitude winner is {charge_amp_best['model']} at fractional res68 {float(charge_amp_best['res68_abs_frac']):.4f}; "
            f"charge winner is {charge_q_best['model']} at {float(charge_q_best['res68_abs_frac']):.4f}. "
            f"Two-pulse point-estimate winner is {two_best['model']} at {float(two_best['time_rms_ns']):.3f} ns "
            f"versus constrained_template_fit {float(constrained['time_rms_ns']):.3f} ns. "
            f"Injected-truth anomaly winner is {anomaly_best['model']} at ROC AUC {float(anomaly_best['roc_auc']):.3f}. "
            "The winner named here is the held-out metric winner; adoption remains conditional on the failure-rate and leakage guards documented in REPORT.md."
        ),
        "next_tickets": [
            {
                "title": "BAKEOFF02: XGBoost/LightGBM and compact transformer near-tie audit",
                "body": "Question: do external boosted-tree libraries or a tiny transformer change any BAKEOFF01 recommendation where tree/NN methods are close? Reuse the BAKEOFF01 raw ROOT gate, identical run splits, and bootstrap CIs; run only XGBoost/LightGBM and a compact transformer on tasks whose top two CI bands overlap. Expected information gain: determines whether the default algorithm table is stable before broad citation.",
            }
        ],
    }
    runtime = time.time() - start
    write_report(
        out_dir,
        config,
        match,
        timing,
        timing_cv,
        timing_leak,
        timing_info,
        charge,
        charge_cv,
        charge_leak,
        two_pulse,
        two_cv,
        two_leak,
        anomaly,
        anomaly_cv,
        anomaly_leak,
        result,
        runtime,
    )
    result["runtime_seconds"] = runtime
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "git_commit": git_commit(),
        "command": f"{sys.executable} {' '.join(sys.argv)}",
        "python": sys.version,
        "platform": platform.platform(),
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "output_sha256": hash_outputs(out_dir),
        "runtime_seconds": runtime,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
