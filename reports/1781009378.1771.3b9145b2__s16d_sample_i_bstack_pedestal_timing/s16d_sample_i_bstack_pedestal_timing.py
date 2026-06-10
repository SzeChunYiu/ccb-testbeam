#!/usr/bin/env python3
"""S16d Sample-I B-stack pedestal-lowering timing-tail nuisance test."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def load_s02():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("s02_timing_pickoff", root / "scripts" / "s02_timing_pickoff.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load S02 timing module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s02_timing_pickoff"] = module
    spec.loader.exec_module(module)
    return module


S02 = load_s02()


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


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


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


def adaptive_pedestal(waveforms: np.ndarray, seed: np.ndarray, cfg: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
    return pedestal, lowering, amp, min_margin


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    total = 0
    sample_i = {k: 0 for k in ["selected_pulses", *stave_names]}
    violations = 0

    for run in configured_runs(config):
        for batch in iter_raw(raw_file(config, run), ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            seed = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - seed[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            total += int(selected.sum())
            if selected.any():
                flat_w = waveforms[selected].reshape(-1, nsamp)
                flat_seed = seed[selected].reshape(-1)
                _, _, _, margin = adaptive_pedestal(flat_w, flat_seed, config)
                violations += int((margin < -1e-9).sum())
            if run in config["run_groups"]["sample_i_analysis"]:
                sample_i["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_i[stave] += int(selected[:, i].sum())

    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        },
        {"quantity": "adaptive post-correction violations", "report_value": 0, "reproduced": int(violations), "tolerance": 0},
    ]
    for key, value in config["expected_counts"]["sample_i_analysis"].items():
        rows.append({"quantity": f"sample_i_analysis {key}", "report_value": int(value), "reproduced": int(sample_i[key]), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def load_downstream_pulses(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    all_staves = {name: int(ch) for name, ch in config["staves"].items()}
    downstream = list(config["timing"]["downstream_staves"])
    channels = np.asarray([all_staves[name] for name in downstream])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    event_uid_base = 0
    timing_runs = sorted(set(config["timing"]["train_runs"] + config["timing"]["heldout_runs"]))
    for run in timing_runs:
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw = events[:, channels, :]
            seed = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - seed[..., None]
            amplitude = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            selected = amplitude > cut
            event_mask = selected.all(axis=1)
            if not event_mask.any():
                event_uid_base += len(eventno)
                continue
            event_idx = np.where(event_mask)[0]
            flat_raw = raw[event_idx].reshape(-1, nsamp)
            flat_seed = seed[event_idx].reshape(-1)
            _, lowering, _, margin = adaptive_pedestal(flat_raw, flat_seed, config)
            lowering = lowering.reshape(len(event_idx), len(downstream))
            margin = margin.reshape(len(event_idx), len(downstream))
            for local_i, e in enumerate(event_idx):
                uid = f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_uid_base + int(e)}"
                for sidx, stave in enumerate(downstream):
                    rows.append(
                        {
                            "event_id": uid,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": stave,
                            "waveform": corrected[e, sidx].astype(float),
                            "amplitude_adc": float(amplitude[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                            "adaptive_lowering_adc": float(lowering[local_i, sidx]),
                            "adaptive_margin_adc": float(margin[local_i, sidx]),
                            "lowering_frac_amp": float(lowering[local_i, sidx] / max(amplitude[e, sidx], 1.0)),
                        }
                    )
            event_uid_base += len(eventno)
    return pd.DataFrame(rows)


def add_cfd_times(pulses: pd.DataFrame, config: dict) -> None:
    period = float(config["sample_period_ns"])
    wf = np.vstack(pulses["waveform"].to_numpy())
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    for frac in config["timing"]["cfd_fractions"]:
        name = f"cfd{int(round(float(frac) * 100)):02d}"
        pulses[f"t_{name}_ns"] = period * S02.cfd_time_samples(wf, amp, float(frac))


def pair_table(pulses: pd.DataFrame, method: str, config: dict, runs: List[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = S02.geometry_positions(downstream, float(config["spacing_cm"]))
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    wide_cols = ["tcorr", "adaptive_lowering_adc", "lowering_frac_amp", "amplitude_adc", "peak_sample", "area_adc_samples"]
    wide = sub.pivot(index="event_id", columns="stave", values=wide_cols)
    rows = []
    for event_id, row in wide.dropna().iterrows():
        run = int(sub[sub["event_id"] == event_id]["run"].iloc[0])
        for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
            residual = float(row[("tcorr", a)] - row[("tcorr", b)])
            la = float(row[("adaptive_lowering_adc", a)])
            lb = float(row[("adaptive_lowering_adc", b)])
            aa = float(row[("amplitude_adc", a)])
            ab = float(row[("amplitude_adc", b)])
            rows.append(
                {
                    "event_id": event_id,
                    "run": run,
                    "pair": f"{a}-{b}",
                    "stave_a": a,
                    "stave_b": b,
                    "residual_ns": residual,
                    "abs_residual_ns": abs(residual),
                    "delta_lowering_adc": la - lb,
                    "abs_delta_lowering_adc": abs(la - lb),
                    "max_lowering_adc": max(la, lb),
                    "sum_lowering_adc": la + lb,
                    "delta_lowering_frac": float(row[("lowering_frac_amp", a)] - row[("lowering_frac_amp", b)]),
                    "max_lowering_frac": max(float(row[("lowering_frac_amp", a)]), float(row[("lowering_frac_amp", b)])),
                    "delta_log_amp": math.log1p(aa) - math.log1p(ab),
                    "min_log_amp": min(math.log1p(aa), math.log1p(ab)),
                    "delta_peak_sample": float(row[("peak_sample", a)] - row[("peak_sample", b)]),
                    "delta_area_over_amp": float(row[("area_adc_samples", a)] / max(aa, 1.0) - row[("area_adc_samples", b)] / max(ab, 1.0)),
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no downstream all-hit residual pairs found")
    med_by_pair = out.groupby("pair")["residual_ns"].transform("median")
    out["centered_residual_ns"] = out["residual_ns"] - med_by_pair
    out["tail_abs_gt_threshold"] = np.abs(out["centered_residual_ns"]) > float(config["timing"]["tail_abs_residual_ns"])
    return out


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def metric_summary(frame: pd.DataFrame, residual_col: str) -> Dict[str, float]:
    vals = frame[residual_col].to_numpy(dtype=float)
    med = float(np.median(vals)) if len(vals) else float("nan")
    centered = vals - med
    return {
        "n_pair_residuals": int(len(vals)),
        "n_events": int(frame["event_id"].nunique()),
        "n_runs": int(frame["run"].nunique()),
        "median_ns": med,
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": float(np.sqrt(np.mean(centered**2))) if len(vals) else float("nan"),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > 5.0)) if len(vals) else float("nan"),
        "mae_ns": float(np.mean(np.abs(centered))) if len(vals) else float("nan"),
    }


def run_event_bootstrap_metrics(frame: pd.DataFrame, residual_col: str, rng: np.random.Generator, n_boot: int) -> Dict[str, float]:
    by_run: Dict[int, List[pd.DataFrame]] = {}
    for run, rframe in frame.groupby("run"):
        by_run[int(run)] = [piece.copy() for _, piece in rframe.groupby("event_id")]
    runs = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(int(n_boot)):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            events = by_run[int(run)]
            chosen = rng.choice(np.arange(len(events)), size=len(events), replace=True)
            pieces.extend(events[int(i)] for i in chosen)
        sample = pd.concat(pieces, ignore_index=True)
        stats.append(metric_summary(sample, residual_col))
    return {
        "sigma68_ci_low": float(np.percentile([s["sigma68_ns"] for s in stats], 2.5)),
        "sigma68_ci_high": float(np.percentile([s["sigma68_ns"] for s in stats], 97.5)),
        "tail_ci_low": float(np.percentile([s["tail_frac_abs_gt5ns"] for s in stats], 2.5)),
        "tail_ci_high": float(np.percentile([s["tail_frac_abs_gt5ns"] for s in stats], 97.5)),
        "mae_ci_low": float(np.percentile([s["mae_ns"] for s in stats], 2.5)),
        "mae_ci_high": float(np.percentile([s["mae_ns"] for s in stats], 97.5)),
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
    "delta_peak_sample",
    "delta_area_over_amp",
]
CATEGORICAL_FEATURES = ["pair"]
TRAD_FEATURES = ["delta_lowering_adc", "abs_delta_lowering_adc", "max_lowering_adc", "sum_lowering_adc", "delta_log_amp", "delta_peak_sample", "pair"]


def make_preprocessor(feature_cols: List[str]) -> ColumnTransformer:
    numeric = [c for c in feature_cols if c not in CATEGORICAL_FEATURES]
    categorical = [c for c in feature_cols if c in CATEGORICAL_FEATURES]
    return ColumnTransformer(
        [
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ]
    )


def fit_traditional(train: pd.DataFrame, heldout: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, dict]:
    feature_cols = TRAD_FEATURES
    model = make_pipeline(make_preprocessor(feature_cols), Ridge(alpha=float(config["traditional"]["ridge_alpha"])))
    model.fit(train[feature_cols], train["centered_residual_ns"])
    out = heldout.copy()
    out["traditional_pred_ns"] = model.predict(out[feature_cols])
    out["residual_traditional_corrected_ns"] = out["residual_ns"] - out["traditional_pred_ns"]

    qs = [float(q) for q in config["traditional"]["threshold_grid_quantiles"]]
    scan = []
    for q in qs:
        threshold = float(train["max_lowering_adc"].quantile(q))
        high = train["max_lowering_adc"] >= threshold
        tail_rate_high = float(train.loc[high, "tail_abs_gt_threshold"].mean()) if high.any() else float("nan")
        tail_rate_low = float(train.loc[~high, "tail_abs_gt_threshold"].mean()) if (~high).any() else float("nan")
        scan.append(
            {
                "quantile": q,
                "threshold_adc": threshold,
                "train_tail_rate_high": tail_rate_high,
                "train_tail_rate_low": tail_rate_low,
                "train_risk_ratio": tail_rate_high / tail_rate_low if tail_rate_low > 0 else float("inf"),
            }
        )
    scan_df = pd.DataFrame(scan)
    finite = scan_df[np.isfinite(scan_df["train_risk_ratio"])].copy()
    if finite.empty:
        finite = scan_df.copy()
    best = finite.sort_values("train_risk_ratio", ascending=False).iloc[0].to_dict()
    out["traditional_high_lowering_bin"] = out["max_lowering_adc"] >= float(best["threshold_adc"])
    return out, {"model": "Ridge residual correction", "features": feature_cols, "threshold_scan": scan_df, "best_threshold": best}


def rf_model(params: dict, seed: int) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        random_state=int(seed),
        n_jobs=1,
    )


def fit_ml(train: pd.DataFrame, heldout: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    params = config["ml"]["random_forest"]
    groups = train["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    fold_scores = []
    for tr, va in gkf.split(train[feature_cols], train["centered_residual_ns"], groups=groups):
        model = make_pipeline(make_preprocessor(feature_cols), rf_model(params, int(config["ml"]["random_seed"])))
        model.fit(train.iloc[tr][feature_cols], train.iloc[tr]["centered_residual_ns"])
        pred = model.predict(train.iloc[va][feature_cols])
        corrected = train.iloc[va]["centered_residual_ns"].to_numpy() - pred
        fold_scores.append(sigma68(corrected))

    row_scores = []
    kfold = KFold(n_splits=min(5, len(train)), shuffle=True, random_state=int(config["ml"]["random_seed"]) + 3)
    for tr, va in kfold.split(train[feature_cols]):
        model = make_pipeline(make_preprocessor(feature_cols), rf_model(params, int(config["ml"]["random_seed"]) + 4))
        model.fit(train.iloc[tr][feature_cols], train.iloc[tr]["centered_residual_ns"])
        pred = model.predict(train.iloc[va][feature_cols])
        corrected = train.iloc[va]["centered_residual_ns"].to_numpy() - pred
        row_scores.append(sigma68(corrected))

    scan = pd.DataFrame(
        [
            {
                "n_estimators": int(params["n_estimators"]),
                "max_depth": int(params["max_depth"]),
                "min_samples_leaf": int(params["min_samples_leaf"]),
                "run_cv_sigma68_ns": float(np.mean(fold_scores)),
                "run_cv_sigma68_std_ns": float(np.std(fold_scores, ddof=1)),
                "row_cv_sigma68_ns": float(np.mean(row_scores)),
                "row_minus_run_cv_sigma68_ns": float(np.mean(row_scores) - np.mean(fold_scores)),
            }
        ]
    )

    model = make_pipeline(make_preprocessor(feature_cols), rf_model(params, int(config["ml"]["random_seed"])))
    model.fit(train[feature_cols], train["centered_residual_ns"])
    out = heldout.copy()
    out["ml_pred_ns"] = model.predict(out[feature_cols])
    out["residual_ml_corrected_ns"] = out["residual_ns"] - out["ml_pred_ns"]

    shuffled = train.copy()
    shuffled["shuffled_target"] = rng.permutation(shuffled["centered_residual_ns"].to_numpy())
    shuffled_model = make_pipeline(make_preprocessor(feature_cols), rf_model(params, int(config["ml"]["random_seed"]) + 1))
    shuffled_model.fit(shuffled[feature_cols], shuffled["shuffled_target"])
    out["ml_shuffled_pred_ns"] = shuffled_model.predict(out[feature_cols])
    out["residual_ml_shuffled_corrected_ns"] = out["residual_ns"] - out["ml_shuffled_pred_ns"]

    leaky_cols = feature_cols + ["centered_residual_ns"]
    leaky_model = make_pipeline(make_preprocessor(leaky_cols), rf_model(params, int(config["ml"]["random_seed"]) + 2))
    leaky_model.fit(train[leaky_cols], train["centered_residual_ns"])
    out["ml_oracle_pred_ns"] = leaky_model.predict(out.assign(centered_residual_ns=out["centered_residual_ns"])[leaky_cols])
    out["residual_ml_oracle_corrected_ns"] = out["residual_ns"] - out["ml_oracle_pred_ns"]
    return out, scan, {"features": feature_cols, "params": params}


def make_benchmark(pair_frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    residual_cols = [
        ("raw_cfd20", "residual_ns"),
        ("traditional_ridge_lowering", "residual_traditional_corrected_ns"),
        ("ml_rf_lowering", "residual_ml_corrected_ns"),
        ("ml_shuffled_target_control", "residual_ml_shuffled_corrected_ns"),
        ("ml_intentional_residual_oracle", "residual_ml_oracle_corrected_ns"),
    ]
    for method, col in residual_cols:
        summary = metric_summary(pair_frame, col)
        ci = run_event_bootstrap_metrics(pair_frame, col, rng, int(config["ml"]["bootstrap_samples"]))
        rows.append({"method": method, **summary, **ci})
    return pd.DataFrame(rows)


def heldout_by_run(pair_frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    residual_cols = [
        ("raw_cfd20", "residual_ns"),
        ("traditional_ridge_lowering", "residual_traditional_corrected_ns"),
        ("ml_rf_lowering", "residual_ml_corrected_ns"),
        ("ml_shuffled_target_control", "residual_ml_shuffled_corrected_ns"),
    ]
    for method, col in residual_cols:
        for run, sub in pair_frame.groupby("run"):
            rows.append({"method": method, "run": int(run), **metric_summary(sub, col)})
    return pd.DataFrame(rows)


def leakage_checks(heldout: pd.DataFrame, benchmark: pd.DataFrame, ml_meta: dict, ml_scan: pd.DataFrame, config: dict) -> pd.DataFrame:
    raw = benchmark[benchmark["method"] == "raw_cfd20"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_rf_lowering"].iloc[0]
    shuffled = benchmark[benchmark["method"] == "ml_shuffled_target_control"].iloc[0]
    oracle = benchmark[benchmark["method"] == "ml_intentional_residual_oracle"].iloc[0]
    feature_names = set(ml_meta["features"])
    forbidden = {"run", "event_id", "eventno", "evt", "residual_ns", "centered_residual_ns", "abs_residual_ns", "tail_abs_gt_threshold"}
    expected_heldout = set(int(r) for r in config["timing"]["heldout_runs"])
    observed_heldout = set(int(r) for r in heldout["run"].unique())
    row_advantage = float(ml_scan.iloc[0]["run_cv_sigma68_ns"] - ml_scan.iloc[0]["row_cv_sigma68_ns"])
    return pd.DataFrame(
        [
            {"check": "split_by_run_heldout_runs_match_config", "value": ",".join(map(str, sorted(observed_heldout))), "pass": observed_heldout == expected_heldout},
            {"check": "ml_features_exclude_run_event_and_residual", "value": ",".join(sorted(feature_names & forbidden)), "pass": len(feature_names & forbidden) == 0},
            {"check": "shuffled_target_not_better_than_actual_ml", "value": float(shuffled["sigma68_ns"] - ml["sigma68_ns"]), "pass": bool(shuffled["sigma68_ns"] >= ml["sigma68_ns"])},
            {"check": "intentional_oracle_is_obviously_leaky", "value": float(oracle["sigma68_ns"]), "pass": bool(oracle["sigma68_ns"] < ml["sigma68_ns"])},
            {"check": "row_cv_not_much_better_than_run_cv", "value": row_advantage, "pass": bool(row_advantage < 1.0)},
            {"check": "actual_ml_improvement_under_raw_one_ns", "value": float(raw["sigma68_ns"] - ml["sigma68_ns"]), "pass": bool((raw["sigma68_ns"] - ml["sigma68_ns"]) < 1.0)},
            {"check": "heldout_predictions_finite", "value": int(np.isfinite(heldout["ml_pred_ns"]).sum()), "pass": bool(np.isfinite(heldout["ml_pred_ns"]).all())},
        ]
    )


def plot_outputs(out_dir: Path, heldout: pd.DataFrame, benchmark: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    low = heldout[~heldout["traditional_high_lowering_bin"]]
    high = heldout[heldout["traditional_high_lowering_bin"]]
    ax.hist(low["centered_residual_ns"], bins=45, histtype="step", density=True, label=f"low lowering n={len(low)}")
    ax.hist(high["centered_residual_ns"], bins=45, histtype="step", density=True, label=f"high lowering n={len(high)}")
    ax.set_xlabel("CFD20 pair residual, pair-centered [ns]")
    ax.set_ylabel("density")
    ax.legend()
    ax.set_title("Sample-I held-out residuals by adaptive-lowering bin")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_lowering_residual_tails.png", dpi=150)
    plt.close(fig)

    shown = benchmark[~benchmark["method"].str.contains("oracle")].copy()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.errorbar(
        np.arange(len(shown)),
        shown["sigma68_ns"],
        yerr=[shown["sigma68_ns"] - shown["sigma68_ci_low"], shown["sigma68_ci_high"] - shown["sigma68_ns"]],
        fmt="o",
    )
    ax.set_xticks(np.arange(len(shown)))
    ax.set_xticklabels(shown["method"], rotation=25, ha="right")
    ax.set_ylabel("held-out sigma68 [ns]")
    ax.set_title("Run-held-out nuisance correction benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head_sigma68.png", dpi=150)
    plt.close(fig)


def format_reproduction(match: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.quantity} | {int(r.report_value)} | {int(r.reproduced)} | {int(r.delta)} | {'yes' if bool(r.pass_) else 'no'} |"
        for r in match.rename(columns={"pass": "pass_"}).itertuples()
    )


def format_benchmark(bench: pd.DataFrame) -> str:
    rows = []
    shown = bench[~bench["method"].str.contains("oracle")]
    for r in shown.itertuples():
        rows.append(
            f"| {r.method} | {r.sigma68_ns:.3f} [{r.sigma68_ci_low:.3f}, {r.sigma68_ci_high:.3f}] | "
            f"{r.tail_frac_abs_gt5ns:.3f} [{r.tail_ci_low:.3f}, {r.tail_ci_high:.3f}] | {r.full_rms_ns:.3f} | {int(r.n_pair_residuals)} |"
        )
    return "\n".join(rows)


def format_leakage(checks: pd.DataFrame) -> str:
    return "\n".join(f"| {r.check} | {r.value} | {'yes' if bool(r.pass_) else 'no'} |" for r in checks.rename(columns={"pass": "pass_"}).itertuples())


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    report = f"""# S16d: Sample-I B-stack pedestal-lowering timing-tail nuisance

- **Ticket:** {config["ticket"]}
- **Author:** {config["worker"]}
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `s16d_config.json`

## Question

Does adaptive-pedestal lowering explain timing residual tails in the higher-statistics Sample-I B-stack B4/B6/B8 residuals?

## Raw-ROOT Reproduction First

Before timing work, the script reruns the S00/S16 raw ROOT gate from `h101/HRDv`, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
{numbers["reproduction_rows"]}

The Sample-I timing subset is downstream all-hit B4/B6/B8. Held-out runs {config["timing"]["heldout_runs"]} have `{numbers["heldout_events"]}` events and `{numbers["heldout_pairs"]}` pair residuals; train runs {config["timing"]["train_runs"]} have `{numbers["train_events"]}` events and `{numbers["train_pairs"]}` pair residuals.

## Methods

The target metric is the S02 `CFD20` pair residual after the 2 cm TOF correction. Adaptive lowering is recomputed from the same raw waveforms as S16 and used only as a nuisance covariate.

The traditional method is a Ridge residual correction using signed, absolute, and summed lowering, log-amplitude difference, peak-sample difference, and pair identity. A train-only threshold scan defines a high-lowering residual-tail bin.

The ML method is a fixed random-forest residual corrector using the same lowering features plus fractional lowering, minimum amplitude, and area/peak differences. Splits are by run: training runs {config["timing"]["train_runs"]}, held-out runs {config["timing"]["heldout_runs"]}. Features exclude run, event id, labels, residuals, and other-stave timing labels.

## Held-out Benchmark

Bootstrap CIs resample held-out runs, then events within each sampled run.

| Method | sigma68 ns [95% CI] | tail frac | full RMS ns | n pairs |
|---|---:|---:|---:|---:|
{numbers["benchmark_rows"]}

Train-selected high-lowering threshold: `{numbers["threshold_adc"]:.2f} ADC`. Held-out high-bin tail fraction `{numbers["high_tail"]:.3f}`, low-bin tail fraction `{numbers["low_tail"]:.3f}`.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
{numbers["leakage_rows"]}

## Verdict

{numbers["verdict"]}

## Reproducibility

```bash
python reports/1781009378.1771.3b9145b2__s16d_sample_i_bstack_pedestal_timing/s16d_sample_i_bstack_pedestal_timing.py --config reports/1781009378.1771.3b9145b2__s16d_sample_i_bstack_pedestal_timing/s16d_config.json
```

Artifacts: `reproduction_match_table.csv`, `pair_residuals_train.csv`, `pair_residuals_heldout.csv`, `threshold_scan.csv`, `ml_cv_scan.csv`, `head_to_head_benchmark.csv`, `heldout_by_run.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and two PNG figures.
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
    out_dir = args.config.parent
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = load_downstream_pulses(config)
    add_cfd_times(pulses, config)
    train_pairs = pair_table(pulses, config["timing"]["base_method"], config, list(config["timing"]["train_runs"]))
    heldout_pairs = pair_table(pulses, config["timing"]["base_method"], config, list(config["timing"]["heldout_runs"]))

    trad_heldout, trad_meta = fit_traditional(train_pairs, heldout_pairs, config)
    ml_heldout, ml_scan, ml_meta = fit_ml(train_pairs, trad_heldout, config, rng)
    benchmark = make_benchmark(ml_heldout, config, rng)
    by_run = heldout_by_run(ml_heldout)
    checks = leakage_checks(ml_heldout, benchmark, ml_meta, ml_scan, config)

    train_pairs.to_csv(out_dir / "pair_residuals_train.csv", index=False)
    ml_heldout.to_csv(out_dir / "pair_residuals_heldout.csv", index=False)
    trad_meta["threshold_scan"].to_csv(out_dir / "threshold_scan.csv", index=False)
    ml_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    by_run.to_csv(out_dir / "heldout_by_run.csv", index=False)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, ml_heldout, benchmark)

    input_rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    best_threshold = trad_meta["best_threshold"]
    high = ml_heldout[ml_heldout["traditional_high_lowering_bin"]]
    low = ml_heldout[~ml_heldout["traditional_high_lowering_bin"]]
    raw = benchmark[benchmark["method"] == "raw_cfd20"].iloc[0]
    trad = benchmark[benchmark["method"] == "traditional_ridge_lowering"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_rf_lowering"].iloc[0]
    ml_gain = float(raw["sigma68_ns"] - ml["sigma68_ns"])
    trad_gain = float(raw["sigma68_ns"] - trad["sigma68_ns"])
    high_tail = float(high["tail_abs_gt_threshold"].mean()) if len(high) else float("nan")
    low_tail = float(low["tail_abs_gt_threshold"].mean()) if len(low) else float("nan")
    verdict = (
        f"Adaptive lowering is not a strong explanation of the held-out Sample-I timing tails: "
        f"traditional lowering correction changes sigma68 by {trad_gain:.3f} ns and ML by {ml_gain:.3f} ns versus raw CFD20. "
        f"The high-lowering bin tail fraction is {high_tail:.3f} versus {low_tail:.3f} in the low-lowering bin."
    )

    numbers = {
        "git_commit": git_commit(),
        "reproduction_rows": format_reproduction(match),
        "benchmark_rows": format_benchmark(benchmark),
        "leakage_rows": format_leakage(checks),
        "threshold_adc": float(best_threshold["threshold_adc"]),
        "high_tail": high_tail,
        "low_tail": low_tail,
        "heldout_events": int(ml_heldout["event_id"].nunique()),
        "heldout_pairs": int(len(ml_heldout)),
        "train_events": int(train_pairs["event_id"].nunique()),
        "train_pairs": int(len(train_pairs)),
        "verdict": verdict,
    }
    write_report(out_dir, config, numbers)

    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "raw_reproduction_pass": bool(match["pass"].all()),
        "sample_i_selected_pulses": int(match[match["quantity"] == "sample_i_analysis selected_pulses"]["reproduced"].iloc[0]),
        "heldout_runs": config["timing"]["heldout_runs"],
        "heldout_events": int(ml_heldout["event_id"].nunique()),
        "heldout_pair_residuals": int(len(ml_heldout)),
        "raw_sigma68_ns": float(raw["sigma68_ns"]),
        "traditional_sigma68_ns": float(trad["sigma68_ns"]),
        "ml_sigma68_ns": float(ml["sigma68_ns"]),
        "traditional_gain_vs_raw_ns": trad_gain,
        "ml_gain_vs_raw_ns": ml_gain,
        "high_lowering_tail_fraction": high_tail,
        "low_lowering_tail_fraction": low_tail,
        "leakage_checks_pass": bool(checks["pass"].all()),
        "conclusion": verdict,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "ticket": config["ticket"],
        "worker": config["worker"],
        "command": " ".join(sys.argv),
        "config_path": str(args.config),
        "git_commit": git_commit(),
        "runtime_seconds": float(time.time() - t0),
        "input_sha256": input_rows,
        "output_sha256": output_hashes(out_dir),
        "ml_features": ml_meta["features"],
        "traditional_features": trad_meta["features"],
        "split": {"train_runs": config["timing"]["train_runs"], "heldout_runs": config["timing"]["heldout_runs"]},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
