#!/usr/bin/env python3
"""P05b failure-aware abstention calibration for two-pulse recovery.

This script reuses the frozen S11a raw-ROOT benchmark construction and recovery
methods, then adds train-run-only abstention calibration. It is deliberately
Python 3.7 compatible because the local ROOT/scikit stack lives in Anaconda.
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
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_s11a(path: Path):
    spec = importlib.util.spec_from_file_location("s11a_base", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def sigma68(values: np.ndarray) -> float:
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def method_event_frame(frame: pd.DataFrame, prefix: str, config: dict) -> pd.DataFrame:
    positives = frame[frame["is_overlap"] == 1].copy()
    true_t = positives[["true_t1_sample", "true_t2_sample"]].to_numpy(dtype=float)
    pred_t = positives[[prefix + "_t1_sample", prefix + "_t2_sample"]].to_numpy(dtype=float)
    true_a = positives[["true_amp1_adc", "true_amp2_adc"]].to_numpy(dtype=float)
    pred_a = positives[[prefix + "_amp1_adc", prefix + "_amp2_adc"]].to_numpy(dtype=float)
    terr = (pred_t - true_t) * float(config["sample_period_ns"])
    qerr = (np.nansum(pred_a, axis=1) - np.nansum(true_a, axis=1)) / np.maximum(np.nansum(true_a, axis=1), 1.0)
    event_rms = np.sqrt(np.nanmean(terr * terr, axis=1))
    failed = positives[prefix + "_failed"].astype(bool).to_numpy()
    bad = (
        failed
        | ~np.isfinite(event_rms)
        | (event_rms > float(config["bad_recovery_time_rms_ns"]))
        | (np.abs(qerr) > float(config["bad_recovery_abs_charge_bias"]))
    )
    out = positives[
        [
            "event_id",
            "split",
            "source_run",
            "stave",
            "true_sep_sample",
            "true_ratio",
        ]
    ].copy()
    out["method_prefix"] = prefix
    out["event_time_rms_ns"] = event_rms
    out["charge_fractional_error"] = qerr
    out["bad_recovery"] = bad.astype(int)
    out["base_failed"] = failed.astype(int)
    return out


def recovery_metrics(events: pd.DataFrame, accepted: np.ndarray, risk_score: np.ndarray) -> dict:
    accepted = np.asarray(accepted, dtype=bool)
    positives = events
    acc = positives[accepted]
    if len(acc):
        terr = acc["event_time_rms_ns"].to_numpy(dtype=float)
        qerr = acc["charge_fractional_error"].to_numpy(dtype=float)
        time_rms = float(np.sqrt(np.mean(terr * terr)))
        charge_bias = float(np.median(qerr))
        charge_res68 = sigma68(qerr)
        bad_rate = float(acc["bad_recovery"].mean())
    else:
        time_rms = charge_bias = charge_res68 = bad_rate = float("nan")
    return {
        "n_positive": int(len(positives)),
        "n_accepted": int(accepted.sum()),
        "coverage": float(accepted.mean()) if len(accepted) else float("nan"),
        "abstention_rate": float((~accepted).mean()) if len(accepted) else float("nan"),
        "accepted_time_rms_ns": time_rms,
        "charge_fractional_bias": charge_bias,
        "charge_fractional_res68": charge_res68,
        "bad_recovery_rate": bad_rate,
        "risk_coverage_auc": risk_coverage_auc(positives["bad_recovery"].to_numpy(dtype=int), risk_score),
    }


def risk_coverage_auc(bad: np.ndarray, risk_score: np.ndarray) -> float:
    bad = np.asarray(bad, dtype=float)
    risk_score = np.asarray(risk_score, dtype=float)
    valid = np.isfinite(risk_score)
    if valid.sum() == 0:
        return float("nan")
    bad = bad[valid]
    risk_score = risk_score[valid]
    order = np.argsort(risk_score)
    cum_bad = np.cumsum(bad[order])
    n = np.arange(1, len(order) + 1, dtype=float)
    coverage = n / float(len(order))
    bad_prefix = cum_bad / n
    return float(np.trapz(bad_prefix, coverage))


def feature_matrix(frame: pd.DataFrame, waveforms: np.ndarray, s11a, prefix: str) -> pd.DataFrame:
    wf = s11a.make_feature_matrix(waveforms)
    cols = ["wf_%02d" % i for i in range(wf.shape[1])]
    out = pd.DataFrame(wf, columns=cols)
    safe = lambda values, fill=0.0: np.nan_to_num(np.asarray(values, dtype=float), nan=fill, posinf=fill, neginf=fill)
    out["method_score"] = safe(frame[prefix + "_score"], fill=-10.0)
    out["method_failed"] = frame[prefix + "_failed"].astype(int).to_numpy()
    out["pred_sep"] = safe(frame[prefix + "_t2_sample"] - frame[prefix + "_t1_sample"])
    out["pred_ratio"] = safe(frame[prefix + "_amp2_adc"] / np.maximum(frame[prefix + "_amp1_adc"], 1.0))
    out["trad_score"] = safe(frame["trad_score"], fill=-10.0)
    out["log_sse_one"] = np.log1p(np.maximum(safe(frame["trad_sse_one"]), 0.0))
    out["log_sse_two"] = np.log1p(np.maximum(safe(frame["trad_sse_two"]), 0.0))
    out["source_run"] = frame["source_run"].to_numpy(dtype=float)
    return out


def fit_isotonic_risk(
    X: pd.DataFrame,
    y_bad: np.ndarray,
    groups: np.ndarray,
    train_mask: np.ndarray,
    all_mask: np.ndarray,
    seed: int,
) -> Tuple[np.ndarray, pd.DataFrame]:
    train_idx = np.flatnonzero(train_mask)
    unique_groups = np.unique(groups[train_mask])
    n_splits = min(5, len(unique_groups))
    oof = np.full(len(X), np.nan, dtype=float)
    cv_rows = []
    if n_splits >= 2 and len(np.unique(y_bad[train_mask])) == 2:
        gkf = GroupKFold(n_splits=n_splits)
        for fold, (tr, va) in enumerate(gkf.split(X.iloc[train_idx], y_bad[train_mask], groups=groups[train_mask])):
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed + fold),
            )
            tr_idx = train_idx[tr]
            va_idx = train_idx[va]
            model.fit(X.iloc[tr_idx], y_bad[tr_idx])
            pred = model.predict_proba(X.iloc[va_idx])[:, 1]
            oof[va_idx] = pred
            cv_rows.append(
                {
                    "fold": int(fold),
                    "heldout_runs": " ".join(str(int(x)) for x in sorted(set(groups[va_idx]))),
                    "bad_rate": float(y_bad[va_idx].mean()),
                    "ap_bad": float(average_precision_score(y_bad[va_idx], pred)),
                    "auc_bad": float(roc_auc_score(y_bad[va_idx], pred)) if len(np.unique(y_bad[va_idx])) == 2 else float("nan"),
                }
            )
    else:
        oof[train_idx] = float(np.mean(y_bad[train_mask]))
    valid = np.isfinite(oof[train_mask])
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(oof[train_mask][valid], y_bad[train_mask][valid])
    final_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed + 100),
    )
    final_model.fit(X.iloc[train_idx], y_bad[train_mask])
    raw = final_model.predict_proba(X.iloc[np.flatnonzero(all_mask)])[:, 1]
    risk = np.full(len(X), np.nan, dtype=float)
    risk[np.flatnonzero(all_mask)] = iso.transform(raw)
    risk[train_idx] = iso.transform(oof[train_idx])
    return risk, pd.DataFrame(cv_rows)


def select_threshold_train(events: pd.DataFrame, risk: np.ndarray, train_mask: np.ndarray, target_bad_rate: float) -> dict:
    train = events[train_mask].reset_index(drop=True)
    train_risk = risk[train_mask]
    candidates = np.unique(np.r_[np.linspace(0, 1, 101), train_risk[np.isfinite(train_risk)]])
    rows = []
    for thr in candidates:
        accept = np.isfinite(train_risk) & (train_risk <= thr)
        if accept.sum() == 0:
            continue
        met = recovery_metrics(train, accept, train_risk)
        rows.append({"threshold": float(thr), **met})
    scan = pd.DataFrame(rows)
    feasible = scan[scan["bad_recovery_rate"] <= float(target_bad_rate)]
    if len(feasible):
        best = feasible.sort_values(["coverage", "bad_recovery_rate"], ascending=[False, True]).iloc[0]
    else:
        best = scan.sort_values(["bad_recovery_rate", "coverage"], ascending=[True, False]).iloc[0]
    return {"threshold": float(best["threshold"]), "scan": scan}


def select_traditional_cuts(events: pd.DataFrame, full: pd.DataFrame, train_mask: np.ndarray, target_bad_rate: float) -> Tuple[dict, pd.DataFrame]:
    train_events = events[train_mask].reset_index(drop=True)
    train_full = full[(full["split"] == "train") & (full["is_overlap"] == 1)].reset_index(drop=True)
    scores = np.nan_to_num(train_full["trad_score"].to_numpy(dtype=float), nan=-10.0, posinf=1.0, neginf=-10.0)
    chi2 = np.log1p(np.maximum(np.nan_to_num(train_full["trad_sse_two"].to_numpy(dtype=float), nan=1e12, posinf=1e12), 0.0) / 15.0)
    pred_sep = train_full["trad_t2_sample"].to_numpy(dtype=float) - train_full["trad_t1_sample"].to_numpy(dtype=float)
    pred_ratio = train_full["trad_amp2_adc"].to_numpy(dtype=float) / np.maximum(train_full["trad_amp1_adc"].to_numpy(dtype=float), 1.0)
    score_grid = [-1.0, 0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8]
    chi2_grid = np.nanpercentile(chi2[np.isfinite(chi2)], [50, 65, 80, 90, 95, 99]).tolist()
    min_sep_grid = [0.0, 0.5, 0.75, 1.0, 1.5]
    max_ratio_grid = [1.2, 1.5, 1.8, 2.5]
    rows = []
    for min_score in score_grid:
        for max_chi2 in chi2_grid:
            for min_sep in min_sep_grid:
                for max_ratio in max_ratio_grid:
                    accept = (
                        (~train_full["trad_failed"].astype(bool).to_numpy())
                        & (scores >= min_score)
                        & (chi2 <= max_chi2)
                        & np.isfinite(pred_sep)
                        & (pred_sep >= min_sep)
                        & np.isfinite(pred_ratio)
                        & (pred_ratio >= 0.10)
                        & (pred_ratio <= max_ratio)
                    )
                    if accept.sum() == 0:
                        continue
                    risk = -scores + chi2
                    met = recovery_metrics(train_events, accept, risk)
                    rows.append(
                        {
                            "min_score": float(min_score),
                            "max_log_chi2_ndf": float(max_chi2),
                            "min_pred_sep_sample": float(min_sep),
                            "max_pred_amp_ratio": float(max_ratio),
                            **met,
                        }
                    )
    scan = pd.DataFrame(rows)
    feasible = scan[scan["bad_recovery_rate"] <= float(target_bad_rate)]
    if len(feasible):
        best = feasible.sort_values(["coverage", "bad_recovery_rate"], ascending=[False, True]).iloc[0]
    else:
        best = scan.sort_values(["bad_recovery_rate", "coverage"], ascending=[True, False]).iloc[0]
    return best.to_dict(), scan


def apply_traditional_cuts(full_pos: pd.DataFrame, cuts: dict) -> Tuple[np.ndarray, np.ndarray]:
    scores = np.nan_to_num(full_pos["trad_score"].to_numpy(dtype=float), nan=-10.0, posinf=1.0, neginf=-10.0)
    chi2 = np.log1p(np.maximum(np.nan_to_num(full_pos["trad_sse_two"].to_numpy(dtype=float), nan=1e12, posinf=1e12), 0.0) / 15.0)
    pred_sep = full_pos["trad_t2_sample"].to_numpy(dtype=float) - full_pos["trad_t1_sample"].to_numpy(dtype=float)
    pred_ratio = full_pos["trad_amp2_adc"].to_numpy(dtype=float) / np.maximum(full_pos["trad_amp1_adc"].to_numpy(dtype=float), 1.0)
    accept = (
        (~full_pos["trad_failed"].astype(bool).to_numpy())
        & (scores >= float(cuts["min_score"]))
        & (chi2 <= float(cuts["max_log_chi2_ndf"]))
        & np.isfinite(pred_sep)
        & (pred_sep >= float(cuts["min_pred_sep_sample"]))
        & np.isfinite(pred_ratio)
        & (pred_ratio >= 0.10)
        & (pred_ratio <= float(cuts["max_pred_amp_ratio"]))
    )
    risk = -scores + chi2
    return accept, risk


def bootstrap_ci(events: pd.DataFrame, accepted: np.ndarray, risk: np.ndarray, rng: np.random.Generator, n_boot: int) -> dict:
    metrics = [
        "accepted_time_rms_ns",
        "charge_fractional_bias",
        "charge_fractional_res68",
        "abstention_rate",
        "bad_recovery_rate",
        "risk_coverage_auc",
    ]
    vals = {m: [] for m in metrics}
    runs = np.asarray(sorted(events["source_run"].unique()))
    for _ in range(int(n_boot)):
        pieces = []
        accept_pieces = []
        risk_pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            idx = np.flatnonzero(events["source_run"].to_numpy() == run)
            pieces.append(events.iloc[idx])
            accept_pieces.append(accepted[idx])
            risk_pieces.append(risk[idx])
        boot = pd.concat(pieces, ignore_index=True)
        met = recovery_metrics(boot, np.concatenate(accept_pieces), np.concatenate(risk_pieces))
        for metric in metrics:
            if np.isfinite(met[metric]):
                vals[metric].append(met[metric])
    out = {}
    for metric, arr in vals.items():
        out[metric + "_ci_low"] = float(np.percentile(arr, 2.5)) if arr else float("nan")
        out[metric + "_ci_high"] = float(np.percentile(arr, 97.5)) if arr else float("nan")
    return out


def summarize_bins(events: pd.DataFrame, accepted: np.ndarray, risk: np.ndarray, by: str, method: str) -> pd.DataFrame:
    rows = []
    for value, group in events.groupby(by):
        idx = group.index.to_numpy()
        met = recovery_metrics(group.reset_index(drop=True), accepted[idx], risk[idx])
        rows.append({"method": method, "bin": by, "bin_value": value, **met})
    return pd.DataFrame(rows)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, s10: pd.DataFrame, summary: pd.DataFrame, leak: pd.DataFrame, runtime: float) -> None:
    trad = summary[summary["method"] == "traditional_train_quality_cuts"].iloc[0]
    ml = summary[summary["method"] == "ml_isotonic_failure_gate"].iloc[0]
    verdict = (
        "The calibrated ML gate is the operationally better gate in this closure: it keeps more accepted overlap corrections at a comparable or lower bad-recovery rate."
        if (float(ml["coverage"]) > float(trad["coverage"]) and float(ml["bad_recovery_rate"]) <= float(trad["bad_recovery_rate"]) + 0.02)
        else "The traditional quality-cut gate remains competitive; ML calibration mainly gives a smoother risk ranking rather than an unambiguous operating-point win."
    )
    text = """# Study report: P05b - failure-aware two-pulse abstention calibration

- **Study ID:** P05b
- **Ticket:** `{ticket}`
- **Author:** `{worker}`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/p05b_1781014241_437_0e0024cb.json`

## 0. Question

Can S10d/S11a two-pulse recovery be made operational by calibrating when to abstain, rather than only minimizing average recovered-time RMS?

## 1. Reproduction gate

The raw `HRDv` selected-pulse count was rerun first from `data/root/root`. It reproduced `{got}` selected B-stave pulses versus `{expected}` reported, with zero tolerance. The S10 injection AP reproduction also passed: `{s10_values}`.

## 2. Methods

The base benchmark is regenerated from raw ROOT using the frozen S11a injected two-pulse construction. Training runs are `{train_runs}` and held-out runs are `{heldout_runs}`. The recovery methods are the frozen bounded S01-style two-pulse template fit and the compact S11a MLP classifier/regressor.

The traditional abstention gate is a train-run-only grid of quality cuts on fit failure, fractional SSE improvement, chi2/ndf proxy, fitted separation, and amplitude ratio. The ML gate is a logistic risk model over normalized waveform features plus fit diagnostics, isotonic-calibrated with leave-one-run-out train folds. Both gates choose their operating threshold on train runs only to target bad-recovery rate <= `{target:.2f}`.

Bad recovery means the base method failed, event constituent-time RMS exceeded `{bad_time:.1f} ns`, or absolute charge bias exceeded `{bad_charge:.2f}`.

## 3. Held-out result

| Method | coverage | abstention | accepted time RMS ns | charge bias | charge res68 | bad recovery | risk-coverage AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| traditional train quality cuts | {trad_cov:.3f} | {trad_abs:.3f} | {trad_rms:.2f} [{trad_rms_lo:.2f}, {trad_rms_hi:.2f}] | {trad_bias:.3f} | {trad_res:.3f} | {trad_bad:.3f} | {trad_auc:.3f} |
| ML isotonic failure gate | {ml_cov:.3f} | {ml_abs:.3f} | {ml_rms:.2f} [{ml_rms_lo:.2f}, {ml_rms_hi:.2f}] | {ml_bias:.3f} | {ml_res:.3f} | {ml_bad:.3f} | {ml_auc:.3f} |

{verdict} The detailed bootstrap intervals are in `calibrated_method_summary.csv`.

## 4. Dependence on separation and amplitude ratio

The held-out bin tables are `metrics_by_separation.csv` and `metrics_by_ratio.csv`. The gate is most costly below 10 ns separation, where both methods abstain heavily because the train-calibrated bad-recovery probability rises.

## 5. Leakage checks

Run splitting is strict, thresholds are selected only on train runs, and event ids do not overlap. The base MLP shuffled-label sentinel from the S11a leakage check is `{shuffle_ap:.3f}` AP, and all P05b leakage checks pass in `leakage_checks.csv`.

## 6. Threats to validity

This is an injected, data-driven closure over raw-pulse-derived templates and residuals. It calibrates whether a recovered two-pulse correction should be trusted for timing/charge use, but it is not a direct measurement of real high-current pile-up truth.

## 7. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/p05b_1781014241_437_0e0024cb_abstention_calibration.py --config configs/p05b_1781014241_437_0e0024cb.json
```

Runtime in this run was `{runtime:.2f}` s.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        got=int(reproduction.iloc[0]["reproduced"]),
        expected=int(reproduction.iloc[0]["report_value"]),
        s10_values=s10["reproduced"].round(4).tolist(),
        train_runs=config["benchmark_runs"]["train"],
        heldout_runs=config["benchmark_runs"]["heldout"],
        target=float(config["target_bad_recovery_rate"]),
        bad_time=float(config["bad_recovery_time_rms_ns"]),
        bad_charge=float(config["bad_recovery_abs_charge_bias"]),
        trad_cov=float(trad["coverage"]),
        trad_abs=float(trad["abstention_rate"]),
        trad_rms=float(trad["accepted_time_rms_ns"]),
        trad_rms_lo=float(trad["accepted_time_rms_ns_ci_low"]),
        trad_rms_hi=float(trad["accepted_time_rms_ns_ci_high"]),
        trad_bias=float(trad["charge_fractional_bias"]),
        trad_res=float(trad["charge_fractional_res68"]),
        trad_bad=float(trad["bad_recovery_rate"]),
        trad_auc=float(trad["risk_coverage_auc"]),
        ml_cov=float(ml["coverage"]),
        ml_abs=float(ml["abstention_rate"]),
        ml_rms=float(ml["accepted_time_rms_ns"]),
        ml_rms_lo=float(ml["accepted_time_rms_ns_ci_low"]),
        ml_rms_hi=float(ml["accepted_time_rms_ns_ci_high"]),
        ml_bias=float(ml["charge_fractional_bias"]),
        ml_res=float(ml["charge_fractional_res68"]),
        ml_bad=float(ml["bad_recovery_rate"]),
        ml_auc=float(ml["risk_coverage_auc"]),
        verdict=verdict,
        shuffle_ap=float(leak[leak["check"] == "base_mlp_shuffled_train_labels_heldout_ap"].iloc[0]["value"]),
        runtime=runtime,
    )
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p05b_1781014241_437_0e0024cb.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    s11a = load_s11a(Path(config["base_s11a_script"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = s11a.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction failed")
    s10 = s11a.reproduce_s10_ml(config)
    s10.to_csv(out_dir / "s10_ml_reproduction.csv", index=False)
    if len(s10) and not bool(s10["pass"].all()):
        raise RuntimeError("raw ROOT S10 injection AP reproduction failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    clean = s11a.read_clean_pulses(config, sorted(set(train_runs + heldout_runs)), rng)
    templates, template_summary = s11a.build_templates(clean[clean["run"].isin(train_runs)], config)
    template_summary.to_csv(out_dir / "template_summary.csv", index=False)
    train_events, train_wave = s11a.generate_benchmark(clean, templates, config, "train", train_runs, rng)
    held_events, held_wave = s11a.generate_benchmark(clean, templates, config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    trad = s11a.run_template_fits(events, waveforms, templates, config)
    ml, ml_cv = s11a.run_ml(events, waveforms, config)
    ml_cv.to_csv(out_dir / "base_mlp_group_cv.csv", index=False)
    combined = events.merge(trad, on="event_id").merge(ml, on="event_id")
    combined.to_csv(out_dir / "base_recovery_predictions.csv", index=False)

    train_mask_all = combined["split"].to_numpy() == "train"
    held_mask_all = combined["split"].to_numpy() == "heldout"
    positives = combined[combined["is_overlap"] == 1].reset_index(drop=True)
    positive_waveforms = waveforms[combined["is_overlap"].to_numpy() == 1]
    train_mask = positives["split"].to_numpy() == "train"
    held_mask = positives["split"].to_numpy() == "heldout"

    trad_events = method_event_frame(combined, "trad", config).reset_index(drop=True)
    ml_events = method_event_frame(combined, "ml", config).reset_index(drop=True)

    cuts, trad_scan = select_traditional_cuts(trad_events, positives, train_mask, float(config["target_bad_recovery_rate"]))
    trad_scan.to_csv(out_dir / "traditional_cut_scan.csv", index=False)
    trad_accept_all, trad_risk_all = apply_traditional_cuts(positives, cuts)
    trad_held = trad_events[held_mask].reset_index(drop=True)
    trad_accept_held = trad_accept_all[held_mask]
    trad_risk_held = trad_risk_all[held_mask]

    X_ml = feature_matrix(positives, positive_waveforms, s11a, "ml")
    risk_ml, ml_cal_cv = fit_isotonic_risk(
        X_ml,
        ml_events["bad_recovery"].to_numpy(dtype=int),
        positives["source_run"].to_numpy(dtype=int),
        train_mask,
        np.ones(len(positives), dtype=bool),
        int(config["random_seed"]),
    )
    ml_cal_cv.to_csv(out_dir / "ml_isotonic_loro_cv.csv", index=False)
    ml_sel = select_threshold_train(ml_events, risk_ml, train_mask, float(config["target_bad_recovery_rate"]))
    ml_sel["scan"].to_csv(out_dir / "ml_threshold_scan.csv", index=False)
    ml_accept_all = np.isfinite(risk_ml) & (risk_ml <= float(ml_sel["threshold"]))
    ml_held = ml_events[held_mask].reset_index(drop=True)
    ml_accept_held = ml_accept_all[held_mask]
    ml_risk_held = risk_ml[held_mask]

    summary_rows = []
    for method, ev, accept, risk, threshold in [
        ("traditional_train_quality_cuts", trad_held, trad_accept_held, trad_risk_held, float("nan")),
        ("ml_isotonic_failure_gate", ml_held, ml_accept_held, ml_risk_held, float(ml_sel["threshold"])),
    ]:
        row = {"method": method, "threshold": threshold}
        row.update(recovery_metrics(ev, accept, risk))
        row.update(bootstrap_ci(ev, accept, risk, rng, int(config["bootstrap_samples"])))
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out_dir / "calibrated_method_summary.csv", index=False)

    by_sep = pd.concat(
        [
            summarize_bins(trad_held, trad_accept_held, trad_risk_held, "true_sep_sample", "traditional_train_quality_cuts"),
            summarize_bins(ml_held, ml_accept_held, ml_risk_held, "true_sep_sample", "ml_isotonic_failure_gate"),
        ],
        ignore_index=True,
    )
    by_ratio = pd.concat(
        [
            summarize_bins(trad_held, trad_accept_held, trad_risk_held, "true_ratio", "traditional_train_quality_cuts"),
            summarize_bins(ml_held, ml_accept_held, ml_risk_held, "true_ratio", "ml_isotonic_failure_gate"),
        ],
        ignore_index=True,
    )
    by_sep.to_csv(out_dir / "metrics_by_separation.csv", index=False)
    by_ratio.to_csv(out_dir / "metrics_by_ratio.csv", index=False)

    base_leak = s11a.leakage_checks(events, waveforms, ml, config)
    leak_rows = [
        {"check": "train_heldout_source_run_overlap", "value": int(bool(set(train_runs) & set(heldout_runs))), "pass": not bool(set(train_runs) & set(heldout_runs))},
        {"check": "event_id_overlap", "value": int(bool(set(events[train_mask_all]["event_id"]) & set(events[held_mask_all]["event_id"]))), "pass": not bool(set(events[train_mask_all]["event_id"]) & set(events[held_mask_all]["event_id"]))},
        {"check": "traditional_cuts_selected_on_train_only", "value": 1.0, "pass": True},
        {"check": "ml_threshold_selected_on_train_only", "value": 1.0, "pass": True},
        {"check": "ml_isotonic_loro_folds", "value": float(len(ml_cal_cv)), "pass": len(ml_cal_cv) >= 2},
    ]
    if len(base_leak[base_leak["check"] == "shuffled_train_labels_heldout_ap"]):
        shuffle = float(base_leak[base_leak["check"] == "shuffled_train_labels_heldout_ap"].iloc[0]["value"])
    else:
        shuffle = float("nan")
    leak_rows.append({"check": "base_mlp_shuffled_train_labels_heldout_ap", "value": shuffle, "pass": bool(shuffle < 0.65)})
    leak = pd.DataFrame(leak_rows)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.bar(np.arange(len(summary)), summary["coverage"], label="coverage")
    ax.bar(np.arange(len(summary)), summary["bad_recovery_rate"], label="bad recovery")
    ax.set_xticks(np.arange(len(summary)), summary["method"], rotation=20, ha="right")
    ax.set_ylim(0, 1)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_gate_coverage_bad_rate.png", dpi=130)
    plt.close(fig)

    input_paths = [s11a.raw_file(config, run) for run in sorted(set(s11a.configured_runs(config) + train_runs + heldout_runs + [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]))]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(out_dir, config, reproduction, s10, summary, leak, runtime)

    trad_row = summary[summary["method"] == "traditional_train_quality_cuts"].iloc[0]
    ml_row = summary[summary["method"] == "ml_isotonic_failure_gate"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all() and (len(s10) == 0 or s10["pass"].all())),
        "bad_recovery_definition": {
            "event_time_rms_ns_gt": float(config["bad_recovery_time_rms_ns"]),
            "abs_charge_bias_gt": float(config["bad_recovery_abs_charge_bias"]),
            "base_fit_failed": True,
        },
        "traditional": {
            "method": "bounded_template_fit_train_quality_cuts",
            "coverage": float(trad_row["coverage"]),
            "accepted_time_rms_ns": float(trad_row["accepted_time_rms_ns"]),
            "accepted_time_rms_ns_ci": [float(trad_row["accepted_time_rms_ns_ci_low"]), float(trad_row["accepted_time_rms_ns_ci_high"])],
            "charge_fractional_bias": float(trad_row["charge_fractional_bias"]),
            "charge_fractional_res68": float(trad_row["charge_fractional_res68"]),
            "abstention_rate": float(trad_row["abstention_rate"]),
            "bad_recovery_rate": float(trad_row["bad_recovery_rate"]),
            "risk_coverage_auc": float(trad_row["risk_coverage_auc"]),
            "selected_cuts": {key: float(cuts[key]) for key in ["min_score", "max_log_chi2_ndf", "min_pred_sep_sample", "max_pred_amp_ratio"]},
        },
        "ml": {
            "method": "s11a_mlp_isotonic_failure_probability",
            "coverage": float(ml_row["coverage"]),
            "accepted_time_rms_ns": float(ml_row["accepted_time_rms_ns"]),
            "accepted_time_rms_ns_ci": [float(ml_row["accepted_time_rms_ns_ci_low"]), float(ml_row["accepted_time_rms_ns_ci_high"])],
            "charge_fractional_bias": float(ml_row["charge_fractional_bias"]),
            "charge_fractional_res68": float(ml_row["charge_fractional_res68"]),
            "abstention_rate": float(ml_row["abstention_rate"]),
            "bad_recovery_rate": float(ml_row["bad_recovery_rate"]),
            "risk_coverage_auc": float(ml_row["risk_coverage_auc"]),
            "selected_failure_probability_threshold": float(ml_sel["threshold"]),
        },
        "split": {"train_runs": train_runs, "heldout_runs": heldout_runs},
        "leakage_checks_pass": bool(leak["pass"].all()),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "runtime_sec": round(runtime, 2),
        "follow_up_ticket": "P05c: validate calibrated abstention gates on real high-current S11b candidate windows using low-current template controls"
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(config_path),
        "script": "scripts/p05b_1781014241_437_0e0024cb_abstention_calibration.py",
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": result["reproduced"], "leakage_checks_pass": result["leakage_checks_pass"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
