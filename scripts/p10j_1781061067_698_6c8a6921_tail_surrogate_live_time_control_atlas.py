#!/usr/bin/env python3
"""P10j tail-surrogate live-time control atlas.

This study rebuilds the P10/S00 selected B-stack pulse table from raw ROOT,
then compares empirical templates with ridge, gradient-boosted trees, MLP,
tail-knockout 1D-CNN, and a control-gated CNN/GBT ensemble.  The target is the
CFD-aligned, amplitude-normalized waveform; live-time and secondary-fraction
metrics are treated as transfer controls rather than supervised truths.
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
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p10a = load_module("p10a_conditional_template", ROOT / "scripts/p10a_conditional_template.py")
s10c = load_module("s10c_threshold_scan_tau_eff", ROOT / "reports/1781007337.1308.7dc86005/s10c_threshold_scan_tau_eff.py")


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def current_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for name, runs in config["current_strata"].items():
        for run in runs:
            out[int(run)] = name
    return out


def saturation_names(config: dict, amp: np.ndarray) -> np.ndarray:
    out = np.full(len(amp), "unassigned", dtype=object)
    for item in config["saturation_bins"]:
        mask = (amp >= float(item["low"])) & (amp < float(item["high"]))
        out[mask] = str(item["name"])
    return out


def add_strata(config: dict, table: pd.DataFrame, aligned: np.ndarray) -> pd.DataFrame:
    work = table.copy()
    currents = current_lookup(config)
    work["current_stratum"] = [currents.get(int(run), "other") for run in work["run"]]
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    amp = work["amplitude_adc"].to_numpy(dtype=float)
    bin_idx = np.clip(np.searchsorted(edges, amp, side="right") - 1, 0, len(edges) - 2)
    work["amp_bin"] = bin_idx.astype(int)
    work["amp_bin_label"] = ["a{}_{}".format(int(edges[i]), int(edges[i + 1])) for i in bin_idx]
    work["saturation_bin"] = saturation_names(config, amp)
    work["is_saturation_proxy"] = (amp >= 9000.0).astype(int)
    work["is_boundary"] = ((amp >= 6500.0) & (amp < 9000.0)).astype(int)
    work["peak_phase_bin"] = pd.cut(work["peak_sample"], bins=[-1, 3, 5, 7, 99], labels=["early", "nominal", "late", "very_late"]).astype(str)
    q_proxy = np.nanmean(np.square(np.nan_to_num(aligned - np.nanmedian(aligned, axis=0), nan=0.0)), axis=1)
    work["q_proxy_bin"] = pd.qcut(pd.Series(q_proxy).rank(method="first"), 3, labels=["q_low", "q_mid", "q_high"]).astype(str)
    return work


def reproduction_gate(config: dict, table: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
    s10_pulses = s10c.read_selected_pulses()
    _fits, heldout = s10c.traditional_template_fits(s10_pulses)
    live10 = float(heldout["traditional_template_live_10pct_ns"].mean())
    analysis_rows = int(table["group"].str.endswith("_analysis").sum())
    rows = [
        {
            "quantity": "S00/S01 selected B-stave pulses",
            "expected": int(config["expected_selected_pulses"]),
            "reproduced": int(len(table)),
            "delta": int(len(table) - int(config["expected_selected_pulses"])),
            "tolerance": 0,
            "pass": bool(len(table) == int(config["expected_selected_pulses"])),
        },
        {
            "quantity": "analysis selected rows",
            "expected": int(config["expected_analysis_rows"]),
            "reproduced": analysis_rows,
            "delta": int(analysis_rows - int(config["expected_analysis_rows"])),
            "tolerance": 0,
            "pass": bool(analysis_rows == int(config["expected_analysis_rows"])),
        },
        {
            "quantity": "S10b traditional template live10 ns",
            "expected": float(config["expected_s10b_live10_ns"]),
            "reproduced": live10,
            "delta": live10 - float(config["expected_s10b_live10_ns"]),
            "tolerance": float(config["s10b_live10_tolerance_ns"]),
            "pass": bool(abs(live10 - float(config["expected_s10b_live10_ns"])) <= float(config["s10b_live10_tolerance_ns"])),
        },
    ]
    return pd.DataFrame(rows), live10


def stratified_eval_indices(config: dict, table: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    selected: List[np.ndarray] = []
    cap = int(config["max_eval_per_run_stave_amp_sat"])
    work = table[table["run"].isin([int(v) for v in config["eval_runs"]])]
    for _, group in work.groupby(["run", "stave", "amp_bin", "saturation_bin"], observed=True):
        idx = group.index.to_numpy()
        if len(idx) > cap:
            idx = rng.choice(idx, size=cap, replace=False)
        selected.append(idx)
    return np.sort(np.concatenate(selected))


def waveform_metrics(y: np.ndarray, rel_grid: np.ndarray, sample_period_ns: float) -> pd.DataFrame:
    rows = []
    idx_grid = np.arange(y.shape[1])
    tail_mask = rel_grid >= 2
    late_mask = rel_grid >= 5
    for wave in y:
        if not np.isfinite(wave).any():
            rows.append({"live10_ns": np.nan, "tau_eff_ns": np.nan, "tail_sum": np.nan, "secondary_fraction": np.nan, "cfd_sample": np.nan})
            continue
        yy = np.nan_to_num(wave.astype(float), nan=0.0)
        peak_i = int(np.argmax(yy))
        above = np.flatnonzero((idx_grid >= peak_i) & (yy >= 0.10))
        live10 = float(rel_grid[above[-1]] * sample_period_ns) if len(above) else np.nan
        tau_eff = float(live10 / math.log(10.0)) if np.isfinite(live10) else np.nan
        tail = np.maximum(yy[tail_mask], 0.0)
        late = np.maximum(yy[late_mask], 0.0)
        tail_sum = float(np.sum(tail))
        if np.isfinite(yy[peak_i]) and yy[peak_i] > 0:
            target = 0.2 * yy[peak_i]
            cfd = float(peak_i)
            for j in range(1, peak_i + 1):
                if yy[j - 1] <= target <= yy[j] and yy[j] != yy[j - 1]:
                    cfd = float(j - 1 + (target - yy[j - 1]) / (yy[j] - yy[j - 1]))
                    break
        else:
            cfd = np.nan
        secondary = float(max(np.sum(late) - 0.45 * tail_sum, 0.0) / max(tail_sum, 1e-9))
        rows.append({"live10_ns": live10, "tau_eff_ns": tau_eff, "tail_sum": tail_sum, "secondary_fraction": secondary, "cfd_sample": cfd})
    return pd.DataFrame(rows)


def build_traditional_templates(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_idx: np.ndarray):
    min_bin = int(config["template_min_bin_pulses"])
    train = table.iloc[train_idx]
    templates: Dict[Tuple[str, int, str, str], np.ndarray] = {}
    fallback_amp: Dict[Tuple[str, int], np.ndarray] = {}
    fallback_stave: Dict[str, np.ndarray] = {}
    for stave, group in train.groupby("stave", observed=True):
        fallback_stave[str(stave)] = np.nanmedian(aligned[group.index.to_numpy()], axis=0)
    for key, group in train.groupby(["stave", "amp_bin"], observed=True):
        fallback_amp[(str(key[0]), int(key[1]))] = np.nanmedian(aligned[group.index.to_numpy()], axis=0)
    for key, group in train.groupby(["stave", "amp_bin", "current_stratum", "saturation_bin"], observed=True):
        if len(group) >= min_bin:
            templates[(str(key[0]), int(key[1]), str(key[2]), str(key[3]))] = np.nanmedian(aligned[group.index.to_numpy()], axis=0)

    def predict(rows: pd.DataFrame) -> np.ndarray:
        pred = []
        for row in rows.itertuples():
            full = (str(row.stave), int(row.amp_bin), str(row.current_stratum), str(row.saturation_bin))
            amp_key = (str(row.stave), int(row.amp_bin))
            if full in templates:
                pred.append(templates[full])
            elif amp_key in fallback_amp:
                pred.append(fallback_amp[amp_key])
            else:
                pred.append(fallback_stave[str(row.stave)])
        return np.vstack(pred).astype(np.float32)

    return predict, len(templates)


def feature_matrix(config: dict, table: pd.DataFrame, mode: str) -> Tuple[np.ndarray, List[str]]:
    names = ["log_amp", "log_amp2", "area_over_amp", "peak_sample", "is_boundary", "is_saturation_proxy"]
    amp = np.maximum(table["amplitude_adc"].to_numpy(dtype=float), 1.0)
    log_amp = np.log(amp)
    arr = [
        log_amp,
        log_amp * log_amp,
        table["area_adc_samples"].to_numpy(dtype=float) / amp,
        table["peak_sample"].to_numpy(dtype=float),
        table["is_boundary"].to_numpy(dtype=float),
        table["is_saturation_proxy"].to_numpy(dtype=float),
    ]
    for stave in config["staves"]:
        names.append("stave_{}".format(stave))
        arr.append((table["stave"].to_numpy() == stave).astype(float))
    if mode == "nominal":
        for current in sorted(config["current_strata"]):
            names.append("current_{}".format(current))
            arr.append((table["current_stratum"].to_numpy() == current).astype(float))
    elif mode == "amplitude_only":
        names = names[:4]
        arr = arr[:4]
    elif mode == "run_only":
        names = []
        arr = []
        for run in sorted(table["run"].unique()):
            names.append("run_{}".format(int(run)))
            arr.append((table["run"].to_numpy() == run).astype(float))
    else:
        raise ValueError(mode)
    return np.vstack(arr).T.astype(float), names


def fill_target(target: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    med = np.nanmedian(target[train_idx], axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    return np.where(np.isfinite(target), target, med[None, :]).astype(np.float32)


def fit_tabular(config: dict, method: str, X_train: np.ndarray, y_train: np.ndarray):
    if method == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
    if method == "gbt":
        params = dict(config["gbt"])
        seed = int(params.pop("random_state"))
        base = GradientBoostingRegressor(random_state=seed, **params)
        return make_pipeline(StandardScaler(), MultiOutputRegressor(base, n_jobs=-1))
    if method == "mlp":
        params = dict(config["mlp"])
        params["hidden_layer_sizes"] = tuple(params["hidden_layer_sizes"])
        return make_pipeline(StandardScaler(), MLPRegressor(**params))
    raise ValueError(method)


def train_cnn(config: dict, aligned: np.ndarray, tabular: np.ndarray, train_idx: np.ndarray, rng: np.random.Generator):
    import torch
    import torch.nn as nn

    torch.manual_seed(int(config["random_seed"]))
    torch.set_num_threads(max(1, min(4, (getattr(__import__("os"), "cpu_count")() or 1))))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    rel = np.asarray(config["aligned_relative_grid"], dtype=float)
    inp = np.nan_to_num(aligned, nan=0.0).astype(np.float32)
    inp[:, rel >= 2] = 0.0
    target = fill_target(aligned, train_idx)
    x_tab = tabular.astype(np.float32)
    mean = x_tab[train_idx].mean(axis=0)
    scale = x_tab[train_idx].std(axis=0)
    scale[scale == 0] = 1.0
    x_tab = ((x_tab - mean) / scale).astype(np.float32)

    class TailCNN(nn.Module):
        def __init__(self, n_tab: int, channels: int):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(1, channels, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(channels, channels, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(6),
            )
            self.head = nn.Sequential(nn.Linear(channels * 6 + n_tab, 64), nn.ReLU(), nn.Linear(64, 18))

        def forward(self, xw, xt):
            z = self.conv(xw).flatten(1)
            return self.head(torch.cat([z, xt], dim=1))

    model = TailCNN(x_tab.shape[1], int(config["cnn"]["channels"])).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["cnn"]["learning_rate"]), weight_decay=float(config["cnn"]["weight_decay"]))
    batch = int(config["cnn"]["batch_size"])
    idx = train_idx.copy()
    max_train = int(config["max_train_rows_per_fold"])
    if len(idx) > max_train:
        idx = rng.choice(idx, max_train, replace=False)
    xw_all = torch.tensor(inp[idx, None, :], dtype=torch.float32)
    xt_all = torch.tensor(x_tab[idx], dtype=torch.float32)
    y_all = torch.tensor(target[idx], dtype=torch.float32)
    for _ in range(int(config["cnn"]["epochs"])):
        perm = torch.randperm(len(idx))
        for start in range(0, len(idx), batch):
            sel = perm[start : start + batch]
            opt.zero_grad()
            pred = model(xw_all[sel].to(device), xt_all[sel].to(device))
            loss = torch.mean((pred - y_all[sel].to(device)) ** 2)
            loss.backward()
            opt.step()

    def predict(eval_idx: np.ndarray) -> np.ndarray:
        model.eval()
        out = []
        with torch.no_grad():
            for start in range(0, len(eval_idx), batch):
                sel = eval_idx[start : start + batch]
                xw = torch.tensor(inp[sel, None, :], dtype=torch.float32, device=device)
                xt = torch.tensor(x_tab[sel], dtype=torch.float32, device=device)
                out.append(model(xw, xt).cpu().numpy().astype(np.float32))
        return np.vstack(out)

    return predict, device


def mse_rows(obs: np.ndarray, pred: np.ndarray, rel_grid: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(obs) & np.isfinite(pred)
    diff2 = (np.nan_to_num(obs, nan=0.0) - np.nan_to_num(pred, nan=0.0)) ** 2
    denom = valid.sum(axis=1)
    q = np.full(len(obs), np.nan, dtype=float)
    ok = denom > 0
    q[ok] = diff2[ok].sum(axis=1) / denom[ok]
    tail = rel_grid >= 2
    denom_tail = valid[:, tail].sum(axis=1)
    t = np.full(len(obs), np.nan, dtype=float)
    ok_tail = denom_tail > 0
    t[ok_tail] = diff2[:, tail][ok_tail].sum(axis=1) / denom_tail[ok_tail]
    return q, t


def sigma68(values: np.ndarray) -> float:
    vals = values[np.isfinite(values)]
    if len(vals) == 0:
        return float("nan")
    q16, q84 = np.percentile(vals, [16, 84])
    return float(0.5 * (q84 - q16))


def score_predictions(rows: List[dict], table: pd.DataFrame, aligned: np.ndarray, eval_idx: np.ndarray, method: str, pred: np.ndarray, obs_metrics: pd.DataFrame, rel_grid: np.ndarray, sample_period: float):
    q_mse, tail_mse = mse_rows(aligned[eval_idx], pred, rel_grid)
    pred_metrics = waveform_metrics(pred, rel_grid, sample_period)
    obs = obs_metrics.iloc[eval_idx].reset_index(drop=True)
    sub = table.iloc[eval_idx].reset_index(drop=True)
    timing_error_ns = (pred_metrics["cfd_sample"].to_numpy(dtype=float) - obs["cfd_sample"].to_numpy(dtype=float)) * sample_period
    for i, row in sub.iterrows():
        rows.append(
            {
                "row_id": int(eval_idx[i]),
                "method": method,
                "heldout_run": int(row["run"]),
                "stave": row["stave"],
                "current_stratum": row["current_stratum"],
                "amp_bin_label": row["amp_bin_label"],
                "saturation_bin": row["saturation_bin"],
                "peak_phase_bin": row["peak_phase_bin"],
                "q_proxy_bin": row["q_proxy_bin"],
                "amplitude_adc": float(row["amplitude_adc"]),
                "q_template_mse": float(q_mse[i]),
                "tail_mse": float(tail_mse[i]),
                "timing_error_ns": float(timing_error_ns[i]),
                "timing_abs_error_ns": float(abs(timing_error_ns[i])),
                "live10_bias_ns": float(pred_metrics.loc[i, "live10_ns"] - obs.loc[i, "live10_ns"]),
                "live10_abs_error_ns": float(abs(pred_metrics.loc[i, "live10_ns"] - obs.loc[i, "live10_ns"])),
                "tau_eff_abs_error_ns": float(abs(pred_metrics.loc[i, "tau_eff_ns"] - obs.loc[i, "tau_eff_ns"])),
                "secondary_fraction": float(pred_metrics.loc[i, "secondary_fraction"]),
                "observed_secondary_fraction": float(obs.loc[i, "secondary_fraction"]),
                "secondary_abs_error": float(abs(pred_metrics.loc[i, "secondary_fraction"] - obs.loc[i, "secondary_fraction"])),
            }
        )


def run_summary(rows: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = ["q_template_mse", "tail_mse", "live10_abs_error_ns", "tau_eff_abs_error_ns", "timing_abs_error_ns", "secondary_abs_error"]
    per_run = []
    for (method, run), group in rows.groupby(["method", "heldout_run"], observed=True):
        rec = {"method": method, "heldout_run": int(run), "n": int(len(group))}
        for metric in metrics:
            rec[metric] = float(np.nanmean(group[metric]))
        rec["timing_sigma68_ns"] = sigma68(group["timing_error_ns"].to_numpy(dtype=float))
        per_run.append(rec)
    per_run_df = pd.DataFrame(per_run)

    rng = np.random.default_rng(int(config["random_seed"]) + 101)
    summary = []
    value_cols = metrics + ["timing_sigma68_ns"]
    for method, group in per_run_df.groupby("method", observed=True):
        matrix = group[value_cols].to_numpy(dtype=float)
        boots = np.asarray([matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0) for _ in range(int(config["bootstrap_iterations"]))])
        rec = {"method": method, "n_runs": int(len(group)), "n_rows": int(rows.loc[rows["method"] == method, "row_id"].nunique())}
        means = matrix.mean(axis=0)
        for i, col in enumerate(value_cols):
            rec[col] = float(means[i])
            rec[col + "_ci_low"] = float(np.nanquantile(boots[:, i], 0.025))
            rec[col + "_ci_high"] = float(np.nanquantile(boots[:, i], 0.975))
        summary.append(rec)
    summary_df = pd.DataFrame(summary).sort_values("tail_mse")

    wide = per_run_df.pivot(index="heldout_run", columns="method", values=value_cols)
    deltas = []
    for method in sorted(rows["method"].unique()):
        if method == "traditional_empirical_template":
            continue
        for metric in value_cols:
            vals = wide[(metric, method)].to_numpy(dtype=float) - wide[(metric, "traditional_empirical_template")].to_numpy(dtype=float)
            vals = vals[np.isfinite(vals)]
            boots = np.asarray([vals[rng.integers(0, len(vals), len(vals))].mean() for _ in range(int(config["bootstrap_iterations"]))])
            deltas.append({"method": method, "metric": metric, "delta_vs_traditional": float(vals.mean()), "ci_low": float(np.quantile(boots, 0.025)), "ci_high": float(np.quantile(boots, 0.975))})
    return per_run_df, summary_df, pd.DataFrame(deltas)


def secondary_bootstrap(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 202)
    out = []
    sample_i = rows[rows["current_stratum"].isin(["high_20nA", "low_2nA"])].copy()
    for method, group in sample_i.groupby("method", observed=True):
        by_run = group.groupby(["current_stratum", "heldout_run"], observed=True)["secondary_fraction"].mean().reset_index()
        obs_by_run = group.groupby(["current_stratum", "heldout_run"], observed=True)["observed_secondary_fraction"].mean().reset_index()
        def delta(frame: pd.DataFrame, col: str) -> float:
            high = frame.loc[frame["current_stratum"] == "high_20nA", col].to_numpy(dtype=float)
            low = frame.loc[frame["current_stratum"] == "low_2nA", col].to_numpy(dtype=float)
            if len(high) == 0 or len(low) == 0:
                return float("nan")
            return float(np.nanmean(high) - np.nanmean(low))
        pred_delta = delta(by_run, "secondary_fraction")
        obs_delta = delta(obs_by_run.rename(columns={"observed_secondary_fraction": "secondary_fraction"}), "secondary_fraction")
        high = by_run[by_run["current_stratum"] == "high_20nA"]["secondary_fraction"].to_numpy(dtype=float)
        low = by_run[by_run["current_stratum"] == "low_2nA"]["secondary_fraction"].to_numpy(dtype=float)
        boots = []
        for _ in range(int(config["bootstrap_iterations"])):
            boots.append(float(np.nanmean(high[rng.integers(0, len(high), len(high))]) - np.nanmean(low[rng.integers(0, len(low), len(low))])))
        out.append({"method": method, "predicted_high_minus_low_secondary_fraction": pred_delta, "observed_high_minus_low_secondary_fraction": obs_delta, "delta_error": pred_delta - obs_delta, "ci_low": float(np.quantile(boots, 0.025)), "ci_high": float(np.quantile(boots, 0.975)), "n_high_runs": int(len(high)), "n_low_runs": int(len(low))})
    return pd.DataFrame(out)


def action_atlas(rows: pd.DataFrame, summary: pd.DataFrame, secondary: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    merged = rows.merge(rows[rows["method"] == "traditional_empirical_template"][["row_id", "q_template_mse", "tail_mse", "live10_abs_error_ns", "timing_abs_error_ns", "secondary_abs_error"]].rename(columns={
        "q_template_mse": "trad_q_template_mse",
        "tail_mse": "trad_tail_mse",
        "live10_abs_error_ns": "trad_live10_abs_error_ns",
        "timing_abs_error_ns": "trad_timing_abs_error_ns",
        "secondary_abs_error": "trad_secondary_abs_error",
    }), on="row_id", how="left")
    atlas_rows = []
    for keys, group in merged.groupby(["method", "current_stratum", "saturation_bin", "amp_bin_label", "peak_phase_bin", "q_proxy_bin"], observed=True):
        if keys[0] == "traditional_empirical_template":
            continue
        rec = {
            "method": keys[0],
            "current_stratum": keys[1],
            "saturation_bin": keys[2],
            "amp_bin_label": keys[3],
            "peak_phase_bin": keys[4],
            "q_proxy_bin": keys[5],
            "n": int(len(group)),
            "n_runs": int(group["heldout_run"].nunique()),
        }
        rec["q_delta"] = float(np.nanmean(group["q_template_mse"] - group["trad_q_template_mse"]))
        rec["tail_delta"] = float(np.nanmean(group["tail_mse"] - group["trad_tail_mse"]))
        rec["live10_delta_ns"] = float(np.nanmean(group["live10_abs_error_ns"] - group["trad_live10_abs_error_ns"]))
        rec["timing_delta_ns"] = float(np.nanmean(group["timing_abs_error_ns"] - group["trad_timing_abs_error_ns"]))
        rec["secondary_error_delta"] = float(np.nanmean(group["secondary_abs_error"] - group["trad_secondary_abs_error"]))
        if rec["n"] < int(config["atlas_min_rows"]) or rec["n_runs"] < int(config["atlas_min_runs"]):
            rec["action_label"] = "diagnostic_only"
            rec["reason"] = "low_support"
        elif rec["q_delta"] < 0 and rec["tail_delta"] < 0 and rec["live10_delta_ns"] <= float(config["control_live10_tolerance_ns"]) and rec["timing_delta_ns"] <= float(config["control_timing_tolerance_ns"]) and rec["secondary_error_delta"] <= float(config["control_secondary_tolerance"]):
            rec["action_label"] = "accept"
            rec["reason"] = "reconstruction_and_controls_pass"
        elif rec["q_delta"] < 0 and rec["tail_delta"] < 0:
            rec["action_label"] = "diagnostic_only"
            rec["reason"] = "reconstruction_gain_control_failure"
        else:
            rec["action_label"] = "veto"
            rec["reason"] = "no_tail_reconstruction_gain"
        atlas_rows.append(rec)
    atlas = pd.DataFrame(atlas_rows)
    support = atlas.groupby(["method", "action_label"], observed=True)["n"].sum().reset_index()
    totals = atlas.groupby("method", observed=True)["n"].sum().rename("total").reset_index()
    support = support.merge(totals, on="method", how="left")
    support["support_fraction"] = support["n"] / support["total"]
    return atlas.sort_values(["method", "action_label", "current_stratum", "saturation_bin"]), support


def sentinel_false_pass(summary: pd.DataFrame, secondary: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
    sentinels = summary[summary["method"].isin(["sentinel_amplitude_only_ridge", "sentinel_run_only_ridge", "sentinel_shuffled_live10_ridge", "sentinel_shuffled_current_ridge"])].copy()
    trad = summary[summary["method"] == "traditional_empirical_template"].iloc[0]
    rows = []
    for row in sentinels.itertuples():
        pass_tail = float(row.tail_mse) <= float(trad.tail_mse)
        pass_live = float(row.live10_abs_error_ns) <= float(trad.live10_abs_error_ns)
        sec_row = secondary[secondary["method"] == row.method]
        pass_sec = bool(len(sec_row) and abs(float(sec_row.iloc[0]["delta_error"])) <= 0.025)
        rows.append({"sentinel": row.method, "passes_tail_mse": pass_tail, "passes_live10": pass_live, "passes_secondary_delta": pass_sec, "false_pass": bool(pass_tail and pass_live and pass_sec)})
    out = pd.DataFrame(rows)
    rate = float(out["false_pass"].mean()) if len(out) else float("nan")
    return out, rate


def write_plots(out_dir: Path, summary: pd.DataFrame, deltas: pd.DataFrame, support: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    plot = summary[~summary["method"].str.startswith("sentinel")].sort_values("tail_mse")
    ax.bar(plot["method"], plot["tail_mse"])
    ax.set_ylabel("tail MSE")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_tail_mse.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    sub = deltas[(deltas["metric"] == "tail_mse") & ~deltas["method"].str.startswith("sentinel")]
    ax.errorbar(sub["method"], sub["delta_vs_traditional"], yerr=[sub["delta_vs_traditional"] - sub["ci_low"], sub["ci_high"] - sub["delta_vs_traditional"]], fmt="o")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("tail MSE delta vs traditional")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_delta_ci.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    pivot = support.pivot(index="method", columns="action_label", values="support_fraction").fillna(0.0)
    pivot = pivot.loc[[i for i in pivot.index if not i.startswith("sentinel")]]
    pivot.plot(kind="bar", stacked=True, ax=ax)
    ax.set_ylabel("support fraction")
    ax.tick_params(axis="x", rotation=30, labelsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_action_support.png", dpi=140)
    plt.close(fig)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, summary: pd.DataFrame, deltas: pd.DataFrame, secondary: pd.DataFrame, atlas_support: pd.DataFrame, sentinels: pd.DataFrame, result: dict) -> None:
    nonsentinel = summary[~summary["method"].str.startswith("sentinel")].copy()
    winner = nonsentinel.sort_values(["tail_mse", "live10_abs_error_ns", "secondary_abs_error"]).iloc[0]
    head = nonsentinel[["method", "n_runs", "n_rows", "q_template_mse", "tail_mse", "timing_sigma68_ns", "live10_abs_error_ns", "tau_eff_abs_error_ns", "secondary_abs_error"]].copy()
    delta_tab = deltas[(deltas["metric"].isin(["q_template_mse", "tail_mse", "timing_sigma68_ns", "live10_abs_error_ns", "secondary_abs_error"])) & ~deltas["method"].str.startswith("sentinel")].copy()
    support_tab = atlas_support[~atlas_support["method"].str.startswith("sentinel")].copy()
    lines = [
        "# P10j: Tail-surrogate live-time control atlas",
        "",
        "- **Ticket:** `{}`".format(config["ticket_id"]),
        "- **Worker:** `{}`".format(config["worker"]),
        "- **Date:** 2026-06-11",
        "- **Input:** raw B-stack ROOT under `{}`".format(config["raw_root_dir"]),
        "- **Git commit:** `{}`".format(result["git_commit"]),
        "- **Config:** `{}`".format(result["config"]),
        "",
        "## 0. Question",
        "",
        "Where do learned tail surrogates improve aligned waveform reconstruction while failing live-time or pile-up-transfer controls, and which support cells should be accepted, retained only as diagnostics, or vetoed?",
        "",
        "The preregistered decision metric is a vector: q MSE, tail MSE, template-implied timing sigma68, live10/tau_eff transfer error, high-minus-low secondary-fraction transfer, accepted support fraction, control false-pass rate, and ML-minus-traditional run-block deltas. Lower is better for all loss metrics.",
        "",
        "## 1. Reproduction from raw ROOT",
        "",
        repro.to_markdown(index=False),
        "",
        "The selected-pulse count is rebuilt by reading `HRDv` from the raw B-stack ROOT files, subtracting the median of samples 0-3, and selecting B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC. The S10b live10 anchor is recomputed with the frozen S10c/S10b template script before any P10j model is scored.",
        "",
        "## 2. Methods",
        "",
        "Let `y_i(t)` be the CFD20-aligned, amplitude-normalized waveform on the grid `t in {-3,...,14}` samples. The full-waveform reconstruction loss is",
        "",
        "`qMSE_i(m) = |V_i|^{-1} sum_{t in V_i} (y_i(t) - yhat_{im}(t))^2`,",
        "",
        "and the tail loss is the same sum restricted to `t >= 2`. Timing is the robust width `sigma68 = (Q84(e_t) - Q16(e_t))/2` of `e_t = 10 ns * (CFD20(yhat) - CFD20(y))`. The live-time proxy is the last post-peak grid point above 10 percent of the normalized peak, and `tau_eff = live10 / ln(10)`. The secondary-fraction proxy is the positive late-tail excess, `max(sum_{t>=5} y(t) - 0.45 sum_{t>=2} y(t), 0) / sum_{t>=2} y(t)`. It is a waveform-control proxy, not pile-up truth.",
        "",
        "Traditional baseline: frozen empirical median templates binned by stave, amplitude, current stratum, and saturation proxy, with stave-amplitude and stave fallbacks. This is intentionally strong because it has explicit amplitude, asymmetric-tail, current, and saturation handles.",
        "",
        "ML/NN methods: ridge and gradient-boosted trees use local pulse scalars and one-hot stave/current features; the MLP uses the same tabular features; the 1D-CNN receives an aligned waveform with the tail (`t>=2`) knocked out plus the same tabular features; the new architecture is a live-time/control-gated CNN/GBT ensemble that falls back to the empirical template if the CNN/GBT live10 or secondary proxy moves too far from the empirical control.",
        "",
        "All primary methods are leave-one-run-out over the 21 analysis runs. Hyperparameters are fixed in the config. Confidence intervals are non-parametric bootstraps over held-out run blocks, preserving event pairing across methods.",
        "",
        "## 3. Head-to-head benchmark",
        "",
        head.to_markdown(index=False, floatfmt=".6g"),
        "",
        "ML-minus-traditional deltas with 95 percent run-block CIs:",
        "",
        delta_tab.to_markdown(index=False, floatfmt=".6g"),
        "",
        "The winner named in `result.json` is **{}** by the preregistered primary ordering: minimum tail MSE, then live10 error, then secondary-fraction error. Its tail MSE is {:.6g} with CI [{:.6g}, {:.6g}].".format(result["winner"], float(winner["tail_mse"]), float(winner["tail_mse_ci_low"]), float(winner["tail_mse_ci_high"])),
        "",
        "## 4. Live-time and pile-up transfer controls",
        "",
        secondary.to_markdown(index=False, floatfmt=".6g"),
        "",
        "The high-minus-low secondary-fraction table uses only Sample-I high-current and low-current held-out runs. This deliberately limits the control to the current contrast for which both a low and high current regime exist in the raw run plan.",
        "",
        "Sentinel false-pass audit:",
        "",
        sentinels.to_markdown(index=False),
        "",
        "The reported `control_false_pass_rate` is `{:.6g}`. A sentinel false pass means a deliberately impoverished or shuffled control met the same tail/live/secondary gates as a real model, so any action-label promotion must be treated cautiously.".format(float(result["control_false_pass_rate"])),
        "",
        "## 5. Action/support atlas",
        "",
        support_tab.to_markdown(index=False, floatfmt=".6g"),
        "",
        "Cells are labelled `accept` only when q and tail losses improve over the empirical baseline and live10, timing, and secondary-fraction controls do not worsen beyond the preregistered tolerances. Cells with reconstruction gain but control failure are `diagnostic_only`; cells without tail gain are `veto`.",
        "",
        "## 6. Systematics and caveats",
        "",
        "- Benchmark/selection: the empirical baseline has amplitude, current, saturation, and fallback handles; it is not a strawman. The control-gated ensemble is evaluated on the same held-out rows as the other methods.",
        "- Data leakage: folds exclude the held-out run before fitting templates or ML models. Primary feature sets exclude run id and event id. Run-only, amplitude-only, shuffled-live10, and shuffled-current models are labelled sentinels and excluded from winner selection.",
        "- Metric misuse: q/tail MSE and template-implied timing sigma68 are waveform-transfer metrics. They do not replace downstream same-particle timing closure. The secondary fraction is a late-tail proxy, not direct pile-up truth.",
        "- Post-hoc selection: method families, tolerances, run bootstrap, and action labels are fixed in the config. The new architecture is included because P10j explicitly asks for accept/diagnostic/veto support conversion.",
        "- Statistical precision: the low-current current-control side contains only two held-out runs, so high-minus-low secondary CIs are honest but coarse.",
        "",
        "## 7. Artifacts and reproducibility",
        "",
        "Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `method_summary.csv`, `method_delta_bootstrap.csv`, `secondary_transfer_bootstrap.csv`, `action_atlas.csv`, `action_support_summary.csv`, `sentinel_false_pass.csv`, `leakage_checks.csv`, `heldout_predictions.csv.gz`, `fold_summary.csv`, `input_sha256.csv`, and PNG figures.",
        "",
        "Reproduce with:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.py --config configs/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.json",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    table, aligned, _norm = p10a.collect_selected(config)
    table = add_strata(config, table, aligned)
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=float)
    sample_period = float(config["sample_period_ns"])
    obs_metrics = waveform_metrics(aligned, rel_grid, sample_period)
    repro, s10b_live10 = reproduction_gate(config, table)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("reproduction gate failed")

    eval_idx_all = stratified_eval_indices(config, table, rng)
    y_full = fill_target(aligned, np.arange(len(aligned)))
    pred_rows: List[dict] = []
    fold_rows: List[dict] = []
    leakage_key_overlap = 0
    feature_names: List[str] = []
    key_cols = ["run", "eventno", "evt", "stave"]

    X_nominal, feature_names = feature_matrix(config, table, "nominal")
    X_amp, amp_names = feature_matrix(config, table, "amplitude_only")
    X_run, run_names = feature_matrix(config, table, "run_only")

    for heldout in sorted(table.iloc[eval_idx_all]["run"].unique()):
        eval_idx = eval_idx_all[table.iloc[eval_idx_all]["run"].to_numpy() == heldout]
        train_idx = np.flatnonzero(table["run"].to_numpy() != int(heldout))
        fit_idx = train_idx.copy()
        if len(fit_idx) > int(config["max_train_rows_per_fold"]):
            fit_idx = rng.choice(fit_idx, int(config["max_train_rows_per_fold"]), replace=False)
        train_keys = set(map(tuple, table.iloc[train_idx][key_cols].to_numpy()))
        eval_keys = set(map(tuple, table.iloc[eval_idx][key_cols].to_numpy()))
        leakage_key_overlap += len(train_keys & eval_keys)

        trad_predict, n_templates = build_traditional_templates(config, table, aligned, train_idx)
        pred_trad = trad_predict(table.iloc[eval_idx])
        score_predictions(pred_rows, table, aligned, eval_idx, "traditional_empirical_template", pred_trad, obs_metrics, rel_grid, sample_period)

        method_preds: Dict[str, np.ndarray] = {}
        for family, X in [("ridge", X_nominal), ("gbt", X_nominal), ("mlp", X_nominal)]:
            model = fit_tabular(config, family, X[fit_idx], y_full[fit_idx])
            model.fit(X[fit_idx], y_full[fit_idx])
            pred = model.predict(X[eval_idx]).astype(np.float32)
            name = {"ridge": "ridge_tail_surrogate", "gbt": "gradient_boosted_trees_tail_surrogate", "mlp": "mlp_tail_surrogate"}[family]
            method_preds[name] = pred
            score_predictions(pred_rows, table, aligned, eval_idx, name, pred, obs_metrics, rel_grid, sample_period)

        cnn_predict, cnn_device = train_cnn(config, aligned, X_nominal, fit_idx, rng)
        pred_cnn = cnn_predict(eval_idx)
        method_preds["cnn_tail_knockout_surrogate"] = pred_cnn
        score_predictions(pred_rows, table, aligned, eval_idx, "cnn_tail_knockout_surrogate", pred_cnn, obs_metrics, rel_grid, sample_period)

        pred_gbt = method_preds["gradient_boosted_trees_tail_surrogate"]
        ensemble_raw = 0.5 * pred_cnn + 0.5 * pred_gbt
        met_trad = waveform_metrics(pred_trad, rel_grid, sample_period)
        met_ens = waveform_metrics(ensemble_raw, rel_grid, sample_period)
        gate = (np.abs(met_ens["live10_ns"].to_numpy(dtype=float) - met_trad["live10_ns"].to_numpy(dtype=float)) <= 10.0) & (np.abs(met_ens["secondary_fraction"].to_numpy(dtype=float) - met_trad["secondary_fraction"].to_numpy(dtype=float)) <= 0.10)
        pred_gated = np.where(gate[:, None], ensemble_raw, pred_trad).astype(np.float32)
        score_predictions(pred_rows, table, aligned, eval_idx, "control_gated_cnn_gbt_ensemble", pred_gated, obs_metrics, rel_grid, sample_period)

        # Sentinels are intentionally excluded from winner selection.
        for sentinel_name, Xsent in [("sentinel_amplitude_only_ridge", X_amp), ("sentinel_run_only_ridge", X_run)]:
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
            model.fit(Xsent[fit_idx], y_full[fit_idx])
            score_predictions(pred_rows, table, aligned, eval_idx, sentinel_name, model.predict(Xsent[eval_idx]).astype(np.float32), obs_metrics, rel_grid, sample_period)

        shuffled_live = obs_metrics.iloc[fit_idx]["live10_ns"].to_numpy(dtype=float).copy()
        finite_live = np.isfinite(shuffled_live)
        live_fill = float(np.nanmedian(shuffled_live[finite_live])) if finite_live.any() else float(config["expected_s10b_live10_ns"])
        shuffled_live = np.where(finite_live, shuffled_live, live_fill)
        rng.shuffle(shuffled_live)
        live_model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
        live_model.fit(X_nominal[fit_idx], shuffled_live)
        shuf_live = live_model.predict(X_nominal[eval_idx])
        pred_shuf_live = pred_trad.copy()
        # Encode a shuffled live-time sentinel by extending or shortening the empirical tail.
        for i, live in enumerate(shuf_live):
            trad_live = float(met_trad.loc[i, "live10_ns"])
            if np.isfinite(live) and np.isfinite(trad_live):
                factor = np.clip(live / max(trad_live, 1.0), 0.5, 1.8)
                pred_shuf_live[i, rel_grid >= 2] *= factor
        score_predictions(pred_rows, table, aligned, eval_idx, "sentinel_shuffled_live10_ridge", pred_shuf_live.astype(np.float32), obs_metrics, rel_grid, sample_period)

        shuffled_current = table.iloc[fit_idx]["current_stratum"].sample(frac=1.0, random_state=int(config["random_seed"]) + int(heldout)).to_numpy()
        tmp_train = table.iloc[fit_idx].copy()
        tmp_train["current_stratum"] = shuffled_current
        tmp_table = table.copy()
        tmp_table.loc[tmp_train.index, "current_stratum"] = tmp_train["current_stratum"]
        X_shuf, _ = feature_matrix(config, tmp_table, "nominal")
        shuf_model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
        shuf_model.fit(X_shuf[fit_idx], y_full[fit_idx])
        score_predictions(pred_rows, table, aligned, eval_idx, "sentinel_shuffled_current_ridge", shuf_model.predict(X_shuf[eval_idx]).astype(np.float32), obs_metrics, rel_grid, sample_period)

        fold_rows.append({"heldout_run": int(heldout), "n_eval": int(len(eval_idx)), "n_train_pool": int(len(train_idx)), "n_fit": int(len(fit_idx)), "traditional_templates": int(n_templates), "cnn_device": cnn_device, "control_gated_accept_fraction": float(np.mean(gate))})
        print("fold {} done n_eval={} n_fit={}".format(int(heldout), len(eval_idx), len(fit_idx)), flush=True)

    rows = pd.DataFrame(pred_rows)
    rows.to_csv(out_dir / "heldout_predictions.csv.gz", index=False, compression="gzip")
    pd.DataFrame(fold_rows).to_csv(out_dir / "fold_summary.csv", index=False)
    per_run, summary, deltas = run_summary(rows, config)
    per_run.to_csv(out_dir / "per_run_method_summary.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)
    secondary = secondary_bootstrap(rows, config)
    secondary.to_csv(out_dir / "secondary_transfer_bootstrap.csv", index=False)
    atlas, support = action_atlas(rows, summary, secondary, config)
    atlas.to_csv(out_dir / "action_atlas.csv", index=False)
    support.to_csv(out_dir / "action_support_summary.csv", index=False)
    sentinel, false_pass_rate = sentinel_false_pass(summary, secondary)
    sentinel.to_csv(out_dir / "sentinel_false_pass.csv", index=False)
    leakage = pd.DataFrame([{
        "heldout_absent_from_train": True,
        "train_eval_key_overlap": int(leakage_key_overlap),
        "primary_feature_names": ";".join(feature_names),
        "no_run_or_event_primary_features": bool(not any(name in {"run", "eventno", "evt"} for name in feature_names)),
        "sentinel_feature_names": "amplitude_only={};run_only={}".format(";".join(amp_names), ";".join(run_names[:5]) + ";..."),
        "control_false_pass_rate": float(false_pass_rate)
    }])
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_paths = [p10a.raw_file(config, run) for run in p10a.configured_runs(config)]
    inputs = [{"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_paths]
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(inputs)

    write_plots(out_dir, summary, deltas, support)
    nonsentinel = summary[~summary["method"].str.startswith("sentinel")].copy()
    winner_row = nonsentinel.sort_values(["tail_mse", "live10_abs_error_ns", "secondary_abs_error"]).iloc[0]
    winner = str(winner_row["method"])
    next_ticket = {
        "title": "P10o downstream timing closure for P10j accepted tail-surrogate cells",
        "body": "Question: do the P10j accepted support cells improve independent downstream same-particle timing and pile-up candidate stability when applied to B4/B6/B8 and B2-inclusive events? Traditional: freeze P10j empirical/action atlas and S02/S03 timing baselines. ML/NN: freeze the P10j winner and control-gated ensemble without refitting action labels. Metric: downstream sigma68/full RMS, >5 ns tail fraction, high-minus-low secondary proxy, and accepted-support harm rate with run-block bootstrap CIs. Expected information gain: tests whether P10j's template-implied accept cells survive a physics timing consumer rather than only waveform reconstruction."
    }
    runtime = time.time() - t0
    result = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "title": config["title"],
        "worker": config["worker"],
        "config": str(config_path),
        "git_commit": git_commit(),
        "runtime_sec": round(runtime, 3),
        "reproduced": bool(repro["pass"].all()),
        "s10b_anchor_recomputed_live10_ns": s10b_live10,
        "split": "leave-one-analysis-run-out with held-out run-block bootstrap confidence intervals",
        "bootstrap_iterations": int(config["bootstrap_iterations"]),
        "methods": sorted([m for m in rows["method"].unique() if not m.startswith("sentinel")]),
        "sentinels": sorted([m for m in rows["method"].unique() if m.startswith("sentinel")]),
        "winner": winner,
        "winner_rule": "lowest tail_mse among non-sentinel methods, then live10_abs_error_ns, then secondary_abs_error",
        "winner_metrics": json.loads(winner_row.to_json()),
        "control_false_pass_rate": float(false_pass_rate),
        "method_summary": json.loads(summary.to_json(orient="records")),
        "ml_minus_traditional_deltas": json.loads(deltas.to_json(orient="records")),
        "secondary_transfer": json.loads(secondary.to_json(orient="records")),
        "action_support_summary": json.loads(support.to_json(orient="records")),
        "leakage_audit": json.loads(leakage.iloc[0].to_json()),
        "next_tickets": [next_ticket]
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, config, repro, summary, deltas, secondary, support, sentinel, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "command": "/home/billy/anaconda3/bin/python scripts/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.py --config {}".format(config_path),
        "git_commit": result["git_commit"],
        "platform": platform.platform(),
        "python": platform.python_version(),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "script": "scripts/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.py",
        "script_sha256": sha256_file(ROOT / "scripts/p10j_1781061067_698_6c8a6921_tail_surrogate_live_time_control_atlas.py"),
        "support_scripts": [
            {"path": "scripts/p10a_conditional_template.py", "sha256": sha256_file(ROOT / "scripts/p10a_conditional_template.py")},
            {"path": "reports/1781007337.1308.7dc86005/s10c_threshold_scan_tau_eff.py", "sha256": sha256_file(ROOT / "reports/1781007337.1308.7dc86005/s10c_threshold_scan_tau_eff.py")}
        ],
        "inputs": inputs,
        "outputs": outputs,
        "random_seed": int(config["random_seed"])
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": winner, "runtime_sec": runtime}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
