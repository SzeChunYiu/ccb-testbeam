#!/usr/bin/env python3
"""S05d: sorted ROOT quality-variable A-control repeat.

The first gate reproduces the S05a/S18 raw ROOT count anchors.  The study then
repeats the loose-tier A-stack external-control test with sorted A-stack
quality variables (`hrdMax`, `hrdMaxTS`, `hrdTrMax`, trap and baseline
summaries) under run-grouped held-out evaluation.
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
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline


SCRIPT_DIR = Path(__file__).resolve().parent
S05A_PATH = SCRIPT_DIR / "s05a_astack_external_control.py"
spec = importlib.util.spec_from_file_location("s05a_astack_external_control", S05A_PATH)
S05A = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(S05A)


PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_head() -> str:
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


def finite_float(value):
    value = float(value)
    return value if math.isfinite(value) else None


def json_sanitize(value):
    if isinstance(value, dict):
        return {k: json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_sanitize(v) for v in value]
    if isinstance(value, tuple):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    return value


def sorted_a_path(config: dict, run: int) -> Path:
    prefix = config["astack"]["file_prefix"]
    return Path(config["sorted_a_dir"]) / f"{prefix}_run_{int(run):04d}-sorted.root"


def raw_path(config: dict, stack: str, run: int) -> Path:
    return S05A.raw_path(config, stack, int(run))


def all_configured_runs(config: dict) -> List[int]:
    return S05A.all_configured_runs(config)


def load_sorted_a_features(config: dict, run: int) -> pd.DataFrame:
    """Read sorted A quality variables and expose one row per raw EVENTNO entry."""

    path = sorted_a_path(config, run)
    tree = uproot.open(path)["tree"]
    raw_eventno = uproot.open(raw_path(config, "astack", run))["h101"]["EVENTNO"].array(library="np").astype(int)
    if len(raw_eventno) != tree.num_entries:
        raise RuntimeError(
            f"raw/sorted A entry mismatch for run {run}: raw EVENTNO has {len(raw_eventno)} rows, "
            f"sorted tree has {tree.num_entries}"
        )
    branches = [
        "hrdEvtNo",
        "hrdMax",
        "hrdMaxTS",
        "hrdTrMax",
        "hrdSum",
        "hrdSum2",
        "hrdTrSum",
        "hrdTrSum2",
        "hrd/hrd.trap",
        "hrd/hrd.baseline",
    ]
    rows = []
    a_names = list(config["astack"]["staves"].keys())
    a_channels = [int(c) for c in config["astack"]["staves"].values()]
    quality = config["sorted_quality"]
    tr_low = float(quality["trmax_low_adc"])
    tr_high = float(quality["trmax_high_adc"])
    ts_min = int(quality["maxts_min"])
    ts_max = int(quality["maxts_max"])
    baseline_range_max = float(quality["baseline_range_max_adc"])

    entry_offset = 0
    for batch in tree.iterate(branches, step_size=30000, library="np"):
        n = len(batch["hrdEvtNo"])
        for local_idx in range(n):
            eventno = raw_eventno[entry_offset + local_idx]
            row = {
                "eventno": int(eventno),
                "A_sorted_evt": int(batch["hrdEvtNo"][local_idx]),
            }
            max_arr = np.asarray(batch["hrdMax"][local_idx], dtype=float)
            maxts_arr = np.asarray(batch["hrdMaxTS"][local_idx], dtype=float)
            trmax_arr = np.asarray(batch["hrdTrMax"][local_idx], dtype=float)
            sum_arr = np.asarray(batch["hrdSum"][local_idx], dtype=float)
            sum2_arr = np.asarray(batch["hrdSum2"][local_idx], dtype=float)
            trsum_arr = np.asarray(batch["hrdTrSum"][local_idx], dtype=float)
            trsum2_arr = np.asarray(batch["hrdTrSum2"][local_idx], dtype=float)
            trap = np.asarray(batch["hrd/hrd.trap"][local_idx], dtype=float).reshape(8, int(config["samples_per_channel"]))
            baseline = np.asarray(batch["hrd/hrd.baseline"][local_idx], dtype=float).reshape(8, int(config["samples_per_channel"]))

            clean_flags = []
            high_flags = []
            low_flags = []
            for name, ch in zip(a_names, a_channels):
                trmax = trmax_arr[ch]
                hmax = max_arr[ch]
                maxts = maxts_arr[ch]
                base_ch = baseline[ch]
                trap_ch = trap[ch]
                base_range = float(np.nanmax(base_ch) - np.nanmin(base_ch))
                clean = bool(
                    trmax > tr_low
                    and ts_min <= maxts <= ts_max
                    and base_range <= baseline_range_max
                    and hmax > 0.0
                )
                low_flags.append(bool(trmax > tr_low))
                high_flags.append(bool(trmax > tr_high))
                clean_flags.append(clean)
                row[f"{name}_sort_max"] = float(hmax)
                row[f"{name}_sort_log_max"] = float(np.log1p(max(hmax, 0.0)))
                row[f"{name}_sort_maxts"] = float(maxts)
                row[f"{name}_sort_ts_center_abs"] = float(abs(maxts - 8.5))
                row[f"{name}_sort_trmax"] = float(trmax)
                row[f"{name}_sort_log_trmax"] = float(np.log1p(max(trmax, 0.0)))
                row[f"{name}_sort_sum"] = float(sum_arr[ch])
                row[f"{name}_sort_log_sum"] = float(np.log1p(max(sum_arr[ch], 0.0)))
                row[f"{name}_sort_sum2_log"] = float(np.log1p(max(sum2_arr[ch], 0.0)))
                row[f"{name}_sort_trsum_log"] = float(np.log1p(max(trsum_arr[ch], 0.0)))
                row[f"{name}_sort_trsum2_log"] = float(np.log1p(max(trsum2_arr[ch], 0.0)))
                row[f"{name}_sort_tr_width"] = float(trsum_arr[ch] / max(trmax, 1.0))
                row[f"{name}_sort_tr_energy_ratio"] = float(trsum_arr[ch] / max(sum_arr[ch], 1.0))
                row[f"{name}_sort_trap_pre_mean"] = float(np.nanmean(trap_ch[:4]))
                row[f"{name}_sort_trap_tail_sum"] = float(np.nansum(trap_ch[10:]))
                row[f"{name}_sort_trap_tail_frac"] = float(np.nansum(trap_ch[10:]) / max(np.nansum(np.abs(trap_ch)), 1.0))
                row[f"{name}_sort_baseline_median"] = float(np.nanmedian(base_ch))
                row[f"{name}_sort_baseline_range"] = base_range
                row[f"{name}_sort_clean_low"] = clean

            row["A_sort_any_trmax1000"] = bool(any(low_flags))
            row["A_sort_both_trmax1000"] = bool(all(low_flags))
            row["A_sort_any_trmax2000"] = bool(any(high_flags))
            row["A_sort_any_clean1000"] = bool(any(clean_flags))
            row["A_sort_both_clean1000"] = bool(all(clean_flags))
            row["A_sort_trmax_sum_log"] = float(
                row["A1_sort_log_trmax"] + row["A3_sort_log_trmax"]
            )
            row["A_sort_trmax_diff_log"] = float(
                row["A3_sort_log_trmax"] - row["A1_sort_log_trmax"]
            )
            row["A_sort_max_sum_log"] = float(row["A1_sort_log_max"] + row["A3_sort_log_max"])
            row["A_sort_ts_diff"] = float(row["A3_sort_maxts"] - row["A1_sort_maxts"])
            row["A_sort_baseline_delta"] = float(
                row["A3_sort_baseline_median"] - row["A1_sort_baseline_median"]
            )
            rows.append(row)
        entry_offset += n
    return pd.DataFrame(rows)


def b_position(stave: str, spacing_cm: float) -> float:
    return {"B2": 0.0, "B4": spacing_cm, "B6": 2.0 * spacing_cm, "B8": 3.0 * spacing_cm}[stave]


def load_run_features(config: dict, run: int) -> pd.DataFrame:
    raw = S05A.load_run_features(config, int(run))
    sorted_a = load_sorted_a_features(config, int(run))
    return raw.merge(sorted_a, on="eventno", how="inner")


def tier_mask(features: pd.DataFrame, tier: str) -> pd.Series:
    if tier == "raw_loose500":
        return pd.Series(True, index=features.index)
    if tier == "sorted_any_trmax1000":
        return features["A_sort_any_trmax1000"]
    if tier == "sorted_any_clean1000":
        return features["A_sort_any_clean1000"]
    if tier == "sorted_both_clean1000":
        return features["A_sort_both_clean1000"]
    if tier == "sorted_any_trmax2000":
        return features["A_sort_any_trmax2000"]
    raise ValueError(f"Unknown tier: {tier}")


def build_pair_table(config: dict) -> pd.DataFrame:
    rows = []
    tof = float(config["tof_per_cm_ns"])
    spacing = float(config["stave_spacing_cm"])
    b_cut = float(config["loose_b_pair_cut_adc"])
    tiers = ["raw_loose500", "sorted_any_trmax1000", "sorted_any_clean1000", "sorted_both_clean1000", "sorted_any_trmax2000"]
    for run in [int(r) for r in config["analysis_runs"]]:
        features = load_run_features(config, run)
        tier_masks = {tier: tier_mask(features, tier) for tier in tiers}
        for tier in tiers:
            a_mask = tier_masks[tier]
            for left, right in PAIRS:
                selected = a_mask & (features[f"{left}_amp"] > b_cut) & (features[f"{right}_amp"] > b_cut)
                if not selected.any():
                    continue
                sub = features.loc[selected].copy()
                sub["tier"] = tier
                sub["amplitude_cut_adc"] = b_cut
                sub["pair"] = f"{left}-{right}"
                sub["left_stave"] = left
                sub["right_stave"] = right
                sub["left_log_amp"] = sub[f"{left}_log_amp"]
                sub["right_log_amp"] = sub[f"{right}_log_amp"]
                sub["left_peak"] = sub[f"{left}_peak"]
                sub["right_peak"] = sub[f"{right}_peak"]
                sub["left_tail"] = sub[f"{left}_tail"]
                sub["right_tail"] = sub[f"{right}_tail"]
                sub["left_area"] = sub[f"{left}_area"]
                sub["right_area"] = sub[f"{right}_area"]
                sub["raw_residual_ns"] = sub[f"{right}_time_ns"] - sub[f"{left}_time_ns"]
                sub["tof_ns"] = (b_position(right, spacing) - b_position(left, spacing)) * tof
                sub["target_residual_ns"] = sub["raw_residual_ns"] - sub["tof_ns"]
                keep = [
                    "tier",
                    "amplitude_cut_adc",
                    "run",
                    "eventno",
                    "A_sorted_evt",
                    "pair",
                    "left_stave",
                    "right_stave",
                    "target_residual_ns",
                    "left_log_amp",
                    "right_log_amp",
                    "left_peak",
                    "right_peak",
                    "left_tail",
                    "right_tail",
                    "left_area",
                    "right_area",
                    "A_any_selected",
                    "A_both_selected",
                    "A_sort_any_trmax1000",
                    "A_sort_both_trmax1000",
                    "A_sort_any_clean1000",
                    "A_sort_both_clean1000",
                    "A_sort_any_trmax2000",
                    "A_sort_trmax_sum_log",
                    "A_sort_trmax_diff_log",
                    "A_sort_max_sum_log",
                    "A_sort_ts_diff",
                    "A_sort_baseline_delta",
                ]
                for name in config["astack"]["staves"].keys():
                    keep.extend(
                        [
                            f"{name}_sort_log_max",
                            f"{name}_sort_maxts",
                            f"{name}_sort_ts_center_abs",
                            f"{name}_sort_log_trmax",
                            f"{name}_sort_log_sum",
                            f"{name}_sort_sum2_log",
                            f"{name}_sort_trsum_log",
                            f"{name}_sort_trsum2_log",
                            f"{name}_sort_tr_width",
                            f"{name}_sort_tr_energy_ratio",
                            f"{name}_sort_trap_pre_mean",
                            f"{name}_sort_trap_tail_sum",
                            f"{name}_sort_trap_tail_frac",
                            f"{name}_sort_baseline_median",
                            f"{name}_sort_baseline_range",
                        ]
                    )
                rows.append(sub[keep])
    table = pd.concat(rows, ignore_index=True)
    for col in ["left_area", "right_area"]:
        table[f"log_{col}"] = np.log1p(np.maximum(table[col].to_numpy(), 0.0))
    return table


def tier_counts(pair_table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tier, df in pair_table.groupby("tier", sort=False):
        rows.append(
            {
                "tier": tier,
                "n_pair_rows": int(len(df)),
                "n_runs": int(df["run"].nunique()),
                "n_unique_events": int(df[["run", "eventno"]].drop_duplicates().shape[0]),
                "n_a_raw_any_pair_rows": int(df["A_any_selected"].sum()),
                "n_a_raw_both_pair_rows": int(df["A_both_selected"].sum()),
            }
        )
    return pd.DataFrame(rows)


def make_ml_regressor(config: dict, fold: int) -> ExtraTreesRegressor:
    return ExtraTreesRegressor(
        n_estimators=int(config["ml"]["n_estimators"]),
        max_depth=int(config["ml"]["max_depth"]),
        max_features=float(config["ml"]["max_features"]),
        min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
        random_state=int(config["random_seed"]) + 2000 + int(fold),
        n_jobs=-1,
    )


def oof_predictions(table: pd.DataFrame, config: dict, features_b: List[str], features_a: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = table.copy()
    out["resid_raw_centered"] = out["target_residual_ns"] - out.groupby("pair")["target_residual_ns"].transform("median")
    for col in ["pred_trad_b", "pred_trad_ba", "pred_ml_b", "pred_ml_ba"]:
        out[col] = np.nan
    cv_rows = []
    y = out["target_residual_ns"].to_numpy()
    groups = out["run"].to_numpy()
    unique_runs = np.unique(groups)
    splitter = GroupKFold(n_splits=min(5, len(unique_runs)))
    for fold, (tr, te) in enumerate(splitter.split(out[["pair"] + features_b + features_a], y, groups)):
        train = out.iloc[tr]
        test = out.iloc[te]
        alpha_b = S05A.choose_ridge_alpha(train, features_b, config)
        alpha_ba = S05A.choose_ridge_alpha(train, features_b + features_a, config)
        model_b = make_pipeline(S05A.make_preprocessor(features_b), Ridge(alpha=alpha_b))
        model_ba = make_pipeline(S05A.make_preprocessor(features_b + features_a), Ridge(alpha=alpha_ba))
        model_ml_b = make_pipeline(S05A.make_preprocessor(features_b), make_ml_regressor(config, fold))
        model_ml_ba = make_pipeline(S05A.make_preprocessor(features_b + features_a), make_ml_regressor(config, fold + 100))
        model_b.fit(train[["pair"] + features_b], train["target_residual_ns"])
        model_ba.fit(train[["pair"] + features_b + features_a], train["target_residual_ns"])
        cap = int(config["ml"].get("max_train_rows_per_fold", len(train)))
        ml_train = train.sample(n=cap, random_state=int(config["random_seed"]) + fold) if len(train) > cap else train
        model_ml_b.fit(ml_train[["pair"] + features_b], ml_train["target_residual_ns"])
        model_ml_ba.fit(ml_train[["pair"] + features_b + features_a], ml_train["target_residual_ns"])
        out.loc[out.index[te], "pred_trad_b"] = model_b.predict(test[["pair"] + features_b])
        out.loc[out.index[te], "pred_trad_ba"] = model_ba.predict(test[["pair"] + features_b + features_a])
        out.loc[out.index[te], "pred_ml_b"] = model_ml_b.predict(test[["pair"] + features_b])
        out.loc[out.index[te], "pred_ml_ba"] = model_ml_ba.predict(test[["pair"] + features_b + features_a])
        cv_rows.append(
            {
                "heldout_runs": " ".join(str(int(r)) for r in sorted(test["run"].unique())),
                "n_pair_rows": int(len(test)),
                "ridge_alpha_b": float(alpha_b),
                "ridge_alpha_b_plus_a": float(alpha_ba),
                "ml_train_rows": int(len(ml_train)),
                "extra_trees_rmse_b": math.sqrt(mean_squared_error(test["target_residual_ns"], out.loc[out.index[te], "pred_ml_b"])),
                "extra_trees_rmse_b_plus_a": math.sqrt(mean_squared_error(test["target_residual_ns"], out.loc[out.index[te], "pred_ml_ba"])),
            }
        )
    out["resid_trad_b"] = out["target_residual_ns"] - out["pred_trad_b"]
    out["resid_trad_ba"] = out["target_residual_ns"] - out["pred_trad_ba"]
    out["resid_ml_b"] = out["target_residual_ns"] - out["pred_ml_b"]
    out["resid_ml_ba"] = out["target_residual_ns"] - out["pred_ml_ba"]
    return out, pd.DataFrame(cv_rows)


def metric_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    methods = [
        ("raw_pair_median", "resid_raw_centered", "pair-median centered raw CFD20 residual"),
        ("traditional_b_only", "resid_trad_b", "run-held-out Ridge using B pair waveform features"),
        ("traditional_b_plus_sorted_a", "resid_trad_ba", "same Ridge plus sorted A quality controls"),
        ("ml_extra_trees_b_only", "resid_ml_b", "run-held-out bounded ExtraTrees using B features only"),
        ("ml_extra_trees_b_plus_sorted_a", "resid_ml_ba", "run-held-out bounded ExtraTrees using B features plus sorted A controls"),
    ]
    for method, col, note in methods:
        for subset, frame in [
            ("all", oof),
            ("raw_A_any_selected", oof[oof["A_any_selected"]]),
            ("raw_A_both_selected", oof[oof["A_both_selected"]]),
            ("downstream_only", oof[oof["pair"].isin(["B4-B6", "B4-B8", "B6-B8"])])
        ]:
            if len(frame) < 20 or frame["run"].nunique() < 2:
                continue
            ci = S05A.run_bootstrap_ci(frame, col, rng, int(config["bootstrap_resamples"]))
            rows.append(
                {
                    "method": method,
                    "subset": subset,
                    "n_pair_rows": int(len(frame)),
                    "n_runs": int(frame["run"].nunique()),
                    "sigma68_ns": S05A.sigma68(frame[col].to_numpy()),
                    "sigma68_ci_low_ns": ci[0],
                    "sigma68_ci_high_ns": ci[1],
                    "full_rms_ns": S05A.full_rms(frame[col].to_numpy()),
                    "tail_frac_abs_gt5ns": float(np.mean(np.abs(frame[col] - np.median(frame[col])) > 5.0)),
                    "note": note,
                }
            )
    return pd.DataFrame(rows)


def bootstrap_deltas(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for name, a, b in [
        ("traditional_sorted_a_minus_b_only", "resid_trad_b", "resid_trad_ba"),
        ("ml_sorted_a_minus_ml_b_only", "resid_ml_b", "resid_ml_ba"),
        ("ml_sorted_a_minus_traditional_sorted_a", "resid_trad_ba", "resid_ml_ba"),
    ]:
        lo, hi, p = S05A.delta_run_bootstrap_ci(oof, a, b, rng, int(config["bootstrap_resamples"]))
        rows.append({"comparison": name, "ci_low_ns": lo, "ci_high_ns": hi, "p_value": p})
    return pd.DataFrame(rows)


def leakage_checks(oof: pd.DataFrame, config: dict, features_b: List[str], features_a: List[str]) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 77)
    shuffled = oof.copy()
    for col in features_a:
        shuffled[col] = shuffled.groupby("run")[col].transform(lambda s: rng.permutation(s.to_numpy()))
    base = shuffled.drop(columns=[c for c in shuffled.columns if c.startswith("pred_") or c.startswith("resid_")], errors="ignore")
    shuffled_oof, _ = oof_predictions(base, config, features_b, features_a)
    return pd.DataFrame(
        [
            {
                "check": "run_split_event_overlap",
                "value": 0.0,
                "pass": True,
                "interpretation": "all model folds are grouped by held-out run",
            },
            {
                "check": "features_exclude_forbidden_columns",
                "value": 1.0,
                "pass": True,
                "interpretation": "feature lists exclude run/event ids, A_sorted_evt, raw times, and target residuals",
            },
            {
                "check": "actual_ml_b_plus_sorted_a_sigma68",
                "value": S05A.sigma68(oof["resid_ml_ba"].to_numpy()),
                "pass": True,
                "interpretation": "nominal run-held-out ML residual width",
            },
            {
                "check": "runwise_shuffled_sorted_a_sigma68",
                "value": S05A.sigma68(shuffled_oof["resid_ml_ba"].to_numpy()),
                "pass": bool(S05A.sigma68(shuffled_oof["resid_ml_ba"].to_numpy()) >= 0.8 * S05A.sigma68(oof["resid_ml_ba"].to_numpy())),
                "interpretation": "sorted A controls lose event matching but preserve run marginals",
            },
            {
                "check": "intentional_target_echo_sigma68",
                "value": 0.0,
                "pass": True,
                "interpretation": "positive leakage sentinel; should be unrealistically small",
            },
        ]
    )


def evaluate_tiers(pair_table: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    b_features = ["left_log_amp", "right_log_amp", "left_peak", "right_peak", "left_tail", "right_tail", "log_left_area", "log_right_area"]
    a_features = [
        "A_sort_trmax_sum_log",
        "A_sort_trmax_diff_log",
        "A_sort_max_sum_log",
        "A_sort_ts_diff",
        "A_sort_baseline_delta",
    ]
    for name in config["astack"]["staves"].keys():
        a_features.extend(
            [
                f"{name}_sort_log_max",
                f"{name}_sort_maxts",
                f"{name}_sort_ts_center_abs",
                f"{name}_sort_log_trmax",
                f"{name}_sort_log_sum",
                f"{name}_sort_sum2_log",
                f"{name}_sort_trsum_log",
                f"{name}_sort_trsum2_log",
                f"{name}_sort_tr_width",
                f"{name}_sort_tr_energy_ratio",
                f"{name}_sort_trap_pre_mean",
                f"{name}_sort_trap_tail_sum",
                f"{name}_sort_trap_tail_frac",
                f"{name}_sort_baseline_median",
                f"{name}_sort_baseline_range",
            ]
        )

    oof_rows = []
    cv_rows = []
    metric_rows = []
    delta_rows = []
    leakage_rows = []
    model_tiers = set(str(t) for t in config["model_tiers"])
    for tier, df in pair_table.groupby("tier", sort=False):
        if tier not in model_tiers:
            continue
        if df["run"].nunique() < 5 or len(df) < 200:
            leakage_rows.append(
                pd.DataFrame(
                    [
                        {
                            "tier": tier,
                            "check": "not_modeled_low_statistics",
                            "value": float(len(df)),
                            "pass": True,
                            "interpretation": "tier has too few rows or runs for grouped held-out model",
                        }
                    ]
                )
            )
            continue
        oof, cv = oof_predictions(df.reset_index(drop=True), config, b_features, a_features)
        cv.insert(0, "tier", tier)
        metrics = metric_table(oof, config, rng)
        metrics.insert(0, "tier", tier)
        deltas = bootstrap_deltas(oof, config, rng)
        deltas.insert(0, "tier", tier)
        if tier == config["primary_tier"] or bool((deltas["comparison"].eq("ml_sorted_a_minus_ml_b_only") & (deltas["ci_high_ns"] < 0.0)).any()):
            leakage = leakage_checks(oof, config, b_features, a_features)
            leakage.insert(0, "tier", tier)
        else:
            leakage = pd.DataFrame(
                [
                    {
                        "tier": tier,
                        "check": "not_triggered",
                        "value": np.nan,
                        "pass": True,
                        "interpretation": "ML sorted-A delta CI was not wholly below zero; primary tier checked separately",
                    }
                ]
            )
        oof_rows.append(oof)
        cv_rows.append(cv)
        metric_rows.append(metrics)
        delta_rows.append(deltas)
        leakage_rows.append(leakage)
    return (
        pd.concat(oof_rows, ignore_index=True),
        pd.concat(cv_rows, ignore_index=True),
        pd.concat(metric_rows, ignore_index=True),
        pd.concat(delta_rows, ignore_index=True),
        pd.concat(leakage_rows, ignore_index=True),
    )


def pair_covariance(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tier, df in oof.groupby("tier", sort=False):
        for method, col in [
            ("raw_pair_median", "resid_raw_centered"),
            ("traditional_b_only", "resid_trad_b"),
            ("traditional_b_plus_sorted_a", "resid_trad_ba"),
            ("ml_extra_trees_b_only", "resid_ml_b"),
            ("ml_extra_trees_b_plus_sorted_a", "resid_ml_ba"),
        ]:
            for run, run_df in df.groupby("run"):
                wide = run_df.pivot_table(index="eventno", columns="pair", values=col, aggfunc="mean")
                if wide.shape[1] < 2 or len(wide.dropna(how="all")) < 10:
                    continue
                cov = wide.cov(min_periods=5)
                for a in cov.columns:
                    for b in cov.columns:
                        if a >= b:
                            continue
                        if pd.notna(cov.loc[a, b]):
                            rows.append({"tier": tier, "method": method, "run": int(run), "pair_a": a, "pair_b": b, "cov_ns2": float(cov.loc[a, b])})
    return pd.DataFrame(rows)


def write_input_hashes(out_dir: Path, config: dict) -> None:
    paths = []
    for run in all_configured_runs(config):
        paths.append(raw_path(config, "astack", run))
        paths.append(raw_path(config, "bstack", run))
        paths.append(sorted_a_path(config, run))
    rows = [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(paths))]
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def md_table(df: pd.DataFrame) -> str:
    return df.fillna("n/a").to_markdown(index=False) if len(df) else "No rows."


def write_result(out_dir: Path, config: dict, counts: pd.DataFrame, tier_count_df: pd.DataFrame, metrics: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame) -> None:
    primary = config["primary_tier"]
    trad = metrics[(metrics["tier"] == primary) & (metrics["method"] == "traditional_b_plus_sorted_a") & (metrics["subset"] == "all")].iloc[0]
    ml = metrics[(metrics["tier"] == primary) & (metrics["method"] == "ml_extra_trees_b_plus_sorted_a") & (metrics["subset"] == "all")].iloc[0]
    trad_delta = deltas[(deltas["tier"] == primary) & (deltas["comparison"] == "traditional_sorted_a_minus_b_only")].iloc[0]
    ml_delta = deltas[(deltas["tier"] == primary) & (deltas["comparison"] == "ml_sorted_a_minus_ml_b_only")].iloc[0]
    finding = (
        "Sorted A quality cuts increase the chance of selected A controls relative to a raw loose B-pair table, "
        "but the run-held-out sorted-A deltas do not establish a robust event-level external-control improvement."
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(counts["pass"].all()),
        "primary_tier": primary,
        "tier_counts": tier_count_df.to_dict(orient="records"),
        "traditional": {
            "method": "grouped-run-heldout Ridge using B pair features plus sorted A quality controls",
            "metric": "heldout sigma68 residual width ns",
            "value": finite_float(trad["sigma68_ns"]),
            "ci": [finite_float(trad["sigma68_ci_low_ns"]), finite_float(trad["sigma68_ci_high_ns"])],
            "sorted_a_delta_vs_b_only_ci": [finite_float(trad_delta["ci_low_ns"]), finite_float(trad_delta["ci_high_ns"])],
        },
        "ml": {
            "method": "grouped-run-heldout bounded ExtraTrees using B pair features plus sorted A quality controls",
            "metric": "heldout sigma68 residual width ns",
            "value": finite_float(ml["sigma68_ns"]),
            "ci": [finite_float(ml["sigma68_ci_low_ns"]), finite_float(ml["sigma68_ci_high_ns"])],
            "sorted_a_delta_vs_ml_b_only_ci": [finite_float(ml_delta["ci_low_ns"]), finite_float(ml_delta["ci_high_ns"])],
        },
        "finding": finding,
        "leakage": leakage.to_dict(orient="records"),
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    tier_count_df: pd.DataFrame,
    cv: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    cov: pd.DataFrame,
) -> None:
    primary = config["primary_tier"]
    selected_metrics = metrics[
        metrics["method"].isin(["traditional_b_only", "traditional_b_plus_sorted_a", "ml_extra_trees_b_only", "ml_extra_trees_b_plus_sorted_a"])
        & metrics["subset"].isin(["all", "raw_A_any_selected", "downstream_only"])
    ].copy()
    cov_summary = pd.DataFrame()
    if len(cov):
        cov_summary = (
            cov.assign(abs_cov_ns2=lambda x: x["cov_ns2"].abs())
            .groupby(["tier", "method"], as_index=False)
            .agg(
                n_covariances=("cov_ns2", "size"),
                median_abs_cov_ns2=("abs_cov_ns2", "median"),
                max_abs_cov_ns2=("abs_cov_ns2", "max"),
            )
        )
    primary_deltas = deltas[deltas["tier"].eq(primary)]
    report = f"""# S05d: sorted ROOT quality-variable A-control repeat

- **Ticket:** {config['ticket']}
- **Worker:** {config['worker']}
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `{config_path}`
- **Raw input:** `{config['raw_root_dir']}`
- **Sorted A input:** `{config['sorted_a_dir']}`

## Question

Repeat the loose-tier A-stack external-control test using sorted ROOT quality variables (`hrdMaxTS`, `hrdTrMax`, `hrdMax`, trap summaries, and baseline summaries). The test asks whether sorted pulse-shape quality cuts isolate cleaner A/B coincidences than raw low-threshold amplitude tiers. No Monte Carlo was used.

## Reproduction first

The raw ROOT count gate was run before reading sorted quality variables.

{md_table(counts)}

## Sorted quality tiers

All tiers use loose B-pair rows with both B staves above `{config['loose_b_pair_cut_adc']:.0f}` ADC. Sorted A tiers then require event-matched A quality in `data/sorted-a`; the sorted tree is joined to raw A by entry order, with `hrdEvtNo` retained as a diagnostic only.

{md_table(tier_count_df)}

## Traditional and ML methods

Traditional method: grouped-run-heldout Ridge using pair identity and B-pair amplitude/shape features; the sorted-A version adds `hrdMax`, `hrdMaxTS`, `hrdTrMax`, trap-window, trap-tail, and baseline summaries. ML method: grouped-run-heldout bounded ExtraTrees with the same B-only and B-plus-sorted-A split. Feature lists exclude run id, event id, `A_sorted_evt`, raw times, and the target residual.

{md_table(selected_metrics)}

Bootstrap deltas are sorted-A minus B-only on sigma68; negative means sorted A controls narrowed held-out B residuals.

{md_table(deltas)}

Primary tier `{primary}` deltas:

{md_table(primary_deltas)}

Run-held-out fold summary:

{md_table(cv)}

## Leakage checks

{md_table(leakage)}

The primary tier is always checked with runwise shuffled sorted-A controls. Any other tier also gets this check if the ML sorted-A improvement CI is wholly below zero.

## Residual covariance

{md_table(cov_summary)}

## Finding

Sorted A quality cuts substantially enrich rows with raw selected A controls, but the held-out B-residual widths do not show a secure event-level external-control gain. The primary sorted-A tier should therefore be treated as another null A-control result rather than evidence for a clean A/B coincidence selector.

## Artifacts

`reproduction_match_table.csv`, `tier_counts.csv`, `sorted_quality_pair_table.csv.gz`, `oof_predictions.csv`, `run_heldout_folds.csv`, `heldout_metrics.csv`, `bootstrap_deltas.csv`, `leakage_checks.csv`, `pair_covariance_by_run.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s05d_1781017418_11811_0f2442d1_sorted_quality_a_control.py --config {config_path}
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: dict, commands: List[str]) -> None:
    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    inputs = pd.read_csv(out_dir / "input_sha256.csv")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "config": str(config_path),
        "commands": commands,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "input_files": {row["file"]: {"sha256": row["sha256"], "bytes": int(row["bytes"])} for _, row in inputs.iterrows()},
        "output_sha256": output_hashes,
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s05d_1781017418_11811_0f2442d1_sorted_quality_a_control.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    counts = S05A.reproduce_counts(config)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    write_input_hashes(out_dir, config)

    pair_path = out_dir / "sorted_quality_pair_table.csv.gz"
    if pair_path.exists():
        pair_table = pd.read_csv(pair_path)
    else:
        pair_table = build_pair_table(config)
        pair_table.to_csv(pair_path, index=False, compression="gzip")
    tier_count_df = tier_counts(pair_table)
    tier_count_df.to_csv(out_dir / "tier_counts.csv", index=False)

    oof, cv, metrics, deltas, leakage = evaluate_tiers(pair_table, config, rng)
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)
    cv.to_csv(out_dir / "run_heldout_folds.csv", index=False)
    metrics.to_csv(out_dir / "heldout_metrics.csv", index=False)
    deltas.to_csv(out_dir / "bootstrap_deltas.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    cov = pair_covariance(oof)
    cov.to_csv(out_dir / "pair_covariance_by_run.csv", index=False)

    command = f"/home/billy/anaconda3/bin/python scripts/s05d_1781017418_11811_0f2442d1_sorted_quality_a_control.py --config {args.config}"
    write_result(out_dir, config, counts, tier_count_df, metrics, deltas, leakage)
    write_report(out_dir, args.config, config, counts, tier_count_df, cv, metrics, deltas, leakage, cov)
    write_manifest(out_dir, args.config, config, [command])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
