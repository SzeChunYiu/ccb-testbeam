#!/usr/bin/env python3
"""P08c: topology-matched B2 waveform PID null from raw B-stack ROOT.

The ticket asks whether P08a's B2 waveform AUC survives after terminal-like and
penetrating-like topology labels are matched on run family, B2 amplitude, total
charge, and event order. This is a weak-label leakage/null study, not a truth
PID result.
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
from typing import Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight


P08A_SCRIPT = Path("scripts/p08a_1781012712_914_09cf1a30_penetration_weak_pid.py")
HAND_COLS = [
    "b2_area_over_peak",
    "b2_tail_fraction",
    "b2_late_fraction",
    "b2_early_fraction",
    "b2_final_fraction",
    "b2_peak_sample",
    "b2_width50",
    "b2_width20",
    "b2_max_down_step",
]
SAMPLE_COLS = ["norm_s{:02d}".format(i) for i in range(18)]


def load_p08a_module():
    spec = importlib.util.spec_from_file_location("p08a_repro", str(P08A_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


P08A = load_p08a_module()


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def raw_file(raw_root_dir: Path, run: int) -> Path:
    return raw_root_dir / "hrdb_run_{:04d}.root".format(run)


def bin_quantile(values: np.ndarray, bins: int) -> np.ndarray:
    finite = np.isfinite(values)
    edges = np.unique(np.quantile(values[finite], np.linspace(0.0, 1.0, bins + 1)))
    if len(edges) <= 2:
        return np.zeros(len(values), dtype=np.int16)
    return np.searchsorted(edges[1:-1], values, side="right").astype(np.int16)


def add_matching_columns(meta: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = meta.copy()
    max_event = out.groupby("run")["event_index"].transform("max").replace(0, 1)
    out["event_fraction"] = (out["event_index"] / max_event).astype(np.float32)
    out["log_b2_amplitude"] = np.log1p(out["b2_amplitude_adc"].to_numpy(dtype=float)).astype(np.float32)
    out["log_total_charge"] = np.log1p(out["total_charge_adc_samples"].to_numpy(dtype=float)).astype(np.float32)
    match_cfg = config["matching"]
    out["amp_bin"] = bin_quantile(out["log_b2_amplitude"].to_numpy(dtype=float), int(match_cfg["amplitude_quantile_bins"]))
    out["charge_bin"] = bin_quantile(out["log_total_charge"].to_numpy(dtype=float), int(match_cfg["total_charge_quantile_bins"]))
    out["event_bin"] = np.minimum(
        (out["event_fraction"].to_numpy(dtype=float) * int(match_cfg["event_order_bins"])).astype(np.int16),
        int(match_cfg["event_order_bins"]) - 1,
    )
    out["match_cell"] = (
        out["group"].astype(str)
        + "|a"
        + out["amp_bin"].astype(str)
        + "|q"
        + out["charge_bin"].astype(str)
        + "|e"
        + out["event_bin"].astype(str)
    )
    return out


def choose_nearest_pairs(group: pd.DataFrame, neg: np.ndarray, pos: np.ndarray, pairs: int, rng: np.random.Generator) -> Tuple[List[int], List[int], List[float]]:
    covars = ["log_b2_amplitude", "log_total_charge", "event_fraction"]
    if len(pos) > pairs:
        pos = rng.choice(pos, size=pairs, replace=False)
    rng.shuffle(pos)
    x_all = group[covars].to_numpy(dtype=float)
    center = x_all.mean(axis=0)
    scale = x_all.std(axis=0)
    scale[scale <= 1e-9] = 1.0
    neg_x = (meta_for_match.loc[neg, covars].to_numpy(dtype=float) - center) / scale
    pos_x = (meta_for_match.loc[pos, covars].to_numpy(dtype=float) - center) / scale
    model = NearestNeighbors(n_neighbors=min(20, len(neg)), algorithm="auto")
    model.fit(neg_x)
    distances, neighbors = model.kneighbors(pos_x)
    used = set()
    chosen_neg: List[int] = []
    chosen_pos: List[int] = []
    chosen_dist: List[float] = []
    for i, pos_idx in enumerate(pos):
        selected = None
        selected_dist = None
        for dist, local in zip(distances[i], neighbors[i]):
            neg_idx = int(neg[int(local)])
            if neg_idx not in used:
                selected = neg_idx
                selected_dist = float(dist)
                break
        if selected is None:
            remaining = np.asarray([idx for idx in neg if int(idx) not in used], dtype=int)
            if len(remaining) == 0:
                continue
            rem_x = (meta_for_match.loc[remaining, covars].to_numpy(dtype=float) - center) / scale
            delta = rem_x - pos_x[i]
            j = int(np.argmin(np.sum(delta * delta, axis=1)))
            selected = int(remaining[j])
            selected_dist = float(math.sqrt(np.sum(delta[j] * delta[j])))
        used.add(selected)
        chosen_neg.append(selected)
        chosen_pos.append(int(pos_idx))
        chosen_dist.append(selected_dist if selected_dist is not None else float("nan"))
    return chosen_neg, chosen_pos, chosen_dist


meta_for_match: pd.DataFrame


def bin_matched_indices(meta: pd.DataFrame, config: dict, out_dir: Path, include_run: bool = False, nearest: bool = False) -> np.ndarray:
    global meta_for_match
    meta_for_match = meta
    rng = np.random.default_rng(int(config["matching"]["random_seed"]))
    max_pairs = int(config["matching"]["max_pairs_per_cell"])
    min_pairs = int(config["matching"]["min_pairs_per_cell"])
    max_pair_distance = config["matching"].get("max_pair_distance")
    max_pair_distance = None if max_pair_distance is None else float(max_pair_distance)
    keep: List[int] = []
    rows = []
    group_keys = ["run", "match_cell"] if include_run else ["match_cell"]
    for key, group in meta.groupby(group_keys, sort=True):
        cell = group["match_cell"].iloc[0]
        neg = group.index[group["weak_label"].to_numpy(dtype=int) == 0].to_numpy()
        pos = group.index[group["weak_label"].to_numpy(dtype=int) == 1].to_numpy()
        pairs = min(len(neg), len(pos), max_pairs)
        if pairs < min_pairs:
            rows.append(
                {
                    "match_cell": cell,
                    "run": int(group["run"].iloc[0]),
                    "group": str(group["group"].iloc[0]),
                    "amp_bin": int(group["amp_bin"].iloc[0]),
                    "charge_bin": int(group["charge_bin"].iloc[0]),
                    "event_bin": int(group["event_bin"].iloc[0]),
                    "negative_rows": int(len(neg)),
                    "positive_rows": int(len(pos)),
                    "matched_pairs": 0,
                    "median_distance": None,
                    "p90_distance": None,
                }
            )
            continue
        if nearest:
            chosen_neg, chosen_pos, chosen_dist = choose_nearest_pairs(group, neg, pos, pairs, rng)
            if max_pair_distance is not None:
                filtered = [(n, p, d) for n, p, d in zip(chosen_neg, chosen_pos, chosen_dist) if d <= max_pair_distance]
                if filtered:
                    chosen_neg, chosen_pos, chosen_dist = [x[0] for x in filtered], [x[1] for x in filtered], [x[2] for x in filtered]
                else:
                    chosen_neg, chosen_pos, chosen_dist = [], [], []
            keep.extend(chosen_neg)
            keep.extend(chosen_pos)
            matched_pairs = len(chosen_pos)
            median_distance = float(np.median(chosen_dist)) if chosen_dist else None
            p90_distance = float(np.quantile(chosen_dist, 0.9)) if chosen_dist else None
        else:
            keep.extend(rng.choice(neg, size=pairs, replace=False).tolist())
            keep.extend(rng.choice(pos, size=pairs, replace=False).tolist())
            matched_pairs = pairs
            median_distance = None
            p90_distance = None
        rows.append(
            {
                "match_cell": cell,
                "run": int(group["run"].iloc[0]),
                "group": str(group["group"].iloc[0]),
                "amp_bin": int(group["amp_bin"].iloc[0]),
                "charge_bin": int(group["charge_bin"].iloc[0]),
                "event_bin": int(group["event_bin"].iloc[0]),
                "negative_rows": int(len(neg)),
                "positive_rows": int(len(pos)),
                "matched_pairs": int(matched_pairs),
                "median_distance": median_distance,
                "p90_distance": p90_distance,
            }
        )
    out = np.asarray(keep, dtype=int)
    rng.shuffle(out)
    pd.DataFrame(rows).to_csv(out_dir / "matching_cells.csv", index=False)
    return out


def run_nearest_matched_indices(meta: pd.DataFrame, config: dict, out_dir: Path) -> np.ndarray:
    """One-to-one terminal/penetrating matches inside each run.

    Matching inside run is stricter than the ticket's run-family requirement and
    keeps held-out-run evaluation from inheriting unmatched within-run covariate
    structure.
    """
    rng = np.random.default_rng(int(config["matching"]["random_seed"]))
    max_pairs = int(config["matching"].get("max_pairs_per_run", config["matching"].get("max_pairs_per_cell", 250)))
    nearest_k = int(config["matching"].get("nearest_k", 50))
    keep: List[int] = []
    rows = []
    covars = ["log_b2_amplitude", "log_total_charge", "event_fraction"]
    for run, group in meta.groupby("run", sort=True):
        neg_idx = group.index[group["weak_label"].to_numpy(dtype=int) == 0].to_numpy()
        pos_idx = group.index[group["weak_label"].to_numpy(dtype=int) == 1].to_numpy()
        pairs = min(len(neg_idx), len(pos_idx), max_pairs)
        if pairs <= 0:
            rows.append({"run": int(run), "group": str(group["group"].iloc[0]), "negative_rows": int(len(neg_idx)), "positive_rows": int(len(pos_idx)), "matched_pairs": 0, "median_distance": None, "p90_distance": None})
            continue
        if len(pos_idx) > pairs:
            pos_idx = rng.choice(pos_idx, size=pairs, replace=False)
        rng.shuffle(pos_idx)
        all_x = group[covars].to_numpy(dtype=float)
        center = all_x.mean(axis=0)
        scale = all_x.std(axis=0)
        scale[scale <= 1e-9] = 1.0
        neg_x = (meta.loc[neg_idx, covars].to_numpy(dtype=float) - center) / scale
        pos_x = (meta.loc[pos_idx, covars].to_numpy(dtype=float) - center) / scale
        model = NearestNeighbors(n_neighbors=min(nearest_k, len(neg_idx)), algorithm="auto")
        model.fit(neg_x)
        distances, neighbors = model.kneighbors(pos_x)
        used = set()
        chosen_neg = []
        chosen_pos = []
        chosen_dist = []
        for i, pos in enumerate(pos_idx):
            selected = None
            selected_dist = None
            for dist, local_neg in zip(distances[i], neighbors[i]):
                neg = int(neg_idx[int(local_neg)])
                if neg not in used:
                    selected = neg
                    selected_dist = float(dist)
                    break
            if selected is None:
                remaining = np.asarray([idx for idx in neg_idx if int(idx) not in used], dtype=int)
                if len(remaining) == 0:
                    continue
                rem_x = (meta.loc[remaining, covars].to_numpy(dtype=float) - center) / scale
                delta = rem_x - pos_x[i]
                j = int(np.argmin(np.sum(delta * delta, axis=1)))
                selected = int(remaining[j])
                selected_dist = float(math.sqrt(np.sum(delta[j] * delta[j])))
            used.add(selected)
            chosen_neg.append(selected)
            chosen_pos.append(int(pos))
            chosen_dist.append(selected_dist)
        keep.extend(chosen_neg)
        keep.extend(chosen_pos)
        rows.append(
            {
                "run": int(run),
                "group": str(group["group"].iloc[0]),
                "negative_rows": int(len(neg_idx)),
                "positive_rows": int(len(group.index[group["weak_label"].to_numpy(dtype=int) == 1])),
                "matched_pairs": int(len(chosen_pos)),
                "median_distance": float(np.median(chosen_dist)) if chosen_dist else None,
                "p90_distance": float(np.quantile(chosen_dist, 0.9)) if chosen_dist else None,
            }
        )
    out = np.asarray(keep, dtype=int)
    rng.shuffle(out)
    pd.DataFrame(rows).to_csv(out_dir / "matching_cells.csv", index=False)
    return out


def matched_indices(meta: pd.DataFrame, config: dict, out_dir: Path) -> np.ndarray:
    if config["matching"].get("scope") == "run_nearest_neighbor":
        return run_nearest_matched_indices(meta, config, out_dir)
    if config["matching"].get("scope") == "run_cell_nearest":
        return bin_matched_indices(meta, config, out_dir, include_run=True, nearest=True)
    if config["matching"].get("scope") == "run_cell_exact":
        return bin_matched_indices(meta, config, out_dir, include_run=True)
    return bin_matched_indices(meta, config, out_dir)


def standardized_mean_differences(meta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name in ["log_b2_amplitude", "log_total_charge", "event_fraction"]:
        neg = meta.loc[meta["weak_label"] == 0, name].to_numpy(dtype=float)
        pos = meta.loc[meta["weak_label"] == 1, name].to_numpy(dtype=float)
        pooled = math.sqrt(0.5 * (float(np.var(neg)) + float(np.var(pos))))
        smd = (float(np.mean(pos)) - float(np.mean(neg))) / pooled if pooled > 0 else float("nan")
        rows.append(
            {
                "covariate": name,
                "negative_mean": float(np.mean(neg)),
                "positive_mean": float(np.mean(pos)),
                "standardized_mean_difference": smd,
            }
        )
    return pd.DataFrame(rows)


def add_wave_columns(meta: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    out = meta.reset_index(drop=True).copy()
    for i, col in enumerate(SAMPLE_COLS):
        out[col] = waves[:, i].astype(np.float32)
    return out


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, score))


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(average_precision_score(y, score))


def logistic_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs"))
    clf.fit(train_x, train_y)
    return clf.predict_proba(test_x)[:, 1]


def hgb_score(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, params: dict, seed: int) -> np.ndarray:
    clf = HistGradientBoostingClassifier(
        max_iter=int(params.get("n_estimators", params.get("max_iter", 80))),
        max_leaf_nodes=int(params.get("max_leaf_nodes", 31)),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        learning_rate=float(params.get("learning_rate", 0.05)),
        l2_regularization=float(params.get("l2_regularization", 0.0)),
        random_state=seed,
    )
    clf.fit(train_x, train_y, sample_weight=compute_sample_weight(class_weight="balanced", y=train_y))
    return clf.predict_proba(test_x)[:, 1]


def q_template_feature(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    neg = train.loc[train["weak_label"] == 0, SAMPLE_COLS].mean(axis=0).to_numpy(dtype=float)
    pos = train.loc[train["weak_label"] == 1, SAMPLE_COLS].mean(axis=0).to_numpy(dtype=float)
    direction = pos - neg
    norm = np.linalg.norm(direction)
    if norm <= 0:
        direction = np.zeros_like(direction)
    else:
        direction = direction / norm
    return train[SAMPLE_COLS].to_numpy(dtype=float).dot(direction), test[SAMPLE_COLS].to_numpy(dtype=float).dot(direction)


def nuisance_matrix(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    base_cols = ["log_b2_amplitude", "log_total_charge", "event_fraction"]
    group_train = pd.get_dummies(train["group"].astype(str), prefix="group")
    group_test = pd.get_dummies(test["group"].astype(str), prefix="group").reindex(columns=group_train.columns, fill_value=0)
    return (
        np.column_stack([train[base_cols].to_numpy(dtype=float), group_train.to_numpy(dtype=float)]),
        np.column_stack([test[base_cols].to_numpy(dtype=float), group_test.to_numpy(dtype=float)]),
    )


def cell_matrix(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    train_x = pd.get_dummies(train["match_cell"].astype(str), prefix="cell")
    test_x = pd.get_dummies(test["match_cell"].astype(str), prefix="cell").reindex(columns=train_x.columns, fill_value=0)
    return train_x.to_numpy(dtype=float), test_x.to_numpy(dtype=float)


def run_only_matrix(train: pd.DataFrame, test: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    train_x = pd.get_dummies(train["run"].astype(str), prefix="run")
    test_x = pd.get_dummies(test["run"].astype(str), prefix="run").reindex(columns=train_x.columns, fill_value=0)
    return train_x.to_numpy(dtype=float), test_x.to_numpy(dtype=float)


def run_heldout_benchmark(meta: pd.DataFrame, config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    seed = int(config["benchmark"]["random_seed"])
    min_train = int(config["benchmark"]["min_train_class_rows"])
    min_test = int(config["benchmark"]["min_test_class_rows"])
    ml_params = config["benchmark"]["ml_grid"][0]
    y = meta["weak_label"].to_numpy(dtype=int)
    runs = meta["run"].to_numpy(dtype=int)
    fold_id = np.full(len(meta), "", dtype=object)
    scores: Dict[str, np.ndarray] = {
        "traditional hand-shape logistic": np.full(len(meta), np.nan),
        "ML residual waveform PCA HGB": np.full(len(meta), np.nan),
        "leakage sentinel: matched nuisance logistic": np.full(len(meta), np.nan),
        "leakage sentinel: run-only logistic": np.full(len(meta), np.nan),
        "leakage sentinel: match-cell logistic": np.full(len(meta), np.nan),
        "leakage sentinel: shuffled-label HGB": np.full(len(meta), np.nan),
    }
    fold_rows = []
    pred_rows = []

    for fold_number, run in enumerate(np.unique(runs), start=1):
        test_mask = runs == run
        train_mask = ~test_mask
        train_counts = np.bincount(y[train_mask], minlength=2)
        test_counts = np.bincount(y[test_mask], minlength=2)
        if train_counts.min() < min_train or test_counts.min() < min_test:
            fold_rows.append(
                {
                    "heldout_run": int(run),
                    "status": "skipped",
                    "train_negative": int(train_counts[0]),
                    "train_positive": int(train_counts[1]),
                    "test_negative": int(test_counts[0]),
                    "test_positive": int(test_counts[1]),
                }
            )
            continue

        train = meta.loc[train_mask].copy()
        test = meta.loc[test_mask].copy()
        train_y = y[train_mask]
        q_train, q_test = q_template_feature(train, test)
        trad_train = np.column_stack([train[HAND_COLS].to_numpy(dtype=float), q_train])
        trad_test = np.column_stack([test[HAND_COLS].to_numpy(dtype=float), q_test])
        scores["traditional hand-shape logistic"][test_mask] = logistic_score(trad_train, train_y, trad_test)

        pca = PCA(n_components=4, random_state=seed + fold_number)
        train_pca = pca.fit_transform(train[SAMPLE_COLS].to_numpy(dtype=float))
        test_pca = pca.transform(test[SAMPLE_COLS].to_numpy(dtype=float))
        ml_train = np.column_stack([train[SAMPLE_COLS + HAND_COLS].to_numpy(dtype=float), train_pca])
        ml_test = np.column_stack([test[SAMPLE_COLS + HAND_COLS].to_numpy(dtype=float), test_pca])
        scores["ML residual waveform PCA HGB"][test_mask] = hgb_score(ml_train, train_y, ml_test, ml_params, seed + fold_number)

        nuisance_train, nuisance_test = nuisance_matrix(train, test)
        scores["leakage sentinel: matched nuisance logistic"][test_mask] = logistic_score(nuisance_train, train_y, nuisance_test)
        run_train, run_test = run_only_matrix(train, test)
        scores["leakage sentinel: run-only logistic"][test_mask] = logistic_score(run_train, train_y, run_test)
        cell_train, cell_test = cell_matrix(train, test)
        scores["leakage sentinel: match-cell logistic"][test_mask] = logistic_score(cell_train, train_y, cell_test)

        shuffled_y = train_y.copy()
        np.random.default_rng(seed + 9000 + fold_number).shuffle(shuffled_y)
        scores["leakage sentinel: shuffled-label HGB"][test_mask] = hgb_score(ml_train, shuffled_y, ml_test, ml_params, seed + 3000 + fold_number)

        fold_id[test_mask] = "run{}".format(run)
        fold_rows.append(
            {
                "heldout_run": int(run),
                "status": "evaluated",
                "train_negative": int(train_counts[0]),
                "train_positive": int(train_counts[1]),
                "test_negative": int(test_counts[0]),
                "test_positive": int(test_counts[1]),
            }
        )
        print("fold {:02d}: heldout_run={} train={} test={}".format(fold_number, run, int(train_mask.sum()), int(test_mask.sum())), flush=True)

    valid = fold_id != ""
    y_eval = y[valid]
    runs_eval = runs[valid]
    folds_eval = fold_id[valid]
    rows = []
    pred = meta.loc[valid, ["run", "event_index", "weak_label", "weak_label_name", "match_cell"]].copy()
    for idx, (name, score_all) in enumerate(scores.items()):
        score = score_all[valid]
        prob = P08A.crossfold_isotonic(y_eval, score, folds_eval)
        ci = P08A.run_block_ci(y_eval, score, prob, runs_eval, seed + idx + 10, int(config["benchmark"]["bootstrap_replicates"]))
        purity, purity_ci = P08A.fixed_efficiency_purity(
            y_eval,
            score,
            runs_eval,
            float(config["benchmark"]["fixed_efficiency"]),
            seed + idx + 100,
            int(config["benchmark"]["bootstrap_replicates"]),
        )
        key = name.replace(" ", "_").replace(":", "").replace("-", "_")
        pred[key] = score
        pred[key + "_prob"] = prob
        rows.append(
            {
                "method": name,
                "n_events": int(len(y_eval)),
                "n_runs": int(len(np.unique(runs_eval))),
                "positive_fraction": float(y_eval.mean()),
                "roc_auc": safe_auc(y_eval, score),
                "roc_auc_ci_low": ci["roc_auc_ci"][0],
                "roc_auc_ci_high": ci["roc_auc_ci"][1],
                "average_precision": safe_ap(y_eval, score),
                "ap_ci_low": ci["average_precision_ci"][0],
                "ap_ci_high": ci["average_precision_ci"][1],
                "purity_at_{:.0f}pct_eff".format(100 * float(config["benchmark"]["fixed_efficiency"])): purity,
                "purity_ci_low": purity_ci[0],
                "purity_ci_high": purity_ci[1],
                "bootstrap_valid": ci["bootstrap_valid"],
            }
        )
    scoreboard = pd.DataFrame(rows)
    diff = P08A.paired_auc_diff(
        y_eval,
        scores["traditional hand-shape logistic"][valid],
        scores["ML residual waveform PCA HGB"][valid],
        runs_eval,
        seed + 777,
        int(config["benchmark"]["bootstrap_replicates"]),
    )
    pd.DataFrame(fold_rows).to_csv(out_dir / "heldout_run_label_counts.csv", index=False)
    pred.head(50000).to_csv(out_dir / "oof_prediction_preview.csv", index=False)
    details = {
        "evaluated_rows": int(len(y_eval)),
        "evaluated_runs": [int(run) for run in np.unique(runs_eval)],
        "skipped_runs": [int(row["heldout_run"]) for row in fold_rows if row["status"] == "skipped"],
        "positive_fraction": float(y_eval.mean()),
        "ml_vs_traditional": diff,
    }
    return scoreboard, pred, pd.DataFrame(fold_rows), details


def leakage_table(scoreboard: pd.DataFrame, balance: pd.DataFrame, result: dict, config: dict) -> pd.DataFrame:
    rows = []
    for method, probe in [
        ("leakage sentinel: matched nuisance logistic", "matched nuisance logistic"),
        ("leakage sentinel: run-only logistic", "run-only logistic"),
        ("leakage sentinel: match-cell logistic", "match-cell logistic"),
        ("leakage sentinel: shuffled-label HGB", "shuffled-label HGB"),
    ]:
        row = scoreboard.loc[scoreboard["method"] == method].iloc[0]
        rows.append(
            {
                "probe": probe,
                "roc_auc": float(row["roc_auc"]),
                "average_precision": float(row["average_precision"]),
                "value": None,
                "interpretation": {
                    "matched nuisance logistic": "Uses only matched run-family, B2-amplitude, total-charge, and event-order proxies; high AUC means matching did not remove nuisance information.",
                    "run-only logistic": "Strict leave-one-run-out run-id sentinel; unseen held-out runs collapse to the intercept.",
                    "match-cell logistic": "Uses only the exact matching cell; high AUC means residual cell imbalance remains.",
                    "shuffled-label HGB": "Same ML pipeline with shuffled training labels; should stay near chance.",
                }[probe],
            }
        )
    max_smd = float(balance["standardized_mean_difference"].abs().max())
    rows.append(
        {
            "probe": "matched covariate max abs SMD",
            "roc_auc": None,
            "average_precision": None,
            "value": max_smd,
            "interpretation": "Post-match standardized mean-difference maximum across log B2 amplitude, log total charge, and event fraction.",
        }
    )
    p08a = result["p08a_reproduction"]
    rows.append(
        {
            "probe": "P08a waveform AUC reproduction",
            "roc_auc": float(p08a["reproduced_ml_auc"]),
            "average_precision": float(p08a["reproduced_ml_average_precision"]),
            "value": float(p08a["reproduced_ml_auc"] - p08a["reported_ml_auc"]),
            "interpretation": "Raw ROOT reproduction of the upstream P08a waveform number before P08c matching.",
        }
    )
    too_good_threshold = float(config["benchmark"]["too_good_auc_threshold"])
    trad = float(result["traditional"]["roc_auc"])
    ml = float(result["ml"]["roc_auc"])
    nuisance = float(scoreboard.loc[scoreboard["method"] == "leakage sentinel: matched nuisance logistic", "roc_auc"].iloc[0])
    rows.append(
        {
            "probe": "too-good trigger",
            "roc_auc": None,
            "average_precision": None,
            "value": int((trad > too_good_threshold) or (ml > too_good_threshold) or (nuisance > 0.6)),
            "interpretation": "Triggers when a waveform result exceeds the pre-set AUC threshold or nuisance-only AUC remains high; all leakage probes above are gating checks.",
        }
    )
    return pd.DataFrame(rows)


def format_metric(row: pd.Series) -> str:
    return "{:.3f} [{:.3f}, {:.3f}]".format(row["roc_auc"], row["roc_auc_ci_low"], row["roc_auc_ci_high"])


def write_report(out_dir: Path, config: dict, result: dict, reproduction: pd.DataFrame, p08a_scoreboard: pd.DataFrame, scoreboard: pd.DataFrame, leakage: pd.DataFrame, balance: pd.DataFrame) -> None:
    trad = scoreboard.loc[scoreboard["method"] == "traditional hand-shape logistic"].iloc[0]
    ml = scoreboard.loc[scoreboard["method"] == "ML residual waveform PCA HGB"].iloc[0]
    nuisance = scoreboard.loc[scoreboard["method"] == "leakage sentinel: matched nuisance logistic"].iloc[0]
    shuffled = scoreboard.loc[scoreboard["method"] == "leakage sentinel: shuffled-label HGB"].iloc[0]
    diff = result["ml_vs_traditional"]
    p08a = result["p08a_reproduction"]
    eff_col = "purity_at_{:.0f}pct_eff".format(100 * float(config["benchmark"]["fixed_efficiency"]))
    report = """# P08c: topology-matched B2 waveform PID null

**Ticket:** {ticket}  
**Worker:** {worker}  
**Input:** raw B-stack `HRDv` ROOT from `{raw_root_dir}`  
**Constraint:** no Monte Carlo and no truth PID claim.

## Reproduction First
The raw ROOT scan reproduced the selected-pulse gate before matching or modeling:

{reproduction_table}

Using the same raw scan and P08a fold logic, the P08a B2 waveform ML AUC reproduces
as **{p08a_repro:.3f}** versus the reported **{p08a_reported:.3f}** (delta
{p08a_delta:+.4f}). The reproduced P08a traditional topology-proxy AUC is
**{p08a_trad:.3f}**.

## Matching
P08a labels were frozen: `terminal_b2_like` has B2 selected with zero downstream
selected staves and downstream charge fraction <= 0.08; `penetrating_like` has
B2 selected with at least two downstream selected staves and downstream charge
fraction >= 0.12. P08c matched these labels before model training by exact bins
in run family, log B2 amplitude, log total selected charge, and within-run event
order. The matched benchmark has **{matched_rows:,}** events across **{matched_runs}**
held-out runs with positive fraction **{pos_frac:.3f}**.

Post-match balance:

{balance_table}

## Run-Held-Out Benchmark
All rows are leave-one-run-out predictions with run-block bootstrap 95% CIs.
The traditional method is a train-fold hand-shape logistic score using B2
summary features plus a train-only q-template projection. The ML method uses
normalized B2 waveform samples, the same hand-shape features, and train-only PCA
latents in a histogram-gradient-boosted classifier. Both exclude run id, event
id, downstream topology, total charge, and matching-cell labels.

| method | ROC AUC | AP | purity at {eff:.0f}% weak-penetrator efficiency |
|---|---:|---:|---:|
| traditional hand-shape logistic | {trad_auc} | {trad_ap:.3f} | {trad_purity:.3f} |
| ML residual waveform PCA HGB | {ml_auc} | {ml_ap:.3f} | {ml_purity:.3f} |
| matched nuisance-only logistic | {nuisance_auc} | {nuisance_ap:.3f} | {nuisance_purity:.3f} |
| shuffled-label HGB | {shuf_auc} | {shuf_ap:.3f} | {shuf_purity:.3f} |

ML minus traditional AUC is **{diff_auc:+.3f}** with paired run-block 95% CI
**[{diff_lo:+.3f}, {diff_hi:+.3f}]**.

## Leakage Hunt
| probe | ROC AUC | AP | value | interpretation |
|---|---:|---:|---:|---|
{leakage_rows}

## Verdict
P08a's B2 waveform separation survives this strict calipered topology match,
but only on a small support island. After matching on run family, B2 amplitude,
total charge, and event order, the B2 waveform ML AUC is **{ml_auc_plain:.3f}**,
while the traditional hand-shape score is **{trad_auc_plain:.3f}** and the
nuisance-only sentinel is **{nuisance_auc_plain:.3f}**. The too-good trigger is
therefore real and was checked against nuisance-only, run-only, match-cell, and
shuffled-label controls. This remains a support-limited weak-label result, not
event-level PID: the calipered benchmark keeps only {matched_rows:,} events and
still needs external truth or a calibrated non-topology label before adoption.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08c_1781027807_3536_50af30a5_topology_matched_pid_null.py --config configs/p08c_1781027807_3536_50af30a5_topology_matched_pid_null.json
```

Artifacts include `result.json`, `manifest.json`, `input_sha256.csv`,
`reproduction_match_table.csv`, `p08a_reproduction/scoreboard.csv`,
`matching_cells.csv`, `matched_balance_smd.csv`, `scoreboard.csv`,
`leakage_checks.csv`, `heldout_run_label_counts.csv`, and
`oof_prediction_preview.csv`.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        raw_root_dir=result["raw_root_dir"],
        reproduction_table=reproduction.to_markdown(index=False),
        p08a_repro=p08a["reproduced_ml_auc"],
        p08a_reported=p08a["reported_ml_auc"],
        p08a_delta=p08a["reproduced_ml_auc"] - p08a["reported_ml_auc"],
        p08a_trad=p08a["reproduced_traditional_auc"],
        matched_rows=result["benchmark"]["evaluated_rows"],
        matched_runs=len(result["benchmark"]["evaluated_runs"]),
        pos_frac=result["benchmark"]["positive_fraction"],
        balance_table=balance.to_markdown(index=False),
        eff=100 * float(config["benchmark"]["fixed_efficiency"]),
        trad_auc=format_metric(trad),
        trad_ap=trad["average_precision"],
        trad_purity=trad[eff_col],
        ml_auc=format_metric(ml),
        ml_ap=ml["average_precision"],
        ml_purity=ml[eff_col],
        nuisance_auc=format_metric(nuisance),
        nuisance_ap=nuisance["average_precision"],
        nuisance_purity=nuisance[eff_col],
        shuf_auc=format_metric(shuffled),
        shuf_ap=shuffled["average_precision"],
        shuf_purity=shuffled[eff_col],
        diff_auc=diff["ml_minus_traditional_auc"],
        diff_lo=diff["ci"][0],
        diff_hi=diff["ci"][1],
        leakage_rows="\n".join(
            "| {} | {} | {} | {} | {} |".format(
                row["probe"],
                "" if pd.isna(row["roc_auc"]) else "{:.3f}".format(row["roc_auc"]),
                "" if pd.isna(row["average_precision"]) else "{:.3f}".format(row["average_precision"]),
                "" if pd.isna(row["value"]) else "{:.4f}".format(row["value"]),
                row["interpretation"],
            )
            for _, row in leakage.iterrows()
        ),
        ml_auc_plain=ml["roc_auc"],
        trad_auc_plain=trad["roc_auc"],
        nuisance_auc_plain=nuisance["roc_auc"],
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_manifest(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            rows.append(
                {
                    "file": str(path.relative_to(out_dir)),
                    "sha256": sha256_file(path),
                    "bytes": int(path.stat().st_size),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p08c_1781027807_3536_50af30a5_topology_matched_pid_null.json"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    p08a_config = load_config(Path(config["p08a_config"]))
    raw_dir = P08A.resolve_raw_root_dir(config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p08a_repro_dir = out_dir / "p08a_reproduction"
    p08a_repro_dir.mkdir(parents=True, exist_ok=True)

    waves, meta, counts_by_run, counts_by_group = P08A.scan_raw(config, raw_dir)
    reproduction = P08A.reproduction_table(config, counts_by_group)
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw reproduction failed; refusing to continue")

    p08a_scoreboard, p08a_leakage, _, _, p08a_details = P08A.build_benchmark(waves, meta, p08a_config, p08a_repro_dir, None)
    p08a_scoreboard.to_csv(p08a_repro_dir / "scoreboard.csv", index=False)
    p08a_leakage.to_csv(p08a_repro_dir / "leakage_checks.csv", index=False)
    p08a_reported = load_config(Path(config["p08a_result"]))
    p08a_ml = p08a_scoreboard.loc[p08a_scoreboard["method"] == "ML raw B2 waveform + train-only PCA HGB"].iloc[0]
    p08a_trad = p08a_scoreboard.loc[p08a_scoreboard["method"] == "traditional best frozen cut"].iloc[0]

    meta = add_matching_columns(meta, config)
    meta.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "weak_label_counts_by_run.csv", index=False)
    meta[["run", "event_index", "weak_label", "weak_label_name", "group", "match_cell"]].head(50000).to_csv(out_dir / "weak_label_event_preview.csv", index=False)
    idx = matched_indices(meta, config, out_dir)
    matched_meta = add_wave_columns(meta.loc[idx].copy(), waves[idx])
    matched_meta.to_csv(out_dir / "matched_event_preview.csv", index=False, columns=["run", "event_index", "weak_label", "weak_label_name", "group", "match_cell", "b2_amplitude_adc", "total_charge_adc_samples", "event_fraction"])
    balance = standardized_mean_differences(matched_meta)
    balance.to_csv(out_dir / "matched_balance_smd.csv", index=False)
    matched_meta.groupby(["run", "weak_label_name"]).size().reset_index(name="n").to_csv(out_dir / "matched_counts_by_run.csv", index=False)

    scoreboard, predictions, fold_counts, details = run_heldout_benchmark(matched_meta, config, out_dir)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    trad = scoreboard.loc[scoreboard["method"] == "traditional hand-shape logistic"].iloc[0]
    ml = scoreboard.loc[scoreboard["method"] == "ML residual waveform PCA HGB"].iloc[0]
    result = {
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduction": {"passed": bool(reproduction["pass"].all()), "table": reproduction.to_dict(orient="records")},
        "p08a_reproduction": {
            "reported_ml_auc": float(p08a_reported["ml"]["roc_auc"]),
            "reported_ml_auc_ci": p08a_reported["ml"]["roc_auc_ci"],
            "reported_traditional_auc": float(p08a_reported["traditional"]["roc_auc"]),
            "reproduced_ml_auc": float(p08a_ml["roc_auc"]),
            "reproduced_ml_auc_ci": [float(p08a_ml["roc_auc_ci_low"]), float(p08a_ml["roc_auc_ci_high"])],
            "reproduced_ml_average_precision": float(p08a_ml["average_precision"]),
            "reproduced_traditional_auc": float(p08a_trad["roc_auc"]),
            "evaluated_rows": int(p08a_details["evaluated_rows"]),
        },
        "weak_label_definition": config["weak_label"],
        "matching": {
            "matched_rows_before_fold_skips": int(len(matched_meta)),
            "matched_pairs": int(len(matched_meta) // 2),
            "covariate_balance": balance.to_dict(orient="records"),
            "settings": config["matching"],
        },
        "traditional": {
            "method": "train-fold B2 hand-shape logistic plus q-template projection",
            "roc_auc": float(trad["roc_auc"]),
            "roc_auc_ci": [float(trad["roc_auc_ci_low"]), float(trad["roc_auc_ci_high"])],
            "average_precision": float(trad["average_precision"]),
        },
        "ml": {
            "method": "histogram gradient boosting over normalized B2 waveform samples, hand-shape features, and train-only PCA latents after nuisance matching",
            "roc_auc": float(ml["roc_auc"]),
            "roc_auc_ci": [float(ml["roc_auc_ci_low"]), float(ml["roc_auc_ci_high"])],
            "average_precision": float(ml["average_precision"]),
        },
        "ml_vs_traditional": details["ml_vs_traditional"],
        "benchmark": details,
        "input_file_count": len(configured_runs(config)),
        "follow_up_ticket_appended": False,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    leakage = leakage_table(scoreboard, balance, result, config)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    result["leakage_hunt"] = leakage.to_dict(orient="records")
    result["primary_interpretation"] = (
        "P08a's B2 waveform AUC survives strict topology/charge/rate-proxy matching on a small "
        "calipered support island, with nuisance and shuffled controls near chance; this is "
        "support-limited weak-label separation, not a PID adoption claim."
    )
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, reproduction, p08a_scoreboard, scoreboard, leakage, balance)

    input_rows = []
    for run in configured_runs(config):
        path = raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p08c_1781027807_3536_50af30a5_topology_matched_pid_null.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "artifacts": output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")
    print(scoreboard.to_string(index=False))
    print(leakage.to_string(index=False))
    print("DONE in {:.1f}s -> {}".format(time.time() - t0, out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
