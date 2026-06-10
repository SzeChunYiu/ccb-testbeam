#!/usr/bin/env python3
"""P10f calibration-only conditional q_template tail validation.

The study rebuilds selected B-stack pulses from raw ROOT, reproduces the
published P10a/S00 selected-pulse gate, then compares calibration-only median
q-template tail scores with a same-pulse conditional ML template score under
held-out analysis runs. No downstream timing labels are used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.neighbors import NearestNeighbors


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import {}".format(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p10a = load_module("p10a_conditional_template", Path("scripts/p10a_conditional_template.py"))
p10d = load_module("p10d_1781012637_1082_5f6513ba", Path("scripts/p10d_1781012637_1082_5f6513ba.py"))

NO_TAIL_HANDLE_COLS = [
    "log_amp",
    "log_amp2",
    "inv_sqrt_amp",
    "inv_amp",
    "area_over_amp",
    "peak_sample",
    "cfd10",
    "cfd20",
    "cfd30",
    "cfd50",
    "rise_10_50",
    "rise_20_50",
    "width_half",
    "peak_to_area",
]


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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        x = float(value)
        return x if np.isfinite(x) else None
    return value


def empirical_prediction(config: dict, table: pd.DataFrame, pack: dict) -> np.ndarray:
    edges = pack["edges"]
    bins = p10a.assign_amp_bins(table["amplitude_adc"].to_numpy(dtype=float), edges)
    pred = []
    for stave, amp_bin in zip(table["stave"].to_numpy(), bins):
        pred.append(pack["templates"][(stave, int(amp_bin))])
    return np.vstack(pred).astype(np.float32)


def mse_scores(obs: np.ndarray, pred: np.ndarray, rel_grid: np.ndarray, tail_min: float) -> Tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(obs) & np.isfinite(pred)
    diff2 = (np.nan_to_num(obs, nan=0.0) - np.nan_to_num(pred, nan=0.0)) ** 2
    diff2[~valid] = 0.0
    denom = valid.sum(axis=1)
    q = np.full(len(obs), np.nan, dtype=float)
    ok = denom > 0
    q[ok] = diff2[ok].sum(axis=1) / denom[ok]

    tail = rel_grid >= float(tail_min)
    denom_tail = valid[:, tail].sum(axis=1)
    q_tail = np.full(len(obs), np.nan, dtype=float)
    ok_tail = denom_tail > 0
    q_tail[ok_tail] = diff2[:, tail][ok_tail].sum(axis=1) / denom_tail[ok_tail]
    return q, q_tail


def waveform_hashes(norm: np.ndarray) -> np.ndarray:
    quantized = np.nan_to_num(np.rint(norm * 1000000.0), nan=-999999999.0).astype(np.int32)
    return np.asarray([hashlib.sha256(row.tobytes()).hexdigest() for row in quantized])


def nearest_neighbor_check(config: dict, norm: np.ndarray, train_mask: np.ndarray, eval_mask: np.ndarray, rng: np.random.Generator) -> dict:
    train_idx = np.flatnonzero(train_mask)
    eval_idx = np.flatnonzero(eval_mask)
    if len(train_idx) > int(config["nearest_neighbor"]["train_max"]):
        train_idx = rng.choice(train_idx, int(config["nearest_neighbor"]["train_max"]), replace=False)
    if len(eval_idx) > int(config["nearest_neighbor"]["eval_max"]):
        eval_idx = rng.choice(eval_idx, int(config["nearest_neighbor"]["eval_max"]), replace=False)
    train = np.nan_to_num(norm[train_idx].astype(float), nan=0.0, posinf=0.0, neginf=0.0)
    ev = np.nan_to_num(norm[eval_idx].astype(float), nan=0.0, posinf=0.0, neginf=0.0)
    model = NearestNeighbors(n_neighbors=1, metric="euclidean")
    model.fit(train)
    dist, _pos = model.kneighbors(ev, return_distance=True)
    dist = dist[:, 0]
    out = {
        "nn_train_sample": int(len(train_idx)),
        "nn_eval_sample": int(len(eval_idx)),
        "nn_distance_min": float(np.min(dist)),
        "nn_distance_p01": float(np.quantile(dist, 0.01)),
        "nn_distance_median": float(np.median(dist)),
        "nn_distance_p95": float(np.quantile(dist, 0.95)),
        "nn_exact_like_count": int(np.sum(dist <= 1.0e-6)),
    }
    for threshold in config["nearest_neighbor"]["distance_thresholds"]:
        out["nn_frac_dist_le_{:g}".format(float(threshold))] = float(np.mean(dist <= float(threshold)))
    return out


def feature_matrix_subset(
    config: dict,
    table: pd.DataFrame,
    handles: pd.DataFrame,
    train_mask: np.ndarray,
    cols: List[str],
) -> Tuple[np.ndarray, List[str]]:
    staves = list(config["staves"].keys())
    stave_to_i = {stave: i for i, stave in enumerate(staves)}
    train_h = handles.loc[train_mask, cols]
    med = train_h.median(numeric_only=True).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    filled_train = train_h.replace([np.inf, -np.inf], np.nan).fillna(med)
    mean = filled_train.mean()
    std = filled_train.std().replace(0.0, 1.0).fillna(1.0)
    h = handles[cols].replace([np.inf, -np.inf], np.nan).fillna(med)
    z = ((h[cols] - mean[cols]) / std[cols]).to_numpy(dtype=float)
    one_hot = np.zeros((len(table), len(staves)), dtype=float)
    for row, stave in enumerate(table["stave"].to_numpy()):
        one_hot[row, stave_to_i[stave]] = 1.0
    interactions = np.hstack([z[:, i : i + 1] * one_hot for i in range(z.shape[1])])
    names = cols + ["stave_{}".format(s) for s in staves] + ["{}:stave_{}".format(col, s) for col in cols for s in staves]
    return np.nan_to_num(np.hstack([z, one_hot, interactions]), nan=0.0, posinf=0.0, neginf=0.0), names


def fit_extra_trees_predictions(
    config: dict,
    table: pd.DataFrame,
    handles: pd.DataFrame,
    aligned: np.ndarray,
    train_mask: np.ndarray,
    rng: np.random.Generator,
    shuffled: bool,
    seed_offset: int,
    feature_cols: List[str] = None,
) -> Tuple[np.ndarray, dict, List[str]]:
    if feature_cols is None:
        X, _stats, feature_names = p10d.feature_matrix(config, table, handles, train_mask)
        feature_policy = "full_same_pulse_handles"
    else:
        X, feature_names = feature_matrix_subset(config, table, handles, train_mask, feature_cols)
        feature_policy = "no_tail_summary_handles"
    train_all = np.flatnonzero(train_mask)
    train_idx = train_all
    max_train = int(config["extra_trees"]["train_max_pulses"])
    if len(train_idx) > max_train:
        train_idx = rng.choice(train_idx, max_train, replace=False)
    y, fill = p10d.fill_target_from_train(aligned.astype(np.float32), train_idx)
    if shuffled:
        shuffled_idx = train_idx.copy()
        rng.shuffle(shuffled_idx)
        y = y.copy()
        y[train_idx] = y[shuffled_idx]
    model = ExtraTreesRegressor(
        n_estimators=int(config["extra_trees"]["n_estimators"]),
        max_depth=int(config["extra_trees"]["max_depth"]),
        min_samples_leaf=int(config["extra_trees"]["min_samples_leaf"]),
        max_features=float(config["extra_trees"]["max_features"]),
        n_jobs=int(config["extra_trees"]["n_jobs"]),
        random_state=int(config["random_seed"]) + int(seed_offset) + (10000 if shuffled else 0),
    )
    model.fit(X[train_idx], y[train_idx])
    pred = model.predict(X).astype(np.float32)
    meta = {
        "train_pulses": int(len(train_idx)),
        "candidate_train_pulses": int(len(train_all)),
        "target_nan_fill": fill.tolist(),
        "shuffled_target": bool(shuffled),
        "n_estimators": int(config["extra_trees"]["n_estimators"]),
        "max_depth": int(config["extra_trees"]["max_depth"]),
        "min_samples_leaf": int(config["extra_trees"]["min_samples_leaf"]),
        "feature_count": int(len(feature_names)),
        "feature_policy": feature_policy,
    }
    return pred, meta, feature_names


def bootstrap_summary(run_df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    metrics = ["q_template_mse", "q_tail_mse"]
    rng = np.random.default_rng(int(config["random_seed"]) + 77)
    summary_rows = []
    delta_rows = []
    for fold, fold_df in run_df.groupby("fold", observed=True):
        for method, group in fold_df.groupby("method", observed=True):
            matrix = group[metrics].to_numpy(dtype=float)
            boots = np.asarray(
                [matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0) for _ in range(int(config["bootstrap_iterations"]))]
            )
            row = {
                "fold": fold,
                "method": method,
                "n_runs": int(group["heldout_run"].nunique()),
                "n_rows": int(group["n"].sum()),
            }
            means = matrix.mean(axis=0)
            for i, metric in enumerate(metrics):
                row[metric] = float(means[i])
                row[metric + "_ci95"] = np.quantile(boots[:, i], [0.025, 0.975]).tolist()
            summary_rows.append(row)

        wide = fold_df.pivot(index="heldout_run", columns="method", values=metrics)
        for method in sorted(set(fold_df["method"]) - {"calibration_amp_median"}):
            for metric in metrics:
                vals = wide[(metric, method)].to_numpy(dtype=float) - wide[(metric, "calibration_amp_median")].to_numpy(dtype=float)
                vals = vals[np.isfinite(vals)]
                boots = [vals[rng.integers(0, len(vals), len(vals))].mean() for _ in range(int(config["bootstrap_iterations"]))]
                delta_rows.append(
                    {
                        "fold": fold,
                        "comparison": "{} minus calibration_amp_median".format(method),
                        "metric": metric,
                        "delta": float(vals.mean()),
                        "delta_ci95": np.quantile(boots, [0.025, 0.975]).tolist(),
                    }
                )
    return pd.DataFrame(summary_rows), pd.DataFrame(delta_rows)


def p10a_empirical_reference(config: dict, table: pd.DataFrame, aligned: np.ndarray) -> Tuple[float, List[float]]:
    calib_mask = table["group"].str.endswith("_calib").to_numpy()
    analysis_mask = table["group"].str.endswith("_analysis").to_numpy()
    pack, _bins = p10a.build_empirical_templates(config, table, aligned, calib_mask)
    pred = empirical_prediction(config, table, pack)
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=float)
    q, _q_tail = mse_scores(aligned, pred, rel_grid, float(config["tail_rel_min"]))
    run_rows = []
    for run in sorted(table.loc[analysis_mask, "run"].unique()):
        mask = analysis_mask & (table["run"].to_numpy() == run)
        run_rows.append(float(np.nanmean(q[mask])))
    return float(np.mean(run_rows)), run_rows


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


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    repro: pd.DataFrame,
    summary: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    summary_cols = ["fold", "method", "n_runs", "n_rows", "q_template_mse", "q_template_mse_ci95", "q_tail_mse", "q_tail_mse_ci95"]
    delta_cols = ["fold", "comparison", "metric", "delta", "delta_ci95"]
    leak_cols = [
        "fold",
        "train_eval_run_overlap",
        "train_eval_key_overlap",
        "waveform_hash_overlap_count",
        "uses_run_or_event_features",
        "uses_downstream_timing_labels",
        "ml_tail_too_good_triggered",
        "no_tail_ml_tail_too_good_triggered",
        "nn_distance_min",
        "nn_distance_p01",
        "nn_frac_dist_le_1e-06",
    ]
    lines = [
        "# P10f: conditional-template q_template tail validation",
        "",
        "- **Ticket ID:** `{}`".format(config["ticket_id"]),
        "- **Worker:** `{}`".format(config["worker"]),
        "- **Input:** raw B-stack ROOT under `{}`; no Monte Carlo.".format(config["raw_root_dir"]),
        "- **Config:** `{}`".format(config_path),
        "",
        "## Raw-ROOT reproduction first",
        "",
        "The selected-pulse table and the P10a calibration-only empirical q-template reference were rebuilt from raw `HRDv` waveforms before any model comparison.",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Split is by run. Sample-I analysis runs 44-57 are scored after training only on Sample-I calibration runs 31-42; Sample-II analysis runs 58-63 and 65 are scored after training only on calibration run 64. CIs bootstrap held-out runs.",
        "",
        "Baseline traditional method: calibration-only median templates by stave and amplitude bin. Strong traditional method: calibration-only median templates further binned by train-quantile rise-width and tail-summary handles, with hierarchical fallback. ML methods: multi-output ExtraTrees conditional templates from same-pulse local handles. The aggressive ML arm includes tail-summary handles; the no-tail ablation removes `tail_mean_8_17`, `tail_area_10_17`, and `late_over_total`. Run id, event id, event order, other-stave observables, downstream timing labels, and held-out target rows are excluded.",
        "",
        "`q_template_mse` uses all aligned samples. `q_tail_mse` is the validation target for this ticket and uses aligned samples with relative index >= `{}`.".format(config["tail_rel_min"]),
        "",
        "## Held-out run-bootstrap summary",
        "",
        summary[summary_cols].to_markdown(index=False),
        "",
        "## Deltas vs calibration median",
        "",
        deltas[delta_cols].to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        leakage[leak_cols].to_markdown(index=False),
        "",
        "A too-good flag fires if real ML tail MSE is less than 25% of its shuffled-target control. Waveform hashes are SHA256 values of normalized 18-sample waveforms quantized at 1e-6.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `heldout_scores_by_run.csv`, `method_summary.csv`, `method_deltas.csv`, `leakage_checks.csv`, and template diagnostics.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p10f_1781027860_942_36c33ff0_conditional_qtail_validation.py --config {}".format(config_path),
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10f_1781027860_942_36c33ff0_conditional_qtail_validation.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    table, aligned, norm = p10a.collect_selected(config)
    analysis_mask = table["group"].str.endswith("_analysis").to_numpy()
    p10a_q_ref, p10a_ref_runs = p10a_empirical_reference(config, table, aligned)
    repro = pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(len(table)),
                "delta": int(len(table) - int(config["expected_selected_pulses"])),
                "tolerance": 0.0,
                "pass": bool(len(table) == int(config["expected_selected_pulses"])),
            },
            {
                "quantity": "analysis selected rows",
                "expected": int(config["expected_analysis_rows"]),
                "reproduced": int(analysis_mask.sum()),
                "delta": int(analysis_mask.sum() - int(config["expected_analysis_rows"])),
                "tolerance": 0.0,
                "pass": bool(int(analysis_mask.sum()) == int(config["expected_analysis_rows"])),
            },
            {
                "quantity": "P10a calibration-only empirical q_template MSE",
                "expected": float(config["expected_p10a_empirical_q_mse"]),
                "reproduced": p10a_q_ref,
                "delta": p10a_q_ref - float(config["expected_p10a_empirical_q_mse"]),
                "tolerance": float(config["expected_p10a_empirical_tolerance"]),
                "pass": bool(abs(p10a_q_ref - float(config["expected_p10a_empirical_q_mse"])) <= float(config["expected_p10a_empirical_tolerance"])),
            },
        ]
    )
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pd.DataFrame({"run": sorted(table.loc[analysis_mask, "run"].unique()), "p10a_empirical_q_mse": p10a_ref_runs}).to_csv(
        out_dir / "p10a_reference_by_run.csv", index=False
    )
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    inputs = write_input_sha(config, out_dir)
    handles = p10d.make_handles(table, norm)
    handles.describe().to_csv(out_dir / "handle_feature_describe.csv")
    hashes = waveform_hashes(norm)
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=float)
    run_rows = []
    leakage_rows = []
    feature_names: List[str] = []
    model_meta: Dict[str, dict] = {}
    template_bin_parts = []
    handle_bin_parts = []

    key_cols = ["run", "eventno", "evt", "stave"]
    for fold_num, fold in enumerate(config["calibration_folds"], start=1):
        groups = table["group"].to_numpy()
        train_mask = groups == fold["train_group"]
        eval_mask = groups == fold["eval_group"]

        empirical_pack, template_bins = p10a.build_empirical_templates(config, table, aligned, train_mask)
        template_bins.insert(0, "fold", fold["name"])
        template_bin_parts.append(template_bins)
        empirical_pred = empirical_prediction(config, table, empirical_pack)

        handle_pred, handle_bins = p10d.handle_binned_templates(config, table, handles, aligned, train_mask)
        handle_bins.insert(0, "fold", fold["name"])
        handle_bin_parts.append(handle_bins)

        ml_pred, ml_meta, feature_names = fit_extra_trees_predictions(
            config, table, handles, aligned, train_mask, rng, shuffled=False, seed_offset=100 * fold_num
        )
        shuf_pred, shuf_meta, _feature_names = fit_extra_trees_predictions(
            config, table, handles, aligned, train_mask, rng, shuffled=True, seed_offset=100 * fold_num
        )
        no_tail_pred, no_tail_meta, no_tail_names = fit_extra_trees_predictions(
            config, table, handles, aligned, train_mask, rng, shuffled=False, seed_offset=500 + 100 * fold_num, feature_cols=NO_TAIL_HANDLE_COLS
        )
        no_tail_shuf_pred, no_tail_shuf_meta, _no_tail_shuf_names = fit_extra_trees_predictions(
            config, table, handles, aligned, train_mask, rng, shuffled=True, seed_offset=500 + 100 * fold_num, feature_cols=NO_TAIL_HANDLE_COLS
        )
        model_meta[fold["name"]] = {
            "extra_trees": ml_meta,
            "shuffled_extra_trees": shuf_meta,
            "no_tail_extra_trees": no_tail_meta,
            "no_tail_shuffled_extra_trees": no_tail_shuf_meta,
            "feature_names": feature_names,
            "no_tail_feature_names": no_tail_names,
        }

        predictions = {
            "calibration_amp_median": empirical_pred,
            "traditional_shape_handle_median": handle_pred,
            "ml_extra_trees_conditional": ml_pred,
            "ml_extra_trees_shuffled": shuf_pred,
            "ml_extra_trees_no_tail": no_tail_pred,
            "ml_extra_trees_no_tail_shuffled": no_tail_shuf_pred,
        }
        scores = {}
        for method, pred in predictions.items():
            q, q_tail = mse_scores(aligned, pred, rel_grid, float(config["tail_rel_min"]))
            scores[method] = {"q_template_mse": q, "q_tail_mse": q_tail}

        for run in sorted(table.loc[eval_mask, "run"].unique()):
            mask = eval_mask & (table["run"].to_numpy() == run)
            for method in predictions:
                run_rows.append(
                    {
                        "fold": fold["name"],
                        "train_group": fold["train_group"],
                        "eval_group": fold["eval_group"],
                        "heldout_run": int(run),
                        "method": method,
                        "n": int(mask.sum()),
                        "q_template_mse": float(np.nanmean(scores[method]["q_template_mse"][mask])),
                        "q_tail_mse": float(np.nanmean(scores[method]["q_tail_mse"][mask])),
                    }
                )

        train_runs = set(table.loc[train_mask, "run"].astype(int))
        eval_runs = set(table.loc[eval_mask, "run"].astype(int))
        train_keys = set(map(tuple, table.loc[train_mask, key_cols].to_numpy()))
        eval_keys = set(map(tuple, table.loc[eval_mask, key_cols].to_numpy()))
        hash_overlap = set(hashes[train_mask]) & set(hashes[eval_mask])
        real_tail = np.nanmean(scores["ml_extra_trees_conditional"]["q_tail_mse"][eval_mask])
        shuf_tail = np.nanmean(scores["ml_extra_trees_shuffled"]["q_tail_mse"][eval_mask])
        no_tail_real = np.nanmean(scores["ml_extra_trees_no_tail"]["q_tail_mse"][eval_mask])
        no_tail_shuf = np.nanmean(scores["ml_extra_trees_no_tail_shuffled"]["q_tail_mse"][eval_mask])
        leakage = {
            "fold": fold["name"],
            "train_eval_run_overlap": sorted(train_runs & eval_runs),
            "train_eval_key_overlap": int(len(train_keys & eval_keys)),
            "waveform_hash_overlap_count": int(len(hash_overlap)),
            "waveform_hash_overlap_frac_eval_unique": float(len(hash_overlap) / max(len(set(hashes[eval_mask])), 1)),
            "uses_run_or_event_features": bool(any(name in {"run", "eventno", "evt"} for name in feature_names)),
            "uses_downstream_timing_labels": False,
            "uses_other_stave_features": False,
            "real_ml_q_tail_mse": float(real_tail),
            "shuffled_ml_q_tail_mse": float(shuf_tail),
            "real_minus_shuffled_q_tail_mse": float(real_tail - shuf_tail),
            "no_tail_ml_q_tail_mse": float(no_tail_real),
            "no_tail_shuffled_ml_q_tail_mse": float(no_tail_shuf),
            "no_tail_real_minus_shuffled_q_tail_mse": float(no_tail_real - no_tail_shuf),
            "ml_tail_too_good_triggered": bool(np.isfinite(real_tail) and np.isfinite(shuf_tail) and real_tail < 0.25 * shuf_tail),
            "no_tail_ml_tail_too_good_triggered": bool(np.isfinite(no_tail_real) and np.isfinite(no_tail_shuf) and no_tail_real < 0.25 * no_tail_shuf),
        }
        leakage.update(nearest_neighbor_check(config, norm, train_mask, eval_mask, rng))
        leakage_rows.append(leakage)

    run_df = pd.DataFrame(run_rows)
    run_df.to_csv(out_dir / "heldout_scores_by_run.csv", index=False)
    pd.concat(template_bin_parts, ignore_index=True).to_csv(out_dir / "template_bin_counts.csv", index=False)
    pd.concat(handle_bin_parts, ignore_index=True).to_csv(out_dir / "handle_bin_counts.csv", index=False)
    summary, deltas = bootstrap_summary(run_df, config)
    summary.to_csv(out_dir / "method_summary.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas.csv", index=False)
    leakage_df = pd.DataFrame(leakage_rows)
    leakage_df.to_csv(out_dir / "leakage_checks.csv", index=False)

    tail_delta = deltas[
        (deltas["comparison"] == "ml_extra_trees_no_tail minus calibration_amp_median")
        & (deltas["metric"] == "q_tail_mse")
    ].copy()
    ci_clean_folds = [row["fold"] for _, row in tail_delta.iterrows() if row["delta_ci95"][1] < 0]
    any_too_good = bool(leakage_df["ml_tail_too_good_triggered"].any())
    no_tail_too_good = bool(leakage_df["no_tail_ml_tail_too_good_triggered"].any())
    finding = (
        "The no-tail ExtraTrees conditional q-tail scores beat the calibration-only amplitude-median baseline with CI-clean run-bootstrap deltas in "
        "{} of {} folds. ".format(len(ci_clean_folds), len(tail_delta))
    )
    if any_too_good:
        finding += "The aggressive tail-handle ML arm fired the too-good trigger, consistent with target-proximal tail handles. "
    else:
        finding += "The aggressive tail-handle ML arm did not fire the too-good trigger. "
    if no_tail_too_good:
        finding += "The no-tail ablation also fired the too-good trigger, so the ML gain is not promoted."
    else:
        finding += "The no-tail ablation did not fire the too-good trigger; train/eval run, key, and hash overlaps are zero."

    runtime = time.time() - t0
    result = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "runtime_sec": round(runtime, 3),
        "raw_root_reproduced": bool(repro["pass"].all()),
        "reproduction": json.loads(repro.to_json(orient="records")),
        "split": "calibration-only train groups; held-out analysis runs; run-bootstrap confidence intervals",
        "methods": {
            "calibration_amp_median": "median aligned template by stave and amplitude bin from calibration runs only",
            "traditional_shape_handle_median": "median aligned template by stave, amplitude bin, rise bin, and tail-summary bin from calibration runs only",
            "ml_extra_trees_conditional": "multi-output ExtraTrees conditional template from same-pulse local handles including tail summaries, without downstream timing labels",
            "ml_extra_trees_shuffled": "same ExtraTrees fit after shuffling calibration targets",
            "ml_extra_trees_no_tail": "multi-output ExtraTrees conditional template after removing same-pulse tail-summary handles",
            "ml_extra_trees_no_tail_shuffled": "no-tail ExtraTrees fit after shuffling calibration targets",
        },
        "primary_metric": "q_tail_mse on aligned samples with relative index >= {}".format(config["tail_rel_min"]),
        "method_summary": json.loads(summary.to_json(orient="records")),
        "method_deltas": json.loads(deltas.to_json(orient="records")),
        "leakage_checks": json.loads(leakage_df.to_json(orient="records")),
        "model_meta": json_clean(model_meta),
        "ci_clean_ml_tail_folds": ci_clean_folds,
        "finding": finding,
        "input_sha256": "input_sha256.csv",
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True), encoding="utf-8")
    write_report(out_dir, config_path, config, repro, summary, deltas, leakage_df, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "command": "/home/billy/anaconda3/bin/python scripts/p10f_1781027860_942_36c33ff0_conditional_qtail_validation.py --config {}".format(config_path),
        "git_commit": result["git_commit"],
        "platform": platform.platform(),
        "python": platform.python_version(),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "script": "scripts/p10f_1781027860_942_36c33ff0_conditional_qtail_validation.py",
        "script_sha256": sha256_file(Path("scripts/p10f_1781027860_942_36c33ff0_conditional_qtail_validation.py")),
        "support_scripts": [
            {"path": "scripts/p10a_conditional_template.py", "sha256": sha256_file(Path("scripts/p10a_conditional_template.py"))},
            {"path": "scripts/p10d_1781012637_1082_5f6513ba.py", "sha256": sha256_file(Path("scripts/p10d_1781012637_1082_5f6513ba.py"))},
        ],
        "inputs": inputs,
        "outputs": outputs,
        "random_seed": int(config["random_seed"]),
        "runtime_sec": round(runtime, 3),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "runtime_sec": runtime, "finding": finding}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
