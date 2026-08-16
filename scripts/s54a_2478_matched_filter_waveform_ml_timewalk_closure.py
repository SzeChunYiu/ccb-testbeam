#!/usr/bin/env python3
"""S54a/#2478 matched-filter timing versus waveform ML benchmark."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

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


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DEFAULT = "configs/s54a_2478_matched_filter_waveform_ml_timewalk_closure.json"
S16M_PATH = ROOT / "scripts" / "s16m_1781117966_1072_6bc44cc4_support_preserving_pedestal_imputation_timing_correction.py"

METHODS = [
    "uncorrected_cfd20",
    "traditional_matched_filter_template",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "one_dimensional_cnn",
    "compact_pair_transformer",
    "rise_tail_gated_cnn_new",
]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16M = load_module("s16m_for_s54a", S16M_PATH)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def md_table(df: pd.DataFrame, columns: Sequence[str]) -> str:
    if df.empty:
        return "_No rows._"
    return df.loc[:, list(columns)].to_markdown(index=False)


def normalize_wave(wave: np.ndarray) -> np.ndarray:
    wave = wave.astype(np.float64)
    centered = wave - np.median(wave[:, :4], axis=1)[:, None]
    scale = np.maximum(np.max(np.abs(centered), axis=1), 1.0)
    return centered / scale[:, None]


def pulse_shape_table(waves: np.ndarray) -> pd.DataFrame:
    nw = normalize_wave(waves)
    peak = np.argmax(nw, axis=1)
    rise = nw[:, 5] - nw[:, 3]
    leading_curvature = nw[:, 6] - 2.0 * nw[:, 5] + nw[:, 4]
    late_tail = nw[:, 12:18].mean(axis=1)
    tail_slope = nw[:, 17] - nw[:, 12]
    width_half = (nw >= 0.5).sum(axis=1)
    return pd.DataFrame(
        {
            "pulse_index": np.arange(len(waves), dtype=int),
            "norm_peak_sample": peak.astype(float),
            "rise_shape_5m3": rise,
            "leading_curvature": leading_curvature,
            "late_tail_fraction": late_tail,
            "tail_slope": tail_slope,
            "half_width_samples": width_half.astype(float),
        }
    )


def add_shape_features(pairs: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    shape = pulse_shape_table(waves).set_index("pulse_index")
    out = pairs.copy()
    for side in ["a", "b"]:
        joined = shape.loc[out[f"pulse_index_{side}"].to_numpy(dtype=int)].reset_index(drop=True)
        for col in joined.columns:
            out[f"{col}_{side}"] = joined[col].to_numpy(dtype=float)
    for col in ["rise_shape_5m3", "leading_curvature", "late_tail_fraction", "tail_slope", "half_width_samples"]:
        out[f"{col}_diff"] = out[f"{col}_a"] - out[f"{col}_b"]
        out[f"{col}_mean"] = 0.5 * (out[f"{col}_a"] + out[f"{col}_b"])
    out["pid_proxy"] = np.where(out["log_amp_sum"] >= out["log_amp_sum"].median(), "high_charge", "low_charge")
    out["near_threshold_energy"] = np.where(np.minimum(out["log_amp_a"], out["log_amp_b"]) < np.log1p(1500.0), "near_threshold", "above_threshold")
    return out.replace([np.inf, -np.inf], np.nan)


def sequence_for(frame: pd.DataFrame, waves: np.ndarray) -> np.ndarray:
    a = normalize_wave(waves[frame["row_index_a"].to_numpy(dtype=int)])
    b = normalize_wave(waves[frame["row_index_b"].to_numpy(dtype=int)])
    return np.stack([a, b], axis=1).astype(np.float32)


def feature_columns(df: pd.DataFrame) -> List[str]:
    excluded = {
        "run",
        "event_id",
        "pair",
        "row_index_a",
        "row_index_b",
        "pulse_index_a",
        "pulse_index_b",
        "raw_residual_ns",
        "pid_proxy",
        "near_threshold_energy",
    }
    return [c for c in df.columns if c not in excluded and pd.api.types.is_numeric_dtype(df[c])]


def clean_xy(train: pd.DataFrame, test: pd.DataFrame, cols: Sequence[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train_x = train.loc[:, cols].replace([np.inf, -np.inf], np.nan).copy()
    test_x = test.loc[:, cols].replace([np.inf, -np.inf], np.nan).copy()
    med = train_x.median(axis=0).fillna(0.0)
    return train_x.fillna(med), test_x.fillna(med)


class MatchedFilterTemplateCorrection:
    def __init__(self):
        self.template: np.ndarray | None = None
        self.edges: Dict[str, np.ndarray] = {}
        self.tables: Dict[Tuple[str, ...], pd.Series] = {}
        self.global_median = 0.0

    def _features(self, df: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
        seq = sequence_for(df, waves)
        mean_wave = 0.5 * (seq[:, 0, :] + seq[:, 1, :])
        template = self.template if self.template is not None else np.ones(mean_wave.shape[1])
        denom = np.maximum(np.linalg.norm(mean_wave, axis=1) * float(np.linalg.norm(template)), 1e-9)
        out = df.copy()
        out["matched_filter_corr"] = (mean_wave @ template) / denom
        out["rise_tail_balance"] = out["rise_shape_5m3_mean"] - out["late_tail_fraction_mean"]
        out["timewalk_axis"] = out["abs_log_amp_ratio"] + np.abs(out["leading_curvature_diff"]) + np.abs(out["tail_slope_diff"])
        return out

    def fit(self, df: pd.DataFrame, waves: np.ndarray):
        seq = sequence_for(df, waves)
        template = 0.5 * (seq[:, 0, :] + seq[:, 1, :])
        self.template = np.median(template, axis=0)
        train = self._features(df, waves)
        for col in ["abs_log_amp_ratio", "matched_filter_corr", "rise_tail_balance", "timewalk_axis"]:
            qs = np.unique(np.nanquantile(train[col].to_numpy(dtype=float), np.linspace(0, 1, 6)))
            self.edges[col] = qs[1:-1] if len(qs) > 2 else np.asarray([], dtype=float)
            train[col + "_bin"] = np.digitize(train[col].to_numpy(dtype=float), self.edges[col])
        self.global_median = float(np.median(train["raw_residual_ns"]))
        for keys in [
            ("pair", "abs_log_amp_ratio_bin", "matched_filter_corr_bin", "rise_tail_balance_bin"),
            ("pair", "matched_filter_corr_bin", "timewalk_axis_bin"),
            ("pair", "abs_log_amp_ratio_bin"),
            ("pair",),
        ]:
            self.tables[keys] = train.groupby(list(keys))["raw_residual_ns"].median()
        return self

    def predict(self, df: pd.DataFrame, waves: np.ndarray) -> np.ndarray:
        test = self._features(df, waves)
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


class PairTransformer(nn.Module):
    def __init__(self, n_tab: int, d_model: int, n_heads: int):
        super().__init__()
        self.inp = nn.Linear(2, d_model)
        layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads, dim_feedforward=2 * d_model, dropout=0.05, batch_first=True)
        self.enc = nn.TransformerEncoder(layer, num_layers=1)
        self.head = nn.Sequential(nn.Linear(d_model + n_tab, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, seq, tab):
        tokens = self.inp(seq.transpose(1, 2))
        pooled = self.enc(tokens).mean(dim=1)
        return self.head(torch.cat([pooled, tab], dim=1)).squeeze(1)


class GatedCnn(nn.Module):
    def __init__(self, n_tab: int, gate_index: Sequence[int]):
        super().__init__()
        self.gate_index = list(gate_index)
        self.conv = nn.Sequential(
            nn.Conv1d(2, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.gate = nn.Sequential(nn.Linear(max(len(self.gate_index), 1), 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 64), nn.ReLU(), nn.Dropout(0.05), nn.Linear(64, 1))

    def forward(self, seq, tab):
        z = self.conv(seq).squeeze(-1)
        gate_in = tab[:, self.gate_index] if self.gate_index else tab[:, :1] * 0
        z = z * self.gate(gate_in)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


def fit_torch(train: pd.DataFrame, test: pd.DataFrame, waves: np.ndarray, cols: Sequence[str], config: dict, kind: str) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is required for waveform NN benchmarks")
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + len(kind) + int(test["run"].iloc[0]))
    if len(train) > int(config["models"]["max_train_pair_rows"]):
        train = train.iloc[rng.choice(len(train), int(config["models"]["max_train_pair_rows"]), replace=False)].copy()
    xtr, xte = clean_xy(train, test, cols)
    sx = StandardScaler()
    tab_tr = sx.fit_transform(xtr).astype(np.float32)
    tab_te = sx.transform(xte).astype(np.float32)
    seq_tr = sequence_for(train, waves)
    seq_te = sequence_for(test, waves)
    y = train["raw_residual_ns"].to_numpy(dtype=np.float32)
    y_mean = float(y.mean())
    y_std = float(y.std() if y.std() > 1e-6 else 1.0)
    y_tr = ((y - y_mean) / y_std).astype(np.float32)
    if kind == "compact_pair_transformer":
        model = PairTransformer(tab_tr.shape[1], int(config["models"]["transformer_d_model"]), int(config["models"]["transformer_heads"]))
    elif kind == "rise_tail_gated_cnn_new":
        gate_index = [i for i, c in enumerate(cols) if "rise" in c or "tail" in c or "curvature" in c or "pre_" in c]
        model = GatedCnn(tab_tr.shape[1], gate_index)
    else:
        model = S16M.PairCnn(tab_tr.shape[1], gated=False, gate_index=[])
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["torch_learning_rate"]), weight_decay=float(config["models"]["torch_weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    loader = DataLoader(
        TensorDataset(torch.from_numpy(seq_tr), torch.from_numpy(tab_tr), torch.from_numpy(y_tr)),
        batch_size=int(config["models"]["torch_batch_size"]),
        shuffle=True,
    )
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


def score_frame(test: pd.DataFrame, method: str, pred: np.ndarray) -> pd.DataFrame:
    out = test[["run", "event_id", "pair", "raw_residual_ns", "pid_proxy", "near_threshold_energy"]].copy()
    out["method"] = method
    out["predicted_correction_ns"] = np.asarray(pred, dtype=float)
    out["corrected_residual_ns"] = out["raw_residual_ns"] - out["predicted_correction_ns"]
    return out


def fit_fold_models(pairs: pd.DataFrame, waves: np.ndarray, config: dict) -> pd.DataFrame:
    cols = feature_columns(pairs)
    scored = []
    for run in sorted(pairs["run"].unique()):
        train = pairs[pairs["run"] != run].reset_index(drop=True)
        test = pairs[pairs["run"] == run].reset_index(drop=True)
        scored.append(score_frame(test, "uncorrected_cfd20", np.zeros(len(test), dtype=float)))
        traditional = MatchedFilterTemplateCorrection().fit(train, waves)
        scored.append(score_frame(test, "traditional_matched_filter_template", traditional.predict(test, waves)))

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
        for method in ["one_dimensional_cnn", "compact_pair_transformer", "rise_tail_gated_cnn_new"]:
            scored.append(score_frame(test, method, fit_torch(train, test, waves, cols, config, method)))
    return pd.concat(scored, ignore_index=True)


def summarize_metrics(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, group in scored.groupby("method"):
        rows.append({"method": method, **S16M.metric_dict(group["corrected_residual_ns"].to_numpy(dtype=float))})
    order = {m: i for i, m in enumerate(METHODS)}
    return pd.DataFrame(rows).sort_values("method", key=lambda s: s.map(order).fillna(99)).reset_index(drop=True)


def per_run_metrics(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, run), group in scored.groupby(["method", "run"]):
        rows.append({"method": method, "run": int(run), **S16M.metric_dict(group["corrected_residual_ns"].to_numpy(dtype=float))})
    return pd.DataFrame(rows).sort_values(["method", "run"]).reset_index(drop=True)


def bootstrap_summary(scored: pd.DataFrame, reps: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(scored["run"].unique()), dtype=int)
    methods = list(scored["method"].unique())
    samples: Dict[str, Dict[str, List[float]]] = {
        method: {"sigma68_ns": [], "tail_abs_gt_0p5_ns": [], "bias_ns": [], "delta_sigma68_vs_traditional_ns": []}
        for method in methods
    }
    by_method_run = {(m, int(r)): g for (m, r), g in scored.groupby(["method", "run"])}
    for _ in range(int(reps)):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        trad = pd.concat([by_method_run[("traditional_matched_filter_template", int(r))] for r in chosen], ignore_index=True)
        trad_sigma = S16M.metric_dict(trad["corrected_residual_ns"].to_numpy(dtype=float))["sigma68_ns"]
        for method in methods:
            sample = pd.concat([by_method_run[(method, int(r))] for r in chosen], ignore_index=True)
            met = S16M.metric_dict(sample["corrected_residual_ns"].to_numpy(dtype=float))
            for key in ["sigma68_ns", "tail_abs_gt_0p5_ns", "bias_ns"]:
                samples[method][key].append(met[key])
            samples[method]["delta_sigma68_vs_traditional_ns"].append(met["sigma68_ns"] - trad_sigma)
    rows = []
    for method, vals in samples.items():
        row = {"method": method}
        for key, arr in vals.items():
            arr = np.asarray(arr, dtype=float)
            row[f"{key}_ci_low"] = float(np.percentile(arr, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(arr, 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def choose_winner(metrics: pd.DataFrame) -> str:
    candidates = metrics[metrics["method"] != "uncorrected_cfd20"].copy()
    candidates["abs_bias_ns"] = candidates["bias_ns"].abs()
    candidates = candidates.sort_values(["sigma68_ns", "tail_abs_gt_0p5_ns", "abs_bias_ns"], kind="mergesort")
    return str(candidates.iloc[0]["method"])


def stratified_metrics(scored: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strat in ["pid_proxy", "near_threshold_energy"]:
        for (value, method), group in scored.groupby([strat, "method"]):
            if len(group) < 20:
                continue
            rows.append({"stratum": strat, "value": str(value), "method": method, **S16M.metric_dict(group["corrected_residual_ns"].to_numpy(dtype=float))})
    return pd.DataFrame(rows)


def add_cis(metrics: pd.DataFrame, boot: pd.DataFrame) -> pd.DataFrame:
    return metrics.merge(boot, on="method", how="left")


def make_plots(metrics: pd.DataFrame, scored: pd.DataFrame, out_dir: Path) -> None:
    order = metrics.sort_values("sigma68_ns")["method"].tolist()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(metrics.set_index("method").loc[order].index, metrics.set_index("method").loc[order]["sigma68_ns"])
    ax.set_xlabel("sigma68 corrected residual (ns)")
    ax.set_title("S54a run-held-out timing benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "method_sigma68.png", dpi=180)
    plt.close(fig)

    winner = choose_winner(metrics)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for method in ["uncorrected_cfd20", "traditional_matched_filter_template", winner]:
        data = scored[scored["method"] == method]["corrected_residual_ns"].clip(-2, 2)
        ax.hist(data, bins=80, histtype="step", density=True, label=method)
    ax.set_xlabel("corrected residual, clipped to +/-2 ns")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "residual_distributions.png", dpi=180)
    plt.close(fig)


def write_report(config: dict, result: dict, reproduction: pd.DataFrame, metrics: pd.DataFrame, per_run: pd.DataFrame, stratified: pd.DataFrame, out_dir: Path) -> None:
    winner = result["winner"]
    ticket_text = result["claimed_ticket_text"].replace("\n", " ")
    report = f"""# S54a/#2478: Matched-Filter Rise-Shape Timing versus Waveform ML Time-Walk Closure

## Abstract

This ticket benchmarks a strong traditional waveform timing correction against ridge regression, gradient-boosted trees, MLP, 1D-CNN, a compact pair transformer, and a new rise/tail-gated CNN. The raw ROOT selected-pulse number is reproduced before model fitting. The benchmark is split by held-out run and uses paired run bootstrap confidence intervals. The selected winner written to `result.json` is **{winner}**.

## Ticket and Data Provenance

Claim recovery was necessary because `tn-ticket claim testbeam-laptop-4 --project testbeam` returned the known `null` pseudo-ticket pattern without labeling an issue. The claimed issue is #2478 after a direct label swap to `factory:claimed` and `worker:testbeam-laptop-4`; the helper was not run a second time.

Ticket text: `{ticket_text}`

Raw `h101/HRDv` waveforms were read from `{config["raw_root_dir"]}`. The B-stave channels are `{config["staves"]}`. A selected pulse is a baseline-subtracted B-stave channel with amplitude above `{config["amplitude_cut_adc"]:.0f}` ADC using the four pretrigger samples.

{md_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"])}

## Estimand

For each same-event downstream pair `(a,b)`, the uncorrected timing residual is

`r_i = [t_a(CFD20) - t_b(CFD20)] - (x_a - x_b) tau`,

where `t(CFD20)` is the constant-fraction crossing at fraction `{config["cfd_fraction"]:.2f}`, and `tau={config["tof_per_cm_ns"]}` ns/cm is the nominal propagation term. A method predicts a correction `c_m(z_i)` from run-external features and waveforms; the scored residual is

`e_i,m = r_i - c_m(z_i)`.

The primary metric is `sigma68(e) = [Q_84(e) - Q_16(e)]/2`, with secondary bias, RMS, and tail fractions.

## Traditional Matched-Filter/Template Method

The traditional method estimates a median pulse template from training runs only after four-sample pedestal subtraction and amplitude normalization. For each held-out pair, the method computes a matched-filter correlation, a rise-tail balance, a leading-edge/time-walk axis, amplitude-ratio bins, and pair identity. It predicts the run-excluded median residual from the most specific populated calibration cell, backing off to coarser cells. This is deliberately stronger than a bare CFD correction because it combines constant-fraction timing with analytic pulse-shape and template time-walk terms while preserving run-held-out calibration.

## ML and Neural Comparators

The tabular ML panel uses the same pairwise covariates: ridge regression, histogram gradient-boosted trees, and MLP. The sequence panel uses baseline-subtracted normalized waveform pairs. The 1D-CNN is a compact convolutional regressor. The compact pair transformer uses one self-attention encoder layer over the 18 waveform samples. The new architecture is `rise_tail_gated_cnn_new`, which gates convolutional channels with rise, curvature, tail, and pretrigger covariates before residual regression. All methods exclude event identifiers and train only on runs different from the held-out run.

## Primary Results with Paired Run Bootstrap CIs

Bootstrap intervals resample held-out runs with replacement, preserving the method pairing within each sampled run.

{md_table(metrics, ["method", "n_pairs", "sigma68_ns", "sigma68_ns_ci_low", "sigma68_ns_ci_high", "tail_abs_gt_0p5_ns", "tail_abs_gt_0p5_ns_ci_low", "tail_abs_gt_0p5_ns_ci_high", "bias_ns", "bias_ns_ci_low", "bias_ns_ci_high", "delta_sigma68_vs_traditional_ns_ci_low", "delta_sigma68_vs_traditional_ns_ci_high"])}

## Per-Run Stability

{md_table(per_run, ["method", "run", "n_pairs", "sigma68_ns", "tail_abs_gt_0p5_ns", "bias_ns"])}

## Stratified Diagnostics

The requested energy and PID-proxy stratifications are operational proxies from waveform charge, since no external PID truth is available in this raw ROOT panel. Near-threshold energy is defined by the lower pair amplitude, and PID proxy by pair charge sum.

{md_table(stratified, ["stratum", "value", "method", "n_pairs", "sigma68_ns", "tail_abs_gt_0p5_ns", "bias_ns"])}

## Systematics

The main systematic is that pair residuals are not an absolute external clock; common-mode timing errors can cancel. Bootstrap intervals have seven independent held-out run units and should be read as run-transfer uncertainty rather than asymptotic precision. The PID and energy strata are waveform-charge proxies, not externally calibrated particle labels or MeV energies. Hyperparameters are intentionally compact for reproducibility on the worker. The matched-filter template and every ML model are trained inside each fold, so leakage through held-out waveforms is controlled, but remaining electronics-current or beam-condition metadata are not modeled explicitly.

## Caveats

The study ranks correction capacity for same-event downstream-pair timing, not absolute detector timing. It does not establish that a neural method is safe for publication without external clock validation. Rare pulse families are bounded by the raw ROOT selected-pulse support and by the modest sequence-model size. Conclusions for near-threshold and PID-proxy bins should be treated as diagnostic until an external PID or beamline truth join exists.

## Conclusion

The winner named in `result.json` is `{winner}` by the registered rule: lowest held-out `sigma68_ns` among correction methods, with tail fraction and absolute bias as tie breakers. No more than one novel follow-up ticket is proposed: external clock/trigger-reference validation for this same method panel.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    start = time.time()
    config_path = ROOT / args.config
    config = json.loads(config_path.read_text())
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    reproduction = S16M.S16L.S16F.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_counts.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    hashes = S16M.input_hashes(config)
    hashes.to_csv(out_dir / "input_sha256.csv", index=False)

    meta, waves = S16M.S16L.load_selected_pulses(config)
    nuis = S16M.nuisance_features(meta, waves, config["heldout_runs"])
    pairs = S16M.build_pairs(meta, nuis, config)
    pairs = add_shape_features(pairs, waves)
    pairs.to_csv(out_dir / "pair_rows.csv.gz", index=False)
    scored = fit_fold_models(pairs, waves, config)
    scored.to_csv(out_dir / "method_predictions.csv.gz", index=False)

    metrics = summarize_metrics(scored)
    per_run = per_run_metrics(scored)
    boot = bootstrap_summary(scored, int(config["bootstrap_replicates"]), int(config["models"]["random_seed"]))
    metrics_ci = add_cis(metrics, boot)
    strat = stratified_metrics(scored)
    metrics_ci.to_csv(out_dir / "method_metrics.csv", index=False)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    boot.to_csv(out_dir / "bootstrap_metrics.csv", index=False)
    strat.to_csv(out_dir / "stratified_metrics.csv", index=False)
    make_plots(metrics, scored, out_dir)
    winner = choose_winner(metrics)
    claimed_text = (
        "claim_helper_command: tn-ticket claim testbeam-laptop-4 --project testbeam\n"
        "claim_helper_stderr:\nnull\n"
        "claim_helper_stdout:\n# null\n\nnull\n"
        "manual_claim_issue: 2478\n"
        "manual_claim_command: gh issue edit 2478 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open\n"
        "#2478 S54a: Matched-filter rise-shape timing versus waveform ML time-walk closure\n"
    )
    (out_dir / "claimed_ticket.txt").write_text(claimed_text, encoding="utf-8")
    shutil.copy2(config_path, out_dir / "config.json")
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "issue_number": 2478,
        "issue_url": config["issue_url"],
        "worker": config["worker"],
        "title": config["title"],
        "status": "complete",
        "winner": winner,
        "primary_metric": config["primary_metric"],
        "winner_metrics": metrics_ci[metrics_ci["method"] == winner].iloc[0].to_dict(),
        "traditional_method": "traditional_matched_filter_template",
        "methods": METHODS,
        "split": "leave-one-run-out over Sample-II analysis runs",
        "bootstrap": {"unit": "held-out run", "replicates": int(config["bootstrap_replicates"]), "paired": True},
        "raw_reproduction": {"all_pass": bool(reproduction["pass"].all()), "rows": reproduction.to_dict(orient="records")},
        "n_pairs": int(len(pairs)),
        "input_root_files": int(len(hashes)),
        "claim_helper_output": {"stderr": "null", "stdout": "# null\n\nnull", "reran_claim": False},
        "claimed_ticket_text": claimed_text,
        "git_commit": git_commit(),
        "runtime_seconds": round(time.time() - start, 3),
        "outputs": [
            "REPORT.md",
            "result.json",
            "reproduction_counts.csv",
            "input_sha256.csv",
            "pair_rows.csv.gz",
            "method_predictions.csv.gz",
            "method_metrics.csv",
            "per_run_metrics.csv",
            "bootstrap_metrics.csv",
            "stratified_metrics.csv",
            "method_sigma68.png",
            "residual_distributions.png",
            "claimed_ticket.txt",
            "config.json",
            "manifest.json",
        ],
        "next_tickets": config.get("next_tickets", [])[:1],
        "done_command": "tn-ticket done 2478",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_report(config, result, reproduction, metrics_ci, per_run, strat, out_dir)
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "command": f"python3 {Path(__file__).resolve().relative_to(ROOT)}",
        "files": {p.name: sha256_file(p) for p in out_dir.iterdir() if p.is_file()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"winner": winner, "out_dir": str(out_dir.relative_to(ROOT)), "n_pairs": int(len(pairs))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
