#!/usr/bin/env python3
"""S02i pretrigger-proxy timing transfer atom map.

The script reads raw B-stack HRDv ROOT waveforms, reproduces the S00 selected
pulse count, then benchmarks train-run-frozen timing residual corrections under
Sample-II leave-one-run-out splits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", "/tmp/testbeam-mplconfig")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.set_num_threads(2)
except Exception:  # pragma: no cover - reported in result/manifest.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


PAIR_ORDER = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
PAIR_TO_INT = {f"{a}-{b}": i for i, (a, b) in enumerate(PAIR_ORDER)}
BASE_FEATURES = [
    "pair_code",
    "log_mean_amp",
    "log_amp_ratio",
    "inv_min_amp",
    "amp_asymmetry",
    "min_amplitude_adc",
    "max_peak_sample",
    "abs_peak_delta",
]
ATOM_GROUPS = {
    "atom_mean": ["mean_pre_mean_adc", "abs_delta_pre_mean_adc"],
    "atom_slope": ["mean_pre_slope_adc_per_sample", "abs_delta_pre_slope_adc_per_sample"],
    "atom_early_minus_late": ["mean_pre_early_minus_late_adc", "abs_delta_pre_early_minus_late_adc"],
    "atom_quiet_proxy_bin": ["quiet_proxy_bin"],
    "atom_large_lowering_flag": ["large_lowering_flag", "max_pre_lowering_adc"],
}
ALL_ATOM_FEATURES = sorted({name for names in ATOM_GROUPS.values() for name in names})
TABULAR_ML_FEATURES = BASE_FEATURES + ALL_ATOM_FEATURES + [
    "max_pre_abs_adc",
    "max_pre_ptp_adc",
    "max_pre_rms_adc",
    "max_abs_pre_slope_adc_per_sample",
]
METHOD_ORDER = [
    "traditional_base_huber",
    "traditional_atom_mean",
    "traditional_atom_slope",
    "traditional_atom_early_minus_late",
    "traditional_atom_quiet_proxy_bin",
    "traditional_atom_large_lowering_flag",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn1d",
    "siamese_cnn_meta",
]


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
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: Sequence[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


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
        y0, y1 = waveforms[i, j - 1], waveforms[i, j]
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def geometry_positions(staves: Sequence[str], spacing_cm: float) -> Dict[str, float]:
    order = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}
    return {stave: float(spacing_cm) * order[stave] for stave in staves}


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
    return float(np.sqrt(np.mean(values**2))) if len(values) else float("nan")


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    total = 0
    sample_ii = {k: 0 for k in ["selected_pulses", *stave_names]}

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        for batch in iter_raw(path, ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            baseline = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            total += int(selected.sum())
            if run in config["run_groups"]["sample_ii_analysis"]:
                sample_ii["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_ii[stave] += int(selected[:, i].sum())

    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for key, value in config["expected_counts"]["sample_ii_analysis"].items():
        rows.append({"quantity": f"sample_ii_analysis {key}", "report_value": int(value), "reproduced": int(sample_ii[key]), "tolerance": 0})
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def load_sample_ii_pulses(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    downstream = list(config["timing"]["downstream_staves"])
    channels = np.asarray([int(config["staves"][name]) for name in downstream])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    period = float(config["sample_period_ns"])
    frac = float(config["timing"]["cfd_fraction"])
    rows = []
    event_uid_base = 0

    for run in [int(r) for r in config["timing"]["loro_runs"]]:
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            raw = events[:, channels, :]
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            event_mask = selected.all(axis=1)
            if not event_mask.any():
                event_uid_base += len(eventno)
                continue
            event_idx = np.where(event_mask)[0]
            flat = corrected[event_idx].reshape(-1, nsamp)
            flat_amp = amplitude[event_idx].reshape(-1)
            times = period * cfd_time_samples(flat, flat_amp, frac)
            times = times.reshape(len(event_idx), len(downstream))
            for local_i, e in enumerate(event_idx):
                event_id = f"{run}:{int(eventno[e])}:{int(evt[e])}:{event_uid_base + int(e)}"
                for sidx, stave in enumerate(downstream):
                    y = corrected[e, sidx].astype(float)
                    pre = y[baseline_idx]
                    x = np.arange(len(pre), dtype=float)
                    slope = float(np.polyfit(x, pre, 1)[0]) if len(pre) > 1 else 0.0
                    early_minus_late = float(0.5 * (pre[0] + pre[1]) - 0.5 * (pre[2] + pre[3]))
                    rows.append(
                        {
                            "event_id": event_id,
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": stave,
                            "amplitude_adc": float(amplitude[e, sidx]),
                            "peak_sample": int(y.argmax()),
                            "t_cfd20_ns": float(times[local_i, sidx]),
                            "pre_0": float(pre[0]),
                            "pre_1": float(pre[1]),
                            "pre_2": float(pre[2]),
                            "pre_3": float(pre[3]),
                            "pre_mean_adc": float(pre.mean()),
                            "pre_abs_adc": float(np.max(np.abs(pre))),
                            "pre_ptp_adc": float(np.ptp(pre)),
                            "pre_rms_adc": float(np.sqrt(np.mean((pre - pre.mean()) ** 2))),
                            "pre_slope_adc_per_sample": slope,
                            "pre_early_minus_late_adc": early_minus_late,
                            "pre_lowering_adc": float(pre[0] - pre[-1]),
                        }
                    )
            event_uid_base += len(eventno)
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no Sample-II all-downstream pulses found")
    return out


def build_pair_table(pulses: pd.DataFrame, config: dict) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = geometry_positions(downstream, float(config["spacing_cm"]))
    sub = pulses.copy()
    sub["tcorr"] = sub["t_cfd20_ns"] - sub["stave"].map(positions).astype(float) * float(config["tof_per_cm_ns"])
    value_cols = [
        "tcorr",
        "pre_0",
        "pre_1",
        "pre_2",
        "pre_3",
        "pre_mean_adc",
        "pre_abs_adc",
        "pre_ptp_adc",
        "pre_rms_adc",
        "pre_slope_adc_per_sample",
        "pre_early_minus_late_adc",
        "pre_lowering_adc",
        "amplitude_adc",
        "peak_sample",
    ]
    wide = sub.pivot(index="event_id", columns="stave", values=value_cols)
    run_lookup = sub.groupby("event_id")["run"].first()
    rows = []
    for event_id, row in wide.dropna().iterrows():
        run = int(run_lookup.loc[event_id])
        for a, b in PAIR_ORDER:
            pair = f"{a}-{b}"
            pre_a = np.asarray([row[(f"pre_{i}", a)] for i in range(4)], dtype=float)
            pre_b = np.asarray([row[(f"pre_{i}", b)] for i in range(4)], dtype=float)
            amp_a = float(row[("amplitude_adc", a)])
            amp_b = float(row[("amplitude_adc", b)])
            peak_a = float(row[("peak_sample", a)])
            peak_b = float(row[("peak_sample", b)])
            min_amp = max(min(amp_a, amp_b), 1.0)
            mean_amp = max(0.5 * (amp_a + amp_b), 1.0)
            rows.append(
                {
                    "event_id": event_id,
                    "run": run,
                    "pair": pair,
                    "pair_code": int(PAIR_TO_INT[pair]),
                    "stave_a": a,
                    "stave_b": b,
                    "residual_ns": float(row[("tcorr", a)] - row[("tcorr", b)]),
                    "log_mean_amp": float(np.log(mean_amp)),
                    "log_amp_ratio": float(np.log((amp_a + 1.0) / (amp_b + 1.0))),
                    "inv_min_amp": float(1.0 / min_amp),
                    "amp_asymmetry": float((amp_a - amp_b) / (amp_a + amp_b + 1.0)),
                    "min_amplitude_adc": float(min_amp),
                    "max_peak_sample": max(peak_a, peak_b),
                    "abs_peak_delta": abs(peak_a - peak_b),
                    "mean_pre_mean_adc": 0.5 * (float(row[("pre_mean_adc", a)]) + float(row[("pre_mean_adc", b)])),
                    "abs_delta_pre_mean_adc": abs(float(row[("pre_mean_adc", a)]) - float(row[("pre_mean_adc", b)])),
                    "mean_pre_slope_adc_per_sample": 0.5
                    * (float(row[("pre_slope_adc_per_sample", a)]) + float(row[("pre_slope_adc_per_sample", b)])),
                    "abs_delta_pre_slope_adc_per_sample": abs(
                        float(row[("pre_slope_adc_per_sample", a)]) - float(row[("pre_slope_adc_per_sample", b)])
                    ),
                    "mean_pre_early_minus_late_adc": 0.5
                    * (float(row[("pre_early_minus_late_adc", a)]) + float(row[("pre_early_minus_late_adc", b)])),
                    "abs_delta_pre_early_minus_late_adc": abs(
                        float(row[("pre_early_minus_late_adc", a)]) - float(row[("pre_early_minus_late_adc", b)])
                    ),
                    "max_pre_abs_adc": max(float(row[("pre_abs_adc", a)]), float(row[("pre_abs_adc", b)])),
                    "max_pre_ptp_adc": max(float(row[("pre_ptp_adc", a)]), float(row[("pre_ptp_adc", b)])),
                    "max_pre_rms_adc": max(float(row[("pre_rms_adc", a)]), float(row[("pre_rms_adc", b)])),
                    "max_abs_pre_slope_adc_per_sample": max(
                        abs(float(row[("pre_slope_adc_per_sample", a)])),
                        abs(float(row[("pre_slope_adc_per_sample", b)])),
                    ),
                    "max_pre_lowering_adc": max(float(row[("pre_lowering_adc", a)]), float(row[("pre_lowering_adc", b)])),
                    "pre_seq": np.vstack([pre_a, pre_b]).astype(np.float32),
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no pair residuals produced")
    return out


def add_fold_atoms(train: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    quiet_ref = np.quantile(train["max_pre_rms_adc"].to_numpy(dtype=float), [0.25, 0.50, 0.75])
    lowering_threshold = float(np.quantile(train["max_pre_lowering_adc"].to_numpy(dtype=float), 0.95))
    out["quiet_proxy_bin"] = np.searchsorted(quiet_ref, out["max_pre_rms_adc"].to_numpy(dtype=float), side="right").astype(float)
    out["large_lowering_flag"] = (out["max_pre_lowering_adc"].to_numpy(dtype=float) >= lowering_threshold).astype(float)
    return out


def one_hot_pair(frame: pd.DataFrame) -> np.ndarray:
    codes = frame["pair_code"].to_numpy(dtype=int)
    out = np.zeros((len(frame), len(PAIR_ORDER)), dtype=float)
    out[np.arange(len(frame)), np.clip(codes, 0, len(PAIR_ORDER) - 1)] = 1.0
    return out


def matrix(frame: pd.DataFrame, cols: Sequence[str]) -> np.ndarray:
    numeric = frame[list(cols)].to_numpy(dtype=float)
    return np.hstack([numeric, one_hot_pair(frame)])


def preseq_arrays(train: pd.DataFrame, frame: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    train_seq = np.stack(train["pre_seq"].to_numpy()).astype(np.float32)
    frame_seq = np.stack(frame["pre_seq"].to_numpy()).astype(np.float32)
    med = np.median(train_seq, axis=(0, 2), keepdims=True)
    mad = np.median(np.abs(train_seq - med), axis=(0, 2), keepdims=True)
    scale = np.maximum(1.4826 * mad, 1.0)
    return ((train_seq - med) / scale).astype(np.float32), ((frame_seq - med) / scale).astype(np.float32)


class TinyCnnRegressor(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(2, 10, kernel_size=2),
            nn.ReLU(),
            nn.Conv1d(10, 10, kernel_size=2),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(20, 12),
            nn.ReLU(),
            nn.Linear(12, 1),
        )

    def forward(self, seq: torch.Tensor, meta: torch.Tensor | None = None) -> torch.Tensor:
        return self.net(seq).squeeze(-1)


class SiameseMetaRegressor(nn.Module):
    def __init__(self, n_meta: int) -> None:
        super().__init__()
        self.branch = nn.Sequential(
            nn.Conv1d(1, 10, kernel_size=2),
            nn.ReLU(),
            nn.Conv1d(10, 10, kernel_size=2),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(20, 10),
            nn.ReLU(),
        )
        self.head = nn.Sequential(nn.Linear(30 + n_meta, 32), nn.ReLU(), nn.Dropout(0.10), nn.Linear(32, 1))

    def forward(self, seq: torch.Tensor, meta: torch.Tensor | None = None) -> torch.Tensor:
        a = self.branch(seq[:, 0:1, :])
        b = self.branch(seq[:, 1:2, :])
        return self.head(torch.cat([a, b, torch.abs(a - b), meta], dim=1)).squeeze(-1)


def train_torch_regressor(
    model: nn.Module,
    train_seq: np.ndarray,
    train_meta: np.ndarray,
    y: np.ndarray,
    frame_seq: np.ndarray,
    frame_meta: np.ndarray,
    config: dict,
    seed: int,
) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is unavailable")
    torch.manual_seed(int(seed))
    device = torch.device("cpu")
    model = model.to(device)
    y_mean = float(np.mean(y))
    y_scale = float(np.std(y))
    if not np.isfinite(y_scale) or y_scale <= 0:
        y_scale = 1.0
    yy = ((y - y_mean) / y_scale).astype(np.float32)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["models"]["nn_learning_rate"]), weight_decay=float(config["models"]["nn_weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    ds = TensorDataset(torch.tensor(train_seq), torch.tensor(train_meta.astype(np.float32)), torch.tensor(yy))
    loader = DataLoader(ds, batch_size=int(config["models"]["nn_batch_size"]), shuffle=True)
    best = float("inf")
    stale = 0
    for _ in range(int(config["models"]["nn_epochs"])):
        model.train()
        total = 0.0
        count = 0
        for xb, mb, yb in loader:
            xb, mb, yb = xb.to(device), mb.to(device), yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb, mb), yb)
            loss.backward()
            opt.step()
            total += float(loss.item()) * len(yb)
            count += len(yb)
        avg = total / max(count, 1)
        if avg + 1e-5 < best:
            best = avg
            stale = 0
        else:
            stale += 1
            if stale >= int(config["models"]["nn_patience"]):
                break
    model.eval()
    with torch.no_grad():
        pred = model(torch.tensor(frame_seq, dtype=torch.float32, device=device), torch.tensor(frame_meta.astype(np.float32), device=device))
    return pred.cpu().numpy() * y_scale + y_mean


def fit_predict(train: pd.DataFrame, frame: pd.DataFrame, config: dict, method: str, seed: int) -> np.ndarray:
    y = train["residual_ns"].to_numpy(dtype=float)
    if method == "traditional_base_huber":
        cols = BASE_FEATURES
        model = make_pipeline(StandardScaler(), HuberRegressor(alpha=0.0001, epsilon=1.35, max_iter=300))
        model.fit(matrix(train, cols), y)
        return model.predict(matrix(frame, cols))
    if method.startswith("traditional_atom_"):
        atom_name = "atom_" + method.split("traditional_atom_", 1)[1]
        cols = BASE_FEATURES + ATOM_GROUPS[atom_name]
        model = make_pipeline(StandardScaler(), HuberRegressor(alpha=0.0001, epsilon=1.35, max_iter=300))
        model.fit(matrix(train, cols), y)
        return model.predict(matrix(frame, cols))
    if method == "ridge":
        best_alpha = None
        best_score = float("inf")
        runs = np.asarray(sorted(train["run"].unique()), dtype=int)
        for alpha in config["models"]["ridge_alphas"]:
            preds = []
            obs = []
            for run in runs:
                tr = train[train["run"] != run]
                va = train[train["run"] == run]
                model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
                model.fit(matrix(tr, TABULAR_ML_FEATURES), tr["residual_ns"].to_numpy(dtype=float))
                preds.append(model.predict(matrix(va, TABULAR_ML_FEATURES)))
                obs.append(va["residual_ns"].to_numpy(dtype=float))
            score = sigma68(np.concatenate(obs) - np.concatenate(preds))
            if score < best_score:
                best_score = score
                best_alpha = float(alpha)
        model = make_pipeline(StandardScaler(), Ridge(alpha=float(best_alpha)))
        model.fit(matrix(train, TABULAR_ML_FEATURES), y)
        return model.predict(matrix(frame, TABULAR_ML_FEATURES))
    if method == "gradient_boosted_trees":
        model = HistGradientBoostingRegressor(
            loss="absolute_error",
            max_iter=int(config["models"]["gbt_max_iter"]),
            learning_rate=float(config["models"]["gbt_learning_rate"]),
            max_leaf_nodes=int(config["models"]["gbt_max_leaf_nodes"]),
            random_state=int(seed),
        )
        model.fit(matrix(train, TABULAR_ML_FEATURES), y)
        return model.predict(matrix(frame, TABULAR_ML_FEATURES))
    if method == "mlp":
        model = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=tuple(int(v) for v in config["models"]["mlp_hidden_layer_sizes"]),
                alpha=float(config["models"]["mlp_alpha"]),
                max_iter=int(config["models"]["mlp_max_iter"]),
                random_state=int(seed),
                early_stopping=True,
                n_iter_no_change=20,
            ),
        )
        model.fit(matrix(train, TABULAR_ML_FEATURES), y)
        return model.predict(matrix(frame, TABULAR_ML_FEATURES))
    if method in {"cnn1d", "siamese_cnn_meta"}:
        train_seq, frame_seq = preseq_arrays(train, frame)
        if method == "cnn1d":
            meta_train = np.zeros((len(train), 1), dtype=np.float32)
            meta_frame = np.zeros((len(frame), 1), dtype=np.float32)
            return train_torch_regressor(TinyCnnRegressor(), train_seq, meta_train, y, frame_seq, meta_frame, config, seed)
        scaler = StandardScaler()
        meta_train = scaler.fit_transform(matrix(train, TABULAR_ML_FEATURES)).astype(np.float32)
        meta_frame = scaler.transform(matrix(frame, TABULAR_ML_FEATURES)).astype(np.float32)
        return train_torch_regressor(SiameseMetaRegressor(meta_train.shape[1]), train_seq, meta_train, y, frame_seq, meta_frame, config, seed)
    raise ValueError(method)


def metric_row(frame: pd.DataFrame, residual_col: str, method: str, heldout_run: int) -> dict:
    vals = frame[residual_col].to_numpy(dtype=float)
    tail = np.abs(vals) > 5.0
    return {
        "heldout_run": int(heldout_run),
        "method": method,
        "n_pairs": int(len(frame)),
        "n_events": int(frame["event_id"].nunique()),
        "sigma68_ns": sigma68(vals),
        "full_rms_ns": full_rms(vals),
        "tail_frac_abs_gt5ns": float(tail.mean()) if len(vals) else float("nan"),
        "mae_ns": float(mean_absolute_error(np.zeros_like(vals), vals)) if len(vals) else float("nan"),
        "rmse_ns": float(math.sqrt(mean_squared_error(np.zeros_like(vals), vals))) if len(vals) else float("nan"),
    }


def run_loro(pair_frame: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    pred_rows = []
    drift_rows = []
    runs = [int(r) for r in config["timing"]["loro_runs"]]
    for fold_i, heldout_run in enumerate(runs):
        raw_train = pair_frame[pair_frame["run"] != heldout_run].copy()
        raw_held = pair_frame[pair_frame["run"] == heldout_run].copy()
        train = add_fold_atoms(raw_train, raw_train)
        held = add_fold_atoms(train, raw_held)
        combined = pd.concat([train, held], ignore_index=True)
        n_train = len(train)
        base = held[["event_id", "run", "pair", "residual_ns"]].copy()
        base["predicted_residual_ns"] = 0.0
        base["corrected_residual_ns"] = base["residual_ns"]
        base["method"] = "uncorrected_cfd20"
        pred_rows.append(base)
        rows.append(metric_row(base, "corrected_residual_ns", "uncorrected_cfd20", heldout_run))
        for method in METHOD_ORDER:
            print(f"fold heldout={heldout_run} method={method}", flush=True)
            seed = int(config["models"]["random_seed"]) + 1000 * fold_i + 31 * METHOD_ORDER.index(method)
            pred_all = fit_predict(train, combined, config, method, seed)
            pred_held = pred_all[n_train:]
            tmp = held[["event_id", "run", "pair", "residual_ns"]].copy()
            tmp["predicted_residual_ns"] = pred_held
            tmp["corrected_residual_ns"] = tmp["residual_ns"] - tmp["predicted_residual_ns"]
            tmp["method"] = method
            pred_rows.append(tmp)
            rows.append(metric_row(tmp, "corrected_residual_ns", method, heldout_run))

        train_mu = train[ALL_ATOM_FEATURES + ["max_pre_abs_adc", "max_pre_rms_adc"]].mean()
        train_sd = train[ALL_ATOM_FEATURES + ["max_pre_abs_adc", "max_pre_rms_adc"]].std(ddof=0).replace(0, np.nan)
        held_mu = held[ALL_ATOM_FEATURES + ["max_pre_abs_adc", "max_pre_rms_adc"]].mean()
        z = ((held_mu - train_mu) / train_sd).replace([np.inf, -np.inf], np.nan)
        drift_rows.append(
            {
                "heldout_run": heldout_run,
                "n_heldout_pairs": int(len(held)),
                "mean_abs_atom_z_drift": float(np.nanmean(np.abs(z.to_numpy(dtype=float)))),
                "max_abs_atom_z_drift": float(np.nanmax(np.abs(z.to_numpy(dtype=float)))),
                **{f"z_{k}": float(v) for k, v in z.to_dict().items()},
            }
        )
    return pd.DataFrame(rows), pd.concat(pred_rows, ignore_index=True), pd.DataFrame(drift_rows)


def aggregate_from_predictions(pred: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    methods = sorted(pred["method"].unique(), key=lambda m: METHOD_ORDER.index(m) + 1 if m in METHOD_ORDER else 0)
    for method in methods:
        sub = pred[pred["method"] == method].reset_index(drop=True)
        vals = sub["corrected_residual_ns"].to_numpy(dtype=float)
        row = {
            "method": method,
            "n_pairs": int(len(sub)),
            "n_events": int(sub["event_id"].nunique()),
            "mean_run_sigma68_ns": float(np.nanmean([sigma68(g["corrected_residual_ns"].to_numpy(dtype=float)) for _, g in sub.groupby("run")])),
            "pooled_sigma68_ns": sigma68(vals),
            "pooled_full_rms_ns": full_rms(vals),
            "tail_frac_abs_gt5ns": float((np.abs(vals) > float(config["timing"]["tail_abs_residual_ns"])).mean()),
            "mae_ns": float(mean_absolute_error(np.zeros_like(vals), vals)),
            "rmse_ns": float(math.sqrt(mean_squared_error(np.zeros_like(vals), vals))),
        }
        runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
        by_run = {}
        for run, run_df in sub.groupby("run"):
            by_run[int(run)] = [idx.to_numpy(dtype=int) for _, idx in run_df.groupby("event_id").groups.items()]
        stats: List[dict] = []
        for _ in range(int(config["models"]["bootstrap_samples"])):
            pieces: List[np.ndarray] = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                events = by_run[int(run)]
                chosen = rng.integers(0, len(events), size=len(events))
                pieces.extend(events[int(i)] for i in chosen)
            idx = np.concatenate(pieces)
            bvals = vals[idx]
            run_sigmas = []
            for run in runs:
                ridx = np.intersect1d(idx, np.concatenate(by_run[int(run)]), assume_unique=False)
                if len(ridx):
                    run_sigmas.append(sigma68(vals[ridx]))
            stats.append(
                {
                    "mean_run_sigma68_ns": float(np.nanmean(run_sigmas)),
                    "pooled_sigma68_ns": sigma68(bvals),
                    "tail_frac_abs_gt5ns": float((np.abs(bvals) > float(config["timing"]["tail_abs_residual_ns"])).mean()),
                    "mae_ns": float(mean_absolute_error(np.zeros_like(bvals), bvals)),
                    "rmse_ns": float(math.sqrt(mean_squared_error(np.zeros_like(bvals), bvals))),
                }
            )
        stat_df = pd.DataFrame(stats)
        for col in ["mean_run_sigma68_ns", "pooled_sigma68_ns", "tail_frac_abs_gt5ns", "mae_ns", "rmse_ns"]:
            row[f"{col}_ci_low"] = float(np.nanpercentile(stat_df[col], 2.5))
            row[f"{col}_ci_high"] = float(np.nanpercentile(stat_df[col], 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def paired_delta_ci(pred: pd.DataFrame, comparator: str, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    methods = [m for m in pred["method"].unique() if m != comparator]
    for method in methods:
        a = pred[pred["method"] == method].set_index(["event_id", "pair"]).sort_index()
        b = pred[pred["method"] == comparator].set_index(["event_id", "pair"]).sort_index()
        joined = a[["run", "corrected_residual_ns"]].join(b[["corrected_residual_ns"]], lsuffix="", rsuffix="_cmp", how="inner")
        joined = joined.reset_index()
        runs = np.asarray(sorted(joined["run"].unique()), dtype=int)
        point = sigma68(joined["corrected_residual_ns"].to_numpy()) - sigma68(joined["corrected_residual_ns_cmp"].to_numpy())
        by_run = {}
        for run, df in joined.groupby("run"):
            by_run[int(run)] = [idx.to_numpy(dtype=int) for _, idx in df.groupby("event_id").groups.items()]
        vals = joined["corrected_residual_ns"].to_numpy(dtype=float)
        cmp_vals = joined["corrected_residual_ns_cmp"].to_numpy(dtype=float)
        stats = []
        for _ in range(int(config["models"]["bootstrap_samples"])):
            pieces: List[np.ndarray] = []
            for run in rng.choice(runs, size=len(runs), replace=True):
                events = by_run[int(run)]
                chosen = rng.integers(0, len(events), size=len(events))
                pieces.extend(events[int(i)] for i in chosen)
            idx = np.concatenate(pieces)
            stats.append(sigma68(vals[idx]) - sigma68(cmp_vals[idx]))
        rows.append(
            {
                "method": method,
                "comparator": comparator,
                "delta_pooled_sigma68_ns": float(point),
                "delta_ci_low": float(np.nanpercentile(stats, 2.5)),
                "delta_ci_high": float(np.nanpercentile(stats, 97.5)),
                "n_pairs": int(len(joined)),
            }
        )
    return pd.DataFrame(rows).sort_values("delta_pooled_sigma68_ns")


def per_pair_summary(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (method, pair), sub in pred.groupby(["method", "pair"]):
        vals = sub["corrected_residual_ns"].to_numpy(dtype=float)
        rows.append(
            {
                "method": method,
                "pair": pair,
                "n_pairs": int(len(sub)),
                "n_events": int(sub["event_id"].nunique()),
                "sigma68_ns": sigma68(vals),
                "tail_frac_abs_gt5ns": float((np.abs(vals) > 5.0).mean()),
                "full_rms_ns": full_rms(vals),
            }
        )
    return pd.DataFrame(rows).sort_values(["method", "pair"])


def leakage_checks(pair_frame: pd.DataFrame, pred: pd.DataFrame, config: dict) -> pd.DataFrame:
    expected_runs = set(int(r) for r in config["timing"]["loro_runs"])
    used_runs = set(int(r) for r in pair_frame["run"].unique())
    overlaps = []
    for heldout_run in expected_runs:
        train_events = set(pair_frame[pair_frame["run"] != heldout_run]["event_id"])
        held_events = set(pair_frame[pair_frame["run"] == heldout_run]["event_id"])
        overlaps.append(len(train_events & held_events))
    forbidden = {"run", "event_id", "eventno", "evt", "residual_ns", "corrected_residual_ns"}
    feature_overlap = sorted((set(BASE_FEATURES) | set(ALL_ATOM_FEATURES) | set(TABULAR_ML_FEATURES)) & forbidden)
    return pd.DataFrame(
        [
            {"check": "loro_runs_match_config", "value": ",".join(map(str, sorted(used_runs))), "pass": used_runs == expected_runs},
            {"check": "train_heldout_event_id_overlap_max", "value": int(max(overlaps)), "pass": max(overlaps) == 0},
            {"check": "features_exclude_run_event_residual_labels", "value": ",".join(feature_overlap), "pass": len(feature_overlap) == 0},
            {"check": "all_corrected_residuals_finite", "value": int(np.isfinite(pred["corrected_residual_ns"]).sum()), "pass": bool(np.isfinite(pred["corrected_residual_ns"]).all())},
            {"check": "one_prediction_per_method_pair_row", "value": int(pred.groupby(["method", "event_id", "pair"]).size().max()), "pass": bool(pred.groupby(["method", "event_id", "pair"]).size().max() == 1)},
        ]
    )


def plot_outputs(out_dir: Path, summary: pd.DataFrame, per_run: pd.DataFrame, pred: pd.DataFrame, winner: str) -> None:
    view = summary[summary["method"].isin(METHOD_ORDER + ["uncorrected_cfd20"])].copy()
    view["order"] = view["method"].map({m: i + 1 for i, m in enumerate(METHOD_ORDER)}).fillna(0)
    view = view.sort_values("order")
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = np.arange(len(view))
    ax.errorbar(
        x,
        view["mean_run_sigma68_ns"],
        yerr=[
            view["mean_run_sigma68_ns"] - view["mean_run_sigma68_ns_ci_low"],
            view["mean_run_sigma68_ns_ci_high"] - view["mean_run_sigma68_ns"],
        ],
        fmt="o",
        capsize=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(view["method"], rotation=25, ha="right")
    ax.set_ylabel("mean run sigma68 [ns]")
    ax.set_title("S02i Sample-II LORO timing correction benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_sigma68_summary.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    for method in ["uncorrected_cfd20", "traditional_base_huber", winner]:
        sub = per_run[per_run["method"] == method].sort_values("heldout_run")
        ax.plot(sub["heldout_run"], sub["sigma68_ns"], marker="o", label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("sigma68 [ns]")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_by_run.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for method in ["uncorrected_cfd20", winner]:
        sub = pred[pred["method"] == method]
        ax.hist(sub["corrected_residual_ns"], bins=60, histtype="step", density=True, label=method)
    ax.set_xlabel("corrected pair residual [ns]")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_winner_residual_histogram.png", dpi=150)
    plt.close(fig)


def fmt_match(match: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.quantity} | {int(r.report_value)} | {int(r.reproduced)} | {int(r.delta)} | {int(r.tolerance)} | {'yes' if bool(r.pass_) else 'no'} |"
        for r in match.rename(columns={"pass": "pass_"}).itertuples()
    )


def fmt_summary(summary: pd.DataFrame) -> str:
    view = summary.copy()
    view["order"] = view["method"].map({m: i + 1 for i, m in enumerate(METHOD_ORDER)}).fillna(0)
    rows = []
    for r in view.sort_values("order").itertuples():
        rows.append(
            f"| {r.method} | {r.mean_run_sigma68_ns:.3f} [{r.mean_run_sigma68_ns_ci_low:.3f}, {r.mean_run_sigma68_ns_ci_high:.3f}] | "
            f"{r.pooled_sigma68_ns:.3f} [{r.pooled_sigma68_ns_ci_low:.3f}, {r.pooled_sigma68_ns_ci_high:.3f}] | "
            f"{r.tail_frac_abs_gt5ns:.4f} [{r.tail_frac_abs_gt5ns_ci_low:.4f}, {r.tail_frac_abs_gt5ns_ci_high:.4f}] | "
            f"{r.mae_ns:.3f} [{r.mae_ns_ci_low:.3f}, {r.mae_ns_ci_high:.3f}] |"
        )
    return "\n".join(rows)


def fmt_delta(delta: pd.DataFrame) -> str:
    return "\n".join(
        f"| {r.method} | {r.comparator} | {r.delta_pooled_sigma68_ns:+.3f} [{r.delta_ci_low:+.3f}, {r.delta_ci_high:+.3f}] |"
        for r in delta.itertuples()
    )


def fmt_per_run(per_run: pd.DataFrame, winner: str) -> str:
    sub = per_run[per_run["method"].isin(["uncorrected_cfd20", "traditional_base_huber", winner])].sort_values(["heldout_run", "method"])
    return "\n".join(
        f"| {int(r.heldout_run)} | {r.method} | {r.n_events} | {r.sigma68_ns:.3f} | {r.tail_frac_abs_gt5ns:.4f} | {r.full_rms_ns:.3f} |"
        for r in sub.itertuples()
    )


def fmt_leakage(checks: pd.DataFrame) -> str:
    return "\n".join(f"| {r.check} | {r.value} | {'yes' if bool(r.pass_) else 'no'} |" for r in checks.rename(columns={"pass": "pass_"}).itertuples())


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    md = fr"""# S02i: Pretrigger-Proxy Timing Transfer Atom Map

- **Study ID:** S02i
- **Ticket:** {config["ticket"]}
- **Worker:** {config["worker"]}
- **Date:** 2026-06-10
- **Input:** raw B-stack `h101/HRDv` ROOT files under `{config["raw_root_dir"]}`
- **Split:** Sample-II leave-one-run-out by run, held-out runs {config["timing"]["loro_runs"]}
- **Primary metric:** mean held-out-run pairwise sigma68 after correction, with run/event bootstrap 95% CIs
- **Git commit:** `{numbers["git_commit"]}`

## 1. Question And Reproduction Gate

The ticket asks which S16e-style pretrigger proxy atoms improve S02b/S02d timing closure under leave-one-run-out transfer, and where ML residual terms transfer worse than frozen traditional pretrigger corrections. Before any modeling, the script reruns the selected-pulse count gate directly from raw ROOT: the median of samples 0-3 is subtracted per B stave, and pulses with baseline-subtracted amplitude `A > 1000 ADC` are counted.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{numbers["match_rows"]}

The timing benchmark then keeps events in held-out runs where B4, B6, and B8 all pass the same cut. This produced `{numbers["n_events"]}` events and `{numbers["n_pairs"]}` pair residual rows.

## 2. Timing Target

For pair \(p=(a,b)\) in event \(i\), the uncorrected CFD20 residual is

\[
r_i = \left(t_{{ia}}^{{20}} - x_a/v\right) - \left(t_{{ib}}^{{20}} - x_b/v\right),
\]

with stave spacing \(x\) in steps of `{config["spacing_cm"]}` cm and \(1/v = {config["tof_per_cm_ns"]}\) ns/cm. A model \(f_m(X_i)\) trained only on non-held-out runs predicts the residual, and the evaluated residual is

\[
\epsilon_i^{{(m)}} = r_i - f_m(X_i).
\]

The headline resolution is

\[
\sigma_{{68}}(\epsilon) = \frac{{Q_{{84}}(\epsilon)-Q_{{16}}(\epsilon)}}{{2}},
\]

reported both per held-out run and after a paired run/event bootstrap. The tail metric is \(P(|\epsilon| > {config["timing"]["tail_abs_residual_ns"]}\,\mathrm{{ns}})\).

## 3. Traditional Atom Map

The frozen traditional comparator is a robust Huber regression on analytic timewalk features: pair identity, log mean amplitude, log amplitude ratio, inverse minimum amplitude, amplitude asymmetry, minimum amplitude, maximum peak sample, and peak-sample difference. The atom-map rows add exactly one S16e-style pretrigger atom family at a time:

- `atom_mean`: pair mean pretrigger level and inter-stave mean difference.
- `atom_slope`: pair mean pretrigger slope and inter-stave slope difference.
- `atom_early_minus_late`: samples 0-1 minus samples 2-3, averaged over staves and differenced across staves.
- `atom_quiet_proxy_bin`: train-run quartile bin of pair pretrigger RMS.
- `atom_large_lowering_flag`: train-run 95th-percentile flag for sample-0 minus sample-3 lowering.

The quiet-bin and lowering thresholds are recalculated inside each fold from training runs only.

## 4. ML And Neural Benchmarks

All ML methods use the same folds and the same train-only feature transforms. None uses run id, event id, held-out labels, or corrected residuals as inputs.

- `ridge`: Ridge regression with alpha selected by inner leave-one-train-run-out sigma68.
- `gradient_boosted_trees`: histogram gradient-boosted absolute-error regressor.
- `mlp`: two-layer MLP regressor on standardized tabular atoms.
- `cnn1d`: compact 1D convolutional regressor using only the two four-sample pretrigger traces.
- `siamese_cnn_meta`: new pair-symmetric architecture with a shared convolutional branch for each stave trace, absolute embedding difference, and tabular atom metadata.

## 5. Head-To-Head Results

| Method | Mean run sigma68 ns [95% CI] | Pooled sigma68 ns [95% CI] | Tail frac [95% CI] | MAE ns [95% CI] |
|---|---:|---:|---:|---:|
{numbers["summary_rows"]}

Winner by mean held-out-run sigma68: **{numbers["winner"]}**. The uncorrected CFD20 baseline mean run sigma68 is `{numbers["baseline_sigma"]:.3f} ns`; the best traditional row is `{numbers["best_traditional"]}` at `{numbers["best_traditional_sigma"]:.3f} ns`; the winner is `{numbers["winner_sigma"]:.3f} ns`.

Paired ML-minus-traditional and method-minus-traditional deltas use the best traditional atom row as comparator:

| Method | Comparator | Delta pooled sigma68 ns [95% CI] |
|---|---|---:|
{numbers["delta_rows"]}

Representative per-run rows:

| Held-out run | Method | n events | sigma68 ns | tail frac | full RMS ns |
|---:|---|---:|---:|---:|---:|
{numbers["per_run_rows"]}

Per-stave-pair summaries are written to `per_pair_summary.csv`. Composition drift of the pretrigger atom distribution for each held-out run is in `composition_drift.csv`; the mean absolute atom z-drift ranges from `{numbers["drift_min"]:.3f}` to `{numbers["drift_max"]:.3f}`.

## 6. Leakage, Systematics, And Caveats

| Check | Value | Pass? |
|---|---:|---|
{numbers["leakage_rows"]}

The analysis is intentionally a transfer benchmark, not a causal proof that pretrigger structure creates timing tails. Pair residual rows are not independent because each event contributes three pairs; therefore CIs resample runs and then events within sampled runs. The raw pretrigger window has only four samples, so neural architectures are deliberately small and regularized. A method that improves sigma68 may still change the accepted timing-support composition; downstream charge, PID, and energy consumers should audit support drift before adopting the correction.

The traditional Huber rows are strong but still approximate the larger S02b template/timewalk family: they keep analytic amplitude and peak-time terms and add pretrigger atoms one at a time. The ML rows are allowed to combine all atoms, so their failure or success should be read as whether flexible residual learning transfers beyond the frozen atom map, not as whether pretrigger atoms carry no information.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02i_1781032083_463_2d9c6a45_pretrigger_atom_transfer.py --config configs/s02i_1781032083_463_2d9c6a45_pretrigger_atom_transfer.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `sample_ii_pair_table.csv.gz`, `per_run_metrics.csv`, `method_summary.csv`, `method_delta_vs_best_traditional.csv`, `per_pair_summary.csv`, `composition_drift.csv`, `leakage_checks.csv`, `heldout_predictions.csv.gz`, and figures.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def output_hashes(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["models"]["random_seed"]))

    match = reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    pulses = load_sample_ii_pulses(config)
    pair_frame = build_pair_table(pulses, config)
    pair_frame.drop(columns=["pre_seq"]).to_csv(out_dir / "sample_ii_pair_table.csv.gz", index=False)

    per_run, pred, drift = run_loro(pair_frame, config)
    per_run.to_csv(out_dir / "per_run_metrics.csv", index=False)
    pred.to_csv(out_dir / "heldout_predictions.csv.gz", index=False)
    drift.to_csv(out_dir / "composition_drift.csv", index=False)

    summary = aggregate_from_predictions(pred, config, rng)
    summary.to_csv(out_dir / "method_summary.csv", index=False)

    traditional_methods = [m for m in summary["method"] if m.startswith("traditional_")]
    best_trad = summary[summary["method"].isin(traditional_methods)].sort_values(["mean_run_sigma68_ns", "tail_frac_abs_gt5ns"]).iloc[0]
    comparator = str(best_trad["method"])
    delta = paired_delta_ci(pred, comparator, config, rng)
    delta.to_csv(out_dir / "method_delta_vs_best_traditional.csv", index=False)

    pair_summary = per_pair_summary(pred)
    pair_summary.to_csv(out_dir / "per_pair_summary.csv", index=False)

    checks = leakage_checks(pair_frame, pred, config)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)

    actual = summary[summary["method"] != "uncorrected_cfd20"].copy()
    winner_row = actual.sort_values(["mean_run_sigma68_ns", "tail_frac_abs_gt5ns", "mae_ns"]).iloc[0]
    winner = str(winner_row["method"])
    plot_outputs(out_dir, summary, per_run, pred, winner)

    input_hash_rows = [{"file": str(raw_file(config, run)), "sha256": sha256_file(raw_file(config, run))} for run in configured_runs(config)]
    pd.DataFrame(input_hash_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    baseline = summary[summary["method"] == "uncorrected_cfd20"].iloc[0]
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": "2026-06-10",
        "reproduced_raw_root_first": bool(match["pass"].all()),
        "raw_reproduction": json.loads(match.to_json(orient="records")),
        "split": "Sample-II leave-one-run-out by run",
        "loro_runs": [int(r) for r in config["timing"]["loro_runs"]],
        "primary_metric": "mean held-out-run pairwise sigma68 after residual correction",
        "winner": {
            "method": winner,
            "mean_run_sigma68_ns": float(winner_row["mean_run_sigma68_ns"]),
            "ci_low": float(winner_row["mean_run_sigma68_ns_ci_low"]),
            "ci_high": float(winner_row["mean_run_sigma68_ns_ci_high"]),
            "tail_frac_abs_gt5ns": float(winner_row["tail_frac_abs_gt5ns"]),
        },
        "traditional_winner": {
            "method": comparator,
            "mean_run_sigma68_ns": float(best_trad["mean_run_sigma68_ns"]),
            "ci_low": float(best_trad["mean_run_sigma68_ns_ci_low"]),
            "ci_high": float(best_trad["mean_run_sigma68_ns_ci_high"]),
        },
        "baseline_uncorrected_cfd20": {
            "mean_run_sigma68_ns": float(baseline["mean_run_sigma68_ns"]),
            "tail_frac_abs_gt5ns": float(baseline["tail_frac_abs_gt5ns"]),
        },
        "methods": json.loads(summary.sort_values("mean_run_sigma68_ns").to_json(orient="records")),
        "best_vs_traditional_deltas": json.loads(delta.to_json(orient="records")),
        "leakage_checks_pass": bool(checks["pass"].astype(bool).all()),
        "failed_leakage_checks": json.loads(checks[~checks["pass"].astype(bool)].to_json(orient="records")),
        "composition_drift_mean_abs_z_range": [float(drift["mean_abs_atom_z_drift"].min()), float(drift["mean_abs_atom_z_drift"].max())],
        "next_tickets": [
            "Propagate the S02i winning residual correction into a charge/current/topology support-drift audit before adopting it for downstream physics selections."
        ],
        "git_commit": git_commit(),
        "runtime_seconds": float(time.time() - t0),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    numbers = {
        "git_commit": result["git_commit"],
        "match_rows": fmt_match(match),
        "n_events": int(pair_frame["event_id"].nunique()),
        "n_pairs": int(len(pair_frame)),
        "summary_rows": fmt_summary(summary),
        "winner": winner,
        "baseline_sigma": float(baseline["mean_run_sigma68_ns"]),
        "best_traditional": comparator,
        "best_traditional_sigma": float(best_trad["mean_run_sigma68_ns"]),
        "winner_sigma": float(winner_row["mean_run_sigma68_ns"]),
        "delta_rows": fmt_delta(delta),
        "per_run_rows": fmt_per_run(per_run, winner),
        "drift_min": float(drift["mean_abs_atom_z_drift"].min()),
        "drift_max": float(drift["mean_abs_atom_z_drift"].max()),
        "leakage_rows": fmt_leakage(checks),
    }
    write_report(out_dir, config, numbers)

    manifest = {
        "script": "scripts/s02i_1781032083_463_2d9c6a45_pretrigger_atom_transfer.py",
        "config": str(args.config),
        "output_dir": str(out_dir),
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}",
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "libraries": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": getattr(uproot, "__version__", "unknown"),
            "torch": getattr(torch, "__version__", "unavailable") if torch is not None else "unavailable",
        },
        "config_json": config,
        "input_sha256": input_hash_rows,
        "output_sha256": output_hashes(out_dir),
        "runtime_seconds": float(time.time() - t0),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "runtime_seconds": result["runtime_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
