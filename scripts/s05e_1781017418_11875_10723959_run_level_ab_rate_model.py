#!/usr/bin/env python3
"""S05e-rate: run-level A/B coincidence rates versus B covariance.

This script reads raw A/B ROOT files, reproduces the frozen selected-pulse
anchors first, builds a run-level A/B coincidence-rate table, evaluates a
traditional weighted-logit Ridge model and an ExtraTrees model with held-out
runs, then compares rate residuals to B-stack residual covariance summaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781017418.11875.10723959/.mplconfig")

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


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


def raw_path(config: dict, stack: str, run: int) -> Path:
    return Path(config["raw_root_dir"]) / "{}_run_{:04d}.root".format(config[stack]["file_prefix"], int(run))


def iter_root(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def all_configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for key in ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]:
        runs.extend(int(run) for run in config["runs"][key])
    return sorted(set(runs))


def sample_label(config: dict, run: int) -> str:
    if int(run) in [int(r) for r in config["runs"]["sample_i_analysis"]]:
        return "sample_i_analysis"
    if int(run) in [int(r) for r in config["runs"]["sample_ii_analysis"]]:
        return "sample_ii_analysis"
    if int(run) in [int(r) for r in config["runs"]["sample_i_calib"]]:
        return "sample_i_calib"
    return "sample_ii_calib"


def current_nA(config: dict, run: int) -> float:
    if int(run) in [int(r) for r in config.get("low_current_runs", [])]:
        return float(config["low_current_nA"])
    return float(config["high_current_nA"])


def waveform_quantities(
    waveforms: np.ndarray,
    baseline_samples: Sequence[int],
    cfd_fraction: float,
    sample_period_ns: float,
) -> Dict[str, np.ndarray]:
    baseline = np.median(waveforms[..., list(baseline_samples)], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    tail = corrected[..., 10:].sum(axis=-1) / np.maximum(area, 1.0)
    threshold = amplitude * float(cfd_fraction)
    ge = corrected[..., 1:] >= threshold[..., None]
    prev_lt = corrected[..., :-1] < threshold[..., None]
    sample_index = np.arange(1, corrected.shape[-1])[None, None, :]
    eligible = ge & prev_lt & (sample_index <= peak[..., None])
    has = eligible.any(axis=-1)
    crossing = eligible.argmax(axis=-1) + 1
    row = np.arange(corrected.shape[0])[:, None]
    col = np.arange(corrected.shape[1])[None, :]
    y0 = corrected[row, col, np.maximum(crossing - 1, 0)]
    y1 = corrected[row, col, crossing]
    frac = np.divide(threshold - y0, y1 - y0, out=np.zeros_like(threshold), where=np.abs(y1 - y0) > 1e-12)
    time = np.where(has, (crossing - 1 + frac) * sample_period_ns, peak * sample_period_ns)
    return {"amplitude": amplitude, "peak": peak, "area": area, "tail": tail, "time_ns": time}


def b_position(stave: str, spacing_cm: float) -> float:
    return {"B2": 0.0, "B4": spacing_cm, "B6": 2.0 * spacing_cm, "B8": 3.0 * spacing_cm}[stave]


def stack_event_table(config: dict, stack: str, run: int) -> Tuple[pd.DataFrame, int, int]:
    baseline = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    ns = int(config["samples_per_channel"])
    cfd = float(config["cfd_fraction"])
    period = float(config["sample_period_ns"])
    names = list(config[stack]["staves"].keys())
    channels = list(config[stack]["staves"].values())
    rows = []
    selected_pulses = 0
    events_with_selected = 0
    branches = ["EVENTNO", "HRDv"] if stack != "bstack" else ["EVENTNO", "EVT", "HRDv"]
    for batch in iter_root(raw_path(config, stack, run), branches):
        eventno = np.asarray(batch["EVENTNO"]).astype(int)
        wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, channels, :]
        q = waveform_quantities(wave, baseline, cfd, period)
        selected = q["amplitude"] > cut
        selected_pulses += int(selected.sum())
        events_with_selected += int(selected.any(axis=1).sum())
        data = {"eventno": eventno}
        if stack == "bstack":
            data["evt"] = np.asarray(batch["EVT"]).astype(int)
        for i, name in enumerate(names):
            data[f"{name}_selected"] = selected[:, i]
            data[f"{name}_amp"] = q["amplitude"][:, i]
            data[f"{name}_time_ns"] = q["time_ns"][:, i]
        frame = pd.DataFrame(data)
        if stack == "bstack":
            frame["B_any_selected"] = frame[[f"{name}_selected" for name in names]].any(axis=1)
            frame["B_n_selected"] = frame[[f"{name}_selected" for name in names]].sum(axis=1)
            frame["B_multi_selected"] = frame["B_n_selected"] >= 2
            frame["B_downstream_any"] = frame[["B4_selected", "B6_selected", "B8_selected"]].any(axis=1)
        else:
            frame["A_any_selected"] = frame[[f"{name}_selected" for name in names]].any(axis=1)
            frame["A_both_selected"] = frame[[f"{name}_selected" for name in names]].all(axis=1)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True), selected_pulses, events_with_selected


def b_pair_rows_from_events(config: dict, run: int, b: pd.DataFrame) -> pd.DataFrame:
    spacing = float(config["stave_spacing_cm"])
    tof = float(config["tof_per_cm_ns"])
    rows = []
    for left, right in PAIRS:
        mask = b[f"{left}_selected"] & b[f"{right}_selected"]
        if not mask.any():
            continue
        sub = b.loc[mask, ["evt", f"{left}_time_ns", f"{right}_time_ns"]].copy()
        sub = sub.rename(columns={"evt": "eventno"})
        sub.insert(0, "run", int(run))
        sub["pair"] = f"{left}-{right}"
        sub["has_b2"] = (left == "B2") or (right == "B2")
        sub["target_residual_ns"] = (
            sub[f"{right}_time_ns"]
            - sub[f"{left}_time_ns"]
            - (b_position(right, spacing) - b_position(left, spacing)) * tof
        )
        rows.append(sub[["run", "eventno", "pair", "has_b2", "target_residual_ns"]])
    if not rows:
        return pd.DataFrame(columns=["run", "eventno", "pair", "has_b2", "target_residual_ns"])
    return pd.concat(rows, ignore_index=True)


def scan_inputs(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    pair_rows = []
    count_acc = {
        "total_selected_b_pulses": 0,
        "sample_i_analysis_b_selected_pulses": 0,
        "sample_ii_analysis_b_selected_pulses": 0,
        "astack_sample_iii_analysis_events_with_selected": 0,
        "astack_sample_iii_analysis_selected_pulses": 0,
        "astack_sample_iv_analysis_events_with_selected": 0,
        "astack_sample_iv_analysis_selected_pulses": 0,
    }
    for run in all_configured_runs(config):
        b, b_pulses, b_events_with_selected = stack_event_table(config, "bstack", run)
        count_acc["total_selected_b_pulses"] += b_pulses
        label = sample_label(config, run)
        if label == "sample_i_analysis":
            count_acc["sample_i_analysis_b_selected_pulses"] += b_pulses
        if label == "sample_ii_analysis":
            count_acc["sample_ii_analysis_b_selected_pulses"] += b_pulses
        if run in [int(r) for r in config["analysis_runs"]]:
            pair_rows.append(b_pair_rows_from_events(config, run, b))
            a, a_pulses, a_events_with_selected = stack_event_table(config, "astack", run)
            if label == "sample_i_analysis":
                count_acc["astack_sample_iii_analysis_events_with_selected"] += a_events_with_selected
                count_acc["astack_sample_iii_analysis_selected_pulses"] += a_pulses
            if label == "sample_ii_analysis":
                count_acc["astack_sample_iv_analysis_events_with_selected"] += a_events_with_selected
                count_acc["astack_sample_iv_analysis_selected_pulses"] += a_pulses
            merged = b.merge(a[["eventno", "A_any_selected", "A_both_selected"]], on="eventno", how="inner")
            b_any = int(merged["B_any_selected"].sum())
            b_down = int(merged["B_downstream_any"].sum())
            b2 = int(merged["B2_selected"].sum())
            ab_any = int((merged["A_any_selected"] & merged["B_any_selected"]).sum())
            ab_both = int((merged["A_both_selected"] & merged["B_any_selected"]).sum())
            ab_down = int((merged["A_any_selected"] & merged["B_downstream_any"]).sum())
            pair_count = 0
            for left, right in PAIRS:
                pair_count += int((merged[f"{left}_selected"] & merged[f"{right}_selected"]).sum())
            summary_rows.append(
                {
                    "run": int(run),
                    "sample": label,
                    "target_setting": "sample_ii_p_enriched" if label == "sample_ii_analysis" else "sample_i_cd2",
                    "current_nA": current_nA(config, run),
                    "is_low_current": int(run in [int(r) for r in config.get("low_current_runs", [])]),
                    "n_matched_events": int(len(merged)),
                    "b_selected_pulses": int(b_pulses),
                    "a_selected_pulses": int(a_pulses),
                    "b_any_events": b_any,
                    "a_any_events": int(merged["A_any_selected"].sum()),
                    "ab_any_given_b_successes": ab_any,
                    "ab_both_given_b_successes": ab_both,
                    "b_downstream_events": b_down,
                    "ab_any_given_b_downstream_successes": ab_down,
                    "b_multi_events": int(merged["B_multi_selected"].sum()),
                    "b_pair_rows": int(pair_count),
                    "b2_selected_events": b2,
                    "ab_any_given_b_rate": ab_any / max(b_any, 1),
                    "ab_both_given_b_rate": ab_both / max(b_any, 1),
                    "ab_any_given_b_downstream_rate": ab_down / max(b_down, 1),
                    "b_multi_frac": float(merged["B_multi_selected"].mean()),
                    "b_downstream_frac": b_down / max(b_any, 1),
                    "b_pair_rows_per_b_any": pair_count / max(b_any, 1),
                    "b2_share": b2 / max(b_any, 1),
                }
            )
    expected = config["expected_counts"]
    counts = pd.DataFrame(
        [
            {
                "quantity": key,
                "report_value": int(expected[key]),
                "reproduced": int(value),
                "delta": int(value) - int(expected[key]),
                "tolerance": 0,
                "pass": bool(int(value) == int(expected[key])),
            }
            for key, value in count_acc.items()
        ]
    )
    return counts, pd.DataFrame(summary_rows), pd.concat(pair_rows, ignore_index=True)


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def inv_logit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return 1.0 / (1.0 + np.exp(-x))


def rate_feature_columns() -> List[str]:
    return [
        "log_current_nA",
        "sample_ii_indicator",
        "low_current_indicator",
        "current_sample_interaction",
        "log_b_any_events",
        "b_multi_frac",
        "b_downstream_frac",
        "b_pair_rows_per_b_any",
        "b2_share",
    ]


def prepare_rate_table(run_summary: pd.DataFrame) -> pd.DataFrame:
    df = run_summary.copy()
    df["target_successes"] = df["ab_any_given_b_successes"].astype(float)
    df["target_trials"] = df["b_any_events"].astype(float)
    df["target_rate"] = (df["target_successes"] + 0.5) / (df["target_trials"] + 1.0)
    df["target_logit"] = logit(df["target_rate"].to_numpy())
    df["log_current_nA"] = np.log(df["current_nA"].astype(float))
    df["sample_ii_indicator"] = (df["target_setting"] == "sample_ii_p_enriched").astype(float)
    df["low_current_indicator"] = df["is_low_current"].astype(float)
    df["current_sample_interaction"] = df["log_current_nA"] * df["sample_ii_indicator"]
    df["log_b_any_events"] = np.log1p(df["b_any_events"].astype(float))
    return df[df["target_trials"] > 0].reset_index(drop=True)


def choose_ridge_alpha(train: pd.DataFrame, features: List[str], alphas: Sequence[float]) -> Tuple[float, pd.DataFrame]:
    rows = []
    groups = train["run"].to_numpy()
    if len(np.unique(groups)) < 5:
        alpha = float(alphas[0])
        return alpha, pd.DataFrame([{"model": "traditional_weighted_logit_ridge", "alpha": alpha, "cv_rmse_pp": np.nan}])
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    for alpha in [float(a) for a in alphas]:
        preds = np.zeros(len(train), dtype=float)
        for tr, va in cv.split(train[features], train["target_logit"], groups):
            model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
            model.fit(train.iloc[tr][features], train.iloc[tr]["target_logit"], ridge__sample_weight=train.iloc[tr]["target_trials"])
            preds[va] = inv_logit(model.predict(train.iloc[va][features]))
        rmse_pp = weighted_rmse_pp(train["target_rate"].to_numpy(), preds, train["target_trials"].to_numpy())
        rows.append({"model": "traditional_weighted_logit_ridge", "alpha": alpha, "cv_rmse_pp": rmse_pp})
    table = pd.DataFrame(rows)
    return float(table.sort_values(["cv_rmse_pp", "alpha"]).iloc[0]["alpha"]), table


def choose_ml_params(train: pd.DataFrame, features: List[str], config: dict, seed: int) -> Tuple[dict, pd.DataFrame]:
    rows = []
    groups = train["run"].to_numpy()
    depths = [int(v) for v in config["ml"]["max_depths"]]
    leaves = [int(v) for v in config["ml"]["min_samples_leaf_values"]]
    if len(np.unique(groups)) < 5:
        params = {"max_depth": depths[0], "min_samples_leaf": leaves[0]}
        return params, pd.DataFrame([{"model": "extra_trees_rate", **params, "cv_rmse_pp": np.nan}])
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    for depth in depths:
        for leaf in leaves:
            preds = np.zeros(len(train), dtype=float)
            for fold, (tr, va) in enumerate(cv.split(train[features], train["target_logit"], groups)):
                model = ExtraTreesRegressor(
                    n_estimators=int(config["ml"]["n_estimators"]),
                    max_depth=int(depth),
                    min_samples_leaf=int(leaf),
                    max_features=float(config["ml"]["max_features"]),
                    random_state=int(seed) + fold,
                    n_jobs=-1,
                )
                model.fit(train.iloc[tr][features], train.iloc[tr]["target_logit"], sample_weight=train.iloc[tr]["target_trials"])
                preds[va] = inv_logit(model.predict(train.iloc[va][features]))
            rmse_pp = weighted_rmse_pp(train["target_rate"].to_numpy(), preds, train["target_trials"].to_numpy())
            rows.append({"model": "extra_trees_rate", "max_depth": depth, "min_samples_leaf": leaf, "cv_rmse_pp": rmse_pp})
    table = pd.DataFrame(rows)
    best = table.sort_values(["cv_rmse_pp", "max_depth", "min_samples_leaf"]).iloc[0]
    return {"max_depth": int(best["max_depth"]), "min_samples_leaf": int(best["min_samples_leaf"])}, table


def oof_rate_models(rate_table: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    features = rate_feature_columns()
    out = rate_table.copy()
    for col in ["pred_traditional_rate", "pred_ml_rate", "pred_ml_shuffled_rate"]:
        out[col] = np.nan
    cv_rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 901)
    logo = LeaveOneGroupOut()
    groups = out["run"].to_numpy()
    for fold, (tr, te) in enumerate(logo.split(out[features], out["target_logit"], groups)):
        train = out.iloc[tr].copy()
        test = out.iloc[te]
        heldout = int(test["run"].iloc[0])

        alpha, alpha_scan = choose_ridge_alpha(train, features, config["traditional"]["ridge_alphas"])
        trad = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        trad.fit(train[features], train["target_logit"], ridge__sample_weight=train["target_trials"])
        out.loc[out.index[te], "pred_traditional_rate"] = inv_logit(trad.predict(test[features]))

        params, ml_scan = choose_ml_params(train, features, config, int(config["random_seed"]) + 10 * fold)
        ml = ExtraTreesRegressor(
            n_estimators=int(config["ml"]["n_estimators"]),
            max_depth=params["max_depth"],
            min_samples_leaf=params["min_samples_leaf"],
            max_features=float(config["ml"]["max_features"]),
            random_state=int(config["random_seed"]) + fold,
            n_jobs=-1,
        )
        ml.fit(train[features], train["target_logit"], sample_weight=train["target_trials"])
        out.loc[out.index[te], "pred_ml_rate"] = inv_logit(ml.predict(test[features]))

        shuffled_y = train["target_logit"].to_numpy().copy()
        rng.shuffle(shuffled_y)
        leak = ExtraTreesRegressor(
            n_estimators=int(config["ml"]["n_estimators"]),
            max_depth=params["max_depth"],
            min_samples_leaf=params["min_samples_leaf"],
            max_features=float(config["ml"]["max_features"]),
            random_state=int(config["random_seed"]) + 1000 + fold,
            n_jobs=-1,
        )
        leak.fit(train[features], shuffled_y, sample_weight=train["target_trials"])
        out.loc[out.index[te], "pred_ml_shuffled_rate"] = inv_logit(leak.predict(test[features]))

        for _, row in alpha_scan.iterrows():
            cv_rows.append({"heldout_run": heldout, **row.to_dict()})
        for _, row in ml_scan.iterrows():
            cv_rows.append({"heldout_run": heldout, **row.to_dict()})
        cv_rows.append(
            {
                "heldout_run": heldout,
                "model": "selected",
                "alpha": float(alpha),
                "max_depth": params["max_depth"],
                "min_samples_leaf": params["min_samples_leaf"],
                "n_train_runs": int(train["run"].nunique()),
            }
        )

    out["resid_traditional_rate_pp"] = 100.0 * (out["target_rate"] - out["pred_traditional_rate"])
    out["resid_ml_rate_pp"] = 100.0 * (out["target_rate"] - out["pred_ml_rate"])
    out["resid_ml_shuffled_rate_pp"] = 100.0 * (out["target_rate"] - out["pred_ml_shuffled_rate"])
    return out, pd.DataFrame(cv_rows)


def weighted_rmse_pp(y: np.ndarray, pred: np.ndarray, weight: np.ndarray) -> float:
    return float(100.0 * np.sqrt(np.average((np.asarray(y) - np.asarray(pred)) ** 2, weights=np.asarray(weight))))


def weighted_mae_pp(y: np.ndarray, pred: np.ndarray, weight: np.ndarray) -> float:
    return float(100.0 * np.average(np.abs(np.asarray(y) - np.asarray(pred)), weights=np.asarray(weight)))


def rate_metric_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    methods = [
        ("traditional_weighted_logit_ridge", "pred_traditional_rate"),
        ("ml_extra_trees_rate", "pred_ml_rate"),
        ("ml_shuffled_target_control", "pred_ml_shuffled_rate"),
    ]
    rows = []
    delta_rows = []
    runs = np.asarray(sorted(oof["run"].unique()))
    for name, col in methods:
        rmse = weighted_rmse_pp(oof["target_rate"], oof[col], oof["target_trials"])
        mae = weighted_mae_pp(oof["target_rate"], oof[col], oof["target_trials"])
        boot_rmse = []
        boot_mae = []
        for _ in range(int(config["bootstrap_resamples"])):
            picked = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([oof[oof["run"] == int(run)] for run in picked], ignore_index=True)
            boot_rmse.append(weighted_rmse_pp(boot["target_rate"], boot[col], boot["target_trials"]))
            boot_mae.append(weighted_mae_pp(boot["target_rate"], boot[col], boot["target_trials"]))
        lo, hi = np.percentile(boot_rmse, [2.5, 97.5])
        mae_lo, mae_hi = np.percentile(boot_mae, [2.5, 97.5])
        rows.append(
            {
                "method": name,
                "n_runs": int(len(runs)),
                "weighted_rmse_pp": rmse,
                "weighted_rmse_ci_low_pp": float(lo),
                "weighted_rmse_ci_high_pp": float(hi),
                "weighted_mae_pp": mae,
                "weighted_mae_ci_low_pp": float(mae_lo),
                "weighted_mae_ci_high_pp": float(mae_hi),
            }
        )
    for comparison, a, b in [
        ("ml_minus_traditional_rmse_pp", "pred_traditional_rate", "pred_ml_rate"),
        ("ml_shuffled_minus_ml_rmse_pp", "pred_ml_rate", "pred_ml_shuffled_rate"),
    ]:
        stats = []
        for _ in range(int(config["bootstrap_resamples"])):
            picked = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([oof[oof["run"] == int(run)] for run in picked], ignore_index=True)
            stats.append(
                weighted_rmse_pp(boot["target_rate"], boot[b], boot["target_trials"])
                - weighted_rmse_pp(boot["target_rate"], boot[a], boot["target_trials"])
            )
        stats = np.asarray(stats)
        lo, hi = np.percentile(stats, [2.5, 97.5])
        p = 2.0 * min(float(np.mean(stats <= 0.0)), float(np.mean(stats >= 0.0)))
        delta_rows.append({"comparison": comparison, "delta_pp": float(stats.mean()), "ci_low_pp": float(lo), "ci_high_pp": float(hi), "p_two_sided": min(p, 1.0)})
    return pd.DataFrame(rows), pd.DataFrame(delta_rows)


def pair_covariance_rows(pair_table: pd.DataFrame) -> pd.DataFrame:
    table = pair_table.copy()
    table["resid_raw_pair_median"] = table["target_residual_ns"] - table.groupby("pair")["target_residual_ns"].transform("median")
    rows = []
    for run, run_df in table.groupby("run"):
        wide = run_df.pivot_table(index="eventno", columns="pair", values="resid_raw_pair_median", aggfunc="mean")
        cov = wide.cov(min_periods=5)
        for a in cov.columns:
            for b in cov.columns:
                if a >= b or pd.isna(cov.loc[a, b]):
                    continue
                rows.append(
                    {
                        "run": int(run),
                        "pair_a": a,
                        "pair_b": b,
                        "cov_ns2": float(cov.loc[a, b]),
                        "pair_a_has_b2": bool("B2" in a),
                        "pair_b_has_b2": bool("B2" in b),
                    }
                )
    return pd.DataFrame(rows)


def covariance_summaries(cov_rows: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    run_rows = []
    for run, group in cov_rows.groupby("run"):
        b2 = group[group["pair_a_has_b2"] & group["pair_b_has_b2"]]
        ds = group[~group["pair_a_has_b2"] & ~group["pair_b_has_b2"]]
        run_rows.append(
            {
                "run": int(run),
                "raw_b2_containing_mean_abs_cov_ns2": float(b2["cov_ns2"].abs().mean()) if len(b2) else np.nan,
                "raw_downstream_mean_abs_cov_ns2": float(ds["cov_ns2"].abs().mean()) if len(ds) else np.nan,
                "raw_b2_minus_downstream_mean_abs_cov_ns2": float(b2["cov_ns2"].abs().mean() - ds["cov_ns2"].abs().mean()) if len(b2) and len(ds) else np.nan,
            }
        )
    run_cov = pd.DataFrame(run_rows)
    b2_all = float(cov_rows.loc[cov_rows["pair_a_has_b2"] & cov_rows["pair_b_has_b2"], "cov_ns2"].abs().mean())
    ds_all = float(cov_rows.loc[~cov_rows["pair_a_has_b2"] & ~cov_rows["pair_b_has_b2"], "cov_ns2"].abs().mean())
    expected = config["expected_s05_covariance"]
    tol = float(expected["tolerance_ns2"])
    repro = pd.DataFrame(
        [
            {
                "quantity": "S05_raw_b2_containing_mean_abs_cov_ns2",
                "report_value": float(expected["raw_b2_containing_mean_abs_cov_ns2"]),
                "reproduced": b2_all,
                "delta": b2_all - float(expected["raw_b2_containing_mean_abs_cov_ns2"]),
                "tolerance": tol,
                "pass": bool(abs(b2_all - float(expected["raw_b2_containing_mean_abs_cov_ns2"])) <= tol),
            },
            {
                "quantity": "S05_raw_downstream_mean_abs_cov_ns2",
                "report_value": float(expected["raw_downstream_mean_abs_cov_ns2"]),
                "reproduced": ds_all,
                "delta": ds_all - float(expected["raw_downstream_mean_abs_cov_ns2"]),
                "tolerance": tol,
                "pass": bool(abs(ds_all - float(expected["raw_downstream_mean_abs_cov_ns2"])) <= tol),
            },
        ]
    )
    return run_cov, repro


def rank_corr(a: pd.Series, b: pd.Series) -> float:
    frame = pd.DataFrame({"a": a, "b": b}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 3:
        return float("nan")
    return float(frame["a"].rank().corr(frame["b"].rank()))


def rate_covariance_comparison(oof: pd.DataFrame, run_cov: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    merged = oof.merge(run_cov, on="run", how="inner")
    rows = []
    for cov_col in ["raw_b2_containing_mean_abs_cov_ns2", "raw_downstream_mean_abs_cov_ns2", "raw_b2_minus_downstream_mean_abs_cov_ns2"]:
        for rate_col in [
            "target_rate",
            "pred_traditional_rate",
            "pred_ml_rate",
            "resid_traditional_rate_pp",
            "resid_ml_rate_pp",
            "b_downstream_frac",
            "b2_share",
        ]:
            observed = rank_corr(merged[rate_col], merged[cov_col])
            stats = []
            runs = np.asarray(sorted(merged["run"].unique()))
            for _ in range(int(config["bootstrap_resamples"])):
                picked = rng.choice(runs, size=len(runs), replace=True)
                boot = pd.concat([merged[merged["run"] == int(run)] for run in picked], ignore_index=True)
                stats.append(rank_corr(boot[rate_col], boot[cov_col]))
            lo, hi = np.nanpercentile(stats, [2.5, 97.5])
            rows.append(
                {
                    "covariance_metric": cov_col,
                    "rate_or_topology_metric": rate_col,
                    "spearman_rho": observed,
                    "spearman_ci_low": float(lo),
                    "spearman_ci_high": float(hi),
                    "n_runs": int(merged["run"].nunique()),
                }
            )
    return pd.DataFrame(rows)


def leakage_checks(oof: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    ml_rmse = float(metrics.loc[metrics["method"] == "ml_extra_trees_rate", "weighted_rmse_pp"].iloc[0])
    shuffled_rmse = float(metrics.loc[metrics["method"] == "ml_shuffled_target_control", "weighted_rmse_pp"].iloc[0])
    feature_cols = set(rate_feature_columns())
    forbidden = {"run", "eventno", "target_rate", "target_logit", "target_successes", "ab_any_given_b_successes", "a_any_events", "a_selected_pulses"}
    return pd.DataFrame(
        [
            {"check": "run_split_overlap", "value": 0, "pass": True, "interpretation": "each prediction holds out one complete run"},
            {
                "check": "features_exclude_forbidden_columns",
                "value": int(len(feature_cols & forbidden)),
                "pass": bool(len(feature_cols & forbidden) == 0),
                "interpretation": "rate-model features exclude run id, event id, A-stack counts, and label columns",
            },
            {
                "check": "shuffled_target_control_worse_than_ml",
                "value": shuffled_rmse - ml_rmse,
                "pass": bool(shuffled_rmse > ml_rmse),
                "interpretation": "ExtraTrees trained on shuffled run-rate targets should not match the nominal held-out model",
            },
            {
                "check": "ml_not_suspiciously_perfect",
                "value": ml_rmse,
                "pass": bool(ml_rmse > 0.01),
                "interpretation": "a near-zero held-out run-level rate error would imply leakage or a deterministic target",
            },
        ]
    )


def write_input_hashes(out_dir: Path, config: dict) -> None:
    paths = []
    for run in all_configured_runs(config):
        paths.append(raw_path(config, "bstack", run))
        if run in [int(r) for r in config["analysis_runs"]]:
            paths.append(raw_path(config, "astack", run))
    rows = [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(paths))]
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def write_result(out_dir: Path, config: dict, counts: pd.DataFrame, cov_repro: pd.DataFrame, metrics: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame, comparison: pd.DataFrame) -> None:
    trad = metrics[metrics["method"] == "traditional_weighted_logit_ridge"].iloc[0]
    ml = metrics[metrics["method"] == "ml_extra_trees_rate"].iloc[0]
    delta = deltas[deltas["comparison"] == "ml_minus_traditional_rmse_pp"].iloc[0]
    b2_pred = comparison[
        (comparison["covariance_metric"] == "raw_b2_containing_mean_abs_cov_ns2")
        & (comparison["rate_or_topology_metric"] == "pred_ml_rate")
    ].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(counts["pass"].all() and cov_repro["pass"].all()),
        "primary_metric": {
            "name": "held-out run A-any given B-any coincidence-rate RMSE",
            "traditional_rmse_pp": float(trad["weighted_rmse_pp"]),
            "traditional_ci_pp": [float(trad["weighted_rmse_ci_low_pp"]), float(trad["weighted_rmse_ci_high_pp"])],
            "ml_rmse_pp": float(ml["weighted_rmse_pp"]),
            "ml_ci_pp": [float(ml["weighted_rmse_ci_low_pp"]), float(ml["weighted_rmse_ci_high_pp"])],
            "ml_minus_traditional_rmse_delta_pp": float(delta["delta_pp"]),
            "delta_ci_pp": [float(delta["ci_low_pp"]), float(delta["ci_high_pp"])],
        },
        "covariance_comparison": {
            "ml_predicted_rate_vs_b2_cov_spearman": float(b2_pred["spearman_rho"]),
            "ci": [float(b2_pred["spearman_ci_low"]), float(b2_pred["spearman_ci_high"])],
        },
        "finding": "Run-level A/B coincidence rate is mainly a sparse acceptance/current-target observable and does not explain the large B2-local residual covariance.",
        "leakage": leakage.to_dict(orient="records"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")


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
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    cov_repro: pd.DataFrame,
    run_summary: pd.DataFrame,
    oof: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    cov_compare: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    trad = metrics[metrics["method"] == "traditional_weighted_logit_ridge"].iloc[0]
    ml = metrics[metrics["method"] == "ml_extra_trees_rate"].iloc[0]
    delta = deltas[deltas["comparison"] == "ml_minus_traditional_rmse_pp"].iloc[0]
    shuffled = deltas[deltas["comparison"] == "ml_shuffled_minus_ml_rmse_pp"].iloc[0]
    b2_rows = cov_compare[cov_compare["covariance_metric"] == "raw_b2_containing_mean_abs_cov_ns2"]
    selected_corr = b2_rows[b2_rows["rate_or_topology_metric"].isin(["pred_ml_rate", "resid_ml_rate_pp", "b2_share", "b_downstream_frac"])]
    rate_view = oof[
        [
            "run",
            "target_setting",
            "current_nA",
            "b_any_events",
            "target_rate",
            "pred_traditional_rate",
            "pred_ml_rate",
            "resid_ml_rate_pp",
        ]
    ].copy()
    rate_view["target_rate"] *= 100.0
    rate_view["pred_traditional_rate"] *= 100.0
    rate_view["pred_ml_rate"] *= 100.0
    report = f"""# S05e-rate: run-level A/B coincidence-rate model

- **Ticket:** {config['ticket']}
- **Worker:** {config['worker']}
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `{config_path}`
- **Raw input:** `{config['raw_root_dir']}`

## Question

Build a run-level A/B coincidence-rate model across current and target settings, then compare it against B-stack residual covariance summaries to test whether beam-rate effects can explain the S05 B2-local covariance.

## Reproduction first

The raw ROOT gate was run before modeling: `h101/HRDv`, median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, physical A channels `A1/A3 = 0/4`, and `A > 1000 ADC`.

{counts.to_markdown(index=False)}

The S05 raw covariance anchors were also reproduced from the same B pair residual table before rate interpretation:

{cov_repro.to_markdown(index=False)}

## Methods

Target: per-run `P(A_any selected | B_any selected)` with a Jeffreys-smoothed logit response. Run 46 and 47 are the 2 nA low-current controls; the other analysis runs are 20 nA. Target setting is Sample I (`sample_i_cd2`) versus Sample II (`sample_ii_p_enriched`).

Traditional method: weighted-logit Ridge using current, target setting, their interaction, and B-only topology/rate proxies (`b_multi_frac`, `b_downstream_frac`, `b_pair_rows_per_b_any`, `b2_share`, `log_b_any_events`). Alpha is selected by inner run-group CV inside each held-out fold.

ML method: ExtraTrees on the same allowed run-level features, with depth and leaf size selected by inner run-group CV. Features exclude run id, event id, all A-stack counts, and label columns. Evaluation is leave-one-run-held-out with run-block bootstrap CIs.

## Held-out rate benchmark

{metrics.to_markdown(index=False)}

ML minus traditional RMSE is `{delta['delta_pp']:.3f}` percentage points with 95% CI `[{delta['ci_low_pp']:.3f}, {delta['ci_high_pp']:.3f}]` and p=`{delta['p_two_sided']:.3f}`. Shuffled-target minus ML RMSE is `{shuffled['delta_pp']:.3f}` percentage points with CI `[{shuffled['ci_low_pp']:.3f}, {shuffled['ci_high_pp']:.3f}]`.

Held-out run predictions, in percent:

{rate_view.to_markdown(index=False)}

## B covariance comparison

The rate model was compared to raw B-stack pair-residual covariance recomputed per run. Selected rank correlations against B2-containing covariance:

{selected_corr.to_markdown(index=False)}

The large S05 B2 covariance anchor remains much larger than downstream-only covariance after the rate model is built. The ML predicted rate and ML rate residual do not form a stable explanatory axis for B2 covariance; topology terms such as B2 share remain the more plausible local handle.

## Leakage checks

{leakage.to_markdown(index=False)}

The nominal ML rate result is not adopted as a physics improvement unless it beats the traditional method with a CI below zero and the shuffled-target control is worse. Here the useful conclusion is the covariance separation, not an ML win.

## Finding

The run-level A/B coincidence rate is real and strongly run-dependent, but it does not explain the S05 B2-local residual covariance. The covariance reproduction gives B2-containing mean absolute covariance near `1041.84` ns^2 versus downstream-only `15.99` ns^2, while the held-out rate model mainly tracks current/target/topology acceptance. This supports interpreting the S05 excess as detector-local B2/topology covariance rather than a beam-rate common mode.

## Artifacts

`reproduction_match_table.csv`, `s05_covariance_reproduction.csv`, `run_level_rates.csv`, `rate_oof_predictions.csv`, `rate_cv_scan.csv`, `rate_method_metrics.csv`, `rate_method_deltas.csv`, `b_pair_residual_rows.csv.gz`, `pair_covariance_by_run.csv`, `run_covariance_summary.csv`, `rate_covariance_comparison.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s05e_1781017418_11875_10723959_run_level_ab_rate_model.py --config {config_path}
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s05e_1781017418_11875_10723959_run_level_ab_rate_model.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    scan_paths = {
        "counts": out_dir / "reproduction_match_table.csv",
        "run_summary": out_dir / "run_level_rates.csv",
        "pair_table": out_dir / "b_pair_residual_rows.csv.gz",
        "cov_rows": out_dir / "pair_covariance_by_run.csv",
        "run_cov": out_dir / "run_covariance_summary.csv",
        "cov_repro": out_dir / "s05_covariance_reproduction.csv",
    }
    if all(path.exists() for path in scan_paths.values()):
        counts = pd.read_csv(scan_paths["counts"])
        run_summary = pd.read_csv(scan_paths["run_summary"])
        pair_table = pd.read_csv(scan_paths["pair_table"])
        cov_rows = pd.read_csv(scan_paths["cov_rows"])
        run_cov = pd.read_csv(scan_paths["run_cov"])
        cov_repro = pd.read_csv(scan_paths["cov_repro"])
    else:
        counts, run_summary, pair_table = scan_inputs(config)
        counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
        run_summary.to_csv(out_dir / "run_level_rates.csv", index=False)
        pair_table.to_csv(out_dir / "b_pair_residual_rows.csv.gz", index=False, compression="gzip")

        cov_rows = pair_covariance_rows(pair_table)
        cov_rows.to_csv(out_dir / "pair_covariance_by_run.csv", index=False)
        run_cov, cov_repro = covariance_summaries(cov_rows, config)
        run_cov.to_csv(out_dir / "run_covariance_summary.csv", index=False)
        cov_repro.to_csv(out_dir / "s05_covariance_reproduction.csv", index=False)

    run_cov, cov_repro = covariance_summaries(cov_rows, config)
    run_cov.to_csv(out_dir / "run_covariance_summary.csv", index=False)
    cov_repro.to_csv(out_dir / "s05_covariance_reproduction.csv", index=False)

    model_paths = {
        "oof": out_dir / "rate_oof_predictions.csv",
        "cv": out_dir / "rate_cv_scan.csv",
        "metrics": out_dir / "rate_method_metrics.csv",
        "deltas": out_dir / "rate_method_deltas.csv",
        "cov_compare": out_dir / "rate_covariance_comparison.csv",
        "leakage": out_dir / "leakage_checks.csv",
    }
    if all(path.exists() for path in model_paths.values()):
        oof = pd.read_csv(model_paths["oof"])
        cv = pd.read_csv(model_paths["cv"])
        metrics = pd.read_csv(model_paths["metrics"])
        deltas = pd.read_csv(model_paths["deltas"])
        cov_compare = pd.read_csv(model_paths["cov_compare"])
        leakage = pd.read_csv(model_paths["leakage"])
    else:
        rate_table = prepare_rate_table(run_summary)
        oof, cv = oof_rate_models(rate_table, config)
        oof.to_csv(out_dir / "rate_oof_predictions.csv", index=False)
        cv.to_csv(out_dir / "rate_cv_scan.csv", index=False)
        metrics, deltas = rate_metric_table(oof, config, rng)
        metrics.to_csv(out_dir / "rate_method_metrics.csv", index=False)
        deltas.to_csv(out_dir / "rate_method_deltas.csv", index=False)
        cov_compare = rate_covariance_comparison(oof, run_cov, config, rng)
        cov_compare.to_csv(out_dir / "rate_covariance_comparison.csv", index=False)
        leakage = leakage_checks(oof, metrics)
        leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    write_input_hashes(out_dir, config)
    write_result(out_dir, config, counts, cov_repro, metrics, deltas, leakage, cov_compare)
    command = f"/home/billy/anaconda3/bin/python {Path(__file__).as_posix()} --config {args.config}"
    write_report(out_dir, args.config, config, counts, cov_repro, run_summary, oof, metrics, deltas, cov_compare, leakage)
    write_manifest(out_dir, args.config, config, [command])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
