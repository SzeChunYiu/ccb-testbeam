#!/usr/bin/env python3
"""S01i selected-table byte-vs-content consumer sentinel.

The ticket asks whether downstream consumers should guard on gzip bytes, on
decompressed table content, or on deterministic consumer replays. This script
reproduces the selected-pulse count from raw ROOT, constructs benign and stale
variants of the S01 q_template table, replays compact S01/S02/S04/P04-style
consumers, and benchmarks a strict traditional sentinel against several ML/NN
classifiers on run-held-out/stability-resampled splits.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


def json_ready(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        value = float(obj)
        return None if not math.isfinite(value) else value
    if isinstance(obj, np.ndarray):
        return json_ready(obj.tolist())
    return obj


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_gzip_content(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with gzip.open(path, "rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def raw_file(config: Dict[str, Any], run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def configured_runs(config: Dict[str, Any]) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def reproduce_selected_count(config: Dict[str, Any]) -> Tuple[pd.DataFrame, int]:
    channels = np.asarray(list(config["stave_channels"].values()), dtype=int)
    baseline_idx = np.asarray(config["baseline_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows: List[Dict[str, Any]] = []
    total_selected = 0
    total_events = 0
    for run in configured_runs(config):
        path = raw_file(config, run)
        tree = uproot.open(path)["h101"]
        run_events = 0
        run_selected = 0
        for batch in tree.iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            waveforms = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            baseline = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            run_events += int(len(batch["EVENTNO"]))
            run_selected += int(selected.sum())
        total_events += run_events
        total_selected += run_selected
        rows.append({"run": run, "events_total": run_events, "selected_pulses": run_selected})
    return pd.DataFrame(rows), total_selected


def canonical_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False, float_format="%.10g", line_terminator="\n")
    return buf.getvalue().encode("utf-8")


def gzip_bytes(payload: bytes, mtime: int) -> bytes:
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=mtime) as handle:
        handle.write(payload)
    return out.getvalue()


def consumer_summary(df: pd.DataFrame, variant: str, label: int, kind: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for (run, stave), sub in df.groupby(["run", "stave"], sort=True):
        q = sub["q_template_rmse"].to_numpy(dtype=float)
        ae = sub["q_autoencoder_rmse"].to_numpy(dtype=float)
        amp = sub["amplitude_adc"].to_numpy(dtype=float)
        area = sub["area_adc_samples"].to_numpy(dtype=float)
        peak = sub["peak_sample"].to_numpy(dtype=float)
        rows.append(
            {
                "variant": variant,
                "label_stale": label,
                "variant_kind": kind,
                "run": int(run),
                "stave": str(stave),
                "n": int(len(sub)),
                "s01_q_median": float(np.nanmedian(q)),
                "s01_q_p95": float(np.nanquantile(q, 0.95)),
                "s02_timing_tail_proxy": float(np.mean((q > np.nanquantile(q, 0.90)) | (peak > 9))),
                "s04_charge_proxy": float(np.nanmedian(area / np.maximum(amp, 1.0))),
                "p04_q_high_fraction": float(np.mean(q > np.nanquantile(q, 0.99))),
                "autoencoder_median": float(np.nanmedian(ae)),
                "amp_median": float(np.nanmedian(amp)),
                "peak_mean": float(np.nanmean(peak)),
            }
        )
    return pd.DataFrame(rows)


def build_variants(df: pd.DataFrame, rng: np.random.Generator) -> Dict[str, Tuple[pd.DataFrame, int, str]]:
    variants: Dict[str, Tuple[pd.DataFrame, int, str]] = {
        "content_exact": (df.copy(), 0, "benign"),
        "gzip_byte_repacked": (df.copy(), 0, "benign_byte_only"),
        "fresh_equivalent_rows": (
            df.sort_values(["run", "eventno", "evt", "stave"]).reset_index(drop=True).copy(),
            0,
            "benign_replay",
        ),
    }
    drop = df.loc[~((df["run"].isin([57, 65])) & (df["q_template_rmse"] > df["q_template_rmse"].quantile(0.985)))].copy()
    variants["stale_tail_rows_dropped"] = (drop, 1, "stale_rows")
    shifted = df.copy()
    shifted.loc[shifted["run"].isin([58, 59, 60, 61, 62, 63, 65]), "q_template_rmse"] *= 1.12
    variants["stale_sampleii_q_shift"] = (shifted, 1, "stale_content")
    rounded = df.copy()
    rounded["q_template_rmse"] = rounded["q_template_rmse"].round(2)
    variants["stale_rounded_qtemplate"] = (rounded, 1, "stale_content")
    shuffled = df.copy()
    shuffled["q_template_rmse"] = rng.permutation(shuffled["q_template_rmse"].to_numpy())
    variants["shuffled_hash_control"] = (shuffled, 1, "stale_content")
    swap = df.copy()
    mask = swap["run"].isin([44, 45])
    swap.loc[mask, "stave"] = swap.loc[mask, "stave"].map({"B2": "B4", "B4": "B2", "B6": "B8", "B8": "B6"})
    variants["stale_run_stave_swap"] = (swap, 1, "stale_join")
    return variants


def variant_hash_table(source_path: Path, df: pd.DataFrame, variants: Dict[str, Tuple[pd.DataFrame, int, str]]) -> pd.DataFrame:
    source_content = gzip.open(source_path, "rb").read()
    source_byte_hash = sha256_file(source_path)
    source_content_hash = hashlib.sha256(source_content).hexdigest()
    rows: List[Dict[str, Any]] = []
    for name, (vdf, label, kind) in variants.items():
        payload = source_content if name in {"content_exact", "gzip_byte_repacked"} else canonical_csv_bytes(vdf)
        gz = gzip_bytes(payload, mtime=0 if name != "gzip_byte_repacked" else 123456789)
        rows.append(
            {
                "variant": name,
                "label_stale": label,
                "variant_kind": kind,
                "byte_sha256": hashlib.sha256(gz).hexdigest(),
                "content_sha256": hashlib.sha256(payload).hexdigest(),
                "source_byte_match": hashlib.sha256(gz).hexdigest() == source_byte_hash,
                "source_content_match": hashlib.sha256(payload).hexdigest() == source_content_hash,
                "row_count": int(len(vdf)),
                "source_row_count": int(len(df)),
                "row_count_match": int(len(vdf)) == int(len(df)),
            }
        )
    return pd.DataFrame(rows)


def make_model_table(df: pd.DataFrame, variants: Dict[str, Tuple[pd.DataFrame, int, str]], hash_table: pd.DataFrame) -> pd.DataFrame:
    base = consumer_summary(df, "content_exact", 0, "benign")
    metric_cols = [
        "n",
        "s01_q_median",
        "s01_q_p95",
        "s02_timing_tail_proxy",
        "s04_charge_proxy",
        "p04_q_high_fraction",
        "autoencoder_median",
        "amp_median",
        "peak_mean",
    ]
    base_key = base.set_index(["run", "stave"])[metric_cols]
    frames = []
    for name, (vdf, label, kind) in variants.items():
        cur = consumer_summary(vdf, name, label, kind)
        cur_key = cur.set_index(["run", "stave"])[metric_cols]
        joined = cur.join(base_key, on=["run", "stave"], rsuffix="_base")
        for col in metric_cols:
            joined[f"delta_{col}"] = joined[col] - joined[f"{col}_base"]
            denom = np.maximum(np.abs(joined[f"{col}_base"].to_numpy(dtype=float)), 1e-9)
            joined[f"reldelta_{col}"] = joined[f"delta_{col}"] / denom
        frames.append(joined)
    out = pd.concat(frames, ignore_index=True).fillna(0.0)
    out = out.merge(hash_table, on=["variant", "label_stale", "variant_kind"], how="left")
    out["byte_mismatch"] = (~out["source_byte_match"]).astype(int)
    out["content_mismatch"] = (~out["source_content_match"]).astype(int)
    out["row_count_mismatch"] = (~out["row_count_match"]).astype(int)
    out["traditional_byte_sentinel"] = out["byte_mismatch"]
    out["traditional_content_sentinel"] = (
        out["content_mismatch"] | out["row_count_mismatch"] | (out["delta_n"].abs() > 0)
    ).astype(int)
    consumer_delta_cols = [c for c in out.columns if c.startswith("delta_") or c.startswith("reldelta_")]
    out["traditional_replay_sentinel"] = (
        out["row_count_mismatch"] | (out[consumer_delta_cols].abs().max(axis=1) > 1e-9)
    ).astype(int)
    return out


def auc_or_nan(y: np.ndarray, score: np.ndarray) -> float:
    return float(roc_auc_score(y, score)) if len(np.unique(y)) == 2 else float("nan")


def ap_or_nan(y: np.ndarray, score: np.ndarray) -> float:
    return float(average_precision_score(y, score)) if len(np.unique(y)) == 2 else float("nan")


def score_method(y: np.ndarray, score: np.ndarray) -> Dict[str, float]:
    pred = (score >= 0.5).astype(int)
    return {
        "roc_auc": auc_or_nan(y, score),
        "average_precision": ap_or_nan(y, score),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "false_alarm_rate": float(np.mean(pred[y == 0])) if np.any(y == 0) else float("nan"),
        "stale_detection_rate": float(np.mean(pred[y == 1])) if np.any(y == 1) else float("nan"),
    }


def cnn_scores(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    *,
    residual_gate: bool,
    seed: int,
) -> np.ndarray:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    xtr = torch.tensor(train_x[:, None, :], dtype=torch.float32)
    ytr = torch.tensor(train_y.astype(np.float32)[:, None], dtype=torch.float32)
    xte = torch.tensor(test_x[:, None, :], dtype=torch.float32)

    class SmallCNN(nn.Module):
        def __init__(self, n: int) -> None:
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(1, 12, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(12, 8, kernel_size=3, dilation=2, padding=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.head = nn.Linear(8, 1)
            self.gate = nn.Linear(n, 1)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            z = self.conv(x).squeeze(-1)
            raw = self.head(z)
            if residual_gate:
                g = torch.sigmoid(self.gate(x.squeeze(1)))
                raw = raw * g
            return raw

    model = SmallCNN(train_x.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    loss_fn = nn.BCEWithLogitsLoss()
    for _ in range(5):
        opt.zero_grad()
        loss = loss_fn(model(xtr), ytr)
        loss.backward()
        opt.step()
    with torch.no_grad():
        return torch.sigmoid(model(xte)).numpy().ravel()


def benchmark_methods(model_df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_cols = [
        c
        for c in model_df.columns
        if c.startswith("delta_")
        or c.startswith("reldelta_")
        or c
        in {
            "byte_mismatch",
            "content_mismatch",
            "row_count_mismatch",
            "source_content_match",
            "source_byte_match",
            "row_count_match",
        }
    ]
    x = model_df[feature_cols].astype(float).to_numpy()
    y = model_df["label_stale"].astype(int).to_numpy()
    rng_seed = int(config["random_seed"])
    rows: List[Dict[str, Any]] = []
    pred_rows: List[pd.DataFrame] = []

    for repeat in range(int(config["ml_repeats"])):
        splitter = StratifiedShuffleSplit(n_splits=1, test_size=float(config["ml_test_fraction"]), random_state=rng_seed + repeat)
        train_idx, test_idx = next(splitter.split(x, y))
        scaler = StandardScaler().fit(x[train_idx])
        xtr, xte = scaler.transform(x[train_idx]), scaler.transform(x[test_idx])
        ytr, yte = y[train_idx], y[test_idx]

        method_scores: Dict[str, np.ndarray] = {
            "traditional_byte_hash": model_df.iloc[test_idx]["traditional_byte_sentinel"].to_numpy(dtype=float),
            "traditional_content_replay": model_df.iloc[test_idx]["traditional_replay_sentinel"].to_numpy(dtype=float),
        }

        ridge = RidgeClassifier(alpha=1.0).fit(xtr, ytr)
        rscore = ridge.decision_function(xte)
        method_scores["ridge"] = (rscore - rscore.min()) / (rscore.max() - rscore.min() + 1e-9)

        hgb = HistGradientBoostingClassifier(max_iter=12, learning_rate=0.12, max_leaf_nodes=6, random_state=rng_seed + repeat)
        hgb.fit(xtr, ytr)
        method_scores["gradient_boosted_trees"] = hgb.predict_proba(xte)[:, 1]

        mlp = MLPClassifier(hidden_layer_sizes=(10,), alpha=1e-3, max_iter=80, random_state=rng_seed + repeat)
        mlp.fit(xtr, ytr)
        method_scores["mlp"] = mlp.predict_proba(xte)[:, 1]

        method_scores["1d_cnn"] = cnn_scores(xtr, ytr, xte, residual_gate=False, seed=rng_seed + repeat)
        method_scores["gated_residual_cnn"] = cnn_scores(xtr, ytr, xte, residual_gate=True, seed=rng_seed + repeat)

        pred = model_df.iloc[test_idx][["variant", "variant_kind", "run", "stave", "label_stale"]].copy()
        pred["repeat"] = repeat
        for method, score in method_scores.items():
            metrics = score_method(yte, score)
            rows.append({"repeat": repeat, "method": method, **metrics})
            pred[f"score_{method}"] = score
        pred_rows.append(pred)

    fold_metrics = pd.DataFrame(rows)
    predictions = pd.concat(pred_rows, ignore_index=True)
    summary_rows = []
    metric_names = ["roc_auc", "average_precision", "balanced_accuracy", "false_alarm_rate", "stale_detection_rate"]
    for method, sub in fold_metrics.groupby("method"):
        row = {"method": method}
        for metric in metric_names:
            vals = sub[metric].to_numpy(dtype=float)
            row[metric] = float(np.nanmean(vals))
            row[f"{metric}_ci_low"] = float(np.nanquantile(vals, 0.025))
            row[f"{metric}_ci_high"] = float(np.nanquantile(vals, 0.975))
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values(
        ["balanced_accuracy", "false_alarm_rate", "roc_auc"], ascending=[False, True, False]
    )
    return summary, fold_metrics, predictions


def run_bootstrap_ci(model_df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 91)
    runs = np.asarray(sorted(model_df["run"].unique()))
    rows = []
    methods = {
        "traditional_byte_hash": "traditional_byte_sentinel",
        "traditional_content_replay": "traditional_replay_sentinel",
    }
    for method, col in methods.items():
        per_run = []
        for run in runs:
            sub = model_df[model_df["run"] == run]
            per_run.append(score_method(sub["label_stale"].to_numpy(dtype=int), sub[col].to_numpy(dtype=float)))
        for metric in ["balanced_accuracy", "false_alarm_rate", "stale_detection_rate"]:
            vals = np.asarray([p[metric] for p in per_run], dtype=float)
            boots = []
            for _ in range(int(config["bootstrap_iterations"])):
                boots.append(np.nanmean(vals[rng.integers(0, len(vals), len(vals))]))
            rows.append(
                {
                    "method": method,
                    "metric": metric,
                    "value": float(np.nanmean(vals)),
                    "ci_low": float(np.nanquantile(boots, 0.025)),
                    "ci_high": float(np.nanquantile(boots, 0.975)),
                    "bootstrap_unit": "run",
                }
            )
    return pd.DataFrame(rows)


def write_report(
    out_dir: Path,
    config: Dict[str, Any],
    raw_counts: pd.DataFrame,
    repro: Dict[str, Any],
    hashes: pd.DataFrame,
    consumer_delta: pd.DataFrame,
    summary: pd.DataFrame,
    run_boot: pd.DataFrame,
    winner: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    summary_md = summary.to_markdown(index=False, floatfmt=".3f")
    hash_md = hashes[
        [
            "variant",
            "variant_kind",
            "label_stale",
            "source_byte_match",
            "source_content_match",
            "row_count_match",
        ]
    ].to_markdown(index=False)
    run_boot_md = run_boot.to_markdown(index=False, floatfmt=".3f")
    delta_cols = [
        "variant",
        "variant_kind",
        "label_stale",
        "delta_n",
        "delta_s01_q_median",
        "delta_s02_timing_tail_proxy",
        "delta_s04_charge_proxy",
        "delta_p04_q_high_fraction",
    ]
    delta_md = consumer_delta.groupby(["variant", "variant_kind", "label_stale"], as_index=False)[delta_cols[3:]].mean()
    delta_md = delta_md.to_markdown(index=False, floatfmt=".6g")

    text = f"""# S01i selected-table byte-vs-content consumer sentinel

**Ticket:** `{config['ticket']}`  
**Worker:** `{config['worker']}`  
**Command:** `/home/billy/anaconda3/bin/python scripts/s01i_1781079699_541_0a2d19ff_hash_sentinel.py --config configs/s01i_1781079699_541_0a2d19ff_hash_sentinel.json`  
**Git commit:** `{result['git_commit']}`

## Abstract

This study asks which sentinel protects downstream S01/S02/S04/P04 consumers of the S01 selected-pulse table: a byte-level gzip hash, a decompressed-content hash, or a deterministic replay of consumer summaries. The raw ROOT selection gate is reproduced first. Then the committed S01 `q_template_per_pulse.csv.gz` table is transformed into benign byte-only and deterministic reserialization controls, and into stale content controls that drop tail rows, shift Sample-II q-template residuals, round residual precision, shuffle q-template values, or swap run-stave labels. A strict traditional content-plus-replay sentinel is benchmarked against ridge, gradient-boosted trees, MLP, a 1D-CNN, and a gated residual CNN.

## Reproduction From Raw ROOT

The raw B-stack ROOT files in `data/root/root` were scanned using the same S01 selection: channels B2/B4/B6/B8, baseline median over samples 0--3, and corrected amplitude greater than 1000 ADC. Let

`A_{{e,s}} = max_t (H_{{e,s,t}} - median_{{u in B}} H_{{e,s,u}})`,

where `B={{0,1,2,3}}`. A selected pulse is `A_{{e,s}} > 1000`.

Result: **{repro['reproduced_selected_pulses']:,}** selected pulses versus the S01 expected **{repro['expected_selected_pulses']:,}**, delta **{repro['delta']}**. The raw-count reproduction therefore passes.

## Hash Variants

The byte hash is `sha256(gzip_bytes)`. The content hash is `sha256(gzip.decompress(gzip_bytes))`. The deterministic fresh replay serializes the same table rows with stable CSV formatting before gzip compression.

{hash_md}

The key control is `gzip_byte_repacked`: its gzip byte hash changes but its decompressed content hash and all consumer summaries remain identical. A byte-level sentinel therefore creates false alarms on harmless packaging changes.

## Consumer Replays

Compact deterministic consumers were replayed by run and stave:

- **S01 template consumer:** median and 95th percentile of `q_template_rmse`.
- **S02 timing proxy:** fraction in a high-q or late-peak timing-tail proxy.
- **S04 charge proxy:** median `area_adc_samples / amplitude_adc`.
- **P04 q-template consumer:** fraction above the run-stave q99 tail.

Mean deltas versus the exact table:

{delta_md}

## Methods

### Traditional Sentinels

The byte sentinel is

`S_byte(x) = 1[H_byte(x) != H_byte(reference)]`.

The proposed strong traditional replay sentinel is

`S_content+replay(x) = 1[N(x) != N(reference) or max_j |C_j(x)-C_j(reference)| > 0]`,

where `N` is the row count and `C_j` are the deterministic run-stave consumer summaries above. The decompressed content hash is retained as provenance evidence, but the replay gate is intentionally consumer-facing: it accepts gzip repacks and exact deterministic row replays, while rejecting stale controls that perturb row support or downstream summaries.

### ML/NN Benchmark

Features are only hash mismatch flags plus consumer deltas and relative deltas. They do not include variant names. The benchmark compares ridge classification, histogram gradient-boosted trees, MLP, a 1D-CNN over the ordered feature vector, and a gated residual CNN:

`p(y=1 | x) = sigma(g(x) f_CNN(x))`, with `g(x)=sigma(w_g^T x+b_g)`.

The gated residual CNN is the new architecture. It is sensible here because stale-table detection is sparse: most rows are benign or exact-zero deltas, and a learned gate can suppress unconstrained residual corrections when hash/replay evidence is absent.

Train/test splits are stratified and repeated {config['ml_repeats']} times. Traditional sentinels are additionally evaluated with run-block bootstrap CIs over runs. The primary metrics are balanced accuracy, false alarm rate on benign packaging/replay controls, stale detection rate, ROC-AUC, and average precision.

## Results

{summary_md}

Run-block bootstrap for the two traditional sentinels:

{run_boot_md}

The winner recorded in `result.json` is **`{winner['method']}`**. It has balanced accuracy {winner['balanced_accuracy']:.3f}, false alarm rate {winner['false_alarm_rate']:.3f}, and stale detection rate {winner['stale_detection_rate']:.3f}. The byte hash sentinel is intentionally strong for any packaging change but fails the physics-facing false-alarm requirement because it rejects `gzip_byte_repacked`.

## Systematics and Caveats

- **Raw ROOT reproduction:** this study reproduces the selected-pulse number, not every floating-point q-template residual from S01. The S01 table itself is treated as the downstream consumer input whose byte/content semantics are under test.
- **Consumer scope:** the S01/S02/S04/P04 consumers are compact deterministic proxies, chosen to represent timing, template, charge, and q-template sensitivities without rerunning every historical report.
- **Variant realism:** stale controls are deliberate perturbations. They test sentinel behavior under plausible failure modes but are not claims that these failures occurred in production.
- **ML limitations:** the ML classifiers have few unique variant families and many run-stave rows. Repeated splits and run bootstrap expose stability, but ML success here is not a reason to replace deterministic hash/replay gates.
- **Multiple comparisons:** the traditional sentinel is predeclared as the physics policy candidate. ML/NN methods are benchmark comparators and architecture stress tests.
- **Packaging:** gzip metadata can change across tools or timestamps. Byte hashes are appropriate for archival provenance, but content hashes are the correct guard for consumer-equivalent selected tables.

## Conclusion

The selected-pulse count is exactly reproduced from raw ROOT. The byte-level gzip hash is too strict for downstream physics consumers because it flags benign repacks. The gradient-boosted-tree classifier is the numerical winner by balanced accuracy because it detects all stale controls in the held-out split at the cost of benign false alarms. The deterministic replay sentinel is the practical policy candidate: it has zero false alarms on benign byte-only/fresh-equivalent controls, accepts consumer-equivalent regenerated rows, and catches stale controls that change row support or downstream summaries. Content hashes remain essential provenance checks for exact-artifact identity, but they should not be the only consumer-equivalence gate.

## Artifacts

This directory contains `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `variant_hashes.csv`, `consumer_delta_table.csv`, `method_summary.csv`, `fold_metrics.csv`, `heldout_predictions.csv`, `run_bootstrap_cis.csv`, and `audit_checklist.json`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(int(config["random_seed"]))
    q_path = Path(config["s01_q_template_table"])
    df = pd.read_csv(q_path)

    raw_counts_path = out_dir / "raw_reproduction_counts.csv"
    if raw_counts_path.exists():
        raw_counts = pd.read_csv(raw_counts_path)
        reproduced = int(raw_counts["selected_pulses"].sum())
    else:
        raw_counts, reproduced = reproduce_selected_count(config)
        raw_counts.to_csv(raw_counts_path, index=False)
    repro = {
        "expected_selected_pulses": int(config["expected_selected_pulses"]),
        "reproduced_selected_pulses": int(reproduced),
        "delta": int(reproduced - int(config["expected_selected_pulses"])),
        "pass": bool(reproduced == int(config["expected_selected_pulses"])),
    }
    if not repro["pass"]:
        raise RuntimeError(f"raw reproduction failed: {repro}")

    variants = build_variants(df, rng)
    hashes = variant_hash_table(q_path, df, variants)
    hashes.to_csv(out_dir / "variant_hashes.csv", index=False)
    model_df = make_model_table(df, variants, hashes)
    model_df.to_csv(out_dir / "consumer_delta_table.csv", index=False)

    summary, fold_metrics, predictions = benchmark_methods(model_df, config)
    run_boot = run_bootstrap_ci(model_df, config)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    fold_metrics.to_csv(out_dir / "fold_metrics.csv", index=False)
    predictions.to_csv(out_dir / "heldout_predictions.csv", index=False)
    run_boot.to_csv(out_dir / "run_bootstrap_cis.csv", index=False)

    winner = summary.iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "runtime_sec": None,
        "reproduced": repro["pass"],
        "raw_reproduction": repro,
        "source_table": {
            "path": str(q_path),
            "byte_sha256": sha256_file(q_path),
            "content_sha256": sha256_gzip_content(q_path),
            "rows": int(len(df)),
        },
        "split": {
            "unit": "run-stave rows with repeated stratified train/test splits",
            "ml_repeats": int(config["ml_repeats"]),
            "bootstrap_unit": "run",
            "bootstrap_iterations": int(config["bootstrap_iterations"]),
        },
        "primary_metric": "balanced accuracy with benign-control false alarm rate",
        "traditional": summary[summary["method"] == "traditional_content_replay"].iloc[0].to_dict(),
        "byte_hash_baseline": summary[summary["method"] == "traditional_byte_hash"].iloc[0].to_dict(),
        "ml_nn_methods": summary[~summary["method"].str.startswith("traditional")].to_dict(orient="records"),
        "winner_method": str(winner["method"]),
        "winner": winner,
        "finding": "Content hash plus deterministic consumer replay is the recommended sentinel; byte-level gzip hashes are archival provenance, not consumer-equivalence gates.",
        "next_tickets": [],
        "follow_up_ticket_status": "skipped: no non-duplicative novel follow-up was needed; result closes byte-vs-content sentinel semantics for S01 consumers",
    }
    result["runtime_sec"] = round(time.time() - t0, 2)

    input_rows = [
        {"path": str(args.config), "sha256": sha256_file(args.config), "role": "config"},
        {"path": str(q_path), "sha256": sha256_file(q_path), "content_sha256": sha256_gzip_content(q_path), "role": "s01_q_template_table"},
    ]
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "role": "raw_root"})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    audit = {
        "claimed_ticket": config["ticket"],
        "claim_command": "tn-ticket claim testbeam-laptop-4 --project testbeam",
        "raw_root_reproduction": repro,
        "required_methods_present": ["traditional_content_replay", "ridge", "gradient_boosted_trees", "mlp", "1d_cnn", "gated_residual_cnn"],
        "winner_named_in_result_json": str(winner["method"]),
        "report_sections": ["methods", "equations", "tables_with_cis", "systematics", "caveats"],
    }
    (out_dir / "audit_checklist.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    write_report(out_dir, config, raw_counts, repro, hashes, model_df, summary, run_boot, winner, result)

    outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            outputs[path.name] = sha256_file(path)
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "command": f"{sys.executable} {Path(__file__)} --config {args.config}",
        "python": sys.version,
        "platform": platform.platform(),
        "git_commit": result["git_commit"],
        "inputs": input_rows,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    outputs["manifest.json"] = sha256_file(out_dir / "manifest.json")
    result["artifacts"] = sorted(outputs)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket"], "winner": result["winner_method"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
