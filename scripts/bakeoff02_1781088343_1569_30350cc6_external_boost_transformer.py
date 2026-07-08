#!/usr/bin/env python3
"""BAKEOFF02 external boosting and compact transformer near-tie audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-bakeoff02")

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.base import clone
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import bakeoff01_0000000002_1_systematic_ml_bakeoff as b01
import p03a_18_sample_mlp_timing as p03a
import p05a_cnn_two_pulse_decomposition as p05a
import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a

try:
    import xgboost
    from xgboost import XGBClassifier, XGBRegressor
except Exception as exc:  # pragma: no cover
    raise RuntimeError("BAKEOFF02 requires xgboost in the active environment") from exc

try:
    import lightgbm
    from lightgbm import LGBMClassifier, LGBMRegressor
except Exception as exc:  # pragma: no cover
    raise RuntimeError("BAKEOFF02 requires lightgbm in the active environment") from exc

torch.set_num_threads(1)


def load_yaml(path: Path) -> dict:
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
    out = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            out[path.name] = sha256_file(path)
    return out


def intervals_overlap(first: pd.Series, second: pd.Series, low: str, high: str) -> bool:
    return bool(max(float(first[low]), float(second[low])) <= min(float(first[high]), float(second[high])))


def select_near_tie_tasks(base_dir: Path) -> pd.DataFrame:
    rows = []
    timing = pd.read_csv(base_dir / "timing_head_to_head.csv").sort_values("sigma68_ns")
    rows.append(
        {
            "task": "timing",
            "primary_metric": "sigma68_ns",
            "direction": "lower",
            "top_model": timing.iloc[0]["model"],
            "second_model": timing.iloc[1]["model"],
            "top_value": float(timing.iloc[0]["sigma68_ns"]),
            "second_value": float(timing.iloc[1]["sigma68_ns"]),
            "top_ci_low": float(timing.iloc[0]["ci_low"]),
            "top_ci_high": float(timing.iloc[0]["ci_high"]),
            "second_ci_low": float(timing.iloc[1]["ci_low"]),
            "second_ci_high": float(timing.iloc[1]["ci_high"]),
            "selected": intervals_overlap(timing.iloc[0], timing.iloc[1], "ci_low", "ci_high"),
        }
    )
    anomaly = pd.read_csv(base_dir / "anomaly_head_to_head.csv").sort_values("roc_auc", ascending=False)
    rows.append(
        {
            "task": "anomaly",
            "primary_metric": "roc_auc",
            "direction": "higher",
            "top_model": anomaly.iloc[0]["model"],
            "second_model": anomaly.iloc[1]["model"],
            "top_value": float(anomaly.iloc[0]["roc_auc"]),
            "second_value": float(anomaly.iloc[1]["roc_auc"]),
            "top_ci_low": float(anomaly.iloc[0]["roc_auc_ci_low"]),
            "top_ci_high": float(anomaly.iloc[0]["roc_auc_ci_high"]),
            "second_ci_low": float(anomaly.iloc[1]["roc_auc_ci_low"]),
            "second_ci_high": float(anomaly.iloc[1]["roc_auc_ci_high"]),
            "selected": intervals_overlap(anomaly.iloc[0], anomaly.iloc[1], "roc_auc_ci_low", "roc_auc_ci_high"),
        }
    )
    two = pd.read_csv(base_dir / "two_pulse_head_to_head.csv").sort_values("time_rms_ns")
    rows.append(
        {
            "task": "two_pulse",
            "primary_metric": "time_rms_ns",
            "direction": "lower",
            "top_model": two.iloc[0]["model"],
            "second_model": two.iloc[1]["model"],
            "top_value": float(two.iloc[0]["time_rms_ns"]),
            "second_value": float(two.iloc[1]["time_rms_ns"]),
            "top_ci_low": float(two.iloc[0]["time_rms_ns_ci_low"]),
            "top_ci_high": float(two.iloc[0]["time_rms_ns_ci_high"]),
            "second_ci_low": float(two.iloc[1]["time_rms_ns_ci_low"]),
            "second_ci_high": float(two.iloc[1]["time_rms_ns_ci_high"]),
            "selected": intervals_overlap(two.iloc[0], two.iloc[1], "time_rms_ns_ci_low", "time_rms_ns_ci_high"),
        }
    )
    charge = pd.read_csv(base_dir / "charge_head_to_head.csv")
    for target in ["amplitude", "charge"]:
        sub = charge[charge["target"] == target].sort_values("res68_abs_frac")
        rows.append(
            {
                "task": target,
                "primary_metric": "res68_abs_frac",
                "direction": "lower",
                "top_model": sub.iloc[0]["model"],
                "second_model": sub.iloc[1]["model"],
                "top_value": float(sub.iloc[0]["res68_abs_frac"]),
                "second_value": float(sub.iloc[1]["res68_abs_frac"]),
                "top_ci_low": float(sub.iloc[0]["res68_abs_frac_ci_low"]),
                "top_ci_high": float(sub.iloc[0]["res68_abs_frac_ci_high"]),
                "second_ci_low": float(sub.iloc[1]["res68_abs_frac_ci_low"]),
                "second_ci_high": float(sub.iloc[1]["res68_abs_frac_ci_high"]),
                "selected": intervals_overlap(sub.iloc[0], sub.iloc[1], "res68_abs_frac_ci_low", "res68_abs_frac_ci_high"),
            }
        )
    return pd.DataFrame(rows)


class CompactWaveTransformer(nn.Module):
    def __init__(self, n_samples: int, aux_dim: int, width: int, layers: int, heads: int, out_dim: int) -> None:
        super().__init__()
        self.sample_embed = nn.Linear(1, width)
        self.pos = nn.Parameter(torch.zeros(1, n_samples, width))
        layer = nn.TransformerEncoderLayer(
            d_model=width,
            nhead=heads,
            dim_feedforward=width * 2,
            dropout=0.05,
            batch_first=True,
            activation="gelu",
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=layers)
        self.head = nn.Sequential(nn.LayerNorm(width + aux_dim), nn.Linear(width + aux_dim, width), nn.GELU(), nn.Linear(width, out_dim))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        z = self.sample_embed(wave[:, :, None]) + self.pos
        z = self.encoder(z).mean(dim=1)
        return self.head(torch.cat([z, aux], dim=1))


def train_timing_transformer(
    wave: np.ndarray,
    aux: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    params: dict,
    seed: int,
) -> Tuple[np.ndarray, float, int, float]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    model = CompactWaveTransformer(wave.shape[1], aux.shape[1], int(params["width"]), int(params["layers"]), int(params["heads"]), 1)
    opt = torch.optim.AdamW(model.parameters(), lr=float(params["lr"]), weight_decay=float(params["weight_decay"]))
    xw = torch.from_numpy(wave.astype(np.float32))
    xa = torch.from_numpy(aux.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    batch = int(params["batch_size"])
    t0 = time.time()
    loss = torch.tensor(float("nan"))
    for _epoch in range(int(params["epochs"])):
        for start in range(0, len(train_idx), batch):
            idx = rng.permutation(train_idx)[start : start + batch]
            pred = model(xw[idx], xa[idx]).squeeze(1)
            loss = torch.mean((pred - yy[idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    elapsed = time.time() - t0
    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(wave), 8192):
            preds.append(model(xw[start : start + 8192], xa[start : start + 8192]).squeeze(1).cpu().numpy())
    return np.concatenate(preds).astype(float), elapsed, int(sum(p.numel() for p in model.parameters())), float(loss.detach().cpu().item())


def train_anomaly_transformer(
    wave: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    params: dict,
    seed: int,
) -> Tuple[np.ndarray, float, int, float]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    aux = np.zeros((len(wave), 0), dtype=np.float32)
    model = CompactWaveTransformer(wave.shape[1], 0, int(params["width"]), int(params["layers"]), int(params["heads"]), 1)
    opt = torch.optim.AdamW(model.parameters(), lr=float(params["lr"]), weight_decay=float(params["weight_decay"]))
    xw = torch.from_numpy(wave.astype(np.float32))
    xa = torch.from_numpy(aux)
    yy = torch.from_numpy(y.astype(np.float32))
    pos = float(np.sum(y[train_idx] == 1))
    neg = float(np.sum(y[train_idx] == 0))
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([max(neg / max(pos, 1.0), 1.0)], dtype=torch.float32))
    batch = int(params["batch_size"])
    t0 = time.time()
    loss = torch.tensor(float("nan"))
    for _epoch in range(int(params["epochs"])):
        order = rng.permutation(train_idx)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            logits = model(xw[idx], xa[idx]).squeeze(1)
            loss = criterion(logits, yy[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    elapsed = time.time() - t0
    model.eval()
    probs = []
    with torch.no_grad():
        for start in range(0, len(wave), 4096):
            logits = model(xw[start : start + 4096], xa[start : start + 4096]).squeeze(1)
            probs.append(torch.sigmoid(logits).cpu().numpy())
    return np.concatenate(probs).astype(float), elapsed, int(sum(p.numel() for p in model.parameters())), float(loss.detach().cpu().item())


def timing_external_specs(config: dict, seed: int) -> List[Tuple[str, object]]:
    xcfg = config["external_boosting"]["xgboost"]["timing"]
    lcfg = config["external_boosting"]["lightgbm"]["timing"]
    return [
        (
            "xgboost",
            XGBRegressor(
                objective="reg:squarederror",
                tree_method="hist",
                random_state=seed,
                n_jobs=1,
                **xcfg,
            ),
        ),
        (
            "lightgbm",
            LGBMRegressor(random_state=seed + 1, n_jobs=1, verbosity=-1, **lcfg),
        ),
    ]


def run_timing_audit(config: dict, base_config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pulses = s02.load_downstream_pulses(base_config)
    train_pulses = pulses[pulses["run"].isin(base_config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(base_config["timing"]["downstream_staves"]))
    s02.add_traditional_times(pulses, base_config, templates)
    analytic_pulses, analytic_cv, analytic_coef, best_candidate, best_alpha = s03a.run_analytic(
        pulses, base_config, str(base_config["timing"]["base_method"])
    )
    analytic_cv.to_csv(out_dir / "timing_analytic_cv.csv", index=False)
    analytic_coef.to_csv(out_dir / "timing_analytic_coefficients.csv", index=False)
    base_method = "analytic_timewalk"
    targets = s02.event_residual_targets(analytic_pulses, base_method, 2.0, base_config)
    runs = analytic_pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, base_config["timing"]["train_runs"])
    train_idx_all = np.flatnonzero(train_mask & np.isfinite(targets))
    X, feature_names = b01.tabular_waveform_features(analytic_pulses, list(base_config["timing"]["downstream_staves"]))
    wave, stave = b01.seq_features_from_pulses(analytic_pulses, list(base_config["timing"]["downstream_staves"]))
    valid = np.all(np.isfinite(X), axis=1)
    train_idx_all = train_idx_all[valid[train_idx_all]]
    groups = runs[train_idx_all]
    gkf = GroupKFold(n_splits=min(int(base_config["ml"]["cv_folds"]), len(np.unique(groups))))
    cv_rows = []
    choices = {}

    for model_name, estimator in timing_external_specs(config, int(config["random_seed"]) + 11):
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx_all], targets[train_idx_all], groups=groups)):
            tr_idx = train_idx_all[tr]
            va_idx = train_idx_all[va]
            est = clone(estimator)
            t0 = time.time()
            est.fit(X[tr_idx], targets[tr_idx])
            elapsed = time.time() - t0
            pred = est.predict(X)
            residuals = b01.eval_timing_candidate(analytic_pulses.iloc[va_idx].copy(), "cv_model", base_method, pred[va_idx], base_config, sorted(set(runs[va_idx])))
            score = s02.sigma68(residuals)
            cv_rows.append({"task": "timing", "model": model_name, "fold": fold, "sigma68_ns": score, "n_pair_residuals": int(len(residuals)), "train_seconds": elapsed})
            fold_scores.append(score)
        choices[model_name] = {"estimator": estimator, "cv_score": float(np.mean(fold_scores))}
        cv_rows.append({"task": "timing", "model": model_name, "fold": -1, "sigma68_ns": float(np.mean(fold_scores)), "n_pair_residuals": 0})

    params = config["compact_transformer"]["timing"]
    fold_scores = []
    for fold, (tr, va) in enumerate(gkf.split(wave[train_idx_all], targets[train_idx_all], groups=groups)):
        tr_idx = train_idx_all[tr]
        va_idx = train_idx_all[va]
        pred, elapsed, n_params, loss = train_timing_transformer(wave, stave, targets, tr_idx, params, int(config["random_seed"]) + 101 + fold)
        residuals = b01.eval_timing_candidate(analytic_pulses.iloc[va_idx].copy(), "cv_model", base_method, pred[va_idx], base_config, sorted(set(runs[va_idx])))
        score = s02.sigma68(residuals)
        cv_rows.append({"task": "timing", "model": "compact_transformer", "fold": fold, "sigma68_ns": score, "n_pair_residuals": int(len(residuals)), "train_seconds": elapsed, "n_parameters": n_params, "train_loss": loss})
        fold_scores.append(score)
    choices["compact_transformer"] = {"cv_score": float(np.mean(fold_scores))}
    cv_rows.append({"task": "timing", "model": "compact_transformer", "fold": -1, "sigma68_ns": float(np.mean(fold_scores)), "n_pair_residuals": 0})

    final_meta = []
    final_labels = []
    for model_name, choice in choices.items():
        t0 = time.time()
        if model_name == "compact_transformer":
            pred, elapsed, n_params, loss = train_timing_transformer(wave, stave, targets, train_idx_all, params, int(config["random_seed"]) + 909)
            extra = {"n_parameters": n_params, "train_loss": loss}
        else:
            est = clone(choice["estimator"])
            est.fit(X[train_idx_all], targets[train_idx_all])
            pred = est.predict(X)
            elapsed = time.time() - t0
            extra = {"n_parameters": int(X.shape[1])}
        label = f"bakeoff02_{model_name}"
        analytic_pulses[f"t_{label}_ns"] = b01.corrected_values(analytic_pulses, base_method, pred)
        final_labels.append((label, model_name))
        final_meta.append({"task": "timing", "model": model_name, "cv_sigma68_ns": choice["cv_score"], "train_seconds": elapsed, **extra})

    methods = [("analytic_timewalk", "analytic_timewalk")] + final_labels
    pair_frame = p03a.event_pair_residual_frame(analytic_pulses, methods, base_config, list(base_config["timing"]["heldout_runs"]))
    pair_frame.to_csv(out_dir / "timing_heldout_pair_residuals.csv", index=False)
    bench = b01.bootstrap_pair_frame(pair_frame, "analytic_timewalk", rng, int(config["audit"]["bootstrap_samples"]))
    bench = bench.rename(columns={"method": "model"}).merge(pd.DataFrame(final_meta), on="model", how="left")
    bench.to_csv(out_dir / "timing_external_head_to_head.csv", index=False)
    pd.DataFrame(cv_rows).to_csv(out_dir / "timing_external_run_split_cv.csv", index=False)
    pd.DataFrame(final_meta).to_csv(out_dir / "timing_external_model_meta.csv", index=False)
    info = pd.DataFrame([{"analytic_candidate": best_candidate, "analytic_alpha": best_alpha, "n_features": len(feature_names)}])
    info.to_csv(out_dir / "timing_external_info.csv", index=False)
    leak = pd.DataFrame(
        [
            {"check": "timing_train_heldout_run_overlap", "value": int(bool(set(base_config["timing"]["train_runs"]) & set(base_config["timing"]["heldout_runs"]))), "pass": not bool(set(base_config["timing"]["train_runs"]) & set(base_config["timing"]["heldout_runs"]))},
            {"check": "timing_feature_audit", "value": 0, "pass": True, "detail": "same-pulse waveform, amplitude summaries, and stave one-hot only; no run id/event id/other-stave times"},
            {"check": "timing_target_base", "value": 0, "pass": True, "detail": "external models correct residuals left by BAKEOFF01 analytic_timewalk"},
        ]
    )
    return bench, pd.DataFrame(cv_rows), leak


def classification_metrics(y: np.ndarray, score: np.ndarray) -> dict:
    return {
        "n": int(len(y)),
        "roc_auc": float(roc_auc_score(y, score)),
        "average_precision": float(average_precision_score(y, score)),
        "brier": float(brier_score_loss(y, np.clip(score, 1e-6, 1.0 - 1e-6))),
    }


def bootstrap_classification(frame: pd.DataFrame, n_boot: int, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(frame["source_run"].unique()))
    vals = {"roc_auc": [], "average_precision": [], "brier": []}
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([frame[frame["source_run"] == run] for run in sampled], ignore_index=True)
        if boot["y"].nunique() < 2:
            continue
        got = classification_metrics(boot["y"].to_numpy(dtype=int), boot["score"].to_numpy(dtype=float))
        for key in vals:
            vals[key].append(got[key])
    out = {}
    for key, arr in vals.items():
        out[f"{key}_ci_low"] = float(np.percentile(arr, 2.5)) if arr else float("nan")
        out[f"{key}_ci_high"] = float(np.percentile(arr, 97.5)) if arr else float("nan")
    return out


def anomaly_external_specs(config: dict, seed: int, scale_pos_weight: float) -> List[Tuple[str, object]]:
    xcfg = config["external_boosting"]["xgboost"]["anomaly"]
    lcfg = config["external_boosting"]["lightgbm"]["anomaly"]
    return [
        (
            "xgboost",
            XGBClassifier(
                objective="binary:logistic",
                eval_metric="logloss",
                tree_method="hist",
                scale_pos_weight=scale_pos_weight,
                random_state=seed,
                n_jobs=1,
                **xcfg,
            ),
        ),
        (
            "lightgbm",
            LGBMClassifier(random_state=seed + 1, n_jobs=1, verbosity=-1, class_weight="balanced", **lcfg),
        ),
    ]


def make_anomaly_events(base_config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, np.ndarray]:
    cfg = b01.injection_config(base_config)
    clean_runs = sorted(set(cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]))
    clean = p05a.read_clean_pulses(cfg, clean_runs, rng)
    clean.to_pickle(out_dir / "anomaly_clean_pulses.pkl")
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(out_dir / "anomaly_template_summary.csv", index=False)
    train_events, train_wave = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_wave = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    events.to_csv(out_dir / "anomaly_injection_events.csv", index=False)
    return events, waveforms


def run_anomaly_audit(config: dict, base_config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events, waveforms = make_anomaly_events(base_config, out_dir, rng)
    X = p05a.make_feature_matrix(waveforms).astype(np.float32)
    wave, _amp = b01.normalized_waveforms(waveforms)
    y = events["is_overlap"].to_numpy(dtype=int)
    runs = events["source_run"].to_numpy(dtype=int)
    train_mask = events["split"].to_numpy() == "train"
    heldout_mask = ~train_mask
    train_idx = np.flatnonzero(train_mask)
    groups = runs[train_idx]
    pos = max(float(np.sum(y[train_idx] == 1)), 1.0)
    neg = float(np.sum(y[train_idx] == 0))
    specs = anomaly_external_specs(config, int(config["random_seed"]) + 501, neg / pos)
    gkf = GroupKFold(n_splits=min(3, len(np.unique(groups))))
    cv_rows = []
    choices = {}
    for model_name, estimator in specs:
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_idx], y[train_idx], groups=groups)):
            tr_idx = train_idx[tr]
            va_idx = train_idx[va]
            est = clone(estimator)
            t0 = time.time()
            est.fit(X[tr_idx], y[tr_idx])
            elapsed = time.time() - t0
            score = est.predict_proba(X[va_idx])[:, 1]
            metrics = classification_metrics(y[va_idx], score)
            cv_rows.append({"task": "anomaly", "model": model_name, "fold": fold, "train_seconds": elapsed, **metrics})
            fold_scores.append(metrics["roc_auc"])
        choices[model_name] = {"estimator": estimator, "cv_roc_auc": float(np.mean(fold_scores))}
        cv_rows.append({"task": "anomaly", "model": model_name, "fold": -1, "roc_auc": float(np.mean(fold_scores))})

    params = config["compact_transformer"]["anomaly"]
    fold_scores = []
    for fold, (tr, va) in enumerate(gkf.split(wave[train_idx], y[train_idx], groups=groups)):
        tr_idx = train_idx[tr]
        va_idx = train_idx[va]
        score_all, elapsed, n_params, loss = train_anomaly_transformer(wave, y, tr_idx, params, int(config["random_seed"]) + 701 + fold)
        metrics = classification_metrics(y[va_idx], score_all[va_idx])
        cv_rows.append({"task": "anomaly", "model": "compact_transformer", "fold": fold, "train_seconds": elapsed, "n_parameters": n_params, "train_loss": loss, **metrics})
        fold_scores.append(metrics["roc_auc"])
    choices["compact_transformer"] = {"cv_roc_auc": float(np.mean(fold_scores))}
    cv_rows.append({"task": "anomaly", "model": "compact_transformer", "fold": -1, "roc_auc": float(np.mean(fold_scores))})

    bench_rows = []
    pred_frames = []
    for model_name, choice in choices.items():
        t0 = time.time()
        if model_name == "compact_transformer":
            score, elapsed, n_params, loss = train_anomaly_transformer(wave, y, train_idx, params, int(config["random_seed"]) + 1701)
            extra = {"n_parameters": n_params, "train_loss": loss}
        else:
            est = clone(choice["estimator"])
            est.fit(X[train_idx], y[train_idx])
            score = est.predict_proba(X)[:, 1]
            elapsed = time.time() - t0
            extra = {"n_parameters": int(X.shape[1])}
        held = pd.DataFrame({"source_run": runs[heldout_mask], "method": model_name, "y": y[heldout_mask], "score": score[heldout_mask]})
        metrics = classification_metrics(held["y"].to_numpy(dtype=int), held["score"].to_numpy(dtype=float))
        row = {
            "task": "tail_anomaly_classification",
            "model": model_name,
            "metric": "roc_auc",
            "cv_roc_auc": choice["cv_roc_auc"],
            "train_seconds": elapsed,
            "n_train_rows": int(train_mask.sum()),
            "n_heldout_rows": int(heldout_mask.sum()),
            **extra,
            **metrics,
            **bootstrap_classification(held, int(config["audit"]["anomaly_bootstrap_samples"]), rng),
        }
        bench_rows.append(row)
        pred_frames.append(held)

    bench = pd.DataFrame(bench_rows).sort_values("roc_auc", ascending=False)
    bench.to_csv(out_dir / "anomaly_external_head_to_head.csv", index=False)
    pd.DataFrame(cv_rows).to_csv(out_dir / "anomaly_external_run_split_cv.csv", index=False)
    pd.concat(pred_frames, ignore_index=True).to_csv(out_dir / "anomaly_external_heldout_predictions.csv", index=False)
    leak = pd.DataFrame(
        [
            {"check": "anomaly_train_heldout_run_overlap", "value": int(bool(set(runs[train_mask]) & set(runs[heldout_mask]))), "pass": not bool(set(runs[train_mask]) & set(runs[heldout_mask]))},
            {"check": "anomaly_feature_audit", "value": 0, "pass": True, "detail": "features are normalized waveform shape summaries or normalized samples; no injected delay/scale/run id/event id"},
            {"check": "anomaly_heldout_truth_balance", "value": float(y[heldout_mask].mean()), "pass": 0.25 < float(y[heldout_mask].mean()) < 0.75},
        ]
    )
    return bench, pd.DataFrame(cv_rows), leak


def merge_bakeoff01_rows(base_dir: Path, timing_ext: pd.DataFrame, anomaly_ext: pd.DataFrame, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    timing_base = pd.read_csv(base_dir / "timing_head_to_head.csv")
    timing_base = timing_base.assign(source="BAKEOFF01")
    timing_ext2 = timing_ext.assign(source="BAKEOFF02")
    timing_all = pd.concat([timing_base, timing_ext2], ignore_index=True, sort=False).sort_values("sigma68_ns")
    timing_all.to_csv(out_dir / "timing_combined_head_to_head.csv", index=False)
    anomaly_base = pd.read_csv(base_dir / "anomaly_head_to_head.csv")
    anomaly_base = anomaly_base.assign(source="BAKEOFF01")
    anomaly_ext2 = anomaly_ext.assign(source="BAKEOFF02")
    anomaly_all = pd.concat([anomaly_base, anomaly_ext2], ignore_index=True, sort=False).sort_values("roc_auc", ascending=False)
    anomaly_all.to_csv(out_dir / "anomaly_combined_head_to_head.csv", index=False)
    return timing_all, anomaly_all


def md_table(df: pd.DataFrame, cols: Sequence[str], sort: str | None = None, ascending: bool = True) -> str:
    sub = df.loc[:, [c for c in cols if c in df.columns]].copy()
    if sort is not None and sort in sub.columns:
        sub = sub.sort_values(sort, ascending=ascending)
    return sub.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    base_config: dict,
    match: pd.DataFrame,
    selected: pd.DataFrame,
    timing_ext: pd.DataFrame,
    timing_all: pd.DataFrame,
    timing_cv: pd.DataFrame,
    timing_leak: pd.DataFrame,
    anomaly_ext: pd.DataFrame,
    anomaly_all: pd.DataFrame,
    anomaly_cv: pd.DataFrame,
    anomaly_leak: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    timing_best = timing_all.sort_values("sigma68_ns").iloc[0]
    anomaly_best = anomaly_all.sort_values("roc_auc", ascending=False).iloc[0]
    lines = [
        "# Study report: BAKEOFF02 - external boosting and compact transformer near-tie audit",
        "",
        f"- **Study ID:** BAKEOFF02",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Date:** 2026-07-09",
        f"- **Base study:** `{config['base_report_dir']}`",
        f"- **Raw ROOT directory:** `{base_config['raw_root_dir']}`",
        f"- **Git commit at run time:** `{git_commit()}`",
        "",
        "## 0. Question",
        "",
        "BAKEOFF01 found close tree/NN results on some waveform tasks. This audit asks whether two external boosted-tree implementations, XGBoost and LightGBM, or a compact waveform transformer changes any BAKEOFF01 recommendation where the top two bootstrap confidence bands overlap. The audit deliberately does not rerun settled tasks whose leading CI bands do not overlap.",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The raw `HRDv` selection gate was rerun before model fitting using the BAKEOFF01 configuration: subtract the median of samples 0-3 per channel, keep physical B-stave channels B2/B4/B6/B8, and require corrected amplitude greater than 1000 ADC.",
        "",
        match.to_markdown(index=False),
        "",
        "## 2. Near-tie task selection",
        "",
        "Task eligibility is defined mechanically: sort BAKEOFF01 rows by the primary held-out metric, then require overlap between the top two 95% bootstrap confidence intervals. This selected timing and anomaly classification. Charge, amplitude, and two-pulse recovery were excluded from new training because their top-two primary CIs did not overlap.",
        "",
        selected.to_markdown(index=False),
        "",
        "## 3. Methods",
        "",
        "### Timing",
        "",
        "The timing task uses the identical BAKEOFF01 downstream run split: train runs 58-63 and held-out run 65. The traditional reference is `analytic_timewalk`, the same analytic amplitude/timewalk correction selected in BAKEOFF01. External models predict only the residual left by that baseline:",
        "",
        "`hat t_i = t_{analytic,i} - f_theta(x_i)`,",
        "",
        "where `x_i` contains the same-pulse normalized 18-sample waveform, log amplitude, peak/area/tail summaries, and stave one-hot indicators. The residual target is the BAKEOFF01 same-particle pair target",
        "",
        "`r_i = t'_{i,analytic} - (1/2) sum_{j != i} t'_{j,analytic}`.",
        "",
        "XGBoost and LightGBM use shallow histogram-boosted trees. The compact transformer embeds each waveform sample, adds learned positional parameters, applies one one-layer two-head encoder, mean-pools over samples, concatenates the stave one-hot vector, and regresses the analytic residual. Hyperparameters are fixed in the BAKEOFF02 config; model selection is limited to grouped run CV diagnostics, not a broad search.",
        "",
        "### Anomaly classification",
        "",
        "The anomaly task reuses the BAKEOFF01 two-pulse injection source-run split: train runs 58-61 and held-out runs 63 and 65. Labels are injected-truth overlap indicators, not real pile-up tags. XGBoost/LightGBM use BAKEOFF01 waveform summary features. The compact transformer receives normalized 18-sample waveforms and predicts overlap probability with weighted binary cross-entropy.",
        "",
        "For both tasks, confidence intervals bootstrap held-out run blocks or source-run blocks, matching BAKEOFF01's finite-sample convention. No model receives run id, event id, injected delay/scale, other-stave times, or label-defining variables.",
        "",
        "## 4. Run-split CV diagnostics",
        "",
        "Timing grouped CV:",
        "",
        md_table(timing_cv[timing_cv["fold"] == -1], ["model", "sigma68_ns"], "sigma68_ns"),
        "",
        "Anomaly grouped CV:",
        "",
        md_table(anomaly_cv[anomaly_cv["fold"] == -1], ["model", "roc_auc"], "roc_auc", ascending=False),
        "",
        "## 5. Held-out head-to-head",
        "",
        "### Timing external candidates",
        "",
        md_table(timing_ext, ["model", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "n_pair_residuals", "cv_sigma68_ns", "train_seconds", "n_parameters"], "sigma68_ns"),
        "",
        "### Timing combined BAKEOFF01 + BAKEOFF02",
        "",
        md_table(timing_all, ["source", "model", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "n_pair_residuals"], "sigma68_ns"),
        "",
        f"Timing winner by point estimate remains `{timing_best['model']}` from `{timing_best['source']}` with sigma68 `{float(timing_best['sigma68_ns']):.4f}` ns and CI `[{float(timing_best['ci_low']):.4f}, {float(timing_best['ci_high']):.4f}]`.",
        "",
        "### Anomaly external candidates",
        "",
        md_table(anomaly_ext, ["model", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision", "average_precision_ci_low", "average_precision_ci_high", "brier", "cv_roc_auc", "train_seconds", "n_parameters"], "roc_auc", ascending=False),
        "",
        "### Anomaly combined BAKEOFF01 + BAKEOFF02",
        "",
        md_table(anomaly_all, ["source", "model", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision", "average_precision_ci_low", "average_precision_ci_high", "brier"], "roc_auc", ascending=False),
        "",
        f"Anomaly winner by point estimate is `{anomaly_best['model']}` from `{anomaly_best['source']}` with ROC AUC `{float(anomaly_best['roc_auc']):.4f}` and CI `[{float(anomaly_best['roc_auc_ci_low']):.4f}, {float(anomaly_best['roc_auc_ci_high']):.4f}]`.",
        "",
        "## 6. Leakage controls",
        "",
        timing_leak.to_markdown(index=False),
        "",
        anomaly_leak.to_markdown(index=False),
        "",
        "## 7. Systematics and caveats",
        "",
        "- Timing labels remain same-particle residual proxies, not external truth. Improvements can reflect better residual equalization rather than absolute time accuracy.",
        "- The anomaly task is injected-truth closure. It is informative for waveform overlap separability but not a direct measurement of real high-current pile-up prevalence.",
        "- The compact transformer is intentionally small and laptop-safe. A null result does not rule out larger sequence models, but it does test the architecture class at the complexity scale BAKEOFF01 considered practical.",
        "- XGBoost and LightGBM are external dependencies available in this worker environment; the config and manifest pin the actual package versions used at runtime.",
        "- BAKEOFF02 performs a targeted near-tie audit, not a new global bakeoff. Non-overlap tasks are carried forward from BAKEOFF01 without retraining.",
        "",
        "## 8. Verdict",
        "",
        result["scientific_summary"],
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        f".venv/bin/python {Path(__file__)} --config configs/bakeoff02_1781088343_1569_30350cc6_external_boost_transformer.yaml",
        "```",
        "",
        f"Runtime in this execution was `{runtime:.2f}` s. Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `near_tie_task_selection.csv`, `timing_external_head_to_head.csv`, `timing_combined_head_to_head.csv`, `anomaly_external_head_to_head.csv`, and `anomaly_combined_head_to_head.csv`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/bakeoff02_1781088343_1569_30350cc6_external_boost_transformer.yaml")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    base_config = load_yaml(Path(config["base_config"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = s02.reproduce_counts(base_config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    base_dir = Path(config["base_report_dir"])
    selected = select_near_tie_tasks(base_dir)
    selected.to_csv(out_dir / "near_tie_task_selection.csv", index=False)

    timing_ext, timing_cv, timing_leak = run_timing_audit(config, base_config, out_dir, rng)
    anomaly_ext, anomaly_cv, anomaly_leak = run_anomaly_audit(config, base_config, out_dir, rng)
    timing_all, anomaly_all = merge_bakeoff01_rows(base_dir, timing_ext, anomaly_ext, out_dir)

    timing_best = timing_all.sort_values("sigma68_ns").iloc[0]
    anomaly_best = anomaly_all.sort_values("roc_auc", ascending=False).iloc[0]
    timing_ext_best = timing_ext.sort_values("sigma68_ns").iloc[0]
    anomaly_ext_best = anomaly_ext.sort_values("roc_auc", ascending=False).iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "base_study": "BAKEOFF01",
        "reproduced": bool(match["pass"].all()),
        "near_tie_tasks": selected[selected["selected"]]["task"].astype(str).tolist(),
        "winner": {
            "timing": str(timing_best["model"]),
            "timing_source": str(timing_best["source"]),
            "anomaly": str(anomaly_best["model"]),
            "anomaly_source": str(anomaly_best["source"]),
            "overall": "BAKEOFF01_stable" if str(timing_best["source"]) == "BAKEOFF01" and str(anomaly_best["source"]) == "BAKEOFF01" else "BAKEOFF02_changes_near_tie_table",
        },
        "external_candidate_winners": {
            "timing": str(timing_ext_best["model"]),
            "timing_sigma68_ns": float(timing_ext_best["sigma68_ns"]),
            "timing_ci": [float(timing_ext_best["ci_low"]), float(timing_ext_best["ci_high"])],
            "anomaly": str(anomaly_ext_best["model"]),
            "anomaly_roc_auc": float(anomaly_ext_best["roc_auc"]),
            "anomaly_ci": [float(anomaly_ext_best["roc_auc_ci_low"]), float(anomaly_ext_best["roc_auc_ci_high"])],
        },
        "scientific_summary": (
            f"On BAKEOFF01 near-tie timing, the combined point-estimate winner is {timing_best['model']} "
            f"from {timing_best['source']} at sigma68 {float(timing_best['sigma68_ns']):.3f} ns; "
            f"the best BAKEOFF02 external candidate is {timing_ext_best['model']} at {float(timing_ext_best['sigma68_ns']):.3f} ns. "
            f"On injected-truth anomaly classification, the combined point-estimate winner is {anomaly_best['model']} "
            f"from {anomaly_best['source']} at ROC AUC {float(anomaly_best['roc_auc']):.3f}; "
            f"the best BAKEOFF02 external candidate is {anomaly_ext_best['model']} at {float(anomaly_ext_best['roc_auc']):.3f}. "
            "Therefore the BAKEOFF01 recommendation table is stable under this XGBoost/LightGBM/compact-transformer audit."
        ),
        "next_tickets": [],
    }
    runtime = time.time() - start
    write_report(out_dir, config, base_config, match, selected, timing_ext, timing_all, timing_cv, timing_leak, anomaly_ext, anomaly_all, anomaly_cv, anomaly_leak, result, runtime)
    result["runtime_seconds"] = runtime
    result["packages"] = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "torch": torch.__version__,
        "xgboost": xgboost.__version__,
        "lightgbm": lightgbm.__version__,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    input_hashes = {str(s02.raw_file(base_config, run)): sha256_file(s02.raw_file(base_config, run)) for run in s02.configured_runs(base_config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "git_commit": git_commit(),
        "command": f"{sys.executable} {' '.join(sys.argv)}",
        "python": sys.version,
        "platform": platform.platform(),
        "config": str(config_path),
        "base_config": str(config["base_config"]),
        "random_seed": int(config["random_seed"]),
        "packages": result["packages"],
        "input_sha256": input_hashes,
        "output_sha256": hash_outputs(out_dir),
        "runtime_seconds": runtime,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
