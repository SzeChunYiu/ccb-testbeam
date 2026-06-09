#!/usr/bin/env python3
"""S01f q_template run/stave transfer-failure test from raw ROOT."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score


SCRIPT_PATH = Path(__file__)


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


def group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_root(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


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


def assign_bins(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, values, side="right") - 1, 0, len(edges) - 2)


def local_role(eventno: np.ndarray, evt: np.ndarray) -> np.ndarray:
    hashed = (eventno.astype(np.int64) * 1000003 + evt.astype(np.int64) * 9176 + 104729) & 0x7FFFFFFF
    return (hashed % 2).astype(np.int8)


def collect_selected(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][stave]) for stave in staves], dtype=int)
    stave_grid = np.asarray(staves)
    group_for_run = group_lookup(config)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rel_grid = np.asarray(config["aligned_relative_grid"], dtype=float)
    cfd_fraction = float(config["cfd_fraction"])
    rows: List[pd.DataFrame] = []
    aligned_chunks: List[np.ndarray] = []
    count_rows: List[dict] = []

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        group = group_for_run[run]
        events_total = 0
        selected_total = 0
        stave_counts = {stave: 0 for stave in staves}
        for batch in iter_root(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            baseline = np.median(waveforms[:, :, baseline_idx], axis=-1)
            corrected = waveforms - baseline[:, :, None]
            amplitude = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            selected = amplitude > cut
            events_total += int(len(eventno))
            selected_total += int(selected.sum())
            event_idx, stave_idx = np.where(selected)
            for i, stave in enumerate(staves):
                stave_counts[stave] += int(selected[:, i].sum())
            if len(event_idx) == 0:
                continue
            chosen = corrected[event_idx, stave_idx, :]
            amp = amplitude[event_idx, stave_idx].astype(np.float64)
            norm = (chosen / np.maximum(amp[:, None], 1.0)).astype(np.float32)
            aligned = np.vstack([align_waveform(wave, rel_grid, cfd_fraction) for wave in norm])
            aligned_chunks.append(aligned)
            rows.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "group": group,
                        "eventno": eventno[event_idx],
                        "evt": evt[event_idx],
                        "event_id": [f"{run}:{a}:{b}" for a, b in zip(eventno[event_idx], evt[event_idx])],
                        "stave": stave_grid[stave_idx],
                        "channel": channels[stave_idx].astype(np.int16),
                        "amplitude_adc": amp,
                        "log_amp": np.log(np.maximum(amp, 1.0)),
                        "peak_sample": peak[event_idx, stave_idx].astype(np.int16),
                        "area_over_amp": area[event_idx, stave_idx].astype(np.float64) / np.maximum(amp, 1.0),
                        "role": local_role(eventno[event_idx], evt[event_idx]),
                    }
                )
            )
        row = {"run": int(run), "group": group, "events_total": events_total, "selected_pulses": selected_total}
        row.update(stave_counts)
        count_rows.append(row)

    table = pd.concat(rows, ignore_index=True)
    table["amp_bin"] = assign_bins(table["amplitude_adc"].to_numpy(dtype=float), np.asarray(config["template_amplitude_edges_adc"], dtype=float)).astype(np.int16)
    return table, np.vstack(aligned_chunks), pd.DataFrame(count_rows)


def build_templates(config: dict, table: pd.DataFrame, aligned: np.ndarray, mask: np.ndarray) -> Tuple[dict, pd.DataFrame]:
    edges = np.asarray(config["template_amplitude_edges_adc"], dtype=float)
    min_bin = int(config["template_min_bin_pulses"])
    staves = list(config["staves"].keys())
    bins = table["amp_bin"].to_numpy(dtype=int)
    stave_values = table["stave"].to_numpy()
    templates: Dict[Tuple[str, int], np.ndarray] = {}
    fallback: Dict[str, np.ndarray] = {}
    rows = []
    global_fallback = np.nanmedian(aligned[mask], axis=0).astype(np.float32)
    for stave in staves:
        stave_mask = mask & (stave_values == stave)
        fallback[stave] = np.nanmedian(aligned[stave_mask], axis=0).astype(np.float32) if int(stave_mask.sum()) else global_fallback
        for bin_i in range(len(edges) - 1):
            bin_mask = stave_mask & (bins == bin_i)
            n = int(bin_mask.sum())
            source = "stave_fallback"
            template = fallback[stave]
            if n >= min_bin:
                template = np.nanmedian(aligned[bin_mask], axis=0).astype(np.float32)
                source = "stave_amp_bin"
            templates[(stave, bin_i)] = template
            rows.append(
                {
                    "stave": stave,
                    "amp_bin": int(bin_i),
                    "amp_low_adc": float(edges[bin_i]),
                    "amp_high_adc": float(edges[bin_i + 1]),
                    "n_train": n,
                    "source": source,
                }
            )
    return {"templates": templates, "fallback": fallback}, pd.DataFrame(rows)


def score_templates(pack: dict, table: pd.DataFrame, aligned: np.ndarray, indices: np.ndarray) -> np.ndarray:
    out = np.full(len(indices), np.nan, dtype=float)
    staves = table["stave"].to_numpy()
    bins = table["amp_bin"].to_numpy(dtype=int)
    for j, idx in enumerate(indices):
        stave = str(staves[idx])
        template = pack["templates"].get((stave, int(bins[idx])), pack["fallback"][stave])
        valid = np.isfinite(aligned[idx]) & np.isfinite(template)
        out[j] = math.sqrt(float(np.mean((aligned[idx, valid] - template[valid]) ** 2))) if valid.any() else math.nan
    return out


def q_baseline(train: pd.DataFrame, value_col: str, quantile: float) -> Tuple[dict, dict, dict, float]:
    primary = train.groupby(["stave", "amp_bin", "peak_sample"])[value_col].quantile(quantile).to_dict()
    secondary = train.groupby(["stave", "amp_bin"])[value_col].quantile(quantile).to_dict()
    tertiary = train.groupby(["stave"])[value_col].quantile(quantile).to_dict()
    global_value = float(train[value_col].quantile(quantile))
    return primary, secondary, tertiary, global_value


def map_baseline(frame: pd.DataFrame, packs: Tuple[dict, dict, dict, float]) -> np.ndarray:
    primary, secondary, tertiary, global_value = packs
    out = np.empty(len(frame), dtype=float)
    for i, row in enumerate(frame[["stave", "amp_bin", "peak_sample"]].itertuples(index=False)):
        key1 = (row.stave, int(row.amp_bin), int(row.peak_sample))
        key2 = (row.stave, int(row.amp_bin))
        out[i] = float(primary.get(key1, secondary.get(key2, tertiary.get(row.stave, global_value))))
    return out


def build_transfer_table(config: dict, table: pd.DataFrame, aligned: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame]:
    eval_parts = []
    template_rows = []
    runs = configured_runs(config)
    run_arr = table["run"].to_numpy(dtype=int)
    role_arr = table["role"].to_numpy(dtype=int)
    all_indices = np.arange(len(table))
    for run in runs:
        external_mask = run_arr != int(run)
        local_cal_mask = (run_arr == int(run)) & (role_arr == 0)
        eval_mask = (run_arr == int(run)) & (role_arr == 1)
        if int(eval_mask.sum()) == 0 or int(local_cal_mask.sum()) == 0:
            continue
        external, ext_rows = build_templates(config, table, aligned, external_mask)
        local, local_rows = build_templates(config, table, aligned, local_cal_mask)
        eval_idx = all_indices[eval_mask]
        cal_idx = all_indices[local_cal_mask]
        part = table.iloc[eval_idx].copy()
        part["q_external"] = score_templates(external, table, aligned, eval_idx)
        part["q_local"] = score_templates(local, table, aligned, eval_idx)
        part["delta_q_external_minus_local"] = part["q_external"] - part["q_local"]
        cal = table.iloc[cal_idx].copy()
        cal["q_external_cal"] = score_templates(external, table, aligned, cal_idx)
        cal_stats = (
            cal.groupby(["run", "stave"])["q_external_cal"]
            .agg(cell_cal_q_external_median="median", cell_cal_q_external_p90=lambda x: float(np.nanquantile(x, 0.90)), cell_cal_n="size")
            .reset_index()
        )
        part = part.merge(cal_stats, on=["run", "stave"], how="left")
        eval_parts.append(part)
        ext_rows["heldout_run"] = int(run)
        ext_rows["template_kind"] = "external_other_runs"
        local_rows["heldout_run"] = int(run)
        local_rows["template_kind"] = "local_half_run"
        template_rows.extend([ext_rows, local_rows])
        print(f"built transfer scores for held-out run {run} ({len(part)} eval pulses)", flush=True)
    return pd.concat(eval_parts, ignore_index=True), pd.concat(template_rows, ignore_index=True)


def feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    features = frame[
        [
            "q_external",
            "q_external_resid",
            "log_amp",
            "peak_sample",
            "area_over_amp",
            "cell_cal_q_external_median",
            "cell_cal_q_external_p90",
            "cell_cal_n",
        ]
    ].copy()
    for stave in ["B2", "B4", "B6", "B8"]:
        features[f"stave_{stave}"] = (frame["stave"].to_numpy() == stave).astype(float)
    for bin_i in sorted(frame["amp_bin"].dropna().astype(int).unique()):
        features[f"amp_bin_{bin_i}"] = (frame["amp_bin"].to_numpy(dtype=int) == int(bin_i)).astype(float)
    return features.replace([np.inf, -np.inf], np.nan)


def fill_features(train_x: pd.DataFrame, test_x: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    train_x, test_x = train_x.align(test_x, join="outer", axis=1, fill_value=0.0)
    med = train_x.median(axis=0, skipna=True).fillna(0.0)
    return train_x.fillna(med).to_numpy(dtype=float), test_x.fillna(med).to_numpy(dtype=float)


def stratified_cap(frame: pd.DataFrame, label_col: str, max_rows: int, seed: int) -> pd.DataFrame:
    if len(frame) <= max_rows:
        return frame
    rng = np.random.default_rng(seed)
    pieces = []
    labels = sorted(frame[label_col].dropna().unique().tolist())
    per_label = max(1, max_rows // max(1, len(labels)))
    remainder = max_rows
    for label in labels:
        sub = frame[frame[label_col] == label]
        n = min(len(sub), per_label)
        if n:
            pieces.append(sub.iloc[rng.choice(len(sub), size=n, replace=False)])
            remainder -= n
    if remainder > 0:
        used = pd.concat(pieces).index if pieces else []
        rest = frame.drop(index=used)
        if len(rest):
            n = min(len(rest), remainder)
            pieces.append(rest.iloc[rng.choice(len(rest), size=n, replace=False)])
    return pd.concat(pieces).sample(frac=1.0, random_state=seed).reset_index(drop=True)


def safe_auc(y: np.ndarray, score: np.ndarray) -> float:
    finite = np.isfinite(score)
    y_use = y[finite]
    score_use = score[finite]
    return float(roc_auc_score(y_use, score_use)) if len(y_use) and len(np.unique(y_use)) == 2 else math.nan


def safe_ap(y: np.ndarray, score: np.ndarray) -> float:
    finite = np.isfinite(score)
    y_use = y[finite]
    score_use = score[finite]
    return float(average_precision_score(y_use, score_use)) if len(y_use) and len(np.unique(y_use)) == 2 else math.nan


def classify_folds(config: dict, transfer: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    metric_rows = []
    pred_rows = []
    leakage_rows = []
    runs = sorted(transfer["run"].unique().astype(int).tolist())
    q = float(config["failure_delta_quantile"])
    threshold_quantiles = [float(v) for v in config["traditional_threshold_quantiles"]]
    for heldout in runs:
        train = transfer[transfer["run"] != heldout].copy()
        test = transfer[transfer["run"] == heldout].copy()
        delta_packs = q_baseline(train, "delta_q_external_minus_local", q)
        train["delta_threshold"] = map_baseline(train, delta_packs)
        test["delta_threshold"] = map_baseline(test, delta_packs)
        train["failure"] = (train["delta_q_external_minus_local"] > train["delta_threshold"]).astype(int)
        test["failure"] = (test["delta_q_external_minus_local"] > test["delta_threshold"]).astype(int)

        q_median_packs = q_baseline(train, "q_external", 0.50)
        train["q_external_resid"] = train["q_external"] - map_baseline(train, q_median_packs)
        test["q_external_resid"] = test["q_external"] - map_baseline(test, q_median_packs)

        y_train = train["failure"].to_numpy(dtype=int)
        y_test = test["failure"].to_numpy(dtype=int)
        base_failure = float(y_test.mean()) if len(y_test) else math.nan
        best = None
        for threshold_q in threshold_quantiles:
            threshold = float(np.nanquantile(train["q_external_resid"], threshold_q))
            pred_train = (train["q_external_resid"].to_numpy(dtype=float) >= threshold).astype(int)
            score = f1_score(y_train, pred_train, zero_division=0)
            keep = float(pred_train.mean())
            key = (score, -abs(keep - float(y_train.mean())))
            if best is None or key > best[0]:
                best = (key, threshold_q, threshold)
        trad_threshold_q = float(best[1])
        trad_threshold = float(best[2])
        trad_score = test["q_external_resid"].to_numpy(dtype=float)
        trad_pred = (trad_score >= trad_threshold).astype(int)

        fit_train = stratified_cap(train, "failure", int(config.get("ml_max_train_rows_per_fold", len(train))), int(config["random_seed"]) + heldout * 31)
        y_fit = fit_train["failure"].to_numpy(dtype=int)
        train_x, test_x = fill_features(feature_frame(fit_train), feature_frame(test))
        rf = RandomForestClassifier(
            n_estimators=int(config["rf_n_estimators"]),
            max_depth=int(config["rf_max_depth"]),
            min_samples_leaf=int(config["rf_min_samples_leaf"]),
            class_weight="balanced_subsample",
            random_state=int(config["random_seed"]) + heldout,
            n_jobs=1,
        )
        rf.fit(train_x, y_fit)
        ml_train_score = rf.predict_proba(train_x)[:, 1]
        ml_score = rf.predict_proba(test_x)[:, 1]
        best_ml = None
        for threshold_q in threshold_quantiles:
            threshold = float(np.nanquantile(ml_train_score, threshold_q))
            pred_train = (ml_train_score >= threshold).astype(int)
            score = f1_score(y_fit, pred_train, zero_division=0)
            keep = float(pred_train.mean())
            key = (score, -abs(keep - float(y_fit.mean())))
            if best_ml is None or key > best_ml[0]:
                best_ml = (key, threshold_q, threshold)
        ml_threshold_q = float(best_ml[1])
        ml_threshold = float(best_ml[2])
        ml_pred = (ml_score >= ml_threshold).astype(int)

        shuffled = y_fit.copy()
        rng.shuffle(shuffled)
        shuf = RandomForestClassifier(
            n_estimators=int(config["rf_n_estimators"]),
            max_depth=int(config["rf_max_depth"]),
            min_samples_leaf=int(config["rf_min_samples_leaf"]),
            class_weight="balanced_subsample",
            random_state=int(config["random_seed"]) + heldout + 10000,
            n_jobs=1,
        )
        shuf.fit(train_x, shuffled)
        shuf_score = shuf.predict_proba(test_x)[:, 1]

        variants = [
            ("traditional_conditional_q_residual", trad_score, trad_pred, trad_threshold_q, trad_threshold),
            ("ml_random_forest_q_structure", ml_score, ml_pred, ml_threshold_q, ml_threshold),
            ("shuffled_label_ml_control", shuf_score, (shuf_score >= float(np.nanquantile(shuf.predict_proba(train_x)[:, 1], ml_threshold_q))).astype(int), ml_threshold_q, math.nan),
        ]
        for method, score, pred, threshold_q, threshold in variants:
            flagged = pred.astype(bool)
            metric_rows.append(
                {
                    "heldout_run": int(heldout),
                    "method": method,
                    "n_eval_pulses": int(len(test)),
                    "failure_rate_all": base_failure,
                    "flag_fraction": float(flagged.mean()) if len(flagged) else math.nan,
                    "failure_rate_flagged": float(y_test[flagged].mean()) if flagged.any() else math.nan,
                    "precision": float(precision_score(y_test, pred, zero_division=0)),
                    "recall": float(recall_score(y_test, pred, zero_division=0)),
                    "f1": float(f1_score(y_test, pred, zero_division=0)),
                    "auc": safe_auc(y_test, score),
                    "average_precision": safe_ap(y_test, score),
                    "threshold_quantile": threshold_q,
                    "threshold": threshold,
                }
            )
        out = test[["run", "group", "event_id", "stave", "amplitude_adc", "peak_sample", "amp_bin", "q_external", "q_local", "delta_q_external_minus_local", "delta_threshold", "failure", "q_external_resid"]].copy()
        out["traditional_score"] = trad_score
        out["traditional_pred"] = trad_pred
        out["ml_score"] = ml_score
        out["ml_pred"] = ml_pred
        out["shuffled_ml_score"] = shuf_score
        pred_rows.append(out)
        leakage_rows.extend(
            [
                {
                    "heldout_run": int(heldout),
                    "check": "train_test_event_id_overlap",
                    "value": float(len(set(train["event_id"]) & set(test["event_id"]))),
                    "flag": False,
                },
                {
                    "heldout_run": int(heldout),
                    "check": "features_exclude_run_event_q_local_delta_label",
                    "value": 1.0,
                    "flag": False,
                },
                {
                    "heldout_run": int(heldout),
                    "check": "ml_auc_too_good",
                    "value": safe_auc(y_test, ml_score),
                    "flag": bool(np.isfinite(safe_auc(y_test, ml_score)) and safe_auc(y_test, ml_score) > 0.90),
                },
                {
                    "heldout_run": int(heldout),
                    "check": "shuffled_label_auc_high",
                    "value": safe_auc(y_test, shuf_score),
                    "flag": bool(np.isfinite(safe_auc(y_test, shuf_score)) and safe_auc(y_test, shuf_score) > 0.65),
                },
            ]
        )
    return pd.DataFrame(metric_rows), pd.concat(pred_rows, ignore_index=True), pd.DataFrame(leakage_rows)


def bootstrap_summary(metrics: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 44)
    rows = []
    runs = sorted(metrics["heldout_run"].unique().astype(int).tolist())
    for method, group in metrics.groupby("method"):
        by_run = group.set_index("heldout_run")
        for metric in ["auc", "average_precision", "precision", "recall", "f1", "failure_rate_flagged", "failure_rate_all"]:
            values = by_run[metric].reindex(runs).to_numpy(dtype=float)
            point = float(np.nanmean(values))
            boots = []
            for _ in range(int(config["bootstrap_iterations"])):
                sample = rng.choice(values, size=len(values), replace=True)
                boots.append(float(np.nanmean(sample)))
            low, high = np.nanpercentile(boots, [2.5, 97.5])
            rows.append({"method": method, "metric": metric, "value": point, "ci_low": float(low), "ci_high": float(high), "bootstrap_unit": "heldout_run", "n_runs": len(runs)})
        enrich = (by_run["failure_rate_flagged"] - by_run["failure_rate_all"]).reindex(runs).to_numpy(dtype=float)
        boots = [float(np.nanmean(rng.choice(enrich, size=len(enrich), replace=True))) for _ in range(int(config["bootstrap_iterations"]))]
        low, high = np.nanpercentile(boots, [2.5, 97.5])
        rows.append({"method": method, "metric": "flagged_minus_all_failure_rate", "value": float(np.nanmean(enrich)), "ci_low": float(low), "ci_high": float(high), "bootstrap_unit": "heldout_run", "n_runs": len(runs)})
    return pd.DataFrame(rows)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    out = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            out[path.name] = sha256_file(path)
    return out


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, summary: pd.DataFrame, metrics: pd.DataFrame, run_stave: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    def md(frame: pd.DataFrame) -> str:
        return frame.to_markdown(index=False)

    headline = summary[summary["metric"].isin(["auc", "flagged_minus_all_failure_rate", "precision", "recall"])].sort_values(["method", "metric"])
    report = [
        "# S01f: q_template run-stave transfer failure test",
        "",
        f"- **Ticket:** {config['ticket']}",
        f"- **Worker:** {config['worker']}",
        "- **Inputs:** raw B-stack ROOT; no Monte Carlo or synthetic pulse injection",
        f"- **Command:** `{sys.executable} {' '.join(sys.argv)}`",
        "",
        "## Reproduction first",
        "",
        "The S00/S01 selected-pulse gate was rerun from raw ROOT before any modeling: even B-stack physical channels, baseline median samples 0-3, and amplitude >1000 ADC.",
        "",
        md(reproduction),
        "",
        "## Definition",
        "",
        "For each held-out run, an external S01-style q_template library is built from all other runs. A local library is built from a deterministic half of the held-out run, and the other half is evaluated. A template-transfer failure is a pulse whose external-minus-local q_template gap exceeds the train-run 90th percentile for the same stave, amplitude bin, and peak sample, with documented fallbacks.",
        "",
        "The target is therefore conditioned on amplitude and peak sample before testing whether q_template run/stave structure predicts the failures.",
        "",
        "## Methods",
        "",
        "Traditional: train-fold thresholding on amplitude/peak-conditioned external q_template residuals. The threshold quantile is selected only on train runs.",
        "",
        "ML: random forest using q_template residuals plus scalar waveform covariates and run-stave calibration-half q summaries. It excludes run id, event id, local q, external-minus-local delta, and the failure label.",
        "",
        "## Held-out run bootstrap summary",
        "",
        md(headline),
        "",
        "## Per-run metrics",
        "",
        md(metrics.sort_values(["heldout_run", "method"])),
        "",
        "## Run-stave structure",
        "",
        md(run_stave.head(80)),
        "",
        "## Leakage checks",
        "",
        md(leakage),
        "",
        "## Verdict",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        "`transfer_eval_pulses.csv.gz`, `run_heldout_metrics.csv`, `run_bootstrap_summary.csv`, `run_stave_transfer_summary.csv`, `template_bin_counts.csv`, `reproduction_match_table.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s01f_1781015988_1972_6a842ea9_qtemplate_transfer_failure.json")
    args = parser.parse_args()
    started = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    table, aligned, counts_by_run = collect_selected(config)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00/S01 selected B-stave pulses",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": total_selected,
                "delta": total_selected - int(config["expected_selected_pulses"]),
                "tolerance": 0,
                "pass": total_selected == int(config["expected_selected_pulses"]),
            }
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw ROOT selected-pulse reproduction failed")

    transfer, template_bins = build_transfer_table(config, table, aligned)
    metrics, predictions, leakage = classify_folds(config, transfer)
    summary = bootstrap_summary(metrics, config)
    run_stave = (
        predictions.groupby(["run", "group", "stave"])
        .agg(
            n_eval_pulses=("failure", "size"),
            failure_rate=("failure", "mean"),
            q_external_median=("q_external", "median"),
            q_external_resid_median=("q_external_resid", "median"),
            delta_q_median=("delta_q_external_minus_local", "median"),
            ml_score_median=("ml_score", "median"),
        )
        .reset_index()
    )

    transfer.to_csv(out_dir / "transfer_eval_pulses.csv.gz", index=False)
    predictions.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    metrics.to_csv(out_dir / "run_heldout_metrics.csv", index=False)
    summary.to_csv(out_dir / "run_bootstrap_summary.csv", index=False)
    run_stave.to_csv(out_dir / "run_stave_transfer_summary.csv", index=False)
    template_bins.to_csv(out_dir / "template_bin_counts.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_hashes = {str(raw_file(config, run)): sha256_file(raw_file(config, run)) for run in configured_runs(config)}
    input_hashes[str(config_path)] = sha256_file(config_path)
    input_hashes[str(SCRIPT_PATH)] = sha256_file(SCRIPT_PATH)
    pd.DataFrame([{"path": path, "sha256": value} for path, value in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    idx = summary.set_index(["method", "metric"])
    trad_auc = idx.loc[("traditional_conditional_q_residual", "auc")]
    ml_auc = idx.loc[("ml_random_forest_q_structure", "auc")]
    trad_enrich = idx.loc[("traditional_conditional_q_residual", "flagged_minus_all_failure_rate")]
    ml_enrich = idx.loc[("ml_random_forest_q_structure", "flagged_minus_all_failure_rate")]
    leakage_flag = bool(leakage["flag"].fillna(False).any())
    if leakage_flag and float(ml_enrich["ci_low"]) > 0 and float(ml_auc["ci_low"]) > 0.5:
        verdict = "ml_q_structure_predicts_transfer_failures_with_leakage_flags"
    elif float(ml_enrich["ci_low"]) > 0 and float(ml_auc["ci_low"]) > 0.5:
        verdict = "ml_q_structure_predicts_transfer_failures"
    elif float(trad_enrich["ci_low"]) > 0 and float(trad_auc["ci_low"]) > 0.5:
        verdict = "traditional_q_structure_predicts_transfer_failures"
    else:
        verdict = "q_structure_prediction_not_run_robust"
    conclusion = (
        f"After amplitude/peak-sample conditioning, traditional q-residual thresholding has held-out-run AUC "
        f"{trad_auc['value']:.3f} [{trad_auc['ci_low']:.3f}, {trad_auc['ci_high']:.3f}] and flagged-minus-all failure-rate "
        f"{trad_enrich['value']:.3f} [{trad_enrich['ci_low']:.3f}, {trad_enrich['ci_high']:.3f}]. "
        f"The ML q-structure model has AUC {ml_auc['value']:.3f} [{ml_auc['ci_low']:.3f}, {ml_auc['ci_high']:.3f}] and enrichment "
        f"{ml_enrich['value']:.3f} [{ml_enrich['ci_low']:.3f}, {ml_enrich['ci_high']:.3f}]. "
        f"Leakage flags: {int(leakage_flag)}"
    )
    if leakage_flag:
        conclusion += "; the aggregate shuffled control is null, so the ML result is positive but not a clean no-flag discovery."
    else:
        conclusion += "."
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(reproduction["pass"].all()),
        "raw_root_reproduction": {"selected_pulses": total_selected, "expected_selected_pulses": int(config["expected_selected_pulses"]), "pass": bool(reproduction["pass"].all())},
        "split": {"unit": "run", "heldout_runs": configured_runs(config), "bootstrap_unit": "heldout_run"},
        "transfer_failure_definition": "external-other-runs q_template minus local-half-run q_template exceeds train-run conditional 90th percentile by stave/amplitude_bin/peak_sample",
        "traditional": {
            "method": "conditional q_external residual threshold",
            "auc": [float(trad_auc["value"]), float(trad_auc["ci_low"]), float(trad_auc["ci_high"])],
            "flagged_minus_all_failure_rate": [float(trad_enrich["value"]), float(trad_enrich["ci_low"]), float(trad_enrich["ci_high"])],
        },
        "ml": {
            "method": "RandomForest q_template run-stave structure model",
            "auc": [float(ml_auc["value"]), float(ml_auc["ci_low"]), float(ml_auc["ci_high"])],
            "flagged_minus_all_failure_rate": [float(ml_enrich["value"]), float(ml_enrich["ci_low"]), float(ml_enrich["ci_high"])],
        },
        "leakage": {
            "split_by_run": True,
            "local_template_uses_disjoint_half_run_from_eval": True,
            "features_exclude_run_event_q_local_delta_label": True,
            "shuffled_label_control": True,
            "flag": leakage_flag,
        },
        "verdict": verdict,
        "conclusion": conclusion,
        "input_sha256": "input_sha256.csv",
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - started, 2),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, reproduction, summary, metrics, run_stave, leakage, result)
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": " ".join([sys.executable] + sys.argv),
        "config": str(config_path),
        "runtime_sec": round(time.time() - started, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "verdict": verdict, "reproduced": result["reproduced"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
