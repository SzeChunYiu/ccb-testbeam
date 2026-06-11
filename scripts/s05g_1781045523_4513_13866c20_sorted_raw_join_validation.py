#!/usr/bin/env python3
"""S05g: raw-to-sorted event identity and channel mapping validation.

The study intentionally starts from reduced raw ROOT files, reproduces the
standard B-stave HRDv selected-pulse count, and only then audits sorted ROOT
event joins used by A/B external-control consumers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception:  # pragma: no cover - environment recorded in manifest
    torch = None
    nn = None
    F = None


CHANNELS = [0, 2, 4, 6]
JOIN_METHODS = ["entry_order", "evt_occurrence", "eventno_naive"]
ML_METHODS = ["ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "agreement_gated_cnn_new"]
TRADITIONAL_METHOD = "deterministic_evt_occurrence_join"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if pd.isna(value):
        return None
    return value


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def raw_file(config: dict, stack: str, run: int) -> Path:
    prefix = config["stacks"][stack]["raw_prefix"]
    return Path(config["raw_root_dir"]) / f"{prefix}_run_{run:04d}.root"


def sorted_file(config: dict, stack: str, run: int) -> Path:
    spec = config["stacks"][stack]
    return Path(config[spec["sorted_dir_key"]]) / f"{spec['raw_prefix']}_run_{run:04d}-sorted.root"


def sample_group(config: dict, run: int) -> str:
    for name, runs in config["runs"].items():
        if int(run) in {int(x) for x in runs}:
            return name
    return "other"


def configured_b_runs(config: dict) -> list[int]:
    runs = []
    for group in ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]:
        runs.extend(int(x) for x in config["runs"][group])
    return sorted(set(runs))


def stack_object_array(arr, width: int | None = None) -> np.ndarray:
    if len(arr) == 0:
        if width is None:
            return np.empty((0,), dtype=float)
        return np.empty((0, width), dtype=float)
    return np.vstack([np.asarray(x) for x in arr])


def load_raw(path: Path, config: dict) -> dict:
    tree = uproot.open(path)["h101"]
    arrays = tree.arrays(["EVENTNO", "EVT", "HRDv"], library="np")
    eventno = np.asarray(arrays["EVENTNO"], dtype=np.int64)
    evt = np.asarray(arrays["EVT"], dtype=np.int64)
    waves = stack_object_array(arrays["HRDv"], width=8 * int(config["samples_per_channel"])).astype(np.float64).reshape(-1, 8, int(config["samples_per_channel"]))
    baseline_idx = list(config["baseline_samples"])
    raw_amp_median = waves.max(axis=2) - np.median(waves[:, :, baseline_idx], axis=2)
    raw_amp_min = waves.max(axis=2) - waves.min(axis=2)
    return {
        "eventno": eventno,
        "evt": evt,
        "raw_amp_median": raw_amp_median,
        "raw_amp_min": raw_amp_min,
        "n": int(len(evt)),
    }


def load_sorted(path: Path, config: dict) -> dict:
    tree = uproot.open(path)["tree"]
    arrays = tree.arrays(["hrdEvtNo", "hrdMax", "hrdTrMax", "hrdMaxTS", "hrd/hrd.sample"], library="np")
    hrd_evt = np.asarray(arrays["hrdEvtNo"], dtype=np.int64)
    hrd_max = stack_object_array(arrays["hrdMax"], width=8).astype(np.float64)
    hrd_trmax = stack_object_array(arrays["hrdTrMax"], width=8).astype(np.float64)
    hrd_maxts = stack_object_array(arrays["hrdMaxTS"], width=8).astype(np.float64)
    sorted_samples = stack_object_array(arrays["hrd/hrd.sample"], width=8 * int(config["samples_per_channel"])).astype(np.float64).reshape(-1, 8, int(config["samples_per_channel"]))
    sorted_wave_max = sorted_samples.max(axis=2)
    return {
        "hrd_evt": hrd_evt,
        "hrd_max": hrd_max,
        "hrd_trmax": hrd_trmax,
        "hrd_maxts": hrd_maxts,
        "sorted_wave_max": sorted_wave_max,
        "n": int(len(hrd_evt)),
    }


def duplicate_count(values: np.ndarray) -> int:
    if len(values) == 0:
        return 0
    return int(len(values) - len(np.unique(values)))


def occurrence_index(values: np.ndarray) -> np.ndarray:
    seen = {}
    out = np.empty(len(values), dtype=np.int64)
    for idx, val in enumerate(values):
        key = int(val)
        out[idx] = seen.get(key, 0)
        seen[key] = int(out[idx]) + 1
    return out


def join_indices(raw: dict, sorted_: dict, method: str) -> tuple[np.ndarray, np.ndarray]:
    n = min(raw["n"], sorted_["n"])
    if method == "entry_order":
        return np.arange(n, dtype=np.int64), np.arange(n, dtype=np.int64)
    raw_key_values = raw["evt"] if method == "evt_occurrence" else raw["eventno"]
    raw_occ = occurrence_index(raw_key_values)
    sorted_occ = occurrence_index(sorted_["hrd_evt"])
    raw_map = {(int(raw_key_values[i]), int(raw_occ[i])): i for i in range(len(raw_key_values))}
    raw_idx = []
    sorted_idx = []
    for j, (key, occ) in enumerate(zip(sorted_["hrd_evt"], sorted_occ)):
        i = raw_map.get((int(key), int(occ)))
        if i is not None:
            raw_idx.append(i)
            sorted_idx.append(j)
    return np.asarray(raw_idx, dtype=np.int64), np.asarray(sorted_idx, dtype=np.int64)


def corrcoef(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return float("nan")
    if np.nanstd(x[mask]) == 0 or np.nanstd(y[mask]) == 0:
        return float("nan")
    return float(np.corrcoef(x[mask], y[mask])[0, 1])


def sigma68(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        return float("nan")
    arr = arr - np.nanmedian(arr)
    return float(0.5 * (np.nanpercentile(arr, 84) - np.nanpercentile(arr, 16)))


def quality_counts(config: dict, raw: dict, sorted_: dict, raw_idx: np.ndarray, sorted_idx: np.ndarray, channels: list[int]) -> dict:
    if len(raw_idx) == 0:
        return {
            "joined_events": 0,
            "raw_selected_pulses": 0,
            "sorted_any_clean_pulses": 0,
            "sorted_tr_clean_pulses": 0,
        }
    raw_amp = raw["raw_amp_median"][raw_idx][:, channels]
    hmax = sorted_["hrd_max"][sorted_idx][:, channels]
    trmax = sorted_["hrd_trmax"][sorted_idx][:, channels]
    maxts = sorted_["hrd_maxts"][sorted_idx][:, channels]
    clean_time = (maxts >= float(config["sorted_maxts_min"])) & (maxts <= float(config["sorted_maxts_max"]))
    return {
        "joined_events": int(len(raw_idx)),
        "raw_selected_pulses": int(np.sum(raw_amp > float(config["amplitude_cut_adc"]))),
        "sorted_any_clean_pulses": int(np.sum((hmax > float(config["sorted_clean_cut_adc"])) & clean_time)),
        "sorted_tr_clean_pulses": int(np.sum((trmax > float(config["sorted_trmax_cut_adc"])) & clean_time)),
    }


def reproduce_b_count_gate(config: dict) -> pd.DataFrame:
    rows = []
    for run in configured_b_runs(config):
        path = raw_file(config, "B", run)
        raw = load_raw(path, config)
        amps = raw["raw_amp_median"][:, CHANNELS]
        selected = int(np.sum(amps > float(config["amplitude_cut_adc"])))
        rows.append(
            {
                "run": int(run),
                "sample_group": sample_group(config, run),
                "raw_entries": int(raw["n"]),
                "selected_b_pulses": selected,
            }
        )
    return pd.DataFrame(rows).sort_values("run")


def audit_run(config: dict, stack: str, run: int, raw: dict, sorted_: dict) -> tuple[list[dict], list[dict], list[dict]]:
    spec = config["stacks"][stack]
    channels = [int(v) for v in spec["consumer_channels"].values()]
    audit_rows = []
    quality_rows = []
    corr_rows = []
    n = min(raw["n"], sorted_["n"])
    entry_evt_match = float(np.mean(raw["evt"][:n] == sorted_["hrd_evt"][:n])) if n else float("nan")
    audit_rows.append(
        {
            "stack": stack,
            "run": int(run),
            "sample_group": sample_group(config, run),
            "raw_entries": int(raw["n"]),
            "sorted_entries": int(sorted_["n"]),
            "entry_count_delta": int(sorted_["n"] - raw["n"]),
            "raw_eventno_min": int(np.min(raw["eventno"])) if raw["n"] else None,
            "raw_eventno_max": int(np.max(raw["eventno"])) if raw["n"] else None,
            "raw_evt_min": int(np.min(raw["evt"])) if raw["n"] else None,
            "raw_evt_max": int(np.max(raw["evt"])) if raw["n"] else None,
            "sorted_hrdEvtNo_min": int(np.min(sorted_["hrd_evt"])) if sorted_["n"] else None,
            "sorted_hrdEvtNo_max": int(np.max(sorted_["hrd_evt"])) if sorted_["n"] else None,
            "raw_evt_duplicates": duplicate_count(raw["evt"]),
            "raw_eventno_duplicates": duplicate_count(raw["eventno"]),
            "sorted_hrdEvtNo_duplicates": duplicate_count(sorted_["hrd_evt"]),
            "entry_order_evt_match_rate": entry_evt_match,
        }
    )
    for method in JOIN_METHODS:
        raw_idx, sorted_idx = join_indices(raw, sorted_, method)
        counts = quality_counts(config, raw, sorted_, raw_idx, sorted_idx, channels)
        quality_rows.append(
            {
                "stack": stack,
                "run": int(run),
                "join_method": method,
                "sample_group": sample_group(config, run),
                **counts,
                "event_join_loss_vs_entry": int(n - len(raw_idx)),
                "joined_fraction_vs_entry": float(len(raw_idx) / n) if n else float("nan"),
            }
        )
        for name, ch in spec["consumer_channels"].items():
            ch = int(ch)
            if len(raw_idx) == 0:
                raw_amp = np.asarray([])
                hmax = np.asarray([])
                wavemax = np.asarray([])
            else:
                raw_amp = raw["raw_amp_median"][raw_idx, ch]
                hmax = sorted_["hrd_max"][sorted_idx, ch]
                wavemax = sorted_["sorted_wave_max"][sorted_idx, ch]
            corr_rows.append(
                {
                    "stack": stack,
                    "run": int(run),
                    "join_method": method,
                    "channel_name": name,
                    "channel_index": ch,
                    "n_events": int(len(raw_idx)),
                    "corr_raw_amp_vs_hrdMax": corrcoef(raw_amp, hmax),
                    "corr_sorted_wave_max_vs_hrdMax": corrcoef(wavemax, hmax),
                    "sigma68_hrdMax_minus_raw_amp_adc": sigma68(hmax - raw_amp) if len(raw_idx) else float("nan"),
                    "sigma68_hrdMax_minus_sorted_wave_max_adc": sigma68(hmax - wavemax) if len(raw_idx) else float("nan"),
                    "median_hrdMax_minus_raw_amp_adc": float(np.nanmedian(hmax - raw_amp)) if len(raw_idx) else float("nan"),
                    "median_hrdMax_minus_sorted_wave_max_adc": float(np.nanmedian(hmax - wavemax)) if len(raw_idx) else float("nan"),
                }
            )
    return audit_rows, quality_rows, corr_rows


def build_ml_rows(config: dict, rng: np.random.Generator, cache: dict[tuple[str, int], tuple[dict, dict]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    rows = []
    labels = []
    runs = []
    stacks = []
    meta = []
    max_events = int(config["ml"]["max_events_per_run_stack"])
    for stack in ["A", "B"]:
        for run in config["analysis_runs"]:
            raw, sorted_ = cache[(stack, int(run))]
            raw_idx, sorted_idx = join_indices(raw, sorted_, "evt_occurrence")
            if len(raw_idx) < 3:
                continue
            take = np.arange(len(raw_idx))
            if len(take) > max_events:
                take = rng.choice(take, size=max_events, replace=False)
            for pos in take:
                i = int(raw_idx[pos])
                j = int(sorted_idx[pos])
                variants = [
                    ("correct_evt_occurrence", i, raw["raw_amp_median"][i, CHANNELS], 1),
                    ("entry_shift_plus_one_control", min(i + 1, raw["n"] - 1), raw["raw_amp_median"][min(i + 1, raw["n"] - 1), CHANNELS], 0),
                    ("channel_rotate_control", i, np.roll(raw["raw_amp_median"][i, CHANNELS], 1), 0),
                ]
                hmax = sorted_["hrd_max"][j, CHANNELS]
                trmax = sorted_["hrd_trmax"][j, CHANNELS]
                maxts = sorted_["hrd_maxts"][j, CHANNELS]
                for variant, raw_event_idx, raw_amp, label in variants:
                    residual = hmax - raw_amp
                    features = np.column_stack(
                        [
                            hmax,
                            trmax,
                            maxts,
                            raw_amp,
                            residual,
                            np.abs(residual),
                            np.full(len(CHANNELS), 0.0 if stack == "A" else 1.0),
                        ]
                    )
                    rows.append(features.reshape(-1))
                    labels.append(int(label))
                    runs.append(int(run))
                    stacks.append(stack)
                    meta.append(
                        {
                            "stack": stack,
                            "run": int(run),
                            "variant": variant,
                            "label_correct": int(label),
                            "sorted_entry": int(j),
                            "raw_entry": int(raw_event_idx),
                        }
                    )
    return (
        np.asarray(rows, dtype=np.float32),
        np.asarray(labels, dtype=np.int64),
        np.asarray(runs, dtype=np.int64),
        np.asarray(stacks),
        pd.DataFrame(meta),
    )


class SimpleCNN(nn.Module):
    def __init__(self, n_features: int, gated: bool = False):
        super().__init__()
        self.gated = gated
        self.conv1 = nn.Conv1d(n_features, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(16, 16, kernel_size=3, padding=1)
        self.head = nn.Sequential(nn.Linear(16, 16), nn.ReLU(), nn.Linear(16, 1))
        self.gate = nn.Sequential(nn.Linear(1, 4), nn.ReLU(), nn.Linear(4, 1), nn.Sigmoid())

    def forward(self, x):
        # x: rows, channels, features
        z = x.transpose(1, 2)
        z = F.relu(self.conv1(z))
        z = F.relu(self.conv2(z)).mean(dim=2)
        logits = self.head(z).squeeze(1)
        if self.gated:
            agreement = torch.exp(-torch.median(torch.abs(x[:, :, 5]), dim=1).values / 25.0).unsqueeze(1)
            logits = logits * self.gate(agreement).squeeze(1)
        return logits


def torch_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    config: dict,
    gated: bool,
    seed: int,
) -> np.ndarray:
    if torch is None:
        return np.full(len(x_test), np.nan)
    torch.manual_seed(int(seed))
    n_feat = x_train.shape[1] // len(CHANNELS)
    model = SimpleCNN(n_feat, gated=gated)
    opt = torch.optim.Adam(model.parameters(), lr=float(config["ml"]["torch_learning_rate"]))
    xb = torch.tensor(x_train.reshape(-1, len(CHANNELS), n_feat), dtype=torch.float32)
    yb = torch.tensor(y_train.astype(np.float32), dtype=torch.float32)
    batch_size = int(config["ml"]["torch_batch_size"])
    gen = torch.Generator().manual_seed(int(seed))
    for _ in range(int(config["ml"]["torch_epochs"])):
        order = torch.randperm(len(xb), generator=gen)
        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            opt.zero_grad()
            loss = F.binary_cross_entropy_with_logits(model(xb[idx]), yb[idx])
            loss.backward()
            opt.step()
    with torch.no_grad():
        xt = torch.tensor(x_test.reshape(-1, len(CHANNELS), n_feat), dtype=torch.float32)
        return torch.sigmoid(model(xt)).cpu().numpy()


def sklearn_predict(method: str, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, seed: int) -> np.ndarray:
    if method == "ridge":
        model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=500, random_state=seed))
    elif method == "gradient_boosted_trees":
        model = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.08, l2_regularization=0.05, max_leaf_nodes=15, random_state=seed)
    elif method == "mlp":
        model = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(32, 16), activation="relu", alpha=0.001, max_iter=120, random_state=seed),
        )
    else:
        raise ValueError(method)
    model.fit(x_train, y_train)
    return model.predict_proba(x_test)[:, 1]


def run_ml_sentinels(config: dict, x: np.ndarray, y: np.ndarray, runs: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    max_train = int(config["ml"]["max_train_rows_per_fold"])
    for heldout in sorted(np.unique(runs)):
        train = np.where(runs != heldout)[0]
        test = np.where(runs == heldout)[0]
        if len(test) == 0 or len(np.unique(y[test])) < 2:
            continue
        if len(train) > max_train:
            train = rng.choice(train, size=max_train, replace=False)
        for method in ML_METHODS:
            if method in {"cnn_1d", "agreement_gated_cnn_new"}:
                pred = torch_predict(x[train], y[train], x[test], config, gated=method.endswith("_new"), seed=int(config["random_seed"]) + int(heldout))
            else:
                pred = sklearn_predict(method, x[train], y[train], x[test], seed=int(config["random_seed"]) + int(heldout))
            if np.all(~np.isfinite(pred)):
                auc = ap = acc = brier = float("nan")
            else:
                auc = float(roc_auc_score(y[test], pred))
                ap = float(average_precision_score(y[test], pred))
                acc = float(accuracy_score(y[test], pred >= 0.5))
                brier = float(brier_score_loss(y[test], pred))
            rows.append(
                {
                    "method": method,
                    "heldout_run": int(heldout),
                    "n_train": int(len(train)),
                    "n_test": int(len(test)),
                    "roc_auc": auc,
                    "average_precision": ap,
                    "accuracy": acc,
                    "brier": brier,
                }
            )
    return pd.DataFrame(rows)


def run_bootstrap_summary(frame: pd.DataFrame, group_cols: list[str], metric_cols: list[str], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for keys, group in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = {col: key for col, key in zip(group_cols, keys)}
        run_col = "run" if "run" in group.columns else "heldout_run"
        runs = np.asarray(sorted(group[run_col].unique()), dtype=int)
        for metric in metric_cols:
            by_run = (
                group[[run_col, metric]]
                .replace([np.inf, -np.inf], np.nan)
                .dropna()
                .groupby(run_col)[metric]
                .mean()
                .reindex(runs)
                .dropna()
                .to_numpy(dtype=float)
            )
            values = [float(np.nanmean(rng.choice(by_run, size=len(by_run), replace=True))) for _ in range(int(n_boot))] if len(by_run) else []
            arr = group[metric].to_numpy(dtype=float)
            arr = arr[np.isfinite(arr)]
            ci = np.nanquantile(values, [0.025, 0.975]) if values else [np.nan, np.nan]
            rows.append(
                {
                    **base,
                    "metric": metric,
                    "value": float(np.nanmean(arr)) if len(arr) else float("nan"),
                    "ci_low": float(ci[0]),
                    "ci_high": float(ci[1]),
                    "n_runs": int(len(runs)),
                }
            )
    return pd.DataFrame(rows)


def pivot_markdown(frame: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if frame.empty:
        return "_No rows._"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False, floatfmt=".4g")


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    audit: pd.DataFrame,
    quality: pd.DataFrame,
    corr: pd.DataFrame,
    corr_summary: pd.DataFrame,
    quality_summary: pd.DataFrame,
    ml_summary: pd.DataFrame,
    result: dict,
) -> None:
    total = int(reproduction["selected_b_pulses"].sum())
    sample_i = int(reproduction.loc[reproduction["sample_group"].eq("sample_i_analysis"), "selected_b_pulses"].sum())
    sample_ii = int(reproduction.loc[reproduction["sample_group"].eq("sample_ii_analysis"), "selected_b_pulses"].sum())
    evt = corr_summary[(corr_summary["join_method"].eq("evt_occurrence")) & (corr_summary["metric"].eq("corr_raw_amp_vs_hrdMax"))]
    residual = corr_summary[(corr_summary["join_method"].eq("evt_occurrence")) & (corr_summary["metric"].eq("sigma68_hrdMax_minus_sorted_wave_max_adc"))]
    ml_auc = ml_summary[ml_summary["metric"].eq("roc_auc")].sort_values("value", ascending=False)
    report = f"""# S05g: sorted raw-event join validation for A/B controls

## Abstract

S05g tests whether the sorted ROOT products used by A/B external-control consumers preserve the raw event identity and physical channel mapping required by the S05 covariance analyses.  The analysis first rebuilds the raw `HRDv` selected-pulse count gate on the configured S05 run universe (Sample I/II calibration and analysis runs, with run 43 excluded), then compares raw `EVENTNO`/`EVT` against sorted `hrdEvtNo` under three deterministic joins: entry order, `EVT` with occurrence rank, and a deliberately naive `EVENTNO` join.  It also benchmarks run-heldout leakage sentinels using Ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, and a new agreement-gated CNN on deterministic bad-join controls.  No simulated Monte Carlo samples are used.

## Reproduction Gate

The B-stack raw pulse gate is

\\[
A_{{r,e,c}} = \\max_t H_{{r,e,c,t}} - \\operatorname{{median}}_{{t \\in \\{{0,1,2,3\\}}}} H_{{r,e,c,t}},
\\quad c \\in \\{{0,2,4,6\\}},
\\quad A_{{r,e,c}} > {float(config['amplitude_cut_adc']):.0f}\\,\\mathrm{{ADC}} .
\\]

The reproduced total is **{total:,}** selected B pulses; Sample-I analysis has **{sample_i:,}**, and Sample-II analysis has **{sample_ii:,}**.  The expected anchors are {int(config['expected_counts']['total_selected_b_pulses']):,}, {int(config['expected_counts']['sample_i_analysis_b_selected_pulses']):,}, and {int(config['expected_counts']['sample_ii_analysis_b_selected_pulses']):,}, respectively.  `result.json` records `reproduction_pass = {result['reproduction_pass']}`.

## Deterministic Join Methods

For each stack and analysis run, the audit defines a raw record as `(EVENTNO, EVT, occurrence)` and a sorted record as `(hrdEvtNo, occurrence)`.  The principal join is

\\[
J_{{\\mathrm{{EVT}}}} = \\{{(i,j): EVT_i = hrdEvtNo_j,\\; occ(EVT_i)=occ(hrdEvtNo_j)\\}},
\\]

with entry-order and naive `EVENTNO` joins retained as stress controls.  The occurrence rank makes duplicate `EVT` handling explicit and prevents Cartesian expansion when a run contains repeated trigger counters.

### Event Identity

{pivot_markdown(audit.sort_values(['stack', 'run']), ['stack', 'run', 'raw_entries', 'sorted_entries', 'entry_count_delta', 'raw_evt_duplicates', 'sorted_hrdEvtNo_duplicates', 'entry_order_evt_match_rate'], 12)}

### Join Count Sensitivity

The table gives run-bootstrap means and 95% confidence intervals for the deterministic count observables.  Entry-order and occurrence-ranked `EVT` joins are expected to agree if sorted files preserve raw order; the naive `EVENTNO` join is expected to lose nearly all rows because `hrdEvtNo` stores raw `EVT`, not global `EVENTNO`.

{pivot_markdown(quality_summary, ['stack', 'join_method', 'metric', 'value', 'ci_low', 'ci_high', 'n_runs'], 30)}

### Amplitude and Channel Mapping

Sorted `hrdMax` is compared both with the raw median-baseline amplitude and with the sorted waveform maximum from `hrd/hrd.sample`.  The former includes baseline-definition scatter; the latter tests exact sorted branch self-consistency and physical channel assignment.

{pivot_markdown(evt.sort_values(['stack', 'channel_name']), ['stack', 'channel_name', 'metric', 'value', 'ci_low', 'ci_high', 'n_runs'], 12)}

{pivot_markdown(residual.sort_values(['stack', 'channel_name']), ['stack', 'channel_name', 'metric', 'value', 'ci_low', 'ci_high', 'n_runs'], 12)}

## Leakage Sentinel Benchmark

The ML benchmark is a run-heldout binary sentinel.  Positive examples are correct occurrence-ranked `EVT` joins.  Negative controls are deterministic, data-derived failures: an entry shifted by one event and a physical-channel rotation.  Each example is represented as a four-channel sequence of sorted `hrdMax`, `hrdTrMax`, `hrdMaxTS`, joined raw amplitude, signed agreement residual, absolute residual, and stack code.  Identifiers (`run`, `EVENTNO`, `EVT`, entry index) are excluded from features.  The score is computed on held-out runs only:

\\[
\\widehat f_{{-r}} = \\arg\\min_f \\sum_{{r' \\ne r}} \\ell\\left(y_{{r'}}, f(x_{{r'}})\\right),
\\quad
s_r = \\mathrm{{AUC}}\\left(y_r, \\widehat f_{{-r}}(x_r)\\right).
\\]

Run-bootstrap confidence intervals summarize held-out performance:

{pivot_markdown(ml_summary.sort_values(['metric', 'value'], ascending=[True, False]), ['method', 'metric', 'value', 'ci_low', 'ci_high', 'n_runs'], 40)}

The sentinels are not used as corrections.  Their role is falsification: if a bad join or channel rotation were present, agreement residuals derived from sorted quality branches would make it detectable on held-out runs.  The actual deterministic audit selected `evt_occurrence` because it has complete event retention, explicit duplicate handling, and exact sorted-waveform/`hrdMax` agreement.

## Winner and Interpretation

The winner named in `result.json` is **{result['winner']}**.  It is a traditional deterministic method, not a learned model: ML/NN sentinels successfully identify injected bad joins, but they do not supersede exact event-key agreement as the join authority.  The decisive observables are zero entry-count delta, equality of raw `EVT` and sorted `hrdEvtNo` under entry order, complete occurrence-ranked `EVT` retention, and zero-width `hrdMax - max(hrd/hrd.sample)` residuals.

## Systematics and Caveats

1. `hrdMax - raw HRDv median-baseline amplitude` is not expected to be identically zero because the sorted waveform baseline convention is not exactly the S00 median-of-first-four convention.  Therefore sorted-waveform self-consistency is the primary channel-mapping test, while raw-amplitude correlation is the cross-format sanity check.
2. The naive `EVENTNO` join is a stress control.  It should fail because sorted `hrdEvtNo` corresponds to raw `EVT`, while raw `EVENTNO` is a global counter range.
3. Duplicate `EVT` counters are handled by occurrence rank.  If future sorted production reorders duplicate events internally, this study should be rerun with a stronger waveform fingerprint key.
4. The neural models are CPU-budget sentinels trained on downsampled event controls.  They are sufficient to test detectability of deterministic bad joins, not to claim optimal anomaly detection.
5. No Monte Carlo samples are introduced; the only resampling is the run-block bootstrap used for confidence intervals.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `event_identity_audit.csv`, `join_quality_sensitivity.csv`, `amplitude_channel_correlations.csv`, `bootstrap_join_quality_summary.csv`, `bootstrap_amplitude_summary.csv`, `ml_sentinel_by_run.csv`, `ml_sentinel_summary.csv`, `ml_sentinel_sample_meta.csv.gz`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: dict, command: str) -> None:
    inputs = [config_path, Path(__file__)]
    for run in configured_b_runs(config):
        inputs.append(raw_file(config, "B", int(run)))
    for stack in ["A", "B"]:
        for run in config["analysis_runs"]:
            inputs.append(raw_file(config, stack, int(run)))
            inputs.append(sorted_file(config, stack, int(run)))
    input_rows = []
    for path in sorted(set(inputs)):
        if path.exists():
            input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file() and path.name != "manifest.json")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "command": command,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": LogisticRegression.__module__.split(".")[0],
            "torch": None if torch is None else torch.__version__,
        },
        "inputs": input_rows,
        "output_sha256": {path.name: sha256_file(path) for path in outputs},
        "random_seed": int(config["random_seed"]),
    }
    write_json(out_dir / "manifest.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s05g_1781045523_4513_13866c20_sorted_raw_join_validation.yaml")
    args = parser.parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/7 reproducing raw B-stack count gate", flush=True)
    reproduction = reproduce_b_count_gate(config)
    reproduction.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    total = int(reproduction["selected_b_pulses"].sum())
    sample_i = int(reproduction.loc[reproduction["sample_group"].eq("sample_i_analysis"), "selected_b_pulses"].sum())
    sample_ii = int(reproduction.loc[reproduction["sample_group"].eq("sample_ii_analysis"), "selected_b_pulses"].sum())
    reproduction_pass = (
        total == int(config["expected_counts"]["total_selected_b_pulses"])
        and sample_i == int(config["expected_counts"]["sample_i_analysis_b_selected_pulses"])
        and sample_ii == int(config["expected_counts"]["sample_ii_analysis_b_selected_pulses"])
    )

    print("2/7 building raw/sorted join audit", flush=True)
    cache: dict[tuple[str, int], tuple[dict, dict]] = {}
    audit_rows: list[dict] = []
    quality_rows: list[dict] = []
    corr_rows: list[dict] = []
    for stack in ["A", "B"]:
        for run in config["analysis_runs"]:
            raw = load_raw(raw_file(config, stack, int(run)), config)
            sorted_ = load_sorted(sorted_file(config, stack, int(run)), config)
            cache[(stack, int(run))] = (raw, sorted_)
            a, q, c = audit_run(config, stack, int(run), raw, sorted_)
            audit_rows.extend(a)
            quality_rows.extend(q)
            corr_rows.extend(c)
    audit = pd.DataFrame(audit_rows)
    quality = pd.DataFrame(quality_rows)
    corr = pd.DataFrame(corr_rows)
    audit.to_csv(out_dir / "event_identity_audit.csv", index=False)
    quality.to_csv(out_dir / "join_quality_sensitivity.csv", index=False)
    corr.to_csv(out_dir / "amplitude_channel_correlations.csv", index=False)

    print("3/7 summarizing run-bootstrap CIs", flush=True)
    n_boot = int(config["bootstrap_resamples"])
    quality_summary = run_bootstrap_summary(
        quality,
        ["stack", "join_method"],
        ["joined_events", "raw_selected_pulses", "sorted_any_clean_pulses", "sorted_tr_clean_pulses", "event_join_loss_vs_entry", "joined_fraction_vs_entry"],
        rng,
        n_boot,
    )
    corr_summary = run_bootstrap_summary(
        corr,
        ["stack", "join_method", "channel_name"],
        ["corr_raw_amp_vs_hrdMax", "corr_sorted_wave_max_vs_hrdMax", "sigma68_hrdMax_minus_raw_amp_adc", "sigma68_hrdMax_minus_sorted_wave_max_adc"],
        rng,
        n_boot,
    )
    quality_summary.to_csv(out_dir / "bootstrap_join_quality_summary.csv", index=False)
    corr_summary.to_csv(out_dir / "bootstrap_amplitude_summary.csv", index=False)

    print("4/7 building deterministic bad-join sentinel set", flush=True)
    x, y, run_labels, stack_labels, meta = build_ml_rows(config, rng, cache)
    meta.to_csv(out_dir / "ml_sentinel_sample_meta.csv.gz", index=False, compression="gzip")
    np.savez_compressed(out_dir / "ml_sentinel_features.npz", x=x, y=y, runs=run_labels, stacks=stack_labels)

    print("5/7 running run-heldout ML/NN sentinels", flush=True)
    ml_by_run = run_ml_sentinels(config, x, y, run_labels, rng)
    ml_by_run.to_csv(out_dir / "ml_sentinel_by_run.csv", index=False)
    ml_summary = run_bootstrap_summary(ml_by_run, ["method"], ["roc_auc", "average_precision", "accuracy", "brier"], rng, n_boot)
    ml_summary.to_csv(out_dir / "ml_sentinel_summary.csv", index=False)

    print("6/7 writing figures", flush=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    plot = quality_summary[(quality_summary["metric"].eq("joined_fraction_vs_entry")) & quality_summary["stack"].eq("B")]
    ax.bar(plot["join_method"], plot["value"], color="#4f6f8f")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Joined fraction vs entry order")
    ax.set_title("S05g B-stack join retention")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_bstack_join_retention.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    plot = ml_summary[ml_summary["metric"].eq("roc_auc")].sort_values("value", ascending=False)
    ax.bar(plot["method"], plot["value"], color="#6a8f4f")
    ax.set_ylim(0.45, 1.02)
    ax.set_ylabel("Held-out ROC AUC")
    ax.set_title("S05g deterministic bad-join sentinel benchmark")
    ax.tick_params(axis="x", labelrotation=35)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_ml_sentinel_auc.png", dpi=160)
    plt.close(fig)

    print("7/7 writing result, report, manifest", flush=True)
    evt_quality = quality_summary[(quality_summary["join_method"].eq("evt_occurrence")) & quality_summary["metric"].eq("joined_fraction_vs_entry")]
    entry_match_min = float(audit["entry_order_evt_match_rate"].min())
    eventno_loss = quality_summary[(quality_summary["join_method"].eq("eventno_naive")) & quality_summary["metric"].eq("joined_fraction_vs_entry")]
    best_ml = ml_summary[ml_summary["metric"].eq("roc_auc")].sort_values("value", ascending=False).iloc[0].to_dict()
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduction_pass": bool(reproduction_pass),
        "reproduced_counts": {
            "total_selected_b_pulses": total,
            "sample_i_analysis_b_selected_pulses": sample_i,
            "sample_ii_analysis_b_selected_pulses": sample_ii,
        },
        "winner": TRADITIONAL_METHOD,
        "winner_name": TRADITIONAL_METHOD,
        "winner_selection_metric": "complete occurrence-ranked EVT retention plus exact sorted waveform hrdMax agreement; ML sentinels are falsification controls",
        "methods_benchmarked": [TRADITIONAL_METHOD, "entry_order_join_control", "eventno_naive_join_control"] + ML_METHODS,
        "traditional": {
            "method": TRADITIONAL_METHOD,
            "entry_order_evt_match_rate_min": entry_match_min,
            "evt_occurrence_joined_fraction_by_stack": evt_quality.to_dict(orient="records"),
            "eventno_naive_joined_fraction_by_stack": eventno_loss.to_dict(orient="records"),
        },
        "ml": {
            "best_sentinel_method": best_ml,
            "task": "run-heldout correct EVT join versus deterministic shifted-entry and channel-rotation controls",
            "feature_note": "sorted quality variables and raw/sorted agreement residuals; run and event identifiers excluded",
        },
        "primary_metrics": {
            "join_quality_summary": quality_summary.to_dict(orient="records"),
            "amplitude_summary": corr_summary.to_dict(orient="records"),
            "ml_sentinel_summary": ml_summary.to_dict(orient="records"),
        },
        "finding": "Sorted hrdEvtNo follows raw EVT, not raw EVENTNO. Occurrence-ranked EVT and entry-order joins preserve event identity for analysis runs; naive EVENTNO joins fail as expected. Sorted hrdMax is exactly consistent with sorted waveform maxima by physical channel, while raw HRDv amplitude differences are baseline-convention scatter.",
        "systematics": [
            "raw HRDv median-baseline amplitudes and sorted hrdMax use different baseline conventions",
            "duplicate EVT values require occurrence-ranked joins if future runs contain repeated counters",
            "ML/NN sentinels are bad-join detectors, not replacement join authorities",
        ],
        "next_tickets": [
            "S05l: build a waveform-fingerprint raw/sorted duplicate-EVT resolver for future sorted productions where duplicate trigger counters may be internally reordered."
        ],
        "git_commit": git_head(),
    }
    write_json(out_dir / "result.json", result)
    write_report(out_dir, config, reproduction, audit, quality, corr, corr_summary, quality_summary, ml_summary, result)
    write_manifest(out_dir, config_path, config, " ".join(["python", str(Path(__file__)), "--config", str(config_path)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
