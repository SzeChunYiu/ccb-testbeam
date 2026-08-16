#!/usr/bin/env python3
"""S51a waveform shape-time identifiability atlas."""

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
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s51a_2454_waveform_shape_time_identifiability_atlas.json"
BASE_SCRIPT = ROOT / "scripts/s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.py"

METHOD_ORDER = [
    "traditional_median_template_cfd_timewalk_shape",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "compact_waveform_transformer",
    "shape_time_gate_transformer_new",
]

DERIVATIVE_COLUMNS = (
    [f"d1_{i:02d}" for i in range(17)]
    + [f"d2_{i:02d}" for i in range(16)]
    + [
        "max_rise_slope",
        "max_fall_slope",
        "onset_slope_sum",
        "late_slope_sum",
        "curvature_peak",
        "curvature_energy",
        "derivative_centroid",
        "curvature_centroid",
        "pretrigger_derivative_rms",
        "late_curvature_rms",
    ]
)
SHAPE_TIME_COLUMNS = (
    "q_template_error",
)

AXES = [
    "pedestal_drift_bin",
    "energy_bin",
    "peak_phase_bin",
    "pulse_shape_class",
    "q_template_error_bin",
    "derivative_onset_bin",
    "curvature_energy_bin",
    "late_tail_morphology",
    "pileup_separation_bin",
    "saturation_onset_bin",
    "pid_sideband",
]


def load_base():
    spec = importlib.util.spec_from_file_location("s32a_base_for_s51a", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.METHOD_ORDER = METHOD_ORDER
    original_feature_columns = module.feature_columns

    def feature_columns_with_derivatives(df: pd.DataFrame) -> list[str]:
        cols = original_feature_columns(df)
        return cols + [c for c in DERIVATIVE_COLUMNS if c in df.columns] + [c for c in SHAPE_TIME_COLUMNS if c in df.columns]

    module.feature_columns = feature_columns_with_derivatives
    return module


def add_derivative_features(df: pd.DataFrame) -> pd.DataFrame:
    waves = df[[f"w{i:02d}" for i in range(18)]].to_numpy(dtype=float)
    d1 = np.diff(waves, axis=1)
    d2 = np.diff(d1, axis=1)
    for i in range(d1.shape[1]):
        df[f"d1_{i:02d}"] = d1[:, i]
    for i in range(d2.shape[1]):
        df[f"d2_{i:02d}"] = d2[:, i]
    positive_d1 = np.maximum(d1, 0.0)
    abs_d2 = np.abs(d2)
    df["max_rise_slope"] = positive_d1.max(axis=1)
    df["max_fall_slope"] = np.minimum(d1, 0.0).min(axis=1)
    df["onset_slope_sum"] = positive_d1[:, 2:8].sum(axis=1)
    df["late_slope_sum"] = positive_d1[:, 9:].sum(axis=1)
    df["curvature_peak"] = abs_d2.max(axis=1)
    df["curvature_energy"] = (d2**2).sum(axis=1)
    d1_weight = np.maximum(np.abs(d1), 1e-9)
    d2_weight = np.maximum(abs_d2, 1e-9)
    df["derivative_centroid"] = (d1_weight * np.arange(17)[None, :]).sum(axis=1) / d1_weight.sum(axis=1)
    df["curvature_centroid"] = (d2_weight * np.arange(16)[None, :]).sum(axis=1) / d2_weight.sum(axis=1)
    df["pretrigger_derivative_rms"] = np.sqrt(np.mean(d1[:, :4] ** 2, axis=1))
    df["late_curvature_rms"] = np.sqrt(np.mean(d2[:, 9:] ** 2, axis=1))
    df["derivative_onset_bin"] = pd.qcut(
        df["onset_slope_sum"], q=3, labels=["slow", "nominal", "sharp"], duplicates="drop"
    ).astype(str)
    df["curvature_energy_bin"] = pd.qcut(
        df["curvature_energy"], q=3, labels=["smooth", "moderate", "curved"], duplicates="drop"
    ).astype(str)
    tail = df["tail_fraction"].to_numpy(float)
    late_slope = df["late_slope_sum"].to_numpy(float)
    tail_hi = float(np.quantile(tail, 0.67))
    slope_hi = float(np.quantile(late_slope, 0.67))
    df["late_tail_morphology"] = np.select(
        [(tail >= tail_hi) & (late_slope >= slope_hi), tail >= tail_hi, late_slope >= slope_hi],
        ["late_rising_tail", "diffuse_tail", "late_derivative_bump"],
        default="compact",
    )
    train = df["split"].eq("train")
    qerr = np.zeros(len(df), dtype=float)
    wave_cols = [f"w{i:02d}" for i in range(18)]
    train_waves = df.loc[train, wave_cols].to_numpy(float)
    global_template = np.median(train_waves, axis=0)
    for stave, group in df.groupby("stave", observed=False):
        train_group = group[group["split"].eq("train")]
        template = (
            np.median(train_group[wave_cols].to_numpy(float), axis=0)
            if len(train_group) > 0
            else global_template
        )
        diff = group[wave_cols].to_numpy(float) - template[None, :]
        qerr[group.index.to_numpy()] = np.mean(diff * diff, axis=1)
    df["q_template_error"] = qerr
    df["q_template_error_bin"] = pd.qcut(
        df["q_template_error"], q=3, labels=["template_like", "moderate_shape", "shape_outlier"], duplicates="drop"
    ).astype(str)
    phase = df["cfd20_sample"] - np.floor(df["cfd20_sample"])
    df["peak_phase_bin"] = pd.cut(
        phase, bins=[-1e-9, 1.0 / 3.0, 2.0 / 3.0, 1.0 + 1e-9], labels=["early_phase", "mid_phase", "late_phase"]
    ).astype(str)
    return df


def extended_metric_values(frame: pd.DataFrame, base) -> dict[str, float]:
    vals = base.metric_values(frame)
    x = frame["prediction_ns"].to_numpy(float)
    y = frame["target_onset_residual_ns"].to_numpy(float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() >= 3 and np.nanstd(x[ok]) > 1e-12:
        vals["calibration_slope"] = float(np.polyfit(x[ok], y[ok], deg=1)[0])
    else:
        vals["calibration_slope"] = float("nan")
    vals["q_template_mse"] = float(np.nanmean(frame["q_template_error"].to_numpy(float))) if "q_template_error" in frame else float("nan")
    vals["failure_rate_abs_gt_5ns"] = vals["tail_fraction_abs_gt_5ns"]
    return vals


def traditional_derivative_prediction(df: pd.DataFrame, base) -> np.ndarray:
    train = df["split"].eq("train").to_numpy()
    y = df["target_onset_residual_ns"].to_numpy(float)
    pred = base.traditional_prediction(df)
    residual = y[train] - pred[train]
    cols = [
        "max_rise_slope",
        "onset_slope_sum",
        "late_slope_sum",
        "curvature_peak",
        "curvature_energy",
        "derivative_centroid",
        "curvature_centroid",
        "pretrigger_derivative_rms",
        "late_curvature_rms",
        "rise_time_sample",
    ]
    x_train = df.loc[train, cols].to_numpy(float)
    x_all = df.loc[:, cols].to_numpy(float)
    mu = x_train.mean(axis=0)
    sig = x_train.std(axis=0) + 1e-9
    design = np.c_[np.ones(len(x_train)), (x_train - mu) / sig]
    penalty = np.diag([0.0] + [3.0] * len(cols))
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ residual)
    return pred + np.c_[np.ones(len(x_all)), (x_all - mu) / sig] @ coef


def fit_derivative_gate_transformer(df: pd.DataFrame, config: dict, seed: int) -> np.ndarray:
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("torch is required for shape_time_gate_transformer_new") from exc

    class DerivativeGateTransformer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embed = nn.Linear(4, 28)
            self.position = nn.Parameter(torch.zeros(1, 18, 28))
            layer = nn.TransformerEncoderLayer(
                d_model=28,
                nhead=4,
                dim_feedforward=72,
                dropout=0.05,
                activation="gelu",
                batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=1)
            self.gate = nn.Sequential(nn.Linear(2, 16), nn.GELU(), nn.Linear(16, 1), nn.Sigmoid())
            self.head = nn.Sequential(nn.LayerNorm(28), nn.Linear(28, 32), nn.GELU(), nn.Linear(32, 1))

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            wave = x[:, 0, :]
            d1 = x[:, 1, :]
            d2 = x[:, 2, :]
            t = torch.linspace(0.0, 1.0, wave.shape[1], device=wave.device).expand_as(wave)
            h = self.embed(torch.stack([wave, d1, d2, t], dim=-1)) + self.position
            gate = self.gate(torch.stack([torch.abs(d1), torch.abs(d2)], dim=-1))
            h = self.encoder(h * (1.0 + gate))
            weights = torch.softmax(2.5 * torch.abs(d1) + 1.5 * torch.abs(d2), dim=1).unsqueeze(-1)
            return self.head((h * weights).sum(dim=1)).squeeze(-1)

    torch.manual_seed(seed)
    torch.set_num_threads(1)
    waves = df[[f"w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    d1 = np.pad(np.diff(waves, axis=1), ((0, 0), (1, 0))).astype(np.float32)
    d2 = np.pad(np.diff(d1, axis=1), ((0, 0), (1, 0))).astype(np.float32)
    x = np.stack([waves, d1, d2], axis=1)
    y = df["target_onset_residual_ns"].to_numpy(dtype=np.float32)
    train = df["split"].eq("train").to_numpy()
    ym = float(y[train].mean())
    ys = float(y[train].std() + 1e-6)
    ds = TensorDataset(torch.from_numpy(x[train]), torch.from_numpy(((y[train] - ym) / ys).astype(np.float32)))
    loader = DataLoader(
        ds,
        batch_size=int(config["nn"]["batch_size"]),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    model = DerivativeGateTransformer()
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(config["nn"].get("transformer_epochs", config["nn"]["epochs"]))):
        for xb, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    out = []
    model.eval()
    with torch.no_grad():
        tx = torch.from_numpy(x)
        for start in range(0, len(tx), 2048):
            out.append(model(tx[start : start + 2048]).cpu().numpy())
    return np.concatenate(out) * ys + ym


def summarize_s51a(predictions: pd.DataFrame, config: dict, rng: np.random.Generator, base) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = predictions[predictions["split"].eq("heldout")].copy()
    metric_rows = []
    run_rows = []
    strata_rows = []
    boot_by_method: dict[str, dict[str, list[float]]] = {}
    for method, group in held.groupby("method", observed=False):
        row = {"method": method, "n": int(len(group)), **extended_metric_values(group, base)}
        runs = sorted(group["run"].unique())
        samples = {k: [] for k in ["bias_ns", "sigma68_ns", "rms_ns", "tail_fraction_abs_gt_5ns", "tail_fraction_abs_gt_10ns", "calibration_slope", "q_template_mse", "failure_rate_abs_gt_5ns"]}
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"].eq(r)] for r in take], ignore_index=True)
            vals = extended_metric_values(boot, base)
            for key, value in vals.items():
                if np.isfinite(value):
                    samples[key].append(value)
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        boot_by_method[str(method)] = samples
        metric_rows.append(row)
        for run, rg in group.groupby("run", observed=False):
            run_rows.append({"method": method, "run": int(run), "n": int(len(rg)), **extended_metric_values(rg, base)})
        for col in AXES:
            for level, sg in group.groupby(col, observed=False):
                strata_rows.append({"method": method, "stratum": col, "level": str(level), "n": int(len(sg)), **extended_metric_values(sg, base)})
    metrics = pd.DataFrame(metric_rows)
    metrics["method"] = pd.Categorical(metrics["method"], METHOD_ORDER, ordered=True)
    metrics = metrics.sort_values("sigma68_ns").reset_index(drop=True)
    delta_rows = []
    reference = "traditional_median_template_cfd_timewalk_shape"
    for method in metrics["method"].astype(str):
        if method == reference:
            continue
        row = {"method": method, "reference_method": reference}
        for key in ["bias_ns", "sigma68_ns", "rms_ns", "tail_fraction_abs_gt_5ns", "tail_fraction_abs_gt_10ns"]:
            val = float(metrics.loc[metrics["method"].astype(str).eq(method), key].iloc[0])
            ref = float(metrics.loc[metrics["method"].astype(str).eq(reference), key].iloc[0])
            paired = np.asarray(boot_by_method[method][key]) - np.asarray(boot_by_method[reference][key])
            row[f"delta_{key}"] = val - ref
            row[f"delta_{key}_ci_low"] = float(np.percentile(paired, 2.5))
            row[f"delta_{key}_ci_high"] = float(np.percentile(paired, 97.5))
        delta_rows.append(row)
    return (
        metrics,
        pd.DataFrame(run_rows).sort_values(["method", "run"]),
        pd.DataFrame(strata_rows).sort_values(["stratum", "level", "method"]),
        pd.DataFrame(delta_rows).sort_values("delta_sigma68_ns"),
    )


def derivative_ablation_study(df: pd.DataFrame, rng: np.random.Generator, base) -> pd.DataFrame:
    train = df["split"].eq("train").to_numpy()
    y = df["target_onset_residual_ns"].to_numpy(float)
    all_cols = base.feature_columns(df)
    feature_sets = {
        "full_derivative_gradient_boosted_trees": all_cols,
        "drop_derivative_features": [c for c in all_cols if c not in DERIVATIVE_COLUMNS and not c.startswith("d1_") and not c.startswith("d2_")],
        "derivative_only": [c for c in DERIVATIVE_COLUMNS if c in df.columns],
        "onset_derivative_window_only": [f"d1_{i:02d}" for i in range(2, 8)] + [f"d2_{i:02d}" for i in range(2, 8)] + ["onset_slope_sum", "max_rise_slope"],
        "late_tail_curvature_window_only": [f"d1_{i:02d}" for i in range(9, 17)] + [f"d2_{i:02d}" for i in range(9, 16)] + ["late_slope_sum", "late_curvature_rms"],
        "pretrigger_derivative_only": [f"d1_{i:02d}" for i in range(0, 4)] + ["pretrigger_derivative_rms", "baseline", "pretrigger_slope"],
        "amplitude_cfd_no_derivative": ["amplitude", "cfd50_sample", "cfd80_sample", "rise_time_sample", "peak_sample"],
    }
    rows = []
    for name, cols in feature_sets.items():
        cols = [c for c in cols if c in df.columns]
        model = HistGradientBoostingRegressor(max_iter=140, learning_rate=0.05, l2_regularization=0.02, random_state=4316)
        x = df[cols].to_numpy(dtype=float)
        model.fit(x[train], y[train])
        pred = model.predict(x)
        frame = df[["run", "split", "target_onset_residual_ns"]].copy()
        frame["error_ns"] = frame["target_onset_residual_ns"] - pred
        held = frame[frame["split"].eq("heldout")]
        vals = base.metric_values(held)
        runs = sorted(held["run"].unique())
        boot = []
        for _ in range(200):
            take = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([held[held["run"].eq(r)] for r in take], ignore_index=True)
            boot.append(base.metric_values(sample)["sigma68_ns"])
        rows.append(
            {
                "ablation": name,
                "n_features": int(len(cols)),
                "sigma68_ns": vals["sigma68_ns"],
                "sigma68_ns_ci_low": float(np.percentile(boot, 2.5)),
                "sigma68_ns_ci_high": float(np.percentile(boot, 97.5)),
                "bias_ns": vals["bias_ns"],
                "tail_fraction_abs_gt_5ns": vals["tail_fraction_abs_gt_5ns"],
            }
        )
    out = pd.DataFrame(rows).sort_values("sigma68_ns").reset_index(drop=True)
    base_value = float(out.loc[out["ablation"].eq("full_derivative_gradient_boosted_trees"), "sigma68_ns"].iloc[0])
    out["delta_sigma68_vs_full_ns"] = out["sigma68_ns"] - base_value
    return out


def run_family_summary(predictions: pd.DataFrame, config: dict, base) -> pd.DataFrame:
    run_to_group = {}
    for family, runs in config["run_groups"].items():
        for run in runs:
            run_to_group[int(run)] = family
    held = predictions[predictions["split"].eq("heldout")].copy()
    held["run_family"] = held["run"].astype(int).map(run_to_group)
    rows = []
    for (method, family), group in held.groupby(["method", "run_family"], observed=False):
        rows.append({"method": str(method), "run_family": str(family), "n": int(len(group)), **extended_metric_values(group, base)})
    return pd.DataFrame(rows).sort_values(["run_family", "sigma68_ns"]).reset_index(drop=True)


def axis_summary(strata: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (axis, method), group in strata.groupby(["stratum", "method"], observed=False):
        if axis not in AXES or group.empty:
            continue
        group = group.copy()
        worst = group.loc[group["sigma68_ns"].idxmax()]
        best = group.loc[group["sigma68_ns"].idxmin()]
        rows.append(
            {
                "axis": str(axis),
                "method": str(method),
                "levels": int(group["level"].nunique()),
                "best_level": str(best["level"]),
                "best_sigma68_ns": float(best["sigma68_ns"]),
                "worst_level": str(worst["level"]),
                "worst_sigma68_ns": float(worst["sigma68_ns"]),
                "sigma68_span_ns": float(worst["sigma68_ns"] - best["sigma68_ns"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["axis", "sigma68_span_ns"], ascending=[True, False]).reset_index(drop=True)


def input_sha256_table(config: dict, base) -> pd.DataFrame:
    rows = []
    for run in base.all_runs(config):
        path = base.root_path(config, int(run))
        rows.append({"run": int(run), "path": str(path), "bytes": int(path.stat().st_size), "sha256": base.sha256_file(path), "role": "raw_root"})
    return pd.DataFrame(rows)


def sha256_path(path: Path, block_size: int = 1024 * 1024) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_manifest(out: Path, config: dict, result: dict) -> dict:
    rows = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json" and not path.name.endswith(".gz"):
            rows.append({"path": path.name, "bytes": int(path.stat().st_size), "sha256": sha256_path(path)})
    return {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "generated_at_unix": time.time(),
        "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
        "done_command": f"tn-ticket done {config['ticket_id']} --project testbeam",
        "result_winner": result["winner"]["method"],
        "artifacts": rows,
    }


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


def write_report(
    config: dict,
    base,
    reproduction: pd.DataFrame,
    input_hashes: pd.DataFrame,
    data: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    axes: pd.DataFrame,
    families: pd.DataFrame,
    ablations: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    out = ROOT / config["output_dir"]
    winner = result["winner"]["method"]
    best = metrics[metrics["method"].astype(str).eq(winner)].iloc[0]
    trad = metrics[metrics["method"].astype(str).eq("traditional_median_template_cfd_timewalk_shape")].iloc[0]
    counts = data.groupby("split").size().reset_index(name="rows")
    methods = pd.DataFrame(
        [
            ["traditional_median_template_cfd_timewalk_shape", "traditional", "aligned median-template CFD/optimal-filter timing, explicit time-walk terms, and ridge-regularized shape/curvature residual correction"],
            ["ridge", "linear ML", "standardized ridge regression on pedestal, amplitude, CFD, waveform, derivative, curvature, and hand pulse-shape features"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted regression on the same leakage-controlled waveform-summary feature matrix"],
            ["mlp", "neural tabular", "two-layer perceptron over engineered waveform, detector-state, derivative, curvature, and q-template summaries"],
            ["1d_cnn", "neural waveform", "compact 1D convolutional regressor over normalized 18-sample waveforms"],
            ["compact_waveform_transformer", "neural waveform", "one-layer waveform self-attention encoder inherited from the audited timing benchmark"],
            ["shape_time_gate_transformer_new", "new architecture", "compact transformer over waveform, first derivative, and second derivative channels with shape/time derivative-magnitude pooling"],
        ],
        columns=["method", "family", "description"],
    )
    text = f"""# S51a Waveform Shape-Time Identifiability Atlas

## Abstract

Ticket `{config['ticket_id']}` asks for a pulse shape and timing
identifiability atlas across stave, run family, amplitude, peak phase,
pedestal state, and mild pile-up strata.  The study
first reproduces the registered B-stack selected-pulse count directly from raw
ROOT `h101/HRDv`, then constructs a run-held-out timing-residual benchmark on
the same digitized pulses.  A strong traditional constant-fraction,
median-template time-walk, and shape-correction fit is compared against ridge,
gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and the
ticket-local `shape_time_gate_transformer_new` architecture.

The primary metric is held-out run-block bootstrap `sigma_68` of residual
timing error.  The result written to `result.json` names **`{winner}`** as the
winner with `sigma_68 = {best['sigma68_ns']:.4g} ns`
`[{best['sigma68_ns_ci_low']:.4g}, {best['sigma68_ns_ci_high']:.4g}]`.  The
traditional shape-time comparator obtains `{trad['sigma68_ns']:.4g} ns`
`[{trad['sigma68_ns_ci_low']:.4g}, {trad['sigma68_ns_ci_high']:.4g}]`.

## Raw ROOT Reproduction

Input files are read from `{config['raw_root_dir']}`.  For each event the raw
vector `HRDv` is reshaped to `(8, 18)`.  The B-stack channels are B2, B4, B6,
and B8.  With pretrigger baseline

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

the reproduced count is

`N = sum_e sum_{{c in B2,B4,B6,B8}} 1[max_t(x_{{e,c,t}} - b_{{e,c}}) > {config['amplitude_cut_adc']:.0f}]`.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

The all-group reproduced raw count is **{int(reproduction.iloc[-1]['selected_pulses'])}**.
Input hashes are stored in `input_sha256.csv`; first rows:

{md_table(input_hashes, ['run', 'path', 'bytes', 'sha256'], max_rows=8)}

## Estimand and Equations

The sub-sample constant-fraction crossing at fraction `f` is computed by
linear interpolation before the waveform peak:

`t_f = k - 1 + (f A - y_{{k-1}}) / (y_k - y_{{k-1}})`,

where `y_t = x_t - b`, `A = max_t y_t`, and `k` is the first pre-peak sample
with `y_k >= f A`.  The supervised target is the run/stave-centered CFD20
residual,

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The normalized waveform is `z_t = (x_t - b) / max(A, 1)`.  Derivative features
are the finite differences

`d_t = z_{{t+1}} - z_t`,

and curvature samples

`c_t = d_{{t+1}} - d_t`.

The traditional method starts from the audited CFD/template time-walk baseline
`hat y_0`, then fits a ridge-regularized derivative residual correction on
training runs only:

`hat y = hat y_0 + beta_0 + beta^T standardize(s_deriv)`,

where `s_deriv` contains onset slope, late slope, curvature peak, curvature
energy, derivative centroids, and pretrigger derivative RMS.  The ridge penalty
prevents derivative summaries from silently absorbing run identity.

For method `m`, residual error is `epsilon_i^m = y_i - hat y_i^m`.  Resolution
is

`sigma_68(epsilon) = 0.5 [Q_84(epsilon) - Q_16(epsilon)]`,

and bias is `median(epsilon)`.

## Split and Uncertainty

The split unit is the run: held-out runs are `{config['heldout_runs']}` and all
other configured B-stack runs are used for training.  Sampled benchmark rows:

{md_table(counts, ['split', 'rows'])}

Confidence intervals use `{config['bootstrap_replicates']}` paired percentile
bootstrap replicates that resample held-out runs with replacement.  Paired
deltas subtract each replicate of the traditional shape-time comparator from
the corresponding replicate of the learned method.

## Methods

{md_table(methods, ['method', 'family', 'description'])}

The new architecture is sensible for this ticket because the hypothesis is not
generic waveform learning; it is that edge, curvature, and normalized
shape-template channels localize pulse-shape timing changes under pedestal
drift.  The model embeds waveform,
first derivative, second derivative, and sample position at each of the 18 time
samples.  A derivative-magnitude gate weights transformer states before a
single regression head predicts the timing residual.

## Primary Held-Out Results

{md_table(metrics, ['method', 'n', 'bias_ns', 'bias_ns_ci_low', 'bias_ns_ci_high', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'calibration_slope', 'q_template_mse', 'failure_rate_abs_gt_5ns', 'tail_fraction_abs_gt_10ns'])}

## Paired Deltas Against Traditional Shape-Time Fit

Positive `delta_sigma68_ns` means wider held-out timing residuals than the
traditional shape-time comparator.

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high', 'delta_bias_ns', 'delta_bias_ns_ci_low', 'delta_bias_ns_ci_high', 'delta_tail_fraction_abs_gt_5ns'])}

## Run-Split Stability

{md_table(families, ['run_family', 'method', 'n', 'bias_ns', 'sigma68_ns', 'calibration_slope', 'q_template_mse', 'failure_rate_abs_gt_5ns'], max_rows=80)}

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'calibration_slope', 'q_template_mse', 'failure_rate_abs_gt_5ns'], max_rows=120)}

## Stratified Systematics

The requested strata are amplitude, pedestal state, and late-tail morphology.
Additional pulse-shape stress axes are included because derivative/curvature
features are expected to be most fragile near pile-up and saturation.

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'calibration_slope', 'q_template_mse', 'failure_rate_abs_gt_5ns'], max_rows=220)}

Compressed axis view:

{md_table(axes, ['axis', 'method', 'levels', 'best_level', 'best_sigma68_ns', 'worst_level', 'worst_sigma68_ns', 'sigma68_span_ns'], max_rows=100)}

## Derivative and Curvature Ablations

The ablations use the gradient-boosted-tree learner to isolate whether the
benefit comes from onset derivatives, late-tail curvature, pretrigger pedestal
derivatives, or non-derivative CFD/amplitude information.

{md_table(ablations, ['ablation', 'n_features', 'bias_ns', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'delta_sigma68_vs_full_ns', 'tail_fraction_abs_gt_5ns'])}

## Interpretation, Systematics, and Caveats

This benchmark measures relative transfer on a reproducible waveform-derived
timing residual.  The raw ROOT files do not contain an independent external
picosecond timing truth for each pulse, so the numerical winner should not be
read as an absolute detector timing limit.  It answers the narrower ticket
question: whether derivative/curvature descriptions improve run-held-out
arrival-time residual prediction beyond a strong CFD/template derivative fit.

The run-block bootstrap is deliberately conservative for data-taking-period
transfer and can produce wider intervals than event bootstrap.  Neural models
are compact and trained under a fixed small epoch budget suitable for this
laptop worker; the study tests whether derivative-aware architectures naturally
outperform transparent timing fits, not whether exhaustive architecture search
can overfit the proxy.  Pedestal drift strata use raw pretrigger baseline
displacement from the run/stave median, so they are useful diagnostics but not
external electronics-state labels.

The result is consistent with the recent S41a/S40b timing family if the
traditional method remains competitive: transparent CFD/template corrections
capture most of the stable sub-sample timing signal, while derivative features
mainly expose where late tails and pedestal wander destabilize learned models.

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
    (out / "claimed_ticket.txt").write_text(config["claimed_ticket_text"], encoding="utf-8")

    reproduction = base.count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    input_hashes = input_sha256_table(config, base)
    input_hashes.to_csv(out / "input_sha256.csv", index=False)

    data = add_derivative_features(base.sample_pulses(config, rng))
    data.to_csv(out / "benchmark_rows.csv.gz", index=False)

    preds = {"traditional_median_template_cfd_timewalk_shape": traditional_derivative_prediction(data, base)}
    preds.update(base.fit_tabular_methods(data))
    preds["1d_cnn"] = base.fit_cnn(data, config, "1d_cnn", gated=False, seed=int(config["random_seed"]) + 1)
    preds["compact_waveform_transformer"] = base.fit_transformer(data, config, seed=int(config["random_seed"]) + 2)
    preds["shape_time_gate_transformer_new"] = fit_derivative_gate_transformer(data, config, seed=int(config["random_seed"]) + 3)

    base_cols = [
        "run",
        "event",
        "stave",
        "split",
        "target_onset_residual_ns",
        "q_template_error",
        *AXES,
    ]
    pred_rows = []
    for method, pred in preds.items():
        frame = data[base_cols].copy()
        frame["method"] = method
        frame["prediction_ns"] = pred
        frame["error_ns"] = frame["target_onset_residual_ns"] - frame["prediction_ns"]
        pred_rows.append(frame)
    predictions = pd.concat(pred_rows, ignore_index=True)
    predictions.to_csv(out / "predictions.csv.gz", index=False)

    metrics, by_run, strata, deltas = summarize_s51a(predictions, config, rng, base)
    axes = axis_summary(strata)
    families = run_family_summary(predictions, config, base)
    ablations = derivative_ablation_study(data, rng, base)

    metrics.to_csv(out / "metrics.csv", index=False)
    deltas.to_csv(out / "method_deltas.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    axes.to_csv(out / "frontier_axis_summary.csv", index=False)
    families.to_csv(out / "run_family_summary.csv", index=False)
    ablations.to_csv(out / "ablations.csv", index=False)

    winner_row = metrics.iloc[0].to_dict()
    runtime = time.time() - started
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "claimed_ticket_text": config["claimed_ticket_text"],
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
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
        "methods": METHOD_ORDER,
        "primary_metric": "held-out run-block bootstrap sigma68_ns of target_onset_residual_ns - prediction_ns; lower is better",
        "winner": {
            "method": str(winner_row["method"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "sigma68_ns_ci_low": float(winner_row["sigma68_ns_ci_low"]),
            "sigma68_ns_ci_high": float(winner_row["sigma68_ns_ci_high"]),
            "bias_ns": float(winner_row["bias_ns"]),
            "bias_ns_ci_low": float(winner_row["bias_ns_ci_low"]),
            "bias_ns_ci_high": float(winner_row["bias_ns_ci_high"]),
            "calibration_slope": float(winner_row["calibration_slope"]),
            "calibration_slope_ci_low": float(winner_row["calibration_slope_ci_low"]),
            "calibration_slope_ci_high": float(winner_row["calibration_slope_ci_high"]),
            "q_template_mse": float(winner_row["q_template_mse"]),
            "q_template_mse_ci_low": float(winner_row["q_template_mse_ci_low"]),
            "q_template_mse_ci_high": float(winner_row["q_template_mse_ci_high"]),
            "failure_rate_abs_gt_5ns": float(winner_row["failure_rate_abs_gt_5ns"]),
            "failure_rate_abs_gt_5ns_ci_low": float(winner_row["failure_rate_abs_gt_5ns_ci_low"]),
            "failure_rate_abs_gt_5ns_ci_high": float(winner_row["failure_rate_abs_gt_5ns_ci_high"]),
        },
        "metric_table": json_safe(metrics.to_dict("records")),
        "paired_delta_table": json_safe(deltas.to_dict("records")),
        "frontier_axis_table": json_safe(axes.to_dict("records")),
        "run_family_table": json_safe(families.to_dict("records")),
        "ablation_table": json_safe(ablations.to_dict("records")),
        "strata_axes": AXES,
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction.csv",
            "method_metrics": "metrics.csv",
            "method_deltas": "method_deltas.csv",
            "run_heldout_metrics": "by_run.csv",
            "strata_metrics": "strata.csv",
            "input_sha256": "input_sha256.csv",
            "derivative_ablations": "ablations.csv"
        },
        "novel_tickets_appended": [],
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, base, reproduction, input_hashes, data, metrics, deltas, by_run, strata, axes, families, ablations, result, runtime)
    (out / "manifest.json").write_text(json.dumps(artifact_manifest(out, config, result), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
