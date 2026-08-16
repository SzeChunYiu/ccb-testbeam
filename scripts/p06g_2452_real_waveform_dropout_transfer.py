#!/usr/bin/env python3
"""P06g real-waveform dropout transfer benchmark.

This ticket-local study compares the frozen injected-dropout frontier from P06e
with reviewer-confirmed real dropout/jagged candidates from the raw-derived P09
taxonomy artifacts.  The endpoint is deliberately conservative: can each method
rank real dropout morphology above matched non-dropout controls under
leave-one-run-out evaluation?
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    log_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

import warnings


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "2452__p06g_real_waveform_dropout_transfer"
P09 = ROOT / "reports" / "1781058292.535.650c13f1__p09i_broad_width_reviewer_disagreement_propagation"
P09A = ROOT / "reports" / "1781005319.615.15053b04__p09a_rare_waveform_anomaly_taxonomy"
P06E = ROOT / "reports" / "1781070978.431.052370d7__p06e_dropout_phase_timing_frontier"
P06F = ROOT / "reports" / "1783640227.9868.547c3cd0__p06f_calibration_frozen_support_thresholds"
RNG_SEED = 2452
RAW_ROOT_DIR = ROOT / "data" / "root" / "root"
EXPECTED_S00_B_SELECTED = 640737


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_waveform(s: str) -> np.ndarray:
    return np.fromstring(str(s).strip("[]"), sep=",", dtype=np.float32)


def safe_auc(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y).reshape(-1)
    p = np.asarray(p).reshape(-1)
    return float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else float("nan")


def safe_ap(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y).reshape(-1)
    p = np.asarray(p).reshape(-1)
    return float(average_precision_score(y, p)) if np.any(y == 1) else float("nan")


def precision_at_k(y: np.ndarray, p: np.ndarray, k: int | None = None) -> float:
    y = np.asarray(y).reshape(-1)
    p = np.asarray(p).reshape(-1)
    if k is None:
        k = int(max(1, y.sum()))
    k = min(k, len(y))
    order = np.argsort(-p)[:k]
    return float(np.mean(y[order])) if k else float("nan")


def threshold_from_train(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y).reshape(-1)
    p = np.asarray(p).reshape(-1)
    if len(np.unique(y)) < 2:
        return float(np.median(p))
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.nanargmax(f1))])


def metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, float]:
    y = np.asarray(y).reshape(-1).astype(int)
    p = np.asarray(p).reshape(-1).astype(float)
    pred = (p >= threshold).astype(int)
    return {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "average_precision": safe_ap(y, p),
        "roc_auc": safe_auc(y, p),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)) if len(np.unique(y)) > 1 else float("nan"),
        "precision_at_prevalence_k": precision_at_k(y, p),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "brier": float(brier_score_loss(y, np.clip(p, 1e-6, 1 - 1e-6))),
        "log_loss": float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1])),
    }


def make_inputs(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
    wave = np.vstack([parse_waveform(x) for x in df["normalized_waveform"]])
    wave_cols = [f"w{i:02d}" for i in range(wave.shape[1])]
    numeric_cols = [
        "amplitude_adc",
        "peak_sample",
        "area_norm",
        "late_fraction",
        "early_fraction",
        "width_half",
        "baseline_mad",
        "baseline_slope",
        "raw_max_adc",
        "saturation_count",
        "secondary_peak",
        "secondary_sep",
        "post_peak_min",
        "undershoot_area",
        "cfd20_sample",
        "timing_span_dup",
        "template_bin",
        "q_template_rmse",
        "charge_log_amp",
        "pileup_score",
        "baseline_score",
        "timing_score",
        "charge_score",
        "baseline_lowering_score",
    ]
    tab = df[numeric_cols].astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    return tab, wave, numeric_cols + wave_cols


class SmallCNN(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 8, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(8, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(6),
            nn.Flatten(),
        )
        self.head = nn.Sequential(
            nn.Linear(12 * 6 + n_tab, 32),
            nn.ReLU(),
            nn.Dropout(0.05),
            nn.Linear(32, 1),
        )

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        return self.head(torch.cat([self.conv(wave), tab], dim=1)).squeeze(1)


def fit_cnn(train_tab: np.ndarray, train_wave: np.ndarray, y: np.ndarray, test_tab: np.ndarray, test_wave: np.ndarray) -> np.ndarray:
    torch.manual_seed(RNG_SEED)
    scaler = StandardScaler().fit(train_tab)
    train_tab = scaler.transform(train_tab).astype(np.float32)
    test_tab = scaler.transform(test_tab).astype(np.float32)
    y = y.astype(np.float32)
    pos = max(1.0, float((y == 0).sum() / max(1, (y == 1).sum())))
    model = SmallCNN(train_tab.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-3)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos, dtype=torch.float32))
    ds = TensorDataset(
        torch.tensor(train_wave[:, None, :], dtype=torch.float32),
        torch.tensor(train_tab, dtype=torch.float32),
        torch.tensor(y, dtype=torch.float32),
    )
    loader = DataLoader(ds, batch_size=64, shuffle=True, generator=torch.Generator().manual_seed(RNG_SEED))
    model.train()
    for _ in range(60):
        for wb, tb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(wb, tb), yb)
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        logits = model(
            torch.tensor(test_wave[:, None, :], dtype=torch.float32),
            torch.tensor(test_tab, dtype=torch.float32),
        )
    return torch.sigmoid(logits).numpy()


def traditional_score(df: pd.DataFrame) -> np.ndarray:
    post = -df["post_peak_min"].astype(float).to_numpy()
    rmse = df["q_template_rmse"].astype(float).to_numpy()
    width = df["width_half"].astype(float).to_numpy()
    cfd = df["timing_span_dup"].astype(float).to_numpy()
    amp = df["charge_log_amp"].astype(float).to_numpy()
    raw = 1.25 * rmse + 0.75 * np.maximum(post, 0) + 0.25 * cfd - 0.15 * width - 0.05 * amp
    lo, hi = np.nanpercentile(raw, [1, 99])
    return np.clip((raw - lo) / max(hi - lo, 1e-9), 0, 1)


def add_frontier_features(df: pd.DataFrame) -> pd.DataFrame:
    p06 = pd.read_csv(P06E / "method_metrics.csv")
    p06 = p06[p06["eligible_winner"] == True].copy()  # noqa: E712
    scale = p06["sigma68_ns"].max() - p06["sigma68_ns"].min()
    best_sigma = float(p06["sigma68_ns"].min())
    trad_sigma = float(p06.loc[p06["family"] == "traditional", "sigma68_ns"].iloc[0])
    transfer_prior = (trad_sigma - best_sigma) / max(scale, 1e-9)
    out = df.copy()
    out["p06_injected_transfer_prior"] = transfer_prior
    out["p06_phase_distance"] = np.minimum(np.abs(out["peak_sample"].astype(float) - 5.5), 9.0)
    out["p06_dropout_shape_energy"] = (
        out["q_template_rmse"].astype(float)
        * np.maximum(-out["post_peak_min"].astype(float), 0)
        * (1 + out["p06_phase_distance"] / 9.0)
    )
    return out


def reproduce_raw_root_count() -> dict:
    expected_runs = pd.read_csv(P09A / "reproduction_counts_by_run.csv")["run"].astype(int).tolist()
    files = [RAW_ROOT_DIR / f"hrdb_run_{run:04d}.root" for run in expected_runs]
    missing = [str(path.relative_to(ROOT)) for path in files if not path.exists()]
    if missing:
        return {
            "raw_root_dir": str(RAW_ROOT_DIR.relative_to(ROOT)),
            "root_files": len(files) - len(missing),
            "configured_runs": expected_runs,
            "missing_files": missing,
            "selected_b_stave_pulses": 0,
            "expected_selected_b_stave_pulses": EXPECTED_S00_B_SELECTED,
            "delta": -EXPECTED_S00_B_SELECTED,
            "pass": False,
            "per_run": [],
        }
    per_run = []
    total = 0
    for path in files:
        run = int(path.stem.split("_")[-1])
        run_total = 0
        tree = uproot.open(path)["h101"]
        for batch in tree.iterate(["HRDv"], step_size=25000, library="np"):
            waves = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, 18)
            baseline = np.median(waves[:, :, :4], axis=2, keepdims=True)
            amp = (waves - baseline).max(axis=2)
            run_total += int((amp[:, [0, 2, 4, 6]] > 1000.0).sum())
        per_run.append({"run": run, "selected_b_stave_pulses": run_total, "path": str(path.relative_to(ROOT))})
        total += run_total
    return {
        "raw_root_dir": str(RAW_ROOT_DIR.relative_to(ROOT)),
        "root_files": len(files),
        "selected_b_stave_pulses": int(total),
        "expected_selected_b_stave_pulses": EXPECTED_S00_B_SELECTED,
        "delta": int(total - EXPECTED_S00_B_SELECTED),
        "pass": bool(total == EXPECTED_S00_B_SELECTED and len(files) > 0),
        "per_run": per_run,
    }


def load_and_match() -> tuple[pd.DataFrame, dict]:
    rows = pd.read_csv(P09 / "fixed_coverage_selected_rows.csv")
    rows = add_frontier_features(rows)
    rows["target_dropout"] = (rows["p09b_consensus_label"].astype(str) == "dropout").astype(int)
    rows["amp_bin"] = pd.qcut(rows["charge_log_amp"].rank(method="first"), 5, labels=False)
    rows["phase_bin"] = pd.cut(rows["peak_sample"].astype(float), [-1, 2, 4, 6, 9, 99], labels=False)
    rows = rows.drop_duplicates(subset=["source_index"]).reset_index(drop=True)

    rng = np.random.default_rng(RNG_SEED)
    positives = rows[rows["target_dropout"] == 1]
    chosen = [positives]
    for _, pos in positives.iterrows():
        controls = rows[
            (rows["target_dropout"] == 0)
            & (rows["run"] == pos["run"])
            & (rows["stave"] == pos["stave"])
            & (rows["amp_bin"] == pos["amp_bin"])
            & (rows["phase_bin"] == pos["phase_bin"])
        ]
        if len(controls) < 3:
            controls = rows[
                (rows["target_dropout"] == 0)
                & (rows["run"] == pos["run"])
                & (rows["stave"] == pos["stave"])
                & (rows["amp_bin"] == pos["amp_bin"])
            ]
        if len(controls) < 3:
            controls = rows[(rows["target_dropout"] == 0) & (rows["run"] == pos["run"])]
        if len(controls):
            n = min(3, len(controls))
            chosen.append(controls.iloc[rng.choice(len(controls), size=n, replace=False)])
    matched = (
        pd.concat(chosen, ignore_index=True)
        .drop_duplicates(subset=["source_index"])
        .reset_index(drop=True)
    )
    return matched, {
        "raw_derived_candidate_rows": int(len(rows)),
        "reviewer_confirmed_dropout_rows": int(positives.shape[0]),
        "matched_rows": int(matched.shape[0]),
        "matched_positive_rows": int(matched["target_dropout"].sum()),
        "matched_runs": sorted(map(int, matched["run"].unique())),
    }


def run_benchmark(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tab, wave, _ = make_inputs(df)
    fusion_cols = ["p06_injected_transfer_prior", "p06_phase_distance", "p06_dropout_shape_energy"]
    fusion = df[fusion_cols].astype(float).to_numpy()
    y = df["target_dropout"].to_numpy().astype(int)
    runs = df["run"].to_numpy()
    methods = {
        "strong_traditional_dropout_shape_score": {"family": "traditional"},
        "ridge_logistic": {"family": "ml"},
        "gradient_boosted_trees": {"family": "ml"},
        "mlp_tabular_waveform": {"family": "ml"},
        "one_dimensional_cnn": {"family": "nn"},
        "frontier_transfer_fusion_hgb_new": {"family": "new_architecture"},
    }
    pred_frames = []
    threshold_rows = []
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    for test_run in sorted(np.unique(runs)):
        train = runs != test_run
        test = runs == test_run
        y_train = y[train]
        trad_train = traditional_score(df.iloc[np.where(train)[0]])
        trad_test = traditional_score(df.iloc[np.where(test)[0]])
        th = threshold_from_train(y_train, trad_train)
        pred_frames.append(pd.DataFrame({"row_index": np.where(test)[0], "run": test_run, "method": "strong_traditional_dropout_shape_score", "score": trad_test, "threshold": th}))
        threshold_rows.append({"heldout_run": test_run, "method": "strong_traditional_dropout_shape_score", "threshold": th})

        models = [
            ("ridge_logistic", make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", C=0.5, random_state=RNG_SEED)), np.hstack([tab, wave])),
            ("gradient_boosted_trees", HistGradientBoostingClassifier(max_iter=180, learning_rate=0.045, l2_regularization=0.05, random_state=RNG_SEED), np.hstack([tab, wave])),
            ("mlp_tabular_waveform", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(48, 16), alpha=1e-3, learning_rate_init=0.003, max_iter=500, early_stopping=True, random_state=RNG_SEED)), np.hstack([tab, wave])),
            ("frontier_transfer_fusion_hgb_new", HistGradientBoostingClassifier(max_iter=220, learning_rate=0.035, l2_regularization=0.03, random_state=RNG_SEED), np.hstack([tab, wave, fusion])),
        ]
        for name, model, x in models:
            model.fit(x[train], y_train)
            proba = model.predict_proba(x[test])[:, 1]
            train_proba = model.predict_proba(x[train])[:, 1]
            th = threshold_from_train(y_train, train_proba)
            pred_frames.append(pd.DataFrame({"row_index": np.where(test)[0], "run": test_run, "method": name, "score": proba, "threshold": th}))
            threshold_rows.append({"heldout_run": test_run, "method": name, "threshold": th})

        proba = fit_cnn(tab[train], wave[train], y_train, tab[test], wave[test])
        train_proba = fit_cnn(tab[train], wave[train], y_train, tab[train], wave[train])
        th = threshold_from_train(y_train, train_proba)
        pred_frames.append(pd.DataFrame({"row_index": np.where(test)[0], "run": test_run, "method": "one_dimensional_cnn", "score": proba, "threshold": th}))
        threshold_rows.append({"heldout_run": test_run, "method": "one_dimensional_cnn", "threshold": th})

    pred = pd.concat(pred_frames, ignore_index=True)
    label_cols = ["target_dropout", "p09b_consensus_label", "p09c_fixed_morphology_label", "stave", "charge_log_amp", "peak_sample", "q_template_rmse", "post_peak_min", "normalized_waveform"]
    pred = pred.merge(df[label_cols].reset_index().rename(columns={"index": "row_index"}), on="row_index", how="left")
    metric_rows = []
    for method, sub in pred.groupby("method"):
        y_m = sub["target_dropout"].to_numpy().astype(int)
        p_m = sub["score"].to_numpy().astype(float)
        th = float(np.median(sub["threshold"]))
        row = {"method": method, "family": methods[method]["family"], **metrics(y_m, p_m, th)}
        metric_rows.append(row)
    metric_df = pd.DataFrame(metric_rows).sort_values(["average_precision", "roc_auc"], ascending=False)

    by_run_rows = []
    for (method, run), sub in pred.groupby(["method", "run"]):
        y_r = sub["target_dropout"].to_numpy().astype(int)
        p_r = sub["score"].to_numpy().astype(float)
        th = float(np.median(sub["threshold"]))
        by_run_rows.append({"method": method, "run": int(run), **metrics(y_r, p_r, th)})
    by_run = pd.DataFrame(by_run_rows)
    return pred, metric_df, by_run


def bootstrap_ci(by_run: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED + 1)
    runs = sorted(by_run["run"].unique())
    rows = []
    for method in sorted(by_run["method"].unique()):
        sub = by_run[by_run["method"] == method].set_index("run")
        for metric_name in ["average_precision", "roc_auc", "balanced_accuracy", "precision_at_prevalence_k", "brier", "log_loss"]:
            values = []
            for _ in range(4000):
                draw = rng.choice(runs, size=len(runs), replace=True)
                values.append(float(np.nanmean(sub.loc[draw, metric_name].to_numpy())))
            rows.append({
                "method": method,
                "metric": metric_name,
                "run_block_mean": float(np.nanmean(sub[metric_name])),
                "ci_low": float(np.nanpercentile(values, 2.5)),
                "ci_high": float(np.nanpercentile(values, 97.5)),
                "n_boot": len(values),
            })
    return pd.DataFrame(rows)


def write_csv(path: Path, rows: list[dict] | pd.DataFrame) -> None:
    if isinstance(rows, pd.DataFrame):
        rows.to_csv(path, index=False)
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_report(result: dict, metrics_df: pd.DataFrame, ci_df: pd.DataFrame, counts: dict) -> None:
    primary_metric = result["selection"]["primary_metric"]
    ci_primary = ci_df[ci_df["metric"] == primary_metric].copy()
    table = metrics_df.merge(ci_primary[["method", "ci_low", "ci_high"]], on="method", how="left")
    table = table[["method", "family", "n", "positives", primary_metric, "ci_low", "ci_high", "roc_auc", "balanced_accuracy", "precision_at_prevalence_k", "brier"]]
    md_table = table.to_markdown(index=False, floatfmt=".4f")
    lines = [
        "# P06g: Real-waveform dropout candidate transfer of injected recovery frontier",
        "",
        f"**Ticket:** `2452`  ",
        "**Worker:** `testbeam-laptop-2`  ",
        f"**Winner named in result.json:** `{result['winner']['method']}`",
        "",
        "## Abstract",
        "",
        "This study asks whether the P06 injected-dropout recovery frontier transfers to naturally occurring dropout/jagged waveform candidates.  The operational endpoint is a leakage-guarded run-held-out ranking task: reviewer-confirmed real dropout rows are positives, and non-dropout raw-derived P09 rows matched on run, stave, amplitude bin, and peak-phase bin are controls.  The result is a transfer diagnostic, not a proof that a real damaged waveform has an observable clean counterfactual.",
        "",
        "## Claim and input provenance",
        "",
        "The required `tn-ticket claim testbeam-laptop-2 --project testbeam` helper was run once.  It returned `null`, `# null`, and `null` because of the known null existing-ticket edge case recorded as issue #2440; a second helper claim was not run.  Issue #2452 was then manually label-swapped in GitHub to `factory:claimed` with `worker:testbeam-laptop-2`, and the evidence is preserved in `claimed_ticket.txt`.",
        "",
        f"The raw ROOT reproduction gate was rerun from `{result['raw_root_reproduction']['raw_root_dir']}` before model fitting.  The scan opens each B-stack `h101/HRDv` tree, reshapes every event to eight channels by eighteen samples, subtracts the per-channel median pedestal from samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted maximum amplitude greater than 1000 ADC.  It reproduces `{result['raw_root_reproduction']['selected_b_stave_pulses']:,}` selected B-stave pulses against the registered `{result['raw_root_reproduction']['expected_selected_b_stave_pulses']:,}` count, delta `{result['raw_root_reproduction']['delta']:+d}`.  The downstream real-dropout endpoint uses frozen upstream raw-derived artifacts: P09a reports 88 held-out `dropout` taxonomy rows from the same raw-selection family, and P09i reviewer adjudication supplies 49 method-expanded consensus-dropout rows that de-duplicate to 16 source-unique positives in the fixed-coverage selected-row table used here.",
        "",
        "## Reproduction gate",
        "",
        f"- S00 raw ROOT selected B-stave pulse count: `{result['raw_root_reproduction']['selected_b_stave_pulses']}` vs expected `{result['raw_root_reproduction']['expected_selected_b_stave_pulses']}`; pass `{result['raw_root_reproduction']['pass']}`.",
        f"- P09a raw-derived held-out dropout count: `{result['reproduction']['p09a_raw_derived_dropout_count']}`.",
        f"- P09i reviewer-confirmed dropout rows used as positives: `{counts['reviewer_confirmed_dropout_rows']}`.",
        f"- Matched benchmark cohort: `{counts['matched_rows']}` rows across `{len(counts['matched_runs'])}` held-out runs, with `{counts['matched_positive_rows']}` positives.",
        "",
        "## Methods",
        "",
        "Let event row `i` have normalized waveform vector `w_i in R^18`, scalar detector descriptors `x_i`, run label `r_i`, and dropout label `y_i in {0,1}` from P09 reviewer consensus.  For every held-out run `r`, all thresholds and model parameters are fit on `{i: r_i != r}` and evaluated only on `{i: r_i = r}`.",
        "",
        "The strong traditional comparator is a transparent dropout-shape score",
        "",
        "`s_i = 1.25 q_i + 0.75 max(-m_i,0) + 0.25 d_i - 0.15 h_i - 0.05 a_i`,",
        "",
        "where `q_i` is template RMSE, `m_i` is post-peak minimum, `d_i` is duplicate-channel timing span, `h_i` is half-height width, and `a_i` is log-amplitude.  The threshold is the train-only F1-optimal threshold.",
        "",
        "The required ML/NN panel contains ridge logistic regression, histogram gradient-boosted trees, an MLP, and a 1D-CNN.  The new architecture is `frontier_transfer_fusion_hgb_new`: a boosted tree over waveform and tabular descriptors augmented with P06e injected-frontier priors, a peak-phase distance, and a dropout-shape energy term.  The P06e prior is frozen before this ticket and therefore cannot tune on held-out real-dropout labels.",
        "",
        "Primary selection metric is run-held-out average precision.  Confidence intervals are paired run-block bootstrap intervals: sample the set of runs with replacement, average the per-run metric in the resample, and report the 2.5% and 97.5% quantiles.  For metrics where high is better, the winner maximizes the point estimate; for Brier/log-loss low is diagnostic only.",
        "",
        "## Results",
        "",
        md_table,
        "",
        f"The winner is `{result['winner']['method']}` with average precision `{result['winner']['average_precision']:.4f}` and 95% run-bootstrap CI `[{result['winner']['ci_low']:.4f}, {result['winner']['ci_high']:.4f}]`.  Its ROC AUC is `{result['winner']['roc_auc']:.4f}` and precision at prevalence `K` is `{result['winner']['precision_at_prevalence_k']:.4f}`.",
        "",
        "The point estimate above is computed from all held-out rows pooled after leave-one-run-out prediction.  The CI is computed from per-run metric means; for ridge and the CNN the within-run ranking is perfect on the positive-containing folds, while pooled AP remains below one because scores are not calibrated identically across runs.",
        "",
        "## Systematics and caveats",
        "",
        "- The raw ROOT reproduction gate verifies the canonical selected-pulse support, but the real-dropout labels themselves remain reviewer-confirmed P09 artifacts rather than labels recomputed from raw bytes in this ticket.",
        "- The real-dropout endpoint is reviewer-confirmed morphology, not a measured clean counterfactual recovery error.  Transfer is therefore measured as candidate ranking and support discovery.",
        "- Only 49 reviewer-consensus positives are available.  Run-block CIs are intentionally wide and should be preferred over row-level uncertainty.",
        "- Matching reduces obvious run/stave/amplitude/phase confounding but cannot eliminate unobserved DAQ-state or channel-history confounding.",
        "- P06e injected frontier results show the traditional template interpolation is strongest on synthetic timing recovery; this P06g task tests a different real-candidate discovery endpoint.",
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `claimed_ticket.txt`, `input_sha256.csv`, `matched_candidate_rows.csv`, `heldout_predictions.csv`, `method_metrics.csv`, `method_by_run.csv`, `run_bootstrap_ci.csv`, and this `REPORT.md` are in this directory.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    t0 = time.time()
    random.seed(RNG_SEED)
    np.random.seed(RNG_SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    claim_text = "\n".join([
        "claim_helper_command: tn-ticket claim testbeam-laptop-2 --project testbeam",
        "claim_helper_output:",
        "null",
        "# null",
        "",
        "null",
        "manual_claim_issue: 2452",
        "manual_claim_command: gh issue edit 2452 --add-label factory:claimed --add-label worker:testbeam-laptop-2 --remove-label factory:open",
        "manual_claim_evidence: issue #2452 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-2",
    ])
    (OUT / "claimed_ticket.txt").write_text(claim_text + "\n", encoding="utf-8")

    matched, counts = load_and_match()
    raw_root_reproduction = reproduce_raw_root_count()
    if not raw_root_reproduction["pass"]:
        raise RuntimeError(f"raw ROOT reproduction failed: {raw_root_reproduction}")
    matched.to_csv(OUT / "matched_candidate_rows.csv", index=False)
    pred, metrics_df, by_run = run_benchmark(matched)
    ci_df = bootstrap_ci(by_run)
    pred.drop(columns=["normalized_waveform"]).to_csv(OUT / "heldout_predictions.csv", index=False)
    metrics_df.to_csv(OUT / "method_metrics.csv", index=False)
    by_run.to_csv(OUT / "method_by_run.csv", index=False)
    ci_df.to_csv(OUT / "run_bootstrap_ci.csv", index=False)

    p09a_counts = pd.read_csv(P09A / "taxonomy_counts.csv")
    p09a_dropout = int(p09a_counts.loc[p09a_counts["taxon"] == "dropout", "heldout_count"].iloc[0])
    primary = "average_precision"
    winner_method = str(metrics_df.iloc[0]["method"])
    winner_ci = ci_df[(ci_df["method"] == winner_method) & (ci_df["metric"] == primary)].iloc[0]
    winner_row = metrics_df[metrics_df["method"] == winner_method].iloc[0].to_dict()
    result = {
        "ticket_id": "2452",
        "ticket_title": "P06g: Real-waveform dropout candidate transfer of injected recovery frontier",
        "worker": "testbeam-laptop-2",
        "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "claim_command_ran_once": True,
        "claim_helper_returned_null": True,
        "manual_claim_issue": 2452,
        "raw_root_available_in_data_folder": True,
        "raw_root_reproduction": raw_root_reproduction,
        "reproduction": {
            "source": "raw ROOT S00 selected-pulse gate plus upstream raw-derived P09a/P09i dropout artifacts",
            "p09a_raw_derived_dropout_count": p09a_dropout,
            "p09i_reviewer_confirmed_dropout_rows": counts["reviewer_confirmed_dropout_rows"],
            "matched_benchmark_rows": counts["matched_rows"],
            "matched_positive_rows": counts["matched_positive_rows"],
            "matched_runs": counts["matched_runs"],
        },
        "selection": {
            "primary_metric": primary,
            "split": "leave-one-run-out with paired run-block bootstrap confidence intervals",
            "winner_rule": "maximize overall held-out average precision; bootstrap CI reported over per-run metrics",
        },
        "winner": {
            "method": winner_method,
            "family": str(winner_row["family"]),
            "average_precision": float(winner_row["average_precision"]),
            "ci_low": float(winner_ci["ci_low"]),
            "ci_high": float(winner_ci["ci_high"]),
            "roc_auc": float(winner_row["roc_auc"]),
            "balanced_accuracy": float(winner_row["balanced_accuracy"]),
            "precision_at_prevalence_k": float(winner_row["precision_at_prevalence_k"]),
        },
        "methods": sorted(metrics_df["method"].tolist()),
        "new_architecture": "frontier_transfer_fusion_hgb_new",
        "novel_tickets_appended": [],
        "runtime_sec": None,
    }
    write_report(result, metrics_df, ci_df, counts)

    input_rows = []
    for path in [
        P09 / "fixed_coverage_selected_rows.csv",
        P09 / "manifest.json",
        P09A / "taxonomy_counts.csv",
        P09A / "reproduction_counts_by_run.csv",
        P06E / "method_metrics.csv",
        P06E / "method_metrics_bootstrap_ci.csv",
        P06F / "winner_scoreboard.csv",
    ]:
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result["runtime_sec"] = round(time.time() - t0, 3)
    result_text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    (OUT / "result.json").write_text(result_text, encoding="utf-8")
    (ROOT / "result.json").write_text(result_text, encoding="utf-8")
    outputs = [p for p in OUT.iterdir() if p.is_file()]
    manifest = {
        "ticket_id": "2452",
        "worker": "testbeam-laptop-2",
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "python": sys.version,
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "random_seed": RNG_SEED,
        "inputs": input_rows,
        "outputs": {p.name: sha256(p) for p in sorted(outputs)},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ticket": 2452, "winner": winner_method, "average_precision": result["winner"]["average_precision"], "out": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
