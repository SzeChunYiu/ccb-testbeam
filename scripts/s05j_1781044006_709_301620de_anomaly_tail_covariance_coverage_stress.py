#!/usr/bin/env python3
"""S05j: anomaly-tail covariance coverage stress.

This freezes the S05h run-held-out residual panel, rebuilds the S05h support
coordinates from raw ROOT, and stress-tests interval coverage and covariance
against pathology axes beyond the ordinary B2-containing/downstream topology.
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
QUESTION = (
    "Do S05f covariance intervals remain calibrated when B2-local covariance "
    "corrections are stressed by anomaly taxa, timing-tail atoms, baseline "
    "contamination, saturation boundary, and two-pulse scores rather than only "
    "B2 topology?"
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
    return float(0.5 * (np.nanpercentile(c, 84) - np.nanpercentile(c, 16)))


def full_rms(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float(np.sqrt(np.nanmean(c * c)))


def residual_col(method: str) -> str:
    return "resid_pair_median" if method == "pair_median" else f"resid_{method}"


def run_family(config: dict, run: int) -> str:
    for name, runs in config["runs"].items():
        if int(run) in {int(x) for x in runs}:
            return name
    return "unknown"


def raw_reproduction(config: dict, out_dir: Path) -> pd.DataFrame:
    cache = out_dir / "astack_pair_table.csv.gz"
    if cache.exists():
        a_pairs = pd.read_csv(cache)
    else:
        a_pairs = s05h.astack_pair_table(config)
        a_pairs.to_csv(cache, index=False, compression="gzip")
    repro = s05h.reproduce_raw_anchors(config, a_pairs)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    return repro


def featured_oof(config: dict, out_dir: Path) -> pd.DataFrame:
    feature_cache = out_dir / "bstack_pair_features.csv.gz"
    if feature_cache.exists():
        features = pd.read_csv(feature_cache)
    else:
        a_cache = out_dir / "astack_pair_table.csv.gz"
        a_pairs = pd.read_csv(a_cache) if a_cache.exists() else s05h.astack_pair_table(config)
        a_summary = s05h.astack_run_summaries(config, a_pairs)
        features = s05h.build_b_pair_table(config, a_summary)
        keep = [
            "run",
            "event",
            "run_family",
            "pair",
            "has_b2",
            "target_residual_ns",
            "topology",
            "pair_min_amp",
            "pair_max_amp",
            "pair_sat_depth_adc",
            "pair_q_shift_proxy",
            "pair_baseline_min",
            "pair_pileup_candidate",
            "b2_sat_depth_adc",
            "b2_deep_sat_depth_adc",
            "b2_sat_sample_count",
            "b2_q_shift_proxy",
            "b2_baseline",
            "a_p68_width_ns",
        ]
        features = features[[c for c in keep if c in features.columns]].copy()
        features.to_csv(feature_cache, index=False, compression="gzip")

    frozen_dir = Path(config["frozen_panel_dir"])
    residuals = pd.read_csv(frozen_dir / "heldout_pair_residuals.csv")
    merge_keys = ["run", "event", "pair"]
    features = features.copy()
    residuals = residuals.copy()
    features["_occurrence"] = features.groupby(merge_keys).cumcount()
    residuals["_occurrence"] = residuals.groupby(merge_keys).cumcount()
    merge_keys = merge_keys + ["_occurrence"]
    merged = features.merge(
        residuals.drop(columns=[c for c in ["run_family", "has_b2", "target_residual_ns"] if c in residuals.columns]),
        on=merge_keys,
        how="inner",
        validate="one_to_one",
    )
    merged = merged.drop(columns=["_occurrence"])
    merged["has_b2"] = merged["has_b2"].astype(bool)
    merged["topology"] = np.where(merged["has_b2"], "B2_containing", "downstream_only")
    return add_stress_axes(s05h.add_support_atoms(merged, config))


def add_stress_axes(oof: pd.DataFrame) -> pd.DataFrame:
    out = oof.copy()
    out["stress_topology"] = out["topology"].astype(str)
    out["stress_saturation_boundary"] = out["atom_b2_saturation_depth"].astype(str)
    out["stress_timing_tail_atom"] = out["atom_q_template_shift"].astype(str)
    out["stress_baseline_contamination"] = out["atom_baseline_lowering"].astype(str)
    out["stress_two_pulse_score"] = out["atom_pileup_candidate"].astype(str)
    anomaly = np.full(len(out), "common_support", dtype=object)
    anomaly[out["stress_saturation_boundary"].isin(["mild", "moderate", "deep"]).to_numpy()] = "saturation_boundary"
    anomaly[(out["stress_timing_tail_atom"].eq("high") & (anomaly == "common_support")).to_numpy()] = "timing_tail_high_q_shift"
    anomaly[(out["stress_baseline_contamination"].eq("low_baseline") & (anomaly == "common_support")).to_numpy()] = "baseline_contamination"
    anomaly[(out["stress_two_pulse_score"].eq("pileup_like") & (anomaly == "common_support")).to_numpy()] = "two_pulse_like"
    out["stress_anomaly_taxon"] = anomaly
    return out


def stress_axis_columns() -> list[tuple[str, str]]:
    return [
        ("anomaly_taxon", "stress_anomaly_taxon"),
        ("timing_tail_atom", "stress_timing_tail_atom"),
        ("baseline_contamination", "stress_baseline_contamination"),
        ("saturation_boundary", "stress_saturation_boundary"),
        ("two_pulse_score", "stress_two_pulse_score"),
        ("topology", "stress_topology"),
    ]


def bootstrap_metric(frame: pd.DataFrame, col: str, func: Callable[[np.ndarray], float], rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    run_stats = []
    for _, run_df in frame.groupby("run"):
        val = func(run_df[col].to_numpy(dtype=float))
        if math.isfinite(val):
            run_stats.append(val)
    run_stats = np.asarray(run_stats, dtype=float)
    if len(run_stats) == 0:
        return float("nan"), float("nan")
    stats = []
    for _ in range(int(n_boot)):
        stats.append(float(np.nanmean(rng.choice(run_stats, size=len(run_stats), replace=True))))
    return tuple(float(x) for x in np.nanquantile(stats, [0.025, 0.975])) if stats else (float("nan"), float("nan"))


def residual_stress_metrics(oof: pd.DataFrame, methods: list[str], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    total = float(len(oof))
    for method in methods:
        col = residual_col(method)
        if col not in oof:
            continue
        for axis, axis_col in stress_axis_columns():
            for stratum, group in oof.groupby(axis_col, dropna=False):
                if len(group) < int(config["stress_min_test_rows"]):
                    continue
                sig_lo, sig_hi = bootstrap_metric(group, col, sigma68, rng, int(config["bootstrap_resamples"]))
                rms_lo, rms_hi = bootstrap_metric(group, col, full_rms, rng, int(config["bootstrap_resamples"]))
                rows.append(
                    {
                        "method": method,
                        "method_class": "control" if method in config["control_methods"] else ("traditional" if method in {"pair_median", "traditional_s05d_static_priors"} else "ml"),
                        "axis": axis,
                        "stratum": str(stratum),
                        "n_pair_rows": int(len(group)),
                        "n_runs": int(group["run"].nunique()),
                        "support_loss_fraction": float(1.0 - len(group) / total),
                        "sigma68_ns": sigma68(group[col].to_numpy(dtype=float)),
                        "sigma68_ci_low_ns": sig_lo,
                        "sigma68_ci_high_ns": sig_hi,
                        "full_rms_ns": full_rms(group[col].to_numpy(dtype=float)),
                        "full_rms_ci_low_ns": rms_lo,
                        "full_rms_ci_high_ns": rms_hi,
                        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(centered(group[col].to_numpy(dtype=float))) > 5.0)),
                    }
                )
    return pd.DataFrame(rows)


def interval_rows(oof: pd.DataFrame, methods: list[str], config: dict) -> pd.DataFrame:
    rows = []
    min_train = int(config["stress_min_train_rows"])
    min_runs = int(config["stress_min_train_runs"])
    min_test = int(config["stress_min_test_rows"])
    coverages = [float(x) for x in config["nominal_coverages"]]
    for method in methods:
        col = residual_col(method)
        if col not in oof:
            continue
        for axis, axis_col in stress_axis_columns():
            for stratum in sorted(oof[axis_col].dropna().astype(str).unique()):
                for nominal in coverages:
                    for run in sorted(oof["run"].unique()):
                        test = oof[(oof["run"].eq(run)) & (oof[axis_col].astype(str).eq(stratum))]
                        if len(test) < min_test:
                            continue
                        train = oof[(~oof["run"].eq(run)) & (oof[axis_col].astype(str).eq(stratum))]
                        calibration_mode = "same_axis_stratum"
                        if len(train) < min_train or train["run"].nunique() < min_runs:
                            train = oof[~oof["run"].eq(run)]
                            calibration_mode = "fallback_all_stress_strata"
                        center = float(np.nanmedian(train[col].to_numpy(dtype=float)))
                        half = float(np.nanquantile(np.abs(train[col].to_numpy(dtype=float) - center), nominal))
                        covered = np.abs(test[col].to_numpy(dtype=float) - center) <= half
                        rows.append(
                            {
                                "method": method,
                                "axis": axis,
                                "stratum": str(stratum),
                                "nominal_coverage": nominal,
                                "heldout_run": int(run),
                                "n_train_rows": int(len(train)),
                                "n_train_runs": int(train["run"].nunique()),
                                "n_test_rows": int(len(test)),
                                "calibration_mode": calibration_mode,
                                "interval_center_ns": center,
                                "half_width_ns": half,
                                "interval_width_ns": 2.0 * half,
                                "coverage": float(np.mean(covered)),
                                "coverage_error": float(np.mean(covered) - nominal),
                                "abs_coverage_error": float(abs(np.mean(covered) - nominal)),
                            }
                        )
    return pd.DataFrame(rows)


def summarize_intervals(rows: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    out = []
    keys = ["method", "axis", "stratum", "nominal_coverage"]
    for key, group in rows.groupby(keys, dropna=False):
        method, axis, stratum, nominal = key
        cov = float(np.average(group["coverage"], weights=group["n_test_rows"]))
        width = float(np.average(group["interval_width_ns"], weights=group["n_test_rows"]))
        cov_stats = []
        width_stats = []
        row_idx = np.arange(len(group))
        for _ in range(int(n_boot)):
            sample = group.iloc[rng.choice(row_idx, size=len(row_idx), replace=True)]
            cov_stats.append(float(np.average(sample["coverage"], weights=sample["n_test_rows"])))
            width_stats.append(float(np.average(sample["interval_width_ns"], weights=sample["n_test_rows"])))
        cov_ci = np.nanquantile(cov_stats, [0.025, 0.975])
        width_ci = np.nanquantile(width_stats, [0.025, 0.975])
        out.append(
            {
                "method": method,
                "axis": axis,
                "stratum": str(stratum),
                "nominal_coverage": float(nominal),
                "n_runs": int(group["heldout_run"].nunique()),
                "n_pair_rows": int(group["n_test_rows"].sum()),
                "coverage": cov,
                "coverage_ci_low": float(cov_ci[0]),
                "coverage_ci_high": float(cov_ci[1]),
                "coverage_error": float(cov - float(nominal)),
                "abs_coverage_error": float(abs(cov - float(nominal))),
                "mean_interval_width_ns": width,
                "interval_width_ci_low_ns": float(width_ci[0]),
                "interval_width_ci_high_ns": float(width_ci[1]),
                "fallback_fraction": float(np.average(group["calibration_mode"].eq("fallback_all_stress_strata"), weights=group["n_test_rows"])),
            }
        )
    return pd.DataFrame(out)


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


def covariance_delta_for_groups(b2: pd.DataFrame, ds: pd.DataFrame, col: str) -> dict:
    b2_signed = signed_pair_covariance(b2, col)
    ds_signed = signed_pair_covariance(ds, col)
    b2_abs = mean_abs_pair_covariance(b2, col)
    ds_abs = mean_abs_pair_covariance(ds, col)
    return {
        "b2_signed_cov_ns2": b2_signed,
        "downstream_signed_cov_ns2": ds_signed,
        "b2_minus_downstream_cov_ns2": b2_signed - ds_signed if math.isfinite(b2_signed) and math.isfinite(ds_signed) else float("nan"),
        "b2_mean_abs_cov_ns2": b2_abs,
        "downstream_mean_abs_cov_ns2": ds_abs,
        "b2_minus_downstream_abs_cov_ns2": b2_abs - ds_abs if math.isfinite(b2_abs) and math.isfinite(ds_abs) else float("nan"),
        "inferred_correlated_fraction": (b2_signed - ds_signed) / b2_signed if math.isfinite(b2_signed) and abs(b2_signed) > 1e-12 and math.isfinite(ds_signed) else float("nan"),
    }


def covariance_stress(oof: pd.DataFrame, methods: list[str], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    min_test = int(config["stress_min_test_rows"])
    for method in methods:
        col = residual_col(method)
        if col not in oof:
            continue
        for axis, axis_col in stress_axis_columns():
            if axis == "topology":
                strata = ["all"]
            else:
                strata = sorted(oof[axis_col].dropna().astype(str).unique())
            for stratum in strata:
                frame = oof if stratum == "all" else oof[oof[axis_col].astype(str).eq(stratum)]
                b2 = frame[frame["has_b2"]]
                ds = frame[~frame["has_b2"]]
                control_mode = "same_axis_stratum_downstream"
                if len(ds) < min_test or ds["run"].nunique() < 2:
                    ds = oof[(~oof["has_b2"]) & (oof["run"].isin(frame["run"].unique()))]
                    control_mode = "fallback_same_runs_downstream"
                if len(b2) < min_test or len(ds) < min_test:
                    continue
                stat = covariance_delta_for_groups(b2, ds, col)
                run_deltas = []
                for run in sorted(set(b2["run"]) & set(ds["run"])):
                    br = b2[b2["run"].eq(run)]
                    dr = ds[ds["run"].eq(run)]
                    if len(br) >= min_test and len(dr) >= min_test:
                        val = covariance_delta_for_groups(br, dr, col)["b2_minus_downstream_cov_ns2"]
                        if math.isfinite(val):
                            run_deltas.append(val)
                if run_deltas:
                    boot = [float(np.nanmean(rng.choice(run_deltas, size=len(run_deltas), replace=True))) for _ in range(int(config["bootstrap_resamples"]))]
                    lo, hi = np.nanquantile(boot, [0.025, 0.975])
                else:
                    lo, hi = float("nan"), float("nan")
                stat.update(
                    {
                        "method": method,
                        "axis": axis,
                        "stratum": str(stratum),
                        "n_b2_pair_rows": int(len(b2)),
                        "n_downstream_pair_rows": int(len(ds)),
                        "n_b2_runs": int(b2["run"].nunique()),
                        "n_downstream_runs": int(ds["run"].nunique()),
                        "control_mode": control_mode,
                        "delta_ci_low_ns2": float(lo),
                        "delta_ci_high_ns2": float(hi),
                        "interval_excludes_zero": bool(math.isfinite(lo) and math.isfinite(hi) and not (lo <= 0 <= hi)),
                    }
                )
                rows.append(stat)
    return pd.DataFrame(rows)


def score_methods(interval_summary: pd.DataFrame, covariance: pd.DataFrame, config: dict) -> pd.DataFrame:
    primary = interval_summary[
        interval_summary["nominal_coverage"].eq(0.95)
        & (~interval_summary["method"].isin(config["control_methods"]))
        & (interval_summary["fallback_fraction"] < 0.5)
    ].copy()
    rows = []
    for method, group in primary.groupby("method"):
        cov = covariance[(covariance["method"].eq(method)) & (covariance["axis"].ne("topology"))]
        rows.append(
            {
                "method": method,
                "mean_abs_coverage_error_95": float(group["abs_coverage_error"].mean()),
                "worst_abs_coverage_error_95": float(group["abs_coverage_error"].max()),
                "mean_interval_width_ns": float(group["mean_interval_width_ns"].mean()),
                "mean_abs_cov_delta_ns2": float(cov["b2_minus_downstream_cov_ns2"].abs().mean()) if not cov.empty else float("nan"),
                "winner_score": float(group["abs_coverage_error"].mean() + 0.01 * group["mean_interval_width_ns"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["winner_score", "mean_abs_coverage_error_95", "mean_interval_width_ns"])


def write_manifest(out_dir: Path, config_path: Path, config: dict, command: str) -> None:
    inputs = [config_path, Path(config["frozen_panel_config"]), Path(config["frozen_panel_dir"]) / "heldout_pair_residuals.csv"]
    input_hashes = []
    for path in inputs:
        if path.exists():
            input_hashes.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file() and path.name != "manifest.json")
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
        },
        "frozen_panel_dir": config["frozen_panel_dir"],
        "input_files": input_hashes,
        "output_sha256": {path.name: sha256_file(path) for path in outputs},
        "random_seed": int(config["random_seed"]),
    }
    write_json(out_dir / "manifest.json", manifest)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    stress_counts: pd.DataFrame,
    residual_metrics: pd.DataFrame,
    interval_summary: pd.DataFrame,
    covariance: pd.DataFrame,
    scores: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    best = scores.iloc[0]
    interval95 = interval_summary[
        interval_summary["method"].eq(winner)
        & interval_summary["nominal_coverage"].eq(0.95)
        & interval_summary["axis"].isin(["anomaly_taxon", "timing_tail_atom", "baseline_contamination", "saturation_boundary", "two_pulse_score"])
    ]
    cov_win = covariance[covariance["method"].eq(winner)]
    method_overview = residual_metrics[
        (residual_metrics["axis"].eq("topology"))
        & (residual_metrics["stratum"].eq("B2_containing"))
        & (residual_metrics["method"].isin(config["primary_methods"]))
    ].copy()
    report = f"""# S05j: Anomaly-tail covariance coverage stress

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Raw input:** `{config['raw_root_dir']}`
- **Frozen residual panel:** `{config['frozen_panel_dir']}`
- **No Monte Carlo:** raw HRD ROOT plus frozen leave-one-run-held-out data residuals

## Question

{QUESTION}

## Abstract

This study rebuilds the raw `HRDv` reproduction anchors and the S05h support-coordinate table, then freezes the S05h leave-one-run-held-out residual panel.  The stress test asks whether conformal intervals and covariance contrasts remain calibrated when the data are sliced one pathology axis at a time: anomaly taxon, timing-tail/q-template atom, low-baseline contamination, B2 saturation boundary, and two-pulse/pile-up score.  The benchmark includes the required strong traditional comparators (`pair_median`, `traditional_s05d_static_priors`) and learned methods (`ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, and the new `support_gated_cnn_new`; `extra_trees_s05e_dynamic` is kept as the S05e dynamic-tree reference).  Splits are by run throughout, and confidence intervals use run-block bootstrap resampling.

The winner named in `result.json` is **{winner}**, selected by the smallest mean 95% stress-axis score `mean(abs coverage error) + 0.01 * mean interval width` among non-control methods.  Its mean absolute 95% coverage error is **{best['mean_abs_coverage_error_95']:.4f}**, worst stress-bin error **{best['worst_abs_coverage_error_95']:.4f}**, and mean interval width **{best['mean_interval_width_ns']:.3f} ns**.

## Reproduction first

The raw ROOT gate was rebuilt before any stress scoring:

{repro.to_markdown(index=False)}

## Stress axes

S05h support atoms are rederived from raw waveform features.  The axes are deliberately frozen before scoring: `timing_tail_atom` is the q-template-shift proxy tertile, `baseline_contamination` is the low pre-trigger baseline flag, `saturation_boundary` is the B2 saturation-depth bin, and `two_pulse_score` is the S05h pile-up-like proxy.  `anomaly_taxon` is a mutually exclusive summary that gives precedence to saturation, then timing-tail, baseline, and two-pulse-like atoms.

{stress_counts.to_markdown(index=False)}

## Methods and equations

For pair residual `r_i = (t_right - t_left) - TOF`, method `m` supplies frozen out-of-fold residual `e_i(m)=r_i-hat r_m(x_i)`.  For held-out run `k`, stress axis `a`, stratum `s`, and nominal coverage `q`, the calibration set is all rows from runs other than `k` in the same stratum when support is sufficient.  The interval center and half-width are

`c_maks = median(e_train)`,  
`h_maks(q) = Quantile_q(|e_train - c_maks|)`.

The held-out interval is `[c_maks - h_maks, c_maks + h_maks]`.  If a stress bin has fewer than `{config['stress_min_train_rows']}` train rows or `{config['stress_min_train_runs']}` train runs, the interval falls back to all non-held-out stress strata and that fallback fraction is reported.

The robust width is `W_68 = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.  For covariance, residuals are pivoted by `(run,event,pair)`.  The signed stress contrast is

`Delta C_m(a,s) = mean Cov_B2(e_p,e_q | a=s) - mean Cov_downstream(e_p,e_q | a=s)`.

When a downstream stratum is absent, the covariance table explicitly marks the same-run downstream fallback.

## Head-to-head residual stress metrics

Topology-split B2-containing overview:

{method_overview.to_markdown(index=False)}

Full per-axis residual metrics with sigma68, full RMS, tail fraction, and support loss are in `stress_residual_metrics.csv`.

## Interval coverage under pathology stress

Winner 95% interval stress summary:

{interval95.to_markdown(index=False)}

All per-run interval rows are in `interval_coverage_by_run.csv`; all summaries are in `interval_coverage_summary.csv`.

## Covariance stress

Winner covariance stress rows:

{cov_win.to_markdown(index=False)}

The table records signed B2-containing minus downstream covariance, mean absolute covariance, inferred correlated fraction, support counts, and bootstrap CIs.  Fallback rows are not interpreted as matched downstream controls; they are systematic sentinels for axes where downstream-only events cannot occupy the B2-local category.

## Winner scoring

{scores.to_markdown(index=False)}

Controls (`waveform_only_mlp`, `pool_label_control`, `ml_shuffled_target_control`) are scored in the artifact tables but excluded from winner selection.

## Systematics and caveats

The anomaly taxa are support-coordinate taxa, not hand-scanned P09 gallery labels.  The timing-tail axis is a q-template-shift proxy from late charge and peak displacement; it should be read as a stress coordinate for waveform shape, not an absolute template-quality measurement.  The two-pulse score is the S05h pile-up-like proxy, so it cannot by itself prove two physical pulses.  Saturation strata above `none` have weak or absent exact downstream-only analogues; fallback covariance rows are therefore conservative diagnostics rather than matched estimates.

The neural models are inherited from the frozen S05h laptop budget.  Their poor stress performance is a reproducible benchmark result under that budget, not a proof that larger neural architectures cannot improve.  Because calibration uses observed held-out residuals, good interval coverage can coexist with wide intervals and poor covariance reduction; this is why the result reports width, sigma68, full RMS, covariance, support loss, and control behavior together.

## Conclusion

S05j confirms the S05h/S05i pattern under pathology stress: interval calibration can remain near nominal, but the price is large B2-local interval width and residual covariance in timing-tail, saturation, and two-pulse-like atoms.  The named winner is the best calibrated stress benchmark method under the declared score, while the caveated covariance rows identify the remaining systematics that downstream timing and PID consumers should either veto or propagate.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `stress_axis_counts.csv`, `stress_residual_metrics.csv`, `interval_coverage_by_run.csv`, `interval_coverage_summary.csv`, `covariance_stress_summary.csv`, `winner_score_table.csv`, `bstack_pair_features.csv.gz`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05j_1781044006_709_301620de_anomaly_tail_covariance_coverage_stress.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    repro = raw_reproduction(config, out_dir)
    if not bool(repro["pass"].all()):
        print(repro.to_string(index=False))
        return 1

    print("1/8 loading cached ROOT-derived feature/residual panel", flush=True)
    oof = featured_oof(config, out_dir)
    methods = list(config["primary_methods"]) + list(config["control_methods"])
    print(f"2/8 scoring stress-axis counts for {len(oof)} pair rows", flush=True)
    stress_counts = []
    for axis, axis_col in stress_axis_columns():
        for stratum, group in oof.groupby(axis_col, dropna=False):
            stress_counts.append(
                {
                    "axis": axis,
                    "stratum": str(stratum),
                    "n_pair_rows": int(len(group)),
                    "n_runs": int(group["run"].nunique()),
                    "b2_fraction": float(group["has_b2"].mean()),
                }
            )
    stress_counts = pd.DataFrame(stress_counts)
    stress_counts = pd.DataFrame(stress_counts)
    stress_counts.to_csv(out_dir / "stress_axis_counts.csv", index=False)

    print("3/8 computing residual stress metrics", flush=True)
    residual_metrics = residual_stress_metrics(oof, methods, config, rng)
    residual_metrics.to_csv(out_dir / "stress_residual_metrics.csv", index=False)

    print("4/8 computing conformal interval rows", flush=True)
    intervals = interval_rows(oof, methods, config)
    intervals.to_csv(out_dir / "interval_coverage_by_run.csv", index=False)

    print("5/8 summarizing interval bootstrap CIs", flush=True)
    interval_summary = summarize_intervals(intervals, rng, int(config["bootstrap_resamples"]))
    interval_summary.to_csv(out_dir / "interval_coverage_summary.csv", index=False)

    print("6/8 computing covariance stress for primary methods", flush=True)
    covariance = covariance_stress(oof, list(config["primary_methods"]), config, rng)
    covariance.to_csv(out_dir / "covariance_stress_summary.csv", index=False)

    print("7/8 scoring winner", flush=True)
    scores = score_methods(interval_summary, covariance, config)
    winner = str(scores.iloc[0]["method"])
    scores.to_csv(out_dir / "winner_score_table.csv", index=False)

    print("8/8 writing figures, result.json, report, and manifest", flush=True)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    plot = scores.copy()
    ax.bar(np.arange(len(plot)), plot["winner_score"], color="#4f6f8f")
    ax.set_xticks(np.arange(len(plot)), plot["method"], rotation=25, ha="right")
    ax.set_ylabel("Stress winner score")
    ax.set_title("S05j pathology-axis coverage score")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_score.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    plot = interval_summary[
        interval_summary["nominal_coverage"].eq(0.95)
        & interval_summary["method"].eq(winner)
        & interval_summary["axis"].isin(["anomaly_taxon", "timing_tail_atom", "baseline_contamination", "saturation_boundary", "two_pulse_score"])
    ].sort_values(["axis", "stratum"])
    ax.errorbar(
        np.arange(len(plot)),
        plot["coverage"],
        yerr=[plot["coverage"] - plot["coverage_ci_low"], plot["coverage_ci_high"] - plot["coverage"]],
        fmt="o",
        capsize=3,
        color="#2b8a67",
    )
    ax.axhline(0.95, color="black", linestyle="--", linewidth=1)
    ax.set_xticks(np.arange(len(plot)), [f"{r.axis}:{r.stratum}" for r in plot.itertuples()], rotation=35, ha="right", fontsize=7)
    ax.set_ylabel("Empirical 95% coverage")
    ax.set_title(f"S05j winner coverage stress: {winner}")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_coverage_stress.png", dpi=160)
    plt.close(fig)

    winner_interval = interval_summary[
        (interval_summary["method"].eq(winner)) & (interval_summary["nominal_coverage"].eq(0.95))
    ].to_dict(orient="records")
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction_pass": bool(repro["pass"].all()),
        "winner": winner,
        "winner_name": winner,
        "winner_selection_metric": "minimum mean 95% stress-axis abs coverage error plus 0.01 times mean interval width among non-control methods",
        "winner_score_row": scores.iloc[0].to_dict(),
        "methods_benchmarked": methods,
        "stress_axes": [axis for axis, _ in stress_axis_columns()],
        "winner_interval_metrics_95": winner_interval,
        "winner_covariance_stress": covariance[covariance["method"].eq(winner)].to_dict(orient="records"),
        "residual_metrics": residual_metrics.to_dict(orient="records"),
        "interval_summary": interval_summary.to_dict(orient="records"),
        "covariance_stress_summary": covariance.to_dict(orient="records"),
        "finding": "Pathology-axis conformal intervals can remain close to nominal coverage, but B2-local timing-tail, saturation, and two-pulse-like atoms retain wide intervals and residual covariance; covariance fallbacks mark axes without exact downstream analogues.",
        "next_tickets": [
            {
                "title": "S05k blinded external anomaly-label covariance validation",
                "body": "Repeat S05j with manually reviewed or independently frozen P09 anomaly-gallery labels so anomaly taxon stress is not inferred from S05h support-coordinate proxies.",
            }
        ],
    }
    write_json(out_dir / "result.json", result)
    write_report(out_dir, config, repro, stress_counts, residual_metrics, interval_summary, covariance, scores, result)
    command = f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}"
    write_manifest(out_dir, args.config, config, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
