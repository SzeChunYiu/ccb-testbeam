#!/usr/bin/env python3
"""P10l tail-handle phase-drift null benchmark.

Rebuilds the selected B-stave pulse table from raw ROOT, then evaluates S01
empirical templates, train-only handle residual tables, and a broad ML/NN
panel under run-family holdouts. The preregistered null is that tail-handle
gains disappear once amplitude, stave, q-template support, saturation proxy,
current family, and CFD phase support are held fixed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import yaml
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


def load_p10a():
    path = Path("scripts/p10a_conditional_template.py")
    spec = importlib.util.spec_from_file_location("p10a_conditional_template", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p10a = load_p10a()


def load_yaml(path: Path) -> dict:
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


def labels_from_edges(edges: np.ndarray) -> List[str]:
    return [f"a{int(edges[i])}_{int(edges[i + 1])}" for i in range(len(edges) - 1)]


def current_lookup(config: dict) -> Dict[int, str]:
    out = {}
    for name, runs in config["current_strata"].items():
        for run in runs:
            out[int(run)] = str(name)
    return out


def add_handle_strata(config: dict, table: pd.DataFrame, aligned: np.ndarray, norm: np.ndarray) -> pd.DataFrame:
    out = table.copy()
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    amp = out["amplitude_adc"].to_numpy(dtype=float)
    amp_bin = p10a.assign_amp_bins(amp, edges)
    amp_labels = np.asarray(labels_from_edges(edges), dtype=object)
    out["amp_bin"] = amp_bin
    out["amp_region"] = amp_labels[amp_bin]

    peak = np.nanmax(norm, axis=1)
    cfd20 = p10a.cfd_times(norm, np.maximum(peak, 1.0e-6), 0.20)
    cfd80 = p10a.cfd_times(norm, np.maximum(peak, 1.0e-6), 0.80)
    rise = cfd80 - cfd20
    phase = cfd20 - np.floor(cfd20)
    out["rise_width_samples"] = rise
    out["cfd_phase"] = phase
    out["rise_width_region"] = pd.cut(
        rise,
        bins=[-np.inf, 1.15, 1.75, np.inf],
        labels=["rise_narrow", "rise_mid", "rise_wide"],
    ).astype(str)
    out["cfd_phase_region"] = pd.cut(
        phase,
        bins=[-0.01, 0.33, 0.66, 1.01],
        labels=["phase_early", "phase_mid", "phase_late"],
    ).astype(str)

    rel = np.asarray(config["aligned_relative_grid"], dtype=float)
    yy = np.nan_to_num(aligned.astype(float), nan=0.0)
    tail_sum = yy[:, rel >= 2].sum(axis=1)
    late_sum = yy[:, rel >= 8].sum(axis=1)
    out["tail_sum"] = tail_sum
    out["tail_late_frac"] = late_sum / np.maximum(tail_sum, 1.0e-9)
    out["tail_shape_region"] = pd.cut(
        out["tail_late_frac"].to_numpy(dtype=float),
        bins=[-np.inf, 0.18, 0.34, np.inf],
        labels=["tail_compact", "tail_mid", "tail_long"],
    ).astype(str)

    out["saturation_region"] = pd.cut(
        amp,
        bins=[999.0, 6500.0, 9000.0, np.inf],
        labels=["unsaturated", "boundary", "saturated_proxy"],
    ).astype(str)
    currents = current_lookup(config)
    out["current_family"] = [currents.get(int(run), "other") for run in out["run"]]
    out["run_family"] = out["group"].astype(str)
    out["support_cell"] = (
        out["amp_region"].astype(str)
        + "|"
        + out["stave"].astype(str)
        + "|"
        + out["rise_width_region"].astype(str)
        + "|"
        + out["cfd_phase_region"].astype(str)
        + "|"
        + out["tail_shape_region"].astype(str)
        + "|"
        + out["saturation_region"].astype(str)
        + "|"
        + out["current_family"].astype(str)
        + "|"
        + out["run_family"].astype(str)
    )
    return out


def waveform_live10_tail(aligned: np.ndarray, config: dict) -> pd.DataFrame:
    rel = np.asarray(config["aligned_relative_grid"], dtype=float)
    period = float(config["sample_period_ns"])
    rows = []
    for y0 in aligned:
        y = np.nan_to_num(y0.astype(float), nan=0.0)
        peak_i = int(np.nanargmax(y))
        after = np.flatnonzero((np.arange(len(y)) >= peak_i) & (y >= 0.10))
        live10 = float(rel[after[-1]] * period) if len(after) else np.nan
        tail = float(y[rel >= 2].sum())
        late = float(y[rel >= 8].sum())
        rows.append({"live10_ns": live10, "tail_sum": tail, "tail_late_frac": late / max(tail, 1.0e-9)})
    return pd.DataFrame(rows)


def select_capped_indices(table: pd.DataFrame, mask: np.ndarray, group_cols: List[str], cap: int, max_total: int, rng: np.random.Generator) -> np.ndarray:
    parts = []
    pool = table.loc[mask]
    for _, sub in pool.groupby(group_cols, observed=True):
        idx = sub.index.to_numpy()
        if len(idx) > cap:
            idx = rng.choice(idx, size=cap, replace=False)
        parts.append(idx)
    if not parts:
        return np.asarray([], dtype=int)
    idx = np.sort(np.concatenate(parts))
    if len(idx) > max_total:
        idx = np.sort(rng.choice(idx, size=max_total, replace=False))
    return idx.astype(int)


def predict_empirical(table: pd.DataFrame, aligned: np.ndarray, pack: dict, rows: np.ndarray) -> np.ndarray:
    edges = pack["edges"]
    bins = p10a.assign_amp_bins(table.iloc[rows]["amplitude_adc"].to_numpy(dtype=float), edges)
    pred = []
    for i, row in enumerate(table.iloc[rows].itertuples()):
        pred.append(pack["templates"][(row.stave, int(bins[i]))])
    return np.vstack(pred).astype(np.float32)


def build_handle_residuals(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_idx: np.ndarray, s01_pred_train: np.ndarray) -> Tuple[dict, pd.DataFrame]:
    residual = aligned[train_idx].astype(np.float32) - s01_pred_train.astype(np.float32)
    work = table.iloc[train_idx].copy()
    work["_local"] = np.arange(len(work))
    full_keys = ["stave", "amp_region", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family"]
    loose_keys = ["stave", "amp_region", "rise_width_region", "tail_shape_region", "saturation_region"]
    min_n = int(config["handle_min_bin_pulses"])
    tables = {"full": {}, "loose": {}}
    occ_rows = []
    for name, keys in [("full", full_keys), ("loose", loose_keys)]:
        for key, sub in work.groupby(keys, observed=True):
            loc = sub["_local"].to_numpy(dtype=int)
            n = int(len(loc))
            if n >= min_n:
                tables[name][tuple(str(v) for v in (key if isinstance(key, tuple) else (key,)))] = np.nanmedian(residual[loc], axis=0).astype(np.float32)
            occ_rows.append({"table": name, "key": "|".join(str(v) for v in (key if isinstance(key, tuple) else (key,))), "n_train": n, "usable": bool(n >= min_n)})
    return {"tables": tables, "full_keys": full_keys, "loose_keys": loose_keys}, pd.DataFrame(occ_rows)


def predict_handles(table: pd.DataFrame, rows: np.ndarray, s01_pred: np.ndarray, handle_pack: dict) -> Tuple[np.ndarray, List[str]]:
    pred = s01_pred.astype(np.float32).copy()
    sources = []
    for out_i, row in enumerate(table.iloc[rows].itertuples()):
        full = tuple(str(getattr(row, col)) for col in handle_pack["full_keys"])
        loose = tuple(str(getattr(row, col)) for col in handle_pack["loose_keys"])
        if full in handle_pack["tables"]["full"]:
            pred[out_i] += handle_pack["tables"]["full"][full]
            sources.append("full_handle")
        elif loose in handle_pack["tables"]["loose"]:
            pred[out_i] += handle_pack["tables"]["loose"][loose]
            sources.append("loose_handle")
        else:
            sources.append("s01_fallback")
    return pred, sources


def mse_to_prediction(aligned: np.ndarray, pred: np.ndarray) -> np.ndarray:
    valid = np.isfinite(aligned) & np.isfinite(pred)
    diff2 = (np.nan_to_num(aligned, nan=0.0) - np.nan_to_num(pred, nan=0.0)) ** 2
    denom = valid.sum(axis=1)
    out = np.full(len(aligned), np.nan, dtype=float)
    ok = denom > 0
    out[ok] = diff2[ok].sum(axis=1) / denom[ok]
    return out


FEATURE_GROUPS = {
    "amplitude": ["log_amp", "log_amp2", "amp_region"],
    "stave": ["stave"],
    "shape": ["rise_width_samples", "cfd_phase", "tail_sum", "tail_late_frac", "rise_width_region", "cfd_phase_region", "tail_shape_region"],
    "saturation": ["saturation_region"],
    "current": ["current_family"],
    "run_family": ["run_family"],
}


def feature_parts(table: pd.DataFrame, groups: Iterable[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    numeric = pd.DataFrame(index=table.index)
    cats = pd.DataFrame(index=table.index)
    amp = table["amplitude_adc"].to_numpy(dtype=float)
    source = table.copy()
    source["log_amp"] = np.log(np.maximum(amp, 1.0))
    source["log_amp2"] = source["log_amp"] ** 2
    for group in groups:
        for col in FEATURE_GROUPS[group]:
            if col in {"log_amp", "log_amp2", "rise_width_samples", "cfd_phase", "tail_sum", "tail_late_frac"}:
                numeric[col] = source[col].astype(float)
            else:
                cats[col] = source[col].astype(str)
    return numeric, cats


def fit_transform_features(train: pd.DataFrame, eval_: pd.DataFrame, groups: Iterable[str]):
    train_num, train_cat = feature_parts(train, groups)
    eval_num, eval_cat = feature_parts(eval_, groups)
    blocks_train, blocks_eval = [], []
    if train_num.shape[1]:
        scaler = StandardScaler()
        blocks_train.append(scaler.fit_transform(train_num.to_numpy(dtype=float)))
        blocks_eval.append(scaler.transform(eval_num.to_numpy(dtype=float)))
    if train_cat.shape[1]:
        enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
        blocks_train.append(enc.fit_transform(train_cat))
        blocks_eval.append(enc.transform(eval_cat))
    return np.column_stack(blocks_train).astype(float), np.column_stack(blocks_eval).astype(float)


def filled_targets(aligned: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    y = aligned[train_idx].astype(float)
    med = np.nanmedian(y, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    return np.where(np.isfinite(y), y, med[None, :]).astype(np.float32)


def filled_targets_all(aligned: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    med = np.nanmedian(aligned[train_idx].astype(float), axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    return np.where(np.isfinite(aligned), aligned, med[None, :]).astype(np.float32)


def cap_indices(idx: np.ndarray, cap: int, rng: np.random.Generator) -> np.ndarray:
    idx = np.asarray(idx, dtype=int)
    if len(idx) <= int(cap):
        return idx
    return np.sort(rng.choice(idx, size=int(cap), replace=False))


class TabularWaveformMLP(nn.Module):
    def __init__(self, n_in: int, n_out: int, hidden: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, n_out),
        )

    def forward(self, x):
        return self.net(x)


class WaveformCNN(nn.Module):
    def __init__(self, n_tab: int, n_out: int, channels: int, hidden: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(
            nn.Linear(channels + n_tab, hidden),
            nn.ReLU(),
            nn.Linear(hidden, n_out),
        )

    def forward(self, wave, tab):
        z = self.conv(wave).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1))


class PhaseGatedCNN(nn.Module):
    def __init__(self, n_tab: int, n_out: int, channels: int, hidden: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.gate = nn.Sequential(nn.Linear(n_tab, channels), nn.Sigmoid())
        self.head = nn.Sequential(
            nn.Linear(channels + n_tab, hidden),
            nn.ReLU(),
            nn.Linear(hidden, n_out),
        )

    def forward(self, wave, tab):
        z = self.conv(wave).squeeze(-1)
        z = z * self.gate(tab)
        return self.head(torch.cat([z, tab], dim=1))


def fit_torch_tabular(config: dict, X_train: np.ndarray, y_train: np.ndarray, X_eval: np.ndarray, rng: np.random.Generator, name: str) -> Tuple[np.ndarray, dict]:
    if torch is None:
        raise RuntimeError("torch is unavailable")
    torch_cfg = config["torch"]
    local = cap_indices(np.arange(len(X_train)), int(torch_cfg["max_train_rows"]), rng)
    scaler = StandardScaler()
    x_fit = scaler.fit_transform(X_train[local]).astype(np.float32)
    y_fit = y_train[local].astype(np.float32)
    ds = TensorDataset(torch.from_numpy(x_fit), torch.from_numpy(y_fit))
    loader = DataLoader(ds, batch_size=int(torch_cfg["batch_size"]), shuffle=True)
    torch.manual_seed(int(config["random_seed"]) + 110 + len(name))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TabularWaveformMLP(X_train.shape[1], y_train.shape[1], int(torch_cfg["hidden_dim"])).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(torch_cfg["learning_rate"]), weight_decay=float(torch_cfg["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(torch_cfg["mlp_epochs"])):
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    x_eval = scaler.transform(X_eval).astype(np.float32)
    pred = []
    with torch.no_grad():
        for start in range(0, len(x_eval), 8192):
            xb = torch.from_numpy(x_eval[start : start + 8192]).to(device)
            pred.append(model(xb).cpu().numpy().astype(np.float32))
    return np.vstack(pred), {"device": str(device), "train_rows": int(len(local)), "epochs": int(torch_cfg["mlp_epochs"])}


def fit_torch_cnn(
    config: dict,
    X_train: np.ndarray,
    wave_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    wave_eval: np.ndarray,
    rng: np.random.Generator,
    gated: bool,
) -> Tuple[np.ndarray, dict]:
    if torch is None:
        raise RuntimeError("torch is unavailable")
    torch_cfg = config["torch"]
    local = cap_indices(np.arange(len(X_train)), int(torch_cfg["max_train_rows"]), rng)
    scaler = StandardScaler()
    x_fit = scaler.fit_transform(X_train[local]).astype(np.float32)
    w_fit = np.nan_to_num(wave_train[local].astype(np.float32), nan=0.0)[:, None, :]
    y_fit = y_train[local].astype(np.float32)
    ds = TensorDataset(torch.from_numpy(w_fit), torch.from_numpy(x_fit), torch.from_numpy(y_fit))
    loader = DataLoader(ds, batch_size=int(torch_cfg["batch_size"]), shuffle=True)
    torch.manual_seed(int(config["random_seed"]) + (211 if gated else 171))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    klass = PhaseGatedCNN if gated else WaveformCNN
    model = klass(X_train.shape[1], y_train.shape[1], int(torch_cfg["cnn_channels"]), int(torch_cfg["hidden_dim"])).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(torch_cfg["learning_rate"]), weight_decay=float(torch_cfg["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(torch_cfg["cnn_epochs"])):
        for wb, xb, yb in loader:
            wb = wb.to(device)
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(wb, xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    x_eval = scaler.transform(X_eval).astype(np.float32)
    w_eval = np.nan_to_num(wave_eval.astype(np.float32), nan=0.0)[:, None, :]
    pred = []
    with torch.no_grad():
        for start in range(0, len(x_eval), 4096):
            wb = torch.from_numpy(w_eval[start : start + 4096]).to(device)
            xb = torch.from_numpy(x_eval[start : start + 4096]).to(device)
            pred.append(model(wb, xb).cpu().numpy().astype(np.float32))
    return np.vstack(pred), {
        "device": str(device),
        "train_rows": int(len(local)),
        "epochs": int(torch_cfg["cnn_epochs"]),
        "architecture": "phase_gated_cnn_new" if gated else "cnn_1d",
    }


def fit_ml_predictions(
    config: dict,
    table: pd.DataFrame,
    aligned: np.ndarray,
    norm: np.ndarray,
    train_idx: np.ndarray,
    eval_idx: np.ndarray,
    rng: np.random.Generator,
) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
    train = table.iloc[train_idx]
    eval_ = table.iloc[eval_idx]
    y = filled_targets(aligned, train_idx)
    rows = []
    out = {}
    model_specs = {
        "ridge": ("ridge", ["amplitude", "stave", "shape", "saturation", "current"]),
        "extra_trees": ("extra_trees", ["amplitude", "stave", "shape", "saturation", "current"]),
        "gradient_boosted_trees": ("gradient_boosted_trees", ["amplitude", "stave", "shape", "saturation", "current"]),
        "family_label_sentinel": ("extra_trees", ["current", "run_family"]),
        "shuffled_target_extra_trees": ("extra_trees_shuffled", ["amplitude", "stave", "shape", "saturation", "current"]),
        "phase_shuffled_gradient_boosted_trees": ("gradient_boosted_trees_phase_shuffled", ["amplitude", "stave", "shape", "saturation", "current"]),
        "knockout_no_amplitude": ("extra_trees", ["stave", "shape", "saturation", "current"]),
        "knockout_no_shape": ("extra_trees", ["amplitude", "stave", "saturation", "current"]),
        "knockout_no_stave": ("extra_trees", ["amplitude", "shape", "saturation", "current"]),
        "knockout_no_current": ("extra_trees", ["amplitude", "stave", "shape", "saturation"]),
    }
    for name, (kind, groups) in model_specs.items():
        print(f"    model {name}", flush=True)
        train_source = train.copy()
        if kind == "gradient_boosted_trees_phase_shuffled":
            train_source["cfd_phase"] = rng.permutation(train_source["cfd_phase"].to_numpy(dtype=float))
            train_source["cfd_phase_region"] = rng.permutation(train_source["cfd_phase_region"].to_numpy(dtype=str))
        X_train, X_eval = fit_transform_features(train_source, eval_, groups)
        target = y.copy()
        if kind == "extra_trees_shuffled":
            order = np.arange(len(target))
            rng.shuffle(order)
            target = target[order]
        if kind == "ridge":
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
        elif kind.startswith("gradient_boosted_trees"):
            params = dict(config["gradient_boosting"])
            params["random_state"] = int(params["random_state"]) + len(rows)
            model = MultiOutputRegressor(GradientBoostingRegressor(**params), n_jobs=2)
        else:
            params = dict(config["extra_trees"])
            params["random_state"] = int(config["random_seed"]) + len(rows) + 13
            model = ExtraTreesRegressor(**params)
        t0 = time.time()
        model.fit(X_train, target)
        out[name] = model.predict(X_eval).astype(np.float32)
        rows.append({"model": name, "kind": kind, "feature_groups": ",".join(groups), "train_rows": int(len(train_idx)), "eval_rows": int(len(eval_idx)), "fit_predict_sec": round(time.time() - t0, 2)})

    X_train, X_eval = fit_transform_features(train, eval_, ["amplitude", "stave", "shape", "saturation", "current"])
    y_all = filled_targets_all(aligned, train_idx)
    y_train = y_all[train_idx]
    for name, fitter in [
        ("mlp", "tabular"),
        ("cnn_1d", "cnn"),
        ("phase_gated_cnn_new", "gated_cnn"),
    ]:
        print(f"    model {name}", flush=True)
        t0 = time.time()
        try:
            if fitter == "tabular":
                pred, meta = fit_torch_tabular(config, X_train, y_train, X_eval, rng, name)
            else:
                pred, meta = fit_torch_cnn(config, X_train, norm[train_idx], y_train, X_eval, norm[eval_idx], rng, gated=(fitter == "gated_cnn"))
            out[name] = pred.astype(np.float32)
            status = "trained"
        except Exception as exc:
            out[name] = np.tile(np.nanmedian(y_train, axis=0), (len(eval_idx), 1)).astype(np.float32)
            meta = {"error": str(exc)}
            status = "fallback_median_due_to_error"
        rows.append(
            {
                "model": name,
                "kind": fitter,
                "feature_groups": "amplitude,stave,shape,saturation,current,waveform" if fitter != "tabular" else "amplitude,stave,shape,saturation,current",
                "train_rows": int(len(train_idx)),
                "eval_rows": int(len(eval_idx)),
                "fit_predict_sec": round(time.time() - t0, 2),
                "status": status,
                "meta": json.dumps(meta, sort_keys=True),
            }
        )
    return out, pd.DataFrame(rows)


def shifted(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - float(shift), x, template, left=np.nan, right=np.nan)


def timing_fit_residual_ns(obs: np.ndarray, pred: np.ndarray, config: dict) -> np.ndarray:
    grid = np.asarray(config["timing_shift_grid_samples"], dtype=float)
    period = float(config["sample_period_ns"])
    out = np.full(len(obs), np.nan, dtype=float)
    shifted_cache = {}
    for i in range(len(obs)):
        key = i
        shifted_pred = shifted_cache.get(key)
        if shifted_pred is None:
            shifted_pred = np.vstack([shifted(pred[i], s) for s in grid])
            shifted_cache[key] = shifted_pred
        valid = np.isfinite(shifted_pred) & np.isfinite(obs[i][None, :])
        denom = valid.sum(axis=1)
        ok = denom > 0
        if ok.any():
            diff2 = (np.nan_to_num(shifted_pred, nan=0.0) - np.nan_to_num(obs[i][None, :], nan=0.0)) ** 2
            mse = np.full(len(grid), np.inf, dtype=float)
            mse[ok] = diff2[ok].sum(axis=1) / denom[ok]
            out[i] = float(grid[int(np.argmin(mse))] * period)
    return out


def sigma68(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def summarize_by_run(table: pd.DataFrame, eval_idx: np.ndarray, metrics: Dict[str, Dict[str, np.ndarray]]) -> pd.DataFrame:
    rows = []
    runs = table.iloc[eval_idx]["run"].to_numpy(dtype=int)
    for run in sorted(np.unique(runs)):
        mask = runs == int(run)
        row = {"run": int(run), "n_eval": int(mask.sum())}
        for method, vals in metrics.items():
            row[f"{method}_q_mse"] = float(np.nanmean(vals["q_mse"][mask]))
            row[f"{method}_live10_abs_ns"] = float(np.nanmean(np.abs(vals["live10_resid_ns"][mask])))
            row[f"{method}_tail_abs"] = float(np.nanmean(np.abs(vals["tail_resid"][mask])))
            row[f"{method}_tail_mse"] = float(np.nanmean(vals["tail_resid"][mask] ** 2))
            row[f"{method}_timing_sigma68_ns"] = sigma68(vals["timing_resid_ns"][mask])
            row[f"{method}_timing_rms_ns"] = float(np.sqrt(np.nanmean(vals["timing_resid_ns"][mask] ** 2)))
            if "fallback" in vals:
                row[f"{method}_fallback_rate"] = float(np.mean(np.asarray(vals["fallback"], dtype=bool)[mask]))
                row[f"{method}_accepted_support_fraction"] = 1.0 - row[f"{method}_fallback_rate"]
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_summary(run_df: pd.DataFrame, fold: str, rng: np.random.Generator, reps: int) -> dict:
    cols = [c for c in run_df.columns if c not in {"run", "n_eval"}]
    matrix = run_df[cols].to_numpy(dtype=float)
    boots = []
    for _ in range(reps):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    out = {"fold": fold, "runs": [int(v) for v in run_df["run"]], "n_eval": int(run_df["n_eval"].sum())}
    means = matrix.mean(axis=0)
    for i, col in enumerate(cols):
        out[col] = float(means[i])
        out[f"{col}_ci"] = np.nanquantile(boots[:, i], [0.025, 0.975]).tolist()
    for metric in ["q_mse", "live10_abs_ns", "tail_abs", "tail_mse", "timing_sigma68_ns", "timing_rms_ns"]:
        for ml in ["ridge", "extra_trees", "gradient_boosted_trees", "mlp", "cnn_1d", "phase_gated_cnn_new"]:
            a = f"{ml}_{metric}"
            b = f"handle_residual_{metric}"
            if a in run_df and b in run_df:
                delta = run_df[a].to_numpy(dtype=float) - run_df[b].to_numpy(dtype=float)
                db = [delta[rng.integers(0, len(delta), len(delta))].mean() for _ in range(reps)]
                out[f"delta_{ml}_minus_handle_{metric}"] = float(np.nanmean(delta))
                out[f"delta_{ml}_minus_handle_{metric}_ci"] = np.nanquantile(db, [0.025, 0.975]).tolist()
        a = f"handle_residual_{metric}"
        b = f"s01_empirical_{metric}"
        if a in run_df and b in run_df:
            delta = run_df[a].to_numpy(dtype=float) - run_df[b].to_numpy(dtype=float)
            db = [delta[rng.integers(0, len(delta), len(delta))].mean() for _ in range(reps)]
            out[f"delta_handle_minus_s01_{metric}"] = float(np.nanmean(delta))
            out[f"delta_handle_minus_s01_{metric}_ci"] = np.nanquantile(db, [0.025, 0.975]).tolist()
    return out


def support_map(table: pd.DataFrame, eval_idx: np.ndarray, metrics: Dict[str, Dict[str, np.ndarray]], fold: str, min_n: int) -> pd.DataFrame:
    local = table.iloc[eval_idx].copy()
    for method, vals in metrics.items():
        local[f"{method}_q_mse"] = vals["q_mse"]
        local[f"{method}_timing_abs_ns"] = np.abs(vals["timing_resid_ns"])
    rows = []
    keys = ["amp_region", "stave", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family", "run_family"]
    for key, sub in local.groupby(keys, observed=True):
        if len(sub) < min_n:
            continue
        row = {"fold": fold, "n_eval": int(len(sub))}
        row.update({col: str(value) for col, value in zip(keys, key)})
        for method in [
            "s01_empirical",
            "handle_residual",
            "ridge",
            "extra_trees",
            "gradient_boosted_trees",
            "mlp",
            "cnn_1d",
            "phase_gated_cnn_new",
            "shuffled_target_extra_trees",
            "phase_shuffled_gradient_boosted_trees",
            "family_label_sentinel",
        ]:
            if method not in metrics:
                continue
            row[f"{method}_q_mse"] = float(np.nanmean(sub[f"{method}_q_mse"]))
            row[f"{method}_timing_abs_ns"] = float(np.nanmean(sub[f"{method}_timing_abs_ns"]))
        row["delta_handle_minus_s01_q_mse"] = row["handle_residual_q_mse"] - row["s01_empirical_q_mse"]
        row["delta_extra_trees_minus_handle_q_mse"] = row.get("extra_trees_q_mse", np.nan) - row["handle_residual_q_mse"]
        row["delta_extra_trees_minus_handle_timing_abs_ns"] = row.get("extra_trees_timing_abs_ns", np.nan) - row["handle_residual_timing_abs_ns"]
        row["delta_phase_gated_minus_handle_q_mse"] = row.get("phase_gated_cnn_new_q_mse", np.nan) - row["handle_residual_q_mse"]
        row["support_call"] = (
            "handles_win" if row["delta_handle_minus_s01_q_mse"] < 0 else "s01_wins_or_ties"
        )
        rows.append(row)
    return pd.DataFrame(rows)


def region_summary(support: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dims = ["amp_region", "stave", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family", "run_family"]
    for dim in dims:
        for value, sub in support.groupby(dim, observed=True):
            rows.append(
                {
                    "dimension": dim,
                    "region": str(value),
                    "n_cells": int(len(sub)),
                    "n_eval": int(sub["n_eval"].sum()),
                    "mean_delta_handle_minus_s01_q_mse": float(np.average(sub["delta_handle_minus_s01_q_mse"], weights=sub["n_eval"])),
                    "mean_delta_extra_trees_minus_handle_q_mse": float(np.average(sub["delta_extra_trees_minus_handle_q_mse"], weights=sub["n_eval"])),
                    "mean_delta_extra_trees_minus_handle_timing_abs_ns": float(np.average(sub["delta_extra_trees_minus_handle_timing_abs_ns"], weights=sub["n_eval"])),
                    "handle_win_cell_fraction": float(np.mean(sub["delta_handle_minus_s01_q_mse"] < 0)),
                    "extra_trees_q_win_cell_fraction": float(np.mean(sub["delta_extra_trees_minus_handle_q_mse"] < 0)),
                }
            )
    return pd.DataFrame(rows)


def input_sha(config: dict, out_dir: Path) -> List[dict]:
    rows = []
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in p10a.configured_runs(config):
            path = p10a.raw_file(config, run)
            item = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            writer.writerow(item)
            rows.append(item)
    return rows


def leakage_rows(config: dict, table: pd.DataFrame, fold_cfg: dict, summary: dict) -> dict:
    train_mask = table["group"].to_numpy() == fold_cfg["train_group"]
    eval_mask = table["group"].to_numpy() == fold_cfg["eval_group"]
    key_cols = ["run", "eventno", "evt", "stave"]
    train_keys = set(map(tuple, table.loc[train_mask, key_cols].to_numpy()))
    eval_keys = set(map(tuple, table.loc[eval_mask, key_cols].to_numpy()))
    et_win_ci = summary.get("delta_extra_trees_minus_handle_q_mse_ci", [math.nan, math.nan])
    shuffled = summary.get("shuffled_target_extra_trees_q_mse", math.nan)
    phase_shuffled = summary.get("phase_shuffled_gradient_boosted_trees_q_mse", math.nan)
    real = summary.get("extra_trees_q_mse", math.nan)
    gbt = summary.get("gradient_boosted_trees_q_mse", math.nan)
    sentinel = summary.get("family_label_sentinel_q_mse", math.nan)
    handle = summary.get("handle_residual_q_mse", math.nan)
    sentinel_values = [v for v in [shuffled, phase_shuffled, sentinel] if np.isfinite(v) and np.isfinite(handle)]
    false_pass_rate = float(np.mean([v < handle for v in sentinel_values])) if sentinel_values else math.nan
    return {
        "fold": fold_cfg["name"],
        "train_eval_run_overlap": sorted(set(table.loc[train_mask, "run"].astype(int)) & set(table.loc[eval_mask, "run"].astype(int))),
        "train_eval_key_overlap": int(len(train_keys & eval_keys)),
        "uses_run_or_event_features": False,
        "extra_trees_beats_handle_q_ci": bool(np.isfinite(et_win_ci[1]) and et_win_ci[1] < 0),
        "shuffled_target_beats_real": bool(np.isfinite(shuffled) and np.isfinite(real) and shuffled < real),
        "phase_shuffled_beats_gbt": bool(np.isfinite(phase_shuffled) and np.isfinite(gbt) and phase_shuffled < gbt),
        "family_label_sentinel_beats_real": bool(np.isfinite(sentinel) and np.isfinite(real) and sentinel < real),
        "false_pass_rate_under_sentinels": false_pass_rate,
        "leakage_alarm": bool(
            (np.isfinite(shuffled) and np.isfinite(real) and shuffled < real)
            or (np.isfinite(phase_shuffled) and np.isfinite(gbt) and phase_shuffled < gbt)
            or (np.isfinite(sentinel) and np.isfinite(real) and sentinel < real)
        ),
    }


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, fold_df: pd.DataFrame, leakage: pd.DataFrame, regions: pd.DataFrame, result: dict) -> None:
    best = regions.sort_values("mean_delta_handle_minus_s01_q_mse").head(8)
    worst = regions.sort_values("mean_delta_handle_minus_s01_q_mse", ascending=False).head(8)
    method_rows = []
    for method in result["method_order"]:
        if f"{method}_q_mse" not in fold_df:
            continue
        q_values = fold_df[f"{method}_q_mse"].to_numpy(dtype=float)
        method_rows.append(
            {
                "method": method,
                "class": result["method_classes"].get(method, ""),
                "q_template_mse": float(np.nanmean(q_values)),
                "fold_q_ci95": "; ".join(
                    f"{row['fold']} [{row.get(f'{method}_q_mse_ci', [np.nan, np.nan])[0]:.5g}, {row.get(f'{method}_q_mse_ci', [np.nan, np.nan])[1]:.5g}]"
                    for _, row in fold_df.iterrows()
                ),
                "tail_mse": float(np.nanmean(fold_df[f"{method}_tail_mse"])) if f"{method}_tail_mse" in fold_df else math.nan,
                "tail_abs": float(np.nanmean(fold_df[f"{method}_tail_abs"])) if f"{method}_tail_abs" in fold_df else math.nan,
                "timing_sigma68_ns": float(np.nanmean(fold_df[f"{method}_timing_sigma68_ns"])) if f"{method}_timing_sigma68_ns" in fold_df else math.nan,
            }
        )
    method_table = pd.DataFrame(method_rows).sort_values("q_template_mse")
    delta_cols = [
        "fold",
        "n_eval",
        "handle_residual_q_mse",
        "handle_residual_q_mse_ci",
    ]
    for method in ["ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "phase_gated_cnn_new"]:
        delta_cols.extend([f"{method}_q_mse", f"delta_{method}_minus_handle_q_mse", f"delta_{method}_minus_handle_q_mse_ci"])
    delta_cols = [col for col in delta_cols if col in fold_df.columns]
    lines = [
        "# P10l: Tail-handle phase-drift null benchmark",
        "",
        f"- **Ticket ID:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        f"- **Git commit:** `{result['git_commit']}`",
        "- **Monte Carlo:** none",
        "",
        "## 0. Question",
        "",
        "Do the P10h/P10e explicit tail and CFD handles fail because CFD phase distributions drift between run families, or because learned conditional template models are intrinsically unstable after amplitude, stave, q-template support, saturation proxy, current family, and run-family support are matched?",
        "",
        "The pre-registered primary metric is held-out run-mean q-template MSE on CFD20-aligned normalized waveforms. Secondary metrics are tail MSE, live10 shift, template-fit timing sigma68/full RMS, accepted support fraction, and false-pass rate under shuffled-target, phase-shuffled, and family-label sentinels.",
        "",
        "## 1. Reproduction Gate",
        "",
        "The selected B-stave pulse table was rebuilt from raw `HRDv` waveforms before any modeling.",
        "",
        repro.to_markdown(index=False),
        "",
        "## 2. Methods and Estimands",
        "",
        "Split: run-family holdout. `holdout_sample_i` trains on run 64 and evaluates runs 44-57; `holdout_sample_ii` trains on runs 31-42 and evaluates runs 58-63 and 65. Every uncertainty interval in the main tables bootstraps held-out runs, not rows.",
        "",
        "A selected waveform is baseline-subtracted, divided by peak amplitude, and interpolated onto the CFD20-relative grid `g`. For pulse `i` and method `m`, the primary loss is",
        "",
        "`MSE_i(m) = |V_i|^{-1} sum_{j in V_i} (y_ij - yhat_ij(m))^2`,",
        "",
        "where `V_i` is the finite aligned-sample set. The run-level score is the within-run mean, and the fold score is the unweighted mean over held-out runs. Tail residuals use the aligned tail sum on samples with relative grid >=2; tail MSE is the run mean of the squared tail residual. The live10 endpoint is the last post-peak grid sample above 10% amplitude, converted with the 10 ns sample period. Template timing residuals scan shifts from -1.5 to +1.5 samples and report `sigma68 = (Q84 - Q16)/2` plus full RMS.",
        "",
        "Traditional comparator: frozen S01 empirical stave/amplitude-bin median templates plus train-only explicit-handle median residual tables. The handle table keys are amplitude region, stave, rise width, CFD phase region, tail-shape region, saturation proxy, and current family. Sparse full cells fall back to a looser handle table, then to S01.",
        "",
        "ML/NN panel: standardized ridge, ExtraTrees, shallow stochastic gradient-boosted trees, tabular MLP, 1D-CNN over the normalized waveform plus tabular handles, and the new `phase_gated_cnn_new`, which multiplies convolutional channels by a learned sigmoid gate from the phase/tail handle vector. All methods exclude run id, event id, and target leakage features.",
        "",
        "## 3. Head-to-Head Benchmark",
        "",
        f"`result.json` names **{result['winner']['method']}** as the winner by lowest held-out q-template MSE among non-control methods. Its mean q-template MSE is `{result['winner']['q_template_mse']:.6g}`.",
        "",
        method_table.to_markdown(index=False),
        "",
        "The same head-to-head q-template MSE ranking is plotted in `fig_head_to_head_q_mse.png`.",
        "",
        "Fold-level deltas relative to the traditional explicit-handle baseline:",
        "",
        fold_df[delta_cols].to_markdown(index=False),
        "",
        "## 4. Phase-Drift Null and Support Regions",
        "",
        "A phase-drift explanation predicts that removing CFD phase information from the learned model should erase most gains and that gains should concentrate in a few phase cells. The phase-shuffled gradient-boosted sentinel tests this directly: training phase values and phase-region labels are permuted inside the training fold while all other supports are preserved.",
        "",
        leakage.to_markdown(index=False),
        "",
        "Most handle-favorable region summaries by weighted q-template MSE delta:",
        "",
        best.to_markdown(index=False),
        "",
        "Least handle-favorable region summaries:",
        "",
        worst.to_markdown(index=False),
        "",
        "## 5. Falsification",
        "",
        "Pre-registration: ML is considered to beat the strong traditional baseline only if the ML-minus-handle q-template MSE bootstrap CI is wholly below zero in a run-held-out fold and sentinel false-pass controls do not beat their matched real models. The multiple-comparison family contains five primary learned challengers to the handle baseline: ridge, gradient-boosted trees, MLP, 1D-CNN, and phase-gated CNN; p-values or sign tests should therefore be interpreted with that five-way search in mind.",
        "",
        f"False-pass sentinel rates by fold are recorded in `leakage_checks.csv`; the maximum observed rate is `{result['max_false_pass_rate_under_sentinels']:.3g}`. A leakage alarm would have falsified any adoption claim.",
        "",
        "## 6. Systematics and Caveats",
        "",
        "- **Benchmark/selection:** all methods use identical held-out rows per fold, but row caps make this a support-balanced benchmark rather than a full-population production fit.",
        "- **Data leakage:** train and evaluation runs are disjoint; event numbers, run ids, and target residuals are not used as features. Sentinel models explicitly test shuffled targets, phase shuffling, and family labels.",
        "- **Metric misuse:** q-template MSE is a waveform-template metric, not a physics truth label. Timing sigma68 and RMS are template-fit diagnostics, not external time-of-flight truth.",
        "- **Post-hoc selection:** the model panel, primary metric, run bootstrap unit, and sentinel alarms follow the claimed ticket and are fixed in the config/script.",
        "- **Raw-data limitation:** the reduced ROOT bundle lacks external beam-current scalers and truth labels, so phase drift is inferred from waveform-handle support rather than a calibrated external phase monitor.",
        "",
        "## 7. Findings and Next Steps",
        "",
        result["conclusion"],
        "",
        f"Queued follow-up candidate: {result['followup_ticket']['title'] if result.get('followup_ticket') else 'none'}. Expected information gain: {result['followup_ticket']['expected_information_gain'].rstrip('.') if result.get('followup_ticket') else 'not applicable'}.",
        "",
        "Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `fold_run_metrics.csv`, `fold_summary.csv`, `support_map.csv`, `support_region_summary.csv`, `model_diagnostics.csv`, `handle_occupancy.csv`, `leakage_checks.csv`, and `fig_head_to_head_q_mse.png`.",
        "",
        "## 8. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p10l_1781068158_1584_4e8d411c_phase_drift_benchmark.py --config configs/p10l_1781068158_1584_4e8d411c_phase_drift_benchmark.yaml",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_plots(out_dir: Path, fold_df: pd.DataFrame, result: dict) -> None:
    methods = [m for m in result["method_order"] if f"{m}_q_mse" in fold_df]
    values = [float(np.nanmean(fold_df[f"{m}_q_mse"].to_numpy(dtype=float))) for m in methods]
    order = np.argsort(values)
    methods = [methods[i] for i in order]
    values = [values[i] for i in order]
    colors = []
    for method in methods:
        cls = result["method_classes"].get(method, "")
        if cls.startswith("traditional"):
            colors.append("#4c78a8")
        elif cls == "sentinel":
            colors.append("#9d9d9d")
        elif cls == "new_neural_architecture":
            colors.append("#e45756")
        else:
            colors.append("#59a14f")
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(np.arange(len(methods)), values, color=colors)
    ax.set_yticks(np.arange(len(methods)))
    ax.set_yticklabels(methods, fontsize=8)
    ax.set_xlabel("held-out run-mean q-template MSE")
    ax.set_title("P10l head-to-head template benchmark")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head_q_mse.png", dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10l_1781068158_1584_4e8d411c_phase_drift_benchmark.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/5 raw ROOT selected-pulse reproduction", flush=True)
    table0, aligned, norm = p10a.collect_selected(config)
    table = add_handle_strata(config, table0, aligned, norm)
    analysis_rows = int(table["group"].str.endswith("_analysis").sum())
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "analysis selected rows",
                "expected": int(config["expected_analysis_rows"]),
                "reproduced": analysis_rows,
                "delta": int(analysis_rows - int(config["expected_analysis_rows"])),
                "pass": bool(analysis_rows == int(config["expected_analysis_rows"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    print("2/5 run-family folds", flush=True)
    fold_runs, fold_summaries, support_parts, diag_parts, occ_parts, leakage_parts = [], [], [], [], [], []
    for fold_cfg in config["family_folds"]:
        print(f"  fold {fold_cfg['name']}", flush=True)
        train_mask = table["group"].to_numpy() == fold_cfg["train_group"]
        eval_mask = table["group"].to_numpy() == fold_cfg["eval_group"]
        train_idx = select_capped_indices(
            table,
            train_mask,
            ["run", "stave", "amp_region", "rise_width_region", "tail_shape_region", "saturation_region"],
            cap=80,
            max_total=int(config["max_train_rows_per_fold"]),
            rng=rng,
        )
        eval_idx = select_capped_indices(
            table,
            eval_mask,
            ["run", "stave", "amp_region", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region"],
            cap=int(config["max_eval_per_run_support"]),
            max_total=int(config["max_eval_rows_per_fold"]),
            rng=rng,
        )

        s01_pack, _ = p10a.build_empirical_templates(config, table, aligned, train_mask)
        s01_train = predict_empirical(table, aligned, s01_pack, train_idx)
        s01_eval = predict_empirical(table, aligned, s01_pack, eval_idx)
        handle_pack, occ = build_handle_residuals(config, table, aligned, train_idx, s01_train)
        handle_eval, handle_sources = predict_handles(table, eval_idx, s01_eval, handle_pack)
        occ["fold"] = fold_cfg["name"]
        occ_parts.append(occ)
        print(f"    train_rows={len(train_idx)} eval_rows={len(eval_idx)}", flush=True)
        ml_pred, diag = fit_ml_predictions(config, table, aligned, norm, train_idx, eval_idx, rng)
        diag["fold"] = fold_cfg["name"]
        diag_parts.append(diag)

        predictions = {"s01_empirical": s01_eval, "handle_residual": handle_eval}
        predictions.update(ml_pred)
        obs_stats = waveform_live10_tail(aligned[eval_idx], config)
        metrics = {}
        for method, pred in predictions.items():
            pred_stats = waveform_live10_tail(pred, config)
            metrics[method] = {
                "q_mse": mse_to_prediction(aligned[eval_idx], pred),
                "live10_resid_ns": pred_stats["live10_ns"].to_numpy(dtype=float) - obs_stats["live10_ns"].to_numpy(dtype=float),
                "tail_resid": pred_stats["tail_sum"].to_numpy(dtype=float) - obs_stats["tail_sum"].to_numpy(dtype=float),
                "timing_resid_ns": timing_fit_residual_ns(aligned[eval_idx], pred, config),
            }
        metrics["handle_residual"]["fallback"] = np.asarray([src == "s01_fallback" for src in handle_sources], dtype=bool)

        run_df = summarize_by_run(table, eval_idx, metrics)
        run_df["fold"] = fold_cfg["name"]
        fold_runs.append(run_df)
        summary = bootstrap_summary(run_df.drop(columns=["fold"]), fold_cfg["name"], rng, int(config["bootstrap_iterations"]))
        summary["train_group"] = fold_cfg["train_group"]
        summary["eval_group"] = fold_cfg["eval_group"]
        summary["train_rows_used"] = int(len(train_idx))
        fold_summaries.append(summary)
        support_parts.append(support_map(table, eval_idx, metrics, fold_cfg["name"], int(config["support_min_eval_pulses"])))
        leakage_parts.append(leakage_rows(config, table, fold_cfg, summary))

    print("3/5 aggregate metrics", flush=True)
    run_df = pd.concat(fold_runs, ignore_index=True)
    fold_df = pd.DataFrame(fold_summaries)
    support_df = pd.concat(support_parts, ignore_index=True)
    regions = region_summary(support_df)
    diag_df = pd.concat(diag_parts, ignore_index=True)
    occ_df = pd.concat(occ_parts, ignore_index=True)
    leakage = pd.DataFrame(leakage_parts)

    run_df.to_csv(out_dir / "fold_run_metrics.csv", index=False)
    fold_df.to_csv(out_dir / "fold_summary.csv", index=False)
    support_df.to_csv(out_dir / "support_map.csv", index=False)
    regions.to_csv(out_dir / "support_region_summary.csv", index=False)
    diag_df.to_csv(out_dir / "model_diagnostics.csv", index=False)
    occ_df.to_csv(out_dir / "handle_occupancy.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    inputs = input_sha(config, out_dir)

    print("4/5 result/report", flush=True)
    method_classes = {
        "s01_empirical": "traditional_base",
        "handle_residual": "traditional_strong",
        "ridge": "ml_linear",
        "extra_trees": "ml_tree_control",
        "gradient_boosted_trees": "ml_tree",
        "mlp": "neural_tabular",
        "cnn_1d": "neural_waveform",
        "phase_gated_cnn_new": "new_neural_architecture",
        "family_label_sentinel": "sentinel",
        "shuffled_target_extra_trees": "sentinel",
        "phase_shuffled_gradient_boosted_trees": "sentinel",
    }
    method_order = [
        "s01_empirical",
        "handle_residual",
        "ridge",
        "extra_trees",
        "gradient_boosted_trees",
        "mlp",
        "cnn_1d",
        "phase_gated_cnn_new",
        "family_label_sentinel",
        "shuffled_target_extra_trees",
        "phase_shuffled_gradient_boosted_trees",
    ]
    primary_methods = ["handle_residual", "ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "phase_gated_cnn_new"]
    winner_rows = []
    for method in primary_methods:
        col = f"{method}_q_mse"
        if col in fold_df:
            winner_rows.append({"method": method, "q_template_mse": float(np.nanmean(fold_df[col].to_numpy(dtype=float)))})
    winner = min(winner_rows, key=lambda row: row["q_template_mse"])
    promotable_folds = int((~leakage["leakage_alarm"]).sum())
    handles_help = bool((fold_df["delta_handle_minus_s01_q_mse_ci"].apply(lambda v: v[1]) < 0).any())
    ml_help = any(
        bool((fold_df[f"delta_{method}_minus_handle_q_mse_ci"].apply(lambda v: v[1]) < 0).any())
        for method in ["ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "phase_gated_cnn_new"]
        if f"delta_{method}_minus_handle_q_mse_ci" in fold_df
    )
    conclusion = (
        "Explicit handle residuals have limited promotable support: at least one fold improves over S01 by q-template CI, but support is region-specific."
        if handles_help
        else "Explicit handle residuals do not produce a fold-level q-template CI win over frozen S01; any gains are local support-map effects."
    )
    if ml_help:
        conclusion += f" The learned panel has at least one CI win over the traditional handle method; the benchmark winner is {winner['method']}, subject to the sentinel audit."
    else:
        conclusion += f" No required ML/NN method beats the traditional handle method by fold-level CI; the point-estimate winner is {winner['method']}."
    if bool(leakage["leakage_alarm"].any()):
        conclusion += " At least one sentinel alarm is active, so the result is a benchmark finding rather than an adoption recommendation."
    else:
        conclusion += " No sentinel alarm fired under the predeclared target-shuffle, phase-shuffle, and family-label controls."

    followup = {
        "title": "P10m freeze phase-gated tail template and test downstream timing/charge consumers",
        "expected_information_gain": "It would decide whether the P10l waveform-template winner improves independent pair-timing and charge-consumer outcomes after freezing the model, instead of only improving q-template reconstruction.",
    }

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction": {"passed": bool(repro["pass"].all()), "selected_b_stave_pulses": int(len(table)), "analysis_selected_rows": analysis_rows},
        "split": "run-family holdout with held-out run bootstrap CIs",
        "traditional": "S01 empirical amplitude-bin templates plus train-only explicit-handle residual medians",
        "ml": "ridge, ExtraTrees, shallow stochastic gradient-boosted trees, tabular MLP, 1D-CNN, and phase-gated CNN multi-output template predictors",
        "winner": winner,
        "method_order": method_order,
        "method_classes": method_classes,
        "metrics": ["q_template_mse", "tail_mse", "tail_abs_residual", "live10_abs_residual_ns", "timing_fit_sigma68_ns", "timing_fit_full_rms_ns", "accepted_support_fraction", "fallback_rate", "false_pass_rate_under_sentinels"],
        "folds": fold_summaries,
        "leakage": leakage_parts,
        "max_false_pass_rate_under_sentinels": float(np.nanmax(leakage["false_pass_rate_under_sentinels"].to_numpy(dtype=float))),
        "promotable_folds_without_sentinel_alarm": promotable_folds,
        "conclusion": conclusion,
        "followup_ticket": followup,
        "next_tickets": [followup],
        "git_commit": git_commit(),
        "input_sha256": "input_sha256.csv",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_plots(out_dir, fold_df, result)
    write_report(out_dir, config, repro, fold_df, leakage, regions, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"/home/billy/anaconda3/bin/python scripts/p10l_1781068158_1584_4e8d411c_phase_drift_benchmark.py --config {config_path}",
        "script": "scripts/p10l_1781068158_1584_4e8d411c_phase_drift_benchmark.py",
        "script_sha256": sha256_file(Path("scripts/p10l_1781068158_1584_4e8d411c_phase_drift_benchmark.py")),
        "support_script": "scripts/p10a_conditional_template.py",
        "support_script_sha256": sha256_file(Path("scripts/p10a_conditional_template.py")),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"5/5 done -> {out_dir} winner={winner['method']}", flush=True)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
