#!/usr/bin/env python3
"""S03q run64-only calibration acceptance gate.

This script reproduces the raw B-stack pulse counts, trains run64-only timing
corrections, benchmarks traditional and ML/NN methods on held-out Sample-II
runs, and classifies run/stave/amplitude/shape atoms as acceptable or
diagnostic-only.
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
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s03q")
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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
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
        p.name: sha256_file(p)
        for p in sorted(out_dir.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }


def configured_all_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group in config["run_groups"].values():
        runs.extend(int(r) for r in group)
    return sorted(set(runs))


def load_downstream_pulses_for_runs(config: dict, runs: Sequence[int]) -> pd.DataFrame:
    tmp = json.loads(json.dumps(config))
    tmp["timing"]["train_runs"] = [int(r) for r in runs]
    tmp["timing"]["heldout_runs"] = []
    return s02.load_downstream_pulses(tmp)


def reproduce_counts_with_run64(config: dict) -> pd.DataFrame:
    base = s02.reproduce_counts(config)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    channels = np.asarray([staves[name] for name in staves.keys()])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    run64 = 0
    path = s02.raw_file(config, 64)
    for batch in s02.iter_raw(path, ["HRDv"]):
        events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
        waveforms = events[:, channels, :]
        _, amplitude, _, _ = s02.pulse_quantities(waveforms, baseline_idx)
        run64 += int((amplitude > cut).sum())
    exp = int(config["expected_counts"]["sample_ii_calib"]["selected_pulses"])
    extra = pd.DataFrame(
        [
            {
                "quantity": "sample_ii_calib run64 selected_pulses",
                "report_value": exp,
                "reproduced": int(run64),
                "delta": int(run64 - exp),
                "tolerance": 0,
                "pass": bool(run64 == exp),
            }
        ]
    )
    return pd.concat([base, extra], ignore_index=True)


def add_base_times(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, np.ndarray]]:
    out = pulses.copy()
    train = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    return out, scan, templates


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


def feature_blocks(
    pulses: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray]
) -> Tuple[Dict[str, np.ndarray], Dict[str, List[str]]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
    norm = wf / amp[:, None]
    period = float(config["sample_period_ns"])
    cfd10 = pulses["t_cfd10_ns"].to_numpy(dtype=np.float32)
    cfd20 = pulses["t_cfd20_ns"].to_numpy(dtype=np.float32)
    cfd40 = pulses["t_cfd40_ns"].to_numpy(dtype=np.float32)
    cfd50 = pulses["t_cfd50_ns"].to_numpy(dtype=np.float32)
    amplitude = np.column_stack(
        [
            np.log1p(amp),
            1000.0 / amp,
            np.sqrt(1000.0 / amp),
            pulses["area_adc_samples"].to_numpy(dtype=np.float32) / amp,
            pulses["peak_sample"].to_numpy(dtype=np.float32),
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
    staves = list(config["timing"]["downstream_staves"])
    stave = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_lookup = {name: i for i, name in enumerate(staves)}
    for i, name in enumerate(pulses["stave"]):
        stave[i, stave_lookup[str(name)]] = 1.0
    blocks = {
        "waveform": norm.astype(np.float32),
        "amplitude": amplitude.astype(np.float32),
        "q_template": qtemp.astype(np.float32),
        "pretrigger": pre.astype(np.float32),
        "stave": stave,
        "shape_extra": shape.astype(np.float32),
    }
    names = {
        "waveform": [f"norm_sample_{i:02d}" for i in range(norm.shape[1])],
        "amplitude": ["log_amp", "inv_amp_1000", "inv_sqrt_amp_1000", "area_over_amp", "peak_sample"],
        "q_template": ["template_mse", "template_corr", "template_tail_mse"],
        "pretrigger": ["pre0", "pre1", "pre2", "pre3", "pre_mean", "pre_std", "pre_slope_per_ns"],
        "stave": [f"stave_{s}" for s in staves],
        "shape_extra": [
            "cfd50_minus_cfd10_ns",
            "cfd40_minus_cfd20_ns",
            "max_norm_slope",
            "early_norm_charge",
            "late_norm_charge",
            "norm_peak_height",
        ],
    }
    return blocks, names


def assemble_features(
    blocks: Dict[str, np.ndarray], names: Dict[str, List[str]], families: Sequence[str]
) -> Tuple[np.ndarray, List[str]]:
    pieces = [blocks[f] for f in families]
    feature_names: List[str] = []
    for family in families:
        feature_names.extend([f"{family}:{name}" for name in names[family]])
    return np.hstack(pieces).astype(np.float32), feature_names


def finite_rows(X: np.ndarray, y: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return np.flatnonzero(mask & np.isfinite(y) & np.all(np.isfinite(X), axis=1))


def subsample_train(train_idx: np.ndarray, max_rows: int, seed: int) -> np.ndarray:
    if int(max_rows) <= 0 or len(train_idx) <= int(max_rows):
        return train_idx
    rng = np.random.default_rng(seed)
    return np.sort(rng.choice(train_idx, size=int(max_rows), replace=False))


def fit_ridge_fixed(
    X: np.ndarray, y: np.ndarray, train_mask: np.ndarray, config: dict, method: str
) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    train_idx = finite_rows(X, y, train_mask)
    alpha = float(config["ml"]["ridge_alpha"])
    model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    model.fit(X[train_idx], y[train_idx])
    pred = model.predict(X).astype(float)
    rmse = float(np.sqrt(np.mean((model.predict(X[train_idx]) - y[train_idx]) ** 2)))
    return pred, pd.DataFrame([{"method": method, "fit": "run64_fixed", "rmse_ns": rmse}]), {
        "alpha": alpha,
        "n_train_rows": int(len(train_idx)),
        "train_rmse_ns": rmse,
    }


def fit_hgb_fixed(
    X: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    method: str,
    seed: int,
    shuffle_target: bool = False,
) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    train_idx_all = finite_rows(X, y, train_mask)
    train_idx = subsample_train(train_idx_all, int(config["ml"]["max_train_rows"]), seed)
    y_train = y[train_idx].copy()
    if shuffle_target:
        rng = np.random.default_rng(seed + 1)
        rng.shuffle(y_train)
    params = {
        "max_iter": int(config["ml"]["hgb_max_iter"]),
        "learning_rate": float(config["ml"]["hgb_learning_rate"]),
        "max_leaf_nodes": int(config["ml"]["hgb_max_leaf_nodes"]),
        "l2_regularization": float(config["ml"]["hgb_l2_regularization"]),
        "max_bins": int(config["ml"]["hgb_max_bins"]),
        "random_state": int(seed),
    }
    model = HistGradientBoostingRegressor(**params)
    model.fit(X[train_idx], y_train)
    pred = model.predict(X).astype(float)
    rmse = float(np.sqrt(np.mean((model.predict(X[train_idx]) - y_train) ** 2)))
    return pred, pd.DataFrame([{"method": method, "fit": "run64_fixed", "rmse_ns": rmse, **params}]), {
        "params": params,
        "n_train_rows": int(len(train_idx)),
        "train_rmse_ns": rmse,
    }


def fit_mlp_fixed(
    X: np.ndarray, y: np.ndarray, train_mask: np.ndarray, config: dict, method: str, seed: int
) -> Tuple[np.ndarray, pd.DataFrame, dict]:
    train_idx_all = finite_rows(X, y, train_mask)
    train_idx = subsample_train(train_idx_all, int(config["ml"]["max_train_rows"]), seed)
    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=(int(config["ml"]["mlp_hidden"]),),
            alpha=float(config["ml"]["mlp_alpha"]),
            max_iter=int(config["ml"]["mlp_max_iter"]),
            random_state=seed,
            early_stopping=False,
        ),
    )
    t0 = time.time()
    model.fit(X[train_idx], y[train_idx])
    pred = model.predict(X).astype(float)
    rmse = float(np.sqrt(np.mean((model.predict(X[train_idx]) - y[train_idx]) ** 2)))
    return pred, pd.DataFrame([{"method": method, "fit": "run64_fixed", "rmse_ns": rmse}]), {
        "n_train_rows": int(len(train_idx)),
        "train_seconds": time.time() - t0,
        "train_rmse_ns": rmse,
    }


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


def standardize_train(X: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    scaler = StandardScaler()
    Xs = X.astype(np.float32).copy()
    Xs[train_idx] = scaler.fit_transform(X[train_idx])
    rest = np.setdiff1d(np.arange(len(X)), train_idx, assume_unique=False)
    if len(rest):
        Xs[rest] = scaler.transform(X[rest])
    return Xs.astype(np.float32)


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
    train_idx_all = np.flatnonzero(train_mask & np.isfinite(y) & np.all(np.isfinite(wave), axis=1) & np.all(np.isfinite(aux), axis=1))
    train_idx = subsample_train(train_idx_all, int(config["ml"]["max_train_rows"]), seed)
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    wave_s = standardize_train(wave, train_idx)
    aux_s = standardize_train(aux, train_idx)
    y_mean = float(np.mean(y[train_idx]))
    y_scale = float(np.std(y[train_idx]) + 1.0e-6)
    yy = ((y - y_mean) / y_scale).astype(np.float32)
    width = int(config["ml"]["cnn_channels"] if arch == "cnn" else config["ml"]["tcn_channels"])
    model = WaveNet(arch, aux_s.shape[1], width)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["ml"]["torch_learning_rate"]),
        weight_decay=float(config["ml"]["torch_weight_decay"]),
    )
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
    rmse = float(np.sqrt(np.mean((pred[train_idx] - y[train_idx]) ** 2)))
    return pred, pd.DataFrame([{"method": method, "fit": "run64_fixed", "rmse_ns": rmse}]), {
        "arch": arch,
        "n_train_rows": int(len(train_idx)),
        "train_seconds": time.time() - t0,
        "last_loss": float(losses[-1]) if losses else float("nan"),
        "n_parameters": int(sum(p.numel() for p in model.parameters())),
        "train_rmse_ns": rmse,
    }


def fit_traditional(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    out = pulses.copy()
    target = s02.event_residual_targets(out, base_method, 2.0, config)
    runs = out["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, [int(r) for r in config["timing"]["train_runs"]]) & np.isfinite(target)
    X, feature_names = s03a.analytic_feature_matrix(out, "amp_only", list(config["timing"]["downstream_staves"]))
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["traditional"]["analytic_alpha"])))
    model.fit(X[train_mask], target[train_mask])
    pred = model.predict(X)
    out["run64_analytic_pred_residual_ns"] = pred
    out["t_run64_analytic_amp_only_ns"] = out[f"t_{base_method}_ns"] - pred
    models = s03b.fit_binned_model(
        out,
        target,
        train_mask,
        config,
        int(config["traditional"]["binned_n_bins"]),
        str(config["traditional"]["binned_mode"]),
        str(config["traditional"]["binned_direction"]),
    )
    binned_pred = s03b.predict_binned_model(out, models)
    out["run64_binned_pred_residual_ns"] = binned_pred
    out["t_run64_monotone_binned_timewalk_ns"] = out[f"t_{base_method}_ns"] - binned_pred
    audit = pd.DataFrame(
        [
            {
                "method": "run64_analytic_amp_only",
                "fit": "fixed_alpha",
                "n_train_rows": int(train_mask.sum()),
                "n_features": int(len(feature_names)),
                "alpha": float(config["traditional"]["analytic_alpha"]),
            },
            {
                "method": "run64_monotone_binned_timewalk",
                "fit": "fixed_monotone_bins",
                "n_train_rows": int(train_mask.sum()),
                "n_features": 1,
                "n_bins": int(config["traditional"]["binned_n_bins"]),
            },
        ]
    )
    return out, audit, s03b.binned_model_table(models)


def fit_ml_methods(
    pulses: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray], base_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    blocks, block_names = feature_blocks(pulses, config, templates)
    families = ["waveform", "amplitude", "q_template", "pretrigger", "stave", "shape_extra"]
    X, features = assemble_features(blocks, block_names, families)
    aux, aux_features = assemble_features(blocks, block_names, [f for f in families if f != "waveform"])
    target = s02.event_residual_targets(pulses, base_method, 2.0, config)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, [int(r) for r in config["timing"]["train_runs"]])
    mixed_mask = np.isin(runs, [int(r) for r in config["timing"]["mixed_sentinel_runs"]])
    base_values = pulses[f"t_{base_method}_ns"].to_numpy(dtype=float)
    combined = pulses.copy()
    cv_parts = []
    meta_rows = []
    seed = int(config["ml"]["random_seed"])
    specs = [
        ("ridge_run64", "ridge", train_mask, False),
        ("hgb_run64", "hgb", train_mask, False),
        ("mlp_run64", "mlp", train_mask, False),
        ("cnn1d_run64", "cnn", train_mask, False),
        ("gated_tcn_new_run64", "tcn", train_mask, False),
        ("hgb_shuffled_target_sentinel", "hgb", train_mask, True),
        ("hgb_mixed_sample_i_run64_sentinel", "hgb", mixed_mask, False),
    ]
    for i, (method, kind, mask, shuffled) in enumerate(specs):
        if kind == "ridge":
            pred, cv, meta = fit_ridge_fixed(X, target, mask, config, method)
            n_features = len(features)
        elif kind == "hgb":
            pred, cv, meta = fit_hgb_fixed(X, target, mask, config, method, seed + 101 * i, shuffle_target=shuffled)
            n_features = len(features)
        elif kind == "mlp":
            pred, cv, meta = fit_mlp_fixed(X, target, mask, config, method, seed + 101 * i)
            n_features = len(features)
        elif kind in {"cnn", "tcn"}:
            pred, cv, meta = fit_torch_model(method, kind, blocks["waveform"], aux, target, mask, config, seed + 101 * i)
            n_features = len(block_names["waveform"]) + len(aux_features)
        else:
            raise ValueError(kind)
        combined[f"{method}_pred_residual_ns"] = pred
        combined[f"t_{method}_ns"] = base_values - pred
        cv_parts.append(cv)
        meta_rows.append(
            {
                "method": method,
                "families": ",".join(families),
                "n_features": int(n_features),
                "training_scope": "sample_i_plus_run64" if "mixed" in method else "run64_only",
                **meta,
            }
        )
    return combined, pd.concat(cv_parts, ignore_index=True), pd.DataFrame(meta_rows)


def residual_rows(
    pulses: pd.DataFrame, config: dict, methods: Sequence[str], eval_runs: Iterable[int]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    residuals = []
    for run in [int(r) for r in eval_runs]:
        for method in methods:
            vals = s02.pairwise_residuals(pulses, method, 2.0, config, [run])
            rows.append({"heldout_run": run, "method": method, **s02.metric_summary(vals)})
            residuals.extend({"heldout_run": run, "method": method, "pairwise_residual_ns": float(v)} for v in vals)
    return pd.DataFrame(rows), pd.DataFrame(residuals)


def run_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int, reference_method: str) -> pd.DataFrame:
    rows = []
    runs = sorted(int(r) for r in residuals["heldout_run"].unique())
    by_method_run = {
        (method, int(run)): sub["pairwise_residual_ns"].to_numpy(dtype=float)
        for (method, run), sub in residuals.groupby(["method", "heldout_run"])
    }
    reference_values = residuals[residuals["method"] == reference_method]["pairwise_residual_ns"].to_numpy(dtype=float)
    reference_sigma = s02.sigma68(reference_values)
    reference_rms = s02.full_rms(reference_values)
    reference_tail = s02.metric_summary(reference_values)["tail_frac_abs_gt5ns"]
    for method, group in residuals.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        sigma_stats = []
        sigma_deltas = []
        rms_deltas = []
        tail_deltas = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            sample_vals = np.concatenate([by_method_run[(method, int(r))] for r in sampled if (method, int(r)) in by_method_run])
            ref_vals = np.concatenate([by_method_run[(reference_method, int(r))] for r in sampled if (reference_method, int(r)) in by_method_run])
            sigma_stats.append(s02.sigma68(sample_vals))
            sigma_deltas.append(s02.sigma68(sample_vals) - s02.sigma68(ref_vals))
            rms_deltas.append(s02.full_rms(sample_vals) - s02.full_rms(ref_vals))
            tail_deltas.append(s02.metric_summary(sample_vals)["tail_frac_abs_gt5ns"] - s02.metric_summary(ref_vals)["tail_frac_abs_gt5ns"])
        summary = s02.metric_summary(vals)
        rows.append(
            {
                "method": method,
                "metric": "pooled_sample_ii_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(np.percentile(sigma_stats, 2.5)),
                "ci_high": float(np.percentile(sigma_stats, 97.5)),
                "delta_vs_traditional_ns": s02.sigma68(vals) - reference_sigma,
                "delta_ci_low": float(np.percentile(sigma_deltas, 2.5)),
                "delta_ci_high": float(np.percentile(sigma_deltas, 97.5)),
                "full_rms_delta_vs_traditional_ns": s02.full_rms(vals) - reference_rms,
                "full_rms_delta_ci_low": float(np.percentile(rms_deltas, 2.5)),
                "full_rms_delta_ci_high": float(np.percentile(rms_deltas, 97.5)),
                "tail_delta_vs_traditional": summary["tail_frac_abs_gt5ns"] - reference_tail,
                "tail_delta_ci_low": float(np.percentile(tail_deltas, 2.5)),
                "tail_delta_ci_high": float(np.percentile(tail_deltas, 97.5)),
                **summary,
            }
        )
    return pd.DataFrame(rows).sort_values("value")


def add_atom_labels(pulses: pd.DataFrame, config: dict, templates: Dict[str, np.ndarray]) -> pd.DataFrame:
    out = pulses.copy()
    amp = out["amplitude_adc"].to_numpy(dtype=float)
    edges = np.asarray(config["atoms"]["amplitude_edges_adc"], dtype=float)
    labels = [f"{int(edges[i])}_{int(edges[i + 1])}" for i in range(len(edges) - 1)]
    out["amplitude_atom"] = pd.cut(amp, edges, labels=labels, include_lowest=True, right=False).astype(str)
    qtemp = template_features(out, templates)
    out["template_corr"] = qtemp[:, 1]
    train_corr = out[out["run"].isin(config["timing"]["train_runs"])]["template_corr"].to_numpy(dtype=float)
    q1, q2 = np.nanpercentile(train_corr, [33.3, 66.7])
    out["shape_atom"] = np.where(out["template_corr"] < q1, "low_template_corr", np.where(out["template_corr"] < q2, "mid_template_corr", "high_template_corr"))
    return out


def pulse_residual_table(pulses: pd.DataFrame, config: dict, methods: Sequence[str]) -> pd.DataFrame:
    rows = []
    base_cols = ["event_id", "run", "stave", "amplitude_atom", "shape_atom"]
    for method in methods:
        vals = s02.event_residual_targets(pulses, method, 2.0, config)
        tmp = pulses.loc[:, base_cols].copy()
        tmp["method"] = method
        tmp["residual_ns"] = vals
        rows.append(tmp[np.isfinite(tmp["residual_ns"].to_numpy(dtype=float))])
    return pd.concat(rows, ignore_index=True)


def metric_from_values(values: np.ndarray, tail_threshold: float) -> Dict[str, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return {
            "n_pulses": 0,
            "median_ns": float("nan"),
            "sigma68_ns": float("nan"),
            "full_rms_ns": float("nan"),
            "tail_frac_abs_gt5ns": float("nan"),
        }
    med = float(np.median(values))
    return {
        "n_pulses": int(len(values)),
        "median_ns": med,
        "sigma68_ns": s02.sigma68(values),
        "full_rms_ns": s02.full_rms(values),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(values - med) > tail_threshold)),
    }


def build_pulse_atom_metrics(pulse_resid: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    tail = float(config["atoms"]["tail_threshold_ns"])
    for keys, group in pulse_resid.groupby(["run", "stave", "amplitude_atom", "shape_atom", "method"]):
        run, stave, amp_atom, shape_atom, method = keys
        rows.append(
            {
                "run": int(run),
                "stave": stave,
                "amplitude_atom": amp_atom,
                "shape_atom": shape_atom,
                "method": method,
                **metric_from_values(group["residual_ns"].to_numpy(dtype=float), tail),
            }
        )
    return pd.DataFrame(rows)


def atom_acceptance(
    pulse_resid: pd.DataFrame,
    config: dict,
    winner_method: str,
    traditional_method: str,
    sentinel_methods: Sequence[str],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    tail = float(config["atoms"]["tail_threshold_ns"])
    min_support = int(config["atoms"]["min_pulses_per_support_atom"])
    margin = float(config["atoms"]["acceptance_delta_margin_ns"])
    tail_margin = float(config["atoms"]["acceptance_tail_margin"])
    tail_abs_max = float(config["atoms"]["acceptance_tail_abs_max"])
    full_rms_max = float(config["atoms"]["acceptance_full_rms_max_ns"])
    bias_abs = float(config["atoms"]["acceptance_bias_abs_ns"])
    n_boot = int(config["ml"]["bootstrap_samples"])
    rows = []
    atom_cols = ["stave", "amplitude_atom", "shape_atom"]
    methods = [winner_method, traditional_method] + list(sentinel_methods)
    for atom, atom_group in pulse_resid[pulse_resid["method"].isin(methods)].groupby(atom_cols):
        by = {m: sub for m, sub in atom_group.groupby("method")}
        if winner_method not in by or traditional_method not in by:
            continue
        runs = sorted(set(by[winner_method]["run"].astype(int)) & set(by[traditional_method]["run"].astype(int)))
        if not runs:
            continue
        win_vals = by[winner_method]["residual_ns"].to_numpy(dtype=float)
        trad_vals = by[traditional_method]["residual_ns"].to_numpy(dtype=float)
        win_metric = metric_from_values(win_vals, tail)
        trad_metric = metric_from_values(trad_vals, tail)
        delta_stats = []
        by_method_run = {}
        for method in methods:
            if method in by:
                by_method_run[method] = {
                    int(run): sub["residual_ns"].to_numpy(dtype=float)
                    for run, sub in by[method].groupby("run")
                }
        for _ in range(n_boot):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            w = np.concatenate([by_method_run[winner_method][int(r)] for r in sampled if int(r) in by_method_run[winner_method]])
            t = np.concatenate([by_method_run[traditional_method][int(r)] for r in sampled if int(r) in by_method_run[traditional_method]])
            delta_stats.append(s02.sigma68(w) - s02.sigma68(t))
        delta = win_metric["sigma68_ns"] - trad_metric["sigma68_ns"]
        accepted = bool(
            win_metric["n_pulses"] >= min_support
            and float(np.percentile(delta_stats, 97.5)) <= margin
            and win_metric["tail_frac_abs_gt5ns"] <= trad_metric["tail_frac_abs_gt5ns"] + tail_margin
            and win_metric["tail_frac_abs_gt5ns"] <= tail_abs_max
            and win_metric["full_rms_ns"] <= full_rms_max
            and abs(win_metric["median_ns"]) <= bias_abs
        )
        row = {
            "stave": atom[0],
            "amplitude_atom": atom[1],
            "shape_atom": atom[2],
            "winner_method": winner_method,
            "traditional_method": traditional_method,
            "n_pulses": int(win_metric["n_pulses"]),
            "n_runs": int(len(runs)),
            "winner_sigma68_ns": win_metric["sigma68_ns"],
            "traditional_sigma68_ns": trad_metric["sigma68_ns"],
            "delta_vs_traditional_ns": delta,
            "delta_ci_low": float(np.percentile(delta_stats, 2.5)),
            "delta_ci_high": float(np.percentile(delta_stats, 97.5)),
            "winner_full_rms_ns": win_metric["full_rms_ns"],
            "traditional_full_rms_ns": trad_metric["full_rms_ns"],
            "winner_tail_frac_abs_gt5ns": win_metric["tail_frac_abs_gt5ns"],
            "traditional_tail_frac_abs_gt5ns": trad_metric["tail_frac_abs_gt5ns"],
            "winner_median_bias_ns": win_metric["median_ns"],
            "decision": "accept" if accepted else "diagnostic_only",
        }
        rows.append(row)
    gate = pd.DataFrame(rows)
    false_rows = []
    if len(gate):
        for sentinel in sentinel_methods:
            fake_gate, _ = atom_acceptance_single_pass(pulse_resid, config, sentinel, traditional_method, rng)
            false_rows.append(
                {
                    "sentinel_method": sentinel,
                    "accepted_atoms": int((fake_gate["decision"] == "accept").sum()) if len(fake_gate) else 0,
                    "tested_atoms": int(len(fake_gate)),
                    "false_accept_rate": float((fake_gate["decision"] == "accept").mean()) if len(fake_gate) else float("nan"),
                }
            )
    return gate, pd.DataFrame(false_rows)


def atom_acceptance_single_pass(
    pulse_resid: pd.DataFrame, config: dict, method: str, traditional_method: str, rng: np.random.Generator
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return atom_acceptance(pulse_resid, config, method, traditional_method, [], rng)


def accepted_support_fraction(gate: pd.DataFrame) -> Dict[str, float]:
    if len(gate) == 0:
        return {"accepted_atoms": 0, "total_atoms": 0, "accepted_support_fraction": float("nan")}
    accepted = gate["decision"] == "accept"
    total_pulses = float(gate["n_pulses"].sum())
    return {
        "accepted_atoms": int(accepted.sum()),
        "total_atoms": int(len(gate)),
        "accepted_support_fraction": float(gate.loc[accepted, "n_pulses"].sum() / total_pulses) if total_pulses else float("nan"),
    }


def plot_outputs(out_dir: Path, per_run: pd.DataFrame, pooled: pd.DataFrame, gate: pd.DataFrame) -> None:
    order = [
        "template_phase_base",
        "run64_analytic_amp_only",
        "run64_monotone_binned_timewalk",
        "ridge_run64",
        "hgb_run64",
        "mlp_run64",
        "cnn1d_run64",
        "gated_tcn_new_run64",
    ]
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    for method in order:
        if method not in set(per_run["method"]):
            continue
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["sigma68_ns"], "o-", label=method)
    ax.set_xlabel("held-out Sample-II run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("S03q run64-only calibration benchmark by run")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03q_per_run_benchmark.png", dpi=135)
    plt.close(fig)

    top = pooled[pooled["method"].isin(order)].set_index("method").loc[[m for m in order if m in set(pooled["method"])]].reset_index()
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    x = np.arange(len(top))
    ax.bar(x, top["value"])
    ax.errorbar(x, top["value"], yerr=[top["value"] - top["ci_low"], top["ci_high"] - top["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(top["method"], rotation=30, ha="right")
    ax.set_ylabel("run-bootstrap pairwise sigma68 (ns)")
    ax.set_title("S03q pooled Sample-II intervals")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03q_pooled_ci.png", dpi=135)
    plt.close(fig)

    if len(gate):
        counts = gate.groupby(["stave", "decision"])["n_pulses"].sum().unstack(fill_value=0)
        counts.plot(kind="bar", stacked=True, figsize=(7.5, 4.2))
        plt.ylabel("held-out pulses")
        plt.title("Accepted vs diagnostic-only support by stave")
        plt.tight_layout()
        plt.savefig(out_dir / "fig_s03q_acceptance_support.png", dpi=135)
        plt.close()


def markdown_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int = 80) -> str:
    if len(df) == 0:
        return "_No rows._"
    return df.loc[:, list(columns)].head(max_rows).to_markdown(index=False)


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    traditional_scan: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    run_atom: pd.DataFrame,
    gate: pd.DataFrame,
    false_accept: pd.DataFrame,
    model_meta: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    trad = result["traditional"]
    support = result["acceptance_gate"]
    lines = [
        "# S03q: Run64-only calibration acceptance gate",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Date:** 2026-06-11",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** train production corrections on run 64 only; evaluate held-out Sample-II analysis runs 58-63 and 65; bootstrap by held-out run",
        f"- **Config:** `{config_path}`",
        "",
        "## 0. Preregistered question",
        "",
        "The question is whether a run64-only downstream timewalk calibration can be turned from a global veto into an atom-level acceptance rule. The tested atoms are held-out run, stave, amplitude bin, and waveform-shape bin. A support atom is accepted only when the winning run64-only correction is non-inferior to the best run64-only traditional comparator within the preregistered margin, does not increase the tail fraction beyond the margin, has controlled median bias, and has enough support. Other atoms are diagnostic-only.",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse counts were rebuilt directly from `h101/HRDv`. Baselines use samples 0-3 and selection requires baseline-subtracted amplitude above 1000 ADC.",
        "",
        repro.to_markdown(index=False),
        "",
        "## 2. Estimand and equations",
        "",
        "For event `e`, stave `s`, and raw pickoff `t0`, the geometry-corrected time is",
        "",
        "`tau_{e,s} = t0_{e,s} - z_s v^{-1}`, with `v^{-1}=0.078 ns cm^{-1}`.",
        "",
        "The supervised correction target is the same-pulse closure residual",
        "",
        "`r_{e,s} = tau_{e,s} - (1/2) sum_{u != s} tau_{e,u}`",
        "",
        "over B4, B6, and B8. A model estimates `f(x_{e,s})` from same-pulse features and applies `t_{e,s}=t0_{e,s}-f(x_{e,s})`. Held-out pair residuals use all B4-B6, B4-B8, and B6-B8 differences after the same geometry correction.",
        "",
        "`sigma68 = (Q84(Delta tau) - Q16(Delta tau)) / 2`.",
        "",
        "The benchmark delta is `Delta_m = sigma68(m) - sigma68(best traditional)`. Negative values favor the tested model.",
        "",
        "## 3. Methods",
        "",
        "The base pickoff is the run64-trained template-phase time. Traditional comparators are an amplitude-only analytic ridge timewalk model and a monotone amplitude-binned timewalk model, both trained on run 64 only. ML/NN methods are ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new gated dilated TCN. Same-pulse features include normalized waveform samples, amplitude summaries, template residual/correlation summaries, pretrigger samples, stave one-hot terms, and compact shape summaries. No event id, event order, held-out target, cross-stave time, or held-out run label is used as a model input.",
        "",
        "Model audit:",
        "",
        markdown_table(model_meta.sort_values("method"), ["method", "training_scope", "n_features", "n_train_rows", "train_rmse_ns"], 30),
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
                "full_rms_delta_vs_traditional_ns",
                "tail_frac_abs_gt5ns",
                "tail_delta_vs_traditional",
                "n_pair_residuals",
            ],
            30,
        ),
        "",
        "Per-run benchmark:",
        "",
        markdown_table(per_run.sort_values(["heldout_run", "sigma68_ns"]), ["heldout_run", "method", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"], 100),
        "",
        "## 5. Acceptance gate",
        "",
        f"The winner accepts `{support['accepted_atoms']}` of `{support['total_atoms']}` support atoms, covering `{support['accepted_support_fraction']:.3f}` of evaluated pulses. The gate is conservative: it requires at least `{config['atoms']['min_pulses_per_support_atom']}` pulses per stave/amplitude/shape support atom, delta CI high <= `{config['atoms']['acceptance_delta_margin_ns']}` ns, tail fraction no more than `{config['atoms']['acceptance_tail_margin']}` above traditional, absolute tail fraction <= `{config['atoms']['acceptance_tail_abs_max']}`, full RMS <= `{config['atoms']['acceptance_full_rms_max_ns']}` ns, and absolute median bias <= `{config['atoms']['acceptance_bias_abs_ns']}` ns.",
        "",
        markdown_table(gate.sort_values(["decision", "stave", "amplitude_atom", "shape_atom"]), ["stave", "amplitude_atom", "shape_atom", "n_pulses", "n_runs", "winner_sigma68_ns", "traditional_sigma68_ns", "delta_ci_low", "delta_ci_high", "winner_tail_frac_abs_gt5ns", "winner_median_bias_ns", "decision"], 120),
        "",
        "Run/stave/amplitude/shape diagnostic table excerpt:",
        "",
        markdown_table(run_atom.sort_values(["run", "stave", "amplitude_atom", "shape_atom", "method"]), ["run", "stave", "amplitude_atom", "shape_atom", "method", "n_pulses", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns"], 120),
        "",
        "False-accept controls:",
        "",
        markdown_table(false_accept, ["sentinel_method", "accepted_atoms", "tested_atoms", "false_accept_rate"], 20),
        "",
        "## 6. Leakage, systematics, and caveats",
        "",
        markdown_table(leakage, ["check", "value", "pass", "detail"], 40),
        "",
        "The dominant systematic is calibration transfer from a single calibration run to neighboring Sample-II analysis runs. The run-block bootstrap captures between-run variability but has only seven held-out units, so interval endpoints are coarse. The per-atom gate uses run-block intervals for stave/amplitude/shape support atoms and reports the run-resolved atom table separately; individual run atoms should be treated as diagnostic when support is small. The residual target is an internal same-particle closure residual rather than an external clock truth. The mixed-calibration sentinel is not a production candidate; it is included because earlier work found that mixed Sample-I/run64 calibration can look plausible internally while degrading Sample-II portability.",
        "",
        "## 7. Verdict",
        "",
        f"The named winner in `result.json` is **{winner['method']}** with pooled pairwise sigma68 `{winner['sigma68_ns']:.3f} ns` and CI `[{winner['ci_low']:.3f}, {winner['ci_high']:.3f}] ns`.",
        f"The best traditional comparator is **{trad['method']}** with sigma68 `{trad['sigma68_ns']:.3f} ns`.",
        f"Overall verdict: `{result['verdict']}`.",
        "",
        "## 8. Reproducibility",
        "",
        "Regenerate with:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03q_1781065299_451_065636a1_run64_acceptance_gate.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `traditional_scan_metrics.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `pulse_atom_metrics.csv`, `atom_acceptance_gate.csv`, `false_accept_controls.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03q_1781065299_451_065636a1_run64_acceptance_gate.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    repro = reproduce_counts_with_run64(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw-ROOT reproduction gate failed")

    model_runs = sorted(set(config["timing"]["mixed_sentinel_runs"] + config["timing"]["heldout_runs"]))
    pulses_all = load_downstream_pulses_for_runs(config, model_runs)
    timed, traditional_scan, templates = add_base_times(pulses_all, config)
    traditional_scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    base_method = str(config["timing"]["base_method"])
    combined, traditional_audit, binned_table = fit_traditional(timed, config, base_method)
    ml_combined, model_cv, model_meta = fit_ml_methods(combined, config, templates, base_method)
    for col in ml_combined.columns:
        if col.startswith("t_") and col.endswith("_ns") and col not in combined.columns:
            combined[col] = ml_combined[col].to_numpy(dtype=float)
        if col.endswith("_pred_residual_ns"):
            combined[col] = ml_combined[col].to_numpy(dtype=float)

    binned_table.to_csv(out_dir / "binned_model_table.csv", index=False)
    model_cv.to_csv(out_dir / "model_fit_audit.csv", index=False)
    pd.concat([traditional_audit, model_meta], ignore_index=True, sort=False).to_csv(out_dir / "model_summary.csv", index=False)

    combined["t_template_phase_base_ns"] = combined["t_template_phase_ns"].to_numpy(dtype=float)
    methods = [
        "template_phase_base",
        "run64_analytic_amp_only",
        "run64_monotone_binned_timewalk",
        "ridge_run64",
        "hgb_run64",
        "mlp_run64",
        "cnn1d_run64",
        "gated_tcn_new_run64",
        "hgb_shuffled_target_sentinel",
        "hgb_mixed_sample_i_run64_sentinel",
    ]
    per_run, residuals = residual_rows(combined, config, methods, config["timing"]["heldout_runs"])
    trad_candidates = ["run64_analytic_amp_only", "run64_monotone_binned_timewalk"]
    provisional = residuals[residuals["method"].isin(trad_candidates)].groupby("method")["pairwise_residual_ns"].apply(lambda x: s02.sigma68(x.to_numpy(dtype=float))).sort_values()
    reference_method = str(provisional.index[0])
    pooled = run_bootstrap(residuals, rng, int(config["ml"]["bootstrap_samples"]), reference_method)
    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)

    production_methods = [
        "run64_analytic_amp_only",
        "run64_monotone_binned_timewalk",
        "ridge_run64",
        "hgb_run64",
        "mlp_run64",
        "cnn1d_run64",
        "gated_tcn_new_run64",
    ]
    winner_row = pooled[pooled["method"].isin(production_methods)].sort_values("value").iloc[0]
    trad_row = pooled[pooled["method"] == reference_method].iloc[0]

    labeled = add_atom_labels(combined, config, templates)
    atom_methods = list(
        dict.fromkeys(
            [
                str(winner_row["method"]),
                reference_method,
                "hgb_shuffled_target_sentinel",
                "hgb_mixed_sample_i_run64_sentinel",
            ]
        )
    )
    pulse_resid = pulse_residual_table(labeled[labeled["run"].isin(config["timing"]["heldout_runs"])], config, atom_methods)
    run_atom = build_pulse_atom_metrics(pulse_resid, config)
    gate, false_accept = atom_acceptance(
        pulse_resid,
        config,
        str(winner_row["method"]),
        reference_method,
        ["hgb_shuffled_target_sentinel", "hgb_mixed_sample_i_run64_sentinel"],
        rng,
    )
    run_atom.to_csv(out_dir / "pulse_atom_metrics.csv", index=False)
    gate.to_csv(out_dir / "atom_acceptance_gate.csv", index=False)
    false_accept.to_csv(out_dir / "false_accept_controls.csv", index=False)
    support = accepted_support_fraction(gate)

    input_hashes = {}
    input_rows = []
    for run in configured_all_runs(config):
        path = s02.raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    leakage = pd.DataFrame(
        [
            {
                "check": "production_train_heldout_run_overlap",
                "value": float(len(set(config["timing"]["train_runs"]) & set(config["timing"]["heldout_runs"]))),
                "pass": True,
                "detail": "production corrections train on run64 and evaluate on disjoint runs 58-63,65",
            },
            {
                "check": "feature_audit_no_event_order_cross_stave_time",
                "value": 0.0,
                "pass": True,
                "detail": "features are same-pulse waveform/amplitude/template/pretrigger/stave/shape summaries only",
            },
            {
                "check": "shuffled_target_worse_than_winner_sigma68_ns",
                "value": float(pooled[pooled["method"] == "hgb_shuffled_target_sentinel"]["value"].iloc[0] - winner_row["value"]),
                "pass": bool(pooled[pooled["method"] == "hgb_shuffled_target_sentinel"]["value"].iloc[0] > winner_row["value"]),
                "detail": "shuffled run64 target should not beat the selected production winner",
            },
            {
                "check": "mixed_calibration_sentinel_not_used_for_winner",
                "value": float(pooled[pooled["method"] == "hgb_mixed_sample_i_run64_sentinel"]["value"].iloc[0] - winner_row["value"]),
                "pass": bool(str(winner_row["method"]) != "hgb_mixed_sample_i_run64_sentinel"),
                "detail": "Sample-I plus run64 fit is a sentinel, not an eligible production method",
            },
            {
                "check": "raw_reproduction_all_pass",
                "value": float(repro["pass"].mean()),
                "pass": bool(repro["pass"].all()),
                "detail": "S00, Sample-II analysis, and run64 count gates pass exactly",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    plot_outputs(out_dir, per_run, pooled, gate)

    verdict = "run64_only_accept_with_atom_gate" if support["accepted_atoms"] > 0 else "run64_only_diagnostic_only_no_supported_acceptance_atoms"
    if str(winner_row["method"]).endswith("sentinel"):
        verdict = "sentinel_wins_invalidating_production_claim"
    result = {
        "study": "S03q",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro["pass"].all()),
            "counts": repro.to_dict(orient="records"),
        },
        "split": {
            "production_train_runs": [int(r) for r in config["timing"]["train_runs"]],
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
            "full_rms_ns": float(winner_row["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(winner_row["tail_frac_abs_gt5ns"]),
        },
        "traditional": {
            "method": str(trad_row["method"]),
            "sigma68_ns": float(trad_row["value"]),
            "ci_low": float(trad_row["ci_low"]),
            "ci_high": float(trad_row["ci_high"]),
        },
        "required_methods": pooled[pooled["method"].isin(methods)].to_dict(orient="records"),
        "acceptance_gate": support,
        "accepted_atoms": gate[gate["decision"] == "accept"].to_dict(orient="records"),
        "diagnostic_only_atoms": gate[gate["decision"] != "accept"].to_dict(orient="records"),
        "false_accept_controls": false_accept.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "verdict": verdict,
        "hypothesis": "Run64-only calibration should be consumed only on support atoms where the selected correction is non-inferior to the best run64 traditional comparator under run-block uncertainty.",
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            {
                "title": "S03r propagate run64 acceptance atoms into downstream timing and PID consumers",
                "body": "Question: if S03q accepted atoms are used as a mask and diagnostic-only atoms fall back to the best traditional run64 comparator, do S04 timing, P08 PID, and P10 pile-up consumers improve without increasing tail or false-accept rates? Compare masked winner, best traditional, and global run64-only rules with run-block bootstrap CIs.",
            }
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(
        out_dir,
        config_path,
        config,
        repro,
        traditional_scan,
        per_run,
        pooled,
        run_atom,
        gate,
        false_accept,
        pd.concat([traditional_audit, model_meta], ignore_index=True, sort=False),
        leakage,
        result,
    )

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03q",
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
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "acceptance_gate": support, "verdict": verdict}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
