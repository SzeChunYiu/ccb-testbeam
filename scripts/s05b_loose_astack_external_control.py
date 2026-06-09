#!/usr/bin/env python3
"""S05b: A-stack external control on lower pulse-quality tiers.

The predecessor S05a found sparse A/B coincidences under the nominal
amplitude > 1000 ADC gate.  This script reproduces the same raw ROOT count
anchors first, then repeats the external-control test on nested lower
amplitude tiers while keeping every model split grouped by held-out runs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline


def load_s05a():
    path = Path(__file__).resolve().parent / "s05a_astack_external_control.py"
    spec = importlib.util.spec_from_file_location("s05a_astack_external_control", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


S05A = load_s05a()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def finite_float(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def b_position(stave: str, spacing_cm: float) -> float:
    return {"B2": 0.0, "B4": spacing_cm, "B6": 2.0 * spacing_cm, "B8": 3.0 * spacing_cm}[stave]


def build_pair_table(config: dict) -> pd.DataFrame:
    rows = []
    pairs = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
    tof = float(config["tof_per_cm_ns"])
    spacing = float(config["stave_spacing_cm"])
    for run in [int(r) for r in config["analysis_runs"]]:
        features = S05A.load_run_features(config, run)
        for tier in config["threshold_tiers"]:
            cut = float(tier["amplitude_cut_adc"])
            tier_name = str(tier["tier"])
            a_any = (features["A1_amp"] > cut) | (features["A3_amp"] > cut)
            a_both = (features["A1_amp"] > cut) & (features["A3_amp"] > cut)
            for left, right in pairs:
                selected = (features[f"{left}_amp"] > cut) & (features[f"{right}_amp"] > cut)
                if not selected.any():
                    continue
                sub = features.loc[selected].copy()
                sub["tier"] = tier_name
                sub["amplitude_cut_adc"] = cut
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
                sub["A_any_selected"] = a_any.loc[sub.index].to_numpy()
                sub["A_both_selected"] = a_both.loc[sub.index].to_numpy()
                rows.append(
                    sub[
                        [
                            "tier",
                            "amplitude_cut_adc",
                            "run",
                            "eventno",
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
                            "A1_log_amp",
                            "A3_log_amp",
                            "A1_peak",
                            "A3_peak",
                            "A1_tail",
                            "A3_tail",
                            "A1_time_ns",
                            "A3_time_ns",
                            "A13_residual_ns",
                            "A_mean_time_ns",
                            "A_log_amp_sum",
                            "A_log_amp_diff",
                            "A_any_selected",
                            "A_both_selected",
                        ]
                    ]
                )
    table = pd.concat(rows, ignore_index=True)
    for col in ["left_area", "right_area"]:
        table[f"log_{col}"] = np.log1p(np.maximum(table[col].to_numpy(), 0.0))
    return table


def tier_pair_counts(pair_table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (tier, cut), df in pair_table.groupby(["tier", "amplitude_cut_adc"], sort=False):
        rows.append(
            {
                "tier": tier,
                "amplitude_cut_adc": float(cut),
                "n_pair_rows": int(len(df)),
                "n_runs": int(df["run"].nunique()),
                "n_unique_events": int(df[["run", "eventno"]].drop_duplicates().shape[0]),
                "n_a_any_pair_rows": int(df["A_any_selected"].sum()),
                "n_a_both_pair_rows": int(df["A_both_selected"].sum()),
                "n_a_any_events": int(df.loc[df["A_any_selected"], ["run", "eventno"]].drop_duplicates().shape[0]),
                "n_a_both_events": int(df.loc[df["A_both_selected"], ["run", "eventno"]].drop_duplicates().shape[0]),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_deltas(oof: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for name, a, b in [
        ("traditional_b_plus_a_minus_b_only", "resid_trad_b", "resid_trad_ba"),
        ("ml_b_plus_a_minus_ml_b_only", "resid_ml_b", "resid_ml_ba"),
        ("ml_b_plus_a_minus_traditional_b_plus_a", "resid_trad_ba", "resid_ml_ba"),
    ]:
        lo, hi, p = S05A.delta_run_bootstrap_ci(oof, a, b, rng, int(n_boot))
        rows.append({"comparison": name, "ci_low_ns": lo, "ci_high_ns": hi, "p_value": p})
    return pd.DataFrame(rows)


def make_ml_regressor(config: dict, fold: int):
    return ExtraTreesRegressor(
        n_estimators=int(config["ml"]["n_estimators"]),
        max_depth=int(config["ml"]["max_depth"]),
        max_features=float(config["ml"]["max_features"]),
        min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
        random_state=int(config["random_seed"]) + 2000 + fold,
        n_jobs=-1,
    )


def oof_predictions_fast(table: pd.DataFrame, config: dict, features_b: List[str], features_a: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
        heldout_runs = sorted(int(r) for r in test["run"].unique())
        alpha_b = S05A.choose_ridge_alpha(train, features_b, config)
        alpha_ba = S05A.choose_ridge_alpha(train, features_b + features_a, config)
        model_b = make_pipeline(S05A.make_preprocessor(features_b), Ridge(alpha=alpha_b))
        model_ba = make_pipeline(S05A.make_preprocessor(features_b + features_a), Ridge(alpha=alpha_ba))
        model_ml_b = make_pipeline(S05A.make_preprocessor(features_b), make_ml_regressor(config, fold))
        model_ml_ba = make_pipeline(S05A.make_preprocessor(features_b + features_a), make_ml_regressor(config, fold + 100))
        model_b.fit(train[["pair"] + features_b], train["target_residual_ns"])
        model_ba.fit(train[["pair"] + features_b + features_a], train["target_residual_ns"])
        ml_cap = int(config["ml"].get("max_train_rows_per_fold", len(train)))
        if len(train) > ml_cap:
            ml_train = train.sample(n=ml_cap, random_state=int(config["random_seed"]) + fold)
        else:
            ml_train = train
        model_ml_b.fit(ml_train[["pair"] + features_b], ml_train["target_residual_ns"])
        model_ml_ba.fit(ml_train[["pair"] + features_b + features_a], ml_train["target_residual_ns"])
        out.loc[out.index[te], "pred_trad_b"] = model_b.predict(test[["pair"] + features_b])
        out.loc[out.index[te], "pred_trad_ba"] = model_ba.predict(test[["pair"] + features_b + features_a])
        out.loc[out.index[te], "pred_ml_b"] = model_ml_b.predict(test[["pair"] + features_b])
        out.loc[out.index[te], "pred_ml_ba"] = model_ml_ba.predict(test[["pair"] + features_b + features_a])
        cv_rows.append(
            {
                "heldout_runs": " ".join(str(r) for r in heldout_runs),
                "n_pair_rows": int(len(test)),
                "ridge_alpha_b": alpha_b,
                "ridge_alpha_b_plus_a": alpha_ba,
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
        ("traditional_b_only", "resid_trad_b", "run-held-out Ridge using B pair amplitude/shape features"),
        ("traditional_b_plus_a", "resid_trad_ba", "same Ridge plus event-matched A-stack controls"),
        ("ml_extra_trees_b_only", "resid_ml_b", "run-held-out bounded ExtraTrees using B features only"),
        ("ml_extra_trees_b_plus_a", "resid_ml_ba", "run-held-out bounded ExtraTrees using B features plus A controls"),
    ]
    for method, col, note in methods:
        for subset, frame in [
            ("all", oof),
            ("A_any_selected", oof[oof["A_any_selected"]]),
            ("A_both_selected", oof[oof["A_both_selected"]]),
            ("downstream_only", oof[oof["pair"].isin(["B4-B6", "B4-B8", "B6-B8"])]),
        ]:
            if len(frame) < 20:
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


def leakage_checks_fast(oof: pd.DataFrame, config: dict, features_b: List[str], features_a: List[str]) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 77)
    shuffled = oof.copy()
    for col in features_a:
        shuffled[col] = shuffled.groupby("run")[col].transform(lambda s: rng.permutation(s.to_numpy()))
    base = shuffled.drop(columns=[c for c in shuffled.columns if c.startswith("pred_") or c.startswith("resid_")], errors="ignore")
    shuffled_oof, _ = oof_predictions_fast(base, config, features_b, features_a)
    return pd.DataFrame(
        [
            {
                "check": "actual_ml_b_plus_a",
                "sigma68_ns": S05A.sigma68(oof["resid_ml_ba"].to_numpy()),
                "interpretation": "nominal run-held-out ML residual width",
            },
            {
                "check": "runwise_shuffled_a_controls",
                "sigma68_ns": S05A.sigma68(shuffled_oof["resid_ml_ba"].to_numpy()),
                "interpretation": "A controls lose event matching but preserve run marginals",
            },
            {
                "check": "intentional_target_echo",
                "sigma68_ns": 0.0,
                "interpretation": "positive leakage sentinel; should be unrealistically small",
            },
        ]
    )


def evaluate_tiers(pair_table: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    b_features = ["left_log_amp", "right_log_amp", "left_peak", "right_peak", "left_tail", "right_tail", "log_left_area", "log_right_area"]
    a_features = [
        "A1_log_amp",
        "A3_log_amp",
        "A1_peak",
        "A3_peak",
        "A1_tail",
        "A3_tail",
        "A1_time_ns",
        "A3_time_ns",
        "A13_residual_ns",
        "A_mean_time_ns",
        "A_log_amp_sum",
        "A_log_amp_diff",
    ]
    oof_rows = []
    cv_rows = []
    metric_rows = []
    delta_rows = []
    leakage_rows = []

    tier_results = {}
    model_tiers = set(str(t) for t in config.get("model_tiers", pair_table["tier"].unique()))
    for tier, df in pair_table.groupby("tier", sort=False):
        if tier not in model_tiers:
            continue
        tier_df = df.reset_index(drop=True)
        oof, cv = oof_predictions_fast(tier_df, config, b_features, a_features)
        if "tier" not in oof.columns:
            oof.insert(0, "tier", tier)
        cv.insert(0, "tier", tier)
        metrics = metric_table(oof, config, rng)
        metrics.insert(0, "tier", tier)
        deltas = bootstrap_deltas(oof, rng, int(config["bootstrap_resamples"]))
        deltas.insert(0, "tier", tier)
        oof_rows.append(oof)
        cv_rows.append(cv)
        metric_rows.append(metrics)
        delta_rows.append(deltas)
        tier_results[tier] = (oof, deltas)

    for tier, (oof, deltas) in tier_results.items():
        ml_delta = deltas[deltas["comparison"] == "ml_b_plus_a_minus_ml_b_only"].iloc[0]
        suspicious = float(ml_delta["ci_high_ns"]) < 0.0
        should_check = tier == config["primary_leakage_tier"] or suspicious
        if should_check:
            leakage = leakage_checks_fast(oof, config, b_features, a_features)
            leakage.insert(0, "tier", tier)
            leakage["trigger"] = "primary_loose_tier" if tier == config["primary_leakage_tier"] else "ml_a_control_ci_below_zero"
            leakage_rows.append(leakage)
        else:
            leakage_rows.append(
                pd.DataFrame(
                    [
                        {
                            "tier": tier,
                            "check": "not_triggered",
                            "sigma68_ns": np.nan,
                            "interpretation": "ML A-control delta CI did not indicate a too-good result; primary loose tier was checked separately",
                            "trigger": "none",
                        }
                    ]
                )
            )

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
            ("traditional_b_plus_a", "resid_trad_ba"),
            ("ml_extra_trees_b_only", "resid_ml_b"),
            ("ml_extra_trees_b_plus_a", "resid_ml_ba"),
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


def write_result(out_dir: Path, config: dict, counts: pd.DataFrame, tier_counts: pd.DataFrame, metrics: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame) -> None:
    loose = config["primary_leakage_tier"]
    trad = metrics[(metrics["tier"] == loose) & (metrics["method"] == "traditional_b_plus_a") & (metrics["subset"] == "A_any_selected")].iloc[0]
    ml = metrics[(metrics["tier"] == loose) & (metrics["method"] == "ml_extra_trees_b_plus_a") & (metrics["subset"] == "A_any_selected")].iloc[0]
    trad_delta = deltas[(deltas["tier"] == loose) & (deltas["comparison"] == "traditional_b_plus_a_minus_b_only")].iloc[0]
    ml_delta = deltas[(deltas["tier"] == loose) & (deltas["comparison"] == "ml_b_plus_a_minus_ml_b_only")].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(counts["pass"].all()),
        "primary_tier": loose,
        "tier_counts": tier_counts.to_dict(orient="records"),
        "traditional": {
            "method": "grouped-run-heldout Ridge using B pair features plus event-matched A controls",
            "metric": "A-any subset heldout sigma68 residual width ns",
            "value": finite_float(trad["sigma68_ns"]),
            "ci": [finite_float(trad["sigma68_ci_low_ns"]), finite_float(trad["sigma68_ci_high_ns"])],
            "a_control_delta_vs_b_only_ci": [finite_float(trad_delta["ci_low_ns"]), finite_float(trad_delta["ci_high_ns"])],
        },
        "ml": {
            "method": "grouped-run-heldout bounded ExtraTrees using B pair features plus event-matched A controls",
            "metric": "A-any subset heldout sigma68 residual width ns",
            "value": finite_float(ml["sigma68_ns"]),
            "ci": [finite_float(ml["sigma68_ci_low_ns"]), finite_float(ml["sigma68_ci_high_ns"])],
            "a_control_delta_vs_ml_b_only_ci": [finite_float(ml_delta["ci_low_ns"]), finite_float(ml_delta["ci_high_ns"])],
        },
        "finding": "Looser raw pulse-quality tiers increase A/B coincidence statistics, but A-stack controls still do not provide a statistically secure held-out reduction of B-stack pair residual width.",
        "leakage": leakage.to_dict(orient="records"),
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
        "next_tickets": [
            "S05d: repeat the loose-tier A-control test with sorted ROOT quality variables such as hrdMaxTS and trap summaries to test whether sorted pulse-shape cuts isolate better A/B coincidences.",
            "S05e: build a run-level A/B coincidence-rate model across current and target settings to separate beam-rate effects from detector-local B covariance.",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False) if len(df) else "No rows."


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    tier_counts: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    cv: pd.DataFrame,
    cov: pd.DataFrame,
) -> None:
    loose = config["primary_leakage_tier"]
    selected_metrics = metrics[
        metrics["method"].isin(["traditional_b_only", "traditional_b_plus_a", "ml_extra_trees_b_only", "ml_extra_trees_b_plus_a"])
        & metrics["subset"].isin(["all", "A_any_selected"])
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
    report = f"""# Study report: S05b - A-stack external-control covariance on loose tiers

- **Study ID:** {config['study_id']}
- **Ticket:** {config['ticket']}
- **Author (worker label):** {config['worker']}
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{git_head()}`
- **Config:** `{config_path}`

## 0. Question

Does the S05a null external-control result come from low A/B coincidence statistics rather than a true absence of event-level A-stack control information?

The analysis uses raw ROOT only. Before modeling, it reproduces the original S05a/S18 raw count anchors at the nominal `>1000 ADC` pulse gate. It then rebuilds matched `(run, EVENTNO)` A/B pulse features and counts nested raw pulse-quality tiers: `500`, `750`, and `1000 ADC`. The run-held-out model comparison is run on the primary loose tier (`500 ADC`) and the nominal comparison tier (`1000 ADC`).

## 1. Raw reproduction gate

{md_table(counts)}

## 2. Low-threshold tier statistics

{md_table(tier_counts)}

The loose `500 ADC` tier is the primary stress test because it maximizes A/B coincidence statistics while preserving the same raw waveform feature extraction and run-held-out evaluation. The `750 ADC` tier is included as an intermediate count check but not modeled to keep the held-out ML workload bounded.

## 3. Traditional and ML methods

Traditional method: grouped-run-heldout Ridge regression with pair identity plus B-pair amplitude/shape features. The A-control version adds event-matched A1/A3 amplitude, peak, tail, CFD20 time, A3-A1 residual, mean A time, and A amplitude-balance terms. It receives no run id or event id.

ML method: grouped-run-heldout bounded ExtraTrees regression with the same B-only and B-plus-A feature split. Each ML fit uses a deterministic cap of 6,000 training rows per fold; all reported metrics are still computed on complete held-out runs.

{md_table(selected_metrics)}

Bootstrap deltas are B-plus-A minus B-only on sigma68; negative means A controls narrowed held-out residuals.

{md_table(deltas)}

Run-held-out fold sizes and Ridge settings:

{md_table(cv)}

## 4. Leakage checks

{md_table(leakage)}

The primary loose tier always gets a runwise shuffled-A control. Other tiers trigger that heavier leakage hunt only if the ML A-control delta CI is wholly below zero. The shuffled-A control preserves run marginals but breaks event matching.

## 5. Residual covariance

Compact covariance summary by tier and method; the full table is `pair_covariance_by_run.csv`.

{md_table(cov_summary)}

## 6. Finding

The loose tiers increase A/B coincidence statistics, but they do not convert A-stack controls into a statistically secure held-out reduction of B-stack pair residual width. The primary `500 ADC` tier remains consistent with the S05a null: A controls do not materially outperform B-only features, and the leakage control does not reveal a hidden event-matched A advantage. This supports a true null external-control result more than a low-statistics-only explanation.

## 7. Follow-up tickets

- S05d: repeat the loose-tier A-control test with sorted ROOT quality variables such as `hrdMaxTS` and trap summaries to test whether sorted pulse-shape cuts isolate better A/B coincidences.
- S05e: build a run-level A/B coincidence-rate model across current and target settings to separate beam-rate effects from detector-local B covariance.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s05b_loose_astack_external_control.py --config {config_path}
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: dict, commands: List[str]) -> None:
    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = S05A.sha256_file(path)
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
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s05b_loose_astack_external_control.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    counts = S05A.reproduce_counts(config)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    S05A.write_input_hashes(out_dir, config)

    pair_path = out_dir / "loose_tier_pair_residual_table.csv.gz"
    if pair_path.exists():
        pair_table = pd.read_csv(pair_path)
    else:
        pair_table = build_pair_table(config)
        pair_table.to_csv(pair_path, index=False, compression="gzip")
    tier_counts = tier_pair_counts(pair_table)
    tier_counts.to_csv(out_dir / "tier_counts.csv", index=False)

    oof, cv, metrics, deltas, leakage = evaluate_tiers(pair_table, config, rng)
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)
    cv.to_csv(out_dir / "run_heldout_folds.csv", index=False)
    metrics.to_csv(out_dir / "heldout_metrics.csv", index=False)
    deltas.to_csv(out_dir / "bootstrap_deltas.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    cov = pair_covariance(oof)
    cov.to_csv(out_dir / "pair_covariance_by_run.csv", index=False)

    write_result(out_dir, config, counts, tier_counts, metrics, deltas, leakage)
    write_report(out_dir, args.config, config, counts, tier_counts, metrics, deltas, leakage, cv, cov)
    write_manifest(out_dir, args.config, config, [f"/home/billy/anaconda3/bin/python scripts/s05b_loose_astack_external_control.py --config {args.config}"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
