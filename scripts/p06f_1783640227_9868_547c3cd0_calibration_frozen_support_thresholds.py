#!/usr/bin/env python3
"""P06f: freeze support thresholds on calibration runs before deployment scoring.

This is a deployability stress test of P06e.  P06e used equal-support
sigma-thresholds from the same held-out panel being scored.  P06f estimates
each method's sigma_hat threshold on a calibration block and applies it
unchanged to disjoint deployment runs before joining the PID and energy
consumer metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p06f-1783640227")

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02  # noqa: E402


METHOD_ORDER = ["traditional", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "phase_conformal_gated_cnn"]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    return value


def metric_summary(frame: pd.DataFrame, config: dict) -> dict:
    residual = frame["residual_ns"].to_numpy(dtype=float)
    pull = frame["pull"].to_numpy(dtype=float)
    sigma = frame["sigma_hat_ns"].to_numpy(dtype=float)
    abs_res = np.abs(residual)
    cov68 = float(np.mean(np.abs(pull) <= 1.0)) if len(frame) else float("nan")
    cov95 = float(np.mean(np.abs(pull) <= 1.96)) if len(frame) else float("nan")
    pull_width = float((np.nanpercentile(pull, 84) - np.nanpercentile(pull, 16)) / 2.0) if len(frame) else float("nan")
    sigma68 = float((np.nanpercentile(residual, 84) - np.nanpercentile(residual, 16)) / 2.0) if len(frame) else float("nan")
    ece = 0.0
    if len(frame):
        bins = pd.qcut(pd.Series(sigma).rank(method="first"), q=min(8, max(2, len(frame) // 50)), duplicates="drop")
        tmp = pd.DataFrame({"bin": bins, "cov68": np.abs(pull) <= 1.0, "cov95": np.abs(pull) <= 1.96})
        for _, group in tmp.groupby("bin", observed=False):
            weight = len(group) / len(tmp)
            ece += weight * 0.5 * (abs(float(group["cov68"].mean()) - config["nominal_coverage68"]) + abs(float(group["cov95"].mean()) - config["nominal_coverage95"]))
    loss = float(np.mean([abs(pull_width - 1.0), abs(cov68 - config["nominal_coverage68"]), abs(cov95 - config["nominal_coverage95"]), ece]))
    return {
        "n": int(len(frame)),
        "n_runs": int(frame["run"].nunique()) if len(frame) else 0,
        "sigma68_ns": sigma68,
        "full_rms_ns": float(np.sqrt(np.nanmean((residual - np.nanmean(residual)) ** 2))) if len(frame) else float("nan"),
        "tail_frac_abs_gt5ns": float(np.mean(abs_res > 5.0)) if len(frame) else float("nan"),
        "pull_width68": pull_width,
        "coverage68": cov68,
        "coverage95": cov95,
        "calibration_ece": float(ece),
        "calibration_loss": loss,
        "mean_sigma_hat_ns": float(np.nanmean(sigma)) if len(frame) else float("nan"),
    }


def bootstrap_ci(rows: pd.DataFrame, threshold: float, rng: np.random.Generator, n_boot: int, config: dict) -> dict:
    runs = np.asarray(sorted(rows["run"].unique()), dtype=int)
    samples: Dict[str, List[float]] = {k: [] for k in ["coverage68", "coverage95", "calibration_loss", "sigma68_ns", "tail_frac_abs_gt5ns", "abstain_fraction"]}
    for _ in range(n_boot):
        parts = [rows[rows["run"] == int(run)] for run in rng.choice(runs, size=len(runs), replace=True)]
        boot = pd.concat(parts, ignore_index=True)
        accepted = boot[boot["sigma_hat_ns"] <= threshold]
        stats = metric_summary(accepted, config)
        stats["abstain_fraction"] = float(1.0 - len(accepted) / max(1, len(boot)))
        for key in samples:
            samples[key].append(float(stats[key]))
    out = {"bootstrap_valid": int(n_boot)}
    for key, values in samples.items():
        arr = np.asarray(values, dtype=float)
        out[f"{key}_ci_low"] = float(np.nanpercentile(arr, 2.5))
        out[f"{key}_ci_high"] = float(np.nanpercentile(arr, 97.5))
    return out


def threshold_from_budget(rows: pd.DataFrame, budget: float) -> float:
    if float(budget) <= 0.0:
        return float("inf")
    return float(rows["sigma_hat_ns"].quantile(1.0 - float(budget)))


def calibration_frozen_interval_table(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]))
    calib_runs = {int(x) for x in config["threshold_calibration_runs"]}
    deployment_runs = {int(x) for x in config["deployment_runs"]}
    records = []
    for method, group in rows.groupby("method", sort=False):
        calib = group[group["run"].isin(calib_runs)].copy()
        deployment = group[group["run"].isin(deployment_runs)].copy()
        if calib.empty or deployment.empty:
            raise RuntimeError(f"empty calibration or deployment rows for {method}")
        for budget in config["abstention_budgets"]:
            budget = float(budget)
            threshold = threshold_from_budget(calib, budget)
            accepted = deployment[deployment["sigma_hat_ns"] <= threshold].copy()
            rec = {
                "method": method,
                "method_label": str(group["method_label"].iloc[0]),
                "threshold_policy": "calibration_frozen",
                "threshold_calibration_runs": ",".join(str(x) for x in sorted(calib_runs)),
                "deployment_runs": ",".join(str(x) for x in sorted(deployment_runs)),
                "abstention_budget": budget,
                "sigma_hat_threshold_ns": threshold,
                "calibration_abstain_fraction": float(1.0 - len(calib[calib["sigma_hat_ns"] <= threshold]) / max(1, len(calib))),
                "abstain_fraction": float(1.0 - len(accepted) / max(1, len(deployment))),
                **metric_summary(accepted, config),
            }
            rec.update(bootstrap_ci(deployment, threshold, rng, int(config["bootstrap_replicates"]), config))
            records.append(rec)
    out = pd.DataFrame(records)
    out["method"] = pd.Categorical(out["method"], METHOD_ORDER, ordered=True)
    return out.sort_values(["abstention_budget", "method"]).reset_index(drop=True)


def pooled_retrospective_interval_table(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Sensitivity table reproducing P06e-style pooled equal-support cutoffs."""
    rng = np.random.default_rng(int(config["random_seed"]) + 1)
    deployment = rows[rows["run"].isin([int(x) for x in config["deployment_runs"]])].copy()
    records = []
    for method, group in deployment.groupby("method", sort=False):
        for budget in config["abstention_budgets"]:
            threshold = threshold_from_budget(group, float(budget))
            accepted = group[group["sigma_hat_ns"] <= threshold].copy()
            rec = {
                "method": method,
                "method_label": str(group["method_label"].iloc[0]),
                "threshold_policy": "deployment_pooled_retrospective",
                "abstention_budget": float(budget),
                "sigma_hat_threshold_ns": threshold,
                "abstain_fraction": float(1.0 - len(accepted) / max(1, len(group))),
                **metric_summary(accepted, config),
            }
            rec.update(bootstrap_ci(group, threshold, rng, int(config["bootstrap_replicates"]), config))
            records.append(rec)
    out = pd.DataFrame(records)
    out["method"] = pd.Categorical(out["method"], METHOD_ORDER, ordered=True)
    return out.sort_values(["abstention_budget", "method"]).reset_index(drop=True)


def per_run_interval_table(rows: pd.DataFrame, config: dict, primary_budget: float) -> pd.DataFrame:
    thresholds = {}
    calib_runs = {int(x) for x in config["threshold_calibration_runs"]}
    deployment_runs = {int(x) for x in config["deployment_runs"]}
    for method, group in rows.groupby("method"):
        calib = group[group["run"].isin(calib_runs)]
        thresholds[method] = threshold_from_budget(calib, primary_budget)
    out = []
    deployment = rows[rows["run"].isin(deployment_runs)].copy()
    for (run, method), group in deployment.groupby(["run", "method"], sort=True):
        accepted = group[group["sigma_hat_ns"] <= thresholds[method]]
        out.append(
            {
                "run": int(run),
                "method": method,
                "method_label": str(group["method_label"].iloc[0]),
                "abstention_budget": primary_budget,
                "abstain_fraction": float(1.0 - len(accepted) / max(1, len(group))),
                **metric_summary(accepted, config),
            }
        )
    return pd.DataFrame(out).sort_values(["run", "method"]).reset_index(drop=True)


def load_consumer_rows(config: dict) -> pd.DataFrame:
    p07 = Path(config["p07k_report_dir"]) / "benchmark_summary.csv"
    p08 = Path(config["p08e_report_dir"]) / "scoreboard_by_mask.csv"
    energy = pd.read_csv(p07)
    pid = pd.read_csv(p08)
    pid = pid[pid["action_mask"] == "all_pre_action"].copy()
    rows = []
    for method, mapping in config["method_map"].items():
        e = energy[energy["method"] == mapping["energy"]].iloc[0]
        p = pid[pid["method"] == mapping["pid"]].iloc[0]
        rows.append(
            {
                "method": method,
                "energy_method": mapping["energy"],
                "pid_method": mapping["pid"],
                "energy_charge_res68": float(e["charge_res68"]),
                "energy_charge_res68_ci_low": float(e["charge_res68_ci_low"]),
                "energy_charge_res68_ci_high": float(e["charge_res68_ci_high"]),
                "energy_charge_bias": float(e["charge_bias"]),
                "energy_harm_rate": float(e["harm_rate_vs_no_correction"]),
                "energy_harm_rate_ci_low": float(e["harm_rate_vs_no_correction_ci_low"]),
                "energy_harm_rate_ci_high": float(e["harm_rate_vs_no_correction_ci_high"]),
                "energy_calibration_coverage": float(e["calibration_coverage"]),
                "pid_roc_auc": float(p["roc_auc"]),
                "pid_roc_auc_ci_low": float(p["roc_auc_ci_low"]),
                "pid_roc_auc_ci_high": float(p["roc_auc_ci_high"]),
                "pid_average_precision": float(p["average_precision"]),
                "pid_ece": float(p["ece"]),
                "pid_ece_ci_low": float(p["ece_ci_low"]),
                "pid_ece_ci_high": float(p["ece_ci_high"]),
            }
        )
    return pd.DataFrame(rows)


def score_methods(intervals: pd.DataFrame, consumers: pd.DataFrame, config: dict) -> pd.DataFrame:
    primary = intervals[np.isclose(intervals["abstention_budget"].astype(float), float(config["primary_abstention_budget"]))].copy()
    merged = primary.merge(consumers, on="method", how="left")
    w = config["winner_score"]
    merged["coverage68_error"] = (merged["coverage68"] - float(config["nominal_coverage68"])).abs()
    merged["coverage95_error"] = (merged["coverage95"] - float(config["nominal_coverage95"])).abs()
    merged["pid_auc_shortfall"] = np.maximum(0.0, float(w["pid_auc_floor"]) - merged["pid_roc_auc"])
    merged["consumer_loss"] = (
        float(w["calibration_loss_weight"]) * merged["calibration_loss"]
        + float(w["coverage68_error_weight"]) * merged["coverage68_error"]
        + float(w["coverage95_error_weight"]) * merged["coverage95_error"]
        + float(w["energy_charge_res68_weight"]) * merged["energy_charge_res68"]
        + float(w["energy_harm_rate_weight"]) * merged["energy_harm_rate"]
        + float(w["pid_ece_weight"]) * merged["pid_ece"]
        + float(w["pid_auc_shortfall_weight"]) * merged["pid_auc_shortfall"]
    )
    merged["method"] = pd.Categorical(merged["method"], METHOD_ORDER, ordered=True)
    return merged.sort_values(["consumer_loss", "method"]).reset_index(drop=True)


def coverage_improvement(intervals: pd.DataFrame) -> pd.DataFrame:
    base = intervals[np.isclose(intervals["abstention_budget"].astype(float), 0.0)][
        ["method", "coverage68", "coverage95", "calibration_loss", "tail_frac_abs_gt5ns"]
    ].rename(
        columns={
            "coverage68": "coverage68_budget0",
            "coverage95": "coverage95_budget0",
            "calibration_loss": "calibration_loss_budget0",
            "tail_frac_abs_gt5ns": "tail_frac_abs_gt5ns_budget0",
        }
    )
    out = intervals.merge(base, on="method", how="left")
    for col in ["coverage68", "coverage95", "calibration_loss", "tail_frac_abs_gt5ns"]:
        out[f"{col}_minus_budget0"] = out[col] - out[f"{col}_budget0"]
    return out


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def md_table(df: pd.DataFrame, cols: Iterable[str], digits: int = 4) -> str:
    sub = df[list(cols)].copy()
    for col in sub.columns:
        if pd.api.types.is_float_dtype(sub[col]):
            sub[col] = sub[col].map(lambda x: "" if pd.isna(x) else f"{float(x):.{digits}g}")
    return sub.to_markdown(index=False)


def write_report(out_dir: Path, config: dict, result: dict, intervals: pd.DataFrame, pooled: pd.DataFrame, scored: pd.DataFrame, consumers: pd.DataFrame, per_run: pd.DataFrame, coverage_delta: pd.DataFrame) -> None:
    winner = result["winner"]
    primary_budget = float(config["primary_abstention_budget"])
    primary_intervals = intervals[np.isclose(intervals["abstention_budget"].astype(float), primary_budget)].copy()
    lines = [
        "# P06f: calibration-run frozen support thresholds for consumer deployment",
        "",
        f"**Ticket:** `{config['ticket_id']}`  ",
        f"**Worker:** `{config['worker']}`  ",
        f"**Input raw ROOT:** `{config['raw_root_dir']}`  ",
        f"**S06b interval source:** `{config['s06b_report_dir']}`  ",
        f"**Threshold calibration runs:** {result['split']['threshold_calibration_runs']}  ",
        f"**Deployment runs:** {result['split']['deployment_runs']} with run-block bootstrap CIs  ",
        f"**Primary nominal calibration budget:** {primary_budget:.0%}",
        "",
        "## Abstract",
        "",
        "P06f tests whether the P06e consumer-score gains survive a deployable threshold policy: each method's support interval scale threshold is frozen on a calibration block before deployment rows are scored. The raw ROOT selected-pulse count is reproduced first. The frozen thresholds are then applied to disjoint deployment runs, benchmarked for a strong traditional support method and ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-conformal gated CNN, and joined to the existing PID and energy consumer scoreboards. The winner named in `result.json` is "
        f"**{winner['method']}** with composite consumer loss **{winner['consumer_loss']:.4f}** under the calibration-frozen 10% nominal threshold policy.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "The reproduction gate reads `h101/HRDv`, reshapes each event into 8 channels by 18 samples, subtracts the median of samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted amplitude above 1000 ADC.",
        "",
        md_table(pd.DataFrame(result["raw_root_reproduction"]), ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"], digits=6),
        "",
        "## Methods And Estimands",
        "",
        "For event pair residuals from S06b, `r_i = tau_{i,a} - tau_{i,b}`, with `tau_{i,s}=t_{i,s}-x_s v_TOF`. Each method supplies an interval scale `sigma_hat_i`; the pull is `z_i=r_i/sigma_hat_i`. The interval metrics are",
        "",
        "`sigma68(r) = (Q84(r)-Q16(r))/2`, `C68 = P(|z| <= 1)`, `C95 = P(|z| <= 1.96)`,",
        "",
        "and the calibration loss is `mean(|sigma68(z)-1|, |C68-0.682689|, |C95-0.95|, ECE)`, where ECE is a sigma-quantile coverage error. For method `m` and nominal budget `b`, P06f computes `theta_m(b)=Q_{1-b}({sigma_hat_i: i in calibration runs, method=m})` and applies `I(sigma_hat_i <= theta_m)` unchanged to deployment runs. The deployment abstention fraction is therefore an observed consequence, not forced to equal `b`.",
        "",
        "The strong traditional comparator is S06b's S02/S03 analytic timing plus S04-style atom robust-width interval lookup. Learned comparators are ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-conformal gated CNN. PID propagation uses P08e all-pre-action run-held-out PID metrics; energy propagation uses P07k charge-closure/action-band metrics. The method map is stored in the config and in `consumer_method_map.csv`.",
        "",
        "## Primary Calibration-Frozen 10% Benchmark",
        "",
        md_table(primary_intervals, ["method", "n", "calibration_abstain_fraction", "abstain_fraction", "sigma_hat_threshold_ns", "coverage68", "coverage68_ci_low", "coverage68_ci_high", "coverage95", "coverage95_ci_low", "coverage95_ci_high", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "sigma68_ns"], digits=5),
        "",
        "## PID And Energy Consumer Join",
        "",
        md_table(consumers, ["method", "energy_method", "energy_charge_res68", "energy_harm_rate", "pid_method", "pid_roc_auc", "pid_average_precision", "pid_ece"], digits=5),
        "",
        "## Winner Score",
        "",
        md_table(scored, ["method", "consumer_loss", "calibration_loss", "coverage68_error", "coverage95_error", "energy_charge_res68", "energy_harm_rate", "pid_roc_auc", "pid_ece"], digits=5),
        "",
        f"**Winner:** `{winner['method']}`. It is selected at the preregistered calibration-frozen {primary_budget:.0%} nominal threshold by minimum composite consumer loss, not by timing calibration alone.",
        "",
        "## Retrospective Equal-Support Comparator",
        "",
        "This table reuses the deployment rows to set an equal-support cutoff. It is not the deployment winner criterion; it quantifies how much the older P06e-style pooled thresholding helped or hurt relative to frozen calibration thresholds.",
        "",
        md_table(pooled[np.isclose(pooled["abstention_budget"].astype(float), primary_budget)], ["method", "n", "abstain_fraction", "coverage68", "coverage95", "calibration_loss", "sigma68_ns"], digits=5),
        "",
        "## Fixed-Budget Coverage Sensitivity",
        "",
        md_table(coverage_delta[coverage_delta["abstention_budget"].isin([0.0, primary_budget, 0.2])], ["method", "abstention_budget", "abstain_fraction", "coverage68", "coverage68_minus_budget0", "coverage95", "coverage95_minus_budget0", "calibration_loss", "calibration_loss_minus_budget0"], digits=5),
        "",
        "## Per-Run Stability",
        "",
        md_table(per_run.head(18), ["run", "method", "abstain_fraction", "coverage68", "coverage95", "calibration_loss", "tail_frac_abs_gt5ns"], digits=5),
        "",
        "The complete per-run table is written to `interval_by_run.csv`; the displayed rows show that the bootstrap is over runs, not IID pulse pairs.",
        "",
        "## Systematics And Caveats",
        "",
        "- The timing intervals are frozen S06b intervals. P06f tests deployable thresholding and consumer propagation, not retraining.",
        "- PID labels are P08e beamline/range enriched proxies, not hidden particle truth. Energy is a duplicate-charge closure proxy, not a calorimetric truth scale.",
        "- Upstream S06b interval rows are only available for Sample-II analysis runs. Run 64 raw ROOT counts are reproduced, but no method-level run-64 sigma_hat rows exist in the frozen upstream table; therefore this study freezes thresholds on the early analysis calibration block 58-60 and deploys to runs 61-63 and 65.",
        "- The abstention thresholds are fixed by calibration-run `sigma_hat`; they are not optimized against deployment residuals, PID, or energy scores. The deployment abstention fraction can drift away from the nominal budget.",
        "- The deployment timing interval rows provide four run blocks. Bootstrap intervals quantify finite run sensitivity and should not be read as asymptotic standard errors.",
        "- The new architecture is included because S06b already established phase/support gating as a sensible timing-interval architecture; P06f checks whether that advantage survives frozen-threshold consumer deployment.",
        "",
        "## Conclusion",
        "",
        result["finding"],
        "",
        "No new follow-up ticket is appended by this study; the direct next step would be a prospective run-64 interval-scoring release so calibration thresholds can be frozen on the nominal calibration run rather than on the available early-analysis proxy block.",
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `reproduction_match_table.csv`, `calibration_frozen_interval_summary.csv`, `retrospective_equal_support_summary.csv`, `interval_by_run.csv`, `coverage_improvement_by_budget.csv`, `consumer_method_map.csv`, `consumer_scoreboard.csv`, `winner_scoreboard.csv`, and `REPORT.md`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p06f_1783640227_9868_547c3cd0_calibration_frozen_support_thresholds.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    repro = s02.reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction failed")

    s06b_dir = Path(config["s06b_report_dir"])
    rows = pd.read_csv(s06b_dir / "pair_residual_rows_with_pulls.csv.gz")
    rows = rows[rows["method"].isin(METHOD_ORDER)].copy()
    intervals = calibration_frozen_interval_table(rows, config)
    pooled = pooled_retrospective_interval_table(rows, config)
    per_run = per_run_interval_table(rows, config, float(config["primary_abstention_budget"]))
    consumers = load_consumer_rows(config)
    scored = score_methods(intervals, consumers, config)
    deltas = coverage_improvement(intervals)

    intervals.to_csv(out_dir / "calibration_frozen_interval_summary.csv", index=False)
    pooled.to_csv(out_dir / "retrospective_equal_support_summary.csv", index=False)
    per_run.to_csv(out_dir / "interval_by_run.csv", index=False)
    consumers.to_csv(out_dir / "consumer_scoreboard.csv", index=False)
    pd.DataFrame(
        [{"method": method, **mapping} for method, mapping in config["method_map"].items()]
    ).to_csv(out_dir / "consumer_method_map.csv", index=False)
    scored.to_csv(out_dir / "winner_scoreboard.csv", index=False)
    deltas.to_csv(out_dir / "coverage_improvement_by_budget.csv", index=False)

    winner = scored.iloc[0].to_dict()
    primary_trad = scored[scored["method"].astype(str) == "traditional"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": config["raw_root_dir"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": repro.to_dict(orient="records"),
        "split": {
            "unit": "run",
            "available_interval_runs": sorted(int(x) for x in rows["run"].unique()),
            "threshold_calibration_runs": [int(x) for x in config["threshold_calibration_runs"]],
            "deployment_runs": [int(x) for x in config["deployment_runs"]],
            "bootstrap": "run-block bootstrap over deployment S06b timing runs",
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "calibration_note": config["calibration_note"],
        },
        "abstention_budgets": config["abstention_budgets"],
        "primary_abstention_budget": float(config["primary_abstention_budget"]),
        "traditional": {
            "method": "traditional",
            "consumer_loss": float(primary_trad["consumer_loss"]),
            "calibration_loss": float(primary_trad["calibration_loss"]),
            "coverage68": float(primary_trad["coverage68"]),
            "coverage95": float(primary_trad["coverage95"]),
            "energy_charge_res68": float(primary_trad["energy_charge_res68"]),
            "pid_roc_auc": float(primary_trad["pid_roc_auc"]),
        },
        "ml": {
            "methods": [m for m in METHOD_ORDER if m != "traditional"],
            "best_method": str(winner["method"]),
            "metric": "composite consumer loss at calibration-frozen support threshold",
        },
        "winner": {
            "method": str(winner["method"]),
            "method_label": str(winner["method_label"]),
            "metric": "calibration_frozen_composite_consumer_loss",
            "consumer_loss": float(winner["consumer_loss"]),
            "abstention_budget": float(winner["abstention_budget"]),
            "calibration_loss": float(winner["calibration_loss"]),
            "calibration_loss_ci": [float(winner["calibration_loss_ci_low"]), float(winner["calibration_loss_ci_high"])],
            "coverage68": float(winner["coverage68"]),
            "coverage68_ci": [float(winner["coverage68_ci_low"]), float(winner["coverage68_ci_high"])],
            "coverage95": float(winner["coverage95"]),
            "coverage95_ci": [float(winner["coverage95_ci_low"]), float(winner["coverage95_ci_high"])],
            "energy_charge_res68": float(winner["energy_charge_res68"]),
            "energy_harm_rate": float(winner["energy_harm_rate"]),
            "pid_roc_auc": float(winner["pid_roc_auc"]),
            "pid_ece": float(winner["pid_ece"]),
            "delta_consumer_loss_vs_traditional": float(winner["consumer_loss"] - primary_trad["consumer_loss"]),
        },
        "ml_beats_baseline": bool(str(winner["method"]) != "traditional" and float(winner["consumer_loss"]) < float(primary_trad["consumer_loss"])),
        "method_summary_file": "calibration_frozen_interval_summary.csv",
        "retrospective_equal_support_file": "retrospective_equal_support_summary.csv",
        "per_run_metrics_file": "interval_by_run.csv",
        "winner_scoreboard_file": "winner_scoreboard.csv",
        "consumer_scoreboard_file": "consumer_scoreboard.csv",
        "coverage_improvement_file": "coverage_improvement_by_budget.csv",
        "next_tickets": [],
        "finding": (
            f"At the calibration-frozen {float(config['primary_abstention_budget']):.0%} nominal support-threshold budget, "
            f"{winner['method']} has the lowest composite consumer loss ({float(winner['consumer_loss']):.4f}) versus "
            f"traditional {float(primary_trad['consumer_loss']):.4f}. Its timing interval calibration loss is "
            f"{float(winner['calibration_loss']):.4f} [{float(winner['calibration_loss_ci_low']):.4f}, "
            f"{float(winner['calibration_loss_ci_high']):.4f}], with PID AUC {float(winner['pid_roc_auc']):.4f} and "
            f"energy charge res68 {float(winner['energy_charge_res68']):.4f}. The result supports propagating the "
            "S06b support-conditioned gated timing intervals under a frozen deployment threshold, while keeping PID/energy "
            "interpretation proxy-limited."
        ),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 3),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, intervals, pooled, scored, consumers, per_run, deltas)
    manifest = {
        "config": str(config_path),
        "command": f"/home/billy/anaconda3/bin/python scripts/p06f_1783640227_9868_547c3cd0_calibration_frozen_support_thresholds.py --config {config_path}",
        "inputs": {
            "s06b_pair_rows": str(s06b_dir / "pair_residual_rows_with_pulls.csv.gz"),
            "p07k_benchmark": str(Path(config["p07k_report_dir"]) / "benchmark_summary.csv"),
            "p08e_scoreboard": str(Path(config["p08e_report_dir"]) / "scoreboard_by_mask.csv"),
        },
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_sec": round(time.time() - start, 3),
        "output_sha256": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(out_dir), "winner": result["winner"]["method"], "consumer_loss": result["winner"]["consumer_loss"]}, sort_keys=True))


if __name__ == "__main__":
    main()
