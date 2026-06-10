#!/usr/bin/env python3
"""P04j: conformal uncertainty and abstention for A/B charge transfer.

The study deliberately starts from the raw ROOT reproduction gates used by
P04c/P04h, then converts broad point predictions into run-held-out conformal
intervals and abstention regions.  Predictors use only B-stack waveforms and
charge summaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04c_ab_event_matched_charge_transfer as p04c  # noqa: E402
import p04h_1781023326_470_61534f82_support_map as p04h  # noqa: E402


REAL_METHODS = [
    "frozen_peak_loglinear",
    "integral_topology_ridge",
    "adaptive_template_ridge",
    "support_huber",
    "b_waveform_extra_trees",
]
SENTINEL_METHODS = [
    "topology_only_sentinel",
    "run_family_sentinel",
    "shuffled_target_extra_trees",
]
ALL_METHODS = REAL_METHODS + SENTINEL_METHODS
INTERVAL_METHODS = [
    "frozen_peak_loglinear",
    "integral_topology_ridge",
    "adaptive_template_ridge",
    "support_huber",
    "b_waveform_extra_trees",
]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def add_run_family(config: dict, frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    lookup = {}
    for family, runs in config["run_families"].items():
        for run in runs:
            lookup[int(run)] = str(family)
    out["run_family"] = out["run"].map(lambda run: lookup.get(int(run), "unknown"))
    return out


def assign_calibration_runs(runs: np.ndarray, heldout_run: int, fraction: float) -> np.ndarray:
    train_runs = np.asarray([int(run) for run in runs if int(run) != int(heldout_run)], dtype=int)
    if len(train_runs) < 4:
        return train_runs[-1:]
    n_cal = max(2, int(round(len(train_runs) * float(fraction))))
    ordered = np.sort(train_runs)
    offset = int(np.where(np.sort(runs) == int(heldout_run))[0][0]) if int(heldout_run) in set(runs) else 0
    rolled = np.roll(ordered, -offset)
    return np.sort(rolled[:n_cal])


def frozen_peak_features(frame: pd.DataFrame) -> np.ndarray:
    b2a = np.log(np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0))
    b2q = np.log(np.maximum(frame["b2_charge"].to_numpy(dtype=float), 1.0))
    peak = frame["B2_peak"].to_numpy(dtype=float)
    return np.column_stack([b2a, b2q, peak, b2a * b2a])


def integral_topology_features(frame: pd.DataFrame) -> np.ndarray:
    b2q = np.log(np.maximum(frame["b2_charge"].to_numpy(dtype=float), 1.0))
    bt = np.log(np.maximum(frame["b_total_charge"].to_numpy(dtype=float), 1.0))
    bd = np.log1p(frame["b_downstream_charge"].to_numpy(dtype=float))
    down_frac = frame["b_downstream_charge"].to_numpy(dtype=float) / np.maximum(frame["b_total_charge"].to_numpy(dtype=float), 1.0)
    return np.column_stack(
        [
            b2q,
            bt,
            bd,
            b2q * b2q,
            bt * bt,
            b2q * bt,
            down_frac,
            frame["b_mult"].to_numpy(dtype=float),
            frame["b_downstream_mult"].to_numpy(dtype=float),
            frame["B4_selected"].to_numpy(dtype=float),
            frame["B6_selected"].to_numpy(dtype=float),
            frame["B8_selected"].to_numpy(dtype=float),
        ]
    )


def topology_matrix(frame: pd.DataFrame) -> np.ndarray:
    cols = [
        "b_mult",
        "b_downstream_mult",
        "B4_selected",
        "B6_selected",
        "B8_selected",
    ]
    numeric = frame[cols].to_numpy(dtype=float)
    amps = pd.get_dummies(frame["b2_amp_bin"], prefix="amp").to_numpy(dtype=float)
    topo = pd.get_dummies(frame["topology_pattern"], prefix="topo").to_numpy(dtype=float)
    family = pd.get_dummies(frame["run_family"], prefix="family").to_numpy(dtype=float)
    return np.column_stack([numeric, amps, topo, family])


def waveform_features(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    scalar = p04h.scalar_wave_features(frame, wave)
    return np.column_stack([wave.reshape(len(wave), -1), scalar])


def fit_log_model(model, x_train: np.ndarray, y_train: np.ndarray, x_eval: np.ndarray) -> np.ndarray:
    model.fit(x_train, np.log(np.maximum(y_train, 1.0)))
    return np.exp(model.predict(x_eval))


def fractional_residual(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    return np.abs(pred - y) / np.maximum(y, 1.0)


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_25pct_rate": float(np.mean(np.abs(frac) < 0.25)),
    }


def quantile_from_calibration(
    cal_frame: pd.DataFrame,
    cal_resid: np.ndarray,
    eval_frame: pd.DataFrame,
    level: float,
    min_rows: int,
) -> np.ndarray:
    q_global = float(np.percentile(cal_resid, 100.0 * level))
    by_cell: Dict[str, float] = {}
    for cell, idx in cal_frame.groupby("support_cell", observed=True).groups.items():
        local = cal_resid[np.asarray(list(idx), dtype=int)]
        if len(local) >= min_rows:
            by_cell[str(cell)] = float(np.percentile(local, 100.0 * level))
    by_group: Dict[Tuple[str, str], float] = {}
    for key, idx in cal_frame.groupby(["topology_pattern", "b2_amp_bin"], observed=True).groups.items():
        local = cal_resid[np.asarray(list(idx), dtype=int)]
        if len(local) >= min_rows:
            by_group[(str(key[0]), str(key[1]))] = float(np.percentile(local, 100.0 * level))
    vals = []
    for row in eval_frame.itertuples(index=False):
        cell = str(row.support_cell)
        key = (str(row.topology_pattern), str(row.b2_amp_bin))
        vals.append(by_cell.get(cell, by_group.get(key, q_global)))
    return np.asarray(vals, dtype=float)


def family_median_predict(train: pd.DataFrame, eval_frame: pd.DataFrame) -> np.ndarray:
    global_median = float(np.median(train["target_a_charge"].to_numpy(dtype=float)))
    med = train.groupby("run_family", observed=True)["target_a_charge"].median().to_dict()
    return eval_frame["run_family"].map(lambda family: float(med.get(str(family), global_median))).to_numpy(dtype=float)


def fit_models(config: dict, frame: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    work = frame.reset_index(drop=True).copy()
    y = work["target_a_charge"].to_numpy(dtype=float)
    runs = np.asarray(sorted(work["run"].unique()), dtype=int)

    x_peak = frozen_peak_features(work)
    x_integral = integral_topology_features(work)
    x_scalar = p04h.scalar_wave_features(work, wave)
    x_wave = waveform_features(work, wave)
    x_topology = topology_matrix(work)

    for method in ALL_METHODS:
        work[f"pred_{method}"] = np.nan
    for method in INTERVAL_METHODS:
        for level_name in ["68", "90"]:
            work[f"q{level_name}_{method}"] = np.nan
            work[f"cover{level_name}_{method}"] = False

    fold_rows = []
    for heldout_run in runs:
        print(f"  P04j fold heldout run {int(heldout_run)}", flush=True)
        held_mask = work["run"].to_numpy() == int(heldout_run)
        cal_runs = assign_calibration_runs(runs, int(heldout_run), float(config["calibration_run_fraction"]))
        cal_mask = np.isin(work["run"].to_numpy(), cal_runs)
        fit_mask = ~(held_mask | cal_mask)
        fit_idx = np.where(fit_mask)[0]
        cal_idx = np.where(cal_mask)[0]
        held_idx = np.where(held_mask)[0]
        if len(fit_idx) < 20 or len(cal_idx) < 20 or len(held_idx) == 0:
            continue

        if len(fit_idx) > int(config["ml_max_train_rows"]):
            ml_fit_idx = rng.choice(fit_idx, size=int(config["ml_max_train_rows"]), replace=False)
        else:
            ml_fit_idx = fit_idx

        cal_frame = work.iloc[cal_idx].reset_index(drop=True)
        held_frame = work.iloc[held_idx].reset_index(drop=True)
        train_frame = work.iloc[fit_idx].reset_index(drop=True)
        train_wave = wave[fit_idx]
        cal_wave = wave[cal_idx]
        held_wave = wave[held_idx]

        model_specs = {
            "frozen_peak_loglinear": (
                make_pipeline(StandardScaler(), Ridge(alpha=3.0)),
                x_peak[fit_idx],
                x_peak[cal_idx],
                x_peak[held_idx],
                fit_idx,
            ),
            "integral_topology_ridge": (
                make_pipeline(StandardScaler(), Ridge(alpha=8.0)),
                x_integral[fit_idx],
                x_integral[cal_idx],
                x_integral[held_idx],
                fit_idx,
            ),
            "support_huber": (
                make_pipeline(StandardScaler(), HuberRegressor(alpha=0.004, epsilon=1.35, max_iter=400)),
                x_scalar[fit_idx],
                x_scalar[cal_idx],
                x_scalar[held_idx],
                fit_idx,
            ),
        }

        for method, (model, x_fit, x_cal, x_held, y_idx) in model_specs.items():
            pred_cal = fit_log_model(model, x_fit, y[y_idx], x_cal)
            pred_held = np.exp(model.predict(x_held))
            work.loc[held_idx, f"pred_{method}"] = pred_held
            cal_resid = fractional_residual(y[cal_idx], pred_cal)
            for level_name, level in [("68", 0.68), ("90", 0.90)]:
                q = quantile_from_calibration(cal_frame, cal_resid, held_frame, level, int(config["min_stratum_calibration_rows"]))
                work.loc[held_idx, f"q{level_name}_{method}"] = q
                work.loc[held_idx, f"cover{level_name}_{method}"] = fractional_residual(y[held_idx], pred_held) <= q

        x_template_fit = np.column_stack([x_scalar[fit_idx], p04h.template_diagnostics(train_frame, train_wave, train_frame, train_wave)])
        x_template_cal = np.column_stack([x_scalar[cal_idx], p04h.template_diagnostics(train_frame, train_wave, cal_frame, cal_wave)])
        x_template_held = np.column_stack([x_scalar[held_idx], p04h.template_diagnostics(train_frame, train_wave, held_frame, held_wave)])
        template_model = make_pipeline(StandardScaler(), Ridge(alpha=12.0))
        pred_cal = fit_log_model(template_model, x_template_fit, y[fit_idx], x_template_cal)
        pred_held = np.exp(template_model.predict(x_template_held))
        work.loc[held_idx, "pred_adaptive_template_ridge"] = pred_held
        cal_resid = fractional_residual(y[cal_idx], pred_cal)
        for level_name, level in [("68", 0.68), ("90", 0.90)]:
            q = quantile_from_calibration(cal_frame, cal_resid, held_frame, level, int(config["min_stratum_calibration_rows"]))
            work.loc[held_idx, f"q{level_name}_adaptive_template_ridge"] = q
            work.loc[held_idx, f"cover{level_name}_adaptive_template_ridge"] = fractional_residual(y[held_idx], pred_held) <= q

        ml_model = ExtraTreesRegressor(
            n_estimators=160,
            max_depth=8,
            min_samples_leaf=4,
            max_features=0.7,
            n_jobs=-1,
            random_state=int(config["random_seed"]) + int(heldout_run),
        )
        ml_model.fit(x_wave[ml_fit_idx], np.log(np.maximum(y[ml_fit_idx], 1.0)))
        pred_cal = np.exp(ml_model.predict(x_wave[cal_idx]))
        pred_held = np.exp(ml_model.predict(x_wave[held_idx]))
        work.loc[held_idx, "pred_b_waveform_extra_trees"] = pred_held
        cal_resid = fractional_residual(y[cal_idx], pred_cal)
        for level_name, level in [("68", 0.68), ("90", 0.90)]:
            q = quantile_from_calibration(cal_frame, cal_resid, held_frame, level, int(config["min_stratum_calibration_rows"]))
            work.loc[held_idx, f"q{level_name}_b_waveform_extra_trees"] = q
            work.loc[held_idx, f"cover{level_name}_b_waveform_extra_trees"] = fractional_residual(y[held_idx], pred_held) <= q

        topology_model = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        work.loc[held_idx, "pred_topology_only_sentinel"] = fit_log_model(
            topology_model, x_topology[fit_idx], y[fit_idx], x_topology[held_idx]
        )
        work.loc[held_idx, "pred_run_family_sentinel"] = family_median_predict(work.iloc[fit_idx], held_frame)

        shuffled = np.log(np.maximum(y[ml_fit_idx], 1.0)).copy()
        rng.shuffle(shuffled)
        shuffled_model = ExtraTreesRegressor(
            n_estimators=80,
            max_depth=8,
            min_samples_leaf=4,
            max_features=0.7,
            n_jobs=-1,
            random_state=700 + int(heldout_run),
        )
        shuffled_model.fit(x_wave[ml_fit_idx], shuffled)
        work.loc[held_idx, "pred_shuffled_target_extra_trees"] = np.exp(shuffled_model.predict(x_wave[held_idx]))

        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "heldout_rows": int(len(held_idx)),
                "fit_rows": int(len(fit_idx)),
                "calibration_rows": int(len(cal_idx)),
                "calibration_runs": " ".join(str(int(run)) for run in cal_runs),
                "train_heldout_run_overlap": int(np.intersect1d(work.loc[fit_idx, "run"].unique(), [heldout_run]).size),
            }
        )

    return work, pd.DataFrame(fold_rows)


def method_metrics(frame: pd.DataFrame, method: str, abstain_threshold: float) -> dict:
    y = frame["target_a_charge"].to_numpy(dtype=float)
    pred = frame[f"pred_{method}"].to_numpy(dtype=float)
    row = {"method": method}
    row.update(robust_metrics(y, pred))
    if f"q68_{method}" in frame:
        q68 = frame[f"q68_{method}"].to_numpy(dtype=float)
        q90 = frame[f"q90_{method}"].to_numpy(dtype=float)
        finite = np.isfinite(q90)
        keep = finite & (q90 <= float(abstain_threshold))
        row.update(
            {
                "coverage68": float(frame[f"cover68_{method}"].mean()),
                "mean_width68_frac": float(np.mean(2.0 * q68)),
                "coverage90": float(frame[f"cover90_{method}"].mean()),
                "mean_width90_frac": float(np.mean(2.0 * q90)),
                "abstention_threshold_width90_frac": float(abstain_threshold),
                "abstention_rate": float(1.0 - np.mean(keep)),
                "retained_n": int(np.sum(keep)),
                "retained_coverage90": float(frame.loc[keep, f"cover90_{method}"].mean()) if np.any(keep) else None,
                "retained_res68_abs_frac": robust_metrics(y[keep], pred[keep])["res68_abs_frac"] if np.any(keep) else None,
                "retained_within_25pct_rate": robust_metrics(y[keep], pred[keep])["within_25pct_rate"] if np.any(keep) else None,
            }
        )
    else:
        row.update(
            {
                "coverage68": None,
                "mean_width68_frac": None,
                "coverage90": None,
                "mean_width90_frac": None,
                "abstention_threshold_width90_frac": None,
                "abstention_rate": None,
                "retained_n": None,
                "retained_coverage90": None,
                "retained_res68_abs_frac": None,
                "retained_within_25pct_rate": None,
            }
        )
    return row


def summarize_methods(config: dict, frame: pd.DataFrame) -> pd.DataFrame:
    threshold = float(config["abstention_width_thresholds"][1])
    rows = []
    for method in ALL_METHODS:
        row = method_metrics(frame, method, threshold)
        if method == "b_waveform_extra_trees":
            row["method_family"] = "ml"
        elif "sentinel" in method or "shuffled" in method:
            row["method_family"] = "sentinel"
        else:
            row["method_family"] = "traditional"
        rows.append(row)
    return pd.DataFrame(rows)


def run_block_bootstrap(config: dict, frame: pd.DataFrame, methods: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 1001)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {run: frame[frame["run"] == run] for run in runs}
    threshold = float(config["abstention_width_thresholds"][1])
    metric_names = [
        "bias_median_frac",
        "res68_abs_frac",
        "full_rms_frac",
        "within_25pct_rate",
        "coverage68",
        "mean_width68_frac",
        "coverage90",
        "mean_width90_frac",
        "abstention_rate",
        "retained_coverage90",
    ]
    samples: Dict[str, Dict[str, List[float]]] = {method: {metric: [] for metric in metric_names} for method in methods}
    deltas: Dict[str, List[float]] = {metric: [] for metric in metric_names}
    for _ in range(int(config["bootstrap_reps"])):
        boot = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        got = {method: method_metrics(boot, method, threshold) for method in methods}
        for method, row in got.items():
            for metric in metric_names:
                val = row.get(metric)
                if val is not None and np.isfinite(val):
                    samples[method][metric].append(float(val))
        ml = got["b_waveform_extra_trees"]
        trad = got["adaptive_template_ridge"]
        for metric in metric_names:
            mval = ml.get(metric)
            tval = trad.get(metric)
            if mval is not None and tval is not None and np.isfinite(mval) and np.isfinite(tval):
                deltas[metric].append(float(mval) - float(tval))

    ci_rows = []
    for method, metrics in samples.items():
        for metric, vals in metrics.items():
            if vals:
                ci_rows.append(
                    {
                        "method": method,
                        "metric": metric,
                        "ci95_low": float(np.percentile(vals, 2.5)),
                        "ci95_high": float(np.percentile(vals, 97.5)),
                    }
                )
    delta_rows = []
    for metric, vals in deltas.items():
        if vals:
            delta_rows.append(
                {
                    "delta": "ml_minus_adaptive_template",
                    "metric": metric,
                    "ci95_low": float(np.percentile(vals, 2.5)),
                    "ci95_high": float(np.percentile(vals, 97.5)),
                    "point_delta": float(
                        method_metrics(frame, "b_waveform_extra_trees", threshold)[metric]
                        - method_metrics(frame, "adaptive_template_ridge", threshold)[metric]
                    ),
                }
            )
    return pd.DataFrame(ci_rows), pd.DataFrame(delta_rows)


def abstention_curve(config: dict, frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    y = frame["target_a_charge"].to_numpy(dtype=float)
    for method in ["adaptive_template_ridge", "support_huber", "b_waveform_extra_trees"]:
        pred = frame[f"pred_{method}"].to_numpy(dtype=float)
        q90 = frame[f"q90_{method}"].to_numpy(dtype=float)
        for threshold in config["abstention_width_thresholds"]:
            keep = np.isfinite(q90) & (q90 <= float(threshold))
            row = {
                "method": method,
                "max_half_width90_frac": float(threshold),
                "retained_n": int(np.sum(keep)),
                "abstention_rate": float(1.0 - np.mean(keep)),
            }
            if np.any(keep):
                row.update(robust_metrics(y[keep], pred[keep]))
                row["coverage90"] = float(frame.loc[keep, f"cover90_{method}"].mean())
                row["mean_width90_frac"] = float(np.mean(2.0 * q90[keep]))
            else:
                row.update({"bias_median_frac": None, "res68_abs_frac": None, "full_rms_frac": None, "within_25pct_rate": None})
                row["coverage90"] = None
                row["mean_width90_frac"] = None
            rows.append(row)
    return pd.DataFrame(rows)


def support_summary(config: dict, frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for category in ["topology_pattern", "b2_amp_bin", "saturation_stratum", "anomaly_stratum", "downstream_coincidence", "support_cell"]:
        for value, sub in frame.groupby(category, observed=True):
            if len(sub) < int(config["min_support_rows"]):
                continue
            trad = method_metrics(sub, "adaptive_template_ridge", float(config["abstention_width_thresholds"][1]))
            ml = method_metrics(sub, "b_waveform_extra_trees", float(config["abstention_width_thresholds"][1]))
            enough = len(sub) >= int(config["strong_support_rows"]) and sub["run"].nunique() >= int(config["strong_support_runs"])
            calibrated = ml["coverage90"] is not None and ml["coverage90"] >= 0.84 and ml["mean_width90_frac"] <= 2.0
            rows.append(
                {
                    "stratum_category": category,
                    "stratum": str(value),
                    "n": int(len(sub)),
                    "n_runs": int(sub["run"].nunique()),
                    "traditional_res68_abs_frac": trad["res68_abs_frac"],
                    "traditional_coverage90": trad["coverage90"],
                    "traditional_width90_frac": trad["mean_width90_frac"],
                    "ml_res68_abs_frac": ml["res68_abs_frac"],
                    "ml_coverage90": ml["coverage90"],
                    "ml_width90_frac": ml["mean_width90_frac"],
                    "ml_minus_traditional_res68": ml["res68_abs_frac"] - trad["res68_abs_frac"],
                    "support_call": "calibrated_candidate" if enough and calibrated else "support_only_or_broad" if enough else "low_support",
                }
            )
    return pd.DataFrame(rows).sort_values(["stratum_category", "n"], ascending=[True, False])


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    ab_counts: pd.DataFrame,
    p04c_summary: pd.DataFrame,
    method_table: pd.DataFrame,
    delta_ci: pd.DataFrame,
    abstain: pd.DataFrame,
    support: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    p04c_trad = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    p04c_ml = p04c_summary[p04c_summary["method"] == "b_waveform_extra_trees"].iloc[0]
    display_methods = [
        "frozen_peak_loglinear",
        "integral_topology_ridge",
        "adaptive_template_ridge",
        "support_huber",
        "b_waveform_extra_trees",
        "topology_only_sentinel",
        "run_family_sentinel",
        "shuffled_target_extra_trees",
    ]
    head = method_table[method_table["method"].isin(display_methods)].copy()
    delta_keep = delta_ci[delta_ci["metric"].isin(["res68_abs_frac", "coverage90", "mean_width90_frac", "abstention_rate"])]
    abstain_keep = abstain[abstain["method"].isin(["adaptive_template_ridge", "b_waveform_extra_trees"])]
    support_keep = support[support["stratum_category"] != "support_cell"].head(20)

    lines = [
        "# P04j Charge-Transfer Conformal Uncertainty Calibration",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.",
        "- **Split:** held-out run predictions; conformal residual quantiles use calibration runs only, never the held-out run.",
        "- **Target:** selected A1/A3 positive-lobe charge on `(run, EVT)` rows with selected B2 and selected A1 or A3.",
        "",
        "## Raw Reproduction First",
        "",
        f"B-stack S00 selected-pulse anchor: `{int(b_counts['selected_pulses'].sum()):,}` vs `{int(config['expected_b_s00_selected_pulses']):,}`.",
        "",
        a_counts[["sample", "events_with_selected", "selected_pulses", "A1", "A3"]].to_markdown(index=False),
        "",
        f"Event-matched A/B rows: `{int(ab_counts['ab_rows_b2_and_a_any'].sum()):,}` vs expected `{int(config['expected_p04c_ab_rows']):,}`. "
        f"P04c reproduces broad point-transfer res68: traditional `{p04c_trad['res68_abs_frac']:.4f}` and waveform ExtraTrees `{p04c_ml['res68_abs_frac']:.4f}`.",
        "",
        "## Point And Interval Metrics",
        "",
        head[
            [
                "method",
                "method_family",
                "n",
                "bias_median_frac",
                "res68_abs_frac",
                "full_rms_frac",
                "within_25pct_rate",
                "coverage68",
                "mean_width68_frac",
                "coverage90",
                "mean_width90_frac",
                "abstention_rate",
                "retained_coverage90",
            ]
        ].to_markdown(index=False),
        "",
        "ML-minus-adaptive-template run-block bootstrap CIs:",
        "",
        delta_keep.to_markdown(index=False),
        "",
        "## Abstention Curve",
        "",
        abstain_keep[
            [
                "method",
                "max_half_width90_frac",
                "retained_n",
                "abstention_rate",
                "coverage90",
                "mean_width90_frac",
                "res68_abs_frac",
                "within_25pct_rate",
            ]
        ].to_markdown(index=False),
        "",
        "## Support/Topology Summary",
        "",
        support_keep[
            [
                "stratum_category",
                "stratum",
                "n",
                "n_runs",
                "traditional_res68_abs_frac",
                "traditional_coverage90",
                "ml_res68_abs_frac",
                "ml_coverage90",
                "ml_width90_frac",
                "support_call",
            ]
        ].to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        f"- Train/held-out run overlap: `{leakage['train_heldout_run_overlap']}`.",
        "- Conformal calibration residuals are computed on calibration runs excluded from both model fitting and held-out evaluation.",
        "- Feature matrices exclude run id, event id, A-stack selected flags, A-stack charge, and the target.",
        f"- Topology-only sentinel res68: `{leakage['topology_only_res68']:.4f}`.",
        f"- Run-family sentinel res68: `{leakage['run_family_res68']:.4f}`.",
        f"- Shuffled-target ExtraTrees res68: `{leakage['shuffled_target_res68']:.4f}`.",
        f"- Too-good flag: `{leakage['too_good_flag']}`.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `astack_gate_counts.csv`, "
        "`ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `p04j_method_metrics.csv`, "
        "`p04j_metric_ci.csv`, `p04j_ml_minus_traditional_ci.csv`, `p04j_abstention_curve.csv`, "
        "`p04j_support_summary.csv`, `p04j_fold_diagnostics.csv`, and `p04j_predictions.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04j_1781026226_572_6e7c10a0_conformal_uncertainty.yaml")
    args = parser.parse_args()
    t0 = time.time()

    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/6 reproducing raw B/A gates ...")
    b_counts = p04c.count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    if got_b != expected_b:
        raise RuntimeError(f"B-stack S00 gate reproduction failed: {got_b} != {expected_b}")

    a_counts = p04c.count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A-stack event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A-stack pulse gate failed for {row['sample']}")

    print("2/6 extracting event-matched A/B rows ...")
    frame, wave, ab_counts = p04c.extract_ab_rows(config)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)
    if int(ab_counts["ab_rows_b2_and_a_any"].sum()) != int(config["expected_p04c_ab_rows"]):
        raise RuntimeError("P04c A/B row-count reproduction failed")
    frame = p04h.add_support_strata(frame, wave, config)
    frame = add_run_family(config, frame)

    print("3/6 reproducing P04c point-transfer number ...")
    p04c_summary, p04c_by_run, p04c_by_amp, _p04c_leakage = p04c.fit_leave_one_run(config, frame.copy(), wave)
    p04c_summary.to_csv(out_dir / "p04c_reproduction_summary.csv", index=False)
    p04c_by_run.to_csv(out_dir / "p04c_reproduction_by_run.csv", index=False)
    p04c_by_amp.to_csv(out_dir / "p04c_reproduction_by_b2_amp.csv", index=False)

    print("4/6 fitting conformal uncertainty models ...")
    pred_frame, folds = fit_models(config, frame, wave)
    folds.to_csv(out_dir / "p04j_fold_diagnostics.csv", index=False)
    pred_cols = ["run", "evt", "run_family", "target_a_charge", "topology_pattern", "b2_amp_bin", "support_cell"]
    for method in ALL_METHODS:
        pred_cols.append(f"pred_{method}")
        if method in INTERVAL_METHODS:
            pred_cols.extend([f"q68_{method}", f"cover68_{method}", f"q90_{method}", f"cover90_{method}"])
    pred_frame[pred_cols].to_csv(out_dir / "p04j_predictions.csv", index=False)

    print("5/6 summarizing intervals, abstention, and support ...")
    method_table = summarize_methods(config, pred_frame)
    metric_ci, delta_ci = run_block_bootstrap(config, pred_frame, INTERVAL_METHODS + SENTINEL_METHODS)
    abstain = abstention_curve(config, pred_frame)
    support = support_summary(config, pred_frame)
    method_table.to_csv(out_dir / "p04j_method_metrics.csv", index=False)
    metric_ci.to_csv(out_dir / "p04j_metric_ci.csv", index=False)
    delta_ci.to_csv(out_dir / "p04j_ml_minus_traditional_ci.csv", index=False)
    abstain.to_csv(out_dir / "p04j_abstention_curve.csv", index=False)
    support.to_csv(out_dir / "p04j_support_summary.csv", index=False)

    print("6/6 writing report and manifest ...")
    trad = method_table[method_table["method"] == "adaptive_template_ridge"].iloc[0]
    ml = method_table[method_table["method"] == "b_waveform_extra_trees"].iloc[0]
    shuffle = method_table[method_table["method"] == "shuffled_target_extra_trees"].iloc[0]
    topology = method_table[method_table["method"] == "topology_only_sentinel"].iloc[0]
    family = method_table[method_table["method"] == "run_family_sentinel"].iloc[0]
    calibrated = support[support["support_call"] == "calibrated_candidate"]
    leakage = {
        "split": "held-out run; calibration residuals from separate train-run blocks",
        "features_exclude": ["run", "evt", "target_a_charge", "A1_charge", "A3_charge", "A1_selected", "A3_selected"],
        "train_heldout_run_overlap": int(folds["train_heldout_run_overlap"].max()) if len(folds) else -1,
        "topology_only_res68": float(topology["res68_abs_frac"]),
        "run_family_res68": float(family["res68_abs_frac"]),
        "shuffled_target_res68": float(shuffle["res68_abs_frac"]),
        "ml_res68": float(ml["res68_abs_frac"]),
        "too_good_flag": bool(ml["res68_abs_frac"] < 0.35 and shuffle["res68_abs_frac"] > 0.48),
    }

    if len(calibrated):
        examples = calibrated.sort_values(["ml_width90_frac", "ml_res68_abs_frac"]).head(3)["stratum"].tolist()
        finding = (
            "Conformal calibration gives high nominal coverage only by admitting very broad intervals. "
            f"The global adaptive-template traditional model has res68 {trad['res68_abs_frac']:.4f}, 90% coverage "
            f"{trad['coverage90']:.3f}, and mean 90% width {trad['mean_width90_frac']:.3f} of charge. "
            f"The ML waveform ExtraTrees model has res68 {ml['res68_abs_frac']:.4f}, coverage {ml['coverage90']:.3f}, "
            f"and width {ml['mean_width90_frac']:.3f}. Candidate calibrated strata are {examples}, but these are support-limited."
        )
    else:
        finding = (
            "Conformal calibration confirms that the external A/B charge proxy is uncertainty-dominated. "
            f"The adaptive-template traditional model has res68 {trad['res68_abs_frac']:.4f}, 90% coverage "
            f"{trad['coverage90']:.3f}, and mean 90% interval width {trad['mean_width90_frac']:.3f}; ML ExtraTrees has "
            f"res68 {ml['res68_abs_frac']:.4f}, coverage {ml['coverage90']:.3f}, and width {ml['mean_width90_frac']:.3f}. "
            f"At a half-width abstention threshold of 1.0, ML abstains on {ml['abstention_rate']:.3f} of rows. "
            f"The shuffled-target sentinel remains similar at res68 {shuffle['res68_abs_frac']:.4f}, so there is no leak-like "
            "precision gain hidden by the intervals."
        )

    result = {
        "study": "P04j",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "b_s00_pass": got_b == expected_b,
            "astack_analysis_counts": json.loads(a_counts.to_json(orient="records")),
            "ab_rows_expected": int(config["expected_p04c_ab_rows"]),
            "ab_rows_reproduced": int(ab_counts["ab_rows_b2_and_a_any"].sum()),
            "p04c_reproduction_summary": json.loads(p04c_summary.to_json(orient="records")),
        },
        "row_definition": {
            "match_key": "(run, EVT)",
            "required_source_topology": "B2 amplitude > 1000 ADC",
            "required_target_topology": "A1 or A3 amplitude > 1000 ADC",
            "target": "sum positive-lobe charge over selected A1/A3 staves",
            "features": "B-stack even-channel waveforms and charge summaries only",
        },
        "n_ab_rows": int(len(pred_frame)),
        "runs_with_rows": sorted(int(run) for run in pred_frame["run"].unique()),
        "split": "held-out by run; nested train-run conformal calibration",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "method_metrics": json.loads(method_table.to_json(orient="records")),
        "ml_minus_traditional_ci": json.loads(delta_ci.to_json(orient="records")),
        "support_call_counts": json.loads(support["support_call"].value_counts().rename_axis("support_call").reset_index(name="n").to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, ab_counts, p04c_summary, method_table, delta_ci, abstain, support, leakage, result)

    input_runs = sorted(set(p04c.configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    manifest = {
        "study": "P04j",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/p04j_1781026226_572_6e7c10a0_conformal_uncertainty.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": git_commit(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
