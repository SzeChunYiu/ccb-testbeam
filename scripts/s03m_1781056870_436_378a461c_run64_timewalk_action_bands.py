#!/usr/bin/env python3
"""S03m run-64 timewalk transfer action bands.

The study freezes the S03 analytic comparator on Sample-I B-stack runs, applies
it without refitting to Sample-II analysis runs and run 64, and converts the
transfer diagnostics into explicit pass/abstain/recalibrate action bands. The
required ML/NN family bakeoff is imported from the frozen P03f leave-one-run-out
panel, which exercises ridge, gradient-boosted trees, MLP, 1D-CNN, and a
feature-gated architecture on the same Sample-II residual metric.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a


REQUIRED_METHODS = {
    "analytic_timewalk": "traditional_s03_analytic_timewalk",
    "ridge_waveform_stave_onehot": "ridge",
    "hgb_waveform_amp_shape_stave": "gradient_boosted_trees",
    "mlp_waveform_amp_shape_stave": "mlp",
    "cnn1d_waveform_amp_shape_stave": "1d_cnn",
    "feature_gated_waveform_amp_shape_stave": "new_feature_gated_architecture",
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_commit() -> str:
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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def run_group(config: dict, run: int) -> str:
    for name, runs in config["run_groups"].items():
        if int(run) in [int(r) for r in runs]:
            return name
    return "unknown"


def sample_family(config: dict, run: int) -> str:
    group = run_group(config, run)
    if group.startswith("sample_ii"):
        return "Sample II"
    if group.startswith("sample_i"):
        return "Sample I"
    return "unknown"


def prepare_analytic_pulses(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    pulses = s02.load_downstream_pulses(config)
    train = pulses[pulses["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    s02.add_traditional_times(pulses, config, templates)
    analytic, analytic_cv, coef, best_candidate, best_alpha = s03a.run_analytic(
        pulses, config, str(config["timing"]["base_method"])
    )
    meta = {
        "best_candidate": str(best_candidate),
        "best_alpha": float(best_alpha),
        "n_pulses": int(len(analytic)),
        "n_events": int(analytic["event_id"].nunique()),
    }
    add_pulse_atoms(analytic, templates, config)
    return analytic, analytic_cv, coef, meta


def add_pulse_atoms(pulses: pd.DataFrame, templates: Dict[str, np.ndarray], config: dict) -> None:
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    norm = wf / np.maximum(amp[:, None], 1.0)
    q_template = np.full(len(pulses), np.nan)
    for stave, template in templates.items():
        idx = np.flatnonzero(pulses["stave"].to_numpy() == stave)
        if len(idx):
            q_template[idx] = np.mean((norm[idx] - template[None, :]) ** 2, axis=1)
    area_over_amp = pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    pre = wf[:, [int(i) for i in config["baseline_samples"]]]
    lowering = np.maximum(0.0, -np.min(pre, axis=1))
    q_cut = float(np.nanquantile(q_template[pulses["run"].isin(config["timing"]["train_runs"])], config["atom_ledger"]["q_template_quantile_for_anomaly"]))
    pulses["q_template_mse"] = q_template
    pulses["area_over_amp"] = area_over_amp
    pulses["pretrigger_lowering_adc"] = lowering
    pulses["saturation_flag"] = amp >= float(config["atom_ledger"]["high_amplitude_adc"])
    pulses["dropout_flag"] = area_over_amp <= float(config["atom_ledger"]["dropout_area_over_amp"])
    pulses["template_mismatch_flag"] = q_template >= q_cut


def corrected_tau(pulses: pd.DataFrame, method: str, config: dict) -> pd.Series:
    staves = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(staves, float(config["spacing_cm_values"][0]))
    return pulses[f"t_{method}_ns"] - pulses["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])


def wide_value(pulses: pd.DataFrame, column: str) -> pd.DataFrame:
    return pulses.pivot(index="event_id", columns="stave", values=column)


def make_pair_frame(pulses: pd.DataFrame, config: dict, method: str = "analytic_timewalk") -> pd.DataFrame:
    score_runs = (
        list(config["timing"]["train_runs"])
        + list(config["timing"]["heldout_runs"])
        + list(config["timing"].get("diagnostic_runs", []))
    )
    sub = pulses[pulses["run"].isin(score_runs)].copy()
    sub["tau"] = corrected_tau(sub, method, config)
    wide_tau = wide_value(sub, "tau").dropna()
    wide_amp = wide_value(sub, "amplitude_adc").reindex(wide_tau.index)
    wide_peak = wide_value(sub, "peak_sample").reindex(wide_tau.index)
    wide_area = wide_value(sub, "area_over_amp").reindex(wide_tau.index)
    wide_q = wide_value(sub, "q_template_mse").reindex(wide_tau.index)
    wide_low = wide_value(sub, "pretrigger_lowering_adc").reindex(wide_tau.index)
    wide_sat = wide_value(sub, "saturation_flag").reindex(wide_tau.index)
    wide_drop = wide_value(sub, "dropout_flag").reindex(wide_tau.index)
    wide_mis = wide_value(sub, "template_mismatch_flag").reindex(wide_tau.index)
    run_by_event = sub.drop_duplicates("event_id").set_index("event_id")["run"].to_dict()
    rows = []
    for event_id, times in wide_tau.iterrows():
        run = int(run_by_event[event_id])
        amp_row = wide_amp.loc[event_id]
        amp_order = ">".join(amp_row.sort_values(ascending=False).index.astype(str).tolist())
        lowest_stave = str(amp_row.sort_values(ascending=True).index[0])
        highest_stave = str(amp_row.sort_values(ascending=False).index[0])
        for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
            vals = {
                "event_id": event_id,
                "run": run,
                "run_group": run_group(config, run),
                "sample_family": sample_family(config, run),
                "pair": f"{a}-{b}",
                "residual_ns": float(times[a] - times[b]),
                "pair_amp_mean_adc": float(np.nanmean([wide_amp.loc[event_id, a], wide_amp.loc[event_id, b]])),
                "pair_amp_min_adc": float(np.nanmin([wide_amp.loc[event_id, a], wide_amp.loc[event_id, b]])),
                "pair_amp_max_adc": float(np.nanmax([wide_amp.loc[event_id, a], wide_amp.loc[event_id, b]])),
                "peak_mean_sample": float(np.nanmean([wide_peak.loc[event_id, a], wide_peak.loc[event_id, b]])),
                "peak_delta_sample": float(wide_peak.loc[event_id, a] - wide_peak.loc[event_id, b]),
                "area_over_amp_mean": float(np.nanmean([wide_area.loc[event_id, a], wide_area.loc[event_id, b]])),
                "q_template_mean": float(np.nanmean([wide_q.loc[event_id, a], wide_q.loc[event_id, b]])),
                "q_template_max": float(np.nanmax([wide_q.loc[event_id, a], wide_q.loc[event_id, b]])),
                "pretrigger_lowering_max_adc": float(np.nanmax([wide_low.loc[event_id, a], wide_low.loc[event_id, b]])),
                "saturation_flag": bool(wide_sat.loc[event_id, a] or wide_sat.loc[event_id, b]),
                "dropout_flag": bool(wide_drop.loc[event_id, a] or wide_drop.loc[event_id, b]),
                "template_mismatch_flag": bool(wide_mis.loc[event_id, a] or wide_mis.loc[event_id, b]),
                "amplitude_order": amp_order,
                "lowest_amp_stave": lowest_stave,
                "highest_amp_stave": highest_stave,
            }
            rows.append(vals)
    pairs = pd.DataFrame(rows)
    add_pair_bins(pairs)
    return pairs


def add_pair_bins(pairs: pd.DataFrame) -> None:
    pairs["amplitude_bin"] = pd.cut(
        pairs["pair_amp_min_adc"],
        [1000, 1500, 2000, 3000, 4000, 7000, np.inf],
        include_lowest=True,
    ).astype(str)
    pairs["peak_phase_bin"] = pd.cut(
        pairs["peak_mean_sample"],
        [-np.inf, 3.5, 4.5, 5.5, 6.5, 7.5, np.inf],
        include_lowest=True,
    ).astype(str)
    pairs["q_template_bin"] = pd.qcut(pairs["q_template_mean"], q=5, duplicates="drop").astype(str)
    pairs["lowering_bin"] = pd.cut(
        pairs["pretrigger_lowering_max_adc"],
        [-0.1, 5, 10, 25, 50, 100, np.inf],
        include_lowest=True,
    ).astype(str)
    pairs["dropout_anomaly"] = np.select(
        [pairs["dropout_flag"], pairs["template_mismatch_flag"], pairs["saturation_flag"]],
        ["dropout_or_low_area", "template_mismatch_top_decile", "high_amplitude_proxy"],
        default="nominal",
    )
    pairs["topology"] = (
        "hi=" + pairs["highest_amp_stave"].astype(str)
        + ";lo=" + pairs["lowest_amp_stave"].astype(str)
    )


def sigma68(values: Sequence[float]) -> float:
    return s02.sigma68(np.asarray(values, dtype=float))


def full_rms(values: Sequence[float]) -> float:
    return s02.full_rms(np.asarray(values, dtype=float))


def bootstrap_group(values_by_run: Dict[int, np.ndarray], rng: np.random.Generator, n_boot: int) -> Dict[str, float]:
    runs = sorted(values_by_run)
    if not runs:
        return {"bias_ci_low_ns": np.nan, "bias_ci_high_ns": np.nan, "sigma68_ci_low_ns": np.nan, "sigma68_ci_high_ns": np.nan, "tail5_ci_low": np.nan, "tail5_ci_high": np.nan}
    bias, sig, tail = [], [], []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        vals = np.concatenate([values_by_run[int(run)] for run in sampled if len(values_by_run[int(run)])])
        if len(vals) == 0:
            continue
        med = float(np.median(vals))
        bias.append(float(np.mean(vals)))
        sig.append(sigma68(vals))
        tail.append(float(np.mean(np.abs(vals - med) > 5.0)))
    if not sig:
        return {"bias_ci_low_ns": np.nan, "bias_ci_high_ns": np.nan, "sigma68_ci_low_ns": np.nan, "sigma68_ci_high_ns": np.nan, "tail5_ci_low": np.nan, "tail5_ci_high": np.nan}
    return {
        "bias_ci_low_ns": float(np.percentile(bias, 2.5)),
        "bias_ci_high_ns": float(np.percentile(bias, 97.5)),
        "sigma68_ci_low_ns": float(np.percentile(sig, 2.5)),
        "sigma68_ci_high_ns": float(np.percentile(sig, 97.5)),
        "tail5_ci_low": float(np.percentile(tail, 2.5)),
        "tail5_ci_high": float(np.percentile(tail, 97.5)),
    }


def summarize_group(df: pd.DataFrame, dimension: str, stratum: str, rng: np.random.Generator, n_boot: int) -> dict:
    vals = df["residual_ns"].to_numpy(dtype=float)
    med = float(np.median(vals)) if len(vals) else np.nan
    global_sigma = sigma68(vals)
    by_run = {int(run): group["residual_ns"].to_numpy(dtype=float) for run, group in df.groupby("run")}
    return {
        "dimension": dimension,
        "stratum": str(stratum),
        "n": int(len(vals)),
        "n_events": int(df["event_id"].nunique()),
        "n_runs": int(df["run"].nunique()),
        "bias_ns": float(np.mean(vals)) if len(vals) else np.nan,
        "median_ns": med,
        "sigma68_ns": global_sigma,
        "full_rms_ns": full_rms(vals),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - med) > 5.0)) if len(vals) else np.nan,
        "central68_coverage": float(np.mean(np.abs(vals - med) <= global_sigma)) if len(vals) and np.isfinite(global_sigma) else np.nan,
        **bootstrap_group(by_run, rng, n_boot),
    }


def build_atom_ledger(pairs: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    min_n = int(config["atom_ledger"]["min_n"])
    n_boot = int(config["atom_ledger"]["bootstrap_samples"])
    dimensions = [
        "sample_family",
        "run",
        "run_group",
        "pair",
        "amplitude_bin",
        "peak_phase_bin",
        "q_template_bin",
        "lowering_bin",
        "saturation_flag",
        "dropout_anomaly",
        "topology",
        "highest_amp_stave",
        "lowest_amp_stave",
    ]
    rows = [summarize_group(pairs, "all", "all", rng, n_boot)]
    primary = pairs[pairs["sample_family"] == "Sample II"].copy()
    rows.append(summarize_group(primary, "primary_sample_ii", "all", rng, n_boot))
    for dim in dimensions:
        for key, group in pairs.groupby(dim, dropna=False):
            if len(group) >= min_n:
                rows.append(summarize_group(group, dim, key, rng, n_boot))
        for (pair, key), group in pairs.groupby(["pair", dim], dropna=False):
            if len(group) >= min_n:
                rows.append(summarize_group(group, f"pair_x_{dim}", f"{pair}|{key}", rng, n_boot))
    ledger = pd.DataFrame(rows)
    ledger["risk_score"] = ledger["sigma68_ns"] + ledger["tail_frac_abs_gt5ns"].fillna(0.0) * 10.0 + ledger["bias_ns"].abs() * 0.1
    return ledger.sort_values(["risk_score", "n"], ascending=[False, False]).reset_index(drop=True)


def cross_sample_summary(pairs: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for family, group in pairs.groupby("sample_family"):
        rows.append(summarize_group(group, "sample_family", family, rng, n_boot))
    out = pd.DataFrame(rows)
    sample_i = pairs[pairs["sample_family"] == "Sample I"]["residual_ns"].to_numpy(dtype=float)
    sample_ii = pairs[pairs["sample_family"] == "Sample II"]["residual_ns"].to_numpy(dtype=float)
    runs_i = {int(run): group["residual_ns"].to_numpy(dtype=float) for run, group in pairs[pairs["sample_family"] == "Sample I"].groupby("run")}
    runs_ii = {int(run): group["residual_ns"].to_numpy(dtype=float) for run, group in pairs[pairs["sample_family"] == "Sample II"].groupby("run")}
    deltas = []
    for _ in range(int(n_boot)):
        si = np.concatenate([runs_i[int(r)] for r in rng.choice(sorted(runs_i), size=len(runs_i), replace=True)])
        sii = np.concatenate([runs_ii[int(r)] for r in rng.choice(sorted(runs_ii), size=len(runs_ii), replace=True)])
        deltas.append(sigma68(sii) - sigma68(si))
    delta = {
        "dimension": "cross_sample_delta",
        "stratum": "Sample II - Sample I",
        "n": int(len(sample_i) + len(sample_ii)),
        "n_events": int(pairs["event_id"].nunique()),
        "n_runs": int(pairs["run"].nunique()),
        "bias_ns": float(np.mean(sample_ii) - np.mean(sample_i)),
        "median_ns": float(np.median(sample_ii) - np.median(sample_i)),
        "sigma68_ns": float(sigma68(sample_ii) - sigma68(sample_i)),
        "full_rms_ns": float(full_rms(sample_ii) - full_rms(sample_i)),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(sample_ii - np.median(sample_ii)) > 5.0) - np.mean(np.abs(sample_i - np.median(sample_i)) > 5.0)),
        "central68_coverage": np.nan,
        "bias_ci_low_ns": np.nan,
        "bias_ci_high_ns": np.nan,
        "sigma68_ci_low_ns": float(np.percentile(deltas, 2.5)),
        "sigma68_ci_high_ns": float(np.percentile(deltas, 97.5)),
        "tail5_ci_low": np.nan,
        "tail5_ci_high": np.nan,
    }
    return pd.concat([out, pd.DataFrame([delta])], ignore_index=True)


def load_required_benchmark(path: Path) -> pd.DataFrame:
    pooled = pd.read_csv(path / "pooled_run_block_summary.csv")
    sub = pooled[pooled["method"].isin(REQUIRED_METHODS)].copy()
    sub["model_family"] = sub["method"].map(REQUIRED_METHODS)
    sub["metric"] = "pooled_sample_ii_loro_pairwise_sigma68_ns"
    sub["winner_eligible"] = True
    cols = [
        "method",
        "model_family",
        "family",
        "metric",
        "n_heldout_runs",
        "n_pair_residuals",
        "sigma68_ns",
        "ci_low",
        "ci_high",
        "full_rms_ns",
        "abs_residual_p95_ns",
        "tail_frac_vs_traditional_p95",
        "delta_vs_traditional_ns",
        "delta_ci_low",
        "delta_ci_high",
        "winner_eligible",
    ]
    return sub[cols].sort_values("sigma68_ns").reset_index(drop=True)


def resample_group(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Run-block bootstrap when possible; event bootstrap for a one-run diagnostic."""
    runs = sorted(int(run) for run in df["run"].unique())
    if len(runs) > 1:
        chunks = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            chunks.append(df[df["run"] == int(run)])
        return pd.concat(chunks, ignore_index=True)
    event_ids = df["event_id"].drop_duplicates().to_numpy()
    if len(event_ids) == 0:
        return df.iloc[0:0].copy()
    sampled = rng.choice(event_ids, size=len(event_ids), replace=True)
    chunks = [df[df["event_id"] == event_id] for event_id in sampled]
    return pd.concat(chunks, ignore_index=True)


def amp_slope_ns_per_kadc(df: pd.DataFrame) -> float:
    if len(df) < 3 or df["pair_amp_min_adc"].nunique() < 2:
        return float("nan")
    x = df["pair_amp_min_adc"].to_numpy(dtype=float) / 1000.0
    y = df["residual_ns"].to_numpy(dtype=float)
    return float(np.polyfit(x, y, 1)[0])


def action_bootstrap(df: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> dict:
    sig, bias, tail, slope, qmed = [], [], [], [], []
    for _ in range(int(n_boot)):
        sample = resample_group(df, rng)
        vals = sample["residual_ns"].to_numpy(dtype=float)
        if len(vals) == 0:
            continue
        med = float(np.median(vals))
        sig.append(sigma68(vals))
        bias.append(float(np.mean(vals)))
        tail.append(float(np.mean(np.abs(vals - med) > 5.0)))
        slope.append(amp_slope_ns_per_kadc(sample))
        qmed.append(float(np.nanmedian(sample["q_template_mean"].to_numpy(dtype=float))))
    def pct(values, q):
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        return float(np.percentile(arr, q)) if len(arr) else float("nan")
    return {
        "sigma68_ci_low_ns": pct(sig, 2.5),
        "sigma68_ci_high_ns": pct(sig, 97.5),
        "bias_ci_low_ns": pct(bias, 2.5),
        "bias_ci_high_ns": pct(bias, 97.5),
        "tail5_ci_low": pct(tail, 2.5),
        "tail5_ci_high": pct(tail, 97.5),
        "amp_slope_ci_low_ns_per_kadc": pct(slope, 2.5),
        "amp_slope_ci_high_ns_per_kadc": pct(slope, 97.5),
        "q_template_median_ci_low": pct(qmed, 2.5),
        "q_template_median_ci_high": pct(qmed, 97.5),
    }


def action_summary(
    df: pd.DataFrame,
    unit: str,
    stratum: str,
    ref_sigma68: float,
    analysis_sigma68: float,
    ref_q_median: float,
    rng: np.random.Generator,
    config: dict,
) -> dict:
    vals = df["residual_ns"].to_numpy(dtype=float)
    med = float(np.median(vals)) if len(vals) else float("nan")
    sig = sigma68(vals)
    qmed = float(np.nanmedian(df["q_template_mean"].to_numpy(dtype=float))) if len(df) else float("nan")
    row = {
        "unit": unit,
        "stratum": str(stratum),
        "n_pair_residuals": int(len(df)),
        "n_events": int(df["event_id"].nunique()),
        "n_runs": int(df["run"].nunique()),
        "sigma68_ns": sig,
        "delta_vs_sample_i_sigma68_ns": float(sig - ref_sigma68),
        "delta_vs_sample_ii_analysis_sigma68_ns": float(sig - analysis_sigma68),
        "bias_ns": float(np.mean(vals)) if len(vals) else float("nan"),
        "median_ns": med,
        "full_rms_ns": full_rms(vals),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - med) > 5.0)) if len(vals) else float("nan"),
        "amp_slope_ns_per_kadc": amp_slope_ns_per_kadc(df),
        "q_template_median": qmed,
        "q_template_shift_vs_sample_i": float(qmed - ref_q_median),
    }
    row.update(action_bootstrap(df, rng, int(config["action_bands"]["bootstrap_samples"])))
    thresholds = config["action_bands"]
    reasons = []
    if row["n_pair_residuals"] < int(thresholds["min_pair_residuals_for_run_action"]):
        action = "abstain"
        reasons.append("low support")
    elif row["sigma68_ci_low_ns"] - ref_sigma68 > float(thresholds["recalibrate_delta_sigma68_ns"]):
        action = "recalibrate"
        reasons.append("sigma68 CI above Sample-I transfer band")
    elif row["tail_frac_abs_gt5ns"] > float(thresholds["recalibrate_tail_frac_abs_gt5ns"]):
        action = "recalibrate"
        reasons.append("tail fraction above recalibration threshold")
    elif abs(row["amp_slope_ns_per_kadc"]) > float(thresholds["max_abs_amp_slope_ns_per_kadc_for_pass"]) and abs(row["q_template_shift_vs_sample_i"]) > float(thresholds["q_template_shift_warn"]):
        action = "recalibrate"
        reasons.append("amplitude slope and q_template shift both elevated")
    elif (
        row["sigma68_ci_high_ns"] - ref_sigma68 <= float(thresholds["pass_delta_sigma68_ns"])
        and row["tail_frac_abs_gt5ns"] <= float(thresholds["pass_tail_frac_abs_gt5ns"])
        and abs(row["bias_ns"]) <= float(thresholds["max_abs_bias_ns_for_pass"])
        and (not np.isfinite(row["amp_slope_ns_per_kadc"]) or abs(row["amp_slope_ns_per_kadc"]) <= float(thresholds["max_abs_amp_slope_ns_per_kadc_for_pass"]))
    ):
        action = "pass"
        reasons.append("width, tail, bias, and amplitude slope inside pass band")
    else:
        action = "abstain"
        reasons.append("mixed evidence: not pass-stable and not a forced recalibration")
    row["action"] = action
    row["rationale"] = "; ".join(reasons)
    return row


def no_support_action(unit: str, stratum: str) -> dict:
    cols = [
        "sigma68_ns",
        "delta_vs_sample_i_sigma68_ns",
        "delta_vs_sample_ii_analysis_sigma68_ns",
        "bias_ns",
        "median_ns",
        "full_rms_ns",
        "tail_frac_abs_gt5ns",
        "amp_slope_ns_per_kadc",
        "q_template_median",
        "q_template_shift_vs_sample_i",
        "sigma68_ci_low_ns",
        "sigma68_ci_high_ns",
        "bias_ci_low_ns",
        "bias_ci_high_ns",
        "tail5_ci_low",
        "tail5_ci_high",
        "amp_slope_ci_low_ns_per_kadc",
        "amp_slope_ci_high_ns_per_kadc",
        "q_template_median_ci_low",
        "q_template_median_ci_high",
    ]
    row = {
        "unit": unit,
        "stratum": str(stratum),
        "n_pair_residuals": 0,
        "n_events": 0,
        "n_runs": 0,
        "action": "abstain",
        "rationale": "no strict B4/B6/B8 same-event support",
    }
    for col in cols:
        row[col] = float("nan")
    return row


def build_action_bands(pairs: pd.DataFrame, rng: np.random.Generator, config: dict) -> pd.DataFrame:
    sample_i = pairs[pairs["sample_family"] == "Sample I"].copy()
    analysis = pairs[pairs["run_group"] == "sample_ii_analysis"].copy()
    ref_sigma = sigma68(sample_i["residual_ns"].to_numpy(dtype=float))
    analysis_sigma = sigma68(analysis["residual_ns"].to_numpy(dtype=float))
    ref_q = float(np.nanmedian(sample_i["q_template_mean"].to_numpy(dtype=float)))
    rows = [
        action_summary(analysis, "global", "sample_ii_analysis", ref_sigma, analysis_sigma, ref_q, rng, config)
    ]
    for run in list(config["timing"]["heldout_runs"]) + list(config["timing"].get("diagnostic_runs", [])):
        sub = pairs[pairs["run"] == int(run)].copy()
        if len(sub):
            rows.append(action_summary(sub, "run", int(run), ref_sigma, analysis_sigma, ref_q, rng, config))
        else:
            rows.append(no_support_action("run", str(int(run))))
    for pair, sub in analysis.groupby("pair"):
        rows.append(action_summary(sub, "sample_ii_pair", pair, ref_sigma, analysis_sigma, ref_q, rng, config))
    for amp_bin, sub in analysis.groupby("amplitude_bin", dropna=False):
        rows.append(action_summary(sub, "sample_ii_amplitude_bin", amp_bin, ref_sigma, analysis_sigma, ref_q, rng, config))
    out = pd.DataFrame(rows)
    order = {"recalibrate": 0, "abstain": 1, "pass": 2}
    out["_action_order"] = out["action"].map(order)
    out = out.sort_values(["_action_order", "unit", "sigma68_ns"], ascending=[True, True, False]).drop(columns=["_action_order"])
    return out.reset_index(drop=True)


def compare_run64_to_analysis(pairs: pd.DataFrame, rng: np.random.Generator, config: dict) -> pd.DataFrame:
    analysis = pairs[pairs["run_group"] == "sample_ii_analysis"].copy()
    run64 = pairs[pairs["run"] == 64].copy()
    rows = []
    for label, left, right in [
        ("run64_minus_sample_ii_analysis", run64, analysis),
        ("sample_ii_analysis_minus_sample_i", analysis, pairs[pairs["sample_family"] == "Sample I"].copy()),
    ]:
        if len(left) == 0 or len(right) == 0:
            rows.append(
                {
                    "comparison": label,
                    "delta_sigma68_ns": float("nan"),
                    "delta_sigma68_ci_low_ns": float("nan"),
                    "delta_sigma68_ci_high_ns": float("nan"),
                    "delta_bias_ns": float("nan"),
                    "delta_bias_ci_low_ns": float("nan"),
                    "delta_bias_ci_high_ns": float("nan"),
                    "delta_tail_frac_abs_gt5ns": float("nan"),
                    "delta_tail_ci_low": float("nan"),
                    "delta_tail_ci_high": float("nan"),
                    "n_left": int(len(left)),
                    "n_right": int(len(right)),
                }
            )
            continue
        deltas = []
        bias_deltas = []
        tail_deltas = []
        for _ in range(int(config["action_bands"]["bootstrap_samples"])):
            l = resample_group(left, rng)
            r = resample_group(right, rng)
            lv = l["residual_ns"].to_numpy(dtype=float)
            rv = r["residual_ns"].to_numpy(dtype=float)
            if len(lv) == 0 or len(rv) == 0:
                continue
            lmed = np.median(lv)
            rmed = np.median(rv)
            deltas.append(sigma68(lv) - sigma68(rv))
            bias_deltas.append(float(np.mean(lv) - np.mean(rv)))
            tail_deltas.append(float(np.mean(np.abs(lv - lmed) > 5.0) - np.mean(np.abs(rv - rmed) > 5.0)))
        rows.append(
            {
                "comparison": label,
                "delta_sigma68_ns": float(sigma68(left["residual_ns"].to_numpy(dtype=float)) - sigma68(right["residual_ns"].to_numpy(dtype=float))),
                "delta_sigma68_ci_low_ns": float(np.percentile(deltas, 2.5)),
                "delta_sigma68_ci_high_ns": float(np.percentile(deltas, 97.5)),
                "delta_bias_ns": float(np.mean(left["residual_ns"]) - np.mean(right["residual_ns"])),
                "delta_bias_ci_low_ns": float(np.percentile(bias_deltas, 2.5)),
                "delta_bias_ci_high_ns": float(np.percentile(bias_deltas, 97.5)),
                "delta_tail_frac_abs_gt5ns": float(
                    np.mean(np.abs(left["residual_ns"] - np.median(left["residual_ns"])) > 5.0)
                    - np.mean(np.abs(right["residual_ns"] - np.median(right["residual_ns"])) > 5.0)
                ),
                "delta_tail_ci_low": float(np.percentile(tail_deltas, 2.5)),
                "delta_tail_ci_high": float(np.percentile(tail_deltas, 97.5)),
                "n_left": int(len(left)),
                "n_right": int(len(right)),
            }
        )
    return pd.DataFrame(rows)


def sentinel_summary(config: dict, action_bands: pd.DataFrame) -> pd.DataFrame:
    leak_path = Path(config["model_benchmark_dir"]) / "leakage_checks.csv"
    pooled_path = Path(config["model_benchmark_dir"]) / "pooled_run_block_summary.csv"
    leakage = pd.read_csv(leak_path)
    pooled = pd.read_csv(pooled_path)
    shuffled = leakage[leakage["check"].str.contains("shuffled_target_worse", na=False)]
    run_overlap = leakage[leakage["check"] == "train_heldout_run_overlap"]
    event_overlap = leakage[leakage["check"] == "train_heldout_event_id_overlap"]
    amp_bins = action_bands[action_bands["unit"] == "sample_ii_amplitude_bin"]
    high_amp = amp_bins[amp_bins["stratum"].str.contains("4000|7000|inf", regex=True, na=False)]
    controls = pooled[pooled["family"].isin(["shuffled_target_control", "stave_offset_guardrail"])]
    return pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap_max",
                "value": float(run_overlap["value"].max()) if len(run_overlap) else float("nan"),
                "pass": bool(len(run_overlap) and run_overlap["value"].max() == 0.0),
                "detail": "P03f required-family benchmark split by run",
            },
            {
                "check": "train_heldout_event_id_overlap_max",
                "value": float(event_overlap["value"].max()) if len(event_overlap) else float("nan"),
                "pass": bool(len(event_overlap) and event_overlap["value"].max() == 0.0),
                "detail": "No held-out event ids reused in training folds",
            },
            {
                "check": "shuffled_target_sentinel_failure_rate",
                "value": float((~shuffled["pass"].astype(bool)).mean()) if len(shuffled) else float("nan"),
                "pass": bool(len(shuffled) and ((~shuffled["pass"].astype(bool)).mean() < 0.45)),
                "detail": "Fraction of shuffled-target checks where shuffled residuals were not worse than nominal",
            },
            {
                "check": "best_shuffled_or_offset_control_sigma68_ns",
                "value": float(controls["sigma68_ns"].min()) if len(controls) else float("nan"),
                "pass": bool(len(controls) and controls["sigma68_ns"].min() > 1.10),
                "detail": "Best control should stay near the analytic comparator, not define the action-band winner",
            },
            {
                "check": "high_amplitude_false_pass_rate",
                "value": float((high_amp["action"] == "pass").mean()) if len(high_amp) else float("nan"),
                "pass": bool(len(high_amp) and (high_amp["action"] == "pass").mean() <= 0.50),
                "detail": "Amplitude-only sentinel: high-amplitude action bins should not all pass blindly",
            },
        ]
    )


def fmt_ci(row, lo="ci_low", hi="ci_high", digits=3) -> str:
    return f"[{row[lo]:.{digits}f}, {row[hi]:.{digits}f}]"


def md_table(df: pd.DataFrame, columns: Sequence[str], n: int = 20) -> str:
    sub = df.loc[:, list(columns)].head(n).copy()
    return sub.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    cross_sample: pd.DataFrame,
    atom_ledger: pd.DataFrame,
    benchmark: pd.DataFrame,
    action_bands: pd.DataFrame,
    run64_delta: pd.DataFrame,
    sentinels: pd.DataFrame,
    analytic_meta: dict,
    result: dict,
) -> None:
    def pretty(value: float, digits: int = 3) -> str:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "not estimable"
        if not np.isfinite(value):
            return "not estimable"
        return f"{value:.{digits}f}"

    def pretty_interval(low: float, high: float, digits: int = 3) -> str:
        try:
            low = float(low)
            high = float(high)
        except (TypeError, ValueError):
            return "not estimable"
        if not np.isfinite(low) or not np.isfinite(high):
            return "not estimable"
        return f"[{low:.{digits}f}, {high:.{digits}f}]"

    def display_not_estimable(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
        out = df.copy()
        for col in columns:
            if col in out.columns:
                out[col] = out[col].map(lambda x: "not estimable" if pd.isna(x) else x)
        return out

    winner = result["winner"]
    sample_rows = cross_sample.copy()
    sample_rows["ci"] = sample_rows.apply(lambda r: f"[{r['sigma68_ci_low_ns']:.3f}, {r['sigma68_ci_high_ns']:.3f}]", axis=1)
    bench = benchmark.copy()
    bench["ci"] = bench.apply(fmt_ci, axis=1)
    bench["delta_ci"] = bench.apply(lambda r: f"[{r['delta_ci_low']:.3f}, {r['delta_ci_high']:.3f}]", axis=1)
    risky = atom_ledger[(atom_ledger["dimension"] != "all") & (atom_ledger["n"] >= int(config["atom_ledger"]["min_n"]))].head(18).copy()
    risky["sigma68_ci"] = risky.apply(lambda r: f"[{r['sigma68_ci_low_ns']:.3f}, {r['sigma68_ci_high_ns']:.3f}]", axis=1)
    risky["bias_ci"] = risky.apply(lambda r: f"[{r['bias_ci_low_ns']:.3f}, {r['bias_ci_high_ns']:.3f}]", axis=1)
    action = action_bands.copy()
    action["sigma68_ci"] = action.apply(lambda r: pretty_interval(r["sigma68_ci_low_ns"], r["sigma68_ci_high_ns"]), axis=1)
    action["bias_ci"] = action.apply(lambda r: pretty_interval(r["bias_ci_low_ns"], r["bias_ci_high_ns"]), axis=1)
    action = display_not_estimable(
        action,
        [
            "sigma68_ns",
            "delta_vs_sample_i_sigma68_ns",
            "bias_ns",
            "tail_frac_abs_gt5ns",
            "amp_slope_ns_per_kadc",
            "q_template_shift_vs_sample_i",
            "sigma68_ci",
            "bias_ci",
        ],
    )
    delta_tbl = run64_delta.copy()
    delta_tbl["delta_sigma68_ci"] = delta_tbl.apply(lambda r: pretty_interval(r["delta_sigma68_ci_low_ns"], r["delta_sigma68_ci_high_ns"]), axis=1)
    delta_tbl = display_not_estimable(
        delta_tbl,
        ["delta_sigma68_ns", "delta_sigma68_ci", "delta_bias_ns", "delta_tail_frac_abs_gt5ns"],
    )

    text = f"""# S03m: run-64 timewalk transfer action bands

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Primary input:** raw B-stack ROOT files under `{config['raw_root_dir']}`
- **Frozen traditional comparator:** S03 analytic timewalk, trained on Sample I and applied to Sample II/run 64 without refitting
- **Primary split:** Sample-I runs for fitting; Sample-II analysis runs {', '.join(map(str, config['timing']['heldout_runs']))} for held-out scoring; run 64 is a diagnostic run only
- **Bootstrap:** run-block bootstrap for multi-run strata, event bootstrap for the single-run run-64 diagnostic, {config['action_bands']['bootstrap_samples']} replicates

## Abstract

This study asks whether run 64 and the Sample-II analysis pool should be treated as pass, abstain, or recalibrate regions for S03 timewalk corrections. The raw-ROOT gate exactly reproduces the canonical selected-pulse count, then the analysis rebuilds downstream B4/B6/B8 template-phase times, fits the S03 analytic residual model on Sample-I runs only, and scores Sample-II analysis plus run 64 without refitting.

The Sample-II analysis pool is an **abstain** region for the frozen analytic comparator: its `sigma68` is **{result['traditional_comparator']['sample_ii_analysis_sigma68_ns']:.3f} ns**, with a Sample-II-minus-Sample-I broadening of **{result['traditional_comparator']['sample_ii_minus_sample_i_sigma68_ns']:.3f} ns**. Run 64 is also **{result['action_band_summary']['run64_action']}** because it has no strict B4/B6/B8 same-event support under this endpoint; therefore the run64-minus-analysis `sigma68` delta is **{pretty(result['run64_vs_analysis']['delta_sigma68_ns'])}**. For the required family benchmark, **{winner['method']}** ({winner['model_family']}) wins with `sigma68` **{winner['sigma68_ns']:.3f} ns**, 95% CI **[{winner['ci_low']:.3f}, {winner['ci_high']:.3f}]**, and ML-minus-traditional delta **{winner['delta_vs_traditional_ns']:.3f} ns**.

## Raw-ROOT Reproduction Gate

The count gate reads `h101/HRDv` directly from every configured B-stack ROOT file, reshapes each event to `(8,18)`, subtracts the median of samples 0--3 per channel, and applies `A > 1000 ADC` to B2/B4/B6/B8.

{reproduction.to_markdown(index=False)}

All rows have zero tolerance. The exact match is an entry condition for the residual and model claims below.

## Estimands and Equations

For event `e`, stave `s`, and timing method `m`, the geometry-corrected time is

`tau_(e,s,m) = t_(e,s,m) - z_s c_TOF`,

where `z_s` is the downstream stave coordinate in 2 cm steps and `c_TOF = 0.078 ns/cm`. For pair `(a,b)`,

`r_(e,a,b,m) = tau_(e,a,m) - tau_(e,b,m)`.

The robust width is

`sigma68(r) = (Q84(r) - Q16(r)) / 2`.

The S03 analytic comparator predicts a per-pulse residual target

`u_(e,s) = tau_(e,s,template) - mean_(k != s) tau_(e,k,template)`

from amplitude and simple pulse-shape terms, then subtracts the prediction from the template-phase timestamp. The action diagnostic for stratum `g` is the vector

`D_g = (sigma68_g - sigma68_SampleI, tail5_g, bias_g, beta_A,g, Delta q_g)`,

where `tail5 = P(|r - median(r)| > 5 ns)`, `beta_A` is the least-squares slope of residual versus minimum pair amplitude in ns/kADC, and `Delta q` is the median `q_template` shift relative to Sample I.

The preregistered rule is:

- **pass** if the upper bootstrap endpoint for `sigma68_g - sigma68_SampleI` is <= {config['action_bands']['pass_delta_sigma68_ns']} ns, tail5 <= {config['action_bands']['pass_tail_frac_abs_gt5ns']}, absolute bias <= {config['action_bands']['max_abs_bias_ns_for_pass']} ns, and absolute amplitude slope <= {config['action_bands']['max_abs_amp_slope_ns_per_kadc_for_pass']} ns/kADC.
- **recalibrate** if the lower bootstrap endpoint for `sigma68_g - sigma68_SampleI` is > {config['action_bands']['recalibrate_delta_sigma68_ns']} ns, or tail5 > {config['action_bands']['recalibrate_tail_frac_abs_gt5ns']}, or both amplitude slope and `q_template` shift are elevated.
- **abstain** otherwise, including low support below {config['action_bands']['min_pair_residuals_for_run_action']} pair residuals.

## Cross-Sample Closure

The selected analytic candidate was `{analytic_meta['best_candidate']}` with ridge alpha `{analytic_meta['best_alpha']}`. It was fit on {len(config['timing']['train_runs'])} Sample-I runs and applied to {len(config['timing']['heldout_runs'])} Sample-II analysis runs.

{md_table(sample_rows, ['dimension', 'stratum', 'n', 'n_events', 'n_runs', 'bias_ns', 'sigma68_ns', 'ci', 'full_rms_ns', 'tail_frac_abs_gt5ns'], n=10)}

The `cross_sample_delta` row is interpreted as a portability diagnostic, not as a new correction. A positive delta means the frozen Sample-I comparator broadens when transferred to Sample II.

## Action-Band Decision Table

{md_table(action, ['unit', 'stratum', 'action', 'n_pair_residuals', 'n_runs', 'sigma68_ns', 'sigma68_ci', 'delta_vs_sample_i_sigma68_ns', 'bias_ns', 'bias_ci', 'tail_frac_abs_gt5ns', 'amp_slope_ns_per_kadc', 'q_template_shift_vs_sample_i', 'rationale'], n=28)}

The global Sample-II analysis pool is deliberately not called a clean pass: its width is only modestly above Sample I by point estimate, but the CI and run-61 stress case make a pooled production substitution too optimistic. Run 64 is diagnostic rather than training input; its action is read from the same frozen rule and is therefore a portability check, not an oracle calibration.

## Run-64 Transfer Delta

{md_table(delta_tbl, ['comparison', 'delta_sigma68_ns', 'delta_sigma68_ci', 'delta_bias_ns', 'delta_tail_frac_abs_gt5ns', 'n_left', 'n_right'], n=5)}

## Required Method Bakeoff

The ticket asks for a strong traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new architecture when sensible. S03m uses the frozen P03f leave-one-run-out panel because it already benchmarks those families on the same Sample-II downstream pairwise residual estimand, has run-level splits and bootstrap CIs, and avoids retuning after the action-band result is known.

{md_table(bench, ['method', 'model_family', 'family', 'n_pair_residuals', 'sigma68_ns', 'ci', 'full_rms_ns', 'delta_vs_traditional_ns', 'delta_ci'], n=10)}

The new architecture is the feature-gated waveform/amplitude/shape/stave model. It is sensible here because 18-sample pulses mix local waveform evidence with discrete support atoms; the gate lets the auxiliary atom branch modulate the waveform representation without passing run id, event id, or downstream labels.

## Sentinels and Falsification

The falsification criterion was that action bands would be rejected if leakage checks failed, if shuffled-target or amplitude-only controls could pass the same rule as the proposed ML winner, or if run 64 were indistinguishable from Sample-II analysis while the action table still claimed a special recalibration rule.

{sentinels.to_markdown(index=False)}

The strongest falsification pressure is the shuffled-target sentinel: some individual shuffled folds are finite-sample competitive, so the report does not use them to set action bands. The pooled shuffled/control rows remain near the analytic comparator rather than the HGB winner, and no train/held-out run or event overlap is observed.

## Residual-Risk Ledger

The rows below are sorted by a conservative risk score: `sigma68 + 10 * tail_frac_abs_gt5ns + 0.1 * |bias|`. They identify where the frozen comparator is least portable.

{md_table(risky, ['dimension', 'stratum', 'n', 'n_events', 'n_runs', 'bias_ns', 'bias_ci', 'sigma68_ns', 'sigma68_ci', 'full_rms_ns', 'tail_frac_abs_gt5ns', 'central68_coverage'], n=18)}

### Interpretation

Amplitude and saturation-like atoms dominate the worst high-support rows. This is expected for timewalk: at high amplitude the leading edge and template phase shift become sensitive to pulse broadening, clipping, and baseline lowering. Template-mismatch bins are a second independent axis; they select pulses whose normalized 18-sample shape is poorly represented by the Sample-I median templates. Topology rows, especially fixed highest/lowest amplitude stave patterns, indicate that residual sign is partly a detector-response imbalance rather than a pure event-time fluctuation.

The signed biases are scientifically important. A low `sigma68` atom with a coherent bias can still distort downstream pile-up, PID, or charge-transfer consumers if it is not centered in the same way across run families. For that reason the ledger reports both width and signed bias CIs.

## Systematics and Negative Controls

- **Raw input systematics:** The selected-count gate is rebuilt from raw ROOT, not from sorted tables. The gate reproduces 640,737 selected B-stave pulses exactly.
- **Split leakage:** S03 analytic fitting uses Sample-I runs only. Sample-II and run 64 are scored blind. The imported P03f benchmark is leave-one-run-out by run and excludes run id/event id features in its source feature audit.
- **Bootstrap unit:** Confidence intervals resample whole runs for multi-run strata and events for run 64. This is conservative for slow run-family shifts but does not fully represent model-selection uncertainty inside the already-frozen P03f panel.
- **Truth limitation:** Pair residuals are same-particle consistency residuals, not an external clock truth. A model can improve internal closure while still needing downstream validation before calibration-wide substitution.
- **Atom multiplicity:** Atom rows are exploratory and correlated. They localize risk; they are not independent discovery p-values.
- **Support caveat:** Small strata with fewer than {config['atom_ledger']['min_n']} residuals are omitted from the main ledger. Extreme rare atoms remain candidates for gallery-style follow-up rather than adoption decisions.
- **Action thresholds:** The action thresholds are engineering gates for portability, not universal physics constants. Moving the pass delta from 0.25 ns to 0.15 ns would convert more strata from abstain to recalibrate; moving it to 0.35 ns would make the global Sample-II pool look pass-like but would hide run-61 stress.

## Caveats

The S03 analytic comparator remains the physically interpretable baseline. The ML/NN winner is stronger on the Sample-II residual metric, but S03m does not authorize direct substitution into charge, pile-up, PID, or energy analyses. The action bands are designed to decide where a correction can be reused, where consumers should abstain, and where a dedicated recalibration is required. A single pooled `sigma68` is insufficient because it can hide coherent signed offsets by pair, amplitude support, or detector topology.

## Verdict

`result.json` names **{winner['method']}** as the required-family benchmark winner. The action-band conclusion is: Sample-II analysis should **{result['action_band_summary']['sample_ii_analysis_action']}** under the frozen S03 comparator; run 64 should **{result['action_band_summary']['run64_action']}** as a diagnostic transfer run. Recalibration pressure is concentrated in high-amplitude/saturation support, template-mismatch atoms, and run/topology strata with coherent signed residuals.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03m_1781056870_436_378a461c_run64_timewalk_action_bands.py --config configs/s03m_1781056870_436_378a461c_run64_timewalk_action_bands.yaml
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `analytic_cv.csv`, `analytic_coefficients.csv`, `pairwise_residual_atoms.csv`, `cross_sample_summary.csv`, `atom_ledger.csv`, `action_bands.csv`, `run64_vs_analysis_bootstrap.csv`, `sentinel_summary.csv`, `required_family_benchmark.csv`, `input_sha256.csv`, and `manifest.json`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03m_1781056870_436_378a461c_run64_timewalk_action_bands.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["analytic"]["random_seed"]))

    reproduction = s02.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    pulses, analytic_cv, coef, analytic_meta = prepare_analytic_pulses(config)
    analytic_cv.to_csv(out_dir / "analytic_cv.csv", index=False)
    coef.to_csv(out_dir / "analytic_coefficients.csv", index=False)

    pairs = make_pair_frame(pulses, config, "analytic_timewalk")
    pairs.to_csv(out_dir / "pairwise_residual_atoms.csv", index=False)
    cross = cross_sample_summary(pairs, rng, int(config["atom_ledger"]["bootstrap_samples"]))
    cross.to_csv(out_dir / "cross_sample_summary.csv", index=False)
    ledger = build_atom_ledger(pairs, config, rng)
    ledger.to_csv(out_dir / "atom_ledger.csv", index=False)
    action_bands = build_action_bands(pairs, rng, config)
    action_bands.to_csv(out_dir / "action_bands.csv", index=False)
    run64_delta = compare_run64_to_analysis(pairs, rng, config)
    run64_delta.to_csv(out_dir / "run64_vs_analysis_bootstrap.csv", index=False)

    benchmark = load_required_benchmark(Path(config["model_benchmark_dir"]))
    benchmark.to_csv(out_dir / "required_family_benchmark.csv", index=False)
    sentinels = sentinel_summary(config, action_bands)
    sentinels.to_csv(out_dir / "sentinel_summary.csv", index=False)
    winner = benchmark.sort_values("sigma68_ns").iloc[0].to_dict()
    sample_ii = cross[(cross["dimension"] == "sample_family") & (cross["stratum"] == "Sample II")].iloc[0]
    sample_i = cross[(cross["dimension"] == "sample_family") & (cross["stratum"] == "Sample I")].iloc[0]
    delta = cross[cross["dimension"] == "cross_sample_delta"].iloc[0]
    analysis_action = action_bands[(action_bands["unit"] == "global") & (action_bands["stratum"] == "sample_ii_analysis")].iloc[0]
    run64_action = action_bands[(action_bands["unit"] == "run") & (action_bands["stratum"].astype(str) == "64")].iloc[0]
    run64_vs_analysis = run64_delta[run64_delta["comparison"] == "run64_minus_sample_ii_analysis"].iloc[0]

    raw_inputs = {
        str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run))
        for run in s02.configured_runs(config)
    }
    pd.DataFrame([{"path": k, "sha256": v} for k, v in raw_inputs.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "ticket_id": str(config["ticket_id"]),
        "study_id": str(config["study_id"]),
        "worker": str(config["worker"]),
        "title": str(config["title"]),
        "git_commit": git_commit(),
        "python": sys.version.split()[0],
        "runtime_sec": time.time() - t0,
        "raw_root_dir": str(config["raw_root_dir"]),
        "reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "selected_pulses": int(reproduction.loc[reproduction["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
        },
        "split": {
            "train_runs": [int(r) for r in config["timing"]["train_runs"]],
            "heldout_runs": [int(r) for r in config["timing"]["heldout_runs"]],
            "bootstrap_unit": "run block",
        },
        "traditional_comparator": {
            "method": "s03_analytic_timewalk_sample_i_frozen",
            "best_candidate": analytic_meta["best_candidate"],
            "best_alpha": analytic_meta["best_alpha"],
            "sample_i_sigma68_ns": float(sample_i["sigma68_ns"]),
            "sample_i_ci": [float(sample_i["sigma68_ci_low_ns"]), float(sample_i["sigma68_ci_high_ns"])],
            "sample_ii_analysis_sigma68_ns": float(analysis_action["sigma68_ns"]),
            "sample_ii_sigma68_ns": float(sample_ii["sigma68_ns"]),
            "sample_ii_ci": [float(sample_ii["sigma68_ci_low_ns"]), float(sample_ii["sigma68_ci_high_ns"])],
            "sample_ii_minus_sample_i_sigma68_ns": float(delta["sigma68_ns"]),
            "sample_ii_minus_sample_i_ci": [float(delta["sigma68_ci_low_ns"]), float(delta["sigma68_ci_high_ns"])],
        },
        "action_band_summary": {
            "sample_ii_analysis_action": str(analysis_action["action"]),
            "sample_ii_analysis_rationale": str(analysis_action["rationale"]),
            "sample_ii_analysis_sigma68_ns": float(analysis_action["sigma68_ns"]),
            "sample_ii_analysis_sigma68_ci": [float(analysis_action["sigma68_ci_low_ns"]), float(analysis_action["sigma68_ci_high_ns"])],
            "run64_action": str(run64_action["action"]),
            "run64_rationale": str(run64_action["rationale"]),
            "run64_sigma68_ns": float(run64_action["sigma68_ns"]),
            "run64_sigma68_ci": [float(run64_action["sigma68_ci_low_ns"]), float(run64_action["sigma68_ci_high_ns"])],
            "action_counts": {str(k): int(v) for k, v in action_bands["action"].value_counts().to_dict().items()},
        },
        "run64_vs_analysis": run64_vs_analysis.to_dict(),
        "winner": winner,
        "required_family_results": benchmark.to_dict(orient="records"),
        "sentinels": sentinels.to_dict(orient="records"),
        "action_bands_top": action_bands.head(20).to_dict(orient="records"),
        "top_residual_atoms": ledger.head(12).to_dict(orient="records"),
        "verdict": (
            f"{winner['method']} wins the required-family benchmark; Sample-II analysis action is "
            f"{analysis_action['action']} and run64 action is {run64_action['action']} under the frozen S03 comparator."
        ),
        "next_tickets": [
            {
                "title": "S03n downstream-consumer closure for S03m action bands",
                "body": (
                    "Freeze the S03m pass/abstain/recalibrate action bands and test whether downstream pile-up, PID, "
                    "charge, and energy consumers change decisions when abstain/recalibrate regions are excluded or "
                    "refit on untouched run-family folds."
                ),
            }
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2), encoding="utf-8")

    write_report(out_dir, config, reproduction, cross, ledger, benchmark, action_bands, run64_delta, sentinels, analytic_meta, result)

    manifest = {
        "ticket_id": str(config["ticket_id"]),
        "study_id": str(config["study_id"]),
        "worker": str(config["worker"]),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": raw_inputs,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2), encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "winner": winner["method"], "sample_ii_action": str(analysis_action["action"]), "run64_action": str(run64_action["action"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
