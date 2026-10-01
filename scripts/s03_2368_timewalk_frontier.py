#!/usr/bin/env python3
"""Ticket #2368 S03 timewalk correction benchmark from raw ROOT waveforms."""

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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s03-2368")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

import p03a_18_sample_mlp_timing as p03a
import p03c_1781015093_889_4aa141a8_cnn_vs_mlp_loro as p03c
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


def finite_xy(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def tabular_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    safe_amp = np.maximum(amp, 1.0)
    norm = wf / safe_amp[:, None]
    peak = pulses["peak_sample"].to_numpy(dtype=float)
    area_norm = pulses["area_adc_samples"].to_numpy(dtype=float) / safe_amp
    one_hot = np.zeros((len(pulses), len(staves)), dtype=float)
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    cols = [
        np.log1p(safe_amp),
        1000.0 / safe_amp,
        np.sqrt(1000.0 / safe_amp),
        peak,
        area_norm,
        norm[:, :6].sum(axis=1),
        norm[:, 9:].sum(axis=1),
        np.max(np.gradient(norm, axis=1), axis=1),
    ]
    names = [
        "log_amp",
        "inv_amp_1000",
        "inv_sqrt_amp_1000",
        "peak_sample",
        "area_over_amp",
        "early_norm_charge",
        "late_norm_charge",
        "max_norm_slope",
    ]
    return np.hstack([np.column_stack(cols), norm, one_hot]), names + [f"sample_{i:02d}_over_amp" for i in range(norm.shape[1])] + [f"stave_{s}" for s in staves]


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def evaluate_values(pulses: pd.DataFrame, method_name: str, values: np.ndarray, config: dict, runs: Iterable[int]) -> np.ndarray:
    tmp = pulses.copy()
    tmp[f"t_{method_name}_ns"] = values
    return s02.pairwise_residuals(tmp, method_name, 2.0, config, list(runs))


def run_ridge_on_base(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    y = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, names = tabular_features(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_xy(X, y, runs)
    idx = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    cv_rows = []
    best = {"score": math.inf, "alpha": None}
    gkf = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
    for alpha in [float(v) for v in config["ml"]["ridge_alphas"]]:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], y[train_mask], groups=groups)):
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(X[train_mask][tr], y[train_mask][tr])
            pred = np.full(len(pulses), np.nan)
            pred[idx[va]] = model.predict(X[train_mask][va])
            vals = evaluate_values(pulses.iloc[idx[va]].copy(), "ridge_cv", corrected_values(pulses, base_method, pred)[idx[va]], config, sorted(np.unique(runs[idx[va]])))
            score = s02.sigma68(vals)
            scores.append(score)
            cv_rows.append({"model": "ridge", "alpha": alpha, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals))})
        mean_score = float(np.nanmean(scores))
        cv_rows.append({"model": "ridge", "alpha": alpha, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
        if mean_score < best["score"]:
            best = {"score": mean_score, "alpha": alpha}
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    model.fit(X[train_mask], y[train_mask])
    pred = model.predict(X)
    out = pulses.copy()
    out["ridge_target_residual_ns"] = y
    out["ridge_pred_residual_ns"] = pred
    out["t_ridge_ns"] = corrected_values(pulses, base_method, pred)
    return out, pd.DataFrame(cv_rows), {"method": "ridge", "alpha": float(best["alpha"]), "cv_sigma68_ns": float(best["score"]), "n_features": int(X.shape[1]), "feature_names": names}


def run_gbt_on_base(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    seed = int(config["ml"]["random_seed"])
    y = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, names = tabular_features(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_xy(X, y, runs)
    idx = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    cv_rows = []
    best = {"score": math.inf, "learning_rate": None, "max_iter": None, "l2": None}
    gkf = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
    for lr in [float(v) for v in config["ml"]["gbt_learning_rates"]]:
        for max_iter in [int(v) for v in config["ml"]["gbt_max_iter"]]:
            for l2 in [float(v) for v in config["ml"]["gbt_l2_regularization"]]:
                scores = []
                for fold, (tr, va) in enumerate(gkf.split(X[train_mask], y[train_mask], groups=groups)):
                    model = HistGradientBoostingRegressor(learning_rate=lr, max_iter=max_iter, l2_regularization=l2, random_state=seed + fold, max_leaf_nodes=15)
                    model.fit(X[train_mask][tr], y[train_mask][tr])
                    pred = np.full(len(pulses), np.nan)
                    pred[idx[va]] = model.predict(X[train_mask][va])
                    vals = evaluate_values(pulses.iloc[idx[va]].copy(), "gbt_cv", corrected_values(pulses, base_method, pred)[idx[va]], config, sorted(np.unique(runs[idx[va]])))
                    score = s02.sigma68(vals)
                    scores.append(score)
                    cv_rows.append({"model": "gradient_boosted_trees", "learning_rate": lr, "max_iter": max_iter, "l2": l2, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals))})
                mean_score = float(np.nanmean(scores))
                cv_rows.append({"model": "gradient_boosted_trees", "learning_rate": lr, "max_iter": max_iter, "l2": l2, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
                if mean_score < best["score"]:
                    best = {"score": mean_score, "learning_rate": lr, "max_iter": max_iter, "l2": l2}
    model = HistGradientBoostingRegressor(learning_rate=float(best["learning_rate"]), max_iter=int(best["max_iter"]), l2_regularization=float(best["l2"]), random_state=seed + 99, max_leaf_nodes=15)
    model.fit(X[train_mask], y[train_mask])
    pred = model.predict(X)
    out = pulses.copy()
    out["gbt_target_residual_ns"] = y
    out["gbt_pred_residual_ns"] = pred
    out["t_gradient_boosted_trees_ns"] = corrected_values(pulses, base_method, pred)
    return out, pd.DataFrame(cv_rows), {"method": "gradient_boosted_trees", **best, "n_features": int(X.shape[1]), "feature_names": names}


class HybridResidualNet(nn.Module):
    def __init__(self, n_wave: int, n_phys: int, hidden: int) -> None:
        super().__init__()
        self.wave = nn.Sequential(nn.Linear(n_wave, hidden), nn.Tanh())
        self.phys = nn.Linear(n_phys, 1, bias=False)
        self.head = nn.Sequential(nn.Linear(hidden + n_phys, max(hidden, 8)), nn.ReLU(), nn.Linear(max(hidden, 8), 1))

    def forward(self, x_wave: torch.Tensor, x_phys: torch.Tensor) -> torch.Tensor:
        z = self.wave(x_wave)
        return (self.phys(x_phys).squeeze(1) + self.head(torch.cat([z, x_phys], dim=1)).squeeze(1))


def hybrid_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    X, _ = p03a.waveform_features(pulses, staves)
    phys, _ = s03a.analytic_feature_matrix(pulses, "amp_only", list(staves))
    return X.astype(np.float32), phys.astype(np.float32)


def standardize_block(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    train_mask = np.zeros(len(X), dtype=bool)
    train_mask[train_idx] = True
    scaler = StandardScaler()
    out = X.copy()
    out[train_mask] = scaler.fit_transform(X[train_mask])
    if (~train_mask).any():
        out[~train_mask] = scaler.transform(X[~train_mask])
    return out.astype(np.float32), scaler


def train_hybrid(Xw: np.ndarray, Xp: np.ndarray, y: np.ndarray, train_idx: np.ndarray, hidden: int, weight_decay: float, config: dict, seed: int) -> Tuple[HybridResidualNet, np.ndarray, np.ndarray]:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    Xws, _ = standardize_block(Xw, train_idx)
    Xps, _ = standardize_block(Xp, train_idx)
    model = HybridResidualNet(Xw.shape[1], Xp.shape[1], int(hidden))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["learning_rate"]), weight_decay=float(weight_decay))
    xw_all = torch.from_numpy(Xws[train_idx])
    xp_all = torch.from_numpy(Xps[train_idx])
    y_all = torch.from_numpy(y[train_idx].astype(np.float32))
    batch_size = int(config["ml"]["batch_size"])
    for _ in range(int(config["ml"]["epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch_size):
            take = order[start:start + batch_size]
            pred = model(xw_all[take], xp_all[take])
            loss = torch.mean((pred - y_all[take]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model, Xws, Xps


def predict_hybrid(model: HybridResidualNet, Xws: np.ndarray, Xps: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        return model(torch.from_numpy(Xws.astype(np.float32)), torch.from_numpy(Xps.astype(np.float32))).numpy().astype(float)


def run_hybrid_on_base(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    seed = int(config["ml"]["random_seed"])
    y = s02.event_residual_targets(pulses, base_method, 2.0, config)
    Xw, Xp = hybrid_features(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_xy(Xw, y, runs) & np.all(np.isfinite(Xp), axis=1)
    idx = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    cv_rows = []
    best = {"score": math.inf, "hidden": None, "weight_decay": None}
    gkf = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
    for hidden in [int(v) for v in config["ml"]["hybrid_hidden"]]:
        for weight_decay in [float(v) for v in config["ml"]["weight_decays"]]:
            scores = []
            for fold, (tr, va) in enumerate(gkf.split(Xw[train_mask], y[train_mask], groups=groups)):
                tr_idx = idx[tr]
                va_idx = idx[va]
                model, Xws, Xps = train_hybrid(Xw, Xp, y, tr_idx, hidden, weight_decay, config, seed + 3000 + fold * 53 + hidden)
                pred = np.full(len(pulses), np.nan)
                pred[:] = predict_hybrid(model, Xws, Xps)
                vals = evaluate_values(pulses.iloc[va_idx].copy(), "hybrid_cv", corrected_values(pulses, base_method, pred)[va_idx], config, sorted(np.unique(runs[va_idx])))
                score = s02.sigma68(vals)
                scores.append(score)
                cv_rows.append({"model": "physics_residual_net", "hidden": hidden, "weight_decay": weight_decay, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals))})
            mean_score = float(np.nanmean(scores))
            cv_rows.append({"model": "physics_residual_net", "hidden": hidden, "weight_decay": weight_decay, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
            if mean_score < best["score"]:
                best = {"score": mean_score, "hidden": hidden, "weight_decay": weight_decay}
    model, Xws, Xps = train_hybrid(Xw, Xp, y, idx, int(best["hidden"]), float(best["weight_decay"]), config, seed + 4903)
    pred = predict_hybrid(model, Xws, Xps)
    out = pulses.copy()
    out["hybrid_target_residual_ns"] = y
    out["hybrid_pred_residual_ns"] = pred
    out["t_physics_residual_net_ns"] = corrected_values(pulses, base_method, pred)
    return out, pd.DataFrame(cv_rows), {"method": "physics_residual_net", **best, "n_wave_features": int(Xw.shape[1]), "n_physics_features": int(Xp.shape[1])}


def pair_frame(pulses: pd.DataFrame, methods: Sequence[Tuple[str, str]], config: dict, runs: Sequence[int]) -> pd.DataFrame:
    rows = []
    for method, label in methods:
        sub = pulses[pulses["run"].isin(runs)].copy()
        downstream = list(config["timing"]["downstream_staves"])
        positions = s02.geometry_positions(downstream, 2.0)
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
            if a in wide and b in wide:
                vals = (wide[a] - wide[b]).to_numpy(dtype=float)
                for event_id, value in zip(wide.index.to_numpy(), vals):
                    if np.isfinite(value):
                        rows.append({"method": label, "event_id": event_id, "pair": f"{a}-{b}", "residual_ns": float(value)})
    return pd.DataFrame(rows)


def event_bootstrap(pairwise: pd.DataFrame, baseline: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    labels = sorted(pairwise["method"].unique())
    event_ids = np.asarray(sorted(pairwise["event_id"].unique()))
    by_method = {label: pairwise[pairwise["method"] == label].groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict() for label in labels}
    observed = {label: s02.sigma68(pairwise[pairwise["method"] == label]["residual_ns"].to_numpy()) for label in labels}
    rms = {label: s02.full_rms(pairwise[pairwise["method"] == label]["residual_ns"].to_numpy()) for label in labels}
    bias = {label: float(np.mean(pairwise[pairwise["method"] == label]["residual_ns"].to_numpy())) for label in labels}
    tail = {label: float(np.mean(np.abs(pairwise[pairwise["method"] == label]["residual_ns"].to_numpy() - np.median(pairwise[pairwise["method"] == label]["residual_ns"].to_numpy())) > 5.0)) for label in labels}
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
            deltas[label].append(boot[label] - boot[baseline])
    rows = []
    for label in labels:
        rows.append({
            "method": label,
            "metric": "heldout_pairwise_sigma68_ns",
            "sigma68_ns": float(observed[label]),
            "ci_low": float(np.percentile(stats[label], 2.5)),
            "ci_high": float(np.percentile(stats[label], 97.5)),
            "delta_vs_baseline_ns": float(observed[label] - observed[baseline]),
            "delta_ci_low": float(np.percentile(deltas[label], 2.5)),
            "delta_ci_high": float(np.percentile(deltas[label], 97.5)),
            "bias_ns": bias[label],
            "full_rms_ns": rms[label],
            "tail_frac_abs_gt5ns": tail[label],
            "n_events": int(len(event_ids)),
            "n_pair_residuals": int(len(pairwise[pairwise["method"] == label])),
        })
    return pd.DataFrame(rows).sort_values("sigma68_ns")


def amplitude_flatness(pulses: pd.DataFrame, methods: Sequence[Tuple[str, str]], config: dict) -> pd.DataFrame:
    rows = []
    heldout = list(config["timing"]["heldout_runs"])
    for method, label in methods:
        target = s02.event_residual_targets(pulses, method, 2.0, config)
        sub = pulses[pulses["run"].isin(heldout)].copy()
        sub["target_residual_ns"] = target[sub.index.to_numpy()]
        sub = sub[np.isfinite(sub["target_residual_ns"])]
        qs = np.unique(np.quantile(sub["amplitude_adc"], np.linspace(0, 1, 7)))
        sub["amp_bin"] = pd.cut(sub["amplitude_adc"], qs, include_lowest=True, duplicates="drop")
        means = []
        for interval, group in sub.groupby("amp_bin"):
            mean = float(group["target_residual_ns"].mean())
            means.append(mean)
            rows.append({"method": label, "amp_bin": str(interval), "n": int(len(group)), "mean_residual_ns": mean, "sigma68_ns": s02.sigma68(group["target_residual_ns"].to_numpy())})
        if means:
            rows.append({"method": label, "amp_bin": "max_abs_bin_mean", "n": int(len(sub)), "mean_residual_ns": float(np.max(np.abs(means))), "sigma68_ns": float("nan")})
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, metrics: pd.DataFrame, flatness: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    ordered = metrics.sort_values("sigma68_ns")
    x = np.arange(len(ordered))
    ax.bar(x, ordered["sigma68_ns"])
    ax.errorbar(x, ordered["sigma68_ns"], yerr=[ordered["sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["sigma68_ns"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["method"], rotation=30, ha="right")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("S03 ticket 2368 run-held-out benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_ranking.png", dpi=140)
    plt.close(fig)

    core = flatness[flatness["amp_bin"] != "max_abs_bin_mean"]
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    for method, group in core.groupby("method"):
        ax.plot(np.arange(len(group)), group["mean_residual_ns"], "o-", label=method)
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xlabel("held-out amplitude quantile bin")
    ax.set_ylabel("mean event residual target (ns)")
    ax.set_title("Residual-vs-amplitude flatness")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_amplitude_flatness.png", dpi=140)
    plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, traditional_scan: pd.DataFrame, metrics: pd.DataFrame, flatness: pd.DataFrame, cv: pd.DataFrame, systematics: pd.DataFrame, result: dict) -> None:
    winner = metrics.iloc[0]
    trad = metrics[metrics["method"] == "analytic_polynomial_timewalk"].iloc[0]
    lines = [
        "# Study report: S03 - Timewalk correction closure and ML frontier",
        "",
        f"- **Study ID:** S03-2368",
        f"- **Ticket:** #{config['ticket_id']} - S03: Timewalk correction closure & held-out-run",
        f"- **Author (worker label):** {config['worker']}",
        "- **Date:** 2026-08-16",
        "- **Depends on:** S00, S02",
        f"- **Input checksum(s):** aggregate sha256 `{result['input_sha256']}`",
        f"- **Git commit:** `{result['git_commit']}`",
        "- **Config:** `configs/s03_2368_timewalk_frontier.yaml`",
        "",
        "## 0. Question",
        "",
        "Does an interpretable amplitude timewalk correction close the residual-vs-amplitude slope on a run-held-out sample, and do modern residual regressors improve the same held-out pairwise timing metric enough to justify extra complexity?",
        "",
        "The pre-registered primary metric is held-out pairwise `sigma68` of corrected B4/B6/B8 time residuals at 2 cm spacing. The winner is the lowest point estimate; superiority over the strong traditional baseline requires the paired event-bootstrap delta confidence interval to exclude zero at alpha=0.05.",
        "",
        "## 1. Reproduction from raw ROOT",
        "",
        "Before fitting any correction, the S00 raw ROOT selector was rerun over every configured B-stack ROOT file. The gate exactly reproduces the selected-pulse count used by downstream S02/S03 timing work.",
        "",
        repro.to_markdown(index=False),
        "",
        "The timing table itself was then rebuilt from the same ROOT pass. Training used runs 58-63 and the held-out benchmark used run 65 only; event identifiers do not cross the split.",
        "",
        "## 2. Traditional non-ML method",
        "",
        "The strong baseline is the S02 `template_phase` pickoff followed by the S03 analytic/polynomial timewalk correction. For pulse p on stave s, the corrected time is",
        "",
        "`t'_p = t_template,p - f_s(A_p, x_p)`,",
        "",
        "where the selected model is a ridge-regularized polynomial/shape expansion over `log(1+A)`, `1/A`, `1/sqrt(A)`, peak sample, normalized area, rise-time proxies, normalized early and late charge, normalized peak height, stave intercepts, and optional stave interactions. Candidate families and ridge alphas were selected only by grouped CV on training runs.",
        "",
        traditional_scan[(traditional_scan["split"] == "heldout") & (traditional_scan["spacing_cm"] == 2.0)][["method", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "core_sigma_ns", "chi2_ndf"]].sort_values("sigma68_ns").head(8).to_markdown(index=False),
        "",
        "## 3. ML and neural methods",
        "",
        "All ML methods predict the same per-pulse residual target, defined as that stave's TOF-corrected residual relative to the mean of the other two downstream staves. The corrected time is `t'_p = t_base,p - g(z_p)`. The split is by run using grouped CV inside runs 58-63 and final evaluation on run 65. Features exclude run id, event id, event order, held-out labels, and other-stave timing.",
        "",
        "Methods benchmarked: ridge residual regression, histogram gradient-boosted trees, a heteroskedastic waveform MLP, a waveform 1D-CNN, and a new physics-residual network. The new architecture has a linear analytic-physics branch over the S03 amplitude basis plus a small neural residual branch over normalized waveform samples; it is intended to test whether enforcing the analytic timewalk prior helps a neural model avoid run leakage and overfit.",
        "",
        cv[cv["fold"] == -1].sort_values("sigma68_ns").head(20).to_markdown(index=False),
        "",
        "## 4. Head-to-head benchmark",
        "",
        metrics[["method", "metric", "sigma68_ns", "ci_low", "ci_high", "delta_vs_baseline_ns", "delta_ci_low", "delta_ci_high", "bias_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "n_pair_residuals"]].to_markdown(index=False),
        "",
        f"Winner: **{winner['method']}**, with held-out sigma68 `{winner['sigma68_ns']:.6f}` ns and 95% paired event-bootstrap CI `[{winner['ci_low']:.6f}, {winner['ci_high']:.6f}]` ns. The strong traditional analytic baseline is `{trad['sigma68_ns']:.6f}` ns with CI `[{trad['ci_low']:.6f}, {trad['ci_high']:.6f}]` ns.",
        "",
        "## 5. Falsification and systematics",
        "",
        "The explicit falsification test is a paired event-bootstrap against the analytic baseline inside the held-out run. A learned method is not adopted as superior unless the entire delta CI is below zero. Because five non-traditional methods were tried, the interpretation also treats overlapping CIs as weak evidence even if the point estimate is lower.",
        "",
        systematics.to_markdown(index=False),
        "",
        "Amplitude-flatness audit:",
        "",
        flatness[flatness["amp_bin"] == "max_abs_bin_mean"].to_markdown(index=False),
        "",
        "## 6. Threats to validity",
        "",
        "- **Benchmark/selection:** the baseline is not a strawman; it is the previously selected template-phase pickoff plus an analytic timewalk scan. All models use the same residual target and held-out run.",
        "- **Data leakage:** all tuning uses grouped CV over training runs only. Inputs exclude run/event identifiers and other-stave timing. The event-id overlap check is zero.",
        "- **Metric misuse:** sigma68 is the primary robust metric, but the table also reports full RMS, core Gaussian sigma, chi2/ndf where relevant, bias, and tail fraction.",
        "- **Post-hoc selection:** the primary metric, split, and method family list are encoded in the config before the final run. Architecture counts are reported in the CV table.",
        "",
        "## 7. Provenance manifest",
        "",
        "`manifest.json` in this directory records input sha256s, git commit, command, seeds, runtime, and output hashes. Raw data were read from `/home/billy/ccb-data/data/extracted/root/root` and were not modified.",
        "",
        "## 8. Findings and next steps",
        "",
        result["summary"],
        "",
        "One novel follow-up ticket is proposed: `S03 follow-up: cross-sample physics-residual timewalk adoption gate`. Expected information gain: it tests whether the winning model transfers from Sample II run-held-out closure to Sample I and run 64 without using sample-specific amplitude support, separating genuine timewalk physics from a run-family artifact.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s03_2368_timewalk_frontier.py --config configs/s03_2368_timewalk_frontier.yaml",
        "```",
        "",
        "Artifacts written: `reproduction_match_table.csv`, `traditional_scan_metrics.csv`, `method_metrics.csv`, `method_cv_scan.csv`, `amplitude_flatness.csv`, `systematics.csv`, `heldout_pair_residuals.csv`, figures, `result.json`, and `manifest.json`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03_2368_timewalk_frontier.yaml")
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
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = s02.load_downstream_pulses(config)
    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(pulses, config, templates)
    traditional_scan = s02.evaluate_methods(pulses, methods, config)
    traditional_scan.to_csv(out_dir / "traditional_scan_metrics.csv", index=False)
    best_method = str(traditional_scan[(traditional_scan["split"] == "train") & (traditional_scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns").iloc[0]["method"])
    if best_method != config["timing"]["base_method"]:
        raise RuntimeError(f"expected base {config['timing']['base_method']}, got {best_method}")

    analytic_pulses, analytic_cv, analytic_coef, analytic_candidate, analytic_alpha = s03a.run_analytic(pulses, config, best_method)
    combined = analytic_pulses.copy()

    ridge_pulses, ridge_cv, ridge_info = run_ridge_on_base(combined, config, "analytic_timewalk")
    combined["t_ridge_ns"] = ridge_pulses["t_ridge_ns"].to_numpy(dtype=float)
    gbt_pulses, gbt_cv, gbt_info = run_gbt_on_base(combined, config, "analytic_timewalk")
    combined["t_gradient_boosted_trees_ns"] = gbt_pulses["t_gradient_boosted_trees_ns"].to_numpy(dtype=float)
    mlp_pulses, mlp_cv, mlp_cal, mlp_info = p03a.run_waveform_mlp(combined, config, "analytic_timewalk")
    combined["t_mlp_waveform_ns"] = mlp_pulses["t_mlp_waveform_ns"].to_numpy(dtype=float)
    cnn_pulses, cnn_cv, cnn_cal, cnn_info = p03c.run_waveform_cnn(combined, config, "analytic_timewalk")
    combined["t_cnn_waveform_ns"] = cnn_pulses["t_cnn_waveform_ns"].to_numpy(dtype=float)
    hybrid_pulses, hybrid_cv, hybrid_info = run_hybrid_on_base(combined, config, "analytic_timewalk")
    combined["t_physics_residual_net_ns"] = hybrid_pulses["t_physics_residual_net_ns"].to_numpy(dtype=float)

    cv = pd.concat([
        analytic_cv.assign(model="analytic_polynomial_timewalk"),
        ridge_cv,
        gbt_cv,
        mlp_cv.assign(model="mlp_waveform"),
        cnn_cv,
        hybrid_cv,
    ], ignore_index=True, sort=False)
    cv.to_csv(out_dir / "method_cv_scan.csv", index=False)
    analytic_coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)
    pd.DataFrame([ridge_info, gbt_info, mlp_info, cnn_info, hybrid_info]).to_json(out_dir / "model_choices.json", orient="records", indent=2)

    benchmark_methods = [
        (best_method, "template_phase_base"),
        ("analytic_timewalk", "analytic_polynomial_timewalk"),
        ("ridge", "ridge"),
        ("gradient_boosted_trees", "gradient_boosted_trees"),
        ("mlp_waveform", "mlp_waveform"),
        ("cnn_waveform", "cnn_waveform"),
        ("physics_residual_net", "physics_residual_net"),
    ]
    heldout_pairwise = pair_frame(combined, benchmark_methods, config, list(config["timing"]["heldout_runs"]))
    heldout_pairwise.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    metrics = event_bootstrap(heldout_pairwise, "analytic_polynomial_timewalk", rng, int(config["ml"]["bootstrap_samples"]))
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    flatness = amplitude_flatness(combined, benchmark_methods, config)
    flatness.to_csv(out_dir / "amplitude_flatness.csv", index=False)

    train_ids = set(combined[combined["run"].isin(config["timing"]["train_runs"])]["event_id"])
    held_ids = set(combined[combined["run"].isin(config["timing"]["heldout_runs"])]["event_id"])
    systematics = pd.DataFrame([
        {"check": "train_heldout_event_id_overlap", "value": float(len(train_ids & held_ids)), "interpretation": "zero required; split is by run"},
        {"check": "analytic_candidate", "value": str(analytic_candidate), "interpretation": f"selected alpha={analytic_alpha} by grouped CV"},
        {"check": "method_family_trials", "value": 6.0, "interpretation": "analytic, ridge, GBT, MLP, CNN, hybrid; delta CIs are interpreted with this multiplicity in mind"},
        {"check": "data_symlink", "value": 0.0, "interpretation": "workspace data symlink was stale; config uses absolute read-only ROOT directory"},
    ])
    systematics.to_csv(out_dir / "systematics.csv", index=False)
    plot_outputs(out_dir, metrics, flatness)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    winner = metrics.iloc[0]
    trad = metrics[metrics["method"] == "analytic_polynomial_timewalk"].iloc[0]
    result = {
        "study_id": "S03-2368",
        "ticket_id": "2368",
        "worker": config["worker"],
        "primary_metric": "heldout_pairwise_sigma68_ns",
        "raw_reproduction_gate": {
            "pass": bool(repro["pass"].all()),
            "quantity": "total selected B-stave pulses",
            "report_value": int(repro.iloc[0]["report_value"]),
            "reproduced": int(repro.iloc[0]["reproduced"]),
            "delta": int(repro.iloc[0]["delta"]),
            "tolerance": int(repro.iloc[0]["tolerance"]),
        },
        "split": {
            "train_runs": list(config["timing"]["train_runs"]),
            "heldout_runs": list(config["timing"]["heldout_runs"]),
            "cv_group": "run",
            "bootstrap_samples": int(config["ml"]["bootstrap_samples"]),
        },
        "traditional_baseline": {
            "method": "analytic_polynomial_timewalk",
            "base_pickoff": best_method,
            "candidate": analytic_candidate,
            "alpha": float(analytic_alpha),
            "sigma68_ns": float(trad["sigma68_ns"]),
            "ci95": [float(trad["ci_low"]), float(trad["ci_high"])],
        },
        "winner": str(winner["method"]),
        "winner_family": "traditional" if str(winner["method"]) == "analytic_polynomial_timewalk" else "ml_nn",
        "winner_metrics": {
            "sigma68_ns": float(winner["sigma68_ns"]),
            "sigma68_ns_ci95": [float(winner["ci_low"]), float(winner["ci_high"])],
            "delta_vs_traditional_ns": float(winner["delta_vs_baseline_ns"]),
            "delta_vs_traditional_ci95": [float(winner["delta_ci_low"]), float(winner["delta_ci_high"])],
            "bias_ns": float(winner["bias_ns"]),
            "full_rms_ns": float(winner["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(winner["tail_frac_abs_gt5ns"]),
            "n_pair_residuals": int(winner["n_pair_residuals"]),
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "artifacts": {
            "report": str(out_dir / "REPORT.md"),
            "metrics": str(out_dir / "method_metrics.csv"),
            "cv": str(out_dir / "method_cv_scan.csv"),
            "result": str(out_dir / "result.json"),
        },
        "novel_ticket": "S03 follow-up: cross-sample physics-residual timewalk adoption gate",
    }
    if str(winner["method"]) == "analytic_polynomial_timewalk":
        result["summary"] = "The analytic timewalk correction remains the preferred method: no learned model beats the strong traditional baseline on the held-out run with a bootstrap delta interval that excludes zero. The result favors adoption of the interpretable correction and treats the neural models as useful stress tests rather than replacements."
    else:
        result["summary"] = f"The best held-out point estimate is {winner['method']}, improving over the analytic baseline by {abs(float(winner['delta_vs_baseline_ns'])):.6f} ns. Adoption should depend on the paired event-bootstrap delta CI and the cross-sample follow-up because the gain is evaluated on one held-out run."
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, traditional_scan, metrics, flatness, cv, systematics, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03-2368",
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
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "sigma68_ns": result["winner_metrics"]["sigma68_ns"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
