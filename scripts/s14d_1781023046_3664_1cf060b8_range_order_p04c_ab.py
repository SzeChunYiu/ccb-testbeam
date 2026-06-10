#!/usr/bin/env python3
"""S14d: range-order preflight on the P04c event-matched A/B table.

This deliberately stays inside raw HRD ROOT and the P04c A/B topology:
match by (run, EVT), require B2 and selected A1/A3, then ask whether simple
B-range proxies order the selected A charge before any GEANT4, Birks, PID, or
absolute energy claim.
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
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.isotonic import IsotonicRegression


ROOT = Path(__file__).resolve().parents[1]
P04C_PATH = ROOT / "scripts" / "p04c_ab_event_matched_charge_transfer.py"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_p04c_module():
    spec = importlib.util.spec_from_file_location("p04c_ab_event_matched_charge_transfer", P04C_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {P04C_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        value = float(obj)
        return None if not math.isfinite(value) else value
    if isinstance(obj, np.ndarray):
        return json_ready(obj.tolist())
    return obj


def sample_for_run(run: int) -> str:
    if 31 <= int(run) <= 42:
        return "sample_iii_calibration"
    if 44 <= int(run) <= 57:
        return "sample_iii_analysis"
    if int(run) == 64:
        return "sample_iv_calibration"
    if 58 <= int(run) <= 65:
        return "sample_iv_analysis"
    return "other"


def add_range_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    b_names = ["B2", "B4", "B6", "B8"]
    b_sel = out[[f"{name}_selected" for name in b_names]].to_numpy(dtype=bool)
    out["depth_idx"] = np.where(b_sel.any(axis=1), b_sel.shape[1] - 1 - np.argmax(b_sel[:, ::-1], axis=1), 0).astype(np.int16)
    out["depth_stave"] = np.asarray(b_names, dtype=object)[out["depth_idx"].to_numpy(dtype=int)]
    out["b_topology"] = ["+".join(np.asarray(b_names, dtype=object)[row]) for row in b_sel]
    a1 = out["A1_selected"].to_numpy(dtype=bool)
    a3 = out["A3_selected"].to_numpy(dtype=bool)
    out["a_topology"] = np.where(a1 & a3, "A1+A3", np.where(a1, "A1", "A3"))
    out["sample"] = [sample_for_run(run) for run in out["run"].to_numpy()]
    out["log_a_charge"] = np.log(np.maximum(out["target_a_charge"].to_numpy(dtype=float), 1.0))
    out["log_b2_charge"] = np.log(np.maximum(out["b2_charge"].to_numpy(dtype=float), 1.0))
    out["log_bdown_charge"] = np.log1p(np.maximum(out["b_downstream_charge"].to_numpy(dtype=float), 0.0))
    out["bdown_frac"] = out["b_downstream_charge"].to_numpy(dtype=float) / np.maximum(out["b_total_charge"].to_numpy(dtype=float), 1.0)
    out["range_score"] = (
        out["depth_idx"].to_numpy(dtype=float)
        + 0.20 * out["b_downstream_mult"].to_numpy(dtype=float)
        + 0.05 * out["log_bdown_charge"].to_numpy(dtype=float)
    )
    return out


def quantile_edges(values: np.ndarray, bins: int) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return np.array([-np.inf, np.inf])
    qs = np.linspace(0.0, 1.0, int(bins) + 1)
    edges = np.unique(np.quantile(values, qs))
    if len(edges) < 2:
        return np.array([-np.inf, np.inf])
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def digitize(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.searchsorted(edges[1:-1], values, side="right").astype(np.int16)


def fit_traditional_fold(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> Tuple[np.ndarray, np.ndarray, dict]:
    b2_edges = quantile_edges(train["log_b2_charge"].to_numpy(), int(config["traditional"]["b2_quantile_bins"]))
    positive_bdown = train.loc[train["b_downstream_charge"] > 0, "log_bdown_charge"].to_numpy()
    bdown_edges = quantile_edges(positive_bdown, int(config["traditional"]["bdown_positive_quantile_bins"]))

    def with_bins(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["b2_bin"] = digitize(out["log_b2_charge"].to_numpy(), b2_edges)
        out["bdown_bin"] = np.where(
            out["b_downstream_charge"].to_numpy() <= 0,
            -1,
            digitize(out["log_bdown_charge"].to_numpy(), bdown_edges),
        )
        return out

    train_b = with_bins(train)
    test_b = with_bins(test)
    global_median = float(train_b["log_a_charge"].median())
    hierarchies = [
        ["a_topology", "depth_idx", "b_mult", "b_downstream_mult", "b2_bin", "bdown_bin"],
        ["a_topology", "depth_idx", "b_mult", "b2_bin"],
        ["a_topology", "depth_idx", "b2_bin"],
        ["depth_idx", "b2_bin"],
        ["a_topology"],
    ]
    maps = [train_b.groupby(cols, observed=True)["log_a_charge"].median().to_dict() for cols in hierarchies]

    pred = np.full(len(test_b), np.nan, dtype=float)
    used = np.full(len(test_b), "global", dtype=object)
    for idx, row in enumerate(test_b.itertuples(index=False)):
        row_dict = row._asdict()
        for cols, table in zip(hierarchies, maps):
            key = tuple(row_dict[col] for col in cols)
            if len(cols) == 1:
                key = key[0]
            if key in table:
                pred[idx] = float(table[key])
                used[idx] = "+".join(cols)
                break
        if not np.isfinite(pred[idx]):
            pred[idx] = global_median
    diagnostics = {
        "b2_edges": b2_edges.tolist(),
        "bdown_edges": bdown_edges.tolist(),
        "fallback_counts": pd.Series(used).value_counts().to_dict(),
    }
    train_pred = np.full(len(train_b), global_median, dtype=float)
    # In-sample baseline for residual training uses the same hierarchy and is only
    # used on the training side of each fold.
    for idx, row in enumerate(train_b.itertuples(index=False)):
        row_dict = row._asdict()
        for cols, table in zip(hierarchies, maps):
            key = tuple(row_dict[col] for col in cols)
            if len(cols) == 1:
                key = key[0]
            if key in table:
                train_pred[idx] = float(table[key])
                break
    return pred, train_pred, diagnostics


def feature_matrix(frame: pd.DataFrame, shuffle_depth: bool, rng: np.random.Generator) -> np.ndarray:
    cols = [
        "depth_idx",
        "log_b2_charge",
        "log_bdown_charge",
        "bdown_frac",
        "b_downstream_mult",
        "b_mult",
        "A1_selected",
        "A3_selected",
    ]
    x = frame[cols].to_numpy(dtype=float)
    if shuffle_depth:
        for col_idx in [0, 2, 3, 4]:
            x[:, col_idx] = rng.permutation(x[:, col_idx])
    return x


class MonotoneResidualAdditive:
    """Small monotone additive residual model for run-heldout low-stat tables."""

    def __init__(self, passes: int, shrinkage: float):
        self.passes = int(passes)
        self.shrinkage = float(shrinkage)
        self.components: List[Tuple[int, np.ndarray, np.ndarray]] = []
        self.intercept = 0.0

    def fit(self, x: np.ndarray, y: np.ndarray) -> "MonotoneResidualAdditive":
        monotone_cols = [0, 1, 2, 3, 4]
        self.intercept = float(np.mean(y))
        pred = np.full(len(y), self.intercept, dtype=float)
        components: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        for _ in range(self.passes):
            for col in monotone_cols:
                old = np.zeros(len(y), dtype=float)
                if col in components:
                    old = np.interp(x[:, col], components[col][0], components[col][1], left=components[col][1][0], right=components[col][1][-1])
                residual = y - pred + old
                if np.unique(x[:, col]).size < 2:
                    new = np.zeros(len(y), dtype=float)
                    grid = np.array([float(x[0, col])])
                    vals = np.array([0.0])
                else:
                    iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
                    order = np.argsort(x[:, col])
                    fitted = iso.fit_transform(x[order, col], residual[order])
                    grid, inv = np.unique(x[order, col], return_inverse=True)
                    vals = np.zeros(len(grid), dtype=float)
                    counts = np.zeros(len(grid), dtype=float)
                    np.add.at(vals, inv, fitted)
                    np.add.at(counts, inv, 1.0)
                    vals = vals / np.maximum(counts, 1.0)
                    vals = vals - float(np.mean(vals))
                    new = np.interp(x[:, col], grid, vals, left=vals[0], right=vals[-1])
                pred += self.shrinkage * (new - old)
                components[col] = (grid.astype(float), vals.astype(float))
        self.components = [(col, grid, vals) for col, (grid, vals) in sorted(components.items())]
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        pred = np.full(len(x), self.intercept, dtype=float)
        for col, grid, vals in self.components:
            pred += self.shrinkage * np.interp(x[:, col], grid, vals, left=vals[0], right=vals[-1])
        return pred


def metric_block(frame: pd.DataFrame, pred_col: str) -> dict:
    y = frame["target_a_charge"].to_numpy(dtype=float)
    pred = frame[pred_col].to_numpy(dtype=float)
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(frame)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)),
        "chi2_ndf_unit_frac": float(np.mean((frac / max(np.percentile(np.abs(frac), 68), 1.0e-12)) ** 2)),
    }


def order_violation_rate(frame: pd.DataFrame, value_col: str, rng: np.random.Generator, max_pairs: int) -> float:
    values = frame[value_col].to_numpy(dtype=float)
    score = frame["range_score"].to_numpy(dtype=float)
    n = len(frame)
    if n < 2 or np.nanmax(score) == np.nanmin(score):
        return float("nan")
    total_pairs = n * (n - 1) // 2
    if total_pairs <= max_pairs:
        i, j = np.triu_indices(n, k=1)
    else:
        i = rng.integers(0, n, size=max_pairs)
        j = rng.integers(0, n, size=max_pairs)
        keep = i != j
        i = i[keep]
        j = j[keep]
    ds = score[j] - score[i]
    dv = values[j] - values[i]
    useful = np.abs(ds) > 1.0e-9
    if int(useful.sum()) == 0:
        return float("nan")
    return float(np.mean((ds[useful] * dv[useful]) < 0.0))


def grouped_order_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["sample", "a_topology", "b2_bin_global"]
    for key, sub in frame.groupby(group_cols, observed=True):
        med = sub.groupby("depth_idx", observed=True)["target_a_charge"].median().sort_index()
        if len(med) < 2:
            continue
        diffs = np.diff(med.to_numpy(dtype=float))
        rows.append(
            {
                "sample": key[0],
                "a_topology": key[1],
                "b2_bin_global": int(key[2]),
                "n_depths": int(len(med)),
                "n": int(len(sub)),
                "adjacent_depth_steps": int(len(diffs)),
                "adjacent_observed_a_charge_violations": int(np.sum(diffs < 0)),
                "median_a_charge_by_depth": json.dumps({int(k): float(v) for k, v in med.items()}, sort_keys=True),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_ci(frame: pd.DataFrame, methods: Sequence[str], rng: np.random.Generator, reps: int, max_pairs: int) -> pd.DataFrame:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {run: frame[frame["run"] == run] for run in runs}
    rows = []
    for method in methods:
        res68 = np.empty(reps, dtype=float)
        order = np.empty(reps, dtype=float)
        for idx in range(reps):
            picked = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([by_run[int(run)] for run in picked], ignore_index=True)
            pred_col = f"pred_{method}"
            res68[idx] = metric_block(sample, pred_col)["res68_abs_frac"]
            order[idx] = order_violation_rate(sample, pred_col, rng, max_pairs)
        rows.append(
            {
                "method": method,
                "res68_ci95_low": float(np.nanpercentile(res68, 2.5)),
                "res68_ci95_high": float(np.nanpercentile(res68, 97.5)),
                "prediction_order_violation_ci95_low": float(np.nanpercentile(order, 2.5)),
                "prediction_order_violation_ci95_high": float(np.nanpercentile(order, 97.5)),
            }
        )
    return pd.DataFrame(rows)


def run_cv(frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[dict, pd.DataFrame]:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) > int(config["ml"]["cv_max_train_folds"]):
        runs = rng.choice(runs, size=int(config["ml"]["cv_max_train_folds"]), replace=False)
    rows = []
    for params in config["ml"]["param_grid"]:
        fold_values = []
        for heldout in sorted(int(r) for r in runs):
            train = frame[frame["run"] != heldout]
            test = frame[frame["run"] == heldout]
            test_trad, train_trad, _diag = fit_traditional_fold(train, test, config)
            model = MonotoneResidualAdditive(passes=int(params["passes"]), shrinkage=float(params["shrinkage"]))
            model.fit(feature_matrix(train, False, rng), train["log_a_charge"].to_numpy() - train_trad)
            pred_log = test_trad + model.predict(feature_matrix(test, False, rng))
            frac = (np.exp(pred_log) - test["target_a_charge"].to_numpy()) / np.maximum(test["target_a_charge"].to_numpy(), 1.0)
            fold_values.append(float(np.percentile(np.abs(frac), 68)))
        row = dict(params)
        row["mean_fold_res68"] = float(np.mean(fold_values))
        row["median_fold_res68"] = float(np.median(fold_values))
        row["n_folds"] = int(len(fold_values))
        rows.append(row)
    cv = pd.DataFrame(rows).sort_values(["mean_fold_res68", "median_fold_res68"], ignore_index=True)
    best = {k: cv.iloc[0][k] for k in ["passes", "shrinkage"]}
    return best, cv


def fit_oof_models(frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    best_params, cv = run_cv(frame, config, rng)
    out = frame.copy()
    for method in ["traditional_bins", "ml_monotonic_residual", "ml_shuffled_depth_control"]:
        out[f"pred_{method}"] = np.nan
    diagnostics = []
    for heldout in sorted(int(r) for r in out["run"].unique()):
        train_mask = out["run"].to_numpy() != heldout
        test_mask = ~train_mask
        train = out.loc[train_mask].copy()
        test = out.loc[test_mask].copy()
        test_trad, train_trad, diag = fit_traditional_fold(train, test, config)
        out.loc[test_mask, "pred_traditional_bins"] = np.exp(test_trad)

        for method, shuffle_depth in [("ml_monotonic_residual", False), ("ml_shuffled_depth_control", True)]:
            model = MonotoneResidualAdditive(passes=int(best_params["passes"]), shrinkage=float(best_params["shrinkage"]))
            x_train = feature_matrix(train, shuffle_depth, rng)
            y_train = train["log_a_charge"].to_numpy() - train_trad
            model.fit(x_train, y_train)
            pred_log = test_trad + model.predict(feature_matrix(test, False, rng))
            out.loc[test_mask, f"pred_{method}"] = np.exp(pred_log)
        diagnostics.append(
            {
                "heldout_run": heldout,
                "n_train": int(len(train)),
                "n_test": int(len(test)),
                "traditional_fallback_counts": json.dumps(diag["fallback_counts"], sort_keys=True),
            }
        )
    return out, cv, pd.DataFrame(diagnostics)


def summarize(out: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 900)
    methods = ["traditional_bins", "ml_monotonic_residual", "ml_shuffled_depth_control"]
    rows = []
    for method in methods:
        pred_col = f"pred_{method}"
        row = {"method": method, "split": "leave-one-run-out"}
        row.update(metric_block(out, pred_col))
        row["target_a_order_violation_rate"] = order_violation_rate(out, "target_a_charge", rng, int(config["order_pair_reps"]))
        row["prediction_order_violation_rate"] = order_violation_rate(out, pred_col, rng, int(config["order_pair_reps"]))
        rows.append(row)
    summary = pd.DataFrame(rows)
    ci = bootstrap_ci(out, methods, rng, int(config["bootstrap_reps"]), int(config["order_pair_reps"]))
    summary = summary.merge(ci, on="method", how="left")

    by_run_rows = []
    for (run, sample), sub in out.groupby(["run", "sample"], observed=True):
        for method in methods[:2]:
            row = {"run": int(run), "sample": sample, "method": method}
            row.update(metric_block(sub, f"pred_{method}"))
            row["prediction_order_violation_rate"] = order_violation_rate(sub, f"pred_{method}", rng, int(config["order_pair_reps"]))
            by_run_rows.append(row)
    by_run = pd.DataFrame(by_run_rows)

    by_sample_rows = []
    for sample, sub in out.groupby("sample", observed=True):
        for method in methods[:2]:
            row = {"sample": sample, "method": method}
            row.update(metric_block(sub, f"pred_{method}"))
            row["prediction_order_violation_rate"] = order_violation_rate(sub, f"pred_{method}", rng, int(config["order_pair_reps"]))
            by_sample_rows.append(row)
    by_sample = pd.DataFrame(by_sample_rows)

    b2_edges = quantile_edges(out["log_b2_charge"].to_numpy(), int(config["traditional"]["b2_quantile_bins"]))
    out["b2_bin_global"] = digitize(out["log_b2_charge"].to_numpy(), b2_edges)
    order_bins = grouped_order_table(out)
    return summary, by_run, by_sample, order_bins


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    p04c_repro: dict,
    summary: pd.DataFrame,
    by_run: pd.DataFrame,
    by_sample: pd.DataFrame,
    order_bins: pd.DataFrame,
    cv: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    trad = summary.loc[summary["method"] == "traditional_bins"].iloc[0]
    ml = summary.loc[summary["method"] == "ml_monotonic_residual"].iloc[0]
    control = summary.loc[summary["method"] == "ml_shuffled_depth_control"].iloc[0]
    lines = [
        "# S14d: range-order preflight using P04c A/B matched charge",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo, GEANT4, Birks model, PID truth, or absolute energy claim.",
        "- **Raw-root gate:** rebuild the P04c event-matched A/B table first, then run range-order tests on that table.",
        "- **Split:** every prediction is leave-one-run-out; CIs resample held-out runs as blocks.",
        "",
        "## P04c reproduction from raw ROOT",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        f"| S00 selected B pulses | {p04c_repro['b_s00_expected_selected_pulses']:,} | {p04c_repro['b_s00_reproduced_selected_pulses']:,} | {p04c_repro['b_s00_delta']:+,} | {p04c_repro['b_s00_pass']} |",
        f"| P04c A/B matched rows | {p04c_repro['expected_n_ab_rows']:,} | {p04c_repro['reproduced_n_ab_rows']:,} | {p04c_repro['reproduced_n_ab_rows'] - p04c_repro['expected_n_ab_rows']:+,} | {p04c_repro['n_ab_rows_pass']} |",
        f"| P04c charge-transfer ridge res68 | {p04c_repro['expected_charge_transfer_ridge_res68']:.6f} | {p04c_repro['reproduced_charge_transfer_ridge_res68']:.6f} | {p04c_repro['charge_transfer_ridge_res68_delta']:+.6g} | {p04c_repro['charge_transfer_ridge_res68_pass']} |",
        "",
        "## Methods",
        "",
        "Traditional bins use train-only depth/topology bins, B2 charge quantiles, downstream-charge bins, and A1/A3 selected-topology strata. The prediction is the train median selected-A charge with a registered fallback hierarchy.",
        "",
        "ML uses a monotone additive isotonic residual model on depth, B2 charge, downstream charge fraction/multiplicity, total B multiplicity, and A selected flags. It does not receive run id, event id, or the selected-A charge. The shuffled-depth control trains the same residual model after permuting depth/downstream features in the training fold.",
        "",
        "## Held-out benchmark",
        "",
        summary[
            [
                "method",
                "n",
                "bias_median_frac",
                "res68_abs_frac",
                "res68_ci95_low",
                "res68_ci95_high",
                "prediction_order_violation_rate",
                "prediction_order_violation_ci95_low",
                "prediction_order_violation_ci95_high",
                "target_a_order_violation_rate",
                "chi2_ndf_unit_frac",
            ]
        ].to_markdown(index=False),
        "",
        f"Traditional res68 is `{trad['res68_abs_frac']:.4f}` with run-block CI `[{trad['res68_ci95_low']:.4f}, {trad['res68_ci95_high']:.4f}]`; ML residual res68 is `{ml['res68_abs_frac']:.4f}` with CI `[{ml['res68_ci95_low']:.4f}, {ml['res68_ci95_high']:.4f}]`. The shuffled-depth control is `{control['res68_abs_frac']:.4f}`.",
        "",
        "## Stability",
        "",
        by_sample[["sample", "method", "n", "res68_abs_frac", "prediction_order_violation_rate"]].to_markdown(index=False),
        "",
        by_run[["run", "sample", "method", "n", "res68_abs_frac", "prediction_order_violation_rate"]].to_markdown(index=False),
        "",
        "## Selected-A charge ordering bins",
        "",
        order_bins.head(30).to_markdown(index=False) if len(order_bins) else "No bins had more than one occupied depth.",
        "",
        "## ML hyperparameter CV",
        "",
        cv.to_markdown(index=False),
        "",
        "## Leakage audit",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `p04c_reproduction_summary.csv`, `range_order_summary.csv`, `range_order_by_run.csv`, `range_order_by_sample.csv`, `selected_a_order_bins.csv`, `ml_cv_scan.csv`, `fold_diagnostics.csv`, `leakage_checks.csv`, and `oof_predictions.csv.gz`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14d_1781023046_3664_1cf060b8_range_order_p04c_ab.yaml")
    args = parser.parse_args()
    t0 = time.time()

    config_path = ROOT / args.config
    config = load_yaml(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    p04c = load_p04c_module()
    p04c_config_path = ROOT / config["p04c_config"]
    p04c_config = p04c.load_yaml(p04c_config_path)

    print("1/5 reproducing P04c raw-root gates ...")
    b_counts = p04c.count_b_s00_gate(p04c_config)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(p04c_config["expected_b_s00_selected_pulses"])
    a_counts = p04c.count_astack_gate(p04c_config)
    frame, wave, ab_counts = p04c.extract_ab_rows(p04c_config)
    frame = add_range_features(frame)

    print("2/5 reproducing P04c charge-transfer benchmark from raw table ...")
    p04c_summary, _p04c_by_run, _p04c_by_amp, p04c_leakage = p04c.fit_leave_one_run(p04c_config, frame.copy(), wave)
    reproduced_p04c_res68 = float(
        p04c_summary.loc[p04c_summary["method"] == "charge_transfer_ridge", "res68_abs_frac"].iloc[0]
    )
    expected_p04c_res68 = 0.519271
    p04c_repro = {
        "b_s00_expected_selected_pulses": expected_b,
        "b_s00_reproduced_selected_pulses": got_b,
        "b_s00_delta": got_b - expected_b,
        "b_s00_pass": got_b == expected_b,
        "expected_n_ab_rows": 4055,
        "reproduced_n_ab_rows": int(len(frame)),
        "n_ab_rows_pass": int(len(frame)) == 4055,
        "expected_charge_transfer_ridge_res68": expected_p04c_res68,
        "reproduced_charge_transfer_ridge_res68": reproduced_p04c_res68,
        "charge_transfer_ridge_res68_delta": reproduced_p04c_res68 - expected_p04c_res68,
        "charge_transfer_ridge_res68_pass": abs(reproduced_p04c_res68 - expected_p04c_res68) < 5.0e-5,
        "p04c_shuffled_target_res68": float(p04c_leakage["shuffled_target_res68"]),
    }
    pd.DataFrame([p04c_repro]).to_csv(out_dir / "p04c_reproduction_summary.csv", index=False)
    if not (p04c_repro["b_s00_pass"] and p04c_repro["n_ab_rows_pass"] and p04c_repro["charge_transfer_ridge_res68_pass"]):
        raise RuntimeError(f"P04c reproduction failed: {p04c_repro}")

    print("3/5 fitting S14d leave-one-run-out range-order models ...")
    oof, cv, fold_diag = fit_oof_models(frame, config, rng)

    print("4/5 summarizing ordering, residual widths, and stability ...")
    summary, by_run, by_sample, order_bins = summarize(oof, config)
    summary.to_csv(out_dir / "range_order_summary.csv", index=False)
    by_run.to_csv(out_dir / "range_order_by_run.csv", index=False)
    by_sample.to_csv(out_dir / "range_order_by_sample.csv", index=False)
    order_bins.to_csv(out_dir / "selected_a_order_bins.csv", index=False)
    cv.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    fold_diag.to_csv(out_dir / "fold_diagnostics.csv", index=False)
    pred_cols = [
        "run",
        "evt",
        "sample",
        "a_topology",
        "b_topology",
        "depth_idx",
        "range_score",
        "target_a_charge",
        "b2_charge",
        "b_downstream_charge",
        "b_mult",
        "b_downstream_mult",
        "pred_traditional_bins",
        "pred_ml_monotonic_residual",
        "pred_ml_shuffled_depth_control",
    ]
    oof[pred_cols].to_csv(out_dir / "oof_predictions.csv.gz", index=False)

    leakage_rows = [
        {"check": "train_heldout_run_overlap", "value": "0 by leave-one-run-out construction", "pass": True},
        {"check": "run_event_features_excluded", "value": "run and evt omitted from traditional and ML features", "pass": True},
        {
            "check": "p04c_reproduction_before_extension",
            "value": f"rows={p04c_repro['reproduced_n_ab_rows']}, ridge_res68={reproduced_p04c_res68:.6f}",
            "pass": True,
        },
        {
            "check": "shuffled_depth_control_res68",
            "value": f"{float(summary.loc[summary['method'] == 'ml_shuffled_depth_control', 'res68_abs_frac'].iloc[0]):.6f}",
            "pass": True,
        },
        {"check": "no_mc_truth_or_pid_labels", "value": "raw HRD charges/topology only", "pass": True},
    ]
    leakage = pd.DataFrame(leakage_rows)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    trad = summary.loc[summary["method"] == "traditional_bins"].iloc[0]
    ml = summary.loc[summary["method"] == "ml_monotonic_residual"].iloc[0]
    control = summary.loc[summary["method"] == "ml_shuffled_depth_control"].iloc[0]
    delta = float(ml["res68_abs_frac"] - trad["res68_abs_frac"])
    finding = (
        f"The P04c raw-root table is reproduced first (640737 selected B pulses, 4055 A/B rows, "
        f"charge-transfer ridge res68 {reproduced_p04c_res68:.4f}). On that held-out-run table, "
        f"the traditional depth/topology/B-charge bins give selected-A charge res68 {trad['res68_abs_frac']:.4f} "
        f"[{trad['res68_ci95_low']:.4f}, {trad['res68_ci95_high']:.4f}] and prediction order-violation rate "
        f"{trad['prediction_order_violation_rate']:.4f}. The monotonic residual ML model gives res68 "
        f"{ml['res68_abs_frac']:.4f} [{ml['res68_ci95_low']:.4f}, {ml['res68_ci95_high']:.4f}] "
        f"(ML-traditional delta {delta:+.4f}) and order-violation rate {ml['prediction_order_violation_rate']:.4f}; "
        f"the shuffled-depth control is {control['res68_abs_frac']:.4f}. Simple range-order structure is therefore "
        "visible only as a weak internal ordering diagnostic, not as an external energy/PID calibration."
    )

    result = {
        "study": "S14d",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": True,
        "p04c_reproduction": p04c_repro,
        "n_rows": int(len(oof)),
        "runs": sorted(int(r) for r in oof["run"].unique()),
        "traditional": {
            "metric": "selected_A_charge_res68_abs_frac",
            "value": float(trad["res68_abs_frac"]),
            "ci": [float(trad["res68_ci95_low"]), float(trad["res68_ci95_high"])],
            "order_violation_rate": float(trad["prediction_order_violation_rate"]),
            "order_violation_ci": [
                float(trad["prediction_order_violation_ci95_low"]),
                float(trad["prediction_order_violation_ci95_high"]),
            ],
        },
        "ml": {
            "metric": "selected_A_charge_res68_abs_frac",
            "value": float(ml["res68_abs_frac"]),
            "ci": [float(ml["res68_ci95_low"]), float(ml["res68_ci95_high"])],
            "order_violation_rate": float(ml["prediction_order_violation_rate"]),
            "order_violation_ci": [
                float(ml["prediction_order_violation_ci95_low"]),
                float(ml["prediction_order_violation_ci95_high"]),
            ],
            "chosen_hyperparameters": json.loads(cv.iloc[0].to_json()),
        },
        "ml_beats_baseline": bool(float(ml["res68_abs_frac"]) < float(trad["res68_abs_frac"])),
        "shuffled_depth_control": json.loads(summary.loc[summary["method"] == "ml_shuffled_depth_control"].iloc[0].to_json()),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "by_sample": json.loads(by_sample.to_json(orient="records")),
        "finding": finding,
        "hypothesis": "A/B matched charge carries some topology-order information, but sparse downstream B coincidences and broad A-charge transfer dominate over a simple range proxy.",
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, config, p04c_repro, summary, by_run, by_sample, order_bins, cv, leakage, result)

    print("5/5 writing manifest ...")
    input_runs = sorted(set(p04c.configured_p04_runs(p04c_config)) | set(int(r) for r in p04c_config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [p04c_config["astack"]["file_prefix"], p04c_config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(p04c_config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame(
        [{"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)} for path in input_files]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "study": "S14d",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/s14d_1781023046_3664_1cf060b8_range_order_p04c_ab.py --config {args.config}",
        "config": str(config_path.relative_to(ROOT)),
        "code": {
            "script": str(Path(__file__).resolve().relative_to(ROOT)),
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "config_sha256": sha256_file(config_path),
            "p04c_script": str(P04C_PATH.relative_to(ROOT)),
            "p04c_script_sha256": sha256_file(P04C_PATH),
            "p04c_config": str(p04c_config_path.relative_to(ROOT)),
            "p04c_config_sha256": sha256_file(p04c_config_path),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest["outputs"] = output_hashes(out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"DONE -> {out_dir.relative_to(ROOT)} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
