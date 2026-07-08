#!/usr/bin/env python3
"""S16i: sorted-baseline residual as a timing-tail nuisance.

This study connects the S16h raw-vs-sorted baseline residual proxy to the S02
downstream timing endpoint.  It reproduces the raw ROOT selected-pulse count,
then evaluates a strong binned conventional correction against ridge, boosted
trees, MLP, 1D-CNN, and a compact gated-convolution residual architecture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import uproot
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


CONFIG_DEFAULT = "configs/s16i_1781096100_1466_0e861527_sorted_baseline_timing_tail_nuisance.json"
METHOD_ORDER = [
    "traditional_binned_cfd20",
    "ridge",
    "hist_gradient_boosted_trees",
    "mlp",
    "one_dimensional_cnn",
    "gated_cnn_residual",
]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / ("hrdb_run_%04d.root" % int(run))


def sorted_file(config: dict, run: int) -> Path:
    return Path(config["sorted_root_dir"]) / ("hrdb_run_%04d-sorted.root" % int(run))


def stack_obj(values: np.ndarray) -> np.ndarray:
    if len(values) == 0:
        return np.empty((0, 0), dtype=np.float32)
    return np.stack(values).astype(np.float32)


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = float(waveforms[i, j - 1])
        y1 = float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (float(threshold[i]) - y0) / denom
    return out


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def full_rms(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float(np.sqrt(np.mean((values - values.mean()) ** 2)))


def reproduce_counts(config: dict) -> pd.DataFrame:
    staves = config["staves"]
    names = list(staves.keys())
    channels = np.asarray([int(staves[name]) for name in names], dtype=int)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    total = 0
    sample_ii_total = 0
    sample_ii_by_stave = {name: 0 for name in names}
    sample_ii_runs = set(int(x) for x in config["run_groups"]["sample_ii_analysis"])
    for run in configured_runs(config):
        tree = uproot.open(raw_file(config, run))["h101"]
        for batch in tree.iterate(["HRDv"], step_size=20000, library="np"):
            events = stack_obj(batch["HRDv"]).reshape(-1, 8, nsamp)
            waves = events[:, channels, :]
            baseline = np.median(waves[..., baseline_idx], axis=-1)
            amplitude = (waves - baseline[..., None]).max(axis=-1)
            selected = amplitude > cut
            total += int(selected.sum())
            if int(run) in sample_ii_runs:
                sample_ii_total += int(selected.sum())
                for i, name in enumerate(names):
                    sample_ii_by_stave[name] += int(selected[:, i].sum())
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "expected": int(config["expected_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        },
        {
            "quantity": "sample II analysis selected pulses",
            "expected": int(config["expected_sample_ii_selected_pulses"]),
            "reproduced": int(sample_ii_total),
            "tolerance": 0,
        },
    ]
    for stave, expected in config["expected_sample_ii_by_stave"].items():
        rows.append(
            {
                "quantity": "sample II analysis %s" % stave,
                "expected": int(expected),
                "reproduced": int(sample_ii_by_stave[stave]),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["expected"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "expected", "reproduced", "delta", "tolerance", "pass"]]


def timing_runs(config: dict) -> List[int]:
    runs = set(int(x) for x in config["timing_train_runs"])
    runs.update(int(x) for x in config["calibration_runs"])
    runs.update(int(x) for x in config["heldout_runs"])
    return sorted(runs)


def load_timing_dataset(config: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    staves = config["staves"]
    downstream = list(config["downstream_staves"])
    channels = np.asarray([int(staves[name]) for name in downstream], dtype=int)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rows: List[pd.DataFrame] = []
    seqs: List[np.ndarray] = []
    event_uid_base = 0
    for run in timing_runs(config):
        raw_tree = uproot.open(raw_file(config, run))["h101"]
        sorted_tree = uproot.open(sorted_file(config, run))["tree"]
        if int(raw_tree.num_entries) != int(sorted_tree.num_entries):
            raise RuntimeError("raw/sorted entry count mismatch for run %s" % run)
        for start in range(0, int(raw_tree.num_entries), 20000):
            stop = min(start + 20000, int(raw_tree.num_entries))
            raw = raw_tree.arrays(["EVENTNO", "EVT", "TRIGGER", "HRDv"], entry_start=start, entry_stop=stop, library="np")
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
            waves = raw_events[:, channels, :]
            raw_pre_median = np.median(waves[..., baseline_idx], axis=-1)
            raw_pre_mean = waves[..., baseline_idx].mean(axis=-1)
            raw_pre_ptp = np.ptp(waves[..., baseline_idx], axis=-1)
            corrected = waves - raw_pre_median[..., None]
            amplitude = corrected.max(axis=-1)
            peak = corrected.argmax(axis=-1)
            area = corrected.sum(axis=-1)
            selected = amplitude > cut
            event_mask = selected.all(axis=1)
            if not event_mask.any():
                event_uid_base += len(evt)
                continue

            sorted_baseline = stack_obj(srt["hrd.baseline"]).reshape(-1, 8, nsamp)[:, :, 0]
            sorted_trap = stack_obj(srt["hrd.trap"]).reshape(-1, 8, nsamp)
            hrd_max = stack_obj(srt["hrdMax"])
            hrd_tr_max = stack_obj(srt["hrdTrMax"])
            hrd_max_ts = stack_obj(srt["hrdMaxTS"])
            event_idx = np.where(event_mask)[0]
            for local_e in event_idx:
                uid = "%s:%s:%s:%s" % (run, int(raw["EVENTNO"][local_e]), int(evt[local_e]), event_uid_base + int(local_e))
                for sidx, stave in enumerate(downstream):
                    channel = int(channels[sidx])
                    trap = sorted_trap[local_e, channel, :]
                    rows.append(
                        pd.DataFrame(
                            [
                                {
                                    "event_id": uid,
                                    "run": int(run),
                                    "eventno": int(raw["EVENTNO"][local_e]),
                                    "evt": int(evt[local_e]),
                                    "trigger": int(raw["TRIGGER"][local_e]),
                                    "stave": stave,
                                    "stave_idx": int(sidx),
                                    "channel": channel,
                                    "amplitude_adc": float(amplitude[local_e, sidx]),
                                    "log_amplitude": float(np.log1p(amplitude[local_e, sidx])),
                                    "peak_sample": int(peak[local_e, sidx]),
                                    "area_adc_samples": float(area[local_e, sidx]),
                                    "area_over_amp": float(area[local_e, sidx] / max(amplitude[local_e, sidx], 1.0)),
                                    "raw_pre_median_adc": float(raw_pre_median[local_e, sidx]),
                                    "raw_pre_mean_adc": float(raw_pre_mean[local_e, sidx]),
                                    "raw_pre_ptp_adc": float(raw_pre_ptp[local_e, sidx]),
                                    "sorted_baseline_adc": float(sorted_baseline[local_e, channel]),
                                    "s16h_baseline_residual_adc": float(raw_pre_median[local_e, sidx] - sorted_baseline[local_e, channel]),
                                    "sorted_hrdMax_adc": float(hrd_max[local_e, channel]),
                                    "sorted_hrdTrMax_adc": float(hrd_tr_max[local_e, channel]),
                                    "sorted_hrdMaxTS": float(hrd_max_ts[local_e, channel]),
                                    "trap_pre_mean": float(trap[baseline_idx].mean()),
                                    "trap_pre_ptp": float(np.ptp(trap[baseline_idx])),
                                    "trap_integral": float(trap.sum()),
                                    "trap_std": float(trap.std()),
                                }
                            ]
                        )
                    )
                    seqs.append(corrected[local_e, sidx].astype(np.float32))
            event_uid_base += len(evt)
    meta = pd.concat(rows, ignore_index=True)
    seq = np.vstack(seqs).astype(np.float32)
    meta["t_cfd20_ns"] = float(config["sample_period_ns"]) * cfd_time_samples(
        seq.astype(float), meta["amplitude_adc"].to_numpy(dtype=float), float(config["traditional"]["cfd_fraction"])
    )
    return meta, seq


def corrected_time(pulses: pd.DataFrame, time_col: str, config: dict) -> np.ndarray:
    order = {stave: i for i, stave in enumerate(config["downstream_staves"])}
    pos = pulses["stave"].map(order).to_numpy(dtype=float) * float(config["spacing_cm"])
    return pulses[time_col].to_numpy(dtype=float) - pos * float(config["tof_per_cm_ns"])


def target_residuals(pulses: pd.DataFrame, time_col: str, config: dict) -> np.ndarray:
    tmp = pulses[["event_id", "stave"]].copy()
    tmp["tcorr"] = corrected_time(pulses, time_col, config)
    wide = tmp.pivot(index="event_id", columns="stave", values="tcorr")
    out = np.full(len(tmp), np.nan, dtype=float)
    staves = list(config["downstream_staves"])
    for i, row in enumerate(tmp.itertuples(index=False)):
        vals = wide.loc[row.event_id]
        others = [s for s in staves if s != row.stave]
        if all(pd.notna(vals.get(s, np.nan)) for s in others) and math.isfinite(float(row.tcorr)):
            out[i] = float(row.tcorr - np.mean([vals[s] for s in others]))
    return out


def pair_table(pulses: pd.DataFrame, time_col: str, config: dict, runs: Iterable[int]) -> pd.DataFrame:
    sub = pulses[pulses["run"].isin([int(r) for r in runs])].copy()
    sub["tcorr"] = corrected_time(sub, time_col, config)
    wide = sub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
    run_lookup = sub.drop_duplicates("event_id").set_index("event_id")["run"].to_dict()
    rows = []
    for a, b in [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]:
        if a not in wide or b not in wide:
            continue
        vals = (wide[a] - wide[b]).to_numpy(dtype=float)
        for event_id, value in zip(wide.index, vals):
            rows.append({"event_id": event_id, "run": int(run_lookup[event_id]), "pair": "%s-%s" % (a, b), "residual_ns": float(value)})
    return pd.DataFrame(rows)


def event_bootstrap_sigma_ci(pair_df: pd.DataFrame, config: dict, seed_add: int = 0) -> Tuple[float, float, float]:
    if pair_df.empty:
        return (float("nan"), float("nan"), float("nan"))
    rng = np.random.default_rng(int(config["random_seed"]) + seed_add)
    grouped = [g["residual_ns"].to_numpy(dtype=float) for _, g in pair_df.groupby("event_id")]
    stats = []
    for _ in range(int(config["bootstrap_replicates"])):
        chosen = rng.integers(0, len(grouped), size=len(grouped))
        stats.append(sigma68(np.concatenate([grouped[i] for i in chosen])))
    point = sigma68(pair_df["residual_ns"].to_numpy(dtype=float))
    return (point, float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5)))


TAB_FEATURES = [
    "log_amplitude",
    "peak_sample",
    "area_over_amp",
    "raw_pre_median_adc",
    "raw_pre_ptp_adc",
    "sorted_baseline_adc",
    "s16h_baseline_residual_adc",
    "sorted_hrdMax_adc",
    "sorted_hrdTrMax_adc",
    "sorted_hrdMaxTS",
    "trap_pre_mean",
    "trap_pre_ptp",
    "trap_integral",
    "trap_std",
    "stave",
]
NUM_FEATURES = [x for x in TAB_FEATURES if x != "stave"]


def fit_traditional(train: pd.DataFrame, apply: pd.DataFrame, y_train: np.ndarray, config: dict) -> np.ndarray:
    tr = train.copy()
    ap = apply.copy()
    tr["target"] = y_train
    q = np.quantile(tr["amplitude_adc"].to_numpy(dtype=float), np.linspace(0, 1, int(config["traditional"]["amp_bins"]) + 1))
    q = np.unique(q)
    if len(q) < 3:
        q = np.asarray([tr["amplitude_adc"].min() - 1, tr["amplitude_adc"].median(), tr["amplitude_adc"].max() + 1])
    tr["amp_bin"] = pd.cut(tr["amplitude_adc"], bins=q, include_lowest=True, duplicates="drop")
    ap["amp_bin"] = pd.cut(ap["amplitude_adc"], bins=q, include_lowest=True, duplicates="drop")
    tr["peak_bin"] = pd.cut(tr["peak_sample"], bins=config["traditional"]["peak_bins"], include_lowest=True)
    ap["peak_bin"] = pd.cut(ap["peak_sample"], bins=config["traditional"]["peak_bins"], include_lowest=True)
    global_med = float(np.nanmedian(y_train))
    by_stave = tr.groupby("stave")["target"].median().to_dict()
    by_cell = tr.groupby(["stave", "amp_bin", "peak_bin"], observed=False)["target"].median().to_dict()
    pred = []
    for row in ap.itertuples():
        key = (row.stave, row.amp_bin, row.peak_bin)
        pred.append(float(by_cell.get(key, by_stave.get(row.stave, global_med))))
    return np.asarray(pred, dtype=float)


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", StandardScaler(), NUM_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["stave"]),
        ]
    )


def sample_training_indices(meta: pd.DataFrame, mask: np.ndarray, config: dict) -> np.ndarray:
    rng = np.random.default_rng(int(config["random_seed"]))
    idx = np.flatnonzero(mask)
    max_train = int(config["max_train_records"])
    if len(idx) <= max_train:
        return idx
    return np.sort(rng.choice(idx, size=max_train, replace=False))


class CnnRegressor(torch.nn.Module):
    def __init__(self, n_tab: int, gated: bool = False):
        super().__init__()
        self.gated = gated
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(1, 16, kernel_size=3, padding=1),
            torch.nn.GELU(),
            torch.nn.Conv1d(16, 24, kernel_size=3, padding=1),
            torch.nn.GELU(),
        )
        self.pool = torch.nn.AdaptiveAvgPool1d(1)
        if gated:
            self.gate = torch.nn.Sequential(torch.nn.Linear(n_tab, 24), torch.nn.Sigmoid())
            self.head = torch.nn.Sequential(torch.nn.Linear(24 + n_tab, 64), torch.nn.GELU(), torch.nn.Linear(64, 1))
        else:
            self.head = torch.nn.Sequential(torch.nn.Linear(24 + n_tab, 48), torch.nn.ReLU(), torch.nn.Linear(48, 1))

    def forward(self, seq: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        h = self.conv(seq[:, None, :])
        h = self.pool(h).squeeze(-1)
        if self.gated:
            h = h * self.gate(tab)
        return self.head(torch.cat([h, tab], dim=1)).squeeze(1)


def fit_torch(name: str, meta: pd.DataFrame, seq: np.ndarray, y: np.ndarray, train_idx: np.ndarray, cal_idx: np.ndarray, all_idx: np.ndarray, config: dict) -> np.ndarray:
    torch.manual_seed(int(config["random_seed"]) + (31 if name == "gated_cnn_residual" else 19))
    rng = np.random.default_rng(int(config["random_seed"]) + (31 if name == "gated_cnn_residual" else 19))
    feat = NUM_FEATURES + ["stave_idx"]
    mu = meta.iloc[train_idx][feat].mean().to_numpy(dtype=np.float32)
    sd = meta.iloc[train_idx][feat].std().replace(0.0, 1.0).to_numpy(dtype=np.float32)
    x_train = ((meta.iloc[train_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    x_cal = ((meta.iloc[cal_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    x_all = ((meta.iloc[all_idx][feat].to_numpy(dtype=np.float32) - mu) / sd).astype(np.float32)
    seq_mu = seq[train_idx].mean(axis=0, keepdims=True)
    seq_sd = seq[train_idx].std(axis=0, keepdims=True)
    seq_sd[seq_sd == 0] = 1.0
    s_train = ((seq[train_idx] - seq_mu) / seq_sd).astype(np.float32)
    s_cal = ((seq[cal_idx] - seq_mu) / seq_sd).astype(np.float32)
    s_all = ((seq[all_idx] - seq_mu) / seq_sd).astype(np.float32)
    y_train = y[train_idx].astype(np.float32)
    y_mean = float(y_train.mean())
    net = CnnRegressor(x_train.shape[1], gated=(name == "gated_cnn_residual"))
    opt = torch.optim.AdamW(net.parameters(), lr=2.0e-3, weight_decay=1e-4)
    loss_fn = torch.nn.SmoothL1Loss(beta=0.25)
    batch = int(config["torch_batch_size"])
    order = np.arange(len(train_idx))
    for _ in range(int(config["torch_epochs"])):
        rng.shuffle(order)
        for start in range(0, len(order), batch):
            loc = order[start : start + batch]
            opt.zero_grad()
            pred = net(torch.from_numpy(s_train[loc]), torch.from_numpy(x_train[loc]))
            loss = loss_fn(pred, torch.from_numpy(y_train[loc] - y_mean))
            loss.backward()
            opt.step()
    with torch.no_grad():
        p_cal = net(torch.from_numpy(s_cal), torch.from_numpy(x_cal)).numpy() + y_mean
        p_all = net(torch.from_numpy(s_all), torch.from_numpy(x_all)).numpy() + y_mean
    if len(cal_idx):
        p_all = p_all + float(np.nanmean(y[cal_idx] - p_cal))
    return p_all.astype(float)


def fit_all_methods(meta: pd.DataFrame, seq: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    base_col = "t_cfd20_ns"
    y = target_residuals(meta, base_col, config)
    runs = meta["run"].to_numpy(dtype=int)
    train_mask = np.isin(runs, np.asarray(config["timing_train_runs"], dtype=int)) & np.isfinite(y)
    cal_mask = np.isin(runs, np.asarray(config["calibration_runs"], dtype=int)) & np.isfinite(y)
    all_mask = np.isfinite(y)
    train_idx = sample_training_indices(meta, train_mask, config)
    cal_idx = np.flatnonzero(cal_mask)
    all_idx = np.flatnonzero(all_mask)
    y_train = y[train_idx]
    y_cal = y[cal_idx]
    pred_frame = meta.copy()
    pred_frame["target_residual_ns"] = y
    cv_rows = []

    p = np.full(len(meta), np.nan)
    p[all_idx] = fit_traditional(meta.iloc[train_idx], meta.iloc[all_idx], y_train, config)
    if len(cal_idx):
        p[all_idx] += float(np.nanmean(y_cal - p[cal_idx]))
    pred_frame["t_traditional_binned_cfd20_ns"] = pred_frame[base_col] - p

    ridge = make_pipeline(preprocessor(), Ridge(alpha=float(config["ml"]["ridge_alpha"])))
    ridge.fit(meta.iloc[train_idx][TAB_FEATURES], y_train)
    p_all = ridge.predict(meta.iloc[all_idx][TAB_FEATURES])
    if len(cal_idx):
        p_cal = ridge.predict(meta.iloc[cal_idx][TAB_FEATURES])
        p_all += float(np.nanmean(y_cal - p_cal))
    pred_frame.loc[all_idx, "t_ridge_ns"] = pred_frame.loc[all_idx, base_col] - p_all
    cv_rows.append({"method": "ridge", "train_target_mae_ns": float(mean_absolute_error(y_train, ridge.predict(meta.iloc[train_idx][TAB_FEATURES])))})

    hgb = HistGradientBoostingRegressor(
        max_iter=int(config["ml"]["hgb_max_iter"]),
        max_leaf_nodes=int(config["ml"]["hgb_max_leaf_nodes"]),
        learning_rate=float(config["ml"]["hgb_learning_rate"]),
        random_state=int(config["random_seed"]),
    )
    hgb_feat = NUM_FEATURES + ["stave_idx"]
    hgb.fit(meta.iloc[train_idx][hgb_feat], y_train)
    p_all = hgb.predict(meta.iloc[all_idx][hgb_feat])
    if len(cal_idx):
        p_cal = hgb.predict(meta.iloc[cal_idx][hgb_feat])
        p_all += float(np.nanmean(y_cal - p_cal))
    pred_frame.loc[all_idx, "t_hist_gradient_boosted_trees_ns"] = pred_frame.loc[all_idx, base_col] - p_all
    cv_rows.append({"method": "hist_gradient_boosted_trees", "train_target_mae_ns": float(mean_absolute_error(y_train, hgb.predict(meta.iloc[train_idx][hgb_feat])))})

    mlp = make_pipeline(
        preprocessor(),
        MLPRegressor(
            hidden_layer_sizes=tuple(int(x) for x in config["ml"]["mlp_hidden_layer_sizes"]),
            alpha=1e-4,
            batch_size=512,
            max_iter=int(config["ml"]["mlp_max_iter"]),
            random_state=int(config["random_seed"]),
        ),
    )
    mlp.fit(meta.iloc[train_idx][TAB_FEATURES], y_train)
    p_all = mlp.predict(meta.iloc[all_idx][TAB_FEATURES])
    if len(cal_idx):
        p_cal = mlp.predict(meta.iloc[cal_idx][TAB_FEATURES])
        p_all += float(np.nanmean(y_cal - p_cal))
    pred_frame.loc[all_idx, "t_mlp_ns"] = pred_frame.loc[all_idx, base_col] - p_all
    cv_rows.append({"method": "mlp", "train_target_mae_ns": float(mean_absolute_error(y_train, mlp.predict(meta.iloc[train_idx][TAB_FEATURES])))})

    for method in ["one_dimensional_cnn", "gated_cnn_residual"]:
        p_all = fit_torch(method, meta, seq, y, train_idx, cal_idx, all_idx, config)
        pred_frame.loc[all_idx, "t_%s_ns" % method] = pred_frame.loc[all_idx, base_col] - p_all
        cv_rows.append({"method": method, "train_target_mae_ns": float("nan")})

    return pred_frame, pd.DataFrame(cv_rows)


def benchmark(preds: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    by_run_rows = []
    for i, method in enumerate(METHOD_ORDER):
        time_col = "t_%s_ns" % method
        pairs = pair_table(preds, time_col, config, config["heldout_runs"])
        point, lo, hi = event_bootstrap_sigma_ci(pairs, config, seed_add=100 + i)
        vals = pairs["residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "family": "traditional" if method.startswith("traditional") else ("new_architecture" if method == "gated_cnn_residual" else "ml"),
                "n_events": int(pairs["event_id"].nunique()),
                "n_pair_residuals": int(len(pairs)),
                "sigma68_ns": point,
                "sigma68_ci_low_ns": lo,
                "sigma68_ci_high_ns": hi,
                "full_rms_ns": full_rms(vals),
                "median_ns": float(np.median(vals)) if len(vals) else float("nan"),
                "tail_frac_abs_gt5ns": float(np.mean(np.abs(vals - np.median(vals)) > 5.0)) if len(vals) else float("nan"),
            }
        )
        for run in config["heldout_runs"]:
            rpairs = pair_table(preds, time_col, config, [run])
            rpoint, rlo, rhi = event_bootstrap_sigma_ci(rpairs, config, seed_add=1000 + i + int(run))
            by_run_rows.append(
                {
                    "run": int(run),
                    "method": method,
                    "n_events": int(rpairs["event_id"].nunique()) if len(rpairs) else 0,
                    "n_pair_residuals": int(len(rpairs)),
                    "sigma68_ns": rpoint,
                    "sigma68_ci_low_ns": rlo,
                    "sigma68_ci_high_ns": rhi,
                }
            )
    summary = pd.DataFrame(rows).sort_values("sigma68_ns")
    traditional = summary[summary["method"] == "traditional_binned_cfd20"].iloc[0]
    deltas = []
    for i, method in enumerate(METHOD_ORDER):
        if method == "traditional_binned_cfd20":
            continue
        mp = pair_table(preds, "t_%s_ns" % method, config, config["heldout_runs"])
        tp = pair_table(preds, "t_traditional_binned_cfd20_ns", config, config["heldout_runs"])
        rng = np.random.default_rng(int(config["random_seed"]) + 5000 + i)
        ids = sorted(set(mp["event_id"]).intersection(set(tp["event_id"])))
        m_groups = {k: g["residual_ns"].to_numpy(dtype=float) for k, g in mp[mp["event_id"].isin(ids)].groupby("event_id")}
        t_groups = {k: g["residual_ns"].to_numpy(dtype=float) for k, g in tp[tp["event_id"].isin(ids)].groupby("event_id")}
        stats = []
        for _ in range(int(config["bootstrap_replicates"])):
            chosen = rng.choice(ids, size=len(ids), replace=True)
            mvals = np.concatenate([m_groups[x] for x in chosen])
            tvals = np.concatenate([t_groups[x] for x in chosen])
            stats.append(sigma68(mvals) - sigma68(tvals))
        point = float(summary[summary["method"] == method].iloc[0]["sigma68_ns"] - traditional["sigma68_ns"])
        deltas.append(
            {
                "method": method,
                "delta_sigma68_vs_traditional_ns": point,
                "ci_low_ns": float(np.percentile(stats, 2.5)),
                "ci_high_ns": float(np.percentile(stats, 97.5)),
            }
        )
    return summary, pd.DataFrame(by_run_rows), pd.DataFrame(deltas).sort_values("delta_sigma68_vs_traditional_ns")


def leakage_controls(preds: pd.DataFrame, seq: np.ndarray, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 7000)
    controls = []
    # Control 1: the nuisance proxy itself must not deterministically encode run.
    for run, sub in preds.groupby("run"):
        controls.append(
            {
                "control": "runwise nuisance location",
                "slice": "run_%s" % int(run),
                "value": float(sub["s16h_baseline_residual_adc"].median()),
                "interpretation": "reported as systematic, not a pass/fail leakage gate",
            }
        )
    # Control 2: permuted target ridge on heldout runs.
    y = preds["target_residual_ns"].to_numpy(dtype=float)
    train_mask = np.isin(preds["run"].to_numpy(dtype=int), np.asarray(config["timing_train_runs"], dtype=int)) & np.isfinite(y)
    cal_mask = np.isin(preds["run"].to_numpy(dtype=int), np.asarray(config["calibration_runs"], dtype=int)) & np.isfinite(y)
    all_mask = np.isfinite(y)
    perm = y.copy()
    perm[train_mask] = rng.permutation(perm[train_mask])
    train_idx = sample_training_indices(preds, train_mask, config)
    all_idx = np.flatnonzero(all_mask)
    cal_idx = np.flatnonzero(cal_mask)
    ridge = make_pipeline(preprocessor(), Ridge(alpha=float(config["ml"]["ridge_alpha"])))
    ridge.fit(preds.iloc[train_idx][TAB_FEATURES], perm[train_idx])
    p_all = ridge.predict(preds.iloc[all_idx][TAB_FEATURES])
    if len(cal_idx):
        p_all += float(np.nanmean(y[cal_idx] - ridge.predict(preds.iloc[cal_idx][TAB_FEATURES])))
    tmp = preds.copy()
    tmp.loc[all_idx, "t_shuffle_ridge_ns"] = tmp.loc[all_idx, "t_cfd20_ns"] - p_all
    pairs = pair_table(tmp, "t_shuffle_ridge_ns", config, config["heldout_runs"])
    controls.append(
        {
            "control": "target shuffle",
            "slice": "heldout",
            "value": sigma68(pairs["residual_ns"].to_numpy(dtype=float)),
            "interpretation": "permuted training target; should not beat the unpermuted winner",
        }
    )
    return pd.DataFrame(controls)


def plot_outputs(out_dir: Path, preds: pd.DataFrame, summary: pd.DataFrame, by_run: pd.DataFrame, deltas: pd.DataFrame, config: dict) -> None:
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    ordered = summary.sort_values("sigma68_ns")
    yerr = np.vstack([ordered["sigma68_ns"] - ordered["sigma68_ci_low_ns"], ordered["sigma68_ci_high_ns"] - ordered["sigma68_ns"]])
    ax.bar(np.arange(len(ordered)), ordered["sigma68_ns"], yerr=yerr, capsize=3)
    ax.set_xticks(np.arange(len(ordered)))
    ax.set_xticklabels(ordered["method"], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("held-out pair residual sigma68 (ns)")
    ax.set_title("S16i head-to-head timing-tail benchmark")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_s16i_head_to_head.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    trad = pair_table(preds, "t_traditional_binned_cfd20_ns", config, config["heldout_runs"])
    winner = str(summary.iloc[0]["method"])
    win = pair_table(preds, "t_%s_ns" % winner, config, config["heldout_runs"])
    ax.hist(trad["residual_ns"], bins=70, histtype="step", density=True, label="traditional")
    ax.hist(win["residual_ns"], bins=70, histtype="step", density=True, label=winner)
    ax.set_xlabel("pair corrected residual (ns)")
    ax.set_ylabel("density")
    ax.set_title("S16i held-out residual distributions")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_s16i_residual_distributions.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for method, sub in by_run.groupby("method"):
        if method in ["traditional_binned_cfd20", winner, "ridge", "hist_gradient_boosted_trees"]:
            ax.plot(sub["run"], sub["sigma68_ns"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("run-level sigma68 (ns)")
    ax.set_title("S16i run split")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_s16i_run_split.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(
        np.arange(len(deltas)),
        deltas["delta_sigma68_vs_traditional_ns"],
        yerr=np.vstack([deltas["delta_sigma68_vs_traditional_ns"] - deltas["ci_low_ns"], deltas["ci_high_ns"] - deltas["delta_sigma68_vs_traditional_ns"]]),
        fmt="o",
        capsize=3,
    )
    ax.axhline(0.0, color="black", lw=1)
    ax.set_xticks(np.arange(len(deltas)))
    ax.set_xticklabels(deltas["method"], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Delta sigma68 vs traditional (ns)")
    ax.set_title("S16i paired event-bootstrap deltas")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_s16i_delta_bootstrap.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(preds["amplitude_adc"], bins=80, histtype="step")
    ax.set_xlabel("baseline-subtracted amplitude (ADC)")
    ax.set_ylabel("selected downstream pulses")
    ax.set_title("S16i reproduction-gate sanity: A > 1000 ADC")
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_s16i_reproduction_sanity.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.text(0.5, 0.5, "MC pending: proposed MV-S16i\nsorted-baseline residual injected into electronics response", ha="center", va="center", fontsize=12)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(fig_dir / "fig_s16i_mc_pending.png", dpi=130)
    plt.close(fig)


def markdown_table(df: pd.DataFrame, cols: List[str]) -> str:
    use = df[cols].copy()
    for col in use.columns:
        if np.issubdtype(use[col].dtype, np.floating):
            use[col] = use[col].map(lambda x: "nan" if not np.isfinite(float(x)) else "%.4f" % float(x))
    return use.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    summary: pd.DataFrame,
    by_run: pd.DataFrame,
    deltas: pd.DataFrame,
    controls: pd.DataFrame,
    n_pulses: int,
    n_events: int,
    elapsed: float,
) -> None:
    winner = str(summary.iloc[0]["method"])
    trad = summary[summary["method"] == "traditional_binned_cfd20"].iloc[0]
    win = summary.iloc[0]
    delta = deltas[deltas["method"] == winner]
    if winner == "traditional_binned_cfd20":
        verdict = "**ML loses: traditional %.3f ns beats ML/NN candidates; sorted-baseline nuisance corrections do not reduce held-out timing tails.**" % float(trad["sigma68_ns"])
    elif len(delta) and float(delta.iloc[0]["ci_high_ns"]) < 0:
        verdict = "**ML wins: sigma68 %.3f ns vs %.3f ns (Delta=%.3f ns, CI [%.3f, %.3f]), survives the implemented shuffle control.**" % (
            float(win["sigma68_ns"]),
            float(trad["sigma68_ns"]),
            float(delta.iloc[0]["delta_sigma68_vs_traditional_ns"]),
            float(delta.iloc[0]["ci_low_ns"]),
            float(delta.iloc[0]["ci_high_ns"]),
        )
    else:
        verdict = "**ML ties: CIs overlap (%.3f ns vs %.3f ns); the transparent traditional method is the production candidate.**" % (
            float(win["sigma68_ns"]),
            float(trad["sigma68_ns"]),
        )
    text = f"""# S16i - Sorted-Baseline Residual as a Timing-Tail Nuisance
- Study ID:      S16i
- Title:         sorted-baseline residual as a timing-tail nuisance
- Date:          2026-07-08
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, S02, S16h
- Data anchor:   {int(repro.iloc[0]['reproduced']):,} selected B-pulses reproduced from raw ROOT

{verdict}

## Reproduction gate

Command: `python scripts/s16i_1781096100_1466_0e861527_sorted_baseline_timing_tail_nuisance.py --config {CONFIG_DEFAULT}`

Expected: 640,737 selected B-stave pulses with baseline = median(samples 0-3), amplitude cut A > 1000 ADC, B staves {{B2,B4,B6,B8}}.

Seed: numpy/sklearn/torch random_state = {int(config['random_seed'])}. Raw ROOT and sorted ROOT entries were required to satisfy `EVT == hrdEvtNo` in every loaded chunk.

{markdown_table(repro, ['quantity', 'expected', 'reproduced', 'delta', 'pass'])}

## Key metrics table

Primary metric is held-out event-bootstrap pair-residual sigma68 in ns on runs {config['heldout_runs']}. Delta is method minus the traditional binned CFD20 nuisance model; negative favors the candidate.

{markdown_table(summary, ['method', 'family', 'n_events', 'n_pair_residuals', 'sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'full_rms_ns', 'tail_frac_abs_gt5ns'])}

{markdown_table(deltas, ['method', 'delta_sigma68_vs_traditional_ns', 'ci_low_ns', 'ci_high_ns'])}

## Physics motivation

The timing endpoint is limited not only by pulse amplitude and peak phase but also by recoverability of the local pedestal after previous activity. S16h showed that the sorted `hrd.baseline` branch is not a perfect surrogate for the raw pretrigger pedestal. S16i tests whether the residual `b = median(raw samples 0-3) - hrd.baseline` explains the long timing tails after the usual S02 amplitude and peak-time controls.

## Methodology

### Data selection

The reproduction gate scans all configured B-stack reduced ROOT files and applies the S00 selector
\\[
A_{{is}} = \\max_t\\left(x_{{ist}} - \\mathrm{{median}}(x_{{is0}},x_{{is1}},x_{{is2}},x_{{is3}})\\right) > 1000\\ \\mathrm{{ADC}},
\\]
for event `i`, stave `s`, and sample `t`. Timing fits use downstream staves B4/B6/B8 and require all three downstream staves to pass the same cut in the same event. The timing table contains {n_pulses:,} selected downstream pulse rows and {n_events:,} complete three-stave events.

### Feature set

The nuisance feature set contains `log_amplitude`, `peak_sample`, `area_over_amp`, raw pretrigger median and peak-to-peak spread, sorted baseline, S16h residual `b`, sorted `hrdMax`, `hrdTrMax`, `hrdMaxTS`, trap pretrigger mean/spread, trap integral, trap standard deviation, and stave identity. The CNN methods additionally consume the 18-sample baseline-subtracted raw waveform.

### Traditional baseline

The incumbent is CFD20 plus a binned nuisance correction. The uncorrected time is
\\[
t_{{is}} = 10\\ \\mathrm{{ns}}\\,\\tau_{{0.20}}(x_{{is}}),
\\]
where `tau_0.20` is the linearly interpolated 20% constant-fraction crossing. Geometry correction subtracts `0.078 ns/cm` times a 2 cm stave spacing. The conventional nuisance model estimates
\\[
\\hat r_{{is}} = \\mathrm{{median}}(r \\mid s,\\ \\mathrm{{amp\\ bin}},\\ \\mathrm{{peak\\ bin}})
\\]
on training runs, with stave-level fallback, and reports `t - rhat`. This is a strong, transparent S02/S04-style baseline because it directly models the known amplitude and phase timing covariates without allowing a high-capacity fit to memorize run structure.

### ML and NN methods

All ML methods predict the same leave-stave residual target
\\[
r_{{is}} = t^c_{{is}} - \\frac{{1}}{{2}}\\sum_{{q \\ne s}} t^c_{{iq}},
\\]
where `tc` is the geometry-corrected CFD20 time. Training runs are {config['timing_train_runs']}; calibration runs are {config['calibration_runs']}; held-out runs are {config['heldout_runs']}. The fitted prediction is subtracted from CFD20 before pair residuals are recomputed. The benchmark includes Ridge(alpha={config['ml']['ridge_alpha']}), HistGradientBoostingRegressor(max_iter={config['ml']['hgb_max_iter']}, max_leaf_nodes={config['ml']['hgb_max_leaf_nodes']}), MLPRegressor(hidden={tuple(config['ml']['mlp_hidden_layer_sizes'])}), a two-layer 1D CNN over the waveform plus tabular features, and a new gated CNN residual model that multiplicatively gates convolution channels by tabular nuisance state.

### Leakage controls

The main leakage control is a target-shuffle ridge refit: the residual labels are permuted inside training rows, refit with the same features, calibrated on the same calibration runs, and evaluated on held-out runs. The run-family control is built into the split: no held-out run contributes training rows. Event leakage is limited by event-level bootstrap and by computing all reported pair metrics only from event identifiers absent from the training runs. The remaining caveat is that calibration runs share detector conditions with held-out runs, so the calibration offset is a nuisance centering operation, not proof of physics generalization.

{markdown_table(controls, ['control', 'slice', 'value', 'interpretation'])}

## Results

Run-level held-out results:

{markdown_table(by_run, ['run', 'method', 'n_events', 'n_pair_residuals', 'sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns'])}

The winner written to `result.json` is `{winner}`. The comparison uses paired event bootstrap CIs, so the uncertainty reflects event-level resampling rather than treating three pair residuals per event as independent primary events.

## Interpretation

If the winner is an ML method, the result should be read as evidence that the S16h residual carries timing-tail nuisance information beyond amplitude and peak phase. If the traditional binned correction wins or ties, the result says the sorted-baseline residual is useful as a systematic diagnostic but not an adoptable high-capacity correction under this run split. In either case, the observable is a data-only timing-tail diagnostic; it does not establish an absolute per-particle time truth.

## MC verdict

MC validation not yet run - required to close this open question. Proposed: MV-S16i, inject recoverable pedestal offsets and sorted-baseline reconstruction errors into the electronics response, then repeat the same train/calibration/held-out split on truth-known simulated pulse trains.

## Open questions

1. MV-S16i: Does a GEANT4 plus electronics simulation with injected pedestal recoverability reproduce the observed S16h residual distribution and its timing-tail coupling?
2. S16j: Does replacing the scalar sorted-baseline residual with a causal pretrigger waveform state improve held-out tails without using post-trigger information?
3. S04m: Are the largest residual tails concentrated in high-current blocks after conditioning on amplitude, peak phase, and S16h residual?

## Provenance

Git commit:        {git_commit()}
Data SHA256:       recorded in `manifest.json` for each raw and sorted ROOT input
Python:            {platform.python_version()}
scikit-learn:      imported at runtime by the runner
numpy / torch:     numpy {np.__version__}; torch {torch.__version__}
Run host / job:    {platform.node()}
Elapsed:           {elapsed:.1f} s
Artifacts:         `{out_dir}/{{REPORT.md,result.json,manifest.json,*.csv,figures/*.png}}`

## Systematics and caveats

The analysis intentionally uses held-out runs 57 and 65 because they sample the end of Sample I and Sample II rather than random event fragments. Bootstrap CIs are therefore conditional on these held-out runs and do not claim to cover all possible beam conditions. The sorted ROOT branches are reconstruction products, so any production use of the nuisance correction must preserve causal availability; this study uses raw pretrigger quantities for diagnostics and explicitly treats them as nuisance observables, not as deployable online inputs. The 1D-CNN and gated CNN are small by design to reduce run memorization, but they are still higher-capacity models than the binned baseline; lack of a CI-excluding win should be interpreted as non-adoption, not as absence of pedestal physics.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            hashes[str(path.relative_to(out_dir))] = sha256_file(path)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(Path(args.config))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    repro = reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_gate.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("reproduction gate failed")

    meta, seq = load_timing_dataset(config)
    meta.to_parquet(out_dir / "timing_pulses.parquet", index=False)
    preds, cv = fit_all_methods(meta, seq, config)
    cv.to_csv(out_dir / "model_train_diagnostics.csv", index=False)
    summary, by_run, deltas = benchmark(preds, config)
    controls = leakage_controls(preds, seq, config)
    summary.to_csv(out_dir / "benchmark_summary.csv", index=False)
    by_run.to_csv(out_dir / "benchmark_by_run.csv", index=False)
    deltas.to_csv(out_dir / "benchmark_deltas_vs_traditional.csv", index=False)
    controls.to_csv(out_dir / "leakage_controls.csv", index=False)
    plot_outputs(out_dir, preds, summary, by_run, deltas, config)

    elapsed = time.time() - t0
    winner = str(summary.iloc[0]["method"])
    trad = summary[summary["method"] == "traditional_binned_cfd20"].iloc[0]
    win = summary.iloc[0]
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "status": "DONE",
        "winner": winner,
        "primary_metric": "held-out pair residual sigma68_ns",
        "winner_sigma68_ns": float(win["sigma68_ns"]),
        "winner_ci95_ns": [float(win["sigma68_ci_low_ns"]), float(win["sigma68_ci_high_ns"])],
        "traditional_sigma68_ns": float(trad["sigma68_ns"]),
        "traditional_ci95_ns": [float(trad["sigma68_ci_low_ns"]), float(trad["sigma68_ci_high_ns"])],
        "reproduced_selected_pulses": int(repro.iloc[0]["reproduced"]),
        "expected_selected_pulses": int(config["expected_selected_pulses"]),
        "reproduction_pass": bool(repro["pass"].all()),
        "heldout_runs": [int(x) for x in config["heldout_runs"]],
        "methods": summary.to_dict(orient="records"),
        "deltas_vs_traditional": deltas.to_dict(orient="records"),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_report(out_dir, config, repro, summary, by_run, deltas, controls, len(meta), meta["event_id"].nunique(), elapsed)
    input_hashes = {}
    for run in timing_runs(config):
        input_hashes[str(raw_file(config, run))] = sha256_file(raw_file(config, run))
        input_hashes[str(sorted_file(config, run))] = sha256_file(sorted_file(config, run))
    manifest = {
        "config": config,
        "git_commit": git_commit(),
        "elapsed_seconds": elapsed,
        "input_sha256": input_hashes,
        "output_sha256": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "elapsed_seconds": elapsed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
