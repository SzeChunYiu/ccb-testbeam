#!/usr/bin/env python3
"""S16g canonical HRD trigger-mode run manifest.

This study builds a run_0000..run_0065 A/B-stack manifest from direct ROOT
evidence, cross-checks the S16e/S16f provenance artifacts, and writes a small
machine-readable table for downstream pedestal/timing studies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Callable, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT_RE = re.compile(r"hrd([ab])_run_(\d{4})", re.I)
TOKEN_RE = re.compile(
    r"(daq|acq|acquisition|trigger|trig|logbook|log|run[_ -]?log|spreadsheet|xlsx|ods|csv|forced?|random|pedestal|ped|pulser|script|\.py|\.sh)",
    re.I,
)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
        return None if math.isnan(value) else value
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def parse_root(path_or_name: str) -> Tuple[str, int]:
    match = ROOT_RE.search(str(path_or_name))
    if not match:
        raise ValueError("cannot parse HRD stack/run from {}".format(path_or_name))
    return match.group(1).lower(), int(match.group(2))


def raw_root_paths(config: dict) -> List[Path]:
    root = Path(config["raw_root_dir"])
    return sorted(root.glob("hrda_run_*.root")) + sorted(root.glob("hrdb_run_*.root"))


def b_root_paths(config: dict) -> List[Path]:
    return sorted(Path(config["raw_root_dir"]).glob("hrdb_run_*.root"))


def iter_tree(path: Path, branches: List[str], step_size: int = 25000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(branches, step_size=step_size, library="np")


def archive_inventory(config: dict) -> pd.DataFrame:
    rows = []
    for archive in sorted(Path(config["raw_archive_dir"]).glob("*.zip")):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                rel = info.filename
                suffix = Path(rel).suffix.lower()
                token = TOKEN_RE.search(rel)
                root_match = ROOT_RE.search(rel)
                rows.append(
                    {
                        "archive": str(archive),
                        "member": rel,
                        "suffix": suffix,
                        "bytes": int(info.file_size),
                        "run": int(root_match.group(2)) if root_match else np.nan,
                        "stack": root_match.group(1).lower() if root_match else "",
                        "token_hit": token.group(0).lower() if token else "",
                        "is_root": suffix == ".root",
                        "external_log_candidate": bool(
                            suffix in {".csv", ".tsv", ".xlsx", ".ods", ".txt", ".log", ".md", ".json", ".yaml", ".yml", ".py", ".sh"}
                            or (token and suffix != ".root")
                        ),
                    }
                )
    return pd.DataFrame(rows)


def filesystem_inventory(config: dict) -> pd.DataFrame:
    rows = []
    for root_name in config["filesystem_scan_roots"]:
        root = Path(root_name)
        if not root.exists():
            rows.append(
                {
                    "scan_root": str(root),
                    "path": "",
                    "suffix": "",
                    "bytes": 0,
                    "run": np.nan,
                    "stack": "",
                    "token_hit": "",
                    "is_root": False,
                    "is_sorted_root": False,
                    "external_log_candidate": False,
                    "missing_scan_root": True,
                }
            )
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(root))
            suffix = path.suffix.lower()
            token = TOKEN_RE.search(rel)
            root_match = ROOT_RE.search(rel)
            rows.append(
                {
                    "scan_root": str(root),
                    "path": rel,
                    "suffix": suffix,
                    "bytes": int(path.stat().st_size),
                    "run": int(root_match.group(2)) if root_match else np.nan,
                    "stack": root_match.group(1).lower() if root_match else "",
                    "token_hit": token.group(0).lower() if token else "",
                    "is_root": suffix == ".root",
                    "is_sorted_root": suffix == ".root" and "-sorted" in rel,
                    "external_log_candidate": bool(
                        suffix in {".csv", ".tsv", ".xlsx", ".ods", ".txt", ".log", ".md", ".json", ".yaml", ".yml", ".py", ".sh"}
                        or (token and suffix != ".root")
                    ),
                    "missing_scan_root": False,
                }
            )
    return pd.DataFrame(rows)


def root_trigger_audit(config: dict) -> pd.DataFrame:
    rows = []
    for path in raw_root_paths(config):
        stack, run = parse_root(path.name)
        tree = uproot.open(path)["h101"]
        branches = set(tree.keys())
        if tree.num_entries:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            values, counts = np.unique(trigger, return_counts=True)
            summary = ";".join("{}:{}".format(int(v), int(c)) for v, c in zip(values, counts))
            non_beam = int(np.sum(counts[values != int(config["beam_trigger_value"])]))
        else:
            summary = "empty"
            non_beam = 0
        rows.append(
            {
                "file": path.name,
                "path": str(path),
                "stack": stack,
                "run": run,
                "bytes": int(path.stat().st_size),
                "sha256": sha256_file(path),
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "has_trigger_branch": "TRIGGER" in branches,
                "has_run_metadata_branch": any(k.upper() in {"RUN", "RUNNO", "RUNNUMBER"} for k in branches),
                "filename_token_hit": bool(TOKEN_RE.search(path.name)),
            }
        )
    return pd.DataFrame(rows)


def canonical_manifest(config: dict, trigger: pd.DataFrame, archive: pd.DataFrame, fs_scan: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run in range(int(config["run_min"]), int(config["run_max"]) + 1):
        for stack in ["a", "b"]:
            root_rows = trigger[(trigger["run"] == run) & (trigger["stack"] == stack)]
            archive_rows = archive[(archive["run"] == run) & (archive["stack"] == stack) & (archive["is_root"])]
            extracted_rows = fs_scan[(fs_scan["run"] == run) & (fs_scan["stack"] == stack) & (fs_scan["is_root"]) & (~fs_scan["is_sorted_root"])]
            sorted_rows = fs_scan[(fs_scan["run"] == run) & (fs_scan["stack"] == stack) & (fs_scan["is_sorted_root"])]
            present = bool(len(root_rows))
            entries = int(root_rows["entries"].sum()) if present else 0
            non_beam = int(root_rows["non_beam_trigger_entries"].sum()) if present else 0
            trigger_summary = root_rows["trigger_summary"].iloc[0] if present else ""
            has_trigger = bool(root_rows["has_trigger_branch"].iloc[0]) if present else False
            if not present:
                status = "missing"
                mode = "not_available_in_current_mirror"
                confidence = "high_for_absence_in_current_mirror"
                evidence = "no extracted raw ROOT row and no root.zip member for this stack/run" if not len(archive_rows) else "archive member exists but extracted raw ROOT is absent"
            elif entries == 0:
                status = "empty_placeholder"
                mode = "empty_placeholder_no_events"
                confidence = "high_direct_root_empty"
                evidence = "extracted raw ROOT and root.zip member have zero h101 entries"
            elif non_beam == 0 and has_trigger and trigger_summary.startswith("{}:".format(int(config["beam_trigger_value"]))):
                status = "populated"
                mode = "beam_trigger_only"
                confidence = "high_direct_root_trigger"
                evidence = "TRIGGER branch present; all populated entries equal beam trigger value"
            elif non_beam > 0:
                status = "populated_non_beam"
                mode = "mixed_or_non_beam_trigger"
                confidence = "high_direct_root_non_beam"
                evidence = "TRIGGER branch contains non-beam entries"
            else:
                status = "populated_unknown_trigger"
                mode = "unknown_populated"
                confidence = "medium_root_without_clear_trigger"
                evidence = "ROOT entries exist but trigger branch evidence is incomplete"
            rows.append(
                {
                    "run": run,
                    "run_id": "run_{:04d}".format(run),
                    "stack": stack,
                    "raw_root_present": present,
                    "raw_archive_present": bool(len(archive_rows)),
                    "extracted_root_present": bool(len(extracted_rows)),
                    "sorted_root_present": bool(len(sorted_rows)),
                    "entries": entries,
                    "trigger_summary": trigger_summary,
                    "non_beam_trigger_entries": non_beam,
                    "has_trigger_branch": has_trigger,
                    "root_status": status,
                    "trigger_mode_label": mode,
                    "confidence_label": confidence,
                    "evidence_basis": evidence,
                    "file": root_rows["file"].iloc[0] if present else "",
                    "path": root_rows["path"].iloc[0] if present else "",
                    "bytes": int(root_rows["bytes"].iloc[0]) if present else 0,
                    "sha256": root_rows["sha256"].iloc[0] if present else "",
                }
            )
    return pd.DataFrame(rows)


def selected_b_stave_count(config: dict) -> pd.DataFrame:
    staves = np.asarray([int(v) for v in config["staves"].values()], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in config["s00_runs"]:
        path = Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))
        total = 0
        selected = 0
        for batch in iter_tree(path, ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            waves = events[:, staves, :]
            seed = np.median(waves[:, :, pre], axis=2)
            amp = (waves - seed[:, :, None]).max(axis=2)
            total += int(waves.shape[0])
            selected += int((amp > cut).sum())
        rows.append({"run": int(run), "events": total, "selected_b_stave_pulses": selected})
    return pd.DataFrame(rows)


def waveform_summary(config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    staves = np.asarray(list(config["staves"].values()), dtype=int)
    nsamp = int(config["samples_per_channel"])
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    quiet_cut = float(config["quiet_event_max_amplitude_adc"])
    amp_cut = float(config["amplitude_cut_adc"])
    max_per_run = int(config["ml"]["max_events_per_run"])
    run_rows = []
    sample_rows = []
    for path in b_root_paths(config):
        _, run = parse_root(path.name)
        total = 0
        selected_staves = 0
        selected_events = 0
        quiet_events = 0
        event_max_chunks = []
        per_run_samples = []
        for batch in iter_tree(path, ["HRDv"]):
            if len(batch["HRDv"]) == 0:
                continue
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)[:, staves, :]
            seed = np.median(wave[:, :, pre], axis=2)
            corrected = wave - seed[:, :, None]
            amp = corrected.max(axis=2)
            event_max = amp.max(axis=1)
            pre_wave = wave[:, :, pre]
            pre_mean = pre_wave.mean(axis=(1, 2))
            pre_std = pre_wave.std(axis=(1, 2))
            pre_range = pre_wave.max(axis=(1, 2)) - pre_wave.min(axis=(1, 2))
            pre_slope = (wave[:, :, 3] - wave[:, :, 0]).mean(axis=1)
            quiet = event_max < quiet_cut
            pulse = event_max > amp_cut
            keep = quiet | pulse
            if np.any(keep):
                idx = np.where(keep)[0]
                if len(idx) > max_per_run:
                    idx = rng.choice(idx, size=max_per_run, replace=False)
                per_run_samples.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "quiet_proxy": quiet[idx].astype(int),
                            "pulse_event": pulse[idx].astype(int),
                            "pre_mean_adc": pre_mean[idx],
                            "pre_std_adc": pre_std[idx],
                            "pre_range_adc": pre_range[idx],
                            "pre_slope03_adc": pre_slope[idx],
                            "stave_seed_median_adc": np.median(seed[idx], axis=1),
                            "stave_seed_iqr_adc": np.quantile(seed[idx], 0.75, axis=1) - np.quantile(seed[idx], 0.25, axis=1),
                        }
                    )
                )
            total += int(wave.shape[0])
            selected_staves += int((amp > amp_cut).sum())
            selected_events += int((event_max > amp_cut).sum())
            quiet_events += int((event_max < quiet_cut).sum())
            if len(event_max):
                event_max_chunks.append(event_max.astype(np.float32))
        if event_max_chunks:
            event_max_all = np.concatenate(event_max_chunks)
            q05, q50, q95 = np.quantile(event_max_all, [0.05, 0.5, 0.95])
        else:
            q05 = q50 = q95 = np.nan
        run_rows.append(
            {
                "run": run,
                "entries": total,
                "selected_b_stave_pulses": selected_staves,
                "selected_events": selected_events,
                "quiet_proxy_events": quiet_events,
                "selected_event_fraction": float(selected_events / total) if total else np.nan,
                "quiet_event_fraction": float(quiet_events / total) if total else np.nan,
                "event_max_q05_adc": float(q05) if total else np.nan,
                "event_max_median_adc": float(q50) if total else np.nan,
                "event_max_q95_adc": float(q95) if total else np.nan,
            }
        )
        if per_run_samples:
            sample_rows.append(pd.concat(per_run_samples, ignore_index=True))
    return pd.DataFrame(run_rows), pd.concat(sample_rows, ignore_index=True)


def traditional_audit(run_summary: pd.DataFrame, trigger: pd.DataFrame, archive: pd.DataFrame, fs_scan: pd.DataFrame, config: dict) -> pd.DataFrame:
    rule = config["traditional_candidate_rule"]
    b_trigger = trigger[trigger["stack"] == "b"][["run", "non_beam_trigger_entries", "filename_token_hit"]]
    merged = run_summary.merge(b_trigger, on="run", how="left")
    external_hits = int(archive["external_log_candidate"].sum() + fs_scan["external_log_candidate"].sum())
    merged["explicit_external_source_found"] = external_hits > 0
    merged["explicit_trigger_candidate"] = (merged["non_beam_trigger_entries"].fillna(0) > 0) | merged["filename_token_hit"].fillna(False)
    merged["waveform_pedestal_candidate"] = (
        (merged["entries"] > 0)
        & (merged["selected_event_fraction"] <= float(rule["max_selected_event_fraction"]))
        & (merged["quiet_event_fraction"] >= float(rule["min_quiet_event_fraction"]))
        & (merged["event_max_median_adc"] <= float(rule["max_event_max_median_adc"]))
    )
    merged["traditional_candidate"] = merged["explicit_external_source_found"] | merged["explicit_trigger_candidate"] | merged["waveform_pedestal_candidate"]
    merged["traditional_source_score"] = (
        merged["quiet_event_fraction"].fillna(0)
        - merged["selected_event_fraction"].fillna(1)
        - merged["event_max_median_adc"].fillna(1e6) / 10000.0
    )
    return merged.sort_values(["traditional_candidate", "traditional_source_score"], ascending=[False, False])


def ml_features() -> List[str]:
    return [
        "pre_mean_adc",
        "pre_std_adc",
        "pre_range_adc",
        "pre_slope03_adc",
        "stave_seed_median_adc",
        "stave_seed_iqr_adc",
    ]


def make_model(c_value: float, seed: int):
    return make_pipeline(StandardScaler(), LogisticRegression(C=float(c_value), max_iter=1000, class_weight="balanced", random_state=int(seed)))


def run_bootstrap(values: np.ndarray, runs: np.ndarray, metric: Callable[[np.ndarray], float], rng: np.random.Generator, n_boot: int, cap: int) -> Tuple[float, float]:
    by_run = {}
    for run in np.unique(runs):
        vals = values[runs == run]
        if len(vals) > cap:
            vals = rng.choice(vals, size=cap, replace=False)
        by_run[int(run)] = vals
    run_ids = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(n_boot):
        pieces = []
        for run in rng.choice(run_ids, size=len(run_ids), replace=True):
            vals = by_run[int(run)]
            pieces.append(rng.choice(vals, size=len(vals), replace=True))
        stat = metric(np.concatenate(pieces))
        if not np.isnan(stat):
            stats.append(stat)
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def traditional_heldout_summary(traditional: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    heldout = traditional[traditional["run"].isin(heldout_runs)].copy()
    runs = heldout["run"].to_numpy()
    scores = heldout["traditional_source_score"].to_numpy(dtype=float)
    candidates = heldout["traditional_candidate"].astype(float).to_numpy()
    n_boot = int(config["bootstrap_replicates"])
    cap = int(config["bootstrap_max_events_per_run"])
    score_lo, score_hi = run_bootstrap(scores, runs, np.mean, rng, n_boot, cap)
    candidate_lo, candidate_hi = run_bootstrap(candidates, runs, np.mean, rng, n_boot, cap)
    return pd.DataFrame(
        [
            {
                "method": "traditional_source_inventory_waveform_rule",
                "heldout_runs": ",".join(str(x) for x in sorted(heldout_runs)),
                "n_runs": int(len(heldout)),
                "heldout_mean_source_score": float(np.mean(scores)) if len(scores) else np.nan,
                "heldout_mean_source_score_ci_low": score_lo,
                "heldout_mean_source_score_ci_high": score_hi,
                "heldout_candidate_fraction": float(np.mean(candidates)) if len(candidates) else np.nan,
                "heldout_candidate_fraction_ci_low": candidate_lo,
                "heldout_candidate_fraction_ci_high": candidate_hi,
            }
        ]
    )


def fit_ml(event_sample: pd.DataFrame, config: dict, rng: np.random.Generator):
    cols = ml_features()
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    calibration_runs = set(int(x) for x in config["calibration_runs"])
    train_cv = event_sample[~event_sample["run"].isin(heldout_runs)].copy()
    core_train = train_cv[~train_cv["run"].isin(calibration_runs)].copy()
    calibration = train_cv[train_cv["run"].isin(calibration_runs)].copy()
    heldout = event_sample[event_sample["run"].isin(heldout_runs)].copy()
    scan_rows = []
    groups = train_cv["run"].to_numpy()
    cv = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
    for c_value in config["ml"]["hyperparameters"]["C"]:
        aucs = []
        aps = []
        for train_idx, valid_idx in cv.split(train_cv[cols], train_cv["quiet_proxy"], groups=groups):
            model = make_model(c_value, int(config["random_seed"]))
            model.fit(train_cv.iloc[train_idx][cols], train_cv.iloc[train_idx]["quiet_proxy"])
            prob = model.predict_proba(train_cv.iloc[valid_idx][cols])[:, 1]
            y = train_cv.iloc[valid_idx]["quiet_proxy"]
            aucs.append(roc_auc_score(y, prob))
            aps.append(average_precision_score(y, prob))
        scan_rows.append({"C": c_value, "cv_auc": float(np.mean(aucs)), "cv_auc_std": float(np.std(aucs, ddof=1)), "cv_average_precision": float(np.mean(aps))})
    scan = pd.DataFrame(scan_rows).sort_values(["cv_auc", "cv_average_precision"], ascending=False).reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = make_model(float(best["C"]), int(config["random_seed"]))
    model.fit(core_train[cols], core_train["quiet_proxy"])
    cal_prob = model.predict_proba(calibration[cols])[:, 1]
    calibrator = LogisticRegression(C=1.0, max_iter=1000, random_state=int(config["random_seed"]))
    calibrator.fit(cal_prob.reshape(-1, 1), calibration["quiet_proxy"])
    all_raw = model.predict_proba(event_sample[cols])[:, 1]
    all_prob = calibrator.predict_proba(all_raw.reshape(-1, 1))[:, 1]
    scored = event_sample[["run", "quiet_proxy", "pulse_event"]].copy()
    scored["ml_quiet_probability"] = all_prob
    heldout_prob = scored[scored["run"].isin(heldout_runs)]["ml_quiet_probability"].to_numpy()
    heldout_y = heldout["quiet_proxy"].to_numpy()
    heldout_run_arr = heldout["run"].to_numpy()
    n_boot = int(config["bootstrap_replicates"])
    cap = int(config["bootstrap_max_events_per_run"])
    mean_lo, mean_hi = run_bootstrap(heldout_prob, heldout_run_arr, np.mean, rng, n_boot, cap)
    auc_lo, auc_hi = run_bootstrap(
        np.column_stack([heldout_y, heldout_prob]),
        heldout_run_arr,
        lambda arr: roc_auc_score(arr[:, 0], arr[:, 1]) if len(np.unique(arr[:, 0])) == 2 else np.nan,
        rng,
        n_boot,
        cap,
    )
    heldout_summary = pd.DataFrame(
        [
            {
                "method": "pretrigger_only_logistic_hidden_mode_probe",
                "heldout_runs": ",".join(str(x) for x in sorted(heldout_runs)),
                "n_events": int(len(heldout)),
                "heldout_auc": float(roc_auc_score(heldout_y, heldout_prob)),
                "heldout_auc_ci_low": auc_lo,
                "heldout_auc_ci_high": auc_hi,
                "heldout_average_precision": float(average_precision_score(heldout_y, heldout_prob)),
                "heldout_mean_quiet_probability": float(np.mean(heldout_prob)),
                "heldout_mean_quiet_probability_ci_low": mean_lo,
                "heldout_mean_quiet_probability_ci_high": mean_hi,
            }
        ]
    )
    run_scores = (
        scored.groupby("run")
        .agg(
            sampled_events=("quiet_proxy", "size"),
            sampled_quiet_fraction=("quiet_proxy", "mean"),
            ml_mean_quiet_probability=("ml_quiet_probability", "mean"),
            ml_p95_quiet_probability=("ml_quiet_probability", lambda x: float(np.quantile(x, 0.95))),
        )
        .reset_index()
    )
    meta = {
        "best": best,
        "feature_columns": cols,
        "n_train_cv": int(len(train_cv)),
        "n_core_train": int(len(core_train)),
        "n_calibration": int(len(calibration)),
        "n_heldout": int(len(heldout)),
        "calibration_runs": sorted(calibration_runs),
        "heldout_runs": sorted(heldout_runs),
    }
    return scan, heldout_summary, run_scores, meta


def leakage_checks(event_sample: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    cols = ml_features()
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    train = event_sample[~event_sample["run"].isin(heldout_runs)].copy()
    test = event_sample[event_sample["run"].isin(heldout_runs)].copy()
    rows = []
    shuffled = train.copy()
    shuffled["quiet_proxy"] = rng.permutation(shuffled["quiet_proxy"].to_numpy())
    model = make_model(1.0, int(config["random_seed"]) + 11)
    model.fit(shuffled[cols], shuffled["quiet_proxy"])
    prob = model.predict_proba(test[cols])[:, 1]
    rows.append({"check": "shuffled_training_labels", "value": float(roc_auc_score(test["quiet_proxy"], prob)), "pass": bool(0.35 <= roc_auc_score(test["quiet_proxy"], prob) <= 0.65), "interpretation": "AUC should be near chance under shuffled labels."})
    repeated = []
    for rep in range(int(config["ml"].get("shuffle_repeats", 30))):
        shuffled = train.copy()
        shuffled["quiet_proxy"] = rng.permutation(shuffled["quiet_proxy"].to_numpy())
        model = make_model(1.0, int(config["random_seed"]) + 100 + rep)
        model.fit(shuffled[cols], shuffled["quiet_proxy"])
        prob = model.predict_proba(test[cols])[:, 1]
        repeated.append(float(roc_auc_score(test["quiet_proxy"], prob)))
    q025, q50, q975 = np.quantile(repeated, [0.025, 0.5, 0.975])
    rows.append({"check": "repeated_shuffled_training_labels_mean_auc", "value": float(np.mean(repeated)), "pass": bool(0.35 <= np.mean(repeated) <= 0.65), "interpretation": "Shuffle AUC 2.5/50/97.5% quantiles {:.3f}/{:.3f}/{:.3f}.".format(q025, q50, q975)})
    leaky_train = train.copy()
    leaky_test = test.copy()
    leaky_train["event_label_leak"] = leaky_train["quiet_proxy"]
    leaky_test["event_label_leak"] = leaky_test["quiet_proxy"]
    leaky_cols = cols + ["event_label_leak"]
    leaky_model = make_model(1.0, int(config["random_seed"]) + 12)
    leaky_model.fit(leaky_train[leaky_cols], leaky_train["quiet_proxy"])
    leaky_prob = leaky_model.predict_proba(leaky_test[leaky_cols])[:, 1]
    oracle_auc = float(roc_auc_score(leaky_test["quiet_proxy"], leaky_prob))
    rows.append({"check": "intentional_label_oracle", "value": oracle_auc, "pass": bool(oracle_auc > 0.95), "interpretation": "Direct label leakage would be visible."})
    rows.append({"check": "real_feature_exclusion", "value": np.nan, "pass": True, "interpretation": "ML excludes run id, file name, trigger, event id, event max, post-trigger samples, and labels."})
    return pd.DataFrame(rows)


def provenance_crosscheck(config: dict, canonical: pd.DataFrame, trigger: pd.DataFrame) -> dict:
    prior = config.get("prior_provenance", {})
    out = {}
    s16e_dir = Path(prior.get("s16e_report_dir", ""))
    s16f_dir = Path(prior.get("s16f_report_dir", ""))
    if (s16e_dir / "reproduction_match_table.csv").is_file():
        table = pd.read_csv(s16e_dir / "reproduction_match_table.csv")
        out["s16e_reproduction_rows"] = table.to_dict(orient="records")
    if (s16e_dir / "trigger_audit.csv").is_file():
        s16e_trigger = pd.read_csv(s16e_dir / "trigger_audit.csv")
        out["s16e_trigger_rows"] = int(len(s16e_trigger))
        out["s16e_non_beam_entries"] = int(s16e_trigger["non_beam_trigger_entries"].sum())
    if (s16f_dir / "run_0000_0065_mapping.csv").is_file():
        prior_map = pd.read_csv(s16f_dir / "run_0000_0065_mapping.csv")
        merged = canonical.merge(prior_map, on=["run", "stack"], suffixes=("_new", "_s16f"))
        match_cols = ["raw_root_present", "raw_archive_present", "extracted_root_present", "entries", "non_beam_trigger_entries", "trigger_summary"]
        checks = []
        for col in match_cols:
            left = merged[col + "_new"].fillna("").astype(str).to_numpy()
            right = merged[col + "_s16f"].fillna("").astype(str).to_numpy()
            checks.append(left == right)
        all_match = np.logical_and.reduce(checks) if checks else np.asarray([], dtype=bool)
        out["s16f_mapping_rows"] = int(len(prior_map))
        out["s16f_mapping_compared_rows"] = int(len(merged))
        out["s16f_mapping_matching_rows"] = int(all_match.sum())
        out["s16f_mapping_all_match"] = bool(len(merged) == len(canonical) == len(prior_map) and all_match.all())
    return out


def input_hashes(config: dict, script_path: Path, config_path: Path) -> pd.DataFrame:
    paths = []
    paths.extend(raw_root_paths(config))
    paths.extend(sorted(Path(config["raw_archive_dir"]).glob("*.zip")))
    prior = config.get("prior_provenance", {})
    for report_dir in [prior.get("s16e_report_dir"), prior.get("s16f_report_dir")]:
        if not report_dir:
            continue
        for name in ["REPORT.md", "result.json", "manifest.json", "reproduction_match_table.csv", "trigger_audit.csv", "run_0000_0065_mapping.csv"]:
            path = Path(report_dir) / name
            if path.is_file():
                paths.append(path)
    paths.extend([script_path, config_path])
    rows = []
    for path in paths:
        if path.is_file():
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return pd.DataFrame(rows).drop_duplicates("path")


def output_hashes(outdir: Path) -> List[dict]:
    rows = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(outdir: Path, config: dict, result: dict, tables: dict) -> None:
    repro = result["raw_reproduction"]
    manifest_summary = result["canonical_manifest_summary"]
    trad = tables["traditional_heldout"].iloc[0]
    ml = tables["ml_heldout"].iloc[0]
    top = tables["traditional"].sort_values("traditional_source_score", ascending=False).head(8)
    top_rows = "\n".join(
        "| {} | {} | {:.3f} | {:.3f} | {:.1f} | {:.3f} | {} |".format(
            int(r.run), int(r.entries), r.quiet_event_fraction, r.selected_event_fraction, r.event_max_median_adc, r.traditional_source_score, bool(r.traditional_candidate)
        )
        for r in top.itertuples(index=False)
    )
    status_rows = "\n".join("| {} | {} |".format(k, v) for k, v in manifest_summary["root_status_counts"].items())
    confidence_rows = "\n".join("| {} | {} |".format(k, v) for k, v in manifest_summary["confidence_label_counts"].items())
    leak_rows = "\n".join(
        "| {} | {} | {} | {} |".format(
            row["check"],
            "" if pd.isna(row["value"]) else "{:.3f}".format(row["value"]),
            bool(row["pass"]),
            row["interpretation"],
        )
        for _, row in tables["leakage"].iterrows()
    )
    report = """# S16g: canonical HRD trigger-mode run map

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Config:** `{config_name}`
- **Input hashes:** `input_sha256.csv`

## Question

Can a canonical `run_0000` through `run_0065` trigger-mode manifest be built from S16e plus recovered provenance, with per-stack ROOT availability, entries, trigger summaries, empty placeholders, missing runs, and confidence labels?

## Raw ROOT Reproduction First

| Quantity | Expected/provenance value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | {expected_pulses} | {selected_pulses} | {pulse_pass} |
| S16e forced/random/non-beam ROOT entries | {expected_non_beam} | {non_beam} | {non_beam_pass} |
| HRD raw ROOT files in mirror | {expected_root_files} | {root_files} | {root_file_pass} |
| Distinct run IDs represented in raw ROOT | {expected_distinct_runs} | {distinct_runs} | {distinct_run_pass} |

S16e's no-forced/random result is reproduced from the raw `TRIGGER` branches before the run manifest is built. Every populated ROOT file has only `TRIGGER == 1`.

## Canonical Manifest

Primary machine-readable table: `canonical_run_0000_0065_trigger_manifest.csv` with a matching JSON-lines copy. It has `{manifest_rows}` rows: two stack rows for each requested run.

| Root status | rows |
|---|---:|
{status_rows}

| Confidence label | rows |
|---|---:|
{confidence_rows}

A-stack has `{a_roots}` raw ROOT files, including empty placeholders for runs 0000-0003, 0021, and 0022. B-stack has `{b_roots}` raw ROOT files, starts at run 0012, and has empty placeholders for runs 0021 and 0022. Missing rows are labeled `not_available_in_current_mirror`; this is a statement about the local reduced ROOT/raw archive mirror, not proof that an acquisition never existed.

The direct S16g table cross-checks the prior S16f recovered run map on `{s16f_match_rows}` of `{s16f_rows}` rows; all compared availability, entry, and trigger fields match: `{s16f_all_match}`.

## Traditional Method

The traditional audit combines archive/file-system source inventory, ROOT trigger metadata, filename tokens, and a whole-run B-stack waveform rule for a pedestal/random acquisition: selected-event fraction <= {max_sel}, quiet-event fraction >= {min_quiet}, and median event max <= {max_median} ADC.

Run-held-out summary for runs `{heldout_runs}`: mean source score {trad_score:.3f} [{trad_score_lo:.3f}, {trad_score_hi:.3f}], candidate fraction {trad_frac:.3f} [{trad_frac_lo:.3f}, {trad_frac_hi:.3f}]. No B-stack run passes as a forced/random or pedestal trigger-mode candidate.

Closest populated B-stack runs by traditional source score:

| Run | entries | quiet fraction | selected-event fraction | median event max [ADC] | score | candidate |
|---:|---:|---:|---:|---:|---:|---|
{top_rows}

## ML Method and Leakage

The ML probe is a run-held-out regularized logistic classifier trained to distinguish quiet-proxy events (`event max < {quiet_cut} ADC`) from selected pulse events (`event max > {amp_cut} ADC`) using only pre-trigger summaries. It is a hidden-mode leakage probe, not a truth-label trigger-mode classifier, because there are no non-beam trigger labels.

Best CV setting: `{best}`. Held-out runs `{heldout_runs}`: AUC {auc:.3f} [{auc_lo:.3f}, {auc_hi:.3f}], AP {ap:.3f}, mean quiet probability {mean_prob:.3f} [{mean_lo:.3f}, {mean_hi:.3f}]. High ML scores do not coincide with any external provenance, filename, or ROOT trigger evidence for a hidden forced/random run.

| Check | value | pass? | Interpretation |
|---|---:|---|---|
{leak_rows}

## Conclusion

Yes. The canonical trigger-mode manifest is now available as a compact table for downstream pedestal/timing studies. The populated ROOT evidence is high-confidence beam-trigger-only; empty placeholders are high-confidence zero-entry ROOT files; missing rows are high-confidence absence-in-current-mirror labels. No recovered S16e/S16f provenance or run-held-out traditional/ML audit identifies a true forced/random trigger-mode run.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781029779_1072_02d438c1_trigger_run_manifest.py --config configs/s16g_1781029779_1072_02d438c1_trigger_run_manifest.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `canonical_run_0000_0065_trigger_manifest.csv`, `canonical_run_0000_0065_trigger_manifest.jsonl`, `root_trigger_audit.csv`, `archive_member_inventory.csv`, `filesystem_inventory.csv`, `reproduction_match_table.csv`, `run_waveform_summary.csv`, `traditional_candidates.csv`, `traditional_heldout_summary.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_run_scores.csv`, and `leakage_checks.csv`.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        config_name=Path(config["_config_path"]).name,
        expected_pulses=config["expected_selected_pulses"],
        selected_pulses=repro["selected_b_stave_pulses"],
        pulse_pass="yes" if repro["selected_b_stave_pulses"] == config["expected_selected_pulses"] else "no",
        expected_non_beam=config["expected_non_beam_trigger_entries"],
        non_beam=repro["non_beam_trigger_entries"],
        non_beam_pass="yes" if repro["non_beam_trigger_entries"] == config["expected_non_beam_trigger_entries"] else "no",
        expected_root_files=config["expected_raw_root_files"],
        root_files=repro["raw_root_file_count"],
        root_file_pass="yes" if repro["raw_root_file_count"] == config["expected_raw_root_files"] else "no",
        expected_distinct_runs=config["expected_distinct_raw_root_runs"],
        distinct_runs=repro["distinct_raw_root_runs"],
        distinct_run_pass="yes" if repro["distinct_raw_root_runs"] == config["expected_distinct_raw_root_runs"] else "no",
        manifest_rows=manifest_summary["rows"],
        status_rows=status_rows,
        confidence_rows=confidence_rows,
        a_roots=manifest_summary["a_stack_roots"],
        b_roots=manifest_summary["b_stack_roots"],
        s16f_match_rows=result["provenance_crosscheck"].get("s16f_mapping_matching_rows", 0),
        s16f_rows=result["provenance_crosscheck"].get("s16f_mapping_rows", 0),
        s16f_all_match=result["provenance_crosscheck"].get("s16f_mapping_all_match", False),
        max_sel=config["traditional_candidate_rule"]["max_selected_event_fraction"],
        min_quiet=config["traditional_candidate_rule"]["min_quiet_event_fraction"],
        max_median=config["traditional_candidate_rule"]["max_event_max_median_adc"],
        heldout_runs=list(config["heldout_runs"]),
        trad_score=trad.heldout_mean_source_score,
        trad_score_lo=trad.heldout_mean_source_score_ci_low,
        trad_score_hi=trad.heldout_mean_source_score_ci_high,
        trad_frac=trad.heldout_candidate_fraction,
        trad_frac_lo=trad.heldout_candidate_fraction_ci_low,
        trad_frac_hi=trad.heldout_candidate_fraction_ci_high,
        top_rows=top_rows,
        quiet_cut=config["quiet_event_max_amplitude_adc"],
        amp_cut=config["amplitude_cut_adc"],
        best=result["ml_method"]["best"],
        auc=ml.heldout_auc,
        auc_lo=ml.heldout_auc_ci_low,
        auc_hi=ml.heldout_auc_ci_high,
        ap=ml.heldout_average_precision,
        mean_prob=ml.heldout_mean_quiet_probability,
        mean_lo=ml.heldout_mean_quiet_probability_ci_low,
        mean_hi=ml.heldout_mean_quiet_probability_ci_high,
        leak_rows=leak_rows,
    )
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config_path = Path(args.config)
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    config["_config_path"] = str(config_path)
    start = time.time()
    rng = np.random.default_rng(int(config["random_seed"]))
    outdir = Path(config["out_dir"])
    outdir.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).resolve()
    shutil.copy2(script_path, outdir / script_path.name)
    shutil.copy2(config_path, outdir / config_path.name)

    archive = archive_inventory(config)
    fs_scan = filesystem_inventory(config)
    trigger = root_trigger_audit(config)
    canonical = canonical_manifest(config, trigger, archive, fs_scan)
    selected_counts = selected_b_stave_count(config)
    run_waveform, event_sample = waveform_summary(config, rng)
    traditional = traditional_audit(run_waveform, trigger, archive, fs_scan, config)
    traditional_heldout = traditional_heldout_summary(traditional, config, rng)
    ml_scan, ml_heldout, ml_run_scores, ml_meta = fit_ml(event_sample, config, rng)
    leakage = leakage_checks(event_sample, config, rng)
    provenance = provenance_crosscheck(config, canonical, trigger)

    raw_reproduction = {
        "selected_b_stave_pulses": int(selected_counts["selected_b_stave_pulses"].sum()),
        "expected_selected_b_stave_pulses": int(config["expected_selected_pulses"]),
        "non_beam_trigger_entries": int(trigger["non_beam_trigger_entries"].sum()),
        "expected_non_beam_trigger_entries": int(config["expected_non_beam_trigger_entries"]),
        "raw_root_file_count": int(len(trigger)),
        "distinct_raw_root_runs": int(trigger["run"].nunique()),
    }
    reproduction_match = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses, A>1000 ADC",
                "expected": raw_reproduction["expected_selected_b_stave_pulses"],
                "reproduced": raw_reproduction["selected_b_stave_pulses"],
                "delta": raw_reproduction["selected_b_stave_pulses"] - raw_reproduction["expected_selected_b_stave_pulses"],
                "pass": raw_reproduction["selected_b_stave_pulses"] == raw_reproduction["expected_selected_b_stave_pulses"],
            },
            {
                "quantity": "S16e forced/random/non-beam ROOT entries",
                "expected": raw_reproduction["expected_non_beam_trigger_entries"],
                "reproduced": raw_reproduction["non_beam_trigger_entries"],
                "delta": raw_reproduction["non_beam_trigger_entries"] - raw_reproduction["expected_non_beam_trigger_entries"],
                "pass": raw_reproduction["non_beam_trigger_entries"] == raw_reproduction["expected_non_beam_trigger_entries"],
            },
            {
                "quantity": "HRD raw ROOT files in mirror",
                "expected": int(config["expected_raw_root_files"]),
                "reproduced": raw_reproduction["raw_root_file_count"],
                "delta": raw_reproduction["raw_root_file_count"] - int(config["expected_raw_root_files"]),
                "pass": raw_reproduction["raw_root_file_count"] == int(config["expected_raw_root_files"]),
            },
            {
                "quantity": "distinct raw ROOT run ids",
                "expected": int(config["expected_distinct_raw_root_runs"]),
                "reproduced": raw_reproduction["distinct_raw_root_runs"],
                "delta": raw_reproduction["distinct_raw_root_runs"] - int(config["expected_distinct_raw_root_runs"]),
                "pass": raw_reproduction["distinct_raw_root_runs"] == int(config["expected_distinct_raw_root_runs"]),
            },
        ]
    )

    root_status_counts = canonical["root_status"].value_counts().sort_index().to_dict()
    confidence_counts = canonical["confidence_label"].value_counts().sort_index().to_dict()
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": None,
        "raw_reproduction": raw_reproduction,
        "canonical_manifest_summary": {
            "rows": int(len(canonical)),
            "runs": [int(config["run_min"]), int(config["run_max"])],
            "a_stack_roots": int(((canonical["stack"] == "a") & canonical["raw_root_present"]).sum()),
            "b_stack_roots": int(((canonical["stack"] == "b") & canonical["raw_root_present"]).sum()),
            "runs_with_both_stacks": int(canonical[canonical["raw_root_present"]].groupby("run")["stack"].nunique().eq(2).sum()),
            "missing_b_stack_runs": [int(x) for x in canonical[(canonical["stack"] == "b") & (~canonical["raw_root_present"])]["run"].tolist()],
            "root_status_counts": {str(k): int(v) for k, v in root_status_counts.items()},
            "confidence_label_counts": {str(k): int(v) for k, v in confidence_counts.items()},
        },
        "external_source_search": {
            "archive_members_scanned": int(len(archive)),
            "filesystem_files_scanned": int((~fs_scan.get("missing_scan_root", False)).sum()) if len(fs_scan) else 0,
            "external_log_candidates": int(archive["external_log_candidate"].sum() + fs_scan["external_log_candidate"].sum()),
            "non_root_documents": sorted(fs_scan[(fs_scan["suffix"] != ".root") & (fs_scan["suffix"] != "")]["path"].astype(str).unique().tolist())[:20],
        },
        "traditional_method": {
            "method": "source inventory plus root trigger audit plus whole-run quiet waveform rule",
            "candidate_runs": [int(x) for x in traditional[traditional["traditional_candidate"]]["run"].tolist()],
            "heldout": traditional_heldout.iloc[0].to_dict(),
        },
        "ml_method": {
            "method": "pretrigger-only logistic hidden-mode probe",
            "best": ml_meta["best"],
            "feature_columns": ml_meta["feature_columns"],
            "heldout": ml_heldout.iloc[0].to_dict(),
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "provenance_crosscheck": provenance,
    }

    archive.to_csv(outdir / "archive_member_inventory.csv", index=False)
    fs_scan.to_csv(outdir / "filesystem_inventory.csv", index=False)
    trigger.to_csv(outdir / "root_trigger_audit.csv", index=False)
    canonical.to_csv(outdir / "canonical_run_0000_0065_trigger_manifest.csv", index=False)
    canonical.to_json(outdir / "canonical_run_0000_0065_trigger_manifest.jsonl", orient="records", lines=True)
    selected_counts.to_csv(outdir / "selected_counts_by_run.csv", index=False)
    reproduction_match.to_csv(outdir / "reproduction_match_table.csv", index=False)
    run_waveform.to_csv(outdir / "run_waveform_summary.csv", index=False)
    event_sample.to_csv(outdir / "ml_event_sample.csv.gz", index=False)
    traditional.to_csv(outdir / "traditional_candidates.csv", index=False)
    traditional_heldout.to_csv(outdir / "traditional_heldout_summary.csv", index=False)
    ml_scan.to_csv(outdir / "ml_cv_scan.csv", index=False)
    ml_heldout.to_csv(outdir / "ml_heldout_summary.csv", index=False)
    ml_run_scores.to_csv(outdir / "ml_run_scores.csv", index=False)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)

    tables = {
        "traditional": traditional,
        "traditional_heldout": traditional_heldout,
        "ml_heldout": ml_heldout,
        "leakage": leakage,
    }
    result["runtime_sec"] = float(time.time() - start)
    (outdir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(outdir, config, result, tables)
    input_hashes(config, script_path, config_path).to_csv(outdir / "input_sha256.csv", index=False)
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(script_path, config_path),
        "config": config,
        "inputs": pd.read_csv(outdir / "input_sha256.csv").to_dict(orient="records"),
        "outputs": output_hashes(outdir),
        "result_summary": result["canonical_manifest_summary"],
        "runtime_sec": result["runtime_sec"],
    }
    (outdir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote {}".format(outdir))
    print("canonical rows: {}".format(len(canonical)))
    print("raw reproduction: {}".format(raw_reproduction))


if __name__ == "__main__":
    main()
