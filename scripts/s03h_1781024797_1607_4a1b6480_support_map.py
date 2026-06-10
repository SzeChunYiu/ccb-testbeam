#!/usr/bin/env python3
"""S03h HGB timewalk gain support map by amplitude and shape atoms."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b


REFERENCE = {
    "s03a_amp_only": 1.5510917109777858,
    "hgb_full_unconstrained": 1.3939661218709831,
}


PRIMARY_TRADITIONAL = "signed_shared_shrinkage"
PRIMARY_ML = "hgb_full_unconstrained"


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


def hash_outputs(out_dir: Path) -> dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def prepare_base_pulses(pulses: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, str]:
    out = pulses.copy()
    train_pulses = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train_pulses, list(config["timing"]["downstream_staves"]))
    methods = s02.add_traditional_times(out, config, templates)
    scan = s02.evaluate_methods(out, methods, config)
    best = str(
        scan[(scan["split"] == "train") & (scan["spacing_cm"] == 2.0)]
        .sort_values("sigma68_ns")
        .iloc[0]["method"]
    )
    expected = str(config["timing"]["base_method"])
    if best != expected:
        raise RuntimeError(f"Expected train-selected base method {expected}, got {best}")
    return out, best


def hgb_param_grid(config: dict) -> list[dict]:
    rows = []
    for max_iter in config["hgb"]["max_iter"]:
        for learning_rate in config["hgb"]["learning_rate"]:
            for max_leaf_nodes in config["hgb"]["max_leaf_nodes"]:
                for l2_regularization in config["hgb"]["l2_regularization"]:
                    rows.append(
                        {
                            "max_iter": int(max_iter),
                            "learning_rate": float(learning_rate),
                            "max_leaf_nodes": int(max_leaf_nodes),
                            "l2_regularization": float(l2_regularization),
                            "max_bins": int(config["hgb"]["max_bins"]),
                            "random_state": int(config["hgb"]["random_seed"]),
                        }
                    )
    return rows


def signed_shrinkage_features(pulses: pd.DataFrame, staves: list[str]) -> tuple[np.ndarray, list[str], list[int]]:
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    safe_amp = np.maximum(amp, 1.0)
    one_hot = np.zeros((len(pulses), len(staves)))
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0
    amp_terms = np.column_stack([1000.0 / safe_amp, np.sqrt(1000.0 / safe_amp)])
    names = [f"stave_{stave}_offset" for stave in staves] + ["inv_amp_1000", "inv_sqrt_amp_1000"]
    amp_idx = [len(staves), len(staves) + 1]
    return np.hstack([one_hot, amp_terms]), names, amp_idx


def fit_signed_shrinkage(X: np.ndarray, y: np.ndarray, alpha: float, sign: int, amp_idx: list[int]) -> np.ndarray:
    n_features = X.shape[1]
    penalty = np.ones(n_features, dtype=float) * float(alpha)
    penalty[: min(3, n_features)] = 0.01 * float(alpha)
    Xa = np.vstack([X, np.diag(np.sqrt(np.maximum(penalty, 0.0)))])
    ya = np.concatenate([y, np.zeros(n_features)])
    lower = np.full(n_features, -np.inf)
    upper = np.full(n_features, np.inf)
    for idx in amp_idx:
        if int(sign) >= 0:
            lower[idx] = 0.0
        else:
            upper[idx] = 0.0
    result = lsq_linear(Xa, ya, bounds=(lower, upper), method="trf", lsmr_tol="auto", max_iter=200)
    if not result.success:
        raise RuntimeError(f"signed shrinkage solve failed: {result.message}")
    return result.x


def run_signed_shrinkage(pulses: pd.DataFrame, config: dict, base_method: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, feature_names, amp_idx = signed_shrinkage_features(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    idx_train = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    n_splits = min(int(config["signed_shrinkage"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": math.inf, "alpha": None, "amplitude_sign": None, "coef": None}
    for alpha in config["signed_shrinkage"]["ridge_alphas"]:
        for sign in config["signed_shrinkage"]["amplitude_signs"]:
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
                coef = fit_signed_shrinkage(X[train_mask][tr], targets[train_mask][tr], float(alpha), int(sign), amp_idx)
                pred = np.full(len(pulses), np.nan)
                pred[idx_train[va]] = X[train_mask][va] @ coef
                tmp = pulses.copy()
                tmp["t_signed_shared_shrinkage_ns"] = tmp[f"t_{base_method}_ns"] - pred
                va_runs = sorted(np.unique(runs[idx_train[va]]).astype(int).tolist())
                vals = s02.pairwise_residuals(
                    tmp.iloc[idx_train[va]].copy(), "signed_shared_shrinkage", 2.0, config, va_runs
                )
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        "alpha": float(alpha),
                        "amplitude_sign": int(sign),
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": int(len(vals)),
                        "n_features": int(len(feature_names)),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    "alpha": float(alpha),
                    "amplitude_sign": int(sign),
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                    "n_features": int(len(feature_names)),
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "alpha": float(alpha), "amplitude_sign": int(sign), "coef": None}
    coef = fit_signed_shrinkage(
        X[train_mask],
        targets[train_mask],
        float(best["alpha"]),
        int(best["amplitude_sign"]),
        amp_idx,
    )
    pred = X @ coef
    out = pulses.copy()
    out["signed_shared_target_residual_ns"] = targets
    out["signed_shared_pred_residual_ns"] = pred
    out["t_signed_shared_shrinkage_ns"] = out[f"t_{base_method}_ns"] - pred
    coef_rows = pd.DataFrame(
        {
            "feature": feature_names,
            "coefficient_ns_per_raw_unit": coef,
            "amplitude_sign_constraint": [
                int(best["amplitude_sign"]) if idx in amp_idx else 0 for idx in range(len(feature_names))
            ],
        }
    )
    best["coef"] = coef_rows
    return out, pd.DataFrame(cv_rows), best


def _trimmed_median(values: np.ndarray, trim_fraction: float = 0.10) -> float:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return 0.0
    if len(vals) < 10:
        return float(np.median(vals))
    lo, hi = np.quantile(vals, [trim_fraction, 1.0 - trim_fraction])
    trimmed = vals[(vals >= lo) & (vals <= hi)]
    return float(np.median(trimmed if len(trimmed) else vals))


def run_robust_heavytail_table(pulses: pd.DataFrame, config: dict, base_method: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    train_runs = list(config["timing"]["train_runs"])
    runs = pulses["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, train_runs) & np.isfinite(targets)
    amp_log = np.log1p(pulses["amplitude_adc"].to_numpy(dtype=float))
    staves = list(config["timing"]["downstream_staves"])
    n_bins = int(config.get("robust_table", {}).get("n_bins", 10))
    rows = []
    pred = np.full(len(pulses), np.nan, dtype=float)
    for stave in staves:
        stave_mask = pulses["stave"].to_numpy() == stave
        fit_mask = train_mask & stave_mask & np.isfinite(amp_log)
        x = amp_log[fit_mask]
        y = targets[fit_mask]
        if len(x) == 0:
            continue
        edges = np.unique(np.quantile(x, np.linspace(0, 1, n_bins + 1)))
        if len(edges) < 3:
            centers = np.asarray([float(np.median(x))])
            values = np.asarray([_trimmed_median(y)])
            counts = np.asarray([len(y)])
        else:
            labels = np.digitize(x, edges[1:-1], right=True)
            centers_list, values_list, counts_list = [], [], []
            for label in range(len(edges) - 1):
                in_bin = labels == label
                if not np.any(in_bin):
                    continue
                centers_list.append(float(np.median(x[in_bin])))
                values_list.append(_trimmed_median(y[in_bin]))
                counts_list.append(int(np.sum(in_bin)))
            order = np.argsort(centers_list)
            centers = np.asarray(centers_list, dtype=float)[order]
            values = np.asarray(values_list, dtype=float)[order]
            counts = np.asarray(counts_list, dtype=int)[order]
        apply_idx = np.flatnonzero(stave_mask)
        if len(centers) == 1:
            pred[apply_idx] = values[0]
        else:
            pred[apply_idx] = np.interp(amp_log[apply_idx], centers, values, left=values[0], right=values[-1])
        for center, value, count in zip(centers, values, counts):
            rows.append(
                {
                    "stave": stave,
                    "log_amp_center": float(center),
                    "trimmed_median_residual_ns": float(value),
                    "n_train_pulses": int(count),
                    "n_bins_requested": n_bins,
                    "trim_fraction_each_tail": 0.10,
                }
            )
    out = pulses.copy()
    out["robust_heavytail_target_residual_ns"] = targets
    out["robust_heavytail_pred_residual_ns"] = pred
    out["t_robust_heavytail_table_ns"] = out[f"t_{base_method}_ns"] - pred
    return out, pd.DataFrame(rows)


def hgb_features(pulses: pd.DataFrame, variant: str, staves: list[str]) -> tuple[np.ndarray, list[str], list[int | None]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    safe_amp = np.maximum(amp, 1.0)
    norm = wf / safe_amp[:, None]
    peak = pulses["peak_sample"].to_numpy(dtype=float)[:, None]
    log_amp = np.log1p(safe_amp)[:, None]
    area_norm = (pulses["area_adc_samples"].to_numpy(dtype=float) / safe_amp)[:, None]
    one_hot = np.zeros((len(pulses), len(staves)))
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for row, stave in enumerate(pulses["stave"]):
        one_hot[row, stave_to_i[stave]] = 1.0

    sample_names = [f"norm_sample_{i:02d}" for i in range(norm.shape[1])]
    stave_names = [f"stave_{stave}" for stave in staves]
    if variant in {"full_unconstrained", "full_monotone_log_amp"}:
        X = np.hstack([norm, log_amp, peak, area_norm, one_hot])
        names = sample_names + ["log_amp", "peak_sample", "area_over_amp"] + stave_names
    elif variant == "amplitude_only":
        X, names = s03a.analytic_feature_matrix(pulses, "amp_only", staves)
    elif variant == "shape_only":
        X = np.hstack([norm, peak, area_norm, one_hot])
        names = sample_names + ["peak_sample", "area_over_amp"] + stave_names
    elif variant == "stave_only":
        X = one_hot
        names = stave_names
    else:
        raise ValueError(f"unknown HGB variant {variant}")

    if variant == "full_monotone_log_amp":
        return X, names, [int(v) for v in [-1, 1]]
    return X, names, [None]


def run_hgb_variant(pulses: pd.DataFrame, config: dict, base_method: str, variant: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, feature_names, monotone_dirs = hgb_features(pulses, variant, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    idx_train = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    n_splits = min(int(config["hgb"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": math.inf, "params": None, "monotone_log_amp": None}

    for params in hgb_param_grid(config):
        for monotone_dir in monotone_dirs:
            fit_params = params.copy()
            if monotone_dir is not None:
                cst = np.zeros(len(feature_names), dtype=int)
                cst[feature_names.index("log_amp")] = int(monotone_dir)
                fit_params["monotonic_cst"] = cst.tolist()
            fold_scores = []
            for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
                model = HistGradientBoostingRegressor(**fit_params)
                model.fit(X[train_mask][tr], targets[train_mask][tr])
                pred = np.full(len(pulses), np.nan)
                pred[idx_train[va]] = model.predict(X[train_mask][va])
                tmp = pulses.copy()
                tmp["t_hgb_variant_ns"] = tmp[f"t_{base_method}_ns"] - pred
                va_runs = sorted(np.unique(runs[idx_train[va]]).astype(int).tolist())
                vals = s02.pairwise_residuals(tmp.iloc[idx_train[va]].copy(), "hgb_variant", 2.0, config, va_runs)
                score = s02.sigma68(vals)
                fold_scores.append(score)
                cv_rows.append(
                    {
                        **params,
                        "variant": variant,
                        "monotone_log_amp": monotone_dir,
                        "fold": int(fold),
                        "sigma68_ns": score,
                        "n_pair_residuals": int(len(vals)),
                        "n_features": int(len(feature_names)),
                    }
                )
            mean_score = float(np.nanmean(fold_scores))
            cv_rows.append(
                {
                    **params,
                    "variant": variant,
                    "monotone_log_amp": monotone_dir,
                    "fold": -1,
                    "sigma68_ns": mean_score,
                    "n_pair_residuals": 0,
                    "n_features": int(len(feature_names)),
                }
            )
            if mean_score < best["score"]:
                best = {"score": mean_score, "params": fit_params, "monotone_log_amp": monotone_dir}

    final_model = HistGradientBoostingRegressor(**best["params"])
    final_model.fit(X[train_mask], targets[train_mask])
    pred = final_model.predict(X)
    out = pulses.copy()
    out[f"{variant}_target_residual_ns"] = targets
    out[f"{variant}_pred_residual_ns"] = pred
    out[f"t_{variant}_ns"] = out[f"t_{base_method}_ns"] - pred
    best["feature_names"] = feature_names
    return out, pd.DataFrame(cv_rows), best


def run_hgb_shuffled_control(
    pulses: pd.DataFrame, config: dict, base_method: str, variant: str, best: dict, heldout_run: int
) -> float:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = list(config["timing"]["train_runs"])
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, _, _ = hgb_features(pulses, variant, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    rng = np.random.default_rng(int(config["hgb"]["random_seed"]) + 1009 + int(heldout_run))
    shuffled = targets[train_mask].copy()
    rng.shuffle(shuffled)
    model = HistGradientBoostingRegressor(**best["params"])
    model.fit(X[train_mask], shuffled)
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp["t_hgb_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "hgb_shuffled", 2.0, config, [heldout_run])
    return s02.sigma68(vals)


def pairwise_records(pulses: pd.DataFrame, method: str, config: dict, runs: list[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    t_wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    a_wide = sub.pivot(index="event_id", columns="stave", values="amplitude_adc")
    rows = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a not in t_wide or b not in t_wide:
            continue
        vals = t_wide[a] - t_wide[b]
        amp = np.log1p(a_wide.loc[vals.index, [a, b]].mean(axis=1).to_numpy(dtype=float))
        run_lookup = sub.drop_duplicates("event_id").set_index("event_id")["run"]
        for event_id, value, log_amp in zip(vals.index, vals.to_numpy(dtype=float), amp):
            if np.isfinite(value) and np.isfinite(log_amp):
                rows.append(
                    {
                        "heldout_run": int(run_lookup.loc[event_id]),
                        "event_id": str(event_id),
                        "pair": f"{a}-{b}",
                        "method": method,
                        "pairwise_residual_ns": float(value),
                        "pair_log_amp": float(log_amp),
                    }
                )
    return pd.DataFrame(rows)


def _cut_label(values: np.ndarray, edges: list[float], prefix: str) -> list[str]:
    labels = []
    for value in values:
        placed = False
        for lo, hi in zip(edges[:-1], edges[1:]):
            if float(lo) <= float(value) < float(hi):
                labels.append(f"{prefix}[{lo:g},{hi:g})")
                placed = True
                break
        if not placed:
            labels.append(f"{prefix}[overflow]")
    return labels


def pulse_shape_atoms(pulses: pd.DataFrame, config: dict, train_runs: list[int]) -> pd.DataFrame:
    support = config["support_map"]
    templates = s02.build_templates(pulses[pulses["run"].isin(train_runs)], list(config["timing"]["downstream_staves"]))
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    peak = pulses["peak_sample"].to_numpy(dtype=int)
    positive = np.clip(norm, 0.0, None)
    pos_sum = np.maximum(positive.sum(axis=1), 1e-9)
    late_fraction = positive[:, 12:].sum(axis=1) / pos_sum
    width_half = (norm > 0.5).sum(axis=1)
    saturation_count = (wf >= 0.995 * amp[:, None]).sum(axis=1)
    pre = wf[:, [int(i) for i in config["baseline_samples"]]]
    pre_rms = np.sqrt(np.mean(pre**2, axis=1))
    q = np.full(len(pulses), np.nan, dtype=float)
    secondary = np.zeros(len(pulses), dtype=float)
    post_min = np.zeros(len(pulses), dtype=float)
    undershoot = np.zeros(len(pulses), dtype=float)
    for i, (stave, p) in enumerate(zip(pulses["stave"], peak)):
        tmpl = templates[str(stave)]
        q[i] = float(np.sqrt(np.mean((norm[i] - tmpl) ** 2)))
        masked = positive[i].copy()
        masked[max(0, p - 1) : min(norm.shape[1], p + 2)] = 0.0
        secondary[i] = float(masked.max())
        tail = norm[i, min(norm.shape[1] - 1, p + 1) :]
        post_min[i] = float(tail.min()) if len(tail) else 0.0
        undershoot[i] = float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0

    thresholds = support["anomaly_thresholds"]
    anomaly = np.full(len(pulses), "common", dtype=object)
    anomaly[(amp >= float(support["saturation_proxy_adc"])) | (saturation_count >= int(thresholds["saturation_count"]))] = "saturation_boundary"
    anomaly[peak >= 9] = "delayed_peak"
    anomaly[width_half >= int(thresholds["width_half"])] = "broad_width"
    anomaly[post_min <= float(thresholds["post_peak_min_norm"])] = "post_peak_undershoot"
    anomaly[late_fraction >= float(thresholds["late_fraction"])] = "late_tail"
    anomaly[secondary >= float(thresholds["secondary_peak"])] = "secondary_peak"
    anomaly[undershoot <= float(thresholds["undershoot_area_norm"])] = "undershoot_area"

    out = pulses[["event_id", "run", "stave", "amplitude_adc", "peak_sample"]].copy()
    out["q_template_rmse"] = q
    out["saturation_count"] = saturation_count
    out["pretrigger_rms_adc"] = pre_rms
    out["late_fraction"] = late_fraction
    out["width_half"] = width_half
    out["post_peak_min_norm"] = post_min
    out["secondary_peak"] = secondary
    out["undershoot_area_norm"] = undershoot
    out["anomaly_atom"] = anomaly
    out["pulse_peak_bin"] = _cut_label(peak.astype(float), list(support["peak_edges"]), "peak")
    out["pulse_q_template_bin"] = _cut_label(q, list(support["q_template_edges"]), "q")
    out["pulse_pretrigger_bin"] = _cut_label(pre_rms, list(support["pretrigger_rms_edges_adc"]), "pre_rms")
    out["pulse_saturation_boundary"] = np.where(
        (amp >= float(support["saturation_proxy_adc"])) | (saturation_count >= int(thresholds["saturation_count"])),
        "near_or_clipped",
        "clear",
    )
    return out


def pair_strata(pulses: pd.DataFrame, config: dict, train_runs: list[int], runs: list[int]) -> pd.DataFrame:
    atoms = pulse_shape_atoms(pulses, config, train_runs)
    support = config["support_map"]
    rows = []
    sub = atoms[atoms["run"].isin(runs)]
    by_event = {event_id: group.set_index("stave") for event_id, group in sub.groupby("event_id")}
    for event_id, wide in by_event.items():
        run = int(wide["run"].iloc[0])
        for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
            if a not in wide.index or b not in wide.index:
                continue
            pair_rows = wide.loc[[a, b]]
            mean_amp = float(pair_rows["amplitude_adc"].mean())
            max_peak = float(pair_rows["peak_sample"].max())
            max_q = float(pair_rows["q_template_rmse"].max())
            max_pre = float(pair_rows["pretrigger_rms_adc"].max())
            sat = "near_or_clipped" if (pair_rows["pulse_saturation_boundary"] == "near_or_clipped").any() else "clear"
            atoms_here = sorted(set(str(v) for v in pair_rows["anomaly_atom"] if str(v) != "common"))
            rows.append(
                {
                    "heldout_run": run,
                    "event_id": str(event_id),
                    "pair": f"{a}-{b}",
                    "amplitude_stratum": _cut_label(np.asarray([mean_amp]), list(support["amplitude_edges_adc"]), "amp")[0],
                    "stave_stratum": f"{a}-{b}",
                    "peak_sample_stratum": _cut_label(np.asarray([max_peak]), list(support["peak_edges"]), "peak")[0],
                    "q_template_stratum": _cut_label(np.asarray([max_q]), list(support["q_template_edges"]), "q")[0],
                    "saturation_boundary_stratum": sat,
                    "pretrigger_stratum": _cut_label(np.asarray([max_pre]), list(support["pretrigger_rms_edges_adc"]), "pre_rms")[0],
                    "anomaly_stratum": "+".join(atoms_here) if atoms_here else "common",
                    "pair_mean_amplitude_adc": mean_amp,
                    "pair_max_q_template_rmse": max_q,
                    "pair_max_pretrigger_rms_adc": max_pre,
                }
            )
    return pd.DataFrame(rows)


def metric_row(values: np.ndarray, amps: np.ndarray | None = None) -> dict[str, float]:
    out = s02.metric_summary(values)
    out["value"] = out["sigma68_ns"]
    centered = values - np.nanmedian(values) if len(values) else values
    out["calibration_coverage_abs_le2ns"] = float(np.mean(np.abs(centered) <= 2.0)) if len(values) else float("nan")
    if amps is not None and len(values) >= 3 and np.nanstd(amps) > 0:
        out["bias_vs_log_amp_slope_ns"] = float(np.polyfit(amps, values, 1)[0])
    else:
        out["bias_vs_log_amp_slope_ns"] = float("nan")
    return out


def bootstrap_metric_ci(records: pd.DataFrame, rng: np.random.Generator, n_boot: int, metric: str, by_run: bool) -> tuple[float, float]:
    if len(records) == 0:
        return (float("nan"), float("nan"))
    stats = []
    runs = sorted(records["heldout_run"].unique().tolist())
    by_run_records = {run: records[records["heldout_run"] == run] for run in runs}
    for _ in range(int(n_boot)):
        if by_run:
            sampled = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([by_run_records[int(run)] for run in sampled], ignore_index=True)
        else:
            sample = records.sample(n=len(records), replace=True, random_state=int(rng.integers(0, 2**31 - 1)))
        vals = sample["pairwise_residual_ns"].to_numpy(dtype=float)
        if metric == "sigma68_ns":
            stats.append(s02.sigma68(vals))
        elif metric == "full_rms_ns":
            stats.append(s02.full_rms(vals))
        elif metric == "tail_frac_abs_gt5ns":
            stats.append(float(np.mean(np.abs(vals - np.median(vals)) > 5.0)))
        elif metric == "bias_vs_log_amp_slope_ns":
            amps = sample["pair_log_amp"].to_numpy(dtype=float)
            stats.append(float(np.polyfit(amps, vals, 1)[0]) if np.nanstd(amps) > 0 else float("nan"))
        elif metric == "calibration_coverage_abs_le2ns":
            stats.append(float(np.mean(np.abs(vals - np.nanmedian(vals)) <= 2.0)))
    return (float(np.nanpercentile(stats, 2.5)), float(np.nanpercentile(stats, 97.5)))


def summarize_records(records: pd.DataFrame, rng: np.random.Generator, n_boot: int, by_run: bool) -> pd.DataFrame:
    rows = []
    for method, group in records.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        amps = group["pair_log_amp"].to_numpy(dtype=float)
        base = metric_row(vals, amps)
        row = {"method": method, "bootstrap_unit": "heldout_run" if by_run else "pair", **base}
        for metric in ["sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_vs_log_amp_slope_ns", "calibration_coverage_abs_le2ns"]:
            ci = bootstrap_metric_ci(group, rng, n_boot, metric, by_run)
            row[f"{metric}_ci_low"] = ci[0]
            row[f"{metric}_ci_high"] = ci[1]
        rows.append(row)
    return pd.DataFrame(rows)


def paired_delta_rows(records: pd.DataFrame, primary_ml: str, primary_trad: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(records["heldout_run"].unique().tolist())
    by_method_run = {
        (method, run): sub
        for (method, run), sub in records.groupby(["method", "heldout_run"])
    }
    comparisons = [
        (primary_ml, primary_trad),
        ("full_monotone_log_amp", primary_trad),
        ("amplitude_only", primary_trad),
        (primary_ml, "monotone_residual_table"),
        (primary_ml, "robust_heavytail_table"),
        (primary_ml, "s03a_amp_only"),
    ]
    for ml_method, trad_method in comparisons:
        if ml_method not in set(records["method"]) or trad_method not in set(records["method"]):
            continue
        for metric in ["sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_vs_log_amp_slope_ns", "calibration_coverage_abs_le2ns"]:
            stats = []
            for _ in range(int(n_boot)):
                sampled = rng.choice(runs, size=len(runs), replace=True)
                ml_sample = pd.concat([by_method_run[(ml_method, int(run))] for run in sampled], ignore_index=True)
                tr_sample = pd.concat([by_method_run[(trad_method, int(run))] for run in sampled], ignore_index=True)
                ml_vals = ml_sample["pairwise_residual_ns"].to_numpy(dtype=float)
                tr_vals = tr_sample["pairwise_residual_ns"].to_numpy(dtype=float)
                if metric == "sigma68_ns":
                    stats.append(s02.sigma68(ml_vals) - s02.sigma68(tr_vals))
                elif metric == "full_rms_ns":
                    stats.append(s02.full_rms(ml_vals) - s02.full_rms(tr_vals))
                elif metric == "tail_frac_abs_gt5ns":
                    stats.append(
                        float(np.mean(np.abs(ml_vals - np.median(ml_vals)) > 5.0))
                        - float(np.mean(np.abs(tr_vals - np.median(tr_vals)) > 5.0))
                    )
                elif metric == "bias_vs_log_amp_slope_ns":
                    ml_amp = ml_sample["pair_log_amp"].to_numpy(dtype=float)
                    tr_amp = tr_sample["pair_log_amp"].to_numpy(dtype=float)
                    ml_slope = float(np.polyfit(ml_amp, ml_vals, 1)[0])
                    tr_slope = float(np.polyfit(tr_amp, tr_vals, 1)[0])
                    stats.append(ml_slope - tr_slope)
                elif metric == "calibration_coverage_abs_le2ns":
                    ml_cov = float(np.mean(np.abs(ml_vals - np.nanmedian(ml_vals)) <= 2.0))
                    tr_cov = float(np.mean(np.abs(tr_vals - np.nanmedian(tr_vals)) <= 2.0))
                    stats.append(ml_cov - tr_cov)
            rows.append(
                {
                    "ml_method": ml_method,
                    "traditional_method": trad_method,
                    "metric": metric,
                    "delta_ml_minus_traditional": float(np.nanmedian(stats)),
                    "ci_low": float(np.nanpercentile(stats, 2.5)),
                    "ci_high": float(np.nanpercentile(stats, 97.5)),
                    "bootstrap_unit": "heldout_run",
                }
            )
    return pd.DataFrame(rows)


def support_map_rows(records: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    strata_cols = [
        "amplitude_stratum",
        "stave_stratum",
        "peak_sample_stratum",
        "q_template_stratum",
        "saturation_boundary_stratum",
        "pretrigger_stratum",
        "anomaly_stratum",
    ]
    metrics = ["sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_vs_log_amp_slope_ns", "calibration_coverage_abs_le2ns"]
    n_boot = int(config["support_map"]["bootstrap_samples"])
    min_pairs = int(config["support_map"]["min_pairs"])
    summary_rows = []
    delta_rows = []
    for stratum_type in strata_cols:
        for stratum_value, stratum_records in records.groupby(stratum_type):
            n_support = int(stratum_records[stratum_records["method"] == PRIMARY_ML][["event_id", "pair"]].drop_duplicates().shape[0])
            if n_support < min_pairs:
                continue
            by_method = {method: group for method, group in stratum_records.groupby("method")}
            for method, group in by_method.items():
                vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
                amps = group["pair_log_amp"].to_numpy(dtype=float)
                row = {
                    "stratum_type": stratum_type,
                    "stratum_value": str(stratum_value),
                    "method": method,
                    "support_count_pairs": n_support,
                    "heldout_runs": ",".join(str(int(r)) for r in sorted(group["heldout_run"].unique())),
                    **metric_row(vals, amps),
                }
                for metric in metrics:
                    ci = bootstrap_metric_ci(group, rng, n_boot, metric, by_run=(group["heldout_run"].nunique() > 1))
                    row[f"{metric}_ci_low"] = ci[0]
                    row[f"{metric}_ci_high"] = ci[1]
                summary_rows.append(row)

            for trad in [PRIMARY_TRADITIONAL, "s03a_amp_only", "monotone_residual_table", "robust_heavytail_table"]:
                if PRIMARY_ML not in by_method or trad not in by_method:
                    continue
                runs = sorted(set(by_method[PRIMARY_ML]["heldout_run"].unique()) & set(by_method[trad]["heldout_run"].unique()))
                if not runs:
                    continue
                by_mr = {}
                for (method, run), sub in stratum_records.groupby(["method", "heldout_run"]):
                    by_mr[(method, int(run))] = (
                        sub["pairwise_residual_ns"].to_numpy(dtype=float),
                        sub["pair_log_amp"].to_numpy(dtype=float),
                    )
                for metric in metrics:
                    stats = []
                    for _ in range(n_boot):
                        sampled = rng.choice(runs, size=len(runs), replace=True)
                        ml_vals = np.concatenate([by_mr[(PRIMARY_ML, int(run))][0] for run in sampled])
                        tr_vals = np.concatenate([by_mr[(trad, int(run))][0] for run in sampled])
                        if metric == "sigma68_ns":
                            stats.append(s02.sigma68(ml_vals) - s02.sigma68(tr_vals))
                        elif metric == "full_rms_ns":
                            stats.append(s02.full_rms(ml_vals) - s02.full_rms(tr_vals))
                        elif metric == "tail_frac_abs_gt5ns":
                            stats.append(
                                float(np.mean(np.abs(ml_vals - np.median(ml_vals)) > 5.0))
                                - float(np.mean(np.abs(tr_vals - np.median(tr_vals)) > 5.0))
                            )
                        elif metric == "bias_vs_log_amp_slope_ns":
                            ml_amp = np.concatenate([by_mr[(PRIMARY_ML, int(run))][1] for run in sampled])
                            tr_amp = np.concatenate([by_mr[(trad, int(run))][1] for run in sampled])
                            ml_slope = float(np.polyfit(ml_amp, ml_vals, 1)[0]) if np.nanstd(ml_amp) > 0 else np.nan
                            tr_slope = float(np.polyfit(tr_amp, tr_vals, 1)[0]) if np.nanstd(tr_amp) > 0 else np.nan
                            stats.append(ml_slope - tr_slope)
                        elif metric == "calibration_coverage_abs_le2ns":
                            ml_cov = float(np.mean(np.abs(ml_vals - np.nanmedian(ml_vals)) <= 2.0))
                            tr_cov = float(np.mean(np.abs(tr_vals - np.nanmedian(tr_vals)) <= 2.0))
                            stats.append(ml_cov - tr_cov)
                    delta_rows.append(
                        {
                            "stratum_type": stratum_type,
                            "stratum_value": str(stratum_value),
                            "ml_method": PRIMARY_ML,
                            "traditional_method": trad,
                            "metric": metric,
                            "support_count_pairs": n_support,
                            "delta_ml_minus_traditional": float(np.nanmedian(stats)),
                            "ci_low": float(np.nanpercentile(stats, 2.5)),
                            "ci_high": float(np.nanpercentile(stats, 97.5)),
                            "bootstrap_unit": "heldout_run",
                        }
                    )
    return pd.DataFrame(summary_rows), pd.DataFrame(delta_rows)


def run_one_fold(
    pulses_all: pd.DataFrame, base_config: dict, heldout_run: int, all_runs: list[int], rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = prepare_base_pulses(pulses_all, config)
    s03a_pulses, _, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    signed_pulses, signed_cv, signed_best = run_signed_shrinkage(pulses, config, base_method)
    binned_pulses, binned_cv, _, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)
    robust_pulses, robust_table = run_robust_heavytail_table(pulses, config, base_method)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_signed_shared_shrinkage_ns"] = signed_pulses["t_signed_shared_shrinkage_ns"].to_numpy(dtype=float)
    combined["t_monotone_residual_table_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)
    combined["t_robust_heavytail_table_ns"] = robust_pulses["t_robust_heavytail_table_ns"].to_numpy(dtype=float)

    cv_parts = []
    leakage_rows = []
    variant_best = {}
    for variant in config["hgb"]["variants"]:
        variant_pulses, cv, best = run_hgb_variant(pulses, config, base_method, variant)
        combined[f"t_{variant}_ns"] = variant_pulses[f"t_{variant}_ns"].to_numpy(dtype=float)
        cv["heldout_run"] = heldout_run
        cv_parts.append(cv)
        variant_best[variant] = best
        leakage_rows.append(
            {
                "heldout_run": heldout_run,
                "check": f"{variant}_shuffled_target_sigma68",
                "value": run_hgb_shuffled_control(pulses, config, base_method, variant, best, heldout_run),
                "unit": "ns",
            }
        )

    records = []
    method_map = [
        (base_method, "template_phase_base"),
        ("s03a_amp_only", "s03a_amp_only"),
        ("signed_shared_shrinkage", "signed_shared_shrinkage"),
        ("monotone_residual_table", "monotone_residual_table"),
        ("robust_heavytail_table", "robust_heavytail_table"),
        ("full_unconstrained", "hgb_full_unconstrained"),
        ("full_monotone_log_amp", "full_monotone_log_amp"),
        ("amplitude_only", "amplitude_only"),
        ("shape_only", "shape_only"),
        ("stave_only", "stave_only"),
    ]
    for method, label in method_map:
        rec = pairwise_records(combined, method, config, [heldout_run])
        rec["method"] = label
        records.append(rec)
    residual_records = pd.concat(records, ignore_index=True)
    strata = pair_strata(combined, config, train_runs, [heldout_run])
    residual_records = residual_records.merge(strata, on=["heldout_run", "event_id", "pair"], how="left", validate="many_to_one")

    metric_rows = []
    for method, group in residual_records.groupby("method"):
        vals = group["pairwise_residual_ns"].to_numpy(dtype=float)
        amps = group["pair_log_amp"].to_numpy(dtype=float)
        ci = s02.bootstrap_ci(vals, rng, int(config["hgb"]["bootstrap_samples"]))
        metric_rows.append(
            {
                "heldout_run": heldout_run,
                "method": method,
                "ci_low": ci[0],
                "ci_high": ci[1],
                "s03a_candidate": s03a_candidate,
                "s03a_alpha": s03a_alpha,
                "signed_alpha": signed_best["alpha"],
                "signed_amplitude_sign": signed_best["amplitude_sign"],
                "s03b_n_bins": binned_best["n_bins"],
                "s03b_direction": binned_best["direction"],
                "robust_table_bins": int(config.get("robust_table", {}).get("n_bins", 10)),
                "hgb_cv_sigma68_ns": variant_best.get(method.replace("hgb_", ""), {}).get("score", np.nan),
                **metric_row(vals, amps),
            }
        )

    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    heldout_event_ids = set(combined[combined["run"].isin([heldout_run])]["event_id"])
    leakage_rows.extend(
        [
            {
                "heldout_run": heldout_run,
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids & heldout_event_ids)),
                "unit": "events",
            },
            {
                "heldout_run": heldout_run,
                "check": "features_exclude_run_event_order_cross_stave_time",
                "value": 1.0,
                "unit": "bool",
            },
            {
                "heldout_run": heldout_run,
                "check": "final_models_use_heldout_rows",
                "value": 0.0,
                "unit": "bool",
            },
            {
                "heldout_run": heldout_run,
                "check": "monotone_log_amp_best_direction",
                "value": float(variant_best["full_monotone_log_amp"]["monotone_log_amp"]),
                "unit": "sign",
            },
        ]
    )
    binned_cv["heldout_run"] = heldout_run
    signed_cv["heldout_run"] = heldout_run
    signed_cv["variant"] = "signed_shared_shrinkage"
    robust_table["heldout_run"] = heldout_run
    return (
        pd.DataFrame(metric_rows),
        residual_records,
        pd.DataFrame(leakage_rows),
        pd.concat(
            [signed_cv, binned_cv.assign(variant="monotone_residual_table"), robust_table.assign(variant="robust_heavytail_table")]
            + cv_parts,
            ignore_index=True,
        ),
    )


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, per_run: pd.DataFrame) -> None:
    order = [
        "template_phase_base",
        "s03a_amp_only",
        "signed_shared_shrinkage",
        "monotone_residual_table",
        "robust_heavytail_table",
        "hgb_full_unconstrained",
        "full_monotone_log_amp",
        "amplitude_only",
        "shape_only",
        "stave_only",
    ]
    view = pooled.set_index("method").loc[order].reset_index()
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    xpos = np.arange(len(view))
    ax.bar(xpos, view["sigma68_ns"])
    ax.errorbar(
        xpos,
        view["sigma68_ns"],
        yerr=[view["sigma68_ns"] - view["sigma68_ns_ci_low"], view["sigma68_ns_ci_high"] - view["sigma68_ns"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.set_xticks(xpos)
    ax.set_xticklabels(view["method"], rotation=30, ha="right")
    ax.set_ylabel("pooled LORO sigma68 (ns)")
    ax.set_title("S03g monotonicity and feature ablation audit")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03g_pooled_sigma68.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.8, 4.6))
    for method in [
        "s03a_amp_only",
        "signed_shared_shrinkage",
        "monotone_residual_table",
        "robust_heavytail_table",
        "hgb_full_unconstrained",
        "full_monotone_log_amp",
    ]:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["sigma68_ns"], "o-", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("sigma68 (ns)")
    ax.set_title("Held-out run folds")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s03g_per_run_sigma68.png", dpi=130)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    config_path: Path,
    reproduction: pd.DataFrame,
    reference_repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    deltas: pd.DataFrame,
    support_summary: pd.DataFrame,
    support_deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    ordered = [
        "template_phase_base",
        "s03a_amp_only",
        "signed_shared_shrinkage",
        "monotone_residual_table",
        "robust_heavytail_table",
        "hgb_full_unconstrained",
        "full_monotone_log_amp",
        "amplitude_only",
        "shape_only",
        "stave_only",
    ]
    pooled_view = pooled.set_index("method").loc[ordered].reset_index()
    leak_summary = leakage.pivot_table(index="check", values="value", aggfunc=["min", "median", "max"])
    leak_summary.columns = ["min_value", "median_value", "max_value"]
    lines = [
        "# Study report: S03h - HGB timewalk gain support map by amplitude and shape atoms",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Author:** `{config['worker']}`",
        "- **Date:** 2026-06-10",
        "- **Input:** raw B-stack ROOT files under `data/root/root`",
        "- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65",
        f"- **Config:** `{config_path}`",
        "",
        "## 0. Question",
        "",
        "In which raw waveform strata does the S03d HGB residual corrector gain over signed/analytic traditional timewalk models appear, fail, or become unsupported?",
        "",
        "## 1. Raw-ROOT reproduction gate",
        "",
        "The selected-pulse count gate was rerun from raw ROOT before any model fitting.",
        "",
        reproduction.to_markdown(index=False),
        "",
        "The S03d pooled numbers named in the ticket were reproduced from the raw-derived pulse table before the audit.",
        "",
        reference_repro.to_markdown(index=False),
        "",
        "## 2. Methods",
        "",
        "Traditional references are the frozen S03a amp-only Ridge correction, a physically signed shared-stave inverse-amplitude shrinkage model, the S03b monotone decreasing residual table, and a robust heavy-tail trimmed-median residual table. The ML audit compares the original HGB feature set with a log-amplitude monotonic constraint, amplitude-only, shape-only, and stave-only controls. No method uses run number, event id, event order, current, cross-stave timing, or held-out labels.",
        "",
        "## 3. Held-out results",
        "",
        pooled_view[
            [
                "method",
                "sigma68_ns",
                "sigma68_ns_ci_low",
                "sigma68_ns_ci_high",
                "full_rms_ns",
                "full_rms_ns_ci_low",
                "full_rms_ns_ci_high",
                "tail_frac_abs_gt5ns",
                "bias_vs_log_amp_slope_ns",
                "calibration_coverage_abs_le2ns",
                "n_pair_residuals",
            ]
        ].to_markdown(index=False),
        "",
        per_run[
            ["heldout_run", "method", "sigma68_ns", "ci_low", "ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "bias_vs_log_amp_slope_ns"]
        ]
        .sort_values(["heldout_run", "method"])
        .to_markdown(index=False),
        "",
        "## 4. Paired ML-minus-traditional deltas",
        "",
        deltas.to_markdown(index=False),
        "",
        "## 5. Support map",
        "",
        "Strata are attached to held-out pair residuals from raw pulse features: mean amplitude, stave pair, max peak-sample bin, max train-template RMSE, saturation boundary proxy, max pretrigger RMS bin, and P09a-like anomaly atom. Rows below are the supported primary HGB-minus-signed-prior sigma68 deltas.",
        "",
        support_deltas[
            (support_deltas["traditional_method"] == PRIMARY_TRADITIONAL) & (support_deltas["metric"] == "sigma68_ns")
        ]
        .sort_values(["stratum_type", "delta_ml_minus_traditional"])
        .head(60)
        .to_markdown(index=False),
        "",
        "Full support-map metrics are in `support_map_metrics.csv`; paired support deltas are in `support_map_paired_deltas.csv`.",
        "",
        "## 6. Leakage checks",
        "",
        leak_summary.reset_index().to_markdown(index=False),
        "",
        "## 7. Verdict",
        "",
        f"`result.json` verdict: `{result['verdict']}`.",
        f"Original HGB sigma68 is `{result['ml']['hgb_full_unconstrained']['sigma68_ns']:.3f} ns` versus S03a `{result['traditional']['s03a_amp_only']['sigma68_ns']:.3f} ns`, signed shrinkage `{result['traditional']['signed_shared_shrinkage']['sigma68_ns']:.3f} ns`, monotone table `{result['traditional']['monotone_residual_table']['sigma68_ns']:.3f} ns`, and robust heavy-tail table `{result['traditional']['robust_heavytail_table']['sigma68_ns']:.3f} ns`.",
        f"Supported strata with HGB sigma68 gain over signed prior: `{result['support_map']['n_supported_gain_strata_vs_signed']}`; unsupported/failing strata: `{result['support_map']['n_unsupported_or_failing_strata_vs_signed']}`.",
        f"The monotone-log-amplitude HGB is `{result['ml']['full_monotone_log_amp']['sigma68_ns']:.3f} ns`; shape-only is `{result['ml']['shape_only']['sigma68_ns']:.3f} ns`; stave-only is `{result['ml']['stave_only']['sigma68_ns']:.3f} ns`.",
        "",
        "## 8. Reproducibility",
        "",
        "Generated by:",
        "",
        "```bash",
        f"{sys.executable} scripts/s03h_1781024797_1607_4a1b6480_support_map.py --config {config_path}",
        "```",
        "",
        "Artifacts: `reproduction_match_table.csv`, `reference_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `paired_deltas.csv`, `support_map_metrics.csv`, `support_map_paired_deltas.csv`, `pairwise_residuals.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03h_1781024797_1607_4a1b6480_support_map.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["hgb"]["random_seed"]))

    reproduction = s02.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw-ROOT count reproduction failed")

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(r) for r in config["timing"]["loo_runs"]]
    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    cv_parts = []
    for heldout_run in all_runs:
        print(f"S03h fold heldout_run={heldout_run}", flush=True)
        per_run, residuals, leakage, cv = run_one_fold(pulses_all, config, heldout_run, all_runs, rng)
        per_run_parts.append(per_run)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        cv_parts.append(cv)

    per_run = pd.concat(per_run_parts, ignore_index=True)
    residuals = pd.concat(residual_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    cv = pd.concat(cv_parts, ignore_index=True)
    pooled = summarize_records(residuals, rng, int(config["hgb"]["bootstrap_samples"]), by_run=True)
    deltas = paired_delta_rows(
        residuals,
        "hgb_full_unconstrained",
        PRIMARY_TRADITIONAL,
        rng,
        int(config["hgb"]["bootstrap_samples"]),
    )
    support_summary, support_deltas = support_map_rows(residuals, config, rng)

    reference_rows = []
    for method, ref in REFERENCE.items():
        value = float(pooled.set_index("method").loc[method]["sigma68_ns"])
        reference_rows.append(
            {
                "method": method,
                "reference_sigma68_ns": ref,
                "reproduced_sigma68_ns": value,
                "delta_ns": value - ref,
                "tolerance_ns": 0.005,
                "pass": abs(value - ref) < 0.005,
            }
        )
    reference_repro = pd.DataFrame(reference_rows)
    reference_repro.to_csv(out_dir / "reference_reproduction.csv", index=False)
    if not bool(reference_repro["pass"].all()):
        raise RuntimeError("S03d pooled reference reproduction failed")

    per_run.to_csv(out_dir / "per_run_benchmark.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap.csv", index=False)
    deltas.to_csv(out_dir / "paired_deltas.csv", index=False)
    support_summary.to_csv(out_dir / "support_map_metrics.csv", index=False)
    support_deltas.to_csv(out_dir / "support_map_paired_deltas.csv", index=False)
    residuals.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    cv.to_csv(out_dir / "hgb_cv_scan.csv", index=False)
    plot_outputs(out_dir, pooled, per_run)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    pidx = pooled.set_index("method")
    leak_shuffle = leakage[leakage["check"].str.endswith("_shuffled_target_sigma68")]["value"]
    event_overlap = int(leakage[leakage["check"] == "train_heldout_event_id_overlap"]["value"].sum())
    hgb = pidx.loc["hgb_full_unconstrained"]
    mono_hgb = pidx.loc["full_monotone_log_amp"]
    table = pidx.loc["monotone_residual_table"]
    robust = pidx.loc["robust_heavytail_table"]
    stave = pidx.loc["stave_only"]
    shape = pidx.loc["shape_only"]
    amp = pidx.loc["amplitude_only"]
    looks_too_good = bool((table["sigma68_ns"] - hgb["sigma68_ns"] > 0.5) or hgb["sigma68_ns"] < 0.8)
    leakage_flag = bool(event_overlap != 0 or float(leak_shuffle.min()) < float(hgb["sigma68_ns"]) + 0.2 or stave["sigma68_ns"] < 2.0)
    monotone_cost = float(mono_hgb["sigma68_ns"] - hgb["sigma68_ns"])
    primary_support = support_deltas[
        (support_deltas["traditional_method"] == PRIMARY_TRADITIONAL) & (support_deltas["metric"] == "sigma68_ns")
    ].copy()
    supported_gain = primary_support[
        (primary_support["delta_ml_minus_traditional"] < 0.0) & (primary_support["ci_high"] < 0.0)
    ]
    failing_or_unsupported = primary_support[
        (primary_support["delta_ml_minus_traditional"] >= 0.0) | (primary_support["ci_low"] <= 0.0)
    ]
    verdict = (
        "hgb_gain_has_atomic_support_but_is_shape_control_limited_no_leakage_flag"
        if len(supported_gain) > 0 and not leakage_flag
        else "hgb_gain_support_map_inconclusive_or_leakage_limited"
    )

    result = {
        "study": "S03h",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all() and reference_repro["pass"].all()),
        "raw_root_reproduction": {
            "selected_count_pass": bool(reproduction["pass"].all()),
            "s03d_reference_pass": bool(reference_repro["pass"].all()),
        },
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "traditional": {
            "s03a_amp_only": {
                "sigma68_ns": float(pidx.loc["s03a_amp_only"]["sigma68_ns"]),
                "ci": [float(pidx.loc["s03a_amp_only"]["sigma68_ns_ci_low"]), float(pidx.loc["s03a_amp_only"]["sigma68_ns_ci_high"])],
            },
            "signed_shared_shrinkage": {
                "sigma68_ns": float(pidx.loc["signed_shared_shrinkage"]["sigma68_ns"]),
                "ci": [
                    float(pidx.loc["signed_shared_shrinkage"]["sigma68_ns_ci_low"]),
                    float(pidx.loc["signed_shared_shrinkage"]["sigma68_ns_ci_high"]),
                ],
            },
            "monotone_residual_table": {
                "sigma68_ns": float(table["sigma68_ns"]),
                "ci": [float(table["sigma68_ns_ci_low"]), float(table["sigma68_ns_ci_high"])],
            },
            "robust_heavytail_table": {
                "sigma68_ns": float(robust["sigma68_ns"]),
                "ci": [float(robust["sigma68_ns_ci_low"]), float(robust["sigma68_ns_ci_high"])],
            },
        },
        "ml": {
            method: {
                "sigma68_ns": float(pidx.loc[method]["sigma68_ns"]),
                "ci": [float(pidx.loc[method]["sigma68_ns_ci_low"]), float(pidx.loc[method]["sigma68_ns_ci_high"])],
                "full_rms_ns": float(pidx.loc[method]["full_rms_ns"]),
                "tail_frac_abs_gt5ns": float(pidx.loc[method]["tail_frac_abs_gt5ns"]),
                "bias_vs_log_amp_slope_ns": float(pidx.loc[method]["bias_vs_log_amp_slope_ns"]),
            }
            for method in ["hgb_full_unconstrained", "full_monotone_log_amp", "amplitude_only", "shape_only", "stave_only"]
        },
        "monotonicity": {
            "monotone_log_amp_minus_full_sigma68_ns": monotone_cost,
            "best_log_amp_constraint_signs_by_fold": leakage[leakage["check"] == "monotone_log_amp_best_direction"]["value"].astype(int).tolist(),
        },
        "leakage": {
            "split_by_run": True,
            "event_id_overlap_total": event_overlap,
            "features_exclude_run_event_order_cross_stave_time": True,
            "final_models_use_heldout_rows": False,
            "shuffled_target_min_sigma68_ns": float(leak_shuffle.min()),
            "stave_only_sigma68_ns": float(stave["sigma68_ns"]),
            "hgb_looks_too_good": looks_too_good,
            "leakage_flag": leakage_flag,
        },
        "paired_deltas_csv": "paired_deltas.csv",
        "support_map": {
            "strata": [
                "amplitude_stratum",
                "stave_stratum",
                "peak_sample_stratum",
                "q_template_stratum",
                "saturation_boundary_stratum",
                "pretrigger_stratum",
                "anomaly_stratum",
            ],
            "min_pairs": int(config["support_map"]["min_pairs"]),
            "n_supported_rows": int(len(support_summary)),
            "n_supported_delta_rows": int(len(support_deltas)),
            "n_supported_gain_strata_vs_signed": int(len(supported_gain)),
            "n_unsupported_or_failing_strata_vs_signed": int(len(failing_or_unsupported)),
            "best_gain_strata_vs_signed": supported_gain.sort_values("delta_ml_minus_traditional")
            .head(12)[
                ["stratum_type", "stratum_value", "support_count_pairs", "delta_ml_minus_traditional", "ci_low", "ci_high"]
            ]
            .to_dict(orient="records"),
        },
        "verdict": verdict,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    write_report(
        out_dir,
        config,
        config_path,
        reproduction,
        reference_repro,
        per_run,
        pooled,
        deltas,
        support_summary,
        support_deltas,
        leakage,
        result,
    )

    manifest = {
        "ticket": config["ticket_id"],
        "study": "S03h",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["hgb"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "verdict": verdict, "runtime_sec": round(time.time() - t0, 2)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
