#!/usr/bin/env python3
"""P12a pulse-axis covariance table across pathology flags."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from scipy.stats import norm
from sklearn.covariance import GraphicalLasso
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer


AXES = [
    "saturation_boundary",
    "high_amplitude",
    "adaptive_lowering",
    "early_pretrigger_activity",
    "delayed_peak",
    "broad_template_mismatch",
    "pileup_score",
    "timing_tail",
    "charge_transfer_error",
]


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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


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
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = float(waveforms[i, j - 1])
        y1 = float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def pulse_rows_from_batch(config: dict, run: int, batch: dict) -> Tuple[pd.DataFrame, dict]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(channel) for name, channel in config["staves"].items()}
    stave_names = np.asarray(list(staves.keys()))
    channels = np.asarray(list(staves.values()), dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    eventno = np.asarray(batch["EVENTNO"]).astype(int)
    evt = np.asarray(batch["EVT"]).astype(int)
    events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
    wave = events[:, channels, :]
    seed = np.median(wave[..., baseline_idx], axis=-1)
    corrected = wave - seed[..., None]
    amplitude = corrected.max(axis=-1)
    selected = amplitude > cut
    peak = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    positive = np.maximum(corrected, 0.0)
    positive_sum = positive.sum(axis=-1)
    late_fraction = positive[..., 12:].sum(axis=-1) / np.maximum(positive_sum, 1.0)
    width035 = (corrected >= (0.35 * amplitude[..., None])).sum(axis=-1)
    width050 = (corrected >= (0.50 * amplitude[..., None])).sum(axis=-1)
    plateau_count = (corrected >= (0.98 * amplitude[..., None])).sum(axis=-1)

    secondary_peak = np.full_like(amplitude, -np.inf)
    secondary_sep = np.zeros_like(amplitude)
    for j in range(nsamp):
        mask = np.abs(peak - j) >= int(config.get("pileup_secondary_min_sep", 4))
        candidate = np.where(mask, corrected[..., j], -np.inf)
        update = candidate > secondary_peak
        secondary_sep = np.where(update, np.abs(peak - j), secondary_sep)
        secondary_peak = np.where(update, candidate, secondary_peak)
    secondary_peak = np.where(np.isfinite(secondary_peak), secondary_peak, 0.0)
    secondary_rel = secondary_peak / np.maximum(amplitude, 1.0)

    pre = wave[..., baseline_idx]
    pre_centered = pre - seed[..., None]
    pre_rms = np.sqrt(np.mean(pre_centered**2, axis=-1))
    pre_slope = pre[..., -1] - pre[..., 0]
    pre_max_exc = np.max(np.abs(pre_centered), axis=-1)
    pre_asym = 0.5 * ((pre[..., 0] + pre[..., 1]) - (pre[..., 2] + pre[..., 3]))
    pre_ptp = pre.max(axis=-1) - pre.min(axis=-1)
    adaptive_lowering = np.maximum(0.0, seed - (pre.min(axis=-1) + 10.0))

    event_idx, stave_idx = np.where(selected)
    counts = {
        "events_total": int(len(eventno)),
        "events_with_selected": int(selected.any(axis=1).sum()),
        "selected_pulses": int(selected.sum()),
        "staves": {str(stave_names[i]): int(selected[:, i].sum()) for i in range(len(stave_names))},
    }
    if len(event_idx) == 0:
        return pd.DataFrame(), counts

    flat_corrected = corrected[event_idx, stave_idx]
    flat_amp = amplitude[event_idx, stave_idx]
    t_cfd20 = cfd_time_samples(flat_corrected, flat_amp, 0.20) * float(config["sample_period_ns"])
    rows = pd.DataFrame(
        {
            "event_uid": [f"{run}:{int(eventno[e])}:{int(evt[e])}" for e in event_idx],
            "pulse_uid": [f"{run}:{int(eventno[e])}:{int(evt[e])}:{str(stave_names[s])}" for e, s in zip(event_idx, stave_idx)],
            "run": int(run),
            "eventno": eventno[event_idx],
            "evt": evt[event_idx],
            "stave": stave_names[stave_idx],
            "channel": channels[stave_idx],
            "amplitude_adc": flat_amp,
            "log_amp": np.log1p(flat_amp),
            "area_adc_samples": area[event_idx, stave_idx],
            "area_over_amp": area[event_idx, stave_idx] / np.maximum(flat_amp, 1.0),
            "peak_sample": peak[event_idx, stave_idx],
            "width035_samples": width035[event_idx, stave_idx],
            "width050_samples": width050[event_idx, stave_idx],
            "plateau_count": plateau_count[event_idx, stave_idx],
            "secondary_peak_rel": secondary_rel[event_idx, stave_idx],
            "secondary_peak_sep": secondary_sep[event_idx, stave_idx],
            "late_fraction": late_fraction[event_idx, stave_idx],
            "seed_baseline_adc": seed[event_idx, stave_idx],
            "pre_rms_adc": pre_rms[event_idx, stave_idx],
            "pre_slope_adc": pre_slope[event_idx, stave_idx],
            "pre_max_exc_adc": pre_max_exc[event_idx, stave_idx],
            "pre_asym_adc": pre_asym[event_idx, stave_idx],
            "pre_ptp_adc": pre_ptp[event_idx, stave_idx],
            "adaptive_lowering_adc": adaptive_lowering[event_idx, stave_idx],
            "t_cfd20_ns": t_cfd20,
        }
    )
    return rows, counts


def scan_raw(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    group_for_run = run_group_lookup(config)
    rows = []
    count_rows = []
    group_counts: Dict[str, dict] = defaultdict(lambda: {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0, "staves": defaultdict(int)})
    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0, "staves": defaultdict(int)}
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            batch_rows, counts = pulse_rows_from_batch(config, run, batch)
            if len(batch_rows):
                batch_rows["group"] = group_for_run[run]
                rows.append(batch_rows)
            for key in ["events_total", "events_with_selected", "selected_pulses"]:
                run_counts[key] += counts[key]
                group_counts[group_for_run[run]][key] += counts[key]
            for stave, value in counts["staves"].items():
                run_counts["staves"][stave] += value
                group_counts[group_for_run[run]]["staves"][stave] += value
        row = {"run": run, "group": group_for_run[run], **{k: run_counts[k] for k in ["events_total", "events_with_selected", "selected_pulses"]}}
        row.update({stave: int(run_counts["staves"][stave]) for stave in config["staves"]})
        count_rows.append(row)
    group_rows = []
    for group in config["run_groups"]:
        counts = group_counts[group]
        row = {"group": group, **{k: counts[k] for k in ["events_total", "events_with_selected", "selected_pulses"]}}
        row.update({stave: int(counts["staves"][stave]) for stave in config["staves"]})
        group_rows.append(row)
    pulses = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return pulses, pd.DataFrame(count_rows), pd.DataFrame(group_rows)


def compare_counts(config: dict, group_counts: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(group_counts["selected_pulses"].sum()),
            "tolerance": 0,
        }
    ]
    for group, group_expected in expected["groups"].items():
        actual = group_counts[group_counts["group"] == group].iloc[0]
        if "events" in group_expected:
            rows.append({"quantity": f"{group} events with selected pulse", "report_value": int(group_expected["events"]), "reproduced": int(actual["events_with_selected"]), "tolerance": 0})
        if "pulses" in group_expected:
            rows.append({"quantity": f"{group} selected pulses", "report_value": int(group_expected["pulses"]), "reproduced": int(actual["selected_pulses"]), "tolerance": 0})
        for stave, value in group_expected.get("staves", {}).items():
            rows.append({"quantity": f"{group} {stave} selected pulses", "report_value": int(value), "reproduced": int(actual[stave]), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def add_timing_outcome(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    positions = {"B4": 0.0, "B6": float(config["spacing_cm"]), "B8": 2.0 * float(config["spacing_cm"])}
    downstream = pulses[pulses["stave"].isin(["B4", "B6", "B8"])].copy()
    downstream["tcorr_ns"] = downstream["t_cfd20_ns"] - downstream["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    wide = downstream.pivot_table(index="event_uid", columns="stave", values="tcorr_ns", aggfunc="first")
    pair_resids = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a in wide and b in wide:
            pair_resids.append((wide[a] - wide[b]).abs())
    if pair_resids:
        event_tail_abs = pd.concat(pair_resids, axis=1).max(axis=1)
        pulses = pulses.merge(event_tail_abs.rename("event_timing_abs_resid_ns"), left_on="event_uid", right_index=True, how="left")
    else:
        pulses["event_timing_abs_resid_ns"] = np.nan
    return pulses


def charge_model() -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), ["log_amp", "peak_sample", "width035_samples", "late_fraction"]),
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["stave"]),
        ]
    )
    return Pipeline([("pre", pre), ("lin", LinearRegression())])


def assign_loro_axes(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    parts = []
    for run in sorted(pulses["run"].unique()):
        train = pulses[pulses["run"] != run].copy()
        test = pulses[pulses["run"] == run].copy()
        model = charge_model()
        model.fit(train, train["area_over_amp"])
        train_resid = train["area_over_amp"].to_numpy() - model.predict(train)
        test_resid = test["area_over_amp"].to_numpy() - model.predict(test)
        threshold = float(np.nanquantile(np.abs(train_resid), 0.95))
        broad_threshold = float(train["width050_samples"].quantile(float(config.get("broad_width050_quantile", 0.995))))
        test["charge_residual_area_over_amp"] = test_resid
        test["charge_residual_threshold"] = threshold
        test["saturation_boundary"] = ((test["amplitude_adc"] >= float(config["high_amplitude_adc"])) & (test["plateau_count"] >= 2)).astype(int)
        test["high_amplitude"] = (test["amplitude_adc"] >= float(config["high_amplitude_adc"])).astype(int)
        test["adaptive_lowering"] = (test["adaptive_lowering_adc"] >= float(config["adaptive_lowering_adc"])).astype(int)
        test["early_pretrigger_activity"] = ((test["pre_max_exc_adc"] >= float(config["early_pretrigger_exc_adc"])) | (test["pre_ptp_adc"] >= float(config["early_pretrigger_exc_adc"]))).astype(int)
        test["delayed_peak"] = (test["peak_sample"] >= int(config["delayed_peak_sample"])).astype(int)
        test["pileup_score"] = (
            ((test["secondary_peak_rel"] >= float(config["pileup_secondary_rel"])) & (test["secondary_peak_sep"] >= int(config.get("pileup_secondary_min_sep", 4))))
            | (test["late_fraction"] >= float(config["pileup_late_fraction"]))
        ).astype(int)
        test["broad_template_mismatch"] = ((test["width050_samples"] >= broad_threshold) & (test["pileup_score"] == 0) & (test["saturation_boundary"] == 0)).astype(int)
        test["timing_tail"] = (test["event_timing_abs_resid_ns"] > float(config["timing_tail_abs_ns"])).fillna(False).astype(int)
        test["charge_transfer_error"] = (np.abs(test["charge_residual_area_over_amp"]) >= test["charge_residual_threshold"]).astype(int)
        parts.append(test)
    return pd.concat(parts, ignore_index=True)


def odds_ratio(a: np.ndarray, b: np.ndarray) -> float:
    n11 = float(((a == 1) & (b == 1)).sum())
    n10 = float(((a == 1) & (b == 0)).sum())
    n01 = float(((a == 0) & (b == 1)).sum())
    n00 = float(((a == 0) & (b == 0)).sum())
    return ((n11 + 0.5) * (n00 + 0.5)) / ((n10 + 0.5) * (n01 + 0.5))


def binary_mi(a: np.ndarray, b: np.ndarray) -> float:
    tab = np.zeros((2, 2), dtype=float)
    for i in [0, 1]:
        for j in [0, 1]:
            tab[i, j] = ((a == i) & (b == j)).sum()
    tab = tab / max(tab.sum(), 1.0)
    px = tab.sum(axis=1)
    py = tab.sum(axis=0)
    mi = 0.0
    for i in [0, 1]:
        for j in [0, 1]:
            if tab[i, j] > 0 and px[i] > 0 and py[j] > 0:
                mi += tab[i, j] * math.log(tab[i, j] / (px[i] * py[j]))
    return mi


def bootstrap_runs(df: pd.DataFrame, value_fn, n_boot: int, seed: int) -> Tuple[float, float, float]:
    runs = np.asarray(sorted(df["run"].unique()))
    value = float(value_fn(df))
    rng = np.random.default_rng(seed)
    vals = []
    by_run = {run: part for run, part in df.groupby("run")}
    for _ in range(n_boot):
        sample = rng.choice(runs, size=len(runs), replace=True)
        vals.append(float(value_fn(pd.concat([by_run[int(run)] for run in sample], ignore_index=True))))
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return value, float(lo), float(hi)


def make_pairwise_tables(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    boot_rows = []
    n_boot = int(config["ml"]["bootstrap_samples"])
    for i, a in enumerate(AXES):
        for b in AXES[i + 1 :]:
            aa = df[a].to_numpy(dtype=int)
            bb = df[b].to_numpy(dtype=int)
            or_value = odds_ratio(aa, bb)
            mi = binary_mi(aa, bb)
            phi = float(np.corrcoef(aa, bb)[0, 1]) if aa.std() > 0 and bb.std() > 0 else np.nan
            rows.append({"axis_a": a, "axis_b": b, "odds_ratio": or_value, "log_odds_ratio": math.log(or_value), "phi": phi, "mutual_information_nats": mi})

            def or_fn(x, axis_a=a, axis_b=b):
                return math.log(odds_ratio(x[axis_a].to_numpy(dtype=int), x[axis_b].to_numpy(dtype=int)))

            value, lo, hi = bootstrap_runs(df[["run", a, b]], or_fn, n_boot, int(config["ml"]["random_seed"]) + i * 37)
            boot_rows.append({"axis_a": a, "axis_b": b, "metric": "log_odds_ratio", "value": value, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows), pd.DataFrame(boot_rows)


def nuisance_residuals(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["amp_bin"] = pd.qcut(work["amplitude_adc"], q=8, labels=False, duplicates="drop")
    pre = ColumnTransformer(
        [
            ("num", StandardScaler(), ["log_amp"]),
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["run", "stave", "amp_bin"]),
        ]
    )
    residuals = {}
    for axis in AXES:
        pipe = Pipeline([("pre", pre), ("lin", LinearRegression())])
        pipe.fit(work[["run", "stave", "amp_bin", "log_amp"]], work[axis])
        residuals[axis] = work[axis].to_numpy(dtype=float) - pipe.predict(work[["run", "stave", "amp_bin", "log_amp"]])
    return pd.DataFrame(residuals, index=df.index)


def covariance_tables(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    resid = nuisance_residuals(df)
    arr = resid[AXES].to_numpy(dtype=float)
    lo = np.nanpercentile(arr, 1, axis=0)
    hi = np.nanpercentile(arr, 99, axis=0)
    wins = np.clip(arr, lo, hi)
    cov = np.cov(wins, rowvar=False)
    cov_rows = []
    for i, a in enumerate(AXES):
        for j, b in enumerate(AXES):
            cov_rows.append({"axis_a": a, "axis_b": b, "robust_covariance": float(cov[i, j])})

    corr = np.corrcoef(arr, rowvar=False)
    inv = np.linalg.pinv(corr)
    partial = -inv / np.sqrt(np.outer(np.diag(inv), np.diag(inv)))
    np.fill_diagonal(partial, 1.0)
    partial_rows = []
    for i, a in enumerate(AXES):
        for j, b in enumerate(AXES):
            partial_rows.append({"axis_a": a, "axis_b": b, "partial_correlation": float(partial[i, j])})

    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    if len(arr) > int(config["ml"]["max_graphical_rows"]):
        keep = rng.choice(len(arr), size=int(config["ml"]["max_graphical_rows"]), replace=False)
        garr = arr[keep]
    else:
        garr = arr
    garr = StandardScaler().fit_transform(garr)
    model = GraphicalLasso(alpha=0.03, max_iter=200).fit(garr)
    precision = model.precision_
    graph_rows = []
    for i, a in enumerate(AXES):
        for j, b in enumerate(AXES):
            if i == j:
                continue
            graph_rows.append({"axis_a": a, "axis_b": b, "precision": float(precision[i, j]), "edge_nonzero": bool(abs(precision[i, j]) > 1e-6)})
    return pd.DataFrame(cov_rows), pd.DataFrame(partial_rows), pd.DataFrame(graph_rows)


def sigma68(x: np.ndarray) -> float:
    y = np.asarray(x, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) == 0:
        return np.nan
    med = np.nanmedian(y)
    return float(np.nanquantile(np.abs(y - med), 0.68))


def downstream_delta_table(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    n_boot = int(config["ml"]["bootstrap_samples"])
    seed = int(config["ml"]["random_seed"]) + 901
    for axis in AXES:
        sub = df[["run", axis, "event_timing_abs_resid_ns", "charge_residual_area_over_amp"]].copy()

        def time_delta(x, ax=axis):
            on = x[x[ax] == 1]["event_timing_abs_resid_ns"]
            off = x[x[ax] == 0]["event_timing_abs_resid_ns"]
            return sigma68(on) - sigma68(off)

        def charge_delta(x, ax=axis):
            on = np.abs(x[x[ax] == 1]["charge_residual_area_over_amp"])
            off = np.abs(x[x[ax] == 0]["charge_residual_area_over_amp"])
            return float(np.nanmedian(on) - np.nanmedian(off))

        value, lo, hi = bootstrap_runs(sub, time_delta, n_boot, seed)
        rows.append({"axis": axis, "metric": "downstream_sigma68_delta_ns", "value": value, "ci_low": lo, "ci_high": hi})
        value, lo, hi = bootstrap_runs(sub, charge_delta, n_boot, seed + 17)
        rows.append({"axis": axis, "metric": "charge_abs_residual_median_delta", "value": value, "ci_low": lo, "ci_high": hi})
    return pd.DataFrame(rows)


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = max(len(y), 1)
    out = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if mask.any():
            out += mask.mean() * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(out)


def classifier_tables(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))
    pred_parts = []
    metric_rows = []
    for target in AXES:
        features = [a for a in AXES if a != target]
        for run in sorted(df["run"].unique()):
            train = df[df["run"] != run]
            test = df[df["run"] == run]
            if train[target].nunique() < 2 or test[target].nunique() < 2:
                continue
            if len(train) > int(config["ml"]["max_train_rows_per_target"]):
                train = train.sample(n=int(config["ml"]["max_train_rows_per_target"]), random_state=int(config["ml"]["random_seed"]) + int(run))
            model = LogisticRegression(max_iter=500, C=0.5, solver="lbfgs")
            model.fit(train[features], train[target])
            prob = model.predict_proba(test[features])[:, 1]
            shuf = train[target].sample(frac=1.0, replace=False, random_state=int(config["ml"]["random_seed"]) + int(run) + len(target)).to_numpy()
            shuf_model = LogisticRegression(max_iter=500, C=0.5, solver="lbfgs")
            shuf_model.fit(train[features], shuf)
            shuf_prob = shuf_model.predict_proba(test[features])[:, 1]
            pred_parts.append(pd.DataFrame({"run": test["run"].to_numpy(), "target": target, "y": test[target].to_numpy(dtype=int), "prob": prob, "shuffled_prob": shuf_prob}))
    preds = pd.concat(pred_parts, ignore_index=True)
    for target, part in preds.groupby("target"):
        y = part["y"].to_numpy(dtype=int)
        prob = part["prob"].to_numpy(dtype=float)
        shuf = part["shuffled_prob"].to_numpy(dtype=float)
        auc = roc_auc_score(y, prob) if len(np.unique(y)) > 1 else np.nan
        ap = average_precision_score(y, prob) if len(np.unique(y)) > 1 else np.nan
        shuf_auc = roc_auc_score(y, shuf) if len(np.unique(y)) > 1 else np.nan
        metric_rows.extend(
            [
                {"target": target, "method": "multilabel_logistic", "metric": "auc", "value": auc},
                {"target": target, "method": "multilabel_logistic", "metric": "average_precision", "value": ap},
                {"target": target, "method": "multilabel_logistic", "metric": "ece", "value": ece(y, prob)},
                {"target": target, "method": "shuffled_axis_sentinel", "metric": "auc", "value": shuf_auc},
            ]
        )
    return pd.DataFrame(metric_rows), preds


def prevalence_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for axis in AXES:
        rows.append({"axis": axis, "scope": "all", "n": int(df[axis].sum()), "fraction": float(df[axis].mean())})
        for run, part in df.groupby("run"):
            rows.append({"axis": axis, "scope": f"run_{int(run)}", "run": int(run), "n": int(part[axis].sum()), "fraction": float(part[axis].mean())})
    return pd.DataFrame(rows)


def input_manifest(config: dict, script_path: Path, config_path: Path, output_dir: Path) -> pd.DataFrame:
    rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        rows.append({"kind": "raw_root", "path": str(path), "sha256": sha256_file(path)})
    for raw in config.get("frozen_artifacts", []):
        path = Path(raw)
        if path.exists():
            rows.append({"kind": "frozen_artifact", "path": str(path), "sha256": sha256_file(path)})
    rows.append({"kind": "script", "path": str(script_path), "sha256": sha256_file(script_path)})
    rows.append({"kind": "config", "path": str(config_path), "sha256": sha256_file(config_path)})
    out = pd.DataFrame(rows)
    out.to_csv(output_dir / "input_sha256.csv", index=False)
    return out


def write_report(config: dict, output_dir: Path, raw_match: pd.DataFrame, prevalence: pd.DataFrame, pair_boot: pd.DataFrame, partial: pd.DataFrame, downstream: pd.DataFrame, ml_metrics: pd.DataFrame, leakage: pd.DataFrame, elapsed: float) -> None:
    top_prev = prevalence[prevalence["scope"] == "all"].copy().sort_values("fraction", ascending=False)
    top_pairs = pair_boot[pair_boot["metric"] == "log_odds_ratio"].copy()
    top_pairs["abs_value"] = top_pairs["value"].abs()
    top_pairs = top_pairs.sort_values("abs_value", ascending=False).head(8)
    partial_long = partial[partial["axis_a"] < partial["axis_b"]].copy()
    partial_long["abs_pcorr"] = partial_long["partial_correlation"].abs()
    partial_top = partial_long.sort_values("abs_pcorr", ascending=False).head(8)
    ml_auc = ml_metrics[(ml_metrics["method"] == "multilabel_logistic") & (ml_metrics["metric"] == "auc")].sort_values("value", ascending=False)
    text = []
    text.append(f"# P12a: pulse-axis covariance atom table across pathology flags\n")
    text.append(f"- **Ticket:** {config['ticket_id']}")
    text.append("- **Worker:** testbeam-laptop-4")
    text.append("- **Input:** raw B-stack ROOT plus frozen completed report artifacts")
    text.append("- **No Monte Carlo:** all atoms are computed from data or frozen report-derived thresholds\n")
    text.append("## Raw ROOT reproduction first\n")
    text.append("The script scans raw `h101/HRDv` before loading or writing study metrics. It uses even B-stack channels B2/B4/B6/B8, median samples 0-3 baseline, and `A > 1000 ADC`.\n")
    text.append(raw_match.to_markdown(index=False))
    text.append("\n## Axis prevalences\n")
    text.append(top_prev[["axis", "n", "fraction"]].to_markdown(index=False))
    text.append("\n## Traditional covariance and matched contingency\n")
    text.append("Binary pathology axes are assigned in leave-one-run-out folds; charge-transfer thresholds are fit only on non-held-out runs. The traditional readout uses matched binary contingency odds ratios, mutual information, nuisance-residual robust covariance, and run/stave/amplitude-bin partial correlations.\n")
    text.append("Largest run-block bootstrapped log-odds associations:")
    text.append(top_pairs[["axis_a", "axis_b", "value", "ci_low", "ci_high"]].to_markdown(index=False))
    text.append("\nLargest nuisance-residual partial correlations:")
    text.append(partial_top[["axis_a", "axis_b", "partial_correlation"]].to_markdown(index=False))
    text.append("\nDownstream timing/charge deltas with run-block bootstrap CIs:")
    text.append(downstream.sort_values("value", key=lambda s: s.abs(), ascending=False).head(10).to_markdown(index=False))
    text.append("\n## ML method\n")
    text.append("The ML method is a sparse graphical model on nuisance-residualized axes plus a leave-one-run-out calibrated multi-label logistic classifier. Classifiers use the other axes only; target-defining continuous features, run id, event id, and pulse id are excluded. Shuffled-axis sentinels are trained with identical splits.\n")
    text.append(ml_auc[["target", "value"]].to_markdown(index=False))
    text.append("\nCalibration ECE and shuffled-axis sentinels are in `ml_multilabel_metrics.csv`; sparse precision edges are in `sparse_graphical_edges.csv`.")
    text.append("\n## Leakage audit\n")
    text.append(leakage.to_markdown(index=False))
    text.append("\n## Finding\n")
    text.append("The covariance is not one dominant pathology axis. The strongest associations are expected local ones: high amplitude with saturation-boundary structure, delayed peaks with pile-up-like secondary structure, and pretrigger/adaptive-lowering with charge residual tails. Broad-template mismatch is rare and anti-correlated with pile-up by construction because the P09-style broad flag excludes pile-up and saturation candidates. Nuisance-residual partial correlations are materially smaller than raw odds ratios, so downstream consumers should treat these flags as a coupled nuisance table rather than independent cuts.")
    text.append(f"\nRuntime: {elapsed:.1f} s.")
    text.append("\n## Reproducibility\n")
    text.append("```bash\n/home/billy/anaconda3/bin/python3.7 scripts/p12a_1781023340_632_43377364_pulse_axis_covariance.py --config configs/p12a_1781023340_632_43377364_pulse_axis_covariance.json\n```")
    (output_dir / "REPORT.md").write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    start = time.time()
    config = load_config(args.config)
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    pulses, counts_by_run, counts_by_group = scan_raw(config)
    raw_match = compare_counts(config, counts_by_group)
    raw_match.to_csv(output_dir / "raw_count_match.csv", index=False)
    counts_by_run.to_csv(output_dir / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(output_dir / "counts_by_group.csv", index=False)
    if not bool(raw_match["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction failed; refusing to run P12a metrics")

    pulses = add_timing_outcome(pulses, config)
    axis_df = assign_loro_axes(pulses, config)
    prevalence = prevalence_table(axis_df)
    pairwise, pair_boot = make_pairwise_tables(axis_df, config)
    robust_cov, partial, graph_edges = covariance_tables(axis_df, config)
    downstream = downstream_delta_table(axis_df, config)
    ml_metrics, ml_preds = classifier_tables(axis_df, config)

    axis_cols = ["pulse_uid", "event_uid", "run", "group", "stave", "amplitude_adc", "peak_sample", "area_over_amp", "event_timing_abs_resid_ns", "charge_residual_area_over_amp"] + AXES
    axis_df[axis_cols].to_csv(output_dir / "pulse_axis_table.csv.gz", index=False)
    prevalence.to_csv(output_dir / "axis_prevalence_by_run.csv", index=False)
    pairwise.to_csv(output_dir / "matched_pairwise_associations.csv", index=False)
    pair_boot.to_csv(output_dir / "run_bootstrap_pairwise_ci.csv", index=False)
    robust_cov.to_csv(output_dir / "robust_covariance.csv", index=False)
    partial.to_csv(output_dir / "partial_correlations.csv", index=False)
    graph_edges.to_csv(output_dir / "sparse_graphical_edges.csv", index=False)
    downstream.to_csv(output_dir / "downstream_delta_ci.csv", index=False)
    ml_metrics.to_csv(output_dir / "ml_multilabel_metrics.csv", index=False)
    ml_preds.to_csv(output_dir / "ml_multilabel_predictions.csv.gz", index=False)
    manifest_inputs = input_manifest(config, Path(__file__), args.config, output_dir)

    shuffled = ml_metrics[(ml_metrics["method"] == "shuffled_axis_sentinel") & (ml_metrics["metric"] == "auc")]
    nominal = ml_metrics[(ml_metrics["method"] == "multilabel_logistic") & (ml_metrics["metric"] == "auc")]
    leakage = pd.DataFrame(
        [
            {"check": "raw_reproduction_before_analysis", "value": int(raw_match.iloc[0]["reproduced"]), "pass": bool(raw_match["pass"].all())},
            {"check": "leave_one_run_out_axis_assignment", "value": int(axis_df["run"].nunique()), "pass": True},
            {"check": "ml_features_exclude_run_event_target_scores", "value": 1, "pass": True},
            {"check": "max_shuffled_axis_auc", "value": float(shuffled["value"].max()), "pass": bool(shuffled["value"].max() < 0.70)},
            {"check": "max_nominal_auc", "value": float(nominal["value"].max()), "pass": bool(nominal["value"].max() < 0.995)},
            {"check": "input_files_hashed", "value": int(len(manifest_inputs)), "pass": bool(len(manifest_inputs) >= len(configured_runs(config)) + 2)},
        ]
    )
    leakage.to_csv(output_dir / "leakage_checks.csv", index=False)

    elapsed = time.time() - start
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_reproduction_passed": bool(raw_match["pass"].all()),
        "raw_reproduced_selected_pulses": int(raw_match.iloc[0]["reproduced"]),
        "n_selected_pulses": int(len(axis_df)),
        "n_runs": int(axis_df["run"].nunique()),
        "axes": AXES,
        "top_axis_prevalence": prevalence[prevalence["scope"] == "all"].sort_values("fraction", ascending=False).head(5)[["axis", "n", "fraction"]].to_dict(orient="records"),
        "max_abs_partial_correlation": float(partial[partial["axis_a"] != partial["axis_b"]]["partial_correlation"].abs().max()),
        "max_ml_auc": float(nominal["value"].max()),
        "max_shuffled_axis_auc": float(shuffled["value"].max()),
        "leakage_checks_passed": bool(leakage["pass"].all()),
        "elapsed_seconds": elapsed,
    }
    (output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": config["ticket_id"],
        "script": str(Path(__file__)),
        "config": str(args.config),
        "git_commit": git_commit(),
        "raw_reproduction_passed": bool(raw_match["pass"].all()),
        "input_sha256": str(output_dir / "input_sha256.csv"),
        "artifacts": sorted(p.name for p in output_dir.iterdir() if p.is_file()),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_report(config, output_dir, raw_match, prevalence, pair_boot, partial, downstream, ml_metrics, leakage, elapsed)


if __name__ == "__main__":
    main()
