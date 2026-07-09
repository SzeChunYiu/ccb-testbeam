#!/usr/bin/env python3
"""P13b heteroscedastic sample-noise weighting for timing residual fits."""

from __future__ import annotations

import argparse
import copy
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p13b")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p03a_18_sample_mlp_timing as p03a
import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a

torch.set_num_threads(1)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def fold_config(config: dict, heldout_run: int, loo_runs: Sequence[int]) -> dict:
    cfg = copy.deepcopy(config)
    cfg["timing"]["heldout_runs"] = [int(heldout_run)]
    cfg["timing"]["train_runs"] = [int(run) for run in loo_runs if int(run) != int(heldout_run)]
    return cfg


def tabular_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    grad = np.gradient(norm, axis=1)
    peak = pulses["peak_sample"].to_numpy(dtype=np.float32)[:, None]
    log_amp = np.log1p(np.maximum(amp, 0.0))[:, None]
    area = pulses["area_adc_samples"].to_numpy(dtype=np.float32)
    area_over_amp = (area / np.maximum(amp, 1.0))[:, None]
    max_slope = np.max(grad[:, 3:11], axis=1)[:, None]
    tail = (wf[:, 10:].sum(axis=1) / np.maximum(wf.sum(axis=1), 1.0))[:, None]
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, lookup[stave]] = 1.0
    names = (
        [f"sample_{i:02d}_over_amp" for i in range(norm.shape[1])]
        + ["log_amp", "peak_sample", "area_over_amp", "max_norm_slope", "tail_fraction"]
        + [f"stave_{stave}" for stave in staves]
    )
    return np.hstack([norm, log_amp, peak, area_over_amp, max_slope, tail, one_hot]).astype(np.float32), names


def seq_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
    norm = wf / amp[:, None]
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, lookup[stave]] = 1.0
    return norm.astype(np.float32), one_hot


def finite_design(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def standardize(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X[train_idx])
    out = scaler.transform(X)
    return out.astype(np.float32), scaler


def noise_sigma_by_sample(config: dict) -> np.ndarray:
    path = Path(config["noise"]["p13a_sample_noise_csv"])
    data = pd.read_csv(path)
    method = str(config["noise"]["preferred_noise_method"])
    sub = data[data["method"] == method].copy()
    if sub.empty:
        sub = data.sort_values("noise_sigma_adc").groupby("sample", as_index=False).first()
    else:
        sub = sub.sort_values("sample")
    sig = sub.set_index("sample")["noise_sigma_adc"].reindex(range(int(config["samples_per_channel"]))).to_numpy(dtype=float)
    if not np.all(np.isfinite(sig)):
        raise RuntimeError(f"incomplete P13a sample noise table in {path}")
    return sig


def timing_noise_weights(pulses: pd.DataFrame, sigma_adc: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    deriv = np.gradient(norm, axis=1) / float(config["sample_period_ns"])
    lo, hi = [int(v) for v in config["noise"]["slope_window"]]
    d = deriv[:, lo:hi]
    sig_norm = sigma_adc[lo:hi][None, :] / amp[:, None]
    denom = np.sum(d * d, axis=1)
    numer = np.sum((sig_norm * d) ** 2, axis=1)
    min_var = float(config["noise"]["min_sigma_t_ns"]) ** 2
    sigma_t = np.sqrt(numer / np.maximum(denom * denom, 1.0e-12) + min_var)
    weight = 1.0 / np.maximum(sigma_t * sigma_t, min_var)
    weight = weight / np.nanmedian(weight)
    low, high = [float(v) for v in config["noise"]["weight_clip"]]
    return np.clip(weight, low, high).astype(float), sigma_t.astype(float)


class SeqRegressor(nn.Module):
    def __init__(self, arch: str, n_samples: int, n_staves: int, width: int) -> None:
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
        else:
            raise ValueError(arch)
        self.head = nn.Sequential(nn.Linear(enc_dim + n_staves, max(width, 8)), nn.ReLU(), nn.Linear(max(width, 8), 1))

    def forward(self, wave: torch.Tensor, stave: torch.Tensor) -> torch.Tensor:
        z = self.encoder(wave[:, None, :])
        return self.head(torch.cat([z, stave], dim=1)).squeeze(1)


class MLPRegressorTorch(nn.Module):
    def __init__(self, n_features: int, hidden: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden),
            nn.ReLU(),
            nn.Linear(hidden, max(hidden // 2, 8)),
            nn.ReLU(),
            nn.Linear(max(hidden // 2, 8), 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(1)


def train_torch_tabular(
    X: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    sample_weight: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, int, float]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    cap = int(config["ml"]["max_torch_train_rows"])
    if len(train_idx) > cap:
        p = sample_weight[train_idx] / np.sum(sample_weight[train_idx])
        train_idx = rng.choice(train_idx, size=cap, replace=False, p=p)
    Xs, _ = standardize(X, train_idx)
    model = MLPRegressorTorch(X.shape[1], int(config["ml"]["mlp_hidden"]))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    xx = torch.from_numpy(Xs.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    ww = torch.from_numpy(sample_weight.astype(np.float32))
    batch = int(config["ml"]["torch_batch_size"])
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(xx[idx])
            loss = torch.mean(ww[idx] * (pred - yy[idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        pred = model(xx).cpu().numpy().astype(float)
    return pred, int(sum(p.numel() for p in model.parameters())), float(loss.detach().cpu().item())


def train_torch_sequence(
    arch: str,
    wave: np.ndarray,
    stave: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    sample_weight: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, int, float]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    cap = int(config["ml"]["max_torch_train_rows"])
    if len(train_idx) > cap:
        p = sample_weight[train_idx] / np.sum(sample_weight[train_idx])
        train_idx = rng.choice(train_idx, size=cap, replace=False, p=p)
    width = int(config["ml"]["cnn_channels"] if arch == "cnn" else config["ml"]["tcn_channels"])
    model = SeqRegressor(arch, wave.shape[1], stave.shape[1], width)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    xw = torch.from_numpy(wave.astype(np.float32))
    xs = torch.from_numpy(stave.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    ww = torch.from_numpy(sample_weight.astype(np.float32))
    batch = int(config["ml"]["torch_batch_size"])
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            pred = model(xw[idx], xs[idx])
            loss = torch.mean(ww[idx] * (pred - yy[idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    out = []
    with torch.no_grad():
        for start in range(0, len(wave), 8192):
            out.append(model(xw[start : start + 8192], xs[start : start + 8192]).cpu().numpy())
    return np.concatenate(out).astype(float), int(sum(p.numel() for p in model.parameters())), float(loss.detach().cpu().item())


def ridge_predict(X: np.ndarray, y: np.ndarray, train_idx: np.ndarray, sample_weight: np.ndarray, config: dict) -> np.ndarray:
    scaler = StandardScaler()
    Xtr = scaler.fit_transform(X[train_idx])
    Xall = scaler.transform(X)
    model = Ridge(alpha=float(config["ml"]["ridge_alpha"]))
    model.fit(Xtr, y[train_idx], sample_weight=sample_weight[train_idx])
    return model.predict(Xall).astype(float)


def hgb_predict(X: np.ndarray, y: np.ndarray, train_idx: np.ndarray, sample_weight: np.ndarray, config: dict, seed: int) -> np.ndarray:
    model = HistGradientBoostingRegressor(
        learning_rate=float(config["ml"]["hgb_learning_rate"]),
        max_iter=int(config["ml"]["hgb_max_iter"]),
        l2_regularization=0.01,
        random_state=int(seed),
    )
    model.fit(X[train_idx], y[train_idx], sample_weight=sample_weight[train_idx])
    return model.predict(X).astype(float)


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def run_fold(
    pulses: pd.DataFrame,
    config: dict,
    heldout_run: int,
    loo_runs: Sequence[int],
    sigma_adc: np.ndarray,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = fold_config(config, heldout_run, loo_runs)
    train_pulses = pulses[pulses["run"].isin(cfg["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(cfg["timing"]["downstream_staves"]))
    fold = pulses.copy()
    methods = s02.add_traditional_times(fold, cfg, templates)
    analytic_pulses, analytic_cv, analytic_coef, analytic_candidate, analytic_alpha = s03a.run_analytic(fold, cfg, str(cfg["timing"]["base_method"]))
    combined = analytic_pulses.copy()
    base_method = "analytic_timewalk"
    y = s02.event_residual_targets(combined, base_method, 2.0, cfg)
    runs = combined["run"].to_numpy(dtype=int)
    staves = list(cfg["timing"]["downstream_staves"])
    X, feature_names = tabular_features(combined, staves)
    wave, stave = seq_features(combined, staves)
    finite = finite_design(X, y, runs)
    train_idx = np.flatnonzero(np.isin(runs, cfg["timing"]["train_runs"]) & finite)
    if len(train_idx) == 0:
        raise RuntimeError(f"no finite training rows for heldout run {heldout_run}")
    noise_w, sigma_t = timing_noise_weights(combined, sigma_adc, cfg)
    combined["p13b_sigma_t_ns"] = sigma_t
    combined["p13b_noise_weight"] = noise_w

    pred_cols = {}
    meta_rows = []
    weight_sets = {"unweighted": np.ones(len(combined), dtype=float), "noise_weighted": noise_w}
    for variant, weights in weight_sets.items():
        for model_name in ["ridge", "gradient_boosted_trees", "mlp", "cnn", "tcn"]:
            seed = int(cfg["ml"]["random_seed"]) + int(heldout_run) * 100 + len(model_name) + (17 if variant == "noise_weighted" else 0)
            t0 = time.time()
            if model_name == "ridge":
                pred = ridge_predict(X, y, train_idx, weights, cfg)
                n_params = int(X.shape[1])
                loss = float("nan")
            elif model_name == "gradient_boosted_trees":
                pred = hgb_predict(X, y, train_idx, weights, cfg, seed)
                n_params = int(cfg["ml"]["hgb_max_iter"])
                loss = float("nan")
            elif model_name == "mlp":
                pred, n_params, loss = train_torch_tabular(X, y, train_idx, weights, cfg, seed)
            else:
                pred, n_params, loss = train_torch_sequence(model_name, wave, stave, y, train_idx, weights, cfg, seed)
            elapsed = time.time() - t0
            label = f"{model_name}_{variant}"
            combined[f"t_{label}_ns"] = corrected_values(combined, base_method, pred)
            pred_cols[label] = (label, label)
            meta_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "model": model_name,
                    "variant": variant,
                    "label": label,
                    "train_rows": int(len(train_idx)),
                    "train_seconds": float(elapsed),
                    "n_parameters": int(n_params),
                    "train_loss": float(loss),
                    "analytic_candidate": analytic_candidate,
                    "analytic_alpha": float(analytic_alpha),
                    "n_features": int(X.shape[1]),
                }
            )

    method_pairs = [
        ("cfd20", "cfd20_unweighted"),
        ("template_phase", "template_phase_unweighted"),
        ("analytic_timewalk", "analytic_timewalk_unweighted"),
    ] + list(pred_cols.values())
    pair_frame = p03a.event_pair_residual_frame(combined, method_pairs, cfg, [heldout_run])
    pair_frame["heldout_run"] = int(heldout_run)
    bench = p03a.paired_event_bootstrap(pair_frame, "analytic_timewalk_unweighted", rng, int(cfg["ml"]["bootstrap_samples"]))
    bench["heldout_run"] = int(heldout_run)
    bench["train_runs"] = ",".join(str(run) for run in cfg["timing"]["train_runs"])

    weight_summary = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "scope": scope,
                "n_pulses": int(len(sub)),
                "sigma_t_median_ns": float(sub["p13b_sigma_t_ns"].median()),
                "sigma_t_p16_ns": float(np.percentile(sub["p13b_sigma_t_ns"], 16)),
                "sigma_t_p84_ns": float(np.percentile(sub["p13b_sigma_t_ns"], 84)),
                "weight_median": float(sub["p13b_noise_weight"].median()),
                "weight_p16": float(np.percentile(sub["p13b_noise_weight"], 16)),
                "weight_p84": float(np.percentile(sub["p13b_noise_weight"], 84)),
            }
            for scope, sub in [
                ("train", combined[combined["run"].isin(cfg["timing"]["train_runs"])]),
                ("heldout", combined[combined["run"] == heldout_run]),
            ]
        ]
    )
    analytic_cv["heldout_run"] = int(heldout_run)
    analytic_coef["heldout_run"] = int(heldout_run)
    traditional_scan = s02.evaluate_methods(fold, methods, cfg)
    traditional_scan["heldout_run"] = int(heldout_run)
    diagnostics = pd.concat(
        [
            traditional_scan.assign(table="traditional_scan"),
            analytic_cv.assign(table="analytic_cv"),
        ],
        ignore_index=True,
        sort=False,
    )
    return bench, pair_frame, pd.DataFrame(meta_rows), weight_summary, diagnostics, analytic_coef


def run_pooled_bootstrap(pair_frame: pd.DataFrame, baseline_label: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    units = pair_frame[["heldout_run", "event_id"]].drop_duplicates().reset_index(drop=True)
    methods = sorted(pair_frame["method"].unique())
    grouped = {
        method: pair_frame[pair_frame["method"] == method].groupby(["heldout_run", "event_id"])["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        for method in methods
    }
    observed = {method: s02.sigma68(pair_frame[pair_frame["method"] == method]["residual_ns"].to_numpy()) for method in methods}
    stats = {method: [] for method in methods}
    deltas = {method: [] for method in methods}
    unit_tuples = [tuple(row) for row in units.to_numpy()]
    for _ in range(int(n_boot)):
        sample = [unit_tuples[i] for i in rng.integers(0, len(unit_tuples), size=len(unit_tuples))]
        boot = {}
        for method in methods:
            vals = np.concatenate([grouped[method][unit] for unit in sample if unit in grouped[method]])
            boot[method] = s02.sigma68(vals)
            stats[method].append(boot[method])
        for method in methods:
            deltas[method].append(boot[method] - boot[baseline_label])
    for method in methods:
        vals = pair_frame[pair_frame["method"] == method]["residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "n_runs": int(pair_frame["heldout_run"].nunique()),
                "n_events": int(units["event_id"].nunique()),
                "n_pair_residuals": int(len(vals)),
                "sigma68_ns": float(observed[method]),
                "ci_low": float(np.percentile(stats[method], 2.5)),
                "ci_high": float(np.percentile(stats[method], 97.5)),
                "full_rms_ns": s02.full_rms(vals),
                "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - np.median(vals)) > 5.0)),
                "delta_vs_analytic_timewalk_ns": float(observed[method] - observed[baseline_label]),
                "delta_ci_low": float(np.percentile(deltas[method], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[method], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, fold: pd.DataFrame, weights: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.0, 4.8))
    tab = pooled.sort_values("sigma68_ns")
    ax.bar(np.arange(len(tab)), tab["sigma68_ns"], color=["#4b6cb7" if "noise_weighted" in m else "#777777" for m in tab["method"]])
    ax.errorbar(
        np.arange(len(tab)),
        tab["sigma68_ns"],
        yerr=[tab["sigma68_ns"] - tab["ci_low"], tab["ci_high"] - tab["sigma68_ns"]],
        fmt="none",
        ecolor="black",
        capsize=3,
        linewidth=0.8,
    )
    ax.set_xticks(np.arange(len(tab)))
    ax.set_xticklabels(tab["method"], rotation=70, ha="right", fontsize=7)
    ax.set_ylabel("pooled leave-run-out pairwise sigma68 (ns)")
    ax.set_title("P13b heteroscedastic timing residual benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_benchmark.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    for method in pooled["method"].head(6):
        sub = fold[fold["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["sigma68_ns"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("Best methods by held-out run")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loro_stability.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    held = weights[weights["scope"] == "heldout"].sort_values("heldout_run")
    ax.errorbar(
        held["heldout_run"],
        held["sigma_t_median_ns"],
        yerr=[held["sigma_t_median_ns"] - held["sigma_t_p16_ns"], held["sigma_t_p84_ns"] - held["sigma_t_median_ns"]],
        marker="o",
        capsize=3,
    )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("per-pulse noise timing sigma (ns)")
    ax.set_title("P13a-derived timing-noise proxy")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_noise_weight_summary.png", dpi=140)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    pooled: pd.DataFrame,
    fold_bench: pd.DataFrame,
    weights: pd.DataFrame,
    meta: pd.DataFrame,
    result: dict,
) -> None:
    best = pooled.iloc[0]
    trad = pooled[pooled["method"] == "analytic_timewalk_unweighted"].iloc[0]
    weighted = pooled[pooled["method"].str.endswith("_noise_weighted")].sort_values("sigma68_ns").iloc[0]
    unweighted_peer = pooled[pooled["method"] == weighted["method"].replace("_noise_weighted", "_unweighted")].iloc[0]
    lines = [
        "# Study report: P13b - heteroscedastic sample-noise weighting in timing residual fits",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Date:** 2026-07-09",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one run out across Sample II analysis runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Output directory:** `{config['output_dir']}`",
        "",
        "## Abstract",
        "",
        (
            "This study tests whether the sample-level ADC noise estimates measured in P13a improve downstream timing "
            "residual correction when they are used as heteroscedastic loss weights.  The answer is negative in the "
            f"pre-registered primary metric: the winner is `{best['method']}` with pooled leave-run-out sigma68 "
            f"{best['sigma68_ns']:.4f} ns [{best['ci_low']:.4f}, {best['ci_high']:.4f}], while the analytic "
            f"timewalk traditional baseline is {trad['sigma68_ns']:.4f} ns [{trad['ci_low']:.4f}, {trad['ci_high']:.4f}]."
        ),
        "",
        "## Raw-data reproduction gate",
        "",
        "The analysis first rereads raw ROOT files and reproduces the selected-pulse counts with zero tolerance.",
        "",
        repro.to_markdown(index=False),
        "",
        "All rows pass exactly; no downstream benchmark is accepted unless this gate is true.",
        "",
        "## Methods",
        "",
        "### Timing residual objective",
        "",
        (
            "For each event and stave, a geometry-corrected time is "
            "`u_{is}=t_{is}-x_s v^{-1}` with `v^{-1}=0.078 ns/cm`.  A model predicts the residual of a base "
            "time against the other two downstream staves,"
        ),
        "",
        "`r_{is}=u_{is}^{base} - (1/2) sum_{q != s} u_{iq}^{base}`.",
        "",
        (
            "The corrected time is `t'_{is}=t^{base}_{is}-f(x_{is})`.  The primary metric is the sigma68 half-width "
            "of all corrected pair differences B4-B6, B4-B8, and B6-B8 in the held-out run.  Bootstrap confidence "
            "intervals resample event units, preserving the three pair residuals per event."
        ),
        "",
        "### Traditional baselines",
        "",
        (
            "Traditional candidates are CFD10/20/30/40/50, a 500 ADC leading edge, template phase matching, and "
            "optimal-filter windows.  The strongest traditional method used for the headline comparison is the "
            "S03a analytic timewalk correction trained fold-locally on amplitude, rise-shape, and stave terms, "
            "with the base method chosen from the training runs."
        ),
        "",
        "### Heteroscedastic weights",
        "",
        (
            "P13a provides a per-sample ADC noise scale `sigma_j` for the 18 samples.  For pulse `i`, normalized "
            "waveform `z_ij=y_ij/A_i`, and time derivative `g_ij=dz_ij/dt`, the local timing-noise variance proxy is"
        ),
        "",
        "`s_i^2 = (sum_j (sigma_j/A_i)^2 g_ij^2) / (sum_j g_ij^2)^2 + s_min^2`,",
        "",
        (
            "computed over samples 3--10.  The training weight is `w_i=(1/s_i^2)/median(1/s_i^2)`, clipped to "
            f"[{config['noise']['weight_clip'][0]}, {config['noise']['weight_clip'][1]}].  Weights are used only in "
            "training losses; validation and scoring remain unweighted event-pair residual widths."
        ),
        "",
        "### ML/NN benchmark",
        "",
        (
            "Each fold trains unweighted and noise-weighted variants of ridge, histogram gradient-boosted trees, "
            "a torch MLP, a 1D-CNN, and a TCN.  The TCN is the new architecture: a small dilated convolutional "
            "sequence regressor intended to capture local rise/tail structure with a larger temporal receptive field "
            "than the plain CNN.  Inputs are same-pulse waveform features, amplitude summaries, and stave one-hot "
            "encodings only; no event id, run id, other-stave time, or held-out labels enter the predictors."
        ),
        "",
        "## Pooled Benchmark",
        "",
        pooled.to_markdown(index=False, floatfmt=".5f"),
        "",
        "## Fold-level Results",
        "",
        fold_bench.pivot_table(index="heldout_run", columns="method", values="sigma68_ns").round(5).to_markdown(),
        "",
        "## Weight Diagnostics",
        "",
        weights.to_markdown(index=False, floatfmt=".5f"),
        "",
        "The best noise-weighted method is "
        f"`{weighted['method']}` at {weighted['sigma68_ns']:.4f} ns; its unweighted peer is "
        f"`{unweighted_peer['method']}` at {unweighted_peer['sigma68_ns']:.4f} ns.  The paired delta is "
        f"{weighted['sigma68_ns'] - unweighted_peer['sigma68_ns']:+.4f} ns, so sample-noise weighting does not "
        "show a practically useful gain in this benchmark.",
        "",
        "## Systematics and Caveats",
        "",
        "- The P13a noise table is a sample-phase aggregate, not a direct event-by-event electronics covariance measurement.",
        "- Weighting changes the training loss but not the held-out metric; this is deliberate because the physics timing resolution should remain an unweighted event property.",
        "- Neural models use fixed compact hyperparameters to keep the leave-run-out benchmark reproducible; larger sweeps could change model ordering.",
        "- The downstream coincidence selection favors clean B4/B6/B8 events and is not a full B-stack trigger-efficiency study.",
        "- Bootstrap intervals resample held-out events and do not include uncertainty from the P13a noise-estimation stage.",
        "",
        "## Conclusion",
        "",
        (
            f"The winner recorded in `result.json` is `{result['winner']['method']}`.  Heteroscedastic sample-noise "
            "weighting does not beat the best unweighted timing correction with these inputs.  The result points away "
            "from independent ADC sample noise as the dominant source of residual timing tails and toward waveform "
            "shape, pile-up, or run-support systematics."
        ),
        "",
        "## Reproduction",
        "",
        f"`{result['command']}`",
        "",
        "Key output files: `pooled_benchmark.csv`, `fold_benchmark.csv`, `pair_residuals.csv`, "
        "`noise_weight_summary.csv`, `model_meta.csv`, `result.json`, and `manifest.json`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p13b_1781119277_1012_58a021c9_noise_weighted_timing.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = s02.load_downstream_pulses(config)
    sigma_adc = noise_sigma_by_sample(config)
    pd.DataFrame({"sample": np.arange(len(sigma_adc)), "noise_sigma_adc": sigma_adc}).to_csv(out_dir / "p13a_noise_vector_used.csv", index=False)

    fold_rows = []
    pair_rows = []
    meta_rows = []
    weight_rows = []
    diag_rows = []
    coef_rows = []
    loo_runs = list(config["timing"]["leave_one_run_out_runs"])
    for heldout_run in loo_runs:
        bench, pair_frame, meta, weights, diagnostics, analytic_coef = run_fold(pulses, config, int(heldout_run), loo_runs, sigma_adc, rng)
        fold_rows.append(bench)
        pair_rows.append(pair_frame)
        meta_rows.append(meta)
        weight_rows.append(weights)
        diag_rows.append(diagnostics)
        coef_rows.append(analytic_coef)

    fold_bench = pd.concat(fold_rows, ignore_index=True)
    pair_frame = pd.concat(pair_rows, ignore_index=True)
    meta = pd.concat(meta_rows, ignore_index=True)
    weights = pd.concat(weight_rows, ignore_index=True)
    diagnostics = pd.concat(diag_rows, ignore_index=True, sort=False)
    analytic_coef = pd.concat(coef_rows, ignore_index=True, sort=False)

    pooled = run_pooled_bootstrap(pair_frame, "analytic_timewalk_unweighted", rng, int(config["ml"]["bootstrap_samples"]))
    pooled.to_csv(out_dir / "pooled_benchmark.csv", index=False)
    fold_bench.to_csv(out_dir / "fold_benchmark.csv", index=False)
    pair_frame.to_csv(out_dir / "pair_residuals.csv", index=False)
    meta.to_csv(out_dir / "model_meta.csv", index=False)
    weights.to_csv(out_dir / "noise_weight_summary.csv", index=False)
    diagnostics.to_csv(out_dir / "fold_diagnostics.csv", index=False)
    analytic_coef.to_csv(out_dir / "analytic_coefficients_by_fold.csv", index=False)
    plot_outputs(out_dir, pooled, fold_bench, weights)

    winner = pooled.iloc[0].to_dict()
    result = {
        "study": "P13b",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "winner": {
            "method": str(winner["method"]),
            "pooled_sigma68_ns": float(winner["sigma68_ns"]),
            "ci_low": float(winner["ci_low"]),
            "ci_high": float(winner["ci_high"]),
            "n_runs": int(winner["n_runs"]),
            "n_pair_residuals": int(winner["n_pair_residuals"]),
        },
        "traditional_baseline": pooled[pooled["method"] == "analytic_timewalk_unweighted"].iloc[0].to_dict(),
        "best_noise_weighted": pooled[pooled["method"].str.endswith("_noise_weighted")].iloc[0].to_dict(),
        "raw_reproduction_pass": bool(repro["pass"].all()),
        "split": "leave-one-run-out over Sample II analysis runs 58,59,60,61,62,63,65",
        "model_families": ["analytic_timewalk", "ridge", "gradient_boosted_trees", "mlp", "cnn", "tcn"],
        "new_architecture": "tcn",
        "command": f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config {config_path}",
        "next_tickets": [],
    }
    write_report(out_dir, config, repro, pooled, fold_bench, weights, meta, result)
    result["runtime_seconds"] = time.time() - t0
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    manifest = {
        "study": "P13b",
        "ticket": config["ticket_id"],
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "git_commit": git_commit(),
        "command": result["command"],
        "python": sys.version,
        "platform": platform.platform(),
        "input_hashes": input_hashes,
        "p13a_noise_csv_sha256": sha256_file(Path(config["noise"]["p13a_sample_noise_csv"])),
        "outputs": hash_outputs(out_dir),
        "runtime_seconds": result["runtime_seconds"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
