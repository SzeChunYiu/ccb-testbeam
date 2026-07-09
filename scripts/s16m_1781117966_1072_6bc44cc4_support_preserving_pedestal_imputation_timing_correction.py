#!/usr/bin/env python3
"""S16m support-preserving timing correction benchmark."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/testbeam-mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.set_num_threads(2)
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


CONFIG_DEFAULT = "configs/s16m_1781117966_1072_6bc44cc4_support_preserving_pedestal_imputation_timing_correction.json"
S16L_PATH = "scripts/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.py"
PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
METHODS = [
    "uncorrected",
    "traditional_binned_median",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "one_dimensional_cnn",
    "nuisance_gated_pair_cnn",
]


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16L = load_module("s16l_helpers_for_s16m", S16L_PATH)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def md_table(df: pd.DataFrame, columns: Sequence[str]) -> str:
    if df.empty:
        return "_No rows._"
    return df.loc[:, list(columns)].to_markdown(index=False)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def metric_dict(residual: np.ndarray) -> Dict[str, float]:
    residual = np.asarray(residual, dtype=float)
    residual = residual[np.isfinite(residual)]
    return {
        "n_pairs": int(len(residual)),
        "sigma68_ns": sigma68(residual),
        "rms_ns": float(np.sqrt(np.mean(residual**2))) if len(residual) else float("nan"),
        "bias_ns": float(np.mean(residual)) if len(residual) else float("nan"),
        "tail_abs_gt_0p5_ns": float(np.mean(np.abs(residual) > 0.5)) if len(residual) else float("nan"),
        "tail_abs_gt_1p0_ns": float(np.mean(np.abs(residual) > 1.0)) if len(residual) else float("nan"),
    }


def input_hashes(config: dict) -> pd.DataFrame:
    rows = []
    for run in S16L.configured_runs(config):
        path = S16L.raw_file(config, run)
        rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return pd.DataFrame(rows)


def nuisance_features(meta: pd.DataFrame, waves: np.ndarray, runs: Sequence[int]) -> pd.DataFrame:
    mask = meta["run"].isin([int(r) for r in runs]).to_numpy()
    pulse_idx = np.where(mask)[0].astype(int)
    full_idx = np.repeat(pulse_idx, 4)
    targets = np.tile(np.arange(4, dtype=int), len(pulse_idx))
    frame = S16L.target_frame(meta, waves, full_idx, targets)
    for name in ["mean3", "median3", "line3"]:
        frame[f"{name}_err_adc"] = frame[f"{name}_adc"] - frame["target_adc"]
        frame[f"{name}_abs_err_adc"] = frame[f"{name}_err_adc"].abs()
    frame["target_excluded_spread_adc"] = frame[["mean3_adc", "median3_adc", "line3_adc"]].max(axis=1) - frame[
        ["mean3_adc", "median3_adc", "line3_adc"]
    ].min(axis=1)
    grouped = frame.groupby("pulse_index")
    out = grouped.agg(
        mean3_err_mean_adc=("mean3_err_adc", "mean"),
        mean3_abs_err_mean_adc=("mean3_abs_err_adc", "mean"),
        mean3_abs_err_max_adc=("mean3_abs_err_adc", "max"),
        median3_err_mean_adc=("median3_err_adc", "mean"),
        median3_abs_err_mean_adc=("median3_abs_err_adc", "mean"),
        median3_abs_err_max_adc=("median3_abs_err_adc", "max"),
        line3_err_mean_adc=("line3_err_adc", "mean"),
        line3_abs_err_mean_adc=("line3_abs_err_adc", "mean"),
        line3_abs_err_max_adc=("line3_abs_err_adc", "max"),
        target_excluded_spread_mean_adc=("target_excluded_spread_adc", "mean"),
        target_adc_std_adc=("target_adc", "std"),
        visible_range_mean_adc=("pre_range3_adc", "mean"),
    ).reset_index()
    return out.fillna(0.0)


def build_pairs(meta: pd.DataFrame, nuisance: pd.DataFrame, config: dict) -> pd.DataFrame:
    pulse = meta[meta["run"].isin(config["heldout_runs"])].copy()
    pulse["row_index"] = np.arange(len(meta), dtype=int)[meta["run"].isin(config["heldout_runs"]).to_numpy()]
    pulse = pulse.merge(nuisance, on="pulse_index", how="left")
    for col in nuisance.columns:
        if col != "pulse_index":
            pulse[col] = pulse[col].fillna(0.0)
    keep = ["run", "event_id", "stave", "row_index", "pulse_index", "ref_t_cfd20_ns", "ref_amp_adc", "ref_peak_sample", "adaptive_lowering_adc", "pre_ptp4_adc", "pre_rms4_adc"] + [
        c for c in nuisance.columns if c != "pulse_index"
    ]
    downstream = set(config["downstream_staves"])
    pulse = pulse[pulse["stave"].isin(downstream)][keep]
    wide = pulse.pivot_table(index=["run", "event_id"], columns="stave", values=[c for c in keep if c not in ("run", "event_id", "stave")], aggfunc="first")
    positions = {"B2": 0.0, "B4": 2.0, "B6": 4.0, "B8": 6.0}
    pair_rows: List[pd.DataFrame] = []

    def val(var: str, stave: str) -> pd.Series:
        key = (var, stave)
        if key in wide.columns:
            return wide[key]
        return pd.Series(np.nan, index=wide.index)

    for code, (a, b) in enumerate(PAIRS):
        ta, tb = val("ref_t_cfd20_ns", a), val("ref_t_cfd20_ns", b)
        loc = ta.notna() & tb.notna()
        if not loc.any():
            continue
        row = pd.DataFrame(index=wide.index[loc])
        row["run"] = [idx[0] for idx in row.index]
        row["event_id"] = [idx[1] for idx in row.index]
        row["pair"] = f"{a}-{b}"
        row["pair_code"] = int(code)
        row["row_index_a"] = val("row_index", a)[loc].astype(int).to_numpy()
        row["row_index_b"] = val("row_index", b)[loc].astype(int).to_numpy()
        row["pulse_index_a"] = val("pulse_index", a)[loc].astype(int).to_numpy()
        row["pulse_index_b"] = val("pulse_index", b)[loc].astype(int).to_numpy()
        tof = (positions[a] - positions[b]) * float(config["tof_per_cm_ns"])
        row["raw_residual_ns"] = (ta[loc] - tb[loc]).to_numpy(dtype=float) - tof
        for suffix, stave in [("a", a), ("b", b)]:
            row[f"log_amp_{suffix}"] = np.log1p(val("ref_amp_adc", stave)[loc].to_numpy(dtype=float))
            row[f"peak_{suffix}"] = val("ref_peak_sample", stave)[loc].to_numpy(dtype=float)
            row[f"pre_ptp4_{suffix}"] = val("pre_ptp4_adc", stave)[loc].to_numpy(dtype=float)
            row[f"pre_rms4_{suffix}"] = val("pre_rms4_adc", stave)[loc].to_numpy(dtype=float)
            row[f"adaptive_lowering_{suffix}"] = val("adaptive_lowering_adc", stave)[loc].to_numpy(dtype=float)
            for ncol in [c for c in nuisance.columns if c != "pulse_index"]:
                row[f"{ncol}_{suffix}"] = val(ncol, stave)[loc].to_numpy(dtype=float)
        row["abs_log_amp_ratio"] = np.abs(row["log_amp_a"] - row["log_amp_b"])
        row["log_amp_sum"] = row["log_amp_a"] + row["log_amp_b"]
        row["delta_peak"] = row["peak_a"] - row["peak_b"]
        row["pre_ptp4_max"] = np.maximum(row["pre_ptp4_a"], row["pre_ptp4_b"])
        row["pre_rms4_max"] = np.maximum(row["pre_rms4_a"], row["pre_rms4_b"])
        row["nuisance_abs_max_adc"] = np.maximum(row["line3_abs_err_max_adc_a"], row["line3_abs_err_max_adc_b"])
        row["nuisance_abs_mean_adc"] = 0.5 * (row["line3_abs_err_mean_adc_a"] + row["line3_abs_err_mean_adc_b"])
        row["nuisance_signed_diff_adc"] = row["line3_err_mean_adc_a"] - row["line3_err_mean_adc_b"]
        pair_rows.append(row.reset_index(drop=True))
    out = pd.concat(pair_rows, ignore_index=True)
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=["raw_residual_ns"]).reset_index(drop=True)
    return out


def feature_columns(df: pd.DataFrame) -> List[str]:
    excluded = {"run", "event_id", "pair", "row_index_a", "row_index_b", "pulse_index_a", "pulse_index_b", "raw_residual_ns"}
    return [c for c in df.columns if c not in excluded and pd.api.types.is_numeric_dtype(df[c])]


def clean_xy(train: pd.DataFrame, test: pd.DataFrame, cols: Sequence[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train_x = train.loc[:, cols].replace([np.inf, -np.inf], np.nan).copy()
    test_x = test.loc[:, cols].replace([np.inf, -np.inf], np.nan).copy()
    med = train_x.median(axis=0).fillna(0.0)
    return train_x.fillna(med), test_x.fillna(med)


class TraditionalBinnedMedian:
    def __init__(self):
        self.edges: Dict[str, np.ndarray] = {}
        self.tables: Dict[Tuple[str, ...], pd.Series] = {}
        self.global_median = 0.0

    def fit(self, df: pd.DataFrame):
        train = df.copy()
        for col in ["abs_log_amp_ratio", "pre_ptp4_max", "nuisance_abs_max_adc"]:
            qs = np.unique(np.nanquantile(train[col].to_numpy(dtype=float), np.linspace(0, 1, 7)))
            self.edges[col] = qs[1:-1] if len(qs) > 2 else np.asarray([], dtype=float)
            train[col + "_bin"] = np.digitize(train[col].to_numpy(dtype=float), self.edges[col])
        self.global_median = float(np.median(train["raw_residual_ns"]))
        for keys in [
            ("pair", "abs_log_amp_ratio_bin", "pre_ptp4_max_bin", "nuisance_abs_max_adc_bin"),
            ("pair", "abs_log_amp_ratio_bin", "nuisance_abs_max_adc_bin"),
            ("pair", "abs_log_amp_ratio_bin"),
            ("pair",),
        ]:
            self.tables[keys] = train.groupby(list(keys))["raw_residual_ns"].median()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        test = df.copy()
        for col, edges in self.edges.items():
            test[col + "_bin"] = np.digitize(test[col].to_numpy(dtype=float), edges)
        out = np.full(len(test), self.global_median, dtype=float)
        unresolved = np.ones(len(test), dtype=bool)
        for keys, table in self.tables.items():
            if not unresolved.any():
                break
            lookup = test.loc[unresolved, list(keys)].apply(lambda r: tuple(r), axis=1)
            pred = lookup.map(table)
            loc = pred.notna().to_numpy()
            idx = np.where(unresolved)[0][loc]
            out[idx] = pred.loc[pred.notna()].to_numpy(dtype=float)
            unresolved[idx] = False
        return out


class PairCnn(nn.Module):
    def __init__(self, n_tab: int, gated: bool, gate_index: Sequence[int]):
        super().__init__()
        self.gated = gated
        self.gate_index = list(gate_index)
        self.conv = nn.Sequential(
            nn.Conv1d(2, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        if gated:
            self.gate = nn.Sequential(nn.Linear(max(len(self.gate_index), 1), 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 64), nn.ReLU(), nn.Dropout(0.05), nn.Linear(64, 1))

    def forward(self, seq, tab):
        z = self.conv(seq).squeeze(-1)
        if self.gated:
            if self.gate_index:
                gate_in = tab[:, self.gate_index]
            else:
                gate_in = tab[:, :1] * 0
            z = z * self.gate(gate_in)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


def fit_torch_model(train: pd.DataFrame, test: pd.DataFrame, waves: np.ndarray, cols: Sequence[str], config: dict, gated: bool) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is required for CNN benchmarks")
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + (17 if gated else 11) + int(test["run"].iloc[0]))
    if len(train) > int(config["models"]["max_train_pair_rows"]):
        train = train.iloc[rng.choice(len(train), int(config["models"]["max_train_pair_rows"]), replace=False)].copy()
    xtr, xte = clean_xy(train, test, cols)
    sx = StandardScaler()
    tab_tr = sx.fit_transform(xtr).astype(np.float32)
    tab_te = sx.transform(xte).astype(np.float32)
    y = train["raw_residual_ns"].to_numpy(dtype=np.float32)
    y_mean, y_std = float(y.mean()), float(y.std() if y.std() > 1e-6 else 1.0)
    y_tr = ((y - y_mean) / y_std).astype(np.float32)

    def seq_for(frame: pd.DataFrame) -> np.ndarray:
        a = waves[frame["row_index_a"].to_numpy(dtype=int)].astype(np.float32)
        b = waves[frame["row_index_b"].to_numpy(dtype=int)].astype(np.float32)
        a = a - np.median(a[:, :4], axis=1)[:, None]
        b = b - np.median(b[:, :4], axis=1)[:, None]
        seq = np.stack([a, b], axis=1)
        return seq

    seq_tr = seq_for(train)
    seq_te = seq_for(test)
    seq_mean = seq_tr.mean(axis=(0, 2), keepdims=True)
    seq_std = seq_tr.std(axis=(0, 2), keepdims=True)
    seq_std[seq_std < 1e-6] = 1.0
    seq_tr = ((seq_tr - seq_mean) / seq_std).astype(np.float32)
    seq_te = ((seq_te - seq_mean) / seq_std).astype(np.float32)
    gate_index = [i for i, c in enumerate(cols) if "nuisance" in c or "line3_" in c]
    model = PairCnn(tab_tr.shape[1], gated=gated, gate_index=gate_index)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_learning_rate"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    ds = TensorDataset(torch.from_numpy(seq_tr), torch.from_numpy(tab_tr), torch.from_numpy(y_tr))
    loader = DataLoader(ds, batch_size=int(config["models"]["torch_batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["models"]["torch_epochs"])):
        for seq_b, tab_b, y_b in loader:
            opt.zero_grad()
            loss = loss_fn(model(seq_b, tab_b), y_b)
            loss.backward()
            opt.step()
    model.eval()
    preds: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(seq_te), 4096):
            p = model(torch.from_numpy(seq_te[start : start + 4096]), torch.from_numpy(tab_te[start : start + 4096]))
            preds.append(p.numpy())
    return np.concatenate(preds) * y_std + y_mean


def fit_fold_models(pairs: pd.DataFrame, waves: np.ndarray, config: dict) -> pd.DataFrame:
    cols = feature_columns(pairs)
    scored = []
    for run in sorted(pairs["run"].unique()):
        train = pairs[pairs["run"] != run].reset_index(drop=True)
        test = pairs[pairs["run"] == run].reset_index(drop=True)
        fold = test[["run", "event_id", "pair", "raw_residual_ns"]].copy()
        fold["method"] = "uncorrected"
        fold["predicted_correction_ns"] = 0.0
        fold["corrected_residual_ns"] = fold["raw_residual_ns"]
        scored.append(fold)

        trad = TraditionalBinnedMedian().fit(train)
        pred = trad.predict(test)
        scored.append(score_frame(test, "traditional_binned_median", pred))

        xtr, xte = clean_xy(train, test, cols)
        y = train["raw_residual_ns"].to_numpy(dtype=float)
        ridge = make_pipeline(StandardScaler(), Ridge(alpha=float(config["models"]["ridge_alpha"])))
        ridge.fit(xtr, y)
        scored.append(score_frame(test, "ridge", ridge.predict(xte)))

        hgb = HistGradientBoostingRegressor(
            max_iter=int(config["models"]["hgb_max_iter"]),
            learning_rate=float(config["models"]["hgb_learning_rate"]),
            max_leaf_nodes=int(config["models"]["hgb_max_leaf_nodes"]),
            l2_regularization=0.01,
            random_state=int(config["models"]["random_seed"]) + int(run),
        )
        hgb.fit(xtr, y)
        scored.append(score_frame(test, "gradient_boosted_trees", hgb.predict(xte)))

        mlp = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=tuple(config["models"]["mlp_hidden_layer_sizes"]),
                alpha=float(config["models"]["mlp_alpha"]),
                max_iter=int(config["models"]["mlp_max_iter"]),
                early_stopping=True,
                random_state=int(config["models"]["random_seed"]) + int(run),
            ),
        )
        mlp.fit(xtr, y)
        scored.append(score_frame(test, "mlp", mlp.predict(xte)))

        scored.append(score_frame(test, "one_dimensional_cnn", fit_torch_model(train, test, waves, cols, config, gated=False)))
        scored.append(score_frame(test, "nuisance_gated_pair_cnn", fit_torch_model(train, test, waves, cols, config, gated=True)))
    return pd.concat(scored, ignore_index=True)


def score_frame(test: pd.DataFrame, method: str, pred: np.ndarray) -> pd.DataFrame:
    out = test[["run", "event_id", "pair", "raw_residual_ns"]].copy()
    out["method"] = method
    out["predicted_correction_ns"] = np.asarray(pred, dtype=float)
    out["corrected_residual_ns"] = out["raw_residual_ns"] - out["predicted_correction_ns"]
    return out


def summarize_metrics(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in scored.groupby("method"):
        rows.append({"method": method, **metric_dict(group["corrected_residual_ns"].to_numpy(dtype=float))})
    order = {m: i for i, m in enumerate(METHODS)}
    return pd.DataFrame(rows).sort_values("method", key=lambda s: s.map(order).fillna(99)).reset_index(drop=True)


def per_run_metrics(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, run), group in scored.groupby(["method", "run"]):
        rows.append({"method": method, "run": int(run), **metric_dict(group["corrected_residual_ns"].to_numpy(dtype=float))})
    return pd.DataFrame(rows).sort_values(["method", "run"]).reset_index(drop=True)


def bootstrap_summary(scored: pd.DataFrame, reps: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(scored["run"].unique()), dtype=int)
    methods = list(scored["method"].unique())
    base = scored[scored["method"] == "uncorrected"]
    samples: Dict[str, Dict[str, List[float]]] = {
        method: {"sigma68_ns": [], "tail_abs_gt_0p5_ns": [], "bias_ns": [], "delta_sigma68_vs_uncorrected_ns": []}
        for method in methods
    }
    by_method_run = {(m, int(r)): g for (m, r), g in scored.groupby(["method", "run"])}
    for _ in range(int(reps)):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        unc = pd.concat([by_method_run[("uncorrected", int(r))] for r in chosen], ignore_index=True)
        unc_metric = metric_dict(unc["corrected_residual_ns"].to_numpy(dtype=float))["sigma68_ns"]
        for method in methods:
            sample = pd.concat([by_method_run[(method, int(r))] for r in chosen], ignore_index=True)
            m = metric_dict(sample["corrected_residual_ns"].to_numpy(dtype=float))
            for key in ["sigma68_ns", "tail_abs_gt_0p5_ns", "bias_ns"]:
                samples[method][key].append(m[key])
            samples[method]["delta_sigma68_vs_uncorrected_ns"].append(m["sigma68_ns"] - unc_metric)
    rows = []
    for method, vals in samples.items():
        row = {"method": method}
        for key, arr in vals.items():
            arr = np.asarray(arr, dtype=float)
            row[f"{key}_ci_low"] = float(np.percentile(arr, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(arr, 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def add_cis(metrics: pd.DataFrame, boot: pd.DataFrame) -> pd.DataFrame:
    out = metrics.merge(boot, on="method", how="left")
    return out


def choose_winner(metrics: pd.DataFrame) -> str:
    candidates = metrics[metrics["method"] != "uncorrected"].copy()
    candidates["abs_bias_ns"] = candidates["bias_ns"].abs()
    candidates = candidates.sort_values(["sigma68_ns", "tail_abs_gt_0p5_ns", "abs_bias_ns"], kind="mergesort")
    return str(candidates.iloc[0]["method"])


def make_plots(metrics: pd.DataFrame, scored: pd.DataFrame, out_dir: Path):
    order = metrics.sort_values("sigma68_ns")["method"].tolist()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(metrics.set_index("method").loc[order].index, metrics.set_index("method").loc[order]["sigma68_ns"])
    ax.set_xlabel("sigma68 corrected residual (ns)")
    ax.set_title("S16m leave-one-run-out timing correction benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "metric_summary.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    for method in ["uncorrected", "traditional_binned_median", choose_winner(metrics)]:
        data = scored[scored["method"] == method]["corrected_residual_ns"].clip(-2, 2)
        ax.hist(data, bins=80, histtype="step", density=True, label=method)
    ax.set_xlabel("corrected residual, clipped to +/-2 ns")
    ax.set_ylabel("density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "residual_distributions.png", dpi=180)
    plt.close(fig)


def write_report(config: dict, result: dict, reproduction: pd.DataFrame, metrics: pd.DataFrame, per_run: pd.DataFrame, out_dir: Path):
    winner = result["winner"]
    report = f"""# S16m: Support-Preserving Pedestal-Imputation Timing Correction

## Abstract

This study tests whether the S16l target-excluded pedestal-imputation signal can be useful as a nuisance covariate for timing correction without replacing the physical waveform support used by the timing estimator. The raw ROOT selection reproduces the registered selected B-stave pulse count exactly. On leave-one-run-out Sample-II downstream-pair timing, the winning correction by the pre-registered rule is **{winner}**.

## Data Reproduction

Raw `h101/HRDv` waveforms were read from `{config["raw_root_dir"]}`. The same B-stave channel map, four-sample median pedestal seed, and amplitude threshold used in S16l were applied. The reproduction gate is exact equality with the registered counts.

{md_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"])}

## Estimand

For a downstream pair `(a,b)` in the same event, the uncorrected support-preserving residual is

`r_i = (t_i,a(CFD20) - t_i,b(CFD20)) - (x_a - x_b) tau`,

where the CFD20 time is the CFD crossing from the original four-sample median baseline, `x` is the B-stack position, and `tau={config["tof_per_cm_ns"]}` ns/cm. A model estimates `c_i = E[r_i | z_i]`; the corrected residual is `r_i - c_i`. No model recomputes a pedestal, waveform, amplitude, or CFD crossing from imputed samples.

## Nuisance Construction

For each pulse and each pretrigger sample `j in {{0,1,2,3}}`, the S16l target-excluded predictors `mean3`, `median3`, and `line3` were computed from the other three pretrigger samples only. Their discrepancies from the observed target sample were aggregated to pulse-level nuisance summaries: signed mean discrepancy, mean absolute discrepancy, maximum absolute discrepancy, model spread, target-sample standard deviation, and visible three-sample range. These quantities enter the correction feature vector only; they are not used as replacement baseline values.

## Models and Split

All comparisons use leave-one-run-out Sample-II analysis splitting over runs `{config["heldout_runs"]}`. The traditional method is a hierarchical binned median correction over pair identity, amplitude-ratio bin, pretrigger-dispersion bin, and nuisance-magnitude bin, with fallbacks to coarser cells and a global median. ML/NN comparators are ridge regression, histogram gradient-boosted trees, MLP, a 1D pair CNN over baseline-subtracted raw waveform pairs, and a new nuisance-gated pair CNN whose convolutional representation is multiplicatively gated by nuisance features.

## Primary Results

Bootstrap intervals resample held-out runs with replacement, preserving the paired method comparison structure within each sampled run.

{md_table(metrics, ["method", "n_pairs", "sigma68_ns", "sigma68_ns_ci_low", "sigma68_ns_ci_high", "tail_abs_gt_0p5_ns", "tail_abs_gt_0p5_ns_ci_low", "tail_abs_gt_0p5_ns_ci_high", "bias_ns", "bias_ns_ci_low", "bias_ns_ci_high", "delta_sigma68_vs_uncorrected_ns_ci_low", "delta_sigma68_vs_uncorrected_ns_ci_high"])}

## Per-Run Stability

{md_table(per_run, ["method", "run", "n_pairs", "sigma68_ns", "tail_abs_gt_0p5_ns", "bias_ns"])}

## Systematics and Caveats

The split-by-run design guards against event-level leakage and tests whether corrections transport across acquisition periods. The remaining systematic limitations are: (1) run bootstrap intervals have only seven independent run units and should be read as operational uncertainty rather than asymptotic confidence intervals; (2) the correction target is pairwise residual symmetry rather than an external timing truth; (3) waveform CNNs use the original median-baseline support and therefore test timing correction capacity, not a new CFD definition; (4) nuisance features are derived from observed pretrigger samples, so their value is diagnostic of contamination but not evidence that imputed pedestal substitution is safe; and (5) hyperparameters are deliberately modest to keep the ROOT-to-report pipeline reproducible on the worker.

## Conclusion

The support-preserving benchmark separates pedestal-contamination diagnosis from unsafe baseline substitution. The named winner in `result.json` is `{winner}`, selected by lowest held-out `sigma68_ns` among correction methods with the registered tie breakers.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    parser.add_argument("--report-only", action="store_true", help="rebuild REPORT.md and manifest from existing output artifacts")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.report_only:
        reproduction = pd.read_csv(out_dir / "reproduction_counts.csv")
        metrics_ci = pd.read_csv(out_dir / "method_metrics.csv")
        per_run = pd.read_csv(out_dir / "per_run_metrics.csv")
        result = json.loads((out_dir / "result.json").read_text())
        write_report(config, result, reproduction, metrics_ci, per_run, out_dir)
        manifest = {
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "files": {p.name: sha256_file(p) for p in out_dir.iterdir() if p.is_file()},
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"report_only": True, "winner": result["winner"], "out_dir": str(out_dir)}, indent=2))
        return 0

    reproduction = S16L.S16F.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_counts.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    hashes = input_hashes(config)
    hashes.to_csv(out_dir / "input_sha256.csv", index=False)

    meta, waves = S16L.load_selected_pulses(config)
    nuis = nuisance_features(meta, waves, config["heldout_runs"])
    nuis.to_csv(out_dir / "nuisance_features.csv.gz", index=False)
    pairs = build_pairs(meta, nuis, config)
    pairs.to_csv(out_dir / "pair_rows.csv.gz", index=False)
    scored = fit_fold_models(pairs, waves, config)
    scored.to_csv(out_dir / "method_predictions.csv.gz", index=False)

    metrics = summarize_metrics(scored)
    per_run = per_run_metrics(scored)
    boot = bootstrap_summary(scored, int(config["bootstrap_replicates"]), int(config["models"]["random_seed"]))
    metrics_ci = add_cis(metrics, boot)
    metrics_ci.to_csv(out_dir / "method_metrics.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    boot.to_csv(out_dir / "bootstrap_metrics.csv", index=False)
    winner = choose_winner(metrics)
    make_plots(metrics, scored, out_dir)

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "winner": winner,
        "primary_metric": config["primary_metric"],
        "winner_metrics": metrics_ci[metrics_ci["method"] == winner].iloc[0].to_dict(),
        "traditional_method": "traditional_binned_median",
        "methods": METHODS,
        "split": "leave-one-run-out over Sample-II analysis runs",
        "bootstrap": {"unit": "held-out run", "replicates": int(config["bootstrap_replicates"]), "paired": True},
        "support_preserving": True,
        "raw_reproduction": {"all_pass": bool(reproduction["pass"].all()), "rows": reproduction.to_dict(orient="records")},
        "n_pairs": int(len(pairs)),
        "input_root_files": int(len(hashes)),
        "git_commit": git_commit(),
        "runtime_seconds": round(time.time() - start, 3),
        "outputs": [
            "REPORT.md",
            "result.json",
            "reproduction_counts.csv",
            "input_sha256.csv",
            "nuisance_features.csv.gz",
            "pair_rows.csv.gz",
            "method_predictions.csv.gz",
            "method_metrics.csv",
            "per_run_metrics.csv",
            "bootstrap_metrics.csv",
            "metric_summary.png",
            "residual_distributions.png",
        ],
        "next_tickets": config.get("next_tickets", [])[:1],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    shutil.copy2(config_path, out_dir / "config.json")
    write_report(config, result, reproduction, metrics_ci, per_run, out_dir)
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "files": {p.name: sha256_file(p) for p in out_dir.iterdir() if p.is_file()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"winner": winner, "out_dir": str(out_dir), "n_pairs": int(len(pairs))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
