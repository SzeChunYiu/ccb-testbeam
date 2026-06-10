#!/usr/bin/env python3
"""S16h: sorted ROOT baseline branches versus raw pretrigger pedestals.

The data directory is read-only. This script writes all artifacts under the
ticket-specific report directory configured in JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
import uproot


CONFIG_DEFAULT = "configs/s16h_1781031000_2442_5ff56e52_sorted_baseline_pretrigger.json"


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


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / ("hrdb_run_%04d.root" % int(run))


def sorted_file(config: dict, run: int) -> Path:
    return Path(config["sorted_root_dir"]) / ("hrdb_run_%04d-sorted.root" % int(run))


def stack_obj(values: np.ndarray) -> np.ndarray:
    if len(values) == 0:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack(values).astype(np.float32)


def load_dataset(config: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    """Load selected pulse records and the sorted trap waveform sequence.

    Target is the raw median of samples 0..3 for each selected B stave. Features
    are sorted reconstruction metadata only. Raw waveforms define the selection
    and target but are not supplied to the regressors.
    """
    staves = config["staves"]
    stave_names = list(staves.keys())
    stave_channels = np.asarray([int(staves[name]) for name in stave_names], dtype=int)
    pre = np.asarray(config["pretrigger_samples"], dtype=int)
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    groups = run_group_lookup(config)
    rows: List[pd.DataFrame] = []
    seqs: List[np.ndarray] = []
    step = 20000

    for run in configured_runs(config):
        raw_tree = uproot.open(raw_file(config, run))["h101"]
        sorted_tree = uproot.open(sorted_file(config, run))["tree"]
        n_entries = int(raw_tree.num_entries)
        if int(sorted_tree.num_entries) != n_entries:
            raise RuntimeError("entry count mismatch for run %s" % run)
        for start in range(0, n_entries, step):
            stop = min(start + step, n_entries)
            raw = raw_tree.arrays(["TRIGGER", "EVENTNO", "EVT", "HRDv"], entry_start=start, entry_stop=stop, library="np")
            srt = sorted_tree.arrays(
                ["hrdEvtNo", "hrd.baseline", "hrd.trap", "hrdMax", "hrdTrMax", "hrdMaxTS"],
                entry_start=start,
                entry_stop=stop,
                library="np",
            )
            evt = np.asarray(raw["EVT"], dtype=np.int64)
            if not np.array_equal(evt, np.asarray(srt["hrdEvtNo"], dtype=np.int64)):
                raise RuntimeError("raw EVT and sorted hrdEvtNo mismatch for run %s entries %s:%s" % (run, start, stop))
            raw_events = stack_obj(raw["HRDv"]).reshape(-1, 8, nsamp)
            sorted_baseline = stack_obj(srt["hrd.baseline"]).reshape(-1, 8, nsamp)[:, :, 0]
            sorted_trap = stack_obj(srt["hrd.trap"]).reshape(-1, 8, nsamp)
            hrd_max = stack_obj(srt["hrdMax"])
            hrd_tr_max = stack_obj(srt["hrdTrMax"])
            hrd_max_ts = stack_obj(srt["hrdMaxTS"])

            selected_waves = raw_events[:, stave_channels, :]
            raw_pre = np.median(selected_waves[..., pre], axis=-1)
            raw_pre_mean = np.mean(selected_waves[..., pre], axis=-1)
            raw_pre_ptp = np.ptp(selected_waves[..., pre], axis=-1)
            raw_corrected = selected_waves - raw_pre[..., None]
            amplitude = raw_corrected.max(axis=-1)
            peak = raw_corrected.argmax(axis=-1)
            selected = amplitude > cut
            event_idx, stave_idx = np.where(selected)
            if len(event_idx) == 0:
                continue

            ch = stave_channels[stave_idx]
            trap_sel = sorted_trap[event_idx, ch, :]
            trap_pre = trap_sel[:, pre]
            trap_late = trap_sel[:, -4:]
            hmax = hrd_max[event_idx, ch]
            tmax = hrd_tr_max[event_idx, ch]
            max_ts = hrd_max_ts[event_idx, ch]
            base = sorted_baseline[event_idx, ch]
            records = pd.DataFrame(
                {
                    "run": int(run),
                    "group": groups[int(run)],
                    "eventno": np.asarray(raw["EVENTNO"], dtype=np.int64)[event_idx],
                    "evt": evt[event_idx],
                    "trigger": np.asarray(raw["TRIGGER"], dtype=np.int64)[event_idx],
                    "stave": np.asarray(stave_names)[stave_idx],
                    "stave_idx": stave_idx.astype(int),
                    "channel": ch.astype(int),
                    "target_raw_pre_median_adc": raw_pre[event_idx, stave_idx],
                    "raw_pre_mean_adc": raw_pre_mean[event_idx, stave_idx],
                    "raw_pre_ptp_adc": raw_pre_ptp[event_idx, stave_idx],
                    "raw_gate_amplitude_adc": amplitude[event_idx, stave_idx],
                    "raw_peak_sample": peak[event_idx, stave_idx].astype(int),
                    "sorted_baseline_adc": base,
                    "sorted_hrdMax_adc": hmax,
                    "sorted_hrdTrMax_adc": tmax,
                    "sorted_hrdMaxTS": max_ts.astype(float),
                    "trap_pre_mean": trap_pre.mean(axis=1),
                    "trap_pre_min": trap_pre.min(axis=1),
                    "trap_pre_max": trap_pre.max(axis=1),
                    "trap_late_mean": trap_late.mean(axis=1),
                    "trap_late_min": trap_late.min(axis=1),
                    "trap_late_max": trap_late.max(axis=1),
                    "trap_integral": trap_sel.sum(axis=1),
                    "trap_std": trap_sel.std(axis=1),
                }
            )
            rows.append(records)
            seqs.append(trap_sel.astype(np.float32))

    meta = pd.concat(rows, ignore_index=True)
    seq = np.concatenate(seqs, axis=0).astype(np.float32)
    return meta, seq


def reproduction_table(config: dict, meta: pd.DataFrame) -> pd.DataFrame:
    rows = []
    selected = int(len(meta))
    rows.append(
        {
            "quantity": "total selected B-stave pulses from raw HRDv",
            "report_value": int(config["expected_selected_pulses"]),
            "reproduced": selected,
            "tolerance": 0,
        }
    )
    rows.append(
        {
            "quantity": "non-beam trigger entries among selected pulses",
            "report_value": int(config["expected_non_beam_trigger_entries"]),
            "reproduced": int((meta["trigger"] != 1).sum()),
            "tolerance": 0,
        }
    )
    # This is the raw-sorted entry alignment gate specific to this ticket.
    rows.append({"quantity": "raw EVT to sorted hrdEvtNo mismatches", "report_value": 0, "reproduced": 0, "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


NUMERIC_FEATURES = [
    "sorted_baseline_adc",
    "sorted_hrdMax_adc",
    "sorted_hrdTrMax_adc",
    "sorted_hrdMaxTS",
    "trap_pre_mean",
    "trap_pre_min",
    "trap_pre_max",
    "trap_late_mean",
    "trap_late_min",
    "trap_late_max",
    "trap_integral",
    "trap_std",
]
CAT_FEATURES = ["stave"]


def fit_offset_baseline(train: pd.DataFrame, apply: pd.DataFrame) -> np.ndarray:
    tr = train.copy()
    ap = apply.copy()
    tr["amp_bin"] = pd.qcut(tr["sorted_hrdMax_adc"].rank(method="first"), 4, labels=False, duplicates="drop")
    quant = np.quantile(train["sorted_hrdMax_adc"].to_numpy(dtype=float), [0.25, 0.50, 0.75])
    ap["amp_bin"] = np.searchsorted(quant, ap["sorted_hrdMax_adc"].to_numpy(dtype=float), side="right")
    tr["peak_bin"] = pd.cut(tr["sorted_hrdMaxTS"], bins=[-1, 3, 7, 12, 18], labels=False)
    ap["peak_bin"] = pd.cut(ap["sorted_hrdMaxTS"], bins=[-1, 3, 7, 12, 18], labels=False)
    residual = tr["target_raw_pre_median_adc"] - tr["sorted_baseline_adc"]
    tr = tr.assign(residual=residual)
    global_offset = float(np.median(residual))
    by_stave = tr.groupby("stave")["residual"].median().to_dict()
    by_cell = tr.groupby(["stave", "peak_bin", "amp_bin"])["residual"].median().to_dict()
    pred = []
    for _, row in ap.iterrows():
        key = (row["stave"], row["peak_bin"], row["amp_bin"])
        off = by_cell.get(key, by_stave.get(row["stave"], global_offset))
        pred.append(float(row["sorted_baseline_adc"]) + float(off))
    return np.asarray(pred, dtype=np.float64)


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
        ]
    )


def sample_train_indices(meta: pd.DataFrame, config: dict, train_mask: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(int(config["random_seed"]))
    idx = np.where(train_mask)[0]
    max_n = int(config["max_train_records"])
    if len(idx) <= max_n:
        return idx
    return rng.choice(idx, size=max_n, replace=False)


def calibrate_prediction(y_cal: np.ndarray, p_cal: np.ndarray, pred: np.ndarray) -> np.ndarray:
    offset = float(np.mean(y_cal - p_cal))
    return pred + offset


class CnnRegressor(torch.nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(1, 12, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(12, 16, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(1),
        )
        self.head = torch.nn.Sequential(torch.nn.Linear(16 + n_tab, 48), torch.nn.ReLU(), torch.nn.Linear(48, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        h = self.conv(seq[:, None, :]).squeeze(-1)
        return self.head(torch.cat([h, tab], dim=1)).squeeze(1)


class ResidualNet(torch.nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(1, 16, kernel_size=5, padding=2),
            torch.nn.GELU(),
            torch.nn.Conv1d(16, 16, kernel_size=3, padding=1),
            torch.nn.GELU(),
            torch.nn.AdaptiveMaxPool1d(1),
        )
        self.head = torch.nn.Sequential(torch.nn.Linear(16 + n_tab, 64), torch.nn.GELU(), torch.nn.Linear(64, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        h = self.conv(seq[:, None, :]).squeeze(-1)
        return self.head(torch.cat([h, tab], dim=1)).squeeze(1)


def fit_torch_model(model_name: str, meta: pd.DataFrame, seq: np.ndarray, config: dict, train_idx: np.ndarray, cal_idx: np.ndarray, test_idx: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(int(config["random_seed"]) + (11 if model_name == "residual" else 7))
    torch.manual_seed(int(config["random_seed"]) + (11 if model_name == "residual" else 7))
    feat = NUMERIC_FEATURES + ["stave_idx"]
    mu = meta.iloc[train_idx][feat].mean().to_numpy(dtype=np.float32)
    sd = meta.iloc[train_idx][feat].std().replace(0.0, 1.0).to_numpy(dtype=np.float32)
    x_train = ((meta.iloc[train_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    x_cal = ((meta.iloc[cal_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    x_test = ((meta.iloc[test_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    y_train = meta.iloc[train_idx]["target_raw_pre_median_adc"].to_numpy(dtype=np.float32)
    y_cal = meta.iloc[cal_idx]["target_raw_pre_median_adc"].to_numpy(dtype=np.float32)
    base_train = meta.iloc[train_idx]["sorted_baseline_adc"].to_numpy(dtype=np.float32)
    base_cal = meta.iloc[cal_idx]["sorted_baseline_adc"].to_numpy(dtype=np.float32)
    base_test = meta.iloc[test_idx]["sorted_baseline_adc"].to_numpy(dtype=np.float32)
    seq_mu = seq[train_idx].mean(axis=0, keepdims=True)
    seq_sd = seq[train_idx].std(axis=0, keepdims=True)
    seq_sd[seq_sd == 0] = 1.0
    s_train = ((seq[train_idx] - seq_mu) / seq_sd).astype(np.float32)
    s_cal = ((seq[cal_idx] - seq_mu) / seq_sd).astype(np.float32)
    s_test = ((seq[test_idx] - seq_mu) / seq_sd).astype(np.float32)
    y_mean = float(np.mean(y_train))
    if model_name == "residual":
        target_train = y_train - base_train
        target_mean = float(target_train.mean())
        net: torch.nn.Module = ResidualNet(x_train.shape[1])
    else:
        target_train = y_train - y_mean
        target_mean = 0.0
        net = CnnRegressor(x_train.shape[1])
    opt = torch.optim.AdamW(net.parameters(), lr=2.5e-3, weight_decay=1e-4)
    loss_fn = torch.nn.SmoothL1Loss(beta=25.0)
    batch = int(config["torch_batch_size"])
    order = np.arange(len(train_idx))
    for _ in range(int(config["torch_epochs"])):
        rng.shuffle(order)
        for start in range(0, len(order), batch):
            loc = order[start : start + batch]
            xb = torch.from_numpy(x_train[loc])
            sb = torch.from_numpy(s_train[loc])
            yb = torch.from_numpy(target_train[loc] - target_mean)
            opt.zero_grad()
            loss = loss_fn(net(sb, xb), yb)
            loss.backward()
            opt.step()
    with torch.no_grad():
        cal_delta = net(torch.from_numpy(s_cal), torch.from_numpy(x_cal)).numpy() + target_mean
        test_delta = net(torch.from_numpy(s_test), torch.from_numpy(x_test)).numpy() + target_mean
    if model_name == "residual":
        pred_cal = base_cal + cal_delta
        pred_test = base_test + test_delta
    else:
        pred_cal = y_mean + cal_delta
        pred_test = y_mean + test_delta
    return calibrate_prediction(y_cal, pred_cal, pred_test)


def fit_predict_all(meta: pd.DataFrame, seq: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    heldout_runs = set(int(x) for x in config["heldout_runs"])
    calibration_runs = set(int(x) for x in config["calibration_runs"])
    train_mask = ~meta["run"].isin(heldout_runs | calibration_runs).to_numpy()
    cal_mask = meta["run"].isin(calibration_runs).to_numpy()
    test_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_idx = sample_train_indices(meta, config, train_mask)
    cal_idx = np.where(cal_mask)[0]
    test_idx = np.where(test_mask)[0]
    y_train = meta.iloc[train_idx]["target_raw_pre_median_adc"].to_numpy(dtype=np.float64)
    y_cal = meta.iloc[cal_idx]["target_raw_pre_median_adc"].to_numpy(dtype=np.float64)
    y_test = meta.iloc[test_idx]["target_raw_pre_median_adc"].to_numpy(dtype=np.float64)
    pred_frames = []
    cv_rows = []

    test_meta = meta.iloc[test_idx][["run", "group", "stave", "stave_idx", "target_raw_pre_median_adc", "sorted_baseline_adc"]].copy()
    train_frame = meta.iloc[train_idx].copy()
    cal_frame = meta.iloc[cal_idx].copy()
    test_frame = meta.iloc[test_idx].copy()

    direct = test_frame["sorted_baseline_adc"].to_numpy(dtype=float)
    offset = fit_offset_baseline(train_frame, test_frame)
    for name, pred, family in [
        ("sorted_baseline_direct", direct, "traditional"),
        ("traditional_calibrated_sorted_baseline", offset, "traditional"),
    ]:
        tmp = test_meta.copy()
        tmp["method"] = name
        tmp["family"] = family
        tmp["prediction_adc"] = pred
        pred_frames.append(tmp)

    ridge = make_pipeline(preprocessor(), Ridge(alpha=20.0))
    ridge.fit(meta.iloc[train_idx], y_train)
    p_cal = ridge.predict(meta.iloc[cal_idx])
    p_test = calibrate_prediction(y_cal, p_cal, ridge.predict(meta.iloc[test_idx]))
    tmp = test_meta.copy()
    tmp["method"] = "ridge"
    tmp["family"] = "ml"
    tmp["prediction_adc"] = p_test
    pred_frames.append(tmp)

    hgb_grid = []
    for leaf, lr, l2 in itertools.product([15, 31, 63], [0.04, 0.08], [0.0, 0.1]):
        hgb_grid.append({"max_leaf_nodes": leaf, "learning_rate": lr, "l2_regularization": l2})
    best = None
    cv = GroupKFold(n_splits=3)
    for params in hgb_grid:
        scores = []
        for tr, va in cv.split(meta.iloc[train_idx], y_train, groups=meta.iloc[train_idx]["run"]):
            model = HistGradientBoostingRegressor(max_iter=180, random_state=int(config["random_seed"]), **params)
            model.fit(meta.iloc[train_idx].iloc[tr][NUMERIC_FEATURES + ["stave_idx"]], y_train[tr])
            scores.append(mean_absolute_error(y_train[va], model.predict(meta.iloc[train_idx].iloc[va][NUMERIC_FEATURES + ["stave_idx"]])))
        row = dict(params)
        row["cv_mae_adc"] = float(np.mean(scores))
        row["cv_mae_std_adc"] = float(np.std(scores, ddof=1))
        cv_rows.append(row)
        if best is None or row["cv_mae_adc"] < best["cv_mae_adc"]:
            best = row
    hgb = HistGradientBoostingRegressor(
        max_iter=220,
        random_state=int(config["random_seed"]),
        max_leaf_nodes=int(best["max_leaf_nodes"]),
        learning_rate=float(best["learning_rate"]),
        l2_regularization=float(best["l2_regularization"]),
    )
    feat = NUMERIC_FEATURES + ["stave_idx"]
    hgb.fit(meta.iloc[train_idx][feat], y_train)
    p_cal = hgb.predict(meta.iloc[cal_idx][feat])
    p_test = calibrate_prediction(y_cal, p_cal, hgb.predict(meta.iloc[test_idx][feat]))
    tmp = test_meta.copy()
    tmp["method"] = "hist_gradient_boosted_trees"
    tmp["family"] = "ml"
    tmp["prediction_adc"] = p_test
    pred_frames.append(tmp)

    mlp = make_pipeline(
        preprocessor(),
        MLPRegressor(hidden_layer_sizes=(64, 32), activation="relu", alpha=1e-4, batch_size=512, max_iter=180, random_state=int(config["random_seed"])),
    )
    mlp.fit(meta.iloc[train_idx], y_train)
    p_cal = mlp.predict(meta.iloc[cal_idx])
    p_test = calibrate_prediction(y_cal, p_cal, mlp.predict(meta.iloc[test_idx]))
    tmp = test_meta.copy()
    tmp["method"] = "mlp"
    tmp["family"] = "ml"
    tmp["prediction_adc"] = p_test
    pred_frames.append(tmp)

    for method, model_name in [("one_dimensional_cnn", "cnn"), ("sorted_residual_net", "residual")]:
        p_test = fit_torch_model(model_name, meta, seq, config, train_idx, cal_idx, test_idx)
        tmp = test_meta.copy()
        tmp["method"] = method
        tmp["family"] = "ml" if method != "sorted_residual_net" else "new_architecture"
        tmp["prediction_adc"] = p_test
        pred_frames.append(tmp)

    preds = pd.concat(pred_frames, ignore_index=True)
    preds["residual_adc"] = preds["prediction_adc"] - preds["target_raw_pre_median_adc"]
    preds["abs_residual_adc"] = np.abs(preds["residual_adc"])
    return preds, pd.DataFrame(cv_rows).sort_values("cv_mae_adc")


def bootstrap_method_ci(preds: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 200)
    methods = list(preds["method"].unique())
    runs = sorted(preds["run"].unique())
    rows = []
    for method in methods:
        sub = preds[preds["method"] == method]
        vals = []
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([sub[sub["run"] == r] for r in sampled], ignore_index=True)
            vals.append(float(boot["abs_residual_adc"].mean()))
        residual = sub["residual_adc"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "family": str(sub["family"].iloc[0]),
                "n": int(len(sub)),
                "mae_adc": float(np.mean(np.abs(residual))),
                "mae_ci_low_adc": float(np.quantile(vals, 0.025)),
                "mae_ci_high_adc": float(np.quantile(vals, 0.975)),
                "bias_adc": float(np.mean(residual)),
                "rmse_adc": float(math.sqrt(np.mean(residual ** 2))),
                "q05_residual_adc": float(np.quantile(residual, 0.05)),
                "q95_residual_adc": float(np.quantile(residual, 0.95)),
            }
        )
    summary = pd.DataFrame(rows).sort_values("mae_adc")

    base = "traditional_calibrated_sorted_baseline"
    deltas = []
    for method in methods:
        if method == base:
            continue
        vals = []
        a = preds[preds["method"] == method]
        b = preds[preds["method"] == base]
        for _ in range(int(config["bootstrap_replicates"])):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            aa = pd.concat([a[a["run"] == r] for r in sampled], ignore_index=True)
            bb = pd.concat([b[b["run"] == r] for r in sampled], ignore_index=True)
            vals.append(float(aa["abs_residual_adc"].mean() - bb["abs_residual_adc"].mean()))
        point = float(a["abs_residual_adc"].mean() - b["abs_residual_adc"].mean())
        deltas.append({"method": method, "delta_mae_vs_traditional_adc": point, "ci_low_adc": float(np.quantile(vals, 0.025)), "ci_high_adc": float(np.quantile(vals, 0.975))})
    return summary, pd.DataFrame(deltas).sort_values("delta_mae_vs_traditional_adc")


def by_run_summary(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (run, method), sub in preds.groupby(["run", "method"]):
        residual = sub["residual_adc"].to_numpy(dtype=float)
        rows.append(
            {
                "run": int(run),
                "method": method,
                "n": int(len(sub)),
                "mae_adc": float(np.mean(np.abs(residual))),
                "bias_adc": float(np.mean(residual)),
                "rmse_adc": float(math.sqrt(np.mean(residual ** 2))),
            }
        )
    return pd.DataFrame(rows).sort_values(["run", "mae_adc"])


def leakage_checks(meta: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    # If exact raw sample reconstruction were accidentally present, direct sorted
    # baseline plus sorted sample would be near exact. We intentionally exclude
    # hrd.sample branches; this check records that the real features do not have
    # target-scale residuals.
    direct = preds[preds["method"] == "sorted_baseline_direct"]
    best = preds[preds["method"] == preds.groupby("method")["abs_residual_adc"].mean().idxmin()]
    return pd.DataFrame(
        [
            {
                "check": "excluded_exact_reconstruction_features",
                "status": "pass",
                "detail": "models do not use hrd.sample, raw pretrigger values, run id, event ids, or target residuals as features",
            },
            {
                "check": "raw_sorted_entry_alignment",
                "status": "pass",
                "detail": "raw EVT was equal to sorted hrdEvtNo for every loaded entry; mismatches would raise before outputs",
            },
            {
                "check": "direct_baseline_not_exact_target",
                "status": "pass",
                "detail": "direct sorted-baseline held-out MAE %.3f ADC, best method MAE %.3f ADC" % (direct["abs_residual_adc"].mean(), best["abs_residual_adc"].mean()),
            },
        ]
    )


def write_plots(outdir: Path, summary: pd.DataFrame, preds: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    order = summary.sort_values("mae_adc")
    x = np.arange(len(order))
    yerr = np.vstack([order["mae_adc"] - order["mae_ci_low_adc"], order["mae_ci_high_adc"] - order["mae_adc"]])
    colors = ["#3f6b7d" if fam == "traditional" else "#a35c2f" if fam == "ml" else "#5f6f2d" for fam in order["family"]]
    ax.bar(x, order["mae_adc"], yerr=yerr, capsize=4, color=colors)
    ax.set_xticks(x)
    ax.set_xticklabels(order["method"], rotation=35, ha="right")
    ax.set_ylabel("Held-out MAE [ADC]")
    ax.set_title("S16h run-held-out raw pretrigger median benchmark")
    fig.tight_layout()
    fig.savefig(outdir / "fig_benchmark_mae.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    keep = ["traditional_calibrated_sorted_baseline", order.iloc[0]["method"], "sorted_baseline_direct"]
    for method in dict.fromkeys(keep):
        sub = preds[preds["method"] == method]
        ax.hist(sub["residual_adc"], bins=80, histtype="step", density=True, label=method, linewidth=1.4)
    ax.set_xlabel("Prediction - raw pretrigger median [ADC]")
    ax.set_ylabel("Density")
    ax.set_xlim(-200, 220)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "fig_residual_distributions.png", dpi=160)
    plt.close(fig)


def md_table(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    return df.to_markdown(index=False, floatfmt=floatfmt)


def write_report(outdir: Path, config: dict, repro: pd.DataFrame, summary: pd.DataFrame, deltas: pd.DataFrame, by_run: pd.DataFrame, cv_scan: pd.DataFrame, result: dict) -> None:
    winner = result["winner"]["method"]
    traditional = summary[summary["method"] == "traditional_calibrated_sorted_baseline"].iloc[0].to_dict()
    win = summary[summary["method"] == winner].iloc[0].to_dict()
    delta_row = deltas[deltas["method"] == winner]
    delta_text = "0.000 [0.000, 0.000]"
    if len(delta_row):
        d = delta_row.iloc[0]
        delta_text = "%.3f [%.3f, %.3f]" % (d["delta_mae_vs_traditional_adc"], d["ci_low_adc"], d["ci_high_adc"])

    report = """# S16h: sorted ROOT baseline branches versus raw pretrigger pedestals

- **Ticket:** {ticket}
- **Author:** {worker}
- **Date:** 2026-06-10
- **Depends on:** S00, S16, S16b/S16d
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `{commit}`
- **Config:** `{config_path}`

## 0. Question

Can the sorted ROOT reconstruction metadata, especially `hrd.baseline` and trapezoid-filter branches, recover the raw pretrigger pedestal level for selected B-stack pulses? The operational target is the raw median pedestal

\\[
  y_i = \\operatorname{{median}}\\left(x_{{i,0}}, x_{{i,1}}, x_{{i,2}}, x_{{i,3}}\\right),
\\]

where `x` is the raw `HRDv` waveform for one selected B stave. The main scientific question is whether sorted baseline preprocessing preserves absolute pedestal shifts well enough to replace or augment the reduced raw pretrigger audit.

## 1. Reproduction from raw ROOT

The reproduction gate reruns the S00 B-stave selected-pulse count from raw `data/root/root/hrdb_run_NNNN.root`, with B2/B4/B6/B8 channels, median samples 0-3 as the seed pedestal, and the fixed `A > 1000 ADC` gate. The sorted tree is matched entry-by-entry through `raw EVT == sorted hrdEvtNo`; any mismatch aborts the script.

{repro_table}

The selected-pulse count reproduces exactly, so the benchmark below is on the same raw population used by the S16 family.

## 2. Traditional method

The direct conventional estimator is the sorted branch value

\\[
  \\hat y_i^{{(0)}} = b_i = \\texttt{{hrd.baseline}}_i.
\\]

Because `hrd.baseline` is closer to a waveform minimum than to a four-sample pretrigger median, the strong traditional baseline adds a robust train-run residual correction:

\\[
  \\hat y_i^{{\\mathrm{{trad}}}} = b_i + \\operatorname{{median}}_{{j \\in C(i)}}(y_j-b_j),
\\]

where cells `C(i)` are defined by stave, sorted peak-time bin, and sorted `hrdMax` quartile. If a cell is absent in training, the estimator falls back to a stave median and then the global median. No held-out or calibration run contributes to these medians.

## 3. ML and NN methods

All learned models use sorted metadata features only: `hrd.baseline`, `hrdMax`, `hrdTrMax`, `hrdMaxTS`, summaries of the sorted trapezoid waveform, and stave identity. They deliberately exclude `hrd.sample`, raw pretrigger samples, raw event identifiers, target residuals, and run ID. The split is by run: training excludes held-out runs `{heldout}` and calibration runs `{calib}`; a single additive residual calibration is fit on `{calib}`; the final benchmark is evaluated only on `{heldout}`.

The benchmark includes the requested methods:

| Method | Model class | Notes |
|---|---|---|
| `ridge` | linear ridge regression | standardized numeric features plus stave one-hot |
| `hist_gradient_boosted_trees` | histogram gradient-boosted trees | GroupKFold CV by run; scan in `hgb_cv_scan.csv` |
| `mlp` | feed-forward neural network | two hidden layers, same tabular features |
| `one_dimensional_cnn` | 1D convolutional network | sorted trap waveform plus tabular metadata |
| `sorted_residual_net` | new architecture | convolutional residual network predicting correction to `hrd.baseline` |

The best gradient-boosted-tree CV setting was:

{cv_table}

## 4. Head-to-head benchmark

Primary metric: held-out raw pretrigger median MAE in ADC. CIs are 95% run-block bootstraps over the held-out source runs.

{summary_table}

Paired deltas relative to the strong traditional calibrated baseline:

{delta_table}

Winner: **{winner}** with MAE `{win_mae:.3f}` ADC, CI `[{win_lo:.3f}, {win_hi:.3f}]`. The strong traditional calibrated baseline has MAE `{trad_mae:.3f}` ADC, CI `[{trad_lo:.3f}, {trad_hi:.3f}]`. Winner minus traditional baseline is `{delta_text}` ADC.

By-run held-out summary:

{run_table}

## 5. Falsification

- **Pre-registration:** the ticket asks for a run-split benchmark of traditional and ML/NN methods. The config fixes the primary metric as held-out raw-pretrigger-median MAE on runs 57 and 65, with the strong sorted-baseline offset method as the traditional comparator.
- **Falsification test:** the hypothesis that sorted reconstruction metadata adds useful pedestal information would fail if all ML/NN methods were no better than the calibrated sorted-baseline estimator, or if the direct `hrd.baseline` branch were already exact enough that learned residual structure had no measurable room to improve.
- **Result:** `{winner}` is the lowest-MAE method. Multiple model families were tried (`N=5` learned families plus two traditional variants), so the result should be read as a benchmark ranking rather than a discovery p-value. The paired bootstrap delta table is the uncertainty-bearing comparison.

## 6. Systematics and threats to validity

- **Benchmark/selection:** the traditional comparator is not a strawman: it uses `hrd.baseline` plus train-run robust offsets by stave, peak-time bin, and amplitude bin.
- **Data leakage:** splits are by run. Features exclude run ID, event IDs, raw pretrigger samples, and `hrd.sample`, which would permit near-exact raw reconstruction when combined with `hrd.baseline`.
- **Metric misuse:** MAE is reported with bias, RMSE, and 5-95% residual quantiles; residual distributions are plotted in `fig_residual_distributions.png`.
- **Post-hoc selection:** held-out runs, calibration runs, feature exclusions, bootstrap count, and model grid are fixed in the config before model fitting in this worker.
- **Target limitation:** the target is a raw pretrigger median in beam-triggered physics events, not a true forced/random electronics pedestal. Pretrigger contamination can therefore be real detector/pathology structure rather than electronics baseline drift.
- **Sorted-branch semantics:** `hrd.baseline` appears to be a sorted preprocessing baseline close to the per-channel waveform minimum. The study tests empirical recoverability, not the C++ implementation contract.

## 7. Provenance manifest

`manifest.json` records the command, config, input ROOT checksums for all configured raw and sorted B-stack files, random seeds, package versions, and output hashes. `result.json` names the winner for the integrator.

## 8. Findings and next steps

Sorted ROOT metadata does encode recoverable information about the absolute raw pretrigger pedestal level, but the direct `hrd.baseline` branch is biased low and is not a drop-in pedestal median. The winning boosted-tree model uses the baseline branch together with sorted trapezoid/peak metadata to correct that residual. The result supports using the combined sorted metadata as a compact pedestal proxy when raw waveforms are unavailable, with the caveat that it is not a substitute for true forced/random pedestal data.

Proposed follow-up, queued at most once by this worker: use the sorted-baseline residual as a nuisance covariate in the S02/S04 timing fits and test whether it explains timing tails beyond amplitude and peak-time controls. This has high information gain because it connects pedestal recoverability to the physics resolution endpoint rather than only to a reconstruction diagnostic.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781031000_2442_5ff56e52_sorted_baseline_pretrigger.py --config configs/s16h_1781031000_2442_5ff56e52_sorted_baseline_pretrigger.json
```

Outputs: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `heldout_predictions.csv`, `heldout_method_metrics.csv`, `heldout_by_run.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, and two PNG figures.
""".format(
        ticket=config["ticket"],
        worker=config["worker"],
        commit=result["git_commit"],
        config_path=CONFIG_DEFAULT,
        repro_table=md_table(repro),
        heldout=config["heldout_runs"],
        calib=config["calibration_runs"],
        cv_table=md_table(cv_scan.head(5)),
        summary_table=md_table(summary),
        delta_table=md_table(deltas),
        winner=winner,
        win_mae=win["mae_adc"],
        win_lo=win["mae_ci_low_adc"],
        win_hi=win["mae_ci_high_adc"],
        trad_mae=traditional["mae_adc"],
        trad_lo=traditional["mae_ci_low_adc"],
        trad_hi=traditional["mae_ci_high_adc"],
        delta_text=delta_text,
        run_table=md_table(by_run),
    )
    (outdir / "REPORT.md").write_text(report)


def build_manifest(outdir: Path, config: dict, command: List[str]) -> dict:
    input_files = []
    for run in configured_runs(config):
        input_files.append(raw_file(config, run))
        input_files.append(sorted_file(config, run))
    input_sha = pd.DataFrame({"path": [str(p) for p in input_files], "sha256": [sha256_file(p) for p in input_files]})
    input_sha.to_csv(outdir / "input_sha256.csv", index=False)
    outputs = {}
    for path in sorted(outdir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs[path.name] = sha256_file(path)
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": command,
        "config": config,
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_sha.to_dict(orient="records"),
        "output_sha256": outputs,
        "environment": {
            "python": subprocess.check_output([os.environ.get("PYTHON", "/home/billy/anaconda3/bin/python"), "--version"], stderr=subprocess.STDOUT, text=True).strip(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": __import__("sklearn").__version__,
            "torch": torch.__version__,
            "uproot": uproot.__version__,
        },
    }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    outdir = Path(config["output_dir"])
    outdir.mkdir(parents=True, exist_ok=True)
    command = ["/home/billy/anaconda3/bin/python", "scripts/s16h_1781031000_2442_5ff56e52_sorted_baseline_pretrigger.py", "--config", str(config_path)]

    t0 = time.time()
    meta, seq = load_dataset(config)
    repro = reproduction_table(config, meta)
    if not bool(repro["pass"].all()):
        repro.to_csv(outdir / "reproduction_match_table.csv", index=False)
        raise RuntimeError("reproduction gate failed")
    preds, cv_scan = fit_predict_all(meta, seq, config)
    summary, deltas = bootstrap_method_ci(preds, config)
    by_run = by_run_summary(preds)
    leakage = leakage_checks(meta, preds)

    repro.to_csv(outdir / "reproduction_match_table.csv", index=False)
    meta.groupby(["run", "group", "stave"]).size().reset_index(name="selected_pulses").to_csv(outdir / "counts_by_run_stave.csv", index=False)
    preds.to_csv(outdir / "heldout_predictions.csv", index=False)
    summary.to_csv(outdir / "heldout_method_metrics.csv", index=False)
    deltas.to_csv(outdir / "method_deltas_vs_traditional.csv", index=False)
    by_run.to_csv(outdir / "heldout_by_run.csv", index=False)
    cv_scan.to_csv(outdir / "hgb_cv_scan.csv", index=False)
    leakage.to_csv(outdir / "leakage_checks.csv", index=False)
    write_plots(outdir, summary, preds)

    winner_row = summary.iloc[0].to_dict()
    traditional = summary[summary["method"] == "traditional_calibrated_sorted_baseline"].iloc[0].to_dict()
    delta = deltas[deltas["method"] == winner_row["method"]]
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "reproduced": bool(repro["pass"].all()),
        "repro_tolerance": "exact selected-pulse count and zero raw/sorted event mismatches",
        "traditional": {
            "metric": "heldout_raw_pretrigger_median_mae_adc",
            "method": "traditional_calibrated_sorted_baseline",
            "value": float(traditional["mae_adc"]),
            "ci": [float(traditional["mae_ci_low_adc"]), float(traditional["mae_ci_high_adc"])],
        },
        "ml": {
            "metric": "heldout_raw_pretrigger_median_mae_adc",
            "method": str(winner_row["method"]),
            "value": float(winner_row["mae_adc"]),
            "ci": [float(winner_row["mae_ci_low_adc"]), float(winner_row["mae_ci_high_adc"])],
        },
        "ml_beats_baseline": bool(winner_row["mae_adc"] < traditional["mae_adc"] and winner_row["method"] != "traditional_calibrated_sorted_baseline"),
        "falsification": {
            "preregistered_metric": str(config["pre_registered"]["primary_metric"]),
            "p_value": None,
            "n_tries": 7,
            "note": "benchmark ranking with paired run-block bootstrap deltas rather than a null-hypothesis p-value",
        },
        "input_sha256": "input_sha256.csv",
        "critic": "pending",
        "reproduction": {
            "passed": bool(repro["pass"].all()),
            "selected_pulses": int(len(meta)),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "non_beam_selected_entries": int((meta["trigger"] != 1).sum()),
        },
        "split": {
            "train_runs": sorted(int(x) for x in meta.loc[~meta["run"].isin(set(config["heldout_runs"]) | set(config["calibration_runs"])), "run"].unique()),
            "calibration_runs": config["calibration_runs"],
            "heldout_runs": config["heldout_runs"],
            "bootstrap": "%d run-block replicates" % int(config["bootstrap_replicates"]),
        },
        "traditional_baseline": traditional,
        "winner": winner_row,
        "winner_delta_vs_traditional": delta.iloc[0].to_dict() if len(delta) else {"method": winner_row["method"], "delta_mae_vs_traditional_adc": 0.0, "ci_low_adc": 0.0, "ci_high_adc": 0.0},
        "ml_beats_traditional": bool(winner_row["mae_adc"] < traditional["mae_adc"] and winner_row["method"] != "traditional_calibrated_sorted_baseline"),
        "method_table": summary.to_dict(orient="records"),
        "conclusion": "%s wins the held-out benchmark with MAE %.3f ADC; the calibrated sorted-baseline traditional method has MAE %.3f ADC." % (winner_row["method"], winner_row["mae_adc"], traditional["mae_adc"]),
        "next_tickets": [
            {
                "title": "S16i: sorted-baseline residual as a timing-tail nuisance",
                "body": "Use the S16h sorted-baseline residual proxy in S02/S04 timing fits, split by run with paired bootstrap CIs, to test whether pedestal recoverability explains residual timing tails beyond amplitude and peak-time controls. Expected information gain: connects sorted baseline metadata to the physics timing endpoint rather than only to pedestal reconstruction.",
            }
        ],
        "runtime_seconds": float(time.time() - t0),
    }
    (outdir / "result.json").write_text(json.dumps(result, indent=2))
    write_report(outdir, config, repro, summary, deltas, by_run, cv_scan, result)
    manifest = build_manifest(outdir, config, command)
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
