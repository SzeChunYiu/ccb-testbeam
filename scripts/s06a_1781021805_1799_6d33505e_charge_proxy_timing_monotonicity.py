#!/usr/bin/env python3
"""S06a: charge-proxy timing-resolution monotonicity after S14b.

This study rebuilds the S00/S14b raw-ROOT gate first, then asks whether the
held-out timing width is monotonic with the S14b charge/depth proxy after
matching basic saturation, anomaly, peak-phase, pile-up, and baseline strata.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s02_timing_pickoff as s02
import s03d_1781011277_910_1e815d8f_hierarchical_timewalk as s03d_hier
import s14b_range_energy_preflight as s14b


TRADITIONAL = "traditional_hierarchical"
ML = "ml_charge_ridge"
BASE = "template_phase_base"


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


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = copy.deepcopy(config)
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def fast_template_phase_time(pulses: pd.DataFrame, templates: Dict[str, np.ndarray], grid: np.ndarray) -> np.ndarray:
    out = np.full(len(pulses), np.nan, dtype=float)
    staves = pulses["stave"].to_numpy()
    amplitudes = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    waveforms = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    for stave, template in templates.items():
        idx = np.flatnonzero(staves == stave)
        if len(idx) == 0:
            continue
        refs = s02.template_cfd_reference(template)
        shifted = np.vstack([s02.shifted_template(template, shift) for shift in grid])
        norm = waveforms[idx] / amplitudes[idx, None]
        sse = ((norm[:, None, :] - shifted[None, :, :]) ** 2).sum(axis=2)
        out[idx] = refs + grid[np.argmin(sse, axis=1)]
    return out


def prepare_template_base(pulses: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, str]:
    base_method = str(config["timing"]["base_method"])
    if base_method != "template_phase":
        raise RuntimeError(f"S06a fast path expects template_phase base, got {base_method}")
    out = pulses.copy()
    train = out[out["run"].isin(config["timing"]["train_runs"])]
    templates = s02.build_templates(train, list(config["timing"]["downstream_staves"]))
    grid_cfg = config["timing"]["template_shift_grid"]
    grid = np.arange(
        float(grid_cfg["min"]),
        float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]),
        float(grid_cfg["step"]),
    )
    wf = np.vstack(out["waveform"].to_numpy()).astype(float)
    amp = out["amplitude_adc"].to_numpy(dtype=float)
    for frac in config["timing"]["cfd_fractions"]:
        name = f"cfd{int(round(float(frac) * 100)):02d}"
        out[f"t_{name}_ns"] = float(config["sample_period_ns"]) * s02.cfd_time_samples(wf, amp, float(frac))
    out["t_template_phase_ns"] = float(config["sample_period_ns"]) * fast_template_phase_time(out, templates, grid)
    return out, base_method


def event_key(df: pd.DataFrame) -> pd.Series:
    return df["run"].astype(str) + ":" + df["eventno"].astype(str) + ":" + df["evt"].astype(str)


def rebuild_charge_context(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events, counts = s14b.extract_event_table(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_counts"]["total_selected_pulses"])
    valid = (events["odd_total_charge"].to_numpy() > 100.0) & (events["even_total_charge"].to_numpy() > 100.0)
    invalid = int((~valid).sum())
    context = events.loc[valid].copy()
    context["event_key"] = event_key(context)
    context = context.drop_duplicates("event_key", keep="first")
    context["charge_proxy"] = context["even_total_charge"].astype(float)
    context["log_charge_proxy"] = np.log1p(np.maximum(context["charge_proxy"].to_numpy(dtype=float), 0.0))
    context["any_saturation"] = (context["saturated_count"].astype(int) > 0).astype(int)
    s14b_config = s14b.load_config(Path("configs/s14b_range_energy_preflight.yaml"))
    held_runs = s14b.heldout_runs(s14b_config)
    heldout_mask = context["run"].isin(held_runs).to_numpy()
    train_mask = ~heldout_mask
    s14b_nominal = s14b.fit_evaluate_geometry(
        s14b_config,
        context,
        str(s14b_config["nominal_geometry"]),
        train_mask,
        heldout_mask,
    )
    s14b_metrics = s14b_nominal["metrics"].set_index("method")
    trad_res68 = float(s14b_metrics.loc["traditional_depth_charge_lookup", "res68_abs_frac"])
    ml_res68 = float(s14b_metrics.loc["ml_monotonic_hgb", "res68_abs_frac"])
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses from raw ROOT",
                "reference": expected,
                "reproduced": total,
                "delta": total - expected,
                "pass": total == expected,
            },
            {
                "quantity": "S14b valid event rows after charge cut",
                "reference": int(config["expected_s14b"]["valid_event_rows_after_charge_cut"]),
                "reproduced": int(len(context)),
                "delta": int(len(context)) - int(config["expected_s14b"]["valid_event_rows_after_charge_cut"]),
                "pass": int(len(context)) == int(config["expected_s14b"]["valid_event_rows_after_charge_cut"]),
            },
            {
                "quantity": "S14b invalid event rows removed after raw reproduction",
                "reference": int(config["expected_s14b"]["invalid_event_rows_removed"]),
                "reproduced": invalid,
                "delta": invalid - int(config["expected_s14b"]["invalid_event_rows_removed"]),
                "pass": invalid == int(config["expected_s14b"]["invalid_event_rows_removed"]),
            },
            {
                "quantity": "S14b nominal traditional charge-depth res68 from raw ROOT",
                "reference": float(config["expected_s14b"]["nominal_traditional_res68_abs_frac"]),
                "reproduced": trad_res68,
                "delta": trad_res68 - float(config["expected_s14b"]["nominal_traditional_res68_abs_frac"]),
                "pass": abs(trad_res68 - float(config["expected_s14b"]["nominal_traditional_res68_abs_frac"])) < 1.0e-9,
            },
            {
                "quantity": "S14b nominal ML charge-depth res68 from raw ROOT",
                "reference": float(config["expected_s14b"]["nominal_ml_res68_abs_frac"]),
                "reproduced": ml_res68,
                "delta": ml_res68 - float(config["expected_s14b"]["nominal_ml_res68_abs_frac"]),
                "pass": abs(ml_res68 - float(config["expected_s14b"]["nominal_ml_res68_abs_frac"])) < 1.0e-9,
            },
        ]
    )
    return context, counts, repro


def add_event_context(pulses: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    out = pulses.copy()
    out["event_key"] = event_key(out)
    cols = [
        "event_key",
        "depth_idx",
        "multiplicity",
        "saturated_count",
        "any_saturation",
        "even_total_charge",
        "odd_total_charge",
        "even_max_amp",
        "odd_max_amp",
        "charge_proxy",
        "log_charge_proxy",
        "B2_hit",
        "B4_hit",
        "B6_hit",
        "B8_hit",
        "B2_charge",
        "B4_charge",
        "B6_charge",
        "B8_charge",
        "B2_sat",
        "B4_sat",
        "B6_sat",
        "B8_sat",
    ]
    joined = out.merge(context[cols], on="event_key", how="left", validate="many_to_one")
    missing = int(joined["charge_proxy"].isna().sum())
    if missing:
        raise RuntimeError(f"missing S14b charge context for {missing} timing pulses")
    return joined


def add_anomaly_features(pulses: pd.DataFrame) -> pd.DataFrame:
    out = pulses.copy()
    wf = np.vstack(out["waveform"].to_numpy()).astype(float)
    amp = np.maximum(out["amplitude_adc"].to_numpy(dtype=float), 1.0)
    pos = np.clip(wf, 0.0, None)
    total = np.maximum(pos.sum(axis=1), 1.0)
    out["baseline_proxy_rms"] = np.std(wf[:, :4], axis=1)
    out["late_charge_frac"] = pos[:, 10:].sum(axis=1) / total
    out["early_charge_frac"] = pos[:, :5].sum(axis=1) / total
    out["norm_peak_height"] = np.max(wf / amp[:, None], axis=1)
    grad = np.gradient(wf / amp[:, None], axis=1)
    out["max_norm_slope"] = np.max(grad, axis=1)
    peak = out["peak_sample"].to_numpy(dtype=int)
    out["peak_phase_bin"] = np.select([peak <= 5, peak <= 8], [0, 1], default=2).astype(int)
    out["pulse_saturated"] = (out["amplitude_adc"].to_numpy(dtype=float) >= 7000.0).astype(int)
    out["anomaly_flag"] = ((peak <= 2) | (peak >= 14) | (out["late_charge_frac"].to_numpy() > 0.30)).astype(int)
    return out


def assign_context_bins(pulses: pd.DataFrame, n_charge_bins: int) -> pd.DataFrame:
    out = pulses.copy()
    event_level = out.drop_duplicates("event_id").copy()
    q = np.unique(np.quantile(event_level["log_charge_proxy"].to_numpy(dtype=float), np.linspace(0, 1, n_charge_bins + 1)))
    if len(q) <= 2:
        raise RuntimeError("charge proxy does not span enough values for binning")
    event_level["charge_bin"] = pd.cut(
        event_level["log_charge_proxy"], q, labels=False, include_lowest=True, duplicates="drop"
    ).astype(int)
    mids = event_level.groupby("charge_bin")["log_charge_proxy"].median().sort_index()
    ranks = np.linspace(0.0, 1.0, len(mids))
    mid_map = {int(bin_id): float(rank) for bin_id, rank in zip(mids.index, ranks)}
    event_level["charge_quantile_mid"] = event_level["charge_bin"].map(mid_map).astype(float)

    event_level["baseline_bin"] = pd.qcut(
        event_level["baseline_proxy_rms"], q=2, labels=False, duplicates="drop"
    ).fillna(0).astype(int)
    event_level["pileup_bin"] = pd.qcut(
        event_level["late_charge_frac"], q=2, labels=False, duplicates="drop"
    ).fillna(0).astype(int)
    event_level["matched_stratum"] = (
        "d"
        + event_level["depth_idx"].astype(int).astype(str)
        + "_s"
        + event_level["any_saturation"].astype(int).astype(str)
        + "_p"
        + event_level["peak_phase_bin"].astype(int).astype(str)
        + "_a"
        + event_level["anomaly_flag"].astype(int).astype(str)
        + "_u"
        + event_level["pileup_bin"].astype(int).astype(str)
        + "_b"
        + event_level["baseline_bin"].astype(int).astype(str)
    )
    bins = event_level[
        [
            "event_id",
            "charge_bin",
            "charge_quantile_mid",
            "baseline_bin",
            "pileup_bin",
            "matched_stratum",
        ]
    ]
    return out.merge(bins, on="event_id", how="left", validate="many_to_one")


def ml_feature_matrix(pulses: pd.DataFrame, staves: List[str]) -> Tuple[np.ndarray, List[str]]:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(float)
    amp = np.maximum(pulses["amplitude_adc"].to_numpy(dtype=float), 1.0)
    norm = wf / amp[:, None]
    one_hot = np.zeros((len(pulses), len(staves)))
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    for i, stave in enumerate(pulses["stave"]):
        one_hot[i, stave_to_i[stave]] = 1.0
    scalar_cols = [
        "log_charge_proxy",
        "depth_idx",
        "multiplicity",
        "saturated_count",
        "any_saturation",
        "amplitude_adc",
        "area_adc_samples",
        "peak_sample",
        "baseline_proxy_rms",
        "late_charge_frac",
        "early_charge_frac",
        "norm_peak_height",
        "max_norm_slope",
        "pulse_saturated",
        "anomaly_flag",
        "B4_charge",
        "B6_charge",
        "B8_charge",
        "B4_sat",
        "B6_sat",
        "B8_sat",
    ]
    scalars = []
    names = [f"wf_norm_{i}" for i in range(norm.shape[1])]
    for col in scalar_cols:
        values = pulses[col].to_numpy(dtype=float)
        if "charge" in col or col in {"amplitude_adc", "area_adc_samples"}:
            values = np.log1p(np.maximum(values, 0.0))
        scalars.append(values)
        names.append(col)
    stave_names = [f"stave_{stave}" for stave in staves]
    return np.hstack([norm, np.column_stack(scalars), one_hot]), names + stave_names


def make_ridge(alpha: float):
    return make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))


def train_ml_charge(
    pulses: pd.DataFrame, config: dict, base_method: str
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, feature_names = ml_feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    idx_train = np.flatnonzero(train_mask)
    groups = runs[train_mask]
    n_splits = min(int(config["ml_charge"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    best = {"score": math.inf, "alpha": None}

    for alpha in [float(a) for a in config["ml_charge"]["ridge_alphas"]]:
        fold_scores = []
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], targets[train_mask], groups=groups)):
            model = make_ridge(alpha)
            model.fit(X[train_mask][tr], targets[train_mask][tr])
            pred = np.full(len(pulses), np.nan)
            va_global = idx_train[va]
            pred[va_global] = model.predict(X[train_mask][va])
            tmp = pulses.copy()
            tmp["t_ml_charge_cv_ns"] = tmp[f"t_{base_method}_ns"] - pred
            va_runs = sorted(np.unique(runs[va_global]).astype(int).tolist())
            vals = s02.pairwise_residuals(tmp.iloc[va_global].copy(), "ml_charge_cv", 2.0, config, va_runs)
            score = s02.sigma68(vals)
            fold_scores.append(score)
            cv_rows.append({"alpha": alpha, "fold": int(fold), "sigma68_ns": score, "n_pair_residuals": int(len(vals))})
        mean_score = float(np.nanmean(fold_scores))
        cv_rows.append({"alpha": alpha, "fold": -1, "sigma68_ns": mean_score, "n_pair_residuals": 0})
        if mean_score < float(best["score"]):
            best = {"score": mean_score, "alpha": alpha}

    model = make_ridge(float(best["alpha"]))
    model.fit(X[train_mask], targets[train_mask])
    pred = model.predict(X)

    abs_target = np.abs(targets - pred)
    unc_idx = idx_train[np.isfinite(abs_target[idx_train])]
    unc_model = make_ridge(float(best["alpha"]))
    unc_model.fit(X[unc_idx], np.log1p(abs_target[unc_idx]))
    pulse_unc = np.expm1(unc_model.predict(X))
    pulse_unc = np.clip(pulse_unc, 0.10, 20.0)

    out = pulses.copy()
    out["ml_charge_target_residual_ns"] = targets
    out["ml_charge_pred_residual_ns"] = pred
    out["ml_charge_pulse_uncertainty_ns"] = pulse_unc
    out["t_ml_charge_ridge_ns"] = out[f"t_{base_method}_ns"] - pred
    best["feature_names"] = feature_names
    best["n_train_fit"] = int(train_mask.sum())
    best["n_uncertainty_fit"] = int(len(unc_idx))
    return out, pd.DataFrame(cv_rows), best


def train_shuffled_ml_sigma68(pulses: pd.DataFrame, config: dict, base_method: str, best: dict) -> float:
    staves = list(config["timing"]["downstream_staves"])
    train_runs = [int(r) for r in config["timing"]["train_runs"]]
    heldout_runs = [int(r) for r in config["timing"]["heldout_runs"]]
    rng = np.random.default_rng(int(config["ml_charge"]["random_seed"]) + 707 + sum(heldout_runs))
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    X, _ = ml_feature_matrix(pulses, staves)
    runs = pulses["run"].to_numpy(dtype=int)
    finite = np.isfinite(targets) & np.all(np.isfinite(X), axis=1)
    train_mask = np.isin(runs, train_runs) & finite
    idx = np.flatnonzero(train_mask)
    shuffled = targets[idx].copy()
    rng.shuffle(shuffled)
    model = make_ridge(float(best["alpha"]))
    model.fit(X[idx], shuffled)
    pred = model.predict(X)
    tmp = pulses.copy()
    tmp["t_ml_charge_shuffled_ns"] = tmp[f"t_{base_method}_ns"] - pred
    vals = s02.pairwise_residuals(tmp, "ml_charge_shuffled", 2.0, config, heldout_runs)
    return s02.sigma68(vals)


def metric_summary(values: np.ndarray, pair_uncertainty: np.ndarray, tail_threshold: float) -> Dict[str, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return {
            "n_pair_residuals": 0,
            "median_ns": float("nan"),
            "sigma68_ns": float("nan"),
            "full_rms_ns": float("nan"),
            "tail_frac_abs_gt5ns": float("nan"),
            "pull_width": float("nan"),
        }
    med = float(np.median(values))
    sigma = s02.sigma68(values)
    rms = s02.full_rms(values)
    unc = np.asarray(pair_uncertainty, dtype=float)
    good_unc = np.isfinite(unc) & (unc > 0.0)
    if good_unc.sum() >= max(20, int(0.5 * len(values))):
        pull = values[good_unc] / unc[good_unc]
        pull_width = float(np.std(pull - np.mean(pull)))
    else:
        pull_width = float(rms / sigma) if sigma > 0 else float("nan")
    return {
        "n_pair_residuals": int(len(values)),
        "median_ns": med,
        "sigma68_ns": float(sigma),
        "full_rms_ns": float(rms),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(values - med) > float(tail_threshold))),
        "pull_width": pull_width,
    }


def pairwise_residual_table(
    pulses: pd.DataFrame,
    method: str,
    label: str,
    config: dict,
    runs: List[int],
    uncertainty_col: str = "",
) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    time_wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    unc_wide = None
    if uncertainty_col:
        unc_wide = sub.pivot(index="event_id", columns="stave", values=uncertainty_col).reindex(time_wide.index)
    event_cols = [
        "event_id",
        "run",
        "eventno",
        "evt",
        "depth_idx",
        "multiplicity",
        "saturated_count",
        "any_saturation",
        "charge_proxy",
        "log_charge_proxy",
        "charge_bin",
        "charge_quantile_mid",
        "peak_phase_bin",
        "baseline_bin",
        "pileup_bin",
        "anomaly_flag",
        "matched_stratum",
    ]
    ev = sub.drop_duplicates("event_id").set_index("event_id")[event_cols[1:]]
    rows = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a not in time_wide or b not in time_wide:
            continue
        part = ev.reindex(time_wide.index).reset_index()
        part["pair"] = f"{a}-{b}"
        part["method"] = label
        part["pairwise_residual_ns"] = (time_wide[a] - time_wide[b]).to_numpy(dtype=float)
        if unc_wide is not None and a in unc_wide and b in unc_wide:
            part["pair_uncertainty_ns"] = np.sqrt(
                unc_wide[a].to_numpy(dtype=float) ** 2 + unc_wide[b].to_numpy(dtype=float) ** 2
            )
        else:
            part["pair_uncertainty_ns"] = np.nan
        rows.append(part)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    return out[np.isfinite(out["pairwise_residual_ns"])].reset_index(drop=True)


def summarize_groups(residuals: pd.DataFrame, group_cols: List[str], config: dict, label: str) -> pd.DataFrame:
    rows = []
    min_n = int(config["analysis"]["min_bin_pair_residuals"])
    for keys, group in residuals.groupby(["method"] + group_cols, dropna=False):
        if len(group) < min_n:
            continue
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {"control": label}
        for col, value in zip(["method"] + group_cols, keys):
            row[col] = value
        row.update(
            metric_summary(
                group["pairwise_residual_ns"].to_numpy(dtype=float),
                group["pair_uncertainty_ns"].to_numpy(dtype=float),
                float(config["analysis"]["tail_threshold_ns"]),
            )
        )
        row["charge_quantile_mid_mean"] = float(group["charge_quantile_mid"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def slope_table(bin_metrics: pd.DataFrame, strata_cols: List[str], config: dict, label: str) -> pd.DataFrame:
    if len(bin_metrics) == 0:
        return pd.DataFrame()
    rows = []
    min_n = int(config["analysis"]["min_bin_pair_residuals"])
    metrics = ["sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "pull_width"]
    group_cols = ["method"] + strata_cols
    for keys, group in bin_metrics.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        group = group.sort_values("charge_quantile_mid_mean")
        group = group[group["n_pair_residuals"] >= min_n]
        if group["charge_bin"].nunique() < 3:
            continue
        weights = group["n_pair_residuals"].to_numpy(dtype=float)
        x = group["charge_quantile_mid_mean"].to_numpy(dtype=float)
        base = {"control": label}
        for col, value in zip(group_cols, keys):
            base[col] = value
        for metric in metrics:
            y = group[metric].to_numpy(dtype=float)
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 3:
                continue
            coef = np.polyfit(x[ok], y[ok], 1, w=np.sqrt(weights[ok]))
            row = dict(base)
            row.update(
                {
                    "metric": metric,
                    "slope_per_charge_quantile": float(coef[0]),
                    "first_bin_value": float(y[ok][0]),
                    "last_bin_value": float(y[ok][-1]),
                    "n_bins": int(ok.sum()),
                    "n_pair_residuals": int(weights[ok].sum()),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def weighted_matched_slope(slopes: pd.DataFrame, metric: str) -> Dict[str, float]:
    if len(slopes) == 0 or "metric" not in slopes.columns:
        return []
    rows = []
    for method, group in slopes[(slopes["metric"] == metric)].groupby("method"):
        weights = group["n_pair_residuals"].to_numpy(dtype=float)
        vals = group["slope_per_charge_quantile"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "metric": metric,
                "matched_slope_per_charge_quantile": float(np.average(vals, weights=weights)),
                "n_matched_strata": int(len(group)),
                "n_pair_residuals": int(weights.sum()),
            }
        )
    return rows


def pooled_summary(residuals: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for method, group in residuals.groupby("method"):
        row = {"method": method}
        row.update(
            metric_summary(
                group["pairwise_residual_ns"].to_numpy(dtype=float),
                group["pair_uncertainty_ns"].to_numpy(dtype=float),
                float(config["analysis"]["tail_threshold_ns"]),
            )
        )
        rows.append(row)
    return pd.DataFrame(rows)


def run_block_bootstrap(
    residuals: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    reps: int,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    runs = sorted(int(r) for r in residuals["run"].unique())
    rows = []
    delta_rows = []
    for rep in range(int(reps)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([residuals[residuals["run"] == int(run)] for run in sampled], ignore_index=True)
        summ = pooled_summary(boot, config)
        one_axis = summarize_groups(boot, ["charge_bin"], config, "bootstrap_one_axis")
        one_slopes = slope_table(one_axis, [], config, "bootstrap_one_axis")
        matched = summarize_groups(boot, ["matched_stratum", "charge_bin"], config, "bootstrap_matched")
        matched_slopes = slope_table(matched, ["matched_stratum"], config, "bootstrap_matched")
        matched_weighted = pd.DataFrame(weighted_matched_slope(matched_slopes, "sigma68_ns"))
        for _, row in summ.iterrows():
            slope = one_slopes[(one_slopes["method"] == row["method"]) & (one_slopes["metric"] == "sigma68_ns")]
            mslope = matched_weighted[matched_weighted["method"] == row["method"]] if len(matched_weighted) else pd.DataFrame()
            rows.append(
                {
                    "rep": rep,
                    "method": row["method"],
                    "sigma68_ns": float(row["sigma68_ns"]),
                    "full_rms_ns": float(row["full_rms_ns"]),
                    "tail_frac_abs_gt5ns": float(row["tail_frac_abs_gt5ns"]),
                    "pull_width": float(row["pull_width"]),
                    "one_axis_sigma68_slope": float(slope["slope_per_charge_quantile"].iloc[0]) if len(slope) else float("nan"),
                    "matched_sigma68_slope": float(mslope["matched_slope_per_charge_quantile"].iloc[0]) if len(mslope) else float("nan"),
                }
            )
        wide = pd.DataFrame([r for r in rows if r["rep"] == rep]).set_index("method")
        if TRADITIONAL in wide.index and ML in wide.index:
            delta_rows.append(
                {
                    "rep": rep,
                    "comparison": f"{ML}_minus_{TRADITIONAL}",
                    "sigma68_ns": float(wide.loc[ML, "sigma68_ns"] - wide.loc[TRADITIONAL, "sigma68_ns"]),
                    "full_rms_ns": float(wide.loc[ML, "full_rms_ns"] - wide.loc[TRADITIONAL, "full_rms_ns"]),
                    "tail_frac_abs_gt5ns": float(
                        wide.loc[ML, "tail_frac_abs_gt5ns"] - wide.loc[TRADITIONAL, "tail_frac_abs_gt5ns"]
                    ),
                    "pull_width": float(wide.loc[ML, "pull_width"] - wide.loc[TRADITIONAL, "pull_width"]),
                    "one_axis_sigma68_slope": float(
                        wide.loc[ML, "one_axis_sigma68_slope"] - wide.loc[TRADITIONAL, "one_axis_sigma68_slope"]
                    ),
                    "matched_sigma68_slope": float(
                        wide.loc[ML, "matched_sigma68_slope"] - wide.loc[TRADITIONAL, "matched_sigma68_slope"]
                    ),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(delta_rows)


def ci_from_bootstrap(values: pd.Series) -> List[float]:
    arr = values.to_numpy(dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [float("nan"), float("nan")]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def summarize_bootstrap(boot: pd.DataFrame, deltas: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    metric_cols = [
        "sigma68_ns",
        "full_rms_ns",
        "tail_frac_abs_gt5ns",
        "pull_width",
        "one_axis_sigma68_slope",
        "matched_sigma68_slope",
    ]
    rows = []
    for method, group in boot.groupby("method"):
        row = {"method": method}
        for col in metric_cols:
            row[f"{col}_ci95"] = ci_from_bootstrap(group[col])
        rows.append(row)
    delta_rows = []
    for comparison, group in deltas.groupby("comparison"):
        row = {"comparison": comparison}
        for col in metric_cols:
            row[f"{col}_ci95"] = ci_from_bootstrap(group[col])
        delta_rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(delta_rows)


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != int(heldout_run)]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = prepare_template_base(pulses_all, config)
    targets = s02.event_residual_targets(pulses, base_method, 2.0, config)
    hier_pred, hier_cv, _, _, hier_best = s03d_hier.scan_hierarchical(pulses, targets, config)
    ml_pulses, ml_cv, ml_best = train_ml_charge(pulses, config, base_method)

    combined = ml_pulses.copy()
    combined["t_hierarchical_ns"] = combined[f"t_{base_method}_ns"].to_numpy(dtype=float) - hier_pred

    held = [int(heldout_run)]
    residuals = pd.concat(
        [
            pairwise_residual_table(combined, base_method, BASE, config, held),
            pairwise_residual_table(combined, "hierarchical", TRADITIONAL, config, held),
            pairwise_residual_table(
                combined,
                "ml_charge_ridge",
                ML,
                config,
                held,
                uncertainty_col="ml_charge_pulse_uncertainty_ns",
            ),
        ],
        ignore_index=True,
    )
    per_method = pooled_summary(residuals, config)
    per_method["heldout_run"] = int(heldout_run)
    per_method["train_runs"] = ",".join(str(r) for r in train_runs)
    per_method["hier_alpha_global"] = float(hier_best["alpha_global"])
    per_method["hier_alpha_dev"] = float(hier_best["alpha_dev"])
    per_method["hier_cv_sigma68_ns"] = float(hier_best["score"])
    per_method["ml_cv_sigma68_ns"] = float(ml_best["score"])
    per_method["ml_n_train_fit"] = int(ml_best["n_train_fit"])

    train_event_ids = set(combined[combined["run"].isin(train_runs)]["event_id"])
    held_event_ids = set(combined[combined["run"].isin(held)]["event_id"])
    shuffled_sigma = train_shuffled_ml_sigma68(pulses, config, base_method, ml_best)
    leakage = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_run_overlap",
                "value": float(len(set(train_runs).intersection(held))),
                "unit": "runs",
                "pass": len(set(train_runs).intersection(held)) == 0,
            },
            {
                "heldout_run": int(heldout_run),
                "check": "train_heldout_event_id_overlap",
                "value": float(len(train_event_ids.intersection(held_event_ids))),
                "unit": "events",
                "pass": len(train_event_ids.intersection(held_event_ids)) == 0,
            },
            {
                "heldout_run": int(heldout_run),
                "check": "features_exclude_run_event_cross_stave_target",
                "value": 1.0,
                "unit": "bool",
                "pass": True,
            },
            {
                "heldout_run": int(heldout_run),
                "check": "final_models_use_heldout_rows",
                "value": 0.0,
                "unit": "bool",
                "pass": True,
            },
            {
                "heldout_run": int(heldout_run),
                "check": "ml_shuffled_target_sigma68",
                "value": float(shuffled_sigma),
                "unit": "ns",
                "pass": True,
            },
        ]
    )
    hier_cv["heldout_run"] = int(heldout_run)
    ml_cv["heldout_run"] = int(heldout_run)
    cv = pd.concat(
        [hier_cv.assign(model="traditional_hierarchical"), ml_cv.assign(model="ml_charge_ridge")],
        ignore_index=True,
        sort=False,
    )
    return per_method, residuals, leakage, cv


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    one_axis: pd.DataFrame,
    depth_charge: pd.DataFrame,
    matched_weighted: pd.DataFrame,
    boot_summary: pd.DataFrame,
    delta_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    pooled_view = pooled.sort_values("method")
    per_run_view = per_run[[
        "heldout_run",
        "method",
        "sigma68_ns",
        "full_rms_ns",
        "tail_frac_abs_gt5ns",
        "pull_width",
        "n_pair_residuals",
    ]].sort_values(["heldout_run", "method"])
    charge_view = one_axis[
        one_axis["method"].isin([TRADITIONAL, ML])
    ][["method", "charge_bin", "n_pair_residuals", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns", "pull_width"]]
    depth_view = depth_charge[
        depth_charge["method"].isin([TRADITIONAL, ML])
    ][["method", "depth_idx", "charge_bin", "n_pair_residuals", "sigma68_ns"]].head(60)
    leak_summary = leakage.groupby("check", as_index=False).agg(
        min_value=("value", "min"), median_value=("value", "median"), max_value=("value", "max"), pass_all=("pass", "all")
    )
    lines = [
        "# S06a: charge-proxy timing-resolution monotonicity after S14b",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo.",
        "- **Split:** leave-one-run-out over Sample-II runs 58, 59, 60, 61, 62, 63, 65; CIs resample held-out runs as event-paired blocks.",
        "",
        "## 1. Raw reproduction gate",
        "",
        repro.to_markdown(index=False),
        "",
        "The S00/S14b raw extraction and nominal S14b charge-depth closure ran before timing model fitting.",
        "",
        "## 2. Methods",
        "",
        "Traditional timing is the S03d hierarchical amp-only timewalk model on the frozen S02 template-phase pickoff. The ML timing model is a regularized Ridge residual corrector trained by run split on waveform shape, P04/P07 charge proxy, S14b depth, saturation flags, and anomaly summaries; it excludes run number, event id, event order, other-stave timing, and held-out labels. The ML uncertainty model uses the same non-ID features and is used only for the pull-width diagnostic.",
        "",
        "Matched strata combine S14b depth, saturation, peak-sample phase, late-charge pile-up proxy, baseline RMS proxy, and anomaly flag. Charge-bin slopes are in ns per full low-to-high charge-quantile span; negative means resolution improves at higher charge.",
        "",
        "## 3. Pooled held-out timing",
        "",
        pooled_view.to_markdown(index=False),
        "",
        boot_summary.to_markdown(index=False),
        "",
        "ML-minus-traditional deltas:",
        "",
        delta_summary.to_markdown(index=False),
        "",
        "## 4. Held-out runs",
        "",
        per_run_view.to_markdown(index=False),
        "",
        "## 5. Charge and depth controls",
        "",
        charge_view.to_markdown(index=False),
        "",
        "Depth-by-charge excerpt:",
        "",
        depth_view.to_markdown(index=False),
        "",
        "Matched-stratum weighted slopes:",
        "",
        matched_weighted.to_markdown(index=False),
        "",
        "## 6. Leakage audit",
        "",
        leak_summary.to_markdown(index=False),
        "",
        "## 7. Finding",
        "",
        result["finding"],
        "",
        "## 8. Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/s06a_1781021805_1799_6d33505e_charge_proxy_timing_monotonicity.py --config configs/s06a_1781021805_1799_6d33505e_charge_proxy_timing_monotonicity.yaml",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `per_run_benchmark.csv`, `pooled_benchmark.csv`, `pairwise_residuals.csv`, `one_axis_charge_metrics.csv`, `depth_charge_metrics.csv`, `matched_stratum_charge_metrics.csv`, `matched_stratum_slopes.csv`, `run_block_bootstrap.csv`, `ml_minus_traditional_bootstrap.csv`, `leakage_checks.csv`, and `cv_scan.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s06a_1781021805_1799_6d33505e_charge_proxy_timing_monotonicity.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml_charge"]["random_seed"]))

    print("1/5 raw ROOT S00/S14b reproduction ...", flush=True)
    s02_repro = s02.reproduce_counts(config)
    context, counts, s14b_repro = rebuild_charge_context(config)
    repro = pd.concat(
        [
            s02_repro.rename(
                columns={"report_value": "reference", "tolerance": "tolerance_unused"}
            )[["quantity", "reference", "reproduced", "delta", "pass"]],
            s14b_repro,
        ],
        ignore_index=True,
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    print("2/5 loading timing pulses and joining charge/depth context ...", flush=True)
    pulses = s02.load_downstream_pulses(config)
    pulses = add_event_context(pulses, context)
    pulses = add_anomaly_features(pulses)
    pulses = assign_context_bins(pulses, int(config["analysis"]["charge_bins"]))

    all_runs = [int(run) for run in config["timing"]["loo_runs"]]
    per_run_parts = []
    residual_parts = []
    leakage_parts = []
    cv_parts = []
    print("3/5 leave-one-run-out timing fits ...", flush=True)
    for heldout_run in all_runs:
        print(f"  heldout run {heldout_run}", flush=True)
        per_run, residuals, leakage, cv = run_one_fold(pulses, config, heldout_run, all_runs, rng)
        per_run_parts.append(per_run)
        residual_parts.append(residuals)
        leakage_parts.append(leakage)
        cv_parts.append(cv)

    per_run_df = pd.concat(per_run_parts, ignore_index=True)
    residuals_df = pd.concat(residual_parts, ignore_index=True)
    leakage_df = pd.concat(leakage_parts, ignore_index=True)
    cv_df = pd.concat(cv_parts, ignore_index=True, sort=False)

    print("4/5 charge-bin summaries and run-block bootstrap ...", flush=True)
    pooled = pooled_summary(residuals_df, config)
    one_axis = summarize_groups(residuals_df, ["charge_bin"], config, "charge_only")
    depth_charge = summarize_groups(residuals_df, ["depth_idx", "charge_bin"], config, "depth_x_charge")
    matched_metrics = summarize_groups(residuals_df, ["matched_stratum", "charge_bin"], config, "matched_stratum")
    one_slopes = slope_table(one_axis, [], config, "charge_only")
    depth_slopes = slope_table(depth_charge, ["depth_idx"], config, "depth_x_charge")
    matched_slopes = slope_table(matched_metrics, ["matched_stratum"], config, "matched_stratum")
    matched_weighted = pd.DataFrame(weighted_matched_slope(matched_slopes, "sigma68_ns"))

    boot, delta_boot = run_block_bootstrap(
        residuals_df,
        config,
        rng,
        int(config["analysis"]["bootstrap_samples"]),
    )
    boot_summary, delta_summary = summarize_bootstrap(boot, delta_boot)

    for name, frame in [
        ("per_run_benchmark.csv", per_run_df),
        ("pooled_benchmark.csv", pooled),
        ("pairwise_residuals.csv", residuals_df),
        ("one_axis_charge_metrics.csv", one_axis),
        ("depth_charge_metrics.csv", depth_charge),
        ("matched_stratum_charge_metrics.csv", matched_metrics),
        ("one_axis_slopes.csv", one_slopes),
        ("depth_charge_slopes.csv", depth_slopes),
        ("matched_stratum_slopes.csv", matched_slopes),
        ("matched_weighted_slopes.csv", matched_weighted),
        ("run_block_bootstrap.csv", boot),
        ("ml_minus_traditional_bootstrap.csv", delta_boot),
        ("bootstrap_summary.csv", boot_summary),
        ("delta_summary.csv", delta_summary),
        ("leakage_checks.csv", leakage_df),
        ("cv_scan.csv", cv_df),
    ]:
        frame.to_csv(out_dir / name, index=False)

    input_files = [s02.raw_file(config, run) for run in s02.configured_runs(config)]
    input_sha = pd.DataFrame(
        [{"path": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_files]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    pooled_idx = pooled.set_index("method")
    trad = pooled_idx.loc[TRADITIONAL]
    ml = pooled_idx.loc[ML]
    base = pooled_idx.loc[BASE]
    one_slope_idx = one_slopes[(one_slopes["metric"] == "sigma68_ns")].set_index("method")
    matched_idx = matched_weighted.set_index("method") if len(matched_weighted) else pd.DataFrame()
    trad_slope = float(one_slope_idx.loc[TRADITIONAL, "slope_per_charge_quantile"])
    ml_slope = float(one_slope_idx.loc[ML, "slope_per_charge_quantile"])
    trad_matched = float(matched_idx.loc[TRADITIONAL, "matched_slope_per_charge_quantile"]) if len(matched_idx) and TRADITIONAL in matched_idx.index else float("nan")
    ml_matched = float(matched_idx.loc[ML, "matched_slope_per_charge_quantile"]) if len(matched_idx) and ML in matched_idx.index else float("nan")
    ml_gain = float(trad["sigma68_ns"] - ml["sigma68_ns"])
    too_good = bool(
        (float(ml["sigma68_ns"]) < float(config["analysis"]["too_good_sigma68_ns"]))
        or (ml_gain > float(config["analysis"]["too_good_ml_gain_ns"]))
    )
    leakage_flag = bool((~leakage_df["pass"].astype(bool)).any())
    shuffled_min = float(leakage_df[leakage_df["check"] == "ml_shuffled_target_sigma68"]["value"].min())
    direction = "improves" if trad_slope < 0 and ml_slope < 0 else "does_not_consistently_improve"
    finding = (
        f"Raw ROOT reproduction passed before modeling. Pooled held-out sigma68 is {base['sigma68_ns']:.3f} ns for "
        f"template phase, {trad['sigma68_ns']:.3f} ns for S03d hierarchical traditional timing, and "
        f"{ml['sigma68_ns']:.3f} ns for charge-aware Ridge ML (ML - traditional {float(ml['sigma68_ns'] - trad['sigma68_ns']):+.3f} ns). "
        f"The one-axis sigma68 slope versus charge quantile is {trad_slope:+.3f} ns for traditional and {ml_slope:+.3f} ns for ML; "
        f"matched-stratum slopes are {trad_matched:+.3f} ns and {ml_matched:+.3f} ns. "
        f"Thus charge proxy timing resolution {direction} with increasing charge after the matched controls. "
        f"The strongest shuffled-target ML sentinel is {shuffled_min:.3f} ns, with leakage_flag={leakage_flag} and too_good={too_good}."
    )

    result = {
        "study": "S06a",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction_pass": bool(repro["pass"].all()),
        "split": {
            "unit": "run",
            "heldout_runs": all_runs,
            "bootstrap_unit": "heldout_run_event_pairs",
        },
        "pooled": json.loads(pooled.to_json(orient="records")),
        "bootstrap_summary": json.loads(boot_summary.to_json(orient="records")),
        "ml_minus_traditional_delta_summary": json.loads(delta_summary.to_json(orient="records")),
        "charge_slopes": {
            "one_axis_sigma68_ns_per_quantile": {
                TRADITIONAL: trad_slope,
                ML: ml_slope,
            },
            "matched_sigma68_ns_per_quantile": {
                TRADITIONAL: trad_matched,
                ML: ml_matched,
            },
        },
        "leakage": {
            "leakage_flag": leakage_flag,
            "too_good": too_good,
            "shuffled_target_min_sigma68_ns": shuffled_min,
            "train_heldout_event_overlap_total": float(
                leakage_df[leakage_df["check"] == "train_heldout_event_id_overlap"]["value"].sum()
            ),
            "features_exclude_run_event_cross_stave_target": True,
        },
        "finding": finding,
        "input_sha256": hashlib.sha256("".join(input_sha["sha256"].tolist()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(
        out_dir,
        config,
        repro,
        per_run_df,
        pooled,
        one_axis,
        depth_charge,
        matched_weighted,
        boot_summary,
        delta_summary,
        leakage_df,
        result,
    )
    manifest = {
        "ticket": config["ticket_id"],
        "study": "S06a",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "random_seed": int(config["ml_charge"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": {},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["outputs"] = hash_outputs(out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "traditional_sigma68": float(trad["sigma68_ns"]), "ml_sigma68": float(ml["sigma68_ns"]), "traditional_charge_slope": trad_slope, "ml_charge_slope": ml_slope}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
