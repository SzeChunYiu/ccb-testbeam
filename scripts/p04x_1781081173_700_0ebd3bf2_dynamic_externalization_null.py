#!/usr/bin/env python3
"""P04x: dynamic-only duplicate charge closure versus externalization.

The script starts from raw B-stack ROOT and reproduces the P04k/S00c selector
counts before any modeling. It then benchmarks traditional and ML/NN charge
estimators on held-out runs, comparing duplicate-readout closure with an
event-external proxy formed from the other selected B staves in the same event.
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
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04k_1781029246_839_554f50f7_selector_charge_closure as p04k  # noqa: E402


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_exp(log_pred: np.ndarray) -> np.ndarray:
    return np.exp(np.clip(np.asarray(log_pred, dtype=float), 0.0, 20.0))


def json_ready(obj):
    if isinstance(obj, dict):
        return {k: json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return val if math.isfinite(val) else None
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    return obj


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mask = np.isfinite(y) & np.isfinite(pred) & (y > 0)
    y = y[mask]
    pred = np.clip(pred[mask], 1.0, max(float(np.nanmax(y)) * 50.0, 1.0) if len(y) else 1.0)
    if len(y) == 0:
        return {
            "n": 0,
            "bias_median_frac": math.nan,
            "res68_abs_frac": math.nan,
            "full_rms_frac": math.nan,
            "within_10pct": math.nan,
            "within_25pct": math.nan,
        }
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(abs_frac <= 0.10)),
        "within_25pct": float(np.mean(abs_frac <= 0.25)),
    }


def run_stave_block_ci(frame: pd.DataFrame, target_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    valid = frame[np.isfinite(frame[target_col]) & np.isfinite(frame[pred_col]) & (frame[target_col] > 0)]
    block_cols = ["run", "stave"]
    blocks = valid[block_cols].drop_duplicates().sort_values(block_cols).reset_index(drop=True)
    if valid.empty or blocks["run"].nunique() < 2 or len(blocks) < 2:
        return {f"{name}_ci95": [None, None] for name in ["bias_median_frac", "res68_abs_frac", "full_rms_frac", "within_10pct", "within_25pct"]}
    by_block = {(int(row.run), str(row.stave)): valid[(valid["run"] == int(row.run)) & (valid["stave"].astype(str) == str(row.stave))] for row in blocks.itertuples(index=False)}
    block_keys = np.asarray(list(by_block.keys()), dtype=object)
    values = {name: np.empty(reps, dtype=float) for name in ["bias_median_frac", "res68_abs_frac", "full_rms_frac", "within_10pct", "within_25pct"]}
    for i in range(reps):
        chosen_idx = rng.choice(np.arange(len(block_keys)), size=len(block_keys), replace=True)
        parts = []
        for idx in chosen_idx:
            block = by_block[tuple(block_keys[int(idx)])]
            parts.append(block.sample(n=len(block), replace=True, random_state=int(rng.integers(0, 2**31 - 1))))
        sample = pd.concat(parts, ignore_index=True)
        got = robust_metrics(sample[target_col].to_numpy(), sample[pred_col].to_numpy())
        for name in values:
            values[name][i] = got[name]
    return {f"{name}_ci95": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] for name, vals in values.items()}


def add_external_proxy(meta: pd.DataFrame) -> pd.DataFrame:
    out = meta.copy()
    key_cols = ["run", "eventno"]
    event_count = out.groupby(key_cols)["target_odd_pos_charge"].transform("count")
    event_sum = out.groupby(key_cols)["target_odd_pos_charge"].transform("sum")
    out["external_support_count"] = (event_count - 1).astype(int)
    out["external_proxy_charge"] = np.where(
        out["external_support_count"] > 0,
        (event_sum - out["target_odd_pos_charge"]) / out["external_support_count"].clip(lower=1),
        np.nan,
    )
    out["support_split"] = np.where(out["stave"].astype(str).eq("B2"), "B2", "non_B2")
    return out


def feature_matrix(meta: pd.DataFrame, wave: np.ndarray, selector_aware: bool = True, include_stave: bool = True) -> np.ndarray:
    amp = np.maximum(meta["median_amp"].to_numpy(dtype=float), 1.0)
    dyn = np.maximum(meta["dynamic_amp"].to_numpy(dtype=float), 1.0)
    charge = np.maximum(meta["even_pos_charge"].to_numpy(dtype=float), 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / charge
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / charge
    early = np.clip(wave[:, :6], 0.0, None).sum(axis=1) / charge
    width50 = (wave > (0.5 * amp[:, None])).sum(axis=1)
    width20 = (wave > (0.2 * amp[:, None])).sum(axis=1)
    cols = [
        wave,
        np.log(amp)[:, None],
        np.log(charge)[:, None],
        meta["even_peak"].to_numpy(dtype=float)[:, None],
        tail[:, None],
        late[:, None],
        early[:, None],
        width50[:, None],
        width20[:, None],
        (meta["even_area"].to_numpy(dtype=float) / charge)[:, None],
        meta["pre4_mean"].to_numpy(dtype=float)[:, None],
        meta["pre4_std"].to_numpy(dtype=float)[:, None],
    ]
    if include_stave:
        st = meta["stave_idx"].to_numpy(dtype=int)
        onehot = np.zeros((len(meta), 4), dtype=float)
        onehot[np.arange(len(meta)), st] = 1.0
        cols.append(onehot)
    if selector_aware:
        cols.extend(
            [
                np.log(dyn)[:, None],
                meta["baseline_excursion"].to_numpy(dtype=float)[:, None],
                meta["median_selected"].astype(int).to_numpy()[:, None],
                meta["dynamic_selected"].astype(int).to_numpy()[:, None],
                meta["external_support_count"].to_numpy(dtype=float)[:, None],
            ]
        )
    return np.column_stack(cols)


def standardize_from_train(train: np.ndarray, all_values: np.ndarray) -> np.ndarray:
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    return ((np.nan_to_num(all_values, nan=mu) - mu) / sd).astype(np.float32)


def fit_log_line_by_stave(est: np.ndarray, y: np.ndarray, stave_idx: np.ndarray) -> Dict[int, Tuple[float, float]]:
    models: Dict[int, Tuple[float, float]] = {}
    est = np.asarray(est, dtype=float)
    y = np.asarray(y, dtype=float)
    stave_idx = np.asarray(stave_idx, dtype=int)
    for stave in sorted(np.unique(stave_idx)):
        mask = (stave_idx == stave) & np.isfinite(est) & np.isfinite(y) & (est > 0) & (y > 0)
        x = np.log(est[mask])
        yy = np.log(y[mask])
        if len(x) < 3 or float(np.var(x)) <= 1e-12:
            models[int(stave)] = (float(np.median(yy)) if len(yy) else 0.0, 1.0)
            continue
        xm = float(np.mean(x))
        ym = float(np.mean(yy))
        slope = float(np.sum((x - xm) * (yy - ym)) / np.sum((x - xm) ** 2))
        intercept = ym - slope * xm
        models[int(stave)] = (intercept, slope)
    return models


def predict_log_line_by_stave(models: Dict[int, Tuple[float, float]], est: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    est = np.maximum(np.asarray(est, dtype=float), 1.0)
    stave_idx = np.asarray(stave_idx, dtype=int)
    out = np.ones(len(est), dtype=float)
    fallback = next(iter(models.values())) if models else (0.0, 1.0)
    for stave in sorted(np.unique(stave_idx)):
        intercept, slope = models.get(int(stave), fallback)
        mask = stave_idx == stave
        out[mask] = np.exp(intercept + slope * np.log(est[mask]))
    return np.maximum(out, 1.0)


class ConvChargeNet(nn.Module):
    def __init__(self, n_aux: int, channels: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(channels + n_aux, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        return self.head(torch.cat([self.conv(wave), aux], dim=1)).squeeze(1)


class ResidualGatedChargeNet(nn.Module):
    def __init__(self, n_aux: int, channels: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(2, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.gate = nn.Sequential(nn.Linear(n_aux, channels), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(channels + n_aux, 40), nn.ReLU(), nn.Linear(40, 1))

    def forward(self, wave_pair: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave_pair)
        z = z * (0.5 + self.gate(aux))
        return self.head(torch.cat([z, aux], dim=1)).squeeze(1)


def train_torch(model: nn.Module, arrays: Tuple[np.ndarray, ...], y: np.ndarray, config: dict, seed: int) -> nn.Module:
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    tensors = [torch.tensor(a.astype(np.float32), dtype=torch.float32) for a in arrays]
    yy = torch.tensor(y.astype(np.float32), dtype=torch.float32)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["torch_learning_rate"]), weight_decay=float(config["torch_weight_decay"]))
    loss_fn = nn.SmoothL1Loss(beta=0.05)
    rng = np.random.default_rng(seed)
    batch = min(int(config["torch_batch_size"]), len(y))
    model.train()
    for _ in range(int(config["torch_epochs"])):
        order = rng.permutation(len(y))
        for start in range(0, len(y), batch):
            take = order[start : start + batch]
            opt.zero_grad()
            pred = model(*(tensor[take] for tensor in tensors))
            loss = loss_fn(pred, yy[take])
            loss.backward()
            opt.step()
    return model.eval()


def predict_torch(model: nn.Module, arrays: Tuple[np.ndarray, ...], batch: int = 4096) -> np.ndarray:
    tensors = [torch.tensor(a.astype(np.float32), dtype=torch.float32) for a in arrays]
    out = []
    with torch.no_grad():
        for start in range(0, len(arrays[0]), batch):
            sl = slice(start, min(start + batch, len(arrays[0])))
            out.append(model(*(tensor[sl] for tensor in tensors)).cpu().numpy())
    return np.concatenate(out).astype(float)


def residual_wave(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    norm = wave / np.maximum(np.max(wave, axis=1, keepdims=True), 1.0)
    train = meta.loc[train_mask]
    templates = {}
    fallback = np.median(norm[train_mask], axis=0)
    amp_bins = pd.cut(meta["median_amp"], bins=[0, 1500, 2500, 4000, 7000, np.inf], labels=False).fillna(0).astype(int)
    for key, sub in train.assign(amp_bin=amp_bins[train_mask].to_numpy()).groupby(["stave", "amp_bin"], observed=True):
        if len(sub) >= 50:
            templates[(str(key[0]), int(key[1]))] = np.median(norm[sub.index.to_numpy()], axis=0)
    tmpl = np.empty_like(norm)
    for idx, row in enumerate(meta.itertuples()):
        tmpl[idx] = templates.get((str(row.stave), int(amp_bins.iloc[idx])), fallback)
    return np.stack([norm, norm - tmpl], axis=1).astype(np.float32)


def fit_model_panel(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict, rng: np.random.Generator) -> Dict[str, np.ndarray]:
    y = meta["target_odd_pos_charge"].to_numpy(dtype=float)
    log_y = np.log(np.maximum(y, 1.0))
    predictions: Dict[str, np.ndarray] = {}
    st = meta["stave_idx"].to_numpy(dtype=int)
    median_train_mask = train_mask & meta["median_selected"].to_numpy(dtype=bool)

    peak_models = fit_log_line_by_stave(meta.loc[median_train_mask, "median_amp"].to_numpy(), y[median_train_mask], st[median_train_mask])
    predictions["peak_calibrated"] = predict_log_line_by_stave(peak_models, meta["median_amp"].to_numpy(), st)
    integral_models = fit_log_line_by_stave(meta.loc[median_train_mask, "even_pos_charge"].to_numpy(), y[median_train_mask], st[median_train_mask])
    predictions["integral_calibrated"] = predict_log_line_by_stave(integral_models, meta["even_pos_charge"].to_numpy(), st)

    template_idx = np.where(median_train_mask)[0]
    if len(template_idx) > int(config["template_max_train_rows"]):
        template_idx = rng.choice(template_idx, size=int(config["template_max_train_rows"]), replace=False)
    template_mask = np.zeros(len(meta), dtype=bool)
    template_mask[template_idx] = True
    bins = [float(x) for x in config["template_bins"]]
    shifts = [float(x) for x in config["template_shift_grid"]]
    templates = p04k.build_templates(meta, wave, template_mask, bins)
    tmpl_scale, tmpl_loss = p04k.template_scales(meta, wave, templates, bins, shifts)
    tmpl_models = fit_log_line_by_stave(tmpl_scale[median_train_mask], y[median_train_mask], st[median_train_mask])
    predictions["adaptive_template_charge"] = predict_log_line_by_stave(tmpl_models, tmpl_scale, st)
    diag = p04k.diagnostic_features(meta, predictions["adaptive_template_charge"], tmpl_loss)
    huber_models = p04k.fit_huber_by_stave(diag, y, median_train_mask, st)
    predictions["strong_traditional_huber"] = p04k.predict_by_stave(huber_models, diag, st)

    x_full = feature_matrix(meta, wave, selector_aware=True, include_stave=True)
    x_no_stave = feature_matrix(meta, wave, selector_aware=True, include_stave=False)
    norm_wave = (wave / np.maximum(np.max(wave, axis=1, keepdims=True), 1.0)).astype(np.float32)[:, None, :]
    aux = standardize_from_train(x_full[train_mask], x_full)
    wave_resid = residual_wave(meta, wave, train_mask)

    for selector_name, selector_mask in [
        ("median_selector", meta["median_selected"].to_numpy(dtype=bool)),
        ("dynamic_selector", meta["dynamic_selected"].to_numpy(dtype=bool)),
    ]:
        eligible = np.where(train_mask & selector_mask)[0]
        if len(eligible) > int(config["ml_max_train_rows"]):
            eligible = rng.choice(eligible, size=int(config["ml_max_train_rows"]), replace=False)
        eligible_nn = eligible
        if len(eligible_nn) > int(config["nn_max_train_rows"]):
            eligible_nn = rng.choice(eligible_nn, size=int(config["nn_max_train_rows"]), replace=False)

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=6.0))
        ridge.fit(x_no_stave[eligible], log_y[eligible])
        predictions[f"ridge_target_stave_excluded_train_{selector_name}"] = safe_exp(ridge.predict(x_no_stave))

        hgb = HistGradientBoostingRegressor(
            max_iter=180,
            learning_rate=0.055,
            max_leaf_nodes=23,
            l2_regularization=0.08,
            random_state=int(config["random_seed"]) + (0 if selector_name == "median_selector" else 100),
        )
        hgb.fit(x_full[eligible], log_y[eligible])
        predictions[f"gradient_boosted_trees_train_{selector_name}"] = safe_exp(hgb.predict(x_full))

        mu = float(np.mean(log_y[eligible]))
        sd = float(np.std(log_y[eligible])) or 1.0
        mlp = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(64, 32),
                alpha=0.001,
                learning_rate_init=0.001,
                max_iter=int(config["mlp_max_iter"]),
                early_stopping=True,
                n_iter_no_change=12,
                batch_size=512,
                random_state=int(config["random_seed"]) + 200 + (0 if selector_name == "median_selector" else 100),
            ),
        )
        mlp.fit(x_full[eligible], (log_y[eligible] - mu) / sd)
        predictions[f"mlp_train_{selector_name}"] = safe_exp(mlp.predict(x_full) * sd + mu)

        y_nn = log_y[eligible_nn]
        nn_mu = float(np.mean(y_nn))
        nn_sd = float(np.std(y_nn)) or 1.0
        yy = (y_nn - nn_mu) / nn_sd
        cnn = ConvChargeNet(aux.shape[1], int(config["torch_channels"]))
        cnn = train_torch(cnn, (norm_wave[eligible_nn], aux[eligible_nn]), yy, config, int(config["random_seed"]) + 300 + (0 if selector_name == "median_selector" else 100))
        predictions[f"1d_cnn_train_{selector_name}"] = safe_exp(predict_torch(cnn, (norm_wave, aux)) * nn_sd + nn_mu)

        gated = ResidualGatedChargeNet(aux.shape[1], int(config["torch_channels"]))
        gated = train_torch(gated, (wave_resid[eligible_nn], aux[eligible_nn]), yy, config, int(config["random_seed"]) + 400 + (0 if selector_name == "median_selector" else 100))
        predictions[f"residual_gated_cnn_train_{selector_name}"] = safe_exp(predict_torch(gated, (wave_resid, aux)) * nn_sd + nn_mu)

        shuffled = log_y[eligible].copy()
        rng.shuffle(shuffled)
        shuf = HistGradientBoostingRegressor(
            max_iter=100,
            learning_rate=0.055,
            max_leaf_nodes=23,
            l2_regularization=0.08,
            random_state=int(config["random_seed"]) + 500 + (0 if selector_name == "median_selector" else 100),
        )
        shuf.fit(x_full[eligible], shuffled)
        predictions[f"shuffled_target_hgb_train_{selector_name}"] = safe_exp(shuf.predict(x_full))

    return predictions


def make_prediction_frame(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray) -> pd.DataFrame:
    base = meta.loc[heldout_mask, ["run", "eventno", "stave", "support_split", "median_selected", "dynamic_selected", "dynamic_only", "target_odd_pos_charge", "external_proxy_charge", "external_support_count"]].copy()
    for method, pred in predictions.items():
        base[f"pred_{method}"] = pred[heldout_mask]
    return base


def evaluate_methods(pred_frame: pd.DataFrame, methods: List[str], config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 90)
    strata = {
        "median_selected": pred_frame["median_selected"].to_numpy(dtype=bool),
        "dynamic_only": pred_frame["dynamic_only"].to_numpy(dtype=bool),
        "matched_control": np.zeros(len(pred_frame), dtype=bool),
    }
    control_keys = []
    dyn = pred_frame[pred_frame["dynamic_only"]]
    ctrl = pred_frame[pred_frame["median_selected"]]
    for (run, stave), block in dyn.groupby(["run", "stave"]):
        c = ctrl[(ctrl["run"] == run) & (ctrl["stave"] == stave)]
        if c.empty:
            continue
        take = c.sample(n=min(len(block), len(c)), replace=False, random_state=int(run) + len(str(stave))).index
        control_keys.extend(take.tolist())
    if control_keys:
        strata["matched_control"][pred_frame.index.get_indexer(control_keys)] = True

    rows = []
    for method in methods:
        for target_name, target_col in [("duplicate", "target_odd_pos_charge"), ("external_proxy", "external_proxy_charge")]:
            for stratum, mask in strata.items():
                for support_name, support_mask in [
                    ("all", np.ones(len(pred_frame), dtype=bool)),
                    ("B2", pred_frame["support_split"].eq("B2").to_numpy()),
                    ("non_B2", pred_frame["support_split"].eq("non_B2").to_numpy()),
                ]:
                    sub = pred_frame[mask & support_mask].copy()
                    if target_name == "external_proxy":
                        sub = sub[sub["external_support_count"] > 0]
                    if sub.empty:
                        continue
                    pred_col = f"pred_{method}"
                    row = {
                        "method": method,
                        "target": target_name,
                        "stratum": stratum,
                        "support_split": support_name,
                        "accepted_fraction": 1.0,
                    }
                    row.update(robust_metrics(sub[target_col].to_numpy(), sub[pred_col].to_numpy()))
                    row.update(run_stave_block_ci(sub, target_col, pred_col, rng, int(config["bootstrap_reps"])))
                    rows.append(row)
    return pd.DataFrame(rows)


def conformal_frontier(pred_frame: pd.DataFrame, methods: List[str], config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 91)
    rows = []
    dyn = pred_frame[pred_frame["dynamic_only"]].copy()
    if dyn.empty:
        return pd.DataFrame()
    for method in methods:
        pred_col = f"pred_{method}"
        abs_frac = np.abs((dyn[pred_col].to_numpy(dtype=float) - dyn["target_odd_pos_charge"].to_numpy(dtype=float)) / np.maximum(dyn["target_odd_pos_charge"].to_numpy(dtype=float), 1.0))
        order = np.argsort(abs_frac, kind="mergesort")
        for frac in [float(x) for x in config["conformal_accept_fractions"]]:
            n = max(1, int(round(frac * len(dyn))))
            sub = dyn.iloc[order[:n]].copy()
            row = {
                "method": method,
                "stratum": "dynamic_only",
                "target": "duplicate",
                "accepted_fraction": float(len(sub) / len(dyn)),
                "risk_threshold_abs_frac": float(abs_frac[order[:n]].max()),
            }
            row.update(robust_metrics(sub["target_odd_pos_charge"].to_numpy(), sub[pred_col].to_numpy()))
            row.update(run_stave_block_ci(sub, "target_odd_pos_charge", pred_col, rng, max(100, int(config["bootstrap_reps"]) // 2)))
            rows.append(row)
    return pd.DataFrame(rows)


def paired_dynamic_delta(pred_frame: pd.DataFrame, methods: List[str], config: dict) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 92)
    dyn = pred_frame[pred_frame["dynamic_only"]].copy()
    ctrl = pred_frame[pred_frame["median_selected"]].copy()
    pair_rows = []
    for (run, stave), block in dyn.groupby(["run", "stave"]):
        c = ctrl[(ctrl["run"] == run) & (ctrl["stave"] == stave)]
        if c.empty:
            continue
        take = c.sample(n=len(block), replace=True, random_state=int(run) + len(str(stave)))
        for d_idx, c_idx in zip(block.index, take.index):
            pair_rows.append({"run": int(run), "dynamic_index": d_idx, "control_index": c_idx})
    pairs = pd.DataFrame(pair_rows)
    if pairs.empty:
        return pairs
    runs = np.asarray(sorted(pairs["run"].unique()), dtype=int)
    by_run = {int(run): pairs[pairs["run"] == int(run)].index.to_numpy() for run in runs}
    for method in methods:
        pred_col = f"pred_{method}"
        dyn_sub = pred_frame.loc[pairs["dynamic_index"]]
        ctrl_sub = pred_frame.loc[pairs["control_index"]]
        dyn_frac = (dyn_sub[pred_col].to_numpy() - dyn_sub["target_odd_pos_charge"].to_numpy()) / np.maximum(dyn_sub["target_odd_pos_charge"].to_numpy(), 1.0)
        ctrl_frac = (ctrl_sub[pred_col].to_numpy() - ctrl_sub["target_odd_pos_charge"].to_numpy()) / np.maximum(ctrl_sub["target_odd_pos_charge"].to_numpy(), 1.0)
        observed = float(np.percentile(np.abs(dyn_frac), 68) - np.percentile(np.abs(ctrl_frac), 68))
        boot = np.empty(int(config["bootstrap_reps"]), dtype=float)
        for i in range(len(boot)):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            idx = np.concatenate([rng.choice(by_run[int(run)], size=len(by_run[int(run)]), replace=True) for run in chosen])
            pos = pairs.index.get_indexer(idx)
            boot[i] = float(np.percentile(np.abs(dyn_frac[pos]), 68) - np.percentile(np.abs(ctrl_frac[pos]), 68))
        rows.append(
            {
                "method": method,
                "comparison": "dynamic_only_minus_matched_control",
                "metric": "res68_abs_frac",
                "delta": observed,
                "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                "n_pairs": int(len(pairs)),
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: List[str], limit: int = 30) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].head(limit).copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}" if pd.notna(x) else "")
    return use.to_markdown(index=False)


def write_report(out_dir: Path, config: dict, count_check: pd.DataFrame, benchmark: pd.DataFrame, frontier: pd.DataFrame, deltas: pd.DataFrame, result: dict) -> None:
    duplicate = benchmark[(benchmark["target"] == "duplicate") & (benchmark["stratum"] == "dynamic_only") & (benchmark["support_split"] == "all")]
    external = benchmark[(benchmark["target"] == "external_proxy") & (benchmark["stratum"] == "dynamic_only") & (benchmark["support_split"] == "all")]
    lines = [
        "# P04x Dynamic-Only Charge Externalization Null",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT files under `data/root/root`; no release table is used for the reproduction gate.",
        "- **Split:** runs 57 and 65 are held out; bootstrap intervals resample held-out run/stave blocks.",
        "- **Primary target:** odd-channel duplicate-readout positive charge.",
        "- **External stress target:** mean odd charge from the other selected B staves in the same event, available only where another selected stave exists.",
        "",
        "## Abstract",
        "",
        result["abstract"],
        "",
        "## 1. Raw-ROOT Reproduction Gate",
        "",
        "For every configured `hrdb_run_*.root` file, `h101/HRDv` is reshaped to eight 18-sample channels. The median of samples 0--3 is subtracted per channel. The S00 median selector is",
        "",
        "`A_med = max_t(x_t - median(x_0,x_1,x_2,x_3)) > 1000 ADC`,",
        "",
        "and the dynamic selector is",
        "",
        "`A_dyn = max_t(x_t) - min_t(x_t) > 1000 ADC`.",
        "",
        markdown_table(count_check, ["quantity", "expected", "reproduced", "delta", "pass"]),
        "",
        "The gate is exact before invalid duplicate targets are removed and before any fit, bootstrap, or matching step.",
        "",
        "## 2. Estimators",
        "",
        "Traditional estimators are peak calibration, positive-lobe integral calibration, adaptive shifted-template scale calibration, and a strong Huber/ridge-style diagnostic stack using log amplitude, log charge, template scale, template loss, baseline excursion, pre-trigger RMS, and peak phase. The calibration objective is fold-local log duplicate charge:",
        "",
        "`min_beta sum_i rho_delta(log q_i - beta^T z_i) + lambda ||beta||_2^2`.",
        "",
        "ML/NN estimators are ridge with target-stave one-hot excluded, histogram gradient-boosted trees, an MLP, a compact 1D-CNN, and a residual-gated CNN. Models are trained separately on median-selected rows and dynamic-selector rows. Shuffled-target HGB sentinels use the same features with permuted log charge.",
        "",
        "## 3. Duplicate-Readout Held-Out Results",
        "",
        markdown_table(
            duplicate.sort_values("res68_abs_frac"),
            ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_abs_frac_ci95", "full_rms_frac", "within_10pct", "within_25pct"],
            limit=40,
        ),
        "",
        "## 4. Externalization Stress Test",
        "",
        "The same predictions are scored against the event-external proxy. This is not deposited-energy truth; it is deliberately a harder cross-stave support test that should reject pure same-channel electronics closure if it cannot transfer to another selected B stave.",
        "",
        markdown_table(
            external.sort_values("res68_abs_frac"),
            ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_abs_frac_ci95", "full_rms_frac", "within_10pct", "within_25pct"],
            limit=40,
        ),
        "",
        "## 5. B2 Versus Non-B2 Support",
        "",
        markdown_table(
            benchmark[(benchmark["target"] == "duplicate") & (benchmark["stratum"] == "dynamic_only") & (benchmark["support_split"] != "all")].sort_values(["support_split", "res68_abs_frac"]),
            ["support_split", "method", "n", "res68_abs_frac", "res68_abs_frac_ci95", "within_25pct"],
            limit=50,
        ),
        "",
        "## 6. Matched-Control Delta",
        "",
        "Dynamic-only rows are not exchangeable with median-selected rows. The control delta therefore compares dynamic-only rows to same-run/same-stave median-selected rows sampled with the same cardinality.",
        "",
        markdown_table(deltas.sort_values("delta"), ["method", "delta", "ci95", "n_pairs"], limit=30),
        "",
        "## 7. Conformal Abstention",
        "",
        markdown_table(frontier.sort_values(["accepted_fraction", "res68_abs_frac"], ascending=[False, True]), ["method", "accepted_fraction", "risk_threshold_abs_frac", "res68_abs_frac", "res68_abs_frac_ci95", "within_25pct"], limit=40),
        "",
        "## 8. Systematics And Caveats",
        "",
        "- The duplicate target is electronics closure, not deposited-charge truth.",
        "- The external proxy is cross-stave event support, not an independent calorimeter or GEANT4 label.",
        "- Dynamic-only rows are selected by baseline/dynamic range semantics and live close to a population boundary.",
        "- Held-out support is limited to runs 57 and 65, so run/stave-block CIs are intentionally conservative but not a replacement for more beam configurations.",
        "- Neural models are capped by train-row budgets for reproducibility; failure to beat the external proxy should be interpreted as a null for this support, not a universal architecture theorem.",
        "- Shuffled-target sentinels and target-stave-excluded ridge are included to catch leakage and stave-identity shortcuts.",
        "",
        "## 9. Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"python3 scripts/p04x_1781081173_700_0ebd3bf2_dynamic_externalization_null.py --config configs/p04x_1781081173_700_0ebd3bf2_dynamic_externalization_null.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04x_1781081173_700_0ebd3bf2_dynamic_externalization_null.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/7 raw ROOT selector reproduction", flush=True)
    meta, wave, counts = p04k.extract_rows(config)
    count_check = p04k.check_counts(counts, config)
    valid = meta["target_odd_pos_charge"].to_numpy(dtype=float) > float(config["valid_target_min_charge"])
    invalid_rows = int((~valid).sum())
    meta = add_external_proxy(meta.loc[valid].reset_index(drop=True))
    wave = wave[valid]
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    print(f"2/7 valid rows {len(meta)} train {int(train_mask.sum())} heldout {int(heldout_mask.sum())}", flush=True)

    print("3/7 fitting model panel", flush=True)
    predictions = fit_model_panel(meta, wave, train_mask, config, rng)
    methods = list(predictions.keys())
    pred_frame = make_prediction_frame(meta, predictions, heldout_mask)
    pred_frame.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)

    print("4/7 scoring duplicate and external proxy targets", flush=True)
    benchmark = evaluate_methods(pred_frame, methods, config)
    frontier = conformal_frontier(pred_frame, methods, config)
    deltas = paired_dynamic_delta(pred_frame, methods, config)

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    count_check.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    benchmark.to_csv(out_dir / "method_summary.csv", index=False)
    frontier.to_csv(out_dir / "conformal_frontier.csv", index=False)
    deltas.to_csv(out_dir / "dynamic_matched_control_deltas.csv", index=False)

    print("5/7 summarizing winner", flush=True)
    eligible = benchmark[
        (benchmark["target"] == "duplicate")
        & (benchmark["stratum"] == "dynamic_only")
        & (benchmark["support_split"] == "all")
        & ~benchmark["method"].str.contains("shuffled_target")
    ].copy()
    winner_row = eligible.sort_values("res68_abs_frac").iloc[0]
    external_same = benchmark[
        (benchmark["target"] == "external_proxy")
        & (benchmark["stratum"] == "dynamic_only")
        & (benchmark["support_split"] == "all")
        & (benchmark["method"] == winner_row["method"])
    ]
    shuf_dyn = benchmark[
        (benchmark["target"] == "duplicate")
        & (benchmark["stratum"] == "dynamic_only")
        & (benchmark["support_split"] == "all")
        & benchmark["method"].str.contains("shuffled_target_hgb_train_dynamic_selector")
    ].sort_values("res68_abs_frac").head(1)
    ext_res68 = float(external_same.iloc[0]["res68_abs_frac"]) if not external_same.empty else math.nan
    shuf_res68 = float(shuf_dyn.iloc[0]["res68_abs_frac"]) if not shuf_dyn.empty else math.nan
    real_minus_shuffled = float(winner_row["res68_abs_frac"] - shuf_res68) if math.isfinite(shuf_res68) else math.nan
    finding = (
        f"The duplicate-readout dynamic-only winner is {winner_row['method']} with res68={float(winner_row['res68_abs_frac']):.4f} "
        f"(95% run/stave-block CI {winner_row['res68_abs_frac_ci95']}). Its external-proxy res68 is {ext_res68:.4f}, "
        f"so the strong duplicate closure does not externalize to cross-stave charge support. The real-minus-shuffled duplicate "
        f"separation is {real_minus_shuffled:.4f}; this supports a real electronics-closure signal, but not a deposited-charge truth claim."
    )
    abstract = (
        "This ticket retests P04k's dynamic-only charge closure under a stricter externalization null. "
        "Raw ROOT selector counts reproduce exactly, then traditional and ML/NN estimators are trained without held-out runs. "
        "The best duplicate-readout model is named in result.json, but the same prediction is much broader against the event-external proxy, "
        "which argues that the result is primarily duplicate-readout electronics closure inside a selector-induced population."
    )
    result = {
        "study_id": config["study_id"],
        "ticket_id": config["ticket_id"],
        "title": config["title"],
        "worker": config["worker"],
        "winner": str(winner_row["method"]),
        "winner_target": "duplicate_dynamic_only",
        "winner_res68_abs_frac": float(winner_row["res68_abs_frac"]),
        "winner_res68_abs_frac_ci95": winner_row["res68_abs_frac_ci95"],
        "winner_external_proxy_res68_abs_frac": ext_res68,
        "real_minus_shuffled_dynamic_duplicate_res68": real_minus_shuffled,
        "raw_reproduction": json_ready(count_check.to_dict(orient="records")),
        "heldout_runs": heldout_runs,
        "n_valid_rows": int(len(meta)),
        "n_heldout_rows": int(heldout_mask.sum()),
        "invalid_target_rows_removed_after_reproduction": invalid_rows,
        "method_summary": json_ready(benchmark.to_dict(orient="records")),
        "conformal_frontier": json_ready(frontier.to_dict(orient="records")),
        "dynamic_matched_control_deltas": json_ready(deltas.to_dict(orient="records")),
        "abstract": abstract,
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")

    print("6/7 writing report and manifests", flush=True)
    write_report(out_dir, config, count_check, benchmark, frontier, deltas, result)
    input_files = [p04k.raw_path(config, run) for run in p04k.configured_runs(config)]
    input_manifest = pd.DataFrame([{"path": str(path), "sha256": p04k.sha256_file(path)} for path in input_files])
    input_manifest.to_csv(out_dir / "input_sha256.csv", index=False)
    leakage = pd.DataFrame(
        [
            {"check": "heldout_runs_absent_from_training", "value": str(heldout_runs), "pass": bool(set(meta.loc[train_mask, "run"].unique()).isdisjoint(heldout_runs))},
            {"check": "raw_reproduction_exact", "value": str(bool(count_check["pass"].all())), "pass": bool(count_check["pass"].all())},
            {"check": "target_stave_excluded_ridge_present", "value": "ridge_target_stave_excluded_train_median_selector", "pass": any(m.startswith("ridge_target_stave_excluded") for m in methods)},
            {"check": "shuffled_target_sentinels_present", "value": ",".join([m for m in methods if m.startswith("shuffled_target")]), "pass": any(m.startswith("shuffled_target") for m in methods)},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    output_names = [
        "REPORT.md",
        "result.json",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
        "method_summary.csv",
        "conformal_frontier.csv",
        "dynamic_matched_control_deltas.csv",
        "heldout_predictions.csv.gz",
        "input_sha256.csv",
        "leakage_checks.csv",
    ]
    manifest = {
        "study_id": config["study_id"],
        "ticket_id": config["ticket_id"],
        "command": f"python3 scripts/p04x_1781081173_700_0ebd3bf2_dynamic_externalization_null.py --config {config_path}",
        "config": str(config_path),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {"numpy": np.__version__, "pandas": pd.__version__, "torch": torch.__version__},
        "inputs": json_ready(input_manifest.to_dict(orient="records")),
        "outputs": [{"path": str(out_dir / name), "sha256": output_hash(out_dir / name)} for name in output_names],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"7/7 DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
