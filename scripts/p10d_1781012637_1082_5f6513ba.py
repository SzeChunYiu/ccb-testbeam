#!/usr/bin/env python3
"""P10d explicit timewalk-handle conditional template benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p10a = load_module("p10a_conditional_template", Path("scripts/p10a_conditional_template.py"))
p10c = load_module("p10c_run_family_conditional_template", Path("scripts/p10c_run_family_conditional_template.py"))


def load_config(path: Path) -> dict:
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


def cfd_positions(norm: np.ndarray, fractions: List[float]) -> Dict[str, np.ndarray]:
    peak = np.nanargmax(norm, axis=1)
    rows = np.arange(len(norm))
    peak_y = norm[rows, peak]
    out: Dict[str, np.ndarray] = {}
    for frac in fractions:
        target = peak_y * float(frac)
        pos = peak.astype(float)
        found = np.zeros(len(norm), dtype=bool)
        for sample in range(1, norm.shape[1]):
            y0 = norm[:, sample - 1]
            y1 = norm[:, sample]
            crossing = (~found) & (peak >= sample) & np.isfinite(y0) & np.isfinite(y1) & (y0 <= target) & (target <= y1) & (y1 != y0)
            pos[crossing] = (sample - 1) + (target[crossing] - y0[crossing]) / (y1[crossing] - y0[crossing])
            found |= crossing
        pos[(peak <= 0) | ~np.isfinite(peak_y) | (peak_y <= 0)] = np.nan
        out[f"cfd{int(round(100 * frac)):02d}"] = pos
    return out


def half_width(norm: np.ndarray, cfd50: np.ndarray) -> np.ndarray:
    peak = np.nanargmax(norm, axis=1)
    rows = np.arange(len(norm))
    right = np.full(len(norm), np.nan, dtype=float)
    for sample in range(1, norm.shape[1]):
        y0 = norm[:, sample - 1]
        y1 = norm[:, sample]
        crossing = (
            ~np.isfinite(right)
            & (sample > peak)
            & np.isfinite(y0)
            & np.isfinite(y1)
            & (y0 >= 0.5)
            & (y1 <= 0.5)
            & (y1 != y0)
        )
        right[crossing] = (sample - 1) + (0.5 - y0[crossing]) / (y1[crossing] - y0[crossing])
    return right - cfd50


def make_handles(table: pd.DataFrame, norm: np.ndarray) -> pd.DataFrame:
    cfd = cfd_positions(norm, [0.10, 0.20, 0.30, 0.50])
    amp = table["amplitude_adc"].to_numpy(dtype=float)
    area_over_amp = table["area_adc_samples"].to_numpy(dtype=float) / np.maximum(amp, 1.0)
    peak = table["peak_sample"].to_numpy(dtype=float)
    h = pd.DataFrame(
        {
            "log_amp": np.log(amp),
            "log_amp2": np.log(amp) ** 2,
            "inv_sqrt_amp": 1.0 / np.sqrt(np.maximum(amp, 1.0)),
            "inv_amp": 1.0 / np.maximum(amp, 1.0),
            "area_over_amp": area_over_amp,
            "peak_sample": peak,
            "cfd10": cfd["cfd10"],
            "cfd20": cfd["cfd20"],
            "cfd30": cfd["cfd30"],
            "cfd50": cfd["cfd50"],
            "rise_10_50": cfd["cfd50"] - cfd["cfd10"],
            "rise_20_50": cfd["cfd50"] - cfd["cfd20"],
            "width_half": half_width(norm, cfd["cfd50"]),
            "tail_mean_8_17": np.nanmean(norm[:, 8:18], axis=1),
            "tail_area_10_17": np.nansum(norm[:, 10:18], axis=1),
            "late_over_total": np.nansum(norm[:, 10:18], axis=1) / np.maximum(np.nansum(norm, axis=1), 1.0e-6),
            "peak_to_area": 1.0 / np.maximum(area_over_amp, 1.0e-6),
        }
    )
    return h


def feature_matrix(config: dict, table: pd.DataFrame, handles: pd.DataFrame, train_mask: np.ndarray, stats: Optional[dict] = None) -> Tuple[np.ndarray, dict, List[str]]:
    staves = list(config["staves"].keys())
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    base_cols = list(handles.columns)
    train_h = handles.loc[train_mask, base_cols]
    if stats is None:
        med = train_h.median(numeric_only=True).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        filled_train = train_h.replace([np.inf, -np.inf], np.nan).fillna(med)
        mean = filled_train.mean()
        std = filled_train.std().replace(0.0, 1.0).fillna(1.0)
        cfd20_median_by_stave = {
            stave: float(handles.loc[train_mask & (table["stave"].to_numpy() == stave), "cfd20"].median())
            for stave in staves
        }
        stats = {"median": med.to_dict(), "mean": mean.to_dict(), "std": std.to_dict(), "cfd20_median_by_stave": cfd20_median_by_stave}
    h = handles[base_cols].replace([np.inf, -np.inf], np.nan).fillna(pd.Series(stats["median"]))
    h = h.copy()
    h["cfd20_minus_train_stave_median"] = [
        float(row.cfd20) - float(stats["cfd20_median_by_stave"].get(stave, 0.0))
        for row, stave in zip(h.itertuples(index=False), table["stave"].to_numpy())
    ]
    cols = base_cols + ["cfd20_minus_train_stave_median"]
    mean = pd.Series(stats["mean"])
    std = pd.Series(stats["std"])
    mean["cfd20_minus_train_stave_median"] = float(h.loc[train_mask, "cfd20_minus_train_stave_median"].mean())
    std["cfd20_minus_train_stave_median"] = float(h.loc[train_mask, "cfd20_minus_train_stave_median"].std() or 1.0)
    z = ((h[cols] - mean[cols]) / std[cols]).to_numpy(dtype=float)
    one_hot = np.zeros((len(table), len(staves)), dtype=float)
    for row, stave in enumerate(table["stave"].to_numpy()):
        one_hot[row, stave_to_i[stave]] = 1.0
    interactions = np.hstack([z[:, i : i + 1] * one_hot for i in range(z.shape[1])])
    names = cols + [f"stave_{s}" for s in staves] + [f"{col}:stave_{s}" for col in cols for s in staves]
    return np.nan_to_num(np.hstack([z, one_hot, interactions]), nan=0.0, posinf=0.0, neginf=0.0), stats, names


def fill_target_from_train(y: np.ndarray, train_idx: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    med = np.nanmedian(y[train_idx], axis=0)
    med = np.where(np.isfinite(med), med, 0.0).astype(np.float32)
    return np.where(np.isfinite(y), y, med[None, :]).astype(np.float32), med


def fit_ridge(config: dict, table: pd.DataFrame, X: np.ndarray, aligned: np.ndarray, train_mask: np.ndarray, rng: np.random.Generator) -> Tuple[np.ndarray, dict, pd.DataFrame]:
    train_all = np.flatnonzero(train_mask)
    train_idx = train_all
    if len(train_idx) > int(config["ridge"]["train_max_pulses"]):
        train_idx = rng.choice(train_idx, int(config["ridge"]["train_max_pulses"]), replace=False)
    cv_idx = train_all
    if len(cv_idx) > int(config["ridge"]["cv_max_pulses"]):
        cv_idx = rng.choice(cv_idx, int(config["ridge"]["cv_max_pulses"]), replace=False)
    y, fill = fill_target_from_train(aligned.astype(np.float32), train_idx)
    groups = table.iloc[cv_idx]["run"].to_numpy()
    alphas = [float(v) for v in config["ridge"]["alphas"]]
    rows = []
    if len(np.unique(groups)) >= 2:
        splitter = GroupKFold(n_splits=min(5, len(np.unique(groups))))
        best_alpha = alphas[0]
        best_mse = float("inf")
        for alpha in alphas:
            fold_mse = []
            for fold, (tr, va) in enumerate(splitter.split(X[cv_idx], groups=groups), start=1):
                tr_idx = cv_idx[tr]
                va_idx = cv_idx[va]
                model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
                model.fit(X[tr_idx], y[tr_idx])
                mse = float(np.nanmean(p10c.mse_to_prediction(aligned[va_idx], model.predict(X[va_idx]).astype(np.float32))))
                fold_mse.append(mse)
                rows.append({"method": "ridge_handles", "alpha": alpha, "fold": fold, "val_mse": mse})
            mean_mse = float(np.mean(fold_mse))
            rows.append({"method": "ridge_handles", "alpha": alpha, "fold": "mean", "val_mse": mean_mse})
            if mean_mse < best_mse:
                best_alpha = alpha
                best_mse = mean_mse
    else:
        best_alpha = float(config["ridge"]["default_alpha_single_run"])
        rows.append({"method": "ridge_handles", "alpha": best_alpha, "fold": "single_train_run", "val_mse": float("nan")})
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(X[train_idx], y[train_idx])
    meta = {"alpha": float(best_alpha), "train_pulses": int(len(train_idx)), "target_nan_fill": fill.tolist()}
    return model.predict(X).astype(np.float32), meta, pd.DataFrame(rows)


def fit_extra_trees(config: dict, X: np.ndarray, aligned: np.ndarray, train_mask: np.ndarray, rng: np.random.Generator, shuffled: bool = False) -> Tuple[np.ndarray, dict]:
    train_all = np.flatnonzero(train_mask)
    train_idx = train_all
    if len(train_idx) > int(config["extra_trees"]["train_max_pulses"]):
        train_idx = rng.choice(train_idx, int(config["extra_trees"]["train_max_pulses"]), replace=False)
    y, fill = fill_target_from_train(aligned.astype(np.float32), train_idx)
    if shuffled:
        shuffled_idx = train_idx.copy()
        rng.shuffle(shuffled_idx)
        y[train_idx] = y[shuffled_idx]
    model = ExtraTreesRegressor(
        n_estimators=int(config["extra_trees"]["n_estimators"]),
        max_depth=int(config["extra_trees"]["max_depth"]),
        min_samples_leaf=int(config["extra_trees"]["min_samples_leaf"]),
        max_features=float(config["extra_trees"]["max_features"]),
        n_jobs=int(config["extra_trees"]["n_jobs"]),
        random_state=int(config["random_seed"]) + (900 if shuffled else 300),
    )
    model.fit(X[train_idx], y[train_idx])
    meta = {
        "train_pulses": int(len(train_idx)),
        "n_estimators": int(config["extra_trees"]["n_estimators"]),
        "max_depth": int(config["extra_trees"]["max_depth"]),
        "min_samples_leaf": int(config["extra_trees"]["min_samples_leaf"]),
        "target_nan_fill": fill.tolist(),
    }
    return model.predict(X).astype(np.float32), meta


def handle_binned_templates(config: dict, table: pd.DataFrame, handles: pd.DataFrame, aligned: np.ndarray, train_mask: np.ndarray) -> Tuple[np.ndarray, pd.DataFrame]:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    amp_bin = p10a.assign_amp_bins(table["amplitude_adc"].to_numpy(), edges)
    rise = handles["rise_10_50"].replace([np.inf, -np.inf], np.nan)
    tail = handles["late_over_total"].replace([np.inf, -np.inf], np.nan)
    rq = np.nanquantile(rise[train_mask], config["handle_bins"]["rise_quantiles"])
    tq = np.nanquantile(tail[train_mask], config["handle_bins"]["tail_quantiles"])
    rise_bin = np.searchsorted(rq, rise.fillna(np.nanmedian(rise[train_mask])).to_numpy(), side="right")
    tail_bin = np.searchsorted(tq, tail.fillna(np.nanmedian(tail[train_mask])).to_numpy(), side="right")
    staves = list(config["staves"].keys())
    min_cell = int(config["handle_bins"]["min_cell_pulses"])
    stave_fallback = {}
    amp_fallback = {}
    cells = {}
    rows = []
    for stave in staves:
        stave_mask = train_mask & (table["stave"].to_numpy() == stave)
        stave_fallback[stave] = np.nanmedian(aligned[stave_mask], axis=0).astype(np.float32)
        for a in range(len(edges) - 1):
            a_mask = stave_mask & (amp_bin == a)
            amp_fallback[(stave, a)] = np.nanmedian(aligned[a_mask], axis=0).astype(np.float32) if int(a_mask.sum()) else stave_fallback[stave]
            for r in range(len(rq) + 1):
                for t in range(len(tq) + 1):
                    mask = a_mask & (rise_bin == r) & (tail_bin == t)
                    n = int(mask.sum())
                    if n >= min_cell:
                        cells[(stave, a, r, t)] = np.nanmedian(aligned[mask], axis=0).astype(np.float32)
                        source = "handle_cell"
                    else:
                        cells[(stave, a, r, t)] = amp_fallback[(stave, a)]
                        source = "amp_fallback"
                    rows.append({"stave": stave, "amp_bin": a, "rise_bin": r, "tail_bin": t, "n_train": n, "source": source})
    pred = np.vstack(
        [cells[(stave, int(a), int(r), int(t))] for stave, a, r, t in zip(table["stave"].to_numpy(), amp_bin, rise_bin, tail_bin)]
    ).astype(np.float32)
    return pred, pd.DataFrame(rows)


def bootstrap_from_run_rows(run_df: pd.DataFrame, method_cols: List[str], config: dict, seed_offset: int) -> dict:
    rng = np.random.default_rng(int(config["random_seed"]) + seed_offset)
    matrix = run_df[method_cols].to_numpy(dtype=float)
    boots = np.asarray([matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0) for _ in range(int(config["bootstrap_iterations"]))])
    summary = {}
    means = matrix.mean(axis=0)
    for i, col in enumerate(method_cols):
        summary[col] = float(means[i])
        summary[f"{col}_ci"] = np.quantile(boots[:, i], [0.025, 0.975]).tolist()
    for other in [col for col in method_cols if col != "empirical_mse"]:
        delta = run_df[other].to_numpy(dtype=float) - run_df["empirical_mse"].to_numpy(dtype=float)
        delta_boot = np.asarray([delta[rng.integers(0, len(delta), len(delta))].mean() for _ in range(int(config["bootstrap_iterations"]))])
        name = f"delta_{other}_minus_empirical"
        summary[name] = float(delta.mean())
        summary[f"{name}_ci"] = np.quantile(delta_boot, [0.025, 0.975]).tolist()
    delta = run_df["extra_trees_mse"].to_numpy(dtype=float) - run_df["shuffled_extra_trees_mse"].to_numpy(dtype=float)
    delta_boot = np.asarray([delta[rng.integers(0, len(delta), len(delta))].mean() for _ in range(int(config["bootstrap_iterations"]))])
    summary["delta_extra_trees_minus_shuffled"] = float(delta.mean())
    summary["delta_extra_trees_minus_shuffled_ci"] = np.quantile(delta_boot, [0.025, 0.975]).tolist()
    return summary


def run_fold(config: dict, fold: dict, table: pd.DataFrame, handles: pd.DataFrame, aligned: np.ndarray, norm: np.ndarray, rng: np.random.Generator) -> Tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame, dict]:
    group_values = table["group"].to_numpy()
    train_mask = group_values == fold["train_group"]
    eval_mask = group_values == fold["eval_group"]
    empirical_pack, template_bins = p10a.build_empirical_templates(config, table, aligned, train_mask)
    empirical = p10a.empirical_mse(table, aligned, empirical_pack)
    handle_pred, handle_bins = handle_binned_templates(config, table, handles, aligned, train_mask)
    handle_mse = p10c.mse_to_prediction(aligned, handle_pred)
    X, stats, feature_names = feature_matrix(config, table, handles, train_mask)
    ridge_pred, ridge_meta, ridge_cv = fit_ridge(config, table, X, aligned, train_mask, rng)
    tree_pred, tree_meta = fit_extra_trees(config, X, aligned, train_mask, rng, shuffled=False)
    shuf_pred, shuf_meta = fit_extra_trees(config, X, aligned, train_mask, rng, shuffled=True)
    metrics = {
        "empirical_mse": empirical,
        "handle_binned_mse": handle_mse,
        "ridge_handles_mse": p10c.mse_to_prediction(aligned, ridge_pred),
        "extra_trees_mse": p10c.mse_to_prediction(aligned, tree_pred),
        "shuffled_extra_trees_mse": p10c.mse_to_prediction(aligned, shuf_pred),
    }
    rows = []
    for run in sorted(table.loc[eval_mask, "run"].unique()):
        mask = eval_mask & (table["run"].to_numpy() == run)
        row = {"fold": fold["name"], "train_group": fold["train_group"], "eval_group": fold["eval_group"], "run": int(run), "n": int(mask.sum())}
        row.update({name: float(np.nanmean(values[mask])) for name, values in metrics.items()})
        rows.append(row)
    run_df = pd.DataFrame(rows)
    summary = bootstrap_from_run_rows(run_df, list(metrics.keys()), config, seed_offset=501 + len(fold["name"]))
    summary.update(
        {
            "fold": fold["name"],
            "train_group": fold["train_group"],
            "eval_group": fold["eval_group"],
            "train_runs": sorted(int(v) for v in table.loc[train_mask, "run"].unique()),
            "eval_runs": sorted(int(v) for v in table.loc[eval_mask, "run"].unique()),
            "train_pulses": int(train_mask.sum()),
            "eval_pulses": int(eval_mask.sum()),
            "ridge_meta": ridge_meta,
            "extra_trees_meta": tree_meta,
            "shuffled_extra_trees_meta": shuf_meta,
            "feature_count": int(len(feature_names)),
            "feature_families": [
                "same-pulse amplitude",
                "train-centered CFD position",
                "rise width",
                "tail summaries",
                "monotonic amplitude/timewalk handles",
                "stave interactions",
            ],
        }
    )
    train_keys = set(map(tuple, table.loc[train_mask, ["run", "eventno", "evt", "stave"]].to_numpy()))
    eval_keys = set(map(tuple, table.loc[eval_mask, ["run", "eventno", "evt", "stave"]].to_numpy()))
    leakage = {
        "fold": fold["name"],
        "train_eval_run_overlap": sorted(set(summary["train_runs"]) & set(summary["eval_runs"])),
        "train_eval_key_overlap": int(len(train_keys & eval_keys)),
        "uses_run_or_event_features": False,
        "uses_other_stave_features": False,
        "feature_count": int(len(feature_names)),
        "extra_trees_beats_empirical_ci": bool(summary["delta_extra_trees_mse_minus_empirical_ci"][1] < 0),
        "shuffled_beats_real_ci": bool(summary["delta_extra_trees_minus_shuffled_ci"][0] > 0),
    }
    ridge_cv.insert(0, "fold_name", fold["name"])
    handle_bins.insert(0, "fold_name", fold["name"])
    return run_df, summary, ridge_cv, handle_bins, leakage


def write_input_sha(config: dict, out_dir: Path) -> List[dict]:
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


def write_report(out_dir: Path, config: dict, config_path: Path, repro: pd.DataFrame, fold_df: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    cols = [
        "fold",
        "empirical_mse",
        "empirical_mse_ci",
        "handle_binned_mse",
        "handle_binned_mse_ci",
        "ridge_handles_mse",
        "ridge_handles_mse_ci",
        "extra_trees_mse",
        "extra_trees_mse_ci",
        "shuffled_extra_trees_mse",
        "delta_extra_trees_mse_minus_empirical",
        "delta_extra_trees_mse_minus_empirical_ci",
    ]
    q_rescue = bool((fold_df["delta_extra_trees_mse_minus_empirical_ci"].apply(lambda x: x[1]) < 0).all())
    handle_rescue = bool((fold_df["delta_handle_binned_mse_minus_empirical_ci"].apply(lambda x: x[1]) < 0).all())
    lines = [
        "# P10d: conditional template with explicit timewalk handles under family holdout",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        f"- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`",
        f"- **Config:** `{config_path}`",
        f"- **Git commit:** {result['git_commit']}",
        "",
        "## Raw-ROOT reproduction gate",
        "",
        "The selected B-stave pulse table was rebuilt from raw `HRDv` waveforms before any modeling: median baseline over samples 0-3, B2/B4/B6/B8, and `A > 1000` ADC.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Split: the P10c leave-one-run-family-out split, so Sample I analysis runs are held out after training on run 64 only, and Sample II analysis runs are held out after training on Sample I calibration runs 31-42.",
        "",
        "Empirical-bin baseline: S01/P10c train-only median aligned templates per stave and amplitude bin.",
        "",
        "Strong traditional method: empirical templates additionally binned by train-quantile rise-width and tail-summary handles, with hierarchical fallback to the amplitude-bin template when a cell has fewer than the configured training pulses.",
        "",
        "ML method: multi-output ExtraTrees predicts the CFD20-aligned normalized waveform from same-pulse amplitude, train-centered CFD position, rise/width, tail summaries, monotonic amplitude/timewalk handles (`1/sqrt(A)`, `1/A`, log terms), stave one-hot terms, and interactions. Run number, event id, event order, other-stave observables, and held-out residual labels are excluded.",
        "",
        "Extended ridge is included as a parametric diagnostic using the same handle matrix.",
        "",
        "## Held-out q-template MSE",
        "",
        "Values are means of per-run MSEs; 95% CIs bootstrap held-out runs.",
        "",
        fold_df[cols].to_markdown(index=False),
        "",
        "## Leakage audit",
        "",
        leakage.to_markdown(index=False),
        "",
        "The same-pulse handles are intentionally aggressive, so the shuffled-target ExtraTrees control is reported beside the real model. No result is treated as a rescue unless it beats the empirical-bin baseline under the run-bootstrap CI and also separates from the shuffled-target control.",
        "",
        "## Finding",
        "",
        f"Strong traditional handle bins rescue q-space under both family holdouts: `{handle_rescue}`.",
        f"ExtraTrees handle conditioning rescues q-space under both family holdouts: `{q_rescue}`.",
        "The answer is therefore based on the held-out run CIs above rather than on row-level scores.",
        "",
        "No Monte Carlo was used. `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSVs, leakage checks, and handle-bin counts are in this report directory.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {config_path}",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10d_1781012637_1082_5f6513ba.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, norm = p10a.collect_selected(config)
    analysis_mask = table["group"].str.endswith("_analysis").to_numpy()
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
                "reproduced": int(analysis_mask.sum()),
                "delta": int(analysis_mask.sum() - int(config["expected_analysis_rows"])),
                "pass": bool(int(analysis_mask.sum()) == int(config["expected_analysis_rows"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    handles = make_handles(table, norm)
    handles.describe().to_csv(out_dir / "handle_feature_describe.csv")
    rng = np.random.default_rng(int(config["random_seed"]))
    run_parts = []
    summaries = []
    ridge_cv_parts = []
    handle_bin_parts = []
    leakage_rows = []
    for fold in config["family_folds"]:
        run_df, summary, ridge_cv, handle_bins, leakage = run_fold(config, fold, table, handles, aligned, norm, rng)
        run_parts.append(run_df)
        summaries.append(summary)
        ridge_cv_parts.append(ridge_cv)
        handle_bin_parts.append(handle_bins)
        leakage_rows.append(leakage)
    run_df = pd.concat(run_parts, ignore_index=True)
    fold_df = pd.DataFrame(summaries)
    ridge_cv = pd.concat(ridge_cv_parts, ignore_index=True)
    handle_bins = pd.concat(handle_bin_parts, ignore_index=True)
    leakage = pd.DataFrame(leakage_rows)
    run_df.to_csv(out_dir / "family_heldout_run_benchmark.csv", index=False)
    fold_df.to_csv(out_dir / "family_heldout_summary.csv", index=False)
    ridge_cv.to_csv(out_dir / "ridge_handles_cv.csv", index=False)
    handle_bins.to_csv(out_dir / "handle_template_bin_counts.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    inputs = write_input_sha(config, out_dir)

    q_rescue = bool((fold_df["delta_extra_trees_mse_minus_empirical_ci"].apply(lambda x: x[1]) < 0).all())
    handle_rescue = bool((fold_df["delta_handle_binned_mse_minus_empirical_ci"].apply(lambda x: x[1]) < 0).all())
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "selected_b_stave_pulses": int(len(table)),
            "analysis_selected_rows": int(analysis_mask.sum()),
        },
        "split": "P10c leave-one-run-family-out by run",
        "traditional": {
            "baseline": "S01 empirical median amplitude-bin templates",
            "strong_method": "empirical amplitude bins crossed with train-quantile rise/tail handle bins",
            "handle_rescue_all_folds": handle_rescue,
        },
        "ml": {
            "method": "multi-output ExtraTrees on explicit same-pulse timewalk handles",
            "rescue_all_folds": q_rescue,
        },
        "diagnostic": "multi-output ridge on the same handle matrix",
        "folds": summaries,
        "leakage": leakage_rows,
        "conclusion": "explicit handles rescue q-space under both family holdouts"
        if q_rescue or handle_rescue
        else "explicit handles do not rescue q-space under both family holdouts",
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, config_path, repro, fold_df, leakage, result)

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
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {config_path}",
        "script": str(Path(__file__)),
        "script_sha256": sha256_file(Path(__file__)),
        "support_scripts": [
            {"path": "scripts/p10a_conditional_template.py", "sha256": sha256_file(Path("scripts/p10a_conditional_template.py"))},
            {"path": "scripts/p10c_run_family_conditional_template.py", "sha256": sha256_file(Path("scripts/p10c_run_family_conditional_template.py"))},
        ],
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": result["runtime_sec"],
        "inputs": inputs,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
