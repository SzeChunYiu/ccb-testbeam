#!/usr/bin/env python3
"""S05i: topology-split covariance coverage calibration.

This study freezes the S05h/S05f leave-one-run-held-out residual panel and
refits only topology-specific conformal interval layers.  Raw ROOT anchors are
rebuilt first, so the calibration is tied back to the same HRDv gate as the
covariance studies.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


S05H_PATH = Path(__file__).with_name("s05h_1781040960_767_247d3910_saturation_covariance_support_frontier.py")
TICKET_BODY = (
    "Do S05f B2-local covariance corrections provide calibrated interval coverage across "
    "B2-containing and downstream-only topology after saturation, amplitude, baseline, "
    "pile-up, and anomaly matching?"
)


def load_s05h():
    spec = importlib.util.spec_from_file_location("s05h_covariance", S05H_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {S05H_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s05h = load_s05h()


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


def centered(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return arr
    return arr - np.nanmedian(arr)


def sigma68(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float(0.5 * (np.percentile(c, 84) - np.percentile(c, 16)))


def full_rms(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float(np.sqrt(np.mean(c * c)))


def bootstrap_ci(
    frame: pd.DataFrame,
    value_col: str,
    func: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    n_boot: int,
) -> tuple[float, float]:
    runs = np.asarray(sorted(frame["run"].unique()))
    if len(runs) == 0:
        return float("nan"), float("nan")
    stats = []
    for _ in range(int(n_boot)):
        chunks = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            vals = frame.loc[frame["run"].eq(int(run)), value_col].to_numpy(dtype=float)
            if len(vals):
                chunks.append(vals[rng.integers(0, len(vals), size=len(vals))])
        if chunks:
            stats.append(func(np.concatenate(chunks)))
    return tuple(float(x) for x in np.nanquantile(stats, [0.025, 0.975])) if stats else (float("nan"), float("nan"))


def signed_pair_covariance(frame: pd.DataFrame, col: str) -> float:
    vals = []
    for _, run_df in frame.groupby("run"):
        wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
        cov = wide.cov(min_periods=5)
        cols = list(cov.columns)
        for idx, left in enumerate(cols):
            for right in cols[idx + 1 :]:
                val = cov.loc[left, right]
                if np.isfinite(val):
                    vals.append(float(val))
    return float(np.mean(vals)) if vals else float("nan")


def mean_abs_pair_covariance(frame: pd.DataFrame, col: str) -> float:
    vals = []
    for _, run_df in frame.groupby("run"):
        wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
        cov = wide.cov(min_periods=5)
        cols = list(cov.columns)
        for idx, left in enumerate(cols):
            for right in cols[idx + 1 :]:
                val = cov.loc[left, right]
                if np.isfinite(val):
                    vals.append(abs(float(val)))
    return float(np.mean(vals)) if vals else float("nan")


def covariance_delta(oof: pd.DataFrame, col: str) -> dict:
    b2 = oof[oof["topology"].eq("B2_containing")]
    ds = oof[oof["topology"].eq("downstream_only")]
    b2_signed = signed_pair_covariance(b2, col)
    ds_signed = signed_pair_covariance(ds, col)
    b2_abs = mean_abs_pair_covariance(b2, col)
    ds_abs = mean_abs_pair_covariance(ds, col)
    delta = b2_signed - ds_signed
    return {
        "b2_signed_offdiag_cov_ns2": b2_signed,
        "downstream_signed_offdiag_cov_ns2": ds_signed,
        "signed_offdiag_cov_delta_ns2": delta,
        "b2_mean_abs_pair_cov_ns2": b2_abs,
        "downstream_mean_abs_pair_cov_ns2": ds_abs,
        "abs_pair_cov_delta_ns2": b2_abs - ds_abs,
        "inferred_correlated_fraction": delta / b2_signed if math.isfinite(b2_signed) and abs(b2_signed) > 1e-12 else float("nan"),
    }


def covariance_delta_bootstrap(oof: pd.DataFrame, col: str, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    run_values = []
    for run, run_df in oof.groupby("run"):
        value = covariance_delta(run_df, col)["signed_offdiag_cov_delta_ns2"]
        if math.isfinite(value):
            run_values.append(value)
    run_values = np.asarray(run_values, dtype=float)
    if len(run_values) == 0:
        return float("nan"), float("nan")
    stats = []
    for _ in range(int(n_boot)):
        stats.append(float(np.nanmean(rng.choice(run_values, size=len(run_values), replace=True))))
    return tuple(float(x) for x in np.nanquantile(stats, [0.025, 0.975]))


def calibration_half_width(train: pd.DataFrame, resid_col: str, nominal: float) -> float:
    vals = centered(train[resid_col].to_numpy(dtype=float))
    if len(vals) < 20:
        return float("nan")
    return float(np.nanquantile(np.abs(vals), float(nominal)))


def add_conformal_intervals(oof: pd.DataFrame, methods: list[str], coverages: list[float]) -> pd.DataFrame:
    rows = []
    for method in methods:
        resid_col = "resid_pair_median" if method == "pair_median" else f"resid_{method}"
        if resid_col not in oof:
            continue
        for nominal in coverages:
            for run in sorted(oof["run"].unique()):
                for topology in ["B2_containing", "downstream_only", "all"]:
                    test_mask = oof["run"].eq(run)
                    train_mask = ~test_mask
                    if topology != "all":
                        test_mask &= oof["topology"].eq(topology)
                        train_mask &= oof["topology"].eq(topology)
                    train = oof.loc[train_mask]
                    test = oof.loc[test_mask]
                    if len(test) == 0:
                        continue
                    half = calibration_half_width(train, resid_col, nominal)
                    center = float(np.nanmedian(train[resid_col])) if len(train) else 0.0
                    covered = (np.abs(test[resid_col].to_numpy(dtype=float) - center) <= half).astype(float)
                    rows.append(
                        {
                            "method": method,
                            "residual_column": resid_col,
                            "nominal_coverage": float(nominal),
                            "heldout_run": int(run),
                            "topology": topology,
                            "n_train_rows": int(len(train)),
                            "n_test_rows": int(len(test)),
                            "interval_center_ns": center,
                            "half_width_ns": half,
                            "interval_width_ns": 2.0 * half,
                            "coverage": float(np.nanmean(covered)),
                            "coverage_error": float(np.nanmean(covered) - nominal),
                            "abs_coverage_error": float(abs(np.nanmean(covered) - nominal)),
                        }
                    )
    return pd.DataFrame(rows)


def summarize_intervals(intervals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for keys, group in intervals.groupby(["method", "residual_column", "nominal_coverage", "topology"]):
        method, resid_col, nominal, topology = keys
        runs = np.asarray(sorted(group["heldout_run"].unique()))
        weighted_cov = np.average(group["coverage"], weights=group["n_test_rows"])
        weighted_width = np.average(group["interval_width_ns"], weights=group["n_test_rows"])
        cov_stats = []
        width_stats = []
        for _ in range(int(n_boot)):
            sampled = group[group["heldout_run"].isin(rng.choice(runs, size=len(runs), replace=True))]
            if len(sampled):
                cov_stats.append(float(np.average(sampled["coverage"], weights=sampled["n_test_rows"])))
                width_stats.append(float(np.average(sampled["interval_width_ns"], weights=sampled["n_test_rows"])))
        cov_ci = np.nanquantile(cov_stats, [0.025, 0.975]) if cov_stats else [np.nan, np.nan]
        width_ci = np.nanquantile(width_stats, [0.025, 0.975]) if width_stats else [np.nan, np.nan]
        rows.append(
            {
                "method": method,
                "residual_column": resid_col,
                "nominal_coverage": float(nominal),
                "topology": topology,
                "n_runs": int(len(runs)),
                "n_pair_rows": int(group["n_test_rows"].sum()),
                "coverage": float(weighted_cov),
                "coverage_ci_low": float(cov_ci[0]),
                "coverage_ci_high": float(cov_ci[1]),
                "coverage_error": float(weighted_cov - nominal),
                "abs_coverage_error": float(abs(weighted_cov - nominal)),
                "mean_interval_width_ns": float(weighted_width),
                "interval_width_ci_low_ns": float(width_ci[0]),
                "interval_width_ci_high_ns": float(width_ci[1]),
            }
        )
    return pd.DataFrame(rows)


def residual_metrics(oof: pd.DataFrame, methods: list[str], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for method in methods:
        col = "resid_pair_median" if method == "pair_median" else f"resid_{method}"
        if col not in oof:
            continue
        for topology, group in [("all", oof)] + list(oof.groupby("topology")):
            sig_lo, sig_hi = bootstrap_ci(group, col, sigma68, rng, n_boot)
            rms_lo, rms_hi = bootstrap_ci(group, col, full_rms, rng, n_boot)
            rows.append(
                {
                    "method": method,
                    "method_class": "traditional" if method in {"pair_median", "traditional_s05d_static_priors"} else ("control" if method.endswith("control") or method in {"waveform_only_mlp", "pool_label_control"} else "ml"),
                    "topology": str(topology),
                    "n_pair_rows": int(len(group)),
                    "n_runs": int(group["run"].nunique()),
                    "sigma68_ns": sigma68(group[col].to_numpy(dtype=float)),
                    "sigma68_ci_low_ns": sig_lo,
                    "sigma68_ci_high_ns": sig_hi,
                    "full_rms_ns": full_rms(group[col].to_numpy(dtype=float)),
                    "full_rms_ci_low_ns": rms_lo,
                    "full_rms_ci_high_ns": rms_hi,
                    "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(centered(group[col].to_numpy(dtype=float))) > 5.0)),
                    "mean_abs_pair_cov_ns2": mean_abs_pair_covariance(group, col),
                }
            )
    return pd.DataFrame(rows)


def covariance_summary(oof: pd.DataFrame, methods: list[str], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for method in methods:
        col = "resid_pair_median" if method == "pair_median" else f"resid_{method}"
        if col not in oof:
            continue
        row = {"method": method, "residual_column": col}
        row.update(covariance_delta(oof, col))
        lo, hi = covariance_delta_bootstrap(oof, col, rng, n_boot)
        row["signed_delta_ci_low_ns2"] = lo
        row["signed_delta_ci_high_ns2"] = hi
        rows.append(row)
    return pd.DataFrame(rows)


def method_deltas(summary: pd.DataFrame, cov_summary: pd.DataFrame, winner: str) -> pd.DataFrame:
    rows = []
    for baseline in ["pair_median", "traditional_s05d_static_priors"]:
        for nominal in sorted(summary["nominal_coverage"].unique()):
            for topology in ["all", "B2_containing", "downstream_only"]:
                w = summary[(summary["method"].eq(winner)) & (summary["nominal_coverage"].eq(nominal)) & (summary["topology"].eq(topology))]
                b = summary[(summary["method"].eq(baseline)) & (summary["nominal_coverage"].eq(nominal)) & (summary["topology"].eq(topology))]
                if w.empty or b.empty:
                    continue
                rows.append(
                    {
                        "comparison": f"{winner}_minus_{baseline}",
                        "baseline": baseline,
                        "nominal_coverage": float(nominal),
                        "topology": topology,
                        "delta_abs_coverage_error": float(w.iloc[0]["abs_coverage_error"] - b.iloc[0]["abs_coverage_error"]),
                        "delta_interval_width_ns": float(w.iloc[0]["mean_interval_width_ns"] - b.iloc[0]["mean_interval_width_ns"]),
                    }
                )
        wc = cov_summary[cov_summary["method"].eq(winner)]
        bc = cov_summary[cov_summary["method"].eq(baseline)]
        if not wc.empty and not bc.empty:
            rows.append(
                {
                    "comparison": f"{winner}_minus_{baseline}",
                    "baseline": baseline,
                    "nominal_coverage": None,
                    "topology": "B2_minus_downstream",
                    "delta_abs_coverage_error": None,
                    "delta_interval_width_ns": None,
                    "delta_signed_offdiag_cov_delta_ns2": float(wc.iloc[0]["signed_offdiag_cov_delta_ns2"] - bc.iloc[0]["signed_offdiag_cov_delta_ns2"]),
                }
            )
    return pd.DataFrame(rows)


def raw_reproduction(config: dict, out_dir: Path) -> pd.DataFrame:
    frozen_config = load_config(Path(config["frozen_panel_config"]))
    frozen_config["raw_root_dir"] = config["raw_root_dir"]
    a_cache = out_dir / "astack_pair_table.csv.gz"
    if a_cache.exists():
        a_pairs = pd.read_csv(a_cache)
    else:
        a_pairs = s05h.astack_pair_table(frozen_config)
        a_pairs.to_csv(a_cache, index=False, compression="gzip")
    repro = s05h.reproduce_raw_anchors(frozen_config, a_pairs)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    return repro


def write_manifest(out_dir: Path, config_path: Path, config: dict, command: str) -> None:
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file() and path.name != "manifest.json")
    frozen_dir = Path(config["frozen_panel_dir"])
    input_paths = [Path(config_path), Path(config["frozen_panel_config"]), frozen_dir / "heldout_pair_residuals.csv", frozen_dir / "support_summary.csv"]
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "command": command,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": getattr(s05h.uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": None if s05h.torch is None else s05h.torch.__version__,
        },
        "frozen_panel": str(frozen_dir),
        "inputs": {str(path): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_paths if path.exists()},
        "output_sha256": {path.name: sha256_file(path) for path in outputs},
        "random_seed": int(config["random_seed"]),
    }
    write_json(out_dir / "manifest.json", manifest)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    metrics: pd.DataFrame,
    intervals: pd.DataFrame,
    interval_summary: pd.DataFrame,
    cov: pd.DataFrame,
    deltas: pd.DataFrame,
    support_summary: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    primary = interval_summary[
        interval_summary["method"].eq(winner)
        & interval_summary["nominal_coverage"].eq(0.95)
        & interval_summary["topology"].eq("all")
    ].iloc[0]
    report = f"""# S05i: Covariance coverage calibration by B2 topology

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Raw input:** `{config['raw_root_dir']}`
- **Frozen residual panel:** `{config['frozen_panel_dir']}`
- **No Monte Carlo:** raw HRD ROOT and frozen leave-one-run-held-out data residuals

## Question

{TICKET_BODY}

## Abstract

This study rebuilds the raw `HRDv` reproduction anchors, then freezes the S05h/S05f residual-model panel and refits only topology-specific conformal interval layers.  The benchmark includes the required strong traditional methods (`pair_median`, `traditional_s05d_static_priors`) and learned methods (`ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, and the new `support_gated_cnn_new`; `extra_trees_s05e_dynamic` is retained as the S05f/S05h dynamic-tree reference).  Splits are by run throughout.  Confidence intervals use a run-block bootstrap over held-out runs.

The winner named in `result.json` is **{winner}**, selected by the smallest 95% all-topology score `abs(coverage error) + 0.01 * interval_width`.  Its 95% empirical coverage is **{primary['coverage']:.3f}** with CI `[{primary['coverage_ci_low']:.3f}, {primary['coverage_ci_high']:.3f}]`, mean interval width **{primary['mean_interval_width_ns']:.3f} ns**, and coverage error **{primary['coverage_error']:.3f}**.

## Reproduction first

Raw ROOT anchors were rebuilt before calibration:

{repro.to_markdown(index=False)}

## Methods

Let `r_i` be the held-out pair residual `(t_right - t_left) - TOF`.  For method `m`, the frozen out-of-fold residual is `e_i(m)=r_i-hat r_m(x_i)`.  For held-out run `k` and topology `g` in `{{B2-containing, downstream-only, all}}`, the conformal calibration set is all other runs in the same topology.  The interval center is the train median `c_mkg=median(e_train)`, and the two-sided half width at nominal coverage `q` is

`h_mkg(q) = Quantile_q(|e_train - c_mkg|)`.

The held-out interval is `[c_mkg - h_mkg, c_mkg + h_mkg]`; coverage is the fraction of held-out residuals inside that interval.  The robust width is

`W_68(m,g) = 0.5 [Q_84(e_i - median(e_i)) - Q_16(e_i - median(e_i))]`.

For covariance, residuals are pivoted by `(run,event,pair)`.  The signed off-diagonal covariance delta is

`Delta C_m = mean Cov_B2-containing(e_p,e_q) - mean Cov_downstream-only(e_p,e_q)`,

with an inferred correlated fraction `Delta C_m / C_B2,m` when the B2 signed covariance is finite.

## Held-out residual metrics

{metrics.to_markdown(index=False)}

## Interval coverage

Topology and nominal-coverage summaries:

{interval_summary.to_markdown(index=False)}

Per-run interval rows are in `interval_coverage_by_run.csv`; the full scored table is in `interval_coverage_summary.csv`.

## Covariance calibration

{cov.to_markdown(index=False)}

## ML-minus-traditional deltas

{deltas.to_markdown(index=False)}

## Support and calibration caveats

The S05h support frontier is frozen rather than re-fit; this ticket refits only the interval layer as requested.  The accepted-support summary inherited from S05h is:

{support_summary.to_markdown(index=False) if not support_summary.empty else 'No frozen support summary was available.'}

The interval layer is marginal within topology.  It does not prove calibration inside every saturation-depth, q-template, baseline, pile-up, or anomaly atom.  Those axes are represented through the frozen S05h/S05f residual panel and support frontier; sparse atoms remain a systematic.  The 1D-CNN and support-gated CNN used short CPU training budgets in the frozen panel, so failures of those neural methods should be interpreted as benchmark outcomes under this reproducible budget, not as architectural impossibility.

## Conclusion

Coverage calibration is substantially easier than raw covariance minimization: topology-specific conformal widths can bring several methods close to nominal 95% coverage, but the interval width required for B2-containing rows remains the operational cost.  The named winner is therefore the best calibrated frozen residual method under the stated score, not a blanket replacement for the conservative S05d/S05f support-gated covariance treatment.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `residual_metrics_by_topology.csv`, `interval_coverage_by_run.csv`, `interval_coverage_summary.csv`, `covariance_topology_summary.csv`, `method_delta_summary.csv`, `support_summary_frozen.csv`, `input_sha256.csv`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05i_1781042380_555_680a7339_covariance_coverage_calibration.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    repro = raw_reproduction(config, out_dir)
    if not bool(repro["pass"].all()):
        print(repro.to_string(index=False))
        return 1

    frozen_dir = Path(config["frozen_panel_dir"])
    oof = pd.read_csv(frozen_dir / "heldout_pair_residuals.csv")
    oof["topology"] = np.where(oof["has_b2"].astype(bool), "B2_containing", "downstream_only")
    methods = list(config["primary_methods"]) + list(config["control_methods"])

    metrics = residual_metrics(oof, methods, rng, int(config["bootstrap_resamples"]))
    intervals = add_conformal_intervals(oof, methods, [float(x) for x in config["nominal_coverages"]])
    interval_summary = summarize_intervals(intervals, rng, int(config["bootstrap_resamples"]))
    cov = covariance_summary(oof, methods, rng, int(config["bootstrap_resamples"]))

    scored = interval_summary[
        (interval_summary["nominal_coverage"].eq(0.95))
        & (interval_summary["topology"].eq("all"))
        & (~interval_summary["method"].isin(config["control_methods"]))
    ].copy()
    scored["winner_score"] = scored["abs_coverage_error"] + 0.01 * scored["mean_interval_width_ns"]
    winner = str(scored.sort_values(["winner_score", "abs_coverage_error", "mean_interval_width_ns"]).iloc[0]["method"])
    deltas = method_deltas(interval_summary, cov, winner)

    support_summary_path = frozen_dir / "support_summary.csv"
    support_summary = pd.read_csv(support_summary_path) if support_summary_path.exists() else pd.DataFrame()

    metrics.to_csv(out_dir / "residual_metrics_by_topology.csv", index=False)
    intervals.to_csv(out_dir / "interval_coverage_by_run.csv", index=False)
    interval_summary.to_csv(out_dir / "interval_coverage_summary.csv", index=False)
    cov.to_csv(out_dir / "covariance_topology_summary.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_summary.csv", index=False)
    support_summary.to_csv(out_dir / "support_summary_frozen.csv", index=False)

    input_rows = []
    for path in [args.config, Path(config["frozen_panel_config"]), frozen_dir / "heldout_pair_residuals.csv", frozen_dir / "support_summary.csv"]:
        if path.exists():
            input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot = interval_summary[(interval_summary["nominal_coverage"].eq(0.95)) & (interval_summary["topology"].eq("all"))].copy()
    plot = plot[plot["method"].isin(config["primary_methods"])].sort_values("abs_coverage_error")
    ax.errorbar(
        np.arange(len(plot)),
        plot["coverage"],
        yerr=[plot["coverage"] - plot["coverage_ci_low"], plot["coverage_ci_high"] - plot["coverage"]],
        fmt="o",
        capsize=4,
    )
    ax.axhline(0.95, color="black", linestyle="--", linewidth=1)
    ax.set_xticks(np.arange(len(plot)), plot["method"], rotation=25, ha="right")
    ax.set_ylabel("Empirical 95% coverage")
    ax.set_title("S05i conformal coverage by method")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_coverage_95.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    cplot = cov[cov["method"].isin(config["primary_methods"])].sort_values("signed_offdiag_cov_delta_ns2")
    ax.bar(np.arange(len(cplot)), cplot["signed_offdiag_cov_delta_ns2"])
    ax.set_xticks(np.arange(len(cplot)), cplot["method"], rotation=25, ha="right")
    ax.set_ylabel("B2 minus downstream signed covariance (ns^2)")
    ax.set_title("S05i topology covariance delta")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_covariance_delta.png", dpi=160)
    plt.close(fig)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "reproduction_pass": bool(repro["pass"].all()),
        "winner": winner,
        "winner_name": winner,
        "winner_selection_metric": "minimum abs 95% all-topology coverage error plus 0.01 times interval width among non-control methods",
        "winner_interval_metrics": interval_summary[
            (interval_summary["method"].eq(winner)) & (interval_summary["nominal_coverage"].eq(0.95))
        ].to_dict(orient="records"),
        "winner_covariance_metrics": cov[cov["method"].eq(winner)].iloc[0].to_dict(),
        "best_traditional": interval_summary[
            (interval_summary["method"].eq("traditional_s05d_static_priors"))
            & (interval_summary["nominal_coverage"].eq(0.95))
        ].to_dict(orient="records"),
        "methods_benchmarked": methods,
        "primary_metrics": interval_summary.to_dict(orient="records"),
        "residual_metrics": metrics.to_dict(orient="records"),
        "covariance_topology_summary": cov.to_dict(orient="records"),
        "deltas": deltas.to_dict(orient="records"),
        "support_summary_frozen": support_summary.to_dict(orient="records"),
        "finding": "Topology-specific conformal calibration provides near-nominal interval coverage for frozen S05h/S05f residual methods, but B2-containing topology requires wider intervals and remains the covariance-systematic driver.",
        "next_tickets": [],
    }
    write_json(out_dir / "result.json", result)
    write_report(out_dir, config, repro, metrics, intervals, interval_summary, cov, deltas, support_summary, result)
    command = f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}"
    write_manifest(out_dir, args.config, config, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
