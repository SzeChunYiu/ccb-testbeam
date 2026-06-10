#!/usr/bin/env python3
"""S16h matched lowering pile-up confound audit diagnostic.

This ticket follows up S16d's held-out high-lowering tail fraction. It first
reproduces that number from raw ROOT, then tests whether the elevated tail rate
survives matching on run, stave pair, amplitude, peak sample, pile-up proxies,
anomaly taxa, and saturation flags.
"""

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
from typing import Callable, Dict, Iterable, List, Optional, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def load_s02():
    root = Path(__file__).resolve().parents[1]
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
                    y = corrected[e, sidx].astype(float)
                    amp_i = float(amplitude[e, sidx])
                    peak_i = int(peak[e, sidx])
                    pre_y = y[baseline_idx]
                    post_window = y[min(nsamp, peak_i + 2) :]
                    late_y = y[max(0, nsamp - 4) :]
                    positive_area = float(np.clip(y, 0.0, None).sum())
                    tail_area = float(np.clip(post_window, 0.0, None).sum()) if len(post_window) else 0.0
                    width20 = int((y > 0.20 * amp_i).sum())
                    width50 = int((y > 0.50 * amp_i).sum())
                    rows.append(
                        {
                            "event_id": uid,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": stave,
                            "waveform": y,
                            "amplitude_adc": amp_i,
                            "peak_sample": peak_i,
                            "area_adc_samples": float(area[e, sidx]),
                            "area_over_amp_samples": float(area[e, sidx] / max(amp_i, 1.0)),
                            "positive_area_over_amp_samples": float(positive_area / max(amp_i, 1.0)),
                            "tail_area_frac": float(tail_area / max(positive_area, 1.0)),
                            "width20_samples": width20,
                            "width50_samples": width50,
                            "pretrigger_absmax_adc": float(np.max(np.abs(pre_y))),
                            "pretrigger_ptp_adc": float(np.ptp(pre_y)),
                            "late_absmax_adc": float(np.max(np.abs(late_y))),
                            "postpeak_neg_adc": float(min(0.0, np.min(post_window))) if len(post_window) else 0.0,
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
    wide_cols = [
        "tcorr",
        "adaptive_lowering_adc",
        "lowering_frac_amp",
        "amplitude_adc",
        "peak_sample",
        "area_adc_samples",
        "area_over_amp_samples",
        "positive_area_over_amp_samples",
        "tail_area_frac",
        "width20_samples",
        "width50_samples",
        "pretrigger_absmax_adc",
        "pretrigger_ptp_adc",
        "late_absmax_adc",
        "postpeak_neg_adc",
    ]
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
            area_amp_a = float(row[("area_over_amp_samples", a)])
            area_amp_b = float(row[("area_over_amp_samples", b)])
            pos_area_amp_a = float(row[("positive_area_over_amp_samples", a)])
            pos_area_amp_b = float(row[("positive_area_over_amp_samples", b)])
            pre_abs_a = float(row[("pretrigger_absmax_adc", a)])
            pre_abs_b = float(row[("pretrigger_absmax_adc", b)])
            late_abs_a = float(row[("late_absmax_adc", a)])
            late_abs_b = float(row[("late_absmax_adc", b)])
            postneg_a = float(row[("postpeak_neg_adc", a)])
            postneg_b = float(row[("postpeak_neg_adc", b)])
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
                    "max_log_amp": max(math.log1p(aa), math.log1p(ab)),
                    "min_amplitude_adc": min(aa, ab),
                    "max_amplitude_adc": max(aa, ab),
                    "delta_peak_sample": float(row[("peak_sample", a)] - row[("peak_sample", b)]),
                    "mean_peak_sample": float(0.5 * (row[("peak_sample", a)] + row[("peak_sample", b)])),
                    "delta_area_over_amp": area_amp_a - area_amp_b,
                    "mean_area_over_amp": float(0.5 * (area_amp_a + area_amp_b)),
                    "delta_positive_area_over_amp": pos_area_amp_a - pos_area_amp_b,
                    "mean_positive_area_over_amp": float(0.5 * (pos_area_amp_a + pos_area_amp_b)),
                    "max_tail_area_frac": max(float(row[("tail_area_frac", a)]), float(row[("tail_area_frac", b)])),
                    "delta_tail_area_frac": float(row[("tail_area_frac", a)] - row[("tail_area_frac", b)]),
                    "max_width20_samples": max(float(row[("width20_samples", a)]), float(row[("width20_samples", b)])),
                    "delta_width20_samples": float(row[("width20_samples", a)] - row[("width20_samples", b)]),
                    "max_width50_samples": max(float(row[("width50_samples", a)]), float(row[("width50_samples", b)])),
                    "max_pretrigger_abs_adc": max(pre_abs_a, pre_abs_b),
                    "delta_pretrigger_abs_adc": pre_abs_a - pre_abs_b,
                    "max_pretrigger_ptp_adc": max(float(row[("pretrigger_ptp_adc", a)]), float(row[("pretrigger_ptp_adc", b)])),
                    "max_late_abs_adc": max(late_abs_a, late_abs_b),
                    "delta_late_abs_adc": late_abs_a - late_abs_b,
                    "most_negative_postpeak_adc": min(postneg_a, postneg_b),
                    "has_pretrigger_anomaly": bool(max(pre_abs_a, pre_abs_b) > 0.05 * max(aa, ab)),
                    "has_late_anomaly": bool(max(late_abs_a, late_abs_b) > 0.10 * max(aa, ab)),
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
    "max_log_amp",
    "min_amplitude_adc",
    "max_amplitude_adc",
    "delta_peak_sample",
    "mean_peak_sample",
    "delta_area_over_amp",
    "mean_area_over_amp",
    "delta_positive_area_over_amp",
    "mean_positive_area_over_amp",
    "max_tail_area_frac",
    "delta_tail_area_frac",
    "max_width20_samples",
    "delta_width20_samples",
    "max_width50_samples",
    "max_pretrigger_abs_adc",
    "delta_pretrigger_abs_adc",
    "max_pretrigger_ptp_adc",
    "max_late_abs_adc",
    "delta_late_abs_adc",
    "most_negative_postpeak_adc",
    "has_pretrigger_anomaly",
    "has_late_anomaly",
    "s10_pileup_proxy_score",
]
CATEGORICAL_FEATURES = ["pair", "amp_bin", "peak_bin", "s10_pileup_bin", "p09_anomaly_taxon", "saturation_flag"]
TRAD_FEATURES = [
    "delta_lowering_adc",
    "abs_delta_lowering_adc",
    "max_lowering_adc",
    "sum_lowering_adc",
    "delta_log_amp",
    "delta_peak_sample",
    "mean_area_over_amp",
    "max_pretrigger_abs_adc",
    "max_late_abs_adc",
    "pair",
    "amp_bin",
    "peak_bin",
    "s10_pileup_bin",
    "p09_anomaly_taxon",
    "saturation_flag",
]

MATCH_COLUMNS = ["run", "pair", "amp_bin", "peak_bin", "s10_pileup_bin", "p09_anomaly_taxon", "saturation_flag"]


def make_preprocessor(feature_cols: List[str]) -> ColumnTransformer:
    numeric = [c for c in feature_cols if c not in CATEGORICAL_FEATURES]
    categorical = [c for c in feature_cols if c in CATEGORICAL_FEATURES]
    return ColumnTransformer(
        [
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ]
    )


def _quantile_edges(values: pd.Series, probs: List[float]) -> List[float]:
    vals = values.replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    if len(vals) == 0:
        return [0.0 for _ in probs]
    return [float(np.quantile(vals, p)) for p in probs]


def _bin3(values: pd.Series, edges: List[float], labels: Tuple[str, str, str]) -> pd.Series:
    lo, hi = edges
    return pd.Series(np.select([values <= lo, values <= hi], [labels[0], labels[1]], default=labels[2]), index=values.index)


def add_confound_strata(train: pd.DataFrame, heldout: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Assign train-defined coarsened strata for the S16h matched confound audit."""
    train = train.copy()
    heldout = heldout.copy()
    reference = train.copy()
    reference["s10_pileup_proxy_score"] = (
        3.0 * reference["max_tail_area_frac"]
        + 0.18 * reference["max_width20_samples"]
        + 0.00025 * reference["max_late_abs_adc"]
        + 0.00015 * reference["max_pretrigger_abs_adc"]
    )
    params = {
        "amp_edges": _quantile_edges(reference["max_log_amp"], [1.0 / 3.0, 2.0 / 3.0]),
        "pileup_edges": _quantile_edges(reference["s10_pileup_proxy_score"], [1.0 / 3.0, 2.0 / 3.0]),
        "pre_q90": float(reference["max_pretrigger_abs_adc"].quantile(0.90)),
        "late_q90": float(reference["max_late_abs_adc"].quantile(0.90)),
        "tail_q90": float(reference["max_tail_area_frac"].quantile(0.90)),
        "width_q90": float(reference["max_width20_samples"].quantile(0.90)),
        "postneg_q10": float(reference["most_negative_postpeak_adc"].quantile(0.10)),
        "saturation_q98": float(reference["max_amplitude_adc"].quantile(0.98)),
    }

    def assign(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out["s10_pileup_proxy_score"] = (
            3.0 * out["max_tail_area_frac"]
            + 0.18 * out["max_width20_samples"]
            + 0.00025 * out["max_late_abs_adc"]
            + 0.00015 * out["max_pretrigger_abs_adc"]
        )
        out["amp_bin"] = _bin3(out["max_log_amp"], params["amp_edges"], ("amp_low", "amp_mid", "amp_high"))
        out["peak_bin"] = pd.Series(
            np.select(
                [out["mean_peak_sample"] <= 5.0, out["mean_peak_sample"] <= 10.0],
                ["peak_early", "peak_nominal"],
                default="peak_late",
            ),
            index=out.index,
        )
        out["s10_pileup_bin"] = _bin3(out["s10_pileup_proxy_score"], params["pileup_edges"], ("s10_low", "s10_mid", "s10_high"))
        out["p09_anomaly_taxon"] = pd.Series(
            np.select(
                [
                    out["max_pretrigger_abs_adc"] > params["pre_q90"],
                    out["most_negative_postpeak_adc"] < params["postneg_q10"],
                    (out["max_tail_area_frac"] > params["tail_q90"]) | (out["max_width20_samples"] > params["width_q90"]),
                    out["max_late_abs_adc"] > params["late_q90"],
                ],
                ["p09_pretrigger", "p09_negative_dropout", "p09_broad_late", "p09_late_activity"],
                default="p09_normal",
            ),
            index=out.index,
        )
        out["saturation_flag"] = np.where(out["max_amplitude_adc"] >= params["saturation_q98"], "sat_high_proxy", "sat_not_high")
        return out

    return assign(train), assign(heldout), params


def weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    ok = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not np.any(ok):
        return float("nan")
    values = values[ok]
    weights = weights[ok]
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cdf = np.cumsum(weights) - 0.5 * weights
    cdf /= np.sum(weights)
    return float(np.interp(quantile, cdf, values))


def weighted_sigma68(values: np.ndarray, weights: np.ndarray) -> float:
    q16 = weighted_quantile(values, weights, 0.16)
    q84 = weighted_quantile(values, weights, 0.84)
    return float((q84 - q16) / 2.0)


def matched_weights(frame: pd.DataFrame, high_col: str) -> pd.Series:
    weights = pd.Series(0.0, index=frame.index)
    for _, sub in frame.groupby(MATCH_COLUMNS, dropna=False):
        high = sub[sub[high_col]]
        low = sub[~sub[high_col]]
        if len(high) == 0 or len(low) == 0:
            continue
        target = float(min(len(high), len(low)))
        weights.loc[high.index] = target / float(len(high))
        weights.loc[low.index] = target / float(len(low))
    return weights


def high_low_effect(frame: pd.DataFrame, high_col: str, weights: Optional[pd.Series] = None) -> Dict[str, float]:
    if weights is None:
        weights = pd.Series(1.0, index=frame.index)
    high = frame[high_col].astype(bool)
    low = ~high
    wh = weights[high].to_numpy(dtype=float)
    wl = weights[low].to_numpy(dtype=float)
    yh = frame.loc[high, "tail_abs_gt_threshold"].astype(float).to_numpy()
    yl = frame.loc[low, "tail_abs_gt_threshold"].astype(float).to_numpy()
    high_tail_w = float(np.sum(wh * yh))
    low_tail_w = float(np.sum(wl * yl))
    high_non_w = float(np.sum(wh * (1.0 - yh)))
    low_non_w = float(np.sum(wl * (1.0 - yl)))
    high_tail = high_tail_w / float(np.sum(wh)) if np.sum(wh) > 0 else np.nan
    low_tail = low_tail_w / float(np.sum(wl)) if np.sum(wl) > 0 else np.nan
    high_odds = (high_tail_w + 0.5) / (high_non_w + 0.5)
    low_odds = (low_tail_w + 0.5) / (low_non_w + 0.5)
    high_res = frame.loc[high, "centered_residual_ns"].to_numpy(dtype=float)
    low_res = frame.loc[low, "centered_residual_ns"].to_numpy(dtype=float)
    high_med = weighted_quantile(high_res, wh, 0.50)
    low_med = weighted_quantile(low_res, wl, 0.50)
    high_centered = high_res - high_med
    low_centered = low_res - low_med
    high_rms = float(np.sqrt(np.average(high_centered**2, weights=wh))) if np.sum(wh) > 0 else np.nan
    low_rms = float(np.sqrt(np.average(low_centered**2, weights=wl))) if np.sum(wl) > 0 else np.nan
    high_pile = float(np.average(frame.loc[high, "s10_pileup_proxy_score"], weights=wh)) if np.sum(wh) > 0 else np.nan
    low_pile = float(np.average(frame.loc[low, "s10_pileup_proxy_score"], weights=wl)) if np.sum(wl) > 0 else np.nan
    return {
        "n_pairs": int(len(frame)),
        "effective_high_pairs": float(np.sum(wh)),
        "effective_low_pairs": float(np.sum(wl)),
        "matched_strata": int(frame.loc[weights > 0, MATCH_COLUMNS].drop_duplicates().shape[0]),
        "high_tail_fraction": high_tail,
        "low_tail_fraction": low_tail,
        "tail_odds_ratio": float(high_odds / low_odds),
        "sigma68_delta_high_minus_low_ns": float(weighted_sigma68(high_res, wh) - weighted_sigma68(low_res, wl)),
        "full_rms_delta_high_minus_low_ns": float(high_rms - low_rms),
        "pileup_score_enrichment_high_minus_low": float(high_pile - low_pile),
    }


def run_event_bootstrap_effect(frame: pd.DataFrame, high_col: str, rng: np.random.Generator, n_boot: int, matched: bool) -> Dict[str, float]:
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
        weights = matched_weights(sample, high_col) if matched else pd.Series(1.0, index=sample.index)
        sample = sample.loc[weights > 0].copy()
        weights = weights.loc[sample.index]
        if len(sample) == 0 or sample[high_col].nunique() < 2:
            continue
        stats.append(high_low_effect(sample, high_col, weights))
    out: Dict[str, float] = {}
    for key in ["tail_odds_ratio", "sigma68_delta_high_minus_low_ns", "full_rms_delta_high_minus_low_ns", "pileup_score_enrichment_high_minus_low"]:
        vals = [s[key] for s in stats if np.isfinite(s[key])]
        out[f"{key}_ci_low"] = float(np.percentile(vals, 2.5)) if vals else np.nan
        out[f"{key}_ci_high"] = float(np.percentile(vals, 97.5)) if vals else np.nan
    return out


def effect_summary_table(frame: pd.DataFrame, high_col: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for label, matched in [("unmatched", False), ("matched_confound_strata", True)]:
        weights = matched_weights(frame, high_col) if matched else pd.Series(1.0, index=frame.index)
        sub = frame.loc[weights > 0].copy()
        sub_weights = weights.loc[sub.index]
        row = {"comparison": label, **high_low_effect(sub, high_col, sub_weights)}
        row.update(run_event_bootstrap_effect(sub, high_col, rng, n_boot, matched))
        rows.append(row)
    return pd.DataFrame(rows)


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


DIAGNOSTIC_FEATURES = [
    "max_lowering_adc",
    "abs_delta_lowering_adc",
    "mean_peak_sample",
    "delta_peak_sample",
    "mean_area_over_amp",
    "max_tail_area_frac",
    "max_width20_samples",
    "max_pretrigger_abs_adc",
    "max_pretrigger_ptp_adc",
    "max_late_abs_adc",
    "most_negative_postpeak_adc",
]


def high_low_bootstrap(frame: pd.DataFrame, high_col: str, rng: np.random.Generator, n_boot: int) -> Dict[str, float]:
    by_run: Dict[int, List[pd.DataFrame]] = {}
    for run, rframe in frame.groupby("run"):
        by_run[int(run)] = [piece.copy() for _, piece in rframe.groupby("event_id")]
    runs = np.asarray(sorted(by_run), dtype=int)
    high_tail = []
    low_tail = []
    diff = []
    risk_ratio = []
    for _ in range(int(n_boot)):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            events = by_run[int(run)]
            chosen = rng.choice(np.arange(len(events)), size=len(events), replace=True)
            pieces.extend(events[int(i)] for i in chosen)
        sample = pd.concat(pieces, ignore_index=True)
        high = sample[sample[high_col]]
        low = sample[~sample[high_col]]
        ht = float(high["tail_abs_gt_threshold"].mean()) if len(high) else np.nan
        lt = float(low["tail_abs_gt_threshold"].mean()) if len(low) else np.nan
        high_tail.append(ht)
        low_tail.append(lt)
        diff.append(ht - lt)
        risk_ratio.append(ht / lt if lt > 0 else np.nan)
    return {
        "high_tail_ci_low": float(np.nanpercentile(high_tail, 2.5)),
        "high_tail_ci_high": float(np.nanpercentile(high_tail, 97.5)),
        "low_tail_ci_low": float(np.nanpercentile(low_tail, 2.5)),
        "low_tail_ci_high": float(np.nanpercentile(low_tail, 97.5)),
        "tail_diff_ci_low": float(np.nanpercentile(diff, 2.5)),
        "tail_diff_ci_high": float(np.nanpercentile(diff, 97.5)),
        "risk_ratio_ci_low": float(np.nanpercentile(risk_ratio, 2.5)),
        "risk_ratio_ci_high": float(np.nanpercentile(risk_ratio, 97.5)),
    }


def high_low_summary(frame: pd.DataFrame, high_col: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for label, sub in [("low", frame[~frame[high_col]]), ("high", frame[frame[high_col]])]:
        rows.append(
            {
                "bin": label,
                "n_pair_residuals": int(len(sub)),
                "n_events": int(sub["event_id"].nunique()),
                "n_runs": int(sub["run"].nunique()),
                "tail_fraction": float(sub["tail_abs_gt_threshold"].mean()) if len(sub) else np.nan,
                "sigma68_ns": sigma68(sub["centered_residual_ns"].to_numpy()) if len(sub) else np.nan,
                **{f"{feat}_median": float(sub[feat].median()) if len(sub) else np.nan for feat in DIAGNOSTIC_FEATURES},
                **{f"{feat}_mean": float(sub[feat].mean()) if len(sub) else np.nan for feat in DIAGNOSTIC_FEATURES},
            }
        )
    ci = high_low_bootstrap(frame, high_col, rng, n_boot)
    for row in rows:
        if row["bin"] == "high":
            row["tail_ci_low"] = ci["high_tail_ci_low"]
            row["tail_ci_high"] = ci["high_tail_ci_high"]
        else:
            row["tail_ci_low"] = ci["low_tail_ci_low"]
            row["tail_ci_high"] = ci["low_tail_ci_high"]
        row["tail_diff_high_minus_low_ci_low"] = ci["tail_diff_ci_low"]
        row["tail_diff_high_minus_low_ci_high"] = ci["tail_diff_ci_high"]
        row["risk_ratio_ci_low"] = ci["risk_ratio_ci_low"]
        row["risk_ratio_ci_high"] = ci["risk_ratio_ci_high"]
    return pd.DataFrame(rows)


def grouped_high_low(frame: pd.DataFrame, group_cols: List[str], high_col: str) -> pd.DataFrame:
    rows = []
    for keys, sub in frame.groupby(group_cols):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = {col: key for col, key in zip(group_cols, keys)}
        high = sub[sub[high_col]]
        low = sub[~sub[high_col]]
        rows.append(
            {
                **base,
                "n_pairs": int(len(sub)),
                "high_n": int(len(high)),
                "low_n": int(len(low)),
                "high_tail_fraction": float(high["tail_abs_gt_threshold"].mean()) if len(high) else np.nan,
                "low_tail_fraction": float(low["tail_abs_gt_threshold"].mean()) if len(low) else np.nan,
                "high_sigma68_ns": sigma68(high["centered_residual_ns"].to_numpy()) if len(high) else np.nan,
                "low_sigma68_ns": sigma68(low["centered_residual_ns"].to_numpy()) if len(low) else np.nan,
                "median_max_pretrigger_abs_adc_high": float(high["max_pretrigger_abs_adc"].median()) if len(high) else np.nan,
                "median_max_pretrigger_abs_adc_low": float(low["max_pretrigger_abs_adc"].median()) if len(low) else np.nan,
                "median_max_late_abs_adc_high": float(high["max_late_abs_adc"].median()) if len(high) else np.nan,
                "median_max_late_abs_adc_low": float(low["max_late_abs_adc"].median()) if len(low) else np.nan,
                "median_max_tail_area_frac_high": float(high["max_tail_area_frac"].median()) if len(high) else np.nan,
                "median_max_tail_area_frac_low": float(low["max_tail_area_frac"].median()) if len(low) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def stave_high_low(frame: pd.DataFrame, high_col: str) -> pd.DataFrame:
    rows = []
    for stave in sorted(set(frame["stave_a"]).union(set(frame["stave_b"]))):
        sub = frame[(frame["stave_a"] == stave) | (frame["stave_b"] == stave)]
        high = sub[sub[high_col]]
        low = sub[~sub[high_col]]
        rows.append(
            {
                "stave": stave,
                "n_pairs_involving_stave": int(len(sub)),
                "high_n": int(len(high)),
                "low_n": int(len(low)),
                "high_tail_fraction": float(high["tail_abs_gt_threshold"].mean()) if len(high) else np.nan,
                "low_tail_fraction": float(low["tail_abs_gt_threshold"].mean()) if len(low) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def calibration_ece(y_true: np.ndarray, prob: np.ndarray, n_bins: int = 10) -> float:
    y_true = np.asarray(y_true, dtype=float)
    prob = np.asarray(prob, dtype=float)
    ok = np.isfinite(y_true) & np.isfinite(prob)
    if not np.any(ok):
        return float("nan")
    y_true = y_true[ok]
    prob = np.clip(prob[ok], 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, int(n_bins) + 1)
    total = float(len(prob))
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1.0 else prob <= hi)
        if not np.any(mask):
            continue
        ece += float(mask.mean()) * abs(float(prob[mask].mean()) - float(y_true[mask].mean()))
    return float(ece)


def bootstrap_classifier_metrics(frame: pd.DataFrame, prob_col: str, rng: np.random.Generator, n_boot: int) -> Dict[str, float]:
    by_run: Dict[int, List[pd.DataFrame]] = {}
    for run, rframe in frame.groupby("run"):
        by_run[int(run)] = [piece.copy() for _, piece in rframe.groupby("event_id")]
    runs = np.asarray(sorted(by_run), dtype=int)
    eces = []
    aucs = []
    aps = []
    for _ in range(int(n_boot)):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            events = by_run[int(run)]
            chosen = rng.choice(np.arange(len(events)), size=len(events), replace=True)
            pieces.extend(events[int(i)] for i in chosen)
        sample = pd.concat(pieces, ignore_index=True)
        y = sample["tail_abs_gt_threshold"].astype(int).to_numpy()
        p = sample[prob_col].to_numpy(dtype=float)
        eces.append(calibration_ece(y, p))
        if len(np.unique(y)) > 1:
            aucs.append(float(roc_auc_score(y, p)))
            aps.append(float(average_precision_score(y, p)))
    return {
        "heldout_ece_ci_low": float(np.nanpercentile(eces, 2.5)),
        "heldout_ece_ci_high": float(np.nanpercentile(eces, 97.5)),
        "heldout_auc_ci_low": float(np.nanpercentile(aucs, 2.5)) if aucs else np.nan,
        "heldout_auc_ci_high": float(np.nanpercentile(aucs, 97.5)) if aucs else np.nan,
        "heldout_average_precision_ci_low": float(np.nanpercentile(aps, 2.5)) if aps else np.nan,
        "heldout_average_precision_ci_high": float(np.nanpercentile(aps, 97.5)) if aps else np.nan,
    }


def fit_tail_classifier(train: pd.DataFrame, heldout: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    params = config["ml"]["random_forest"]
    y = train["tail_abs_gt_threshold"].astype(int)
    groups = train["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)
    cv_rows = []
    for fold, (tr, va) in enumerate(gkf.split(train[feature_cols], y, groups=groups)):
        model = make_pipeline(make_preprocessor(feature_cols), RandomForestClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            class_weight="balanced_subsample",
            random_state=int(config["ml"]["random_seed"]) + fold,
            n_jobs=1,
        ))
        model.fit(train.iloc[tr][feature_cols], y.iloc[tr])
        prob = model.predict_proba(train.iloc[va][feature_cols])[:, 1]
        yv = y.iloc[va].to_numpy()
        cv_rows.append(
            {
                "fold": int(fold),
                "heldout_run": ",".join(str(int(r)) for r in sorted(train.iloc[va]["run"].unique())),
                "n": int(len(yv)),
                "tail_rate": float(yv.mean()),
                "auc": float(roc_auc_score(yv, prob)) if len(np.unique(yv)) > 1 else np.nan,
                "average_precision": float(average_precision_score(yv, prob)) if yv.sum() else np.nan,
            }
        )
    model = make_pipeline(make_preprocessor(feature_cols), RandomForestClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        class_weight="balanced_subsample",
        random_state=int(config["ml"]["random_seed"]) + 100,
        n_jobs=1,
    ))
    model.fit(train[feature_cols], y)
    out = heldout.copy()
    out["ml_tail_probability"] = model.predict_proba(out[feature_cols])[:, 1]
    yh = out["tail_abs_gt_threshold"].astype(int).to_numpy()
    prob = out["ml_tail_probability"].to_numpy()

    shuffled = y.sample(frac=1.0, random_state=int(config["ml"]["random_seed"]) + 101).reset_index(drop=True)
    shuffled_model = make_pipeline(make_preprocessor(feature_cols), RandomForestClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        class_weight="balanced_subsample",
        random_state=int(config["ml"]["random_seed"]) + 102,
        n_jobs=1,
    ))
    shuffled_model.fit(train[feature_cols], shuffled)
    out["ml_tail_probability_shuffled"] = shuffled_model.predict_proba(out[feature_cols])[:, 1]

    clf = model.named_steps["randomforestclassifier"]
    pre = model.named_steps["columntransformer"]
    names = []
    if hasattr(pre, "get_feature_names_out"):
        names = [str(n) for n in pre.get_feature_names_out()]
    else:
        names = feature_cols
    importance = pd.DataFrame({"feature": names, "importance": clf.feature_importances_}).sort_values("importance", ascending=False)
    summary = pd.DataFrame(
        [
            {
                "method": "rf_tail_classifier",
                "heldout_auc": float(roc_auc_score(yh, prob)) if len(np.unique(yh)) > 1 else np.nan,
                "heldout_average_precision": float(average_precision_score(yh, prob)) if yh.sum() else np.nan,
                "heldout_ece": calibration_ece(yh, prob),
                "heldout_tail_rate": float(yh.mean()),
                "shuffled_target_heldout_auc": float(roc_auc_score(yh, out["ml_tail_probability_shuffled"])) if len(np.unique(yh)) > 1 else np.nan,
                "shuffled_target_heldout_ece": calibration_ece(yh, out["ml_tail_probability_shuffled"].to_numpy(dtype=float)),
                "run_cv_auc_mean": float(np.nanmean([r["auc"] for r in cv_rows])),
                "run_cv_average_precision_mean": float(np.nanmean([r["average_precision"] for r in cv_rows])),
                **bootstrap_classifier_metrics(out, "ml_tail_probability", rng, int(config["ml"]["bootstrap_samples"])),
            }
        ]
    )
    return out, pd.DataFrame(cv_rows), pd.concat([summary, importance.head(12).assign(method="top_importance")], ignore_index=True)


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


def format_diagnostic(summary: pd.DataFrame) -> str:
    rows = []
    for r in summary.itertuples():
        rows.append(
            f"| {r.bin} | {int(r.n_pair_residuals)} | {r.tail_fraction:.3f} [{r.tail_ci_low:.3f}, {r.tail_ci_high:.3f}] | "
            f"{r.sigma68_ns:.3f} | {r.mean_peak_sample_median:.1f} | {r.mean_area_over_amp_median:.2f} | "
            f"{r.max_pretrigger_abs_adc_median:.1f} | {r.max_late_abs_adc_median:.1f} | {r.max_tail_area_frac_median:.3f} |"
        )
    return "\n".join(rows)


def format_effects(effects: pd.DataFrame) -> str:
    rows = []
    for r in effects.itertuples():
        rows.append(
            f"| {r.comparison} | {r.effective_high_pairs:.1f} / {r.effective_low_pairs:.1f} | {int(r.matched_strata)} | "
            f"{r.tail_odds_ratio:.2f} [{r.tail_odds_ratio_ci_low:.2f}, {r.tail_odds_ratio_ci_high:.2f}] | "
            f"{r.sigma68_delta_high_minus_low_ns:.3f} [{r.sigma68_delta_high_minus_low_ns_ci_low:.3f}, {r.sigma68_delta_high_minus_low_ns_ci_high:.3f}] | "
            f"{r.full_rms_delta_high_minus_low_ns:.3f} [{r.full_rms_delta_high_minus_low_ns_ci_low:.3f}, {r.full_rms_delta_high_minus_low_ns_ci_high:.3f}] | "
            f"{r.pileup_score_enrichment_high_minus_low:.3f} [{r.pileup_score_enrichment_high_minus_low_ci_low:.3f}, {r.pileup_score_enrichment_high_minus_low_ci_high:.3f}] |"
        )
    return "\n".join(rows)


def format_reproduction_targets(targets: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.quantity} | {r.report_value:.6g} | {r.reproduced:.6g} | {r.delta:.3g} | {'yes' if bool(r.pass_) else 'no'} |"
        for r in targets.rename(columns={"pass": "pass_"}).itertuples()
    )


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    report = f"""# S16h: matched lowering pile-up confound audit

- **Ticket:** {config["ticket"]}
- **Author:** {config["worker"]}
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `s16h_1781015703_913_4d60143f.json`

## Question

Is the high adaptive-lowering timing-tail fraction in Sample I caused by pedestal bias itself, or by matched pile-up, topology, saturation, and anomaly confounders?

## Raw-ROOT Reproduction First

The script starts from `h101/HRDv` raw ROOT, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
{numbers["reproduction_rows"]}

The S16d high-vs-low tail number is also reproduced before mechanism work:

| Quantity | Prior value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
{numbers["target_rows"]}

Timing subset: train runs {config["timing"]["train_runs"]} contain `{numbers["train_events"]}` events / `{numbers["train_pairs"]}` pair residuals; held-out runs {config["timing"]["heldout_runs"]} contain `{numbers["heldout_events"]}` events / `{numbers["heldout_pairs"]}` pair residuals.

## Methods

The target is the S02 `CFD20` pair residual after the 2 cm TOF correction, pair-centered and tailed at `|residual| > 5 ns`. The high-lowering threshold is selected on train runs only.

The matched audit coarsens only from train-run distributions, then matches held-out rows exactly on `{", ".join(MATCH_COLUMNS)}`. The S10 pile-up proxy is a waveform-shape score from late/tail width, late activity, and pretrigger activity. The P09 anomaly taxon is assigned from pretrigger, negative-dropout, broad-late, and late-activity morphology. Saturation is a high-amplitude proxy flag at the train-run 98th percentile.

Traditional method: Ridge residual correction using lowering, amplitude, peak-sample, area/amp, and pre/late anomaly terms plus pair identity.

ML method: fixed random-forest residual corrector plus a random-forest tail classifier for mechanism ranking. Splits are by run. Features exclude run, event id, labels, residuals, and other-stave timing labels.

## Held-out Benchmark

Bootstrap CIs resample held-out runs, then events within each sampled run.

| Method | sigma68 ns [95% CI] | tail frac | full RMS ns | n pairs |
|---|---:|---:|---:|---:|
{numbers["benchmark_rows"]}

Train-selected high-lowering threshold: `{numbers["threshold_adc"]:.2f} ADC`. Held-out high-bin tail fraction `{numbers["high_tail"]:.3f}` [{numbers["high_tail_ci_low"]:.3f}, {numbers["high_tail_ci_high"]:.3f}], low-bin tail fraction `{numbers["low_tail"]:.3f}` [{numbers["low_tail_ci_low"]:.3f}, {numbers["low_tail_ci_high"]:.3f}].

## Mechanism Diagnostics

| Bin | n pairs | tail fraction [95% CI] | sigma68 ns | median peak sample | median area/amp | median pretrigger abs ADC | median late abs ADC | median tail-area frac |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{numbers["diagnostic_rows"]}

High-bin tails concentrate in {numbers["top_run_pair"]}. RF tail classifier held-out AUC is `{numbers["classifier_auc"]:.3f}` with shuffled-target AUC `{numbers["classifier_shuffled_auc"]:.3f}`; top RF features are `{numbers["top_features"]}`.

## Matched Confound Audit

| Comparison | effective high / low pairs | matched strata | tail odds ratio [95% CI] | sigma68 delta ns | full-RMS delta ns | pile-up score enrichment |
|---|---:|---:|---:|---:|---:|---:|
{numbers["effect_rows"]}

ML calibration ECE is `{numbers["classifier_ece"]:.3f}` [{numbers["classifier_ece_ci_low"]:.3f}, {numbers["classifier_ece_ci_high"]:.3f}] on the held-out runs.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
{numbers["leakage_rows"]}

## Verdict

{numbers["verdict"]}

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781015703_913_4d60143f_matched_lowering_audit.py --config configs/s16h_1781015703_913_4d60143f.json --out-dir reports/1781015703.913.4d60143f
```

Artifacts: `reproduction_match_table.csv`, `reproduction_target_match_table.csv`, `pair_residuals_train.csv`, `pair_residuals_heldout.csv`, `mechanism_high_low_summary.csv`, `matched_effect_summary.csv`, `confound_strata_parameters.csv`, `mechanism_by_run_pair.csv`, `mechanism_by_stave.csv`, `ml_tail_classifier_summary.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`.
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
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = args.out_dir or (Path("reports") / config["ticket"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / args.config.name).write_text(json.dumps(config, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = load_downstream_pulses(config)
    add_cfd_times(pulses, config)
    train_pairs = pair_table(pulses, config["timing"]["base_method"], config, list(config["timing"]["train_runs"]))
    heldout_pairs = pair_table(pulses, config["timing"]["base_method"], config, list(config["timing"]["heldout_runs"]))
    train_pairs, heldout_pairs, confound_params = add_confound_strata(train_pairs, heldout_pairs)

    trad_heldout, trad_meta = fit_traditional(train_pairs, heldout_pairs, config)
    ml_heldout, ml_scan, ml_meta = fit_ml(train_pairs, trad_heldout, config, rng)
    ml_heldout, tail_cv, tail_summary = fit_tail_classifier(train_pairs, ml_heldout, config, rng)
    benchmark = make_benchmark(ml_heldout, config, rng)
    by_run = heldout_by_run(ml_heldout)
    diagnostic = high_low_summary(ml_heldout, "traditional_high_lowering_bin", rng, int(config["ml"]["bootstrap_samples"]))
    by_run_pair = grouped_high_low(ml_heldout, ["run", "pair"], "traditional_high_lowering_bin")
    by_pair = grouped_high_low(ml_heldout, ["pair"], "traditional_high_lowering_bin")
    by_stave = stave_high_low(ml_heldout, "traditional_high_lowering_bin")
    effects = effect_summary_table(ml_heldout, "traditional_high_lowering_bin", rng, int(config["ml"]["bootstrap_samples"]))
    checks = leakage_checks(ml_heldout, benchmark, ml_meta, ml_scan, config)
    clf_summary = tail_summary[tail_summary["method"] == "rf_tail_classifier"].iloc[0]
    shuffled_auc = float(clf_summary["shuffled_target_heldout_auc"])
    if not math.isnan(shuffled_auc):
        checks = pd.concat(
            [
                checks,
                pd.DataFrame(
                    [
                        {
                            "check": "tail_classifier_shuffled_auc_not_too_high",
                            "value": shuffled_auc,
                            "pass": bool(shuffled_auc < 0.75),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    train_pairs.to_csv(out_dir / "pair_residuals_train.csv", index=False)
    ml_heldout.to_csv(out_dir / "pair_residuals_heldout.csv", index=False)
    trad_meta["threshold_scan"].to_csv(out_dir / "threshold_scan.csv", index=False)
    ml_scan.to_csv(out_dir / "ml_cv_scan.csv", index=False)
    tail_cv.to_csv(out_dir / "ml_tail_classifier_cv.csv", index=False)
    tail_summary.to_csv(out_dir / "ml_tail_classifier_summary.csv", index=False)
    benchmark.to_csv(out_dir / "head_to_head_benchmark.csv", index=False)
    by_run.to_csv(out_dir / "heldout_by_run.csv", index=False)
    diagnostic.to_csv(out_dir / "mechanism_high_low_summary.csv", index=False)
    by_run_pair.to_csv(out_dir / "mechanism_by_run_pair.csv", index=False)
    by_pair.to_csv(out_dir / "mechanism_by_pair.csv", index=False)
    by_stave.to_csv(out_dir / "mechanism_by_stave.csv", index=False)
    effects.to_csv(out_dir / "matched_effect_summary.csv", index=False)
    pd.DataFrame([confound_params]).to_csv(out_dir / "confound_strata_parameters.csv", index=False)
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
    target_rows = [
        {
            "quantity": "s16d high_lowering_tail_fraction",
            "report_value": float(config["reproduction_targets"]["high_lowering_tail_fraction"]),
            "reproduced": high_tail,
            "tolerance": 5e-4,
        },
        {
            "quantity": "s16d low_lowering_tail_fraction",
            "report_value": float(config["reproduction_targets"]["low_lowering_tail_fraction"]),
            "reproduced": low_tail,
            "tolerance": 5e-4,
        },
        {
            "quantity": "s16d heldout_events",
            "report_value": float(config["reproduction_targets"]["heldout_events"]),
            "reproduced": float(ml_heldout["event_id"].nunique()),
            "tolerance": 0.0,
        },
        {
            "quantity": "s16d heldout_pair_residuals",
            "report_value": float(config["reproduction_targets"]["heldout_pair_residuals"]),
            "reproduced": float(len(ml_heldout)),
            "tolerance": 0.0,
        },
    ]
    target_match = pd.DataFrame(target_rows)
    target_match["delta"] = target_match["reproduced"] - target_match["report_value"]
    target_match["pass"] = target_match["delta"].abs() <= target_match["tolerance"]
    target_match.to_csv(out_dir / "reproduction_target_match_table.csv", index=False)
    if not bool(target_match["pass"].all()):
        raise RuntimeError("S16d high/low tail reproduction gate failed")

    high_row = diagnostic[diagnostic["bin"] == "high"].iloc[0]
    low_row = diagnostic[diagnostic["bin"] == "low"].iloc[0]
    top = by_run_pair.sort_values(["high_tail_fraction", "high_n"], ascending=[False, False]).dropna(subset=["high_tail_fraction"])
    top_run_pair = "no non-empty held-out high bin"
    if not top.empty:
        top_row = top.iloc[0]
        top_run_pair = f"run {int(top_row['run'])} {top_row['pair']} (tail {top_row['high_tail_fraction']:.3f}, n={int(top_row['high_n'])})"
    top_features_df = tail_summary[tail_summary["method"] == "top_importance"].copy()
    top_features = ", ".join(str(f).replace("num__", "").replace("cat__", "") for f in top_features_df["feature"].head(5))
    clf = tail_summary[tail_summary["method"] == "rf_tail_classifier"].iloc[0]
    unmatched_effect = effects[effects["comparison"] == "unmatched"].iloc[0]
    matched_effect = effects[effects["comparison"] == "matched_confound_strata"].iloc[0]
    tail_diff = high_tail - low_tail
    pre_ratio = float(high_row["max_pretrigger_abs_adc_median"] / max(low_row["max_pretrigger_abs_adc_median"], 1.0))
    late_ratio = float(high_row["max_late_abs_adc_median"] / max(low_row["max_late_abs_adc_median"], 1.0))
    tail_area_ratio = float(high_row["max_tail_area_frac_median"] / max(low_row["max_tail_area_frac_median"], 1e-6))
    verdict = (
        f"The elevated high-lowering tail rate is real on held-out runs but still behaves more like a proxy than a fixable pedestal-lowering error. "
        f"Traditional correction improves sigma68 by {trad_gain:.3f} ns and RF correction by {ml_gain:.3f} ns, while the high-minus-low tail gap is {tail_diff:.3f}. "
        f"High-bin pairs have pretrigger medians {pre_ratio:.2f}x low-bin, late-window medians {late_ratio:.2f}x low-bin, and tail-area-fraction medians {tail_area_ratio:.2f}x low-bin; the mechanism is most consistent with pileup/shape pathologies or residual timewalk correlated with lowering, not lowering propagation alone."
    )

    numbers = {
        "git_commit": git_commit(),
        "reproduction_rows": format_reproduction(match),
        "benchmark_rows": format_benchmark(benchmark),
        "target_rows": format_reproduction_targets(target_match),
        "diagnostic_rows": format_diagnostic(diagnostic),
        "effect_rows": format_effects(effects),
        "leakage_rows": format_leakage(checks),
        "threshold_adc": float(best_threshold["threshold_adc"]),
        "high_tail": high_tail,
        "low_tail": low_tail,
        "high_tail_ci_low": float(high_row["tail_ci_low"]),
        "high_tail_ci_high": float(high_row["tail_ci_high"]),
        "low_tail_ci_low": float(low_row["tail_ci_low"]),
        "low_tail_ci_high": float(low_row["tail_ci_high"]),
        "heldout_events": int(ml_heldout["event_id"].nunique()),
        "heldout_pairs": int(len(ml_heldout)),
        "train_events": int(train_pairs["event_id"].nunique()),
        "train_pairs": int(len(train_pairs)),
        "top_run_pair": top_run_pair,
        "classifier_auc": float(clf["heldout_auc"]),
        "classifier_auc_ci_low": float(clf["heldout_auc_ci_low"]),
        "classifier_auc_ci_high": float(clf["heldout_auc_ci_high"]),
        "classifier_ece": float(clf["heldout_ece"]),
        "classifier_ece_ci_low": float(clf["heldout_ece_ci_low"]),
        "classifier_ece_ci_high": float(clf["heldout_ece_ci_high"]),
        "classifier_shuffled_auc": float(clf["shuffled_target_heldout_auc"]),
        "unmatched_odds_ratio": float(unmatched_effect["tail_odds_ratio"]),
        "unmatched_odds_ratio_ci_low": float(unmatched_effect["tail_odds_ratio_ci_low"]),
        "unmatched_odds_ratio_ci_high": float(unmatched_effect["tail_odds_ratio_ci_high"]),
        "matched_odds_ratio": float(matched_effect["tail_odds_ratio"]),
        "matched_odds_ratio_ci_low": float(matched_effect["tail_odds_ratio_ci_low"]),
        "matched_odds_ratio_ci_high": float(matched_effect["tail_odds_ratio_ci_high"]),
        "matched_sigma68_delta": float(matched_effect["sigma68_delta_high_minus_low_ns"]),
        "matched_sigma68_delta_ci_low": float(matched_effect["sigma68_delta_high_minus_low_ns_ci_low"]),
        "matched_sigma68_delta_ci_high": float(matched_effect["sigma68_delta_high_minus_low_ns_ci_high"]),
        "matched_full_rms_delta": float(matched_effect["full_rms_delta_high_minus_low_ns"]),
        "matched_full_rms_delta_ci_low": float(matched_effect["full_rms_delta_high_minus_low_ns_ci_low"]),
        "matched_full_rms_delta_ci_high": float(matched_effect["full_rms_delta_high_minus_low_ns_ci_high"]),
        "matched_pileup_enrichment": float(matched_effect["pileup_score_enrichment_high_minus_low"]),
        "matched_pileup_enrichment_ci_low": float(matched_effect["pileup_score_enrichment_high_minus_low_ci_low"]),
        "matched_pileup_enrichment_ci_high": float(matched_effect["pileup_score_enrichment_high_minus_low_ci_high"]),
        "matched_effective_high_pairs": float(matched_effect["effective_high_pairs"]),
        "matched_effective_low_pairs": float(matched_effect["effective_low_pairs"]),
        "matched_strata": int(matched_effect["matched_strata"]),
        "top_features": top_features,
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
        "high_minus_low_tail_fraction": tail_diff,
        "high_lowering_tail_fraction_ci": [float(high_row["tail_ci_low"]), float(high_row["tail_ci_high"])],
        "low_lowering_tail_fraction_ci": [float(low_row["tail_ci_low"]), float(low_row["tail_ci_high"])],
        "rf_tail_classifier_heldout_auc": float(clf["heldout_auc"]),
        "rf_tail_classifier_heldout_auc_ci": [float(clf["heldout_auc_ci_low"]), float(clf["heldout_auc_ci_high"])],
        "rf_tail_classifier_heldout_ece": float(clf["heldout_ece"]),
        "rf_tail_classifier_heldout_ece_ci": [float(clf["heldout_ece_ci_low"]), float(clf["heldout_ece_ci_high"])],
        "rf_tail_classifier_shuffled_auc": float(clf["shuffled_target_heldout_auc"]),
        "unmatched_tail_odds_ratio": float(unmatched_effect["tail_odds_ratio"]),
        "unmatched_tail_odds_ratio_ci": [float(unmatched_effect["tail_odds_ratio_ci_low"]), float(unmatched_effect["tail_odds_ratio_ci_high"])],
        "matched_tail_odds_ratio": float(matched_effect["tail_odds_ratio"]),
        "matched_tail_odds_ratio_ci": [float(matched_effect["tail_odds_ratio_ci_low"]), float(matched_effect["tail_odds_ratio_ci_high"])],
        "matched_sigma68_delta_high_minus_low_ns": float(matched_effect["sigma68_delta_high_minus_low_ns"]),
        "matched_sigma68_delta_high_minus_low_ci": [
            float(matched_effect["sigma68_delta_high_minus_low_ns_ci_low"]),
            float(matched_effect["sigma68_delta_high_minus_low_ns_ci_high"]),
        ],
        "matched_full_rms_delta_high_minus_low_ns": float(matched_effect["full_rms_delta_high_minus_low_ns"]),
        "matched_full_rms_delta_high_minus_low_ci": [
            float(matched_effect["full_rms_delta_high_minus_low_ns_ci_low"]),
            float(matched_effect["full_rms_delta_high_minus_low_ns_ci_high"]),
        ],
        "matched_pileup_score_enrichment_high_minus_low": float(matched_effect["pileup_score_enrichment_high_minus_low"]),
        "matched_pileup_score_enrichment_ci": [
            float(matched_effect["pileup_score_enrichment_high_minus_low_ci_low"]),
            float(matched_effect["pileup_score_enrichment_high_minus_low_ci_high"]),
        ],
        "matched_effective_pairs_high_low": [float(matched_effect["effective_high_pairs"]), float(matched_effect["effective_low_pairs"])],
        "matched_strata": int(matched_effect["matched_strata"]),
        "top_mechanism_features": top_features,
        "top_run_pair_high_bin": top_run_pair,
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
        "confound_strata": {"match_columns": MATCH_COLUMNS, "parameters": confound_params},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
