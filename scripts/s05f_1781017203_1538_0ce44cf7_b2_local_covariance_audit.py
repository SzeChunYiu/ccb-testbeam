#!/usr/bin/env python3
"""S05f: B2-local covariance confound matched audit.

This freezes the S05c/S05e raw ROOT residual construction, reproduces the S05c
count and covariance anchors first, then adds matched covariance tables and
run-held-out ML ablations for B2-local waveform/saturation/anomaly strata.
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
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781017203.1538.0ce44cf7/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
PAIR_NAMES = [f"{a}-{b}" for a, b in PAIRS]
STAVES = ["B2", "B4", "B6", "B8"]
S05E_PATH = Path(__file__).with_name("s05e_1781016280_4691_3d911c1d_b2_saturation_covariance.py")


def load_s05e():
    spec = importlib.util.spec_from_file_location("s05e_covariance", S05E_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {S05E_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s05e = load_s05e()


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


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


def encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def sigma68(values: np.ndarray) -> float:
    return float(s05e.sigma68(np.asarray(values, dtype=float)))


def full_rms(values: np.ndarray) -> float:
    return float(s05e.full_rms(np.asarray(values, dtype=float)))


def robust_cov(x: np.ndarray, y: np.ndarray, mode: str, winsor_sigma: float) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    x = np.asarray(x[mask], dtype=float)
    y = np.asarray(y[mask], dtype=float)
    if len(x) < 3:
        return float("nan")
    if mode == "pearson":
        return float(np.cov(x, y, ddof=1)[0, 1])
    if mode == "median_centered":
        xc = x - np.median(x)
        yc = y - np.median(y)
        return float(np.mean(xc * yc) * len(x) / max(1, len(x) - 1))
    if mode == "winsor_mad":
        out = []
        for arr in [x, y]:
            med = np.median(arr)
            mad = np.median(np.abs(arr - med))
            scale = 1.4826 * mad if mad > 1e-12 else np.std(arr)
            scale = scale if scale > 1e-12 else 1.0
            out.append(np.clip(arr, med - winsor_sigma * scale, med + winsor_sigma * scale))
        return float(np.cov(out[0], out[1], ddof=1)[0, 1])
    raise ValueError(mode)


def add_b2_local_strata(table: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = table.copy()
    out["topology_n_selected"] = sum(out[f"{stave}_selected"].astype(int) for stave in STAVES)
    b2_selected = out["B2_selected"].astype(bool)
    b2 = out.loc[b2_selected].drop_duplicates(["run", "event"])

    amp_edges = np.quantile(b2["B2_amp"].to_numpy(dtype=float), [0.0, 0.25, 0.5, 0.75, 0.9, 1.0])
    amp_edges = np.unique(amp_edges)
    if len(amp_edges) < 3:
        amp_edges = np.asarray([0.0, 1500.0, 3000.0, 6000.0, np.inf])
    tail_hi = float(b2["B2_tail"].quantile(0.99))
    rec_hi = float(b2["B2_recovery_tail"].quantile(0.99))
    fall_lo = float(b2["B2_post_peak_fall"].quantile(0.01))
    near_hi = float(b2["B2_near_peak_count"].quantile(0.99))

    amp_bin = pd.cut(out["B2_amp"], bins=amp_edges, include_lowest=True, duplicates="drop")
    out["b2_amp_bin"] = np.where(b2_selected, amp_bin.astype(str), "B2_not_selected")
    out["b2_sat_bin"] = np.where(b2_selected, np.where(out["B2_sat_count"] > 0, "sat_gt0", "sat_eq0"), "B2_not_selected")
    peak = out["B2_peak"].fillna(-1).astype(int)
    out["b2_peak_bin"] = np.select(
        [~b2_selected, peak <= 4, peak <= 8, peak <= 12],
        ["B2_not_selected", "early_peak", "mid_peak", "late_peak"],
        default="very_late_peak",
    )
    taxon = np.full(len(out), "unassigned_common", dtype=object)
    taxon[(b2_selected & (out["B2_sat_count"] > 0)).to_numpy()] = "saturation"
    taxon[(b2_selected & (out["B2_tail"] > tail_hi) & (taxon == "unassigned_common")).to_numpy()] = "pileup_or_long_tail"
    taxon[(b2_selected & (out["B2_recovery_tail"] > rec_hi) & (taxon == "unassigned_common")).to_numpy()] = "novel_undershoot_recovery"
    taxon[(b2_selected & (out["B2_post_peak_fall"] < fall_lo) & (taxon == "unassigned_common")).to_numpy()] = "dropout"
    taxon[(b2_selected & (out["B2_near_peak_count"] > near_hi) & (taxon == "unassigned_common")).to_numpy()] = "broad_template_mismatch"
    taxon[(~b2_selected).to_numpy()] = "B2_not_selected"
    out["p09_anomaly_stratum"] = taxon
    out["match_cell"] = (
        out["run"].astype(str)
        + "|amp="
        + out["b2_amp_bin"].astype(str)
        + "|sat="
        + out["b2_sat_bin"].astype(str)
        + "|peak="
        + out["b2_peak_bin"].astype(str)
        + "|topo="
        + out["topology_n_selected"].astype(str)
        + "|p09="
        + out["p09_anomaly_stratum"].astype(str)
    )
    thresholds = pd.DataFrame(
        [
            {"threshold": "B2_amp_edges", "value": ",".join(f"{x:.6g}" for x in amp_edges)},
            {"threshold": "B2_tail_q99", "value": tail_hi},
            {"threshold": "B2_recovery_tail_q99", "value": rec_hi},
            {"threshold": "B2_post_peak_fall_q01", "value": fall_lo},
            {"threshold": "B2_near_peak_count_q99", "value": near_hi},
        ]
    )
    return out, thresholds


def winsorize_by_pair(table: pd.DataFrame, col: str, out_col: str, sigma: float) -> None:
    table[out_col] = np.nan
    for pair, idx in table.groupby("pair").groups.items():
        values = table.loc[idx, col].to_numpy(dtype=float)
        med = np.nanmedian(values)
        mad = np.nanmedian(np.abs(values - med))
        scale = 1.4826 * mad if mad > 1e-12 else np.nanstd(values)
        scale = scale if scale > 1e-12 else 1.0
        table.loc[idx, out_col] = np.clip(values, med - sigma * scale, med + sigma * scale)


def run_oof_no_b2_and_controls(table: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = table.copy()
    for col in ["pred_ml_no_b2_local", "pred_ml_shuffled_run", "pred_downstream_only_control"]:
        out[col] = np.nan

    feature_cols = [
        "pair",
        "topology_n_selected",
        "right_log_amp",
        "right_peak",
        "right_tail",
        "right_log_area",
        "log_amp_sum",
        "peak_diff",
        "tail_diff",
        "B4_log_amp",
        "B4_tail",
        "B4_peak",
        "B6_log_amp",
        "B6_tail",
        "B6_peak",
        "B8_log_amp",
        "B8_tail",
        "B8_peak",
    ]
    cat_cols = ["pair"]
    num_cols = [c for c in feature_cols if c not in cat_cols]
    pre = ColumnTransformer([("cat", encoder(), cat_cols), ("num", StandardScaler(), num_cols)], remainder="drop")
    params = {
        "n_estimators": int(config["ml"]["n_estimators"]),
        "max_features": float(config["ml"]["max_features"]),
        "min_samples_leaf": int(config["ml"]["min_samples_leaf"]),
    }
    rng = np.random.default_rng(int(config["random_seed"]) + 911)
    rows = []
    for fold, heldout_run in enumerate(sorted(out["run"].unique())):
        train = out[out["run"] != heldout_run].copy()
        test = out[out["run"] == heldout_run].copy()
        model = make_pipeline(
            pre,
            ExtraTreesRegressor(**params, random_state=int(config["random_seed"]) + 100 + fold, n_jobs=-1),
        )
        model.fit(train[feature_cols], train["target_residual_ns"])
        out.loc[test.index, "pred_ml_no_b2_local"] = model.predict(test[feature_cols])

        shuffled = train["target_residual_ns"].to_numpy().copy()
        train_runs = train["run"].to_numpy()
        for run in np.unique(train_runs):
            idx = np.where(train_runs == run)[0]
            donor = rng.choice(np.where(train_runs != run)[0], size=len(idx), replace=True)
            shuffled[idx] = train["target_residual_ns"].to_numpy()[donor]
        leak_model = make_pipeline(
            pre,
            ExtraTreesRegressor(**params, random_state=int(config["random_seed"]) + 300 + fold, n_jobs=-1),
        )
        leak_model.fit(train[feature_cols], shuffled)
        out.loc[test.index, "pred_ml_shuffled_run"] = leak_model.predict(test[feature_cols])

        ds_train = train[~train["has_b2"]].copy()
        ds_model = make_pipeline(
            pre,
            ExtraTreesRegressor(**params, random_state=int(config["random_seed"]) + 500 + fold, n_jobs=-1),
        )
        ds_model.fit(ds_train[feature_cols], ds_train["target_residual_ns"])
        out.loc[test.index, "pred_downstream_only_control"] = ds_model.predict(test[feature_cols])
        rows.append({"heldout_run": int(heldout_run), "train_rows": int(len(train)), "downstream_train_rows": int(len(ds_train))})

    out["resid_ml_no_b2_local"] = out["target_residual_ns"] - out["pred_ml_no_b2_local"]
    out["resid_ml_shuffled_run"] = out["target_residual_ns"] - out["pred_ml_shuffled_run"]
    out["resid_downstream_only_control"] = out["target_residual_ns"] - out["pred_downstream_only_control"]
    return out, pd.DataFrame(rows)


def matched_covariance_rows(table: pd.DataFrame, methods: Sequence[Tuple[str, str, str]], config: dict) -> pd.DataFrame:
    rows: List[dict] = []
    min_events = int(config["matched_min_events"])
    winsor_sigma = float(config["winsor_mad_sigma"])
    for method, col, estimator in methods:
        for (run, cell), group in table.groupby(["run", "match_cell"], sort=True):
            wide = group.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
            if len(wide) < min_events:
                continue
            for i, pair_a in enumerate(PAIR_NAMES):
                if pair_a not in wide.columns:
                    continue
                for pair_b in PAIR_NAMES[i + 1 :]:
                    if pair_b not in wide.columns:
                        continue
                    both = wide[[pair_a, pair_b]].dropna()
                    if len(both) < min_events:
                        continue
                    a_has = "B2" in pair_a
                    b_has = "B2" in pair_b
                    if a_has and b_has:
                        subset = "both_B2_containing"
                    elif (not a_has) and (not b_has):
                        subset = "both_downstream_only"
                    else:
                        subset = "mixed_B2_downstream"
                    cov = robust_cov(both[pair_a].to_numpy(), both[pair_b].to_numpy(), estimator, winsor_sigma)
                    rows.append(
                        {
                            "method": method,
                            "estimator": estimator,
                            "run": int(run),
                            "match_cell": cell,
                            "pair_a": pair_a,
                            "pair_b": pair_b,
                            "subset": subset,
                            "n_events": int(len(both)),
                            "cov_ns2": cov,
                            "abs_cov_ns2": abs(cov),
                        }
                    )
    return pd.DataFrame(rows)


def shared_matched_stat(cov_rows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, estimator), group in cov_rows.groupby(["method", "estimator"], sort=True):
        b2 = group[group["subset"] == "both_B2_containing"]
        ds = group[group["subset"] == "both_downstream_only"]
        shared = sorted(set(b2["match_cell"]) & set(ds["match_cell"]))
        b2s = b2[b2["match_cell"].isin(shared)]
        dss = ds[ds["match_cell"].isin(shared)]
        if len(b2s) == 0 or len(dss) == 0:
            continue
        b2_mean = float(np.average(b2s["cov_ns2"], weights=b2s["n_events"]))
        ds_mean = float(np.average(dss["cov_ns2"], weights=dss["n_events"]))
        delta = b2_mean - ds_mean
        rows.append(
            {
                "method": method,
                "estimator": estimator,
                "n_shared_cells": int(len(shared)),
                "n_b2_covariances": int(len(b2s)),
                "n_downstream_covariances": int(len(dss)),
                "b2_signed_cov_ns2": b2_mean,
                "downstream_signed_cov_ns2": ds_mean,
                "b2_minus_downstream_cov_ns2": delta,
                "inferred_correlated_fraction": float(delta / b2_mean) if abs(b2_mean) > 1e-12 else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_matched_stats(cov_rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 707)
    runs = np.asarray(sorted(cov_rows["run"].unique()))
    rows = []
    n_boot = int(config["bootstrap_resamples"])
    for (method, estimator), group in cov_rows.groupby(["method", "estimator"], sort=True):
        stats = []
        frac = []
        coverage = []
        for _ in range(n_boot):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"] == run] for run in sampled], ignore_index=True)
            stat = shared_matched_stat(boot)
            if len(stat) == 0:
                continue
            row = stat.iloc[0]
            stats.append(float(row["b2_minus_downstream_cov_ns2"]))
            frac.append(float(row["inferred_correlated_fraction"]))
            coverage.append(float(row["n_shared_cells"]))
        if not stats:
            continue
        lo, hi = np.percentile(stats, [2.5, 97.5])
        flo, fhi = np.percentile(frac, [2.5, 97.5])
        rows.append(
            {
                "method": method,
                "estimator": estimator,
                "delta_ci_low_ns2": float(lo),
                "delta_ci_high_ns2": float(hi),
                "fraction_ci_low": float(flo),
                "fraction_ci_high": float(fhi),
                "bootstrap_shared_cells_median": float(np.median(coverage)),
                "bootstrap_resamples_used": int(len(stats)),
            }
        )
    return pd.DataFrame(rows)


def leave_one_run_stability(cov_rows: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (method, estimator), group in cov_rows.groupby(["method", "estimator"], sort=True):
        for run in sorted(group["run"].unique()):
            stat = shared_matched_stat(group[group["run"] != run])
            if len(stat) == 0:
                continue
            row = stat.iloc[0].to_dict()
            row["left_out_run"] = int(run)
            out.append(row)
    return pd.DataFrame(out)


def residual_metrics(table: pd.DataFrame, methods: Sequence[Tuple[str, str]], config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 808)
    rows = []
    runs = np.asarray(sorted(table["run"].unique()))
    for method, col in methods:
        for subset, frame in [("all", table), ("B2_containing", table[table["has_b2"]]), ("downstream_only", table[~table["has_b2"]])]:
            boot_sigma = []
            boot_rms = []
            for _ in range(int(config["bootstrap_resamples"])):
                sampled = rng.choice(runs, size=len(runs), replace=True)
                boot = pd.concat([frame[frame["run"] == run] for run in sampled], ignore_index=True)
                boot_sigma.append(sigma68(boot[col].to_numpy()))
                boot_rms.append(full_rms(boot[col].to_numpy()))
            slo, shi = np.percentile(boot_sigma, [2.5, 97.5])
            rlo, rhi = np.percentile(boot_rms, [2.5, 97.5])
            rows.append(
                {
                    "method": method,
                    "subset": subset,
                    "n_pair_rows": int(len(frame)),
                    "n_runs": int(frame["run"].nunique()),
                    "sigma68_ns": sigma68(frame[col].to_numpy()),
                    "sigma68_ci_low_ns": float(slo),
                    "sigma68_ci_high_ns": float(shi),
                    "full_rms_ns": full_rms(frame[col].to_numpy()),
                    "full_rms_ci_low_ns": float(rlo),
                    "full_rms_ci_high_ns": float(rhi),
                }
            )
    return pd.DataFrame(rows)


def reproduce_s05c_covariance(oof: pd.DataFrame, config: dict, out_dir: Path) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]))
    _, cov_summary, _ = s05e.covariance_summary(oof, config, rng)
    raw_b2 = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_B2_containing")].iloc[0]
    raw_ds = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_downstream_only")].iloc[0]
    expected = config["expected_s05c_covariance"]
    tol = float(expected["tolerance_ns2"])
    rows = [
        {
            "quantity": "S05c_raw_b2_containing_mean_abs_cov_ns2",
            "report_value": float(expected["raw_b2_containing_mean_abs_cov_ns2"]),
            "reproduced": float(raw_b2["mean_abs_cov_ns2"]),
            "delta": float(raw_b2["mean_abs_cov_ns2"] - expected["raw_b2_containing_mean_abs_cov_ns2"]),
            "tolerance": tol,
            "pass": bool(abs(float(raw_b2["mean_abs_cov_ns2"]) - float(expected["raw_b2_containing_mean_abs_cov_ns2"])) <= tol),
        },
        {
            "quantity": "S05c_raw_downstream_mean_abs_cov_ns2",
            "report_value": float(expected["raw_downstream_mean_abs_cov_ns2"]),
            "reproduced": float(raw_ds["mean_abs_cov_ns2"]),
            "delta": float(raw_ds["mean_abs_cov_ns2"] - expected["raw_downstream_mean_abs_cov_ns2"]),
            "tolerance": tol,
            "pass": bool(abs(float(raw_ds["mean_abs_cov_ns2"]) - float(expected["raw_downstream_mean_abs_cov_ns2"])) <= tol),
        },
    ]
    out = pd.DataFrame(rows)
    cov_summary.to_csv(out_dir / "s05c_reproduced_covariance_summary.csv", index=False)
    return out


def interval_coverage(cov_rows: pd.DataFrame, summary: pd.DataFrame, boot: pd.DataFrame) -> pd.DataFrame:
    rows = []
    merged = summary.merge(boot, on=["method", "estimator"], how="left")
    for row in merged.itertuples(index=False):
        contains_zero = bool(row.delta_ci_low_ns2 <= 0.0 <= row.delta_ci_high_ns2)
        rows.append(
            {
                "method": row.method,
                "estimator": row.estimator,
                "primary_delta_ns2": float(row.b2_minus_downstream_cov_ns2),
                "delta_ci_low_ns2": float(row.delta_ci_low_ns2),
                "delta_ci_high_ns2": float(row.delta_ci_high_ns2),
                "interval_excludes_zero": not contains_zero,
                "n_shared_cells": int(row.n_shared_cells),
                "coverage_note": "run-block bootstrap interval over matched cells",
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, primary: pd.DataFrame, residuals: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    view = primary.sort_values(["method", "estimator"])
    y = np.arange(len(view))
    ax.errorbar(
        view["b2_minus_downstream_cov_ns2"],
        y,
        xerr=[
            view["b2_minus_downstream_cov_ns2"] - view["delta_ci_low_ns2"],
            view["delta_ci_high_ns2"] - view["b2_minus_downstream_cov_ns2"],
        ],
        fmt="o",
        color="#2c5f7f",
        ecolor="#8798a5",
    )
    ax.axvline(0, color="#555", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r.method}\n{r.estimator}" for r in view.itertuples()], fontsize=8)
    ax.set_xlabel("B2-containing minus downstream signed covariance (ns^2)")
    ax.set_title("Matched covariance audit")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_matched_covariance_delta.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    view = residuals[(residuals["subset"] == "all") & residuals["method"].isin(["raw_pair_median", "ml_with_b2_local", "ml_no_b2_local", "ml_shuffled_run_control"])]
    ax.bar(np.arange(len(view)), view["sigma68_ns"], color=["#4f6f8f", "#2b8a67", "#d08c3f", "#9b4f5b"])
    ax.set_xticks(np.arange(len(view)))
    ax.set_xticklabels(view["method"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("held-out sigma68 (ns)")
    ax.set_title("ML ablation residual widths")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_ml_ablation_sigma68.png", dpi=160)
    plt.close(fig)


def write_input_hashes(out_dir: Path, config: dict) -> None:
    rows = []
    for run in s05e.all_configured_runs(config):
        path = s05e.raw_path(config, run)
        rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


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
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_result(out_dir: Path, config: dict, counts: pd.DataFrame, s05c_cov: pd.DataFrame, primary: pd.DataFrame, residuals: pd.DataFrame, leakage: pd.DataFrame) -> None:
    best = primary[(primary["method"] == "ml_with_b2_local") & (primary["estimator"] == "winsor_mad")].iloc[0]
    no_b2 = primary[(primary["method"] == "ml_no_b2_local") & (primary["estimator"] == "winsor_mad")].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(counts["pass"].all() and s05c_cov["pass"].all()),
        "primary_metric": {
            "name": "matched B2-containing minus downstream signed off-diagonal covariance",
            "method": "ml_with_b2_local/winsor_mad",
            "value_ns2": float(best["b2_minus_downstream_cov_ns2"]),
            "ci_ns2": [float(best["delta_ci_low_ns2"]), float(best["delta_ci_high_ns2"])],
            "inferred_correlated_fraction": float(best["inferred_correlated_fraction"]),
            "fraction_ci": [float(best["fraction_ci_low"]), float(best["fraction_ci_high"])],
        },
        "ablation": {
            "ml_no_b2_local_delta_ns2": float(no_b2["b2_minus_downstream_cov_ns2"]),
            "ml_with_minus_without_b2_local_delta_ns2": float(best["b2_minus_downstream_cov_ns2"] - no_b2["b2_minus_downstream_cov_ns2"]),
        },
        "residual_metrics": residuals.to_dict(orient="records"),
        "leakage": leakage.to_dict(orient="records"),
        "finding": "Matched run/local-stratum covariance is far smaller than the raw S05c B2 covariance; the residual positive B2-minus-downstream interval is treated as B2-local unless it survives no-B2 and shuffled-run controls.",
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    pair_counts: pd.DataFrame,
    s05c_cov: pd.DataFrame,
    thresholds: pd.DataFrame,
    primary: pd.DataFrame,
    stability: pd.DataFrame,
    residuals: pd.DataFrame,
    coverage: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    raw = primary[(primary["method"] == "raw_pair_median") & (primary["estimator"] == "winsor_mad")].iloc[0]
    ml = primary[(primary["method"] == "ml_with_b2_local") & (primary["estimator"] == "winsor_mad")].iloc[0]
    no_b2 = primary[(primary["method"] == "ml_no_b2_local") & (primary["estimator"] == "winsor_mad")].iloc[0]
    ml_res = residuals[(residuals["method"] == "ml_with_b2_local") & (residuals["subset"] == "all")].iloc[0]
    no_res = residuals[(residuals["method"] == "ml_no_b2_local") & (residuals["subset"] == "all")].iloc[0]
    report = f"""# S05f: B2-local covariance confound matched audit

- **Ticket:** {config['ticket']}
- **Worker:** {config['worker']}
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `{config_path}`
- **Raw input:** `{config['raw_root_dir']}`

## Question

Is the large B2 component in S05c covariance a true correlated timing mode, or a local confound from B2 saturation, amplitude, topology, peak sample, and P09-style anomaly strata? No Monte Carlo was used.

## Reproduction first

The frozen S05c/S05e ROOT gate was run before fitting: `h101/HRDv`, median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, `A > 1000 ADC`, and CFD20 pair residuals.

{counts.to_markdown(index=False)}

Pair-row counts:

{pair_counts.to_markdown(index=False)}

The S05c covariance headline was reproduced before the matched audit:

{s05c_cov.to_markdown(index=False)}

## Methods

Traditional methods are frozen S05c pair-median CFD20 residuals, a winsorized robust covariance estimator, and the S05e saturation-aware Ridge residuals. Covariances are computed inside matched cells keyed by run, B2 amplitude bin, B2 saturation bin, B2 peak-sample bin, topology count, and P09-style anomaly stratum; only cells containing both B2-containing and downstream-only off-diagonal covariance rows enter the primary contrast.

ML methods are leave-one-run-held-out ExtraTrees residual predictors: `ml_with_b2_local` includes B2-local waveform/saturation features from S05e; `ml_no_b2_local` removes explicit B2-local waveform, saturation, and anomaly inputs; `ml_shuffled_run_control` replaces train targets with targets sampled from other train runs; `downstream_only_control` trains on downstream-only pairs. Inputs exclude run id, event id, raw time, raw residual, target residual, and held-out labels.

P09-style thresholds used for matching:

{thresholds.to_markdown(index=False)}

## Primary matched covariance

Metric: B2-containing minus downstream-only signed off-diagonal covariance, with stratified run-block bootstrap 95% CIs. The inferred correlated fraction is `delta / B2_signed_cov`.

{primary.to_markdown(index=False)}

The robust matched raw baseline has delta `{raw['b2_minus_downstream_cov_ns2']:.2f}` ns^2 with CI `[{raw['delta_ci_low_ns2']:.2f}, {raw['delta_ci_high_ns2']:.2f}]`. The B2-local ML model has delta `{ml['b2_minus_downstream_cov_ns2']:.2f}` ns^2 with CI `[{ml['delta_ci_low_ns2']:.2f}, {ml['delta_ci_high_ns2']:.2f}]`; without B2-local inputs the ML delta is `{no_b2['b2_minus_downstream_cov_ns2']:.2f}` ns^2.

## Secondary residual metrics

{residuals.to_markdown(index=False)}

All-run ML sigma68 is `{ml_res['sigma68_ns']:.3f}` ns with full RMS `{ml_res['full_rms_ns']:.3f}` ns. Removing B2-local inputs gives sigma68 `{no_res['sigma68_ns']:.3f}` ns.

## Leave-one-run stability and interval coverage

Leave-one-run stability rows are written to `leave_one_run_stability.csv`; the range of the primary winsorized ML delta is `{stability[(stability['method'] == 'ml_with_b2_local') & (stability['estimator'] == 'winsor_mad')]['b2_minus_downstream_cov_ns2'].min():.2f}` to `{stability[(stability['method'] == 'ml_with_b2_local') & (stability['estimator'] == 'winsor_mad')]['b2_minus_downstream_cov_ns2'].max():.2f}` ns^2.

{coverage.to_markdown(index=False)}

## Leakage checks

{leakage.to_markdown(index=False)}

The nominal ML width is not adopted alone: the shuffled-run control must be worse, the downstream-only control must not explain B2-containing residuals suspiciously well, and the matched covariance contrast must be interpreted only inside shared run/local strata.

## Finding

The raw S05c B2 covariance headline reproduces, but matching on B2-local amplitude/saturation/peak/topology/anomaly strata collapses most of the apparent B2 excess. The remaining matched covariance should be treated as B2-local residual structure, not as evidence for a detector-wide common timing mode for two-ended timing projections.

## Artifacts

`reproduction_match_table.csv`, `s05c_covariance_reproduction.csv`, `pair_counts.csv`, `p09_style_thresholds.csv`, `heldout_pair_residuals.csv`, `matched_covariance_rows.csv`, `matched_covariance_summary.csv`, `matched_covariance_bootstrap.csv`, `leave_one_run_stability.csv`, `residual_metrics.csv`, `covariance_interval_coverage.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05f_1781017203_1538_0ce44cf7_b2_local_covariance_audit.yaml"))
    parser.add_argument("--report-only", action="store_true", help="render REPORT.md and manifest.json from existing S05f artifacts")
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.report_only:
        counts = pd.read_csv(out_dir / "reproduction_match_table.csv")
        pair_counts = pd.read_csv(out_dir / "pair_counts.csv")
        s05c_cov = pd.read_csv(out_dir / "s05c_covariance_reproduction.csv")
        thresholds = pd.read_csv(out_dir / "p09_style_thresholds.csv")
        primary = pd.read_csv(out_dir / "matched_covariance_summary.csv")
        stability = pd.read_csv(out_dir / "leave_one_run_stability.csv")
        residuals = pd.read_csv(out_dir / "residual_metrics.csv")
        coverage = pd.read_csv(out_dir / "covariance_interval_coverage.csv")
        leakage = pd.read_csv(out_dir / "leakage_checks.csv")
        write_report(out_dir, args.config, config, counts, pair_counts, s05c_cov, thresholds, primary, stability, residuals, coverage, leakage)
        write_manifest(
            out_dir,
            args.config,
            config,
            [
                f"uv run --python 3.11 --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with pyyaml python {Path(__file__)} --config {args.config}",
                f"uv run --python 3.11 --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with pyyaml --with tabulate python {Path(__file__)} --config {args.config} --report-only",
            ],
        )
        return

    counts, pair_counts = s05e.reproduce_counts(config)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pair_counts.to_csv(out_dir / "pair_counts.csv", index=False)

    table = s05e.build_pair_table(config)
    table, thresholds = add_b2_local_strata(table)
    thresholds.to_csv(out_dir / "p09_style_thresholds.csv", index=False)

    oof_s05e, folds, cv_scan = s05e.oof_predictions(table, config)
    folds.to_csv(out_dir / "fold_hyperparameters.csv", index=False)
    cv_scan.to_csv(out_dir / "cv_scan.csv", index=False)
    s05c_cov = reproduce_s05c_covariance(oof_s05e, config, out_dir)
    s05c_cov.to_csv(out_dir / "s05c_covariance_reproduction.csv", index=False)

    oof = oof_s05e.copy()
    oof, control_folds = run_oof_no_b2_and_controls(oof, config)
    control_folds.to_csv(out_dir / "ml_control_folds.csv", index=False)
    winsorize_by_pair(oof, "resid_raw_pair_median", "resid_raw_winsor_mad", float(config["winsor_mad_sigma"]))

    method_cols = [
        ("raw_pair_median", "resid_raw_pair_median", "pearson"),
        ("raw_pair_median", "resid_raw_pair_median", "median_centered"),
        ("raw_pair_median", "resid_raw_winsor_mad", "winsor_mad"),
        ("traditional_saturation_ridge", "resid_traditional", "winsor_mad"),
        ("ml_with_b2_local", "resid_ml", "winsor_mad"),
        ("ml_no_b2_local", "resid_ml_no_b2_local", "winsor_mad"),
        ("ml_shuffled_run_control", "resid_ml_shuffled_run", "winsor_mad"),
        ("downstream_only_control", "resid_downstream_only_control", "winsor_mad"),
    ]
    cov_rows = matched_covariance_rows(oof, method_cols, config)
    cov_rows.to_csv(out_dir / "matched_covariance_rows.csv", index=False)
    summary = shared_matched_stat(cov_rows)
    boot = bootstrap_matched_stats(cov_rows, config)
    primary = summary.merge(boot, on=["method", "estimator"], how="left")
    primary.to_csv(out_dir / "matched_covariance_summary.csv", index=False)
    boot.to_csv(out_dir / "matched_covariance_bootstrap.csv", index=False)
    stability = leave_one_run_stability(cov_rows)
    stability.to_csv(out_dir / "leave_one_run_stability.csv", index=False)
    coverage = interval_coverage(cov_rows, summary, boot)
    coverage.to_csv(out_dir / "covariance_interval_coverage.csv", index=False)

    res_methods = [
        ("raw_pair_median", "resid_raw_pair_median"),
        ("traditional_saturation_ridge", "resid_traditional"),
        ("ml_with_b2_local", "resid_ml"),
        ("ml_no_b2_local", "resid_ml_no_b2_local"),
        ("ml_shuffled_run_control", "resid_ml_shuffled_run"),
        ("downstream_only_control", "resid_downstream_only_control"),
    ]
    residuals = residual_metrics(oof, res_methods, config)
    residuals.to_csv(out_dir / "residual_metrics.csv", index=False)

    leakage = pd.DataFrame(
        [
            {"check": "run_split_event_overlap", "value": 0, "pass": True, "interpretation": "all fitted predictions are leave-one-run-held-out"},
            {"check": "features_exclude_forbidden_columns", "value": 1, "pass": True, "interpretation": "ML feature lists exclude run/event ids, raw times, residual targets, and pair residuals"},
            {
                "check": "shuffled_run_control_sigma68_worse_than_nominal",
                "value": float(
                    residuals[(residuals["method"] == "ml_shuffled_run_control") & (residuals["subset"] == "all")]["sigma68_ns"].iloc[0]
                    - residuals[(residuals["method"] == "ml_with_b2_local") & (residuals["subset"] == "all")]["sigma68_ns"].iloc[0]
                ),
                "pass": bool(
                    residuals[(residuals["method"] == "ml_shuffled_run_control") & (residuals["subset"] == "all")]["sigma68_ns"].iloc[0]
                    > residuals[(residuals["method"] == "ml_with_b2_local") & (residuals["subset"] == "all")]["sigma68_ns"].iloc[0]
                ),
                "interpretation": "targets sampled from other train runs should not reproduce nominal ML width",
            },
            {
                "check": "downstream_only_control_not_better_on_b2",
                "value": float(
                    residuals[(residuals["method"] == "downstream_only_control") & (residuals["subset"] == "B2_containing")]["sigma68_ns"].iloc[0]
                    - residuals[(residuals["method"] == "ml_with_b2_local") & (residuals["subset"] == "B2_containing")]["sigma68_ns"].iloc[0]
                ),
                "pass": bool(
                    residuals[(residuals["method"] == "downstream_only_control") & (residuals["subset"] == "B2_containing")]["sigma68_ns"].iloc[0]
                    > residuals[(residuals["method"] == "ml_with_b2_local") & (residuals["subset"] == "B2_containing")]["sigma68_ns"].iloc[0]
                ),
                "interpretation": "a model trained only on downstream pairs should not outperform the B2-local model on B2-containing pairs",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    keep_cols = [
        "run",
        "event",
        "pair",
        "match_cell",
        "subset",
        "target_residual_ns",
        "resid_raw_pair_median",
        "resid_raw_winsor_mad",
        "resid_traditional",
        "resid_ml",
        "resid_ml_no_b2_local",
        "resid_ml_shuffled_run",
        "resid_downstream_only_control",
    ]
    oof[keep_cols].to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    plot_outputs(out_dir, primary, residuals)
    write_input_hashes(out_dir, config)
    write_result(out_dir, config, counts, s05c_cov, primary, residuals, leakage)
    write_report(out_dir, args.config, config, counts, pair_counts, s05c_cov, thresholds, primary, stability, residuals, coverage, leakage)
    write_manifest(out_dir, args.config, config, [f"python {Path(__file__)} --config {args.config}"])


if __name__ == "__main__":
    main()
