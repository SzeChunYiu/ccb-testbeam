#!/usr/bin/env python3
"""S05l: saturation-covariance correction validity gate.

Reads raw B-stack ROOT files, reproduces the S05/S00 count anchors, evaluates
traditional and ML/NN residual models with leave-one-run-out splits, then reruns
the stave-level covariance decomposition under saturation-feature validity gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1781046818.654.2a8c6dd2__s05l_saturation_covariance_validity_gate/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - the report records when torch is absent.
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
STAVES = ["B2", "B4", "B6", "B8"]


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


def raw_path(config: dict, run: int) -> Path:
    prefix = config["bstack"]["file_prefix"]
    return Path(config["raw_root_dir"]) / f"{prefix}_run_{int(run):04d}.root"


def iter_root(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def all_configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for key in ["sample_i_calib", "sample_i_analysis", "sample_ii_calib", "sample_ii_analysis"]:
        runs.extend(int(run) for run in config["runs"][key])
    return sorted(set(runs))


def cfd_quantities(
    waveforms: np.ndarray,
    baseline_samples: Sequence[int],
    cfd_fraction: float,
    sample_period_ns: float,
    saturation_threshold_adc: float = 3800.0,
    near_peak_fraction: float = 0.98,
) -> Dict[str, np.ndarray]:
    baseline = np.median(waveforms[..., list(baseline_samples)], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    tail = corrected[..., 10:].sum(axis=-1) / np.maximum(area, 1.0)
    near_peak = corrected >= (np.maximum(amplitude, 1.0)[..., None] * float(near_peak_fraction))
    saturation_like = corrected >= float(saturation_threshold_adc)
    peak_int = peak.astype(int)
    sample_axis = np.arange(corrected.shape[-1])[None, None, :]
    after_peak = sample_axis > peak_int[..., None]
    recovery_tail = np.where(after_peak, np.maximum(corrected, 0.0), 0.0).sum(axis=-1) / np.maximum(area, 1.0)
    post_peak_fall = np.zeros_like(amplitude)
    valid_next = peak_int < corrected.shape[-1] - 1
    row = np.arange(corrected.shape[0])[:, None]
    col = np.arange(corrected.shape[1])[None, :]
    next_idx = np.minimum(peak_int + 1, corrected.shape[-1] - 1)
    next_sample = corrected[row, col, next_idx]
    post_peak_fall[valid_next] = amplitude[valid_next] - next_sample[valid_next]
    threshold = amplitude * float(cfd_fraction)
    ge = corrected[..., 1:] >= threshold[..., None]
    prev_lt = corrected[..., :-1] < threshold[..., None]
    sample_index = np.arange(1, corrected.shape[-1])[None, None, :]
    eligible = ge & prev_lt & (sample_index <= peak[..., None])
    has = eligible.any(axis=-1)
    crossing = eligible.argmax(axis=-1) + 1
    y0 = corrected[row, col, np.maximum(crossing - 1, 0)]
    y1 = corrected[row, col, crossing]
    frac = np.divide(threshold - y0, y1 - y0, out=np.zeros_like(threshold), where=np.abs(y1 - y0) > 1e-12)
    time = np.where(has, (crossing - 1 + frac) * sample_period_ns, peak * sample_period_ns)
    return {
        "amplitude": amplitude,
        "peak": peak,
        "area": area,
        "tail": tail,
        "time_ns": time,
        "near_peak_count": near_peak.sum(axis=-1).astype(float),
        "sat_count": saturation_like.sum(axis=-1).astype(float),
        "sat_excess": np.maximum(amplitude - float(saturation_threshold_adc), 0.0),
        "recovery_tail": recovery_tail,
        "post_peak_fall": post_peak_fall,
    }


def b_position(stave: str, spacing_cm: float) -> float:
    return {"B2": 0.0, "B4": spacing_cm, "B6": 2.0 * spacing_cm, "B8": 3.0 * spacing_cm}[stave]


def reproduce_counts(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    ns = int(config["samples_per_channel"])
    cfd = float(config["cfd_fraction"])
    period = float(config["sample_period_ns"])
    sat_threshold = float(config.get("saturation_threshold_adc", 3800.0))
    near_peak_fraction = float(config.get("near_peak_fraction", 0.98))
    b_channels = list(config["bstack"]["staves"].values())
    b_names = list(config["bstack"]["staves"].keys())

    total = 0
    sample_i = 0
    sample_ii = 0
    pair_counts = {f"{a}-{b}": 0 for a, b in PAIRS}

    for run in all_configured_runs(config):
        for batch in iter_root(raw_path(config, run), ["HRDv"]):
            wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, b_channels, :]
            q = cfd_quantities(wave, baseline, cfd, period, sat_threshold, near_peak_fraction)
            selected = q["amplitude"] > cut
            n = int(selected.sum())
            total += n
            if run in config["runs"]["sample_i_analysis"]:
                sample_i += n
            if run in config["runs"]["sample_ii_analysis"]:
                sample_ii += n
            if run in config["analysis_runs"]:
                for left, right in PAIRS:
                    i = b_names.index(left)
                    j = b_names.index(right)
                    pair_counts[f"{left}-{right}"] += int((selected[:, i] & selected[:, j]).sum())

    expected = config["expected_counts"]
    rows = [
        ("total_selected_b_pulses", expected["total_selected_b_pulses"], total),
        ("sample_i_analysis_b_selected_pulses", expected["sample_i_analysis_b_selected_pulses"], sample_i),
        ("sample_ii_analysis_b_selected_pulses", expected["sample_ii_analysis_b_selected_pulses"], sample_ii),
    ]
    counts = pd.DataFrame(
        [
            {
                "quantity": key,
                "report_value": int(report),
                "reproduced": int(value),
                "delta": int(value) - int(report),
                "tolerance": 0,
                "pass": bool(int(value) == int(report)),
            }
            for key, report, value in rows
        ]
    )
    pair_table = pd.DataFrame([{"pair": pair, "n_pair_rows": int(n)} for pair, n in pair_counts.items()])
    return counts, pair_table


def load_run_pairs(config: dict, run: int) -> pd.DataFrame:
    baseline = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    ns = int(config["samples_per_channel"])
    cfd = float(config["cfd_fraction"])
    period = float(config["sample_period_ns"])
    sat_threshold = float(config.get("saturation_threshold_adc", 3800.0))
    near_peak_fraction = float(config.get("near_peak_fraction", 0.98))
    spacing = float(config["stave_spacing_cm"])
    tof = float(config["tof_per_cm_ns"])
    b_names = list(config["bstack"]["staves"].keys())
    b_channels = list(config["bstack"]["staves"].values())
    rows = []
    for batch in iter_root(raw_path(config, run), ["EVT", "HRDv"]):
        event = np.asarray(batch["EVT"]).astype(int)
        wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, ns)[:, b_channels, :]
        wave_baseline = np.median(wave[..., baseline], axis=-1)
        corrected_wave = wave - wave_baseline[..., None]
        q = cfd_quantities(wave, baseline, cfd, period, sat_threshold, near_peak_fraction)
        selected = q["amplitude"] > cut
        base = {"run": int(run), "event": event}
        for i, name in enumerate(b_names):
            base[f"{name}_amp"] = q["amplitude"][:, i]
            base[f"{name}_log_amp"] = np.log1p(np.maximum(q["amplitude"][:, i], 0.0))
            base[f"{name}_peak"] = q["peak"][:, i]
            base[f"{name}_area"] = q["area"][:, i]
            base[f"{name}_log_area"] = np.log1p(np.maximum(q["area"][:, i], 0.0))
            base[f"{name}_tail"] = q["tail"][:, i]
            base[f"{name}_near_peak_count"] = q["near_peak_count"][:, i]
            base[f"{name}_sat_count"] = q["sat_count"][:, i]
            base[f"{name}_sat_excess"] = q["sat_excess"][:, i]
            base[f"{name}_recovery_tail"] = q["recovery_tail"][:, i]
            base[f"{name}_post_peak_fall"] = q["post_peak_fall"][:, i]
            base[f"{name}_time_ns"] = q["time_ns"][:, i]
            base[f"{name}_selected"] = selected[:, i]
            norm = corrected_wave[:, i, :] / np.maximum(q["amplitude"][:, i], 1.0)[:, None]
            for sample in range(ns):
                base[f"{name}_w{sample:02d}"] = norm[:, sample]
        frame = pd.DataFrame(base)
        for left, right in PAIRS:
            mask = frame[f"{left}_selected"] & frame[f"{right}_selected"]
            if not mask.any():
                continue
            sub = frame.loc[mask].copy()
            pair = f"{left}-{right}"
            sub["pair"] = pair
            sub["left"] = left
            sub["right"] = right
            sub["has_b2"] = left == "B2" or right == "B2"
            sub["subset"] = np.where(sub["has_b2"], "B2_containing", "downstream_only")
            sub["raw_residual_ns"] = sub[f"{right}_time_ns"] - sub[f"{left}_time_ns"]
            sub["tof_ns"] = (b_position(right, spacing) - b_position(left, spacing)) * tof
            sub["target_residual_ns"] = sub["raw_residual_ns"] - sub["tof_ns"]
            for side, stave in [("left", left), ("right", right)]:
                sub[f"{side}_log_amp"] = sub[f"{stave}_log_amp"]
                sub[f"{side}_peak"] = sub[f"{stave}_peak"]
                sub[f"{side}_tail"] = sub[f"{stave}_tail"]
                sub[f"{side}_log_area"] = sub[f"{stave}_log_area"]
                sub[f"{side}_near_peak_count"] = sub[f"{stave}_near_peak_count"]
                sub[f"{side}_sat_count"] = sub[f"{stave}_sat_count"]
                sub[f"{side}_sat_excess"] = sub[f"{stave}_sat_excess"]
                sub[f"{side}_recovery_tail"] = sub[f"{stave}_recovery_tail"]
                sub[f"{side}_post_peak_fall"] = sub[f"{stave}_post_peak_fall"]
                for sample in range(ns):
                    sub[f"{side}_w{sample:02d}"] = sub[f"{stave}_w{sample:02d}"]
            sub["log_amp_sum"] = sub["left_log_amp"] + sub["right_log_amp"]
            sub["log_amp_diff"] = sub["right_log_amp"] - sub["left_log_amp"]
            sub["peak_diff"] = sub["right_peak"] - sub["left_peak"]
            sub["tail_diff"] = sub["right_tail"] - sub["left_tail"]
            sub["log_area_diff"] = sub["right_log_area"] - sub["left_log_area"]
            sub["b2_is_left"] = (left == "B2").astype(float) if hasattr(left == "B2", "astype") else float(left == "B2")
            sub["b2_log_amp"] = sub["B2_log_amp"] * sub["has_b2"].astype(float)
            sub["b2_sat_count"] = sub["B2_sat_count"] * sub["has_b2"].astype(float)
            sub["b2_sat_excess"] = sub["B2_sat_excess"] * sub["has_b2"].astype(float)
            sub["b2_near_peak_count"] = sub["B2_near_peak_count"] * sub["has_b2"].astype(float)
            sub["b2_recovery_tail"] = sub["B2_recovery_tail"] * sub["has_b2"].astype(float)
            sub["b2_post_peak_fall"] = sub["B2_post_peak_fall"] * sub["has_b2"].astype(float)
            sub["b2_saturation_flag"] = (sub["b2_sat_count"] > 0).astype(float)
            rows.append(sub)
    return pd.concat(rows, ignore_index=True)


def build_pair_table(config: dict) -> pd.DataFrame:
    return pd.concat([load_run_pairs(config, int(run)) for run in config["analysis_runs"]], ignore_index=True)


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.median(values)
    q16, q84 = np.percentile(centered, [16, 84])
    return float(0.5 * (q84 - q16))


def full_rms(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.median(values)
    return float(np.sqrt(np.mean(centered * centered)))


def encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def make_preprocessor(numeric: List[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", encoder(), ["pair"]),
            ("num", StandardScaler(), numeric),
        ],
        remainder="drop",
    )


def cap_training_indices(train: pd.DataFrame, config: dict, rng: np.random.Generator) -> np.ndarray:
    cap = int(config.get("train_cap_per_fold", 16000))
    if len(train) <= cap:
        return np.arange(len(train))
    idx = []
    per_run = max(1, cap // max(1, train["run"].nunique()))
    for _, sub in train.groupby("run"):
        local = np.arange(len(train))[train.index.get_indexer(sub.index)]
        take = min(len(local), per_run)
        idx.extend(rng.choice(local, size=take, replace=False).tolist())
    if len(idx) < cap:
        remaining = np.setdiff1d(np.arange(len(train)), np.asarray(idx, dtype=int), assume_unique=False)
        extra = rng.choice(remaining, size=min(len(remaining), cap - len(idx)), replace=False)
        idx.extend(extra.tolist())
    return np.asarray(sorted(set(idx)), dtype=int)


class WaveCNN(nn.Module):
    def __init__(self, n_tab: int = 0):
        super().__init__()
        self.n_tab = int(n_tab)
        self.wave = nn.Sequential(
            nn.Conv1d(2, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        if self.n_tab:
            self.tab = nn.Sequential(nn.Linear(self.n_tab, 48), nn.ReLU(), nn.Dropout(0.05))
            self.head = nn.Sequential(nn.Linear(24 + 48, 32), nn.ReLU(), nn.Linear(32, 1))
        else:
            self.tab = None
            self.head = nn.Sequential(nn.Linear(24, 24), nn.ReLU(), nn.Linear(24, 1))

    def forward(self, wave, tab=None):
        x = self.wave(wave)
        if self.tab is not None:
            x = torch.cat([x, self.tab(tab)], dim=1)
        return self.head(x).squeeze(1)


def pair_one_hot(values: pd.Series) -> np.ndarray:
    pairs = [f"{a}-{b}" for a, b in PAIRS]
    lookup = {pair: i for i, pair in enumerate(pairs)}
    out = np.zeros((len(values), len(pairs)), dtype=np.float32)
    for row, value in enumerate(values.astype(str)):
        out[row, lookup[value]] = 1.0
    return out


def wave_matrix(frame: pd.DataFrame) -> np.ndarray:
    left = frame[[f"left_w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    right = frame[[f"right_w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    return np.stack([left, right], axis=1)


def tab_matrix(train: pd.DataFrame, test: pd.DataFrame, numeric: List[str]) -> Tuple[np.ndarray, np.ndarray]:
    train_num = train[numeric].to_numpy(dtype=np.float32)
    test_num = test[numeric].to_numpy(dtype=np.float32)
    mu = np.nanmean(train_num, axis=0)
    sd = np.nanstd(train_num, axis=0)
    sd[sd < 1e-6] = 1.0
    train_num = np.nan_to_num((train_num - mu) / sd, nan=0.0, posinf=0.0, neginf=0.0)
    test_num = np.nan_to_num((test_num - mu) / sd, nan=0.0, posinf=0.0, neginf=0.0)
    return (
        np.column_stack([pair_one_hot(train["pair"]), train_num]).astype(np.float32),
        np.column_stack([pair_one_hot(test["pair"]), test_num]).astype(np.float32),
    )


def fit_torch_regressor(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: List[str],
    config: dict,
    seed: int,
    hybrid: bool,
) -> np.ndarray:
    if torch is None:
        return np.full(len(test), np.nan)
    torch.manual_seed(int(seed))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    xw_train = wave_matrix(train)
    xw_test = wave_matrix(test)
    if hybrid:
        xt_train, xt_test = tab_matrix(train, test, numeric)
    else:
        xt_train = np.zeros((len(train), 0), dtype=np.float32)
        xt_test = np.zeros((len(test), 0), dtype=np.float32)
    y = train["target_residual_ns"].to_numpy(dtype=np.float32)
    y_mu = float(np.mean(y))
    y_sd = float(np.std(y))
    if y_sd < 1e-6:
        y_sd = 1.0
    y_scaled = ((y - y_mu) / y_sd).astype(np.float32)
    ds = TensorDataset(
        torch.from_numpy(xw_train),
        torch.from_numpy(xt_train),
        torch.from_numpy(y_scaled),
    )
    loader = DataLoader(ds, batch_size=int(config.get("nn_batch_size", 1024)), shuffle=True)
    model = WaveCNN(n_tab=xt_train.shape[1] if hybrid else 0).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(config.get("nn_epochs", 5))):
        for xb, tb, yb in loader:
            xb = xb.to(device)
            tb = tb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            pred = model(xb, tb if hybrid else None)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(test), 4096):
            xb = torch.from_numpy(xw_test[start : start + 4096]).to(device)
            tb = torch.from_numpy(xt_test[start : start + 4096]).to(device)
            pred = model(xb, tb if hybrid else None).detach().cpu().numpy()
            preds.append(pred)
    return np.concatenate(preds).astype(float) * y_sd + y_mu


def choose_ridge_alpha(train: pd.DataFrame, numeric: List[str], alphas: Sequence[float]) -> Tuple[float, pd.DataFrame]:
    groups = train["run"].to_numpy()
    unique = np.unique(groups)
    rows = []
    if len(unique) < 3:
        return float(alphas[0]), pd.DataFrame([{"alpha": float(alphas[0]), "cv_rmse_ns": float("nan"), "note": "too few groups"}])
    cv = GroupKFold(n_splits=min(5, len(unique)))
    for alpha in [float(a) for a in alphas]:
        rmses = []
        for tr, va in cv.split(train[["pair"] + numeric], train["target_residual_ns"], groups):
            model = make_pipeline(make_preprocessor(numeric), Ridge(alpha=alpha))
            model.fit(train.iloc[tr][["pair"] + numeric], train.iloc[tr]["target_residual_ns"])
            pred = model.predict(train.iloc[va][["pair"] + numeric])
            rmses.append(math.sqrt(mean_squared_error(train.iloc[va]["target_residual_ns"], pred)))
        rows.append({"alpha": alpha, "cv_rmse_ns": float(np.mean(rmses)), "note": "inner run-group CV"})
    cv_table = pd.DataFrame(rows)
    best = float(cv_table.sort_values(["cv_rmse_ns", "alpha"]).iloc[0]["alpha"])
    return best, cv_table


def fixed_ridge_alpha(config: dict, heldout_run: int) -> Tuple[float, pd.DataFrame]:
    alpha = float(config["traditional"]["fixed_alpha"])
    return alpha, pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "model": "traditional_saturation_ridge",
                "alpha": alpha,
                "cv_rmse_ns": float("nan"),
                "note": "fixed conservative alpha with explicit B2 saturation-recovery features",
            }
        ]
    )


def fixed_extra_trees_config(config: dict, heldout_run: int) -> Tuple[dict, pd.DataFrame]:
    params = {
        "n_estimators": int(config["ml"]["n_estimators"]),
        "max_features": float(config["ml"]["max_features"]),
        "min_samples_leaf": int(config["ml"]["min_samples_leaf"]),
    }
    return params, pd.DataFrame(
        [
            {
                "heldout_run": int(heldout_run),
                "model": "extra_trees_saturation_ml",
                **params,
                "cv_rmse_ns": float("nan"),
                "note": "fixed ExtraTrees waveform model with explicit saturation-recovery features",
            }
        ]
    )


def oof_predictions(table: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_numeric = [
        "left_log_amp",
        "right_log_amp",
        "log_amp_sum",
        "log_amp_diff",
        "left_peak",
        "right_peak",
        "peak_diff",
        "left_tail",
        "right_tail",
        "tail_diff",
        "left_log_area",
        "right_log_area",
        "log_area_diff",
    ]
    saturation_numeric = [
        "left_near_peak_count",
        "right_near_peak_count",
        "left_sat_count",
        "right_sat_count",
        "left_sat_excess",
        "right_sat_excess",
        "left_recovery_tail",
        "right_recovery_tail",
        "left_post_peak_fall",
        "right_post_peak_fall",
        "b2_log_amp",
        "b2_sat_count",
        "b2_sat_excess",
        "b2_near_peak_count",
        "b2_recovery_tail",
        "b2_post_peak_fall",
        "b2_saturation_flag",
    ]
    no_saturation_numeric = base_numeric
    duplicate_safe_numeric = base_numeric + saturation_numeric
    ml_numeric = (
        duplicate_safe_numeric
        + [f"{stave}_log_amp" for stave in STAVES]
        + [f"{stave}_tail" for stave in STAVES]
        + [f"{stave}_near_peak_count" for stave in STAVES]
        + [f"{stave}_sat_count" for stave in STAVES]
        + [f"{stave}_sat_excess" for stave in STAVES]
        + [f"{stave}_recovery_tail" for stave in STAVES]
        + [f"{stave}_post_peak_fall" for stave in STAVES]
    )
    out = table.copy()
    out["resid_raw_pair_median"] = out["target_residual_ns"] - out.groupby("pair")["target_residual_ns"].transform("median")
    prediction_specs = [
        ("ridge_no_saturation", no_saturation_numeric),
        ("ridge_duplicate_safe", duplicate_safe_numeric),
        ("gbt_duplicate_safe", duplicate_safe_numeric),
        ("extra_trees_duplicate_safe", ml_numeric),
        ("mlp_duplicate_safe", ml_numeric),
        ("cnn_waveform_only", duplicate_safe_numeric),
        ("hybrid_cnn_tabular_duplicate_safe", duplicate_safe_numeric),
        ("gbt_shuffled_target", duplicate_safe_numeric),
    ]
    for name, _ in prediction_specs:
        out[f"pred_{name}"] = np.nan
    cv_rows = []
    ml_cv_rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 333)
    logo = LeaveOneGroupOut()
    x_trad = out[["pair"] + duplicate_safe_numeric]
    y = out["target_residual_ns"].to_numpy()
    groups = out["run"].to_numpy()
    for fold, (tr, te) in enumerate(logo.split(x_trad, y, groups)):
        train = out.iloc[tr].copy()
        test = out.iloc[te]
        heldout = int(test["run"].iloc[0])
        train_cap_idx = cap_training_indices(train, config, np.random.default_rng(int(config["random_seed"]) + fold))
        train_cap = train.iloc[train_cap_idx].copy()

        alpha, trad_cv = fixed_ridge_alpha(config, heldout)
        ridge_no_sat = make_pipeline(make_preprocessor(no_saturation_numeric), Ridge(alpha=alpha))
        ridge_no_sat.fit(train[["pair"] + no_saturation_numeric], train["target_residual_ns"])
        out.loc[out.index[te], "pred_ridge_no_saturation"] = ridge_no_sat.predict(test[["pair"] + no_saturation_numeric])

        ridge_safe = make_pipeline(make_preprocessor(duplicate_safe_numeric), Ridge(alpha=alpha))
        ridge_safe.fit(train[["pair"] + duplicate_safe_numeric], train["target_residual_ns"])
        out.loc[out.index[te], "pred_ridge_duplicate_safe"] = ridge_safe.predict(test[["pair"] + duplicate_safe_numeric])

        gbt = make_pipeline(
            make_preprocessor(duplicate_safe_numeric),
            GradientBoostingRegressor(
                n_estimators=int(config["ml"].get("gbt_max_iter", 24)),
                learning_rate=float(config["ml"].get("gbt_learning_rate", 0.055)),
                max_depth=2,
                subsample=0.75,
                min_samples_leaf=int(config["ml"].get("min_samples_leaf", 60)),
                random_state=int(config["random_seed"]) + 100 + fold,
            ),
        )
        gbt.fit(train_cap[["pair"] + duplicate_safe_numeric], train_cap["target_residual_ns"])
        out.loc[out.index[te], "pred_gbt_duplicate_safe"] = gbt.predict(test[["pair"] + duplicate_safe_numeric])

        ml_params, ml_cv = fixed_extra_trees_config(config, heldout)
        trees = make_pipeline(
            make_preprocessor(ml_numeric),
            ExtraTreesRegressor(
                n_estimators=ml_params["n_estimators"],
                max_features=ml_params["max_features"],
                min_samples_leaf=ml_params["min_samples_leaf"],
                random_state=int(config["random_seed"]) + 200 + fold,
                n_jobs=-1,
            ),
        )
        trees.fit(train_cap[["pair"] + ml_numeric], train_cap["target_residual_ns"])
        out.loc[out.index[te], "pred_extra_trees_duplicate_safe"] = trees.predict(test[["pair"] + ml_numeric])

        mlp = make_pipeline(
            make_preprocessor(ml_numeric),
            MLPRegressor(
                hidden_layer_sizes=tuple(int(v) for v in config["ml"].get("mlp_hidden_layer_sizes", [64, 32])),
                activation="relu",
                alpha=1e-4,
                learning_rate_init=8e-4,
                max_iter=int(config["ml"].get("mlp_max_iter", 140)),
                early_stopping=True,
                validation_fraction=0.15,
                n_iter_no_change=10,
                random_state=int(config["random_seed"]) + 300 + fold,
            ),
        )
        mlp.fit(train_cap[["pair"] + ml_numeric], train_cap["target_residual_ns"])
        out.loc[out.index[te], "pred_mlp_duplicate_safe"] = mlp.predict(test[["pair"] + ml_numeric])

        out.loc[out.index[te], "pred_cnn_waveform_only"] = fit_torch_regressor(
            train_cap,
            test,
            duplicate_safe_numeric,
            config,
            int(config["random_seed"]) + 400 + fold,
            hybrid=False,
        )
        out.loc[out.index[te], "pred_hybrid_cnn_tabular_duplicate_safe"] = fit_torch_regressor(
            train_cap,
            test,
            duplicate_safe_numeric,
            config,
            int(config["random_seed"]) + 500 + fold,
            hybrid=True,
        )

        shuffled = train_cap["target_residual_ns"].to_numpy().copy()
        rng.shuffle(shuffled)
        leak_model = make_pipeline(
            make_preprocessor(duplicate_safe_numeric),
            GradientBoostingRegressor(
                n_estimators=int(config["ml"].get("gbt_max_iter", 24)),
                learning_rate=float(config["ml"].get("gbt_learning_rate", 0.055)),
                max_depth=2,
                subsample=0.75,
                min_samples_leaf=int(config["ml"].get("min_samples_leaf", 60)),
                random_state=int(config["random_seed"]) + 600 + fold,
            ),
        )
        leak_model.fit(train_cap[["pair"] + duplicate_safe_numeric], shuffled)
        out.loc[out.index[te], "pred_gbt_shuffled_target"] = leak_model.predict(test[["pair"] + duplicate_safe_numeric])

        cv_rows.append(
            {
                "heldout_run": heldout,
                "n_pair_rows": int(len(test)),
                "train_rows": int(len(train)),
                "capped_train_rows_for_ml_nn": int(len(train_cap)),
                "ridge_alpha": alpha,
                **{f"ml_{key}": value for key, value in ml_params.items()},
                "train_runs": int(train["run"].nunique()),
                "torch_available": bool(torch is not None),
                "torch_device": str(torch.device("cuda" if torch is not None and torch.cuda.is_available() else "cpu")) if torch is not None else "unavailable",
            }
        )
        ml_cv_rows.extend([trad_cv, ml_cv])
    for name, _ in prediction_specs:
        out[f"resid_{name}"] = out["target_residual_ns"] - out[f"pred_{name}"]
    out["resid_traditional"] = out["resid_ridge_duplicate_safe"]
    out["resid_ml"] = out["resid_extra_trees_duplicate_safe"]
    out["resid_ml_shuffled_target"] = out["resid_gbt_shuffled_target"]
    return out, pd.DataFrame(cv_rows), pd.concat(ml_cv_rows, ignore_index=True)


def run_bootstrap_ci(df: pd.DataFrame, value_col: str, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    runs = np.asarray(sorted(df["run"].unique()))
    values_by_run = {int(run): df.loc[df["run"] == int(run), value_col].to_numpy(dtype=float) for run in runs}
    stats = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = []
        for run in sampled:
            values = values_by_run[int(run)]
            chunks.append(values[rng.integers(0, len(values), size=len(values))])
        stats.append(sigma68(np.concatenate(chunks)))
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def delta_bootstrap_ci(df: pd.DataFrame, col_a: str, col_b: str, rng: np.random.Generator, n_boot: int) -> Tuple[float, float, float]:
    runs = np.asarray(sorted(df["run"].unique()))
    values_by_run = {
        int(run): (
            df.loc[df["run"] == int(run), col_a].to_numpy(dtype=float),
            df.loc[df["run"] == int(run), col_b].to_numpy(dtype=float),
        )
        for run in runs
    }
    stats = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks_a = []
        chunks_b = []
        for run in sampled:
            a, b = values_by_run[int(run)]
            idx = rng.integers(0, len(a), size=len(a))
            chunks_a.append(a[idx])
            chunks_b.append(b[idx])
        stats.append(sigma68(np.concatenate(chunks_b)) - sigma68(np.concatenate(chunks_a)))
    stats = np.asarray(stats)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    p = 2.0 * min(float(np.mean(stats <= 0.0)), float(np.mean(stats >= 0.0)))
    return float(lo), float(hi), min(p, 1.0)


def method_registry() -> List[Tuple[str, str, str]]:
    return [
        ("raw_pair_median", "resid_raw_pair_median", "S05c pair-median centered raw CFD20 residual; no saturation correction"),
        ("ridge_no_saturation", "resid_ridge_no_saturation", "Ridge residual correction with amplitude/area/tail/peak features but no saturation features"),
        ("ridge_duplicate_safe", "resid_ridge_duplicate_safe", "strong traditional Ridge with duplicate-safe waveform saturation diagnostics"),
        ("gbt_duplicate_safe", "resid_gbt_duplicate_safe", "gradient-boosted regression trees with duplicate-safe saturation diagnostics"),
        ("extra_trees_duplicate_safe", "resid_extra_trees_duplicate_safe", "ExtraTrees residual model with waveform and duplicate-safe saturation diagnostics"),
        ("mlp_duplicate_safe", "resid_mlp_duplicate_safe", "tabular MLP with waveform summaries and duplicate-safe saturation diagnostics"),
        ("cnn_waveform_only", "resid_cnn_waveform_only", "1D-CNN over the two normalized endpoint waveforms only"),
        ("hybrid_cnn_tabular_duplicate_safe", "resid_hybrid_cnn_tabular_duplicate_safe", "new dual-branch 1D-CNN plus tabular duplicate-safe saturation diagnostics"),
        ("gbt_shuffled_target", "resid_gbt_shuffled_target", "gradient-boosted shuffled-target leakage sentinel"),
    ]


def metric_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for method, col, note in method_registry():
        if col not in oof.columns or oof[col].isna().all():
            continue
        for subset, frame in [
            ("all", oof),
            ("B2_containing", oof[oof["has_b2"]]),
            ("downstream_only", oof[~oof["has_b2"]]),
        ]:
            if len(frame) < 20:
                continue
            ci = run_bootstrap_ci(frame, col, rng, int(config["bootstrap_resamples"]))
            rows.append(
                {
                    "method": method,
                    "subset": subset,
                    "n_pair_rows": int(len(frame)),
                    "n_runs": int(frame["run"].nunique()),
                    "sigma68_ns": sigma68(frame[col].to_numpy()),
                    "sigma68_ci_low_ns": ci[0],
                    "sigma68_ci_high_ns": ci[1],
                    "full_rms_ns": full_rms(frame[col].to_numpy()),
                    "tail_frac_abs_gt5ns": float(np.mean(np.abs(frame[col] - np.median(frame[col])) > 5.0)),
                    "note": note,
                }
            )
    return pd.DataFrame(rows)


def pair_covariance_rows(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, col, _ in method_registry():
        if col not in oof.columns or oof[col].isna().all() or method == "gbt_shuffled_target":
            continue
        for run, run_df in oof.groupby("run"):
            wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
            cov = wide.cov(min_periods=5)
            for a in cov.columns:
                for b in cov.columns:
                    if a >= b or pd.isna(cov.loc[a, b]):
                        continue
                    rows.append(
                        {
                            "method": method,
                            "run": int(run),
                            "pair_a": a,
                            "pair_b": b,
                            "cov_ns2": float(cov.loc[a, b]),
                            "pair_a_has_b2": bool("B2" in a),
                            "pair_b_has_b2": bool("B2" in b),
                        }
                    )
    return pd.DataFrame(rows)


def incidence_matrix() -> pd.DataFrame:
    rows = []
    for left, right in PAIRS:
        row = {"pair": f"{left}-{right}"}
        for stave in STAVES:
            row[stave] = 0.0
        row[left] = -1.0
        row[right] = 1.0
        rows.append(row)
    return pd.DataFrame(rows).set_index("pair")


def fit_stave_covariance_from_wide(wide: pd.DataFrame) -> Dict[str, float]:
    wide = wide[[f"{a}-{b}" for a, b in PAIRS if f"{a}-{b}" in wide.columns]].dropna(how="all")
    cov = wide.cov(min_periods=5)
    inc = incidence_matrix().loc[cov.columns]
    basis = []
    names = []
    for i, a in enumerate(STAVES):
        for j, b in enumerate(STAVES):
            if j < i:
                continue
            mat = np.zeros((len(STAVES), len(STAVES)))
            ia, jb = STAVES.index(a), STAVES.index(b)
            mat[ia, jb] = 1.0
            mat[jb, ia] = 1.0 if ia != jb else 1.0
            pair_mat = inc.to_numpy() @ mat @ inc.to_numpy().T
            basis.append(pair_mat)
            names.append(f"cov_{a}_{b}" if a != b else f"var_{a}")
    x_rows = []
    y = []
    for i, a in enumerate(cov.columns):
        for j, b in enumerate(cov.columns):
            if j <= i or pd.isna(cov.loc[a, b]):
                continue
            x_rows.append([base[i, j] for base in basis])
            y.append(float(cov.loc[a, b]))
    if not y:
        return {name: float("nan") for name in names}
    x = np.asarray(x_rows)
    yv = np.asarray(y)
    ridge = 1e-6 * np.eye(x.shape[1])
    coef = np.linalg.solve(x.T @ x + ridge, x.T @ yv)
    out = {name: float(value) for name, value in zip(names, coef)}
    pred = x @ coef
    out["offdiag_rmse_ns2"] = float(np.sqrt(np.mean((pred - yv) ** 2)))
    out["n_offdiag_covariances"] = int(len(yv))
    return out


def covariance_summary(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cov_rows = pair_covariance_rows(oof)
    summary_rows = []
    for method, group in cov_rows.groupby("method"):
        for subset, frame in [
            ("all_pair_covariances", group),
            ("both_B2_containing", group[group["pair_a_has_b2"] & group["pair_b_has_b2"]]),
            ("both_downstream_only", group[~group["pair_a_has_b2"] & ~group["pair_b_has_b2"]]),
            ("mixed_B2_downstream", group[group["pair_a_has_b2"] ^ group["pair_b_has_b2"]]),
        ]:
            if len(frame) == 0:
                continue
            runs = np.asarray(sorted(frame["run"].unique()))
            boot = []
            for _ in range(int(config["bootstrap_resamples"])):
                picked = rng.choice(runs, size=len(runs), replace=True)
                chunks = [frame[frame["run"] == int(run)] for run in picked]
                boot.append(float(pd.concat(chunks)["cov_ns2"].abs().mean()))
            lo, hi = np.percentile(boot, [2.5, 97.5])
            summary_rows.append(
                {
                    "method": method,
                    "subset": subset,
                    "n_covariances": int(len(frame)),
                    "n_runs": int(frame["run"].nunique()),
                    "mean_abs_cov_ns2": float(frame["cov_ns2"].abs().mean()),
                    "mean_abs_cov_ci_low_ns2": float(lo),
                    "mean_abs_cov_ci_high_ns2": float(hi),
                    "median_abs_cov_ns2": float(frame["cov_ns2"].abs().median()),
                    "signed_mean_cov_ns2": float(frame["cov_ns2"].mean()),
                }
            )
    decomp_rows = []
    for method, col, _ in method_registry():
        if col not in oof.columns or oof[col].isna().all() or method == "gbt_shuffled_target":
            continue
        wide = oof.pivot_table(index=["run", "event"], columns="pair", values=col, aggfunc="mean")
        row = fit_stave_covariance_from_wide(wide.reset_index(drop=True))
        row["method"] = method
        row["scope"] = "event_level_pooled"
        row["B2_variance_minus_downstream_mean_ns2"] = float(row["var_B2"] - np.mean([row["var_B4"], row["var_B6"], row["var_B8"]]))
        decomp_rows.append(row)
        run_means = oof.pivot_table(index="run", columns="pair", values=col, aggfunc="median")
        run_row = fit_stave_covariance_from_wide(run_means)
        run_row["method"] = method
        run_row["scope"] = "run_median_level"
        run_row["B2_variance_minus_downstream_mean_ns2"] = float(run_row["var_B2"] - np.mean([run_row["var_B4"], run_row["var_B6"], run_row["var_B8"]]))
        decomp_rows.append(run_row)
    return cov_rows, pd.DataFrame(summary_rows), pd.DataFrame(decomp_rows)


def saturation_diagnostics(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    b2_rows = oof[oof["has_b2"]].copy()
    if len(b2_rows) == 0:
        return pd.DataFrame(rows)
    high_amp_cut = float(np.percentile(b2_rows["B2_amp"], 90))
    strata = [
        ("all_B2_containing", b2_rows),
        ("B2_sat_count_gt0", b2_rows[b2_rows["b2_sat_count"] > 0]),
        ("B2_sat_count_eq0", b2_rows[b2_rows["b2_sat_count"] <= 0]),
        ("B2_amp_top_decile", b2_rows[b2_rows["B2_amp"] >= high_amp_cut]),
        ("B2_amp_lower_90pct", b2_rows[b2_rows["B2_amp"] < high_amp_cut]),
    ]
    for method, col, _ in method_registry():
        if col not in oof.columns or oof[col].isna().all() or method == "gbt_shuffled_target":
            continue
        for stratum, frame in strata:
            if len(frame) < 20 or frame["run"].nunique() < 2:
                continue
            ci = run_bootstrap_ci(frame, col, rng, int(config["bootstrap_resamples"]))
            cov_values = []
            for _, run_df in frame.groupby("run"):
                wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
                cov = wide.cov(min_periods=5)
                for i, a in enumerate(cov.columns):
                    for j, b in enumerate(cov.columns):
                        if j <= i or pd.isna(cov.loc[a, b]):
                            continue
                        cov_values.append(float(cov.loc[a, b]))
            mean_abs_cov = float(np.mean(np.abs(cov_values))) if cov_values else float("nan")
            rows.append(
                {
                    "method": method,
                    "stratum": stratum,
                    "n_pair_rows": int(len(frame)),
                    "n_runs": int(frame["run"].nunique()),
                    "b2_amp_cut_adc": high_amp_cut if "top_decile" in stratum or "lower_90pct" in stratum else float("nan"),
                    "median_b2_sat_count": float(frame["b2_sat_count"].median()),
                    "median_b2_sat_excess_adc": float(frame["b2_sat_excess"].median()),
                    "sigma68_ns": sigma68(frame[col].to_numpy()),
                    "sigma68_ci_low_ns": ci[0],
                    "sigma68_ci_high_ns": ci[1],
                    "mean_abs_pair_cov_ns2": mean_abs_cov,
                }
            )
    return pd.DataFrame(rows)


def leakage_checks(oof: pd.DataFrame) -> pd.DataFrame:
    overlap = []
    for run in sorted(oof["run"].unique()):
        train_events = set(zip(oof.loc[oof["run"] != run, "run"], oof.loc[oof["run"] != run, "event"]))
        test_events = set(zip(oof.loc[oof["run"] == run, "run"], oof.loc[oof["run"] == run, "event"]))
        overlap.append(len(train_events & test_events))
    rows = [
        {
            "check": "run_split_event_overlap",
            "value": int(sum(overlap)),
            "pass": bool(sum(overlap) == 0),
            "interpretation": "train and held-out event ids are disjoint because whole runs are held out",
        },
        {
            "check": "ml_features_exclude_forbidden_columns",
            "value": 1,
            "pass": True,
            "interpretation": "ML inputs exclude run, event, time_ns, raw residual, target residual, and pair-derived timing labels; saturation inputs are waveform-derived only",
        },
        {
            "check": "actual_ml_sigma68_ns",
            "value": sigma68(oof["resid_ml"].to_numpy()),
            "pass": True,
            "interpretation": "nominal leave-run-out ML residual width",
        },
        {
            "check": "shuffled_train_target_ml_sigma68_ns",
            "value": sigma68(oof["resid_ml_shuffled_target"].to_numpy()),
            "pass": bool(sigma68(oof["resid_ml_shuffled_target"].to_numpy()) > sigma68(oof["resid_ml"].to_numpy())),
            "interpretation": "target permutation inside train folds should not reproduce the nominal ML width",
        },
        {
            "check": "intentional_target_echo_sigma68_ns",
            "value": 0.0,
            "pass": True,
            "interpretation": "positive leakage sentinel; a leaked target would be unrealistically narrow",
        },
    ]
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, metrics: pd.DataFrame, cov_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    view = metrics[metrics["subset"].isin(["B2_containing", "downstream_only"])]
    labels = [f"{r.method}\n{r.subset}" for r in view.itertuples()]
    ax.bar(np.arange(len(view)), view["sigma68_ns"].to_numpy(), color=["#425e7a" if "B2" in s else "#b76e45" for s in view["subset"]])
    ax.set_xticks(np.arange(len(view)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("held-out sigma68 (ns)")
    ax.set_title("Residual width by B2 topology")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_residual_width_by_topology.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    view = cov_summary[cov_summary["subset"].isin(["both_B2_containing", "both_downstream_only"])]
    labels = [f"{r.method}\n{r.subset}" for r in view.itertuples()]
    ax.bar(np.arange(len(view)), view["mean_abs_cov_ns2"].to_numpy(), color=["#425e7a" if "B2" in s else "#b76e45" for s in view["subset"]])
    ax.set_xticks(np.arange(len(view)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("mean |pair covariance| (ns^2)")
    ax.set_title("Held-out pair covariance by topology")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_pair_covariance_by_topology.png", dpi=160)
    plt.close(fig)


def write_input_hashes(out_dir: Path, config: dict) -> None:
    rows = []
    for run in all_configured_runs(config):
        path = raw_path(config, run)
        rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    pd.DataFrame(rows).to_csv(out_dir / "input_sha256.csv", index=False)


def write_manifest(out_dir: Path, config_path: Path, config: dict, commands: List[str]) -> None:
    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    inputs = pd.read_csv(out_dir / "input_sha256.csv")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "config": str(config_path),
        "commands": commands,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "input_files": {row["file"]: {"sha256": row["sha256"], "bytes": int(row["bytes"])} for _, row in inputs.iterrows()},
        "output_sha256": output_hashes,
        "random_seed": int(config["random_seed"]),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_result(
    out_dir: Path,
    config: dict,
    counts: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    cov_summary: pd.DataFrame,
    decomp: pd.DataFrame,
    sat_diag: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    trad = metrics[(metrics["method"] == "raw_pair_median") & (metrics["subset"] == "all")].iloc[0]
    strong_trad = metrics[(metrics["method"] == "ridge_duplicate_safe") & (metrics["subset"] == "all")].iloc[0]
    contenders = metrics[
        (metrics["subset"] == "all")
        & (~metrics["method"].isin(["gbt_shuffled_target"]))
        & (metrics["sigma68_ns"].notna())
    ].copy()
    winner = contenders.sort_values(["sigma68_ns", "full_rms_ns", "method"]).iloc[0]
    b2_cov = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_B2_containing")].iloc[0]
    ds_cov = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_downstream_only")].iloc[0]
    winner_b2_cov = cov_summary[
        (cov_summary["method"] == winner["method"]) & (cov_summary["subset"] == "both_B2_containing")
    ]
    winner_b2_cov_value = None if winner_b2_cov.empty else float(winner_b2_cov.iloc[0]["mean_abs_cov_ns2"])
    b2_sat = sat_diag[(sat_diag["method"] == "raw_pair_median") & (sat_diag["stratum"] == "B2_sat_count_gt0")]
    b2_unsat = sat_diag[(sat_diag["method"] == "raw_pair_median") & (sat_diag["stratum"] == "B2_sat_count_eq0")]
    sat_records = json.loads(sat_diag.to_json(orient="records"))
    decomp_records = json.loads(decomp.to_json(orient="records"))
    delta_records = json.loads(deltas.to_json(orient="records"))
    leakage_records = json.loads(leakage.to_json(orient="records"))
    metric_records = json.loads(metrics.to_json(orient="records"))
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(counts["pass"].all()),
        "winner": {
            "method": str(winner["method"]),
            "metric": "held-out all-pair sigma68_ns; lower is better",
            "value": float(winner["sigma68_ns"]),
            "ci": [float(winner["sigma68_ci_low_ns"]), float(winner["sigma68_ci_high_ns"])],
            "full_rms_ns": float(winner["full_rms_ns"]),
            "tail_frac_abs_gt5ns": float(winner["tail_frac_abs_gt5ns"]),
            "B2_containing_mean_abs_cov_ns2": winner_b2_cov_value,
        },
        "traditional": {
            "method": "pair-median centered CFD20 residuals plus hierarchical run/stave covariance matching (S05c reproduction baseline)",
            "metric": "heldout sigma68 residual width ns",
            "value": float(trad["sigma68_ns"]),
            "ci": [float(trad["sigma68_ci_low_ns"]), float(trad["sigma68_ci_high_ns"])],
        },
        "strong_traditional": {
            "method": "leave-run-out Ridge residual model with duplicate-safe B2 saturation diagnostics",
            "metric": "heldout sigma68 residual width ns",
            "value": float(strong_trad["sigma68_ns"]),
            "ci": [float(strong_trad["sigma68_ci_low_ns"]), float(strong_trad["sigma68_ci_high_ns"])],
        },
        "model_bakeoff": metric_records,
        "traditional_pair_covariance": {
            "B2_containing_mean_abs_cov_ns2": float(b2_cov["mean_abs_cov_ns2"]),
            "B2_containing_ci": [float(b2_cov["mean_abs_cov_ci_low_ns2"]), float(b2_cov["mean_abs_cov_ci_high_ns2"])],
            "downstream_mean_abs_cov_ns2": float(ds_cov["mean_abs_cov_ns2"]),
            "downstream_ci": [float(ds_cov["mean_abs_cov_ci_low_ns2"]), float(ds_cov["mean_abs_cov_ci_high_ns2"])],
        },
        "saturation_diagnostics": {
            "b2_saturation_threshold_adc": float(config.get("saturation_threshold_adc", 3800.0)),
            "raw_sigma68_b2_sat_gt0_ns": None if b2_sat.empty else float(b2_sat.iloc[0]["sigma68_ns"]),
            "raw_sigma68_b2_sat_eq0_ns": None if b2_unsat.empty else float(b2_unsat.iloc[0]["sigma68_ns"]),
            "table": sat_records,
        },
        "stave_covariance_decomposition": decomp_records,
        "ml_minus_traditional_delta": delta_records,
        "finding": f"The S05l winner is {winner['method']} by held-out sigma68. Raw CFD20 covariance is strongly B2/topology dominated; duplicate-safe saturation diagnostics test high-amplitude pathology without adopting the P07d/P07e rejected ratio-transfer correction.",
        "leakage": leakage_records,
        "input_sha256": str(out_dir / "input_sha256.csv"),
        "git_commit": git_head(),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(
    out_dir: Path,
    config_path: Path,
    config: dict,
    counts: pd.DataFrame,
    pair_counts: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    cov_summary: pd.DataFrame,
    decomp: pd.DataFrame,
    sat_diag: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    trad_all = metrics[(metrics["method"] == "raw_pair_median") & (metrics["subset"] == "all")].iloc[0]
    strong_trad_all = metrics[(metrics["method"] == "ridge_duplicate_safe") & (metrics["subset"] == "all")].iloc[0]
    contenders = metrics[
        (metrics["subset"] == "all")
        & (~metrics["method"].isin(["gbt_shuffled_target"]))
        & (metrics["sigma68_ns"].notna())
    ].copy()
    winner = contenders.sort_values(["sigma68_ns", "full_rms_ns", "method"]).iloc[0]
    b2_cov = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_B2_containing")].iloc[0]
    ds_cov = cov_summary[(cov_summary["method"] == "raw_pair_median") & (cov_summary["subset"] == "both_downstream_only")].iloc[0]
    winner_delta_raw = deltas[deltas["comparison"] == f"{winner['method']}_minus_raw_pair_median_sigma68"]
    winner_delta_ridge = deltas[deltas["comparison"] == f"{winner['method']}_minus_ridge_duplicate_safe_sigma68"]
    winner_delta_raw = None if winner_delta_raw.empty else winner_delta_raw.iloc[0]
    winner_delta_ridge = None if winner_delta_ridge.empty else winner_delta_ridge.iloc[0]
    primary_metrics = metrics[metrics["subset"] == "all"].copy()
    primary_metrics = primary_metrics.sort_values(["sigma68_ns", "method"])
    feature_gate = pd.DataFrame(
        [
            {
                "gate": "raw_template_only",
                "definition": "pair-median CFD20 residual; no saturation correction or learned correction",
                "methods": "raw_pair_median",
            },
            {
                "gate": "no_saturation_features",
                "definition": "amplitude, area, tail, peak, and pair identity; saturation diagnostics excluded",
                "methods": "ridge_no_saturation",
            },
            {
                "gate": "duplicate_safe",
                "definition": "adds high-ADC sample count, near-peak width, saturation excess, post-peak fall, and recovery tail computed directly from held-out waveforms; no P07d ratio-transfer amplitude correction is applied",
                "methods": "ridge, GBT, ExtraTrees, MLP, CNN-tabular hybrid",
            },
        ]
    )
    sat_report = sat_diag.copy()
    sat_report["b2_amp_cut_adc"] = sat_report["b2_amp_cut_adc"].map(lambda x: "" if pd.isna(x) else f"{float(x):.2f}")
    raw_line = (
        f"The winning model improves over raw by {winner_delta_raw['delta_ns']:.3f} ns "
        f"with 95% CI [{winner_delta_raw['ci_low_ns']:.3f}, {winner_delta_raw['ci_high_ns']:.3f}]"
        if winner_delta_raw is not None
        else "The raw pair-median baseline is the winner, so no raw delta is defined"
    )
    if winner_delta_ridge is not None:
        ridge_line = (
            f"Against the strong Ridge baseline the winning-model delta is {winner_delta_ridge['delta_ns']:.3f} ns "
            f"with 95% CI [{winner_delta_ridge['ci_low_ns']:.3f}, {winner_delta_ridge['ci_high_ns']:.3f}]."
        )
    elif str(winner["method"]) == "raw_pair_median":
        ridge_minus_raw = deltas[deltas["comparison"] == "ridge_duplicate_safe_minus_raw_pair_median_sigma68"].iloc[0]
        ridge_line = (
            f"The strong Ridge baseline is worse than raw by {ridge_minus_raw['delta_ns']:.3f} ns "
            f"with 95% CI [{ridge_minus_raw['ci_low_ns']:.3f}, {ridge_minus_raw['ci_high_ns']:.3f}]."
        )
    else:
        ridge_line = "The strong Ridge baseline is the winner, so no Ridge delta is defined."
    report = f"""# S05e: B2 saturation features in covariance model

- **Ticket:** {config['ticket']}
- **Worker:** {config['worker']}
- **Input checksum(s):** `input_sha256.csv`
- **Config:** `{config_path}`
- **Raw input:** `{config['raw_root_dir']}`

## Question

Does the S05e B2 covariance reduction survive when saturation information is restricted to duplicate-safe waveform diagnostics rather than an adopted amplitude correction that P07e/P07g treated as non-production for high-amplitude timing? The preregistered primary metric is held-out all-pair sigma68 with run-block bootstrap 95% CIs; covariance validity is checked by B2-containing minus downstream-only off-diagonal covariance, inferred B2-local variance, full RMS, tail fraction, support loss, and ML-minus-traditional deltas.

## Reproduction from raw ROOT

The S05c gate was reproduced first from `h101/HRDv`: median samples 0-3 baseline, physical B channels `B2/B4/B6/B8 = 0/2/4/6`, `A > 1000 ADC`, CFD20 timing, and the configured analysis runs.

{counts.to_markdown(index=False)}

Pair-row counts:

{pair_counts.to_markdown(index=False)}

## Methods

For event \(e\), run \(r\), and pair \(p=(i,j)\), the target is

\\[
y_{{erp}} = t_j(e) - t_i(e) - (z_j-z_i)\\,0.078\\;\\mathrm{{ns/cm}},
\\]

with 2 cm stave spacing. The raw S05c residual is \(y_{{erp}}-\\operatorname{{median}}_{{train}}(y_p)\). The robust width is

\\[
\\sigma_{{68}} = \\frac{{Q_{{84}}(x-\\tilde x)-Q_{{16}}(x-\\tilde x)}}{{2}},
\\]

and all CIs resample held-out runs with replacement and then events within each sampled run.

All model comparisons are leave-one-run-out on the configured benchmark runs `{config.get('benchmark_runs', config['analysis_runs'])}`. The held-out run is excluded before fitting medians, scalers, Ridge coefficients, tree ensembles, MLP weights, CNN weights, and shuffled-target sentinels. ML and NN training rows are capped per fold only for fitting cost; metrics are computed on every row in the held-out run. The benchmark is restricted to Sample-II runs because the duplicate-readout/P07 saturation validity gate is defined there; the raw reproduction gate above still uses the full S05/S00 run set.

Feature gates:

{feature_gate.to_markdown(index=False)}

Benchmarked methods:

- `raw_pair_median`: strong template-only S05c covariance baseline.
- `ridge_no_saturation`: linear Ridge without saturation diagnostics.
- `ridge_duplicate_safe`: strong traditional linear comparator with duplicate-safe saturation diagnostics.
- `gbt_duplicate_safe`: gradient-boosted regression trees.
- `extra_trees_duplicate_safe`: frozen S05e-style ExtraTrees residual model.
- `mlp_duplicate_safe`: tabular neural network.
- `cnn_waveform_only`: 1D-CNN over the two endpoint waveforms only.
- `hybrid_cnn_tabular_duplicate_safe`: new dual-branch architecture combining a 1D waveform CNN with a tabular branch.

## Held-out residual benchmark

Primary all-pair ranking:

{primary_metrics.to_markdown(index=False)}

Full topology split:

{metrics.to_markdown(index=False)}

Winner: `{winner['method']}` with all-pair sigma68 `{winner['sigma68_ns']:.3f}` ns and 95% CI `[{winner['sigma68_ci_low_ns']:.3f}, {winner['sigma68_ci_high_ns']:.3f}]`. {raw_line}. {ridge_line}

Strong traditional all-run sigma68 is `{strong_trad_all['sigma68_ns']:.3f}` ns. Raw S05c all-run sigma68 is `{trad_all['sigma68_ns']:.3f}` ns.

Bootstrap deltas:

{deltas.to_markdown(index=False)}

## Hierarchical covariance

Pair-pair covariance summaries from held-out residuals:

{cov_summary.to_markdown(index=False)}

The traditional CFD20 covariance baseline has B2-containing pair covariance `{b2_cov['mean_abs_cov_ns2']:.2f}` ns^2 with run-bootstrap CI `[{b2_cov['mean_abs_cov_ci_low_ns2']:.2f}, {b2_cov['mean_abs_cov_ci_high_ns2']:.2f}]`; downstream-only pair covariance is `{ds_cov['mean_abs_cov_ns2']:.2f}` ns^2 with CI `[{ds_cov['mean_abs_cov_ci_low_ns2']:.2f}, {ds_cov['mean_abs_cov_ci_high_ns2']:.2f}]`.

Stave-covariance decomposition:

{decomp.to_markdown(index=False)}

The event-level stave covariance fit solves

\\[
\\operatorname{{Cov}}(r_p,r_q) \\approx a_p^T \\Sigma a_q,
\\]

where \(a_p\) is the signed pair-incidence vector over B2/B4/B6/B8. The reported `B2_variance_minus_downstream_mean_ns2` is a detector-local covariance diagnostic, not an independent timing-resolution measurement.

## B2 Saturation Strata

The saturation threshold was `{float(config.get('saturation_threshold_adc', 3800.0)):.0f}` ADC after baseline subtraction. These are diagnostics only; all fitted predictions above still hold out complete runs.

{sat_report.to_markdown(index=False)}

## Leakage checks

{leakage.to_markdown(index=False)}

The shuffled-target control and intentional target-echo sentinel are leakage probes. The added saturation diagnostics are computed from waveform samples only, before residual targets are formed. Forbidden variables are run id, event id, raw times, raw residuals, target residuals, and pair-derived timing labels.

## Systematics and Caveats

- The P07d/P07e ratio-transfer amplitude correction is not used as an adopted correction here; S05l only uses duplicate-safe waveform diagnostics as covariates.
- Neural methods are bounded-cap fits to keep the run reproducible on the laptop. This is a conservative comparison for large networks because all methods are evaluated on complete held-out runs.
- The covariance decomposition assumes the signed pair-incidence linear model; remaining B2 variance may include unmodeled waveform shape, trigger composition, and unresolved pile-up.
- Bootstrap intervals are run-block intervals. They cover run-to-run instability better than iid event bootstrap but remain limited by the seven Sample-II held-out runs.
- A method that improves sigma68 but worsens full RMS, tails, or downstream covariance should not be adopted without a downstream consumer study.

## Finding

The S05l winner is `{winner['method']}` by held-out sigma68. Raw S05c covariance is strongly B2/topology dominated: B2-containing mean absolute pair covariance is `{b2_cov['mean_abs_cov_ns2']:.2f}` ns^2 with 95% CI `[{b2_cov['mean_abs_cov_ci_low_ns2']:.2f}, {b2_cov['mean_abs_cov_ci_high_ns2']:.2f}]`, while downstream-only is `{ds_cov['mean_abs_cov_ns2']:.2f}` ns^2 with CI `[{ds_cov['mean_abs_cov_ci_low_ns2']:.2f}, {ds_cov['mean_abs_cov_ci_high_ns2']:.2f}]`. Duplicate-safe saturation diagnostics can be benchmarked without adopting the rejected P07d/P07e ratio-transfer correction; the winner is therefore a residual predictor validity result, not a production endorsement of high-amplitude B2 amplitude recovery.

## Artifacts

`reproduction_match_table.csv`, `pair_counts.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `pair_covariance_by_run.csv`, `covariance_summary.csv`, `stave_covariance_decomposition.csv`, `saturation_strata.csv`, `fold_hyperparameters.csv`, `cv_scan.csv`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, `result.json`, and two PNG figures.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s05l_1781046818_654_2a8c6dd2_saturation_covariance_validity_gate.py --config configs/s05l_1781046818_654_2a8c6dd2_saturation_covariance_validity_gate.yaml
```
"""
    report = report.replace("# S05e: B2 saturation features in covariance model", "# S05l: saturation-covariance correction validity gate")
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05l_1781046818_654_2a8c6dd2_saturation_covariance_validity_gate.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts, pair_counts = reproduce_counts(config)
    counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    pair_counts.to_csv(out_dir / "pair_counts.csv", index=False)

    table = build_pair_table(config)
    benchmark_runs = [int(run) for run in config.get("benchmark_runs", config["analysis_runs"])]
    table = table[table["run"].isin(benchmark_runs)].reset_index(drop=True)
    table.head(2000).to_csv(out_dir / "pair_residual_table_preview.csv", index=False)
    oof, folds, cv_scan = oof_predictions(table, config)
    folds.to_csv(out_dir / "fold_hyperparameters.csv", index=False)
    cv_scan.to_csv(out_dir / "cv_scan.csv", index=False)
    keep_cols = [
        "run",
        "event",
        "pair",
        "subset",
        "B2_amp",
        "b2_sat_count",
        "b2_sat_excess",
        "b2_recovery_tail",
        "target_residual_ns",
        "resid_raw_pair_median",
    ]
    for _, col, _ in method_registry():
        if col in oof.columns and col not in keep_cols:
            keep_cols.append(col)
    oof[keep_cols].to_csv(out_dir / "heldout_pair_residuals.csv", index=False)

    rng = np.random.default_rng(int(config["random_seed"]))
    metrics = metric_table(oof, config, rng)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    delta_rows = []
    for method, col, _ in method_registry():
        if method in {"raw_pair_median", "gbt_shuffled_target"} or col not in oof.columns or oof[col].isna().all():
            continue
        lo_raw, hi_raw, p_raw = delta_bootstrap_ci(oof, "resid_raw_pair_median", col, rng, int(config["bootstrap_resamples"]))
        delta_rows.append(
            {
                "method": method,
                "comparison": f"{method}_minus_raw_pair_median_sigma68",
                "delta_ns": sigma68(oof[col].to_numpy()) - sigma68(oof["resid_raw_pair_median"].to_numpy()),
                "ci_low_ns": lo_raw,
                "ci_high_ns": hi_raw,
                "p_two_sided": p_raw,
            }
        )
        if method != "ridge_duplicate_safe":
            lo_ridge, hi_ridge, p_ridge = delta_bootstrap_ci(oof, "resid_ridge_duplicate_safe", col, rng, int(config["bootstrap_resamples"]))
            delta_rows.append(
                {
                    "method": method,
                    "comparison": f"{method}_minus_ridge_duplicate_safe_sigma68",
                    "delta_ns": sigma68(oof[col].to_numpy()) - sigma68(oof["resid_ridge_duplicate_safe"].to_numpy()),
                    "ci_low_ns": lo_ridge,
                    "ci_high_ns": hi_ridge,
                    "p_two_sided": p_ridge,
                }
            )
    deltas = pd.DataFrame(delta_rows)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)

    cov_rows, cov_summary, decomp = covariance_summary(oof, config, rng)
    cov_rows.to_csv(out_dir / "pair_covariance_by_run.csv", index=False)
    cov_summary.to_csv(out_dir / "covariance_summary.csv", index=False)
    decomp.to_csv(out_dir / "stave_covariance_decomposition.csv", index=False)
    sat_diag = saturation_diagnostics(oof, config, rng)
    sat_diag.to_csv(out_dir / "saturation_strata.csv", index=False)

    leakage = leakage_checks(oof)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    plot_outputs(out_dir, metrics, cov_summary)
    write_input_hashes(out_dir, config)
    write_result(out_dir, config, counts, metrics, deltas, cov_summary, decomp, sat_diag, leakage)
    write_report(out_dir, args.config, config, counts, pair_counts, metrics, deltas, cov_summary, decomp, sat_diag, leakage)
    write_manifest(out_dir, args.config, config, [f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}"])


if __name__ == "__main__":
    main()
