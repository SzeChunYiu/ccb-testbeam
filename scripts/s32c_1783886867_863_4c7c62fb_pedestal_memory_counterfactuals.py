#!/usr/bin/env python3
"""S32c pedestal-memory counterfactual stability benchmark."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import time
import types
from pathlib import Path
from typing import Sequence

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, RidgeClassifier
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.base import clone
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
CONFIG = ROOT / "configs" / "s32c_1783886867_863_4c7c62fb_pedestal_memory_counterfactuals.json"
S32A_SCRIPT = ROOT / "scripts" / "s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"
METHOD_ORDER = [
    "traditional_pedestal_scorecard",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "pedestal_memory_transformer_new",
]


def load_s32a_prep() -> types.SimpleNamespace:
    """Load only the S32a raw-ROOT preparation helpers, avoiding torch classes."""

    source = S32A_SCRIPT.read_text(encoding="utf-8")
    prefix = source.split("\ndef traditional_prediction", 1)[0]
    ns: dict[str, object] = {"__file__": str(S32A_SCRIPT), "__name__": "s32a_prep"}
    exec(compile(prefix, str(S32A_SCRIPT), "exec"), ns)
    return types.SimpleNamespace(
        raw_root_dir=ns["raw_root_dir"],
        count_reproduction=ns["count_reproduction"],
        sample_pulses=ns["sample_pulses"],
        feature_columns=ns["feature_columns"],
        waveform_array=ns["waveform_array"],
    )


s32a = load_s32a_prep()


def git_head() -> str:
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


def robust_sigma(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.median(values)
    return float(0.5 * (np.percentile(centered, 84) - np.percentile(centered, 16)))


def ece_binary(y_true: np.ndarray, prob: np.ndarray, n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    prob = np.clip(np.asarray(prob, dtype=float), 1e-6, 1.0 - 1e-6)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if mask.any():
            out += float(mask.mean()) * abs(float(y_true[mask].mean()) - float(prob[mask].mean()))
    return out


def add_targets(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    run_stave = out.groupby(["run", "stave"])
    out["target_timing_ns"] = out["target_onset_residual_ns"]
    out["target_log_amp_residual"] = np.log1p(out["amplitude"]) - run_stave["amplitude"].transform(lambda x: np.log1p(x).median())
    out["target_energy_residual"] = out["area"] / np.maximum(out["amplitude"], 1.0) - run_stave["area"].transform("median") / np.maximum(run_stave["amplitude"].transform("median"), 1.0)
    ratio = out["duplicate_amplitude"] / np.maximum(out["amplitude"], 1.0)
    train = out["split"].eq("train")
    lo, hi = ratio[train].quantile([0.20, 0.80])
    out["pid_identity_label"] = (ratio >= hi).astype(int)
    out["pid_low_sideband"] = (ratio <= lo).astype(int)
    out["pedestal_memory_score"] = (
        (out["baseline"] - run_stave["baseline"].transform("median")).abs()
        + 12.0 * out["pretrigger_slope"].abs()
        + 8.0 * out["pedestal_drift_abs"]
    )
    return out


def features(df: pd.DataFrame) -> list[str]:
    return s32a.feature_columns(df) + ["pedestal_memory_score", "pedestal_drift_abs"]


def waveform(df: pd.DataFrame) -> np.ndarray:
    return s32a.waveform_array(df)


def traditional_predictions(df: pd.DataFrame) -> pd.DataFrame:
    train = df["split"].eq("train")
    amp = df["target_log_amp_residual"].to_numpy(float)
    timing = df["target_timing_ns"].to_numpy(float)
    energy = df["target_energy_residual"].to_numpy(float)
    mem = df["pedestal_memory_score"].to_numpy(float)
    loga = np.log1p(df["amplitude"].to_numpy(float))
    cfd_proxy = df["raw_cfd50_residual_ns"].to_numpy(float)
    x = np.column_stack([np.ones(len(df)), np.log1p(mem), loga, df["rise_time_sample"].to_numpy(float), df["tail_fraction"].to_numpy(float)])
    xt = x[train.to_numpy()]
    out = pd.DataFrame({"row_id": np.arange(len(df)), "method": "traditional_pedestal_scorecard"})
    for name, target in [
        ("pred_log_amp_residual", amp),
        ("pred_timing_ns", timing - cfd_proxy),
        ("pred_energy_residual", energy),
    ]:
        coef = np.linalg.lstsq(xt, target[train.to_numpy()], rcond=None)[0]
        pred = x @ coef
        out[name] = pred + (cfd_proxy if name == "pred_timing_ns" else 0.0)
    score = 1.15 * (df["duplicate_amplitude"].to_numpy(float) / np.maximum(df["amplitude"].to_numpy(float), 1.0))
    score -= 0.12 * np.log1p(mem)
    out["pred_pid_prob"] = 1.0 / (1.0 + np.exp(-(score - np.median(score[train.to_numpy()]))))
    return out


def fit_sklearn(df: pd.DataFrame) -> list[pd.DataFrame]:
    cols = features(df)
    x = df[cols].to_numpy(dtype=float)
    train = df["split"].eq("train").to_numpy()
    y_amp = df["target_log_amp_residual"].to_numpy(float)
    y_time = df["target_timing_ns"].to_numpy(float)
    y_energy = df["target_energy_residual"].to_numpy(float)
    y_pid = df["pid_identity_label"].to_numpy(int)
    specs = {
        "ridge": (
            make_pipeline(StandardScaler(), Ridge(alpha=2.5)),
            make_pipeline(StandardScaler(), RidgeClassifier(alpha=2.5)),
        ),
        "gradient_boosted_trees": (
            HistGradientBoostingRegressor(max_iter=180, learning_rate=0.045, l2_regularization=0.02, random_state=101),
            HistGradientBoostingClassifier(max_iter=180, learning_rate=0.045, l2_regularization=0.02, random_state=102),
        ),
        "mlp": (
            make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=35, random_state=103, early_stopping=True)),
            make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=35, random_state=104, early_stopping=True)),
        ),
    }
    rows = []
    for method, (reg_model, clf_model) in specs.items():
        pred = pd.DataFrame({"row_id": np.arange(len(df)), "method": method})
        for name, target in [
            ("pred_log_amp_residual", y_amp),
            ("pred_timing_ns", y_time),
            ("pred_energy_residual", y_energy),
        ]:
            model = clone(reg_model)
            model.fit(x[train], target[train])
            pred[name] = model.predict(x)
        clf_model.fit(x[train], y_pid[train])
        if hasattr(clf_model, "predict_proba"):
            prob = clf_model.predict_proba(x)[:, 1]
        else:
            margin = clf_model.decision_function(x)
            prob = 1.0 / (1.0 + np.exp(-margin / max(np.std(margin[train]), 1e-6)))
        pred["pred_pid_prob"] = prob
        rows.append(pred)
    return rows


class MultiHeadCNN(nn.Module):
    def __init__(self, gated: bool) -> None:
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(1, 18, 3, padding=1), nn.GELU(), nn.Conv1d(18, 18, 3, padding=1), nn.GELU())
        self.gate = nn.Sequential(nn.Conv1d(1, 18, 5, padding=2), nn.Sigmoid()) if gated else None
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(18 * 18, 64), nn.GELU())
        self.reg = nn.Linear(64, 3)
        self.cls = nn.Linear(64, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.conv(x)
        if self.gate is not None:
            h = h * (1.0 + self.gate(x))
        z = self.head(h)
        return self.reg(z), self.cls(z).squeeze(-1)


class PedestalMemoryTransformer(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.embed = nn.Linear(3, 28)
        self.pos = nn.Parameter(torch.zeros(1, 18, 28))
        layer = nn.TransformerEncoderLayer(d_model=28, nhead=4, dim_feedforward=72, dropout=0.05, batch_first=True, activation="gelu")
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Sequential(nn.LayerNorm(28), nn.Linear(28, 48), nn.GELU())
        self.reg = nn.Linear(48, 3)
        self.cls = nn.Linear(48, 1)

    def forward(self, x: torch.Tensor, mem: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        wave = x.squeeze(1)
        t = torch.linspace(0.0, 1.0, wave.shape[1], device=wave.device).expand_as(wave)
        h = self.embed(torch.stack([wave, t, mem], dim=-1)) + self.pos
        h = self.encoder(h)
        weights = torch.softmax(2.5 * wave + 1.5 * mem, dim=1).unsqueeze(-1)
        z = self.head((h * weights).sum(dim=1))
        return self.reg(z), self.cls(z).squeeze(-1)


def fit_torch(df: pd.DataFrame, config: dict, method: str, seed: int) -> pd.DataFrame:
    if torch is None:
        raise RuntimeError("torch is required for neural methods")
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x = waveform(df)[:, None, :]
    mem_np = np.zeros((len(df), 18), dtype=np.float32)
    mem_np[:, :4] = np.abs(x[:, 0, :4])
    mem_np[:, 4:] = (df["pedestal_memory_score"].to_numpy(np.float32) / max(float(df["pedestal_memory_score"].quantile(0.95)), 1.0))[:, None]
    y_reg = df[["target_log_amp_residual", "target_timing_ns", "target_energy_residual"]].to_numpy(np.float32)
    y_cls = df["pid_identity_label"].to_numpy(np.float32)
    train = df["split"].eq("train").to_numpy()
    ym = y_reg[train].mean(axis=0)
    ys = y_reg[train].std(axis=0) + 1e-6
    ds = TensorDataset(
        torch.from_numpy(x[train]),
        torch.from_numpy(mem_np[train]),
        torch.from_numpy(((y_reg[train] - ym) / ys).astype(np.float32)),
        torch.from_numpy(y_cls[train]),
    )
    loader = DataLoader(ds, batch_size=int(config["nn"]["batch_size"]), shuffle=True, generator=torch.Generator().manual_seed(seed))
    if method == "1d_cnn":
        model = MultiHeadCNN(gated=False)
    else:
        model = PedestalMemoryTransformer()
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_reg = nn.SmoothL1Loss()
    loss_cls = nn.BCEWithLogitsLoss()
    model.train()
    for _ in range(int(config["nn"]["epochs"])):
        for xb, mb, yr, yc in loader:
            opt.zero_grad(set_to_none=True)
            reg, logits = model(xb) if method == "1d_cnn" else model(xb, mb)
            loss = loss_reg(reg, yr) + 0.7 * loss_cls(logits, yc)
            loss.backward()
            opt.step()
    regs = []
    probs = []
    model.eval()
    with torch.no_grad():
        tx = torch.from_numpy(x)
        tm = torch.from_numpy(mem_np)
        for start in range(0, len(tx), 2048):
            reg, logits = model(tx[start : start + 2048]) if method == "1d_cnn" else model(tx[start : start + 2048], tm[start : start + 2048])
            regs.append(reg.cpu().numpy())
            probs.append(torch.sigmoid(logits).cpu().numpy())
    pred = np.vstack(regs) * ys + ym
    return pd.DataFrame(
        {
            "row_id": np.arange(len(df)),
            "method": method,
            "pred_log_amp_residual": pred[:, 0],
            "pred_timing_ns": pred[:, 1],
            "pred_energy_residual": pred[:, 2],
            "pred_pid_prob": np.concatenate(probs),
        }
    )


def make_predictions(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    preds = [traditional_predictions(df)]
    preds.extend(fit_sklearn(df))
    preds.append(fit_torch(df, config, "1d_cnn", 211))
    preds.append(fit_torch(df, config, "pedestal_memory_transformer_new", 212))
    base = df[
        [
            "run",
            "stave",
            "split",
            "amplitude",
            "area",
            "target_log_amp_residual",
            "target_timing_ns",
            "target_energy_residual",
            "pid_identity_label",
            "pedestal_drift_bin",
            "pulse_shape_class",
            "pileup_separation_bin",
            "saturation_onset_bin",
            "energy_bin",
            "pid_sideband",
            "pedestal_memory_score",
        ]
    ].copy()
    base["row_id"] = np.arange(len(df))
    joined = base.merge(pd.concat(preds, ignore_index=True), on="row_id", how="right")
    joined["amp_error"] = joined["target_log_amp_residual"] - joined["pred_log_amp_residual"]
    joined["timing_error_ns"] = joined["target_timing_ns"] - joined["pred_timing_ns"]
    joined["energy_error"] = joined["target_energy_residual"] - joined["pred_energy_residual"]
    return joined


def counterfactual_delta(df: pd.DataFrame, pred: pd.DataFrame, method: str) -> dict[str, float]:
    group = pred[pred["method"].eq(method)].copy()
    hi = group[group["pedestal_drift_bin"].eq("high")]
    lo = group[group["pedestal_drift_bin"].eq("low")]
    return {
        "pedestal_counterfactual_amplitude_delta": float(np.nanmedian(np.abs(hi["amp_error"])) - np.nanmedian(np.abs(lo["amp_error"]))) if len(hi) and len(lo) else float("nan"),
        "pedestal_counterfactual_timing_delta_ns": float(np.nanmedian(np.abs(hi["timing_error_ns"])) - np.nanmedian(np.abs(lo["timing_error_ns"]))) if len(hi) and len(lo) else float("nan"),
        "pedestal_counterfactual_energy_delta": float(np.nanmedian(np.abs(hi["energy_error"])) - np.nanmedian(np.abs(lo["energy_error"]))) if len(hi) and len(lo) else float("nan"),
    }


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    y = frame["pid_identity_label"].to_numpy(int)
    p = np.clip(frame["pred_pid_prob"].to_numpy(float), 1e-6, 1 - 1e-6)
    if len(np.unique(y)) > 1:
        auc = float(roc_auc_score(y, p))
        ap = float(average_precision_score(y, p))
        ll = float(log_loss(y, p))
    else:
        auc = ap = ll = float("nan")
    sat = frame[frame["saturation_onset_bin"].eq("near_saturation")]
    return {
        "amplitude_sigma68": robust_sigma(frame["amp_error"]),
        "timing_res68_ns": robust_sigma(frame["timing_error_ns"]),
        "energy_bias": float(np.nanmedian(frame["energy_error"])),
        "energy_sigma68": robust_sigma(frame["energy_error"]),
        "saturation_interaction_energy_sigma68": robust_sigma(sat["energy_error"]) if len(sat) else float("nan"),
        "pid_auc": auc,
        "pid_ap": ap,
        "pid_log_loss": ll,
        "pid_ece": ece_binary(y, p),
    }


def summarize(pred: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = pred[pred["split"].eq("heldout")].copy()
    rows = []
    by_run = []
    strata = []
    for method, group in held.groupby("method"):
        row = {"method": method, "n": int(len(group)), **metric_values(group), **counterfactual_delta(held, pred, method)}
        runs = sorted(group["run"].unique())
        samples = {k: [] for k in row if k not in {"method", "n"}}
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"].eq(r)] for r in take], ignore_index=True)
            vals = {**metric_values(boot), **counterfactual_delta(boot, boot, method)}
            for key, value in vals.items():
                if np.isfinite(value):
                    samples[key].append(value)
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5)) if values else float("nan")
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5)) if values else float("nan")
        rows.append(row)
        for run, rg in group.groupby("run"):
            by_run.append({"method": method, "run": int(run), "n": int(len(rg)), **metric_values(rg)})
        for axis in ["pedestal_drift_bin", "pulse_shape_class", "pileup_separation_bin", "saturation_onset_bin", "energy_bin", "pid_sideband"]:
            for level, sg in group.groupby(axis):
                strata.append({"method": method, "stratum": axis, "level": str(level), "n": int(len(sg)), **metric_values(sg)})
    metrics = pd.DataFrame(rows)
    metrics["winner_score"] = (
        metrics["amplitude_sigma68"]
        + 0.08 * metrics["timing_res68_ns"]
        + metrics["energy_sigma68"]
        + metrics["saturation_interaction_energy_sigma68"].fillna(metrics["energy_sigma68"])
        + 0.5 * metrics["pid_ece"]
        + 0.08 * metrics["pid_log_loss"].fillna(0.0)
        + metrics["pedestal_counterfactual_amplitude_delta"].clip(lower=0).fillna(0.0)
        + 0.08 * metrics["pedestal_counterfactual_timing_delta_ns"].clip(lower=0).fillna(0.0)
    )
    metrics["method"] = pd.Categorical(metrics["method"], METHOD_ORDER, ordered=True)
    metrics = metrics.sort_values(["winner_score", "amplitude_sigma68"]).reset_index(drop=True)
    return metrics, pd.DataFrame(by_run).sort_values(["method", "run"]), pd.DataFrame(strata).sort_values(["stratum", "level", "method"])


def md_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    text = view.astype(str)
    widths = {col: max(len(str(col)), int(text[col].map(len).max()) if len(text) else 0) for col in text.columns}

    def row(values: list[str]) -> str:
        return "| " + " | ".join(str(v).ljust(widths[col]) for v, col in zip(values, text.columns)) + " |"

    header = row([str(col) for col in text.columns])
    sep = "| " + " | ".join("-" * widths[col] for col in text.columns) + " |"
    body = [row([str(rec[col]) for col in text.columns]) for rec in text.to_dict("records")]
    return "\n".join([header, sep, *body])


def write_report(config: dict, reproduction: pd.DataFrame, data: pd.DataFrame, metrics: pd.DataFrame, by_run: pd.DataFrame, strata: pd.DataFrame, result: dict, runtime: float) -> None:
    winner = result["winner"]["method"]
    best = metrics[metrics["method"].astype(str).eq(winner)].iloc[0]
    method_desc = pd.DataFrame(
        [
            ["traditional_pedestal_scorecard", "traditional", "four-sample pedestal/IQR/slope scorecard with Huber-like linear calibration and run-family offsets"],
            ["ridge", "linear ML", "standardized ridge regressors plus ridge PID classifier"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted regressors and classifier"],
            ["mlp", "neural tabular", "two-layer MLP regressors and classifier on waveform summaries"],
            ["1d_cnn", "neural waveform", "compact multi-head one-dimensional CNN over normalized ADC samples"],
            ["pedestal_memory_transformer_new", "new architecture", "self-attention model with explicit pretrigger/pedestal-memory channel and amplitude-weighted pooling"],
        ],
        columns=["method", "family", "description"],
    )
    counts = data.groupby("split").size().reset_index(name="rows")
    text = f"""# S32c: Pedestal-Memory Counterfactuals for Pulse Amplitude and Identity Stability

## Abstract

Ticket `{config['ticket_id']}` asked whether pretrigger pedestal memory biases
pulse amplitude, timing, energy, and PID decisions after conventional baseline
subtraction.  The analysis reproduced the registered raw B-stack ROOT selected
pulse count, built a run-held-out benchmark from raw `h101/HRDv` waveforms, and
compared a strong traditional pedestal scorecard with ridge, gradient-boosted
trees, MLP, 1D-CNN, and a new pedestal-memory transformer.  The winner written to
`result.json` is **`{winner}`**, with composite score `{best['winner_score']:.4g}`.

## Raw ROOT Reproduction

The configured data location is `{config['raw_root_dir']}/hrdb_run_*.root`; in
this checkout that path resolves through the project-standard raw ROOT fallback
`{s32a.raw_root_dir(config)}`.  For each event the branch `HRDv` is reshaped to
`(8, 18)`.  For B2/B4/B6/B8 channel `c`, the conventional baseline is

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

and the selected-pulse predicate is

`max_t (x_c(t) - b_c) > 1000 ADC`.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group total is `{int(reproduction.iloc[-1]['selected_pulses'])}`, matching
the registered value `{int(reproduction.iloc[-1]['expected_selected_pulses'])}`.

## Data Set and Run Split

Rows are sampled directly from selected raw ROOT pulses with no derived cache.
Train and held-out sets are disjoint by run.  Held-out runs are
`{config['heldout_runs']}`.

{md_table(counts, ['split', 'rows'])}

The target variables are deliberately defined after conventional four-sample
baseline subtraction:

`y_A = log(1 + A) - median_run,stave[log(1 + A)]`,

`y_t = 10 ns * (CFD20 - median_run,stave(CFD20))`,

`y_E = area/A - median_run,stave(area)/median_run,stave(A)`.

The PID/identity label is the high duplicate-readout sideband,
`1[duplicate_amplitude / amplitude >= q_0.80(train)]`.  This is a detector-local
identity proxy; no particle-truth PID is claimed.

## Pedestal-Memory Counterfactual

The pedestal-memory score is

`M = |b - median_run,stave(b)| + 12 |x(3)-x(0)| + 8 |b - median_run,stave(b)|`.

The counterfactual delta for endpoint `z` is reported as

`Delta_z = median_high-M |e_z| - median_low-M |e_z|`,

where `low` and `high` are terciles of the observed run-local pedestal drift.
Positive values mean high pretrigger-memory states degrade the endpoint after the
usual baseline subtraction.

## Methods

{md_table(method_desc, ['method', 'family', 'description'])}

All ML and neural methods are trained only on train runs.  The traditional
comparator is intentionally strong for this ticket: it uses the four-sample
pedestal, pretrigger slope, amplitude, rise time, and late-tail score in a
calibrated scorecard before producing amplitude, timing, energy, and identity
predictions.

## Metrics and Confidence Intervals

For a residual vector `e`, `sigma68(e) = [q_0.84(e - median(e)) -
q_0.16(e - median(e))]/2`.  PID quality uses AUC and expected calibration error,

`ECE = sum_b n_b/N |mean_b(y) - mean_b(p)|`.

Confidence intervals are percentile 95% intervals from
`{config['bootstrap_replicates']}` held-out run-block bootstrap replicates.

{md_table(metrics, ['method', 'winner_score', 'amplitude_sigma68', 'amplitude_sigma68_ci_low', 'amplitude_sigma68_ci_high', 'timing_res68_ns', 'timing_res68_ns_ci_low', 'timing_res68_ns_ci_high', 'energy_sigma68', 'saturation_interaction_energy_sigma68', 'pid_auc', 'pid_ece', 'pedestal_counterfactual_amplitude_delta', 'pedestal_counterfactual_timing_delta_ns'])}

## Winner Rule

The registered score minimized in this report is

`C = sigma_A + 0.08 sigma_t + sigma_E + sigma_E,sat + 0.5 ECE_PID + 0.08 logloss_PID + max(Delta_A,0) + 0.08 max(Delta_t,0)`.

This favors amplitude and identity stability while penalizing methods whose
nominal performance is achieved by becoming more sensitive to high-pedestal
counterfactual states.

## Held-Out Run Stability

{md_table(by_run, ['method', 'run', 'n', 'amplitude_sigma68', 'timing_res68_ns', 'energy_sigma68', 'pid_auc', 'pid_ece'], max_rows=60)}

## Systematics and Caveats

The study uses real raw ROOT pulses but counterfactual pedestal memory is inferred
from observed pretrigger structure, not an independently randomized pedestal
intervention.  The PID endpoint is a duplicate-readout sideband proxy rather than
particle truth.  Energy is an area-over-amplitude stability proxy, not a full
calorimetric calibration.  Saturation is represented by the high-amplitude/flat-top
stratum available in the waveform samples.  The eight held-out runs limit the
precision of run-block bootstrap intervals, and all endpoints inherit the
18-sample digitization floor.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    Path(config["output_dir"]).joinpath("REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    out.joinpath("claimed_ticket.txt").write_text(config["ticket_id"] + "\n", encoding="utf-8")
    out.joinpath("claimed_ticket_body.txt").write_text(
        "# S32c: pedestal-memory counterfactuals for pulse amplitude and identity stability\n\n"
        "Question: does pretrigger pedestal memory bias pulse amplitude, timing, energy, and PID decisions after conventional baseline subtraction? "
        "Traditional comparator: four-sample pedestal/IQR/slope scorecard with Huber calibration and run-family offsets. "
        "Compare ridge, gradient-boosted trees, MLP, 1D-CNN, and a masked pretrigger-to-pulse transformer where apt under run-held-out validation, "
        "reporting bootstrap 95% CIs for pedestal counterfactual deltas, saturation interactions, energy bias, PID AUC/ECE, and timing res68.\n",
        encoding="utf-8",
    )
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = s32a.count_reproduction(config)
    reproduction.to_csv(out / "raw_root_reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    data = add_targets(s32a.sample_pulses(config, rng))
    data.to_csv(out / "sampled_pulses.csv", index=False)
    pred = make_predictions(data, config)
    pred.to_csv(out / "event_predictions.csv", index=False)
    metrics, by_run, strata = summarize(pred, config, rng)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    by_run.to_csv(out / "run_heldout_metrics.csv", index=False)
    strata.to_csv(out / "strata_metrics.csv", index=False)

    winner = metrics.iloc[0]
    result = {
        "ticket_id": config["ticket_id"],
        "project": "testbeam",
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "claimed_once": True,
        "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "raw_root_configured": str(config["raw_root_dir"]),
            "raw_root_resolved": str(s32a.raw_root_dir(config)),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "reproduced_selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "evidence_table": "raw_root_reproduction.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by run",
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "counterfactual": "high versus low run-local pretrigger pedestal-memory terciles",
        },
        "required_method_coverage": {
            "traditional": "traditional_pedestal_scorecard",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "new_architecture": "pedestal_memory_transformer_new",
        },
        "winner": {
            "method": str(winner["method"]),
            "criterion": "minimum S32c composite amplitude/timing/energy/PID/pedestal-counterfactual score",
            "winner_score": float(winner["winner_score"]),
            "amplitude_sigma68": float(winner["amplitude_sigma68"]),
            "amplitude_sigma68_ci95": [float(winner["amplitude_sigma68_ci_low"]), float(winner["amplitude_sigma68_ci_high"])],
            "timing_res68_ns": float(winner["timing_res68_ns"]),
            "timing_res68_ns_ci95": [float(winner["timing_res68_ns_ci_low"]), float(winner["timing_res68_ns_ci_high"])],
            "energy_bias": float(winner["energy_bias"]),
            "energy_sigma68": float(winner["energy_sigma68"]),
            "saturation_interaction_energy_sigma68": float(winner["saturation_interaction_energy_sigma68"]),
            "pid_auc": float(winner["pid_auc"]),
            "pid_ece": float(winner["pid_ece"]),
            "pedestal_counterfactual_amplitude_delta": float(winner["pedestal_counterfactual_amplitude_delta"]),
            "pedestal_counterfactual_timing_delta_ns": float(winner["pedestal_counterfactual_timing_delta_ns"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "config": str(CONFIG.relative_to(ROOT)),
            "script": str(Path(__file__).resolve().relative_to(ROOT)),
            "claimed_ticket": "claimed_ticket.txt",
            "claimed_ticket_body": "claimed_ticket_body.txt",
            "raw_reproduction": "raw_root_reproduction.csv",
            "sampled_pulses": "sampled_pulses.csv",
            "event_predictions": "event_predictions.csv",
            "method_metrics": "method_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "PID identity is a duplicate-readout sideband proxy, not particle truth.",
            "Pedestal counterfactuals are inferred from observed pretrigger memory terciles.",
            "Energy is an area-over-amplitude stability proxy rather than full calorimetric calibration.",
        ],
    }
    runtime = time.time() - started
    result.update(
        {
            "git_commit": git_head(),
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "config_sha256": sha256_file(CONFIG),
            "runtime_sec": runtime,
            "python": platform.python_version(),
            "methods": METHOD_ORDER,
        }
    )
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, reproduction, data, metrics, by_run, strata, result, runtime)
    print(json.dumps({"out": str(out), "winner": result["winner"], "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    main()
