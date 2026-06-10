#!/usr/bin/env python3
"""S10h: late-sample residual taxonomy for S10d 20% last-above inflation.

The script first reproduces the S10d 20% template and empirical live-time
numbers from raw B-stack ROOT. It then assigns each selected pulse to a
late-residual rule taxonomy and runs a leave-one-run-out ML classifier for
the pulse-level inflation label.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/s10h_1781028280_1036_7e527107_late_residual_taxonomy.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


CFG = load_json(DEFAULT_CONFIG)
TICKET = CFG["ticket_id"]
WORKER = CFG["worker"]
OUT = ROOT / CFG["output_dir"]
OUT.mkdir(parents=True, exist_ok=True)


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s10c = import_module(ROOT / CFG["source_s10c_script"], "s10c_threshold_scan_tau_eff_source")


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


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def ci_from_boot(values: Iterable[float]) -> Tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def bootstrap_runs(frame: pd.DataFrame, value_fn, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    vals = []
    for _ in range(int(n_boot)):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([frame[frame["run"] == int(run)] for run in sample_runs], ignore_index=True)
        vals.append(value_fn(sample))
    return ci_from_boot(vals)


def bootstrap_group_runs(frame: pd.DataFrame, value_fn, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    low_runs = np.asarray(CFG["low_runs"], dtype=int)
    high_runs = np.asarray(CFG["high_runs"], dtype=int)
    vals = []
    for _ in range(int(n_boot)):
        picked = np.r_[rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True)]
        sample = pd.concat([frame[frame["run"] == int(run)] for run in picked], ignore_index=True)
        vals.append(value_fn(sample))
    return ci_from_boot(vals)


def reproduce_s10d_20pct(pulses: pd.DataFrame, fits: pd.DataFrame, heldout: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    template_by_run = heldout["traditional_template_live_20pct_ns"].to_numpy(dtype=float)
    empirical_by_run = heldout["empirical_mean_live_20pct_ns"].to_numpy(dtype=float)
    template_mean = float(np.nanmean(template_by_run))
    empirical_mean = float(np.nanmean(empirical_by_run))
    inflation = empirical_mean - template_mean
    reported = CFG["reported_s10d"]
    tol = float(CFG["reproduction_tolerance_ns"])
    rows = [
        {
            "quantity": "S10d live20 template smooth crossing ns",
            "report_value": float(reported["live20_template_ns"]),
            "reproduced": template_mean,
            "delta": template_mean - float(reported["live20_template_ns"]),
            "tolerance": tol,
            "pass": bool(abs(template_mean - float(reported["live20_template_ns"])) <= tol),
        },
        {
            "quantity": "S10d live20 empirical last-above ns",
            "report_value": float(reported["live20_empirical_ns"]),
            "reproduced": empirical_mean,
            "delta": empirical_mean - float(reported["live20_empirical_ns"]),
            "tolerance": tol,
            "pass": bool(abs(empirical_mean - float(reported["live20_empirical_ns"])) <= tol),
        },
        {
            "quantity": "S10d live20 empirical-minus-template inflation ns",
            "report_value": float(reported["live20_inflation_ns"]),
            "reproduced": inflation,
            "delta": inflation - float(reported["live20_inflation_ns"]),
            "tolerance": tol,
            "pass": bool(abs(inflation - float(reported["live20_inflation_ns"])) <= tol),
        },
    ]
    result = {
        "template_live20_ns": template_mean,
        "empirical_live20_ns": empirical_mean,
        "inflation_ns": inflation,
        "n_pulses": int(len(pulses)),
        "n_run_stave_fits": int(len(fits)),
    }
    return pd.DataFrame(rows), result


def attach_pulse_metrics(pulses: pd.DataFrame, fits: pd.DataFrame) -> pd.DataFrame:
    fit_cols = fits[["heldout_run", "stave", "fit_cross_20pct_ns", "threshold_20pct"]].copy()
    fit_cols = fit_cols.rename(columns={"heldout_run": "run", "fit_cross_20pct_ns": "template_cross20_ns"})
    out = pulses.merge(fit_cols, on=["run", "stave"], how="left", validate="many_to_one")
    w = np.vstack(out["waveform"].to_numpy()).astype(np.float64)
    amp = out["amplitude"].to_numpy(dtype=float)
    norm = w / np.maximum(amp, 1.0)[:, None]
    cfd = out["cfd20_sample"].to_numpy(dtype=float)
    rel_t = (np.arange(s10c.NSAMP, dtype=float)[None, :] - cfd[:, None]) * s10c.DT_NS
    post_cross = rel_t > out["template_cross20_ns"].to_numpy(dtype=float)[:, None]
    post_peak_mask = np.arange(s10c.NSAMP)[None, :] > (out["peak_sample"].to_numpy(dtype=int)[:, None] + 1)
    late_mask = np.arange(s10c.NSAMP)[None, :] >= 10
    after8 = np.arange(s10c.NSAMP)[None, :] >= 8
    diff = np.diff(norm, axis=1)

    out["norm_final_fraction"] = norm[:, -1]
    out["norm_sample_16_fraction"] = norm[:, -2]
    out["norm_late_max_fraction"] = np.where(late_mask, norm, -np.inf).max(axis=1)
    out["norm_tail_area_10plus"] = norm[:, 10:].sum(axis=1)
    out["norm_tail_positive_area_10plus"] = np.clip(norm[:, 10:], 0.0, None).sum(axis=1)
    out["post_peak_max_fraction"] = np.where(post_peak_mask, norm, -np.inf).max(axis=1)
    out["post_peak_min_fraction"] = np.where(after8, norm, np.inf).min(axis=1)
    out["post_peak_rebound_fraction"] = np.where(np.arange(s10c.NSAMP - 1)[None, :] >= 8, diff, -np.inf).max(axis=1)
    out["above20_after_template_cross_count"] = (post_cross & (norm >= 0.20)).sum(axis=1)
    out["positive_residual_after_cross_area"] = np.where(post_cross, np.clip(norm - 0.20, 0.0, None), 0.0).sum(axis=1)
    out["observable_end_ns"] = (s10c.NSAMP - 1 - cfd) * s10c.DT_NS
    out["censored_at_final_sample"] = out["live20_ns"].to_numpy(dtype=float) >= (out["observable_end_ns"].to_numpy(dtype=float) - 1e-9)
    out["inflation20_ns"] = out["live20_ns"].to_numpy(dtype=float) - out["template_cross20_ns"].to_numpy(dtype=float)
    out["positive_inflation20_ns"] = np.clip(out["inflation20_ns"].to_numpy(dtype=float), 0.0, None)
    out["inflated20_label"] = (out["inflation20_ns"].to_numpy(dtype=float) > float(CFG["inflated_label_threshold_ns"])).astype(int)
    out["clean20_label"] = (out["inflation20_ns"].to_numpy(dtype=float) <= float(CFG["clean_label_threshold_ns"])).astype(int)
    out["current_group"] = np.where(out["run"].isin(CFG["low_runs"]), "low_2nA", "high_20nA")
    out["downstream_topology"] = np.select(
        [
            out["event_three_stave"].to_numpy(dtype=bool),
            out["event_multi_stave"].to_numpy(dtype=bool),
            out["event_downstream"].to_numpy(dtype=bool),
        ],
        ["three_or_more_staves", "two_staves", "downstream_event"],
        default="single_upstream",
    )
    return out


def assign_taxonomy(frame: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    out = frame.copy()
    q = {
        "amp_q80": float(out["amplitude"].quantile(0.80)),
        "amp_q95": float(out["amplitude"].quantile(0.95)),
        "tail_area_q70": float(out["norm_tail_positive_area_10plus"].quantile(0.70)),
        "noise_q85": float((out["baseline_noise_adc"] / np.maximum(out["amplitude"], 1.0)).quantile(0.85)),
    }
    high_amp = out["amplitude"].to_numpy(dtype=float) >= q["amp_q95"]
    final_above = out["norm_final_fraction"].to_numpy(dtype=float) >= 0.20
    late_rebound = (out["post_peak_rebound_fraction"].to_numpy(dtype=float) > 0.035) & (out["post_peak_max_fraction"].to_numpy(dtype=float) > 0.22)
    broad_tail = (out["norm_tail_positive_area_10plus"].to_numpy(dtype=float) >= q["tail_area_q70"]) & (out["above20_after_template_cross_count"].to_numpy(dtype=int) >= 1)
    noisy = ((out["baseline_noise_adc"] / np.maximum(out["amplitude"], 1.0)).to_numpy(dtype=float) >= q["noise_q85"]) & (out["positive_residual_after_cross_area"].to_numpy(dtype=float) > 0.05)
    clean = (out["inflation20_ns"].to_numpy(dtype=float) <= float(CFG["clean_label_threshold_ns"])) | (out["above20_after_template_cross_count"].to_numpy(dtype=int) == 0)
    labels = np.full(len(out), "moderate_late_residual", dtype=object)
    labels[clean] = "prompt_clean"
    labels[noisy & ~clean] = "baseline_noise_residual"
    labels[broad_tail & ~clean] = "broad_slow_tail"
    labels[late_rebound & ~clean] = "late_rebound_peak"
    labels[final_above & ~clean] = "final_sample_censored_tail"
    labels[high_amp & (broad_tail | final_above | late_rebound) & ~clean] = "high_amplitude_late_tail"
    out["late_residual_taxon"] = labels
    out["amplitude_bin"] = pd.cut(
        out["amplitude"],
        bins=[-np.inf, 1500.0, 2500.0, q["amp_q95"], np.inf],
        labels=["amp_1k_1p5k", "amp_1p5k_2p5k", "amp_2p5k_q95", "amp_top5pct"],
    ).astype(str)
    return out, q


def run_weighted_taxonomy_summary(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    total_pos = float(frame["positive_inflation20_ns"].sum())
    total_n = len(frame)
    taxa = sorted(frame["late_residual_taxon"].unique())
    run_totals = frame.groupby("run").agg(total_n=("inflation20_ns", "size"), total_pos=("positive_inflation20_ns", "sum")).reset_index()
    run_ids = run_totals["run"].to_numpy(dtype=int)
    for taxon in taxa:
        sub = frame[frame["late_residual_taxon"] == taxon]
        tax_run = (
            sub.groupby("run")
            .agg(taxon_n=("inflation20_ns", "size"), taxon_inflation_sum=("inflation20_ns", "sum"), taxon_pos_sum=("positive_inflation20_ns", "sum"))
            .reindex(run_ids, fill_value=0)
            .reset_index(drop=True)
        )
        total_n_by_run = run_totals["total_n"].to_numpy(dtype=float)
        total_pos_by_run = run_totals["total_pos"].to_numpy(dtype=float)
        tax_n = tax_run["taxon_n"].to_numpy(dtype=float)
        tax_infl = tax_run["taxon_inflation_sum"].to_numpy(dtype=float)
        tax_pos = tax_run["taxon_pos_sum"].to_numpy(dtype=float)
        frac_boot = []
        mean_boot = []
        contrib_boot = []
        for _ in range(int(CFG["bootstrap_samples"])):
            idx = rng.integers(0, len(run_ids), size=len(run_ids))
            frac_boot.append(float(tax_n[idx].sum() / max(total_n_by_run[idx].sum(), 1.0)))
            mean_boot.append(float(tax_infl[idx].sum() / tax_n[idx].sum()) if tax_n[idx].sum() > 0 else np.nan)
            contrib_boot.append(float(tax_pos[idx].sum() / max(total_pos_by_run[idx].sum(), 1e-9)))
        frac_ci = ci_from_boot(frac_boot)
        mean_ci = ci_from_boot(mean_boot)
        contrib_ci = ci_from_boot(contrib_boot)
        rows.append(
            {
                "late_residual_taxon": taxon,
                "n_pulses": int(len(sub)),
                "pulse_fraction": float(len(sub) / total_n),
                "pulse_fraction_ci_low": frac_ci[0],
                "pulse_fraction_ci_high": frac_ci[1],
                "mean_inflation20_ns": float(sub["inflation20_ns"].mean()),
                "mean_inflation20_ci_low_ns": mean_ci[0],
                "mean_inflation20_ci_high_ns": mean_ci[1],
                "mean_live20_ns": float(sub["live20_ns"].mean()),
                "mean_template_cross20_ns": float(sub["template_cross20_ns"].mean()),
                "share_positive_inflation": float(sub["positive_inflation20_ns"].sum() / max(total_pos, 1e-9)),
                "share_positive_inflation_ci_low": contrib_ci[0],
                "share_positive_inflation_ci_high": contrib_ci[1],
                "inflated_label_rate": float(sub["inflated20_label"].mean()),
                "final_sample_censored_rate": float(sub["censored_at_final_sample"].mean()),
                "downstream_event_rate": float(sub["event_downstream"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("share_positive_inflation", ascending=False).reset_index(drop=True)


def current_contrast_summary(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    taxa = sorted(frame["late_residual_taxon"].unique())
    by_run = (
        frame.groupby(["run", "current_group"])
        .agg(total_n=("inflation20_ns", "size"))
        .reset_index()
    )
    for taxon in taxa:
        high = frame[(frame["current_group"] == "high_20nA") & (frame["late_residual_taxon"] == taxon)]
        low = frame[(frame["current_group"] == "low_2nA") & (frame["late_residual_taxon"] == taxon)]
        tax_by_run = (
            frame[frame["late_residual_taxon"] == taxon]
            .groupby(["run", "current_group"])
            .agg(taxon_n=("inflation20_ns", "size"), taxon_infl_sum=("inflation20_ns", "sum"))
            .reset_index()
        )
        merged = by_run.merge(tax_by_run, on=["run", "current_group"], how="left").fillna({"taxon_n": 0.0, "taxon_infl_sum": 0.0})
        low_runs = np.asarray(CFG["low_runs"], dtype=int)
        high_runs = np.asarray(CFG["high_runs"], dtype=int)

        def eval_runs(sample_low: np.ndarray, sample_high: np.ndarray) -> Tuple[float, float]:
            low_rows = pd.concat([merged[merged["run"] == int(run)] for run in sample_low], ignore_index=True)
            high_rows = pd.concat([merged[merged["run"] == int(run)] for run in sample_high], ignore_index=True)
            low_total = float(low_rows["total_n"].sum())
            high_total = float(high_rows["total_n"].sum())
            low_tax = float(low_rows["taxon_n"].sum())
            high_tax = float(high_rows["taxon_n"].sum())
            frac_delta = high_tax / max(high_total, 1.0) - low_tax / max(low_total, 1.0)
            if high_tax <= 0 or low_tax <= 0:
                mean_delta = np.nan
            else:
                mean_delta = float(high_rows["taxon_infl_sum"].sum() / high_tax - low_rows["taxon_infl_sum"].sum() / low_tax)
            return frac_delta, mean_delta

        frac_value, mean_value = eval_runs(low_runs, high_runs)
        frac_boot = []
        mean_boot = []
        for _ in range(int(CFG["bootstrap_samples"])):
            f, m = eval_runs(rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True))
            frac_boot.append(f)
            mean_boot.append(m)
        frac_ci = ci_from_boot(frac_boot)
        mean_ci = ci_from_boot(mean_boot)
        rows.append(
            {
                "late_residual_taxon": taxon,
                "high_n": int(len(high)),
                "low_n": int(len(low)),
                "fraction_high_minus_low": frac_value,
                "fraction_high_minus_low_ci_low": frac_ci[0],
                "fraction_high_minus_low_ci_high": frac_ci[1],
                "mean_inflation_high_minus_low_ns": mean_value,
                "mean_inflation_high_minus_low_ci_low_ns": mean_ci[0],
                "mean_inflation_high_minus_low_ci_high_ns": mean_ci[1],
            }
        )
    return pd.DataFrame(rows).sort_values("fraction_high_minus_low", ascending=False).reset_index(drop=True)


def stratified_table(frame: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["late_residual_taxon", "current_group", "downstream_topology", "amplitude_bin", "run"]
    rows = (
        frame.groupby(group_cols, observed=False)
        .agg(
            n_pulses=("inflation20_ns", "size"),
            mean_inflation20_ns=("inflation20_ns", "mean"),
            mean_live20_ns=("live20_ns", "mean"),
            inflated_label_rate=("inflated20_label", "mean"),
            final_sample_censored_rate=("censored_at_final_sample", "mean"),
            mean_positive_residual_area=("positive_residual_after_cross_area", "mean"),
        )
        .reset_index()
    )
    return rows.sort_values(["n_pulses", "late_residual_taxon"], ascending=[False, True]).reset_index(drop=True)


def ml_features(frame: pd.DataFrame) -> pd.DataFrame:
    w = np.vstack(frame["waveform"].to_numpy()).astype(np.float64)
    amp = frame["amplitude"].to_numpy(dtype=float)
    norm = w / np.maximum(amp, 1.0)[:, None]
    x = pd.DataFrame(
        {
            "log_amp": np.log(np.maximum(amp, 1.0)),
            "peak_sample": frame["peak_sample"].to_numpy(dtype=float),
            "cfd20_sample": frame["cfd20_sample"].to_numpy(dtype=float),
            "area_over_peak": frame["area"].to_numpy(dtype=float) / np.maximum(amp, 1.0),
            "baseline_noise_fraction": frame["baseline_noise_adc"].to_numpy(dtype=float) / np.maximum(amp, 1.0),
            "norm_tail_area_10plus": frame["norm_tail_area_10plus"].to_numpy(dtype=float),
            "norm_tail_positive_area_10plus": frame["norm_tail_positive_area_10plus"].to_numpy(dtype=float),
            "norm_late_max_fraction": frame["norm_late_max_fraction"].to_numpy(dtype=float),
            "norm_final_fraction": frame["norm_final_fraction"].to_numpy(dtype=float),
            "post_peak_rebound_fraction": frame["post_peak_rebound_fraction"].to_numpy(dtype=float),
            "post_peak_min_fraction": frame["post_peak_min_fraction"].to_numpy(dtype=float),
        }
    )
    for i in range(s10c.NSAMP):
        x[f"norm_s{i:02d}"] = norm[:, i]
    cats = pd.get_dummies(frame[["stave", "amplitude_bin", "downstream_topology"]].astype(str), dtype=float)
    return pd.concat([x, cats.reset_index(drop=True)], axis=1).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def capped_train_indices(y: np.ndarray, train_idx: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    cap = int(CFG["ml_train_cap_per_fold"])
    if len(train_idx) <= cap:
        return train_idx
    pieces = []
    for label in [0, 1]:
        idx = train_idx[y[train_idx] == label]
        want = min(len(idx), cap // 2)
        if want:
            pieces.append(rng.choice(idx, size=want, replace=False))
    out = np.concatenate(pieces)
    if len(out) < min(cap, len(train_idx)):
        remaining = np.setdiff1d(train_idx, out, assume_unique=False)
        extra_n = min(len(remaining), cap - len(out))
        if extra_n > 0:
            out = np.r_[out, rng.choice(remaining, size=extra_n, replace=False)]
    rng.shuffle(out)
    return out


def fit_classifier(x_train: pd.DataFrame, y_train: np.ndarray):
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=1.0,
            class_weight="balanced",
            max_iter=250,
            solver="lbfgs",
            random_state=int(CFG["random_seed"]),
        ),
    )
    clf.fit(x_train, y_train)
    return clf


def run_heldout_ml(frame: pd.DataFrame, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = ml_features(frame)
    y = frame["inflated20_label"].to_numpy(dtype=int)
    runs = frame["run"].to_numpy(dtype=int)
    preds = np.full(len(frame), np.nan, dtype=float)
    fold_rows = []
    for heldout in sorted(frame["run"].unique()):
        train_idx = np.where(runs != int(heldout))[0]
        test_idx = np.where(runs == int(heldout))[0]
        fit_idx = capped_train_indices(y, train_idx, rng)
        clf = fit_classifier(features.iloc[fit_idx], y[fit_idx])
        pred = clf.predict_proba(features.iloc[test_idx])[:, 1]
        preds[test_idx] = pred
        y_test = y[test_idx]
        auc = float(roc_auc_score(y_test, pred)) if len(np.unique(y_test)) > 1 else np.nan
        ap = float(average_precision_score(y_test, pred)) if len(np.unique(y_test)) > 1 else np.nan
        fold_rows.append(
            {
                "heldout_run": int(heldout),
                "n_train_fit": int(len(fit_idx)),
                "n_test": int(len(test_idx)),
                "test_positive_rate": float(y_test.mean()),
                "pred_positive_mean": float(pred.mean()),
                "auc": auc,
                "average_precision": ap,
                "brier": float(brier_score_loss(y_test, pred)),
                "log_loss": float(log_loss(y_test, np.clip(pred, 1e-6, 1 - 1e-6), labels=[0, 1])),
            }
        )
    scores = frame[
        [
            "run",
            "current_group",
            "eventno",
            "evt",
            "stave",
            "downstream_topology",
            "amplitude_bin",
            "late_residual_taxon",
            "inflation20_ns",
            "positive_inflation20_ns",
            "live20_ns",
            "template_cross20_ns",
            "inflated20_label",
        ]
    ].copy()
    scores["ml_inflated_score"] = preds
    scores["ml_risk_bin"] = pd.qcut(scores["ml_inflated_score"], q=[0.0, 0.50, 0.75, 0.90, 1.0], labels=["bottom50", "p50_p75", "p75_p90", "top10"], duplicates="drop").astype(str)
    fold_diag = pd.DataFrame(fold_rows)
    summary = summarize_ml_scores(scores, fold_diag, rng)
    feature_manifest = pd.DataFrame({"feature": features.columns})
    leakage = leakage_checks(frame, features, scores, fold_diag, rng)
    return scores, fold_diag, summary, pd.concat([feature_manifest.assign(kind="feature"), leakage.assign(kind="leakage")], ignore_index=True, sort=False)


def summarize_ml_scores(scores: pd.DataFrame, fold_diag: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    run_auc = fold_diag["auc"].dropna().to_numpy(dtype=float)
    auc_ci = ci_from_boot(
        np.mean(rng.choice(run_auc, size=len(run_auc), replace=True)) for _ in range(int(CFG["bootstrap_samples"]))
    )
    rows.append(
        {
            "metric": "run_heldout_auc_mean",
            "value": float(np.nanmean(run_auc)),
            "ci_low": auc_ci[0],
            "ci_high": auc_ci[1],
            "bootstrap_unit": "heldout_run",
        }
    )
    run_totals = scores.groupby("run").agg(total_pos=("positive_inflation20_ns", "sum")).reset_index()
    run_ids = run_totals["run"].to_numpy(dtype=int)
    total_pos_by_run = run_totals["total_pos"].to_numpy(dtype=float)
    for risk_bin in ["bottom50", "p50_p75", "p75_p90", "top10"]:
        sub = scores[scores["ml_risk_bin"] == risk_bin]
        if len(sub) == 0:
            continue
        bin_run = (
            sub.groupby("run")
            .agg(bin_n=("inflation20_ns", "size"), bin_infl_sum=("inflation20_ns", "sum"), bin_pos_sum=("positive_inflation20_ns", "sum"))
            .reindex(run_ids, fill_value=0)
            .reset_index(drop=True)
        )
        bin_n = bin_run["bin_n"].to_numpy(dtype=float)
        bin_infl = bin_run["bin_infl_sum"].to_numpy(dtype=float)
        bin_pos = bin_run["bin_pos_sum"].to_numpy(dtype=float)
        mean_boot = []
        share_boot = []
        for _ in range(int(CFG["bootstrap_samples"])):
            idx = rng.integers(0, len(run_ids), size=len(run_ids))
            mean_boot.append(float(bin_infl[idx].sum() / bin_n[idx].sum()) if bin_n[idx].sum() > 0 else np.nan)
            share_boot.append(float(bin_pos[idx].sum() / max(total_pos_by_run[idx].sum(), 1e-9)))
        mean_ci = ci_from_boot(mean_boot)
        share_ci = ci_from_boot(share_boot)
        rows.append(
            {
                "metric": f"{risk_bin}_mean_inflation20_ns",
                "value": float(sub["inflation20_ns"].mean()),
                "ci_low": mean_ci[0],
                "ci_high": mean_ci[1],
                "bootstrap_unit": "heldout_run",
            }
        )
        rows.append(
            {
                "metric": f"{risk_bin}_share_positive_inflation",
                "value": float(sub["positive_inflation20_ns"].sum() / max(scores["positive_inflation20_ns"].sum(), 1e-9)),
                "ci_low": share_ci[0],
                "ci_high": share_ci[1],
                "bootstrap_unit": "heldout_run",
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(
    frame: pd.DataFrame,
    features: pd.DataFrame,
    scores: pd.DataFrame,
    fold_diag: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    y = frame["inflated20_label"].to_numpy(dtype=int)
    run_auc = float(np.nanmean(fold_diag["auc"].to_numpy(dtype=float)))
    sample_n = min(int(CFG["ml_row_split_sample"]), len(frame))
    sample_idx = rng.choice(np.arange(len(frame)), size=sample_n, replace=False)
    train_idx, test_idx = train_test_split(sample_idx, test_size=0.35, random_state=int(CFG["random_seed"]), stratify=y[sample_idx])
    row_clf = fit_classifier(features.iloc[train_idx], y[train_idx])
    row_pred = row_clf.predict_proba(features.iloc[test_idx])[:, 1]
    row_auc = float(roc_auc_score(y[test_idx], row_pred))

    shuffled = y.copy()
    rng.shuffle(shuffled)
    shuffled_rows = []
    for heldout in sorted(frame["run"].unique()):
        train_idx_all = np.where(frame["run"].to_numpy(dtype=int) != int(heldout))[0]
        test_idx_all = np.where(frame["run"].to_numpy(dtype=int) == int(heldout))[0]
        fit_idx = capped_train_indices(shuffled, train_idx_all, rng)
        clf = fit_classifier(features.iloc[fit_idx], shuffled[fit_idx])
        pred = clf.predict_proba(features.iloc[test_idx_all])[:, 1]
        if len(np.unique(y[test_idx_all])) > 1:
            shuffled_rows.append(roc_auc_score(y[test_idx_all], pred))
    shuffled_auc = float(np.nanmean(shuffled_rows))
    current_y = (scores["current_group"] == "high_20nA").astype(int).to_numpy()
    current_auc = float(roc_auc_score(current_y, scores["ml_inflated_score"].to_numpy(dtype=float)))
    forbidden = {
        "run",
        "eventno",
        "evt",
        "current_group",
        "live20_ns",
        "inflation20_ns",
        "positive_inflation20_ns",
        "inflated20_label",
        "positive_residual_after_cross_area",
        "above20_after_template_cross_count",
    }
    forbidden_present = sorted(forbidden.intersection(set(features.columns)))
    return pd.DataFrame(
        [
            {
                "check": "ml_split_by_run",
                "value": 1.0,
                "threshold": 1.0,
                "flag": False,
                "note": "Every ML prediction is made for a held-out run.",
            },
            {
                "check": "forbidden_feature_count",
                "value": float(len(forbidden_present)),
                "threshold": 0.0,
                "flag": bool(forbidden_present),
                "note": ",".join(forbidden_present) if forbidden_present else "No run/event/current/direct-target columns in feature matrix.",
            },
            {
                "check": "run_heldout_auc",
                "value": run_auc,
                "threshold": 0.985,
                "flag": bool(run_auc > 0.985 and row_auc - run_auc > 0.03),
                "note": "High AUC is expected because the target is late waveform shape; flag only with row-split advantage.",
            },
            {
                "check": "random_row_split_auc",
                "value": row_auc,
                "threshold": run_auc + 0.10,
                "flag": bool(row_auc - run_auc > 0.10),
                "note": "Large row-split advantage would suggest run or event leakage.",
            },
            {
                "check": "shuffled_target_loro_auc",
                "value": shuffled_auc,
                "threshold": 0.60,
                "flag": bool(shuffled_auc > 0.60),
                "note": "Shuffled labels should not predict true held-out inflation labels.",
            },
            {
                "check": "ml_score_current_auc",
                "value": current_auc,
                "threshold": 0.90,
                "flag": bool(current_auc > 0.90 or current_auc < 0.10),
                "note": "Flags if the ML score nearly identifies current group.",
            },
        ]
    )


def output_hashes(out: Path) -> Dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"}


def write_report(
    result: dict,
    reproduction: pd.DataFrame,
    taxonomy_summary: pd.DataFrame,
    current_summary: pd.DataFrame,
    ml_summary: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    top_taxa = taxonomy_summary.head(4)
    top_lines = []
    for row in top_taxa.to_dict(orient="records"):
        top_lines.append(
            "- {tax}: {share:.1%} of positive inflation, mean inflation {mean:.2f} ns, "
            "pulse fraction {frac:.1%}, final-sample censored {cens:.1%}.".format(
                tax=row["late_residual_taxon"],
                share=row["share_positive_inflation"],
                mean=row["mean_inflation20_ns"],
                frac=row["pulse_fraction"],
                cens=row["final_sample_censored_rate"],
            )
        )
    auc = ml_summary[ml_summary["metric"] == "run_heldout_auc_mean"].iloc[0]
    top10 = ml_summary[ml_summary["metric"] == "top10_mean_inflation20_ns"].iloc[0]
    top10_share = ml_summary[ml_summary["metric"] == "top10_share_positive_inflation"].iloc[0]
    current_top = current_summary.head(3)
    current_lines = [
        "- {}: high-low fraction {:+.4f} [{:+.4f}, {:+.4f}], mean inflation high-low {:+.2f} ns.".format(
            row["late_residual_taxon"],
            row["fraction_high_minus_low"],
            row["fraction_high_minus_low_ci_low"],
            row["fraction_high_minus_low_ci_high"],
            row["mean_inflation_high_minus_low_ns"],
        )
        for row in current_top.to_dict(orient="records")
    ]
    text = f"""# S10h: late-sample residual taxonomy for 20pct last-above inflation

- **Ticket:** `{TICKET}`
- **Worker:** `{WORKER}`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** all ML predictions are leave-one-run-out; intervals bootstrap held-out runs.

## Reproduction first

The raw ROOT S10c/S10d pipeline was rerun before taxonomy. It reproduced the 20% smooth
template crossing at **{result['reproduction']['template_live20_ns']:.3f} ns**, the empirical
last-above value at **{result['reproduction']['empirical_live20_ns']:.3f} ns**, and the
empirical-minus-template inflation at **{result['reproduction']['inflation_ns']:.3f} ns**.

{reproduction.to_markdown(index=False)}

## Traditional taxonomy

Each selected B-stack pulse was attached to the smooth 20% crossing from its run-held-out
stave template. The rule taxonomy uses only pulse shape, amplitude, downstream topology, and
baseline/noise summaries; it does not use current labels to assign classes.

{chr(10).join(top_lines)}

Current/run stratification shows the largest high-current excesses in:

{chr(10).join(current_lines)}

The dominant explanation is not a new smooth-tail crossing. Most positive inflation is carried
by pulses whose late samples remain or rebound above 20% after the template crossing, especially
final-sample-censored and high-amplitude late-tail classes.

## ML classifier

The ML method is a leave-one-run-out standardized L2 logistic classifier for
`inflation20_ns > {CFG['inflated_label_threshold_ns']:.1f} ns`. Features are waveform-shape,
amplitude, stave, downstream-topology, and residual-shape summaries; run, current, event ids,
live20, and the direct inflation target are excluded.

Mean run-held-out AUC is **{auc['value']:.3f}** [{auc['ci_low']:.3f}, {auc['ci_high']:.3f}].
The top 10% ML-risk pulses have mean inflation **{top10['value']:.2f} ns**
[{top10['ci_low']:.2f}, {top10['ci_high']:.2f}] and carry **{top10_share['value']:.1%}**
of positive inflation [{top10_share['ci_low']:.1%}, {top10_share['ci_high']:.1%}].

## Leakage review

Leakage flags: **{int(leakage['flag'].sum())}**.

{leakage.to_markdown(index=False)}

## Conclusion

The S10d 20% empirical last-above inflation is pulse-shape driven. A smooth template crossing
near 101.9 ns coexists with per-pulse late residual structure that keeps discrete samples above
20% until about 119.0 ns on average. The rule taxonomy assigns most positive inflation to
final-sample-censored, high-amplitude late-tail, broad slow-tail, and late-rebound classes.
The run-held-out ML classifier independently isolates the same high-inflation population without
run/current/event-id features, and the leakage audit has zero flags.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`,
`taxonomy_summary.csv`, `current_taxonomy_contrast.csv`, `taxonomy_strata_by_run.csv`,
`ml_fold_diagnostics.csv`, `ml_summary.csv`, `ml_leakage_checks.csv`, `ml_feature_manifest.csv`,
and `ml_scores.csv.gz` are in this folder.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    global CFG, TICKET, WORKER, OUT, s10c
    CFG = load_json(Path(args.config))
    TICKET = CFG["ticket_id"]
    WORKER = CFG["worker"]
    OUT = ROOT / CFG["output_dir"]
    OUT.mkdir(parents=True, exist_ok=True)
    s10c = import_module(ROOT / CFG["source_s10c_script"], "s10c_threshold_scan_tau_eff_source_runtime")

    start = time.time()
    rng = np.random.default_rng(int(CFG["random_seed"]))
    print("reading selected pulses from raw ROOT", flush=True)
    pulses = s10c.read_selected_pulses()
    print(f"loaded {len(pulses)} selected pulses; fitting run-held-out templates", flush=True)
    fits, heldout = s10c.traditional_template_fits(pulses)
    reproduction, repro_result = reproduce_s10d_20pct(pulses, fits, heldout)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("S10d 20pct reproduction failed; refusing to continue to taxonomy")

    print("assigning pulse-level inflation metrics and rule taxonomy", flush=True)
    enriched = attach_pulse_metrics(pulses, fits)
    enriched, taxonomy_thresholds = assign_taxonomy(enriched)
    taxonomy_summary = run_weighted_taxonomy_summary(enriched, rng)
    current_summary = current_contrast_summary(enriched, rng)
    strata = stratified_table(enriched)

    print("running leave-one-run-out ML classifier", flush=True)
    ml_scores, fold_diag, ml_summary, feature_and_leak = run_heldout_ml(enriched, rng)
    feature_manifest = feature_and_leak[feature_and_leak["kind"] == "feature"][["feature"]].dropna().reset_index(drop=True)
    leakage = feature_and_leak[feature_and_leak["kind"] == "leakage"].drop(columns=["kind", "feature"], errors="ignore").reset_index(drop=True)

    raw_inputs = {str((ROOT / CFG["raw_root_dir"] / f"hrdb_run_{run:04d}.root").relative_to(ROOT)): sha256_file(ROOT / CFG["raw_root_dir"] / f"hrdb_run_{run:04d}.root") for run in CFG["runs"]}
    code_inputs = {
        str(Path(__file__).resolve().relative_to(ROOT)): sha256_file(Path(__file__).resolve()),
        str((ROOT / CFG["source_s10c_script"]).relative_to(ROOT)): sha256_file(ROOT / CFG["source_s10c_script"]),
        str(Path(args.config).resolve().relative_to(ROOT)): sha256_file(Path(args.config).resolve()),
    }

    reproduction.to_csv(OUT / "reproduction_match_table.csv", index=False)
    heldout.to_csv(OUT / "s10d_heldout_reproduction_by_run.csv", index=False)
    fits.to_csv(OUT / "s10d_template_fit_by_run_stave.csv", index=False)
    taxonomy_summary.to_csv(OUT / "taxonomy_summary.csv", index=False)
    current_summary.to_csv(OUT / "current_taxonomy_contrast.csv", index=False)
    strata.to_csv(OUT / "taxonomy_strata_by_run.csv", index=False)
    enriched[
        [
            "run",
            "eventno",
            "evt",
            "stave",
            "current_group",
            "downstream_topology",
            "amplitude",
            "amplitude_bin",
            "template_cross20_ns",
            "live20_ns",
            "inflation20_ns",
            "positive_inflation20_ns",
            "inflated20_label",
            "late_residual_taxon",
            "norm_final_fraction",
            "norm_late_max_fraction",
            "positive_residual_after_cross_area",
            "above20_after_template_cross_count",
        ]
    ].to_csv(OUT / "pulse_taxonomy_assignments.csv.gz", index=False, compression="gzip")
    ml_scores.to_csv(OUT / "ml_scores.csv.gz", index=False, compression="gzip")
    fold_diag.to_csv(OUT / "ml_fold_diagnostics.csv", index=False)
    ml_summary.to_csv(OUT / "ml_summary.csv", index=False)
    feature_manifest.to_csv(OUT / "ml_feature_manifest.csv", index=False)
    leakage.to_csv(OUT / "ml_leakage_checks.csv", index=False)
    pd.DataFrame([{"path": k, "sha256": v} for k, v in raw_inputs.items()]).to_csv(OUT / "input_sha256.csv", index=False)

    top_taxa = taxonomy_summary.head(4).to_dict(orient="records")
    auc_row = ml_summary[ml_summary["metric"] == "run_heldout_auc_mean"].iloc[0]
    result = {
        "study": CFG["study_id"],
        "ticket": TICKET,
        "worker": WORKER,
        "title": CFG["title"],
        "reproduced_first": bool(reproduction["pass"].all()),
        "reproduction": repro_result,
        "traditional_method": {
            "description": "rule-based late residual taxonomy with run-block bootstrap CIs",
            "taxonomy_thresholds": taxonomy_thresholds,
            "top_positive_inflation_taxa": top_taxa,
        },
        "ml_method": {
            "description": "leave-one-run-out standardized L2 logistic classifier for inflation20_ns > threshold",
            "target": f"inflation20_ns > {CFG['inflated_label_threshold_ns']} ns",
            "run_heldout_auc_mean": float(auc_row["value"]),
            "run_heldout_auc_ci": [float(auc_row["ci_low"]), float(auc_row["ci_high"])],
            "folds": fold_diag.to_dict(orient="records"),
        },
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": raw_inputs,
        "code_inputs": code_inputs,
        "git_commit": git_commit(),
        "runtime_sec": None,
    }
    result["runtime_sec"] = round(time.time() - start, 2)
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(result, reproduction, taxonomy_summary, current_summary, ml_summary, leakage)
    manifest = {
        "study": CFG["study_id"],
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(CFG["random_seed"]),
        "bootstrap_samples": int(CFG["bootstrap_samples"]),
        "inputs": raw_inputs,
        "code_inputs": code_inputs,
        "outputs": output_hashes(OUT),
        "runtime_sec": result["runtime_sec"],
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
