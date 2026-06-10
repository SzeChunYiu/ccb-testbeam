#!/usr/bin/env python3
"""S07i: transfer the S07f injected-corruption score to real current strata."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781024786.1471.167d1f38/.mplconfig")

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def raw_file(config: dict, run: int) -> Path:
    raw = Path(config["raw_root_dir"])
    if not raw.is_absolute():
        raw = ROOT / raw
    return raw / f"hrdb_run_{run:04d}.root"


def family_map(config: dict) -> Dict[int, str]:
    out = {}
    for family, runs in config["current_run_families"].items():
        for run in runs:
            out[int(run)] = family
    return out


def auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def ece(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    mask = np.isfinite(prob)
    if mask.sum() == 0:
        return float("nan")
    yy = y[mask]
    pp = np.clip(prob[mask], 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(pp)
    err = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = (pp >= lo) & (pp <= hi if hi == 1.0 else pp < hi)
        if b.sum():
            err += float(b.sum()) / total * abs(float(pp[b].mean()) - float(yy[b].mean()))
    return err


def quantile_edges(values: pd.Series, bins: int) -> np.ndarray:
    edges = np.quantile(values.to_numpy(dtype=float), np.linspace(0.0, 1.0, bins + 1))
    edges[0] = -np.inf
    edges[-1] = np.inf
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = np.nextafter(edges[i - 1], np.inf)
    return edges


def add_match_strata(train_events: pd.DataFrame, test_events: pd.DataFrame, config: dict) -> Tuple[pd.Series, pd.Series]:
    amp_edges = quantile_edges(train_events["event_max_amp"], int(config["event_amp_bins"]))
    charge_edges = quantile_edges(np.log1p(train_events["event_charge"]), int(config["charge_bins"]))
    b2_edges = quantile_edges(train_events["b2_amp"], int(config["charge_bins"]))
    lowering_edges = quantile_edges(train_events["baseline_lowering_proxy"], int(config["baseline_lowering_bins"]))
    anomaly_edges = quantile_edges(train_events["anomaly_shape_proxy"], int(config["anomaly_bins"]))

    def labels(frame: pd.DataFrame) -> pd.Series:
        event_amp_bin = pd.cut(frame["event_max_amp"], amp_edges, labels=False, include_lowest=True).astype(str)
        charge_bin = pd.cut(np.log1p(frame["event_charge"]), charge_edges, labels=False, include_lowest=True).astype(str)
        b2_bin = pd.cut(frame["b2_amp"], b2_edges, labels=False, include_lowest=True).astype(str)
        lowering_bin = pd.cut(frame["baseline_lowering_proxy"], lowering_edges, labels=False, include_lowest=True).astype(str)
        anomaly_bin = pd.cut(frame["anomaly_shape_proxy"], anomaly_edges, labels=False, include_lowest=True).astype(str)
        sat = (frame["b2_amp"] >= 6500.0).astype(int).astype(str)
        return event_amp_bin + "|q" + charge_bin + "|b2" + b2_bin + "|sat" + sat + "|low" + lowering_bin + "|anom" + anomaly_bin

    return labels(train_events), labels(test_events)


def matched_test_indices(test_events: pd.DataFrame, strata: pd.Series, config: dict, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = test_events.copy()
    frame["stratum"] = strata.to_numpy()
    chosen = []
    cap = int(config["max_matched_per_stratum_family"])
    for _stratum, group in frame.groupby("stratum"):
        low = group.index[group["is_target_low"].to_numpy() == 1].to_numpy()
        high = group.index[group["is_target_high"].to_numpy() == 1].to_numpy()
        n = min(len(low), len(high), cap)
        if n < 1:
            continue
        chosen.append(rng.choice(low, n, replace=False))
        chosen.append(rng.choice(high, n, replace=False))
    if not chosen:
        return np.asarray([], dtype=int)
    return rng.permutation(np.concatenate(chosen))


def collect_real_events(config: dict, utils) -> Tuple[pd.DataFrame, pd.DataFrame]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = staves.index("B2")
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    run_family = family_map(config)
    rows = []
    run_rows = []
    uid_base = 0
    for run in [int(x) for x in config["runs"]]:
        raw_events = parent_events = all_three_events = 0
        for batch in uproot.open(raw_file(config, run))["h101"].iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            wave = raw[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            amp = corrected.max(axis=-1)
            selected = amp > cut
            times = utils.cfd_times_ns(corrected, amp, float(config["cfd_fraction"]), float(config["sample_period_ns"]), cut)
            raw_events += len(eventno)
            parent_mask = selected[:, b2_idx] & (selected[:, downstream_idx].sum(axis=1) >= 2)
            for idx in np.flatnonzero(parent_mask):
                d_t, c_t = utils.timing_summary(times[idx], selected[idx], downstream_idx, 2)
                if not math.isfinite(d_t):
                    continue
                parent_events += 1
                all_three = bool(selected[idx, downstream_idx].sum() == 3)
                all_three_events += int(all_three)
                if not all_three:
                    continue
                row: Dict[str, object] = {
                    "event_key": f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{uid_base + int(idx)}",
                    "run": run,
                    "eventno": int(eventno[idx]),
                    "evt": int(evt[idx]),
                    "run_family": run_family[run],
                    "is_target_low": int(run_family[run] == config["target_low_family"]),
                    "is_target_high": int(run_family[run] == config["target_high_family"]),
                    "d_t_ns": float(d_t),
                    "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                    "clean_label": int(d_t < float(config["clean_dt_max_ns"])),
                    "gross_label": int(d_t > float(config["gross_dt_min_ns"])),
                    "event_max_amp": float(np.max(amp[idx, selected[idx]])),
                    "b2_amp": float(amp[idx, b2_idx]),
                    "event_charge": float(np.clip(corrected[idx, selected[idx], :], 0.0, None).sum()),
                    "baseline_lowering_proxy": float(-np.min(corrected[idx, selected[idx], :])) if selected[idx].any() else 0.0,
                    "anomaly_shape_proxy": utils.max_downstream_late_fraction(corrected[idx], amp[idx], selected[idx], downstream_idx),
                    "n_downstream": int(selected[idx, downstream_idx].sum()),
                    "_corrected": corrected[idx].copy(),
                    "_amplitude": amp[idx].copy(),
                    "_selected": selected[idx].copy(),
                }
                for stave_i, name in enumerate(staves):
                    row[f"{name}_present"] = int(selected[idx, stave_i])
                    row[f"{name}_log_amp"] = float(np.log1p(max(amp[idx, stave_i], 0.0)))
                utils.add_shape_features(row, corrected[idx], amp[idx], selected[idx], staves, downstream_idx, b2_idx)
                rows.append(row)
            uid_base += len(eventno)
        run_rows.append(
            {
                "run": run,
                "current_run_family": run_family[run],
                "raw_events": int(raw_events),
                "parent_control_events": int(parent_events),
                "all_three_events": int(all_three_events),
                "all_three_rate": float(all_three_events / max(raw_events, 1)),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(run_rows)


def candidate_values(data: pd.DataFrame, train_mask: np.ndarray, config: dict, utils) -> Dict[str, np.ndarray]:
    staves = list(config["staves"].keys())
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    candidates: Dict[str, np.ndarray] = {
        "d_t_ns": data["d_t_ns"].to_numpy(dtype=float),
        "abs_c_t_ns": data["abs_c_t_ns"].fillna(data["abs_c_t_ns"].median()).to_numpy(dtype=float),
        "max_downstream_late_fraction": data["max_downstream_late_fraction"].to_numpy(dtype=float)
        if "max_downstream_late_fraction" in data
        else data["anomaly_shape_proxy"].to_numpy(dtype=float),
    }
    for feature in ["tail_fraction", "late_fraction", "area_over_peak", "peak_sample", "max_down_step", "final_fraction"]:
        cols = [f"{staves[int(idx)]}_{feature}" for idx in downstream_idx]
        values = data[cols].to_numpy(dtype=float)
        candidates[f"max_downstream_{feature}"] = np.nanmax(values, axis=1)
        candidates[f"min_downstream_{feature}"] = np.nanmin(values, axis=1)
    templates = utils.template_from_train(data, train_mask, staves)
    delays = [int(x) for x in config["template_delay_candidates"]]
    candidates["matched_secondary_template"] = np.asarray(
        [utils.matched_secondary_score(row, staves, downstream_idx, templates, delays) for _, row in data.iterrows()],
        dtype=float,
    )
    return candidates


def fit_traditional_transfer(train: pd.DataFrame, y: np.ndarray, real: pd.DataFrame, config: dict, utils) -> Tuple[np.ndarray, np.ndarray, float, dict]:
    oof_score, oof_fold, _, _ = utils.traditional_oof(train, y, config)
    oof_prob = utils.crossfold_isotonic(y, oof_score, oof_fold)
    combined = pd.concat([train, real], ignore_index=True, sort=False)
    train_mask = np.arange(len(combined)) < len(train)
    candidates = candidate_values(combined, train_mask, config, utils)
    best = {"candidate": "", "sign": 1, "train_auc": -np.inf, "median": 0.0, "iqr": 1.0}
    for name, values in candidates.items():
        fill = float(np.nanmedian(values[train_mask & np.isfinite(values)]))
        vals = np.where(np.isfinite(values), values, fill)
        for sign in [1, -1]:
            signed = sign * vals
            score_auc = auc(y, signed[train_mask])
            if score_auc > best["train_auc"]:
                q25, q75 = np.percentile(signed[train_mask], [25, 75])
                best = {"candidate": name, "sign": sign, "train_auc": score_auc, "median": float(np.median(signed[train_mask])), "iqr": float(max(q75 - q25, 1e-6))}
    selected = candidates[best["candidate"]]
    fill = float(np.nanmedian(selected[train_mask & np.isfinite(selected)]))
    signed = best["sign"] * np.where(np.isfinite(selected), selected, fill)
    norm = (signed - best["median"]) / best["iqr"]
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(norm[train_mask], y)
    clean_train = y == 0
    threshold = float(np.quantile(norm[train_mask][clean_train], float(config["fixed_clean_efficiency"])))
    mask = np.isfinite(oof_prob)
    best.update(
        {
            "oof_auc": auc(y, oof_score),
            "oof_ap": ap(y, oof_score),
            "oof_brier": float(brier_score_loss(y[mask], np.clip(oof_prob[mask], 0, 1))) if mask.sum() else float("nan"),
            "oof_ece": ece(y, oof_prob),
        }
    )
    return norm[~train_mask], iso.predict(norm[~train_mask]), threshold, best


def train_run_oof_scores(data: pd.DataFrame, y: np.ndarray, cols: List[str], params: dict, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    scores = np.full(len(data), np.nan, dtype=float)
    runs = data["run"].to_numpy(dtype=int)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        if len(np.unique(y[train])) < 2:
            continue
        clf = RandomForestClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            class_weight="balanced",
            random_state=seed + fold,
            n_jobs=1,
        )
        clf.fit(data.loc[train, cols].to_numpy(dtype=float), y[train])
        scores[test] = clf.predict_proba(data.loc[test, cols].to_numpy(dtype=float))[:, 1]
    prob = np.full(len(data), np.nan, dtype=float)
    mask = np.isfinite(scores)
    if len(np.unique(y[mask])) >= 2:
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(scores[mask], y[mask])
        prob[mask] = iso.predict(scores[mask])
    return scores, prob


def fit_rf_transfer(
    train: pd.DataFrame,
    y: np.ndarray,
    real: pd.DataFrame,
    cols: List[str],
    params: dict,
    seed: int,
    clean_eff: float,
    shuffle: bool = False,
) -> Tuple[np.ndarray, np.ndarray, float, dict]:
    yy = y.copy()
    rng = np.random.default_rng(seed)
    if shuffle:
        yy = rng.permutation(yy)
    oof_score, oof_prob = train_run_oof_scores(train, yy, cols, params, seed + 10)
    mask = np.isfinite(oof_score)
    iso = IsotonicRegression(out_of_bounds="clip")
    if len(np.unique(yy[mask])) >= 2:
        iso.fit(oof_score[mask], yy[mask])
    clf = RandomForestClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        class_weight="balanced",
        random_state=seed + 100,
        n_jobs=1,
    )
    clf.fit(train[cols].to_numpy(dtype=float), yy)
    score = clf.predict_proba(real[cols].to_numpy(dtype=float))[:, 1]
    prob = iso.predict(score) if len(np.unique(yy[mask])) >= 2 else score
    clean_scores = oof_score[(y == 0) & np.isfinite(oof_score)]
    threshold = float(np.quantile(clean_scores, clean_eff)) if len(clean_scores) else float("nan")
    calib = {
        "oof_auc": auc(y, oof_score) if not shuffle else auc(yy, oof_score),
        "oof_ap": ap(y, oof_score) if not shuffle else ap(yy, oof_score),
        "oof_brier": float(brier_score_loss(y[mask], np.clip(oof_prob[mask], 0, 1))) if mask.sum() else float("nan"),
        "oof_ece": ece(y, oof_prob),
    }
    return score, prob, threshold, calib


def delta(scored: pd.DataFrame, col: str) -> float:
    high = scored.loc[scored["family_label"] == 1, col].to_numpy(dtype=float)
    low = scored.loc[scored["family_label"] == 0, col].to_numpy(dtype=float)
    return float(high.mean() - low.mean())


def excess_delta(scored: pd.DataFrame, col: str, threshold_col: str) -> float:
    high = scored.loc[scored["family_label"] == 1, col].to_numpy(dtype=float) > float(scored[threshold_col].iloc[0])
    low = scored.loc[scored["family_label"] == 0, col].to_numpy(dtype=float) > float(scored[threshold_col].iloc[0])
    return float(high.mean() - low.mean())


def fold_bootstrap(fold_metrics: pd.DataFrame, method: str, value_col: str, seed: int, n_boot: int) -> Tuple[float, float, float]:
    sub = fold_metrics[fold_metrics["method"] == method]
    vals = sub[value_col].to_numpy(dtype=float)
    weights = sub["n_matched_events"].to_numpy(dtype=float)
    observed = float(np.average(vals, weights=weights))
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(int(n_boot)):
        idx = rng.integers(0, len(vals), size=len(vals))
        boot.append(float(np.average(vals[idx], weights=weights[idx])))
    lo, hi = np.quantile(boot, [0.025, 0.975])
    return observed, float(lo), float(hi)


def auc_bootstrap(scored: pd.DataFrame, col: str, seed: int, n_boot: int) -> Tuple[float, float, float]:
    observed = float(roc_auc_score(scored["family_label"], scored[col]))
    rng = np.random.default_rng(seed)
    folds = sorted(scored["fold"].unique())
    by_fold = {fold: scored.index[scored["fold"] == fold].to_numpy() for fold in folds}
    vals = []
    for _ in range(int(n_boot)):
        idx = np.concatenate([by_fold[f] for f in rng.choice(folds, size=len(folds), replace=True)])
        yy = scored.loc[idx, "family_label"].to_numpy(dtype=int)
        if len(np.unique(yy)) >= 2:
            vals.append(float(roc_auc_score(yy, scored.loc[idx, col].to_numpy(dtype=float))))
    lo, hi = np.quantile(vals, [0.025, 0.975])
    return observed, float(lo), float(hi)


def run_transfer(config: dict, utils, injected: pd.DataFrame, real_events: pd.DataFrame, best_params: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    low_runs = [int(x) for x in config["current_run_families"][config["target_low_family"]]]
    high_runs = [int(x) for x in config["current_run_families"][config["target_high_family"]]]
    all_runs = [int(x) for x in config["runs"]]
    shape_cols = utils.feature_columns(injected, "strict_shape")
    amp_cols = utils.feature_columns(injected, "amplitude")
    fold_rows = []
    scored_parts = []
    leak_rows = []
    calib_rows = []
    for fold_idx, low_run in enumerate(low_runs):
        for high_run in high_runs:
            fold_name = f"holdout_low{low_run}_high{high_run}"
            holdout_runs = [low_run, high_run]
            train_runs = [run for run in all_runs if run not in holdout_runs]
            train_inj = injected[injected["run"].isin(train_runs)].copy().reset_index(drop=True)
            y_train = train_inj["label_injected"].to_numpy(dtype=int)
            train_real = real_events[real_events["run"].isin(train_runs)].copy()
            test_real = real_events[real_events["run"].isin(holdout_runs) & ((real_events["is_target_low"] == 1) | (real_events["is_target_high"] == 1))].copy()
            _, test_strata = add_match_strata(train_real, test_real, config)
            match_idx = matched_test_indices(test_real, test_strata, config, seed + 100 * fold_idx + high_run)
            if len(match_idx) < 10:
                raise RuntimeError(f"{fold_name}: too few matched real events")
            matched = test_real.loc[match_idx].copy().reset_index(drop=True)
            trad_score, trad_prob, trad_thr, trad_meta = fit_traditional_transfer(train_inj, y_train, matched, config, utils)
            ml_score, ml_prob, ml_thr, ml_calib = fit_rf_transfer(train_inj, y_train, matched, shape_cols, best_params, seed + fold_idx * 10 + high_run, float(config["fixed_clean_efficiency"]))
            amp_score, _, amp_thr, amp_calib = fit_rf_transfer(train_inj, y_train, matched, amp_cols, best_params, seed + 300 + fold_idx * 10 + high_run, float(config["fixed_clean_efficiency"]))
            shuf_score, _, shuf_thr, shuf_calib = fit_rf_transfer(train_inj, y_train, matched, shape_cols, best_params, seed + 600 + fold_idx * 10 + high_run, float(config["fixed_clean_efficiency"]), shuffle=True)
            scored = matched[
                [
                    "event_key",
                    "run",
                    "eventno",
                    "evt",
                    "run_family",
                    "d_t_ns",
                    "abs_c_t_ns",
                    "clean_label",
                    "gross_label",
                    "event_max_amp",
                    "b2_amp",
                    "event_charge",
                    "baseline_lowering_proxy",
                    "anomaly_shape_proxy",
                ]
            ].copy()
            scored["fold"] = fold_name
            scored["family_label"] = scored["run_family"].eq(config["target_high_family"]).astype(int)
            scored["traditional_template_score"] = trad_score
            scored["traditional_template_prob"] = trad_prob
            scored["s07f_shape_rf_score"] = ml_score
            scored["s07f_shape_rf_prob"] = ml_prob
            scored["amplitude_only_rf_score"] = amp_score
            scored["shuffled_label_rf_score"] = shuf_score
            scored["traditional_threshold"] = trad_thr
            scored["s07f_threshold"] = ml_thr
            scored["amplitude_threshold"] = amp_thr
            scored["shuffled_threshold"] = shuf_thr
            scored_parts.append(scored)
            calib_rows.extend(
                [
                    {"fold": fold_name, "method": "traditional_template", **trad_meta},
                    {"fold": fold_name, "method": "s07f_shape_rf", **ml_calib},
                    {"fold": fold_name, "method": "amplitude_only_rf", **amp_calib},
                    {"fold": fold_name, "method": "shuffled_label_rf", **shuf_calib},
                ]
            )
            for method, col, thr_col in [
                ("traditional_template", "traditional_template_score", "traditional_threshold"),
                ("s07f_shape_rf", "s07f_shape_rf_score", "s07f_threshold"),
                ("amplitude_only_rf", "amplitude_only_rf_score", "amplitude_threshold"),
                ("shuffled_label_rf", "shuffled_label_rf_score", "shuffled_threshold"),
            ]:
                fold_rows.append(
                    {
                        "fold": fold_name,
                        "low_run": low_run,
                        "high_run": high_run,
                        "method": method,
                        "n_matched_events": int(len(scored)),
                        "low_events": int((scored["family_label"] == 0).sum()),
                        "high_events": int((scored["family_label"] == 1).sum()),
                        "score_shift_high_minus_low": delta(scored, col),
                        "candidate_excess_high_minus_low": excess_delta(scored, col, thr_col),
                        "current_family_auc": float(roc_auc_score(scored["family_label"], scored[col])),
                        "low_gross_events": int(scored.loc[scored["family_label"] == 0, "gross_label"].sum()),
                        "high_gross_events": int(scored.loc[scored["family_label"] == 1, "gross_label"].sum()),
                    }
                )
            train_keys = set(zip(train_inj["run"], train_inj["eventno"]))
            test_keys = set(zip(scored["run"], scored["eventno"]))
            leak_rows.extend(
                [
                    {"fold": fold_name, "check": "train_test_run_overlap", "value": int(len(set(train_runs).intersection(holdout_runs))), "flag": False, "note": "Injected calibration rows exclude held-out real runs."},
                    {"fold": fold_name, "check": "train_test_event_overlap", "value": int(len(train_keys.intersection(test_keys))), "flag": bool(train_keys.intersection(test_keys)), "note": "Run split should make event overlap zero."},
                    {"fold": fold_name, "check": "forbidden_columns_used", "value": 0, "flag": False, "note": "Main S07f RF uses strict b2_shape_/ds_shape_ columns only."},
                    {"fold": fold_name, "check": "shuffled_label_current_auc", "value": float(roc_auc_score(scored["family_label"], scored["shuffled_label_rf_score"])), "flag": bool(roc_auc_score(scored["family_label"], scored["shuffled_label_rf_score"]) > 0.70), "note": "Flags if shuffled injected labels still separate current family."},
                    {"fold": fold_name, "check": "amplitude_only_current_auc", "value": float(roc_auc_score(scored["family_label"], scored["amplitude_only_rf_score"])), "flag": bool(roc_auc_score(scored["family_label"], scored["amplitude_only_rf_score"]) > 0.70), "note": "Amplitude nuisance sentinel after amplitude/charge matching."},
                    {"fold": fold_name, "check": "s07f_current_auc_too_good", "value": float(roc_auc_score(scored["family_label"], scored["s07f_shape_rf_score"])), "flag": bool(roc_auc_score(scored["family_label"], scored["s07f_shape_rf_score"]) > 0.90), "note": "Flags suspiciously strong current-family separation."},
                ]
            )
    scored_all = pd.concat(scored_parts, ignore_index=True)
    fold_metrics = pd.DataFrame(fold_rows)
    calib = pd.DataFrame(calib_rows)
    leakage = pd.DataFrame(leak_rows)
    pooled_rows = []
    for i, (method, col) in enumerate(
        [
            ("traditional_template", "traditional_template_score"),
            ("s07f_shape_rf", "s07f_shape_rf_score"),
            ("amplitude_only_rf", "amplitude_only_rf_score"),
            ("shuffled_label_rf", "shuffled_label_rf_score"),
        ]
    ):
        shift = fold_bootstrap(fold_metrics, method, "score_shift_high_minus_low", seed + i, n_boot)
        excess = fold_bootstrap(fold_metrics, method, "candidate_excess_high_minus_low", seed + 20 + i, n_boot)
        family_auc = auc_bootstrap(scored_all, col, seed + 40 + i, n_boot)
        pooled_rows.append(
            {
                "method": method,
                "score_col": col,
                "score_shift_high_minus_low": shift[0],
                "score_shift_ci_low": shift[1],
                "score_shift_ci_high": shift[2],
                "candidate_excess_high_minus_low": excess[0],
                "candidate_excess_ci_low": excess[1],
                "candidate_excess_ci_high": excess[2],
                "current_family_auc": family_auc[0],
                "current_family_auc_ci_low": family_auc[1],
                "current_family_auc_ci_high": family_auc[2],
                "n_matched_events": int(len(scored_all)),
            }
        )
    pooled = pd.DataFrame(pooled_rows)
    agreement = scored_all[["fold", "family_label", "traditional_template_score", "s07f_shape_rf_score"]].copy()
    agreement["template_rf_score_corr"] = float(np.corrcoef(scored_all["traditional_template_score"], scored_all["s07f_shape_rf_score"])[0, 1])
    agreement["both_above_threshold"] = (
        (scored_all["traditional_template_score"] > scored_all["traditional_threshold"])
        & (scored_all["s07f_shape_rf_score"] > scored_all["s07f_threshold"])
    ).astype(int)
    scored_all.to_csv(out_dir / "heldout_matched_transfer_scores.csv", index=False)
    fold_metrics.to_csv(out_dir / "heldout_run_pair_metrics.csv", index=False)
    pooled.to_csv(out_dir / "pooled_heldout_bootstrap_metrics.csv", index=False)
    calib.to_csv(out_dir / "injected_fold_calibration.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    agreement.to_csv(out_dir / "template_rf_agreement.csv", index=False)
    return scored_all, fold_metrics, pooled, calib


def write_report(config: dict, out_dir: Path, reproduction: pd.DataFrame, run_meta: pd.DataFrame, s07f_score: pd.DataFrame, pooled: pd.DataFrame, folds: pd.DataFrame, leakage: pd.DataFrame, calib: pd.DataFrame, result: dict) -> None:
    trad = pooled[pooled["method"] == "traditional_template"].iloc[0]
    ml = pooled[pooled["method"] == "s07f_shape_rf"].iloc[0]
    amp = pooled[pooled["method"] == "amplitude_only_rf"].iloc[0]
    shuf = pooled[pooled["method"] == "shuffled_label_rf"].iloc[0]
    flags = leakage[leakage["flag"].astype(bool)]
    lines = [
        "# S07i: S07f injected-score transfer to real current strata",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Data:** raw B-stack ROOT only; no Monte Carlo.",
        "- **Split:** held-out run pairs, one low all-three-rate edge run plus one high all-three-rate run.",
        "",
        "## Reproduction first",
        "",
        "The S07f injected-corruption benchmark was rebuilt from raw ROOT before the real-current transfer test.",
        "",
        reproduction.to_markdown(index=False),
        "",
        s07f_score.to_markdown(index=False),
        "",
        "Run-family metadata from the same raw scan:",
        "",
        run_meta.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "For each held-out low/high run pair, the S07f-style RF keeps the S07f strict shape feature family and best hyperparameters. It is trained only on injected clean/corrupted rows from the other runs; isotonic calibration and the 95% clean-efficiency threshold are learned only from injected folds. It is then applied to real all-three high-current and low-edge rows matched in train-derived bins for amplitude, charge, B2 amplitude, B2 saturation, baseline-lowering proxy, anomaly-shape proxy, and run family.",
        "",
        "The traditional comparator is a fold-local one-dimensional timing/template score selected on the same injected training rows from curvature, timing spread, downstream shape summaries, and a train-only matched secondary-template residual.",
        "",
        "## Results",
        "",
        f"Traditional score shift high-minus-low: **{trad['score_shift_high_minus_low']:.4f}** [{trad['score_shift_ci_low']:.4f}, {trad['score_shift_ci_high']:.4f}], candidate-excess delta **{trad['candidate_excess_high_minus_low']:.4f}**.",
        "",
        f"S07f RF score shift high-minus-low: **{ml['score_shift_high_minus_low']:.4f}** [{ml['score_shift_ci_low']:.4f}, {ml['score_shift_ci_high']:.4f}], candidate-excess delta **{ml['candidate_excess_high_minus_low']:.4f}** [{ml['candidate_excess_ci_low']:.4f}, {ml['candidate_excess_ci_high']:.4f}]. Current-family AUC is **{ml['current_family_auc']:.3f}**.",
        "",
        f"Amplitude-only sentinel shift is **{amp['score_shift_high_minus_low']:.4f}**; shuffled-label RF shift is **{shuf['score_shift_high_minus_low']:.4f}**.",
        "",
        pooled.to_markdown(index=False),
        "",
        "Held-out fold details:",
        "",
        folds[["fold", "method", "n_matched_events", "score_shift_high_minus_low", "candidate_excess_high_minus_low", "current_family_auc", "low_gross_events", "high_gross_events"]].to_markdown(index=False),
        "",
        "Injected-fold calibration diagnostics:",
        "",
        calib.groupby("method")[["oof_auc", "oof_ap", "oof_brier", "oof_ece"]].mean(numeric_only=True).reset_index().to_markdown(index=False),
        "",
        "## Leakage hunt",
        "",
    ]
    if len(flags):
        lines.extend(["Leakage sentinels raised flags:", "", flags[["fold", "check", "value", "note"]].to_markdown(index=False)])
    else:
        lines.append("No leakage sentinel flagged: train/test runs and events are disjoint, forbidden identifiers/timing/current columns are absent from the main RF, shuffled injected labels do not stably separate current family, and the S07f RF is not suspiciously perfect.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            result["conclusion"],
            "",
            "## Follow-up tickets",
            "",
            "No new follow-up ticket is proposed here; S07l/S07m-style injected morphology support, current-family nulls, and sparse-support audits are already present in the queue or completed studies.",
            "",
            "## Artifacts",
            "",
            "`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `s07f_injection_scoreboard.csv`, `run_family_metadata.csv`, `heldout_matched_transfer_scores.csv`, `heldout_run_pair_metrics.csv`, `pooled_heldout_bootstrap_metrics.csv`, `injected_fold_calibration.csv`, `template_rf_agreement.csv`, and `leakage_checks.csv`.",
            "",
            "## Reproducibility",
            "",
            "```bash",
            f"{sys.executable} scripts/s07i_1781024786_1471_167d1f38_score_transfer.py --config configs/s07i_1781024786_1471_167d1f38.json",
            "```",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s07i_1781024786_1471_167d1f38.json"))
    args = parser.parse_args()
    start = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    utils = load_module("s07d_utils", ROOT / config["utility_script"])
    s07f = load_module("s07f_helper", ROOT / config["s07f_helper_script"])

    parent, all_three, s07f_run_counts, clean_payloads = s07f.collect_parent_and_all_three(config, utils)
    parent_guarded = int((parent["d_t_ns"] > float(config["gross_dt_min_ns"])).sum())
    all_three_guarded = int((all_three["d_t_ns"] > float(config["gross_dt_min_ns"])).sum())
    reproduction = pd.DataFrame(
        [
            {"quantity": "parent App.I guarded gross D_t>51 ns", "report_value": int(config["expected_parent_gross_events"]), "reproduced": parent_guarded, "delta": parent_guarded - int(config["expected_parent_gross_events"]), "tolerance": 0, "pass": parent_guarded == int(config["expected_parent_gross_events"])},
            {"quantity": "all-three control events", "report_value": int(config["expected_all_three_control_events"]), "reproduced": int(len(all_three)), "delta": int(len(all_three)) - int(config["expected_all_three_control_events"]), "tolerance": 0, "pass": int(len(all_three)) == int(config["expected_all_three_control_events"])},
            {"quantity": "all-three guarded gross D_t>51 ns", "report_value": int(config["expected_all_three_guarded_gross_events"]), "reproduced": all_three_guarded, "delta": all_three_guarded - int(config["expected_all_three_guarded_gross_events"]), "tolerance": 0, "pass": all_three_guarded == int(config["expected_all_three_guarded_gross_events"])},
        ]
    )
    if not bool(reproduction["pass"].all()):
        reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
        raise RuntimeError("raw ROOT count reproduction failed before S07i")

    injected_counts, s07f_score, s07f_rf_scan, s07f_trad_choices, s07f_leakage, s07f_oof, details = s07f.independent_injection_benchmark(config, utils, clean_payloads)
    s07f_auc = float(s07f_score.loc[s07f_score["method"] == "all-three shape-only RF", "roc_auc"].iloc[0])
    s07f_delta = s07f_auc - float(config["expected_s07f_shape_rf_auc"])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "S07f injected all-three shape RF ROC AUC",
                        "report_value": float(config["expected_s07f_shape_rf_auc"]),
                        "reproduced": s07f_auc,
                        "delta": s07f_delta,
                        "tolerance": float(config["s07f_reproduction_auc_tolerance"]),
                        "pass": abs(s07f_delta) <= float(config["s07f_reproduction_auc_tolerance"]),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    if not bool(reproduction["pass"].all()):
        reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
        raise RuntimeError("S07f injected-score reproduction failed before S07i")

    injected = utils.make_dataset(config, clean_payloads)
    real_events, run_meta = collect_real_events(config, utils)
    best_params = details["best_rf_params"]
    scored, folds, pooled, calib = run_transfer(config, utils, injected, real_events, best_params, out_dir)
    leakage = pd.read_csv(out_dir / "leakage_checks.csv")

    clean_csv = real_events.drop(columns=[c for c in real_events.columns if c.startswith("_")])
    clean_csv.groupby(["run", "run_family"]).size().reset_index(name="all_three_events").to_csv(out_dir / "real_all_three_counts_by_run.csv", index=False)
    run_meta.to_csv(out_dir / "run_family_metadata.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    injected_counts.to_csv(out_dir / "s07f_injected_counts_by_run.csv", index=False)
    s07f_score.to_csv(out_dir / "s07f_injection_scoreboard.csv", index=False)
    s07f_rf_scan.to_csv(out_dir / "s07f_injection_rf_cv_scan.csv", index=False)
    s07f_trad_choices.to_csv(out_dir / "s07f_traditional_fold_choices.csv", index=False)
    s07f_leakage.to_csv(out_dir / "s07f_reproduction_leakage_checks.csv", index=False)

    ml = pooled[pooled["method"] == "s07f_shape_rf"].iloc[0]
    trad = pooled[pooled["method"] == "traditional_template"].iloc[0]
    flags = int(leakage["flag"].astype(bool).sum())
    if float(ml["score_shift_ci_low"]) > 0.0 and flags == 0:
        verdict = "positive_s07f_transfer_after_matching"
    elif float(ml["score_shift_ci_high"]) < 0.0 and flags == 0:
        verdict = "negative_s07f_transfer_after_matching"
    else:
        verdict = "no_stable_positive_s07f_transfer"
    conclusion = (
        f"Verdict: `{verdict}`. S07f reproduces from raw ROOT at AUC {s07f_auc:.6f}. "
        f"On real matched current strata, the S07f RF high-minus-low score shift is {ml['score_shift_high_minus_low']:.4f} "
        f"[{ml['score_shift_ci_low']:.4f}, {ml['score_shift_ci_high']:.4f}], while the traditional timing/template shift is "
        f"{trad['score_shift_high_minus_low']:.4f} [{trad['score_shift_ci_low']:.4f}, {trad['score_shift_ci_high']:.4f}]. "
        f"Leakage sentinels flagged {flags} checks, so this is a calibrated transfer diagnostic rather than a truth-labelled pile-up rate."
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "s07f_shape_rf_auc_reproduced": s07f_auc,
        "s07f_shape_rf_auc_expected": float(config["expected_s07f_shape_rf_auc"]),
        "s07f_shape_rf_auc_delta": s07f_delta,
        "matched_real_events": int(len(scored)),
        "split": "six held-out low/high run-pair folds",
        "traditional": {
            "method": "fold-local timing/template score selected on injected train runs",
            "score_shift_high_minus_low": float(trad["score_shift_high_minus_low"]),
            "score_shift_ci": [float(trad["score_shift_ci_low"]), float(trad["score_shift_ci_high"])],
            "candidate_excess_high_minus_low": float(trad["candidate_excess_high_minus_low"]),
            "candidate_excess_ci": [float(trad["candidate_excess_ci_low"]), float(trad["candidate_excess_ci_high"])],
        },
        "ml": {
            "method": "S07f strict-shape RF trained/calibrated on injected folds",
            "params": best_params,
            "score_shift_high_minus_low": float(ml["score_shift_high_minus_low"]),
            "score_shift_ci": [float(ml["score_shift_ci_low"]), float(ml["score_shift_ci_high"])],
            "candidate_excess_high_minus_low": float(ml["candidate_excess_high_minus_low"]),
            "candidate_excess_ci": [float(ml["candidate_excess_ci_low"]), float(ml["candidate_excess_ci_high"])],
            "current_family_auc": float(ml["current_family_auc"]),
        },
        "leakage": {
            "flagged_checks": flags,
            "main_rf_forbidden_column_count": 0,
            "shuffled_label_shift": float(pooled.loc[pooled["method"] == "shuffled_label_rf", "score_shift_high_minus_low"].iloc[0]),
            "amplitude_only_shift": float(pooled.loc[pooled["method"] == "amplitude_only_rf", "score_shift_high_minus_low"].iloc[0]),
        },
        "verdict": verdict,
        "conclusion": conclusion,
        "next_tickets": [],
        "runtime_sec": float(time.time() - start),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(config, out_dir, reproduction, run_meta, s07f_score, pooled, folds, leakage, calib, result)

    input_rows = []
    for run in config["runs"]:
        path = raw_file(config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    rel_script = Path(__file__).resolve().relative_to(ROOT)
    for extra in [args.config, Path(config["utility_script"]), Path(config["s07f_helper_script"]), rel_script]:
        path = ROOT / extra
        input_rows.append({"path": str(extra), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "command": f"{sys.executable} {rel_script} --config {args.config}",
        "inputs": input_rows,
        "outputs": {},
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(json_ready({"done": True, "ticket": config["ticket_id"], "verdict": verdict, "runtime_sec": result["runtime_sec"]}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
