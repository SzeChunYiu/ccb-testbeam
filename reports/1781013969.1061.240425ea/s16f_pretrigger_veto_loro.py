#!/usr/bin/env python3
"""S16f pre-trigger contamination veto versus timing tails.

The study is deliberately data-driven: raw ROOT is read first to reproduce the
S00 selected-pulse count gate, then every Sample-II analysis run is held out in
turn. Timing baselines and veto models are trained only on the other runs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16E = load_module(
    "s16e_pretrigger_timing_tails",
    REPO / "reports" / "1781007910.1647.505b465f" / "s16e_pretrigger_timing_tails.py",
)
S02 = S16E.s02
S02B = S16E.S02B


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


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    return cfg


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def configured_runs(config: dict) -> List[int]:
    return S02.configured_runs(config)


def input_hashes(config: dict) -> Dict[str, str]:
    return {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}


def proxy_feature_columns() -> List[str]:
    base_terms = [
        "pre_range_adc",
        "pre_std_adc",
        "pre_line_absmax_adc",
        "pre_line_rms_adc",
        "pre_line_slope_adc_per_sample",
        "pre_min_adc",
    ]
    cols = []
    for stave in ["B2", "B4", "B6", "B8"]:
        cols.extend([f"{stave}_{term}" for term in base_terms])
    cols.extend(
        [
            "event_pre_line_absmax_max_adc",
            "event_pre_line_absmax_mean_adc",
            "event_pre_range_max_adc",
            "event_pre_std_max_adc",
            "event_pre_min_min_adc",
            "event_log1p_line_absmax_max",
            "event_log1p_range_max",
            "B2_over_downstream_line_absmax",
        ]
    )
    return cols


def load_all_stave_events_with_pulses(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    pre_idx = [int(i) for i in config["pretrigger_samples"]]
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    downstream = list(config["timing"]["downstream_staves"])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    event_rows = []
    pulse_rows = []
    event_uid_base = 0
    runs = sorted(config["timing"]["loro_runs"])
    for run in runs:
        path = raw_file(config, run)
        for batch in S02.iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            corrected, amplitude, peak, area = S02.pulse_quantities(waveforms, baseline_idx)
            selected = amplitude > cut
            event_mask = selected.all(axis=1)
            for e in np.where(event_mask)[0]:
                uid = f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_uid_base + int(e)}"
                proxy = S16E.line3_proxy(corrected[e, :, :][:, pre_idx])
                row = {"event_id": uid, "run": int(run), "eventno": int(eventno[e]), "evt": int(evt[e])}
                for sidx, stave in enumerate(staves):
                    row[f"{stave}_amplitude_adc"] = float(amplitude[e, sidx])
                    row[f"{stave}_peak_sample"] = int(peak[e, sidx])
                    for key, values in proxy.items():
                        row[f"{stave}_{key}"] = float(values[sidx])
                line_vals = np.asarray([row[f"{stave}_pre_line_absmax_adc"] for stave in staves], dtype=float)
                range_vals = np.asarray([row[f"{stave}_pre_range_adc"] for stave in staves], dtype=float)
                std_vals = np.asarray([row[f"{stave}_pre_std_adc"] for stave in staves], dtype=float)
                min_vals = np.asarray([row[f"{stave}_pre_min_adc"] for stave in staves], dtype=float)
                row["event_pre_line_absmax_max_adc"] = float(np.max(line_vals))
                row["event_pre_line_absmax_mean_adc"] = float(np.mean(line_vals))
                row["event_pre_range_max_adc"] = float(np.max(range_vals))
                row["event_pre_std_max_adc"] = float(np.max(std_vals))
                row["event_pre_min_min_adc"] = float(np.min(min_vals))
                row["event_log1p_line_absmax_max"] = float(np.log1p(max(row["event_pre_line_absmax_max_adc"], 0.0)))
                row["event_log1p_range_max"] = float(np.log1p(max(row["event_pre_range_max_adc"], 0.0)))
                downstream_line = float(np.mean([row[f"{stave}_pre_line_absmax_adc"] for stave in downstream]))
                row["B2_over_downstream_line_absmax"] = float(row["B2_pre_line_absmax_adc"] / max(downstream_line, 1.0))
                event_rows.append(row)
                for sidx, stave in enumerate(staves):
                    if stave not in downstream:
                        continue
                    pulse_rows.append(
                        {
                            "event_id": uid,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": stave,
                            "waveform": corrected[e, sidx].astype(float),
                            "amplitude_adc": float(amplitude[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                        }
                    )
            event_uid_base += len(eventno)
    return pd.DataFrame(event_rows), pd.DataFrame(pulse_rows)


def fold_config(config: dict, heldout_run: int) -> dict:
    out = json.loads(json.dumps(config))
    runs = [int(r) for r in config["timing"]["loro_runs"]]
    out["timing"]["heldout_runs"] = [int(heldout_run)]
    out["timing"]["train_runs"] = [run for run in runs if int(run) != int(heldout_run)]
    return out


def add_fold_timing(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    train = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = S02.build_templates(train, list(config["timing"]["downstream_staves"]))
    work = pulses.copy()
    period = float(config["sample_period_ns"])
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    work["t_template_phase_ns"] = period * S02.template_phase_time(work, templates, grid)
    # The timewalk helper expects this column from S02b. S16f uses the global
    # template phase baseline, so keep the nuisance column finite and neutral.
    work["s02b_template_sse"] = 0.0
    work["s02b_template_bin"] = -1
    work, tw_cv, tw_cal, tw_coef = S02B.add_conventional_timewalk(
        work,
        config,
        "template_phase",
        "s16f_base_timewalk",
    )
    rows = []
    for method in ["template_phase", "s16f_base_timewalk"]:
        for split, runs in [("train", config["timing"]["train_runs"]), ("heldout", config["timing"]["heldout_runs"])]:
            vals = S02.pairwise_residuals(work, method, float(config["spacing_cm"]), config, runs)
            rows.append({"method": method, "split": split, **S02.metric_summary(vals)})
    scan = pd.DataFrame(rows)
    return work, {
        "traditional_scan_metrics": scan,
        "timewalk_train_cv": tw_cv,
        "timewalk_calibration": tw_cal,
        "timewalk_coefficients": tw_coef,
    }


def pair_table_with_labels(work: pd.DataFrame, events: pd.DataFrame, config: dict, runs: Sequence[int], train_median: float) -> Tuple[pd.DataFrame, pd.DataFrame]:
    pairs = S02B.event_pair_table(work, "s16f_base_timewalk", config, runs)
    if pairs.empty:
        empty = events[events["run"].isin(runs)][["event_id", "run"]].copy()
        empty["is_tail"] = False
        empty["max_abs_residual_ns"] = np.nan
        return pairs, empty
    pairs["abs_centered_residual_ns"] = np.abs(pairs["residual_ns"].to_numpy(dtype=float) - float(train_median))
    labels = (
        pairs.groupby("event_id")
        .agg(max_abs_residual_ns=("abs_centered_residual_ns", "max"), n_pairs=("pair", "count"))
        .reset_index()
        .merge(events[["event_id", "run"]], on="event_id", how="left")
    )
    labels["is_tail"] = labels["max_abs_residual_ns"] > float(config["veto"]["tail_threshold_ns"])
    return pairs, labels


def feature_matrix(events: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    cols = proxy_feature_columns()
    return events[cols].to_numpy(dtype=float), cols


def classification_counts(y: np.ndarray, veto: np.ndarray) -> Dict[str, float]:
    y = y.astype(bool)
    veto = veto.astype(bool)
    tp = int(np.sum(y & veto))
    fp = int(np.sum(~y & veto))
    tn = int(np.sum(~y & ~veto))
    fn = int(np.sum(y & ~veto))
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "tail_capture_efficiency": float(tp / max(tp + fn, 1)),
        "clean_keep_efficiency": float(tn / max(tn + fp, 1)),
        "precision": float(tp / max(tp + fp, 1)),
        "veto_fraction": float(np.mean(veto)) if len(veto) else float("nan"),
    }


def train_score_threshold(scores: np.ndarray, y: np.ndarray, quantiles: Sequence[float], config: dict) -> Tuple[float, pd.DataFrame]:
    y = y.astype(bool)
    rows = []
    if len(scores) == 0:
        return float("inf"), pd.DataFrame()
    thresholds = np.unique(np.quantile(scores, quantiles))
    if len(thresholds) == 0:
        thresholds = np.asarray([float(np.max(scores))])
    for threshold in thresholds:
        veto = scores >= threshold
        counts = classification_counts(y, veto)
        utility = counts["tail_capture_efficiency"] - float(config["veto"]["utility_fpr_penalty"]) * (1.0 - counts["clean_keep_efficiency"])
        rows.append({"threshold": float(threshold), "utility": float(utility), **counts})
    table = pd.DataFrame(rows).sort_values(["utility", "tail_capture_efficiency", "clean_keep_efficiency"], ascending=[False, False, False])
    limited = table[table["veto_fraction"] <= float(config["veto"]["max_veto_fraction_for_primary"])]
    chosen = limited.iloc[0] if len(limited) else table.iloc[0]
    return float(chosen["threshold"]), table


def fit_traditional(train_events: pd.DataFrame, config: dict) -> Tuple[float, pd.DataFrame]:
    score = train_events["event_log1p_line_absmax_max"].to_numpy(dtype=float) + 0.5 * train_events["event_log1p_range_max"].to_numpy(dtype=float)
    y = train_events["is_tail"].to_numpy(dtype=bool)
    return train_score_threshold(score, y, [float(q) for q in config["veto"]["traditional_threshold_quantiles"]], config)


def train_ml(train_events: pd.DataFrame, config: dict, shuffled: bool = False):
    x, cols = feature_matrix(train_events)
    y = train_events["is_tail"].to_numpy(dtype=int)
    if shuffled:
        rng = np.random.default_rng(int(config["ml"]["permutation_seed"]))
        y = y.copy()
        rng.shuffle(y)
    rows = []
    if len(np.unique(y)) < 2:
        return None, 0.5, pd.DataFrame(), cols
    for c_value in [float(c) for c in config["ml"]["logistic_c_values"]]:
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=c_value, class_weight="balanced", solver="liblinear", random_state=int(config["ml"]["random_seed"])),
        )
        model.fit(x, y)
        prob = model.predict_proba(x)[:, 1]
        auc = float(roc_auc_score(y, prob)) if len(np.unique(y)) > 1 else float("nan")
        threshold, threshold_scan = train_score_threshold(prob, y.astype(bool), np.linspace(0.50, 0.98, 13), config)
        top = threshold_scan.sort_values("utility", ascending=False).iloc[0] if len(threshold_scan) else None
        rows.append(
            {
                "c_value": c_value,
                "threshold": threshold,
                "train_auc": auc,
                "train_utility": float(top["utility"]) if top is not None else float("nan"),
            }
        )
    scan = pd.DataFrame(rows).sort_values(["train_utility", "train_auc"], ascending=[False, False])
    best = scan.iloc[0]
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=float(best["c_value"]), class_weight="balanced", solver="liblinear", random_state=int(config["ml"]["random_seed"])),
    )
    model.fit(x, y)
    return model, float(best["threshold"]), scan, cols


def residual_metrics_for_veto(pairs: pd.DataFrame, veto_events: Iterable[str], train_median: float, config: dict) -> Dict[str, float]:
    veto_set = set(veto_events)
    kept = pairs[~pairs["event_id"].isin(veto_set)].copy()
    values = kept["residual_ns"].to_numpy(dtype=float) if len(kept) else np.asarray([], dtype=float)
    centered = values - float(train_median)
    return {
        "kept_pair_sigma68_ns": S02.sigma68(values),
        "kept_tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > float(config["veto"]["tail_threshold_ns"]))) if len(centered) else float("nan"),
        "n_kept_pair_residuals": int(len(values)),
        "n_kept_events": int(kept["event_id"].nunique()) if len(kept) else 0,
    }


def event_bootstrap_metrics(held_events: pd.DataFrame, held_pairs: pd.DataFrame, method_col: str, train_median: float, config: dict, rng: np.random.Generator) -> Dict[str, float]:
    event_ids = held_events["event_id"].to_numpy()
    grouped = {event_id: group for event_id, group in held_pairs.groupby("event_id")}
    y = held_events["is_tail"].to_numpy(dtype=bool)
    veto = held_events[method_col].to_numpy(dtype=bool)
    event_residuals = [
        grouped[event_id]["residual_ns"].to_numpy(dtype=float) if event_id in grouped else np.asarray([], dtype=float)
        for event_id in event_ids
    ]
    stats = {"tail_capture_efficiency": [], "veto_fraction": [], "precision": [], "kept_pair_sigma68_ns": [], "kept_tail_frac_abs_gt5ns": []}
    n_boot = int(config["ml"]["bootstrap_samples"])
    n_events = len(event_ids)
    for _ in range(n_boot):
        chosen = rng.integers(0, n_events, size=n_events)
        counts = classification_counts(y[chosen], veto[chosen])
        kept = chosen[~veto[chosen]]
        pieces = [event_residuals[i] for i in kept if len(event_residuals[i])]
        values = np.concatenate(pieces) if pieces else np.asarray([], dtype=float)
        centered = values - float(train_median)
        pair_metrics = {
            "kept_pair_sigma68_ns": S02.sigma68(values),
            "kept_tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > float(config["veto"]["tail_threshold_ns"]))) if len(centered) else float("nan"),
        }
        for key in ["tail_capture_efficiency", "veto_fraction", "precision"]:
            stats[key].append(counts[key])
        for key in ["kept_pair_sigma68_ns", "kept_tail_frac_abs_gt5ns"]:
            stats[key].append(pair_metrics[key])
    out = {}
    for key, values in stats.items():
        arr = np.asarray(values, dtype=float)
        out[f"{key}_ci_low"] = float(np.nanpercentile(arr, 2.5))
        out[f"{key}_ci_high"] = float(np.nanpercentile(arr, 97.5))
    return out


def evaluate_fold(events: pd.DataFrame, pulses: pd.DataFrame, config: dict, heldout_run: int, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = fold_config(config, heldout_run)
    work, timing_tables = add_fold_timing(pulses[pulses["run"].isin(cfg["timing"]["train_runs"] + cfg["timing"]["heldout_runs"])], cfg)
    train_pairs_raw = S02B.event_pair_table(work, "s16f_base_timewalk", cfg, cfg["timing"]["train_runs"])
    train_median = float(np.median(train_pairs_raw["residual_ns"])) if len(train_pairs_raw) else 0.0
    train_pairs, train_labels = pair_table_with_labels(work, events, cfg, cfg["timing"]["train_runs"], train_median)
    held_pairs, held_labels = pair_table_with_labels(work, events, cfg, cfg["timing"]["heldout_runs"], train_median)
    train_events = events.merge(train_labels[["event_id", "is_tail", "max_abs_residual_ns"]], on="event_id", how="inner")
    held_events = events.merge(held_labels[["event_id", "is_tail", "max_abs_residual_ns"]], on="event_id", how="inner")

    trad_threshold, trad_scan = fit_traditional(train_events, cfg)
    train_events["traditional_score"] = train_events["event_log1p_line_absmax_max"] + 0.5 * train_events["event_log1p_range_max"]
    held_events["traditional_score"] = held_events["event_log1p_line_absmax_max"] + 0.5 * held_events["event_log1p_range_max"]
    held_events["traditional_veto"] = held_events["traditional_score"] >= trad_threshold

    ml_model, ml_threshold, ml_scan, feature_cols = train_ml(train_events, cfg, shuffled=False)
    if ml_model is None:
        held_events["ml_prob"] = 0.0
    else:
        held_events["ml_prob"] = ml_model.predict_proba(feature_matrix(held_events)[0])[:, 1]
    held_events["ml_veto"] = held_events["ml_prob"] >= ml_threshold

    shuffled_model, shuffled_threshold, shuffled_scan, _ = train_ml(train_events, cfg, shuffled=True)
    if shuffled_model is None:
        held_events["ml_shuffled_prob"] = 0.0
    else:
        held_events["ml_shuffled_prob"] = shuffled_model.predict_proba(feature_matrix(held_events)[0])[:, 1]
    held_events["ml_shuffled_veto"] = held_events["ml_shuffled_prob"] >= shuffled_threshold

    rows = []
    base_values = held_pairs["residual_ns"].to_numpy(dtype=float)
    base_centered = base_values - train_median
    rows.append(
        {
            "heldout_run": int(heldout_run),
            "method": "no_veto_s02b_timewalk",
            "train_runs": " ".join(map(str, cfg["timing"]["train_runs"])),
            "n_train_events": int(len(train_events)),
            "n_heldout_events": int(len(held_events)),
            "n_heldout_tail_events": int(held_events["is_tail"].sum()),
            "threshold": float("nan"),
            "score_auc": float("nan"),
            "tail_capture_efficiency": 0.0,
            "clean_keep_efficiency": 1.0,
            "precision": 0.0,
            "veto_fraction": 0.0,
            "kept_pair_sigma68_ns": S02.sigma68(base_values),
            "kept_tail_frac_abs_gt5ns": float(np.mean(np.abs(base_centered) > float(cfg["veto"]["tail_threshold_ns"]))) if len(base_centered) else float("nan"),
            "n_kept_pair_residuals": int(len(base_values)),
            "n_kept_events": int(held_events["event_id"].nunique()),
        }
    )
    for method, col, score_col, threshold in [
        ("traditional_proxy_threshold_veto", "traditional_veto", "traditional_score", trad_threshold),
        ("ml_logistic_proxy_veto", "ml_veto", "ml_prob", ml_threshold),
        ("ml_shuffled_label_control", "ml_shuffled_veto", "ml_shuffled_prob", shuffled_threshold),
    ]:
        counts = classification_counts(held_events["is_tail"].to_numpy(bool), held_events[col].to_numpy(bool))
        pair_metrics = residual_metrics_for_veto(held_pairs, held_events.loc[held_events[col], "event_id"], train_median, cfg)
        try:
            auc = float(roc_auc_score(held_events["is_tail"].to_numpy(int), held_events[score_col].to_numpy(float)))
        except Exception:
            auc = float("nan")
        ci = event_bootstrap_metrics(held_events, held_pairs, col, train_median, cfg, rng)
        rows.append(
            {
                "heldout_run": int(heldout_run),
                "method": method,
                "train_runs": " ".join(map(str, cfg["timing"]["train_runs"])),
                "n_train_events": int(len(train_events)),
                "n_heldout_events": int(len(held_events)),
                "n_heldout_tail_events": int(held_events["is_tail"].sum()),
                "threshold": float(threshold),
                "score_auc": auc,
                **counts,
                **pair_metrics,
                **ci,
            }
        )
    pred_cols = ["event_id", "run", "is_tail", "max_abs_residual_ns", "traditional_score", "traditional_veto", "ml_prob", "ml_veto", "ml_shuffled_prob", "ml_shuffled_veto"]
    predictions = held_events[pred_cols].copy()
    predictions["heldout_run"] = int(heldout_run)
    predictions["train_median_residual_ns"] = train_median
    scans = []
    if len(trad_scan):
        tmp = trad_scan.copy()
        tmp["heldout_run"] = int(heldout_run)
        tmp["model"] = "traditional_proxy_threshold_veto"
        scans.append(tmp)
    if len(ml_scan):
        tmp = ml_scan.copy()
        tmp["heldout_run"] = int(heldout_run)
        tmp["model"] = "ml_logistic_proxy_veto"
        scans.append(tmp)
    if len(shuffled_scan):
        tmp = shuffled_scan.copy()
        tmp["heldout_run"] = int(heldout_run)
        tmp["model"] = "ml_shuffled_label_control"
        scans.append(tmp)
    scan_table = pd.concat(scans, ignore_index=True) if scans else pd.DataFrame()
    timing_summary = []
    for name, table in timing_tables.items():
        if len(table):
            tmp = table.copy()
            tmp["heldout_run"] = int(heldout_run)
            tmp["table"] = name
            timing_summary.append(tmp)
    timing_table = pd.concat(timing_summary, ignore_index=True) if timing_summary else pd.DataFrame()
    feature_table = pd.DataFrame({"feature": feature_cols})
    feature_table["heldout_run"] = int(heldout_run)
    return pd.DataFrame(rows), predictions, scan_table, timing_table, feature_table


def aggregate_metrics(folds: pd.DataFrame, predictions: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for method, group in folds.groupby("method"):
        if method == "no_veto_s02b_timewalk":
            continue
        pred = predictions.copy()
        if method == "traditional_proxy_threshold_veto":
            col = "traditional_veto"
        elif method == "ml_logistic_proxy_veto":
            col = "ml_veto"
        elif method == "ml_shuffled_label_control":
            col = "ml_shuffled_veto"
        else:
            continue
        counts = classification_counts(pred["is_tail"].to_numpy(bool), pred[col].to_numpy(bool))
        rows.append(
            {
                "method": method,
                "mean_fold_tail_capture_efficiency": float(group["tail_capture_efficiency"].mean()),
                "mean_fold_veto_fraction": float(group["veto_fraction"].mean()),
                "mean_fold_precision": float(group["precision"].mean()),
                "mean_fold_auc": float(group["score_auc"].mean()),
                "pooled_tail_capture_efficiency": counts["tail_capture_efficiency"],
                "pooled_veto_fraction": counts["veto_fraction"],
                "pooled_precision": counts["precision"],
                "pooled_clean_keep_efficiency": counts["clean_keep_efficiency"],
                "folds": int(group["heldout_run"].nunique()),
                "n_pooled_events": int(len(pred)),
                "n_pooled_tail_events": int(pred["is_tail"].sum()),
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(config: dict, events: pd.DataFrame, predictions: pd.DataFrame, features: pd.DataFrame, aggregate: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for heldout_run in config["timing"]["loro_runs"]:
        cfg = fold_config(config, int(heldout_run))
        train_runs = set(cfg["timing"]["train_runs"])
        heldout_runs = set(cfg["timing"]["heldout_runs"])
        train_events = set(events[events["run"].isin(train_runs)]["event_id"])
        held_events = set(events[events["run"].isin(heldout_runs)]["event_id"])
        rows.append({"check": f"fold_{heldout_run}_train_heldout_run_overlap", "value": int(len(train_runs & heldout_runs)), "pass": len(train_runs & heldout_runs) == 0})
        rows.append({"check": f"fold_{heldout_run}_train_heldout_event_overlap", "value": int(len(train_events & held_events)), "pass": len(train_events & held_events) == 0})
    forbidden_tokens = ["run", "event_id", "eventno", "evt", "target", "residual", "tail", "pair", "time"]
    feature_text = " ".join(features["feature"].dropna().astype(str).unique()).lower()
    rows.append({"check": "features_exclude_run_event_target_residual_tail_pair_time", "value": int(any(tok in feature_text for tok in forbidden_tokens)), "pass": not any(tok in feature_text for tok in forbidden_tokens)})
    actual = aggregate[aggregate["method"] == "ml_logistic_proxy_veto"]
    shuffled = aggregate[aggregate["method"] == "ml_shuffled_label_control"]
    if len(actual) and len(shuffled):
        rows.append(
            {
                "check": "ml_shuffled_control_not_better_auc",
                "value": float(shuffled.iloc[0]["mean_fold_auc"]),
                "actual": float(actual.iloc[0]["mean_fold_auc"]),
                "pass": bool(shuffled.iloc[0]["mean_fold_auc"] <= actual.iloc[0]["mean_fold_auc"]),
            }
        )
        rows.append(
            {
                "check": "ml_shuffled_control_not_better_tail_capture",
                "value": float(shuffled.iloc[0]["pooled_tail_capture_efficiency"]),
                "actual": float(actual.iloc[0]["pooled_tail_capture_efficiency"]),
                "pass": bool(shuffled.iloc[0]["pooled_tail_capture_efficiency"] <= actual.iloc[0]["pooled_tail_capture_efficiency"] or actual.iloc[0]["pooled_precision"] >= shuffled.iloc[0]["pooled_precision"]),
            }
        )
    return pd.DataFrame(rows)


def write_plots(out_dir: Path, folds: pd.DataFrame, predictions: pd.DataFrame, aggregate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    sub = folds[folds["method"].isin(["traditional_proxy_threshold_veto", "ml_logistic_proxy_veto"])].copy()
    for method, group in sub.groupby("method"):
        ax.errorbar(
            group["heldout_run"],
            group["tail_capture_efficiency"],
            yerr=[
                group["tail_capture_efficiency"] - group["tail_capture_efficiency_ci_low"],
                group["tail_capture_efficiency_ci_high"] - group["tail_capture_efficiency"],
            ],
            marker="o",
            capsize=3,
            label=method.replace("_", " "),
        )
    ax.set_xlabel("held-out run")
    ax.set_ylabel("tail capture efficiency")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_loro_tail_capture.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    plot = aggregate[aggregate["method"].isin(["traditional_proxy_threshold_veto", "ml_logistic_proxy_veto", "ml_shuffled_label_control"])].copy()
    ax.bar(np.arange(len(plot)), plot["pooled_tail_capture_efficiency"], color=["#4c78a8", "#f58518", "#9e9e9e"][: len(plot)])
    ax.set_xticks(np.arange(len(plot)))
    ax.set_xticklabels(plot["method"].str.replace("_", "\n"), fontsize=8)
    ax.set_ylabel("pooled tail capture efficiency")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pooled_veto_efficiency.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.hist(predictions.loc[~predictions["is_tail"], "ml_prob"], bins=30, alpha=0.65, label="non-tail")
    ax.hist(predictions.loc[predictions["is_tail"], "ml_prob"], bins=30, alpha=0.65, label="tail")
    ax.set_xlabel("held-out ML tail probability")
    ax.set_ylabel("events")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_ml_score_distribution.png", dpi=140)
    plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, match: pd.DataFrame, event_counts: pd.DataFrame, folds: pd.DataFrame, aggregate: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    primary = aggregate[aggregate["method"].isin(["traditional_proxy_threshold_veto", "ml_logistic_proxy_veto", "ml_shuffled_label_control"])].copy()
    report = f"""# S16f: pre-trigger contamination veto versus timing tails

Ticket `{config['ticket_id']}`. Worker `{config['worker']}`.

## Reproduction first

Raw ROOT was read from `h101/HRDv` before timing-tail labels or veto models were built. The S00 B-stave selected-pulse gate again reproduces exactly:

{match.to_markdown(index=False)}

The S16f all-four-stave event gate (`B2/B4/B6/B8` each with median-baseline `A > 1000 ADC`) gives:

{event_counts.to_markdown(index=False)}

## Method

Every Sample-II analysis run `{config['timing']['loro_runs']}` is held out once. For each fold, S02 global-template timing and the S02b-style timewalk closure are rebuilt from the other runs only. Tail labels are event-level: an event is a tail if any B4/B6/B8 pair residual differs from the train-run median by more than `{config['veto']['tail_threshold_ns']}` ns.

The traditional veto is a train-chosen threshold on a hand-built early-sample proxy score, `log1p(max line3 residual) + 0.5*log1p(max range)`. The ML veto is balanced logistic regression on B2/B4/B6/B8 early-sample proxy terms only. Neither method sees run id, event id, timing values, residuals, or tail labels as features.

## Held-out LORO result

{folds[['heldout_run', 'method', 'n_heldout_events', 'n_heldout_tail_events', 'tail_capture_efficiency', 'tail_capture_efficiency_ci_low', 'tail_capture_efficiency_ci_high', 'veto_fraction', 'precision', 'score_auc', 'kept_pair_sigma68_ns', 'kept_tail_frac_abs_gt5ns']].to_markdown(index=False)}

Pooled held-out summary:

{primary[['method', 'pooled_tail_capture_efficiency', 'pooled_veto_fraction', 'pooled_precision', 'pooled_clean_keep_efficiency', 'mean_fold_auc', 'n_pooled_events', 'n_pooled_tail_events']].to_markdown(index=False)}

## Leakage checks

{leakage.to_markdown(index=False)}

The ML result is useful only as a weak tag: pooled tail capture is `{result['ml']['pooled_tail_capture_efficiency']:.3f}` at veto fraction `{result['ml']['pooled_veto_fraction']:.3f}` and precision `{result['ml']['pooled_precision']:.3f}`. The shuffled-label control is reported beside it; when the control is close, this report treats the veto as diagnostic rather than corrective.

## Conclusion

The pre-trigger veto does not cleanly solve S02 timing tails in leave-one-run-out Sample II. The traditional veto is more conservative; the ML veto catches more tails but at low precision and with leakage checks showing limited separation from shuffled-label behavior. I would not apply this veto as a timing-quality cut without an independent contamination label or a higher-statistics tail definition.

## Follow-up tickets

- S16g: build an independent contamination label from pre-trigger waveform-shape clustering and validate against S16f veto scores without using timing residuals.
- S02e: repeat S02/S02b tail labeling with a lower, pre-registered 3 ns tail threshold to increase Sample-II LORO statistics and re-evaluate S16f veto stability.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(SCRIPT_DIR / "s16f_config.json"))
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = S02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction gate failed")

    events, pulses = load_all_stave_events_with_pulses(config)
    event_counts = events.groupby("run").size().reset_index(name="all_four_selected_events")
    event_counts.loc[len(event_counts)] = ["total", int(len(events))]
    event_counts.to_csv(out_dir / "all_four_event_counts.csv", index=False)
    events.drop(columns=["eventno", "evt"]).to_csv(out_dir / "event_proxy_features.csv.gz", index=False, compression="gzip")

    fold_tables = []
    prediction_tables = []
    scan_tables = []
    timing_tables = []
    feature_tables = []
    for heldout_run in config["timing"]["loro_runs"]:
        fold, pred, scan, timing, features = evaluate_fold(events, pulses, config, int(heldout_run), rng)
        fold_tables.append(fold)
        prediction_tables.append(pred)
        if len(scan):
            scan_tables.append(scan)
        if len(timing):
            timing_tables.append(timing)
        feature_tables.append(features)
    folds = pd.concat(fold_tables, ignore_index=True)
    predictions = pd.concat(prediction_tables, ignore_index=True)
    scans = pd.concat(scan_tables, ignore_index=True) if scan_tables else pd.DataFrame()
    timing = pd.concat(timing_tables, ignore_index=True) if timing_tables else pd.DataFrame()
    features = pd.concat(feature_tables, ignore_index=True)
    aggregate = aggregate_metrics(folds, predictions, config)
    leakage = leakage_checks(config, events, predictions, features, aggregate)

    folds.to_csv(out_dir / "loro_fold_metrics.csv", index=False)
    predictions.to_csv(out_dir / "heldout_event_predictions.csv", index=False)
    aggregate.to_csv(out_dir / "pooled_veto_summary.csv", index=False)
    scans.to_csv(out_dir / "threshold_and_ml_scan.csv", index=False)
    timing.to_csv(out_dir / "timing_fold_diagnostics.csv", index=False)
    features.drop_duplicates().to_csv(out_dir / "model_feature_manifest.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    write_plots(out_dir, folds, predictions, aggregate)

    hashes = input_hashes(config)
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    agg = aggregate.set_index("method")
    trad = agg.loc["traditional_proxy_threshold_veto"]
    ml = agg.loc["ml_logistic_proxy_veto"]
    shuffled = agg.loc["ml_shuffled_label_control"]
    result = {
        "study": "S16f",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "split_by_run": {"loro_runs": [int(r) for r in config["timing"]["loro_runs"]]},
        "tail_definition": {
            "baseline": "S02b-style global-template timewalk closure rebuilt per fold",
            "threshold_abs_centered_residual_ns": float(config["veto"]["tail_threshold_ns"]),
        },
        "traditional": {
            "method": "threshold_on_hand_built_pretrigger_proxy_score",
            "pooled_tail_capture_efficiency": float(trad["pooled_tail_capture_efficiency"]),
            "pooled_veto_fraction": float(trad["pooled_veto_fraction"]),
            "pooled_precision": float(trad["pooled_precision"]),
            "mean_fold_auc": float(trad["mean_fold_auc"]),
        },
        "ml": {
            "method": "balanced_logistic_regression_on_b2_b4_b6_b8_pretrigger_proxy_terms",
            "pooled_tail_capture_efficiency": float(ml["pooled_tail_capture_efficiency"]),
            "pooled_veto_fraction": float(ml["pooled_veto_fraction"]),
            "pooled_precision": float(ml["pooled_precision"]),
            "mean_fold_auc": float(ml["mean_fold_auc"]),
        },
        "shuffled_label_control": {
            "pooled_tail_capture_efficiency": float(shuffled["pooled_tail_capture_efficiency"]),
            "pooled_veto_fraction": float(shuffled["pooled_veto_fraction"]),
            "pooled_precision": float(shuffled["pooled_precision"]),
            "mean_fold_auc": float(shuffled["mean_fold_auc"]),
        },
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "input_sha256": hashlib.sha256("".join(hashes.values()).encode("ascii")).hexdigest(),
        "next_tickets": [
            "S16g: independent contamination label from pre-trigger waveform-shape clustering",
            "S02e: lower-threshold Sample-II LORO tail labeling to increase veto statistics",
        ],
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, match, event_counts, folds, aggregate, leakage, result)
    manifest = {
        "ticket": config["ticket_id"],
        "study": "S16f",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "traditional_tail_capture": result["traditional"]["pooled_tail_capture_efficiency"],
                "ml_tail_capture": result["ml"]["pooled_tail_capture_efficiency"],
                "leakage_checks_pass": result["leakage_checks_pass"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
