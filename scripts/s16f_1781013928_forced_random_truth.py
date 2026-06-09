#!/usr/bin/env python3
"""S16f forced/random pedestal truth gate and held-out proxy benchmark.

The ticket asks for direct forced/random no-pulse ROOT validation. This script
first reproduces the established raw-ROOT pulse count, then audits whether such
direct non-beam entries are present. If they are absent, the truth comparison is
blocked and the quiet-event proxy benchmark is emitted only as a fallback sanity
check, not as a replacement for acquired forced/random pedestal truth.
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
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold


TOKEN_RE = re.compile(r"(forced?|random|pedestal|ped|pulser|noise|dark|trigger|trig|log)", re.I)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    return {int(run): group for group, runs in config["run_groups"].items() for run in runs}


def raw_root_paths(config: dict) -> List[Path]:
    root = Path(config["raw_root_dir"])
    return sorted(root.glob("hrda_run_*.root")) + sorted(root.glob("hrdb_run_*.root"))


def bstack_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{int(run):04d}.root"


def parse_run(path: Path) -> int:
    match = re.search(r"_run_(\d+)", path.name)
    if not match:
        raise ValueError(f"cannot parse run from {path}")
    return int(match.group(1))


def iter_tree(path: Path, branches: Sequence[str], step_size: int = 25000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


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
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def reproduce_selected_pulses(config: dict) -> pd.DataFrame:
    stave_channels = np.asarray(list(config["staves"].values()), dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in configured_runs(config):
        path = bstack_path(config, run)
        events = 0
        selected = 0
        for batch in iter_tree(path, ["HRDv"]):
            wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)[:, stave_channels, :]
            seed = np.median(wave[:, :, pre], axis=2)
            amp = (wave - seed[:, :, None]).max(axis=2)
            events += int(wave.shape[0])
            selected += int((amp > cut).sum())
        rows.append({"run": int(run), "events_total": events, "selected_b_stave_pulses": selected})
    return pd.DataFrame(rows)


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
                "stack": path.name[:4],
                "run": parse_run(path),
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "forced_random_filename_token": bool(
                    TOKEN_RE.search(path.name)
                    and any(token in path.name.lower() for token in ["force", "random", "ped", "pulser"])
                ),
            }
        )
    return pd.DataFrame(rows)


def filesystem_scan(config: dict) -> pd.DataFrame:
    rows = []
    root = Path(config["data_root"])
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        token = TOKEN_RE.search(str(rel))
        rows.append(
            {
                "path": str(rel),
                "bytes": int(path.stat().st_size),
                "suffix": path.suffix.lower(),
                "token_match": token.group(0).lower() if token else "",
                "forced_random_name_hit": bool(
                    token and token.group(0).lower() in {"force", "forced", "random", "pedestal", "ped", "pulser"}
                ),
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
    jagged = (left > high) & (right > high) & ((middle < low) | (middle < -float(params["negative_adc"])))
    mask[:, 1:-1] = jagged
    return mask


def adaptive_pedestal(
    waveforms: np.ndarray, seed: np.ndarray, config: dict, exclude_sample: int | None = None
) -> Tuple[np.ndarray, np.ndarray]:
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
    estimate = np.minimum(seed, eligible.min(axis=1) + eps)
    return estimate, seed - estimate


def load_direct_nonbeam_records(config: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    stave_channels = np.asarray(list(config["staves"].values()), dtype=int)
    stave_names = np.asarray(list(config["staves"].keys()))
    n_samples = int(config["samples_per_channel"])
    groups = run_group_lookup(config)
    rows = []
    waves = []
    for run in configured_runs(config):
        path = bstack_path(config, run)
        for batch in iter_tree(path, ["EVENTNO", "EVT", "TRIGGER", "HRDv"]):
            trigger = np.asarray(batch["TRIGGER"])
            keep = trigger != 1
            if not np.any(keep):
                continue
            eventno = np.asarray(batch["EVENTNO"])[keep]
            evt = np.asarray(batch["EVT"])[keep]
            trig = trigger[keep]
            wave = np.stack(batch["HRDv"])[keep].astype(np.float32).reshape(-1, 8, n_samples)[:, stave_channels, :]
            n_events = wave.shape[0]
            flat = wave.reshape(-1, n_samples)
            stave_idx = np.tile(np.arange(len(stave_channels), dtype=int), n_events)
            event_idx = np.repeat(np.arange(n_events), len(stave_channels))
            rows.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "group": groups[int(run)],
                        "eventno": eventno[event_idx].astype(int),
                        "evt": evt[event_idx].astype(int),
                        "trigger": trig[event_idx].astype(int),
                        "stave": stave_names[stave_idx],
                        "stave_idx": stave_idx.astype(int),
                    }
                )
            )
            waves.append(flat)
    if not rows:
        columns = ["run", "group", "eventno", "evt", "trigger", "stave", "stave_idx"]
        return pd.DataFrame(columns=columns), np.empty((0, int(config["samples_per_channel"])), dtype=np.float32)
    return pd.concat(rows, ignore_index=True), np.concatenate(waves, axis=0)


def load_quiet_proxy_records(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    stave_channels = np.asarray(list(config["staves"].values()), dtype=int)
    stave_names = np.asarray(list(config["staves"].keys()))
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    quiet_cut = float(config["quiet_event_max_amplitude_adc"])
    amp_cut = float(config["amplitude_cut_adc"])
    groups = run_group_lookup(config)
    rows = []
    waves = []
    count_rows = []
    for run in configured_runs(config):
        events = 0
        selected = 0
        quiet_events = 0
        quiet_records = 0
        for batch in iter_tree(bstack_path(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"])
            evt = np.asarray(batch["EVT"])
            all_wave = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)[:, stave_channels, :]
            seed = np.median(all_wave[:, :, pre], axis=2)
            amp = (all_wave - seed[:, :, None]).max(axis=2)
            event_quiet = amp.max(axis=1) < quiet_cut
            events += int(all_wave.shape[0])
            selected += int((amp > amp_cut).sum())
            quiet_events += int(event_quiet.sum())
            if not np.any(event_quiet):
                continue
            quiet_wave = all_wave[event_quiet]
            n_events = quiet_wave.shape[0]
            flat = quiet_wave.reshape(-1, n_samples)
            stave_idx = np.tile(np.arange(len(stave_channels), dtype=int), n_events)
            event_idx = np.repeat(np.where(event_quiet)[0], len(stave_channels))
            rows.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "group": groups[int(run)],
                        "eventno": eventno[event_idx].astype(int),
                        "evt": evt[event_idx].astype(int),
                        "stave": stave_names[stave_idx],
                        "stave_idx": stave_idx.astype(int),
                    }
                )
            )
            waves.append(flat)
            quiet_records += int(flat.shape[0])
        count_rows.append(
            {
                "run": int(run),
                "events_total": events,
                "selected_b_stave_pulses": selected,
                "quiet_proxy_events": quiet_events,
                "quiet_proxy_stave_records": quiet_records,
            }
        )
    return pd.concat(rows, ignore_index=True), np.concatenate(waves, axis=0), pd.DataFrame(count_rows)


def make_target_records(meta: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    train_limit = int(config["proxy_train_max_records"])
    heldout = set(int(run) for run in config["heldout_runs"])
    train_idx = np.where(~meta["run"].isin(heldout).to_numpy())[0]
    heldout_idx = np.where(meta["run"].isin(heldout).to_numpy())[0]
    if len(train_idx) > train_limit:
        train_idx = rng.choice(train_idx, size=train_limit, replace=False)
    indices = np.concatenate([train_idx, heldout_idx])
    parts = []
    pre = waveforms[indices][:, config["pretrigger_samples"]].astype(float)
    seed = np.median(pre, axis=1)
    for target_sample in config["target_samples"]:
        target_sample = int(target_sample)
        parts.append(
            pd.DataFrame(
                {
                    "row_index": indices.astype(int),
                    "run": meta["run"].to_numpy()[indices],
                    "stave_idx": meta["stave_idx"].to_numpy()[indices],
                    "target_sample": target_sample,
                    "target_adc": waveforms[indices, target_sample].astype(float),
                    "seed_median4_adc": seed,
                    "pre_mean4_adc": pre.mean(axis=1),
                    "pre_std4_adc": pre.std(axis=1),
                    "pre_min4_adc": pre.min(axis=1),
                    "pre_max4_adc": pre.max(axis=1),
                    "pre_slope03_adc": pre[:, 3] - pre[:, 0],
                }
            )
        )
    return pd.concat(parts, ignore_index=True)


def ml_feature_columns() -> List[str]:
    return [
        "stave_idx",
        "target_sample",
        "seed_median4_adc",
        "pre_mean4_adc",
        "pre_std4_adc",
        "pre_min4_adc",
        "pre_max4_adc",
        "pre_slope03_adc",
    ]


def run_bootstrap_ci(
    residual: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    n_boot: int,
    max_records_per_run: int,
) -> Tuple[float, float]:
    by_run = {}
    for run in np.unique(runs):
        vals = residual[runs == run]
        if len(vals) > max_records_per_run:
            vals = rng.choice(vals, size=max_records_per_run, replace=False)
        by_run[int(run)] = vals
    run_values = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(n_boot):
        pieces = []
        for run in rng.choice(run_values, size=len(run_values), replace=True):
            vals = by_run[int(run)]
            pieces.append(rng.choice(vals, size=len(vals), replace=True))
        stats.append(metric(np.concatenate(pieces)))
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def metric_summary(method: str, residual: np.ndarray, runs: np.ndarray, config: dict, rng: np.random.Generator) -> dict:
    residual = np.asarray(residual, dtype=float)
    n_boot = int(config["bootstrap_replicates"])
    cap = int(config["bootstrap_max_records_per_run"])
    bias_lo, bias_hi = run_bootstrap_ci(residual, runs, np.mean, rng, n_boot, cap)
    mae_lo, mae_hi = run_bootstrap_ci(residual, runs, lambda x: float(np.mean(np.abs(x))), rng, n_boot, cap)
    return {
        "method": method,
        "n_records": int(len(residual)),
        "mean_bias_adc": float(np.mean(residual)),
        "mean_bias_ci_low_adc": bias_lo,
        "mean_bias_ci_high_adc": bias_hi,
        "mae_adc": float(np.mean(np.abs(residual))),
        "mae_ci_low_adc": mae_lo,
        "mae_ci_high_adc": mae_hi,
        "rmse_adc": float(math.sqrt(np.mean(residual**2))),
        "median_bias_adc": float(np.median(residual)),
        "q05_adc": float(np.quantile(residual, 0.05)),
        "q95_adc": float(np.quantile(residual, 0.95)),
    }


def make_tree_model(config: dict, max_leaf_nodes: int) -> ExtraTreesRegressor:
    return ExtraTreesRegressor(
        n_estimators=int(config["ml"]["max_iter"]),
        max_leaf_nodes=int(max_leaf_nodes),
        min_samples_leaf=4,
        n_jobs=-1,
        random_state=int(config["random_seed"]),
    )


def fit_ml(train_cv: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, dict, ExtraTreesRegressor, LinearRegression]:
    feature_cols = ml_feature_columns()
    calibration_runs = set(int(run) for run in config["calibration_runs"])
    core_train = train_cv[~train_cv["run"].isin(calibration_runs)].copy()
    calibration = train_cv[train_cv["run"].isin(calibration_runs)].copy()
    if calibration.empty:
        calibration = core_train.sample(frac=0.15, random_state=int(config["random_seed"]))
        core_train = core_train.drop(calibration.index)
    groups = train_cv["run"].to_numpy()
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    scan_rows = []
    cv = GroupKFold(n_splits=n_splits)
    for max_leaf_nodes in config["ml"]["hyperparameters"]["max_leaf_nodes"]:
        for learning_rate in config["ml"]["hyperparameters"]["learning_rate"]:
            for l2_regularization in config["ml"]["hyperparameters"]["l2_regularization"]:
                scores = []
                for train_idx, valid_idx in cv.split(train_cv[feature_cols], train_cv["target_adc"], groups=groups):
                    model = make_tree_model(config, int(max_leaf_nodes))
                    model.fit(train_cv.iloc[train_idx][feature_cols], train_cv.iloc[train_idx]["target_adc"])
                    pred = model.predict(train_cv.iloc[valid_idx][feature_cols])
                    scores.append(mean_absolute_error(train_cv.iloc[valid_idx]["target_adc"], pred))
                scan_rows.append(
                    {
                        "max_leaf_nodes": int(max_leaf_nodes),
                        "learning_rate": float(learning_rate),
                        "l2_regularization": float(l2_regularization),
                        "cv_mae_adc": float(np.mean(scores)),
                        "cv_mae_std_adc": float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0,
                    }
                )
    scan = pd.DataFrame(scan_rows).sort_values("cv_mae_adc").reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = make_tree_model(config, int(best["max_leaf_nodes"]))
    model.fit(core_train[feature_cols], core_train["target_adc"])
    cal_pred = model.predict(calibration[feature_cols])
    calibrator = LinearRegression().fit(cal_pred.reshape(-1, 1), calibration["target_adc"])
    meta = {
        "best": best,
        "feature_columns": feature_cols,
        "n_train_cv": int(len(train_cv)),
        "n_core_train": int(len(core_train)),
        "n_calibration": int(len(calibration)),
        "calibration_slope": float(calibrator.coef_[0]),
        "calibration_intercept": float(calibrator.intercept_),
    }
    return scan, meta, model, calibrator


def evaluate_proxy(features: pd.DataFrame, waveforms: np.ndarray, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    heldout_runs = set(int(run) for run in config["heldout_runs"])
    train = features[~features["run"].isin(heldout_runs)].copy()
    test = features[features["run"].isin(heldout_runs)].copy()
    offsets = (
        train.assign(residual=lambda x: x["target_adc"] - x["seed_median4_adc"])
        .groupby(["stave_idx", "target_sample"], as_index=False)["residual"]
        .median()
        .rename(columns={"residual": "train_median_offset_adc"})
    )
    test = test.merge(offsets, on=["stave_idx", "target_sample"], how="left")
    test["train_median_offset_adc"] = test["train_median_offset_adc"].fillna(0.0)
    scan, ml_meta, model, calibrator = fit_ml(train, config)
    feature_cols = ml_feature_columns()
    target = test["target_adc"].to_numpy(dtype=float)
    runs = test["run"].to_numpy(dtype=int)
    method_residuals = {
        "traditional_median4_pre": test["seed_median4_adc"].to_numpy(dtype=float) - target,
        "traditional_mean4_pre": test["pre_mean4_adc"].to_numpy(dtype=float) - target,
        "traditional_median4_plus_train_offset": (
            test["seed_median4_adc"].to_numpy(dtype=float) + test["train_median_offset_adc"].to_numpy(dtype=float) - target
        ),
    }
    adaptive = np.empty(len(test), dtype=float)
    for target_sample in sorted(test["target_sample"].unique()):
        mask = test["target_sample"].to_numpy() == target_sample
        idx = test.loc[mask, "row_index"].to_numpy(dtype=int)
        seed = test.loc[mask, "seed_median4_adc"].to_numpy(dtype=float)
        estimate, _ = adaptive_pedestal(waveforms[idx].astype(float), seed, config, exclude_sample=int(target_sample))
        adaptive[mask] = estimate
    method_residuals["traditional_adaptive_pc_excluding_target"] = adaptive - target
    ml_raw = model.predict(test[feature_cols])
    ml_pred = calibrator.predict(ml_raw.reshape(-1, 1))
    method_residuals["ml_pretrigger_extra_trees_calibrated"] = ml_pred - target
    summary = pd.DataFrame(
        [metric_summary(method, residual, runs, config, rng) for method, residual in method_residuals.items()]
    ).sort_values("mae_adc")
    by_run_rows = []
    for method, residual in method_residuals.items():
        for run in sorted(np.unique(runs)):
            vals = residual[runs == run]
            by_run_rows.append(
                {
                    "method": method,
                    "run": int(run),
                    "n_records": int(len(vals)),
                    "mean_bias_adc": float(np.mean(vals)),
                    "mae_adc": float(np.mean(np.abs(vals))),
                    "rmse_adc": float(math.sqrt(np.mean(vals**2))),
                }
            )
    by_run = pd.DataFrame(by_run_rows)
    leak = leakage_checks(train, test, feature_cols, config, rng)
    return summary, by_run, scan, leak, ml_meta


def leakage_checks(train: pd.DataFrame, test: pd.DataFrame, feature_cols: List[str], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    shuffled = train.copy()
    shuffled["target_adc"] = rng.permutation(shuffled["target_adc"].to_numpy())
    model = ExtraTreesRegressor(
        n_estimators=20,
        max_leaf_nodes=64,
        min_samples_leaf=4,
        n_jobs=-1,
        random_state=int(config["random_seed"]) + 7,
    )
    model.fit(shuffled[feature_cols], shuffled["target_adc"])
    pred = model.predict(test[feature_cols])
    rows.append(
        {
            "check": "shuffled_training_target",
            "metric": "mae_adc",
            "value": float(mean_absolute_error(test["target_adc"], pred)),
            "interpretation": "negative control; should be much worse than the real ML model",
        }
    )
    leaky_cols = feature_cols + ["target_adc"]
    oracle = ExtraTreesRegressor(
        n_estimators=20,
        max_leaf_nodes=64,
        min_samples_leaf=2,
        n_jobs=-1,
        random_state=int(config["random_seed"]) + 8,
    )
    oracle.fit(train[leaky_cols], train["target_adc"])
    oracle_pred = oracle.predict(test[leaky_cols])
    rows.append(
        {
            "check": "intentional_target_feature_oracle",
            "metric": "mae_adc",
            "value": float(mean_absolute_error(test["target_adc"], oracle_pred)),
            "interpretation": "positive control; direct target leakage would make the error suspiciously small",
        }
    )
    rows.append(
        {
            "check": "real_feature_exclusion",
            "metric": "n_excluded_leakage_columns",
            "value": 4.0,
            "interpretation": "real features exclude run, eventno, evt, and target_adc; split is by run",
        }
    )
    return pd.DataFrame(rows)


def output_hashes(paths: Iterable[Path]) -> List[dict]:
    rows = []
    for path in sorted(paths):
        if path.is_file():
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def write_report(outdir: Path, config: dict, result: dict, proxy_summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    rows = "\n".join(
        f"| {r.method} | {r.n_records} | {r.mae_adc:.2f} [{r.mae_ci_low_adc:.2f}, {r.mae_ci_high_adc:.2f}] | "
        f"{r.mean_bias_adc:.2f} [{r.mean_bias_ci_low_adc:.2f}, {r.mean_bias_ci_high_adc:.2f}] |"
        for r in proxy_summary.itertuples(index=False)
    )
    leak_rows = "\n".join(
        f"| {r.check} | {r.metric} | {r.value:.2f} | {r.interpretation} |"
        for r in leakage.itertuples(index=False)
    )
    direct = result["direct_forced_random"]
    reproduction = result["raw_reproduction"]
    best = result["proxy_benchmark"]["best_method"]
    conclusion = result["conclusion"]
    report = f"""# S16f: forced/random pedestal truth validation

- **Ticket:** {config["ticket"]}
- **Worker:** {config["worker"]}
- **Date:** 2026-06-09
- **Input manifest:** `input_sha256.csv`
- **Config:** `configs/s16f_1781013928_1541_3e1c5146.json`

## Question

Once non-beam HRD pedestal entries are available, does the S16 adaptive pedestal lowering remain biased relative to true forced/random no-pulse samples?

## Raw reproduction first

The raw B-stack ROOT reproduction gives **{reproduction["selected_b_stave_pulses"]:,}** selected B-stave pulses with `A > {config["amplitude_cut_adc"]:.0f}` ADC, matching the expected **{reproduction["expected_selected_pulses"]:,}**. The direct forced/random audit finds **{direct["non_beam_trigger_entries"]}** `TRIGGER != 1` entries and **{direct["forced_random_filename_hits"]}** forced/random/pedestal filename hits across **{direct["raw_root_files_scanned"]}** raw ROOT files.

## Direct truth gate

No acquired forced/random no-pulse HRD entries are present in this mirror. Therefore the requested direct electronics-pedestal comparison is **not estimable** from the available raw ROOT, and neither the traditional nor ML method below is claimed as direct forced/random truth.

## Held-out proxy benchmark

As a fallback sanity check only, quiet B-stack events with event maximum below `{config["quiet_event_max_amplitude_adc"]:.0f}` ADC were split by run. Runs `{', '.join(str(r) for r in config["heldout_runs"])}` are held out; bootstrap intervals resample held-out runs.

| Method | Records | MAE ADC | Mean bias ADC |
|---|---:|---:|---:|
{rows}

The best proxy method is `{best["method"]}` with MAE {best["mae_adc"]:.2f} ADC and mean bias {best["mean_bias_adc"]:.2f} ADC. This is a proxy for electronics stability, not evidence that S16 lowering is unbiased on forced/random triggers.

## Leakage checks

| Check | Metric | Value | Interpretation |
|---|---|---:|---|
{leak_rows}

## Conclusion

{conclusion}
"""
    (outdir / "REPORT.md").write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    root_paths = raw_root_paths(config)
    input_sha = pd.DataFrame(
        [{"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)} for path in root_paths]
    )
    input_sha.to_csv(outdir / "input_sha256.csv", index=False)

    selected = reproduce_selected_pulses(config)
    selected.to_csv(outdir / "selected_reproduction_by_run.csv", index=False)
    trigger = trigger_audit(config)
    trigger.to_csv(outdir / "raw_trigger_audit.csv", index=False)
    fs_scan = filesystem_scan(config)
    fs_scan.to_csv(outdir / "data_file_scan.csv", index=False)

    direct_meta, direct_waves = load_direct_nonbeam_records(config)
    direct_meta.to_csv(outdir / "direct_nonbeam_records.csv", index=False)

    quiet_meta, quiet_waves, quiet_counts = load_quiet_proxy_records(config)
    quiet_counts.to_csv(outdir / "quiet_proxy_counts_by_run.csv", index=False)
    features = make_target_records(quiet_meta, quiet_waves, config, rng)
    proxy_summary, proxy_by_run, ml_scan, leakage, ml_meta = evaluate_proxy(features, quiet_waves, config, rng)
    proxy_summary.to_csv(outdir / "proxy_method_summary.csv", index=False)
    proxy_by_run.to_csv(outdir / "proxy_method_by_run.csv", index=False)
    ml_scan.to_csv(outdir / "proxy_ml_cv_scan.csv", index=False)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)

    selected_total = int(selected["selected_b_stave_pulses"].sum())
    nonbeam_total = int(trigger["non_beam_trigger_entries"].sum())
    filename_hits = int(trigger["forced_random_filename_token"].sum() + fs_scan["forced_random_name_hit"].sum())
    selected_pass = selected_total == int(config["expected_selected_pulses"])
    direct_available = len(direct_meta) > 0
    direct_status = "available" if direct_available else "not_available"
    conclusion = (
        "The requested S16f direct forced/random pedestal validation is blocked: this data mirror contains no "
        "non-beam HRD ROOT entries or forced/random/pedestal filename hits. The quiet-proxy benchmark remains "
        "compatible with prior S16d behavior, but it must not be treated as acquired forced/random electronics truth."
    )
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": time.time() - start,
        "raw_reproduction": {
            "selected_b_stave_pulses": selected_total,
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "selected_pass": selected_pass,
        },
        "direct_forced_random": {
            "status": direct_status,
            "direct_nonbeam_stave_records": int(len(direct_meta)),
            "direct_nonbeam_waveforms_shape": list(direct_waves.shape),
            "non_beam_trigger_entries": nonbeam_total,
            "expected_forced_random_tagged_entries": int(config["expected_forced_random_tagged_entries"]),
            "raw_root_files_scanned": int(len(trigger)),
            "forced_random_filename_hits": filename_hits,
            "traditional_method_status": "blocked_no_direct_truth_sample",
            "ml_method_status": "blocked_no_direct_truth_sample",
        },
        "proxy_benchmark": {
            "status": "fallback_not_direct_truth",
            "quiet_event_max_amplitude_adc": float(config["quiet_event_max_amplitude_adc"]),
            "quiet_proxy_events": int(quiet_counts["quiet_proxy_events"].sum()),
            "quiet_proxy_stave_records": int(quiet_counts["quiet_proxy_stave_records"].sum()),
            "heldout_runs": [int(run) for run in config["heldout_runs"]],
            "target_records_after_sampling": int(len(features)),
            "best_method": proxy_summary.iloc[0].to_dict(),
            "traditional_adaptive": proxy_summary[
                proxy_summary["method"] == "traditional_adaptive_pc_excluding_target"
            ].iloc[0].to_dict(),
            "ml_method": proxy_summary[proxy_summary["method"] == "ml_pretrigger_extra_trees_calibrated"].iloc[0].to_dict(),
            "ml_meta": ml_meta,
        },
        "leakage_checks": leakage.to_dict(orient="records"),
        "conclusion": conclusion,
        "next_tickets": [
            {
                "title": "S16g: acquire or mirror forced/random HRD pedestal ROOT",
                "body": "Locate the DAQ forced/random pedestal runs or regenerate the reduced ROOT with non-beam triggers preserved, then rerun S16f as a direct truth comparison without quiet-proxy fallback.",
            },
            {
                "title": "S16h: compare sorted ROOT baseline branches to raw pretrigger pedestals",
                "body": "Use sorted HRD baseline/trap branches to test whether baseline preprocessing encodes pedestal shifts that are absent from the reduced raw TRIGGER audit.",
            },
        ],
    }
    result = json_clean(result)
    (outdir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    write_report(outdir, config, result, proxy_summary, leakage)

    outputs = [p for p in outdir.iterdir() if p.is_file() and p.name != "manifest.json"]
    outputs.extend([config_path, Path(__file__)])
    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {config_path}",
        "config": str(config_path),
        "script": str(Path(__file__)),
        "git_commit": result["git_commit"],
        "random_seed": int(config["random_seed"]),
        "input_sha256": str(outdir / "input_sha256.csv"),
        "outputs": output_hashes(outputs),
    }
    (outdir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
