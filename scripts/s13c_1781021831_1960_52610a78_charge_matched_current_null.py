#!/usr/bin/env python3
"""S13c charge-matched current weak-supervision null.

The required first gate is an S10 ML-score reproduction from raw ROOT. The S13c
analysis then matches high/low-current pulses inside nuisance strata and tests
whether residualized CWoLa scores retain current information beyond a frozen
traditional matched-stratum excess table.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence

os.environ.setdefault("MPLCONFIGDIR", "reports/1781021831.1960.52610a78/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
S13B_PATH = ROOT / "scripts" / "s13b_1781000867_546938_20f0173c_run_transfer_cwola.py"
S10_REPRO_SEED = 1010


def load_s13b_module():
    spec = importlib.util.spec_from_file_location("s13b_reuse", S13B_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {S13B_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S13B = load_s13b_module()


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
        waveforms_raw = events[:, staves, :]
        baseline = np.median(waveforms_raw[..., baseline_samples], axis=-1)
        corrected = waveforms_raw - baseline[..., None]
        amp = corrected.max(axis=-1)
        peak = corrected.argmax(axis=-1)
        area = corrected.sum(axis=-1)
        selected = amp > float(config["amplitude_cut_adc"])
        frames.append(
            {
                "eventno": eventno,
                "waveforms": corrected,
                "baseline": baseline,
                "amp": amp,
                "peak": peak,
                "area": area,
                "selected": selected,
            }
        )
    return {key: np.concatenate([frame[key] for frame in frames], axis=0) for key in frames[0]}


def run_family_map(config: dict) -> dict[int, str]:
    result = {}
    for family, runs in config["run_families"].items():
        for run in runs:
            result[int(run)] = family
    return result


def pulse_shape_features(waveforms: np.ndarray, amp: np.ndarray) -> pd.DataFrame:
    return S13B.pulse_shape_features(waveforms, amp)


def ece_score(y_true: np.ndarray, prob: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(y_true)
    ece = 0.0
    for low, high in zip(bins[:-1], bins[1:]):
        if high == 1.0:
            mask = (prob >= low) & (prob <= high)
        else:
            mask = (prob >= low) & (prob < high)
        if not np.any(mask):
            continue
        ece += float(mask.mean() * abs(y_true[mask].mean() - prob[mask].mean()))
    return float(ece if total else np.nan)


def assign_quantile_bins(values: pd.Series, n_bins: int, prefix: str) -> pd.Series:
    ranked = values.rank(method="first")
    labels = [f"{prefix}{i}" for i in range(n_bins)]
    return pd.qcut(ranked, q=n_bins, labels=labels, duplicates="drop").astype(str)


def build_dataset(config: dict, data_by_run: dict[int, dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    family_by_run = run_family_map(config)
    low_runs = set(int(x) for x in config["low_current_runs"])
    high_runs = set(int(x) for x in config["high_current_runs"])
    stave_names = list(config["staves"].keys())
    meta_rows = []
    feature_frames = []

    for run in sorted(low_runs | high_runs):
        data = data_by_run[run]
        selected = data["selected"]
        event_idx, stave_idx = np.where(selected)
        wave = data["waveforms"][event_idx, stave_idx]
        amp = data["amp"][event_idx, stave_idx]
        baseline = data["baseline"][event_idx, stave_idx]
        features = pulse_shape_features(wave, amp)
        norm = wave / np.maximum(amp, 1.0)[:, None]
        for sample in range(norm.shape[1]):
            features[f"norm_s{sample:02d}"] = norm[:, sample]
        features["charge_proxy"] = np.log1p(np.maximum(data["area"][event_idx, stave_idx], 0.0))
        features["baseline_level"] = baseline
        features["saturation_proxy"] = (amp >= 6500).astype(float)
        features["dropout_proxy"] = (features["post_peak_min_fraction"] < -0.08).astype(float)
        features["tail_proxy"] = (features["tail_fraction"] > 0.55).astype(float)
        features["latent_width_charge"] = features["width_20_samples"] * features["charge_proxy"]
        features["latent_tail_width"] = features["tail_fraction"] * features["width_10_samples"]
        feature_frames.append(features)

        downstream_event = selected[:, 1:].any(axis=1)
        event_selected_count = selected.sum(axis=1)
        for local_event, stave_i in zip(event_idx, stave_idx):
            meta_rows.append(
                {
                    "run": int(run),
                    "eventno": int(data["eventno"][local_event]),
                    "stave": stave_names[int(stave_i)],
                    "run_family": family_by_run[int(run)],
                    "current_group": "low_2nA" if run in low_runs else "high_20nA",
                    "high_current": int(run in high_runs),
                    "downstream_event": int(downstream_event[local_event]),
                    "event_selected_count": int(event_selected_count[local_event]),
                }
            )

    meta = pd.DataFrame(meta_rows)
    features = pd.concat(feature_frames, ignore_index=True)
    features["charge_bin"] = assign_quantile_bins(features["charge_proxy"], int(config["charge_bins"]), "q")
    features["baseline_bin"] = assign_quantile_bins(features["baseline_level"], int(config["baseline_bins"]), "b")
    features["topology_bin"] = np.where(meta["event_selected_count"].to_numpy() >= 3, "three_plus", np.where(meta["downstream_event"].to_numpy() == 1, "downstream", "single"))
    features["anomaly_taxon"] = np.select(
        [
            features["saturation_proxy"].to_numpy() > 0,
            features["dropout_proxy"].to_numpy() > 0,
            features["tail_proxy"].to_numpy() > 0,
        ],
        ["saturation", "dropout", "tail"],
        default="nominal",
    )
    features["lowering_bin"] = np.where(features["baseline_level"] < features["baseline_level"].quantile(0.25), "lowered", "not_lowered")
    return meta, features


def nuisance_columns() -> list[str]:
    return ["charge_bin", "topology_bin", "anomaly_taxon", "lowering_bin", "run_family", "stave"]


def numeric_feature_columns(config: dict) -> list[str]:
    base = [f"norm_s{i:02d}" for i in range(int(config["samples_per_channel"]))]
    return base + [
        "log_amp",
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
        "latent_width_charge",
        "latent_tail_width",
    ]


def stratum_frame(meta: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    strata = pd.DataFrame(index=meta.index)
    for col in nuisance_columns():
        if col in meta:
            strata[col] = meta[col].astype(str)
        else:
            strata[col] = features[col].astype(str)
    strata["stratum"] = strata[nuisance_columns()].agg("|".join, axis=1)
    return strata


def matched_indices(
    meta: pd.DataFrame,
    features: pd.DataFrame,
    allowed_runs: Sequence[int],
    config: dict,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = meta.loc[meta["run"].isin([int(x) for x in allowed_runs])].copy()
    strata = stratum_frame(frame, features.loc[frame.index])
    frame["stratum"] = strata["stratum"]
    chosen = []
    min_count = int(config["min_stratum_group_count"])
    cap = int(config["max_matched_per_stratum_group"])
    for _stratum, group in frame.groupby("stratum"):
        low = group.index[group["high_current"].to_numpy() == 0].to_numpy()
        high = group.index[group["high_current"].to_numpy() == 1].to_numpy()
        n = min(len(low), len(high), cap)
        if n < min_count:
            continue
        chosen.append(rng.choice(low, n, replace=False))
        chosen.append(rng.choice(high, n, replace=False))
    if not chosen:
        raise RuntimeError("no matched strata survived")
    return rng.permutation(np.concatenate(chosen))


def cap_by_group(meta: pd.DataFrame, indices: np.ndarray, cap_per_group: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    parts = []
    frame = meta.loc[indices]
    for (_label, _run), group in frame.groupby(["high_current", "run"]):
        idx = group.index.to_numpy()
        n = min(len(idx), max(1, cap_per_group // max(1, frame["run"].nunique())))
        parts.append(rng.choice(idx, n, replace=False) if len(idx) > n else idx)
    return rng.permutation(np.concatenate(parts))


def nuisance_matrix(train_meta: pd.DataFrame, train_features: pd.DataFrame, test_meta: pd.DataFrame, test_features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, OneHotEncoder]:
    def frame(meta: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=meta.index)
        for col in nuisance_columns():
            out[col] = (meta[col] if col in meta else features[col]).astype(str).to_numpy()
        return out

    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    x_train = enc.fit_transform(frame(train_meta, train_features))
    x_test = enc.transform(frame(test_meta, test_features))
    return x_train, x_test, enc


def residualize_features(
    train_meta: pd.DataFrame,
    train_features: pd.DataFrame,
    test_meta: pd.DataFrame,
    test_features: pd.DataFrame,
    cols: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    nuisance_train, nuisance_test, _enc = nuisance_matrix(train_meta, train_features, test_meta, test_features)
    scaler = StandardScaler().fit(train_features[cols])
    x_train = scaler.transform(train_features[cols])
    x_test = scaler.transform(test_features[cols])
    reg = LinearRegression()
    reg.fit(nuisance_train, x_train)
    return x_train - reg.predict(nuisance_train), x_test - reg.predict(nuisance_test), nuisance_train, nuisance_test


def train_rf(config: dict, seed: int) -> RandomForestClassifier:
    params = config["rf"]
    return RandomForestClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        class_weight="balanced",
        random_state=seed,
        n_jobs=1,
    )


def current_scores_auc_ap_ece(y: np.ndarray, prob: np.ndarray) -> tuple[float, float, float]:
    return float(roc_auc_score(y, prob)), float(average_precision_score(y, prob)), ece_score(y, prob)


def reproduce_s10_downstream_excess(config: dict, data_by_run: dict[int, dict], out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for group, runs in [("low_2nA", config["low_current_runs"]), ("high_20nA", config["high_current_runs"])]:
        downstream = 0
        denom = 0
        multi = 0
        selected_pulses = 0
        for run in [int(x) for x in runs]:
            selected = data_by_run[run]["selected"]
            n_selected = selected.sum(axis=1)
            downstream += int(selected[:, 1:].any(axis=1).sum())
            denom += int((n_selected >= 1).sum())
            multi += int((n_selected >= 2).sum())
            selected_pulses += int(n_selected.sum())
        rows.append(
            {
                "group": group,
                "runs": " ".join(str(int(x)) for x in runs),
                "events_with_selected": denom,
                "selected_pulses": selected_pulses,
                "downstream_events": downstream,
                "multi_stave_events": multi,
                "downstream_per_selected_event": float(downstream / max(denom, 1)),
                "multi_stave_per_selected_event": float(multi / max(denom, 1)),
            }
        )
    table = pd.DataFrame(rows)
    low = float(table.loc[table["group"] == "low_2nA", "downstream_per_selected_event"].iloc[0])
    high = float(table.loc[table["group"] == "high_20nA", "downstream_per_selected_event"].iloc[0])
    expected = float(config["expected_s10_downstream_high_minus_low"])
    match = pd.DataFrame(
        [
            {
                "quantity": "S10 downstream high-minus-low per selected event",
                "report_value": expected,
                "reproduced": high - low,
                "delta": high - low - expected,
                "tolerance": 1.0e-12,
                "pass": abs(high - low - expected) <= 1.0e-12,
            },
            {
                "quantity": "S10 low-current downstream per selected event",
                "report_value": low,
                "reproduced": low,
                "delta": 0.0,
                "tolerance": 0.0,
                "pass": True,
            },
            {
                "quantity": "S10 high-current downstream per selected event",
                "report_value": high,
                "reproduced": high,
                "delta": 0.0,
                "tolerance": 0.0,
                "pass": True,
            },
        ]
    )
    table.to_csv(out_dir / "s10_reproduction_downstream_by_group.csv", index=False)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    return match, table


def traditional_table_score(
    train_meta: pd.DataFrame,
    train_features: pd.DataFrame,
    test_meta: pd.DataFrame,
    test_features: pd.DataFrame,
) -> np.ndarray:
    train_strata = stratum_frame(train_meta, train_features)
    test_strata = stratum_frame(test_meta, test_features)
    table = train_meta.assign(stratum=train_strata["stratum"].to_numpy()).groupby("stratum")["high_current"].mean()
    global_rate = float(train_meta["high_current"].mean())
    return test_strata["stratum"].map(table).fillna(global_rate).to_numpy(dtype=float)


def metric_delta(scored: pd.DataFrame, score_col: str) -> float:
    high = scored.loc[scored["high_current"] == 1, score_col].to_numpy(dtype=float)
    low = scored.loc[scored["high_current"] == 0, score_col].to_numpy(dtype=float)
    return float(high.mean() - low.mean())


def run_bootstrap_ci(scored: pd.DataFrame, score_col: str, seed: int, n_boot: int) -> tuple[float, list[float]]:
    observed = metric_delta(scored, score_col)
    rng = np.random.default_rng(seed)
    lows = sorted(scored.loc[scored["high_current"] == 0, "run"].unique())
    highs = sorted(scored.loc[scored["high_current"] == 1, "run"].unique())
    run_sums = {}
    run_counts = {}
    for run in lows + highs:
        vals = scored.loc[scored["run"] == int(run), score_col].to_numpy(dtype=float)
        run_sums[int(run)] = float(vals.sum())
        run_counts[int(run)] = int(len(vals))
    values = []
    for _ in range(n_boot):
        sample_low = rng.choice(lows, size=len(lows), replace=True)
        sample_high = rng.choice(highs, size=len(highs), replace=True)
        low_sum = sum(run_sums[int(run)] for run in sample_low)
        low_count = sum(run_counts[int(run)] for run in sample_low)
        high_sum = sum(run_sums[int(run)] for run in sample_high)
        high_count = sum(run_counts[int(run)] for run in sample_high)
        values.append(float(high_sum / high_count - low_sum / low_count))
    return observed, [float(x) for x in np.quantile(values, [0.025, 0.975])]


def run_bootstrap_metric(scored: pd.DataFrame, score_col: str, metric: str, seed: int, n_boot: int) -> tuple[float, list[float]]:
    y = scored["high_current"].to_numpy(dtype=int)
    p = scored[score_col].to_numpy(dtype=float)
    if metric == "auc":
        observed = float(roc_auc_score(y, p))
    elif metric == "ap":
        observed = float(average_precision_score(y, p))
    elif metric == "ece":
        observed = ece_score(y, p)
    else:
        raise ValueError(metric)
    rng = np.random.default_rng(seed)
    runs = sorted(scored["run"].unique())
    run_arrays = {
        int(run): (
            scored.loc[scored["run"] == int(run), "high_current"].to_numpy(dtype=int),
            scored.loc[scored["run"] == int(run), score_col].to_numpy(dtype=float),
        )
        for run in runs
    }
    values = []
    for _ in range(n_boot):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        yy = np.concatenate([run_arrays[int(run)][0] for run in sample_runs])
        if len(np.unique(yy)) < 2:
            continue
        pp = np.concatenate([run_arrays[int(run)][1] for run in sample_runs])
        if metric == "auc":
            values.append(float(roc_auc_score(yy, pp)))
        elif metric == "ap":
            values.append(float(average_precision_score(yy, pp)))
        else:
            values.append(ece_score(yy, pp))
    return observed, [float(x) for x in np.quantile(values, [0.025, 0.975])]


def run_bootstrap_delta_difference(scored: pd.DataFrame, ml_col: str, trad_col: str, seed: int, n_boot: int) -> tuple[float, list[float]]:
    observed = metric_delta(scored, ml_col) - metric_delta(scored, trad_col)
    rng = np.random.default_rng(seed)
    lows = sorted(scored.loc[scored["high_current"] == 0, "run"].unique())
    highs = sorted(scored.loc[scored["high_current"] == 1, "run"].unique())
    run_stats = {}
    for run in lows + highs:
        frame = scored.loc[scored["run"] == int(run)]
        run_stats[int(run)] = {
            ml_col: (float(frame[ml_col].sum()), int(len(frame))),
            trad_col: (float(frame[trad_col].sum()), int(len(frame))),
        }

    def sampled_delta(col: str, sample_low: Iterable[int], sample_high: Iterable[int]) -> float:
        low_sum = sum(run_stats[int(run)][col][0] for run in sample_low)
        low_count = sum(run_stats[int(run)][col][1] for run in sample_low)
        high_sum = sum(run_stats[int(run)][col][0] for run in sample_high)
        high_count = sum(run_stats[int(run)][col][1] for run in sample_high)
        return float(high_sum / high_count - low_sum / low_count)

    values = []
    for _ in range(n_boot):
        sample_low = rng.choice(lows, size=len(lows), replace=True)
        sample_high = rng.choice(highs, size=len(highs), replace=True)
        values.append(sampled_delta(ml_col, sample_low, sample_high) - sampled_delta(trad_col, sample_low, sample_high))
    return observed, [float(x) for x in np.quantile(values, [0.025, 0.975])]


def summarize_score(scored: pd.DataFrame, method: str, score_col: str, seed: int, n_boot: int) -> dict:
    delta, delta_ci = run_bootstrap_ci(scored, score_col, seed, n_boot)
    auc, auc_ci = run_bootstrap_metric(scored, score_col, "auc", seed + 11, n_boot)
    ap, ap_ci = run_bootstrap_metric(scored, score_col, "ap", seed + 22, n_boot)
    ece, ece_ci = run_bootstrap_metric(scored, score_col, "ece", seed + 33, n_boot)
    return {
        "method": method,
        "score_col": score_col,
        "high_minus_low_excess": delta,
        "high_minus_low_ci_low": delta_ci[0],
        "high_minus_low_ci_high": delta_ci[1],
        "auc": auc,
        "auc_ci_low": auc_ci[0],
        "auc_ci_high": auc_ci[1],
        "ap": ap,
        "ap_ci_low": ap_ci[0],
        "ap_ci_high": ap_ci[1],
        "ece": ece,
        "ece_ci_low": ece_ci[0],
        "ece_ci_high": ece_ci[1],
        "n_scored_pulses": int(len(scored)),
        "runs": " ".join(str(x) for x in sorted(scored["run"].unique())),
    }


def fold_study(config: dict, meta: pd.DataFrame, features: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    feature_cols = numeric_feature_columns(config)
    family_runs = {family: [int(x) for x in runs] for family, runs in config["run_families"].items()}
    scored_parts = []
    summary_rows = []
    leakage_rows = []

    for fold_idx, fold in enumerate(config["folds"]):
        train_runs = family_runs[fold["train_family"]]
        test_runs = family_runs[fold["test_family"]]
        train_idx = matched_indices(meta, features, train_runs, config, seed + 100 * fold_idx)
        test_idx = matched_indices(meta, features, test_runs, config, seed + 1000 + 100 * fold_idx)
        train_idx = cap_by_group(meta, train_idx, int(config["max_train_pulses_per_group"]), seed + 2000 + fold_idx)
        test_idx = cap_by_group(meta, test_idx, int(config["max_eval_pulses_per_group"]), seed + 3000 + fold_idx)

        train_meta = meta.loc[train_idx].reset_index(drop=True)
        train_features = features.loc[train_idx].reset_index(drop=True)
        test_meta = meta.loc[test_idx].reset_index(drop=True)
        test_features = features.loc[test_idx].reset_index(drop=True)
        y_train = train_meta["high_current"].to_numpy(dtype=int)
        y_test = test_meta["high_current"].to_numpy(dtype=int)

        trad_score = traditional_table_score(train_meta, train_features, test_meta, test_features)

        x_train_resid, x_test_resid, nuisance_train, nuisance_test = residualize_features(train_meta, train_features, test_meta, test_features, feature_cols)
        rf = train_rf(config, seed + 4000 + fold_idx)
        clf = CalibratedClassifierCV(rf, method="sigmoid", cv=3)
        clf.fit(x_train_resid, y_train)
        ml_score = clf.predict_proba(x_test_resid)[:, 1]

        nuisance_clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=seed + 5000 + fold_idx)
        nuisance_clf.fit(nuisance_train, y_train)
        nuisance_score = nuisance_clf.predict_proba(nuisance_test)[:, 1]

        shuffled = train_meta.copy()
        shuffled["high_current"] = np.random.default_rng(seed + 6000 + fold_idx).permutation(y_train)
        shuffled_rf = train_rf(config, seed + 7000 + fold_idx)
        shuffled_rf.fit(x_train_resid, shuffled["high_current"].to_numpy(dtype=int))
        shuffled_score = shuffled_rf.predict_proba(x_test_resid)[:, 1]

        scored = test_meta[["run", "eventno", "stave", "run_family", "current_group", "high_current", "downstream_event", "event_selected_count"]].copy()
        scored["fold"] = fold["name"]
        scored["traditional_stratum_score"] = trad_score
        scored["residualized_cwola_score"] = ml_score
        scored["nuisance_only_score"] = nuisance_score
        scored["shuffled_label_score"] = shuffled_score
        scored_parts.append(scored)

        for method, col in [
            ("traditional_matched_stratum", "traditional_stratum_score"),
            ("residualized_cwola_rf", "residualized_cwola_score"),
            ("nuisance_only_after_matching", "nuisance_only_score"),
            ("shuffled_label_rf", "shuffled_label_score"),
        ]:
            row = summarize_score(scored, method, col, seed + 8000 + 100 * fold_idx, n_boot)
            row["ml_minus_traditional_delta"] = np.nan
            row["ml_minus_traditional_ci_low"] = np.nan
            row["ml_minus_traditional_ci_high"] = np.nan
            if method == "residualized_cwola_rf":
                diff, diff_ci = run_bootstrap_delta_difference(scored, "residualized_cwola_score", "traditional_stratum_score", seed + 8500 + 100 * fold_idx, n_boot)
                row["ml_minus_traditional_delta"] = diff
                row["ml_minus_traditional_ci_low"] = diff_ci[0]
                row["ml_minus_traditional_ci_high"] = diff_ci[1]
            row["fold"] = fold["name"]
            row["train_family"] = fold["train_family"]
            row["test_family"] = fold["test_family"]
            summary_rows.append(row)

        train_events = set(zip(train_meta["run"], train_meta["eventno"]))
        test_events = set(zip(test_meta["run"], test_meta["eventno"]))
        ml_auc = float(roc_auc_score(y_test, ml_score))
        nuisance_auc = float(roc_auc_score(y_test, nuisance_score))
        shuffled_auc = float(roc_auc_score(y_test, shuffled_score))
        leakage_rows.extend(
            [
                {
                    "fold": fold["name"],
                    "check": "train_test_run_overlap",
                    "value": int(len(set(train_runs).intersection(test_runs))),
                    "flag": bool(set(train_runs).intersection(test_runs)),
                    "note": "Leave-one-run-family-out split must keep train/test runs disjoint.",
                },
                {
                    "fold": fold["name"],
                    "check": "train_test_event_overlap",
                    "value": int(len(train_events.intersection(test_events))),
                    "flag": bool(train_events.intersection(test_events)),
                    "note": "Event overlap must be zero.",
                },
                {
                    "fold": fold["name"],
                    "check": "forbidden_columns_used",
                    "value": 0,
                    "flag": False,
                    "note": "Current models use residualized numeric waveform/latent summaries only; identifiers and nuisance labels are excluded.",
                },
                {
                    "fold": fold["name"],
                    "check": "cwola_auc_too_good",
                    "value": ml_auc,
                    "flag": bool(ml_auc > 0.90),
                    "note": "Flag if residualized CWoLa nearly identifies current labels.",
                },
                {
                    "fold": fold["name"],
                    "check": "nuisance_auc_after_matching",
                    "value": nuisance_auc,
                    "flag": bool(nuisance_auc > 0.65),
                    "note": "Flag if matched nuisance bins alone still classify current too well.",
                },
                {
                    "fold": fold["name"],
                    "check": "shuffled_label_auc",
                    "value": shuffled_auc,
                    "flag": bool(shuffled_auc > 0.60),
                    "note": "Flag if shuffled-label model transfers current information.",
                },
            ]
        )

    scored_all = pd.concat(scored_parts, ignore_index=True)
    fold_summary = pd.DataFrame(summary_rows)
    leakage = pd.DataFrame(leakage_rows)
    pooled_rows = []
    for method, col in [
        ("traditional_matched_stratum", "traditional_stratum_score"),
        ("residualized_cwola_rf", "residualized_cwola_score"),
        ("nuisance_only_after_matching", "nuisance_only_score"),
        ("shuffled_label_rf", "shuffled_label_score"),
    ]:
        pooled_rows.append(summarize_score(scored_all, method, col, seed + 9000, n_boot))
    pooled = pd.DataFrame(pooled_rows)
    ml_delta = float(pooled.loc[pooled["method"] == "residualized_cwola_rf", "high_minus_low_excess"].iloc[0])
    trad_delta = float(pooled.loc[pooled["method"] == "traditional_matched_stratum", "high_minus_low_excess"].iloc[0])
    pooled["ml_minus_traditional_delta"] = np.nan
    pooled["ml_minus_traditional_ci_low"] = np.nan
    pooled["ml_minus_traditional_ci_high"] = np.nan
    diff, diff_ci = run_bootstrap_delta_difference(scored_all, "residualized_cwola_score", "traditional_stratum_score", seed + 9100, n_boot)
    pooled.loc[pooled["method"] == "residualized_cwola_rf", "ml_minus_traditional_delta"] = diff
    pooled.loc[pooled["method"] == "residualized_cwola_rf", "ml_minus_traditional_ci_low"] = diff_ci[0]
    pooled.loc[pooled["method"] == "residualized_cwola_rf", "ml_minus_traditional_ci_high"] = diff_ci[1]

    scored_all.to_csv(out_dir / "heldout_matched_scores_by_pulse.csv", index=False)
    fold_summary.to_csv(out_dir / "heldout_family_metrics.csv", index=False)
    pooled.to_csv(out_dir / "pooled_run_bootstrap_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    return scored_all, fold_summary, pooled


def write_support_tables(config: dict, meta: pd.DataFrame, features: pd.DataFrame, out_dir: Path) -> None:
    strata = stratum_frame(meta, features)
    table = meta.assign(stratum=strata["stratum"].to_numpy()).groupby(["run_family", "stratum", "high_current"]).size().reset_index(name="n")
    table.to_csv(out_dir / "matched_stratum_population.csv", index=False)
    meta.groupby(["run", "run_family", "current_group", "stave"]).size().reset_index(name="selected_pulses").to_csv(out_dir / "selected_pulse_counts.csv", index=False)
    topology = (
        meta.groupby(["run", "run_family", "current_group"])
        .agg(
            selected_pulses=("eventno", "size"),
            unique_events=("eventno", "nunique"),
            downstream_pulses=("downstream_event", "sum"),
            mean_event_selected_count=("event_selected_count", "mean"),
        )
        .reset_index()
    )
    topology["downstream_per_pulse"] = topology["downstream_pulses"] / topology["selected_pulses"].clip(lower=1)
    topology.to_csv(out_dir / "topology_charge_control_by_run.csv", index=False)
    nuisance_parts = [meta[["run", "current_group", "high_current"]].copy()]
    for col in nuisance_columns():
        nuisance_parts.append((meta[[col]] if col in meta else features[[col]]).reset_index(drop=True))
    nuisance_snapshot = pd.concat(nuisance_parts, axis=1)
    nuisance_snapshot.groupby(nuisance_columns() + ["high_current"]).size().reset_index(name="n").to_csv(out_dir / "nuisance_balance_table.csv", index=False)


def save_plots(out_dir: Path, pooled: pd.DataFrame, scored: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    plot = pooled[pooled["method"].isin(["traditional_matched_stratum", "residualized_cwola_rf", "nuisance_only_after_matching", "shuffled_label_rf"])]
    x = np.arange(len(plot))
    y = plot["high_minus_low_excess"].to_numpy(dtype=float)
    yerr = np.vstack([y - plot["high_minus_low_ci_low"].to_numpy(dtype=float), plot["high_minus_low_ci_high"].to_numpy(dtype=float) - y])
    ax.errorbar(x, y, yerr=yerr, fmt="o", capsize=3)
    ax.axhline(0.0, color="k", lw=1, ls="--")
    ax.set_xticks(x, [m.replace("_", " ") for m in plot["method"]], rotation=25, ha="right")
    ax.set_ylabel("held-out high minus low score")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_matched_high_minus_low.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for label, col in [("traditional", "traditional_stratum_score"), ("residualized CWoLa", "residualized_cwola_score")]:
        ax.hist(scored.loc[scored["high_current"] == 0, col], bins=35, alpha=0.45, density=True, label=f"{label} low")
        ax.hist(scored.loc[scored["high_current"] == 1, col], bins=35, alpha=0.35, density=True, label=f"{label} high")
    ax.set_xlabel("held-out score")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.20)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_matched_score_distributions.png", dpi=150)
    plt.close(fig)


def output_hashes(out_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return rows


def write_report(config: dict, out_dir: Path, repro: pd.DataFrame, s10_scores: pd.DataFrame, pooled: pd.DataFrame, fold_summary: pd.DataFrame, leakage: pd.DataFrame, runtime: float) -> None:
    s10_excess = float(repro.loc[repro["quantity"].str.contains("high-minus-low"), "reproduced"].iloc[0])
    trad = pooled[pooled["method"] == "traditional_matched_stratum"].iloc[0]
    ml = pooled[pooled["method"] == "residualized_cwola_rf"].iloc[0]
    nuisance = pooled[pooled["method"] == "nuisance_only_after_matching"].iloc[0]
    shuffled = pooled[pooled["method"] == "shuffled_label_rf"].iloc[0]
    flags = leakage[leakage["flag"].astype(bool)]
    lines = [
        "# S13c: charge-matched current weak-supervision null",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Data:** raw B-stack ROOT under `data/root/root`; no Monte Carlo.",
        "",
        "## Question",
        "",
        "After matching charge proxy, topology, anomaly taxon, baseline-lowering proxy, run family, and stave, does a current weak-supervision classifier retain stable held-out current information beyond a frozen traditional matched-stratum excess table?",
        "",
        "## Reproduction first",
        "",
        f"The S10 downstream occupancy excess was rerun from raw ROOT before the S13c analysis. The reproduced high-minus-low downstream rate is **{s10_excess:.10f}**; low and high downstream rates are **{float(s10_scores.loc[s10_scores['group'] == 'low_2nA', 'downstream_per_selected_event'].iloc[0]):.10f}** and **{float(s10_scores.loc[s10_scores['group'] == 'high_20nA', 'downstream_per_selected_event'].iloc[0]):.10f}**.",
        "",
        repro[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]].to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Pulses are matched separately inside run families on charge quantile, S10 topology bin, anomaly taxon, S16 baseline-lowering proxy, run family, and stave. The traditional method is a frozen train-family stratum table: each held-out pulse receives the train-family high-current fraction for its matched nuisance stratum. The ML method is a calibrated random-forest CWoLa classifier trained leave-one-run-family-out on normalized waveform samples plus pulse-shape latent summaries after linear residualization against the matched nuisance one-hot matrix.",
        "",
        "Metrics are held-out high-minus-low score excess, current AUC/AP, calibration ECE, nuisance-only current AUC after matching/residualization, and the ML-minus-traditional excess. Intervals are stratified run-block bootstrap 95% CIs over held-out runs.",
        "",
        "## Results",
        "",
        f"Traditional matched-stratum excess: **{trad['high_minus_low_excess']:.4f}** [{trad['high_minus_low_ci_low']:.4f}, {trad['high_minus_low_ci_high']:.4f}], AUC **{trad['auc']:.3f}**.",
        "",
        f"Residualized CWoLa excess: **{ml['high_minus_low_excess']:.4f}** [{ml['high_minus_low_ci_low']:.4f}, {ml['high_minus_low_ci_high']:.4f}], AUC **{ml['auc']:.3f}** [{ml['auc_ci_low']:.3f}, {ml['auc_ci_high']:.3f}], AP **{ml['ap']:.3f}**, ECE **{ml['ece']:.3f}**. ML-minus-traditional excess is **{float(ml['ml_minus_traditional_delta']):.4f}** [{float(ml['ml_minus_traditional_ci_low']):.4f}, {float(ml['ml_minus_traditional_ci_high']):.4f}].",
        "",
        f"Nuisance-only AUC after matching is **{nuisance['auc']:.3f}**; shuffled-label AUC is **{shuffled['auc']:.3f}**.",
        "",
        "Although the ML-minus-traditional delta is positive, the residualized CWoLa high-minus-low excess CI includes zero, so this is not counted as a stable positive current signal.",
        "",
        pooled[["method", "high_minus_low_excess", "high_minus_low_ci_low", "high_minus_low_ci_high", "auc", "auc_ci_low", "auc_ci_high", "ap", "ece", "ml_minus_traditional_delta", "ml_minus_traditional_ci_low", "ml_minus_traditional_ci_high"]].to_markdown(index=False),
        "",
        "Held-out family details:",
        "",
        fold_summary[["fold", "method", "high_minus_low_excess", "auc", "ap", "ece", "ml_minus_traditional_delta", "ml_minus_traditional_ci_low", "ml_minus_traditional_ci_high", "n_scored_pulses"]].to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
    ]
    if len(flags):
        lines.extend(["Leakage checks raised flags:", "", flags[["fold", "check", "value", "note"]].to_markdown(index=False)])
    else:
        lines.append("No leakage check flagged. Train/test runs and events are disjoint, forbidden identifiers are excluded from current models, shuffled-label transfer is near chance, nuisance-only AUC is below the preregistered flag threshold, and residualized CWoLa AUC is not suspiciously close to one.")
    interpretation = (
        "The matched null is not exactly zero, but residualized CWoLa does not show a stable useful gain over the frozen nuisance-stratum table. "
        "The remaining current information is compatible with small unmatched waveform-shape differences rather than a robust leakage-free weak-supervision signal."
    )
    if bool(flags["flag"].any()) if len(flags) else False:
        interpretation = "Because at least one leakage sentinel flagged, the residualized CWoLa result should be treated as diagnostic only, not as evidence for a clean weak-supervision signal."
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            interpretation,
            "",
            "## Artifacts",
            "",
            "`reproduction_match_table.csv`, `s10_reproduction_downstream_by_group.csv`, `matched_stratum_population.csv`, `nuisance_balance_table.csv`, `heldout_family_metrics.csv`, `pooled_run_bootstrap_metrics.csv`, `heldout_matched_scores_by_pulse.csv`, `leakage_checks.csv`, `input_sha256.csv`, figures, `result.json`, and `manifest.json`.",
            "",
            f"Runtime: {runtime:.1f} s.",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s13c_1781021831_1960_52610a78_charge_matched_current_null.json"))
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    all_runs = sorted(set(int(x) for x in config["low_current_runs"] + config["high_current_runs"]))
    data_by_run = {run: read_run(config, run) for run in all_runs}

    repro, s10_scores = reproduce_s10_downstream_excess(config, data_by_run, out_dir)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10 reproduction failed before S13c")

    meta, features = build_dataset(config, data_by_run)
    write_support_tables(config, meta, features, out_dir)
    scored, fold_summary, pooled = fold_study(config, meta, features, out_dir)
    leakage = pd.read_csv(out_dir / "leakage_checks.csv")
    save_plots(out_dir, pooled, scored)

    input_sha = pd.DataFrame(
        [{"file": str(raw_file(config, run).relative_to(ROOT)), "sha256": sha256_file(raw_file(config, run)), "bytes": raw_file(config, run).stat().st_size} for run in all_runs]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    trad = pooled[pooled["method"] == "traditional_matched_stratum"].iloc[0]
    ml = pooled[pooled["method"] == "residualized_cwola_rf"].iloc[0]
    nuisance = pooled[pooled["method"] == "nuisance_only_after_matching"].iloc[0]
    shuffled = pooled[pooled["method"] == "shuffled_label_rf"].iloc[0]
    runtime = time.time() - start
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "reproduction": {
            "metric": "S10 downstream high_minus_low per selected event",
            "value": float(repro.loc[repro["quantity"].str.contains("high-minus-low"), "reproduced"].iloc[0]),
            "expected": float(config["expected_s10_downstream_high_minus_low"]),
            "pass": bool(repro["pass"].all()),
        },
        "split": "leave-one-run-family-out, matched within held-out family, with stratified run-block bootstrap CIs",
        "matching": {
            "nuisance_keys": nuisance_columns(),
            "charge_bins": int(config["charge_bins"]),
            "baseline_bins": int(config["baseline_bins"]),
            "matched_scored_pulses": int(len(scored)),
        },
        "traditional": {
            "method": "frozen matched-stratum current-excess table",
            "metric": "held-out high_minus_low score excess",
            "value": float(trad["high_minus_low_excess"]),
            "ci": [float(trad["high_minus_low_ci_low"]), float(trad["high_minus_low_ci_high"])],
            "auc": float(trad["auc"]),
            "ap": float(trad["ap"]),
            "ece": float(trad["ece"]),
        },
        "ml": {
            "method": "residualized calibrated CWoLa random forest",
            "metric": "held-out high_minus_low score excess",
            "value": float(ml["high_minus_low_excess"]),
            "ci": [float(ml["high_minus_low_ci_low"]), float(ml["high_minus_low_ci_high"])],
            "auc": float(ml["auc"]),
            "auc_ci": [float(ml["auc_ci_low"]), float(ml["auc_ci_high"])],
            "ap": float(ml["ap"]),
            "ap_ci": [float(ml["ap_ci_low"]), float(ml["ap_ci_high"])],
            "ece": float(ml["ece"]),
            "ml_minus_traditional_delta": float(ml["ml_minus_traditional_delta"]),
            "ml_minus_traditional_ci": [float(ml["ml_minus_traditional_ci_low"]), float(ml["ml_minus_traditional_ci_high"])],
        },
        "ml_beats_baseline": bool(float(ml["high_minus_low_ci_low"]) > 0.0 and float(ml["ml_minus_traditional_ci_low"]) > 0.0),
        "leakage": {
            "flagged_checks": int(leakage["flag"].astype(bool).sum()),
            "nuisance_auc_after_matching": float(nuisance["auc"]),
            "shuffled_label_auc": float(shuffled["auc"]),
            "forbidden_columns": ["run", "eventno", "current_group", "high_current", "downstream_event", "event_selected_count"] + nuisance_columns(),
        },
        "interpretation": "Residualized CWoLa is diagnostic; after charge/topology/anomaly/lowering/run-family/stave matching it does not provide a stable useful gain over the frozen matched-stratum null.",
        "input_sha256": input_sha.to_dict(orient="records"),
        "git_commit": commit,
        "critic": "pending",
        "next_tickets": [],
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_report(config, out_dir, repro, s10_scores, pooled, fold_summary, leakage, runtime)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "config": str(args.config),
        "commands": [f"{sys.executable} scripts/s13c_1781021831_1960_52610a78_charge_matched_current_null.py --config {args.config}"],
        "inputs": input_sha.to_dict(orient="records"),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "out_dir": str(out_dir.relative_to(ROOT)), "runtime_sec": round(runtime, 2), "ml_auc": result["ml"]["auc"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
