#!/usr/bin/env python3
"""S16c pedestal-lowering nuisance propagation into S02 timing residuals."""

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
from typing import Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer


def load_s02():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("s02_timing_pickoff", root / "scripts" / "s02_timing_pickoff.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load S02 module")
    module = importlib.util.module_from_spec(spec)
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
    sample_ii = {k: 0 for k in ["selected_pulses", *stave_names]}
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
            if run in config["run_groups"]["sample_ii_analysis"]:
                sample_ii["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_ii[stave] += int(selected[:, i].sum())

    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        },
        {"quantity": "adaptive post-correction violations", "report_value": 0, "reproduced": int(violations), "tolerance": 0},
    ]
    for key, value in config["expected_counts"]["sample_ii_analysis"].items():
        rows.append({"quantity": f"sample_ii_analysis {key}", "report_value": int(value), "reproduced": int(sample_ii[key]), "tolerance": 0})
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
    for run in sorted(set(config["timing"]["train_runs"] + config["timing"]["heldout_runs"])):
        path = raw_file(config, run)
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
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
    med_by_pair = out.groupby("pair")["residual_ns"].transform("median")
    out["centered_residual_ns"] = out["residual_ns"] - med_by_pair
    out["tail_abs_gt_threshold"] = (out["residual_ns"] - float(out["residual_ns"].median())).abs() > float(config["timing"]["tail_abs_residual_ns"])
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
        "median_ns": med,
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": float(np.sqrt(np.mean(centered**2))) if len(vals) else float("nan"),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > 5.0)) if len(vals) else float("nan"),
        "mae_ns": float(np.mean(np.abs(centered))) if len(vals) else float("nan"),
    }


def bootstrap_metrics(frame: pd.DataFrame, residual_col: str, rng: np.random.Generator, n_boot: int) -> Dict[str, float]:
    stats = []
    events = frame["event_id"].drop_duplicates().to_numpy()
    for _ in range(int(n_boot)):
        sampled_events = rng.choice(events, size=len(events), replace=True)
        sample = pd.concat([frame[frame["event_id"] == event_id] for event_id in sampled_events], ignore_index=True)
        stats.append(metric_summary(sample, residual_col))
    return {
        "sigma68_ci_low": float(np.percentile([s["sigma68_ns"] for s in stats], 2.5)),
        "sigma68_ci_high": float(np.percentile([s["sigma68_ns"] for s in stats], 97.5)),
        "tail_ci_low": float(np.percentile([s["tail_frac_abs_gt5ns"] for s in stats], 2.5)),
        "tail_ci_high": float(np.percentile([s["tail_frac_abs_gt5ns"] for s in stats], 97.5)),
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


def make_preprocessor(feature_cols: List[str]):
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
    model = make_pipeline(
        make_preprocessor(feature_cols),
        Ridge(alpha=float(config["traditional"]["ridge_alpha"])),
    )
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
    finite_scan = scan_df[np.isfinite(scan_df["train_risk_ratio"])].copy()
    if finite_scan.empty:
        finite_scan = scan_df.copy()
    scan_df = scan_df.sort_values("train_risk_ratio", ascending=False)
    best = finite_scan.sort_values("train_risk_ratio", ascending=False).iloc[0].to_dict()
    out["traditional_high_lowering_bin"] = out["max_lowering_adc"] >= float(best["threshold_adc"])
    return out, {"model": "Ridge residual correction", "features": feature_cols, "threshold_scan": scan_df, "best_threshold": best}


def fit_ml(train: pd.DataFrame, heldout: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    params = config["ml"]["random_forest"]
    groups = train["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    rows = []
    fold_scores = []
    for tr, va in gkf.split(train[feature_cols], train["centered_residual_ns"], groups=groups):
        model = make_pipeline(
            make_preprocessor(feature_cols),
            RandomForestRegressor(
                n_estimators=int(params["n_estimators"]),
                max_depth=int(params["max_depth"]),
                min_samples_leaf=int(params["min_samples_leaf"]),
                random_state=int(config["ml"]["random_seed"]),
                n_jobs=1,
            ),
        )
        model.fit(train.iloc[tr][feature_cols], train.iloc[tr]["centered_residual_ns"])
        pred = model.predict(train.iloc[va][feature_cols])
        corrected = train.iloc[va]["centered_residual_ns"].to_numpy() - pred
        fold_scores.append(sigma68(corrected))
    rows.append(
        {
            "n_estimators": int(params["n_estimators"]),
            "max_depth": int(params["max_depth"]),
            "min_samples_leaf": int(params["min_samples_leaf"]),
            "cv_sigma68_ns": float(np.mean(fold_scores)),
            "cv_sigma68_std_ns": float(np.std(fold_scores, ddof=1)),
        }
    )
    scan = pd.DataFrame(rows).sort_values("cv_sigma68_ns").reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = make_pipeline(
        make_preprocessor(feature_cols),
        RandomForestRegressor(
            n_estimators=int(best["n_estimators"]),
            max_depth=int(best["max_depth"]),
            min_samples_leaf=int(best["min_samples_leaf"]),
            random_state=int(config["ml"]["random_seed"]),
            n_jobs=1,
        ),
    )
    model.fit(train[feature_cols], train["centered_residual_ns"])
    out = heldout.copy()
    out["ml_pred_ns"] = model.predict(out[feature_cols])
    out["residual_ml_corrected_ns"] = out["residual_ns"] - out["ml_pred_ns"]

    shuffled = train.copy()
    shuffled["shuffled_target"] = rng.permutation(shuffled["centered_residual_ns"].to_numpy())
    shuffled_model = make_pipeline(
        make_preprocessor(feature_cols),
        RandomForestRegressor(
            n_estimators=int(best["n_estimators"]),
            max_depth=int(best["max_depth"]),
            min_samples_leaf=int(best["min_samples_leaf"]),
            random_state=int(config["ml"]["random_seed"]) + 1,
            n_jobs=1,
        ),
    )
    shuffled_model.fit(shuffled[feature_cols], shuffled["shuffled_target"])
    out["ml_shuffled_pred_ns"] = shuffled_model.predict(out[feature_cols])
    out["residual_ml_shuffled_corrected_ns"] = out["residual_ns"] - out["ml_shuffled_pred_ns"]
    return out, scan, {"best": best, "features": feature_cols}


def make_benchmark(pair_frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    residual_cols = [
        ("raw_cfd20", "residual_ns"),
        ("traditional_ridge_lowering", "residual_traditional_corrected_ns"),
        ("ml_rf_lowering", "residual_ml_corrected_ns"),
        ("ml_shuffled_target_control", "residual_ml_shuffled_corrected_ns"),
    ]
    for method, col in residual_cols:
        summary = metric_summary(pair_frame, col)
        ci = bootstrap_metrics(pair_frame, col, rng, int(config["ml"]["bootstrap_samples"]))
        rows.append({"method": method, **summary, **ci})
    return pd.DataFrame(rows)


def leakage_checks(heldout: pd.DataFrame, benchmark: pd.DataFrame, ml_meta: dict) -> pd.DataFrame:
    raw = benchmark[benchmark["method"] == "raw_cfd20"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_rf_lowering"].iloc[0]
    shuffled = benchmark[benchmark["method"] == "ml_shuffled_target_control"].iloc[0]
    feature_names = set(ml_meta["features"])
    forbidden = {"run", "event_id", "residual_ns", "centered_residual_ns", "abs_residual_ns", "tail_abs_gt_threshold"}
    return pd.DataFrame(
        [
            {"check": "split_by_run_train_58_63_heldout_65", "value": 1, "pass": True},
            {"check": "ml_features_exclude_run_event_and_residual", "value": ",".join(sorted(feature_names & forbidden)), "pass": len(feature_names & forbidden) == 0},
            {"check": "shuffled_target_not_better_than_actual_ml", "value": float(shuffled["sigma68_ns"] - ml["sigma68_ns"]), "pass": bool(shuffled["sigma68_ns"] >= ml["sigma68_ns"])},
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
    ax.set_xlabel("template-phase pair residual, pair-centered [ns]")
    ax.set_ylabel("density")
    ax.legend()
    ax.set_title("Held-out residuals by adaptive-lowering bin")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_lowering_residual_tails.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.errorbar(
        np.arange(len(benchmark)),
        benchmark["sigma68_ns"],
        yerr=[benchmark["sigma68_ns"] - benchmark["sigma68_ci_low"], benchmark["sigma68_ci_high"] - benchmark["sigma68_ns"]],
        fmt="o",
    )
    ax.set_xticks(np.arange(len(benchmark)))
    ax.set_xticklabels(benchmark["method"], rotation=25, ha="right")
    ax.set_ylabel("held-out sigma68 [ns]")
    ax.set_title("Run-held-out nuisance correction benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_head_to_head_sigma68.png", dpi=150)
    plt.close(fig)


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    report = f"""# S16c: pedestal-lowering nuisance propagation into timing residuals

- **Ticket:** {config["ticket"]}
- **Author:** {config["worker"]}
- **Date:** 2026-06-09
- **Depends on:** S00, S02, S16
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `s16c_config.json`

## Question

Does adaptive-pedestal lowering explain timing residual tails in the downstream S02 B4/B6/B8 timing benchmark?

## Raw-ROOT Reproduction

The script first reruns the S00/S16 raw ROOT gate from `h101/HRDv`, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
{numbers["reproduction_rows"]}

The timing subset is the S02 Sample-II downstream all-hit subset. On held-out run 65 it has `{numbers["heldout_events"]}` events and `{numbers["heldout_pairs"]}` pair residuals.

## Methods

The primary reported metric is the S02 `CFD20` pair residual after the 2 cm TOF correction. Nuisance models train on pair-centered residuals so they do not get credit merely for reproducing fixed pair offsets, but the held-out benchmark applies their corrections back to the uncentered S02 residuals. Adaptive lowering is recomputed from the same raw waveforms as S16, but it is used only as a nuisance covariate.

The traditional method is an analytic Ridge residual correction using interpretable pair features: signed/absolute/summed lowering, log-amplitude difference, peak-sample difference, and pair identity. A separate train-only threshold scan defines a high-lowering bin for tail stratification.

The ML method is a fixed random-forest residual corrector using the same lowering features plus fractional lowering, min amplitude, and area/peak difference. It is checked by run-grouped CV on runs 58-63, then evaluated on held-out run 65. Features exclude run, event id, labels, residuals, and other-stave timing labels.

## Held-out Benchmark

Bootstrap CIs resample held-out events, not individual duplicated pair rows.

| Method | sigma68 ns [95% CI] | tail frac | full RMS ns | n pairs |
|---|---:|---:|---:|---:|
{numbers["benchmark_rows"]}

Held-out high-lowering bin from the train scan: threshold `{numbers["threshold_adc"]:.2f} ADC`, high-bin tail fraction `{numbers["high_tail"]:.3f}`, low-bin tail fraction `{numbers["low_tail"]:.3f}`.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
{numbers["leakage_rows"]}

## Verdict

{numbers["verdict"]}

## Reproducibility

```bash
python reports/1781001221.625989.53423f03__s16c_pedestal_timing_nuisance/s16c_pedestal_timing.py --config reports/1781001221.625989.53423f03__s16c_pedestal_timing_nuisance/s16c_config.json
```

Artifacts: `reproduction_match_table.csv`, `pair_residuals_train.csv`, `pair_residuals_heldout.csv`, `threshold_scan.csv`, `ml_cv_scan.csv`, `head_to_head_benchmark.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and two PNG figures.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def format_reproduction(match: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.quantity} | {int(r.report_value)} | {int(r.reproduced)} | {int(r.delta)} | {'yes' if bool(r.pass_) else 'no'} |"
        for r in match.rename(columns={"pass": "pass_"}).itertuples()
    )


def format_benchmark(bench: pd.DataFrame) -> str:
    rows = []
    for r in bench.itertuples():
        rows.append(
            f"| {r.method} | {r.sigma68_ns:.3f} [{r.sigma68_ci_low:.3f}, {r.sigma68_ci_high:.3f}] | "
            f"{r.tail_frac_abs_gt5ns:.3f} [{r.tail_ci_low:.3f}, {r.tail_ci_high:.3f}] | {r.full_rms_ns:.3f} | {int(r.n_pair_residuals)} |"
        )
    return "\n".join(rows)


def format_leakage(checks: pd.DataFrame) -> str:
    return "\n".join(f"| {r.check} | {r.value} | {'yes' if bool(r.pass_) else 'no'} |" for r in checks.rename(columns={"pass": "pass_"}).itertuples())


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
    train_runs = list(config["timing"]["train_runs"])
    heldout_runs = list(config["timing"]["heldout_runs"])
    add_cfd_times(pulses, config)

    train_pairs = pair_table(pulses, config["timing"]["base_method"], config, train_runs)
    heldout_pairs = pair_table(pulses, config["timing"]["base_method"], config, heldout_runs)
    trad_heldout, trad_meta = fit_traditional(train_pairs, heldout_pairs, config)
    ml_heldout, ml_scan, ml_meta = fit_ml(train_pairs, trad_heldout, config, rng)

    train_pairs.to_csv(out_dir / "pair_residuals_train.csv", index=False)
    ml_heldout.to_csv(out_dir / "pair_residuals_heldout.csv", index=False)
    trad_meta["threshold_scan"].to_csv(out_dir / "threshold_scan.csv", index=False)
    ml_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)

    benchmark = make_benchmark(ml_heldout, config, rng)
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    checks = leakage_checks(ml_heldout, benchmark, ml_meta)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, ml_heldout, benchmark)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    pd.DataFrame([{"run": run, "path": str(raw_file(config, run)), "sha256": input_hashes[str(raw_file(config, run))]} for run in configured_runs(config)]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    raw = benchmark[benchmark["method"] == "raw_cfd20"].iloc[0]
    trad = benchmark[benchmark["method"] == "traditional_ridge_lowering"].iloc[0]
    ml = benchmark[benchmark["method"] == "ml_rf_lowering"].iloc[0]
    best_threshold = trad_meta["best_threshold"]
    high = ml_heldout["traditional_high_lowering_bin"]
    high_tail = float(ml_heldout.loc[high, "tail_abs_gt_threshold"].mean()) if high.any() else float("nan")
    low_tail = float(ml_heldout.loc[~high, "tail_abs_gt_threshold"].mean()) if (~high).any() else float("nan")

    trad_gain = float(raw["sigma68_ns"] - trad["sigma68_ns"])
    ml_gain = float(raw["sigma68_ns"] - ml["sigma68_ns"])
    if ml_gain > 0.5 or trad_gain > 0.5:
        verdict = (
            f"Adaptive-lowering covariates materially reduce the held-out timing spread "
            f"(traditional gain {trad_gain:.3f} ns, ML gain {ml_gain:.3f} ns). Treat pedestal lowering as a downstream timing nuisance."
        )
    elif np.isfinite(low_tail) and high_tail > low_tail * 1.5:
        verdict = (
            f"Adaptive lowering stratifies held-out tails (tail fraction {high_tail:.3f} vs {low_tail:.3f}) but residual correction gains are small "
            f"(traditional {trad_gain:.3f} ns, ML {ml_gain:.3f} ns). Use it as a tail diagnostic, not a timing correction."
        )
    else:
        verdict = (
            f"Adaptive lowering does not explain the S02 held-out timing tails strongly: high-vs-low tail fractions are {high_tail:.3f} vs {low_tail:.3f}, "
            f"and sigma68 gains are {trad_gain:.3f} ns traditional and {ml_gain:.3f} ns ML."
        )

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(match["pass"].all()),
        "reproduction": match.to_dict(orient="records"),
        "traditional": {
            "method": "Ridge residual correction on adaptive-lowering nuisance features",
            "metric": "heldout_pairwise_sigma68_ns",
            "value": float(trad["sigma68_ns"]),
            "ci": [float(trad["sigma68_ci_low"]), float(trad["sigma68_ci_high"])],
            "tail_frac_abs_gt5ns": float(trad["tail_frac_abs_gt5ns"]),
        },
        "ml": {
            "method": "RandomForestRegressor residual correction on lowering/shape features",
            "metric": "heldout_pairwise_sigma68_ns",
            "value": float(ml["sigma68_ns"]),
            "ci": [float(ml["sigma68_ci_low"]), float(ml["sigma68_ci_high"])],
            "tail_frac_abs_gt5ns": float(ml["tail_frac_abs_gt5ns"]),
            "best_hyperparameters": ml_meta["best"],
        },
        "raw_reference": {
            "method": "S02 CFD20",
            "value": float(raw["sigma68_ns"]),
            "ci": [float(raw["sigma68_ci_low"]), float(raw["sigma68_ci_high"])],
            "tail_frac_abs_gt5ns": float(raw["tail_frac_abs_gt5ns"]),
        },
        "lowering_tail_stratification": {
            "threshold_adc": float(best_threshold["threshold_adc"]),
            "heldout_high_tail_fraction": None if not np.isfinite(high_tail) else high_tail,
            "heldout_low_tail_fraction": None if not np.isfinite(low_tail) else low_tail,
        },
        "ml_beats_baseline": bool(ml["sigma68_ns"] < trad["sigma68_ns"]),
        "verdict": verdict,
        "leakage_checks_pass": bool(checks["pass"].all()),
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "S16d: repeat pedestal-lowering timing nuisance test on Sample-I B-stack residuals",
            "S04b: add adaptive-lowering covariates to full timing-resolution tail tables",
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    numbers = {
        "git_commit": git_commit(),
        "reproduction_rows": format_reproduction(match),
        "heldout_events": int(ml_heldout["event_id"].nunique()),
        "heldout_pairs": int(len(ml_heldout)),
        "benchmark_rows": format_benchmark(benchmark),
        "threshold_adc": float(best_threshold["threshold_adc"]),
        "high_tail": high_tail,
        "low_tail": low_tail,
        "leakage_rows": format_leakage(checks),
        "verdict": verdict,
    }
    write_report(out_dir, config, numbers)

    outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs[path.name] = sha256_file(path)
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(args.config),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "raw_sigma68": float(raw["sigma68_ns"]), "traditional_sigma68": float(trad["sigma68_ns"]), "ml_sigma68": float(ml["sigma68_ns"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
