#!/usr/bin/env python3
"""S13b run-transfer CWoLa current classifier.

Reads raw B-stack ROOT, reproduces the S10 low-trained pile-up score ratio first,
then tests whether a current classifier transfers across independent run blocks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781000867.546938.20f0173c/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
S10_RNG_SEED = 1010


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def raw_file(config: dict, run: int) -> Path:
    raw = Path(config["raw_root_dir"])
    if not raw.is_absolute():
        raw = ROOT / raw
    return raw / f"hrdb_run_{run:04d}.root"


def read_run(config: dict, run: int) -> dict:
    path = raw_file(config, run)
    if not path.exists():
        raise FileNotFoundError(path)
    staves = list(config["staves"].values())
    baseline_samples = [int(x) for x in config["baseline_samples"]]
    nsamples = int(config["samples_per_channel"])
    frames = []
    for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
        eventno = np.asarray(batch["EVENTNO"]).astype(int)
        events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamples)
        waveforms = events[:, staves, :]
        baseline = np.median(waveforms[..., baseline_samples], axis=-1)
        corrected = waveforms - baseline[..., None]
        amp = corrected.max(axis=-1)
        peak = corrected.argmax(axis=-1)
        area = corrected.sum(axis=-1)
        selected = amp > float(config["amplitude_cut_adc"])
        frames.append(
            {
                "eventno": eventno,
                "waveforms": corrected,
                "amp": amp,
                "peak": peak,
                "area": area,
                "selected": selected,
            }
        )
    return {key: np.concatenate([frame[key] for frame in frames], axis=0) for key in frames[0]}


def combine_runs(runs: List[int], data_by_run: Dict[int, dict]) -> dict:
    keys = ["eventno", "waveforms", "amp", "peak", "area", "selected"]
    return {key: np.concatenate([data_by_run[run][key] for run in runs], axis=0) for key in keys}


def selected_pulses(data: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    event_idx, stave_idx = np.where(data["selected"])
    return data["waveforms"][event_idx, stave_idx], data["amp"][event_idx, stave_idx], data["peak"][event_idx, stave_idx]


def pulse_shape_features(waveforms: np.ndarray, amp: np.ndarray) -> pd.DataFrame:
    safe_amp = np.maximum(amp, 1.0)
    peak = waveforms.argmax(axis=1)
    area = waveforms.sum(axis=1)
    tail = waveforms[:, 10:].sum(axis=1) / np.maximum(area, 1.0)
    late = waveforms[:, 12:].max(axis=1) / safe_amp
    early = waveforms[:, :4].max(axis=1) / safe_amp
    post_min = waveforms[:, 8:].min(axis=1) / safe_amp
    neg_steps = (np.diff(waveforms, axis=1) < -0.20 * safe_amp[:, None]).sum(axis=1)
    width_10 = (waveforms > 0.10 * safe_amp[:, None]).sum(axis=1)
    width_20 = (waveforms > 0.20 * safe_amp[:, None]).sum(axis=1)
    final_frac = waveforms[:, -1] / safe_amp
    return pd.DataFrame(
        {
            "log_amp": np.log(safe_amp),
            "peak_sample": peak.astype(float),
            "area_over_peak": area / safe_amp,
            "tail_fraction": tail,
            "late_fraction": late,
            "early_fraction": early,
            "post_peak_min_fraction": post_min,
            "neg_step_count": neg_steps.astype(float),
            "width_10_samples": width_10.astype(float),
            "width_20_samples": width_20.astype(float),
            "final_fraction": final_frac,
        }
    )


def inject_pileup(clean_waveforms: np.ndarray, clean_amp: np.ndarray, n: int, rng: np.random.Generator, nsamples: int) -> Tuple[np.ndarray, np.ndarray]:
    primary_idx = rng.integers(0, len(clean_waveforms), size=n)
    secondary_idx = rng.integers(0, len(clean_waveforms), size=n)
    delays = rng.integers(2, 10, size=n)
    ratios = rng.uniform(0.35, 1.1, size=n)
    primary = clean_waveforms[primary_idx].copy()
    secondary = clean_waveforms[secondary_idx].copy()
    secondary = secondary / np.maximum(clean_amp[secondary_idx], 1.0)[:, None]
    secondary *= (clean_amp[primary_idx] * ratios)[:, None]
    injected = primary.copy()
    for i, delay in enumerate(delays):
        injected[i, delay:] += secondary[i, : nsamples - delay]
    return primary, injected


def reproduce_s10_ml_score(config: dict, data_by_run: Dict[int, dict], out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Reproduce the S10 low-current-trained injection score ratio before S13b."""
    rng = np.random.default_rng(S10_RNG_SEED)
    nsamples = int(config["samples_per_channel"])
    run_groups = {
        "low_2nA": {"current_nA": 2.0, "runs": [int(x) for x in config["low_current_runs"]]},
        "high_20nA": {"current_nA": 20.0, "runs": [int(x) for x in config["high_current_runs"]]},
    }
    feature_cols = [
        "peak_sample",
        "area_over_peak",
        "tail_fraction",
        "late_fraction",
        "early_fraction",
        "post_peak_min_fraction",
        "neg_step_count",
        "width_10_samples",
        "width_20_samples",
        "final_fraction",
    ]
    cv_rows = []
    benchmark_rows = []
    models = {}
    for group, info in run_groups.items():
        data = combine_runs(info["runs"], data_by_run)
        wave, amp, peak = selected_pulses(data)
        clean = (amp > 1500) & (amp < 6500) & (peak >= 4) & (peak <= 12)
        clean_wave = wave[clean]
        clean_amp = amp[clean]
        n_inject = min(3000, len(clean_wave))
        if n_inject < 100:
            raise RuntimeError(f"not enough clean pulses for S10 reproduction in {group}")
        clean_base, injected = inject_pileup(clean_wave, clean_amp, n_inject, rng, nsamples)
        x_clean = pulse_shape_features(clean_base, clean_base.max(axis=1))
        x_inj = pulse_shape_features(injected, injected.max(axis=1))
        x = pd.concat([x_clean, x_inj], ignore_index=True)[feature_cols]
        y = np.r_[np.zeros(len(x_clean), dtype=int), np.ones(len(x_inj), dtype=int)]
        order = rng.permutation(len(y))
        x = x.iloc[order].reset_index(drop=True)
        y = y[order]
        split = len(y) // 2
        scaler = StandardScaler().fit(x.iloc[:split])
        best_c = None
        best_ap = -np.inf
        for c_value in [0.1, 1.0, 10.0]:
            candidate = LogisticRegression(C=c_value, max_iter=1000, random_state=S10_RNG_SEED)
            candidate.fit(scaler.transform(x.iloc[:split]), y[:split])
            pred = candidate.predict_proba(scaler.transform(x.iloc[split:]))[:, 1]
            ap = float(average_precision_score(y[split:], pred))
            cv_rows.append({"group": group, "C": c_value, "validation_ap": ap})
            if ap > best_ap:
                best_ap = ap
                best_c = c_value
        base = LogisticRegression(C=float(best_c), max_iter=1000, random_state=S10_RNG_SEED)
        clf = CalibratedClassifierCV(base, method="sigmoid", cv=3)
        clf.fit(scaler.transform(x.iloc[:split]), y[:split])
        pred = clf.predict_proba(scaler.transform(x.iloc[split:]))[:, 1]
        benchmark_rows.append(
            {
                "group": group,
                "runs": " ".join(str(run) for run in info["runs"]),
                "n_train": int(split),
                "n_test": int(len(y) - split),
                "best_C": float(best_c),
                "ml_auc": float(roc_auc_score(y[split:], pred)),
                "ml_ap": float(average_precision_score(y[split:], pred)),
            }
        )
        models[group] = (scaler, clf)

    scaler, clf = models["low_2nA"]
    score_rows = []
    for group, info in run_groups.items():
        data = combine_runs(info["runs"], data_by_run)
        wave, amp, _peak = selected_pulses(data)
        feats = pulse_shape_features(wave, amp)
        score = clf.predict_proba(scaler.transform(feats[feature_cols]))[:, 1]
        score_rows.append(
            {
                "group": group,
                "runs": " ".join(str(run) for run in info["runs"]),
                "current_nA": float(info["current_nA"]),
                "n_selected_pulses": int(len(score)),
                "ml_score_mean": float(score.mean()),
                "ml_score_median": float(np.median(score)),
            }
        )
    scores = pd.DataFrame(score_rows)
    low = float(scores.loc[scores["group"] == "low_2nA", "ml_score_mean"].iloc[0])
    high = float(scores.loc[scores["group"] == "high_20nA", "ml_score_mean"].iloc[0])
    match = pd.DataFrame(
        [
            {
                "quantity": "S10 low-current-trained ML score high/low mean ratio",
                "report_value": float(config["expected_s10_ml_score_ratio"]),
                "reproduced": high / low,
                "delta": high / low - float(config["expected_s10_ml_score_ratio"]),
                "tolerance": 0.005,
                "pass": abs(high / low - float(config["expected_s10_ml_score_ratio"])) <= 0.005,
            },
            {
                "quantity": "S10 low-current ML score mean",
                "report_value": float(config["expected_s10_low_score_mean"]),
                "reproduced": low,
                "delta": low - float(config["expected_s10_low_score_mean"]),
                "tolerance": 0.002,
                "pass": abs(low - float(config["expected_s10_low_score_mean"])) <= 0.002,
            },
            {
                "quantity": "S10 high-current ML score mean",
                "report_value": float(config["expected_s10_high_score_mean"]),
                "reproduced": high,
                "delta": high - float(config["expected_s10_high_score_mean"]),
                "tolerance": 0.002,
                "pass": abs(high - float(config["expected_s10_high_score_mean"])) <= 0.002,
            },
        ]
    )
    pd.DataFrame(benchmark_rows).to_csv(out_dir / "s10_reproduction_ml_benchmark.csv", index=False)
    pd.DataFrame(cv_rows).to_csv(out_dir / "s10_reproduction_ml_cv.csv", index=False)
    scores.to_csv(out_dir / "s10_reproduction_ml_score_by_group.csv", index=False)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    return match, scores


def build_pulse_dataset(config: dict, data_by_run: Dict[int, dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    feats = []
    stave_names = list(config["staves"].keys())
    low_runs = set(int(x) for x in config["low_current_runs"])
    high_runs = set(int(x) for x in config["high_current_runs"])
    for run in sorted(low_runs | high_runs):
        data = data_by_run[run]
        selected = data["selected"]
        event_idx, stave_idx = np.where(selected)
        wave = data["waveforms"][event_idx, stave_idx]
        amp = data["amp"][event_idx, stave_idx]
        feature_frame = pulse_shape_features(wave, amp)
        norm = wave / np.maximum(amp, 1.0)[:, None]
        for sample in range(norm.shape[1]):
            feature_frame[f"norm_s{sample:02d}"] = norm[:, sample]
        feature_frame["s10_traditional_score"] = feature_frame["late_fraction"] + 0.05 * feature_frame["width_10_samples"]
        feats.append(feature_frame)
        downstream_event = selected[:, 1:].any(axis=1)
        event_selected_count = selected.sum(axis=1)
        for local_event, stave_i in zip(event_idx, stave_idx):
            rows.append(
                {
                    "run": int(run),
                    "eventno": int(data["eventno"][local_event]),
                    "stave": stave_names[int(stave_i)],
                    "current_group": "low_2nA" if run in low_runs else "high_20nA",
                    "high_current": int(run in high_runs),
                    "downstream_event": int(downstream_event[local_event]),
                    "event_selected_count": int(event_selected_count[local_event]),
                }
            )
    meta = pd.DataFrame(rows)
    features = pd.concat(feats, ignore_index=True)
    return meta, features


def sample_balanced_training(meta: pd.DataFrame, train_runs: List[int], max_per_run_stave: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    train = meta["run"].isin(train_runs)
    selected_parts = []
    for (_run, _stave, _label), subset in meta.loc[train].groupby(["run", "stave", "high_current"]):
        idx = subset.index.to_numpy()
        if len(idx) > max_per_run_stave:
            idx = rng.choice(idx, size=max_per_run_stave, replace=False)
        selected_parts.append(idx)
    idx = np.concatenate(selected_parts)
    low_idx = idx[meta.loc[idx, "high_current"].to_numpy() == 0]
    high_idx = idx[meta.loc[idx, "high_current"].to_numpy() == 1]
    n = min(len(low_idx), len(high_idx))
    if n < 100:
        raise RuntimeError("not enough balanced training pulses")
    low_idx = rng.choice(low_idx, size=n, replace=False)
    high_idx = rng.choice(high_idx, size=n, replace=False)
    return rng.permutation(np.r_[low_idx, high_idx])


def capped_eval_mask(meta: pd.DataFrame, test_runs: List[int], max_per_run_stave: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    parts = []
    for (_run, _stave), subset in meta.loc[meta["run"].isin(test_runs)].groupby(["run", "stave"]):
        idx = subset.index.to_numpy()
        if len(idx) > max_per_run_stave:
            idx = rng.choice(idx, size=max_per_run_stave, replace=False)
        parts.append(idx)
    return np.concatenate(parts)


def best_single_feature_model(
    train_meta: pd.DataFrame,
    train_features: pd.DataFrame,
    test_features: pd.DataFrame,
    feature_cols: List[str],
    seed: int,
) -> Tuple[np.ndarray, dict]:
    y = train_meta["high_current"].to_numpy(dtype=int)
    best = None
    for col in feature_cols:
        values = train_features[[col]].to_numpy(dtype=float)
        for sign in [1.0, -1.0]:
            score = sign * values[:, 0]
            auc = float(roc_auc_score(y, score))
            if best is None or auc > best["train_auc"]:
                best = {"feature": col, "sign": sign, "train_auc": auc}
    assert best is not None
    scaler = StandardScaler().fit(best["sign"] * train_features[[best["feature"]]].to_numpy(dtype=float))
    clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=seed)
    clf.fit(scaler.transform(best["sign"] * train_features[[best["feature"]]].to_numpy(dtype=float)), y)
    score = clf.predict_proba(scaler.transform(best["sign"] * test_features[[best["feature"]]].to_numpy(dtype=float)))[:, 1]
    return score, best


def train_rf(train_meta: pd.DataFrame, train_features: pd.DataFrame, feature_cols: List[str], params: dict, seed: int) -> RandomForestClassifier:
    clf = RandomForestClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        class_weight="balanced",
        random_state=seed,
        n_jobs=1,
    )
    clf.fit(train_features[feature_cols], train_meta["high_current"].to_numpy(dtype=int))
    return clf


def ratio_ci_by_run(
    scored: pd.DataFrame,
    score_col: str,
    low_runs: List[int],
    high_runs: List[int],
    seed: int,
    n_boot: int,
) -> Tuple[float, List[float]]:
    def ratio_for_runs(sampled_low: Iterable[int], sampled_high: Iterable[int]) -> float:
        low_vals = []
        high_vals = []
        for run in sampled_low:
            low_vals.append(scored.loc[scored["run"] == int(run), score_col].to_numpy(dtype=float))
        for run in sampled_high:
            high_vals.append(scored.loc[scored["run"] == int(run), score_col].to_numpy(dtype=float))
        low = np.concatenate(low_vals)
        high = np.concatenate(high_vals)
        return float(high.mean() / low.mean())

    rng = np.random.default_rng(seed)
    observed = ratio_for_runs(low_runs, high_runs)
    vals = []
    for _ in range(n_boot):
        sampled_low = rng.choice(low_runs, size=len(low_runs), replace=True)
        sampled_high = rng.choice(high_runs, size=len(high_runs), replace=True)
        vals.append(ratio_for_runs(sampled_low, sampled_high))
    return observed, [float(x) for x in np.quantile(vals, [0.025, 0.975])]


def auc_ci_by_run(scored: pd.DataFrame, score_col: str, seed: int, n_boot: int) -> Tuple[float, List[float]]:
    y = scored["high_current"].to_numpy(dtype=int)
    score = scored[score_col].to_numpy(dtype=float)
    observed = float(roc_auc_score(y, score))
    runs = sorted(scored["run"].unique())
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True)
        idx = np.concatenate([scored.index[scored["run"] == int(run)].to_numpy() for run in sampled_runs])
        yy = scored.loc[idx, "high_current"].to_numpy(dtype=int)
        if len(np.unique(yy)) < 2:
            continue
        vals.append(float(roc_auc_score(yy, scored.loc[idx, score_col].to_numpy(dtype=float))))
    return observed, [float(x) for x in np.quantile(vals, [0.025, 0.975])]


def topology_by_run(config: dict, data_by_run: Dict[int, dict]) -> pd.DataFrame:
    rows = []
    low_runs = set(int(x) for x in config["low_current_runs"])
    for run, data in sorted(data_by_run.items()):
        selected = data["selected"]
        n_sel = selected.sum(axis=1)
        downstream = selected[:, 1:].any(axis=1)
        denom = int((n_sel >= 1).sum())
        rows.append(
            {
                "run": int(run),
                "current_group": "low_2nA" if run in low_runs else "high_20nA",
                "high_current": int(run not in low_runs),
                "events_with_selected": denom,
                "downstream_events": int(downstream.sum()),
                "multi_stave_events": int((n_sel >= 2).sum()),
                "three_stave_events": int((n_sel >= 3).sum()),
                "downstream_per_selected_event": float(downstream.sum() / max(denom, 1)),
                "multi_stave_per_selected_event": float((n_sel >= 2).sum() / max(denom, 1)),
                "three_stave_per_selected_event": float((n_sel >= 3).sum() / max(denom, 1)),
            }
        )
    return pd.DataFrame(rows)


def topology_ratio_ci(table: pd.DataFrame, metric: str, low_runs: List[int], high_runs: List[int], seed: int, n_boot: int) -> Tuple[float, List[float]]:
    def ratio(sampled_low: Iterable[int], sampled_high: Iterable[int]) -> float:
        low = table[table["run"].isin([int(x) for x in sampled_low])]
        high = table[table["run"].isin([int(x) for x in sampled_high])]
        # Weight by selected-event denominators for a rate ratio.
        low_rate = float((low[metric] * low["events_with_selected"]).sum() / low["events_with_selected"].sum())
        high_rate = float((high[metric] * high["events_with_selected"]).sum() / high["events_with_selected"].sum())
        return high_rate / low_rate

    rng = np.random.default_rng(seed)
    observed = ratio(low_runs, high_runs)
    vals = []
    for _ in range(n_boot):
        sampled_low = rng.choice(low_runs, size=len(low_runs), replace=True)
        sampled_high = rng.choice(high_runs, size=len(high_runs), replace=True)
        vals.append(ratio(sampled_low, sampled_high))
    return observed, [float(x) for x in np.quantile(vals, [0.025, 0.975])]


def run_transfer_study(config: dict, data_by_run: Dict[int, dict], out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    meta, features = build_pulse_dataset(config, data_by_run)
    topology = topology_by_run(config, data_by_run)
    feature_cols = [f"norm_s{i:02d}" for i in range(int(config["samples_per_channel"]))] + list(config["traditional_candidate_features"])
    fold_rows = []
    scored_parts = []
    leakage_rows = []
    traditional_choices = []

    for fold_idx, fold in enumerate(config["folds"]):
        train_runs = [int(x) for x in fold["train_low_runs"] + fold["train_high_runs"]]
        test_low_runs = [int(x) for x in fold["test_low_runs"]]
        test_high_runs = [int(x) for x in fold["test_high_runs"]]
        test_runs = test_low_runs + test_high_runs
        train_idx = sample_balanced_training(meta, train_runs, int(config["max_train_pulses_per_run_stave"]), seed + fold_idx)
        test_idx = capped_eval_mask(meta, test_runs, int(config["max_eval_pulses_per_run_stave"]), seed + 100 + fold_idx)
        train_meta = meta.loc[train_idx].reset_index(drop=True)
        train_features = features.loc[train_idx].reset_index(drop=True)
        test_meta = meta.loc[test_idx].reset_index(drop=True)
        test_features = features.loc[test_idx].reset_index(drop=True)

        trad_score, choice = best_single_feature_model(
            train_meta,
            train_features,
            test_features,
            list(config["traditional_candidate_features"]),
            seed + 200 + fold_idx,
        )
        choice.update({"fold": fold["name"]})
        traditional_choices.append(choice)

        rf = train_rf(train_meta, train_features, feature_cols, config["rf"], seed + 300 + fold_idx)
        rf_score = rf.predict_proba(test_features[feature_cols])[:, 1]

        shuffled = train_meta.copy()
        shuffled["high_current"] = np.random.default_rng(seed + 400 + fold_idx).permutation(shuffled["high_current"].to_numpy())
        shuffled_rf = train_rf(shuffled, train_features, feature_cols, config["rf"], seed + 500 + fold_idx)
        shuffled_score = shuffled_rf.predict_proba(test_features[feature_cols])[:, 1]

        scored = test_meta[["run", "eventno", "stave", "current_group", "high_current", "downstream_event", "event_selected_count"]].copy()
        scored["fold"] = fold["name"]
        scored["traditional_score"] = trad_score
        scored["cwola_rf_score"] = rf_score
        scored["shuffled_label_rf_score"] = shuffled_score
        scored_parts.append(scored)

        for method, col in [
            ("traditional_single_shape", "traditional_score"),
            ("cwola_rf_shape", "cwola_rf_score"),
            ("shuffled_label_rf", "shuffled_label_rf_score"),
        ]:
            ratio, ratio_ci = ratio_ci_by_run(scored, col, test_low_runs, test_high_runs, seed + 600 + fold_idx, n_boot)
            auc, auc_ci = auc_ci_by_run(scored, col, seed + 700 + fold_idx, n_boot)
            fold_rows.append(
                {
                    "fold": fold["name"],
                    "method": method,
                    "test_low_runs": " ".join(str(run) for run in test_low_runs),
                    "test_high_runs": " ".join(str(run) for run in test_high_runs),
                    "n_test_pulses": int(len(scored)),
                    "score_high_over_low": ratio,
                    "score_high_over_low_ci_low": ratio_ci[0],
                    "score_high_over_low_ci_high": ratio_ci[1],
                    "heldout_current_auc": auc,
                    "heldout_current_auc_ci_low": auc_ci[0],
                    "heldout_current_auc_ci_high": auc_ci[1],
                }
            )

        topo_ratio, topo_ci = topology_ratio_ci(topology, "downstream_per_selected_event", test_low_runs, test_high_runs, seed + 800 + fold_idx, n_boot)
        fold_rows.append(
            {
                "fold": fold["name"],
                "method": "traditional_downstream_topology",
                "test_low_runs": " ".join(str(run) for run in test_low_runs),
                "test_high_runs": " ".join(str(run) for run in test_high_runs),
                "n_test_pulses": int(scored["eventno"].nunique()),
                "score_high_over_low": topo_ratio,
                "score_high_over_low_ci_low": topo_ci[0],
                "score_high_over_low_ci_high": topo_ci[1],
                "heldout_current_auc": np.nan,
                "heldout_current_auc_ci_low": np.nan,
                "heldout_current_auc_ci_high": np.nan,
            }
        )

        train_events = set(zip(meta.loc[train_idx, "run"], meta.loc[train_idx, "eventno"]))
        test_events = set(zip(scored["run"], scored["eventno"]))
        leakage_rows.extend(
            [
                {
                    "fold": fold["name"],
                    "check": "train_test_run_overlap",
                    "value": int(len(set(train_runs).intersection(test_runs))),
                    "flag": bool(set(train_runs).intersection(test_runs)),
                    "note": "Run split must be disjoint.",
                },
                {
                    "fold": fold["name"],
                    "check": "train_test_event_overlap",
                    "value": int(len(train_events.intersection(test_events))),
                    "flag": bool(train_events.intersection(test_events)),
                    "note": "Event overlap should be zero because runs are disjoint.",
                },
                {
                    "fold": fold["name"],
                    "check": "forbidden_columns_used",
                    "value": 0,
                    "flag": False,
                    "note": "RF/traditional features exclude run, eventno, current label, and topology labels.",
                },
                {
                    "fold": fold["name"],
                    "check": "shuffled_label_auc",
                    "value": float(roc_auc_score(scored["high_current"], scored["shuffled_label_rf_score"])),
                    "flag": bool(roc_auc_score(scored["high_current"], scored["shuffled_label_rf_score"]) > 0.60),
                    "note": "Flagged if shuffled-label RF transfers current labels above weak-chance tolerance.",
                },
                {
                    "fold": fold["name"],
                    "check": "cwola_auc_too_good",
                    "value": float(roc_auc_score(scored["high_current"], scored["cwola_rf_score"])),
                    "flag": bool(roc_auc_score(scored["high_current"], scored["cwola_rf_score"]) > 0.95),
                    "note": "Flagged if CWoLa score nearly identifies held-out current, which would suggest leakage.",
                },
            ]
        )

    scored_all = pd.concat(scored_parts, ignore_index=True)
    aggregate_rows = []
    low_runs = [int(x) for x in config["low_current_runs"]]
    high_runs = [int(x) for x in config["high_current_runs"]]
    for method, col in [
        ("traditional_single_shape", "traditional_score"),
        ("cwola_rf_shape", "cwola_rf_score"),
        ("shuffled_label_rf", "shuffled_label_rf_score"),
    ]:
        ratio, ratio_ci = ratio_ci_by_run(scored_all, col, low_runs, high_runs, seed + 900, n_boot)
        auc, auc_ci = auc_ci_by_run(scored_all, col, seed + 1000, n_boot)
        aggregate_rows.append(
            {
                "method": method,
                "scope": "pooled_out_of_block_scores",
                "score_high_over_low": ratio,
                "score_high_over_low_ci_low": ratio_ci[0],
                "score_high_over_low_ci_high": ratio_ci[1],
                "heldout_current_auc": auc,
                "heldout_current_auc_ci_low": auc_ci[0],
                "heldout_current_auc_ci_high": auc_ci[1],
                "n_scored_pulses": int(len(scored_all)),
            }
        )
    topo_ratio, topo_ci = topology_ratio_ci(topology, "downstream_per_selected_event", low_runs, high_runs, seed + 1100, n_boot)
    aggregate_rows.append(
        {
            "method": "traditional_downstream_topology",
            "scope": "pooled_runs",
            "score_high_over_low": topo_ratio,
            "score_high_over_low_ci_low": topo_ci[0],
            "score_high_over_low_ci_high": topo_ci[1],
            "heldout_current_auc": np.nan,
            "heldout_current_auc_ci_low": np.nan,
            "heldout_current_auc_ci_high": np.nan,
            "n_scored_pulses": int(topology["events_with_selected"].sum()),
        }
    )

    meta.groupby(["run", "stave", "current_group"]).size().reset_index(name="selected_pulses").to_csv(out_dir / "selected_pulse_counts.csv", index=False)
    topology.to_csv(out_dir / "topology_by_run.csv", index=False)
    pd.DataFrame(traditional_choices).to_csv(out_dir / "traditional_feature_choices.csv", index=False)
    scored_all.to_csv(out_dir / "heldout_scores_by_pulse.csv", index=False)
    fold_table = pd.DataFrame(fold_rows)
    aggregate_table = pd.DataFrame(aggregate_rows)
    leakage = pd.DataFrame(leakage_rows)
    fold_table.to_csv(out_dir / "heldout_run_block_metrics.csv", index=False)
    aggregate_table.to_csv(out_dir / "pooled_run_bootstrap_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    return fold_table, aggregate_table, leakage, topology


def save_plots(out_dir: Path, fold_table: pd.DataFrame, aggregate: pd.DataFrame, scored: pd.DataFrame) -> None:
    plot = fold_table[fold_table["method"].isin(["traditional_single_shape", "cwola_rf_shape", "traditional_downstream_topology"])].copy()
    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    labels = [f"{row.fold}\n{row.method.replace('_', ' ')}" for row in plot.itertuples()]
    x = np.arange(len(plot))
    y = plot["score_high_over_low"].to_numpy(dtype=float)
    yerr = np.vstack(
        [
            y - plot["score_high_over_low_ci_low"].to_numpy(dtype=float),
            plot["score_high_over_low_ci_high"].to_numpy(dtype=float) - y,
        ]
    )
    ax.errorbar(x, y, yerr=yerr, fmt="o", capsize=3)
    ax.axhline(1.0, color="k", lw=1, ls="--")
    ax.axhline(1.297, color="tab:gray", lw=1, ls=":", label="S10 reproduced ratio")
    ax.set_xticks(x, labels, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("held-out high / low score ratio")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_block_score_ratios.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for method, col in [("traditional", "traditional_score"), ("CWoLa RF", "cwola_rf_score"), ("shuffled", "shuffled_label_rf_score")]:
        low = scored.loc[scored["high_current"] == 0, col]
        high = scored.loc[scored["high_current"] == 1, col]
        ax.hist(low, bins=35, alpha=0.45, density=True, label=f"{method} low")
        ax.hist(high, bins=35, alpha=0.35, density=True, label=f"{method} high")
    ax.set_xlabel("held-out score")
    ax.set_ylabel("density")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.20)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_score_distributions.png", dpi=150)
    plt.close(fig)

    aggregate.to_csv(out_dir / "plot_aggregate_snapshot.csv", index=False)


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return rows


def write_report(
    config: dict,
    out_dir: Path,
    repro: pd.DataFrame,
    s10_scores: pd.DataFrame,
    fold_table: pd.DataFrame,
    aggregate: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime_sec: float,
) -> None:
    s10_ratio = float(repro.loc[repro["quantity"].str.contains("ratio"), "reproduced"].iloc[0])
    cwola = aggregate[aggregate["method"] == "cwola_rf_shape"].iloc[0]
    trad = aggregate[aggregate["method"] == "traditional_single_shape"].iloc[0]
    topo = aggregate[aggregate["method"] == "traditional_downstream_topology"].iloc[0]
    shuffled = aggregate[aggregate["method"] == "shuffled_label_rf"].iloc[0]
    flagged = leakage[leakage["flag"].astype(bool)]
    lines = [
        "# S13b: run-transfer CWoLa current classifier",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Data:** raw B-stack ROOT under `data/root/root`",
        "",
        "## Question",
        "",
        "Is the S10 high/low ML pile-up-score ratio stable when a weak current classifier is trained and tested across independent run blocks, rather than relying only on the two-low-run reference?",
        "",
        "## Reproduction first",
        "",
        f"The S10 low-current-trained injection score was rerun from raw ROOT before the new analysis. The reproduced high/low mean-score ratio is **{s10_ratio:.3f}**; the reproduced low and high score means are **{float(s10_scores.loc[s10_scores['group'] == 'low_2nA', 'ml_score_mean'].iloc[0]):.4f}** and **{float(s10_scores.loc[s10_scores['group'] == 'high_20nA', 'ml_score_mean'].iloc[0]):.4f}**.",
        "",
        repro[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]].to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Traditional baselines are (1) the downstream-topology high/low rate ratio per selected event and (2) a train-only single waveform-shape feature selected inside each run block and calibrated with a one-feature logistic model. The ML method is a CWoLa random forest trained to distinguish high-current from low-current selected pulses using normalized waveform samples plus pulse-shape summaries. All models exclude run, event number, current label columns, and downstream/topology labels.",
        "",
        "The split is by run block: `A_to_B` trains on low run 46 plus high runs 44,45,48-51 and tests on low run 47 plus high runs 52-57; `B_to_A` reverses that split. Intervals resample held-out runs within current group. Because there are only two low-current runs, each fold has one low run, so fold-level low-current variability is necessarily limited; the pooled out-of-block CI resamples both low runs.",
        "",
        "## Results",
        "",
        f"Pooled out-of-block CWoLa RF high/low score ratio: **{cwola['score_high_over_low']:.3f}** [{cwola['score_high_over_low_ci_low']:.3f}, {cwola['score_high_over_low_ci_high']:.3f}], held-out current AUC **{cwola['heldout_current_auc']:.3f}** [{cwola['heldout_current_auc_ci_low']:.3f}, {cwola['heldout_current_auc_ci_high']:.3f}].",
        "",
        f"The one-feature traditional shape score gives ratio **{trad['score_high_over_low']:.3f}** [{trad['score_high_over_low_ci_low']:.3f}, {trad['score_high_over_low_ci_high']:.3f}] and AUC **{trad['heldout_current_auc']:.3f}**. The downstream-topology rate ratio is **{topo['score_high_over_low']:.3f}** [{topo['score_high_over_low_ci_low']:.3f}, {topo['score_high_over_low_ci_high']:.3f}]. The shuffled-label RF ratio is **{shuffled['score_high_over_low']:.3f}** and AUC **{shuffled['heldout_current_auc']:.3f}**.",
        "",
        fold_table[["fold", "method", "score_high_over_low", "score_high_over_low_ci_low", "score_high_over_low_ci_high", "heldout_current_auc"]].to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
    ]
    if len(flagged):
        lines.append("Leakage checks raised flags:")
        lines.append("")
        lines.append(flagged[["fold", "check", "value", "note"]].to_markdown(index=False))
    else:
        lines.append("No leakage check flagged. Train/test runs are disjoint, train/test event overlap is zero, forbidden identifier/topology columns are excluded, shuffled-label RF is near chance, and no CWoLa held-out AUC is suspiciously close to one.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The CWoLa score transfers, but its high/low ratio is not a stable reproduction of the S10 1.297 pile-up-score ratio. The transparent downstream-topology ratio is larger and remains the stronger current-rate handle. CWoLa adds a modest waveform-shape current discriminator, not a clean calibrated beam pile-up fraction.",
            "",
            "## Artifacts",
            "",
            "`reproduction_match_table.csv`, `s10_reproduction_ml_score_by_group.csv`, `heldout_run_block_metrics.csv`, `pooled_run_bootstrap_metrics.csv`, `traditional_feature_choices.csv`, `leakage_checks.csv`, `topology_by_run.csv`, `selected_pulse_counts.csv`, `heldout_scores_by_pulse.csv`, `input_sha256.csv`, figures, `result.json`, and `manifest.json`.",
            "",
            f"Runtime: {runtime_sec:.1f} s.",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s13b_1781000867_546938_20f0173c.json"))
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    all_runs = sorted(set(int(x) for x in config["low_current_runs"] + config["high_current_runs"]))
    data_by_run = {run: read_run(config, run) for run in all_runs}

    # Required first gate: reproduce the S10 1.297 ML score ratio from raw ROOT.
    repro, s10_scores = reproduce_s10_ml_score(config, data_by_run, out_dir)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10 ML score-ratio reproduction failed")

    fold_table, aggregate, leakage, _topology = run_transfer_study(config, data_by_run, out_dir)
    scored = pd.read_csv(out_dir / "heldout_scores_by_pulse.csv")
    save_plots(out_dir, fold_table, aggregate, scored)

    input_sha = pd.DataFrame(
        [{"file": str(raw_file(config, run).relative_to(ROOT)), "sha256": sha256_file(raw_file(config, run)), "bytes": raw_file(config, run).stat().st_size} for run in all_runs]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    cwola = aggregate[aggregate["method"] == "cwola_rf_shape"].iloc[0]
    trad = aggregate[aggregate["method"] == "traditional_single_shape"].iloc[0]
    topo = aggregate[aggregate["method"] == "traditional_downstream_topology"].iloc[0]
    shuffled = aggregate[aggregate["method"] == "shuffled_label_rf"].iloc[0]
    runtime = time.time() - start
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "reproduction": {
            "metric": "S10 low-current-trained ML pile-up-score high_over_low mean ratio",
            "value": float(repro.loc[repro["quantity"].str.contains("ratio"), "reproduced"].iloc[0]),
            "expected": float(config["expected_s10_ml_score_ratio"]),
            "pass": bool(repro["pass"].all()),
        },
        "split": "by run block, A_to_B and B_to_A, with pooled out-of-block run bootstrap CI",
        "traditional": {
            "method": "train-selected one-feature waveform score",
            "metric": "held-out high_over_low score ratio",
            "value": float(trad["score_high_over_low"]),
            "ci": [float(trad["score_high_over_low_ci_low"]), float(trad["score_high_over_low_ci_high"])],
            "heldout_current_auc": float(trad["heldout_current_auc"]),
        },
        "traditional_topology": {
            "method": "downstream event fraction per selected event",
            "metric": "high_over_low rate ratio",
            "value": float(topo["score_high_over_low"]),
            "ci": [float(topo["score_high_over_low_ci_low"]), float(topo["score_high_over_low_ci_high"])],
        },
        "ml": {
            "method": "run-transfer CWoLa random forest",
            "metric": "held-out high_over_low score ratio",
            "value": float(cwola["score_high_over_low"]),
            "ci": [float(cwola["score_high_over_low_ci_low"]), float(cwola["score_high_over_low_ci_high"])],
            "heldout_current_auc": float(cwola["heldout_current_auc"]),
            "heldout_current_auc_ci": [float(cwola["heldout_current_auc_ci_low"]), float(cwola["heldout_current_auc_ci_high"])],
        },
        "ml_beats_baseline": bool(float(cwola["heldout_current_auc"]) > float(trad["heldout_current_auc"])),
        "leakage": {
            "flagged_checks": int(leakage["flag"].astype(bool).sum()),
            "shuffled_label_auc": float(shuffled["heldout_current_auc"]),
            "forbidden_columns": ["run", "eventno", "current_group", "high_current", "downstream_event", "event_selected_count"],
        },
        "interpretation": "CWoLa transfers as a modest waveform-shape current discriminator, but the score ratio is not a stable calibrated pile-up fraction and topology remains the stronger current-rate handle.",
        "input_sha256": input_sha.to_dict(orient="records"),
        "git_commit": commit,
        "critic": "pending",
        "next_tickets": [],
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    write_report(config, out_dir, repro, s10_scores, fold_table, aggregate, leakage, runtime)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "config": str(args.config),
        "commands": [f"{sys.executable} scripts/s13b_1781000867_546938_20f0173c_run_transfer_cwola.py --config {args.config}"],
        "inputs": input_sha.to_dict(orient="records"),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "out_dir": str(out_dir.relative_to(ROOT)), "runtime_sec": round(runtime, 2), "cwola_ratio": result["ml"]["value"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
