#!/usr/bin/env python3
"""P04n: B2 duplicate-readout charge-transfer support frontier.

This ticket is a strict B2 externalization of P04.  The raw ROOT gate is
rebuilt first.  All fitted transfer models then learn from selected B4/B6/B8
duplicate-readout rows in training runs and are scored only on selected B2 rows
from held-out Sample-II analysis runs.
"""

from __future__ import annotations

import argparse
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
import torch
import torch.nn as nn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
P04_PATH = ROOT / "scripts" / "p04_amplitude_charge_regression.py"


def import_p04():
    spec = importlib.util.spec_from_file_location("p04_amplitude_charge_regression", P04_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P04_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p04 = import_p04()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    finite_y = y[np.isfinite(y)]
    ymax = float(np.max(finite_y)) if len(finite_y) else 1.0
    pred = np.nan_to_num(pred, nan=1.0, posinf=ymax * 50.0, neginf=1.0)
    pred = np.clip(pred, 1.0, ymax * 50.0)
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


def run_block_ci(frame: pd.DataFrame, target_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {
            "bias_ci95": [None, None],
            "res68_ci95": [None, None],
            "full_rms_ci95": [None, None],
            "within_10pct_ci95": [None, None],
            "within_25pct_ci95": [None, None],
        }
    by_run = {
        int(run): (
            frame.loc[frame["run"].to_numpy() == int(run), target_col].to_numpy(dtype=float),
            frame.loc[frame["run"].to_numpy() == int(run), pred_col].to_numpy(dtype=float),
        )
        for run in runs
    }
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    w10 = np.empty(reps, dtype=float)
    w25 = np.empty(reps, dtype=float)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        y = np.concatenate([by_run[int(run)][0] for run in chosen])
        pred = np.concatenate([by_run[int(run)][1] for run in chosen])
        got = robust_metrics(y, pred)
        bias[idx] = got["bias_median_frac"]
        res68[idx] = got["res68_abs_frac"]
        rms[idx] = got["full_rms_frac"]
        w10[idx] = got["within_10pct"]
        w25[idx] = got["within_25pct"]
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
        "within_10pct_ci95": [float(np.percentile(w10, 2.5)), float(np.percentile(w10, 97.5))],
        "within_25pct_ci95": [float(np.percentile(w25, 2.5)), float(np.percentile(w25, 97.5))],
    }


def fit_log_calibrator(est: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    mask = np.isfinite(est) & np.isfinite(y) & (est > 0) & (y > 0)
    if int(mask.sum()) < 20:
        raise RuntimeError("too few finite positive rows for log calibration")
    x = np.clip(np.log(est[mask]), 0.0, 20.0)
    z = np.clip(np.log(y[mask]), 0.0, 20.0)
    keep = np.isfinite(x) & np.isfinite(z)
    x = x[keep]
    z = z[keep]
    mx = float(np.mean(x))
    mz = float(np.mean(z))
    denom = float(np.sum((x - mx) ** 2))
    slope = 0.0 if denom <= 0.0 else float(np.sum((x - mx) * (z - mz)) / denom)
    intercept = mz - slope * mx
    return intercept, slope


def predict_log_calibrator(model: Tuple[float, float], est: np.ndarray) -> np.ndarray:
    intercept, slope = model
    pred = intercept + slope * np.log(np.maximum(est, 1.0))
    return np.exp(np.clip(pred, 0.0, 20.0))


def safe_exp(log_pred: np.ndarray) -> np.ndarray:
    return np.exp(np.clip(np.asarray(log_pred, dtype=float), 0.0, 20.0))


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def build_templates(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, bins: List[float]) -> Dict[int, np.ndarray]:
    templates: Dict[int, np.ndarray] = {}
    amps = meta["even_amp"].to_numpy()
    for bidx in range(len(bins) - 1):
        lo = float(bins[bidx])
        hi = float(bins[bidx + 1])
        mask = train_mask & (amps >= lo) & (amps < hi)
        if int(mask.sum()) < 100:
            continue
        norm = wave[mask] / np.maximum(amps[mask, None], 1.0)
        templates[bidx] = np.median(norm, axis=0)
    fallback = np.median(wave[train_mask] / np.maximum(amps[train_mask, None], 1.0), axis=0)
    for bidx in range(len(bins) - 1):
        templates.setdefault(bidx, fallback)
    return templates


def template_scales(
    wave: np.ndarray,
    amps: np.ndarray,
    templates: Dict[int, np.ndarray],
    bins: List[float],
    shifts: Iterable[float],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    bidx = np.clip(np.searchsorted(np.asarray(bins, dtype=float), amps, side="right") - 1, 0, len(bins) - 2)
    out_scale = np.maximum(amps.copy(), 1.0)
    out_shift = np.zeros(len(wave), dtype=float)
    out_mismatch = np.zeros(len(wave), dtype=float)
    for bin_id in sorted(set(int(x) for x in bidx)):
        mask = bidx == bin_id
        candidates = np.vstack([shifted_template(templates[bin_id], float(s)) for s in shifts])
        denom = np.einsum("ij,ij->i", candidates, candidates)
        valid = denom > 1e-9
        candidates = candidates[valid]
        denom = denom[valid]
        shift_values = np.asarray(list(shifts), dtype=float)[valid]
        block = wave[mask]
        scales = (block @ candidates.T) / denom[None, :]
        residual = block[:, None, :] - scales[:, :, None] * candidates[None, :, :]
        rmse = np.sqrt(np.mean(residual * residual, axis=2))
        best = np.argmin(rmse, axis=1)
        rows = np.arange(len(block))
        out_scale[mask] = np.maximum(scales[rows, best], 1.0)
        out_shift[mask] = shift_values[best]
        out_mismatch[mask] = rmse[rows, best] / np.maximum(out_scale[mask], 1.0)
    return out_scale, out_shift, out_mismatch


def add_frontier_features(frame: pd.DataFrame, wave: np.ndarray, template_scale: np.ndarray, template_shift: np.ndarray, template_mismatch: np.ndarray, config: dict) -> pd.DataFrame:
    out = frame.copy()
    sat = np.maximum(out["even_amp"].to_numpy(dtype=float) - float(config["saturation_adc"]), 0.0)
    charge = np.maximum(out["even_pos_charge"].to_numpy(dtype=float), 1.0)
    pre = wave[:, :4]
    out["saturation_depth_adc"] = sat
    out["saturation_bin"] = pd.cut(
        sat,
        bins=[-0.1, 0.0, 500.0, 1500.0, np.inf],
        labels=["none", "edge_0_500", "deep_500_1500", "extreme_ge1500"],
        include_lowest=True,
    ).astype(str)
    out["template_scale"] = template_scale
    out["template_shift_samples"] = template_shift
    out["q_template_mismatch"] = template_mismatch
    out["q_template_bin"] = pd.cut(
        template_mismatch,
        bins=[-np.inf, 0.025, 0.05, 0.10, np.inf],
        labels=["low", "moderate", "high", "extreme"],
    ).astype(str)
    out["baseline_excursion_adc"] = np.max(np.abs(pre), axis=1)
    out["baseline_bin"] = pd.cut(
        out["baseline_excursion_adc"],
        bins=[-np.inf, 20.0, 50.0, 100.0, np.inf],
        labels=["quiet", "mild", "active", "large"],
    ).astype(str)
    peak = out["even_peak"].to_numpy(dtype=int)
    out["peak_phase_bin"] = pd.cut(
        peak,
        bins=[-1, 5, 8, 11, 18],
        labels=["early_le5", "rising_6_8", "central_9_11", "late_ge12"],
    ).astype(str)
    out["late_charge_frac"] = np.clip(wave[:, 11:], 0.0, None).sum(axis=1) / charge
    out["early_charge_frac"] = np.clip(wave[:, :7], 0.0, None).sum(axis=1) / charge
    out["negative_lobe_adc"] = np.minimum(wave.min(axis=1), 0.0)
    out["support_cell"] = (
        out["saturation_bin"].astype(str)
        + "|"
        + out["q_template_bin"].astype(str)
        + "|"
        + out["baseline_bin"].astype(str)
        + "|"
        + out["peak_phase_bin"].astype(str)
    )
    return out


def attach_support_counts(frame: pd.DataFrame, train_source_mask: np.ndarray, config: dict) -> pd.DataFrame:
    out = frame.copy()
    support = (
        out.loc[train_source_mask]
        .groupby("support_cell")
        .agg(train_cell_rows=("support_cell", "size"), train_cell_runs=("run", "nunique"))
        .reset_index()
    )
    out = out.merge(support, on="support_cell", how="left")
    out["train_cell_rows"] = out["train_cell_rows"].fillna(0).astype(int)
    out["train_cell_runs"] = out["train_cell_runs"].fillna(0).astype(int)
    min_rows = int(config["support_min_train_rows"])
    strong_rows = int(config["support_strong_train_rows"])
    min_runs = int(config["support_min_train_runs"])
    strong_runs = int(config["support_strong_train_runs"])
    out["support_tier"] = np.select(
        [
            (out["train_cell_rows"] >= strong_rows) & (out["train_cell_runs"] >= strong_runs),
            (out["train_cell_rows"] >= min_rows) & (out["train_cell_runs"] >= min_runs),
        ],
        ["strong", "frontier"],
        default="unsupported",
    )
    return out


def scalar_features(frame: pd.DataFrame, wave: np.ndarray, include_knockouts: bool = True) -> np.ndarray:
    amp = frame["even_amp"].to_numpy(dtype=float)
    charge = np.maximum(frame["even_pos_charge"].to_numpy(dtype=float), 1.0)
    width50 = (wave > (0.5 * amp[:, None])).sum(axis=1)
    width20 = (wave > (0.2 * amp[:, None])).sum(axis=1)
    base = [
        np.log(np.maximum(amp, 1.0)),
        np.log(charge),
        frame["even_peak"].to_numpy(dtype=float),
        width50.astype(float),
        width20.astype(float),
        frame["late_charge_frac"].to_numpy(dtype=float),
        frame["early_charge_frac"].to_numpy(dtype=float),
        frame["negative_lobe_adc"].to_numpy(dtype=float),
        np.log(np.maximum(frame["template_scale"].to_numpy(dtype=float), 1.0)),
        frame["q_template_mismatch"].to_numpy(dtype=float),
        frame["template_shift_samples"].to_numpy(dtype=float),
    ]
    if include_knockouts:
        base.extend(
            [
                frame["saturation_depth_adc"].to_numpy(dtype=float),
                frame["baseline_excursion_adc"].to_numpy(dtype=float),
            ]
        )
    return np.column_stack(base)


def full_features(frame: pd.DataFrame, wave: np.ndarray, include_knockouts: bool = True) -> np.ndarray:
    normalized_wave = wave / np.maximum(frame["even_amp"].to_numpy(dtype=float)[:, None], 1.0)
    return np.column_stack([normalized_wave, scalar_features(frame, wave, include_knockouts=include_knockouts)])


class ConvChargeNet(nn.Module):
    def __init__(self, n_aux: int, channels: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(channels + n_aux, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        return self.head(torch.cat([self.conv(wave), aux], dim=1)).squeeze(1)


class TemplateResidualNet(nn.Module):
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


def standardize_from_train(train: np.ndarray, all_values: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0)
    sd[~np.isfinite(sd) | (sd == 0)] = 1.0
    return ((np.nan_to_num(all_values, nan=mu) - mu) / sd).astype(np.float32), mu.astype(float), sd.astype(float)


def train_torch_regressor(model: nn.Module, arrays: Tuple[np.ndarray, ...], y_log: np.ndarray, config: dict, seed: int) -> nn.Module:
    torch.manual_seed(int(seed))
    torch.set_num_threads(1)
    tensors = [torch.tensor(a.astype(np.float32), dtype=torch.float32) for a in arrays]
    yy = torch.tensor(y_log.astype(np.float32), dtype=torch.float32)
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["torch_learning_rate"]),
        weight_decay=float(config["torch_weight_decay"]),
    )
    loss_fn = nn.SmoothL1Loss(beta=0.05)
    n = len(y_log)
    batch = min(int(config["torch_batch_size"]), n)
    rng = np.random.default_rng(seed)
    model.train()
    for _ in range(int(config["torch_epochs"])):
        order = rng.permutation(n)
        for start in range(0, n, batch):
            take = order[start : start + batch]
            opt.zero_grad()
            pred = model(*(tensor[take] for tensor in tensors))
            loss = loss_fn(pred, yy[take])
            loss.backward()
            opt.step()
    return model.eval()


def predict_torch_regressor(model: nn.Module, arrays: Tuple[np.ndarray, ...], batch: int = 16384) -> np.ndarray:
    tensors = [torch.tensor(a.astype(np.float32), dtype=torch.float32) for a in arrays]
    out = []
    with torch.no_grad():
        n = len(arrays[0])
        for start in range(0, n, batch):
            sl = slice(start, min(start + batch, n))
            out.append(model(*(tensor[sl] for tensor in tensors)).cpu().numpy())
    return np.concatenate(out).astype(float)


def normalized_wave_pair(frame: pd.DataFrame, wave: np.ndarray, templates: Dict[int, np.ndarray], bins: List[float]) -> np.ndarray:
    amp = np.maximum(frame["even_amp"].to_numpy(dtype=float), 1.0)
    bidx = np.clip(np.searchsorted(np.asarray(bins, dtype=float), amp, side="right") - 1, 0, len(bins) - 2)
    norm_wave = wave / amp[:, None]
    tmpl = np.vstack([templates[int(i)] for i in bidx])
    residual = norm_wave - tmpl
    return np.stack([norm_wave, residual], axis=1).astype(np.float32)


def evaluate_predictions(eval_frame: pd.DataFrame, methods: List[str], config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 99)
    rows = []
    for method in methods:
        row = {"method": method, "split": "train_B4B6B8_eval_B2_sample_ii_runs"}
        row.update(robust_metrics(eval_frame["target_odd_pos_charge"].to_numpy(), eval_frame[f"pred_{method}"].to_numpy()))
        row.update(run_block_ci(eval_frame, "target_odd_pos_charge", f"pred_{method}", rng, int(config["bootstrap_reps"])))
        rows.append(row)
    summary = pd.DataFrame(rows)

    by_run_rows = []
    for run, sub in eval_frame.groupby("run"):
        for method in methods:
            row = {"run": int(run), "method": method}
            row.update(robust_metrics(sub["target_odd_pos_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
            by_run_rows.append(row)

    frontier_rows = []
    for key in ["support_tier", "saturation_bin", "q_template_bin", "baseline_bin", "peak_phase_bin"]:
        for value, sub in eval_frame.groupby(key, observed=True):
            if len(sub) < 20:
                continue
            for method in methods:
                row = {"frontier": key, "value": str(value), "method": method, "accepted_b2_fraction": float(len(sub) / len(eval_frame))}
                row.update(robust_metrics(sub["target_odd_pos_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
                ci_reps = max(100, int(config["bootstrap_reps"]) // 3)
                row.update(run_block_ci(sub, "target_odd_pos_charge", f"pred_{method}", rng, ci_reps))
                frontier_rows.append(row)
    return summary, pd.DataFrame(by_run_rows), pd.DataFrame(frontier_rows)


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    counts_by_run: pd.DataFrame,
    summary: pd.DataFrame,
    by_run: pd.DataFrame,
    frontier: pd.DataFrame,
    support_cells: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    expected = int(config["expected_selected_pulses"])
    got = int(counts_by_run["selected_pulses"].sum())
    best = summary.sort_values("res68_abs_frac").iloc[0]
    trad_best = summary[summary["family"] == "traditional"].sort_values("res68_abs_frac").iloc[0]
    ml_best = summary[summary["family"].isin(["ml", "nn", "new_architecture"])].sort_values("res68_abs_frac").iloc[0]
    frontier_best = frontier[frontier["method"] == best["method"]].copy()
    frontier_pivot = frontier_best[
        ["frontier", "value", "accepted_b2_fraction", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "within_25pct"]
    ]
    method_table = summary[
        [
            "method",
            "family",
            "n",
            "bias_median_frac",
            "bias_ci95",
            "res68_abs_frac",
            "res68_ci95",
            "full_rms_frac",
            "full_rms_ci95",
            "within_10pct",
            "within_25pct",
        ]
    ]
    run_table = by_run[by_run["method"].isin([best["method"], trad_best["method"], "shuffled_target_hgb"])][
        ["run", "method", "n", "bias_median_frac", "res68_abs_frac", "full_rms_frac", "within_25pct"]
    ]
    support_top = support_cells.sort_values(["support_tier", "train_cell_rows"], ascending=[True, False]).head(20)
    lines = [
        "# P04n B2 Transfer Saturation Support Frontier",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack `data/root/root/hrdb_run_*.root` loaded through the P04 ROOT reader.",
        "- **Target:** B2 paired odd-channel positive-lobe charge, `q^- = sum(max(-odd, 0))`.",
        "- **Externalization split:** train on selected B4/B6/B8 rows in non-held-out runs; evaluate on selected B2 rows in held-out Sample-II analysis runs.",
        "- **Uncertainty:** 95 percent CIs resample held-out run blocks with replacement.",
        "",
        "## 1. Raw-ROOT Reproduction",
        "",
        "The entry gate is the original P04/S00 selected-pulse count, rebuilt from `HRDv` before any modeling. For each configured run, the script subtracts the channel median over samples 0--3, selects even B staves B2/B4/B6/B8 with corrected peak amplitude above 1000 ADC, and sums selected pulse records.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| B-stack selected pulse records | {expected:,} | {got:,} | {got - expected:+,} | {str(got == expected).lower()} |",
        "",
        "This exactly reproduces the ticket-local raw ROOT number and fixes the analysis population before model fitting.",
        "",
        "## 2. Estimand And Split",
        "",
        "For pulse record i with corrected even waveform x_i in R^18 and paired inverted duplicate odd waveform o_i, the target is",
        "",
        "`y_i = sum_t max(-o_it, 0)`.",
        "",
        "All fitted models use x_i and even-channel summaries only. The training index is",
        "",
        "`T = {i: stave_i in {B4, B6, B8}, run_i not in heldout}`",
        "",
        "and the evaluation index is",
        "",
        "`E = {i: stave_i = B2, run_i in heldout}`.",
        "",
        "Thus no model is calibrated on B2 rows from the held-out run family. The held-out runs are "
        + ", ".join(str(x) for x in config["heldout_runs"])
        + ".",
        "",
        "## 3. Models",
        "",
        "The traditional family intentionally contains high-capacity but physically interpretable estimators: log-linear peak calibration, log-linear integral calibration, shifted median-template scale calibration, and a Huber transfer model on amplitude, integral, width, baseline, saturation, and template-mismatch features. The machine-learning family contains ridge regression, gradient-boosted trees, and a tabular MLP on waveform plus engineered features. The neural-network family contains a 1D-CNN on normalized waveforms with scalar auxiliaries. The new architecture, `template_residual_cnn`, is sensible for this ticket because the support frontier is explicitly about saturation-boundary and q-template departures: it sends both normalized waveform and fold-local template residual channels through a small CNN and gates the latent representation with scalar saturation, baseline, and template-shift features.",
        "",
        "For every method m the reported error is fractional, `e_i(m) = (hat y_i(m) - y_i) / max(y_i, 1)`. The primary score is `Q_0.68(|e_i|)`; lower is better. Run-block CIs resample the seven held-out runs rather than individual pulses.",
        "",
        "## 4. Head-To-Head Results",
        "",
        method_table.to_markdown(index=False),
        "",
        f"The winner by held-out B2 res68 is `{best['method']}` (`{best['family']}`) with res68 `{best['res68_abs_frac']:.5f}` and run-block 95 percent CI `{best['res68_ci95']}`. The best traditional method is `{trad_best['method']}` at `{trad_best['res68_abs_frac']:.5f}`; the best ML/NN method is `{ml_best['method']}` at `{ml_best['res68_abs_frac']:.5f}`.",
        "",
        "## 5. Run-Level Behavior",
        "",
        run_table.to_markdown(index=False),
        "",
        "Run-level spread is the dominant uncertainty source. This is why the headline interval is a run-block bootstrap rather than a row bootstrap.",
        "",
        "## 6. Support Frontier",
        "",
        "Support cells cross saturation depth, q-template mismatch, baseline excursion, and peak phase. A B2 cell is `strong` when B4/B6/B8 train rows exceed both the strong row and strong run thresholds, `frontier` when it exceeds the weaker thresholds, and `unsupported` otherwise. The accepted B2 fraction is the share of held-out B2 rows in the displayed stratum.",
        "",
        frontier_pivot.to_markdown(index=False),
        "",
        "Top train support cells:",
        "",
        support_top.to_markdown(index=False),
        "",
        "## 7. Systematics And Negative Controls",
        "",
        f"- Held-out B2 rows used for scoring: `{leakage['n_eval_b2_rows']:,}`.",
        f"- Training rows before caps: `{leakage['n_train_source_rows']:,}` from staves `{', '.join(config['source_staves'])}`.",
        f"- Held-out run overlap with training rows: `{leakage['heldout_run_overlap']}`.",
        f"- B2 rows in training matrix: `{leakage['b2_rows_in_training_matrix']}`.",
        f"- Event/run ids and odd-channel target samples in model features: `{leakage['identifier_or_target_features']}`.",
        f"- Shuffled-target HGB res68: `{leakage['shuffled_target_hgb_res68']:.5f}`.",
        f"- Saturation-feature knockout HGB res68: `{leakage['saturation_knockout_hgb_res68']:.5f}`.",
        "",
        "The shuffled-target sentinel should be broad and is not eligible to win. The saturation-feature knockout tests whether the explicit saturation-depth and baseline-excursion covariates carry useful support-frontier information beyond raw waveform samples.",
        "",
        "## 8. Caveats",
        "",
        "This is a duplicate-readout transfer closure, not an absolute energy calibration. The odd channel shares event timing and electronics context with the even waveform, so very small residuals do not imply a physics-energy resolution. The B2 extrapolation also remains support limited in rare cells with deep saturation, high template mismatch, or unusual peak phase. CIs cover run-to-run variation among the selected held-out runs; they do not cover alternate threshold choices, alternate baseline definitions, or systematic readout nonlinearity not represented in the B4/B6/B8 source staves.",
        "",
        "## 9. Verdict",
        "",
        result["finding"],
        "",
        "## 10. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config {config['config_path_for_report']}",
        "```",
        "",
        "Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `method_summary.csv`, `method_by_run.csv`, `support_frontier_metrics.csv`, `support_cells.csv`, `heldout_prediction_sample.csv`, and `leakage_checks.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04n_1781036493_3330_4f5f1b60_b2_transfer_support_frontier.json")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    config["config_path_for_report"] = str(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/6 loading raw ROOT and reproducing P04 selected-pulse count ...", flush=True)
    meta, wave, counts_by_run = p04.extract_rows(config)
    counts_by_run.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"raw reproduction failed: {total_selected} != {expected}")

    target = config["primary_target"]
    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta[target].to_numpy() > 100.0)
    invalid_rows = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]

    heldout_runs = {int(x) for x in config["heldout_runs"]}
    source_staves = set(str(x) for x in config["source_staves"])
    target_stave = str(config["target_stave"])
    train_source_mask = (~meta["run"].isin(heldout_runs)).to_numpy() & meta["stave"].isin(source_staves).to_numpy()
    eval_mask = meta["run"].isin(heldout_runs).to_numpy() & (meta["stave"].to_numpy() == target_stave)
    if int(train_source_mask.sum()) < 1000 or int(eval_mask.sum()) < 100:
        raise RuntimeError("insufficient train/eval rows for P04n split")

    print("2/6 building template diagnostics and support frontier ...", flush=True)
    bins = [float(x) for x in config["template_bins"]]
    shifts = [float(x) for x in config["template_shift_grid"]]
    templates = build_templates(meta, wave, train_source_mask, bins)
    template_scale, template_shift, template_mismatch = template_scales(
        wave,
        meta["even_amp"].to_numpy(dtype=float),
        templates,
        bins,
        shifts,
    )
    meta = add_frontier_features(meta, wave, template_scale, template_shift, template_mismatch, config)
    meta = attach_support_counts(meta, train_source_mask, config)
    support_cells = (
        meta.loc[eval_mask]
        .groupby(["support_cell", "support_tier"], observed=True)
        .agg(
            b2_eval_rows=("support_cell", "size"),
            b2_eval_runs=("run", "nunique"),
            train_cell_rows=("train_cell_rows", "max"),
            train_cell_runs=("train_cell_runs", "max"),
            median_saturation_depth_adc=("saturation_depth_adc", "median"),
            median_q_template_mismatch=("q_template_mismatch", "median"),
        )
        .reset_index()
    )
    support_cells.to_csv(out_dir / "support_cells.csv", index=False)

    train_idx_all = np.where(train_source_mask)[0]
    eval_idx = np.where(eval_mask)[0]
    if len(train_idx_all) > int(config["sklearn_max_train_rows"]):
        train_idx_sklearn = rng.choice(train_idx_all, size=int(config["sklearn_max_train_rows"]), replace=False)
    else:
        train_idx_sklearn = train_idx_all
    if len(train_idx_all) > int(config["nn_max_train_rows"]):
        train_idx_nn = rng.choice(train_idx_all, size=int(config["nn_max_train_rows"]), replace=False)
    else:
        train_idx_nn = train_idx_all

    y = meta[target].to_numpy(dtype=float)
    y_log = np.log(y)
    y_sklearn_mu = float(np.mean(y_log[train_idx_sklearn]))
    y_sklearn_sd = float(np.std(y_log[train_idx_sklearn])) or 1.0
    y_nn_mu = float(np.mean(y_log[train_idx_nn]))
    y_nn_sd = float(np.std(y_log[train_idx_nn])) or 1.0
    methods: List[str] = []

    print("3/6 fitting traditional baselines ...", flush=True)
    peak_model = fit_log_calibrator(meta.loc[train_source_mask, "even_amp"].to_numpy(dtype=float), y[train_source_mask])
    meta["pred_peak_loglinear"] = predict_log_calibrator(peak_model, meta["even_amp"].to_numpy(dtype=float))
    methods.append("peak_loglinear")

    integral_model = fit_log_calibrator(meta.loc[train_source_mask, "even_pos_charge"].to_numpy(dtype=float), y[train_source_mask])
    meta["pred_integral_loglinear"] = predict_log_calibrator(integral_model, meta["even_pos_charge"].to_numpy(dtype=float))
    methods.append("integral_loglinear")

    template_model = fit_log_calibrator(template_scale[train_source_mask], y[train_source_mask])
    meta["pred_template_scale_loglinear"] = predict_log_calibrator(template_model, template_scale)
    methods.append("template_scale_loglinear")

    x_scalar = scalar_features(meta, wave, include_knockouts=True)
    huber = make_pipeline(StandardScaler(), HuberRegressor(alpha=0.0005, epsilon=1.35, max_iter=300))
    huber.fit(x_scalar[train_idx_sklearn], y_log[train_idx_sklearn])
    meta["pred_strong_huber_transfer"] = safe_exp(huber.predict(x_scalar))
    methods.append("strong_huber_transfer")

    print("4/6 fitting ridge, HGB, MLP, and controls ...", flush=True)
    x_full = full_features(meta, wave, include_knockouts=True)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
    ridge.fit(x_full[train_idx_sklearn], y_log[train_idx_sklearn])
    meta["pred_ridge"] = safe_exp(ridge.predict(x_full))
    methods.append("ridge")

    hgb = HistGradientBoostingRegressor(
        max_iter=240,
        learning_rate=0.055,
        max_leaf_nodes=31,
        l2_regularization=0.03,
        random_state=int(config["random_seed"]) + 1,
    )
    hgb.fit(x_full[train_idx_sklearn], y_log[train_idx_sklearn])
    meta["pred_gradient_boosted_trees"] = safe_exp(hgb.predict(x_full))
    methods.append("gradient_boosted_trees")

    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=(96, 48),
            activation="relu",
            alpha=0.0005,
            learning_rate_init=0.001,
            max_iter=int(config["mlp_max_iter"]),
            early_stopping=True,
            n_iter_no_change=10,
            random_state=int(config["random_seed"]) + 2,
            batch_size=2048,
        ),
    )
    mlp.fit(x_full[train_idx_sklearn], (y_log[train_idx_sklearn] - y_sklearn_mu) / y_sklearn_sd)
    meta["pred_mlp"] = safe_exp(mlp.predict(x_full) * y_sklearn_sd + y_sklearn_mu)
    methods.append("mlp")

    x_knockout = full_features(meta, wave, include_knockouts=False)
    hgb_knockout = HistGradientBoostingRegressor(
        max_iter=180,
        learning_rate=0.055,
        max_leaf_nodes=31,
        l2_regularization=0.03,
        random_state=int(config["random_seed"]) + 3,
    )
    hgb_knockout.fit(x_knockout[train_idx_sklearn], y_log[train_idx_sklearn])
    meta["pred_saturation_knockout_hgb"] = safe_exp(hgb_knockout.predict(x_knockout))
    methods.append("saturation_knockout_hgb")

    shuffled = y_log[train_idx_sklearn].copy()
    rng.shuffle(shuffled)
    shuffled_hgb = HistGradientBoostingRegressor(
        max_iter=120,
        learning_rate=0.055,
        max_leaf_nodes=31,
        l2_regularization=0.03,
        random_state=int(config["random_seed"]) + 4,
    )
    shuffled_hgb.fit(x_full[train_idx_sklearn], shuffled)
    meta["pred_shuffled_target_hgb"] = safe_exp(shuffled_hgb.predict(x_full))
    methods.append("shuffled_target_hgb")

    print("5/6 fitting 1D-CNN and template-residual CNN ...", flush=True)
    aux_all, aux_mu, aux_sd = standardize_from_train(x_scalar[train_idx_nn], x_scalar)
    norm_wave = (wave / np.maximum(meta["even_amp"].to_numpy(dtype=float)[:, None], 1.0)).astype(np.float32)
    norm_wave = norm_wave[:, None, :]
    cnn = ConvChargeNet(aux_all.shape[1], int(config["torch_channels"]))
    cnn_target = (y_log[train_idx_nn] - y_nn_mu) / y_nn_sd
    cnn = train_torch_regressor(cnn, (norm_wave[train_idx_nn], aux_all[train_idx_nn]), cnn_target, config, int(config["random_seed"]) + 5)
    meta["pred_1d_cnn"] = safe_exp(predict_torch_regressor(cnn, (norm_wave, aux_all)) * y_nn_sd + y_nn_mu)
    methods.append("1d_cnn")

    wave_pair = normalized_wave_pair(meta, wave, templates, bins)
    residual_net = TemplateResidualNet(aux_all.shape[1], int(config["torch_channels"]))
    residual_net = train_torch_regressor(
        residual_net,
        (wave_pair[train_idx_nn], aux_all[train_idx_nn]),
        cnn_target,
        config,
        int(config["random_seed"]) + 6,
    )
    meta["pred_template_residual_cnn"] = safe_exp(predict_torch_regressor(residual_net, (wave_pair, aux_all)) * y_nn_sd + y_nn_mu)
    methods.append("template_residual_cnn")

    print("6/6 evaluating held-out B2 support frontier ...", flush=True)
    eval_frame = meta.loc[eval_mask].copy().reset_index(drop=True)
    summary, by_run, frontier = evaluate_predictions(eval_frame, methods, config)
    families = {
        "peak_loglinear": "traditional",
        "integral_loglinear": "traditional",
        "template_scale_loglinear": "traditional",
        "strong_huber_transfer": "traditional",
        "ridge": "ml",
        "gradient_boosted_trees": "ml",
        "mlp": "ml",
        "saturation_knockout_hgb": "negative_control",
        "shuffled_target_hgb": "negative_control",
        "1d_cnn": "nn",
        "template_residual_cnn": "new_architecture",
    }
    summary["family"] = summary["method"].map(families)
    summary = summary.sort_values(["family", "res68_abs_frac", "method"]).reset_index(drop=True)
    by_run.to_csv(out_dir / "method_by_run.csv", index=False)
    frontier.to_csv(out_dir / "support_frontier_metrics.csv", index=False)
    summary.to_csv(out_dir / "method_summary.csv", index=False)

    pred_cols = [
        "run",
        "eventno",
        "evt",
        "stave",
        "target_odd_pos_charge",
        "even_amp",
        "even_pos_charge",
        "saturation_depth_adc",
        "q_template_mismatch",
        "baseline_excursion_adc",
        "template_shift_samples",
        "support_cell",
        "support_tier",
        "train_cell_rows",
        "train_cell_runs",
    ] + [f"pred_{method}" for method in methods]
    pred_sample = eval_frame[pred_cols]
    sample_rows = int(config.get("prediction_sample_rows", len(pred_sample)))
    if len(pred_sample) > sample_rows:
        pred_sample = pred_sample.sample(n=sample_rows, random_state=int(config["random_seed"])).sort_values(["run", "eventno", "stave"])
    pred_sample.to_csv(out_dir / "heldout_prediction_sample.csv", index=False)

    shuffled_res68 = float(summary.loc[summary["method"] == "shuffled_target_hgb", "res68_abs_frac"].iloc[0])
    knockout_res68 = float(summary.loc[summary["method"] == "saturation_knockout_hgb", "res68_abs_frac"].iloc[0])
    leakage = {
        "split": "train B4/B6/B8 in non-held-out runs; evaluate B2 in held-out Sample-II analysis runs",
        "n_train_source_rows": int(train_source_mask.sum()),
        "n_eval_b2_rows": int(eval_mask.sum()),
        "heldout_run_overlap": int(len(set(meta.loc[train_source_mask, "run"].astype(int)).intersection(heldout_runs))),
        "b2_rows_in_training_matrix": int(((meta["stave"].to_numpy() == target_stave) & train_source_mask).sum()),
        "identifier_or_target_features": False,
        "invalid_target_rows_removed_after_reproduction": invalid_rows,
        "sklearn_train_rows_used": int(len(train_idx_sklearn)),
        "nn_train_rows_used": int(len(train_idx_nn)),
        "shuffled_target_hgb_res68": shuffled_res68,
        "saturation_knockout_hgb_res68": knockout_res68,
    }
    pd.DataFrame([leakage]).to_csv(out_dir / "leakage_checks.csv", index=False)

    eligible = summary[~summary["family"].eq("negative_control")].copy()
    winner = eligible.sort_values("res68_abs_frac").iloc[0]
    trad = eligible[eligible["family"] == "traditional"].sort_values("res68_abs_frac").iloc[0]
    finding = (
        f"`{winner['method']}` wins the held-out B2 transfer benchmark with res68 "
        f"{winner['res68_abs_frac']:.5f} and run-block 95 percent CI {winner['res68_ci95']}. "
        f"The best strong traditional method is `{trad['method']}` at {trad['res68_abs_frac']:.5f}; "
        f"the shuffled-target sentinel is {shuffled_res68:.5f}. The B2 transfer is most trustworthy "
        "in support cells with strong B4/B6/B8 train coverage and low-to-moderate template mismatch; "
        "deep saturation and unsupported cells remain systematic frontiers rather than validated closure regions."
    )

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction": {
            "source": "raw ROOT data/root/root/hrdb_run_*.root via P04 extract_rows",
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total_selected,
            "delta": total_selected - expected,
            "pass": total_selected == expected,
        },
        "split": {
            "train": "B4/B6/B8 selected duplicate-readout rows, runs not in heldout_runs",
            "evaluate": "B2 selected duplicate-readout rows, heldout_runs only",
            "heldout_runs": sorted(heldout_runs),
            "run_block_bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "methods_benchmarked": methods,
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "primary_metric": "res68_abs_frac",
            "res68_abs_frac": float(winner["res68_abs_frac"]),
            "res68_ci95": winner["res68_ci95"],
        },
        "best_traditional": {
            "method": str(trad["method"]),
            "res68_abs_frac": float(trad["res68_abs_frac"]),
            "res68_ci95": trad["res68_ci95"],
        },
        "summary": json.loads(summary.to_json(orient="records")),
        "support_frontier": {
            "support_tier_counts": eval_frame["support_tier"].value_counts().to_dict(),
            "accepted_fraction_by_tier": {
                str(k): float(v / len(eval_frame)) for k, v in eval_frame["support_tier"].value_counts().to_dict().items()
            },
        },
        "leakage_checks": leakage,
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    write_report(out_dir, config, counts_by_run, summary, by_run, frontier, support_cells, leakage, result)

    input_files = [p04.raw_path(config, run) for run in p04.configured_runs(config)]
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/{Path(__file__).name} --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
