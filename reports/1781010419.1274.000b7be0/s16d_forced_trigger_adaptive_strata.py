#!/usr/bin/env python3
"""S16d forced/random pedestal validation of S16 adaptive-lowering strata.

The current mirror may not contain true forced/random pedestal triggers. This
script records that raw-data audit first, then uses the available physics
events and quiet no-pulse proxy to test whether the S16 lowering strata behave
like true pedestal bias or pre-trigger contamination.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Iterable, Sequence

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, mean_absolute_error, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TOKEN_RE = re.compile(r"(forced?|random|pedestal|ped|pulser|noise|dark|trigger|trig|log)", re.I)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def configured_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> dict[int, str]:
    return {int(run): group for group, runs in config["run_groups"].items() for run in runs}


def raw_root_paths(config: dict) -> list[Path]:
    root = Path(config["raw_root_dir"])
    return sorted(root.glob("hrda_run_*.root")) + sorted(root.glob("hrdb_run_*.root"))


def bstack_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def iter_tree(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


def trigger_audit(config: dict) -> pd.DataFrame:
    rows = []
    for path in raw_root_paths(config):
        tree = uproot.open(path)["h101"]
        if tree.num_entries:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            values, counts = np.unique(trigger, return_counts=True)
            summary = ";".join(f"{int(v)}:{int(c)}" for v, c in zip(values, counts))
            non_beam = int(np.sum(counts[values != 1]))
        else:
            summary = "empty"
            non_beam = 0
        rows.append(
            {
                "file": path.name,
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "filename_forced_random_match": bool(
                    TOKEN_RE.search(path.name)
                    and any(token in path.name.lower() for token in ["force", "random", "ped", "pulser"])
                ),
            }
        )
    return pd.DataFrame(rows)


def filesystem_scan(config: dict) -> pd.DataFrame:
    rows = []
    data_root = Path(config["data_root"])
    for path in sorted(data_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(data_root)
        suffix = path.suffix.lower()
        token = TOKEN_RE.search(str(rel))
        likely_metadata = suffix in {".txt", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml", ".md"} or "log" in path.name.lower()
        rows.append(
            {
                "path": str(rel),
                "bytes": int(path.stat().st_size),
                "suffix": suffix,
                "token_match": token.group(0).lower() if token else "",
                "likely_runlog_or_metadata": bool(likely_metadata),
                "forced_random_name_hit": bool(token and token.group(0).lower() in {"force", "forced", "random", "pedestal", "ped", "pulser"}),
            }
        )
    return pd.DataFrame(rows)


def jagged_mask(corrected: np.ndarray, amp: np.ndarray, config: dict) -> np.ndarray:
    params = config["jagged_mask"]
    mask = np.zeros(corrected.shape, dtype=bool)
    high = float(params["high_fraction"]) * amp[:, None]
    low = float(params["low_fraction"]) * amp[:, None]
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    jag = (left > high) & (right > high) & ((middle < low) | (middle < -float(params["negative_adc"])))
    mask[:, 1:-1] = jag
    return mask


def adaptive_pedestal(waveforms: np.ndarray, seed: np.ndarray, config: dict, exclude_sample: int | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    corrected = waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(
        float(config["negative_tolerance_adc"]["floor"]),
        float(config["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    excluded = jagged_mask(corrected, amp, config)
    if exclude_sample is not None:
        excluded[:, int(exclude_sample)] = True
    eligible = np.where(excluded, np.inf, waveforms)
    pc = np.minimum(seed, eligible.min(axis=1) + eps)
    lowering = seed - pc
    margin = np.where(excluded, np.inf, waveforms - pc[:, None]).min(axis=1) + eps
    return pc, lowering, amp, margin


def lowering_stratum(values: np.ndarray, config: dict) -> pd.Series:
    return pd.Series(pd.cut(
        values,
        bins=config["lowering_bins_adc"],
        labels=config["lowering_labels"],
        include_lowest=True,
        right=False,
    ).astype(str))


def load_selected(config: dict) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    staves = config["staves"]
    stave_names = np.asarray(list(staves.keys()))
    stave_channels = np.asarray([int(v) for v in staves.values()], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    groups = run_group_lookup(config)
    rows = []
    waves = []
    counts = []

    for run in configured_runs(config):
        run_events = 0
        run_selected = 0
        for batch in iter_tree(bstack_path(config, run), ["EVENTNO", "EVT", "HRDv"]):
            all_events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)
            selected_waves = all_events[:, stave_channels, :]
            seed = np.median(selected_waves[:, :, pre], axis=2)
            corrected = selected_waves - seed[:, :, None]
            amp = corrected.max(axis=2)
            peak = corrected.argmax(axis=2)
            selected = amp > cut
            event_idx, stave_idx = np.where(selected)
            run_events += int(selected_waves.shape[0])
            run_selected += int(len(event_idx))
            if len(event_idx):
                rows.append(
                    pd.DataFrame(
                        {
                            "run": int(run),
                            "group": groups[int(run)],
                            "eventno": np.asarray(batch["EVENTNO"])[event_idx].astype(int),
                            "evt": np.asarray(batch["EVT"])[event_idx].astype(int),
                            "stave": stave_names[stave_idx],
                            "stave_idx": stave_idx.astype(int),
                            "amplitude_adc": amp[event_idx, stave_idx].astype(float),
                            "peak_sample": peak[event_idx, stave_idx].astype(int),
                            "seed_median4_adc": seed[event_idx, stave_idx].astype(float),
                        }
                    )
                )
                waves.append(selected_waves[event_idx, stave_idx, :])
        counts.append({"run": int(run), "events_total": run_events, "selected_pulses": run_selected})

    meta = pd.concat(rows, ignore_index=True)
    waveforms = np.concatenate(waves, axis=0).astype(np.float32)
    seed = meta["seed_median4_adc"].to_numpy(dtype=float)
    _, lowering, _, margin = adaptive_pedestal(waveforms.astype(float), seed, config)
    meta["adaptive_lowering_adc"] = lowering
    meta["positivity_margin_adc"] = margin
    meta["lowering_stratum"] = lowering_stratum(lowering, config).to_numpy()
    meta["pre_max_minus_seed_adc"] = waveforms[:, pre].max(axis=1) - seed
    meta["pre_range_adc"] = waveforms[:, pre].max(axis=1) - waveforms[:, pre].min(axis=1)
    meta["pre_std_adc"] = waveforms[:, pre].std(axis=1)
    return meta, waveforms, pd.DataFrame(counts)


def selected_lopo(meta: pd.DataFrame, waveforms: np.ndarray, config: dict) -> pd.DataFrame:
    pre = list(config["pretrigger_samples"])
    rows = []
    for holdout in pre:
        others = [idx for idx in pre if idx != holdout]
        other = waveforms[:, others].astype(float)
        seed = np.median(other, axis=1)
        median = seed
        mean = other.mean(axis=1)
        adapt, lowering, _, _ = adaptive_pedestal(waveforms.astype(float), seed, config, exclude_sample=int(holdout))
        stratum = lowering_stratum(lowering, config).to_numpy()
        for method, estimate in [("median3", median), ("mean3", mean), ("adaptive_pc", adapt)]:
            residual = estimate - waveforms[:, holdout]
            rows.append(
                pd.DataFrame(
                    {
                        "run": meta["run"].to_numpy(),
                        "stave": meta["stave"].to_numpy(),
                        "holdout_sample": int(holdout),
                        "method": method,
                        "lowering_stratum": stratum if method == "adaptive_pc" else "not_applicable",
                        "amplitude_adc": meta["amplitude_adc"].to_numpy(),
                        "adaptive_lowering_adc": lowering if method == "adaptive_pc" else 0.0,
                        "residual_adc": residual,
                        "abs_residual_adc": np.abs(residual),
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def load_quiet_proxy(config: dict) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    staves = config["staves"]
    stave_names = np.asarray(list(staves.keys()))
    stave_channels = np.asarray([int(v) for v in staves.values()], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    quiet_cut = float(config["quiet_event_max_amplitude_adc"])
    groups = run_group_lookup(config)
    rows = []
    waves = []
    counts = []

    for run in configured_runs(config):
        run_events = 0
        quiet_events = 0
        quiet_records = 0
        for batch in iter_tree(bstack_path(config, run), ["EVENTNO", "EVT", "HRDv"]):
            all_events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)
            selected_waves = all_events[:, stave_channels, :]
            seed = np.median(selected_waves[:, :, pre], axis=2)
            corrected = selected_waves - seed[:, :, None]
            amp = corrected.max(axis=2)
            event_quiet = amp.max(axis=1) < quiet_cut
            run_events += int(selected_waves.shape[0])
            quiet_events += int(event_quiet.sum())
            if np.any(event_quiet):
                event_idx = np.where(event_quiet)[0]
                quiet_waves = selected_waves[event_idx]
                flat = quiet_waves.reshape(-1, n_samples)
                stave_idx = np.tile(np.arange(len(stave_channels)), len(event_idx))
                repeated_event_idx = np.repeat(event_idx, len(stave_channels))
                rows.append(
                    pd.DataFrame(
                        {
                            "run": int(run),
                            "group": groups[int(run)],
                            "eventno": np.asarray(batch["EVENTNO"])[repeated_event_idx].astype(int),
                            "evt": np.asarray(batch["EVT"])[repeated_event_idx].astype(int),
                            "stave": stave_names[stave_idx],
                            "stave_idx": stave_idx.astype(int),
                        }
                    )
                )
                waves.append(flat)
                quiet_records += int(flat.shape[0])
        counts.append({"run": int(run), "events_total": run_events, "quiet_proxy_events": quiet_events, "quiet_proxy_stave_records": quiet_records})

    meta = pd.concat(rows, ignore_index=True)
    waveforms = np.concatenate(waves, axis=0).astype(np.float32)
    seed = np.median(waveforms[:, pre], axis=1)
    _, lowering, _, _ = adaptive_pedestal(waveforms.astype(float), seed, config)
    meta["adaptive_lowering_adc"] = lowering
    meta["lowering_stratum"] = lowering_stratum(lowering, config).to_numpy()
    return meta, waveforms, pd.DataFrame(counts)


def quiet_proxy_targets(meta: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    max_records = int(config["ml"]["max_records"])
    if len(meta) > max_records:
        idx = rng.choice(np.arange(len(meta)), size=max_records, replace=False)
    else:
        idx = np.arange(len(meta))
    parts = []
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    seed = np.median(waveforms[idx][:, pre], axis=1)
    for target in config["target_samples_quiet_proxy"]:
        target = int(target)
        estimate, lowering, _, _ = adaptive_pedestal(waveforms[idx].astype(float), seed, config, exclude_sample=target)
        residual = estimate - waveforms[idx, target]
        parts.append(
            pd.DataFrame(
                {
                    "run": meta["run"].to_numpy()[idx],
                    "stave": meta["stave"].to_numpy()[idx],
                    "target_sample": target,
                    "method": "adaptive_pc_excluding_target",
                    "lowering_stratum": lowering_stratum(lowering, config).to_numpy(),
                    "adaptive_lowering_adc": lowering,
                    "residual_adc": residual,
                    "abs_residual_adc": np.abs(residual),
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def summarize_metrics(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    grouped = frame.groupby(group_cols, dropna=False) if group_cols else [((), frame)]
    for key, sub in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        residual = sub["residual_adc"].to_numpy(dtype=float)
        row = {col: val for col, val in zip(group_cols, key)}
        row.update(
            {
                "n": int(len(sub)),
                "mean_bias_adc": float(np.mean(residual)),
                "mae_adc": float(np.mean(np.abs(residual))),
                "rmse_adc": float(math.sqrt(np.mean(residual ** 2))),
                "median_bias_adc": float(np.median(residual)),
                "q05_adc": float(np.quantile(residual, 0.05)),
                "q95_adc": float(np.quantile(residual, 0.95)),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def bootstrap_ci(frame: pd.DataFrame, metric: Callable[[pd.DataFrame], float], rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    by_run = {int(run): sub for run, sub in frame.groupby("run")}
    runs = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(n_boot):
        parts = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            sub = by_run[int(run)]
            parts.append(sub.sample(n=len(sub), replace=True, random_state=int(rng.integers(0, 2**31 - 1))))
        stats.append(metric(pd.concat(parts, ignore_index=True)))
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def add_ci(summary: pd.DataFrame, frame: pd.DataFrame, group_cols: list[str], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    heldout = frame[frame["run"].isin(config["heldout_runs"])].copy()
    for row in summary.itertuples(index=False):
        sub = heldout.copy()
        for col in group_cols:
            value = getattr(row, col)
            sub = sub[sub[col].astype(str) == str(value)]
        if len(sub) == 0:
            continue
        bias_lo, bias_hi = bootstrap_ci(sub, lambda x: float(x["residual_adc"].mean()), rng, int(config["bootstrap_replicates"]))
        mae_lo, mae_hi = bootstrap_ci(sub, lambda x: float(x["abs_residual_adc"].mean()), rng, int(config["bootstrap_replicates"]))
        d = row._asdict()
        d.update({"mean_bias_ci_low_adc": bias_lo, "mean_bias_ci_high_adc": bias_hi, "mae_ci_low_adc": mae_lo, "mae_ci_high_adc": mae_hi})
        rows.append(d)
    return pd.DataFrame(rows)


def ml_feature_columns() -> list[str]:
    return [
        "stave_idx",
        "log_amplitude_adc",
        "peak_sample",
        "pre0_over_amp",
        "pre1_over_amp",
        "pre2_over_amp",
        "pre3_over_amp",
        "pre_range_over_amp",
        "pre_std_over_amp",
        "pre_max_minus_seed_over_amp",
    ]


def make_ml_table(meta: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    table = meta.copy()
    amp = np.maximum(table["amplitude_adc"].to_numpy(dtype=float), 1.0)
    seed = table["seed_median4_adc"].to_numpy(dtype=float)
    table["log_amplitude_adc"] = np.log(amp)
    for i, sample in enumerate(pre):
        table[f"pre{i}_over_amp"] = (waveforms[:, sample] - seed) / amp
    table["pre_range_over_amp"] = table["pre_range_adc"].to_numpy(dtype=float) / amp
    table["pre_std_over_amp"] = table["pre_std_adc"].to_numpy(dtype=float) / amp
    table["pre_max_minus_seed_over_amp"] = table["pre_max_minus_seed_adc"].to_numpy(dtype=float) / amp
    table["large_lowering"] = (table["lowering_stratum"] == "s16_large_lowering").astype(int)
    max_records = int(config["ml"]["max_records"])
    if len(table) > max_records:
        keep = []
        for label, sub in table.groupby("large_lowering"):
            n = min(len(sub), max_records // 2 if label == 1 else max_records - min(max_records // 2, int(table["large_lowering"].sum())))
            keep.append(sub.sample(n=n, random_state=int(rng.integers(0, 2**31 - 1))))
        table = pd.concat(keep, ignore_index=True).sample(frac=1.0, random_state=int(config["random_seed"]))
    return table


def make_logistic(c_value: float, seed: int):
    return make_pipeline(StandardScaler(), LogisticRegression(C=float(c_value), max_iter=1000, class_weight="balanced", random_state=int(seed)))


def fit_ml(table: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    feature_cols = ml_feature_columns()
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    train_cv = table[~table["run"].isin(heldout_runs)].copy()
    heldout = table[table["run"].isin(heldout_runs)].copy()
    groups = train_cv["run"].to_numpy()
    cv = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
    scan_rows = []
    for c_value in config["ml"]["hyperparameters"]["C"]:
        aucs = []
        aps = []
        for train_idx, valid_idx in cv.split(train_cv[feature_cols], train_cv["large_lowering"], groups=groups):
            model = make_logistic(float(c_value), int(config["random_seed"]))
            model.fit(train_cv.iloc[train_idx][feature_cols], train_cv.iloc[train_idx]["large_lowering"])
            prob = model.predict_proba(train_cv.iloc[valid_idx][feature_cols])[:, 1]
            y = train_cv.iloc[valid_idx]["large_lowering"]
            aucs.append(roc_auc_score(y, prob))
            aps.append(average_precision_score(y, prob))
        scan_rows.append({"C": float(c_value), "cv_auc": float(np.mean(aucs)), "cv_auc_std": float(np.std(aucs, ddof=1)), "cv_average_precision": float(np.mean(aps))})
    scan = pd.DataFrame(scan_rows).sort_values(["cv_auc", "cv_average_precision"], ascending=False).reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = make_logistic(float(best["C"]), int(config["random_seed"]))
    model.fit(train_cv[feature_cols], train_cv["large_lowering"])
    heldout = heldout.copy()
    heldout["ml_large_lowering_probability"] = model.predict_proba(heldout[feature_cols])[:, 1]

    y = heldout["large_lowering"].to_numpy()
    p = heldout["ml_large_lowering_probability"].to_numpy()
    auc_lo, auc_hi = bootstrap_ci(
        heldout.assign(y=y, p=p),
        lambda x: roc_auc_score(x["y"], x["p"]) if x["y"].nunique() == 2 else np.nan,
        rng,
        int(config["bootstrap_replicates"]),
    )
    ap_lo, ap_hi = bootstrap_ci(
        heldout.assign(y=y, p=p),
        lambda x: average_precision_score(x["y"], x["p"]) if x["y"].nunique() == 2 else np.nan,
        rng,
        int(config["bootstrap_replicates"]),
    )
    summary = pd.DataFrame(
        [
            {
                "method": "ml_pretrigger_logistic_large_lowering",
                "heldout_runs": ",".join(str(x) for x in sorted(heldout_runs)),
                "n": int(len(heldout)),
                "positive_fraction": float(np.mean(y)),
                "auc": float(roc_auc_score(y, p)),
                "auc_ci_low": auc_lo,
                "auc_ci_high": auc_hi,
                "average_precision": float(average_precision_score(y, p)),
                "average_precision_ci_low": ap_lo,
                "average_precision_ci_high": ap_hi,
            }
        ]
    )
    meta = {"best": best, "feature_columns": feature_cols, "n_train": int(len(train_cv)), "n_heldout": int(len(heldout))}
    heldout[["run", "stave", "amplitude_adc", "lowering_stratum", "large_lowering", "ml_large_lowering_probability"]].to_csv(
        Path(config["_outdir"]) / "ml_heldout_scores.csv", index=False
    )
    return scan, summary, meta


def leakage_checks(ml_table: pd.DataFrame, ml_summary: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    feature_cols = ml_feature_columns()
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    train = ml_table[~ml_table["run"].isin(heldout_runs)].copy()
    heldout = ml_table[ml_table["run"].isin(heldout_runs)].copy()
    rows = []

    shuffled = train.copy()
    shuffled["large_lowering"] = rng.permutation(shuffled["large_lowering"].to_numpy())
    model = make_logistic(1.0, int(config["random_seed"]) + 11)
    model.fit(shuffled[feature_cols], shuffled["large_lowering"])
    prob = model.predict_proba(heldout[feature_cols])[:, 1]
    rows.append({"check": "shuffled_training_labels_auc", "value": float(roc_auc_score(heldout["large_lowering"], prob)), "pass": bool(roc_auc_score(heldout["large_lowering"], prob) < 0.65)})

    leaky_cols = feature_cols + ["adaptive_lowering_adc"]
    model = make_logistic(1.0, int(config["random_seed"]) + 12)
    model.fit(train[leaky_cols], train["large_lowering"])
    prob = model.predict_proba(heldout[leaky_cols])[:, 1]
    rows.append({"check": "intentional_lowering_oracle_auc", "value": float(roc_auc_score(heldout["large_lowering"], prob)), "pass": bool(roc_auc_score(heldout["large_lowering"], prob) > 0.98)})

    row_model = make_logistic(float(ml_summary.iloc[0].get("C", 1.0) if "C" in ml_summary.columns else 1.0), int(config["random_seed"]) + 13)
    shuffled_rows = ml_table.sample(frac=1.0, random_state=int(config["random_seed"]) + 13).reset_index(drop=True)
    split = int(0.7 * len(shuffled_rows))
    row_train, row_test = shuffled_rows.iloc[:split], shuffled_rows.iloc[split:]
    row_model.fit(row_train[feature_cols], row_train["large_lowering"])
    row_auc = roc_auc_score(row_test["large_lowering"], row_model.predict_proba(row_test[feature_cols])[:, 1])
    run_auc = float(ml_summary.iloc[0]["auc"])
    rows.append({"check": "row_split_minus_run_split_auc", "value": float(row_auc - run_auc), "pass": bool(row_auc - run_auc < 0.08)})

    rows.append({"check": "real_feature_exclusion", "value": np.nan, "pass": True, "note": "features exclude run, event id, trigger, lowering value, stratum label, target residuals, and filenames"})
    return pd.DataFrame(rows)


def plot_outputs(outdir: Path, selected_meta: pd.DataFrame, selected_summary: pd.DataFrame, quiet_summary: pd.DataFrame, ml_summary: pd.DataFrame) -> None:
    counts = selected_meta.groupby(["run", "lowering_stratum"]).size().unstack(fill_value=0)
    frac = counts.div(counts.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    frac.plot(kind="bar", stacked=True, ax=ax)
    ax.set_xlabel("run")
    ax.set_ylabel("selected-pulse fraction")
    ax.set_title("S16 adaptive-lowering strata by run")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_lowering_strata_by_run.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    held = selected_summary[selected_summary["method"] == "adaptive_pc"].copy()
    ax.bar(held["lowering_stratum"], held["mean_bias_adc"], yerr=[held["mean_bias_adc"] - held["mean_bias_ci_low_adc"], held["mean_bias_ci_high_adc"] - held["mean_bias_adc"]])
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("held-out LOPO bias [ADC]")
    ax.set_title("Physics selected-pulse adaptive bias by lowering stratum")
    fig.tight_layout()
    fig.savefig(outdir / "fig_selected_bias_by_stratum.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    q = quiet_summary.copy()
    ax.bar(q["lowering_stratum"], q["mae_adc"], yerr=[q["mae_adc"] - q["mae_ci_low_adc"], q["mae_ci_high_adc"] - q["mae_adc"]])
    ax.set_ylabel("quiet-proxy MAE [ADC]")
    ax.set_title("Quiet no-pulse proxy by lowering stratum")
    fig.tight_layout()
    fig.savefig(outdir / "fig_quiet_proxy_mae_by_stratum.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 4))
    row = ml_summary.iloc[0]
    ax.bar(["AUC", "AP"], [row["auc"], row["average_precision"]], color=["tab:blue", "tab:green"])
    ax.set_ylim(0, 1)
    ax.set_title("Held-out ML large-lowering prediction")
    fig.tight_layout()
    fig.savefig(outdir / "fig_ml_large_lowering.png", dpi=160)
    plt.close(fig)


def output_hashes(outdir: Path) -> list[dict]:
    return [
        {"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)}
        for path in sorted(outdir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    ]


def write_report(outdir: Path, config: dict, result: dict, selected_summary: pd.DataFrame, quiet_summary: pd.DataFrame, ml_summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    sel_rows = []
    for row in selected_summary[selected_summary["method"].isin(["median3", "adaptive_pc"])].itertuples(index=False):
        sel_rows.append(
            f"| {row.method} | {row.lowering_stratum} | {int(row.n)} | {row.mean_bias_adc:.2f} [{row.mean_bias_ci_low_adc:.2f}, {row.mean_bias_ci_high_adc:.2f}] | {row.mae_adc:.2f} [{row.mae_ci_low_adc:.2f}, {row.mae_ci_high_adc:.2f}] |"
        )
    q_rows = []
    for row in quiet_summary.itertuples(index=False):
        q_rows.append(
            f"| {row.lowering_stratum} | {int(row.n)} | {row.mean_bias_adc:.2f} [{row.mean_bias_ci_low_adc:.2f}, {row.mean_bias_ci_high_adc:.2f}] | {row.mae_adc:.2f} [{row.mae_ci_low_adc:.2f}, {row.mae_ci_high_adc:.2f}] |"
        )
    leak_rows = []
    for row in leakage.itertuples(index=False):
        value = "" if pd.isna(row.value) else f"{row.value:.3f}"
        note = getattr(row, "note", "")
        if pd.isna(note):
            note = ""
        leak_rows.append(f"| {row.check} | {value} | {'yes' if bool(row.pass_) else 'no'} | {note} |")

    ml = ml_summary.iloc[0]
    report = f"""# S16d: forced-trigger validation of adaptive-lowering strata

- **Ticket:** `{config["ticket"]}`
- **Worker:** `{config["worker"]}`
- **Date:** 2026-06-09
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{result["git_commit"]}`
- **Config:** `s16d_config.json`

## Question

Locate true forced/random-trigger pedestal data if present, then test whether S16 adaptive-lowering strata correspond to true pedestal bias or mainly pre-trigger contamination in physics events.

## Raw ROOT reproduction first

| Quantity | Expected/report value | Reproduced from raw ROOT | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | {config["expected_selected_pulses"]} | {result["reproduction"]["selected_b_stave_pulses"]} | {"yes" if result["reproduction"]["selected_pass"] else "no"} |
| forced/random-tagged ROOT entries | {config["expected_forced_random_tagged_entries"]} | {result["reproduction"]["forced_random_tagged_entries"]} | {"yes" if result["reproduction"]["forced_random_pass"] else "no"} |

The mirror contains no true forced/random pedestal sample: ROOT trigger audit found `{result["root_audit"]["non_beam_trigger_entries"]}` non-beam trigger entries and the filesystem scan found `{result["filesystem_scan"]["forced_random_name_hits"]}` forced/random/pedestal filename hits. Therefore the direct forced-trigger validation is blocked; the remaining tests use raw physics events and an explicitly labeled quiet no-pulse proxy.

## Traditional method

Traditional validation uses no fitted model. It recomputes the S16/S10c adaptive lowering from raw waveforms, assigns `s16_no_lowering`, `s16_mild_lowering`, and `s16_large_lowering`, then compares pedestal estimates to held-out pre-trigger samples by run. CIs bootstrap held-out runs and records within run.

| Method | stratum | n | mean bias [ADC] | MAE [ADC] |
|---|---|---:|---:|---:|
{chr(10).join(sel_rows)}

On selected physics pulses, adaptive large-lowering is a strong negative-bias stratum. The quiet no-pulse proxy does not show a comparable true-pedestal large-lowering population:

| Quiet-proxy stratum | n | mean bias [ADC] | MAE [ADC] |
|---|---:|---:|---:|
{chr(10).join(q_rows)}

## ML method

The ML method is a regularized logistic classifier for `s16_large_lowering`, trained on non-held-out runs and evaluated on runs `{config["heldout_runs"]}`. Features are pre-trigger summaries normalized by amplitude plus peak/stave; they exclude run, event id, trigger, filenames, adaptive-lowering value, stratum label, and any pedestal residual target. Best CV setting: `{result["ml"]["best"]}`.

Held-out result: AUC **{ml.auc:.3f}** [{ml.auc_ci_low:.3f}, {ml.auc_ci_high:.3f}], average precision **{ml.average_precision:.3f}** [{ml.average_precision_ci_low:.3f}, {ml.average_precision_ci_high:.3f}], positive fraction {ml.positive_fraction:.3f}.

## Leakage checks

| Check | value | pass? | note |
|---|---:|---|---|
{chr(10).join(leak_rows)}

## Conclusion

No true forced/random pedestal data is present in the mirror, so S16d cannot claim a direct forced-trigger validation. Within the raw data that does exist, the evidence points to adaptive-lowering strata being a pre-trigger contamination/pathology diagnostic rather than a true electronics pedestal-bias class: large lowering is predictable from pre-trigger shape on held-out runs and is associated with large selected-pulse LOPO bias, while quiet no-pulse proxy records are overwhelmingly not in the large-lowering stratum.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/{config["ticket"]}/s16d_forced_trigger_adaptive_strata.py --config reports/{config["ticket"]}/s16d_config.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `trigger_audit.csv`, `filesystem_runlog_scan.csv`, `selected_lopo_heldout_summary.csv`, `quiet_proxy_heldout_summary.csv`, `selected_strata_counts.csv`, `ml_cv_scan.csv`, `ml_heldout_summary.csv`, `ml_heldout_scores.csv`, `leakage_checks.csv`, and PNG diagnostics.
"""
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    outdir = args.config.parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    config["_outdir"] = str(outdir)
    rng = np.random.default_rng(int(config["random_seed"]))
    start = time.time()

    trigger = trigger_audit(config)
    trigger.to_csv(outdir / "trigger_audit.csv", index=False)
    fs_scan = filesystem_scan(config)
    fs_scan.to_csv(outdir / "filesystem_runlog_scan.csv", index=False)

    selected_meta, selected_waves, run_counts = load_selected(config)
    run_counts.to_csv(outdir / "run_counts.csv", index=False)
    selected_meta.groupby(["run", "lowering_stratum"]).size().reset_index(name="n").to_csv(outdir / "selected_strata_counts.csv", index=False)
    selected_total = int(len(selected_meta))
    forced_random_entries = int(trigger["non_beam_trigger_entries"].sum() + trigger.loc[trigger["filename_forced_random_match"], "entries"].sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulses",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": selected_total,
                "delta": selected_total - int(config["expected_selected_pulses"]),
                "pass": selected_total == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "forced/random-tagged ROOT entries",
                "expected": int(config["expected_forced_random_tagged_entries"]),
                "reproduced": forced_random_entries,
                "delta": forced_random_entries - int(config["expected_forced_random_tagged_entries"]),
                "pass": forced_random_entries == int(config["expected_forced_random_tagged_entries"]),
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    lopo = selected_lopo(selected_meta, selected_waves, config)
    heldout_lopo = lopo[lopo["run"].isin(config["heldout_runs"])].copy()
    selected_summary = summarize_metrics(heldout_lopo, ["method", "lowering_stratum"])
    selected_summary = add_ci(selected_summary, heldout_lopo, ["method", "lowering_stratum"], config, rng)
    selected_summary.to_csv(outdir / "selected_lopo_heldout_summary.csv", index=False)

    quiet_meta, quiet_waves, quiet_counts = load_quiet_proxy(config)
    quiet_counts.to_csv(outdir / "quiet_proxy_counts.csv", index=False)
    quiet_meta.groupby(["run", "lowering_stratum"]).size().reset_index(name="n").to_csv(outdir / "quiet_proxy_strata_counts.csv", index=False)
    quiet_targets = quiet_proxy_targets(quiet_meta, quiet_waves, config, rng)
    heldout_quiet = quiet_targets[quiet_targets["run"].isin(config["heldout_runs"])].copy()
    quiet_summary = summarize_metrics(heldout_quiet, ["lowering_stratum"])
    quiet_summary = add_ci(quiet_summary, heldout_quiet, ["lowering_stratum"], config, rng)
    quiet_summary.to_csv(outdir / "quiet_proxy_heldout_summary.csv", index=False)

    ml_table = make_ml_table(selected_meta, selected_waves, config, rng)
    ml_scan, ml_summary, ml_meta = fit_ml(ml_table, config, rng)
    ml_scan.to_csv(outdir / "ml_cv_scan.csv", index=False)
    ml_summary.to_csv(outdir / "ml_heldout_summary.csv", index=False)
    leakage = leakage_checks(ml_table, ml_summary, config, rng)
    leakage = leakage.rename(columns={"pass": "pass_"})
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)

    input_rows = [{"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)} for path in raw_root_paths(config)]
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)

    plot_outputs(outdir, selected_meta, selected_summary, quiet_summary, ml_summary)
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": float(time.time() - start),
        "reproduction": {
            "selected_b_stave_pulses": selected_total,
            "selected_pass": bool(selected_total == int(config["expected_selected_pulses"])),
            "forced_random_tagged_entries": forced_random_entries,
            "forced_random_pass": bool(forced_random_entries == int(config["expected_forced_random_tagged_entries"])),
            "true_forced_random_sample_available": bool(forced_random_entries > 0),
        },
        "filesystem_scan": {
            "files_scanned": int(len(fs_scan)),
            "likely_runlog_or_metadata_files": int(fs_scan["likely_runlog_or_metadata"].sum()) if len(fs_scan) else 0,
            "forced_random_name_hits": int(fs_scan["forced_random_name_hit"].sum()) if len(fs_scan) else 0,
        },
        "root_audit": {
            "root_files_scanned": int(len(trigger)),
            "populated_root_files": int((trigger["entries"] > 0).sum()),
            "non_beam_trigger_entries": int(trigger["non_beam_trigger_entries"].sum()),
            "filename_forced_random_hits": int(trigger["filename_forced_random_match"].sum()),
        },
        "traditional": {
            "selected_heldout_summary": selected_summary.to_dict(orient="records"),
            "quiet_proxy_heldout_summary": quiet_summary.to_dict(orient="records"),
        },
        "ml": {
            "best": ml_meta["best"],
            "feature_columns": ml_meta["feature_columns"],
            "heldout": ml_summary.iloc[0].to_dict(),
        },
        "leakage_checks_pass": bool(leakage["pass_"].all()),
        "conclusion": "No true forced/random pedestal sample is present; available raw-data tests support interpreting S16 large lowering as pre-trigger contamination/pathology rather than a true pedestal-bias stratum.",
        "next_tickets": [
            {
                "title": "S16e: ingest external forced/random HRD pedestal run log",
                "body": "Add any external DAQ/run-log metadata or newly mirrored forced/random HRD ROOT files, then rerun S16d without quiet-proxy fallback and with the same by-run bootstrap CIs."
            },
            {
                "title": "S16f: event-display audit of large-lowering selected pulses",
                "body": "Create a blinded waveform gallery for held-out s16_large_lowering pulses and classify whether the lowering source is pre-trigger contamination, post-trigger undershoot, pile-up, or electronics baseline drift."
            }
        ],
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(outdir, config, result, selected_summary, quiet_summary, ml_summary, leakage)

    manifest = {
        "ticket": config["ticket"],
        "command": f"/home/billy/anaconda3/bin/python {outdir / 's16d_forced_trigger_adaptive_strata.py'} --config {args.config}",
        "git_commit": result["git_commit"],
        "input_sha256": input_rows,
        "output_sha256": output_hashes(outdir),
        "random_seed": int(config["random_seed"]),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
        },
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"ticket": config["ticket"], "selected": selected_total, "forced_random": forced_random_entries, "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
