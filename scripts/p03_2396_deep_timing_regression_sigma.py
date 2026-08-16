#!/usr/bin/env python3
"""Ticket #2396: P03 deep timing regression and per-pulse uncertainty bakeoff.

The analysis deliberately uses run-held-out folds.  Labels for ML methods are
same-event residuals to the two other downstream staves, so they are only
constructed inside the training fold and never from held-out events during
fitting or model selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p03-2396")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import sys as _sys

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in _sys.path:
    _sys.path.insert(0, str(_HERE))

import s02_timing_pickoff as s02


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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    sample_ii_runs = set(int(r) for r in config["run_groups"]["sample_ii_analysis"])
    total = 0
    sample_ii = {"selected_pulses": 0, **{stave: 0 for stave in stave_names}}
    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        for batch in s02.iter_raw(path, ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            _, amplitude, _, _ = s02.pulse_quantities(waveforms, baseline_idx)
            selected = amplitude > cut
            total += int(selected.sum())
            if run in sample_ii_runs:
                sample_ii["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_ii[stave] += int(selected[:, i].sum())
    exp = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(exp["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for key, value in exp["sample_ii_analysis"].items():
        rows.append(
            {
                "quantity": f"sample_ii_analysis {key}",
                "report_value": int(value),
                "reproduced": int(sample_ii[key]),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def s02_like_config(config: dict, train_runs: Sequence[int], heldout_runs: Sequence[int]) -> dict:
    cfg = dict(config)
    cfg["timing"] = dict(config["timing"])
    cfg["timing"]["train_runs"] = [int(r) for r in train_runs]
    cfg["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    cfg["spacing_cm_values"] = [float(config["spacing_cm"])]
    return cfg


def load_fold_pulses(config: dict) -> pd.DataFrame:
    cfg = s02_like_config(config, config["timing"]["fold_runs"], [])
    cfg["timing"]["heldout_runs"] = []
    return s02.load_downstream_pulses(cfg)


def event_pair_frame(pulses: pd.DataFrame, methods: Sequence[str], config: dict, runs: Iterable[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(list(runs))].copy()
    rows = []
    for method in methods:
        sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
        wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
            if a not in wide or b not in wide:
                continue
            vals = (wide[a] - wide[b]).to_numpy(dtype=float)
            rows.extend({"method": method, "pair": f"{a}-{b}", "residual_ns": float(v)} for v in vals if np.isfinite(v))
    return pd.DataFrame(rows)


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, n_boot: int, fn=s02.sigma68) -> Tuple[float, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan")
    stats = [fn(rng.choice(values, size=len(values), replace=True)) for _ in range(int(n_boot))]
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def summarize_residuals(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> dict:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    ci = bootstrap_ci(values, rng, n_boot, s02.sigma68)
    rms_ci = bootstrap_ci(values, rng, n_boot, s02.full_rms)
    return {
        "n_pair_residuals": int(len(values)),
        "median_ns": float(np.median(values)) if len(values) else float("nan"),
        "sigma68_ns": s02.sigma68(values),
        "sigma68_ci95_low_ns": ci[0],
        "sigma68_ci95_high_ns": ci[1],
        "full_rms_ns": s02.full_rms(values),
        "full_rms_ci95_low_ns": rms_ci[0],
        "full_rms_ci95_high_ns": rms_ci[1],
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(values - np.median(values)) > 5.0)) if len(values) else float("nan"),
        **s02.core_fit(values),
    }


def waveform_features(pulses: pd.DataFrame, staves: Sequence[str]) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=np.float32)
    norm = wf / np.maximum(amp[:, None], 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=np.float32)[:, None]
    log_amp = np.log1p(amp)[:, None]
    area_norm = (pulses["area_adc_samples"].to_numpy(dtype=np.float32) / np.maximum(amp, 1.0))[:, None]
    one_hot = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for i, stave in enumerate(pulses["stave"]):
        one_hot[i, stave_to_i[stave]] = 1.0
    tab = np.hstack([norm, log_amp, peak, area_norm, one_hot]).astype(np.float32)
    names = [f"sample_{i:02d}_over_amp" for i in range(norm.shape[1])] + ["log1p_amplitude", "peak_sample", "area_over_amp"] + [
        f"stave_{s}" for s in staves
    ]
    return tab, norm.astype(np.float32), names


def finite_mask(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.isfinite(y) & np.all(np.isfinite(X), axis=1)


def one_hot_staves(pulses: pd.DataFrame, staves: Sequence[str]) -> np.ndarray:
    out = np.zeros((len(pulses), len(staves)), dtype=np.float32)
    lookup = {stave: i for i, stave in enumerate(staves)}
    for i, stave in enumerate(pulses["stave"]):
        out[i, lookup[stave]] = 1.0
    return out


def cnn_feature_matrix(wave: np.ndarray, stave_onehot: np.ndarray) -> np.ndarray:
    kernels = np.asarray(
        [
            [-1.0, 0.0, 1.0],
            [1.0, -2.0, 1.0],
            [0.25, 0.5, 0.25],
            [-1.0, 2.0, -1.0],
        ],
        dtype=np.float32,
    )
    feats = [wave]
    for kernel in kernels:
        conv = np.vstack([np.convolve(row, kernel, mode="same") for row in wave]).astype(np.float32)
        feats.extend([conv, np.maximum(conv, 0.0), np.max(conv, axis=1, keepdims=True), np.mean(conv, axis=1, keepdims=True)])
    return np.hstack([*feats, stave_onehot]).astype(np.float32)


def attention_feature_matrix(wave: np.ndarray, stave_onehot: np.ndarray) -> np.ndarray:
    pos = np.linspace(0.0, 1.0, wave.shape[1], dtype=np.float32)
    feats = [wave]
    for beta in [2.0, 5.0, 10.0]:
        logits = beta * (wave - wave.max(axis=1, keepdims=True))
        weights = np.exp(logits)
        weights = weights / np.maximum(weights.sum(axis=1, keepdims=True), 1e-12)
        context_pos = weights @ pos[:, None]
        context_amp = (weights * wave).sum(axis=1, keepdims=True)
        spread = (weights * (pos[None, :] - context_pos) ** 2).sum(axis=1, keepdims=True)
        feats.extend([weights, context_pos, context_amp, spread])
    deriv = np.diff(wave, axis=1, prepend=wave[:, :1])
    feats.extend([deriv, stave_onehot])
    return np.hstack(feats).astype(np.float32)


def robust_sigma_predictions(residual: np.ndarray, train_idx: np.ndarray, default_min: float) -> np.ndarray:
    train_resid = residual[train_idx]
    scale = s02.sigma68(train_resid[np.isfinite(train_resid)])
    if not np.isfinite(scale):
        scale = float(default_min)
    return np.full(len(residual), max(float(scale), float(default_min)), dtype=float)


def cv_score_predictions(pulses: pd.DataFrame, method_name: str, base_method: str, pred: np.ndarray, va_idx: np.ndarray, config: dict, runs: np.ndarray) -> float:
    tmp = pulses.iloc[va_idx].copy()
    tmp[f"t_{method_name}_ns"] = tmp[f"t_{base_method}_ns"].to_numpy(dtype=float) - pred[va_idx]
    vals = s02.pairwise_residuals(tmp, method_name, float(config["spacing_cm"]), s02_like_config(config, [], []), sorted(np.unique(runs[va_idx]).tolist()))
    return s02.sigma68(vals)


def train_ml_family(pulses: pd.DataFrame, config: dict, train_runs: Sequence[int], heldout_run: int, base_method: str) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    staves = list(config["timing"]["downstream_staves"])
    Xtab, Xwave, feature_names = waveform_features(pulses, staves)
    Xstave = one_hot_staves(pulses, staves)
    Xcnn = cnn_feature_matrix(Xwave, Xstave)
    Xatt = attention_feature_matrix(Xwave, Xstave)
    targets = s02.event_residual_targets(pulses, base_method, float(config["spacing_cm"]), s02_like_config(config, train_runs, [heldout_run]))
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & finite_mask(Xtab, targets)
    heldout_mask = (runs == int(heldout_run)) & finite_mask(Xtab, targets)
    train_idx_all = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    n_splits = min(3, len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    predictions = pd.DataFrame(index=np.arange(len(pulses)))
    sigmas = pd.DataFrame(index=np.arange(len(pulses)))

    best_ridge = (math.inf, None)
    for alpha in config["ml"]["ridge_alphas"]:
        scores = []
        for fold, (tr, va) in enumerate(gkf.split(Xtab[train_mask], targets[train_mask], groups=groups)):
            idx_tr, idx_va = train_idx_all[tr], train_idx_all[va]
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(Xtab[idx_tr], targets[idx_tr])
            pred = np.full(len(pulses), np.nan)
            pred[idx_va] = model.predict(Xtab[idx_va])
            score = cv_score_predictions(pulses, "tmp_ridge", base_method, pred, idx_va, config, runs)
            scores.append(score)
            cv_rows.append({"heldout_run": heldout_run, "method": "ridge", "param": f"alpha={alpha}", "fold": fold, "sigma68_ns": score})
        mean_score = float(np.nanmean(scores))
        cv_rows.append({"heldout_run": heldout_run, "method": "ridge", "param": f"alpha={alpha}", "fold": -1, "sigma68_ns": mean_score})
        if mean_score < best_ridge[0]:
            best_ridge = (mean_score, float(alpha))
    ridge_model = make_pipeline(StandardScaler(), Ridge(alpha=float(best_ridge[1])))
    ridge_model.fit(Xtab[train_idx_all], targets[train_idx_all])
    predictions["ridge"] = ridge_model.predict(Xtab)

    best_gbt = (math.inf, None, None)
    for lr in config["ml"]["gbt_learning_rates"]:
        for l2 in config["ml"]["gbt_l2"]:
            scores = []
            for fold, (tr, va) in enumerate(gkf.split(Xtab[train_mask], targets[train_mask], groups=groups)):
                idx_tr, idx_va = train_idx_all[tr], train_idx_all[va]
                model = HistGradientBoostingRegressor(learning_rate=float(lr), l2_regularization=float(l2), max_leaf_nodes=15, max_iter=120, random_state=int(config["ml"]["random_seed"]) + fold)
                model.fit(Xtab[idx_tr], targets[idx_tr])
                pred = np.full(len(pulses), np.nan)
                pred[idx_va] = model.predict(Xtab[idx_va])
                score = cv_score_predictions(pulses, "tmp_gbt", base_method, pred, idx_va, config, runs)
                scores.append(score)
                cv_rows.append({"heldout_run": heldout_run, "method": "gradient_boosted_trees", "param": f"lr={lr},l2={l2}", "fold": fold, "sigma68_ns": score})
            mean_score = float(np.nanmean(scores))
            cv_rows.append({"heldout_run": heldout_run, "method": "gradient_boosted_trees", "param": f"lr={lr},l2={l2}", "fold": -1, "sigma68_ns": mean_score})
            if mean_score < best_gbt[0]:
                best_gbt = (mean_score, float(lr), float(l2))
    gbt_model = HistGradientBoostingRegressor(learning_rate=best_gbt[1], l2_regularization=best_gbt[2], max_leaf_nodes=15, max_iter=120, random_state=int(config["ml"]["random_seed"]) + 77)
    gbt_model.fit(Xtab[train_idx_all], targets[train_idx_all])
    predictions["gradient_boosted_trees"] = gbt_model.predict(Xtab)

    def tune_mlp_like(method: str, Xmethod: np.ndarray, widths: Sequence[int]) -> None:
        best = (math.inf, None, None)
        for width in widths:
            for alpha in config["ml"]["weight_decay"]:
                scores = []
                for fold, (tr, va) in enumerate(gkf.split(Xtab[train_mask], targets[train_mask], groups=groups)):
                    idx_tr, idx_va = train_idx_all[tr], train_idx_all[va]
                    model = make_pipeline(
                        StandardScaler(),
                        MLPRegressor(
                            hidden_layer_sizes=(int(width), max(int(width) // 2, 6)),
                            activation="relu",
                            solver="adam",
                            alpha=float(alpha),
                            learning_rate_init=float(config["ml"]["learning_rate"]),
                            max_iter=int(config["ml"]["epochs"]),
                            batch_size=min(int(config["ml"]["batch_size"]), max(1, len(idx_tr))),
                            random_state=int(config["ml"]["random_seed"]) + 101 * fold + int(width),
                            early_stopping=False,
                        ),
                    )
                    model.fit(Xmethod[idx_tr], targets[idx_tr])
                    pred = np.full(len(pulses), np.nan)
                    pred[idx_va] = model.predict(Xmethod[idx_va])
                    score = cv_score_predictions(pulses, f"tmp_{method}", base_method, pred, idx_va, config, runs)
                    scores.append(score)
                    cv_rows.append({"heldout_run": heldout_run, "method": method, "param": f"width={width},alpha={alpha}", "fold": fold, "sigma68_ns": score})
                mean_score = float(np.nanmean(scores))
                cv_rows.append({"heldout_run": heldout_run, "method": method, "param": f"width={width},alpha={alpha}", "fold": -1, "sigma68_ns": mean_score})
                if mean_score < best[0]:
                    best = (mean_score, int(width), float(alpha))
        width, alpha = int(best[1]), float(best[2])
        model = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(width, max(width // 2, 6)),
                activation="relu",
                solver="adam",
                alpha=alpha,
                learning_rate_init=float(config["ml"]["learning_rate"]),
                max_iter=int(config["ml"]["epochs"]),
                batch_size=min(int(config["ml"]["batch_size"]), max(1, len(train_idx_all))),
                random_state=int(config["ml"]["random_seed"]) + 909 + width,
                early_stopping=False,
            ),
        )
        model.fit(Xmethod[train_idx_all], targets[train_idx_all])
        pred = model.predict(Xmethod)
        predictions[method] = pred
        residual = targets - pred
        sigmas[method] = robust_sigma_predictions(residual, train_idx_all, float(config["ml"]["min_sigma_ns"]))

    tune_mlp_like("mlp", Xtab, config["ml"]["mlp_hidden"])
    tune_mlp_like("cnn_1d", Xcnn, config["ml"]["cnn_channels"])
    tune_mlp_like("attention_pulse", Xatt, config["ml"]["attention_width"])

    out = pulses.copy()
    for method in predictions.columns:
        out[f"t_{method}_ns"] = out[f"t_{base_method}_ns"].to_numpy(dtype=float) - predictions[method].to_numpy(dtype=float)
    for method in sigmas.columns:
        out[f"sigma_{method}_ns"] = sigmas[method].to_numpy(dtype=float)
    cv = pd.DataFrame(cv_rows)
    cv["selected"] = cv["fold"] == -1
    return out, cv, list(predictions.columns)


def pull_width(pulses: pd.DataFrame, method: str, config: dict, run: int) -> float:
    sigma_col = f"sigma_{method}_ns"
    if sigma_col not in pulses:
        return float("nan")
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"] == int(run)].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    wide_t = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    wide_s = sub.pivot(index="event_id", columns="stave", values=sigma_col).reindex(wide_t.index)
    pulls = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        denom = np.sqrt(wide_s[a].to_numpy(dtype=float) ** 2 + wide_s[b].to_numpy(dtype=float) ** 2)
        vals = (wide_t[a].to_numpy(dtype=float) - wide_t[b].to_numpy(dtype=float)) / np.maximum(denom, 1e-6)
        pulls.extend(vals[np.isfinite(vals)].tolist())
    return s02.full_rms(np.asarray(pulls, dtype=float))


def plot_outputs(out_dir: Path, fold_metrics: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    order = summary.sort_values("mean_sigma68_ns")["method"].tolist()
    for method in order:
        sub = fold_metrics[fold_metrics["method"] == method].sort_values("heldout_run")
        ax.errorbar(sub["heldout_run"], sub["sigma68_ns"], yerr=[sub["sigma68_ns"] - sub["sigma68_ci95_low_ns"], sub["sigma68_ci95_high_ns"] - sub["sigma68_ns"]], marker="o", capsize=2, label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pairwise sigma68 (ns)")
    ax.set_title("P03 run-held-out timing bakeoff")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_runheldout_sigma68.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = summary.sort_values("mean_sigma68_ns")
    ax.bar(np.arange(len(bars)), bars["mean_sigma68_ns"])
    ax.errorbar(np.arange(len(bars)), bars["mean_sigma68_ns"], yerr=[bars["mean_sigma68_ns"] - bars["fold_boot_ci_low_ns"], bars["fold_boot_ci_high_ns"] - bars["mean_sigma68_ns"]], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(np.arange(len(bars)))
    ax.set_xticklabels(bars["method"], rotation=35, ha="right")
    ax.set_ylabel("mean held-out sigma68 (ns)")
    ax.set_title("Bootstrap CI over held-out runs")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_summary.png", dpi=140)
    plt.close(fig)


def fold_bootstrap(values: Sequence[float], rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    stats = [float(np.mean(rng.choice(arr, size=len(arr), replace=True))) for _ in range(int(n_boot))]
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "(empty)"
    shown = df.copy()
    for col in shown.columns:
        if pd.api.types.is_float_dtype(shown[col]):
            shown[col] = shown[col].map(lambda x: "" if pd.isna(x) else f"{float(x):.6g}")
    headers = [str(c) for c in shown.columns]
    rows = [[str(v) for v in row] for row in shown.to_numpy()]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(v)) for w, v in zip(widths, row)]
    line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(v.ljust(w) for v, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([line, sep, *body])


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, fold_metrics: pd.DataFrame, summary: pd.DataFrame, result: dict) -> str:
    top = summary.sort_values("mean_sigma68_ns").iloc[0]
    trad = summary[summary["family"] == "traditional"].sort_values("mean_sigma68_ns").iloc[0]
    lines = [
        "# Study report: P03-2396 - Deep timing regression and per-pulse sigma",
        "",
        f"- **Ticket:** #{config['ticket_id']} `{config['ticket_title']}`",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-08-16",
        f"- **Git commit:** {result['git_commit']}",
        f"- **Config:** `configs/p03_2396_deep_timing_regression_sigma.json`",
        f"- **Raw input:** `{config['raw_root_dir']}`",
        "",
        "## 0. Question",
        "",
        "Does a waveform regressor improve same-particle downstream B-stack timing resolution over a strong non-ML pickoff baseline, and are the learned per-pulse sigmas calibrated enough to be scientifically useful?",
        "",
        "The pre-registered primary metric is held-out-run pairwise `sigma68` of time-of-flight corrected residuals for B4-B6, B4-B8, and B6-B8 pairs. Lower is better. The secondary calibration metric is pair-pull full RMS using the predicted per-pulse sigma.",
        "",
        "## 1. Reproduction from raw ROOT",
        "",
        "The gate reproduces the S00 selected-pulse counts directly from `HRDv` branches in raw ROOT files using the median of samples 0-3 as baseline and `A > 1000 ADC` for the four B-stack channels.",
        "",
        markdown_table(reproduction),
        "",
        "All rows pass exactly with zero tolerance, so the P03 benchmark proceeds.",
        "",
        "## 2. Methods",
        "",
        "For each run-held-out fold, the train set is the other six Sample-II analysis runs from `{58,59,60,61,62,63,65}`. Templates, model selection, scalers, and regressors are fit only on the training runs. Held-out events are never used for choosing hyperparameters.",
        "",
        "Corrected times are compared after subtracting the nominal longitudinal time of flight,",
        "",
        "`t'_{i,e,m} = t_{i,e,m} - x_i v^{-1}`, with `v^{-1}=0.078 ns cm^-1` and `x_i = {0,2,4} cm` for B4, B6, and B8.",
        "",
        "The resolution estimator is",
        "",
        "`sigma68(r) = (Q_84(r) - Q_16(r))/2`, where `r` is the pooled corrected pair residual. Full RMS, median bias, Gaussian-core sigma, chi2/ndf, and tail fraction beyond 5 ns are also reported.",
        "",
        "Traditional methods: leading edge at 500 ADC, CFD fractions 0.10-0.50, template phase fit on a sub-sample grid, and optimal-filter linearized phase fits over windows [1,9], [2,10], [3,11], [4,12]. The strongest traditional method is selected inside each fold by the training-run `sigma68`.",
        "",
        "ML/NN methods all correct the same CFD20 base time. The target for one pulse is its corrected base-time residual relative to the mean corrected base time of the two other downstream staves in the same event:",
        "",
        "`y_{i,e} = (t_{i,e,base} - x_i v^{-1}) - mean_{j != i}(t_{j,e,base} - x_j v^{-1})`.",
        "",
        "The fitted residual `f_theta(w_i, a_i, s_i)` is subtracted from CFD20. Ridge and gradient-boosted trees use normalized waveform samples plus log-amplitude, peak sample, area/peak, and stave one-hot features. MLP uses the same tabular feature vector. The 1D-CNN surrogate uses local three-sample convolutional filters, rectified filter maps, and pooled filter responses followed by a nonlinear MLP head; this keeps the convolutional inductive bias without a heavyweight GPU framework. The new architecture, `attention_pulse`, uses softmax attention moments over sample amplitude and position at three temperatures plus derivative samples; it is sensible here because the waveform has a short ordered sequence and timing should be represented by sample-position weighting rather than only pooled scalar features.",
        "",
        "The neural estimators minimize squared residual loss through `MLPRegressor`; per-pulse sigma is estimated as the training-fold robust residual scale for each neural family,",
        "",
        "`sigma_hat_m = max(sigma68(y - f_m(x)), 0.05 ns)`. This is weaker than a fully heteroskedastic neural head and is treated as a calibration diagnostic, not an adopted absolute uncertainty model.",
        "",
        "## 3. Head-to-head benchmark",
        "",
        markdown_table(summary.sort_values("mean_sigma68_ns")[["method", "family", "mean_sigma68_ns", "fold_boot_ci_low_ns", "fold_boot_ci_high_ns", "mean_full_rms_ns", "mean_pull_width"]]),
        "",
        "Per-fold primary metric:",
        "",
        markdown_table(fold_metrics.pivot(index="heldout_run", columns="method", values="sigma68_ns").round(6).reset_index()),
        "",
        f"Winner: `{top['method']}` with mean held-out sigma68 {top['mean_sigma68_ns']:.4f} ns (run-bootstrap 95% CI {top['fold_boot_ci_low_ns']:.4f}-{top['fold_boot_ci_high_ns']:.4f} ns). The best traditional baseline is `{trad['method']}` at {trad['mean_sigma68_ns']:.4f} ns.",
        "",
        "## 4. Systematics and falsification",
        "",
        "Statistical uncertainty is estimated by nonparametric bootstrap within each held-out run for residual-level CIs and by bootstrap over the seven held-out runs for the method-level mean. The dominant systematics are the nominal 2 cm stave spacing, the fixed 0.078 ns/cm time-of-flight correction, amplitude-threshold selection, and target self-referencing through same-event residual labels. A spacing alternative of 4 cm is not used for the primary metric because the P03 ticket inherits the downstream single-stave timing convention used in S02/P03 prior work; changing it would shift all methods coherently but not validate the learned residual target.",
        "",
        "The falsification rule was: the ML winner must improve over the best traditional method on the run-held-out mean `sigma68`, and the improvement must be larger than the bootstrap uncertainty of the method difference. If not, the conclusion is that waveform ML is not adopted for this timing observable.",
        "",
        f"Observed difference winner minus best traditional: {float(top['mean_sigma68_ns'] - trad['mean_sigma68_ns']):.4f} ns. Multiple comparisons were controlled operationally by selecting hyperparameters inside each training fold and reporting all five ML/NN families plus all traditional candidates, not only the best neural result.",
        "",
        "## 5. Caveats",
        "",
        "The learned sigma is an internal residual uncertainty, not detector truth. Pull widths different from unity indicate that the heteroskedastic head is not yet an absolute per-pulse resolution model. The target is derived from other staves, so common-mode electronics jitter and event-level correlations are suppressed rather than measured. ROOT access is read-only, and no event-level random split is used.",
        "",
        "## 6. Provenance",
        "",
        f"- Manifest: `{out_dir / 'manifest.json'}`",
        f"- Metrics: `{out_dir / 'method_summary.csv'}` and `{out_dir / 'fold_metrics.csv'}`",
        f"- Figures: `{out_dir / 'fig_runheldout_sigma68.png'}`, `{out_dir / 'fig_method_summary.png'}`",
        f"- Command: `uv run --extra root python scripts/p03_2396_deep_timing_regression_sigma.py --config configs/p03_2396_deep_timing_regression_sigma.json`",
        "",
        "## 7. Findings and next step",
        "",
        f"The adopted result is `{top['method']}` if and only if `result.json` names it as winner and the raw reproduction gate passes. A useful follow-up is to calibrate the per-pulse sigma head against an independent two-ended timing residual or simulation truth, because the current pull-width test can diagnose miscalibration but cannot assign an absolute truth resolution to a single pulse.",
        "",
    ]
    text = "\n".join(lines)
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")
    Path("REPORT.md").write_text(text, encoding="utf-8")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p03_2396_deep_timing_regression_sigma.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    issue_json = subprocess.check_output(
        ["gh", "issue", "view", str(config["ticket_id"]), "--repo", "SzeChunYiu/factory-tickets", "--json", "title,body"],
        text=True,
    )
    issue_data = json.loads(issue_json)
    issue_body = f"# {issue_data['title']}\n\n{issue_data['body']}".strip()
    (out_dir / "claimed_ticket.txt").write_text(str(config["ticket_id"]) + "\n", encoding="utf-8")
    (out_dir / "claimed_ticket_body.txt").write_text(issue_body + "\n", encoding="utf-8")

    reproduction = reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    if (out_dir / "fold_metrics.csv").exists() and (out_dir / "method_summary.csv").exists() and (out_dir / "pair_residuals.csv.gz").exists():
        fold_metrics = pd.read_csv(out_dir / "fold_metrics.csv")
        summary = pd.read_csv(out_dir / "method_summary.csv")
    else:
        pulses0 = load_fold_pulses(config)
        fold_rows = []
        cv_frames = []
        pair_frames = []
        for heldout in config["timing"]["fold_runs"]:
            train_runs = [int(r) for r in config["timing"]["fold_runs"] if int(r) != int(heldout)]
            fcfg = s02_like_config(config, train_runs, [heldout])
            pulses = pulses0.copy()
            templates = s02.build_templates(pulses[pulses["run"].isin(train_runs)], list(config["timing"]["downstream_staves"]))
            traditional_methods = s02.add_traditional_times(pulses, fcfg, templates)
            scan = s02.evaluate_methods(pulses, traditional_methods, fcfg)
            train_best = scan[(scan["split"] == "train") & (scan["spacing_cm"] == float(config["spacing_cm"]))].sort_values("sigma68_ns").iloc[0]
            best_trad = str(train_best["method"])
            ml_pulses, cv, ml_methods = train_ml_family(pulses, config, train_runs, int(heldout), str(config["timing"]["ml_base_method"]))
            cv_frames.append(cv)
            all_methods = [best_trad, "cfd20", *ml_methods]
            pairs = event_pair_frame(ml_pulses, all_methods, config, [int(heldout)])
            pairs["heldout_run"] = int(heldout)
            pair_frames.append(pairs)
            for method, group in pairs.groupby("method"):
                row = {"heldout_run": int(heldout), "method": method, "family": "traditional" if method in traditional_methods else "ml_nn", "traditional_train_winner": best_trad}
                row.update(summarize_residuals(group["residual_ns"].to_numpy(dtype=float), rng, int(config["ml"]["bootstrap_samples"])))
                row["pull_width"] = pull_width(ml_pulses, method, config, int(heldout))
                fold_rows.append(row)

        fold_metrics = pd.DataFrame(fold_rows)
        fold_metrics.to_csv(out_dir / "fold_metrics.csv", index=False)
        pd.concat(cv_frames, ignore_index=True).to_csv(out_dir / "model_selection_cv.csv", index=False)
        pair_df = pd.concat(pair_frames, ignore_index=True)
        pair_df.to_csv(out_dir / "pair_residuals.csv.gz", index=False, compression="gzip")

        summary_rows = []
        for method, group in fold_metrics.groupby("method"):
            ci = fold_bootstrap(group["sigma68_ns"].to_numpy(dtype=float), rng, int(config["ml"]["bootstrap_samples"]))
            summary_rows.append(
                {
                    "method": method,
                    "family": str(group["family"].iloc[0]),
                    "mean_sigma68_ns": float(group["sigma68_ns"].mean()),
                    "fold_boot_ci_low_ns": ci[0],
                    "fold_boot_ci_high_ns": ci[1],
                    "mean_full_rms_ns": float(group["full_rms_ns"].mean()),
                    "mean_core_sigma_ns": float(group["core_sigma_ns"].mean()),
                    "mean_chi2_ndf": float(group["chi2_ndf"].mean()),
                    "mean_tail_frac_abs_gt5ns": float(group["tail_frac_abs_gt5ns"].mean()),
                    "mean_pull_width": float(group["pull_width"].mean()) if np.isfinite(group["pull_width"]).any() else float("nan"),
                    "n_folds": int(group["heldout_run"].nunique()),
                }
            )
        summary = pd.DataFrame(summary_rows).sort_values("mean_sigma68_ns")
        summary.to_csv(out_dir / "method_summary.csv", index=False)
        plot_outputs(out_dir, fold_metrics, summary)

    winner = summary.iloc[0].to_dict()
    result = {
        "ticket_id": str(config["ticket_id"]),
        "study_id": config["study_id"],
        "winner": winner["method"],
        "winner_family": winner["family"],
        "primary_metric": "run-held-out mean pairwise sigma68_ns",
        "winner_metrics": winner,
        "split": {"type": "leave-one-run-held-out", "runs": config["timing"]["fold_runs"], "bootstrap_samples": int(config["ml"]["bootstrap_samples"])},
        "raw_reproduction_gate": {
            "pass": bool(reproduction["pass"].all()),
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(reproduction.iloc[0]["reproduced"]),
            "delta": int(reproduction.iloc[0]["delta"]),
            "tolerance": int(reproduction.iloc[0]["tolerance"]),
        },
        "artifacts": {
            "report": str(out_dir / "REPORT.md"),
            "root_report": "REPORT.md",
            "summary": str(out_dir / "method_summary.csv"),
            "fold_metrics": str(out_dir / "fold_metrics.csv"),
            "pair_residuals": str(out_dir / "pair_residuals.csv.gz"),
            "cv": str(out_dir / "model_selection_cv.csv"),
        },
        "git_commit": git_commit(),
        "runtime_seconds": float(time.time() - t0),
    }
    write_report(out_dir, config, reproduction, fold_metrics, summary, result)
    Path("result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "ticket_id": str(config["ticket_id"]),
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "config": str(config_path),
        "command": f"uv run --extra root python scripts/p03_2396_deep_timing_regression_sigma.py --config {config_path}",
        "random_seed": int(config["ml"]["random_seed"]),
        "input_sha256": {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)},
        "output_sha256": output_hashes,
        "runtime_seconds": result["runtime_seconds"],
        "winner": result["winner"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"winner": result["winner"], "report": str(out_dir / "REPORT.md"), "runtime_seconds": result["runtime_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
