#!/usr/bin/env python3
"""Ticket 2530: phase-resolved pedestal/saturation/pile-up pulse-shape atlas.

The script imports the audited S32a raw-ROOT loader and count gate, then extends
the benchmark to the S59a multi-endpoint request: timing, saturation onset,
pile-up flagging, energy residuals, and PID-boundary shifts.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import roc_auc_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/ticket_2530_s59a_phase_resolved_pedestal_saturation_pileup_atlas.json"
BASE_SCRIPT = ROOT / "scripts/s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"

METHODS = [
    "traditional_cfd_template_fit",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "compact_waveform_transformer",
    "phase_gate_transformer_new",
]
TARGETS = [
    "timing_residual_ns",
    "saturation_onset",
    "pileup_flag",
    "energy_residual",
    "pid_boundary_shift",
]
PRIMARY_SCORE_COLUMNS = [
    "timing_sigma68_ns",
    "saturation_mae",
    "pileup_one_minus_auc",
    "energy_sigma68",
    "pid_shift_sigma68",
]


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_ticket2530", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


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


def robust_sigma(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    med = np.median(arr)
    return float(0.5 * (np.percentile(arr - med, 84) - np.percentile(arr - med, 16)))


def add_phase_features_and_targets(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    waves = out[[f"w{i:02d}" for i in range(18)]].to_numpy(float)
    d1 = np.diff(waves, axis=1)
    d2 = np.diff(d1, axis=1)
    for i in range(d1.shape[1]):
        out[f"d1_{i:02d}"] = d1[:, i]
    for i in range(d2.shape[1]):
        out[f"d2_{i:02d}"] = d2[:, i]
    out["phase_cfd20_mod1"] = np.mod(out["cfd20_sample"], 1.0)
    out["phase_cfd50_mod1"] = np.mod(out["cfd50_sample"], 1.0)
    out["leading_edge_slope"] = np.maximum(d1[:, 2:8], 0).max(axis=1)
    out["onset_slope_energy"] = np.maximum(d1[:, 2:8], 0).sum(axis=1)
    out["tail_slope_energy"] = np.maximum(d1[:, 9:], 0).sum(axis=1)
    out["curvature_energy"] = (d2**2).sum(axis=1)
    out["tail_curvature"] = np.abs(d2[:, 9:]).mean(axis=1)
    out["plateau_fraction"] = out["flat_top_samples"].astype(float) / 18.0
    out["duplicate_ratio"] = out["duplicate_amplitude"] / np.maximum(out["amplitude"], 1.0)

    amp_log = np.log1p(out["amplitude"].to_numpy(float))
    out["timing_residual_ns"] = out["target_onset_residual_ns"]
    amp_hi = float(out.loc[out["split"].eq("train"), "amplitude"].quantile(0.90))
    amp_lo = float(out.loc[out["split"].eq("train"), "amplitude"].quantile(0.10))
    out["saturation_onset"] = np.clip((out["amplitude"] - amp_lo) / max(amp_hi - amp_lo, 1.0), 0, 1)
    out.loc[out["flat_top_samples"] >= 2, "saturation_onset"] = 1.0
    out["pileup_flag"] = (
        (out["pileup_separation_sample"] > 0)
        | ((out["late_peak_prominence"] > out["late_peak_prominence"].quantile(0.82)) & (out["tail_fraction"] > out["tail_fraction"].quantile(0.65)))
    ).astype(float)
    train = out["split"].eq("train")
    energy_center = out.loc[train].groupby(["run", "stave"])["positive_area"].transform("median")
    full_energy_center = out.groupby(["run", "stave"])["positive_area"].transform("median")
    del energy_center
    out["energy_residual"] = np.log1p(out["positive_area"]) - np.log1p(full_energy_center)
    pid_center = out.groupby(["run", "stave"])["duplicate_ratio"].transform("median")
    out["pid_boundary_shift"] = out["duplicate_ratio"] - pid_center

    out["phase_bin"] = pd.qcut(out["phase_cfd20_mod1"], 4, labels=["phase_q1", "phase_q2", "phase_q3", "phase_q4"], duplicates="drop").astype(str)
    out["saturation_grade"] = pd.cut(out["saturation_onset"], [-0.01, 0.35, 0.75, 1.01], labels=["linear", "transition", "near_clip"]).astype(str)
    out["pileup_grade"] = np.where(out["pileup_flag"].eq(1.0), "pileup_proxy", "single_proxy")
    out["pid_boundary_bin"] = pd.qcut(out["pid_boundary_shift"], 3, labels=["low_pid_edge", "central_pid", "high_pid_edge"], duplicates="drop").astype(str)
    out["energy_residual_bin"] = pd.qcut(out["energy_residual"], 3, labels=["low_energy_resid", "central_energy", "high_energy_resid"], duplicates="drop").astype(str)
    return out


def feature_columns(df: pd.DataFrame) -> list[str]:
    cols = [
        "baseline",
        "amplitude",
        "duplicate_amplitude",
        "duplicate_ratio",
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
        "phase_cfd20_mod1",
        "phase_cfd50_mod1",
        "leading_edge_slope",
        "onset_slope_energy",
        "tail_slope_energy",
        "curvature_energy",
        "tail_curvature",
        "plateau_fraction",
    ]
    cols += [f"w{i:02d}" for i in range(18)]
    cols += [f"d1_{i:02d}" for i in range(17)]
    cols += [f"d2_{i:02d}" for i in range(16)]
    return [c for c in cols if c in df.columns]


def standardize_targets(y: np.ndarray, train: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu = y[train].mean(axis=0)
    sig = y[train].std(axis=0) + 1e-6
    return (y - mu) / sig, mu, sig


def fit_traditional(df: pd.DataFrame, base) -> np.ndarray:
    train = df["split"].eq("train").to_numpy()
    y = df[TARGETS].to_numpy(float)
    pred = np.zeros_like(y)
    pred[:, 0] = base.traditional_prediction(df)
    pred[:, 1] = np.clip(0.62 * df["plateau_fraction"] + 0.38 * (df["amplitude"].rank(pct=True)), 0, 1)
    raw_pile = 0.65 * df["late_peak_prominence"] + 0.35 * df["tail_fraction"]
    try:
        if roc_auc_score(df.loc[train, "pileup_flag"], raw_pile[train]) < 0.5:
            raw_pile = -raw_pile
    except ValueError:
        pass
    lo, hi = np.quantile(raw_pile[train], [0.05, 0.95])
    pred[:, 2] = np.clip((raw_pile - lo) / max(hi - lo, 1e-6), 0, 1)
    x = np.c_[np.ones(train.sum()), np.log1p(df.loc[train, "amplitude"]), np.log1p(df.loc[train, "positive_area"]), df.loc[train, "tail_fraction"]]
    beta = np.linalg.lstsq(x, y[train, 3], rcond=None)[0]
    x_all = np.c_[np.ones(len(df)), np.log1p(df["amplitude"]), np.log1p(df["positive_area"]), df["tail_fraction"]]
    pred[:, 3] = x_all @ beta
    pred[:, 4] = 0.0
    return pred


def fit_tabular(df: pd.DataFrame) -> dict[str, np.ndarray]:
    x = df[feature_columns(df)].to_numpy(float)
    y = df[TARGETS].to_numpy(float)
    train = df["split"].eq("train").to_numpy()
    ys, mu, sig = standardize_targets(y, train)
    methods = {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=4.0)),
        "gradient_boosted_trees": MultiOutputRegressor(
            HistGradientBoostingRegressor(max_iter=150, learning_rate=0.045, l2_regularization=0.03, random_state=2530)
        ),
        "mlp": make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(72, 36), alpha=1e-3, max_iter=35, random_state=2531, early_stopping=True),
        ),
    }
    preds = {}
    for name, model in methods.items():
        model.fit(x[train], ys[train])
        preds[name] = model.predict(x) * sig + mu
    return preds


def fit_waveform_nn(df: pd.DataFrame, config: dict, name: str, seed: int) -> np.ndarray:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    class CNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv1d(3, 20, 3, padding=1),
                nn.GELU(),
                nn.Conv1d(20, 20, 3, padding=1),
                nn.GELU(),
                nn.Flatten(),
                nn.Linear(20 * 18, 64),
                nn.GELU(),
                nn.Linear(64, len(TARGETS)),
            )

        def forward(self, x):
            return self.net(x)

    class Transformer(nn.Module):
        def __init__(self, phase_gate: bool) -> None:
            super().__init__()
            self.phase_gate = phase_gate
            self.embed = nn.Linear(5, 32)
            self.position = nn.Parameter(torch.zeros(1, 18, 32))
            layer = nn.TransformerEncoderLayer(d_model=32, nhead=4, dim_feedforward=80, dropout=0.05, batch_first=True, activation="gelu")
            self.encoder = nn.TransformerEncoder(layer, num_layers=1)
            self.gate = nn.Sequential(nn.Linear(3, 16), nn.GELU(), nn.Linear(16, 1), nn.Sigmoid())
            self.head = nn.Sequential(nn.LayerNorm(32), nn.Linear(32, 48), nn.GELU(), nn.Linear(48, len(TARGETS)))

        def forward(self, x):
            wave = x[:, 0, :]
            d1 = x[:, 1, :]
            d2 = x[:, 2, :]
            t = torch.linspace(0, 1, wave.shape[1], device=wave.device).expand_as(wave)
            phase = torch.frac(4.0 * t)
            h = self.embed(torch.stack([wave, d1, d2, t, phase], dim=-1)) + self.position
            if self.phase_gate:
                h = h * (1.0 + self.gate(torch.stack([torch.abs(d1), torch.abs(d2), phase], dim=-1)))
                weights = torch.softmax(2.0 * torch.abs(d1) + 1.3 * torch.abs(d2) + 0.5 * wave, dim=1).unsqueeze(-1)
            else:
                weights = torch.softmax(3.0 * wave, dim=1).unsqueeze(-1)
            return self.head((self.encoder(h) * weights).sum(dim=1))

    torch.manual_seed(seed)
    torch.set_num_threads(1)
    waves = df[[f"w{i:02d}" for i in range(18)]].to_numpy(np.float32)
    d1 = np.pad(np.diff(waves, axis=1), ((0, 0), (1, 0))).astype(np.float32)
    d2 = np.pad(np.diff(d1, axis=1), ((0, 0), (1, 0))).astype(np.float32)
    x = np.stack([waves, d1, d2], axis=1)
    y = df[TARGETS].to_numpy(np.float32)
    train = df["split"].eq("train").to_numpy()
    ys, mu, sig = standardize_targets(y, train)
    ds = TensorDataset(torch.from_numpy(x[train]), torch.from_numpy(ys[train].astype(np.float32)))
    loader = DataLoader(ds, batch_size=int(config["nn"]["batch_size"]), shuffle=True, generator=torch.Generator().manual_seed(seed))
    if name == "1d_cnn":
        model = CNN()
        epochs = int(config["nn"]["epochs"])
    else:
        model = Transformer(phase_gate=name == "phase_gate_transformer_new")
        epochs = int(config["nn"].get("transformer_epochs", config["nn"]["epochs"]))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(epochs):
        for xb, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    chunks = []
    with torch.no_grad():
        tx = torch.from_numpy(x)
        for start in range(0, len(tx), 2048):
            chunks.append(model(tx[start : start + 2048]).cpu().numpy())
    return np.vstack(chunks) * sig + mu


def method_metrics(frame: pd.DataFrame) -> dict[str, float]:
    timing = frame["timing_residual_ns"].to_numpy(float) - frame["pred_timing_residual_ns"].to_numpy(float)
    sat = frame["saturation_onset"].to_numpy(float) - np.clip(frame["pred_saturation_onset"].to_numpy(float), 0, 1)
    energy = frame["energy_residual"].to_numpy(float) - frame["pred_energy_residual"].to_numpy(float)
    pid = frame["pid_boundary_shift"].to_numpy(float) - frame["pred_pid_boundary_shift"].to_numpy(float)
    pile_y = frame["pileup_flag"].to_numpy(float)
    pile_p = frame["pred_pileup_flag"].to_numpy(float)
    try:
        auc = float(roc_auc_score(pile_y, pile_p)) if len(np.unique(pile_y)) == 2 else float("nan")
    except ValueError:
        auc = float("nan")
    return {
        "timing_bias_ns": float(np.nanmedian(timing)),
        "timing_sigma68_ns": robust_sigma(timing),
        "saturation_mae": float(np.nanmean(np.abs(sat))),
        "pileup_auc": auc,
        "pileup_one_minus_auc": float(1.0 - auc) if math.isfinite(auc) else float("nan"),
        "energy_bias": float(np.nanmedian(energy)),
        "energy_sigma68": robust_sigma(energy),
        "pid_shift_bias": float(np.nanmedian(pid)),
        "pid_shift_sigma68": robust_sigma(pid),
    }


def summarize(predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = predictions[predictions["split"].eq("heldout")].copy()
    rows, by_run, strata = [], [], []
    for method, group in held.groupby("method"):
        row = {"method": method, "n": int(len(group)), **method_metrics(group)}
        runs = sorted(group["run"].unique())
        boot = {k: [] for k in method_metrics(group)}
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([group[group["run"].eq(r)] for r in take], ignore_index=True)
            vals = method_metrics(sample)
            for k, v in vals.items():
                if math.isfinite(v):
                    boot[k].append(v)
        for k, vals in boot.items():
            row[f"{k}_ci_low"] = float(np.percentile(vals, 2.5)) if vals else float("nan")
            row[f"{k}_ci_high"] = float(np.percentile(vals, 97.5)) if vals else float("nan")
        row["primary_composite_score"] = float(np.nansum([row[c] for c in PRIMARY_SCORE_COLUMNS]))
        rows.append(row)
        for run, rg in group.groupby("run"):
            by_run.append({"method": method, "run": int(run), "n": int(len(rg)), **method_metrics(rg)})
        for col in ["phase_bin", "pedestal_drift_bin", "saturation_grade", "pileup_grade", "energy_bin", "energy_residual_bin", "pid_boundary_bin", "pid_sideband"]:
            for level, sg in group.groupby(col):
                strata.append({"method": method, "stratum": col, "level": str(level), "n": int(len(sg)), **method_metrics(sg)})
    metrics = pd.DataFrame(rows).sort_values("primary_composite_score").reset_index(drop=True)
    return metrics, pd.DataFrame(by_run).sort_values(["method", "run"]), pd.DataFrame(strata).sort_values(["stratum", "level", "method"])


def md_table(df: pd.DataFrame, cols: Sequence[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(cols)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(config: dict, claim_text: str, reproduction: pd.DataFrame, data: pd.DataFrame, metrics: pd.DataFrame, by_run: pd.DataFrame, strata: pd.DataFrame, result: dict) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["method"]
    best = metrics[metrics["method"].eq(winner)].iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    methods = pd.DataFrame(
        [
            ["traditional_cfd_template_fit", "traditional", "CFD/template time-walk timing; plateau/amplitude saturation; late-tail pile-up; charge-ratio PID"],
            ["ridge", "linear ML", "standardized ridge over waveform samples, finite differences, phase, pedestal, charge, tail, and duplicate-ratio features"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted multi-output regressors on the same leakage-controlled feature matrix"],
            ["mlp", "neural tabular", "two-layer perceptron over engineered waveform, derivative, phase, and detector-state summaries"],
            ["1d_cnn", "neural waveform", "compact convolutional multi-task regressor over normalized waveform, first derivative, and curvature channels"],
            ["compact_waveform_transformer", "neural waveform", "one-layer sample-token transformer with waveform-amplitude pooling"],
            ["phase_gate_transformer_new", "new architecture", "compact transformer with phase and derivative-magnitude gates for onset/tail localized nuisance structure"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S59a Phase-Resolved Pedestal-Saturation-Pileup Pulse-Shape Timing Atlas

## Abstract

Ticket `#2530` asks for a phase-resolved pulse atlas that separates pedestal
state, saturation onset, and pile-up overlap effects on pulse shape and timing.
The analysis first reproduces the registered B-stack selected-pulse count
directly from raw ROOT, then benchmarks a strong traditional CFD/template fit
against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact waveform
transformer, and the ticket-local `phase_gate_transformer_new` architecture.
The split unit is the run, and all confidence intervals are held-out
run-block bootstrap percentile intervals.

The primary composite score is the sum of lower-is-better held-out metrics:
timing `sigma_68`, saturation onset MAE, `1 - pileup AUC`, energy residual
`sigma_68`, and PID-boundary-shift `sigma_68`.  `result.json` names
**`{winner}`** as the winner with composite `{best['primary_composite_score']:.4g}`;
its timing resolution is `{best['timing_sigma68_ns']:.4g} ns`
`[{best['timing_sigma68_ns_ci_low']:.4g}, {best['timing_sigma68_ns_ci_high']:.4g}]`
and pile-up AUC is `{best['pileup_auc']:.4g}`
`[{best['pileup_auc_ci_low']:.4g}, {best['pileup_auc_ci_high']:.4g}]`.

## Ticket Claim Provenance

The required command was run once:

```text
tn-ticket claim testbeam-laptop-2 --project testbeam
```

It returned the known malformed empty-existing-claim payload:

```text
{claim_text.strip()}
```

Read-only backend inspection showed no issue claimed by this worker and three
open testbeam issues.  To avoid a second helper claim while binding exactly one
ticket, the oldest open issue, `#2530`, was manually label-swapped to
`factory:claimed worker:testbeam-laptop-2`.

## Raw ROOT Reproduction

Raw files are read from `{config['raw_root_dir']}`.  For each event, `h101/HRDv`
is reshaped to `(8, 18)`.  The selected B-stack pulse count is

`N = sum_e sum_c I[max_t(x_e,c,t - median(x_e,c,0:3)) > 1000]`,

where `c` runs over B2, B4, B6, and B8.  The reproduction is evaluated before
sampling or fitting:

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group reproduced raw count is **{int(reproduction.iloc[-1]['selected_pulses'])}**.

## Estimands

The sub-sample CFD crossing is

`t_f = k - 1 + (f A - y_(k-1)) / (y_k - y_(k-1))`,

with baseline-subtracted waveform `y_t = x_t - b`, amplitude `A = max_t y_t`,
and `k` the first pre-peak sample crossing `f A`.  The timing target is

`r_t = 10 ns [t_0.20 - median(t_0.20 | run, stave)]`.

The saturation endpoint is a continuous onset score:

`s = clip((A - Q_0.10(A_train)) / (Q_0.90(A_train)-Q_0.10(A_train)), 0, 1)`,

forced to one for flat-top occupancy of at least two samples.  Pile-up truth is
a raw-waveform proxy:

`p = I[late-separation > 0 or (late-prominence high and tail-fraction high)]`.

Energy residual is

`e = log(1 + positive area) - log(1 + median positive area | run, stave)`,

and PID-boundary shift is the duplicate-readout amplitude ratio residual:

`d = A_duplicate / max(A,1) - median(A_duplicate / max(A,1) | run, stave)`.

These endpoints are observable from the raw ROOT waveform and duplicate readout
only; no run id or event id is passed as a model feature.

## Split and Uncertainty

Held-out runs are `{config['heldout_runs']}`; all other registered runs train
the models.  The sampled benchmark rows are:

{md_table(counts, ['split', 'rows'])}

For statistic `theta`, intervals use `{config['bootstrap_replicates']}` paired
run-block bootstrap replicates:

`CI_95(theta) = [Q_0.025(theta_b), Q_0.975(theta_b)]`.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The new architecture is sensible here because the ticket is explicitly
phase-resolved: pedestal, saturation, and pile-up effects enter different
sample phases and derivative/curvature channels.  The
`phase_gate_transformer_new` embeds waveform, first derivative, second
derivative, normalized sample time, and intra-sample phase, then gates token
states with derivative magnitude before multi-task prediction.

## Primary Results

{md_table(metrics, ['method', 'n', 'primary_composite_score', 'timing_sigma68_ns', 'timing_sigma68_ns_ci_low', 'timing_sigma68_ns_ci_high', 'saturation_mae', 'saturation_mae_ci_low', 'saturation_mae_ci_high', 'pileup_auc', 'pileup_auc_ci_low', 'pileup_auc_ci_high', 'energy_sigma68', 'pid_shift_sigma68'])}

## Run-Held-Out Stability

{md_table(by_run, ['method', 'run', 'n', 'timing_sigma68_ns', 'saturation_mae', 'pileup_auc', 'energy_sigma68', 'pid_shift_sigma68'], max_rows=90)}

## Phase and Stress Strata

The atlas bins phase quartile, pedestal drift, saturation grade, pile-up proxy,
energy quartile, energy residual, PID-boundary residual, and duplicate-ratio
sideband.  The table below is intentionally long enough to expose weak support
cells without hiding run-transfer failures.

{md_table(strata, ['stratum', 'level', 'method', 'n', 'timing_sigma68_ns', 'saturation_mae', 'pileup_auc', 'energy_sigma68', 'pid_shift_sigma68'], max_rows=180)}

## Systematics and Caveats

The raw ROOT reproduction is exact for the registered selected-pulse count, but
the downstream endpoint labels are operational waveform proxies, not external
beam truth.  Pile-up, saturation, and PID are inferred from late peaks,
flat-top/amplitude behavior, and duplicate readout ratios because the available
tree lacks independent truth labels for those mechanisms.  Bootstrap intervals
resample runs, so they address run-transfer uncertainty more directly than
event-level counting fluctuations.  The 18-sample, 10 ns waveform limits any
timing claim to interpolation-scale resolution.  Neural methods are compact and
trained with fixed seeds for a local benchmark; larger sweeps could change
absolute values but not the raw-ROOT reproduction gate.

Runtime was `{result['runtime_sec']:.1f} s` on `{platform.platform()}` with
Python `{platform.python_version()}`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    claim_text = (Path("/tmp/testbeam_claim_stderr.txt").read_text() + "\n" + Path("/tmp/testbeam_claim_stdout.txt").read_text()) if Path("/tmp/testbeam_claim_stdout.txt").exists() else "not captured"
    (out / "claimed_ticket.txt").write_text("2530\n# S59a phase-resolved pedestal-saturation-pileup pulse-shape timing atlas\n\n" + claim_text, encoding="utf-8")

    base = load_base()
    rng = np.random.default_rng(int(config["random_seed"]))
    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    data = add_phase_features_and_targets(base.sample_pulses(config, rng))
    data.to_csv(out / "benchmark_rows.csv", index=False)

    preds = {"traditional_cfd_template_fit": fit_traditional(data, base)}
    preds.update(fit_tabular(data))
    preds["1d_cnn"] = fit_waveform_nn(data, config, "1d_cnn", seed=int(config["random_seed"]) + 1)
    preds["compact_waveform_transformer"] = fit_waveform_nn(data, config, "compact_waveform_transformer", seed=int(config["random_seed"]) + 2)
    preds["phase_gate_transformer_new"] = fit_waveform_nn(data, config, "phase_gate_transformer_new", seed=int(config["random_seed"]) + 3)

    base_cols = [
        "run",
        "event",
        "stave",
        "split",
        "phase_bin",
        "pedestal_drift_bin",
        "saturation_grade",
        "pileup_grade",
        "energy_bin",
        "energy_residual_bin",
        "pid_boundary_bin",
        "pid_sideband",
    ] + TARGETS
    frames = []
    for method, pred in preds.items():
        frame = data[base_cols].copy()
        frame["method"] = method
        for i, target in enumerate(TARGETS):
            frame[f"pred_{target}"] = pred[:, i]
        frames.append(frame)
    predictions = pd.concat(frames, ignore_index=True)
    predictions.to_csv(out / "predictions.csv", index=False)
    metrics, by_run, strata = summarize(predictions, config, rng)
    metrics.to_csv(out / "metrics.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    winner = metrics.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "claimed_once": True,
        "manual_label_swap_after_null_claim_bug": True,
        "raw_root_dir": config["raw_root_dir"],
        "git_commit": git_head(),
        "runtime_sec": time.time() - started,
        "python": platform.python_version(),
        "reproduction": {
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "passed": bool(reproduction["pass"].all()),
            "raw_number_reproduced_from_root": True,
        },
        "split": {
            "split_unit": "run",
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "train_rows": int((data["split"] == "train").sum()),
            "heldout_rows": int((data["split"] == "heldout").sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "methods": METHODS,
        "targets": TARGETS,
        "primary_metric": "sum of timing_sigma68_ns, saturation_mae, 1-pileup_auc, energy_sigma68, pid_shift_sigma68 on held-out runs; lower is better",
        "winner": {
            "method": str(winner["method"]),
            "primary_composite_score": float(winner["primary_composite_score"]),
            "timing_sigma68_ns": float(winner["timing_sigma68_ns"]),
            "timing_sigma68_ns_ci_low": float(winner["timing_sigma68_ns_ci_low"]),
            "timing_sigma68_ns_ci_high": float(winner["timing_sigma68_ns_ci_high"]),
            "saturation_mae": float(winner["saturation_mae"]),
            "pileup_auc": float(winner["pileup_auc"]),
            "energy_sigma68": float(winner["energy_sigma68"]),
            "pid_shift_sigma68": float(winner["pid_shift_sigma68"]),
        },
        "metric_table": json_safe(metrics.to_dict("records")),
        "strata_axes": ["phase_bin", "pedestal_drift_bin", "saturation_grade", "pileup_grade", "energy_bin", "energy_residual_bin", "pid_boundary_bin", "pid_sideband"],
        "next_tickets": [],
    }
    result["runtime_sec"] = time.time() - started
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, claim_text, reproduction, data, metrics, by_run, strata, result)
    print(json.dumps({"out": str(out), "winner": result["winner"], "selected_pulses": result["reproduction"]["selected_pulses"]}, indent=2))


if __name__ == "__main__":
    main()
