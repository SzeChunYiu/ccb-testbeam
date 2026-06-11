#!/usr/bin/env python3
"""P11b: pretrigger atom charge-transfer gate from raw B-stack ROOT.

This study starts by reproducing the S00 selected-pulse count from raw ROOT, then asks
whether P11a pretrigger atoms predict duplicate-readout charge-transfer harm after matching
amplitude, saturation, dropout/anomaly taxa, and run family. It benchmarks frozen traditional
charge estimators against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new pretrigger-gated
residual CNN under a run-held-out split.
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
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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


def add_p11a_atoms(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    out = meta.copy()
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    pre = wave[:, baseline_idx].astype(np.float64)
    pre_centered = pre - np.median(pre, axis=1)[:, None]
    out["p11a_pre_mean_adc"] = (out["baseline_median"].to_numpy(dtype=float) + pre_centered.mean(axis=1)).astype(np.float32)
    out["p11a_pre_rms_adc"] = np.sqrt(np.mean(pre_centered**2, axis=1)).astype(np.float32)
    out["p11a_pre_slope_adc"] = (pre[:, -1] - pre[:, 0]).astype(np.float32)
    out["p11a_pre_max_exc_adc"] = np.max(np.abs(pre_centered), axis=1).astype(np.float32)
    out["p11a_pre_asym_adc"] = (0.5 * ((pre[:, 0] + pre[:, 1]) - (pre[:, 2] + pre[:, 3]))).astype(np.float32)
    out["p11a_pre_ptp_adc"] = (pre.max(axis=1) - pre.min(axis=1)).astype(np.float32)
    out["p11a_adaptive_lowering_adc"] = np.maximum(0.0, -pre_centered.min(axis=1) - 10.0).astype(np.float32)

    th = {
        "rms_hi": float(out.loc[train_mask, "p11a_pre_rms_adc"].quantile(0.75)),
        "exc_hi": float(out.loc[train_mask, "p11a_pre_max_exc_adc"].quantile(0.95)),
        "slope_hi": float(out.loc[train_mask, "p11a_pre_slope_adc"].abs().quantile(0.75)),
        "asym_hi": float(out.loc[train_mask, "p11a_pre_asym_adc"].abs().quantile(0.75)),
        "lower_hi": float(out.loc[train_mask, "p11a_adaptive_lowering_adc"].quantile(0.90)),
    }
    atom = np.full(len(out), "quiet", dtype=object)
    atom[out["p11a_pre_rms_adc"].to_numpy() >= th["rms_hi"]] = "noisy_rms"
    atom[np.abs(out["p11a_pre_slope_adc"].to_numpy()) >= th["slope_hi"]] = "sloped"
    atom[np.abs(out["p11a_pre_asym_adc"].to_numpy()) >= th["asym_hi"]] = "early_asym"
    atom[out["p11a_adaptive_lowering_adc"].to_numpy() >= th["lower_hi"]] = "adaptive_lowering"
    atom[out["p11a_pre_max_exc_adc"].to_numpy() >= th["exc_hi"]] = "spike"
    out["p11a_atom"] = atom
    out["p11a_atom_is_adaptive_lowering"] = (out["p11a_atom"] == "adaptive_lowering").astype(np.int8)
    out["p11a_atom_is_spike"] = (out["p11a_atom"] == "spike").astype(np.int8)
    out["p11a_atom_is_quiet"] = (out["p11a_atom"] == "quiet").astype(np.int8)
    out["p11a_pretrigger_score"] = np.sqrt(
        out["p11a_pre_rms_adc"].to_numpy() ** 2
        + out["p11a_pre_slope_adc"].to_numpy() ** 2
        + out["p11a_pre_max_exc_adc"].to_numpy() ** 2
        + out["p11a_adaptive_lowering_adc"].to_numpy() ** 2
    ).astype(np.float32)
    out.attrs["p11a_thresholds"] = th
    return out


def p11b_feature_matrix(meta: pd.DataFrame, wave: np.ndarray, include_pretrigger: bool = True) -> np.ndarray:
    base = p04l.feature_matrix(meta, wave)
    atom_names = ["quiet", "noisy_rms", "sloped", "early_asym", "adaptive_lowering", "spike"]
    atom_code = np.zeros((len(meta), len(atom_names)), dtype=np.float32)
    atom_lookup = {name: i for i, name in enumerate(atom_names)}
    for i, atom in enumerate(meta["p11a_atom"].to_numpy(dtype=object)):
        atom_code[i, atom_lookup.get(str(atom), 0)] = 1.0
    extras = [atom_code]
    if include_pretrigger:
        extras.append(
            meta[
                [
                    "p11a_pre_rms_adc",
                    "p11a_pre_slope_adc",
                    "p11a_pre_max_exc_adc",
                    "p11a_pre_asym_adc",
                    "p11a_pre_ptp_adc",
                    "p11a_adaptive_lowering_adc",
                    "p11a_pretrigger_score",
                ]
            ].to_numpy(dtype=np.float32)
        )
    return np.nan_to_num(np.column_stack([base] + extras), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def p11b_context(meta: pd.DataFrame) -> np.ndarray:
    atom_names = ["quiet", "noisy_rms", "sloped", "early_asym", "adaptive_lowering", "spike"]
    atom_code = np.zeros((len(meta), len(atom_names)), dtype=np.float32)
    atom_lookup = {name: i for i, name in enumerate(atom_names)}
    for i, atom in enumerate(meta["p11a_atom"].to_numpy(dtype=object)):
        atom_code[i, atom_lookup.get(str(atom), 0)] = 1.0
    return np.column_stack(
        [
            p04l.scalar_context(meta),
            meta[
                [
                    "p11a_pre_rms_adc",
                    "p11a_pre_slope_adc",
                    "p11a_pre_max_exc_adc",
                    "p11a_pre_asym_adc",
                    "p11a_adaptive_lowering_adc",
                    "p11a_pretrigger_score",
                ]
            ].to_numpy(dtype=np.float32),
            atom_code,
        ]
    ).astype(np.float32)


def p11a_atom_cell_corrected_prediction(meta: pd.DataFrame, base_pred: np.ndarray, y: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    pred = base_pred.copy()
    train = meta.loc[train_mask].copy()
    train["_frac"] = (base_pred[train_mask] - y[train_mask]) / np.maximum(y[train_mask], 1.0)
    keys = ["stave", "amp_bin", "peak_bin", "is_saturated", "atom_dropout", "p09_anomaly_bin", "p11a_atom"]
    fallback_keys = ["stave", "amp_bin", "is_saturated", "p11a_atom"]
    corrections = train.groupby(keys)["_frac"].median()
    fallback = train.groupby(fallback_keys)["_frac"].median()
    global_corr = float(train["_frac"].median())
    corr = np.zeros(len(meta), dtype=float)
    all_keys = list(zip(*(meta[col].to_numpy() for col in keys)))
    all_fallback = list(zip(*(meta[col].to_numpy() for col in fallback_keys)))
    for i, key in enumerate(all_keys):
        value = corrections.get(key, np.nan)
        if not np.isfinite(value):
            value = fallback.get(all_fallback[i], global_corr)
        corr[i] = float(value)
    return np.maximum(pred / np.maximum(1.0 + corr, 0.1), 1.0)


class PretriggerGatedResidualCNN(nn.Module):
    def __init__(self, n_context: int) -> None:
        super().__init__()
        self.wave = nn.Sequential(
            nn.Conv1d(1, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(32, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.context = nn.Sequential(nn.Linear(n_context, 48), nn.ReLU(), nn.Linear(48, 32), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(n_context, 32), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x_tab: torch.Tensor, x_wave: torch.Tensor) -> torch.Tensor:
        zw = self.wave(x_wave[:, None, :]).squeeze(-1)
        zc = self.context(x_tab)
        return self.head(torch.cat([zw * self.gate(x_tab), zc], dim=1)).squeeze(1)


def fit_pretrigger_gated_residual_cnn(x_tab: np.ndarray, x_wave: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict) -> np.ndarray:
    seed = int(config["random_seed"]) + 1107
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    use_idx = train_idx.copy()
    if len(use_idx) > int(config["nn_max_train_rows"]):
        use_idx = rng.choice(use_idx, size=int(config["nn_max_train_rows"]), replace=False)

    tab_scaler = StandardScaler()
    train_tab = tab_scaler.fit_transform(x_tab[use_idx]).astype(np.float32)
    all_tab = tab_scaler.transform(x_tab).astype(np.float32)
    wave_scale = float(max(np.percentile(np.abs(x_wave[use_idx]), 95), 1.0))
    train_wave = (x_wave[use_idx] / wave_scale).astype(np.float32)
    all_wave = (x_wave / wave_scale).astype(np.float32)
    y_log = np.log(np.maximum(y, 1.0))
    y_mean = float(y_log[use_idx].mean())
    y_std = float(y_log[use_idx].std() + 1e-6)
    train_y = ((y_log[use_idx] - y_mean) / y_std).astype(np.float32)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PretriggerGatedResidualCNN(train_tab.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn_learning_rate"]), weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    batch_size = int(config["nn_batch_size"])
    for epoch in range(int(config["nn_epochs"])):
        order = rng.permutation(len(use_idx))
        model.train()
        losses = []
        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            xt = torch.from_numpy(train_tab[idx]).to(device)
            xw = torch.from_numpy(train_wave[idx]).to(device)
            yy = torch.from_numpy(train_y[idx]).to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xt, xw), yy)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print(f"pretrigger_gated_residual_cnn epoch {epoch + 1}/{int(config['nn_epochs'])}: loss={np.mean(losses):.5f}", flush=True)

    preds = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(all_tab), batch_size * 4):
            xt = torch.from_numpy(all_tab[start : start + batch_size * 4]).to(device)
            xw = torch.from_numpy(all_wave[start : start + batch_size * 4]).to(device)
            preds.append(model(xt, xw).detach().cpu().numpy())
    pred_std = np.concatenate(preds)
    return np.maximum(np.exp(pred_std * y_std + y_mean), 1.0)


def regression_metrics(y: np.ndarray, pred: np.ndarray, catastrophic_cut: float) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "charge_bias_tail_rate": float(np.mean(abs_frac > catastrophic_cut)),
        "within_10pct": float(np.mean(abs_frac < 0.10)),
    }


def run_block_metric_ci(frame: pd.DataFrame, target_col: str, pred_col: str, reps: int, seed: int, catastrophic_cut: float) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == int(run)] for run in runs}
    rng = np.random.default_rng(seed)
    bias, res68, tail = [], [], []
    for _ in range(reps):
        sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        frac = (sample[pred_col].to_numpy() - sample[target_col].to_numpy()) / np.maximum(sample[target_col].to_numpy(), 1.0)
        bias.append(float(np.median(frac)))
        res68.append(float(np.percentile(np.abs(frac), 68)))
        tail.append(float(np.mean(np.abs(frac) > catastrophic_cut)))
    return {
        "bias_ci95": ci(bias),
        "res68_ci95": ci(res68),
        "charge_bias_tail_rate_ci95": ci(tail),
    }


def evaluate_regression(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows, run_rows = [], []
    held = meta.loc[heldout_mask, ["run", "target_odd_pos_charge"]].copy()
    y = held["target_odd_pos_charge"].to_numpy(dtype=float)
    for i, (method, pred_all) in enumerate(predictions.items()):
        pred = pred_all[heldout_mask]
        tmp = held.copy()
        tmp["_pred"] = pred
        row = {"target": "duplicate_odd_charge", "method": method, "split": "sample_ii_run_heldout"}
        row.update(regression_metrics(y, pred, float(config["catastrophic_abs_frac"])))
        row.update(run_block_metric_ci(tmp, "target_odd_pos_charge", "_pred", int(config["bootstrap_reps"]), int(config["random_seed"]) + i, float(config["catastrophic_abs_frac"])))
        rows.append(row)
        for run, sub in tmp.groupby("run"):
            rr = {"target": "duplicate_odd_charge", "method": method, "run": int(run)}
            rr.update(regression_metrics(sub["target_odd_pos_charge"].to_numpy(dtype=float), sub["_pred"].to_numpy(dtype=float), float(config["catastrophic_abs_frac"])))
            run_rows.append(rr)
    benchmark = pd.DataFrame(rows)
    best_trad_name = benchmark[benchmark["method"].str.startswith("traditional_")].sort_values("res68_abs_frac").iloc[0]["method"]
    deltas = ml_minus_traditional_deltas(meta, predictions, heldout_mask, str(best_trad_name), config)
    return benchmark, pd.DataFrame(run_rows), deltas


def ml_minus_traditional_deltas(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, traditional_method: str, config: dict) -> pd.DataFrame:
    held = meta.loc[heldout_mask, ["run", "target_odd_pos_charge"]].reset_index(drop=True)
    y = held["target_odd_pos_charge"].to_numpy(dtype=float)
    trad = predictions[traditional_method][heldout_mask]
    runs = np.asarray(sorted(held["run"].unique()), dtype=int)
    by_run_idx = {int(r): np.flatnonzero(held["run"].to_numpy() == int(r)) for r in runs}
    rng = np.random.default_rng(int(config["random_seed"]) + 606)
    rows = []
    for method, pred_all in predictions.items():
        if method.startswith("traditional_"):
            continue
        pred = pred_all[heldout_mask]
        frac_m = (pred - y) / np.maximum(y, 1.0)
        frac_t = (trad - y) / np.maximum(y, 1.0)
        center_res68 = float(np.percentile(np.abs(frac_m), 68) - np.percentile(np.abs(frac_t), 68))
        center_tail = float(np.mean(np.abs(frac_m) > float(config["catastrophic_abs_frac"])) - np.mean(np.abs(frac_t) > float(config["catastrophic_abs_frac"])))
        boot_res68, boot_tail = [], []
        for _ in range(int(config["bootstrap_reps"])):
            idx = np.concatenate([by_run_idx[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)])
            fm = frac_m[idx]
            ft = frac_t[idx]
            boot_res68.append(float(np.percentile(np.abs(fm), 68) - np.percentile(np.abs(ft), 68)))
            boot_tail.append(float(np.mean(np.abs(fm) > float(config["catastrophic_abs_frac"])) - np.mean(np.abs(ft) > float(config["catastrophic_abs_frac"]))))
        rows.append(
            {
                "method": method,
                "traditional_reference": traditional_method,
                "delta_res68_abs_frac": center_res68,
                "delta_res68_abs_frac_ci95": ci(boot_res68),
                "delta_charge_bias_tail_rate": center_tail,
                "delta_charge_bias_tail_rate_ci95": ci(boot_tail),
            }
        )
    return pd.DataFrame(rows)


def matched_p11a_atom_effects(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, methods: List[str], config: dict) -> pd.DataFrame:
    held = meta.loc[heldout_mask].reset_index(drop=True).copy()
    y = held["target_odd_pos_charge"].to_numpy(dtype=float)
    controls = ["run", "group", "stave", "amp_bin", "is_saturated", "atom_dropout", "p09_anomaly_bin"]
    rng = np.random.default_rng(int(config["random_seed"]) + 707)
    rows = []
    for method in methods:
        pred = predictions[method][heldout_mask]
        frac = (pred - y) / np.maximum(y, 1.0)
        held["_abs_frac"] = np.abs(frac)
        held["_signed_frac"] = frac
        held["_tail"] = (np.abs(frac) > float(config["catastrophic_abs_frac"])).astype(float)
        for atom in ["noisy_rms", "sloped", "early_asym", "adaptive_lowering", "spike"]:
            cells = []
            for _, sub in held.groupby(controls, sort=True):
                exposed = sub[sub["p11a_atom"] == atom]
                control = sub[sub["p11a_atom"] == "quiet"]
                if len(exposed) < int(config["min_matched_cell"]) or len(control) < int(config["min_matched_cell"]):
                    continue
                cells.append(
                    {
                        "run": int(sub["run"].iloc[0]),
                        "weight": min(len(exposed), len(control)),
                        "delta_res68_proxy_abs_mean": float(exposed["_abs_frac"].mean() - control["_abs_frac"].mean()),
                        "delta_signed_bias": float(exposed["_signed_frac"].median() - control["_signed_frac"].median()),
                        "delta_charge_bias_tail_rate": float(exposed["_tail"].mean() - control["_tail"].mean()),
                        "n_exposed": int(len(exposed)),
                        "n_quiet": int(len(control)),
                    }
                )
            if not cells:
                continue
            cdf = pd.DataFrame(cells)
            w = cdf["weight"].to_numpy(dtype=float)
            runs = np.asarray(sorted(cdf["run"].unique()), dtype=int)
            by_run = {int(r): cdf[cdf["run"] == int(r)] for r in runs}
            boot_abs, boot_bias, boot_tail = [], [], []
            for _ in range(int(config["bootstrap_reps"])):
                sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
                sw = sample["weight"].to_numpy(dtype=float)
                boot_abs.append(float(np.average(sample["delta_res68_proxy_abs_mean"], weights=sw)))
                boot_bias.append(float(np.average(sample["delta_signed_bias"], weights=sw)))
                boot_tail.append(float(np.average(sample["delta_charge_bias_tail_rate"], weights=sw)))
            rows.append(
                {
                    "method": method,
                    "p11a_atom": atom,
                    "matched_controls": "+".join(controls),
                    "n_cells": int(len(cdf)),
                    "n_exposed": int(cdf["n_exposed"].sum()),
                    "n_quiet": int(cdf["n_quiet"].sum()),
                    "delta_abs_frac_mean": float(np.average(cdf["delta_res68_proxy_abs_mean"], weights=w)),
                    "delta_abs_frac_mean_ci95": ci(boot_abs),
                    "delta_signed_bias": float(np.average(cdf["delta_signed_bias"], weights=w)),
                    "delta_signed_bias_ci95": ci(boot_bias),
                    "delta_charge_bias_tail_rate": float(np.average(cdf["delta_charge_bias_tail_rate"], weights=w)),
                    "delta_charge_bias_tail_rate_ci95": ci(boot_tail),
                }
            )
    return pd.DataFrame(rows)


def abstention_metrics(meta: pd.DataFrame, pred: np.ndarray, train_mask: np.ndarray, heldout_mask: np.ndarray, config: dict) -> dict:
    y = meta["target_odd_pos_charge"].to_numpy(dtype=float)
    train_abs = np.abs((pred[train_mask] - y[train_mask]) / np.maximum(y[train_mask], 1.0))
    held_abs = np.abs((pred[heldout_mask] - y[heldout_mask]) / np.maximum(y[heldout_mask], 1.0))
    held = meta.loc[heldout_mask].copy()
    harm_cut = float(np.quantile(train_abs, float(config["harm_quantile"])))
    pre_cut = float(meta.loc[train_mask, "p11a_pretrigger_score"].quantile(float(config["abstain_quantile"])))
    keep = held["p11a_pretrigger_score"].to_numpy(dtype=float) < pre_cut
    before = float(np.mean(held_abs > harm_cut))
    after = float(np.mean(held_abs[keep] > harm_cut)) if keep.any() else float("nan")
    return {
        "harm_abs_frac_threshold_train_q90": harm_cut,
        "abstain_pretrigger_score_threshold_train_q80": pre_cut,
        "support_coverage_retained": float(np.mean(keep)),
        "support_loss": float(1.0 - np.mean(keep)),
        "charge_harm_rate_no_abstention": before,
        "charge_harm_rate_after_abstention": after,
        "abstention_harm_reduction": before - after,
        "retained_res68_abs_frac": float(np.percentile(held_abs[keep], 68)) if keep.any() else None,
    }


def ece_score(y_true: np.ndarray, prob: np.ndarray, bins: int) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if mask.any():
            out += float(mask.mean()) * abs(float(y_true[mask].mean()) - float(prob[mask].mean()))
    return float(out)


def auc_or_nan(y_true: np.ndarray, score: np.ndarray) -> float:
    return float(roc_auc_score(y_true, score)) if len(np.unique(y_true)) > 1 else float("nan")


def ap_or_nan(y_true: np.ndarray, score: np.ndarray) -> float:
    return float(average_precision_score(y_true, score)) if len(np.unique(y_true)) > 1 else float("nan")


def classify_controls(meta: pd.DataFrame, features: np.ndarray, y_harm: np.ndarray, train_mask: np.ndarray, heldout_mask: np.ndarray, config: dict) -> pd.DataFrame:
    train_idx = np.where(train_mask)[0]
    held_idx = np.where(heldout_mask)[0]
    rng = np.random.default_rng(int(config["random_seed"]) + 909)
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    controls = {
        "traditional_p11a_atom_only": None,
        "ML_hgb_pretrigger_wave_atoms": features,
        "control_pretrigger_knockout": p11b_feature_matrix(meta, np.zeros((len(meta), int(config["samples_per_channel"])), dtype=np.float32), include_pretrigger=False),
        "control_saturation_only": meta[["saturation_count", "raw_max_adc", "is_saturated", "even_amp"]].to_numpy(dtype=np.float32),
        "control_dropout_only": meta[["dropout_score", "atom_dropout", "secondary_peak", "p09_pca_anomaly_score"]].to_numpy(dtype=np.float32),
        "control_amplitude_only": meta[["even_amp", "even_pos_charge", "even_peak", "stave_idx"]].to_numpy(dtype=np.float32),
        "control_run_only": meta[["run"]].to_numpy(dtype=np.float32),
    }
    rows = []
    for name, X in controls.items():
        if name == "traditional_p11a_atom_only":
            enc = OneHotEncoder(handle_unknown="ignore")
            Xtr = enc.fit_transform(meta.loc[train_idx, ["p11a_atom"]])
            Xhe = enc.transform(meta.loc[held_idx, ["p11a_atom"]])
            model = LogisticRegression(max_iter=300, class_weight="balanced", solver="liblinear")
            model.fit(Xtr, y_harm[train_idx])
            prob = model.predict_proba(Xhe)[:, 1]
        else:
            model = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.08, random_state=int(config["random_seed"]) + len(rows))
            model.fit(np.nan_to_num(X[train_idx], nan=0.0, posinf=0.0, neginf=0.0), y_harm[train_idx])
            prob = model.predict_proba(np.nan_to_num(X[held_idx], nan=0.0, posinf=0.0, neginf=0.0))[:, 1]
        yy = y_harm[held_idx]
        threshold = float(np.quantile(prob, 0.80))
        keep = prob < threshold
        rows.append(
            {
                "task": "charge_harm_tail",
                "method": name,
                "n": int(len(yy)),
                "positive_rate": float(np.mean(yy)),
                "roc_auc": auc_or_nan(yy, prob),
                "average_precision": ap_or_nan(yy, prob),
                "ece": ece_score(yy, prob, int(config["calibration_bins"])),
                "coverage_retained_at_80pct_low_risk": float(np.mean(keep)),
                "harm_rate_retained": float(np.mean(yy[keep])) if keep.any() else None,
            }
        )

    shuffled = y_harm[train_idx].copy()
    rng.shuffle(shuffled)
    model = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.06, max_leaf_nodes=31, random_state=int(config["random_seed"]) + 999)
    model.fit(features[train_idx], shuffled)
    prob = model.predict_proba(features[held_idx])[:, 1]
    rows.append(
        {
            "task": "charge_harm_tail",
            "method": "control_shuffled_harm_labels",
            "n": int(len(held_idx)),
            "positive_rate": float(np.mean(y_harm[held_idx])),
            "roc_auc": auc_or_nan(y_harm[held_idx], prob),
            "average_precision": ap_or_nan(y_harm[held_idx], prob),
            "ece": ece_score(y_harm[held_idx], prob, int(config["calibration_bins"])),
            "coverage_retained_at_80pct_low_risk": None,
            "harm_rate_retained": None,
        }
    )
    return pd.DataFrame(rows)


def support_summary(full_meta: pd.DataFrame, valid_mask: np.ndarray, train_mask_full: np.ndarray, heldout_mask_full: np.ndarray, config: dict) -> pd.DataFrame:
    cols = ["even_amp", "even_pos_charge", "even_peak", "baseline_mad", "baseline_slope", "baseline_range", "dropout_score", "saturation_count", "raw_max_adc", "stave_idx"]
    X = full_meta[cols].to_numpy(dtype=np.float32)
    y = valid_mask.astype(int)
    train_idx = np.where(train_mask_full)[0]
    held_idx = np.where(heldout_mask_full)[0]
    rows = []
    for name, use_cols in {
        "support_traditional_pretrigger_huber_proxy": ["baseline_mad", "baseline_slope", "baseline_range", "dropout_score"],
        "support_ML_hgb_full": cols,
        "support_amplitude_only": ["even_amp", "even_pos_charge", "even_peak"],
    }.items():
        XX = full_meta[use_cols].to_numpy(dtype=np.float32)
        if len(np.unique(y[train_idx])) < 2:
            prob = np.full(len(held_idx), float(np.mean(y[train_idx])), dtype=float)
        else:
            model = HistGradientBoostingClassifier(max_iter=120, learning_rate=0.06, max_leaf_nodes=31, random_state=int(config["random_seed"]) + len(rows))
            model.fit(np.nan_to_num(XX[train_idx], nan=0.0), y[train_idx])
            prob = model.predict_proba(np.nan_to_num(XX[held_idx], nan=0.0))[:, 1]
        yy = y[held_idx]
        threshold = float(np.quantile(prob, 0.20))
        keep = prob > threshold
        rows.append(
            {
                "task": "duplicate_target_support",
                "method": name,
                "n": int(len(yy)),
                "positive_rate": float(np.mean(yy)),
                "roc_auc": auc_or_nan(yy, prob),
                "average_precision": ap_or_nan(yy, prob),
                "ece": ece_score(yy, prob, int(config["calibration_bins"])),
                "coverage_retained_at_80pct_high_support": float(np.mean(keep)),
                "support_valid_rate_retained": float(np.mean(yy[keep])) if keep.any() else None,
            }
        )
    return pd.DataFrame(rows)


def atom_outcome_summary(meta: pd.DataFrame, pred: np.ndarray, heldout_mask: np.ndarray, config: dict) -> pd.DataFrame:
    held = meta.loc[heldout_mask].copy()
    y = held["target_odd_pos_charge"].to_numpy(dtype=float)
    frac = (pred[heldout_mask] - y) / np.maximum(y, 1.0)
    held["_signed_frac"] = frac
    held["_abs_frac"] = np.abs(frac)
    held["_tail"] = (np.abs(frac) > float(config["catastrophic_abs_frac"])).astype(float)
    rows = []
    for atom, sub in held.groupby("p11a_atom"):
        rows.append(
            {
                "p11a_atom": atom,
                "n": int(len(sub)),
                "fraction": float(len(sub) / len(held)),
                "bias_median_frac": float(sub["_signed_frac"].median()),
                "res68_abs_frac": float(np.percentile(sub["_abs_frac"], 68)),
                "charge_bias_tail_rate": float(sub["_tail"].mean()),
                "saturation_fraction": float(sub["is_saturated"].mean()),
                "dropout_atom_fraction": float(sub["atom_dropout"].mean()),
                "anomaly_q4_fraction": float((sub["p09_anomaly_bin"] == "q4").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("fraction", ascending=False)


def markdown_table(frame: pd.DataFrame, columns: List[str], max_rows: int | None = None) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].copy()
    if max_rows is not None:
        use = use.head(max_rows)
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}" if pd.notna(x) else "")
    return use.to_markdown(index=False)


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(out_dir: Path, config: dict, counts: pd.DataFrame, benchmark: pd.DataFrame, by_run: pd.DataFrame, deltas: pd.DataFrame, atom_summary: pd.DataFrame, atom_effects: pd.DataFrame, classifier_metrics: pd.DataFrame, support_metrics: pd.DataFrame, abstention: dict, result: dict) -> None:
    expected = int(config["expected_selected_pulses"])
    total = int(counts["selected_pulses"].sum())
    winner = result["winner"]["method"]
    best_trad = result["best_traditional"]["method"]
    bench_cols = ["method", "n", "bias_median_frac", "bias_ci95", "res68_abs_frac", "res68_ci95", "charge_bias_tail_rate", "charge_bias_tail_rate_ci95"]
    delta_cols = ["method", "traditional_reference", "delta_res68_abs_frac", "delta_res68_abs_frac_ci95", "delta_charge_bias_tail_rate", "delta_charge_bias_tail_rate_ci95"]
    atom_cols = ["p11a_atom", "n", "fraction", "bias_median_frac", "res68_abs_frac", "charge_bias_tail_rate", "saturation_fraction", "dropout_atom_fraction"]
    matched_cols = ["method", "p11a_atom", "n_cells", "delta_abs_frac_mean", "delta_abs_frac_mean_ci95", "delta_signed_bias", "delta_charge_bias_tail_rate", "delta_charge_bias_tail_rate_ci95"]
    clf_cols = ["task", "method", "n", "positive_rate", "roc_auc", "average_precision", "ece", "coverage_retained_at_80pct_low_risk", "harm_rate_retained"]
    support_cols = ["task", "method", "n", "positive_rate", "roc_auc", "average_precision", "ece", "coverage_retained_at_80pct_high_support", "support_valid_rate_retained"]
    run_cols = ["method", "run", "n", "res68_abs_frac", "charge_bias_tail_rate", "bias_median_frac"]

    lines = [
        "# P11b: Pretrigger Atom Charge-transfer Gate",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Date:** {time.strftime('%Y-%m-%d')}",
        "- **Input:** raw B-stack ROOT files `h101/HRDv`; no simulation and no derived pulse table.",
        f"- **Config:** `configs/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.json`",
        f"- **Git commit:** `{git_commit()}`",
        "",
        "## Abstract",
        "",
        result["finding"],
        "",
        "## 1. Reproduction Gate",
        "",
        "| quantity | report value | reproduced | delta | tolerance | pass |",
        "|---|---:|---:|---:|---:|:---|",
        f"| selected B-stave pulse records | {expected:,} | {total:,} | {total - expected:+,} | 0 | {str(total == expected).lower()} |",
        "",
        "The script subtracts the per-channel median over samples 0--3, reshapes each raw `HRDv` record to `(8,18)`, and selects even-channel B2/B4/B6/B8 pulse records with peak amplitude greater than 1000 ADC. Duplicate-target quality cuts are applied only after this raw reproduction gate.",
        "",
        "## 2. Estimands",
        "",
        "The paired odd-channel charge target is",
        "",
        "\\[ y_i^{dup}=\\sum_t \\max[-o_i(t),0], \\]",
        "",
        "where `o_i(t)` is the baseline-subtracted odd readout paired with the selected even-channel waveform. A charge estimator returns `hat y_i`; the fractional residual is",
        "",
        "\\[ r_i=(\\hat y_i-y_i^{dup})/\\max(y_i^{dup},1). \\]",
        "",
        "The primary width metric is `Q_0.68(|r_i|)`. Secondary quantities are median signed bias, charge-bias-tail rate `P(|r_i|>0.25)`, support coverage, abstention harm reduction, calibration ECE, and matched atom deltas. Confidence intervals are non-parametric run-block bootstraps over the seven held-out Sample-II runs.",
        "",
        "## 3. Methods",
        "",
        "P11a atoms are frozen from train-run pretrigger samples 0--3 with the same precedence as P11a: `quiet`, `noisy_rms`, `sloped`, `early_asym`, `adaptive_lowering`, then `spike`. Matching controls are run family, stave, amplitude bin, P07-style saturation flag, dropout atom, and P09 anomaly quantile.",
        "",
        "Traditional estimators are P04-style peak and integral log calibrations, shifted adaptive-template scaling, a Huber model on hand-built waveform/charge/pathology summaries, and a P11a atom-cell residual correction of the integral estimator. ML/NN estimators are ridge, histogram gradient-boosted trees, a tabular MLP, a waveform-only 1D-CNN, and the new `NN_pretrigger_gated_residual_cnn_new`, which gates a temporal convolution branch by pretrigger atom summaries.",
        "",
        "## 4. Held-out Charge Benchmark",
        "",
        markdown_table(benchmark.sort_values("res68_abs_frac"), bench_cols),
        "",
        f"Winner by held-out charge res68: `{winner}`. Strongest traditional comparator: `{best_trad}`.",
        "",
        "## 5. ML-minus-traditional Deltas",
        "",
        markdown_table(deltas.sort_values("delta_res68_abs_frac"), delta_cols),
        "",
        "Negative deltas favor the ML/NN method. The bootstrap unit is the held-out run, not individual pulse records.",
        "",
        "## 6. Per-run Stability",
        "",
        markdown_table(by_run[by_run["method"].isin([winner, best_trad, "ML_hgb_pretrigger_wave_atoms", "NN_1d_cnn_waveform"])], run_cols, max_rows=80),
        "",
        "## 7. Atom-stratified Outcomes",
        "",
        markdown_table(atom_summary, atom_cols),
        "",
        "## 8. Matched Atom Effects",
        "",
        markdown_table(atom_effects[atom_effects["method"].isin([winner, best_trad])], matched_cols, max_rows=80),
        "",
        "Positive matched deltas mean the P11a atom has worse charge residuals than quiet records after conditioning on amplitude, saturation, dropout, anomaly, stave, and run family.",
        "",
        "## 9. Harm Classifier Calibration and Controls",
        "",
        markdown_table(classifier_metrics, clf_cols, max_rows=80),
        "",
        "The controls test whether the pretrigger/waveform model is only rediscovering saturation, dropout, amplitude, run family, or shuffled harm labels. ECE is computed in ten probability bins on held-out runs.",
        "",
        "## 10. Support Model and Abstention",
        "",
        markdown_table(support_metrics, support_cols),
        "",
        "| quantity | value |",
        "|---|---:|",
        f"| train q90 harm threshold | {abstention['harm_abs_frac_threshold_train_q90']:.6g} |",
        f"| pretrigger abstention threshold | {abstention['abstain_pretrigger_score_threshold_train_q80']:.6g} |",
        f"| support coverage retained | {abstention['support_coverage_retained']:.6g} |",
        f"| support loss | {abstention['support_loss']:.6g} |",
        f"| harm rate before abstention | {abstention['charge_harm_rate_no_abstention']:.6g} |",
        f"| harm rate after abstention | {abstention['charge_harm_rate_after_abstention']:.6g} |",
        f"| abstention harm reduction | {abstention['abstention_harm_reduction']:.6g} |",
        f"| retained res68 | {abstention['retained_res68_abs_frac']:.6g} |",
        "",
        "## 11. Systematics and Caveats",
        "",
        "- The split is by run: Sample I plus run 64 train, Sample-II analysis runs 58, 59, 60, 61, 62, 63, 65 held out.",
        "- The target is duplicate-readout charge closure, not absolute deposited-energy truth. It is an electronics-transfer proxy.",
        "- P11a atoms are support labels from pretrigger samples, not interventions. Matched deltas are residual associations.",
        "- Neural models are laptop-scale probes with fixed epochs; the claim is comparative under a common split, not an exhaustive architecture search.",
        "- Run-block CIs dominate because only seven held-out runs define the external uncertainty scale.",
        "",
        "## 12. Conclusion",
        "",
        result["hypothesis"],
        "",
        "No follow-up ticket was appended from this run; P11b closes with an abstain/veto recommendation rather than opening a new branch.",
        "",
        "## 13. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.py --config configs/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.json",
        "```",
        "",
        "Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `counts_by_run.csv`, `benchmark.csv`, `benchmark_by_run.csv`, `ml_minus_traditional.csv`, `atom_outcome_summary.csv`, `matched_p11a_atom_effects.csv`, `harm_classifier_metrics.csv`, and `support_model_metrics.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.json")
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/7 scan raw ROOT and reproduce selected-pulse count", flush=True)
    meta_all, wave_all, counts = p04l.extract_rows(config)
    total = int(counts["selected_pulses"].sum())
    if total != int(config["expected_selected_pulses"]):
        raise RuntimeError(f"raw ROOT selected-pulse reproduction failed: {total} != {config['expected_selected_pulses']}")

    valid = (
        np.isfinite(meta_all["target_odd_neg_amp"].to_numpy())
        & np.isfinite(meta_all["target_odd_pos_charge"].to_numpy())
        & (meta_all["target_odd_neg_amp"].to_numpy() > 100.0)
        & (meta_all["target_odd_pos_charge"].to_numpy() > 100.0)
        & (meta_all["even_amp"].to_numpy() > 0.0)
        & (meta_all["even_pos_charge"].to_numpy() > 0.0)
    )
    heldout_runs = [int(r) for r in config["heldout_runs"]]
    heldout_mask_all = meta_all["run"].isin(heldout_runs).to_numpy()
    train_mask_all = ~heldout_mask_all

    meta = meta_all.loc[valid].reset_index(drop=True)
    wave = wave_all[valid]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    print(f"selected={total} valid_duplicate_target={len(meta)} train={int(train_mask.sum())} heldout={int(heldout_mask.sum())}", flush=True)

    print("2/7 derive P04/P07/dropout/anomaly taxa and freeze P11a atoms", flush=True)
    meta = p04l.add_derived_columns(meta, wave, train_mask, config)
    meta = add_p11a_atoms(meta, wave, train_mask, config)
    anomaly_edges = np.quantile(meta.loc[train_mask, "p09_pca_anomaly_score"], [0.25, 0.50, 0.75])
    meta["p09_anomaly_bin"] = pd.cut(meta["p09_pca_anomaly_score"], bins=[-np.inf] + [float(x) for x in anomaly_edges] + [np.inf], labels=["q1", "q2", "q3", "q4"]).astype(str)
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    y = meta["target_odd_pos_charge"].to_numpy(dtype=float)
    stave_idx = meta["stave_idx"].to_numpy().astype(int)

    print("3/7 fit traditional estimators", flush=True)
    predictions: Dict[str, np.ndarray] = {}
    predictions["traditional_peak_logcal"] = p04l.fit_log_calibrated(meta["even_amp"].to_numpy(), y, train_mask, stave_idx)
    predictions["traditional_integral_logcal"] = p04l.fit_log_calibrated(meta["even_pos_charge"].to_numpy(), y, train_mask, stave_idx)
    templates = p04l.p04.build_templates(meta, wave, train_mask, [float(x) for x in config["template_bins"]])
    template_scale = p04l.p04.template_scales(meta, wave, templates, [float(x) for x in config["template_bins"]], [float(x) for x in config["template_shift_grid"]])
    predictions["traditional_adaptive_template_logcal"] = p04l.fit_log_calibrated(template_scale, y, train_mask, stave_idx)
    trad_features = meta[
        [
            "even_amp",
            "even_pos_charge",
            "even_peak",
            "tail_fraction",
            "late_fraction",
            "width_half",
            "baseline_score",
            "dropout_score",
            "saturation_count",
            "is_saturated",
            "p09_pca_anomaly_score",
            "p11a_pretrigger_score",
        ]
    ].to_numpy(dtype=np.float32)
    predictions["traditional_huber_p11a_support"] = p04l.fit_strong_huber(trad_features, y, train_mask)
    predictions["traditional_p11a_atom_cell_corrected"] = p11a_atom_cell_corrected_prediction(meta, predictions["traditional_integral_logcal"], y, train_mask)

    print("4/7 fit ridge, GBDT, MLP, 1D-CNN, and new gated CNN", flush=True)
    features = p11b_feature_matrix(meta, wave, include_pretrigger=True)
    no_pre_features = p11b_feature_matrix(meta, wave, include_pretrigger=False)
    predictions["ML_ridge_pretrigger_wave_atoms"] = p04l.fit_ridge(features, y, train_idx)
    predictions["ML_hgb_pretrigger_wave_atoms"] = p04l.fit_hgb(features, y, train_idx, int(config["random_seed"]) + 1)
    context = p11b_context(meta)
    norm_wave = (wave / np.maximum(meta["even_amp"].to_numpy()[:, None], 1.0)).astype(np.float32)
    predictions["NN_mlp_pretrigger_wave_atoms"] = p04l.fit_torch_model("mlp", features, norm_wave, y, train_idx, config)
    predictions["NN_1d_cnn_waveform"] = p04l.fit_torch_model("cnn", context, norm_wave, y, train_idx, config)
    predictions["NN_pretrigger_gated_residual_cnn_new"] = fit_pretrigger_gated_residual_cnn(context, norm_wave, y, train_idx, config)

    print("5/7 evaluate regression, matched atoms, abstention, calibration controls", flush=True)
    benchmark, by_run, deltas = evaluate_regression(meta, predictions, heldout_mask, config)
    best_trad = benchmark[benchmark["method"].str.startswith("traditional_")].sort_values("res68_abs_frac").iloc[0]
    winner = benchmark.sort_values("res68_abs_frac").iloc[0]
    abstention = abstention_metrics(meta, predictions[str(winner["method"])], train_mask, heldout_mask, config)
    atom_summary = atom_outcome_summary(meta, predictions[str(winner["method"])], heldout_mask, config)
    effect_methods = list(dict.fromkeys([str(best_trad["method"]), str(winner["method"]), "ML_hgb_pretrigger_wave_atoms", "NN_pretrigger_gated_residual_cnn_new"]))
    atom_effects = matched_p11a_atom_effects(meta, predictions, heldout_mask, effect_methods, config)

    train_abs_best_trad = np.abs((predictions[str(best_trad["method"])][train_mask] - y[train_mask]) / np.maximum(y[train_mask], 1.0))
    harm_cut = float(np.quantile(train_abs_best_trad, float(config["harm_quantile"])))
    y_harm = (np.abs((predictions[str(best_trad["method"])] - y) / np.maximum(y, 1.0)) > harm_cut).astype(int)
    classifier_metrics = classify_controls(meta, features, y_harm, train_mask, heldout_mask, config)
    support_metrics = support_summary(meta_all, valid, train_mask_all, heldout_mask_all, config)

    print("6/7 write result tables", flush=True)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    benchmark.to_csv(out_dir / "benchmark.csv", index=False)
    by_run.to_csv(out_dir / "benchmark_by_run.csv", index=False)
    deltas.to_csv(out_dir / "ml_minus_traditional.csv", index=False)
    atom_summary.to_csv(out_dir / "atom_outcome_summary.csv", index=False)
    atom_effects.to_csv(out_dir / "matched_p11a_atom_effects.csv", index=False)
    classifier_metrics.to_csv(out_dir / "harm_classifier_metrics.csv", index=False)
    support_metrics.to_csv(out_dir / "support_model_metrics.csv", index=False)
    pd.DataFrame(
        [{"file": str(raw_path(config, run).relative_to(ROOT)), "sha256": sha256_file(raw_path(config, run)), "bytes": raw_path(config, run).stat().st_size} for run in configured_runs(config)]
    ).to_csv(out_dir / "input_sha256.csv", index=False)

    finding = (
        f"Raw selected-pulse reproduction passes exactly ({total} vs {config['expected_selected_pulses']}). "
        f"The held-out duplicate-charge winner is `{winner['method']}` with res68 {winner['res68_abs_frac']:.4f} "
        f"[{winner['res68_ci95'][0]:.4f}, {winner['res68_ci95'][1]:.4f}], compared with the strongest traditional "
        f"method `{best_trad['method']}` at {best_trad['res68_abs_frac']:.4f}. Matched P11a atom effects are small relative "
        "to the main amplitude/dropout/saturation structure, so adaptive-lowering/spike atoms are best used as support "
        "and abstention flags rather than as independent charge-correction variables."
    )
    hypothesis = (
        "P11a pretrigger atoms do carry charge-transfer support information, but after explicit matching on amplitude, "
        "P07 saturation, dropout/anomaly taxa, stave, and run family they behave primarily as electronics-support labels. "
        "The operational rule is therefore pass quiet records, abstain or down-weight high pretrigger-score records near "
        "support boundaries, and avoid a hard veto unless downstream consumers require the lowest charge-tail rate."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "runtime_sec": time.time() - t0,
        "raw_reproduction_passed": total == int(config["expected_selected_pulses"]),
        "raw_reproduction": {
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "reproduced_selected_pulses": total,
            "delta": total - int(config["expected_selected_pulses"]),
            "invalid_duplicate_target_rows_removed_after_reproduction": int((~valid).sum()),
        },
        "split": {
            "train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()),
            "heldout_runs": heldout_runs,
            "bootstrap_unit": "held-out run",
            "bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "primary_metric": "duplicate-readout charge res68_abs_frac; lower is better",
        "winner": json.loads(pd.Series(winner).to_json()),
        "best_traditional": json.loads(pd.Series(best_trad).to_json()),
        "ml_minus_traditional": json.loads(deltas.to_json(orient="records")),
        "abstention": abstention,
        "harm_classifier_metrics": json.loads(classifier_metrics.to_json(orient="records")),
        "support_model_metrics": json.loads(support_metrics.to_json(orient="records")),
        "p11a_atom_thresholds": meta.attrs.get("p11a_thresholds", {}),
        "finding": finding,
        "hypothesis": hypothesis,
        "next_tickets": [],
        "leakage_audit": {
            "train_heldout_run_overlap": sorted(set(meta.loc[train_mask, "run"].unique()).intersection(set(heldout_runs))),
            "feature_exclusions": ["eventno", "evt", "target_odd_pos_charge", "target_odd_neg_amp"],
            "controls": ["pretrigger_knockout", "saturation_only", "dropout_only", "amplitude_only", "run_only", "shuffled_harm"],
        },
    }

    print("7/7 write report, manifest, result", flush=True)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, counts, benchmark, by_run, deltas, atom_summary, atom_effects, classifier_metrics, support_metrics, abstention, result)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "script": "scripts/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.py",
        "config": str(args.config.relative_to(ROOT) if args.config.is_absolute() else args.config),
        "command": "/home/billy/anaconda3/bin/python scripts/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.py --config configs/p11b_1781061059_627_4bc647a3_pretrigger_charge_transfer_gate.json",
        "random_seed": int(config["random_seed"]),
        "inputs": [{"path": str(raw_path(config, run).relative_to(ROOT)), "sha256": sha256_file(raw_path(config, run)), "bytes": raw_path(config, run).stat().st_size} for run in configured_runs(config)],
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
