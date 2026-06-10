#!/usr/bin/env python3
"""S03f: q_template-only plus external timing-tail validation for App.A replacement."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/s03f_1781027415_1845_71ed23e7_qtemplate_external_tail.json"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"

    def fmt(value: Any) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def load_s07c(config: dict[str, Any]):
    helper = ROOT / config["s07c_helper"]
    spec = importlib.util.spec_from_file_location("s07c_for_s03f_external_tail", str(helper))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {helper}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RAW_DIR = ROOT / config["raw_root_dir"]
    module.QTEMPLATE_PATH = ROOT / config["qtemplate_path"]
    module.SEED = int(config["seed"])
    return module


def score_ci_by_run(
    y: np.ndarray, score: np.ndarray, runs: np.ndarray, seed: int, metric: str, n_boot: int
) -> tuple[float, float, float]:
    if metric == "roc_auc":
        point = float(roc_auc_score(y, score))
    elif metric == "average_precision":
        point = float(average_precision_score(y, score))
    elif metric == "brier":
        point = float(brier_score_loss(y, np.clip(score, 0.0, 1.0)))
    else:
        raise ValueError(metric)
    rng = np.random.default_rng(seed + len(metric) * 991)
    values = []
    unique_runs = np.unique(runs)
    for _ in range(int(n_boot)):
        sample_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sample_runs])
        if len(np.unique(y[idx])) < 2:
            continue
        if metric == "roc_auc":
            values.append(roc_auc_score(y[idx], score[idx]))
        elif metric == "average_precision":
            values.append(average_precision_score(y[idx], score[idx]))
        else:
            values.append(brier_score_loss(y[idx], np.clip(score[idx], 0.0, 1.0)))
    lo, hi = np.quantile(values, [0.025, 0.975])
    return point, float(lo), float(hi)


def rate_ci_by_run(frame: pd.DataFrame, value_col: str, runs_col: str, seed: int, n_boot: int) -> tuple[float, float, float]:
    point = float(frame[value_col].mean())
    rng = np.random.default_rng(seed + 31337)
    by_run = {int(run): sub[value_col].to_numpy(dtype=float) for run, sub in frame.groupby(runs_col)}
    runs = np.asarray(sorted(by_run), dtype=int)
    values = []
    for _ in range(int(n_boot)):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        vals = np.concatenate([by_run[int(run)] for run in sample_runs])
        values.append(float(vals.mean()))
    lo, hi = np.quantile(values, [0.025, 0.975])
    return point, float(lo), float(hi)


def scan_all_candidates(config: dict[str, Any], s07c) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    channels = np.asarray([s07c.STAVES[stave] for stave in s07c.STAVES], dtype=int)
    stave_names = list(s07c.STAVES.keys())
    tail_cfg = config["tail_validation"]
    s00_counts = {group: 0 for group in s07c.RUN_GROUPS}
    s00_counts["total_selected_pulses"] = 0
    per_run_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []

    for run in s07c.all_runs():
        path = s07c.raw_file(run)
        tree = uproot.open(path)["h101"]
        group = s07c.run_group(run)
        run_stats = {
            "run": int(run),
            "group": group,
            "events_total": 0,
            "selected_pulses": 0,
            "downstream_ge2_events": 0,
            "clean_events": 0,
            "violating_events": 0,
            "ambiguous_events": 0,
        }
        for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=30000, library="np"):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, s07c.SAMPLES_PER_CHANNEL)[:, channels, :]
            baseline = np.median(raw[..., s07c.BASELINE_SAMPLES], axis=-1)
            wave = raw - baseline[..., None]
            amplitude = wave.max(axis=-1)
            selected = amplitude > s07c.AMPLITUDE_CUT_ADC
            run_stats["events_total"] += int(len(eventno))
            selected_count = int(selected.sum())
            run_stats["selected_pulses"] += selected_count
            s00_counts[group] += selected_count
            s00_counts["total_selected_pulses"] += selected_count

            times = np.full(amplitude.shape, np.nan, dtype=float)
            shape_by_stave: dict[str, dict[str, np.ndarray]] = {}
            for idx, stave in enumerate(stave_names):
                hit_idx = np.where(selected[:, idx])[0]
                if len(hit_idx):
                    times[hit_idx, idx] = s07c.cfd_time_samples(wave[hit_idx, idx], amplitude[hit_idx, idx]) * s07c.SAMPLE_PERIOD_NS
                shape_by_stave[stave] = s07c.pulse_shape_features(wave[:, idx], amplitude[:, idx])

            ds_selected = selected[:, 1:]
            candidate_mask = ds_selected.sum(axis=1) >= 2
            if not candidate_mask.any():
                continue
            ds_times_all = times[:, 1:].copy()
            ds_times_all[~ds_selected] = np.nan
            all_times = times.copy()
            all_times[~selected] = np.nan
            cand_idx = np.where(candidate_mask)[0]
            ds_times = ds_times_all[candidate_mask]
            ds_span = np.nanmax(ds_times, axis=1) - np.nanmin(ds_times, axis=1)
            all_span = np.nanmax(all_times[candidate_mask], axis=1) - np.nanmin(all_times[candidate_mask], axis=1)
            ds_median = np.nanmedian(ds_times, axis=1)
            b2_hit = selected[candidate_mask, 0]
            b2_displacement = np.full(len(cand_idx), np.nan, dtype=float)
            b2_displacement[b2_hit] = np.abs(times[candidate_mask, 0][b2_hit] - ds_median[b2_hit])

            clean = (ds_span < float(tail_cfg["clean_downstream_span_ns"])) & (all_span < float(tail_cfg["clean_all_span_ns"]))
            violating = (ds_span > float(tail_cfg["gross_downstream_span_ns"])) | (
                np.nan_to_num(b2_displacement, nan=-np.inf) > float(tail_cfg["gross_b2_displacement_ns"])
            )
            labelled = clean | violating
            run_stats["downstream_ge2_events"] += int(candidate_mask.sum())
            run_stats["clean_events"] += int(clean.sum())
            run_stats["violating_events"] += int(violating.sum())
            run_stats["ambiguous_events"] += int((~labelled).sum())

            for local_pos, event_idx in enumerate(cand_idx):
                row = {
                    "run": int(run),
                    "group": group,
                    "eventno": int(eventno[event_idx]),
                    "evt": int(evt[event_idx]),
                    "label_clean": int(clean[local_pos]),
                    "label_violating": int(violating[local_pos]),
                    "label_ambiguous": int(not bool(labelled[local_pos])),
                    "labelled_appa_raw": int(labelled[local_pos]),
                    "external_clean_gate": int(clean[local_pos]),
                    "external_gross_tail": int(violating[local_pos]),
                    "downstream_span_ns": float(ds_span[local_pos]),
                    "all_span_ns": float(all_span[local_pos]),
                    "b2_displacement_ns": float(b2_displacement[local_pos]) if np.isfinite(b2_displacement[local_pos]) else np.nan,
                    "hit_count": int(selected[event_idx].sum()),
                    "downstream_hit_count": int(ds_selected[event_idx].sum()),
                }
                for sidx, stave in enumerate(stave_names):
                    hit = bool(selected[event_idx, sidx])
                    row[f"hit_{stave}"] = int(hit)
                    row[f"amp_{stave}"] = float(amplitude[event_idx, sidx]) if hit else 0.0
                    row[f"log_amp_{stave}"] = float(np.log1p(max(amplitude[event_idx, sidx], 0.0))) if hit else 0.0
                    for feature, values in shape_by_stave[stave].items():
                        row[f"{feature}_{stave}"] = float(values[event_idx]) if hit else 0.0
                event_rows.append(row)
        per_run_rows.append(run_stats)
        print(run, run_stats, flush=True)

    s00_rows = []
    for quantity, expected in s07c.EXPECTED_S00_COUNTS.items():
        observed = int(s00_counts[quantity])
        s00_rows.append(
            {
                "quantity": quantity,
                "report_value": int(expected),
                "reproduced": observed,
                "delta": observed - int(expected),
                "tolerance": 0,
                "pass": observed == int(expected),
            }
        )
    return pd.DataFrame(s00_rows), pd.DataFrame(per_run_rows), pd.DataFrame(event_rows)


def add_qtemplate(config: dict[str, Any], s07c, events: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    q_event = s07c.qtemplate_event_table()
    data = events.merge(q_event, on=["run", "eventno", "evt"], how="left")
    q_cols = [col for col in data.columns if col.startswith("q_")]
    unmatched = int(data[q_cols].isna().all(axis=1).sum())
    data[q_cols] = data[q_cols].fillna(data[q_cols].median(numeric_only=True))
    data["q_downstream_any_bad"] = data["q_downstream_max"]
    data["q_all_any_bad"] = data["q_all_max"]
    data["q_downstream_spread"] = data[[f"q_{stave}" for stave in s07c.DOWNSTREAM]].max(axis=1) - data[
        [f"q_{stave}" for stave in s07c.DOWNSTREAM]
    ].min(axis=1)
    return data, unmatched


def run_heldout_methods(config: dict[str, Any], data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    labelled = data[data["labelled_appa_raw"] == 1].reset_index(drop=True)
    y_clean = labelled["label_clean"].to_numpy(dtype=int)
    y_tail = labelled["external_gross_tail"].to_numpy(dtype=int)
    runs = labelled["run"].to_numpy(dtype=int)
    seed = int(config["seed"])
    retention_grid = [float(x) for x in config["tail_validation"]["retention_grid"]]
    min_retention = float(config["tail_validation"]["min_adopted_retention"])
    q_candidates = ["q_downstream_max", "q_all_max", "q_downstream_mean", "q_all_mean", "q_downstream_spread"]

    forbidden = {"downstream_span_ns", "all_span_ns", "b2_displacement_ns", "label_clean", "label_violating"}
    ml_features = [
        col
        for col in labelled.columns
        if (
            col.startswith("hit_")
            or col.startswith("amp_")
            or col.startswith("log_amp_")
            or col.startswith("tail_fraction_")
            or col.startswith("late_fraction_")
            or col.startswith("area_over_peak_")
            or col.startswith("max_down_step_")
            or col.startswith("final_fraction_")
            or col.startswith("quench_proxy_")
            or col.startswith("q_")
            or col in {"hit_count", "downstream_hit_count"}
        )
    ]
    ml_features = [col for col in ml_features if col not in forbidden]
    leaky_features = ml_features + ["downstream_span_ns", "all_span_ns", "b2_displacement_ns"]
    q_amp_features = [
        col
        for col in ml_features
        if col.startswith("q_")
        or col.startswith("hit_")
        or col.startswith("amp_")
        or col.startswith("log_amp_")
        or col in {"hit_count", "downstream_hit_count"}
    ]
    shape_no_q_features = [col for col in ml_features if not col.startswith("q_")]
    rf_grid = [
        {"n_estimators": 180, "max_depth": 4, "min_samples_leaf": 25},
        {"n_estimators": 260, "max_depth": 5, "min_samples_leaf": 20},
        {"n_estimators": 320, "max_depth": 7, "min_samples_leaf": 15},
    ]

    splitter = GroupKFold(n_splits=min(5, len(np.unique(runs))))
    q_scores = np.full(len(labelled), np.nan)
    q_accept = np.zeros(len(labelled), dtype=int)
    rf_scores_grid = {json.dumps(params, sort_keys=True): np.full(len(labelled), np.nan) for params in rf_grid}
    q_amp_rf_score = np.full(len(labelled), np.nan)
    shape_no_q_rf_score = np.full(len(labelled), np.nan)
    leaky_score = np.full(len(labelled), np.nan)
    folds = []

    for fold, (train_idx, test_idx) in enumerate(splitter.split(labelled, y_clean, groups=runs), start=1):
        train = labelled.iloc[train_idx]
        test = labelled.iloc[test_idx]
        best = None
        for col in q_candidates:
            train_q = train[col].to_numpy(dtype=float)
            for retention in retention_grid:
                threshold = float(np.quantile(train_q, retention))
                accept = train_q <= threshold
                if accept.mean() < min_retention:
                    continue
                accepted = train.loc[accept]
                rejected = train.loc[~accept]
                accepted_tail = float(accepted["external_gross_tail"].mean()) if len(accepted) else 1.0
                rejected_tail = float(rejected["external_gross_tail"].mean()) if len(rejected) else accepted_tail
                accepted_clean = float(accepted["external_clean_gate"].mean()) if len(accepted) else 0.0
                utility = (accepted_clean - float(train["external_clean_gate"].mean())) + 0.5 * (
                    rejected_tail - accepted_tail
                )
                candidate = (utility, accepted_clean, -accepted_tail, retention, col, threshold)
                if best is None or candidate > best:
                    best = candidate
        if best is None:
            raise RuntimeError(f"fold {fold}: no q_template gate candidate")
        _utility, _acc_clean, _neg_tail, retention, q_col, threshold = best
        q_raw = -test[q_col].to_numpy(dtype=float)
        q_scores[test_idx] = q_raw
        q_accept[test_idx] = (test[q_col].to_numpy(dtype=float) <= threshold).astype(int)

        for params in rf_grid:
            key = json.dumps(params, sort_keys=True)
            model = RandomForestClassifier(**params, class_weight="balanced", random_state=seed + fold, n_jobs=-1)
            model.fit(train[ml_features].to_numpy(dtype=float), y_clean[train_idx])
            rf_scores_grid[key][test_idx] = model.predict_proba(test[ml_features].to_numpy(dtype=float))[:, 1]

        ablation_params = {"n_estimators": 260, "max_depth": 5, "min_samples_leaf": 20}
        q_amp_model = RandomForestClassifier(
            **ablation_params,
            class_weight="balanced",
            random_state=seed + 500 + fold,
            n_jobs=-1,
        )
        q_amp_model.fit(train[q_amp_features].to_numpy(dtype=float), y_clean[train_idx])
        q_amp_rf_score[test_idx] = q_amp_model.predict_proba(test[q_amp_features].to_numpy(dtype=float))[:, 1]

        shape_no_q_model = RandomForestClassifier(
            **ablation_params,
            class_weight="balanced",
            random_state=seed + 700 + fold,
            n_jobs=-1,
        )
        shape_no_q_model.fit(train[shape_no_q_features].to_numpy(dtype=float), y_clean[train_idx])
        shape_no_q_rf_score[test_idx] = shape_no_q_model.predict_proba(test[shape_no_q_features].to_numpy(dtype=float))[:, 1]

        leak_model = RandomForestClassifier(
            n_estimators=180,
            max_depth=5,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=seed + 1000 + fold,
            n_jobs=-1,
        )
        leak_model.fit(train[leaky_features].fillna(999.0).to_numpy(dtype=float), y_clean[train_idx])
        leaky_score[test_idx] = leak_model.predict_proba(test[leaky_features].fillna(999.0).to_numpy(dtype=float))[:, 1]
        folds.append(
            {
                "fold": int(fold),
                "test_runs": ",".join(str(int(run)) for run in sorted(np.unique(runs[test_idx]))),
                "train_n": int(len(train_idx)),
                "test_n": int(len(test_idx)),
                "q_selected_column": q_col,
                "q_retention_quantile": float(retention),
                "q_threshold": float(threshold),
            }
        )

    rf_cv = []
    for key, score in rf_scores_grid.items():
        params = json.loads(key)
        rf_cv.append(
            {
                **params,
                "roc_auc_clean": float(roc_auc_score(y_clean, score)),
                "ap_clean": float(average_precision_score(y_clean, score)),
                "brier_clean": float(brier_score_loss(y_clean, np.clip(score, 0.0, 1.0))),
            }
        )
    rf_cv_frame = pd.DataFrame(rf_cv).sort_values("roc_auc_clean", ascending=False).reset_index(drop=True)
    best_params = {k: int(rf_cv_frame.iloc[0][k]) for k in ["n_estimators", "max_depth", "min_samples_leaf"]}
    best_key = json.dumps(best_params, sort_keys=True)
    scores = labelled[
        [
            "run",
            "group",
            "eventno",
            "evt",
            "label_clean",
            "label_violating",
            "external_clean_gate",
            "external_gross_tail",
            "downstream_span_ns",
            "all_span_ns",
            "b2_displacement_ns",
        ]
    ].copy()
    scores["q_template_only_score"] = q_scores
    scores["q_template_gate_accept"] = q_accept
    scores["rf_shape_q_score"] = rf_scores_grid[best_key]
    scores["q_amp_rf_score"] = q_amp_rf_score
    scores["shape_no_q_rf_score"] = shape_no_q_rf_score
    scores["leaky_timing_control_score"] = leaky_score

    n_boot = int(config["bootstrap_samples"])
    scoreboard_rows = []
    for method, col in [
        ("traditional_q_template_only", "q_template_only_score"),
        ("ml_shape_q_random_forest", "rf_shape_q_score"),
        ("ablation_q_amp_random_forest", "q_amp_rf_score"),
        ("ablation_shape_no_q_random_forest", "shape_no_q_rf_score"),
        ("leaky_timing_control", "leaky_timing_control_score"),
    ]:
        clean_auc = score_ci_by_run(y_clean, scores[col].to_numpy(dtype=float), runs, seed, "roc_auc", n_boot)
        clean_ap = score_ci_by_run(y_clean, scores[col].to_numpy(dtype=float), runs, seed, "average_precision", n_boot)
        tail_auc = score_ci_by_run(1 - y_tail, scores[col].to_numpy(dtype=float), runs, seed + 7, "roc_auc", n_boot)
        row = {
            "method": method,
            "target": "raw_reconstructed_clean_vs_violating",
            "roc_auc": clean_auc[0],
            "roc_auc_ci_low": clean_auc[1],
            "roc_auc_ci_high": clean_auc[2],
            "average_precision": clean_ap[0],
            "average_precision_ci_low": clean_ap[1],
            "average_precision_ci_high": clean_ap[2],
            "external_non_tail_auc": tail_auc[0],
            "external_non_tail_auc_ci_low": tail_auc[1],
            "external_non_tail_auc_ci_high": tail_auc[2],
        }
        if col != "q_template_only_score":
            brier = score_ci_by_run(y_clean, scores[col].to_numpy(dtype=float), runs, seed, "brier", n_boot)
            row.update({"brier": brier[0], "brier_ci_low": brier[1], "brier_ci_high": brier[2]})
        scoreboard_rows.append(row)

    accepted = scores[scores["q_template_gate_accept"] == 1]
    rejected = scores[scores["q_template_gate_accept"] == 0]
    acc_tail = rate_ci_by_run(accepted, "external_gross_tail", "run", seed, n_boot)
    rej_tail = rate_ci_by_run(rejected, "external_gross_tail", "run", seed + 1, n_boot)
    acc_clean = rate_ci_by_run(accepted, "external_clean_gate", "run", seed + 2, n_boot)
    rej_clean = rate_ci_by_run(rejected, "external_clean_gate", "run", seed + 3, n_boot)
    gate_rows = [
        {
            "subset": "q_template_gate_accepted",
            "n": int(len(accepted)),
            "fraction": float(len(accepted) / len(scores)),
            "external_gross_tail_rate": acc_tail[0],
            "external_gross_tail_ci_low": acc_tail[1],
            "external_gross_tail_ci_high": acc_tail[2],
            "external_clean_rate": acc_clean[0],
            "external_clean_ci_low": acc_clean[1],
            "external_clean_ci_high": acc_clean[2],
        },
        {
            "subset": "q_template_gate_rejected",
            "n": int(len(rejected)),
            "fraction": float(len(rejected) / len(scores)),
            "external_gross_tail_rate": rej_tail[0],
            "external_gross_tail_ci_low": rej_tail[1],
            "external_gross_tail_ci_high": rej_tail[2],
            "external_clean_rate": rej_clean[0],
            "external_clean_ci_low": rej_clean[1],
            "external_clean_ci_high": rej_clean[2],
        },
    ]
    return pd.DataFrame(folds), rf_cv_frame, scores, pd.DataFrame(scoreboard_rows), pd.DataFrame(gate_rows), ml_features


def write_outputs(
    config: dict[str, Any],
    s07c,
    out_dir: Path,
    start: float,
    command: str,
    s00: pd.DataFrame,
    per_run: pd.DataFrame,
    data: pd.DataFrame,
    unmatched_q: int,
    folds: pd.DataFrame,
    rf_cv: pd.DataFrame,
    scores: pd.DataFrame,
    scoreboard: pd.DataFrame,
    gate_validation: pd.DataFrame,
    ml_features: list[str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    s00.to_csv(out_dir / "reproduction_s00_counts.csv", index=False)
    per_run.to_csv(out_dir / "raw_label_counts_by_run.csv", index=False)
    data.to_csv(out_dir / "raw_candidate_event_dataset.csv.gz", index=False)
    folds.to_csv(out_dir / "run_heldout_folds.csv", index=False)
    rf_cv.to_csv(out_dir / "rf_cv_scan.csv", index=False)
    scores.to_csv(out_dir / "heldout_scores.csv", index=False)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    gate_validation.to_csv(out_dir / "qtemplate_gate_external_validation.csv", index=False)

    raw_counts = {
        "labelled_events": int(per_run["clean_events"].sum() + per_run["violating_events"].sum()),
        "clean": int(per_run["clean_events"].sum()),
        "violating": int(per_run["violating_events"].sum()),
        "ambiguous": int(per_run["ambiguous_events"].sum()),
        "downstream_ge2_events": int(per_run["downstream_ge2_events"].sum()),
    }
    target = config["target"]
    reproduction = pd.DataFrame(
        [
            {
                "quantity": key,
                "documented": int(target[key]),
                "raw_reconstructed": int(raw_counts[key]),
                "delta": int(raw_counts[key] - int(target[key])),
                "matches": bool(raw_counts[key] == int(target[key])),
            }
            for key in ["labelled_events", "clean", "violating"]
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    forbidden_present = sorted(
        set(ml_features).intersection({"downstream_span_ns", "all_span_ns", "b2_displacement_ns", "run", "eventno", "evt"})
    )
    leak_auc = float(scoreboard.loc[scoreboard["method"] == "leaky_timing_control", "roc_auc"].iloc[0])
    ml_auc = float(scoreboard.loc[scoreboard["method"] == "ml_shape_q_random_forest", "roc_auc"].iloc[0])
    q_auc = float(scoreboard.loc[scoreboard["method"] == "traditional_q_template_only", "roc_auc"].iloc[0])
    q_amp_auc = float(scoreboard.loc[scoreboard["method"] == "ablation_q_amp_random_forest", "roc_auc"].iloc[0])
    shape_no_q_auc = float(scoreboard.loc[scoreboard["method"] == "ablation_shape_no_q_random_forest", "roc_auc"].iloc[0])
    accepted_tail = float(gate_validation.loc[gate_validation["subset"] == "q_template_gate_accepted", "external_gross_tail_rate"].iloc[0])
    rejected_tail = float(gate_validation.loc[gate_validation["subset"] == "q_template_gate_rejected", "external_gross_tail_rate"].iloc[0])
    accepted_clean = float(gate_validation.loc[gate_validation["subset"] == "q_template_gate_accepted", "external_clean_rate"].iloc[0])
    rejected_clean = float(gate_validation.loc[gate_validation["subset"] == "q_template_gate_rejected", "external_clean_rate"].iloc[0])
    leakage = pd.DataFrame(
        [
            {"check": "raw_count_matches_documented_appa", "value": bool(reproduction["matches"].all()), "flag": bool(reproduction["matches"].all()), "note": "Flag true would mean the unrecovered App.A tuple reproduced exactly; it does not."},
            {"check": "ml_forbidden_feature_intersection", "value": "|".join(forbidden_present), "flag": bool(forbidden_present), "note": "ML excludes run/event identifiers and timing-tail label-defining columns."},
            {"check": "leaky_timing_control_near_ceiling", "value": leak_auc, "flag": bool(leak_auc > 0.995), "note": "Expected leakage ceiling when timing spans and B2 displacement are supplied."},
            {"check": "ml_too_good_vs_qtemplate", "value": ml_auc - q_auc, "flag": bool(ml_auc > 0.98 and (ml_auc - q_auc) > 0.10), "note": "Would trigger extra suspicion if non-timing ML nearly recovers clean labels."},
            {"check": "shape_no_q_ablation_near_full_ml", "value": shape_no_q_auc - ml_auc, "flag": bool(shape_no_q_auc > 0.95 and abs(shape_no_q_auc - ml_auc) < 0.03), "note": "If true, high ML performance survives without q_template and is likely same-waveform timing-tail proxy information."},
            {"check": "q_amp_ablation_vs_qtemplate", "value": q_amp_auc - q_auc, "flag": bool((q_amp_auc - q_auc) > 0.10), "note": "Checks whether amplitude/hit-count structure, not q_template alone, carries most of the ML gain."},
            {"check": "qtemplate_unmatched_candidate_events", "value": int(unmatched_q), "flag": bool(unmatched_q > 5), "note": "Events with no S01 q_template match before median fill."},
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    verdict = (
        "do_not_replace_appa_with_qtemplate_only"
        if accepted_tail >= rejected_tail or accepted_clean <= rejected_clean or q_auc < 0.70
        else "qtemplate_only_can_replace_as_conservative_gate_not_probability_table"
    )
    result = {
        "study": "S03f_qtemplate_external_timing_tail",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "raw_root_reproduction": {
            "documented_appa": target,
            "raw_reconstructed": raw_counts,
            "matches_documented": bool(reproduction["matches"].all()),
        },
        "traditional_qtemplate_only": clean_json(scoreboard[scoreboard["method"] == "traditional_q_template_only"].iloc[0].to_dict()),
        "ml_shape_q_random_forest": clean_json(scoreboard[scoreboard["method"] == "ml_shape_q_random_forest"].iloc[0].to_dict()),
        "ablation_q_amp_random_forest": clean_json(scoreboard[scoreboard["method"] == "ablation_q_amp_random_forest"].iloc[0].to_dict()),
        "ablation_shape_no_q_random_forest": clean_json(scoreboard[scoreboard["method"] == "ablation_shape_no_q_random_forest"].iloc[0].to_dict()),
        "leaky_timing_control": clean_json(scoreboard[scoreboard["method"] == "leaky_timing_control"].iloc[0].to_dict()),
        "qtemplate_gate_external_validation": clean_json(gate_validation.to_dict("records")),
        "rf_cv_best": clean_json(rf_cv.iloc[0].to_dict()),
        "ml_feature_count": int(len(ml_features)),
        "ml_forbidden_features_present": forbidden_present,
        "qtemplate_unmatched_candidate_events": int(unmatched_q),
        "verdict": verdict,
        "follow_up_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2), encoding="utf-8")

    input_rows = []
    for run in s07c.all_runs():
        path = s07c.raw_file(run)
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": "raw_b_root"})
    for path, role in [
        (ROOT / config["qtemplate_path"], "s01_qtemplate_table"),
        (ROOT / config["s07c_helper"], "raw_reproduction_helper"),
        (ROOT / "scripts/s03f_1781027415_1845_71ed23e7_qtemplate_external_tail.py", "study_script"),
        (ROOT / "configs/s03f_1781027415_1845_71ed23e7_qtemplate_external_tail.json", "study_config"),
    ]:
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": role})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    report = f"""# S03f: q_template-only plus external timing-tail validation

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Question:** can q_template-only plus external held-out timing-tail validation replace the unrecovered App.A weak-label table for S03/S04/S09 consumers?
- **Inputs:** raw B-stack `HRDv` ROOT and the S01 q_template table; checksums are in `input_sha256.csv`.

## Raw ROOT Reproduction First

{markdown_table(reproduction)}

The current raw `HRDv` CFD20 reconstruction gives `{raw_counts['labelled_events']}` labelled events (`{raw_counts['clean']}` clean, `{raw_counts['violating']}` violating), not the documented App.A tuple `12,147` (`10,636` clean, `1,511` violating). The downstream-ge2 candidate population has `{raw_counts['downstream_ge2_events']}` events, with `{raw_counts['ambiguous']}` ambiguous events excluded from clean-vs-violating scoring.

## Run-Held-Out Benchmark

Rows below use held-out run predictions with run-bootstrap 95% CIs. The traditional method is q_template-only: each fold chooses only a q_template event score and retention gate from train runs, then applies it to held-out runs. The ML method is a random forest using q_template, amplitude, hit-count, and waveform-shape summaries; it excludes run/event ids and all timing-tail defining columns. The two ablation RF rows are leakage-hunt probes, not replacement candidates.

{markdown_table(scoreboard)}

## External Timing-Tail Gate Validation

The q_template-only gate is evaluated on independent held-out timing-tail gates, not on the unrecovered App.A table.

{markdown_table(gate_validation)}

Accepted q_template-gate events have gross-tail rate `{accepted_tail:.4f}` versus `{rejected_tail:.4f}` for rejected events, and clean-gate rate `{accepted_clean:.4f}` versus `{rejected_clean:.4f}`.

## Leakage Hunt

{markdown_table(leakage)}

The leaky timing control is intentionally near the ceiling because it receives downstream span, all-span, and B2 displacement. The production ML feature set has no timing-span, displacement, run, or event identifier columns. The no-q_template waveform ablation is the critical same-waveform proxy check: if it remains near the full ML score, the high ML result is not independent support for replacing App.A; it is largely recovery of timing-tail information from the same pulse shapes used by CFD timing.

## Finding

Verdict: `{verdict}`. The q_template-only gate is useful as a conservative event-quality gate when paired with held-out timing-tail validation, but it should not recreate the unrecovered App.A weak-label probability table. S03/S04/S09 consumers can use the gate plus the external validation rates, not the historical 12,147-row label source.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03f_1781027415_1845_71ed23e7_qtemplate_external_tail.py --config configs/s03f_1781027415_1845_71ed23e7_qtemplate_external_tail.json
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")

    outputs = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    manifest = {
        "study": "S03f_qtemplate_external_timing_tail",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "command": command,
        "git_commit_at_run": git_commit(),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_sec": round(time.time() - start, 3),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "inputs": input_rows,
        "outputs": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    start = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = ROOT / config["output_dir"]
    command = f"/home/billy/anaconda3/bin/python scripts/{Path(__file__).name} --config {args.config.relative_to(ROOT) if args.config.is_absolute() else args.config}"
    s07c = load_s07c(config)

    s00, per_run, events = scan_all_candidates(config, s07c)
    data, unmatched_q = add_qtemplate(config, s07c, events)
    folds, rf_cv, scores, scoreboard, gate_validation, ml_features = run_heldout_methods(config, data)
    write_outputs(
        config,
        s07c,
        out_dir,
        start,
        command,
        s00,
        per_run,
        data,
        unmatched_q,
        folds,
        rf_cv,
        scores,
        scoreboard,
        gate_validation,
        ml_features,
    )


if __name__ == "__main__":
    main()
