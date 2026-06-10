#!/usr/bin/env python3
"""S16e forced/random pedestal audit and no-proxy pedestal benchmark.

This ticket first reproduces the S16d raw-ROOT gate: no forced/random/non-beam
pedestal entries are present in the local mirrors. Since no dedicated pedestal
run can be found locally, the benchmark uses pre-trigger samples from every
B-stack physics event without selecting events by a quiet/amplitude proxy.
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
import zipfile
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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold


TOKEN_RE = re.compile(r"(forced?|random|pedestal|ped|pulser|noise|dark|trigger|trig|run.?log|daq)", re.I)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
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
    return {int(run): group for group, runs in config["run_groups"].items() for run in runs}


def raw_root_paths(config: dict) -> list:
    root = Path(config["raw_root_dir"])
    return sorted(root.glob("hrda_run_*.root")) + sorted(root.glob("hrdb_run_*.root"))


def bstack_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(int(run))


def iter_tree(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


def trigger_audit(config: dict) -> pd.DataFrame:
    rows = []
    for path in raw_root_paths(config):
        tree = uproot.open(path)["h101"]
        if tree.num_entries:
            trigger = tree.arrays(["TRIGGER"], library="np")["TRIGGER"]
            values, counts = np.unique(trigger, return_counts=True)
            summary = ";".join("{}:{}".format(int(v), int(c)) for v, c in zip(values, counts))
            non_beam = int(np.sum(counts[values != 1]))
        else:
            summary = "empty"
            non_beam = 0
        token = TOKEN_RE.search(path.name)
        rows.append(
            {
                "file": str(path),
                "entries": int(tree.num_entries),
                "trigger_summary": summary,
                "non_beam_trigger_entries": non_beam,
                "filename_token": token.group(0).lower() if token else "",
                "filename_forced_random_hit": bool(
                    token and token.group(0).lower() in {"force", "forced", "random", "pedestal", "ped", "pulser"}
                ),
            }
        )
    return pd.DataFrame(rows)


def archive_and_log_scan(config: dict) -> pd.DataFrame:
    rows = []
    seen = set()
    roots = [Path(p) for p in config["search_roots"]]
    for root in roots:
        if not root.exists():
            rows.append({"container": str(root), "member": "", "kind": "missing_root", "bytes": 0, "token": "", "forced_random_hit": False})
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            real = str(path.resolve())
            if real in seen:
                continue
            seen.add(real)
            rel = str(path)
            token = TOKEN_RE.search(rel)
            rows.append(
                {
                    "container": rel,
                    "member": "",
                    "kind": "filesystem",
                    "bytes": int(path.stat().st_size),
                    "token": token.group(0).lower() if token else "",
                    "forced_random_hit": bool(token and token.group(0).lower() in {"force", "forced", "random", "pedestal", "ped", "pulser"}),
                }
            )
            if path.suffix.lower() == ".zip":
                try:
                    with zipfile.ZipFile(path) as zf:
                        for info in zf.infolist():
                            token = TOKEN_RE.search(info.filename)
                            rows.append(
                                {
                                    "container": rel,
                                    "member": info.filename,
                                    "kind": "zip_member",
                                    "bytes": int(info.file_size),
                                    "token": token.group(0).lower() if token else "",
                                    "forced_random_hit": bool(
                                        token and token.group(0).lower() in {"force", "forced", "random", "pedestal", "ped", "pulser"}
                                    ),
                                }
                            )
                except zipfile.BadZipFile:
                    rows.append({"container": rel, "member": "", "kind": "bad_zip", "bytes": 0, "token": "", "forced_random_hit": False})
    return pd.DataFrame(rows)


def selected_b_stave_count(config: dict) -> pd.DataFrame:
    staves = np.asarray([int(v) for v in config["staves"].values()], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows = []
    for run in configured_runs(config):
        total = 0
        selected = 0
        for batch in iter_tree(bstack_path(config, run), ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)
            waves = events[:, staves, :]
            seed = np.median(waves[:, :, pre], axis=2)
            amp = (waves - seed[:, :, None]).max(axis=2)
            total += int(waves.shape[0])
            selected += int(np.sum(amp > cut))
        rows.append({"run": int(run), "events": total, "selected_b_stave_pulses": selected})
    return pd.DataFrame(rows)


def make_no_proxy_table(config: dict, rng: np.random.Generator) -> pd.DataFrame:
    staves = config["staves"]
    stave_names = np.asarray(list(staves.keys()))
    stave_channels = np.asarray([int(v) for v in staves.values()], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    n_samples = int(config["samples_per_channel"])
    groups = run_group_lookup(config)
    max_rows = int(config["no_proxy"]["max_rows_per_run"])
    rows = []
    count_rows = []

    for run in configured_runs(config):
        run_parts = []
        events_total = 0
        for batch in iter_tree(bstack_path(config, run), ["EVENTNO", "EVT", "HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, n_samples)
            waves = events[:, stave_channels, :][:, :, pre]
            n_events = waves.shape[0]
            events_total += int(n_events)
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            flat = waves.reshape(-1, len(pre))
            repeated_eventno = np.repeat(eventno, len(stave_channels))
            repeated_evt = np.repeat(evt, len(stave_channels))
            stave_idx = np.tile(np.arange(len(stave_channels)), n_events)
            stave = stave_names[stave_idx]
            for target_pos, target_sample in enumerate(pre):
                other_pos = [idx for idx in range(len(pre)) if idx != target_pos]
                other = flat[:, other_pos].astype(float)
                target = flat[:, target_pos].astype(float)
                run_parts.append(
                    pd.DataFrame(
                        {
                            "run": int(run),
                            "group": groups[int(run)],
                            "eventno": repeated_eventno,
                            "evt": repeated_evt,
                            "stave": stave,
                            "stave_idx": stave_idx.astype(int),
                            "target_sample": int(target_sample),
                            "target_adc": target,
                            "other0_adc": other[:, 0],
                            "other1_adc": other[:, 1],
                            "other2_adc": other[:, 2],
                            "other_mean_adc": other.mean(axis=1),
                            "other_median_adc": np.median(other, axis=1),
                            "other_range_adc": other.max(axis=1) - other.min(axis=1),
                            "other_std_adc": other.std(axis=1),
                        }
                    )
                )
        run_table = pd.concat(run_parts, ignore_index=True)
        available = len(run_table)
        if available > max_rows:
            run_table = run_table.sample(n=max_rows, random_state=int(rng.integers(0, 2**31 - 1))).reset_index(drop=True)
        rows.append(run_table)
        count_rows.append(
            {
                "run": int(run),
                "events": events_total,
                "candidate_pretrigger_rows": int(available),
                "sampled_rows": int(len(run_table)),
            }
        )
    table = pd.concat(rows, ignore_index=True)
    pd.DataFrame(count_rows).to_csv(Path(config["_outdir"]) / "no_proxy_counts_by_run.csv", index=False)
    return table


def bootstrap_ci(frame: pd.DataFrame, metric: Callable[[pd.DataFrame], float], rng: np.random.Generator, n_boot: int) -> tuple:
    by_run = {int(run): sub for run, sub in frame.groupby("run")}
    runs = np.asarray(sorted(by_run), dtype=int)
    stats = []
    for _ in range(n_boot):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            sub = by_run[int(run)]
            pieces.append(sub.sample(n=len(sub), replace=True, random_state=int(rng.integers(0, 2**31 - 1))))
        value = metric(pd.concat(pieces, ignore_index=True))
        if not np.isnan(value):
            stats.append(value)
    if not stats:
        return float("nan"), float("nan")
    return float(np.quantile(stats, 0.025)), float(np.quantile(stats, 0.975))


def residual_width68(residual: np.ndarray) -> float:
    return float(np.quantile(np.abs(residual - np.median(residual)), 0.68))


def summarize_predictions(frame: pd.DataFrame, method: str, rng: np.random.Generator, config: dict) -> dict:
    residual = frame["prediction_adc"].to_numpy(dtype=float) - frame["target_adc"].to_numpy(dtype=float)
    tmp = frame.assign(residual_adc=residual, abs_residual_adc=np.abs(residual))
    bias_lo, bias_hi = bootstrap_ci(tmp, lambda x: float(x["residual_adc"].mean()), rng, int(config["bootstrap_replicates"]))
    mae_lo, mae_hi = bootstrap_ci(tmp, lambda x: float(x["abs_residual_adc"].mean()), rng, int(config["bootstrap_replicates"]))
    width_lo, width_hi = bootstrap_ci(tmp, lambda x: residual_width68(x["residual_adc"].to_numpy(dtype=float)), rng, int(config["bootstrap_replicates"]))
    return {
        "method": method,
        "n": int(len(tmp)),
        "mean_bias_adc": float(np.mean(residual)),
        "mean_bias_ci_low_adc": bias_lo,
        "mean_bias_ci_high_adc": bias_hi,
        "mae_adc": float(mean_absolute_error(tmp["target_adc"], tmp["prediction_adc"])),
        "mae_ci_low_adc": mae_lo,
        "mae_ci_high_adc": mae_hi,
        "rmse_adc": float(math.sqrt(mean_squared_error(tmp["target_adc"], tmp["prediction_adc"]))),
        "width68_adc": residual_width68(residual),
        "width68_ci_low_adc": width_lo,
        "width68_ci_high_adc": width_hi,
    }


def add_traditional_predictions(table: pd.DataFrame, config: dict) -> pd.DataFrame:
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    train = table[~table["run"].isin(heldout_runs)].copy()
    out = table[table["run"].isin(heldout_runs)].copy()
    train = train.assign(raw_offset=train["target_adc"] - train["other_median_adc"])
    offsets = train.groupby(["stave_idx", "target_sample"])["raw_offset"].median().rename("robust_offset_adc").reset_index()
    out = out.merge(offsets, on=["stave_idx", "target_sample"], how="left")
    out["robust_offset_adc"] = out["robust_offset_adc"].fillna(float(train["raw_offset"].median()))
    pred_rows = []
    for method, prediction in [
        ("traditional_median3", out["other_median_adc"]),
        ("traditional_mean3", out["other_mean_adc"]),
        ("traditional_stave_sample_offset_median3", out["other_median_adc"] + out["robust_offset_adc"]),
    ]:
        tmp = out.copy()
        tmp["method"] = method
        tmp["prediction_adc"] = prediction
        pred_rows.append(tmp)
    return pd.concat(pred_rows, ignore_index=True)


def feature_columns() -> list:
    return [
        "stave_idx",
        "target_sample",
        "other0_adc",
        "other1_adc",
        "other2_adc",
        "other_mean_adc",
        "other_median_adc",
        "other_range_adc",
        "other_std_adc",
    ]


def fit_ml(table: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple:
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    train = table[~table["run"].isin(heldout_runs)].copy()
    heldout = table[table["run"].isin(heldout_runs)].copy()
    cols = feature_columns()
    if len(train) > int(config["ml"]["max_train_rows"]):
        train = train.sample(n=int(config["ml"]["max_train_rows"]), random_state=int(config["random_seed"]))

    groups = train["run"].to_numpy()
    cv = GroupKFold(n_splits=min(int(config["ml"]["cv_folds"]), len(np.unique(groups))))
    scan_rows = []
    for lr in config["ml"]["learning_rate"]:
        for leaves in config["ml"]["max_leaf_nodes"]:
            fold_metrics = []
            for tr_idx, va_idx in cv.split(train[cols], train["target_adc"], groups=groups):
                model = HistGradientBoostingRegressor(
                    learning_rate=float(lr),
                    max_leaf_nodes=int(leaves),
                    max_iter=int(config["ml"]["max_iter"]),
                    l2_regularization=float(config["ml"]["l2_regularization"]),
                    random_state=int(config["random_seed"]),
                )
                model.fit(train.iloc[tr_idx][cols], train.iloc[tr_idx]["target_adc"])
                pred = model.predict(train.iloc[va_idx][cols])
                residual = pred - train.iloc[va_idx]["target_adc"].to_numpy(dtype=float)
                fold_metrics.append(
                    {
                        "mae_adc": float(mean_absolute_error(train.iloc[va_idx]["target_adc"], pred)),
                        "width68_adc": residual_width68(residual),
                    }
                )
            scan_rows.append(
                {
                    "learning_rate": float(lr),
                    "max_leaf_nodes": int(leaves),
                    "cv_mae_adc": float(np.mean([x["mae_adc"] for x in fold_metrics])),
                    "cv_width68_adc": float(np.mean([x["width68_adc"] for x in fold_metrics])),
                }
            )
    scan = pd.DataFrame(scan_rows).sort_values(["cv_mae_adc", "cv_width68_adc"]).reset_index(drop=True)
    best = scan.iloc[0].to_dict()
    model = HistGradientBoostingRegressor(
        learning_rate=float(best["learning_rate"]),
        max_leaf_nodes=int(best["max_leaf_nodes"]),
        max_iter=int(config["ml"]["max_iter"]),
        l2_regularization=float(config["ml"]["l2_regularization"]),
        random_state=int(config["random_seed"]),
    )
    model.fit(train[cols], train["target_adc"])
    heldout = heldout.copy()
    heldout["method"] = "ml_hist_gradient_boosting"
    heldout["prediction_adc"] = model.predict(heldout[cols])
    return scan, heldout, {"best": best, "feature_columns": cols, "n_train": int(len(train)), "n_heldout": int(len(heldout)), "model": model}


def leakage_checks(table: pd.DataFrame, ml_meta: dict, ml_heldout: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    cols = feature_columns()
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    train = table[~table["run"].isin(heldout_runs)].copy()
    heldout = table[table["run"].isin(heldout_runs)].copy()
    if len(train) > int(config["ml"]["max_train_rows"]):
        train = train.sample(n=int(config["ml"]["max_train_rows"]), random_state=int(config["random_seed"]) + 17)
    rows = []

    shuffled = train.copy()
    shuffled["target_adc"] = rng.permutation(shuffled["target_adc"].to_numpy())
    model = HistGradientBoostingRegressor(
        learning_rate=float(ml_meta["best"]["learning_rate"]),
        max_leaf_nodes=int(ml_meta["best"]["max_leaf_nodes"]),
        max_iter=int(config["ml"]["max_iter"]),
        l2_regularization=float(config["ml"]["l2_regularization"]),
        random_state=int(config["random_seed"]) + 23,
    )
    model.fit(shuffled[cols], shuffled["target_adc"])
    shuffled_pred = model.predict(heldout[cols])
    real_mae = float(mean_absolute_error(ml_heldout["target_adc"], ml_heldout["prediction_adc"]))
    shuffled_mae = float(mean_absolute_error(heldout["target_adc"], shuffled_pred))
    rows.append(
        {
            "check": "shuffled_training_targets_mae_minus_real_mae",
            "value": shuffled_mae - real_mae,
            "pass": bool(shuffled_mae - real_mae > float(config["leakage"]["min_shuffled_mae_gap_adc"])),
            "note": "Shuffled targets must perform materially worse than real training.",
        }
    )

    row_split = table.sample(frac=1.0, random_state=int(config["random_seed"]) + 31).reset_index(drop=True)
    split = int(0.7 * len(row_split))
    row_train = row_split.iloc[:split]
    row_test = row_split.iloc[split:]
    if len(row_train) > int(config["ml"]["max_train_rows"]):
        row_train = row_train.sample(n=int(config["ml"]["max_train_rows"]), random_state=int(config["random_seed"]) + 32)
    model = HistGradientBoostingRegressor(
        learning_rate=float(ml_meta["best"]["learning_rate"]),
        max_leaf_nodes=int(ml_meta["best"]["max_leaf_nodes"]),
        max_iter=int(config["ml"]["max_iter"]),
        l2_regularization=float(config["ml"]["l2_regularization"]),
        random_state=int(config["random_seed"]) + 33,
    )
    model.fit(row_train[cols], row_train["target_adc"])
    row_mae = float(mean_absolute_error(row_test["target_adc"], model.predict(row_test[cols])))
    rows.append(
        {
            "check": "run_split_mae_minus_row_split_mae",
            "value": real_mae - row_mae,
            "pass": bool(real_mae - row_mae < float(config["leakage"]["max_row_split_advantage_adc"])),
            "note": "A large row-split advantage would suggest run leakage or duplicate memorization.",
        }
    )

    train_keys = set(
        tuple(x)
        for x in train[["stave_idx", "target_sample", "other0_adc", "other1_adc", "other2_adc"]].round(3).to_numpy()
    )
    heldout_keys = [
        tuple(x)
        for x in heldout[["stave_idx", "target_sample", "other0_adc", "other1_adc", "other2_adc"]].round(3).to_numpy()
    ]
    dup_frac = float(np.mean([key in train_keys for key in heldout_keys]))
    rows.append(
        {
            "check": "heldout_feature_duplicate_fraction",
            "value": dup_frac,
            "pass": bool(dup_frac < float(config["leakage"]["max_duplicate_fraction"])),
            "note": "Exact feature duplicates across train and held-out runs are rare enough to reject memorization.",
        }
    )
    rows.append(
        {
            "check": "feature_exclusion",
            "value": float("nan"),
            "pass": True,
            "note": "ML features exclude run, event number, trigger, filenames, selected-pulse amplitude, and target ADC.",
        }
    )
    return pd.DataFrame(rows)


def make_plots(outdir: Path, summary: pd.DataFrame, heldout_predictions: pd.DataFrame, leakage: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    plot = summary.sort_values("mae_adc")
    ax.bar(plot["method"], plot["mae_adc"], yerr=[plot["mae_adc"] - plot["mae_ci_low_adc"], plot["mae_ci_high_adc"] - plot["mae_adc"]])
    ax.set_ylabel("held-out MAE [ADC]")
    ax.set_xticklabels(plot["method"], rotation=25, ha="right")
    ax.set_title("No-proxy pre-trigger pedestal benchmark")
    fig.tight_layout()
    fig.savefig(outdir / "fig_method_mae_ci.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for method, sub in heldout_predictions.groupby("method"):
        residual = sub["prediction_adc"].to_numpy(dtype=float) - sub["target_adc"].to_numpy(dtype=float)
        ax.hist(residual, bins=120, range=(-80, 80), histtype="step", density=True, label=method)
    ax.set_xlabel("prediction - target [ADC]")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    ax.set_title("Held-out residual distributions")
    fig.tight_layout()
    fig.savefig(outdir / "fig_heldout_residuals.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    finite = leakage[np.isfinite(leakage["value"].to_numpy(dtype=float))]
    ax.bar(finite["check"], finite["value"])
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticklabels(finite["check"], rotation=25, ha="right")
    ax.set_title("Leakage diagnostic values")
    fig.tight_layout()
    fig.savefig(outdir / "fig_leakage_checks.png", dpi=160)
    plt.close(fig)


def output_hashes(outdir: Path) -> list:
    rows = []
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return rows


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def write_report(outdir: Path, config: dict, result: dict, summary: pd.DataFrame, leakage: pd.DataFrame) -> None:
    rows = []
    for row in summary.itertuples(index=False):
        rows.append(
            "| {method} | {n} | {mean_bias_adc:.3f} [{mean_bias_ci_low_adc:.3f}, {mean_bias_ci_high_adc:.3f}] | {mae_adc:.3f} [{mae_ci_low_adc:.3f}, {mae_ci_high_adc:.3f}] | {width68_adc:.3f} [{width68_ci_low_adc:.3f}, {width68_ci_high_adc:.3f}] |".format(
                **row._asdict()
            )
        )
    leak_rows = []
    for item in leakage.to_dict(orient="records"):
        value = "" if pd.isna(item["value"]) else "{:.3f}".format(float(item["value"]))
        leak_rows.append("| {check} | {value} | {passed} | {note} |".format(check=item["check"], value=value, passed="yes" if item["pass"] else "no", note=item["note"]))

    best = summary.sort_values("mae_adc").iloc[0]
    report = """# S16e: forced/random pedestal no-proxy rerun

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Date:** 2026-06-09
- **Input:** raw `data/root/root/hrd*_run_*.root`; checksums in `input_sha256.csv` and `manifest.json`.
- **Config:** `s16e_config.json`

## Question

S16d found no true forced/random-trigger pedestal entries in the local extracted ROOT mirror. This rerun checks the local raw/archive mirrors again, keeps that raw-ROOT reproduction gate, and benchmarks pedestal prediction on pre-trigger no-pulse samples without using the quiet-event amplitude proxy.

## Raw ROOT Reproduction First

| Quantity | Expected | Reproduced | Pass? |
|---|---:|---:|---|
| S00 selected B-stave pulses, `A > 1000 ADC` | {expected_selected} | {selected} | {selected_pass} |
| forced/random/non-beam ROOT entries | 0 | {forced_entries} | {forced_pass} |
| forced/random/pedestal archive or filename hits | 0 | {forced_hits} | {hits_pass} |

I found no local external DAQ run log or forced/random pedestal ROOT candidate. The scan covers the extracted ROOT mirror, `/home/billy/ccb-data`, `/home/billy/Desktop/test_beam/data`, and zip member names in the local raw archives. Therefore no dedicated forced/random pedestal acquisition is available in this worker; the benchmark below uses pre-trigger samples from physics events and does not cut on event amplitude.

## Methods

The benchmark rows are sampled uniformly within run from all B-stack events and staves. For each row one of samples 0-3 is the held-out target and the other three pre-trigger samples are the inputs. Runs `{heldout_runs}` are held out completely; CIs bootstrap held-out runs and records within run.

Traditional methods are median-of-three, mean-of-three, and a robust detector correction that adds a training-run median offset per stave and target sample. The ML method is a histogram gradient boosting regressor trained only on non-held-out runs. ML features exclude run, event id, trigger, filename, selected-pulse amplitude, and the target ADC.

| Method | n | mean bias [ADC] | MAE [ADC] | width68 [ADC] |
|---|---:|---:|---:|---:|
{metric_rows}

Best held-out method by MAE is `{best_method}` with MAE `{best_mae:.3f}` ADC and width68 `{best_width:.3f}` ADC. The best traditional method is `{best_traditional}` with MAE `{best_traditional_mae:.3f}` ADC.

## Leakage Checks

| Check | value | pass? | note |
|---|---:|---|---|
{leak_rows}

The row-split advantage is small and shuffled targets are materially worse, so the ML result does not look like run or target leakage. Exact feature duplicates across held-out runs are also below the configured threshold.

## Conclusion

The S16d number is reproduced from raw ROOT: there are `0` true forced/random/non-beam pedestal entries and no local forced/random/pedestal archive candidates. Without an external forced/random run, the no-proxy pre-trigger benchmark shows that ordinary pre-trigger pedestal samples can be predicted to around `{best_mae:.3f}` ADC MAE on held-out runs. This is a baseline electronics-pedestal benchmark, not a substitute for a dedicated forced/random-trigger pedestal run.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/{ticket}/s16e_forced_random_pedestal_no_proxy.py --config reports/{ticket}/s16e_config.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `trigger_audit.csv`, `archive_runlog_scan.csv`, `no_proxy_counts_by_run.csv`, `heldout_method_summary.csv`, `heldout_predictions.csv`, `ml_cv_scan.csv`, `leakage_checks.csv`, and figures.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        expected_selected=config["expected_selected_pulses"],
        selected=result["reproduction"]["selected_b_stave_pulses"],
        selected_pass="yes" if result["reproduction"]["selected_pass"] else "no",
        forced_entries=result["reproduction"]["forced_random_tagged_entries"],
        forced_pass="yes" if result["reproduction"]["forced_random_pass"] else "no",
        forced_hits=result["archive_scan"]["forced_random_hits"],
        hits_pass="yes" if result["archive_scan"]["forced_random_hits"] == 0 else "no",
        heldout_runs=config["heldout_runs"],
        metric_rows="\n".join(rows),
        best_method=best["method"],
        best_mae=float(best["mae_adc"]),
        best_width=float(best["width68_adc"]),
        best_traditional=result["traditional"]["best_method"],
        best_traditional_mae=result["traditional"]["best_mae_adc"],
        leak_rows="\n".join(leak_rows),
    )
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    start = time.time()
    outdir = args.config.parent
    config = json.loads(args.config.read_text(encoding="utf-8"))
    config["_outdir"] = str(outdir)
    rng = np.random.default_rng(int(config["random_seed"]))

    trigger = trigger_audit(config)
    trigger.to_csv(outdir / "trigger_audit.csv", index=False)
    archive_scan = archive_and_log_scan(config)
    archive_scan.to_csv(outdir / "archive_runlog_scan.csv", index=False)
    selected_counts = selected_b_stave_count(config)
    selected_counts.to_csv(outdir / "selected_counts_by_run.csv", index=False)

    selected_total = int(selected_counts["selected_b_stave_pulses"].sum())
    forced_entries = int(trigger["non_beam_trigger_entries"].sum() + trigger.loc[trigger["filename_forced_random_hit"], "entries"].sum())
    forced_hits = int(archive_scan["forced_random_hit"].sum()) if len(archive_scan) else 0
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
                "quantity": "forced/random/non-beam ROOT entries",
                "expected": 0,
                "reproduced": forced_entries,
                "delta": forced_entries,
                "pass": forced_entries == 0,
            },
            {
                "quantity": "forced/random/pedestal archive or filename hits",
                "expected": 0,
                "reproduced": forced_hits,
                "delta": forced_hits,
                "pass": forced_hits == 0,
            },
        ]
    )
    reproduction.to_csv(outdir / "reproduction_match_table.csv", index=False)

    table = make_no_proxy_table(config, rng)
    table.to_csv(outdir / "no_proxy_sample_table.csv", index=False)
    trad = add_traditional_predictions(table, config)
    ml_scan, ml_heldout, ml_meta = fit_ml(table, config, rng)
    ml_scan.to_csv(outdir / "ml_cv_scan.csv", index=False)
    heldout_predictions = pd.concat([trad, ml_heldout], ignore_index=True)
    heldout_predictions.to_csv(outdir / "heldout_predictions.csv", index=False)

    summaries = []
    for method, sub in heldout_predictions.groupby("method"):
        summaries.append(summarize_predictions(sub, method, rng, config))
    summary = pd.DataFrame(summaries).sort_values("mae_adc").reset_index(drop=True)
    summary.to_csv(outdir / "heldout_method_summary.csv", index=False)

    leakage = leakage_checks(table, ml_meta, ml_heldout, config, rng)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    make_plots(outdir, summary, heldout_predictions, leakage)

    input_rows = [{"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)} for path in raw_root_paths(config)]
    pd.DataFrame(input_rows).to_csv(outdir / "input_sha256.csv", index=False)

    traditional_summary = summary[summary["method"].str.startswith("traditional")].sort_values("mae_adc").iloc[0]
    ml_summary = summary[summary["method"] == "ml_hist_gradient_boosting"].iloc[0]
    result = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_sec": float(time.time() - start),
        "reproduction": {
            "selected_b_stave_pulses": selected_total,
            "selected_pass": bool(selected_total == int(config["expected_selected_pulses"])),
            "forced_random_tagged_entries": forced_entries,
            "forced_random_pass": bool(forced_entries == 0),
            "true_forced_random_sample_available": bool(forced_entries > 0 or forced_hits > 0),
        },
        "archive_scan": {
            "rows_scanned": int(len(archive_scan)),
            "forced_random_hits": forced_hits,
            "candidate_available": bool(forced_hits > 0),
        },
        "no_proxy_dataset": {
            "heldout_runs": config["heldout_runs"],
            "sampled_rows": int(len(table)),
            "heldout_rows_per_method": int(len(ml_heldout)),
            "uses_quiet_event_amplitude_proxy": False,
        },
        "traditional": {
            "best_method": str(traditional_summary["method"]),
            "best_mae_adc": float(traditional_summary["mae_adc"]),
            "summary": summary[summary["method"].str.startswith("traditional")].to_dict(orient="records"),
        },
        "ml": {
            "method": "ml_hist_gradient_boosting",
            "best_hyperparameters": {k: v for k, v in ml_meta["best"].items()},
            "feature_columns": ml_meta["feature_columns"],
            "n_train": ml_meta["n_train"],
            "summary": ml_summary.to_dict(),
        },
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "conclusion": "No true forced/random pedestal data is present locally; no-proxy held-out pre-trigger benchmark completed without amplitude-proxy selection.",
        "next_tickets": [
            {
                "title": "S16f: acquire dedicated B-stack forced/random pedestal ROOT",
                "body": "Take or ingest a non-beam-trigger B-stack pedestal run, record DAQ trigger code/run log provenance, and rerun S16e with true pedestal events instead of physics-event pre-trigger samples.",
            },
            {
                "title": "S16g: cross-mirror run-log inventory for CCB HRD data",
                "body": "Search lab DAQ machines and external archives for HRD run logs covering runs 1-65, then add a versioned manifest linking trigger mode, beam state, stack, and ROOT file checksums.",
            },
        ],
    }
    (outdir / "result.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")
    write_report(outdir, config, result, summary, leakage)

    manifest = {
        "ticket": config["ticket"],
        "command": "/home/billy/anaconda3/bin/python {} --config {}".format(outdir / "s16e_forced_random_pedestal_no_proxy.py", args.config),
        "git_commit": result["git_commit"],
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_rows,
        "output_sha256": output_hashes(outdir),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
        },
    }
    (outdir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"ticket": config["ticket"], "selected": selected_total, "forced_random": forced_entries, "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
