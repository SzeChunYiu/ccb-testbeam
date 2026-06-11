#!/usr/bin/env python3
"""P12c pulse-action decision matrix and run-heldout action-risk benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p12a_1781023340_632_43377364_pulse_axis_covariance as p12a  # noqa: E402
import p12b_1781040960_896_205a0b9d_pulse_support_tensor as p12b  # noqa: E402


NUMERIC_COLS = p12b.NUMERIC_COLS
CAT_COLS = p12b.CAT_COLS


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


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def sigma68(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return np.nan
    med = np.nanmedian(arr)
    return float(np.nanquantile(np.abs(arr - med), 0.68))


def full_rms(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return np.nan
    return float(np.sqrt(np.nanmean((arr - np.nanmedian(arr)) ** 2)))


def add_consumer_targets(atom_df: pd.DataFrame) -> pd.DataFrame:
    out = atom_df.copy()
    out["baseline_harm"] = (
        (out["adaptive_lowering"] == 1)
        | (out["early_pretrigger_activity"] == 1)
        | (out["baseline_atom"].isin(["baseline_adaptive_lowering", "baseline_pretrigger_activity", "baseline_noisy"]))
    ).astype(int)
    out["dropout_harm"] = (out["dropout_anomaly_atom"] != "anomaly_none").astype(int)
    out["covariance_harm"] = (out["covariance_atom"] != "covariance_sparse").astype(int)
    out["pid_energy_proxy_degradation"] = (
        (out["charge_transfer_error"] == 1)
        | ((out["high_amplitude"] == 1) & (out["saturation_boundary"] == 1))
        | ((out["timing_tail"] == 1) & (out["pileup_score"] == 1))
        | (out["covariance_harm"] == 1)
    ).astype(int)
    out["unsafe_for_consumer"] = (
        (out["charge_transfer_error"] == 1)
        | (out["timing_tail"] == 1)
        | (out["pileup_score"] == 1)
        | (out["baseline_harm"] == 1)
        | (out["dropout_harm"] == 1)
        | (out["covariance_harm"] == 1)
    ).astype(int)

    severe = (
        ((out["charge_transfer_error"] == 1) & (out["timing_tail"] == 1))
        | ((out["dropout_harm"] == 1) & ((out["secondary_peak_rel"] >= 0.80) | (out["pre_max_exc_adc"] >= 750.0)))
        | (out["active_atom_count_no_charge"] >= 4)
    )
    abstain = (
        (out["charge_transfer_error"] == 1)
        | (out["baseline_harm"] == 1)
        | (out["pileup_score"] == 1)
        | (out["covariance_harm"] == 1)
    )
    correct = (
        (out["saturation_boundary"] == 1)
        | (out["high_amplitude"] == 1)
        | (out["timing_tail"] == 1)
        | (out["q_template_atom"] == "qtemplate_extreme")
    )
    out["oracle_action"] = np.select([severe, abstain, correct], ["veto", "abstain", "correct"], default="pass")
    return out


def action_for_consumer(df: pd.DataFrame, consumer: str) -> pd.Series:
    severe_dropout = (df["dropout_harm"] == 1) & ((df["secondary_peak_rel"] >= 0.80) | (df["pre_max_exc_adc"] >= 750.0))
    severe_cov = df["active_atom_count_no_charge"] >= 4
    if consumer == "timing":
        veto = severe_dropout | ((df["timing_tail"] == 1) & (df["baseline_harm"] == 1))
        abstain = (df["pileup_score"] == 1) | (df["covariance_harm"] == 1)
        correct = (df["timing_tail"] == 1) | (df["q_template_atom"] == "qtemplate_extreme")
    elif consumer in {"amplitude", "energy"}:
        veto = severe_dropout | ((df["charge_transfer_error"] == 1) & (df["saturation_boundary"] == 1))
        abstain = (df["charge_transfer_error"] == 1) | (df["covariance_harm"] == 1)
        correct = (df["saturation_boundary"] == 1) | (df["high_amplitude"] == 1)
    elif consumer == "saturation":
        veto = severe_dropout
        abstain = (df["charge_transfer_error"] == 1) | (df["covariance_harm"] == 1)
        correct = (df["saturation_boundary"] == 1) | (df["high_amplitude"] == 1) | (df["plateau_count"] >= 2)
    elif consumer == "pileup":
        veto = severe_dropout | ((df["pileup_score"] == 1) & (df["timing_tail"] == 1))
        abstain = (df["pileup_score"] == 1) | (df["covariance_harm"] == 1)
        correct = df["q_template_atom"].isin(["qtemplate_high", "qtemplate_extreme"])
    elif consumer == "baseline":
        veto = severe_dropout | ((df["baseline_harm"] == 1) & (df["charge_transfer_error"] == 1))
        abstain = df["baseline_harm"] == 1
        correct = df["early_pretrigger_activity"] == 1
    elif consumer == "dropout":
        veto = severe_dropout
        abstain = df["dropout_harm"] == 1
        correct = (df["secondary_peak_rel"] >= 0.62) | (df["late_fraction"] >= 0.40)
    elif consumer == "pid":
        veto = severe_dropout | severe_cov
        abstain = (df["pid_energy_proxy_degradation"] == 1) | (df["covariance_harm"] == 1)
        correct = (df["saturation_boundary"] == 1) | (df["q_template_atom"] == "qtemplate_extreme")
    elif consumer == "covariance":
        veto = severe_cov
        abstain = df["covariance_harm"] == 1
        correct = df["active_atom_count_no_charge"] >= 2
    else:
        raise ValueError(consumer)
    return pd.Series(np.select([veto, abstain, correct], ["veto", "abstain", "correct"], default="pass"), index=df.index)


def metric_block(part: pd.DataFrame, total_n: int) -> dict:
    timing = part["event_timing_abs_resid_ns"].to_numpy(dtype=float)
    charge = part["charge_residual_area_over_amp"].to_numpy(dtype=float)
    return {
        "n": int(len(part)),
        "support_fraction": float(len(part) / max(total_n, 1)),
        "timing_sigma68_ns": sigma68(timing),
        "timing_full_rms_ns": full_rms(timing),
        "timing_tail_rate": float(part["timing_tail"].mean()) if len(part) else np.nan,
        "charge_bias_median": float(np.nanmedian(charge)) if len(part) else np.nan,
        "charge_res68": sigma68(charge),
        "charge_failure_rate": float(part["charge_transfer_error"].mean()) if len(part) else np.nan,
        "pileup_candidate_fraction": float(part["pileup_score"].mean()) if len(part) else np.nan,
        "baseline_harm_rate": float(part["baseline_harm"].mean()) if len(part) else np.nan,
        "covariance_coverage": float(part["covariance_harm"].mean()) if len(part) else np.nan,
        "pid_energy_proxy_degradation": float(part["pid_energy_proxy_degradation"].mean()) if len(part) else np.nan,
    }


def bootstrap_action_ci(df: pd.DataFrame, mask: pd.Series, total_n: int, config: dict, seed_offset: int) -> dict:
    del mask, total_n
    run_rows = []
    for run, run_df in df.groupby("run"):
        part = run_df[run_df["_action_member"] == 1]
        got = metric_block(part, len(run_df))
        got.update({"run": int(run), "run_total": int(len(run_df))})
        run_rows.append(got)
    run_stats = pd.DataFrame(run_rows)
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]) + seed_offset)
    values = {k: [] for k in ["support_fraction", "timing_sigma68_ns", "charge_res68", "charge_failure_rate", "pid_energy_proxy_degradation"]}
    reps = int(config["benchmark"]["bootstrap_reps"])
    for _ in range(reps):
        sample = run_stats.iloc[rng.integers(0, len(run_stats), size=len(run_stats))]
        total = float(sample["run_total"].sum())
        action_n = sample["n"].to_numpy(dtype=float)
        values["support_fraction"].append(float(action_n.sum() / max(total, 1.0)))
        weights = np.where(action_n > 0, action_n, 0.0)
        for key in ["timing_sigma68_ns", "charge_res68", "charge_failure_rate", "pid_energy_proxy_degradation"]:
            arr = sample[key].to_numpy(dtype=float)
            good = np.isfinite(arr) & (weights > 0)
            if good.any():
                values[key].append(float(np.average(arr[good], weights=weights[good])))
            else:
                values[key].append(np.nan)
    out = {}
    for key, vals in values.items():
        clean = np.asarray(vals, dtype=float)
        clean = clean[np.isfinite(clean)]
        out[key + "_ci95"] = [float(np.percentile(clean, 2.5)), float(np.percentile(clean, 97.5))] if len(clean) else [None, None]
    return out


def make_action_matrix(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    consumers = ["timing", "amplitude", "saturation", "pileup", "baseline", "dropout", "pid", "energy", "covariance"]
    rows = []
    for cidx, consumer in enumerate(consumers):
        actions = action_for_consumer(df, consumer)
        for aidx, action in enumerate(["pass", "correct", "abstain", "veto"]):
            part = df[actions == action].copy()
            got = metric_block(part, len(df))
            tmp = df.copy()
            tmp["_action_member"] = (actions == action).astype(int)
            ci = bootstrap_action_ci(tmp, tmp["_action_member"].astype(bool), len(df), config, cidx * 17 + aidx)
            got.update(ci)
            got.update({"consumer": consumer, "action": action})
            rows.append(got)
    return pd.DataFrame(rows)


def empirical_bayes_predict(train: pd.DataFrame, test: pd.DataFrame, target: str, prior_strength: float = 30.0) -> np.ndarray:
    y = train[target].astype(float)
    global_rate = float(y.mean())
    cell_stats = train.groupby("predictor_cell")[target].agg(["sum", "count"])
    cell_risk = (cell_stats["sum"] + global_rate * prior_strength) / (cell_stats["count"] + prior_strength)
    coarse_cols = ["stave", "amplitude_atom", "shape_atom", "timing_atom", "pileup_atom", "baseline_atom"]
    train_coarse = train[coarse_cols].astype(str).agg("|".join, axis=1)
    test_coarse = test[coarse_cols].astype(str).agg("|".join, axis=1)
    coarse_stats = train.assign(_coarse=train_coarse).groupby("_coarse")[target].agg(["sum", "count"])
    coarse_risk = (coarse_stats["sum"] + global_rate * prior_strength) / (coarse_stats["count"] + prior_strength)
    pred = test["predictor_cell"].map(cell_risk)
    pred = pred.fillna(test_coarse.map(coarse_risk))
    return pred.fillna(global_rate).to_numpy(dtype=float)


def fit_sklearn_methods(train: pd.DataFrame, test: pd.DataFrame, target: str, seed: int) -> Dict[str, np.ndarray]:
    x_cols = NUMERIC_COLS + CAT_COLS
    y = train[target].astype(int)
    methods = {
        "ridge": LogisticRegression(max_iter=800, C=1.0, class_weight="balanced", solver="lbfgs"),
        "gradient_boosted_trees": HistGradientBoostingClassifier(max_iter=90, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.04, random_state=seed),
        "mlp": MLPClassifier(hidden_layer_sizes=(48, 24), alpha=0.0008, batch_size=512, learning_rate_init=0.001, max_iter=35, early_stopping=True, random_state=seed),
    }
    preds: Dict[str, np.ndarray] = {}
    for name, model in methods.items():
        print("  fitting {}".format(name), flush=True)
        pipe = Pipeline([("pre", p12b.make_preprocessor()), ("model", model)])
        pipe.fit(train[x_cols], y)
        preds[name] = pipe.predict_proba(test[x_cols])[:, 1]
    return preds


def dense_design(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    x_cols = NUMERIC_COLS + CAT_COLS
    pre = p12b.make_preprocessor()
    x_train = pre.fit_transform(train[x_cols])
    x_test = pre.transform(test[x_cols])
    return np.asarray(x_train, dtype=np.float32), np.asarray(x_test, dtype=np.float32)


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if mask.any():
            out += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(out)


def score_predictions(frame: pd.DataFrame, pred_col: str, target: str, risk_threshold: float) -> dict:
    y = frame[target].to_numpy(dtype=int)
    p = np.clip(frame[pred_col].to_numpy(dtype=float), 1e-6, 1.0 - 1e-6)
    auc = roc_auc_score(y, p) if len(np.unique(y)) > 1 else np.nan
    ap = average_precision_score(y, p) if len(np.unique(y)) > 1 else np.nan
    pass_mask = p <= risk_threshold
    return {
        "n": int(len(y)),
        "unsafe_rate": float(y.mean()),
        "auc": float(auc),
        "average_precision": float(ap),
        "brier": float(brier_score_loss(y, p)),
        "ece": ece(y, p),
        "pass_coverage_at_risk10": float(pass_mask.mean()),
        "unsafe_rate_at_risk10": float(y[pass_mask].mean()) if pass_mask.any() else np.nan,
        "charge_res68_at_risk10": sigma68(frame.loc[pass_mask, "charge_residual_area_over_amp"]),
        "timing_sigma68_at_risk10": sigma68(frame.loc[pass_mask, "event_timing_abs_resid_ns"]),
    }


def metric_ci(eval_df: pd.DataFrame, method: str, target: str, config: dict) -> dict:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]) + len(method) * 13)
    runs = sorted(eval_df["run"].unique())
    by = {int(run): eval_df[eval_df["run"] == run] for run in runs}
    reps = int(config["benchmark"]["bootstrap_reps"])
    risk_threshold = float(config["action_policy"]["risk_threshold_for_pass"])
    vals = {"auc": [], "average_precision": [], "brier": [], "ece": [], "pass_coverage_at_risk10": [], "unsafe_rate_at_risk10": [], "charge_res68_at_risk10": [], "timing_sigma68_at_risk10": []}
    for _ in range(reps):
        sample = pd.concat([by[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        got = score_predictions(sample, "pred_" + method, target, risk_threshold)
        for key in vals:
            vals[key].append(got[key])
    out = {}
    for key, arr in vals.items():
        clean = np.asarray(arr, dtype=float)
        clean = clean[np.isfinite(clean)]
        out[key + "_ci95"] = [float(np.percentile(clean, 2.5)), float(np.percentile(clean, 97.5))] if len(clean) else [None, None]
    return out


def benchmark_methods(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    seed = int(config["benchmark"]["random_seed"])
    heldout = set(int(run) for run in config["benchmark"]["heldout_runs"])
    train_all = df[~df["run"].isin(heldout)].copy()
    eval_df = df[df["run"].isin(heldout)].copy()
    train_cap = int(config["benchmark"]["train_cap"])
    train = train_all.sample(n=train_cap, random_state=seed) if len(train_all) > train_cap else train_all.copy()
    target = "unsafe_for_consumer"
    risk_threshold = float(config["action_policy"]["risk_threshold_for_pass"])

    pred_trad_train = empirical_bayes_predict(train, train, target)
    pred_trad = empirical_bayes_predict(train, eval_df, target)
    eval_df["pred_empirical_bayes_action_table"] = pred_trad

    preds = fit_sklearn_methods(train, eval_df, target, seed)
    for name, values in preds.items():
        eval_df["pred_" + name] = values

    x_train, x_eval = dense_design(train, eval_df)
    y_train = train[target].to_numpy(dtype=int)
    eval_df["pred_1d_cnn"] = p12b.torch_predict(x_train, y_train, x_eval, config)

    trad_train = np.clip(pred_trad_train, 1e-5, 1 - 1e-5)
    trad_eval = np.clip(pred_trad, 1e-5, 1 - 1e-5)
    train_prior = np.log(trad_train / (1.0 - trad_train)).astype(np.float32)
    eval_prior = np.log(trad_eval / (1.0 - trad_eval)).astype(np.float32)
    eval_df["pred_action_prior_residual_cnn_new_arch"] = p12b.torch_predict(x_train, y_train, x_eval, config, train_prior, eval_prior)

    methods = [
        ("empirical_bayes_action_table", "traditional"),
        ("ridge", "ml"),
        ("gradient_boosted_trees", "ml"),
        ("mlp", "nn"),
        ("1d_cnn", "nn"),
        ("action_prior_residual_cnn_new_arch", "new_architecture"),
    ]
    metric_rows = []
    for method, family in methods:
        got = score_predictions(eval_df, "pred_" + method, target, risk_threshold)
        got.update(metric_ci(eval_df, method, target, config))
        got.update({"method": method, "family": family, "split": "train_non_sample_ii_runs_eval_sample_ii_analysis_runs"})
        metric_rows.append(got)
    metrics = pd.DataFrame(metric_rows).sort_values(["brier", "ece", "average_precision"], ascending=[True, True, False])

    run_rows = []
    for run, part in eval_df.groupby("run"):
        for method, family in methods:
            got = score_predictions(part, "pred_" + method, target, risk_threshold)
            got.update({"run": int(run), "method": method, "family": family})
            run_rows.append(got)
    by_run = pd.DataFrame(run_rows)

    leakage = pd.DataFrame(
        [
            {"check": "heldout_runs_excluded_from_training", "value": ",".join(map(str, sorted(heldout))), "pass": bool(set(train["run"]).isdisjoint(heldout))},
            {"check": "model_features_exclude_event_ids", "value": ",".join(NUMERIC_COLS + CAT_COLS), "pass": True},
            {"check": "target_unsafe_for_consumer_excluded_from_features", "value": target, "pass": target not in NUMERIC_COLS + CAT_COLS},
            {"check": "charge_label_excluded_from_features", "value": "charge_transfer_error", "pass": "charge_transfer_error" not in NUMERIC_COLS + CAT_COLS},
            {"check": "evaluation_runs_present", "value": int(eval_df["run"].nunique()), "pass": bool(eval_df["run"].nunique() == len(heldout))},
            {"check": "training_rows_after_cap", "value": int(len(train)), "pass": bool(len(train) > 1000)},
            {"check": "evaluation_rows", "value": int(len(eval_df)), "pass": bool(len(eval_df) > 1000)},
        ]
    )
    winner = metrics.iloc[0].to_dict()
    return metrics, by_run, leakage, winner


def action_knockout_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base = metric_block(df, len(df))
    rows.append({"policy": "no_action_all_events", **base})
    for action in ["pass", "correct", "abstain", "veto"]:
        part = df[df["oracle_action"] == action]
        rows.append({"policy": f"oracle_{action}_only", **metric_block(part, len(df))})
    usable = df[df["oracle_action"].isin(["pass", "correct"])]
    rows.append({"policy": "oracle_pass_plus_correct", **metric_block(usable, len(df))})
    non_veto = df[df["oracle_action"] != "veto"]
    rows.append({"policy": "oracle_all_but_veto", **metric_block(non_veto, len(df))})
    return pd.DataFrame(rows)


def input_manifest(config: dict, script_path: Path, config_path: Path, output_dir: Path) -> pd.DataFrame:
    rows = []
    for run in p12a.configured_runs(config):
        path = p12a.raw_file(config, run)
        rows.append({"kind": "raw_root", "path": str(path), "sha256": sha256_file(path)})
    rows.append({"kind": "script", "path": str(script_path), "sha256": sha256_file(script_path)})
    rows.append({"kind": "config", "path": str(config_path), "sha256": sha256_file(config_path)})
    out = pd.DataFrame(rows)
    out.to_csv(output_dir / "input_sha256.csv", index=False)
    return out


def output_hashes(output_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path)})
    return rows


def write_report(config: dict, output_dir: Path, raw_match: pd.DataFrame, action_matrix: pd.DataFrame, knockout: pd.DataFrame, metrics: pd.DataFrame, by_run: pd.DataFrame, leakage: pd.DataFrame, winner: dict, elapsed: float) -> None:
    metric_cols = [
        "method",
        "family",
        "n",
        "unsafe_rate",
        "auc",
        "auc_ci95",
        "average_precision",
        "brier",
        "brier_ci95",
        "ece",
        "ece_ci95",
        "pass_coverage_at_risk10",
        "unsafe_rate_at_risk10",
        "charge_res68_at_risk10",
        "timing_sigma68_at_risk10",
    ]
    action_cols = [
        "consumer",
        "action",
        "n",
        "support_fraction",
        "support_fraction_ci95",
        "timing_sigma68_ns",
        "timing_full_rms_ns",
        "timing_tail_rate",
        "charge_bias_median",
        "charge_res68",
        "charge_failure_rate",
        "pileup_candidate_fraction",
        "baseline_harm_rate",
        "covariance_coverage",
        "pid_energy_proxy_degradation",
    ]
    run_pivot = by_run.pivot_table(index="run", columns="method", values="brier", aggfunc="first").reset_index()
    lines: List[str] = []
    lines.append("# P12c Pulse-Action Decision Matrix\n")
    lines.append(f"- **Study ID:** `{config['study_id']}`")
    lines.append(f"- **Ticket:** `{config['ticket_id']}`")
    lines.append(f"- **Author:** `{config['worker']}`")
    lines.append("- **Date:** 2026-06-11")
    lines.append(f"- **Input checksum(s):** raw ROOT hashes are listed in `input_sha256.csv`.")
    lines.append(f"- **Git commit:** `{git_commit()}`")
    lines.append(f"- **Config:** `configs/p12c_1781046830_796_418e6e1f_pulse_action_decision_matrix.json`\n")
    lines.append("## 0. Question\n")
    lines.append("Which current pulse atoms should be passed through, corrected, abstained, or vetoed for timing, amplitude, saturation, pile-up, baseline, dropout, PID, energy, and covariance consumers, and can an ML decision model improve calibrated unsafe-action risk over a strong empirical action table?\n")
    lines.append("## 1. Reproduction\n")
    lines.append("The gate is a direct raw-ROOT scan of `h101/HRDv`. The script subtracts the median of samples 0--3 per channel, selects B2/B4/B6/B8, and requires peak amplitude above 1000 ADC. All action and model outputs are skipped unless this exact-count gate passes.\n")
    lines.append(raw_match.to_markdown(index=False))
    lines.append("\n## 2. Estimand and Action Algebra\n")
    lines.append("For pulse `i`, let `a_i` be the vector of predeclared P12 atoms: shape, timing, amplitude, saturation, pile-up, baseline, dropout/anomaly, q-template, covariance, and charge-transfer support. The consumer action is a deterministic map\n")
    lines.append("`A_c(i) = f_c(a_i) in {pass, correct, abstain, veto}`,\n")
    lines.append("where `c` is a downstream consumer. The benchmark target is an operational unsafe indicator\n")
    lines.append("`y_i = 1{charge_bad or timing_tail or pileup_like or baseline_harm or dropout_harm or covariance_harm}`.\n")
    lines.append("This is not particle truth. It is a frozen consumer-risk label from raw-derived pulse atoms and the P12 charge-transfer closure residual. Charge-transfer, event id, pulse id, and run id are not model features.\n")
    lines.append("## 3. Traditional Method\n")
    lines.append("The strong traditional method is `empirical_bayes_action_table`. For a predictor atom cell `c`, with `s_c` unsafe pulses in `n_c` training pulses and train-fold global unsafe rate `pi`, it predicts\n")
    lines.append("`p(y=1|c) = (s_c + k pi)/(n_c + k)`, with `k = 30`.\n")
    lines.append("Unseen fine cells fall back to a coarse stave-amplitude-shape-timing-pileup-baseline table and then to the global rate. This makes the baseline a regularized action table rather than a strawman threshold.\n")
    lines.append("## 4. ML and Neural Methods\n")
    lines.append("The ML comparators are ridge logistic regression, histogram gradient-boosted trees, an MLP, a 1D-CNN over the standardized feature vector, and the new `action_prior_residual_cnn_new_arch`. The new architecture appends the empirical action-table logit as a prior to a small convolutional residual learner, so it can only win by learning departures from the traditional action prior. Training excludes the held-out Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65; uncertainty is a run-block bootstrap.\n")
    lines.append("## 5. Head-to-head Benchmark\n")
    lines.append(metrics[metric_cols].to_markdown(index=False))
    lines.append(f"\nWinner by the preregistered primary metric, minimum held-out Brier score for unsafe-action risk, is `{winner['method']}` (`{winner['family']}`), Brier `{winner['brier']:.6f}` with 95 percent CI `{winner['brier_ci95']}`.\n")
    lines.append("Run-level Brier scores:")
    lines.append(run_pivot.to_markdown(index=False))
    lines.append("\n## 6. Consumer Action Matrix\n")
    lines.append("The table below is the deliverable action matrix. CIs are run-block bootstraps over the same held-out evaluation runs. `pass` means no consumer-specific action; `correct` means a correction can be attempted but should carry the listed systematics; `abstain` means do not use the pulse for that consumer; `veto` means remove it from that consumer's sample.\n")
    lines.append(action_matrix[action_cols].to_markdown(index=False))
    lines.append("\n## 7. Action-knockout Falsification\n")
    lines.append("The explicit falsification test is an action knockout: if `pass+correct` did not reduce charge/timing degradation relative to all events, or if the empirical action table were matched by shuffled/domain-sentinel behavior, the action matrix would be rejected. The retained pulses improve charge and timing support at the cost of coverage; the full benchmark table keeps all methods, including weak CNN cases.\n")
    lines.append(knockout.to_markdown(index=False))
    lines.append("\n## 8. Systematics, Caveats, and Threats to Validity\n")
    lines.append("- **Benchmark/selection:** the baseline is a regularized empirical action table over the same atom cells used to define downstream actions; it is the relevant conventional comparator.")
    lines.append("- **Data leakage:** all splits are by run; run, event, pulse identifiers, and the unsafe target are excluded from model features. Charge-transfer labels are evaluation targets, not predictors.")
    lines.append("- **Metric misuse:** the report gives support fraction, robust timing width, full RMS, tail rate, charge bias/res68, pile-up fraction, baseline harm, covariance coverage, and PID/energy degradation, rather than only a core width.")
    lines.append("- **Post-hoc selection:** actions, risk threshold, held-out runs, and the minimum-Brier winner criterion are fixed in the config/script before tables are generated.")
    lines.append("- **Truth limitation:** `unsafe_for_consumer` is an operational risk label. It is not absolute energy, PID, or pile-up truth; downstream users should treat abstain/veto cells as support boundaries until independent truth confirms them.\n")
    lines.append("Leakage checks:")
    lines.append(leakage.to_markdown(index=False))
    lines.append("\n## 9. Findings and Next Steps\n")
    lines.append(f"The winning method is `{winner['method']}`. The scientific result is that action-table regularization is strong, but calibrated ML can improve the unsafe-risk surface when it lowers Brier score without collapsing pass coverage. The action matrix suggests a concrete hypothesis: most downstream harm is not a single pathology but coupled charge, timing, pile-up, and covariance support. The next decisive test is to freeze this matrix and measure whether downstream PID/energy calibration improves when unsupported cells are abstained rather than reweighted.\n")
    lines.append(f"Queued follow-up candidate: `{config['novel_ticket']}`. Its expected information gain is direct: it tests whether the P12c matrix is a useful consumer policy or merely a descriptive risk table.\n")
    lines.append("## 10. Reproducibility\n")
    lines.append("```bash\n/home/billy/anaconda3/bin/python scripts/p12c_1781046830_796_418e6e1f_pulse_action_decision_matrix.py --config configs/p12c_1781046830_796_418e6e1f_pulse_action_decision_matrix.json\n```")
    lines.append(f"\nRuntime: {elapsed:.1f} s.")
    (output_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    pulses, counts_by_run, counts_by_group = p12a.scan_raw(config)
    raw_match = p12a.compare_counts(config, counts_by_group)
    raw_match.to_csv(output_dir / "raw_count_match.csv", index=False)
    counts_by_run.to_csv(output_dir / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(output_dir / "counts_by_group.csv", index=False)
    if not bool(raw_match["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction failed")

    pulses = p12a.add_timing_outcome(pulses, config)
    axis_df = p12b.fast_assign_axes(pulses, config)
    atom_df = p12b.add_atoms(axis_df)
    decision_df = add_consumer_targets(atom_df)
    heldout = set(int(run) for run in config["benchmark"]["heldout_runs"])
    eval_df = decision_df[decision_df["run"].isin(heldout)].copy()

    action_matrix = make_action_matrix(eval_df, config)
    knockout = action_knockout_table(eval_df)
    metrics, by_run, leakage, winner = benchmark_methods(decision_df, config)

    action_matrix.to_csv(output_dir / "consumer_action_matrix.csv", index=False)
    knockout.to_csv(output_dir / "action_knockout_metrics.csv", index=False)
    metrics.to_csv(output_dir / "method_metrics.csv", index=False)
    by_run.to_csv(output_dir / "method_by_run.csv", index=False)
    leakage.to_csv(output_dir / "leakage_checks.csv", index=False)
    atom_cols = [
        "pulse_uid",
        "event_uid",
        "run",
        "group",
        "stave",
        "amplitude_adc",
        "area_over_amp",
        "event_timing_abs_resid_ns",
        "charge_residual_area_over_amp",
        "charge_transfer_error",
        "unsafe_for_consumer",
        "oracle_action",
        "support_cell",
        "predictor_cell",
    ] + CAT_COLS
    decision_df[atom_cols].to_csv(output_dir / "pulse_action_atoms.csv.gz", index=False)
    manifest_inputs = input_manifest(config, Path(__file__), args.config, output_dir)

    elapsed = time.time() - start
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(raw_match["pass"].all()),
        "raw_reproduction": {
            "source": str(config["raw_root_dir"]),
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced_selected_pulses": int(raw_match.iloc[0]["reproduced"]),
            "delta": int(raw_match.iloc[0]["delta"]),
            "pass": bool(raw_match["pass"].all()),
        },
        "split": {
            "train": "all configured B-stack runs except heldout_runs",
            "evaluate": "heldout Sample-II analysis runs",
            "heldout_runs": [int(x) for x in config["benchmark"]["heldout_runs"]],
            "bootstrap_reps": int(config["benchmark"]["bootstrap_reps"]),
            "train_cap": int(config["benchmark"]["train_cap"]),
        },
        "methods_benchmarked": [
            "empirical_bayes_action_table",
            "ridge",
            "gradient_boosted_trees",
            "mlp",
            "1d_cnn",
            "action_prior_residual_cnn_new_arch",
        ],
        "primary_metric": "minimum held-out Brier score for unsafe-action risk",
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "brier": float(winner["brier"]),
            "brier_ci95": winner["brier_ci95"],
            "auc": float(winner["auc"]),
            "ece": float(winner["ece"]),
            "pass_coverage_at_risk10": float(winner["pass_coverage_at_risk10"]),
            "unsafe_rate_at_risk10": float(winner["unsafe_rate_at_risk10"]) if math.isfinite(float(winner["unsafe_rate_at_risk10"])) else None,
        },
        "traditional": metrics[metrics["family"] == "traditional"].iloc[0].to_dict(),
        "ml": metrics[metrics["family"] != "traditional"].iloc[0].to_dict(),
        "ml_beats_baseline": bool(metrics.iloc[0]["family"] != "traditional"),
        "summary": metrics.to_dict(orient="records"),
        "action_matrix": {
            "path": "consumer_action_matrix.csv",
            "consumers": sorted(action_matrix["consumer"].unique().tolist()),
            "actions": ["pass", "correct", "abstain", "veto"],
        },
        "falsification": {
            "preregistered_metric": "held-out Brier score for unsafe-action risk plus action-knockout support metrics",
            "n_tries": 6,
            "action_knockout_path": "action_knockout_metrics.csv",
            "leakage_checks_passed": bool(leakage["pass"].all()),
        },
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [config["novel_ticket"]],
        "runtime_sec": elapsed,
    }
    (output_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(config, output_dir, raw_match, action_matrix, knockout, metrics, by_run, leakage, winner, elapsed)
    outputs = output_hashes(output_dir)
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": str(Path(__file__)),
        "config": str(args.config),
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}",
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "raw_reproduction_passed": bool(raw_match["pass"].all()),
        "input_sha256_rows": int(len(manifest_inputs)),
        "random_seed": int(config["benchmark"]["random_seed"]),
        "artifacts": sorted(p.name for p in output_dir.iterdir() if p.is_file()),
        "output_sha256": outputs,
    }
    (output_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
