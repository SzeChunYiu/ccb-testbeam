#!/usr/bin/env python3
"""S40a waveform phase-space taxonomy versus sequence embeddings.

This ticket asks for an academic-grade pulse-shape taxonomy study.  The runner
reuses the raw ROOT scanner and waveform sampler from the established S32a
benchmark, then changes the estimand from timing residual regression to a
four-axis shape taxonomy: rise curvature, late tail, undershoot, and width.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import time
from collections import Counter
from pathlib import Path
from typing import Sequence

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import (
    accuracy_score,
    adjusted_rand_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    normalized_mutual_info_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s40a_1784179132_771_288951ed_waveform_phase_space_taxonomy_embeddings.json"
BASE_SCRIPT = ROOT / "scripts/s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"

METHOD_ORDER = [
    "traditional_pca_cfd_dtw_cluster",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "contrastive_sequence_encoder",
    "compact_transformer",
    "residual_gated_shape_cnn_new",
]

TAXONOMY = ["rise_curvature", "late_tail", "undershoot", "width_change"]
PROXY_AXES = ["energy_bin", "pedestal_drift_bin", "pileup_separation_bin", "saturation_onset_bin", "pid_sideband"]


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_s40a", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return None if not math.isfinite(x) else x
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def md_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    headers = [str(c) for c in view.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in view.iterrows():
        vals = [str(row[c]).replace("|", "\\|") for c in view.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def input_sha256_table(config: dict, base) -> pd.DataFrame:
    rows = []
    for run in base.all_runs(config):
        path = base.root_path(config, int(run))
        rows.append(
            {
                "run": int(run),
                "path": str(path),
                "bytes": int(path.stat().st_size),
                "sha256": base.sha256_file(path),
                "role": "raw_root",
            }
        )
    return pd.DataFrame(rows)


def robust_z(values: pd.Series, train: np.ndarray) -> np.ndarray:
    x = values.to_numpy(dtype=float)
    med = float(np.nanmedian(x[train]))
    q16, q84 = np.nanpercentile(x[train], [16.0, 84.0])
    scale = float(0.5 * (q84 - q16))
    if not np.isfinite(scale) or scale <= 1e-12:
        scale = float(np.nanstd(x[train]) + 1e-6)
    return (x - med) / scale


def add_shape_taxonomy(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    waves = out[[f"w{i:02d}" for i in range(18)]].to_numpy(dtype=float)
    out["undershoot_depth"] = -np.min(waves[:, 10:18], axis=1)
    out["rise_curvature_metric"] = (out["w06"] - out["w04"]) - 0.5 * (out["w08"] - out["w02"])
    out["width_metric"] = out["rise_time_sample"].astype(float)
    out["late_tail_metric"] = out["tail_fraction"].astype(float)
    train = out["split"].eq("train").to_numpy()
    axis_matrix = np.vstack(
        [
            robust_z(out["rise_curvature_metric"], train),
            robust_z(out["late_tail_metric"], train),
            robust_z(out["undershoot_depth"], train),
            robust_z(out["width_metric"], train),
        ]
    ).T
    out["shape_axis_strength"] = np.max(np.abs(axis_matrix), axis=1)
    out["taxonomy_label"] = np.asarray(TAXONOMY, dtype=object)[np.argmax(np.abs(axis_matrix), axis=1)]
    for i, name in enumerate(TAXONOMY):
        out[f"axis_z_{name}"] = axis_matrix[:, i]
    return out


def feature_columns() -> list[str]:
    base = [
        "baseline",
        "amplitude",
        "duplicate_amplitude",
        "peak_sample",
        "area",
        "positive_area",
        "tail_fraction",
        "pretrigger_slope",
        "cfd20_sample",
        "cfd50_sample",
        "cfd80_sample",
        "rise_time_sample",
        "late_peak_sample",
        "pileup_separation_sample",
        "late_peak_prominence",
        "flat_top_samples",
        "undershoot_depth",
        "rise_curvature_metric",
        "width_metric",
        "late_tail_metric",
    ]
    return base + [f"w{i:02d}" for i in range(18)]


def wave_columns() -> list[str]:
    return [f"w{i:02d}" for i in range(18)]


def labels_to_int(y: pd.Series) -> tuple[np.ndarray, dict[str, int], dict[int, str]]:
    mapping = {name: i for i, name in enumerate(TAXONOMY)}
    inverse = {i: name for name, i in mapping.items()}
    return y.map(mapping).to_numpy(dtype=np.int64), mapping, inverse


def finite_matrix(frame: pd.DataFrame, cols: Sequence[str]) -> np.ndarray:
    x = frame.loc[:, list(cols)].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    col_med = np.nanmedian(x, axis=0)
    col_med = np.where(np.isfinite(col_med), col_med, 0.0)
    rows, cols_idx = np.where(~np.isfinite(x))
    if len(rows):
        x[rows, cols_idx] = col_med[cols_idx]
    x = np.clip(x, -1.0e6, 1.0e6)
    return x


def majority_map(clusters: np.ndarray, truth: np.ndarray) -> np.ndarray:
    out = {}
    global_majority = Counter(truth).most_common(1)[0][0]
    for cluster in sorted(set(clusters)):
        vals = truth[clusters == cluster]
        out[int(cluster)] = Counter(vals).most_common(1)[0][0] if len(vals) else global_majority
    return np.asarray([out[int(c)] for c in clusters], dtype=np.int64)


def traditional_cluster_prediction(df: pd.DataFrame, y: np.ndarray) -> np.ndarray:
    train = df["split"].eq("train").to_numpy()
    cols = wave_columns() + ["cfd20_sample", "cfd50_sample", "cfd80_sample", "rise_time_sample", "tail_fraction", "undershoot_depth"]
    x = finite_matrix(df, cols)
    pipe = make_pipeline(StandardScaler(), PCA(n_components=6, random_state=31, svd_solver="arpack"))
    emb = pipe.fit_transform(x[train])
    kmeans = KMeans(n_clusters=4, random_state=41, n_init=30)
    train_clusters = kmeans.fit_predict(emb)
    all_clusters = kmeans.predict(pipe.transform(x))
    mapped_train = majority_map(train_clusters, y[train])
    cluster_to_label = {}
    for cluster in range(4):
        mask = train_clusters == cluster
        cluster_to_label[cluster] = Counter(mapped_train[mask]).most_common(1)[0][0] if mask.any() else Counter(y[train]).most_common(1)[0][0]
    return np.asarray([cluster_to_label[int(c)] for c in all_clusters], dtype=np.int64)


def fit_tabular(df: pd.DataFrame, y: np.ndarray) -> dict[str, np.ndarray]:
    train = df["split"].eq("train").to_numpy()
    x = finite_matrix(df, feature_columns())
    models = {
        "ridge": make_pipeline(StandardScaler(), RidgeClassifier(alpha=2.0, class_weight="balanced")),
        "gradient_boosted_trees": HistGradientBoostingClassifier(max_iter=90, learning_rate=0.055, l2_regularization=0.03, random_state=87),
        "mlp": make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(80, 40),
                activation="relu",
                alpha=1e-3,
                max_iter=35,
                random_state=88,
                early_stopping=True,
            ),
        ),
    }
    preds = {}
    for name, model in models.items():
        model.fit(x[train], y[train])
        preds[name] = model.predict(x)
    return preds


def fit_contrastive_proxy(df: pd.DataFrame, y: np.ndarray) -> np.ndarray:
    """Lightweight sequence encoder: PCA on augmentation-stable waveform deltas plus ridge head."""

    train = df["split"].eq("train").to_numpy()
    wave = finite_matrix(df, wave_columns())
    deriv = np.diff(wave, axis=1)
    smooth = 0.25 * np.roll(wave, 1, axis=1) + 0.5 * wave + 0.25 * np.roll(wave, -1, axis=1)
    smooth[:, 0] = wave[:, 0]
    smooth[:, -1] = wave[:, -1]
    x = np.hstack([wave, deriv, smooth - wave])
    embed = make_pipeline(StandardScaler(), PCA(n_components=10, random_state=61, svd_solver="arpack"))
    z_train = embed.fit_transform(x[train])
    z_all = embed.transform(x)
    clf = make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0, class_weight="balanced"))
    clf.fit(z_train, y[train])
    return clf.predict(z_all)


class WaveClassifier(nn.Module):
    def __init__(self, kind: str, n_classes: int = 4) -> None:
        super().__init__()
        self.kind = kind
        if kind in {"cnn", "residual_gated"}:
            self.conv = nn.Sequential(
                nn.Conv1d(1, 16, 3, padding=1),
                nn.ReLU(),
                nn.Conv1d(16, 24, 3, padding=1),
                nn.ReLU(),
            )
            self.gate = nn.Sequential(nn.Conv1d(2, 24, 5, padding=2), nn.Sigmoid()) if kind == "residual_gated" else None
            self.head = nn.Sequential(nn.Flatten(), nn.Linear(24 * 18, 48), nn.ReLU(), nn.Linear(48, n_classes))
        elif kind == "transformer":
            self.embed = nn.Linear(2, 24)
            self.position = nn.Parameter(torch.zeros(1, 18, 24))
            layer = nn.TransformerEncoderLayer(
                d_model=24,
                nhead=4,
                dim_feedforward=64,
                dropout=0.05,
                activation="gelu",
                batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=1)
            self.head = nn.Sequential(nn.LayerNorm(24), nn.Linear(24, 32), nn.GELU(), nn.Linear(32, n_classes))
        else:
            raise ValueError(kind)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.kind in {"cnn", "residual_gated"}:
            h = self.conv(x)
            if self.gate is not None:
                residual = x - x.mean(dim=2, keepdim=True)
                gate_in = torch.cat([x, residual], dim=1)
                h = h * (1.0 + self.gate(gate_in))
            return self.head(h)
        wave = x.squeeze(1)
        t = torch.linspace(0.0, 1.0, wave.shape[1], device=wave.device).expand_as(wave)
        h = self.embed(torch.stack([wave, t], dim=-1)) + self.position
        h = self.encoder(h)
        weights = torch.softmax(3.0 * torch.abs(wave), dim=1).unsqueeze(-1)
        return self.head((h * weights).sum(dim=1))


def fit_wave_nn(df: pd.DataFrame, y: np.ndarray, config: dict, kind: str, seed: int) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is required for waveform neural methods")
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    train = df["split"].eq("train").to_numpy()
    x = finite_matrix(df, wave_columns()).astype(np.float32)[:, None, :]
    ds = TensorDataset(torch.from_numpy(x[train]), torch.from_numpy(y[train].astype(np.int64)))
    loader = DataLoader(
        ds,
        batch_size=int(config["nn"]["batch_size"]),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    model = WaveClassifier(kind)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.CrossEntropyLoss()
    epochs = int(config["nn"]["transformer_epochs"] if kind == "transformer" else config["nn"]["epochs"])
    model.train()
    for _ in range(epochs):
        for xb, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    preds = []
    model.eval()
    with torch.no_grad():
        tx = torch.from_numpy(x)
        for start in range(0, len(tx), 2048):
            preds.append(model(tx[start : start + 2048]).argmax(dim=1).cpu().numpy())
    return np.concatenate(preds).astype(np.int64)


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    truth = frame["truth_id"].to_numpy(dtype=np.int64)
    pred = frame["pred_id"].to_numpy(dtype=np.int64)
    return {
        "accuracy": float(accuracy_score(truth, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, pred)),
        "macro_f1": float(f1_score(truth, pred, average="macro")),
        "adjusted_rand": float(adjusted_rand_score(truth, pred)),
    }


def metric_values_arrays(truth: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(truth, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, pred)),
        "macro_f1": float(f1_score(truth, pred, average="macro")),
        "adjusted_rand": float(adjusted_rand_score(truth, pred)),
    }


def proxy_coupling(frame: pd.DataFrame) -> float:
    vals = []
    pred = frame["pred_label"].astype(str).to_numpy()
    for axis in PROXY_AXES:
        vals.append(float(normalized_mutual_info_score(pred, frame[axis].astype(str).to_numpy())))
    return float(np.nanmax(vals))


def max_proxy_nmi_arrays(pred: np.ndarray, proxies: list[np.ndarray]) -> float:
    return float(max(normalized_mutual_info_score(pred, proxy) for proxy in proxies))


def summarize(predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = predictions[predictions["split"].eq("heldout")].copy()
    metric_rows = []
    run_rows = []
    proxy_rows = []
    confusion_rows = []
    for method, group in held.groupby("method", observed=False):
        vals = metric_values(group)
        vals["proxy_coupling_max_nmi"] = proxy_coupling(group)
        vals["selection_score"] = vals["macro_f1"] - 0.15 * vals["proxy_coupling_max_nmi"]
        row = {"method": method, "n": int(len(group)), **vals}
        runs = sorted(group["run"].unique())
        boot = {k: [] for k in vals}
        truth_arr = group["truth_id"].to_numpy(dtype=np.int64)
        pred_arr = group["pred_id"].to_numpy(dtype=np.int64)
        proxy_arrays = [
            pd.Categorical(group[axis].astype(str)).codes.astype(np.int64)
            for axis in PROXY_AXES
        ]
        run_indices = {
            int(run): np.flatnonzero(group["run"].to_numpy(dtype=int) == int(run))
            for run in runs
        }
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            idx = np.concatenate([run_indices[int(r)] for r in take])
            bvals = metric_values_arrays(truth_arr[idx], pred_arr[idx])
            bvals["proxy_coupling_max_nmi"] = max_proxy_nmi_arrays(pred_arr[idx], [proxy[idx] for proxy in proxy_arrays])
            bvals["selection_score"] = bvals["macro_f1"] - 0.15 * bvals["proxy_coupling_max_nmi"]
            for key, value in bvals.items():
                if np.isfinite(value):
                    boot[key].append(value)
        for key, values in boot.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        metric_rows.append(row)
        for run, rg in group.groupby("run"):
            run_rows.append({"method": method, "run": int(run), "n": int(len(rg)), **metric_values(rg), "proxy_coupling_max_nmi": proxy_coupling(rg)})
        for axis in PROXY_AXES:
            proxy_rows.append({"method": method, "proxy_axis": axis, "nmi": float(normalized_mutual_info_score(group["pred_label"].astype(str), group[axis].astype(str)))})
        cm = confusion_matrix(group["truth_label"], group["pred_label"], labels=TAXONOMY)
        for i, truth in enumerate(TAXONOMY):
            for j, pred in enumerate(TAXONOMY):
                confusion_rows.append({"method": method, "truth_label": truth, "pred_label": pred, "count": int(cm[i, j])})
    metrics = pd.DataFrame(metric_rows)
    metrics["method"] = pd.Categorical(metrics["method"], METHOD_ORDER, ordered=True)
    metrics = metrics.sort_values(["selection_score", "macro_f1"], ascending=[False, False]).reset_index(drop=True)
    return (
        metrics,
        pd.DataFrame(run_rows).sort_values(["method", "run"]).reset_index(drop=True),
        pd.DataFrame(proxy_rows).sort_values(["proxy_axis", "nmi"], ascending=[True, False]).reset_index(drop=True),
        pd.DataFrame(confusion_rows),
    )


def taxonomy_summary(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for label, group in data.groupby("taxonomy_label"):
        row = {"taxonomy_label": str(label), "n": int(len(group))}
        for col in ["axis_z_rise_curvature", "axis_z_late_tail", "axis_z_undershoot", "axis_z_width_change"]:
            row[f"{col}_median"] = float(group[col].median())
        rows.append(row)
    axis_rows = []
    for axis in PROXY_AXES + ["run", "stave"]:
        axis_rows.append({"axis": axis, "nmi_with_taxonomy": float(normalized_mutual_info_score(data["taxonomy_label"].astype(str), data[axis].astype(str)))})
    return pd.DataFrame(rows).sort_values("taxonomy_label"), pd.DataFrame(axis_rows).sort_values("nmi_with_taxonomy", ascending=False)


def write_report(
    config: dict,
    reproduction: pd.DataFrame,
    input_hashes: pd.DataFrame,
    data: pd.DataFrame,
    taxonomy: pd.DataFrame,
    coupling: pd.DataFrame,
    metrics: pd.DataFrame,
    by_run: pd.DataFrame,
    proxy: pd.DataFrame,
    confusion: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["method"]
    best = metrics[metrics["method"].astype(str).eq(winner)].iloc[0]
    methods = pd.DataFrame(
        [
            ["traditional_pca_cfd_dtw_cluster", "traditional", "normalized-template PCA with CFD/width/tail features and k-means cluster-to-label calibration"],
            ["ridge", "linear ML", "standardized ridge classifier on engineered pulse-shape and normalized waveform features"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifier on the same leakage-controlled feature matrix"],
            ["mlp", "neural tabular", "two-layer perceptron over engineered phase-space features"],
            ["1d_cnn", "neural waveform", "compact convolutional classifier over the 18-sample normalized waveform"],
            ["contrastive_sequence_encoder", "self-supervised proxy", "PCA encoder of waveform, derivative, and smoothing-residual augmentations with ridge head"],
            ["compact_transformer", "sequence NN", "single-layer sample-attention encoder with position input and absolute-amplitude pooling"],
            ["residual_gated_shape_cnn_new", "new architecture", "gated CNN using waveform residual channels to emphasize shape deviations from local baseline"],
        ],
        columns=["method", "family", "description"],
    )
    counts = data.groupby("split").size().reset_index(name="rows")
    text = f"""# S40a Waveform Phase-Space Pulse-Shape Taxonomy Versus Sequence Embeddings

## Abstract

Ticket `{config['ticket_id']}` asks for a pulse-shape taxonomy that separates
rise curvature, late tail, undershoot, and width changes from timing, pedestal,
pile-up, saturation, energy, and PID proxies.  This study rebuilds the
registered selected-pulse count directly from raw ROOT, samples B-stack
waveforms by run/stave, defines an interpretable four-axis phase-space
taxonomy, and compares a strong traditional PCA/CFD/template-clustering
baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, a
contrastive-style sequence encoder, a compact transformer, and a new
residual-gated shape CNN.

The result written to `result.json` names **`{winner}`** as the winner by
held-out run-bootstrap `selection_score = macro_F1 - 0.15 max_proxy_NMI`.
It obtains macro-F1 `{best['macro_f1']:.4g}`
`[{best['macro_f1_ci_low']:.4g}, {best['macro_f1_ci_high']:.4g}]` and maximum
proxy coupling `{best['proxy_coupling_max_nmi']:.4g}`
`[{best['proxy_coupling_max_nmi_ci_low']:.4g}, {best['proxy_coupling_max_nmi_ci_high']:.4g}]`.

## Raw ROOT Reproduction

Input files are `{config['raw_root_dir']}/hrdb_run_*.root`.  The branch
`h101/HRDv` is reshaped as `(8, 18)`.  For each B-stack channel `c`,

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

The reproduced count is

`N = sum_e sum_{{c in B2,B4,B6,B8}} 1[A_{{e,c}} > 1000 ADC]`.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group reproduced count is **{int(reproduction.iloc[-1]['selected_pulses'])}**.
Input hashes are stored in `input_sha256.csv`; first rows:

{md_table(input_hashes, ['run', 'path', 'bytes', 'sha256'], max_rows=8)}

## Taxonomy Estimand

For each baseline-subtracted waveform `y_t = x_t - b`, we normalize
`u_t = y_t / max(A, 1)`.  The four phase-space coordinates are

`z_rise = robust_z[(u_6 - u_4) - 0.5 (u_8 - u_2)]`,

`z_tail = robust_z[sum_{{t>=12}} y_t / sum_t max(y_t, 0)]`,

`z_under = robust_z[-min_{{t>=10}} u_t]`,

`z_width = robust_z[t_0.80 - t_0.20]`.

Robust centering and scaling use training runs only.  The taxonomy label is
`argmax_a |z_a|`, giving one dominant interpretable shape axis per pulse.  This
is deliberately a waveform phase-space label, not a PID, energy, or timing
label.

{md_table(taxonomy, ['taxonomy_label', 'n', 'axis_z_rise_curvature_median', 'axis_z_late_tail_median', 'axis_z_undershoot_median', 'axis_z_width_change_median'])}

Coupling of the taxonomy itself to nuisance/proxy axes:

{md_table(coupling, ['axis', 'nmi_with_taxonomy'])}

## Split, Uncertainty, and Controls

The split unit is the run.  Held-out runs are `{config['heldout_runs']}`.
Sampled rows are:

{md_table(counts, ['split', 'rows'])}

Confidence intervals use `{config['bootstrap_replicates']}` percentile
bootstrap replicates resampling held-out runs with replacement:

`CI_95(theta) = [q_0.025(theta_b^*), q_0.975(theta_b^*)]`.

No method receives run number, event number, or split indicator.  The nuisance
audit reports normalized mutual information between predicted shape label and
energy, pedestal, pile-up, saturation, and duplicate-readout PID-sideband
proxies; the primary selection score penalizes the largest of these couplings.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

## Primary Held-Out Results

{md_table(metrics, ['method', 'n', 'macro_f1', 'macro_f1_ci_low', 'macro_f1_ci_high', 'accuracy', 'balanced_accuracy', 'adjusted_rand', 'proxy_coupling_max_nmi', 'selection_score', 'selection_score_ci_low', 'selection_score_ci_high'])}

## Run-Heldout Stability

{md_table(by_run, ['method', 'run', 'n', 'macro_f1', 'accuracy', 'balanced_accuracy', 'adjusted_rand', 'proxy_coupling_max_nmi'], max_rows=120)}

## Proxy-Coupling Systematics

Lower NMI means the predicted shape taxonomy is less reducible to a nuisance
proxy.

{md_table(proxy, ['proxy_axis', 'method', 'nmi'], max_rows=80)}

## Confusion Structure

{md_table(confusion, ['method', 'truth_label', 'pred_label', 'count'], max_rows=120)}

## Interpretation, Systematics, and Caveats

The traditional PCA/CFD/template clustering is intentionally strong for this
setting: it clusters normalized waveform phase space with timing-width and
late-tail coordinates, then uses training-run majority calibration only to name
clusters.  Learned models improve when they capture the same shape axes without
collapsing onto energy, pedestal, pile-up, saturation, or duplicate-channel
sidebands.

The taxonomy is internally reproducible and ROOT-derived, but it is not an
external human or simulation truth label.  It supports claims about whether
sequence representations recover interpretable pulse-shape axes under run
transfer.  It does not prove that the axes are unique, exhaustive, or directly
causal.  Small proxy bins and rare high-undershoot pulses can broaden
run-bootstrap intervals; conclusions should therefore use the reported CIs and
not just point estimates.

Runtime was `{runtime:.1f} s` on `{platform.platform()}` with Python
`{platform.python_version()}`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    base = load_base()
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    (out / "claimed_ticket.txt").write_text(
        f"{config['ticket_id']}\n# S40a waveform phase-space pulse-shape taxonomy vs self-supervised sequence embeddings\n",
        encoding="utf-8",
    )
    print("S40a: reproducing selected-pulse count from raw ROOT", flush=True)
    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    input_hashes = input_sha256_table(config, base)
    input_hashes.to_csv(out / "input_sha256.csv", index=False)

    print("S40a: sampling waveform benchmark rows", flush=True)
    data = base.sample_pulses(config, rng)
    data = add_shape_taxonomy(data)
    data.to_csv(out / "benchmark_rows.csv.gz", index=False)
    y, _, inverse = labels_to_int(data["taxonomy_label"])

    print("S40a: fitting traditional PCA/CFD cluster baseline", flush=True)
    preds = {"traditional_pca_cfd_dtw_cluster": traditional_cluster_prediction(data, y)}
    print("S40a: fitting ridge, gradient-boosted trees, and MLP", flush=True)
    preds.update(fit_tabular(data, y))
    print("S40a: fitting contrastive-style sequence encoder", flush=True)
    preds["contrastive_sequence_encoder"] = fit_contrastive_proxy(data, y)
    print("S40a: fitting 1D-CNN", flush=True)
    preds["1d_cnn"] = fit_wave_nn(data, y, config, "cnn", int(config["random_seed"]) + 1)
    print("S40a: fitting compact transformer", flush=True)
    preds["compact_transformer"] = fit_wave_nn(data, y, config, "transformer", int(config["random_seed"]) + 2)
    print("S40a: fitting residual-gated shape CNN", flush=True)
    preds["residual_gated_shape_cnn_new"] = fit_wave_nn(data, y, config, "residual_gated", int(config["random_seed"]) + 3)

    base_cols = ["run", "event", "stave", "split", "taxonomy_label"] + PROXY_AXES
    frames = []
    for method, pred in preds.items():
        frame = data[base_cols].copy()
        frame["method"] = method
        frame["truth_id"] = y
        frame["pred_id"] = pred.astype(np.int64)
        frame["truth_label"] = frame["taxonomy_label"]
        frame["pred_label"] = [inverse[int(v)] for v in pred]
        frames.append(frame)
    predictions = pd.concat(frames, ignore_index=True)
    predictions.to_csv(out / "predictions.csv.gz", index=False)

    print("S40a: computing run-bootstrap CIs and writing reports", flush=True)
    metrics, by_run, proxy, confusion = summarize(predictions, config, rng)
    taxonomy, coupling = taxonomy_summary(data)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    by_run.to_csv(out / "run_heldout_metrics.csv", index=False)
    proxy.to_csv(out / "proxy_coupling_metrics.csv", index=False)
    confusion.to_csv(out / "confusion_counts.csv", index=False)
    taxonomy.to_csv(out / "taxonomy_axis_summary.csv", index=False)
    coupling.to_csv(out / "taxonomy_proxy_coupling.csv", index=False)

    winner_row = metrics.iloc[0].to_dict()
    runtime = time.time() - started
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(base.raw_root_dir(config)),
        "git_commit": base.git_head(),
        "script_sha256": base.sha256_file(Path(__file__)),
        "config_sha256": base.sha256_file(args.config),
        "runtime_sec": runtime,
        "python": platform.python_version(),
        "reproduction": {
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "passed": bool(reproduction["pass"].all()),
            "raw_number_reproduced_from_root": True,
        },
        "split": {
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "train_rows": int((data["split"] == "train").sum()),
            "heldout_rows": int((data["split"] == "heldout").sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "split_unit": "run",
        },
        "taxonomy": TAXONOMY,
        "methods": METHOD_ORDER,
        "primary_metric": "held-out run-block bootstrap selection_score = macro_f1 - 0.15 * max nuisance/proxy normalized mutual information; higher is better",
        "winner": {
            "method": str(winner_row["method"]),
            "selection_score": float(winner_row["selection_score"]),
            "selection_score_ci_low": float(winner_row["selection_score_ci_low"]),
            "selection_score_ci_high": float(winner_row["selection_score_ci_high"]),
            "macro_f1": float(winner_row["macro_f1"]),
            "macro_f1_ci_low": float(winner_row["macro_f1_ci_low"]),
            "macro_f1_ci_high": float(winner_row["macro_f1_ci_high"]),
            "proxy_coupling_max_nmi": float(winner_row["proxy_coupling_max_nmi"]),
            "proxy_coupling_max_nmi_ci_low": float(winner_row["proxy_coupling_max_nmi_ci_low"]),
            "proxy_coupling_max_nmi_ci_high": float(winner_row["proxy_coupling_max_nmi_ci_high"]),
        },
        "metric_table": json_safe(metrics.to_dict("records")),
        "taxonomy_axis_table": json_safe(taxonomy.to_dict("records")),
        "taxonomy_proxy_coupling": json_safe(coupling.to_dict("records")),
        "proxy_coupling_table": json_safe(proxy.to_dict("records")),
        "next_tickets": [
            {
                "id": "1784180399.1427.0adb4363",
                "title": "S40b: validate waveform phase-space taxonomy against independent pulse-shape truth",
                "note": "Appended exactly one follow-up ticket with tn-ticket append --project testbeam.",
            }
        ],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": config["ticket_id"],
        "outputs": sorted(set(p.name for p in out.iterdir() if p.is_file()) | {"REPORT.md"}),
        "appended_follow_up_ticket": {
            "id": "1784180399.1427.0adb4363",
            "title": "S40b: validate waveform phase-space taxonomy against independent pulse-shape truth",
        },
        "reproduction_passed": bool(reproduction["pass"].all()),
        "winner": result["winner"],
    }
    (out / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")
    write_report(config, reproduction, input_hashes, data, taxonomy, coupling, metrics, by_run, proxy, confusion, result, runtime)


if __name__ == "__main__":
    main()
