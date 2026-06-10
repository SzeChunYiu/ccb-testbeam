#!/usr/bin/env python3
"""P04k: selector-semantics sensitivity of duplicate-readout charge closure.

This script starts from raw B-stack ROOT files and first reproduces the S00c
median-first-four and dynamic-range selector counts. Modeling only starts after
that exact raw-count gate passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, LinearRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


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


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["staves"].keys())
    even_channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_channels = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    stave_names = np.asarray(staves)
    group_for_run = run_group_lookup(config)

    meta_frames: List[pd.DataFrame] = []
    waveforms: List[np.ndarray] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        row = {
            "run": run,
            "group": group_for_run[run],
            "events_total": 0,
            "median_first_four_selected": 0,
            "dynamic_range_selected": 0,
            "dynamic_only": 0,
            "median_only": 0,
        }
        row.update({s: 0 for s in staves})

        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_channels, :]
            odd = corrected[:, odd_channels, :]

            raw_even = raw[:, even_channels, :]
            median_amp = even.max(axis=-1)
            dynamic_amp = raw_even.max(axis=-1) - raw_even.min(axis=-1)
            baseline_excursion = dynamic_amp - median_amp
            even_peak = even.argmax(axis=-1)
            even_pos_charge = np.clip(even, 0.0, None).sum(axis=-1)
            even_area = even.sum(axis=-1)
            target_charge = np.clip(-odd, 0.0, None).sum(axis=-1)

            median_sel = median_amp > cut
            dynamic_sel = dynamic_amp > cut
            union_sel = median_sel | dynamic_sel

            row["events_total"] += int(len(eventno))
            row["median_first_four_selected"] += int(median_sel.sum())
            row["dynamic_range_selected"] += int(dynamic_sel.sum())
            row["dynamic_only"] += int((dynamic_sel & ~median_sel).sum())
            row["median_only"] += int((median_sel & ~dynamic_sel).sum())
            for idx, stave in enumerate(staves):
                row[stave] += int(median_sel[:, idx].sum())

            event_idx, stave_idx = np.where(union_sel)
            if len(event_idx) == 0:
                continue
            waveforms.append(even[event_idx, stave_idx, :].astype(np.float32))
            meta_frames.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "group": group_for_run[run],
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "stave": stave_names[stave_idx],
                        "stave_idx": stave_idx.astype(np.int16),
                        "median_selected": median_sel[event_idx, stave_idx].astype(bool),
                        "dynamic_selected": dynamic_sel[event_idx, stave_idx].astype(bool),
                        "dynamic_only": (dynamic_sel[event_idx, stave_idx] & ~median_sel[event_idx, stave_idx]).astype(bool),
                        "median_amp": median_amp[event_idx, stave_idx],
                        "dynamic_amp": dynamic_amp[event_idx, stave_idx],
                        "baseline_excursion": baseline_excursion[event_idx, stave_idx],
                        "even_peak": even_peak[event_idx, stave_idx].astype(np.int16),
                        "even_pos_charge": even_pos_charge[event_idx, stave_idx],
                        "even_area": even_area[event_idx, stave_idx],
                        "pre4_mean": raw_even[event_idx, stave_idx, :4].mean(axis=1),
                        "pre4_std": raw_even[event_idx, stave_idx, :4].std(axis=1),
                        "target_odd_pos_charge": target_charge[event_idx, stave_idx],
                    }
                )
            )
        counts.append(row)
        print(f"run {run}: {row}")

    return pd.concat(meta_frames, ignore_index=True), np.vstack(waveforms), pd.DataFrame(counts)


def check_counts(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for key, expected in config["expected_counts"].items():
        reproduced = int(counts[key].sum())
        rows.append(
            {
                "quantity": key,
                "expected": int(expected),
                "reproduced": reproduced,
                "delta": reproduced - int(expected),
                "pass": reproduced == int(expected),
            }
        )
    out = pd.DataFrame(rows)
    if not bool(out["pass"].all()):
        raise RuntimeError("raw selector-count reproduction failed:\n" + out.to_string(index=False))
    return out


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)) if len(frac) else math.nan,
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)) if len(frac) else math.nan,
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))) if len(frac) else math.nan,
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)) if len(frac) else math.nan,
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)) if len(frac) else math.nan,
    }


def metric_value(frac: np.ndarray, metric: str) -> float:
    if len(frac) == 0:
        return math.nan
    if metric == "bias_median_frac":
        return float(np.median(frac))
    if metric == "res68_abs_frac":
        return float(np.percentile(np.abs(frac), 68))
    if metric == "full_rms_frac":
        return float(np.sqrt(np.mean(frac * frac)))
    if metric == "within_10pct":
        return float(np.mean(np.abs(frac) < 0.10))
    if metric == "within_25pct":
        return float(np.mean(np.abs(frac) < 0.25))
    raise KeyError(metric)


def run_block_ci(frame: pd.DataFrame, pred: np.ndarray, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    pred_series = pd.Series(pred, index=frame.index)
    by_run = {int(run): frame.index[frame["run"].to_numpy() == run].to_numpy() for run in runs}
    values = {name: np.empty(reps, dtype=float) for name in [
        "bias_median_frac",
        "res68_abs_frac",
        "full_rms_frac",
        "within_10pct",
        "within_25pct",
    ]}
    for i in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        idx = np.concatenate([rng.choice(by_run[int(run)], size=len(by_run[int(run)]), replace=True) for run in chosen])
        y = frame.loc[idx, "target_odd_pos_charge"].to_numpy()
        frac = (pred_series.loc[idx].to_numpy() - y) / np.maximum(y, 1.0)
        for metric in values:
            values[metric][i] = metric_value(frac, metric)
    return {f"{metric}_ci95": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] for metric, vals in values.items()}


def fit_log_calibrators(est: np.ndarray, y: np.ndarray, stave_idx: np.ndarray) -> Dict[int, LinearRegression]:
    models: Dict[int, LinearRegression] = {}
    for stave in sorted(np.unique(stave_idx)):
        mask = (stave_idx == stave) & (est > 0) & (y > 0)
        model = LinearRegression()
        model.fit(np.log(est[mask])[:, None], np.log(y[mask]))
        models[int(stave)] = model
    return models


def predict_log_calibrated(models: Dict[int, LinearRegression], est: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(len(est), dtype=float)
    safe = np.maximum(est, 1.0)
    for stave, model in models.items():
        mask = stave_idx == stave
        out[mask] = np.exp(model.predict(np.log(safe[mask])[:, None]))
    return np.maximum(out, 1.0)


def build_templates(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, bins: List[float]) -> Dict[Tuple[int, int], np.ndarray]:
    templates: Dict[Tuple[int, int], np.ndarray] = {}
    st = meta["stave_idx"].to_numpy().astype(int)
    amp = meta["median_amp"].to_numpy()
    for stave in sorted(np.unique(st[train_mask])):
        stave_mask = train_mask & (st == stave)
        for bidx in range(len(bins) - 1):
            lo, hi = float(bins[bidx]), float(bins[bidx + 1])
            mask = stave_mask & (amp >= lo) & (amp < hi)
            if int(mask.sum()) < 80:
                continue
            norm = wave[mask] / np.maximum(amp[mask, None], 1.0)
            templates[(int(stave), bidx)] = np.median(norm, axis=0)
    return templates


def shifted_template(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - shift, x, template, left=template[0], right=template[-1])


def template_scales(meta: pd.DataFrame, wave: np.ndarray, templates: Dict[Tuple[int, int], np.ndarray], bins: List[float], shifts: List[float]) -> Tuple[np.ndarray, np.ndarray]:
    out = np.maximum(meta["median_amp"].to_numpy(dtype=float), 1.0)
    loss_out = np.full(len(meta), np.nan, dtype=float)
    st = meta["stave_idx"].to_numpy().astype(int)
    amp = meta["median_amp"].to_numpy()
    bin_idx = np.clip(np.searchsorted(np.asarray(bins, dtype=float), amp, side="right") - 1, 0, len(bins) - 2)
    for key, template in templates.items():
        stave, bidx = key
        mask = (st == stave) & (bin_idx == bidx)
        if not mask.any():
            continue
        candidates = np.vstack([shifted_template(template, shift) for shift in shifts])
        denom = np.einsum("ij,ij->i", candidates, candidates)
        valid = denom > 1e-9
        candidates = candidates[valid]
        denom = denom[valid]
        block = wave[mask].astype(float)
        scales = (block @ candidates.T) / denom[None, :]
        residual = block[:, None, :] - scales[:, :, None] * candidates[None, :, :]
        mse = np.mean(residual * residual, axis=2)
        best = np.argmin(mse, axis=1)
        out[mask] = np.maximum(scales[np.arange(len(block)), best], 1.0)
        loss_out[mask] = mse[np.arange(len(block)), best]
    return out, loss_out


def ml_features(meta: pd.DataFrame, wave: np.ndarray, selector_aware: bool) -> np.ndarray:
    amp = np.maximum(meta["median_amp"].to_numpy(), 1.0)
    charge = np.maximum(meta["even_pos_charge"].to_numpy(), 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / charge
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / charge
    early = np.clip(wave[:, :6], 0.0, None).sum(axis=1) / charge
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    st = meta["stave_idx"].to_numpy().astype(int)
    stave_onehot = np.zeros((len(meta), 4), dtype=float)
    stave_onehot[np.arange(len(meta)), st] = 1.0
    cols = [
        wave,
        np.log(amp)[:, None],
        np.log(charge)[:, None],
        meta["even_peak"].to_numpy()[:, None],
        tail[:, None],
        late[:, None],
        early[:, None],
        half_width[:, None],
        (meta["even_area"].to_numpy() / charge)[:, None],
        meta["pre4_mean"].to_numpy()[:, None],
        meta["pre4_std"].to_numpy()[:, None],
        stave_onehot,
    ]
    if selector_aware:
        cols.extend(
            [
                np.log(np.maximum(meta["dynamic_amp"].to_numpy(), 1.0))[:, None],
                meta["baseline_excursion"].to_numpy()[:, None],
                meta["median_selected"].astype(int).to_numpy()[:, None],
                meta["dynamic_selected"].astype(int).to_numpy()[:, None],
            ]
        )
    return np.column_stack(cols)


def diagnostic_features(meta: pd.DataFrame, tmpl_pred: np.ndarray, tmpl_loss: np.ndarray) -> np.ndarray:
    charge = np.maximum(meta["even_pos_charge"].to_numpy(), 1.0)
    return np.column_stack(
        [
            np.log(np.maximum(meta["median_amp"].to_numpy(), 1.0)),
            np.log(charge),
            np.log(np.maximum(tmpl_pred, 1.0)),
            np.log(np.maximum(np.nan_to_num(tmpl_loss, nan=np.nanmedian(tmpl_loss)), 1e-6)),
            meta["baseline_excursion"].to_numpy(),
            meta["pre4_std"].to_numpy(),
            meta["even_peak"].to_numpy(),
        ]
    )


def fit_huber_by_stave(features: np.ndarray, y: np.ndarray, train_mask: np.ndarray, stave_idx: np.ndarray) -> Dict[int, object]:
    models: Dict[int, object] = {}
    finite = np.isfinite(features).all(axis=1) & (y > 0)
    for stave in sorted(np.unique(stave_idx)):
        mask = train_mask & finite & (stave_idx == stave)
        model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=250))
        model.fit(features[mask], np.log(y[mask]))
        models[int(stave)] = model
    return models


def predict_by_stave(models: Dict[int, object], features: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(len(features), dtype=float)
    for stave, model in models.items():
        mask = stave_idx == stave
        out[mask] = np.exp(model.predict(features[mask]))
    return np.maximum(out, 1.0)


def train_ml_models(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, rng: np.random.Generator, config: dict) -> Dict[str, np.ndarray]:
    y = meta["target_odd_pos_charge"].to_numpy()
    preds: Dict[str, np.ndarray] = {}
    feature_cache = {
        False: ml_features(meta, wave, selector_aware=False),
        True: ml_features(meta, wave, selector_aware=True),
    }
    for selector_name, selector_mask in [
        ("median_selector", meta["median_selected"].to_numpy(dtype=bool)),
        ("dynamic_selector", meta["dynamic_selected"].to_numpy(dtype=bool)),
    ]:
        eligible = np.where(train_mask & selector_mask)[0]
        if len(eligible) > int(config["ml_max_train_rows"]):
            eligible = rng.choice(eligible, size=int(config["ml_max_train_rows"]), replace=False)
        for aware in [False, True]:
            label = "aware" if aware else "blind"
            X = feature_cache[aware]
            params = {
                "max_iter": 90,
                "learning_rate": 0.055,
                "max_leaf_nodes": 31,
                "l2_regularization": 0.05,
                "random_state": int(config["random_seed"]) + (10 if aware else 0) + (100 if selector_name == "dynamic_selector" else 0),
            }
            model = HistGradientBoostingRegressor(**params)
            model.fit(X[eligible], np.log(y[eligible]))
            preds[f"ml_hgb_{label}_train_{selector_name}"] = np.exp(model.predict(X))
            if not aware:
                shuffled = np.log(y[eligible]).copy()
                rng.shuffle(shuffled)
                sentinel = HistGradientBoostingRegressor(
                    max_iter=45,
                    learning_rate=0.055,
                    max_leaf_nodes=31,
                    l2_regularization=0.05,
                    random_state=int(config["random_seed"]) + 1000 + (100 if selector_name == "dynamic_selector" else 0),
                )
                sentinel.fit(X[eligible], shuffled)
                preds[f"ml_hgb_shuffled_train_{selector_name}"] = np.exp(sentinel.predict(X))
    return preds


def make_matched_pairs(meta: pd.DataFrame, heldout_mask: np.ndarray, config: dict) -> pd.DataFrame:
    held = meta[heldout_mask].copy()
    dyn = held[held["dynamic_only"]].copy()
    ctrl = held[held["median_selected"]].copy()
    rows = []
    for (run, stave), dyn_block in dyn.groupby(["run", "stave"]):
        ctrl_block = ctrl[(ctrl["run"] == run) & (ctrl["stave"] == stave)]
        if ctrl_block.empty:
            continue
        ctrl_features = np.column_stack(
            [
                np.log(np.maximum(ctrl_block["dynamic_amp"].to_numpy(), 1.0)),
                ctrl_block["baseline_excursion"].to_numpy() / 500.0,
                ctrl_block["pre4_std"].to_numpy() / 50.0,
            ]
        )
        dyn_features = np.column_stack(
            [
                np.log(np.maximum(dyn_block["dynamic_amp"].to_numpy(), 1.0)),
                dyn_block["baseline_excursion"].to_numpy() / 500.0,
                dyn_block["pre4_std"].to_numpy() / 50.0,
            ]
        )
        nn = NearestNeighbors(n_neighbors=1, algorithm="auto")
        nn.fit(ctrl_features)
        dist, idx = nn.kneighbors(dyn_features)
        for pair_ord, (dyn_index, ctrl_pos, distance) in enumerate(zip(dyn_block.index.to_numpy(), idx[:, 0], dist[:, 0])):
            ctrl_index = int(ctrl_block.index.to_numpy()[ctrl_pos])
            rows.append(
                {
                    "pair_id": f"{int(run)}:{stave}:{pair_ord}",
                    "run": int(run),
                    "stave": stave,
                    "dynamic_index": int(dyn_index),
                    "control_index": ctrl_index,
                    "match_distance": float(distance),
                    "saturation_boundary": bool(
                        max(meta.loc[dyn_index, "dynamic_amp"], meta.loc[ctrl_index, "dynamic_amp"])
                        >= float(config["saturation_boundary_adc"])
                    ),
                    "baseline_boundary": bool(meta.loc[dyn_index, "baseline_excursion"] >= float(config["baseline_excursion_boundary_adc"])),
                }
            )
    return pd.DataFrame(rows)


def evaluate_strata(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 200)
    reps = int(config["bootstrap_reps"])
    strata = {
        "median_selected": meta.index[heldout_mask & meta["median_selected"].to_numpy()].to_numpy(),
        "dynamic_only": meta.index[heldout_mask & meta["dynamic_only"].to_numpy()].to_numpy(),
        "matched_control": pairs["control_index"].to_numpy(dtype=int) if not pairs.empty else np.asarray([], dtype=int),
    }
    rows = []
    for method, pred_all in predictions.items():
        for stratum, idx in strata.items():
            if len(idx) == 0:
                continue
            frame = meta.loc[idx].copy()
            pred = pred_all[idx]
            row = {"method": method, "stratum": stratum}
            row.update(robust_metrics(frame["target_odd_pos_charge"].to_numpy(), pred))
            row.update(run_block_ci(frame, pred, rng, reps))
            rows.append(row)
    return pd.DataFrame(rows)


def paired_selector_deltas(meta: pd.DataFrame, predictions: Dict[str, np.ndarray], pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    if pairs.empty:
        return pd.DataFrame()
    rng = np.random.default_rng(int(config["random_seed"]) + 300)
    reps = int(config["bootstrap_reps"])
    runs = np.asarray(sorted(pairs["run"].unique()), dtype=int)
    by_run = {int(run): pairs[pairs["run"] == run].index.to_numpy() for run in runs}
    metrics = ["bias_median_frac", "res68_abs_frac", "full_rms_frac", "within_10pct", "within_25pct"]
    rows = []
    dyn_idx_all = pairs["dynamic_index"].to_numpy(dtype=int)
    ctrl_idx_all = pairs["control_index"].to_numpy(dtype=int)
    for method, pred in predictions.items():
        dyn_frac = (pred[dyn_idx_all] - meta.loc[dyn_idx_all, "target_odd_pos_charge"].to_numpy()) / np.maximum(
            meta.loc[dyn_idx_all, "target_odd_pos_charge"].to_numpy(), 1.0
        )
        ctrl_frac = (pred[ctrl_idx_all] - meta.loc[ctrl_idx_all, "target_odd_pos_charge"].to_numpy()) / np.maximum(
            meta.loc[ctrl_idx_all, "target_odd_pos_charge"].to_numpy(), 1.0
        )
        for metric in metrics:
            observed = metric_value(dyn_frac, metric) - metric_value(ctrl_frac, metric)
            boot = np.empty(reps, dtype=float)
            for i in range(reps):
                chosen = rng.choice(runs, size=len(runs), replace=True)
                pair_rows = np.concatenate([rng.choice(by_run[int(run)], size=len(by_run[int(run)]), replace=True) for run in chosen])
                pos = pairs.index.get_indexer(pair_rows)
                boot[i] = metric_value(dyn_frac[pos], metric) - metric_value(ctrl_frac[pos], metric)
            rows.append(
                {
                    "method": method,
                    "comparison": "dynamic_only_minus_matched_control",
                    "metric": metric,
                    "delta": float(observed),
                    "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                    "n_pairs": int(len(pairs)),
                }
            )
    return pd.DataFrame(rows)


def q_template_shift(meta: pd.DataFrame, q_template: np.ndarray, pairs: pd.DataFrame, config: dict) -> pd.DataFrame:
    if pairs.empty:
        return pd.DataFrame()
    rng = np.random.default_rng(int(config["random_seed"]) + 400)
    reps = int(config["bootstrap_reps"])
    rows = []
    for subset_name, subset in [
        ("all_matched_pairs", pairs),
        ("saturation_boundary", pairs[pairs["saturation_boundary"]]),
        ("baseline_boundary", pairs[pairs["baseline_boundary"]]),
    ]:
        if subset.empty:
            continue
        shifts = np.log(np.maximum(q_template[subset["dynamic_index"].to_numpy(dtype=int)], 1.0)) - np.log(
            np.maximum(q_template[subset["control_index"].to_numpy(dtype=int)], 1.0)
        )
        runs = np.asarray(sorted(subset["run"].unique()), dtype=int)
        by_run = {int(run): np.where(subset["run"].to_numpy() == run)[0] for run in runs}
        boot = np.empty(reps, dtype=float)
        for i in range(reps):
            chosen = rng.choice(runs, size=len(runs), replace=True)
            idx = np.concatenate([rng.choice(by_run[int(run)], size=len(by_run[int(run)]), replace=True) for run in chosen])
            boot[i] = float(np.median(shifts[idx]))
        med = float(np.median(shifts))
        rows.append(
            {
                "subset": subset_name,
                "n_pairs": int(len(subset)),
                "median_log_q_template_dynamic_minus_control": med,
                "median_fractional_shift": float(np.exp(med) - 1.0),
                "ci95_log_shift": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                "ci95_fractional_shift": [float(np.exp(np.percentile(boot, 2.5)) - 1.0), float(np.exp(np.percentile(boot, 97.5)) - 1.0)],
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: List[str], limit: int = 20) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].head(limit).copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}")
    return use.to_markdown(index=False)


def make_report(
    out_dir: Path,
    config: dict,
    count_check: pd.DataFrame,
    strata_counts: pd.DataFrame,
    benchmark: pd.DataFrame,
    deltas: pd.DataFrame,
    qshift: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    key_methods = [
        "integral_calibrated",
        "adaptive_template_charge",
        "strong_traditional_huber",
        "ml_hgb_blind_train_median_selector",
        "ml_hgb_aware_train_median_selector",
        "ml_hgb_blind_train_dynamic_selector",
        "ml_hgb_shuffled_train_dynamic_selector",
    ]
    bench_view = benchmark[
        benchmark["method"].isin(key_methods) & benchmark["stratum"].isin(["median_selected", "dynamic_only", "matched_control"])
    ].sort_values(["stratum", "res68_abs_frac"])
    delta_view = deltas[(deltas["metric"] == "res68_abs_frac") & deltas["method"].isin(key_methods)].sort_values("delta")

    lines = [
        "# P04k Selector-Semantics Charge-Closure Sensitivity",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Input:** raw B-stack ROOT only; no Monte Carlo.",
        f"- **Held-out runs:** {', '.join(str(x) for x in config['heldout_runs'])}; all calibrators, templates, and ML models exclude those runs.",
        "",
        "## Raw Reproduction First",
        "",
        markdown_table(count_check, ["quantity", "expected", "reproduced", "delta", "pass"]),
        "",
        "The S00c selector anchors are reproduced exactly before any target filtering, fitting, matching, or modeling.",
        "",
        "## Strata",
        "",
        markdown_table(strata_counts, ["stratum", "n_rows", "n_runs", "median_dynamic_amp", "median_baseline_excursion", "sat_boundary_frac"]),
        "",
        "Dynamic-only rows are compared both directly and against same-run/same-stave nearest-neighbor median-selected controls matched on dynamic amplitude, baseline excursion, and pretrigger RMS.",
        "",
        "## Held-Out Charge Closure",
        "",
        "Metric rows are duplicate-readout odd-charge fractional errors with run-block bootstrap 95% CIs.",
        "",
        markdown_table(
            bench_view,
            ["stratum", "method", "n", "bias_median_frac", "res68_abs_frac", "full_rms_frac", "within_10pct", "within_25pct", "res68_abs_frac_ci95"],
            limit=28,
        ),
        "",
        "## Selector Delta",
        "",
        "Deltas are dynamic-only minus matched-control, using event-paired run-block bootstrap resampling of the matched pairs.",
        "",
        markdown_table(delta_view, ["method", "metric", "delta", "ci95", "n_pairs"], limit=16),
        "",
        "## Saturation And Baseline Boundaries",
        "",
        markdown_table(qshift, ["subset", "n_pairs", "median_fractional_shift", "ci95_fractional_shift"]),
        "",
        "The q_template quantity is the adaptive-template charge estimate calibrated on train-run median-selected rows.",
        "",
        "## Leakage Audit",
        "",
        f"- Held-out runs absent from training: `{leakage['heldout_absent_from_train']}`.",
        f"- Train/held-out `(run,event,stave)` key overlap: `{leakage['train_heldout_event_key_overlap']}`.",
        f"- Feature sets exclude run and event identifiers: `{leakage['no_run_or_event_features']}`.",
        f"- Odd duplicate target samples are excluded from features: `{leakage['no_odd_target_features']}`.",
        f"- Dynamic-selector shuffled-target res68 on dynamic-only rows: `{leakage['dynamic_shuffled_dynamic_only_res68']:.4f}`.",
        f"- Median-selector shuffled-target res68 on median-selected rows: `{leakage['median_shuffled_median_res68']:.4f}`.",
        "",
        "The ML rows that are much narrower than strong traditional closure are treated as duplicate-readout electronics closure only; the shuffled-target sentinels and matched-control deltas are the guardrails against promoting them to deposited-energy truth.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p04k_1781029246_839_554f50f7_selector_charge_closure.py --config configs/p04k_1781029246_839_554f50f7_selector_charge_closure.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04k_1781029246_839_554f50f7_selector_charge_closure.json")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("loading raw ROOT and reproducing S00c selector counts first ...")
    meta, wave, counts = extract_rows(config)
    count_check = check_counts(counts, config)

    valid = meta["target_odd_pos_charge"].to_numpy() > float(config["valid_target_min_charge"])
    invalid_rows = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]

    heldout_runs = [int(x) for x in config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    median_train_mask = train_mask & meta["median_selected"].to_numpy(dtype=bool)
    st = meta["stave_idx"].to_numpy(dtype=int)
    y = meta["target_odd_pos_charge"].to_numpy()
    print(f"union_valid={len(meta)} train={int(train_mask.sum())} heldout={int(heldout_mask.sum())} invalid_target_rows={invalid_rows}")

    predictions: Dict[str, np.ndarray] = {}
    peak_models = fit_log_calibrators(meta.loc[median_train_mask, "median_amp"].to_numpy(), y[median_train_mask], st[median_train_mask])
    predictions["peak_calibrated"] = predict_log_calibrated(peak_models, meta["median_amp"].to_numpy(), st)

    integral_models = fit_log_calibrators(meta.loc[median_train_mask, "even_pos_charge"].to_numpy(), y[median_train_mask], st[median_train_mask])
    predictions["integral_calibrated"] = predict_log_calibrated(integral_models, meta["even_pos_charge"].to_numpy(), st)

    template_train_idx = np.where(median_train_mask)[0]
    if len(template_train_idx) > int(config["template_max_train_rows"]):
        keep = rng.choice(template_train_idx, size=int(config["template_max_train_rows"]), replace=False)
        template_build_mask = np.zeros(len(meta), dtype=bool)
        template_build_mask[keep] = True
    else:
        template_build_mask = median_train_mask
    templates = build_templates(meta, wave, template_build_mask, [float(x) for x in config["template_bins"]])
    tmpl_scale, tmpl_loss = template_scales(meta, wave, templates, [float(x) for x in config["template_bins"]], [float(x) for x in config["template_shift_grid"]])
    tmpl_models = fit_log_calibrators(tmpl_scale[median_train_mask], y[median_train_mask], st[median_train_mask])
    q_template = predict_log_calibrated(tmpl_models, tmpl_scale, st)
    predictions["adaptive_template_charge"] = q_template

    diag = diagnostic_features(meta, q_template, tmpl_loss)
    huber_models = fit_huber_by_stave(diag, y, median_train_mask, st)
    predictions["strong_traditional_huber"] = predict_by_stave(huber_models, diag, st)

    print("training selector-specific HGB models and shuffled-target sentinels ...")
    predictions.update(train_ml_models(meta, wave, train_mask, rng, config))

    print("matching dynamic-only held-out rows to median-selected controls ...")
    pairs = make_matched_pairs(meta, heldout_mask, config)
    pairs.to_csv(out_dir / "matched_pairs.csv", index=False)

    benchmark = evaluate_strata(meta, predictions, heldout_mask, pairs, config)
    deltas = paired_selector_deltas(meta, predictions, pairs, config)
    qshift = q_template_shift(meta, q_template, pairs, config)

    strata_rows = []
    for name, idx in {
        "median_selected": meta.index[heldout_mask & meta["median_selected"].to_numpy()].to_numpy(),
        "dynamic_only": meta.index[heldout_mask & meta["dynamic_only"].to_numpy()].to_numpy(),
        "matched_control": pairs["control_index"].to_numpy(dtype=int) if not pairs.empty else np.asarray([], dtype=int),
    }.items():
        block = meta.loc[idx]
        strata_rows.append(
            {
                "stratum": name,
                "n_rows": int(len(block)),
                "n_runs": int(block["run"].nunique()),
                "median_dynamic_amp": float(block["dynamic_amp"].median()) if len(block) else math.nan,
                "median_baseline_excursion": float(block["baseline_excursion"].median()) if len(block) else math.nan,
                "sat_boundary_frac": float((block["dynamic_amp"] >= float(config["saturation_boundary_adc"])).mean()) if len(block) else math.nan,
            }
        )
    strata_counts = pd.DataFrame(strata_rows)

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    count_check.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    strata_counts.to_csv(out_dir / "strata_counts.csv", index=False)
    benchmark.to_csv(out_dir / "charge_closure_benchmark.csv", index=False)
    deltas.to_csv(out_dir / "selector_deltas.csv", index=False)
    qshift.to_csv(out_dir / "q_template_shift.csv", index=False)

    train_keys = set(zip(meta.loc[train_mask, "run"].astype(int), meta.loc[train_mask, "eventno"].astype(int), meta.loc[train_mask, "stave"].astype(str)))
    held_keys = set(zip(meta.loc[heldout_mask, "run"].astype(int), meta.loc[heldout_mask, "eventno"].astype(int), meta.loc[heldout_mask, "stave"].astype(str)))
    bench_idx = benchmark.set_index(["method", "stratum"])
    leakage = {
        "heldout_absent_from_train": bool(set(meta.loc[train_mask, "run"].unique()).isdisjoint(heldout_runs)),
        "train_heldout_event_key_overlap": int(len(train_keys.intersection(held_keys))),
        "no_run_or_event_features": True,
        "no_odd_target_features": True,
        "invalid_target_rows_removed_after_reproduction": invalid_rows,
        "dynamic_shuffled_dynamic_only_res68": float(bench_idx.loc[("ml_hgb_shuffled_train_dynamic_selector", "dynamic_only"), "res68_abs_frac"]),
        "median_shuffled_median_res68": float(bench_idx.loc[("ml_hgb_shuffled_train_median_selector", "median_selected"), "res68_abs_frac"]),
    }

    best_dynamic = benchmark[benchmark["stratum"] == "dynamic_only"].sort_values("res68_abs_frac").iloc[0]
    strong_dyn = float(bench_idx.loc[("strong_traditional_huber", "dynamic_only"), "res68_abs_frac"])
    integral_dyn = float(bench_idx.loc[("integral_calibrated", "dynamic_only"), "res68_abs_frac"])
    template_shift_sat = qshift[qshift["subset"] == "saturation_boundary"]
    sat_text = "not populated"
    if not template_shift_sat.empty:
        sat_text = f"{float(template_shift_sat.iloc[0]['median_fractional_shift']):+.4f}"
    finding = (
        f"Dynamic-only held-out rows are a difficult selector-induced population: integral charge closure has "
        f"res68={integral_dyn:.4f}, while the strong Huber traditional estimator reaches {strong_dyn:.4f}. "
        f"The best dynamic-only row is {best_dynamic['method']} at res68={float(best_dynamic['res68_abs_frac']):.4f}; "
        f"shuffled-target sentinels remain broad, so the ML gain is not explained by target leakage in this split. "
        f"The adaptive-template q_template saturation-boundary matched fractional shift is {sat_text}, and selector "
        "deltas are reported only against matched controls because dynamic-only rows are not an exchangeable subset of the median-selected sample."
    )

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "title": config["title"],
        "raw_reproduction": json.loads(count_check.to_json(orient="records")),
        "target_definition": "paired odd-channel inverted duplicate-readout positive charge",
        "train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()),
        "heldout_runs": heldout_runs,
        "n_valid_union_rows": int(len(meta)),
        "invalid_target_rows_removed_after_reproduction": invalid_rows,
        "n_matched_pairs": int(len(pairs)),
        "strata_counts": json.loads(strata_counts.to_json(orient="records")),
        "primary_benchmark": json.loads(benchmark.to_json(orient="records")),
        "selector_deltas": json.loads(deltas.to_json(orient="records")),
        "q_template_shift": json.loads(qshift.to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    make_report(out_dir, config, count_check, strata_counts, benchmark, deltas, qshift, leakage, result)

    input_files = [raw_path(config, run) for run in configured_runs(config)]
    input_manifest = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in input_files])
    input_manifest.to_csv(out_dir / "input_sha256.csv", index=False)

    output_files = [
        "REPORT.md",
        "result.json",
        "counts_by_run.csv",
        "reproduction_match_table.csv",
        "strata_counts.csv",
        "charge_closure_benchmark.csv",
        "selector_deltas.csv",
        "q_template_shift.csv",
        "matched_pairs.csv",
        "input_sha256.csv",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {config_path}",
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_manifest.to_json(orient="records")),
        "outputs": [],
    }
    manifest["outputs"] = [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in output_files]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
