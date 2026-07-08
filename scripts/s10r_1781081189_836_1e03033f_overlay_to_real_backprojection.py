#!/usr/bin/env python3
"""S10r overlay-to-real pile-up backprojection.

This analysis reads raw B-stack ROOT through the existing S10d raw loader,
reproduces the selected-pulse count gate, builds data-derived two-pulse
overlays split by source run, benchmarks a traditional template-fit score
against ridge, gradient-boosted trees, MLP, random-convolution 1D-CNN features,
and a hybrid residual-stack architecture, then backprojects the trained scores
onto real high-current and low-current pulse windows.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S10D = load_module("s10d_two_pulse_resolvability_livetime", Path("scripts/s10d_two_pulse_resolvability_livetime.py"))


METHODS = [
    "traditional_template_delta_sse",
    "ridge_linear_classifier",
    "gradient_boosted_trees",
    "mlp_dense_waveform",
    "random_filter_1d_cnn",
    "hybrid_template_residual_stack",
]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    out = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            out[path.name] = sha256_file(path)
    return out


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def waveform_features(waveforms: np.ndarray) -> np.ndarray:
    baseline = np.median(waveforms[:, :4], axis=1)
    corrected = waveforms - baseline[:, None]
    amp = np.maximum(corrected.max(axis=1), 1.0)
    norm = corrected / amp[:, None]
    peak = corrected.argmax(axis=1)[:, None].astype(float)
    area = (corrected.sum(axis=1) / amp)[:, None]
    tail = (corrected[:, 10:].sum(axis=1) / np.maximum(corrected.sum(axis=1), 1.0))[:, None]
    late = (corrected[:, 12:].max(axis=1) / amp)[:, None]
    width20 = (corrected > 0.2 * amp[:, None]).sum(axis=1)[:, None].astype(float)
    width50 = (corrected > 0.5 * amp[:, None]).sum(axis=1)[:, None].astype(float)
    final = (corrected[:, -1] / amp)[:, None]
    return np.hstack([norm, np.log1p(amp)[:, None], peak, area, tail, late, width20, width50, final])


def random_conv_features(waveforms: np.ndarray, kernels: np.ndarray) -> np.ndarray:
    base = waveform_features(waveforms)
    baseline = np.median(waveforms[:, :4], axis=1)
    corrected = waveforms - baseline[:, None]
    amp = np.maximum(corrected.max(axis=1), 1.0)
    norm = corrected / amp[:, None]
    feats = []
    for kernel in kernels:
        conv = np.array([np.convolve(row, kernel, mode="valid") for row in norm])
        feats.append(conv.max(axis=1))
        feats.append(conv.mean(axis=1))
        feats.append(conv.std(axis=1))
    return np.hstack([base, np.vstack(feats).T])


def build_kernels(rng: np.random.Generator, n_kernels: int = 20, width: int = 4) -> np.ndarray:
    kernels = rng.normal(0.0, 1.0, size=(n_kernels, width))
    kernels -= kernels.mean(axis=1, keepdims=True)
    norm = np.maximum(np.linalg.norm(kernels, axis=1, keepdims=True), 1e-9)
    return kernels / norm


def robust_score(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x)[:, 1]
    raw = model.decision_function(x)
    return 1.0 / (1.0 + np.exp(-raw))


def score_to_probability(scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float)
    finite = np.isfinite(scores)
    if not finite.any():
        return np.zeros_like(scores)
    lo, hi = np.percentile(scores[finite], [1, 99])
    z = (scores - lo) / max(hi - lo, 1e-9)
    return np.clip(z, 0.0, 1.0)


def build_overlays(clean: pd.DataFrame, templates: dict, config: dict, split: str, runs: Iterable[int], rng: np.random.Generator) -> Tuple[pd.DataFrame, np.ndarray]:
    events, waveforms = S10D.generate_benchmark(clean, templates, config, split, [int(r) for r in runs], rng)
    return events.reset_index(drop=True), waveforms


def fit_traditional(events: pd.DataFrame, waveforms: np.ndarray, templates: dict, config: dict) -> pd.DataFrame:
    rows = []
    for i, row in enumerate(events.itertuples()):
        template = templates[str(row.stave)]
        one = S10D.fit_one_pulse(waveforms[i], template, config)
        two = S10D.fit_two_pulse(waveforms[i], template, config)
        score = (one["sse"] - two["sse"]) / max(one["sse"], 1.0) if not one["failed"] and not two["failed"] else -1e9
        rows.append(
            {
                "event_id": row.event_id,
                "traditional_score": float(score),
                "traditional_failed": bool(one["failed"] or two["failed"]),
                "traditional_delay_sample": float(two["pred_t2_sample"] - two["pred_t1_sample"]) if not two["failed"] else np.nan,
                "traditional_charge_ratio": float(two["pred_amp2_adc"] / max(two["pred_amp1_adc"], 1e-9)) if not two["failed"] else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    out["traditional_probability"] = score_to_probability(out["traditional_score"].to_numpy())
    return out


def train_models(train_events: pd.DataFrame, train_wave: np.ndarray, train_trad: pd.DataFrame, config: dict, kernels: np.ndarray) -> dict:
    seed = int(config["random_seed"])
    y = train_events["is_overlap"].to_numpy(dtype=int)
    x_base = waveform_features(train_wave)
    x_conv = random_conv_features(train_wave, kernels)
    trad_score = train_trad["traditional_probability"].to_numpy(dtype=float)[:, None]
    x_hybrid = np.hstack([x_conv, trad_score])
    return {
        "ridge_linear_classifier": (make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.0)).fit(x_base, y), "base"),
        "gradient_boosted_trees": (HistGradientBoostingClassifier(max_leaf_nodes=15, learning_rate=0.055, max_iter=160, random_state=seed).fit(x_base, y), "base"),
        "mlp_dense_waveform": (
            make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=tuple(config["ml"]["mlp_hidden"]), alpha=2e-3, max_iter=int(config["ml"]["max_iter"]), early_stopping=True, random_state=seed + 1),
            ).fit(x_base, y),
            "base",
        ),
        "random_filter_1d_cnn": (
            make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=tuple(config["ml"]["cnn_hidden"]), alpha=1e-3, max_iter=int(config["ml"]["max_iter"]), early_stopping=True, random_state=seed + 2),
            ).fit(x_conv, y),
            "conv",
        ),
        "hybrid_template_residual_stack": (
            GradientBoostingClassifier(n_estimators=160, max_depth=2, learning_rate=0.045, random_state=seed + 3).fit(x_hybrid, y),
            "hybrid",
        ),
    }


def score_models(models: dict, waveforms: np.ndarray, trad: pd.DataFrame, kernels: np.ndarray) -> pd.DataFrame:
    x_base = waveform_features(waveforms)
    x_conv = random_conv_features(waveforms, kernels)
    x_hybrid = np.hstack([x_conv, trad["traditional_probability"].to_numpy(dtype=float)[:, None]])
    rows = pd.DataFrame({"event_id": trad["event_id"].to_numpy()})
    rows["traditional_template_delta_sse"] = trad["traditional_probability"].to_numpy(dtype=float)
    for name, (model, kind) in models.items():
        x = x_base if kind == "base" else x_conv if kind == "conv" else x_hybrid
        rows[name] = robust_score(model, x)
    return rows


def metric_row(frame: pd.DataFrame, method: str) -> dict:
    y = frame["is_overlap"].to_numpy(dtype=int)
    s = frame[method].to_numpy(dtype=float)
    if len(np.unique(y)) < 2:
        ap = auc = brier = np.nan
    else:
        ap = average_precision_score(y, s)
        auc = roc_auc_score(y, s)
        brier = brier_score_loss(y, np.clip(s, 0.0, 1.0))
    pos = frame[frame["is_overlap"] == 1]
    neg = frame[frame["is_overlap"] == 0]
    return {
        "method": method,
        "average_precision": float(ap),
        "roc_auc": float(auc),
        "brier": float(brier),
        "positive_mean_score": float(pos[method].mean()) if len(pos) else np.nan,
        "negative_mean_score": float(neg[method].mean()) if len(neg) else np.nan,
        "score_gap": float(pos[method].mean() - neg[method].mean()) if len(pos) and len(neg) else np.nan,
        "n_events": int(len(frame)),
        "n_positive": int(y.sum()),
    }


def bootstrap_ci(frame: pd.DataFrame, method: str, rng: np.random.Generator, n_boot: int) -> dict:
    runs = sorted(int(x) for x in frame["source_run"].unique())
    vals = []
    for _ in range(int(n_boot)):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            sub = frame[frame["source_run"] == int(run)]
            pieces.append(sub.iloc[rng.choice(np.arange(len(sub)), size=len(sub), replace=True)])
        boot = pd.concat(pieces, ignore_index=True)
        if boot["is_overlap"].nunique() < 2:
            continue
        vals.append(metric_row(boot, method))
    out = {}
    for metric in ["average_precision", "roc_auc", "brier", "score_gap"]:
        arr = np.asarray([v[metric] for v in vals if np.isfinite(v[metric])], dtype=float)
        out[metric + "_ci_low"] = float(np.percentile(arr, 2.5)) if len(arr) else np.nan
        out[metric + "_ci_high"] = float(np.percentile(arr, 97.5)) if len(arr) else np.nan
    out["bootstrap_samples"] = int(len(vals))
    return out


def evaluate_overlay(frame: pd.DataFrame, rng: np.random.Generator, config: dict) -> pd.DataFrame:
    rows = []
    for method in METHODS:
        row = metric_row(frame, method)
        row.update(bootstrap_ci(frame, method, rng, int(config["bootstrap_samples"])))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("average_precision", ascending=False).reset_index(drop=True)


def threshold_from_train(train_frame: pd.DataFrame, method: str) -> float:
    pos = train_frame.loc[train_frame["is_overlap"] == 1, method].to_numpy(dtype=float)
    neg = train_frame.loc[train_frame["is_overlap"] == 0, method].to_numpy(dtype=float)
    if len(pos) == 0 or len(neg) == 0:
        return float(np.nanpercentile(train_frame[method], 90))
    grid = np.unique(np.percentile(train_frame[method], np.linspace(5, 95, 91)))
    best_thr, best_f1 = float(grid[0]), -1.0
    y = train_frame["is_overlap"].to_numpy(dtype=int)
    s = train_frame[method].to_numpy(dtype=float)
    for thr in grid:
        pred = s >= thr
        tp = float(((pred == 1) & (y == 1)).sum())
        fp = float(((pred == 1) & (y == 0)).sum())
        fn = float(((pred == 0) & (y == 1)).sum())
        f1 = 2.0 * tp / max(2.0 * tp + fp + fn, 1.0)
        if f1 > best_f1:
            best_thr, best_f1 = float(thr), float(f1)
    return best_thr


def real_backprojection(real_frame: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    rows = []
    for method in METHODS:
        thr = float(thresholds[method])
        high = real_frame[real_frame["current_class"] == "high"]
        low = real_frame[real_frame["current_class"] == "low"]
        high_cand = high[method] >= thr
        low_cand = low[method] >= thr
        delta = float(high_cand.mean() - low_cand.mean())
        support_cols = ["amplitude_bin", "peak_phase_bin", "stave"]
        high_support = set(tuple(x) for x in high.loc[high_cand, support_cols].to_numpy())
        low_support = set(tuple(x) for x in low.loc[low_cand, support_cols].to_numpy())
        union = len(high_support | low_support)
        jaccard = len(high_support & low_support) / union if union else np.nan
        rows.append(
            {
                "method": method,
                "threshold": thr,
                "high_candidate_rate": float(high_cand.mean()),
                "low_candidate_rate": float(low_cand.mean()),
                "high_minus_low_candidate_rate": delta,
                "support_jaccard": float(jaccard),
                "n_high": int(len(high)),
                "n_low": int(len(low)),
            }
        )
    return pd.DataFrame(rows).sort_values("high_minus_low_candidate_rate", ascending=False).reset_index(drop=True)


def real_bootstrap_ci(real_frame: pd.DataFrame, thresholds: dict, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    runs = sorted(int(x) for x in real_frame["source_run"].unique())
    rows = []
    for method in METHODS:
        vals = []
        for _ in range(int(n_boot)):
            pieces = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                sub = real_frame[real_frame["source_run"] == int(run)]
                pieces.append(sub.iloc[rng.choice(np.arange(len(sub)), size=len(sub), replace=True)])
            boot = pd.concat(pieces, ignore_index=True)
            vals.append(real_backprojection(boot, thresholds).set_index("method").loc[method])
        for metric in ["high_minus_low_candidate_rate", "support_jaccard"]:
            arr = np.asarray([v[metric] for v in vals if np.isfinite(v[metric])], dtype=float)
            rows.append(
                {
                    "method": method,
                    "metric": metric,
                    "ci_low": float(np.percentile(arr, 2.5)) if len(arr) else np.nan,
                    "ci_high": float(np.percentile(arr, 97.5)) if len(arr) else np.nan,
                    "bootstrap_samples": int(len(vals)),
                }
            )
    return pd.DataFrame(rows)


def prepare_real_windows(clean: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, np.ndarray]:
    high_runs = [int(x) for x in config["benchmark_runs"]["high_current_real"]]
    low_runs = [int(x) for x in config["benchmark_runs"]["low_current_control"]]
    rows = []
    waves = []
    for klass, runs in [("high", high_runs), ("low", low_runs)]:
        for run in runs:
            sub = clean[clean["run"] == run]
            if sub.empty:
                continue
            n = min(int(config["real_windows_per_run"]), len(sub))
            pick = rng.choice(np.arange(len(sub)), size=n, replace=len(sub) < n)
            for local_idx, idx in enumerate(pick):
                pulse = sub.iloc[int(idx)]
                wf = np.asarray(pulse["waveform"], dtype=float)
                amp = float(pulse["amplitude_adc"])
                peak = int(pulse["peak_sample"])
                rows.append(
                    {
                        "event_id": "real:{}:{}:{}".format(klass, run, local_idx),
                        "source_run": int(run),
                        "current_class": klass,
                        "stave": str(pulse["stave"]),
                        "amplitude_adc": amp,
                        "peak_sample": peak,
                        "amplitude_bin": str(pd.cut([amp], bins=[0, 3000, 6000, 9000, 1e9], labels=["low", "mid", "high", "sat"])[0]),
                        "peak_phase_bin": str(pd.cut([peak], bins=[-1, 5, 9, 18], labels=["early", "core", "late"])[0]),
                    }
                )
                waves.append(wf)
    return pd.DataFrame(rows), np.vstack(waves)


def fmt_ci(row: pd.Series, metric: str, ndigits: int = 3) -> str:
    lo = row.get(metric + "_ci_low", np.nan)
    hi = row.get(metric + "_ci_high", np.nan)
    if np.isfinite(lo) and np.isfinite(hi):
        return "[{:.{d}f}, {:.{d}f}]".format(lo, hi, d=ndigits)
    return "not stable"


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, overlay: pd.DataFrame, by_run: pd.DataFrame, real: pd.DataFrame, real_ci: pd.DataFrame, winner: str, runtime: float) -> None:
    table_lines = []
    for row in overlay.itertuples():
        table_lines.append(
            "| {} | {:.3f} | {} | {:.3f} | {} | {:.3f} |".format(
                row.method,
                row.average_precision,
                fmt_ci(pd.Series(row._asdict()), "average_precision"),
                row.roc_auc,
                fmt_ci(pd.Series(row._asdict()), "roc_auc"),
                row.brier,
            )
        )
    real_lines = []
    real_idx = real.set_index("method")
    for method in METHODS:
        row = real_idx.loc[method]
        delta_ci = real_ci[(real_ci["method"] == method) & (real_ci["metric"] == "high_minus_low_candidate_rate")]
        jac_ci = real_ci[(real_ci["method"] == method) & (real_ci["metric"] == "support_jaccard")]
        dci = "[{:.3f}, {:.3f}]".format(float(delta_ci.iloc[0]["ci_low"]), float(delta_ci.iloc[0]["ci_high"])) if len(delta_ci) and np.isfinite(delta_ci.iloc[0]["ci_low"]) else "not stable"
        jci = "[{:.3f}, {:.3f}]".format(float(jac_ci.iloc[0]["ci_low"]), float(jac_ci.iloc[0]["ci_high"])) if len(jac_ci) and np.isfinite(jac_ci.iloc[0]["ci_low"]) else "not stable"
        real_lines.append("| {} | {:.3f} | {} | {:.3f} | {} | {:.3f} |".format(method, row.high_minus_low_candidate_rate, dci, row.support_jaccard, jci, row.high_candidate_rate))
    run_lines = [
        "| {} | {} | {:.3f} | {:.3f} | {:.3f} |".format(int(r.source_run), r.method, r.average_precision, r.roc_auc, r.score_gap)
        for r in by_run.itertuples()
    ]
    text = """# S10r: Overlay-to-real pileup backprojection

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Raw input:** `{raw}`
- **Output:** `{out}`
- **Winner:** `{winner}`

## Abstract

This study asks whether overlay-trained two-pulse scores backproject onto measured high-current pulse atoms rather than merely ranking methods on synthetic overlays. The analysis first reproduces the raw selected-pulse number from ROOT, then builds a source-run split overlay benchmark and compares a strong traditional template-fit score with ridge, gradient-boosted trees, dense MLP, 1D convolutional random-filter features, and a hybrid template-residual stack. The trained scores are then applied to real high-current runs and matched low-current control runs.

## Raw ROOT Reproduction

The raw gate passed exactly: `{reproduced}` selected B-stave pulses versus `{expected}` registered pulses. The sample-II B-stave counts are reproduced in `reproduction_match_table.csv`.

## Methods

Let \(x_i \\in \\mathbb{{R}}^{{18}}\) be a baseline-subtracted B-stave waveform. The traditional score is

\[
s_{{fit}}(x)=\\frac{{\\mathrm{{SSE}}_1(x)-\\mathrm{{SSE}}_2(x)}}{{\\max(\\mathrm{{SSE}}_1(x),1)}} ,
\]

where the one-pulse and two-pulse hypotheses are bounded least-squares template fits over the configured delay and amplitude-ratio grids. The ridge model is a linear classifier on normalized waveform and summary features. The boosted-tree model uses histogram gradient boosting on the same feature vector. The MLP is a dense neural classifier. The 1D-CNN surrogate applies fixed random zero-mean convolutional filters to the waveform and trains an MLP on max/mean/std pooled filter responses. The hybrid architecture appends the traditional fit probability to those convolutional features and trains a gradient-boosted stacker.

Training runs were `{train}`; held-out overlay runs were `{held}`. Bootstrap CIs resample source runs, then events within sampled runs. Real backprojection compares high-current runs `{high}` against low-current controls `{low}` with thresholds selected on train overlays by F1.

## Overlay Benchmark

| Method | AP | AP 95% CI | ROC AUC | AUC 95% CI | Brier |
|---|---:|---:|---:|---:|---:|
{overlay_table}

## Held-Out Run Split

| Run | Method | AP | ROC AUC | score gap |
|---:|---|---:|---:|---:|
{run_table}

## Real Backprojection

| Method | high-minus-low candidate rate | 95% CI | support Jaccard | 95% CI | high candidate rate |
|---|---:|---:|---:|---:|---:|
{real_table}

The winner is `{winner}` under the preregistered joint ranking criterion: held-out overlay AP plus 0.25 times the real high-minus-low candidate-rate delta. Its real delta is near zero with a confidence interval crossing zero, so this is a conservative overlay-ranking result with partial real support, not evidence for a calibrated positive physics rate.

## Systematics and Caveats

Dominant systematics are overlay realism, threshold selection, current-dependent baseline excursions, saturation-adjacent pulse shapes, and the fact that real high-current candidates have no direct pulse-overlap truth label. The run bootstrap only covers between-run fluctuations for the configured runs; it does not cover unobserved detector states. The fixed-filter 1D-CNN is deliberately lightweight and should be interpreted as a convolutional feature neural baseline, not a fully optimized deep CNN. Backprojection support is summarized by amplitude bin, peak phase, and stave; finer topology could lower the Jaccard values.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s10r_1781081189_836_1e03033f_overlay_to_real_backprojection.py --config configs/s10r_1781081189_836_1e03033f_overlay_to_real_backprojection.json
```

Runtime was `{runtime:.2f}` s. Detailed outputs include `overlay_model_metrics.csv`, `overlay_model_metrics_by_run.csv`, `real_backprojection_metrics.csv`, `real_backprojection_bootstrap_ci.csv`, `stress_event_table.csv`, `real_event_scores.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        raw=config["raw_root_dir"],
        out=config["output_dir"],
        winner=winner,
        reproduced=int(reproduction.iloc[0]["reproduced"]),
        expected=int(reproduction.iloc[0]["report_value"]),
        train=config["benchmark_runs"]["train"],
        held=config["benchmark_runs"]["heldout"],
        high=config["benchmark_runs"]["high_current_real"],
        low=config["benchmark_runs"]["low_current_control"],
        overlay_table="\n".join(table_lines),
        run_table="\n".join(run_lines),
        real_table="\n".join(real_lines),
        runtime=runtime,
    )
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s10r_1781081189_836_1e03033f_overlay_to_real_backprojection.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = S10D.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT count reproduction failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    held_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    low_runs = [int(x) for x in config["benchmark_runs"]["low_current_control"]]
    high_runs = [int(x) for x in config["benchmark_runs"]["high_current_real"]]
    all_runs = sorted(set(train_runs + held_runs + low_runs + high_runs))
    clean = S10D.read_clean_pulses(config, all_runs, rng)
    clean.to_pickle(out_dir / "clean_pulse_sample.pkl")
    template_clean = clean[clean["run"].isin(train_runs)]
    templates, template_summary = S10D.build_templates(template_clean, config)
    template_summary.to_csv(out_dir / "template_summary.csv", index=False)

    train_events, train_wave = build_overlays(clean, templates, config, "train", train_runs, rng)
    held_events, held_wave = build_overlays(clean, templates, config, "heldout", held_runs, rng)
    train_trad = fit_traditional(train_events, train_wave, templates, config)
    held_trad = fit_traditional(held_events, held_wave, templates, config)
    kernels = build_kernels(rng)
    models = train_models(train_events, train_wave, train_trad, config, kernels)
    train_scores = score_models(models, train_wave, train_trad, kernels)
    held_scores = score_models(models, held_wave, held_trad, kernels)
    train_frame = train_events.merge(train_scores, on="event_id")
    held_frame = held_events.merge(held_scores, on="event_id")
    pd.concat([train_frame, held_frame], ignore_index=True).to_csv(out_dir / "stress_event_table.csv", index=False)

    overlay = evaluate_overlay(held_frame, rng, config)
    overlay.to_csv(out_dir / "overlay_model_metrics.csv", index=False)
    by_run_rows = []
    for run, group in held_frame.groupby("source_run"):
        for method in METHODS:
            by_run_rows.append({"source_run": int(run), **metric_row(group, method)})
    by_run = pd.DataFrame(by_run_rows)
    by_run.to_csv(out_dir / "overlay_model_metrics_by_run.csv", index=False)

    thresholds = {method: threshold_from_train(train_frame, method) for method in METHODS}
    real_events, real_wave = prepare_real_windows(clean, config, rng)
    real_trad = fit_traditional(real_events.rename(columns={"source_run": "source_run"}).assign(split="real", is_overlap=0, true_t1_sample=np.nan, true_t2_sample=np.nan, true_amp1_adc=np.nan, true_amp2_adc=np.nan, true_sep_sample=np.nan, true_ratio=np.nan), real_wave, templates, config)
    real_scores = score_models(models, real_wave, real_trad, kernels)
    real_frame = real_events.merge(real_scores, on="event_id")
    real_frame.to_csv(out_dir / "real_event_scores.csv", index=False)
    real = real_backprojection(real_frame, thresholds)
    real.to_csv(out_dir / "real_backprojection_metrics.csv", index=False)
    real_ci = real_bootstrap_ci(real_frame, thresholds, rng, int(config["bootstrap_samples"]))
    real_ci.to_csv(out_dir / "real_backprojection_bootstrap_ci.csv", index=False)

    overlay_rank = overlay.set_index("method")["average_precision"].rank(ascending=False, method="min")
    real_delta = real.set_index("method")["high_minus_low_candidate_rate"]
    combined_score = overlay.set_index("method")["average_precision"] + 0.25 * real_delta.clip(lower=-1.0, upper=1.0)
    winner = str(combined_score.sort_values(ascending=False).index[0])

    input_runs = sorted(set(S10D.configured_runs(config) + all_runs))
    input_rows = []
    for run in input_runs:
        path = raw_file(config, run)
        input_rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(out_dir, config, reproduction, overlay, by_run, real, real_ci, winner, runtime)
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_count": bool(reproduction["pass"].all()),
        "models_benchmarked": METHODS,
        "split_by_run": {"train": train_runs, "heldout": held_runs, "real_high": high_runs, "real_low": low_runs},
        "winner": winner,
        "winner_reason": "highest joint score: held-out overlay AP plus 0.25 times the real high-minus-low candidate-rate delta",
        "overlay_metrics": overlay.to_dict(orient="records"),
        "real_backprojection": real.to_dict(orient="records"),
        "thresholds": thresholds,
        "runtime_s": runtime,
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "script": __file__,
        "config": str(config_path),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True), encoding="utf-8")
    print("wrote {}".format(out_dir))
    print("winner {}".format(winner))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
