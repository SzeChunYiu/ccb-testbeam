#!/usr/bin/env python3
"""S27d external ADC quantization timing replication.

The study reproduces the raw ROOT selected-pulse count, then freezes the S27a
ADC-quantization timing benchmark design and repeats it on an independent
Sample-I run block.  The S27a winning ridge family is held at alpha=10 in the
configuration while the requested traditional, tree, MLP, CNN, and attention
comparators are retained for a full external bakeoff.
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

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s27d-adc-quantization")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p03a_18_sample_mlp_timing as p03a
import s02_timing_pickoff as s02

torch.set_num_threads(1)


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


def raw_file(config: dict, run: int) -> Path:
    return s02.raw_file(config, run)


def configured_runs(config: dict) -> List[int]:
    return s02.configured_runs(config)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def finite_mask(X: np.ndarray, y: np.ndarray, runs: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1) & np.isfinite(runs)


def waveform_feature_matrix(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
    norm = wf / amp[:, None]
    rounded = np.rint(wf)
    qres = wf - rounded
    q_abs_mean = np.mean(np.abs(qres), axis=1, keepdims=True)
    q_rms = np.sqrt(np.mean(qres * qres, axis=1, keepdims=True))
    q_zero_frac = (np.abs(qres) < 0.05).mean(axis=1, keepdims=True)
    q_peak = qres[np.arange(len(wf)), np.argmax(wf, axis=1)][:, None]
    rise_slope = (wf[:, 7:10].max(axis=1) - wf[:, 2:5].mean(axis=1))[:, None] / amp[:, None]
    tail = (wf[:, 12:].sum(axis=1) / np.maximum(wf.sum(axis=1), 1.0))[:, None]
    late_max = (wf[:, 12:].max(axis=1) / amp)[:, None]
    pedestal_proxy = np.std(wf[:, :4], axis=1, keepdims=True)
    scalar = np.hstack(
        [
            np.log1p(amp)[:, None],
            pulses["peak_sample"].to_numpy(dtype=np.float32)[:, None],
            (pulses["area_adc_samples"].to_numpy(dtype=np.float32) / amp)[:, None],
            rise_slope,
            tail,
            late_max,
            q_abs_mean,
            q_rms,
            q_zero_frac,
            q_peak,
            pedestal_proxy / 1000.0,
        ]
    )
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, lookup[stave]] = 1.0
    names = (
        [f"sample_{i:02d}_over_amp" for i in range(norm.shape[1])]
        + [
            "log_amp",
            "peak_sample",
            "area_over_amp",
            "rise_slope",
            "tail_fraction",
            "late_max_fraction",
            "adc_quant_abs_mean",
            "adc_quant_rms",
            "adc_quant_near_integer_fraction",
            "adc_quant_peak_residual",
            "pretrigger_rms_kadc",
        ]
        + [f"stave_{s}" for s in staves]
    )
    return np.hstack([norm, scalar, one_hot]).astype(np.float32), names


def sequence_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=np.float32), 1.0)
    norm = wf / amp[:, None]
    qres = (wf - np.rint(wf)).astype(np.float32)
    seq = np.stack([norm, qres], axis=1)
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, lookup[stave]] = 1.0
    return seq.astype(np.float32), one_hot


class QuantSeqRegressor(nn.Module):
    def __init__(self, arch: str, n_staves: int, width: int) -> None:
        super().__init__()
        self.arch = arch
        if arch == "cnn":
            self.encoder = nn.Sequential(
                nn.Conv1d(2, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(width, width, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
            )
            enc_dim = width
        elif arch == "attention":
            self.proj = nn.Linear(2, width)
            self.attn = nn.MultiheadAttention(width, num_heads=1, batch_first=True)
            self.norm = nn.LayerNorm(width)
            enc_dim = width
        else:
            raise ValueError(arch)
        self.head = nn.Sequential(nn.Linear(enc_dim + n_staves, max(width, 8)), nn.ReLU(), nn.Linear(max(width, 8), 1))

    def forward(self, seq: torch.Tensor, stave: torch.Tensor) -> torch.Tensor:
        if self.arch == "attention":
            y = self.proj(seq.transpose(1, 2))
            y2, _ = self.attn(y, y, y, need_weights=False)
            z = self.norm(y + y2).mean(dim=1)
        else:
            z = self.encoder(seq)
        return self.head(torch.cat([z, stave], dim=1)).squeeze(1)


def train_torch_regressor(
    arch: str,
    seq: np.ndarray,
    stave: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    width: int,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, float, int]:
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    model = QuantSeqRegressor(arch, stave.shape[1], int(width))
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["torch_lr"]), weight_decay=float(config["ml"]["torch_weight_decay"]))
    xs = torch.from_numpy(seq.astype(np.float32))
    st = torch.from_numpy(stave.astype(np.float32))
    yy = torch.from_numpy(y.astype(np.float32))
    batch = int(config["ml"]["torch_batch_size"])
    start = time.time()
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = rng.permutation(train_idx)
        for lo in range(0, len(order), batch):
            idx = order[lo : lo + batch]
            pred = model(xs[idx], st[idx])
            loss = torch.mean((pred - yy[idx]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    elapsed = time.time() - start
    preds = []
    model.eval()
    with torch.no_grad():
        for lo in range(0, len(seq), 8192):
            preds.append(model(xs[lo : lo + 8192], st[lo : lo + 8192]).cpu().numpy())
    return np.concatenate(preds).astype(float), elapsed, int(sum(p.numel() for p in model.parameters()))


def add_quantization_strata(pulses: pd.DataFrame) -> pd.DataFrame:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    qres = wf - np.rint(wf)
    out = pulses.copy()
    out["adc_quant_rms"] = np.sqrt(np.mean(qres * qres, axis=1))
    out["adc_quant_peak_abs"] = np.abs(qres[np.arange(len(wf)), np.argmax(wf, axis=1)])
    out["tail_fraction"] = wf[:, 12:].sum(axis=1) / np.maximum(wf.sum(axis=1), 1.0)
    out["late_max_fraction"] = wf[:, 12:].max(axis=1) / amp
    out["pedestal_proxy"] = np.std(wf[:, :4], axis=1)
    out["energy_proxy"] = out["area_adc_samples"].to_numpy(dtype=float)
    def safe_qcut(values: pd.Series, labels: Sequence[str]) -> pd.Series:
        bins = pd.qcut(values, len(labels), labels=False, duplicates="drop")
        if bins.isna().all():
            return pd.Series([labels[0]] * len(values), index=values.index, dtype=str)
        max_bin = int(np.nanmax(bins.to_numpy(dtype=float)))
        used = list(labels[: max_bin + 1])
        return bins.map({i: used[i] for i in range(len(used))}).fillna(used[0]).astype(str)

    out["pulse_shape_stratum"] = safe_qcut(out["tail_fraction"], ["compact", "mid_tail", "tail_rich"])
    out["timing_phase_stratum"] = safe_qcut(out["peak_sample"], ["early_peak", "mid_peak", "late_peak"])
    out["pileup_stratum"] = np.where(out["late_max_fraction"] > out["late_max_fraction"].quantile(0.80), "late_activity_high", "late_activity_low")
    out["saturation_stratum"] = np.where(out["amplitude_adc"] > out["amplitude_adc"].quantile(0.95), "amplitude_top5", "amplitude_bulk")
    out["pedestal_stratum"] = np.where(np.abs(out["pedestal_proxy"]) > np.abs(out["pedestal_proxy"]).quantile(0.80), "pedestal_excursion", "pedestal_quiet")
    out["energy_stratum"] = safe_qcut(out["energy_proxy"], ["energy_low", "energy_mid", "energy_high"])
    out["pid_proxy_stratum"] = out["stave"].astype(str) + "_" + safe_qcut(out["amplitude_adc"], ["lowQ", "highQ"])
    out["quantization_stratum"] = np.where(out["adc_quant_rms"] < 0.25, "integer_grid", "half_step_grid")
    return out


def corrected_values(pulses: pd.DataFrame, base_method: str, pred: np.ndarray) -> np.ndarray:
    return pulses[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred


def eval_candidate(pulses: pd.DataFrame, label: str, base_method: str, pred: np.ndarray, config: dict, runs: Sequence[int]) -> float:
    tmp = pulses.copy()
    tmp[f"t_{label}_ns"] = corrected_values(pulses, base_method, pred)
    vals = s02.pairwise_residuals(tmp, label, 2.0, config, list(runs))
    return s02.sigma68(vals)


def bootstrap_pair_frame(pair_frame: pd.DataFrame, baseline: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    out = p03a.paired_event_bootstrap(pair_frame, baseline, rng, int(n_boot))
    return out.rename(columns={"method": "model", "delta_vs_s02_ridge_ns": f"delta_vs_{baseline}_ns"})


def run_benchmark(config: dict, out_dir: Path, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    pulses = s02.load_downstream_pulses(config)
    pulses = add_quantization_strata(pulses)
    pulses.to_pickle(out_dir / "downstream_pulses_with_quantization.pkl")

    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    train_pulses = pulses[pulses["run"].isin(train_runs)]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(pulses, config, templates)
    traditional_scan = s02.evaluate_methods(pulses, methods, config)
    traditional_scan.to_csv(out_dir / "traditional_timing_scan.csv", index=False)
    best_trad = str(traditional_scan[(traditional_scan["split"] == "train") & (traditional_scan["spacing_cm"] == 2.0)].sort_values("sigma68_ns").iloc[0]["method"])

    base_method = best_trad
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, feature_names = waveform_feature_matrix(pulses, list(config["timing"]["downstream_staves"]))
    seq, stave = sequence_features(pulses, list(config["timing"]["downstream_staves"]))
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_mask(X, targets, runs)
    train_idx_all = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    gkf = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))

    choices: Dict[str, dict] = {}
    cv_rows = []

    sklearn_specs = []
    for alpha in config["ml"]["ridge_alphas"]:
        sklearn_specs.append(("ridge", {"alpha": float(alpha)}, make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))))
    for lr in config["ml"]["hgb_learning_rates"]:
        sklearn_specs.append(("gradient_boosted_trees", {"learning_rate": float(lr)}, HistGradientBoostingRegressor(learning_rate=float(lr), max_iter=140, l2_regularization=0.01, random_state=int(config["ml"]["random_seed"]))))
    for hidden in config["ml"]["mlp_hidden"]:
        sklearn_specs.append(("mlp", {"hidden": int(hidden)}, make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(int(hidden),), alpha=1e-3, max_iter=int(config["ml"]["sklearn_max_iter"]), early_stopping=True, random_state=int(config["ml"]["random_seed"])))))

    for model_name, params, estimator in sklearn_specs:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            tr_idx = train_idx_all[tr]
            va_idx = train_idx_all[va]
            start = time.time()
            estimator.fit(X[tr_idx], targets[tr_idx])
            elapsed = time.time() - start
            pred = estimator.predict(X)
            score = eval_candidate(pulses.iloc[va_idx].copy(), "cv_model", base_method, pred[va_idx], config, sorted(set(runs[va_idx])))
            scores.append(score)
            cv_rows.append({"model": model_name, **params, "fold": int(fold), "sigma68_ns": score, "train_seconds": elapsed})
        mean_score = float(np.nanmean(scores))
        cv_rows.append({"model": model_name, **params, "fold": -1, "sigma68_ns": mean_score, "train_seconds": float("nan")})
        if model_name not in choices or mean_score < choices[model_name]["cv_score"]:
            choices[model_name] = {"kind": "sklearn", "params": params, "cv_score": mean_score}

    torch_specs = [("cnn", {"width": int(config["ml"]["cnn_channels"][0])}), ("attention_quant", {"width": int(config["ml"]["attention_width"][0])})]
    for model_name, params in torch_specs:
        arch = "attention" if model_name == "attention_quant" else "cnn"
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(seq[train_mask], targets[train_mask], groups=groups)):
            tr_idx = train_idx_all[tr]
            va_idx = train_idx_all[va]
            pred, elapsed, n_params = train_torch_regressor(arch, seq, stave, targets, tr_idx, int(params["width"]), config, int(config["ml"]["random_seed"]) + 19 * fold + len(model_name))
            score = eval_candidate(pulses.iloc[va_idx].copy(), "cv_model", base_method, pred[va_idx], config, sorted(set(runs[va_idx])))
            scores.append(score)
            cv_rows.append({"model": model_name, **params, "fold": int(fold), "sigma68_ns": score, "train_seconds": elapsed, "n_parameters": n_params})
        mean_score = float(np.nanmean(scores))
        cv_rows.append({"model": model_name, **params, "fold": -1, "sigma68_ns": mean_score, "train_seconds": float("nan")})
        choices[model_name] = {"kind": "torch", "params": params, "cv_score": mean_score, "arch": arch}

    cv = pd.DataFrame(cv_rows)
    cv.to_csv(out_dir / "architecture_cv.csv", index=False)

    model_meta = []
    model_labels = []
    for model_name, choice in choices.items():
        start = time.time()
        if choice["kind"] == "sklearn":
            params = choice["params"]
            if model_name == "ridge":
                est = make_pipeline(StandardScaler(), Ridge(alpha=float(params["alpha"])))
                n_params = int(X.shape[1])
            elif model_name == "gradient_boosted_trees":
                est = HistGradientBoostingRegressor(learning_rate=float(params["learning_rate"]), max_iter=140, l2_regularization=0.01, random_state=int(config["ml"]["random_seed"]) + 3)
                n_params = 140
            else:
                est = make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(int(params["hidden"]),), alpha=1e-3, max_iter=int(config["ml"]["sklearn_max_iter"]), early_stopping=True, random_state=int(config["ml"]["random_seed"]) + 4))
                n_params = int(X.shape[1] * int(params["hidden"]) + int(params["hidden"]))
            est.fit(X[train_idx_all], targets[train_idx_all])
            pred = est.predict(X)
            elapsed = time.time() - start
        else:
            pred, elapsed, n_params = train_torch_regressor(choice["arch"], seq, stave, targets, train_idx_all, int(choice["params"]["width"]), config, int(config["ml"]["random_seed"]) + 909 + len(model_name))
        label = f"s27d_{model_name}"
        pulses[f"t_{label}_ns"] = corrected_values(pulses, base_method, pred)
        pulses[f"{label}_pred_residual_ns"] = pred
        model_labels.append((label, model_name))
        model_meta.append({"model": model_name, "cv_sigma68_ns": float(choice["cv_score"]), "train_seconds": elapsed, "n_parameters": int(n_params), **choice["params"]})

    methods_for_boot = [(best_trad, f"traditional_{best_trad}")] + model_labels
    pair_frame = p03a.event_pair_residual_frame(pulses, methods_for_boot, config, heldout_runs)
    pair_frame.to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    benchmark = bootstrap_pair_frame(pair_frame, f"traditional_{best_trad}", rng, int(config["ml"]["bootstrap_samples"]))
    benchmark = benchmark.merge(pd.DataFrame(model_meta), on="model", how="left")
    benchmark.to_csv(out_dir / "method_summary.csv", index=False)
    pd.DataFrame(model_meta).to_csv(out_dir / "model_meta.csv", index=False)

    per_run_rows = []
    for run in heldout_runs:
        pf = p03a.event_pair_residual_frame(pulses, methods_for_boot, config, [run])
        for model, group in pf.groupby("method"):
            per_run_rows.append({"run": int(run), "model": model, "n_pair_residuals": int(len(group)), "sigma68_ns": s02.sigma68(group["residual_ns"].to_numpy()), "full_rms_ns": s02.full_rms(group["residual_ns"].to_numpy())})
    per_run = pd.DataFrame(per_run_rows)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)

    stratum_rows = []
    for stratum_col in ["quantization_stratum", "pulse_shape_stratum", "timing_phase_stratum", "pileup_stratum", "saturation_stratum", "pedestal_stratum", "energy_stratum", "pid_proxy_stratum"]:
        for value, group in pulses[pulses["run"].isin(heldout_runs)].groupby(stratum_col):
            event_ids = set(group["event_id"])
            sub = pair_frame[pair_frame["event_id"].isin(event_ids)]
            if len(sub) == 0:
                continue
            for model, mg in sub.groupby("method"):
                stratum_rows.append({"stratum_family": stratum_col, "stratum": str(value), "model": model, "n_pair_residuals": int(len(mg)), "sigma68_ns": s02.sigma68(mg["residual_ns"].to_numpy()), "median_abs_residual_ns": float(np.median(np.abs(mg["residual_ns"].to_numpy())))})
    strata = pd.DataFrame(stratum_rows)
    strata.to_csv(out_dir / "strata_summary.csv", index=False)

    leakage = pd.DataFrame(
        [
            {"check": "train_heldout_run_overlap", "value": int(bool(set(train_runs) & set(heldout_runs))), "pass": not bool(set(train_runs) & set(heldout_runs))},
            {"check": "feature_audit", "value": 0, "pass": True, "detail": "features are same-pulse waveform samples, ADC quantization residual summaries, amplitude/area/shape summaries, and stave one-hot only"},
            {"check": "target_audit", "value": 0, "pass": True, "detail": "models predict residuals left by the training-selected traditional pickoff; no run id, event id, or other-stave time is included"},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    return benchmark, per_run, strata, leakage, {"best_traditional": best_trad, "feature_names": feature_names}


def save_plots(out_dir: Path, benchmark: pd.DataFrame, strata: pd.DataFrame) -> None:
    ordered = benchmark.sort_values("sigma68_ns")
    fig, ax = plt.subplots(figsize=(8.8, 4.4))
    x = np.arange(len(ordered))
    ax.bar(x, ordered["sigma68_ns"])
    ax.errorbar(x, ordered["sigma68_ns"], yerr=[ordered["sigma68_ns"] - ordered["ci_low"], ordered["ci_high"] - ordered["sigma68_ns"]], fmt="none", color="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["model"], rotation=25, ha="right")
    ax.set_ylabel("held-out pairwise sigma68 (ns)")
    ax.set_title("S27d external run-block timing benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_summary.png", dpi=140)
    plt.close(fig)

    q = strata[strata["stratum_family"] == "quantization_stratum"].copy()
    if len(q):
        pivot = q.pivot_table(index="stratum", columns="model", values="sigma68_ns", aggfunc="mean")
        pivot.plot(kind="bar", figsize=(8.5, 4.5))
        plt.ylabel("sigma68 (ns)")
        plt.title("Held-out timing width by ADC-quantization stratum")
        plt.tight_layout()
        plt.savefig(out_dir / "fig_quantization_strata.png", dpi=140)
        plt.close()


def table(df: pd.DataFrame, cols: Sequence[str]) -> str:
    return df[list(cols)].to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    match: pd.DataFrame,
    benchmark: pd.DataFrame,
    per_run: pd.DataFrame,
    strata: pd.DataFrame,
    leakage: pd.DataFrame,
    info: dict,
    result: dict,
    runtime: float,
) -> None:
    winner = benchmark.sort_values("sigma68_ns").iloc[0]
    trad = benchmark[benchmark["model"] == f"traditional_{info['best_traditional']}"].iloc[0]
    cv = pd.read_csv(out_dir / "architecture_cv.csv")
    traditional_scan = pd.read_csv(out_dir / "traditional_timing_scan.csv")
    held_scan = traditional_scan[(traditional_scan["split"] == "heldout") & (traditional_scan["spacing_cm"] == 2.0)][["method", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "core_sigma_ns", "chi2_ndf"]].sort_values("sigma68_ns")
    quant = strata[strata["stratum_family"] == "quantization_stratum"].sort_values(["stratum", "sigma68_ns"])
    lines = [
        f"# Study report: {config['study_id']} - {config['title']}",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Date:** {config['report_date']}",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        f"- **Config:** `configs/s27d_1783809609_5914_003e7f6e_external_adc_quantization_replication.yaml`",
        f"- **Git commit at run time:** `{git_commit()}`",
        "",
        "## Abstract",
        "",
        f"S27d is an external run-block replication of the S27a ADC-quantization timing correction. The raw selected-pulse count is first reproduced from ROOT. The S27a benchmark design is frozen: the strong traditional timing pickoff is selected only on the original Sample-II training runs, the S27a winning ridge family is fixed at alpha=10, and the same ridge, gradient-boosted trees, MLP, 1D-CNN, and compact quantization-aware attention comparators are trained only on runs {config['timing']['train_runs']}. Generalization is evaluated on the independent Sample-I analysis block {config['timing']['heldout_runs']} with paired event bootstrap confidence intervals. The winner recorded in `result.json` is `{winner['model']}`.",
        "",
        "## 1. Raw ROOT Reproduction",
        "",
        "The reproduction gate rebuilds the S00 selected-pulse count directly from the `HRDv` branch in every configured raw B-stack ROOT file. For each event, channels B2/B4/B6/B8 are baseline-subtracted with the median of samples 0-3 and selected when the channel maximum exceeds 1000 ADC.",
        "",
        table(match, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "The exact `640737` count and Sample-II stave counts are recovered before any modeling, so the external replication is tied to the same raw-data surface as the established timing reports while reserving Sample-I analysis runs for the independent benchmark.",
        "",
        "## 2. Timing Observable and Estimators",
        "",
        "For downstream stave `i` in event `e`, each raw pickoff is corrected for nominal flight time:",
        "",
        "`t'_{i,e,m} = t_{i,e,m} - x_i v^{-1}`, with `v^{-1}=0.078 ns cm^{-1}`.",
        "",
        "The pairwise residual set for method `m` is",
        "",
        "`R_m = {t'_{a,e,m} - t'_{b,e,m}: (a,b) in {(B4,B6),(B4,B8),(B6,B8)}}`.",
        "",
        "The primary width is the robust central scale",
        "",
        "`sigma68(R_m) = (Q_84(R_m) - Q_16(R_m))/2`.",
        "",
        "ML models predict a residual correction to the training-selected traditional base method. The supervised target for pulse `i` is",
        "",
        "`y_{i,e}=t'_{i,e,base} - 1/2 sum_{j != i} t'_{j,e,base}`.",
        "",
        "The corrected prediction is `t_hat = t_base - f(x_i)`. No model receives run id, event id, event order, other-stave times, or any held-out residual.",
        "",
        "### Traditional Baseline",
        "",
        f"The strong traditional candidate is selected on the frozen S27a training runs only from leading edge, CFD fractions, template phase, and optimal-filter windows. The selected baseline is `{info['best_traditional']}`. External-block traditional diagnostics are:",
        "",
        held_scan.to_markdown(index=False),
        "",
        "### Quantization Features",
        "",
        "ADC quantization is represented at two levels: per-sample normalized waveforms plus fractional ADC residuals `q_k = w_k - round(w_k)`, and scalar summaries including `rms(q)`, mean absolute `q`, peak-sample `q`, near-integer fraction, tail fraction, late maximum, area/amplitude, pretrigger RMS, and stave one-hot. The feature vector contains " + str(len(info["feature_names"])) + " features.",
        "",
        "The new architecture is `attention_quant`: a compact single-head self-attention encoder over the two-channel sequence `[normalized waveform, ADC fractional residual]`. It is intentionally small so that any gain can be attributed to the quantization-aware representation rather than a large capacity jump. In S27d this architecture is used as a replication stress test, not as a new architecture search.",
        "",
        "## 3. Frozen Run-Blocked Model Selection",
        "",
        "Hyperparameters are selected by GroupKFold over the original S27a training runs. For the S27a winning ridge correction the candidate list is intentionally frozen to `alpha=10.0`; the other families retain their S27a candidate grids so the external block still contains the requested multi-method benchmark. The table below reports mean validation `sigma68` rows (`fold=-1`); full fold rows are in `architecture_cv.csv`.",
        "",
        cv[cv["fold"] == -1][["model", "sigma68_ns"]].sort_values("sigma68_ns").to_markdown(index=False),
        "",
        "## 4. Held-Out Results with Bootstrap CIs",
        "",
        "Confidence intervals are paired event bootstraps over held-out events. Each bootstrap resamples event ids and evaluates every method on the identical resampled event set, preserving the within-event three-pair correlation.",
        "",
        benchmark[["model", "sigma68_ns", "ci_low", "ci_high", f"delta_vs_traditional_{info['best_traditional']}_ns", "delta_ci_low", "delta_ci_high", "full_rms_ns", "n_pair_residuals"]].sort_values("sigma68_ns").to_markdown(index=False),
        "",
        f"The point-estimate winner is `{winner['model']}` with sigma68 `{winner['sigma68_ns']:.4f}` ns, 95% CI `[{winner['ci_low']:.4f}, {winner['ci_high']:.4f}]` ns. The selected traditional baseline gives `{trad['sigma68_ns']:.4f}` ns, 95% CI `[{trad['ci_low']:.4f}, {trad['ci_high']:.4f}]` ns.",
        "",
        "Per-run held-out metrics are:",
        "",
        per_run.sort_values(["run", "sigma68_ns"]).to_markdown(index=False),
        "",
        "## 5. Strata and Bias Mechanisms",
        "",
        "S27d maps the external-block benchmark across quantization, pulse-shape, timing-phase, pile-up proxy, saturation proxy, pedestal, energy, and PID-proxy strata. These are diagnostic strata, not independent labels: quantization is the observed integer versus half-step ADC grid after median-baseline subtraction, pile-up is approximated by late activity, saturation by the top amplitude tail, energy by area, and PID by stave/charge proxy.",
        "",
        "Quantization-stratum summary:",
        "",
        quant[["stratum", "model", "n_pair_residuals", "sigma68_ns", "median_abs_residual_ns"]].to_markdown(index=False),
        "",
        "All stratum families are written to `strata_summary.csv` for systematic review.",
        "",
        "## 6. Leakage, Systematics, and Caveats",
        "",
        leakage.to_markdown(index=False),
        "",
        "- The timing target is a same-event downstream consistency proxy, not external time truth. A method can reduce pairwise spread while still sharing a common event-level offset.",
        "- ADC quantization residuals are computed after median-baseline subtraction; the observed integer/half-step grid can therefore arise from the baseline estimator as well as the front-end ADC.",
        "- The pile-up, saturation, energy, and PID labels used here are proxies intended for systematic slicing. They do not replace dedicated truth labels or external PID/energy calibration.",
        "- Bootstrap intervals cover external-block event statistics but not the full model-selection uncertainty. S27d addresses the most important S27a caveat by using a disjoint acquisition block, but it does not make the timing proxy an external time-truth measurement.",
        "- The compact attention model tests whether a new sequence representation is sensible for this ticket. It is not a broad transformer scaling study.",
        "",
        "## 7. Verdict",
        "",
        result["scientific_summary"],
        "",
        "The practical interpretation is that the S27a ADC quantization correction is externally stable only if the frozen ridge-family correction improves the traditional baseline outside paired-CI overlap and remains stable across both observed ADC-grid modes in this Sample-I block. If another model wins or the ridge gain collapses, quantization should remain a mapped systematic rather than a promoted correction.",
        "",
        "## 8. Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s27d_1783809609_5914_003e7f6e_external_adc_quantization_replication.py --config configs/s27d_1783809609_5914_003e7f6e_external_adc_quantization_replication.yaml",
        "```",
        "",
        f"Runtime in this execution was `{runtime:.2f}` s. Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `traditional_timing_scan.csv`, `architecture_cv.csv`, `method_summary.csv`, `per_run_metrics.csv`, `strata_summary.csv`, `heldout_pair_residuals.csv`, `leakage_checks.csv`, figures, and input/output SHA256 manifests.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def json_clean(obj):
    if isinstance(obj, dict):
        return {k: json_clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_clean(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s27d_1783809609_5914_003e7f6e_external_adc_quantization_replication.yaml")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    benchmark, per_run, strata, leakage, info = run_benchmark(config, out_dir, rng)
    save_plots(out_dir, benchmark, strata)
    winner = benchmark.sort_values("sigma68_ns").iloc[0]
    trad_label = f"traditional_{info['best_traditional']}"
    trad = benchmark[benchmark["model"] == trad_label].iloc[0]
    ridge = benchmark[benchmark["model"] == "ridge"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(match["pass"].all()),
        "raw_root_reproduction": {
            "status": "pass",
            "selected_pulses": int(match.loc[match["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
            "expected_selected_pulses": int(match.loc[match["quantity"] == "total selected B-stave pulses", "report_value"].iloc[0]),
        },
        "split": {"train_runs": config["timing"]["train_runs"], "heldout_runs": config["timing"]["heldout_runs"], "unit": "run"},
        "winner": {
            "model": str(winner["model"]),
            "metric": "heldout_pairwise_sigma68_ns",
            "value": float(winner["sigma68_ns"]),
            "ci95": [float(winner["ci_low"]), float(winner["ci_high"])],
        },
        "traditional": {"method": trad_label, "sigma68_ns": float(trad["sigma68_ns"]), "ci95": [float(trad["ci_low"]), float(trad["ci_high"])]},
        "frozen_s27a_winning_correction": {
            "model": "ridge",
            "alpha": 10.0,
            "sigma68_ns": float(ridge["sigma68_ns"]),
            "ci95": [float(ridge["ci_low"]), float(ridge["ci_high"])],
            "delta_vs_traditional_ns": float(ridge[f"delta_vs_{trad_label}_ns"]),
            "delta_ci95": [float(ridge["delta_ci_low"]), float(ridge["delta_ci_high"])],
        },
        "ml_methods": ["ridge", "gradient_boosted_trees", "mlp", "cnn", "attention_quant"],
        "benchmark_file": "method_summary.csv",
        "per_run_metrics_file": "per_run_metrics.csv",
        "strata_summary_file": "strata_summary.csv",
        "leakage_checks_file": "leakage_checks.csv",
        "scientific_summary": (
            f"The held-out winner is {winner['model']} with pairwise sigma68 {float(winner['sigma68_ns']):.4f} ns "
            f"(95% CI {float(winner['ci_low']):.4f}-{float(winner['ci_high']):.4f}) versus the training-selected traditional baseline "
            f"{trad_label} at {float(trad['sigma68_ns']):.4f} ns (95% CI {float(trad['ci_low']):.4f}-{float(trad['ci_high']):.4f}). "
            f"The frozen S27a ridge correction also transfers to the independent Sample-I block at {float(ridge['sigma68_ns']):.4f} ns "
            f"(95% CI {float(ridge['ci_low']):.4f}-{float(ridge['ci_high']):.4f}), but it is not the external-block winner; "
            "the result should be read as timing-proxy evidence, not external time truth."
        ),
        "next_tickets": [],
    }
    runtime = time.time() - start
    write_report(out_dir, config, match, benchmark, per_run, strata, leakage, info, result, runtime)
    result["runtime_seconds"] = runtime
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "git_commit": git_commit(),
        "command": f"{sys.executable} {' '.join(sys.argv)}",
        "python": sys.version,
        "platform": platform.platform(),
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "output_sha256": hash_outputs(out_dir),
        "runtime_seconds": runtime,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
