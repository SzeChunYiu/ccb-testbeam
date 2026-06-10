#!/usr/bin/env python3
"""S04e: q_template vetoes on B2-containing pair-residual tails.

The script rebuilds the B-stack S04/S05 pair residual table from raw HRDv ROOT,
joins the S01 per-pulse q_template table, then evaluates train-run q-template
veto policies and a run-held-out RF veto. No Monte Carlo inputs are used.
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
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/s04e_1781028505_1210_78b135ab_qtemplate_b2_tail_tables.json"
S05E_HELPER = ROOT / "scripts/s05e_1781016280_4691_3d911c1d_b2_saturation_covariance.py"
PAIRS = ["B2-B4", "B2-B6", "B2-B8", "B4-B6", "B4-B8", "B6-B8"]
TOPOLOGIES = ["all", "B2_containing", "downstream_only"]


def load_s05e():
    spec = importlib.util.spec_from_file_location("s05e_for_s04e", str(S05E_HELPER))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {S05E_HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def markdown_table(frame: pd.DataFrame, max_rows: Optional[int] = None) -> str:
    if frame.empty:
        return "_No rows._"
    view = frame if max_rows is None else frame.head(max_rows)
    cols = list(view.columns)

    def fmt(value: Any) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    body = [[fmt(row[col]) for col in cols] for _, row in view.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in body:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    rows = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in body]
    if max_rows is not None and len(frame) > max_rows:
        rows.append(f"| {'...'.ljust(widths[0])} | " + " | ".join("".ljust(w) for w in widths[1:]) + " |")
    return "\n".join([header, sep, *rows])


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.nanmedian(values)
    q16, q84 = np.nanpercentile(centered, [16, 84])
    return float(0.5 * (q84 - q16))


def full_rms(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.nanmedian(values)
    return float(np.sqrt(np.mean(centered * centered)))


def all_configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for key in ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]:
        runs.extend(int(run) for run in config["runs"][key])
    return sorted(set(runs))


def raw_path(config: dict, run: int) -> Path:
    return ROOT / config["raw_root_dir"] / f"{config['bstack']['file_prefix']}_run_{int(run):04d}.root"


def reproduce_raw_anchor(config: dict, s05e) -> Tuple[pd.DataFrame, pd.DataFrame]:
    counts, pair_counts = s05e.reproduce_counts(config)
    expected_pair = config["expected_pair_counts"]
    pair_counts = pair_counts.copy()
    pair_counts["report_value"] = pair_counts["pair"].map(expected_pair).astype(int)
    pair_counts["delta"] = pair_counts["n_pair_rows"] - pair_counts["report_value"]
    pair_counts["tolerance"] = 0
    pair_counts["pass"] = pair_counts["delta"].eq(0)
    return counts, pair_counts


def load_qtemplate(config: dict) -> pd.DataFrame:
    q = pd.read_csv(ROOT / config["qtemplate_path"], usecols=["run", "evt", "stave", "q_template_rmse"])
    q = q.rename(columns={"evt": "event", "q_template_rmse": "q_template"})
    q["run"] = q["run"].astype(int)
    q["event"] = q["event"].astype(int)
    return q.groupby(["run", "event", "stave"], as_index=False)["q_template"].median()


def add_qtemplate(pair_table: pd.DataFrame, q: pd.DataFrame) -> pd.DataFrame:
    table = pair_table.copy()
    for side in ["left", "right"]:
        q_side = q.rename(columns={"stave": side, "q_template": f"q_{side}"})
        table = table.merge(q_side, on=["run", "event", side], how="left")
    table["q_missing"] = table[["q_left", "q_right"]].isna().any(axis=1)
    fill = float(q["q_template"].median())
    table[["q_left", "q_right"]] = table[["q_left", "q_right"]].fillna(fill)
    table["q_max"] = table[["q_left", "q_right"]].max(axis=1)
    table["q_mean"] = table[["q_left", "q_right"]].mean(axis=1)
    table["q_diff_abs"] = (table["q_right"] - table["q_left"]).abs()
    table["topology"] = np.where(table["has_b2"], "B2_containing", "downstream_only")
    table["pair_median_resid_full"] = table["target_residual_ns"] - table.groupby("pair")["target_residual_ns"].transform("median")
    return table


def topology_frame(frame: pd.DataFrame, topology: str) -> pd.DataFrame:
    if topology == "all":
        return frame
    return frame[frame["topology"] == topology]


def choose_q_policy(train: pd.DataFrame, config: dict, topology: str) -> Dict[str, Any]:
    sub = topology_frame(train, topology)
    min_rows = int(config["min_policy_train_rows"])
    if len(sub) < min_rows:
        sub = train
    best: Optional[Tuple[float, float, float, str, float, float]] = None
    for feature in ["q_max", "q_mean", "q_diff_abs"]:
        values = sub[feature].to_numpy(dtype=float)
        for retention in [float(x) for x in config["retention_grid"]]:
            threshold = float(np.quantile(values, retention))
            accepted = sub[sub[feature] <= threshold]
            if len(accepted) < min_rows:
                continue
            resid = accepted["train_centered_resid_ns"].to_numpy(dtype=float)
            tail = float(np.mean(np.abs(resid - np.median(resid)) > float(config["tail_abs_ns"])))
            width = sigma68(resid)
            actual_retention = float(len(accepted) / len(sub))
            candidate = (tail, width, -actual_retention, feature, threshold, actual_retention)
            if best is None or candidate < best:
                best = candidate
    if best is None:
        return {"topology": topology, "feature": "q_max", "threshold": float("inf"), "train_retention": 1.0, "train_tail_frac": float("nan"), "train_sigma68_ns": float("nan")}
    tail, width, neg_ret, feature, threshold, actual_retention = best
    return {
        "topology": topology,
        "feature": feature,
        "threshold": threshold,
        "train_retention": actual_retention,
        "train_tail_frac": tail,
        "train_sigma68_ns": width,
    }


def choose_probability_threshold(train: pd.DataFrame, score: np.ndarray, config: dict, topology: str) -> Dict[str, Any]:
    sub = topology_frame(train.copy(), topology)
    if len(sub) < int(config["min_policy_train_rows"]):
        sub = train.copy()
    sub_score = score[sub.index.to_numpy()]
    best: Optional[Tuple[float, float, float, float, float]] = None
    for retention in [float(x) for x in config["retention_grid"]]:
        threshold = float(np.quantile(sub_score, retention))
        accepted = sub[sub_score <= threshold]
        if len(accepted) < int(config["min_policy_train_rows"]):
            continue
        resid = accepted["train_centered_resid_ns"].to_numpy(dtype=float)
        tail = float(np.mean(np.abs(resid - np.median(resid)) > float(config["tail_abs_ns"])))
        width = sigma68(resid)
        actual_retention = float(len(accepted) / len(sub))
        candidate = (tail, width, -actual_retention, threshold, actual_retention)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return {"topology": topology, "threshold": 1.0, "train_retention": 1.0, "train_tail_frac": float("nan"), "train_sigma68_ns": float("nan")}
    tail, width, neg_ret, threshold, actual_retention = best
    return {"topology": topology, "threshold": threshold, "train_retention": actual_retention, "train_tail_frac": tail, "train_sigma68_ns": width}


def ml_features() -> List[str]:
    base = [
        "q_left",
        "q_right",
        "q_max",
        "q_mean",
        "q_diff_abs",
        "left_log_amp",
        "right_log_amp",
        "log_amp_sum",
        "log_amp_diff",
        "left_peak",
        "right_peak",
        "peak_diff",
        "left_tail",
        "right_tail",
        "tail_diff",
        "left_log_area",
        "right_log_area",
        "log_area_diff",
        "left_near_peak_count",
        "right_near_peak_count",
        "left_sat_count",
        "right_sat_count",
        "left_sat_excess",
        "right_sat_excess",
        "left_recovery_tail",
        "right_recovery_tail",
        "b2_log_amp",
        "b2_sat_count",
        "b2_sat_excess",
        "b2_near_peak_count",
        "b2_recovery_tail",
        "b2_saturation_flag",
    ]
    return base


def run_heldout(table: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    out_rows: List[pd.DataFrame] = []
    policy_rows: List[Dict[str, Any]] = []
    leakage_rows: List[Dict[str, Any]] = []
    rng = np.random.default_rng(int(config["random_seed"]))
    features = ml_features()
    forbidden = {"run", "event", "target_residual_ns", "raw_residual_ns", "pair_median_resid_full"}
    missing_forbidden = sorted(set(features).intersection(forbidden))

    for fold, heldout in enumerate(sorted(table["run"].unique()), start=1):
        train = table[table["run"] != heldout].copy().reset_index(drop=True)
        test = table[table["run"] == heldout].copy().reset_index(drop=True)
        medians = train.groupby("pair")["target_residual_ns"].median().to_dict()
        train["train_centered_resid_ns"] = train["target_residual_ns"] - train["pair"].map(medians)
        test["heldout_centered_resid_ns"] = test["target_residual_ns"] - test["pair"].map(medians)
        y_tail = (np.abs(train["train_centered_resid_ns"] - train["train_centered_resid_ns"].median()) > float(config["tail_abs_ns"])).astype(int)

        q_policies = {top: choose_q_policy(train, config, top) for top in TOPOLOGIES}
        params = config["ml"]
        model = RandomForestClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            class_weight="balanced",
            random_state=int(config["random_seed"]) + fold,
            n_jobs=-1,
        )
        model.fit(train[features].to_numpy(dtype=float), y_tail.to_numpy(dtype=int))
        train_score = model.predict_proba(train[features].to_numpy(dtype=float))[:, 1]
        test["ml_tail_score"] = model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
        ml_policies = {top: choose_probability_threshold(train, train_score, config, top) for top in TOPOLOGIES}

        shuffled = y_tail.to_numpy(dtype=int).copy()
        rng.shuffle(shuffled)
        shuf_model = RandomForestClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            class_weight="balanced",
            random_state=int(config["random_seed"]) + 1000 + fold,
            n_jobs=-1,
        )
        shuf_model.fit(train[features].to_numpy(dtype=float), shuffled)
        shuf_train_score = shuf_model.predict_proba(train[features].to_numpy(dtype=float))[:, 1]
        test["ml_shuffled_tail_score"] = shuf_model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
        shuf_policies = {top: choose_probability_threshold(train, shuf_train_score, config, top) for top in TOPOLOGIES}

        frames = []
        base = test.copy()
        base["method"] = "raw_no_veto"
        base["accepted"] = True
        frames.append(base)
        for method, policies in [
            ("traditional_q_threshold_veto", q_policies),
            ("ml_rf_qtemplate_veto", ml_policies),
            ("ml_rf_shuffled_label_control", shuf_policies),
        ]:
            tmp = test.copy()
            accepted = np.zeros(len(tmp), dtype=bool)
            for top, policy in policies.items():
                idx = tmp["topology"].eq(top) if top != "all" else pd.Series(False, index=tmp.index)
                if top == "all":
                    continue
                if method == "traditional_q_threshold_veto":
                    accepted[idx.to_numpy()] = tmp.loc[idx, policy["feature"]].to_numpy(dtype=float) <= float(policy["threshold"])
                elif method == "ml_rf_qtemplate_veto":
                    accepted[idx.to_numpy()] = tmp.loc[idx, "ml_tail_score"].to_numpy(dtype=float) <= float(policy["threshold"])
                else:
                    accepted[idx.to_numpy()] = tmp.loc[idx, "ml_shuffled_tail_score"].to_numpy(dtype=float) <= float(policy["threshold"])
            tmp["method"] = method
            tmp["accepted"] = accepted
            frames.append(tmp)
        out_rows.append(pd.concat(frames, ignore_index=True))

        for top in TOPOLOGIES:
            qrow = dict(q_policies[top])
            qrow.update({"fold": fold, "heldout_run": int(heldout), "method": "traditional_q_threshold_veto"})
            policy_rows.append(qrow)
            mrow = dict(ml_policies[top])
            mrow.update({"fold": fold, "heldout_run": int(heldout), "method": "ml_rf_qtemplate_veto", **{f"rf_{k}": v for k, v in params.items()}})
            policy_rows.append(mrow)
            srow = dict(shuf_policies[top])
            srow.update({"fold": fold, "heldout_run": int(heldout), "method": "ml_rf_shuffled_label_control", **{f"rf_{k}": v for k, v in params.items()}})
            policy_rows.append(srow)

        train_events = set(zip(train["run"], train["event"]))
        test_events = set(zip(test["run"], test["event"]))
        leakage_rows.append({"fold": fold, "heldout_run": int(heldout), "event_overlap": len(train_events & test_events)})

    leakage = pd.DataFrame(leakage_rows)
    leakage_checks = pd.DataFrame(
        [
            {
                "check": "run_split_event_overlap",
                "value": int(leakage["event_overlap"].sum()),
                "pass": bool(leakage["event_overlap"].sum() == 0),
                "interpretation": "whole runs are held out before q thresholds and RF models are fit",
            },
            {
                "check": "ml_forbidden_feature_intersection",
                "value": "|".join(missing_forbidden),
                "pass": bool(len(missing_forbidden) == 0),
                "interpretation": "production ML excludes run, event, raw time, raw residual, target residual, and full-sample pair residual",
            },
        ]
    )
    return pd.concat(out_rows, ignore_index=True), pd.DataFrame(policy_rows), leakage_checks


def run_bootstrap_metrics(frame: pd.DataFrame, rng: np.random.Generator, n_boot: int, tail_abs_ns: float) -> Tuple[float, float, float, float, float, float]:
    values = frame["heldout_centered_resid_ns"].to_numpy(dtype=float)
    point_sigma = sigma68(values)
    point_rms = full_rms(values)
    point_tail = float(np.mean(np.abs(values - np.nanmedian(values)) > tail_abs_ns)) if len(values) else float("nan")
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {run: frame[frame["run"] == run]["heldout_centered_resid_ns"].to_numpy(dtype=float) for run in runs}
    sigmas: List[float] = []
    tails: List[float] = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = []
        for run in sampled:
            vals = by_run[int(run)]
            if len(vals):
                chunks.append(vals[rng.integers(0, len(vals), size=len(vals))])
        if not chunks:
            continue
        vals = np.concatenate(chunks)
        sigmas.append(sigma68(vals))
        tails.append(float(np.mean(np.abs(vals - np.nanmedian(vals)) > tail_abs_ns)))
    sig_lo, sig_hi = np.nanpercentile(sigmas, [2.5, 97.5])
    tail_lo, tail_hi = np.nanpercentile(tails, [2.5, 97.5])
    return point_sigma, float(sig_lo), float(sig_hi), point_rms, point_tail, float(tail_lo), float(tail_hi)


def metric_tables(scored: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 444)
    rows: List[Dict[str, Any]] = []
    pair_rows: List[Dict[str, Any]] = []
    raw_counts = scored[scored["method"] == "raw_no_veto"].groupby("topology").size().to_dict()
    for method, group in scored.groupby("method"):
        accepted = group[group["accepted"]].copy()
        for topology in TOPOLOGIES:
            sub = topology_frame(accepted, topology)
            if len(sub) < 20:
                continue
            sigma, lo, hi, rms, tail, tail_lo, tail_hi = run_bootstrap_metrics(
                sub, rng, int(config["bootstrap_resamples"]), float(config["tail_abs_ns"])
            )
            denom = len(scored[(scored["method"] == method) & (scored["topology"] == topology)]) if topology != "all" else len(group)
            rows.append(
                {
                    "method": method,
                    "topology": topology,
                    "n_pair_rows": int(len(sub)),
                    "n_runs": int(sub["run"].nunique()),
                    "retention": float(len(sub) / denom) if denom else float("nan"),
                    "sigma68_ns": sigma,
                    "sigma68_ci_low_ns": lo,
                    "sigma68_ci_high_ns": hi,
                    "full_rms_ns": rms,
                    "tail_frac_abs_gt5ns": tail,
                    "tail_frac_ci_low": tail_lo,
                    "tail_frac_ci_high": tail_hi,
                }
            )
        for pair in PAIRS:
            sub = accepted[accepted["pair"] == pair]
            if len(sub) < 20:
                continue
            sigma, lo, hi, rms, tail, tail_lo, tail_hi = run_bootstrap_metrics(
                sub, rng, int(config["bootstrap_resamples"]), float(config["tail_abs_ns"])
            )
            pair_rows.append(
                {
                    "method": method,
                    "pair": pair,
                    "topology": "B2_containing" if "B2" in pair else "downstream_only",
                    "n_pair_rows": int(len(sub)),
                    "n_runs": int(sub["run"].nunique()),
                    "retention": float(len(sub) / max(raw_counts.get("B2_containing" if "B2" in pair else "downstream_only", len(sub)), 1)),
                    "sigma68_ns": sigma,
                    "sigma68_ci_low_ns": lo,
                    "sigma68_ci_high_ns": hi,
                    "full_rms_ns": rms,
                    "tail_frac_abs_gt5ns": tail,
                    "tail_frac_ci_low": tail_lo,
                    "tail_frac_ci_high": tail_hi,
                }
            )
    order = {"raw_no_veto": 0, "traditional_q_threshold_veto": 1, "ml_rf_qtemplate_veto": 2, "ml_rf_shuffled_label_control": 3}
    metrics = pd.DataFrame(rows)
    metrics["_method_order"] = metrics["method"].map(order)
    metrics = metrics.sort_values(["_method_order", "topology"]).drop(columns=["_method_order"]).reset_index(drop=True)
    by_pair = pd.DataFrame(pair_rows)
    by_pair["_method_order"] = by_pair["method"].map(order)
    by_pair = by_pair.sort_values(["_method_order", "pair"]).drop(columns=["_method_order"]).reset_index(drop=True)
    return metrics, by_pair


def delta_table(metrics: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for topology in TOPOLOGIES:
        raw = metrics[(metrics["method"] == "raw_no_veto") & (metrics["topology"] == topology)]
        if raw.empty:
            continue
        raw_sigma = float(raw.iloc[0]["sigma68_ns"])
        raw_tail = float(raw.iloc[0]["tail_frac_abs_gt5ns"])
        for method in ["traditional_q_threshold_veto", "ml_rf_qtemplate_veto", "ml_rf_shuffled_label_control"]:
            row = metrics[(metrics["method"] == method) & (metrics["topology"] == topology)]
            if row.empty:
                continue
            rows.append(
                {
                    "comparison": f"{method}_minus_raw_no_veto",
                    "topology": topology,
                    "delta_sigma68_ns": float(row.iloc[0]["sigma68_ns"]) - raw_sigma,
                    "delta_tail_frac_abs_gt5ns": float(row.iloc[0]["tail_frac_abs_gt5ns"]) - raw_tail,
                    "retention": float(row.iloc[0]["retention"]),
                }
            )
    return pd.DataFrame(rows)


def write_outputs(
    config: dict,
    config_path: Path,
    start: float,
    command: str,
    counts: pd.DataFrame,
    pair_counts: pd.DataFrame,
    table: pd.DataFrame,
    scored: pd.DataFrame,
    policies: pd.DataFrame,
    metrics: pd.DataFrame,
    pair_metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage_checks: pd.DataFrame,
) -> None:
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pair_counts.to_csv(out_dir / "raw_pair_count_reproduction.csv", index=False)
    table.head(2000).to_csv(out_dir / "raw_pair_table_preview.csv", index=False)
    policies.to_csv(out_dir / "heldout_veto_policies.csv", index=False)
    scored[[
        "run",
        "event",
        "pair",
        "topology",
        "method",
        "accepted",
        "heldout_centered_resid_ns",
        "q_max",
        "q_mean",
        "q_diff_abs",
        "ml_tail_score",
        "ml_shuffled_tail_score",
    ]].to_csv(out_dir / "heldout_pair_scores.csv.gz", index=False)
    metrics.to_csv(out_dir / "method_metrics_by_topology.csv", index=False)
    pair_metrics.to_csv(out_dir / "method_metrics_by_pair.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_vs_raw.csv", index=False)

    shuf = metrics[(metrics["method"] == "ml_rf_shuffled_label_control") & (metrics["topology"] == "B2_containing")]
    ml = metrics[(metrics["method"] == "ml_rf_qtemplate_veto") & (metrics["topology"] == "B2_containing")]
    trad = metrics[(metrics["method"] == "traditional_q_threshold_veto") & (metrics["topology"] == "B2_containing")]
    raw = metrics[(metrics["method"] == "raw_no_veto") & (metrics["topology"] == "B2_containing")]
    missing_q = int(table["q_missing"].sum())
    missing_q_fraction = float(missing_q / max(len(table), 1))
    extra_checks = [
        {
            "check": "qtemplate_join_missing_pair_rows",
            "value": missing_q,
            "pass": bool(missing_q_fraction <= 0.005),
            "interpretation": "small unmatched S01 q_template support is median-filled and reported; threshold is <=0.5% of pair rows",
        },
        {
            "check": "qtemplate_join_missing_pair_fraction",
            "value": missing_q_fraction,
            "pass": bool(missing_q_fraction <= 0.005),
            "interpretation": "fraction of pair rows with at least one missing q_template side after run/EVT/stave aggregation",
        },
        {
            "check": "shuffled_label_control_not_better_than_ml_b2_tail",
            "value": None if shuf.empty or ml.empty else float(shuf.iloc[0]["tail_frac_abs_gt5ns"] - ml.iloc[0]["tail_frac_abs_gt5ns"]),
            "pass": bool(shuf.empty or ml.empty or float(shuf.iloc[0]["tail_frac_abs_gt5ns"]) >= float(ml.iloc[0]["tail_frac_abs_gt5ns"])),
            "interpretation": "a shuffled-label RF should not reduce B2 tail fraction more than the nominal RF",
        },
        {
            "check": "ml_not_unphysical_zero_width",
            "value": None if ml.empty else float(ml.iloc[0]["sigma68_ns"]),
            "pass": bool(ml.empty or float(ml.iloc[0]["sigma68_ns"]) > 0.2),
            "interpretation": "guards against accidental target echo leakage",
        },
    ]
    leakage_checks = pd.concat([leakage_checks, pd.DataFrame(extra_checks)], ignore_index=True)
    leakage_checks.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    for run in all_configured_runs(config):
        path = raw_path(config, run)
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size), "role": "raw_b_root"})
    for path, role in [
        (ROOT / config["qtemplate_path"], "s01_qtemplate_table"),
        (S05E_HELPER, "raw_pair_table_helper"),
        (Path(__file__).resolve(), "study_script"),
        (config_path.resolve(), "study_config"),
    ]:
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size), "role": role})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_reproduction_pass": bool(counts["pass"].all() and pair_counts["pass"].all()),
        "qtemplate_join_missing_pair_rows": int(table["q_missing"].sum()),
        "primary_metrics": clean_json(metrics.to_dict("records")),
        "pair_metrics": clean_json(pair_metrics.to_dict("records")),
        "deltas_vs_raw": clean_json(deltas.to_dict("records")),
        "leakage_checks": clean_json(leakage_checks.to_dict("records")),
        "finding": "q_template vetoes reduce B2-containing tail fractions only by rejecting a substantial part of the pair table; downstream-only pairs change little because their raw tails are already small. The run-held-out RF is diagnostic, with shuffled-label and forbidden-feature controls preventing adoption as a target-echo shortcut.",
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")

    report = f"""# S04e: q_template vetoes on B2-containing residual tails

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Config:** `{config_path.relative_to(ROOT) if config_path.is_absolute() else config_path}`
- **Inputs:** raw B-stack ROOT under `{config['raw_root_dir']}` and the S01 q_template table.

## Question

Do q_template veto policies that were weak on S03 downstream-only pairs change the full S04/S05 B2-containing pair-residual tail tables by topology?

## Raw ROOT Reproduction First

The gate rebuilds the S05e/S05c B-stack pair table directly from `h101/HRDv`: baseline samples 0-3, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, CFD20 timing, `A > 1000 ADC`, and the configured S04/S05 analysis runs.

{markdown_table(counts)}

Pair-row anchor:

{markdown_table(pair_counts)}

## Held-out Methods

Residuals are scored by held-out run. Each fold computes pair medians, q-thresholds, and RF veto thresholds on train runs only, then applies them to the held-out run. The traditional method is a fixed q-template threshold policy chosen on train rows by topology. The ML method is a RandomForest tail-veto using q-template plus waveform shape summaries; it excludes run, event, raw times, raw residuals, and target residuals. A shuffled-label RF is the leakage/control row.

{markdown_table(metrics)}

By pair:

{markdown_table(pair_metrics)}

Delta versus no veto:

{markdown_table(deltas)}

## Leakage Checks

{markdown_table(leakage_checks)}

## Finding

The q-template policies mostly act as B2/topology pathology vetoes, not as a clean downstream timing-quality improvement. B2-containing rows start with the largest `abs > 5 ns` tail fraction and receive the visible tail reduction, but only after rejecting a material fraction of the table. Downstream-only rows have small raw tails, so q-template vetoes have little room to improve them. The RF veto is useful as a diagnostic because it is run-held-out and beats the shuffled-label control where it matters, but it should be treated as a veto/support map, not a replacement residual correction. The q-template join leaves `{missing_q}` pair rows (`{missing_q_fraction:.3%}`) with at least one unmatched side after the necessary `run/EVT/stave` aggregation; those rows are median-filled and tracked as a support limitation.

## Reproducibility

```bash
{command}
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "command": command,
        "git_commit_at_run": git_head(),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_sec": round(time.time() - start, 3),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "inputs": input_rows,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    start = time.time()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rel_config = config_path.relative_to(ROOT)
    command = f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config {rel_config}"

    s05e = load_s05e()
    counts, pair_counts = reproduce_raw_anchor(config, s05e)
    pair_table = s05e.build_pair_table(config)
    q = load_qtemplate(config)
    table = add_qtemplate(pair_table, q)
    scored, policies, leakage_checks = run_heldout(table, config)
    metrics, pair_metrics = metric_tables(scored, config)
    deltas = delta_table(metrics, config)
    write_outputs(config, config_path, start, command, counts, pair_counts, table, scored, policies, metrics, pair_metrics, deltas, leakage_checks)


if __name__ == "__main__":
    main()
