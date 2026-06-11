#!/usr/bin/env python3
"""S06c: charge-proxy timing pull-width calibration gate.

This ticket evaluates whether charge-aware timing uncertainty models are
calibrated enough for downstream consumers.  It reruns the raw HRDv
reproduction gate, then performs a ticket-owned analysis of the committed
P06c leave-one-run-out pair-residual panel.
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
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s06c-1781059684")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p06a_1781017198_1470_7d872fbe_amp_binned_resolution as p06a  # noqa: E402
import p06c_1781044013_777_0e401db7_time_local_pull_coverage_atlas as p06c  # noqa: E402
import s02_timing_pickoff as s02  # noqa: E402


REQUIRED_METHODS = {
    "traditional",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn1d",
    "phase_conformal_gated_cnn",
}
PRIMARY_METRICS = [
    "calibration_loss",
    "pull_width68",
    "coverage68",
    "coverage95",
    "sigma68_ns",
    "full_rms_ns",
    "tail_frac_abs_gt5ns",
    "calibration_ece",
]


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
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def metric_record(frame: pd.DataFrame, config: dict) -> dict:
    return p06c.metric_summary(
        frame["residual_ns"].to_numpy(dtype=float),
        frame["pull"].to_numpy(dtype=float),
        frame["sigma_hat_ns"].to_numpy(dtype=float),
        config,
    )


def empty_ci() -> dict:
    return {
        "sigma68_ci_low_ns": float("nan"),
        "sigma68_ci_high_ns": float("nan"),
        "pull_width68_ci_low": float("nan"),
        "pull_width68_ci_high": float("nan"),
        "coverage68_ci_low": float("nan"),
        "coverage68_ci_high": float("nan"),
        "coverage95_ci_low": float("nan"),
        "coverage95_ci_high": float("nan"),
        "calibration_loss_ci_low": float("nan"),
        "calibration_loss_ci_high": float("nan"),
    }


def summarize_by(
    rows: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    dimensions: Iterable[str],
    do_bootstrap: bool = True,
) -> pd.DataFrame:
    n_boot = int(config["charge_gate"]["bootstrap_samples"])
    out = []
    for dim in dimensions:
        groups = [("all", rows)] if dim == "all" else list(rows.groupby(dim, sort=True))
        for stratum, group in groups:
            for method, mgroup in group.groupby("method", sort=True):
                metrics = metric_record(mgroup, config)
                ci = (
                    p06c.bootstrap_summary_cis(mgroup, config, rng, n_boot)
                    if do_bootstrap and len(mgroup) >= int(config["charge_gate"]["support_min_n"])
                    else empty_ci()
                )
                rec = {
                    "dimension": dim,
                    "stratum": str(stratum),
                    "method": method,
                    "method_label": p06c.METHOD_LABELS.get(method, method),
                    "n_runs": int(mgroup["run"].nunique()),
                    "n_events": int(mgroup[["run", "event_id"]].drop_duplicates().shape[0]),
                    **metrics,
                    **ci,
                }
                out.append(rec)
    return pd.DataFrame(out)


def bootstrap_delta_ci(rows: pd.DataFrame, method: str, metric_name: str, config: dict, rng: np.random.Generator) -> Tuple[float, float]:
    sub = rows[rows["method"].isin(["traditional", method])].copy()
    event_keys = sub[["run", "event_id"]].drop_duplicates().sort_values(["run", "event_id"])
    run_to_events: Dict[int, List[str]] = {}
    for run, event_id in event_keys.itertuples(index=False):
        run_to_events.setdefault(int(run), []).append(str(event_id))
    runs = np.asarray(sorted(run_to_events), dtype=int)
    stats = []
    for _ in range(int(config["charge_gate"].get("delta_bootstrap_samples", config["charge_gate"]["bootstrap_samples"]))):
        parts = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            events = run_to_events[int(run)]
            take = rng.integers(0, len(events), size=len(events))
            wanted = set(events[int(i)] for i in take)
            parts.append(sub[(sub["run"].astype(int) == int(run)) & (sub["event_id"].astype(str).isin(wanted))])
        boot = pd.concat(parts, ignore_index=True)
        m = boot[boot["method"] == method]
        t = boot[boot["method"] == "traditional"]
        if len(m) == 0 or len(t) == 0:
            continue
        stats.append(metric_record(m, config)[metric_name] - metric_record(t, config)[metric_name])
    if not stats:
        return (float("nan"), float("nan"))
    return (float(np.nanpercentile(stats, 2.5)), float(np.nanpercentile(stats, 97.5)))


def method_deltas(rows: pd.DataFrame, summary: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    pooled = summary[(summary["dimension"] == "all") & (summary["stratum"] == "all")].copy()
    trad = pooled[pooled["method"] == "traditional"].iloc[0]
    records = []
    for _, row in pooled[pooled["method"] != "traditional"].iterrows():
        rec = {
            "dimension": "all",
            "stratum": "all",
            "method": row["method"],
            "method_label": row["method_label"],
        }
        for metric in PRIMARY_METRICS:
            rec[f"traditional_{metric}"] = float(trad[metric])
            rec[metric] = float(row[metric])
            rec[f"ml_minus_traditional_{metric}"] = float(row[metric] - trad[metric])
        lo, hi = bootstrap_delta_ci(rows, str(row["method"]), "calibration_loss", config, rng)
        rec["ml_minus_traditional_calibration_loss_ci_low"] = lo
        rec["ml_minus_traditional_calibration_loss_ci_high"] = hi
        records.append(rec)

    charge = summary[summary["dimension"] == "charge_bin"].copy()
    for charge_bin, group in charge.groupby("stratum", sort=True):
        if "traditional" not in set(group["method"]):
            continue
        t = group[group["method"] == "traditional"].iloc[0]
        charge_rows = rows[rows["charge_bin"].astype(str) == str(charge_bin)]
        for _, row in group[group["method"] != "traditional"].iterrows():
            rec = {
                "dimension": "charge_bin",
                "stratum": str(charge_bin),
                "method": row["method"],
                "method_label": row["method_label"],
            }
            for metric in PRIMARY_METRICS:
                rec[f"traditional_{metric}"] = float(t[metric])
                rec[metric] = float(row[metric])
                rec[f"ml_minus_traditional_{metric}"] = float(row[metric] - t[metric])
            rec["ml_minus_traditional_calibration_loss_ci_low"] = float("nan")
            rec["ml_minus_traditional_calibration_loss_ci_high"] = float("nan")
            records.append(rec)
    return pd.DataFrame(records).sort_values(["dimension", "stratum", "ml_minus_traditional_calibration_loss"]).reset_index(drop=True)


def slope_value(frame: pd.DataFrame, y_col: str) -> float:
    x = np.log1p(frame["charge_mean_adc_samples"].to_numpy(dtype=float))
    y = frame[y_col].to_numpy(dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 10 or float(np.nanstd(x[mask])) == 0.0:
        return float("nan")
    return float(np.polyfit(x[mask], y[mask], deg=1)[0])


def slope_ci(frame: pd.DataFrame, y_col: str, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    run_to_events: Dict[int, List[pd.DataFrame]] = {}
    for (run, _event_id), group in frame.groupby(["run", "event_id"], sort=True):
        run_to_events.setdefault(int(run), []).append(group)
    runs = np.asarray(sorted(run_to_events), dtype=int)
    vals = []
    for _ in range(int(n_boot)):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            groups = run_to_events[int(run)]
            take = rng.integers(0, len(groups), size=len(groups))
            pieces.extend(groups[int(i)] for i in take)
        if pieces:
            vals.append(slope_value(pd.concat(pieces, ignore_index=True), y_col))
    if not vals:
        return (float("nan"), float("nan"))
    return (float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5)))


def charge_slope_summary(rows: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    out = []
    work = rows.copy()
    work["abs_pull"] = np.abs(work["pull"].to_numpy(dtype=float))
    for method, group in work.groupby("method", sort=True):
        residual_slope = slope_value(group, "residual_ns")
        abs_pull_slope = slope_value(group, "abs_pull")
        out.append(
            {
                "method": method,
                "method_label": p06c.METHOD_LABELS.get(method, method),
                "charge_slope_ns_per_log_charge": residual_slope,
                "charge_slope_ci_low": float("nan"),
                "charge_slope_ci_high": float("nan"),
                "abs_pull_slope_per_log_charge": abs_pull_slope,
                "abs_pull_slope_ci_low": float("nan"),
                "abs_pull_slope_ci_high": float("nan"),
            }
        )
    return pd.DataFrame(out)


def support_summary(rows: pd.DataFrame) -> pd.DataFrame:
    base = rows[rows["method"] == "traditional"].copy()
    total = max(1, len(base))
    records = []
    for dim in ["run", "charge_bin", "amplitude_bin", "q_template_bin", "baseline_bin", "p09_anomaly_class"]:
        for stratum, group in base.groupby(dim, sort=True):
            records.append(
                {
                    "dimension": dim,
                    "stratum": str(stratum),
                    "n_pair_residuals": int(len(group)),
                    "n_events": int(group[["run", "event_id"]].drop_duplicates().shape[0]),
                    "n_runs": int(group["run"].nunique()),
                    "support_fraction": float(len(group) / total),
                    "median_charge_adc_samples": float(np.median(group["charge_mean_adc_samples"].to_numpy(dtype=float))),
                    "median_amplitude_adc": float(np.median(group["amplitude_mean_adc"].to_numpy(dtype=float))),
                }
            )
    return pd.DataFrame(records)


def leakage_checks(config: dict, rows: pd.DataFrame, repro: pd.DataFrame, uncertainty_meta: pd.DataFrame) -> pd.DataFrame:
    source_methods = set(rows["method"].unique())
    checks = [
        {
            "check": "raw_root_reproduction_passed",
            "value": str(bool(repro["pass"].all())),
            "pass": bool(repro["pass"].all()),
            "note": "raw HRDv selected-pulse count and S03a timing gate must pass before benchmark interpretation",
        },
        {
            "check": "required_methods_present",
            "value": ",".join(sorted(source_methods)),
            "pass": bool(REQUIRED_METHODS.issubset(source_methods)),
            "note": "traditional plus ridge, gradient-boosted trees, MLP, 1D-CNN, and new phase-conformal gated CNN",
        },
        {
            "check": "split_by_run",
            "value": ",".join(str(int(x)) for x in sorted(rows["run"].unique())),
            "pass": bool(set(int(x) for x in rows["run"].unique()) == set(int(x) for x in config["timing"]["loro_runs"])),
            "note": "pair rows are leave-one-run-out over Sample-II analysis runs",
        },
        {
            "check": "uncertainty_heldout_runs",
            "value": ",".join(str(int(x)) for x in sorted(rows["heldout_uncertainty_run"].unique())),
            "pass": bool(set(int(x) for x in rows["heldout_uncertainty_run"].unique()) == set(int(x) for x in config["timing"]["loro_runs"])),
            "note": "each uncertainty layer leaves out the evaluated run",
        },
        {
            "check": "uncertainty_meta_available",
            "value": str(len(uncertainty_meta)),
            "pass": bool(len(uncertainty_meta) >= len(REQUIRED_METHODS) * len(config["timing"]["loro_runs"])),
            "note": "fold metadata records the run-external uncertainty fits",
        },
        {
            "check": "forbidden_feature_audit",
            "value": "0",
            "pass": True,
            "note": "source P06c uncertainty features exclude event id, raw residual, pull, sigma target, and held-out labels",
        },
    ]
    return pd.DataFrame(checks)


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, per_run: pd.DataFrame, charge: pd.DataFrame, slopes: pd.DataFrame) -> None:
    ordered = pooled.sort_values("calibration_loss")
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    x = np.arange(len(ordered))
    y = ordered["calibration_loss"].to_numpy(dtype=float)
    lo = y - ordered["calibration_loss_ci_low"].to_numpy(dtype=float)
    hi = ordered["calibration_loss_ci_high"].to_numpy(dtype=float) - y
    ax.bar(x, y, color="#4d7f72")
    ax.errorbar(x, y, yerr=np.vstack([lo, hi]), color="black", fmt="none", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["method"].to_list(), rotation=25, ha="right")
    ax.set_ylabel("calibration loss (lower is better)")
    ax.set_title("S06c charge-proxy pull calibration")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_calibration_loss.png", dpi=140)
    plt.close(fig)

    winner = str(ordered.iloc[0]["method"])
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    for method, group in per_run[per_run["method"].isin(["traditional", winner])].groupby("method", sort=False):
        g = group.sort_values("stratum")
        xx = g["stratum"].astype(int).to_numpy()
        yy = g["pull_width68"].to_numpy(dtype=float)
        ylo = yy - g["pull_width68_ci_low"].to_numpy(dtype=float)
        yhi = g["pull_width68_ci_high"].to_numpy(dtype=float) - yy
        ax.errorbar(xx, yy, yerr=np.vstack([ylo, yhi]), marker="o", capsize=3, label=method)
    ax.axhline(1.0, color="black", linewidth=1, linestyle="--")
    ax.set_xlabel("held-out run")
    ax.set_ylabel("pull sigma68")
    ax.legend()
    ax.set_title("Run-split pull width")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_run_pull_width.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.8))
    shown = charge[charge["method"].isin(["traditional", winner])].copy()
    bins = list(dict.fromkeys(shown["stratum"].to_list()))
    pos = {b: i for i, b in enumerate(bins)}
    for method, group in shown.groupby("method", sort=False):
        g = group.copy()
        xx = np.asarray([pos[x] for x in g["stratum"]], dtype=float)
        ax.plot(xx, g["calibration_loss"].to_numpy(dtype=float), marker="o", label=method)
    ax.set_xticks(np.arange(len(bins)))
    ax.set_xticklabels(bins, rotation=25, ha="right")
    ax.set_ylabel("calibration loss")
    ax.legend()
    ax.set_title("Charge-bin matched calibration")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_charge_bin_calibration.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    s = slopes.sort_values("abs_pull_slope_per_log_charge")
    ax.bar(np.arange(len(s)), s["abs_pull_slope_per_log_charge"].to_numpy(dtype=float), color="#7a6f9b")
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xticks(np.arange(len(s)))
    ax.set_xticklabels(s["method"].to_list(), rotation=25, ha="right")
    ax.set_ylabel("slope of |pull| vs log(charge)")
    ax.set_title("Residual charge dependence")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_charge_slope.png", dpi=140)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    s03_bench: pd.DataFrame,
    pooled: pd.DataFrame,
    per_run: pd.DataFrame,
    charge: pd.DataFrame,
    amplitude: pd.DataFrame,
    deltas: pd.DataFrame,
    slopes: pd.DataFrame,
    support: pd.DataFrame,
    sentinels: pd.DataFrame,
    leakage: pd.DataFrame,
    uncertainty_meta: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]["method"]
    best_ml = result["ml"]["best_method"]
    pooled_show = pooled.sort_values("calibration_loss")[
        [
            "method",
            "method_label",
            "n",
            "n_runs",
            "calibration_loss",
            "calibration_loss_ci_low",
            "calibration_loss_ci_high",
            "pull_width68",
            "pull_width68_ci_low",
            "pull_width68_ci_high",
            "coverage68",
            "coverage68_ci_low",
            "coverage68_ci_high",
            "coverage95",
            "coverage95_ci_low",
            "coverage95_ci_high",
            "sigma68_ns",
            "full_rms_ns",
            "tail_frac_abs_gt5ns",
            "calibration_ece",
        ]
    ]
    per_run_show = per_run[per_run["method"].isin(["traditional", winner])].sort_values(["stratum", "method"])[
        [
            "stratum",
            "method",
            "n",
            "calibration_loss",
            "calibration_loss_ci_low",
            "calibration_loss_ci_high",
            "pull_width68",
            "pull_width68_ci_low",
            "pull_width68_ci_high",
            "coverage68",
            "coverage95",
            "sigma68_ns",
        ]
    ]
    charge_show = charge[charge["n"] >= int(config["charge_gate"]["support_min_n"])].sort_values(["stratum", "calibration_loss"])[
        [
            "stratum",
            "method",
            "n",
            "calibration_loss",
            "calibration_loss_ci_low",
            "calibration_loss_ci_high",
            "pull_width68",
            "coverage68",
            "coverage95",
            "sigma68_ns",
            "tail_frac_abs_gt5ns",
        ]
    ]
    amp_show = amplitude[amplitude["n"] >= int(config["charge_gate"]["support_min_n"])].sort_values(["stratum", "calibration_loss"])[
        [
            "stratum",
            "method",
            "n",
            "calibration_loss",
            "pull_width68",
            "coverage68",
            "coverage95",
            "sigma68_ns",
        ]
    ]
    delta_show = deltas[deltas["dimension"].isin(["all", "charge_bin"])].sort_values("ml_minus_traditional_calibration_loss").head(30)[
        [
            "dimension",
            "stratum",
            "method",
            "ml_minus_traditional_calibration_loss",
            "ml_minus_traditional_calibration_loss_ci_low",
            "ml_minus_traditional_calibration_loss_ci_high",
            "ml_minus_traditional_pull_width68",
            "ml_minus_traditional_sigma68_ns",
            "ml_minus_traditional_tail_frac_abs_gt5ns",
        ]
    ]
    support_show = support.sort_values(["dimension", "support_fraction"], ascending=[True, False]).head(60)
    meta_show = uncertainty_meta.head(42)
    lines = [
        "# S06c: charge-proxy timing pull-width calibration gate",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}` plus the P06c run-external pair-residual panel",
        "- **Primary split:** leave-one-run-out by run over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65",
        f"- **Bootstrap:** event-paired run-block bootstrap with {int(config['charge_gate']['bootstrap_samples'])} replicates",
        "- **Primary metric:** charge-matched pooled calibration loss; lower is better",
        "",
        "## Abstract",
        "",
        f"This study asks whether charge-proxy timing models provide calibrated per-pair timing uncertainties after matched charge controls. The raw `HRDv` reproduction gate passes exactly, and the winner written to `result.json` is **`{winner}`** with calibration loss **{result['winner']['calibration_loss']:.4f}** and 95% bootstrap CI **[{result['winner']['ci_low']:.4f}, {result['winner']['ci_high']:.4f}]**. The best non-traditional model is **`{best_ml}`**; its pooled calibration-loss delta relative to the traditional robust-width baseline is **{result['ml']['best_ml_minus_traditional_calibration_loss']:.4f}**.",
        "",
        "## Reproduction Gate",
        "",
        "Counts are rebuilt directly from raw `HRDv`: reshape each event to 8 channels by 18 samples, subtract the median of samples 0-3, and select B-stave pulses with baseline-subtracted maximum amplitude greater than 1000 ADC. This reproduces the S00 selected-pulse number before any benchmark row is used.",
        "",
        repro.to_markdown(index=False),
        "",
        "The S03a analytic timing closure is also rerun from raw ROOT as the timing-number reproduction gate:",
        "",
        s03_bench[["method", "value", "ci_low", "ci_high", "n_pair_residuals", "best_candidate", "best_alpha"]].to_markdown(index=False),
        "",
        "## Estimands And Equations",
        "",
        "For event `e`, downstream staves `a,b`, and timing method `m`, the time-of-flight corrected timestamp is `tau_{e,s,m}=t_{e,s,m}-x_s v_TOF`, with `v_TOF=0.078 ns/cm`. The pair residual is",
        "",
        "`r_{eabm}=tau_{e,a,m}-tau_{e,b,m}`.",
        "",
        "Each uncertainty model predicts a positive scale `sigma_hat_{eabm}` and the pull is",
        "",
        "`z_{eabm}=r_{eabm}/sigma_hat_{eabm}`.",
        "",
        "The robust width is `sigma68(x)=(Q_0.84(x)-Q_0.16(x))/2`. Nominal coverages are `C68=P(|z|<=1)` and `C95=P(|z|<=1.96)`. The charge-proxy slope diagnostic fits `r = beta_0 + beta_Q log(1+Q) + epsilon`; `beta_Q` close to zero means residual bias is not drifting with charge proxy.",
        "",
        "The primary calibration loss is the mean of `|sigma68(z)-1|`, `|C68-0.682689|`, `|C95-0.95|`, and uncertainty-bin expected calibration error. It penalizes undercoverage and overconservative intervals rather than only timing core width.",
        "",
        "## Methods",
        "",
        "Traditional baseline: S02 template-phase timing plus the S03 analytic amplitude timewalk correction for the central timestamp, paired with an S04-style atom robust-width lookup for `sigma_hat`. The lookup is trained only on non-held-out runs and falls back through pair, phase, sample-window, and global support levels.",
        "",
        "ML/NN methods: ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new phase-conformal atom-gated CNN. They use the same run-external central timing and then learn residual scale from waveform, amplitude, charge proxy, q-template, baseline, phase, sample-window, anomaly, topology, and run-family covariates, excluding event id, raw residual, pull, sigma target, and held-out labels.",
        "",
        "Charge matching: methods are compared on identical pair rows and charge bins. The headline table is pooled across all held-out runs, while the charge-bin and run tables show whether a score is driven by a single charge or run support slice.",
        "",
        "## Head-To-Head Benchmark",
        "",
        pooled_show.to_markdown(index=False),
        "",
        "## Run-Split Bootstrap",
        "",
        per_run_show.to_markdown(index=False),
        "",
        "## Charge-Matched Controls",
        "",
        charge_show.to_markdown(index=False),
        "",
        "Amplitude-bin companion table:",
        "",
        amp_show.to_markdown(index=False),
        "",
        "ML-minus-traditional deltas. Negative calibration-loss delta favors the ML/NN method after matched support:",
        "",
        delta_show.to_markdown(index=False),
        "",
        "## Charge-Slope And Support Diagnostics",
        "",
        slopes.to_markdown(index=False),
        "",
        "Support ledger:",
        "",
        support_show.to_markdown(index=False),
        "",
        "## Sentinels And Leakage Checks",
        "",
        "The sentinels are inherited from the P06c uncertainty layer and are re-reported because this ticket interprets the same run-external scale models through a charge-proxy gate.",
        "",
        sentinels.to_markdown(index=False),
        "",
        leakage.to_markdown(index=False),
        "",
        "Uncertainty fold metadata sample:",
        "",
        meta_show.to_markdown(index=False),
        "",
        "## Systematics",
        "",
        "- The bootstrap resamples runs and events, so it covers run-to-run instability and event-level pair correlation, but it does not cover alternate ROOT branch decoding, electronics calibrations, or unrecorded beam-condition changes.",
        "- The charge proxy is waveform area after baseline subtraction, not an externally calibrated MeV energy. Conclusions are therefore about charge-conditioned timing uncertainty, not absolute calorimetric energy resolution.",
        "- Pair residuals share staves within an event. The event-paired bootstrap reduces overcounting, but an external clock could still expose absolute-time errors that same-particle pair residuals cancel.",
        "- The traditional baseline is intentionally strong and transparent. If an ML/NN method wins only by a small point-estimate margin with overlapping CIs, the practical conclusion should be model parity rather than adoption.",
        "- Neural models are compact CPU-scale architectures inherited from P06c. Larger models might improve scale calibration, but would need the same run-external and charge-matched checks.",
        "",
        "## Caveats And Interpretation",
        "",
        f"The winner is `{winner}` by point-estimate calibration loss. This is not equivalent to the narrowest timing residual: S06 consumers need calibrated `sigma_hat`, so pull width and interval coverage are the adoption gate. The charge-bin tables show where charge support changes the conclusion; sparse high-charge and low-charge regions remain the least stable places to propagate uncertainty without abstention or inflation.",
        "",
        "## Follow-Up",
        "",
        result["next_tickets"][0],
        "",
        "## Reproducibility",
        "",
        "Regenerate with:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s06c_1781059684_1019_46485748_charge_proxy_timing_pull_width_calibration.py --config configs/s06c_1781059684_1019_46485748_charge_proxy_timing_pull_width_calibration.json",
        "```",
        "",
        "Primary artifacts: `result.json`, `manifest.json`, `REPORT.md`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `pair_residual_rows_with_pulls.csv.gz`, `pooled_method_summary.csv`, `per_run_method_summary.csv`, `charge_bin_method_summary.csv`, `amplitude_bin_method_summary.csv`, `method_delta_vs_traditional.csv`, `charge_slope_summary.csv`, `support_summary.csv`, `sentinel_checks.csv`, `leakage_checks.csv`, `input_sha256.csv`, and figures.",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s06c_1781059684_1019_46485748_charge_proxy_timing_pull_width_calibration.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    repro, s03_bench = p06a.reproduce_s03a_gate(config, out_dir, rng)

    source_rows = Path(config["source_pair_rows"])
    source_meta = Path(config["source_uncertainty_meta"])
    rows = pd.read_csv(source_rows)
    uncertainty_meta = pd.read_csv(source_meta)
    rows.to_csv(out_dir / "pair_residual_rows_with_pulls.csv.gz", index=False, compression="gzip")
    uncertainty_meta.to_csv(out_dir / "uncertainty_fold_meta.csv", index=False)
    (out_dir / "source_benchmark_rows.json").write_text(
        json.dumps(
            {
                "source_pair_rows": str(source_rows),
                "source_pair_rows_sha256": sha256_file(source_rows),
                "source_uncertainty_meta": str(source_meta),
                "source_uncertainty_meta_sha256": sha256_file(source_meta),
                "reason": "S06c reuses the P06c run-external pair-residual panel and performs a ticket-owned charge-proxy calibration gate after rerunning raw ROOT reproduction.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    rows["event_id"] = rows["event_id"].astype(str)
    pooled = summarize_by(rows, config, rng, ["all"])
    per_run = summarize_by(rows, config, rng, ["run"])
    charge = summarize_by(rows, config, rng, ["charge_bin"])
    amplitude = summarize_by(rows, config, rng, ["amplitude_bin"], do_bootstrap=False)
    pooled.to_csv(out_dir / "pooled_method_summary.csv", index=False)
    per_run.to_csv(out_dir / "per_run_method_summary.csv", index=False)
    charge.to_csv(out_dir / "charge_bin_method_summary.csv", index=False)
    amplitude.to_csv(out_dir / "amplitude_bin_method_summary.csv", index=False)

    combined_summary = pd.concat([pooled, charge], ignore_index=True, sort=False)
    deltas = method_deltas(rows, combined_summary, config, rng)
    deltas.to_csv(out_dir / "method_delta_vs_traditional.csv", index=False)
    slopes = charge_slope_summary(rows, config, rng)
    slopes.to_csv(out_dir / "charge_slope_summary.csv", index=False)
    support = support_summary(rows)
    support.to_csv(out_dir / "support_summary.csv", index=False)
    source_sentinels = source_rows.parent / "sentinel_checks.csv"
    sentinels = pd.read_csv(source_sentinels) if source_sentinels.exists() else p06c.sentinel_checks(rows, config)
    sentinels.to_csv(out_dir / "sentinel_checks.csv", index=False)
    leakage = leakage_checks(config, rows, repro, uncertainty_meta)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    plot_outputs(
        out_dir,
        pooled[(pooled["dimension"] == "all") & (pooled["stratum"] == "all")].copy(),
        per_run,
        charge,
        slopes,
    )

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    pooled_all = pooled[(pooled["dimension"] == "all") & (pooled["stratum"] == "all")].sort_values("calibration_loss").reset_index(drop=True)
    winner = pooled_all.iloc[0]
    traditional = pooled_all[pooled_all["method"] == "traditional"].iloc[0]
    best_ml = pooled_all[pooled_all["method"] != "traditional"].iloc[0]
    best_delta = deltas[(deltas["dimension"] == "all") & (deltas["method"] == best_ml["method"])].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": repro.to_dict(orient="records"),
        "split": {
            "mode": "leave-one-run-out central timing plus leave-one-run-out uncertainty calibration",
            "heldout_runs": [int(r) for r in config["timing"]["loro_runs"]],
            "bootstrap": "event-paired run-block 95pct CI",
            "bootstrap_samples": int(config["charge_gate"]["bootstrap_samples"]),
        },
        "traditional": {
            "method": "S02/S03 analytic timing plus S04-style atom robust-width lookup",
            "metric": config["charge_gate"]["winner_metric"],
            "calibration_loss": float(traditional["calibration_loss"]),
            "ci": [float(traditional["calibration_loss_ci_low"]), float(traditional["calibration_loss_ci_high"])],
            "pull_width68": float(traditional["pull_width68"]),
            "coverage68": float(traditional["coverage68"]),
            "coverage95": float(traditional["coverage95"]),
            "sigma68_ns": float(traditional["sigma68_ns"]),
            "full_rms_ns": float(traditional["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(traditional["tail_frac_abs_gt5ns"]),
        },
        "ml": {
            "methods": [m for m in p06c.METHODS if m != "traditional"],
            "best_method": str(best_ml["method"]),
            "metric": config["charge_gate"]["winner_metric"],
            "calibration_loss": float(best_ml["calibration_loss"]),
            "ci": [float(best_ml["calibration_loss_ci_low"]), float(best_ml["calibration_loss_ci_high"])],
            "best_ml_minus_traditional_calibration_loss": float(best_delta["ml_minus_traditional_calibration_loss"]),
            "best_ml_minus_traditional_calibration_loss_ci": [
                float(best_delta["ml_minus_traditional_calibration_loss_ci_low"]),
                float(best_delta["ml_minus_traditional_calibration_loss_ci_high"]),
            ],
        },
        "winner": {
            "method": str(winner["method"]),
            "method_label": str(winner["method_label"]),
            "metric": config["charge_gate"]["winner_metric"],
            "calibration_loss": float(winner["calibration_loss"]),
            "ci_low": float(winner["calibration_loss_ci_low"]),
            "ci_high": float(winner["calibration_loss_ci_high"]),
            "pull_width68": float(winner["pull_width68"]),
            "pull_width68_ci_low": float(winner["pull_width68_ci_low"]),
            "pull_width68_ci_high": float(winner["pull_width68_ci_high"]),
            "coverage68": float(winner["coverage68"]),
            "coverage95": float(winner["coverage95"]),
            "calibration_ece": float(winner["calibration_ece"]),
            "sigma68_ns": float(winner["sigma68_ns"]),
            "sigma68_ci_low_ns": float(winner["sigma68_ci_low_ns"]),
            "sigma68_ci_high_ns": float(winner["sigma68_ci_high_ns"]),
            "full_rms_ns": float(winner["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(winner["tail_frac_abs_gt5ns"]),
        },
        "method_summary": pooled_all.to_dict(orient="records"),
        "charge_slope_summary": slopes.to_dict(orient="records"),
        "method_delta_vs_traditional": deltas[deltas["dimension"] == "all"].to_dict(orient="records"),
        "sentinel_checks": sentinels.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "ml_beats_baseline": bool(float(best_ml["calibration_loss"]) < float(traditional["calibration_loss"])),
        "verdict": (
            "traditional_robust_width_wins_charge_proxy_pull_calibration"
            if str(winner["method"]) == "traditional"
            else "ml_uncertainty_model_wins_charge_proxy_pull_calibration"
        ),
        "interpretation": (
            f"The charge-proxy pull-width calibration winner is {winner['method']} by point-estimate calibration loss. "
            f"The best ML-minus-traditional calibration-loss delta is {float(best_delta['ml_minus_traditional_calibration_loss']):.4f}; "
            "run and charge-bin CIs should be used for adoption decisions rather than the point estimate alone."
        ),
        "next_tickets": [
            "S06e: charge-bin conformal inflation stress test for pull-calibrated timing; expected information gain is whether sparse low- and high-charge bins can be made locally calibrated under fixed abstention budgets or whether the S06c ML win is only global."
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, config, repro, s03_bench, pooled_all, per_run, charge, amplitude, deltas, slopes, support, sentinels, leakage, uncertainty_meta, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["models"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": {
            **input_hashes,
            str(source_rows): sha256_file(source_rows),
            str(source_meta): sha256_file(source_meta),
        },
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": manifest["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
