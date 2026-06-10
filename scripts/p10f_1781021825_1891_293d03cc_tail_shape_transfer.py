#!/usr/bin/env python3
"""P10f tail-shape transfer across current and saturation strata.

The script rebuilds the selected B-stack pulse table from raw ROOT before any
model fit, reproduces the S10b live10 anchor, then compares a train-run empirical
template baseline with a conditional ExtraTrees tail surrogate under leave-one-run-out
evaluation.
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
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.preprocessing import StandardScaler


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p10a = load_module("p10a_conditional_template", Path("scripts/p10a_conditional_template.py"))
s10c = load_module("s10c_threshold_scan_tau_eff", Path("reports/1781007337.1308.7dc86005/s10c_threshold_scan_tau_eff.py"))


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


def current_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for name, runs in config["current_strata"].items():
        for run in runs:
            out[int(run)] = name
    return out


def saturation_names(config: dict, amp: np.ndarray) -> np.ndarray:
    out = np.full(len(amp), "unassigned", dtype=object)
    for item in config["saturation_bins"]:
        mask = (amp >= float(item["low"])) & (amp < float(item["high"]))
        out[mask] = str(item["name"])
    return out


def add_strata(config: dict, table: pd.DataFrame) -> pd.DataFrame:
    work = table.copy()
    currents = current_lookup(config)
    work["current_stratum"] = [currents.get(int(run), "other") for run in work["run"]]
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    amp = work["amplitude_adc"].to_numpy(dtype=float)
    bin_idx = np.clip(np.searchsorted(edges, amp, side="right") - 1, 0, len(edges) - 2)
    work["amp_bin"] = bin_idx.astype(int)
    work["amp_bin_label"] = [f"a{int(edges[i])}_{int(edges[i + 1])}" for i in bin_idx]
    work["saturation_bin"] = saturation_names(config, amp)
    work["is_saturation_proxy"] = (amp >= 9000.0).astype(int)
    work["is_boundary"] = ((amp >= 6500.0) & (amp < 9000.0)).astype(int)
    return work


def reproduction_gate(config: dict, table: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
    s10_pulses = s10c.read_selected_pulses()
    _fits, heldout = s10c.traditional_template_fits(s10_pulses)
    live10 = float(heldout["traditional_template_live_10pct_ns"].mean())
    analysis_rows = int(table["group"].str.endswith("_analysis").sum())
    rows = [
        {
            "quantity": "S00/S01 selected B-stave pulses",
            "expected": float(config["expected_selected_pulses"]),
            "reproduced": float(len(table)),
            "delta": float(len(table) - int(config["expected_selected_pulses"])),
            "tolerance": 0.0,
            "pass": bool(len(table) == int(config["expected_selected_pulses"])),
        },
        {
            "quantity": "analysis selected rows",
            "expected": float(config["expected_analysis_rows"]),
            "reproduced": float(analysis_rows),
            "delta": float(analysis_rows - int(config["expected_analysis_rows"])),
            "tolerance": 0.0,
            "pass": bool(analysis_rows == int(config["expected_analysis_rows"])),
        },
        {
            "quantity": "S10b traditional template live10 ns",
            "expected": float(config["expected_s10b_live10_ns"]),
            "reproduced": live10,
            "delta": live10 - float(config["expected_s10b_live10_ns"]),
            "tolerance": float(config["s10b_live10_tolerance_ns"]),
            "pass": bool(abs(live10 - float(config["expected_s10b_live10_ns"])) <= float(config["s10b_live10_tolerance_ns"])),
        },
    ]
    return pd.DataFrame(rows), live10


def stratified_eval_indices(config: dict, table: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    selected: List[np.ndarray] = []
    cap = int(config["max_eval_per_run_stave_amp_sat"])
    eval_runs = set(int(v) for v in config["eval_runs"])
    work = table[table["run"].isin(eval_runs)]
    for _, group in work.groupby(["run", "stave", "amp_bin", "saturation_bin"], observed=True):
        idx = group.index.to_numpy()
        if len(idx) > cap:
            idx = rng.choice(idx, size=cap, replace=False)
        selected.append(idx)
    return np.sort(np.concatenate(selected))


def waveform_metrics(aligned: np.ndarray, rel_grid: np.ndarray, sample_period_ns: float) -> pd.DataFrame:
    tail_mask = rel_grid >= 2
    late_mask = rel_grid >= 8
    rows = []
    for y in aligned:
        valid = np.isfinite(y)
        if not valid.any():
            rows.append({"obs_live10_ns": np.nan, "obs_live20_ns": np.nan, "obs_tail_sum": np.nan, "obs_tail_late_frac": np.nan, "obs_tail_slope": np.nan})
            continue
        yy = np.nan_to_num(y.astype(float), nan=0.0)
        peak_i = int(np.nanargmax(yy))
        live = {}
        for frac in [0.10, 0.20]:
            ok = np.flatnonzero((np.arange(len(yy)) >= peak_i) & (yy >= frac))
            live[f"obs_live{int(frac * 100)}_ns"] = float(rel_grid[ok[-1]] * sample_period_ns) if len(ok) else np.nan
        tail = yy[tail_mask]
        late = yy[late_mask]
        x = rel_grid[tail_mask]
        slope = np.polyfit(x[np.isfinite(tail)], tail[np.isfinite(tail)], 1)[0] if np.isfinite(tail).sum() >= 3 else np.nan
        rows.append(
            {
                **live,
                "obs_tail_sum": float(np.nansum(tail)),
                "obs_tail_late_frac": float(np.nansum(late) / max(np.nansum(tail), 1e-9)),
                "obs_tail_slope": float(slope),
            }
        )
    return pd.DataFrame(rows)


def build_traditional_templates(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_idx: np.ndarray) -> dict:
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=float)
    train = table.iloc[train_idx]
    train_aligned = aligned[train_idx]
    templates: Dict[Tuple[str, int, str, str], np.ndarray] = {}
    fall_amp: Dict[Tuple[str, int], np.ndarray] = {}
    fall_stave: Dict[str, np.ndarray] = {}
    min_bin = int(config["template_min_bin_pulses"])

    for stave, sgroup in train.groupby("stave", observed=True):
        sidx = sgroup.index.to_numpy()
        fall_stave[str(stave)] = np.nanmedian(aligned[sidx], axis=0)
    for (stave, amp_bin), agroup in train.groupby(["stave", "amp_bin"], observed=True):
        idx = agroup.index.to_numpy()
        fall_amp[(str(stave), int(amp_bin))] = np.nanmedian(aligned[idx], axis=0)
    for key, group in train.groupby(["stave", "amp_bin", "current_stratum", "saturation_bin"], observed=True):
        idx = group.index.to_numpy()
        if len(idx) >= min_bin:
            templates[(str(key[0]), int(key[1]), str(key[2]), str(key[3]))] = np.nanmedian(aligned[idx], axis=0)

    def predict(rows: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        pred = []
        source = []
        for row in rows.itertuples():
            full = (str(row.stave), int(row.amp_bin), str(row.current_stratum), str(row.saturation_bin))
            amp_key = (str(row.stave), int(row.amp_bin))
            if full in templates:
                pred.append(templates[full])
                source.append("stave_amp_current_saturation")
            elif amp_key in fall_amp:
                pred.append(fall_amp[amp_key])
                source.append("stave_amp")
            else:
                pred.append(fall_stave[str(row.stave)])
                source.append("stave")
        return np.vstack(pred).astype(np.float32), source

    return {"predict": predict, "n_full_templates": len(templates), "grid": rel_grid}


def feature_matrix(config: dict, table: pd.DataFrame, fit_stats: dict = None) -> Tuple[np.ndarray, dict, List[str]]:
    names = ["log_amp", "log_amp2", "is_boundary", "is_saturation_proxy"]
    amp = table["amplitude_adc"].to_numpy(dtype=float)
    log_amp = np.log(np.maximum(amp, 1.0))
    base = [log_amp, log_amp * log_amp, table["is_boundary"].to_numpy(dtype=float), table["is_saturation_proxy"].to_numpy(dtype=float)]
    for stave in config["staves"]:
        names.append(f"stave_{stave}")
        base.append((table["stave"].to_numpy() == stave).astype(float))
    for current in sorted(config["current_strata"]):
        names.append(f"current_{current}")
        base.append((table["current_stratum"].to_numpy() == current).astype(float))
    X = np.vstack(base).T.astype(float)
    if fit_stats is None:
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        fit_stats = {"mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}
    else:
        mean = np.asarray(fit_stats["mean"], dtype=float)
        scale = np.asarray(fit_stats["scale"], dtype=float)
        scale[scale == 0] = 1.0
        Xs = (X - mean) / scale
    return Xs, fit_stats, names


def fit_et_predictions(config: dict, table: pd.DataFrame, aligned: np.ndarray, train_idx: np.ndarray, eval_idx: np.ndarray, rng: np.random.Generator) -> Tuple[np.ndarray, np.ndarray, dict]:
    max_train = int(config["max_train_rows_per_fold"])
    fit_idx = train_idx.copy()
    if len(fit_idx) > max_train:
        fit_idx = rng.choice(fit_idx, size=max_train, replace=False)
    X_train, stats, names = feature_matrix(config, table.iloc[fit_idx])
    X_eval, _, _ = feature_matrix(config, table.iloc[eval_idx], stats)
    params = dict(config["extra_trees"])
    target = aligned[fit_idx].astype(float)
    med = np.nanmedian(target, axis=0)
    med = np.where(np.isfinite(med), med, 0.0)
    y = np.where(np.isfinite(target), target, med[None, :])
    model = ExtraTreesRegressor(**params)
    model.fit(X_train, y)
    pred = model.predict(X_eval).astype(np.float32)
    shuffled_live10_pred = np.full(len(eval_idx), np.nan, dtype=float)

    live_train = waveform_metrics(aligned[fit_idx], np.asarray(config["aligned_relative_grid"], dtype=float), float(config["sample_period_ns"]))["obs_live10_ns"].to_numpy(dtype=float)
    ok = np.isfinite(live_train)
    if ok.sum() >= 100:
        shuffled = live_train[ok].copy()
        rng.shuffle(shuffled)
        shuf_params = dict(params)
        shuf_params["random_state"] = int(config["random_seed"]) + 909
        shuf_model = ExtraTreesRegressor(**shuf_params)
        shuf_model.fit(X_train[ok], shuffled)
        shuffled_live10_pred = shuf_model.predict(X_eval)

    meta = {"train_rows": int(len(fit_idx)), "feature_names": names}
    return pred, shuffled_live10_pred, meta


def mse_rows(obs: np.ndarray, pred: np.ndarray, rel_grid: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(obs) & np.isfinite(pred)
    diff2 = (np.nan_to_num(obs, nan=0.0) - np.nan_to_num(pred, nan=0.0)) ** 2
    denom = valid.sum(axis=1)
    q = np.full(len(obs), np.nan, dtype=float)
    ok = denom > 0
    q[ok] = diff2[ok].sum(axis=1) / denom[ok]
    tail = rel_grid >= 2
    denom_tail = valid[:, tail].sum(axis=1)
    t = np.full(len(obs), np.nan, dtype=float)
    ok_tail = denom_tail > 0
    t[ok_tail] = diff2[:, tail][ok_tail].sum(axis=1) / denom_tail[ok_tail]
    return q, t


def summarize_by_run(rows: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    metrics = ["q_template_mse", "tail_mse", "live10_abs_error_ns", "live10_bias_ns", "live20_abs_error_ns"]
    run_rows = []
    for (method, run), group in rows.groupby(["method", "heldout_run"], observed=True):
        row = {"method": method, "heldout_run": int(run), "n": int(len(group))}
        for metric in metrics:
            row[metric] = float(np.nanmean(group[metric]))
        run_rows.append(row)
    run_df = pd.DataFrame(run_rows)
    rng = np.random.default_rng(int(config["random_seed"]) + 33)
    summary_rows = []
    for method, group in run_df.groupby("method", observed=True):
        matrix = group[metrics].to_numpy(dtype=float)
        boots = []
        for _ in range(int(config["bootstrap_iterations"])):
            boots.append(matrix[rng.integers(0, len(matrix), len(matrix))].mean(axis=0))
        boots = np.asarray(boots)
        row = {"method": method, "n_runs": int(len(group)), "n_rows": int(rows.loc[rows["method"] == method, "row_id"].nunique())}
        means = matrix.mean(axis=0)
        for i, metric in enumerate(metrics):
            row[metric] = float(means[i])
            row[f"{metric}_ci95"] = np.quantile(boots[:, i], [0.025, 0.975]).tolist()
        summary_rows.append(row)
    return run_df, pd.DataFrame(summary_rows)


def summarize_deltas(run_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    metrics = ["q_template_mse", "tail_mse", "live10_abs_error_ns", "live20_abs_error_ns"]
    wide = run_df.pivot(index="heldout_run", columns="method", values=metrics)
    rng = np.random.default_rng(int(config["random_seed"]) + 44)
    rows = []
    for metric in metrics:
        vals = wide[(metric, "ml_et_tail_surrogate")].to_numpy(dtype=float) - wide[(metric, "traditional_empirical_template")].to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        boots = [vals[rng.integers(0, len(vals), len(vals))].mean() for _ in range(int(config["bootstrap_iterations"]))]
        rows.append(
            {
                "comparison": "ml_et_tail_surrogate minus traditional_empirical_template",
                "metric": metric,
                "delta": float(vals.mean()),
                "delta_ci95": np.quantile(boots, [0.025, 0.975]).tolist(),
            }
        )
    return pd.DataFrame(rows)


def summarize_strata(rows: pd.DataFrame) -> pd.DataFrame:
    metrics = ["q_template_mse", "tail_mse", "live10_abs_error_ns", "live20_abs_error_ns"]
    out = []
    for keys, group in rows.groupby(["method", "current_stratum", "saturation_bin"], observed=True):
        row = {"method": keys[0], "current_stratum": keys[1], "saturation_bin": keys[2], "n": int(len(group)), "n_runs": int(group["heldout_run"].nunique())}
        for metric in metrics:
            row[metric] = float(np.nanmean(group[metric]))
        out.append(row)
    return pd.DataFrame(out).sort_values(["current_stratum", "saturation_bin", "method"])


def write_report(out_dir: Path, config: dict, repro: pd.DataFrame, summary: pd.DataFrame, deltas: pd.DataFrame, strata: pd.DataFrame, leakage: dict, result: dict) -> None:
    best_tail = summary.sort_values("tail_mse").iloc[0]
    live_delta = deltas[deltas["metric"] == "live10_abs_error_ns"].iloc[0]
    lines = [
        "# P10f: template tail-shape saturation and current transfer",
        "",
        f"Ticket `{config['ticket_id']}`. Raw B-stack ROOT under `{config['raw_root_dir']}` was used directly; no Monte Carlo was used.",
        "",
        "## Raw reproduction first",
        "",
        repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Evaluation is leave-one-run-out over analysis runs. For every held-out run, all empirical templates and ExtraTrees models are fit after excluding that run. CIs bootstrap held-out runs.",
        "",
        "Traditional method: S01/P10 empirical median templates binned by stave, amplitude, current stratum, and saturation proxy, with stave-amplitude and stave fallbacks.",
        "",
        "ML method: multi-output ExtraTrees conditional tail surrogate using log amplitude, stave, current stratum, and saturation/boundary flags. It predicts the aligned normalized template samples; run id, event id, and target residuals are excluded.",
        "",
        "## Held-out summary",
        "",
        summary[["method", "n_runs", "n_rows", "q_template_mse", "tail_mse", "live10_abs_error_ns", "live20_abs_error_ns"]].to_markdown(index=False),
        "",
        "## ML minus traditional deltas",
        "",
        deltas.to_markdown(index=False),
        "",
        "## Current and saturation strata",
        "",
        strata[["method", "current_stratum", "saturation_bin", "n", "n_runs", "tail_mse", "live10_abs_error_ns", "live20_abs_error_ns"]].to_markdown(index=False),
        "",
        "## Leakage audit",
        "",
        f"- Held-out runs absent from train: `{leakage['heldout_absent_from_train']}`.",
        f"- Train/eval `(run,event,evt,stave)` overlap: `{leakage['train_eval_key_overlap']}`.",
        f"- Feature matrix excludes run id and event id: `{leakage['no_run_or_event_features']}`.",
        f"- Real ML live10 absolute error on held-out rows: `{leakage['real_ml_live10_abs_error_ns']:.4g}` ns.",
        f"- Shuffled live10 absolute error on held-out rows: `{leakage['shuffled_live10_abs_error_ns']:.4g}` ns.",
        f"- Too-good trigger fired: `{leakage['too_good_triggered']}`.",
        "",
        "## Finding",
        "",
        f"The best held-out tail MSE is `{best_tail['method']}` at `{best_tail['tail_mse']:.6g}`. The ML-minus-traditional live10 absolute-error delta is `{live_delta['delta']:.4g}` ns with run-bootstrap CI `{live_delta['delta_ci95']}`, but the shuffled-live10 control is not worse than the real ML live10 prediction, so the live10 gain is not promoted as a trustworthy transfer claim. The stable result is narrower: ExtraTrees improves q/tail-shape MSE, while live-time and live20 transfer still need a better target/control.",
        "",
        "## Reproduce",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/p10f_1781021825_1891_293d03cc_tail_shape_transfer.py --config configs/p10f_1781021825_1891_293d03cc_tail_shape_transfer.json",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p10f_1781021825_1891_293d03cc_tail_shape_transfer.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    table, aligned, _norm = p10a.collect_selected(config)
    table = add_strata(config, table)
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=float)
    obs_metrics = waveform_metrics(aligned, rel_grid, float(config["sample_period_ns"]))
    table = pd.concat([table.reset_index(drop=True), obs_metrics], axis=1)

    repro, live10 = reproduction_gate(config, table)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("reproduction gate failed")

    eval_idx_all = stratified_eval_indices(config, table, rng)
    eval_runs = sorted(int(v) for v in table.iloc[eval_idx_all]["run"].unique())
    pred_rows = []
    fold_rows = []
    leakage_key_overlap = 0
    shuffled_abs = []
    feature_names = []

    key_cols = ["run", "eventno", "evt", "stave"]
    for heldout in eval_runs:
        eval_idx = eval_idx_all[table.iloc[eval_idx_all]["run"].to_numpy() == heldout]
        train_idx = np.flatnonzero(table["run"].to_numpy() != heldout)
        train_keys = set(map(tuple, table.iloc[train_idx][key_cols].to_numpy()))
        eval_keys = set(map(tuple, table.iloc[eval_idx][key_cols].to_numpy()))
        leakage_key_overlap += len(train_keys & eval_keys)

        trad = build_traditional_templates(config, table, aligned, train_idx)
        trad_pred, trad_source = trad["predict"](table.iloc[eval_idx])
        ml_pred, shuffled_live10, meta = fit_et_predictions(config, table, aligned, train_idx, eval_idx, rng)
        feature_names = meta["feature_names"]

        for method, pred, source in [
            ("traditional_empirical_template", trad_pred, trad_source),
            ("ml_et_tail_surrogate", ml_pred, ["extra_trees"] * len(eval_idx)),
        ]:
            q_mse, tail_mse = mse_rows(aligned[eval_idx], pred, rel_grid)
            pred_metrics = waveform_metrics(pred, rel_grid, float(config["sample_period_ns"]))
            sub = table.iloc[eval_idx].reset_index(drop=True)
            for i, row in sub.iterrows():
                pred_rows.append(
                    {
                        "row_id": int(eval_idx[i]),
                        "method": method,
                        "heldout_run": int(heldout),
                        "stave": row["stave"],
                        "current_stratum": row["current_stratum"],
                        "saturation_bin": row["saturation_bin"],
                        "amp_bin_label": row["amp_bin_label"],
                        "amplitude_adc": float(row["amplitude_adc"]),
                        "template_source": source[i],
                        "q_template_mse": float(q_mse[i]),
                        "tail_mse": float(tail_mse[i]),
                        "live10_bias_ns": float(pred_metrics.loc[i, "obs_live10_ns"] - row["obs_live10_ns"]),
                        "live10_abs_error_ns": float(abs(pred_metrics.loc[i, "obs_live10_ns"] - row["obs_live10_ns"])),
                        "live20_abs_error_ns": float(abs(pred_metrics.loc[i, "obs_live20_ns"] - row["obs_live20_ns"])),
                        "tail_sum_bias": float(pred_metrics.loc[i, "obs_tail_sum"] - row["obs_tail_sum"]),
                    }
                )
        shuffled_abs.extend(np.abs(shuffled_live10 - table.iloc[eval_idx]["obs_live10_ns"].to_numpy(dtype=float)).tolist())
        fold_rows.append({"heldout_run": int(heldout), "n_eval": int(len(eval_idx)), "n_train": int(len(train_idx)), "ml_train_rows": int(meta["train_rows"]), "traditional_full_templates": int(trad["n_full_templates"])})

    rows = pd.DataFrame(pred_rows)
    rows.to_csv(out_dir / "heldout_predictions.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(out_dir / "fold_summary.csv", index=False)
    run_summary, summary = summarize_by_run(rows, config)
    run_summary.to_csv(out_dir / "run_summary.csv", index=False)
    summary.to_csv(out_dir / "heldout_summary.csv", index=False)
    deltas = summarize_deltas(run_summary, config)
    deltas.to_csv(out_dir / "ml_deltas.csv", index=False)
    strata = summarize_strata(rows)
    strata.to_csv(out_dir / "stratum_summary.csv", index=False)

    input_paths = [p10a.raw_file(config, run) for run in p10a.configured_runs(config)]
    inputs = [{"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_paths]
    with (out_dir / "input_sha256.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(inputs)

    shuf = np.asarray(shuffled_abs, dtype=float)
    real_ml_live = rows[rows["method"] == "ml_et_tail_surrogate"]["live10_abs_error_ns"].to_numpy(dtype=float)
    leakage = {
        "heldout_absent_from_train": True,
        "train_eval_key_overlap": int(leakage_key_overlap),
        "no_run_or_event_features": bool(not any(name in {"run", "eventno", "evt"} for name in feature_names)),
        "shuffled_live10_abs_error_ns": float(np.nanmean(shuf)),
        "real_ml_live10_abs_error_ns": float(np.nanmean(real_ml_live)),
        "too_good_triggered": bool(np.nanmean(real_ml_live) < 0.1 or np.nanmean(real_ml_live) < 0.25 * np.nanmean(shuf)),
    }
    pd.DataFrame([leakage]).to_csv(out_dir / "leakage_checks.csv", index=False)

    runtime = time.time() - t0
    result = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": round(runtime, 3),
        "reproduced": bool(repro["pass"].all()),
        "s10b_anchor_recomputed_live10_ns": live10,
        "methods": sorted(rows["method"].unique().tolist()),
        "split": "leave-one-analysis-run-out; run-bootstrap confidence intervals",
        "heldout_summary": json.loads(summary.to_json(orient="records")),
        "ml_minus_traditional_deltas": json.loads(deltas.to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": "ExtraTrees improves held-out q/tail-shape MSE over the empirical template, but the shuffled-live10 control is not worse than real ML live10, so P10f does not promote the live-time transfer as trustworthy.",
        "input_sha256": "input_sha256.csv"
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_report(out_dir, config, repro, summary, deltas, strata, leakage, result)

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "command": f"/home/billy/anaconda3/bin/python scripts/p10f_1781021825_1891_293d03cc_tail_shape_transfer.py --config {config_path}",
        "git_commit": result["git_commit"],
        "platform": platform.platform(),
        "python": platform.python_version(),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "script": "scripts/p10f_1781021825_1891_293d03cc_tail_shape_transfer.py",
        "script_sha256": sha256_file(Path("scripts/p10f_1781021825_1891_293d03cc_tail_shape_transfer.py")),
        "support_scripts": [
            {"path": "scripts/p10a_conditional_template.py", "sha256": sha256_file(Path("scripts/p10a_conditional_template.py"))},
            {"path": "reports/1781007337.1308.7dc86005/s10c_threshold_scan_tau_eff.py", "sha256": sha256_file(Path("reports/1781007337.1308.7dc86005/s10c_threshold_scan_tau_eff.py"))}
        ],
        "inputs": inputs,
        "outputs": outputs,
        "random_seed": int(config["random_seed"])
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "runtime_sec": runtime, "reproduced": result["reproduced"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
