#!/usr/bin/env python3
"""S16k pretrigger-veto support frontier.

This ticket is a support audit on top of the immediately preceding S16f
run-held-out veto benchmark.  It rechecks the raw ROOT selected-pulse counts,
joins S16f held-out scores to raw-derived support features, scans each
train-fold threshold quantile, and chooses the lowest held-out timing-tail
fraction subject to timing-efficiency and support-drift constraints.
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
import time
from pathlib import Path
from typing import Iterable, Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/s16k_1781032083_mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
S16F_PATH = ROOT / "scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py"
METHOD_ORDER = [
    "traditional_quantile",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn1d",
    "siamese_cnn_meta",
]


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s16f = import_module(S16F_PATH, "s16f_source_for_s16k")


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    return value


def ci(values: Sequence[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def configured_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return ROOT / Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def event_uid(event_id: str) -> int:
    return int(str(event_id).split(":")[-1])


def tvd(values_a: Iterable, values_b: Iterable, categories: Sequence) -> float:
    a = np.asarray(list(values_a))
    b = np.asarray(list(values_b))
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    pa = np.asarray([(a == cat).mean() for cat in categories], dtype=float)
    pb = np.asarray([(b == cat).mean() for cat in categories], dtype=float)
    return float(0.5 * np.abs(pa - pb).sum())


def sigma68(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    q16, q84 = np.quantile(arr, [0.16, 0.84])
    return float((q84 - q16) / 2.0)


def load_source_artifacts(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    src = ROOT / Path(config["source_s16f_report_dir"])
    pred_path = src / "heldout_predictions.csv.gz"
    pair_path = src / "sample_ii_pair_table.csv.gz"
    scan_path = src / "threshold_scans.csv"
    missing = [str(path) for path in [pred_path, pair_path, scan_path] if not path.exists()]
    if missing:
        raise FileNotFoundError("missing S16f source artifacts: {}".format(", ".join(missing)))
    pred = pd.read_csv(pred_path)
    pairs = pd.read_csv(pair_path)
    scans = pd.read_csv(scan_path)
    return pred, pairs, scans


def add_support_features(pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = pairs.copy()
    frontier = config["frontier"]
    out["event_uid"] = out["event_id"].map(event_uid)
    out["event_order_proxy"] = out.groupby("run")["event_uid"].rank(pct=True, method="average")
    out["charge_bin"] = pd.cut(
        out["min_amplitude_adc"],
        bins=[float(x) for x in frontier["charge_bins_adc"]],
        labels=False,
        include_lowest=True,
        right=False,
    ).astype(int)
    out["current_proxy_bin"] = pd.cut(
        out["event_order_proxy"],
        bins=[float(x) for x in frontier["current_proxy_quantiles"]],
        labels=False,
        include_lowest=True,
    ).astype(int)
    out["saturation_proxy"] = (out["min_amplitude_adc"] >= float(frontier["saturation_proxy_adc"])).astype(int)
    out["late_peak_proxy"] = (out["max_peak_sample"] >= float(frontier["late_peak_proxy_sample"])).astype(int)
    return out


def metric_bundle(frame: pd.DataFrame) -> dict:
    kept = frame[~frame["veto"]]
    y = frame["tail_abs_gt5ns"].astype(bool).to_numpy()
    veto = frame["veto"].astype(bool).to_numpy()
    before_tail = float(y.mean()) if len(y) else float("nan")
    after_tail = float(kept["tail_abs_gt5ns"].mean()) if len(kept) else float("nan")
    residual = frame["centered_residual_ns"].to_numpy(dtype=float)
    kept_residual = kept["centered_residual_ns"].to_numpy(dtype=float)
    pair_cats = ["B4-B6", "B4-B8", "B6-B8"]
    charge_cats = sorted(frame["charge_bin"].dropna().unique())
    current_cats = sorted(frame["current_proxy_bin"].dropna().unique())
    charge_tvd = tvd(frame["charge_bin"], kept["charge_bin"], charge_cats)
    current_tvd = tvd(frame["current_proxy_bin"], kept["current_proxy_bin"], current_cats)
    topology_tvd = tvd(frame["pair"], kept["pair"], pair_cats)
    saturation_delta = abs(float(kept["saturation_proxy"].mean()) - float(frame["saturation_proxy"].mean())) if len(kept) else float("nan")
    late_peak_delta = abs(float(kept["late_peak_proxy"].mean()) - float(frame["late_peak_proxy"].mean())) if len(kept) else float("nan")
    support_drift = float(np.nanmax([charge_tvd, current_tvd, topology_tvd, saturation_delta, late_peak_delta]))
    return {
        "n_pairs": int(len(frame)),
        "n_events": int(frame["event_id"].nunique()),
        "veto_fraction": float(veto.mean()) if len(veto) else float("nan"),
        "timing_efficiency": float(1.0 - veto.mean()) if len(veto) else float("nan"),
        "tail_capture": float(veto[y].mean()) if y.any() else 0.0,
        "tail_fraction_before": before_tail,
        "tail_fraction_after": after_tail,
        "tail_fraction_delta": after_tail - before_tail if math.isfinite(after_tail) else float("nan"),
        "sigma68_before_ns": sigma68(residual),
        "sigma68_after_ns": sigma68(kept_residual),
        "full_rms_before_ns": float(np.sqrt(np.mean(residual**2))) if len(residual) else float("nan"),
        "full_rms_after_ns": float(np.sqrt(np.mean(kept_residual**2))) if len(kept_residual) else float("nan"),
        "charge_support_tvd": charge_tvd,
        "current_proxy_tvd": current_tvd,
        "topology_support_tvd": topology_tvd,
        "saturation_fraction_delta": saturation_delta,
        "late_peak_fraction_delta": late_peak_delta,
        "support_drift_max": support_drift,
    }


def build_frontier(pred: pd.DataFrame, pairs: pd.DataFrame, scans: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = [
        "event_id",
        "run",
        "pair",
        "min_amplitude_adc",
        "max_peak_sample",
        "charge_bin",
        "current_proxy_bin",
        "saturation_proxy",
        "late_peak_proxy",
    ]
    work = pred.merge(pairs[features], on=["event_id", "run", "pair"], how="left", validate="many_to_one")
    if work[features[3:]].isna().any().any():
        raise RuntimeError("support feature join produced missing values")

    actual_scans = scans[~scans["shuffled_proxy"]].copy()
    rows = []
    fold_rows = []
    pred_rows = []
    for method in config["methods"]:
        method_pred = work[(work["method"] == method) & (~work["shuffled_proxy"])].copy()
        method_scans = actual_scans[actual_scans["method"] == method].copy()
        for quantile in config["frontier"]["threshold_quantiles"]:
            parts = []
            for run in config["timing"]["loro_runs"]:
                threshold_row = method_scans[
                    (method_scans["heldout_run"] == int(run))
                    & (np.isclose(method_scans["threshold_quantile"], float(quantile)))
                ]
                if len(threshold_row) != 1:
                    raise RuntimeError("missing threshold for {} q={} run={}".format(method, quantile, run))
                sub = method_pred[method_pred["run"] == int(run)].copy()
                sub["frontier_threshold_quantile"] = float(quantile)
                sub["frontier_threshold"] = float(threshold_row["threshold"].iloc[0])
                sub["veto"] = sub["score"] >= float(threshold_row["threshold"].iloc[0])
                parts.append(sub)
                fold_metric = metric_bundle(sub)
                fold_metric.update({"method": method, "threshold_quantile": float(quantile), "heldout_run": int(run)})
                fold_rows.append(fold_metric)
            frontier_pred = pd.concat(parts, ignore_index=True)
            bundle = metric_bundle(frontier_pred)
            bundle.update({"method": method, "threshold_quantile": float(quantile)})
            rows.append(bundle)
            pred_rows.append(frontier_pred)
    return pd.DataFrame(rows), pd.DataFrame(fold_rows), pd.concat(pred_rows, ignore_index=True)


def bootstrap_frontier(frontier_pred: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["models"]["random_seed"]) + 97)
    rows = []
    for (method, quantile), sub in frontier_pred.groupby(["method", "frontier_threshold_quantile"]):
        sub = sub.reset_index(drop=True)
        runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
        by_run = {}
        for run, run_df in sub.groupby("run"):
            by_run[int(run)] = [idx.to_numpy(dtype=int) for _, idx in run_df.groupby("event_id").groups.items()]
        stats = []
        for _ in range(int(config["models"]["bootstrap_samples"])):
            pieces = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                groups = by_run[int(run)]
                chosen = rng.integers(0, len(groups), size=len(groups))
                pieces.extend(groups[int(i)] for i in chosen)
            idx = np.concatenate(pieces)
            stats.append(metric_bundle(sub.iloc[idx].copy()))
        stat_df = pd.DataFrame(stats)
        row = {"method": method, "threshold_quantile": float(quantile)}
        for col in [
            "timing_efficiency",
            "tail_capture",
            "tail_fraction_after",
            "tail_fraction_delta",
            "sigma68_after_ns",
            "full_rms_after_ns",
            "charge_support_tvd",
            "current_proxy_tvd",
            "topology_support_tvd",
            "saturation_fraction_delta",
            "late_peak_fraction_delta",
            "support_drift_max",
        ]:
            lo, hi = ci(stat_df[col].to_numpy(dtype=float))
            row[f"{col}_ci_low"] = lo
            row[f"{col}_ci_high"] = hi
        rows.append(row)
    return pd.DataFrame(rows)


def choose_winner(frontier: pd.DataFrame, config: dict) -> pd.Series:
    min_eff = float(config["frontier"]["min_timing_efficiency"])
    max_drift = float(config["frontier"]["max_support_drift"])
    out = frontier.copy()
    out["constraint_pass"] = (out["timing_efficiency"] >= min_eff) & (out["support_drift_max"] <= max_drift)
    out["winner_score"] = (
        out["tail_fraction_after"]
        + float(config["frontier"]["efficiency_penalty"]) * np.maximum(0.0, min_eff - out["timing_efficiency"])
        + float(config["frontier"]["support_drift_penalty"]) * np.maximum(0.0, out["support_drift_max"] - max_drift)
    )
    candidates = out[out["constraint_pass"]].copy()
    if candidates.empty:
        candidates = out.copy()
    return candidates.sort_values(["winner_score", "tail_fraction_after", "support_drift_max"]).iloc[0]


def constrained_table(frontier: pd.DataFrame, ci_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    min_eff = float(config["frontier"]["min_timing_efficiency"])
    max_drift = float(config["frontier"]["max_support_drift"])
    rows = []
    for method, sub in frontier.groupby("method"):
        work = sub.copy()
        work["constraint_pass"] = (work["timing_efficiency"] >= min_eff) & (work["support_drift_max"] <= max_drift)
        valid = work[work["constraint_pass"]]
        if valid.empty:
            best = work.sort_values(["support_drift_max", "tail_fraction_after"]).iloc[0]
        else:
            best = valid.sort_values(["tail_fraction_after", "support_drift_max"]).iloc[0]
        rows.append(best)
    table = pd.DataFrame(rows).merge(ci_df, on=["method", "threshold_quantile"], how="left")
    table["method_order"] = table["method"].map({method: idx for idx, method in enumerate(METHOD_ORDER)})
    return table.sort_values("method_order").drop(columns=["method_order"])


def leakage_checks(pred: pd.DataFrame, pairs: pd.DataFrame, frontier: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    expected_runs = set(int(x) for x in config["timing"]["loro_runs"])
    rows.append(
        {
            "check": "loro_runs_match_config",
            "value": ",".join(str(x) for x in sorted(pred["run"].unique())),
            "pass": set(int(x) for x in pred["run"].unique()) == expected_runs,
        }
    )
    rows.append(
        {
            "check": "all_methods_present",
            "value": ",".join(sorted(pred.loc[~pred["shuffled_proxy"], "method"].unique())),
            "pass": set(pred.loc[~pred["shuffled_proxy"], "method"].unique()) == set(config["methods"]),
        }
    )
    rows.append(
        {
            "check": "support_join_complete",
            "value": int(len(pairs)),
            "pass": int(len(pairs)) == int(pred.loc[(pred["method"] == config["methods"][0]) & (~pred["shuffled_proxy"])].shape[0]),
        }
    )
    rows.append(
        {
            "check": "frontier_has_all_method_quantiles",
            "value": int(len(frontier)),
            "pass": int(len(frontier)) == len(config["methods"]) * len(config["frontier"]["threshold_quantiles"]),
        }
    )
    rows.append(
        {
            "check": "all_frontier_metrics_finite",
            "value": int(np.isfinite(frontier.select_dtypes(include=[float, int])).to_numpy().sum()),
            "pass": bool(np.isfinite(frontier.select_dtypes(include=[float, int])).all().all()),
        }
    )
    return pd.DataFrame(rows)


def fmt_match_table(match: pd.DataFrame) -> str:
    lines = []
    for row in match.rename(columns={"pass": "passed"}).itertuples():
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                row.quantity,
                int(row.report_value),
                int(row.reproduced),
                int(row.delta),
                int(row.tolerance),
                "yes" if bool(row.passed) else "no",
            )
        )
    return "\n".join(lines)


def fmt_benchmark_table(table: pd.DataFrame) -> str:
    lines = []
    for row in table.itertuples():
        lines.append(
            "| {} | {:.2f} | {:.3f} [{:.3f}, {:.3f}] | {:.3f} [{:.3f}, {:.3f}] | {:.4f} [{:.4f}, {:.4f}] | {:.4f} [{:.4f}, {:.4f}] | {:.3f} [{:.3f}, {:.3f}] | {:.3f} | {:.3f} | {:.3f} | {:.3f} |".format(
                row.method,
                row.threshold_quantile,
                row.timing_efficiency,
                row.timing_efficiency_ci_low,
                row.timing_efficiency_ci_high,
                row.tail_capture,
                row.tail_capture_ci_low,
                row.tail_capture_ci_high,
                row.tail_fraction_after,
                row.tail_fraction_after_ci_low,
                row.tail_fraction_after_ci_high,
                row.support_drift_max,
                row.support_drift_max_ci_low,
                row.support_drift_max_ci_high,
                row.sigma68_after_ns,
                row.sigma68_after_ns_ci_low,
                row.sigma68_after_ns_ci_high,
                row.charge_support_tvd,
                row.current_proxy_tvd,
                row.topology_support_tvd,
                max(row.saturation_fraction_delta, row.late_peak_fraction_delta),
            )
        )
    return "\n".join(lines)


def fmt_frontier_table(frontier: pd.DataFrame, winner: pd.Series) -> str:
    method = str(winner["method"])
    sub = frontier[frontier["method"] == method].sort_values("threshold_quantile")
    lines = []
    for row in sub.itertuples():
        lines.append(
            "| {:.2f} | {:.3f} | {:.3f} | {:.4f} | {:.4f} | {:.3f} | {:.3f} |".format(
                row.threshold_quantile,
                row.timing_efficiency,
                row.tail_capture,
                row.tail_fraction_after,
                row.support_drift_max,
                row.sigma68_after_ns,
                row.veto_fraction,
            )
        )
    return "\n".join(lines)


def fmt_leakage_table(checks: pd.DataFrame) -> str:
    lines = []
    for row in checks.rename(columns={"pass": "passed"}).itertuples():
        lines.append("| {} | {} | {} |".format(row.check, row.value, "yes" if bool(row.passed) else "no"))
    return "\n".join(lines)


def plot_outputs(out_dir: Path, constrained: pd.DataFrame, frontier: pd.DataFrame, winner: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(constrained))
    ax.errorbar(
        x,
        constrained["tail_fraction_after"],
        yerr=[
            constrained["tail_fraction_after"] - constrained["tail_fraction_after_ci_low"],
            constrained["tail_fraction_after_ci_high"] - constrained["tail_fraction_after"],
        ],
        fmt="o",
        label="post-veto tail fraction",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(constrained["method"], rotation=25, ha="right")
    ax.set_ylabel("held-out tail fraction after support-constrained veto")
    ax.set_title("S16k support-constrained method winners")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_support_constrained_benchmark.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for method, sub in frontier.groupby("method"):
        ax.plot(sub["support_drift_max"], sub["tail_fraction_after"], marker="o", ms=3, lw=1, label=method)
    ax.scatter([winner["support_drift_max"]], [winner["tail_fraction_after"]], s=80, color="black", zorder=5, label="winner")
    ax.set_xlabel("maximum support drift")
    ax.set_ylabel("held-out post-veto tail fraction")
    ax.set_title("Tail removal versus support drift")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_vs_support_frontier.png", dpi=150)
    plt.close(fig)


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    report = """# S16k: Pretrigger-Veto Support Frontier

- **Study ID:** S16k
- **Ticket:** {ticket}
- **Worker:** {worker}
- **Date:** {date}
- **Config:** `configs/s16k_1781032083_478_14791743_pretrigger_veto_support_frontier.json`
- **Raw ROOT path:** `{raw_root_dir}`
- **Score source:** `{source_s16f_report_dir}`
- **Git commit:** `{git_commit}`

## 1. Preregistered Question

What pretrigger-contamination veto threshold captures real Sample-II timing tails while preserving charge, current, topology, and saturation support?  S16f established that pretrigger-only scores can remove timing-tail pairs under run-held-out splits, but it also warned that a veto can improve timing metrics by deleting a biased subset of events.  This S16k ticket therefore treats support preservation as a first-class selection constraint rather than an after-the-fact caveat.

## 2. Raw ROOT Reproduction Gate

The reproduction gate reads `h101/HRDv` directly from raw ROOT files, subtracts the median of samples 0--3 for each B stave, and counts pulses with baseline-subtracted amplitude above `{amplitude_cut_adc:.0f}` ADC.  The gate is independent of the S16f score tables and must pass before the support frontier is evaluated.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{match_rows}

The downstream timing benchmark uses Sample-II LORO runs `{loro_runs}`.  Joining held-out score rows to the raw-derived pair support table gives `{n_pairs}` pair rows from `{n_events}` all-downstream events.

## 3. Estimand And Equations

For each event pair `i`, the base timing residual is the S16f CFD20 pair residual after train-fold pair centering,

`r_i = (t_a - x_a/v) - (t_b - x_b/v) - m_p`,

where `m_p` is the median residual for pair `p` in the training runs only.  The tail label used for score training and evaluation is

`y_i = 1(|r_i| > {tail_cut:.1f} ns)`.

For method `m` and train-selected quantile `q`, the veto is

`V_i(m,q) = 1(s_i^m >= tau_{{m,q,fold}})`,

where `tau` is selected from the S16f train-fold score distribution.  S16k scans all configured quantiles rather than inheriting the single S16f utility threshold.

The primary objective is the held-out post-veto tail fraction

`P(y=1 | V=0)`,

subject to timing efficiency `P(V=0) >= {min_eff:.2f}` and maximum support drift `D_max <= {max_drift:.2f}`.

## 4. Support Metrics

All support metrics are computed on held-out rows only and compare the kept sample (`V=0`) with the pre-veto sample for the same method/threshold:

- **Charge support:** total variation distance over pair minimum-amplitude bins `{charge_bins}` ADC.
- **Current/rate proxy support:** total variation distance over event-order quartiles inside each run.  The raw ROOT mirror has no scaler branch, so this is explicitly a run-local ordering proxy, not an external beam-current measurement.
- **Topology support:** total variation distance over B4-B6, B4-B8, and B6-B8 pair categories.
- **Saturation support:** absolute change in the fraction of pair rows with `min_amplitude_adc >= {sat_adc:.0f}` ADC.
- **Late-peak support:** absolute change in the fraction of pair rows with `max_peak_sample >= {late_peak:.0f}`.

`D_max` is the maximum of those five drift numbers.  Run/event bootstrap confidence intervals resample runs first and then events within each sampled run, preserving the three pair rows carried by an event.

## 5. Compared Methods

The score families are the same head-to-head methods required by the ticket and produced by S16f under run-held-out splits:

- `traditional_quantile`: empirical train-run quantile envelope over hand-built pretrigger proxies.
- `ridge`: balanced RidgeClassifier over pretrigger summary features.
- `gradient_boosted_trees`: histogram gradient-boosted trees.
- `mlp`: small tabular multilayer perceptron.
- `cnn1d`: compact 1D-CNN over the two four-sample pretrigger traces.
- `siamese_cnn_meta`: new pair-symmetric CNN branch plus pretrigger metadata.

S16k does not retrain those scores; it audits and selects the threshold frontier from their held-out predictions.  The raw ROOT reproduction gate and support features are recomputed in this ticket's script.

## 6. Support-Constrained Benchmark

For each method, the table reports the best threshold quantile that satisfies the S16k timing-efficiency and support-drift constraints.  Confidence intervals are 95% run/event bootstrap intervals.

| Method | q | Efficiency [95% CI] | Tail capture [95% CI] | Post-veto tail fraction [95% CI] | Dmax [95% CI] | Sigma68 after [95% CI] ns | Charge TVD | Current-proxy TVD | Topology TVD | Sat/late drift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{benchmark_rows}

The winner is **{winner_method}** at threshold quantile `{winner_q:.2f}`.  It gives post-veto tail fraction `{winner_tail:.4f}` with timing efficiency `{winner_eff:.3f}`, tail capture `{winner_capture:.3f}`, and maximum support drift `{winner_drift:.4f}`.  The pre-veto tail fraction was `{baseline_tail:.4f}`.

## 7. Winner Frontier

The full threshold frontier for the winning method is:

| q | efficiency | tail capture | post-veto tail fraction | Dmax | sigma68 after ns | veto fraction |
|---:|---:|---:|---:|---:|---:|---:|
{winner_frontier_rows}

This shows the trade-off that motivated S16k: lower thresholds remove more tails but can cross support-drift or efficiency boundaries; higher thresholds preserve support better but remove fewer tails.

## 8. Leakage And Completeness Checks

| Check | Value | Pass? |
|---|---:|---|
{leakage_rows}

The support frontier is only as valid as the upstream S16f score split.  S16f used leave-one-run-out folds and excluded run id, event id, residuals, labels, post-trigger samples, pulse amplitude, and peak sample from score features.  S16k adds support variables after scoring for audit and selection, not for model training.

## 9. Systematics And Caveats

The tail label is a reconstruction residual proxy, not external contamination truth.  The current metric is an event-order/rate proxy because the raw ROOT tree used here has no scaler-current branch.  The saturation support metric is conservative because the saved pair table carries pair minimum amplitude rather than per-stave maximum amplitude; it flags high-charge pairs where both staves are high.  Charge, topology, and current support are measured on the all-downstream pair population only, so adoption for PID, energy, or pile-up studies still requires the corresponding downstream support audit.

The method comparison is a threshold-selection study, not a claim that CNN features are physically causal.  Multiple methods and thresholds are scanned; the decision rule is therefore constrained and operational: choose the lowest post-veto held-out tail fraction among rows satisfying fixed support and efficiency constraints.  If no row satisfied the constraints, the script would report a penalized winner rather than a passed frontier.

## 10. Conclusion

Under the S16k constraints (`efficiency >= {min_eff:.2f}`, `Dmax <= {max_drift:.2f}`), **{winner_method}** is the winner.  It improves the held-out timing-tail fraction from `{baseline_tail:.4f}` to `{winner_tail:.4f}` while keeping the maximum measured support drift at `{winner_drift:.4f}`.  The result supports using the S16k frontier as an operational veto benchmark, but not adopting the veto blindly in charge, PID, pile-up, or energy analyses.

## 11. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16k_1781032083_478_14791743_pretrigger_veto_support_frontier.py --config configs/s16k_1781032083_478_14791743_pretrigger_veto_support_frontier.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `support_frontier.csv`, `support_frontier_cis.csv`, `support_constrained_benchmark.csv`, `fold_support_metrics.csv`, `support_frontier_predictions.csv.gz`, `support_checks.csv`, `fig_support_constrained_benchmark.png`, and `fig_tail_vs_support_frontier.png`.
""".format(**numbers)
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_hashes(out_dir: Path) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = ROOT / Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    match = s16f.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pred, pairs, scans = load_source_artifacts(config)
    pairs = add_support_features(pairs, config)
    frontier, fold_metrics, frontier_pred = build_frontier(pred, pairs, scans, config)
    ci_df = bootstrap_frontier(frontier_pred, config)
    constrained = constrained_table(frontier, ci_df, config)
    winner = choose_winner(frontier, config)
    checks = leakage_checks(pred, pairs, frontier, config)

    frontier.to_csv(out_dir / "support_frontier.csv", index=False)
    ci_df.to_csv(out_dir / "support_frontier_cis.csv", index=False)
    constrained.to_csv(out_dir / "support_constrained_benchmark.csv", index=False)
    fold_metrics.to_csv(out_dir / "fold_support_metrics.csv", index=False)
    frontier_pred.to_csv(out_dir / "support_frontier_predictions.csv.gz", index=False)
    checks.to_csv(out_dir / "support_checks.csv", index=False)

    input_rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"file": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    plot_outputs(out_dir, constrained, frontier, winner)

    baseline_tail = float(frontier["tail_fraction_before"].iloc[0])
    numbers = {
        "ticket": config["ticket"],
        "worker": config["worker"],
        "date": config["date"],
        "raw_root_dir": config["raw_root_dir"],
        "source_s16f_report_dir": config["source_s16f_report_dir"],
        "git_commit": git_commit(),
        "amplitude_cut_adc": float(config["amplitude_cut_adc"]),
        "match_rows": fmt_match_table(match),
        "loro_runs": ", ".join(str(x) for x in config["timing"]["loro_runs"]),
        "n_pairs": int(frontier["n_pairs"].iloc[0]),
        "n_events": int(frontier["n_events"].iloc[0]),
        "tail_cut": float(config["timing"]["tail_abs_residual_ns"]),
        "min_eff": float(config["frontier"]["min_timing_efficiency"]),
        "max_drift": float(config["frontier"]["max_support_drift"]),
        "charge_bins": ", ".join("{:.0f}".format(float(x)) for x in config["frontier"]["charge_bins_adc"]),
        "sat_adc": float(config["frontier"]["saturation_proxy_adc"]),
        "late_peak": float(config["frontier"]["late_peak_proxy_sample"]),
        "benchmark_rows": fmt_benchmark_table(constrained),
        "winner_method": str(winner["method"]),
        "winner_q": float(winner["threshold_quantile"]),
        "winner_tail": float(winner["tail_fraction_after"]),
        "winner_eff": float(winner["timing_efficiency"]),
        "winner_capture": float(winner["tail_capture"]),
        "winner_drift": float(winner["support_drift_max"]),
        "baseline_tail": baseline_tail,
        "winner_frontier_rows": fmt_frontier_table(frontier, winner),
        "leakage_rows": fmt_leakage_table(checks),
    }
    write_report(out_dir, config, numbers)

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": config["date"],
        "reproduction_pass": bool(match["pass"].all()),
        "raw_reproduction": match.to_dict(orient="records"),
        "split": "Sample-II leave-one-run-out by run",
        "score_source": config["source_s16f_report_dir"],
        "support_constraints": {
            "min_timing_efficiency": float(config["frontier"]["min_timing_efficiency"]),
            "max_support_drift": float(config["frontier"]["max_support_drift"]),
        },
        "baseline": {
            "tail_fraction_abs_gt5ns": baseline_tail,
            "sigma68_ns": float(frontier["sigma68_before_ns"].iloc[0]),
        },
        "methods": constrained.drop(columns=[col for col in ["winner_score"] if col in constrained.columns]).to_dict(orient="records"),
        "winner": {
            "method": str(winner["method"]),
            "threshold_quantile": float(winner["threshold_quantile"]),
            "criterion": "lowest held-out post-veto tail fraction subject to timing-efficiency and support-drift constraints",
            "tail_fraction_after": float(winner["tail_fraction_after"]),
            "timing_efficiency": float(winner["timing_efficiency"]),
            "tail_capture": float(winner["tail_capture"]),
            "support_drift_max": float(winner["support_drift_max"]),
            "sigma68_after_ns": float(winner["sigma68_after_ns"]),
        },
        "support_checks": checks.to_dict(orient="records"),
        "next_tickets": [],
        "runtime_sec": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "script": str(Path("scripts") / Path(__file__).name),
        "config": str(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "source_s16f_report_dir": config["source_s16f_report_dir"],
        "inputs": input_rows,
        "outputs": output_hashes(out_dir),
        "runtime_sec": time.time() - t0,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket"], "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
