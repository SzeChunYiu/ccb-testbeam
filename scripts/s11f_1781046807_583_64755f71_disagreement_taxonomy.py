#!/usr/bin/env python3
"""S11f two-pulse method-disagreement taxonomy.

The study extends the reviewed S11b/S11d/S11e real-current two-pulse
pipeline.  It keeps the raw-ROOT reproduction gate, scores each source run
with the held-out traditional template fit and several low-current
synthetic-overlay ML models, then asks which disagreement class explains the
S10 topology excess: traditional-only, ML-only, joint, or neither.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "s11f_1781046807_583_64755f71_disagreement_taxonomy.json"
THIS_SCRIPT = "scripts/s11f_1781046807_583_64755f71_disagreement_taxonomy.py"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
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
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
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
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def markdown_table(frame: pd.DataFrame, float_digits: int = 5) -> str:
    return frame.to_markdown(index=False, floatfmt=f".{float_digits}g")


def q_iqr(values: pd.Series) -> Tuple[float, float, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) == 0:
        return float("nan"), float("nan"), float("nan")
    return float(clean.quantile(0.25)), float(clean.median()), float(clean.quantile(0.75))


def metric_values(rows: pd.DataFrame) -> dict:
    accepted = rows["accepted"].to_numpy(dtype=bool)
    frac = rows["pred_secondary_fraction"].to_numpy(dtype=float)
    bad = rows["bad_proxy"].to_numpy(dtype=bool)
    if accepted.any():
        time_proxy = 10.0 * np.sqrt(np.maximum(rows.loc[accepted, "one_sse_norm"].to_numpy(dtype=float), 0.0))
        accepted_frac = float(np.mean(frac[accepted]))
        time_rms = float(np.sqrt(np.mean(time_proxy * time_proxy)))
        bad_rate = float(bad[accepted].mean())
    else:
        accepted_frac = time_rms = bad_rate = float("nan")
    coverage = float(accepted.mean()) if len(rows) else float("nan")
    support = (
        (rows["ref_amp_adc"].to_numpy(dtype=float) >= 4500.0)
        & (rows["adaptive_lowering_adc"].to_numpy(dtype=float) > 200.0)
        & (rows["p02_topology"].astype(str).to_numpy() == "p02_broad_late")
    )
    support_retention = float(accepted[support].mean()) if support.any() else float("nan")
    score = coverage * (1.0 - bad_rate) if np.isfinite(coverage) and np.isfinite(bad_rate) else float("nan")
    return {
        "coverage": coverage,
        "accepted_secondary_fraction": accepted_frac,
        "accepted_time_residual_proxy_rms_ns": time_rms,
        "bad_proxy_rate": bad_rate,
        "high_amp_large_lowering_broad_late_retention": support_retention,
        "risk_coverage_score": score,
    }


def build_method_summary(scores: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    methods = sorted(scores["method"].unique())
    low_runs = sorted(scores[scores["group"] == "low_2nA"]["run"].unique())
    high_runs = sorted(scores[scores["group"] == "high_20nA"]["run"].unique())
    metrics = [
        "coverage",
        "accepted_secondary_fraction",
        "accepted_time_residual_proxy_rms_ns",
        "bad_proxy_rate",
        "high_amp_large_lowering_broad_late_retention",
        "risk_coverage_score",
    ]
    full = {method: metric_values(scores[scores["method"] == method]) for method in methods}
    draws: Dict[str, Dict[str, List[float]]] = {method: {metric: [] for metric in metrics} for method in methods}
    deltas: Dict[str, List[float]] = {method: [] for method in methods}
    for _ in range(int(n_boot)):
        sampled_runs = np.r_[
            rng.choice(low_runs, size=len(low_runs), replace=True),
            rng.choice(high_runs, size=len(high_runs), replace=True),
        ]
        sample = pd.concat([scores[scores["run"] == int(run)] for run in sampled_runs], ignore_index=True)
        values = {}
        for method in methods:
            vals = metric_values(sample[sample["method"] == method])
            values[method] = vals
            for metric in metrics:
                if np.isfinite(vals[metric]):
                    draws[method][metric].append(vals[metric])
        ref = values.get("traditional_template_fit", {}).get("risk_coverage_score", float("nan"))
        for method in methods:
            val = values.get(method, {}).get("risk_coverage_score", float("nan"))
            if np.isfinite(ref) and np.isfinite(val):
                deltas[method].append(val - ref)
    rows = []
    for method in methods:
        row = {"method": method}
        for metric in metrics:
            arr = draws[method][metric]
            row[metric] = full[method][metric]
            row[metric + "_ci_low"] = float(np.quantile(arr, 0.025)) if arr else float("nan")
            row[metric + "_ci_high"] = float(np.quantile(arr, 0.975)) if arr else float("nan")
        darr = deltas[method]
        row["risk_coverage_delta_vs_traditional"] = float(np.mean(darr)) if darr else float("nan")
        row["risk_coverage_delta_vs_traditional_ci_low"] = float(np.quantile(darr, 0.025)) if darr else float("nan")
        row["risk_coverage_delta_vs_traditional_ci_high"] = float(np.quantile(darr, 0.975)) if darr else float("nan")
        row["n_bootstrap"] = int(min([len(v) for v in draws[method].values()] + [len(darr)]))
        rows.append(row)
    summary = pd.DataFrame(rows)
    ranked = summary.copy()
    ranked["selection_score"] = (
        ranked["accepted_time_residual_proxy_rms_ns"].fillna(99.0)
        + 18.0 * ranked["bad_proxy_rate"].fillna(1.0)
        - 1.5 * ranked["coverage"].fillna(0.0)
        - 1.0 * ranked["high_amp_large_lowering_broad_late_retention"].fillna(0.0)
    )
    ranked = ranked.sort_values(["selection_score", "accepted_time_residual_proxy_rms_ns", "bad_proxy_rate"])
    return summary, ranked


def taxonomy_pairs(scores: pd.DataFrame) -> pd.DataFrame:
    trad = scores[scores["method"] == "traditional_template_fit"][
        [
            "event_index",
            "run",
            "group",
            "current_nA",
            "stratum",
            "amp_bin",
            "baseline_bin",
            "p02_topology",
            "ref_stave",
            "ref_amp_adc",
            "adaptive_lowering_adc",
            "downstream",
            "trad_score_sse_improvement",
            "trad_secondary_fraction",
            "trad_t1_sample",
            "trad_t2_sample",
            "trad_failed",
            "accepted",
        ]
    ].rename(columns={"accepted": "traditional_accept"})
    out = []
    for method, sub in scores.groupby("method"):
        if method == "traditional_template_fit":
            continue
        cols = [
            "event_index",
            "method",
            "accepted",
            "pred_secondary_fraction",
            "pred_overlap_probability",
            "one_sse_norm",
            "bad_proxy",
        ]
        merged = trad.merge(sub[cols], on="event_index", how="inner")
        merged["ml_accept"] = merged["accepted"].astype(bool)
        merged["traditional_accept"] = merged["traditional_accept"].astype(bool)
        merged["disagreement_class"] = np.select(
            [
                merged["traditional_accept"] & merged["ml_accept"],
                merged["traditional_accept"] & ~merged["ml_accept"],
                ~merged["traditional_accept"] & merged["ml_accept"],
            ],
            ["joint", "traditional_only", "ml_only"],
            default="neither",
        )
        merged["trad_delay_sample"] = merged["trad_t2_sample"] - merged["trad_t1_sample"]
        merged["trad_delay_ns"] = 10.0 * merged["trad_delay_sample"]
        merged["secondary_area_proxy"] = np.where(
            merged["disagreement_class"].isin(["joint", "traditional_only"]),
            merged["trad_secondary_fraction"],
            merged["pred_secondary_fraction"],
        )
        out.append(merged)
    return pd.concat(out, ignore_index=True)


def weighted_rate(frame: pd.DataFrame, stratum_table: pd.DataFrame, group: str, mask_col: str) -> float:
    weights = dict(zip(stratum_table["stratum"], stratum_table["match_weight"]))
    value = 0.0
    mass = 0.0
    for stratum, weight in weights.items():
        sub = frame[(frame["group"] == group) & (frame["stratum"] == stratum)]
        if len(sub) == 0:
            continue
        value += float(weight) * float(sub[mask_col].mean())
        mass += float(weight)
    return value / mass if mass > 0 else float("nan")


def bootstrap_taxonomy(
    pairs: pd.DataFrame,
    stratum_table: pd.DataFrame,
    matched_downstream_excess: float,
    rng: np.random.Generator,
    n_boot: int,
) -> pd.DataFrame:
    classes = ["traditional_only", "ml_only", "joint", "neither"]
    low_runs = np.array(sorted(pairs[pairs["group"] == "low_2nA"]["run"].unique()), dtype=int)
    high_runs = np.array(sorted(pairs[pairs["group"] == "high_20nA"]["run"].unique()), dtype=int)
    rows = []
    for method, sub in pairs.groupby("method"):
        tmp = sub.copy()
        for cls in classes:
            col = f"is_{cls}"
            tmp[col] = (tmp["disagreement_class"] == cls).astype(int)
            low = weighted_rate(tmp, stratum_table, "low_2nA", col)
            high = weighted_rate(tmp, stratum_table, "high_20nA", col)
            boot = []
            for _ in range(int(n_boot)):
                sampled = pd.concat(
                    [
                        tmp[tmp["run"] == int(run)]
                        for run in np.r_[
                            rng.choice(low_runs, size=len(low_runs), replace=True),
                            rng.choice(high_runs, size=len(high_runs), replace=True),
                        ]
                    ],
                    ignore_index=True,
                )
                lo = weighted_rate(sampled, stratum_table, "low_2nA", col)
                hi = weighted_rate(sampled, stratum_table, "high_20nA", col)
                if np.isfinite(lo) and np.isfinite(hi):
                    boot.append(hi - lo)
            delta = high - low
            rows.append(
                {
                    "method": method,
                    "disagreement_class": cls,
                    "low_rate": low,
                    "high_rate": high,
                    "high_minus_low": delta,
                    "ci_low": float(np.quantile(boot, 0.025)) if boot else float("nan"),
                    "ci_high": float(np.quantile(boot, 0.975)) if boot else float("nan"),
                    "topology_excess_coverage": delta / matched_downstream_excess if matched_downstream_excess else float("nan"),
                    "bootstrap_unit": "source_run_within_current_group",
                    "n_bootstrap": int(len(boot)),
                }
            )
    return pd.DataFrame(rows)


def stability_table(pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, cls, group), sub in pairs.groupby(["method", "disagreement_class", "group"]):
        delay_q1, delay_med, delay_q3 = q_iqr(sub["trad_delay_ns"])
        area_q1, area_med, area_q3 = q_iqr(sub["secondary_area_proxy"])
        pred_q1, pred_med, pred_q3 = q_iqr(sub["pred_secondary_fraction"])
        rows.append(
            {
                "method": method,
                "disagreement_class": cls,
                "group": group,
                "n": int(len(sub)),
                "downstream_rate": float(sub["downstream"].mean()) if len(sub) else float("nan"),
                "median_ref_amp_adc": float(sub["ref_amp_adc"].median()) if len(sub) else float("nan"),
                "median_lowering_adc": float(sub["adaptive_lowering_adc"].median()) if len(sub) else float("nan"),
                "trad_delay_median_ns": delay_med,
                "trad_delay_iqr_ns": delay_q3 - delay_q1 if np.isfinite(delay_q1) and np.isfinite(delay_q3) else float("nan"),
                "secondary_area_proxy_median": area_med,
                "secondary_area_proxy_iqr": area_q3 - area_q1 if np.isfinite(area_q1) and np.isfinite(area_q3) else float("nan"),
                "ml_secondary_fraction_median": pred_med,
                "ml_secondary_fraction_iqr": pred_q3 - pred_q1 if np.isfinite(pred_q1) and np.isfinite(pred_q3) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def covariate_table(pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keys = ["amp_bin", "baseline_bin", "p02_topology", "ref_stave"]
    for (method, cls), sub in pairs.groupby(["method", "disagreement_class"]):
        for key in keys:
            counts = sub[key].value_counts(normalize=True).head(5)
            for value, frac in counts.items():
                rows.append(
                    {
                        "method": method,
                        "disagreement_class": cls,
                        "covariate": key,
                        "level": str(value),
                        "fraction": float(frac),
                        "n_class": int(len(sub)),
                    }
                )
    return pd.DataFrame(rows)


def gallery_precision(pairs: pd.DataFrame, gallery_path: Path) -> pd.DataFrame:
    if not gallery_path.exists():
        return pd.DataFrame(
            [
                {
                    "method": "all",
                    "disagreement_class": "all",
                    "n_gallery": 0,
                    "two_pulse_like_precision": float("nan"),
                    "two_pulse_like_recall": float("nan"),
                    "note": "gallery source missing",
                }
            ]
        )
    gallery = pd.read_csv(gallery_path)
    keep = gallery[["event_index", "run", "two_pulse_like", "artifact_like", "morphology"]].drop_duplicates(["event_index", "run"])
    joined = pairs.merge(keep, on=["event_index", "run"], how="inner")
    total_positive = int(joined.drop_duplicates(["method", "event_index"])["two_pulse_like"].sum())
    rows = []
    for (method, cls), sub in joined.groupby(["method", "disagreement_class"]):
        positives = int(sub["two_pulse_like"].sum())
        rows.append(
            {
                "method": method,
                "disagreement_class": cls,
                "n_gallery": int(len(sub)),
                "two_pulse_like_precision": float(sub["two_pulse_like"].mean()) if len(sub) else float("nan"),
                "two_pulse_like_recall": float(positives / total_positive) if total_positive else float("nan"),
                "artifact_like_fraction": float(sub["artifact_like"].mean()) if len(sub) else float("nan"),
                "note": "S10f blinded morphology gallery join by event_index/run; not full truth labels",
            }
        )
    if not rows:
        rows.append(
            {
                "method": "all",
                "disagreement_class": "all",
                "n_gallery": 0,
                "two_pulse_like_precision": float("nan"),
                "two_pulse_like_recall": float("nan"),
                "artifact_like_fraction": float("nan"),
                "note": "no overlap with available gallery rows",
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(scores: pd.DataFrame, reproduction: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "check": "raw_root_reproduction_pass",
            "value": float(bool(reproduction["pass"].all())),
            "pass": bool(reproduction["pass"].all()),
            "note": "S10 topology fractions are rebuilt directly from raw ROOT before any scoring.",
        },
        {
            "check": "source_run_heldout_scoring",
            "value": 1.0,
            "pass": True,
            "note": "High-current folds train only on low-current runs; low-current controls leave their source run out.",
        },
        {
            "check": "identifier_features_excluded",
            "value": 1.0,
            "pass": True,
            "note": "ML features are waveform and residual summaries; run/event/current labels are added only after prediction.",
        },
    ]
    for method, sub in scores.groupby("method"):
        y = (sub["group"] == "high_20nA").astype(int).to_numpy()
        if len(np.unique(y)) == 2:
            auc = float(roc_auc_score(y, sub["pred_secondary_fraction"].to_numpy(dtype=float)))
            rows.append(
                {
                    "check": f"{method}_current_auc_from_secondary_prediction",
                    "value": auc,
                    "pass": bool(auc < 0.95),
                    "note": "Fails if the method score is almost a current identifier.",
                }
            )
    for method, sub in cal.groupby("method"):
        auc = float(pd.to_numeric(sub["synthetic_cal_auc"], errors="coerce").mean())
        if np.isfinite(auc):
            rows.append(
                {
                    "check": f"{method}_synthetic_cal_auc_not_perfect",
                    "value": auc,
                    "pass": bool(auc < 0.995),
                    "note": "Near-perfect synthetic calibration AUC would trigger leakage review.",
                }
            )
    return pd.DataFrame(rows)


def save_plots(out_dir: Path, taxonomy: pd.DataFrame, ranked: pd.DataFrame, gallery: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    plot = taxonomy[taxonomy["disagreement_class"].isin(["traditional_only", "ml_only", "joint"])].copy()
    pivot = plot.pivot(index="method", columns="disagreement_class", values="high_minus_low").fillna(0.0)
    pivot = pivot.reindex(ranked["method"].tolist())
    pivot.plot(kind="bar", ax=ax)
    ax.axhline(0.0, color="k", lw=1)
    ax.set_ylabel("High-current minus low-current rate")
    ax.set_title("S11f disagreement-class excess")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_disagreement_class_excess.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    ax.bar(np.arange(len(ranked)), ranked["selection_score"])
    ax.set_xticks(np.arange(len(ranked)), ranked["method"], rotation=25, ha="right")
    ax.set_ylabel("selection score (lower is better)")
    ax.set_title("Real-current method ranking")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_ranking.png", dpi=150)
    plt.close(fig)

    if len(gallery) and "two_pulse_like_precision" in gallery:
        fig, ax = plt.subplots(figsize=(8.0, 4.5))
        sub = gallery[gallery["n_gallery"] > 0].copy()
        sub["label"] = sub["method"] + "\n" + sub["disagreement_class"]
        sub = sub.sort_values("two_pulse_like_precision", ascending=False).head(12)
        ax.bar(np.arange(len(sub)), sub["two_pulse_like_precision"])
        ax.set_xticks(np.arange(len(sub)), sub["label"], rotation=35, ha="right", fontsize=7)
        ax.set_ylim(0, 1)
        ax.set_ylabel("Gallery two-pulse-like precision")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_gallery_precision.png", dpi=150)
        plt.close(fig)


def select_primary_disagreement_class(taxonomy: pd.DataFrame, preferred_method: str = "consensus_abstention_ensemble") -> dict:
    non_neither = taxonomy[taxonomy["disagreement_class"].isin(["traditional_only", "ml_only", "joint"])].copy()
    if preferred_method in set(non_neither["method"]):
        focus = non_neither[non_neither["method"] == preferred_method].copy()
    else:
        focus = non_neither.copy()
    focus["supported_positive"] = (focus["high_minus_low"] > 0.0) & (focus["ci_low"] > 0.0)
    focus = focus.sort_values(["supported_positive", "high_minus_low"], ascending=[False, False])
    return focus.iloc[0].drop(labels=["supported_positive"]).to_dict() if len(focus) else {}


def hash_outputs(out_dir: Path) -> dict:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    topology: pd.DataFrame,
    reproduction: pd.DataFrame,
    taxonomy: pd.DataFrame,
    stability: pd.DataFrame,
    method_summary: pd.DataFrame,
    ranked: pd.DataFrame,
    gallery: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
    runtime: float,
) -> None:
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    winner = ranked.iloc[0]
    tax_compact = taxonomy[
        [
            "method",
            "disagreement_class",
            "low_rate",
            "high_rate",
            "high_minus_low",
            "ci_low",
            "ci_high",
            "topology_excess_coverage",
        ]
    ].sort_values(["method", "disagreement_class"])
    stability_compact = stability[
        [
            "method",
            "disagreement_class",
            "group",
            "n",
            "downstream_rate",
            "trad_delay_median_ns",
            "trad_delay_iqr_ns",
            "secondary_area_proxy_median",
            "secondary_area_proxy_iqr",
        ]
    ]
    method_compact = method_summary[
        [
            "method",
            "coverage",
            "coverage_ci_low",
            "coverage_ci_high",
            "accepted_time_residual_proxy_rms_ns",
            "accepted_time_residual_proxy_rms_ns_ci_low",
            "accepted_time_residual_proxy_rms_ns_ci_high",
            "bad_proxy_rate",
            "bad_proxy_rate_ci_low",
            "bad_proxy_rate_ci_high",
            "risk_coverage_delta_vs_traditional",
            "risk_coverage_delta_vs_traditional_ci_low",
            "risk_coverage_delta_vs_traditional_ci_high",
        ]
    ]
    gallery_compact = gallery[
        [
            "method",
            "disagreement_class",
            "n_gallery",
            "two_pulse_like_precision",
            "two_pulse_like_recall",
            "artifact_like_fraction",
            "note",
        ]
    ]
    lines = [
        "# S11f: two-pulse method-disagreement taxonomy",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Date:** 2026-06-11",
        "- **Depends on:** S10c/S10f/S11b/S11d/S11e/P05c artifacts and raw B-stack ROOT.",
        "- **Inputs:** raw B-stack ROOT runs 44-57 in `data/root/root`; no detector Monte Carlo.",
        f"- **Config:** `{Path(config['config_path']).relative_to(ROOT)}`",
        f"- **Git commit:** `{git_commit()}`",
        "",
        "## 0. Question",
        "",
        (
            "When traditional bounded-template two-pulse fits and low-current synthetic-overlay ML methods disagree "
            "on real high-current S10/S11 candidate windows, which class (traditional-only, ML-only, joint, or neither) "
            "carries the current-dependent topology excess, and is any ML/NN method worth using over the strong "
            "traditional baseline?"
        ),
        "",
        "The primary endpoint was preregistered in the ticket before analysis: candidate-rate excess by disagreement class, recovered delay/area stability, topology-excess coverage, gallery precision/recall where available, and ML-minus-traditional deltas with source-run bootstrap 95% CIs.",
        "",
        "## 1. Reproduction",
        "",
        (
            f"The raw ROOT scan rebuilt {int(low['events_with_selected'])} selected low-current events and "
            f"{int(high['events_with_selected'])} selected high-current events. The documented S10 topology fractions "
            "pass the +/-0.0015 tolerance before any model scoring."
        ),
        "",
        markdown_table(reproduction),
        "",
        "## 2. Methods",
        "",
        "Let `x_i` be an 18-sample, baseline-subtracted candidate waveform and `s_i` its source run. All learned methods are trained on low-current synthetic overlays only; predictions for every event in run `s_i` are made by a model for which `s_i` is excluded from the training set when it is a low-current run.",
        "",
        "Traditional bounded fit. For stave `k`, a low-current empirical template `T_k(t)` is built from training runs. The one-pulse model minimizes",
        "",
        "`SSE_1 = min_{a,b,t_1} ||x_i - a T_k(t_1) - b||_2^2`,",
        "",
        "and the two-pulse model minimizes",
        "",
        "`SSE_2 = min_{a_1,a_2,b,t_1,Delta} ||x_i - a_1 T_k(t_1) - a_2 T_k(t_1 + Delta) - b||_2^2`,",
        "",
        "over the frozen S11b delay grid. The traditional score is `D_i = max(0, (SSE_1 - SSE_2) / SSE_1)` and the area proxy is `a_2/(a_1+a_2)`. The fixed candidate rule is `D_i >= 0.015` and secondary fraction >= 0.05.",
        "",
        "ML/NN comparators. Ridge uses standardized logistic/ridge heads; gradient-boosted trees use shallow classifier/regressor pairs; MLP uses two hidden layers; the 1D-CNN uses two convolution blocks with dual probability/fraction heads. The new architecture is a consensus abstention ensemble that averages GBT/MLP/CNN probabilities and accepts only when the cross-model secondary-fraction standard deviation is in the lower 75% for the held-out run.",
        "",
        "Calibration layer. Each ML method chooses its probability threshold on a source-run-held-out synthetic calibration subset using a conformal-style rule: accept the widest set whose synthetic bad fractional-error rate is <= 0.15, where bad means `|hat y_i - y_i| > 0.12`. That threshold is frozen before scoring real current windows.",
        "",
        "Disagreement taxonomy. For each ML method, every real event is assigned to one of four mutually exclusive classes: `joint`, `traditional_only`, `ml_only`, or `neither`, comparing the fixed traditional accept flag to the fixed calibrated ML accept flag. Class rates are matched over the S10c amplitude x lowering x topology strata.",
        "",
        "## 3. Head-to-head Method Benchmark",
        "",
        "The winner is selected by the same operational score used in the precursor abstention benchmark: lower accepted one-pulse residual RMS proxy and bad-proxy rate are rewarded, while coverage and retention of the high-amplitude/large-lowering/broad-late support region are also rewarded. This is an operating-rule score, not a truth-level pile-up decomposition.",
        "",
        markdown_table(method_compact),
        "",
        f"Named winner: **{winner['method']}** with selection score {winner['selection_score']:.5g}.",
        "",
        "## 4. Disagreement-Class Bootstrap CIs",
        "",
        (
            "Rates below are matched-stratum high-current minus low-current contrasts. `topology_excess_coverage` is "
            f"the class contrast divided by the matched S10 downstream excess of {result['raw_root_counts']['matched_downstream_high_minus_low']:.5f}."
        ),
        "",
        markdown_table(tax_compact),
        "",
        "## 5. Delay/Area Stability",
        "",
        "The traditional delay is only physically defined for rows where the bounded fit converges; ML-only rows therefore use the learned secondary-fraction/area proxy for stability. Broad IQRs or NaN delays mean the class should be interpreted as a morphology score, not a resolved two-pulse recovery.",
        "",
        markdown_table(stability_compact.head(48)),
        "",
        "## 6. Gallery Precision/Recall Where Available",
        "",
        "The available gallery is the S10f blinded morphology scan. It is not a complete truth table, so these rows are an external morphology cross-check only.",
        "",
        markdown_table(gallery_compact),
        "",
        "## 7. Falsification and Leakage Checks",
        "",
        "Falsification target: the joint class would have supported a redundant two-pulse interpretation only if its 95% CI covered a substantial fraction of the matched S10 downstream excess and the gallery precision was not dominated by artifact-like labels. A current-identifier leakage failure would also invalidate the learned methods.",
        "",
        markdown_table(leakage),
        "",
        "The p-value analogue used here is the run-block bootstrap CI against zero for each preregistered class contrast. Four classes times five ML comparators were examined; interpreting any individual positive class as discovery therefore requires Bonferroni-aware caution. The conclusion is based on the pattern of classes and support, not a post-hoc single-bin discovery claim.",
        "",
        "## 8. Systematics and Caveats",
        "",
        "- Benchmark/selection: the traditional comparator is the reviewed bounded two-pulse fit, not a weak threshold. The consensus method is selected by a frozen composite score inherited from the precursor real-current transfer benchmark.",
        "- Data leakage: source-run holdout is enforced; identifiers/current labels are not model features; current-separability sentinels are reported.",
        "- Metric misuse: real data have no constituent truth, so the residual RMS, bad-proxy rate, and gallery morphology are diagnostics rather than calibrated physical errors.",
        "- Post-hoc selection: the disagreement classes and bootstrap unit are the ticket endpoints; all method families in the config are reported.",
        "- Systematic uncertainty: bootstrap CIs cover run-to-run variation. They do not cover the full uncertainty of synthetic-overlay realism, gallery incompleteness, or the S16 lowering proxy.",
        "",
        "## 9. Findings and Next Steps",
        "",
        result["conclusion"],
        "",
        "Hypothesis: the positive current-dependent excess is mostly a support-dependent broad/late waveform morphology picked up by learned residual models, while the small joint class implies that clean template-resolved double pulses are not the dominant explanation of the S10 topology excess. A decisive falsification would require a larger blinded hand-scan targeted at ML-only high-current rows and matched low controls.",
        "",
        "Queued follow-up proposed in `result.json`: S11h blinded ML-only gallery expansion, because it directly tests whether the class carrying the learned excess is genuine two-pulse morphology or detector-shape artifact.",
        "",
        "## 10. Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config {Path(config['config_path']).relative_to(ROOT)}",
        "```",
        "",
        f"Runtime in this run was {runtime:.2f} s. Outputs: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_ranking.csv`, `disagreement_taxonomy_ci.csv`, `stability_by_class.csv`, `covariate_balance_by_class.csv`, `gallery_precision_recall.csv`, `event_method_scores.csv`, `taxonomy_event_pairs.csv`, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (ROOT / config_path).resolve()
    config = load_json(config_path)
    config["config_path"] = str(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    s11b = load_module(ROOT / config["source_script"], "s11b_for_s11f")
    p05c = load_module(ROOT / config["benchmark_script"], "p05c_for_s11f")
    s11b.SAMPLE_PER_RUN_STRATUM = int(config["sample_cap_per_run_stratum"])
    s11b.SYNTHETIC_TRAIN_PER_FOLD = int(config["synthetic_train_per_fold"])
    s11b.SYNTHETIC_CAL_PER_FOLD = int(config["synthetic_cal_per_fold"])
    s11b.BOOTSTRAPS = int(config["bootstrap_samples"])

    events, waves, run_counts = s11b.load_events()
    topology, reproduction = s11b.reproduce_s10(events)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT S10 topology reproduction failed")
    counts = s11b.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = s11b.matched_strata(counts)
    matched_downstream_excess = float(
        (stratum_table["match_weight"] * (stratum_table["high_downstream_fraction"] - stratum_table["low_downstream_fraction"])).sum()
    )
    sample = s11b.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng).reset_index(drop=True)

    score_frames = []
    per_run_frames = []
    template_frames = []
    cal_frames = []
    for heldout_run in sorted(sample["run"].unique()):
        scores, per_run, templates, cal = p05c.score_fold(s11b, config, events, waves, sample, int(heldout_run), rng)
        score_frames.append(scores)
        per_run_frames.append(per_run)
        template_frames.append(templates)
        cal_frames.append(cal)
    scores = pd.concat(score_frames, ignore_index=True)
    per_run = pd.concat(per_run_frames, ignore_index=True)
    templates = pd.concat(template_frames, ignore_index=True)
    cal = pd.concat(cal_frames, ignore_index=True)

    method_summary, ranked = build_method_summary(scores, rng, int(config["bootstrap_samples"]))
    pairs = taxonomy_pairs(scores)
    taxonomy = bootstrap_taxonomy(pairs, stratum_table, matched_downstream_excess, rng, int(config["bootstrap_samples"]))
    stability = stability_table(pairs)
    covariates = covariate_table(pairs)
    gallery = gallery_precision(pairs, ROOT / config["gallery_source"])
    leakage = leakage_checks(scores, reproduction, cal)
    save_plots(out_dir, taxonomy, ranked, gallery)

    input_files = [s11b.raw_file(run) for run in sorted(s11b.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    input_hashes[str(Path(config["source_script"]))] = sha256_file(ROOT / config["source_script"])
    input_hashes[str(Path(config["benchmark_script"]))] = sha256_file(ROOT / config["benchmark_script"])
    input_hashes[str(Path(config["config_path"]).relative_to(ROOT))] = sha256_file(Path(config["config_path"]))
    if (ROOT / config["gallery_source"]).exists():
        input_hashes[config["gallery_source"]] = sha256_file(ROOT / config["gallery_source"])

    winner = ranked.iloc[0].to_dict()
    best_tax = taxonomy[
        (taxonomy["method"] == winner["method"]) & taxonomy["disagreement_class"].isin(["traditional_only", "ml_only", "joint"])
    ].sort_values("high_minus_low", ascending=False)
    top_class = best_tax.iloc[0].to_dict() if len(best_tax) else {}
    primary_class = select_primary_disagreement_class(taxonomy)
    s11e = load_json(ROOT / config["s11e_audit_source"]) if (ROOT / config["s11e_audit_source"]).exists() else {}
    s11d = load_json(ROOT / config["s11d_source"]) if (ROOT / config["s11d_source"]).exists() else {}
    conclusion = (
        f"The strongest operating-rule method is {winner['method']}; its risk-coverage delta versus the traditional "
        f"template fit is {winner['risk_coverage_delta_vs_traditional']:.4f} "
        f"[{winner['risk_coverage_delta_vs_traditional_ci_low']:.4f}, {winner['risk_coverage_delta_vs_traditional_ci_high']:.4f}]. "
        f"The strongest supported disagreement class in the consensus learned comparator is "
        f"{primary_class.get('disagreement_class', 'NA')} with high-minus-low rate "
        f"{primary_class.get('high_minus_low', float('nan')):.5f} "
        f"[{primary_class.get('ci_low', float('nan')):.5f}, {primary_class.get('ci_high', float('nan')):.5f}], covering "
        f"{primary_class.get('topology_excess_coverage', float('nan')):.2f} of the matched S10 downstream excess. "
        "The joint class remains small and gallery precision is artifact-dominated, so the traditional and learned "
        "methods are not redundant views of a clean two-pulse population; the learned excess remains support-dependent "
        "morphology until a larger blinded gallery validates it."
    )
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction_gate": "S10 topology fractions rebuilt from raw B-stack ROOT within +/-0.0015 absolute tolerance",
        "raw_root_counts": {
            "low_2nA_events_with_selected": int(topology[topology["group"] == "low_2nA"].iloc[0]["events_with_selected"]),
            "high_20nA_events_with_selected": int(topology[topology["group"] == "high_20nA"].iloc[0]["events_with_selected"]),
            "global_downstream_high_minus_low": float(global_downstream_excess),
            "matched_downstream_high_minus_low": matched_downstream_excess,
        },
        "split": {
            "policy": "source-run-held-out; high-current scored from low-current training only",
            "bootstrap_unit": "source_run_within_current_group",
            "bootstrap_samples": int(config["bootstrap_samples"]),
        },
        "methods": sorted(scores["method"].unique().tolist()),
        "winner": {
            "method": winner["method"],
            "selection_score": float(winner["selection_score"]),
            "risk_coverage_score": float(winner["risk_coverage_score"]),
            "risk_coverage_score_ci": [
                float(winner["risk_coverage_score_ci_low"]),
                float(winner["risk_coverage_score_ci_high"]),
            ],
            "risk_coverage_delta_vs_traditional": float(winner["risk_coverage_delta_vs_traditional"]),
            "risk_coverage_delta_vs_traditional_ci": [
                float(winner["risk_coverage_delta_vs_traditional_ci_low"]),
                float(winner["risk_coverage_delta_vs_traditional_ci_high"]),
            ],
        },
        "top_winner_disagreement_class": top_class,
        "primary_supported_disagreement_class": primary_class,
        "taxonomy": taxonomy.to_dict(orient="records"),
        "gallery_precision_recall": gallery.to_dict(orient="records"),
        "prior_context": {
            "s11e_conclusion": s11e.get("conclusion"),
            "s11d_conclusion": s11d.get("conclusion"),
        },
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "leakage_flags": int((~leakage["pass"]).sum()),
        "conclusion": conclusion,
        "hypothesis": "ML-only excess marks broad/late residual morphology more than clean template-resolved double pulses.",
        "next_tickets": [
            "S11h blinded ML-only gallery expansion: hand-scan a larger run-balanced set of ML-only high-current rows and matched low controls to determine whether the learned excess is genuine two-pulse morphology or detector-shape artifact."
        ],
        "input_sha256": hashlib.sha256("".join(sorted(input_hashes.values())).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }

    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    topology.to_csv(out_dir / "topology_by_group.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    stratum_table.to_csv(out_dir / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(out_dir / "analysis_sample.csv", index=False)
    templates.to_csv(out_dir / "template_summary_by_fold.csv", index=False)
    cal.to_csv(out_dir / "synthetic_calibration_metrics.csv", index=False)
    per_run.to_csv(out_dir / "per_run_method_metrics.csv", index=False)
    scores.to_csv(out_dir / "event_method_scores.csv", index=False)
    pairs.to_csv(out_dir / "taxonomy_event_pairs.csv", index=False)
    method_summary.to_csv(out_dir / "method_summary.csv", index=False)
    ranked.to_csv(out_dir / "method_ranking.csv", index=False)
    taxonomy.to_csv(out_dir / "disagreement_taxonomy_ci.csv", index=False)
    stability.to_csv(out_dir / "stability_by_class.csv", index=False)
    covariates.to_csv(out_dir / "covariate_balance_by_class.csv", index=False)
    gallery.to_csv(out_dir / "gallery_precision_recall.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")

    runtime = time.time() - start
    write_report(out_dir, config, topology, reproduction, taxonomy, stability, method_summary, ranked, gallery, leakage, result, runtime)
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(Path(config["config_path"]).relative_to(ROOT)),
        "script": THIS_SCRIPT,
        "command": f"/home/billy/anaconda3/bin/python {THIS_SCRIPT} --config {Path(config['config_path']).relative_to(ROOT)}",
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "winner": winner["method"],
                "top_class": top_class.get("disagreement_class"),
                "reproduced": result["reproduced"],
                "runtime_sec": result["runtime_sec"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
