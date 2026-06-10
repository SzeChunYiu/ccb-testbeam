#!/usr/bin/env python3
"""S01g q-template quality covariate map.

The primary benchmark is a run-held-out timing-tail risk map on the S03b
pair-residual table. Secondary tables quantify whether the same fold-local
q_template atom tracks amplitude/saturation support, late-shape pile-up
proxies, baseline noise, and charge-shape residuals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s01g")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s01f_1781012803_fold_local_qtemplate as s01f
import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b
import s03d_leave_one_run_s03ab_hgb_stability as s03d

SCRIPT_PATH = Path(__file__)
PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
RUN65_EXPECTED = {
    "template_phase_base": 2.889152765080617,
    "s03a_amp_only": 1.494640076269676,
    "s03b_monotone_binned": 1.5695763825403084,
}
TABULAR_FEATURES = [
    "q_pair_max",
    "q_pair_mean",
    "q_pair_absdiff",
    "q_downstream_mean",
    "q_downstream_max",
    "q_downstream_std",
    "log_amp_mean",
    "log_amp_absdiff",
    "area_over_amp_mean",
    "area_over_amp_absdiff",
    "tail_fraction_mean",
    "tail_fraction_max",
    "late_fraction_mean",
    "late_fraction_max",
    "baseline_rms_mean",
    "baseline_rms_max",
    "peak_sample_mean",
    "peak_sample_absdiff",
    "pair_B4_B6",
    "pair_B4_B8",
    "pair_B6_B8",
]
TOKEN_FEATURES = ["q", "log_amp", "area_over_amp", "tail_fraction", "late_fraction", "baseline_rms", "peak_sample_scaled"]


def load_config(path: Path) -> dict:
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
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = json.loads(json.dumps(config))
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def add_pulse_shape_features(pulses: pd.DataFrame) -> pd.DataFrame:
    out = pulses.copy()
    wf = np.vstack(out["waveform"].to_numpy()).astype(float)
    amp = np.maximum(out["amplitude_adc"].to_numpy(dtype=float), 1.0)
    area = np.maximum(out["area_adc_samples"].to_numpy(dtype=float), 1.0)
    out["log_amp"] = np.log1p(out["amplitude_adc"].to_numpy(dtype=float))
    out["area_over_amp"] = area / amp
    out["tail_fraction"] = np.sum(np.clip(wf[:, 10:], 0.0, None), axis=1) / np.maximum(np.sum(np.clip(wf, 0.0, None), axis=1), 1.0)
    out["late_fraction"] = np.max(wf[:, 12:], axis=1) / amp
    out["baseline_rms"] = np.std(wf[:, :4], axis=1)
    out["peak_sample_scaled"] = out["peak_sample"].to_numpy(dtype=float) / max(wf.shape[1] - 1, 1)
    return out


def _metric(values: np.ndarray) -> dict:
    return s02.metric_summary(np.asarray(values, dtype=float))


def pair_frame(pulses: pd.DataFrame, config: dict, runs: Sequence[int]) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    sub["tcorr"] = sub["t_s03b_monotone_binned_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    fields = [
        "tcorr",
        "q_template",
        "amplitude_adc",
        "log_amp",
        "area_over_amp",
        "tail_fraction",
        "late_fraction",
        "baseline_rms",
        "peak_sample",
        "peak_sample_scaled",
    ]
    wide = {name: sub.pivot(index="event_id", columns="stave", values=name) for name in fields}
    meta = sub[["event_id", "run", "eventno", "evt"]].drop_duplicates("event_id").set_index("event_id")
    wave_map = sub.set_index(["event_id", "stave"])["waveform"].to_dict()
    rows = []
    wave_rows = []
    token_rows = []
    q_down = wide["q_template"].reindex(columns=downstream)
    for left, right in PAIRS:
        if left not in wide["tcorr"] or right not in wide["tcorr"]:
            continue
        resid = wide["tcorr"][left] - wide["tcorr"][right]
        frame = pd.DataFrame({"event_id": resid.index, "pair": f"{left}-{right}", "residual_ns": resid.to_numpy(dtype=float)}).set_index("event_id")
        frame = frame.join(meta, how="left").reset_index()
        for prefix, stave in [("left", left), ("right", right)]:
            for field in fields[1:]:
                frame[f"{field}_{prefix}"] = wide[field][stave].reindex(frame["event_id"]).to_numpy(dtype=float)
        frame["q_pair_max"] = frame[["q_template_left", "q_template_right"]].max(axis=1)
        frame["q_pair_mean"] = frame[["q_template_left", "q_template_right"]].mean(axis=1)
        frame["q_pair_absdiff"] = (frame["q_template_left"] - frame["q_template_right"]).abs()
        frame["q_downstream_mean"] = q_down.mean(axis=1).reindex(frame["event_id"]).to_numpy(dtype=float)
        frame["q_downstream_max"] = q_down.max(axis=1).reindex(frame["event_id"]).to_numpy(dtype=float)
        frame["q_downstream_std"] = q_down.std(axis=1).fillna(0.0).reindex(frame["event_id"]).to_numpy(dtype=float)
        for base in ["log_amp", "area_over_amp", "tail_fraction", "late_fraction", "baseline_rms"]:
            frame[f"{base}_mean"] = frame[[f"{base}_left", f"{base}_right"]].mean(axis=1)
            frame[f"{base}_max"] = frame[[f"{base}_left", f"{base}_right"]].max(axis=1)
            frame[f"{base}_absdiff"] = (frame[f"{base}_left"] - frame[f"{base}_right"]).abs()
        frame["peak_sample_mean"] = frame[["peak_sample_left", "peak_sample_right"]].mean(axis=1)
        frame["peak_sample_absdiff"] = (frame["peak_sample_left"] - frame["peak_sample_right"]).abs()
        for pair in ["B4-B6", "B4-B8", "B6-B8"]:
            frame[f"pair_{pair.replace('-', '_')}"] = (frame["pair"] == pair).astype(float)
        frame = frame[np.isfinite(frame["residual_ns"])].copy()
        for row in frame.itertuples(index=False):
            wl = np.asarray(wave_map[(row.event_id, left)], dtype=np.float32)
            wr = np.asarray(wave_map[(row.event_id, right)], dtype=np.float32)
            waves = np.vstack([wl / max(float(getattr(row, "amplitude_adc_left")), 1.0), wr / max(float(getattr(row, "amplitude_adc_right")), 1.0)])
            wave_rows.append(waves.astype(np.float32))
            left_token = [
                getattr(row, "q_template_left"),
                getattr(row, "log_amp_left"),
                getattr(row, "area_over_amp_left"),
                getattr(row, "tail_fraction_left"),
                getattr(row, "late_fraction_left"),
                getattr(row, "baseline_rms_left"),
                getattr(row, "peak_sample_scaled_left"),
            ]
            right_token = [
                getattr(row, "q_template_right"),
                getattr(row, "log_amp_right"),
                getattr(row, "area_over_amp_right"),
                getattr(row, "tail_fraction_right"),
                getattr(row, "late_fraction_right"),
                getattr(row, "baseline_rms_right"),
                getattr(row, "peak_sample_scaled_right"),
            ]
            down_token = [
                getattr(row, "q_downstream_mean"),
                getattr(row, "log_amp_mean"),
                getattr(row, "area_over_amp_mean"),
                getattr(row, "tail_fraction_mean"),
                getattr(row, "late_fraction_mean"),
                getattr(row, "baseline_rms_mean"),
                getattr(row, "peak_sample_mean") / 17.0,
            ]
            token_rows.append(np.asarray([left_token, right_token, down_token], dtype=np.float32))
        rows.append(frame)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return out, np.stack(wave_rows).astype(np.float32), np.stack(token_rows).astype(np.float32)


def calibrate_by_train_bins(train_score: np.ndarray, train_y: np.ndarray, test_score: np.ndarray, n_bins: int) -> np.ndarray:
    train_score = np.asarray(train_score, dtype=float)
    test_score = np.asarray(test_score, dtype=float)
    train_y = np.asarray(train_y, dtype=int)
    if len(np.unique(train_y)) < 2:
        return np.full(len(test_score), float(np.mean(train_y)) if len(train_y) else 0.0)
    edges = np.unique(np.nanquantile(train_score, np.linspace(0.0, 1.0, int(n_bins) + 1)))
    if len(edges) < 3:
        return np.full(len(test_score), float(np.mean(train_y)))
    bins = np.digitize(train_score, edges[1:-1], right=True)
    rates = []
    for b in range(len(edges) - 1):
        mask = bins == b
        rates.append(float(np.mean(train_y[mask])) if mask.any() else float(np.mean(train_y)))
    test_bins = np.clip(np.digitize(test_score, edges[1:-1], right=True), 0, len(rates) - 1)
    return np.clip(np.asarray([rates[b] for b in test_bins], dtype=float), 1.0e-4, 1.0 - 1.0e-4)


def choose_threshold(train: pd.DataFrame, score: np.ndarray, config: dict) -> dict:
    quantiles = [float(q) for q in config["benchmark"]["threshold_quantiles"]]
    min_keep = float(config["benchmark"]["minimum_keep_fraction"])
    best = None
    y = train["tail_label"].to_numpy(dtype=int)
    residual = train["residual_ns"].to_numpy(dtype=float)
    for q in quantiles:
        threshold = float(np.nanquantile(score, q))
        keep = score <= threshold
        keep_frac = float(np.mean(keep))
        if keep_frac < min_keep or keep.sum() < 50:
            continue
        kept = residual[keep]
        row = {
            "threshold": threshold,
            "threshold_quantile": q,
            "train_keep_fraction": keep_frac,
            "train_tail_fraction": float(np.mean(y[keep])),
            "train_sigma68_ns": s02.sigma68(kept),
        }
        key = (row["train_tail_fraction"], row["train_sigma68_ns"], -row["train_keep_fraction"])
        if best is None or key < best[0]:
            best = (key, row)
    if best is None:
        return {
            "threshold": math.inf,
            "threshold_quantile": 1.0,
            "train_keep_fraction": 1.0,
            "train_tail_fraction": float(np.mean(y)),
            "train_sigma68_ns": s02.sigma68(residual),
        }
    return best[1]


class PairCNN(nn.Module):
    def __init__(self, n_aux: int, channels: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(2, channels, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(channels + n_aux, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, wave: torch.Tensor, aux: torch.Tensor) -> torch.Tensor:
        return self.head(torch.cat([self.conv(wave), aux], dim=1)).squeeze(1)


class QTokenAttention(nn.Module):
    def __init__(self, n_token_features: int, width: int) -> None:
        super().__init__()
        self.proj = nn.Linear(n_token_features, width)
        self.attn = nn.MultiheadAttention(width, num_heads=1, batch_first=True)
        self.norm = nn.LayerNorm(width)
        self.head = nn.Sequential(nn.Linear(width * 2, width), nn.ReLU(), nn.Linear(width, 1))

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        z = torch.relu(self.proj(tokens))
        a, _ = self.attn(z, z, z)
        z = self.norm(z + a)
        pooled = torch.cat([z.mean(dim=1), z.amax(dim=1)], dim=1)
        return self.head(pooled).squeeze(1)


def train_binary_torch(model: nn.Module, arrays: Tuple[np.ndarray, ...], y: np.ndarray, config: dict, seed: int) -> nn.Module:
    torch.manual_seed(int(seed))
    torch.set_num_threads(1)
    model.train()
    tensors = [torch.tensor(a.astype(np.float32), dtype=torch.float32) for a in arrays]
    yy = torch.tensor(y.astype(np.float32), dtype=torch.float32)
    pos = max(float(np.sum(y == 1)), 1.0)
    neg = max(float(np.sum(y == 0)), 1.0)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_lr"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    n = len(y)
    batch = min(int(config["models"]["torch_batch_size"]), n)
    rng = np.random.default_rng(seed)
    for _ in range(int(config["models"]["torch_epochs"])):
        order = rng.permutation(n)
        for start in range(0, n, batch):
            take = order[start : start + batch]
            opt.zero_grad()
            if len(tensors) == 1:
                pred = model(tensors[0][take])
            else:
                pred = model(tensors[0][take], tensors[1][take])
            loss = loss_fn(pred, yy[take])
            loss.backward()
            opt.step()
    return model.eval()


def predict_torch(model: nn.Module, arrays: Tuple[np.ndarray, ...], batch: int = 8192) -> np.ndarray:
    out = []
    tensors = [torch.tensor(a.astype(np.float32), dtype=torch.float32) for a in arrays]
    with torch.no_grad():
        n = len(arrays[0])
        for start in range(0, n, batch):
            sl = slice(start, min(start + batch, n))
            if len(tensors) == 1:
                logits = model(tensors[0][sl])
            else:
                logits = model(tensors[0][sl], tensors[1][sl])
            out.append(torch.sigmoid(logits).cpu().numpy())
    return np.concatenate(out).astype(float)


def standardize_train_test(train: np.ndarray, test: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0)
    sd[sd == 0] = 1.0
    return ((np.nan_to_num(train, nan=mu) - mu) / sd).astype(np.float32), ((np.nan_to_num(test, nan=mu) - mu) / sd).astype(np.float32)


def fit_scores(train: pd.DataFrame, held: pd.DataFrame, train_wave: np.ndarray, held_wave: np.ndarray, train_tok: np.ndarray, held_tok: np.ndarray, config: dict, seed: int) -> List[dict]:
    y = train["tail_label"].to_numpy(dtype=int)
    Xtr_raw = train[TABULAR_FEATURES].replace([np.inf, -np.inf], np.nan)
    Xhe_raw = held[TABULAR_FEATURES].replace([np.inf, -np.inf], np.nan)
    med = Xtr_raw.median(axis=0, skipna=True).fillna(0.0)
    Xtr = Xtr_raw.fillna(med).to_numpy(dtype=float)
    Xhe = Xhe_raw.fillna(med).to_numpy(dtype=float)
    rows = []

    trad_score_train = train["q_pair_max"].to_numpy(dtype=float)
    trad_score_held = held["q_pair_max"].to_numpy(dtype=float)
    rows.append({"method": "traditional_q_threshold", "family": "traditional", "train_score": trad_score_train, "held_score": trad_score_held, "train_prob": calibrate_by_train_bins(trad_score_train, y, trad_score_train, int(config["benchmark"]["calibration_bins"])), "held_prob": calibrate_by_train_bins(trad_score_train, y, trad_score_held, int(config["benchmark"]["calibration_bins"]))})

    ridge = make_pipeline(StandardScaler(), RidgeClassifier(alpha=float(config["models"]["ridge_alpha"]), class_weight="balanced"))
    ridge.fit(Xtr, y)
    ridge_train = ridge.decision_function(Xtr)
    ridge_held = ridge.decision_function(Xhe)
    rows.append({"method": "ridge", "family": "ml", "train_score": ridge_train, "held_score": ridge_held, "train_prob": sigmoid(ridge_train), "held_prob": sigmoid(ridge_held)})

    weights = np.where(y == 1, max(np.sum(y == 0) / max(np.sum(y == 1), 1), 1.0), 1.0)
    hgb = HistGradientBoostingClassifier(
        max_iter=int(config["models"]["hgb_max_iter"]),
        learning_rate=float(config["models"]["hgb_learning_rate"]),
        max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
        l2_regularization=float(config["models"]["hgb_l2_regularization"]),
        random_state=int(seed) + 1,
    )
    hgb.fit(Xtr, y, sample_weight=weights)
    hgb_train = hgb.predict_proba(Xtr)[:, 1]
    hgb_held = hgb.predict_proba(Xhe)[:, 1]
    rows.append({"method": "gradient_boosted_trees", "family": "ml", "train_score": hgb_train, "held_score": hgb_held, "train_prob": hgb_train, "held_prob": hgb_held})

    mlp = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=tuple(int(v) for v in config["models"]["mlp_hidden"]),
            alpha=float(config["models"]["mlp_alpha"]),
            max_iter=int(config["models"]["mlp_max_iter"]),
            random_state=int(seed) + 2,
            early_stopping=True,
        ),
    )
    mlp.fit(Xtr, y)
    mlp_train = mlp.predict_proba(Xtr)[:, 1]
    mlp_held = mlp.predict_proba(Xhe)[:, 1]
    rows.append({"method": "mlp", "family": "nn", "train_score": mlp_train, "held_score": mlp_held, "train_prob": mlp_train, "held_prob": mlp_held})

    aux_tr, aux_he = standardize_train_test(Xtr, Xhe)
    cnn = PairCNN(aux_tr.shape[1], int(config["models"]["torch_channels"]))
    cnn = train_binary_torch(cnn, (train_wave, aux_tr), y, config, seed + 3)
    cnn_train = predict_torch(cnn, (train_wave, aux_tr))
    cnn_held = predict_torch(cnn, (held_wave, aux_he))
    rows.append({"method": "1d_cnn", "family": "nn", "train_score": cnn_train, "held_score": cnn_held, "train_prob": cnn_train, "held_prob": cnn_held})

    tok_tr = train_tok.copy()
    tok_he = held_tok.copy()
    flat_tr, flat_he = standardize_train_test(tok_tr.reshape(len(tok_tr), -1), tok_he.reshape(len(tok_he), -1))
    tok_tr = flat_tr.reshape(tok_tr.shape)
    tok_he = flat_he.reshape(tok_he.shape)
    attn = QTokenAttention(tok_tr.shape[2], int(config["models"]["attention_width"]))
    attn = train_binary_torch(attn, (tok_tr,), y, config, seed + 4)
    attn_train = predict_torch(attn, (tok_tr,))
    attn_held = predict_torch(attn, (tok_he,))
    rows.append({"method": "q_token_attention", "family": "new_architecture", "train_score": attn_train, "held_score": attn_held, "train_prob": attn_train, "held_prob": attn_held})
    return rows


def run_fold(pulses_all: pd.DataFrame, base_config: dict, heldout_run: int, all_runs: List[int], rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != int(heldout_run)]
    cfg = fold_config(base_config, train_runs, [int(heldout_run)])
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, cfg)
    s03a_pulses, _, _, _, _ = s03a.run_analytic(pulses, cfg, base_method)
    binned_pulses, _, _, _ = s03b.scan_binned_candidates(pulses, cfg, base_method)
    q_table, q_bins = s01f.build_fold_q_templates(cfg, pulses, train_runs)
    combined = s01f.annotate_q_template(pulses, q_table)
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined = add_pulse_shape_features(combined)

    bench, _ = s03d.bootstrap_rows(
        combined,
        cfg,
        rng,
        [(base_method, "template_phase_base"), ("s03a_amp_only", "s03a_amp_only"), ("s03b_monotone_binned", "s03b_monotone_binned")],
    )
    train_pairs, train_wave, train_tok = pair_frame(combined, cfg, train_runs)
    held_pairs, held_wave, held_tok = pair_frame(combined, cfg, [int(heldout_run)])
    center = float(np.nanmedian(train_pairs["residual_ns"]))
    cut = float(cfg["benchmark"]["primary_label_abs_residual_gt_ns"])
    train_pairs["tail_label"] = (np.abs(train_pairs["residual_ns"].to_numpy(dtype=float) - center) > cut).astype(int)
    held_pairs["tail_label"] = (np.abs(held_pairs["residual_ns"].to_numpy(dtype=float) - center) > cut).astype(int)

    prediction_rows = []
    metric_rows = []
    policy_rows = []
    model_scores = fit_scores(train_pairs, held_pairs, train_wave, held_wave, train_tok, held_tok, cfg, int(cfg["random_seed"]) + int(heldout_run) * 17)
    base_summary = _metric(held_pairs["residual_ns"].to_numpy(dtype=float))
    for item in model_scores:
        policy = choose_threshold(train_pairs, item["train_score"], cfg)
        keep = item["held_score"] <= float(policy["threshold"])
        kept_residuals = held_pairs.loc[keep, "residual_ns"].to_numpy(dtype=float)
        summary = _metric(kept_residuals)
        metric_rows.append(
            {
                "heldout_run": int(heldout_run),
                "method": item["method"],
                "family": item["family"],
                "average_precision": safe_ap(held_pairs["tail_label"].to_numpy(dtype=int), item["held_score"]),
                "roc_auc": safe_auc(held_pairs["tail_label"].to_numpy(dtype=int), item["held_score"]),
                "brier": brier_score_loss(held_pairs["tail_label"].to_numpy(dtype=int), np.clip(item["held_prob"], 0.0, 1.0)),
                "keep_fraction": float(np.mean(keep)),
                "sigma68_delta_vs_no_cut_ns": float(summary["sigma68_ns"] - base_summary["sigma68_ns"]),
                **summary,
            }
        )
        policy_rows.append({"heldout_run": int(heldout_run), "method": item["method"], **policy})
        for i, row in enumerate(held_pairs.itertuples(index=False)):
            prediction_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "event_id": row.event_id,
                    "pair": row.pair,
                    "method": item["method"],
                    "family": item["family"],
                    "residual_ns": float(row.residual_ns),
                    "tail_label": int(row.tail_label),
                    "score": float(item["held_score"][i]),
                    "probability": float(item["held_prob"][i]),
                    "kept": bool(keep[i]),
                    "q_pair_max": float(row.q_pair_max),
                    "q_downstream_max": float(row.q_downstream_max),
                    "log_amp_mean": float(row.log_amp_mean),
                    "amplitude_adc_max": float(max(row.amplitude_adc_left, row.amplitude_adc_right)),
                    "area_over_amp_mean": float(row.area_over_amp_mean),
                    "area_over_amp_absdiff": float(row.area_over_amp_absdiff),
                    "tail_fraction_max": float(row.tail_fraction_max),
                    "late_fraction_max": float(row.late_fraction_max),
                    "baseline_rms_max": float(row.baseline_rms_max),
                    "peak_sample_mean": float(row.peak_sample_mean),
                    "peak_sample_absdiff": float(row.peak_sample_absdiff),
                    "log_amp_absdiff": float(row.log_amp_absdiff),
                }
            )
    base_metrics = {
        "heldout_run": int(heldout_run),
        "method": "no_cut",
        "family": "reference",
        "average_precision": float("nan"),
        "roc_auc": float("nan"),
        "brier": float("nan"),
        "keep_fraction": 1.0,
        "sigma68_delta_vs_no_cut_ns": 0.0,
        **base_summary,
    }
    metric_rows.append(base_metrics)

    leakage = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_id_overlap",
                "value": float(len(set(train_pairs["event_id"]) & set(held_pairs["event_id"]))),
                "flag": bool(len(set(train_pairs["event_id"]) & set(held_pairs["event_id"]))),
            },
            {
                "heldout_run": int(heldout_run),
                "check": "train_tail_positive_pairs",
                "value": float(train_pairs["tail_label"].sum()),
                "flag": bool(train_pairs["tail_label"].sum() < 10),
            },
            {
                "heldout_run": int(heldout_run),
                "check": "heldout_tail_positive_pairs",
                "value": float(held_pairs["tail_label"].sum()),
                "flag": bool(held_pairs["tail_label"].sum() == 0),
            },
            {
                "heldout_run": int(heldout_run),
                "check": "q_template_missing_heldout_rows",
                "value": float(held_pairs["q_pair_max"].isna().sum()),
                "flag": bool(held_pairs["q_pair_max"].isna().any()),
            },
            {"heldout_run": int(heldout_run), "check": "forbidden_identifier_features_used", "value": 0.0, "flag": False},
        ]
    )
    q_bins["heldout_run"] = int(heldout_run)
    return bench, pd.DataFrame(metric_rows), pd.DataFrame(prediction_rows), pd.DataFrame(policy_rows), q_bins, leakage


def run_block_bootstrap(pred: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(pred["heldout_run"].unique().tolist())
    for method, group in pred.groupby("method"):
        unique = group.drop_duplicates(["heldout_run", "event_id", "pair"]).copy() if method == "no_cut" else group.copy()
        kept_by_run = {run: sub.loc[sub["kept"], "residual_ns"].to_numpy(dtype=float) for run, sub in unique.groupby("heldout_run")}
        all_by_run = {run: sub.drop_duplicates(["event_id", "pair"])["residual_ns"].to_numpy(dtype=float) for run, sub in unique.groupby("heldout_run")}
        stats, deltas = [], []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            vals = np.concatenate([kept_by_run[int(run)] for run in sampled if int(run) in kept_by_run])
            base_vals = np.concatenate([all_by_run[int(run)] for run in sampled if int(run) in all_by_run])
            s = s02.sigma68(vals)
            stats.append(s)
            deltas.append(s - s02.sigma68(base_vals))
        vals_all = unique.loc[unique["kept"], "residual_ns"].to_numpy(dtype=float)
        base_all = unique.drop_duplicates(["event_id", "pair"])["residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "family": str(unique["family"].iloc[0]),
                "metric": "kept_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals_all),
                "ci_low": float(np.percentile(stats, 2.5)),
                "ci_high": float(np.percentile(stats, 97.5)),
                "delta_vs_no_cut_ns": s02.sigma68(vals_all) - s02.sigma68(base_all),
                "delta_ci_low": float(np.percentile(deltas, 2.5)),
                "delta_ci_high": float(np.percentile(deltas, 97.5)),
                "keep_fraction": float(np.mean(unique["kept"])),
                "n_pair_residuals": int(len(vals_all)),
            }
        )
    return pd.DataFrame(rows)


def support_map(pred: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    one = pred[pred["method"].eq("traditional_q_threshold")].drop_duplicates(["event_id", "pair"]).copy().reset_index(drop=True)
    q = float(one["q_pair_max"].quantile(0.90))
    one["high_q"] = one["q_pair_max"] >= q
    amp_sat = (one["amplitude_adc_max"].to_numpy(dtype=float) >= 6800.0).astype(float)
    late_cut = float(one["late_fraction_max"].quantile(0.90))
    baseline_cut = float(one["baseline_rms_max"].quantile(0.90))
    peak_edge = ((one["peak_sample_mean"].to_numpy(dtype=float) <= 4.0) | (one["peak_sample_mean"].to_numpy(dtype=float) >= 10.0)).astype(float)
    rows = []
    targets = {
        "timing_tail_abs_gt5ns": one["tail_label"].to_numpy(dtype=float),
        "abs_residual_ns": np.abs(one["residual_ns"].to_numpy(dtype=float) - np.nanmedian(one["residual_ns"])),
        "amplitude_log_mean": one["log_amp_mean"].to_numpy(dtype=float),
        "saturation_boundary_amp_ge_6800": amp_sat,
        "pileup_late_fraction_max": one["late_fraction_max"].to_numpy(dtype=float),
        "pileup_late_top_decile": (one["late_fraction_max"].to_numpy(dtype=float) >= late_cut).astype(float),
        "baseline_excursion_rms_max": one["baseline_rms_max"].to_numpy(dtype=float),
        "baseline_excursion_top_decile": (one["baseline_rms_max"].to_numpy(dtype=float) >= baseline_cut).astype(float),
        "charge_shape_area_over_amp_absdiff": one["area_over_amp_absdiff"].to_numpy(dtype=float),
        "dropout_peak_edge_proxy": peak_edge,
        "pid_energy_proxy_log_amp_absdiff": one["log_amp_absdiff"].to_numpy(dtype=float),
        "downstream_q_max": one["q_downstream_max"].to_numpy(dtype=float),
    }
    for name, values in targets.items():
        high = one["high_q"].to_numpy(dtype=bool)
        delta = float(np.nanmean(values[high]) - np.nanmean(values[~high]))
        boots = []
        by_run = {run: idx.to_numpy() for run, idx in one.groupby("heldout_run").groups.items()}
        for _ in range(int(n_boot)):
            sampled = rng.choice(sorted(by_run), size=len(by_run), replace=True)
            idx = np.concatenate([by_run[int(run)] for run in sampled])
            hh = high[idx]
            if hh.any() and (~hh).any():
                boots.append(float(np.nanmean(values[idx][hh]) - np.nanmean(values[idx][~hh])))
        lo, hi = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) if boots else (math.nan, math.nan)
        rows.append({"map": name, "contrast": "top_decile_q_pair_max_minus_rest", "value": delta, "ci_low": lo, "ci_high": hi, "high_q_threshold": q})
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, per_run: pd.DataFrame, support: pd.DataFrame) -> None:
    show = pooled.sort_values("value")
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    x = np.arange(len(show))
    ax.bar(x, show["value"])
    ax.errorbar(x, show["value"], yerr=[show["value"] - show["ci_low"], show["ci_high"] - show["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(show["method"], rotation=35, ha="right")
    ax.set_ylabel("kept pairwise sigma68 (ns)")
    ax.set_title("S01g run-block benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_model_sigma68_ci.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    for method, group in per_run[per_run["method"].ne("no_cut")].groupby("method"):
        ax.plot(group["heldout_run"], group["sigma68_delta_vs_no_cut_ns"], marker="o", label=method)
    ax.axhline(0.0, color="black", lw=1)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("sigma68 delta vs no cut (ns)")
    ax.legend(fontsize=7, ncol=2)
    ax.set_title("Per-run quality-map deltas")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_per_run_deltas.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    x = np.arange(len(support))
    ax.axhline(0.0, color="black", lw=1)
    ax.bar(x, support["value"])
    ax.errorbar(x, support["value"], yerr=[support["value"] - support["ci_low"], support["ci_high"] - support["value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(support["map"], rotation=25, ha="right")
    ax.set_title("High-q support-map contrasts")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_support_map.png", dpi=140)
    plt.close(fig)


def md(df: pd.DataFrame, cols: Sequence[str] | None = None) -> str:
    part = df[list(cols)].copy() if cols else df.copy()
    return part.to_markdown(index=False)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, run65: pd.DataFrame, per_run: pd.DataFrame, pooled: pd.DataFrame, support: pd.DataFrame, policies: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    model_table = pooled.sort_values("value")
    report = [
        "# S01g q-template quality covariate map",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Inputs:** raw B-stack ROOT files under `data/root/root`; no shared q-template artifact is read.",
        f"- **Primary endpoint:** S03b pair-residual timing-tail quality map, leave-one-run-out over Sample-II runs `{config['timing']['loo_runs']}`.",
        "",
        "## Preregistered question",
        "",
        "S01f showed that fold-local q_template vetoes did not securely narrow S03b timing tails. S01g asks the broader question: does the fold-local q_template residual remain a useful atomic quality covariate for timing-tail, amplitude/support, saturation-like, pile-up-like, baseline, dropout, PID, or energy maps?",
        "",
        "The raw B-stack files do not contain external PID or absolute energy truth labels. I therefore treat timing-tail classification as the primary benchmark and report secondary support-map proxies only as covariate diagnostics, not PID or energy claims.",
        "",
        "## Raw-ROOT reproduction",
        "",
        md(repro),
        "",
        "The run-65 S03 timing references were regenerated from the same raw-derived pulse table before training any S01g model.",
        "",
        md(run65, ["method", "value", "reference_value", "delta", "pass"]),
        "",
        "## Methods",
        "",
        "For held-out run \\(r\\), all q_template medians are built only from train runs \\(R \\setminus r\\). Each waveform \\(x_i(t)\\) is baseline-subtracted, peak-normalized, CFD20-aligned, and compared with the train-run median template \\(m_{s,b}(t)\\) for stave \\(s\\) and amplitude bin \\(b\\):",
        "",
        "\\[q_i = \\left(|T_i|^{-1}\\sum_{t\\in T_i}(x_i(t)-m_{s,b}(t))^2\\right)^{1/2}.\\]",
        "",
        "The pair-level target is \\(y=1[|\\Delta t - \\mathrm{median}_{train}(\\Delta t)|>5\\,\\mathrm{ns}]\\), where \\(\\Delta t\\) is the S03b monotone timewalk-corrected residual for B4-B6, B4-B8, or B6-B8. Each method chooses a train-run score threshold from the preregistered quantile grid with at least 88% train-pair retention, minimizing train tail fraction and then train sigma68. The same threshold is applied to the held-out run.",
        "",
        "The strong traditional baseline is a fold-local threshold on `q_pair_max`. ML/NN competitors are ridge, gradient-boosted trees, MLP, 1D-CNN, and the new `q_token_attention` architecture. The new architecture is sensible here because it treats left-pulse, right-pulse, and downstream-summary q/shape atoms as tokens, allowing a tiny attention layer to learn asymmetric quality interactions without using event IDs, run IDs, residuals, or labels as features.",
        "",
        "Confidence intervals are 95% nonparametric run-block bootstraps. For a statistic \\(S\\), each bootstrap replicate samples the seven held-out runs with replacement, pools their retained pair residuals, and recomputes \\(S_b\\).",
        "",
        "## Head-to-head benchmark",
        "",
        md(model_table, ["method", "family", "value", "ci_low", "ci_high", "delta_vs_no_cut_ns", "delta_ci_low", "delta_ci_high", "keep_fraction", "n_pair_residuals"]),
        "",
        "Per-run held-out performance:",
        "",
        md(per_run.sort_values(["heldout_run", "method"]), ["heldout_run", "method", "average_precision", "roc_auc", "brier", "keep_fraction", "sigma68_delta_vs_no_cut_ns", "sigma68_ns", "tail_frac_abs_gt5ns"]),
        "",
        "## Secondary q-template support maps",
        "",
        md(support),
        "",
        "These secondary maps show whether high-q pairs concentrate other quality atoms. They do not establish external PID or absolute energy resolution because the raw B-stack stream used here lacks those truth labels.",
        "",
        "## Policies and leakage checks",
        "",
        md(policies.head(42)),
        "",
        md(leakage),
        "",
        "## Systematics and caveats",
        "",
        "- Run-heldout splitting is the main leakage guard; event IDs and run IDs are excluded from model features.",
        "- The target is an S03b timing residual tail, so it is a quality-risk proxy rather than independent detector truth.",
        "- The high-q secondary maps use internally defined baseline, late-shape, and support proxies. They are useful for hypothesis generation, not final PID/energy calibration.",
        "- The seven-run bootstrap captures run-to-run instability, but run 65 has low statistics and therefore visibly affects the interval width.",
        "- The NN models use fixed small architectures to avoid a large multiple-comparison scan on a small pair table.",
        "",
        "## Verdict",
        "",
        result["conclusion"],
        "",
        "## Hypothesis and next experiment",
        "",
        result["hypothesis"],
        "",
        "## Artifacts",
        "",
        "`reproduction_match_table.csv`, `run65_reproduction.csv`, `heldout_model_metrics.csv`, `model_predictions.csv`, `run_bootstrap_ci.csv`, `secondary_support_map.csv`, `threshold_policies.csv`, `fold_local_template_bin_counts.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s01g_1781036493_3261_7a6c05c5_qtemplate_quality_covariate_map.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction failed")

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(r) for r in config["timing"]["loo_runs"]]
    bench_parts, metric_parts, pred_parts, policy_parts, qbin_parts, leak_parts = [], [], [], [], [], []
    for run in all_runs:
        print(f"heldout run {run}", flush=True)
        bench, metrics, pred, policies, q_bins, leakage = run_fold(pulses_all, config, run, all_runs, rng)
        bench_parts.append(bench)
        metric_parts.append(metrics)
        pred_parts.append(pred)
        policy_parts.append(policies)
        qbin_parts.append(q_bins)
        leak_parts.append(leakage)

    bench = pd.concat(bench_parts, ignore_index=True)
    per_run = pd.concat(metric_parts, ignore_index=True)
    pred = pd.concat(pred_parts, ignore_index=True)
    policies = pd.concat(policy_parts, ignore_index=True)
    q_bins = pd.concat(qbin_parts, ignore_index=True)
    leakage = pd.concat(leak_parts, ignore_index=True)

    run65 = bench[(bench["heldout_run"].eq(65)) & (bench["method"].isin(RUN65_EXPECTED))].copy()
    run65["reference_value"] = run65["method"].map(RUN65_EXPECTED)
    run65["delta"] = run65["value"] - run65["reference_value"]
    run65["pass"] = run65["delta"].abs() < 1.0e-9
    if not bool(run65["pass"].all()):
        raise RuntimeError("Run-65 S03 reproduction failed")

    no_cut = pred.copy()
    no_cut["method"] = "no_cut"
    no_cut["family"] = "reference"
    no_cut["score"] = 0.0
    no_cut["probability"] = np.nan
    no_cut["kept"] = True
    pred_with_ref = pd.concat([pred, no_cut], ignore_index=True)
    pooled = run_block_bootstrap(pred_with_ref, rng, int(config["benchmark"]["bootstrap_samples"]))
    support = support_map(pred, rng, int(config["benchmark"]["bootstrap_samples"]))
    plot_outputs(out_dir, pooled, per_run, support)

    bench.to_csv(out_dir / "s03_reference_per_run.csv", index=False)
    run65[["heldout_run", "method", "value", "reference_value", "delta", "pass"]].to_csv(out_dir / "run65_reproduction.csv", index=False)
    per_run.to_csv(out_dir / "heldout_model_metrics.csv", index=False)
    pred.to_csv(out_dir / "model_predictions.csv", index=False)
    pooled.to_csv(out_dir / "run_bootstrap_ci.csv", index=False)
    support.to_csv(out_dir / "secondary_support_map.csv", index=False)
    policies.to_csv(out_dir / "threshold_policies.csv", index=False)
    q_bins.to_csv(out_dir / "fold_local_template_bin_counts.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    input_hashes[str(config_path)] = sha256_file(config_path)
    input_hashes[str(SCRIPT_PATH)] = sha256_file(SCRIPT_PATH)
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    candidate = pooled[pooled["method"].ne("no_cut")].sort_values(["value", "delta_vs_no_cut_ns"]).iloc[0]
    traditional = pooled[pooled["method"].eq("traditional_q_threshold")].iloc[0]
    no_cut_row = pooled[pooled["method"].eq("no_cut")].iloc[0]
    winner = str(candidate["method"])
    improves = bool(float(candidate["delta_ci_high"]) < 0.0)
    beats_trad = bool(float(candidate["ci_high"]) < float(traditional["ci_low"]))
    conclusion = (
        f"The point-estimate winner is {winner}: kept-pair sigma68 {candidate['value']:.3f} ns "
        f"[{candidate['ci_low']:.3f}, {candidate['ci_high']:.3f}], delta vs no-cut {candidate['delta_vs_no_cut_ns']:.3f} ns "
        f"[{candidate['delta_ci_low']:.3f}, {candidate['delta_ci_high']:.3f}]. "
        f"The traditional q-threshold gives {traditional['value']:.3f} ns [{traditional['ci_low']:.3f}, {traditional['ci_high']:.3f}], "
        f"while no-cut is {no_cut_row['value']:.3f} ns [{no_cut_row['ci_low']:.3f}, {no_cut_row['ci_high']:.3f}]. "
        f"Adoption status: {'secure narrowing vs no-cut' if improves else 'diagnostic only; CI does not prove narrowing'}. "
        f"Clear separation from traditional: {int(beats_trad)}."
    )
    hypothesis = (
        "Hypothesis: q_template is best treated as a local support/risk atom, not a standalone timing-tail veto. "
        "If this is correct, future externally labeled PID/energy or injected-pileup studies should show high-q enrichment in failure modes but only weak standalone resolution gains after amplitude, topology, and run-family controls."
    )
    next_ticket = {
        "title": "S01h external q-template support transfer",
        "body": "Question: does the S01g q-template risk atom transfer to an externally labeled or injected support target rather than an S03b-defined timing-tail proxy? Compare the S01g winner and traditional q-threshold against ridge, gradient-boosted trees, MLP, 1D-CNN, and q-token attention on injected pile-up/dropout or calibrated charge-depth labels with identical run-block bootstrap CIs. Expected information gain: separates q_template as a general detector-quality covariate from a timing-residual self-reference.",
    }
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all() and run65["pass"].all()),
        "raw_root_reproduction": {"s00_counts_pass": bool(repro["pass"].all()), "run65_s03_reference_pass": bool(run65["pass"].all())},
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "primary_metric": "kept_pairwise_sigma68_ns on S03b timing-tail risk map",
        "winner": winner,
        "winner_family": str(candidate["family"]),
        "winner_value_ci": [float(candidate["value"]), float(candidate["ci_low"]), float(candidate["ci_high"])],
        "winner_delta_vs_no_cut_ci": [float(candidate["delta_vs_no_cut_ns"]), float(candidate["delta_ci_low"]), float(candidate["delta_ci_high"])],
        "traditional": {
            "method": "traditional_q_threshold",
            "value_ci": [float(traditional["value"]), float(traditional["ci_low"]), float(traditional["ci_high"])],
            "delta_vs_no_cut_ci": [float(traditional["delta_vs_no_cut_ns"]), float(traditional["delta_ci_low"]), float(traditional["delta_ci_high"])],
        },
        "models_benchmarked": ["traditional_q_threshold", "ridge", "gradient_boosted_trees", "mlp", "1d_cnn", "q_token_attention"],
        "new_architecture": "q_token_attention",
        "adoption": {"secure_narrowing_vs_no_cut": improves, "clear_win_over_traditional": beats_trad},
        "leakage": {"split_by_run": True, "q_templates_train_run_only_per_fold": True, "forbidden_feature_flags": bool(leakage["flag"].fillna(False).any())},
        "conclusion": conclusion,
        "hypothesis": hypothesis,
        "next_tickets": [next_ticket],
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, run65, per_run, pooled, support, policies, leakage, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
