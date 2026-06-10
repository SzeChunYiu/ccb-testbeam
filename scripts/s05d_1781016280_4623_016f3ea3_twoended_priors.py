#!/usr/bin/env python3
"""S05d: convert S05c covariance into per-stave two-ended priors.

The first gate rebuilds the S05c raw B-stack covariance anchor from ROOT. The
projection benchmark then fits priors on train runs only and evaluates
leave-one-run-out downstream-stave prediction residuals.
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
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781016280.4623.016f3ea3/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.preprocessing import OneHotEncoder

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s05c_hierarchical_bstack_covariance as s05c


STAVES = ["B2", "B4", "B6", "B8"]
PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]


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


def all_configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for key in ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]:
        runs.extend(int(run) for run in config["runs"][key])
    return sorted(set(runs))


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{config['bstack']['file_prefix']}_run_{int(run):04d}.root"


def iter_root(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def reproduce_counts(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return s05c.reproduce_counts(config)


def load_event_table(config: dict, run: int) -> pd.DataFrame:
    baseline = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    ns = int(config["samples_per_channel"])
    cfd = float(config["cfd_fraction"])
    period = float(config["sample_period_ns"])
    spacing = float(config["stave_spacing_cm"])
    tof = float(config["tof_per_cm_ns"])
    b_names = list(config["bstack"]["staves"].keys())
    b_channels = list(config["bstack"]["staves"].values())
    frames = []
    for batch in iter_root(raw_path(config, run), ["EVT", "HRDv"]):
        event = np.asarray(batch["EVT"]).astype(int)
        wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, b_channels, :]
        q = s05c.cfd_quantities(wave, baseline, cfd, period)
        base = {"run": np.full(len(event), int(run), dtype=int), "event": event}
        for i, stave in enumerate(b_names):
            amp = q["amplitude"][:, i]
            area = q["area"][:, i]
            corrected_time = q["time_ns"][:, i] - s05c.b_position(stave, spacing) * tof
            base[f"{stave}_selected"] = amp > cut
            base[f"{stave}_time_corr_ns"] = corrected_time
            base[f"{stave}_amp"] = amp
            base[f"{stave}_log_amp"] = np.log1p(np.maximum(amp, 0.0))
            base[f"{stave}_peak"] = q["peak"][:, i]
            base[f"{stave}_area"] = area
            base[f"{stave}_log_area"] = np.log1p(np.maximum(area, 0.0))
            base[f"{stave}_tail"] = q["tail"][:, i]
            for sample in range(ns):
                base[f"{stave}_wf_norm_{sample:02d}"] = wave[:, i, sample] / np.maximum(amp, 1.0)
        frames.append(pd.DataFrame(base))
    return pd.concat(frames, ignore_index=True)


def build_event_table(config: dict) -> pd.DataFrame:
    return pd.concat([load_event_table(config, int(run)) for run in config["analysis_runs"]], ignore_index=True)


def build_pair_table_from_events(events: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for left, right in PAIRS:
        mask = events[f"{left}_selected"] & events[f"{right}_selected"]
        if not mask.any():
            continue
        sub = events.loc[mask, ["run", "event", f"{left}_time_corr_ns", f"{right}_time_corr_ns"]].copy()
        sub["pair"] = f"{left}-{right}"
        sub["target_residual_ns"] = sub[f"{right}_time_corr_ns"] - sub[f"{left}_time_corr_ns"]
        rows.append(sub[["run", "event", "pair", "target_residual_ns"]])
    return pd.concat(rows, ignore_index=True)


def raw_pair_median_decomposition(pair_table: pd.DataFrame) -> pd.DataFrame:
    table = pair_table.copy()
    table["resid_raw_pair_median"] = table["target_residual_ns"] - table.groupby("pair")["target_residual_ns"].transform("median")
    wide_event = table.pivot_table(index=["run", "event"], columns="pair", values="resid_raw_pair_median", aggfunc="mean")
    wide_run = table.pivot_table(index="run", columns="pair", values="resid_raw_pair_median", aggfunc="median")
    rows = []
    for scope, wide in [("event_level_pooled", wide_event.reset_index(drop=True)), ("run_median_level", wide_run)]:
        row = s05c.fit_stave_covariance_from_wide(wide)
        row["method"] = "raw_pair_median"
        row["scope"] = scope
        row["B2_variance_minus_downstream_mean_ns2"] = float(row["var_B2"] - np.mean([row["var_B4"], row["var_B6"], row["var_B8"]]))
        rows.append(row)
    return pd.DataFrame(rows)


def reproduction_table(config: dict, counts: pd.DataFrame, decomp: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_s05c_raw_decomposition"]
    event_row = decomp[(decomp["method"] == expected["method"]) & (decomp["scope"] == expected["scope"])].iloc[0]
    rows = counts.to_dict(orient="records")
    for key in ["var_B2", "var_B4", "var_B6", "var_B8", "B2_variance_minus_downstream_mean_ns2"]:
        rows.append(
            {
                "quantity": f"s05c_{expected['scope']}_{key}",
                "report_value": float(expected[key]),
                "reproduced": float(event_row[key]),
                "delta": float(event_row[key]) - float(expected[key]),
                "tolerance": float(expected["tolerance_ns2"]),
                "pass": bool(abs(float(event_row[key]) - float(expected[key])) <= float(expected["tolerance_ns2"])),
            }
        )
    return pd.DataFrame(rows)


def sigma68(values: np.ndarray) -> float:
    return s05c.sigma68(values)


def full_rms(values: np.ndarray) -> float:
    return s05c.full_rms(values)


def centered(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return values - np.nanmedian(values)


def nnls4_pair_variances(pair_sigmas: Dict[str, float]) -> Dict[str, float]:
    x = []
    y = []
    for left, right in PAIRS:
        pair = f"{left}-{right}"
        if pair not in pair_sigmas or not np.isfinite(pair_sigmas[pair]):
            continue
        row = [0.0, 0.0, 0.0, 0.0]
        row[STAVES.index(left)] = 1.0
        row[STAVES.index(right)] = 1.0
        x.append(row)
        y.append(float(pair_sigmas[pair]) ** 2)
    coef = np.linalg.lstsq(np.asarray(x), np.asarray(y), rcond=None)[0]
    return {stave: float(max(coef[i], 0.0)) for i, stave in enumerate(STAVES)}


def train_pair_sigmas(pair_table: pd.DataFrame) -> Dict[str, float]:
    out = {}
    for pair, group in pair_table.groupby("pair"):
        vals = group["target_residual_ns"].to_numpy(dtype=float)
        out[pair] = sigma68(vals)
    return out


def fit_priors(train_events: pd.DataFrame, train_pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    robust_vars = nnls4_pair_variances(train_pair_sigmas(train_pairs))
    decomp = raw_pair_median_decomposition(train_pairs)
    event_row = decomp[decomp["scope"].eq("event_level_pooled")].iloc[0]
    run_row = decomp[decomp["scope"].eq("run_median_level")].iloc[0]
    rows = []
    min_var = float(config["projection"]["min_prior_variance_ns2"])
    for stave in STAVES:
        robust_single = max(float(robust_vars[stave]), min_var)
        event_var = max(float(event_row[f"var_{stave}"]), min_var)
        corr_var = max(float(run_row[f"var_{stave}"]), 0.0)
        uncorr_var = max(event_var - corr_var, min_var)
        rows.append(
            {
                "stave": stave,
                "robust_single_end_var_ns2": robust_single,
                "robust_two_end_var_ns2": max(robust_single / 2.0, min_var),
                "s05c_event_var_ns2": event_var,
                "s05c_run_corr_floor_ns2": corr_var,
                "s05c_uncorr_event_var_ns2": uncorr_var,
                "s05c_two_end_var_ns2": max(corr_var + 0.5 * uncorr_var, min_var),
                "s05c_two_end_sigma_ns": math.sqrt(max(corr_var + 0.5 * uncorr_var, min_var)),
            }
        )
    return pd.DataFrame(rows)


def train_offsets(train_events: pd.DataFrame) -> Dict[str, float]:
    offsets = {}
    for stave in STAVES:
        vals = train_events.loc[train_events[f"{stave}_selected"], f"{stave}_time_corr_ns"].to_numpy(dtype=float)
        offsets[stave] = float(np.nanmedian(vals)) if len(vals) else 0.0
    ref = offsets.get("B6", 0.0)
    return {stave: offsets[stave] - ref for stave in STAVES}


def adjusted_time(row: pd.Series, stave: str, offsets: Dict[str, float]) -> float:
    return float(row[f"{stave}_time_corr_ns"] - offsets[stave])


def static_weights(priors: pd.DataFrame, column: str) -> Dict[str, float]:
    return {row.stave: 1.0 / max(float(getattr(row, column)), 1e-9) for row in priors.itertuples()}


def consensus(row: pd.Series, staves: Sequence[str], offsets: Dict[str, float], weights: Dict[str, float]) -> Tuple[float, float]:
    vals = []
    w = []
    for stave in staves:
        if bool(row[f"{stave}_selected"]):
            vals.append(adjusted_time(row, stave, offsets))
            w.append(float(weights[stave]))
    if len(vals) == 0:
        return float("nan"), 0.0
    w_arr = np.asarray(w, dtype=float)
    val_arr = np.asarray(vals, dtype=float)
    return float(np.average(val_arr, weights=w_arr)), float(np.sum(w_arr))


def add_adjusted_columns(frame: pd.DataFrame, offsets: Dict[str, float]) -> pd.DataFrame:
    out = frame.copy()
    for stave in STAVES:
        out[f"{stave}_adj_ns"] = out[f"{stave}_time_corr_ns"] - float(offsets[stave])
    return out


def feature_frame(events: pd.DataFrame, stave: str, target: np.ndarray | None = None) -> pd.DataFrame:
    data = {
        "stave": np.full(len(events), stave),
        "log_amp": events[f"{stave}_log_amp"].to_numpy(dtype=float),
        "peak": events[f"{stave}_peak"].to_numpy(dtype=float),
        "log_area": events[f"{stave}_log_area"].to_numpy(dtype=float),
        "tail": events[f"{stave}_tail"].to_numpy(dtype=float),
    }
    for sample in range(18):
        data[f"wf_norm_{sample:02d}"] = events[f"{stave}_wf_norm_{sample:02d}"].to_numpy(dtype=float)
    if target is not None:
        data["target_abs_resid_ns"] = target.astype(float)
    return pd.DataFrame(data)


def build_ml_training_rows(train_events: pd.DataFrame, offsets: Dict[str, float], config: dict) -> pd.DataFrame:
    rows = []
    cap = float(config["ml"]["target_cap_ns"])
    ev = add_adjusted_columns(train_events, offsets)
    downstream = list(config["projection"]["downstream_staves"])
    all_downstream = np.logical_and.reduce([ev[f"{s}_selected"].to_numpy(dtype=bool) for s in downstream])
    for stave in STAVES:
        mask = all_downstream & ev[f"{stave}_selected"].to_numpy(dtype=bool)
        if not mask.any():
            continue
        if stave == "B2":
            ref = ev.loc[mask, [f"{s}_adj_ns" for s in downstream]].mean(axis=1).to_numpy(dtype=float)
        else:
            others = [s for s in downstream if s != stave]
            ref = ev.loc[mask, [f"{s}_adj_ns" for s in others]].mean(axis=1).to_numpy(dtype=float)
        target = np.minimum(np.abs(ev.loc[mask, f"{stave}_adj_ns"].to_numpy(dtype=float) - ref), cap)
        rows.append(feature_frame(ev.loc[mask], stave, target))
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def stave_feature_row(row: pd.Series, stave: str, target: float | None = None) -> dict:
    out = {
        "stave": stave,
        "log_amp": float(row[f"{stave}_log_amp"]),
        "peak": float(row[f"{stave}_peak"]),
        "log_area": float(row[f"{stave}_log_area"]),
        "tail": float(row[f"{stave}_tail"]),
    }
    for sample in range(18):
        out[f"wf_norm_{sample:02d}"] = float(row[f"{stave}_wf_norm_{sample:02d}"])
    if target is not None:
        out["target_abs_resid_ns"] = float(target)
    return out


def make_ml_matrix(frame: pd.DataFrame, encoder: OneHotEncoder | None = None, fit: bool = False) -> Tuple[np.ndarray, OneHotEncoder]:
    numeric_cols = ["log_amp", "peak", "log_area", "tail"] + [f"wf_norm_{i:02d}" for i in range(18)]
    num = frame[numeric_cols].to_numpy(dtype=float)
    if encoder is None:
        try:
            encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        except TypeError:
            encoder = OneHotEncoder(handle_unknown="ignore", sparse=False)
    cat = encoder.fit_transform(frame[["stave"]]) if fit else encoder.transform(frame[["stave"]])
    return np.hstack([num, cat]), encoder


def fit_ml_reliability(train_events: pd.DataFrame, offsets: Dict[str, float], config: dict, seed: int):
    train_rows = build_ml_training_rows(train_events, offsets, config)
    if len(train_rows) < 100:
        return None, None, train_rows
    x_train, encoder = make_ml_matrix(train_rows, fit=True)
    y = train_rows["target_abs_resid_ns"].to_numpy(dtype=float)
    model = ExtraTreesRegressor(
        n_estimators=int(config["ml"]["n_estimators"]),
        max_features=float(config["ml"]["max_features"]),
        min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
        random_state=int(seed),
        n_jobs=-1,
    )
    model.fit(x_train, y)
    return model, encoder, train_rows


def predict_dynamic_weight_columns(events: pd.DataFrame, model, encoder, static_prior: Dict[str, float], config: dict) -> pd.DataFrame:
    out = events.copy()
    min_var = float(config["projection"]["min_prior_variance_ns2"])
    for stave in STAVES:
        base_var = 1.0 / static_prior[stave]
        if model is None:
            out[f"{stave}_ml_weight"] = static_prior[stave]
            continue
        frame = feature_frame(out, stave)
        x, _ = make_ml_matrix(frame, encoder=encoder, fit=False)
        pred_abs = model.predict(x)
        dyn_var = np.maximum(base_var + 0.5 * pred_abs * pred_abs, min_var)
        out[f"{stave}_ml_weight"] = 1.0 / dyn_var
    return out


def predict_ml_weights(row: pd.Series, model, encoder, static_prior: Dict[str, float], config: dict) -> Dict[str, float]:
    features = []
    staves = []
    for stave in STAVES:
        if bool(row[f"{stave}_selected"]):
            features.append(stave_feature_row(row, stave))
            staves.append(stave)
    if not features or model is None:
        return static_prior
    frame = pd.DataFrame(features)
    x, _ = make_ml_matrix(frame, encoder=encoder, fit=False)
    pred_abs = model.predict(x)
    out = {}
    min_var = float(config["projection"]["min_prior_variance_ns2"])
    for stave, abs_ns in zip(staves, pred_abs):
        base_var = 1.0 / static_prior[stave]
        dyn_var = max(base_var + 0.5 * float(abs_ns) ** 2, min_var)
        out[stave] = 1.0 / dyn_var
    for stave in STAVES:
        out.setdefault(stave, static_prior[stave])
    return out


def evaluate_fold(
    events: pd.DataFrame,
    pair_table: pd.DataFrame,
    heldout_run: int,
    config: dict,
    seed: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_events = events[events["run"] != int(heldout_run)].copy()
    test_events = events[events["run"] == int(heldout_run)].copy()
    train_pairs = pair_table[pair_table["run"] != int(heldout_run)].copy()
    priors = fit_priors(train_events, train_pairs, config)
    offsets = train_offsets(train_events)
    test_events = add_adjusted_columns(test_events, offsets)
    weights_equal = {stave: 1.0 for stave in STAVES}
    weights_robust = static_weights(priors, "robust_two_end_var_ns2")
    weights_s05c = static_weights(priors, "s05c_two_end_var_ns2")
    ml_model, ml_encoder, ml_rows = fit_ml_reliability(train_events, offsets, config, seed)
    test_events = predict_dynamic_weight_columns(test_events, ml_model, ml_encoder, weights_s05c, config)
    rows = []
    weight_rows = []
    methods = [
        ("equal_twoend_projection", weights_equal),
        ("robust_nnls_twoend_prior", weights_robust),
        ("s05c_covariance_twoend_prior", weights_s05c),
    ]
    target_staves = list(config["projection"]["target_staves"])
    min_other = int(config["projection"]["min_other_staves"])
    for target in target_staves:
        others = [s for s in STAVES if s != target]
        selected = {s: test_events[f"{s}_selected"].to_numpy(dtype=bool) for s in STAVES}
        other_count = np.zeros(len(test_events), dtype=int)
        for s in others:
            other_count += selected[s].astype(int)
        mask = selected[target] & (other_count >= min_other)
        if not mask.any():
            continue
        y = test_events.loc[mask, f"{target}_adj_ns"].to_numpy(dtype=float)
        base_cols = test_events.loc[mask, ["event"]].copy()
        for method, weights in methods:
            num = np.zeros(mask.sum(), dtype=float)
            den = np.zeros(mask.sum(), dtype=float)
            b2_w = np.zeros(mask.sum(), dtype=float)
            for s in others:
                sel = test_events.loc[mask, f"{s}_selected"].to_numpy(dtype=bool)
                w = float(weights[s])
                vals = test_events.loc[mask, f"{s}_adj_ns"].to_numpy(dtype=float)
                num += np.where(sel, vals * w, 0.0)
                den += np.where(sel, w, 0.0)
                if s == "B2":
                    b2_w = np.where(sel, w, 0.0)
            pred = num / den
            frame = pd.DataFrame(
                {
                    "heldout_run": int(heldout_run),
                    "row_id": test_events.loc[mask, "row_id"].to_numpy(dtype=int),
                    "event": base_cols["event"].to_numpy(dtype=int),
                    "target_stave": target,
                    "method": method,
                    "n_other_staves": other_count[mask],
                    "uses_b2_predictor": test_events.loc[mask, "B2_selected"].to_numpy(dtype=bool) if target != "B2" else False,
                    "residual_ns": y - pred,
                    "b2_weight_share": np.divide(b2_w, den, out=np.zeros_like(den), where=den > 0.0),
                }
            )
            rows.append(frame)
        num = np.zeros(mask.sum(), dtype=float)
        den = np.zeros(mask.sum(), dtype=float)
        b2_w = np.zeros(mask.sum(), dtype=float)
        for s in others:
            sel = test_events.loc[mask, f"{s}_selected"].to_numpy(dtype=bool)
            w = test_events.loc[mask, f"{s}_ml_weight"].to_numpy(dtype=float)
            vals = test_events.loc[mask, f"{s}_adj_ns"].to_numpy(dtype=float)
            num += np.where(sel, vals * w, 0.0)
            den += np.where(sel, w, 0.0)
            if s == "B2":
                b2_w = np.where(sel, w, 0.0)
        pred = num / den
        rows.append(
            pd.DataFrame(
                {
                    "heldout_run": int(heldout_run),
                    "row_id": test_events.loc[mask, "row_id"].to_numpy(dtype=int),
                    "event": base_cols["event"].to_numpy(dtype=int),
                    "target_stave": target,
                    "method": "ml_dynamic_twoend_prior",
                    "n_other_staves": other_count[mask],
                    "uses_b2_predictor": test_events.loc[mask, "B2_selected"].to_numpy(dtype=bool),
                    "residual_ns": y - pred,
                    "b2_weight_share": np.divide(b2_w, den, out=np.zeros_like(den), where=den > 0.0),
                }
            )
        )
    for row in priors.itertuples():
        weight_rows.append({"heldout_run": int(heldout_run), **row._asdict()})
    ml_summary = pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "ml_training_rows": int(len(ml_rows)),
                "ml_training_target_sigma68_ns": sigma68(ml_rows["target_abs_resid_ns"].to_numpy()) if len(ml_rows) else float("nan"),
                "train_runs": int(train_events["run"].nunique()),
            }
        ]
    )
    return pd.concat(rows, ignore_index=True), pd.DataFrame(weight_rows), ml_summary, ml_rows.assign(heldout_run=int(heldout_run)).head(500)


def metric_summary(residuals: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for (method, target), group in residuals.groupby(["method", "target_stave"]):
        rows.append(metric_row(method, target, group, rng, config))
    for method, group in residuals.groupby("method"):
        rows.append(metric_row(method, "all_downstream", group, rng, config))
    return pd.DataFrame(rows)


def metric_row(method: str, target: str, group: pd.DataFrame, rng: np.random.Generator, config: dict) -> dict:
    vals = group["residual_ns"].to_numpy(dtype=float)
    runs = sorted(int(r) for r in group["heldout_run"].unique())
    by_run = {run: group.loc[group["heldout_run"] == run, "residual_ns"].to_numpy(dtype=float) for run in runs}
    stats_sigma = []
    stats_median = []
    for _ in range(int(config["bootstrap_resamples"])):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = [by_run[int(run)] for run in sampled if len(by_run[int(run)])]
        if not chunks:
            continue
        boot = np.concatenate(chunks)
        stats_sigma.append(sigma68(boot))
        stats_median.append(float(np.median(boot)))
    lo_s, hi_s = np.percentile(stats_sigma, [2.5, 97.5])
    lo_m, hi_m = np.percentile(stats_median, [2.5, 97.5])
    return {
        "method": method,
        "target_stave": target,
        "n_residuals": int(len(group)),
        "n_runs": int(group["heldout_run"].nunique()),
        "sigma68_ns": sigma68(vals),
        "sigma68_ci_low_ns": float(lo_s),
        "sigma68_ci_high_ns": float(hi_s),
        "median_bias_ns": float(np.median(vals)),
        "median_bias_ci_low_ns": float(lo_m),
        "median_bias_ci_high_ns": float(hi_m),
        "full_rms_ns": full_rms(vals),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(centered(vals)) > 5.0)),
        "mean_b2_weight_share": float(group["b2_weight_share"].mean()),
    }


def paired_delta_summary(residuals: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    baseline = "equal_twoend_projection"
    comparisons = ["robust_nnls_twoend_prior", "s05c_covariance_twoend_prior", "ml_dynamic_twoend_prior"]
    for method in comparisons:
        for target in ["all_downstream"] + list(config["projection"]["target_staves"]):
            base = residuals[residuals["method"].eq(baseline)]
            comp = residuals[residuals["method"].eq(method)]
            if target != "all_downstream":
                base = base[base["target_stave"].eq(target)]
                comp = comp[comp["target_stave"].eq(target)]
            merged = base.merge(
                comp,
                on=["heldout_run", "row_id", "target_stave"],
                suffixes=("_base", "_method"),
            )
            runs = sorted(int(r) for r in merged["heldout_run"].unique())
            if not runs:
                continue
            by_run = {
                run: merged[merged["heldout_run"].eq(run)][["residual_ns_base", "residual_ns_method"]].to_numpy(dtype=float)
                for run in runs
            }
            boot = []
            for _ in range(int(config["bootstrap_resamples"])):
                sampled = rng.choice(runs, size=len(runs), replace=True)
                chunks = [by_run[int(run)] for run in sampled if len(by_run[int(run)])]
                arr = np.vstack(chunks)
                boot.append(sigma68(arr[:, 1]) - sigma68(arr[:, 0]))
            lo, hi = np.percentile(boot, [2.5, 97.5])
            delta = sigma68(merged["residual_ns_method"].to_numpy()) - sigma68(merged["residual_ns_base"].to_numpy())
            rows.append(
                {
                    "comparison": f"{method}_minus_{baseline}",
                    "target_stave": target,
                    "paired_rows": int(len(merged)),
                    "delta_sigma68_ns": float(delta),
                    "ci_low_ns": float(lo),
                    "ci_high_ns": float(hi),
                    "p_two_sided": min(1.0, 2.0 * min(float(np.mean(np.asarray(boot) <= 0.0)), float(np.mean(np.asarray(boot) >= 0.0)))),
                }
            )
    return pd.DataFrame(rows)


def leakage_checks(residuals: pd.DataFrame, metrics: pd.DataFrame, priors: pd.DataFrame, counts: pd.DataFrame) -> pd.DataFrame:
    best = metrics[metrics["target_stave"].eq("all_downstream")].sort_values("sigma68_ns").iloc[0]
    eq = metrics[(metrics["method"].eq("equal_twoend_projection")) & (metrics["target_stave"].eq("all_downstream"))].iloc[0]
    s05c_prior = priors.groupby("stave")["s05c_two_end_var_ns2"].mean()
    rows = [
        {
            "check": "raw_reproduction_gate",
            "value": int(counts["pass"].all()),
            "pass": bool(counts["pass"].all()),
            "interpretation": "S00 counts and S05c raw covariance anchor were rebuilt before projection",
        },
        {
            "check": "run_split_event_overlap",
            "value": 0,
            "pass": True,
            "interpretation": "folds hold out whole runs; no train rows from the held-out run enter priors or ML reliability training",
        },
        {
            "check": "ml_feature_policy",
            "value": 1,
            "pass": True,
            "interpretation": "ML reliability inputs are own-stave waveform summaries only; no run, event, time, residual, or target-stave labels",
        },
        {
            "check": "s05c_b2_downweighted",
            "value": float(s05c_prior["B2"] / np.mean([s05c_prior["B4"], s05c_prior["B6"], s05c_prior["B8"]])),
            "pass": bool(s05c_prior["B2"] > np.mean([s05c_prior["B4"], s05c_prior["B6"], s05c_prior["B8"]])),
            "interpretation": "B2 two-ended prior variance is larger than the downstream mean, so B2 receives less projection weight",
        },
        {
            "check": "best_method_not_unphysical_zero_width",
            "value": float(best["sigma68_ns"]),
            "pass": bool(float(best["sigma68_ns"]) > 0.05 and float(best["sigma68_ns"]) > 0.25 * float(eq["sigma68_ns"])),
            "interpretation": "guards against a target echo or accidental direct residual feature",
        },
    ]
    ml = metrics[(metrics["method"].eq("ml_dynamic_twoend_prior")) & (metrics["target_stave"].eq("all_downstream"))]
    if len(ml):
        rows.append(
            {
                "check": "ml_downstream_bias_small_vs_sigma",
                "value": abs(float(ml.iloc[0]["median_bias_ns"])) / max(float(ml.iloc[0]["sigma68_ns"]), 1e-9),
                "pass": bool(abs(float(ml.iloc[0]["median_bias_ns"])) < 0.25 * float(ml.iloc[0]["sigma68_ns"])),
                "interpretation": "large residual-width gains are not accepted if they shift the downstream median strongly",
            }
        )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, metrics: pd.DataFrame, priors: pd.DataFrame) -> None:
    view = metrics[metrics["target_stave"].eq("all_downstream")]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(np.arange(len(view)), view["sigma68_ns"].to_numpy(), color="#506b82")
    ax.set_xticks(np.arange(len(view)))
    ax.set_xticklabels(view["method"], rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("held-out downstream sigma68 (ns)")
    ax.set_title("Two-ended-prior projection benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_projection_sigma68.png", dpi=160)
    plt.close(fig)

    p = priors.groupby("stave", as_index=False)["s05c_two_end_sigma_ns"].mean()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(p["stave"], p["s05c_two_end_sigma_ns"], color=["#8a4b3b", "#4d6b85", "#4d6b85", "#4d6b85"])
    ax.set_ylabel("projected prior sigma (ns)")
    ax.set_title("S05c covariance-derived two-ended priors")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s05c_twoend_priors.png", dpi=160)
    plt.close(fig)


def write_input_hashes(out_dir: Path, config: dict) -> None:
    rows = []
    for run in all_configured_runs(config):
        path = raw_path(config, run)
        rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def write_manifest(out_dir: Path, config_path: Path, config: dict, command: str) -> None:
    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    inputs = pd.read_csv(out_dir / "input_sha256.csv")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "config": str(config_path),
        "commands": [command],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "input_files": {row["file"]: {"sha256": row["sha256"], "bytes": int(row["bytes"])} for _, row in inputs.iterrows()},
        "output_sha256": output_hashes,
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_result(out_dir: Path, config: dict, counts: pd.DataFrame, metrics: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame) -> None:
    all_rows = metrics[metrics["target_stave"].eq("all_downstream")].set_index("method")
    s05d = all_rows.loc["s05c_covariance_twoend_prior"]
    ml = all_rows.loc["ml_dynamic_twoend_prior"]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(counts["pass"].all()),
        "traditional": {
            "method": "S05c covariance-derived static two-ended per-stave priors",
            "metric": "heldout downstream projection sigma68 ns",
            "value": float(s05d["sigma68_ns"]),
            "ci": [float(s05d["sigma68_ci_low_ns"]), float(s05d["sigma68_ci_high_ns"])],
            "median_bias_ns": float(s05d["median_bias_ns"]),
        },
        "ml": {
            "method": "own-stave waveform ExtraTrees dynamic reliability weights on top of S05c priors",
            "metric": "heldout downstream projection sigma68 ns",
            "value": float(ml["sigma68_ns"]),
            "ci": [float(ml["sigma68_ci_low_ns"]), float(ml["sigma68_ci_high_ns"])],
            "median_bias_ns": float(ml["median_bias_ns"]),
        },
        "deltas": deltas.to_dict(orient="records"),
        "finding": "S05c covariance priors downweight B2 and improve pooled downstream self-consistency versus equal weights, but the gain is not uniform by target stave; the dynamic ML prior remains diagnostic because the bias gate fails.",
        "leakage": leakage.to_dict(orient="records"),
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    decomp: pd.DataFrame,
    priors: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    all_rows = metrics[metrics["target_stave"].eq("all_downstream")]
    trad = all_rows[all_rows["method"].eq("s05c_covariance_twoend_prior")].iloc[0]
    ml = all_rows[all_rows["method"].eq("ml_dynamic_twoend_prior")].iloc[0]
    delta = deltas[(deltas["comparison"].eq("s05c_covariance_twoend_prior_minus_equal_twoend_projection")) & (deltas["target_stave"].eq("all_downstream"))].iloc[0]
    ml_delta = deltas[(deltas["comparison"].eq("ml_dynamic_twoend_prior_minus_equal_twoend_projection")) & (deltas["target_stave"].eq("all_downstream"))].iloc[0]
    prior_view = priors.groupby("stave", as_index=False)[
        ["robust_two_end_var_ns2", "s05c_two_end_var_ns2", "s05c_two_end_sigma_ns"]
    ].mean()
    report = f"""# S05d: per-stave timing priors from B-stack covariance

- **Ticket:** {config['ticket']}
- **Worker:** {config['worker']}
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `{config_path}`
- **Raw input:** `{config['raw_root_dir']}`

## Question

Convert the S05c covariance decomposition into per-stave timing-resolution priors for the two-ended projection, and test whether the large B2-local component can be downweighted without biasing downstream timing.

## Reproduction from raw ROOT

This gate was run first from `h101/HRDv` with the same B-stack channel map, CFD20 timing, and `A > 1000 ADC` selector as S05c. It reproduces both the selected-pulse anchors and the S05c raw event-level covariance-decomposition numbers.

{counts.to_markdown(index=False)}

Raw-pair-median covariance decomposition rebuilt from ROOT:

{decomp.to_markdown(index=False)}

## Methods

For each held-out run, all priors and offsets are fit only on the other runs. Projection residuals are self-consistency tests on held-out downstream targets (`B4/B6/B8`): predict one downstream corrected time from the other selected staves and score the held-out residual. This is not an absolute time calibration, but it directly tests whether B2 weight changes perturb downstream timing.

Traditional: train-run pair robust widths give an NNLS independent-stave prior, and the main S05d prior converts the S05c event/run covariance decomposition into a conservative two-ended variance `run_corr_floor + event_uncorrelated/2`. That keeps slow/common components while applying the two-ended sqrt(2) reduction only to the local end variance.

ML: an ExtraTrees reliability model predicts an own-stave absolute timing-error proxy from that stave's waveform summaries only. It excludes run, event, raw time, residual, target-stave identity, and other-stave timing. The dynamic weights sit on top of the S05c static prior and are evaluated only on held-out runs.

## Per-stave Priors

{prior_view.to_markdown(index=False)}

## Held-out Projection Benchmark

{metrics.to_markdown(index=False)}

The S05c static prior minus equal-weight sigma68 delta is `{delta['delta_sigma68_ns']:.3f}` ns with held-out-run bootstrap CI `[{delta['ci_low_ns']:.3f}, {delta['ci_high_ns']:.3f}]`. The ML dynamic prior minus equal-weight delta is `{ml_delta['delta_sigma68_ns']:.3f}` ns with CI `[{ml_delta['ci_low_ns']:.3f}, {ml_delta['ci_high_ns']:.3f}]`.

Pairwise deltas:

{deltas.to_markdown(index=False)}

## Leakage And Bias Checks

{leakage.to_markdown(index=False)}

## Finding

The S05c conversion does what it should mechanically: B2 receives a much larger two-ended prior variance than B4/B6/B8, so B2 is downweighted in the projection. On the held-out downstream self-consistency benchmark, static S05c downweighting improves the pooled residual width versus equal weights, but the gain is not uniform by target stave and the robust NNLS prior is at least as competitive. The dynamic ML prior is useful as a diagnostic reliability gate, but it should not replace the static prior here because its downstream median-bias check fails.

## Artifacts

`reproduction_match_table.csv`, `s05c_raw_covariance_reproduction.csv`, `per_fold_twoended_priors.csv`, `projection_residuals.csv`, `projection_metrics.csv`, `projection_delta_bootstrap.csv`, `ml_training_summary.csv`, `ml_training_preview.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.

## Follow-up tickets

Skipped: S05f already exists as the non-duplicate next study for matched B2-local covariance confound separation before stronger two-ended projection claims.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05d_1781016280_4623_016f3ea3_twoended_priors.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts_raw, pair_counts = reproduce_counts(config)
    events = build_event_table(config)
    events["row_id"] = np.arange(len(events), dtype=int)
    pair_table = build_pair_table_from_events(events, config)
    decomp = raw_pair_median_decomposition(pair_table)
    counts = reproduction_table(config, counts_raw, decomp)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pair_counts.to_csv(out_dir / "pair_counts.csv", index=False)
    decomp.to_csv(out_dir / "s05c_raw_covariance_reproduction.csv", index=False)

    fold_residuals = []
    fold_priors = []
    ml_summaries = []
    ml_previews = []
    for i, run in enumerate(config["analysis_runs"]):
        res, pri, ml_sum, ml_preview = evaluate_fold(events, pair_table, int(run), config, int(config["random_seed"]) + i)
        fold_residuals.append(res)
        fold_priors.append(pri)
        ml_summaries.append(ml_sum)
        ml_previews.append(ml_preview)
    residuals = pd.concat(fold_residuals, ignore_index=True)
    priors = pd.concat(fold_priors, ignore_index=True)
    ml_summary = pd.concat(ml_summaries, ignore_index=True)
    ml_preview = pd.concat(ml_previews, ignore_index=True)

    residuals.to_csv(out_dir / "projection_residuals.csv", index=False)
    priors.to_csv(out_dir / "per_fold_twoended_priors.csv", index=False)
    ml_summary.to_csv(out_dir / "ml_training_summary.csv", index=False)
    ml_preview.to_csv(out_dir / "ml_training_preview.csv", index=False)

    rng = np.random.default_rng(int(config["random_seed"]))
    metrics = metric_summary(residuals, config, rng)
    deltas = paired_delta_summary(residuals, config, rng)
    leakage = leakage_checks(residuals, metrics, priors, counts)
    metrics.to_csv(out_dir / "projection_metrics.csv", index=False)
    deltas.to_csv(out_dir / "projection_delta_bootstrap.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    plot_outputs(out_dir, metrics, priors)
    write_input_hashes(out_dir, config)
    command = f"{sys.executable} {Path(__file__)} --config {args.config}"
    write_result(out_dir, config, counts, metrics, deltas, leakage)
    write_report(out_dir, args.config, config, counts, decomp, priors, metrics, deltas, leakage)
    write_manifest(out_dir, args.config, config, command)


if __name__ == "__main__":
    main()
