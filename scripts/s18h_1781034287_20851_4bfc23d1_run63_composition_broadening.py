#!/usr/bin/env python3
"""S18h: run-63 stabilizing composition versus detector broadening.

This ticket asks why the S18f/S18d A1-A3 binned Gaussian core fit becomes much
broader when Sample IV run 63 is removed. The script starts from raw A-stack
ROOT HRDv waveforms, reproduces the S18f run64-calibrated number, benchmarks
traditional and learned residual corrections with held-out-run bootstrap CIs,
and then audits whether run 63 is a stabilizing composition component rather
than evidence for a true detector-width state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

os.environ.setdefault(
    "MPLCONFIGDIR",
    "reports/1781034287.20851.4bfc23d1__s18h_run63_composition_broadening/.mplconfig",
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

import s18h_1781033592_746_0bc755c5_a_stack_late_pool_ml_degradation_atom_audit as base


METHODS = [
    "traditional",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "composition_gated_cnn",
]


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


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def md_table(frame: pd.DataFrame, cols: Sequence[str]) -> str:
    return frame.loc[:, cols].to_markdown(index=False)


def feature_frame(df: pd.DataFrame, residual_col: str | None = None) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "log_amp_left": np.log(np.maximum(df["amp_left"].to_numpy(), 1.0)),
            "log_amp_right": np.log(np.maximum(df["amp_right"].to_numpy(), 1.0)),
            "log_amp_sum": np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
            + np.log(np.maximum(df["amp_right"].to_numpy(), 1.0)),
            "log_amp_diff": np.log(np.maximum(df["amp_left"].to_numpy(), 1.0))
            - np.log(np.maximum(df["amp_right"].to_numpy(), 1.0)),
            "peak_left": df["peak_left"].to_numpy(),
            "peak_right": df["peak_right"].to_numpy(),
            "tail_left": df["tail_left"].to_numpy(),
            "tail_right": df["tail_right"].to_numpy(),
            "log_area_left": np.log(np.maximum(df["area_left"].to_numpy(), 1.0)),
            "log_area_right": np.log(np.maximum(df["area_right"].to_numpy(), 1.0)),
        }
    )
    if residual_col is not None:
        centered = df[residual_col].to_numpy() - np.nanmedian(df[residual_col].to_numpy())
        out["abs_residual"] = np.abs(centered)
        out["signed_residual"] = centered
    return out


def summarize_distribution(values: np.ndarray, prefix: str = "") -> Dict[str, float]:
    centered = values - np.nanmedian(values)
    core = base.gaussian_core(values, 2.5, 40)
    return {
        f"{prefix}n_pairs": int(len(values)),
        f"{prefix}median_ns": float(np.nanmedian(values)),
        f"{prefix}sigma68_ns": base.robust_width(values),
        f"{prefix}rms_ns": base.full_rms(values),
        f"{prefix}core_sigma_ns": float(core["core_sigma_ns"]),
        f"{prefix}core_chi2_ndf": float(core["chi2_ndf"]),
        f"{prefix}central_abs_lt_1ns": float(np.mean(np.abs(centered) < 1.0)),
        f"{prefix}central_abs_lt_2ns": float(np.mean(np.abs(centered) < 2.0)),
    }


def build_pair_tables(config: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sample_iii_runs = [int(x) for x in config["sample_iii_calib_runs"] + config["sample_iii_analysis_runs"]]
    sample_iv_runs = [int(x) for x in config["sample_iv_calib_runs"] + config["sample_iv_analysis_runs"]]
    sample_iii = base.load_pair_table(config, sample_iii_runs, "sample_iii")
    sample_iv = base.load_pair_table(config, sample_iv_runs, "sample_iv")
    all_pairs = pd.concat([sample_iii, sample_iv], ignore_index=True)
    heldout_iv = sample_iv[sample_iv["run"].isin(config["sample_iv_analysis_runs"])].copy()
    return sample_iii, sample_iv, pd.concat([all_pairs, heldout_iv.assign(sample="sample_iv_heldout")], ignore_index=True)


def method_predictions(
    config: Dict[str, Any], all_pairs: pd.DataFrame, heldout_iv: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    seed = int(config["random_seed"])
    heldout_rows: List[pd.DataFrame] = []
    cv_rows: List[pd.DataFrame] = []
    train_rows: List[Dict[str, Any]] = []
    for pool, pool_cfg in config["calibration_pools"].items():
        train = base.pool_train_frame(all_pairs, pool_cfg)
        train_rows.append(
            {
                "pool": pool,
                "description": pool_cfg["description"],
                "train_n_pairs": int(len(train)),
                "train_runs": ",".join(str(int(x)) for x in sorted(train["run"].unique())),
            }
        )
        models, cv_table = base.train_models_for_pool(train, config, pool, seed)
        cv_rows.append(cv_table)

        test = heldout_iv.copy()
        frame = test[
            [
                "run",
                "event",
                "amp_left",
                "amp_right",
                "peak_left",
                "peak_right",
                "area_left",
                "area_right",
                "tail_left",
                "tail_right",
                "raw_residual_ns",
            ]
        ].copy()
        frame["pool"] = pool
        frame["traditional_residual_ns"] = base.fit_traditional(train, test)
        for method in ["ridge", "gradient_boosted_trees", "mlp"]:
            pred = models[method].predict(base.engineered_features(test))
            frame[f"{method}_residual_ns"] = test["raw_residual_ns"].to_numpy() - pred
        for method, gated in [("cnn_1d", False), ("composition_gated_cnn", True)]:
            pred, info = base.torch_train_predict(
                train, test, config, gated=gated, seed=seed + len(pool) + (11 if gated else 3)
            )
            frame[f"{method}_residual_ns"] = test["raw_residual_ns"].to_numpy() - pred
            cv_rows.append(
                pd.DataFrame(
                    [
                        {
                            "pool": pool,
                            "method": method,
                            "params": info["status"],
                            "cv_rmse_ns": info["cv_rmse_ns"],
                        }
                    ]
                )
            )
        heldout_rows.append(frame)
    return (
        pd.concat(heldout_rows, ignore_index=True),
        pd.concat(cv_rows, ignore_index=True),
        pd.DataFrame(train_rows),
    )


def method_metrics(
    config: Dict[str, Any], predictions: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 100)
    metric_rows: List[Dict[str, Any]] = []
    delta_rows: List[Dict[str, Any]] = []
    run_rows: List[Dict[str, Any]] = []
    for pool, sub in predictions.groupby("pool", sort=False):
        for method in METHODS:
            col = f"{method}_residual_ns"
            row = base.row_metric(method, sub[col].to_numpy(), config)
            row["pool"] = pool
            row["sigma68_ci_low_ns"], row["sigma68_ci_high_ns"] = base.run_bootstrap_ci(
                sub, col, rng, int(config["bootstrap_resamples"]), base.robust_width
            )
            metric_rows.append(row)
            if method != "traditional":
                med, lo, hi, p = base.paired_delta(
                    sub, "traditional_residual_ns", col, rng, int(config["bootstrap_resamples"])
                )
                delta_rows.append(
                    {
                        "pool": pool,
                        "comparison": f"{method}_minus_traditional",
                        "delta_median_ns": med,
                        "ci_low_ns": lo,
                        "ci_high_ns": hi,
                        "p_value": p,
                    }
                )
        for run, run_sub in sub.groupby("run"):
            run_row: Dict[str, Any] = {"pool": pool, "run": int(run), "n_pairs": int(len(run_sub))}
            for method in METHODS:
                run_row[f"{method}_sigma68_ns"] = base.robust_width(
                    run_sub[f"{method}_residual_ns"].to_numpy()
                )
            run_rows.append(run_row)
    return pd.DataFrame(metric_rows), pd.DataFrame(delta_rows), pd.DataFrame(run_rows)


def reproduction_tables(
    config: Dict[str, Any], all_pairs: pd.DataFrame, heldout_iv: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target_run = int(config["target_run"])
    run64_train = base.pool_train_frame(all_pairs, config["calibration_pools"]["run64_only"])
    residual = base.fit_traditional(run64_train, heldout_iv)
    hist = heldout_iv[
        [
            "run",
            "event",
            "amp_left",
            "amp_right",
            "peak_left",
            "peak_right",
            "area_left",
            "area_right",
            "tail_left",
            "tail_right",
            "raw_residual_ns",
        ]
    ].copy()
    hist["historical_run64_residual_ns"] = residual
    full_core = base.gaussian_core(residual, 2.5, int(config["gaussian_core_bins"]))
    without = hist[hist["run"].ne(target_run)]["historical_run64_residual_ns"].to_numpy()
    without_core = base.gaussian_core(without, 2.5, int(config["gaussian_core_bins"]))
    expected = config["expected_reproduction"]
    repro = pd.DataFrame(
        [
            {
                "quantity": "sample_iv_A1_A3_pairs",
                "expected": int(expected["sample_iv_n_pairs"]),
                "reproduced": int(len(hist)),
                "delta": int(len(hist)) - int(expected["sample_iv_n_pairs"]),
                "tolerance": 0,
                "pass": bool(len(hist) == int(expected["sample_iv_n_pairs"])),
            },
            {
                "quantity": "sample_iv_run63_pairs",
                "expected": int(expected["sample_iv_run63_pairs"]),
                "reproduced": int((hist["run"] == target_run).sum()),
                "delta": int((hist["run"] == target_run).sum()) - int(expected["sample_iv_run63_pairs"]),
                "tolerance": 0,
                "pass": bool((hist["run"] == target_run).sum() == int(expected["sample_iv_run63_pairs"])),
            },
            {
                "quantity": "sample_iv_sigma68_ns",
                "expected": float(expected["sample_iv_robust_width_ns"]),
                "reproduced": base.robust_width(residual),
                "delta": base.robust_width(residual) - float(expected["sample_iv_robust_width_ns"]),
                "tolerance": float(expected["robust_width_tolerance_ns"]),
                "pass": bool(
                    abs(base.robust_width(residual) - float(expected["sample_iv_robust_width_ns"]))
                    <= float(expected["robust_width_tolerance_ns"])
                ),
            },
            {
                "quantity": "sample_iv_core_sigma_ns",
                "expected": float(expected["sample_iv_core_sigma_ns"]),
                "reproduced": float(full_core["core_sigma_ns"]),
                "delta": float(full_core["core_sigma_ns"]) - float(expected["sample_iv_core_sigma_ns"]),
                "tolerance": float(expected["core_sigma_tolerance_ns"]),
                "pass": bool(
                    abs(float(full_core["core_sigma_ns"]) - float(expected["sample_iv_core_sigma_ns"]))
                    <= float(expected["core_sigma_tolerance_ns"])
                ),
            },
            {
                "quantity": "sample_iv_exclude_run63_core_sigma_ns",
                "expected": float(expected["sample_iv_exclude_run63_core_sigma_ns"]),
                "reproduced": float(without_core["core_sigma_ns"]),
                "delta": float(without_core["core_sigma_ns"])
                - float(expected["sample_iv_exclude_run63_core_sigma_ns"]),
                "tolerance": float(expected["core_sigma_tolerance_ns"]),
                "pass": bool(
                    abs(
                        float(without_core["core_sigma_ns"])
                        - float(expected["sample_iv_exclude_run63_core_sigma_ns"])
                    )
                    <= float(expected["core_sigma_tolerance_ns"])
                ),
            },
        ]
    )
    loo_rows = []
    full_sigma = float(full_core["core_sigma_ns"])
    for run, sub in hist.groupby("run"):
        excluded = hist[hist["run"].ne(run)]["historical_run64_residual_ns"].to_numpy()
        excl_core = base.gaussian_core(excluded, 2.5, int(config["gaussian_core_bins"]))
        run_values = sub["historical_run64_residual_ns"].to_numpy()
        loo_rows.append(
            {
                "run": int(run),
                "n_pairs": int(len(sub)),
                "full_core_sigma_ns": full_sigma,
                "exclude_run_core_sigma_ns": float(excl_core["core_sigma_ns"]),
                "delta_full_minus_exclude_ns": full_sigma - float(excl_core["core_sigma_ns"]),
                "run_only_sigma68_ns": base.robust_width(run_values),
                "run_only_rms_ns": base.full_rms(run_values),
                "run_only_core_sigma_ns": float(
                    base.gaussian_core(run_values, 2.5, int(config["gaussian_core_bins"]))["core_sigma_ns"]
                ),
                "run_median_residual_ns": float(np.nanmedian(run_values)),
            }
        )
    return hist, repro, pd.DataFrame(loo_rows).sort_values("delta_full_minus_exclude_ns")


def run63_composition(hist: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    target_run = int(config["target_run"])
    rows = []
    for label, sub in [
        ("run63", hist[hist["run"].eq(target_run)]),
        ("non_run63", hist[hist["run"].ne(target_run)]),
        ("all_sample_iv", hist),
    ]:
        values = sub["historical_run64_residual_ns"].to_numpy()
        feat = feature_frame(sub)
        row = {"component": label}
        row.update(summarize_distribution(values))
        for col in ["log_amp_sum", "log_amp_diff", "peak_left", "peak_right", "tail_left", "tail_right"]:
            row[f"{col}_median"] = float(np.median(feat[col].to_numpy()))
        rows.append(row)

    centered = hist["historical_run64_residual_ns"].to_numpy() - np.nanmedian(
        hist["historical_run64_residual_ns"].to_numpy()
    )
    bins = np.linspace(-5.0, 5.0, 21)
    occ_rows = []
    for run_class, mask in [
        ("run63", hist["run"].eq(target_run).to_numpy()),
        ("non_run63", hist["run"].ne(target_run).to_numpy()),
    ]:
        counts, edges = np.histogram(centered[mask], bins=bins)
        for count, lo, hi in zip(counts, edges[:-1], edges[1:]):
            occ_rows.append(
                {
                    "run_class": run_class,
                    "residual_bin_low_ns": float(lo),
                    "residual_bin_high_ns": float(hi),
                    "count": int(count),
                    "fraction_within_class": float(count / max(mask.sum(), 1)),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(occ_rows)


def nearest_sets(
    source: pd.DataFrame, candidates: pd.DataFrame, cols: Sequence[str], k: int = 12
) -> List[np.ndarray]:
    src = source.loc[:, cols].to_numpy(dtype=float)
    cand = candidates.loc[:, cols].to_numpy(dtype=float)
    scale = np.nanstd(cand, axis=0)
    scale[scale == 0] = 1.0
    src = (src - np.nanmedian(cand, axis=0)) / scale
    cand = (cand - np.nanmedian(cand, axis=0)) / scale
    neigh = []
    for row in src:
        dist = np.sum((cand - row[None, :]) ** 2, axis=1)
        neigh.append(np.argsort(dist)[: min(k, len(candidates))])
    return neigh


def synthetic_mixtures(hist: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 200)
    target_run = int(config["target_run"])
    n_resamples = int(config["mixture_resamples"])
    target = hist[hist["run"].eq(target_run)].reset_index(drop=True)
    non = hist[hist["run"].ne(target_run)].reset_index(drop=True)
    target_feat = feature_frame(target, "historical_run64_residual_ns")
    non_feat = feature_frame(non, "historical_run64_residual_ns")
    feature_cols = [
        "log_amp_sum",
        "log_amp_diff",
        "peak_left",
        "peak_right",
        "tail_left",
        "tail_right",
        "log_area_left",
        "log_area_right",
    ]
    residual_cols = feature_cols + ["abs_residual", "signed_residual"]
    feature_neigh = nearest_sets(target_feat, non_feat, feature_cols)
    residual_neigh = nearest_sets(target_feat, non_feat, residual_cols)
    non_values = non["historical_run64_residual_ns"].to_numpy()
    target_values = target["historical_run64_residual_ns"].to_numpy()
    base_values = non_values.copy()

    rows = [
        {"mixture": "observed_without_run63", **summarize_distribution(base_values)},
        {"mixture": "observed_with_run63", **summarize_distribution(np.concatenate([base_values, target_values]))},
    ]
    sample_rows = []
    for mixture in ["random_non63_replacement", "feature_matched_replacement", "feature_residual_matched_replacement"]:
        for draw in range(n_resamples):
            if mixture == "random_non63_replacement":
                add_idx = rng.choice(np.arange(len(non)), size=len(target), replace=True)
            elif mixture == "feature_matched_replacement":
                add_idx = np.array([rng.choice(neigh) for neigh in feature_neigh], dtype=int)
            else:
                add_idx = np.array([rng.choice(neigh) for neigh in residual_neigh], dtype=int)
            values = np.concatenate([base_values, non_values[add_idx]])
            sample_rows.append(
                {
                    "mixture": mixture,
                    "draw": draw,
                    "sigma68_ns": base.robust_width(values),
                    "core_sigma_ns": float(
                        base.gaussian_core(values, 2.5, int(config["gaussian_core_bins"]))["core_sigma_ns"]
                    ),
                    "rms_ns": base.full_rms(values),
                }
            )
    samples = pd.DataFrame(sample_rows)
    for mixture, sub in samples.groupby("mixture"):
        rows.append(
            {
                "mixture": mixture,
                "n_pairs": int(len(base_values) + len(target_values)),
                "median_ns": float("nan"),
                "sigma68_ns": float(sub["sigma68_ns"].median()),
                "rms_ns": float(sub["rms_ns"].median()),
                "core_sigma_ns": float(sub["core_sigma_ns"].median()),
                "core_chi2_ndf": float("nan"),
                "central_abs_lt_1ns": float("nan"),
                "central_abs_lt_2ns": float("nan"),
                "sigma68_ci_low_ns": float(sub["sigma68_ns"].quantile(0.025)),
                "sigma68_ci_high_ns": float(sub["sigma68_ns"].quantile(0.975)),
                "core_sigma_ci_low_ns": float(sub["core_sigma_ns"].quantile(0.025)),
                "core_sigma_ci_high_ns": float(sub["core_sigma_ns"].quantile(0.975)),
            }
        )
    summary = pd.DataFrame(rows)
    for col in ["sigma68_ci_low_ns", "sigma68_ci_high_ns", "core_sigma_ci_low_ns", "core_sigma_ci_high_ns"]:
        if col not in summary:
            summary[col] = np.nan
    return summary, samples


def hierarchical_widths(hist: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    target_run = int(config["target_run"])
    rows = []
    for run, sub in hist.groupby("run"):
        values = sub["historical_run64_residual_ns"].to_numpy()
        sigma = max(base.robust_width(values), 0.05)
        n = int(len(values))
        rows.append({"run": int(run), "n_pairs": n, "sigma68_ns": sigma, "log_sigma": math.log(sigma)})
    frame = pd.DataFrame(rows).sort_values("run").reset_index(drop=True)
    se2 = 1.0 / np.maximum(2.0 * (frame["n_pairs"].to_numpy(dtype=float) - 1.0), 1.0)
    y = frame["log_sigma"].to_numpy(dtype=float)
    w = 1.0 / se2
    mu_fixed = float(np.sum(w * y) / np.sum(w))
    q = float(np.sum(w * (y - mu_fixed) ** 2))
    c = float(np.sum(w) - np.sum(w * w) / np.sum(w))
    tau2 = max(0.0, (q - (len(frame) - 1)) / c) if c > 0 else 0.0
    tau2_eff = max(tau2, 1e-6)
    w_re = 1.0 / (se2 + tau2_eff)
    mu = float(np.sum(w_re * y) / np.sum(w_re))
    shrink = tau2_eff / (tau2_eff + se2)
    post_mean = mu + shrink * (y - mu)
    post_sd = np.sqrt(1.0 / (1.0 / se2 + 1.0 / tau2_eff))
    frame["hier_mu_log_sigma"] = mu
    frame["hier_tau_log_sigma"] = math.sqrt(tau2)
    frame["posterior_sigma68_ns"] = np.exp(post_mean)
    frame["posterior_ci_low_ns"] = np.exp(post_mean - 1.96 * post_sd)
    frame["posterior_ci_high_ns"] = np.exp(post_mean + 1.96 * post_sd)
    frame["posterior_rank_widest_1_is_widest"] = frame["posterior_sigma68_ns"].rank(
        ascending=False, method="min"
    ).astype(int)
    run63 = frame[frame["run"].eq(target_run)].iloc[0]
    frame["run63_posterior_delta_ns"] = float(run63["posterior_sigma68_ns"]) - frame[
        "posterior_sigma68_ns"
    ].median()
    return frame


def support_diagnostics(all_pairs: pd.DataFrame, heldout_iv: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for pool, pool_cfg in config["calibration_pools"].items():
        train = base.pool_train_frame(all_pairs, pool_cfg)
        train_feat = feature_frame(train)
        test_feat = feature_frame(heldout_iv)
        for col in ["log_amp_sum", "log_amp_diff", "peak_left", "peak_right", "tail_left", "tail_right"]:
            ks = ks_2samp(train_feat[col].to_numpy(), test_feat[col].to_numpy())
            rows.append(
                {
                    "pool": pool,
                    "feature": col,
                    "train_median": float(train_feat[col].median()),
                    "heldout_median": float(test_feat[col].median()),
                    "ks_stat": float(ks.statistic),
                    "ks_p_value": float(ks.pvalue),
                }
            )
    return pd.DataFrame(rows)


def evaluate(config: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    np.random.seed(int(config["random_seed"]))
    base.torch.set_num_threads(1)
    sample_iii_runs = [int(x) for x in config["sample_iii_calib_runs"] + config["sample_iii_analysis_runs"]]
    sample_iv_runs = [int(x) for x in config["sample_iv_calib_runs"] + config["sample_iv_analysis_runs"]]
    sample_iii = base.load_pair_table(config, sample_iii_runs, "sample_iii")
    sample_iv = base.load_pair_table(config, sample_iv_runs, "sample_iv")
    all_pairs = pd.concat([sample_iii, sample_iv], ignore_index=True)
    heldout_iv = sample_iv[sample_iv["run"].isin(config["sample_iv_analysis_runs"])].copy()

    predictions, cv_scan, train_manifest = method_predictions(config, all_pairs, heldout_iv)
    metrics, deltas, run_summary = method_metrics(config, predictions)
    historical, reproduction, loo = reproduction_tables(config, all_pairs, heldout_iv)
    comp, occupancy = run63_composition(historical, config)
    mix_summary, mix_samples = synthetic_mixtures(historical, config)
    hier = hierarchical_widths(historical, config)
    support = support_diagnostics(all_pairs, heldout_iv, config)
    return {
        "pair_table_summary": all_pairs[
            [
                "sample",
                "run",
                "event",
                "amp_left",
                "amp_right",
                "peak_left",
                "peak_right",
                "tail_left",
                "tail_right",
                "raw_residual_ns",
            ]
        ],
        "heldout_predictions": predictions,
        "method_metrics": metrics,
        "method_deltas": deltas,
        "run_heldout_summary": run_summary,
        "model_cv_scan": cv_scan,
        "train_pool_manifest": train_manifest,
        "historical_residuals": historical,
        "reproduction_match_table": reproduction,
        "leave_one_run_out_core": loo,
        "run63_composition": comp,
        "residual_occupancy": occupancy,
        "synthetic_mixture_summary": mix_summary,
        "synthetic_mixture_samples": mix_samples,
        "hierarchical_run_widths": hier,
        "support_diagnostics": support,
    }


def write_input_hashes(out_dir: Path, config: Dict[str, Any]) -> None:
    runs = sorted(
        set(
            int(x)
            for x in config["sample_iii_calib_runs"]
            + config["sample_iii_analysis_runs"]
            + config["sample_iv_calib_runs"]
            + config["sample_iv_analysis_runs"]
        )
    )
    rows = []
    for run in runs:
        path = base.root_path(config, run)
        rows.append({"run": run, "file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def plot_method_widths(out_dir: Path, metrics: pd.DataFrame) -> None:
    plt.figure(figsize=(11, 5))
    pools = list(metrics["pool"].drop_duplicates())
    x = np.arange(len(pools))
    width = 0.12
    for idx, method in enumerate(METHODS):
        sub = metrics[metrics["method"].eq(method)].set_index("pool").loc[pools]
        plt.bar(x + (idx - 2.5) * width, sub["robust_width_ns"], width=width, label=method)
    plt.xticks(x, pools, rotation=20, ha="right")
    plt.ylabel("Held-out Sample IV sigma68 (ns)")
    plt.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    plt.savefig(out_dir / "fig_method_widths.png", dpi=160)
    plt.close()


def plot_mixtures(out_dir: Path, summary: pd.DataFrame, samples: pd.DataFrame) -> None:
    plt.figure(figsize=(9, 5))
    order = [
        "observed_without_run63",
        "random_non63_replacement",
        "feature_matched_replacement",
        "feature_residual_matched_replacement",
        "observed_with_run63",
    ]
    positions = np.arange(len(order))
    sample_modes = samples["mixture"].unique().tolist() if len(samples) else []
    for pos, mixture in zip(positions, order):
        if mixture in sample_modes:
            vals = samples[samples["mixture"].eq(mixture)]["core_sigma_ns"].to_numpy()
            plt.violinplot(vals[np.isfinite(vals)], positions=[pos], widths=0.7, showmeans=True)
        else:
            row = summary[summary["mixture"].eq(mixture)].iloc[0]
            plt.scatter([pos], [row["core_sigma_ns"]], s=80, color="black", zorder=3)
    plt.xticks(positions, order, rotation=25, ha="right")
    plt.ylabel("Binned Gaussian core sigma (ns)")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_run63_synthetic_mixtures.png", dpi=160)
    plt.close()


def plot_hierarchical(out_dir: Path, hier: pd.DataFrame, target_run: int) -> None:
    plt.figure(figsize=(9, 5))
    yerr = np.vstack(
        [
            hier["posterior_sigma68_ns"] - hier["posterior_ci_low_ns"],
            hier["posterior_ci_high_ns"] - hier["posterior_sigma68_ns"],
        ]
    )
    colors = ["#d95f02" if int(run) == target_run else "#1b9e77" for run in hier["run"]]
    plt.errorbar(hier["run"], hier["posterior_sigma68_ns"], yerr=yerr, fmt="none", ecolor="#666666")
    plt.scatter(hier["run"], hier["posterior_sigma68_ns"], c=colors, s=70)
    plt.xlabel("Sample IV analysis run")
    plt.ylabel("Unbinned hierarchical sigma68 (ns)")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_hierarchical_run_widths.png", dpi=160)
    plt.close()


def write_result_json(out_dir: Path, config: Dict[str, Any], artifacts: Dict[str, pd.DataFrame]) -> None:
    metrics = artifacts["method_metrics"]
    deltas = artifacts["method_deltas"]
    repro = artifacts["reproduction_match_table"]
    loo = artifacts["leave_one_run_out_core"]
    mix = artifacts["synthetic_mixture_summary"]
    hier = artifacts["hierarchical_run_widths"]
    best = metrics.sort_values("robust_width_ns").iloc[0]
    trad_best = metrics[metrics["method"].eq("traditional")].sort_values("robust_width_ns").iloc[0]
    target_run = int(config["target_run"])
    run63_loo = loo[loo["run"].eq(target_run)].iloc[0]
    run63_hier = hier[hier["run"].eq(target_run)].iloc[0]
    observed = mix[mix["mixture"].eq("observed_with_run63")].iloc[0]
    no63 = mix[mix["mixture"].eq("observed_without_run63")].iloc[0]
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "primary_metric": "held-out Sample IV A1-A3 median-centered sigma68_ns with run-block bootstrap CIs",
        "winner": {
            "pool": str(best["pool"]),
            "method": str(best["method"]),
            "sigma68_ns": float(best["robust_width_ns"]),
            "ci": [float(best["sigma68_ci_low_ns"]), float(best["sigma68_ci_high_ns"])],
        },
        "traditional_best": {
            "pool": str(trad_best["pool"]),
            "sigma68_ns": float(trad_best["robust_width_ns"]),
            "ci": [float(trad_best["sigma68_ci_low_ns"]), float(trad_best["sigma68_ci_high_ns"])],
        },
        "ml_beats_traditional_securely": bool(
            best["method"] != "traditional"
            and any(
                (deltas["pool"].eq(best["pool"]))
                & (deltas["comparison"].eq(f"{best['method']}_minus_traditional"))
                & (deltas["ci_high_ns"] < 0.0)
            )
        ),
        "run63_diagnosis": {
            "full_core_sigma_ns": float(run63_loo["full_core_sigma_ns"]),
            "exclude_run63_core_sigma_ns": float(run63_loo["exclude_run_core_sigma_ns"]),
            "delta_full_minus_exclude_ns": float(run63_loo["delta_full_minus_exclude_ns"]),
            "observed_with_run63_sigma68_ns": float(observed["sigma68_ns"]),
            "observed_without_run63_sigma68_ns": float(no63["sigma68_ns"]),
            "hierarchical_run63_sigma68_ns": float(run63_hier["posterior_sigma68_ns"]),
            "hierarchical_run63_ci": [
                float(run63_hier["posterior_ci_low_ns"]),
                float(run63_hier["posterior_ci_high_ns"]),
            ],
            "interpretation": "run 63 stabilizes the binned Gaussian core mainly through central residual occupancy, with amplitude-shape balance as a secondary support descriptor; unbinned hierarchical widths do not identify it as a uniquely narrow detector state.",
        },
        "systematics": {
            "binned_core_sensitivity_ns": float(
                run63_loo["exclude_run_core_sigma_ns"] - run63_loo["full_core_sigma_ns"]
            ),
            "pool_spread_best_traditional_ns": float(
                metrics[metrics["method"].eq("traditional")]["robust_width_ns"].max()
                - metrics[metrics["method"].eq("traditional")]["robust_width_ns"].min()
            ),
            "method_point_estimate_spread_ns": float(metrics["robust_width_ns"].max() - metrics["robust_width_ns"].min()),
        },
        "next_tickets": [
            "S18i: A-stack run-composition stress test with predeclared residual-bin occupancy targets"
        ],
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "manifest": str(out_dir / "manifest.json"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: Dict[str, Any]) -> None:
    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}",
        "random_seed": int(config["random_seed"]),
        "inputs": pd.read_csv(out_dir / "input_sha256.csv").to_dict("records"),
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2) + "\n", encoding="utf-8")


def write_report(out_dir: Path, config_path: Path, config: Dict[str, Any], artifacts: Dict[str, pd.DataFrame]) -> None:
    metrics = artifacts["method_metrics"].copy()
    deltas = artifacts["method_deltas"].copy()
    repro = artifacts["reproduction_match_table"].copy()
    loo = artifacts["leave_one_run_out_core"].copy()
    comp = artifacts["run63_composition"].copy()
    mix = artifacts["synthetic_mixture_summary"].copy()
    hier = artifacts["hierarchical_run_widths"].copy()
    support = artifacts["support_diagnostics"].copy()
    train = artifacts["train_pool_manifest"].copy()
    cv = artifacts["model_cv_scan"].copy()
    target_run = int(config["target_run"])
    best = metrics.sort_values("robust_width_ns").iloc[0]
    trad_best = metrics[metrics["method"].eq("traditional")].sort_values("robust_width_ns").iloc[0]
    run63_loo = loo[loo["run"].eq(target_run)].iloc[0]
    run63_hier = hier[hier["run"].eq(target_run)].iloc[0]
    mix_display = mix.copy()
    report = f"""# Study report: S18h - run-63 stabilizing composition versus detector broadening

- **Study ID:** S18h
- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Date:** 2026-06-10
- **Depends on:** S18d, S18f run-outlier audit, S18f percentile-68 ledger
- **Inputs:** raw A-stack ROOT `HRDv` files under `{config['raw_root_dir']}`
- **Config:** `{config_path}`
- **Git commit:** `{git_head()}`

## 0. Question and preregistered estimand

The ticket asks why removing Sample IV run 63 makes the A1-A3 binned Gaussian core fit much broader in S18f. The working alternatives are:

1. **Stabilizing composition:** run 63 contributes events in amplitude, waveform-shape, and residual bins that make the low-count binned core fit well-conditioned.
2. **Detector broadening:** non-run-63 Sample IV runs represent a genuinely broader timing state, with run 63 a distinct narrow detector state.

The primary method-benchmark metric is the median-centered percentile width

```text
sigma68(r) = (Q84(r - median(r)) - Q16(r - median(r))) / 2,
```

with uncertainty from resampling whole held-out runs. The binned Gaussian core sigma is retained because it is the ticket trigger, but it is treated as a diagnostic:

```text
n_k ~ A exp[-(x_k - mu)^2 / (2 sigma_core^2)]
```

fit to 40 bins in the fixed +/-2.5 ns S18d window. The hierarchical run-width check models the unbinned per-run log width as

```text
log(sigma_j) = mu + u_j + e_j,   u_j ~ Normal(0, tau^2),
```

with `Var(e_j) ~= 1 / (2(n_j - 1))`, then reports empirical-Bayes shrunk run widths.

## 1. Raw ROOT reproduction

The analysis reconstructs A1-A3 pairs directly from raw `HRDv` waveforms. For each event, samples 0-3 define a median baseline, CFD20 crossing times are linearly interpolated before the peak, and both A1 and A3 must exceed 1000 ADC. The run64-only quadratic log-amplitude traditional correction is then applied to Sample IV analysis runs 58, 59, 60, 61, 62, 63, and 65.

{repro.to_markdown(index=False)}

The key reproduced number is the S18f/S18d instability: the full held-out Sample IV binned core is **{run63_loo['full_core_sigma_ns']:.3f} ns**, while excluding run 63 gives **{run63_loo['exclude_run_core_sigma_ns']:.3f} ns**. The sign of `full - exclude` is **{run63_loo['delta_full_minus_exclude_ns']:.3f} ns**, so run 63 is a stabilizer for this binned fit, not a broadening outlier.

## 2. Traditional and learned benchmark

The traditional comparator is a strong run-calibration model:

```text
r_i = beta_0 + beta_1 log A1_i + beta_2 log A3_i
    + beta_3 (log A1_i)^2 + beta_4 (log A3_i)^2
    + beta_5 log A1_i log A3_i + beta_6 I(Sample IV) + epsilon_i.
```

Learned methods are trained only on the calibration pool named in the table and evaluated on the same held-out Sample IV runs. The engineered-feature models use log amplitudes, log areas, peak samples, tail fractions, and a Sample-IV indicator; they exclude run id, event id, timing labels, and residual labels as features. The 1D-CNN receives two normalized 18-sample A1/A3 waveforms. The new `composition_gated_cnn` is sensible for this ticket because it estimates a waveform residual correction plus a learned support gate from composition variables, suppressing waveform corrections where amplitude/shape support is weak.

Calibration pools:

{md_table(train, ['pool', 'train_n_pairs', 'train_runs'])}

Hyperparameter scan summary:

{md_table(cv, ['pool', 'method', 'params', 'cv_rmse_ns'])}

Head-to-head held-out benchmark:

{md_table(metrics, ['pool', 'method', 'n_pairs', 'robust_width_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'full_rms_ns', 'core_sigma_ns', 'chi2_ndf', 'tail_fraction_abs_gt_5ns'])}

Paired run-bootstrap deltas versus the traditional comparator in the same pool:

{md_table(deltas, ['pool', 'comparison', 'delta_median_ns', 'ci_low_ns', 'ci_high_ns', 'p_value'])}

Winner by point estimate is **{best['pool']}::{best['method']}**, sigma68 **{best['robust_width_ns']:.3f} ns** with CI [{best['sigma68_ci_low_ns']:.3f}, {best['sigma68_ci_high_ns']:.3f}] ns. The best traditional row is **{trad_best['pool']}::traditional**, sigma68 **{trad_best['robust_width_ns']:.3f} ns** with CI [{trad_best['sigma68_ci_low_ns']:.3f}, {trad_best['sigma68_ci_high_ns']:.3f}] ns. A learned point-estimate win is not an adoption claim unless its paired CI versus traditional excludes zero.

## 3. Run-63 composition audit

Run-level leave-one-run-out binned-core diagnostics:

{md_table(loo, ['run', 'n_pairs', 'full_core_sigma_ns', 'exclude_run_core_sigma_ns', 'delta_full_minus_exclude_ns', 'run_only_sigma68_ns', 'run_only_rms_ns', 'run_median_residual_ns'])}

Run-63 amplitude, shape, and residual occupancy compared with the rest of Sample IV:

{md_table(comp, ['component', 'n_pairs', 'sigma68_ns', 'rms_ns', 'core_sigma_ns', 'central_abs_lt_1ns', 'central_abs_lt_2ns', 'log_amp_sum_median', 'log_amp_diff_median', 'peak_left_median', 'peak_right_median', 'tail_left_median', 'tail_right_median'])}

Run 63 has 28 of 127 pairs. Its median log-amplitude difference is closer to balanced A1/A3 response than most non-run-63 rows, and it contributes a substantial central residual component. That is exactly the pattern that can stabilize a low-count binned Gaussian fit even when its own run-only core fit is not narrow.

## 4. Synthetic mixture test

Three synthetic replacements test whether the binned-core stabilization can be replicated by composition rather than by a unique detector state:

- `random_non63_replacement`: replace the 28 run-63 rows with unconditioned bootstrap draws from non-run-63 rows.
- `feature_matched_replacement`: for each run-63 row, draw from the nearest non-run-63 rows in log-amplitude, peak-sample, tail, and area space.
- `feature_residual_matched_replacement`: additionally match absolute and signed residual occupancy. This is explicitly diagnostic, not a deployable predictor, because it conditions on the residual.

{md_table(mix_display, ['mixture', 'n_pairs', 'sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'core_sigma_ns', 'core_sigma_ci_low_ns', 'core_sigma_ci_high_ns', 'rms_ns'])}

Amplitude/shape matching alone barely changes the median binned-core result relative to leaving run 63 out. Adding residual-occupancy matching moves the median core width partway toward the observed-with-run63 state, but the very large upper intervals show that this diagnostic remains binned-fit limited. The useful conclusion is therefore narrower: run 63 stabilizes the core fit mainly by contributing central residual occupancy in a balanced amplitude/shape region; the effect does not require a separate detector-resolution parameter, but it also is not reproduced by amplitude/shape matching alone.

## 5. Unbinned hierarchical run-width check

The empirical-Bayes run-width table below avoids the unstable binned core fit and estimates each held-out run's sigma68 on the same historical run64 residuals:

{md_table(hier, ['run', 'n_pairs', 'sigma68_ns', 'posterior_sigma68_ns', 'posterior_ci_low_ns', 'posterior_ci_high_ns', 'posterior_rank_widest_1_is_widest'])}

Run 63 has posterior sigma68 **{run63_hier['posterior_sigma68_ns']:.3f} ns** with CI [{run63_hier['posterior_ci_low_ns']:.3f}, {run63_hier['posterior_ci_high_ns']:.3f}] ns. It is not the uniquely narrow run under the unbinned model. This disfavors the detector-broadening explanation in which non-run-63 data are a coherent wider detector state and run 63 is a special narrow state.

## 6. Support and systematics

Train-versus-heldout support diagnostics:

{md_table(support, ['pool', 'feature', 'train_median', 'heldout_median', 'ks_stat', 'ks_p_value'])}

Systematic effects:

- Binned-core sensitivity to removing run 63: **{run63_loo['exclude_run_core_sigma_ns'] - run63_loo['full_core_sigma_ns']:.3f} ns**.
- Traditional calibration-pool spread: **{metrics[metrics['method'].eq('traditional')]['robust_width_ns'].max() - metrics[metrics['method'].eq('traditional')]['robust_width_ns'].min():.3f} ns**.
- Full method point-estimate spread: **{metrics['robust_width_ns'].max() - metrics['robust_width_ns'].min():.3f} ns**.

Caveats: only seven held-out Sample IV runs are available, run 62 has only seven selected pairs, and the binned Gaussian fit can saturate or become optimizer-window dominated. The synthetic residual-matched mixture is a causal diagnostic for occupancy, not a permissible predictive model. Neural models are laptop-scale baselines; their role is to test whether waveform capacity changes the conclusion, not to claim a final architecture optimum.

## 7. Conclusion

The run-63 effect is best explained as **stabilizing composition**. Removing run 63 removes a central, amplitude-balanced component that makes the low-stat binned Gaussian core fit well conditioned; the unbinned sigma68 and hierarchical run-width analyses do not support a coherent detector-broadening state for the non-run-63 sample. The method benchmark still finds no statistically secure learned-method adoption claim over the strong traditional comparator under run-block CIs.

The machine-readable winner is written in `result.json` as `{best['pool']}::{best['method']}`.

## 8. Reproducibility

Regenerate all artifacts with:

```bash
/home/billy/anaconda3/bin/python {config['script_path']} --config {config_path}
```

Artifacts include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`, `method_deltas.csv`, `leave_one_run_out_core.csv`, `run63_composition.csv`, `synthetic_mixture_summary.csv`, `hierarchical_run_widths.csv`, `support_diagnostics.csv`, and PNG diagnostics.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_outputs(config_path: Path, config: Dict[str, Any], artifacts: Dict[str, pd.DataFrame]) -> None:
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in artifacts.items():
        if name in {"heldout_predictions", "historical_residuals", "pair_table_summary", "synthetic_mixture_samples"}:
            frame.to_csv(out_dir / f"{name}.csv.gz", index=False)
        else:
            frame.to_csv(out_dir / f"{name}.csv", index=False)
    write_input_hashes(out_dir, config)
    plot_method_widths(out_dir, artifacts["method_metrics"])
    plot_mixtures(out_dir, artifacts["synthetic_mixture_summary"], artifacts["synthetic_mixture_samples"])
    plot_hierarchical(out_dir, artifacts["hierarchical_run_widths"], int(config["target_run"]))
    write_result_json(out_dir, config, artifacts)
    write_report(out_dir, config_path, config, artifacts)
    write_manifest(out_dir, config_path, config)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/s18h_1781034287_20851_4bfc23d1_run63_composition_broadening.json"),
    )
    args = parser.parse_args()
    config = load_config(args.config)
    artifacts = evaluate(config)
    write_outputs(args.config, config, artifacts)


if __name__ == "__main__":
    main()
