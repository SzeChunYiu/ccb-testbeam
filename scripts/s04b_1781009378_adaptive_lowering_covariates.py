#!/usr/bin/env python3
"""S04b adaptive-lowering covariates for full timing-resolution tail tables."""

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
from typing import Dict, Iterable, List, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import numpy as np
import pandas as pd
import uproot
from scipy.optimize import curve_fit
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def analysis_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group in config["timing"]["analysis_groups"]:
        runs.extend(int(run) for run in config["run_groups"][group])
    return sorted(set(runs))


def run_sample(config: dict, run: int) -> str:
    for group in config["timing"]["analysis_groups"]:
        if int(run) in set(int(r) for r in config["run_groups"][group]):
            return group.replace("_analysis", "")
    return "other"


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    if not valid.any():
        return out
    idx = np.where(valid)[0]
    j = first[idx]
    prev = np.maximum(j - 1, 0)
    y0 = waveforms[idx, prev]
    y1 = waveforms[idx, j]
    denom = y1 - y0
    interp = prev.astype(float)
    good_interp = (j > 0) & (denom > 0)
    interp[good_interp] = prev[good_interp] + (threshold[idx][good_interp] - y0[good_interp]) / denom[good_interp]
    interp[~good_interp] = j[~good_interp].astype(float)
    out[idx] = interp
    return out


def geometry_positions(staves: Sequence[str], spacing_cm: float) -> Dict[str, float]:
    order = ["B2", "B4", "B6", "B8"]
    return {stave: order.index(stave) * float(spacing_cm) for stave in staves}


def jagged_mask(corrected: np.ndarray, amp: np.ndarray, cfg: dict) -> np.ndarray:
    params = cfg["jagged_mask"]
    mask = np.zeros(corrected.shape, dtype=bool)
    high = float(params["high_fraction"]) * amp[:, None]
    low = float(params["low_fraction"]) * amp[:, None]
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    jag = (left > high) & (right > high) & ((middle < low) | (middle < -float(params["negative_adc"])))
    mask[:, 1:-1] = jag
    return mask


def adaptive_pedestal(waveforms: np.ndarray, seed: np.ndarray, cfg: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    corrected = waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(
        float(cfg["negative_tolerance_adc"]["floor"]),
        float(cfg["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    exclude = jagged_mask(corrected, amp, cfg)
    eligible = np.where(exclude, np.inf, waveforms)
    min_allowed_source = eligible.min(axis=1)
    pedestal = np.minimum(seed, min_allowed_source + eps)
    lowering = seed - pedestal
    corrected_pc = waveforms - pedestal[:, None]
    min_margin = np.where(exclude, np.inf, corrected_pc).min(axis=1) + eps
    return pedestal, lowering, min_margin


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    total = 0
    by_group = {
        "sample_i_analysis": {k: 0 for k in ["selected_pulses", *stave_names]},
        "sample_ii_analysis": {k: 0 for k in ["selected_pulses", *stave_names]},
    }
    violations = 0
    for run in configured_runs(config):
        for batch in iter_raw(raw_file(config, run), ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw = events[:, channels, :]
            seed = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - seed[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            total += int(selected.sum())
            if selected.any():
                _, _, margin = adaptive_pedestal(raw[selected].reshape(-1, nsamp), seed[selected].reshape(-1), config)
                violations += int((margin < -1e-9).sum())
            for group in by_group:
                if run in config["run_groups"][group]:
                    by_group[group]["selected_pulses"] += int(selected.sum())
                    for i, stave in enumerate(stave_names):
                        by_group[group][stave] += int(selected[:, i].sum())
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        },
        {"quantity": "adaptive post-correction violations", "report_value": 0, "reproduced": int(violations), "tolerance": 0},
    ]
    for group in ["sample_i_analysis", "sample_ii_analysis"]:
        for key, value in config["expected_counts"][group].items():
            rows.append({"quantity": f"{group} {key}", "report_value": int(value), "reproduced": int(by_group[group][key]), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def load_analysis_pulses(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    period = float(config["sample_period_ns"])
    frac = float(config["timing"]["cfd_fraction"])
    frames = []
    for run in analysis_runs(config):
        sample = run_sample(config, run)
        event_uid_base = 0
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw = events[:, channels, :]
            seed = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - seed[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_mask = selected.sum(axis=1) >= 2
            if not event_mask.any():
                event_uid_base += len(eventno)
                continue
            idx = np.where(event_mask)[0]
            flat_raw = raw[idx].reshape(-1, nsamp)
            flat_seed = seed[idx].reshape(-1)
            _, lowering, margin = adaptive_pedestal(flat_raw, flat_seed, config)
            lowering = lowering.reshape(len(idx), len(stave_names))
            margin = margin.reshape(len(idx), len(stave_names))
            times = period * cfd_time_samples(corrected[idx].reshape(-1, nsamp), amplitude[idx].reshape(-1), frac)
            times = times.reshape(len(idx), len(stave_names))
            peak = corrected[idx].argmax(axis=-1)
            area = corrected[idx].sum(axis=-1)
            local_event_idx, stave_idx = np.where(selected[idx])
            if len(local_event_idx):
                source_event_idx = idx[local_event_idx]
                event_ids = np.asarray(
                    [f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_uid_base + int(e)}" for e in idx],
                    dtype=object,
                )
                amp_vals = amplitude[idx][local_event_idx, stave_idx].astype(float)
                frame = pd.DataFrame(
                    {
                        "event_id": event_ids[local_event_idx],
                        "run": int(run),
                        "sample": sample,
                        "eventno": eventno[source_event_idx].astype(int),
                        "evt": evt[source_event_idx].astype(int),
                        "stave": np.asarray(stave_names, dtype=object)[stave_idx],
                        "t_cfd20_ns": times[local_event_idx, stave_idx].astype(float),
                        "amplitude_adc": amp_vals,
                        "peak_sample": peak[local_event_idx, stave_idx].astype(int),
                        "area_adc_samples": area[local_event_idx, stave_idx].astype(float),
                        "adaptive_lowering_adc": lowering[local_event_idx, stave_idx].astype(float),
                        "adaptive_margin_adc": margin[local_event_idx, stave_idx].astype(float),
                        "lowering_frac_amp": lowering[local_event_idx, stave_idx].astype(float) / np.maximum(amp_vals, 1.0),
                    }
                )
                frames.append(frame)
            event_uid_base += len(eventno)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_pair_table(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    staves = list(config["staves"].keys())
    positions = geometry_positions(staves, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses.copy()
    sub["tcorr"] = sub["t_cfd20_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    rows = []
    for left, right in config["timing"]["pairs"]:
        lframe = sub[sub["stave"] == left]
        rframe = sub[sub["stave"] == right]
        if lframe.empty or rframe.empty:
            continue
        keep = [
            "event_id",
            "run",
            "sample",
            "eventno",
            "evt",
            "tcorr",
            "adaptive_lowering_adc",
            "lowering_frac_amp",
            "amplitude_adc",
            "peak_sample",
            "area_adc_samples",
        ]
        merged = lframe[keep].merge(rframe[["event_id", "tcorr", "adaptive_lowering_adc", "lowering_frac_amp", "amplitude_adc", "peak_sample", "area_adc_samples"]], on="event_id", suffixes=("_a", "_b"))
        if merged.empty:
            continue
        aa = merged["amplitude_adc_a"].to_numpy(dtype=float)
        ab = merged["amplitude_adc_b"].to_numpy(dtype=float)
        la = merged["adaptive_lowering_adc_a"].to_numpy(dtype=float)
        lb = merged["adaptive_lowering_adc_b"].to_numpy(dtype=float)
        frame = pd.DataFrame(
            {
                "event_id": merged["event_id"].to_numpy(),
                "run": merged["run"].to_numpy(dtype=int),
                "sample": merged["sample"].to_numpy(),
                "eventno": merged["eventno"].to_numpy(dtype=int),
                "evt": merged["evt"].to_numpy(dtype=int),
                "pair": f"{left}-{right}",
                "stave_a": left,
                "stave_b": right,
                "residual_ns": merged["tcorr_a"].to_numpy(dtype=float) - merged["tcorr_b"].to_numpy(dtype=float),
                "delta_lowering_adc": la - lb,
                "abs_delta_lowering_adc": np.abs(la - lb),
                "max_lowering_adc": np.maximum(la, lb),
                "sum_lowering_adc": la + lb,
                "delta_lowering_frac": merged["lowering_frac_amp_a"].to_numpy(dtype=float) - merged["lowering_frac_amp_b"].to_numpy(dtype=float),
                "max_lowering_frac": np.maximum(merged["lowering_frac_amp_a"].to_numpy(dtype=float), merged["lowering_frac_amp_b"].to_numpy(dtype=float)),
                "delta_log_amp": np.log1p(aa) - np.log1p(ab),
                "min_log_amp": np.minimum(np.log1p(aa), np.log1p(ab)),
                "max_log_amp": np.maximum(np.log1p(aa), np.log1p(ab)),
                "delta_peak_sample": merged["peak_sample_a"].to_numpy(dtype=float) - merged["peak_sample_b"].to_numpy(dtype=float),
                "delta_area_over_amp": merged["area_adc_samples_a"].to_numpy(dtype=float) / np.maximum(aa, 1.0) - merged["area_adc_samples_b"].to_numpy(dtype=float) / np.maximum(ab, 1.0),
            }
        )
        rows.append(frame)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if out.empty:
        raise RuntimeError("no pair residuals found")
    out["lowering_bin"] = pd.cut(
        out["max_lowering_adc"],
        bins=[-np.inf, 0.0, 250.0, 800.0, np.inf],
        labels=["none", "small", "medium", "large"],
        right=True,
    ).astype(str)
    return out[np.isfinite(out["residual_ns"])].reset_index(drop=True)


def center_by_train(train: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    med = train.groupby(["sample", "pair"])["residual_ns"].median()
    global_med = float(train["residual_ns"].median())
    keys = list(zip(frame["sample"], frame["pair"]))
    centers = np.asarray([float(med.get(key, global_med)) for key in keys], dtype=float)
    return frame["residual_ns"].to_numpy(dtype=float) - centers


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def gaussian_const(x: np.ndarray, amp: float, mu: float, sigma: float, const: float) -> np.ndarray:
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2) + const


def gaussian_core_fit(values: np.ndarray, config: dict) -> Dict[str, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 30:
        return {"core_sigma_ns": math.nan, "core_mu_ns": math.nan, "core_chi2_ndf": math.nan}
    centered = values - float(np.median(values))
    lim = float(config["timing"]["core_fit_range_ns"])
    core = centered[np.abs(centered) <= lim]
    if len(core) < 30:
        return {"core_sigma_ns": math.nan, "core_mu_ns": math.nan, "core_chi2_ndf": math.nan}
    counts, edges = np.histogram(core, bins=int(config["timing"]["core_fit_bins"]), range=(-lim, lim))
    x = 0.5 * (edges[:-1] + edges[1:])
    sigma_y = np.sqrt(np.maximum(counts, 1.0))
    try:
        p0 = [max(float(counts.max()), 1.0), 0.0, max(sigma68(core), 0.2), max(float(np.median(counts)), 0.0)]
        popt, _ = curve_fit(gaussian_const, x, counts, p0=p0, sigma=sigma_y, absolute_sigma=True, bounds=([0, -lim, 0.05, 0], [np.inf, lim, lim, np.inf]), maxfev=20000)
        expected = gaussian_const(x, *popt)
        chi2 = float(np.sum(((counts - expected) / sigma_y) ** 2))
        ndf = max(len(counts) - len(popt), 1)
        return {"core_sigma_ns": float(abs(popt[2])), "core_mu_ns": float(popt[1]), "core_chi2_ndf": chi2 / ndf}
    except Exception:
        return {"core_sigma_ns": math.nan, "core_mu_ns": math.nan, "core_chi2_ndf": math.nan}


def metric_summary(frame: pd.DataFrame, residual_col: str, config: dict) -> Dict[str, float]:
    vals = frame[residual_col].to_numpy(dtype=float)
    vals = vals[np.isfinite(vals)]
    med = float(np.median(vals)) if len(vals) else float("nan")
    centered = vals - med
    out = {
        "n_pair_residuals": int(len(vals)),
        "n_events": int(frame["event_id"].nunique()) if len(frame) else 0,
        "n_runs": int(frame["run"].nunique()) if len(frame) else 0,
        "median_ns": med,
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": float(np.sqrt(np.mean(centered**2))) if len(vals) else float("nan"),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > float(config["timing"]["tail_abs_residual_ns"]))) if len(vals) else float("nan"),
        "mae_ns": float(np.mean(np.abs(centered))) if len(vals) else float("nan"),
    }
    out.update(gaussian_core_fit(vals, config))
    return out


def run_event_bootstrap(frame: pd.DataFrame, residual_col: str, config: dict, rng: np.random.Generator) -> Dict[str, float]:
    if frame.empty:
        return {"sigma68_ci_low": math.nan, "sigma68_ci_high": math.nan, "tail_ci_low": math.nan, "tail_ci_high": math.nan, "full_rms_ci_low": math.nan, "full_rms_ci_high": math.nan}
    local = frame[["run", "event_id"]].reset_index(drop=True)
    values = frame[residual_col].to_numpy(dtype=float)
    by_run: Dict[int, List[np.ndarray]] = {}
    for (run, _event_id), positions in local.groupby(["run", "event_id"]).indices.items():
        by_run.setdefault(int(run), []).append(np.asarray(positions, dtype=int))
    runs = np.asarray(sorted(by_run), dtype=int)
    sigma_stats = []
    tail_stats = []
    rms_stats = []
    for _ in range(int(config["ml"]["bootstrap_samples"])):
        pieces: List[np.ndarray] = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            events = by_run[int(run)]
            chosen = rng.choice(np.arange(len(events)), size=len(events), replace=True)
            pieces.extend(events[int(i)] for i in chosen)
        sample_values = values[np.concatenate(pieces)]
        med = float(np.median(sample_values))
        centered = sample_values - med
        sigma_stats.append(sigma68(sample_values))
        tail_stats.append(float(np.mean(np.abs(centered) > float(config["timing"]["tail_abs_residual_ns"]))))
        rms_stats.append(float(np.sqrt(np.mean(centered**2))))
    return {
        "sigma68_ci_low": float(np.percentile(sigma_stats, 2.5)),
        "sigma68_ci_high": float(np.percentile(sigma_stats, 97.5)),
        "tail_ci_low": float(np.percentile(tail_stats, 2.5)),
        "tail_ci_high": float(np.percentile(tail_stats, 97.5)),
        "full_rms_ci_low": float(np.percentile(rms_stats, 2.5)),
        "full_rms_ci_high": float(np.percentile(rms_stats, 97.5)),
    }


NUMERIC_FEATURES = [
    "delta_lowering_adc",
    "abs_delta_lowering_adc",
    "max_lowering_adc",
    "sum_lowering_adc",
    "delta_lowering_frac",
    "max_lowering_frac",
    "delta_log_amp",
    "min_log_amp",
    "max_log_amp",
    "delta_peak_sample",
    "delta_area_over_amp",
]
CATEGORICAL_FEATURES = ["pair", "sample", "lowering_bin"]
TRAD_FEATURES = ["delta_lowering_adc", "abs_delta_lowering_adc", "max_lowering_adc", "sum_lowering_adc", "delta_log_amp", "delta_peak_sample", "pair", "sample"]
ML_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def make_preprocessor(feature_cols: List[str]) -> ColumnTransformer:
    numeric = [c for c in feature_cols if c not in CATEGORICAL_FEATURES]
    categorical = [c for c in feature_cols if c in CATEGORICAL_FEATURES]
    return ColumnTransformer([("num", StandardScaler(), numeric), ("cat", OneHotEncoder(handle_unknown="ignore"), categorical)])


def rf_model(config: dict, seed: int) -> RandomForestRegressor:
    params = config["ml"]["random_forest"]
    return RandomForestRegressor(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        random_state=int(seed),
        n_jobs=1,
    )


def fit_oof_models(pairs: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    out = pairs.copy()
    out["residual_traditional_corrected_ns"] = np.nan
    out["residual_ml_corrected_ns"] = np.nan
    out["residual_ml_shuffled_corrected_ns"] = np.nan
    out["residual_ml_oracle_corrected_ns"] = np.nan
    groups = out["run"].to_numpy(dtype=int)
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    fold_rows = []
    for fold, (tr, va) in enumerate(GroupKFold(n_splits=n_splits).split(out, groups=groups), start=1):
        train = out.iloc[tr].copy()
        valid = out.iloc[va].copy()
        y_train = center_by_train(train, train)
        y_valid_raw = valid["residual_ns"].to_numpy(dtype=float)

        trad = make_pipeline(make_preprocessor(TRAD_FEATURES), Ridge(alpha=float(config["traditional"]["ridge_alpha"])))
        trad.fit(train[TRAD_FEATURES], y_train)
        trad_pred = trad.predict(valid[TRAD_FEATURES])
        out.loc[out.index[va], "residual_traditional_corrected_ns"] = y_valid_raw - trad_pred

        ml = make_pipeline(make_preprocessor(ML_FEATURES), rf_model(config, int(config["ml"]["random_seed"]) + fold))
        ml.fit(train[ML_FEATURES], y_train)
        ml_pred = ml.predict(valid[ML_FEATURES])
        out.loc[out.index[va], "residual_ml_corrected_ns"] = y_valid_raw - ml_pred

        shuffled = rng.permutation(y_train)
        shuf = make_pipeline(make_preprocessor(ML_FEATURES), rf_model(config, int(config["ml"]["random_seed"]) + 100 + fold))
        shuf.fit(train[ML_FEATURES], shuffled)
        out.loc[out.index[va], "residual_ml_shuffled_corrected_ns"] = y_valid_raw - shuf.predict(valid[ML_FEATURES])

        leaky_cols = ML_FEATURES + ["centered_oracle_ns"]
        train = train.assign(centered_oracle_ns=y_train)
        valid = valid.assign(centered_oracle_ns=center_by_train(train, valid))
        oracle = make_pipeline(make_preprocessor(leaky_cols), rf_model(config, int(config["ml"]["random_seed"]) + 200 + fold))
        oracle.fit(train[leaky_cols], train["centered_oracle_ns"])
        out.loc[out.index[va], "residual_ml_oracle_corrected_ns"] = y_valid_raw - oracle.predict(valid[leaky_cols])

        fold_rows.append(
            {
                "fold": fold,
                "heldout_runs": ",".join(str(r) for r in sorted(valid["run"].unique())),
                "train_rows": int(len(train)),
                "heldout_rows": int(len(valid)),
                "raw_sigma68_ns": sigma68(center_by_train(train, valid)),
                "traditional_sigma68_ns": sigma68(out.loc[out.index[va], "residual_traditional_corrected_ns"].to_numpy(dtype=float)),
                "ml_sigma68_ns": sigma68(out.loc[out.index[va], "residual_ml_corrected_ns"].to_numpy(dtype=float)),
            }
        )

    row_scores = []
    kfold = KFold(n_splits=5, shuffle=True, random_state=int(config["ml"]["random_seed"]) + 300)
    for tr, va in kfold.split(out):
        train = out.iloc[tr].copy()
        valid = out.iloc[va].copy()
        y_train = center_by_train(train, train)
        ml = make_pipeline(make_preprocessor(ML_FEATURES), rf_model(config, int(config["ml"]["random_seed"]) + 301))
        ml.fit(train[ML_FEATURES], y_train)
        corrected = valid["residual_ns"].to_numpy(dtype=float) - ml.predict(valid[ML_FEATURES])
        row_scores.append(sigma68(corrected))

    fold_df = pd.DataFrame(fold_rows)
    cv_df = pd.DataFrame(
        [
            {
                "run_cv_raw_sigma68_ns": float(fold_df["raw_sigma68_ns"].mean()),
                "run_cv_traditional_sigma68_ns": float(fold_df["traditional_sigma68_ns"].mean()),
                "run_cv_ml_sigma68_ns": float(fold_df["ml_sigma68_ns"].mean()),
                "row_cv_ml_sigma68_ns": float(np.mean(row_scores)),
                "row_minus_run_cv_ml_sigma68_ns": float(np.mean(row_scores) - fold_df["ml_sigma68_ns"].mean()),
            }
        ]
    )
    return out, fold_df, cv_df


def benchmark_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    residual_cols = [
        ("raw_cfd20", "residual_ns"),
        ("traditional_ridge_lowering", "residual_traditional_corrected_ns"),
        ("ml_rf_lowering", "residual_ml_corrected_ns"),
        ("ml_shuffled_target_control", "residual_ml_shuffled_corrected_ns"),
        ("ml_intentional_residual_oracle", "residual_ml_oracle_corrected_ns"),
    ]
    for sample, sframe in oof.groupby("sample"):
        for method, col in residual_cols:
            rows.append({"sample": sample, "method": method, **metric_summary(sframe, col, config), **run_event_bootstrap(sframe, col, config, rng)})
    for method, col in residual_cols:
        rows.append({"sample": "pooled", "method": method, **metric_summary(oof, col, config), **run_event_bootstrap(oof, col, config, rng)})
    return pd.DataFrame(rows)


def tail_tables(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    tail_config = json.loads(json.dumps(config))
    tail_config["ml"]["bootstrap_samples"] = min(int(config["ml"]["bootstrap_samples"]), 120)
    residual_cols = [
        ("raw_cfd20", "residual_ns"),
        ("traditional_ridge_lowering", "residual_traditional_corrected_ns"),
        ("ml_rf_lowering", "residual_ml_corrected_ns"),
    ]
    for keys, sub in oof.groupby(["sample", "pair", "lowering_bin"], dropna=False):
        if len(sub) < 20:
            continue
        sample, pair, lowering_bin = keys
        for method, col in residual_cols:
            rows.append({"sample": sample, "pair": pair, "lowering_bin": lowering_bin, "method": method, **metric_summary(sub, col, config), **run_event_bootstrap(sub, col, tail_config, rng)})
    return pd.DataFrame(rows)


def heldout_by_run(oof: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for (run, sample), sub in oof.groupby(["run", "sample"]):
        for method, col in [
            ("raw_cfd20", "residual_ns"),
            ("traditional_ridge_lowering", "residual_traditional_corrected_ns"),
            ("ml_rf_lowering", "residual_ml_corrected_ns"),
        ]:
            rows.append({"run": int(run), "sample": sample, "method": method, **metric_summary(sub, col, config)})
    return pd.DataFrame(rows)


def downstream_variance_table(oof: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for sample, sub in oof[oof["pair"].isin(["B4-B6", "B4-B8", "B6-B8"])].groupby("sample"):
        sig = {pair: sigma68(pframe["residual_ns"].to_numpy(dtype=float)) for pair, pframe in sub.groupby("pair")}
        if not {"B4-B6", "B4-B8", "B6-B8"}.issubset(sig):
            continue
        s46, s48, s68 = sig["B4-B6"], sig["B4-B8"], sig["B6-B8"]
        variances = {
            "B4": 0.5 * (s46**2 + s48**2 - s68**2),
            "B6": 0.5 * (s46**2 + s68**2 - s48**2),
            "B8": 0.5 * (s48**2 + s68**2 - s46**2),
        }
        for stave, var in variances.items():
            rows.append({"sample": sample, "stave": stave, "s04_downstream_exact_sigma68_ns": math.sqrt(var) if var > 0 else math.nan})
    return pd.DataFrame(rows)


def leakage_checks(oof: pd.DataFrame, bench: pd.DataFrame, cv: pd.DataFrame) -> pd.DataFrame:
    raw = bench[(bench["sample"] == "pooled") & (bench["method"] == "raw_cfd20")].iloc[0]
    ml = bench[(bench["sample"] == "pooled") & (bench["method"] == "ml_rf_lowering")].iloc[0]
    shuffled = bench[(bench["sample"] == "pooled") & (bench["method"] == "ml_shuffled_target_control")].iloc[0]
    oracle = bench[(bench["sample"] == "pooled") & (bench["method"] == "ml_intentional_residual_oracle")].iloc[0]
    forbidden = {"run", "event_id", "eventno", "evt", "residual_ns", "centered_residual_ns", "tail_abs_gt_threshold"}
    feature_overlap = set(ML_FEATURES) & forbidden
    return pd.DataFrame(
        [
            {"check": "all_predictions_are_run_heldout_oof", "value": int(oof["run"].nunique()), "pass": bool(np.isfinite(oof["residual_ml_corrected_ns"]).all())},
            {"check": "ml_features_exclude_identifiers_and_labels", "value": ",".join(sorted(feature_overlap)), "pass": len(feature_overlap) == 0},
            {"check": "shuffled_target_not_better_than_actual_ml", "value": float(shuffled["sigma68_ns"] - ml["sigma68_ns"]), "pass": bool(shuffled["sigma68_ns"] >= ml["sigma68_ns"])},
            {"check": "intentional_oracle_is_obviously_leaky", "value": float(oracle["sigma68_ns"]), "pass": bool(oracle["sigma68_ns"] < ml["sigma68_ns"])},
            {"check": "row_cv_not_much_better_than_run_cv", "value": float(cv.iloc[0]["run_cv_ml_sigma68_ns"] - cv.iloc[0]["row_cv_ml_sigma68_ns"]), "pass": bool((cv.iloc[0]["run_cv_ml_sigma68_ns"] - cv.iloc[0]["row_cv_ml_sigma68_ns"]) < 1.0)},
            {"check": "actual_ml_improvement_under_raw_one_ns", "value": float(raw["sigma68_ns"] - ml["sigma68_ns"]), "pass": bool((raw["sigma68_ns"] - ml["sigma68_ns"]) < 1.0)},
        ]
    )


def format_reproduction(match: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.quantity} | {int(r.report_value)} | {int(r.reproduced)} | {int(r.delta)} | {'yes' if bool(r.pass_) else 'no'} |"
        for r in match.rename(columns={"pass": "pass_"}).itertuples()
    )


def format_benchmark(bench: pd.DataFrame) -> str:
    rows = []
    shown = bench[(bench["sample"] == "pooled") & (~bench["method"].str.contains("oracle"))]
    for r in shown.itertuples():
        rows.append(
            f"| {r.method} | {r.sigma68_ns:.3f} [{r.sigma68_ci_low:.3f}, {r.sigma68_ci_high:.3f}] | "
            f"{r.tail_frac_abs_gt5ns:.3f} [{r.tail_ci_low:.3f}, {r.tail_ci_high:.3f}] | "
            f"{r.full_rms_ns:.3f} [{r.full_rms_ci_low:.3f}, {r.full_rms_ci_high:.3f}] | {r.core_sigma_ns:.3f} | {r.core_chi2_ndf:.2f} | {int(r.n_pair_residuals)} |"
        )
    return "\n".join(rows)


def format_sample_rows(bench: pd.DataFrame) -> str:
    rows = []
    shown = bench[(bench["sample"] != "pooled") & (bench["method"].isin(["raw_cfd20", "ml_rf_lowering"]))]
    for r in shown.itertuples():
        rows.append(f"| {r.sample} | {r.method} | {r.sigma68_ns:.3f} | {r.tail_frac_abs_gt5ns:.3f} | {r.full_rms_ns:.3f} | {int(r.n_pair_residuals)} |")
    return "\n".join(rows)


def format_worst_tail_rows(tails: pd.DataFrame) -> str:
    if tails.empty:
        return ""
    raw = tails[tails["method"] == "raw_cfd20"].sort_values("tail_frac_abs_gt5ns", ascending=False).head(8)
    return "\n".join(
        f"| {r.sample} | {r.pair} | {r.lowering_bin} | {int(r.n_pair_residuals)} | {r.sigma68_ns:.3f} | {r.tail_frac_abs_gt5ns:.3f} | {r.full_rms_ns:.3f} |"
        for r in raw.itertuples()
    )


def format_leakage(checks: pd.DataFrame) -> str:
    return "\n".join(f"| {r.check} | {r.value} | {'yes' if bool(r.pass_) else 'no'} |" for r in checks.rename(columns={"pass": "pass_"}).itertuples())


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    report = f"""# S04b: adaptive-lowering covariates in full timing-resolution tail tables

- **Ticket:** {config["ticket"]}
- **Author:** {config["worker"]}
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `s04b_1781009378_adaptive_lowering_covariates.json`

## Question

Should adaptive-pedestal lowering enter the full S04 timing-resolution systematic tables as a nuisance covariate?

## Raw-ROOT Reproduction First

The script first rescans `h101/HRDv` from raw B-stack ROOT, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
{numbers["reproduction_rows"]}

The full timing table then uses every Sample-I and Sample-II analysis event with at least two selected B staves, producing `{numbers["pair_rows"]}` pair residuals across `{numbers["runs"]}` held-out-by-run folds.

## Methods

The traditional method is the S04-style CFD20 inter-stave table after the 2 cm TOF correction: narrow-core Gaussian+constant sigma with chi2/ndf, sigma68, full RMS, abs(residual)>5 ns tail fraction, and adaptive-lowering strata. A Ridge residual correction on signed/absolute/summed lowering, log-amplitude and peak-sample differences, pair, and sample is included only as an interpretable nuisance-correction stress test.

The ML method is a random-forest residual corrector using the same lowering terms plus fractional lowering, amplitude, area/peak, pair, sample, and lowering-bin features. Every prediction is out-of-fold with folds grouped by run. Bootstrap CIs resample held-out runs and then events within sampled runs.

## Held-out Pooled Benchmark

| Method | sigma68 ns [95% CI] | tail frac [95% CI] | full RMS ns [95% CI] | core sigma ns | chi2/ndf | n pairs |
|---|---:|---:|---:|---:|---:|---:|
{numbers["benchmark_rows"]}

## Sample Split

| Sample | Method | sigma68 ns | tail frac | full RMS ns | n pairs |
|---|---|---:|---:|---:|---:|
{numbers["sample_rows"]}

## Worst Raw Tail Strata

| Sample | Pair | Lowering bin | n pairs | sigma68 ns | tail frac | full RMS ns |
|---|---|---|---:|---:|---:|---:|
{numbers["worst_tail_rows"]}

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
{numbers["leakage_rows"]}

## Verdict

{numbers["verdict"]}

## Reproducibility

```bash
python scripts/s04b_1781009378_adaptive_lowering_covariates.py --config configs/s04b_1781009378_adaptive_lowering_covariates.json
```

Artifacts: `reproduction_match_table.csv`, `pair_residuals_oof.csv`, `fold_metrics.csv`, `ml_cv_scan.csv`, `head_to_head_benchmark.csv`, `tail_tables.csv`, `heldout_by_run.csv`, `downstream_variance_reproduction.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def output_hashes(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    print("stage=reproduce_counts", flush=True)
    match = reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    print("stage=load_analysis_pulses", flush=True)
    pulses = load_analysis_pulses(config)
    print(f"stage=build_pair_table pulses={len(pulses)}", flush=True)
    pair_frame = build_pair_table(pulses, config)
    print(f"stage=fit_oof_models pairs={len(pair_frame)}", flush=True)
    oof, folds, cv = fit_oof_models(pair_frame, config, rng)
    oof.to_csv(out_dir / "pair_residuals_oof.csv", index=False)
    folds.to_csv(out_dir / "fold_metrics.csv", index=False)
    cv.to_csv(out_dir / "ml_cv_scan.csv", index=False)

    print("stage=benchmark_tables", flush=True)
    bench = benchmark_table(oof, config, rng)
    bench.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    tails = tail_tables(oof, config, rng)
    tails.to_csv(out_dir / "tail_tables.csv", index=False)
    by_run = heldout_by_run(oof, config)
    by_run.to_csv(out_dir / "heldout_by_run.csv", index=False)
    variance = downstream_variance_table(oof, config)
    variance.to_csv(out_dir / "downstream_variance_reproduction.csv", index=False)
    checks = leakage_checks(oof, bench, cv)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    pd.DataFrame([{"run": run, "path": str(raw_file(config, run)), "sha256": input_hashes[str(raw_file(config, run))]} for run in configured_runs(config)]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    raw = bench[(bench["sample"] == "pooled") & (bench["method"] == "raw_cfd20")].iloc[0]
    trad = bench[(bench["sample"] == "pooled") & (bench["method"] == "traditional_ridge_lowering")].iloc[0]
    ml = bench[(bench["sample"] == "pooled") & (bench["method"] == "ml_rf_lowering")].iloc[0]
    large = tails[(tails["method"] == "raw_cfd20") & (tails["lowering_bin"] == "large")]
    nonlarge = tails[(tails["method"] == "raw_cfd20") & (tails["lowering_bin"].isin(["none", "small", "medium"]))]
    large_tail = float(np.average(large["tail_frac_abs_gt5ns"], weights=large["n_pair_residuals"])) if not large.empty else math.nan
    nonlarge_tail = float(np.average(nonlarge["tail_frac_abs_gt5ns"], weights=nonlarge["n_pair_residuals"])) if not nonlarge.empty else math.nan
    trad_gain = float(raw["sigma68_ns"] - trad["sigma68_ns"])
    ml_gain = float(raw["sigma68_ns"] - ml["sigma68_ns"])
    if np.isfinite(large_tail) and large_tail > nonlarge_tail * 2.0 and ml_gain < 0.5:
        verdict = (
            f"Adaptive lowering should enter S04 tail/systematic tables as a stratifying nuisance covariate, not as a correction. "
            f"Large-lowering strata have weighted raw tail fraction {large_tail:.3f} versus {nonlarge_tail:.3f} elsewhere, "
            f"while the ML residual correction gains only {ml_gain:.3f} ns and the Ridge nuisance correction worsens sigma68 by {-trad_gain:.3f} ns."
        )
    elif ml_gain >= 0.5:
        verdict = (
            f"Adaptive lowering should enter S04 both as a covariate and candidate ML residual correction: pooled sigma68 ML gain is "
            f"{ml_gain:.3f} ns, while the Ridge nuisance correction gain is {trad_gain:.3f} ns."
        )
    else:
        verdict = (
            f"Adaptive lowering has weak pooled correction value and only modest tail stratification: weighted large-lowering tail "
            f"{large_tail:.3f} versus {nonlarge_tail:.3f}, ML gain {ml_gain:.3f} ns and Ridge nuisance gain {trad_gain:.3f} ns."
        )

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "conclusion": verdict,
        "raw_reproduction_pass": bool(match["pass"].all()),
        "analysis_runs": analysis_runs(config),
        "pair_residuals": int(len(oof)),
        "traditional": {
            "method": "CFD20 S04-style Gaussian-core/tail table stratified by adaptive lowering",
            "sigma68_ns": float(raw["sigma68_ns"]),
            "ci": [float(raw["sigma68_ci_low"]), float(raw["sigma68_ci_high"])],
            "tail_frac_abs_gt5ns": float(raw["tail_frac_abs_gt5ns"]),
            "full_rms_ns": float(raw["full_rms_ns"]),
            "core_sigma_ns": float(raw["core_sigma_ns"]),
            "core_chi2_ndf": float(raw["core_chi2_ndf"])
        },
        "traditional_nuisance_stress_test": {
            "method": "run-held-out Ridge residual correction on adaptive-lowering nuisance features",
            "sigma68_ns": float(trad["sigma68_ns"]),
            "ci": [float(trad["sigma68_ci_low"]), float(trad["sigma68_ci_high"])],
            "tail_frac_abs_gt5ns": float(trad["tail_frac_abs_gt5ns"]),
            "gain_vs_raw_ns": trad_gain
        },
        "ml": {
            "method": "run-held-out RandomForestRegressor residual correction",
            "sigma68_ns": float(ml["sigma68_ns"]),
            "ci": [float(ml["sigma68_ci_low"]), float(ml["sigma68_ci_high"])],
            "tail_frac_abs_gt5ns": float(ml["tail_frac_abs_gt5ns"]),
            "gain_vs_raw_ns": ml_gain
        },
        "raw_reference": {
            "method": "CFD20 S04-style pair residual table",
            "sigma68_ns": float(raw["sigma68_ns"]),
            "ci": [float(raw["sigma68_ci_low"]), float(raw["sigma68_ci_high"])],
            "tail_frac_abs_gt5ns": float(raw["tail_frac_abs_gt5ns"]),
            "full_rms_ns": float(raw["full_rms_ns"]),
            "core_sigma_ns": float(raw["core_sigma_ns"]),
            "core_chi2_ndf": float(raw["core_chi2_ndf"])
        },
        "large_lowering_weighted_tail_fraction": None if not np.isfinite(large_tail) else large_tail,
        "nonlarge_lowering_weighted_tail_fraction": None if not np.isfinite(nonlarge_tail) else nonlarge_tail,
        "leakage_checks_pass": bool(checks["pass"].all()),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": []
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    numbers = {
        "git_commit": git_commit(),
        "reproduction_rows": format_reproduction(match),
        "pair_rows": int(len(oof)),
        "runs": int(oof["run"].nunique()),
        "benchmark_rows": format_benchmark(bench),
        "sample_rows": format_sample_rows(bench),
        "worst_tail_rows": format_worst_tail_rows(tails),
        "leakage_rows": format_leakage(checks),
        "verdict": verdict,
    }
    write_report(out_dir, config, numbers)

    config_copy = out_dir / args.config.name
    config_copy.write_text(json.dumps(config, indent=2), encoding="utf-8")
    script_copy = out_dir / Path(__file__).name
    script_copy.write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": " ".join([sys.executable] + sys.argv),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "raw_sigma68": float(raw["sigma68_ns"]), "traditional_sigma68": float(trad["sigma68_ns"]), "ml_sigma68": float(ml["sigma68_ns"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
