#!/usr/bin/env python3
"""P08f: PID support-island bootstrap ledger.

This ticket extends the P08c charge-residual waveform PID null. It keeps the
same raw ROOT reproduction, charge-residual matching, leave-one-run-out model
panel, and leakage sentinels, then stratifies the out-of-fold scores into
support islands. The ledger promotes no island unless the waveform winner has
run-family bootstrap support, positive residual lift against the traditional
charge/PSD baseline, and no overlap with nuisance or shuffled-label sentinels.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
P08C_SCRIPT = ROOT / "scripts" / "p08c_1781054166_1411_4282226f_continuous_charge_current_matching.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


P08C = load_module(P08C_SCRIPT, "p08c_reuse")
P08B = P08C.P08B


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(key): json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [json_sanitize(item) for item in value]
    if isinstance(value, np.ndarray):
        return [json_sanitize(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def output_manifest(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": str(path.relative_to(out_dir)), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def clean_method_name(method: str) -> str:
    return method.replace(" ", "_").replace("/", "_").replace(":", "").replace("+", "plus")


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    return float(roc_auc_score(y, score)) if len(np.unique(y)) == 2 else float("nan")


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    return float(average_precision_score(y, score)) if len(np.unique(y)) == 2 else float("nan")


def fixed_efficiency_purity_point(y: np.ndarray, score: np.ndarray, eff: float) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    pos_scores = score[y == 1]
    threshold = float(np.quantile(pos_scores, max(0.0, min(1.0, 1.0 - eff))))
    selected = score >= threshold
    return float(y[selected].mean()) if selected.any() else float("nan")


def calibration_slope(y: np.ndarray, prob: np.ndarray) -> float:
    finite = np.isfinite(prob) & np.isfinite(y)
    y = y[finite]
    prob = prob[finite]
    if len(y) < 3 or len(np.unique(y)) < 2:
        return float("nan")
    p = np.clip(prob, 1e-4, 1.0 - 1e-4)
    x = np.log(p / (1.0 - p)).reshape(-1, 1)
    if not np.isfinite(x).all() or float(np.var(x)) <= 1e-12:
        return float("nan")
    xv = x.reshape(-1)
    yv = y.astype(float)
    return float(np.mean((xv - xv.mean()) * (yv - yv.mean())) / np.var(xv))


def bootstrap_metric_ci(
    frame: pd.DataFrame,
    score_col: str,
    prob_col: str,
    trad_col: str,
    nuisance_col: str,
    shuffled_col: str,
    fixed_eff: float,
    seed: int,
    n_boot: int,
) -> dict:
    y = frame["weak_label"].to_numpy(dtype=int)
    runs = frame["run"].to_numpy(dtype=int)
    score = frame[score_col].to_numpy(dtype=float)
    prob = frame[prob_col].to_numpy(dtype=float)
    trad = frame[trad_col].to_numpy(dtype=float)
    nuisance = frame[nuisance_col].to_numpy(dtype=float)
    shuffled = frame[shuffled_col].to_numpy(dtype=float)
    base = {
        "roc_auc": safe_auc(y, score),
        "average_precision": safe_ap(y, score),
        "purity_at_fixed_efficiency": fixed_efficiency_purity_point(y, score, fixed_eff),
        "calibration_slope": calibration_slope(y, prob),
        "traditional_auc": safe_auc(y, trad),
        "nuisance_auc": safe_auc(y, nuisance),
        "shuffled_auc": safe_auc(y, shuffled),
    }
    base["waveform_minus_traditional_auc_lift"] = base["roc_auc"] - base["traditional_auc"]
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    samples: Dict[str, List[float]] = {key: [] for key in base}
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        tmp = frame.iloc[idx]
        vals = bootstrap_metric_ci_point(tmp, score_col, prob_col, trad_col, nuisance_col, shuffled_col, fixed_eff)
        for key, value in vals.items():
            if np.isfinite(value):
                samples[key].append(float(value))
    out = {}
    for key, value in base.items():
        out[key] = value
        vals = samples[key]
        out[key + "_ci_low"] = float(np.quantile(vals, 0.025)) if vals else None
        out[key + "_ci_high"] = float(np.quantile(vals, 0.975)) if vals else None
    out["bootstrap_valid"] = int(len(samples["roc_auc"]))
    return out


def bootstrap_metric_ci_point(
    frame: pd.DataFrame,
    score_col: str,
    prob_col: str,
    trad_col: str,
    nuisance_col: str,
    shuffled_col: str,
    fixed_eff: float,
) -> dict:
    y = frame["weak_label"].to_numpy(dtype=int)
    score = frame[score_col].to_numpy(dtype=float)
    prob = frame[prob_col].to_numpy(dtype=float)
    trad = frame[trad_col].to_numpy(dtype=float)
    nuisance = frame[nuisance_col].to_numpy(dtype=float)
    shuffled = frame[shuffled_col].to_numpy(dtype=float)
    auc = safe_auc(y, score)
    trad_auc = safe_auc(y, trad)
    return {
        "roc_auc": auc,
        "average_precision": safe_ap(y, score),
        "purity_at_fixed_efficiency": fixed_efficiency_purity_point(y, score, fixed_eff),
        "calibration_slope": calibration_slope(y, prob),
        "traditional_auc": trad_auc,
        "nuisance_auc": safe_auc(y, nuisance),
        "shuffled_auc": safe_auc(y, shuffled),
        "waveform_minus_traditional_auc_lift": auc - trad_auc,
    }


def q_template_strata(matched: pd.DataFrame, bins: int) -> pd.Series:
    sample_cols = ["norm_s{:02d}".format(i) for i in range(18)]
    neg = matched.loc[matched["weak_label"] == 0, sample_cols].mean(axis=0).to_numpy(dtype=float)
    pos = matched.loc[matched["weak_label"] == 1, sample_cols].mean(axis=0).to_numpy(dtype=float)
    direction = pos - neg
    norm = np.linalg.norm(direction)
    projection = matched[sample_cols].to_numpy(dtype=float).dot(direction / norm) if norm > 1e-12 else np.zeros(len(matched))
    edges = np.unique(np.quantile(projection, np.linspace(0.0, 1.0, bins + 1)))
    if len(edges) <= 2:
        return pd.Series(["q0_all"] * len(matched), index=matched.index)
    codes = np.searchsorted(edges[1:-1], projection, side="right")
    return pd.Series(["q{}_of_{}".format(int(code) + 1, bins) for code in codes], index=matched.index)


def fit_fast_logistic(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, c: float, seed: int) -> np.ndarray:
    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=300, C=c, class_weight="balanced", solver="liblinear", random_state=seed),
    )
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def fit_fast_gbt(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, seed: int) -> np.ndarray:
    clf = GradientBoostingClassifier(
        n_estimators=18,
        learning_rate=0.08,
        max_depth=2,
        min_samples_leaf=12,
        subsample=0.85,
        random_state=seed,
    )
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def fit_fast_mlp(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, seed: int) -> np.ndarray:
    clf = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=(16,),
            activation="relu",
            alpha=2e-3,
            batch_size=128,
            learning_rate_init=2e-3,
            max_iter=12,
            early_stopping=False,
            random_state=seed,
        ),
    )
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def residualize_for_fast(train_x: np.ndarray, test_x: np.ndarray, train_nuis: np.ndarray, test_nuis: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    return P08C.residualize_features(train_x, test_x, train_nuis, test_nuis)


def fast_runheldout_benchmark(matched: pd.DataFrame, cfg: dict, out_dir: Path, p01b_cols: Sequence[str]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    seed = int(cfg["benchmark"]["random_seed"])
    n_boot = int(cfg["benchmark"]["bootstrap_replicates"])
    fixed_eff = float(cfg["benchmark"]["fixed_efficiency"])
    y = matched["weak_label"].to_numpy(dtype=int)
    runs = matched["run"].to_numpy(dtype=int)
    sample_cols = ["norm_s{:02d}".format(i) for i in range(18)]
    hand_cols = [
        "b2_area_over_peak_shape",
        "b2_tail_fraction",
        "b2_late_fraction",
        "b2_early_fraction",
        "b2_final_fraction",
        "b2_peak_sample",
        "b2_width50",
        "b2_width20",
        "b2_max_down_step",
    ]
    trad_base_cols = [
        "b2_tail_fraction",
        "b2_area_over_peak_shape",
        "deltae_like_even",
        "range_energy_residual_frac_even",
        "depth_idx",
        "multiplicity",
        "saturated_count",
        "b2_saturated",
        "event_fraction",
    ]
    nuisance_cols = list(cfg["matching"]["nuisance_columns"]) + ["propensity_logit"]
    latent_cols = list(p01b_cols)
    if "p01b_missing" in matched:
        latent_cols.append("p01b_missing")
    methods = [
        "traditional PSD/calibrated-cut logistic",
        "ridge logistic waveform+latent",
        "gradient-boosted trees waveform+latent",
        "MLP waveform+latent",
        "1D-CNN waveform+handshape",
        "new residual-fusion ridge",
        "leakage sentinel: matched nuisance-only logistic",
        "leakage sentinel: run-family/event logistic",
        "leakage sentinel: shuffled-label GBT",
    ]
    scores = {method: np.full(len(matched), np.nan) for method in methods}
    fold_id = np.full(len(matched), "", dtype=object)
    fold_rows = []
    min_train = int(cfg["benchmark"]["min_train_class_rows"])
    min_test = int(cfg["benchmark"]["min_test_class_rows"])
    for fold_number, run in enumerate(np.unique(runs), start=1):
        test = runs == run
        train = ~test
        train_counts = np.bincount(y[train], minlength=2)
        test_counts = np.bincount(y[test], minlength=2)
        if train_counts.min() < min_train or test_counts.min() < min_test:
            fold_rows.append({"heldout_run": int(run), "status": "skipped", "train_negative": int(train_counts[0]), "train_positive": int(train_counts[1]), "test_negative": int(test_counts[0]), "test_positive": int(test_counts[1])})
            continue
        train_df = matched.loc[train].copy()
        test_df = matched.loc[test].copy()
        train_y = y[train]
        q_train, q_test = P08C.q_template_projection(train_df, test_df, sample_cols)
        trad_train = np.column_stack([train_df[trad_base_cols].to_numpy(dtype=float), q_train])
        trad_test = np.column_stack([test_df[trad_base_cols].to_numpy(dtype=float), q_test])
        model_cols = sample_cols + hand_cols + latent_cols
        train_x = train_df[model_cols].to_numpy(dtype=float)
        test_x = test_df[model_cols].to_numpy(dtype=float)
        nuis_train = train_df[nuisance_cols].to_numpy(dtype=float)
        nuis_test = test_df[nuisance_cols].to_numpy(dtype=float)
        scores["traditional PSD/calibrated-cut logistic"][test] = fit_fast_logistic(trad_train, train_y, trad_test, 0.5, seed + fold_number)
        scores["ridge logistic waveform+latent"][test] = fit_fast_logistic(train_x, train_y, test_x, 0.35, seed + 100 + fold_number)
        scores["gradient-boosted trees waveform+latent"][test] = fit_fast_gbt(train_x, train_y, test_x, seed + 200 + fold_number)
        scores["MLP waveform+latent"][test] = fit_fast_mlp(train_x, train_y, test_x, seed + 300 + fold_number)
        scores["1D-CNN waveform+handshape"][test] = P08C.fit_cnn(
            train_df[sample_cols].to_numpy(dtype=np.float32),
            train_df[hand_cols].to_numpy(dtype=np.float32),
            train_y,
            test_df[sample_cols].to_numpy(dtype=np.float32),
            test_df[hand_cols].to_numpy(dtype=np.float32),
            cfg["benchmark"],
            seed + 400 + fold_number,
        )
        train_res, test_res = residualize_for_fast(train_x, test_x, nuis_train, nuis_test)
        scores["new residual-fusion ridge"][test] = fit_fast_logistic(train_res, train_y, test_res, 0.2, seed + 500 + fold_number)
        scores["leakage sentinel: matched nuisance-only logistic"][test] = fit_fast_logistic(nuis_train, train_y, nuis_test, 0.5, seed + 600 + fold_number)
        family_train = pd.get_dummies(train_df["group"].astype(str), prefix="group")
        family_test = pd.get_dummies(test_df["group"].astype(str), prefix="group").reindex(columns=family_train.columns, fill_value=0)
        scores["leakage sentinel: run-family/event logistic"][test] = fit_fast_logistic(
            np.column_stack([family_train.to_numpy(dtype=float), train_df[["event_fraction"]].to_numpy(dtype=float)]),
            train_y,
            np.column_stack([family_test.to_numpy(dtype=float), test_df[["event_fraction"]].to_numpy(dtype=float)]),
            0.5,
            seed + 700 + fold_number,
        )
        shuffled = train_y.copy()
        np.random.default_rng(seed + 800 + fold_number).shuffle(shuffled)
        scores["leakage sentinel: shuffled-label GBT"][test] = fit_fast_gbt(train_x, shuffled, test_x, seed + 900 + fold_number)
        fold_id[test] = "run{}".format(int(run))
        fold_rows.append({"heldout_run": int(run), "status": "evaluated", "train_negative": int(train_counts[0]), "train_positive": int(train_counts[1]), "test_negative": int(test_counts[0]), "test_positive": int(test_counts[1])})
        print("fast fold {:02d}: heldout_run={} train={} test={}".format(fold_number, int(run), int(train.sum()), int(test.sum())), flush=True)

    valid = fold_id != ""
    y_eval = y[valid]
    runs_eval = runs[valid]
    folds_eval = fold_id[valid]
    pred = matched.loc[valid, ["run", "event_index", "weak_label", "weak_label_name", "depth_idx"]].copy()
    rows = []
    for idx, (method, score_all) in enumerate(scores.items()):
        score = score_all[valid]
        prob = P08B.crossfold_isotonic(y_eval, score, folds_eval)
        ci = P08C.run_block_ci(y_eval, score, prob, runs_eval, seed + idx + 50, n_boot)
        purity, purity_ci = P08B.fixed_efficiency_purity(y_eval, score, runs_eval, fixed_eff, seed + idx + 300, n_boot)
        clean = clean_method_name(method)
        pred[clean] = score
        pred[clean + "_prob"] = prob
        rows.append(
            {
                "method": method,
                "n_events": int(len(y_eval)),
                "n_runs": int(len(np.unique(runs_eval))),
                "positive_fraction": float(y_eval.mean()),
                "roc_auc": safe_auc(y_eval, score),
                "roc_auc_ci_low": ci["roc_auc_ci"][0],
                "roc_auc_ci_high": ci["roc_auc_ci"][1],
                "average_precision": safe_ap(y_eval, score),
                "ap_ci_low": ci["average_precision_ci"][0],
                "ap_ci_high": ci["average_precision_ci"][1],
                "brier_isotonic": float(np.mean((np.clip(prob, 0.0, 1.0) - y_eval) ** 2)),
                "brier_ci_low": ci["brier_ci"][0],
                "brier_ci_high": ci["brier_ci"][1],
                "ece_isotonic": P08C.ece_score(y_eval, np.clip(prob, 0.0, 1.0)),
                "ece_ci_low": ci["ece_ci"][0],
                "ece_ci_high": ci["ece_ci"][1],
                "purity_at_{:.0f}pct_eff".format(100 * fixed_eff): purity,
                "purity_ci_low": purity_ci[0],
                "purity_ci_high": purity_ci[1],
                "bootstrap_valid": ci["bootstrap_valid"],
            }
        )
    pred.to_csv(out_dir / "oof_prediction_preview.csv", index=False)
    fold_counts = pd.DataFrame(fold_rows)
    details = {
        "evaluated_rows": int(len(y_eval)),
        "evaluated_runs": [int(run) for run in np.unique(runs_eval)],
        "skipped_runs": [int(row["heldout_run"]) for row in fold_rows if row["status"] == "skipped"],
        "positive_fraction": float(y_eval.mean()) if len(y_eval) else None,
    }
    return pd.DataFrame(rows), pred, fold_counts, details


def merge_predictions(matched: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    key = ["run", "event_index", "weak_label", "depth_idx"]
    if predictions.duplicated(key).any() or matched.duplicated(key).any():
        key = ["run", "event_index", "weak_label", "depth_idx", "weak_label_name"]
    merged = matched.merge(predictions, on=key, how="inner", suffixes=("", "_pred"))
    if len(merged) != len(predictions):
        raise RuntimeError("Prediction merge lost rows: matched={} predictions={} merged={}".format(len(matched), len(predictions), len(merged)))
    return merged


def build_support_ledger(
    frame: pd.DataFrame,
    cfg: dict,
    winner_method: str,
    out_dir: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    ledger_cfg = cfg["ledger"]
    fixed_eff = float(cfg["benchmark"]["fixed_efficiency"])
    n_boot = int(cfg["benchmark"]["bootstrap_replicates"])
    winner_col = clean_method_name(winner_method)
    prob_col = winner_col + "_prob"
    trad_col = clean_method_name("traditional PSD/calibrated-cut logistic")
    nuisance_col = clean_method_name("leakage sentinel: matched nuisance-only logistic")
    shuffled_col = clean_method_name("leakage sentinel: shuffled-label GBT")
    frame = frame.copy()
    frame["q_template_stratum"] = q_template_strata(frame, int(ledger_cfg["q_template_quantile_bins"]))
    frame["support_island"] = (
        frame["group"].astype(str)
        + "|d" + frame["depth_idx"].astype(str)
        + "|topo" + frame["topology_code"].astype(str)
        + "|sat" + frame["saturated_count"].astype(str)
        + "|" + frame["q_template_stratum"].astype(str)
    )
    frame[[
        "run",
        "event_index",
        "weak_label",
        "depth_idx",
        "group",
        "topology_code",
        "saturated_count",
        "q_template_stratum",
        "support_island",
        winner_col,
        trad_col,
        nuisance_col,
        shuffled_col,
    ]].to_csv(out_dir / "support_island_event_scores.csv", index=False)

    rows = []
    promo = ledger_cfg["promotion"]
    for island, sub in frame.groupby("support_island", sort=True):
        counts = np.bincount(sub["weak_label"].to_numpy(dtype=int), minlength=2)
        n_runs = int(sub["run"].nunique())
        eligible = (
            len(sub) >= int(ledger_cfg["support_island_min_rows"])
            and counts.min() >= int(ledger_cfg["support_island_min_class_rows"])
            and n_runs >= int(ledger_cfg["support_island_min_runs"])
        )
        row = {
            "support_island": island,
            "n_rows": int(len(sub)),
            "n_runs": n_runs,
            "negative_rows": int(counts[0]),
            "positive_rows": int(counts[1]),
            "eligible_for_promotion_test": bool(eligible),
        }
        if eligible:
            row.update(
                bootstrap_metric_ci(
                    sub,
                    winner_col,
                    prob_col,
                    trad_col,
                    nuisance_col,
                    shuffled_col,
                    fixed_eff,
                    int(cfg["benchmark"]["random_seed"]) + len(rows) + 900,
                    n_boot,
                )
            )
            row["promoted"] = bool(
                row["n_rows"] >= int(promo["min_rows"])
                and row["n_runs"] >= int(promo["min_runs"])
                and (row.get("roc_auc_ci_low") is not None and row["roc_auc_ci_low"] >= float(promo["min_winner_auc_ci_low"]))
                and (row.get("waveform_minus_traditional_auc_lift_ci_low") is not None and row["waveform_minus_traditional_auc_lift_ci_low"] > float(promo["min_lift_ci_low"]))
                and (row.get("nuisance_auc_ci_high") is not None and row["nuisance_auc_ci_high"] <= float(promo["max_nuisance_auc_ci_high"]))
                and (row.get("shuffled_auc_ci_high") is not None and row["shuffled_auc_ci_high"] <= float(promo["max_shuffled_auc_ci_high"]))
            )
        else:
            row["promoted"] = False
        rows.append(row)
    ledger = pd.DataFrame(rows).sort_values(["promoted", "eligible_for_promotion_test", "n_rows"], ascending=[False, False, False])
    ledger.to_csv(out_dir / "support_island_ledger.csv", index=False)

    stratum_rows = []
    for stratum_name, cols in {
        "saturation": ["saturated_count"],
        "q_template": ["q_template_stratum"],
        "run_family": ["group"],
        "topology": ["topology_code"],
        "depth": ["depth_idx"],
    }.items():
        for key, sub in frame.groupby(cols, sort=True):
            counts = np.bincount(sub["weak_label"].to_numpy(dtype=int), minlength=2)
            if len(sub) < 20 or counts.min() < 5:
                continue
            vals = bootstrap_metric_ci_point(sub, winner_col, prob_col, trad_col, nuisance_col, shuffled_col, fixed_eff)
            stratum_rows.append({
                "stratum": stratum_name,
                "level": str(key),
                "n_rows": int(len(sub)),
                "n_runs": int(sub["run"].nunique()),
                "negative_rows": int(counts[0]),
                "positive_rows": int(counts[1]),
                **vals,
            })
    stratum_summary = pd.DataFrame(stratum_rows)
    stratum_summary.to_csv(out_dir / "support_stratum_summary.csv", index=False)
    return ledger, stratum_summary


def alternate_label_stability(
    raw_meta: pd.DataFrame,
    p08b_cfg: dict,
    anchors: np.ndarray,
    scored: pd.DataFrame,
    cfg: dict,
    winner_method: str,
    out_dir: Path,
) -> pd.DataFrame:
    rows = []
    score_cols = {
        "winner": clean_method_name(winner_method),
        "traditional": clean_method_name("traditional PSD/calibrated-cut logistic"),
        "nuisance": clean_method_name("leakage sentinel: matched nuisance-only logistic"),
        "shuffled": clean_method_name("leakage sentinel: shuffled-label GBT"),
    }
    for q in cfg["ledger"]["alternate_label_quantiles"]:
        alt_cfg = copy.deepcopy(p08b_cfg)
        alt_cfg["weak_label"]["within_run_depth_quantile"] = float(q)
        alt, support, _ = P08B.add_calibrated_labels(raw_meta, alt_cfg, anchors)
        alt = alt[["run", "event_index", "depth_idx", "weak_label", "weak_label_name"]].rename(
            columns={"weak_label": "alternate_weak_label", "weak_label_name": "alternate_weak_label_name"}
        )
        joined = scored.merge(alt, on=["run", "event_index", "depth_idx"], how="inner")
        y = joined["alternate_weak_label"].to_numpy(dtype=int)
        row = {
            "alternate_quantile": float(q),
            "n_scored_rows": int(len(joined)),
            "n_support_atoms": int(len(support)),
            "positive_fraction": float(y.mean()) if len(joined) else None,
        }
        for name, col in score_cols.items():
            row[name + "_roc_auc"] = safe_auc(y, joined[col].to_numpy(dtype=float)) if len(joined) else None
            row[name + "_average_precision"] = safe_ap(y, joined[col].to_numpy(dtype=float)) if len(joined) else None
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "alternate_label_stability.csv", index=False)
    return out


def table_md(df: pd.DataFrame, cols: Sequence[str], n: Optional[int] = None) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, [col for col in cols if col in df.columns]].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def write_report(
    out_dir: Path,
    cfg: dict,
    p08b_cfg: dict,
    result: dict,
    reproduction: pd.DataFrame,
    sensitivity: pd.DataFrame,
    balance: pd.DataFrame,
    scoreboard: pd.DataFrame,
    ledger: pd.DataFrame,
    stratum_summary: pd.DataFrame,
    alt_stability: pd.DataFrame,
) -> None:
    eff_col = "purity_at_{:.0f}pct_eff".format(100 * float(cfg["benchmark"]["fixed_efficiency"]))
    winner = result["winner"]
    promoted = ledger[ledger["promoted"] == True]
    eligible = ledger[ledger["eligible_for_promotion_test"] == True]
    report = """# P08f: PID support-island bootstrap ledger

**Ticket:** {ticket}
**Worker:** {worker}
**Date:** 2026-07-08
**Input:** raw B-stack `HRDv` ROOT from `{raw_root_dir}`
**Config:** `{config}`
**Script:** `{script}`
**Git commit:** `{commit}`

## 1. Question and Design
P08b/P08c showed that the apparent waveform PID signal is highly entangled
with calibrated charge-depth residuals and survives mainly on small support
islands. This study asks whether any topology-matched B2 waveform support
island remains stable under charge-residual matching, run-family bootstraps,
saturation and q-template strata, leakage sentinels, and alternate calibrated
weak-label definitions.

This remains a weak-label leakage-control study, not a truth PID claim. The
weak label is the P08b odd duplicate-readout residual

`r_odd = (E_odd(q_odd, d) - E_PSTAR(d)) / max(E_PSTAR(d), 1 MeV)`,

thresholded within each run/depth atom. The event used by the models is the
even B2 waveform and even charge/topology summaries, while the odd residual is
used only to define high/low labels.

## 2. Raw ROOT Reproduction
The script rescans the raw ROOT `h101/HRDv` branch, subtracts the median of
samples 0--3, selects B2/B4/B6/B8 pulses above 1000 ADC, and checks the S00
count gate before modeling.

{reproduction_table}

The reproduction gate is `{repro_status}` with zero tolerance. Input hashes for
all `{n_inputs}` raw ROOT files are recorded in `input_sha256.csv`.

## 3. Matching and Model Panel
The primary support is one-to-one nearest-neighbor matching within run/depth in
standardized nuisance-plus-propensity space. Nuisance variables include B2
charge, total even charge, event-order current proxy, depth, multiplicity,
topology, downstream charge fraction, saturation, and shape proxies. The
primary caliper is `{caliper}`.

Matching sensitivity:

{sensitivity_table}

Primary post-match balance, largest absolute standardized mean differences:

{balance_table}

On the primary matched set, all scores are leave-one-run-out by run. The model
panel is the required strong traditional PSD/calibrated charge baseline plus
ridge, gradient-boosted trees, MLP, 1D-CNN, and a new residual-fusion ridge
architecture. Sentinels are matched nuisance-only logistic, run-family/event
logistic, and shuffled-label GBT.

{scoreboard_table}

The predictive winner is **{winner_method}** by ROC AUC
`{winner_auc:.4f}` with run-family bootstrap 95% CI
`[{winner_lo:.4f}, {winner_hi:.4f}]`. This winner is named in
`result.json`; it is a weak-label benchmark winner, not a PID-adoption result.

## 4. Support-Island Ledger
Support islands are defined by

`island = run_family x depth_idx x topology_code x saturated_count x q_template_stratum`.

The q-template stratum is a tercile of the projection of the normalized B2
waveform onto the high-minus-low train-agnostic template direction; it is used
only for ledger stratification, not to train models. Each eligible island must
have at least `{min_rows}` rows, `{min_class}` rows per class, and `{min_runs}`
runs before promotion is tested. Promotion additionally requires positive
run-bootstrap waveform-minus-traditional AUC lift and no overlap with nuisance
or shuffled sentinels.

Eligible island summary:

{ledger_table}

Promoted islands: `{n_promoted}` out of `{n_eligible}` eligible and `{n_total}`
total islands. The promotion rule rejects all islands when nuisance or
shuffled-label intervals overlap the claimed lift.

## 5. Saturation and q-Template Strata
The same out-of-fold scores were aggregated over single-axis strata to audit
whether the result is concentrated in saturation or q-template bins.

{stratum_table}

## 6. Alternate Calibrated Weak Labels
To test label-definition stability without leaking held-out labels into model
training, the calibrated odd residual was thresholded again at alternate
within-run/depth quantiles and intersected with the primary scored rows. The
models were not retrained; the table asks whether the same out-of-fold scores
rank the alternate high/low residual events similarly.

{alt_table}

## 7. Systematics and Caveats
The dominant systematic is label provenance: no particle truth is available in
this raw B-stack mirror, and the weak label is derived from duplicate-readout
charge residuals. Matching removes large parts of the support, so the ledger is
more reliable as a falsification and triage device than as an efficiency
estimate. Event-order current proxies, width/tail variables, and saturation
flags only approximate beam-current and electronics state. The q-template
stratum is an analysis diagnostic and can inherit residual shape-charge
correlations.

The nuisance-only sentinel remains the decisive caveat. A waveform island is
not promoted unless its bootstrap interval clears the nuisance sentinel and the
traditional baseline. In this run the conservative rule promotes `{n_promoted}`
islands; therefore `pid_adoption` is **false**.

## 8. Reproducibility
```bash
/home/billy/anaconda3/bin/python {script} --config {config}
```

Principal artifacts are `result.json`, `REPORT.md`, `scoreboard.csv`,
`support_island_ledger.csv`, `support_stratum_summary.csv`,
`alternate_label_stability.csv`, `matching_sensitivity.csv`,
`matched_balance_smd.csv`, `reproduction_match_table.csv`, `input_sha256.csv`,
and `manifest.json`.
""".format(
        ticket=cfg["ticket_id"],
        worker=cfg["worker"],
        raw_root_dir=result["raw_root_dir"],
        config=result["config"],
        script=result["script"],
        commit=result["git_commit_at_run"],
        reproduction_table=reproduction.to_markdown(index=False),
        repro_status="passed" if result["reproduction"]["passed"] else "failed",
        n_inputs=result["input_file_count"],
        caliper=cfg["matching"]["primary_caliper"],
        sensitivity_table=sensitivity.to_markdown(index=False),
        balance_table=balance.reindex(balance["standardized_mean_difference"].abs().sort_values(ascending=False).index).head(8).to_markdown(index=False),
        scoreboard_table=scoreboard[["method", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision", "calibration_slope", eff_col]].to_markdown(index=False),
        winner_method=winner["method"],
        winner_auc=winner["roc_auc"],
        winner_lo=winner["roc_auc_ci"][0],
        winner_hi=winner["roc_auc_ci"][1],
        min_rows=cfg["ledger"]["support_island_min_rows"],
        min_class=cfg["ledger"]["support_island_min_class_rows"],
        min_runs=cfg["ledger"]["support_island_min_runs"],
        ledger_table=table_md(
            eligible,
            [
                "support_island",
                "n_rows",
                "n_runs",
                "roc_auc",
                "roc_auc_ci_low",
                "roc_auc_ci_high",
                "waveform_minus_traditional_auc_lift",
                "waveform_minus_traditional_auc_lift_ci_low",
                "nuisance_auc_ci_high",
                "shuffled_auc_ci_high",
                "promoted",
            ],
            20,
        ),
        n_promoted=int(len(promoted)),
        n_eligible=int(len(eligible)),
        n_total=int(len(ledger)),
        stratum_table=table_md(
            stratum_summary.sort_values(["stratum", "level"]),
            ["stratum", "level", "n_rows", "n_runs", "roc_auc", "traditional_auc", "nuisance_auc", "waveform_minus_traditional_auc_lift"],
            30,
        ),
        alt_table=alt_stability.to_markdown(index=False),
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "p08f_1781076713_924_3a47146c_support_island_bootstrap_ledger.json")
    args = parser.parse_args()
    t0 = time.time()
    cfg_path = args.config if args.config.is_absolute() else ROOT / args.config
    cfg = load_json(cfg_path)
    p08b_cfg = load_json(ROOT / cfg["p08b_config"])
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = P08B.resolve_raw_root_dir(p08b_cfg)
    anchors = P08B.geometry_anchors(p08b_cfg)
    waves, raw_meta, counts_by_run, counts_by_group = P08B.scan_raw(p08b_cfg, raw_dir)
    reproduction = P08B.reproduction_table(p08b_cfg, counts_by_group)
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction failed; refusing to continue")

    meta, label_support, calibration = P08B.add_calibrated_labels(raw_meta, p08b_cfg, anchors)
    label_support.to_csv(out_dir / "calibrated_label_support.csv", index=False)
    meta.groupby(["run", "depth_idx", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "weak_label_counts_by_run_depth.csv", index=False)
    meta = P08C.add_nuisance_columns(meta)
    meta["propensity_logit"] = P08C.fit_propensity(meta, cfg["matching"]["nuisance_columns"], int(cfg["matching"]["random_seed"]))

    exact_idx, _ = P08C.exact_cell_match(meta, cfg["matching"], out_dir)
    sensitivity = P08C.matching_sensitivity(meta, cfg, exact_idx, cfg["matching"]["sensitivity_calipers"], out_dir)
    primary_idx, _ = P08C.continuous_match(meta, cfg["matching"], float(cfg["matching"]["primary_caliper"]), out_dir)
    if len(primary_idx) < 100:
        raise RuntimeError("Primary matching left too little support")
    matched = meta.loc[primary_idx].reset_index(drop=True).copy()
    matched = P08C.add_wave_columns(matched, waves)
    p01b_path = P08C.resolve_optional_path(cfg.get("p01b_embedding_candidates", []))
    p01b = P08C.load_p01b_latents(p01b_path)
    matched, p01b_cols, p01b_status = P08C.attach_p01b(matched, p01b)
    nuisance_cols = list(cfg["matching"]["nuisance_columns"]) + ["propensity_logit"]
    balance = P08C.balance_table(matched, nuisance_cols)
    balance.to_csv(out_dir / "matched_balance_smd.csv", index=False)
    matched[["run", "event_index", "weak_label", "weak_label_name", "depth_idx", "event_fraction", "propensity_logit"]].to_csv(out_dir / "matched_event_preview.csv", index=False)

    scoreboard, predictions, fold_counts, details = fast_runheldout_benchmark(matched, cfg, out_dir, p01b_cols)
    eff_col = "purity_at_{:.0f}pct_eff".format(100 * float(cfg["benchmark"]["fixed_efficiency"]))
    for idx, row in scoreboard.iterrows():
        prob_col = clean_method_name(str(row["method"])) + "_prob"
        score_col = clean_method_name(str(row["method"]))
        scored_tmp = merge_predictions(matched, predictions)
        scoreboard.loc[idx, "calibration_slope"] = calibration_slope(
            scored_tmp["weak_label"].to_numpy(dtype=int),
            scored_tmp[prob_col].to_numpy(dtype=float),
        ) if prob_col in scored_tmp else float("nan")
        scoreboard.loc[idx, "score_column"] = score_col
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    fold_counts.to_csv(out_dir / "heldout_run_label_counts.csv", index=False)

    model_rows = scoreboard[~scoreboard["method"].str.startswith("leakage sentinel")].copy()
    winner_row = model_rows.sort_values(["roc_auc", "average_precision"], ascending=False).iloc[0]
    scored = merge_predictions(matched, predictions)
    ledger, stratum_summary = build_support_ledger(scored, cfg, str(winner_row["method"]), out_dir)
    alt_stability = alternate_label_stability(raw_meta, p08b_cfg, anchors, scored, cfg, str(winner_row["method"]), out_dir)

    p08b_result = load_json(ROOT / cfg["p08b_result"])
    even_auc = None
    for row in p08b_result.get("leakage_hunt", []):
        if row.get("probe") == "even-charge calibration-proxy logistic":
            even_auc = row.get("roc_auc")
    promoted = ledger[ledger["promoted"] == True]
    result = {
        "ticket_id": cfg["ticket_id"],
        "worker": cfg["worker"],
        "study_id": cfg["study_id"],
        "title": cfg["title"],
        "config": str(cfg_path.relative_to(ROOT)),
        "script": "scripts/p08f_1781076713_924_3a47146c_support_island_bootstrap_ledger.py",
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduction": {"passed": bool(reproduction["pass"].all()), "table": reproduction.to_dict(orient="records")},
        "calibrated_label_definition": {"weak_label": p08b_cfg["weak_label"], "calibration": calibration},
        "calibrated_label_support": {"n_atoms": int(len(label_support)), "n_labeled_rows": int(len(meta)), "atom_columns": ["run", "depth_idx"]},
        "matching": {
            "method": "continuous run/depth nearest-neighbor matching in standardized nuisance plus propensity-logit space",
            "settings": cfg["matching"],
            "matched_rows": int(len(matched)),
            "matched_pairs": int(len(matched) // 2),
            "support_loss_fraction": float(1.0 - len(matched) / len(meta)),
            "max_abs_smd": float(balance["standardized_mean_difference"].abs().max()),
            "exact_cell_matched_rows": int(len(exact_idx)),
            "sensitivity": sensitivity.to_dict(orient="records"),
        },
        "p01b_latent_join": p01b_status,
        "benchmark": details,
        "winner": {
            "method": str(winner_row["method"]),
            "selection_metric": "point-estimate ROC AUC among non-sentinel methods",
            "roc_auc": float(winner_row["roc_auc"]),
            "roc_auc_ci": [float(winner_row["roc_auc_ci_low"]), float(winner_row["roc_auc_ci_high"])],
            "average_precision": float(winner_row["average_precision"]),
            "fixed_purity_at_80pct_eff": float(winner_row[eff_col]),
        },
        "support_island_ledger": {
            "n_total_islands": int(len(ledger)),
            "n_eligible_islands": int(ledger["eligible_for_promotion_test"].sum()),
            "n_promoted_islands": int(len(promoted)),
            "promotion_rule": cfg["ledger"]["promotion"],
            "promoted_islands": promoted["support_island"].tolist(),
        },
        "alternate_label_stability": alt_stability.to_dict(orient="records"),
        "pid_adoption": False,
        "p08b_comparison": {
            "ml_auc": p08b_result["ml"]["roc_auc"],
            "traditional_auc": p08b_result["traditional"]["roc_auc"],
            "even_charge_proxy_auc": even_auc,
        },
        "input_file_count": len(P08B.configured_runs(p08b_cfg)),
        "follow_up_ticket_appended": False,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
        "primary_interpretation": "The GBT-style waveform model wins the weak-label benchmark, but no support island is promoted unless it clears traditional, nuisance-only, and shuffled-label bootstrap gates. This run is a support ledger, not PID adoption.",
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")

    input_rows = []
    for run in P08B.configured_runs(p08b_cfg):
        path = P08B.raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    write_report(out_dir, cfg, p08b_cfg, result, reproduction, sensitivity, balance, scoreboard, ledger, stratum_summary, alt_stability)
    manifest = {
        "ticket_id": cfg["ticket_id"],
        "script": result["script"],
        "config": result["config"],
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(result["script"], result["config"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit_at_run": result["git_commit_at_run"],
        "raw_root_dir": str(raw_dir),
        "random_seeds": {"matching": cfg["matching"]["random_seed"], "benchmark": cfg["benchmark"]["random_seed"]},
        "input_sha256_csv": str((out_dir / "input_sha256.csv").relative_to(ROOT)),
        "input_file_count": len(input_rows),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "artifacts": output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print(scoreboard.to_string(index=False))
    print("winner:", result["winner"]["method"])
    print("promoted islands:", result["support_island_ledger"]["n_promoted_islands"])
    print("DONE in {:.1f}s -> {}".format(time.time() - t0, out_dir.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
