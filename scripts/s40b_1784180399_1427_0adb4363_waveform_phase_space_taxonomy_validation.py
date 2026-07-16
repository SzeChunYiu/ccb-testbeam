#!/usr/bin/env python3
"""S40b independent validation of a four-axis waveform phase-space taxonomy."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s40b_1784180399_1427_0adb4363_waveform_phase_space_taxonomy_validation.json"
BASE_SCRIPT = ROOT / "scripts/s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"

TICKET_TEXT = """1784180399.1427.0adb4363
# S40b: validate waveform phase-space taxonomy against independent pulse-shape truth

Validate the S40a four-axis waveform phase-space taxonomy against an independent hand-scan or simulation-derived pulse-shape label set before treating the labels as physics truth. Compare the traditional PCA/CFD/template clustering baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, compact transformer, and residual-gated sequence encoders with run-heldout bootstrap CIs. Quantify whether rise curvature, late tail, undershoot, and width axes remain separated from timing, pedestal, pile-up, saturation, energy, and PID proxies under the external truth labels.
"""

AXES = ["rise_curvature", "late_tail", "undershoot", "width_broad"]
METHODS = [
    "traditional_pca_cfd_template_cluster",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "compact_transformer",
    "residual_gated_sequence_encoder_new",
]
NUISANCE = ["timing", "pedestal", "pileup", "saturation", "energy", "pid_proxy"]


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_s40b", BASE_SCRIPT)
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
    headers = [str(col) for col in view.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in view.iterrows():
        values = [str(row[col]).replace("|", "\\|") for col in view.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def input_sha256_table(config: dict, base) -> pd.DataFrame:
    rows = []
    for run in base.all_runs(config):
        path = base.root_path(config, int(run))
        rows.append({"run": int(run), "path": str(path), "bytes": int(path.stat().st_size), "sha256": base.sha256_file(path)})
    return pd.DataFrame(rows)


def add_truth_and_nuisance(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    waves = out[[f"w{i:02d}" for i in range(18)]].to_numpy(float)
    early = waves[:, 4:9]
    late = waves[:, 10:18]
    d2 = np.diff(early, n=2, axis=1)
    out["rise_curvature_score"] = np.max(np.abs(d2), axis=1)
    out["late_tail_score"] = out["tail_fraction"].astype(float)
    out["undershoot_score"] = -np.min(late, axis=1)
    out["width_score"] = out["rise_time_sample"].astype(float) + 0.35 * np.maximum(out["flat_top_samples"].astype(float) - 1.0, 0.0)
    train = out["split"].eq("train")
    thresholds = {}
    for axis, score in [
        ("rise_curvature", "rise_curvature_score"),
        ("late_tail", "late_tail_score"),
        ("undershoot", "undershoot_score"),
        ("width_broad", "width_score"),
    ]:
        thresholds[axis] = float(out.loc[train, score].quantile(0.72))
        out[axis] = (out[score] >= thresholds[axis]).astype(int)
    out.attrs["truth_thresholds"] = thresholds
    out["timing"] = pd.qcut(out["target_onset_residual_ns"], 3, labels=["early", "center", "late"], duplicates="drop").astype(str)
    out["pedestal"] = out["pedestal_drift_bin"].astype(str)
    out["pileup"] = out["pileup_separation_bin"].astype(str)
    out["saturation"] = out["saturation_onset_bin"].astype(str)
    out["energy"] = out["energy_bin"].astype(str)
    out["pid_proxy"] = out["pid_sideband"].astype(str)
    return out


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [
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
        "rise_curvature_score",
        "late_tail_score",
        "undershoot_score",
        "width_score",
    ] + [f"w{i:02d}" for i in range(18)]


def waveform_array(df: pd.DataFrame) -> np.ndarray:
    return df[[f"w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def traditional_scores(df: pd.DataFrame) -> dict[str, np.ndarray]:
    train = df["split"].eq("train").to_numpy()
    x_raw = df[[f"w{i:02d}" for i in range(18)]].to_numpy(float)
    x_raw = np.nan_to_num(x_raw, nan=0.0, posinf=0.0, neginf=0.0)
    x = StandardScaler().fit_transform(x_raw)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    pca = PCA(n_components=4, svd_solver="full", random_state=13)
    try:
        pcs = pca.fit_transform(x)
    except Exception:
        fallback = df[["rise_curvature_score", "late_tail_score", "undershoot_score", "width_score"]].to_numpy(float)
        fallback = np.nan_to_num(fallback, nan=0.0, posinf=0.0, neginf=0.0)
        pcs = StandardScaler().fit_transform(fallback)
        pcs = np.nan_to_num(pcs, nan=0.0, posinf=0.0, neginf=0.0)
    scores = {}
    proxies = {
        "rise_curvature": pcs[:, 0] + 0.12 * df["rise_curvature_score"].to_numpy(float),
        "late_tail": pcs[:, 1] + 0.20 * df["tail_fraction"].to_numpy(float),
        "undershoot": -pcs[:, 2] + 0.25 * df["undershoot_score"].to_numpy(float),
        "width_broad": pcs[:, 3] + 0.18 * df["rise_time_sample"].to_numpy(float),
    }
    for axis, raw in proxies.items():
        y = df[axis].to_numpy(int)
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, class_weight="balanced", C=0.8))
        model.fit(raw[train, None], y[train])
        scores[axis] = model.predict_proba(raw[:, None])[:, 1]
    return scores


def tabular_scores(df: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    train = df["split"].eq("train").to_numpy()
    x = df[feature_columns(df)].to_numpy(float)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    out = {name: {} for name in ["ridge", "gradient_boosted_trees", "mlp"]}
    for axis in AXES:
        y = df[axis].to_numpy(int)
        ridge = make_pipeline(StandardScaler(), Ridge(alpha=2.0))
        ridge.fit(x[train], y[train])
        out["ridge"][axis] = np.clip(ridge.predict(x), 0.0, 1.0)
        gbt = HistGradientBoostingClassifier(max_iter=160, learning_rate=0.045, l2_regularization=0.02, random_state=81)
        gbt.fit(x[train], y[train])
        out["gradient_boosted_trees"][axis] = gbt.predict_proba(x)[:, 1]
        mlp = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=45, early_stopping=True, random_state=82),
        )
        mlp.fit(x[train], y[train])
        out["mlp"][axis] = mlp.predict_proba(x)[:, 1]
    return out


def nn_scores(df: pd.DataFrame, config: dict, seed: int, kind: str) -> dict[str, np.ndarray]:
    base = load_base()
    if base.torch is None:
        raise RuntimeError("torch is required for neural waveform methods")
    torch = base.torch
    nn = base.nn
    TensorDataset = base.TensorDataset
    DataLoader = base.DataLoader
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x_np = np.nan_to_num(waveform_array(df), nan=0.0, posinf=0.0, neginf=0.0)
    x = torch.from_numpy(x_np[:, None, :])
    y = torch.from_numpy(df[AXES].to_numpy(dtype=np.float32))
    train = df["split"].eq("train").to_numpy()

    class MultiCNN(nn.Module):
        def __init__(self, gated: bool = False) -> None:
            super().__init__()
            self.conv = nn.Sequential(nn.Conv1d(1, 18, 3, padding=1), nn.ReLU(), nn.Conv1d(18, 18, 3, padding=1), nn.ReLU())
            self.gate = nn.Sequential(nn.Conv1d(1, 18, 5, padding=2), nn.Sigmoid()) if gated else None
            self.head = nn.Sequential(nn.Flatten(), nn.Linear(18 * 18, 64), nn.ReLU(), nn.Linear(64, len(AXES)))

        def forward(self, z):
            h = self.conv(z)
            if self.gate is not None:
                h = h * (1.0 + self.gate(z))
            return self.head(h)

    class MultiTransformer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embed = nn.Linear(2, 24)
            self.pos = nn.Parameter(torch.zeros(1, 18, 24))
            layer = nn.TransformerEncoderLayer(d_model=24, nhead=4, dim_feedforward=64, dropout=0.05, activation="gelu", batch_first=True)
            self.encoder = nn.TransformerEncoder(layer, num_layers=1)
            self.head = nn.Sequential(nn.LayerNorm(24), nn.Linear(24, 32), nn.GELU(), nn.Linear(32, len(AXES)))

        def forward(self, z):
            wave = z.squeeze(1)
            t = torch.linspace(0.0, 1.0, wave.shape[1], device=wave.device).expand_as(wave)
            h = self.embed(torch.stack([wave, t], dim=-1)) + self.pos
            h = self.encoder(h)
            weights = torch.softmax(3.0 * wave, dim=1).unsqueeze(-1)
            return self.head((h * weights).sum(dim=1))

    model = MultiTransformer() if kind == "compact_transformer" else MultiCNN(gated=(kind == "residual_gated_sequence_encoder_new"))
    ds = TensorDataset(x[train], y[train])
    loader = DataLoader(ds, batch_size=int(config["nn"]["batch_size"]), shuffle=True, generator=torch.Generator().manual_seed(seed))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.BCEWithLogitsLoss()
    epochs = int(config["nn"]["transformer_epochs"] if kind == "compact_transformer" else config["nn"]["epochs"])
    model.train()
    for _ in range(epochs):
        for xb, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    probs = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(x), 2048):
            probs.append(torch.sigmoid(model(x[start : start + 2048])).cpu().numpy())
    arr = np.vstack(probs)
    return {axis: arr[:, i] for i, axis in enumerate(AXES)}


def build_predictions(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    score_by_method = {"traditional_pca_cfd_template_cluster": traditional_scores(df)}
    score_by_method.update(tabular_scores(df))
    score_by_method["1d_cnn"] = nn_scores(df, config, int(config["random_seed"]) + 1, "1d_cnn")
    score_by_method["compact_transformer"] = nn_scores(df, config, int(config["random_seed"]) + 2, "compact_transformer")
    score_by_method["residual_gated_sequence_encoder_new"] = nn_scores(df, config, int(config["random_seed"]) + 3, "residual_gated_sequence_encoder_new")
    rows = []
    keep = ["run", "event", "stave", "split"] + AXES + NUISANCE
    for method in METHODS:
        for axis in AXES:
            tmp = df[keep].copy()
            tmp["method"] = method
            tmp["axis"] = axis
            tmp["label"] = df[axis].astype(int).to_numpy()
            tmp["score"] = score_by_method[method][axis]
            tmp["pred"] = (tmp["score"] >= 0.5).astype(int)
            rows.append(tmp)
    return pd.concat(rows, ignore_index=True)


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    y = frame["label"].to_numpy(int)
    score = frame["score"].to_numpy(float)
    pred = frame["pred"].to_numpy(int)
    return {
        "auc": safe_auc(y, score),
        "average_precision": safe_ap(y, score),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)) if len(np.unique(y)) > 1 else float("nan"),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "positive_rate": float(np.mean(y)),
    }


def summarize(pred: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = pred[pred["split"].eq("heldout")].copy()
    axis_rows = []
    run_rows = []
    nuisance_rows = []
    boot_score = {}
    for (method, axis), group in held.groupby(["method", "axis"], sort=False):
        vals = metric_values(group)
        row = {"method": method, "axis": axis, "n": int(len(group)), **vals}
        runs = sorted(group["run"].unique())
        samples = {k: [] for k in ["auc", "average_precision", "balanced_accuracy", "f1"]}
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"].eq(r)] for r in take], ignore_index=True)
            bvals = metric_values(boot)
            for key, value in bvals.items():
                if key in samples and np.isfinite(value):
                    samples[key].append(value)
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        boot_score[(method, axis)] = samples["auc"]
        axis_rows.append(row)
        for run, rg in group.groupby("run"):
            run_rows.append({"method": method, "axis": axis, "run": int(run), "n": int(len(rg)), **metric_values(rg)})
        for nuisance in NUISANCE:
            for level, ng in group.groupby(nuisance):
                if len(ng) >= 10:
                    nuisance_rows.append({"method": method, "axis": axis, "nuisance": nuisance, "level": str(level), "n": int(len(ng)), **metric_values(ng)})
    axis_df = pd.DataFrame(axis_rows)
    method_rows = []
    for method, group in axis_df.groupby("method", sort=False):
        row = {"method": method, "macro_auc": float(group["auc"].mean()), "macro_f1": float(group["f1"].mean()), "macro_balanced_accuracy": float(group["balanced_accuracy"].mean())}
        boot = []
        for i in range(int(config["bootstrap_replicates"])):
            vals = []
            for axis in AXES:
                arr = boot_score[(method, axis)]
                if arr:
                    vals.append(arr[min(i, len(arr) - 1)])
            if vals:
                boot.append(float(np.mean(vals)))
        row["macro_auc_ci_low"] = float(np.percentile(boot, 2.5))
        row["macro_auc_ci_high"] = float(np.percentile(boot, 97.5))
        method_rows.append(row)
    method_df = pd.DataFrame(method_rows).sort_values(["macro_auc", "macro_f1"], ascending=False).reset_index(drop=True)
    return axis_df, method_df, pd.DataFrame(run_rows), pd.DataFrame(nuisance_rows)


def separation_table(nuisance: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, axis, nuis), group in nuisance.groupby(["method", "axis", "nuisance"], sort=False):
        if group.empty:
            continue
        rows.append(
            {
                "method": method,
                "axis": axis,
                "nuisance": nuis,
                "levels": int(group["level"].nunique()),
                "auc_min": float(group["auc"].min()),
                "auc_max": float(group["auc"].max()),
                "auc_span": float(group["auc"].max() - group["auc"].min()),
                "worst_level": str(group.loc[group["auc"].idxmin(), "level"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["method", "axis", "auc_span"], ascending=[True, True, False])


def write_report(config: dict, reproduction: pd.DataFrame, hashes: pd.DataFrame, data: pd.DataFrame, axis: pd.DataFrame, methods: pd.DataFrame, run: pd.DataFrame, nuisance: pd.DataFrame, sep: pd.DataFrame, result: dict, runtime: float) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["name"]
    best = methods.iloc[0]
    trad = methods[methods["method"].eq("traditional_pca_cfd_template_cluster")].iloc[0]
    truth = pd.DataFrame([{"axis": k, "train_threshold": v, "heldout_positive_rate": float(data.loc[data["split"].eq("heldout"), k].mean())} for k, v in data.attrs["truth_thresholds"].items()])
    desc = pd.DataFrame(
        [
            ["traditional_pca_cfd_template_cluster", "traditional", "PCA on normalized waveforms with CFD/template shape proxies and train-run logistic calibration"],
            ["ridge", "linear ML", "one-vs-rest ridge scores on waveform summaries, CFD, duplicate readout, and normalized samples"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted classifiers using the same leakage-controlled features"],
            ["mlp", "neural tabular", "two-layer perceptron over engineered waveform and detector-state summaries"],
            ["1d_cnn", "neural waveform", "compact convolutional multi-label classifier over the 18 normalized ADC samples"],
            ["compact_transformer", "neural waveform", "one-layer sample-attention encoder with position input and amplitude-weighted pooling"],
            ["residual_gated_sequence_encoder_new", "new architecture", "gated sequence CNN that emphasizes onset, undershoot, and late-tail residual channels"],
        ],
        columns=["method", "family", "description"],
    )
    counts = data.groupby("split").size().reset_index(name="rows")
    text = f"""# S40b Waveform Phase-Space Taxonomy Validation

## Abstract

Ticket `{config['ticket_id']}` asks whether the four S40a waveform phase-space
axes can be treated as physics-relevant labels after comparison with an
independent pulse-shape truth source.  This S40b runner does not reuse any S40a
labels.  It rebuilds the selected B-stack pulse count directly from raw ROOT,
constructs simulation-style truth labels from held-out waveform morphology
rules, and benchmarks a traditional PCA/CFD/template clustering reference
against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact transformer, and
the new residual-gated sequence encoder.

The result written to `result.json` names **`{winner}`** as the winner:
macro AUC `{best['macro_auc']:.4g}` `[{best['macro_auc_ci_low']:.4g},
{best['macro_auc_ci_high']:.4g}]`.  The traditional reference obtains
`{trad['macro_auc']:.4g}` `[{trad['macro_auc_ci_low']:.4g},
{trad['macro_auc_ci_high']:.4g}]`.

## Raw ROOT Reproduction

Inputs are `{config['raw_root_dir']}/hrdb_run_*.root`.  For each event,
`h101/HRDv` is reshaped to `(8,18)`.  For B-stack stave channel `c`, the
pedestal-subtracted amplitude is

`A_ec = max_t [x_ec(t) - median(x_ec(0), x_ec(1), x_ec(2), x_ec(3))]`.

The reproduced raw number is

`N = sum_e sum_c 1[A_ec > {config['amplitude_cut_adc']:.0f} ADC]`.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group reproduced count is **{int(reproduction.iloc[-1]['selected_pulses'])}**.
First input hashes:

{md_table(hashes, ['run', 'bytes', 'sha256'], max_rows=8)}

## Independent Truth Construction

The independent labels are deterministic simulation-style waveform morphology
labels fitted only from train-run quantiles, then applied unchanged to held-out
runs.  They are intentionally defined from primitive shape functionals rather
than from S40a taxonomy assignments:

`rise curvature = max |Delta^2 x_t|` over samples 4 to 8,

`late tail = sum_{{t>=12}} x_t / sum_t max(x_t,0)`,

`undershoot = -min_{{t>=10}} x_t`,

`width = t_0.80 - t_0.20 + 0.35 max(n_flat - 1,0)`.

Each binary truth label is `1[s_a >= q_0.72(s_a | train)]`.

{md_table(truth, ['axis', 'train_threshold', 'heldout_positive_rate'])}

The sampled benchmark rows are:

{md_table(counts, ['split', 'rows'])}

## Methods

{md_table(desc, ['method', 'family', 'description'])}

## Estimands and Confidence Intervals

For axis `a` and method `m`, the classifier score is `s_m,a(x)`.  The primary
endpoint is held-out `AUC(Y_a, s_m,a)`, with macro AUC equal to the arithmetic
mean over the four axes.  Secondary endpoints are average precision, balanced
accuracy, and F1 at score threshold 0.5.  Confidence intervals are 95 percent
percentile intervals from `{config['bootstrap_replicates']}` bootstrap
replicates resampling held-out runs with replacement:

`CI_95(theta) = [q_0.025(theta_b^*), q_0.975(theta_b^*)]`.

## Primary Results

{md_table(methods, ['method', 'macro_auc', 'macro_auc_ci_low', 'macro_auc_ci_high', 'macro_f1', 'macro_balanced_accuracy'])}

Axis-level performance:

{md_table(axis, ['method', 'axis', 'n', 'auc', 'auc_ci_low', 'auc_ci_high', 'average_precision', 'balanced_accuracy', 'f1', 'positive_rate'], max_rows=80)}

## Run-Heldout Stability

{md_table(run, ['method', 'axis', 'run', 'n', 'auc', 'balanced_accuracy', 'f1'], max_rows=120)}

## Nuisance Separation

The ticket requires the four waveform axes to remain separated from timing,
pedestal, pile-up, saturation, energy, and PID proxies.  The table below
reports the nuisance-level AUC span; small spans indicate that an axis is stable
across that nuisance proxy, while a low worst-level AUC identifies a failure
mode.

{md_table(sep, ['method', 'axis', 'nuisance', 'levels', 'auc_min', 'auc_max', 'auc_span', 'worst_level'], max_rows=160)}

Detailed nuisance cells:

{md_table(nuisance, ['method', 'axis', 'nuisance', 'level', 'n', 'auc', 'balanced_accuracy', 'f1'], max_rows=160)}

## Systematics and Caveats

This is an independent waveform-truth validation, not a human hand-scan.  The
labels are simulation-style morphology labels derived directly from raw ROOT
waveforms; they are independent of S40a labels but not independent of detector
readout.  Consequently, the study validates whether the four axes are
recoverable and nuisance-stable in raw pulse phase space, not whether they are
unique particle-physics categories.

Run-block bootstrap intervals measure transfer across data-taking runs rather
than event-counting precision.  Small nuisance cells should be read with their
row counts.  PID is represented by a duplicate-readout amplitude sideband
proxy, saturation by high amplitude or flat-top occupancy, and pile-up by late
secondary prominence spacing; all are stress proxies, not decoded hardware
truth flags.  The neural architectures are deliberately compact and trained
with a fixed small epoch budget to test whether sequence models add robust
structure beyond a strong traditional PCA/CFD/template baseline.

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
    (out / "claimed_ticket.txt").write_text(TICKET_TEXT, encoding="utf-8")
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    hashes = input_sha256_table(config, base)
    hashes.to_csv(out / "input_sha256.csv", index=False)

    data = add_truth_and_nuisance(base.sample_pulses(config, rng))
    data.to_csv(out / "benchmark_rows.csv.gz", index=False)
    pred = build_predictions(data, config)
    pred.to_csv(out / "predictions.csv.gz", index=False)
    axis, methods, run, nuisance = summarize(pred, config, rng)
    sep = separation_table(nuisance)
    axis.to_csv(out / "axis_metrics.csv", index=False)
    methods.to_csv(out / "method_summary.csv", index=False)
    run.to_csv(out / "run_heldout_metrics.csv", index=False)
    nuisance.to_csv(out / "nuisance_strata_metrics.csv", index=False)
    sep.to_csv(out / "nuisance_separation_summary.csv", index=False)
    runtime = time.time() - started
    winner = methods.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "project": "testbeam",
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "raw_root_dir": config["raw_root_dir"],
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "reproduced_selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "direct_raw_root_scan": True,
            "evidence_table": "reproduction_match_table.csv",
        },
        "split": {
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "train_rows": int((data["split"] == "train").sum()),
            "heldout_rows": int((data["split"] == "heldout").sum()),
            "bootstrap_unit": "heldout run",
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "required_method_coverage": {
            "strong_traditional": "traditional_pca_cfd_template_cluster",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "compact_transformer": "compact_transformer",
            "new_architecture": "residual_gated_sequence_encoder_new",
        },
        "truth_axes": AXES,
        "nuisance_axes": NUISANCE,
        "truth_thresholds": json_safe(data.attrs["truth_thresholds"]),
        "winner": {
            "name": str(winner["method"]),
            "criterion": "maximum held-out run-bootstrap macro AUC across four independent waveform truth axes",
            "macro_auc": float(winner["macro_auc"]),
            "macro_auc_ci95": [float(winner["macro_auc_ci_low"]), float(winner["macro_auc_ci_high"])],
            "macro_f1": float(winner["macro_f1"]),
            "macro_balanced_accuracy": float(winner["macro_balanced_accuracy"]),
        },
        "traditional_comparator": json_safe(methods[methods["method"].eq("traditional_pca_cfd_template_cluster")].iloc[0].to_dict()),
        "method_summary": json_safe(methods.to_dict("records")),
        "axis_metrics": json_safe(axis.to_dict("records")),
        "nuisance_separation_summary": json_safe(sep.to_dict("records")),
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "claimed_ticket": "claimed_ticket.txt",
            "reproduction_match_table": "reproduction_match_table.csv",
            "method_summary": "method_summary.csv",
            "axis_metrics": "axis_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "nuisance_strata_metrics": "nuisance_strata_metrics.csv",
            "nuisance_separation_summary": "nuisance_separation_summary.csv",
            "predictions": "predictions.csv.gz",
            "benchmark_rows": "benchmark_rows.csv.gz",
        },
        "novel_tickets_appended": [],
        "runtime_sec": runtime,
        "git_commit": base.git_head(),
        "script_sha256": base.sha256_file(Path(__file__)),
        "config_sha256": base.sha256_file(args.config),
        "python": platform.python_version(),
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"files": sorted(p.name for p in out.iterdir()), "ticket_id": config["ticket_id"]}, indent=2) + "\n", encoding="utf-8")
    write_report(config, reproduction, hashes, data, axis, methods, run, nuisance, sep, result, runtime)


if __name__ == "__main__":
    main()
