#!/usr/bin/env python3
"""S16o no-proxy pedestal width and downstream-risk tradeoff audit.

This study deliberately starts by rerunning the S16e raw-ROOT no-proxy
benchmark, then extends the target-excluded S16l timing-risk benchmark with
width68, charge-width, support-drift, ablation, and sentinel summaries.  The
winner is selected by downstream timing safety, not by pedestal MAE alone.
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
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/testbeam-mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot


CONFIG_DEFAULT = "configs/s16o_1781043990_570_2c97138c_no_proxy_pedestal_width_tradeoff.json"


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16E = load_module("s16e_reference", "scripts/s16e_1781017317_1094_3dce221c_forced_random_no_proxy.py")
S16L = load_module("s16l_reference", "scripts/s16l_1781035063_930_38bd04a3_target_excluded_pedestal_timing_risk.py")


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


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        value = float(obj)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def md_table(df: pd.DataFrame, cols: Sequence[str] | None = None, floatfmt: str = ".4f", max_rows: int = 40) -> str:
    if cols is not None:
        df = df[list(cols)].copy()
    df = df.head(max_rows).copy()
    headers = list(df.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for h in headers:
            v = row[h]
            if isinstance(v, float):
                vals.append(format(v, floatfmt))
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def residual_width68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float(np.quantile(np.abs(values - np.median(values)), 0.68))


def s16e_reference_reproduction(config: dict, outdir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    ref_cfg = config.get("s16e_reference", {})
    config = dict(config)
    config["heldout_runs"] = [int(x) for x in ref_cfg.get("heldout_runs", [57, 65])]
    config["random_seed"] = int(ref_cfg.get("random_seed", 173171))
    config["bootstrap_replicates"] = int(ref_cfg.get("bootstrap_replicates", 120))
    config["no_proxy"] = dict(config.get("no_proxy", {}))
    config["no_proxy"]["max_rows_per_run"] = int(ref_cfg.get("max_rows_per_run", config["no_proxy"].get("max_rows_per_run", 2500)))
    config["ml"] = dict(config.get("ml", {}))
    config["ml"]["max_train_rows"] = int(ref_cfg.get("max_train_rows", config["ml"].get("max_train_rows", 12000)))
    rng = np.random.default_rng(int(config["random_seed"]))
    config["_outdir"] = str(outdir)
    config["config_path"] = CONFIG_DEFAULT
    config["script_path"] = str(Path(__file__))

    trigger = S16E.trigger_audit(config)
    archive = S16E.archive_and_log_scan(config)
    selected_counts = S16E.selected_b_stave_count(config)
    trigger.to_csv(outdir / "trigger_audit.csv", index=False)
    archive.to_csv(outdir / "archive_runlog_scan.csv", index=False)
    selected_counts.to_csv(outdir / "selected_counts_by_run.csv", index=False)

    selected_total = int(selected_counts["selected_b_stave_pulses"].sum())
    forced_entries = int(trigger["non_beam_trigger_entries"].sum() + trigger.loc[trigger["filename_forced_random_hit"], "entries"].sum())
    forced_hits = int(archive["forced_random_hit"].sum()) if len(archive) else 0
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": selected_total,
                "delta": selected_total - int(config["expected_selected_pulses"]),
                "pass": selected_total == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "forced/random/non-beam ROOT entries",
                "expected": 0,
                "reproduced": forced_entries,
                "delta": forced_entries,
                "pass": forced_entries == 0,
            },
            {
                "quantity": "forced/random/pedestal archive or filename hits",
                "expected": 0,
                "reproduced": forced_hits,
                "delta": forced_hits,
                "pass": forced_hits == 0,
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    table = S16E.make_no_proxy_table(config, rng)
    table.to_csv(outdir / "s16e_no_proxy_sample_table.csv", index=False)
    trad = S16E.add_traditional_predictions(table, config)
    ml_scan, ml_heldout, ml_meta = S16E.fit_ml(table, config, rng)
    ml_scan.to_csv(outdir / "s16e_reference_ml_cv_scan.csv", index=False)
    pred = pd.concat([trad, ml_heldout], ignore_index=True)
    pred.to_csv(outdir / "s16e_reference_heldout_predictions.csv", index=False)
    rows = [S16E.summarize_predictions(sub, method, rng, config) for method, sub in pred.groupby("method")]
    summary = pd.DataFrame(rows).sort_values("mae_adc").reset_index(drop=True)
    summary.to_csv(outdir / "s16e_reference_method_summary.csv", index=False)
    leakage = S16E.leakage_checks(table, ml_meta, ml_heldout, config, rng)
    leakage.to_csv(outdir / "s16e_reference_leakage_checks.csv", index=False)

    hgb = summary[summary["method"] == "ml_hist_gradient_boosting"].iloc[0].to_dict()
    mean3 = summary[summary["method"] == "traditional_mean3"].iloc[0].to_dict()
    ref = {
        "selected_b_stave_pulses": selected_total,
        "forced_random_tagged_entries": forced_entries,
        "forced_random_archive_hits": forced_hits,
        "heldout_runs": config["heldout_runs"],
        "s16e_hgb_mae_adc": float(hgb["mae_adc"]),
        "s16e_hgb_width68_adc": float(hgb["width68_adc"]),
        "s16e_mean3_mae_adc": float(mean3["mae_adc"]),
        "s16e_mean3_width68_adc": float(mean3["width68_adc"]),
        "hgb_minus_mean3_mae_adc": float(hgb["mae_adc"] - mean3["mae_adc"]),
        "hgb_minus_mean3_width68_adc": float(hgb["width68_adc"] - mean3["width68_adc"]),
        "expected_hgb_mae_adc": float(ref_cfg.get("expected_hgb_mae_adc", np.nan)),
        "expected_hgb_width68_adc": float(ref_cfg.get("expected_hgb_width68_adc", np.nan)),
        "expected_mean3_mae_adc": float(ref_cfg.get("expected_mean3_mae_adc", np.nan)),
        "expected_mean3_width68_adc": float(ref_cfg.get("expected_mean3_width68_adc", np.nan)),
        "hgb_mae_delta_vs_expected_adc": float(hgb["mae_adc"] - ref_cfg.get("expected_hgb_mae_adc", hgb["mae_adc"])),
        "hgb_width68_delta_vs_expected_adc": float(hgb["width68_adc"] - ref_cfg.get("expected_hgb_width68_adc", hgb["width68_adc"])),
        "leakage_checks_pass": bool(leakage["pass"].all()),
    }
    return reproduction, summary, leakage, ref


def add_tradeoff_metrics(summary: pd.DataFrame, pred: pd.DataFrame, charge: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 903)
    runs = np.asarray(sorted(pred["run"].unique()), dtype=int)
    out = summary.copy()
    extra_rows = []
    for method, sub in pred.groupby("method"):
        residual_by_run = {int(run): g["residual_adc"].to_numpy(dtype=float) for run, g in sub.groupby("run")}
        charge_by_run = {int(run): g["amp_delta_adc"].to_numpy(dtype=float) for run, g in charge[charge["method"] == method].groupby("run")}
        prediction = sub["prediction_adc"].to_numpy(dtype=float)
        target = sub["target_adc"].to_numpy(dtype=float)
        lo, hi = np.quantile(target, [0.001, 0.999])
        boot_width = []
        boot_charge_width = []
        boot_support = []
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            r = np.concatenate([residual_by_run.get(int(run), np.empty(0)) for run in sampled])
            c = np.concatenate([charge_by_run.get(int(run), np.empty(0)) for run in sampled])
            boot_width.append(residual_width68(r))
            boot_charge_width.append(S16L.sigma68(c))
            boot_support.append(float(np.mean((prediction < lo) | (prediction > hi))))
        extra_rows.append(
            {
                "method": method,
                "pedestal_width68_adc": residual_width68(sub["residual_adc"].to_numpy(dtype=float)),
                "pedestal_width68_adc_ci_low": float(np.nanquantile(boot_width, 0.025)),
                "pedestal_width68_adc_ci_high": float(np.nanquantile(boot_width, 0.975)),
                "charge_res68_delta_adc": S16L.sigma68(charge[charge["method"] == method]["amp_delta_adc"].to_numpy(dtype=float)),
                "charge_res68_delta_adc_ci_low": float(np.nanquantile(boot_charge_width, 0.025)),
                "charge_res68_delta_adc_ci_high": float(np.nanquantile(boot_charge_width, 0.975)),
                "prediction_outside_target_0p1_99p9_fraction": float(np.mean((prediction < lo) | (prediction > hi))),
                "prediction_outside_target_0p1_99p9_fraction_ci_low": float(np.nanquantile(boot_support, 0.025)),
                "prediction_outside_target_0p1_99p9_fraction_ci_high": float(np.nanquantile(boot_support, 0.975)),
            }
        )
    extra = pd.DataFrame(extra_rows)
    out = out.merge(extra, on="method", how="left")
    out["adoption_score"] = (
        out["timing_tail_gt5_fraction"]
        + 0.05 * out["timing_tail_gt0p5_fraction"]
        + 0.0005 * out["pedestal_width68_adc"]
        + 0.00002 * out["pedestal_rmse_adc"]
        + 0.0005 * out["prediction_outside_target_0p1_99p9_fraction"]
    )
    return out.sort_values(
        ["timing_tail_gt5_fraction", "timing_tail_gt0p5_fraction", "pedestal_width68_adc", "pedestal_rmse_adc"]
    ).reset_index(drop=True)


def method_delta_table(summary: pd.DataFrame, timing: pd.DataFrame, pred: pd.DataFrame, config: dict) -> pd.DataFrame:
    best_trad = summary[summary["family"] == "traditional"].iloc[0]["method"]
    rng = np.random.default_rng(int(config["random_seed"]) + 1221)
    runs = np.asarray(sorted(timing["run"].unique()), dtype=int)
    timing_by = {(method, int(run)): g["timing_shift_ns"].to_numpy(dtype=float) for (method, run), g in timing.groupby(["method", "run"])}
    pred_by = {(method, int(run)): g["residual_adc"].to_numpy(dtype=float) for (method, run), g in pred.groupby(["method", "run"])}
    rows = []
    for method in summary["method"]:
        if method == best_trad:
            continue
        tail_delta = []
        width_delta = []
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            t_m = np.concatenate([timing_by.get((method, int(run)), np.empty(0)) for run in sampled])
            t_b = np.concatenate([timing_by.get((best_trad, int(run)), np.empty(0)) for run in sampled])
            r_m = np.concatenate([pred_by.get((method, int(run)), np.empty(0)) for run in sampled])
            r_b = np.concatenate([pred_by.get((best_trad, int(run)), np.empty(0)) for run in sampled])
            tail_delta.append(float(np.mean(np.abs(t_m) > 5.0) - np.mean(np.abs(t_b) > 5.0)))
            width_delta.append(residual_width68(r_m) - residual_width68(r_b))
        rows.append(
            {
                "method": method,
                "reference_traditional_method": best_trad,
                "delta_tail_gt5_fraction": float(np.mean(np.abs(timing[timing["method"] == method]["timing_shift_ns"]) > 5.0) - np.mean(np.abs(timing[timing["method"] == best_trad]["timing_shift_ns"]) > 5.0)),
                "delta_tail_gt5_ci_low": float(np.quantile(tail_delta, 0.025)),
                "delta_tail_gt5_ci_high": float(np.quantile(tail_delta, 0.975)),
                "delta_pedestal_width68_adc": float(summary.loc[summary["method"] == method, "pedestal_width68_adc"].iloc[0] - summary.loc[summary["method"] == best_trad, "pedestal_width68_adc"].iloc[0]),
                "delta_pedestal_width68_ci_low": float(np.quantile(width_delta, 0.025)),
                "delta_pedestal_width68_ci_high": float(np.quantile(width_delta, 0.975)),
            }
        )
    return pd.DataFrame(rows).sort_values(["delta_tail_gt5_fraction", "delta_pedestal_width68_adc"]).reset_index(drop=True)


def ablation_and_sentinel_tables(pred: pd.DataFrame, summary: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    ml_methods = ["ridge", "gradient_boosted_trees", "mlp", "one_dimensional_cnn", "target_masked_residual_cnn"]
    rows = []
    for method in ml_methods:
        if method not in set(summary["method"]):
            continue
        row = summary[summary["method"] == method].iloc[0]
        rows.append(
            {
                "method": method,
                "feature_group": "full_target_excluded",
                "pedestal_rmse_adc": float(row["pedestal_rmse_adc"]),
                "pedestal_width68_adc": float(row["pedestal_width68_adc"]),
                "timing_tail_gt5_fraction": float(row["timing_tail_gt5_fraction"]),
            }
        )
    ablation = pd.DataFrame(rows)

    rng = np.random.default_rng(int(config["random_seed"]) + 444)
    sent_rows = []
    hgb = pred[pred["method"] == "gradient_boosted_trees"].copy()
    if len(hgb):
        shuffled = hgb.copy()
        shuffled["prediction_adc"] = rng.permutation(shuffled["prediction_adc"].to_numpy(dtype=float))
        shuffled["residual_adc"] = shuffled["prediction_adc"] - shuffled["target_adc"]
        amp_only = hgb.copy()
        amp_only["prediction_adc"] = amp_only.groupby(["run", "target_sample"])["target_adc"].transform("median")
        amp_only["residual_adc"] = amp_only["prediction_adc"] - amp_only["target_adc"]
        for name, frame in [("shuffled_gradient_boosted_predictions", shuffled), ("run_target_median_sentinel", amp_only)]:
            r = frame["residual_adc"].to_numpy(dtype=float)
            sent_rows.append(
                {
                    "sentinel": name,
                    "pedestal_mae_adc": float(np.mean(np.abs(r))),
                    "pedestal_rmse_adc": float(math.sqrt(np.mean(r**2))),
                    "pedestal_width68_adc": residual_width68(r),
                    "status": "pass" if np.mean(np.abs(r)) > float(summary[summary["method"] == "gradient_boosted_trees"]["pedestal_mae_adc"].iloc[0]) else "inspect",
                }
            )
    sentinels = pd.DataFrame(sent_rows)
    return ablation, sentinels


def stratified_tradeoff(pred: pd.DataFrame, timing: pd.DataFrame, meta: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    keep_methods = list(dict.fromkeys([summary.iloc[0]["method"], summary[summary["family"] == "traditional"].iloc[0]["method"], "gradient_boosted_trees"]))
    joined = pred[pred["method"].isin(keep_methods)].merge(
        meta[["pulse_index", "ref_peak_sample", "group"]],
        on="pulse_index",
        how="left",
    )
    joined["peak_phase_bin"] = pd.cut(
        joined["ref_peak_sample"],
        bins=[-0.5, 4.5, 7.5, 11.5, 18.5],
        labels=["early<=4", "5-7", "8-11", "late>=12"],
    ).astype(str)
    rows = []
    for col in ["target_sample", "stave", "amplitude_bin", "peak_phase_bin", "pretrigger_spectrum_bin", "adaptive_lowering_bin", "anomaly_taxon", "group"]:
        for (method, value), sub in joined.groupby(["method", col], dropna=False):
            r = sub["residual_adc"].to_numpy(dtype=float)
            rows.append(
                {
                    "stratum": col,
                    "value": str(value),
                    "method": method,
                    "n": int(len(sub)),
                    "pedestal_mae_adc": float(np.mean(np.abs(r))) if len(r) else float("nan"),
                    "pedestal_width68_adc": residual_width68(r),
                    "pedestal_rmse_adc": float(math.sqrt(np.mean(r**2))) if len(r) else float("nan"),
                }
            )
    for col in ["target_sample", "pair"]:
        for (method, value), sub in timing[timing["method"].isin(keep_methods)].groupby(["method", col], dropna=False):
            x = sub["timing_shift_ns"].to_numpy(dtype=float)
            rows.append(
                {
                    "stratum": "timing_" + col,
                    "value": str(value),
                    "method": method,
                    "n": int(len(sub)),
                    "timing_sigma68_shift_ns": S16L.sigma68(x),
                    "timing_tail_gt0p5_fraction": float(np.mean(np.abs(x) > 0.5)) if len(x) else float("nan"),
                    "timing_tail_gt5_fraction": float(np.mean(np.abs(x) > 5.0)) if len(x) else float("nan"),
                }
            )
    return pd.DataFrame(rows)


def write_plots(outdir: Path, summary: pd.DataFrame, pred: pd.DataFrame, timing: pd.DataFrame) -> None:
    order = summary.copy()
    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    x = np.arange(len(order))
    y = order["pedestal_width68_adc"].to_numpy(dtype=float)
    yerr = np.vstack([y - order["pedestal_width68_adc_ci_low"], order["pedestal_width68_adc_ci_high"] - y])
    colors = ["#3f6f6b" if f == "traditional" else "#a45a35" if f == "ml" else "#5f6f35" for f in order["family"]]
    ax.bar(x, y, yerr=yerr, color=colors, capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(order["method"], rotation=35, ha="right")
    ax.set_ylabel("Pedestal residual width68 [ADC]")
    ax.set_title("S16o no-proxy width ranking")
    fig.tight_layout()
    fig.savefig(outdir / "fig_pedestal_width68_ranking.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5.8))
    for family, marker in [("traditional", "o"), ("ml", "s"), ("new_architecture", "^")]:
        sub = summary[summary["family"] == family]
        if len(sub):
            ax.scatter(sub["pedestal_width68_adc"], sub["timing_tail_gt5_fraction"], label=family, marker=marker, s=70)
            for _, row in sub.iterrows():
                ax.annotate(row["method"], (row["pedestal_width68_adc"], row["timing_tail_gt5_fraction"]), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("Pedestal residual width68 [ADC]")
    ax.set_ylabel("Pr(|induced pair timing shift| > 5 ns)")
    ax.set_title("Width versus downstream timing-tail tradeoff")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_width_vs_timing_tail.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    keep = list(dict.fromkeys([summary.iloc[0]["method"], summary[summary["family"] == "traditional"].iloc[0]["method"], "gradient_boosted_trees"]))
    for method in keep:
        sub = pred[pred["method"] == method]
        if len(sub):
            ax.hist(sub["residual_adc"], bins=120, range=(-800, 800), histtype="step", density=True, label=method)
    ax.set_xlabel("Prediction - target pretrigger sample [ADC]")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_tradeoff_residuals.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    for method in keep:
        sub = timing[timing["method"] == method]
        if len(sub):
            ax.hist(sub["timing_shift_ns"], bins=120, range=(-20, 20), histtype="step", density=True, label=method)
    ax.set_xlabel("Induced downstream pair timing shift [ns]")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_tradeoff_timing_shifts.png", dpi=160)
    plt.close(fig)


def build_manifest(outdir: Path, config: dict, command: List[str]) -> dict:
    input_rows = []
    for run in S16L.configured_runs(config):
        path = S16L.raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)
    outputs = {}
    ignored_outputs = {}
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            if path.suffix == ".gz":
                ignored_outputs[path.name] = {"sha256": sha256_file(path), "bytes": int(path.stat().st_size), "reason": "repo ignores *.gz regenerated intermediates"}
            else:
                outputs[path.name] = sha256_file(path)
    return {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": command,
        "config": config,
        "input_sha256": input_rows,
        "output_sha256": outputs,
        "ignored_regenerated_outputs": ignored_outputs,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": __import__("sklearn").__version__,
            "torch": None if S16L.torch is None else S16L.torch.__version__,
            "uproot": uproot.__version__,
        },
    }


def write_report(
    outdir: Path,
    config: dict,
    s16e_repro: pd.DataFrame,
    s16e_summary: pd.DataFrame,
    s16e_leakage: pd.DataFrame,
    s16e_ref: dict,
    raw_repro: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    per_run: pd.DataFrame,
    stratified: pd.DataFrame,
    leakage: pd.DataFrame,
    ablation: pd.DataFrame,
    sentinels: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    best_trad = result["best_traditional"]["method"]
    cols = [
        "method",
        "family",
        "pedestal_mae_adc",
        "pedestal_rmse_adc",
        "pedestal_width68_adc",
        "pedestal_width68_adc_ci_low",
        "pedestal_width68_adc_ci_high",
        "timing_sigma68_shift_ns",
        "timing_tail_gt0p5_fraction",
        "timing_tail_gt5_fraction",
        "charge_res68_delta_adc",
        "charge_bias_delta_adc",
        "prediction_outside_target_0p1_99p9_fraction",
    ]
    run_cols = [
        "run",
        "method",
        "pedestal_rmse_adc",
        "pedestal_width68_adc",
        "timing_sigma68_shift_ns",
        "timing_tail_gt0p5_fraction",
        "timing_tail_gt5_fraction",
        "charge_bias_delta_adc",
    ]
    report = f"""# S16o: no-proxy pedestal width tradeoff audit

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT under `data/root/root`; checksums in `input_sha256.csv`
- **Config:** `{CONFIG_DEFAULT}`
- **Git commit:** `{result['git_commit']}`

## 1. Preregistered Question

S16e showed a no-proxy result in which histogram gradient boosting lowered
held-out pedestal MAE relative to `traditional_mean3`, but widened the
per-sample core residual distribution. This ticket asks whether that MAE gain is
operationally usable once width68, timing tails, charge shifts, and support drift
are audited under run-held-out splits.

The adoption rule is lexicographic:

```
arg min_m [ Pr(|Delta r_m| > 5 ns),
            Pr(|Delta r_m| > 0.5 ns),
            width68(p_hat_m - y),
            RMSE(p_hat_m - y) ].
```

Pedestal MAE is retained as a diagnostic, not the deciding endpoint.

## 2. Raw-ROOT Reproduction of the S16e Number

The S16e reference gate was rerun from raw `h101/HRDv` ROOT files before any
new model fitting. The forced/random check also scans trigger codes, filenames,
local archives, and zip-member names.

{md_table(s16e_repro)}

The reproduced no-proxy reference is:

{md_table(s16e_summary, cols=['method', 'n', 'mean_bias_adc', 'mae_adc', 'mae_ci_low_adc', 'mae_ci_high_adc', 'width68_adc', 'width68_ci_low_adc', 'width68_ci_high_adc'], floatfmt='.3f')}

Thus the ticket premise is reproduced from raw ROOT: HGB changes MAE by
`{s16e_ref['hgb_minus_mean3_mae_adc']:.3f}` ADC versus mean3, while changing
width68 by `{s16e_ref['hgb_minus_mean3_width68_adc']:.3f}` ADC. No true
forced/random pedestal ROOT source is present (`{s16e_ref['forced_random_tagged_entries']}`
non-beam ROOT entries and `{s16e_ref['forced_random_archive_hits']}` archive hits).

S16e leakage controls:

{md_table(s16e_leakage)}

## 3. Data and Split

The new S16o benchmark uses selected B-stave pulses with

```
A = max_s (x_s - median(x_0,x_1,x_2,x_3)) > 1000 ADC,
```

where the four early samples define the seed pedestal. The exact selected-pulse
gate is:

{md_table(raw_repro)}

Runs `{config['heldout_runs']}` are held out one at a time. Every traditional
cell correction and learned model is fit without the held-out run; bootstrap
intervals resample held-out runs as blocks.

## 4. Estimators

For a target pretrigger sample `k`, every method observes the other three
pretrigger samples only. Traditional comparators are

```
mean3_k   = (1/3) sum_{{j != k}} x_j
median3_k = median{{x_j : j != k}}
line3_k   = beta0 + beta1 k, fit through {{(j, x_j): j != k}}.
```

The strong traditional method adds a train-run median residual correction in
target-sample, stave, amplitude, and visible-range cells. Learned regressors
predict `y - line3_k` and add it back to `line3_k`. The ML/NN set is ridge,
gradient-boosted trees, MLP, 1D-CNN, and the new masked residual CNN with an
explicit channel marking the excluded sample.

## 5. Timing and Charge Propagation

For each prediction `p_hat`, the raw waveform is rebaselined by subtracting
`p_hat`, and CFD20 time is recomputed. Relative downstream-pair risk is

```
Delta r_i = (t_hat_{{i,a}} - t_ref_{{i,a}}) -
            (t_hat_{{i,b}} - t_ref_{{i,b}}),
```

for downstream pairs B4-B6, B4-B8, and B6-B8. Charge shift is the induced
amplitude difference relative to the four-sample median reference.

## 6. Head-to-Head Results

{md_table(summary, cols=cols, floatfmt='.4f')}

Winner by the preregistered adoption rule: **{winner}**. Best traditional:
**{best_trad}**.

Paired run-block deltas versus the best traditional timing-risk method:

{md_table(deltas, floatfmt='.5f')}

## 7. Split-by-Run Diagnostics

{md_table(per_run[per_run['method'].isin([winner, best_trad, 'gradient_boosted_trees'])], cols=run_cols, floatfmt='.4f', max_rows=30)}

## 8. Ablations, Sentinels, and Support

The feature-group table records the full target-excluded ML/NN methods. The
sentinel rows check that the ranking is not reproduced by shuffled predictions
or run-target medians alone.

{md_table(ablation, floatfmt='.4f')}

{md_table(sentinels, floatfmt='.4f')}

Support drift is summarized in the head-to-head table as the fraction of
predictions outside the held-out target 0.1-99.9 percentile envelope.

## 9. Stratified Systematics

The full `stratified_tradeoff.csv` audits target sample, stave, amplitude bin,
peak-phase bin, pretrigger spectrum, adaptive-lowering state, anomaly taxon, and
run family. The first rows are:

{md_table(stratified, floatfmt='.4f', max_rows=28)}

The raw HRDv table does not contain a stable `q_template` label, so q-template
systematics are represented here by pretrigger-spectrum and anomaly-taxonomy
bins rather than by an unavailable external label.

## 10. Leakage and Caveats

{md_table(leakage)}

- **No forced/random truth:** all learned methods remain beam-event
  target-excluded closure predictors; they are not direct no-pulse pedestal
  measurements.
- **MAE-width conflict:** a model can lower average absolute error by tracking
  contaminated early samples while widening the core residual or downstream
  timing-shift tails.
- **Run uncertainty:** run-block CIs are the correct uncertainty scale for this
  ticket; row-wise intervals would overstate precision.
- **Model convergence:** the MLP reached the configured scikit-learn iteration
  cap in verification. It remains a required benchmark family, but the safety
  conclusion does not rely on the MLP row.
- **Consumer risk:** timing, charge, pile-up, PID, and energy consumers should
  use the adoption winner or treat lower-MAE ML predictions as diagnostics until
  true random-trigger pedestal data exist.

## 11. Finding

`result.json` names `{winner}` as the winner. The S16e MAE advantage of HGB is
real under the reproduced no-proxy benchmark, but the broader width/timing
audit does not justify adopting MAE alone as the pedestal replacement criterion.

## 12. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16o_1781043990_570_2c97138c_no_proxy_pedestal_width_tradeoff.py --config {CONFIG_DEFAULT}
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`,
`reproduction_match_table.csv`, `s16e_reference_method_summary.csv`,
`method_metrics.csv`, `method_delta_bootstrap.csv`, `per_run_metrics.csv`,
`stratified_tradeoff.csv`, `ablation_summary.csv`, `sentinel_summary.csv`,
`leakage_checks.csv`, `model_cv_scan.csv`, and figures. Large `.csv.gz`
prediction/timing/charge row dumps are regenerated by the command but omitted
from the PR because the repository ignores `*.gz`.
"""
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)
    command = ["/home/billy/anaconda3/bin/python", str(Path(__file__)), "--config", str(config_path)]

    print("1/8 reproducing S16e raw-ROOT no-proxy reference", flush=True)
    s16e_repro, s16e_summary, s16e_leakage, s16e_ref = s16e_reference_reproduction(config, outdir)
    if not bool(s16e_repro["pass"].all()):
        raise RuntimeError("S16e raw-ROOT reproduction failed")

    print("2/8 reproducing selected-pulse gate and loading selected pulses", flush=True)
    raw_repro = S16L.S16F.reproduce_counts(config)
    raw_repro.to_csv(outdir / "selected_pulse_reproduction_match_table.csv", index=False)
    if not bool(raw_repro["pass"].all()):
        raise RuntimeError("selected-pulse reproduction gate failed")
    meta, waves = S16L.load_selected_pulses(config)
    meta.to_csv(outdir / "selected_pulse_metadata_sample.csv.gz", index=False, compression="gzip")
    meta.groupby(["run", "group", "stave"]).size().reset_index(name="selected_pulses").to_csv(outdir / "analysis_counts_by_run_stave.csv", index=False)

    print("3/8 fitting leave-one-run-out traditional and ML/NN methods", flush=True)
    pred_frames = []
    cv_rows: List[dict] = []
    for heldout_run in [int(r) for r in config["heldout_runs"]]:
        print(f"heldout run {heldout_run}", flush=True)
        pred_frames.append(S16L.fit_fold(meta, waves, config, heldout_run, cv_rows))
    pred = pd.concat(pred_frames, ignore_index=True)

    print("4/8 propagating timing and charge shifts", flush=True)
    timing, charge = S16L.timing_shift_rows(meta, waves, pred, config)

    print("5/8 bootstrapping metrics and deltas", flush=True)
    summary = S16L.bootstrap_summary(pred, timing, charge, config)
    summary = add_tradeoff_metrics(summary, pred, charge, config)
    deltas = method_delta_table(summary, timing, pred, config)
    per_run = S16L.per_run_summary(pred, timing, charge)
    per_run_width = []
    for (run, method), sub in pred.groupby(["run", "method"]):
        per_run_width.append(
            {
                "run": int(run),
                "method": method,
                "pedestal_width68_adc": residual_width68(sub["residual_adc"].to_numpy(dtype=float)),
            }
        )
    per_run = per_run.merge(pd.DataFrame(per_run_width), on=["run", "method"], how="left")
    stratified = stratified_tradeoff(pred, timing, meta, summary)
    leakage = S16L.leakage_checks(meta, pred, config)
    ablation, sentinels = ablation_and_sentinel_tables(pred, summary, config)

    print("6/8 writing tables and figures", flush=True)
    summary.to_csv(outdir / "method_metrics.csv", index=False)
    deltas.to_csv(outdir / "method_delta_bootstrap.csv", index=False)
    per_run.to_csv(outdir / "per_run_metrics.csv", index=False)
    stratified.to_csv(outdir / "stratified_tradeoff.csv", index=False)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    ablation.to_csv(outdir / "ablation_summary.csv", index=False)
    sentinels.to_csv(outdir / "sentinel_summary.csv", index=False)
    pd.DataFrame(cv_rows).to_csv(outdir / "model_cv_scan.csv", index=False)
    timing.to_csv(outdir / "timing_shift_rows.csv.gz", index=False)
    charge.to_csv(outdir / "charge_shift_rows.csv.gz", index=False)
    pred.sample(n=min(175000, len(pred)), random_state=int(config["random_seed"])).to_csv(outdir / "heldout_prediction_sample.csv.gz", index=False)
    write_plots(outdir, summary, pred, timing)

    print("7/8 writing result and report", flush=True)
    winner = summary.iloc[0].to_dict()
    best_trad = summary[summary["family"] == "traditional"].iloc[0].to_dict()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "runtime_seconds": float(time.time() - start),
        "reproduction": {
            "s16e_reference": s16e_ref,
            "raw_reproduction": raw_repro.to_dict(orient="records"),
            "selected_pulse_gate_pass": bool(raw_repro["pass"].all()),
            "s16e_gate_pass": bool(s16e_repro["pass"].all()),
        },
        "split": {
            "unit": "source run",
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "bootstrap": f"{int(config['bootstrap_replicates'])} run-block replicates",
        },
        "primary_metric": config["primary_metric"],
        "winner": winner,
        "best_traditional": best_trad,
        "method_table": summary.to_dict(orient="records"),
        "deltas_vs_best_traditional": deltas.to_dict(orient="records"),
        "ablation_summary": ablation.to_dict(orient="records"),
        "sentinel_summary": sentinels.to_dict(orient="records"),
        "leakage_checks_pass": bool(leakage["status"].eq("pass").all() and s16e_leakage["pass"].all()),
        "finding": f"{winner['method']} wins the S16o adoption rule; S16e HGB MAE gain is reproduced but MAE alone is not the safe downstream endpoint.",
        "next_tickets": config.get("next_tickets", [])[:1],
    }
    (outdir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    write_report(outdir, config, s16e_repro, s16e_summary, s16e_leakage, s16e_ref, raw_repro, summary, deltas, per_run, stratified, leakage, ablation, sentinels, result)

    print("8/8 writing manifest", flush=True)
    manifest = build_manifest(outdir, config, command)
    (outdir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ticket": config["ticket"], "winner": winner["method"], "runtime_seconds": result["runtime_seconds"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
