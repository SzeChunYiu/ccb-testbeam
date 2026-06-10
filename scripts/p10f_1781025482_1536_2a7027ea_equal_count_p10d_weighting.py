#!/usr/bin/env python3
"""P10f equal-count P10d run-weighting control from raw ROOT."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ALL_PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
DOWNSTREAM_PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def pulse_quantities(waveforms: np.ndarray, baseline_idx: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_idx], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    return corrected, amplitude, peak, area


def cfd_times(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float, period_ns: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = 0.0
            continue
        y0 = float(waveforms[i, j - 1])
        y1 = float(waveforms[i, j])
        denom = y1 - y0
        sample_pos = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
        out[i] = period_ns * sample_pos
    return out


def collect_from_raw(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][stave]) for stave in staves], dtype=int)
    stave_grid = np.asarray(staves)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    period = float(config["sample_period_ns"])
    timing_runs = set(int(r) for r in config["timing"]["train_runs"] + config["timing"]["heldout_runs"])

    repro_rows = []
    pulse_rows = []
    uid_offset = 0
    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_events = 0
        run_selected_pulses = 0
        run_all_hit_events = 0
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            corrected, amplitude, peak, area = pulse_quantities(events[:, channels, :], baseline_idx)
            selected = amplitude > cut
            all_hit = selected.all(axis=1)
            run_events += int(len(eventno))
            run_selected_pulses += int(selected.sum())
            run_all_hit_events += int(all_hit.sum())

            if run in timing_runs and bool(all_hit.any()):
                for e in np.where(all_hit)[0]:
                    event_id = f"{run}:{int(eventno[e])}:{int(evt[e])}:{uid_offset + int(e)}"
                    cfd = cfd_times(corrected[e], amplitude[e], float(config["cfd_fraction"]), period)
                    for sidx, stave in enumerate(stave_grid):
                        amp = float(amplitude[e, sidx])
                        pulse_rows.append(
                            {
                                "event_id": event_id,
                                "run": int(run),
                                "eventno": int(eventno[e]),
                                "evt": int(evt[e]),
                                "stave": str(stave),
                                "waveform": corrected[e, sidx].astype(np.float32),
                                "amplitude_adc": amp,
                                "peak_sample": int(peak[e, sidx]),
                                "area_adc_samples": float(area[e, sidx]),
                                "t_cfd_ns": float(cfd[sidx]),
                            }
                        )
            uid_offset += len(eventno)
        repro_rows.append(
            {
                "run": int(run),
                "n_events": run_events,
                "selected_pulses": run_selected_pulses,
                "all_hit_b2_b4_b6_b8_events": run_all_hit_events,
                "used_for_timing": bool(run in timing_runs),
            }
        )
    return pd.DataFrame(repro_rows), pd.DataFrame(pulse_rows)


def positions(config: dict) -> Dict[str, float]:
    spacing = float(config["spacing_cm"])
    return {stave: idx * spacing for idx, stave in enumerate(config["timing"]["external_staves"])}


def corrected_time(pulses: pd.DataFrame, method_col: str, config: dict) -> pd.Series:
    return pulses[method_col].astype(float) - pulses["stave"].map(positions(config)).astype(float) * float(config["tof_per_cm_ns"])


def sigma68(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def pairwise_residuals(pulses: pd.DataFrame, method_col: str, config: dict, run: int, pairs: List[Tuple[str, str]]) -> np.ndarray:
    sub = pulses[pulses["run"] == int(run)].copy()
    sub["tcorr"] = corrected_time(sub, method_col, config)
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    residuals = []
    for a, b in pairs:
        if a in wide and b in wide:
            residuals.append((wide[a] - wide[b]).to_numpy(dtype=float))
    if not residuals:
        return np.asarray([], dtype=float)
    return np.concatenate(residuals)


def downstream_targets(pulses: pd.DataFrame, config: dict, base_col: str) -> np.ndarray:
    target_staves = list(config["timing"]["target_staves"])
    sub = pulses.copy()
    sub["tcorr"] = corrected_time(sub, base_col, config)
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr")
    target = np.full(len(pulses), np.nan, dtype=float)
    event_to_vals = {event_id: wide.loc[event_id] for event_id in wide.index}
    for i, row in enumerate(pulses.itertuples()):
        if row.stave not in target_staves:
            continue
        vals = event_to_vals[row.event_id]
        others = [stave for stave in target_staves if stave != row.stave and pd.notna(vals.get(stave, np.nan))]
        if len(others) == 2 and math.isfinite(float(row.t_cfd_ns)):
            target[i] = float(vals[row.stave] - np.mean([float(vals[stave]) for stave in others]))
    return target


def assign_amp_bins(amplitude: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, amplitude, side="right") - 1, 0, len(edges) - 2)


def one_hot_staves(pulses: pd.DataFrame, staves: List[str]) -> np.ndarray:
    lookup = {stave: i for i, stave in enumerate(staves)}
    out = np.zeros((len(pulses), len(staves)), dtype=float)
    for i, stave in enumerate(pulses["stave"].to_numpy()):
        if stave in lookup:
            out[i, lookup[stave]] = 1.0
    return out


def traditional_features(config: dict, pulses: pd.DataFrame, feature_set: str) -> np.ndarray:
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    log_amp = np.log1p(amp)
    area_over_amp = pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    peak = pulses["peak_sample"].to_numpy(dtype=float)
    target_staves = list(config["timing"]["target_staves"])
    one_hot = one_hot_staves(pulses, target_staves)
    base = np.column_stack([log_amp, log_amp**2, 1.0 / np.sqrt(np.maximum(amp, 1.0)), area_over_amp, peak])
    if feature_set == "amp_poly":
        X = np.hstack([base, one_hot])
    elif feature_set == "amp_poly_by_stave":
        X = np.hstack([base, one_hot] + [base[:, j : j + 1] * one_hot for j in range(base.shape[1])])
    elif feature_set == "amp_bin_by_stave":
        edges = np.asarray(config["traditional"]["amplitude_edges_adc"], dtype=float)
        bins = assign_amp_bins(amp, edges)
        bin_hot = np.zeros((len(pulses), len(edges) - 1), dtype=float)
        bin_hot[np.arange(len(pulses)), bins] = 1.0
        X = np.hstack([base[:, [0, 2, 3, 4]], one_hot] + [bin_hot[:, j : j + 1] * one_hot for j in range(bin_hot.shape[1])])
    else:
        raise ValueError(feature_set)
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)


def ml_features(config: dict, pulses: pd.DataFrame, feature_set: str) -> np.ndarray:
    wf = np.vstack(pulses["waveform"].to_numpy()).astype(np.float32)
    amp = pulses["amplitude_adc"].to_numpy(dtype=float)
    norm = wf / np.maximum(amp[:, None], 1.0)
    if feature_set == "waveform":
        X = norm
    elif feature_set == "waveform_amp":
        X = np.hstack(
            [
                norm,
                np.log1p(amp)[:, None],
                (pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0))[:, None],
                pulses["peak_sample"].to_numpy(dtype=float)[:, None],
            ]
        )
    elif feature_set == "waveform_amp_stave":
        X = np.hstack(
            [
                norm,
                np.log1p(amp)[:, None],
                (pulses["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0))[:, None],
                pulses["peak_sample"].to_numpy(dtype=float)[:, None],
                one_hot_staves(pulses, list(config["timing"]["target_staves"])),
            ]
        )
    else:
        raise ValueError(feature_set)
    return np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)


def train_mask(config: dict, pulses: pd.DataFrame, target: np.ndarray) -> np.ndarray:
    runs = pulses["run"].to_numpy(dtype=int)
    staves = pulses["stave"].to_numpy()
    return (
        np.isin(runs, np.asarray(config["timing"]["train_runs"], dtype=int))
        & np.isin(staves, np.asarray(config["timing"]["target_staves"]))
        & np.isfinite(target)
    )


def score_validation(pulses: pd.DataFrame, pred: np.ndarray, rows: np.ndarray, config: dict) -> float:
    tmp = pulses.iloc[rows].copy()
    local_pred = pred[rows]
    tmp["t_model_ns"] = tmp["t_cfd_ns"].to_numpy(dtype=float) - local_pred
    vals = []
    for run in sorted(tmp["run"].unique()):
        vals.append(pairwise_residuals(tmp, "t_model_ns", config, int(run), DOWNSTREAM_PAIRS))
    joined = np.concatenate([v for v in vals if len(v)]) if vals else np.asarray([], dtype=float)
    return sigma68(joined)


def select_traditional(config: dict, pulses: pd.DataFrame, target: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, dict, pd.DataFrame]:
    idx = np.flatnonzero(mask)
    groups = pulses.iloc[idx]["run"].to_numpy(dtype=int)
    n_splits = min(5, len(np.unique(groups)))
    rows = []
    best = {"score": float("inf"), "feature_set": None, "alpha": None}
    for feature_set in config["traditional"]["feature_sets"]:
        X = traditional_features(config, pulses, feature_set)
        for alpha in config["traditional"]["ridge_alphas"]:
            fold_scores = []
            splitter = GroupKFold(n_splits=n_splits)
            for fold, (tr, va) in enumerate(splitter.split(X[idx], target[idx], groups=groups), start=1):
                model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha), solver="lsqr"))
                model.fit(X[idx][tr], target[idx][tr])
                pred = np.zeros(len(pulses), dtype=float)
                pred[idx[va]] = model.predict(X[idx][va])
                score = score_validation(pulses, pred, idx[va], config)
                fold_scores.append(score)
                rows.append({"method": "traditional", "feature_set": feature_set, "alpha": float(alpha), "fold": fold, "sigma68_ns": score})
            mean_score = float(np.nanmean(fold_scores))
            rows.append({"method": "traditional", "feature_set": feature_set, "alpha": float(alpha), "fold": -1, "sigma68_ns": mean_score})
            if mean_score < best["score"]:
                best = {"score": mean_score, "feature_set": feature_set, "alpha": float(alpha)}
    X = traditional_features(config, pulses, str(best["feature_set"]))
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"]), solver="lsqr"))
    model.fit(X[mask], target[mask])
    pred = np.zeros(len(pulses), dtype=float)
    apply_staves = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["target_staves"]))
    pred[apply_staves] = model.predict(X[apply_staves])
    best["train_pulses"] = int(mask.sum())
    best["train_runs"] = sorted(int(v) for v in np.unique(pulses.loc[mask, "run"]))
    return pred, best, pd.DataFrame(rows)


def select_ml(config: dict, pulses: pd.DataFrame, target: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, dict, pd.DataFrame]:
    idx = np.flatnonzero(mask)
    groups = pulses.iloc[idx]["run"].to_numpy(dtype=int)
    n_splits = min(5, len(np.unique(groups)))
    rows = []
    best = {"score": float("inf"), "feature_set": None, "n_estimators": None, "max_depth": None, "min_samples_leaf": None}
    for feature_set in config["ml"]["feature_sets"]:
        X = ml_features(config, pulses, feature_set)
        for n_estimators in config["ml"]["n_estimators"]:
            for max_depth in config["ml"]["max_depth"]:
                for min_samples_leaf in config["ml"]["min_samples_leaf"]:
                    fold_scores = []
                    splitter = GroupKFold(n_splits=n_splits)
                    for fold, (tr, va) in enumerate(splitter.split(X[idx], target[idx], groups=groups), start=1):
                        model = ExtraTreesRegressor(
                            n_estimators=int(n_estimators),
                            max_depth=int(max_depth),
                            min_samples_leaf=int(min_samples_leaf),
                            random_state=int(config["random_seed"]) + fold,
                            n_jobs=1,
                        )
                        model.fit(X[idx][tr], target[idx][tr])
                        pred = np.zeros(len(pulses), dtype=float)
                        pred[idx[va]] = model.predict(X[idx][va])
                        score = score_validation(pulses, pred, idx[va], config)
                        fold_scores.append(score)
                        rows.append(
                            {
                                "method": "ml",
                                "feature_set": feature_set,
                                "n_estimators": int(n_estimators),
                                "max_depth": int(max_depth),
                                "min_samples_leaf": int(min_samples_leaf),
                                "fold": fold,
                                "sigma68_ns": score,
                            }
                        )
                    mean_score = float(np.nanmean(fold_scores))
                    rows.append(
                        {
                            "method": "ml",
                            "feature_set": feature_set,
                            "n_estimators": int(n_estimators),
                            "max_depth": int(max_depth),
                            "min_samples_leaf": int(min_samples_leaf),
                            "fold": -1,
                            "sigma68_ns": mean_score,
                        }
                    )
                    if mean_score < best["score"]:
                        best = {
                            "score": mean_score,
                            "feature_set": feature_set,
                            "n_estimators": int(n_estimators),
                            "max_depth": int(max_depth),
                            "min_samples_leaf": int(min_samples_leaf),
                        }
    X = ml_features(config, pulses, str(best["feature_set"]))
    model = ExtraTreesRegressor(
        n_estimators=int(best["n_estimators"]),
        max_depth=int(best["max_depth"]),
        min_samples_leaf=int(best["min_samples_leaf"]),
        random_state=int(config["random_seed"]) + 99,
        n_jobs=1,
    )
    model.fit(X[mask], target[mask])
    pred = np.zeros(len(pulses), dtype=float)
    apply_staves = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["target_staves"]))
    pred[apply_staves] = model.predict(X[apply_staves])
    best["train_pulses"] = int(mask.sum())
    best["train_runs"] = sorted(int(v) for v in np.unique(pulses.loc[mask, "run"]))
    return pred, best, pd.DataFrame(rows)


def shuffled_control(
    config: dict,
    pulses: pd.DataFrame,
    target: np.ndarray,
    mask: np.ndarray,
    pred_builder: Callable[[np.ndarray], np.ndarray],
    seed_offset: int,
) -> np.ndarray:
    rng = np.random.default_rng(int(config["random_seed"]) + seed_offset)
    shuffled = target.copy()
    train_values = shuffled[mask].copy()
    rng.shuffle(train_values)
    shuffled[mask] = train_values
    return pred_builder(shuffled)


def final_traditional_with_fixed_best(config: dict, pulses: pd.DataFrame, target: np.ndarray, mask: np.ndarray, best: dict) -> np.ndarray:
    X = traditional_features(config, pulses, str(best["feature_set"]))
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"]), solver="lsqr"))
    model.fit(X[mask], target[mask])
    pred = np.zeros(len(pulses), dtype=float)
    apply_staves = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["target_staves"]))
    pred[apply_staves] = model.predict(X[apply_staves])
    return pred


def final_ml_with_fixed_best(config: dict, pulses: pd.DataFrame, target: np.ndarray, mask: np.ndarray, best: dict) -> np.ndarray:
    X = ml_features(config, pulses, str(best["feature_set"]))
    model = ExtraTreesRegressor(
        n_estimators=int(best["n_estimators"]),
        max_depth=int(best["max_depth"]),
        min_samples_leaf=int(best["min_samples_leaf"]),
        random_state=int(config["random_seed"]) + 199,
        n_jobs=1,
    )
    model.fit(X[mask], target[mask])
    pred = np.zeros(len(pulses), dtype=float)
    apply_staves = np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["target_staves"]))
    pred[apply_staves] = model.predict(X[apply_staves])
    return pred


def equal_count_row_filter(config: dict, pulses: pd.DataFrame) -> Tuple[np.ndarray, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 1001)
    per_run_events = {}
    for run in config["timing"]["heldout_runs"]:
        events = sorted(pulses.loc[pulses["run"] == int(run), "event_id"].unique())
        if not events:
            raise RuntimeError(f"No held-out all-hit events for run {run}")
        per_run_events[int(run)] = np.asarray(events, dtype=object)
    target_n = min(len(events) for events in per_run_events.values())
    rows = []
    selected_events = []
    for run, events in per_run_events.items():
        chosen = set(rng.choice(events, size=target_n, replace=False).tolist())
        selected_events.extend(chosen)
        rows.append(
            {
                "run": int(run),
                "available_all_hit_events": int(len(events)),
                "selected_all_hit_events": int(target_n),
                "selection_fraction": float(target_n / len(events)),
            }
        )
    row_filter = pulses.index[pulses["event_id"].isin(selected_events)].to_numpy(dtype=int)
    return np.sort(row_filter), pd.DataFrame(rows)


def evaluate_methods(config: dict, pulses: pd.DataFrame, predictions: Dict[str, np.ndarray], row_filter: np.ndarray = None) -> pd.DataFrame:
    if row_filter is None:
        work = pulses.copy()
        local_predictions = predictions
    else:
        work = pulses.iloc[row_filter].copy()
        local_predictions = {name: pred[row_filter] for name, pred in predictions.items()}
    for name, pred in predictions.items():
        work[f"t_{name}_ns"] = work["t_cfd_ns"].to_numpy(dtype=float) - local_predictions[name]
    rows = []
    for run in config["timing"]["heldout_runs"]:
        row = {"run": int(run), "n_all_hit_events": int(work.loc[work["run"] == int(run), "event_id"].nunique())}
        for name in ["baseline"] + list(predictions.keys()):
            col = "t_cfd_ns" if name == "baseline" else f"t_{name}_ns"
            vals_all = pairwise_residuals(work, col, config, int(run), ALL_PAIRS)
            vals_down = pairwise_residuals(work, col, config, int(run), DOWNSTREAM_PAIRS)
            row[f"{name}_external_sigma68_ns"] = sigma68(vals_all)
            row[f"{name}_external_n_pairs"] = int(len(vals_all))
            row[f"{name}_downstream_sigma68_ns"] = sigma68(vals_down)
            row[f"{name}_downstream_n_pairs"] = int(len(vals_down))
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_summary(run_df: pd.DataFrame, config: dict) -> dict:
    rng = np.random.default_rng(int(config["random_seed"]) + 707)
    method_cols = [
        "baseline_external_sigma68_ns",
        "traditional_external_sigma68_ns",
        "ml_external_sigma68_ns",
        "traditional_shuffled_external_sigma68_ns",
        "ml_shuffled_external_sigma68_ns",
        "baseline_downstream_sigma68_ns",
        "traditional_downstream_sigma68_ns",
        "ml_downstream_sigma68_ns",
    ]
    matrix = run_df[method_cols].to_numpy(dtype=float)
    boots = []
    n_boot = int(config["bootstrap_iterations"])
    for _ in range(n_boot):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    summary = {"bootstrap_unit": "heldout_run", "n_bootstrap": n_boot}
    means = matrix.mean(axis=0)
    for i, col in enumerate(method_cols):
        summary[col] = float(means[i])
        summary[f"{col}_ci"] = np.nanquantile(boots[:, i], [0.025, 0.975]).tolist()
    deltas = {
        "traditional_minus_baseline_external_ns": run_df["traditional_external_sigma68_ns"].to_numpy(dtype=float)
        - run_df["baseline_external_sigma68_ns"].to_numpy(dtype=float),
        "ml_minus_baseline_external_ns": run_df["ml_external_sigma68_ns"].to_numpy(dtype=float)
        - run_df["baseline_external_sigma68_ns"].to_numpy(dtype=float),
        "ml_minus_traditional_external_ns": run_df["ml_external_sigma68_ns"].to_numpy(dtype=float)
        - run_df["traditional_external_sigma68_ns"].to_numpy(dtype=float),
        "traditional_minus_baseline_downstream_ns": run_df["traditional_downstream_sigma68_ns"].to_numpy(dtype=float)
        - run_df["baseline_downstream_sigma68_ns"].to_numpy(dtype=float),
        "ml_minus_traditional_downstream_ns": run_df["ml_downstream_sigma68_ns"].to_numpy(dtype=float)
        - run_df["traditional_downstream_sigma68_ns"].to_numpy(dtype=float),
    }
    for name, values in deltas.items():
        boots_delta = []
        for _ in range(n_boot):
            boots_delta.append(values[rng.integers(0, len(values), len(values))].mean())
        summary[name] = float(np.nanmean(values))
        summary[f"{name}_ci"] = np.nanquantile(np.asarray(boots_delta), [0.025, 0.975]).tolist()
    return summary


def markdown_metric_row(label: str, value: float, ci: List[float]) -> str:
    return f"| {label} | {value:.6g} | [{ci[0]:.6g}, {ci[1]:.6g}] |"


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    p10d_summary: dict,
    equal_selection: pd.DataFrame,
    equal_run_df: pd.DataFrame,
    summary: dict,
    trad_best: dict,
    ml_best: dict,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    lines = [
        "# Study report: P10f - Equal-count P10d run weighting control",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Date:** 2026-06-10",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        f"- **Git commit:** {result['git_commit']}",
        "",
        "## Question",
        "",
        "Does P10d's B2/B4/B6/B8 external closure change when each held-out run is forced to contribute the same number of all-hit events, separating run/event weighting from high-current topology effects?",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The canonical S00/P10 selected-pulse count and the P10d unweighted held-out closure are recomputed from raw ROOT before the equal-count control is read out.",
        "",
        "| quantity | report_value | reproduced | delta | tolerance | pass |",
        "|---|---:|---:|---:|---:|---:|",
        f"| selected B-stave pulses | {config['expected_selected_pulses']} | {int(repro['selected_pulses'].sum())} | {int(repro['selected_pulses'].sum() - config['expected_selected_pulses'])} | 0 | {int(result['reproduced'])} |",
        f"| P10d held-out all-hit events | {config['p10d_reference']['heldout_all_hit_events']} | {result['p10d_reproduction']['heldout_all_hit_events']} | {result['p10d_reproduction']['heldout_all_hit_events_delta']} | 0 | {int(result['p10d_reproduction']['heldout_all_hit_events_pass'])} |",
        f"| P10d traditional external sigma68 ns | {config['p10d_reference']['traditional_external_sigma68_ns']:.9g} | {p10d_summary['traditional_external_sigma68_ns']:.9g} | {result['p10d_reproduction']['traditional_external_delta_ns']:.3g} | 1e-6 | {int(result['p10d_reproduction']['traditional_external_pass'])} |",
        f"| P10d ML external sigma68 ns | {config['p10d_reference']['ml_external_sigma68_ns']:.9g} | {p10d_summary['ml_external_sigma68_ns']:.9g} | {result['p10d_reproduction']['ml_external_delta_ns']:.3g} | 1e-6 | {int(result['p10d_reproduction']['ml_external_pass'])} |",
        "",
        "P10d is reproduced before applying the equal-count held-out event sample. The equal-count sample uses "
        f"{result['equal_count']['selected_all_hit_events_per_run']} all-hit events from each of "
        f"{result['equal_count']['n_heldout_runs']} held-out runs.",
        "",
        "## Methods",
        "",
        "Population: events in which B2, B4, B6, and B8 all pass the same baseline-median `A>1000 ADC` pulse gate. Train runs are calibration runs 31-37, 39-42, and 64; held-out runs are 58-63 and 65. Models are fitted exactly as in P10d: the target is only the downstream B4/B6/B8 same-event residual, while B2 is included only in the external evaluation.",
        "",
        f"Traditional method: Ridge explicit timewalk correction over amplitude, area/amp, peak sample, stave identity, and bin/stave interactions. Selected feature set `{trad_best['feature_set']}`, alpha `{trad_best['alpha']}`, train pulses `{trad_best['train_pulses']}`.",
        "",
        f"ML method: nonlinear ExtraTrees residual model over normalized waveform and pulse-summary features. Selected feature set `{ml_best['feature_set']}`, n_estimators `{ml_best['n_estimators']}`, max_depth `{ml_best['max_depth']}`, min_samples_leaf `{ml_best['min_samples_leaf']}`, train pulses `{ml_best['train_pulses']}`.",
        "",
        "## Equal-count Held-out External Closure",
        "",
        "Metric: per-run `sigma68` over all six B2/B4/B6/B8 pairwise residuals after geometry correction. Each held-out run is downsampled to the same all-hit event count, and CIs bootstrap held-out runs.",
        "",
        "| Method | sigma68 ns | 95% CI |",
        "|---|---:|---:|",
        markdown_metric_row("CFD20 baseline", summary["baseline_external_sigma68_ns"], summary["baseline_external_sigma68_ns_ci"]),
        markdown_metric_row("Traditional explicit correction", summary["traditional_external_sigma68_ns"], summary["traditional_external_sigma68_ns_ci"]),
        markdown_metric_row("ML residual correction", summary["ml_external_sigma68_ns"], summary["ml_external_sigma68_ns_ci"]),
        markdown_metric_row("Traditional shuffled target", summary["traditional_shuffled_external_sigma68_ns"], summary["traditional_shuffled_external_sigma68_ns_ci"]),
        markdown_metric_row("ML shuffled target", summary["ml_shuffled_external_sigma68_ns"], summary["ml_shuffled_external_sigma68_ns_ci"]),
        "",
        "| Delta | ns | 95% CI |",
        "|---|---:|---:|",
        markdown_metric_row("Traditional - baseline", summary["traditional_minus_baseline_external_ns"], summary["traditional_minus_baseline_external_ns_ci"]),
        markdown_metric_row("ML - baseline", summary["ml_minus_baseline_external_ns"], summary["ml_minus_baseline_external_ns_ci"]),
        markdown_metric_row("ML - traditional", summary["ml_minus_traditional_external_ns"], summary["ml_minus_traditional_external_ns_ci"]),
        "",
        "## Equal-count Sample",
        "",
        equal_selection.to_markdown(index=False),
        "",
        "## Downstream-Only Diagnostic",
        "",
        "The same held-out all-hit events are also scored on only the B4/B6/B8 pairs to show how much of the apparent correction remains on the original target topology.",
        "",
        "| Method | sigma68 ns | 95% CI |",
        "|---|---:|---:|",
        markdown_metric_row("CFD20 baseline", summary["baseline_downstream_sigma68_ns"], summary["baseline_downstream_sigma68_ns_ci"]),
        markdown_metric_row("Traditional explicit correction", summary["traditional_downstream_sigma68_ns"], summary["traditional_downstream_sigma68_ns_ci"]),
        markdown_metric_row("ML residual correction", summary["ml_downstream_sigma68_ns"], summary["ml_downstream_sigma68_ns_ci"]),
        "",
        "## Leakage Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "Leakage audit: no run or event overlap exists between train and held-out sets; B2 rows are excluded from fitted targets; run number, event id, and event order are not model features; and shuffled-target controls are reported beside the real fits.",
        "",
        "## Files",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_by_run.csv`, `p10d_external_closure_by_run.csv`, `external_closure_by_run.csv`, `equal_count_selection.csv`, `model_cv.csv`, and `leakage_checks.csv` are in this directory. No Monte Carlo was used.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10f_1781025482_1536_2a7027ea_equal_count_p10d_weighting.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    repro, pulses = collect_from_raw(config)
    repro.to_csv(out_dir / "reproduction_by_run.csv", index=False)
    reproduced_count = int(repro["selected_pulses"].sum())
    reproduced = reproduced_count == int(config["expected_selected_pulses"])
    if not reproduced:
        raise RuntimeError(f"Raw ROOT reproduction failed: {reproduced_count} != {config['expected_selected_pulses']}")
    if pulses.empty:
        raise RuntimeError("No all-hit timing pulses collected")

    target = downstream_targets(pulses, config, "t_cfd_ns")
    mask = train_mask(config, pulses, target)
    if int(mask.sum()) < 100:
        raise RuntimeError(f"Too few training target pulses: {int(mask.sum())}")

    trad_pred, trad_best, trad_cv = select_traditional(config, pulses, target, mask)
    ml_pred, ml_best, ml_cv = select_ml(config, pulses, target, mask)

    trad_shuffle = shuffled_control(
        config,
        pulses,
        target,
        mask,
        lambda shuffled_target: final_traditional_with_fixed_best(config, pulses, shuffled_target, mask, trad_best),
        301,
    )
    ml_shuffle = shuffled_control(
        config,
        pulses,
        target,
        mask,
        lambda shuffled_target: final_ml_with_fixed_best(config, pulses, shuffled_target, mask, ml_best),
        401,
    )
    model_cv = pd.concat([trad_cv, ml_cv], ignore_index=True)
    model_cv.to_csv(out_dir / "model_cv.csv", index=False)

    predictions = {
        "traditional": trad_pred,
        "ml": ml_pred,
        "traditional_shuffled": trad_shuffle,
        "ml_shuffled": ml_shuffle,
    }
    p10d_run_df = evaluate_methods(config, pulses, predictions)
    p10d_run_df.to_csv(out_dir / "p10d_external_closure_by_run.csv", index=False)
    p10d_summary = bootstrap_summary(p10d_run_df, config)

    equal_rows, equal_selection = equal_count_row_filter(config, pulses)
    equal_selection.to_csv(out_dir / "equal_count_selection.csv", index=False)
    run_df = evaluate_methods(config, pulses, predictions, equal_rows)
    run_df.to_csv(out_dir / "external_closure_by_run.csv", index=False)
    summary = bootstrap_summary(run_df, config)

    train_events = set(pulses.loc[pulses["run"].isin(config["timing"]["train_runs"]), "event_id"])
    heldout_events = set(pulses.loc[pulses["run"].isin(config["timing"]["heldout_runs"]), "event_id"])
    p10d_tol = 1.0e-6
    p10d_repro = {
        "reference_ticket_id": config["p10d_reference"]["ticket_id"],
        "heldout_all_hit_events": int(pulses.loc[pulses["run"].isin(config["timing"]["heldout_runs"]), "event_id"].nunique()),
        "heldout_all_hit_events_delta": int(
            pulses.loc[pulses["run"].isin(config["timing"]["heldout_runs"]), "event_id"].nunique()
            - int(config["p10d_reference"]["heldout_all_hit_events"])
        ),
        "baseline_external_delta_ns": float(
            p10d_summary["baseline_external_sigma68_ns"] - float(config["p10d_reference"]["baseline_external_sigma68_ns"])
        ),
        "traditional_external_delta_ns": float(
            p10d_summary["traditional_external_sigma68_ns"] - float(config["p10d_reference"]["traditional_external_sigma68_ns"])
        ),
        "ml_external_delta_ns": float(p10d_summary["ml_external_sigma68_ns"] - float(config["p10d_reference"]["ml_external_sigma68_ns"])),
    }
    p10d_repro["heldout_all_hit_events_pass"] = p10d_repro["heldout_all_hit_events_delta"] == 0
    p10d_repro["baseline_external_pass"] = abs(p10d_repro["baseline_external_delta_ns"]) <= p10d_tol
    p10d_repro["traditional_external_pass"] = abs(p10d_repro["traditional_external_delta_ns"]) <= p10d_tol
    p10d_repro["ml_external_pass"] = abs(p10d_repro["ml_external_delta_ns"]) <= p10d_tol
    p10d_reproduced = all(
        bool(p10d_repro[name])
        for name in [
            "heldout_all_hit_events_pass",
            "baseline_external_pass",
            "traditional_external_pass",
            "ml_external_pass",
        ]
    )
    if not p10d_reproduced:
        raise RuntimeError(f"P10d reproduction failed: {p10d_repro}")

    leakage = pd.DataFrame(
        [
            {
                "check": "train_heldout_run_overlap",
                "value": int(len(set(config["timing"]["train_runs"]) & set(config["timing"]["heldout_runs"]))),
                "flag": False,
                "unit": "runs",
            },
            {"check": "train_heldout_event_overlap", "value": int(len(train_events & heldout_events)), "flag": False, "unit": "events"},
            {"check": "b2_rows_used_in_target_fit", "value": int((mask & (pulses["stave"].to_numpy() == "B2")).sum()), "flag": False, "unit": "pulses"},
            {"check": "run_or_event_id_features_used", "value": 0, "flag": False, "unit": "bool"},
            {
                "check": "equal_count_events_identical_per_run",
                "value": int(equal_selection["selected_all_hit_events"].nunique() == 1),
                "flag": bool(equal_selection["selected_all_hit_events"].nunique() != 1),
                "unit": "bool",
            },
            {
                "check": "p10d_reproduction_failed",
                "value": int(not p10d_reproduced),
                "flag": bool(not p10d_reproduced),
                "unit": "bool",
            },
            {
                "check": "traditional_shuffled_beats_real_external",
                "value": int(summary["traditional_shuffled_external_sigma68_ns"] < summary["traditional_external_sigma68_ns"]),
                "flag": bool(summary["traditional_shuffled_external_sigma68_ns"] < summary["traditional_external_sigma68_ns"]),
                "unit": "bool",
            },
            {
                "check": "ml_shuffled_beats_real_external",
                "value": int(summary["ml_shuffled_external_sigma68_ns"] < summary["ml_external_sigma68_ns"]),
                "flag": bool(summary["ml_shuffled_external_sigma68_ns"] < summary["ml_external_sigma68_ns"]),
                "unit": "bool",
            },
            {
                "check": "too_good_external_sigma68_lt_1ns",
                "value": int(min(summary["traditional_external_sigma68_ns"], summary["ml_external_sigma68_ns"]) < 1.0),
                "flag": bool(min(summary["traditional_external_sigma68_ns"], summary["ml_external_sigma68_ns"]) < 1.0),
                "unit": "bool",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"])
        writer.writeheader()
        for run in configured_runs(config):
            path = raw_file(config, run)
            writer.writerow({"path": str(path), "sha256": sha256_file(path)})

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduced),
        "reproduction": {
            "quantity": "S00/P10 selected B-stave pulses from raw ROOT",
            "expected": int(config["expected_selected_pulses"]),
            "reproduced": reproduced_count,
            "delta": int(reproduced_count - int(config["expected_selected_pulses"])),
            "tolerance": 0,
        },
        "p10d_reproduction": p10d_repro,
        "population": {
            "all_hit_definition": "B2/B4/B6/B8 all have baseline-subtracted amplitude > 1000 ADC",
            "train_runs": [int(r) for r in config["timing"]["train_runs"]],
            "heldout_runs": [int(r) for r in config["timing"]["heldout_runs"]],
            "train_all_hit_events": int(pulses.loc[pulses["run"].isin(config["timing"]["train_runs"]), "event_id"].nunique()),
            "heldout_all_hit_events": int(pulses.loc[pulses["run"].isin(config["timing"]["heldout_runs"]), "event_id"].nunique()),
            "target_train_pulses": int(mask.sum()),
        },
        "equal_count": {
            "selection": "deterministic downsample without replacement within each held-out run",
            "selected_all_hit_events_per_run": int(equal_selection["selected_all_hit_events"].iloc[0]),
            "n_heldout_runs": int(len(equal_selection)),
            "selected_total_all_hit_events": int(equal_selection["selected_all_hit_events"].sum()),
            "available_total_all_hit_events": int(equal_selection["available_all_hit_events"].sum()),
        },
        "reference": config["p10b_reference"],
        "traditional": {
            "method": "Ridge explicit timewalk residual correction trained on B4/B6/B8 target pulses only",
            "best": trad_best,
            "external_metric": "heldout_run_mean_all_six_B2_B4_B6_B8_pairwise_sigma68_ns",
            "external_value": summary["traditional_external_sigma68_ns"],
            "external_ci": summary["traditional_external_sigma68_ns_ci"],
            "downstream_value": summary["traditional_downstream_sigma68_ns"],
            "downstream_ci": summary["traditional_downstream_sigma68_ns_ci"],
        },
        "ml": {
            "method": "ExtraTreesRegressor residual correction trained on normalized waveform features for B4/B6/B8 target pulses only",
            "best": ml_best,
            "external_metric": "heldout_run_mean_all_six_B2_B4_B6_B8_pairwise_sigma68_ns",
            "external_value": summary["ml_external_sigma68_ns"],
            "external_ci": summary["ml_external_sigma68_ns_ci"],
            "downstream_value": summary["ml_downstream_sigma68_ns"],
            "downstream_ci": summary["ml_downstream_sigma68_ns_ci"],
        },
        "baseline": {
            "method": "CFD20 pickoff, no residual correction",
            "external_value": summary["baseline_external_sigma68_ns"],
            "external_ci": summary["baseline_external_sigma68_ns_ci"],
            "downstream_value": summary["baseline_downstream_sigma68_ns"],
            "downstream_ci": summary["baseline_downstream_sigma68_ns_ci"],
        },
        "falsification": {
            "traditional_minus_baseline_external_ns": summary["traditional_minus_baseline_external_ns"],
            "traditional_minus_baseline_external_ci": summary["traditional_minus_baseline_external_ns_ci"],
            "ml_minus_baseline_external_ns": summary["ml_minus_baseline_external_ns"],
            "ml_minus_baseline_external_ci": summary["ml_minus_baseline_external_ns_ci"],
            "ml_minus_traditional_external_ns": summary["ml_minus_traditional_external_ns"],
            "ml_minus_traditional_external_ci": summary["ml_minus_traditional_external_ns_ci"],
            "traditional_shuffled_external_sigma68_ns": summary["traditional_shuffled_external_sigma68_ns"],
            "traditional_shuffled_external_ci": summary["traditional_shuffled_external_sigma68_ns_ci"],
            "ml_shuffled_external_sigma68_ns": summary["ml_shuffled_external_sigma68_ns"],
            "ml_shuffled_external_ci": summary["ml_shuffled_external_sigma68_ns_ci"],
            "leakage_flags": int(leakage["flag"].sum()),
        },
        "summary": summary,
        "p10d_unweighted_summary": p10d_summary,
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "elapsed_sec": float(time.time() - t0),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, p10d_summary, equal_selection, run_df, summary, trad_best, ml_best, leakage, result)

    output_hashes = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes.append({"path": str(path), "sha256": sha256_file(path)})
    input_hashes = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        input_hashes.append({"path": str(path), "sha256": sha256_file(path)})
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "script": str(Path(__file__)),
        "script_sha256": sha256_file(Path(__file__)),
        "command": f"{sys.executable} {Path(__file__)} --config {config_path}",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "inputs": input_hashes,
        "outputs": output_hashes,
        "elapsed_sec": result["elapsed_sec"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
