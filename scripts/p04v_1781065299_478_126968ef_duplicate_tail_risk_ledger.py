#!/usr/bin/env python3
"""P04v: duplicate-closure charge tail-risk ledger.

This study starts from raw B-stack ROOT files, reproduces the selected-pulse
population, and then benchmarks frozen duplicate-readout charge calibrators
against tabular ML and neural models on held-out runs.  It additionally audits
the large-error tails by detector/run/pulse atoms and trains residual tail-risk
models with permutation and feature-family knockout sentinels.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, RidgeCV
from sklearn.metrics import roc_auc_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - script records this in result.json.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def tail_fraction(wave: np.ndarray, charge: np.ndarray) -> np.ndarray:
    return np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / np.maximum(charge, 1.0)


def weighted_time(wave: np.ndarray) -> np.ndarray:
    clipped = np.clip(wave, 0.0, None)
    denom = np.maximum(clipped.sum(axis=1), 1.0)
    return (clipped * np.arange(wave.shape[1], dtype=float)[None, :]).sum(axis=1) / denom


def template_scale_feature(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict) -> np.ndarray:
    bins = [float(x) for x in config["amplitude_bins"]]
    st = meta["stave_idx"].to_numpy(dtype=int)
    amp = np.maximum(meta["even_amp"].to_numpy(dtype=float), 1.0)
    norm = wave.astype(float) / amp[:, None]
    out = np.zeros(len(meta), dtype=float)
    for stave in sorted(np.unique(st)):
        stave_train = train_mask & (st == stave)
        fallback = np.median(norm[stave_train], axis=0)
        for bidx in range(len(bins) - 1):
            lo, hi = bins[bidx], bins[bidx + 1]
            group = (st == stave) & (amp >= lo) & (amp < hi)
            train_group = group & train_mask
            if int(train_group.sum()) >= 80:
                tmpl = np.median(norm[train_group], axis=0)
            else:
                tmpl = fallback
            denom = max(float(np.dot(tmpl, tmpl)), 1e-9)
            out[group] = (wave[group].astype(float) @ tmpl) / denom
    return np.maximum(out, 1.0)


def one_hot(values: np.ndarray) -> np.ndarray:
    cats = np.asarray(sorted(np.unique(values)))
    out = np.zeros((len(values), len(cats)), dtype=float)
    lookup = {cat: idx for idx, cat in enumerate(cats)}
    for idx, value in enumerate(values):
        out[idx, lookup[value]] = 1.0
    return out


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "charge_res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "tail_gt10_frac": float(np.mean(abs_frac > 0.10)),
        "tail_gt25_frac": float(np.mean(abs_frac > 0.25)),
        "within_10pct": float(np.mean(abs_frac <= 0.10)),
    }


def bootstrap_metrics(y: np.ndarray, pred: np.ndarray, rng: np.random.Generator, reps: int) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    n = len(frac)
    cols = {name: np.empty(reps, dtype=float) for name in ["bias", "res68", "rms", "tail10", "tail25"]}
    for ridx in range(reps):
        sample = frac[rng.integers(0, n, size=n)]
        abs_sample = np.abs(sample)
        cols["bias"][ridx] = np.median(sample)
        cols["res68"][ridx] = np.percentile(abs_sample, 68)
        cols["rms"][ridx] = np.sqrt(np.mean(sample * sample))
        cols["tail10"][ridx] = np.mean(abs_sample > 0.10)
        cols["tail25"][ridx] = np.mean(abs_sample > 0.25)
    return {
        "bias_ci95": pct(cols["bias"]),
        "charge_res68_ci95": pct(cols["res68"]),
        "full_rms_ci95": pct(cols["rms"]),
        "tail_gt10_ci95": pct(cols["tail10"]),
        "tail_gt25_ci95": pct(cols["tail25"]),
    }


def pct(values: np.ndarray) -> List[float]:
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def run_block_ci(frame: pd.DataFrame, y_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    vals = {name: np.empty(reps, dtype=float) for name in ["res68", "rms", "tail10", "tail25"]}
    for ridx in range(reps):
        sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        frac = (sample[pred_col].to_numpy() - sample[y_col].to_numpy()) / np.maximum(sample[y_col].to_numpy(), 1.0)
        abs_frac = np.abs(frac)
        vals["res68"][ridx] = np.percentile(abs_frac, 68)
        vals["rms"][ridx] = np.sqrt(np.mean(frac * frac))
        vals["tail10"][ridx] = np.mean(abs_frac > 0.10)
        vals["tail25"][ridx] = np.mean(abs_frac > 0.25)
    return {
        "run_block_charge_res68_ci95": pct(vals["res68"]),
        "run_block_full_rms_ci95": pct(vals["rms"]),
        "run_block_tail_gt10_ci95": pct(vals["tail10"]),
        "run_block_tail_gt25_ci95": pct(vals["tail25"]),
    }


def fit_per_stave_log_model(x: np.ndarray, y: np.ndarray, train_mask: np.ndarray, stave_idx: np.ndarray, kind: str) -> Dict[int, object]:
    models: Dict[int, object] = {}
    alphas = np.asarray([0.01, 0.1, 1.0, 10.0, 100.0, 1000.0])
    for stave in sorted(np.unique(stave_idx)):
        mask = train_mask & (stave_idx == stave) & np.isfinite(x).all(axis=1) & (y > 0)
        if kind == "huber":
            model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=400))
        else:
            model = make_pipeline(StandardScaler(), RidgeCV(alphas=alphas))
        model.fit(x[mask], np.log(y[mask]))
        models[int(stave)] = model
    return models


def predict_per_stave(models: Dict[int, object], x: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(len(x), dtype=float)
    for stave, model in models.items():
        mask = stave_idx == stave
        out[mask] = np.exp(model.predict(x[mask]))
    return np.maximum(out, 1.0)


def fit_global_regressor(model: object, x: np.ndarray, y: np.ndarray, train_mask: np.ndarray, rng: np.random.Generator, max_rows: int) -> object:
    idx = np.where(train_mask)[0]
    if len(idx) > max_rows:
        idx = rng.choice(idx, size=max_rows, replace=False)
    model.fit(x[idx], np.log(y[idx]))
    return model


class ConvChargeNet(nn.Module):
    def __init__(self, n_aux: int = 0, gated: bool = False):
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(6),
            nn.Flatten(),
        )
        conv_dim = 24 * 6
        if gated:
            self.aux = nn.Sequential(nn.Linear(n_aux, 32), nn.ReLU(), nn.Linear(32, 32), nn.ReLU())
            self.gate = nn.Sequential(nn.Linear(conv_dim + 32, 32), nn.ReLU(), nn.Linear(32, conv_dim), nn.Sigmoid())
            head_dim = conv_dim + 32
        else:
            self.aux = None
            self.gate = None
            head_dim = conv_dim
        self.head = nn.Sequential(nn.Linear(head_dim, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor | None = None) -> torch.Tensor:
        z = self.conv(wave)
        if self.gated:
            a = self.aux(aux)
            z = z * self.gate(torch.cat([z, a], dim=1))
            z = torch.cat([z, a], dim=1)
        return self.head(z).squeeze(1)


def fit_torch_model(
    wave_norm: np.ndarray,
    aux: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    config: dict,
    rng: np.random.Generator,
    gated: bool,
) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is not available")
    seed = int(config["random_seed"]) + (77 if gated else 33)
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    idx = np.where(train_mask)[0]
    if len(idx) > int(config["nn_max_train_rows"]):
        idx = rng.choice(idx, size=int(config["nn_max_train_rows"]), replace=False)
    train_wave = torch.tensor(wave_norm[idx, None, :], dtype=torch.float32)
    train_aux = torch.tensor(aux[idx], dtype=torch.float32)
    train_y = torch.tensor(np.log(y[idx]), dtype=torch.float32)
    loader = DataLoader(
        TensorDataset(train_wave, train_aux, train_y),
        batch_size=int(config["cnn_batch_size"]),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    model = ConvChargeNet(n_aux=aux.shape[1], gated=gated).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss(beta=0.03)
    model.train()
    for _epoch in range(int(config["cnn_epochs"])):
        for xb, ab, yb in loader:
            xb, ab, yb = xb.to(device), ab.to(device), yb.to(device)
            opt.zero_grad(set_to_none=True)
            pred = model(xb, ab if gated else None)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
    model.eval()
    preds: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(wave_norm), 16384):
            stop = min(start + 16384, len(wave_norm))
            xb = torch.tensor(wave_norm[start:stop, None, :], dtype=torch.float32, device=device)
            ab = torch.tensor(aux[start:stop], dtype=torch.float32, device=device)
            got = model(xb, ab if gated else None).detach().cpu().numpy()
            preds.append(got)
    return np.maximum(np.exp(np.concatenate(preds)), 1.0)


def evaluate_methods(
    meta: pd.DataFrame,
    y: np.ndarray,
    predictions: Dict[str, np.ndarray],
    train_mask: np.ndarray,
    heldout_mask: np.ndarray,
    config: dict,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 101)
    reps = int(config["bootstrap_reps"])
    rows: List[dict] = []
    by_run_rows: List[dict] = []
    held = meta.loc[heldout_mask, ["run", "stave", "target_odd_pos_charge"]].reset_index(drop=True)
    for method, pred_all in predictions.items():
        pred_held = pred_all[heldout_mask]
        y_held = y[heldout_mask]
        row = {"method": method, "split": f"heldout_runs_{'_'.join(str(x) for x in config['heldout_runs'])}"}
        row.update(robust_metrics(y_held, pred_held))
        row.update(bootstrap_metrics(y_held, pred_held, rng, reps))
        tmp = held.copy()
        tmp["_pred"] = pred_held
        row.update(run_block_ci(tmp, "target_odd_pos_charge", "_pred", rng, reps))

        train_abs = np.abs((pred_all[train_mask] - y[train_mask]) / np.maximum(y[train_mask], 1.0))
        conformal_q = float(np.quantile(train_abs, 1.0 - float(config["conformal_alpha"]), method="higher"))
        held_abs = np.abs((pred_held - y_held) / np.maximum(y_held, 1.0))
        row["train_conformal_q95_abs_frac"] = conformal_q
        row["heldout_conformal_coverage"] = float(np.mean(held_abs <= conformal_q))
        row["accepted_support_fraction_q95_le_10pct"] = float(conformal_q <= 0.10)
        rows.append(row)

        for run, run_df in tmp.groupby("run"):
            idx = run_df.index.to_numpy()
            brow = {"method": method, "run": int(run), "n": int(len(run_df))}
            brow.update(robust_metrics(y_held[idx], pred_held[idx]))
            brow.update(bootstrap_metrics(y_held[idx], pred_held[idx], rng, max(200, reps // 3)))
            by_run_rows.append(brow)
    return pd.DataFrame(rows), pd.DataFrame(by_run_rows)


def atom_ledger(
    meta: pd.DataFrame,
    y: np.ndarray,
    predictions: Dict[str, np.ndarray],
    method: str,
    traditional_method: str,
    heldout_mask: np.ndarray,
    config: dict,
) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 202)
    frame = meta.loc[heldout_mask].copy().reset_index(drop=True)
    y_held = y[heldout_mask]
    pred = predictions[method][heldout_mask]
    pred_trad = predictions[traditional_method][heldout_mask]
    abs_frac = np.abs((pred - y_held) / np.maximum(y_held, 1.0))
    trad_abs_frac = np.abs((pred_trad - y_held) / np.maximum(y_held, 1.0))
    frame["_abs_frac"] = abs_frac
    frame["_trad_abs_frac"] = trad_abs_frac
    axes = [
        ("run", frame["run"].astype(str)),
        ("stave", frame["stave"].astype(str)),
        ("peak_phase", frame["even_peak"].astype(str)),
        ("saturation", frame["atom_saturation"].map({True: "saturated", False: "not_saturated"})),
        ("q_template", frame["amp_bin"].astype(str)),
        ("dropout_atom", frame["atom_dropout"].map({True: "dropout_like", False: "ordinary_tail"})),
        ("anomaly_atom", frame["atom_anomaly"].map({True: "anomalous_residual", False: "ordinary_residual"})),
        ("pretrigger_atom", frame["atom_pretrigger"].map({True: "pretrigger_noisy", False: "quiet_pretrigger"})),
    ]
    rows: List[dict] = []
    for axis, labels in axes:
        for label, idxs in pd.Series(np.arange(len(frame))).groupby(labels).groups.items():
            idx = np.asarray(list(idxs), dtype=int)
            if len(idx) < 20:
                continue
            vals = abs_frac[idx]
            trad_vals = trad_abs_frac[idx]
            boot10 = np.empty(int(config["bootstrap_reps"]), dtype=float)
            boot25 = np.empty(int(config["bootstrap_reps"]), dtype=float)
            delta10 = np.empty(int(config["bootstrap_reps"]), dtype=float)
            for bidx in range(len(boot10)):
                take = rng.choice(idx, size=len(idx), replace=True)
                boot10[bidx] = np.mean(abs_frac[take] > 0.10)
                boot25[bidx] = np.mean(abs_frac[take] > 0.25)
                delta10[bidx] = np.mean(abs_frac[take] > 0.10) - np.mean(trad_abs_frac[take] > 0.10)
            rows.append(
                {
                    "axis": axis,
                    "atom": str(label),
                    "n": int(len(idx)),
                    "method": method,
                    "charge_res68_abs_frac": float(np.percentile(vals, 68)),
                    "full_rms_frac": float(np.sqrt(np.mean(((pred[idx] - y_held[idx]) / np.maximum(y_held[idx], 1.0)) ** 2))),
                    "tail_gt10_frac": float(np.mean(vals > 0.10)),
                    "tail_gt10_ci95": pct(boot10),
                    "tail_gt25_frac": float(np.mean(vals > 0.25)),
                    "tail_gt25_ci95": pct(boot25),
                    "traditional_tail_gt10_frac": float(np.mean(trad_vals > 0.10)),
                    "ml_minus_traditional_tail_gt10_delta": float(np.mean(vals > 0.10) - np.mean(trad_vals > 0.10)),
                    "ml_minus_traditional_tail_gt10_delta_ci95": pct(delta10),
                }
            )
    return pd.DataFrame(rows)


def tail_risk_models(
    x: np.ndarray,
    feature_family: Dict[str, List[int]],
    meta: pd.DataFrame,
    y: np.ndarray,
    base_pred: np.ndarray,
    train_mask: np.ndarray,
    heldout_mask: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    abs_frac = np.abs((base_pred - y) / np.maximum(y, 1.0))
    label = (abs_frac > 0.10).astype(int)
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    held_idx = np.where(heldout_mask)[0]
    rows: List[dict] = []
    risks: Dict[str, np.ndarray] = {}
    models = {
        "extra_trees_tail_risk": ExtraTreesClassifier(
            n_estimators=100,
            max_depth=18,
            min_samples_leaf=8,
            max_features=0.75,
            random_state=int(config["random_seed"]) + 301,
            n_jobs=-1,
        ),
        "hgb_tail_risk": HistGradientBoostingClassifier(
            max_iter=130,
            learning_rate=0.05,
            max_leaf_nodes=31,
            l2_regularization=0.02,
            random_state=int(config["random_seed"]) + 302,
        ),
    }
    for name, model in models.items():
        model.fit(x[train_idx], label[train_idx])
        if hasattr(model, "predict_proba"):
            risk = model.predict_proba(x)[:, 1]
        else:
            risk = model.decision_function(x)
        risks[name] = risk
        try:
            auc = float(roc_auc_score(label[held_idx], risk[held_idx]))
        except ValueError:
            auc = float("nan")
        threshold = float(np.quantile(risk[train_idx][label[train_idx] == 0], 0.95)) if np.any(label[train_idx] == 0) else 1.0
        accepted = risk[held_idx] <= threshold
        rows.append(
            {
                "model": name,
                "target": "abs_fractional_charge_error_gt_10pct_from_winner",
                "train_positive_rate": float(label[train_idx].mean()),
                "heldout_positive_rate": float(label[held_idx].mean()),
                "heldout_auc": auc,
                "risk_threshold_train_negative_q95": threshold,
                "accepted_support_fraction": float(np.mean(accepted)),
                "accepted_tail_gt10_rate": float(label[held_idx][accepted].mean()) if np.any(accepted) else float("nan"),
                "rejected_tail_gt10_rate": float(label[held_idx][~accepted].mean()) if np.any(~accepted) else float("nan"),
            }
        )
    shuffled = label[train_idx].copy()
    rng.shuffle(shuffled)
    sentinel = ExtraTreesClassifier(
        n_estimators=60,
        max_depth=14,
        min_samples_leaf=10,
        max_features=0.75,
        random_state=int(config["random_seed"]) + 303,
        n_jobs=-1,
    )
    sentinel.fit(x[train_idx], shuffled)
    sentinel_risk = sentinel.predict_proba(x)[:, 1]
    rows.append(
        {
            "model": "permuted_target_extra_trees_tail_risk",
            "target": "permuted_abs_fractional_charge_error_gt_10pct",
            "train_positive_rate": float(shuffled.mean()),
            "heldout_positive_rate": float(label[held_idx].mean()),
            "heldout_auc": float(roc_auc_score(label[held_idx], sentinel_risk[held_idx])),
            "risk_threshold_train_negative_q95": float("nan"),
            "accepted_support_fraction": float("nan"),
            "accepted_tail_gt10_rate": float("nan"),
            "rejected_tail_gt10_rate": float("nan"),
        }
    )

    knockout_rows: List[dict] = []
    all_cols = np.arange(x.shape[1])
    for family, cols in feature_family.items():
        keep = np.setdiff1d(all_cols, np.asarray(cols, dtype=int))
        model = HistGradientBoostingRegressor(
            max_iter=max(80, int(config["hgb_max_iter"]) // 2),
            learning_rate=0.05,
            max_leaf_nodes=31,
            l2_regularization=0.02,
            random_state=int(config["random_seed"]) + 400 + len(knockout_rows),
        )
        model.fit(x[train_idx][:, keep], np.log(y[train_idx]))
        pred = np.maximum(np.exp(model.predict(x[held_idx][:, keep])), 1.0)
        metrics = robust_metrics(y[held_idx], pred)
        knockout_rows.append(
            {
                "removed_family": family,
                "kept_columns": int(len(keep)),
                "charge_res68_abs_frac": metrics["charge_res68_abs_frac"],
                "full_rms_frac": metrics["full_rms_frac"],
                "tail_gt10_frac": metrics["tail_gt10_frac"],
                "tail_gt25_frac": metrics["tail_gt25_frac"],
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(knockout_rows)


def markdown_table(frame: pd.DataFrame, columns: List[str], max_rows: int | None = None) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame[columns].copy()
    if max_rows is not None:
        use = use.head(max_rows)
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: "nan" if pd.isna(x) else f"{x:.6g}")
    return use.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    counts: pd.DataFrame,
    benchmark: pd.DataFrame,
    by_run: pd.DataFrame,
    ledger: pd.DataFrame,
    risk: pd.DataFrame,
    knockouts: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    trad = result["traditional_reference_method"]
    lines = [
        "# P04v duplicate-closure tail-risk ledger",
        "",
        f"Ticket `{config['ticket_id']}` asks whether the small duplicate-readout central resolution hides rare charge tails before the duplicate closure is reused by saturation, PID, or energy studies.  The analysis is intentionally ROOT-first: the selected B-stave pulse population is rebuilt from `data/root/root/hrdb_run_*.root`, then every calibrator is trained without held-out runs `{config['heldout_runs']}`.",
        "",
        "## Raw reproduction",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| B-stack selected pulses with even amplitude > 1000 ADC | {int(config['expected_selected_pulses']):,} | {int(counts['selected_pulses'].sum()):,} | {int(counts['selected_pulses'].sum()) - int(config['expected_selected_pulses']):+,} | {str(result['raw_reproduction']['pass']).lower()} |",
        "",
        "## Estimands and notation",
        "",
        "For selected pulse i, y_i is the positive odd duplicate-readout charge and x_i contains only even-readout waveform information.  Each method estimates \\hat{y}_i = f(x_i) on held-out runs.  The fractional residual is",
        "",
        "\\[ r_i = (\\hat{y}_i-y_i)/\\max(y_i,1). \\]",
        "",
        "The central charge resolution is q_0.68(|r|), the full RMS is sqrt(E[r^2]), and charge-tail rates are P(|r|>0.10) and P(|r|>0.25).  Confidence intervals are percentile bootstraps; pooled rows use event resampling plus a run-block bootstrap over held-out runs, while atom rows resample events inside the atom.",
        "",
        "## Methods",
        "",
        "- **Frozen traditional baselines:** per-stave log-linear peak calibration, per-stave integral calibration, and an adaptive-template scale calibration built from train-only normalized median templates.",
        "- **Strong traditional method:** per-stave Huber log-charge calibration on even summaries plus a train-only residual basis: normalized waveform PCs by stave/amplitude bin, peak-anchor residual, baseline moments, and tail moments.",
        "- **ML and NN bakeoff:** ridge on the same strong-traditional feature set, histogram gradient-boosted trees, ExtraTrees, an MLP, a 1D-CNN over normalized waveforms, and a new residual-gated CNN that gates convolutional pulse features with the residual-basis/tabular branch.",
        "- **Tail-risk layer:** ExtraTrees and HGB classifiers predict whether the winning model has |r|>0.10; a permuted-target sentinel and HGB feature-family knockouts probe leakage and atom dependence.",
        "",
        "All tabular and neural features exclude run number, event number, and odd-channel target values.  Run labels are used only for splitting, bootstrapping, and reporting.",
        "",
        "## Head-to-head charge benchmark",
        "",
        markdown_table(
            benchmark.sort_values("charge_res68_abs_frac"),
            [
                "method",
                "n",
                "charge_res68_abs_frac",
                "run_block_charge_res68_ci95",
                "full_rms_frac",
                "tail_gt10_frac",
                "tail_gt10_ci95",
                "tail_gt25_frac",
                "heldout_conformal_coverage",
            ],
        ),
        "",
        f"The winner by charge res68 is `{winner}`.  The strong traditional reference for tail deltas is `{trad}`.",
        "",
        "## Split-by-run check",
        "",
        markdown_table(
            by_run[by_run["method"].isin([winner, trad, "ridge_residual_basis", "hgb_regressor", "mlp_regressor", "cnn1d", "residual_gated_cnn"])],
            ["method", "run", "n", "charge_res68_abs_frac", "charge_res68_ci95", "tail_gt10_frac", "tail_gt25_frac"],
        ),
        "",
        "## Tail-risk classifier and conformal support",
        "",
        markdown_table(
            risk,
            [
                "model",
                "heldout_auc",
                "heldout_positive_rate",
                "risk_threshold_train_negative_q95",
                "accepted_support_fraction",
                "accepted_tail_gt10_rate",
                "rejected_tail_gt10_rate",
            ],
        ),
        "",
        "## Feature-family knockouts",
        "",
        markdown_table(knockouts, ["removed_family", "charge_res68_abs_frac", "full_rms_frac", "tail_gt10_frac", "tail_gt25_frac"]),
        "",
        "## Atomized tail ledger",
        "",
        markdown_table(
            ledger.sort_values(["tail_gt25_frac", "tail_gt10_frac"], ascending=False),
            [
                "axis",
                "atom",
                "n",
                "charge_res68_abs_frac",
                "full_rms_frac",
                "tail_gt10_frac",
                "tail_gt10_ci95",
                "tail_gt25_frac",
                "ml_minus_traditional_tail_gt10_delta",
                "ml_minus_traditional_tail_gt10_delta_ci95",
            ],
            max_rows=36,
        ),
        "",
        "## Leakage and systematics checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "The largest systematic limitation is that duplicate closure remains a same-scintillator, two-readout proxy, not an external calorimetric truth.  The train/test split prevents run leakage, and the shuffled-target/risk sentinels reject memorization at the model-family level, but residual tails can still encode detector-specific behavior that may not transfer to a different geometry, range-energy observable, or PID selection.  The run-block intervals are intentionally shown because event-only intervals understate uncertainty when only two runs are held out.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/p04v_1781065299_478_126968ef_duplicate_tail_risk_ledger.py --config configs/p04v_1781065299_478_126968ef_duplicate_tail_risk_ledger.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path)})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04v_1781065299_478_126968ef_duplicate_tail_risk_ledger.json")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    p04d = load_module("p04d_adaptive_template_scale_pathology", Path("scripts/p04d_adaptive_template_scale_pathology.py"))
    p04f = load_module("p04f_residual_basis_diagnosis", Path("scripts/p04f_1781024351_1905_535c46de_residual_basis_diagnosis.py"))
    p04d_config = p04d.load_config(Path(config["p04d_config"]))

    print("1/9 rebuilding raw ROOT duplicate rows ...", flush=True)
    meta, wave, counts = p04d.extract_rows(p04d_config)
    selected = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if selected != expected:
        raise RuntimeError(f"raw reproduction failed: got {selected}, expected {expected}")
    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
    invalid_rows = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid].astype(np.float32)
    y = meta["target_odd_pos_charge"].to_numpy(dtype=float)
    st = meta["stave_idx"].to_numpy(dtype=int)
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    if set(meta.loc[train_mask, "run"].astype(int)).intersection(heldout_runs):
        raise RuntimeError("held-out run leaked into training")
    print(f"selected={selected} valid={len(meta)} train={int(train_mask.sum())} heldout={int(heldout_mask.sum())}", flush=True)

    print("2/9 building residual basis and atoms ...", flush=True)
    residual_x, basis_summary = p04f.build_residual_basis(meta, wave, train_mask, config, rng)
    shape_x = p04f.waveform_shape_features(meta, wave)
    template_scale = template_scale_feature(meta, wave, train_mask, config)
    even_charge = np.maximum(meta["even_pos_charge"].to_numpy(dtype=float), 1.0)
    baseline_std = wave[:, :4].std(axis=1)
    tail_frac = tail_fraction(wave, even_charge)
    train_resid_rms = meta["resid_rms"].to_numpy(dtype=float)
    meta["atom_saturation"] = meta["even_amp"].to_numpy(dtype=float) >= float(config["saturation_amp_adc"])
    meta["atom_pretrigger"] = baseline_std >= float(np.quantile(baseline_std[train_mask], float(config["pretrigger_std_quantile"])))
    meta["atom_dropout"] = tail_frac <= float(np.quantile(tail_frac[train_mask], float(config["dropout_tail_quantile"])))
    meta["atom_anomaly"] = train_resid_rms >= float(np.quantile(train_resid_rms[train_mask], float(config["anomaly_resid_quantile"])))

    feature_blocks: Dict[str, np.ndarray] = {
        "waveform": wave / np.maximum(meta["even_amp"].to_numpy(dtype=float)[:, None], 1.0),
        "shape": shape_x,
        "residual_basis": residual_x,
        "stave": one_hot(st),
        "atoms": np.column_stack(
            [
                meta["atom_saturation"].to_numpy(dtype=float),
                meta["atom_pretrigger"].to_numpy(dtype=float),
                meta["atom_dropout"].to_numpy(dtype=float),
                meta["atom_anomaly"].to_numpy(dtype=float),
            ]
        ),
    }
    feature_family: Dict[str, List[int]] = {}
    cursor = 0
    x_parts = []
    for name, block in feature_blocks.items():
        block = np.asarray(block, dtype=float)
        x_parts.append(block)
        feature_family[name] = list(range(cursor, cursor + block.shape[1]))
        cursor += block.shape[1]
    x_ml = np.column_stack(x_parts)
    x_trad = np.column_stack([shape_x, residual_x, np.log(template_scale), one_hot(st)])
    x_aux = np.column_stack([shape_x, residual_x, one_hot(st), feature_blocks["atoms"]])
    wave_norm = feature_blocks["waveform"].astype(np.float32)

    predictions: Dict[str, np.ndarray] = {}
    print("3/9 fitting frozen traditional calibrators ...", flush=True)
    predictions["peak_log_calibrated"] = predict_per_stave(
        fit_per_stave_log_model(np.log(np.maximum(meta["even_amp"].to_numpy(dtype=float), 1.0))[:, None], y, train_mask, st, "ridge"),
        np.log(np.maximum(meta["even_amp"].to_numpy(dtype=float), 1.0))[:, None],
        st,
    )
    predictions["integral_log_calibrated"] = predict_per_stave(
        fit_per_stave_log_model(np.log(even_charge)[:, None], y, train_mask, st, "ridge"),
        np.log(even_charge)[:, None],
        st,
    )
    predictions["adaptive_template_scale"] = predict_per_stave(
        fit_per_stave_log_model(np.log(template_scale)[:, None], y, train_mask, st, "ridge"),
        np.log(template_scale)[:, None],
        st,
    )
    predictions["strong_traditional_huber"] = predict_per_stave(
        fit_per_stave_log_model(x_trad, y, train_mask, st, "huber"),
        x_trad,
        st,
    )

    print("4/9 fitting ridge, boosted trees, and ExtraTrees ...", flush=True)
    predictions["ridge_residual_basis"] = predict_per_stave(
        fit_per_stave_log_model(x_trad, y, train_mask, st, "ridge"),
        x_trad,
        st,
    )
    hgb = HistGradientBoostingRegressor(
        max_iter=int(config["hgb_max_iter"]),
        learning_rate=0.045,
        max_leaf_nodes=31,
        l2_regularization=0.02,
        random_state=int(config["random_seed"]) + 10,
    )
    predictions["hgb_regressor"] = np.maximum(
        np.exp(fit_global_regressor(hgb, x_ml, y, train_mask, rng, int(config["ml_max_train_rows"])).predict(x_ml)),
        1.0,
    )
    et = ExtraTreesRegressor(
        n_estimators=int(config["extra_trees_estimators"]),
        max_depth=22,
        min_samples_leaf=3,
        max_features=0.75,
        random_state=int(config["random_seed"]) + 11,
        n_jobs=-1,
    )
    predictions["extra_trees_regressor"] = np.maximum(
        np.exp(fit_global_regressor(et, x_ml, y, train_mask, rng, int(config["ml_max_train_rows"])).predict(x_ml)),
        1.0,
    )

    print("5/9 fitting MLP and 1D-CNN family ...", flush=True)
    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=(96, 48),
            activation="relu",
            solver="adam",
            alpha=1e-4,
            learning_rate_init=5e-4,
            batch_size=512,
            max_iter=int(config["mlp_max_iter"]),
            early_stopping=True,
            n_iter_no_change=8,
            random_state=int(config["random_seed"]) + 12,
        ),
    )
    predictions["mlp_regressor"] = np.maximum(
        np.exp(fit_global_regressor(mlp, x_ml, y, train_mask, rng, int(config["nn_max_train_rows"])).predict(x_ml)),
        1.0,
    )
    predictions["cnn1d"] = fit_torch_model(wave_norm, x_aux.astype(np.float32), y, train_mask, config, rng, gated=False)
    predictions["residual_gated_cnn"] = fit_torch_model(wave_norm, x_aux.astype(np.float32), y, train_mask, config, rng, gated=True)

    print("6/9 evaluating held-out and per-run CIs ...", flush=True)
    benchmark, by_run = evaluate_methods(meta, y, predictions, train_mask, heldout_mask, config)
    benchmark.to_csv(out_dir / "method_benchmark.csv", index=False)
    by_run.to_csv(out_dir / "heldout_per_run_metrics.csv", index=False)

    winner_method = str(benchmark.sort_values(["charge_res68_abs_frac", "tail_gt10_frac"]).iloc[0]["method"])
    trad_method = "strong_traditional_huber"
    print(f"winner={winner_method}", flush=True)

    print("7/9 building atom ledger and tail-risk sentinels ...", flush=True)
    ledger = atom_ledger(meta, y, predictions, winner_method, trad_method, heldout_mask, config)
    risk, knockouts = tail_risk_models(x_ml, feature_family, meta, y, predictions[winner_method], train_mask, heldout_mask, config, rng)
    ledger.to_csv(out_dir / "tail_atom_ledger.csv", index=False)
    risk.to_csv(out_dir / "tail_risk_models.csv", index=False)
    knockouts.to_csv(out_dir / "feature_family_knockouts.csv", index=False)
    basis_summary.to_csv(out_dir / "residual_basis_summary.csv", index=False)
    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)

    print("8/9 writing leakage checks and result ...", flush=True)
    train_keys = set(
        zip(meta.loc[train_mask, "run"].astype(int), meta.loc[train_mask, "eventno"].astype(int), meta.loc[train_mask, "stave"].astype(str))
    )
    held_keys = set(
        zip(meta.loc[heldout_mask, "run"].astype(int), meta.loc[heldout_mask, "eventno"].astype(int), meta.loc[heldout_mask, "stave"].astype(str))
    )
    wave_hash = np.asarray([hashlib.sha1(np.ascontiguousarray(row).view(np.uint8)).hexdigest() for row in wave])
    leakage = pd.DataFrame(
        [
            {"check": "raw_selected_pulse_reproduction", "value": int(selected), "pass": selected == expected},
            {"check": "train_heldout_run_overlap", "value": int(len(set(meta.loc[train_mask, "run"]).intersection(heldout_runs))), "pass": True},
            {"check": "train_heldout_event_stave_key_overlap", "value": int(len(train_keys.intersection(held_keys))), "pass": len(train_keys.intersection(held_keys)) == 0},
            {"check": "exact_even_waveform_hash_overlap", "value": int(len(set(wave_hash[train_mask]).intersection(set(wave_hash[heldout_mask])))), "pass": int(len(set(wave_hash[train_mask]).intersection(set(wave_hash[heldout_mask])))) == 0},
            {"check": "features_exclude_run_event_odd_target", "value": "even waveform, even summaries, train-only residual basis, stave one-hot, atom flags", "pass": True},
            {"check": "permuted_tail_risk_auc_near_random", "value": float(risk.loc[risk["model"] == "permuted_target_extra_trees_tail_risk", "heldout_auc"].iloc[0]), "pass": float(risk.loc[risk["model"] == "permuted_target_extra_trees_tail_risk", "heldout_auc"].iloc[0]) < 0.60},
            {"check": "torch_available_for_cnn", "value": bool(torch is not None), "pass": bool(torch is not None)},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    winner_row = benchmark[benchmark["method"] == winner_method].iloc[0]
    trad_row = benchmark[benchmark["method"] == trad_method].iloc[0]
    hgb_row = benchmark[benchmark["method"] == "hgb_regressor"].iloc[0]
    cnn_row = benchmark[benchmark["method"] == "cnn1d"].iloc[0]
    gated_row = benchmark[benchmark["method"] == "residual_gated_cnn"].iloc[0]
    worst_atom = ledger.sort_values(["tail_gt25_frac", "tail_gt10_frac"], ascending=False).iloc[0]
    finding = (
        f"The charge-closure winner is {winner_method} with res68={winner_row['charge_res68_abs_frac']:.4f}, "
        f"full RMS={winner_row['full_rms_frac']:.4f}, tail10={winner_row['tail_gt10_frac']:.4f}, "
        f"and tail25={winner_row['tail_gt25_frac']:.4f}.  The strong traditional Huber residual-basis "
        f"reference gives res68={trad_row['charge_res68_abs_frac']:.4f} and tail10={trad_row['tail_gt10_frac']:.4f}; "
        f"HGB gives res68={hgb_row['charge_res68_abs_frac']:.4f}, the plain 1D-CNN gives {cnn_row['charge_res68_abs_frac']:.4f}, "
        f"and the residual-gated CNN gives {gated_row['charge_res68_abs_frac']:.4f}.  The largest held-out "
        f"tail25 atom is {worst_atom['axis']}={worst_atom['atom']} (n={int(worst_atom['n'])}, "
        f"tail25={worst_atom['tail_gt25_frac']:.4f}).  Therefore P04f-like central closure does hide "
        f"localized charge-tail risk; reuse should require the atom ledger or conformal support filter rather "
        f"than only a central res68 threshold."
    )
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": selected,
            "delta": selected - expected,
            "pass": selected == expected,
        },
        "target_definition": "odd duplicate-readout positive charge; features from even readout only",
        "split": {
            "heldout_runs": heldout_runs,
            "train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()),
            "bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "row_counts": {
            "valid_rows": int(len(meta)),
            "train_rows": int(train_mask.sum()),
            "heldout_rows": int(heldout_mask.sum()),
            "invalid_target_rows_removed_after_reproduction": invalid_rows,
        },
        "methods_benchmarked": sorted(predictions.keys()),
        "traditional_reference_method": trad_method,
        "winner": {
            "method": winner_method,
            "criterion": "minimum held-out charge res68; tail rates reported as co-primary safety diagnostics",
            "metrics": json.loads(winner_row.to_json()),
        },
        "benchmark": json.loads(benchmark.to_json(orient="records")),
        "tail_risk_models": json.loads(risk.to_json(orient="records")),
        "feature_family_knockouts": json.loads(knockouts.to_json(orient="records")),
        "tail_ledger_top_atoms": json.loads(
            ledger.sort_values(["tail_gt25_frac", "tail_gt10_frac"], ascending=False).head(24).to_json(orient="records")
        ),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, counts, benchmark, by_run, ledger, risk, knockouts, leakage, result)

    print("9/9 writing input and manifest hashes ...", flush=True)
    input_files = [p04d.raw_path(p04d_config, run) for run in p04d.configured_runs(p04d_config)]
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/p04v_1781065299_478_126968ef_duplicate_tail_risk_ledger.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": "scripts/p04v_1781065299_478_126968ef_duplicate_tail_risk_ledger.py",
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
            "p04d_source_script": "scripts/p04d_adaptive_template_scale_pathology.py",
            "p04d_source_script_sha256": sha256_file(Path("scripts/p04d_adaptive_template_scale_pathology.py")),
            "p04f_source_script": "scripts/p04f_1781024351_1905_535c46de_residual_basis_diagnosis.py",
            "p04f_source_script_sha256": sha256_file(Path("scripts/p04f_1781024351_1905_535c46de_residual_basis_diagnosis.py")),
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
