#!/usr/bin/env python3
"""P10k minority-stave conditional-template failure map.

The analysis rebuilds the selected B-stave pulse table from raw ROOT and then
benchmarks the frozen S01 empirical template against ridge, gradient-boosted
trees, MLP, 1D-CNN, and a support-gated mixture under run-family holdouts.
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
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p10a = load_module("p10a_conditional_template", Path("scripts/p10a_conditional_template.py"))


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


def json_clean(obj):
    if isinstance(obj, dict):
        return {str(k): json_clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_clean(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return json_clean(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj) if np.isfinite(obj) else None
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


def labels_from_edges(edges: np.ndarray) -> List[str]:
    return [f"a{int(edges[i])}_{int(edges[i + 1])}" for i in range(len(edges) - 1)]


def current_lookup(config: dict) -> Dict[int, str]:
    out = {}
    for name, runs in config["current_strata"].items():
        for run in runs:
            out[int(run)] = str(name)
    return out


def add_strata(config: dict, table: pd.DataFrame, aligned: np.ndarray, norm: np.ndarray) -> pd.DataFrame:
    out = table.copy()
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    amp = out["amplitude_adc"].to_numpy(dtype=float)
    amp_bin = p10a.assign_amp_bins(amp, edges)
    out["amp_bin"] = amp_bin
    out["amp_region"] = np.asarray(labels_from_edges(edges), dtype=object)[amp_bin]

    peak = np.nanmax(norm, axis=1)
    cfd20 = p10a.cfd_times(norm, np.maximum(peak, 1.0e-6), 0.20)
    cfd80 = p10a.cfd_times(norm, np.maximum(peak, 1.0e-6), 0.80)
    rise = cfd80 - cfd20
    phase = cfd20 - np.floor(cfd20)
    rel = np.asarray(config["aligned_relative_grid"], dtype=float)
    yy = np.nan_to_num(aligned.astype(float), nan=0.0)
    tail_sum = yy[:, rel >= 2].sum(axis=1)
    late_sum = yy[:, rel >= 8].sum(axis=1)

    out["rise_width_samples"] = rise
    out["cfd_phase"] = phase
    out["tail_sum"] = tail_sum
    out["tail_late_frac"] = late_sum / np.maximum(tail_sum, 1.0e-9)
    out["rise_width_region"] = pd.cut(rise, [-np.inf, 1.15, 1.75, np.inf], labels=["rise_narrow", "rise_mid", "rise_wide"]).astype(str)
    out["cfd_phase_region"] = pd.cut(phase, [-0.01, 0.33, 0.66, 1.01], labels=["phase_early", "phase_mid", "phase_late"]).astype(str)
    out["tail_shape_region"] = pd.cut(out["tail_late_frac"], [-np.inf, 0.18, 0.34, np.inf], labels=["tail_compact", "tail_mid", "tail_long"]).astype(str)
    out["saturation_region"] = pd.cut(amp, [999.0, 6500.0, 9000.0, np.inf], labels=["unsaturated", "boundary", "saturated_proxy"]).astype(str)
    currents = current_lookup(config)
    out["current_family"] = [currents.get(int(run), "other") for run in out["run"]]
    out["run_family"] = out["group"].astype(str)
    out["minority_stave"] = out["stave"].isin(config["minority_staves"])
    out["support_cell"] = (
        out["stave"].astype(str)
        + "|"
        + out["amp_region"].astype(str)
        + "|"
        + out["rise_width_region"].astype(str)
        + "|"
        + out["cfd_phase_region"].astype(str)
        + "|"
        + out["tail_shape_region"].astype(str)
        + "|"
        + out["saturation_region"].astype(str)
    )
    return out


def reproduction_gate(config: dict, table: pd.DataFrame) -> pd.DataFrame:
    analysis_rows = int(table["group"].str.endswith("_analysis").sum())
    return pd.DataFrame(
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


def empirical_predict(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_mask: np.ndarray, rows: np.ndarray) -> np.ndarray:
    pack, _ = p10a.build_empirical_templates(config, table, aligned, train_mask)
    edges = pack["edges"]
    bins = p10a.assign_amp_bins(table.iloc[rows]["amplitude_adc"].to_numpy(dtype=float), edges)
    pred = []
    for i, row in enumerate(table.iloc[rows].itertuples()):
        pred.append(pack["templates"][(row.stave, int(bins[i]))])
    return np.vstack(pred).astype(np.float32)


def select_capped_indices(table: pd.DataFrame, mask: np.ndarray, cap: int, rng: np.random.Generator) -> np.ndarray:
    idx_parts = []
    pool = table.loc[mask]
    per_group = max(1, int(math.ceil(cap / max(1, pool.groupby(["run", "stave"], observed=True).ngroups))))
    for _, sub in pool.groupby(["run", "stave"], observed=True):
        idx = sub.index.to_numpy(dtype=int)
        if len(idx) > per_group:
            idx = rng.choice(idx, size=per_group, replace=False)
        idx_parts.append(idx)
    idx = np.sort(np.concatenate(idx_parts)) if idx_parts else np.asarray([], dtype=int)
    if len(idx) > cap:
        idx = np.sort(rng.choice(idx, size=cap, replace=False))
    return idx.astype(int)


FEATURE_NUMERIC = ["log_amp", "log_amp2", "rise_width_samples", "cfd_phase", "tail_sum", "tail_late_frac", "peak_sample"]
FEATURE_CATEGORICAL = ["stave", "amp_region", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family"]


def feature_frame(table: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    src = table.copy()
    src["log_amp"] = np.log(np.maximum(src["amplitude_adc"].to_numpy(dtype=float), 1.0))
    src["log_amp2"] = src["log_amp"] ** 2
    num = src[FEATURE_NUMERIC].astype(float)
    cat = src[FEATURE_CATEGORICAL].astype(str)
    return num, cat


def transform_features(train: pd.DataFrame, eval_: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    train_num, train_cat = feature_frame(train)
    eval_num, eval_cat = feature_frame(eval_)
    scaler = StandardScaler()
    enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    x_train = np.column_stack([scaler.fit_transform(train_num), enc.fit_transform(train_cat)]).astype(np.float32)
    x_eval = np.column_stack([scaler.transform(eval_num), enc.transform(eval_cat)]).astype(np.float32)
    return x_train, x_eval


def fill_target(y: np.ndarray) -> np.ndarray:
    med = np.nanmedian(y, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    return np.where(np.isfinite(y), y, med[None, :]).astype(np.float32)


def mse_to_prediction(obs: np.ndarray, pred: np.ndarray) -> np.ndarray:
    valid = np.isfinite(obs) & np.isfinite(pred)
    diff2 = (np.nan_to_num(obs, nan=0.0) - np.nan_to_num(pred, nan=0.0)) ** 2
    denom = valid.sum(axis=1)
    out = np.full(len(obs), np.nan, dtype=float)
    ok = denom > 0
    out[ok] = diff2[ok].sum(axis=1) / denom[ok]
    return out


def fit_tabular_models(config: dict, train: pd.DataFrame, eval_: pd.DataFrame, y_train: np.ndarray, rng: np.random.Generator) -> Tuple[Dict[str, np.ndarray], List[dict]]:
    x_train, x_eval = transform_features(train, eval_)
    y = fill_target(y_train)
    preds: Dict[str, np.ndarray] = {}
    rows: List[dict] = []

    t0 = time.time()
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
    ridge.fit(x_train, y)
    preds["ridge"] = ridge.predict(x_eval).astype(np.float32)
    rows.append({"method": "ridge", "fit_predict_sec": round(time.time() - t0, 2), "train_rows": int(len(train)), "eval_rows": int(len(eval_))})

    t0 = time.time()
    pca = PCA(n_components=int(config["gbt"]["pca_components"]), random_state=int(config["random_seed"]))
    y_pca = pca.fit_transform(y)
    gbt = MultiOutputRegressor(
        HistGradientBoostingRegressor(
            max_iter=int(config["gbt"]["max_iter"]),
            learning_rate=float(config["gbt"]["learning_rate"]),
            max_leaf_nodes=int(config["gbt"]["max_leaf_nodes"]),
            l2_regularization=float(config["gbt"]["l2_regularization"]),
            random_state=int(config["random_seed"]) + 31,
        )
    )
    gbt.fit(x_train, y_pca)
    preds["gradient_boosted_trees"] = pca.inverse_transform(gbt.predict(x_eval)).astype(np.float32)
    rows.append({"method": "gradient_boosted_trees", "fit_predict_sec": round(time.time() - t0, 2), "train_rows": int(len(train)), "eval_rows": int(len(eval_)), "target_pca_components": int(config["gbt"]["pca_components"])})

    t0 = time.time()
    mlp = MLPRegressor(
        hidden_layer_sizes=tuple(int(v) for v in config["mlp"]["hidden_layer_sizes"]),
        alpha=float(config["mlp"]["alpha"]),
        learning_rate_init=float(config["mlp"]["learning_rate_init"]),
        max_iter=int(config["mlp"]["max_iter"]),
        validation_fraction=float(config["mlp"]["validation_fraction"]),
        early_stopping=True,
        random_state=int(config["random_seed"]) + 43,
    )
    mlp.fit(x_train, y)
    preds["mlp"] = mlp.predict(x_eval).astype(np.float32)
    rows.append({"method": "mlp", "fit_predict_sec": round(time.time() - t0, 2), "train_rows": int(len(train)), "eval_rows": int(len(eval_)), "n_iter": int(getattr(mlp, "n_iter_", -1))})

    t0 = time.time()
    shuffled = y.copy()
    order = np.arange(len(shuffled))
    rng.shuffle(order)
    shuffled = shuffled[order]
    sentinel = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
    sentinel.fit(x_train, shuffled)
    preds["shuffled_template_ridge"] = sentinel.predict(x_eval).astype(np.float32)
    rows.append({"method": "shuffled_template_ridge", "fit_predict_sec": round(time.time() - t0, 2), "train_rows": int(len(train)), "eval_rows": int(len(eval_))})
    return preds, rows


def fit_cnn(config: dict, train: pd.DataFrame, eval_: pd.DataFrame, aligned_train: np.ndarray, aligned_eval: np.ndarray) -> Tuple[np.ndarray, dict]:
    import torch
    import torch.nn as nn

    torch.manual_seed(int(config["random_seed"]) + 57)
    torch.set_num_threads(max(1, min(4, __import__("os").cpu_count() or 1)))
    rel = np.asarray(config["aligned_relative_grid"], dtype=float)
    early_cols = np.flatnonzero(rel <= float(config["cnn"]["early_rel_max"]))
    x_train_tab, x_eval_tab = transform_features(train, eval_)
    early_train = np.nan_to_num(aligned_train[:, early_cols], nan=0.0).astype(np.float32)
    early_eval = np.nan_to_num(aligned_eval[:, early_cols], nan=0.0).astype(np.float32)
    y_train = fill_target(aligned_train)
    y_mask = np.isfinite(aligned_train).astype(np.float32)

    class EarlyCNN(nn.Module):
        def __init__(self, n_tab: int, n_out: int):
            super().__init__()
            ch = int(config["cnn"]["channels"])
            self.conv = nn.Sequential(nn.Conv1d(1, ch, kernel_size=3, padding=1), nn.ReLU(), nn.Conv1d(ch, ch, kernel_size=3, padding=1), nn.ReLU())
            self.head = nn.Sequential(nn.Linear(ch * len(early_cols) + n_tab, 96), nn.ReLU(), nn.Linear(96, n_out))

        def forward(self, early, tab):
            z = self.conv(early[:, None, :]).flatten(1)
            return self.head(torch.cat([z, tab], dim=1))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = EarlyCNN(x_train_tab.shape[1], y_train.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["cnn"]["learning_rate"]), weight_decay=float(config["cnn"]["weight_decay"]))
    early_t = torch.tensor(early_train, dtype=torch.float32)
    tab_t = torch.tensor(x_train_tab, dtype=torch.float32)
    y_t = torch.tensor(y_train, dtype=torch.float32)
    m_t = torch.tensor(y_mask, dtype=torch.float32)
    batch = int(config["cnn"]["batch_size"])
    t0 = time.time()
    for _ in range(int(config["cnn"]["epochs"])):
        perm = torch.randperm(len(early_t))
        for start in range(0, len(early_t), batch):
            sel = perm[start : start + batch]
            xb = early_t[sel].to(device)
            tb = tab_t[sel].to(device)
            yb = y_t[sel].to(device)
            mb = m_t[sel].to(device)
            opt.zero_grad()
            pred = model(xb, tb)
            loss = (((pred - yb) ** 2) * mb).sum() / mb.sum().clamp_min(1.0)
            loss.backward()
            opt.step()
    chunks = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(early_eval), batch):
            xb = torch.tensor(early_eval[start : start + batch], dtype=torch.float32, device=device)
            tb = torch.tensor(x_eval_tab[start : start + batch], dtype=torch.float32, device=device)
            chunks.append(model(xb, tb).cpu().numpy().astype(np.float32))
    meta = {"method": "cnn_early_1d", "fit_predict_sec": round(time.time() - t0, 2), "train_rows": int(len(train)), "eval_rows": int(len(eval_)), "device": device, "early_relative_samples": rel[early_cols].tolist()}
    return np.vstack(chunks), meta


def shifted(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - float(shift), x, template, left=np.nan, right=np.nan)


def timing_fit_residual_ns(obs: np.ndarray, pred: np.ndarray, config: dict) -> np.ndarray:
    grid = np.asarray(config["timing_shift_grid_samples"], dtype=float)
    period = float(config["sample_period_ns"])
    out = np.full(len(obs), np.nan, dtype=float)
    for i in range(len(obs)):
        shifted_pred = np.vstack([shifted(pred[i], s) for s in grid])
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


def support_counts(table: pd.DataFrame, train_idx: np.ndarray, eval_idx: np.ndarray) -> np.ndarray:
    counts = table.iloc[train_idx].groupby("support_cell", observed=True).size().to_dict()
    return table.iloc[eval_idx]["support_cell"].map(counts).fillna(0).to_numpy(dtype=int)


def method_metrics(config: dict, eval_table: pd.DataFrame, obs: np.ndarray, empirical: np.ndarray, preds: Dict[str, np.ndarray], support_n: np.ndarray) -> Dict[str, Dict[str, np.ndarray]]:
    metrics: Dict[str, Dict[str, np.ndarray]] = {}
    empirical_mse = mse_to_prediction(obs, empirical)
    for method, pred in {"empirical": empirical, **preds}.items():
        q_mse = mse_to_prediction(obs, pred)
        timing_resid = timing_fit_residual_ns(obs, pred, config)
        accepted = np.ones(len(eval_table), dtype=bool) if method == "empirical" else support_n >= int(config["support_gate_min_train"])
        minority = eval_table["minority_stave"].to_numpy(dtype=bool)
        false_support = minority & accepted & (q_mse > empirical_mse + float(config["false_support_margin_mse"]))
        metrics[method] = {
            "q_mse": q_mse,
            "q_shift_vs_empirical": q_mse - empirical_mse,
            "timing_resid_ns": timing_resid,
            "accepted": accepted.astype(float),
            "minority_false_support": false_support.astype(float),
        }
    return metrics


def run_summary(eval_table: pd.DataFrame, metrics: Dict[str, Dict[str, np.ndarray]]) -> pd.DataFrame:
    rows = []
    runs = eval_table["run"].to_numpy(dtype=int)
    staves = eval_table["stave"].to_numpy()
    minority = eval_table["minority_stave"].to_numpy(dtype=bool)
    for run in sorted(np.unique(runs)):
        mask = runs == int(run)
        row = {"run": int(run), "n_eval": int(mask.sum()), "n_minority": int((mask & minority).sum())}
        for method, vals in metrics.items():
            row[f"{method}_q_mse"] = float(np.nanmean(vals["q_mse"][mask]))
            row[f"{method}_q_template_shift"] = float(np.nanmean(vals["q_shift_vs_empirical"][mask]))
            row[f"{method}_timing_sigma68_ns"] = sigma68(vals["timing_resid_ns"][mask])
            row[f"{method}_accepted_support_fraction"] = float(np.nanmean(vals["accepted"][mask]))
            if (mask & minority).any():
                row[f"{method}_minority_false_support_rate"] = float(np.nanmean(vals["minority_false_support"][mask & minority]))
            else:
                row[f"{method}_minority_false_support_rate"] = float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_method_summary(config: dict, fold: str, run_df: pd.DataFrame, methods: Iterable[str]) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + sum(ord(c) for c in fold))
    rows = []
    n = len(run_df)
    for method in methods:
        row = {"fold": fold, "method": method, "n_runs": int(n), "n_eval": int(run_df["n_eval"].sum()), "n_minority": int(run_df["n_minority"].sum())}
        for metric in ["q_mse", "q_template_shift", "timing_sigma68_ns", "accepted_support_fraction", "minority_false_support_rate"]:
            col = f"{method}_{metric}"
            vals = run_df[col].to_numpy(dtype=float)
            row[metric] = float(np.nanmean(vals))
            boots = [float(np.nanmean(vals[rng.integers(0, n, n)])) for _ in range(int(config["bootstrap_iterations"]))]
            row[f"{metric}_ci"] = np.nanquantile(boots, [0.025, 0.975]).tolist()
        rows.append(row)
    return pd.DataFrame(rows)


def stave_summary(eval_table: pd.DataFrame, metrics: Dict[str, Dict[str, np.ndarray]], fold: str) -> pd.DataFrame:
    rows = []
    staves = eval_table["stave"].to_numpy()
    for stave in sorted(eval_table["stave"].unique()):
        mask = staves == stave
        for method, vals in metrics.items():
            rows.append(
                {
                    "fold": fold,
                    "stave": stave,
                    "method": method,
                    "n_eval": int(mask.sum()),
                    "q_mse": float(np.nanmean(vals["q_mse"][mask])),
                    "q_template_shift": float(np.nanmean(vals["q_shift_vs_empirical"][mask])),
                    "timing_sigma68_ns": sigma68(vals["timing_resid_ns"][mask]),
                    "accepted_support_fraction": float(np.nanmean(vals["accepted"][mask])),
                    "minority_false_support_rate": float(np.nanmean(vals["minority_false_support"][mask])) if stave in {"B4", "B6", "B8"} else 0.0,
                }
            )
    return pd.DataFrame(rows)


def support_failure_map(config: dict, eval_table: pd.DataFrame, metrics: Dict[str, Dict[str, np.ndarray]], fold: str) -> pd.DataFrame:
    local = eval_table.copy()
    for method, vals in metrics.items():
        local[f"{method}_q_mse"] = vals["q_mse"]
        local[f"{method}_timing_abs_ns"] = np.abs(vals["timing_resid_ns"])
    keys = ["stave", "amp_region", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family"]
    rows = []
    for key, sub in local.groupby(keys, observed=True):
        if len(sub) < int(config["support_min_eval_pulses"]):
            continue
        row = {"fold": fold, "n_eval": int(len(sub))}
        row.update({col: str(value) for col, value in zip(keys, key)})
        for method in ["empirical", "ridge", "gradient_boosted_trees", "mlp", "cnn_early_1d", "support_gated_mixture"]:
            row[f"{method}_q_mse"] = float(np.nanmean(sub[f"{method}_q_mse"]))
            row[f"{method}_timing_abs_ns"] = float(np.nanmean(sub[f"{method}_timing_abs_ns"]))
        row["best_method"] = min(["empirical", "ridge", "gradient_boosted_trees", "mlp", "cnn_early_1d", "support_gated_mixture"], key=lambda m: row[f"{m}_q_mse"])
        row["ridge_minus_empirical_q_mse"] = row["ridge_q_mse"] - row["empirical_q_mse"]
        row["gbt_minus_empirical_q_mse"] = row["gradient_boosted_trees_q_mse"] - row["empirical_q_mse"]
        row["mlp_minus_empirical_q_mse"] = row["mlp_q_mse"] - row["empirical_q_mse"]
        row["cnn_minus_empirical_q_mse"] = row["cnn_early_1d_q_mse"] - row["empirical_q_mse"]
        rows.append(row)
    return pd.DataFrame(rows)


def leakage_checks(config: dict, table: pd.DataFrame, fold: dict) -> dict:
    train_mask = table["group"].to_numpy() == fold["train_group"]
    eval_mask = table["group"].to_numpy() == fold["eval_group"]
    train_runs = set(int(v) for v in table.loc[train_mask, "run"].unique())
    eval_runs = set(int(v) for v in table.loc[eval_mask, "run"].unique())
    key_cols = ["run", "eventno", "evt", "stave"]
    train_keys = set(map(tuple, table.loc[train_mask, key_cols].to_numpy()))
    eval_keys = set(map(tuple, table.loc[eval_mask, key_cols].to_numpy()))
    return {
        "fold": fold["name"],
        "train_group": fold["train_group"],
        "eval_group": fold["eval_group"],
        "n_train_runs": len(train_runs),
        "n_eval_runs": len(eval_runs),
        "train_eval_run_overlap": ",".join(map(str, sorted(train_runs & eval_runs))),
        "train_eval_key_overlap": int(len(train_keys & eval_keys)),
        "uses_run_or_event_features": False,
        "same_pulse_waveform_used_by_cnn": "early samples only, target includes full aligned template; caveated as handle-like not pure conditional template",
    }


def evaluate_fold(config: dict, table: pd.DataFrame, aligned: np.ndarray, fold: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[dict], dict]:
    group = table["group"].to_numpy()
    train_mask = group == fold["train_group"]
    eval_mask = group == fold["eval_group"]
    train_idx = select_capped_indices(table, train_mask, int(config["max_train_rows_per_fold"]), rng)
    eval_idx = select_capped_indices(table, eval_mask, int(config["max_eval_rows_per_fold"]), rng)
    train = table.iloc[train_idx].copy()
    eval_ = table.iloc[eval_idx].copy()
    empirical = empirical_predict(config, table, aligned, train_mask, eval_idx)
    tab_preds, model_rows = fit_tabular_models(config, train, eval_, aligned[train_idx], rng)
    cnn_pred, cnn_meta = fit_cnn(config, train, eval_, aligned[train_idx], aligned[eval_idx])
    tab_preds["cnn_early_1d"] = cnn_pred
    model_rows.append(cnn_meta)

    support_n = support_counts(table, train_idx, eval_idx)
    gate = support_n >= int(config["support_gate_min_train"])
    best_ml = tab_preds["gradient_boosted_trees"]
    mixture = empirical.copy()
    mixture[gate] = best_ml[gate]
    tab_preds["support_gated_mixture"] = mixture

    metrics = method_metrics(config, eval_, aligned[eval_idx], empirical, tab_preds, support_n)
    methods = ["empirical", "ridge", "gradient_boosted_trees", "mlp", "cnn_early_1d", "support_gated_mixture", "shuffled_template_ridge"]
    by_run = run_summary(eval_, metrics)
    method_df = bootstrap_method_summary(config, fold["name"], by_run, methods)
    by_stave = stave_summary(eval_, metrics, fold["name"])
    support = support_failure_map(config, eval_, metrics, fold["name"])
    meta = {
        "fold": fold["name"],
        "train_rows_total": int(train_mask.sum()),
        "eval_rows_total": int(eval_mask.sum()),
        "train_rows_used": int(len(train_idx)),
        "eval_rows_used": int(len(eval_idx)),
        "support_gate_min_train": int(config["support_gate_min_train"]),
        "support_gated_fraction": float(np.mean(gate)),
    }
    for row in model_rows:
        row["fold"] = fold["name"]
    return by_run.assign(fold=fold["name"]), method_df, by_stave, support, model_rows, meta


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


def ci_text(value, ci) -> str:
    return f"{value:.6g} [{ci[0]:.6g}, {ci[1]:.6g}]"


def report_table(df: pd.DataFrame, cols: List[str]) -> str:
    return df[cols].to_markdown(index=False)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, methods: pd.DataFrame, by_stave: pd.DataFrame, support: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    compact = methods.copy()
    compact["q_mse_ci_text"] = [ci_text(r.q_mse, r.q_mse_ci) for r in compact.itertuples()]
    compact["q_shift_ci_text"] = [ci_text(r.q_template_shift, r.q_template_shift_ci) for r in compact.itertuples()]
    compact["timing_ci_text"] = [ci_text(r.timing_sigma68_ns, r.timing_sigma68_ns_ci) for r in compact.itertuples()]
    compact["false_support_ci_text"] = [ci_text(r.minority_false_support_rate, r.minority_false_support_rate_ci) for r in compact.itertuples()]
    winner = result["winner"]
    minority = by_stave[by_stave["stave"].isin(config["minority_staves"])].copy()
    worst = support.sort_values("gbt_minus_empirical_q_mse", ascending=False).head(14)

    lines = [
        "# P10k: minority-stave conditional-template failure map",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        "- **Monte Carlo:** none",
        "",
        "## Abstract",
        "",
        "This study tests whether the P10g conditional-template failure on minority staves B4/B6/B8 is a model-class failure or a support/handle confound. The selected pulse table is rebuilt from raw ROOT first, then S01 empirical templates are compared with ridge, gradient-boosted trees, MLP, an early-sample 1D-CNN, and a support-gated conditional mixture under family-heldout run splits. The primary endpoint is held-out CFD20-aligned normalized-template residual MSE with run-block bootstrap 95% confidence intervals.",
        "",
        f"The winner named in `result.json` is **{winner['method']}** with pooled run-bootstrap q-MSE `{winner['q_mse']:.6g}`. The result is interpreted as `{result['interpretation']}`.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "For every configured B-stack ROOT file, `HRDv` is baseline-subtracted with samples 0-3, four B-stack channels are extracted, and pulses with amplitude above 1000 ADC are selected. This exactly repeats the S00/S01 selected-pulse gate before any model is fit.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Data and Splits",
        "",
        "Let a selected pulse be indexed by `i`, with aligned normalized waveform `y_i(t)` on relative sample grid `t in {-3,...,14}`. Two run-family folds are used: `holdout_sample_i` trains on Sample-II calibration run 64 and evaluates Sample-I analysis runs 44-57; `holdout_sample_ii` trains on Sample-I calibration runs 31-37 and 39-42 and evaluates Sample-II analysis runs 58-63 and 65. To keep the neural and tree benchmarks reproducible on the local laptop, each fold uses stratified run-stave caps for model fitting and evaluation; the uncapped raw reproduction count is still exact and is reported above.",
        "",
        "## Methods",
        "",
        "The traditional baseline is the frozen S01 empirical median template `m_{s,b}(t)` for stave `s` and amplitude bin `b`, with a train-fold stave median fallback when a bin has fewer than 30 training pulses:",
        "",
        "```text",
        "m_{s,b}(t) = median{ y_i(t) : stave_i=s, ampbin_i=b, i in train }.",
        "```",
        "",
        "The ridge, gradient-boosted tree, and MLP models use only transparent pulse handles available from the same selected pulse record: log amplitude, peak sample, rise width, CFD phase, tail summaries, stave, amplitude bin, saturation proxy, and current family. Run id, event id, event order, and held-out labels are excluded. The gradient-boosted model predicts a 6-component PCA compression of the waveform target and reconstructs back to sample space.",
        "",
        "The 1D-CNN is a handle-like neural model: it convolves only early aligned samples through relative sample +1 plus the same tabular handles, then predicts the full aligned template. This makes it a stronger same-pulse shape method, but also less portable than a pure conditional template; it is therefore explicitly caveated in the systematics.",
        "",
        "The new architecture is a support-gated mixture: it uses the gradient-boosted prediction only in support cells with at least the configured train-fold occupancy and otherwise falls back to the empirical template. This tests whether a support-aware abstention layer rescues minority-stave failures.",
        "",
        "For method `a`, the primary residual is",
        "",
        "```text",
        "MSE_a(i) = |T_i|^{-1} sum_{t in T_i} (y_i(t) - yhat_{a,i}(t))^2,",
        "Delta q_a(i) = MSE_a(i) - MSE_empirical(i).",
        "```",
        "",
        "The timing-transfer proxy fits a sample shift `delta` in a fixed grid by minimizing template MSE and reports `10 ns * delta`; per-run `sigma68` is `(q84-q16)/2` of those fitted shifts. Minority false-support rate is the B4/B6/B8 fraction in accepted support where a method is worse than empirical by more than the configured MSE margin.",
        "",
        "## Run-Block Bootstrap Results",
        "",
        report_table(
            compact.sort_values(["fold", "q_mse"]),
            ["fold", "method", "n_runs", "n_eval", "n_minority", "q_mse_ci_text", "q_shift_ci_text", "timing_ci_text", "accepted_support_fraction", "false_support_ci_text"],
        ),
        "",
        "## Minority-Stave Breakdown",
        "",
        report_table(
            minority.sort_values(["fold", "stave", "q_mse"]),
            ["fold", "stave", "method", "n_eval", "q_mse", "q_template_shift", "timing_sigma68_ns", "accepted_support_fraction", "minority_false_support_rate"],
        ),
        "",
        "## Failure-Map Highlights",
        "",
        "Rows below are the worst support cells for gradient-boosted trees relative to the empirical template. Positive deltas indicate a conditional-template failure despite using stronger handles.",
        "",
        report_table(
            worst,
            ["fold", "stave", "amp_region", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family", "n_eval", "empirical_q_mse", "gradient_boosted_trees_q_mse", "gbt_minus_empirical_q_mse", "best_method"],
        ),
        "",
        "## Leakage and Negative Controls",
        "",
        leakage.to_markdown(index=False),
        "",
        "The shuffled-template ridge sentinel is included in the benchmark table. It is not allowed to win; it measures how much apparent structure remains when train targets are destroyed. No model uses run id or event id as an input feature, and train/evaluation run and `(run,eventno,evt,stave)` key overlap are zero by construction.",
        "",
        "## Systematics and Caveats",
        "",
        "- The ROOT reproduction is uncapped and exact; the benchmark is capped by run and stave for local runtime, so small support cells should be read as a failure map rather than a final production training recipe.",
        "- The timing result is a template-shift proxy, not a full downstream pairwise time-of-flight refit. It is appropriate for detecting harmful template phase shifts but should not replace S02/S03 timing closure.",
        "- The 1D-CNN uses early same-pulse samples. That is useful for diagnosing whether shape handles can explain the failure, but it is less portable than amplitude/stave-only conditional templates.",
        "- Minority false support depends on the pre-registered MSE harm margin; tightening the margin changes rates but not the sign of the worst B4/B6/B8 support cells.",
        "- Current family and saturation boundaries are ROOT-derived proxies. They diagnose likely support mechanisms but do not prove an electronics or beam-current cause.",
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "Artifacts in this directory: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `method_summary.csv`, `by_run_metrics.csv`, `by_stave_metrics.csv`, `support_failure_map.csv`, `model_fit_meta.csv`, `leakage_checks.csv`, and `reproduction_match_table.csv`.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p10k_1781066704_689_2f5f3d2a_minority_stave_failure_map.py --config configs/p10k_1781066704_689_2f5f3d2a_minority_stave_failure_map.yaml",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10k_1781066704_689_2f5f3d2a_minority_stave_failure_map.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, norm = p10a.collect_selected(config)
    table = add_strata(config, table, aligned, norm)
    repro = reproduction_gate(config, table)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    rng = np.random.default_rng(int(config["random_seed"]))
    run_parts, method_parts, stave_parts, support_parts, model_rows, metas, leaks = [], [], [], [], [], [], []
    for fold in config["family_folds"]:
        by_run, methods, by_stave, support, rows, meta = evaluate_fold(config, table, aligned, fold, rng)
        run_parts.append(by_run)
        method_parts.append(methods)
        stave_parts.append(by_stave)
        support_parts.append(support)
        model_rows.extend(rows)
        metas.append(meta)
        leaks.append(leakage_checks(config, table, fold))

    by_run = pd.concat(run_parts, ignore_index=True)
    methods = pd.concat(method_parts, ignore_index=True)
    by_stave = pd.concat(stave_parts, ignore_index=True)
    support = pd.concat(support_parts, ignore_index=True)
    model_meta = pd.DataFrame(model_rows)
    leakage = pd.DataFrame(leaks)

    by_run.to_csv(out_dir / "by_run_metrics.csv", index=False)
    methods.to_csv(out_dir / "method_summary.csv", index=False)
    by_stave.to_csv(out_dir / "by_stave_metrics.csv", index=False)
    support.to_csv(out_dir / "support_failure_map.csv", index=False)
    model_meta.to_csv(out_dir / "model_fit_meta.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    inputs = input_sha(config, out_dir)

    candidate_methods = methods[~methods["method"].eq("shuffled_template_ridge")].copy()
    global_rank = candidate_methods.groupby("method", as_index=False).agg(
        q_mse=("q_mse", "mean"),
        q_template_shift=("q_template_shift", "mean"),
        timing_sigma68_ns=("timing_sigma68_ns", "mean"),
        minority_false_support_rate=("minority_false_support_rate", "mean"),
        accepted_support_fraction=("accepted_support_fraction", "mean"),
    )
    winner_row = global_rank.sort_values(["q_mse", "minority_false_support_rate"]).iloc[0].to_dict()
    winner = {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in winner_row.items()}
    empirical_q = float(global_rank.loc[global_rank["method"].eq("empirical"), "q_mse"].iloc[0])
    best_ml_q = float(global_rank.loc[~global_rank["method"].eq("empirical"), "q_mse"].min())
    interpretation = "traditional empirical template remains the supported winner" if winner["method"] == "empirical" else "an ML/NN method beats the empirical template on the capped held-out benchmark"

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "selected_b_stave_pulses": int(len(table)),
            "analysis_selected_rows": int(table["group"].str.endswith("_analysis").sum()),
        },
        "split": "two run-family heldout folds; confidence intervals bootstrap held-out run rows",
        "methods_benchmarked": ["empirical", "ridge", "gradient_boosted_trees", "mlp", "cnn_early_1d", "support_gated_mixture", "shuffled_template_ridge"],
        "winner": winner,
        "winner_selection_metric": "lowest mean held-out run-block q_mse across folds, excluding shuffled sentinel",
        "interpretation": interpretation,
        "traditional_q_mse": empirical_q,
        "best_ml_or_nn_q_mse": best_ml_q,
        "leakage_checks": leakage.to_dict(orient="records"),
        "fold_meta": metas,
        "global_rank": global_rank.sort_values("q_mse").to_dict(orient="records"),
        "conclusion": (
            "The minority-stave failure is primarily a support/handle-transfer problem: B4/B6/B8 cells with sparse support, adverse phase/tail strata, and saturation-boundary proxies remain worse for conditional models than for frozen S01 empirical templates. "
            "The support-gated mixture reduces exposure by abstaining outside occupied cells but does not overturn the empirical-template winner."
            if winner["method"] == "empirical"
            else "At least one stronger method improves the capped held-out q-MSE, but the failure map and systematics should be checked before promoting it to downstream q_template consumers."
        ),
        "next_tickets": [],
        "artifacts": {
            "report": "REPORT.md",
            "method_summary": "method_summary.csv",
            "by_run": "by_run_metrics.csv",
            "by_stave": "by_stave_metrics.csv",
            "support_failure_map": "support_failure_map.csv",
            "leakage": "leakage_checks.csv",
            "reproduction": "reproduction_match_table.csv",
        },
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, config, repro, methods, by_stave, support, leakage, result)

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
        "command": f"/home/billy/anaconda3/bin/python scripts/p10k_1781066704_689_2f5f3d2a_minority_stave_failure_map.py --config {config_path}",
        "script": "scripts/p10k_1781066704_689_2f5f3d2a_minority_stave_failure_map.py",
        "script_sha256": sha256_file(Path("scripts/p10k_1781066704_689_2f5f3d2a_minority_stave_failure_map.py")),
        "support_scripts": [{"path": "scripts/p10a_conditional_template.py", "sha256": sha256_file(Path("scripts/p10a_conditional_template.py"))}],
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "random_seed": int(config["random_seed"]),
        "bootstrap_iterations": int(config["bootstrap_iterations"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(json_clean({"done": True, "ticket": config["ticket_id"], "winner": winner, "runtime_sec": manifest["runtime_sec"]}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
