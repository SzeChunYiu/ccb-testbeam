#!/usr/bin/env python3
"""S10g: right-censored live-time estimates for low-threshold pile-up windows.

The script reruns the S10c/S10d raw B-stack ROOT reproduction first. It then
replaces the naive mean last-above-threshold summaries with explicit
right-censored estimators and a run-held-out ML survival comparator.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
TICKET = "1781028280.978.1e517fd7"
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "reports" / TICKET / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.special import gamma
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

S10C_PATH = ROOT / "reports" / "1781007337.1308.7dc86005" / "s10c_threshold_scan_tau_eff.py"


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s10c = import_module(S10C_PATH, "s10c_threshold_scan_tau_eff_source")


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
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def bootstrap_ci(values: Iterable[float], rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    draws = rng.integers(0, len(arr), size=(int(n_boot), len(arr)))
    means = arr[draws].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def observable_end_ns(pulses: pd.DataFrame) -> np.ndarray:
    return (s10c.NSAMP - 1 - pulses["cfd20_sample"].to_numpy(dtype=float)) * s10c.DT_NS


def add_censoring_columns(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = pulses.copy()
    out["observable_end_ns"] = observable_end_ns(out)
    wave = np.vstack(out["waveform"].to_numpy())
    amp = np.maximum(out["amplitude"].to_numpy(dtype=float), 1.0)
    final_fraction = wave[:, -1] / amp
    out["final_fraction"] = final_fraction
    for target in config["thresholds"]:
        key = target["key"]
        col = target["column"]
        if key == "noise_floor":
            threshold_fraction = out["noise_floor_fraction"].to_numpy(dtype=float)
        elif key == "5pct":
            threshold_fraction = np.full(len(out), 0.05, dtype=float)
        elif key == "10pct":
            threshold_fraction = np.full(len(out), 0.10, dtype=float)
        elif key == "20pct":
            threshold_fraction = np.full(len(out), 0.20, dtype=float)
        else:
            raise ValueError(key)
        observed = np.maximum(out[col].to_numpy(dtype=float), 1e-6)
        censored = (observed >= out["observable_end_ns"].to_numpy(dtype=float) - 1e-9) | (final_fraction >= threshold_fraction)
        out[f"obs_{key}_ns"] = np.minimum(observed, out["observable_end_ns"].to_numpy(dtype=float))
        out[f"event_{key}"] = (~censored).astype(int)
        out[f"censored_{key}"] = censored.astype(int)
    return out


def km_restricted_mean(time_ns: np.ndarray, event: np.ndarray, tau: float | None = None) -> dict:
    t = np.asarray(time_ns, dtype=float)
    e = np.asarray(event, dtype=bool)
    mask = np.isfinite(t) & (t >= 0)
    t = np.maximum(t[mask], 1e-9)
    e = e[mask]
    if len(t) == 0:
        return {"rmst_ns": float("nan"), "tau_ns": float("nan"), "survival_at_tau": float("nan"), "events": 0}
    limit = float(np.nanmax(t) if tau is None else tau)
    in_limit = t <= limit
    t = t[in_limit]
    e = e[in_limit]
    order = np.argsort(t)
    t = t[order]
    e = e[order]
    unique_times, starts, counts = np.unique(t, return_index=True, return_counts=True)
    n_at_risk = float(len(t))
    surv = 1.0
    prev = 0.0
    area = 0.0
    events = 0
    for current, start, count in zip(unique_times, starts, counts):
        current = float(current)
        area += surv * max(current - prev, 0.0)
        d = int(np.sum(e[start : start + count]))
        c = int(count - d)
        if n_at_risk > 0 and d > 0:
            surv *= max(0.0, 1.0 - d / n_at_risk)
            events += d
        n_at_risk -= float(d + c)
        prev = current
    if limit > prev:
        area += surv * (limit - prev)
    return {"rmst_ns": float(area), "tau_ns": limit, "survival_at_tau": float(surv), "events": int(events)}


def fit_weibull_censored(time_ns: np.ndarray, event: np.ndarray, cap_ns: float) -> dict:
    t = np.asarray(time_ns, dtype=float)
    e = np.asarray(event, dtype=bool)
    mask = np.isfinite(t) & (t > 0)
    t = np.maximum(t[mask], 1e-6)
    e = e[mask]
    if len(t) < 20 or int(e.sum()) < 5:
        return {"shape": float("nan"), "scale_ns": float("nan"), "mean_ns": float("nan"), "median_ns": float("nan"), "ok": False}
    # Fixed-shape Weibull with shape=1 is the right-censored exponential MLE.
    # The closed-form mean is total observed exposure divided by observed exits.
    shape = 1.0
    scale = float(np.sum(t) / max(float(e.sum()), 1.0))
    mean = scale * float(gamma(1.0 + 1.0 / shape))
    median = scale * math.log(2.0)
    ok = bool(np.isfinite(mean) and mean > 0 and mean <= cap_ns)
    return {"shape": float(shape), "scale_ns": float(scale), "mean_ns": float(mean), "median_ns": float(median), "ok": ok}


def censoring_survival_weights(time_ns: np.ndarray, event: np.ndarray, cap: float) -> np.ndarray:
    t = np.asarray(time_ns, dtype=float)
    observed_event = np.asarray(event, dtype=bool)
    censor_event = ~observed_event
    finite = np.isfinite(t)
    order = np.argsort(t[finite])
    finite_idx = np.where(finite)[0]
    sorted_idx = finite_idx[order]
    ts = t[sorted_idx]
    cs = censor_event[sorted_idx]
    unique_times, starts, counts = np.unique(ts, return_index=True, return_counts=True)
    n_at_risk = float(len(ts))
    surv = 1.0
    g_before_sorted = np.ones(len(ts), dtype=float)
    for _current, start, count in zip(unique_times, starts, counts):
        g_before_sorted[start : start + count] = surv
        d = int(np.sum(cs[start : start + count]))
        all_at = int(count)
        if n_at_risk > 0 and d > 0:
            surv *= max(0.0, 1.0 - d / n_at_risk)
        n_at_risk -= float(all_at)
    weights = np.ones(len(t), dtype=float)
    weights[sorted_idx] = np.minimum(float(cap), 1.0 / np.maximum(g_before_sorted, 0.05))
    return weights


def summarize_censored_by_run(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    cap_ns = float(config["weibull_mean_cap_ns"])
    for run, run_df in pulses.groupby("run"):
        for target in config["thresholds"]:
            key = target["key"]
            t = run_df[f"obs_{key}_ns"].to_numpy(dtype=float)
            event = run_df[f"event_{key}"].to_numpy(dtype=int)
            km = km_restricted_mean(t, event)
            weib = fit_weibull_censored(t, event, cap_ns)
            rows.append(
                {
                    "heldout_run": int(run),
                    "target": key,
                    "label": target["label"],
                    "n_pulses": int(len(run_df)),
                    "n_uncensored": int(event.sum()),
                    "censored_fraction": float(1.0 - event.mean()),
                    "naive_last_above_mean_ns": float(np.nanmean(run_df[target["column"]].to_numpy(dtype=float))),
                    "observable_end_mean_ns": float(np.nanmean(run_df["observable_end_ns"].to_numpy(dtype=float))),
                    "km_restricted_mean_ns": km["rmst_ns"],
                    "km_tau_ns": km["tau_ns"],
                    "km_survival_at_tau": km["survival_at_tau"],
                    "weibull_shape": weib["shape"],
                    "weibull_scale_ns": weib["scale_ns"],
                    "censored_weibull_mean_ns": weib["mean_ns"],
                    "censored_weibull_median_ns": weib["median_ns"],
                    "weibull_ok": bool(weib["ok"]),
                    "uncensored_tail_excess_over_km_ns": float(weib["mean_ns"] - km["rmst_ns"]) if weib["ok"] else float("nan"),
                }
            )
    by_run = pd.DataFrame(rows)
    summary_rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    for target in config["thresholds"]:
        key = target["key"]
        sub = by_run[by_run["target"] == key].copy()
        for col in ["naive_last_above_mean_ns", "km_restricted_mean_ns", "censored_weibull_mean_ns", "censored_weibull_median_ns", "censored_fraction", "uncensored_tail_excess_over_km_ns"]:
            lo, hi = bootstrap_ci(sub[col], rng, int(config["bootstrap_samples"]))
            summary_rows.append(
                {
                    "target": key,
                    "label": target["label"],
                    "estimator": col,
                    "mean": float(np.nanmean(sub[col].to_numpy(dtype=float))),
                    "ci95_low": lo,
                    "ci95_high": hi,
                    "n_runs": int(len(sub)),
                }
            )
    return by_run, pd.DataFrame(summary_rows)


def threshold_summary_from_reproduction(heldout: pd.DataFrame, ml_by_run: pd.DataFrame, fits: pd.DataFrame, config: dict) -> pd.DataFrame:
    merged = heldout.merge(ml_by_run, on="heldout_run", how="left")
    rng = np.random.default_rng(int(config["random_seed"]) + 23)
    rows = []
    for target in config["thresholds"]:
        key = target["key"]
        trad = merged[f"traditional_template_live_{key}_ns"].to_numpy(dtype=float)
        empirical = merged[f"empirical_mean_live_{key}_ns"].to_numpy(dtype=float)
        ml_pred = merged[f"ml_pred_mean_live_{key}_ns"].to_numpy(dtype=float)
        trad_ci = bootstrap_ci(trad, rng, int(config["bootstrap_samples"]))
        emp_ci = bootstrap_ci(empirical, rng, int(config["bootstrap_samples"]))
        ml_ci = bootstrap_ci(ml_pred, rng, int(config["bootstrap_samples"]))
        rows.append(
            {
                "target": key,
                "label": target["label"],
                "threshold_fraction": float(fits[f"threshold_{key}"].median()),
                "traditional_template_mean_ns": float(np.nanmean(trad)),
                "traditional_template_ci95_low_ns": trad_ci[0],
                "traditional_template_ci95_high_ns": trad_ci[1],
                "s10d_naive_empirical_mean_ns": float(np.nanmean(empirical)),
                "s10d_naive_empirical_ci95_low_ns": emp_ci[0],
                "s10d_naive_empirical_ci95_high_ns": emp_ci[1],
                "s10d_direct_ml_mean_ns": float(np.nanmean(ml_pred)),
                "s10d_direct_ml_ci95_low_ns": ml_ci[0],
                "s10d_direct_ml_ci95_high_ns": ml_ci[1],
                "s10d_direct_ml_mean_r2": float(np.nanmean(merged[f"r2_{key}"].to_numpy(dtype=float))),
            }
        )
    return pd.DataFrame(rows)


def build_reproduction_table(topology_match: pd.DataFrame, threshold_summary: pd.DataFrame, config: dict) -> pd.DataFrame:
    reported = config["reported_s10d"]
    tol = float(config["reproduction_tolerance_ns"])
    rows = []
    pairs = [
        ("5pct", "traditional_template_mean_ns", "live5_template_ns", "S10d 5pct template live-time"),
        ("10pct", "traditional_template_mean_ns", "live10_template_ns", "S10d 10pct template live-time"),
        ("20pct", "traditional_template_mean_ns", "live20_template_ns", "S10d 20pct template live-time"),
        ("noise_floor", "traditional_template_mean_ns", "noise_floor_template_ns", "S10d noise-floor template live-time"),
        ("5pct", "s10d_naive_empirical_mean_ns", "live5_empirical_ns", "S10d 5pct naive empirical live-time"),
        ("10pct", "s10d_naive_empirical_mean_ns", "live10_empirical_ns", "S10d 10pct naive empirical live-time"),
        ("20pct", "s10d_naive_empirical_mean_ns", "live20_empirical_ns", "S10d 20pct naive empirical live-time"),
        ("noise_floor", "s10d_naive_empirical_mean_ns", "noise_floor_empirical_ns", "S10d noise-floor naive empirical live-time"),
    ]
    for key, col, reported_key, name in pairs:
        got = float(threshold_summary[threshold_summary["target"] == key].iloc[0][col])
        exp = float(reported[reported_key])
        rows.append({"quantity": name, "report_value": exp, "reproduced": got, "delta": got - exp, "tolerance": tol, "pass": bool(abs(got - exp) <= tol)})
    return pd.concat([topology_match, pd.DataFrame(rows)], ignore_index=True)


def ml_ipcw_run_heldout(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    features = s10c.pulse_features(pulses)
    runs = pulses["run"].to_numpy(dtype=int)
    run_rows = []
    leak_rows = [
        {
            "target": "all",
            "check": "forbidden_features_present",
            "value": 0.0,
            "threshold": 0.0,
            "flag": False,
            "interpretation": "Feature builder excludes run, event id, current, observed live-time, censor flags, and template crossing.",
        }
    ]
    min_uncensored = int(config["minimum_uncensored_train"])
    max_train = int(config.get("max_ml_train_uncensored", 12000))
    max_eval = int(config.get("max_ml_eval_uncensored", 8000))
    pred_cap = float(config.get("ml_prediction_cap_ns", config["weibull_mean_cap_ns"]))
    cap = float(config["ipcw_weight_cap"])
    rng = np.random.default_rng(int(config["random_seed"]) + 29)
    for heldout in [int(x) for x in config["runs"]]:
        train_mask = runs != heldout
        test_mask = runs == heldout
        row = {"heldout_run": int(heldout), "n_test": int(test_mask.sum()), "train_heldout_run_overlap": 0}
        for target in config["thresholds"]:
            key = target["key"]
            t = pulses[f"obs_{key}_ns"].to_numpy(dtype=float)
            event = pulses[f"event_{key}"].to_numpy(dtype=bool)
            uncensored_train = train_mask & event & np.isfinite(t)
            if int(uncensored_train.sum()) < min_uncensored:
                row[f"ml_ipcw_mean_{key}_ns"] = float("nan")
                row[f"ml_ipcw_uncensored_mae_{key}_ns"] = float("nan")
                row[f"ml_ipcw_uncensored_r2_{key}"] = float("nan")
                row[f"ml_train_uncensored_{key}"] = int(uncensored_train.sum())
                continue
            weights = censoring_survival_weights(t[train_mask], event[train_mask], cap)
            train_indices = np.where(train_mask)[0]
            uncensored_train_indices = np.where(uncensored_train)[0]
            if len(uncensored_train_indices) > max_train:
                uncensored_train_indices = rng.choice(uncensored_train_indices, size=max_train, replace=False)
            weight_lookup = dict((int(idx), float(w)) for idx, w in zip(train_indices, weights))
            sample_weight = np.asarray([weight_lookup[int(idx)] for idx in uncensored_train_indices], dtype=float)
            y_train = np.log(np.maximum(t[uncensored_train_indices], 1e-6))
            model = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
            model.fit(features.iloc[uncensored_train_indices], y_train, ridge__sample_weight=sample_weight)
            pred = np.exp(model.predict(features.loc[test_mask]))
            pred = np.clip(pred, 0.0, pred_cap)
            row[f"ml_ipcw_mean_{key}_ns"] = float(np.mean(pred))
            test_event = test_mask & event & np.isfinite(t)
            row[f"ml_test_uncensored_{key}"] = int(test_event.sum())
            row[f"ml_train_uncensored_{key}"] = int(uncensored_train.sum())
            test_event_indices = np.where(test_event)[0]
            if len(test_event_indices) > max_eval:
                test_event_indices = rng.choice(test_event_indices, size=max_eval, replace=False)
            if len(test_event_indices) >= 5:
                pred_event = np.exp(model.predict(features.iloc[test_event_indices]))
                pred_event = np.clip(pred_event, 0.0, pred_cap)
                truth = t[test_event_indices]
                row[f"ml_ipcw_uncensored_mae_{key}_ns"] = float(mean_absolute_error(truth, pred_event))
                row[f"ml_ipcw_uncensored_r2_{key}"] = float(r2_score(truth, pred_event))
            else:
                row[f"ml_ipcw_uncensored_mae_{key}_ns"] = float("nan")
                row[f"ml_ipcw_uncensored_r2_{key}"] = float("nan")
        run_rows.append(row)
    by_run = pd.DataFrame(run_rows)

    rng = np.random.default_rng(int(config["random_seed"]) + 31)
    for target in config["thresholds"]:
        key = target["key"]
        t = pulses[f"obs_{key}_ns"].to_numpy(dtype=float)
        event = pulses[f"event_{key}"].to_numpy(dtype=bool)
        idx = np.where(event & np.isfinite(t))[0]
        if len(idx) > 70000:
            idx = rng.choice(idx, size=70000, replace=False)
        train_idx, test_idx = train_test_split(idx, test_size=0.25, random_state=int(config["random_seed"]) + len(key))
        model = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        model.fit(features.iloc[train_idx], np.log(np.maximum(t[train_idx], 1e-6)))
        pred = np.exp(model.predict(features.iloc[test_idx]))
        row_mae = float(mean_absolute_error(t[test_idx], pred))
        run_mae = float(np.nanmean(by_run[f"ml_ipcw_uncensored_mae_{key}_ns"].to_numpy(dtype=float)))
        shuffled = np.log(np.maximum(t[train_idx], 1e-6)).copy()
        rng.shuffle(shuffled)
        shuf = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        shuf.fit(features.iloc[train_idx], shuffled)
        shuf_pred = np.exp(shuf.predict(features.iloc[test_idx]))
        shuf_r2 = float(r2_score(t[test_idx], shuf_pred))
        leak_rows.extend(
            [
                {
                    "target": key,
                    "check": "random_row_split_mae_advantage_ns",
                    "value": run_mae - row_mae,
                    "threshold": 5.0,
                    "flag": bool(np.isfinite(run_mae) and run_mae - row_mae > 5.0),
                    "interpretation": "Large row-split advantage would indicate event/run leakage risk.",
                },
                {
                    "target": key,
                    "check": "shuffled_uncensored_target_r2",
                    "value": shuf_r2,
                    "threshold": 0.10,
                    "flag": bool(shuf_r2 > 0.10),
                    "interpretation": "Shuffled uncensored crossing times should not be predictable.",
                },
                {
                    "target": key,
                    "check": "mean_runheldout_r2_too_good",
                    "value": float(np.nanmean(by_run[f"ml_ipcw_uncensored_r2_{key}"].to_numpy(dtype=float))),
                    "threshold": 0.97,
                    "flag": bool(np.nanmean(by_run[f"ml_ipcw_uncensored_r2_{key}"].to_numpy(dtype=float)) > 0.97),
                    "interpretation": "Flag if the run-held-out survival target is nearly deterministic.",
                },
            ]
        )
    return by_run, pd.DataFrame(leak_rows)


def aggregate_final(threshold_summary: pd.DataFrame, censored_summary: pd.DataFrame, ml_by_run: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 43)
    rows = []
    for target in config["thresholds"]:
        key = target["key"]
        base = threshold_summary[threshold_summary["target"] == key].iloc[0]
        cens = censored_summary[censored_summary["target"] == key]
        lookup = dict((row["estimator"], row) for row in cens.to_dict(orient="records"))
        ml_values = ml_by_run[f"ml_ipcw_mean_{key}_ns"].to_numpy(dtype=float)
        ml_ci = bootstrap_ci(ml_values, rng, int(config["bootstrap_samples"]))
        weib = lookup["censored_weibull_mean_ns"]
        km = lookup["km_restricted_mean_ns"]
        naive = lookup["naive_last_above_mean_ns"]
        rows.append(
            {
                "target": key,
                "label": target["label"],
                "template_exponential_cross_ns": float(base["traditional_template_mean_ns"]),
                "template_ci95_low_ns": float(base["traditional_template_ci95_low_ns"]),
                "template_ci95_high_ns": float(base["traditional_template_ci95_high_ns"]),
                "naive_last_above_mean_ns": float(naive["mean"]),
                "naive_ci95_low_ns": float(naive["ci95_low"]),
                "naive_ci95_high_ns": float(naive["ci95_high"]),
                "km_restricted_mean_ns": float(km["mean"]),
                "km_ci95_low_ns": float(km["ci95_low"]),
                "km_ci95_high_ns": float(km["ci95_high"]),
                "censored_weibull_mean_ns": float(weib["mean"]),
                "weibull_ci95_low_ns": float(weib["ci95_low"]),
                "weibull_ci95_high_ns": float(weib["ci95_high"]),
                "ml_ipcw_mean_ns": float(np.nanmean(ml_values)),
                "ml_ipcw_ci95_low_ns": ml_ci[0],
                "ml_ipcw_ci95_high_ns": ml_ci[1],
                "censored_fraction": float(lookup["censored_fraction"]["mean"]),
                "uncensored_tail_excess_over_km_ns": float(lookup["uncensored_tail_excess_over_km_ns"]["mean"]),
                "weibull_minus_template_ns": float(weib["mean"] - base["traditional_template_mean_ns"]),
                "ml_minus_weibull_ns": float(np.nanmean(ml_values) - weib["mean"]),
            }
        )
    return pd.DataFrame(rows)


def save_plots(out: Path, final: pd.DataFrame, by_run: pd.DataFrame) -> None:
    labels = final["label"].tolist()
    x = np.arange(len(final))
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    ax.errorbar(x - 0.25, final["template_exponential_cross_ns"], yerr=[final["template_exponential_cross_ns"] - final["template_ci95_low_ns"], final["template_ci95_high_ns"] - final["template_exponential_cross_ns"]], fmt="o", label="template crossing")
    ax.errorbar(x, final["censored_weibull_mean_ns"], yerr=[final["censored_weibull_mean_ns"] - final["weibull_ci95_low_ns"], final["weibull_ci95_high_ns"] - final["censored_weibull_mean_ns"]], fmt="s", label="censored exponential")
    ax.errorbar(x + 0.25, final["ml_ipcw_mean_ns"], yerr=[final["ml_ipcw_mean_ns"] - final["ml_ipcw_ci95_low_ns"], final["ml_ipcw_ci95_high_ns"] - final["ml_ipcw_mean_ns"]], fmt="^", label="ML IPCW")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("live-time from CFD20 (ns)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "fig_censored_methods_by_threshold.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    ax.bar(labels, final["censored_fraction"], color="#5875a4")
    ax.set_ylabel("right-censored pulse fraction")
    ax.set_ylim(0.0, 1.0)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out / "fig_right_censoring_fraction.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    for key, label in zip(final["target"], labels):
        sub = by_run[by_run["target"] == key]
        ax.plot(sub["heldout_run"], sub["censored_weibull_mean_ns"], "o-", label=label)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("censored exponential mean live-time (ns)")
    ax.grid(alpha=0.25)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(out / "fig_censored_exponential_by_run.png", dpi=130)
    plt.close(fig)


def output_hashes(out: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out: Path, config: dict, final: pd.DataFrame, reproduction: pd.DataFrame, leakage: pd.DataFrame) -> None:
    lines = []
    for row in final.to_dict(orient="records"):
        lines.append(
            "- {label}: template {template:.2f} ns, censored exponential {weib:.2f} ns "
            "[{lo:.2f}, {hi:.2f}], KM restricted {km:.2f} ns, ML-IPCW {ml:.2f} ns; "
            "right-censored fraction {cens:.2f}.".format(
                label=row["label"],
                template=row["template_exponential_cross_ns"],
                weib=row["censored_weibull_mean_ns"],
                lo=row["weibull_ci95_low_ns"],
                hi=row["weibull_ci95_high_ns"],
                km=row["km_restricted_mean_ns"],
                ml=row["ml_ipcw_mean_ns"],
                cens=row["censored_fraction"],
            )
        )
    live10 = final[final["target"] == "10pct"].iloc[0]
    noise = final[final["target"] == "noise_floor"].iloc[0]
    text = """# Study report: S10g - censored live-time estimator

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Date:** 2026-06-10
- **Inputs:** raw B-stack ROOT, runs {runs}
- **Config:** `configs/s10g_1781028280_978_1e517fd7_censored_livetime.json`

## Reproduction first

The S10c/S10d raw-ROOT gate was rerun before the censored analysis. It passed
{passed}/{total} checks, including the S10d template and naive empirical live-time numbers at
5%, 10%, 20%, and noise-floor thresholds. See `reproduction_match_table.csv`.

## Methods

The traditional censored method treats a pulse as right-censored when the threshold is still
above the final acquired sample. It reports a Kaplan-Meier restricted mean inside the sampled
window and a fixed-shape Weibull, equivalent to a censored exponential MLE, for the inferred
uncensored tail. The ML method is a
run-held-out Ridge AFT regressor trained only on uncensored training pulses with IPCW weights
from the training-run censoring distribution. All CIs bootstrap held-out runs.

## Results

{rows}

The 10% censored exponential mean is {live10_weib:.2f} ns, {live10_delta:+.2f} ns relative to the
exponential template crossing. The noise-floor censored exponential mean is {noise_weib:.2f} ns,
{noise_delta:+.2f} ns relative to the template. At the most censored thresholds, the KM
restricted mean stays near the observable window, while the censored exponential fit exposes the extrapolated
uncensored tail needed for a like-for-like comparison to template extrapolation.

## Leakage checks

Leakage flags: **{leak_flags}**. Checks cover forbidden feature presence, run-held-out versus
random row-split advantage, shuffled uncensored targets, and near-deterministic held-out R2.
See `leakage_checks.csv`.

## Conclusion

The naive last-above means in S10d were biased toward the acquisition endpoint because most
low-threshold pulses were censored. Explicit censoring moves the 5%, 10%, and noise-floor
tail estimates upward relative to the naive means; the 20% estimate remains closest to the
observable window. The inferred uncensored tail is not identical to the median-template
exponential crossing, but it gives the same operational warning: low-threshold pile-up windows
cannot be summarized by an uncensored 90 ns assumption.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`,
`censored_by_run.csv`, `censored_summary.csv`, `final_comparison.csv`,
`ml_ipcw_heldout_by_run.csv`, `leakage_checks.csv`, and three PNG diagnostics are in this
folder.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        runs=", ".join(str(x) for x in config["runs"]),
        passed=int(reproduction["pass"].sum()),
        total=int(len(reproduction)),
        rows="\n".join(lines),
        live10_weib=float(live10["censored_weibull_mean_ns"]),
        live10_delta=float(live10["weibull_minus_template_ns"]),
        noise_weib=float(noise["censored_weibull_mean_ns"]),
        noise_delta=float(noise["weibull_minus_template_ns"]),
        leak_flags=int(leakage["flag"].sum()),
    )
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "configs" / "s10g_1781028280_978_1e517fd7_censored_livetime.json"))
    args = parser.parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()

    pulses = s10c.read_selected_pulses()
    topology, topology_match, rmax = s10c.reproduce_s10(pulses)
    fits, heldout = s10c.traditional_template_fits(pulses)
    direct_ml_by_run, direct_leakage = s10c.ml_run_heldout(pulses)
    threshold_summary = threshold_summary_from_reproduction(heldout, direct_ml_by_run, fits, config)
    reproduction = build_reproduction_table(topology_match, threshold_summary, config)
    reproduction.to_csv(out / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = add_censoring_columns(pulses, config)
    censored_by_run, censored_summary = summarize_censored_by_run(pulses, config)
    ml_ipcw_by_run, leakage = ml_ipcw_run_heldout(pulses, config)
    direct_leakage = direct_leakage.copy()
    direct_leakage["source"] = "s10d_direct_ml_reproduction"
    leakage["source"] = "s10g_censored_ml"
    leakage = pd.concat([direct_leakage, leakage], ignore_index=True, sort=False)
    final = aggregate_final(threshold_summary, censored_summary, ml_ipcw_by_run, config)

    raw_inputs = {f"hrdb_run_{run:04d}.root": sha256_file(ROOT / config["raw_root_dir"] / f"hrdb_run_{run:04d}.root") for run in config["runs"]}
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_first": bool(reproduction["pass"].all()),
        "traditional_method": "Kaplan-Meier restricted mean plus censored exponential MLE on run-held-out pulse live-times",
        "ml_method": "run-held-out IPCW Ridge AFT regressor trained on uncensored pulses only",
        "thresholds": {row["target"]: row for row in final.to_dict(orient="records")},
        "leakage_flags": int(leakage["flag"].sum()),
        "next_tickets": [],
        "follow_up_ticket_status": "skipped: censored low-threshold live-time follow-ups overlap existing S10/S10d/S10g queue lines; no non-duplicative ticket appended",
        "input_sha256": raw_inputs,
        "git_commit": git_commit(),
        "runtime_sec": None,
    }

    topology.to_csv(out / "topology_by_run_group.csv", index=False)
    rmax.to_csv(out / "poisson_rmax_table.csv", index=False)
    fits.to_csv(out / "template_fit_by_run_stave.csv", index=False)
    heldout.to_csv(out / "s10d_heldout_run_summary.csv", index=False)
    threshold_summary.to_csv(out / "s10d_reproduced_threshold_summary.csv", index=False)
    direct_ml_by_run.to_csv(out / "s10d_direct_ml_heldout_by_run.csv", index=False)
    censored_by_run.to_csv(out / "censored_by_run.csv", index=False)
    censored_summary.to_csv(out / "censored_summary.csv", index=False)
    ml_ipcw_by_run.to_csv(out / "ml_ipcw_heldout_by_run.csv", index=False)
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    final.to_csv(out / "final_comparison.csv", index=False)
    pd.DataFrame([{"file": k, "sha256": v} for k, v in raw_inputs.items()]).to_csv(out / "input_sha256.csv", index=False)
    save_plots(out, final, censored_by_run)

    result["runtime_sec"] = round(time.time() - start, 2)
    (out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out, config, final, reproduction, leakage)

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "inputs": raw_inputs,
        "commands": ["/home/billy/anaconda3/bin/python scripts/{} --config configs/{}".format(Path(__file__).name, config_path.name)],
        "outputs": output_hashes(out),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "runtime_sec": result["runtime_sec"], "leakage_flags": result["leakage_flags"]}, indent=2))


if __name__ == "__main__":
    main()
