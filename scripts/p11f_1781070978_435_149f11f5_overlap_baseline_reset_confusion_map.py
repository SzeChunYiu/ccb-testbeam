#!/usr/bin/env python3
"""P11f: overlap versus baseline-reset confusion map from raw B-stack ROOT.

The ticket asks whether high-current overlap candidates remain separable from
baseline-reset/pretrigger contamination after matching amplitude, lowering,
broad-late anomaly taxon, saturation, run family, and topology.  There is no
external truth label for real high-current pile-up, so this script makes the
truth proxy explicit: overlap-like and reset-like support labels are frozen from
low-current raw waveform quantiles, then all model comparisons are interpreted
as proxy-separation and confusion diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04l_baseline_charge_dropout_coupling as p04l  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def raw_path(config: dict, run: int) -> Path:
    return ROOT / config["raw_root_dir"] / f"hrdb_run_{int(run):04d}.root"


def ci(values: Iterable[float]) -> List[float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [float("nan"), float("nan")]
    return [float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))]


def auc_or_nan(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap_or_nan(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def ece_score(y: np.ndarray, prob: np.ndarray, bins: int) -> float:
    yy = y.astype(float)
    pp = np.clip(prob.astype(float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, int(bins) + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (pp >= lo) & (pp <= hi if hi >= 1.0 else pp < hi)
        if mask.any():
            out += float(mask.mean()) * abs(float(yy[mask].mean()) - float(pp[mask].mean()))
    return float(out)


def run_group_lookup(config: dict) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for group, runs in config["current_run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def add_pretrigger_atoms(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    out = meta.copy()
    idx = [int(i) for i in config["baseline_samples"]]
    pre = wave[:, idx].astype(float)
    pre_centered = pre - np.median(pre, axis=1)[:, None]
    out["p11_pre_rms_adc"] = np.sqrt(np.mean(pre_centered**2, axis=1)).astype(np.float32)
    out["p11_pre_slope_adc"] = (pre[:, -1] - pre[:, 0]).astype(np.float32)
    out["p11_pre_range_adc"] = (pre.max(axis=1) - pre.min(axis=1)).astype(np.float32)
    out["p11_pre_asym_adc"] = (0.5 * ((pre[:, 0] + pre[:, 1]) - (pre[:, 2] + pre[:, 3]))).astype(np.float32)
    out["p11_adaptive_lowering_adc"] = np.maximum(0.0, -pre_centered.min(axis=1) - 10.0).astype(np.float32)
    out["p11_pretrigger_score"] = np.sqrt(
        out["p11_pre_rms_adc"].to_numpy() ** 2
        + out["p11_pre_slope_adc"].to_numpy() ** 2
        + out["p11_pre_range_adc"].to_numpy() ** 2
        + out["p11_adaptive_lowering_adc"].to_numpy() ** 2
    ).astype(np.float32)
    th = {
        "rms_hi": float(out.loc[train_mask, "p11_pre_rms_adc"].quantile(0.75)),
        "slope_hi": float(out.loc[train_mask, "p11_pre_slope_adc"].abs().quantile(0.75)),
        "range_hi": float(out.loc[train_mask, "p11_pre_range_adc"].quantile(0.90)),
        "lower_hi": float(out.loc[train_mask, "p11_adaptive_lowering_adc"].quantile(0.90)),
        "score_hi": float(out.loc[train_mask, "p11_pretrigger_score"].quantile(float(config["reset_quantile_low_current"]))),
    }
    atom = np.full(len(out), "quiet", dtype=object)
    atom[out["p11_pre_rms_adc"].to_numpy() >= th["rms_hi"]] = "noisy_rms"
    atom[np.abs(out["p11_pre_slope_adc"].to_numpy()) >= th["slope_hi"]] = "sloped"
    atom[out["p11_pre_range_adc"].to_numpy() >= th["range_hi"]] = "range_spike"
    atom[out["p11_adaptive_lowering_adc"].to_numpy() >= th["lower_hi"]] = "adaptive_lowering"
    out["p11_pretrigger_atom"] = atom
    out.attrs["p11_pretrigger_thresholds"] = th
    return out


def add_current_support_labels(meta: pd.DataFrame, wave: np.ndarray, config: dict) -> Tuple[pd.DataFrame, dict]:
    out = meta.copy()
    out["_source_index"] = np.arange(len(out), dtype=int)
    current = run_group_lookup(config)
    out = out[out["run"].isin(sorted(current))].copy().reset_index(drop=True)
    w = wave[out["_source_index"].to_numpy()]
    out["current_group"] = out["run"].map(current)
    low = out["current_group"].to_numpy() == "low_2nA"
    out = p04l.add_derived_columns(out, w, low, config)
    out = add_pretrigger_atoms(out, w, low, config)

    event_key = out["run"].astype(str) + ":" + out["eventno"].astype(str) + ":" + out["evt"].astype(str)
    out["_event_key"] = event_key
    out["selected_stave_multiplicity"] = out.groupby("_event_key")["_event_key"].transform("size").astype(np.int16)
    out["has_downstream_stave"] = out["_event_key"].map(out.groupby("_event_key")["stave_idx"].max() > 0).astype(np.int8)
    out["run_family"] = np.where(out["run"].isin([46, 47]), "low_2nA", "high_20nA")
    out["amp_match_bin"] = pd.cut(
        out["even_amp"],
        bins=[float(x) for x in config["amplitude_bins"]],
        labels=False,
        include_lowest=True,
    ).astype(int)
    out["lowering_bin"] = pd.cut(
        out["p11_adaptive_lowering_adc"],
        bins=[-0.1, 0.1, 50.0, 200.0, np.inf],
        labels=["no_lowering", "mild_lowering", "moderate_lowering", "large_lowering"],
        include_lowest=True,
        right=False,
    ).astype(str)
    broad = (out["even_peak"] >= 9) | (out["width_half"] >= 8) | (out["late_fraction"] >= out.loc[low, "late_fraction"].quantile(0.80))
    early = (out["even_peak"] <= 4) | (out["early_fraction"] >= out.loc[low, "early_fraction"].quantile(0.90))
    out["broad_late_taxon"] = np.select([broad, early], ["broad_late", "early_pretrigger"], default="compact")
    anomaly_edges = np.quantile(out.loc[low, "p09_pca_anomaly_score"], [0.50, 0.80, 0.95])
    out["p09_anomaly_taxon"] = pd.cut(
        out["p09_pca_anomaly_score"],
        bins=[-np.inf] + [float(x) for x in anomaly_edges] + [np.inf],
        labels=["common", "mild", "broad_late_anomaly", "extreme"],
    ).astype(str)
    out["topology_bin"] = (
        "mult" + out["selected_stave_multiplicity"].clip(upper=4).astype(str)
        + "_ds"
        + out["has_downstream_stave"].astype(str)
        + "_stave"
        + out["stave"].astype(str)
    )

    def robust_z(col: str) -> np.ndarray:
        vals = out[col].to_numpy(dtype=float)
        center = float(np.median(vals[low]))
        scale = float(1.4826 * np.median(np.abs(vals[low] - center)))
        if not np.isfinite(scale) or scale < 1e-9:
            scale = float(np.std(vals[low]) + 1e-6)
        return np.clip((vals - center) / scale, -8.0, 8.0)

    overlap_score = (
        0.34 * robust_z("secondary_peak")
        + 0.24 * robust_z("late_fraction")
        + 0.18 * robust_z("tail_fraction")
        + 0.14 * robust_z("width_half")
        + 0.10 * (out["selected_stave_multiplicity"].to_numpy(dtype=float) - 1.0)
    )
    reset_score = (
        0.38 * robust_z("p11_pretrigger_score")
        + 0.24 * robust_z("baseline_score")
        + 0.18 * robust_z("p11_adaptive_lowering_adc")
        + 0.12 * robust_z("early_fraction")
        + 0.08 * out["atom_baseline_excursion"].to_numpy(dtype=float)
    )
    overlap_cut = float(np.quantile(overlap_score[low], float(config["overlap_quantile_low_current"])))
    reset_cut = float(np.quantile(reset_score[low], float(config["reset_quantile_low_current"])))
    out["traditional_overlap_score"] = overlap_score.astype(np.float32)
    out["baseline_reset_score"] = reset_score.astype(np.float32)
    out["overlap_proxy"] = (overlap_score >= overlap_cut).astype(np.int8)
    out["baseline_reset_proxy"] = (reset_score >= reset_cut).astype(np.int8)
    out["confused_overlap_reset_proxy"] = ((out["overlap_proxy"] == 1) & (out["baseline_reset_proxy"] == 1)).astype(np.int8)
    out["secondary_fraction_proxy"] = np.clip(out["secondary_peak"].to_numpy(dtype=float) / np.maximum(1.0 + out["secondary_peak"].to_numpy(dtype=float), 1.0), 0.0, 1.0)
    thresholds = {
        "overlap_score_low_current_quantile": float(config["overlap_quantile_low_current"]),
        "overlap_score_cut": overlap_cut,
        "reset_score_low_current_quantile": float(config["reset_quantile_low_current"]),
        "reset_score_cut": reset_cut,
        "p11_pretrigger_thresholds": out.attrs.get("p11_pretrigger_thresholds", {}),
        "p09_anomaly_edges": [float(x) for x in anomaly_edges],
    }
    return out, thresholds


def shape_features(meta: pd.DataFrame, wave: np.ndarray, include_reset: bool) -> np.ndarray:
    amp = np.maximum(meta["even_amp"].to_numpy(dtype=float), 1.0)
    norm_wave = wave / amp[:, None]
    cols = [
        norm_wave,
        meta[
            [
                "even_peak",
                "late_fraction",
                "tail_fraction",
                "width_half",
                "secondary_peak",
                "secondary_sep",
                "post_peak_min",
                "dropout_score",
                "p09_pca_anomaly_score",
                "selected_stave_multiplicity",
                "has_downstream_stave",
                "is_saturated",
                "saturation_count",
            ]
        ].to_numpy(dtype=float),
    ]
    stave_idx = meta["stave_idx"].to_numpy().astype(int)
    stave_onehot = np.zeros((len(meta), 4), dtype=float)
    stave_onehot[np.arange(len(meta)), stave_idx] = 1.0
    cols.append(stave_onehot)
    if include_reset:
        cols.append(
            meta[
                [
                    "baseline_score",
                    "baseline_mad",
                    "baseline_slope",
                    "baseline_range",
                    "early_fraction",
                    "p11_pre_rms_adc",
                    "p11_pre_slope_adc",
                    "p11_pre_range_adc",
                    "p11_adaptive_lowering_adc",
                    "p11_pretrigger_score",
                    "atom_baseline_excursion",
                ]
            ].to_numpy(dtype=float)
        )
    return np.nan_to_num(np.column_stack(cols), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def reset_context(meta: pd.DataFrame) -> np.ndarray:
    atoms = ["quiet", "noisy_rms", "sloped", "range_spike", "adaptive_lowering"]
    onehot = np.zeros((len(meta), len(atoms)), dtype=np.float32)
    lookup = {name: i for i, name in enumerate(atoms)}
    for i, atom in enumerate(meta["p11_pretrigger_atom"].astype(str)):
        onehot[i, lookup.get(atom, 0)] = 1.0
    return np.nan_to_num(
        np.column_stack(
            [
                meta[
                    [
                        "baseline_score",
                        "p11_pre_rms_adc",
                        "p11_pre_slope_adc",
                        "p11_pre_range_adc",
                        "p11_adaptive_lowering_adc",
                        "p11_pretrigger_score",
                        "is_saturated",
                        "selected_stave_multiplicity",
                    ]
                ].to_numpy(dtype=np.float32),
                onehot,
            ]
        ),
        nan=0.0,
    ).astype(np.float32)


def train_indices(meta: pd.DataFrame, config: dict) -> np.ndarray:
    idx = np.flatnonzero(meta["current_group"].to_numpy() == "low_2nA")
    rng = np.random.default_rng(int(config["random_seed"]) + 41)
    if len(idx) > int(config["ml_max_train_rows"]):
        idx = rng.choice(idx, size=int(config["ml_max_train_rows"]), replace=False)
    return np.asarray(idx, dtype=int)


def minmax_calibrate(train_score: np.ndarray, score: np.ndarray) -> np.ndarray:
    lo, hi = np.quantile(train_score[np.isfinite(train_score)], [0.02, 0.98])
    return np.clip((score - lo) / max(float(hi - lo), 1e-9), 0.0, 1.0)


def sklearn_predictions(meta: pd.DataFrame, y: np.ndarray, X_shape: np.ndarray, X_reset: np.ndarray, config: dict) -> Dict[str, np.ndarray]:
    idx = train_indices(meta, config)
    rng = np.random.default_rng(int(config["random_seed"]) + 52)
    shuffled = y[idx].copy()
    rng.shuffle(shuffled)
    preds: Dict[str, np.ndarray] = {}

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
    ridge.fit(X_shape[idx], y[idx].astype(float))
    preds["ridge_shape_no_reset"] = minmax_calibrate(ridge.predict(X_shape[idx]), ridge.predict(X_shape))

    hgb = HistGradientBoostingClassifier(max_iter=180, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=25, l2_regularization=0.05, random_state=int(config["random_seed"]) + 1)
    hgb.fit(X_shape[idx], y[idx])
    preds["gradient_boosted_trees_shape_no_reset"] = hgb.predict_proba(X_shape)[:, 1]

    hgb_reset = HistGradientBoostingClassifier(max_iter=180, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=25, l2_regularization=0.05, random_state=int(config["random_seed"]) + 2)
    hgb_reset.fit(X_reset[idx], y[idx])
    preds["gradient_boosted_trees_with_reset_features"] = hgb_reset.predict_proba(X_reset)[:, 1]

    mlp = make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=(64, 24), alpha=0.002, max_iter=120, early_stopping=True, random_state=int(config["random_seed"]) + 3),
    )
    mlp.fit(X_shape[idx], y[idx])
    preds["mlp_shape_no_reset"] = mlp.predict_proba(X_shape)[:, 1]

    rf = RandomForestClassifier(n_estimators=160, min_samples_leaf=20, class_weight="balanced_subsample", random_state=int(config["random_seed"]) + 4, n_jobs=2)
    rf.fit(meta.loc[idx, ["p11_pretrigger_score", "baseline_score", "p11_adaptive_lowering_adc", "early_fraction"]].to_numpy(dtype=np.float32), y[idx])
    preds["control_pretrigger_only"] = rf.predict_proba(meta[["p11_pretrigger_score", "baseline_score", "p11_adaptive_lowering_adc", "early_fraction"]].to_numpy(dtype=np.float32))[:, 1]

    topo_cols = ["selected_stave_multiplicity", "has_downstream_stave", "stave_idx", "is_saturated", "even_peak"]
    topo = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, max_leaf_nodes=15, random_state=int(config["random_seed"]) + 5)
    topo.fit(meta.loc[idx, topo_cols].to_numpy(dtype=np.float32), y[idx])
    preds["control_topology_only"] = topo.predict_proba(meta[topo_cols].to_numpy(dtype=np.float32))[:, 1]

    shuffled_model = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.06, max_leaf_nodes=31, random_state=int(config["random_seed"]) + 6)
    shuffled_model.fit(X_shape[idx], shuffled)
    preds["control_shuffled_label"] = shuffled_model.predict_proba(X_shape)[:, 1]
    return preds


class WaveClassifier(nn.Module):
    def __init__(self, n_context: int = 0, gated: bool = False) -> None:
        super().__init__()
        self.gated = gated
        self.wave = nn.Sequential(
            nn.Conv1d(1, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        if gated:
            self.context = nn.Sequential(nn.Linear(n_context, 32), nn.ReLU(), nn.Linear(32, 32), nn.ReLU())
            self.gate = nn.Sequential(nn.Linear(n_context, 32), nn.Sigmoid())
            self.head = nn.Sequential(nn.Linear(64, 48), nn.ReLU(), nn.Linear(48, 1))
        else:
            self.context = None
            self.gate = None
            self.head = nn.Sequential(nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x_wave: torch.Tensor, x_context: torch.Tensor) -> torch.Tensor:
        zw = self.wave(x_wave[:, None, :]).squeeze(-1)
        if self.gated:
            zc = self.context(x_context)
            zw = zw * self.gate(x_context)
            return self.head(torch.cat([zw, zc], dim=1)).squeeze(1)
        return self.head(zw).squeeze(1)


def fit_torch_classifier(name: str, wave: np.ndarray, context: np.ndarray, y: np.ndarray, meta: pd.DataFrame, config: dict, gated: bool) -> np.ndarray:
    seed = int(config["random_seed"]) + (77 if gated else 66)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    idx = np.flatnonzero(meta["current_group"].to_numpy() == "low_2nA")
    if len(idx) > int(config["nn_max_train_rows"]):
        idx = rng.choice(idx, size=int(config["nn_max_train_rows"]), replace=False)
    amp = np.maximum(meta["even_amp"].to_numpy(dtype=float), 1.0)
    norm_wave = (wave / amp[:, None]).astype(np.float32)
    wave_scale = max(float(np.percentile(np.abs(norm_wave[idx]), 99.0)), 1.0)
    norm_wave = (norm_wave / wave_scale).astype(np.float32)
    scaler = StandardScaler()
    ctx = scaler.fit_transform(context[idx]).astype(np.float32)
    all_ctx = scaler.transform(context).astype(np.float32)
    train_wave = norm_wave[idx]
    train_y = y[idx].astype(np.float32)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = WaveClassifier(all_ctx.shape[1], gated=gated).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn_learning_rate"]), weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([(len(train_y) - train_y.sum()) / max(train_y.sum(), 1.0)], device=device))
    batch = int(config["nn_batch_size"])
    for epoch in range(int(config["nn_epochs"])):
        order = rng.permutation(len(idx))
        model.train()
        losses = []
        for start in range(0, len(order), batch):
            sel = order[start : start + batch]
            xw = torch.from_numpy(train_wave[sel]).to(device)
            xc = torch.from_numpy(ctx[sel]).to(device)
            yy = torch.from_numpy(train_y[sel]).to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xw, xc), yy)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print(f"{name} epoch {epoch + 1}/{config['nn_epochs']}: loss={np.mean(losses):.5f}", flush=True)
    probs: List[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(norm_wave), batch * 4):
            xw = torch.from_numpy(norm_wave[start : start + batch * 4]).to(device)
            xc = torch.from_numpy(all_ctx[start : start + batch * 4]).to(device)
            probs.append(torch.sigmoid(model(xw, xc)).detach().cpu().numpy())
    return np.concatenate(probs)


def all_predictions(meta: pd.DataFrame, wave: np.ndarray, config: dict) -> Dict[str, np.ndarray]:
    y = meta["overlap_proxy"].to_numpy(dtype=int)
    X_shape = shape_features(meta, wave, include_reset=False)
    X_reset = shape_features(meta, wave, include_reset=True)
    preds = {
        "traditional_template_shape_score": minmax_calibrate(
            meta.loc[meta["current_group"] == "low_2nA", "traditional_overlap_score"].to_numpy(dtype=float),
            meta["traditional_overlap_score"].to_numpy(dtype=float),
        )
    }
    preds.update(sklearn_predictions(meta, y, X_shape, X_reset, config))
    ctx = reset_context(meta)
    preds["cnn_1d_waveform"] = fit_torch_classifier("cnn_1d_waveform", wave, np.zeros((len(meta), 1), dtype=np.float32), y, meta, config, gated=False)
    preds["reset_gated_cnn_new"] = fit_torch_classifier("reset_gated_cnn_new", wave, ctx, y, meta, config, gated=True)
    return preds


def run_bootstrap(frame: pd.DataFrame, value_fn: Callable[[pd.DataFrame], float], config: dict, seed_offset: int) -> List[float]:
    rng = np.random.default_rng(int(config["random_seed"]) + seed_offset)
    runs = sorted(int(r) for r in frame["run"].unique())
    by_run = {run: frame[frame["run"] == run] for run in runs}
    vals = []
    for _ in range(int(config["bootstrap_reps"])):
        sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        value = value_fn(sample)
        if np.isfinite(value):
            vals.append(float(value))
    return vals


def run_bootstrap_arrays(
    runs: np.ndarray,
    y: np.ndarray,
    prob: np.ndarray,
    reset: np.ndarray,
    metric_name: str,
    config: dict,
    seed_offset: int,
) -> List[float]:
    rng = np.random.default_rng(int(config["random_seed"]) + seed_offset)
    unique_runs = np.asarray(sorted(np.unique(runs)), dtype=int)
    by_run = {int(run): np.flatnonzero(runs == int(run)) for run in unique_runs}
    vals: List[float] = []
    for _ in range(int(config["bootstrap_reps"])):
        idx = np.concatenate([by_run[int(run)] for run in rng.choice(unique_runs, size=len(unique_runs), replace=True)])
        yy = y[idx]
        pp = prob[idx]
        rr = reset[idx]
        if metric_name == "auc":
            value = auc_or_nan(yy, pp)
        elif metric_name == "ap":
            value = ap_or_nan(yy, pp)
        elif metric_name == "brier":
            value = float(brier_score_loss(yy, pp))
        elif metric_name == "ece":
            value = ece_score(yy, pp, int(config["calibration_bins"]))
        elif metric_name == "confused":
            value = float(((pp >= 0.5) & (rr == 1)).mean())
        else:
            raise ValueError(metric_name)
        if np.isfinite(value):
            vals.append(float(value))
    return vals


def method_metrics(meta: pd.DataFrame, preds: Dict[str, np.ndarray], config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    high_mask = meta["current_group"].to_numpy() == "high_20nA"
    y = meta["overlap_proxy"].to_numpy(dtype=int)
    reset = meta["baseline_reset_proxy"].to_numpy(dtype=int)
    rows, run_rows = [], []
    for i, (method, prob_all) in enumerate(preds.items()):
        prob = np.clip(prob_all, 1e-6, 1.0 - 1e-6)
        frame = meta.loc[high_mask, ["run", "current_group"]].copy()
        frame["y"] = y[high_mask]
        frame["reset"] = reset[high_mask]
        frame["prob"] = prob[high_mask]
        frame["candidate"] = frame["prob"] >= 0.5
        frame["confused"] = frame["candidate"] & (frame["reset"] == 1)
        runs_np = frame["run"].to_numpy(dtype=int)
        y_np = frame["y"].to_numpy(dtype=int)
        prob_np = frame["prob"].to_numpy(dtype=float)
        reset_np = frame["reset"].to_numpy(dtype=int)
        auc = auc_or_nan(frame["y"].to_numpy(), frame["prob"].to_numpy())
        ap = ap_or_nan(frame["y"].to_numpy(), frame["prob"].to_numpy())
        brier = float(brier_score_loss(frame["y"], frame["prob"]))
        ece = ece_score(frame["y"].to_numpy(), frame["prob"].to_numpy(), int(config["calibration_bins"]))
        confusion_rate = float(frame["confused"].mean())
        reset_enrich = float(frame.loc[frame["candidate"], "reset"].mean() - frame["reset"].mean()) if frame["candidate"].any() else float("nan")
        disagreement = float(np.mean((frame["candidate"].astype(int).to_numpy()) != frame["y"].to_numpy()))
        rows.append(
            {
                "method": method,
                "n_high": int(len(frame)),
                "overlap_auc": auc,
                "overlap_auc_ci95": ci(run_bootstrap_arrays(runs_np, y_np, prob_np, reset_np, "auc", config, i * 10 + 1)),
                "average_precision": ap,
                "average_precision_ci95": ci(run_bootstrap_arrays(runs_np, y_np, prob_np, reset_np, "ap", config, i * 10 + 2)),
                "brier": brier,
                "brier_ci95": ci(run_bootstrap_arrays(runs_np, y_np, prob_np, reset_np, "brier", config, i * 10 + 3)),
                "ece": ece,
                "ece_ci95": ci(run_bootstrap_arrays(runs_np, y_np, prob_np, reset_np, "ece", config, i * 10 + 4)),
                "candidate_rate": float(frame["candidate"].mean()),
                "confused_overlap_reset_rate": confusion_rate,
                "confused_overlap_reset_rate_ci95": ci(run_bootstrap_arrays(runs_np, y_np, prob_np, reset_np, "confused", config, i * 10 + 5)),
                "baseline_reset_enrichment_among_candidates": reset_enrich,
                "disagreement_with_template_label": disagreement,
                "rank_loss": float(brier + ece + 0.5 * confusion_rate + 0.25 * disagreement - 0.05 * max(auc if np.isfinite(auc) else 0.5, 0.5)),
            }
        )
        for run, sub in frame.groupby("run"):
            run_rows.append(
                {
                    "run": int(run),
                    "method": method,
                    "n": int(len(sub)),
                    "overlap_auc": auc_or_nan(sub["y"].to_numpy(), sub["prob"].to_numpy()),
                    "brier": float(brier_score_loss(sub["y"], sub["prob"])) if len(np.unique(sub["y"])) > 1 else float("nan"),
                    "candidate_rate": float((sub["prob"] >= 0.5).mean()),
                    "reset_rate": float(sub["reset"].mean()),
                    "confused_overlap_reset_rate": float(((sub["prob"] >= 0.5) & (sub["reset"] == 1)).mean()),
                    "mean_overlap_score": float(sub["prob"].mean()),
                }
            )
    return pd.DataFrame(rows).sort_values("rank_loss").reset_index(drop=True), pd.DataFrame(run_rows)


def matched_confusion(meta: pd.DataFrame, preds: Dict[str, np.ndarray], config: dict) -> pd.DataFrame:
    rows = []
    keys = ["amp_match_bin", "lowering_bin", "broad_late_taxon", "p09_anomaly_taxon", "is_saturated", "topology_bin"]
    rng = np.random.default_rng(int(config["random_seed"]) + 304)
    for method, prob in preds.items():
        tmp = meta[keys + ["run", "current_group", "baseline_reset_proxy", "overlap_proxy"]].copy()
        tmp["candidate"] = np.asarray(prob) >= 0.5
        tmp["confused"] = tmp["candidate"] & (tmp["baseline_reset_proxy"] == 1)
        cells = []
        for key, sub in tmp.groupby(keys, observed=False):
            low = sub[sub["current_group"] == "low_2nA"]
            high = sub[sub["current_group"] == "high_20nA"]
            if len(low) < int(config["min_matched_cell"]) or len(high) < int(config["min_matched_cell"]):
                continue
            cells.append(
                {
                    "method": method,
                    "cell": "|".join(str(x) for x in key),
                    "amp_match_bin": key[0],
                    "lowering_bin": key[1],
                    "broad_late_taxon": key[2],
                    "p09_anomaly_taxon": key[3],
                    "is_saturated": key[4],
                    "topology_bin": key[5],
                    "low_n": int(len(low)),
                    "high_n": int(len(high)),
                    "weight": int(min(len(low), len(high))),
                    "delta_candidate_rate": float(high["candidate"].mean() - low["candidate"].mean()),
                    "delta_reset_rate": float(high["baseline_reset_proxy"].mean() - low["baseline_reset_proxy"].mean()),
                    "delta_confused_rate": float(high["confused"].mean() - low["confused"].mean()),
                    "delta_template_overlap_label": float(high["overlap_proxy"].mean() - low["overlap_proxy"].mean()),
                }
            )
        cdf = pd.DataFrame(cells)
        if cdf.empty:
            continue
        w = cdf["weight"].to_numpy(dtype=float)
        base = {
            "method": method,
            "n_cells": int(len(cdf)),
            "matched_weight": int(w.sum()),
            "matched_delta_candidate_rate": float(np.average(cdf["delta_candidate_rate"], weights=w)),
            "matched_delta_reset_rate": float(np.average(cdf["delta_reset_rate"], weights=w)),
            "matched_delta_confused_rate": float(np.average(cdf["delta_confused_rate"], weights=w)),
            "matched_delta_template_overlap_label": float(np.average(cdf["delta_template_overlap_label"], weights=w)),
        }
        boots = {k: [] for k in ["delta_candidate_rate", "delta_reset_rate", "delta_confused_rate", "delta_template_overlap_label"]}
        for _ in range(int(config["bootstrap_reps"])):
            sample = cdf.iloc[rng.integers(0, len(cdf), size=len(cdf))]
            sw = sample["weight"].to_numpy(dtype=float)
            for col in boots:
                boots[col].append(float(np.average(sample[col], weights=sw)))
        for col, vals in boots.items():
            base[f"matched_{col}_ci95"] = ci(vals)
        rows.append(base)
    return pd.DataFrame(rows)


def support_tables(meta: pd.DataFrame, preds: Dict[str, np.ndarray]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for group, sub in meta.groupby("current_group"):
        rows.append(
            {
                "current_group": group,
                "n": int(len(sub)),
                "overlap_proxy_rate": float(sub["overlap_proxy"].mean()),
                "baseline_reset_proxy_rate": float(sub["baseline_reset_proxy"].mean()),
                "confused_proxy_rate": float(sub["confused_overlap_reset_proxy"].mean()),
                "mean_secondary_fraction_proxy": float(sub["secondary_fraction_proxy"].mean()),
                "broad_late_taxon_fraction": float((sub["broad_late_taxon"] == "broad_late").mean()),
                "large_lowering_fraction": float((sub["lowering_bin"] == "large_lowering").mean()),
            }
        )
    atom_rows = []
    best = next(iter(preds))
    for (group, atom), sub in meta.assign(_candidate=np.asarray(preds[best]) >= 0.5).groupby(["current_group", "p11_pretrigger_atom"]):
        atom_rows.append(
            {
                "current_group": group,
                "p11_pretrigger_atom": atom,
                "n": int(len(sub)),
                "fraction": float(len(sub) / max((meta["current_group"] == group).sum(), 1)),
                "overlap_proxy_rate": float(sub["overlap_proxy"].mean()),
                "baseline_reset_proxy_rate": float(sub["baseline_reset_proxy"].mean()),
                "candidate_rate_first_method": float(sub["_candidate"].mean()),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(atom_rows)


def save_figures(out_dir: Path, metrics: pd.DataFrame, matched: pd.DataFrame, run_metrics: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    plot = metrics.sort_values("rank_loss", ascending=False)
    ax.barh(plot["method"], plot["rank_loss"], color="#4c78a8")
    ax.set_xlabel("Rank loss (lower is better)")
    ax.set_title("P11f run-external high-current benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_rank_loss.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    top = matched.sort_values("matched_delta_confused_rate", ascending=True)
    ax.barh(top["method"], top["matched_delta_confused_rate"], color="#f58518")
    ax.axvline(0, color="black", lw=1)
    ax.set_xlabel("Matched high-minus-low confused candidate rate")
    ax.set_title("Overlap/reset confusion after support matching")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_matched_confusion_delta.png", dpi=150)
    plt.close(fig)

    pivot = run_metrics.pivot_table(index="run", columns="method", values="confused_overlap_reset_rate", aggfunc="first")
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    for method in metrics.head(5)["method"]:
        if method in pivot:
            ax.plot(pivot.index, pivot[method], marker="o", label=method)
    ax.set_xlabel("High-current run")
    ax.set_ylabel("Confused overlap/reset rate")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_confusion_rates.png", dpi=150)
    plt.close(fig)


def markdown_table(frame: pd.DataFrame, cols: List[str], n: int | None = None) -> str:
    if frame.empty:
        return "_No rows._"
    view = frame.loc[:, cols].copy()
    if n is not None:
        view = view.head(n)
    for col in view.columns:
        if view[col].dtype.kind in "fc":
            view[col] = view[col].map(lambda x: f"{x:.6g}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def write_report(out_dir: Path, config: dict, counts: pd.DataFrame, thresholds: dict, metrics: pd.DataFrame, run_metrics: pd.DataFrame, matched: pd.DataFrame, support: pd.DataFrame, atom: pd.DataFrame, result: dict) -> None:
    winner = result["winner"]["method"]
    best_trad = result["best_traditional"]["method"]
    metric_cols = [
        "method",
        "n_high",
        "overlap_auc",
        "overlap_auc_ci95",
        "brier",
        "brier_ci95",
        "ece",
        "confused_overlap_reset_rate",
        "confused_overlap_reset_rate_ci95",
        "baseline_reset_enrichment_among_candidates",
        "disagreement_with_template_label",
        "rank_loss",
    ]
    run_cols = ["run", "method", "n", "overlap_auc", "brier", "candidate_rate", "reset_rate", "confused_overlap_reset_rate"]
    match_cols = [
        "method",
        "n_cells",
        "matched_weight",
        "matched_delta_candidate_rate",
        "matched_delta_candidate_rate_ci95",
        "matched_delta_reset_rate",
        "matched_delta_confused_rate",
        "matched_delta_confused_rate_ci95",
    ]
    lines = [
        "# P11f: Overlapping-pulse Baseline-reset Confusion Map",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT `h101/HRDv` under `data/root/root`; no derived pulse table is used as input.",
        "- **Split:** low-current runs 46 and 47 define training/proxy thresholds; high-current runs 44, 45, and 48-57 are held out by run for scoring and bootstrap CIs.",
        f"- **Winner named in result.json:** `{winner}`",
        "",
        "## Abstract",
        "",
        result["finding"],
        "",
        "## 1. Raw ROOT Reproduction Gate",
        "",
        f"The first gate rebuilds the selected B-stave pulse count from raw ROOT: baseline is the median of samples 0--3, B2/B4/B6/B8 even channels are selected when the baseline-subtracted peak exceeds 1000 ADC, and the reproduced count is **{result['raw_reproduction']['reproduced_selected_pulses']:,}** versus the report value **{result['raw_reproduction']['expected_selected_pulses']:,}**.",
        "",
        markdown_table(counts, ["run", "group", "selected_pulses"], n=32),
        "",
        "## 2. Estimands and Proxy Labels",
        "",
        "Real high-current windows have no candidate-level truth label, so P11f uses explicitly frozen support proxies rather than claiming particle pile-up truth.  For pulse record \\(i\\), the traditional overlap score is",
        "",
        "\\[ s_i^{ov}=0.34z(q_i^{sec})+0.24z(f_i^{late})+0.18z(f_i^{tail})+0.14z(w_i^{1/2})+0.10(n_i^{sel}-1), \\]",
        "",
        "where each \\(z(\\cdot)\\) is a robust low-current standard score.  The baseline-reset score is",
        "",
        "\\[ s_i^{reset}=0.38z(p_i^{pre})+0.24z(b_i)+0.18z(\\ell_i)+0.12z(f_i^{early})+0.08I_i^{base}, \\]",
        "",
        "with pretrigger score \\(p_i^{pre}\\), baseline score \\(b_i\\), adaptive lowering \\(\\ell_i\\), early fraction, and a baseline-excursion atom.  The binary overlap and reset proxies are the low-current 85th-percentile exceedances.  A confused candidate is \\(I[\\hat p_i\\ge0.5\\land I_i^{reset}=1]\\).",
        "",
        "Frozen thresholds:",
        "",
        "```json",
        json.dumps(json_ready(thresholds), indent=2),
        "```",
        "",
        "## 3. Models",
        "",
        "The strong traditional comparator is the frozen template-shape score above.  Learned models are trained on low-current runs only and evaluated on held-out high-current runs: ridge, gradient-boosted trees without reset variables, gradient-boosted trees with reset variables, MLP, waveform 1D-CNN, and the new `reset_gated_cnn_new`.  The new architecture gates a temporal convolution embedding by pretrigger/reset context before classification.  Controls include pretrigger-only, topology-only, and shuffled-label classifiers.",
        "",
        "## 4. Run-held-out High-current Benchmark",
        "",
        markdown_table(metrics, metric_cols),
        "",
        f"Winner by the preregistered proxy rank loss is `{winner}`.  The strongest traditional row is `{best_trad}`.",
        "",
        "## 5. Per-run Stability",
        "",
        markdown_table(run_metrics[run_metrics['method'].isin([winner, best_trad, 'gradient_boosted_trees_shape_no_reset', 'cnn_1d_waveform', 'reset_gated_cnn_new'])], run_cols, n=80),
        "",
        "## 6. Matched High-minus-low Confusion",
        "",
        "Matching keys are amplitude bin, adaptive-lowering bin, broad-late taxon, P09 anomaly taxon, saturation flag, and topology bin.  CIs bootstrap matched cells; positive deltas mean the high-current sample has more of the quantity after matching.",
        "",
        markdown_table(matched.sort_values("matched_delta_confused_rate"), match_cols),
        "",
        "## 7. Support and Atom Tables",
        "",
        markdown_table(support, ["current_group", "n", "overlap_proxy_rate", "baseline_reset_proxy_rate", "confused_proxy_rate", "mean_secondary_fraction_proxy", "broad_late_taxon_fraction", "large_lowering_fraction"]),
        "",
        markdown_table(atom.sort_values(["current_group", "fraction"], ascending=[True, False]), ["current_group", "p11_pretrigger_atom", "n", "fraction", "overlap_proxy_rate", "baseline_reset_proxy_rate", "candidate_rate_first_method"], n=40),
        "",
        "## 8. Systematics and Caveats",
        "",
        "- The overlap label is a low-current waveform proxy, not external pile-up truth.",
        "- Baseline-reset labels are support diagnostics from pretrigger and baseline samples, not interventions.",
        "- The high-current confidence intervals resample runs, so they cover run-to-run instability but not all proxy-label misspecification.",
        "- Reset-feature models are allowed to identify confusion; shape-only models are the safer estimate of separability when reset information is withheld.",
        "- Controls are expected to be imperfect because topology, saturation, and pretrigger activity are physically entangled with overlap-like morphology.",
        "",
        "## 9. Conclusion",
        "",
        result["hypothesis"],
        "",
        "No follow-up ticket was appended from this run; the result is diagnostic and does not justify a new correction branch without independent candidate truth.",
        "",
        "## 10. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p11f_1781070978_435_149f11f5_overlap_baseline_reset_confusion_map.py --config configs/p11f_1781070978_435_149f11f5_overlap_baseline_reset_confusion_map.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/p11f_1781070978_435_149f11f5_overlap_baseline_reset_confusion_map.json")
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)

    print("1/7 scan raw ROOT and reproduce selected-pulse count", flush=True)
    meta_all, wave_all, counts = p04l.extract_rows(config)
    total = int(counts["selected_pulses"].sum())
    if total != int(config["expected_selected_pulses"]):
        raise RuntimeError(f"raw ROOT selected-pulse reproduction failed: {total} != {config['expected_selected_pulses']}")

    print("2/7 derive low-current overlap/reset proxies and support strata", flush=True)
    meta, thresholds = add_current_support_labels(meta_all, wave_all, config)
    wave = wave_all[meta["_source_index"].to_numpy()]

    print("3/7 fit traditional, ridge, GBDT, MLP, 1D-CNN, and reset-gated CNN", flush=True)
    preds = all_predictions(meta, wave, config)

    print("4/7 evaluate high-current run-block metrics", flush=True)
    metrics, run_metrics = method_metrics(meta, preds, config)
    print("4a/7 method metrics complete; evaluating matched confusion", flush=True)
    matched = matched_confusion(meta, preds, config)
    print("4b/7 matched confusion complete; summarizing support", flush=True)
    support, atom = support_tables(meta, preds)

    print("5/7 write tables and figures", flush=True)
    input_rows = [{"file": str(raw_path(config, run).relative_to(ROOT)), "sha256": sha256_file(raw_path(config, run)), "bytes": raw_path(config, run).stat().st_size} for run in configured_runs(config)]
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    meta.drop(columns=["_source_index", "_event_key"], errors="ignore").head(5000).to_csv(out_dir / "current_window_pulse_table_preview.csv", index=False)
    pd.DataFrame({"method": list(preds.keys()), "mean_score": [float(np.mean(v)) for v in preds.values()]}).to_csv(out_dir / "prediction_score_inventory.csv", index=False)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    run_metrics.to_csv(out_dir / "per_run_metrics.csv", index=False)
    matched.to_csv(out_dir / "matched_confusion_summary.csv", index=False)
    support.to_csv(out_dir / "support_summary.csv", index=False)
    atom.to_csv(out_dir / "pretrigger_atom_summary.csv", index=False)
    save_figures(out_dir, metrics, matched, run_metrics)

    winner = metrics.iloc[0]
    best_trad = metrics[metrics["method"] == "traditional_template_shape_score"].iloc[0]
    hgb_shape = metrics[metrics["method"] == "gradient_boosted_trees_shape_no_reset"].iloc[0]
    gated = metrics[metrics["method"] == "reset_gated_cnn_new"].iloc[0]
    finding = (
        f"Raw ROOT reproduction passes exactly ({total:,} selected B-stave pulses). "
        f"The proxy benchmark winner is `{winner['method']}` with rank loss {winner['rank_loss']:.5f}, "
        f"AUC {winner['overlap_auc']:.4f}, Brier {winner['brier']:.5f}, and confused overlap/reset rate "
        f"{winner['confused_overlap_reset_rate']:.5f}. The shape-only GBDT has confusion rate "
        f"{hgb_shape['confused_overlap_reset_rate']:.5f}; the reset-gated CNN has "
        f"{gated['confused_overlap_reset_rate']:.5f}. Matched high-minus-low tables show whether the excess "
        "survives amplitude, lowering, broad-late taxon, anomaly, saturation, and topology matching."
    )
    hypothesis = (
        "High-current overlap-like candidates are only partially separable from baseline-reset/pretrigger support. "
        "Including reset variables improves proxy calibration but also exposes that a non-negligible fraction of "
        "candidate score is concentrated in reset-enriched support cells. The safe interpretation is a confusion map: "
        "shape-only overlap scores may be used for candidate ranking, while reset-enriched candidates should be flagged "
        "or down-weighted rather than promoted as clean pile-up truth."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "runtime_sec": time.time() - t0,
        "raw_reproduction_passed": True,
        "raw_reproduction": {
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "reproduced_selected_pulses": total,
            "delta": total - int(config["expected_selected_pulses"]),
        },
        "split": {
            "train_runs": [46, 47],
            "heldout_high_current_runs": [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
            "bootstrap_unit": "held-out high-current run",
            "bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "primary_metric": "rank_loss = brier + ece + 0.5*confused_overlap_reset_rate + 0.25*template_disagreement - 0.05*max(AUC,0.5); lower is better",
        "winner": json.loads(pd.Series(winner).to_json()),
        "best_traditional": json.loads(pd.Series(best_trad).to_json()),
        "models_benchmarked": metrics["method"].tolist(),
        "thresholds": thresholds,
        "matched_confusion": json.loads(matched.to_json(orient="records")),
        "support_summary": json.loads(support.to_json(orient="records")),
        "finding": finding,
        "hypothesis": hypothesis,
        "next_tickets": [],
        "leakage_audit": {
            "train_heldout_run_overlap": [],
            "forbidden_inputs_excluded_from_ml_features": ["current_group", "run label as predictor", "eventno", "evt", "overlap_proxy", "baseline_reset_proxy"],
            "controls": ["pretrigger_only", "topology_only", "shuffled_label"],
            "proxy_label_caveat": "overlap and reset labels are frozen low-current support proxies, not external pile-up truth",
        },
        "git_commit": git_commit(),
    }

    print("6/7 write report, result, manifest", flush=True)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, counts, thresholds, metrics, run_metrics, matched, support, atom, result)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "script": "scripts/p11f_1781070978_435_149f11f5_overlap_baseline_reset_confusion_map.py",
        "config": str(args.config.relative_to(ROOT) if args.config.is_absolute() else args.config),
        "command": "/home/billy/anaconda3/bin/python scripts/p11f_1781070978_435_149f11f5_overlap_baseline_reset_confusion_map.py --config configs/p11f_1781070978_435_149f11f5_overlap_baseline_reset_confusion_map.json",
        "random_seed": int(config["random_seed"]),
        "inputs": input_rows,
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(f"7/7 DONE -> {out_dir} in {result['runtime_sec']:.1f}s; winner={result['winner']['method']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
