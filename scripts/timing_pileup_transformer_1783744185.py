#!/usr/bin/env python
"""Ticket 1783744185.18732.50fe0fac: timing-pileup disentanglement.

This script intentionally reads raw h101/HRDv ROOT waveforms.  It builds a
small, reproducible benchmark from Sample-II B-stack runs and compares a strong
traditional waveform method against ridge, gradient-boosted trees, MLP, 1D-CNN,
and a compact waveform transformer under leave-one-run-out evaluation.
"""

from __future__ import division, print_function

import argparse
import json
import math
import os
import random
import re
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import Ridge, RidgeClassifier
from sklearn.metrics import average_precision_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import uproot


TICKET = "1783744185.18732.50fe0fac"
STUDY = "timing_pileup_transformer"
WORKER = "testbeam-laptop-3"
EXPECTED_SELECTED = 640737
SAMPLE_II_ANALYSIS_RUNS = [58, 59, 60, 61, 62, 63, 65]
SAMPLES = 18
EVEN_CHANNELS = [0, 2, 4, 6]
CHANNEL_NAMES = {0: "B2", 2: "B4", 4: "B6", 6: "B8"}
STAVE_CM = {0: 0.0, 2: 20.0, 4: 40.0, 6: 60.0}
INV_V_NS_PER_CM = 0.078
RNG_SEED = 1783744185


def robust_sigma68(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    q84, q16 = np.percentile(x, [84, 16])
    return float(0.5 * (q84 - q16))


def ci_from_values(values, rng, n_boot=1200, alpha=0.05):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return [float("nan"), float("nan")]
    if len(values) == 1:
        return [float(values[0]), float(values[0])]
    draws = []
    for _ in range(n_boot):
        idx = rng.randint(0, len(values), len(values))
        draws.append(float(np.mean(values[idx])))
    return [float(np.percentile(draws, 100 * alpha / 2.0)), float(np.percentile(draws, 100 * (1 - alpha / 2.0)))]


def bootstrap_run_ci(frame, metric_col, rng, n_boot=1200):
    per_run = frame.groupby("run")[metric_col].mean().values.astype(float)
    return ci_from_values(per_run, rng, n_boot=n_boot)


def run_from_path(path):
    m = re.search(r"run_(\d+)", str(path))
    return int(m.group(1)) if m else -1


def root_dir_candidates():
    return [
        Path("/home/billy/ccb-data/extracted/root/root"),
        Path("/home/billy/Desktop/test_beam/data/root/root"),
        Path("data/root/root"),
        Path("data/extracted/root/root"),
    ]


def resolve_root_dir(cli_value):
    if cli_value:
        p = Path(cli_value)
        if p.exists():
            return p
    for p in root_dir_candidates():
        if p.exists():
            return p
    raise RuntimeError("No raw ROOT directory found")


def iter_batches(path, branches, step_size=20000):
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(branches, step_size=step_size, library="np"):
        yield batch


def baseline_subtract(waves):
    ped = np.median(waves[:, :, :4], axis=2, keepdims=True)
    return waves.astype(np.float32) - ped.astype(np.float32)


def cfd_time(w, frac=0.3):
    amp = float(np.max(w))
    if not np.isfinite(amp) or amp <= 0:
        return float(np.argmax(w))
    level = frac * amp
    imax = int(np.argmax(w))
    for i in range(1, imax + 1):
        if w[i] >= level:
            y0, y1 = float(w[i - 1]), float(w[i])
            if y1 == y0:
                return float(i)
            return float(i - 1 + (level - y0) / (y1 - y0))
    return float(imax)


def peak_time(w):
    i = int(np.argmax(w))
    if i <= 0 or i >= len(w) - 1:
        return float(i)
    y0, y1, y2 = float(w[i - 1]), float(w[i]), float(w[i + 1])
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-6:
        return float(i)
    return float(i + 0.5 * (y0 - y2) / denom)


def waveform_features(w, channel):
    w = np.asarray(w, dtype=np.float32)
    amp = float(np.max(w))
    area = float(np.sum(w))
    imax = int(np.argmax(w))
    xx = np.arange(len(w), dtype=np.float32)
    pos = np.maximum(w, 0)
    denom = float(np.sum(pos)) + 1e-6
    centroid = float(np.sum(xx * pos) / denom)
    width = float(np.sqrt(np.sum(((xx - centroid) ** 2) * pos) / denom))
    pre_std = float(np.std(w[:4]))
    tail = float(np.sum(w[imax + 1 :])) if imax + 1 < len(w) else 0.0
    rise = cfd_time(w, 0.8) - cfd_time(w, 0.2)
    norm = w / (abs(amp) + 1e-6)
    feats = [amp, math.log(max(amp, 1.0)), area, imax, peak_time(w), cfd_time(w, 0.2), cfd_time(w, 0.3),
             centroid, width, pre_std, tail, rise, float(channel), float(channel == 0), float(channel == 2),
             float(channel == 4), float(channel == 6), float(np.max(w) >= 4090)]
    feats.extend([float(v) for v in norm])
    return np.asarray(feats, dtype=np.float32)


def reproduce_counts_and_pulses(root_dir, max_pulses_per_run=900):
    total = 0
    per_run = defaultdict(int)
    per_sample_ii_channel = defaultdict(int)
    rows = []
    waves_by_run = defaultdict(list)
    paths = sorted(root_dir.glob("hrdb_run_*.root"))
    for path in paths:
        run = run_from_path(path)
        kept = 0
        for batch in iter_batches(path, ["EVENTNO", "EVT", "HRDv"]):
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, SAMPLES)
            waves = baseline_subtract(raw)
            amps = np.max(waves[:, EVEN_CHANNELS, :], axis=2)
            selected = amps > 1000.0
            nsel = int(np.sum(selected))
            # The S00/S01 analysis anchor is the report-domain B-stack data:
            # runs 31--65 with run 43 removed. Earlier runs are commissioning/
            # pre-split data and are present in the raw bundle but not in the
            # 640,737-pulse gate.
            if run >= 31 and run != 43:
                total += nsel
                per_run[run] += nsel
            if run in SAMPLE_II_ANALYSIS_RUNS:
                for ci, channel in enumerate(EVEN_CHANNELS):
                    per_sample_ii_channel[channel] += int(np.sum(selected[:, ci]))
                for eidx in range(waves.shape[0]):
                    chans = [EVEN_CHANNELS[ci] for ci in range(len(EVEN_CHANNELS)) if selected[eidx, ci]]
                    if len(chans) < 2:
                        continue
                    corrected_times = {}
                    for ch in chans:
                        ww = waves[eidx, ch, :]
                        corrected_times[ch] = cfd_time(ww, 0.3) - STAVE_CM[ch] * INV_V_NS_PER_CM
                    for ch in chans:
                        if kept >= max_pulses_per_run:
                            continue
                        ww = waves[eidx, ch, :].astype(np.float32)
                        other = [corrected_times[c] for c in chans if c != ch]
                        residual = corrected_times[ch] - float(np.median(other))
                        rows.append(
                            {
                                "run": run,
                                "event": int(batch["EVENTNO"][eidx]),
                                "channel": ch,
                                "residual_ns": residual,
                                "raw_time_ns": corrected_times[ch],
                                "amp": float(np.max(ww)),
                                "features": waveform_features(ww, ch),
                                "wave": ww,
                            }
                        )
                        waves_by_run[run].append(ww)
                        kept += 1
    repro = [
        {"quantity": "total selected B-stave pulses", "report_value": EXPECTED_SELECTED, "reproduced": int(total), "delta": int(total - EXPECTED_SELECTED), "pass": bool(total == EXPECTED_SELECTED)},
        {"quantity": "sample_ii_analysis selected_pulses", "report_value": 125096, "reproduced": int(sum(per_run[r] for r in SAMPLE_II_ANALYSIS_RUNS)), "delta": int(sum(per_run[r] for r in SAMPLE_II_ANALYSIS_RUNS) - 125096), "pass": bool(sum(per_run[r] for r in SAMPLE_II_ANALYSIS_RUNS) == 125096)},
    ]
    for ch, expected in [(0, 88213), (2, 21229), (4, 11148), (6, 4506)]:
        val = int(per_sample_ii_channel[ch])
        repro.append({"quantity": "sample_ii_analysis %s" % CHANNEL_NAMES[ch], "report_value": expected, "reproduced": val, "delta": val - expected, "pass": bool(val == expected)})
    return repro, rows, waves_by_run, dict(per_run)


def fit_predict_sklearn_reg(method, xtr, ytr, xte):
    if method == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
    elif method == "gradient_boosted_trees":
        model = GradientBoostingRegressor(random_state=RNG_SEED, n_estimators=90, max_depth=2, learning_rate=0.05)
    elif method == "mlp":
        model = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=0.01, max_iter=450, random_state=RNG_SEED, early_stopping=True))
    else:
        raise ValueError(method)
    model.fit(xtr, ytr)
    return model.predict(xte)


class CNNRegressor(nn.Module):
    def __init__(self):
        super(CNNRegressor, self).__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 8, 3, padding=1), nn.ReLU(),
            nn.Conv1d(8, 12, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1), nn.Flatten(),
            nn.Linear(12, 12), nn.ReLU(), nn.Linear(12, 1),
        )

    def forward(self, x):
        return self.net(x)


class TinyTransformerRegressor(nn.Module):
    def __init__(self):
        super(TinyTransformerRegressor, self).__init__()
        self.proj = nn.Linear(1, 16)
        layer = nn.TransformerEncoderLayer(d_model=16, nhead=2, dim_feedforward=32, dropout=0.0, batch_first=True)
        self.enc = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Sequential(nn.Linear(16, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):
        # x: batch, 1, samples
        z = x.transpose(1, 2)
        z = self.proj(z)
        z = self.enc(z)
        return self.head(z.mean(dim=1))


def normalize_waves(w):
    w = np.asarray(w, dtype=np.float32)
    amp = np.max(np.abs(w), axis=1, keepdims=True) + 1e-6
    return w / amp


def fit_predict_torch(kind, wtr, ytr, wte, epochs=45):
    torch.manual_seed(RNG_SEED)
    np.random.seed(RNG_SEED)
    model = CNNRegressor() if kind == "1d_cnn" else TinyTransformerRegressor()
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    x = torch.tensor(normalize_waves(wtr)[:, None, :], dtype=torch.float32)
    y = torch.tensor(np.asarray(ytr, dtype=np.float32)[:, None], dtype=torch.float32)
    for _ in range(epochs):
        perm = torch.randperm(x.shape[0])
        for start in range(0, x.shape[0], 96):
            idx = perm[start : start + 96]
            pred = model(x[idx])
            loss = torch.mean((pred - y[idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        xt = torch.tensor(normalize_waves(wte)[:, None, :], dtype=torch.float32)
        return model(xt).numpy().reshape(-1)


def timing_benchmark(rows):
    df = pd.DataFrame([{k: v for k, v in row.items() if k not in ("features", "wave")} for row in rows])
    x = np.vstack([row["features"] for row in rows])
    w = np.vstack([row["wave"] for row in rows])
    y = df["residual_ns"].values.astype(float)
    out = []
    pred_store = {}
    for test_run in SAMPLE_II_ANALYSIS_RUNS:
        tr = df["run"].values != test_run
        te = df["run"].values == test_run
        for method in ["ridge", "gradient_boosted_trees", "mlp"]:
            pred = fit_predict_sklearn_reg(method, x[tr], y[tr], x[te])
            pred_store.setdefault(method, []).append((te, pred))
        # Strong traditional amplitude/timewalk model: log-amplitude polynomial plus channel indicators.
        amp_feats = x[:, [0, 1, 3, 12, 13, 14, 15, 16, 17]]
        pred_store.setdefault("traditional_template_timewalk", []).append((te, fit_predict_sklearn_reg("ridge", amp_feats[tr], y[tr], amp_feats[te])))
        pred_store.setdefault("1d_cnn", []).append((te, fit_predict_torch("1d_cnn", w[tr], y[tr], w[te], epochs=35)))
        pred_store.setdefault("compact_waveform_transformer", []).append((te, fit_predict_torch("transformer", w[tr], y[tr], w[te], epochs=35)))
    for method, chunks in pred_store.items():
        pred_all = np.zeros_like(y, dtype=float)
        mask_all = np.zeros_like(y, dtype=bool)
        for mask, pred in chunks:
            pred_all[mask] = pred
            mask_all |= mask
        corrected = y[mask_all] - pred_all[mask_all]
        tmp = df.loc[mask_all, ["run", "residual_ns"]].copy()
        tmp["corrected"] = corrected
        tmp["abs_corrected"] = np.abs(corrected)
        by_run = []
        for run, g in tmp.groupby("run"):
            by_run.append({"run": int(run), "sigma68_ns": robust_sigma68(g["corrected"].values), "bias_ns": float(np.mean(g["corrected"].values)), "tail_frac_abs_gt3ns": float(np.mean(np.abs(g["corrected"].values) > 3.0)), "n": int(len(g))})
        run_df = pd.DataFrame(by_run)
        out.append(
            {
                "model": method,
                "sigma68_ns": float(np.mean(run_df["sigma68_ns"])),
                "sigma68_ci": ci_from_values(run_df["sigma68_ns"].values, np.random.RandomState(RNG_SEED + 1)),
                "timing_bias_ns": float(np.mean(run_df["bias_ns"])),
                "timing_bias_ci": ci_from_values(run_df["bias_ns"].values, np.random.RandomState(RNG_SEED + 2)),
                "tail_frac_abs_gt3ns": float(np.mean(run_df["tail_frac_abs_gt3ns"])),
                "n_pulses": int(len(tmp)),
                "per_run": by_run,
            }
        )
    return sorted(out, key=lambda r: r["sigma68_ns"])


def shift_wave(w, shift):
    x = np.arange(SAMPLES)
    return np.interp(x - shift, x, w, left=0.0, right=0.0).astype(np.float32)


def make_pileup_data(waves_by_run, per_run=420):
    rng = np.random.RandomState(RNG_SEED + 7)
    rows = []
    for run in SAMPLE_II_ANALYSIS_RUNS:
        waves = np.asarray(waves_by_run[run], dtype=np.float32)
        if len(waves) < 20:
            continue
        template = np.median(normalize_waves(waves[: min(len(waves), 500)]), axis=0)
        for i in range(per_run):
            if i % 2 == 0:
                a, b = rng.randint(0, len(waves), 2)
                sep = float(rng.uniform(1.0, 6.0))
                mix = waves[a] + rng.uniform(0.45, 0.95) * shift_wave(waves[b], sep)
                label = 1
            else:
                a = rng.randint(0, len(waves))
                sep = 0.0
                mix = waves[a].copy()
                label = 0
            noise = rng.normal(0, max(1.0, 0.01 * np.max(mix)), size=SAMPLES)
            mix = mix + noise.astype(np.float32)
            amp = np.max(np.abs(mix)) + 1e-6
            nw = mix / amp
            feats = [float(np.max(mix)), float(np.sum(mix)), float(np.argmax(mix)), float(np.std(mix[:4])), float(np.sum(mix[10:])), float(np.max(mix) >= 4090)]
            feats.extend([float(v) for v in nw])
            # Traditional constrained two-pulse scan against the empirical template.
            one = np.linalg.lstsq(np.vstack([template, np.ones(SAMPLES)]).T, nw, rcond=None)[0]
            sse_one = float(np.sum((nw - (one[0] * template + one[1])) ** 2))
            best_sse, best_sep = sse_one, 0.0
            for sep_grid in np.linspace(1.0, 6.0, 11):
                shifted = shift_wave(template, sep_grid)
                mat = np.vstack([template, shifted, np.ones(SAMPLES)]).T
                coef = np.linalg.lstsq(mat, nw, rcond=None)[0]
                if coef[0] < 0 or coef[1] < 0:
                    continue
                sse = float(np.sum((nw - mat.dot(coef)) ** 2))
                if sse < best_sse:
                    best_sse, best_sep = sse, float(sep_grid)
            rows.append({"run": run, "label": label, "sep": sep, "wave": nw.astype(np.float32), "features": np.asarray(feats, dtype=np.float32), "trad_score": sse_one - best_sse, "trad_sep": best_sep, "trad_residual": best_sse})
    return rows


def fit_predict_sklearn_cls_reg(method, xtr, ytr, sep_tr, xte):
    if method == "ridge":
        cls = make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0))
        reg = make_pipeline(StandardScaler(), Ridge(alpha=5.0))
    elif method == "gradient_boosted_trees":
        cls = GradientBoostingClassifier(random_state=RNG_SEED, n_estimators=80, max_depth=2, learning_rate=0.05)
        reg = GradientBoostingRegressor(random_state=RNG_SEED, n_estimators=80, max_depth=2, learning_rate=0.05)
    elif method == "mlp":
        cls = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(40, 20), alpha=0.01, max_iter=350, random_state=RNG_SEED, early_stopping=True))
        reg = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(40, 20), alpha=0.01, max_iter=350, random_state=RNG_SEED, early_stopping=True))
    cls.fit(xtr, ytr)
    pos = ytr == 1
    reg.fit(xtr[pos], sep_tr[pos])
    if hasattr(cls, "predict_proba"):
        score = cls.predict_proba(xte)[:, 1]
    else:
        score = cls.decision_function(xte)
    sep = reg.predict(xte)
    return np.asarray(score, dtype=float), np.asarray(sep, dtype=float)


class TorchPileupNet(nn.Module):
    def __init__(self, kind):
        super(TorchPileupNet, self).__init__()
        self.kind = kind
        if kind == "1d_cnn":
            self.body = nn.Sequential(nn.Conv1d(1, 8, 3, padding=1), nn.ReLU(), nn.Conv1d(8, 12, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool1d(1), nn.Flatten())
            dim = 12
        else:
            self.proj = nn.Linear(1, 16)
            layer = nn.TransformerEncoderLayer(d_model=16, nhead=2, dim_feedforward=32, dropout=0.0, batch_first=True)
            self.body = nn.TransformerEncoder(layer, num_layers=1)
            dim = 16
        self.cls = nn.Linear(dim, 1)
        self.reg = nn.Linear(dim, 1)

    def embed(self, x):
        if self.kind == "1d_cnn":
            return self.body(x)
        z = self.proj(x.transpose(1, 2))
        return self.body(z).mean(dim=1)

    def forward(self, x):
        z = self.embed(x)
        return self.cls(z), self.reg(z)


def fit_predict_torch_pileup(kind, wtr, ytr, sep_tr, wte, epochs=30):
    torch.manual_seed(RNG_SEED)
    model = TorchPileupNet(kind)
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    x = torch.tensor(np.asarray(wtr, dtype=np.float32)[:, None, :], dtype=torch.float32)
    y = torch.tensor(np.asarray(ytr, dtype=np.float32)[:, None], dtype=torch.float32)
    sep = torch.tensor(np.asarray(sep_tr, dtype=np.float32)[:, None], dtype=torch.float32)
    for _ in range(epochs):
        perm = torch.randperm(x.shape[0])
        for start in range(0, x.shape[0], 128):
            idx = perm[start : start + 128]
            logit, pred_sep = model(x[idx])
            cls_loss = nn.functional.binary_cross_entropy_with_logits(logit, y[idx])
            pos = y[idx] > 0.5
            reg_loss = torch.mean((pred_sep[pos] - sep[idx][pos]) ** 2) if torch.any(pos) else 0.0 * cls_loss
            loss = cls_loss + 0.12 * reg_loss
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        xt = torch.tensor(np.asarray(wte, dtype=np.float32)[:, None, :], dtype=torch.float32)
        logit, pred_sep = model(xt)
        score = torch.sigmoid(logit).numpy().reshape(-1)
        return score, pred_sep.numpy().reshape(-1)


def pileup_benchmark(rows):
    df = pd.DataFrame([{k: v for k, v in row.items() if k not in ("features", "wave")} for row in rows])
    x = np.vstack([row["features"] for row in rows])
    w = np.vstack([row["wave"] for row in rows])
    y = df["label"].values.astype(int)
    sep = df["sep"].values.astype(float)
    pred = defaultdict(list)
    for test_run in SAMPLE_II_ANALYSIS_RUNS:
        tr = df["run"].values != test_run
        te = df["run"].values == test_run
        for method in ["ridge", "gradient_boosted_trees", "mlp"]:
            pred[method].append((te,) + fit_predict_sklearn_cls_reg(method, x[tr], y[tr], sep[tr], x[te]))
        pred["1d_cnn"].append((te,) + fit_predict_torch_pileup("1d_cnn", w[tr], y[tr], sep[tr], w[te], epochs=25))
        pred["compact_waveform_transformer"].append((te,) + fit_predict_torch_pileup("transformer", w[tr], y[tr], sep[tr], w[te], epochs=25))
    trad_score = df["trad_score"].values.astype(float)
    trad_sep = df["trad_sep"].values.astype(float)
    pred["traditional_template_deconvolution"] = [(np.ones(len(df), dtype=bool), trad_score, trad_sep)]
    out = []
    for method, chunks in pred.items():
        score = np.zeros(len(df), dtype=float)
        sep_pred = np.zeros(len(df), dtype=float)
        mask_all = np.zeros(len(df), dtype=bool)
        for mask, sc, sp in chunks:
            score[mask] = sc
            sep_pred[mask] = sp
            mask_all |= mask
        tmp = df.loc[mask_all, ["run", "label", "sep", "trad_residual"]].copy()
        tmp["score"] = score[mask_all]
        tmp["sep_pred"] = sep_pred[mask_all]
        run_rows = []
        for run, g in tmp.groupby("run"):
            pos = g["label"].values == 1
            ap = float(average_precision_score(g["label"].values, g["score"].values))
            sep_rmse = float(np.sqrt(np.mean((g.loc[pos, "sep_pred"].values - g.loc[pos, "sep"].values) ** 2)))
            sep_bias = float(np.mean(g.loc[pos, "sep_pred"].values - g.loc[pos, "sep"].values))
            run_rows.append({"run": int(run), "average_precision": ap, "separation_rmse_samples": sep_rmse, "separation_bias_samples": sep_bias, "n": int(len(g))})
        rdf = pd.DataFrame(run_rows)
        out.append(
            {
                "model": method,
                "average_precision": float(np.mean(rdf["average_precision"])),
                "average_precision_ci": ci_from_values(rdf["average_precision"].values, np.random.RandomState(RNG_SEED + 3)),
                "separation_rmse_samples": float(np.mean(rdf["separation_rmse_samples"])),
                "separation_rmse_ci": ci_from_values(rdf["separation_rmse_samples"].values, np.random.RandomState(RNG_SEED + 4)),
                "separation_bias_samples": float(np.mean(rdf["separation_bias_samples"])),
                "n_waveforms": int(len(tmp)),
                "per_run": run_rows,
            }
        )
    return sorted(out, key=lambda r: (-r["average_precision"], r["separation_rmse_samples"]))


def write_table(rows, cols):
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in rows:
        vals = []
        for c in cols:
            v = row.get(c, "")
            if isinstance(v, float):
                vals.append("%.4g" % v)
            elif isinstance(v, list):
                vals.append("[%.4g, %.4g]" % (v[0], v[1]))
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def systematics(timing_rows, pileup_rows):
    timing_best = timing_rows[0]
    trad = [r for r in timing_rows if r["model"] == "traditional_template_timewalk"][0]
    pile_best = pileup_rows[0]
    pile_trad = [r for r in pileup_rows if r["model"] == "traditional_template_deconvolution"][0]
    return {
        "timing_ml_minus_traditional_sigma68_ns": float(timing_best["sigma68_ns"] - trad["sigma68_ns"]),
        "pileup_ap_minus_traditional": float(pile_best["average_precision"] - pile_trad["average_precision"]),
        "pedestal_sensitivity_note": "Pedestal enters via median(samples 0:4); pretrigger std is included as a nuisance feature and reported as a caveat rather than varied because raw forced-trigger pedestal labels are absent in this ticket.",
        "saturation_note": "Saturation is tracked by max ADC near 4090 and by tail fractions; saturated pulses are not removed, so the reported score is an inclusive failure-mode benchmark.",
    }


def make_report(out_dir, result, timing_rows, pileup_rows):
    report = []
    report.append("# Study report: timing-pileup disentanglement with waveform transformers")
    report.append("")
    report.append("- **Ticket:** `%s`" % TICKET)
    report.append("- **Worker:** `%s`" % WORKER)
    report.append("- **Input raw ROOT:** `%s`" % result["raw_root_dir"])
    report.append("- **Run split:** leave-one-run-out over Sample-II analysis runs `%s`" % ", ".join(map(str, SAMPLE_II_ANALYSIS_RUNS)))
    report.append("")
    report.append("## Abstract")
    report.append("This benchmark asks whether learned waveform models improve timing-pileup disentanglement over a strong traditional comparator. The raw ROOT reproduction gate reads `h101/HRDv`, subtracts the median of samples 0--3, and applies the canonical B-stave amplitude threshold `A > 1000` to even physical B channels in report-domain runs 31--65 with run 43 removed. The gate reproduces the S00 count exactly before model training. Timing is evaluated as event-internal residual correction, and pile-up is evaluated on injected two-pulse mixtures built from real selected B-stave waveforms. The named winner in `result.json` is selected by a composite rank of timing robust width and pile-up recovery.")
    report.append("")
    report.append("## Raw ROOT reproduction")
    report.append(write_table(result["raw_reproduction"], ["quantity", "report_value", "reproduced", "delta", "pass"]))
    report.append("")
    report.append("## Methods")
    report.append("For an event `e` and B-stave channel `i`, the baseline-subtracted waveform is `w_{e,i,k}=HRDv_{e,i,k}-median(HRDv_{e,i,0:3})`. A selected pulse satisfies `max_k w_{e,i,k}>1000`. The timing pickoff is a CFD crossing at 30% amplitude, corrected by a fixed propagation term `x_i/v`, `v^{-1}=0.078 ns/cm`. The supervised residual target is")
    report.append("")
    report.append("`r_{e,i}=t_{e,i}^{CFD30}-x_i/v-median_{j != i}(t_{e,j}^{CFD30}-x_j/v)`.") 
    report.append("")
    report.append("Each model predicts `hat r_{e,i}` from the same pulse waveform only, and the corrected residual is `r_{e,i}-hat r_{e,i}`. The traditional method is a regularized template/timewalk surrogate using amplitude, log-amplitude, peak phase, saturation, and channel indicators. Ridge, gradient-boosted trees, and MLP use the full handcrafted pulse descriptor plus normalized waveform samples. The 1D-CNN and compact waveform transformer consume only normalized 18-sample waveforms. Pile-up positives are formed as `w_a + alpha w_b(k-delta)` using real selected waveforms; negatives are single pulses with matched noise. The traditional two-pulse method scans separations, solves constrained non-negative template amplitudes by least squares, and scores the one-pulse versus two-pulse SSE improvement.")
    report.append("")
    report.append("## Timing residual correction")
    report.append(write_table(timing_rows, ["model", "sigma68_ns", "sigma68_ci", "timing_bias_ns", "timing_bias_ci", "tail_frac_abs_gt3ns", "n_pulses"]))
    report.append("")
    report.append("## Two-pulse recovery")
    report.append(write_table(pileup_rows, ["model", "average_precision", "average_precision_ci", "separation_rmse_samples", "separation_rmse_ci", "separation_bias_samples", "n_waveforms"]))
    report.append("")
    report.append("## Composite result")
    report.append("The overall winner is **%s**. The timing winner is **%s** with sigma68 %.3f ns, and the pile-up winner is **%s** with AP %.3f and separation RMSE %.3f samples." % (result["winner"]["overall"], result["winner"]["timing"], result["winner"]["timing_sigma68_ns"], result["winner"]["pileup"], result["winner"]["pileup_average_precision"], result["winner"]["pileup_separation_rmse_samples"]))
    report.append("")
    report.append("## Systematics and caveats")
    report.append("- **Run splitting:** all reported confidence intervals bootstrap over held-out run summaries, not over rows, so event multiplicity within a run does not masquerade as independent exposure.")
    report.append("- **Pedestal sensitivity:** the baseline estimator is fixed to the canonical median of samples 0--3; pretrigger standard deviation is exposed to tabular models as a nuisance coordinate. A future forced-trigger pedestal transfer should vary this explicitly.")
    report.append("- **Saturation failure modes:** saturated or near-saturated pulses are retained. The `max ADC >= 4090` indicator is available to tabular models, while waveform-only neural methods must infer clipping from shape.")
    report.append("- **Two-pulse truth:** pile-up labels and separations are injected from real raw waveforms rather than externally labeled beam pile-up. This gives controlled separation truth but may understate pathologies from real multi-particle event topology.")
    report.append("- **Transformer capacity:** the compact transformer has one encoder layer and two attention heads. It is deliberately small to keep the comparison in the data-limited regime; this is an architecture test, not a maximum-capacity sweep.")
    report.append("")
    report.append("## Novel follow-up ticket")
    report.append("At most one follow-up is appended in `result.json`: validate the winning compact waveform model on externally tagged pile-up or forced-trigger pedestal runs, because this study uses injected overlap truth.")
    (out_dir / "REPORT.md").write_text("\n".join(report) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-dir", default=None)
    parser.add_argument("--out-dir", default="reports/1783744185.18732.50fe0fac__timing_pileup_transformer")
    parser.add_argument("--max-pulses-per-run", type=int, default=900)
    args = parser.parse_args()
    random.seed(RNG_SEED)
    np.random.seed(RNG_SEED)
    t0 = time.time()
    root_dir = resolve_root_dir(args.root_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    repro, pulse_rows, waves_by_run, per_run_counts = reproduce_counts_and_pulses(root_dir, max_pulses_per_run=args.max_pulses_per_run)
    if not all(r["pass"] for r in repro):
        raise RuntimeError("Raw ROOT reproduction gate failed: %s" % repro)
    timing_rows = timing_benchmark(pulse_rows)
    pile_rows = pileup_benchmark(make_pileup_data(waves_by_run))
    # Composite rank: normalized timing rank + pileup rank. Lower is better.
    ranks = defaultdict(float)
    for i, r in enumerate(timing_rows):
        ranks[r["model"]] += i + 1
    for i, r in enumerate(pile_rows):
        ranks[r["model"]] += i + 1
    overall = sorted(ranks.items(), key=lambda kv: kv[1])[0][0]
    result = {
        "ticket": TICKET,
        "study": STUDY,
        "worker": WORKER,
        "raw_root_dir": str(root_dir),
        "reproduced": True,
        "raw_reproduction": repro,
        "per_run_selected_counts": {str(k): int(v) for k, v in sorted(per_run_counts.items())},
        "timing": timing_rows,
        "pileup": pile_rows,
        "systematics": systematics(timing_rows, pile_rows),
        "winner": {
            "overall": overall,
            "timing": timing_rows[0]["model"],
            "timing_sigma68_ns": timing_rows[0]["sigma68_ns"],
            "timing_sigma68_ci": timing_rows[0]["sigma68_ci"],
            "pileup": pile_rows[0]["model"],
            "pileup_average_precision": pile_rows[0]["average_precision"],
            "pileup_average_precision_ci": pile_rows[0]["average_precision_ci"],
            "pileup_separation_rmse_samples": pile_rows[0]["separation_rmse_samples"],
            "pileup_separation_rmse_ci": pile_rows[0]["separation_rmse_ci"],
        },
        "next_tickets": [
            {
                "title": "Validate waveform-transformer pile-up disentanglement on external pedestal and tagged-overlap controls",
                "body": "Run the winning timing-pileup model from ticket 1783744185.18732.50fe0fac on forced-trigger pedestal windows and any externally tagged overlap/control runs. Keep the same leave-run-out bootstrap, but replace injected overlap truth with externally anchored pile-up labels where available.",
            }
        ],
        "runtime_seconds": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    make_report(out_dir, result, timing_rows, pile_rows)
    print("Wrote", out_dir)
    print("Winner", result["winner"])


if __name__ == "__main__":
    main()
