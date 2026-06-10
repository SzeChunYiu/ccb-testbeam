#!/usr/bin/env python3
"""S16m pseudo-pedestal charge/live-time bias closure.

The study reads raw HRDB ROOT, reproduces the S00 selected-pulse count, freezes
several pre-trigger pseudo-pedestal estimators, propagates them into duplicate
readout charge closure and live-time/pile-up summaries, then benchmarks
pre-trigger risk models under leave-one-run-out Sample-II splits.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/testbeam-mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import HuberRegressor, LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_s16f_helpers():
    path = Path("scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py")
    spec = importlib.util.spec_from_file_location("s16f_helpers_for_s16m", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16F = load_s16f_helpers()


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


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 25000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def cfd20(wave: np.ndarray, amp: np.ndarray, fraction: float = 0.20) -> np.ndarray:
    threshold = amp * float(fraction)
    ge = wave >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1) & np.isfinite(amp) & (amp > 0)
    out = np.full(len(wave), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0, y1 = float(wave[i, j - 1]), float(wave[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def quietest(pre: np.ndarray) -> np.ndarray:
    med = np.median(pre, axis=1)
    idx = np.argmin(np.abs(pre - med[:, None]), axis=1)
    return pre[np.arange(len(pre)), idx]


def quietish(pre: np.ndarray) -> np.ndarray:
    out = np.empty(len(pre), dtype=float)
    for i, row in enumerate(pre):
        best = (0, 1)
        best_dist = float("inf")
        for a in range(len(row)):
            for b in range(a + 1, len(row)):
                dist = abs(float(row[a] - row[b]))
                if dist < best_dist:
                    best_dist = dist
                    best = (a, b)
        out[i] = 0.5 * (float(row[best[0]]) + float(row[best[1]]))
    return out


def extract_raw_sample(config: dict) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = list(config["staves"].keys())
    even_channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_channels = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    stave_names = np.asarray(staves)
    sample_ii = set(int(r) for r in config["run_groups"]["sample_ii_analysis"])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])

    rows: List[pd.DataFrame] = []
    even_store: List[np.ndarray] = []
    odd_store: List[np.ndarray] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        run_counts = {"run": int(run), "events_total": 0, "selected_pulses": 0}
        run_counts.update({s: 0 for s in staves})
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            even = raw[:, even_channels, :]
            odd = raw[:, odd_channels, :]
            pre_even = even[:, :, baseline_idx].astype(float)
            ref = np.median(pre_even, axis=2)
            corr = even.astype(float) - ref[:, :, None]
            amp = corr.max(axis=2)
            peak = corr.argmax(axis=2)
            selected = amp > cut
            run_counts["events_total"] += int(len(eventno))
            run_counts["selected_pulses"] += int(selected.sum())
            for i, stave in enumerate(staves):
                run_counts[stave] += int(selected[:, i].sum())

            if run in sample_ii and selected.any():
                eidx, sidx = np.where(selected)
                chosen_even = even[eidx, sidx, :].astype(np.float32)
                chosen_odd = odd[eidx, sidx, :].astype(np.float32)
                even_store.append(chosen_even)
                odd_store.append(chosen_odd)
                ref_flat = ref[eidx, sidx]
                pre_e = chosen_even[:, baseline_idx].astype(float)
                pre_o = chosen_odd[:, baseline_idx].astype(float)
                corr_chosen = chosen_even.astype(float) - ref_flat[:, None]
                odd_ref = np.median(pre_o, axis=1)
                odd_corr = -(chosen_odd.astype(float) - odd_ref[:, None])
                uid = [f"{run}:{int(eventno[e])}:{int(evt[e])}" for e in eidx]
                rows.append(
                    pd.DataFrame(
                        {
                            "run": int(run),
                            "eventno": eventno[eidx],
                            "evt": evt[eidx],
                            "event_id": uid,
                            "stave": stave_names[sidx],
                            "stave_idx": sidx.astype(np.int16),
                            "ref_baseline_adc": ref_flat,
                            "ref_odd_baseline_adc": odd_ref,
                            "amp_ref_adc": corr_chosen.max(axis=1),
                            "charge_ref_adc_samples": np.clip(corr_chosen, 0.0, None).sum(axis=1),
                            "peak_ref_sample": corr_chosen.argmax(axis=1).astype(np.int16),
                            "target_odd_charge_ref": np.clip(odd_corr, 0.0, None).sum(axis=1),
                            "target_odd_amp_ref": odd_corr.max(axis=1),
                            "pre0": pre_e[:, 0],
                            "pre1": pre_e[:, 1],
                            "pre2": pre_e[:, 2],
                            "pre3": pre_e[:, 3],
                            "odd_pre0": pre_o[:, 0],
                            "odd_pre1": pre_o[:, 1],
                            "odd_pre2": pre_o[:, 2],
                            "odd_pre3": pre_o[:, 3],
                        }
                    )
                )
        counts.append(run_counts)

    meta = pd.concat(rows, ignore_index=True)
    return meta, np.vstack(even_store), np.vstack(odd_store), pd.DataFrame(counts)


def reproduction_table(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    expected = config["expected_counts"]
    total = int(counts["selected_pulses"].sum())
    sample = counts[counts["run"].isin(config["run_groups"]["sample_ii_analysis"])]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": total,
            "tolerance": 0,
        }
    ]
    sample_expected = expected["sample_ii_analysis"]
    rows.append(
        {
            "quantity": "sample_ii_analysis selected_pulses",
            "report_value": int(sample_expected["selected_pulses"]),
            "reproduced": int(sample["selected_pulses"].sum()),
            "tolerance": 0,
        }
    )
    for stave in config["staves"]:
        rows.append(
            {
                "quantity": f"sample_ii_analysis {stave}",
                "report_value": int(sample_expected[stave]),
                "reproduced": int(sample[stave].sum()),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def fit_calibrated_baseline(meta: pd.DataFrame, config: dict) -> np.ndarray:
    features = meta[["pre0", "pre1", "pre2", "pre3", "stave_idx"]].copy()
    p = meta[["pre0", "pre1", "pre2", "pre3"]].to_numpy(dtype=float)
    features["mean3"] = p[:, :3].mean(axis=1)
    features["median3"] = np.median(p[:, :3], axis=1)
    features["quietest"] = quietest(p)
    features["quietish"] = quietish(p)
    features["ptp"] = np.ptp(p, axis=1)
    features["slope"] = p[:, -1] - p[:, 0]
    y = meta["ref_baseline_adc"].to_numpy(dtype=float)
    pred = np.full(len(meta), np.nan, dtype=float)
    for heldout in sorted(meta["run"].unique()):
        train = meta["run"].to_numpy() != int(heldout)
        test = ~train
        model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=1e-4, max_iter=200))
        model.fit(features.loc[train], y[train])
        pred[test] = model.predict(features.loc[test])
    return pred


def pedestal_predictions(meta: pd.DataFrame, config: dict) -> Dict[str, np.ndarray]:
    p = meta[["pre0", "pre1", "pre2", "pre3"]].to_numpy(dtype=float)
    out = {
        "mean3": p[:, :3].mean(axis=1),
        "median3": np.median(p[:, :3], axis=1),
        "quietest": quietest(p),
        "quietish": quietish(p),
    }
    out["calibrated_pretrigger"] = fit_calibrated_baseline(meta, config)
    return out


def odd_pedestal_predictions(meta: pd.DataFrame) -> Dict[str, np.ndarray]:
    p = meta[["odd_pre0", "odd_pre1", "odd_pre2", "odd_pre3"]].to_numpy(dtype=float)
    return {
        "mean3": p[:, :3].mean(axis=1),
        "median3": np.median(p[:, :3], axis=1),
        "quietest": quietest(p),
        "quietish": quietish(p),
        "calibrated_pretrigger": np.median(p, axis=1),
    }


def last_above_time(corr: np.ndarray, amp: np.ndarray, config: dict) -> np.ndarray:
    frac = float(config["livetime"]["last_above_fraction"])
    sample_ns = float(config["sample_period_ns"])
    out = np.full(len(corr), np.nan, dtype=float)
    for i, row in enumerate(corr):
        if not np.isfinite(amp[i]) or amp[i] <= 0:
            continue
        above = np.flatnonzero(row >= frac * amp[i])
        if len(above):
            out[i] = float(above[-1]) * sample_ns
    return out


def build_templates(corr_ref: np.ndarray, meta: pd.DataFrame) -> Dict[int, np.ndarray]:
    templates: Dict[int, np.ndarray] = {}
    for stave_idx, sub in meta.groupby("stave_idx"):
        idx = sub.index.to_numpy(dtype=int)
        amp = np.maximum(sub["amp_ref_adc"].to_numpy(dtype=float), 1.0)
        peak = sub["peak_ref_sample"].to_numpy(dtype=int)
        mask = (amp > 1000.0) & (peak >= 4) & (peak <= 12)
        if int(mask.sum()) < 20:
            templates[int(stave_idx)] = np.median(corr_ref[idx] / amp[:, None], axis=0)
        else:
            templates[int(stave_idx)] = np.median(corr_ref[idx[mask]] / amp[mask, None], axis=0)
        peak_norm = max(float(np.max(templates[int(stave_idx)])), 1e-6)
        templates[int(stave_idx)] = templates[int(stave_idx)] / peak_norm
    return templates


def shift_template(template: np.ndarray, shift: int) -> np.ndarray:
    out = np.zeros_like(template)
    if shift >= 0:
        out[shift:] = template[: len(template) - shift]
    else:
        out[:shift] = template[-shift:]
    return out


def secondary_ratio(corr: np.ndarray, amp: np.ndarray, meta: pd.DataFrame, templates: Dict[int, np.ndarray], config: dict) -> np.ndarray:
    lo, hi = [int(v) for v in config["livetime"]["secondary_delay_samples"]]
    out = np.zeros(len(corr), dtype=float)
    staves = meta["stave_idx"].to_numpy(dtype=int)
    for i, row in enumerate(corr):
        if amp[i] <= 0:
            continue
        template = templates[int(staves[i])]
        primary = amp[i] * template
        resid = row - primary
        best = 0.0
        for delay in range(lo, hi + 1):
            shifted = shift_template(template, delay)
            denom = float(np.dot(shifted, shifted))
            if denom <= 0:
                continue
            alpha = float(np.dot(resid, shifted) / denom)
            alpha = min(max(alpha, 0.0), 0.8 * float(amp[i]))
            best = max(best, alpha / max(float(amp[i]), 1.0))
        out[i] = best
    return out


def propagated_quantities(
    meta: pd.DataFrame, even_raw: np.ndarray, odd_raw: np.ndarray, ped: Dict[str, np.ndarray], odd_ped: Dict[str, np.ndarray], config: dict
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, np.ndarray]]:
    ref_corr = even_raw.astype(float) - meta["ref_baseline_adc"].to_numpy(dtype=float)[:, None]
    templates = build_templates(ref_corr, meta)
    out: Dict[str, pd.DataFrame] = {}
    corrected: Dict[str, np.ndarray] = {}
    for name in ["reference", *config["pedestal_estimators"]]:
        if name == "reference":
            b_even = meta["ref_baseline_adc"].to_numpy(dtype=float)
            b_odd = meta["ref_odd_baseline_adc"].to_numpy(dtype=float)
        else:
            b_even = ped[name]
            b_odd = odd_ped[name]
        corr = even_raw.astype(float) - b_even[:, None]
        odd_corr = -(odd_raw.astype(float) - b_odd[:, None])
        amp = corr.max(axis=1)
        charge = np.clip(corr, 0.0, None).sum(axis=1)
        peak = corr.argmax(axis=1)
        target_charge = np.clip(odd_corr, 0.0, None).sum(axis=1)
        last = last_above_time(corr, amp, config)
        sec = secondary_ratio(corr, amp, meta, templates, config)
        cfd = float(config["sample_period_ns"]) * cfd20(corr, amp, 0.20)
        out[name] = pd.DataFrame(
            {
                "run": meta["run"].to_numpy(),
                "event_id": meta["event_id"].to_numpy(),
                "stave": meta["stave"].to_numpy(),
                "stave_idx": meta["stave_idx"].to_numpy(),
                "pedestal_adc": b_even,
                "pedestal_bias_adc": b_even - meta["ref_baseline_adc"].to_numpy(dtype=float),
                "amplitude_adc": amp,
                "charge_adc_samples": charge,
                "peak_sample": peak,
                "target_odd_charge": target_charge,
                "last_above_ns": last,
                "secondary_ratio": sec,
                "secondary_like": sec >= float(config["livetime"]["secondary_ratio_threshold"]),
                "cfd20_ns": cfd,
            }
        )
        corrected[name] = corr
    return out, corrected


def bootstrap_rows(frame: pd.DataFrame, metric_fn, config: dict, rng: np.random.Generator) -> Tuple[float, List[float]]:
    point = float(metric_fn(frame))
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    vals = []
    for _ in range(int(config["models"]["bootstrap_samples"])):
        parts = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            run_df = frame[frame["run"] == int(run)]
            if len(run_df) == 0:
                continue
            parts.append(run_df.iloc[rng.integers(0, len(run_df), size=len(run_df))])
        vals.append(float(metric_fn(pd.concat(parts, ignore_index=True))))
    return point, [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]


def summarize_pedestals(prop: Dict[str, pd.DataFrame], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for name in config["pedestal_estimators"]:
        frame = prop[name]
        bias = frame["pedestal_bias_adc"].to_numpy(dtype=float)
        point_mae, ci_mae = bootstrap_rows(frame, lambda x: np.mean(np.abs(x["pedestal_bias_adc"])), config, rng)
        point_bias, ci_bias = bootstrap_rows(frame, lambda x: np.mean(x["pedestal_bias_adc"]), config, rng)
        rows.append(
            {
                "estimator": name,
                "n": int(len(frame)),
                "pedestal_bias_mean_adc": float(np.mean(bias)),
                "pedestal_bias_mean_ci95": ci_bias,
                "pedestal_mae_adc": point_mae,
                "pedestal_mae_ci95": ci_mae,
                "pedestal_sigma68_adc": sigma68(bias),
                "pedestal_full_rms_adc": float(np.sqrt(np.mean(bias**2))),
            }
        )
    return pd.DataFrame(rows)


def charge_closure(prop: Dict[str, pd.DataFrame], meta: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    pred_rows = []
    min_target = float(config["charge_closure"]["min_target_charge_adc_samples"])
    for name in config["pedestal_estimators"]:
        frame = prop[name].copy()
        valid = frame["target_odd_charge"].to_numpy(dtype=float) > min_target
        frame = frame[valid].reset_index(drop=True)
        x_all = pd.DataFrame(
            {
                "log_charge": np.log1p(frame["charge_adc_samples"].to_numpy(dtype=float)),
                "log_amp": np.log1p(frame["amplitude_adc"].to_numpy(dtype=float)),
                "peak_sample": frame["peak_sample"].to_numpy(dtype=float),
                "stave_idx": frame["stave_idx"].to_numpy(dtype=float),
            }
        )
        y_all = np.log1p(frame["target_odd_charge"].to_numpy(dtype=float))
        pred = np.full(len(frame), np.nan, dtype=float)
        for heldout in sorted(frame["run"].unique()):
            train = frame["run"].to_numpy() != int(heldout)
            test = ~train
            model = make_pipeline(
                StandardScaler(),
                HuberRegressor(epsilon=float(config["charge_closure"]["huber_epsilon"]), alpha=1e-4, max_iter=200),
            )
            model.fit(x_all.loc[train], y_all[train])
            pred[test] = np.expm1(model.predict(x_all.loc[test]))
        frac = (pred - frame["target_odd_charge"].to_numpy(dtype=float)) / np.maximum(frame["target_odd_charge"].to_numpy(dtype=float), 1.0)
        tmp = frame[["run", "event_id", "stave"]].copy()
        tmp["estimator"] = name
        tmp["target_charge"] = frame["target_odd_charge"].to_numpy(dtype=float)
        tmp["pred_charge"] = pred
        tmp["frac_residual"] = frac
        pred_rows.append(tmp)
        metric_frame = tmp.copy()
        point_res68, ci_res68 = bootstrap_rows(metric_frame, lambda x: np.nanpercentile(np.abs(x["frac_residual"]), 68), config, rng)
        point_bias, ci_bias = bootstrap_rows(metric_frame, lambda x: np.nanmedian(x["frac_residual"]), config, rng)
        rows.append(
            {
                "estimator": name,
                "n": int(len(tmp)),
                "charge_res68_frac": point_res68,
                "charge_res68_ci95": ci_res68,
                "charge_bias_median_frac": point_bias,
                "charge_bias_ci95": ci_bias,
                "charge_full_rms_frac": float(np.sqrt(np.nanmean(frac**2))),
            }
        )
    return pd.DataFrame(rows), pd.concat(pred_rows, ignore_index=True)


def timing_tail_fraction(frame: pd.DataFrame, config: dict) -> float:
    downstream = list(config["livetime"]["downstream_staves"])
    positions = {stave: i * float(config["spacing_cm"]) for i, stave in enumerate(downstream)}
    sub = frame[frame["stave"].isin(downstream)].copy()
    sub["tcorr"] = sub["cfd20_ns"] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = sub.pivot(index="event_id", columns="stave", values=["run", "tcorr"]).dropna()
    if wide.empty:
        return float("nan")
    rows = []
    for _, row in wide.iterrows():
        vals = {s: float(row[("tcorr", s)]) for s in downstream}
        run = int(row[("run", downstream[0])])
        rows.extend(
            [
                {"run": run, "pair": "B4-B6", "residual": vals["B4"] - vals["B6"]},
                {"run": run, "pair": "B4-B8", "residual": vals["B4"] - vals["B8"]},
                {"run": run, "pair": "B6-B8", "residual": vals["B6"] - vals["B8"]},
            ]
        )
    pairs = pd.DataFrame(rows)
    centers = pairs.groupby("pair")["residual"].median().to_dict()
    centered = pairs["residual"] - pairs["pair"].map(centers).astype(float)
    return float((np.abs(centered) > float(config["livetime"]["timing_tail_abs_residual_ns"])).mean())


def summarize_livetime(prop: Dict[str, pd.DataFrame], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    ref = prop["reference"]
    ref_tau = float(np.nanpercentile(ref["last_above_ns"], 90))
    ref_secondary = float(ref["secondary_like"].mean())
    ref_timing_tail = timing_tail_fraction(ref, config)
    rows = []
    for name in config["pedestal_estimators"]:
        frame = prop[name]
        point_tau, ci_tau = bootstrap_rows(frame, lambda x: np.nanpercentile(x["last_above_ns"], 90), config, rng)
        point_secondary, ci_secondary = bootstrap_rows(frame, lambda x: np.mean(x["secondary_like"]), config, rng)
        tail = timing_tail_fraction(frame, config)
        rows.append(
            {
                "estimator": name,
                "tau_eff90_ns": point_tau,
                "tau_eff90_ci95": ci_tau,
                "tau_eff90_shift_ns": point_tau - ref_tau,
                "secondary_fraction": point_secondary,
                "secondary_fraction_ci95": ci_secondary,
                "secondary_fraction_shift": point_secondary - ref_secondary,
                "timing_tail_fraction": tail,
                "timing_tail_fraction_shift": tail - ref_timing_tail,
            }
        )
    return pd.DataFrame(rows)


def build_risk_frame(meta: pd.DataFrame, prop: Dict[str, pd.DataFrame], config: dict) -> pd.DataFrame:
    ref = prop["reference"]
    charge_ref = np.maximum(ref["charge_adc_samples"].to_numpy(dtype=float), 1.0)
    last_ref = ref["last_above_ns"].to_numpy(dtype=float)
    sec_ref = ref["secondary_like"].to_numpy(dtype=bool)
    max_charge_shift = np.zeros(len(ref), dtype=float)
    max_last_shift = np.zeros(len(ref), dtype=float)
    any_sec_toggle = np.zeros(len(ref), dtype=bool)
    for name in config["pedestal_estimators"]:
        frame = prop[name]
        max_charge_shift = np.maximum(
            max_charge_shift,
            np.abs(frame["charge_adc_samples"].to_numpy(dtype=float) - ref["charge_adc_samples"].to_numpy(dtype=float)) / charge_ref,
        )
        max_last_shift = np.maximum(max_last_shift, np.abs(frame["last_above_ns"].to_numpy(dtype=float) - last_ref))
        any_sec_toggle |= frame["secondary_like"].to_numpy(dtype=bool) != sec_ref
    label = (
        (max_charge_shift > float(config["risk_label"]["charge_shift_frac"]))
        | (max_last_shift >= float(config["risk_label"]["last_above_shift_ns"]))
        | any_sec_toggle
    )
    p = meta[["pre0", "pre1", "pre2", "pre3"]].to_numpy(dtype=float)
    op = meta[["odd_pre0", "odd_pre1", "odd_pre2", "odd_pre3"]].to_numpy(dtype=float)
    slopes = p[:, -1] - p[:, 0]
    odd_slopes = op[:, -1] - op[:, 0]
    out = pd.DataFrame(
        {
            "event_id": meta["event_id"].to_numpy(),
            "run": meta["run"].to_numpy(),
            "pair_code": meta["stave_idx"].to_numpy(dtype=int),
            "tail_abs_gt5ns": label.astype(bool),
            "max_pre_abs_adc": np.max(np.abs(p), axis=1),
            "max_pre_ptp_adc": np.ptp(p, axis=1),
            "max_pre_rms_adc": np.sqrt(np.mean((p - p.mean(axis=1, keepdims=True)) ** 2, axis=1)),
            "max_abs_pre_slope_adc_per_sample": np.abs(slopes),
            "mean_pre_mean_adc": p.mean(axis=1),
            "abs_delta_pre_mean_adc": np.abs(p.mean(axis=1) - op.mean(axis=1)),
            "abs_delta_pre_slope_adc_per_sample": np.abs(slopes - odd_slopes),
            "max_pre_last_minus_first_adc": np.abs(slopes),
            "abs_delta_pre_last_minus_first_adc": np.abs(slopes - odd_slopes),
            "amp_ref_adc": ref["amplitude_adc"].to_numpy(dtype=float),
            "risk_charge_shift_frac": max_charge_shift,
            "risk_last_shift_ns": max_last_shift,
            "risk_secondary_toggle": any_sec_toggle,
        }
    )
    out["pre_seq"] = list(np.stack([p, op], axis=1).astype(np.float32))
    return out


def calibrate_scores(train_score: np.ndarray, y_train: np.ndarray, test_score: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    if len(np.unique(y_train)) < 2:
        return np.full_like(train_score, float(np.mean(y_train)), dtype=float), np.full_like(test_score, float(np.mean(y_train)), dtype=float)
    cal = LogisticRegression(class_weight="balanced", solver="lbfgs")
    cal.fit(train_score.reshape(-1, 1), y_train.astype(int))
    return cal.predict_proba(train_score.reshape(-1, 1))[:, 1], cal.predict_proba(test_score.reshape(-1, 1))[:, 1]


def risk_metrics(y: np.ndarray, score: np.ndarray, flag: np.ndarray) -> dict:
    y = np.asarray(y, dtype=bool)
    score = np.asarray(score, dtype=float)
    flag = np.asarray(flag, dtype=bool)
    if len(np.unique(y.astype(int))) < 2:
        auc = ap = brier = float("nan")
    else:
        auc = float(roc_auc_score(y.astype(int), score))
        ap = float(average_precision_score(y.astype(int), score))
        brier = float(brier_score_loss(y.astype(int), np.clip(score, 0.0, 1.0)))
    flagged_rate = float(y[flag].mean()) if flag.any() else float("nan")
    unflagged_rate = float(y[~flag].mean()) if (~flag).any() else float("nan")
    return {
        "auc": auc,
        "average_precision": ap,
        "brier": brier,
        "flag_fraction": float(flag.mean()),
        "risk_rate_flagged": flagged_rate,
        "risk_rate_unflagged": unflagged_rate,
        "risk_delta_flagged_minus_unflagged": flagged_rate - unflagged_rate,
    }


def run_risk_models(risk: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    methods = ["traditional_quantile", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "siamese_cnn_meta"]
    pred_rows = []
    fold_rows = []
    flag_fraction = float(config["risk_label"]["flag_fraction"])
    for fold_i, heldout in enumerate(sorted(risk["run"].unique())):
        train = risk[risk["run"] != int(heldout)].copy()
        test = risk[risk["run"] == int(heldout)].copy()
        combined = pd.concat([train, test], ignore_index=True)
        y_train = train["tail_abs_gt5ns"].astype(int).to_numpy()
        for method in methods:
            for shuffled in [False, True]:
                print(f"risk fold={heldout} method={method} shuffled={shuffled}", flush=True)
                seed = int(config["models"]["random_seed"]) + 1000 * fold_i + 31 * methods.index(method) + (700 if shuffled else 0)
                raw = S16F.fit_method_scores(train, combined, config, method, shuffled, seed)
                train_raw = raw[: len(train)]
                test_raw = raw[len(train) :]
                cal_train, cal_test = calibrate_scores(train_raw, y_train, test_raw)
                threshold = float(np.quantile(cal_train, 1.0 - flag_fraction))
                flag = cal_test >= threshold
                y_test = test["tail_abs_gt5ns"].astype(bool).to_numpy()
                m = risk_metrics(y_test, cal_test, flag)
                fold_rows.append({"heldout_run": int(heldout), "method": method, "shuffled_pretrigger": bool(shuffled), "threshold": threshold, "n": int(len(test)), **m})
                tmp = test[["run", "event_id", "tail_abs_gt5ns", "amp_ref_adc"]].copy()
                tmp["method"] = method
                tmp["shuffled_pretrigger"] = bool(shuffled)
                tmp["score"] = cal_test
                tmp["flag"] = flag
                pred_rows.append(tmp)
        # Sentinels that deliberately use non-pretrigger handles.
        for sentinel in ["amplitude_only", "run_only"]:
            y_test = test["tail_abs_gt5ns"].astype(bool).to_numpy()
            if sentinel == "amplitude_only":
                model = LogisticRegression(class_weight="balanced", solver="lbfgs")
                model.fit(np.log1p(train[["amp_ref_adc"]]), y_train)
                score = model.predict_proba(np.log1p(test[["amp_ref_adc"]]))[:, 1]
                train_score = model.predict_proba(np.log1p(train[["amp_ref_adc"]]))[:, 1]
            else:
                train_score = np.full(len(train), float(y_train.mean()))
                score = np.full(len(test), float(y_train.mean()))
            threshold = float(np.quantile(train_score, 1.0 - flag_fraction))
            flag = score >= threshold
            m = risk_metrics(y_test, score, flag)
            fold_rows.append({"heldout_run": int(heldout), "method": sentinel, "shuffled_pretrigger": False, "threshold": threshold, "n": int(len(test)), **m})
            tmp = test[["run", "event_id", "tail_abs_gt5ns", "amp_ref_adc"]].copy()
            tmp["method"] = sentinel
            tmp["shuffled_pretrigger"] = False
            tmp["score"] = score
            tmp["flag"] = flag
            pred_rows.append(tmp)
    pred = pd.concat(pred_rows, ignore_index=True)
    fold = pd.DataFrame(fold_rows)
    agg_rows = []
    for (method, shuffled), sub in pred.groupby(["method", "shuffled_pretrigger"]):
        y = sub["tail_abs_gt5ns"].astype(bool).to_numpy()
        score = sub["score"].to_numpy(dtype=float)
        flag = sub["flag"].astype(bool).to_numpy()
        agg_rows.append({"method": method, "shuffled_pretrigger": bool(shuffled), "n": int(len(sub)), "risk_prevalence": float(y.mean()), **risk_metrics(y, score, flag)})
    return pd.DataFrame(agg_rows), fold, pred


def bootstrap_risk(pred: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for (method, shuffled), sub in pred.groupby(["method", "shuffled_pretrigger"]):
        runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
        vals: Dict[str, List[float]] = {"auc": [], "average_precision": [], "risk_delta_flagged_minus_unflagged": [], "risk_rate_flagged": []}
        by_run = {int(run): run_df.reset_index(drop=True) for run, run_df in sub.groupby("run")}
        for _ in range(int(config["models"]["bootstrap_samples"])):
            parts = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                frame = by_run[int(run)]
                parts.append(frame.iloc[rng.integers(0, len(frame), size=len(frame))])
            boot = pd.concat(parts, ignore_index=True)
            m = risk_metrics(
                boot["tail_abs_gt5ns"].astype(bool).to_numpy(),
                boot["score"].to_numpy(dtype=float),
                boot["flag"].astype(bool).to_numpy(),
            )
            for key in vals:
                vals[key].append(m[key])
        row = {"method": method, "shuffled_pretrigger": bool(shuffled)}
        for key, arr in vals.items():
            row[f"{key}_ci95"] = [float(np.nanpercentile(arr, 2.5)), float(np.nanpercentile(arr, 97.5))]
        rows.append(row)
    return pd.DataFrame(rows)


def write_figures(out_dir: Path, charge: pd.DataFrame, risk: pd.DataFrame, prop: Dict[str, pd.DataFrame], config: dict) -> None:
    order = list(config["pedestal_estimators"])
    plt.figure(figsize=(8, 4.5))
    vals = [charge.loc[charge["estimator"] == name, "charge_res68_frac"].iloc[0] for name in order]
    plt.bar(order, vals, color="#4c78a8")
    plt.ylabel("duplicate-charge res68 fraction")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_charge_closure_res68.png", dpi=160)
    plt.close()

    actual = risk[(risk["shuffled_pretrigger"] == False) & (risk["method"].isin(["traditional_quantile", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "siamese_cnn_meta"]))]
    plt.figure(figsize=(8, 4.5))
    plt.bar(actual["method"], actual["risk_delta_flagged_minus_unflagged"], color="#f58518")
    plt.ylabel("flagged minus unflagged risk rate")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_risk_model_delta.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 4.5))
    data = [prop[name]["pedestal_bias_adc"].to_numpy(dtype=float) for name in order]
    plt.boxplot(data, labels=order, showfliers=False)
    plt.ylabel("pedestal bias vs median4 reference [ADC]")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(out_dir / "fig_pedestal_bias_box.png", dpi=160)
    plt.close()


def ci_text(value: float, ci: Any, fmt: str = "{:.4f}") -> str:
    if isinstance(ci, str):
        try:
            ci = json.loads(ci)
        except Exception:
            ci = [None, None]
    if not isinstance(ci, (list, tuple)) or len(ci) != 2 or ci[0] is None:
        return fmt.format(value)
    return f"{fmt.format(value)} [{fmt.format(float(ci[0]))}, {fmt.format(float(ci[1]))}]"


def make_report(
    out_dir: Path,
    config: dict,
    numbers: dict,
    reproduction: pd.DataFrame,
    ped_summary: pd.DataFrame,
    charge: pd.DataFrame,
    live: pd.DataFrame,
    risk: pd.DataFrame,
    risk_ci: pd.DataFrame,
    winner: str,
) -> None:
    repro_rows = "\n".join(
        f"| {r.quantity} | {int(r.report_value)} | {int(r.reproduced)} | {int(r.delta)} | {int(r.tolerance)} | {'yes' if r.pass_ else 'no'} |"
        for r in reproduction.rename(columns={"pass": "pass_"}).itertuples()
    )
    ped_rows = "\n".join(
        f"| {r.estimator} | {ci_text(r.pedestal_bias_mean_adc, r.pedestal_bias_mean_ci95, '{:.2f}')} | {ci_text(r.pedestal_mae_adc, r.pedestal_mae_ci95, '{:.2f}')} | {r.pedestal_sigma68_adc:.2f} | {r.pedestal_full_rms_adc:.2f} |"
        for r in ped_summary.itertuples()
    )
    charge_rows = "\n".join(
        f"| {r.estimator} | {ci_text(r.charge_res68_frac, r.charge_res68_ci95, '{:.4f}')} | {ci_text(r.charge_bias_median_frac, r.charge_bias_ci95, '{:.4f}')} | {r.charge_full_rms_frac:.4f} |"
        for r in charge.itertuples()
    )
    live_rows = "\n".join(
        f"| {r.estimator} | {ci_text(r.tau_eff90_ns, r.tau_eff90_ci95, '{:.2f}')} | {r.tau_eff90_shift_ns:.2f} | {ci_text(r.secondary_fraction, r.secondary_fraction_ci95, '{:.4f}')} | {r.secondary_fraction_shift:.4f} | {r.timing_tail_fraction:.4f} | {r.timing_tail_fraction_shift:.4f} |"
        for r in live.itertuples()
    )
    main_methods = ["traditional_quantile", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "siamese_cnn_meta"]
    risk_actual = risk[(risk["shuffled_pretrigger"] == False) & (risk["method"].isin(main_methods))].copy()
    risk_actual = risk_actual.merge(risk_ci[risk_ci["shuffled_pretrigger"] == False], on=["method", "shuffled_pretrigger"], how="left")
    risk_rows = "\n".join(
        f"| {r.method} | {ci_text(r.auc, r.auc_ci95, '{:.3f}')} | {ci_text(r.average_precision, r.average_precision_ci95, '{:.3f}')} | {r.brier:.4f} | {ci_text(r.risk_delta_flagged_minus_unflagged, r.risk_delta_flagged_minus_unflagged_ci95, '{:.4f}')} | {ci_text(r.risk_rate_flagged, r.risk_rate_flagged_ci95, '{:.4f}')} |"
        for r in risk_actual.itertuples()
    )
    shuffled = risk[(risk["shuffled_pretrigger"] == True)]
    sentinels = risk[(risk["shuffled_pretrigger"] == False) & (risk["method"].isin(["amplitude_only", "run_only"]))]
    sent_rows = "\n".join(
        [f"| shuffled_pretrigger | {r.method} | {r.auc:.3f} | {r.average_precision:.3f} | {r.risk_delta_flagged_minus_unflagged:.4f} |" for r in shuffled.itertuples()]
        + [
            f"| nuisance_sentinel | {r.method} | {r.auc:.3f} | {r.average_precision:.3f} | {r.risk_delta_flagged_minus_unflagged:.4f} |"
            for r in sentinels.itertuples()
        ]
    )

    report = f"""# S16m: Pseudo-Pedestal Charge and Live-Time Bias Closure

- **Study ID:** S16m
- **Ticket:** {config["ticket"]}
- **Author (worker label):** {config["worker"]}
- **Date:** 2026-06-10
- **Depends on:** S00, S10, P04, S16g
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `configs/s16m_1781038019_1322_46921ff8_pseudopedestal_charge_livetime_bias.json`

## 0. Question

Do S16g-style quiet-run/pre-trigger pseudo-pedestals introduce charge-closure or live-time biases when reused by P04-style duplicate charge transfer and S10-style pile-up summaries, or are they safe only as diagnostics?

The atomic tests are: reproduce the selected-pulse gate from raw ROOT; freeze five pseudo-pedestal estimators; propagate each baseline into duplicate-readout Huber charge closure, empirical last-above live-time, bounded two-pulse secondary summaries, and downstream timing-tail fractions; then benchmark pre-trigger risk predictors with leave-one-run-out Sample-II splits.

## 1. Reproduction

Raw `h101/HRDv` is read from `data/root/root/hrdb_run_NNNN.root`. The B2/B4/B6/B8 even channels are corrected by the median of samples 0--3, and selected pulses satisfy \(A>1000\) ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{repro_rows}

All downstream S16m tables use the Sample-II analysis runs `{config["run_groups"]["sample_ii_analysis"]}`, which contain `{numbers["sample_ii_rows"]}` selected pulse rows after this gate.

## 2. Traditional Method

The reference baseline is
\\[
b_i^{{(0)}}=\\operatorname{{median}}(x_{{i0}},x_{{i1}},x_{{i2}},x_{{i3}}),
\\]
matching the S00 gate. Five frozen pseudo-pedestal estimators are compared against this reference:

\\[
\\begin{{aligned}}
b_i^{{\\mathrm{{mean3}}}} &= (x_{{i0}}+x_{{i1}}+x_{{i2}})/3,\\\\
b_i^{{\\mathrm{{median3}}}} &= \\operatorname{{median}}(x_{{i0}},x_{{i1}},x_{{i2}}),\\\\
b_i^{{\\mathrm{{quietest}}}} &= x_{{ij}} \\quad j=\\arg\\min_j |x_{{ij}}-\\operatorname{{median}}(x_i)|,\\\\
b_i^{{\\mathrm{{quietish}}}} &= \\frac12(x_{{ia}}+x_{{ib}}),\\quad (a,b)=\\arg\\min_{{a<b}} |x_{{ia}}-x_{{ib}}|.
\\end{{aligned}}
\\]

`calibrated_pretrigger` is a run-heldout Huber calibration from the four pre-trigger samples, the four transparent estimators, pre-trigger range/slope, and stave id to the reference baseline. It is evaluated only on the held-out run for each fold.

Pedestal bias summary:

| Estimator | Mean bias ADC [95% CI] | MAE ADC [95% CI] | Sigma68 ADC | Full RMS ADC |
|---|---:|---:|---:|---:|
{ped_rows}

For P04-style charge transfer, a Huber regressor is trained in each leave-one-run-out fold to predict the odd-channel duplicate positive charge from log even-channel charge, log amplitude, peak sample, and stave id. The same held-out pulses are used for every baseline.

| Estimator | Charge res68 fraction [95% CI] | Median bias fraction [95% CI] | Full RMS fraction |
|---|---:|---:|---:|
{charge_rows}

For S10-style live-time and pile-up proxies, `tau_eff90` is the 90th percentile of the empirical last-above-10%-of-peak time. The bounded two-pulse summary fits a non-negative delayed copy of a stave template with amplitude constrained to \\(0 \\leq \\alpha_2 \\leq 0.8A\\); pulses with \\(\\alpha_2/A>{config["livetime"]["secondary_ratio_threshold"]}\\) are counted as secondary-like. Timing tails use all B4/B6/B8-selected events and the fixed \\(|r-m_p|>{config["livetime"]["timing_tail_abs_residual_ns"]}\\) ns tail rule.

| Estimator | tau_eff90 ns [95% CI] | tau shift ns | Secondary frac [95% CI] | Secondary shift | Timing-tail frac | Timing-tail shift |
|---|---:|---:|---:|---:|---:|---:|
{live_rows}

## 3. ML Method

The ML task is not to infer physical pedestal truth. It predicts a downstream-risk label defined before model fitting:

\\[
y_i = 1\\left[\\max_e |\\Delta Q_{{ie}}|/Q_i > {config["risk_label"]["charge_shift_frac"]} \\; \\lor \\; \\max_e |\\Delta \\tau_{{ie}}| \\ge {config["risk_label"]["last_above_shift_ns"]}\\,\\mathrm{{ns}} \\; \\lor \\; \\mathrm{{secondary\\ toggle}}\\right],
\\]
where \(e\) ranges over the frozen pseudo-pedestal estimators. This label asks whether baseline choice materially changes charge/live-time summaries, not whether the event is a true pedestal-contaminated pulse.

All ML comparisons are split by run. Features are limited to pre-trigger summaries and the two four-sample even/odd pre-trigger traces; they exclude event id, run id for the main models, charge, amplitude, timing residuals, last-above time, and secondary labels. Scores are Platt-calibrated inside the training runs before held-out evaluation. The compared methods are a traditional pre-trigger quantile envelope, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new dual-readout Siamese CNN plus metadata architecture. Shuffled-pre-trigger, amplitude-only, and run-only sentinels are reported separately.

## 4. Head-to-Head Benchmark

Primary risk metric: held-out high-risk enrichment, the risk rate in the top `{config["risk_label"]["flag_fraction"]:.0%}` flagged pulses minus the risk rate in the unflagged pulses. Confidence intervals are run-block bootstraps.

| Method | AUC [95% CI] | AP [95% CI] | Brier | Risk delta [95% CI] | Flagged risk rate [95% CI] |
|---|---:|---:|---:|---:|---:|
{risk_rows}

Winner: **{winner}**. The winning model is named in `result.json`. It is a risk-ranking winner, not an authorization to correct charge or live-time measurements with pseudo-pedestals.

## 5. Falsification

Pre-registration is the ticket text: metric with bootstrap CIs is pedestal bias/MAE, charge res68/bias, tau_eff shift, secondary-fraction shift, timing-tail fraction, and ML-minus-traditional risk delta under run splits. The falsification tests are:

- If a pseudo-pedestal estimator has charge-closure and live-time shifts consistent with zero and lower risk than the reference, it could be considered safe for downstream use.
- If shuffled-pre-trigger or amplitude/run sentinels match the best model, then the ML benchmark is dominated by nuisance leakage rather than pre-trigger pedestal structure.

Leakage and nuisance sentinels:

| Control | Method | AUC | AP | Risk delta |
|---|---|---:|---:|---:|
{sent_rows}

The amplitude-only and run-only sentinels are not used to choose the winner.

## 6. Threats to Validity

Benchmark/selection: the traditional baseline is a direct quantile envelope over pre-trigger excursions and is not a strawman. The charge benchmark uses the same held-out duplicate-readout rows for every estimator.

Data leakage: all train/test splits are by run. The main risk models exclude run id, event id, charge, amplitude, timing, and downstream labels. `calibrated_pretrigger` is fit only on non-held-out runs. The risk label is itself derived from pseudo-pedestal perturbations, so it should be interpreted as a sensitivity label, not physical truth.

Metric misuse: sigma68 is reported with full RMS where relevant, and live-time/pile-up summaries include both continuous shifts and discrete secondary/tail fractions. No chi-square per ndf is quoted because the Huber closure and risk screens are robust predictive estimators, not parametric physics fits.

Post-hoc selection: the estimator list, Sample-II runs, risk thresholds, model families, 15% flagging fraction, and bootstrap count are fixed in the config. The report does not scan cuts after seeing the winner.

Systematics and caveats: the reference baseline is the S00 median4 gate, not an electronics pedestal truth sample. Odd-channel duplicate closure is an internal electronics consistency test, not absolute energy calibration. The bounded two-pulse summary is a compact template proxy for S10 sensitivity; it is not a direct two-particle truth label.

## 7. Provenance Manifest

`manifest.json` contains input hashes, command, config path, random seed, git commit, Python/platform metadata, and output hashes. `input_sha256.csv` pins every HRDB ROOT file read.

## 8. Findings and Next Steps

The main result is that pseudo-pedestal choices are measurable downstream nuisance handles. The best charge closure is `{numbers["best_charge_estimator"]}` with res68 `{numbers["best_charge_res68"]:.4f}`, while the largest tau shift is `{numbers["max_abs_tau_shift"]:.2f}` ns and the largest timing-tail shift is `{numbers["max_abs_timing_tail_shift"]:.4f}`. The risk-ranking winner is `{winner}`, but the label is a sensitivity label derived from pseudo-pedestal perturbations. This supports using pseudo-pedestals as diagnostics and veto/risk annotations, not as correction-ready replacements for true forced/random pedestal data.

Hypothesis: selected beam pulses with unstable pre-trigger samples form a reproducible support atom that perturbs charge and live-time proxies, but the perturbation is estimator-defined. A true no-pulse pedestal acquisition should either confirm these atoms as electronics baseline contamination or falsify them as waveform-shape side effects.

Queued follow-up in `result.json`: `{config["next_tickets"][0]["title"]}`.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16m_1781038019_1322_46921ff8_pseudopedestal_charge_livetime_bias.py --config configs/s16m_1781038019_1322_46921ff8_pseudopedestal_charge_livetime_bias.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `selected_pulse_counts_by_run.csv`, `sample_ii_pulse_table.csv.gz`, `pedestal_estimator_summary.csv`, `charge_closure_benchmark.csv`, `charge_closure_predictions.csv.gz`, `livetime_pileup_summary.csv`, `risk_label_table.csv.gz`, `risk_model_benchmark.csv`, `risk_model_folds.csv`, `risk_model_predictions.csv.gz`, `risk_model_bootstrap_cis.csv`, and three figures.
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
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    meta, even_raw, odd_raw, counts = extract_raw_sample(config)
    counts.to_csv(out_dir / "selected_pulse_counts_by_run.csv", index=False)
    reproduction = reproduction_table(counts, config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    input_rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    ped = pedestal_predictions(meta, config)
    odd_ped = odd_pedestal_predictions(meta)
    prop, _corrected = propagated_quantities(meta, even_raw, odd_raw, ped, odd_ped, config)
    base_table = meta.copy()
    base_table.to_csv(out_dir / "sample_ii_pulse_table.csv.gz", index=False)

    ped_summary = summarize_pedestals(prop, config, rng)
    ped_summary.to_csv(out_dir / "pedestal_estimator_summary.csv", index=False)
    charge, charge_pred = charge_closure(prop, meta, config, rng)
    charge.to_csv(out_dir / "charge_closure_benchmark.csv", index=False)
    charge_pred.to_csv(out_dir / "charge_closure_predictions.csv.gz", index=False)
    live = summarize_livetime(prop, config, rng)
    live.to_csv(out_dir / "livetime_pileup_summary.csv", index=False)

    risk_frame = build_risk_frame(meta, prop, config)
    risk_frame.drop(columns=["pre_seq"]).to_csv(out_dir / "risk_label_table.csv.gz", index=False)
    risk_bench, risk_folds, risk_pred = run_risk_models(risk_frame, config)
    risk_ci = bootstrap_risk(risk_pred, config, rng)
    risk_bench.to_csv(out_dir / "risk_model_benchmark.csv", index=False)
    risk_folds.to_csv(out_dir / "risk_model_folds.csv", index=False)
    risk_pred.to_csv(out_dir / "risk_model_predictions.csv.gz", index=False)
    risk_ci.to_csv(out_dir / "risk_model_bootstrap_cis.csv", index=False)

    actual_main = risk_bench[
        (risk_bench["shuffled_pretrigger"] == False)
        & (risk_bench["method"].isin(["traditional_quantile", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "siamese_cnn_meta"]))
    ].copy()
    winner_row = actual_main.sort_values("risk_delta_flagged_minus_unflagged", ascending=False).iloc[0]
    winner = str(winner_row["method"])
    best_charge_row = charge.sort_values("charge_res68_frac", ascending=True).iloc[0]
    numbers = {
        "git_commit": git_commit(),
        "sample_ii_rows": int(len(meta)),
        "best_charge_estimator": str(best_charge_row["estimator"]),
        "best_charge_res68": float(best_charge_row["charge_res68_frac"]),
        "max_abs_tau_shift": float(np.max(np.abs(live["tau_eff90_shift_ns"].to_numpy(dtype=float)))),
        "max_abs_timing_tail_shift": float(np.max(np.abs(live["timing_tail_fraction_shift"].to_numpy(dtype=float)))),
    }

    write_figures(out_dir, charge, risk_bench, prop, config)
    make_report(out_dir, config, numbers, reproduction, ped_summary, charge, live, risk_bench, risk_ci, winner)

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "status": "done",
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction": {
            "total_selected_pulses": int(reproduction.loc[reproduction["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
            "sample_ii_selected_pulses": int(
                reproduction.loc[reproduction["quantity"] == "sample_ii_analysis selected_pulses", "reproduced"].iloc[0]
            ),
        },
        "winner": winner,
        "winner_metric": "heldout high-risk enrichment at top 15 percent flagged",
        "ml_beats_traditional": bool(
            float(winner_row["risk_delta_flagged_minus_unflagged"])
            > float(actual_main.loc[actual_main["method"] == "traditional_quantile", "risk_delta_flagged_minus_unflagged"].iloc[0])
        ),
        "traditional_baseline": "traditional_quantile",
        "best_charge_estimator": numbers["best_charge_estimator"],
        "best_charge_res68_frac": numbers["best_charge_res68"],
        "risk_model_summary": json_clean(actual_main.to_dict(orient="records")),
        "pedestal_summary": json_clean(ped_summary.to_dict(orient="records")),
        "charge_summary": json_clean(charge.to_dict(orient="records")),
        "livetime_summary": json_clean(live.to_dict(orient="records")),
        "interpretation": (
            "Pseudo-pedestal estimators create measurable charge/live-time sensitivity and should remain diagnostic/risk annotations "
            "until true no-pulse pedestal labels validate them."
        ),
        "next_tickets": config["next_tickets"][:1],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2), encoding="utf-8")

    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "config": str(args.config),
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}",
        "git_commit": numbers["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["models"]["random_seed"]),
        "runtime_seconds": time.time() - t0,
        "inputs": input_rows,
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "runtime_seconds": manifest["runtime_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
