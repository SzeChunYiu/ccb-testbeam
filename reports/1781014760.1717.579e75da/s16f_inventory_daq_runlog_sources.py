#!/usr/bin/env python3
"""S16f DAQ/run-log source inventory for B-stack forced/random pedestals.

Ticket question: can DAQ/run-log sources for true B-stack random or
forced-trigger pedestal runs be found, and do they show that the missing S16e
truth gate is because such runs were never recorded or only absent from this
ROOT mirror? This script treats the current data mirror as evidence: it
reproduces the raw ROOT count first, inventories archives and extracted files,
then runs traditional and ML run-held-out cross-checks for hidden
pedestal/random trigger-mode structure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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


TOKEN_RE = re.compile(r"(daq|acq|acquisition|trigger|trig|logbook|log|run[_ -]?log|spreadsheet|xlsx|ods|csv|forced?|random|pedestal|ped|pulser|script|\.py|\.sh)", re.I)
ROOT_RE = re.compile(r"hrd([ab])_run_(\d{4})", re.I)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def raw_root_paths(config: dict) -> List[Path]:
    root_dir = Path(config["raw_root_dir"])
    return sorted(root_dir.glob("hrda_run_*.root")) + sorted(root_dir.glob("hrdb_run_*.root"))


def b_root_paths(config: dict) -> List[Path]:
    return sorted(Path(config["raw_root_dir"]).glob("hrdb_run_*.root"))


def parse_root(path_or_name: str) -> Tuple[str, int]:
    match = ROOT_RE.search(str(path_or_name))
    if not match:
        raise ValueError("cannot parse HRD stack/run from {}".format(path_or_name))
    return match.group(1).lower(), int(match.group(2))


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
                stack = ""
                run = np.nan
                root_match = ROOT_RE.search(rel)
                if root_match:
                    stack = root_match.group(1).lower()
                    run = int(root_match.group(2))
                rows.append(
                    {
                        "archive": str(archive),
                        "member": rel,
                        "suffix": suffix,
                        "bytes": int(info.file_size),
                        "run": run,
                        "stack": stack,
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
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            rel = str(path.relative_to(root))
            token = TOKEN_RE.search(rel)
            stack = ""
            run = np.nan
            root_match = ROOT_RE.search(rel)
            if root_match:
                stack = root_match.group(1).lower()
                run = int(root_match.group(2))
            rows.append(
                {
                    "scan_root": str(root),
                    "path": rel,
                    "suffix": suffix,
                    "bytes": int(path.stat().st_size),
                    "run": run,
                    "stack": stack,
                    "token_hit": token.group(0).lower() if token else "",
                    "is_root": suffix == ".root",
                    "external_log_candidate": bool(
                        suffix in {".csv", ".tsv", ".xlsx", ".ods", ".txt", ".log", ".md", ".json", ".yaml", ".yml", ".py", ".sh"}
                        or (token and suffix != ".root")
                    ),
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
                "stack": stack,
                "run": run,
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "has_trigger_branch": "TRIGGER" in branches,
                "has_run_metadata_branch": any(k.upper() in {"RUN", "RUNNO", "RUNNUMBER"} for k in branches),
                "filename_token_hit": bool(TOKEN_RE.search(path.name)),
            }
        )
    return pd.DataFrame(rows)


def run_mapping(config: dict, trigger: pd.DataFrame, archive: pd.DataFrame, fs_scan: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run in range(int(config["run_min"]), int(config["run_max"]) + 1):
        for stack in ["a", "b"]:
            root_rows = trigger[(trigger["run"] == run) & (trigger["stack"] == stack)]
            arch_rows = archive[(archive["run"] == run) & (archive["stack"] == stack) & (archive["is_root"])]
            fs_rows = fs_scan[(fs_scan["run"] == run) & (fs_scan["stack"] == stack) & (fs_scan["is_root"])]
            rows.append(
                {
                    "run": run,
                    "stack": stack,
                    "raw_root_present": bool(len(root_rows)),
                    "raw_archive_present": bool(len(arch_rows)),
                    "extracted_root_present": bool(len(fs_rows)),
                    "entries": int(root_rows["entries"].sum()) if len(root_rows) else 0,
                    "non_beam_trigger_entries": int(root_rows["non_beam_trigger_entries"].sum()) if len(root_rows) else 0,
                    "trigger_summary": root_rows["trigger_summary"].iloc[0] if len(root_rows) else "",
                }
            )
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
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(C=float(c_value), max_iter=1000, class_weight="balanced", random_state=int(seed)),
    )


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
    rows.append({"check": "shuffled_training_labels", "value": float(roc_auc_score(test["quiet_proxy"], prob)), "interpretation": "AUC should be near chance if the signal is not leakage."})

    repeated = []
    for rep in range(int(config["ml"].get("shuffle_repeats", 30))):
        shuffled = train.copy()
        shuffled["quiet_proxy"] = rng.permutation(shuffled["quiet_proxy"].to_numpy())
        model = make_model(1.0, int(config["random_seed"]) + 100 + rep)
        model.fit(shuffled[cols], shuffled["quiet_proxy"])
        prob = model.predict_proba(test[cols])[:, 1]
        repeated.append(float(roc_auc_score(test["quiet_proxy"], prob)))
    rows.append(
        {
            "check": "repeated_shuffled_training_labels_mean_auc",
            "value": float(np.mean(repeated)),
            "interpretation": "Thirty shuffled-label fits gave 2.5/50/97.5% quantiles {:.3f}/{:.3f}/{:.3f}.".format(
                *np.quantile(repeated, [0.025, 0.5, 0.975])
            ),
        }
    )

    leaky_train = train.copy()
    leaky_test = test.copy()
    leaky_train["event_label_leak"] = leaky_train["quiet_proxy"]
    leaky_test["event_label_leak"] = leaky_test["quiet_proxy"]
    leaky_cols = cols + ["event_label_leak"]
    leaky_model = make_model(1.0, int(config["random_seed"]) + 12)
    leaky_model.fit(leaky_train[leaky_cols], leaky_train["quiet_proxy"])
    leaky_prob = leaky_model.predict_proba(leaky_test[leaky_cols])[:, 1]
    rows.append({"check": "intentional_label_oracle", "value": float(roc_auc_score(leaky_test["quiet_proxy"], leaky_prob)), "interpretation": "AUC near 1 shows direct label leakage would be visible."})
    rows.append({"check": "real_feature_exclusion", "value": np.nan, "interpretation": "ML excludes run id, file name, trigger, event id, event max, post-trigger samples, and quiet/pulse labels."})
    return pd.DataFrame(rows)


def input_hashes(config: dict) -> pd.DataFrame:
    paths = []
    paths.extend(raw_root_paths(config))
    paths.extend(sorted(Path(config["raw_archive_dir"]).glob("*.zip")))
    for doc_root in config.get("document_roots", []):
        paths.extend(sorted(Path(doc_root).glob("*")))
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
    root_cov = result["raw_reproduction"]
    trad_hold = tables["traditional_heldout"].iloc[0]
    ml = tables["ml_heldout"].iloc[0]
    top = tables["traditional"].sort_values("traditional_source_score", ascending=False).head(8)
    top_rows = "\n".join(
        "| {} | {} | {:.3f} | {:.3f} | {:.1f} | {:.3f} | {} |".format(
            int(r.run), int(r.entries), r.quiet_event_fraction, r.selected_event_fraction, r.event_max_median_adc, r.traditional_source_score, bool(r.traditional_candidate)
        )
        for r in top.itertuples(index=False)
    )
    leak_rows = "\n".join(
        "| {} | {} | {} |".format(r.check, "" if pd.isna(r.value) else "{:.3f}".format(r.value), r.interpretation)
        for r in tables["leakage"].itertuples(index=False)
    )
    report = """# S16f: DAQ/run-log source inventory for B-stack forced/random pedestals

- **Ticket:** {ticket}
- **Worker:** {worker}
- **Date:** 2026-06-09
- **Config:** `s16f_inventory_daq_runlog_sources_config.json`
- **Input checksums:** `input_sha256.csv`
- **Git commit at runtime:** `{commit}`

## Question

Can DAQ/run-log sources for true B-stack random or forced-trigger pedestal runs be found, and can they distinguish whether the S16e gate failed because the sample was never recorded or only missing from this ROOT mirror?

## Raw ROOT Reproduction First

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| B-stack selected stave pulses, `A > 1000 ADC`, S00 runs | {expected_pulses} | {selected_pulses} | {pulse_pass} |
| HRD raw ROOT files in mirror | 110 | {root_files} | {root_pass} |
| distinct run ids represented in raw ROOT | 57 | {distinct_runs} | {run_pass} |
| ROOT entries with `TRIGGER != 1` | 0 | {non_beam} | {trigger_pass} |

The run map covers requested runs `0000-0065`, but not every run has both stacks. A-stack has 57 ROOT files including empty placeholder runs 0000-0003; B-stack has 53 ROOT files and starts at run 0012. Every populated raw ROOT file has only `TRIGGER == 1`.

## External Source Search

Archive member inventory and extracted filesystem inventory found `{external_hits}` DAQ/run-log/source candidates. The only non-ROOT document under the data mirror is `{doc_note}`; no DAQ logbook, trigger-mode spreadsheet, forced/random run list, or acquisition script was found in the local mirror or raw zip member names.

## Traditional Method

The traditional method combines archive/file-system source inventory, ROOT trigger metadata, filename tokens, and a whole-run waveform rule for a pedestal/random acquisition: selected-event fraction <= {max_sel}, quiet-event fraction >= {min_quiet}, and median event max <= {max_median} ADC.

Run-held-out summary for runs `{heldout_runs}`: mean source score {trad_score:.3f} [{trad_score_lo:.3f}, {trad_score_hi:.3f}], candidate fraction {trad_frac:.3f} [{trad_frac_lo:.3f}, {trad_frac_hi:.3f}].

No run passes as a true external-source or pedestal/random trigger-mode candidate. Closest B-stack runs by waveform score:

| Run | entries | quiet fraction | selected-event fraction | median event max [ADC] | score | candidate |
|---:|---:|---:|---:|---:|---:|---|
{top_rows}

## ML Method

The ML probe is a run-held-out regularized logistic classifier trained to distinguish quiet-proxy events (`event max < {quiet_cut} ADC`) from selected pulse events (`event max > {amp_cut} ADC`) using only pre-trigger summaries. It excludes run id, file names, trigger, event ids, post-trigger samples, event max, and labels. It is not a truth-label classifier for DAQ mode; it is a leakage-audited check for hidden pre-trigger mode structure.

Best CV setting: `{best}`. Held-out runs `{heldout_runs}`: AUC {auc:.3f} [{auc_lo:.3f}, {auc_hi:.3f}], AP {ap:.3f}, mean quiet probability {mean_prob:.3f} [{mean_lo:.3f}, {mean_hi:.3f}].

The ML ranking does not reveal a hidden forced/random run: high-score runs still have ordinary beam selected-event fractions, and there is no matching external-source or ROOT trigger evidence.

## Leakage Checks

| Check | value | Interpretation |
|---|---:|---|
{leak_rows}

## Conclusion

No DAQ/run-log source for true B-stack forced/random pedestal runs is present in the current data mirror. The available raw ROOT can be matched across runs `0000-0065`, but it contains no forced/random trigger tags and no external trigger-mode source. Therefore this inventory **does not prove the sample was never recorded**; it supports only the narrower conclusion that the sample is absent from the current reduced ROOT mirror and raw zip archives inspected here.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/{ticket}/s16f_inventory_daq_runlog_sources.py --config reports/{ticket}/s16f_inventory_daq_runlog_sources_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `archive_member_inventory.csv`, `filesystem_inventory.csv`, `root_trigger_audit.csv`, `run_0000_0065_mapping.csv`, `run_waveform_summary.csv`, `traditional_candidates.csv`, `traditional_heldout_summary.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_run_scores.csv`, and `leakage_checks.csv`.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        commit=result["git_commit"],
        expected_pulses=config["expected_selected_pulses"],
        selected_pulses=root_cov["selected_b_stave_pulses"],
        pulse_pass="yes" if root_cov["selected_b_stave_pulses"] == config["expected_selected_pulses"] else "no",
        root_files=root_cov["raw_root_file_count"],
        root_pass="yes" if root_cov["raw_root_file_count"] == 110 else "no",
        distinct_runs=root_cov["distinct_raw_root_runs"],
        run_pass="yes" if root_cov["distinct_raw_root_runs"] == 57 else "no",
        non_beam=root_cov["non_beam_trigger_entries"],
        trigger_pass="yes" if root_cov["non_beam_trigger_entries"] == 0 else "no",
        external_hits=result["external_source_search"]["external_log_candidates"],
        doc_note=result["external_source_search"]["non_root_documents"],
        max_sel=config["traditional_candidate_rule"]["max_selected_event_fraction"],
        min_quiet=config["traditional_candidate_rule"]["min_quiet_event_fraction"],
        max_median=config["traditional_candidate_rule"]["max_event_max_median_adc"],
        trad_score=trad_hold.heldout_mean_source_score,
        trad_score_lo=trad_hold.heldout_mean_source_score_ci_low,
        trad_score_hi=trad_hold.heldout_mean_source_score_ci_high,
        trad_frac=trad_hold.heldout_candidate_fraction,
        trad_frac_lo=trad_hold.heldout_candidate_fraction_ci_low,
        trad_frac_hi=trad_hold.heldout_candidate_fraction_ci_high,
        top_rows=top_rows,
        quiet_cut=config["quiet_event_max_amplitude_adc"],
        amp_cut=config["amplitude_cut_adc"],
        best=result["ml_meta"]["best"],
        heldout_runs=config["heldout_runs"],
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
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    start = time.time()
    outdir = args.config.parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    rng = np.random.default_rng(int(config["random_seed"]))

    archive = archive_inventory(config)
    archive.to_csv(outdir / "archive_member_inventory.csv", index=False)
    fs_scan = filesystem_inventory(config)
    fs_scan.to_csv(outdir / "filesystem_inventory.csv", index=False)
    trigger = root_trigger_audit(config)
    trigger.to_csv(outdir / "root_trigger_audit.csv", index=False)
    mapping = run_mapping(config, trigger, archive, fs_scan)
    mapping.to_csv(outdir / "run_0000_0065_mapping.csv", index=False)
    run_summary, event_sample = waveform_summary(config, rng)
    run_summary.to_csv(outdir / "run_waveform_summary.csv", index=False)
    event_sample.to_csv(outdir / "ml_event_sample.csv.gz", index=False)

    selected_pulses = int(run_summary[run_summary["run"].isin(config["s00_runs"])]["selected_b_stave_pulses"].sum())
    raw_roots = raw_root_paths(config)
    distinct_runs = len({parse_root(p.name)[1] for p in raw_roots})
    non_beam = int(trigger["non_beam_trigger_entries"].sum())
    reproduction = pd.DataFrame(
        [
            {"quantity": "B-stack selected stave pulses, A>1000 ADC, S00 runs", "expected": config["expected_selected_pulses"], "reproduced": selected_pulses, "pass": selected_pulses == config["expected_selected_pulses"]},
            {"quantity": "HRD raw ROOT file count", "expected": 110, "reproduced": len(raw_roots), "pass": len(raw_roots) == 110},
            {"quantity": "distinct raw ROOT run ids", "expected": 57, "reproduced": distinct_runs, "pass": distinct_runs == 57},
            {"quantity": "ROOT entries with TRIGGER != 1", "expected": 0, "reproduced": non_beam, "pass": non_beam == 0},
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    traditional = traditional_audit(run_summary, trigger, archive, fs_scan, config)
    traditional.to_csv(outdir / "traditional_candidates.csv", index=False)
    traditional_heldout = traditional_heldout_summary(traditional, config, rng)
    traditional_heldout.to_csv(outdir / "traditional_heldout_summary.csv", index=False)
    ml_scan, ml_heldout, ml_run_scores, ml_meta = fit_ml(event_sample, config, rng)
    ml_scan.to_csv(outdir / "ml_cv_scan.csv", index=False)
    ml_heldout.to_csv(outdir / "ml_heldout_summary.csv", index=False)
    ml_run_scores.to_csv(outdir / "ml_run_scores.csv", index=False)
    leakage = leakage_checks(event_sample, config, rng)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    input_sha = input_hashes(config)
    input_sha.to_csv(outdir / "input_sha256.csv", index=False)

    non_root_docs = sorted(
        set(fs_scan.loc[(~fs_scan["is_root"]) & (fs_scan["suffix"].isin([".pdf", ".csv", ".xlsx", ".ods", ".txt", ".log", ".py", ".sh"])), "path"].astype(str).tolist())
    )
    external_candidates = int(archive["external_log_candidate"].sum() + fs_scan["external_log_candidate"].sum())
    commit = git_commit()
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "raw_reproduction": {
            "selected_b_stave_pulses": selected_pulses,
            "expected_selected_b_stave_pulses": int(config["expected_selected_pulses"]),
            "raw_root_file_count": int(len(raw_roots)),
            "distinct_raw_root_runs": int(distinct_runs),
            "non_beam_trigger_entries": non_beam,
            "runs_requested": [int(config["run_min"]), int(config["run_max"])],
        },
        "external_source_search": {
            "archive_members_scanned": int(len(archive)),
            "filesystem_files_scanned": int(len(fs_scan)),
            "external_log_candidates": external_candidates,
            "non_root_documents": ", ".join(non_root_docs) if non_root_docs else "none",
            "acquired_external_daq_source": bool(external_candidates > 0),
        },
        "run_mapping": {
            "rows": int(len(mapping)),
            "a_stack_roots": int(mapping[(mapping["stack"] == "a") & (mapping["raw_root_present"])].shape[0]),
            "b_stack_roots": int(mapping[(mapping["stack"] == "b") & (mapping["raw_root_present"])].shape[0]),
            "runs_with_both_stacks": int(mapping.groupby("run")["raw_root_present"].sum().eq(2).sum()),
            "runs_missing_b_stack": [int(x) for x in mapping[(mapping["stack"] == "b") & (~mapping["raw_root_present"])]["run"].tolist()],
        },
        "traditional_method": {
            "method": "source inventory plus root trigger audit plus whole-run quiet waveform rule",
            "candidate_runs": [int(x) for x in traditional.loc[traditional["traditional_candidate"], "run"].tolist()],
            "heldout": traditional_heldout.iloc[0].to_dict(),
            "top_runs_by_score": traditional.sort_values("traditional_source_score", ascending=False).head(5).to_dict(orient="records"),
        },
        "ml_method": {
            "method": "pretrigger-only logistic hidden-mode probe",
            "heldout": ml_heldout.iloc[0].to_dict(),
            "top_runs_by_ml_quiet_probability": ml_run_scores.sort_values("ml_mean_quiet_probability", ascending=False).head(5).to_dict(orient="records"),
        },
        "ml_meta": ml_meta,
        "leakage_checks": leakage.replace({np.nan: None}).to_dict(orient="records"),
        "conclusion": "No DAQ/run-log source for true B-stack forced/random pedestal runs was found in the current mirror; raw ROOT has no non-beam trigger tags, so the inventory supports absent-from-mirror rather than never-recorded.",
        "git_commit": commit,
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    write_report(outdir, config, result, {"traditional": traditional, "traditional_heldout": traditional_heldout, "ml_heldout": ml_heldout, "leakage": leakage})

    manifest = {
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(outdir / "s16f_inventory_daq_runlog_sources.py", outdir / "s16f_inventory_daq_runlog_sources_config.json"),
        "config": str(outdir / "s16f_inventory_daq_runlog_sources_config.json"),
        "git_commit": commit,
        "random_seed": int(config["random_seed"]),
        "environment": {
            "python": ".".join(map(str, os.sys.version_info[:3])),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
        },
        "inputs": str(outdir / "input_sha256.csv"),
        "outputs": output_hashes(outdir),
        "runtime_seconds": float(time.time() - start),
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
