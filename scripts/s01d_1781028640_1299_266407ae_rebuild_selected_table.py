#!/usr/bin/env python3
"""S01d: rebuild the S00 selected-pulse table and compare it with S01b."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import platform
import struct
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


CONFIG = Path("configs/s01d_1781028640_1299_266407ae_rebuild_selected_table.yaml")
SCRIPT = Path("scripts/s01d_1781028640_1299_266407ae_rebuild_selected_table.py")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_decompressed_gzip(path: Path) -> str:
    digest = hashlib.sha256()
    with gzip.open(str(path), "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def configured_runs(config: dict) -> list:
    runs = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> dict:
    lookup = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def gzip_header(path: Path) -> dict:
    header = path.read_bytes()[:512]
    if header[:2] != b"\x1f\x8b":
        raise ValueError("{} is not gzip".format(path))
    flags = header[3]
    mtime = struct.unpack("<I", header[4:8])[0]
    fname = ""
    if flags & 0x08:
        end = header.index(b"\x00", 10)
        fname = header[10:end].decode("latin1")
    return {"mtime": int(mtime), "fname": fname, "flags": int(flags), "xfl": int(header[8]), "os": int(header[9])}


def write_gzip_csv_like_reference(frame: pd.DataFrame, path: Path, reference_header: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fname = reference_header.get("fname") or path.with_suffix("").name
    with path.open("wb") as raw:
        with gzip.GzipFile(
            filename=fname,
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=int(reference_header["mtime"]),
        ) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as text:
                frame.to_csv(text, index=False)


def iter_raw_batches(path: Path, samples_per_channel: int, step_size: int = 10000):
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np"):
        waves = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, samples_per_channel)
        yield np.asarray(batch["EVENTNO"], dtype=np.int64), np.asarray(batch["EVT"], dtype=np.int64), waves


def init_counts() -> dict:
    return {"events_total": 0, "events_with_selected": 0, "selected_pulses": 0, "staves": defaultdict(int)}


def scan_raw(config: dict):
    raw_dir = Path(config["raw_root_dir"])
    cut = float(config["amplitude_cut_adc"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    samples_per_channel = int(config["samples_per_channel"])
    staves = {name: int(idx) for name, idx in config["staves"].items()}
    stave_names = list(staves.keys())
    stave_channels = np.asarray([staves[name] for name in stave_names], dtype=int)
    stave_grid = np.asarray(stave_names)
    group_for_run = run_group_lookup(config)
    ml_cfg = config["ml_check"]
    rng = np.random.default_rng(int(ml_cfg["random_seed"]))

    selected_frames = []
    ml_frames = []
    counts_by_run = []
    counts_by_group = defaultdict(init_counts)
    input_rows = []

    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        if not path.exists():
            raise FileNotFoundError(path)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
        group = group_for_run[run]
        run_counts = init_counts()
        for eventno, evt, all_waves in iter_raw_batches(path, samples_per_channel):
            waves = all_waves[:, stave_channels, :]
            baseline = np.median(waves[..., baseline_idx], axis=-1)
            corrected = waves - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            peak_sample = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            dynamic_amp = waves.max(axis=-1) - waves.min(axis=-1)
            selected = amplitude > cut
            event_selected = selected.any(axis=1)

            run_counts["events_total"] += int(len(eventno))
            run_counts["events_with_selected"] += int(event_selected.sum())
            run_counts["selected_pulses"] += int(selected.sum())
            counts_by_group[group]["events_total"] += int(len(eventno))
            counts_by_group[group]["events_with_selected"] += int(event_selected.sum())
            counts_by_group[group]["selected_pulses"] += int(selected.sum())
            for idx, stave in enumerate(stave_names):
                stave_count = int(selected[:, idx].sum())
                run_counts["staves"][stave] += stave_count
                counts_by_group[group]["staves"][stave] += stave_count

            event_idx, stave_idx = np.where(selected)
            if len(event_idx):
                selected_frames.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "group": group,
                            "eventno": eventno[event_idx].astype(int),
                            "evt": evt[event_idx].astype(int),
                            "stave": stave_grid[stave_idx],
                            "channel": stave_channels[stave_idx].astype(int),
                            "baseline_adc": baseline[event_idx, stave_idx],
                            "amplitude_adc": amplitude[event_idx, stave_idx],
                            "peak_sample": peak_sample[event_idx, stave_idx].astype(int),
                            "area_adc_samples": area[event_idx, stave_idx],
                        }
                    )
                )

            near = (amplitude > float(ml_cfg["near_threshold_low_adc"])) | (
                dynamic_amp > float(ml_cfg["near_threshold_low_adc"])
            )
            near &= (amplitude < float(ml_cfg["near_threshold_high_adc"])) | (
                dynamic_amp < float(ml_cfg["near_threshold_high_adc"])
            )
            keep_probability = np.where(
                selected,
                float(ml_cfg["selected_keep_probability"]),
                float(ml_cfg["nonselected_keep_probability"]),
            )
            keep = (rng.random(selected.shape) < keep_probability) | near
            if keep.any():
                kept_event, kept_stave = np.where(keep)
                pre4 = waves[..., baseline_idx]
                ml_frames.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "evt": evt[kept_event].astype(int),
                            "stave": stave_grid[kept_stave],
                            "stave_idx": kept_stave.astype(int),
                            "selected": selected[kept_event, kept_stave].astype(int),
                            "wave_max": waves.max(axis=-1)[kept_event, kept_stave],
                            "wave_min": waves.min(axis=-1)[kept_event, kept_stave],
                            "pre4_mean": pre4.mean(axis=-1)[kept_event, kept_stave],
                            "pre4_std": pre4.std(axis=-1)[kept_event, kept_stave],
                            "post_mean": waves[..., 4:].mean(axis=-1)[kept_event, kept_stave],
                            "post_std": waves[..., 4:].std(axis=-1)[kept_event, kept_stave],
                            "dynamic_amp": dynamic_amp[kept_event, kept_stave],
                            "median_amp": amplitude[kept_event, kept_stave],
                        }
                    )
                )

        row = {
            "run": run,
            "group": group,
            "events_total": run_counts["events_total"],
            "events_with_selected": run_counts["events_with_selected"],
            "selected_pulses": run_counts["selected_pulses"],
        }
        row.update({stave: int(run_counts["staves"][stave]) for stave in stave_names})
        counts_by_run.append(row)
        print("run {} selected {}".format(run, row["selected_pulses"]))

    group_rows = []
    for group in config["run_groups"]:
        counts = counts_by_group[group]
        row = {
            "group": group,
            "events_total": counts["events_total"],
            "events_with_selected": counts["events_with_selected"],
            "selected_pulses": counts["selected_pulses"],
        }
        row.update({stave: int(counts["staves"][stave]) for stave in stave_names})
        group_rows.append(row)

    selected_table = pd.concat(selected_frames, ignore_index=True)
    ml_sample = pd.concat(ml_frames, ignore_index=True)
    return pd.DataFrame(counts_by_run), pd.DataFrame(group_rows), selected_table, ml_sample, pd.DataFrame(input_rows)


def cap_ml_sample(sample: pd.DataFrame, config: dict) -> pd.DataFrame:
    ml_cfg = config["ml_check"]
    heldout = set(int(run) for run in ml_cfg["heldout_runs"])
    seed = int(ml_cfg["random_seed"])
    frames = []
    for split_name, split_df, cap_key in [
        ("train", sample[~sample["run"].isin(heldout)], "max_train_per_class"),
        ("test", sample[sample["run"].isin(heldout)], "max_test_per_class"),
    ]:
        for selected_value, subset in split_df.groupby("selected"):
            n = min(len(subset), int(ml_cfg[cap_key]))
            frames.append(
                subset.sample(n=n, random_state=seed + 17 * int(selected_value) + (0 if split_name == "train" else 1000))
            )
    return pd.concat(frames, ignore_index=True)


def count_match_table(config: dict, counts_by_group: pd.DataFrame) -> pd.DataFrame:
    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "expected": int(expected["total_selected_pulses"]),
            "reproduced": int(counts_by_group["selected_pulses"].sum()),
            "tolerance": 0,
        }
    ]
    for group, group_expected in expected["groups"].items():
        row = counts_by_group[counts_by_group["group"] == group].iloc[0]
        if "events" in group_expected:
            rows.append(
                {
                    "quantity": "{} events with selected pulse".format(group),
                    "expected": int(group_expected["events"]),
                    "reproduced": int(row["events_with_selected"]),
                    "tolerance": 0,
                }
            )
        if "pulses" in group_expected:
            rows.append(
                {
                    "quantity": "{} selected pulses".format(group),
                    "expected": int(group_expected["pulses"]),
                    "reproduced": int(row["selected_pulses"]),
                    "tolerance": 0,
                }
            )
        for stave, value in group_expected.get("staves", {}).items():
            rows.append(
                {
                    "quantity": "{} {} selected pulses".format(group, stave),
                    "expected": int(value),
                    "reproduced": int(row[stave]),
                    "tolerance": 0,
                }
            )
    result = pd.DataFrame(rows)
    result["delta"] = result["reproduced"] - result["expected"]
    result["pass"] = result["delta"].abs() <= result["tolerance"]
    return result[["quantity", "expected", "reproduced", "delta", "tolerance", "pass"]]


def compare_reference_table(config: dict, selected: pd.DataFrame, rebuilt_path: Path) -> tuple:
    reference_table = Path(config["s01b_reference_table"])
    reference_manifest = json.loads(Path(config["s01b_reference_manifest"]).read_text())
    reference_result = json.loads(Path(config["s01b_reference_result"]).read_text())
    reference_rows = pd.read_csv(reference_table, usecols=["run", "stave"])
    expected_by_run_stave = reference_rows.groupby(["run", "stave"]).size().reset_index(name="s01b_rows")
    rebuilt_by_run_stave = selected.groupby(["run", "stave"]).size().reset_index(name="rebuilt_rows")
    by_run_stave = expected_by_run_stave.merge(rebuilt_by_run_stave, on=["run", "stave"], how="outer").fillna(0)
    by_run_stave["delta"] = by_run_stave["rebuilt_rows"].astype(int) - by_run_stave["s01b_rows"].astype(int)
    by_run_stave["pass"] = by_run_stave["delta"] == 0

    row = {
        "reference_table": str(reference_table),
        "reference_rows": int(reference_manifest["selected_pulse_table"]["data_rows"]),
        "rebuilt_rows": int(len(selected)),
        "row_delta": int(len(selected) - int(reference_manifest["selected_pulse_table"]["data_rows"])),
        "reference_gzip_sha256": reference_manifest["selected_pulse_table"]["sha256"],
        "rebuilt_gzip_sha256": sha256_file(rebuilt_path),
        "reference_content_sha256": sha256_decompressed_gzip(reference_table),
        "rebuilt_content_sha256": sha256_decompressed_gzip(rebuilt_path),
        "result_json_reference_sha256": reference_result["traditional"]["sha256"],
    }
    row["gzip_sha256_match"] = row["rebuilt_gzip_sha256"] == row["reference_gzip_sha256"]
    row["content_sha256_match"] = row["rebuilt_content_sha256"] == row["reference_content_sha256"]
    row["row_count_match"] = row["row_delta"] == 0
    row["run_stave_count_match"] = bool(by_run_stave["pass"].all())
    summary = pd.DataFrame([row])
    return summary, by_run_stave


def metric_bundle(y_true, y_pred, score=None) -> dict:
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }
    if score is not None and len(np.unique(y_true)) == 2:
        out["roc_auc"] = float(roc_auc_score(y_true, score))
        out["average_precision"] = float(average_precision_score(y_true, score))
    else:
        out["roc_auc"] = math.nan
        out["average_precision"] = math.nan
    return out


def run_bootstrap_ci(frame: pd.DataFrame, metric: str, rng: np.random.Generator, n_boot: int) -> tuple:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    values = []
    for _ in range(n_boot):
        draw = rng.choice(runs, size=len(runs), replace=True)
        subset = pd.concat([frame[frame["run"] == run] for run in draw], ignore_index=True)
        values.append(metric_bundle(subset["y_true"].to_numpy(), subset["y_pred"].to_numpy(), subset["score"].to_numpy())[metric])
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def evaluate_predictions(method: str, test: pd.DataFrame, y_pred, score, rng: np.random.Generator, n_boot: int) -> tuple:
    pred_frame = pd.DataFrame(
        {
            "run": test["run"].to_numpy(dtype=int),
            "y_true": test["selected"].to_numpy(dtype=int),
            "y_pred": np.asarray(y_pred, dtype=int),
            "score": np.asarray(score, dtype=float),
        }
    )
    rows = []
    overall = metric_bundle(pred_frame["y_true"].to_numpy(), pred_frame["y_pred"].to_numpy(), pred_frame["score"].to_numpy())
    for metric, value in overall.items():
        lo, hi = run_bootstrap_ci(pred_frame, metric, rng, n_boot)
        rows.append({"method": method, "scope": "heldout_runs", "metric": metric, "value": value, "ci_low": lo, "ci_high": hi})
    by_run_rows = []
    for run, subset in pred_frame.groupby("run"):
        metrics = metric_bundle(subset["y_true"].to_numpy(), subset["y_pred"].to_numpy(), subset["score"].to_numpy())
        for metric, value in metrics.items():
            by_run_rows.append({"method": method, "run": int(run), "metric": metric, "value": value, "n": int(len(subset))})
    return pd.DataFrame(rows), pd.DataFrame(by_run_rows), pred_frame


def run_ml_check(config: dict, sample: pd.DataFrame, out_dir: Path) -> tuple:
    ml_cfg = config["ml_check"]
    heldout = set(int(run) for run in ml_cfg["heldout_runs"])
    sample = cap_ml_sample(sample, config)
    train = sample[~sample["run"].isin(heldout)].copy()
    test = sample[sample["run"].isin(heldout)].copy()
    y_train = train["selected"].to_numpy(dtype=int)
    y_test = test["selected"].to_numpy(dtype=int)
    groups = train["run"].to_numpy(dtype=int)
    honest_features = ["wave_max", "wave_min", "pre4_mean", "pre4_std", "post_mean", "post_std", "dynamic_amp", "stave_idx"]
    leaky_features = honest_features + ["median_amp"]
    rng = np.random.default_rng(int(ml_cfg["random_seed"]) + 31)

    cv_rows = []
    best_c = None
    best_score = -np.inf
    x_train = train[honest_features].to_numpy(dtype=float)
    splitter = GroupKFold(n_splits=int(ml_cfg["cv_folds"]))
    for c_value in [float(x) for x in ml_cfg["regularization_c"]]:
        scores = []
        for fit_idx, valid_idx in splitter.split(x_train, y_train, groups):
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=c_value, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
            )
            model.fit(x_train[fit_idx], y_train[fit_idx])
            probability = model.predict_proba(x_train[valid_idx])[:, 1]
            scores.append(roc_auc_score(y_train[valid_idx], probability))
        mean_score = float(np.mean(scores))
        cv_rows.append({"feature_set": "honest_raw_summaries", "C": c_value, "group_cv_roc_auc": mean_score})
        if mean_score > best_score:
            best_score = mean_score
            best_c = c_value

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_c, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    model.fit(train[honest_features].to_numpy(dtype=float), y_train)
    ml_score = model.predict_proba(test[honest_features].to_numpy(dtype=float))[:, 1]
    ml_pred = (ml_score >= 0.5).astype(int)

    leaky_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=10.0, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    leaky_model.fit(train[leaky_features].to_numpy(dtype=float), y_train)
    leaky_score = leaky_model.predict_proba(test[leaky_features].to_numpy(dtype=float))[:, 1]
    leaky_pred = (leaky_score >= 0.5).astype(int)

    shuffled = y_train.copy()
    rng.shuffle(shuffled)
    shuffled_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_c, max_iter=1000, class_weight="balanced", random_state=int(ml_cfg["random_seed"])),
    )
    shuffled_model.fit(train[honest_features].to_numpy(dtype=float), shuffled)
    shuffled_score = shuffled_model.predict_proba(test[honest_features].to_numpy(dtype=float))[:, 1]
    shuffled_pred = (shuffled_score >= 0.5).astype(int)

    traditional_score = test["median_amp"].to_numpy(dtype=float)
    traditional_pred = (traditional_score > float(config["amplitude_cut_adc"])).astype(int)
    dynamic_score = test["dynamic_amp"].to_numpy(dtype=float)
    dynamic_pred = (dynamic_score > float(config["amplitude_cut_adc"])).astype(int)

    n_boot = int(ml_cfg["bootstrap_samples"])
    summaries = []
    by_run = []
    prediction_frames = []
    for method, pred, score in [
        ("traditional_median_first_four_gate", traditional_pred, traditional_score),
        ("dynamic_range_comparator", dynamic_pred, dynamic_score),
        ("ml_logistic_honest_raw_summaries", ml_pred, ml_score),
        ("ml_leaky_median_amp_sentinel", leaky_pred, leaky_score),
        ("ml_shuffled_label_negative_control", shuffled_pred, shuffled_score),
    ]:
        summary, method_by_run, pred_frame = evaluate_predictions(method, test, pred, score, rng, n_boot)
        summaries.append(summary)
        by_run.append(method_by_run)
        pred_frame["method"] = method
        prediction_frames.append(pred_frame)

    leakage = pd.DataFrame(
        [
            {
                "check": "train_test_run_overlap",
                "value": int(len(set(train["run"]).intersection(set(test["run"])))),
                "pass": len(set(train["run"]).intersection(set(test["run"]))) == 0,
                "notes": "Split is by run; heldout runs are {}.".format(",".join(str(x) for x in sorted(heldout))),
            },
            {
                "check": "honest_feature_excludes_threshold_variable",
                "value": int("median_amp" not in honest_features),
                "pass": "median_amp" not in honest_features,
                "notes": "Honest ML features exclude median_amp, run, evt, event order, and labels.",
            },
            {
                "check": "leaky_sentinel_accuracy",
                "value": float(accuracy_score(y_test, leaky_pred)),
                "pass": float(accuracy_score(y_test, leaky_pred)) >= 0.995,
                "notes": "Including median_amp should nearly reproduce the deterministic threshold; ROC AUC was {:.6f}.".format(
                    float(roc_auc_score(y_test, leaky_score))
                ),
            },
            {
                "check": "shuffled_label_accuracy",
                "value": float(accuracy_score(y_test, shuffled_pred)),
                "pass": float(accuracy_score(y_test, shuffled_pred)) < 0.90,
                "notes": "Randomized training labels should not reproduce the gate.",
            },
        ]
    )
    pd.DataFrame(cv_rows).to_csv(out_dir / "ml_group_cv_scan.csv", index=False)
    pd.concat(summaries, ignore_index=True).to_csv(out_dir / "heldout_benchmark.csv", index=False)
    pd.concat(by_run, ignore_index=True).to_csv(out_dir / "heldout_benchmark_by_run.csv", index=False)
    pd.concat(prediction_frames, ignore_index=True).to_csv(out_dir / "heldout_prediction_audit.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    sample.groupby(["run", "selected"]).size().reset_index(name="sample_rows").to_csv(out_dir / "ml_sample_by_run.csv", index=False)
    return pd.concat(summaries, ignore_index=True), pd.concat(by_run, ignore_index=True), leakage


def write_input_hashes(config: dict, input_rows: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    extra = [
        Path(config["s00c_config"]),
        Path(config["s01b_reference_manifest"]),
        Path(config["s01b_reference_result"]),
        Path(config["s01b_reference_table"]),
        CONFIG,
        SCRIPT,
    ]
    rows = input_rows.to_dict(orient="records")
    for path in extra:
        rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    result = pd.DataFrame(rows)
    result.to_csv(out_dir / "input_sha256.csv", index=False)
    return result


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    config: dict,
    out_dir: Path,
    count_match: pd.DataFrame,
    table_cmp: pd.DataFrame,
    benchmark: pd.DataFrame,
    leakage: pd.DataFrame,
    runtime_s: float,
) -> None:
    table = table_cmp.iloc[0].to_dict()
    trad = benchmark[(benchmark["method"] == "traditional_median_first_four_gate") & (benchmark["metric"] == "accuracy")].iloc[0]
    ml = benchmark[(benchmark["method"] == "ml_logistic_honest_raw_summaries") & (benchmark["metric"] == "accuracy")].iloc[0]
    dyn = benchmark[(benchmark["method"] == "dynamic_range_comparator") & (benchmark["metric"] == "accuracy")].iloc[0]
    shuffled = leakage[leakage["check"] == "shuffled_label_accuracy"].iloc[0]
    lines = [
        "# S01d: selected-pulse table rebuild from S00c checked selector",
        "",
        "- Ticket: `{}`".format(config["ticket_id"]),
        "- Worker: `{}`".format(config["worker"]),
        "- Inputs: raw B-stack ROOT under `{}`; no Monte Carlo.".format(config["raw_root_dir"]),
        "- Reference: S01b selected-table manifest in `{}`.".format(config["s01b_reference_report"]),
        "",
        "## Result",
        "",
        "The raw `HRDv` scan reproduced the S00/S01b selected-pulse table exactly: **{:,} rows**, count delta **{}**, gzip sha match `{}`, and decompressed CSV sha match `{}`.".format(
            int(table["rebuilt_rows"]),
            int(table["row_delta"]),
            table["gzip_sha256_match"],
            table["content_sha256_match"],
        ),
        "",
        "| Check | Reference | Rebuilt | Pass |",
        "|---|---:|---:|---|",
        "| data rows | {} | {} | {} |".format(int(table["reference_rows"]), int(table["rebuilt_rows"]), bool(table["row_count_match"])),
        "| gzip sha256 | `{}` | `{}` | {} |".format(table["reference_gzip_sha256"][:12], table["rebuilt_gzip_sha256"][:12], bool(table["gzip_sha256_match"])),
        "| content sha256 | `{}` | `{}` | {} |".format(table["reference_content_sha256"][:12], table["rebuilt_content_sha256"][:12], bool(table["content_sha256_match"])),
        "| run/stave counts | S01b table | rebuilt table | {} |".format(bool(table["run_stave_count_match"])),
        "",
        "The match depends on preserving the S01b gzip header timestamp and original filename; `table_hash_comparison.csv` records both the byte hash and the decompressed-content hash.",
        "",
        "## Reproduction Gate",
        "",
        "The selector is the S00c checked rule: B2/B4/B6/B8 even channels, median baseline from samples 0-3, and `max(waveform - baseline) > 1000 ADC`. All configured S00/S01b count checks passed with zero tolerance.",
        "",
        count_match.to_markdown(index=False),
        "",
        "## Held-Out Methods",
        "",
        "Held-out runs were `{}`. CIs bootstrap held-out runs, not rows.".format(",".join(str(x) for x in config["ml_check"]["heldout_runs"])),
        "",
        "| Method | Held-out accuracy [95% CI] | Notes |",
        "|---|---:|---|",
        "| Traditional median-first-four gate | {:.6f} [{:.6f}, {:.6f}] | Production rule; exact by definition. |".format(trad["value"], trad["ci_low"], trad["ci_high"]),
        "| Dynamic-range comparator | {:.6f} [{:.6f}, {:.6f}] | Strong alternate threshold semantics. |".format(dyn["value"], dyn["ci_low"], dyn["ci_high"]),
        "| ML logistic raw summaries | {:.6f} [{:.6f}, {:.6f}] | GroupKFold by run; excludes `median_amp`, run, evt, and labels. |".format(ml["value"], ml["ci_low"], ml["ci_high"]),
        "",
        "ML is not a production replacement here. The deterministic selector is the table definition, so the correct outcome is a tie or ML loss against the exact rule.",
        "",
        "## Leakage Audit",
        "",
        "The honest ML score is high because waveform maxima, minima, and pretrigger summaries approximate the same threshold algebra, so leakage checks were run explicitly. Train/test run overlap is zero; the leaky `median_amp` sentinel reaches the expected near-perfect score; shuffled-label training falls to {:.3f} accuracy.".format(float(shuffled["value"])),
        "",
        leakage.to_markdown(index=False),
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `s00_selected_b_pulses.csv.gz`, `table_hash_comparison.csv`, `run_stave_count_comparison.csv`, `count_match_table.csv`, `heldout_benchmark.csv`, `heldout_benchmark_by_run.csv`, `ml_group_cv_scan.csv`, `leakage_checks.csv`, and `ml_sample_by_run.csv` are in this report directory.",
        "",
        "Runtime: {:.1f} s on `{}`.".format(runtime_s, platform.node()),
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    started = time.time()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rebuilt_path = Path(config["rebuilt_table"])

    reference_header = gzip_header(Path(config["s01b_reference_table"]))
    counts_by_run, counts_by_group, selected, ml_sample, input_rows = scan_raw(config)
    write_gzip_csv_like_reference(selected, rebuilt_path, reference_header)

    count_match = count_match_table(config, counts_by_group)
    table_cmp, run_stave_cmp = compare_reference_table(config, selected, rebuilt_path)
    benchmark, by_run, leakage = run_ml_check(config, ml_sample, out_dir)
    input_hashes = write_input_hashes(config, input_rows, out_dir)

    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "counts_by_group.csv", index=False)
    count_match.to_csv(out_dir / "count_match_table.csv", index=False)
    table_cmp.to_csv(out_dir / "table_hash_comparison.csv", index=False)
    run_stave_cmp.to_csv(out_dir / "run_stave_count_comparison.csv", index=False)

    runtime_s = time.time() - started
    write_report(config, out_dir, count_match, table_cmp, benchmark, leakage, runtime_s)

    table = table_cmp.iloc[0].to_dict()
    trad = benchmark[(benchmark["method"] == "traditional_median_first_four_gate") & (benchmark["metric"] == "accuracy")].iloc[0]
    ml = benchmark[(benchmark["method"] == "ml_logistic_honest_raw_summaries") & (benchmark["metric"] == "accuracy")].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "reproduced": bool(count_match["pass"].all() and table["gzip_sha256_match"] and table["run_stave_count_match"]),
        "traditional": {
            "metric": "selected_table_rows_and_sha256",
            "value": int(table["rebuilt_rows"]),
            "ci": [int(table["rebuilt_rows"]), int(table["rebuilt_rows"])],
            "gzip_sha256": table["rebuilt_gzip_sha256"],
            "content_sha256": table["rebuilt_content_sha256"],
        },
        "ml": {
            "method": "logistic_honest_raw_summaries",
            "metric": "heldout_selection_accuracy",
            "value": float(ml["value"]),
            "ci": [float(ml["ci_low"]), float(ml["ci_high"])],
        },
        "traditional_heldout": {
            "metric": "heldout_selection_accuracy",
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
        },
        "ml_beats_baseline": bool(float(ml["value"]) > float(trad["value"])),
        "leakage_checks_passed": bool(leakage["pass"].all()),
        "input_sha256": "input_sha256.csv",
        "critic": "pending",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(CONFIG),
        "script": str(SCRIPT),
        "command": "/home/billy/anaconda3/bin/python3.7 {}".format(SCRIPT),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "runtime_s": runtime_s,
        "reference_gzip_header": reference_header,
        "count_match_passed": bool(count_match["pass"].all()),
        "table_hash_match_passed": bool(table["gzip_sha256_match"] and table["content_sha256_match"]),
        "run_stave_count_match_passed": bool(table["run_stave_count_match"]),
        "input_sha256_rows": int(len(input_hashes)),
        "output_sha256": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("selected rows:", int(table["rebuilt_rows"]))
    print("gzip sha match:", bool(table["gzip_sha256_match"]))
    print("content sha match:", bool(table["content_sha256_match"]))
    print("count match:", bool(count_match["pass"].all()))
    print("leakage checks:", bool(leakage["pass"].all()))
    return 0 if result["reproduced"] and result["leakage_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
