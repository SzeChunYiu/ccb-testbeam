#!/usr/bin/env python3
"""Pulse saturation and pile-up recovery benchmark for ticket 1783745883.3711.1b7b30b5.

The study starts from raw B-stack ROOT, reproduces the canonical selected-pulse
count, builds raw-derived self-supervised saturation and pile-up tasks, and
compares a traditional template/CFD method with ridge, gradient-boosted trees,
MLP, 1D-CNN-style feature maps, and a causal-attention feature architecture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-pulse-sat-pileup")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def resolve_raw_root_dir(config: dict) -> Path:
    for candidate in config["raw_root_dir_candidates"]:
        path = Path(candidate).expanduser()
        if path.exists() and list(path.glob("hrdb_run_*.root")):
            return path
    raise FileNotFoundError("No raw B-stack ROOT directory found")


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def iter_raw_events(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def threshold_crossing(waves: np.ndarray, fraction: float) -> np.ndarray:
    threshold = np.max(waves, axis=1) * float(fraction)
    ge = waves >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waves), np.nan, dtype=np.float64)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = waves[i, j - 1]
        y1 = waves[i, j]
        denom = y1 - y0
        out[i] = float(j) if abs(denom) < 1e-12 else (j - 1) + (threshold[i] - y0) / denom
    return out


def scan_raw(config: dict, raw_root_dir: Path) -> Tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    channels = np.asarray([staves[name] for name in STAVE_NAMES], dtype=int)
    groups = run_group_lookup(config)
    stave_grid = np.asarray(STAVE_NAMES, dtype=object)
    waves = []
    meta_frames = []
    count_rows = []

    for run in configured_runs(config):
        path = raw_root_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        counts = {
            "run": run,
            "group": groups[run],
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        counts.update({name: 0 for name in STAVE_NAMES})
        event_offset = 0
        for batch in iter_raw_events(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            selected_channels = raw[:, channels, :]
            baseline = np.median(selected_channels[..., baseline_idx], axis=-1)
            corrected = selected_channels - baseline[..., None]
            amp = corrected.max(axis=-1)
            selected = amp > cut
            event_idx, stave_idx = np.where(selected)
            counts["events_total"] += int(len(eventno))
            counts["events_with_selected"] += int(selected.any(axis=1).sum())
            counts["selected_pulses"] += int(selected.sum())
            for i, name in enumerate(STAVE_NAMES):
                counts[name] += int(selected[:, i].sum())
            if len(event_idx):
                chosen = corrected[event_idx, stave_idx, :]
                chosen_amp = amp[event_idx, stave_idx].astype(np.float32)
                waves.append(chosen.astype(np.float32))
                meta_frames.append(
                    pd.DataFrame(
                        {
                            "run": np.full(len(event_idx), run, dtype=np.int16),
                            "group": groups[run],
                            "event_index": (event_idx + event_offset).astype(np.int32),
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_grid[stave_idx],
                            "stave_idx": stave_idx.astype(np.int8),
                            "amplitude_adc": chosen_amp,
                            "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                            "baseline_adc": baseline[event_idx, stave_idx].astype(np.float32),
                        }
                    )
                )
            event_offset += int(len(eventno))
        count_rows.append(counts)
        print("run {:04d}: {} selected pulses".format(run, counts["selected_pulses"]))

    if not waves:
        raise RuntimeError("no selected B-stack pulses found")
    return np.concatenate(waves, axis=0), pd.concat(meta_frames, ignore_index=True), pd.DataFrame(count_rows)


def choose_clean_sample(waves: np.ndarray, meta: pd.DataFrame, config: dict, rng: np.random.Generator) -> np.ndarray:
    amp = meta["amplitude_adc"].to_numpy(dtype=float)
    peak = meta["peak_sample"].to_numpy(dtype=int)
    t50 = threshold_crossing(waves, 0.5)
    area = waves.sum(axis=1) / np.maximum(amp, 1.0)
    clean = (
        (amp > 1300.0)
        & (amp < 7000.0)
        & (peak >= 4)
        & (peak <= 11)
        & np.isfinite(t50)
        & (area > 2.2)
        & (area < 9.5)
    )
    pieces = []
    max_per = int(config["max_clean_per_run_stave"])
    for _, group in meta[clean].groupby(["run", "stave_idx"], sort=True):
        idx = group.index.to_numpy(dtype=int)
        take = min(len(idx), max_per)
        if take:
            pieces.append(rng.choice(idx, size=take, replace=False))
    out = np.concatenate(pieces).astype(int)
    rng.shuffle(out)
    return np.sort(out)


def normalize(waves: np.ndarray) -> np.ndarray:
    return (waves / np.maximum(waves.max(axis=1, keepdims=True), 1.0)).astype(np.float32)


def build_template(waves: np.ndarray) -> np.ndarray:
    return normalize(waves).mean(axis=0)


def template_scale_recover(waves: np.ndarray, template: np.ndarray, clipped: np.ndarray | None = None) -> np.ndarray:
    out = np.zeros(len(waves), dtype=float)
    for i in range(len(waves)):
        mask = np.ones(waves.shape[1], dtype=bool)
        if clipped is not None:
            mask = ~clipped[i]
            if mask.sum() < 3:
                mask = np.arange(waves.shape[1]) <= max(2, int(np.argmax(waves[i])) - 1)
        x = template[mask]
        y = waves[i, mask]
        denom = float(x @ x)
        out[i] = float((x @ y) / denom) if denom > 1e-9 else float(waves[i].max())
    return out


def cfd_time(waves: np.ndarray) -> np.ndarray:
    return threshold_crossing(waves, 0.5)


def base_features(waves: np.ndarray, meta: pd.DataFrame | None = None) -> np.ndarray:
    x = waves.astype(np.float32)
    norm = normalize(x)
    amp = np.maximum(x.max(axis=1), 1.0)
    pos = np.clip(x, 0, None)
    pos_area = np.maximum(pos.sum(axis=1), 1.0)
    diff = np.diff(x, axis=1)
    t50 = cfd_time(x)
    t20 = threshold_crossing(x, 0.2)
    t80 = threshold_crossing(x, 0.8)
    feats = [
        x,
        norm,
        np.log10(amp)[:, None],
        (pos_area / amp)[:, None],
        (pos[:, 10:].sum(axis=1) / pos_area)[:, None],
        (pos[:, :5].sum(axis=1) / pos_area)[:, None],
        np.nan_to_num(t50)[:, None],
        np.nan_to_num(t80 - t20)[:, None],
        diff.max(axis=1)[:, None],
        diff.min(axis=1)[:, None],
    ]
    if meta is not None:
        stave = np.zeros((len(meta), len(STAVE_NAMES)), dtype=np.float32)
        idx = meta["stave_idx"].to_numpy(dtype=int)
        stave[np.arange(len(meta)), idx] = 1.0
        feats.append(stave)
    return np.hstack(feats).astype(np.float32)


def cnn_features(waves: np.ndarray, meta: pd.DataFrame | None = None) -> np.ndarray:
    x = normalize(waves).astype(np.float32)
    kernels = np.asarray(
        [
            [-1, 0, 1],
            [1, -2, 1],
            [1, 1, 1],
            [-1, -1, 2],
            [2, -1, -1],
        ],
        dtype=np.float32,
    )
    pieces = [x]
    padded = np.pad(x, ((0, 0), (1, 1)), mode="edge")
    for kernel in kernels:
        conv = sum(kernel[j] * padded[:, j : j + x.shape[1]] for j in range(3))
        pieces.extend([conv.max(axis=1)[:, None], conv.mean(axis=1)[:, None], conv.std(axis=1)[:, None]])
    return np.hstack([base_features(waves, meta)] + pieces).astype(np.float32)


def causal_attention_features(waves: np.ndarray, meta: pd.DataFrame | None = None) -> np.ndarray:
    x = normalize(waves).astype(np.float32)
    t = np.arange(x.shape[1], dtype=np.float32)
    slopes = np.maximum(np.diff(np.pad(x, ((0, 0), (1, 0)), mode="edge"), axis=1), 0.0)
    causal_mass = np.cumsum(np.clip(x, 0, None), axis=1)
    causal_mass = causal_mass / np.maximum(causal_mass[:, -1:], 1e-6)
    weights = np.exp(3.0 * slopes)
    weights = weights / np.maximum(np.cumsum(weights, axis=1), 1e-6)
    att_time = np.cumsum(weights * t[None, :], axis=1)
    att_signal = np.cumsum(weights * x, axis=1)
    feats = [
        base_features(waves, meta),
        causal_mass,
        att_time[:, [3, 6, 9, 12, 15, 17]],
        att_signal[:, [3, 6, 9, 12, 15, 17]],
        np.maximum.accumulate(x, axis=1),
    ]
    return np.hstack(feats).astype(np.float32)


def make_tasks(waves: np.ndarray, meta: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame, np.ndarray]:
    amp = meta["amplitude_adc"].to_numpy(dtype=float)
    true_t50 = cfd_time(waves)
    ceilings = np.asarray(config["saturation_ceilings_adc"], dtype=float)
    ceiling = ceilings[np.arange(len(waves)) % len(ceilings)]
    sat_wave = np.minimum(waves, ceiling[:, None])
    sat_meta = meta.copy().reset_index(drop=True)
    sat_meta["ceiling_adc"] = ceiling
    sat_meta["true_amplitude_adc"] = amp
    sat_meta["true_t50"] = true_t50
    sat_meta["is_saturated"] = (waves >= ceiling[:, None]).any(axis=1).astype(int)

    n = len(waves)
    frac_lo, frac_hi = [float(v) for v in config["pileup_secondary_fraction_range"]]
    frac = rng.uniform(frac_lo, frac_hi, size=n).astype(np.float32)
    delays = np.asarray(config["pileup_delay_samples"], dtype=int)
    delay = rng.choice(delays, size=n, replace=True)
    secondary_idx = rng.permutation(n)
    secondary = waves[secondary_idx]
    injected = waves.copy().astype(np.float32)
    for i in range(n):
        d = int(delay[i])
        injected[i, d:] += frac[i] * secondary[i, : waves.shape[1] - d]
    clean_meta = meta.copy().reset_index(drop=True)
    clean_meta["pileup_label"] = 0
    clean_meta["secondary_fraction"] = 0.0
    clean_meta["delay_samples"] = 0
    injected_meta = meta.copy().reset_index(drop=True)
    injected_meta["pileup_label"] = 1
    injected_meta["secondary_fraction"] = frac
    injected_meta["delay_samples"] = delay
    pile_meta = pd.concat([clean_meta, injected_meta], ignore_index=True)
    pile_waves = np.vstack([waves, injected]).astype(np.float32)
    pile_meta["true_amplitude_adc"] = np.concatenate([amp, amp])
    pile_meta["true_t50"] = np.concatenate([true_t50, true_t50])
    return sat_meta, sat_wave.astype(np.float32), pile_meta, pile_waves


def regression_models(config: dict):
    return {
        "ML_ridge": make_pipeline(StandardScaler(), Ridge(alpha=2.0)),
        "ML_gradient_boosted_trees": HistGradientBoostingRegressor(
            max_iter=int(config["models"]["hgb_max_iter"]),
            learning_rate=0.06,
            max_leaf_nodes=15,
            l2_regularization=0.02,
            random_state=1801,
        ),
        "ML_mlp": make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-4, max_iter=int(config["models"]["mlp_max_iter"]), early_stopping=True, random_state=1802),
        ),
        "NN_1d_cnn_feature_mlp": make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(48, 24), alpha=5e-4, max_iter=int(config["models"]["mlp_max_iter"]), early_stopping=True, random_state=1803),
        ),
        "NN_causal_attention_mlp_new": make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(64, 32), alpha=5e-4, max_iter=int(config["models"]["mlp_max_iter"]), early_stopping=True, random_state=1804),
        ),
    }


def classifier_models(config: dict):
    return {
        "ML_ridge": make_pipeline(StandardScaler(), RidgeClassifier(alpha=2.0, class_weight="balanced")),
        "ML_gradient_boosted_trees": HistGradientBoostingClassifier(
            max_iter=int(config["models"]["hgb_max_iter"]),
            learning_rate=0.06,
            max_leaf_nodes=15,
            l2_regularization=0.02,
            random_state=1901,
        ),
        "ML_mlp": make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-4, max_iter=int(config["models"]["mlp_max_iter"]), early_stopping=True, random_state=1902),
        ),
        "NN_1d_cnn_feature_mlp": make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(48, 24), alpha=5e-4, max_iter=int(config["models"]["mlp_max_iter"]), early_stopping=True, random_state=1903),
        ),
        "NN_causal_attention_mlp_new": make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(64, 32), alpha=5e-4, max_iter=int(config["models"]["mlp_max_iter"]), early_stopping=True, random_state=1904),
        ),
    }


def score_classifier(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "decision_function"):
        return np.asarray(model.decision_function(x), dtype=float)
    return np.asarray(model.predict_proba(x)[:, 1], dtype=float)


def sigma68(x: np.ndarray) -> float:
    return float(np.nanpercentile(np.abs(x - np.nanmedian(x)), 68))


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def run_bootstrap(pred: pd.DataFrame, metric: str, higher_is_better: bool, n_boot: int, rng: np.random.Generator) -> Tuple[float, float]:
    runs = np.sort(pred["run"].unique())
    by_run = {run: pred[pred["run"] == run] for run in runs}
    vals = []
    for _ in range(n_boot):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        sub = pd.concat([by_run[int(run)] for run in sample_runs], ignore_index=True)
        vals.append(compute_metric(sub, metric))
    arr = np.asarray([v for v in vals if np.isfinite(v)], dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan")
    lo, hi = np.quantile(arr, [0.025, 0.975])
    return float(lo), float(hi)


def compute_metric(df: pd.DataFrame, metric: str) -> float:
    if metric == "energy_res68_frac":
        return sigma68(df["pred_amp"].to_numpy(dtype=float) / df["true_amp"].to_numpy(dtype=float) - 1.0)
    if metric == "energy_bias_frac":
        return float(np.nanmedian(df["pred_amp"].to_numpy(dtype=float) / df["true_amp"].to_numpy(dtype=float) - 1.0))
    if metric == "timing_sigma68_samples":
        return sigma68(df["pred_t50"].to_numpy(dtype=float) - df["true_t50"].to_numpy(dtype=float))
    if metric == "pileup_auc":
        return safe_auc(df["y_true"].to_numpy(dtype=int), df["score"].to_numpy(dtype=float))
    if metric == "pileup_ap":
        return safe_ap(df["y_true"].to_numpy(dtype=int), df["score"].to_numpy(dtype=float))
    raise KeyError(metric)


def summarize_predictions(pred: pd.DataFrame, task: str, n_boot: int, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    per_run_rows = []
    metrics = ["pileup_auc", "pileup_ap"] if task == "pileup" else ["energy_res68_frac", "energy_bias_frac", "timing_sigma68_samples"]
    for method, group in pred.groupby("method", sort=True):
        row = {"method": method, "task": task, "n": int(len(group))}
        for metric in metrics:
            row[metric] = compute_metric(group, metric)
            lo, hi = run_bootstrap(group, metric, metric in {"pileup_auc", "pileup_ap"}, n_boot, rng)
            row[metric + "_ci_low"] = lo
            row[metric + "_ci_high"] = hi
        rows.append(row)
        for run, rg in group.groupby("run", sort=True):
            run_row = {"method": method, "task": task, "run": int(run), "n": int(len(rg))}
            for metric in metrics:
                run_row[metric] = compute_metric(rg, metric)
            per_run_rows.append(run_row)
    return pd.DataFrame(rows), pd.DataFrame(per_run_rows)


def fit_leave_one_run_out(
    waves: np.ndarray,
    meta: pd.DataFrame,
    config: dict,
    task: str,
    template: np.ndarray,
) -> pd.DataFrame:
    runs = meta["run"].to_numpy(dtype=int)
    unique_runs = np.sort(np.unique(runs))
    frames = []
    if task == "saturation":
        y_log_amp = np.log(meta["true_amplitude_adc"].to_numpy(dtype=float))
        true_t = meta["true_t50"].to_numpy(dtype=float)
        feat_sets = {
            "base": base_features(waves, meta),
            "cnn": cnn_features(waves, meta),
            "attn": causal_attention_features(waves, meta),
        }
        models = regression_models(config)
        for heldout in unique_runs:
            train = runs != heldout
            test = runs == heldout
            train_template = build_template(waves[train])
            trad_amp = template_scale_recover(waves[test], train_template, waves[test] >= meta.loc[test, "ceiling_adc"].to_numpy(dtype=float)[:, None])
            trad_t = cfd_time(waves[test] / np.maximum(trad_amp[:, None], 1.0))
            frames.append(
                pd.DataFrame(
                    {
                        "method": "traditional_template_deconvolution_cfd",
                        "run": runs[test],
                        "row_index": np.where(test)[0],
                        "true_amp": meta.loc[test, "true_amplitude_adc"].to_numpy(dtype=float),
                        "pred_amp": trad_amp,
                        "true_t50": true_t[test],
                        "pred_t50": trad_t,
                    }
                )
            )
            for name, model in models.items():
                feat_key = "cnn" if name == "NN_1d_cnn_feature_mlp" else "attn" if name == "NN_causal_attention_mlp_new" else "base"
                fit = clone(model)
                fit.fit(feat_sets[feat_key][train], y_log_amp[train])
                pred_amp = np.exp(fit.predict(feat_sets[feat_key][test]))
                pred_t = cfd_time(waves[test] / np.maximum(pred_amp[:, None], 1.0))
                frames.append(
                    pd.DataFrame(
                        {
                            "method": name,
                            "run": runs[test],
                            "row_index": np.where(test)[0],
                            "true_amp": meta.loc[test, "true_amplitude_adc"].to_numpy(dtype=float),
                            "pred_amp": pred_amp,
                            "true_t50": true_t[test],
                            "pred_t50": pred_t,
                        }
                    )
                )
            print("saturation heldout run {} done".format(int(heldout)))
        return pd.concat(frames, ignore_index=True)

    y = meta["pileup_label"].to_numpy(dtype=int)
    feat_sets = {
        "base": base_features(waves, meta),
        "cnn": cnn_features(waves, meta),
        "attn": causal_attention_features(waves, meta),
    }
    models = classifier_models(config)
    for heldout in unique_runs:
        train = runs != heldout
        test = runs == heldout
        train_template = build_template(waves[train][y[train] == 0])
        rec_amp = template_scale_recover(waves, train_template)
        rec_norm = waves / np.maximum(rec_amp[:, None], 1.0)
        residual = ((rec_norm - train_template[None, :]) ** 2).mean(axis=1)
        cfd = cfd_time(rec_norm)
        trad_score = residual + 0.05 * np.nan_to_num(np.abs(cfd - np.nanmedian(cfd[train & (y == 0)])))
        if safe_auc(y[train], trad_score[train]) < 0.5:
            trad_score *= -1.0
        frames.append(
            pd.DataFrame(
                {
                    "method": "traditional_template_residual_cfd",
                    "run": runs[test],
                    "row_index": np.where(test)[0],
                    "y_true": y[test],
                    "score": trad_score[test],
                }
            )
        )
        for name, model in models.items():
            feat_key = "cnn" if name == "NN_1d_cnn_feature_mlp" else "attn" if name == "NN_causal_attention_mlp_new" else "base"
            fit = clone(model)
            fit.fit(feat_sets[feat_key][train], y[train])
            score = score_classifier(fit, feat_sets[feat_key][test])
            frames.append(
                pd.DataFrame(
                    {
                        "method": name,
                        "run": runs[test],
                        "row_index": np.where(test)[0],
                        "y_true": y[test],
                        "score": score,
                    }
                )
            )
        print("pileup heldout run {} done".format(int(heldout)))
    return pd.concat(frames, ignore_index=True)


def rank_winner(sat_summary: pd.DataFrame, pile_summary: pd.DataFrame) -> Tuple[str, pd.DataFrame]:
    sat = sat_summary.copy()
    pile = pile_summary.copy()
    methods = sorted(set(sat["method"]).intersection(set(pile["method"])))
    rows = []
    for method in methods:
        s = sat[sat["method"] == method].iloc[0]
        p = pile[pile["method"] == method].iloc[0]
        rows.append(
            {
                "method": method,
                "energy_res68_frac": float(s["energy_res68_frac"]),
                "timing_sigma68_samples": float(s["timing_sigma68_samples"]),
                "pileup_auc": float(p["pileup_auc"]),
            }
        )
    table = pd.DataFrame(rows)
    table["energy_rank"] = table["energy_res68_frac"].rank(method="min", ascending=True)
    table["timing_rank"] = table["timing_sigma68_samples"].rank(method="min", ascending=True)
    table["pileup_rank"] = table["pileup_auc"].rank(method="min", ascending=False)
    table["composite_rank_score"] = table[["energy_rank", "timing_rank", "pileup_rank"]].mean(axis=1)
    table = table.sort_values(["composite_rank_score", "energy_res68_frac", "pileup_auc"], ascending=[True, True, False])
    return str(table.iloc[0]["method"]), table


def write_report(
    out_dir: Path,
    result: dict,
    sat_summary: pd.DataFrame,
    pile_summary: pd.DataFrame,
    composite: pd.DataFrame,
    sat_per_run: pd.DataFrame,
    pile_per_run: pd.DataFrame,
) -> None:
    lines = [
        "# PULSE-SAT-PILEUP: template deconvolution vs ML saturation/pile-up recovery",
        "",
        "**Ticket:** `{}`  ".format(result["ticket_id"]),
        "**Worker:** `{}`  ".format(result["worker"]),
        "**Raw ROOT directory:** `{}`".format(result["raw_root_dir"]),
        "",
        "## Abstract",
        "",
        "This study tests whether saturated and piled-up waveform recovery benefits from ML/NN-style models relative to a strong traditional template-deconvolution and constant-fraction timing baseline. The inputs are raw B-stack ROOT waveforms. Because no row-level external amplitude, timing, and pile-up truth is available in the raw files, the study uses a self-supervised construction: clean measured pulses supply the truth, then controlled clipping and delayed secondary-pulse injection create saturation and pile-up stress samples. Evaluation is leave-one-run-out, and uncertainty intervals are run-block bootstraps. The composite winner is **{}**.".format(result["winner"]["method"]),
        "",
        "## Raw reproduction gate",
        "",
        "The analysis rescans every configured B-stack run from raw ROOT. For each event, `HRDv` is reshaped to `(8, 18)`, samples 0--3 define the pedestal, the even B-stave channels B2/B4/B6/B8 are baseline-subtracted, and a selected pulse has `max_t v(t) > 1000 ADC`. The reproduced selected-pulse count is **{:,}**, matching the registered count **{:,}** with delta **{}**.".format(
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
            result["reproduction"]["delta"],
        ),
        "",
        "## Data set and truth construction",
        "",
        "Clean seed pulses are selected from the raw reproduction table with peak sample in `[4, 11]`, amplitude in `[1300, 7000] ADC`, finite CFD50 time, and normalized area between 2.2 and 9.5. A stratified cap of `{}` clean pulses per `(run, stave)` avoids domination by high-rate runs. This yields **{:,}** clean seeds across **{}** runs.".format(
            result["config"]["max_clean_per_run_stave"], result["clean_seed_count"], len(result["runs"])
        ),
        "",
        "For saturation, each clean waveform `v_i(t)` with true amplitude `A_i=max_t v_i(t)` is clipped at a deterministic rotating ceiling `C_i in {{{}}}`:".format(
            ", ".join(str(c) for c in result["config"]["saturation_ceilings_adc"])
        ),
        "",
        "`x_i^sat(t) = min(v_i(t), C_i),    y_i^E = log A_i,    y_i^T = t50(v_i).`",
        "",
        "For pile-up, the same primary pulse is paired with another raw clean pulse `u_j`, a delay `d in {{{}}}`, and a secondary scale `alpha in [{:.2f}, {:.2f}]`:".format(
            ", ".join(str(d) for d in result["config"]["pileup_delay_samples"]),
            result["config"]["pileup_secondary_fraction_range"][0],
            result["config"]["pileup_secondary_fraction_range"][1],
        ),
        "",
        "`x_i^pile(t) = v_i(t) + alpha_i u_j(t-d) 1{t >= d},    y_i^P = 1.`",
        "",
        "The negative pile-up class is the unmodified clean pulse, `y_i^P=0`. Thus the amplitude and timing truth remain the measured primary pulse, while pile-up class truth is exactly known by construction.",
        "",
        "## Methods",
        "",
        "### Traditional template deconvolution and CFD",
        "",
        "For each held-out run, the template `q(t)` is the mean normalized clean training pulse. Saturated amplitudes are recovered by least-squares scaling on unclipped samples:",
        "",
        "`a_hat = argmin_a sum_{t in U_i} (x_i^sat(t) - a q(t))^2 = (sum_{t in U_i} q(t)x_i^sat(t))/(sum_{t in U_i} q(t)^2)`,",
        "",
        "where `U_i={t: x_i^sat(t)<C_i}`. Timing is the CFD50 crossing of `x_i^sat/a_hat`. Pile-up uses the same template scale and scores the event by normalized residual energy plus a small CFD-time displacement term.",
        "",
        "### ML/NN panel",
        "",
        "Ridge, gradient-boosted trees, and MLP use waveform samples, normalized shape samples, log-amplitude, area/tail/rise/derivative descriptors, CFD times, and stave one-hot indicators. The 1D-CNN entry uses explicit local convolutional filters over the 18-sample waveform followed by an MLP head. The new architecture is `NN_causal_attention_mlp_new`: it augments the pulse with causal cumulative charge, slope-weighted causal attention time, attention-weighted signal summaries, and causal running maxima before an MLP head. This is a sensible transformer-like substitute in the current environment because PyTorch is absent and the waveform has only 18 samples; the causal attention features preserve the intended directional inductive bias without unverified torch training.",
        "",
        "All models are trained in leave-one-run-out folds. For saturation the regression target is `log A_i`; for pile-up the classification target is the injected-pile-up indicator.",
        "",
        "## Metrics and intervals",
        "",
        "Energy residuals are `delta_E=(A_hat-A)/A`; the main energy metric is `sigma68(delta_E)=percentile_68(|delta_E-median(delta_E)|)`. Timing residuals are `delta_t=t50_hat-t50`; the timing metric is `sigma68(delta_t)`. Pile-up tagging uses ROC AUC and average precision. Bootstrap CIs resample runs with replacement, pool their rows, and recompute each metric 300 times.",
        "",
        "## Saturation recovery results",
        "",
        "| method | energy sigma68 | 95% CI | energy bias | timing sigma68 | 95% CI | rows |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in sat_summary.sort_values("energy_res68_frac").iterrows():
        lines.append(
            "| {} | {:.5f} | [{:.5f}, {:.5f}] | {:+.5f} | {:.4f} | [{:.4f}, {:.4f}] | {:,} |".format(
                row["method"],
                row["energy_res68_frac"],
                row["energy_res68_frac_ci_low"],
                row["energy_res68_frac_ci_high"],
                row["energy_bias_frac"],
                row["timing_sigma68_samples"],
                row["timing_sigma68_samples_ci_low"],
                row["timing_sigma68_samples_ci_high"],
                int(row["n"]),
            )
        )
    lines.extend(
        [
            "",
            "## Pile-up tagging results",
            "",
            "| method | ROC AUC | 95% CI | average precision | 95% CI | rows |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in pile_summary.sort_values("pileup_auc", ascending=False).iterrows():
        lines.append(
            "| {} | {:.5f} | [{:.5f}, {:.5f}] | {:.5f} | [{:.5f}, {:.5f}] | {:,} |".format(
                row["method"],
                row["pileup_auc"],
                row["pileup_auc_ci_low"],
                row["pileup_auc_ci_high"],
                row["pileup_ap"],
                row["pileup_ap_ci_low"],
                row["pileup_ap_ci_high"],
                int(row["n"]),
            )
        )
    lines.extend(
        [
            "",
            "## Composite decision",
            "",
            "The winner is chosen by the mean rank of saturation energy sigma68, saturation timing sigma68, and pile-up ROC AUC. Lower composite rank is better.",
            "",
            "| method | energy sigma68 | timing sigma68 | pile-up AUC | composite rank |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for _, row in composite.iterrows():
        lines.append(
            "| {} | {:.5f} | {:.4f} | {:.5f} | {:.2f} |".format(
                row["method"],
                row["energy_res68_frac"],
                row["timing_sigma68_samples"],
                row["pileup_auc"],
                row["composite_rank_score"],
            )
        )
    lines.extend(
        [
            "",
            "## Per-run stability",
            "",
            "| task | method | mean | min | max | finite runs |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for method, group in sat_per_run.groupby("method", sort=True):
        vals = group["energy_res68_frac"].dropna()
        lines.append("| saturation energy sigma68 | {} | {:.5f} | {:.5f} | {:.5f} | {} |".format(method, vals.mean(), vals.min(), vals.max(), len(vals)))
    for method, group in pile_per_run.groupby("method", sort=True):
        vals = group["pileup_auc"].dropna()
        lines.append("| pile-up AUC | {} | {:.5f} | {:.5f} | {:.5f} | {} |".format(method, vals.mean(), vals.min(), vals.max(), len(vals)))
    lines.extend(
        [
            "",
            "## Systematics",
            "",
            "- The labels are self-supervised transformations of measured pulses. This is stronger than a toy waveform simulation because the seeds are raw measured pulses, but it is not a substitute for external beam truth.",
            "- The saturation ceiling is imposed in software. Real electronics saturation may include recovery dynamics, baseline distortion, or nonlinearity before the ADC; those effects are not modeled.",
            "- Pile-up uses delayed clean B-stack pulses as secondaries. It preserves realistic pulse shapes but assumes linear superposition and a uniform secondary scale/delay prior.",
            "- Leave-one-run-out controls run leakage. The bootstrap CI treats runs as exchangeable blocks and therefore reflects run-to-run stability better than row-level CIs.",
            "- PyTorch is not installed in this worker, so the CNN and causal-transformer-like entries are implemented as fixed temporal convolution and causal-attention feature maps with MLP heads. The report and `result.json` mark them as feature-map NN surrogates, not torch-trained end-to-end networks.",
            "",
            "## Caveats",
            "",
            "The study answers a bounded question: on raw-derived clipping and delayed-superposition stress tests, which method best recovers primary amplitude/timing and tags pile-up under run-heldout evaluation? It should not be read as a claim that the same ranking holds for all detector operating points, for external PID truth, or for hardware saturation modes absent from the measured seed pulses.",
            "",
            "## Verdict",
            "",
            "`result.json` names **{}** as the winner. The best traditional baseline is `traditional_template_deconvolution_cfd` for saturation and `traditional_template_residual_cfd` for pile-up; the composite table quantifies whether the ML/NN panel improves on those baselines.".format(result["winner"]["method"]),
            "",
            "## Reproducibility",
            "",
            "```bash",
            ".venv/bin/python scripts/pulse_sat_pileup_1783745883_3711_1b7b30b5.py --config configs/1783745883.3711.1b7b30b5_pulse_sat_pileup.json",
            "```",
            "",
            "Primary artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `counts_by_run.csv`, `clean_seed_sample.csv`, `saturation_summary.csv`, `pileup_summary.csv`, `composite_ranking.csv`, `saturation_per_run.csv`, `pileup_per_run.csv`, `saturation_predictions.csv.gz`, `pileup_predictions.csv.gz`, and `manifest.json`.",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_manifest(out_dir: Path, config: dict) -> None:
    artifacts = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            artifacts.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {"ticket_id": config["ticket_id"], "generated_at_unix": time.time(), "artifacts": artifacts}
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")


def plot_results(out_dir: Path, sat_summary: pd.DataFrame, pile_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    sat = sat_summary.sort_values("energy_res68_frac")
    axes[0].barh(np.arange(len(sat)), sat["energy_res68_frac"], color="#4c78a8")
    axes[0].set_yticks(np.arange(len(sat)))
    axes[0].set_yticklabels(sat["method"])
    axes[0].set_xlabel("Saturation energy sigma68")
    axes[0].grid(axis="x", alpha=0.25)
    pile = pile_summary.sort_values("pileup_auc")
    axes[1].barh(np.arange(len(pile)), pile["pileup_auc"], color="#59a14f")
    axes[1].set_yticks(np.arange(len(pile)))
    axes[1].set_yticklabels(pile["method"])
    axes[1].set_xlabel("Pile-up ROC AUC")
    axes[1].set_xlim(0.5, 1.01)
    axes[1].grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "benchmark_summary.png", dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/1783745883.3711.1b7b30b5_pulse_sat_pileup.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_dir = resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, meta, counts = scan_raw(config, raw_dir)
    selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError("raw reproduction failed: selected {}, expected {}".format(selected, expected))
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "selected B-stave pulses with baseline-subtracted amplitude > 1000 ADC",
                "expected": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    clean_idx = choose_clean_sample(waves, meta, config, rng)
    clean_waves = waves[clean_idx].astype(np.float32)
    clean_meta = meta.iloc[clean_idx].reset_index(drop=True)
    clean_meta.to_csv(out_dir / "clean_seed_sample.csv", index=False)
    template = build_template(clean_waves)

    sat_meta, sat_waves, pile_meta, pile_waves = make_tasks(clean_waves, clean_meta, config, rng)
    sat_meta.to_csv(out_dir / "saturation_task_rows.csv", index=False)
    pile_meta.to_csv(out_dir / "pileup_task_rows.csv", index=False)

    sat_pred = fit_leave_one_run_out(sat_waves, sat_meta, config, "saturation", template)
    pile_pred = fit_leave_one_run_out(pile_waves, pile_meta, config, "pileup", template)
    sat_pred.to_csv(out_dir / "saturation_predictions.csv.gz", index=False)
    pile_pred.to_csv(out_dir / "pileup_predictions.csv.gz", index=False)

    sat_summary, sat_per_run = summarize_predictions(sat_pred, "saturation", int(config["bootstrap_replicates"]), rng)
    pile_summary, pile_per_run = summarize_predictions(pile_pred, "pileup", int(config["bootstrap_replicates"]), rng)
    winner, composite = rank_winner(sat_summary, pile_summary)
    sat_summary.to_csv(out_dir / "saturation_summary.csv", index=False)
    pile_summary.to_csv(out_dir / "pileup_summary.csv", index=False)
    sat_per_run.to_csv(out_dir / "saturation_per_run.csv", index=False)
    pile_per_run.to_csv(out_dir / "pileup_per_run.csv", index=False)
    composite.to_csv(out_dir / "composite_ranking.csv", index=False)
    plot_results(out_dir, sat_summary, pile_summary)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "script": "scripts/pulse_sat_pileup_1783745883_3711_1b7b30b5.py",
        "config_path": str(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "config": {
            "max_clean_per_run_stave": int(config["max_clean_per_run_stave"]),
            "saturation_ceilings_adc": config["saturation_ceilings_adc"],
            "pileup_secondary_fraction_range": config["pileup_secondary_fraction_range"],
            "pileup_delay_samples": config["pileup_delay_samples"],
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "delta": selected - expected,
            "passed": selected == expected,
            "baseline_samples": config["baseline_samples"],
            "amplitude_cut_adc": config["amplitude_cut_adc"],
        },
        "runs": configured_runs(config),
        "split": "leave-one-run-out with run-block bootstrap CIs",
        "clean_seed_count": int(len(clean_waves)),
        "method_family_note": {
            "NN_1d_cnn_feature_mlp": "fixed 1D temporal convolution feature map plus MLP head; PyTorch unavailable",
            "NN_causal_attention_mlp_new": "causal cumulative-attention feature map plus MLP head; transformer-like surrogate due to PyTorch unavailable",
        },
        "winner": composite.iloc[0].to_dict(),
        "best_saturation_energy": sat_summary.sort_values("energy_res68_frac").iloc[0].to_dict(),
        "best_pileup_auc": pile_summary.sort_values("pileup_auc", ascending=False).iloc[0].to_dict(),
        "traditional_baselines": {
            "saturation": sat_summary[sat_summary["method"] == "traditional_template_deconvolution_cfd"].iloc[0].to_dict(),
            "pileup": pile_summary[pile_summary["method"] == "traditional_template_residual_cfd"].iloc[0].to_dict(),
        },
        "runtime_sec": round(time.time() - t0, 3),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, sat_summary, pile_summary, composite, sat_per_run, pile_per_run)
    write_manifest(out_dir, config)
    print("DONE {} in {:.1f}s winner={}".format(config["ticket_id"], time.time() - t0, winner))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
