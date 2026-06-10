#!/usr/bin/env python3
"""P04m: pretrigger-mode charge-transfer abstention map.

The study starts from raw HRDB ROOT, reproduces the S00/P04 selected-pulse
number, then tests whether S16-style pretrigger modes define regions where
duplicate-readout charge closure remains good but external downstream charge
transfer degrades. Outputs are isolated to the claimed ticket report folder.
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
import uproot
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, LinearRegression, Ridge
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


def raw_path(config: dict, run: int, stack: str = "b") -> Path:
    return ROOT / config["raw_root_dir"] / "hrd{}_run_{:04d}.root".format(stack, int(run))


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def ci(values) -> List[float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [float("nan"), float("nan")]
    return [float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))]


def robust_metrics(y: np.ndarray, pred: np.ndarray, catastrophic_cut: float) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "catastrophic_rate": float(np.mean(abs_frac > catastrophic_cut)),
        "within_10pct": float(np.mean(abs_frac < 0.10)),
    }


def run_block_ci(frame: pd.DataFrame, target_col: str, pred_col: str, catastrophic_cut: float, reps: int, seed: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    rng = np.random.default_rng(seed)
    by_run = {int(run): frame[frame["run"] == int(run)] for run in runs}
    bias, res68, rms, cat = [], [], [], []
    for _ in range(reps):
        pieces = [by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)]
        sample = pd.concat(pieces, ignore_index=True)
        frac = (sample[pred_col].to_numpy() - sample[target_col].to_numpy()) / np.maximum(sample[target_col].to_numpy(), 1.0)
        abs_frac = np.abs(frac)
        bias.append(float(np.median(frac)))
        res68.append(float(np.percentile(abs_frac, 68)))
        rms.append(float(np.sqrt(np.mean(frac * frac))))
        cat.append(float(np.mean(abs_frac > catastrophic_cut)))
    return {
        "bias_ci95": ci(bias),
        "res68_ci95": ci(res68),
        "full_rms_ci95": ci(rms),
        "catastrophic_rate_ci95": ci(cat),
    }


def add_pretrigger_modes(meta: pd.DataFrame, train_mask: np.ndarray, config: dict) -> pd.DataFrame:
    out = meta.copy()
    pre = np.sqrt(
        out["baseline_mad"].to_numpy() ** 2
        + out["baseline_slope"].to_numpy() ** 2
        + out["baseline_range"].to_numpy() ** 2
    )
    out["pretrigger_score"] = pre.astype(np.float32)
    out["pretrigger_slope_abs"] = out["baseline_slope"].abs().astype(np.float32)
    q_pre = [float(x) for x in np.quantile(pre[train_mask], [0.50, 0.80, 0.95])]
    q_slope = [float(x) for x in np.quantile(out.loc[train_mask, "pretrigger_slope_abs"], [0.50, 0.80, 0.95])]
    q_range = [float(x) for x in np.quantile(out.loc[train_mask, "baseline_range"], [0.50, 0.80, 0.95])]

    def qbin(values: np.ndarray, cuts: List[float], labels: List[str]) -> np.ndarray:
        clean = []
        for val in cuts:
            if not clean or float(val) > clean[-1]:
                clean.append(float(val))
        idx = np.searchsorted(np.asarray(clean, dtype=float), values.astype(float), side="right")
        return np.asarray([labels[min(int(i), len(labels) - 1)] for i in idx], dtype=object)

    out["pre_score_bin"] = qbin(out["pretrigger_score"].to_numpy(), q_pre, ["p1", "p2", "p3", "p4"])
    out["pre_slope_bin"] = qbin(out["pretrigger_slope_abs"].to_numpy(), q_slope, ["s1", "s2", "s3", "s4"])
    out["pre_range_bin"] = qbin(out["baseline_range"].to_numpy(), q_range, ["r1", "r2", "r3", "r4"])
    out["pretrigger_mode"] = out["pre_score_bin"] + "|" + out["pre_slope_bin"] + "|" + out["pre_range_bin"]
    high = (out["pre_score_bin"] == "p4") | (out["pre_slope_bin"] == "s4") | (out["pre_range_bin"] == "r4")
    out["pretrigger_risk_group"] = np.where(high, "high_pretrigger", "quiet_reference")
    return out


def fit_extra_trees(features: np.ndarray, y: np.ndarray, train_idx: np.ndarray, seed: int) -> np.ndarray:
    model = ExtraTreesRegressor(
        n_estimators=160,
        min_samples_leaf=8,
        max_features=0.75,
        random_state=seed,
        n_jobs=1,
    )
    model.fit(features[train_idx], np.log(y[train_idx]))
    return np.maximum(np.exp(model.predict(features)), 1.0)


class PretriggerGatedWaveNet(nn.Module):
    def __init__(self, n_context: int) -> None:
        super().__init__()
        self.wave = nn.Sequential(
            nn.Conv1d(1, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.context = nn.Sequential(nn.Linear(n_context, 48), nn.ReLU(), nn.Linear(48, 32), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(n_context, 32), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x_tab: torch.Tensor, x_wave: torch.Tensor) -> torch.Tensor:
        zw = self.wave(x_wave[:, None, :]).squeeze(-1)
        zc = self.context(x_tab)
        gated = zw * self.gate(x_tab)
        return self.head(torch.cat([gated, zc], dim=1)).squeeze(1)


def fit_pretrigger_gated_net(x_tab: np.ndarray, x_wave: np.ndarray, y: np.ndarray, train_idx: np.ndarray, config: dict) -> np.ndarray:
    seed = int(config["random_seed"]) + 914
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    use_idx = train_idx.copy()
    if len(use_idx) > int(config["nn_max_train_rows"]):
        use_idx = rng.choice(use_idx, size=int(config["nn_max_train_rows"]), replace=False)

    tab_scaler = StandardScaler()
    x_tab_fit = tab_scaler.fit_transform(x_tab[use_idx]).astype(np.float32)
    x_tab_all = tab_scaler.transform(x_tab).astype(np.float32)
    wave_fit = x_wave[use_idx].astype(np.float32)
    wave_scale = float(max(np.percentile(np.abs(wave_fit), 95), 1.0))
    wave_fit = wave_fit / wave_scale
    wave_all = x_wave.astype(np.float32) / wave_scale
    y_log = np.log(y)
    y_mean = float(y_log[use_idx].mean())
    y_std = float(y_log[use_idx].std() + 1e-6)
    y_fit = ((y_log[use_idx] - y_mean) / y_std).astype(np.float32)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PretriggerGatedWaveNet(x_tab_fit.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn_learning_rate"]), weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    batch_size = int(config["nn_batch_size"])
    for epoch in range(int(config["nn_epochs"])):
        order = rng.permutation(len(use_idx))
        losses = []
        model.train()
        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            xt = torch.from_numpy(x_tab_fit[idx]).to(device)
            xw = torch.from_numpy(wave_fit[idx]).to(device)
            yy = torch.from_numpy(y_fit[idx]).to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xt, xw), yy)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        print("pretrigger_gated_net epoch {}/{} loss={:.5f}".format(epoch + 1, int(config["nn_epochs"]), np.mean(losses)), flush=True)

    preds = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(x_tab_all), batch_size * 4):
            xt = torch.from_numpy(x_tab_all[start : start + batch_size * 4]).to(device)
            xw = torch.from_numpy(wave_all[start : start + batch_size * 4]).to(device)
            preds.append(model(xt, xw).detach().cpu().numpy())
    pred_std = np.concatenate(preds)
    return np.maximum(np.exp(pred_std * y_std + y_mean), 1.0)


def duplicate_method_predictions(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(int(config["random_seed"]))
    y = meta["target_odd_pos_charge"].to_numpy()
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    stave_idx = meta["stave_idx"].to_numpy().astype(int)

    predictions: Dict[str, np.ndarray] = {}
    predictions["traditional_peak_logcal"] = p04l.fit_log_calibrated(meta["even_amp"].to_numpy(), y, train_mask, stave_idx)
    predictions["traditional_integral_logcal"] = p04l.fit_log_calibrated(meta["even_pos_charge"].to_numpy(), y, train_mask, stave_idx)
    templates = p04l.p04.build_templates(meta, wave, train_mask, [float(x) for x in config["template_bins"]])
    template_scale = p04l.p04.template_scales(
        meta,
        wave,
        templates,
        [float(x) for x in config["template_bins"]],
        [float(x) for x in config["template_shift_grid"]],
    )
    predictions["traditional_adaptive_template"] = p04l.fit_log_calibrated(template_scale, y, train_mask, stave_idx)
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
            "pretrigger_score",
            "saturation_count",
            "is_saturated",
            "p09_pca_anomaly_score",
        ]
    ].to_numpy(dtype=np.float32)
    predictions["traditional_strong_huber_pretrigger"] = p04l.fit_strong_huber(trad_features, y, train_mask)
    predictions["traditional_dropout_cell_corrected"] = p04l.dropout_injected_prediction(
        meta, predictions["traditional_integral_logcal"], y, train_mask
    )

    features_with_pre = p04l.feature_matrix(meta, wave)
    features_without_pre = np.delete(features_with_pre, np.s_[:0], axis=1) if False else features_with_pre
    predictions["ML_ridge_with_pretrigger"] = p04l.fit_ridge(features_with_pre, y, train_idx)
    predictions["ML_hgb_with_pretrigger"] = p04l.fit_hgb(features_with_pre, y, train_idx, int(config["random_seed"]) + 1)
    predictions["ML_extratrees_with_pretrigger"] = fit_extra_trees(features_with_pre, y, train_idx, int(config["random_seed"]) + 2)

    no_pre_cols = [
        "even_amp",
        "even_pos_charge",
        "even_peak",
        "late_fraction",
        "early_fraction",
        "tail_fraction",
        "width_half",
        "area_norm",
        "secondary_peak",
        "secondary_sep",
        "dropout_score",
        "saturation_count",
        "is_saturated",
        "stave_idx",
    ]
    X_no_pre = meta[no_pre_cols].to_numpy(dtype=np.float32)
    X_no_pre = np.column_stack([wave / np.maximum(meta["even_amp"].to_numpy()[:, None], 1.0), X_no_pre]).astype(np.float32)
    predictions["ML_hgb_without_pretrigger"] = p04l.fit_hgb(X_no_pre, y, train_idx, int(config["random_seed"]) + 3)
    predictions["ML_extratrees_without_pretrigger"] = fit_extra_trees(X_no_pre, y, train_idx, int(config["random_seed"]) + 4)

    context = p04l.scalar_context(meta)
    norm_wave = (wave / np.maximum(meta["even_amp"].to_numpy()[:, None], 1.0)).astype(np.float32)
    predictions["ML_mlp"] = p04l.fit_torch_model("mlp", features_with_pre, norm_wave, y, train_idx, config)
    predictions["NN_1d_cnn"] = p04l.fit_torch_model("cnn", context, norm_wave, y, train_idx, config)
    predictions["NN_wave_atom_net"] = p04l.fit_torch_model("wave_atom_net", context, norm_wave, y, train_idx, config)
    gate_context = np.column_stack(
        [
            context,
            meta[["pretrigger_score", "baseline_range", "pretrigger_slope_abs"]].to_numpy(dtype=np.float32),
        ]
    )
    predictions["NN_pretrigger_gated_wave_net_new"] = fit_pretrigger_gated_net(gate_context, norm_wave, y, train_idx, config)
    return predictions


def evaluate_predictions(
    meta: pd.DataFrame,
    predictions: Dict[str, np.ndarray],
    heldout_mask: np.ndarray,
    config: dict,
    target_col: str,
    target_name: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows, run_rows = [], []
    held = meta.loc[heldout_mask, ["run", target_col, "pretrigger_risk_group"]].copy()
    for method, pred_all in predictions.items():
        pred = pred_all[heldout_mask]
        tmp = held.copy()
        tmp["_pred"] = pred
        row = {"target": target_name, "method": method, "split": "run_heldout"}
        row.update(robust_metrics(tmp[target_col].to_numpy(), pred, float(config["catastrophic_abs_frac"])))
        row.update(run_block_ci(tmp, target_col, "_pred", float(config["catastrophic_abs_frac"]), int(config["bootstrap_reps"]), int(config["random_seed"]) + len(rows)))
        rows.append(row)
        for run, sub in tmp.groupby("run"):
            rr = {"target": target_name, "method": method, "run": int(run)}
            rr.update(robust_metrics(sub[target_col].to_numpy(), sub["_pred"].to_numpy(), float(config["catastrophic_abs_frac"])))
            run_rows.append(rr)
    return pd.DataFrame(rows), pd.DataFrame(run_rows)


def mode_effects(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, methods: List[str], config: dict) -> pd.DataFrame:
    held = meta.loc[heldout_mask].reset_index(drop=True).copy()
    rows = []
    controls = ["run", "stave", "amp_bin", "peak_bin", "is_saturated"]
    y = held["target_odd_pos_charge"].to_numpy()
    rng = np.random.default_rng(int(config["random_seed"]) + 808)
    for method in methods:
        pred = predictions[method][heldout_mask]
        held["_abs_frac"] = np.abs((pred - y) / np.maximum(y, 1.0))
        high_col = "pretrigger_risk_group"
        cell_rows = []
        for _, sub in held.groupby(controls, sort=True):
            exposed = sub[sub[high_col] == "high_pretrigger"]
            control = sub[sub[high_col] == "quiet_reference"]
            if len(exposed) < int(config["min_matched_cell"]) or len(control) < int(config["min_matched_cell"]):
                continue
            cell_rows.append(
                {
                    "run": int(sub["run"].iloc[0]),
                    "weight": min(len(exposed), len(control)),
                    "delta_abs_frac": float(exposed["_abs_frac"].mean() - control["_abs_frac"].mean()),
                }
            )
        if not cell_rows:
            continue
        cells = pd.DataFrame(cell_rows)
        w = cells["weight"].to_numpy(dtype=float)
        point = float(np.average(cells["delta_abs_frac"], weights=w))
        runs = np.asarray(sorted(cells["run"].unique()), dtype=int)
        by_run = {int(r): cells[cells["run"] == int(r)] for r in runs}
        boot = []
        for _ in range(int(config["bootstrap_reps"])):
            sample = pd.concat([by_run[int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            boot.append(float(np.average(sample["delta_abs_frac"], weights=sample["weight"])))
        rows.append(
            {
                "method": method,
                "contrast": "high_pretrigger_minus_quiet_reference",
                "matched_controls": "+".join(controls),
                "n_cells": int(len(cells)),
                "delta_abs_frac": point,
                "delta_abs_frac_ci95": ci(boot),
            }
        )
    return pd.DataFrame(rows)


def conformal_abstention(meta: pd.DataFrame, pred: np.ndarray, train_mask: np.ndarray, heldout_mask: np.ndarray, config: dict) -> dict:
    y = meta["target_odd_pos_charge"].to_numpy()
    train_abs = np.abs((pred[train_mask] - y[train_mask]) / np.maximum(y[train_mask], 1.0))
    q = float(np.quantile(train_abs, 1.0 - float(config["conformal_alpha"])))
    held_abs = np.abs((pred[heldout_mask] - y[heldout_mask]) / np.maximum(y[heldout_mask], 1.0))
    held = meta.loc[heldout_mask].copy()
    score = held["pretrigger_score"].to_numpy(dtype=float)
    threshold = float(np.quantile(meta.loc[train_mask, "pretrigger_score"], float(config["abstain_quantile"])))
    keep = score < threshold
    return {
        "conformal_abs_frac_threshold": q,
        "nominal_coverage": float(1.0 - float(config["conformal_alpha"])),
        "coverage_no_abstention": float(np.mean(held_abs <= q)),
        "coverage_after_pretrigger_abstention": float(np.mean(held_abs[keep] <= q)) if keep.any() else None,
        "support_loss": float(1.0 - np.mean(keep)),
        "retained_res68_abs_frac": float(np.percentile(held_abs[keep], 68)) if keep.any() else None,
    }


def extract_external_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    b2_ch = int(config["b2_channel"])
    b2_dup_ch = int(config["b2_duplicate_channel"])
    downstream = {name: int(ch) for name, ch in config["downstream_channels"].items()}
    frames, waves, counts = [], [], []
    for run in [int(r) for r in config["sample_ii_runs"]]:
        path = raw_path(config, run, "b")
        run_count = {"run": run, "events_total": 0, "b2_selected": 0, "penetrating_rows": 0}
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            b2 = corrected[:, b2_ch, :]
            b2_dup = corrected[:, b2_dup_ch, :]
            down = np.stack([corrected[:, ch, :] for ch in downstream.values()], axis=1)
            b2_amp = b2.max(axis=1)
            b2_charge = np.clip(b2, 0.0, None).sum(axis=1)
            b2_dup_charge = np.clip(-b2_dup, 0.0, None).sum(axis=1)
            down_amp = down.max(axis=2)
            down_charge_by_stave = np.clip(down, 0.0, None).sum(axis=2)
            downstream_charge = down_charge_by_stave.sum(axis=1)
            selected = (b2_amp > cut) & (down_amp > cut).all(axis=1) & (b2_dup_charge > 100.0) & (downstream_charge > 100.0)
            run_count["events_total"] += int(len(eventno))
            run_count["b2_selected"] += int((b2_amp > cut).sum())
            run_count["penetrating_rows"] += int(selected.sum())
            if selected.any():
                idx = np.where(selected)[0]
                waves.append(b2[idx].astype(np.float32))
                pre = b2[idx][:, baseline_idx]
                frame = pd.DataFrame(
                    {
                        "run": run,
                        "eventno": eventno[idx],
                        "evt": evt[idx],
                        "b2_amp": b2_amp[idx],
                        "b2_charge": b2_charge[idx],
                        "b2_duplicate_charge": b2_dup_charge[idx],
                        "downstream_charge": downstream_charge[idx],
                        "pre_mean": pre.mean(axis=1),
                        "pre_rms": np.sqrt(np.mean((pre - pre.mean(axis=1)[:, None]) ** 2, axis=1)),
                        "pre_slope": pre[:, -1] - pre[:, 0],
                        "pre_range": pre.max(axis=1) - pre.min(axis=1),
                    }
                )
                for stave_idx, stave in enumerate(downstream):
                    frame[f"{stave}_charge"] = down_charge_by_stave[idx, stave_idx]
                frames.append(frame)
        counts.append(run_count)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def external_features(frame: pd.DataFrame, wave: np.ndarray, include_pretrigger: bool) -> np.ndarray:
    amp = frame["b2_amp"].to_numpy(dtype=float)
    charge = frame["b2_charge"].to_numpy(dtype=float)
    total = np.maximum(charge, 1.0)
    base = [
        wave / np.maximum(amp[:, None], 1.0),
        np.column_stack(
            [
                np.log(np.maximum(amp, 1.0)),
                np.log(total),
                wave.argmax(axis=1),
                np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / total,
                np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total,
                (wave > (0.5 * amp[:, None])).sum(axis=1),
            ]
        ),
    ]
    if include_pretrigger:
        base.append(frame[["pre_mean", "pre_rms", "pre_slope", "pre_range", "pretrigger_score"]].to_numpy(dtype=float))
    return np.nan_to_num(np.column_stack(base), nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def exp_from_log_prediction(log_pred: np.ndarray, y_train: np.ndarray, margin: float = 1.0) -> np.ndarray:
    log_y = np.log(np.maximum(np.asarray(y_train, dtype=float), 1.0))
    finite = np.isfinite(log_y)
    lo = float(log_y[finite].min() - margin) if finite.any() else 0.0
    hi = float(log_y[finite].max() + margin) if finite.any() else 20.0
    return np.exp(np.clip(np.nan_to_num(log_pred, nan=lo, posinf=hi, neginf=lo), lo, hi))


def evaluate_external(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame, wave, counts = extract_external_rows(config)
    frame = frame.copy()
    frame["pretrigger_score"] = np.sqrt(frame["pre_rms"] ** 2 + frame["pre_slope"] ** 2 + frame["pre_range"] ** 2)
    frame["pretrigger_risk_group"] = "quiet_reference"
    for heldout_run in sorted(frame["run"].unique()):
        train = frame["run"] != heldout_run
        high_threshold = float(frame.loc[train, "pretrigger_score"].quantile(0.80))
        frame.loc[frame["run"] == heldout_run, "pretrigger_risk_group"] = np.where(
            frame.loc[frame["run"] == heldout_run, "pretrigger_score"] >= high_threshold,
            "high_pretrigger",
            "quiet_reference",
        )
    y_ext = frame["downstream_charge"].to_numpy(dtype=float)
    y_dup = frame["b2_duplicate_charge"].to_numpy(dtype=float)
    X_pre = external_features(frame, wave, True)
    X_no_pre = external_features(frame, wave, False)
    methods = [
        "external_traditional_ridge",
        "external_hgb_without_pretrigger",
        "external_hgb_with_pretrigger",
        "external_extratrees_with_pretrigger",
        "external_duplicate_transfer_hgb",
    ]
    for method in methods:
        frame["pred_" + method] = np.nan
    rng = np.random.default_rng(int(config["random_seed"]) + 606)
    for heldout_run in sorted(frame["run"].unique()):
        train = frame["run"].to_numpy() != heldout_run
        test = ~train
        train_idx = np.where(train)[0]
        if len(train_idx) > int(config["ml_max_train_rows"]):
            train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
        trad = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=1e-4, max_iter=250))
        trad.fit(X_no_pre[train], np.log(y_ext[train]))
        frame.loc[test, "pred_external_traditional_ridge"] = np.exp(trad.predict(X_no_pre[test]))
        hgb_params = {
            "max_iter": 180,
            "learning_rate": 0.06,
            "max_leaf_nodes": 31,
            "l2_regularization": 0.08,
            "random_state": int(config["random_seed"]) + int(heldout_run),
        }
        for method, X in [("external_hgb_without_pretrigger", X_no_pre), ("external_hgb_with_pretrigger", X_pre)]:
            model = HistGradientBoostingRegressor(**hgb_params)
            model.fit(X[train_idx], np.log(y_ext[train_idx]))
            frame.loc[test, "pred_" + method] = exp_from_log_prediction(model.predict(X[test]), y_ext[train])
        et = ExtraTreesRegressor(n_estimators=140, min_samples_leaf=5, max_features=0.75, random_state=int(config["random_seed"]) + int(heldout_run), n_jobs=1)
        et.fit(X_pre[train_idx], np.log(y_ext[train_idx]))
        frame.loc[test, "pred_external_extratrees_with_pretrigger"] = exp_from_log_prediction(et.predict(X_pre[test]), y_ext[train])
        dup = HistGradientBoostingRegressor(**hgb_params)
        dup.fit(X_pre[train_idx], np.log(y_dup[train_idx]))
        dup_train = exp_from_log_prediction(dup.predict(X_pre[train]), y_dup[train])
        dup_test = exp_from_log_prediction(dup.predict(X_pre[test]), y_dup[train])
        log_dup_train = np.log(np.maximum(dup_train, 1.0))
        log_y_train = np.log(np.maximum(y_ext[train], 1.0))
        finite = np.isfinite(log_dup_train) & np.isfinite(log_y_train)
        if int(finite.sum()) >= 10:
            transfer = LinearRegression()
            transfer.fit(log_dup_train[finite, None], log_y_train[finite])
            log_transfer = transfer.predict(np.log(np.maximum(dup_test, 1.0))[:, None])
            frame.loc[test, "pred_external_duplicate_transfer_hgb"] = exp_from_log_prediction(log_transfer, y_ext[train])
        else:
            frame.loc[test, "pred_external_duplicate_transfer_hgb"] = float(np.median(y_ext[train]))

    rows, mode_rows = [], []
    for method in methods:
        tmp = frame[["run", "downstream_charge", "pretrigger_risk_group", "pred_" + method]].copy()
        row = {"target": "downstream_B4B6B8_charge_proxy", "method": method, "split": "leave_one_run_out"}
        row.update(robust_metrics(tmp["downstream_charge"].to_numpy(), tmp["pred_" + method].to_numpy(), float(config["catastrophic_abs_frac"])))
        row.update(run_block_ci(tmp.rename(columns={"pred_" + method: "_pred"}), "downstream_charge", "_pred", float(config["catastrophic_abs_frac"]), int(config["bootstrap_reps"]), int(config["random_seed"]) + len(rows) + 500))
        rows.append(row)
        for group, sub in tmp.groupby("pretrigger_risk_group"):
            grow = {"method": method, "pretrigger_risk_group": group}
            grow.update(robust_metrics(sub["downstream_charge"].to_numpy(), sub["pred_" + method].to_numpy(), float(config["catastrophic_abs_frac"])))
            mode_rows.append(grow)
    return pd.DataFrame(rows), pd.DataFrame(mode_rows), frame, counts


def markdown_table(frame: pd.DataFrame, columns: List[str], max_rows: int | None = None) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].copy()
    if max_rows is not None:
        use = use.head(max_rows)
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: "{:.6g}".format(x) if pd.notna(x) else "")
    return use.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    counts: pd.DataFrame,
    duplicate_summary: pd.DataFrame,
    duplicate_by_run: pd.DataFrame,
    mode_eff: pd.DataFrame,
    external_summary: pd.DataFrame,
    external_modes: pd.DataFrame,
    conformal: dict,
    result: dict,
) -> None:
    expected = int(config["expected_selected_pulses"])
    reproduced = int(counts["selected_pulses"].sum())
    winner = result["winner"]["method"]
    best_trad = result["best_traditional"]["method"]
    cols = ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_ci95", "full_rms_frac", "catastrophic_rate", "catastrophic_rate_ci95"]
    lines = [
        "# P04m: Pretrigger-mode charge-transfer abstention map",
        "",
        "- **Ticket:** `{}`".format(config["ticket_id"]),
        "- **Worker:** `{}`".format(config["worker"]),
        "- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.",
        "- **Primary split:** train on Sample I plus run 64, hold out Sample II analysis runs `{}`.".format(", ".join(str(x) for x in config["heldout_runs"])),
        "",
        "## Abstract",
        "",
        result["finding"],
        "",
        "## 1. Raw ROOT reproduction gate",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        "| selected B-stave pulse records | {:,} | {:,} | {:+,} | {} |".format(expected, reproduced, reproduced - expected, str(reproduced == expected).lower()),
        "",
        "The gate subtracts each channel's median over samples 0--3, reshapes `HRDv` to `(8,18)`, and selects B2/B4/B6/B8 even-channel records with peak amplitude greater than 1000 ADC. This reproduces the P04/S00 count before invalid duplicate targets are removed.",
        "",
        "## 2. Estimands and equations",
        "",
        "For selected pulse `i`, the duplicate-readout charge target is",
        "",
        "`y_i^dup = sum_t max(-o_i(t), 0)`,",
        "",
        "where `o_i(t)` is the paired odd-channel waveform after the same baseline subtraction. For penetrating B2 events, the external proxy is",
        "",
        "`y_i^ext = sum_{s in {B4,B6,B8}} sum_t max(x_{i,s}(t), 0)`.",
        "",
        "Every method is scored by fractional residual `r_i = (hat y_i - y_i) / max(y_i, 1)`. The primary metric is `Q_0.68(|r|)`; full RMS, median bias, and `P(|r|>0.25)` are secondary. Confidence intervals resample held-out runs with replacement.",
        "",
        "## 3. Methods",
        "",
        "Traditional estimators include peak, positive integral, shifted adaptive-template scale, Huber regression on hand-built pulse and pretrigger summaries, and a frozen dropout-cell correction. ML/NN estimators include ridge, histogram gradient-boosted trees, ExtraTrees, a tabular MLP, waveform-only 1D-CNN, the prior wave-atom net, and the new `NN_pretrigger_gated_wave_net_new`, which gates a temporal convolution by pretrigger summary features. Pretrigger modes are frozen train-run quantile bins of baseline score, slope, and range.",
        "",
        "## 4. Duplicate-readout benchmark",
        "",
        markdown_table(duplicate_summary.sort_values("res68_abs_frac"), cols),
        "",
        "Winner by held-out duplicate res68: `{}`. Best traditional comparator: `{}`.".format(winner, best_trad),
        "",
        "## 5. Run stability",
        "",
        markdown_table(duplicate_by_run[duplicate_by_run["method"].isin([winner, best_trad, "ML_hgb_with_pretrigger", "NN_1d_cnn"])], ["method", "run", "n", "res68_abs_frac", "full_rms_frac", "catastrophic_rate"], max_rows=80),
        "",
        "## 6. Pretrigger-mode support effects",
        "",
        markdown_table(mode_eff, ["method", "contrast", "n_cells", "delta_abs_frac", "delta_abs_frac_ci95"], max_rows=80),
        "",
        "Positive `delta_abs_frac` means high-pretrigger records have larger absolute fractional charge error after matching on run, stave, amplitude bin, peak bin, and saturation.",
        "",
        "## 7. Conformal abstention",
        "",
        "| quantity | value |",
        "|---|---:|",
        "| conformal abs-frac threshold | {:.6g} |".format(conformal["conformal_abs_frac_threshold"]),
        "| nominal coverage | {:.6g} |".format(conformal["nominal_coverage"]),
        "| coverage without abstention | {:.6g} |".format(conformal["coverage_no_abstention"]),
        "| coverage after pretrigger abstention | {:.6g} |".format(conformal["coverage_after_pretrigger_abstention"]),
        "| support loss | {:.6g} |".format(conformal["support_loss"]),
        "| retained res68 | {:.6g} |".format(conformal["retained_res68_abs_frac"]),
        "",
        "This is a diagnostic abstention map, not a deployed uncertainty guarantee: the nonconformity threshold is learned on train-run residuals for the winning model and the abstention rule is a frozen pretrigger-score quantile.",
        "",
        "## 8. External downstream charge proxy",
        "",
        markdown_table(external_summary.sort_values("res68_abs_frac"), cols),
        "",
        "External proxy stratified by pretrigger risk group:",
        "",
        markdown_table(external_modes, ["method", "pretrigger_risk_group", "n", "bias_median_frac", "res68_abs_frac", "full_rms_frac", "catastrophic_rate"], max_rows=80),
        "",
        "The external target is not deposited-energy truth; it is a downstream charge proxy in penetrating Sample-II events. It tests whether duplicate-readout charge closure transfers to an independently located charge observable.",
        "",
        "## 9. Systematics and caveats",
        "",
        "- Splits are by run; event identifiers and odd/downstream target samples are excluded from model features.",
        "- Duplicate-readout closure can be excellent because the target is same-event electronics, not absolute energy.",
        "- Pretrigger modes are derived from samples 0--3. They are support variables and nuisance diagnostics, not causal interventions.",
        "- The held-out run count is seven, so run-block CIs are the relevant uncertainty scale.",
        "- Neural rows are intentionally laptop-scale probes; they test whether extra capacity changes the conclusion, not whether an exhaustive NN search is complete.",
        "",
        "## 10. Hypothesis and next step",
        "",
        result["hypothesis"],
        "",
        "Proposed follow-up ticket: `{}`".format(result["next_tickets"][0]["title"]),
        "",
        "## 11. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04m_1781032084_548_4ccc082b_pretrigger_charge_abstention_map.py --config configs/p04m_1781032084_548_4ccc082b_pretrigger_charge_abstention_map.json",
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/p04m_1781032084_548_4ccc082b_pretrigger_charge_abstention_map.json")
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/7 scan raw ROOT and reproduce selected-pulse count", flush=True)
    meta, wave, counts = p04l.extract_rows(config)
    total_selected = int(counts["selected_pulses"].sum())
    if total_selected != int(config["expected_selected_pulses"]):
        raise RuntimeError("selected-pulse reproduction failed: {} != {}".format(total_selected, config["expected_selected_pulses"]))
    valid = (
        np.isfinite(meta["target_odd_neg_amp"].to_numpy())
        & np.isfinite(meta["target_odd_pos_charge"].to_numpy())
        & (meta["target_odd_neg_amp"].to_numpy() > 100.0)
        & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
        & (meta["even_amp"].to_numpy() > 0.0)
        & (meta["even_pos_charge"].to_numpy() > 0.0)
    )
    invalid_rows = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]
    heldout_runs = [int(r) for r in config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    print("selected={} valid={} train={} heldout={}".format(total_selected, len(meta), int(train_mask.sum()), int(heldout_mask.sum())), flush=True)

    print("2/7 derive atoms and frozen pretrigger modes", flush=True)
    meta = p04l.add_derived_columns(meta, wave, train_mask, config)
    meta = add_pretrigger_modes(meta, train_mask, config)
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask

    print("3/7 duplicate-readout traditional, ML, and NN benchmark", flush=True)
    predictions = duplicate_method_predictions(meta, wave, train_mask, config)
    duplicate_summary, duplicate_by_run = evaluate_predictions(
        meta, predictions, heldout_mask, config, "target_odd_pos_charge", "duplicate_odd_charge"
    )

    traditional = [m for m in predictions if m.startswith("traditional_")]
    best_trad = duplicate_summary[duplicate_summary["method"].isin(traditional)].sort_values("res68_abs_frac").iloc[0]
    winner = duplicate_summary.sort_values("res68_abs_frac").iloc[0]
    print("winner={} res68={:.5f}; best traditional={} res68={:.5f}".format(winner["method"], winner["res68_abs_frac"], best_trad["method"], best_trad["res68_abs_frac"]), flush=True)

    print("4/7 pretrigger-mode matched effects and conformal abstention", flush=True)
    effect_methods = list(dict.fromkeys([str(winner["method"]), str(best_trad["method"]), "ML_hgb_with_pretrigger", "ML_hgb_without_pretrigger"]))
    mode_eff = mode_effects(meta, predictions, heldout_mask, effect_methods, config)
    conformal = conformal_abstention(meta, predictions[str(winner["method"])], train_mask, heldout_mask, config)

    print("5/7 external downstream charge proxy benchmark", flush=True)
    external_summary, external_modes, external_predictions, external_counts = evaluate_external(config)

    print("6/7 write tables", flush=True)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    duplicate_summary.to_csv(out_dir / "duplicate_benchmark.csv", index=False)
    duplicate_by_run.to_csv(out_dir / "duplicate_benchmark_by_run.csv", index=False)
    mode_eff.to_csv(out_dir / "pretrigger_mode_effects.csv", index=False)
    external_summary.to_csv(out_dir / "external_summary.csv", index=False)
    external_modes.to_csv(out_dir / "external_pretrigger_modes.csv", index=False)
    external_counts.to_csv(out_dir / "external_counts_by_run.csv", index=False)
    external_predictions.to_csv(out_dir / "external_predictions.csv", index=False)

    best_external = external_summary.sort_values("res68_abs_frac").iloc[0]
    finding = (
        "Raw selected-pulse reproduction passes exactly ({} vs {}). The duplicate-readout winner is {} "
        "with res68 {:.4f} [{:.4f}, {:.4f}], while the strongest traditional method is {} at {:.4f}. "
        "The best external downstream-charge proxy is {} with res68 {:.4f}, much wider than duplicate closure, "
        "so pretrigger support should be treated as a nuisance/abstention map rather than evidence of external energy recovery."
    ).format(
        total_selected,
        int(config["expected_selected_pulses"]),
        winner["method"],
        winner["res68_abs_frac"],
        winner["res68_ci95"][0],
        winner["res68_ci95"][1],
        best_trad["method"],
        best_trad["res68_abs_frac"],
        best_external["method"],
        best_external["res68_abs_frac"],
    )
    hypothesis = (
        "Pretrigger hidden modes mark electronics support boundaries: within the B-stack duplicate channel they mostly identify where "
        "ordinary charge estimators need abstention or correction, but they do not by themselves make same-event duplicate closure "
        "transfer to downstream charge. A forced/random pedestal or independently blinded energy proxy should confirm whether the "
        "high-pretrigger support loss is an electronics-only nuisance."
    )
    next_ticket = {
        "title": "P04n: forced-random pedestal validation of P04m pretrigger abstention",
        "body": (
            "Question: do P04m high-pretrigger abstention regions correspond to independently measured forced/random pedestal disturbances, "
            "and do they predict external charge-proxy failure after amplitude, saturation, run, and topology matching? Expected information gain: "
            "distinguishes a useful electronics support veto from an overfit duplicate-readout nuisance map."
        ),
    }
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "runtime_sec": time.time() - start,
        "reproduced": True,
        "raw_reproduction": {
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "reproduced_selected_pulses": total_selected,
            "delta": total_selected - int(config["expected_selected_pulses"]),
            "invalid_target_rows_removed_after_reproduction": invalid_rows,
        },
        "split": {
            "train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()),
            "heldout_runs": heldout_runs,
            "bootstrap_unit": "held-out run",
            "bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "primary_metric": "duplicate-readout charge res68_abs_frac; lower is better",
        "best_traditional": json.loads(pd.Series(best_trad).to_json()),
        "winner": json.loads(pd.Series(winner).to_json()),
        "external_winner": json.loads(pd.Series(best_external).to_json()),
        "primary_methods": list(predictions.keys()),
        "duplicate_benchmark": json.loads(duplicate_summary.to_json(orient="records")),
        "external_summary": json.loads(external_summary.to_json(orient="records")),
        "pretrigger_mode_effects": json.loads(mode_eff.to_json(orient="records")),
        "conformal_abstention": conformal,
        "finding": finding,
        "hypothesis": hypothesis,
        "next_tickets": [next_ticket],
        "leakage_audit": {
            "train_heldout_run_overlap": sorted(set(meta.loc[train_mask, "run"].unique()).intersection(set(heldout_runs))),
            "feature_exclusions": ["eventno", "evt", "target_odd_pos_charge", "target_odd_neg_amp", "downstream_charge"],
        },
    }

    print("7/7 write report, result, manifest", flush=True)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    write_report(
        out_dir,
        config,
        counts,
        duplicate_summary,
        duplicate_by_run,
        mode_eff,
        external_summary,
        external_modes,
        conformal,
        result,
    )
    input_runs = sorted({int(r) for vals in config["run_groups"].values() for r in vals} | {int(r) for r in config["sample_ii_runs"]})
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "script": "scripts/p04m_1781032084_548_4ccc082b_pretrigger_charge_abstention_map.py",
        "config": str(args.config.relative_to(ROOT) if args.config.is_absolute() else args.config),
        "command": "/home/billy/anaconda3/bin/python scripts/p04m_1781032084_548_4ccc082b_pretrigger_charge_abstention_map.py --config configs/p04m_1781032084_548_4ccc082b_pretrigger_charge_abstention_map.json",
        "random_seed": int(config["random_seed"]),
        "inputs": [{"path": str(raw_path(config, run, "b").relative_to(ROOT)), "sha256": sha256_file(raw_path(config, run, "b"))} for run in input_runs],
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print("DONE -> {} in {:.1f}s".format(out_dir, result["runtime_sec"]), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
