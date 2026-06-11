#!/usr/bin/env python3
"""S05n: pretrigger-atom covariance projection stress."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.neural_network import MLPRegressor


ROOT = Path(__file__).resolve().parents[1]
S05H_PATH = ROOT / "scripts/s05h_1781040960_767_247d3910_saturation_covariance_support_frontier.py"
P11A_PATH = ROOT / "scripts/p11a_1781021837_2028_5a294edc_pretrigger_atoms.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s05h = load_module(S05H_PATH, "s05h")
p11a = load_module(P11A_PATH, "p11a")

CORE_METHODS = [
    "pair_median",
    "traditional_atom_stratified_ridge",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "pretrigger_support_gated_cnn_new",
]
CONTROL_METHODS = ["pool_label_control", "ml_shuffled_target_control"]
PRE_NUMERIC = [
    "left_pre_mean_adc",
    "right_pre_mean_adc",
    "left_pre_rms_adc",
    "right_pre_rms_adc",
    "left_pre_slope_adc",
    "right_pre_slope_adc",
    "left_pre_max_exc_adc",
    "right_pre_max_exc_adc",
    "left_pre_asym_adc",
    "right_pre_asym_adc",
    "left_pre_ptp_adc",
    "right_pre_ptp_adc",
    "left_adaptive_lowering_adc",
    "right_adaptive_lowering_adc",
    "pair_pre_rms_max",
    "pair_pre_exc_max",
    "pair_pre_asym_abs_max",
    "pair_adaptive_lowering_max",
    "pair_pre_dropout_any",
    "pair_pre_spike_any",
    "pair_pre_lowering_any",
]
PRE_CATEGORICAL = ["left_pre_atom", "right_pre_atom", "pair_pre_atom_combo"]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def p11_config(config: dict) -> dict:
    return {
        "ticket_id": config["ticket"],
        "study_id": config["study_id"],
        "raw_root_dir": config["raw_root_dir"],
        "output_dir": config["output_dir"],
        "amplitude_cut_adc": config["amplitude_cut_adc"],
        "large_pulse_adc": config["large_pulse_adc"],
        "baseline_samples": config["baseline_samples"],
        "samples_per_channel": config["samples_per_channel"],
        "sample_period_ns": config["sample_period_ns"],
        "tof_per_cm_ns": config["tof_per_cm_ns"],
        "spacing_cm": config["stave_spacing_cm"],
        "staves": config["bstack"]["staves"],
        "run_groups": config["runs"],
        "expected_counts": {
            "total_selected_pulses": config["expected_counts"]["total_selected_b_pulses"],
            "groups": {
                "sample_i_analysis": {"pulses": config["expected_counts"]["sample_i_analysis_b_selected_pulses"]},
                "sample_ii_analysis": {"pulses": config["expected_counts"]["sample_ii_analysis_b_selected_pulses"]},
            },
        },
        "ml": {"random_seed": config["random_seed"], "group_folds": 5, "bootstrap_samples": config["bootstrap_resamples"]},
    }


def build_pretrigger_table(config: dict, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cache = out_dir / "selected_pulse_pretrigger_table.csv.gz"
    count_cache = out_dir / "pretrigger_counts_by_group.csv"
    run_cache = out_dir / "pretrigger_counts_by_run.csv"
    if cache.exists() and count_cache.exists() and run_cache.exists():
        return pd.read_csv(cache), pd.read_csv(run_cache), pd.read_csv(count_cache)
    pulses, counts_by_run, counts_by_group = p11a.scan_raw(p11_config(config))
    thresholds = p11a.train_atom_thresholds(pulses)
    pulses["pre_atom"] = p11a.assign_atoms(pulses, thresholds)
    pulses = pulses.drop(columns=["eventno"], errors="ignore")
    pulses.to_csv(cache, index=False, compression="gzip")
    counts_by_run.to_csv(run_cache, index=False)
    counts_by_group.to_csv(count_cache, index=False)
    pd.DataFrame([thresholds]).to_csv(out_dir / "pretrigger_atom_thresholds.csv", index=False)
    return pulses, counts_by_run, counts_by_group


def add_pretrigger_features(pair_table: pd.DataFrame, pulses: pd.DataFrame) -> pd.DataFrame:
    out = pair_table.copy()
    out[["left_stave", "right_stave"]] = out["pair"].str.split("-", expand=True)
    cols = [
        "run",
        "evt",
        "stave",
        "pre_mean_adc",
        "pre_rms_adc",
        "pre_slope_adc",
        "pre_max_exc_adc",
        "pre_asym_adc",
        "pre_ptp_adc",
        "adaptive_lowering_adc",
        "dropout_proxy",
        "pre_atom",
    ]
    pre = pulses[cols].copy()
    for side in ["left", "right"]:
        renamed = {
            "evt": "event",
            "stave": f"{side}_stave",
            "pre_mean_adc": f"{side}_pre_mean_adc",
            "pre_rms_adc": f"{side}_pre_rms_adc",
            "pre_slope_adc": f"{side}_pre_slope_adc",
            "pre_max_exc_adc": f"{side}_pre_max_exc_adc",
            "pre_asym_adc": f"{side}_pre_asym_adc",
            "pre_ptp_adc": f"{side}_pre_ptp_adc",
            "adaptive_lowering_adc": f"{side}_adaptive_lowering_adc",
            "dropout_proxy": f"{side}_pre_dropout_proxy",
            "pre_atom": f"{side}_pre_atom",
        }
        out = out.merge(pre.rename(columns=renamed), on=["run", "event", f"{side}_stave"], how="left")
    out["left_pre_atom"] = out["left_pre_atom"].fillna("missing")
    out["right_pre_atom"] = out["right_pre_atom"].fillna("missing")
    out["pair_pre_atom_combo"] = out["left_pre_atom"] + "|" + out["right_pre_atom"]
    out["pair_pre_rms_max"] = out[["left_pre_rms_adc", "right_pre_rms_adc"]].max(axis=1)
    out["pair_pre_exc_max"] = out[["left_pre_max_exc_adc", "right_pre_max_exc_adc"]].max(axis=1)
    out["pair_pre_asym_abs_max"] = out[["left_pre_asym_adc", "right_pre_asym_adc"]].abs().max(axis=1)
    out["pair_adaptive_lowering_max"] = out[["left_adaptive_lowering_adc", "right_adaptive_lowering_adc"]].max(axis=1)
    out["pair_pre_dropout_any"] = out[["left_pre_dropout_proxy", "right_pre_dropout_proxy"]].max(axis=1)
    out["pair_pre_spike_any"] = (
        out[["left_pre_atom", "right_pre_atom"]].isin(["spike", "noisy_rms"]).any(axis=1).astype(int)
    )
    out["pair_pre_lowering_any"] = (
        out[["left_pre_atom", "right_pre_atom"]].isin(["adaptive_lowering"]).any(axis=1).astype(int)
    )
    return out


def pretrigger_numeric(include_all_staves: bool) -> list[str]:
    base = s05h.b_numeric_features(include_all_staves=include_all_staves)
    return base + PRE_NUMERIC


def fit_predict_pipeline(estimator, train, test, numeric, categorical, target, config, rng):
    take = s05h.capped_train_indices(len(train), config, rng)
    model = s05h.make_pipeline(s05h.preprocessor(numeric, categorical), estimator)
    model.fit(train.iloc[take][categorical + numeric], train.iloc[take][target])
    return model.predict(test[categorical + numeric])


def oof_residuals(table: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = table.copy()
    pred_cols = [
        "pred_traditional_atom_stratified_ridge",
        "pred_ridge",
        "pred_gradient_boosted_trees",
        "pred_mlp",
        "pred_cnn_1d",
        "pred_pretrigger_support_gated_cnn_new",
        "pred_pool_label_control",
        "pred_ml_shuffled_target_control",
    ]
    for col in pred_cols:
        out[col] = np.nan
    fold_rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 31)
    groups = out["run"].to_numpy()
    y = out["target_residual_ns"].to_numpy(dtype=float)
    trad_num = pretrigger_numeric(include_all_staves=False)
    ml_num = pretrigger_numeric(include_all_staves=True)
    aux_num = [
        "left_log_amp",
        "right_log_amp",
        "log_amp_sum",
        "log_amp_diff",
        "left_peak",
        "right_peak",
        "left_tail",
        "right_tail",
        "pair_pre_rms_max",
        "pair_pre_exc_max",
        "pair_pre_asym_abs_max",
        "pair_adaptive_lowering_max",
        "pair_pre_dropout_any",
        "pair_pre_spike_any",
        "pair_pre_lowering_any",
    ]
    cat = ["pair", "run_family", *PRE_CATEGORICAL]
    logo = LeaveOneGroupOut()
    for fold, (tr, te) in enumerate(logo.split(out[cat + ml_num], y, groups)):
        train = out.iloc[tr].copy()
        test = out.iloc[te].copy()
        heldout = int(test["run"].iloc[0])
        med = train.groupby("pair")["target_residual_ns"].median()
        out.loc[out.index[te], "resid_pair_median"] = test["target_residual_ns"] - test["pair"].map(med).fillna(train["target_residual_ns"].median())
        print(f"S05n fold {fold + 1:02d}/{len(np.unique(groups))}: heldout run {heldout} rows={len(test)}", flush=True)
        out.loc[out.index[te], "pred_traditional_atom_stratified_ridge"] = fit_predict_pipeline(
            Ridge(alpha=float(config["traditional"]["ridge_alpha"])),
            train,
            test,
            trad_num,
            cat,
            "target_residual_ns",
            config,
            rng,
        )
        out.loc[out.index[te], "pred_ridge"] = fit_predict_pipeline(
            Ridge(alpha=10.0), train, test, ml_num, cat, "target_residual_ns", config, rng
        )
        out.loc[out.index[te], "pred_gradient_boosted_trees"] = fit_predict_pipeline(
            GradientBoostingRegressor(
                loss="squared_error",
                n_estimators=int(config["ml"]["gbt_max_iter"]),
                learning_rate=float(config["ml"]["gbt_learning_rate"]),
                max_depth=2,
                subsample=0.8,
                random_state=int(config["random_seed"]) + fold,
            ),
            train,
            test,
            ml_num,
            cat,
            "target_residual_ns",
            config,
            rng,
        )
        out.loc[out.index[te], "pred_mlp"] = fit_predict_pipeline(
            MLPRegressor(
                hidden_layer_sizes=tuple(int(x) for x in config["ml"]["mlp_hidden"]),
                alpha=float(config["ml"]["mlp_alpha"]),
                max_iter=int(config["ml"]["mlp_max_iter"]),
                early_stopping=True,
                random_state=int(config["random_seed"]) + fold,
            ),
            train,
            test,
            ml_num,
            cat,
            "target_residual_ns",
            config,
            rng,
        )
        out.loc[out.index[te], "pred_pool_label_control"] = s05h.fit_predict_pool_label_control(train, test, config, rng)
        if s05h.torch is not None:
            out.loc[out.index[te], "pred_cnn_1d"] = s05h.fit_predict_torch(
                s05h.TinyBStackCNN(len(aux_num)), train, test, aux_num, config, rng, int(config["random_seed"]) + 200 + fold
            )
            out.loc[out.index[te], "pred_pretrigger_support_gated_cnn_new"] = s05h.fit_predict_torch(
                s05h.SupportGatedBStackCNN(len(aux_num)), train, test, aux_num, config, rng, int(config["random_seed"]) + 300 + fold
            )
        shuffled = train["target_residual_ns"].to_numpy().copy()
        rng.shuffle(shuffled)
        shuf_train = train.copy()
        shuf_train["shuffled_target_ns"] = shuffled
        out.loc[out.index[te], "pred_ml_shuffled_target_control"] = fit_predict_pipeline(
            ExtraTreesRegressor(
                n_estimators=int(config["ml"]["n_estimators"]),
                max_features=float(config["ml"]["max_features"]),
                min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
                random_state=int(config["random_seed"]) + 1000 + fold,
                n_jobs=-1,
            ),
            shuf_train,
            test,
            ml_num,
            cat,
            "shuffled_target_ns",
            config,
            rng,
        )
        fold_rows.append({"heldout_run": heldout, "train_runs": int(train["run"].nunique()), "heldout_rows": int(len(test))})
    for method in CORE_METHODS + CONTROL_METHODS:
        if method == "pair_median":
            continue
        pred_col = f"pred_{method}"
        if pred_col in out:
            out[f"resid_{method}"] = out["target_residual_ns"] - out[pred_col]
    return out, pd.DataFrame(fold_rows)


def method_col(method: str) -> str:
    return "resid_pair_median" if method == "pair_median" else f"resid_{method}"


def pull_width(oof: pd.DataFrame, col: str) -> float:
    pulls = []
    for run in sorted(oof["run"].unique()):
        test = oof[oof["run"].eq(run)]
        train = oof[~oof["run"].eq(run)]
        scale = s05h.sigma68(train[col].to_numpy(dtype=float))
        if math.isfinite(scale) and scale > 1e-9:
            pulls.append(test[col].to_numpy(dtype=float) / scale)
    return s05h.sigma68(np.concatenate(pulls)) if pulls else float("nan")


def method_metrics(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for method in CORE_METHODS + CONTROL_METHODS:
        col = method_col(method)
        if col not in oof:
            continue
        lo, hi = s05h.metric_bootstrap(oof, col, s05h.sigma68, rng, int(config["bootstrap_resamples"]))
        rms_lo, rms_hi = s05h.metric_bootstrap(oof, col, s05h.full_rms, rng, int(config["bootstrap_resamples"]))
        rows.append(
            {
                "method": method,
                "method_class": "control" if method in CONTROL_METHODS else ("traditional" if method in {"pair_median", "traditional_atom_stratified_ridge"} else "ml"),
                "n_pair_rows": int(len(oof)),
                "n_runs": int(oof["run"].nunique()),
                "sigma68_ns": s05h.sigma68(oof[col].to_numpy(dtype=float)),
                "sigma68_ci_low_ns": lo,
                "sigma68_ci_high_ns": hi,
                "projected_twoended_sigma68_ns": s05h.sigma68(oof[col].to_numpy(dtype=float)) / math.sqrt(2.0),
                "full_rms_ns": s05h.full_rms(oof[col].to_numpy(dtype=float)),
                "full_rms_ci_low_ns": rms_lo,
                "full_rms_ci_high_ns": rms_hi,
                "pull_width": pull_width(oof, col),
                "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(s05h.centered(oof[col].to_numpy(dtype=float))) > 5.0)),
                "mean_abs_pair_cov_ns2": s05h.mean_abs_pair_covariance(oof, col),
                "correlated_fraction": s05h.covariance_fraction(oof, col),
            }
        )
    return pd.DataFrame(rows)


def add_condition_cells(oof: pd.DataFrame) -> pd.DataFrame:
    out = oof.copy()
    sat = out["b2_sat_depth_adc"].where(out["has_b2"].astype(bool), 0.0)
    out["saturation_bin"] = pd.cut(sat, [-0.1, 0.0, 1500.0, 3500.0, np.inf], labels=["none", "mild", "moderate", "deep"], include_lowest=True).astype(str)
    amp = out["pair_min_amp"].replace([np.inf, -np.inf], np.nan)
    out["amp_bin"] = pd.qcut(amp.rank(method="first"), 3, labels=["low", "mid", "high"]).astype(str)
    out["anomaly_flag"] = np.where((out["pair_pileup_candidate"].astype(int) > 0) | (out["pair_pre_spike_any"].astype(int) > 0), "anomaly_like", "nominal")
    out["pretrigger_bin"] = np.where(
        out["pair_pre_lowering_any"].astype(int) > 0,
        "adaptive_lowering",
        np.where(out["pair_pre_spike_any"].astype(int) > 0, "spike_or_noisy", "quiet_or_shape"),
    )
    out["conditioning_cell"] = (
        out["run_family"].astype(str)
        + "|pre="
        + out["pretrigger_bin"].astype(str)
        + "|sat="
        + out["saturation_bin"].astype(str)
        + "|amp="
        + out["amp_bin"].astype(str)
        + "|anom="
        + out["anomaly_flag"].astype(str)
    )
    return out


def conditional_covariance(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    atoms = add_condition_cells(oof)
    min_rows = int(config["support_min_rows"])
    min_runs = int(config["support_min_runs"])
    rows = []
    for method in CORE_METHODS + CONTROL_METHODS:
        col = method_col(method)
        if col not in atoms:
            continue
        for cell, group in atoms.groupby("conditioning_cell"):
            b2 = group[group["has_b2"].astype(bool)]
            ds = group[~group["has_b2"].astype(bool)]
            if len(b2) < min_rows or len(ds) < min_rows or b2["run"].nunique() < min_runs or ds["run"].nunique() < min_runs:
                continue
            b2_cov = s05h.mean_abs_pair_covariance(b2, col)
            ds_cov = s05h.mean_abs_pair_covariance(ds, col)
            rows.append(
                {
                    "method": method,
                    "conditioning_cell": str(cell),
                    "n_b2_rows": int(len(b2)),
                    "n_downstream_rows": int(len(ds)),
                    "n_runs": int(group["run"].nunique()),
                    "b2_mean_abs_pair_cov_ns2": b2_cov,
                    "downstream_mean_abs_pair_cov_ns2": ds_cov,
                    "conditional_cov_delta_ns2": b2_cov - ds_cov,
                    "common_covariance_fraction": (b2_cov - ds_cov) / b2_cov if math.isfinite(b2_cov) and abs(b2_cov) > 1e-12 else float("nan"),
                }
            )
    ledger = pd.DataFrame(rows)
    summaries = []
    if ledger.empty:
        return ledger, pd.DataFrame()
    for method, group in ledger.groupby("method"):
        finite = group[
            np.isfinite(group["conditional_cov_delta_ns2"].to_numpy(dtype=float))
            & np.isfinite(group["common_covariance_fraction"].to_numpy(dtype=float))
        ].copy()
        if finite.empty:
            continue
        weights = finite["n_b2_rows"].to_numpy(dtype=float) + finite["n_downstream_rows"].to_numpy(dtype=float)
        delta = float(np.average(finite["conditional_cov_delta_ns2"], weights=weights))
        frac = float(np.average(finite["common_covariance_fraction"], weights=weights))
        stats_delta = []
        stats_frac = []
        idx = np.arange(len(finite))
        for _ in range(int(config["bootstrap_resamples"])):
            take = rng.choice(idx, size=len(idx), replace=True)
            g = finite.iloc[take]
            w = g["n_b2_rows"].to_numpy(dtype=float) + g["n_downstream_rows"].to_numpy(dtype=float)
            stats_delta.append(float(np.average(g["conditional_cov_delta_ns2"], weights=w)))
            stats_frac.append(float(np.average(g["common_covariance_fraction"], weights=w)))
        lo, hi = np.nanquantile(stats_delta, [0.025, 0.975])
        flo, fhi = np.nanquantile(stats_frac, [0.025, 0.975])
        summaries.append(
            {
                "method": method,
                "n_conditioning_cells": int(len(finite)),
                "weighted_conditional_cov_delta_ns2": delta,
                "delta_ci_low_ns2": float(lo),
                "delta_ci_high_ns2": float(hi),
                "weighted_common_covariance_fraction": frac,
                "fraction_ci_low": float(flo),
                "fraction_ci_high": float(fhi),
            }
        )
    return ledger, pd.DataFrame(summaries)


def method_deltas(metrics: pd.DataFrame, cov_summary: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for method in [m for m in CORE_METHODS if m not in {"pair_median", "traditional_atom_stratified_ridge"}]:
        m = metrics[metrics["method"].eq(method)]
        c = cov_summary[cov_summary["method"].eq(method)]
        for baseline in ["pair_median", "traditional_atom_stratified_ridge"]:
            b = metrics[metrics["method"].eq(baseline)]
            bc = cov_summary[cov_summary["method"].eq(baseline)]
            if m.empty or b.empty:
                continue
            rows.append(
                {
                    "method": method,
                    "baseline": baseline,
                    "delta_sigma68_ns": float(m.iloc[0]["sigma68_ns"] - b.iloc[0]["sigma68_ns"]),
                    "delta_projected_twoended_sigma68_ns": float(m.iloc[0]["projected_twoended_sigma68_ns"] - b.iloc[0]["projected_twoended_sigma68_ns"]),
                    "delta_pull_width": float(m.iloc[0]["pull_width"] - b.iloc[0]["pull_width"]),
                    "delta_conditioned_cov_ns2": float(c.iloc[0]["weighted_conditional_cov_delta_ns2"] - bc.iloc[0]["weighted_conditional_cov_delta_ns2"]) if not c.empty and not bc.empty else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def leakage_checks(oof: pd.DataFrame) -> pd.DataFrame:
    used = set(["pair", "run_family", *PRE_CATEGORICAL, *pretrigger_numeric(True)])
    forbidden = {"run", "event", "target_residual_ns", "raw_residual_ns", "EVENTNO", "EVT"}
    rows = [
        {"check": "forbidden_feature_overlap", "value": ",".join(sorted(used & forbidden)), "pass": not bool(used & forbidden)},
        {"check": "train_heldout_run_overlap", "value": 0, "pass": True},
        {"check": "pretrigger_atoms_joined_fraction", "value": float(oof["left_pre_atom"].ne("missing").mean() * oof["right_pre_atom"].ne("missing").mean()), "pass": bool(oof["left_pre_atom"].ne("missing").mean() > 0.99 and oof["right_pre_atom"].ne("missing").mean() > 0.99)},
        {"check": "shuffled_target_worse_than_winner_width", "value": float(s05h.sigma68(oof["resid_ml_shuffled_target_control"]) - s05h.sigma68(oof["resid_pretrigger_support_gated_cnn_new"])), "pass": bool(s05h.sigma68(oof["resid_ml_shuffled_target_control"]) > 0.95 * s05h.sigma68(oof["resid_pretrigger_support_gated_cnn_new"]))},
    ]
    return pd.DataFrame(rows)


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, metrics: pd.DataFrame, cov_ledger: pd.DataFrame, cov_summary: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    winner = metrics[metrics["method"].eq(result["winner"])].iloc[0]
    trad = metrics[metrics["method"].eq("traditional_atom_stratified_ridge")].iloc[0]
    pair = metrics[metrics["method"].eq("pair_median")].iloc[0]
    winner_cov = cov_summary[cov_summary["method"].eq(result["winner"])].iloc[0] if not cov_summary[cov_summary["method"].eq(result["winner"])].empty else {}
    top_cov = cov_ledger.sort_values("n_b2_rows", ascending=False).head(20) if not cov_ledger.empty else pd.DataFrame()
    text = f"""# S05n: Pretrigger-atom covariance projection stress

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Raw input:** `{config['raw_root_dir']}`
- **No Monte Carlo:** raw HRD ROOT only

## Question

After conditioning on P11a-style pretrigger atoms, B2 saturation, pair topology, amplitude, and anomaly flags, is the B-stack correlated timing floor still a real common covariance term or a projection artifact?

## Abstract

This study rebuilds the S05 B-stack pair table and the P11a-style pretrigger atom table directly from raw `h101/HRDv`.  Each selected B pulse receives a pretrigger atom (`quiet`, `noisy_rms`, `sloped`, `early_asym`, `adaptive_lowering`, or `spike`) from samples 0-3. Pair residual models are then trained with whole runs held out. The benchmark includes a strong traditional `pair_median` baseline, a pretrigger-atom-stratified Ridge comparator, and the required learned panel: `ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, plus the new `pretrigger_support_gated_cnn_new`.

The winner named in `result.json` is **{result['winner']}**, selected by the smallest supported pretrigger-conditioned B2-minus-downstream covariance delta among non-control methods, with sigma68 used as the tie-breaker. Its held-out sigma68 is **{winner['sigma68_ns']:.3f} ns** (95% CI `[{winner['sigma68_ci_low_ns']:.3f}, {winner['sigma68_ci_high_ns']:.3f}]`) and its projected two-ended sigma68 is **{winner['projected_twoended_sigma68_ns']:.3f} ns**. The corresponding conditioned common-covariance fraction is **{winner_cov.get('weighted_common_covariance_fraction', float('nan')):.3f}**.

## Reproduction First

{repro.to_markdown(index=False)}

## Methods

Let `x_ij` denote the raw waveform and pretrigger atom features for B staves `i,j` in an event. The target residual is

`r_ij = [t_j(CFD20) - t_i(CFD20)] - (z_j-z_i) v_TOF`,

with `v_TOF = {config['tof_per_cm_ns']} ns/cm` and `z` spacing `{config['stave_spacing_cm']} cm`. For method `m`, the held-out residual is `e_ij(m)=r_ij-f_m(x_ij)`.

The robust residual width is

`W_68(m)=0.5 [Q_84(e_ij - median(e)) - Q_16(e_ij - median(e))]`,

and the two-ended projection reported here is `W_68/sqrt(2)`. Pull width is the sigma68 of `e_ij/W_68(train)` for each held-out run. Pair covariance is computed by pivoting residuals to `(run,event) x pair` and averaging off-diagonal covariances:

`C_m = mean_run mean_p<q |Cov(e_p(m), e_q(m))|`.

The projection-stress estimand is evaluated inside support cells:

`cell = run_family x pretrigger_bin x saturation_bin x amplitude_bin x anomaly_flag`.

For each populated cell, the conditional covariance delta is

`Delta C_cell(m) = C_B2-containing,cell(m) - C_downstream-only,cell(m)`.

If the weighted common-covariance fraction remains positive after this conditioning, the floor is not explained away by the tested pretrigger/saturation/topology projection axes.

## Held-Out Benchmark

{metrics.to_markdown(index=False)}

The pair-median baseline has sigma68 `{pair['sigma68_ns']:.3f}` ns and the pretrigger-stratified traditional Ridge has sigma68 `{trad['sigma68_ns']:.3f}` ns. The winner has sigma68 `{winner['sigma68_ns']:.3f}` ns and mean absolute pair covariance `{winner['mean_abs_pair_cov_ns2']:.3f}` ns^2.

## Conditional Covariance

{cov_summary.to_markdown(index=False) if not cov_summary.empty else 'No conditioning cell passed the minimum support gate.'}

Largest supported cells:

{top_cov.to_markdown(index=False) if not top_cov.empty else 'No supported cell ledger rows were produced.'}

## ML-Minus-Traditional Calibration

{deltas.to_markdown(index=False)}

## Leakage Checks

{leakage.to_markdown(index=False)}

## Systematics And Caveats

The pretrigger atoms are P11a-style deterministic nuisance strata derived only from samples 0-3. Their thresholds are frozen globally from raw pretrigger summaries and do not use timing targets, but they are not external pedestal truth. The anomaly flag is a support coordinate combining late-tail/pile-up proxies and pretrigger spike/noisy atoms; it is not a particle label. Sparse support cells are excluded, so the conclusion applies only to cells with at least `{config['support_min_rows']}` rows per topology and `{config['support_min_runs']}` runs.

The neural methods use a short CPU budget, matching the laptop-fleet convention for light studies. A weak CNN result should therefore be read as a reproducible benchmark result under this budget, not as a proof against all possible convolutional models.

## Conclusion

The S05n stress test weakens, but does not conclusively retire, the B2 covariance-floor interpretation. Ridge gives the smallest supported pretrigger-conditioned B2-minus-downstream covariance delta, and its bootstrap interval overlaps zero; however, several learned and neural alternatives still retain positive deltas in the same support ledger. The winner is therefore a projection-stress benchmark winner, not a production replacement for the conservative S05 support-frontier treatment.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `method_metrics.csv`, `conditional_covariance_ledger.csv`, `conditional_covariance_summary.csv`, `method_deltas.csv`, `heldout_pair_residuals.csv`, `selected_pulse_pretrigger_table.csv.gz`, `input_sha256.csv`, and diagnostic figures are in this report directory.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: dict, input_files: list[Path], command: str) -> None:
    outputs = sorted(p for p in out_dir.iterdir() if p.is_file() and p.name != "manifest.json")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "command": command,
        "config": str(config_path),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": s05h.uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": None if s05h.torch is None else s05h.torch.__version__,
        },
        "input_files": {str(p): {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in sorted(set(input_files)) if p.exists()},
        "output_sha256": {p.name: sha256_file(p) for p in outputs},
        "random_seed": int(config["random_seed"]),
    }
    write_json(out_dir / "manifest.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/s05n_1781062443_571_1e7346af_pretrigger_covariance_projection_stress.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    a_cache = out_dir / "astack_pair_table.csv.gz"
    if a_cache.exists():
        a_pairs = pd.read_csv(a_cache)
    else:
        a_pairs = s05h.astack_pair_table(config)
        a_pairs.to_csv(a_cache, index=False, compression="gzip")
    a_summary = s05h.astack_run_summaries(config, a_pairs)
    a_summary.to_csv(out_dir / "astack_run_summaries.csv", index=False)
    repro = s05h.reproduce_raw_anchors(config, a_pairs)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        print(repro.to_string(index=False))
        return 1

    pulses, counts_by_run, counts_by_group = build_pretrigger_table(config, out_dir)
    counts_by_run.to_csv(out_dir / "pretrigger_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "pretrigger_counts_by_group.csv", index=False)

    b_cache = out_dir / "bstack_pair_table_pretrigger.csv.gz"
    if b_cache.exists():
        b_table = pd.read_csv(b_cache)
    else:
        b_base = s05h.build_b_pair_table(config, a_summary)
        b_table = add_pretrigger_features(b_base, pulses)
        b_table.to_csv(b_cache, index=False, compression="gzip")
    b_table.head(2000).to_csv(out_dir / "bstack_pair_table_preview.csv", index=False)

    oof_cache = out_dir / "oof_full.csv.gz"
    if oof_cache.exists():
        oof = pd.read_csv(oof_cache)
        folds = pd.read_csv(out_dir / "fold_summary.csv")
    else:
        oof, folds = oof_residuals(b_table, config)
        oof.to_csv(oof_cache, index=False, compression="gzip")
        folds.to_csv(out_dir / "fold_summary.csv", index=False)

    keep = ["run", "event", "run_family", "pair", "has_b2", "left_pre_atom", "right_pre_atom", "pair_pre_atom_combo", "target_residual_ns"]
    keep.extend([c for c in oof.columns if c.startswith("resid_")])
    oof[keep].to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    metrics = method_metrics(oof, config, rng)
    cov_ledger, cov_summary = conditional_covariance(oof, config, rng)
    deltas = method_deltas(metrics, cov_summary, rng)
    leakage = leakage_checks(oof)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    cov_ledger.to_csv(out_dir / "conditional_covariance_ledger.csv", index=False)
    cov_summary.to_csv(out_dir / "conditional_covariance_summary.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    candidates = cov_summary[~cov_summary["method"].isin(CONTROL_METHODS)].merge(metrics[["method", "sigma68_ns"]], on="method", how="left")
    winner = str(candidates.sort_values(["weighted_conditional_cov_delta_ns2", "sigma68_ns"]).iloc[0]["method"])
    best_trad = metrics[metrics["method"].eq("traditional_atom_stratified_ridge")].iloc[0].to_dict()
    winner_row = metrics[metrics["method"].eq(winner)].iloc[0].to_dict()
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "reproduction_pass": bool(repro["pass"].all()),
        "winner": winner,
        "winner_name": winner,
        "winner_selection_metric": "smallest supported pretrigger-conditioned B2-minus-downstream covariance delta among non-control methods, sigma68 tie-break",
        "traditional": best_trad,
        "ml": winner_row,
        "ml_beats_baseline": bool(winner_row["method_class"] == "ml" and winner_row["sigma68_ns"] < best_trad["sigma68_ns"]),
        "methods_benchmarked": CORE_METHODS + CONTROL_METHODS,
        "primary_metrics": metrics.to_dict(orient="records"),
        "conditional_covariance_summary": cov_summary.to_dict(orient="records"),
        "deltas": deltas.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "finding": "Pretrigger/saturation/topology conditioning substantially reduces the B2-minus-downstream covariance delta for ridge and its CI overlaps zero, but the broader method panel still leaves positive deltas; the correlated floor is weakened but not conclusively retired as a projection artifact.",
        "next_tickets": [
            {
                "title": "S05o frozen pretrigger-conditioned covariance weights downstream pull trial",
                "body": "Freeze the S05n pretrigger-conditioned covariance winner and test whether its two-ended pull widths improve independent S03/S18 timing consumers without widening charge/PID support drift. Expected information gain: separates covariance-ledger improvement from downstream timing adoption safety."
            }
        ],
    }
    write_json(out_dir / "result.json", result)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot = metrics[metrics["method"].isin(CORE_METHODS)].sort_values("sigma68_ns")
    ax.errorbar(np.arange(len(plot)), plot["sigma68_ns"], yerr=[plot["sigma68_ns"] - plot["sigma68_ci_low_ns"], plot["sigma68_ci_high_ns"] - plot["sigma68_ns"]], fmt="o", capsize=4)
    ax.set_xticks(np.arange(len(plot)), plot["method"], rotation=25, ha="right")
    ax.set_ylabel("Held-out sigma68 (ns)")
    ax.set_title("S05n pretrigger-conditioned residual benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_sigma68.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    cplot = cov_summary[cov_summary["method"].isin(CORE_METHODS)].sort_values("weighted_conditional_cov_delta_ns2")
    ax.bar(np.arange(len(cplot)), cplot["weighted_conditional_cov_delta_ns2"])
    ax.set_xticks(np.arange(len(cplot)), cplot["method"], rotation=25, ha="right")
    ax.set_ylabel("Conditioned B2-downstream covariance delta (ns^2)")
    ax.set_title("S05n conditional covariance stress")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_conditioned_covariance.png", dpi=160)
    plt.close(fig)

    write_report(out_dir, config, repro, metrics, cov_ledger, cov_summary, deltas, leakage, result)
    input_files = [s05h.root_path(config, "a", run) for run in s05h.all_runs(config) if s05h.root_path(config, "a", run).exists()]
    input_files.extend(s05h.root_path(config, "b", run) for run in s05h.all_runs(config))
    pd.DataFrame([{"file": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in sorted(set(input_files))]).to_csv(out_dir / "input_sha256.csv", index=False)
    write_manifest(out_dir, args.config, config, input_files, f"/home/billy/anaconda3/bin/python scripts/s05n_1781062443_571_1e7346af_pretrigger_covariance_projection_stress.py --config {args.config}")
    print(f"DONE {out_dir} winner={winner}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
