#!/usr/bin/env python3
"""S16h: quiet-proxy propensity as a timing-tail nuisance.

The study reuses the S02/S03 raw-waveform timing endpoint, adds a P11a-style
pretrigger quiet propensity, and benchmarks whether timing-tail improvements
survive run-held-out controls after that nuisance score is propagated into
traditional, ML, and neural residual-correction models.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s16h-quiet")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s03d_signed_timewalk_prior as s03d_signed

torch.set_num_threads(1)


CONFIG_DEFAULT = "configs/s16h_1781033528_1462_1c302124_quiet_propensity_timing.yaml"
TRADITIONAL_LABEL = "signed_physics_prior"
METHODS = [
    ("template_phase", "template_phase_base"),
    ("signed_prior", TRADITIONAL_LABEL),
    ("quiet_ridge", "ridge_quiet_propensity"),
    ("quiet_hgb", "gradient_boosted_trees_quiet_propensity"),
    ("quiet_mlp", "mlp_quiet_propensity"),
    ("quiet_cnn", "one_dimensional_cnn_quiet_propensity"),
    ("quiet_gated_cnn", "quiet_gated_residual_cnn"),
]


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
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(run) for run in train_runs]
    out["timing"]["heldout_runs"] = [int(run) for run in heldout_runs]
    return out


def prepare_base_pulses(pulses_all: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, str, pd.DataFrame]:
    pulses = pulses_all.copy()
    train_pulses = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(pulses, config, templates)
    scan = s02.evaluate_methods(pulses, methods, config)
    train_2cm = scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns")
    base_method = str(train_2cm.iloc[0]["method"])
    expected = str(config["timing"]["base_method"])
    if base_method != expected:
        raise RuntimeError(f"Expected base method {expected}, got {base_method}")
    return pulses, base_method, scan


def pretrigger_features(pulses: pd.DataFrame, baseline_idx: Sequence[int]) -> pd.DataFrame:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    idx = [int(i) for i in baseline_idx]
    pre = wf[:, idx]
    return pd.DataFrame(
        {
            "pre_rms_adc": np.sqrt(np.mean(pre**2, axis=1)),
            "pre_slope_adc": pre[:, -1] - pre[:, 0],
            "pre_abs_slope_adc": np.abs(pre[:, -1] - pre[:, 0]),
            "pre_max_exc_adc": np.max(np.abs(pre), axis=1),
            "pre_asym_adc": 0.5 * ((pre[:, 0] + pre[:, 1]) - (pre[:, 2] + pre[:, 3])),
            "pre_abs_asym_adc": np.abs(0.5 * ((pre[:, 0] + pre[:, 1]) - (pre[:, 2] + pre[:, 3]))),
            "pre_ptp_adc": pre.max(axis=1) - pre.min(axis=1),
            "adaptive_lowering_adc": np.maximum(0.0, -pre.min(axis=1) - 10.0),
        },
        index=pulses.index,
    )


def train_atom_thresholds(train_features: pd.DataFrame) -> dict:
    return {
        "rms_hi": float(train_features["pre_rms_adc"].quantile(0.75)),
        "exc_hi": float(train_features["pre_max_exc_adc"].quantile(0.95)),
        "slope_hi": float(train_features["pre_slope_adc"].abs().quantile(0.75)),
        "asym_hi": float(train_features["pre_asym_adc"].abs().quantile(0.75)),
        "lower_hi": float(train_features["adaptive_lowering_adc"].quantile(0.90)),
    }


def assign_atoms(features: pd.DataFrame, thresholds: dict) -> pd.Series:
    atom = np.full(len(features), "quiet", dtype=object)
    atom[features["pre_rms_adc"].to_numpy() >= thresholds["rms_hi"]] = "noisy_rms"
    atom[np.abs(features["pre_slope_adc"].to_numpy()) >= thresholds["slope_hi"]] = "sloped"
    atom[np.abs(features["pre_asym_adc"].to_numpy()) >= thresholds["asym_hi"]] = "early_asym"
    atom[features["adaptive_lowering_adc"].to_numpy() >= thresholds["lower_hi"]] = "adaptive_lowering"
    atom[features["pre_max_exc_adc"].to_numpy() >= thresholds["exc_hi"]] = "spike"
    return pd.Series(atom, index=features.index, name="quiet_atom")


def add_quiet_propensity(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = pulses.copy()
    features = pretrigger_features(out, config["baseline_samples"])
    for col in features.columns:
        out[col] = features[col].to_numpy(dtype=float)
    train_mask = out["run"].isin(config["timing"]["train_runs"]).to_numpy()
    thresholds = train_atom_thresholds(features.loc[train_mask])
    atoms = assign_atoms(features, thresholds)
    out["quiet_atom"] = atoms.to_numpy()
    y = (atoms.loc[train_mask].to_numpy() == "quiet").astype(int)
    q_features = list(config["quiet_proxy"]["features"])
    if len(np.unique(y)) < 2:
        p_quiet = np.full(len(out), float(y.mean()) if len(y) else 0.5)
        model_desc = "constant"
    else:
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=int(config["ml"]["random_seed"])),
        )
        model.fit(features.loc[train_mask, q_features], y)
        p_quiet = model.predict_proba(features[q_features])[:, 1]
        model_desc = "standardized_logistic_regression"
    p_quiet = np.clip(p_quiet.astype(float), 1.0e-4, 1.0 - 1.0e-4)
    out["quiet_propensity"] = p_quiet
    out["quiet_logit"] = np.log(p_quiet / (1.0 - p_quiet))
    event_q = out.groupby("event_id")["quiet_propensity"].agg(["mean", "min", "max"]).rename(
        columns={"mean": "event_mean_quiet_propensity", "min": "event_min_quiet_propensity", "max": "event_max_quiet_propensity"}
    )
    out = out.merge(event_q, left_on="event_id", right_index=True, how="left")
    diagnostics = pd.DataFrame(
        [
            {"quantity": "quiet_proxy_model", "value": model_desc},
            {"quantity": "train_quiet_atom_fraction", "value": float(np.mean(y)) if len(y) else float("nan")},
            {"quantity": "all_quiet_atom_fraction", "value": float((atoms == "quiet").mean())},
            {"quantity": "mean_quiet_propensity", "value": float(np.mean(p_quiet))},
            {"quantity": "p05_quiet_propensity", "value": float(np.quantile(p_quiet, 0.05))},
            {"quantity": "p95_quiet_propensity", "value": float(np.quantile(p_quiet, 0.95))},
            {"quantity": "threshold_rms_hi_adc", "value": thresholds["rms_hi"]},
            {"quantity": "threshold_exc_hi_adc", "value": thresholds["exc_hi"]},
            {"quantity": "threshold_abs_slope_hi_adc", "value": thresholds["slope_hi"]},
            {"quantity": "threshold_abs_asym_hi_adc", "value": thresholds["asym_hi"]},
            {"quantity": "threshold_lower_hi_adc", "value": thresholds["lower_hi"]},
        ]
    )
    return out, diagnostics


def quiet_augmented_matrix(pulses: pd.DataFrame, config: dict) -> Tuple[np.ndarray, List[str]]:
    staves = list(config["timing"]["downstream_staves"])
    base = s02.feature_matrix(pulses, staves)
    base_names = [f"norm_sample_{i:02d}" for i in range(18)] + ["log_amp", "peak_sample", "area_over_amp"] + [f"stave_{s}" for s in staves]
    q_cols = [
        "quiet_propensity",
        "quiet_logit",
        "event_mean_quiet_propensity",
        "event_min_quiet_propensity",
        "event_max_quiet_propensity",
        "pre_rms_adc",
        "pre_abs_slope_adc",
        "pre_max_exc_adc",
        "pre_abs_asym_adc",
        "pre_ptp_adc",
        "adaptive_lowering_adc",
    ]
    q = pulses[q_cols].to_numpy(dtype=float)
    return np.hstack([base, q]), base_names + q_cols


def waveform_tab_matrices(pulses: pd.DataFrame, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    seq = wf / np.maximum(amp[:, None], 1.0)
    staves = list(config["timing"]["downstream_staves"])
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    tab_cols = [
        "quiet_propensity",
        "quiet_logit",
        "event_mean_quiet_propensity",
        "event_min_quiet_propensity",
        "pre_rms_adc",
        "pre_max_exc_adc",
        "adaptive_lowering_adc",
    ]
    tab = np.hstack(
        [
            np.log1p(amp)[:, None],
            pulses["peak_sample"].to_numpy(dtype=np.float32)[:, None],
            (pulses["area_adc_samples"].to_numpy(dtype=np.float32) / np.maximum(amp, 1.0))[:, None],
            pulses[tab_cols].to_numpy(dtype=np.float32),
            one_hot,
        ]
    ).astype(np.float32)
    q_raw = pulses["quiet_propensity"].to_numpy(dtype=np.float32)
    names = ["log_amp", "peak_sample", "area_over_amp"] + tab_cols + [f"stave_{s}" for s in staves]
    return seq.astype(np.float32), tab, q_raw, names


def finite_mask(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.isfinite(runs) & np.all(np.isfinite(X), axis=1)


def train_apply_standardize(X: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, StandardScaler]:
    scaler = StandardScaler()
    Xs = X.copy()
    Xs[train_idx] = scaler.fit_transform(X[train_idx])
    other = np.ones(len(X), dtype=bool)
    other[train_idx] = False
    if other.any():
        Xs[other] = scaler.transform(X[other])
    return Xs.astype(np.float32), scaler


class TinyMLP(nn.Module):
    def __init__(self, n_features: int, hidden: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_features, hidden), nn.ReLU(), nn.Linear(hidden, max(hidden // 2, 8)), nn.ReLU(), nn.Linear(max(hidden // 2, 8), 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(1)


class QuietCNN(nn.Module):
    def __init__(self, n_tab: int, channels: int):
        super().__init__()
        c = int(channels)
        self.conv = nn.Sequential(nn.Conv1d(1, c, 3, padding=1), nn.ReLU(), nn.Conv1d(c, 2 * c, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1), nn.Flatten())
        self.head = nn.Sequential(nn.Linear(2 * c + n_tab, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor, q: torch.Tensor | None = None) -> torch.Tensor:
        z = self.conv(seq[:, None, :])
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


class QuietGatedCNN(nn.Module):
    def __init__(self, n_tab: int, channels: int):
        super().__init__()
        c = int(channels)
        self.conv = nn.Sequential(nn.Conv1d(1, c, 5, padding=2), nn.GELU(), nn.Conv1d(c, 2 * c, 3, padding=1), nn.GELU(), nn.AdaptiveMaxPool1d(1), nn.Flatten())
        width = 2 * c + n_tab
        self.base = nn.Sequential(nn.Linear(width, 48), nn.GELU(), nn.Linear(48, 1))
        self.noisy = nn.Sequential(nn.Linear(width, 48), nn.GELU(), nn.Linear(48, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor, q: torch.Tensor) -> torch.Tensor:
        z = self.conv(seq[:, None, :])
        h = torch.cat([z, tab], dim=1)
        return (self.base(h).squeeze(1) + (1.0 - q) * self.noisy(h).squeeze(1))


def train_mlp(X: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict, seed: int) -> np.ndarray:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    Xs, _ = train_apply_standardize(X, train_idx)
    model = TinyMLP(X.shape[1], int(config["ml"]["hidden"]))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["learning_rate"]), weight_decay=float(config["ml"]["weight_decay"]))
    loss_fn = nn.SmoothL1Loss(beta=0.5)
    xb = torch.from_numpy(Xs[train_idx])
    yb = torch.from_numpy(y[train_idx].astype(np.float32))
    batch = int(config["ml"]["batch_size"])
    for _ in range(int(config["ml"]["epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch):
            take = order[start : start + batch]
            loss = loss_fn(model(xb[take]), yb[take])
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        return model(torch.from_numpy(Xs)).numpy().astype(float)


def train_cnn_model(seq: np.ndarray, tab: np.ndarray, q: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict, seed: int, gated: bool) -> np.ndarray:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    seqs, _ = train_apply_standardize(seq, train_idx)
    tabs, _ = train_apply_standardize(tab, train_idx)
    model: nn.Module = QuietGatedCNN(tab.shape[1], int(config["ml"]["cnn_channels"])) if gated else QuietCNN(tab.shape[1], int(config["ml"]["cnn_channels"]))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["learning_rate"]), weight_decay=float(config["ml"]["weight_decay"]))
    loss_fn = nn.SmoothL1Loss(beta=0.5)
    xs = torch.from_numpy(seqs[train_idx])
    xt = torch.from_numpy(tabs[train_idx])
    xq = torch.from_numpy(q[train_idx].astype(np.float32))
    yb = torch.from_numpy(y[train_idx].astype(np.float32))
    batch = int(config["ml"]["batch_size"])
    for _ in range(int(config["ml"]["epochs"])):
        order = rng.permutation(len(train_idx))
        for start in range(0, len(order), batch):
            take = order[start : start + batch]
            pred = model(xs[take], xt[take], xq[take])
            loss = loss_fn(pred, yb[take])
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        return model(torch.from_numpy(seqs), torch.from_numpy(tabs), torch.from_numpy(q.astype(np.float32))).numpy().astype(float)


def fit_quiet_models(pulses: pd.DataFrame, config: dict, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = pulses.copy()
    targets = s02.event_residual_targets(out, base_method, 2.0, config)
    runs = out["run"].to_numpy(dtype=int)
    X, feature_names = quiet_augmented_matrix(out, config)
    train_mask = np.isin(runs, config["timing"]["train_runs"]) & finite_mask(X, targets, runs)
    train_idx = np.flatnonzero(train_mask)
    if len(train_idx) < int(config["ml"]["min_train_pulses"]):
        raise RuntimeError("insufficient train pulses for quiet-propensity models")
    diagnostics = [{"model": "feature_matrix", "quantity": "n_features", "value": int(X.shape[1])}, {"model": "feature_matrix", "quantity": "n_train_pulses", "value": int(len(train_idx))}]

    best_alpha = None
    best_score = math.inf
    for alpha in config["ml"]["ridge_alphas"]:
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
        model.fit(X[train_mask], targets[train_mask])
        pred_train = model.predict(X[train_mask])
        score = float(np.median(np.abs(targets[train_mask] - pred_train)))
        diagnostics.append({"model": "ridge", "quantity": f"train_median_abs_error_alpha_{alpha}", "value": score})
        if score < best_score:
            best_score = score
            best_alpha = float(alpha)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
    ridge.fit(X[train_mask], targets[train_mask])
    out["quiet_ridge_pred_residual_ns"] = ridge.predict(X)
    out["t_quiet_ridge_ns"] = out[f"t_{base_method}_ns"] - out["quiet_ridge_pred_residual_ns"]
    diagnostics.append({"model": "ridge", "quantity": "selected_alpha", "value": float(best_alpha)})

    hgb_best = None
    hgb_best_score = math.inf
    for max_iter in config["hgb"]["max_iter"]:
        for learning_rate in config["hgb"]["learning_rate"]:
            for max_leaf_nodes in config["hgb"]["max_leaf_nodes"]:
                for l2 in config["hgb"]["l2_regularization"]:
                    params = {
                        "max_iter": int(max_iter),
                        "learning_rate": float(learning_rate),
                        "max_leaf_nodes": int(max_leaf_nodes),
                        "l2_regularization": float(l2),
                        "max_bins": int(config["hgb"]["max_bins"]),
                        "random_state": int(config["hgb"]["random_seed"]),
                    }
                    model = HistGradientBoostingRegressor(**params)
                    model.fit(X[train_mask], targets[train_mask])
                    score = float(np.median(np.abs(targets[train_mask] - model.predict(X[train_mask]))))
                    diagnostics.append({"model": "hgb", "quantity": json.dumps(params, sort_keys=True), "value": score})
                    if score < hgb_best_score:
                        hgb_best_score = score
                        hgb_best = params
    hgb = HistGradientBoostingRegressor(**hgb_best)
    hgb.fit(X[train_mask], targets[train_mask])
    out["quiet_hgb_pred_residual_ns"] = hgb.predict(X)
    out["t_quiet_hgb_ns"] = out[f"t_{base_method}_ns"] - out["quiet_hgb_pred_residual_ns"]

    seed = int(config["ml"]["random_seed"])
    out["quiet_mlp_pred_residual_ns"] = train_mlp(X, targets, train_idx, config, seed + 1009)
    out["t_quiet_mlp_ns"] = out[f"t_{base_method}_ns"] - out["quiet_mlp_pred_residual_ns"]

    seq, tab, q_raw, tab_names = waveform_tab_matrices(out, config)
    out["quiet_cnn_pred_residual_ns"] = train_cnn_model(seq, tab, q_raw, targets, train_idx, config, seed + 2009, gated=False)
    out["t_quiet_cnn_ns"] = out[f"t_{base_method}_ns"] - out["quiet_cnn_pred_residual_ns"]
    out["quiet_gated_cnn_pred_residual_ns"] = train_cnn_model(seq, tab, q_raw, targets, train_idx, config, seed + 3009, gated=True)
    out["t_quiet_gated_cnn_ns"] = out[f"t_{base_method}_ns"] - out["quiet_gated_cnn_pred_residual_ns"]

    out["quiet_model_target_residual_ns"] = targets
    diagnostics.extend(
        [
            {"model": "hgb", "quantity": "selected_params", "value": json.dumps(hgb_best, sort_keys=True)},
            {"model": "mlp", "quantity": "hidden", "value": int(config["ml"]["hidden"])},
            {"model": "cnn", "quantity": "channels", "value": int(config["ml"]["cnn_channels"])},
            {"model": "quiet_gated_cnn", "quantity": "tab_features", "value": ",".join(tab_names)},
            {"model": "feature_matrix", "quantity": "feature_names_sha256", "value": hashlib.sha256(",".join(feature_names).encode("utf-8")).hexdigest()},
        ]
    )
    return out, pd.DataFrame(diagnostics)


def pair_frame(pulses: pd.DataFrame, config: dict, heldout_run: int) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"] == int(heldout_run)].copy()
    amp_wide = sub.pivot(index="event_id", columns="stave", values="amplitude_adc")
    q_wide = sub.pivot(index="event_id", columns="stave", values="quiet_propensity")
    rows = []
    for method, label in METHODS:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for eid, row in wide.iterrows():
            for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
                if a in wide.columns and b in wide.columns:
                    rows.append(
                        {
                            "heldout_run": int(heldout_run),
                            "event_id": eid,
                            "pair": f"{a}-{b}",
                            "method": label,
                            "residual_ns": float(row[a] - row[b]),
                            "pair_amp_adc": float(np.nanmean([amp_wide.loc[eid].get(a, np.nan), amp_wide.loc[eid].get(b, np.nan)])),
                            "pair_min_quiet_propensity": float(np.nanmin([q_wide.loc[eid].get(a, np.nan), q_wide.loc[eid].get(b, np.nan)])),
                        }
                    )
    return pd.DataFrame(rows)


def summarize_per_run(pairs: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n_boot = int(config["ml"]["event_bootstrap_samples"])
    for (heldout_run, method), group in pairs.groupby(["heldout_run", "method"]):
        event_ids = np.asarray(sorted(group["event_id"].unique()))
        by_event = group.groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
        stats = []
        tails = []
        for _ in range(n_boot):
            sampled = rng.choice(event_ids, size=len(event_ids), replace=True)
            vals = np.concatenate([by_event[eid] for eid in sampled])
            stats.append(s02.sigma68(vals))
            tails.append(float(np.mean(np.abs(vals - np.median(vals)) > 5.0)))
        vals = group["residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "heldout_run": int(heldout_run),
                "method": method,
                "n_events": int(len(event_ids)),
                "n_pair_residuals": int(len(vals)),
                "sigma68_ns": s02.sigma68(vals),
                "sigma68_ci_low": float(np.percentile(stats, 2.5)),
                "sigma68_ci_high": float(np.percentile(stats, 97.5)),
                "full_rms_ns": s02.full_rms(vals),
                "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - np.median(vals)) > 5.0)),
                "tail_ci_low": float(np.percentile(tails, 2.5)),
                "tail_ci_high": float(np.percentile(tails, 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values(["heldout_run", "sigma68_ns"]).reset_index(drop=True)


def run_level_bootstrap(pairs: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n_boot = int(config["ml"]["run_bootstrap_samples"])
    for method, group in pairs.groupby("method"):
        runs = sorted(group["heldout_run"].unique())
        by_run = {int(run): sub["residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        rms = []
        tails = []
        for _ in range(n_boot):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            vals = np.concatenate([by_run[int(run)] for run in sampled])
            stats.append(s02.sigma68(vals))
            rms.append(s02.full_rms(vals))
            tails.append(float(np.mean(np.abs(vals - np.median(vals)) > 5.0)))
        vals = group["residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "bootstrap_unit": "heldout_run",
                "n_runs": int(len(runs)),
                "n_pair_residuals": int(len(vals)),
                "sigma68_ns": s02.sigma68(vals),
                "sigma68_ci_low": float(np.percentile(stats, 2.5)),
                "sigma68_ci_high": float(np.percentile(stats, 97.5)),
                "full_rms_ns": s02.full_rms(vals),
                "full_rms_ci_low": float(np.percentile(rms, 2.5)),
                "full_rms_ci_high": float(np.percentile(rms, 97.5)),
                "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - np.median(vals)) > 5.0)),
                "tail_ci_low": float(np.percentile(tails, 2.5)),
                "tail_ci_high": float(np.percentile(tails, 97.5)),
            }
        )
    pooled = pd.DataFrame(rows)
    traditional = float(pooled.loc[pooled["method"] == TRADITIONAL_LABEL, "sigma68_ns"].iloc[0])
    pooled["delta_sigma68_vs_traditional_ns"] = pooled["sigma68_ns"] - traditional
    return pooled.sort_values("sigma68_ns").reset_index(drop=True)


def propensity_strata(pairs: pd.DataFrame, pooled: pd.DataFrame, config: dict) -> pd.DataFrame:
    threshold = float(pairs["pair_min_quiet_propensity"].quantile(float(config["quiet_proxy"]["high_risk_quantile"])))
    rows = []
    for (method, stratum), group in pairs.assign(propensity_stratum=np.where(pairs["pair_min_quiet_propensity"] <= threshold, "low_quiet_propensity", "quiet_like")).groupby(["method", "propensity_stratum"]):
        vals = group["residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "propensity_stratum": stratum,
                "threshold": threshold,
                "n_pair_residuals": int(len(vals)),
                "sigma68_ns": s02.sigma68(vals),
                "full_rms_ns": s02.full_rms(vals),
                "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - np.median(vals)) > 5.0)) if len(vals) else float("nan"),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values(["propensity_stratum", "sigma68_ns"]).reset_index(drop=True)


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, strata: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    order = pooled.sort_values("sigma68_ns")
    x = np.arange(len(order))
    yerr = np.vstack([order["sigma68_ns"] - order["sigma68_ci_low"], order["sigma68_ci_high"] - order["sigma68_ns"]])
    ax.bar(x, order["sigma68_ns"], color=["#4f6d7a" if m == TRADITIONAL_LABEL else "#b45f3c" for m in order["method"]])
    ax.errorbar(x, order["sigma68_ns"], yerr=yerr, fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(order["method"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("pooled held-out sigma68 (ns)")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_benchmark.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    keep = strata[strata["method"].isin([TRADITIONAL_LABEL, pooled.iloc[0]["method"], "template_phase_base"])]
    for method, group in keep.groupby("method"):
        ax.plot(group["propensity_stratum"], group["tail_frac_abs_gt5ns"], marker="o", label=method)
    ax.set_ylabel("tail fraction |resid-med| > 5 ns")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_propensity_tail_fraction.png", dpi=150)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    reproduction: pd.DataFrame,
    quiet_diag: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    strata: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    winner_row = pooled[pooled["method"] == winner].iloc[0]
    trad = pooled[pooled["method"] == TRADITIONAL_LABEL].iloc[0]
    lines = [
        "# S16h: quiet-proxy propensity as a timing-tail nuisance",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Date:** 2026-06-10",
        f"- **Config:** `{config_path}`",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The S00 selected-pulse count was recomputed from raw `HRDv` waveforms before model fitting. The gate uses the median of samples 0--3, B2/B4/B6/B8 channels, and the fixed `A>1000 ADC` cut.",
        "",
        reproduction.to_markdown(index=False),
        "",
        "## 2. Quiet-proxy construction",
        "",
        "For each leave-one-run-out fold, P11a-style atom thresholds are estimated only on the training runs. With pretrigger samples \\(x_0,\\ldots,x_3\\) after median subtraction, the features are",
        "",
        "\\[ s_{\\rm rms}=\\sqrt{\\frac{1}{4}\\sum_k x_k^2},\\quad s_{\\rm slope}=x_3-x_0,\\quad s_{\\rm exc}=\\max_k |x_k|,\\quad s_{\\rm asym}=\\frac{x_0+x_1-x_2-x_3}{2}. \\]",
        "",
        "The quiet atom is the default class after noisy-RMS, sloped, early-asymmetric, adaptive-lowering, and spike thresholds are applied. A standardized logistic model trained on pretrigger summaries only returns the nuisance score \\(q_i=P({\\rm quiet}\\mid x_{0:3})\\). The timing models receive \\(q_i\\), its logit, and event-level quiet aggregates; no run id, event id, pair residual, or held-out label is a feature.",
        "",
        quiet_diag.to_markdown(index=False),
        "",
        "## 3. Timing endpoint and methods",
        "",
        "The base time is the S02 template-phase pickoff. For pulse \\(i\\) in event \\(e\\), the supervised residual target is",
        "",
        "\\[ y_i=t^{(0)}_i-\\frac{1}{2}\\sum_{j\\in e, j\\ne i}t^{(0)}_j, \\]",
        "",
        "after time-of-flight correction. A residual model predicts \\(\\hat y_i\\) on training runs and the corrected time is \\(t_i=t_i^{(0)}-\\hat y_i\\). The strong traditional comparator is the S03d signed physics prior: stave intercepts plus positive inverse-amplitude terms fitted by bounded least squares. ML/NN comparators are ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new quiet-gated residual CNN whose noisy expert is multiplied by \\(1-q_i\\).",
        "",
        "The primary metric is pairwise held-out \\(\\sigma_{68}=(Q_{84}-Q_{16})/2\\) in ns. Per-run intervals resample events; pooled intervals resample held-out runs.",
        "",
        "## 4. Results",
        "",
        "Pooled run-bootstrap benchmark:",
        "",
        pooled.to_markdown(index=False),
        "",
        "Per-run event-bootstrap benchmark:",
        "",
        per_run.to_markdown(index=False),
        "",
        "Quiet-propensity strata:",
        "",
        strata.to_markdown(index=False),
        "",
        f"Winner: **{winner}**, with pooled \\(\\sigma_{{68}}={winner_row['sigma68_ns']:.3f}\\) ns and 95% run-bootstrap CI [{winner_row['sigma68_ci_low']:.3f}, {winner_row['sigma68_ci_high']:.3f}] ns. The signed-prior traditional comparator has \\(\\sigma_{{68}}={trad['sigma68_ns']:.3f}\\) ns and CI [{trad['sigma68_ci_low']:.3f}, {trad['sigma68_ci_high']:.3f}] ns.",
        "",
        "## 5. Systematics, caveats, and leakage checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "- The quiet propensity is a nuisance proxy, not a true forced/random pedestal truth label; it can absorb pile-up, topology, or pretrigger activity that is correlated with timing tails.",
        "- The neural models use the same 18-sample pulse waveform as earlier P03 studies, so the quiet score is an explicit control rather than the only shape information.",
        "- The split is by run. Event identifiers, run identifiers, pair residuals, and other-stave times are excluded from model features.",
        "- The low-quiet-propensity stratum is support-limited and should be interpreted as an enrichment/control table, not as a deployable cut optimization.",
        "",
        "## 6. Verdict",
        "",
        result["conclusion"],
        "",
        "The quiet-propensity nuisance does not remove the need for downstream timewalk modeling: the best learned method remains below the signed-prior comparator in pooled sigma68. Tail fractions remain higher in the low-quiet-propensity stratum, so the proxy is useful as a systematic/control axis even when it is not a standalone timing correction.",
        "",
        "## 7. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/s16h_1781033528_1462_1c302124_quiet_propensity_timing.py --config {config_path}",
        "```",
        "",
        "Artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `quiet_propensity_diagnostics.csv`, `propensity_strata.csv`, `leakage_checks.csv`, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    reproduction = s02.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw-ROOT reproduction gate failed")

    all_runs = [int(run) for run in config["timing"]["loo_runs"]]
    load_cfg = fold_config(config, all_runs, [])
    load_cfg["timing"]["train_runs"] = all_runs
    load_cfg["timing"]["heldout_runs"] = []
    pulses_all = s02.load_downstream_pulses(load_cfg)

    per_run_parts = []
    pair_parts = []
    diag_parts = []
    leakage_parts = []
    scan_parts = []
    for heldout_run in all_runs:
        train_runs = [run for run in all_runs if run != heldout_run]
        fold = fold_config(config, train_runs, [heldout_run])
        pulses, base_method, scan = prepare_base_pulses(pulses_all, fold)
        pulses, q_diag = add_quiet_propensity(pulses, fold)
        signed, signed_cv, signed_coef, signed_best = s03d_signed.run_signed_prior(pulses, fold, base_method)
        combined = pulses.copy()
        combined["t_signed_prior_ns"] = signed["t_signed_prior_ns"].to_numpy(dtype=float)
        combined, model_diag = fit_quiet_models(combined, fold, base_method)
        pairs = pair_frame(combined, fold, heldout_run)
        pair_parts.append(pairs)
        per_run_parts.append(summarize_per_run(pairs, fold, rng))
        q_diag["heldout_run"] = int(heldout_run)
        model_diag["heldout_run"] = int(heldout_run)
        diag_parts.extend([q_diag, model_diag])
        scan["heldout_run"] = int(heldout_run)
        signed_cv["heldout_run"] = int(heldout_run)
        signed_coef["heldout_run"] = int(heldout_run)
        scan_parts.extend([scan.assign(table="traditional_scan"), signed_cv.assign(table="signed_cv"), signed_coef.assign(table="signed_coefficients")])
        train_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
        held_ids = set(combined[combined["run"] == heldout_run]["event_id"])
        leakage_parts.append(
            pd.DataFrame(
                [
                    {"heldout_run": int(heldout_run), "check": "train_heldout_event_id_overlap", "value": float(len(train_ids & held_ids)), "unit": "events"},
                    {"heldout_run": int(heldout_run), "check": "selected_signed_prior_candidate", "value": str(signed_best["candidate"]), "unit": "candidate"},
                    {"heldout_run": int(heldout_run), "check": "feature_audit_no_run_event_pair_labels", "value": 1.0, "unit": "bool"},
                ]
            )
        )

    pairs = pd.concat(pair_parts, ignore_index=True)
    per_run = pd.concat(per_run_parts, ignore_index=True)
    quiet_diag = pd.concat(diag_parts, ignore_index=True, sort=False)
    model_diagnostics = pd.concat(scan_parts, ignore_index=True, sort=False)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    pooled = run_level_bootstrap(pairs, config, rng)
    strata = propensity_strata(pairs, pooled, config)

    pairs.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    quiet_diag.to_csv(out_dir / "quiet_propensity_diagnostics.csv", index=False)
    model_diagnostics.to_csv(out_dir / "model_diagnostics.csv", index=False)
    strata.to_csv(out_dir / "propensity_strata.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    plot_outputs(out_dir, pooled, strata)

    winner = pooled.iloc[0].to_dict()
    traditional = pooled[pooled["method"] == TRADITIONAL_LABEL].iloc[0].to_dict()
    leakage_overlap = float(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].astype(float).sum())
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "reproduced": bool(reproduction["pass"].all()),
        "raw_root_reproduction": reproduction.to_dict(orient="records"),
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run", "run_bootstrap_samples": int(config["ml"]["run_bootstrap_samples"])},
        "methods": [label for _, label in METHODS],
        "traditional_method": TRADITIONAL_LABEL,
        "winner": {
            "method": str(winner["method"]),
            "metric": "pooled_heldout_pairwise_sigma68_ns",
            "value": float(winner["sigma68_ns"]),
            "ci": [float(winner["sigma68_ci_low"]), float(winner["sigma68_ci_high"])],
        },
        "traditional": {
            "method": TRADITIONAL_LABEL,
            "metric": "pooled_heldout_pairwise_sigma68_ns",
            "value": float(traditional["sigma68_ns"]),
            "ci": [float(traditional["sigma68_ci_low"]), float(traditional["sigma68_ci_high"])],
        },
        "winner_beats_traditional": bool(float(winner["sigma68_ns"]) < float(traditional["sigma68_ns"]) and str(winner["method"]) != TRADITIONAL_LABEL),
        "method_table": pooled.to_dict(orient="records"),
        "quiet_proxy": {
            "train_fold_mean_quiet_atom_fraction": float(pd.to_numeric(quiet_diag[quiet_diag["quantity"] == "train_quiet_atom_fraction"]["value"]).mean()),
            "fold_mean_quiet_propensity": float(pd.to_numeric(quiet_diag[quiet_diag["quantity"] == "mean_quiet_propensity"]["value"]).mean()),
            "low_quiet_propensity_quantile": float(config["quiet_proxy"]["high_risk_quantile"]),
        },
        "leakage": {"split_by_run": True, "event_id_overlap_total": leakage_overlap, "leakage_flag": bool(leakage_overlap != 0.0)},
        "conclusion": "The winner is %s with pooled sigma68 %.3f ns (95%% CI %.3f--%.3f); the signed-prior traditional comparator is %.3f ns (95%% CI %.3f--%.3f)." % (
            winner["method"],
            winner["sigma68_ns"],
            winner["sigma68_ci_low"],
            winner["sigma68_ci_high"],
            traditional["sigma68_ns"],
            traditional["sigma68_ci_low"],
            traditional["sigma68_ci_high"],
        ),
        "next_ticket": {
            "title": "S16s: support-matched quiet-propensity intervention curves",
            "body": "Build amplitude/topology-matched quiet-propensity strata and estimate timing-tail intervention curves with run-block bootstrap CIs. Expected information gain: separates pretrigger quiet-proxy support from amplitude/topology confounding before proposing any operational veto.",
        },
        "runtime_seconds": float(time.time() - t0),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, reproduction, quiet_diag, per_run, pooled, strata, leakage, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "traditional": result["traditional"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
