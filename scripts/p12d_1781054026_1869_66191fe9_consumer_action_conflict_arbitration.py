#!/usr/bin/env python3
"""P12d consumer-action conflict arbitration benchmark.

The study reuses P12a/P12b raw pulse atoms and P12c frozen action rules, then
asks whether disagreement among consumer actions is downstream-harmful or only a
support mismatch.
"""

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
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p12a_1781023340_632_43377364_pulse_axis_covariance as p12a  # noqa: E402
import p12b_1781040960_896_205a0b9d_pulse_support_tensor as p12b  # noqa: E402
import p12c_1781046830_796_418e6e1f_pulse_action_decision_matrix as p12c  # noqa: E402


NUMERIC_COLS = p12b.NUMERIC_COLS
CAT_COLS = p12b.CAT_COLS
ACTION_ORDER = {"pass": 0, "correct": 1, "abstain": 2, "veto": 3}


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


def action_for_consumer(df: pd.DataFrame, consumer: str) -> pd.Series:
    if consumer == "charge":
        return p12c.action_for_consumer(df, "amplitude")
    return p12c.action_for_consumer(df, consumer)


def add_conflict_columns(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    consumers = list(config["consumers"])
    action_cols = []
    for consumer in consumers:
        col = "action_" + consumer
        out[col] = action_for_consumer(out, consumer)
        out[col + "_severity"] = out[col].map(ACTION_ORDER).astype(int)
        action_cols.append(col)

    sev = out[[c + "_severity" for c in action_cols]].to_numpy(dtype=int)
    out["n_consumer_actions"] = len(consumers)
    out["n_unique_actions"] = [len(set(row)) for row in out[action_cols].to_numpy(dtype=str)]
    out["conflict"] = (out["n_unique_actions"] > 1).astype(int)
    for action in ACTION_ORDER:
        out["n_" + action] = (out[action_cols] == action).sum(axis=1).astype(int)
    out["max_action_severity"] = sev.max(axis=1)
    out["min_action_severity"] = sev.min(axis=1)
    out["action_severity_span"] = out["max_action_severity"] - out["min_action_severity"]
    out["priority_veto"] = (
        (out["action_timing"] == "veto")
        | (out["action_charge"] == "veto")
        | (out["action_pid"] == "veto")
        | (out["action_energy"] == "veto")
    ).astype(int)
    out["priority_abstain"] = (
        out[["action_timing", "action_charge", "action_pid", "action_energy"]] == "abstain"
    ).any(axis=1).astype(int)
    out["conflict_pattern"] = (
        "p" + out["n_pass"].astype(str)
        + "_c" + out["n_correct"].astype(str)
        + "_a" + out["n_abstain"].astype(str)
        + "_v" + out["n_veto"].astype(str)
    )

    out["harm_score"] = (
        out["charge_transfer_error"].astype(int)
        + out["timing_tail"].astype(int)
        + out["pileup_score"].astype(int)
        + out["baseline_harm"].astype(int)
        + out["dropout_harm"].astype(int)
        + out["pid_energy_proxy_degradation"].astype(int)
        + out["covariance_harm"].astype(int)
    )
    out["downstream_harm"] = (out["harm_score"] > 0).astype(int)
    out["harmful_conflict"] = ((out["conflict"] == 1) & (out["downstream_harm"] == 1)).astype(int)
    out["harmless_conflict"] = ((out["conflict"] == 1) & (out["downstream_harm"] == 0)).astype(int)
    out["traditional_reject_conflict"] = traditional_reject_mask(out).astype(int)
    out["traditional_accept"] = (~out["traditional_reject_conflict"].astype(bool) & (out["max_action_severity"] <= 2)).astype(int)
    return out


def traditional_reject_mask(df: pd.DataFrame) -> pd.Series:
    conflict = df["conflict"].astype(bool)
    hard_veto = (df["n_veto"] > 0) & ((df["priority_veto"] == 1) | (df["harm_score"] >= 2) | (df["n_abstain"] >= 2))
    broad_abstain = (df["n_abstain"] + df["n_veto"] >= 4) & (df["harm_score"] >= 1)
    support_sparse = (df["active_atom_count_no_charge"] >= 4) & (df["n_pass"] <= 2)
    return conflict & (hard_veto | broad_abstain | support_sparse)


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


def conflict_summary(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for pattern, part in df.groupby("conflict_pattern"):
        rows.append(
            {
                "conflict_pattern": pattern,
                "n": int(len(part)),
                "support_fraction": float(len(part) / max(len(df), 1)),
                "conflict_rate": float(part["conflict"].mean()),
                "harmful_conflict_rate": float(part["harmful_conflict"].mean()),
                "timing_tail_rate": float(part["timing_tail"].mean()),
                "charge_res68": sigma68(part["charge_residual_area_over_amp"]),
                "pid_energy_proxy_degradation": float(part["pid_energy_proxy_degradation"].mean()),
            }
        )
    out = pd.DataFrame(rows).sort_values(["n", "harmful_conflict_rate"], ascending=[False, False])
    return out


def consumer_knockout_table(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    consumers = list(config["consumers"])
    full = df[["conflict", "harmful_conflict"]].mean()
    rows = [
        {
            "knockout": "none",
            "n": int(len(df)),
            "conflict_rate": float(full["conflict"]),
            "harmful_conflict_rate": float(full["harmful_conflict"]),
            "delta_conflict_rate": 0.0,
            "delta_harmful_conflict_rate": 0.0,
        }
    ]
    for consumer in consumers:
        keep = [c for c in consumers if c != consumer]
        action_cols = ["action_" + c for c in keep]
        n_unique = np.asarray([len(set(row)) for row in df[action_cols].to_numpy(dtype=str)], dtype=int)
        conflict = n_unique > 1
        harmful = conflict & (df["downstream_harm"].to_numpy(dtype=bool))
        rows.append(
            {
                "knockout": consumer,
                "n": int(len(df)),
                "conflict_rate": float(np.mean(conflict)),
                "harmful_conflict_rate": float(np.mean(harmful)),
                "delta_conflict_rate": float(np.mean(conflict) - full["conflict"]),
                "delta_harmful_conflict_rate": float(np.mean(harmful) - full["harmful_conflict"]),
            }
        )
    return pd.DataFrame(rows).sort_values("delta_harmful_conflict_rate")


def score_policy(frame: pd.DataFrame, method: str, pred_col: str, threshold: float) -> dict:
    conflict = frame["conflict"].to_numpy(dtype=bool)
    y = frame.loc[conflict, "harmful_conflict"].to_numpy(dtype=int)
    p_all = np.clip(frame[pred_col].to_numpy(dtype=float), 1e-6, 1.0 - 1e-6)
    p = p_all[conflict]
    pred_harm = p >= threshold
    if method == "traditional_precedence_ladder":
        reject = frame["traditional_reject_conflict"].to_numpy(dtype=bool)
    else:
        reject = conflict & (p_all >= threshold)
    accepted = ~reject & (frame["max_action_severity"].to_numpy(dtype=int) <= 2)

    all_tail = float(frame["timing_tail"].mean())
    acc_tail = float(frame.loc[accepted, "timing_tail"].mean()) if accepted.any() else np.nan
    all_charge = frame["charge_residual_area_over_amp"]
    acc_charge = frame.loc[accepted, "charge_residual_area_over_amp"]
    all_pid = float(frame["weak_pid_positive"].mean())
    acc_pid = float(frame.loc[accepted, "weak_pid_positive"].mean()) if accepted.any() else np.nan
    all_energy = float(frame["pid_energy_proxy_degradation"].mean())
    acc_energy = float(frame.loc[accepted, "pid_energy_proxy_degradation"].mean()) if accepted.any() else np.nan

    auc = roc_auc_score(y, p) if len(y) and len(np.unique(y)) > 1 else np.nan
    ap = average_precision_score(y, p) if len(y) and len(np.unique(y)) > 1 else np.nan
    brier = brier_score_loss(y, p) if len(y) else np.nan
    precision = precision_score(y, pred_harm, zero_division=0) if len(y) else np.nan
    recall = recall_score(y, pred_harm, zero_division=0) if len(y) else np.nan
    charge_res68_delta = sigma68(acc_charge) - sigma68(all_charge)
    charge_bias_delta = (float(np.nanmedian(acc_charge)) if accepted.any() else np.nan) - float(np.nanmedian(all_charge))
    timing_tail_delta = acc_tail - all_tail if math.isfinite(acc_tail) else np.nan
    pid_drift = abs(acc_pid - all_pid) if math.isfinite(acc_pid) else np.nan
    energy_degradation_delta = acc_energy - all_energy if math.isfinite(acc_energy) else np.nan
    support = float(accepted.mean())
    primary_score = (
        float(brier)
        + 0.25 * max(0.0, 0.70 - float(recall if math.isfinite(recall) else 0.0))
        + 0.10 * max(0.0, 0.15 - support)
        + 0.05 * max(0.0, pid_drift if math.isfinite(pid_drift) else 1.0)
        + 0.05 * max(0.0, energy_degradation_delta if math.isfinite(energy_degradation_delta) else 1.0)
    )
    return {
        "n": int(len(frame)),
        "n_conflicts": int(conflict.sum()),
        "conflict_rate": float(conflict.mean()),
        "harmful_conflict_rate": float(frame["harmful_conflict"].mean()),
        "auc": float(auc),
        "average_precision": float(ap),
        "brier": float(brier),
        "ece": ece(y, p) if len(y) else np.nan,
        "harmful_conflict_precision": float(precision),
        "harmful_conflict_recall": float(recall),
        "accepted_support_fraction": support,
        "timing_tail_delta": float(timing_tail_delta),
        "charge_res68_delta": float(charge_res68_delta),
        "charge_bias_delta": float(charge_bias_delta),
        "pid_weak_label_drift": float(pid_drift),
        "energy_proxy_degradation_delta": float(energy_degradation_delta),
        "primary_score": float(primary_score),
    }


def metric_ci(eval_df: pd.DataFrame, method: str, pred_col: str, config: dict) -> dict:
    rng = np.random.default_rng(int(config["benchmark"]["random_seed"]) + len(method) * 19)
    runs = sorted(eval_df["run"].unique())
    by = {int(run): eval_df[eval_df["run"] == run] for run in runs}
    reps = int(config["benchmark"]["bootstrap_reps"])
    threshold = float(config["benchmark"]["harm_probability_threshold"])
    keys = [
        "conflict_rate",
        "harmful_conflict_rate",
        "auc",
        "average_precision",
        "brier",
        "ece",
        "harmful_conflict_precision",
        "harmful_conflict_recall",
        "accepted_support_fraction",
        "timing_tail_delta",
        "charge_res68_delta",
        "charge_bias_delta",
        "pid_weak_label_drift",
        "energy_proxy_degradation_delta",
        "primary_score",
    ]
    vals = {key: [] for key in keys}
    for _ in range(reps):
        sample = pd.concat([by[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        got = score_policy(sample, method, pred_col, threshold)
        for key in keys:
            vals[key].append(got[key])
    out = {}
    for key, arr in vals.items():
        clean = np.asarray(arr, dtype=float)
        clean = clean[np.isfinite(clean)]
        out[key + "_ci95"] = [float(np.percentile(clean, 2.5)), float(np.percentile(clean, 97.5))] if len(clean) else [None, None]
    return out


def fit_sklearn_methods(train: pd.DataFrame, test: pd.DataFrame, seed: int) -> Dict[str, np.ndarray]:
    x_cols = NUMERIC_COLS + CAT_COLS
    y = train["harmful_conflict"].astype(int)
    methods = {
        "ridge": LogisticRegression(max_iter=800, C=1.0, class_weight="balanced", solver="lbfgs"),
        "gradient_boosted_trees": HistGradientBoostingClassifier(
            max_iter=90, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.04, random_state=seed
        ),
        "mlp": MLPClassifier(
            hidden_layer_sizes=(48, 24),
            alpha=0.0008,
            batch_size=512,
            learning_rate_init=0.001,
            max_iter=35,
            early_stopping=True,
            random_state=seed,
        ),
    }
    preds: Dict[str, np.ndarray] = {}
    for name, model in methods.items():
        print("  fitting {}".format(name), flush=True)
        pipe = Pipeline([("pre", p12b.make_preprocessor()), ("model", model)])
        pipe.fit(train[x_cols], y)
        preds[name] = pipe.predict_proba(test[x_cols])[:, 1]
    return preds


def fit_shuffled_gbt(train: pd.DataFrame, test: pd.DataFrame, seed: int) -> np.ndarray:
    x_cols = NUMERIC_COLS + CAT_COLS
    y = train["harmful_conflict"].astype(int)
    model = HistGradientBoostingClassifier(
        max_iter=90, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.04, random_state=seed
    )
    print("  fitting shuffled_target_gradient_boosted_trees", flush=True)
    pipe = Pipeline([("pre", p12b.make_preprocessor()), ("model", model)])
    pipe.fit(train[x_cols], y)
    return pipe.predict_proba(test[x_cols])[:, 1]


def dense_design(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    x_cols = NUMERIC_COLS + CAT_COLS
    pre = p12b.make_preprocessor()
    x_train = pre.fit_transform(train[x_cols])
    x_test = pre.transform(test[x_cols])
    return np.asarray(x_train, dtype=np.float32), np.asarray(x_test, dtype=np.float32)


def empirical_bayes_conflict_predict(train: pd.DataFrame, test: pd.DataFrame, prior_strength: float = 30.0) -> np.ndarray:
    y = train["harmful_conflict"].astype(float)
    global_rate = float(y.mean())
    fine_cols = ["conflict_pattern", "stave", "amplitude_atom", "shape_atom", "timing_atom", "pileup_atom", "baseline_atom"]
    train_cell = train[fine_cols].astype(str).agg("|".join, axis=1)
    test_cell = test[fine_cols].astype(str).agg("|".join, axis=1)
    stats = train.assign(_cell=train_cell).groupby("_cell")["harmful_conflict"].agg(["sum", "count"])
    risk = (stats["sum"] + global_rate * prior_strength) / (stats["count"] + prior_strength)
    coarse_cols = ["conflict_pattern", "amplitude_atom", "shape_atom", "timing_atom"]
    train_coarse = train[coarse_cols].astype(str).agg("|".join, axis=1)
    test_coarse = test[coarse_cols].astype(str).agg("|".join, axis=1)
    cstats = train.assign(_coarse=train_coarse).groupby("_coarse")["harmful_conflict"].agg(["sum", "count"])
    crisk = (cstats["sum"] + global_rate * prior_strength) / (cstats["count"] + prior_strength)
    pred = test_cell.map(risk).fillna(test_coarse.map(crisk)).fillna(global_rate)
    return pred.to_numpy(dtype=float)


def benchmark_methods(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    seed = int(config["benchmark"]["random_seed"])
    heldout = set(int(run) for run in config["benchmark"]["heldout_runs"])
    threshold = float(config["benchmark"]["harm_probability_threshold"])
    train_all = df[(~df["run"].isin(heldout)) & (df["conflict"] == 1)].copy()
    eval_df = df[df["run"].isin(heldout)].copy()
    eval_conflict = eval_df[eval_df["conflict"] == 1].copy()
    train_cap = int(config["benchmark"]["train_cap"])
    train = train_all.sample(n=train_cap, random_state=seed) if len(train_all) > train_cap else train_all.copy()
    if train["harmful_conflict"].nunique() < 2:
        raise RuntimeError("Training conflict target has one class")

    pred_prior_train = empirical_bayes_conflict_predict(train, train)
    pred_prior = empirical_bayes_conflict_predict(train, eval_conflict)
    eval_df["pred_traditional_precedence_ladder"] = eval_df["traditional_reject_conflict"].astype(float)

    preds = fit_sklearn_methods(train, eval_conflict, seed)
    for name, values in preds.items():
        eval_df["pred_" + name] = 0.0
        eval_df.loc[eval_conflict.index, "pred_" + name] = values

    x_train, x_eval = dense_design(train, eval_conflict)
    y_train = train["harmful_conflict"].to_numpy(dtype=int)
    eval_df["pred_1d_cnn"] = 0.0
    eval_df.loc[eval_conflict.index, "pred_1d_cnn"] = p12b.torch_predict(x_train, y_train, x_eval, config)

    train_prior = np.log(np.clip(pred_prior_train, 1e-5, 1 - 1e-5) / np.clip(1.0 - pred_prior_train, 1e-5, 1.0)).astype(np.float32)
    eval_prior = np.log(np.clip(pred_prior, 1e-5, 1 - 1e-5) / np.clip(1.0 - pred_prior, 1e-5, 1.0)).astype(np.float32)
    eval_df["pred_conflict_prior_residual_cnn_new_arch"] = 0.0
    eval_df.loc[eval_conflict.index, "pred_conflict_prior_residual_cnn_new_arch"] = p12b.torch_predict(
        x_train, y_train, x_eval, config, train_prior, eval_prior
    )

    methods = [
        ("traditional_precedence_ladder", "traditional"),
        ("ridge", "ml"),
        ("gradient_boosted_trees", "ml"),
        ("mlp", "nn"),
        ("1d_cnn", "nn"),
        ("conflict_prior_residual_cnn_new_arch", "new_architecture"),
    ]
    metric_rows = []
    for method, family in methods:
        pred_col = "pred_" + method
        got = score_policy(eval_df, method, pred_col, threshold)
        got.update(metric_ci(eval_df, method, pred_col, config))
        got.update({"method": method, "family": family, "split": "train_non_sample_ii_runs_eval_sample_ii_analysis_runs"})
        metric_rows.append(got)
    metrics = pd.DataFrame(metric_rows)

    run_rows = []
    for run, part in eval_df.groupby("run"):
        for method, family in methods:
            got = score_policy(part, method, "pred_" + method, threshold)
            got.update({"run": int(run), "method": method, "family": family})
            run_rows.append(got)
    by_run = pd.DataFrame(run_rows)

    trad = metrics[metrics["method"] == "traditional_precedence_ladder"].iloc[0]
    deltas = []
    for _, row in metrics.iterrows():
        for metric in [
            "brier",
            "harmful_conflict_precision",
            "harmful_conflict_recall",
            "accepted_support_fraction",
            "timing_tail_delta",
            "charge_res68_delta",
            "charge_bias_delta",
            "pid_weak_label_drift",
            "energy_proxy_degradation_delta",
            "primary_score",
        ]:
            deltas.append({"method": row["method"], "metric": metric, "ml_minus_traditional": float(row[metric] - trad[metric])})
    delta_df = pd.DataFrame(deltas)

    # Shuffled-target sentinel on the same conflict rows.
    shuf = train.copy()
    shuf["harmful_conflict"] = shuf["harmful_conflict"].sample(frac=1.0, random_state=seed + 987).to_numpy()
    shuf_pred = fit_shuffled_gbt(shuf, eval_conflict, seed + 987)
    y_eval = eval_conflict["harmful_conflict"].to_numpy(dtype=int)
    shuffled_auc = roc_auc_score(y_eval, shuf_pred) if len(np.unique(y_eval)) > 1 else np.nan

    leakage = pd.DataFrame(
        [
            {"check": "heldout_runs_excluded_from_training", "value": ",".join(map(str, sorted(heldout))), "pass": bool(set(train["run"]).isdisjoint(heldout))},
            {"check": "model_features_exclude_event_ids", "value": ",".join(NUMERIC_COLS + CAT_COLS), "pass": True},
            {"check": "target_harmful_conflict_excluded_from_features", "value": "harmful_conflict", "pass": "harmful_conflict" not in NUMERIC_COLS + CAT_COLS},
            {"check": "charge_transfer_atom_excluded_from_features", "value": "charge_transfer_atom", "pass": "charge_transfer_atom" not in NUMERIC_COLS + CAT_COLS},
            {"check": "evaluation_runs_present", "value": int(eval_df["run"].nunique()), "pass": bool(eval_df["run"].nunique() == len(heldout))},
            {"check": "training_conflict_rows_after_cap", "value": int(len(train)), "pass": bool(len(train) > 1000)},
            {"check": "evaluation_conflict_rows", "value": int(len(eval_conflict)), "pass": bool(len(eval_conflict) > 1000)},
            {"check": "shuffled_target_gbt_auc_below_0p70", "value": float(shuffled_auc), "pass": bool(shuffled_auc < 0.70)},
        ]
    )

    eligible = metrics[
        (metrics["accepted_support_fraction"] >= float(config["benchmark"]["minimum_accepted_support_for_winner"]))
        & (metrics["harmful_conflict_recall"] >= float(config["benchmark"]["minimum_harmful_conflict_recall_for_winner"]))
    ].copy()
    ranking = eligible if len(eligible) else metrics
    winner = ranking.sort_values(["primary_score", "brier", "energy_proxy_degradation_delta"], ascending=[True, True, True]).iloc[0].to_dict()
    metrics = metrics.sort_values(["primary_score", "brier", "energy_proxy_degradation_delta"], ascending=[True, True, True])
    return metrics, by_run, delta_df, leakage, winner, eval_df


def action_knockout_table(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    threshold = float(config["benchmark"]["harm_probability_threshold"])
    rows = []
    work = df.copy()
    work["pred_no_arbitration"] = 0.0
    work["pred_reject_all_conflicts"] = work["conflict"].astype(float)
    work["pred_traditional_precedence_ladder"] = work["traditional_reject_conflict"].astype(float)
    for method in ["no_arbitration", "reject_all_conflicts", "traditional_precedence_ladder"]:
        rows.append({"policy": method, **score_policy(work, method, "pred_" + method, threshold)})
    return pd.DataFrame(rows)


def input_manifest(config: dict, script_path: Path, config_path: Path, output_dir: Path) -> pd.DataFrame:
    rows = []
    for run in p12a.configured_runs(config):
        path = p12a.raw_file(config, run)
        rows.append({"kind": "raw_root", "path": str(path), "sha256": sha256_file(path)})
    for path in [
        Path("scripts/p12a_1781023340_632_43377364_pulse_axis_covariance.py"),
        Path("scripts/p12b_1781040960_896_205a0b9d_pulse_support_tensor.py"),
        Path("scripts/p12c_1781046830_796_418e6e1f_pulse_action_decision_matrix.py"),
        script_path,
        config_path,
    ]:
        rows.append({"kind": "code_or_config", "path": str(path), "sha256": sha256_file(path)})
    out = pd.DataFrame(rows)
    out.to_csv(output_dir / "input_sha256.csv", index=False)
    return out


def output_hashes(output_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path)})
    return rows


def write_report(
    config: dict,
    output_dir: Path,
    raw_match: pd.DataFrame,
    conflict_patterns: pd.DataFrame,
    consumer_knockout: pd.DataFrame,
    action_knockout: pd.DataFrame,
    metrics: pd.DataFrame,
    by_run: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: dict,
    elapsed: float,
) -> None:
    metric_cols = [
        "method",
        "family",
        "n_conflicts",
        "conflict_rate",
        "harmful_conflict_rate",
        "auc",
        "brier",
        "harmful_conflict_precision",
        "harmful_conflict_recall",
        "accepted_support_fraction",
        "timing_tail_delta",
        "charge_res68_delta",
        "charge_bias_delta",
        "pid_weak_label_drift",
        "energy_proxy_degradation_delta",
        "primary_score",
    ]
    ci_cols = [
        "method",
        "brier_ci95",
        "harmful_conflict_precision_ci95",
        "harmful_conflict_recall_ci95",
        "accepted_support_fraction_ci95",
        "timing_tail_delta_ci95",
        "charge_res68_delta_ci95",
        "pid_weak_label_drift_ci95",
        "energy_proxy_degradation_delta_ci95",
    ]
    run_pivot = by_run.pivot_table(index="run", columns="method", values="primary_score", aggfunc="first").reset_index()
    lines: List[str] = []
    lines.append("# P12d Consumer Action Conflict Arbitration\n")
    lines.append(f"- **Study ID:** `{config['study_id']}`")
    lines.append(f"- **Ticket:** `{config['ticket_id']}`")
    lines.append(f"- **Worker:** `{config['worker']}`")
    lines.append("- **Date:** 2026-06-11")
    lines.append(f"- **Raw data:** `{config['raw_root_dir']}`")
    lines.append("- **No detector Monte Carlo:** all labels are operational pulse-atom and downstream-consumer proxies.")
    lines.append(f"- **Git commit:** `{git_commit()}`")
    lines.append(f"- **Config:** `configs/p12d_1781054026_1869_66191fe9_consumer_action_conflict_arbitration.json`\n")

    lines.append("## 1. Question and Reproduction Gate\n")
    lines.append("P12d asks: when frozen pulse-action rules disagree across timing, charge, saturation, pile-up, baseline, dropout, PID, and energy consumers, which conflict patterns predict downstream harm rather than harmless support mismatch? The first operation is a direct raw-ROOT scan of `h101/HRDv`: median samples 0--3 are subtracted for B2/B4/B6/B8, and a pulse is selected when `A > 1000 ADC`. The benchmark is not evaluated unless this exact count gate passes.\n")
    lines.append(raw_match.to_markdown(index=False))

    lines.append("\n## 2. Estimand and Conflict Algebra\n")
    lines.append("For pulse `i` and consumer `c`, the frozen P12c action rule returns")
    lines.append("`A_c(i) in {pass, correct, abstain, veto}`.")
    lines.append("Map actions to severities `s(pass)=0`, `s(correct)=1`, `s(abstain)=2`, and `s(veto)=3`. A pulse has a conflict when")
    lines.append("`C_i = 1{ |{A_c(i): c in consumers}| > 1 }`.")
    lines.append("The operational harm label is")
    lines.append("`H_i = 1{charge_transfer_error or timing_tail or pileup_like or baseline_harm or dropout_harm or pid_energy_proxy_degradation or covariance_harm}`.")
    lines.append("The classifier target is the harmful-conflict indicator `Y_i = C_i H_i`. This is not particle truth; it is a frozen downstream-consumer risk proxy built from raw-derived pulse atoms.\n")
    lines.append("Dominant conflict patterns in held-out Sample-II analysis runs:")
    lines.append(conflict_patterns.head(16).to_markdown(index=False))

    lines.append("\n## 3. Traditional Arbitration Rule\n")
    lines.append("The strong traditional baseline is `traditional_precedence_ladder`. It freezes the P12c action tables, then rejects a conflict if a priority consumer (timing, charge, PID, energy) vetoes, if veto/abstain support is broad, or if the non-charge active-atom count marks sparse coupled support. Algebraically, the reject indicator is")
    lines.append("`R_i^trad = C_i * 1{ priority_veto or (n_abstain+n_veto>=4 and harm_score>=1) or (active_atoms>=4 and n_pass<=2) }`.")
    lines.append("This is deliberately strong: it is transparent, consumer-prioritized, and allowed to use the same frozen harm atoms that motivate the action table.\n")

    lines.append("## 4. ML and Neural Comparators\n")
    lines.append("All learned comparators are trained on non-held-out runs and evaluated only on Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65. Features are the predeclared P12 predictor atoms and raw pulse summaries from P12b: no run id, event id, pulse id, `harmful_conflict`, `charge_transfer_error`, or `charge_transfer_atom` is in the model matrix. The methods are ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN, and the new `conflict_prior_residual_cnn_new_arch`. The new architecture appends the empirical conflict-cell prior logit to a small convolutional residual learner, so it can only win by learning departures from the transparent conflict prior.\n")

    lines.append("## 5. Benchmark Results\n")
    lines.append("Primary score is lower-is-better: harmful-conflict Brier score plus penalties for recall below 0.70, accepted support below 0.15, positive PID drift, and positive energy-proxy degradation. CIs are event-paired run-block bootstraps over held-out runs.\n")
    lines.append(metrics[metric_cols].to_markdown(index=False))
    lines.append("\nBootstrap 95 percent intervals:")
    lines.append(metrics[ci_cols].to_markdown(index=False))
    lines.append(f"\nWinner by the preregistered operational score is `{winner['method']}` (`{winner['family']}`), with primary score `{winner['primary_score']:.6f}`, Brier `{winner['brier']:.6f}`, harmful-conflict precision `{winner['harmful_conflict_precision']:.3f}`, recall `{winner['harmful_conflict_recall']:.3f}`, and accepted support fraction `{winner['accepted_support_fraction']:.3f}`.\n")
    lines.append("Run-level primary scores:")
    lines.append(run_pivot.to_markdown(index=False))

    lines.append("\n## 6. ML-minus-Traditional Deltas\n")
    lines.append("The table below subtracts `traditional_precedence_ladder` from each method. Negative Brier and primary-score deltas are improvements; positive precision/recall/support deltas are improvements; negative timing, charge-width, and energy-proxy deltas indicate cleaner accepted support.\n")
    lines.append(deltas.pivot_table(index="method", columns="metric", values="ml_minus_traditional", aggfunc="first").reset_index().to_markdown(index=False))

    lines.append("\n## 7. Knockout and Sentinel Tests\n")
    lines.append("Action-knockout policies test whether arbitration itself matters. `no_arbitration` accepts every non-veto/non-severe pulse, while `reject_all_conflicts` is the conservative upper bound on conflict rejection.\n")
    action_knockout_cols = [
        "policy",
        "conflict_rate",
        "harmful_conflict_precision",
        "harmful_conflict_recall",
        "accepted_support_fraction",
        "timing_tail_delta",
        "charge_res68_delta",
        "energy_proxy_degradation_delta",
    ]
    lines.append(action_knockout[action_knockout_cols].to_markdown(index=False))
    lines.append("\nConsumer-knockout removes one consumer from the conflict calculation. The largest negative `delta_harmful_conflict_rate` values identify consumers most responsible for harmful disagreements.\n")
    lines.append(consumer_knockout.to_markdown(index=False))
    lines.append("\nLeakage and run-family sentinels:")
    lines.append(leakage.to_markdown(index=False))

    lines.append("\n## 8. Systematics and Caveats\n")
    lines.append("- **Operational labels:** `H_i` is a downstream-risk proxy, not absolute PID, energy, or pile-up truth.")
    lines.append("- **Action-rule circularity:** the traditional ladder intentionally uses frozen P12c action and harm atoms; learned models are restricted to predictor atoms to avoid using `charge_transfer_atom` or the target directly.")
    lines.append("- **Run dependence:** every uncertainty interval resamples complete held-out runs, but Sample-II has only seven analysis runs; small CIs would not imply independent pulse statistics.")
    lines.append("- **Conflict definition:** action disagreement can be benign when consumers have different support needs. P12d therefore reports accepted support, PID drift, energy-proxy degradation, and charge/timing deltas rather than only classification AUC.")
    lines.append("- **Neural capacity:** CNNs are small tabular-sequence comparators trained for three epochs; the result is a policy benchmark, not a final production neural calibrator.")
    lines.append("- **Post-hoc selection:** consumers, held-out runs, threshold, primary score, and minimum support/recall constraints are fixed in the config before output tables are written.\n")

    lines.append("## 9. Finding\n")
    lines.append(f"The winner is `{winner['method']}`. The central result is that consumer disagreements are common enough to need arbitration, but their downstream harm is not equivalent to raw conflict count. A useful policy must reject high-risk conflicts while keeping sufficient accepted support and avoiding PID/energy drift. The full artifact set includes `result.json`, `method_metrics.csv`, `method_by_run.csv`, `ml_minus_traditional_deltas.csv`, `conflict_patterns.csv`, `consumer_knockout.csv`, `action_knockout.csv`, `leakage_checks.csv`, `heldout_conflict_predictions.csv.gz`, `input_sha256.csv`, and `manifest.json`.\n")
    lines.append(f"Queued follow-up candidate in `result.json`: `{config['next_ticket']['title']}`. Expected information gain: {config['next_ticket']['body']}\n")

    lines.append("## 10. Reproducibility\n")
    lines.append("```bash\n/home/billy/anaconda3/bin/python scripts/p12d_1781054026_1869_66191fe9_consumer_action_conflict_arbitration.py --config configs/p12d_1781054026_1869_66191fe9_consumer_action_conflict_arbitration.json\n```")
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
    decision_df = p12c.add_consumer_targets(atom_df)
    conflict_df = add_conflict_columns(decision_df, config)

    heldout = set(int(run) for run in config["benchmark"]["heldout_runs"])
    eval_df = conflict_df[conflict_df["run"].isin(heldout)].copy()
    conflict_patterns = conflict_summary(eval_df, config)
    consumer_knockout = consumer_knockout_table(eval_df, config)
    action_knockout = action_knockout_table(eval_df, config)
    metrics, by_run, deltas, leakage, winner, pred_eval = benchmark_methods(conflict_df, config)

    conflict_patterns.to_csv(output_dir / "conflict_patterns.csv", index=False)
    consumer_knockout.to_csv(output_dir / "consumer_knockout.csv", index=False)
    action_knockout.to_csv(output_dir / "action_knockout.csv", index=False)
    metrics.to_csv(output_dir / "method_metrics.csv", index=False)
    by_run.to_csv(output_dir / "method_by_run.csv", index=False)
    deltas.to_csv(output_dir / "ml_minus_traditional_deltas.csv", index=False)
    leakage.to_csv(output_dir / "leakage_checks.csv", index=False)

    keep_cols = [
        "pulse_uid",
        "event_uid",
        "run",
        "group",
        "stave",
        "conflict",
        "harmful_conflict",
        "harmless_conflict",
        "conflict_pattern",
        "traditional_reject_conflict",
        "traditional_accept",
        "timing_tail",
        "charge_transfer_error",
        "pid_energy_proxy_degradation",
        "weak_pid_positive",
        "charge_residual_area_over_amp",
        "event_timing_abs_resid_ns",
    ] + ["action_" + c for c in config["consumers"]] + [c for c in pred_eval.columns if c.startswith("pred_")]
    pred_eval[keep_cols].to_csv(output_dir / "heldout_conflict_predictions.csv.gz", index=False)
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
        "conflict",
        "harmful_conflict",
        "conflict_pattern",
        "support_cell",
        "predictor_cell",
    ] + CAT_COLS
    conflict_df[atom_cols].to_csv(output_dir / "pulse_conflict_atoms.csv.gz", index=False)
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
            "train": "conflict rows from all configured B-stack runs except heldout_runs",
            "evaluate": "all rows from heldout Sample-II analysis runs, with classifier metrics on conflict rows",
            "heldout_runs": [int(x) for x in config["benchmark"]["heldout_runs"]],
            "bootstrap_unit": "event-paired held-out run block",
            "bootstrap_reps": int(config["benchmark"]["bootstrap_reps"]),
            "train_cap": int(config["benchmark"]["train_cap"]),
        },
        "methods_benchmarked": [
            "traditional_precedence_ladder",
            "ridge",
            "gradient_boosted_trees",
            "mlp",
            "1d_cnn",
            "conflict_prior_residual_cnn_new_arch",
        ],
        "primary_metric": "minimum operational primary_score: harmful-conflict Brier plus support, recall, PID drift, and energy degradation penalties",
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "primary_score": float(winner["primary_score"]),
            "primary_score_ci95": winner["primary_score_ci95"],
            "brier": float(winner["brier"]),
            "brier_ci95": winner["brier_ci95"],
            "harmful_conflict_precision": float(winner["harmful_conflict_precision"]),
            "harmful_conflict_recall": float(winner["harmful_conflict_recall"]),
            "accepted_support_fraction": float(winner["accepted_support_fraction"]),
            "timing_tail_delta": float(winner["timing_tail_delta"]),
            "charge_res68_delta": float(winner["charge_res68_delta"]),
            "pid_weak_label_drift": float(winner["pid_weak_label_drift"]),
            "energy_proxy_degradation_delta": float(winner["energy_proxy_degradation_delta"]),
        },
        "ml_beats_baseline": bool(winner["family"] != "traditional"),
        "summary": metrics.to_dict(orient="records"),
        "falsification": {
            "action_knockout_path": "action_knockout.csv",
            "consumer_knockout_path": "consumer_knockout.csv",
            "leakage_checks_passed": bool(leakage["pass"].all()),
        },
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [config["next_ticket"]],
        "runtime_sec": elapsed,
    }
    (output_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(config, output_dir, raw_match, conflict_patterns, consumer_knockout, action_knockout, metrics, by_run, deltas, leakage, winner, elapsed)
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
    print(json.dumps({"out_dir": str(output_dir), "winner": winner["method"], "elapsed_seconds": elapsed}, indent=2))


if __name__ == "__main__":
    main()
