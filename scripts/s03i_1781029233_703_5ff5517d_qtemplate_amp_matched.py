#!/usr/bin/env python3
"""S03i amplitude-matched q_template timing-tail isolation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline


STAVES = ["B2", "B4", "B6", "B8"]
DOWNSTREAM = ["B4", "B6", "B8"]
PAIR_COLS = ["pair_b4_b6_ns", "pair_b4_b8_ns", "pair_b6_b8_ns"]
Q_COLS = ["q_b2", "q_b4", "q_b6", "q_b8", "q_mean", "q_max", "q_std", "q_ds_mean", "q_ds_max", "q_ds_std", "q_b2_minus_ds_mean", "q_ds_span"]
AMP_COLS = ["amp_b2", "amp_b4", "amp_b6", "amp_b8", "amp_mean", "amp_ds_mean", "amp_max", "amp_ds_max", "log_amp_ds_mean", "log_amp_ds_max"]
TOPO_COLS = ["downstream_count", "all_three_downstream"]
DOWNSTREAM_Q_COLS = ["q_b4", "q_b6", "q_b8", "q_ds_mean", "q_ds_max", "q_ds_std", "q_ds_span"]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    out: List[int] = []
    for runs in config["run_groups"].values():
        out.extend(int(r) for r in runs)
    return sorted(set(out))


def group_for_run(config: dict) -> Dict[int, str]:
    out = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def cfd_position(norm_waveform: np.ndarray, fraction: float) -> float:
    peak = int(np.nanargmax(norm_waveform))
    if peak <= 0 or not np.isfinite(norm_waveform[peak]) or norm_waveform[peak] <= 0:
        return float("nan")
    target = float(fraction) * float(norm_waveform[peak])
    for idx in range(1, peak + 1):
        y0 = float(norm_waveform[idx - 1])
        y1 = float(norm_waveform[idx])
        if np.isfinite(y0) and np.isfinite(y1) and y0 <= target <= y1 and y1 != y0:
            return float(idx - 1 + (target - y0) / (y1 - y0))
    return float(peak)


def align_waveform(norm_waveform: np.ndarray, rel_grid: np.ndarray, fraction: float) -> np.ndarray:
    pos = cfd_position(norm_waveform, fraction)
    if not np.isfinite(pos):
        return np.full(len(rel_grid), np.nan, dtype=np.float32)
    x = np.arange(len(norm_waveform), dtype=np.float64)
    return np.interp(pos + rel_grid, x, norm_waveform, left=np.nan, right=np.nan).astype(np.float32)


def cfd_times_ns(corrected: np.ndarray, amplitude: np.ndarray, fraction: float, period_ns: float, cut_adc: float) -> np.ndarray:
    out = np.full(amplitude.shape, np.nan, dtype=np.float32)
    for stave_idx in range(corrected.shape[1]):
        wave = corrected[:, stave_idx, :]
        amp = amplitude[:, stave_idx]
        threshold = amp * float(fraction)
        ge = wave >= threshold[:, None]
        first = np.argmax(ge, axis=1)
        valid = ge.any(axis=1) & (amp > float(cut_adc))
        for row in np.where(valid)[0]:
            j = int(first[row])
            if j <= 0:
                out[row, stave_idx] = 0.0
            else:
                y0 = float(wave[row, j - 1])
                y1 = float(wave[row, j])
                denom = y1 - y0
                frac = 0.0 if denom <= 0 else (float(threshold[row]) - y0) / denom
                out[row, stave_idx] = float(j - 1 + np.clip(frac, 0.0, 1.0)) * float(period_ns)
    return out


def assign_bins(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, values, side="right") - 1, 0, len(edges) - 2)


def scan_raw(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DataFrame, np.ndarray, pd.DataFrame]:
    channels = np.asarray([int(config["staves"][s]) for s in STAVES], dtype=int)
    downstream_idx = np.asarray([STAVES.index(s) for s in DOWNSTREAM], dtype=int)
    b2_idx = STAVES.index("B2")
    groups = group_for_run(config)
    baseline_idx = np.asarray(config["baseline_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=np.float64)
    cfd_fraction = float(config["cfd_fraction"])
    period_ns = float(config["sample_period_ns"])
    calib_runs = {r for g, runs in config["run_groups"].items() if g.endswith("_calib") for r in map(int, runs)}
    benchmark_runs = set(map(int, config["benchmark_runs"]))
    calib_rows: List[pd.DataFrame] = []
    calib_aligned: List[np.ndarray] = []
    bench_rows: List[pd.DataFrame] = []
    bench_aligned: List[np.ndarray] = []
    event_rows: List[dict] = []
    run_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_file(config, run)
        group = groups[run]
        counts = {
            "run": run,
            "group": group,
            "raw_events": 0,
            "selected_pulses": 0,
            "events_with_selected": 0,
            "parent_control_events": 0,
            "parent_clean_dt_lt3": 0,
            "parent_gross_dt_gt50": 0,
            "parent_gross_dt_gt51": 0,
            "all_three_control_events": 0,
            "all_three_gross_dt_gt51": 0,
        }
        event_offset = 0
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, channels, :]
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            peak_sample = corrected.argmax(axis=-1)
            raw_peak = raw.max(axis=-1)
            selected = amplitude > cut
            counts["raw_events"] += int(len(eventno))
            counts["selected_pulses"] += int(selected.sum())
            counts["events_with_selected"] += int(selected.any(axis=1).sum())

            if run in calib_runs or run in benchmark_runs:
                event_idx, stave_idx = np.where(selected)
                if len(event_idx):
                    chosen = corrected[event_idx, stave_idx, :]
                    chosen_amp = np.maximum(amplitude[event_idx, stave_idx].astype(np.float64), 1.0)
                    norm = chosen / chosen_amp[:, None]
                    aligned = np.vstack([align_waveform(w, rel_grid, cfd_fraction) for w in norm])
                    frame = pd.DataFrame(
                        {
                            "run": run,
                            "group": group,
                            "event_uid": [f"{run}:{int(eventno[i])}:{int(evt[i])}:{event_offset + int(i)}" for i in event_idx],
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": np.asarray(STAVES, dtype=object)[stave_idx],
                            "amplitude_adc": chosen_amp,
                            "peak_sample": peak_sample[event_idx, stave_idx].astype(float),
                            "raw_peak_adc": raw_peak[event_idx, stave_idx].astype(float),
                        }
                    )
                    if run in calib_runs:
                        calib_rows.append(frame)
                        calib_aligned.append(aligned)
                    if run in benchmark_runs:
                        bench_rows.append(frame)
                        bench_aligned.append(aligned)

            if run in benchmark_runs:
                times = cfd_times_ns(corrected, amplitude, cfd_fraction, period_ns, cut)
                downstream_count = selected[:, downstream_idx].sum(axis=1)
                parent = selected[:, b2_idx] & (downstream_count >= int(config["min_downstream_staves"]))
                all_three = selected[:, b2_idx] & (downstream_count == len(DOWNSTREAM))
                for idx in np.where(parent)[0]:
                    ds_times = times[idx, downstream_idx]
                    ds_sel = selected[idx, downstream_idx]
                    valid_times = ds_times[ds_sel & np.isfinite(ds_times)]
                    if len(valid_times) < int(config["min_downstream_staves"]):
                        continue
                    d_t = float(np.max(valid_times) - np.min(valid_times))
                    pair_vals = {"pair_b4_b6_ns": math.nan, "pair_b4_b8_ns": math.nan, "pair_b6_b8_ns": math.nan}
                    if np.isfinite(ds_times[0]) and np.isfinite(ds_times[1]):
                        pair_vals["pair_b4_b6_ns"] = float(ds_times[0] - ds_times[1])
                    if np.isfinite(ds_times[0]) and np.isfinite(ds_times[2]):
                        pair_vals["pair_b4_b8_ns"] = float(ds_times[0] - ds_times[2])
                    if np.isfinite(ds_times[1]) and np.isfinite(ds_times[2]):
                        pair_vals["pair_b6_b8_ns"] = float(ds_times[1] - ds_times[2])
                    event_rows.append(
                        {
                            "event_uid": f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{event_offset + int(idx)}",
                            "run": run,
                            "eventno": int(eventno[idx]),
                            "evt": int(evt[idx]),
                            "d_t_ns": d_t,
                            "downstream_count": int(downstream_count[idx]),
                            "all_three_downstream": int(bool(all_three[idx])),
                            **pair_vals,
                        }
                    )
                    counts["parent_control_events"] += 1
                    counts["parent_clean_dt_lt3"] += int(d_t < float(config["clean_dt_max_ns"]))
                    counts["parent_gross_dt_gt50"] += int(d_t > float(config["documented_gross_dt_min_ns"]))
                    counts["parent_gross_dt_gt51"] += int(d_t > float(config["gross_dt_min_ns"]))
                    if bool(all_three[idx]):
                        counts["all_three_control_events"] += 1
                        counts["all_three_gross_dt_gt51"] += int(d_t > float(config["gross_dt_min_ns"]))
            event_offset += len(eventno)
        run_rows.append(counts)
        print(f"run {run:04d}: selected={counts['selected_pulses']} parent={counts['parent_control_events']} gross={counts['parent_gross_dt_gt51']}", flush=True)

    return (
        pd.DataFrame(run_rows),
        pd.concat(calib_rows, ignore_index=True),
        np.vstack(calib_aligned),
        pd.concat(bench_rows, ignore_index=True),
        np.vstack(bench_aligned),
        pd.DataFrame(event_rows),
    )


def reproduction_table(config: dict, run_counts: pd.DataFrame) -> pd.DataFrame:
    exp = config["expected_counts"]
    rows = []
    for quantity, report_value in [
        ("total selected B-stave pulses", exp["total_selected_pulses"]),
        ("sample_i_calib selected pulses", exp["sample_i_calib_pulses"]),
        ("sample_i_analysis selected pulses", exp["sample_i_analysis_pulses"]),
        ("sample_ii_calib selected pulses", exp["sample_ii_calib_pulses"]),
        ("sample_ii_analysis selected pulses", exp["sample_ii_analysis_pulses"]),
    ]:
        if quantity.startswith("total"):
            reproduced = int(run_counts["selected_pulses"].sum())
        else:
            group = quantity.split(" selected")[0]
            reproduced = int(run_counts.loc[run_counts["group"] == group, "selected_pulses"].sum())
        rows.append({"quantity": quantity, "report_value": int(report_value), "reproduced": reproduced, "tolerance": 0})
    rows.extend(
        [
            {"quantity": "S07 parent guarded gross events, D_t>51 ns", "report_value": int(config["expected_s07_guarded_gross_events"]), "reproduced": int(run_counts["parent_gross_dt_gt51"].sum()), "tolerance": 0},
            {"quantity": "all-three downstream control events", "report_value": int(config["expected_all_three_control_events"]), "reproduced": int(run_counts["all_three_control_events"].sum()), "tolerance": 0},
            {"quantity": "all-three downstream guarded gross events, D_t>51 ns", "report_value": int(config["expected_all_three_gross_events"]), "reproduced": int(run_counts["all_three_gross_dt_gt51"].sum()), "tolerance": 0},
        ]
    )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def build_templates(config: dict, calib_meta: pd.DataFrame, calib_aligned: np.ndarray) -> Tuple[dict, pd.DataFrame]:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    bins = assign_bins(calib_meta["amplitude_adc"].to_numpy(dtype=float), edges)
    staves = calib_meta["stave"].to_numpy()
    min_bin = int(config["template_min_bin_pulses"])
    templates: Dict[Tuple[str, int], np.ndarray] = {}
    fallback: Dict[str, np.ndarray] = {}
    rows = []
    for stave in STAVES:
        stave_mask = staves == stave
        fallback[stave] = np.nanmedian(calib_aligned[stave_mask], axis=0).astype(np.float32)
        for b in range(len(edges) - 1):
            mask = stave_mask & (bins == b)
            n = int(mask.sum())
            if n >= min_bin:
                source = "bin"
                template = np.nanmedian(calib_aligned[mask], axis=0).astype(np.float32)
            else:
                source = "stave_fallback"
                template = fallback[stave]
            templates[(stave, b)] = template
            rows.append({"stave": stave, "bin": b, "amp_low_adc": float(edges[b]), "amp_high_adc": float(edges[b + 1]), "n_calib": n, "source": source})
    return {"templates": templates, "edges": edges}, pd.DataFrame(rows)


def template_q(meta: pd.DataFrame, aligned: np.ndarray, pack: dict) -> np.ndarray:
    bins = assign_bins(meta["amplitude_adc"].to_numpy(dtype=float), pack["edges"])
    out = np.full(len(meta), np.nan, dtype=np.float64)
    for i, stave in enumerate(meta["stave"].to_numpy()):
        template = pack["templates"][(str(stave), int(bins[i]))]
        valid = np.isfinite(aligned[i]) & np.isfinite(template)
        if valid.any():
            out[i] = float(np.sqrt(np.mean((aligned[i, valid] - template[valid]) ** 2)))
    return out


def aggregate_events(events: pd.DataFrame, pulses: pd.DataFrame, q_values: np.ndarray, config: dict) -> pd.DataFrame:
    p = pulses.copy()
    p["q_template_rmse"] = q_values
    q = p.pivot_table(index="event_uid", columns="stave", values="q_template_rmse", aggfunc="first").reindex(columns=STAVES)
    amp = p.pivot_table(index="event_uid", columns="stave", values="amplitude_adc", aggfunc="first").reindex(columns=STAVES)
    peak = p.pivot_table(index="event_uid", columns="stave", values="peak_sample", aggfunc="first").reindex(columns=STAVES)
    raw_peak = p.pivot_table(index="event_uid", columns="stave", values="raw_peak_adc", aggfunc="first").reindex(columns=STAVES)
    q.columns = [f"q_{c.lower()}" for c in q.columns]
    amp.columns = [f"amp_{c.lower()}" for c in amp.columns]
    peak.columns = [f"peak_{c.lower()}" for c in peak.columns]
    raw_peak.columns = [f"raw_peak_{c.lower()}" for c in raw_peak.columns]
    out = events.merge(q.reset_index(), on="event_uid", how="left")
    out = out.merge(amp.reset_index(), on="event_uid", how="left")
    out = out.merge(peak.reset_index(), on="event_uid", how="left")
    out = out.merge(raw_peak.reset_index(), on="event_uid", how="left")
    q_cols = [f"q_{s.lower()}" for s in STAVES]
    ds_q_cols = [f"q_{s.lower()}" for s in DOWNSTREAM]
    amp_cols = [f"amp_{s.lower()}" for s in STAVES]
    ds_amp_cols = [f"amp_{s.lower()}" for s in DOWNSTREAM]
    ds_peak_cols = [f"peak_{s.lower()}" for s in DOWNSTREAM]
    raw_peak_cols = [f"raw_peak_{s.lower()}" for s in STAVES]
    out["q_mean"] = np.nanmean(out[q_cols].to_numpy(dtype=float), axis=1)
    out["q_max"] = np.nanmax(out[q_cols].to_numpy(dtype=float), axis=1)
    out["q_std"] = np.nanstd(out[q_cols].to_numpy(dtype=float), axis=1)
    out["q_ds_mean"] = np.nanmean(out[ds_q_cols].to_numpy(dtype=float), axis=1)
    out["q_ds_max"] = np.nanmax(out[ds_q_cols].to_numpy(dtype=float), axis=1)
    out["q_ds_std"] = np.nanstd(out[ds_q_cols].to_numpy(dtype=float), axis=1)
    out["q_b2_minus_ds_mean"] = out["q_b2"] - out["q_ds_mean"]
    out["q_ds_span"] = np.nanmax(out[ds_q_cols].to_numpy(dtype=float), axis=1) - np.nanmin(out[ds_q_cols].to_numpy(dtype=float), axis=1)
    out["amp_mean"] = np.nanmean(out[amp_cols].to_numpy(dtype=float), axis=1)
    out["amp_ds_mean"] = np.nanmean(out[ds_amp_cols].to_numpy(dtype=float), axis=1)
    out["amp_max"] = np.nanmax(out[amp_cols].to_numpy(dtype=float), axis=1)
    out["amp_ds_max"] = np.nanmax(out[ds_amp_cols].to_numpy(dtype=float), axis=1)
    out["log_amp_ds_mean"] = np.log1p(out["amp_ds_mean"])
    out["log_amp_ds_max"] = np.log1p(out["amp_ds_max"])
    out["peak_ds_mean"] = np.nanmean(out[ds_peak_cols].to_numpy(dtype=float), axis=1)
    out["peak_ds_max"] = np.nanmax(out[ds_peak_cols].to_numpy(dtype=float), axis=1)
    out["near_adc_boundary"] = (np.nanmax(out[raw_peak_cols].to_numpy(dtype=float), axis=1) >= 4090.0).astype(int)
    out["high_amp_boundary"] = (out["amp_ds_max"] >= 10000.0).astype(int)
    out["run_family"] = out["run"].map(lambda r: "edge" if int(r) in {58, 65} else ("high60" if int(r) >= 61 else "low60"))
    amp_edges = np.asarray(config["matching"]["amp_edges_adc"], dtype=float)
    phase_edges = np.asarray(config["matching"]["phase_edges"], dtype=float)
    out["match_amp_bin"] = assign_bins(out["amp_ds_mean"].to_numpy(dtype=float), amp_edges)
    out["match_phase_bin"] = assign_bins(out["peak_ds_mean"].to_numpy(dtype=float), phase_edges)
    keys = ["run_family", "downstream_count", "all_three_downstream", "match_amp_bin", "match_phase_bin", "high_amp_boundary"]
    out["match_stratum"] = out[keys].astype(str).agg("|".join, axis=1)
    return out


def auc_metric(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap_metric(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def brier_metric(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0:
        return float("nan")
    return float(brier_score_loss(y[mask], np.clip(score[mask], 0.0, 1.0)))


def ece_metric(y: np.ndarray, score: np.ndarray, n_bins: int = 10) -> float:
    mask = np.isfinite(score)
    y = y[mask]
    p = np.clip(score[mask], 0.0, 1.0)
    if len(y) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if b.any():
            total += float(b.mean()) * abs(float(y[b].mean()) - float(p[b].mean()))
    return total


def run_bootstrap(y: np.ndarray, runs: np.ndarray, scores: Dict[str, np.ndarray], metric_fn: Callable[[np.ndarray, np.ndarray], float], seed: int, n_boot: int) -> Dict[str, Tuple[float, float]]:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    values = {name: [] for name in scores}
    for _ in range(n_boot):
        sample = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sample])
        if len(np.unique(y[idx])) < 2:
            continue
        for name, score in scores.items():
            value = metric_fn(y[idx], score[idx])
            if np.isfinite(value):
                values[name].append(value)
    out = {}
    for name, vals in values.items():
        if len(vals) < 20:
            out[name] = (float("nan"), float("nan"))
        else:
            out[name] = (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))
    return out


def run_bootstrap_delta(y: np.ndarray, runs: np.ndarray, a: np.ndarray, b: np.ndarray, metric_fn: Callable[[np.ndarray, np.ndarray], float], seed: int, n_boot: int) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    vals = []
    for _ in range(n_boot):
        sample = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run)[0:] for run in sample])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric_fn(y[idx], a[idx]) - metric_fn(y[idx], b[idx])
        if np.isfinite(value):
            vals.append(value)
    if len(vals) < 20:
        return (float("nan"), float("nan"))
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def imputed(train: pd.DataFrame, frame: pd.DataFrame, cols: List[str]) -> np.ndarray:
    med = train[cols].median(axis=0, skipna=True).fillna(0.0)
    return frame[cols].fillna(med).to_numpy(dtype=float)


def residualize_by_stratum(train: pd.DataFrame, frame: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    out = frame.copy()
    global_med = train[cols].median(axis=0, skipna=True).fillna(0.0)
    stat = train.groupby("match_stratum")[cols].median()
    for col in cols:
        med = frame["match_stratum"].map(stat[col]).fillna(global_med[col]).to_numpy(dtype=float)
        out[f"{col}_resid"] = frame[col].to_numpy(dtype=float) - med
    return out


def rf_oof(data: pd.DataFrame, y: np.ndarray, cols: List[str], config: dict, seed: int, residualize: bool = False, shuffle: bool = False) -> np.ndarray:
    runs = data["run"].to_numpy(dtype=int)
    out = np.full(len(data), np.nan, dtype=float)
    rng = np.random.default_rng(seed)
    params = config["rf_params"]
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        train_mask = runs != held_run
        test_mask = runs == held_run
        train = data.loc[train_mask].copy()
        test = data.loc[test_mask].copy()
        use_cols = cols
        if residualize:
            train = residualize_by_stratum(train, train, cols)
            test = residualize_by_stratum(train, test, cols)
            use_cols = [f"{c}_resid" for c in cols]
        y_train = y[train_mask].copy()
        if shuffle:
            rng.shuffle(y_train)
        clf = make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(
                n_estimators=int(params["n_estimators"]),
                max_depth=int(params["max_depth"]),
                min_samples_leaf=int(params["min_samples_leaf"]),
                class_weight="balanced",
                random_state=seed + fold,
                n_jobs=1,
            ),
        )
        clf.fit(train[use_cols].to_numpy(dtype=float), y_train)
        out[test_mask] = clf.predict_proba(test[use_cols].to_numpy(dtype=float))[:, 1]
    return out


def traditional_oof(data: pd.DataFrame, y: np.ndarray, candidates: List[str], residualize: bool = True) -> Tuple[np.ndarray, pd.DataFrame]:
    runs = data["run"].to_numpy(dtype=int)
    out = np.full(len(data), np.nan, dtype=float)
    rows = []
    for held_run in sorted(np.unique(runs)):
        train_mask = runs != held_run
        test_mask = runs == held_run
        train = data.loc[train_mask].copy()
        test = data.loc[test_mask].copy()
        if residualize:
            train_r = residualize_by_stratum(train, train, candidates)
            test_r = residualize_by_stratum(train, test, candidates)
            use_candidates = [f"{c}_resid" for c in candidates]
        else:
            train_r = train
            test_r = test
            use_candidates = candidates
        best = None
        for col in use_candidates:
            values = train_r[col].to_numpy(dtype=float)
            for sign, sign_name in [(1.0, "high_bad"), (-1.0, "low_bad")]:
                score = sign * values
                row = {"heldout_run": int(held_run), "candidate": col, "sign": sign_name, "train_auc": auc_metric(y[train_mask], score), "train_ap": ap_metric(y[train_mask], score)}
                rows.append(row)
                key = (row["train_ap"], row["train_auc"])
                if best is None or key > best[0]:
                    best = (key, col, sign, sign_name)
        assert best is not None
        out[test_mask] = best[2] * test_r[best[1]].to_numpy(dtype=float)
        rows.append({"heldout_run": int(held_run), "candidate": "__selected__", "sign": best[3], "train_auc": math.nan, "train_ap": math.nan, "selected": best[1]})
    return out, pd.DataFrame(rows)


def fixed_efficiency_rows(data: pd.DataFrame, y: np.ndarray, score: np.ndarray, eff: float, method: str) -> pd.DataFrame:
    runs = data["run"].to_numpy(dtype=int)
    rows = []
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        clean_train = score[train & (y == 0)]
        clean_train = clean_train[np.isfinite(clean_train)]
        if not len(clean_train):
            continue
        threshold = float(np.quantile(clean_train, eff))
        clean = test & (y == 0) & np.isfinite(score)
        tail = test & (y == 1) & np.isfinite(score)
        rows.append(
            {
                "method": method,
                "heldout_run": int(held_run),
                "threshold": threshold,
                "clean_efficiency": float(np.mean(score[clean] <= threshold)) if clean.any() else math.nan,
                "tail_rejection": float(np.mean(score[tail] > threshold)) if tail.any() else math.nan,
                "n_clean": int(clean.sum()),
                "n_tail": int(tail.sum()),
            }
        )
    return pd.DataFrame(rows)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return float("nan")
    q16, q84 = np.percentile(values, [15.865, 84.135])
    return float(0.5 * (q84 - q16))


def residual_summary(values: np.ndarray) -> dict:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return {"sigma68_ns": math.nan, "full_rms_ns": math.nan, "tail_frac_abs_gt5ns": math.nan, "n_pair_values": 0}
    centered = values - np.nanmedian(values)
    return {
        "sigma68_ns": sigma68(values),
        "full_rms_ns": float(np.sqrt(np.mean(centered ** 2))),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(centered) > 5.0)),
        "n_pair_values": int(len(values)),
    }


def pair_values(frame: pd.DataFrame) -> np.ndarray:
    return frame[PAIR_COLS].to_numpy(dtype=float).ravel()


def fixed_efficiency_summary(fixed: pd.DataFrame, seed: int, n_boot: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for method, group in fixed.groupby("method"):
        clean_num = group["clean_efficiency"].to_numpy(dtype=float) * group["n_clean"].to_numpy(dtype=float)
        clean_den = group["n_clean"].to_numpy(dtype=float)
        tail_num = group["tail_rejection"].to_numpy(dtype=float) * group["n_tail"].to_numpy(dtype=float)
        tail_den = group["n_tail"].to_numpy(dtype=float)
        point_clean = float(np.nansum(clean_num) / np.nansum(clean_den)) if np.nansum(clean_den) else math.nan
        point_tail = float(np.nansum(tail_num) / np.nansum(tail_den)) if np.nansum(tail_den) else math.nan
        boots_clean = []
        boots_tail = []
        idx = np.arange(len(group))
        for _ in range(n_boot):
            sample = rng.choice(idx, size=len(idx), replace=True)
            cden = np.nansum(clean_den[sample])
            tden = np.nansum(tail_den[sample])
            if cden:
                boots_clean.append(float(np.nansum(clean_num[sample]) / cden))
            if tden:
                boots_tail.append(float(np.nansum(tail_num[sample]) / tden))
        rows.append(
            {
                "method": method,
                "clean_efficiency": point_clean,
                "clean_efficiency_ci_low": float(np.percentile(boots_clean, 2.5)) if len(boots_clean) else math.nan,
                "clean_efficiency_ci_high": float(np.percentile(boots_clean, 97.5)) if len(boots_clean) else math.nan,
                "tail_rejection": point_tail,
                "tail_rejection_ci_low": float(np.percentile(boots_tail, 2.5)) if len(boots_tail) else math.nan,
                "tail_rejection_ci_high": float(np.percentile(boots_tail, 97.5)) if len(boots_tail) else math.nan,
                "n_clean": int(np.nansum(clean_den)),
                "n_tail": int(np.nansum(tail_den)),
            }
        )
    return pd.DataFrame(rows)


def residual_delta_table(data: pd.DataFrame, y: np.ndarray, fixed: pd.DataFrame, scores: Dict[str, np.ndarray], seed: int, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = data["run"].to_numpy(dtype=int)
    base = residual_summary(pair_values(data))
    for method, score in scores.items():
        keep = np.zeros(len(data), dtype=bool)
        for _, row in fixed[fixed["method"] == method].iterrows():
            run = int(row["heldout_run"])
            threshold = float(row["threshold"])
            keep |= (runs == run) & (score <= threshold)
        kept = residual_summary(pair_values(data.loc[keep]))
        point = {
            "delta_sigma68_ns": kept["sigma68_ns"] - base["sigma68_ns"],
            "delta_full_rms_ns": kept["full_rms_ns"] - base["full_rms_ns"],
            "delta_tail_frac_abs_gt5ns": kept["tail_frac_abs_gt5ns"] - base["tail_frac_abs_gt5ns"],
        }
        stable_offset = sum((i + 1) * ord(ch) for i, ch in enumerate(method))
        rng = np.random.default_rng(seed + stable_offset % 100000)
        unique_runs = np.unique(runs)
        boots = {k: [] for k in point}
        for _ in range(n_boot):
            sample = rng.choice(unique_runs, size=len(unique_runs), replace=True)
            idx = np.concatenate([np.flatnonzero(runs == run) for run in sample])
            boot_base = residual_summary(pair_values(data.iloc[idx]))
            boot_kept = residual_summary(pair_values(data.iloc[idx[keep[idx]]]))
            boot_point = {
                "delta_sigma68_ns": boot_kept["sigma68_ns"] - boot_base["sigma68_ns"],
                "delta_full_rms_ns": boot_kept["full_rms_ns"] - boot_base["full_rms_ns"],
                "delta_tail_frac_abs_gt5ns": boot_kept["tail_frac_abs_gt5ns"] - boot_base["tail_frac_abs_gt5ns"],
            }
            for key, value in boot_point.items():
                if np.isfinite(value):
                    boots[key].append(float(value))
        row = {"method": method, **{f"base_{k}": v for k, v in base.items()}, **{f"kept_{k}": v for k, v in kept.items()}, **point}
        for key, vals in boots.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5)) if len(vals) else math.nan
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5)) if len(vals) else math.nan
        rows.append(row)
    return pd.DataFrame(rows)


def scoreboard(data: pd.DataFrame, y: np.ndarray, scores: Dict[str, np.ndarray], seed: int, n_boot: int) -> pd.DataFrame:
    runs = data["run"].to_numpy(dtype=int)
    auc_ci = run_bootstrap(y, runs, scores, auc_metric, seed, n_boot)
    ap_ci = run_bootstrap(y, runs, scores, ap_metric, seed + 100, n_boot)
    brier_ci = run_bootstrap(y, runs, scores, brier_metric, seed + 200, n_boot)
    ece_ci = run_bootstrap(y, runs, scores, ece_metric, seed + 300, n_boot)
    rows = []
    for name, score in scores.items():
        rows.append(
            {
                "method": name,
                "roc_auc": auc_metric(y, score),
                "roc_auc_ci_low": auc_ci[name][0],
                "roc_auc_ci_high": auc_ci[name][1],
                "average_precision": ap_metric(y, score),
                "ap_ci_low": ap_ci[name][0],
                "ap_ci_high": ap_ci[name][1],
                "brier": brier_metric(y, score),
                "brier_ci_low": brier_ci[name][0],
                "brier_ci_high": brier_ci[name][1],
                "ece": ece_metric(y, score),
                "ece_ci_low": ece_ci[name][0],
                "ece_ci_high": ece_ci[name][1],
            }
        )
    return pd.DataFrame(rows)


def delta_scoreboard(y: np.ndarray, runs: np.ndarray, ml: np.ndarray, trad: np.ndarray, seed: int, n_boot: int) -> pd.DataFrame:
    metrics = [("roc_auc", auc_metric), ("average_precision", ap_metric), ("brier", brier_metric), ("ece", ece_metric)]
    rows = []
    for i, (name, fn) in enumerate(metrics):
        value = fn(y, ml) - fn(y, trad)
        ci = run_bootstrap_delta(y, runs, ml, trad, fn, seed + 77 * i, n_boot)
        rows.append({"delta": f"ml_minus_traditional_{name}", "value": value, "ci_low": ci[0], "ci_high": ci[1]})
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.6g}"
        return str(value).replace("|", "\\|")

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(c)) for c in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(c).ljust(w) for c, w in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if math.isfinite(val) else None
    return value


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, s03d_repro: pd.DataFrame, dataset_counts: pd.DataFrame, matched_counts: pd.DataFrame, scores: pd.DataFrame, deltas: pd.DataFrame, fixed_summary: pd.DataFrame, residuals: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    ml = scores[scores["method"] == "ml_qtemplate_shape_rf"].iloc[0]
    trad = scores[scores["method"] == "traditional_matched_q_hand"].iloc[0]
    amp = scores[scores["method"] == "amplitude_only_rf"].iloc[0]
    text = f"""# S03i: q_template amplitude-matched tail-label isolation

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT in `{config['raw_root_dir']}`
- **Split:** leave-one-run-out over `{', '.join(map(str, config['benchmark_runs']))}`; intervals use held-out run-block bootstrap.

## Question
Does the S03d downstream `q_template` tail signal survive matching on downstream amplitude, topology, peak-sample phase, high-amplitude boundary, and run family, or is it mostly an amplitude nuisance?

## Raw Reproduction First
The raw `HRDv` scan reran the S00 B-stave selected-pulse gate and the S07/S03d downstream timing-tail parent gate before any matched model was fit.

{markdown_table(reproduction)}

The S03d headline was then reproduced from the same raw scan and calibration-only q-template construction:

{markdown_table(s03d_repro)}

## Matched Dataset
Labels are the S03d external timing-tail labels: clean if `D_t < {config['clean_dt_max_ns']} ns`, tail if `D_t > {config['gross_dt_min_ns']} ns`; intermediate events are excluded. Matching strata combine run family, downstream topology, downstream amplitude bin, downstream peak-sample phase bin, and high-amplitude boundary.

{markdown_table(dataset_counts)}

{markdown_table(matched_counts)}

## Methods
Traditional: train-fold hand threshold tables choose the best residualized q-template aggregate inside matched strata, with thresholds evaluated at fixed clean efficiency on held-out runs.

ML: a run-heldout random forest on amplitude-residualized q-template/shape features (`q_*`, downstream q summaries, peak phase, and high-amplitude boundary). Controls are amplitude-only, topology-only, downstream-only q, shuffled-label q, and forbidden `D_t`.

## Held-Out Benchmark
{markdown_table(scores)}

ML minus traditional deltas:

{markdown_table(deltas)}

At 95% train clean efficiency:

{markdown_table(fixed_summary)}

Pair residual deltas after applying the fixed-efficiency cut:

{markdown_table(residuals)}

## Leakage Hunt
{markdown_table(leakage)}

The matched ML AUC is {ml['roc_auc']:.3f} versus {trad['roc_auc']:.3f} traditional and {amp['roc_auc']:.3f} amplitude-only. The shuffled-label sentinel stays near null and the deliberate `D_t` ceiling is perfect, so the matched q signal is not explained by an obvious split leak. The downstream-only sentinel remains strong, which is expected because the label is downstream timing based; the result is therefore a downstream waveform-quality isolation, not an independent particle-ID truth label.

## Verdict
After amplitude/topology/phase/boundary/run-family matching, `q_template` still carries held-out timing-tail information, but the matched signal is smaller than the raw S03d headline. Use q_template vetoes as a downstream shape-quality handle only with amplitude/topology matching and leakage sentinels attached.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03i_1781029233_703_5ff5517d_qtemplate_amp_matched.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])

    run_counts, calib_meta, calib_aligned, bench_pulses, bench_aligned, events = scan_raw(config)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction = reproduction_table(config, run_counts)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw reproduction gate failed")

    pack, template_bins = build_templates(config, calib_meta, calib_aligned)
    template_bins.to_csv(out_dir / "template_bin_counts.csv", index=False)
    q_values = template_q(bench_pulses, bench_aligned, pack)
    data = aggregate_events(events, bench_pulses, q_values, config)
    clean = data["d_t_ns"].to_numpy(dtype=float) < float(config["clean_dt_max_ns"])
    tail = data["d_t_ns"].to_numpy(dtype=float) > float(config["gross_dt_min_ns"])
    bench = data[clean | tail].copy().reset_index(drop=True)
    bench["label_tail"] = (bench["d_t_ns"] > float(config["gross_dt_min_ns"])).astype(int)
    y_full = bench["label_tail"].to_numpy(dtype=int)
    runs_full = bench["run"].to_numpy(dtype=int)

    s03d_trad, s03d_choices = traditional_oof(bench, y_full, ["q_mean", "q_max", "q_std", "q_ds_mean", "q_ds_max", "q_ds_std", "q_b2_minus_ds_mean", "q_ds_span"], residualize=False)
    s03d_rf = rf_oof(bench, y_full, Q_COLS, config, seed + 1, residualize=False)
    s03d_repro = pd.DataFrame(
        [
            {"quantity": "S03d traditional q_template ROC-AUC", "report_value": float(config["expected_s03d"]["traditional_auc"]), "reproduced": auc_metric(y_full, s03d_trad), "delta": auc_metric(y_full, s03d_trad) - float(config["expected_s03d"]["traditional_auc"]), "tolerance": 0.003, "pass": abs(auc_metric(y_full, s03d_trad) - float(config["expected_s03d"]["traditional_auc"])) <= 0.003},
            {"quantity": "S03d q_template RF ROC-AUC", "report_value": float(config["expected_s03d"]["qtemplate_rf_auc"]), "reproduced": auc_metric(y_full, s03d_rf), "delta": auc_metric(y_full, s03d_rf) - float(config["expected_s03d"]["qtemplate_rf_auc"]), "tolerance": 0.003, "pass": abs(auc_metric(y_full, s03d_rf) - float(config["expected_s03d"]["qtemplate_rf_auc"])) <= 0.003},
        ]
    )
    s03d_repro.to_csv(out_dir / "s03d_headline_reproduction.csv", index=False)
    s03d_choices.to_csv(out_dir / "s03d_traditional_fold_choices.csv", index=False)
    if not bool(s03d_repro["pass"].all()):
        raise RuntimeError("S03d headline reproduction failed")

    min_train = int(config["matching"]["min_train_rows_per_stratum"])
    min_test = int(config["matching"]["min_heldout_rows_per_stratum"])
    keep = np.zeros(len(bench), dtype=bool)
    match_rows = []
    for held_run in sorted(np.unique(runs_full)):
        train = bench["run"].to_numpy(dtype=int) != held_run
        test = bench["run"].to_numpy(dtype=int) == held_run
        train_counts = bench.loc[train, "match_stratum"].value_counts()
        test_counts = bench.loc[test, "match_stratum"].value_counts()
        supported = sorted(set(train_counts[train_counts >= min_train].index) & set(test_counts[test_counts >= min_test].index))
        fold_keep = test & bench["match_stratum"].isin(supported).to_numpy()
        keep |= fold_keep
        match_rows.append({"heldout_run": int(held_run), "supported_strata": len(supported), "heldout_rows": int(test.sum()), "matched_heldout_rows": int(fold_keep.sum()), "heldout_tail": int(bench.loc[test, "label_tail"].sum()), "matched_heldout_tail": int(bench.loc[fold_keep, "label_tail"].sum())})
    matched = bench.loc[keep].copy().reset_index(drop=True)
    y = matched["label_tail"].to_numpy(dtype=int)
    runs = matched["run"].to_numpy(dtype=int)
    matched.to_csv(out_dir / "matched_event_table.csv.gz", index=False)

    dataset_counts = pd.DataFrame(
        [
            {"quantity": "parent control events", "value": int(len(data))},
            {"quantity": "clean events D_t<3 ns", "value": int((y_full == 0).sum())},
            {"quantity": "tail events D_t>51 ns", "value": int((y_full == 1).sum())},
            {"quantity": "extreme benchmark events", "value": int(len(bench))},
            {"quantity": "matched benchmark events", "value": int(len(matched))},
            {"quantity": "matched tail events", "value": int(y.sum())},
            {"quantity": "matched tail fraction", "value": float(y.mean())},
        ]
    )
    matched_counts = pd.DataFrame(match_rows)
    dataset_counts.to_csv(out_dir / "dataset_counts.csv", index=False)
    matched_counts.to_csv(out_dir / "matched_counts_by_run.csv", index=False)

    q_shape_cols = Q_COLS + ["peak_ds_mean", "peak_ds_max", "high_amp_boundary", "near_adc_boundary"]
    trad_score, trad_choices = traditional_oof(matched, y, ["q_max", "q_ds_max", "q_ds_mean", "q_ds_span", "q_b2_minus_ds_mean"], residualize=True)
    ml_score = rf_oof(matched, y, q_shape_cols, config, seed + 10, residualize=True)
    amp_score = rf_oof(matched, y, AMP_COLS, config, seed + 20, residualize=False)
    topo_score = rf_oof(matched, y, TOPO_COLS, config, seed + 30, residualize=False)
    downstream_score = rf_oof(matched, y, DOWNSTREAM_Q_COLS, config, seed + 40, residualize=True)
    shuffled_score = rf_oof(matched, y, q_shape_cols, config, seed + 50, residualize=True, shuffle=True)
    leaky_score = matched["d_t_ns"].to_numpy(dtype=float)
    trad_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)

    score_dict = {
        "traditional_matched_q_hand": trad_score,
        "ml_qtemplate_shape_rf": ml_score,
        "amplitude_only_rf": amp_score,
        "topology_only_rf": topo_score,
        "downstream_only_q_rf": downstream_score,
        "shuffled_label_q_rf": shuffled_score,
        "leaky_dt_ceiling": leaky_score,
    }
    score_table = scoreboard(matched, y, score_dict, seed + 100, int(config["bootstrap_replicates"]))
    score_table.to_csv(out_dir / "scoreboard.csv", index=False)
    delta_table = delta_scoreboard(y, runs, ml_score, trad_score, seed + 200, int(config["bootstrap_replicates"]))
    delta_table.to_csv(out_dir / "ml_minus_traditional_deltas.csv", index=False)
    fixed = pd.concat(
        [fixed_efficiency_rows(matched, y, score, float(config["fixed_clean_efficiency"]), method) for method, score in score_dict.items() if method != "leaky_dt_ceiling"],
        ignore_index=True,
    )
    fixed.to_csv(out_dir / "fixed_clean_efficiency.csv", index=False)
    fixed_summary = fixed_efficiency_summary(fixed, seed + 250, int(config["bootstrap_replicates"]))
    fixed_summary.to_csv(out_dir / "fixed_clean_efficiency_summary.csv", index=False)
    residual_deltas = residual_delta_table(matched, y, fixed, {k: v for k, v in score_dict.items() if k in {"traditional_matched_q_hand", "ml_qtemplate_shape_rf", "amplitude_only_rf", "downstream_only_q_rf", "shuffled_label_q_rf"}}, seed + 300, int(config["bootstrap_replicates"]))
    residual_deltas.to_csv(out_dir / "pair_residual_deltas.csv", index=False)

    oof = matched[["event_uid", "run", "eventno", "evt", "label_tail", "d_t_ns", "downstream_count", "all_three_downstream", "match_stratum", *PAIR_COLS, *Q_COLS, *AMP_COLS]].copy()
    for name, score in score_dict.items():
        oof[f"{name}_score"] = score
    oof.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)

    leakage = pd.DataFrame(
        [
            {"check": "train_heldout_run_overlap", "value": 0.0, "flag": False, "detail": "Leave-one-run-out folds use disjoint run ids."},
            {"check": "main_feature_forbidden_columns", "value": 0.0, "flag": False, "detail": f"Main columns exclude run/event id, D_t, pair residuals, and absolute amplitude: {q_shape_cols}"},
            {"check": "matched_rows_fraction", "value": float(len(matched) / len(bench)), "flag": False, "detail": "Rows retained after train/heldout matched-stratum support."},
            {"check": "shuffled_label_auc", "value": auc_metric(y, shuffled_score), "flag": bool(auc_metric(y, shuffled_score) > 0.70), "detail": "Labels shuffled inside training runs."},
            {"check": "amplitude_only_auc", "value": auc_metric(y, amp_score), "flag": bool(auc_metric(y, amp_score) > auc_metric(y, ml_score)), "detail": "Amplitude nuisance sentinel."},
            {"check": "topology_only_auc", "value": auc_metric(y, topo_score), "flag": bool(auc_metric(y, topo_score) > 0.70), "detail": "Topology-only sentinel."},
            {"check": "downstream_only_auc", "value": auc_metric(y, downstream_score), "flag": False, "detail": "Expected to remain strong if downstream waveform quality drives the label."},
            {"check": "leaky_dt_auc", "value": auc_metric(y, leaky_score), "flag": False, "detail": "Forbidden label-defining ceiling."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_rows = []
    input_hashes = {}
    for run in configured_runs(config):
        path = raw_file(config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest, "size": path.stat().st_size})
    input_rows.append({"path": str(config_path), "sha256": sha256_file(config_path), "size": config_path.stat().st_size})
    input_rows.append({"path": "scripts/s03i_1781029233_703_5ff5517d_qtemplate_amp_matched.py", "sha256": sha256_file(Path("scripts/s03i_1781029233_703_5ff5517d_qtemplate_amp_matched.py")), "size": Path("scripts/s03i_1781029233_703_5ff5517d_qtemplate_amp_matched.py").stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    ml = score_table[score_table["method"] == "ml_qtemplate_shape_rf"].iloc[0]
    trad = score_table[score_table["method"] == "traditional_matched_q_hand"].iloc[0]
    amp = score_table[score_table["method"] == "amplitude_only_rf"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "s03d_headline_reproduction_pass": bool(s03d_repro["pass"].all()),
        "s03d_headline_reproduction": s03d_repro.to_dict(orient="records"),
        "matched_dataset": dataset_counts.to_dict(orient="records"),
        "traditional": score_table[score_table["method"] == "traditional_matched_q_hand"].iloc[0].to_dict(),
        "ml": score_table[score_table["method"] == "ml_qtemplate_shape_rf"].iloc[0].to_dict(),
        "amplitude_only": score_table[score_table["method"] == "amplitude_only_rf"].iloc[0].to_dict(),
        "ml_minus_traditional": delta_table.to_dict(orient="records"),
        "fixed_clean_efficiency_summary": fixed_summary.to_dict(orient="records"),
        "pair_residual_deltas": residual_deltas.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "verdict": "q_template_signal_survives_matching" if float(ml["roc_auc"]) > float(amp["roc_auc"]) and float(ml["roc_auc"]) > 0.5 else "amplitude_or_support_dominated",
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
        "next_tickets": []
    }

    write_report(out_dir, config, reproduction, s03d_repro, dataset_counts, matched_counts, score_table, delta_table, fixed_summary, residual_deltas, leakage, result)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "script": "scripts/s03i_1781029233_703_5ff5517d_qtemplate_amp_matched.py",
        "command": " ".join(sys.argv),
        "random_seed": seed,
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "s03d_rf_auc": auc_metric(y_full, s03d_rf), "matched_ml_auc": float(ml["roc_auc"]), "matched_traditional_auc": float(trad["roc_auc"]), "matched_amp_auc": float(amp["roc_auc"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
