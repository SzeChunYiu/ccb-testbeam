#!/usr/bin/env python3
"""S31a frequency-domain pulse-shape timing/PID benchmark.

The analysis intentionally starts from raw ROOT, reproduces the canonical
selected-pulse count, then evaluates traditional Fourier/wavelet/CFD features
against ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact spectral
transformer on run-held-out endpoint proxies derived from the same waveforms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s31a")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge, RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import t07_tradshape_ml_benchmark as t07

STAVE_NAMES = t07.STAVE_NAMES
torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))


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


def one_hot_stave(meta: pd.DataFrame) -> np.ndarray:
    out = np.zeros((len(meta), len(STAVE_NAMES)), dtype=np.float32)
    idx = meta["stave_idx"].to_numpy(dtype=int)
    out[np.arange(len(meta)), idx] = 1.0
    return out


def sigma68(residual: np.ndarray) -> float:
    residual = np.asarray(residual, dtype=float)
    residual = residual[np.isfinite(residual)]
    if len(residual) == 0:
        return float("nan")
    q16, q84 = np.quantile(residual, [0.16, 0.84])
    return float(0.5 * (q84 - q16))


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def make_endpoint_targets(waves: np.ndarray, meta: pd.DataFrame, feats: pd.DataFrame, train_mask: np.ndarray) -> Tuple[pd.DataFrame, Dict[str, dict]]:
    x = waves.astype(np.float64)
    fft = np.abs(np.fft.rfft(x - x.mean(axis=1, keepdims=True), axis=1))
    hi = fft[:, 4:].sum(axis=1) / np.maximum(fft[:, 1:].sum(axis=1), 1e-9)
    tail = feats["tail_12_17_over_total"].to_numpy(dtype=float)
    fall = -feats["max_fall_step"].to_numpy(dtype=float)
    cfd50 = feats["cfd50_time"].to_numpy(dtype=float)
    amp = meta["amplitude_adc"].to_numpy(dtype=float)
    log_amp = np.log1p(np.maximum(amp, 0.0))
    odd_ratio = meta["target_odd_neg_amp"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    pedestal = meta["baseline_adc"].to_numpy(dtype=float)
    pedestal_residual = pedestal.copy()
    energy_residual = log_amp.copy()
    timing_residual = cfd50.copy()
    for run in np.unique(meta["run"]):
        for stave in np.unique(meta["stave_idx"]):
            m = (meta["run"].to_numpy() == run) & (meta["stave_idx"].to_numpy() == stave)
            if m.any():
                pedestal_residual[m] -= np.median(pedestal[m])
                energy_residual[m] -= np.median(log_amp[m])
                timing_residual[m] -= np.nanmedian(cfd50[m])
    plateau = (np.abs(x - x.max(axis=1, keepdims=True)) < 0.015).sum(axis=1)
    pile = 0.55 * tail + 0.45 * np.clip(fall, 0.0, None)
    color = np.abs(pedestal_residual) + 0.4 * np.abs(feats["late_minus_early_asym"].to_numpy(dtype=float))
    pid_proxy = odd_ratio + 0.2 * feats["fft_k1_fraction"].to_numpy(dtype=float) - 0.1 * tail

    def high_label(values: np.ndarray, q: float) -> Tuple[np.ndarray, float]:
        threshold = float(np.quantile(values[train_mask], q))
        return (values >= threshold).astype(np.int8), threshold

    labels = pd.DataFrame(
        {
            "pulse_shape_harmonics": high_label(hi, 0.75)[0],
            "pileup_sideband": high_label(pile, 0.80)[0],
            "saturation_clipping": ((amp >= np.quantile(amp[train_mask], 0.92)) | (plateau >= 3)).astype(np.int8),
            "pedestal_noise_color": high_label(color, 0.80)[0],
            "pid_separation": high_label(pid_proxy, 0.50)[0],
            "timing_residual": timing_residual.astype(np.float32),
            "energy_scale": energy_residual.astype(np.float32),
        }
    )
    definitions = {
        "pulse_shape_harmonics": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "top-quartile high-frequency FFT power fraction after removing waveform mean"},
        "timing_residual": {"kind": "regression", "metric": "sigma68", "better": "lower", "definition": "CFD50 time minus run/stave median CFD50 time"},
        "pileup_sideband": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "top-quintile late-tail plus negative-step sideband score"},
        "saturation_clipping": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "high-amplitude or flat-top pulse proxy for ADC clipping/saturation"},
        "pedestal_noise_color": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "top-quintile run/stave pedestal residual plus early-late color proxy"},
        "energy_scale": {"kind": "regression", "metric": "sigma68", "better": "lower", "definition": "log-amplitude energy proxy minus run/stave median"},
        "pid_separation": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "median-split duplicate-readout response ratio with low-order harmonic context; PID proxy, not truth PID"},
    }
    return labels, definitions


class WaveCNN(nn.Module):
    def __init__(self, n_staves: int, regression: bool) -> None:
        super().__init__()
        self.regression = regression
        self.conv = nn.Sequential(
            nn.Conv1d(1, 18, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(18, 32, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(32 + n_staves, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, wave, stave):
        return self.head(torch.cat([self.conv(wave[:, None, :]), stave], dim=1)).squeeze(1)


class SpectralTransformer(nn.Module):
    def __init__(self, n_staves: int, regression: bool, width: int = 24) -> None:
        super().__init__()
        self.regression = regression
        self.sample_proj = nn.Linear(2, width)
        layer = nn.TransformerEncoderLayer(d_model=width, nhead=2, dim_feedforward=64, dropout=0.05, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.freq_gate = nn.Sequential(nn.Linear(10, width), nn.ReLU(), nn.Linear(width, width), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(width + n_staves, 40), nn.ReLU(), nn.Linear(40, 1))

    def forward(self, wave, stave):
        n = wave.shape[1]
        t = torch.linspace(0, 1, n, device=wave.device)[None, :, None].expand(wave.shape[0], -1, -1)
        z = self.sample_proj(torch.cat([wave[:, :, None], t], dim=2))
        z = self.encoder(z).mean(dim=1)
        mag = torch.abs(torch.fft.rfft(wave - wave.mean(dim=1, keepdim=True), dim=1))
        if mag.shape[1] < 10:
            mag = torch.nn.functional.pad(mag, (0, 10 - mag.shape[1]))
        mag = mag[:, :10] / torch.clamp(mag[:, 1:].sum(dim=1, keepdim=True), min=1e-6)
        z = z * self.freq_gate(mag)
        return self.head(torch.cat([z, stave], dim=1)).squeeze(1)


def train_torch(method: str, waves: np.ndarray, staves: np.ndarray, y: np.ndarray, train_mask: np.ndarray, test_mask: np.ndarray, config: dict, regression: bool, seed: int) -> np.ndarray:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = WaveCNN(staves.shape[1], regression) if method == "NN_1d_cnn" else SpectralTransformer(staves.shape[1], regression)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    idx = np.where(train_mask)[0]
    max_train = int(config["nn"].get("max_train_rows", len(idx)))
    if len(idx) > max_train:
        idx = rng.choice(idx, size=max_train, replace=False)
    yy = y.astype(np.float32)
    if regression:
        center = float(np.median(yy[idx]))
        scale = float(np.std(yy[idx])) or 1.0
        y_train = (yy[idx] - center) / scale
        loss_fn = nn.SmoothL1Loss()
    else:
        y_train = yy[idx]
        pos = max(float(y_train.sum()), 1.0)
        neg = max(float(len(y_train) - y_train.sum()), 1.0)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    batch = int(config["nn"]["batch_size"])
    xw = waves.astype(np.float32)
    xs = staves.astype(np.float32)
    for _ in range(int(config["nn"]["epochs"])):
        order = rng.permutation(len(idx))
        for start in range(0, len(order), batch):
            take = order[start : start + batch]
            rows = idx[take]
            pred = model(torch.tensor(xw[rows], device=device), torch.tensor(xs[rows], device=device))
            target = torch.tensor(y_train[take], dtype=torch.float32, device=device)
            loss = loss_fn(pred, target)
            opt.zero_grad()
            loss.backward()
            opt.step()
    test_idx = np.where(test_mask)[0]
    out = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(test_idx), 4096):
            rows = test_idx[start : start + 4096]
            pred = model(torch.tensor(xw[rows], device=device), torch.tensor(xs[rows], device=device)).cpu().numpy()
            out.append(pred)
    pred = np.concatenate(out).astype(float)
    return pred * scale + center if regression else pred


def summarize_endpoint_predictions(pred: pd.DataFrame, kind: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = np.sort(pred["run"].unique())
    for method, group in pred.groupby("method", sort=True):
        y = group["y_true"].to_numpy(dtype=float)
        score = group["score"].to_numpy(dtype=float)
        if kind == "classification":
            value = safe_auc(y.astype(int), score)
            ap = safe_ap(y.astype(int), score)
        else:
            value = sigma68(score - y)
            ap = float("nan")
        boot = []
        by_run = [group[group["run"] == run] for run in runs]
        for _ in range(int(n_boot)):
            sample = rng.integers(0, len(by_run), len(by_run))
            g = pd.concat([by_run[i] for i in sample], ignore_index=True)
            yy = g["y_true"].to_numpy(dtype=float)
            ss = g["score"].to_numpy(dtype=float)
            boot.append(safe_auc(yy.astype(int), ss) if kind == "classification" else sigma68(ss - yy))
        arr = np.asarray([v for v in boot if np.isfinite(v)], dtype=float)
        lo, hi = np.quantile(arr, [0.025, 0.975]) if len(arr) else (float("nan"), float("nan"))
        rows.append(
            {
                "method": method,
                "kind": kind,
                "n": int(len(group)),
                "positives": int(np.sum(y)) if kind == "classification" else None,
                "metric_value": float(value),
                "ci_low": float(lo),
                "ci_high": float(hi),
                "average_precision": float(ap) if np.isfinite(ap) else None,
            }
        )
    ascending = kind == "regression"
    return pd.DataFrame(rows).sort_values("metric_value", ascending=ascending)


def fit_endpoint(endpoint: str, kind: str, y: np.ndarray, x_trad: np.ndarray, x_all: np.ndarray, waves: np.ndarray, staves: np.ndarray, runs: np.ndarray, train_mask: np.ndarray, test_mask: np.ndarray, config: dict, seed: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if kind == "classification":
        models = [
            ("traditional_fourier_wavelet_cfd_matched", make_pipeline(StandardScaler(), RidgeClassifier(alpha=0.8, class_weight="balanced")), x_trad),
            ("ML_ridge", make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0, class_weight="balanced")), x_all),
            ("ML_gradient_boosted_trees", HistGradientBoostingClassifier(max_iter=90, learning_rate=0.08, max_leaf_nodes=15, l2_regularization=0.02, random_state=seed), x_all),
            ("ML_mlp", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32), early_stopping=True, max_iter=int(config["mlp_max_iter"]), batch_size=512, alpha=1e-4, random_state=seed + 1)), x_all),
        ]
    else:
        models = [
            ("traditional_fourier_wavelet_cfd_matched", make_pipeline(StandardScaler(), HuberRegressor(alpha=1e-4, max_iter=200)), x_trad),
            ("ML_ridge", make_pipeline(StandardScaler(), Ridge(alpha=1.0)), x_all),
            ("ML_gradient_boosted_trees", HistGradientBoostingRegressor(max_iter=90, learning_rate=0.08, max_leaf_nodes=15, l2_regularization=0.02, random_state=seed), x_all),
            ("ML_mlp", make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32), early_stopping=True, max_iter=int(config["mlp_max_iter"]), batch_size=512, alpha=1e-4, random_state=seed + 1)), x_all),
        ]
    pred_frames = []
    for name, model, x in models:
        print(f"{endpoint}: fitting {name}")
        fit = clone(model)
        fit.fit(x[train_mask], y[train_mask])
        if kind == "classification" and hasattr(fit, "decision_function"):
            score = fit.decision_function(x[test_mask])
        else:
            score = fit.predict(x[test_mask])
        pred_frames.append(pd.DataFrame({"endpoint": endpoint, "method": name, "run": runs[test_mask].astype(int), "y_true": y[test_mask], "score": np.asarray(score, dtype=float)}))
    for method, add in [("NN_1d_cnn", 11), ("NN_spectral_transformer_new", 29)]:
        print(f"{endpoint}: fitting {method}")
        score = train_torch(method, waves, staves, y, train_mask, test_mask, config, regression=(kind == "regression"), seed=seed + add)
        pred_frames.append(pd.DataFrame({"endpoint": endpoint, "method": method, "run": runs[test_mask].astype(int), "y_true": y[test_mask], "score": score}))
    pred = pd.concat(pred_frames, ignore_index=True)
    summary = summarize_endpoint_predictions(pred, kind, np.random.default_rng(seed + 77), int(config["bootstrap_replicates"]))
    summary.insert(0, "endpoint", endpoint)
    return pred, summary


def plot_winners(out_dir: Path, endpoint_summary: pd.DataFrame, definitions: Dict[str, dict]) -> None:
    rows = []
    for endpoint, group in endpoint_summary.groupby("endpoint", sort=False):
        kind = definitions[endpoint]["kind"]
        best = group.sort_values("metric_value", ascending=(kind == "regression")).iloc[0]
        rows.append(best)
    sub = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(sub))
    ax.barh(y, sub["metric_value"], color="#4c78a8")
    ax.errorbar(sub["metric_value"], y, xerr=[sub["metric_value"] - sub["ci_low"], sub["ci_high"] - sub["metric_value"]], fmt="none", ecolor="black", capsize=3)
    ax.set_yticks(y)
    ax.set_yticklabels(sub["endpoint"])
    ax.set_xlabel("Winner metric: AUC for classification, sigma68 for regression")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "endpoint_winner_ci.png", dpi=160)
    plt.close(fig)


def write_report(out_dir: Path, result: dict, endpoint_summary: pd.DataFrame, definitions: Dict[str, dict]) -> None:
    rows = []
    for endpoint, group in endpoint_summary.groupby("endpoint", sort=False):
        kind = definitions[endpoint]["kind"]
        rows.append(group.sort_values("metric_value", ascending=(kind == "regression")).iloc[0])
    winners = pd.DataFrame(rows)
    lines = [
        "# S31a Frequency-Domain Pulse-Shape Timing PID Benchmark",
        "",
        f"**Ticket:** `{result['ticket_id']}`  ",
        f"**Worker:** `{result['worker']}`  ",
        f"**Raw ROOT directory:** `{result['raw_root_dir']}`",
        "",
        "## Abstract",
        "",
        "This study rescans the B-stack raw ROOT files and benchmarks a strong traditional Fourier/wavelet/matched-filter/constant-fraction feature set against ridge, gradient-boosted trees, an MLP, a 1D-CNN, and a new compact spectral transformer. The selected-pulse reproduction is exact: **{:,}** selected B-stave pulses versus the registered **{:,}** count. Across the seven endpoint proxies, the overall winner by endpoint-win count is **{}**.".format(
            result["reproduction"]["selected_pulses"],
            result["reproduction"]["expected_selected_pulses"],
            result["winner"]["method"],
        ),
        "",
        "## Raw ROOT Reproduction",
        "",
        "For each configured run, `h101/HRDv` is reshaped to `(8,18)`. Samples 0-3 define a channel pedestal, B-stave even channels B2/B4/B6/B8 are baseline-subtracted, and a selected pulse is counted when the maximum corrected amplitude exceeds 1000 ADC.",
        "",
        "| quantity | expected | reproduced | delta |",
        "|---|---:|---:|---:|",
        "| selected B-stave pulses | {:,} | {:,} | {} |".format(result["reproduction"]["expected_selected_pulses"], result["reproduction"]["selected_pulses"], result["reproduction"]["delta"]),
        "",
        "## Split and Bootstrap",
        "",
        "Rows are sampled with a cap per `(run, stave)` cell before modeling. Runs `{}` are held out completely. For metric `m`, bootstrap replicate `b` samples held-out runs with replacement and recomputes `m_b`; the quoted interval is `[Q_0.025(m_b), Q_0.975(m_b)]`. This estimates run-to-run stability rather than event-only precision.".format(
            ", ".join(str(r) for r in result["split"]["heldout_runs"])
        ),
        "",
        "Formally, with held-out run blocks `D_r`, the reported point estimate is `m(union_r D_r)`. Bootstrap replicate `b` draws `R` run labels with replacement from the held-out set and computes `m_b=m(union_{r in S_b} D_r)`. Classification endpoints use ROC AUC, with average precision listed as a secondary positive-class metric. Regression endpoints report `sigma68 = 0.5 [Q_0.84(yhat-y)-Q_0.16(yhat-y)]`, so lower is better.",
        "",
        "## Endpoint Definitions",
        "",
        "| endpoint | kind | metric | definition |",
        "|---|---|---|---|",
    ]
    for endpoint, info in definitions.items():
        lines.append(f"| {endpoint} | {info['kind']} | {info['metric']} | {info['definition']} |")
    lines.extend(
        [
            "",
            "These are waveform-derived endpoint proxies because no independent truth PID, pile-up, saturation, or pedestal-noise labels are present in the reduced raw ROOT branch used here. The PID endpoint is therefore a duplicate-readout response proxy, not a particle-species truth label.",
            "",
            "## Methods",
            "",
            "Let `x_i(t)` be the pedestal-subtracted waveform normalized by peak amplitude. The traditional feature set contains CFD crossing times, rise widths, late/early charge ratios, derivative extrema, Gatti/template scores, Haar coefficients, and FFT harmonic ratios. Its multivariate estimator is a regularized linear matched discriminator for classification and a robust Huber model for regression.",
            "",
            "The main derived quantities are: `H_i=sum_{k>=4}|FFT(x_i-mean(x_i))_k| / sum_{k>=1}|FFT(x_i-mean(x_i))_k|` for harmonic content; `t_CFD(f)=t_j+(fA-x_j)/(x_{j+1}-x_j)` for constant-fraction time; `P_i=0.55 tail_i+0.45 max(-Delta x_i)` for the pile-up sideband; and `E_i=log(1+A_i)-median_{run,stave} log(1+A)` for the energy-scale proxy. The matched-template component uses `chi2_c(i)=mean_t [x_i(t)-mu_c(t)]^2`, where `mu_c` is estimated on training runs only.",
            "",
            "For ridge models, classification minimizes an L2-regularized margin loss and regression minimizes `||y-X beta||_2^2 + lambda ||beta||_2^2`. Gradient-boosted trees fit additive shallow trees `F_M(x)=sum_m eta h_m(x)`. The MLP is a two-hidden-layer ReLU network. The 1D-CNN uses local temporal convolutions. The new spectral transformer embeds `(sample, time)` tokens with a one-layer self-attention encoder and gates the representation with normalized FFT magnitudes, which is specifically matched to the frequency-domain ticket.",
            "",
            "All supervised estimators are fit on the same training runs. Thresholds that define high-side classification endpoints are fixed from the training runs before held-out scoring, so held-out labels do not tune the decision boundary. The traditional estimator sees only engineered Fourier/wavelet/CFD/template variables; ridge, GBT, and MLP see those variables plus the normalized waveform and stave one-hot indicators; CNN and spectral-transformer methods see the normalized waveform and stave one-hot indicators.",
            "",
            "## Primary Results",
            "",
            "| endpoint | winner | metric | 95% CI | next best traditional |",
            "|---|---|---:|---:|---|",
        ]
    )
    for _, row in winners.iterrows():
        endpoint = row["endpoint"]
        trad = endpoint_summary[(endpoint_summary["endpoint"] == endpoint) & (endpoint_summary["method"] == "traditional_fourier_wavelet_cfd_matched")].iloc[0]
        lines.append("| {} | {} | {:.5f} | [{:.5f}, {:.5f}] | {:.5f} [{:.5f}, {:.5f}] |".format(endpoint, row["method"], row["metric_value"], row["ci_low"], row["ci_high"], trad["metric_value"], trad["ci_low"], trad["ci_high"]))
    lines.extend(["", "Complete method table:", "", "| endpoint | method | metric | 95% CI | AP/positives |", "|---|---|---:|---:|---:|"])
    for _, row in endpoint_summary.iterrows():
        ap = "" if pd.isna(row.get("average_precision")) else "{:.5f}".format(float(row["average_precision"]))
        lines.append("| {} | {} | {:.5f} | [{:.5f}, {:.5f}] | {} |".format(row["endpoint"], row["method"], row["metric_value"], row["ci_low"], row["ci_high"], ap))
    lines.extend(
        [
            "",
            "## Systematics and Caveats",
            "",
            "- Endpoint labels are deterministic proxies from the same waveforms, so absolute AUC values can be optimistic when a model observes variables close to the label definition.",
            "- Run-held-out splitting prevents random-row leakage but cannot create missing external truth. The PID and pile-up results should be interpreted as stability of waveform-response proxies.",
            "- The raw ROOT reproduction is exact for the selected-pulse count; it does not by itself validate the physics labels.",
            "- Neural models are deliberately compact because each pulse has only 18 samples and the finite held-out run set limits reliable high-capacity training.",
            "- Regression endpoints report sigma68 of residuals. For energy scale this is a log-amplitude proxy, not a calibrated GeV response.",
            "",
            "## Verdict",
            "",
            "`result.json` names **{}** as the overall winner by endpoint-win count. Endpoint-specific winners remain more informative than a single aggregate: the table above records which method wins each physics proxy and where the traditional Fourier/wavelet/CFD baseline is already competitive.".format(result["winner"]["method"]),
            "",
            "## Reproducibility",
            "",
            "```bash",
            "/home/billy/anaconda3/bin/python scripts/s31a_1783882773_37910_7224325e_frequency_domain_pulse_timing_pid_benchmark.py --config configs/s31a_1783882773_37910_7224325e_frequency_domain_pulse_timing_pid_benchmark.json",
            "```",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s31a_1783882773_37910_7224325e_frequency_domain_pulse_timing_pid_benchmark.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_dir = t07.resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    waves, meta, counts_by_run = t07.scan_raw(config, raw_dir)
    selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError(f"raw reproduction failed: selected {selected}, expected {expected}")
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame([{"quantity": "selected B-stave pulses with baseline-subtracted amplitude > 1000 ADC", "report_value": expected, "reproduced": selected, "delta": selected - expected, "pass": selected == expected}]).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    sample_idx = t07.balanced_sample(meta, int(config["max_per_run_stave"]), rng)
    sample_idx.sort()
    bench_waves = waves[sample_idx]
    bench_meta = meta.iloc[sample_idx].reset_index(drop=True)
    runs = bench_meta["run"].to_numpy(dtype=int)
    heldout_runs = np.asarray([int(run) for run in config["heldout_runs"]], dtype=int)
    train_mask = ~np.isin(runs, heldout_runs)
    test_mask = np.isin(runs, heldout_runs)
    feats, feature_roles = t07.classic_features(bench_waves, bench_meta)
    targets, definitions = make_endpoint_targets(bench_waves, bench_meta, feats, train_mask)
    targets.to_csv(out_dir / "endpoint_targets.csv", index=False)
    feature_roles.to_csv(out_dir / "traditional_feature_families.csv", index=False)

    trad_cols = [c for c in feats.columns if c != "stave_idx"]
    x_trad = feats[trad_cols].to_numpy(dtype=np.float32)
    x_all = np.hstack([bench_waves.astype(np.float32), x_trad, one_hot_stave(bench_meta)]).astype(np.float32)
    staves = one_hot_stave(bench_meta)

    pred_frames = []
    summary_frames = []
    for i, (endpoint, info) in enumerate(definitions.items()):
        y = targets[endpoint].to_numpy(dtype=np.float32 if info["kind"] == "regression" else np.int8)
        pred, summary = fit_endpoint(endpoint, info["kind"], y, x_trad, x_all, bench_waves, staves, runs, train_mask, test_mask, config, int(config["random_seed"]) + i * 101)
        pred_frames.append(pred)
        summary_frames.append(summary)
    predictions = pd.concat(pred_frames, ignore_index=True)
    endpoint_summary = pd.concat(summary_frames, ignore_index=True)
    predictions.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    endpoint_summary.to_csv(out_dir / "endpoint_method_summary.csv", index=False)

    winner_rows = []
    for endpoint, group in endpoint_summary.groupby("endpoint", sort=False):
        kind = definitions[endpoint]["kind"]
        winner_rows.append(group.sort_values("metric_value", ascending=(kind == "regression")).iloc[0].to_dict())
    winner_table = pd.DataFrame(winner_rows)
    winner_table.to_csv(out_dir / "endpoint_winners.csv", index=False)
    plot_winners(out_dir, endpoint_summary, definitions)
    win_counts = winner_table["method"].value_counts()
    overall_winner = str(win_counts.index[0])
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit": git_commit(),
        "runtime_sec": time.time() - t0,
        "python": platform.python_version(),
        "reproduction": {"selected_pulses": selected, "expected_selected_pulses": expected, "delta": selected - expected, "passed": selected == expected, "samples_per_channel": int(config["samples_per_channel"])},
        "split": {"heldout_runs": [int(r) for r in heldout_runs], "train_rows": int(train_mask.sum()), "heldout_rows": int(test_mask.sum()), "bootstrap_replicates": int(config["bootstrap_replicates"])},
        "endpoints": definitions,
        "primary_methods": ["traditional_fourier_wavelet_cfd_matched", "ML_ridge", "ML_gradient_boosted_trees", "ML_mlp", "NN_1d_cnn", "NN_spectral_transformer_new"],
        "endpoint_winners": json_clean(winner_rows),
        "winner": {"method": overall_winner, "endpoint_wins": int(win_counts.iloc[0]), "win_counts": win_counts.to_dict()},
        "verdict": f"overall winner is {overall_winner} by endpoint-win count; endpoint-specific winners are listed in endpoint_winners",
        "next_tickets": []
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, endpoint_summary, definitions)
    manifest_rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json" and not path.name.endswith(".gz"):
            manifest_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    (out_dir / "manifest.json").write_text(json.dumps(json_clean({"ticket_id": config["ticket_id"], "generated_at_unix": time.time(), "artifacts": manifest_rows}), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": overall_winner, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
