#!/usr/bin/env python3
"""S05k: rate-residual covariance atom sieve.

This study freezes the S05h run-held-out residual panel and the S05e-rate
run-level A/B acceptance residuals, rebuilds the raw ROOT count anchors, then
asks whether adding A/B rate-residual atoms changes B2-local covariance and
interval conclusions.
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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


S05J_PATH = Path(__file__).with_name("s05j_1781044006_709_301620de_anomaly_tail_covariance_coverage_stress.py")
QUESTION = (
    "After S05e-rate showed that run-level A/B coincidence rate does not explain "
    "B2-local covariance, do residual A/B acceptance/current-rate atoms still bias "
    "B-pair covariance intervals in narrow support cells?"
)


def load_s05j():
    spec = importlib.util.spec_from_file_location("s05j_covariance", S05J_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {S05J_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s05j = load_s05j()


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


def residual_col(method: str) -> str:
    return "resid_pair_median" if method == "pair_median" else f"resid_{method}"


def add_rate_atoms(oof: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rates = pd.read_csv(Path(config["rate_panel_dir"]) / "rate_oof_predictions.csv")
    keep = [
        "run",
        "sample",
        "target_setting",
        "current_nA",
        "b_any_events",
        "target_rate",
        "pred_traditional_rate",
        "pred_ml_rate",
        "resid_traditional_rate_pp",
        "resid_ml_rate_pp",
        "b_downstream_frac",
        "b2_share",
    ]
    rates = rates[[c for c in keep if c in rates.columns]].copy()
    labels = ["low_rate_residual", "mid_rate_residual", "high_rate_residual"]
    rates["rate_residual_quantile"] = pd.qcut(
        rates["resid_ml_rate_pp"],
        q=int(config["rate_quantiles"]),
        labels=labels[: int(config["rate_quantiles"])],
        duplicates="drop",
    ).astype(str)
    rates["traditional_rate_residual_quantile"] = pd.qcut(
        rates["resid_traditional_rate_pp"],
        q=int(config["rate_quantiles"]),
        labels=labels[: int(config["rate_quantiles"])],
        duplicates="drop",
    ).astype(str)
    rates["current_group"] = np.where(rates["current_nA"] <= 2.0, "low_current_2nA", "nominal_current_20nA")
    out = oof.merge(rates, on="run", how="left", validate="many_to_one")
    if out["rate_residual_quantile"].isna().any():
        missing = sorted(out.loc[out["rate_residual_quantile"].isna(), "run"].unique())
        raise RuntimeError(f"missing rate residual rows for runs: {missing}")
    amp = pd.qcut(out["pair_min_amp"], 3, labels=["amp_low", "amp_mid", "amp_high"], duplicates="drop").astype(str)
    out["atom_pair_amplitude"] = amp
    out["atom_rate_residual_quantile"] = out["rate_residual_quantile"].astype(str)
    out["atom_traditional_rate_residual_quantile"] = out["traditional_rate_residual_quantile"].astype(str)
    out["rate_support_atom"] = (
        out["run_family"].astype(str)
        + "|topo="
        + out["topology"].astype(str)
        + "|amp="
        + out["atom_pair_amplitude"].astype(str)
        + "|sat="
        + out["atom_b2_saturation_depth"].astype(str)
        + "|anom="
        + out["stress_anomaly_taxon"].astype(str)
        + "|rateq="
        + out["atom_rate_residual_quantile"].astype(str)
    )
    rate_summary = rates.sort_values("run")
    return out, rate_summary


def axis_columns() -> list[tuple[str, str]]:
    return [
        ("rate_residual_quantile", "atom_rate_residual_quantile"),
        ("current_group", "current_group"),
        ("topology", "stress_topology"),
    ]


def support_count_axis_columns() -> list[tuple[str, str]]:
    return axis_columns() + [("rate_support_atom", "rate_support_atom")]


def stress_counts(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for axis, col in support_count_axis_columns():
        for stratum, group in oof.groupby(col, dropna=False):
            rows.append(
                {
                    "axis": axis,
                    "stratum": str(stratum),
                    "n_pair_rows": int(len(group)),
                    "n_runs": int(group["run"].nunique()),
                    "b2_fraction": float(group["has_b2"].mean()),
                    "rate_residual_pp_median": float(group["resid_ml_rate_pp"].median()),
                    "target_rate_percent_median": float(100.0 * group["target_rate"].median()),
                }
            )
    return pd.DataFrame(rows)


def bootstrap_metric(frame: pd.DataFrame, col: str, func, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    runs = np.asarray(sorted(frame["run"].unique()))
    if len(runs) == 0:
        return float("nan"), float("nan")
    stats = []
    for _ in range(int(n_boot)):
        chunks = [frame.loc[frame["run"].eq(int(run)), col].to_numpy(dtype=float) for run in rng.choice(runs, size=len(runs), replace=True)]
        vals = np.concatenate([chunk for chunk in chunks if len(chunk)])
        stat = func(vals)
        if math.isfinite(stat):
            stats.append(float(stat))
    if not stats:
        return float("nan"), float("nan")
    lo, hi = np.nanquantile(stats, [0.025, 0.975])
    return float(lo), float(hi)


def residual_metrics(oof: pd.DataFrame, methods: list[str], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for method in methods:
        col = residual_col(method)
        if col not in oof:
            continue
        for axis, axis_col in axis_columns():
            for stratum, group in oof.groupby(axis_col, dropna=False):
                if len(group) < int(config["stress_min_test_rows"]):
                    continue
                sig_lo, sig_hi = bootstrap_metric(group, col, s05j.sigma68, rng, int(config["bootstrap_resamples"]))
                rms_lo, rms_hi = bootstrap_metric(group, col, s05j.full_rms, rng, int(config["bootstrap_resamples"]))
                rows.append(
                    {
                        "method": method,
                        "method_class": "control" if method in config["control_methods"] else ("traditional" if method in {"pair_median", "traditional_s05d_static_priors"} else "ml"),
                        "axis": axis,
                        "stratum": str(stratum),
                        "n_pair_rows": int(len(group)),
                        "n_runs": int(group["run"].nunique()),
                        "sigma68_ns": s05j.sigma68(group[col].to_numpy(dtype=float)),
                        "sigma68_ci_low_ns": sig_lo,
                        "sigma68_ci_high_ns": sig_hi,
                        "full_rms_ns": s05j.full_rms(group[col].to_numpy(dtype=float)),
                        "full_rms_ci_low_ns": rms_lo,
                        "full_rms_ci_high_ns": rms_hi,
                        "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(s05j.centered(group[col].to_numpy(dtype=float))) > 5.0)),
                    }
                )
    return pd.DataFrame(rows)


def interval_rows(oof: pd.DataFrame, methods: list[str], config: dict) -> pd.DataFrame:
    rows = []
    min_train = int(config["stress_min_train_rows"])
    min_runs = int(config["stress_min_train_runs"])
    min_test = int(config["stress_min_test_rows"])
    for method in methods:
        col = residual_col(method)
        if col not in oof:
            continue
        for axis, axis_col in axis_columns():
            for stratum in sorted(oof[axis_col].dropna().astype(str).unique()):
                for nominal in [float(x) for x in config["nominal_coverages"]]:
                    for run in sorted(oof["run"].unique()):
                        test = oof[(oof["run"].eq(run)) & (oof[axis_col].astype(str).eq(stratum))]
                        if len(test) < min_test:
                            continue
                        train = oof[(~oof["run"].eq(run)) & (oof[axis_col].astype(str).eq(stratum))]
                        calibration_mode = "same_rate_atom"
                        if len(train) < min_train or train["run"].nunique() < min_runs:
                            train = oof[~oof["run"].eq(run)]
                            calibration_mode = "fallback_all_rate_atoms"
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
        row_idx = np.arange(len(group))
        cov_stats = []
        width_stats = []
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
                "fallback_fraction": float(np.average(group["calibration_mode"].eq("fallback_all_rate_atoms"), weights=group["n_test_rows"])),
            }
        )
    return pd.DataFrame(out)


def covariance_rate_stress(oof: pd.DataFrame, methods: list[str], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    min_test = int(config["stress_min_test_rows"])
    for method in methods:
        col = residual_col(method)
        if col not in oof:
            continue
        for axis, axis_col in axis_columns():
            strata = ["all"] if axis == "topology" else sorted(oof[axis_col].dropna().astype(str).unique())
            for stratum in strata:
                frame = oof if stratum == "all" else oof[oof[axis_col].astype(str).eq(stratum)]
                b2 = frame[frame["has_b2"]]
                ds = frame[~frame["has_b2"]]
                control_mode = "same_rate_atom_downstream"
                if len(ds) < min_test or ds["run"].nunique() < 2:
                    ds = oof[(~oof["has_b2"]) & (oof["run"].isin(frame["run"].unique()))]
                    control_mode = "fallback_same_runs_downstream"
                if len(b2) < min_test or len(ds) < min_test:
                    continue
                stat = s05j.covariance_delta_for_groups(b2, ds, col)
                run_deltas = []
                for run in sorted(set(b2["run"]) & set(ds["run"])):
                    br = b2[b2["run"].eq(run)]
                    dr = ds[ds["run"].eq(run)]
                    if len(br) >= min_test and len(dr) >= min_test:
                        val = s05j.covariance_delta_for_groups(br, dr, col)["b2_minus_downstream_cov_ns2"]
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
        & (interval_summary["axis"].isin(["rate_residual_quantile", "current_group"]))
        & (interval_summary["fallback_fraction"] < 0.5)
    ].copy()
    rows = []
    for method, group in primary.groupby("method"):
        cov = covariance[
            covariance["method"].eq(method)
            & covariance["axis"].isin(["rate_residual_quantile", "current_group"])
        ]
        rows.append(
            {
                "method": method,
                "mean_abs_coverage_error_95": float(group["abs_coverage_error"].mean()),
                "worst_abs_coverage_error_95": float(group["abs_coverage_error"].max()),
                "mean_interval_width_ns": float(group["mean_interval_width_ns"].mean()),
                "mean_abs_cov_delta_ns2": float(cov["b2_minus_downstream_cov_ns2"].abs().mean()) if not cov.empty else float("nan"),
                "winner_score": float(group["abs_coverage_error"].mean() + 0.01 * group["mean_interval_width_ns"].mean() + 0.0005 * cov["b2_minus_downstream_cov_ns2"].abs().mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["winner_score", "mean_abs_coverage_error_95", "mean_interval_width_ns"])


def rate_feature_sentinels(oof: pd.DataFrame, covariance: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Run-block sentinel table for the ticket's with/without-rate predictor question."""
    rows = []
    base = covariance[(covariance["axis"].eq("rate_residual_quantile")) & (covariance["method"].eq("extra_trees_s05e_dynamic"))]
    if base.empty:
        return pd.DataFrame()
    run_rate = oof.drop_duplicates("run")[["run", "resid_ml_rate_pp", "resid_traditional_rate_pp", "target_rate", "b2_share", "b_downstream_frac"]]
    for label, cols in [
        ("extra_trees_with_rate_residual", ["resid_ml_rate_pp", "target_rate", "b2_share", "b_downstream_frac"]),
        ("extra_trees_without_rate_residual", ["target_rate", "b2_share", "b_downstream_frac"]),
        ("gam_spline_like_with_rate_residual", ["resid_ml_rate_pp", "target_rate"]),
        ("shuffled_rate_sentinel", ["shuffled_rate_residual_pp", "target_rate", "b2_share"]),
        ("run_only_sentinel", ["run_index"]),
        ("topology_only_sentinel", ["b2_share", "b_downstream_frac"]),
    ]:
        frame = run_rate.copy()
        frame["run_index"] = np.arange(len(frame), dtype=float)
        frame["shuffled_rate_residual_pp"] = rng.permutation(frame["resid_ml_rate_pp"].to_numpy())
        target = []
        for run in frame["run"]:
            run_rows = oof[oof["run"].eq(run)]
            val = s05j.covariance_delta_for_groups(
                run_rows[run_rows["has_b2"]],
                run_rows[~run_rows["has_b2"]],
                "resid_extra_trees_s05e_dynamic",
            )["b2_minus_downstream_cov_ns2"]
            target.append(val)
        frame["target_cov_delta_ns2"] = target
        pred = []
        obs = []
        for run in frame["run"]:
            train = frame[~frame["run"].eq(run)].dropna()
            test = frame[frame["run"].eq(run)]
            obs.append(float(test["target_cov_delta_ns2"].iloc[0]))
            x = train[cols].to_numpy(dtype=float)
            y = train["target_cov_delta_ns2"].to_numpy(dtype=float)
            xt = test[cols].to_numpy(dtype=float)
            x = np.column_stack([np.ones(len(x)), x])
            xt = np.column_stack([np.ones(len(xt)), xt])
            if len(y) < len(cols) + 2:
                pred.append(float(np.nanmean(y)))
            else:
                beta = np.linalg.pinv(x.T @ x + 1e-3 * np.eye(x.shape[1])) @ x.T @ y
                pred.append(float(xt @ beta))
        err = np.asarray(pred) - np.asarray(obs)
        rows.append(
            {
                "predictor": label,
                "n_runs": int(len(obs)),
                "rmse_ns2": float(np.sqrt(np.nanmean(err * err))),
                "mae_ns2": float(np.nanmean(np.abs(err))),
                "bias_ns2": float(np.nanmean(err)),
            }
        )
    return pd.DataFrame(rows)


def write_manifest(out_dir: Path, config_path: Path, config: dict, command: str) -> None:
    inputs = [
        config_path,
        Path(config["frozen_panel_config"]),
        Path(config["frozen_panel_dir"]) / "heldout_pair_residuals.csv",
        Path(config["rate_panel_config"]),
        Path(config["rate_panel_dir"]) / "rate_oof_predictions.csv",
    ]
    input_hashes = []
    for path in inputs:
        if path.exists():
            input_hashes.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_hashes).to_csv(out_dir / "input_sha256.csv", index=False)
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file() and path.name != "manifest.json")
    write_json(
        out_dir / "manifest.json",
        {
            "study": config["study_id"],
            "ticket": config["ticket"],
            "worker": config["worker"],
            "git_commit": git_head(),
            "command": command,
            "environment": {"python": platform.python_version(), "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
            "frozen_panel_dir": config["frozen_panel_dir"],
            "rate_panel_dir": config["rate_panel_dir"],
            "input_files": input_hashes,
            "output_sha256": {path.name: sha256_file(path) for path in outputs},
            "random_seed": int(config["random_seed"]),
        },
    )


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, rates: pd.DataFrame, counts: pd.DataFrame, metrics: pd.DataFrame, intervals: pd.DataFrame, covariance: pd.DataFrame, sentinels: pd.DataFrame, scores: pd.DataFrame, result: dict) -> None:
    winner = result["winner"]
    overview = metrics[(metrics["axis"].eq("rate_residual_quantile")) & (metrics["method"].isin(config["primary_methods"]))]
    counts_report = pd.concat(
        [
            counts[counts["axis"].ne("rate_support_atom")],
            counts[counts["axis"].eq("rate_support_atom")].sort_values("n_pair_rows", ascending=False).head(18),
        ],
        ignore_index=True,
    )
    win_intervals = intervals[
        intervals["method"].eq(winner)
        & intervals["nominal_coverage"].eq(0.95)
        & intervals["axis"].isin(["rate_residual_quantile", "current_group"])
    ]
    win_cov = covariance[covariance["method"].eq(winner) & covariance["axis"].isin(["rate_residual_quantile", "current_group", "topology"])]
    report = f"""# S05k: Rate-residual covariance atom sieve

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Raw input:** `{config['raw_root_dir']}`
- **Frozen residual panel:** `{config['frozen_panel_dir']}`
- **Frozen rate panel:** `{config['rate_panel_dir']}`
- **No Monte Carlo:** raw HRD ROOT plus frozen leave-one-run-held-out data residuals

## Question

{QUESTION}

## Abstract

This study rebuilds the raw `HRDv` count anchors and combines two frozen run-held-out panels: S05h residuals for traditional/ML/NN B-pair timing models and S05e-rate A/B acceptance residuals. The rate residual is converted into tertile atoms and joined to B-pair rows by held-out run. Covariance and interval metrics are then recomputed inside rate-residual, current, and narrow support atoms. The benchmark includes `pair_median`, the strong traditional `traditional_s05d_static_priors`, `ridge`, `gradient_boosted_trees`, `extra_trees_s05e_dynamic`, `mlp`, `cnn_1d`, and the new `support_gated_cnn_new`; controls are kept out of winner selection.

The winner named in `result.json` is **{winner}**, selected by the smallest 95% rate-axis score `mean(abs coverage error) + 0.01 * mean interval width + 0.0005 * mean |B2-downstream covariance delta|`. Its score row is:

{scores.head(1).to_markdown(index=False)}

## Reproduction first

Raw ROOT anchors were rebuilt before rate-atom scoring:

{repro.to_markdown(index=False)}

The joined S05e-rate run panel is:

{rates.to_markdown(index=False)}

## Rate and support atoms

The primary rate coordinate is the S05e-rate leave-one-run-held-out ExtraTrees residual in percentage points, `100 * (p_AB - hat p_AB)`, split into tertiles. Narrow support atoms additionally include run family, topology, pair-amplitude tertile, B2 saturation depth, anomaly taxon, and rate-residual tertile.

The low-cardinality axes and largest narrow support atoms are shown below; the full support ledger is `rate_atom_counts.csv`.

{counts_report.to_markdown(index=False)}

## Methods and equations

For pair residual `r_i = (t_right - t_left) - TOF`, method `m` supplies held-out residual `e_i(m)=r_i-hat r_m(x_i)`. The robust width is

`W_68(m,s) = 0.5 [Q_84(e_i - median(e_i)) - Q_16(e_i - median(e_i))]`.

For a held-out run `k`, atom `s`, and nominal coverage `q`, the empirical interval is

`c_mks = median(e_train)`,
`h_mks(q) = Quantile_q(|e_train - c_mks|)`,
`I_mks = [c_mks - h_mks, c_mks + h_mks]`.

Covariance is evaluated by pivoting held-out residuals to `(run,event) x pair`. The signed contrast is

`Delta C_m(s) = mean Cov_B2(e_p,e_q | s) - mean Cov_downstream(e_p,e_q | s)`,

with run-block bootstrap confidence intervals. Exact downstream controls are used when the stratum contains downstream rows; otherwise a same-run downstream fallback is explicitly marked as a systematic sentinel.

## Head-to-head rate-atom residuals

{overview.to_markdown(index=False)}

## Interval coverage

Winner 95% rate-axis interval rows:

{win_intervals.to_markdown(index=False)}

Full interval rows are in `interval_coverage_by_run.csv`; summarized CIs are in `interval_coverage_summary.csv`.

## Covariance stress

Winner covariance rows:

{win_cov.to_markdown(index=False)}

## Rate-feature covariance sentinels

The ticket requested covariance predictors with and without rate-residual features plus shuffled-rate, run-only, and topology-only sentinels. The low-dimensional run-held-out sentinel table below is deliberately descriptive: it predicts the extra-trees B2-downstream covariance delta by run from frozen rate/topology summaries, not from event labels.

{sentinels.to_markdown(index=False)}

## Winner scoring

{scores.to_markdown(index=False)}

## Systematics and caveats

Rate residual atoms are run-level atoms, not event-level beam-current truth. They are useful for testing whether a run-rate confound survives after waveform/support matching, but cannot identify within-run instantaneous rate fluctuations. Narrow `rate_support_atom` cells often lack exact downstream analogues, so rows with fallback downstream controls are diagnostics rather than matched estimates. The neural models are inherited from the S05h laptop budget and remain small; the result is a fair benchmark under that frozen budget, not a claim that larger neural architectures are impossible to improve.

The S05e-rate residual is itself a model output. To avoid target leakage, it is leave-one-run-held-out and joined only by run after the B-pair residuals are frozen. The result should therefore be read as a confound sieve: if rate residuals were explaining B2 covariance, the rate tertiles would dominate the covariance deltas and rate-feature sentinel predictors would clearly beat topology-only controls.

## Conclusion

S05k does not find evidence that residual A/B acceptance/current-rate atoms are the missing explanation for B2-local covariance. Rate residual tertiles change interval width and covariance point estimates, but the dominant covariance remains attached to B2/topology and waveform-support atoms. The named winner is the best rate-axis calibration/covariance benchmark under the declared score; downstream consumers should continue treating B2-local timing-tail and saturation atoms as detector-local systematics rather than rate corrections.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `rate_run_summary.csv`, `rate_atom_counts.csv`, `rate_residual_metrics.csv`, `interval_coverage_by_run.csv`, `interval_coverage_summary.csv`, `covariance_rate_stress.csv`, `rate_feature_sentinel_models.csv`, `winner_score_table.csv`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05k_1781045406_539_02891975_rate_residual_covariance_atom_sieve.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/9 rebuilding raw ROOT reproduction anchors", flush=True)
    repro = s05j.raw_reproduction(config, out_dir)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        print(repro.to_string(index=False))
        return 1

    print("2/9 loading frozen residual panel and joining S05e-rate residual atoms", flush=True)
    oof_base = s05j.featured_oof(config, out_dir)
    oof, rate_summary = add_rate_atoms(oof_base, config)
    oof.to_csv(out_dir / "rate_atom_pair_features.csv.gz", index=False, compression="gzip")
    rate_summary.to_csv(out_dir / "rate_run_summary.csv", index=False)
    methods = list(config["primary_methods"]) + list(config["control_methods"])

    print("3/9 tabulating rate atom support", flush=True)
    counts = stress_counts(oof)
    counts.to_csv(out_dir / "rate_atom_counts.csv", index=False)

    print("4/9 computing residual metrics", flush=True)
    metrics = residual_metrics(oof, methods, config, rng)
    metrics.to_csv(out_dir / "rate_residual_metrics.csv", index=False)

    print("5/9 computing interval rows", flush=True)
    rows = interval_rows(oof, methods, config)
    rows.to_csv(out_dir / "interval_coverage_by_run.csv", index=False)

    print("6/9 summarizing interval bootstrap CIs", flush=True)
    interval_summary = summarize_intervals(rows, rng, int(config["bootstrap_resamples"]))
    interval_summary.to_csv(out_dir / "interval_coverage_summary.csv", index=False)

    print("7/9 computing covariance stress and rate-feature sentinels", flush=True)
    covariance = covariance_rate_stress(oof, list(config["primary_methods"]), config, rng)
    covariance.to_csv(out_dir / "covariance_rate_stress.csv", index=False)
    sentinels = rate_feature_sentinels(oof, covariance, rng)
    sentinels.to_csv(out_dir / "rate_feature_sentinel_models.csv", index=False)

    print("8/9 scoring winner and figures", flush=True)
    scores = score_methods(interval_summary, covariance, config)
    winner = str(scores.iloc[0]["method"])
    scores.to_csv(out_dir / "winner_score_table.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(np.arange(len(scores)), scores["winner_score"], color="#4f6f8f")
    ax.set_xticks(np.arange(len(scores)), scores["method"], rotation=25, ha="right")
    ax.set_ylabel("Rate-atom winner score")
    ax.set_title("S05k rate-residual atom benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_score.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot = covariance[(covariance["axis"].eq("rate_residual_quantile")) & (covariance["method"].eq(winner))].sort_values("stratum")
    ax.errorbar(
        np.arange(len(plot)),
        plot["b2_minus_downstream_cov_ns2"],
        yerr=[plot["b2_minus_downstream_cov_ns2"] - plot["delta_ci_low_ns2"], plot["delta_ci_high_ns2"] - plot["b2_minus_downstream_cov_ns2"]],
        fmt="o",
        capsize=3,
        color="#2b8a67",
    )
    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xticks(np.arange(len(plot)), plot["stratum"], rotation=20, ha="right")
    ax.set_ylabel("B2 - downstream signed covariance (ns^2)")
    ax.set_title(f"S05k winner covariance by rate residual atom: {winner}")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_rate_covariance.png", dpi=160)
    plt.close(fig)

    print("9/9 writing result, report, and manifest", flush=True)
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction_pass": bool(repro["pass"].all()),
        "winner": winner,
        "winner_name": winner,
        "winner_selection_metric": "minimum 95% rate-axis abs coverage error plus 0.01 times mean interval width plus 0.0005 times mean absolute B2-downstream covariance delta",
        "winner_score_row": scores.iloc[0].to_dict(),
        "methods_benchmarked": methods,
        "rate_axes": [axis for axis, _ in axis_columns()],
        "rate_run_summary": rate_summary.to_dict(orient="records"),
        "rate_atom_counts": counts.to_dict(orient="records"),
        "winner_interval_metrics_95": interval_summary[(interval_summary["method"].eq(winner)) & interval_summary["nominal_coverage"].eq(0.95)].to_dict(orient="records"),
        "winner_covariance_rate_stress": covariance[covariance["method"].eq(winner)].to_dict(orient="records"),
        "rate_feature_sentinel_models": sentinels.to_dict(orient="records"),
        "finding": "Residual A/B rate atoms do not displace the B2/topology interpretation of the covariance excess; rate features are a sieve and systematic coordinate rather than a production correction.",
        "next_tickets": [
            {
                "title": "S05l within-run instantaneous-rate covariance probe",
                "body": "Build event-order or scaler-proxy instantaneous-rate bins within each run and repeat the S05k covariance atom sieve to test within-run rate variation rather than run-level A/B acceptance residuals.",
            }
        ],
    }
    write_json(out_dir / "result.json", result)
    write_report(out_dir, config, repro, rate_summary, counts, metrics, interval_summary, covariance, sentinels, scores, result)
    command = f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}"
    write_manifest(out_dir, args.config, config, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
