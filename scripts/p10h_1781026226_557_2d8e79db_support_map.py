#!/usr/bin/env python3
"""P10h explicit-handle q-template support map.

Rebuilds the selected B-stave pulse table from raw ROOT, then evaluates S01
empirical templates, train-only handle residual tables, and explicit-handle ML
template predictors under run-family holdouts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def load_p10a():
    path = Path("scripts/p10a_conditional_template.py")
    spec = importlib.util.spec_from_file_location("p10a_conditional_template", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p10a = load_p10a()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def labels_from_edges(edges: np.ndarray) -> List[str]:
    return [f"a{int(edges[i])}_{int(edges[i + 1])}" for i in range(len(edges) - 1)]


def current_lookup(config: dict) -> Dict[int, str]:
    out = {}
    for name, runs in config["current_strata"].items():
        for run in runs:
            out[int(run)] = str(name)
    return out


def add_handle_strata(config: dict, table: pd.DataFrame, aligned: np.ndarray, norm: np.ndarray) -> pd.DataFrame:
    out = table.copy()
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    amp = out["amplitude_adc"].to_numpy(dtype=float)
    amp_bin = p10a.assign_amp_bins(amp, edges)
    amp_labels = np.asarray(labels_from_edges(edges), dtype=object)
    out["amp_bin"] = amp_bin
    out["amp_region"] = amp_labels[amp_bin]

    peak = np.nanmax(norm, axis=1)
    cfd20 = p10a.cfd_times(norm, np.maximum(peak, 1.0e-6), 0.20)
    cfd80 = p10a.cfd_times(norm, np.maximum(peak, 1.0e-6), 0.80)
    rise = cfd80 - cfd20
    phase = cfd20 - np.floor(cfd20)
    out["rise_width_samples"] = rise
    out["cfd_phase"] = phase
    out["rise_width_region"] = pd.cut(
        rise,
        bins=[-np.inf, 1.15, 1.75, np.inf],
        labels=["rise_narrow", "rise_mid", "rise_wide"],
    ).astype(str)
    out["cfd_phase_region"] = pd.cut(
        phase,
        bins=[-0.01, 0.33, 0.66, 1.01],
        labels=["phase_early", "phase_mid", "phase_late"],
    ).astype(str)

    rel = np.asarray(config["aligned_relative_grid"], dtype=float)
    yy = np.nan_to_num(aligned.astype(float), nan=0.0)
    tail_sum = yy[:, rel >= 2].sum(axis=1)
    late_sum = yy[:, rel >= 8].sum(axis=1)
    out["tail_sum"] = tail_sum
    out["tail_late_frac"] = late_sum / np.maximum(tail_sum, 1.0e-9)
    out["tail_shape_region"] = pd.cut(
        out["tail_late_frac"].to_numpy(dtype=float),
        bins=[-np.inf, 0.18, 0.34, np.inf],
        labels=["tail_compact", "tail_mid", "tail_long"],
    ).astype(str)

    out["saturation_region"] = pd.cut(
        amp,
        bins=[999.0, 6500.0, 9000.0, np.inf],
        labels=["unsaturated", "boundary", "saturated_proxy"],
    ).astype(str)
    currents = current_lookup(config)
    out["current_family"] = [currents.get(int(run), "other") for run in out["run"]]
    out["run_family"] = out["group"].astype(str)
    out["support_cell"] = (
        out["amp_region"].astype(str)
        + "|"
        + out["stave"].astype(str)
        + "|"
        + out["rise_width_region"].astype(str)
        + "|"
        + out["cfd_phase_region"].astype(str)
        + "|"
        + out["tail_shape_region"].astype(str)
        + "|"
        + out["saturation_region"].astype(str)
        + "|"
        + out["current_family"].astype(str)
        + "|"
        + out["run_family"].astype(str)
    )
    return out


def waveform_live10_tail(aligned: np.ndarray, config: dict) -> pd.DataFrame:
    rel = np.asarray(config["aligned_relative_grid"], dtype=float)
    period = float(config["sample_period_ns"])
    rows = []
    for y0 in aligned:
        y = np.nan_to_num(y0.astype(float), nan=0.0)
        peak_i = int(np.nanargmax(y))
        after = np.flatnonzero((np.arange(len(y)) >= peak_i) & (y >= 0.10))
        live10 = float(rel[after[-1]] * period) if len(after) else np.nan
        tail = float(y[rel >= 2].sum())
        late = float(y[rel >= 8].sum())
        rows.append({"live10_ns": live10, "tail_sum": tail, "tail_late_frac": late / max(tail, 1.0e-9)})
    return pd.DataFrame(rows)


def select_capped_indices(table: pd.DataFrame, mask: np.ndarray, group_cols: List[str], cap: int, max_total: int, rng: np.random.Generator) -> np.ndarray:
    parts = []
    pool = table.loc[mask]
    for _, sub in pool.groupby(group_cols, observed=True):
        idx = sub.index.to_numpy()
        if len(idx) > cap:
            idx = rng.choice(idx, size=cap, replace=False)
        parts.append(idx)
    if not parts:
        return np.asarray([], dtype=int)
    idx = np.sort(np.concatenate(parts))
    if len(idx) > max_total:
        idx = np.sort(rng.choice(idx, size=max_total, replace=False))
    return idx.astype(int)


def predict_empirical(table: pd.DataFrame, aligned: np.ndarray, pack: dict, rows: np.ndarray) -> np.ndarray:
    edges = pack["edges"]
    bins = p10a.assign_amp_bins(table.iloc[rows]["amplitude_adc"].to_numpy(dtype=float), edges)
    pred = []
    for i, row in enumerate(table.iloc[rows].itertuples()):
        pred.append(pack["templates"][(row.stave, int(bins[i]))])
    return np.vstack(pred).astype(np.float32)


def build_handle_residuals(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_idx: np.ndarray, s01_pred_train: np.ndarray) -> Tuple[dict, pd.DataFrame]:
    residual = aligned[train_idx].astype(np.float32) - s01_pred_train.astype(np.float32)
    work = table.iloc[train_idx].copy()
    work["_local"] = np.arange(len(work))
    full_keys = ["stave", "amp_region", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family"]
    loose_keys = ["stave", "amp_region", "rise_width_region", "tail_shape_region", "saturation_region"]
    min_n = int(config["handle_min_bin_pulses"])
    tables = {"full": {}, "loose": {}}
    occ_rows = []
    for name, keys in [("full", full_keys), ("loose", loose_keys)]:
        for key, sub in work.groupby(keys, observed=True):
            loc = sub["_local"].to_numpy(dtype=int)
            n = int(len(loc))
            if n >= min_n:
                tables[name][tuple(str(v) for v in (key if isinstance(key, tuple) else (key,)))] = np.nanmedian(residual[loc], axis=0).astype(np.float32)
            occ_rows.append({"table": name, "key": "|".join(str(v) for v in (key if isinstance(key, tuple) else (key,))), "n_train": n, "usable": bool(n >= min_n)})
    return {"tables": tables, "full_keys": full_keys, "loose_keys": loose_keys}, pd.DataFrame(occ_rows)


def predict_handles(table: pd.DataFrame, rows: np.ndarray, s01_pred: np.ndarray, handle_pack: dict) -> Tuple[np.ndarray, List[str]]:
    pred = s01_pred.astype(np.float32).copy()
    sources = []
    for out_i, row in enumerate(table.iloc[rows].itertuples()):
        full = tuple(str(getattr(row, col)) for col in handle_pack["full_keys"])
        loose = tuple(str(getattr(row, col)) for col in handle_pack["loose_keys"])
        if full in handle_pack["tables"]["full"]:
            pred[out_i] += handle_pack["tables"]["full"][full]
            sources.append("full_handle")
        elif loose in handle_pack["tables"]["loose"]:
            pred[out_i] += handle_pack["tables"]["loose"][loose]
            sources.append("loose_handle")
        else:
            sources.append("s01_fallback")
    return pred, sources


def mse_to_prediction(aligned: np.ndarray, pred: np.ndarray) -> np.ndarray:
    valid = np.isfinite(aligned) & np.isfinite(pred)
    diff2 = (np.nan_to_num(aligned, nan=0.0) - np.nan_to_num(pred, nan=0.0)) ** 2
    denom = valid.sum(axis=1)
    out = np.full(len(aligned), np.nan, dtype=float)
    ok = denom > 0
    out[ok] = diff2[ok].sum(axis=1) / denom[ok]
    return out


FEATURE_GROUPS = {
    "amplitude": ["log_amp", "log_amp2", "amp_region"],
    "stave": ["stave"],
    "shape": ["rise_width_samples", "cfd_phase", "tail_sum", "tail_late_frac", "rise_width_region", "cfd_phase_region", "tail_shape_region"],
    "saturation": ["saturation_region"],
    "current": ["current_family"],
    "run_family": ["run_family"],
}


def feature_parts(table: pd.DataFrame, groups: Iterable[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    numeric = pd.DataFrame(index=table.index)
    cats = pd.DataFrame(index=table.index)
    amp = table["amplitude_adc"].to_numpy(dtype=float)
    source = table.copy()
    source["log_amp"] = np.log(np.maximum(amp, 1.0))
    source["log_amp2"] = source["log_amp"] ** 2
    for group in groups:
        for col in FEATURE_GROUPS[group]:
            if col in {"log_amp", "log_amp2", "rise_width_samples", "cfd_phase", "tail_sum", "tail_late_frac"}:
                numeric[col] = source[col].astype(float)
            else:
                cats[col] = source[col].astype(str)
    return numeric, cats


def fit_transform_features(train: pd.DataFrame, eval_: pd.DataFrame, groups: Iterable[str]):
    train_num, train_cat = feature_parts(train, groups)
    eval_num, eval_cat = feature_parts(eval_, groups)
    blocks_train, blocks_eval = [], []
    if train_num.shape[1]:
        scaler = StandardScaler()
        blocks_train.append(scaler.fit_transform(train_num.to_numpy(dtype=float)))
        blocks_eval.append(scaler.transform(eval_num.to_numpy(dtype=float)))
    if train_cat.shape[1]:
        enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
        blocks_train.append(enc.fit_transform(train_cat))
        blocks_eval.append(enc.transform(eval_cat))
    return np.column_stack(blocks_train).astype(float), np.column_stack(blocks_eval).astype(float)


def filled_targets(aligned: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    y = aligned[train_idx].astype(float)
    med = np.nanmedian(y, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    return np.where(np.isfinite(y), y, med[None, :]).astype(np.float32)


def fit_ml_predictions(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_idx: np.ndarray, eval_idx: np.ndarray, rng: np.random.Generator) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
    train = table.iloc[train_idx]
    eval_ = table.iloc[eval_idx]
    y = filled_targets(aligned, train_idx)
    rows = []
    out = {}
    model_specs = {
        "ridge": ("ridge", ["amplitude", "stave", "shape", "saturation", "current"]),
        "extra_trees": ("extra_trees", ["amplitude", "stave", "shape", "saturation", "current"]),
        "shuffled_target_extra_trees": ("extra_trees_shuffled", ["amplitude", "stave", "shape", "saturation", "current"]),
        "family_label_sentinel": ("extra_trees", ["current", "run_family"]),
        "knockout_no_amplitude": ("extra_trees", ["stave", "shape", "saturation", "current"]),
        "knockout_no_shape": ("extra_trees", ["amplitude", "stave", "saturation", "current"]),
        "knockout_no_stave": ("extra_trees", ["amplitude", "shape", "saturation", "current"]),
        "knockout_no_current": ("extra_trees", ["amplitude", "stave", "shape", "saturation"]),
    }
    for name, (kind, groups) in model_specs.items():
        X_train, X_eval = fit_transform_features(train, eval_, groups)
        target = y.copy()
        if kind == "extra_trees_shuffled":
            order = np.arange(len(target))
            rng.shuffle(order)
            target = target[order]
        if kind == "ridge":
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(config["ridge_alpha"])))
        else:
            params = dict(config["extra_trees"])
            params["random_state"] = int(config["random_seed"]) + len(rows) + 13
            model = ExtraTreesRegressor(**params)
        t0 = time.time()
        model.fit(X_train, target)
        out[name] = model.predict(X_eval).astype(np.float32)
        rows.append({"model": name, "kind": kind, "feature_groups": ",".join(groups), "train_rows": int(len(train_idx)), "eval_rows": int(len(eval_idx)), "fit_predict_sec": round(time.time() - t0, 2)})
    return out, pd.DataFrame(rows)


def shifted(template: np.ndarray, shift: float) -> np.ndarray:
    x = np.arange(len(template), dtype=float)
    return np.interp(x - float(shift), x, template, left=np.nan, right=np.nan)


def timing_fit_residual_ns(obs: np.ndarray, pred: np.ndarray, config: dict) -> np.ndarray:
    grid = np.asarray(config["timing_shift_grid_samples"], dtype=float)
    period = float(config["sample_period_ns"])
    out = np.full(len(obs), np.nan, dtype=float)
    shifted_cache = {}
    for i in range(len(obs)):
        key = i
        shifted_pred = shifted_cache.get(key)
        if shifted_pred is None:
            shifted_pred = np.vstack([shifted(pred[i], s) for s in grid])
            shifted_cache[key] = shifted_pred
        valid = np.isfinite(shifted_pred) & np.isfinite(obs[i][None, :])
        denom = valid.sum(axis=1)
        ok = denom > 0
        if ok.any():
            diff2 = (np.nan_to_num(shifted_pred, nan=0.0) - np.nan_to_num(obs[i][None, :], nan=0.0)) ** 2
            mse = np.full(len(grid), np.inf, dtype=float)
            mse[ok] = diff2[ok].sum(axis=1) / denom[ok]
            out[i] = float(grid[int(np.argmin(mse))] * period)
    return out


def sigma68(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def summarize_by_run(table: pd.DataFrame, eval_idx: np.ndarray, metrics: Dict[str, Dict[str, np.ndarray]]) -> pd.DataFrame:
    rows = []
    runs = table.iloc[eval_idx]["run"].to_numpy(dtype=int)
    for run in sorted(np.unique(runs)):
        mask = runs == int(run)
        row = {"run": int(run), "n_eval": int(mask.sum())}
        for method, vals in metrics.items():
            row[f"{method}_q_mse"] = float(np.nanmean(vals["q_mse"][mask]))
            row[f"{method}_live10_abs_ns"] = float(np.nanmean(np.abs(vals["live10_resid_ns"][mask])))
            row[f"{method}_tail_abs"] = float(np.nanmean(np.abs(vals["tail_resid"][mask])))
            row[f"{method}_timing_sigma68_ns"] = sigma68(vals["timing_resid_ns"][mask])
            row[f"{method}_timing_rms_ns"] = float(np.sqrt(np.nanmean(vals["timing_resid_ns"][mask] ** 2)))
            if "fallback" in vals:
                row[f"{method}_fallback_rate"] = float(np.mean(np.asarray(vals["fallback"], dtype=bool)[mask]))
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_summary(run_df: pd.DataFrame, fold: str, rng: np.random.Generator, reps: int) -> dict:
    cols = [c for c in run_df.columns if c not in {"run", "n_eval"}]
    matrix = run_df[cols].to_numpy(dtype=float)
    boots = []
    for _ in range(reps):
        boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
    boots = np.asarray(boots)
    out = {"fold": fold, "runs": [int(v) for v in run_df["run"]], "n_eval": int(run_df["n_eval"].sum())}
    means = matrix.mean(axis=0)
    for i, col in enumerate(cols):
        out[col] = float(means[i])
        out[f"{col}_ci"] = np.nanquantile(boots[:, i], [0.025, 0.975]).tolist()
    for metric in ["q_mse", "live10_abs_ns", "tail_abs", "timing_sigma68_ns", "timing_rms_ns"]:
        for ml in ["ridge", "extra_trees"]:
            a = f"{ml}_{metric}"
            b = f"handle_residual_{metric}"
            if a in run_df and b in run_df:
                delta = run_df[a].to_numpy(dtype=float) - run_df[b].to_numpy(dtype=float)
                db = [delta[rng.integers(0, len(delta), len(delta))].mean() for _ in range(reps)]
                out[f"delta_{ml}_minus_handle_{metric}"] = float(np.nanmean(delta))
                out[f"delta_{ml}_minus_handle_{metric}_ci"] = np.nanquantile(db, [0.025, 0.975]).tolist()
        a = f"handle_residual_{metric}"
        b = f"s01_empirical_{metric}"
        if a in run_df and b in run_df:
            delta = run_df[a].to_numpy(dtype=float) - run_df[b].to_numpy(dtype=float)
            db = [delta[rng.integers(0, len(delta), len(delta))].mean() for _ in range(reps)]
            out[f"delta_handle_minus_s01_{metric}"] = float(np.nanmean(delta))
            out[f"delta_handle_minus_s01_{metric}_ci"] = np.nanquantile(db, [0.025, 0.975]).tolist()
    return out


def support_map(table: pd.DataFrame, eval_idx: np.ndarray, metrics: Dict[str, Dict[str, np.ndarray]], fold: str, min_n: int) -> pd.DataFrame:
    local = table.iloc[eval_idx].copy()
    for method, vals in metrics.items():
        local[f"{method}_q_mse"] = vals["q_mse"]
        local[f"{method}_timing_abs_ns"] = np.abs(vals["timing_resid_ns"])
    rows = []
    keys = ["amp_region", "stave", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family", "run_family"]
    for key, sub in local.groupby(keys, observed=True):
        if len(sub) < min_n:
            continue
        row = {"fold": fold, "n_eval": int(len(sub))}
        row.update({col: str(value) for col, value in zip(keys, key)})
        for method in ["s01_empirical", "handle_residual", "ridge", "extra_trees", "shuffled_target_extra_trees", "family_label_sentinel"]:
            row[f"{method}_q_mse"] = float(np.nanmean(sub[f"{method}_q_mse"]))
            row[f"{method}_timing_abs_ns"] = float(np.nanmean(sub[f"{method}_timing_abs_ns"]))
        row["delta_handle_minus_s01_q_mse"] = row["handle_residual_q_mse"] - row["s01_empirical_q_mse"]
        row["delta_extra_trees_minus_handle_q_mse"] = row["extra_trees_q_mse"] - row["handle_residual_q_mse"]
        row["delta_extra_trees_minus_handle_timing_abs_ns"] = row["extra_trees_timing_abs_ns"] - row["handle_residual_timing_abs_ns"]
        row["support_call"] = (
            "handles_win" if row["delta_handle_minus_s01_q_mse"] < 0 else "s01_wins_or_ties"
        )
        rows.append(row)
    return pd.DataFrame(rows)


def region_summary(support: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dims = ["amp_region", "stave", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region", "current_family", "run_family"]
    for dim in dims:
        for value, sub in support.groupby(dim, observed=True):
            rows.append(
                {
                    "dimension": dim,
                    "region": str(value),
                    "n_cells": int(len(sub)),
                    "n_eval": int(sub["n_eval"].sum()),
                    "mean_delta_handle_minus_s01_q_mse": float(np.average(sub["delta_handle_minus_s01_q_mse"], weights=sub["n_eval"])),
                    "mean_delta_extra_trees_minus_handle_q_mse": float(np.average(sub["delta_extra_trees_minus_handle_q_mse"], weights=sub["n_eval"])),
                    "mean_delta_extra_trees_minus_handle_timing_abs_ns": float(np.average(sub["delta_extra_trees_minus_handle_timing_abs_ns"], weights=sub["n_eval"])),
                    "handle_win_cell_fraction": float(np.mean(sub["delta_handle_minus_s01_q_mse"] < 0)),
                    "extra_trees_q_win_cell_fraction": float(np.mean(sub["delta_extra_trees_minus_handle_q_mse"] < 0)),
                }
            )
    return pd.DataFrame(rows)


def input_sha(config: dict, out_dir: Path) -> List[dict]:
    rows = []
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        for run in p10a.configured_runs(config):
            path = p10a.raw_file(config, run)
            item = {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            writer.writerow(item)
            rows.append(item)
    return rows


def leakage_rows(config: dict, table: pd.DataFrame, fold_cfg: dict, summary: dict) -> dict:
    train_mask = table["group"].to_numpy() == fold_cfg["train_group"]
    eval_mask = table["group"].to_numpy() == fold_cfg["eval_group"]
    key_cols = ["run", "eventno", "evt", "stave"]
    train_keys = set(map(tuple, table.loc[train_mask, key_cols].to_numpy()))
    eval_keys = set(map(tuple, table.loc[eval_mask, key_cols].to_numpy()))
    et_win_ci = summary.get("delta_extra_trees_minus_handle_q_mse_ci", [math.nan, math.nan])
    shuffled = summary.get("shuffled_target_extra_trees_q_mse", math.nan)
    real = summary.get("extra_trees_q_mse", math.nan)
    sentinel = summary.get("family_label_sentinel_q_mse", math.nan)
    return {
        "fold": fold_cfg["name"],
        "train_eval_run_overlap": sorted(set(table.loc[train_mask, "run"].astype(int)) & set(table.loc[eval_mask, "run"].astype(int))),
        "train_eval_key_overlap": int(len(train_keys & eval_keys)),
        "uses_run_or_event_features": False,
        "extra_trees_beats_handle_q_ci": bool(np.isfinite(et_win_ci[1]) and et_win_ci[1] < 0),
        "shuffled_target_beats_real": bool(np.isfinite(shuffled) and np.isfinite(real) and shuffled < real),
        "family_label_sentinel_beats_real": bool(np.isfinite(sentinel) and np.isfinite(real) and sentinel < real),
        "leakage_alarm": bool((np.isfinite(shuffled) and np.isfinite(real) and shuffled < real) or (np.isfinite(sentinel) and np.isfinite(real) and sentinel < real)),
    }


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, fold_df: pd.DataFrame, leakage: pd.DataFrame, regions: pd.DataFrame, result: dict) -> None:
    best = regions.sort_values("mean_delta_handle_minus_s01_q_mse").head(8)
    worst = regions.sort_values("mean_delta_handle_minus_s01_q_mse", ascending=False).head(8)
    lines = [
        "# P10h: Explicit-handle q-template support map",
        "",
        f"- **Ticket ID:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        "- **Monte Carlo:** none",
        "",
        "## Raw reproduction first",
        "",
        "The selected B-stave pulse table was rebuilt from raw `HRDv` waveforms before any modeling.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Split: run-family holdout. `holdout_sample_i` trains on run 64 and evaluates runs 44-57; `holdout_sample_ii` trains on runs 31-42 and evaluates runs 58-63 and 65. CIs bootstrap held-out runs.",
        "",
        "Traditional method: frozen S01 empirical stave/amplitude-bin median templates plus train-only explicit-handle median residual tables. Handle bins below occupancy fall back to a looser handle table or the S01 template.",
        "",
        "ML method: ridge and ExtraTrees multi-output template predictors using local explicit handles only. Grouped knockouts remove amplitude, shape, stave, or current-family handles. Shuffled-target and family-label sentinel models are evaluated on the same held-out rows. Monotonic constraints were not available in the local scikit-learn version used by this repo.",
        "",
        "Metrics: q-template MSE, absolute live10 residual, absolute tail-sum residual, template-fit timing sigma68, and full timing RMS.",
        "",
        "## Fold Summary",
        "",
        fold_df[
            [
                "fold",
                "n_eval",
                "s01_empirical_q_mse",
                "handle_residual_q_mse",
                "extra_trees_q_mse",
                "delta_handle_minus_s01_q_mse",
                "delta_handle_minus_s01_q_mse_ci",
                "delta_extra_trees_minus_handle_q_mse",
                "delta_extra_trees_minus_handle_q_mse_ci",
                "handle_residual_fallback_rate",
                "extra_trees_timing_sigma68_ns",
                "delta_extra_trees_minus_handle_timing_sigma68_ns",
            ]
        ].to_markdown(index=False),
        "",
        "## Support Regions",
        "",
        "Most handle-favorable region summaries by weighted q-template MSE delta:",
        "",
        best.to_markdown(index=False),
        "",
        "Least handle-favorable region summaries:",
        "",
        worst.to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        leakage.to_markdown(index=False),
        "",
        "A result is treated as too-good only when the ML-minus-traditional q-template CI is wholly below zero. In this run, sentinel alarms are reported in `leakage_checks.csv`; any fold with a shuffled-target or family-label sentinel beating the real model is not promotable as a physics support claim.",
        "",
        "## Finding",
        "",
        result["conclusion"],
        "",
        "Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `fold_run_metrics.csv`, `fold_summary.csv`, `support_map.csv`, `support_region_summary.csv`, `model_diagnostics.csv`, `handle_occupancy.csv`, and `leakage_checks.csv`.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p10h_1781026226_557_2d8e79db_support_map.py --config configs/p10h_1781026226_557_2d8e79db_support_map.yaml",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10h_1781026226_557_2d8e79db_support_map.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    table0, aligned, norm = p10a.collect_selected(config)
    table = add_handle_strata(config, table0, aligned, norm)
    analysis_rows = int(table["group"].str.endswith("_analysis").sum())
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "analysis selected rows",
                "expected": int(config["expected_analysis_rows"]),
                "reproduced": analysis_rows,
                "delta": int(analysis_rows - int(config["expected_analysis_rows"])),
                "pass": bool(analysis_rows == int(config["expected_analysis_rows"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    fold_runs, fold_summaries, support_parts, diag_parts, occ_parts, leakage_parts = [], [], [], [], [], []
    for fold_cfg in config["family_folds"]:
        train_mask = table["group"].to_numpy() == fold_cfg["train_group"]
        eval_mask = table["group"].to_numpy() == fold_cfg["eval_group"]
        train_idx = select_capped_indices(
            table,
            train_mask,
            ["run", "stave", "amp_region", "rise_width_region", "tail_shape_region", "saturation_region"],
            cap=80,
            max_total=int(config["max_train_rows_per_fold"]),
            rng=rng,
        )
        eval_idx = select_capped_indices(
            table,
            eval_mask,
            ["run", "stave", "amp_region", "rise_width_region", "cfd_phase_region", "tail_shape_region", "saturation_region"],
            cap=int(config["max_eval_per_run_support"]),
            max_total=int(config["max_eval_rows_per_fold"]),
            rng=rng,
        )

        s01_pack, _ = p10a.build_empirical_templates(config, table, aligned, train_mask)
        s01_train = predict_empirical(table, aligned, s01_pack, train_idx)
        s01_eval = predict_empirical(table, aligned, s01_pack, eval_idx)
        handle_pack, occ = build_handle_residuals(config, table, aligned, train_idx, s01_train)
        handle_eval, handle_sources = predict_handles(table, eval_idx, s01_eval, handle_pack)
        occ["fold"] = fold_cfg["name"]
        occ_parts.append(occ)
        ml_pred, diag = fit_ml_predictions(config, table, aligned, train_idx, eval_idx, rng)
        diag["fold"] = fold_cfg["name"]
        diag_parts.append(diag)

        predictions = {"s01_empirical": s01_eval, "handle_residual": handle_eval}
        predictions.update(ml_pred)
        obs_stats = waveform_live10_tail(aligned[eval_idx], config)
        metrics = {}
        for method, pred in predictions.items():
            pred_stats = waveform_live10_tail(pred, config)
            metrics[method] = {
                "q_mse": mse_to_prediction(aligned[eval_idx], pred),
                "live10_resid_ns": pred_stats["live10_ns"].to_numpy(dtype=float) - obs_stats["live10_ns"].to_numpy(dtype=float),
                "tail_resid": pred_stats["tail_sum"].to_numpy(dtype=float) - obs_stats["tail_sum"].to_numpy(dtype=float),
                "timing_resid_ns": timing_fit_residual_ns(aligned[eval_idx], pred, config),
            }
        metrics["handle_residual"]["fallback"] = np.asarray([src == "s01_fallback" for src in handle_sources], dtype=bool)

        run_df = summarize_by_run(table, eval_idx, metrics)
        run_df["fold"] = fold_cfg["name"]
        fold_runs.append(run_df)
        summary = bootstrap_summary(run_df.drop(columns=["fold"]), fold_cfg["name"], rng, int(config["bootstrap_iterations"]))
        summary["train_group"] = fold_cfg["train_group"]
        summary["eval_group"] = fold_cfg["eval_group"]
        summary["train_rows_used"] = int(len(train_idx))
        fold_summaries.append(summary)
        support_parts.append(support_map(table, eval_idx, metrics, fold_cfg["name"], int(config["support_min_eval_pulses"])))
        leakage_parts.append(leakage_rows(config, table, fold_cfg, summary))

    run_df = pd.concat(fold_runs, ignore_index=True)
    fold_df = pd.DataFrame(fold_summaries)
    support_df = pd.concat(support_parts, ignore_index=True)
    regions = region_summary(support_df)
    diag_df = pd.concat(diag_parts, ignore_index=True)
    occ_df = pd.concat(occ_parts, ignore_index=True)
    leakage = pd.DataFrame(leakage_parts)

    run_df.to_csv(out_dir / "fold_run_metrics.csv", index=False)
    fold_df.to_csv(out_dir / "fold_summary.csv", index=False)
    support_df.to_csv(out_dir / "support_map.csv", index=False)
    regions.to_csv(out_dir / "support_region_summary.csv", index=False)
    diag_df.to_csv(out_dir / "model_diagnostics.csv", index=False)
    occ_df.to_csv(out_dir / "handle_occupancy.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    inputs = input_sha(config, out_dir)

    promotable_folds = int((~leakage["leakage_alarm"]).sum())
    handles_help = bool((fold_df["delta_handle_minus_s01_q_mse_ci"].apply(lambda v: v[1]) < 0).any())
    et_help = bool((fold_df["delta_extra_trees_minus_handle_q_mse_ci"].apply(lambda v: v[1]) < 0).any())
    conclusion = (
        "Explicit handle residuals have limited promotable support: at least one fold improves over S01 by q-template CI, but support is region-specific."
        if handles_help
        else "Explicit handle residuals do not produce a fold-level q-template CI win over frozen S01; any gains are local support-map effects."
    )
    if et_help:
        conclusion += " ExtraTrees beats the traditional handle method in at least one fold, subject to the sentinel audit."
    else:
        conclusion += " ExtraTrees does not beat the traditional handle method at fold level."

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction": {"passed": bool(repro["pass"].all()), "selected_b_stave_pulses": int(len(table)), "analysis_selected_rows": analysis_rows},
        "split": "run-family holdout with held-out run bootstrap CIs",
        "traditional": "S01 empirical amplitude-bin templates plus train-only explicit-handle residual medians",
        "ml": "ridge and ExtraTrees explicit-handle multi-output template predictors with grouped knockouts",
        "metrics": ["q_template_mse", "live10_abs_residual_ns", "tail_abs_residual", "timing_fit_sigma68_ns", "timing_fit_full_rms_ns", "fallback_rate"],
        "folds": fold_summaries,
        "leakage": leakage_parts,
        "promotable_folds_without_sentinel_alarm": promotable_folds,
        "conclusion": conclusion,
        "git_commit": git_commit(),
        "input_sha256": "input_sha256.csv",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro, fold_df, leakage, regions, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": f"/home/billy/anaconda3/bin/python scripts/p10h_1781026226_557_2d8e79db_support_map.py --config {config_path}",
        "script": "scripts/p10h_1781026226_557_2d8e79db_support_map.py",
        "script_sha256": sha256_file(Path("scripts/p10h_1781026226_557_2d8e79db_support_map.py")),
        "support_script": "scripts/p10a_conditional_template.py",
        "support_script_sha256": sha256_file(Path("scripts/p10a_conditional_template.py")),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(time.time() - t0, 1),
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
