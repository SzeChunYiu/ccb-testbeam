#!/usr/bin/env python3
"""P10o downstream timing closure for P10j accepted tail-surrogate cells."""

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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
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


def import_script(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, Path(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


p10a = import_script("p10a_conditional_template", "scripts/p10a_conditional_template.py")
s02 = import_script("s02_timing_pickoff", "scripts/s02_timing_pickoff.py")


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


def configured_runs(config: dict) -> List[int]:
    runs = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def cap_indices(idx: np.ndarray, cap: int, rng: np.random.Generator) -> np.ndarray:
    idx = np.asarray(idx, dtype=int)
    if len(idx) <= int(cap):
        return idx
    return np.sort(rng.choice(idx, size=int(cap), replace=False))


def pulse_features(config: dict, pulses: pd.DataFrame) -> pd.DataFrame:
    out = pulses.copy()
    wf = np.vstack(out["waveform"].to_numpy()).astype(np.float32)
    amp = out["amplitude_adc"].to_numpy(dtype=float)
    norm = wf / np.maximum(amp[:, None], 1.0)
    cfd20 = p10a.cfd_times(wf, amp, 0.20)
    cfd80 = p10a.cfd_times(wf, amp, 0.80)
    phase = cfd20 - np.floor(cfd20)
    tail = norm[:, 8:].sum(axis=1)
    late = norm[:, 12:].sum(axis=1)
    out["cfd20_samples"] = cfd20
    out["cfd80_samples"] = cfd80
    out["cfd_phase"] = phase
    out["rise_width_samples"] = cfd80 - cfd20
    out["log_amp"] = np.log(np.maximum(amp, 1.0))
    out["log_area"] = np.log(np.maximum(out["area_adc_samples"].to_numpy(dtype=float), 1.0))
    out["area_over_amp"] = out["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    out["tail_sum_norm"] = tail
    out["tail_late_frac"] = late / np.maximum(tail, 1.0e-9)
    out["amp_bin"] = p10a.assign_amp_bins(amp, np.asarray(config["template_amplitude_edges_adc"], dtype=float))
    out["phase_bin"] = np.clip(np.searchsorted(np.asarray(config["phase_edges"], dtype=float), phase, side="right") - 1, 0, 2)
    out["rise_bin"] = np.clip(np.searchsorted(np.asarray(config["rise_edges_samples"], dtype=float), out["rise_width_samples"].to_numpy(dtype=float), side="right") - 1, 0, 2)
    out["tail_bin"] = np.clip(np.searchsorted(np.asarray(config["tail_edges"], dtype=float), tail, side="right") - 1, 0, 2)
    out.attrs["norm"] = norm
    return out


def build_phase_templates(config: dict, pulses: pd.DataFrame, train_mask: np.ndarray) -> dict:
    norm = pulses.attrs["norm"]
    min_n = int(config["template_min_bin_pulses"])
    templates = {}
    fallback = {}
    rows = []
    for stave, stave_sub in pulses[train_mask].groupby("stave", observed=True):
        idx_stave = stave_sub.index.to_numpy(dtype=int)
        fallback[str(stave)] = np.nanmedian(norm[idx_stave], axis=0).astype(np.float32)
    for key, sub in pulses[train_mask].groupby(["stave", "amp_bin", "phase_bin"], observed=True):
        idx = sub.index.to_numpy(dtype=int)
        source = "phase_amp_bin" if len(idx) >= min_n else "stave_fallback"
        template = np.nanmedian(norm[idx], axis=0).astype(np.float32) if source == "phase_amp_bin" else fallback[str(key[0])]
        templates[(str(key[0]), int(key[1]), int(key[2]))] = template
        rows.append({"stave": key[0], "amp_bin": int(key[1]), "phase_bin": int(key[2]), "n_train": int(len(idx)), "source": source})
    for stave in sorted(pulses["stave"].unique()):
        for amp_bin in range(len(config["template_amplitude_edges_adc"]) - 1):
            for phase_bin in range(len(config["phase_edges"]) - 1):
                templates.setdefault((str(stave), int(amp_bin), int(phase_bin)), fallback[str(stave)])
    return {"templates": templates, "fallback": fallback, "rows": pd.DataFrame(rows)}


def template_residual_features(config: dict, pulses: pd.DataFrame, pack: dict) -> pd.DataFrame:
    norm = pulses.attrs["norm"]
    rows = []
    for i, row in enumerate(pulses.itertuples()):
        tmpl = pack["templates"][(str(row.stave), int(row.amp_bin), int(row.phase_bin))]
        resid = norm[i] - tmpl
        rows.append(
            {
                "template_mse": float(np.nanmean(resid**2)),
                "template_tail_bias": float(np.nansum(resid[8:])),
                "template_late_bias": float(np.nansum(resid[12:])),
            }
        )
    return pd.DataFrame(rows, index=pulses.index)


def geometry_positions(staves: List[str], spacing_cm: float) -> Dict[str, float]:
    order = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}
    return {stave: spacing_cm * order[stave] for stave in staves}


def add_targets(config: dict, pulses: pd.DataFrame) -> pd.DataFrame:
    out = pulses.copy()
    staves = list(config["timing"]["downstream_staves"])
    positions = geometry_positions(staves, float(config["timing"]["spacing_cm"]))
    out["t_cfd20_ns"] = float(config["sample_period_ns"]) * out["cfd20_samples"]
    out["t_geom_ns"] = out["t_cfd20_ns"] - out["stave"].map(positions).astype(float) * float(config["timing"]["tof_per_cm_ns"])
    wide_t = out.pivot(index="event_id", columns="stave", values="t_geom_ns")
    wide_q = out.pivot(index="event_id", columns="stave", values="log_area")
    target_t = np.full(len(out), np.nan)
    target_q = np.full(len(out), np.nan)
    for i, row in enumerate(out.itertuples()):
        if row.event_id not in wide_t.index:
            continue
        others = [s for s in staves if s != row.stave]
        tv = wide_t.loc[row.event_id, others].to_numpy(dtype=float)
        qv = wide_q.loc[row.event_id, others].to_numpy(dtype=float)
        if np.isfinite(tv).all() and np.isfinite(row.t_geom_ns):
            target_t[i] = float(row.t_geom_ns - tv.mean())
        if np.isfinite(qv).all() and np.isfinite(row.log_area):
            target_q[i] = float(row.log_area - qv.mean())
    out["target_t_ns"] = target_t
    out["target_log_charge"] = target_q
    return out


def feature_matrix(pulses: pd.DataFrame, include_wave: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    numeric_cols = [
        "log_amp",
        "area_over_amp",
        "peak_sample",
        "cfd20_samples",
        "cfd_phase",
        "rise_width_samples",
        "tail_sum_norm",
        "tail_late_frac",
        "template_mse",
        "template_tail_bias",
        "template_late_bias",
    ]
    cat_cols = ["stave", "amp_bin", "phase_bin", "rise_bin", "tail_bin"]
    num = pulses[numeric_cols].to_numpy(dtype=float)
    enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    cat = enc.fit_transform(pulses[cat_cols].astype(str))
    X = np.hstack([num, cat]).astype(np.float32)
    wave = pulses.attrs["norm"].astype(np.float32) if include_wave else np.empty((len(pulses), 0), dtype=np.float32)
    return X, wave


def transform_eval_features(train: pd.DataFrame, eval_: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    numeric_cols = [
        "log_amp",
        "area_over_amp",
        "peak_sample",
        "cfd20_samples",
        "cfd_phase",
        "rise_width_samples",
        "tail_sum_norm",
        "tail_late_frac",
        "template_mse",
        "template_tail_bias",
        "template_late_bias",
    ]
    cat_cols = ["stave", "amp_bin", "phase_bin", "rise_bin", "tail_bin"]
    scaler = StandardScaler()
    enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    Xtr = np.hstack([scaler.fit_transform(train[numeric_cols].to_numpy(dtype=float)), enc.fit_transform(train[cat_cols].astype(str))]).astype(np.float32)
    Xev = np.hstack([scaler.transform(eval_[numeric_cols].to_numpy(dtype=float)), enc.transform(eval_[cat_cols].astype(str))]).astype(np.float32)
    return Xtr, Xev, train.attrs["norm"].astype(np.float32), eval_.attrs["norm"].astype(np.float32)


def fit_traditional(config: dict, train: pd.DataFrame, eval_: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
    keys_full = ["stave", "amp_bin", "phase_bin", "rise_bin", "tail_bin"]
    keys_loose = ["stave", "amp_bin", "phase_bin"]
    y = train[["target_t_ns", "target_log_charge"]].to_numpy(dtype=float)
    table_full, table_loose, rows = {}, {}, []
    for name, keys, store, min_n in [("full", keys_full, table_full, int(config["handle_min_bin_pulses"])), ("loose", keys_loose, table_loose, int(config["handle_min_bin_pulses"]))]:
        for key, sub in train.groupby(keys, observed=True):
            idx = sub.index.to_numpy(dtype=int)
            local = train.index.get_indexer(idx)
            if len(local) >= min_n:
                store[tuple(str(v) for v in (key if isinstance(key, tuple) else (key,)))] = np.nanmedian(y[local], axis=0)
            rows.append({"table": name, "key": "|".join(str(v) for v in (key if isinstance(key, tuple) else (key,))), "n_train": int(len(local)), "usable": bool(len(local) >= min_n)})
    fallback = {}
    for stave, sub in train.groupby("stave", observed=True):
        local = train.index.get_indexer(sub.index.to_numpy(dtype=int))
        fallback[str(stave)] = np.nanmedian(y[local], axis=0)
    global_fb = np.nanmedian(y, axis=0)
    pred, sources = [], []
    for row in eval_.itertuples():
        full = tuple(str(getattr(row, k)) for k in keys_full)
        loose = tuple(str(getattr(row, k)) for k in keys_loose)
        if full in table_full:
            pred.append(table_full[full])
            sources.append("full")
        elif loose in table_loose:
            pred.append(table_loose[loose])
            sources.append("loose")
        elif str(row.stave) in fallback:
            pred.append(fallback[str(row.stave)])
            sources.append("stave")
        else:
            pred.append(global_fb)
            sources.append("global")
    occ = pd.DataFrame(rows)
    occ["eval_full_fallback_rate"] = float(np.mean(np.asarray(sources) != "full"))
    return np.vstack(pred).astype(float), occ


class MLP(nn.Module):
    def __init__(self, n_in: int, n_out: int, hidden: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, n_out))

    def forward(self, x):
        return self.net(x)


class WaveCNN(nn.Module):
    def __init__(self, n_tab: int, n_out: int, channels: int, hidden: int, gated: bool):
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(nn.Conv1d(1, channels, 3, padding=1), nn.ReLU(), nn.Conv1d(channels, channels, 5, padding=2), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
        self.gate = nn.Sequential(nn.Linear(n_tab, channels), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(n_tab + channels, hidden), nn.ReLU(), nn.Linear(hidden, n_out))

    def forward(self, wave, tab):
        z = self.conv(wave).squeeze(-1)
        if self.gated:
            z = z * self.gate(tab)
        return self.head(torch.cat([z, tab], dim=1))


def fit_torch(config: dict, name: str, Xtr: np.ndarray, ytr: np.ndarray, Xev: np.ndarray, Wtr: np.ndarray, Wev: np.ndarray, rng: np.random.Generator) -> Tuple[np.ndarray, dict]:
    if torch is None:
        raise RuntimeError("torch unavailable")
    cfg = config["torch"]
    idx = cap_indices(np.arange(len(Xtr)), int(cfg["max_train_rows"]), rng)
    y_mean = np.nanmean(ytr[idx], axis=0)
    y_std = np.nanstd(ytr[idx], axis=0)
    y_std[y_std == 0] = 1.0
    yfit = ((ytr[idx] - y_mean) / y_std).astype(np.float32)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(int(config["random_seed"]) + len(name))
    if name == "mlp":
        ds = TensorDataset(torch.from_numpy(Xtr[idx].astype(np.float32)), torch.from_numpy(yfit))
        model = MLP(Xtr.shape[1], ytr.shape[1], int(cfg["hidden_dim"])).to(device)
        epochs = int(cfg["mlp_epochs"])
    else:
        ds = TensorDataset(torch.from_numpy(Wtr[idx, None, :].astype(np.float32)), torch.from_numpy(Xtr[idx].astype(np.float32)), torch.from_numpy(yfit))
        model = WaveCNN(Xtr.shape[1], ytr.shape[1], int(cfg["cnn_channels"]), int(cfg["hidden_dim"]), gated=(name == "phase_gated_cnn_new")).to(device)
        epochs = int(cfg["cnn_epochs"])
    loader = DataLoader(ds, batch_size=int(cfg["batch_size"]), shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["learning_rate"]), weight_decay=float(cfg["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(epochs):
        for batch in loader:
            opt.zero_grad()
            if name == "mlp":
                pred = model(batch[0].to(device))
                target = batch[1].to(device)
            else:
                pred = model(batch[0].to(device), batch[1].to(device))
                target = batch[2].to(device)
            loss = loss_fn(pred, target)
            loss.backward()
            opt.step()
    model.eval()
    pred = []
    with torch.no_grad():
        for start in range(0, len(Xev), 4096):
            if name == "mlp":
                out = model(torch.from_numpy(Xev[start : start + 4096].astype(np.float32)).to(device))
            else:
                out = model(torch.from_numpy(Wev[start : start + 4096, None, :].astype(np.float32)).to(device), torch.from_numpy(Xev[start : start + 4096].astype(np.float32)).to(device))
            pred.append(out.cpu().numpy())
    return np.vstack(pred) * y_std + y_mean, {"device": str(device), "train_rows": int(len(idx)), "epochs": epochs}


def fit_models(config: dict, train: pd.DataFrame, eval_: pd.DataFrame, rng: np.random.Generator) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
    Xtr, Xev, Wtr, Wev = transform_eval_features(train, eval_)
    ytr = train[["target_t_ns", "target_log_charge"]].to_numpy(dtype=float)
    rows, preds = [], {}
    specs = [
        ("ridge", make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))),
        ("gradient_boosted_trees", MultiOutputRegressor(GradientBoostingRegressor(**dict(config["gradient_boosting"])))),
    ]
    for name, model in specs:
        t0 = time.time()
        model.fit(Xtr, ytr)
        preds[name] = model.predict(Xev).astype(float)
        rows.append({"model": name, "status": "trained", "train_rows": int(len(train)), "eval_rows": int(len(eval_)), "fit_predict_sec": round(time.time() - t0, 2)})
    t0 = time.time()
    order = np.arange(len(ytr))
    rng.shuffle(order)
    sentinel = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
    sentinel.fit(Xtr, ytr[order])
    preds["shuffled_target_ridge_sentinel"] = sentinel.predict(Xev).astype(float)
    rows.append({"model": "shuffled_target_ridge_sentinel", "status": "trained_control", "train_rows": int(len(train)), "eval_rows": int(len(eval_)), "fit_predict_sec": round(time.time() - t0, 2), "meta": json.dumps({"target": "row-permuted train targets"}, sort_keys=True)})
    for name in ["mlp", "cnn_1d", "phase_gated_cnn_new"]:
        t0 = time.time()
        try:
            preds[name], meta = fit_torch(config, name, Xtr, ytr, Xev, Wtr, Wev, rng)
            status = "trained"
        except Exception as exc:
            preds[name] = np.tile(np.nanmedian(ytr, axis=0), (len(eval_), 1))
            meta = {"error": str(exc)}
            status = "fallback_median_due_to_error"
        rows.append({"model": name, "status": status, "train_rows": int(len(train)), "eval_rows": int(len(eval_)), "fit_predict_sec": round(time.time() - t0, 2), "meta": json.dumps(meta, sort_keys=True)})
    return preds, pd.DataFrame(rows)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def run_metrics(config: dict, eval_: pd.DataFrame, pred: np.ndarray, method: str, fold: str) -> pd.DataFrame:
    work = eval_.copy()
    work["t_consumer"] = work["t_geom_ns"] - pred[:, 0]
    work["q_consumer"] = work["log_area"] - pred[:, 1]
    rows = []
    pairs = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
    for run, sub in work.groupby("run", observed=True):
        raw_wide_t = sub.pivot(index="event_id", columns="stave", values="t_geom_ns").dropna()
        wide_t = sub.pivot(index="event_id", columns="stave", values="t_consumer").dropna()
        wide_q = sub.pivot(index="event_id", columns="stave", values="q_consumer").dropna()
        wide_secondary = sub.pivot(index="event_id", columns="stave", values="area_over_amp").dropna()
        raw_tres, tres, qres, secondary_proxy = [], [], [], []
        for a, b in pairs:
            if a in raw_wide_t and b in raw_wide_t and a in wide_t and b in wide_t:
                paired = pd.concat(
                    [
                        raw_wide_t[[a, b]].rename(columns={a: "raw_a", b: "raw_b"}),
                        wide_t[[a, b]].rename(columns={a: "fit_a", b: "fit_b"}),
                        wide_secondary[[a, b]].rename(columns={a: "sec_a", b: "sec_b"}) if a in wide_secondary and b in wide_secondary else pd.DataFrame(index=raw_wide_t.index),
                    ],
                    axis=1,
                ).dropna()
                if len(paired):
                    raw_tres.append((paired["raw_a"] - paired["raw_b"]).to_numpy())
                    tres.append((paired["fit_a"] - paired["fit_b"]).to_numpy())
                    if "sec_a" in paired and "sec_b" in paired:
                        secondary_proxy.append(paired[["sec_a", "sec_b"]].max(axis=1).to_numpy())
            if a in wide_q and b in wide_q:
                qres.append((wide_q[a] - wide_q[b]).to_numpy())
        raw_tv = np.concatenate(raw_tres) if raw_tres else np.asarray([])
        tv = np.concatenate(tres) if tres else np.asarray([])
        qv = np.concatenate(qres) if qres else np.asarray([])
        sv = np.concatenate(secondary_proxy) if secondary_proxy else np.asarray([])
        raw_sigma68 = sigma68(raw_tv)
        timing_sigma68 = sigma68(tv)
        raw_tail = float(np.mean(np.abs(raw_tv) > 5.0)) if len(raw_tv) else float("nan")
        tail = float(np.mean(np.abs(tv) > 5.0)) if len(tv) else float("nan")
        if len(tv) and len(sv) == len(tv):
            cut = np.nanmedian(sv)
            high = sv >= cut
            low = sv < cut
            high_tail = float(np.mean(np.abs(tv[high]) > 5.0)) if np.any(high) else float("nan")
            low_tail = float(np.mean(np.abs(tv[low]) > 5.0)) if np.any(low) else float("nan")
            high_minus_low_secondary_proxy = high_tail - low_tail if np.isfinite(high_tail) and np.isfinite(low_tail) else float("nan")
        else:
            high_minus_low_secondary_proxy = float("nan")
        accepted_support_harm_rate = (
            float(np.mean(((np.abs(tv) > 5.0) & (np.abs(raw_tv) <= 5.0)) | (np.abs(tv) > np.abs(raw_tv) + 1.0)))
            if len(tv) and len(raw_tv) == len(tv)
            else float("nan")
        )
        ratio = float(timing_sigma68 / raw_sigma68) if np.isfinite(timing_sigma68) and np.isfinite(raw_sigma68) and raw_sigma68 > 0 else float("nan")
        too_good = bool(np.isfinite(ratio) and ratio < 0.10)
        rows.append(
            {
                "fold": fold,
                "method": method,
                "run": int(run),
                "n_eval_pulses": int(len(sub)),
                "n_events": int(sub["event_id"].nunique()),
                "raw_timing_sigma68_ns": raw_sigma68,
                "raw_timing_rms_ns": float(np.nanstd(raw_tv)),
                "timing_sigma68_ns": timing_sigma68,
                "timing_rms_ns": float(np.nanstd(tv)),
                "raw_tail_gt5ns_fraction": raw_tail,
                "tail_gt5ns_fraction": tail,
                "tail_gt5ns_delta_vs_raw": float(tail - raw_tail) if np.isfinite(tail) and np.isfinite(raw_tail) else float("nan"),
                "high_minus_low_secondary_proxy": high_minus_low_secondary_proxy,
                "accepted_support_harm_rate": accepted_support_harm_rate,
                "trigger_carryover_ratio": ratio,
                "too_good_trigger_carryover_rate": float(too_good),
                "charge_sigma68_log": sigma68(qv),
                "charge_rms_log": float(np.nanstd(qv)),
            }
        )
    return pd.DataFrame(rows)


def bootstrap(run_df: pd.DataFrame, rng: np.random.Generator, reps: int) -> pd.DataFrame:
    rows = []
    metrics = [
        "raw_timing_sigma68_ns",
        "timing_sigma68_ns",
        "timing_rms_ns",
        "raw_tail_gt5ns_fraction",
        "tail_gt5ns_fraction",
        "tail_gt5ns_delta_vs_raw",
        "high_minus_low_secondary_proxy",
        "accepted_support_harm_rate",
        "trigger_carryover_ratio",
        "too_good_trigger_carryover_rate",
        "charge_sigma68_log",
        "charge_rms_log",
    ]
    for (fold, method), sub in run_df.groupby(["fold", "method"], observed=True):
        mat = sub[metrics].to_numpy(dtype=float)
        boots = np.asarray([mat[rng.integers(0, len(mat), len(mat))].mean(axis=0) for _ in range(int(reps))])
        row = {"fold": fold, "method": method, "runs": ",".join(map(str, sub["run"].astype(int))), "n_eval_pulses": int(sub["n_eval_pulses"].sum()), "n_events": int(sub["n_events"].sum())}
        means = mat.mean(axis=0)
        for i, metric in enumerate(metrics):
            row[metric] = float(means[i])
            row[f"{metric}_ci_low"] = float(np.nanquantile(boots[:, i], 0.025))
            row[f"{metric}_ci_high"] = float(np.nanquantile(boots[:, i], 0.975))
        row["primary_loss"] = float(row["timing_sigma68_ns"] + 0.25 * row["timing_rms_ns"] + 10.0 * row["tail_gt5ns_fraction"])
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, summary: pd.DataFrame, diagnostics: pd.DataFrame, result: dict) -> None:
    table = summary.sort_values(["fold", "primary_loss"]).to_markdown(index=False)
    diag = diagnostics.to_markdown(index=False)
    winner = result["winner"]
    report = rf"""# P10o: Downstream Timing Closure for P10j Accepted Tail-Surrogate Cells

**Ticket:** {config['ticket_id']}  
**Worker:** {config['worker']}  
**Date:** 2026-07-11  
**Raw input:** `{config['raw_root_dir']}`  
**Git commit:** `{result['git_commit']}`

## Question

P10o asks whether the P10j accepted tail-surrogate support cells still improve an independent same-particle downstream timing consumer when applied to B4/B6/B8 and B2-inclusive events. The analysis freezes the empirical support/template machinery inside each training split before evaluating held-out downstream runs, then compares it with S02/S03-style explicit timing baselines and several ML/NN consumers without using held-out run labels, event identifiers, or peer residuals as model features.

## Reproduction Gate

All B-stave pulses with amplitude greater than 1000 ADC were recounted from raw ROOT before fitting any consumer:

{repro.to_markdown(index=False)}

The equality requirement is exact; the analysis aborts if this table has any failing row.

## Methods

For pulse \(i\) in event \(e\) and stave \(s\), the raw waveform \(x_i(t)\) is baseline-subtracted by the median of samples 0--3. Amplitude \(A_i=\max_t x_i(t)\), charge proxy \(Q_i=\sum_t x_i(t)\), and CFD20 time \(c_i\) are computed directly from the raw waveform. The normalized waveform is \(u_i(t)=x_i(t)/A_i\).

The frozen template family is trained only inside each fold's training runs. Templates are medians of \(u_i(t)\) in cells keyed by stave, amplitude bin, and CFD phase bin:

\[
T_{{s,a,p}}(t)=\operatorname{{median}}\{{u_i(t): s_i=s, a_i=a, p_i=p, i\in \mathcal{{D}}_\mathrm{{train}}\}}.
\]

Cells below {config['template_min_bin_pulses']} pulses fall back to the train-only stave median. The downstream feature vector includes explicit handles \(\log A_i\), \(Q_i/A_i\), peak sample, CFD20 phase, rise width, normalized tail sums, categorical stave/bin labels, and frozen-template residual summaries \(\|u_i-T\|_2^2\), tail bias, and late-tail bias.

Timing and charge targets are event-internal leave-one-stave residuals. With geometry correction \(g_s\),

\[
y^t_i = (t_i-g_s)-\frac{{1}}{{3}}\sum_{{r\ne s_i}}(t_{{e,r}}-g_r),
\quad
y^q_i = \log Q_i-\frac{{1}}{{3}}\sum_{{r\ne s_i}}\log Q_{{e,r}}.
\]

Each method predicts \((\hat y^t_i,\hat y^q_i)\). Consumer values are \(t_i^\star=t_i-g_s-\hat y^t_i\) and \(q_i^\star=\log Q_i-\hat y^q_i\). Evaluation uses all pairwise same-event residuals among B2/B4/B6/B8. For a held-out run \(r\), the timing resolution is

\[
\sigma_{{68}}(r)=\frac{{Q_{{84}}(\Delta t^\star_r)-Q_{{16}}(\Delta t^\star_r)}}{{2}},
\quad
f_{{|t|>5}}(r)=\frac{{1}}{{N_r}}\sum_j \mathbb{{1}}(|\Delta t^\star_{{r,j}}|>5\ \mathrm{{ns}}).
\]

The full RMS and charge \(\sigma_{{68}}\) are reported as secondary diagnostics. A too-good trigger-carryover guardrail is also bootstrapped: \(C(r)=\sigma_{{68}}^\star(r)/\sigma_{{68}}^\mathrm{{raw}}(r)\), with a run flagged when \(C(r)<0.10\). This does not prove the absence of all leakage channels, but it makes implausibly trigger-like timing collapse visible in the same run-block uncertainty model as the physics metrics.

Pile-up candidate stability is summarized by a high-minus-low secondary proxy. For each same-event stave pair the secondary score is \(z_j=\max(Q/A)_j\); within each held-out run the median of \(z\) splits pairs into high- and low-secondary halves, and the reported statistic is

\[
H(r)=f_{{|t|>5}}^\mathrm{{high\ z}}(r)-f_{{|t|>5}}^\mathrm{{low\ z}}(r).
\]

Accepted-support harm is a pair-level rate,

\[
A(r)=\frac{{1}}{{N_r}}\sum_j \mathbb{{1}}\left[
\left(|\Delta t^\star_j|>5\ \mathrm{{ns}}\wedge |\Delta t^\mathrm{{raw}}_j|\le 5\ \mathrm{{ns}}\right)
\vee |\Delta t^\star_j|>|\Delta t^\mathrm{{raw}}_j|+1\ \mathrm{{ns}}
\right],
\]

so support cells that improve the central resolution while creating new tails or materially worsening accepted raw pairs remain visible.

## Compared Methods

- `traditional_explicit_handles`: train-only median residual tables keyed by stave, amplitude bin, phase bin, rise bin, and tail bin, with loose/stave/global fallbacks.
- `ridge`: strong linear comparator on the explicit handles and frozen-template residual features.
- `gradient_boosted_trees`: multi-output gradient-boosted trees on the same tabular inputs.
- `mlp`: tabular neural network.
- `cnn_1d`: waveform CNN with tabular head.
- `phase_gated_cnn_new`: new architecture; a CNN representation is multiplicatively gated by phase/template-handle tabular features before the consumer head.
- `shuffled_target_ridge_sentinel`: leakage/sanity control; the ridge model is fit to row-permuted training targets and is reported only as a sentinel, not as a winner candidate.

## Results

{table}

The winner named in `result.json` is **{winner}**, selected among non-sentinel methods by the mean of the fold-level downstream timing loss `timing_sigma68_ns + 0.25 * timing_rms_ns + 10 * tail_gt5ns_fraction`. The raw timing columns, >5 ns tail fraction, high-minus-low secondary proxy, accepted-support harm rate, and carryover ratio are reported with run-block bootstrap 95% CIs; charge closure remains in the table as a secondary check that the consumer did not win by destroying the q-template behavior.

## Model Diagnostics

{diag}

## Systematics and Caveats

Run-family splits are deliberately harsh: Sample-I analysis is evaluated after training on run 64 only, while Sample-II analysis is evaluated after training on Sample-I calibration runs. This tests transport across sample/current families but gives the Sample-I holdout a small training source. The charge target uses the raw area sum as a stable charge proxy, not a calibrated energy scale. The bootstrap treats runs as exchangeable units within each fold; it captures run-to-run variation but not alternate waveform preprocessing choices, alternate CFD fractions, or raw ROOT calibration drift. All template and consumer fits are train-only within fold, and event identifiers, run labels, and held-out peer residuals are excluded from model features. The P10j accepted-support claim is operational here: support-cell handles are frozen before held-out consumer evaluation, but the models are not loaded from an external P10j checkpoint artifact. The shuffled-target ridge sentinel is included to make gross leakage visible; it is excluded from winner selection by construction.

## Files

The report directory contains `result.json`, `manifest.json`, `reproduction_match_table.csv`, `fold_run_metrics.csv`, `fold_summary.csv`, `model_diagnostics.csv`, `template_support.csv`, `input_sha256.csv`, and `fig_consumer_summary.png`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def plot_summary(out_dir: Path, summary: pd.DataFrame) -> None:
    held = summary.copy().sort_values(["fold", "primary_loss"])
    fig, ax = plt.subplots(figsize=(10, 4.8))
    labels = held["fold"] + "\n" + held["method"]
    x = np.arange(len(held))
    ax.bar(x, held["timing_sigma68_ns"], label="timing sigma68 ns")
    ax2 = ax.twinx()
    ax2.plot(x, held["tail_gt5ns_fraction"], "o-", color="tab:red", label="|dt| > 5 ns fraction")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=75, ha="right", fontsize=7)
    ax.set_ylabel("timing sigma68 (ns)")
    ax2.set_ylabel("|dt| > 5 ns fraction")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_consumer_summary.png", dpi=140)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10o_1783657995_18783_32d55674_downstream_timing_closure.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    table, _, _ = p10a.collect_selected(config)
    repro = pd.DataFrame([{"quantity": "S00/S01 selected B-stave pulses", "report_value": int(config["expected_selected_pulses"]), "reproduced": int(len(table)), "delta": int(len(table) - int(config["expected_selected_pulses"])), "tolerance": 0, "pass": bool(len(table) == int(config["expected_selected_pulses"]))}])
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    dcfg = dict(config)
    all_train = sorted(set(sum([fold["train_runs"] for fold in config["family_folds"]], [])))
    all_eval = sorted(set(sum([fold["eval_runs"] for fold in config["family_folds"]], [])))
    dcfg["timing"] = dict(config["timing"], train_runs=all_train, heldout_runs=all_eval)
    pulses = s02.load_downstream_pulses(dcfg)
    pulses = pulse_features(config, pulses)
    pulses = add_targets(config, pulses)

    run_rows, diag_rows, support_rows = [], [], []
    for fold in config["family_folds"]:
        fold_name = str(fold["name"])
        train_mask = pulses["run"].isin(fold["train_runs"]).to_numpy() & np.isfinite(pulses["target_t_ns"].to_numpy()) & np.isfinite(pulses["target_log_charge"].to_numpy())
        eval_mask = pulses["run"].isin(fold["eval_runs"]).to_numpy() & np.isfinite(pulses["target_t_ns"].to_numpy()) & np.isfinite(pulses["target_log_charge"].to_numpy())
        train_idx = cap_indices(np.flatnonzero(train_mask), int(config["max_train_rows_per_fold"]), rng)
        eval_idx = cap_indices(np.flatnonzero(eval_mask), int(config["max_eval_rows_per_fold"]), rng)
        fold_pulses = pulses.iloc[np.r_[train_idx, eval_idx]].copy().reset_index(drop=True)
        fold_pulses.attrs["norm"] = pulses.attrs["norm"][np.r_[train_idx, eval_idx]]
        local_train = np.arange(len(train_idx))
        pack = build_phase_templates(config, fold_pulses, np.isin(np.arange(len(fold_pulses)), local_train))
        support = pack["rows"].copy()
        support["fold"] = fold_name
        support_rows.append(support)
        feat = template_residual_features(config, fold_pulses, pack)
        for col in feat:
            fold_pulses[col] = feat[col]
        train = fold_pulses.iloc[: len(train_idx)].copy()
        train.attrs["norm"] = fold_pulses.attrs["norm"][: len(train_idx)]
        eval_ = fold_pulses.iloc[len(train_idx) :].copy()
        eval_.attrs["norm"] = fold_pulses.attrs["norm"][len(train_idx) :]
        trad_pred, occ = fit_traditional(config, train, eval_)
        occ["fold"] = fold_name
        occ.to_csv(out_dir / f"{fold_name}_traditional_occupancy.csv", index=False)
        pred_map = {"traditional_explicit_handles": trad_pred}
        ml_pred, diag = fit_models(config, train, eval_, rng)
        pred_map.update(ml_pred)
        diag["fold"] = fold_name
        diag_rows.append(diag)
        for method, pred in pred_map.items():
            run_rows.append(run_metrics(config, eval_, pred, method, fold_name))

    run_df = pd.concat(run_rows, ignore_index=True)
    diagnostics = pd.concat(diag_rows, ignore_index=True)
    support = pd.concat(support_rows, ignore_index=True)
    summary = bootstrap(run_df, rng, int(config["bootstrap_iterations"]))
    run_df.to_csv(out_dir / "fold_run_metrics.csv", index=False)
    summary.to_csv(out_dir / "fold_summary.csv", index=False)
    diagnostics.to_csv(out_dir / "model_diagnostics.csv", index=False)
    support.to_csv(out_dir / "template_support.csv", index=False)
    plot_summary(out_dir, summary)

    overall = summary.groupby("method", observed=True)[
        [
            "timing_sigma68_ns",
            "timing_rms_ns",
            "tail_gt5ns_fraction",
            "high_minus_low_secondary_proxy",
            "accepted_support_harm_rate",
            "trigger_carryover_ratio",
            "too_good_trigger_carryover_rate",
            "charge_sigma68_log",
            "primary_loss",
        ]
    ].mean().reset_index().sort_values("primary_loss")
    eligible = overall[~overall["method"].str.contains("sentinel", regex=False)]
    winner = str(eligible.iloc[0]["method"])
    input_rows = []
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in configured_runs(config):
            path = p10a.raw_file(config, int(run))
            row = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            writer.writerow(row)
            input_rows.append(row)
    result = {
        "study": "P10o",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "winner": winner,
        "winner_selection": "lowest non-sentinel mean fold primary_loss = timing_sigma68_ns + 0.25 * timing_rms_ns + 10 * tail_gt5ns_fraction",
        "overall_method_ranking": overall.to_dict(orient="records"),
        "next_tickets": [],
        "reproduction_pass": bool(repro["pass"].all()),
        "reproduced_selected_pulses": int(repro.iloc[0]["reproduced"]),
        "raw_root_dir": config["raw_root_dir"],
        "git_commit": git_commit(),
        "elapsed_sec": round(time.time() - t0, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_report(out_dir, config, repro, summary, diagnostics, result)
    manifest = {
        "config": str(config_path),
        "script": "scripts/p10o_1783657995_18783_32d55674_downstream_timing_closure.py",
        "outputs": sorted(p.name for p in out_dir.iterdir() if p.is_file()),
        "input_count": len(input_rows),
        "platform": platform.platform(),
        "python": sys.version,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"winner": winner, "elapsed_sec": result["elapsed_sec"], "output_dir": str(out_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
